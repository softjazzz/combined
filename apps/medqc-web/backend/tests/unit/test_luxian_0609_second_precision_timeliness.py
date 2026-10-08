"""秒级时限裁决须穿过正式 Finalizer，并保留可保存的精确事实。"""
from __future__ import annotations

from datetime import datetime, timedelta
import json

import pytest

from app.services.luxian_0609.canonical_result_finalizer import (
    finalize_luxian_0609_reduced_customer_result,
    validate_luxian_0609_published_customer_display_facts,
)
from app.services.luxian_0609.decision_binding import (
    bind_and_reduce_luxian_0609_rule_decisions,
)
from app.services.luxian_0609.evidence_snapshot_provider import (
    SnapshotSourceRows,
    build_luxian_0609_evidence_read_session,
)
from app.services.luxian_0609.native_surgery_gate_execution import (
    execute_luxian_0609_native_surgery_gate_rules,
)

from app.services.luxian_0609.native_course_quality_execution import (
    execute_luxian_0609_native_course_quality_rules,
)
from app.services.luxian_0609.source_evidence_reader import (
    CURRENT_VISIT_DISCHARGE_HORIZON_SOURCE_KEY,
)

SURGERY_RULE = "LX0609-04-02-01"
COURSE_RULE = "LX0609-02-01-03"


def session_for(rule, rows):
    def reader(**kwargs):
        source = kwargs["source_key"]
        return SnapshotSourceRows.create(
            source_key=source, rows=rows.get(source, ()),
            truncated=False, limit_rows=50,
        )

    return build_luxian_0609_evidence_read_session(
        selected_rule_ids=(rule,), institute_id="I", patient_id="P", visit_id="V",
        source_schema=None, created_at="2026-01-08T12:00:00+08:00",
        evaluation_as_of_date="2026-01-08", row_reader=reader,
    )


async def run_surgery(record_time):
    rows = {"mr_surgery": [{
        "surgery_name": "左侧手术", "surgeon": "甲", "surgical_level": "二级",
        "surgery_begin_datetime": datetime(2026, 1, 1, 8),
        "surgery_end_datetime": datetime(2026, 1, 1, 10),
    }], "surgery_record": [{
        "document_id": "S1", "surgery_name": "左侧手术", "surgeon": "甲",
        "surgery_begin_time": datetime(2026, 1, 1, 8),
        "surgery_end_time": datetime(2026, 1, 1, 10),
        "record_time": record_time,
    }]}
    session = session_for(SURGERY_RULE, rows)
    execution = await execute_luxian_0609_native_surgery_gate_rules(
        rule_ids=(SURGERY_RULE,), decision_rule_ids=(SURGERY_RULE,),
        wrapper_rules=[{"rule_id": SURGERY_RULE}], evidence_payload=None,
        institute_id="I", patient_id="P", visit_id="V", source_schema=None,
        evidence_snapshot=session.snapshot, evidence_materials=session.materials,
        llm_client=None,
    )
    reduced = bind_and_reduce_luxian_0609_rule_decisions(
        decisions=execution.decisions, expected_rule_ids=(SURGERY_RULE,),
        snapshot=session.snapshot, evidence_materials=session.materials,
    )[0]
    final = finalize_luxian_0609_reduced_customer_result(
        decision=reduced,
        raw_customer_display_facts=dict(execution.customer_display_facts).get(SURGERY_RULE),
        evidence_snapshot=session.snapshot, evidence_materials=session.materials,
    )
    assert execution.llm_call_count == 0
    return reduced, final


@pytest.mark.asyncio
async def test_surgery_one_second_late_survives_finalizer_with_exact_duration():
    reduced, final = await run_surgery(datetime(2026, 1, 2, 10, 0, 1))
    assert reduced.final_state.value == "non_compliant"
    assert (final["status"], final["reason_code"]) == ("non_compliant", "threshold_exceeded")
    assert final["customer_display_facts"]["elapsed_seconds"] == 86401


async def run_course(record_time):
    horizon = record_time + timedelta(hours=1) if record_time else datetime(2026, 1, 4, 9)
    rows = {
        "inpat_registration": [{"admission_datetime": "2026-01-01 08:00:00"}],
        CURRENT_VISIT_DISCHARGE_HORIZON_SOURCE_KEY: [{"discharge_datetime": horizon}],
        "daily_course_record": [
            {"document_id": "C1", "record_time": "2026-01-01 08:00:00",
             "record_content": "今日查房，患者病情平稳，维持现有治疗。"},
            {"document_id": "C2", "record_time": record_time,
             "record_content": "今日查房，患者病情平稳，维持现有治疗。"},
        ],
    }
    session = session_for(COURSE_RULE, rows)
    execution = await execute_luxian_0609_native_course_quality_rules(
        rule_ids=(COURSE_RULE,), decision_rule_ids=(COURSE_RULE,),
        wrapper_rules=[{"rule_id": COURSE_RULE}], evidence_payload=None,
        institute_id="I", patient_id="P", visit_id="V", source_schema=None,
        evidence_snapshot=session.snapshot, evidence_materials=session.materials,
        llm_client=None,
    )
    reduced = bind_and_reduce_luxian_0609_rule_decisions(
        decisions=execution.decisions, expected_rule_ids=(COURSE_RULE,),
        snapshot=session.snapshot, evidence_materials=session.materials,
    )[0]
    final = finalize_luxian_0609_reduced_customer_result(
        decision=reduced,
        raw_customer_display_facts=dict(execution.customer_display_facts).get(COURSE_RULE),
        evidence_snapshot=session.snapshot, evidence_materials=session.materials,
    )
    assert execution.llm_call_count == 0
    return reduced, final


@pytest.mark.asyncio
async def test_course_one_second_late_survives_finalizer_with_exact_duration():
    reduced, final = await run_course(datetime(2026, 1, 4, 8, 0, 1))
    assert reduced.final_state.value == "non_compliant"
    assert (final["status"], final["reason_code"]) == ("non_compliant", "threshold_exceeded")
    assert final["customer_display_facts"]["interval_seconds"] == 259201
    assert final["customer_display_facts"]["overdue_seconds"] == 1


@pytest.mark.asyncio
@pytest.mark.parametrize("record_time,seconds", [
    (datetime(2026, 1, 2, 9, 59, 59), 86399),
    (datetime(2026, 1, 2, 10), 86400),
])
async def test_surgery_before_and_at_deadline_remain_compliant(record_time, seconds):
    reduced, final = await run_surgery(record_time)
    assert final["status"] == reduced.final_state.value == "compliant"
    assert final["reason_code"] == "requirement_within_threshold"
    assert final["customer_display_facts"]["elapsed_seconds"] == seconds
    assert final["customer_display_facts"]["threshold_hours"] == 24


@pytest.mark.asyncio
@pytest.mark.parametrize("record_time,seconds", [
    (datetime(2026, 1, 4, 7, 59, 59), 259199),
    (datetime(2026, 1, 4, 8), 259200),
])
async def test_course_before_and_at_interval_limit_remain_compliant(record_time, seconds):
    reduced, final = await run_course(record_time)
    assert final["status"] == reduced.final_state.value == "compliant"
    assert final["reason_code"] == "requirement_within_threshold"
    assert final["customer_display_facts"]["interval_seconds"] == seconds
    assert final["customer_display_facts"]["overdue_seconds"] == 0
    assert final["customer_display_facts"]["threshold_hours"] == 72


@pytest.mark.asyncio
@pytest.mark.parametrize("runner", [run_surgery, run_course])
async def test_missing_record_time_keeps_data_gap(runner):
    reduced, final = await runner(None)
    assert final["status"] == reduced.final_state.value == "data_gap"
    assert final["reason_code"] in {"authoritative_time_missing", "required_field_missing"}


def sqlite_roundtrip(tmp_path, items):
    from sqlalchemy import MetaData, create_engine
    from sqlalchemy.orm import Session
    import app.services.custom_qc_workspace_service as workspace
    from app.services.qc_workspace.canonical_result_store import (
        CanonicalResultStore, envelope_item_from_rule_result,
    )

    table = workspace._record_result_envelopes_table().to_metadata(MetaData(), schema=None)
    engine = create_engine("sqlite:///" + str(tmp_path / "second-precision.sqlite"))
    table.metadata.create_all(engine)
    store = CanonicalResultStore(table)
    payload = [{**item, "record_id": "V", "visit_id": "V", "institute_id": "I",
                "patient_id": "P"} for item in items]
    try:
        with Session(engine) as writing:
            store.replace_for_job(
                writing,
                job_row={"id": "J", "created_by": "test", "filters_json": json.dumps({
                    "rule_set_key": "luxian_0609_qc_v1", "rule_set_version": "2026-06-09",
                })},
                items=payload, now=datetime(2026, 10, 7),
                projector=lambda raw: envelope_item_from_rule_result(raw, hmac_key="test"),
                projection_key="test",
            )
            writing.commit()
        # 关闭写 Session 和引擎；独立引擎的新 Session 经正式公开接口回读。
        engine.dispose()
        engine = create_engine("sqlite:///" + str(tmp_path / "second-precision.sqlite"))
        with Session(engine) as reading:
            loaded = store.load_selected(
                reading, root_job_id="J", institute_id="I", patient_id="P", visit_id="V",
                rule_set_key="luxian_0609_qc_v1", rule_set_version="2026-06-09",
            )["items"]
        assert len(loaded) == len(items)
        by_rule = {item["rule_id"]: item for item in loaded}
        for original in items:
            saved = by_rule[original["rule_id"]]
            for field in ("status", "reason_code", "customer_display_facts", "suggestion"):
                if field in original:
                    assert saved[field] == original[field]
            # 保存接口将内部坐标投影为公开 evidence/source_ref；按该公开合同回读。
            expected_evidence = envelope_item_from_rule_result(original, hmac_key="test")["evidence"]
            assert saved["evidence"] == expected_evidence
        return by_rule
    finally:
        engine.dispose()


@pytest.mark.asyncio
async def test_one_second_late_facts_survive_new_session_sqlite_read(tmp_path):
    _, surgery = await run_surgery(datetime(2026, 1, 2, 10, 0, 1))
    _, course = await run_course(datetime(2026, 1, 4, 8, 0, 1))
    assert surgery["status"] == course["status"] == "non_compliant"
    loaded = sqlite_roundtrip(tmp_path, [surgery, course])
    assert loaded[SURGERY_RULE]["customer_display_facts"]["elapsed_seconds"] == 86401
    assert loaded[COURSE_RULE]["customer_display_facts"]["interval_seconds"] == 259201
    assert loaded[COURSE_RULE]["customer_display_facts"]["overdue_seconds"] == 1


@pytest.mark.parametrize("rule,status,reason,facts", [
    (SURGERY_RULE, "compliant", "requirement_within_threshold", {
        "failure_kind": "surgery_record_within_threshold", "performed_surgery_confirmed": True,
        "surgery_end_time": "2026-01-01 10:00:00", "record_time": "2026-01-01 10:49:00",
        "elapsed_hours": 0.82, "threshold_hours": 24, "source_label": "手术记录",
    }),
    (COURSE_RULE, "non_compliant", "threshold_exceeded", {
        "failure_kind": "course_record_interval_over_72h",
        "interval_start_source": "inpat_registration", "interval_end_source": "daily_course_record",
        "interval_start_time": "2026-01-01 08:00:00", "interval_end_time": "2026-01-04 08:00:01",
        "interval_hours": 72.0, "threshold_hours": 72, "recorded_dates": ["2026-01-04"],
    }),
])
def test_historical_hour_facts_are_not_rewritten_on_new_session_read(
    tmp_path, rule, status, reason, facts,
):
    assert validate_luxian_0609_published_customer_display_facts(
        rule_id=rule, raw=facts, status=status, reason_code=reason,
    ) == facts
    item = {"rule_id": rule, "status": status, "result_status": status,
            "is_compliant": status == "compliant", "reason_code": reason,
            "customer_display_facts": facts}
    loaded = sqlite_roundtrip(tmp_path, [item])
    assert loaded[rule]["customer_display_facts"] == facts


@pytest.mark.asyncio
@pytest.mark.parametrize("rule,runner,record_time,field", [
    (SURGERY_RULE, run_surgery, datetime(2026, 1, 2, 10, 0, 1), "elapsed_seconds"),
    (COURSE_RULE, run_course, datetime(2026, 1, 4, 8, 0, 1), "interval_seconds"),
])
async def test_inconsistent_second_facts_still_fail_closed(rule, runner, record_time, field):
    _, final = await runner(record_time)
    damaged = {**final["customer_display_facts"], field: 1}
    with pytest.raises(ValueError, match="解释合同不完整"):
        validate_luxian_0609_published_customer_display_facts(
            rule_id=rule, raw=damaged, status="non_compliant", reason_code="threshold_exceeded",
        )
