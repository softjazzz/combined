"""人工确认边界的合成保护：四状态经真实发布、隔离保存、读取和三种导出。"""

import csv
from datetime import datetime
from io import StringIO
import json
from pathlib import Path

from openpyxl import load_workbook
import pytest
from sqlalchemy import MetaData, create_engine
from sqlalchemy.orm import Session

from app.services import custom_qc_workspace_service as workspace
from app.services.luxian_0609.extended_document.discharge_medication_extraction import SCHEMA_VERSION
from app.services.qc_workspace.canonical_result_store import CanonicalResultStore, envelope_item_from_rule_result
from test_luxian_0609_discharge_medication_integration import FakeClient, _payload, _run, TEXT


MANIFEST = json.loads((Path(__file__).parents[1] / "fixtures/qc_confirmed_cases/delivery-v1.json").read_text(encoding="utf8"))
pytestmark = pytest.mark.usefixtures("workspace_tables_without_database")


async def first_course_with_clinical_context():
    from app.services.luxian_0609.course_quality.rule_077 import evaluate_rule_077, RULE_ID
    from app.services.luxian_0609.evidence_snapshot_provider import SnapshotSourceRows, build_luxian_0609_evidence_read_session
    from app.services.luxian_0609.decision_reducer import reduce_luxian_0609_rule_decision
    from app.services.luxian_0609.canonical_result_finalizer import finalize_luxian_0609_reduced_customer_result

    row = {"document_id": "synthetic-first-course", "first_diagnosis": "桡骨骨折", "differential_diagnosis": "脑出血：结合头部外伤和意识改变鉴别。",
           "case_characteristic": "同次外伤存在头部包块及短暂意识改变。", "diagnose_based_on": "外伤后腕部影像提示桡骨骨折。"}
    def reader(**kwargs):
        return SnapshotSourceRows.create(source_key=kwargs["source_key"], rows=[row] if kwargs["source_key"] == "first_course_record" else [], truncated=False, limit_rows=50)
    session = build_luxian_0609_evidence_read_session(selected_rule_ids=(RULE_ID,), institute_id="synthetic-hospital", patient_id="synthetic-patient", visit_id="synthetic-visit", source_schema=None, created_at="2026-10-24T08:00:00+08:00", row_reader=reader)
    class Client:
        async def generate(self, prompt, **kwargs):
            assert "头部包块及短暂意识改变" in prompt and "不要求鉴别诊断与第一诊断逐病名" in prompt
            return {"content": json.dumps({"relation_state": "related", "rationale_code": "same_clinical_problem", "medical_analysis": "首诊为肢体骨折，同次外伤存在头部包块及意识改变，鉴别脑出血解释相关临床问题。", "evidence_quote": "头部包块及短暂意识改变"}), "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15}}
    result = await evaluate_rule_077(snapshot=session.snapshot, materials=session.materials, llm_client=Client())
    return finalize_luxian_0609_reduced_customer_result(decision=reduce_luxian_0609_rule_decision(result.decision), raw_customer_display_facts=None, evidence_snapshot=session.snapshot, evidence_materials=session.materials)


def test_protection_is_explicit_about_four_states_and_not_full_clinical_signoff():
    assert {case["expected_status"] for case in MANIFEST["cases"]} == {"compliant", "non_compliant", "data_gap", "not_applicable"}
    assert MANIFEST["clinical_full_case_signoff"] is False
    assert {case["sample"] for case in MANIFEST["confirmed_boundaries"]} >= {"C23", "C14", "C11", "C04", "C06"}


@pytest.mark.asyncio
@pytest.mark.parametrize("case", MANIFEST["cases"], ids=lambda case: case["id"])
async def test_confirmed_pattern_survives_publication_sqlite_read_and_exports(case):
    scenario = case["scenario"]
    text = TEXT.replace("口服", "服用") if scenario == "missing_route" else TEXT
    payload = _payload(missing_route=scenario == "missing_route", uncertain=scenario == "uncertain")
    if scenario == "absent":
        text = "出院无带药，注意休息。"
        payload = {"schema_version": SCHEMA_VERSION, "state": "no_medications", "items": []}
    if scenario == "first_course_context":
        published = await first_course_with_clinical_context()
    elif scenario == "pathology_senior":
        from test_luxian_0609_pathology_event_association import _rows, _run as pathology_run
        rows = _rows()
        rows["senior_course_record"] = rows.pop("daily_course_record")
        rows["senior_course_record"][0]["submit_time"] = rows["senior_course_record"][0].pop("record_time")
        published = await pathology_run(rows, case["rule_id"])
        assert any(row["source_type"] == "senior_course_record" for row in published["customer_evidence"])
    else:
        _, published = await _run(FakeClient(payload), text=text)
    assert published["status"] == case["expected_status"]
    published.update(record_id="synthetic-visit", visit_id="synthetic-visit", institute_id="synthetic-hospital", patient_id="synthetic-patient")
    table = workspace._record_result_envelopes_table().to_metadata(MetaData(), schema=None)
    engine = create_engine("sqlite://")
    table.metadata.create_all(engine)
    store = CanonicalResultStore(table)
    with Session(engine) as session:
        store.replace_for_job(session, job_row={"id": case["id"], "created_by": "synthetic-owner", "filters_json": json.dumps({"rule_set_key": "luxian_0609_qc_v1", "rule_set_version": "2026-06-09"})},
            items=[published], now=datetime(2026, 10, 24), projector=lambda row: envelope_item_from_rule_result(row, hmac_key="synthetic-key"), projection_key="synthetic-key")
        session.commit()
        loaded = store.load_selected(session, root_job_id=case["id"], institute_id="synthetic-hospital", patient_id="synthetic-patient", visit_id="synthetic-visit", rule_set_key="luxian_0609_qc_v1", rule_set_version="2026-06-09")
    job = {"id": case["id"], "filters": {"rule_set_key": "luxian_0609_qc_v1"}, "items": loaded["items"]}
    projected = workspace.project_customer_safe_result_item(loaded["items"][0], hmac_key="synthetic-key")
    for key in ("rule_id", "status", "reason_code"):
        assert projected[key] == published[key]
    assert projected.get("customer_display_facts") == published.get("customer_display_facts")
    assert projected["record_ref"] == loaded["record_ref"]
    _, rows, _ = workspace._customer_export_rows(job, hmac_key="synthetic-key")
    expected = rows[0]
    csv_rows = list(csv.reader(StringIO(workspace._export_customer_safe_csv(job, hmac_key="synthetic-key").getvalue())))
    assert any(row[:7] == expected[:7] for row in csv_rows)
    workbook = load_workbook(workspace._export_customer_safe_workbook(job, hmac_key="synthetic-key"))
    assert any(tuple(row[:7]) == tuple(expected[:7]) for row in workbook["全部明细"].values)
    html = workspace._export_customer_safe_html(job, hmac_key="synthetic-key", canonical_items=loaded["items"])
    assert case["rule_id"] in html and expected[3] in html
    engine.dispose()
