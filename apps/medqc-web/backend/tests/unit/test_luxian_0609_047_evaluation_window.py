from __future__ import annotations

from datetime import datetime
from typing import Any

import pytest

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
        selected_rule_ids=("LX0609-047",),
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
        rule_ids=("LX0609-047",),
        wrapper_rules=[],
        evidence_payload=None,
        institute_id="I",
        patient_id="P",
        visit_id="V",
        source_schema=None,
        llm_client=None,
        evidence_snapshot=session.snapshot,
        evidence_materials=session.materials,
        decision_rule_ids=("LX0609-047",),
    )


def _canonical_state(*, result: Any, session: Any) -> tuple[str, str]:
    canonical = bind_and_reduce_luxian_0609_rule_decisions(
        decisions=result.decisions,
        expected_rule_ids=("LX0609-047",),
        snapshot=session.snapshot,
        evidence_materials=session.materials,
    )[0]
    return canonical.final_state.value, canonical.reason_code


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


def test_047_explicit_missing_only_controls_its_own_unmatured_event():
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
    ) == ("not_applicable", "evaluation_window_not_mature")


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
    assert result.llm_call_count == 0
    assert result.customer_display_facts == ()
