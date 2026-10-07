"""Luxian0916 入院记录规则族（001 至 009）。"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from .contracts import Luxian0916RuleResult
from .admission_content_items import ITEM_LABELS, ground_items


ADMISSION_RULE_IDS = tuple(f"LX0916-{number:03d}" for number in range(1, 10))
_SEMANTIC_STATES = frozenset({"complete", "incomplete", "not_applicable", "unknown"})


def execute_admission_rules(
    context: Mapping[str, Any], rule_ids: Sequence[str] | None = None
) -> list[Luxian0916RuleResult]:
    """直接形成入院规则的完整客户结果，不从正文关键词推断语义结论。"""

    if not isinstance(context, Mapping):
        raise TypeError("context must be a mapping")
    selected_rule_ids = tuple(rule_ids or ADMISSION_RULE_IDS)
    invalid_rule_ids = set(selected_rule_ids).difference(ADMISSION_RULE_IDS)
    if invalid_rule_ids:
        raise ValueError(f"unsupported admission rule_ids: {sorted(invalid_rule_ids)}")
    documents = context.get("documents")
    document_facts = context.get("document_facts")
    semantic_facts = context.get("semantic_facts")
    admission_record = _admission_record(documents, document_facts)
    if admission_record is None:
        if context.get("admission_evaluation_window_mature") is False:
            return [_not_executed(rule_id) for rule_id in selected_rule_ids]
        return [_source_unavailable(rule_id) for rule_id in selected_rule_ids]
    return [
        _evaluate_rule(
            rule_id=rule_id,
            admission_record=admission_record,
            semantic_facts=semantic_facts,
        )
        for rule_id in selected_rule_ids
    ]


def _admission_record(
    documents: Any, document_facts: Any
) -> Mapping[str, Any] | None:
    if isinstance(documents, Mapping) and isinstance(documents.get("admission_record"), Mapping):
        return documents["admission_record"]
    if isinstance(document_facts, Mapping) and isinstance(
        document_facts.get("admission_record"), Mapping
    ):
        return document_facts["admission_record"]
    return None


def _evaluate_rule(
    *,
    rule_id: str,
    admission_record: Mapping[str, Any],
    semantic_facts: Any,
) -> Luxian0916RuleResult:
    if rule_id == "LX0916-001":
        return _evaluate_repeat_admission(admission_record, semantic_facts)
    if rule_id == "LX0916-002":
        return _evaluate_civil_capacity(admission_record, semantic_facts)
    if rule_id == "LX0916-008":
        return _evaluate_child_history(admission_record, semantic_facts)
    if rule_id in ITEM_LABELS:
        return _evaluate_content_items(rule_id, admission_record, semantic_facts)
    return _evaluate_semantic_content(rule_id, admission_record, semantic_facts)


def _evaluate_content_items(
    rule_id: str, admission_record: Mapping[str, Any], semantic_facts: Any,
) -> Luxian0916RuleResult:
    raw_fact = semantic_facts.get(rule_id) if isinstance(semantic_facts, Mapping) else None
    items = ground_items(rule_id, raw_fact, admission_record)
    facts = _admission_decision_facts(admission_record)
    if items is None:
        return _result(
            rule_id, "data_quality_gap", "semantic_fact_unavailable", admission_record,
            "未取得可定位的逐项内容事实，不能据此认定医生漏写。",
            "请核对入院记录来源与逐项抽取依据后复核。", decision_facts=facts,
        )
    labels = ITEM_LABELS[rule_id]
    missing = [labels[key] for key, item in items.items() if item["status"] == "missing"]
    unknown = [labels[key] for key, item in items.items() if item["status"] == "unknown"]
    documented_unknown = [labels[key] for key, item in items.items() if item["status"] == "documented_unknown"]
    facts.update(item_states={key: item["status"] for key, item in items.items()},
                 missing_items=missing, unknown_items=unknown)
    if rule_id == "LX0916-005":
        facts["documented_unknown_items"] = documented_unknown
    if missing:
        status, reason = "non_compliant", "requirement_violated"
        findings = "核对入院记录后确认缺失或描述笼统：" + "、".join(missing) + "。"
        suggestion = "请依据实际病史补充：" + "、".join(missing) + "；明确否认或不详时如实记录，不补写虚构经历。"
    elif unknown:
        status, reason = "data_quality_gap", "semantic_fact_unavailable"
        explanation = "抽取未确定或信息归属、含义冲突，不等于医生漏写。" if rule_id == "LX0916-005" else "信息不详或抽取未确定，不等于医生漏写。"
        findings = "尚无法确认：" + "、".join(unknown) + "；" + explanation
        suggestion = "请复核相关原文及信息来源，保留明确不详的说明后再判断。"
    elif documented_unknown:
        status, reason = "data_quality_gap", "recorded_information_unknown"
        findings = "原文已明确记载信息不详：" + "、".join(documented_unknown) + "；是否满足详细记录要求尚需人工复核，未认定为漏写或合规。"
        suggestion = "请结合已记录的诊疗经过、效果及信息来源复核详细程度；无法获知的信息如实保留，不推造药名或方案。"
    elif rule_id == "LX0916-005" and all(item["status"] in {"denied", "not_applicable"} for item in items.values()):
        status, reason = "not_applicable", "eligibility_not_met"
        findings, suggestion = "原文未显示需要核对的院前检查治疗行为。", ""
    else:
        status, reason = "compliant", "requirement_satisfied"
        findings, suggestion = "逐项内容均有记录或明确否认，未发现确认缺项。", ""
    if missing and unknown:
        findings += "另有待确认项：" + "、".join(unknown) + "，未计入确认缺项。"
    if documented_unknown and (missing or unknown):
        findings += "另有原文已明确记载信息不详：" + "、".join(documented_unknown) + "，未计入确认缺项。"
    base = _result(rule_id, status, reason, admission_record, findings, suggestion, facts)
    # 原文摘录只放证据，不塞入公开的判定事实快照。
    evidence = tuple(f"{labels[key]}：{item['quote']}" for key, item in items.items() if item["quote"])
    return Luxian0916RuleResult(
        rule_id=base.rule_id, status=base.status, reason_code=base.reason_code,
        findings=base.findings, suggestion=base.suggestion,
        evidence=evidence or base.evidence, document_anchors=base.document_anchors,
        diagnostics=base.diagnostics, decision_facts=base.decision_facts,
    )


def _evaluate_repeat_admission(
    admission_record: Mapping[str, Any], semantic_facts: Any
) -> Luxian0916RuleResult:
    patient = _patient(admission_record)
    prior_admission_count = patient.get("prior_admission_count")
    decision_facts = _admission_decision_facts(admission_record)
    if not isinstance(prior_admission_count, int) or isinstance(prior_admission_count, bool) or prior_admission_count < 0:
        decision_facts["prior_admission_count_available"] = False
        return _evaluate_semantic_content(
            "LX0916-001", admission_record, semantic_facts, decision_facts=decision_facts
        )
    decision_facts["prior_admission_count"] = prior_admission_count
    if prior_admission_count < 2:
        return _result(
            "LX0916-001", "not_applicable", "eligibility_not_met", admission_record,
            "当前结构化资料未显示再次或多次入院。",
            decision_facts=decision_facts,
        )
    return _evaluate_semantic_content(
        "LX0916-001", admission_record, semantic_facts, decision_facts=decision_facts
    )


def _evaluate_civil_capacity(
    admission_record: Mapping[str, Any], semantic_facts: Any
) -> Luxian0916RuleResult:
    patient = _patient(admission_record)
    capacity = patient.get("civil_capacity")
    decision_facts = _admission_decision_facts(admission_record)
    if capacity in {"full", "limited", "none"}:
        decision_facts["civil_capacity"] = capacity
    else:
        decision_facts["civil_capacity_available"] = False
    if capacity == "full":
        return _result(
            "LX0916-002", "not_applicable", "eligibility_not_met", admission_record,
            "患者具完全民事行为能力，本规则不适用。",
            decision_facts=decision_facts,
        )
    age_years = _patient_age_years(patient)
    if age_years is None:
        decision_facts["age_years_available"] = False
    else:
        decision_facts["age_years"] = age_years
    if capacity not in {"limited", "none"} and age_years is not None:
        if age_years < 16:
            capacity = "none"
            decision_facts["civil_capacity_inferred_from_age"] = True
        elif age_years < 18:
            return _result(
                "LX0916-002", "data_quality_gap", "civil_capacity_fact_unavailable", admission_record,
                "16至17岁患者未取得明确民事行为能力事实，无法忽略法定例外。",
                decision_facts=decision_facts,
            )
    if capacity not in {"limited", "none"}:
        return _evaluate_semantic_content(
            "LX0916-002", admission_record, semantic_facts, decision_facts=decision_facts
        )
    narrator = admission_record.get("history_narrator")
    if narrator in {"patient", "guardian", "relative", "caregiver"}:
        decision_facts["history_narrator"] = narrator
    else:
        decision_facts["history_narrator_available"] = False
    if narrator == "patient":
        return _result(
            "LX0916-002", "non_compliant", "requirement_violated", admission_record,
            "无完全民事行为能力患者被记录为病史陈述者。",
            "请由法定代理人或能够提供病史的相关人员陈述并记录关系。",
            decision_facts=decision_facts,
        )
    if narrator in {"guardian", "relative", "caregiver"}:
        return _result(
            "LX0916-002", "compliant", "requirement_satisfied", admission_record,
            "病史陈述者与患者民事行为能力要求相符。",
            decision_facts=decision_facts,
        )
    return _result(
        "LX0916-002", "data_quality_gap", "semantic_fact_unavailable", admission_record,
        "未取得病史陈述者身份，无法作出可靠判断。",
        decision_facts=decision_facts,
    )


def _evaluate_child_history(
    admission_record: Mapping[str, Any], semantic_facts: Any
) -> Luxian0916RuleResult:
    age_years = _patient_age_years(_patient(admission_record))
    decision_facts = _admission_decision_facts(admission_record)
    if age_years is None:
        decision_facts["age_years_available"] = False
        return _evaluate_semantic_content(
            "LX0916-008", admission_record, semantic_facts, decision_facts=decision_facts
        )
    decision_facts["age_years"] = age_years
    if age_years >= 18:
        return _result(
            "LX0916-008", "not_applicable", "eligibility_not_met", admission_record,
            "患者不属于儿童，婴幼儿喂养史和生长发育史要求不适用。",
            decision_facts=decision_facts,
        )
    if _semantic_state(semantic_facts, "LX0916-008") == "not_applicable":
        return _result(
            "LX0916-008", "data_quality_gap", "semantic_fact_conflicts_with_age", admission_record,
            "儿童年龄事实与文书内容不适用的语义事实冲突，无法作出可靠判断。",
            decision_facts={
                **decision_facts,
                "semantic_state": "not_applicable",
            },
        )
    return _evaluate_semantic_content(
        "LX0916-008", admission_record, semantic_facts, decision_facts=decision_facts
    )


def _evaluate_semantic_content(
    rule_id: str,
    admission_record: Mapping[str, Any],
    semantic_facts: Any,
    *,
    decision_facts: Mapping[str, Any] | None = None,
) -> Luxian0916RuleResult:
    state = _semantic_state(semantic_facts, rule_id)
    facts = _admission_decision_facts(admission_record)
    facts.update(decision_facts or {})
    if state is not None:
        facts["semantic_state"] = state
    if state is None or state == "unknown":
        return _result(
            rule_id, "data_quality_gap", "semantic_fact_unavailable", admission_record,
            "未取得本规则所需的权威语义事实，无法可靠判断文书内容。",
            decision_facts=facts,
        )
    if state == "complete":
        return _result(
            rule_id, "compliant", "requirement_satisfied", admission_record,
            "已取得完整性事实，未发现本规则定义的内容缺陷。",
            decision_facts=facts,
        )
    if state == "incomplete":
        return _result(
            rule_id, "non_compliant", "requirement_violated", admission_record,
            "权威事实显示目标内容不完整或不清楚。",
            "请依据本次就诊的实际情况补充或修正文书内容。",
            decision_facts=facts,
        )
    return _result(
        rule_id, "not_applicable", "eligibility_not_met", admission_record,
        "权威事实显示本规则在当前患者和文书场景中不适用。",
        decision_facts=facts,
    )


def _semantic_state(semantic_facts: Any, rule_id: str) -> str | None:
    if not isinstance(semantic_facts, Mapping):
        return None
    rule_facts = semantic_facts.get(rule_id)
    if not isinstance(rule_facts, Mapping):
        return None
    state = rule_facts.get("state")
    return state if state in _SEMANTIC_STATES else None


def _patient(admission_record: Mapping[str, Any]) -> Mapping[str, Any]:
    patient = admission_record.get("patient")
    return patient if isinstance(patient, Mapping) else {}


def _patient_age_years(patient: Mapping[str, Any]) -> int | None:
    value = patient.get("age_years")
    if isinstance(value, bool) or not isinstance(value, int) or not 0 <= value <= 130:
        return None
    return value


def _not_executed(rule_id: str) -> Luxian0916RuleResult:
    return Luxian0916RuleResult(
        rule_id=rule_id,
        status="not_executed",
        reason_code="evaluation_window_not_mature",
        findings="尚未取得已形成的入院记录，本规则未到检查时点。",
        suggestion="待入院记录形成后重新执行质控。",
        diagnostics={"family": "admission", "target_document_available": False},
        decision_facts={
            "source_type": "admission_record",
            "target_document_available": False,
            "evaluation_window_mature": False,
        },
    )


def _source_unavailable(rule_id: str) -> Luxian0916RuleResult:
    return Luxian0916RuleResult(
        rule_id=rule_id,
        status="data_quality_gap",
        reason_code="admission_document_source_unavailable",
        findings="未取得可读取的入院记录，无法判断文书内容质量。",
        suggestion="补齐入院记录数据源后重新执行质控。",
        diagnostics={"family": "admission", "target_document_available": False},
        decision_facts={
            "source_type": "admission_record",
            "target_document_available": False,
        },
    )


def _result(
    rule_id: str,
    status: str,
    reason_code: str,
    admission_record: Mapping[str, Any],
    findings: str,
    suggestion: str = "",
    decision_facts: Mapping[str, Any] | None = None,
) -> Luxian0916RuleResult:
    document_id = admission_record.get("document_id")
    anchor = {"document_type": "admission_record"}
    if isinstance(document_id, str) and document_id.strip():
        anchor["document_id"] = document_id.strip()
    evidence = (f"admission_record:{anchor.get('document_id', 'unidentified')}",)
    return Luxian0916RuleResult(
        rule_id=rule_id,
        status=status,
        reason_code=reason_code,
        findings=findings,
        evidence=evidence,
        suggestion=suggestion,
        document_anchors=(anchor,),
        diagnostics={"family": "admission", "decision_owner": "admission_rules"},
        decision_facts=decision_facts or _admission_decision_facts(admission_record),
    )


def _admission_decision_facts(admission_record: Mapping[str, Any]) -> dict[str, Any]:
    """返回规则实际使用的可复核事实，绝不携带病历正文。"""

    facts: dict[str, Any] = {
        "source_type": "admission_record",
        "target_document_available": True,
    }
    document_id = admission_record.get("document_id")
    if isinstance(document_id, str) and document_id.strip():
        facts["document_id"] = document_id.strip()
    return facts
