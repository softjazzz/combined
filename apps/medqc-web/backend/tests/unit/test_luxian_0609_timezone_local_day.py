"""带时区的医嘱时间按医院本地时间取自然日（02-01-04 与 02-01-05 口径一致）。"""

from datetime import date, datetime, timedelta, timezone

from app.services.luxian_0609.course_quality.rules_008_009 import _authoritative_natural_date


def test_utc_order_time_is_projected_to_hospital_local_day():
    assert _authoritative_natural_date("2026-06-01T17:00:00+00:00") == date(2026, 6, 2)
    assert _authoritative_natural_date("2026-06-01T17:00:00Z") == date(2026, 6, 2)
    assert _authoritative_natural_date(
        datetime(2026, 6, 1, 17, tzinfo=timezone.utc)
    ) == date(2026, 6, 2)


def test_naive_and_local_offset_times_keep_their_day():
    assert _authoritative_natural_date("2026-06-01 17:00:00") == date(2026, 6, 1)
    assert _authoritative_natural_date(
        datetime(2026, 6, 1, 23, tzinfo=timezone(timedelta(hours=8)))
    ) == date(2026, 6, 1)
    assert _authoritative_natural_date("2026-06-01") == date(2026, 6, 1)
