from __future__ import annotations

from datetime import datetime

from app.services.luxian_0609.exam_lab_fact_extraction import (
    build_exam_lab_text_projection,
)
from app.services.luxian_0609.exam_lab_window import (
    EvaluationWindowState,
    resolve_evaluation_window_state,
)


def _culture_row(test_id: str, report_datetime: str | None) -> dict[str, str]:
    row = {
        "test_id": test_id,
        "labtest_subject": "细菌培养",
    }
    if report_datetime is not None:
        row["report_datetime"] = report_datetime
    return row


def _projected_culture_times(
    *, culture_rows: tuple[dict[str, str], ...], horizon_row: dict[str, str]
) -> tuple[datetime | None, ...]:
    projection = build_exam_lab_text_projection(
        rows_by_source={
            "labtest_master": culture_rows,
            "evaluation_context.horizon": (horizon_row,),
        },
        max_course_rows=None,
        max_row_chars=None,
        max_context_chars=None,
    )
    return tuple(event.report_time for event in projection.culture_events)


def test_culture_projection_date_horizon_keeps_whole_day_and_unknown_times() -> None:
    times = _projected_culture_times(
        culture_rows=(
            _culture_row("before", "2026-09-10 08:00:00"),
            _culture_row("same-day-late", "2026-09-11 23:59:59"),
            _culture_row("after", "2026-09-12 00:00:00"),
            _culture_row("missing", None),
            _culture_row("invalid", "not-a-time"),
        ),
        horizon_row={"horizon_date": "2026-09-11"},
    )

    assert times == (
        datetime(2026, 9, 10, 8),
        datetime(2026, 9, 11, 23, 59, 59),
        None,
        None,
    )


def test_culture_projection_precise_horizon_uses_inclusive_instant() -> None:
    times = _projected_culture_times(
        culture_rows=(
            _culture_row("before", "2026-09-11 11:59:59"),
            _culture_row("equal", "2026-09-11 12:00:00"),
            _culture_row("after", "2026-09-11 12:00:01"),
            _culture_row("missing", None),
        ),
        horizon_row={
            "horizon_datetime": "2026-09-11 12:00:00",
            "horizon_date": "2026-09-11",
        },
    )

    assert times == (
        datetime(2026, 9, 11, 11, 59, 59),
        datetime(2026, 9, 11, 12),
        None,
    )


def test_culture_projection_keeps_events_when_horizon_fields_cross_dates() -> None:
    projection = build_exam_lab_text_projection(
        rows_by_source={
            "labtest_master": (
                _culture_row("between-conflicting-bounds", "2026-09-11 18:00:00"),
            ),
            "evaluation_context.horizon": ({
                "horizon_datetime": "2026-09-11 12:00:00",
                "horizon_date": "2026-09-12",
            },),
        },
        max_course_rows=None,
        max_row_chars=None,
        max_context_chars=None,
    )

    assert projection.horizon_conflict is True
    assert len(projection.culture_events) == 1
    assert resolve_evaluation_window_state(
        projection=projection,
        event_time=projection.culture_events[0].report_time,
    ) is EvaluationWindowState.CONFLICT


def test_culture_projection_normalizes_local_timezone_and_keeps_incomparable_time() -> None:
    times = _projected_culture_times(
        culture_rows=(
            _culture_row("equal-local", "2026-09-11T12:00:00+08:00"),
            _culture_row("after-local", "2026-09-11T12:00:01+08:00"),
            _culture_row("other-zone", "2026-09-11T05:00:00+00:00"),
        ),
        horizon_row={
            "horizon_datetime": "2026-09-11T12:00:00+08:00",
            "horizon_date": "2026-09-11",
        },
    )

    assert times == (datetime(2026, 9, 11, 12), None)
