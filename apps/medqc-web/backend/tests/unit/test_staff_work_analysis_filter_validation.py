"""报表筛选的独立参数边界；不连接数据库。"""

from datetime import datetime, timezone

import pytest

from app.services import staff_work_analysis_service as service


@pytest.mark.parametrize("filters", [
    {"department": "内科"},
    {"institute_id": "A"},
    {"institute_id": "A", "department": " "},
    {"start_date": "2026-09-01"},
    {"end_date": "2026-09-28"},
    {"start_date": "2026-09-28", "end_date": "2026-09-01"},
    {"start_date": "2026-02-30", "end_date": "2026-03-01"},
    {"start_date": "2026-9-01", "end_date": "2026-09-02"},
    {"start_date": "9999-12-31", "end_date": "9999-12-31"},
    {"as_of": "2026-09-28T10:00:00"},
    {"as_of": "not-a-date"},
])
def test_invalid_filters_are_rejected_before_database_access(monkeypatch, filters):
    monkeypatch.setattr(service, "SessionLocal", None)
    with pytest.raises(service.StaffWorkAnalysisInvalid):
        service.get_staff_work_analysis(period="this_month", **filters)


def test_custom_day_uses_shanghai_midnight_and_exclusive_next_midnight():
    scope = service._scope(
        period="this_month", start_date="2026-09-21", end_date="2026-09-21",
        as_of="2026-09-28T00:00:00Z",
    )
    assert scope.window.utc_start == datetime(2026, 9, 20, 16)
    assert scope.window.utc_end == datetime(2026, 9, 21, 16)
    assert scope.as_of == datetime(2026, 9, 28, tzinfo=timezone.utc)
