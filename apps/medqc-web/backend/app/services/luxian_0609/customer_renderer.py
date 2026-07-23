"""LX0609 native 决策的客户结果白名单渲染器。"""

from __future__ import annotations

import re
from typing import Any, Callable, Mapping

from ..luxian_0609_rule_catalog import (
    LUXIAN_0609_RULE_SET_KEY,
    get_luxian_0609_rule,
)
from .decision_reducer import CustomerFinalState, ReducedRuleDecision
from .rule_contracts import load_luxian_0609_rule_contracts


CUSTOMER_SCHEMA_VERSION = "lx0609-customer-result-v2"
RULE_SET_VERSION = "2026-06-09"
CUSTOMER_RESULT_KEYS = frozenset(
    {
        "rule_id",
        "rule_code",
        "rule_name",
        "qc_point_id",
        "rule_set_key",
        "rule_set_version",
        "rule_version",
        "schema_version",
        "status",
        "result_status",
        "is_compliant",
        "findings",
        "evidence",
        "suggestion",
        "confidence",
        "reason_code",
        "evidence_items",
    }
)

_SAFE_CODE = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9._-]{0,63}$")
_STATUS_MAP = {
    CustomerFinalState.COMPLIANT: "compliant",
    CustomerFinalState.NON_COMPLIANT: "non_compliant",
    CustomerFinalState.NOT_APPLICABLE: "not_applicable",
    CustomerFinalState.DATA_GAP: "data_gap",
    CustomerFinalState.TECHNICAL_ERROR: "technical_error",
    CustomerFinalState.EVALUATION_UNKNOWN: "uncertain",
}
_CUSTOMER_MESSAGES = {
    CustomerFinalState.COMPLIANT: (
        "符合质控要求",
        "已根据受控证据完成判断。",
        "继续保持。",
    ),
    CustomerFinalState.NON_COMPLIANT: (
        "发现质控问题",
        "受控证据表明本次记录未满足质控要求。",
        "请按质控要求核对并完善相关记录。",
    ),
    CustomerFinalState.NOT_APPLICABLE: (
        "本次就诊不适用该质控点",
        "完整适用性证据未触发本质控点。",
        "无需处理。",
    ),
    CustomerFinalState.DATA_GAP: (
        "现有数据不足",
        "当前受控数据不足以形成确定结论。",
        "请补充或同步所需数据后重新评估。",
    ),
    CustomerFinalState.TECHNICAL_ERROR: (
        "质控执行未完成",
        "本次执行未形成临床结论。",
        "请在技术问题处理后重新评估。",
    ),
    CustomerFinalState.EVALUATION_UNKNOWN: (
        "暂无法形成确定结论",
        "现有受控证据存在冲突或语义不确定性。",
        "建议补充证据后复核。",
    ),
}

SafeTraceSink = Callable[[Mapping[str, Any]], None]


def _safe_code(value: Any) -> str:
    if not isinstance(value, str):
        return ""
    text = value.strip()
    return text if _SAFE_CODE.fullmatch(text) else ""


def _trusted_catalog_identity(rule_id: str) -> tuple[str, str, str]:
    rule = get_luxian_0609_rule(rule_id)
    if not isinstance(rule, dict):
        raise ValueError("decision rule is missing from trusted catalog")
    catalog_id = str(rule.get("rule_id") or rule.get("rule_code") or "").strip().upper()
    if catalog_id != rule_id:
        raise ValueError("trusted catalog rule mismatch")
    name = str(rule.get("name") or rule.get("rule_name") or "").strip()
    if not name or len(name) > 120:
        raise ValueError("trusted catalog rule name is invalid")
    version = _safe_code(rule.get("rule_version") or rule.get("version")) or "v1"
    contract = next(
        (item for item in load_luxian_0609_rule_contracts() if item.rule_id == rule_id),
        None,
    )
    if contract is None or not _safe_code(contract.executor_key):
        raise ValueError("trusted rule contract is missing executor identity")
    return name, version, contract.executor_key


def _emit_safe_trace(
    sink: SafeTraceSink | None,
    *,
    decision: ReducedRuleDecision,
    executor_key: str,
) -> None:
    if sink is None:
        return
    payload = {
        "event": "customer_result_rendered",
        "rule_id": decision.rule_id,
        "snapshot_hash": decision.snapshot_hash,
        "decision_fingerprint": decision.decision_fingerprint,
        "reason_code": decision.reason_code,
        "fact_refs": decision.fact_refs,
        "evaluator_version": decision.evaluator_version,
        "executor_key": _safe_code(executor_key),
        "final_state": decision.final_state.value,
    }
    try:
        sink(payload)
    except Exception:
        return


def render_luxian_0609_customer_result(
    *,
    decision: ReducedRuleDecision,
    trace_sink: SafeTraceSink | None = None,
) -> dict[str, Any]:
    """从可信目录和 reducer 决策零构造 DTO，不接受任意展示字符串。"""

    if not isinstance(decision, ReducedRuleDecision):
        raise TypeError("decision must be ReducedRuleDecision")
    rule_name, rule_version, executor_key = _trusted_catalog_identity(decision.rule_id)
    status = _STATUS_MAP[decision.final_state]
    findings, evidence, suggestion = _CUSTOMER_MESSAGES[decision.final_state]
    if decision.final_state in {
        CustomerFinalState.COMPLIANT,
        CustomerFinalState.NOT_APPLICABLE,
    }:
        is_compliant: bool | None = True
    elif decision.final_state is CustomerFinalState.NON_COMPLIANT:
        is_compliant = False
    else:
        is_compliant = None

    result = {
        "rule_id": decision.rule_id,
        "rule_code": decision.rule_id,
        "rule_name": rule_name,
        "qc_point_id": decision.rule_id,
        "rule_set_key": LUXIAN_0609_RULE_SET_KEY,
        "rule_set_version": RULE_SET_VERSION,
        "rule_version": rule_version,
        "schema_version": CUSTOMER_SCHEMA_VERSION,
        "status": status,
        "result_status": status,
        "is_compliant": is_compliant,
        "findings": findings,
        "evidence": evidence,
        "suggestion": suggestion,
        "confidence": decision.confidence,
        # 仅返回 reducer 已验证的受控枚举码；不返回快照、文书、坐标或模型原文。
        "reason_code": _safe_code(decision.reason_code),
        "evidence_items": [],
    }
    _emit_safe_trace(
        trace_sink,
        decision=decision,
        executor_key=executor_key,
    )
    return result
