"""Luxian0916 病程事件质控（LX0916-015..020）。

事件是否触发、关联文书是否存在、以及语义判断均由受控 ``event_facts`` 提供。
本模块只按这些事实形成最终客户结果，不调用或映射任何四川规则。
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import replace
from typing import Any

from .contracts import Luxian0916RuleResult


_RULE_IDS = (
    "LX0916-015",
    "LX0916-016",
    "LX0916-017",
    "LX0916-018",
    "LX0916-019",
    "LX0916-020",
)
_EVENT_KEY_BY_RULE = {
    "LX0916-015": "disease_changes",
    "LX0916-016": "disease_changes",
    "LX0916-017": "exam_or_medication_orders",
    "LX0916-018": "critical_values",
    "LX0916-019": "important_operations",
    "LX0916-020": "diagnosis_changes",
}
_DOCUMENTATION_FIELDS_BY_RULE = {
    "LX0916-015": ("record_present", "complete"),
    "LX0916-016": ("analysis_recorded", "specific_management_recorded"),
    "LX0916-018": ("report_recorded", "disposition_recorded"),
    "LX0916-019": ("record_present", "complete"),
    "LX0916-020": ("reason_recorded", "basis_recorded"),
}
_APPROPRIATENESS_VALUES = frozenset({"reasonable", "unreasonable"})


def _decision_facts_from_context(
    context: Mapping[str, Any], rule_id: str
) -> Mapping[str, Any]:
    """持久化规则实际读取的受控事件事实，拒绝带出正文或模型原始输出。"""

    event_key = _EVENT_KEY_BY_RULE[rule_id]
    facts = context.get("event_facts")
    states = context.get("event_source_state_by_rule")
    source_state = states.get(rule_id) if isinstance(states, Mapping) else None
    if not isinstance(facts, Mapping) or event_key not in facts:
        return {
            "event_key": event_key,
            "source_state": (
                source_state
                if source_state in {"selected", "not_selected", "partial"}
                else "unverified"
            ),
            "events": [],
        }

    rows = facts.get(event_key)
    if not isinstance(rows, Sequence) or isinstance(rows, (str, bytes)):
        return {"event_key": event_key, "source_state": "invalid", "events": []}

    source_state = "partial" if source_state == "partial" else "available"
    documentation_fields = _DOCUMENTATION_FIELDS_BY_RULE.get(rule_id, ())
    serialized_events: list[Mapping[str, Any]] = []
    for event in rows:
        if not isinstance(event, Mapping):
            source_state = "invalid"
            continue
        documentation = event.get("documentation")
        snapshot: dict[str, Any] = {
            "trigger_confirmed": (
                event.get("trigger_confirmed")
                if isinstance(event.get("trigger_confirmed"), bool)
                else None
            ),
            "evaluation_window_mature": (
                event.get("evaluation_window_mature")
                if isinstance(event.get("evaluation_window_mature"), bool)
                else None
            ),
            "documentation": {
                field: documentation.get(field)
                for field in documentation_fields
                if isinstance(documentation, Mapping)
                and isinstance(documentation.get(field), bool)
            },
        }
        if rule_id == "LX0916-017":
            snapshot["appropriateness"] = (
                event.get("appropriateness")
                if event.get("appropriateness") in _APPROPRIATENESS_VALUES
                else None
            )
        for field in ("event_type", "event_id", "document_id", "source_type"):
            value = str(event.get(field) or "").strip()
            if value and len(value) <= 160 and "\n" not in value and "\r" not in value:
                snapshot[field] = value
        serialized_events.append(snapshot)
    return {
        "event_key": event_key,
        "source_state": source_state,
        "events": serialized_events,
    }


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
    )


def _event_rows(
    context: Mapping[str, Any], rule_id: str
) -> tuple[tuple[Mapping[str, Any], ...] | None, Luxian0916RuleResult | None]:
    facts = context.get("event_facts")
    event_key = _EVENT_KEY_BY_RULE[rule_id]
    if not isinstance(facts, Mapping) or event_key not in facts:
        states = context.get("event_source_state_by_rule")
        source_state = states.get(rule_id) if isinstance(states, Mapping) else None
        if source_state == "partial":
            return None, _partial_event_source_result(rule_id)
        if source_state == "selected":
            reason_code = "event_fact_unavailable"
            findings = "该规则相关资料已纳入本次受控核对，但未形成可验证的事件事实，无法确认是否触发病程记录检查。"
            suggestion = "复核受控提取后重新质控。"
        elif source_state == "not_selected":
            reason_code = "event_source_unavailable"
            findings = "本次受控输入未选出可读取的目标文书，无法确认是否触发病程记录检查。"
            suggestion = "补充可读取的目标文书后重新质控。"
        else:
            reason_code = "event_source_unverified"
            findings = "未验证本次受控输入是否选出该规则的目标文书，无法确认是否触发病程记录检查。"
            suggestion = "核对事件来源选择与受控事实后重新质控。"
        return None, _result(
            rule_id,
            "data_quality_gap",
            reason_code,
            findings,
            suggestion=suggestion,
            diagnostics={"event_key": event_key, "event_source_state": source_state},
        )
    rows = facts.get(event_key)
    if not isinstance(rows, Sequence) or isinstance(rows, (str, bytes)):
        return None, _result(
            rule_id,
            "data_quality_gap",
            "event_source_invalid",
            "事件数据源格式无效，无法确认是否触发病程记录检查。",
            suggestion="修复事件数据源格式后重新质控。",
            diagnostics={"event_key": event_key},
        )
    if any(not isinstance(row, Mapping) for row in rows):
        return None, _result(
            rule_id,
            "data_quality_gap",
            "event_source_invalid",
            "事件数据源含不可读取记录，无法安全确认触发条件。",
            suggestion="修复事件记录后重新质控。",
            diagnostics={"event_key": event_key},
        )
    return tuple(rows), None


def _triggered_events(
    rule_id: str, rows: tuple[Mapping[str, Any], ...]
) -> tuple[tuple[Mapping[str, Any], ...] | None, Luxian0916RuleResult | None]:
    if not rows:
        return (), _result(
            rule_id,
            "not_applicable",
            "trigger_event_absent",
            "未发现该规则对应的触发事件。",
        )
    if any(
        row.get("trigger_confirmed") is not True
        and row.get("trigger_confirmed") is not False
        for row in rows
    ):
        return None, _result(
            rule_id,
            "data_quality_gap",
            "event_trigger_unavailable",
            "事件是否满足触发条件未被确认，无法进入病程记录检查。",
            suggestion="补齐事件触发确认结果后重新质控。",
        )
    triggered = tuple(row for row in rows if row.get("trigger_confirmed") is True)
    if not triggered:
        return (), _result(
            rule_id,
            "not_applicable",
            "trigger_event_absent",
            "现有事件均不满足该规则的触发条件。",
        )
    return triggered, None


def _event_anchor(event: Mapping[str, Any], *fields: str) -> Mapping[str, Any]:
    return {
        "event_type": str(event.get("event_type") or ""),
        "event_id": str(event.get("event_id") or ""),
        "document_type": str(event.get("source_type") or ""),
        "document_id": str(event.get("document_id") or ""),
        "fields": list(fields),
    }


def _maturity(
    rule_id: str, events: tuple[Mapping[str, Any], ...]
) -> tuple[tuple[Mapping[str, Any], ...] | None, Luxian0916RuleResult | None]:
    if any(
        event.get("evaluation_window_mature") is not True
        and event.get("evaluation_window_mature") is not False
        for event in events
    ):
        return None, _result(
            rule_id,
            "data_quality_gap",
            "evaluation_window_unknown",
            "未提供触发事件的评价时间窗，无法判断是否应检查病程记录。",
            suggestion="补齐触发事件的评价时间窗后重新质控。",
        )
    return events, None


def _documentation(
    rule_id: str, events: tuple[Mapping[str, Any], ...], fields: tuple[str, ...]
) -> tuple[tuple[Mapping[str, Any], ...] | None, Luxian0916RuleResult | None]:
    missing = [event for event in events if not isinstance(event.get("documentation"), Mapping)]
    if missing:
        return None, _result(
            rule_id,
            "data_quality_gap",
            "event_documentation_source_missing",
            "触发事件已确认，但未提供可关联的病程记录事实，无法判断记录是否完整。",
            suggestion="补齐事件关联的病程记录事实后重新质控。",
            anchors=tuple(_event_anchor(event, *fields) for event in missing),
        )
    return events, None


def _not_mature_result(rule_id: str, events: tuple[Mapping[str, Any], ...]) -> Luxian0916RuleResult:
    return _result(
        rule_id,
        "not_executed",
        "evaluation_window_not_mature",
        "存在已触发事件，但其病程记录评价时间窗尚未成熟。",
        anchors=tuple(_event_anchor(event, "evaluation_window_mature") for event in events if event.get("evaluation_window_mature") is False),
    )


def _partial_event_source_result(rule_id: str) -> Luxian0916RuleResult:
    return _result(
        rule_id,
        "data_quality_gap",
        "event_source_partial",
        "本次仅核对部分病程资料，无法确认是否还有其他触发事件或整体记录是否符合要求。",
        suggestion="补齐未纳入或截断的病程资料后重新质控。",
        diagnostics={"event_source_state": "partial"},
    )


def _bool_documentation(
    rule_id: str,
    events: tuple[Mapping[str, Any], ...],
    fields: tuple[str, ...],
) -> tuple[dict[str, bool] | None, Luxian0916RuleResult | None]:
    values: dict[str, bool] = {}
    invalid: list[Mapping[str, Any]] = []
    for field in fields:
        field_values: list[bool] = []
        for event in events:
            value = event["documentation"].get(field)
            if not isinstance(value, bool):
                invalid.append(event)
                continue
            field_values.append(value)
        if len(field_values) != len(events):
            continue
        values[field] = all(field_values)
    if invalid or len(values) != len(fields):
        return None, _result(
            rule_id,
            "data_quality_gap",
            "event_documentation_fact_unavailable",
            "触发事件的病程记录事实不完整，无法判断是否符合要求。",
            suggestion="补齐事件关联病程记录的受控事实后重新质控。",
            anchors=tuple(_event_anchor(event, *fields) for event in invalid),
        )
    return values, None


def _confirmed_documentation_defects(
    events: tuple[Mapping[str, Any], ...], fields: tuple[str, ...]
) -> tuple[list[str], tuple[Mapping[str, Any], ...]]:
    """只归集已到检查时点且明确缺项的事件，其他事件不能遮蔽已确定的问题。"""

    failed_fields: list[str] = []
    anchors: list[Mapping[str, Any]] = []
    for event in events:
        if event.get("evaluation_window_mature") is not True:
            continue
        documentation = event.get("documentation")
        if not isinstance(documentation, Mapping):
            continue
        event_defects = tuple(field for field in fields if documentation.get(field) is False)
        if event_defects:
            failed_fields.extend(field for field in event_defects if field not in failed_fields)
            anchors.append(_event_anchor(event, *event_defects))
    return failed_fields, tuple(anchors)


def _evaluate_015(context: Mapping[str, Any]) -> Luxian0916RuleResult:
    rows, early = _event_rows(context, "LX0916-015")
    if early:
        return early
    assert rows is not None
    states = context.get("event_source_state_by_rule")
    partial = isinstance(states, Mapping) and states.get("LX0916-015") == "partial"
    if partial:
        events = tuple(row for row in rows if row.get("trigger_confirmed") is True)
    else:
        events, early = _triggered_events("LX0916-015", rows)
        if early:
            return early
    assert events is not None
    fields = ("record_present", "complete")
    defects, defect_anchors = _confirmed_documentation_defects(events, fields)
    if defects:
        return _result(
            "LX0916-015", "non_compliant", "disease_change_documentation_incomplete",
            "重要病情变化的病程记录缺失或不完整。",
            suggestion="补记重要病情变化及其完整病程记录。",
            anchors=defect_anchors,
            diagnostics={"failed_facts": defects},
        )
    if partial:
        return _partial_event_source_result("LX0916-015")
    _, early = _maturity("LX0916-015", events)
    if early:
        return early
    if any(event.get("evaluation_window_mature") is False for event in events):
        return _not_mature_result("LX0916-015", events)
    _, early = _documentation("LX0916-015", events, fields)
    if early:
        return early
    _, early = _bool_documentation("LX0916-015", events, fields)
    if early:
        return early
    return _result("LX0916-015", "compliant", "disease_change_documentation_complete", "重要病情变化已记录且内容完整。", anchors=tuple(_event_anchor(event, *fields) for event in events))


def _evaluate_016(context: Mapping[str, Any]) -> Luxian0916RuleResult:
    rows, early = _event_rows(context, "LX0916-016")
    if early:
        return early
    assert rows is not None
    states = context.get("event_source_state_by_rule")
    partial = isinstance(states, Mapping) and states.get("LX0916-016") == "partial"
    if partial:
        events = tuple(row for row in rows if row.get("trigger_confirmed") is True)
    else:
        events, early = _triggered_events("LX0916-016", rows)
        if early:
            return early
    assert events is not None
    fields = ("analysis_recorded", "specific_management_recorded")
    defects, defect_anchors = _confirmed_documentation_defects(events, fields)
    if defects:
        return _result("LX0916-016", "non_compliant", "disease_change_analysis_or_management_missing", "病情变化未记录分析判断或具体处理意见。", suggestion="补充病情变化的分析判断和具体处理意见。", anchors=defect_anchors, diagnostics={"failed_facts": defects})
    if partial:
        return _partial_event_source_result("LX0916-016")
    _, early = _maturity("LX0916-016", events)
    if early:
        return early
    if any(event.get("evaluation_window_mature") is False for event in events):
        return _not_mature_result("LX0916-016", events)
    _, early = _documentation("LX0916-016", events, fields)
    if early:
        return early
    _, early = _bool_documentation("LX0916-016", events, fields)
    if early:
        return early
    return _result("LX0916-016", "compliant", "disease_change_analysis_and_management_present", "病情变化已记录分析判断和具体处理意见。", anchors=tuple(_event_anchor(event, *fields) for event in events))


def _evaluate_017(context: Mapping[str, Any]) -> Luxian0916RuleResult:
    rows, early = _event_rows(context, "LX0916-017")
    if early:
        return early
    assert rows is not None
    events, early = _triggered_events("LX0916-017", rows)
    if early:
        return early
    assert events is not None
    _, early = _maturity("LX0916-017", events)
    if early:
        return early
    if any(event.get("evaluation_window_mature") is False for event in events):
        return _not_mature_result("LX0916-017", events)
    states = [event.get("appropriateness") for event in events]
    if not set(states).issubset({"reasonable", "unreasonable"}):
        return _result("LX0916-017", "data_quality_gap", "semantic_fact_unavailable", "未提供检查或用药合理性的受控语义事实，无法判断是否存在不合理检查或用药。", suggestion="补齐检查或用药合理性的受控语义事实后重新质控。", anchors=tuple(_event_anchor(event, "appropriateness") for event in events))
    if "unreasonable" in states:
        return _result("LX0916-017", "non_compliant", "exam_or_medication_unreasonable", "存在经受控事实确认的不合理检查或用药。", suggestion="复核检查或用药指征，并记录调整依据。", anchors=tuple(_event_anchor(event, "appropriateness") for event in events if event.get("appropriateness") == "unreasonable"), diagnostics={"appropriateness": states})
    return _result("LX0916-017", "compliant", "exam_or_medication_reasonable", "现有检查或用药均经受控事实确认合理。", anchors=tuple(_event_anchor(event, "appropriateness") for event in events))


def _evaluate_018(context: Mapping[str, Any]) -> Luxian0916RuleResult:
    rows, early = _event_rows(context, "LX0916-018")
    if early:
        return early
    assert rows is not None
    events, early = _triggered_events("LX0916-018", rows)
    if early:
        return early
    assert events is not None
    _, early = _maturity("LX0916-018", events)
    if early:
        return early
    if any(event.get("evaluation_window_mature") is False for event in events):
        return _not_mature_result("LX0916-018", events)
    fields = ("report_recorded", "disposition_recorded")
    _, early = _documentation("LX0916-018", events, fields)
    if early:
        return early
    values, early = _bool_documentation("LX0916-018", events, fields)
    if early:
        return early
    assert values is not None
    defects = [key for key, value in values.items() if not value]
    if defects:
        return _result("LX0916-018", "non_compliant", "critical_value_documentation_incomplete", "危急值报告或处理记录不完整。", suggestion="补充危急值报告及处理记录。", anchors=tuple(_event_anchor(event, *defects) for event in events), diagnostics={"failed_facts": defects})
    return _result("LX0916-018", "compliant", "critical_value_documentation_complete", "危急值报告及处理记录完整。", anchors=tuple(_event_anchor(event, *fields) for event in events))


def _evaluate_019(context: Mapping[str, Any]) -> Luxian0916RuleResult:
    rows, early = _event_rows(context, "LX0916-019")
    if early:
        return early
    assert rows is not None
    events, early = _triggered_events("LX0916-019", rows)
    if early:
        return early
    assert events is not None
    _, early = _maturity("LX0916-019", events)
    if early:
        return early
    if any(event.get("evaluation_window_mature") is False for event in events):
        return _not_mature_result("LX0916-019", events)
    fields = ("record_present", "complete")
    _, early = _documentation("LX0916-019", events, fields)
    if early:
        return early
    values, early = _bool_documentation("LX0916-019", events, fields)
    if early:
        return early
    assert values is not None
    defects = [key for key, value in values.items() if not value]
    if defects:
        return _result("LX0916-019", "non_compliant", "important_operation_documentation_incomplete", "重要操作未记录或记录不规范。", suggestion="补记重要操作并完善记录要素。", anchors=tuple(_event_anchor(event, *defects) for event in events), diagnostics={"failed_facts": defects})
    return _result("LX0916-019", "compliant", "important_operation_documentation_complete", "重要操作已记录且记录完整。", anchors=tuple(_event_anchor(event, *fields) for event in events))


def _evaluate_020(context: Mapping[str, Any]) -> Luxian0916RuleResult:
    rows, early = _event_rows(context, "LX0916-020")
    if early:
        return early
    assert rows is not None
    events, early = _triggered_events("LX0916-020", rows)
    if early:
        return early
    assert events is not None
    _, early = _maturity("LX0916-020", events)
    if early:
        return early
    if any(event.get("evaluation_window_mature") is False for event in events):
        return _not_mature_result("LX0916-020", events)
    fields = ("reason_recorded", "basis_recorded")
    _, early = _documentation("LX0916-020", events, fields)
    if early:
        return early
    values, early = _bool_documentation("LX0916-020", events, fields)
    if early:
        return early
    assert values is not None
    defects = [key for key, value in values.items() if not value]
    if defects:
        return _result("LX0916-020", "non_compliant", "diagnosis_change_reason_or_basis_missing", "修正或补充诊断未记录理由和依据。", suggestion="补充修正或补充诊断的理由和诊断依据。", anchors=tuple(_event_anchor(event, *defects) for event in events), diagnostics={"failed_facts": defects})
    return _result("LX0916-020", "compliant", "diagnosis_change_reason_and_basis_present", "修正或补充诊断已记录理由和依据。", anchors=tuple(_event_anchor(event, *fields) for event in events))


_EVALUATORS = {
    "LX0916-015": _evaluate_015,
    "LX0916-016": _evaluate_016,
    "LX0916-017": _evaluate_017,
    "LX0916-018": _evaluate_018,
    "LX0916-019": _evaluate_019,
    "LX0916-020": _evaluate_020,
}


def execute_course_event_rules(
    context: Mapping[str, Any], rule_ids: Sequence[str] | None = None
) -> list[Luxian0916RuleResult]:
    """直接形成事件触发病程规则的客户交付结果。"""

    selected = _RULE_IDS if rule_ids is None else tuple(
        rule_id for rule_id in _RULE_IDS if rule_id in set(rule_ids)
    )
    return [
        replace(
            _EVALUATORS[rule_id](context),
            decision_facts=_decision_facts_from_context(context, rule_id),
        )
        for rule_id in selected
    ]
