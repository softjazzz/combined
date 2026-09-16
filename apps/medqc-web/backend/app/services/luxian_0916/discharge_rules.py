"""Luxian0916 出院前规则（LX0916-031..032）。

只读取 ``discharge_facts`` 与 ``document_facts`` 中的权威结构化事实；不解析
病历全文。普通在院阶段必须返回未到检查时点，不能提前形成质控问题。
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from .contracts import Luxian0916RuleResult


_RULE_IDS = ("LX0916-031", "LX0916-032")
_RULE_SPECS = {
    "LX0916-031": ("discharge_record", "出院记录诊疗经过"),
    "LX0916-032": ("discharge_orders", "出院医嘱"),
}


def _safe_mapping(value: object) -> Mapping[str, Any] | None:
    return value if isinstance(value, Mapping) else None


def _safe_evidence(value: object) -> tuple[str, ...]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        return ()
    return tuple(item.strip() for item in value if isinstance(item, str) and item.strip())


def _safe_anchors(value: object) -> tuple[Mapping[str, Any], ...]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        return ()
    return tuple(item for item in value if isinstance(item, Mapping))


def _result(
    *,
    rule_id: str,
    status: str,
    reason_code: str,
    findings: str,
    evidence: tuple[str, ...] = (),
    suggestion: str = "",
    anchors: tuple[Mapping[str, Any], ...] = (),
    diagnostics: Mapping[str, Any],
    decision_facts: Mapping[str, Any],
) -> Luxian0916RuleResult:
    return Luxian0916RuleResult(
        rule_id=rule_id,
        status=status,
        reason_code=reason_code,
        findings=findings,
        evidence=evidence,
        suggestion=suggestion,
        document_anchors=anchors,
        diagnostics=diagnostics,
        decision_facts=decision_facts,
    )


def _is_discharge_window_ready(discharge_facts: Mapping[str, Any]) -> bool | None:
    arranged = discharge_facts.get("discharge_arranged")
    record_formed = discharge_facts.get("discharge_record_formed")
    if arranged is True or record_formed is True:
        return True
    if arranged is False and record_formed is False:
        return False
    return None


def _optional_bool(value: object) -> bool | None:
    return value if isinstance(value, bool) else None


def _decision_facts(
    *,
    document_key: str,
    discharge_facts: Mapping[str, Any] | None,
    discharge_window_ready: bool | None = None,
    fact: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """持久化本规则实际消费的出院阶段与文书事实，不保存病历原文。"""

    result: dict[str, Any] = {
        "discharge_gate": "discharge_arranged_or_record_formed",
        "discharge_arranged": (
            _optional_bool(discharge_facts.get("discharge_arranged"))
            if discharge_facts is not None
            else None
        ),
        "discharge_record_formed": (
            _optional_bool(discharge_facts.get("discharge_record_formed"))
            if discharge_facts is not None
            else None
        ),
        "discharge_window_ready": discharge_window_ready,
        "document_fact_key": document_key,
    }
    if fact is not None:
        result.update(
            {
                "document_presence": fact.get("presence"),
                "document_completeness": fact.get("completeness"),
                "document_id": fact.get("document_id"),
                "source_type": fact.get("source_type"),
            }
        )
    return result


def _evaluate_rule(
    *,
    rule_id: str,
    discharge_facts: Mapping[str, Any] | None,
    document_facts: Mapping[str, Any] | None,
) -> Luxian0916RuleResult:
    document_key, subject = _RULE_SPECS[rule_id]
    diagnostics: dict[str, Any] = {"document_fact": document_key}
    if discharge_facts is None:
        return _result(
            rule_id=rule_id,
            status="data_quality_gap",
            reason_code="discharge_context_unavailable",
            findings="缺少出院安排和出院记录形成状态，无法确定检查时点。",
            diagnostics=diagnostics,
            decision_facts=_decision_facts(
                document_key=document_key, discharge_facts=None
            ),
        )
    ready = _is_discharge_window_ready(discharge_facts)
    diagnostics["discharge_window_ready"] = ready
    if ready is False:
        return _result(
            rule_id=rule_id,
            status="not_executed",
            reason_code="evaluation_window_not_mature",
            findings="患者仍处于普通住院阶段，尚未进入出院前检查时点。",
            diagnostics=diagnostics,
            decision_facts=_decision_facts(
                document_key=document_key,
                discharge_facts=discharge_facts,
                discharge_window_ready=ready,
            ),
        )
    if ready is None:
        return _result(
            rule_id=rule_id,
            status="data_quality_gap",
            reason_code="discharge_context_unavailable",
            findings="出院安排或出院记录形成状态不完整，无法确定检查时点。",
            diagnostics=diagnostics,
            decision_facts=_decision_facts(
                document_key=document_key,
                discharge_facts=discharge_facts,
                discharge_window_ready=ready,
            ),
        )

    fact = _safe_mapping(document_facts.get(document_key)) if document_facts else None
    if fact is None:
        return _result(
            rule_id=rule_id,
            status="data_quality_gap",
            reason_code="semantic_fact_unavailable",
            findings=f"已进入出院前检查时点，但缺少{subject}的权威事实。",
            diagnostics=diagnostics,
            decision_facts=_decision_facts(
                document_key=document_key,
                discharge_facts=discharge_facts,
                discharge_window_ready=ready,
            ),
        )
    presence = fact.get("presence")
    completeness = fact.get("completeness")
    evidence = _safe_evidence(fact.get("evidence"))
    anchors = _safe_anchors(fact.get("anchors"))
    diagnostics["document_presence"] = presence
    diagnostics["document_completeness"] = completeness
    decision_facts = _decision_facts(
        document_key=document_key,
        discharge_facts=discharge_facts,
        discharge_window_ready=ready,
        fact=fact,
    )
    if presence == "missing":
        return _result(
            rule_id=rule_id,
            status="non_compliant",
            reason_code="required_document_missing",
            findings=f"已进入出院前检查时点，但未找到{subject}。",
            evidence=evidence,
            suggestion=f"补充{subject}并完成出院前核对。",
            anchors=anchors,
            diagnostics=diagnostics,
            decision_facts=decision_facts,
        )
    if presence != "present" or completeness not in {"complete", "incomplete"}:
        return _result(
            rule_id=rule_id,
            status="data_quality_gap",
            reason_code="semantic_fact_unavailable",
            findings=f"无法确认{subject}完整性，不能以文本关键词替代语义事实。",
            evidence=evidence,
            anchors=anchors,
            diagnostics=diagnostics,
            decision_facts=decision_facts,
        )
    if completeness == "complete":
        return _result(
            rule_id=rule_id,
            status="compliant",
            reason_code="required_document_complete",
            findings=f"{subject}完整性事实满足规则要求。",
            evidence=evidence,
            anchors=anchors,
            diagnostics=diagnostics,
            decision_facts=decision_facts,
        )
    return _result(
        rule_id=rule_id,
        status="non_compliant",
        reason_code="required_document_incomplete",
        findings=f"{subject}存在缺项或内容不完整。",
        evidence=evidence,
        suggestion=f"补全{subject}的必填内容。",
        anchors=anchors,
        diagnostics=diagnostics,
        decision_facts=decision_facts,
    )


def execute_discharge_rules(
    context: Mapping[str, Any], rule_ids: Sequence[str] | None = None
) -> list[Luxian0916RuleResult]:
    """执行 LX0916-031..032，并在规则层直接形成最终客户结果。"""

    requested = tuple(rule_ids) if rule_ids is not None else _RULE_IDS
    unknown = set(requested).difference(_RULE_SPECS)
    if unknown:
        raise ValueError(f"unsupported Luxian0916 discharge rule ids: {sorted(unknown)}")
    discharge_facts = _safe_mapping(context.get("discharge_facts"))
    document_facts = _safe_mapping(context.get("document_facts"))
    return [
        _evaluate_rule(
            rule_id=rule_id,
            discharge_facts=discharge_facts,
            document_facts=document_facts,
        )
        for rule_id in requested
    ]
