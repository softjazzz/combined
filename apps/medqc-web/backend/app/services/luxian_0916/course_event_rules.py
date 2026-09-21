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
    "LX0916-018": ("report_recorded", "disposition_recorded"),
    "LX0916-019": ("record_present", "complete"),
    "LX0916-020": ("reason_recorded", "basis_recorded"),
}
_APPROPRIATENESS_VALUES = frozenset({"reasonable", "unreasonable"})
_STAGE2_FACT_KINDS_BY_RULE = {
    "LX0916-015": ("record_present", "time_recorded", "content_recorded"),
    "LX0916-016": ("analysis_present", "management_present"),
    "LX0916-018": ("report_recorded", "disposition_recorded"),
}
_STAGE2_FACT_FIELDS = frozenset(
    {"fact_kind", "state", "event_id", "source_type", "document_id", "clause_id"}
)
_STAGE2_FACT_STATES = frozenset({"present", "absent", "unknown"})
_STAGE1_EVENT_FIELDS = (
    "event_type",
    "event_id",
    "event_source_type",
    "event_source_id",
    "event_time",
    "related_source_type",
    "related_source_id",
    "event_kind",
    "lifecycle_state",
)


def _controlled_text(value: Any) -> str | None:
    normalized = str(value or "").strip()
    if (
        not normalized
        or len(normalized) > 160
        or "\n" in normalized
        or "\r" in normalized
    ):
        return None
    return normalized


def _controlled_stage2_fact(
    fact: Any, event_id: str | None, fact_kinds: tuple[str, ...]
) -> Mapping[str, Any] | None:
    if not isinstance(fact, Mapping) or set(fact) != _STAGE2_FACT_FIELDS:
        return None
    if (
        fact.get("fact_kind") not in fact_kinds
        or fact.get("state") not in _STAGE2_FACT_STATES
    ):
        return None
    controlled = {
        "fact_kind": _controlled_text(fact.get("fact_kind")),
        "state": _controlled_text(fact.get("state")),
        "event_id": _controlled_text(fact.get("event_id")),
        "source_type": _controlled_text(fact.get("source_type")),
        "document_id": _controlled_text(fact.get("document_id")),
        "clause_id": _controlled_text(fact.get("clause_id")),
    }
    if event_id is None or controlled["event_id"] != event_id:
        return None
    raw_coordinates = tuple(
        fact.get(field) for field in ("source_type", "document_id", "clause_id")
    )
    coordinates = (
        controlled["source_type"],
        controlled["document_id"],
        controlled["clause_id"],
    )
    if controlled["state"] == "present":
        if any(value is None for value in coordinates):
            return None
    elif any(value is not None for value in raw_coordinates):
        return None
    return controlled


def _stage2_event_facts(
    event: Mapping[str, Any], rule_id: str
) -> tuple[tuple[Mapping[str, Any], ...], bool]:
    fact_kinds = _STAGE2_FACT_KINDS_BY_RULE[rule_id]
    raw_facts = event.get("stage2_facts")
    if not isinstance(raw_facts, Sequence) or isinstance(raw_facts, (str, bytes)):
        return (), True
    selected = tuple(
        fact
        for fact in raw_facts
        if isinstance(fact, Mapping) and fact.get("fact_kind") in fact_kinds
    )
    facts = tuple(
        controlled
        for fact in selected
        if (
            controlled := _controlled_stage2_fact(
                fact, _controlled_text(event.get("event_id")), fact_kinds
            )
        )
        is not None
    )
    counts = {
        kind: sum(fact["fact_kind"] == kind for fact in facts) for kind in fact_kinds
    }
    invalid = any(not isinstance(fact, Mapping) for fact in raw_facts)
    return facts, invalid or len(facts) != len(selected) or set(counts.values()) != {1}


def _stage2_decision_events(
    rows: Sequence[Any], rule_id: str
) -> list[Mapping[str, Any]]:
    serialized_events: list[Mapping[str, Any]] = []
    for event in rows:
        if not isinstance(event, Mapping):
            continue
        trigger = event.get("trigger_confirmed")
        snapshot: dict[str, Any] = {
            "trigger_confirmed": trigger if isinstance(trigger, bool) else None
        }
        for field in _STAGE1_EVENT_FIELDS:
            value = _controlled_text(event.get(field))
            if value:
                snapshot[field] = value
        for field in ("related_source_ids", "critical_flags"):
            raw_values = event.get(field)
            if not isinstance(raw_values, Sequence) or isinstance(raw_values, (str, bytes)):
                continue
            values = [
                value
                for raw_value in raw_values
                if (value := _controlled_text(raw_value)) is not None
            ]
            if values:
                snapshot[field] = values
        stage2_states = event.get("stage2_state_by_rule")
        state = (
            stage2_states.get(rule_id) if isinstance(stage2_states, Mapping) else None
        )
        snapshot["stage2_state"] = _controlled_text(state)
        maturity = event.get("evaluation_window_mature")
        snapshot["evaluation_window_mature"] = (
            maturity if isinstance(maturity, bool) else None
        )
        snapshot["stage2_facts"] = list(_stage2_event_facts(event, rule_id)[0])
        serialized_events.append(snapshot)
    return serialized_events


def _decision_facts_from_context(
    context: Mapping[str, Any], rule_id: str
) -> Mapping[str, Any]:
    """持久化规则实际读取的受控事件事实，拒绝带出正文或模型原始输出。"""

    event_key = _EVENT_KEY_BY_RULE[rule_id]
    facts = context.get("event_facts")
    states = context.get("event_source_state_by_rule")
    source_state = states.get(rule_id) if isinstance(states, Mapping) else None
    if source_state == "structured_complete":
        decision_source_state = "available"
    elif source_state == "critical_value_source_complete":
        decision_source_state = "available"
    elif isinstance(source_state, str) and source_state.startswith("structured_trigger_"):
        decision_source_state = source_state
    elif isinstance(source_state, str) and source_state.startswith("critical_value_source_"):
        decision_source_state = source_state
    else:
        decision_source_state = (
            source_state
            if source_state in {"selected", "not_selected", "partial"}
            else "unverified"
        )
    if not isinstance(facts, Mapping) or event_key not in facts:
        return {
            "event_key": event_key,
            "source_state": decision_source_state,
            "events": [],
        }

    rows = facts.get(event_key)
    if not isinstance(rows, Sequence) or isinstance(rows, (str, bytes)):
        return {"event_key": event_key, "source_state": "invalid", "events": []}

    source_state = (
        "available"
        if decision_source_state in {"available", "selected"}
        else decision_source_state
    )
    if rule_id in _STAGE2_FACT_KINDS_BY_RULE:
        return {
            "event_key": event_key,
            "source_state": source_state,
            "events": _stage2_decision_events(rows, rule_id),
        }

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
        for field in (
            "event_source_type", "event_source_id", "related_source_type",
            "related_source_id", "event_time", "event_kind", "lifecycle_state",
        ):
            value = str(event.get(field) or "").strip()
            if value and len(value) <= 160 and "\n" not in value and "\r" not in value:
                snapshot[field] = value
        for field in ("related_source_ids", "critical_flags"):
            raw_values = event.get(field)
            if not isinstance(raw_values, Sequence) or isinstance(raw_values, (str, bytes)):
                continue
            values = [
                str(value).strip()
                for value in raw_values
                if str(value).strip()
                and len(str(value).strip()) <= 160
                and "\n" not in str(value)
                and "\r" not in str(value)
            ]
            if values:
                snapshot[field] = values
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
    states = context.get("event_source_state_by_rule")
    source_state = states.get(rule_id) if isinstance(states, Mapping) else None
    structured_gap = {
        "structured_trigger_source_unavailable": (
            "structured_trigger_source_unavailable",
            "病情变化触发来源读取失败，无法确认是否存在病危/病重医嘱或检验危急值。",
        ),
        "structured_trigger_source_partial": (
            "structured_trigger_source_partial",
            "病情变化触发来源读取被截断，无法确认是否存在全部病危/病重医嘱或检验危急值。",
        ),
        "structured_trigger_source_invalid": (
            "structured_trigger_source_invalid",
            "病情变化触发来源存在关键状态、坐标或关联字段缺失，无法安全确认触发条件。",
        ),
    }
    critical_value_gap = {
        "critical_value_source_unavailable": (
            "critical_value_source_unavailable",
            "危急值检验来源读取失败，无法确认是否存在危急值事件。",
        ),
        "critical_value_source_partial": (
            "critical_value_source_partial",
            "危急值检验来源读取或投影不完整，无法确认是否存在全部危急值事件。",
        ),
        "critical_value_source_invalid": (
            "critical_value_source_invalid",
            "危急值检验来源存在关键状态、坐标或关联字段缺失，无法安全确认触发条件。",
        ),
    }
    if source_state in structured_gap:
        reason_code, findings = structured_gap[source_state]
        return None, _result(
            rule_id,
            "data_quality_gap",
            reason_code,
            findings,
            suggestion="补齐病情变化触发来源后重新质控。",
            diagnostics={"event_key": event_key, "event_source_state": source_state},
        )
    if source_state in critical_value_gap:
        reason_code, findings = critical_value_gap[source_state]
        return None, _result(
            rule_id,
            "data_quality_gap",
            reason_code,
            findings,
            suggestion="补齐危急值检验来源后重新质控。",
            diagnostics={"event_key": event_key, "event_source_state": source_state},
        )
    if not isinstance(facts, Mapping) or event_key not in facts:
        return None, _event_source_gap_result(
            rule_id, event_key=event_key, source_state=source_state
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
    if not rows and source_state not in {
        "selected",
        "structured_complete",
        "critical_value_source_complete",
    }:
        return None, _event_source_gap_result(
            rule_id, event_key=event_key, source_state=source_state
        )
    return tuple(rows), None


def _event_source_gap_result(
    rule_id: str, *, event_key: str, source_state: Any
) -> Luxian0916RuleResult:
    if source_state == "partial":
        return _partial_event_source_result(rule_id)
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
    return _result(
        rule_id,
        "data_quality_gap",
        reason_code,
        findings,
        suggestion=suggestion,
        diagnostics={"event_key": event_key, "event_source_state": source_state},
    )


def _incomplete_event_coverage_result(
    context: Mapping[str, Any], rule_id: str
) -> Luxian0916RuleResult | None:
    states = context.get("event_source_state_by_rule")
    source_state = states.get(rule_id) if isinstance(states, Mapping) else None
    if source_state in {"selected", "critical_value_source_complete"}:
        return None
    return _event_source_gap_result(
        rule_id,
        event_key=_EVENT_KEY_BY_RULE[rule_id],
        source_state=source_state,
    )


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
    anchor: dict[str, Any] = {
        "event_type": str(event.get("event_type") or ""),
        "event_id": str(event.get("event_id") or ""),
        "document_type": str(event.get("source_type") or ""),
        "document_id": str(event.get("document_id") or ""),
        "fields": list(fields),
    }
    for key in (
        "event_source_type", "event_source_id", "related_source_type",
        "related_source_id", "event_time", "event_kind", "lifecycle_state",
    ):
        value = str(event.get(key) or "").strip()
        if value:
            anchor[key] = value
    for key in ("related_source_ids", "critical_flags"):
        raw_values = event.get(key)
        if isinstance(raw_values, Sequence) and not isinstance(raw_values, (str, bytes)):
            values = [str(value).strip() for value in raw_values if str(value).strip()]
            if values:
                anchor[key] = values
    return anchor


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
        "本次仅核对部分事件相关资料，无法确认是否还有其他触发事件或整体记录是否符合要求。",
        suggestion="补齐未纳入、读取失败或截断的事件相关资料后重新质控。",
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


def _stage2_fact_anchor(
    event: Mapping[str, Any], fact: Mapping[str, Any]
) -> Mapping[str, Any]:
    return {
        "event_type": str(event.get("event_type") or ""),
        "event_id": fact["event_id"],
        "fact_kind": fact["fact_kind"],
        "state": fact["state"],
        "document_type": str(fact["source_type"]),
        "document_id": str(fact["document_id"]),
        "clause_id": str(fact["clause_id"]),
    }


def _evaluate_disease_change_stage2(
    context: Mapping[str, Any], rule_id: str
) -> Luxian0916RuleResult:
    rows, early = _event_rows(context, rule_id)
    if early:
        return early
    assert rows is not None
    states = context.get("event_source_state_by_rule")
    partial = isinstance(states, Mapping) and states.get(rule_id) == "partial"
    if partial:
        events = tuple(row for row in rows if row.get("trigger_confirmed") is True)
    else:
        events, early = _triggered_events(rule_id, rows)
        if early:
            return early
    assert events is not None

    event_facts: list[
        tuple[Mapping[str, Any], tuple[Mapping[str, Any], ...], bool]
    ] = []
    defect_facts: list[tuple[Mapping[str, Any], Mapping[str, Any]]] = []
    unresolved_anchors: list[Mapping[str, Any]] = []
    blocking_unresolved = False
    unknown_facts_present = False
    for event in events:
        facts, invalid = _stage2_event_facts(event, rule_id)
        event_facts.append((event, facts, invalid))
        defect_facts.extend(
            (event, fact) for fact in facts if fact["state"] == "absent"
        )
        unknown_facts = tuple(fact for fact in facts if fact["state"] == "unknown")
        unknown_facts_present = unknown_facts_present or bool(unknown_facts)
        unresolved_anchors.extend(
            _event_anchor(event, str(fact["fact_kind"])) for fact in unknown_facts
        )
        stage2_states = event.get("stage2_state_by_rule")
        if (
            not isinstance(stage2_states, Mapping)
            or stage2_states.get(rule_id) != "ready"
            or invalid
        ):
            blocking_unresolved = True

    maturity_values = tuple(event.get("evaluation_window_mature") for event in events)
    maturity_unknown = any(
        value is not True and value is not False for value in maturity_values
    )
    if maturity_unknown:
        blocking_unresolved = True
        defect_facts = []
        unresolved_anchors.extend(
            _event_anchor(event, "evaluation_window_mature")
            for event in events
            if event.get("evaluation_window_mature") is not True
            and event.get("evaluation_window_mature") is not False
        )
    elif any(value is False for value in maturity_values):
        return _not_mature_result(rule_id, events)

    if blocking_unresolved:
        return _result(
            rule_id,
            "data_quality_gap",
            "disease_change_stage2_fact_unavailable",
            "触发事件的病程记录原子事实未完整形成，无法安全判断。",
            suggestion="补齐事件关联病程记录的受控原子事实后重新质控。",
            anchors=tuple(unresolved_anchors),
        )
    if defect_facts:
        failed_facts = list(
            dict.fromkeys(fact["fact_kind"] for _, fact in defect_facts)
        )
        if rule_id == "LX0916-015":
            reason_code = "disease_change_documentation_incomplete"
            findings = "重要病情变化的病程记录缺失或时间、内容不完整。"
            suggestion = "补记重要病情变化及其记录时间和事件内容。"
        else:
            reason_code = "disease_change_analysis_or_management_missing"
            findings = "病情变化未记录独立分析判断或具体处理意见。"
            suggestion = "补充病情变化的独立分析判断和具体处理意见。"
        return _result(
            rule_id,
            "non_compliant",
            reason_code,
            findings,
            suggestion=suggestion,
            anchors=tuple(
                _event_anchor(event, str(fact["fact_kind"]))
                for event, fact in defect_facts
            ),
            diagnostics={"failed_facts": failed_facts},
        )
    if partial:
        return _partial_event_source_result(rule_id)
    if unknown_facts_present:
        return _result(
            rule_id,
            "data_quality_gap",
            "disease_change_stage2_fact_unavailable",
            "触发事件的病程记录原子事实未完整形成，无法安全判断。",
            suggestion="补齐事件关联病程记录的受控原子事实后重新质控。",
            anchors=tuple(unresolved_anchors),
        )

    anchors = tuple(
        _stage2_fact_anchor(event, fact)
        for event, facts, _ in event_facts
        for fact in facts
    )
    if rule_id == "LX0916-015":
        return _result(
            rule_id,
            "compliant",
            "disease_change_documentation_complete",
            "重要病情变化已记录，且时间和事件内容完整。",
            anchors=anchors,
        )
    return _result(
        rule_id,
        "compliant",
        "disease_change_analysis_and_management_present",
        "病情变化已记录独立分析判断和具体处理意见。",
        anchors=anchors,
    )


def _evaluate_015(context: Mapping[str, Any]) -> Luxian0916RuleResult:
    return _evaluate_disease_change_stage2(context, "LX0916-015")


def _evaluate_016(context: Mapping[str, Any]) -> Luxian0916RuleResult:
    return _evaluate_disease_change_stage2(context, "LX0916-016")


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
    if coverage_gap := _incomplete_event_coverage_result(context, "LX0916-017"):
        return coverage_gap
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
    maturity_values = tuple(event.get("evaluation_window_mature") for event in events)
    if any(value is not True and value is not False for value in maturity_values):
        return _result(
            "LX0916-018",
            "data_quality_gap",
            "critical_value_stage2_fact_unavailable",
            "危急值事件的评价时间窗或病程原子事实未完整形成，无法安全判断。",
            suggestion="补齐危急值事件关联病程的受控原子事实后重新质控。",
            anchors=tuple(
                _event_anchor(event, "evaluation_window_mature")
                for event in events
                if event.get("evaluation_window_mature") is not True
                and event.get("evaluation_window_mature") is not False
            ),
        )
    if any(value is False for value in maturity_values):
        return _not_mature_result("LX0916-018", events)

    ready_facts: list[tuple[Mapping[str, Any], Mapping[str, Any]]] = []
    defect_facts: list[tuple[Mapping[str, Any], Mapping[str, Any]]] = []
    unresolved_anchors: list[Mapping[str, Any]] = []
    blocking_unresolved = False
    for event in events:
        facts, invalid = _stage2_event_facts(event, "LX0916-018")
        stage2_states = event.get("stage2_state_by_rule")
        stage2_ready = (
            isinstance(stage2_states, Mapping)
            and stage2_states.get("LX0916-018") == "ready"
            and not invalid
        )
        if not stage2_ready:
            blocking_unresolved = True
            unresolved_anchors.append(_event_anchor(event, "stage2_facts"))
            continue
        ready_facts.extend((event, fact) for fact in facts)
        defect_facts.extend(
            (event, fact) for fact in facts if fact["state"] == "absent"
        )
        unknown_facts = tuple(fact for fact in facts if fact["state"] == "unknown")
        if unknown_facts:
            blocking_unresolved = True
            unresolved_anchors.extend(
                _event_anchor(event, str(fact["fact_kind"]))
                for fact in unknown_facts
            )

    if defect_facts:
        failed_facts = list(
            dict.fromkeys(fact["fact_kind"] for _, fact in defect_facts)
        )
        return _result(
            "LX0916-018",
            "non_compliant",
            "critical_value_documentation_incomplete",
            "危急值报告或处理记录不完整。",
            suggestion="补充危急值报告及处理记录。",
            anchors=tuple(
                _event_anchor(event, str(fact["fact_kind"]))
                for event, fact in defect_facts
            ),
            diagnostics={"failed_facts": failed_facts},
        )
    if blocking_unresolved:
        return _result(
            "LX0916-018",
            "data_quality_gap",
            "critical_value_stage2_fact_unavailable",
            "危急值事件的病程原子事实未完整形成，无法安全判断。",
            suggestion="补齐危急值事件关联病程的受控原子事实后重新质控。",
            anchors=tuple(unresolved_anchors),
        )
    if coverage_gap := _incomplete_event_coverage_result(context, "LX0916-018"):
        return coverage_gap
    return _result(
        "LX0916-018",
        "compliant",
        "critical_value_documentation_complete",
        "危急值报告及处理记录完整。",
        anchors=tuple(
            _stage2_fact_anchor(event, fact)
            for event, fact in ready_facts
            if fact["state"] == "present"
        ),
    )


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
    if coverage_gap := _incomplete_event_coverage_result(context, "LX0916-019"):
        return coverage_gap
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
    if coverage_gap := _incomplete_event_coverage_result(context, "LX0916-020"):
        return coverage_gap
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

    selected = (
        _RULE_IDS
        if rule_ids is None
        else tuple(rule_id for rule_id in _RULE_IDS if rule_id in set(rule_ids))
    )
    return [
        replace(
            _EVALUATORS[rule_id](context),
            decision_facts=_decision_facts_from_context(context, rule_id),
        )
        for rule_id in selected
    ]
