from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, Mapping

from .luxian_0609_evidence_formatter import format_luxian_0609_evidence
from .luxian_0609_result_schema import (
    CANONICAL_RESULT_STATUSES,
    apply_luxian_0609_result_schema,
)
from .luxian_0609.canonical_result_finalizer import (
    finalizer_owns_executor_customer_display_facts,
    finalizer_rejects_invalid_public_executor_customer_display_facts,
    finalizer_requires_public_fact_ref_evidence,
    finalizer_validates_missing_executor_customer_display_facts,
    finalize_luxian_0609_canonical_result,
    finalize_luxian_0609_executor_customer_display_facts,
    validate_luxian_0609_executor_customer_display_facts,
)
from .luxian_0609.customer_evidence_enrichment import (
    enrich_customer_evidence,
    project_legacy_source_level_evidence,
    project_selected_document_evidence,
)
from .luxian_0609.decision_reducer import ReducedRuleDecision
from .luxian_0609_trigger_gate import (
    Luxian0609GateDecision,
    TRIGGER_ABSENT,
    TRIGGER_DATA_GAP,
    decision_to_result,
)

if TYPE_CHECKING:
    from .luxian_0609.customer_renderer import SafeTraceSink as DecisionTraceSink


_STATUS_PRIORITY = {
    "non_compliant": 50,
    "ai_suggested_non_compliant": 48,
    "data_gap": 45,
    "uncertain": 40,
    "ai_suggested_compliant": 25,
    "compliant": 20,
    "not_applicable": 10,
    "not_executed": 5,
    "technical_error": 60,
}
logger = logging.getLogger(__name__)


class Luxian0609CustomerDisplayFactsError(ValueError):
    """保留失败规则编号，但错误正文继续使用固定客户安全文本。"""

    def __init__(self, rule_id: str) -> None:
        super().__init__("invalid customer display facts")
        self.rule_id = _norm_id(rule_id)

_SENSITIVE_KEYS = {
    "raw_response",
    "raw_output",
    "llm_raw_output",
    "prompt",
    "embedding",
    "medical_text",
    "documents",
    "bundle",
    "record_content",
    "internal_data",
}
def _norm_id(value: Any) -> str:
    return str(value or "").strip().upper()


def _confidence(value: Any) -> float:
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def _status(item: dict[str, Any]) -> str:
    status = str(item.get("status") or "").strip().lower()
    if status in CANONICAL_RESULT_STATUSES:
        return status
    if status in {"technical_error_internal", "error"}:
        return "technical_error"
    if status in {"skipped", "unsupported"}:
        return "not_executed"
    return "compliant" if item.get("is_compliant") is True else "non_compliant"


def _strip_sensitive(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            key: _strip_sensitive(item)
            for key, item in value.items()
            if str(key).lower() not in _SENSITIVE_KEYS
        }
    if isinstance(value, list):
        return [_strip_sensitive(item) for item in value]
    return value


def _select_best_result(
    *,
    mapped_results: list[dict[str, Any]],
    primary_rule_id: str,
) -> tuple[dict[str, Any] | None, str]:
    if not mapped_results:
        return None, "missing_mapped_result"

    primary = [item for item in mapped_results if _norm_id(item.get("rule_id") or item.get("rule_code")) == primary_rule_id]
    for target_status, source in (
        ("technical_error", "mapped_technical_error"),
        ("non_compliant", "mapped_non_compliant"),
        ("data_gap", "mapped_data_gap"),
        ("uncertain", "mapped_uncertain"),
        ("not_executed", "mapped_not_executed"),
    ):
        candidates = [item for item in mapped_results if _status(item) == target_status]
        if candidates:
            candidates.sort(key=lambda item: (_confidence(item.get("confidence")), _norm_id(item.get("rule_id"))), reverse=True)
            primary_match = [item for item in primary if _status(item) == target_status]
            if primary_match:
                return primary_match[0], f"primary_{target_status}"
            return candidates[0], source

    if primary:
        return primary[0], "primary_result"
    return mapped_results[0], "first_mapped_result"


def _source_evidence_snapshot(item: dict[str, Any]) -> Any:
    evidence_items = item.get("evidence_items")
    if isinstance(evidence_items, list) and evidence_items:
        return _strip_sensitive(evidence_items[:8])
    evidence = str(item.get("evidence") or "").strip()
    if evidence:
        return evidence[:1200]
    return ""


def _source_execution_snapshot(item: dict[str, Any]) -> dict[str, Any]:
    metadata = dict(item.get("metadata") or {})
    return _strip_sensitive(
        {
            "source_rule_id": _norm_id(item.get("rule_id") or item.get("rule_code")),
            "source_status": _status(item),
            "source_conclusion": str(
                item.get("findings")
                or item.get("conclusion")
                or item.get("summary")
                or ""
            ).strip(),
            "source_evidence": _source_evidence_snapshot(item),
            "confidence": _confidence(item.get("confidence")),
            "executor_type": str(metadata.get("executor_type") or item.get("executor_type") or ""),
            "model_version": str(metadata.get("model_version") or item.get("model_version") or ""),
            "final_decision_source": str(
                metadata.get("final_decision_source")
                or item.get("final_decision_source")
                or ""
            ),
            "postprocess_reason": str(
                metadata.get("postprocess_reason")
                or item.get("postprocess_reason")
                or ""
            ),
        }
    )


def _trigger_decision_snapshot(decision: Luxian0609GateDecision | None) -> dict[str, Any]:
    if decision is None:
        return {}
    return {
        "rule_id": _norm_id(decision.rule_id),
        "status": decision.status,
        "reason": decision.reason,
        "data_gap_fields": list(decision.data_gap_fields),
        "matched_keywords": list(decision.matched_keywords),
    }


def _build_diagnostic_trace(
    *,
    wrapper_id: str,
    selected: dict[str, Any],
    mapped_results: list[dict[str, Any]],
    source: str,
    gate_decision: Luxian0609GateDecision | None,
    primary_rule_id: str,
    mapped_rule_ids: list[str],
) -> dict[str, Any]:
    selected_source_rule_id = _norm_id(selected.get("rule_id") or selected.get("rule_code"))
    source_results = [_source_execution_snapshot(item) for item in mapped_results if isinstance(item, dict)]
    if not source_results and source not in {"trigger_gate", "missing_mapped_result"}:
        source_results = [_source_execution_snapshot(selected)]
    selected_metadata = dict(selected.get("metadata") or {})
    aggregation_reason = (
        f"{source}: selected {selected_source_rule_id or wrapper_id} "
        f"from {len(mapped_results)} mapped execution result(s)"
    )
    postprocess_reason = str(
        selected_metadata.get("postprocess_reason")
        or selected.get("postprocess_reason")
        or selected_metadata.get("customer_display_guard")
        or ""
    )
    original_status = str(selected_metadata.get("internal_original_status") or "").strip().lower()
    customer_status = _status(selected)
    return _strip_sensitive(
        {
            "customer_rule_id": wrapper_id,
            "source_rule_id": selected_source_rule_id or wrapper_id,
            "source_status": original_status or customer_status,
            "customer_status": customer_status,
            "source_conclusion": str(
                selected.get("findings")
                or selected.get("conclusion")
                or selected.get("summary")
                or ""
            ).strip(),
            "source_evidence": _source_evidence_snapshot(selected),
            "trigger_decision": _trigger_decision_snapshot(gate_decision),
            "aggregation_reason": aggregation_reason,
            "postprocess_reason": postprocess_reason,
            "primary_execution_rule_id": primary_rule_id,
            "mapped_rule_ids": mapped_rule_ids,
            "selected_execution_rule_id": selected_source_rule_id,
            "source_execution_results": source_results,
        }
    )



def _copy_customer_fields(
    *,
    wrapper: dict[str, Any],
    selected: dict[str, Any],
    mapped_results: list[dict[str, Any]],
    source: str,
    gate_decision: Luxian0609GateDecision | None,
) -> dict[str, Any]:
    wrapper_id = _norm_id(wrapper.get("rule_id") or wrapper.get("rule_code"))
    primary_rule_id = _norm_id(wrapper.get("primary_execution_rule_id"))
    mapped_rule_ids = [_norm_id(item) for item in list(wrapper.get("mapped_rule_ids") or []) if _norm_id(item)]
    status = _status(selected)
    if status not in {
        "compliant",
        "non_compliant",
        "ai_suggested_non_compliant",
        "ai_suggested_compliant",
        "not_applicable",
        "data_gap",
        "uncertain",
        "not_executed",
        "technical_error",
    }:
        status = "technical_error"
    selected_metadata_raw = selected.get("metadata")
    selected_metadata_mapping = (
        selected_metadata_raw if isinstance(selected_metadata_raw, Mapping) else {}
    )
    raw_display_facts = selected.get("customer_display_facts")
    if raw_display_facts is None:
        raw_display_facts = selected_metadata_mapping.get("customer_display_facts")
    metadata = _strip_sensitive(dict(selected.get("metadata") or {}))
    if gate_decision is not None:
        metadata.update(gate_decision.to_metadata())
    metadata.update(
        {
            "mapped_rule_ids": mapped_rule_ids,
            "primary_execution_rule_id": primary_rule_id,
            "aggregation_source": source,
            "selected_execution_rule_id": _norm_id(selected.get("rule_id") or selected.get("rule_code")),
            "mapped_result_count": len(mapped_results),
            "customer_rule_id": wrapper_id,
        }
    )
    diagnostic_trace = _build_diagnostic_trace(
        wrapper_id=wrapper_id,
        selected=selected,
        mapped_results=mapped_results,
        source=source,
        gate_decision=gate_decision,
        primary_rule_id=primary_rule_id,
        mapped_rule_ids=mapped_rule_ids,
    )
    metadata["diagnostic_trace"] = diagnostic_trace
    metadata["source_execution_results"] = diagnostic_trace.get("source_execution_results") or []
    metadata["trigger_decision"] = diagnostic_trace.get("trigger_decision") or {}
    metadata["postprocess_reason"] = diagnostic_trace.get("postprocess_reason") or ""
    result = {
        **_strip_sensitive(selected),
        "rule_id": wrapper_id,
        "rule_code": wrapper_id,
        "rule_name": str(wrapper.get("name") or wrapper.get("rule_name") or selected.get("rule_name") or wrapper_id),
        "status": status,
        "is_compliant": status in {"compliant", "not_applicable", "ai_suggested_compliant"},
        "metadata": metadata,
        "diagnostic_trace": diagnostic_trace,
        "source_rule_id": diagnostic_trace.get("source_rule_id") or "",
        "source_status": diagnostic_trace.get("source_status") or "",
        "source_conclusion": diagnostic_trace.get("source_conclusion") or "",
        "source_evidence": diagnostic_trace.get("source_evidence") or "",
        "trigger_decision": diagnostic_trace.get("trigger_decision") or {},
        "postprocess_reason": diagnostic_trace.get("postprocess_reason") or "",
    }
    if finalizer_validates_missing_executor_customer_display_facts(wrapper_id):
        result, _handled = finalize_luxian_0609_executor_customer_display_facts(
            result=result,
            raw_facts=raw_display_facts,
            preserve_legacy_exception=True,
        )
    return result


def safe_luxian_0609_customer_display_facts(
    *, rule_id: str, raw: Any
) -> dict[str, Any] | None:
    """旧原生分支只保留尚未迁移到通用子结论合同的受控展示事实。"""
    delegated_facts = validate_luxian_0609_executor_customer_display_facts(
        rule_id=rule_id,
        raw=raw,
    )
    if delegated_facts is not NotImplemented:
        return delegated_facts
    return None

def _copy_native_customer_fields(
    *, wrapper: dict[str, Any], selected: dict[str, Any]
) -> dict[str, Any]:
    """原生结果不携带旧映射诊断，并保留程序/模型执行类型。"""
    wrapper_id = _norm_id(wrapper.get("rule_id") or wrapper.get("rule_code"))
    finalizer_owns_facts = finalizer_owns_executor_customer_display_facts(wrapper_id)
    def reject_invalid_display_facts() -> None:
        raise Luxian0609CustomerDisplayFactsError(wrapper_id)

    status = _status(selected)
    if status not in {"compliant", "non_compliant", "not_applicable", "data_gap", "uncertain", "technical_error"}:
        status = "technical_error"
    selected_metadata_raw = selected.get("metadata")
    selected_metadata_mapping = (
        selected_metadata_raw if isinstance(selected_metadata_raw, Mapping) else {}
    )
    top_level_display_facts = selected.get("customer_display_facts")
    metadata_display_facts = selected_metadata_mapping.get("customer_display_facts")
    supplied_display_facts = tuple(
        candidate
        for candidate in (top_level_display_facts, metadata_display_facts)
        if candidate is not None
    )

    def safe_executor_display_facts(raw: Any) -> tuple[dict[str, Any] | None, bool]:
        validated_facts = validate_luxian_0609_executor_customer_display_facts(
            rule_id=wrapper_id,
            raw=raw,
        )
        return (
            safe_luxian_0609_customer_display_facts(
                rule_id=wrapper_id,
                raw=raw,
            )
            if validated_facts is NotImplemented
            else validated_facts,
            validated_facts is not NotImplemented,
        )

    supplied_fact_contracts = tuple(
        safe_executor_display_facts(supplied_facts)
        for supplied_facts in supplied_display_facts
    )
    supplied_safe_facts = tuple(item[0] for item in supplied_fact_contracts)
    supplied_contracts_handled = tuple(item[1] for item in supplied_fact_contracts)
    contract_failure = False
    for supplied_facts, supplied_safe_facts_item, contract_handled in zip(
        supplied_display_facts, supplied_safe_facts, supplied_contracts_handled
    ):
        if supplied_safe_facts_item is not None:
            continue
        if (
            contract_handled
            and finalizer_owns_facts
            and not finalizer_rejects_invalid_public_executor_customer_display_facts(
                wrapper_id
            )
        ):
            contract_failure = True
            continue
        reject_invalid_display_facts()
    if len(supplied_display_facts) == 2:
        if all(item is not None for item in supplied_safe_facts):
            if supplied_safe_facts[0] != supplied_safe_facts[1]:
                if (
                    finalizer_owns_facts
                    and any(supplied_contracts_handled)
                    and not finalizer_rejects_invalid_public_executor_customer_display_facts(
                        wrapper_id
                    )
                ):
                    contract_failure = True
                else:
                    reject_invalid_display_facts()
        else:
            if finalizer_owns_facts and any(supplied_contracts_handled):
                contract_failure = True
            else:
                reject_invalid_display_facts()
    raw_display_facts = (
        top_level_display_facts
        if top_level_display_facts is not None
        else metadata_display_facts
    )
    safe_display_facts = (
        supplied_safe_facts[0] if supplied_safe_facts else None
    )
    selected_metadata = _strip_sensitive(dict(selected_metadata_mapping))
    # 原生结果可能同时带有旧链写入的顶层 executor_type 和当前执行器
    # 元数据。客户结果必须以当前元数据为准，并把同一个值投影到顶层，
    # 避免出现“实际程序执行、页面仍显示 llm”的字段漂移。
    selected_executor_type = str(
        selected_metadata.get("executor_type")
        or selected.get("executor_type")
        or ""
    ).strip().lower()
    metadata = {
        key: selected_metadata.get(key)
        for key in (
            "execution_source",
            "executor_type",
            "finding_kind",
            "source_state",
            "reason_code",
            "comparable_document_count",
            "maximum_similarity",
            "similarity_threshold",
            "best_match_source_types",
            "diagnostic_semantic_snapshot",
        )
        if key in selected_metadata
    }

    metadata["execution_source"] = "lx0609_native"
    # 原生执行结果没有携带执行器字段时，默认按原生程序结果处理；
    # 这样后续 canonical schema 不会再次退回客户规则目录中的 llm 默认值。
    metadata["executor_type"] = selected_executor_type or "program"
    metadata["aggregation_source"] = (
        "native_llm"
        if str(metadata.get("executor_type") or "").strip().lower() == "llm"
        else "native_programmatic"
    )
    metadata["customer_rule_id"] = wrapper_id
    result = {
        **_strip_sensitive(selected),
        "rule_id": wrapper_id,
        "rule_code": wrapper_id,
        "rule_name": str(wrapper.get("name") or wrapper.get("rule_name") or wrapper_id),
        "status": status,
        "is_compliant": status in {"compliant", "not_applicable"},
        "metadata": metadata,
        "executor_type": selected_executor_type or "program",
        "diagnostic_trace": {},
        "source_rule_id": "",
        "source_status": str(metadata.get("source_state") or ""),
        "source_conclusion": "",
        "source_evidence": "",
        "trigger_decision": {},
        "postprocess_reason": str(metadata.get("reason_code") or ""),
    }
    result.pop("customer_display_facts", None)
    if safe_display_facts:
        result["customer_display_facts"] = safe_display_facts
    if (
        (finalizer_owns_facts and raw_display_facts is not None)
        or finalizer_validates_missing_executor_customer_display_facts(wrapper_id)
    ):
        result, _handled = finalize_luxian_0609_executor_customer_display_facts(
            result=result,
            raw_facts=raw_display_facts,
            contract_failure=contract_failure,
            preserve_legacy_exception=True,
        )
    return result


def _index_reduced_decisions(
    *,
    wrapper_rules: list[dict[str, Any]],
    reduced_decisions: tuple[ReducedRuleDecision, ...],
) -> dict[str, ReducedRuleDecision]:
    if type(reduced_decisions) is not tuple or any(
        not isinstance(item, ReducedRuleDecision) for item in reduced_decisions
    ):
        raise TypeError("reduced_decisions must be a tuple of ReducedRuleDecision")
    wrapper_ids = tuple(
        _norm_id(item.get("rule_id") or item.get("rule_code"))
        for item in wrapper_rules
        if _norm_id(item.get("rule_id") or item.get("rule_code"))
    )
    if reduced_decisions and len(wrapper_ids) != len(set(wrapper_ids)):
        raise ValueError("duplicate customer wrapper scope")
    actual_ids = tuple(item.rule_id for item in reduced_decisions)
    if len(actual_ids) != len(set(actual_ids)):
        raise ValueError("duplicate reduced decision")
    if any(rule_id not in wrapper_ids for rule_id in actual_ids):
        raise ValueError("reduced decision is outside customer scope")
    actual_id_set = set(actual_ids)
    expected_order = tuple(rule_id for rule_id in wrapper_ids if rule_id in actual_id_set)
    if actual_ids != expected_order:
        raise ValueError("reduced decision order mismatch")
    return {item.rule_id: item for item in reduced_decisions}


def aggregate_luxian_0609_results(
    *,
    wrapper_rules: list[dict[str, Any]],
    execution_results: list[dict[str, Any]],
    gate_decisions: dict[str, Luxian0609GateDecision] | None = None,
    format_evidence: bool = True,
    audit_context: dict[str, Any] | None = None,
    reduced_decisions: tuple[ReducedRuleDecision, ...] = (),
    customer_display_facts: tuple[tuple[str, Mapping[str, Any]], ...] = (),
    decision_trace_sink: DecisionTraceSink | None = None,
) -> list[dict[str, Any]]:
    # 延迟加载避免聚合器导入时触发 luxian_0609 包的公开 re-export，
    # 从而与 customer_rule_package 形成循环依赖。
    from .luxian_0609.customer_renderer import (
        customer_finding_from_controlled_facts,
        render_luxian_0609_customer_result,
    )

    reduced_by_rule = _index_reduced_decisions(
        wrapper_rules=wrapper_rules,
        reduced_decisions=reduced_decisions,
    )
    display_facts_by_rule: dict[str, dict[str, Any]] = {}
    raw_executor_display_facts_by_rule: dict[str, Mapping[str, Any]] = {}
    wrapper_rule_ids = {
        _norm_id(item.get("rule_id") or item.get("rule_code"))
        for item in wrapper_rules
    }
    native_direct_rule_ids = {
        _norm_id(item.get("rule_id") or item.get("rule_code"))
        for item in execution_results
        if str((item.get("metadata") or {}).get("execution_source") or "")
        == "lx0609_native"
    }
    for rule_id, facts in customer_display_facts:
        if (
            rule_id in display_facts_by_rule
            or rule_id not in wrapper_rule_ids
            or not isinstance(facts, Mapping)
        ):
            raise ValueError("invalid customer display facts scope")
        validated_facts = validate_luxian_0609_executor_customer_display_facts(
            rule_id=rule_id,
            raw=facts,
        )
        safe_facts = validated_facts
        if validated_facts is NotImplemented:
            safe_facts = safe_luxian_0609_customer_display_facts(
                rule_id=rule_id,
                raw=facts,
            )
        finalizer_owns_facts = finalizer_owns_executor_customer_display_facts(rule_id)
        if finalizer_owns_facts:
            raw_executor_display_facts_by_rule[rule_id] = facts
        if safe_facts is not None:
            display_facts_by_rule[rule_id] = safe_facts
        else:
            # 独立传入的事实不是执行器结果的延迟合同。若没有 Typed 决策或
            # native 直接结果能交给 Finalizer，不能静默丢弃非法客户事实。
            if (
                not finalizer_owns_facts
                or finalizer_rejects_invalid_public_executor_customer_display_facts(
                    rule_id
                )
                or (
                    rule_id not in reduced_by_rule
                    and rule_id not in native_direct_rule_ids
                )
            ):
                raise Luxian0609CustomerDisplayFactsError(rule_id)
    result_by_rule: dict[str, list[dict[str, Any]]] = {}
    for item in execution_results:
        key = _norm_id(item.get("rule_id") or item.get("rule_code"))
        if key in reduced_by_rule:
            continue
        if key:
            result_by_rule.setdefault(key, []).append(dict(item))

    customer_results: list[dict[str, Any]] = []
    decisions = gate_decisions or {}
    for wrapper in wrapper_rules:
        wrapper_id = _norm_id(wrapper.get("rule_id") or wrapper.get("rule_code"))
        if not wrapper_id:
            continue
        finalizer_owns_facts = finalizer_owns_executor_customer_display_facts(
            wrapper_id
        )
        reduced = reduced_by_rule.get(wrapper_id)
        if reduced is not None:
            result = render_luxian_0609_customer_result(
                decision=reduced,
                safe_customer_display_facts=display_facts_by_rule.get(wrapper_id),
                trace_sink=decision_trace_sink,
            )
            if wrapper_id in display_facts_by_rule:
                result["customer_display_facts"] = display_facts_by_rule[wrapper_id]
                precise_findings = customer_finding_from_controlled_facts(
                    rule_id=wrapper_id,
                    facts=display_facts_by_rule[wrapper_id],
                )
                if precise_findings:
                    result["findings"] = precise_findings
            raw_executor_facts = raw_executor_display_facts_by_rule.get(wrapper_id)
            if (
                raw_executor_facts is not None
                or finalizer_validates_missing_executor_customer_display_facts(
                    wrapper_id
                )
            ):
                result, handled = finalize_luxian_0609_executor_customer_display_facts(
                    result=result,
                    raw_facts=raw_executor_facts,
                    preserve_legacy_exception=True,
                )
                if handled and "customer_display_facts" not in result:
                    result = finalize_luxian_0609_canonical_result(result)
                    customer_results.append(result)
                    continue
            selected_document_evidence = project_selected_document_evidence(
                decision=reduced,
                evidence_snapshot=(audit_context or {}).get("evidence_snapshot"),
                evidence_materials=(audit_context or {}).get("evidence_materials"),
            )
            if selected_document_evidence is not None:
                # 已有明确逐行选择时，公共投影是唯一证据所有者。不得先让旧的
                # 来源级反查或 display facts 补入文书，再以合并结果掩盖猜测。
                customer_evidence = selected_document_evidence
            elif finalizer_requires_public_fact_ref_evidence(wrapper_id):
                # 已迁出事实合同的规则只能由公共逐行 fact_refs 投影证据；没有
                # 精确坐标时保持无客户证据，不能回退到旧来源级反查。
                customer_evidence = []
            else:
                # 只有尚未迁移的旧合同才允许保留历史反查路径。
                decision_evidence = project_legacy_source_level_evidence(
                    decision=reduced,
                    evidence_snapshot=(audit_context or {}).get(
                        "evidence_snapshot"
                    ),
                    evidence_materials=(audit_context or {}).get(
                        "evidence_materials"
                    ),
                )
                customer_evidence = decision_evidence
            customer_evidence = enrich_customer_evidence(
                customer_evidence,
                evidence_materials=(audit_context or {}).get("evidence_materials"),
            )
            if customer_evidence:
                result["customer_evidence"] = customer_evidence
            result = finalize_luxian_0609_canonical_result(result)
            customer_results.append(result)
            continue
        decision = decisions.get(wrapper_id)
        gate_result = None
        if decision and decision.status == TRIGGER_ABSENT:
            gate_result = decision_to_result(wrapper, decision)
            if gate_result is not None:
                result = _copy_customer_fields(
                    wrapper=wrapper,
                    selected=gate_result,
                    mapped_results=[],
                    source="trigger_gate",
                    gate_decision=decision,
                )
                if format_evidence:
                    result = format_luxian_0609_evidence(
                        result=result,
                        wrapper_rule=wrapper,
                        gate_decision=decision,
                    )
                result = apply_luxian_0609_result_schema(
                    result=result,
                    wrapper_rule=wrapper,
                    gate_decision=decision,
                    audit_context=audit_context,
                )
                result = finalize_luxian_0609_canonical_result(result)
                customer_results.append(result)
                continue

        direct_results = list(result_by_rule.get(wrapper_id) or [])
        if direct_results:
            direct_results.sort(
                # 同一客户规则同时存在原生结果和兼容映射结果时，原生结果是
                # 唯一可用的客户结论来源。不能让遗留 LLM 的置信度覆盖原生
                # 受控事实（例如 018 的字数、诊断指向两个子结论）。
                key=lambda item: (
                    str((item.get("metadata") or {}).get("execution_source") or "")
                    == "lx0609_native",
                    _confidence(item.get("confidence")),
                    _norm_id(item.get("rule_id")),
                ),
                reverse=True,
            )
            selected = direct_results[0]
            if str((selected.get("metadata") or {}).get("execution_source") or "") == "lx0609_native":
                result = _copy_native_customer_fields(
                    wrapper=wrapper,
                    selected=selected,
                )
                raw_executor_facts = raw_executor_display_facts_by_rule.get(
                    wrapper_id
                )
                if raw_executor_facts is not None:
                    result, _handled = (
                        finalize_luxian_0609_executor_customer_display_facts(
                            result=result,
                            raw_facts=raw_executor_facts,
                            preserve_legacy_exception=True,
                        )
                    )
                if str(result.get("status") or "") != "technical_error":
                    facts_for_render = (
                        display_facts_by_rule.get(wrapper_id)
                        or result.get("customer_display_facts")
                    )
                    if isinstance(facts_for_render, Mapping):
                        result["customer_display_facts"] = dict(facts_for_render)
                        precise_findings = customer_finding_from_controlled_facts(
                            rule_id=wrapper_id,
                            facts=facts_for_render,
                        )
                        if precise_findings:
                            result["findings"] = precise_findings
                else:
                    # Finalizer 已因合同或状态冲突将本条安全降级。此处只能继续
                    # 装配，不能把循环前缓存的展示事实或证据重新写回。
                    result.pop("customer_display_facts", None)
                    result.pop("customer_evidence", None)
                enriched_customer_evidence = enrich_customer_evidence(
                    list(result.get("customer_evidence") or []),
                    evidence_materials=(audit_context or {}).get(
                        "evidence_materials"
                    ),
                )
                if enriched_customer_evidence:
                    result["customer_evidence"] = enriched_customer_evidence
                else:
                    result.pop("customer_evidence", None)
                native_audit_context = {
                    key: value
                    for key, value in dict(audit_context or {}).items()
                    if key not in {"visit_id", "patient_id", "evidence_payload"}
                }
                result = apply_luxian_0609_result_schema(
                    result=result,
                    wrapper_rule=wrapper,
                    gate_decision=decision,
                    audit_context=native_audit_context,
                )
                native_audit = dict(result.get("audit") or {})
                for internal_key in (
                    "visit_id",
                    "patient_id",
                    "model_name",
                    "prompt_version",
                    "error_message",
                ):
                    native_audit.pop(internal_key, None)
                result["audit"] = native_audit
                result = finalize_luxian_0609_canonical_result(result)
                customer_results.append(result)
                continue
            source = "customer_programmatic"
            result = _copy_customer_fields(
                wrapper=wrapper,
                selected=selected,
                mapped_results=direct_results,
                source=source,
                gate_decision=decision,
            )
            if format_evidence:
                result = format_luxian_0609_evidence(
                    result=result,
                    wrapper_rule=wrapper,
                    gate_decision=decision,
                )
            result = apply_luxian_0609_result_schema(
                result=result,
                wrapper_rule=wrapper,
                gate_decision=decision,
                audit_context=audit_context,
            )
            result = finalize_luxian_0609_canonical_result(result)
            customer_results.append(result)
            continue
        if decision and decision.status in {TRIGGER_ABSENT, TRIGGER_DATA_GAP}:
            gate_result = decision_to_result(wrapper, decision)
        if gate_result is not None:
            source = "trigger_gate"
            mapped_results: list[dict[str, Any]] = []
            result = _copy_customer_fields(
                wrapper=wrapper,
                selected=gate_result,
                mapped_results=mapped_results,
                source=source,
                gate_decision=decision,
            )
        else:
            mapped_rule_ids = [_norm_id(item) for item in list(wrapper.get("mapped_rule_ids") or []) if _norm_id(item)]
            mapped_results = []
            for rule_id in mapped_rule_ids:
                mapped_results.extend(result_by_rule.get(rule_id) or [])
            selected, source = _select_best_result(
                mapped_results=mapped_results,
                primary_rule_id=_norm_id(wrapper.get("primary_execution_rule_id")),
            )
            if selected is None:
                selected = {
                    "rule_id": wrapper_id,
                    "rule_name": str(wrapper.get("name") or wrapper_id),
                    "status": "technical_error",
                    "reason_code": "missing_mapped_result",
                    "is_compliant": None,
                    "findings": "当前自动判定未形成可靠结论，建议质控员确认。",
                    "evidence": "",
                    "suggestion": "请质控员结合相关病历文书和诊疗记录确认；必要时重新执行质控。",
                    "confidence": 0.0,
                    "metadata": {"technical_error_internal": True},
                }
            result = _copy_customer_fields(
                wrapper=wrapper,
                selected=selected,
                mapped_results=mapped_results,
                source=source,
                gate_decision=decision,
            )
        if format_evidence:
            result = format_luxian_0609_evidence(
                result=result,
                wrapper_rule=wrapper,
                gate_decision=decision,
            )
        result = apply_luxian_0609_result_schema(
            result=result,
            wrapper_rule=wrapper,
            gate_decision=decision,
            audit_context=audit_context,
        )
        result = finalize_luxian_0609_canonical_result(result)
        customer_results.append(result)
    return customer_results


def summarize_luxian_0609_results(results: list[dict[str, Any]]) -> dict[str, Any]:
    status_counts: dict[str, int] = {status: 0 for status in CANONICAL_RESULT_STATUSES}
    for item in results:
        status = _status(item)
        status_counts[status] = int(status_counts.get(status) or 0) + 1
    total = len(results)
    not_applicable = int(status_counts.get("not_applicable") or 0)
    data_gap = int(status_counts.get("data_gap") or 0)
    not_executed = int(status_counts.get("not_executed") or 0)
    technical_error = int(status_counts.get("technical_error") or 0)
    compliance_denominator = max(0, total - not_applicable - data_gap - not_executed - technical_error)
    compliant = int(status_counts.get("compliant") or 0)
    ai_suggested_non_compliant = int(status_counts.get("ai_suggested_non_compliant") or 0)
    ai_suggested_compliant = int(status_counts.get("ai_suggested_compliant") or 0)
    compliance_rate = round((compliant / compliance_denominator * 100.0), 2) if compliance_denominator else 100.0
    return {
        "customer_rule_count": total,
        "status_counts": status_counts,
        "defect_count": int(status_counts.get("non_compliant") or 0),
        "ai_suggested_non_compliant_count": ai_suggested_non_compliant,
        "ai_suggested_compliant_count": ai_suggested_compliant,
        "not_applicable_count": not_applicable,
        "data_gap_count": data_gap,
        "uncertain_count": int(status_counts.get("uncertain") or 0),
        "not_executed_count": not_executed,
        "technical_error_count": technical_error,
        "compliant_count": compliant + ai_suggested_compliant,
        "compliance_denominator": compliance_denominator,
        "compliance_rate": compliance_rate,
    }
