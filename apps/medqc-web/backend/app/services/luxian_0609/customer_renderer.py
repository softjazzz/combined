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
        "criterion_results",
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
_DATA_GAP_MESSAGES = {
    "source_unavailable": (
        "本次未读取到判断所需资料",
        "当前可查看的病历资料不足以完成本项判断。",
        "请确认相关资料已同步完整后重新评估。",
    ),
    "source_truncated": (
        "本次读取的相关资料不完整",
        "当前结果仅依据部分病历资料，暂时不能形成确定结论。",
        "请确认全部相关资料已同步后重新评估。",
    ),
    "source_readiness_unproven": (
        "相关资料是否完整尚待确认",
        "目前无法确认本项判断所需资料是否已经全部读取。",
        "请确认相关资料完整后重新评估。",
    ),
    "required_field_missing": (
        "相关记录缺少判断所需信息",
        "当前读取到的记录中缺少完成本项判断的关键信息。",
        "请核对相关记录内容是否完整后重新评估。",
    ),
    "authoritative_time_missing": (
        "相关记录缺少明确时间",
        "目前缺少本项判断所需的起始、完成或评估时间。",
        "请核对相关记录时间后重新评估。",
    ),
    "linkage_unresolved": (
        "暂未找到可相互核对的对应记录",
        "现有资料中尚未找到能够明确对应的前后记录。",
        "请核对相关记录及时间是否完整后重新评估。",
    ),
    "applicability_source_gap": (
        "暂无法确认本质控点是否适用",
        "现有资料不足以确认本次诊疗是否属于本质控点的检查范围。",
        "请核对相关诊疗记录后重新评估。",
    ),
}
_RULE_DATA_GAP_MESSAGES = {
    "LX0609-009": (
        "暂时无法核对病情变化时的病程记录",
        "病危期间每日病程记录已完成，但相关检查检验结果明细不完整，无法继续核对病情变化时是否及时记录病程。",
        "请确认检查检验结果明细已完整同步后重新评估。",
    ),
    "LX0609-041": (
        "本次未读取到输血知情同意书",
        "已读取到输血相关记录，但没有可核对的输血知情同意书。",
        "请确认输血知情同意书已归档并同步后重新评估。",
    ),
    "LX0609-042": (
        "输血知情同意书的签名信息不完整",
        "当前资料不足以核对患者、家属或医师签名及签署时间是否完整。",
        "请补充完整的签名和签署时间后重新评估。",
    ),
    "LX0609-043": (
        "输血前检查资料不完整",
        "当前未读取到可完整核对的输血前常规检查项目、结果和检查时间。",
        "请补充输血前检查结果及检查时间后重新评估。",
    ),
    "LX0609-049": (
        "暂时无法核对输血医嘱与收费",
        "已读取到输血记录，但缺少可相互核对的输血医嘱或收费明细。",
        "请确认输血医嘱和收费明细已同步后重新评估。",
    ),
}
_RULE_NON_COMPLIANT_MESSAGES = {
    "LX0609-016": (
        "入院记录与首次病程记录存在高度重复",
        "入院记录现病史与首次病程记录病例特点的相似度超过 70% 判定标准。",
        "请结合首次病程记录要求，补充病例特点的归纳、分析和诊疗思路。",
    ),
    "LX0609-023": (
        "会诊意见执行情况记录过于笼统",
        "当前仅记录已按会诊意见执行，未说明具体执行措施、执行结果或后续安排。",
        "请归纳记录会诊意见的具体执行措施、执行结果及后续安排。",
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
    if decision.final_state is CustomerFinalState.DATA_GAP:
        findings, evidence, suggestion = _RULE_DATA_GAP_MESSAGES.get(
            decision.rule_id,
            _DATA_GAP_MESSAGES.get(
                decision.reason_code,
                (findings, evidence, suggestion),
            ),
        )
    elif decision.final_state is CustomerFinalState.NON_COMPLIANT:
        findings, evidence, suggestion = _RULE_NON_COMPLIANT_MESSAGES.get(
            decision.rule_id,
            (findings, evidence, suggestion),
        )
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
        "criterion_results": [],
    }
    if decision.criterion_results:
        contract = next(
            item
            for item in load_luxian_0609_rule_contracts()
            if item.rule_id == decision.rule_id
        )
        criteria_by_id = {
            item.criterion_id: item for item in contract.criteria
        }
        criterion_rows: list[dict[str, Any]] = []
        for criterion_result in decision.criterion_results:
            criterion = criteria_by_id.get(criterion_result.criterion_id)
            if criterion is None:
                raise ValueError("decision criterion is missing from rule contract")
            criterion_rows.append(
                {
                    **criterion_result.to_safe_dict(),
                    "kind": criterion.kind,
                    "source_fact": criterion.source_fact,
                    "left_fact": criterion.left_fact,
                    "right_fact": criterion.right_fact,
                }
            )
        result["criterion_results"] = criterion_rows
    _emit_safe_trace(
        trace_sink,
        decision=decision,
        executor_key=executor_key,
    )
    return result
