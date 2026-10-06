"""Luxian0916 首次病程内容质控（LX0916-010..014）。

本模块只消费调用方已经归集的首次病程结构化字段和受控语义事实；不读取
四川规则包，也不从病程正文的宽泛关键词猜测语义结论。
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from .contracts import Luxian0916RuleResult


_RULE_IDS = (
    "LX0916-010",
    "LX0916-011",
    "LX0916-012",
    "LX0916-013",
    "LX0916-014",
)
_QUALITY_VALUES = frozenset({"adequate", "inadequate"})


def _text(value: Any) -> str:
    return value.strip() if isinstance(value, str) else ""


def _result(
    rule_id: str,
    status: str,
    reason_code: str,
    findings: str,
    *,
    evidence: tuple[str, ...] = (),
    suggestion: str = "",
    anchors: tuple[Mapping[str, Any], ...] = (),
    diagnostics: Mapping[str, Any] | None = None,
    decision_facts: Mapping[str, Any] | None = None,
) -> Luxian0916RuleResult:
    return Luxian0916RuleResult(
        rule_id=rule_id,
        status=status,
        reason_code=reason_code,
        findings=findings,
        evidence=evidence,
        suggestion=suggestion,
        document_anchors=anchors,
        diagnostics=diagnostics or {},
        decision_facts=decision_facts or {"source_type": "first_course_record"},
    )


def _document_decision_facts(
    row: Mapping[str, Any] | None = None,
    *,
    target_document_available: bool,
    candidate_document_count: int | None = None,
    primary_document_count: int | None = None,
    evaluation_window_mature: bool | None = None,
) -> dict[str, Any]:
    """仅保留文书选择与检查时点，不将文书正文写入批量结果。"""

    facts: dict[str, Any] = {
        "source_type": "first_course_record",
        "target_document_available": target_document_available,
    }
    if candidate_document_count is not None:
        facts["candidate_document_count"] = candidate_document_count
    if primary_document_count is not None:
        facts["primary_document_count"] = primary_document_count
    if evaluation_window_mature is not None:
        facts["evaluation_window_mature"] = evaluation_window_mature
    if row is not None:
        document_id = _text(row.get("document_id") or row.get("id"))
        if document_id:
            facts["document_id"] = document_id
        facts["document_selected"] = True
    return facts


def _field_decision_facts(
    context: Mapping[str, Any], row: Mapping[str, Any], states: Mapping[str, tuple[bool, str]]
) -> dict[str, Any]:
    facts = _selected_document_decision_facts(context, row)
    facts["field_states"] = {
        field: "unavailable" if not available else "present" if value else "empty"
        for field, (available, value) in states.items()
    }
    return facts


def _selected_document_decision_facts(
    context: Mapping[str, Any], row: Mapping[str, Any]
) -> dict[str, Any]:
    documents = context.get("documents")
    rows = documents.get("first_course_record") if isinstance(documents, Mapping) else None
    valid_rows = (
        [item for item in rows if isinstance(item, Mapping)]
        if isinstance(rows, Sequence) and not isinstance(rows, (str, bytes))
        else []
    )
    return _document_decision_facts(
        row,
        target_document_available=True,
        candidate_document_count=len(valid_rows),
        primary_document_count=sum(item.get("is_primary") is True for item in valid_rows),
    )


def _semantic_quality_decision_facts(
    facts: Mapping[str, Any], values: Mapping[str, str | None]
) -> dict[str, Any]:
    result = dict(facts)
    result["semantic_quality_states"] = {
        key: value if value is not None else "unavailable" for key, value in values.items()
    }
    return result


def _first_course_row(
    context: Mapping[str, Any], rule_id: str
) -> tuple[Mapping[str, Any] | None, Luxian0916RuleResult | None]:
    documents = context.get("documents")
    if not isinstance(documents, Mapping) or "first_course_record" not in documents:
        return None, _result(
            rule_id,
            "data_quality_gap",
            "first_course_document_source_missing",
            "未提供首次病程记录数据源，无法检查内容质量。",
            suggestion="补齐首次病程记录数据源后重新质控。",
            decision_facts=_document_decision_facts(target_document_available=False),
        )

    rows = documents.get("first_course_record")
    if not isinstance(rows, Sequence) or isinstance(rows, (str, bytes)):
        return None, _result(
            rule_id,
            "data_quality_gap",
            "first_course_document_source_invalid",
            "首次病程记录数据源格式无效，无法检查内容质量。",
            suggestion="修复首次病程记录数据源格式后重新质控。",
            decision_facts=_document_decision_facts(target_document_available=False),
        )

    valid_rows = [item for item in rows if isinstance(item, Mapping)]
    if rows and not valid_rows:
        return None, _result(
            rule_id,
            "data_quality_gap",
            "first_course_document_source_invalid",
            "首次病程记录数据源不含可读取文书，无法检查内容质量。",
            suggestion="补齐可读取的首次病程记录后重新质控。",
            decision_facts=_document_decision_facts(
                target_document_available=False,
                candidate_document_count=0,
            ),
        )
    if not valid_rows:
        mature = context.get("first_course_evaluation_window_mature")
        if mature is False:
            return None, _result(
                rule_id,
                "not_executed",
                "evaluation_window_not_mature",
                "首次病程记录尚未到内容检查时点。",
                decision_facts=_document_decision_facts(
                    target_document_available=False,
                    candidate_document_count=0,
                    evaluation_window_mature=False,
                ),
            )
        if mature is not True:
            return None, _result(
                rule_id,
                "data_quality_gap",
                "first_course_evaluation_window_unknown",
                "未提供首次病程记录检查时点，无法区分未形成文书与数据缺失。",
                suggestion="补齐首次病程记录的检查时点。",
                decision_facts=_document_decision_facts(
                    target_document_available=False,
                    candidate_document_count=0,
                ),
            )
        return None, _result(
            rule_id,
            "not_applicable",
            "first_course_document_not_formed",
            "首次病程记录尚未形成；内容质量规则不评价文书是否按时形成。",
            suggestion="首次病程记录时效性请由独立时效规则检查。",
            decision_facts=_document_decision_facts(
                target_document_available=False,
                candidate_document_count=0,
                evaluation_window_mature=True,
            ),
        )

    # 首次病程应为单份首程文书。多个候选且未给出主文书标记时，拒绝由行序猜测。
    primary_rows = [row for row in valid_rows if row.get("is_primary") is True]
    if len(valid_rows) > 1 and len(primary_rows) != 1:
        return None, _result(
            rule_id,
            "data_quality_gap",
            "first_course_document_ambiguous",
            "存在多份首次病程候选文书，无法确认应检查的首次病程记录。",
            suggestion="标记唯一首次病程主文书后重新质控。",
            decision_facts=_document_decision_facts(
                target_document_available=True,
                candidate_document_count=len(valid_rows),
                primary_document_count=len(primary_rows),
            ),
        )
    return (primary_rows[0] if primary_rows else valid_rows[0]), None


def _anchor(row: Mapping[str, Any], *fields: str) -> tuple[Mapping[str, Any], ...]:
    return (
        {
            "document_type": "first_course_record",
            "document_id": _text(row.get("document_id") or row.get("id")),
            "fields": list(fields),
        },
    )


_PRESENCE_FACT_BY_FIELD = {
    "case_characteristic": "case_characteristic_present",
    "diagnose_based_on": "diagnosis_basis_present",
    "differential_diagnosis": "differential_diagnosis_present",
    "treatment_plan": "treatment_plan_present",
}


def _field_state(
    context: Mapping[str, Any], row: Mapping[str, Any], field_name: str
) -> tuple[bool, str]:
    if field_name not in row:
        sections = row.get("structured_sections")
        if isinstance(sections, Mapping):
            section_value = sections.get(field_name)
            if isinstance(section_value, str):
                return True, _text(section_value)
        semantic_facts = context.get("semantic_facts")
        presence_key = _PRESENCE_FACT_BY_FIELD[field_name]
        if isinstance(semantic_facts, Mapping) and type(semantic_facts.get(presence_key)) is bool:
            return True, "受控语义事实已确认" if semantic_facts[presence_key] else ""
        return False, ""
    return True, _text(row.get(field_name))


def _semantic_fact(
    context: Mapping[str, Any], row: Mapping[str, Any], key: str
) -> str | None:
    for source in (row.get("semantic_facts"), context.get("semantic_facts")):
        if isinstance(source, Mapping) and source.get(key) in _QUALITY_VALUES:
            return str(source[key])
    return None


def _missing_semantic_result(
    rule_id: str,
    context: Mapping[str, Any],
    row: Mapping[str, Any],
    fact_keys: tuple[str, ...],
    decision_facts: Mapping[str, Any],
) -> Luxian0916RuleResult:
    return _result(
        rule_id,
        "data_quality_gap",
        "semantic_fact_unavailable",
        "未提供受控语义事实，无法评价首次病程内容是否充分或具体。",
        suggestion="补齐该首次病程的受控语义事实后重新质控。",
        anchors=_anchor(row, *fact_keys),
        diagnostics={"missing_semantic_facts": list(fact_keys)},
        decision_facts=_semantic_quality_decision_facts(
            decision_facts,
            {key: None for key in fact_keys},
        ),
    )


def _evaluate_010(context: Mapping[str, Any]) -> Luxian0916RuleResult:
    row, early = _first_course_row(context, "LX0916-010")
    if early:
        return early
    assert row is not None
    available, value = _field_state(context, row, "case_characteristic")
    decision_facts = _field_decision_facts(
        context,
        row,
        {"case_characteristic": (available, value)},
    )
    if not available:
        return _result(
            "LX0916-010", "data_quality_gap", "first_course_structured_field_missing",
            "首次病程记录未提供病例特点结构化字段，无法判断是否缺失。",
            suggestion="补齐病例特点结构化字段后重新质控。",
            anchors=_anchor(row, "case_characteristic"),
            decision_facts=decision_facts,
        )
    if not value:
        return _result(
            "LX0916-010", "non_compliant", "case_characteristic_missing",
            "首次病程记录未填写病例特点。",
            evidence=("首次病程记录的病例特点字段为空。",),
            suggestion="补充病例特点。",
            anchors=_anchor(row, "case_characteristic"),
            decision_facts=decision_facts,
        )
    return _result(
        "LX0916-010", "compliant", "case_characteristic_present",
        "首次病程记录已填写病例特点。",
        evidence=("首次病程记录的病例特点字段已填写。",),
        anchors=_anchor(row, "case_characteristic"),
        decision_facts=decision_facts,
    )


def _evaluate_011(context: Mapping[str, Any]) -> Luxian0916RuleResult:
    row, early = _first_course_row(context, "LX0916-011")
    if early:
        return early
    assert row is not None
    available, value = _field_state(context, row, "case_characteristic")
    decision_facts = _field_decision_facts(
        context,
        row,
        {"case_characteristic": (available, value)},
    )
    if not available:
        return _result(
            "LX0916-011", "data_quality_gap", "first_course_structured_field_missing",
            "首次病程记录未提供病例特点结构化字段，无法评价是否已归纳提炼。",
            suggestion="补齐病例特点结构化字段后重新质控。",
            anchors=_anchor(row, "case_characteristic"),
            decision_facts=decision_facts,
        )
    if not value:
        return _result(
            "LX0916-011", "non_compliant", "case_characteristic_missing",
            "首次病程记录未填写病例特点，无法体现病史、查体和辅助检查的归纳。",
            suggestion="补充并归纳病例特点。",
            anchors=_anchor(row, "case_characteristic"),
            decision_facts=decision_facts,
        )
    quality = _semantic_fact(context, row, "case_characteristic_quality")
    if quality is None:
        return _missing_semantic_result(
            "LX0916-011",
            context,
            row,
            ("case_characteristic_quality",),
            decision_facts,
        )
    if quality == "inadequate":
        return _result(
            "LX0916-011", "non_compliant", "case_characteristic_inadequate",
            "病例特点未归纳提炼或不全面。",
            suggestion="结合病史、查体和辅助检查归纳并完善病例特点。",
            anchors=_anchor(row, "case_characteristic"),
            diagnostics={"case_characteristic_quality": quality},
            decision_facts=_semantic_quality_decision_facts(
                decision_facts,
                {"case_characteristic_quality": quality},
            ),
        )
    return _result(
        "LX0916-011", "compliant", "case_characteristic_adequate",
        "病例特点已归纳且内容充分。",
        anchors=_anchor(row, "case_characteristic"),
        diagnostics={"case_characteristic_quality": quality},
        decision_facts=_semantic_quality_decision_facts(
            decision_facts,
            {"case_characteristic_quality": quality},
        ),
    )


def _evaluate_012(context: Mapping[str, Any]) -> Luxian0916RuleResult:
    row, early = _first_course_row(context, "LX0916-012")
    if early:
        return early
    assert row is not None
    fields = {
        "diagnose_based_on": "诊断依据",
        "differential_diagnosis": "鉴别诊断",
        "treatment_plan": "诊疗计划",
    }
    states = {field: _field_state(context, row, field) for field in fields}
    decision_facts = _field_decision_facts(context, row, states)
    unavailable = [field for field, (available, _value) in states.items() if not available]
    if unavailable:
        return _result(
            "LX0916-012", "data_quality_gap", "first_course_structured_field_missing",
            "首次病程记录缺少必要结构化字段，无法判断诊断依据、鉴别诊断和诊疗计划是否齐全。",
            suggestion="补齐首次病程的必要结构化字段后重新质控。",
            anchors=_anchor(row, *unavailable),
            diagnostics={"missing_fields": unavailable},
            decision_facts=decision_facts,
        )
    missing = [label for field, label in fields.items() if not states[field][1]]
    if missing:
        return _result(
            "LX0916-012", "non_compliant", "first_course_required_section_missing",
            "首次病程记录缺少" + "、".join(missing) + "。",
            evidence=("缺少字段：" + "、".join(missing) + "。",),
            suggestion="补充诊断依据、鉴别诊断和诊疗计划中的缺失内容。",
            anchors=_anchor(row, *[field for field, label in fields.items() if label in missing]),
            diagnostics={"missing_sections": missing},
            decision_facts=decision_facts,
        )
    return _result(
        "LX0916-012", "compliant", "first_course_required_sections_present",
        "首次病程记录已填写诊断依据、鉴别诊断和诊疗计划。",
        anchors=_anchor(row, *fields),
        decision_facts=decision_facts,
    )


def _evaluate_013(context: Mapping[str, Any]) -> Luxian0916RuleResult:
    row, early = _first_course_row(context, "LX0916-013")
    if early:
        return early
    assert row is not None
    sections = {
        "diagnose_based_on": "诊断依据",
        "differential_diagnosis": "鉴别诊断",
    }
    states = {field: _field_state(context, row, field) for field in sections}
    decision_facts = _field_decision_facts(context, row, states)
    unavailable = [field for field, (available, _value) in states.items() if not available]
    if unavailable:
        return _result(
            "LX0916-013", "data_quality_gap", "first_course_structured_field_missing",
            "首次病程记录未提供诊断依据或鉴别诊断结构化字段，无法评价内容是否充分。",
            suggestion="补齐诊断依据和鉴别诊断结构化字段后重新质控。",
            anchors=_anchor(row, *unavailable),
            diagnostics={"missing_fields": unavailable},
            decision_facts=decision_facts,
        )
    missing = [label for field, label in sections.items() if not states[field][1]]
    if missing:
        return _result(
            "LX0916-013", "non_compliant", "diagnostic_reasoning_missing",
            "首次病程记录缺少" + "、".join(missing) + "，无法形成充分的拟诊讨论。",
            suggestion="补充与病例特点相对应的诊断依据和鉴别诊断分析。",
            anchors=_anchor(row, *[field for field, label in sections.items() if label in missing]),
            diagnostics={"missing_sections": missing},
            decision_facts=decision_facts,
        )
    keys = ("diagnosis_basis_quality", "differential_diagnosis_quality")
    facts = {key: _semantic_fact(context, row, key) for key in keys}
    if any(value is None for value in facts.values()):
        return _missing_semantic_result(
            "LX0916-013",
            context,
            row,
            keys,
            decision_facts,
        )
    inadequate = [key for key, value in facts.items() if value == "inadequate"]
    if inadequate:
        labels = {
            "diagnosis_basis_quality": "诊断依据",
            "differential_diagnosis_quality": "鉴别诊断",
        }
        source_fields = {
            "diagnosis_basis_quality": "diagnose_based_on",
            "differential_diagnosis_quality": "differential_diagnosis",
        }
        return _result(
            "LX0916-013", "non_compliant", "diagnostic_reasoning_inadequate",
            "首次病程记录的" + "、".join(labels[key] for key in inadequate) + "不充分。",
            suggestion="补充与诊断结论相关的诊断依据和鉴别诊断分析。",
            anchors=_anchor(row, *[source_fields[key] for key in inadequate]),
            diagnostics=facts,
            decision_facts=_semantic_quality_decision_facts(decision_facts, facts),
        )
    return _result(
        "LX0916-013", "compliant", "diagnostic_reasoning_adequate",
        "首次病程记录的诊断依据和鉴别诊断充分。",
        anchors=_anchor(row, "diagnose_based_on", "differential_diagnosis"),
        diagnostics=facts,
        decision_facts=_semantic_quality_decision_facts(decision_facts, facts),
    )


def _evaluate_014(context: Mapping[str, Any]) -> Luxian0916RuleResult:
    row, early = _first_course_row(context, "LX0916-014")
    if early:
        return early
    assert row is not None
    available, value = _field_state(context, row, "treatment_plan")
    decision_facts = _field_decision_facts(
        context,
        row,
        {"treatment_plan": (available, value)},
    )
    if not available:
        return _result(
            "LX0916-014", "data_quality_gap", "first_course_structured_field_missing",
            "首次病程记录未提供诊疗计划结构化字段，无法评价计划是否全面具体。",
            suggestion="补齐诊疗计划结构化字段后重新质控。",
            anchors=_anchor(row, "treatment_plan"),
            decision_facts=decision_facts,
        )
    if not value:
        return _result(
            "LX0916-014", "non_compliant", "treatment_plan_missing",
            "首次病程记录未填写诊疗计划。",
            suggestion="补充诊疗计划。",
            anchors=_anchor(row, "treatment_plan"),
            decision_facts=decision_facts,
        )
    quality = _semantic_fact(context, row, "treatment_plan_quality")
    if quality is None:
        return _missing_semantic_result(
            "LX0916-014",
            context,
            row,
            ("treatment_plan_quality",),
            decision_facts,
        )
    if quality == "inadequate":
        return _result(
            "LX0916-014", "non_compliant", "treatment_plan_inadequate",
            "首次病程记录的诊疗计划不全面或不具体。",
            suggestion="补充具体、完整的诊疗计划。",
            anchors=_anchor(row, "treatment_plan"),
            diagnostics={"treatment_plan_quality": quality},
            decision_facts=_semantic_quality_decision_facts(
                decision_facts,
                {"treatment_plan_quality": quality},
            ),
        )
    return _result(
        "LX0916-014", "compliant", "treatment_plan_adequate",
        "首次病程记录的诊疗计划全面且具体。",
        anchors=_anchor(row, "treatment_plan"),
        diagnostics={"treatment_plan_quality": quality},
        decision_facts=_semantic_quality_decision_facts(
            decision_facts,
            {"treatment_plan_quality": quality},
        ),
    )


_EVALUATORS = {
    "LX0916-010": _evaluate_010,
    "LX0916-011": _evaluate_011,
    "LX0916-012": _evaluate_012,
    "LX0916-013": _evaluate_013,
    "LX0916-014": _evaluate_014,
}


def execute_first_course_rules(
    context: Mapping[str, Any], rule_ids: Sequence[str] | None = None
) -> list[Luxian0916RuleResult]:
    """直接形成首次病程规则的客户交付结果。"""

    selected = _RULE_IDS if rule_ids is None else tuple(
        rule_id for rule_id in _RULE_IDS if rule_id in set(rule_ids)
    )
    return [_EVALUATORS[rule_id](context) for rule_id in selected]
