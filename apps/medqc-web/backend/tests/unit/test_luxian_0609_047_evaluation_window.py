from __future__ import annotations

from datetime import date, datetime
from typing import Any

import pytest

from transfusion_order_test_support import FrozenTransfusionProtocolClient

from app.services.luxian_0609.evidence_snapshot_provider import (
    SnapshotSourceRows,
    build_luxian_0609_evidence_read_session,
)
from app.services.luxian_0609.decision_binding import (
    bind_and_reduce_luxian_0609_rule_decisions,
)
from app.services.luxian_0609 import native_transfusion_execution as transfusion
from app.services.luxian_0609.native_transfusion_execution import (
    execute_luxian_0609_native_transfusion_rules,
)


def _session(
    *,
    horizon_date: str | None,
    bloodtrans_rows: list[dict[str, Any]],
    daily_rows: list[dict[str, Any]] | None = None,
):
    def reader(**kwargs: Any) -> SnapshotSourceRows:
        source_key = str(kwargs["source_key"])
        rows_by_source = {
            "mr_bloodtrans": [
                {"transfution_datetime": datetime(2026, 1, 1, 14, 20)}
            ],
            "bloodtrans_record": bloodtrans_rows,
            "daily_course_record": daily_rows or [],
        }
        return SnapshotSourceRows.create(
            source_key=source_key,
            rows=rows_by_source.get(source_key, []),
            truncated=False,
            limit_rows=50,
        )

    return build_luxian_0609_evidence_read_session(
        selected_rule_ids=("LX0609-07-03-01",),
        institute_id="I",
        patient_id="P",
        visit_id="V",
        source_schema=None,
        created_at="2026-01-04T08:00:00+08:00",
        evaluation_as_of_date=horizon_date,
        evaluation_horizon_policy=("frozen_task_date" if horizon_date else "disabled"),
        horizon_unavailable_reason=(
            None if horizon_date else "authoritative_time_missing"
        ),
        row_reader=reader,
    )


async def _execute(session: Any):
    return await execute_luxian_0609_native_transfusion_rules(
        rule_ids=("LX0609-07-03-01",),
        wrapper_rules=[],
        evidence_payload=None,
        institute_id="I",
        patient_id="P",
        visit_id="V",
        source_schema=None,
        # 本文件专用输血记录均由测试作者写成实际输注过程；只验证 047 时间与关联。
        llm_client=FrozenTransfusionProtocolClient(default_course_label="record"),
        evidence_snapshot=session.snapshot,
        evidence_materials=session.materials,
        decision_rule_ids=("LX0609-07-03-01",),
    )


def _canonical_state(*, result: Any, session: Any) -> tuple[str, str]:
    canonical = bind_and_reduce_luxian_0609_rule_decisions(
        decisions=result.decisions,
        expected_rule_ids=("LX0609-07-03-01",),
        snapshot=session.snapshot,
        evidence_materials=session.materials,
    )[0]
    return canonical.final_state.value, canonical.reason_code


def _timed_evaluation_session(**time_fields: Any):
    return _session(
        horizon_date="2026-06-07",
        bloodtrans_rows=[
            {
                "document_id": "BT-F07",
                "record_content": "2026-06-05 10:00:00输血结束。",
            }
        ],
        daily_rows=[
            {
                "document_title": "输血后评价记录",
                "document_id": "EVAL-F07",
                "record_content": "输血后复查血红蛋白较前改善。",
                **time_fields,
            }
        ],
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "record_time",
    (
        "2026-06-06T03:00:00+00:00",
        "2026-06-06T11:00:00+08:00",
    ),
)
async def test_047_equivalent_aware_evaluation_times_are_both_late(record_time: str):
    """同一时刻不得因偏移写法不同得到 17h/25h 两种结论。"""

    session = _timed_evaluation_session(record_time=record_time)

    result = await _execute(session)

    assert _canonical_state(result=result, session=session) == (
        "non_compliant",
        "requirement_violated",
    )
    assert result.decisions[0].reason_code == "requirement_violated"
    assert result.decisions[0].evaluator_version == (
        "transfusion-ruledecision-post-time-precision-v8"
    )


@pytest.mark.asyncio
async def test_047_date_only_evaluation_time_is_a_data_gap_not_midnight():
    session = _timed_evaluation_session(record_time="2026-06-06")

    result = await _execute(session)

    assert _canonical_state(result=result, session=session)[0] == "data_gap"
    assert result.decisions[0].reason_code == "authoritative_time_missing"
    assert result.customer_display_facts == ()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("record_time", "expected_state", "expected_reason"),
    (
        (
            "2026-06-06T02:00:00+00:00",
            "compliant",
            "requirement_satisfied",
        ),
        (
            "2026-06-06T02:00:00.000001+00:00",
            "non_compliant",
            "requirement_violated",
        ),
        (
            "2026-06-06 10:00:00",
            "compliant",
            "requirement_satisfied",
        ),
    ),
)
async def test_047_aware_24_hour_boundary_preserves_microseconds_and_naive_local_time(
    record_time: str,
    expected_state: str,
    expected_reason: str,
):
    session = _timed_evaluation_session(record_time=record_time)

    result = await _execute(session)

    assert _canonical_state(result=result, session=session)[0] == expected_state
    assert result.decisions[0].reason_code == expected_reason


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "field",
    ("record_time", "record_datetime", "submit_time", "submit_datetime"),
)
async def test_047_uses_precise_authoritative_record_or_submission_time(field: str):
    session = _timed_evaluation_session(
        **{field: "2026-06-06T02:00:00+00:00"}
    )

    result = await _execute(session)

    assert _canonical_state(result=result, session=session)[0] == "compliant"
    assert result.decisions[0].reason_code == "requirement_satisfied"


@pytest.mark.asyncio
async def test_047_signature_time_cannot_replace_missing_document_time():
    session = _timed_evaluation_session(
        physician_sign_datetime="2026-06-06T02:00:00+00:00"
    )

    result = await _execute(session)

    assert _canonical_state(result=result, session=session)[0] == "data_gap"
    assert result.decisions[0].reason_code == "authoritative_time_missing"


def test_047_confirmed_missing_event_survives_other_unresolved_end_marker():
    assessment = transfusion._programmatic_047_assessment(
        {
            "bloodtrans_record": [
                {
                    "document_id": "MISSING-A",
                    "record_content": "2026-06-01 10:00:00输血结束。",
                },
                {
                    "document_id": "UNKNOWN-B",
                    "record_content": "输血结束，输注过程顺利。",
                },
            ],
            "daily_course_record": [],
            "__evaluation_horizon_rows__": [
                {"horizon_datetime": "2026-06-09 12:00:00"}
            ],
        }
    )

    assert (assessment.status, assessment.reason_code) == (
        "non_compliant",
        "posttransfusion_evaluation_missing",
    )
    assert assessment.selected_source_document_refs == (
        ("bloodtrans_record", "MISSING-A"),
    )


@pytest.mark.parametrize(
    "time_fields",
    (
        {"record_time": "2026-06-05"},
        {"authored_at": "2026-06-05", "time_basis": "record_time"},
        {"record_time": date(2026, 6, 5)},
    ),
    ids=("record-time", "authored-at-record-basis", "date-object"),
)
def test_047_date_only_evaluation_scope_does_not_cover_an_earlier_event(
    time_fields: dict[str, Any],
):
    assessment = transfusion._programmatic_047_assessment(
        {
            "bloodtrans_record": [
                {
                    "document_id": "MISSING-A",
                    "record_content": "2026-06-01 10:00:00输血结束。",
                },
                {
                    "document_id": "POSSIBLE-B",
                    "record_content": "2026-06-05 10:00:00输血结束。",
                },
            ],
            "daily_course_record": [
                {
                    "document_title": "输血后评价记录",
                    "document_id": "DATE-B",
                    "record_content": "输血后复查血红蛋白较前改善。",
                    **time_fields,
                }
            ],
            "__evaluation_horizon_rows__": [
                {"horizon_datetime": "2026-06-09 12:00:00"}
            ],
        }
    )

    assert (assessment.status, assessment.reason_code) == (
        "non_compliant",
        "posttransfusion_evaluation_missing",
    )
    assert assessment.selected_source_document_refs == (
        ("bloodtrans_record", "MISSING-A"),
    )


def test_047_date_only_outside_every_window_does_not_expand_to_all_events():
    assessment = transfusion._programmatic_047_assessment(
        {
            "bloodtrans_record": [
                {
                    "document_id": "MISSING-A",
                    "record_content": "2026-06-01 10:00:00输血结束。",
                }
            ],
            "daily_course_record": [
                {
                    "document_title": "输血后评价记录",
                    "document_id": "UNRELATED-DATE",
                    "record_time": "2026-06-05",
                    "record_content": "输血后复查血红蛋白较前改善。",
                }
            ],
            "__evaluation_horizon_rows__": [
                {"horizon_datetime": "2026-06-09 12:00:00"}
            ],
        }
    )

    assert (assessment.status, assessment.reason_code) == (
        "non_compliant",
        "posttransfusion_evaluation_missing",
    )
    assert assessment.selected_source_document_refs == (
        ("bloodtrans_record", "MISSING-A"),
    )


def test_047_another_unresolved_end_stays_on_the_explicit_anchor_date():
    assessment = transfusion._programmatic_047_assessment(
        {
            "bloodtrans_record": [
                {
                    "document_id": "MISSING-A",
                    "record_content": "2026-06-01 10:00:00输血结束。",
                },
                {
                    "document_id": "AMBIGUOUS-B",
                    "record_content": "2026-06-05 10:00:00输血结束。",
                },
                {
                    "document_id": "AMBIGUOUS-C",
                    "record_content": "2026-06-05 12:00:00输血结束。",
                },
            ],
            "daily_course_record": [
                {
                    "document_title": "输血后评价记录",
                    "document_id": "EVAL-BC",
                    "record_time": "2026-06-05 13:00:00",
                    "record_content": (
                        "2026-06-05 10:00:00输血结束；"
                        "另一次输血结束，复查血红蛋白较前改善。"
                    ),
                }
            ],
            "__evaluation_horizon_rows__": [
                {"horizon_datetime": "2026-06-09 12:00:00"}
            ],
        }
    )

    assert (assessment.status, assessment.reason_code) == (
        "non_compliant",
        "posttransfusion_evaluation_missing",
    )
    assert assessment.selected_source_document_refs == (
        ("bloodtrans_record", "MISSING-A"),
    )


@pytest.mark.parametrize(
    "order",
    (("MISSING-A", "ANCHORED-B", "UNKNOWN-C"),
     ("UNKNOWN-C", "MISSING-A", "ANCHORED-B")),
)
def test_047_unknown_end_scope_does_not_depend_on_source_row_order(
    order: tuple[str, ...],
):
    rows = {
        "MISSING-A": {
            "document_id": "MISSING-A",
            "record_content": "2026-06-01 10:00:00输血结束。",
        },
        "ANCHORED-B": {
            "document_id": "ANCHORED-B",
            "record_content": "2026-06-05 10:00:00输血结束。",
        },
        "UNKNOWN-C": {
            "document_id": "UNKNOWN-C",
            "record_content": "输血结束，输注过程顺利。",
        },
    }
    assessment = transfusion._programmatic_047_assessment(
        {
            "bloodtrans_record": [rows[key] for key in order],
            "daily_course_record": [
                {
                    "document_title": "输血后评价记录",
                    "document_id": "EVAL-BC",
                    "record_time": "2026-06-05 13:00:00",
                    "record_content": (
                        "2026-06-05 10:00:00输血结束；"
                        "另一次输血结束，复查血红蛋白较前改善。"
                    ),
                }
            ],
            "__evaluation_horizon_rows__": [
                {"horizon_datetime": "2026-06-09 12:00:00"}
            ],
        }
    )

    assert (assessment.status, assessment.reason_code) == (
        "non_compliant",
        "posttransfusion_evaluation_missing",
    )
    assert assessment.selected_source_document_refs == (
        ("bloodtrans_record", "MISSING-A"),
    )


@pytest.mark.asyncio
async def test_047_date_only_horizon_keeps_unexpired_window_not_applicable():
    session = _session(
        horizon_date="2026-01-02",
        bloodtrans_rows=[
            {
                "document_id": "BT-1",
                "record_content": "2026-01-01 16:00:00输血结束。",
            }
        ],
    )

    result = await _execute(session)

    assert _canonical_state(result=result, session=session) == (
        "not_applicable",
        "evaluation_window_not_mature",
    )
    assert result.decisions[0].reason_code == "evaluation_window_not_mature"
    assert result.customer_display_facts == ()


@pytest.mark.asyncio
async def test_047_date_only_horizon_proves_missing_only_after_deadline_date():
    session = _session(
        horizon_date="2026-01-03",
        bloodtrans_rows=[
            {
                "document_id": "BT-1",
                "record_content": "2026-01-01 16:00:00输血结束。",
            }
        ],
    )

    result = await _execute(session)

    assert _canonical_state(result=result, session=session) == (
        "non_compliant",
        "requirement_violated",
    )


@pytest.mark.asyncio
async def test_047_missing_horizon_is_data_gap_without_guessing_now():
    session = _session(
        horizon_date=None,
        bloodtrans_rows=[
            {
                "document_id": "BT-1",
                "record_content": "2026-01-01 16:00:00输血结束。",
            }
        ],
    )

    result = await _execute(session)

    assert _canonical_state(result=result, session=session) == (
        "data_gap",
        "authoritative_time_missing",
    )
    assert result.decisions[0].reason_code == "authoritative_time_missing"


@pytest.mark.asyncio
async def test_047_mature_earlier_missing_event_is_not_hidden_by_later_unmatured_event():
    session = _session(
        horizon_date="2026-01-03",
        bloodtrans_rows=[
            {
                "document_id": "BT-EARLY",
                "record_content": "2026-01-01 10:00:00输血结束。",
            },
            {
                "document_id": "BT-LATE",
                "record_content": "2026-01-02 22:00:00输血结束。",
            },
        ],
    )

    result = await _execute(session)

    assert _canonical_state(result=result, session=session) == (
        "non_compliant",
        "requirement_violated",
    )


@pytest.mark.parametrize(
    ("horizon_datetime", "expected"),
    (
        ("2026-01-02 15:59:59", ("not_applicable", "evaluation_window_not_mature")),
        ("2026-01-02 16:00:00", ("not_applicable", "evaluation_window_not_mature")),
        ("2026-01-02 16:00:01", ("non_compliant", "posttransfusion_evaluation_missing")),
    ),
)
def test_047_datetime_horizon_uses_strictly_after_24_hours_boundary(
    horizon_datetime: str, expected: tuple[str, str]
):
    assert transfusion._programmatic_047_status(
        {
            "bloodtrans_record": [
                {"record_content": "2026-01-01 16:00:00输血结束。"}
            ],
            "daily_course_record": [],
            "__evaluation_horizon_rows__": [
                {
                    "horizon_date": "2026-01-02",
                    "horizon_datetime": horizon_datetime,
                }
            ],
        }
    ) == expected


@pytest.mark.parametrize(
    "horizon_datetime",
    (
        "2026-01-02T03:00:00+00:00",
        "2026-01-02T11:00:00+08:00",
    ),
)
def test_047_equivalent_aware_horizons_use_the_same_hospital_time(
    horizon_datetime: str,
):
    assert transfusion._programmatic_047_status(
        {
            "bloodtrans_record": [
                {"record_content": "2026-01-01 10:00:00输血结束。"}
            ],
            "daily_course_record": [],
            "__evaluation_horizon_rows__": [
                {
                    "horizon_date": "2026-01-02",
                    "horizon_datetime": horizon_datetime,
                }
            ],
        }
    ) == ("non_compliant", "posttransfusion_evaluation_missing")


@pytest.mark.parametrize(
    ("horizon_date", "horizon_datetime"),
    (
        ("2026-01-02", "2026-01-02T20:00:00+00:00"),
        ("2026-01-03", "2026-01-03T04:00:00+08:00"),
    ),
)
def test_047_cross_date_aware_horizons_validate_before_hospital_normalization(
    horizon_date: str,
    horizon_datetime: str,
):
    assert transfusion._programmatic_047_status(
        {
            "bloodtrans_record": [
                {"record_content": "2026-01-01 10:00:00输血结束。"}
            ],
            "daily_course_record": [],
            "__evaluation_horizon_rows__": [
                {
                    "horizon_date": horizon_date,
                    "horizon_datetime": horizon_datetime,
                }
            ],
        }
    ) == ("non_compliant", "posttransfusion_evaluation_missing")


def test_047_horizon_date_still_rejects_a_true_raw_calendar_conflict():
    assert transfusion._programmatic_047_status(
        {
            "bloodtrans_record": [
                {"record_content": "2026-01-01 10:00:00输血结束。"}
            ],
            "daily_course_record": [],
            "__evaluation_horizon_rows__": [
                {
                    "horizon_date": "2026-01-01",
                    "horizon_datetime": "2026-01-02T20:00:00+00:00",
                }
            ],
        }
    ) == ("data_gap", "posttransfusion_evaluation_horizon_conflict")


def test_047_date_only_horizon_datetime_keeps_date_precision():
    assert transfusion._programmatic_047_status(
        {
            "bloodtrans_record": [
                {"record_content": "2026-01-01 16:00:00输血结束。"}
            ],
            "daily_course_record": [],
            "__evaluation_horizon_rows__": [
                {"horizon_datetime": "2026-01-02"}
            ],
        }
    ) == ("not_applicable", "evaluation_window_not_mature")


def test_047_inline_effect_does_not_satisfy_earlier_mature_event():
    assert transfusion._programmatic_047_status(
        {
            "bloodtrans_record": [
                {
                    "record_content": "2026-01-01 10:00:00输血结束；输血后复查血红蛋白改善。",
                    "record_time": "2026-01-01 11:00:00",
                },
                {
                    "record_content": "2026-01-02 22:00:00输血结束；未记录输血后评价。",
                },
            ],
            "daily_course_record": [],
            "__evaluation_horizon_rows__": [{"horizon_date": "2026-01-03"}],
        }
    ) == ("non_compliant", "posttransfusion_evaluation_missing")


def test_047_future_record_evaluation_is_ignored_like_future_daily_course():
    assert transfusion._programmatic_047_status(
        {
            "bloodtrans_record": [
                {
                    "record_content": "2026-01-01 16:00:00输血结束；输血后复查血红蛋白改善。",
                    "record_time": "2026-01-03 09:00:00",
                }
            ],
            "daily_course_record": [],
            "__evaluation_horizon_rows__": [{"horizon_date": "2026-01-02"}],
        }
    ) == ("not_applicable", "evaluation_window_not_mature")


@pytest.mark.parametrize(
    "bloodtrans_rows",
    tuple(
        [
            {
                "record_content": f"2026-01-01 16:00:00输血结束；{missing_text}",
            }
        ]
        for missing_text in ("未记录输血后评价。", "缺少输血后评价。", "未书写输血后评价。")
    )
    + (
        [
            {"record_content": "2026-01-01 16:00:00输血结束；输注过程顺利。"},
        ],
        [
            {
                "record_content": "2026-01-01 10:00:00输血结束；输血后复查血红蛋白改善。",
                "record_time": "2026-01-01 11:00:00",
            },
            {"record_content": "2026-01-02 16:00:00输血结束。"},
        ],
    ),
)
def test_047_mature_window_retains_missing_and_weak_context_defects(
    bloodtrans_rows: list[dict[str, Any]],
):
    assert transfusion._programmatic_047_status(
        {
            "bloodtrans_record": bloodtrans_rows,
            "daily_course_record": [],
            "__evaluation_horizon_rows__": [{"horizon_date": "2026-01-04"}],
        }
    ) == ("non_compliant", "posttransfusion_evaluation_missing")


@pytest.mark.asyncio
async def test_047_uses_one_assessment_for_status_and_display_facts(
    monkeypatch: pytest.MonkeyPatch,
):
    session = _session(
        horizon_date="2026-01-02",
        bloodtrans_rows=[
            {
                "document_id": "BT-1",
                "record_content": "2026-01-01 16:00:00输血结束。",
            }
        ],
    )
    calls = 0
    original = transfusion._programmatic_047_assessment

    def counted(documents: dict[str, Any]):
        nonlocal calls
        calls += 1
        return original(documents)

    monkeypatch.setattr(transfusion, "_programmatic_047_assessment", counted)

    result = await _execute(session)

    assert calls == 1
    # 仅一次专用记录实施核验（与 045/046 共享），状态与展示事实不重复计算。
    assert result.llm_call_count == 1
    assert result.customer_display_facts == ()


async def _execute_with_effect_labels(session: Any, effect_labels: dict[str, tuple[str, str]]):
    client = FrozenTransfusionProtocolClient(default_course_label="record", effect_labels=effect_labels)
    result = await execute_luxian_0609_native_transfusion_rules(
        rule_ids=("LX0609-07-03-01",),
        wrapper_rules=[],
        evidence_payload=None,
        institute_id="I",
        patient_id="P",
        visit_id="V",
        source_schema=None,
        llm_client=client,
        evidence_snapshot=session.snapshot,
        evidence_materials=session.materials,
        decision_rule_ids=("LX0609-07-03-01",),
    )
    return result, client


_UNMATCHED_EVALUATION = "复查血红蛋白较前变化不大，考虑消耗所致，继续观察。"
_DATE_ONLY_SEMANTIC_EVALUATION = "输血后症状明显改善，疗效满意。"


def _effect_session():
    return _session(
        horizon_date="2026-01-03",
        bloodtrans_rows=[{"document_id": "BT-1", "record_content": "2026-01-01 16:00:00输血结束。"}],
        daily_rows=[{
            "document_title": "输血后评价记录",
            "document_id": "D-1",
            "record_time": "2026-01-02 08:00:00",
            "record_content": "今日查房，患者精神可。" + _UNMATCHED_EVALUATION,
        }],
    )


@pytest.mark.asyncio
async def test_047_date_only_semantic_evaluation_is_reviewed_then_keeps_time_gap():
    session = _session(
        horizon_date="2026-06-07",
        bloodtrans_rows=[
            {
                "document_id": "BT-DATE-SEMANTIC",
                "record_content": "2026-06-05 10:00:00输血结束。",
            }
        ],
        daily_rows=[
            {
                "document_title": "输血后评价记录",
                "document_id": "DATE-SEMANTIC",
                "record_time": "2026-06-06",
                "record_content": _DATE_ONLY_SEMANTIC_EVALUATION,
            }
        ],
    )

    result, client = await _execute_with_effect_labels(
        session,
        {
            _DATE_ONLY_SEMANTIC_EVALUATION: (
                "evaluated",
                "输血后症状明显改善",
            )
        },
    )

    assert _canonical_state(result=result, session=session) == (
        "data_gap",
        "authoritative_time_missing",
    )
    assert any(
        "lx0609-posttransfusion-effect-v1" in prompt
        for prompt in client.protocol_prompts
    )


@pytest.mark.asyncio
async def test_047_unmatched_wording_is_confirmed_by_model_not_closed_world_defect():
    """“较前变化不大”不在词表内：交受控模型确认评价后合规（2026-10-22）。"""
    session = _effect_session()
    result, client = await _execute_with_effect_labels(
        session, {_UNMATCHED_EVALUATION: ("evaluated", "复查血红蛋白较前变化不大")},
    )

    assert _canonical_state(result=result, session=session) == ("compliant", "requirement_satisfied")
    assert any("lx0609-posttransfusion-effect-v1" in prompt for prompt in client.protocol_prompts)


@pytest.mark.asyncio
async def test_047_model_not_evaluated_keeps_python_missing_defect():
    session = _effect_session()
    result, _ = await _execute_with_effect_labels(session, {})

    assert _canonical_state(result=result, session=session) == ("non_compliant", "requirement_violated")


@pytest.mark.asyncio
async def test_047_model_unclear_is_data_gap_not_defect():
    session = _effect_session()
    result, _ = await _execute_with_effect_labels(session, {_UNMATCHED_EVALUATION: ("unclear", "")})

    assert _canonical_state(result=result, session=session)[0] == "data_gap"
    assert result.decisions[0].reason_code == "semantic_extraction_unresolved"


@pytest.mark.asyncio
@pytest.mark.parametrize("wording", ["输血后复查血常规。", "输血效果好，继续观察。"])
async def test_047_loose_wording_without_clinical_or_lab_effect_is_not_auto_compliant(wording):
    """院方口径：评价须含临床或实验室效果。“输血后复查”“效果好”交模型确认，模型判否仍缺评价。"""
    session = _session(
        horizon_date="2026-01-03",
        bloodtrans_rows=[{"document_id": "BT-1", "record_content": "2026-01-01 16:00:00输血结束。"}],
        daily_rows=[{"document_title": "输血后评价记录", "document_id": "D-1", "record_time": "2026-01-02 08:00:00", "record_content": wording}],
    )
    result, client = await _execute_with_effect_labels(session, {})

    assert _canonical_state(result=result, session=session) == ("non_compliant", "requirement_violated")
    assert any("lx0609-posttransfusion-effect-v1" in prompt for prompt in client.protocol_prompts)
