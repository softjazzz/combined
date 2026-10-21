"""正文签名读取的身份边界；病例和医师均为合成资料。"""

import pytest

from app.services.luxian_0609.extended_document.shared import course_record_signer
from test_luxian_0609_physician_handoff import _body_signed, _execute


@pytest.mark.parametrize("label", ("医师签名", "医生签名"))
@pytest.mark.parametrize("submitter", (None, "李乙", "张甲"))
def test_explicit_terminal_signature_is_independent_of_submitter(label, submitter):
    assert course_record_signer({
        "record_content": f"患者恢复平稳。\n{label}： 张甲\n",
        "submitter": submitter,
    }) == "张甲"


def test_structured_signature_has_priority_over_body_and_submitter():
    assert course_record_signer({
        "physician_sign": "张甲", "record_content": "医师签名：李乙", "submitter": "李乙",
    }) == "张甲"


@pytest.mark.parametrize("body", (
    "张甲查房后建议继续观察。",
    "患者诉此前记录写了医师签名：张甲，具体签名尚待核实。",
    "上级医师签名：张甲",
    "医师签名：张甲 李乙",
    "医师签名：张甲/李乙",
    "医师签名：张甲\n医师签名：李乙",
    "医师签名：",
))
def test_mentions_role_signatures_and_ambiguous_lists_are_not_single_author(body):
    assert course_record_signer({"record_content": body, "submitter": "张甲"}) == ""


@pytest.mark.asyncio
async def test_body_signatures_preserve_handoff_change_and_missing_record_checks():
    rows = (
        _body_signed("A1", "2026-08-20 08:00:00", "张甲", "代录人"),
        _body_signed("A2", "2026-08-21 08:00:00", "张甲", None),
        _body_signed("B1", "2026-08-22 08:00:00", "李乙", "代录人"),
        _body_signed("B2", "2026-08-23 08:00:00", "李乙", None),
    )
    result = await _execute(
        {"daily_course_record": rows},
        unavailable_sources={"physician_change_event", "inpat_nondrug_order"},
    )
    assert result.decisions[0].reason_code == "requirement_violated"
    assert result.llm_call_count == result.total_tokens == 0


@pytest.mark.asyncio
async def test_ambiguous_body_signature_keeps_handoff_timeline_unresolved():
    row = _body_signed("A1", "2026-08-20 08:00:00", "张甲 李乙", "张甲")
    result = await _execute(
        {"daily_course_record": (row,)},
        unavailable_sources={"physician_change_event", "inpat_nondrug_order"},
    )
    assert result.decisions[0].reason_code == "required_field_missing"
    assert result.llm_call_count == result.total_tokens == 0
