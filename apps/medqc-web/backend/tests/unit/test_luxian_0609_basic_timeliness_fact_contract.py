from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from app.services.luxian_0609.basic_timeliness_facts import (
    AdmissionAnchorState,
    CourseRoundRole,
    associate_timeliness_event,
    classify_course_round_role,
    extract_admission_anchor,
    extract_document_events,
    extract_rescue_events,
    parse_authoritative_datetime,
)


@pytest.mark.unit
@pytest.mark.parametrize(
    "value",
    [
        datetime(2026, 10, 5, 9, tzinfo=timezone(timedelta(hours=8))),
        datetime(2026, 10, 5, 1, tzinfo=timezone.utc),
        "2026-10-05T09:00:00+08:00",
        "2026-10-05T01:00:00Z",
        "2026-10-05 01:00:00+00:00",
        "2026-10-05 09:00:00",
    ],
)
def test_authoritative_time_normalizes_same_instant_to_hospital_time(value) -> None:
    assert parse_authoritative_datetime(value) == datetime(2026, 10, 5, 9)


@pytest.mark.unit
@pytest.mark.parametrize(
    "value",
    [
        "2026-10-05",
        "完成于2026-10-05 09:00:00",
        "2026-13-05T09:00:00+08:00",
        "2026-10-05T09:00:00+25:00",
    ],
)
def test_authoritative_time_still_rejects_invalid_or_descriptive_values(value) -> None:
    assert parse_authoritative_datetime(value) is None


@pytest.mark.unit
def test_conflicting_registration_admission_times_are_not_silently_reduced() -> None:
    fact = extract_admission_anchor(
        registration_rows=(
            {"admission_datetime": "2026-06-01 08:00:00"},
            {"admission_datetime": "2026-06-01 09:00:00"},
        ),
        admission_rows=(),
        discharge_rows=(),
        allow_date_fallback=True,
    )

    assert fact.state is AdmissionAnchorState.CONFLICT
    assert fact.anchor_time is None
    assert fact.candidate_count == 2


@pytest.mark.unit
def test_document_event_accepts_submit_datetime_as_authoritative_time() -> None:
    events = extract_document_events(
        (
            {
                "document_id": "rescue-1",
                "submit_datetime": "2026-06-01 15:00:00",
            },
        )
    )

    assert events[0].observed_time == datetime(2026, 6, 1, 15, 0)
    assert events[0].document_id == "rescue-1"


@pytest.mark.unit
def test_rescue_event_keeps_exact_and_one_second_over_boundary() -> None:
    events = extract_rescue_events(
        (
            {
                "document_id": "exact",
                "submit_datetime": "2026-06-01 15:00:00",
                "record_content": "抢救结束时间：2026-06-01 09:00:00",
            },
            {
                "document_id": "late",
                "submit_datetime": "2026-06-02 15:00:01",
                "record_content": "抢救结束时间：2026-06-02 09:00:00",
            },
        )
    )

    exact = associate_timeliness_event(
        anchor_time=events[0].rescue_end_time,
        observed_event=events[0].document,
        threshold_hours=6,
    )
    late = associate_timeliness_event(
        anchor_time=events[1].rescue_end_time,
        observed_event=events[1].document,
        threshold_hours=6,
    )

    assert exact.state == "within"
    assert exact.elapsed_hours == 6
    assert late.state == "late"
    assert late.overdue_hours == pytest.approx(1 / 3600)


@pytest.mark.unit
@pytest.mark.parametrize(
    ("title", "author_title", "expected"),
    [
        ("主治医师首次查房记录", "", CourseRoundRole.ATTENDING_OR_ABOVE),
        ("上级医师查房记录", "", CourseRoundRole.ATTENDING_OR_ABOVE),
        ("上级医生查房记录", "", CourseRoundRole.ATTENDING_OR_ABOVE),
        ("普通查房记录", "副主任医师", CourseRoundRole.SENIOR),
        ("查房记录", "", CourseRoundRole.AMBIGUOUS),
        ("日常病程记录", "", CourseRoundRole.NONE),
    ],
)
def test_course_round_role_is_a_controlled_fact(
    title: str,
    author_title: str,
    expected: CourseRoundRole,
) -> None:
    assert (
        classify_course_round_role(
            {"document_title": title, "author_title": author_title}
        )
        is expected
    )
