"""P0-2 (rules_008_009 病危/病重医嘱停止时间截断) 与 P0-4 (basic_timeliness 入院锚点与出院终点回退) 回归单测。"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import pytest

from app.services.luxian_0609 import native_basic_timeliness as basic_timeliness
from app.services.luxian_0609.canonical_result_finalizer import (
    finalize_luxian_0609_reduced_customer_result,
)
from app.services.luxian_0609.decision_binding import (
    bind_and_reduce_luxian_0609_rule_decisions,
)
from app.services.luxian_0609.decision_reducer import CustomerFinalState
from app.services.luxian_0609.evidence_snapshot_provider import (
    SnapshotSourceRows,
    build_luxian_0609_evidence_read_session,
)
from app.services.luxian_0609.native_basic_timeliness import (
    execute_luxian_0609_native_basic_timeliness,
)
from app.services.luxian_0609.native_course_quality_execution import (
    execute_luxian_0609_native_course_quality_rules,
)
from app.services.luxian_0609.source_evidence_reader import (
    CURRENT_VISIT_DISCHARGE_HORIZON_SOURCE_KEY as DISCHARGE_HORIZON,
    CURRENT_VISIT_RESCUE_ORDER_SOURCE_KEY as RESCUE_ORDER,
    CURRENT_VISIT_SEVERITY_ORDER_SOURCE_KEY as SEVERITY_ORDER,
    CURRENT_VISIT_UNSTABLE_ORDER_SOURCE_KEY as UNSTABLE_ORDER,
    EVALUATION_HORIZON_SOURCE_KEY,
)


SERIOUS_RULE = "LX0609-02-01-04"
CRITICAL_RULE = "LX0609-02-01-05"
CORE_TIMELINESS_RULES = (
    "LX0609-01-01-01",
    "LX0609-01-02-01",
    "LX0609-02-01-01",
    "LX0609-02-01-02",
)


def _course_note(when: str, doc_id: str, title: str = "日常病程记录") -> dict[str, Any]:
    return {
        "document_id": doc_id,
        "record_time": when,
        "document_title": title,
        "record_content": "今日查房，患者生命体征监测中，继续当前治疗方案并观察病情。",
    }


def _severity_order(
    *,
    severity: str,
    start: str,
    end: str | None = None,
    lifecycle_state: str = "active",
    end_field: str = "planned_end_datetime",
    marker: str = "o1",
) -> dict[str, Any]:
    row: dict[str, Any] = {
        "severity": severity,
        "event_kind": "start",
        "status_state": "effective",
        "lifecycle_state": lifecycle_state,
        "prescribed_datetime": start,
        "planned_start_datetime": start,
        "planned_end_datetime": None,
        "row_ref": f"{severity}/{start}/{end}/{marker}",
    }
    row[end_field] = end
    return row


async def _eval_severity(
    rule_id: str,
    *,
    orders: list[dict[str, Any]],
    notes: list[dict[str, Any]],
    discharge: str | None = "2026-09-14 09:38:29",
    as_of: str | None = None,
    created_at: str = "2026-10-26T00:00:00Z",
) -> dict[str, Any]:
    rows: dict[str, list[dict[str, Any]]] = {
        "inpat_registration": [{"admission_datetime": None}],
        "admission_record": [{"admission_datetime": "2026-08-19 08:55:40"}],
        "daily_course_record": notes,
        "senior_course_record": [],
        SEVERITY_ORDER: orders,
        DISCHARGE_HORIZON: [{"discharge_datetime": discharge}] if discharge else [],
        UNSTABLE_ORDER: [{"present": True}] if orders else [],
        "exam_item_report": [],
        "labtest_master": [],
        "labtest_item_report": [],
    }

    def reader(**kwargs: Any) -> SnapshotSourceRows:
        source_key = kwargs["source_key"]
        return SnapshotSourceRows.create(
            source_key=source_key,
            rows=rows.get(source_key, ()),
            truncated=False,
            limit_rows=50,
        )

    session = build_luxian_0609_evidence_read_session(
        selected_rule_ids=(rule_id,),
        institute_id="I",
        patient_id="P",
        visit_id="V",
        source_schema=None,
        created_at=created_at,
        evaluation_as_of_date=as_of,
        row_reader=reader,
    )
    execution = await execute_luxian_0609_native_course_quality_rules(
        rule_ids=(rule_id,),
        decision_rule_ids=(rule_id,),
        wrapper_rules=[{"rule_id": rule_id}],
        evidence_payload=None,
        institute_id="I",
        patient_id="P",
        visit_id="V",
        source_schema=None,
        llm_client=None,
        evidence_snapshot=session.snapshot,
        evidence_materials=session.materials,
    )
    assert execution.llm_call_count == 0
    reduced = bind_and_reduce_luxian_0609_rule_decisions(
        decisions=execution.decisions,
        expected_rule_ids=(rule_id,),
        snapshot=session.snapshot,
        evidence_materials=session.materials,
    )[0]
    return finalize_luxian_0609_reduced_customer_result(
        decision=reduced,
        raw_customer_display_facts=dict(execution.customer_display_facts).get(rule_id),
        evidence_snapshot=session.snapshot,
        evidence_materials=session.materials,
    )


def _eval_typed_basic_with_discharge_horizon(
    *,
    rows_by_source: dict[str, list[dict[str, Any]]],
    rule_ids: tuple[str, ...] = CORE_TIMELINESS_RULES,
    created_at: str = "2026-10-26T00:00:00Z",
    evaluation_as_of_date: str | None = None,
):
    def reader(**kwargs: Any) -> SnapshotSourceRows:
        source_key = kwargs["source_key"]
        return SnapshotSourceRows.create(
            source_key=source_key,
            rows=rows_by_source.get(source_key, ()),
            truncated=False,
            limit_rows=50,
        )

    # 模拟 51 规则同跑：带入 discharge_horizon（无 task_frozen_date 的单病历/终末直评场景）。
    session = build_luxian_0609_evidence_read_session(
        selected_rule_ids=(*rule_ids, SERIOUS_RULE),
        institute_id="I",
        patient_id="P",
        visit_id="V",
        source_schema=None,
        created_at=created_at,
        evaluation_as_of_date=evaluation_as_of_date,
        row_reader=reader,
        additional_source_keys=(
            "admission_record",
            "inpat_registration",
            "discharge_record",
            "first_course_record",
            "daily_course_record",
            "senior_course_record",
            RESCUE_ORDER,
            "rescue_record",
        ),
    )
    execution = execute_luxian_0609_native_basic_timeliness(
        rule_ids=rule_ids,
        decision_rule_ids=rule_ids,
        evidence_payload=None,
        evidence_snapshot=session.snapshot,
        evidence_materials=session.materials,
    )
    reduced = bind_and_reduce_luxian_0609_rule_decisions(
        decisions=execution.decisions,
        expected_rule_ids=rule_ids,
        snapshot=session.snapshot,
        evidence_materials=session.materials,
    )
    finals = {
        dec.rule_id: finalize_luxian_0609_reduced_customer_result(
            decision=dec,
            raw_customer_display_facts=dict(execution.customer_display_facts).get(dec.rule_id),
            evidence_snapshot=session.snapshot,
            evidence_materials=session.materials,
        )
        for dec in reduced
    }
    return session, execution, reduced, finals


# ---------------------------------------------------------------------------
# P0-2: LX0609-02-01-05 (病危) & LX0609-02-01-04 (病重) 停止时间截断回归
# ---------------------------------------------------------------------------


@pytest.mark.unit
@pytest.mark.asyncio
async def test_p0_2_critical_active_order_truncates_at_planned_end_datetime() -> None:
    """复现 #25：order_status='新开'(lifecycle='active') 但带 planned_end_datetime 时必须按停嘱日截断。"""
    result = await _eval_severity(
        CRITICAL_RULE,
        orders=[
            _severity_order(
                severity="critical",
                start="2026-08-30 12:15:17+08:00",
                end="2026-08-31 09:30:48+08:00",
                lifecycle_state="active",
            )
        ],
        notes=[
            _course_note("2026-08-30 12:42:00", "C1"),
            _course_note("2026-08-31 09:30:00", "C2"),
            # 停嘱后 09-06/07/12/13 无病程不应再被误判
            _course_note("2026-09-03 23:12:00", "C3"),
            _course_note("2026-09-11 17:57:29", "C4"),
        ],
        discharge="2026-09-14 09:38:29",
    )
    assert result["status"] == "compliant"
    assert result["reason_code"] == "requirement_satisfied"
    facts = result["customer_display_facts"]
    assert facts["required_dates"] == ["2026-08-30", "2026-08-31"]
    assert facts["covered_dates"] == ["2026-08-30", "2026-08-31"]
    assert facts["missing_count"] == 0


@pytest.mark.unit
@pytest.mark.asyncio
async def test_p0_2_critical_active_order_still_flags_missing_day_inside_interval() -> None:
    result = await _eval_severity(
        CRITICAL_RULE,
        orders=[
            _severity_order(
                severity="critical",
                start="2026-08-30 12:15:17+08:00",
                end="2026-09-01 09:30:48+08:00",
                lifecycle_state="active",
            )
        ],
        notes=[
            _course_note("2026-08-30 12:42:00", "C1"),
            _course_note("2026-09-01 09:30:00", "C3"),
        ],
        discharge="2026-09-14 09:38:29",
    )
    assert result["status"] == "non_compliant"
    assert result["reason_code"] == "requirement_violated"
    facts = result["customer_display_facts"]
    assert facts["required_dates"] == ["2026-08-30", "2026-08-31", "2026-09-01"]
    assert facts["missing_dates"] == ["2026-08-31"]


@pytest.mark.unit
@pytest.mark.asyncio
async def test_p0_2_critical_planned_end_after_discharge_clamps_to_discharge_horizon() -> None:
    result = await _eval_severity(
        CRITICAL_RULE,
        orders=[
            _severity_order(
                severity="critical",
                start="2026-08-30 12:00:00",
                end="2026-09-20 12:00:00",
                lifecycle_state="active",
            )
        ],
        notes=[
            _course_note("2026-08-30 15:00:00", "C1"),
            _course_note("2026-08-31 10:00:00", "C2"),
            _course_note("2026-09-01 10:00:00", "C3"),
            _course_note("2026-09-02 09:00:00", "C4"),
        ],
        discharge="2026-09-02 10:00:00",
    )
    assert result["status"] == "compliant"
    assert result["customer_display_facts"]["required_dates"] == [
        "2026-08-30",
        "2026-08-31",
        "2026-09-01",
        "2026-09-02",
    ]


@pytest.mark.unit
@pytest.mark.asyncio
async def test_p0_2_critical_multiple_non_overlapping_and_overlapping_active_orders() -> None:
    # 非重叠双区间：中间间隔日不纳入病危要求
    non_overlap = await _eval_severity(
        CRITICAL_RULE,
        orders=[
            _severity_order(
                severity="critical",
                start="2026-07-31 09:51:08",
                end="2026-08-01 10:00:00",
                lifecycle_state="active",
                marker="o1",
            ),
            _severity_order(
                severity="critical",
                start="2026-08-05 00:33:01",
                end="2026-08-06 10:20:54",
                lifecycle_state="active",
                marker="o2",
            ),
        ],
        notes=[
            _course_note("2026-07-31 12:00:00", "C1"),
            _course_note("2026-08-01 12:00:00", "C2"),
            _course_note("2026-08-05 12:00:00", "C3"),
            _course_note("2026-08-06 12:00:00", "C4"),
        ],
        discharge="2026-08-10 09:00:00",
    )
    assert non_overlap["status"] == "compliant"
    assert non_overlap["customer_display_facts"]["required_dates"] == [
        "2026-07-31",
        "2026-08-01",
        "2026-08-05",
        "2026-08-06",
    ]

    # 重叠区间：先停嘱的一条不得关闭后一条仍有效的病危医嘱
    overlap = await _eval_severity(
        CRITICAL_RULE,
        orders=[
            _severity_order(
                severity="critical",
                start="2026-07-30 10:13:18",
                end="2026-07-30 12:32:50",
                lifecycle_state="active",
                marker="o1",
            ),
            _severity_order(
                severity="critical",
                start="2026-07-30 12:32:25",
                end="2026-08-01 14:30:13",
                lifecycle_state="active",
                marker="o2",
            ),
        ],
        notes=[_course_note("2026-07-30 15:00:00", "C1")],
        discharge="2026-08-10 09:00:00",
    )
    assert overlap["status"] == "non_compliant"
    assert overlap["customer_display_facts"]["missing_dates"] == [
        "2026-07-31",
        "2026-08-01",
    ]


@pytest.mark.unit
@pytest.mark.asyncio
async def test_p0_2_serious_order_truncates_when_stopped_and_keeps_unbounded_defect() -> None:
    # 病重医嘱有 planned_end_datetime：仅在有效期内按 2 日间隔检查
    bounded = await _eval_severity(
        SERIOUS_RULE,
        orders=[
            _severity_order(
                severity="serious",
                start="2026-08-24 08:20:36+08:00",
                end="2026-08-26 08:53:56+08:00",
                lifecycle_state="active",
            )
        ],
        notes=[
            _course_note("2026-08-24 10:00:00", "S1"),
            _course_note("2026-08-26 08:00:00", "S2"),
        ],
        discharge="2026-09-10 10:00:00",
    )
    assert bounded["status"] == "compliant"
    assert bounded["reason_code"] == "requirement_within_threshold"

    # 复现 #02：病重医嘱无停止时间（planned_end_datetime=None）时仍查至出院并维持 non_compliant
    unbounded = await _eval_severity(
        SERIOUS_RULE,
        orders=[
            _severity_order(
                severity="serious",
                start="2025-10-05 12:18:08+08:00",
                end=None,
                lifecycle_state="active",
            )
        ],
        notes=[
            _course_note("2025-10-06 08:51:11", "S1"),
            _course_note("2025-10-08 09:00:00", "S2"),
            _course_note("2025-10-10 09:00:00", "S3"),
            _course_note("2025-10-12 09:00:00", "S4"),
            _course_note("2025-10-14 09:00:00", "S5"),
            _course_note("2025-10-16 09:00:00", "S6"),
            # 10-16 至 10-19 间隔 3 天 > 2 天
            _course_note("2025-10-19 08:56:00", "S7"),
        ],
        discharge="2025-10-20 09:26:00",
    )
    assert unbounded["status"] == "non_compliant"
    assert unbounded["reason_code"] == "threshold_exceeded"
    assert unbounded["customer_display_facts"]["gap_start_date"] == "2025-10-16"
    assert unbounded["customer_display_facts"]["gap_end_date"] == "2025-10-19"
    assert unbounded["customer_display_facts"]["gap_days"] == 3


@pytest.mark.unit
@pytest.mark.asyncio
@pytest.mark.parametrize("end_field", ("stop_datetime", "end_datetime", "order_end_time"))
async def test_p0_2_alternative_stop_datetime_fields_and_invalid_end_fail_closed(
    end_field: str,
) -> None:
    valid = await _eval_severity(
        CRITICAL_RULE,
        orders=[
            _severity_order(
                severity="critical",
                start="2026-08-30 12:00:00",
                end="2026-08-31 09:00:00",
                lifecycle_state="active",
                end_field=end_field,
            )
        ],
        notes=[
            _course_note("2026-08-30 13:00:00", "C1"),
            _course_note("2026-08-31 08:30:00", "C2"),
        ],
        discharge="2026-09-14 09:38:29",
    )
    assert valid["status"] == "compliant"

    # 结束时间早于开始时间必须 fail-closed 为 data_gap
    earlier = await _eval_severity(
        CRITICAL_RULE,
        orders=[
            _severity_order(
                severity="critical",
                start="2026-08-30 12:00:00",
                end="2026-08-29 09:00:00",
                lifecycle_state="active",
                end_field=end_field,
            )
        ],
        notes=[_course_note("2026-08-30 13:00:00", "C1")],
        discharge="2026-09-14 09:38:29",
    )
    assert (earlier["status"], earlier["reason_code"]) == (
        "data_gap",
        "authoritative_time_missing",
    )


# ---------------------------------------------------------------------------
# P0-4: basic_timeliness 入院锚点回退与终末 discharge_date 终点无 task_frozen_date 回归
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_p0_4_typed_basic_timeliness_falls_back_to_admission_record_under_discharge_horizon() -> None:
    """复现 Stage 1：inpat_registration.admission_datetime 为 NULL 且终末终点无 task_frozen_date。"""
    session, execution, reduced, finals = _eval_typed_basic_with_discharge_horizon(
        rows_by_source={
            "inpat_registration": [{"admission_datetime": None, "discharge_datetime": None}],
            "admission_record": [
                {
                    "document_id": "ADM-25",
                    "admission_datetime": datetime(2026, 8, 19, 8, 55, 40),
                    "record_time": datetime(2026, 8, 19, 9, 6, 28),
                    "chief_complaint": "体检发现右肺结节1月余。",
                }
            ],
            "first_course_record": [
                {
                    "document_id": "FC-25",
                    "record_time": datetime(2026, 8, 19, 9, 49, 48),
                    "record_content": "患者因右肺结节入院，拟完善术前评估及病理检查。",
                }
            ],
            "daily_course_record": [],
            "senior_course_record": [
                {
                    "document_id": "SC-25",
                    "document_title": "副主任医师代主治医师查房记录",
                    "record_time": datetime(2026, 8, 20, 9, 9, 16),
                    "record_content": "上级医师查房，审阅影像并拟定手术计划。",
                }
            ],
            "discharge_record": [
                {
                    "document_id": "DIS-25",
                    "admission_date": "2026-08-19",
                    "discharge_date": "2026-09-14",
                    "discharge_time": "2026-09-14 09:38:29",
                }
            ],
            DISCHARGE_HORIZON: [{"discharge_datetime": "2026-09-14 09:38:29"}],
        }
    )

    adm_obs = next(
        obs for obs in session.snapshot.observations if obs.source_key == "admission_record"
    )
    reg_obs = next(
        obs for obs in session.snapshot.observations if obs.source_key == "inpat_registration"
    )
    adm_ref = adm_obs.snapshot_ref.removeprefix("sha256:")
    reg_ref = reg_obs.snapshot_ref.removeprefix("sha256:")

    for rule_id in CORE_TIMELINESS_RULES:
        assert finals[rule_id]["status"] == "compliant", f"{rule_id} -> {finals[rule_id]}"
        assert finals[rule_id]["reason_code"] == "requirement_within_threshold"
        assert finals[rule_id]["customer_display_facts"]["anchor_time"] == "2026-08-19 08:55:40"

    # 全部 4 条规则均绑定 admission_record 作为锚点来源，而非 NULL 住院登记。
    for decision in execution.decisions:
        assert adm_ref in decision.fact_refs
        assert reg_ref not in decision.fact_refs


@pytest.mark.unit
def test_p0_4_typed_basic_timeliness_detects_late_documents_with_admission_record_anchor() -> None:
    _session, _execution, _reduced, finals = _eval_typed_basic_with_discharge_horizon(
        rows_by_source={
            "inpat_registration": [{"admission_datetime": None, "discharge_datetime": None}],
            "admission_record": [
                {
                    "document_id": "ADM-LATE",
                    "admission_datetime": "2026-08-19 08:00:00",
                    "record_time": "2026-08-20 10:00:00",  # 26h > 24h
                    "chief_complaint": "胸闷气促三天。",
                }
            ],
            "first_course_record": [
                {
                    "document_id": "FC-LATE",
                    "record_time": "2026-08-19 18:00:00",  # 10h > 8h
                    "record_content": "患者胸闷气促入院，完善心电图及心肌酶学检查。",
                }
            ],
            "daily_course_record": [],
            "senior_course_record": [
                {
                    "document_id": "SC-LATE",
                    "document_title": "主任医师首次查房记录",
                    "record_time": "2026-08-22 10:00:00",  # 74h > 48h & 72h
                    "record_content": "主任医师查房，调整诊疗方案。",
                }
            ],
            "discharge_record": [],
            DISCHARGE_HORIZON: [{"discharge_datetime": "2026-08-25 10:00:00"}],
        }
    )

    for rule_id in CORE_TIMELINESS_RULES:
        assert finals[rule_id]["status"] == "non_compliant"
        assert finals[rule_id]["reason_code"] == "threshold_exceeded"


@pytest.mark.unit
def test_p0_4_typed_basic_timeliness_missing_both_anchors_remains_data_gap() -> None:
    """inpat_registration 与 admission_record 均缺入院时间时，必须保持 data_gap: authoritative_time_missing。"""
    _session, _execution, reduced, finals = _eval_typed_basic_with_discharge_horizon(
        rows_by_source={
            "inpat_registration": [{"admission_datetime": None, "discharge_datetime": None}],
            "admission_record": [
                {
                    "document_id": "ADM-NO-ANCHOR",
                    "admission_datetime": None,
                    "record_time": "2026-08-19 09:06:28",
                    "chief_complaint": "反复咳嗽一周。",
                }
            ],
            "first_course_record": [
                {
                    "document_id": "FC-1",
                    "record_time": "2026-08-19 09:49:48",
                    "record_content": "患者反复咳嗽入院，完善胸部影像学检查。",
                }
            ],
            "daily_course_record": [],
            "senior_course_record": [
                {
                    "document_id": "SC-1",
                    "document_title": "主任医师首次查房记录",
                    "record_time": "2026-08-20 09:09:16",
                    "record_content": "主任医师查房，评估病情。",
                }
            ],
            "discharge_record": [],
            DISCHARGE_HORIZON: [{"discharge_datetime": "2026-09-14 09:38:29"}],
        }
    )

    assert all(dec.final_state is CustomerFinalState.DATA_GAP for dec in reduced)
    assert all(dec.reason_code == "authoritative_time_missing" for dec in reduced)
    assert all(finals[r]["status"] == "data_gap" for r in CORE_TIMELINESS_RULES)


@pytest.mark.unit
def test_p0_4_post_discharge_completion_visible_without_task_frozen_date() -> None:
    """无 task_frozen_date 的终末直评：出院当日入院、次日凌晨（24h内、快照创建前）补写仍应判合规。"""
    _session, _execution, _reduced, finals = _eval_typed_basic_with_discharge_horizon(
        rows_by_source={
            "inpat_registration": [{"admission_datetime": None}],
            "admission_record": [
                {
                    "document_id": "ADM-POST",
                    "admission_datetime": "2026-08-19 20:00:00",
                    "record_time": "2026-08-20 02:00:00",  # 6h <= 24h，晚于出院日但早于 created_at
                    "chief_complaint": "急性腹痛入院。",
                }
            ],
            "first_course_record": [
                {
                    "document_id": "FC-POST",
                    "record_time": "2026-08-20 01:00:00",  # 5h <= 8h
                    "record_content": "患者急性腹痛入院，予对症支持治疗后离院。",
                }
            ],
            "discharge_record": [],
            DISCHARGE_HORIZON: [{"discharge_datetime": "2026-08-19 23:00:00"}],
        },
        rule_ids=("LX0609-01-01-01", "LX0609-01-02-01"),
        created_at="2026-08-25T10:00:00+08:00",
    )

    assert finals["LX0609-01-01-01"]["status"] == "compliant"
    assert finals["LX0609-01-02-01"]["status"] == "compliant"


@pytest.mark.unit
def test_p0_4_legacy_programmatic_fallback_uses_admission_record_admission_datetime(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        basic_timeliness,
        "read_luxian_0609_course_round_timeline",
        lambda **_kwargs: {
            "daily_course_record": [],
            "senior_course_record": [
                {
                    "title": "主治医师首次查房记录",
                    "author_title": "主治医师",
                    "authored_at": "2026-08-20 09:00:00",
                },
                {
                    "title": "主任医师首次查房记录",
                    "author_title": "主任医师",
                    "authored_at": "2026-08-21 09:00:00",
                },
            ],
        },
    )

    # 1. admission_time 缺失但 documents.admission_record 含权威 admission_datetime -> 成功回退并记录来源
    execution = execute_luxian_0609_native_basic_timeliness(
        rule_ids=("LX0609-01-01-01", "LX0609-02-01-01", "LX0609-02-01-02"),
        evidence_payload={
            "programmatic_timeline": {
                "admission_time": "",
                "admission_time_basis": "",
                "admission_time_trusted": False,
                "documents": {
                    "admission_record": [
                        {
                            "source_table": "admission_record",
                            "title": "入院记录",
                            "admission_datetime": "2026-08-19 08:55:40",
                            "authored_at": "2026-08-19 09:06:28",
                        }
                    ],
                },
            }
        },
        institute_id="I",
        patient_id="P",
        visit_id="V",
    )
    assert [item["status"] for item in execution.results] == [
        "compliant",
        "compliant",
        "compliant",
    ]
    assert all(
        item["metadata"].get("admission_anchor_source")
        == "admission_record.admission_datetime"
        for item in execution.results
    )

    # 2. 两处均无 admission_datetime（仅 authored_at 且无批准 basis）-> 仍保守 data_gap
    missing_both = execute_luxian_0609_native_basic_timeliness(
        rule_ids=("LX0609-01-01-01", "LX0609-02-01-01", "LX0609-02-01-02"),
        evidence_payload={
            "programmatic_timeline": {
                "admission_time": "",
                "admission_time_basis": "",
                "admission_time_trusted": False,
                "documents": {
                    "admission_record": [
                        {
                            "source_table": "admission_record",
                            "title": "入院记录",
                            "authored_at": "2026-08-19 09:06:28",
                        }
                    ],
                },
            }
        },
    )
    assert [item["status"] for item in missing_both.results] == ["data_gap"] * 3
    assert {
        item["metadata"]["reason_code"] for item in missing_both.results
    } == {"trusted_admission_anchor_unavailable"}
