from __future__ import annotations

import logging
import re
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
    project_selected_document_evidence,
)
from .luxian_0609.decision_reducer import ReducedRuleDecision
from .luxian_0609.surgery_gate_result_mapping import (
    legacy_surgery_gate_customer_evidence,
)
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
_SAFE_SOURCE_TYPE = re.compile(r"^[a-z][a-z0-9_]{0,63}$")
# 旧兼容投影仍统一读取该表。已迁出的规则族不得在此增加规则专属来源选择。
_EXACT_CUSTOMER_EVIDENCE_SOURCES_BY_RULE: dict[str, frozenset[str]] = {}


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


def _has_any(text: str, *needles: str) -> bool:
    return any(needle and needle in text for needle in needles)


def _implant_absence_language(text: str) -> bool:
    return _has_any(
        text,
        "未提及植入物",
        "未见植入物",
        "无植入物",
        "未发现植入物",
        "无法判断是否存在植入物",
    )


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

def _controlled_customer_findings(
    *, rule_id: str, facts: Mapping[str, Any] | None
) -> str:
    """统一调用后端客户渲染器解释白名单事实，前端不得重算业务语义。"""

    from .luxian_0609.customer_renderer import customer_finding_from_controlled_facts

    return customer_finding_from_controlled_facts(rule_id=rule_id, facts=facts)


def _customer_evidence_from_display_facts(
    *, rule_id: str, raw: Any
) -> list[dict[str, str]]:
    """将已验证的内部文书 ID 交给客户投影层做不可逆引用。

    此处不输出 ID 给客户；`custom_qc_workspace_service` 会统一将其 HMAC
    为 `src_…`，与文书列表中的安全引用一一对应。
    """

    if not isinstance(raw, Mapping):
        return []
    verified_facts = validate_luxian_0609_executor_customer_display_facts(
        rule_id=rule_id,
        raw=raw,
    )
    if verified_facts is not NotImplemented:
        legacy_evidence = legacy_surgery_gate_customer_evidence(
            rule_id=rule_id,
            raw=raw,
            safe_facts=verified_facts,
        )
        return [] if legacy_evidence is None else legacy_evidence
    # 先复用展示事实白名单验证业务形态；内部 ID 只在此函数中转成
    # customer_evidence，绝不能进入 customer_display_facts。
    if safe_luxian_0609_customer_display_facts(rule_id=rule_id, raw=raw) is None:
        return []

    return []




def _valid_customer_evidence_document_id(value: Any) -> str:
    """仅允许内部已验证的文书 ID 进入后续安全签名环节。"""

    candidate = str(value or "").strip()
    return (
        candidate
        if candidate
        and len(candidate) <= 256
        and "\n" not in candidate
        and "\r" not in candidate
        else ""
    )



def _customer_evidence_from_reduced_decision(
    *,
    decision: ReducedRuleDecision,
    evidence_snapshot: Any,
    evidence_materials: Any,
) -> list[dict[str, str]]:
    """由 RuleDecision 的事实引用反查已存在的原始文书。

    所有原生规则复用这一条路径：只接受 decision 已引用的 FactV2；若事实未携带
    单行 ID，仅在同一冻结材料中该来源唯一对应一份文书时补回。这里不猜标题、
    不以正文相似度选文书；真正不可逆的 ``src_…`` 引用仍由客户安全投影统一生成。
    """

    facts = getattr(evidence_snapshot, "facts", ())
    observations = getattr(evidence_snapshot, "observations", ())
    if not decision.fact_refs:
        return []
    referenced = set(decision.fact_refs)
    exact_source_keys = _EXACT_CUSTOMER_EVIDENCE_SOURCES_BY_RULE.get(
        str(decision.rule_id or "").strip().upper()
    )
    rows: list[dict[str, str]] = []
    seen_document_ids: set[str] = set()
    for fact in facts if isinstance(facts, tuple) else ():
        fact_id = str(getattr(fact, "fact_id", "") or "")
        source_snapshot_hash = str(
            getattr(fact, "source_snapshot_hash", "") or ""
        ).removeprefix("sha256:")
        if fact_id not in referenced and source_snapshot_hash not in referenced:
            continue
        document_id = _valid_customer_evidence_document_id(
            getattr(fact, "source_document_id", "")
        )
        source_type = str(getattr(fact, "source_key", "") or "").strip().lower()
        # 部分确定性事实只绑定来源快照，不携带单行文书 ID。仅当本次冻结
        # 材料恰好一行且该行带有效 ID 时，才可安全补回当前 Bundle 的真实 ID；
        # 多行（即使仅一个非空 ID 或复用同一 ID）时保持无证据，避免猜测行。
        if (
            not document_id
            and evidence_materials is not None
            and _SAFE_SOURCE_TYPE.fullmatch(source_type)
        ):
            try:
                material_rows = tuple(evidence_materials.rows(source_type))
            except Exception:
                material_rows = ()
            if len(material_rows) == 1 and isinstance(material_rows[0], Mapping):
                document_id = _valid_customer_evidence_document_id(
                    material_rows[0].get("document_id") or material_rows[0].get("id")
                )
        if (
            not document_id
            or document_id in seen_document_ids
            or not _SAFE_SOURCE_TYPE.fullmatch(source_type)
            or (exact_source_keys is not None and source_type not in exact_source_keys)
        ):
            continue
        seen_document_ids.add(document_id)
        rows.append(
            {
                "source_type": source_type,
                "source_document_id": document_id,
            }
        )
        if len(rows) >= 8:
            return rows

    # 一部分纯 Python 决策直接绑定来源快照而非 FactV2。例如 018 同时依赖
    # 入院记录和初步诊断；这时仅当该来源在同一 Evidence Session 内唯一对应一份
    # 原始文书，才可补出引用。多文书来源保持无引用，禁止猜测哪一份支持结论。
    source_keys: set[str] = set()
    if isinstance(observations, tuple):
        for observation in observations:
            snapshot_ref = str(
                getattr(observation, "snapshot_ref", "") or ""
            ).removeprefix("sha256:")
            if snapshot_ref in referenced:
                source_keys.add(
                    str(getattr(observation, "source_key", "") or "").strip().lower()
                )
    for source_key in sorted(source_keys):
        if (
            not _SAFE_SOURCE_TYPE.fullmatch(source_key)
            or (exact_source_keys is not None and source_key not in exact_source_keys)
        ):
            continue
        try:
            material_rows = tuple(evidence_materials.rows(source_key))
        except Exception:
            continue
        if len(material_rows) != 1 or not isinstance(material_rows[0], Mapping):
            continue
        document_id = _valid_customer_evidence_document_id(
            material_rows[0].get("document_id") or material_rows[0].get("id")
        )
        if not document_id or document_id in seen_document_ids:
            continue
        seen_document_ids.add(document_id)
        rows.append(
            {"source_type": source_key, "source_document_id": document_id}
        )
        if len(rows) >= 8:
            break
    return rows


def _merge_customer_evidence(
    *groups: list[dict[str, str]],
) -> list[dict[str, str]]:
    """显式规则证据优先，通用 fact 反查只补足缺失引用。"""

    merged: list[dict[str, str]] = []
    seen: set[str] = set()
    for group in groups:
        for item in group:
            document_id = _valid_customer_evidence_document_id(
                item.get("source_document_id")
            )
            source_type = str(item.get("source_type") or "").strip().lower()
            if (
                not document_id
                or document_id in seen
                or not _SAFE_SOURCE_TYPE.fullmatch(source_type)
            ):
                continue
            seen.add(document_id)
            merged.append(
                {"source_type": source_type, "source_document_id": document_id}
            )
            if len(merged) >= 8:
                return merged
    return merged


def _copy_native_customer_fields(
    *, wrapper: dict[str, Any], selected: dict[str, Any], evidence_materials: Any = None
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
    customer_evidence = _customer_evidence_from_display_facts(
        rule_id=wrapper_id,
        raw=raw_display_facts,
    )
    if customer_evidence:
        result["customer_evidence"] = customer_evidence
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
    from .luxian_0609.customer_renderer import render_luxian_0609_customer_result

    reduced_by_rule = _index_reduced_decisions(
        wrapper_rules=wrapper_rules,
        reduced_decisions=reduced_decisions,
    )
    display_facts_by_rule: dict[str, dict[str, Any]] = {}
    raw_executor_display_facts_by_rule: dict[str, Mapping[str, Any]] = {}
    customer_evidence_by_rule: dict[str, list[dict[str, str]]] = {}
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
        customer_evidence = _customer_evidence_from_display_facts(
            rule_id=rule_id,
            raw=facts,
        )
        if customer_evidence:
            customer_evidence_by_rule[rule_id] = customer_evidence
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
                precise_findings = _controlled_customer_findings(
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
                decision_evidence = _customer_evidence_from_reduced_decision(
                    decision=reduced,
                    evidence_snapshot=(audit_context or {}).get(
                        "evidence_snapshot"
                    ),
                    evidence_materials=(audit_context or {}).get(
                        "evidence_materials"
                    ),
                )
                customer_evidence = _merge_customer_evidence(
                    customer_evidence_by_rule.get(wrapper_id, []),
                    decision_evidence,
                )
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
                    evidence_materials=(audit_context or {}).get(
                        "evidence_materials"
                    ),
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
                        precise_findings = _controlled_customer_findings(
                            rule_id=wrapper_id,
                            facts=facts_for_render,
                        )
                        if precise_findings:
                            result["findings"] = precise_findings
                    if wrapper_id in customer_evidence_by_rule:
                        result["customer_evidence"] = customer_evidence_by_rule[
                            wrapper_id
                        ]
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
