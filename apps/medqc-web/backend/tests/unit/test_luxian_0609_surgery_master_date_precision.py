"""003 逐台覆盖：病案首页手术时间只精确到日时按日历日关联手术记录。"""

from datetime import datetime

from app.services.luxian_0609.native_surgery_gate_execution import (
    _surgery_records_cover_master_rows,
)


def _record(begin: str) -> dict:
    return {"document_id": "E1", "surgery_begin_time": begin}


def test_date_only_master_rows_split_from_one_operation_are_covered_by_same_day_record():
    masters = (
        {"surgery_begin_datetime": datetime(2025, 8, 15), "surgeon": "甲"},
        {"surgery_begin_datetime": datetime(2025, 8, 15), "surgeon": "甲"},
    )
    assert _surgery_records_cover_master_rows(masters, (_record("2025-08-15 09:45:00+08"),))


def test_date_only_master_on_another_day_is_not_covered():
    masters = ({"surgery_begin_datetime": datetime(2025, 8, 8), "surgeon": "甲"},)
    assert not _surgery_records_cover_master_rows(masters, (_record("2025-08-15 09:45:00+08"),))


def test_precise_master_time_still_requires_exact_match():
    masters = ({"surgery_begin_datetime": datetime(2025, 8, 15, 8, 0), "surgeon": "甲"},)
    assert not _surgery_records_cover_master_rows(masters, (_record("2025-08-15 09:45:00+08"),))
