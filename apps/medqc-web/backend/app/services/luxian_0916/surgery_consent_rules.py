"""Luxian0916 手术、麻醉与知情同意规则（LX0916-021..030）。

本模块只消费上游已经校验来源的 ``context``：

* ``event_facts``：明确的布尔事件事实；
* ``document_facts``：文书索引和语义核验后的事实，使用 ``presence``
  （``present``/``missing``）和 ``completeness``（``complete``/``incomplete``）；
* 每个文书事实可选 ``evidence`` 与 ``anchors``，由本模块原样转为客户结果。

不从病历全文以关键词推断事件或文书质量。没有权威事实时，保守返回
``data_quality_gap``，避免把数据覆盖缺口误报成质控问题。

若上游显式给出 ``event_facts.evaluation_window_mature=false``，规则尚未到
检查时点，直接返回 ``not_executed/evaluation_window_not_mature``。
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from .contracts import Luxian0916RuleResult


_RULE_IDS = tuple(f"LX0916-{number:03d}" for number in range(21, 31))

_RULE_SPECS: dict[str, dict[str, str]] = {
    "LX0916-021": {
        "name": "手术同意书缺项或描述不清",
        "event": "surgery_arranged_or_performed",
        "document": "surgery_consent",
        "requirements": "术前诊断、手术名称、术中及术后可能并发症、手术风险、患者意见及签名、经治医师和术者签名",
    },
    "LX0916-022": {
        "name": "麻醉同意书缺项或描述不清",
        "event": "anesthesia_arranged_or_performed",
        "document": "anesthesia_consent",
        "requirements": "患者基本信息、术前诊断、拟施手术及麻醉方式、基础疾病影响、有创操作监测、麻醉风险/并发症/意外、患者及麻醉医师签名和日期",
    },
    "LX0916-023": {
        "name": "无麻醉记录",
        "event": "anesthesia_performed",
        "document": "anesthesia_record",
    },
    "LX0916-024": {
        "name": "麻醉记录缺项或描述不清",
        "event": "anesthesia_record_formed",
        "document": "anesthesia_record",
        "requirements": "一般情况、术前用药、术前及术中诊断、麻醉方式、期间用药和处置、手术起止时间、麻醉医师签名",
    },
    "LX0916-025": {
        "name": "手术记录缺项或描述不清",
        "event": "surgery_performed",
        "document": "surgery_record",
    },
    "LX0916-026": {
        "name": "手术安全核查记录缺项或描述不清",
        "event": "surgery_performed",
        "document": "surgery_safety_check",
    },
    "LX0916-027": {
        "name": "急诊手术缺主治及以上医师指示记录",
        "event": "emergency_surgery",
        "document": "emergency_surgery_instruction",
    },
    "LX0916-028": {
        "name": "非计划再次手术相关记录未说明上次手术情况或原因",
        "event": "unplanned_reoperation",
        "document": "unplanned_reoperation_explanation",
    },
    "LX0916-029": {
        "name": "特殊诊疗、特殊用药、试验、高耗材或自费项目同意书不清",
        "event": "special_treatment",
        "document": "special_treatment_consent",
    },
    "LX0916-030": {
        "name": "病危（重）通知书缺项或描述不清",
        "event": "critical_or_serious_condition",
        "document": "critical_condition_notice",
    },
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
    )


def _event_value(event_facts: Mapping[str, Any], event_key: str) -> bool | None:
    if event_key == "surgery_arranged_or_performed":
        arranged = event_facts.get("surgery_arranged")
        performed = event_facts.get("surgery_performed")
        if arranged is True or performed is True:
            return True
        if arranged is False and performed is False:
            return False
        return None
    if event_key == "anesthesia_arranged_or_performed":
        arranged = event_facts.get("anesthesia_arranged")
        performed = event_facts.get("anesthesia_performed")
        if arranged is True or performed is True:
            return True
        if arranged is False and performed is False:
            return False
        return None
    value = event_facts.get(event_key)
    return value if isinstance(value, bool) else None


def _evaluate_rule(
    *,
    rule_id: str,
    event_facts: Mapping[str, Any] | None,
    document_facts: Mapping[str, Any] | None,
) -> Luxian0916RuleResult:
    spec = _RULE_SPECS[rule_id]
    diagnostics: dict[str, Any] = {"event_gate": spec["event"], "document_fact": spec["document"]}
    if event_facts is None:
        return _result(
            rule_id=rule_id,
            status="data_quality_gap",
            reason_code="event_fact_unavailable",
            findings="缺少手术相关事件事实，无法确认本规则是否适用。",
            diagnostics=diagnostics,
        )
    if event_facts.get("evaluation_window_mature") is False:
        return _result(
            rule_id=rule_id,
            status="not_executed",
            reason_code="evaluation_window_not_mature",
            findings="手术相关文书尚未到检查时点。",
            diagnostics=diagnostics,
        )

    event_value = _event_value(event_facts, spec["event"])
    diagnostics["event_value"] = event_value
    if event_value is False:
        return _result(
            rule_id=rule_id,
            status="not_applicable",
            reason_code="trigger_event_not_present",
            findings="未发现该规则要求的触发事件。",
            diagnostics=diagnostics,
        )
    if event_value is None:
        return _result(
            rule_id=rule_id,
            status="data_quality_gap",
            reason_code="event_fact_unavailable",
            findings="触发事件事实不完整，无法确认本规则是否适用。",
            diagnostics=diagnostics,
        )

    fact = _safe_mapping(document_facts.get(spec["document"])) if document_facts else None
    if fact is None:
        return _result(
            rule_id=rule_id,
            status="data_quality_gap",
            reason_code="semantic_fact_unavailable",
            findings="缺少该文书的权威存在性或完整性事实，无法作出内容质量结论。",
            diagnostics=diagnostics,
        )

    presence = fact.get("presence")
    completeness = fact.get("completeness")
    evidence = _safe_evidence(fact.get("evidence"))
    anchors = _safe_anchors(fact.get("anchors"))
    diagnostics["document_presence"] = presence
    diagnostics["document_completeness"] = completeness

    if rule_id == "LX0916-023":
        if presence == "present":
            return _result(
                rule_id=rule_id,
                status="compliant",
                reason_code="anesthesia_record_present",
                findings="已实施麻醉，且存在麻醉记录。",
                evidence=evidence,
                anchors=anchors,
                diagnostics=diagnostics,
            )
        if presence == "missing":
            return _result(
                rule_id=rule_id,
                status="non_compliant",
                reason_code="anesthesia_record_missing",
                findings="已实施麻醉，但权威文书索引显示无麻醉记录。",
                evidence=evidence,
                suggestion="补充麻醉记录并关联本次麻醉事件。",
                anchors=anchors,
                diagnostics=diagnostics,
            )
        return _result(
            rule_id=rule_id,
            status="data_quality_gap",
            reason_code="document_presence_unavailable",
            findings="无法确认麻醉记录是否存在。",
            evidence=evidence,
            anchors=anchors,
            diagnostics=diagnostics,
        )

    if rule_id == "LX0916-024" and presence == "missing":
        return _result(
            rule_id=rule_id,
            status="data_quality_gap",
            reason_code="event_document_fact_conflict",
            findings="麻醉记录形成事件与文书存在性事实相互矛盾，无法评价内容完整性。",
            evidence=evidence,
            anchors=anchors,
            diagnostics=diagnostics,
        )

    if presence == "missing":
        return _result(
            rule_id=rule_id,
            status="non_compliant",
            reason_code="required_document_missing",
            findings=f"触发事件已确认，但未找到{spec['name']}对应的必需文书。",
            evidence=evidence,
            suggestion="补充必需文书并完成对应内容记录。",
            anchors=anchors,
            diagnostics=diagnostics,
        )
    if presence != "present" or completeness not in {"complete", "incomplete"}:
        return _result(
            rule_id=rule_id,
            status="data_quality_gap",
            reason_code="semantic_fact_unavailable",
            findings="无法确认目标文书的完整性，不能以文本关键词替代语义事实。",
            evidence=evidence,
            anchors=anchors,
            diagnostics=diagnostics,
        )
    if completeness == "complete":
        return _result(
            rule_id=rule_id,
            status="compliant",
            reason_code="required_document_complete",
            findings="触发事件及对应文书完整性事实均满足规则要求。",
            evidence=evidence,
            anchors=anchors,
            diagnostics=diagnostics,
        )
    requirements = spec.get("requirements", "该文书对应的必填内容")
    return _result(
        rule_id=rule_id,
        status="non_compliant",
        reason_code="required_document_incomplete",
        findings=(
            f"已确认触发事件，但{spec['name']}对应文书存在缺项或描述不清；"
            f"完整性核验范围包括：{requirements}。"
        ),
        evidence=evidence,
        suggestion=f"对照完整性核验范围补全必填项目：{requirements}。",
        anchors=anchors,
        diagnostics=diagnostics,
    )


def execute_surgery_consent_rules(
    context: Mapping[str, Any], rule_ids: Sequence[str] | None = None
) -> list[Luxian0916RuleResult]:
    """执行 LX0916-021..030，并在规则层直接形成最终客户结果。"""

    requested = tuple(rule_ids) if rule_ids is not None else _RULE_IDS
    unknown = set(requested).difference(_RULE_SPECS)
    if unknown:
        raise ValueError(f"unsupported Luxian0916 surgery rule ids: {sorted(unknown)}")
    event_facts = _safe_mapping(context.get("event_facts"))
    document_facts = _safe_mapping(context.get("document_facts"))
    return [
        _evaluate_rule(
            rule_id=rule_id,
            event_facts=event_facts,
            document_facts=document_facts,
        )
        for rule_id in requested
    ]
