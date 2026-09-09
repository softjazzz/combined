"""069已提供但为空的申请时间不能误报机构未接入。"""
import pytest
from test_luxian_0609_consultation_timeliness import _execute


@pytest.mark.asyncio
@pytest.mark.parametrize("value", [None, "", "   "])
async def test_present_empty_request_column_is_missing_time(value):
    result = await _execute(({
        "document_id": "CONSULT-1", "document_title": "会诊记录",
        "request_time": value, "consultation_time": None,
        "record_time": "2026-08-20 10:00:00",
    },))
    assert result.decisions[0].reason_code == "authoritative_time_missing"
    assert result.llm_call_count == 0
