"""CT-04：无成熟触发时，已存在讨论资料不改变原生NA裁决。"""
from datetime import datetime
import json

import pytest

from app.services.luxian_0609.canonical_result_finalizer import finalize_luxian_0609_executor_customer_display_facts
from app.services.luxian_0609.difficult_case_result_mapping import safe_difficult_case_customer_display_facts
from app.services.luxian_0609_result_aggregator import aggregate_luxian_0609_results
from test_luxian_0609_native_extended_document_execution import _evaluate_selected

RULE = "LX0609-03-02-01"
ADMISSION = "2026-06-01 08:00:00"
YOUNG = "2026-06-02 09:00:00"
MATURE = "2026-06-08 09:00:00"
OLD = "uncertain_diagnosis_discussion_check"
MISSING = object()


@pytest.fixture(autouse=True)
def no_external_access(monkeypatch):
    import httpx
    import socket
    from sqlalchemy import event
    from sqlalchemy.engine import Engine

    def blocked(*args, **kwargs):
        raise AssertionError("CT04禁止PG、网络及真实模型")

    def sqlite_only(connection, *args):
        assert connection.dialect.name == "sqlite"

    monkeypatch.setattr(socket, "create_connection", blocked)
    monkeypatch.setattr(httpx.Client, "send", blocked)
    monkeypatch.setattr(httpx.AsyncClient, "send", blocked)
    event.listen(Engine, "before_cursor_execute", sqlite_only)
    yield
    event.remove(Engine, "before_cursor_execute", sqlite_only)


class ForbiddenModel:
    async def generate(self, *args, **kwargs):
        raise AssertionError("050 program_only/0不得调用模型")


def sources(*, body="合成正文", count=1, time=YOUNG, text="目前诊断仍不明确。"):
    discussions = []
    for index in range(count):
        row = {"document_id": f"SYN-D{index}", "record_time": MATURE}
        if body is not MISSING:
            row["record_content"] = body[index] if isinstance(body, tuple) else body
        discussions.append(row)
    course = {"document_id": "SYN-COURSE", "record_content": text}
    if time is not None:
        course["record_time"] = time
    return {"inpat_registration": [{"admission_datetime": ADMISSION}],
            "daily_course_record": [course], "diffcase_discussion_record": discussions}


async def evaluate(rows):
    snapshot, materials, execution, reduced = await _evaluate_selected((RULE,), rows, llm_client=ForbiddenModel())
    results = aggregate_luxian_0609_results(
        wrapper_rules=[{"rule_id": RULE}], execution_results=[], reduced_decisions=reduced,
        customer_display_facts=execution.customer_display_facts,
        audit_context={"evidence_snapshot": snapshot, "evidence_materials": materials},
    )
    assert execution.llm_call_count == execution.total_tokens == 0
    return snapshot, materials, execution, reduced[0], results[0]


NATIVE_CASES = [
    ("N01_valid", {}, "not_applicable", "trigger_absent_complete", OLD),
    ("N02_missing", {"body": MISSING}, "not_applicable", "trigger_absent_complete", OLD),
    ("N03_blank", {"body": " \t\n "}, "not_applicable", "trigger_absent_complete", OLD),
    ("N04_nonstring", {"body": 123}, "not_applicable", "trigger_absent_complete", OLD),
    ("N05_multiple", {"count": 2, "body": ("合成正文", " ")}, "not_applicable", "trigger_absent_complete", OLD),
    ("N06_no_discussion", {"count": 0}, "not_applicable", "trigger_absent_complete", OLD),
    ("N07_no_candidate", {"text": "目前诊断已明确。", "time": MATURE}, "not_applicable", "trigger_absent_complete", OLD),
    ("N08_exact_nc", {"time": "2026-06-08 08:00:00", "count": 0}, "non_compliant", "required_document_missing", OLD),
    ("N09_exact_c", {"time": "2026-06-08 08:00:00"}, "compliant", "requirement_satisfied", OLD),
    ("N10_time_gap", {"time": None}, "data_gap", "authoritative_time_missing", "uncertain_diagnosis_course_time_gap"),
    ("N11_local", {"time": MATURE, "text": "患者发热原因待查，当前诊断为社区获得性肺炎。"}, "uncertain", "diagnosis_scope_uncertain", "uncertain_diagnosis_scope_unverified"),
    ("N12_body_gap", {"time": MATURE, "body": " "}, "data_gap", "required_field_missing", "uncertain_diagnosis_discussion_body_gap"),
]


@pytest.mark.asyncio
@pytest.mark.parametrize("case,arguments,status,reason,kind", NATIVE_CASES, ids=[c[0] for c in NATIVE_CASES])
async def test_ct04_frozen_native_and_public_status_alignment(case, arguments, status, reason, kind):
    _, _, _, reduced, result = await evaluate(sources(**arguments))
    assert {"evaluation_unknown": "uncertain"}.get(reduced.final_state.value, reduced.final_state.value) == status
    assert reduced.reason_code == reason
    assert result["status"] == status
    assert result["reason_code"] == reason
    facts = result["customer_display_facts"]
    assert facts["verification_kind"] == kind
    assert facts["discussion_count"] == arguments.get("count", 1)
    if status == "not_applicable":
        assert facts == {"verification_kind": OLD, "admission_time": ADMISSION,
                         "uncertain_record_times": [], "discussion_count": arguments.get("count", 1)}
        assert "本质控点不适用" in result["findings"]
        assert "已完成讨论" not in result["findings"]
        assert "未见疑难病例讨论" not in result["findings"]
        assert result.get("customer_evidence", []) == []


def facts(records, count, kind=OLD, **extra):
    return {"verification_kind": kind, "admission_time": ADMISSION,
            "uncertain_record_times": records, "discussion_count": count, **extra}


PUBLIC_CASES = [
    ("C01", facts([], 0), "not_applicable", True),
    ("C02", facts([], 1), "not_applicable", True),
    ("C03", facts([], 2), "not_applicable", True),
    ("C04", facts([MATURE], 0), "not_applicable", False),
    ("C05", facts([MATURE], 1), "not_applicable", False),
    ("C06", facts([], 1), "compliant", False),
    ("C07", facts([], 0), "non_compliant", False),
    ("C08", facts([MATURE], 0), "non_compliant", True),
    ("C09", facts([MATURE], 1), "compliant", True),
    ("C10", facts([MATURE], 0), "compliant", False),
    ("C11", facts([MATURE], 1), "non_compliant", False),
    ("C12", facts([], 1, candidate_course_time_gap_count=1), "not_applicable", False),
    ("C13", facts([], 1, "uncertain_diagnosis_course_time_gap", candidate_course_time_gap_count=1), "not_applicable", False),
    ("C14", facts([MATURE], 1, "uncertain_diagnosis_discussion_body_gap", discussion_body_gap_count=1), "not_applicable", False),
    ("C15", facts([MATURE], 1, "uncertain_diagnosis_scope_unverified"), "not_applicable", False),
]


@pytest.mark.parametrize("case,raw,status,accept", PUBLIC_CASES, ids=[c[0] for c in PUBLIC_CASES])
def test_ct04_frozen_real_finalizer_contract(case, raw, status, accept):
    reason = {"not_applicable": "trigger_absent_complete", "compliant": "requirement_satisfied",
              "non_compliant": "required_document_missing"}[status]
    result, handled = finalize_luxian_0609_executor_customer_display_facts(
        result={"rule_id": RULE, "status": status, "reason_code": reason}, raw_facts=raw,
    )
    assert handled
    if accept:
        assert result["status"] == status and result["reason_code"] == reason
        assert result["customer_display_facts"] == raw
    else:
        assert result["status"] == "technical_error"
        assert result["reason_code"] == "model_invalid_output"
        assert not result.get("customer_display_facts")


@pytest.mark.parametrize("count", [-1, True, False, 1.5, "1", None])
def test_na_relaxation_does_not_allow_invalid_discussion_counts(count):
    raw = facts([], count)
    assert safe_difficult_case_customer_display_facts(rule_id=RULE, raw=raw) is None
    result, _ = finalize_luxian_0609_executor_customer_display_facts(
        result={"rule_id": RULE, "status": "not_applicable", "reason_code": "trigger_absent_complete"}, raw_facts=raw,
    )
    assert result["status"] == "technical_error"


def test_na_relaxation_preserves_extra_internal_field_filtering():
    raw = {**facts([], 1), "raw_text": "PRIVATE", "document_id": "PRIVATE-ID"}
    result, _ = finalize_luxian_0609_executor_customer_display_facts(
        result={"rule_id": RULE, "status": "not_applicable", "reason_code": "trigger_absent_complete"}, raw_facts=raw,
    )
    assert result["status"] == "not_applicable"
    assert result["customer_display_facts"] == facts([], 1)


@pytest.mark.asyncio
async def test_synthetic_new_sqlite_instance_preserves_na_positive_count_without_fake_evidence(tmp_path):
    from sqlalchemy import MetaData, create_engine
    from sqlalchemy.orm import Session
    import app.services.custom_qc_workspace_service as workspace
    from app.services.qc_workspace.canonical_result_store import CanonicalResultStore, envelope_item_from_rule_result

    snapshot, materials, execution, reduced, result = await evaluate(sources())
    assert reduced.final_state.value == result["status"] == "not_applicable"
    assert result["reason_code"] == "trigger_absent_complete"
    assert len(materials.document_rows("diffcase_discussion_record", snapshot=snapshot)) == 1
    assert any(ob.snapshot_ref.removeprefix("sha256:") in execution.decisions[0].fact_refs
               for ob in snapshot.observations if ob.source_key == "diffcase_discussion_record")
    assert result.get("customer_evidence", []) == []
    item = {**result, "record_id": "V", "visit_id": "V", "institute_id": "I", "patient_id": "P"}
    table = workspace._record_result_envelopes_table().to_metadata(MetaData(), schema=None)
    url = "sqlite:///" + (tmp_path / "ct04.sqlite").as_posix()
    engine = create_engine(url)
    table.metadata.create_all(engine)
    try:
        with Session(engine) as write_db:
            CanonicalResultStore(table).replace_for_job(
                write_db, job_row={"id": "J", "created_by": "synthetic-reviewer",
                    "filters_json": json.dumps({"rule_set_key": "luxian_0609_qc_v1", "rule_set_version": "2026-06-09"})},
                items=[item], now=datetime(2026, 10, 8, 12),
                projector=lambda raw: envelope_item_from_rule_result(raw, hmac_key="test-key"), projection_key="test-key",
            )
            write_db.commit()
        engine.dispose()
        engine = create_engine(url)
        with Session(engine) as read_db:
            saved = CanonicalResultStore(table).load_selected(
                read_db, root_job_id="J", institute_id="I", patient_id="P", visit_id="V",
                rule_set_key="luxian_0609_qc_v1", rule_set_version="2026-06-09",
            )["items"][0]
            for key in ("status", "reason_code", "customer_display_facts", "findings", "suggestion"):
                assert saved.get(key) == item.get(key)
            projected = workspace.project_customer_safe_result_item(saved, hmac_key="test-key")
            assert projected["status"] == "not_applicable"
            assert projected["customer_display_facts"] == facts([], 1)
            assert projected["evidence"] == []
    finally:
        engine.dispose()
