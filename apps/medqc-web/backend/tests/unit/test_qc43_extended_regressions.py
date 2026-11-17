"""确定性出院/用药边界，固定合成材料、无模型调用。"""
import pytest
from test_luxian_0609_native_extended_document_execution import _evaluate, _056_rows


@pytest.mark.asyncio
async def test_all_discharge_drugs_omitted_compared_to_valid_prescription():
    _, result = await _evaluate("LX0609-08-01-02", {
        "discharge_record": ({"document_id": "discharge", "discharge_order": "规律作息，定期复诊。"},),
        "inpat_prescription": ({"prescription_id": "rx", "order_type": "出院带药", "order_status": "完成"},),
        "inpat_prescription_item": ({"prescription_id": "rx", "prescription_item_id": "rx-1", "generic_name": "阿司匹林"},),
    })
    assert (result.final_state, result.reason_code) == ("non_compliant", "requirement_violated")


@pytest.mark.asyncio
async def test_two_antimicrobials_lab_check_does_not_require_unused_courses():
    rows = _056_rows(("注射用美罗培南", "2026-06-01 10:00:00"), ("利奈唑胺注射液", "2026-06-01 10:00:00"), culture_time="2026-06-01 09:00:00")
    _, baseline = await _evaluate("LX0609-05-01-04", rows)
    _, missing_courses = await _evaluate("LX0609-05-01-04", rows,
        unavailable_sources=frozenset({"daily_course_record", "senior_course_record"}))
    assert baseline.final_state == "compliant"
    assert missing_courses.final_state == baseline.final_state


@pytest.mark.asyncio
async def test_discharge_approval_empty_window_body_is_gap():
    class NeverCall:
        async def generate(self, *_args, **_kwargs):
            raise AssertionError("空正文不得送模")
    _, result = await _evaluate("LX0609-08-02-02", {
        "inpat_registration": ({"discharge_datetime": "2026-06-09 10:00:00"},),
        "discharge_record": ({"record_time": "2026-06-09 10:00:00"},),
        "daily_course_record": ({"document_id": "course", "record_time": "2026-06-09 09:00:00", "record_content": None},),
    }, llm_client=NeverCall())
    assert result.final_state == "data_gap"
