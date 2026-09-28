from __future__ import annotations

from enum import Enum
from typing import Any, Mapping

from .visual_condition_fact_builder import (
    VisualFact,
    VisualFactSourceUnavailable,
    build_visual_condition_facts,
)
from .visual_condition_service import (
    VisualConditionInvalid,
    normalize_visual_condition,
)


class TruthValue(str, Enum):
    TRUE = "true"
    FALSE = "false"
    UNKNOWN = "unknown"


def _combine(operator: str, values: list[TruthValue]) -> TruthValue:
    if operator == "all":
        if TruthValue.FALSE in values:
            return TruthValue.FALSE
        if TruthValue.UNKNOWN in values:
            return TruthValue.UNKNOWN
        return TruthValue.TRUE
    if TruthValue.TRUE in values:
        return TruthValue.TRUE
    if TruthValue.UNKNOWN in values:
        return TruthValue.UNKNOWN
    return TruthValue.FALSE


def _exists(fact: VisualFact | None, operator: str) -> TruthValue:
    if fact is None or not fact.known:
        return TruthValue.UNKNOWN
    present = fact.value is not None
    return TruthValue.TRUE if present == (operator == "exists") else TruthValue.FALSE


def _evaluate_condition(
    condition: Mapping[str, Any],
    facts: Mapping[str, VisualFact],
) -> tuple[TruthValue, dict[str, Any]]:
    kind = condition["kind"]
    operator = condition["operator"]
    trace: dict[str, Any] = {
        "condition_id": condition["id"],
        "kind": kind,
        "operator": operator,
    }
    if kind == "field":
        fact = facts.get(str(condition["fact_key"]))
        trace["fact_key"] = condition["fact_key"]
        if operator in {"exists", "not_exists"}:
            truth = _exists(fact, operator)
            trace.update({"truth": truth.value, "actual": fact.value if fact and fact.known else None})
            return truth, trace
        if fact is None or not fact.known:
            trace["truth"] = TruthValue.UNKNOWN.value
            return TruthValue.UNKNOWN, trace
        expected = condition.get("value")
        if operator == "eq":
            matched = fact.value == expected
        elif operator == "ne":
            matched = fact.value != expected
        elif operator == "in":
            matched = fact.value in expected
        else:
            matched = fact.value not in expected
        truth = TruthValue.TRUE if matched else TruthValue.FALSE
        trace.update({"truth": truth.value, "actual": fact.value, "expected": expected})
        return truth, trace

    if kind == "document_presence":
        fact = facts.get(f"document.{condition['document_type']}.exists")
        trace["document_type"] = condition["document_type"]
        if fact is None or not fact.known:
            trace["truth"] = TruthValue.UNKNOWN.value
            return TruthValue.UNKNOWN, trace
        present = fact.value is True
        matched = present if operator == "exists" else not present
        truth = TruthValue.TRUE if matched else TruthValue.FALSE
        trace.update({"truth": truth.value, "actual": present})
        return truth, trace

    start = facts.get(str(condition["start_fact"]))
    end = facts.get(str(condition["end_fact"]))
    if start is None or end is None or not start.known or not end.known:
        trace.update(
            {
                "truth": TruthValue.UNKNOWN.value,
                "start_fact": condition["start_fact"],
                "end_fact": condition["end_fact"],
            }
        )
        return TruthValue.UNKNOWN, trace
    seconds = (end.value - start.value).total_seconds()
    threshold = condition["threshold"]
    multiplier = {"minutes": 60, "hours": 3600, "days": 86400}[threshold["unit"]]
    expected = threshold["value"] * multiplier
    matched = {
        "lt": seconds < expected,
        "lte": seconds <= expected,
        "gt": seconds > expected,
        "gte": seconds >= expected,
    }[operator]
    truth = TruthValue.TRUE if matched else TruthValue.FALSE
    trace.update(
        {
            "truth": truth.value,
            "start_fact": condition["start_fact"],
            "end_fact": condition["end_fact"],
            "actual_seconds": seconds,
            "threshold": dict(threshold),
        }
    )
    return truth, trace


class VisualConditionExecutor:
    def can_execute(self, rule: Mapping[str, Any]) -> bool:
        check_logic = rule.get("check_logic")
        return isinstance(check_logic, Mapping) and "visual_condition" in check_logic

    def evaluate(
        self,
        *,
        rule: Mapping[str, Any],
        medical_record: Mapping[str, Any],
        meta: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        rule_id = str(rule.get("rule_id") or rule.get("rule_code") or "").strip()
        check_logic = rule.get("check_logic")
        try:
            if not isinstance(check_logic, Mapping):
                raise VisualConditionInvalid("check_logic 必须是对象")
            config = normalize_visual_condition(check_logic.get("visual_condition"))
        except VisualConditionInvalid as exc:
            return self._result(
                rule=rule,
                rule_id=rule_id,
                status="technical_error",
                is_compliant=False,
                findings="可视化条件配置无效，本次未执行。",
                evidence="配置校验失败。",
                truth=None,
                meta=meta,
                reason=str(exc),
            )

        required_fact_keys: set[str] = set()
        for group in config["groups"]:
            for condition in group["conditions"]:
                if condition["kind"] == "field":
                    required_fact_keys.add(condition["fact_key"])
                elif condition["kind"] == "document_presence":
                    required_fact_keys.add(f"document.{condition['document_type']}.exists")
                else:
                    required_fact_keys.update((condition["start_fact"], condition["end_fact"]))
        try:
            facts = build_visual_condition_facts(
                medical_record,
                required_fact_keys=required_fact_keys,
            )
        except VisualFactSourceUnavailable as exc:
            return self._result(
                rule=rule,
                rule_id=rule_id,
                status="technical_error",
                is_compliant=False,
                findings="可信结构化事实读取失败，本次未形成质控结论。",
                evidence="结构化事实来源不可用。",
                truth=None,
                meta=meta,
                reason=str(exc),
            )
        group_values: list[TruthValue] = []
        condition_trace: list[dict[str, Any]] = []
        for group in config["groups"]:
            evaluated = [_evaluate_condition(condition, facts) for condition in group["conditions"]]
            group_truth = _combine(group["operator"], [item[0] for item in evaluated])
            group_values.append(group_truth)
            condition_trace.append(
                {
                    "group_id": group["id"],
                    "operator": group["operator"],
                    "truth": group_truth.value,
                    "conditions": [item[1] for item in evaluated],
                }
            )
        truth = _combine(config["root_operator"], group_values)
        decisive = [
            condition
            for group in condition_trace
            for condition in group["conditions"]
            if condition["truth"] == truth.value
        ]
        decisive_ids = ", ".join(item["condition_id"] for item in decisive[:10]) or "无"
        if truth is TruthValue.UNKNOWN:
            return self._result(
                rule=rule,
                rule_id=rule_id,
                status="data_gap",
                is_compliant=False,
                findings="可信结构化事实不足，无法完成条件判定。",
                evidence=f"决定性未知条件: {decisive_ids}；未将未知按不命中处理。",
                truth=truth,
                meta=meta,
                condition_trace=condition_trace,
            )
        if truth is TruthValue.TRUE:
            return self._result(
                rule=rule,
                rule_id=rule_id,
                status="non_compliant",
                is_compliant=False,
                findings="已满足配置的缺陷触发条件。",
                evidence=f"缺陷触发条件: {decisive_ids}。",
                truth=truth,
                meta=meta,
                condition_trace=condition_trace,
            )
        return self._result(
            rule=rule,
            rule_id=rule_id,
            status="compliant",
            is_compliant=True,
            findings="未满足配置的缺陷触发条件。",
            evidence=f"未触发条件: {decisive_ids}。",
            truth=truth,
            meta=meta,
            condition_trace=condition_trace,
        )

    @staticmethod
    def _result(
        *,
        rule: Mapping[str, Any],
        rule_id: str,
        status: str,
        is_compliant: bool,
        findings: str,
        evidence: str,
        truth: TruthValue | None,
        meta: Mapping[str, Any] | None,
        reason: str = "",
        condition_trace: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        metadata = dict(meta or {})
        metadata.update(
            {
                "executor_type": "program",
                "visual_condition_schema": "visual-condition-v1",
                "visual_condition_truth": truth.value if truth else "invalid",
                "tokens_used": 0,
                "prompt_tokens": 0,
                "completion_tokens": 0,
                "api_time": 0.0,
            }
        )
        if reason:
            metadata["visual_condition_error"] = reason
        if condition_trace is not None:
            metadata["visual_condition_trace"] = condition_trace
        return {
            "rule_id": rule_id,
            "rule_code": rule_id,
            "rule_name": str(rule.get("name") or ""),
            "status": status,
            "is_compliant": is_compliant,
            "issues": (
                [{"description": findings, "evidence": evidence}]
                if status == "non_compliant"
                else []
            ),
            "findings": findings,
            "evidence": evidence,
            "suggestion": "请核对结构化事实与规则配置。" if not is_compliant else "",
            "confidence": 1.0 if status in {"compliant", "non_compliant"} else 0.0,
            "metadata": metadata,
        }
