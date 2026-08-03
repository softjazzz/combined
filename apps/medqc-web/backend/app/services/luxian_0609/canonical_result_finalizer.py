"""LX0609 客户结果的唯一状态终结接口。"""

from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
from typing import Any

from ..luxian_0609_result_schema import CANONICAL_RESULT_STATUSES


_DEFAULT_INCOMPLETE_EXPLANATION = (
    "本次结果缺少规则专属、可核对的事实依据，暂不作为确定问题展示。",
    "未返回可展示的具体原因、核对标准或证据定位。",
    "请重新质控；如仍出现该提示，请补齐对应规则的受控事实和证据引用后再确认。",
)

_INCOMPLETE_EXPLANATION_BY_RULE = {
    "LX0609-040": (
        "暂无法确认是否需要进行四级手术术前多学科讨论",
        "当前缺少明确的手术级别或可核对的多学科讨论资料，不能将本项作为确定问题展示。",
        "请确认手术级别、术前讨论记录及参加科室信息后重新评估。",
    ),
}


def _has_locatable_evidence(result: Mapping[str, Any]) -> bool:
    evidence_items = result.get("evidence_items")
    return isinstance(evidence_items, list) and any(
        isinstance(item, Mapping)
        and bool(str(item.get("quote") or "").strip())
        and bool(
            str(
                item.get("source_table")
                or item.get("source_document_id")
                or item.get("evidence_ref")
                or ""
            ).strip()
        )
        for item in evidence_items
    )


def _is_compliant_for_status(status: str) -> bool | None:
    if status in {"compliant", "not_applicable"}:
        return True
    if status == "non_compliant":
        return False
    return None


def finalize_luxian_0609_canonical_result(
    result: Mapping[str, Any],
) -> dict[str, Any]:
    """生成最终客户结果；返回后状态字段不得再被下游改写。"""

    if not isinstance(result, Mapping):
        raise TypeError("result must be a mapping")
    rule_id = str(result.get("rule_id") or result.get("rule_code") or "").strip().upper()
    if not rule_id:
        raise ValueError("canonical result requires rule_id")
    status = str(result.get("status") or "").strip().lower()
    if status not in CANONICAL_RESULT_STATUSES:
        raise ValueError("canonical result has invalid status")

    finalized = deepcopy(dict(result))
    finalized["rule_id"] = rule_id
    finalized["status"] = status
    finalized["result_status"] = status
    finalized["is_compliant"] = _is_compliant_for_status(status)

    if status != "non_compliant":
        return finalized
    if (
        finalized.get("criterion_results")
        or finalized.get("customer_display_facts")
        or _has_locatable_evidence(finalized)
    ):
        return finalized

    findings, evidence, suggestion = _INCOMPLETE_EXPLANATION_BY_RULE.get(
        rule_id,
        _DEFAULT_INCOMPLETE_EXPLANATION,
    )
    finalized.update(
        {
            "status": "uncertain",
            "result_status": "uncertain",
            "is_compliant": None,
            "findings": findings,
            "evidence": evidence,
            "suggestion": suggestion,
            "reason_code": "customer_explanation_incomplete",
        }
    )
    return finalized
