"""044申请来源缺口保持资料不足，正式Finalizer不误映射技术错误。"""

from datetime import datetime

import pytest

from app.services.luxian_0609.canonical_result_finalizer import (
    finalize_luxian_0609_reduced_customer_result,
)
from app.services.luxian_0609.decision_binding import (
    bind_and_reduce_luxian_0609_rule_decisions,
)
from app.services.luxian_0609.evidence_snapshot_provider import (
    SnapshotSourceRows,
    SourceEvidenceUnavailable,
    build_luxian_0609_evidence_read_session,
)
from app.services.luxian_0609.native_transfusion_execution import (
    execute_luxian_0609_native_transfusion_rules,
)

RULE = "LX0609-07-01-02"

@pytest.fixture(autouse=True)
def reject_network_and_non_sqlite(monkeypatch):
    import httpx
    from sqlalchemy import event
    from sqlalchemy.engine import Engine

    def blocked_network(*args, **kwargs):
        raise AssertionError("044测试禁止网络调用")

    def sqlite_only(connection, *args):
        assert connection.dialect.name == "sqlite", "044测试禁止非SQLite访问"

    monkeypatch.setattr(httpx.Client, "send", blocked_network)
    monkeypatch.setattr(httpx.AsyncClient, "send", blocked_network)
    event.listen(Engine, "before_cursor_execute", sqlite_only)
    yield
    event.remove(Engine, "before_cursor_execute", sqlite_only)



def sources():
    return {
        "mr_bloodtrans": [{
            "document_id": "E1", "transfution_datetime": datetime(2026, 7, 16, 10),
        }],
        "bloodtrans_record": [{
            "document_id": "D1", "record_time": "2026-07-16 12:10:00",
            "record_content": "输血指征为贫血Hb65g/L，已输注红细胞2U。开始时间10:00，结束时间12:00。生命体征平稳，无输血反应。",
        }],
        "blood_application": [{
            "application_id": "A1", "request_datetime": "2026-07-16 09:00:00",
            "reason_for_blood": "贫血改善携氧能力", "hemoglobin": "65",
        }],
        "daily_course_record": [],
    }


async def formal(rows, *, unavailable=None, truncated=None, forged_facts=None):
    def reader(**kwargs):
        key = kwargs["source_key"]
        if key == unavailable:
            raise SourceEvidenceUnavailable("合成不可用来源")
        return SnapshotSourceRows.create(
            source_key=key, rows=rows.get(key, []),
            truncated=key == truncated, limit_rows=500,
        )

    session = build_luxian_0609_evidence_read_session(
        selected_rule_ids=(RULE,), institute_id="I", patient_id="P", visit_id="V",
        source_schema=None, created_at="2026-07-20T12:00:00+08:00", row_reader=reader,
    )
    execution = await execute_luxian_0609_native_transfusion_rules(
        rule_ids=(RULE,), wrapper_rules=[{"rule_id": RULE}], evidence_payload=None,
        institute_id="I", patient_id="P", visit_id="V", source_schema=None,
        llm_client=None, evidence_materials=session.materials,
        evidence_snapshot=session.snapshot, decision_rule_ids=(RULE,),
    )
    assert execution.llm_call_count == 0
    reduced = bind_and_reduce_luxian_0609_rule_decisions(
        decisions=execution.decisions, expected_rule_ids=(RULE,),
        snapshot=session.snapshot, evidence_materials=session.materials,
    )[0]
    facts = dict(execution.customer_display_facts).get(RULE)
    final = finalize_luxian_0609_reduced_customer_result(
        decision=reduced, raw_customer_display_facts=(
            facts if forged_facts is None else forged_facts
        ), evidence_snapshot=session.snapshot, evidence_materials=session.materials,
    )
    return final, reduced


@pytest.mark.asyncio
async def test_unavailable_application_is_deliverable_data_gap():
    final, reduced = await formal(sources(), unavailable="blood_application")
    assert reduced.final_state.value == "data_gap"
    assert final["status"] == "data_gap"
    assert final["customer_display_facts"] == {
        "failure_kind": "system_data_contract_gap",
        "system_gap_reason": "pretransfusion_assessment_source_unavailable",
        "gap_owner": "system_integration",
    }

@pytest.mark.asyncio
@pytest.mark.parametrize("source_state", ["unavailable", "truncated"])
@pytest.mark.parametrize("event_count", [1, 2])
async def test_application_source_gap_single_and_multiple_events(source_state, event_count):
    rows = sources()
    if event_count == 2:
        rows["mr_bloodtrans"].append({
            "document_id": "E2", "transfution_datetime": datetime(2026, 7, 18, 10),
        })
    options = {source_state: "blood_application"}
    final, _ = await formal(rows, **options)
    assert final["status"] == "data_gap"
    assert final["reason_code"] == "source_unavailable"
    assert final["customer_display_facts"]["gap_owner"] == "system_integration"
    assert "不完整" not in final["findings"]


@pytest.mark.asyncio
@pytest.mark.parametrize("scenario,expected", [
    ("available_application", "compliant"),
    ("complete_empty_without_assessment_signals", "non_compliant"),
    ("missing_application_time", "data_gap"),
    ("late_application", "non_compliant"),
])
async def test_application_complete_source_and_time_boundaries(scenario, expected):
    rows = sources()
    if scenario == "complete_empty_without_assessment_signals":
        rows["blood_application"] = []
        rows["bloodtrans_record"][0]["record_content"] = "已开始输注红细胞2U，输血过程中无不良反应。"
    elif scenario == "missing_application_time":
        rows["blood_application"][0].pop("request_datetime")
    elif scenario == "late_application":
        rows["blood_application"][0]["request_datetime"] = "2026-07-16 11:00:00"
    elif scenario.startswith("second_application"):
        rows["mr_bloodtrans"].append({
            "document_id": "E2", "transfution_datetime": datetime(2026, 7, 18, 10),
        })
        if scenario == "second_application_empty":
            rows["blood_application"].append({
                "application_id": "A2", "request_datetime": "2026-07-18 09:00:00",
                "reason_for_blood": "", "hemoglobin": "",
                "record_content": "第二次输血申请。",
            })
    final, _ = await formal(rows)
    assert final["status"] == expected


@pytest.mark.asyncio
@pytest.mark.parametrize("forged", [
    {"failure_kind": "pretransfusion_assessment_incomplete",
     "performed_transfusion_confirmed": True,
     "checked_fields": ["indication", "laboratory_indicator", "risk_history_or_status"],
     "missing_fields": []},
    {"failure_kind": "system_data_contract_gap", "gap_owner": "system_integration",
     "system_gap_reason": "wrong_rule_reason"},
    {"failure_kind": "system_data_contract_gap", "gap_owner": "clinician",
     "system_gap_reason": "pretransfusion_assessment_source_unavailable"},
    {"failure_kind": "system_data_contract_gap", "gap_owner": "system_integration",
     "system_gap_reason": "pretransfusion_assessment_source_unavailable", "extra": True},
])
async def test_forged_source_gap_facts_still_rejected(forged):
    final, _ = await formal(
        sources(), unavailable="blood_application", forged_facts=forged,
    )
    assert final["status"] == "technical_error"
    assert "customer_display_facts" not in final


@pytest.mark.asyncio
@pytest.mark.parametrize("scenario", ["unavailable", "complete_empty_with_procedure_signals"])
async def test_valid_assessment_result_publish_save_and_new_session_readback(tmp_path, scenario):
    import json
    from datetime import timezone

    from sqlalchemy import MetaData, create_engine, event
    from sqlalchemy.orm import Session

    from app.services import custom_qc_workspace_service as workspace
    from app.services.qc_workspace.canonical_result_store import (
        CanonicalResultStore, envelope_item_from_rule_result,
    )

    rows = sources()
    if scenario == "complete_empty_with_procedure_signals":
        rows["blood_application"] = []
    final, _ = await formal(
        rows, unavailable="blood_application" if scenario == "unavailable" else None,
    )
    assert final["status"] == ("data_gap" if scenario == "unavailable" else "non_compliant")
    table = workspace._record_result_envelopes_table().to_metadata(MetaData(), schema=None)
    engine = create_engine("sqlite:///" + str(tmp_path / "044-source-gap.sqlite"))

    @event.listens_for(engine, "before_cursor_execute")
    def sqlite_only(connection, *args):
        assert connection.dialect.name == "sqlite"

    table.metadata.create_all(engine)
    store = CanonicalResultStore(table)
    raw = {**final, "record_id": "V", "visit_id": "V", "patient_id": "P", "institute_id": "I"}
    expected = envelope_item_from_rule_result(raw, hmac_key="offline-044-test-key")
    job = {
        "id": "offline-044-source-gap", "created_by": "offline-test",
        "filters_json": json.dumps({
            "rule_set_key": "luxian_0609_qc_v1", "rule_set_version": "2026-06-09",
            "scoped_customer_rule_ids": [RULE],
        }),
    }
    with Session(engine) as writing:
        store.replace_for_job(
            writing, job_row=job, items=[raw], now=datetime.now(timezone.utc),
            projector=lambda item: envelope_item_from_rule_result(item, hmac_key="offline-044-test-key"),
            projection_key="offline-044-test-key",
        )
        writing.commit()
    engine.dispose()
    engine = create_engine("sqlite:///" + str(tmp_path / "044-source-gap.sqlite"))
    with Session(engine) as reading:
        loaded = store.load_selected(
            reading, root_job_id=job["id"], institute_id="I", patient_id="P", visit_id="V",
            rule_set_key="luxian_0609_qc_v1", rule_set_version="2026-06-09",
        )["items"][0]
    assert {key: loaded[key] for key in expected if key != "record_ref"} == {
        key: value for key, value in expected.items() if key != "record_ref"
    }
    api = workspace.project_customer_safe_result_item(loaded, hmac_key="offline-044-test-key")
    assert api["customer_display_facts"] == final["customer_display_facts"]
    forged = {**final["customer_display_facts"]}
    if scenario == "unavailable":
        forged["extra"] = True
    else:
        forged["requirement"] = "wrong_requirement"
    with pytest.raises(ValueError):
        with Session(engine) as invalid_writing:
            store.replace_for_job(
                invalid_writing, job_row=job, items=[{
                    **raw, "customer_display_facts": forged,
                }], now=datetime.now(timezone.utc),
                projector=lambda item: envelope_item_from_rule_result(item, hmac_key="offline-044-test-key"),
                projection_key="offline-044-test-key",
            )
    engine.dispose()

@pytest.mark.asyncio
async def test_complete_empty_application_cannot_borrow_procedure_signals_as_preassessment():
    rows = sources()
    rows["blood_application"] = []
    final, reduced = await formal(rows)
    assert reduced.final_state.value == "non_compliant"
    assert final["status"] == "non_compliant"
    assert final["customer_display_facts"] == {
        "failure_kind": "transfusion_requirement_not_documented",
        "requirement": "pretransfusion_assessment",
        "checked_sources": ["bloodtrans_record", "blood_application", "course_record"],
    }
    assert "missing_fields" not in final["customer_display_facts"]

@pytest.mark.asyncio
async def test_existing_application_with_empty_fields_remains_field_incomplete():
    rows = sources()
    rows["blood_application"][0].update(reason_for_blood="", hemoglobin="")
    final, _ = await formal(rows)
    assert final["status"] == "non_compliant"
    assert final["customer_display_facts"]["failure_kind"] == "pretransfusion_assessment_incomplete"
    assert final["customer_display_facts"]["missing_fields"] == [
        "application_reason", "laboratory_indicator",
    ]


@pytest.mark.asyncio
async def test_independent_course_preassessment_can_satisfy_empty_application_source():
    rows = sources()
    rows["blood_application"] = []
    rows["daily_course_record"] = [{
        "document_id": "PRE1", "record_time": "2026-07-16 09:00:00",
        "record_content": "输血前评估：输血指征为贫血Hb65g/L，既往无输血不良反应，患者生命体征平稳。",
    }]
    final, _ = await formal(rows)
    assert final["status"] == "compliant"
    assert final["customer_display_facts"]["verification_kind"] == "pretransfusion_assessment_complete"




@pytest.mark.asyncio
async def test_explicit_missing_assessment_uses_record_absence_not_fabricated_fields():
    rows = sources()
    rows["blood_application"] = []
    rows["daily_course_record"] = [{
        "document_id": "M1", "record_content": "未记录输血前评估。",
    }]
    final, _ = await formal(rows)
    assert final["status"] == "non_compliant"
    assert final["customer_display_facts"]["failure_kind"] == "transfusion_requirement_not_documented"
    assert "missing_fields" not in final["customer_display_facts"]
