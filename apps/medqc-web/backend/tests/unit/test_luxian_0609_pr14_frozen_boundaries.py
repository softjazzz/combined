"""PR14复审：未来材料不得改变冻结结论或混入选中证据。"""
from datetime import datetime, timedelta

import pytest

from test_luxian_0609_death_record_timeliness import (
    DEATH, final_result as death_final, row as death_row, saved_roundtrip,
)
from test_luxian_0609_stage_summary_timeliness import (
    START, document, final_result as summary_final,
)

FROZEN = "2026-01-01T12:00:00+08:00"


def assert_saved_same(current, baseline, *, ambiguous_id=False):
    for key in ("status", "reason_code", "customer_display_facts"):
        assert current.get(key) == baseline.get(key)
    loaded = saved_roundtrip(current)
    for key in ("status", "reason_code", "customer_display_facts"):
        assert loaded.get(key) == current.get(key)
    if ambiguous_id:
        # 公共投影仍拒绝同来源同ID的多版本定位，不为本修复放宽既有保护。
        assert not current.get("customer_evidence")
    else:
        assert current.get("customer_evidence") == baseline.get("customer_evidence")
    evidence = current.get("customer_evidence", [])
    assert len(loaded["evidence"]) == len(evidence)
    for stored, raw in zip(loaded["evidence"], evidence):
        for key, value in raw.items():
            if key != "source_document_id":
                assert stored[key] == value
        assert "source_document_id" not in stored


@pytest.mark.asyncio
@pytest.mark.parametrize("future_changes", [
    {"document_id": "FUTURE"},
    {"document_id": "FUTURE", "death_datetime": DEATH + timedelta(days=1)},
    {"document_id": "FUTURE", "document_title": "出院记录"},
    {"document_id": "D1"},
])
async def test_death_future_version_cannot_change_frozen_result_or_evidence(future_changes):
    original = death_row(death_datetime=DEATH)
    baseline = await death_final([original], created_at=FROZEN)
    future = death_row(record_time=DEATH + timedelta(days=1, hours=1),
                       record_content="FUTURE_PRIVATE_BODY", **future_changes)
    result = await death_final([future, original], created_at=FROZEN)
    assert baseline["status"] == "compliant"
    assert_saved_same(result, baseline, ambiguous_id=future_changes.get("document_id") == "D1")
    assert "FUTURE_PRIVATE_BODY" not in str(result.get("customer_evidence"))


@pytest.mark.asyncio
async def test_future_discharge_source_cannot_change_terminal_type():
    original = death_row(death_datetime=DEATH)
    baseline = await death_final([original], created_at=FROZEN)
    result = await death_final([original], created_at=FROZEN, discharge_rows=[{
        "document_id": "FUTURE_OUT", "document_title": "出院记录",
        "record_content": "未来出院来源文书", "record_time": "2026-01-02 09:00:00",
    }])
    assert_saved_same(result, baseline)


@pytest.mark.asyncio
@pytest.mark.parametrize("offset,selected", [(0, "AT_BOUNDARY"), (1, "D1")])
async def test_death_exact_frozen_boundary_keeps_microsecond_precision(offset, selected):
    original = death_row(death_datetime=DEATH)
    candidate = death_row(document_id="AT_BOUNDARY", death_datetime=DEATH,
                          record_time=datetime(2026, 1, 1, 12) + timedelta(microseconds=offset))
    result = await death_final([original, candidate], created_at=FROZEN)
    assert result["status"] == "compliant"
    expected = candidate if selected == "AT_BOUNDARY" else original
    assert result["customer_display_facts"]["record_time"] == expected["record_time"].isoformat(sep=" ")
    assert saved_roundtrip(result)["customer_display_facts"] == result["customer_display_facts"]


@pytest.mark.asyncio
async def test_death_freeze_uses_hospital_timezone_and_rejects_date_only_precision():
    rows = [death_row(death_datetime=DEATH), death_row(document_id="AFTER",
        record_time="2026-01-01T04:00:00.000001Z", death_datetime=DEATH)]
    result = await death_final(rows, created_at="2026-01-01T04:00:00Z")
    baseline = await death_final(rows[:1], created_at=FROZEN)
    assert_saved_same(result, baseline)
    unknown = await death_final(rows[:1], created_at="2026-01-01")
    assert (unknown["status"], unknown["reason_code"]) == ("data_gap", "authoritative_time_missing")


@pytest.mark.asyncio
async def test_unknown_death_version_time_stays_gap():
    result = await death_final([death_row(death_datetime=DEATH), death_row(document_id="UNKNOWN", record_time=None)], created_at=FROZEN)
    assert (result["status"], result["reason_code"]) == ("data_gap", "authoritative_time_missing")
    assert saved_roundtrip(result)["status"] == "data_gap"


@pytest.mark.asyncio
async def test_visible_late_death_record_still_reports_24_hour_violation():
    result = await death_final([death_row(90000, death_datetime=DEATH)], created_at="2026-01-03T12:00:00+08:00")
    assert (result["status"], result["reason_code"]) == ("non_compliant", "threshold_exceeded")
    assert saved_roundtrip(result)["status"] == "non_compliant"


@pytest.mark.asyncio
@pytest.mark.parametrize("source,title", [
    ("summary_record", "阶段小结"), ("handoff_record", "交班记录"),
    ("handover_record", "接班记录"), ("transfer_in_record", "转入记录"),
    ("transfer_out_record", "转出记录"),
])
async def test_future_empty_summary_or_substitute_cannot_hide_missing_periods(source, title):
    common = {"inpat_registration": [{"admission_datetime": START}],
              "inpat_registration.discharge_horizon": [{"discharge_datetime": START + timedelta(days=62)}]}
    baseline = await summary_final(common, days=62)
    result = await summary_final({**common, source: [document(93, document_title=title, record_content="")]}, days=62)
    assert baseline["status"] == "non_compliant"
    assert len(baseline["customer_display_facts"]["overdue_deadlines"]) == 2
    assert_saved_same(result, baseline)


@pytest.mark.asyncio
async def test_future_same_id_summary_does_not_create_visible_version_conflict():
    common = {"inpat_registration": [{"admission_datetime": START}],
              "inpat_registration.discharge_horizon": [{"discharge_datetime": START + timedelta(days=62)}],
              "summary_record": [document(30)]}
    baseline = await summary_final(common, days=62)
    result = await summary_final({**common, "summary_record": [document(30), document(93, document_id="S30")]}, days=62)
    assert_saved_same(result, baseline, ambiguous_id=True)


@pytest.mark.asyncio
async def test_visible_or_unknown_empty_summary_still_requires_data():
    for clock in (START + timedelta(days=30), None):
        result = await summary_final({"inpat_registration": [{"admission_datetime": START}],
            "inpat_registration.discharge_horizon": [{"discharge_datetime": START + timedelta(days=62)}],
            "summary_record": [document(record_time=clock, record_content="")]}, days=62)
        assert result["status"] == "data_gap"
        assert saved_roundtrip(result)["status"] == "data_gap"
