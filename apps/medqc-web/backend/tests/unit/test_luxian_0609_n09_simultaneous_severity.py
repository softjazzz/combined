"""N09：同刻跨行解除/重开不得用输入行序或事件类型假定先后。"""
from datetime import date
from itertools import permutations

import pytest

from app.services.luxian_0609.course_quality.rules_008_009 import (
    _severity_active_date_intervals,
)
from test_luxian_0609_round2_severity_regressions import _final, _note, _order


@pytest.mark.asyncio
@pytest.mark.parametrize("severity,suffix", [("serious", "04"), ("critical", "05")])
@pytest.mark.parametrize("order_indices", list(permutations(range(3))))
async def test_same_time_restart_is_data_gap_for_every_row_order(severity, suffix, order_indices):
    rows = [
        _order("2026-01-01 08:00:00", severity),
        _order("2026-01-01 10:00:00", severity, "end"),
        _order("2026-01-01 10:00:00", severity),
    ]
    result = await _final(
        f"LX0609-02-01-{suffix}", [rows[index] for index in order_indices], [_note(1)],
    )
    assert result["status"] == "data_gap"
    assert result["reason_code"] == "authoritative_time_missing"


@pytest.mark.asyncio
@pytest.mark.parametrize("severity,suffix", [("serious", "04"), ("critical", "05")])
@pytest.mark.parametrize("restart", [None, "2026-01-01 15:00:00", "2026-01-01 10:00:01"])
async def test_known_stop_and_later_restart_keep_existing_coverage(severity, suffix, restart):
    rows = [
        _order("2026-01-01 08:00:00", severity),
        _order("2026-01-01 10:00:00", severity, "end"),
    ]
    if restart is not None:
        rows.append(_order(restart, severity))
    result = await _final(f"LX0609-02-01-{suffix}", rows, [_note(1)])
    assert result["status"] == ("non_compliant" if restart else "compliant")


def test_one_stopped_order_with_equal_start_end_has_known_lifecycle():
    row = dict(_order("2026-01-01 10:00:00"), lifecycle_state="stopped",
               planned_end_datetime="2026-01-01 10:00:00")
    assert _severity_active_date_intervals([row], horizon_date=date(2026, 1, 7)) == (
        (date(2026, 1, 1), date(2026, 1, 1)),
    )


def test_implicit_stop_and_different_row_restart_are_also_ambiguous():
    stopped = dict(_order("2026-01-01 08:00:00"), lifecycle_state="stopped",
                   planned_end_datetime="2026-01-01 10:00:00")
    assert _severity_active_date_intervals(
        [stopped, _order("2026-01-01 10:00:00")], horizon_date=date(2026, 1, 7),
    ) is None


def test_out_of_horizon_ambiguous_events_do_not_change_closed_interval():
    rows = [_order("2026-01-01 08:00:00"), _order("2026-01-01 10:00:00", event="end"),
            _order("2026-01-08 10:00:00"), _order("2026-01-08 10:00:00", event="end")]
    assert _severity_active_date_intervals(rows, horizon_date=date(2026, 1, 7)) == (
        (date(2026, 1, 1), date(2026, 1, 1)),
    )
