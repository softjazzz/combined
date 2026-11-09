"""根因A：日期级出院不得被当作“出院日 00:00”精确时刻。

覆盖建任务冻结、执行时冻结读取、Provider 终点行形状和基础时效的同日/截止日边界。
"""

from datetime import date, datetime

from app.services.luxian_0609.canonical_result_finalizer import (
    finalize_luxian_0609_reduced_customer_result,
)
from app.services.luxian_0609.decision_binding import (
    bind_and_reduce_luxian_0609_rule_decisions,
)
from app.services.luxian_0609.evaluation_horizon import (
    build_record_evaluation_horizon_snapshot,
    read_frozen_evaluation_horizon,
    resolve_frozen_discharge_horizon,
    resolve_record_evaluation_horizon,
)
from app.services.luxian_0609.evidence_snapshot_provider import (
    SnapshotSourceRows,
    build_luxian_0609_evidence_read_session,
)
from app.services.luxian_0609.native_basic_timeliness import (
    execute_luxian_0609_native_basic_timeliness,
)

FIRST_BODY = {"record_content": "患者突发头痛，入院进一步诊治，完善头颅CT等检查。"}


def _frozen(admission, discharge, task_day="2026-01-05"):
    record = {
        "record_id": "V", "institute_id": "I", "patient_id": "P", "visit_id": "V",
        "scope": "final", "admission_datetime": admission, "discharge_datetime": discharge,
    }
    return build_record_evaluation_horizon_snapshot([record], task_frozen_date=task_day)[0]


def _session(rule, frozen, rows=None, task_day="2026-01-05"):
    rows = rows or {}

    def reader(**kwargs):
        key = kwargs["source_key"]
        return SnapshotSourceRows.create(
            source_key=key, rows=rows.get(key, ()), truncated=False, limit_rows=50
        )

    return build_luxian_0609_evidence_read_session(
        selected_rule_ids=(rule,), institute_id="I", patient_id="P", visit_id="V",
        source_schema=None, created_at=task_day + "T10:00:00+08:00",
        evaluation_as_of_date=task_day, evaluation_horizon_policy="authoritative_discharge",
        evaluation_horizon_snapshot=frozen, row_reader=reader,
    )


def _basic(rule, rows, *, admission, discharge, task_day):
    session = _session(rule, _frozen(admission, discharge, task_day), rows, task_day)
    execution = execute_luxian_0609_native_basic_timeliness(
        rule_ids=(rule,), decision_rule_ids=(rule,), evidence_payload=None,
        evidence_snapshot=session.snapshot, evidence_materials=session.materials,
    )
    reduced = bind_and_reduce_luxian_0609_rule_decisions(
        decisions=execution.decisions, expected_rule_ids=(rule,),
        snapshot=session.snapshot, evidence_materials=session.materials,
    )[0]
    final = finalize_luxian_0609_reduced_customer_result(
        decision=reduced,
        raw_customer_display_facts=dict(execution.customer_display_facts).get(rule),
        evidence_snapshot=session.snapshot, evidence_materials=session.materials,
    )
    return final["status"], final.get("reason_code")


def test_same_day_date_only_discharge_is_not_time_conflict_at_task_creation():
    resolved = resolve_record_evaluation_horizon(
        record_id="V", record_scene="final", admission_datetime="2026-01-01 10:00:00",
        discharge_datetime="2026-01-01", task_frozen_date="2026-01-05",
    )
    assert (resolved.resolution_status, resolved.evaluation_horizon) == ("resolved", "2026-01-01")
    earlier = resolve_record_evaluation_horizon(
        record_id="V", record_scene="final", admission_datetime="2026-01-02 10:00:00",
        discharge_datetime="2026-01-01", task_frozen_date="2026-01-05",
    )
    assert earlier.resolution_status == "time_conflict"
    precise_earlier = resolve_record_evaluation_horizon(
        record_id="V", record_scene="final", admission_datetime="2026-01-01 10:00:00",
        discharge_datetime="2026-01-01 09:00:00", task_frozen_date="2026-01-05",
    )
    assert precise_earlier.resolution_status == "time_conflict"


def test_frozen_discharge_reader_keeps_date_precision():
    frozen = {**_frozen("2026-01-01 10:00:00", "2026-01-01"), "resolution_status": "resolved"}
    horizon, error = resolve_frozen_discharge_horizon(
        frozen, institute_id="I", patient_id="P", visit_id="V"
    )
    assert (horizon, error) == (date(2026, 1, 1), "")
    precise, error = resolve_frozen_discharge_horizon(
        {**frozen, "discharge_datetime": "2026-01-01 15:00:00", "discharge_time_precision": "datetime"},
        institute_id="I", patient_id="P", visit_id="V",
    )
    assert (precise, error) == (datetime(2026, 1, 1, 15), "")
    # 旧任务若已在建任务时冻结成冲突，执行时不改写。
    _, error = resolve_frozen_discharge_horizon(
        {**frozen, "discharge_datetime": "2026-01-01 09:00:00"},
        institute_id="I", patient_id="P", visit_id="V",
    )
    assert error == "authoritative_time_conflict"


def test_provider_date_only_row_has_no_midnight_moment():
    frozen = _frozen("2026-01-01 20:00:00", "2026-01-01")
    session = _session("LX0609-01-02-01", frozen)
    row = session.materials.rows("evaluation_context.horizon")[0]
    assert row["horizon_date"] == "2026-01-01"
    assert row["time_precision"] == "date"
    assert "horizon_datetime" not in row
    horizon, basis, error = read_frozen_evaluation_horizon(
        snapshot=session.snapshot, materials=session.materials
    )
    assert (horizon, basis, error) == (date(2026, 1, 1), "discharge_date", "")


def test_same_day_date_only_discharge_keeps_definite_late_first_course():
    rows = {
        "inpat_registration": [{"admission_datetime": "2026-01-01 10:00:00"}],
        "first_course_record": [
            {"document_id": "FC", "record_time": "2026-01-01 20:00:00", **FIRST_BODY}
        ],
    }
    assert _basic(
        "LX0609-01-02-01", rows, admission="2026-01-01 10:00:00",
        discharge="2026-01-01", task_day="2026-01-03",
    )[0] == "non_compliant"


def test_date_only_discharge_on_deadline_day_is_data_gap_not_immature():
    # 8h 截止 01-02 04:00；仅知 01-02 出院，无法判断是否已越过截止时刻。
    rows = {"inpat_registration": [{"admission_datetime": "2026-01-01 20:00:00"}]}
    assert _basic(
        "LX0609-01-02-01", rows, admission="2026-01-01 20:00:00",
        discharge="2026-01-02", task_day="2026-01-05",
    ) == ("data_gap", "authoritative_time_missing")
    assert _basic(
        "LX0609-02-01-02", {"inpat_registration": [{"admission_datetime": "2026-01-01 10:00:00"}]},
        admission="2026-01-01 10:00:00", discharge="2026-01-04", task_day="2026-01-06",
    ) == ("data_gap", "authoritative_time_missing")
