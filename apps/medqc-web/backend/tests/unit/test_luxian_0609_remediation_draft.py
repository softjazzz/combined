from __future__ import annotations

from typing import Any, Mapping

import pytest

from app.services.luxian_0609.remediation_draft import (
    REMEDIATION_DRAFT_RULE_IDS,
    build_remediation_draft_prompt,
    generate_remediation_draft,
    sanitize_remediation_draft,
)


def _item(**overrides: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "rule_id": "LX0609-020",
        "rule_name": "会诊意见执行记录",
        "qc_point": "请会诊执行记录不规范，未进行归纳总结，未明确具体会诊意见执行情况",
        "status": "non_compliant",
        "reason_code": "no_execution_trace",
        "conclusion": "第2次会诊意见未见对应执行记录",
        # 以下两个字段不进入提示词，防止把内部推断当成病历事实改写。
        "detail": "内部细节不应进入提示词",
        "model_analysis": "模型分析不应进入提示词",
        "suggestion": "修改对象：会诊意见执行记录\n需要补充：具体措施与结果",
        "customer_display_facts": {
            "recommendation_count": 3,
            "missing_execution_count": 1,
            "recommendation_evidence": [
                {
                    "recommendation_index": 2,
                    "opinion_evidence": [
                        {"source_ref": "src_" + "a" * 24, "source_type": "consultation"}
                    ],
                    "execution_evidence": [],
                }
            ],
        },
        "evidence": [
            {
                "source_ref": "src_" + "b" * 24,
                "source_label": "会诊记录单",
                "record_time": "2026-08-13 10:00:00",
                "recommendation_index": 2,
                "evidence_role": "opinion",
                "evidence_excerpt": "建议完善相关检查",
            }
        ],
    }
    base.update(overrides)
    return base


async def _returns(content: str) -> Mapping[str, Any]:
    return {"choices": [{"message": {"content": content}}]}


def test_supported_rule_ids_are_the_consultation_triad() -> None:
    assert REMEDIATION_DRAFT_RULE_IDS == {"LX0609-020", "LX0609-022", "LX0609-023"}


def test_prompt_uses_only_customer_visible_fields() -> None:
    prompt = build_remediation_draft_prompt(item=_item())

    assert "LX0609-020" in prompt
    assert "第2次会诊意见未见对应执行记录" in prompt
    assert "会诊记录单" in prompt
    assert "第2条建议：有会诊意见证据" in prompt

    # 内部推断字段不得进入提示词。
    assert "内部细节不应进入提示词" not in prompt
    assert "模型分析不应进入提示词" not in prompt


def test_prompt_omits_absent_facts_without_inventing() -> None:
    prompt = build_remediation_draft_prompt(
        item=_item(customer_display_facts=None, evidence=[], conclusion="", suggestion="")
    )

    assert "（未提供额外字段级事实）" in prompt
    assert "（无可定位证据）" in prompt
    assert "（未提供）" in prompt


@pytest.mark.asyncio
async def test_unsupported_rule_is_not_generated() -> None:
    called = False

    async def _generate(prompt: str) -> Mapping[str, Any]:
        nonlocal called
        called = True
        return await _returns("草稿")

    result = await generate_remediation_draft(
        item=_item(rule_id="LX0609-018"),
        generate=_generate,
    )

    assert result == {
        "available": False,
        "rule_id": "LX0609-018",
        "reason": "rule_not_supported",
    }
    assert called is False


@pytest.mark.asyncio
async def test_non_compliant_status_is_required() -> None:
    result = await generate_remediation_draft(
        item=_item(status="data_gap"),
        generate=lambda prompt: _returns("草稿"),
    )

    assert result == {
        "available": False,
        "rule_id": "LX0609-020",
        "reason": "status_not_supported",
    }


@pytest.mark.asyncio
async def test_generation_failure_degrades_without_raising() -> None:
    async def _boom(prompt: str) -> Mapping[str, Any]:
        raise RuntimeError("provider unavailable")

    result = await generate_remediation_draft(item=_item(), generate=_boom)

    assert result == {
        "available": False,
        "rule_id": "LX0609-020",
        "reason": "generation_failed",
    }


@pytest.mark.asyncio
async def test_empty_draft_is_reported_as_unavailable() -> None:
    result = await generate_remediation_draft(
        item=_item(),
        generate=lambda prompt: _returns("   ```   "),
    )

    assert result == {
        "available": False,
        "rule_id": "LX0609-020",
        "reason": "empty_draft",
    }


def test_sanitize_strips_thinking_block_and_fences() -> None:
    raw = "<think>内部推理</think>\n```markdown\n草稿：拟补充第2次会诊意见的执行情况。\n```"

    assert sanitize_remediation_draft(raw) == "拟补充第2次会诊意见的执行情况。"


@pytest.mark.asyncio
async def test_draft_is_capped() -> None:
    result = await generate_remediation_draft(
        item=_item(),
        generate=lambda prompt: _returns("拟" * 500),
    )

    assert result["available"] is True
    assert result["draft"].endswith("…")
    assert len(result["draft"]) == 301
