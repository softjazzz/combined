"""067 的正文存在性、时间优先级及客户定位合同。"""

import pytest

from test_luxian_0609_native_extended_document_execution import (
    _canonical_extended_result,
    _evaluate_selected,
)


async def _run(daily, senior=()):
    snapshot, materials, result, reduced = await _evaluate_selected(
        ("LX0609-067",),
        {
            "inpat_registration": ({"patient_status": "出院", "discharge_datetime": "2026-07-03 12:00:00"},),
            "daily_course_record": daily,
            "senior_course_record": senior,
        },
    )
    canonical = _canonical_extended_result(
        rule_id="LX0609-067", snapshot=snapshot, materials=materials,
        result=result, reduced=reduced,
    )
    assert result.llm_call_count == result.total_tokens == 0
    return canonical


def _row(body, *, document_id="shell", time="2026-07-02 09:00:00"):
    return {"document_id": document_id, "submit_datetime": time, "record_content": body}


@pytest.mark.asyncio
@pytest.mark.parametrize("body", [None, "", " \n\t", "医生签名:", "医师签名：", " 医生 签名 : \n"])
async def test_window_shell_is_specific_body_gap_with_exact_location(body):
    result = await _run((_row(body), _row("病情稳定", document_id="outside", time="2026-07-01 09:00:00")))
    assert result["status"] == "data_gap"
    assert result["reason_code"] == "required_field_missing"
    assert result["customer_display_facts"]["missing_body_count"] == 1
    assert result["missing_fields"] == ["出院前一天或当天病程记录正文（1份）"]
    assert "正文" in result["customer_message"]
    assert "未找到" not in result["customer_message"]
    assert result["data_gap_details"]["missing_fields"] == result["missing_fields"]
    assert [item["source_document_id"] for item in result["customer_evidence"]] == ["shell"]
    assert "source_document_refs" not in result["customer_display_facts"]


@pytest.mark.asyncio
@pytest.mark.parametrize("body", ["稳定", "医生签名:继续观察。", "病情稳定。医生签名:"])
async def test_short_or_signature_containing_body_is_present(body):
    result = await _run((_row("医生签名:"),), (_row(body, document_id="valid"),))
    assert result["status"] == "compliant"
    assert [item["source_document_id"] for item in result["customer_evidence"]] == ["valid"]


@pytest.mark.asyncio
async def test_undated_body_takes_time_gap_priority_over_window_shell():
    result = await _run((_row("医生签名:"), _row("病情稳定", document_id="undated", time=None)))
    assert result["reason_code"] == "authoritative_time_missing"
    assert [item["source_document_id"] for item in result["customer_evidence"]] == ["undated"]


@pytest.mark.asyncio
async def test_undated_shell_keeps_existing_time_gap_contract():
    result = await _run((_row(None, time=None),))
    assert result["reason_code"] == "authoritative_time_missing"
    assert [item["source_document_id"] for item in result["customer_evidence"]] == ["shell"]


@pytest.mark.asyncio
async def test_two_window_shells_report_both_and_no_other_documents():
    result = await _run((_row(None),), (_row("医师签名：", document_id="senior"),))
    assert result["missing_fields"] == ["出院前一天或当天病程记录正文（2份）"]
    assert {item["source_document_id"] for item in result["customer_evidence"]} == {"shell", "senior"}


@pytest.mark.asyncio
async def test_title_and_author_do_not_replace_missing_body_column():
    result = await _run(({
        "document_id": "shell", "record_time": "2026-07-02 09:00:00",
        "document_title": "日常病程记录", "author_name": "测试医师",
    },))
    assert result["reason_code"] == "required_field_missing"


@pytest.mark.asyncio
async def test_no_rows_keeps_source_empty_contract():
    result = await _run(())
    assert result["reason_code"] == "source_empty"


@pytest.mark.parametrize("field,value", [("missing_body_count", 0), ("missing_body_count", True), ("checked_dates", ["2026-07-01", "2026-07-03"])])
def test_body_gap_display_rejects_invalid_executor_facts(field, value):
    from app.services.luxian_0609.discharge_result_mapping import safe_discharge_customer_display_facts

    raw = {
        "failure_kind": "predischarge_course_body_missing", "discharge_date": "2026-07-03",
        "checked_dates": ["2026-07-02", "2026-07-03"], "missing_body_count": 1,
    }
    raw[field] = value
    assert safe_discharge_customer_display_facts(rule_id="LX0609-067", raw=raw) is None
