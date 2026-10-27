"""旧时效映射：未知版本与日期精度不得冒充确定完成时刻。"""

from datetime import date

import pytest

from tests.unit.test_luxian_0609_native_extended_document_execution import (
    _canonical_extended_result,
    _evaluate_selected,
)
from test_luxian_0609_death_record_timeliness import saved_roundtrip


async def pipeline(rule, rows):
    snapshot, materials, execution, reduced = await _evaluate_selected((rule,), rows)
    result = _canonical_extended_result(
        rule_id=rule,
        snapshot=snapshot,
        materials=materials,
        result=execution,
        reduced=reduced,
    )
    assert execution.llm_call_count == execution.total_tokens == 0
    loaded = saved_roundtrip(result)
    assert loaded["status"] == result["status"]
    return result


@pytest.mark.asyncio
@pytest.mark.parametrize("raw", ["未知", "无", "not-a-time"])
async def test_alive_case_invalid_death_placeholder_does_not_assert_death(raw):
    result = await pipeline(
        "LX0609-08-01-01",
        {
            "inpat_registration": (
                {
                    "discharge_datetime": "2026-01-02 08:00:00",
                    "patient_status": "出院",
                    "death_time": raw,
                },
            ),
            "discharge_record": (
                {"document_id": "D", "record_time": "2026-01-02 09:00:00"},
            ),
        },
    )
    assert result["status"] == "compliant"


@pytest.mark.asyncio
@pytest.mark.parametrize("unknown", [None, "", "2026-01-02", date(2026, 1, 2)])
@pytest.mark.parametrize("reverse", [False, True])
async def test_discharge_unknown_version_does_not_get_dropped(unknown, reverse):
    records = (
        {
            "document_id": "KNOWN",
            "record_time": "2026-01-02 09:00:00",
            "record_content": "出院记录。",
        },
        {
            "document_id": "UNKNOWN",
            "record_time": unknown,
            "record_content": "修订后的出院记录。",
        },
    )
    result = await pipeline(
        "LX0609-08-01-01",
        {
            "inpat_registration": (
                {"discharge_datetime": "2026-01-02 08:00:00", "patient_status": "出院"},
            ),
            "discharge_record": tuple(reversed(records)) if reverse else records,
        },
    )
    assert result["status"] == "data_gap"
    assert result["reason_code"] == "authoritative_time_missing"


@pytest.mark.asyncio
@pytest.mark.parametrize("source", ["death_record", "inpat_registration"])
@pytest.mark.parametrize("raw", ["2026-01-01", date(2026, 1, 1)])
async def test_death_date_is_not_promoted_to_midnight(source, raw):
    result = await pipeline(
        "LX0609-09-02-01",
        {
            source: ({"document_id": "DEATH", "death_datetime": raw},),
            "death_discussion": (
                {
                    "document_id": "DISCUSS",
                    "record_time": "2026-01-02 08:00:00",
                    "record_content": "死亡病例讨论。",
                },
            ),
            "evaluation_context.horizon": (
                {"horizon_date": "2026-01-20", "basis": "evaluation_as_of"},
            ),
        },
    )
    assert result["status"] == "data_gap"
    assert result["reason_code"] == "authoritative_time_missing"


@pytest.mark.asyncio
@pytest.mark.parametrize("raw", ["2026-01-02", date(2026, 1, 2)])
async def test_death_discussion_completion_date_does_not_become_exact_clock(raw):
    result = await pipeline(
        "LX0609-09-02-01",
        {
            "death_record": (
                {"document_id": "DEATH", "death_datetime": "2026-01-01 08:00:00"},
            ),
            "death_discussion": (
                {
                    "document_id": "DISCUSS",
                    "record_time": raw,
                    "record_content": "死亡病例讨论。",
                },
            ),
            "evaluation_context.horizon": (
                {"horizon_date": "2026-01-20", "basis": "evaluation_as_of"},
            ),
        },
    )
    assert result["status"] == "data_gap"
    assert result["reason_code"] == "authoritative_time_missing"
