"""LX0609-09-02-01 死亡病例讨论时限的确定性判定。"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Any, Mapping, Sequence

from .shared import _clean, _parse_datetime, _row_time


@dataclass(frozen=True)
class DeathDiscussionOutcome:
    final_state: str
    reason_code: str
    display_facts: Mapping[str, Any] | None = None


def _horizon_unavailable(
    *, death_time: datetime, issue: str
) -> DeathDiscussionOutcome:
    return DeathDiscussionOutcome(
        "data_gap",
        issue,
        {
            "verification_kind": "death_discussion_evaluation_horizon_unavailable",
            "death_time": death_time.isoformat(sep=" "),
            "issue": issue,
        },
    )


def evaluate_death_discussion_timeliness(
    *,
    death_time: datetime | None,
    death_rows: Sequence[Mapping[str, Any]],
    discussion_rows: Sequence[Mapping[str, Any]],
    discussion_error: str,
    horizon_rows: Sequence[Mapping[str, Any]],
    horizon_error: str,
) -> DeathDiscussionOutcome:
    """按死亡后最早有效讨论记录核对七日时限。"""

    if discussion_error:
        return DeathDiscussionOutcome("data_gap", discussion_error)
    if death_time is None:
        return DeathDiscussionOutcome(
            "data_gap",
            "authoritative_time_missing",
        )

    timed_discussions = tuple(
        (candidate, index, row)
        for index, row in enumerate(discussion_rows)
        if (candidate := _row_time(row)) is not None
    )
    postdeath_discussions = tuple(
        candidate
        for candidate in timed_discussions
        if candidate[0] >= death_time
    )
    selected_discussion = min(
        postdeath_discussions,
        key=lambda candidate: (candidate[0], candidate[1]),
        default=None,
    )
    death_row = next(
        (
            row
            for row in death_rows
            if _parse_datetime(row.get("death_datetime") or row.get("death_time"))
            == death_time
        ),
        next(
            (row for row in death_rows if _row_time(row) == death_time),
            None,
        ),
    )
    source_document_refs: list[dict[str, str]] = []
    if death_row is not None:
        death_document_id = _clean(death_row.get("document_id") or death_row.get("id"))
        if death_document_id:
            source_document_refs.append(
                {
                    "source_type": "death_record",
                    "source_document_id": death_document_id,
                }
            )

    if discussion_rows and not timed_discussions:
        return DeathDiscussionOutcome(
            "data_gap",
            "authoritative_time_missing",
        )
    if selected_discussion is not None:
        discussion_time, _, discussion_row = selected_discussion
        hours = (discussion_time - death_time).total_seconds() / 3600
        final_state = "compliant" if hours <= 168 else "non_compliant"
        reason_code = (
            "requirement_within_threshold"
            if hours <= 168
            else "threshold_exceeded"
        )
        discussion_document_id = _clean(
            discussion_row.get("document_id") or discussion_row.get("id")
        )
        if discussion_document_id:
            source_document_refs.append(
                {
                    "source_type": "death_discussion",
                    "source_document_id": discussion_document_id,
                }
            )
        return DeathDiscussionOutcome(
            final_state,
            reason_code,
            {
                "verification_kind": "death_discussion_timeliness_check",
                "death_time": death_time.isoformat(sep=" "),
                "discussion_time": discussion_time.isoformat(sep=" "),
                "threshold_hours": 168,
                "actual_interval_hours": round(hours, 2),
                "source_document_refs": source_document_refs,
            },
        )

    if horizon_error:
        if horizon_error in {
            "authoritative_time_missing",
            "authoritative_time_conflict",
        }:
            return _horizon_unavailable(death_time=death_time, issue=horizon_error)
        return DeathDiscussionOutcome("data_gap", horizon_error)
    if len(horizon_rows) != 1:
        return _horizon_unavailable(
            death_time=death_time,
            issue="authoritative_time_missing",
        )

    horizon_row = horizon_rows[0]
    horizon_time = _parse_datetime(horizon_row.get("horizon_datetime"))
    try:
        horizon_date = date.fromisoformat(str(horizon_row.get("horizon_date") or ""))
    except ValueError:
        horizon_date = None
    deadline = death_time + timedelta(hours=168)
    if horizon_time is not None:
        if horizon_time < death_time:
            return _horizon_unavailable(
                death_time=death_time,
                issue="authoritative_time_conflict",
            )
        if horizon_time < deadline:
            return DeathDiscussionOutcome(
                "data_gap",
                "evaluation_window_not_mature",
                {
                    "verification_kind": "death_discussion_window_not_mature",
                    "death_time": death_time.isoformat(sep=" "),
                    "deadline_time": deadline.isoformat(sep=" "),
                    "evaluation_time": horizon_time.isoformat(sep=" "),
                    "remaining_seconds": int((deadline - horizon_time).total_seconds()),
                },
            )
        mature = True
    elif horizon_date is not None:
        if horizon_date < death_time.date():
            return _horizon_unavailable(
                death_time=death_time,
                issue="authoritative_time_conflict",
            )
        # 只有日期时，截止日当天无法证明具体时刻已经越过截止点。
        mature = horizon_date > deadline.date()
        if not mature:
            return DeathDiscussionOutcome(
                "data_gap",
                "evaluation_window_not_mature",
                {
                    "verification_kind": "death_discussion_window_not_mature",
                    "death_time": death_time.isoformat(sep=" "),
                    "deadline_time": deadline.isoformat(sep=" "),
                    "evaluation_date": horizon_date.isoformat(),
                },
            )
    else:
        return _horizon_unavailable(
            death_time=death_time,
            issue="authoritative_time_missing",
        )

    if mature:
        return DeathDiscussionOutcome(
            "non_compliant",
            "required_document_missing",
            {
                "failure_kind": "death_discussion_missing_after_deadline",
                "death_time": death_time.isoformat(sep=" "),
                "threshold_hours": 168,
                "discussion_count": 0,
                "source_document_refs": source_document_refs,
            },
        )
    raise AssertionError("unreachable death discussion maturity state")
