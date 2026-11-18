"""068 语义意见的角色证据必须由来源或绑定引文确定。

用户口径（2026-10-22）：同意、附条件、拒绝以模型意见为准；程序只核对引文原文、
来源与上级称谓等身份结构，不再用关键词正则直接认定或推翻上级同意。
"""

from __future__ import annotations

import json

import pytest

from app.services.luxian_0609.decision_reducer import CustomerFinalState
from app.services.luxian_0609.extended_document.discharge_approval_extraction import (
    SCHEMA_VERSION,
)
from tests.unit.test_luxian_0609_native_extended_document_execution import (
    _canonical_extended_result,
    _evaluate,
    _evaluate_selected,
)


class _Client:
    def __init__(self, *items: dict[str, object]):
        self.items = items
        self.calls = []

    async def generate(self, prompt, **kwargs):
        self.calls.append((prompt, kwargs))
        return {
            "choices": [{
                "message": {"content": json.dumps({
                    "schema_version": SCHEMA_VERSION,
                    "items": self.items,
                })},
                "finish_reason": "stop",
            }],
            "usage": {
                "prompt_tokens": 80,
                "completion_tokens": 20,
                "total_tokens": 100,
            },
            "_api_time": 0.1,
        }


def _item(
    local_doc_id: str,
    *,
    opinion: str,
    quote: str,
) -> dict[str, object]:
    return {
        "local_doc_id": local_doc_id,
        "opinion": opinion,
        "quote": quote,
    }


def _base_rows() -> dict[str, tuple[dict[str, object], ...]]:
    return {
        "inpat_registration": ({
            "patient_status": "出院",
            "discharge_datetime": "2026-07-03 12:00:00",
        },),
        "discharge_record": ({"record_time": "2026-07-03 12:00:00"},),
    }


@pytest.mark.asyncio
async def test_daily_approval_without_senior_role_is_not_senior_approval() -> None:
    daily_text = "病情好转，予以办理出院。"
    senior_text = "主任医师指示：今日继续治疗，明日如无特殊情况可办理出院。"
    client = _Client(
        _item("doc_01", opinion="approved", quote=daily_text),
        _item("doc_02", opinion="conditional", quote=senior_text),
    )
    result, reduced = await _evaluate(
        "LX0609-08-02-02",
        {
            **_base_rows(),
            "daily_course_record": ({
                "document_id": "daily-without-role",
                "record_time": "2026-07-03 08:00:00",
                "record_content": daily_text,
            },),
            "senior_course_record": ({
                "document_id": "senior-conditional",
                "record_time": "2026-07-03 09:00:00",
                "record_content": senior_text,
            },),
        },
        llm_client=client,
    )

    assert reduced.final_state is CustomerFinalState.NON_COMPLIANT
    assert reduced.reason_code == "requirement_violated"
    assert dict(result.customer_display_facts)["LX0609-08-02-02"]["approval_present"] is False
    assert result.llm_call_count == len(client.calls) == 1


@pytest.mark.asyncio
async def test_daily_approval_with_senior_role_inside_opinion_quote_is_compliant() -> None:
    text = "主任医师指示：患者病情稳定，批准办理出院。"
    client = _Client(_item("doc_01", opinion="approved", quote=text))
    result, reduced = await _evaluate(
        "LX0609-08-02-02",
        {
            **_base_rows(),
            "daily_course_record": ({
                "document_id": "daily-senior-approval",
                "record_time": "2026-07-03 08:00:00",
                "record_content": text,
            },),
        },
        llm_client=client,
    )

    assert reduced.final_state is CustomerFinalState.COMPLIANT
    assert reduced.reason_code == "requirement_satisfied"
    facts = dict(result.customer_display_facts)["LX0609-08-02-02"]
    assert facts["approval_path"] == "senior_approval"
    assert facts["checked_source"] == "daily_course_record"
    assert result.llm_call_count == len(client.calls) == 1


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("document_id", "text"),
    (
        ("c02", "可安排出院"),
        ("c08", "准予其出院"),
        ("c30", "于今日出院"),
        ("completed-condition", "病情好转后，予以出院"),
        # 查体阴性“不肿”不能被当作否定出院（1022 C15）。
        ("c15-negative-exam", "副主任医师查房后指出：患者好转，双下肢不肿，患者拟明日出院"),
        ("c08-mixed-plan-and-approval", "拟于今日出院，请示主任后准予其出院"),
    ),
)
async def test_model_approved_senior_opinion_is_compliant_with_exact_evidence(
    document_id: str,
    text: str,
) -> None:
    client = _Client(_item("doc_01", opinion="approved", quote=text))
    snapshot, materials, result, reduced = await _evaluate_selected(
        ("LX0609-08-02-02",),
        {
            **_base_rows(),
            "senior_course_record": ({
                "document_id": document_id,
                "record_time": "2026-07-03 08:00:00",
                "record_content": text,
            },),
        },
        llm_client=client,
    )

    assert reduced[0].final_state is CustomerFinalState.COMPLIANT
    assert reduced[0].reason_code == "requirement_satisfied"
    assert result.llm_call_count == len(client.calls) == 1
    canonical = _canonical_extended_result(
        rule_id="LX0609-08-02-02",
        snapshot=snapshot,
        materials=materials,
        result=result,
        reduced=reduced,
    )
    assert [item["source_document_id"] for item in canonical["customer_evidence"]] == [
        document_id
    ]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("text", "opinion"),
    (
        ("拟办理出院", "unknown"),
        ("不建议出院", "denied"),
        ("不准许出院", "denied"),
        ("复查后可出院", "conditional"),
        ("若稳定再建议出院", "conditional"),
    ),
)
async def test_model_non_approval_opinion_is_not_senior_approval(text: str, opinion: str) -> None:
    client = _Client(_item("doc_01", opinion=opinion, quote="" if opinion == "unknown" else text))
    snapshot, materials, result, reduced = await _evaluate_selected(
        ("LX0609-08-02-02",),
        {
            **_base_rows(),
            "senior_course_record": ({
                "document_id": "not-approved",
                "record_time": "2026-07-03 08:00:00",
                "record_content": text,
            },),
        },
        llm_client=client,
    )

    assert reduced[0].final_state is CustomerFinalState.NON_COMPLIANT
    assert reduced[0].reason_code == "requirement_violated"
    assert result.llm_call_count == len(client.calls) == 1


@pytest.mark.asyncio
async def test_unattributed_dated_discharge_plan_in_daily_course_is_not_senior_approval() -> None:
    # 1016 第六轮 C27：住院医师日常病程只写“拟明日出院”，未提及上级医师；
    # 模型称 approved，但写明日期的出院安排只有确认为上级医师所写才视为同意。
    text = "查房后处置：患者术后恢复良好，拟明日出院，今日予以换药。"
    # approved 引文须为整句（2026-11-18 合同变更）；本测验证无上级称谓不得成为上级同意，替身改给整句。
    client = _Client(_item("doc_01", opinion="approved", quote=text))
    _snapshot, _materials, _result, reduced = await _evaluate_selected(
        ("LX0609-08-02-02",),
        {
            **_base_rows(),
            "daily_course_record": ({
                "document_id": "resident-plan",
                "record_time": "2026-07-03 08:00:00",
                "record_content": text,
            },),
        },
        llm_client=client,
    )

    assert reduced[0].final_state is CustomerFinalState.NON_COMPLIANT
    assert reduced[0].reason_code == "requirement_violated"
