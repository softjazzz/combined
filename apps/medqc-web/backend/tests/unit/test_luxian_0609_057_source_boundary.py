"""冻结 057 的来源边界；此测试记录现状，不替代临床口径验收。"""

import pytest

from test_luxian_0609_native_extended_document_execution import _evaluate
from app.services.luxian_0609.decision_reducer import CustomerFinalState


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("source", "expected"),
    [
        ("daily_course_record", CustomerFinalState.NON_COMPLIANT),
        ("consultation_record", CustomerFinalState.NOT_APPLICABLE),
    ],
)
async def test_057_current_same_explicit_statement_has_source_sensitive_result(
    source, expected
):
    execution, decision = await _evaluate(
        "LX0609-05-01-05",
        {
            "inpat_drug_order": ({"order_id": "drug-1", "generic_name": "万古霉素"},),
            source: ({
                "document_id": "note-1",
                "record_time": "2026-04-02 16:56:00",
                "record_content": "建议万古霉素经验性抗感染治疗，已遵会诊意见给予万古霉素。",
            },),
        },
    )
    assert decision.final_state is expected
    assert execution.llm_call_count == 0
    assert execution.total_tokens == 0
