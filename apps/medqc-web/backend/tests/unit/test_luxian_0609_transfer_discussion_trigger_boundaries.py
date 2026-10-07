"""转科计划与已解决历史诊断的不误触发回归。"""
import pytest

from test_luxian_0609_native_extended_document_execution import _evaluate


@pytest.mark.asyncio
@pytest.mark.parametrize("rule_id", ["LX0609-10-02-01", "LX0609-10-02-02"])
@pytest.mark.parametrize("name, expected", [
    ("计划明日转科，今日暂不转科", "not_applicable"),
    ("病情稳定后再转科", "not_applicable"),
    ("暂不转科", "not_applicable"),
    ("拟转科", "not_applicable"),
    ("转科", "non_compliant"),
    ("转入ICU", "non_compliant"),
    ("原计划明日转科，现已转科", "non_compliant"),
])
async def test_transfer_requires_current_order(rule_id, name, expected):
    result, decision = await _evaluate(rule_id, {
        "inpat_nondrug_order": [{"order_id": "t1", "order_name": name,
            "order_status": "新开", "prescribed_datetime": "2026-07-01 09:00:00"}],
        "evaluation_context.horizon": [{"horizon_datetime": "2026-07-03 09:00:00",
            "horizon_date": "2026-07-03", "basis": "evaluation_as_of"}],
    })
    assert decision.final_state.value == expected
    assert result.llm_call_count == 0


@pytest.mark.asyncio
@pytest.mark.parametrize("content, expected", [
    ("入院时诊断不明确，现已明确诊断为细菌性肺炎，诊疗方案已确定。", "not_applicable"),
    ("既往诊断不明确，目前诊断已明确。", "not_applicable"),
    ("目前诊断仍不明确，诊疗方案难以确定。", "non_compliant"),
    ("入院时诊断不明确，目前诊断仍不明确。", "non_compliant"),
    ("入院时诊断不明确，现已明确诊断为肺炎。但新的发热诊断仍不明确。", "non_compliant"),
    ("入院时诊断不明确，现已明确诊断为肺炎。", "not_applicable"),
    ("诊断不明确。", "non_compliant"),
    ("入院时诊断不明确，至今发热原因未查明，治疗方案仍难以确定。", "non_compliant"),
    ("入院时诊断不明确，至今发热原因未查明，治疗方案仍难以确定。另一疾病目前已明确诊断为高血压。", "non_compliant"),
    ("入院时诊断不明确，另一疾病目前已明确诊断为高血压。", "non_compliant"),
    ("入院时诊断不明确，目前已明确诊断为另一疾病高血压。", "non_compliant"),
    ("入院时诊断不明确，现已明确诊断为肺炎。但至今发热原因未查明，治疗方案仍难以确定。", "non_compliant"),
])
async def test_difficult_discussion_requires_current_uncertainty(content, expected):
    result, decision = await _evaluate("LX0609-03-02-01", {
        "inpat_registration": [{"admission_datetime": "2026-07-01 09:00:00"}],
        "daily_course_record": [{"document_id": "c1", "record_time": "2026-07-09 09:00:00",
            "record_content": content}],
    })
    assert decision.final_state.value == expected
    assert result.llm_call_count == 0
