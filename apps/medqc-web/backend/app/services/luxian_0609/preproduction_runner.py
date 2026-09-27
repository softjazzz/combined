"""LX0609 全规则只读准生产旁路入口。

该入口只编排独立规则包，不调用四川旧服务、路由、任务或持久化 API。
调用方必须显式提供客户规则范围和冻结评价日；返回对象只包含客户结果与
聚合运行指标，不返回病历正文、三坐标、提示词或内部证据对象。
"""

from __future__ import annotations

from collections import Counter
from datetime import date
import hashlib
import json
import math
import re
from time import perf_counter
from typing import Any, Callable, Iterable, Mapping, Sequence

from .customer_rule_package import LUXIAN_0609_RULE_SET_KEY
from .execution import (
    aggregate_luxian_0609_orchestrated_results,
    prepare_luxian_0609_execution,
)
from .execution_contract import FamilyUsageAttribution
from .rule_contracts import load_luxian_0609_rule_contracts
from .rule_decision_settings import build_full_rule_decision_settings


PREPRODUCTION_RUNNER_SCHEMA_VERSION = "lx0609-preproduction-runner-v1"
EVIDENCE_ATTESTATION_VERSION = "lx0609-evidence-attestation-v1"

_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_VERSION_RE = re.compile(r"^[a-z0-9][a-z0-9._-]{0,63}$")
_REASON_CODE_RE = re.compile(r"^[a-z0-9][a-z0-9._-]{0,127}$")
_OBSERVED_STATES = frozenset(
    {
        "compliant",
        "non_compliant",
        "not_applicable",
        "data_gap",
        "evaluation_unknown",
        "technical_error",
    }
)
EvidenceAttestationSink = Callable[[Sequence[Mapping[str, str]]], None]

_SCALAR_RESULT_FIELDS = (
    "rule_id",
    "rule_code",
    "rule_name",
    "status",
    "is_compliant",
    "confidence",
    "defect_level",
    "qc_point_id",
    "rule_set_key",
    "rule_set_version",
    "rule_version",
    "version",
    "schema_version",
    "executor_type",
    "result_status",
    "source_table",
    "source_document",
    "source_field",
    "decision_summary",
    "review_status",
)
_PUBLIC_RESULT_FIELDS = (
    "issues",
    "findings",
    "evidence",
    "suggestion",
    "trigger",
    "dependencies",
    "missing_sources",
    "evidence_items",
    "decision",
    "review",
    "audit",
)
_METADATA_FIELDS = (
    "execution_source",
    "executor_type",
    "finding_kind",
    "source_state",
    "reason_code",
    "aggregation_source",
    "customer_rule_id",
    "comparable_document_count",
    "maximum_similarity",
    "similarity_threshold",
    "best_match_source_types",
)
_PRIVATE_KEY_PARTS = (
    "institute_id",
    "patient_id",
    "visit_id",
    "source_schema",
    "medical_text",
    "record_content",
    "primary_document_text",
    "supporting_documents",
    "programmatic_timeline",
    "timeline_facts",
    "evidence_payload",
    "source_coordinates",
    "fact_ref",
    "snapshot",
    "prompt",
    "raw_response",
    "llm_raw_output",
    "job_id",
    "model_name",
    "prompt_version",
    "error_message",
    "documents",
    "bundle",
)
_PRIVATE_VALUE_KEY_PARTS = (
    "institute_id",
    "patient_id",
    "visit_id",
    "medical_text",
    "record_content",
    "content",
    "text_preview",
    "evidence_text",
    "prompt",
    "raw_response",
    "llm_raw_output",
)
_PUBLIC_DURATION_KEYS = frozenset(
    {
        "elapsed_ms",
        "wall_time_ms",
        "api_time",
        "total_api_time",
    }
)
_PUBLIC_DATETIME_EXACT_KEYS = frozenset(
    {
        "record_time",
        "executed_at",
        "created_at",
        "updated_at",
        "occurred_at",
    }
)
_PUBLIC_DATETIME_SUFFIXES = ("_time", "_date", "_datetime", "_timestamp")
_MIN_PRIVATE_FRAGMENT_CHARS = 12


def _catalog_rule_ids() -> tuple[str, ...]:
    return tuple(item.rule_id for item in load_luxian_0609_rule_contracts())


def _validate_selected_rule_ids(values: Iterable[str]) -> tuple[str, ...]:
    normalized = tuple(str(value or "").strip().upper() for value in values)
    if not normalized or any(not value for value in normalized):
        raise ValueError("selected LX0609 rule scope is required")
    if len(normalized) != len(set(normalized)):
        raise ValueError("duplicate LX0609 customer rule id")
    catalog = _catalog_rule_ids()
    catalog_set = set(catalog)
    if any(rule_id not in catalog_set for rule_id in normalized):
        raise ValueError("invalid LX0609 customer rule id")
    expected_order = tuple(rule_id for rule_id in catalog if rule_id in set(normalized))
    if normalized != expected_order:
        raise ValueError("LX0609 customer rule order mismatch")
    if len(normalized) == len(catalog) and normalized != catalog:
        raise ValueError("full LX0609 run must use catalog order")
    return normalized


def _validate_evaluation_as_of_date(value: str) -> str:
    normalized = str(value or "").strip()
    try:
        parsed = date.fromisoformat(normalized)
    except ValueError as exc:
        raise ValueError("evaluation_as_of_date must be ISO date") from exc
    if parsed.isoformat() != normalized:
        raise ValueError("evaluation_as_of_date must be ISO date")
    return normalized


def _collect_private_terms(value: Any, *, key: str = "") -> set[str]:
    terms: set[str] = set()
    normalized_key = str(key or "").strip().lower()
    if isinstance(value, Mapping):
        for child_key, child_value in value.items():
            terms.update(_collect_private_terms(child_value, key=str(child_key)))
        return terms
    if isinstance(value, (list, tuple)):
        for item in value:
            terms.update(_collect_private_terms(item, key=key))
        return terms
    if any(part in normalized_key for part in _PRIVATE_VALUE_KEY_PARTS):
        text = str(value or "").strip()
        if len(text) >= 4:
            terms.add(text)
    return terms


def _safe_string(value: Any, *, private_terms: set[str]) -> str:
    text = str(value or "")
    candidate = text.strip()
    for raw_term in private_terms:
        term = raw_term.strip()
        if not term:
            continue
        # 坐标或完整正文即使被包裹在客户文案中，也必须整体脱敏。
        if term in candidate:
            return "[redacted]"
        if len(candidate) < _MIN_PRIVATE_FRAGMENT_CHARS:
            continue
        # evidence quote 可能只携带正文前缀或中间片段；逐窗口检查避免
        # 通过添加固定前后缀绕过完全相等比较。
        if candidate in term:
            return "[redacted]"
        if len(term) < _MIN_PRIVATE_FRAGMENT_CHARS:
            continue
        for start in range(len(candidate) - _MIN_PRIVATE_FRAGMENT_CHARS + 1):
            fragment = candidate[start : start + _MIN_PRIVATE_FRAGMENT_CHARS]
            if fragment in term:
                return "[redacted]"
    return text


def _is_public_datetime_field(key: str, value: Any) -> bool:
    """公开旁路不得返回原始日期/时间字段，纯数值性能指标例外。"""
    normalized_key = str(key or "").strip().lower()
    if normalized_key in _PUBLIC_DURATION_KEYS and isinstance(value, (int, float)):
        return False
    return (
        normalized_key in _PUBLIC_DATETIME_EXACT_KEYS
        or normalized_key.endswith(_PUBLIC_DATETIME_SUFFIXES)
    )


def _sanitize_metadata(value: Any, *, private_terms: set[str]) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        return {}
    safe: dict[str, Any] = {}
    for key in _METADATA_FIELDS:
        if key not in value:
            continue
        item = value[key]
        if isinstance(item, str):
            safe[key] = _safe_string(item, private_terms=private_terms)
        elif isinstance(item, (bool, int, float)) or item is None:
            safe[key] = item
        elif isinstance(item, (list, tuple)):
            safe[key] = [
                _safe_string(entry, private_terms=private_terms)
                for entry in item
                if isinstance(entry, (str, int, float, bool))
            ]
    return safe


def _sanitize_public_value(value: Any, *, private_terms: set[str]) -> Any:
    if isinstance(value, Mapping):
        safe: dict[str, Any] = {}
        for raw_key, item in value.items():
            key = str(raw_key or "")
            normalized_key = key.strip().lower()
            if any(part in normalized_key for part in _PRIVATE_KEY_PARTS):
                continue
            if _is_public_datetime_field(key, item):
                continue
            safe[key] = _sanitize_public_value(item, private_terms=private_terms)
        return safe
    if isinstance(value, (list, tuple)):
        return [
            _sanitize_public_value(item, private_terms=private_terms)
            for item in value
        ]
    if isinstance(value, str):
        return _safe_string(value, private_terms=private_terms)
    if isinstance(value, (bool, int, float)) or value is None:
        return value
    return _safe_string(value, private_terms=private_terms)


def _sanitize_customer_result(
    value: Mapping[str, Any],
    *,
    private_terms: set[str],
) -> dict[str, Any]:
    safe: dict[str, Any] = {}
    for key in _SCALAR_RESULT_FIELDS:
        if key not in value:
            continue
        item = value[key]
        if isinstance(item, str):
            safe[key] = _safe_string(item, private_terms=private_terms)
        elif isinstance(item, (bool, int, float)) or item is None:
            safe[key] = item
    for key in _PUBLIC_RESULT_FIELDS:
        if key in value:
            safe[key] = _sanitize_public_value(
                value[key],
                private_terms=private_terms,
            )
    safe["metadata"] = _sanitize_metadata(
        value.get("metadata"),
        private_terms=private_terms,
    )
    return safe


def _contract_maturity() -> dict[str, int]:
    contracts = load_luxian_0609_rule_contracts()
    typed_contract_rule_ids = {
        item.rule_id for item in contracts if item.contract_version != "v1"
    }
    typed_source_rule_ids = {
        item.rule_id
        for item in contracts
        if item.source_contract_state == "typed_shadow_v1"
    }
    return {
        "rule_decision_count": len(typed_contract_rule_ids),
        "typed_shadow_adapter_count": len(
            typed_source_rule_ids - typed_contract_rule_ids
        ),
        "legacy_projection_count": sum(
            item.source_contract_state == "legacy_projection_v1"
            for item in contracts
        ),
    }


def _technical_results(
    rule_ids: tuple[str, ...], *, reason_code: str
) -> list[dict[str, Any]]:
    return [
        {
            "rule_id": rule_id,
            "rule_code": rule_id,
            "rule_name": rule_id,
            "status": "technical_error",
            "is_compliant": False,
            "findings": "本次准生产旁路执行未形成可靠结果。",
            "suggestion": "请稍后重试或回退旧引擎。",
            "metadata": {
                "execution_source": "lx0609_preproduction",
                "reason_code": reason_code,
                "customer_rule_id": rule_id,
            },
        }
        for rule_id in rule_ids
    ]


class _UsageAccountingError(ValueError):
    def __init__(self, *, observed_metrics: Mapping[str, Any]) -> None:
        super().__init__("usage_accounting_mismatch")
        self.observed_metrics = dict(observed_metrics)


def _metric_vector(
    *,
    llm_call_count: Any,
    prompt_tokens: Any,
    completion_tokens: Any,
    total_tokens: Any,
    api_time_seconds: Any,
) -> dict[str, Any] | None:
    integer_values = (
        llm_call_count,
        prompt_tokens,
        completion_tokens,
        total_tokens,
    )
    if any(
        not isinstance(value, int) or isinstance(value, bool) or value < 0
        for value in integer_values
    ):
        return None
    if total_tokens != prompt_tokens + completion_tokens:
        return None
    if (
        isinstance(api_time_seconds, bool)
        or not isinstance(api_time_seconds, (int, float))
        or not math.isfinite(api_time_seconds)
        or api_time_seconds < 0
    ):
        return None
    return {
        "llm_call_count": llm_call_count,
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "total_tokens": total_tokens,
        "api_time_seconds": round(float(api_time_seconds), 6),
    }


def _observed_usage_metrics(context: Any, orchestrated: Mapping[str, Any]) -> dict[str, Any]:
    context_metrics = _metric_vector(
        llm_call_count=getattr(context, "native_llm_call_count", 0),
        prompt_tokens=getattr(context, "native_prompt_tokens", 0),
        completion_tokens=getattr(context, "native_completion_tokens", 0),
        total_tokens=getattr(context, "native_total_tokens", 0),
        api_time_seconds=getattr(context, "native_api_time", 0.0),
    )
    orchestrated_metrics = _metric_vector(
        llm_call_count=getattr(context, "native_llm_call_count", 0),
        prompt_tokens=orchestrated.get("total_prompt_tokens", 0),
        completion_tokens=orchestrated.get("total_completion_tokens", 0),
        total_tokens=orchestrated.get("total_tokens", 0),
        api_time_seconds=orchestrated.get("total_api_time", 0.0),
    )
    candidates = [
        item for item in (context_metrics, orchestrated_metrics) if item is not None
    ]
    if not candidates:
        return {
            "llm_call_count": 0,
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "total_tokens": 0,
            "api_time_seconds": 0.0,
        }
    return max(
        candidates,
        key=lambda item: (item["total_tokens"], item["llm_call_count"]),
    )


def _validate_usage_accounting(
    *,
    context: Any,
    orchestrated: Mapping[str, Any],
) -> tuple[dict[str, Any], ...]:
    attributions = getattr(context, "native_usage_attributions", ())
    if type(attributions) is not tuple or any(
        not isinstance(item, FamilyUsageAttribution) for item in attributions
    ):
        raise _UsageAccountingError(
            observed_metrics=_observed_usage_metrics(context, orchestrated)
        )
    executor_keys = tuple(item.executor_key for item in attributions)
    covered_rule_ids = tuple(
        rule_id
        for item in attributions
        for rule_id in item.covered_customer_rule_ids
    )
    if (
        len(executor_keys) != len(set(executor_keys))
        or len(covered_rule_ids) != len(set(covered_rule_ids))
    ):
        raise _UsageAccountingError(
            observed_metrics=_observed_usage_metrics(context, orchestrated)
        )
    derived = _metric_vector(
        llm_call_count=sum(item.llm_call_count for item in attributions),
        prompt_tokens=sum(item.prompt_tokens for item in attributions),
        completion_tokens=sum(item.completion_tokens for item in attributions),
        total_tokens=sum(item.total_tokens for item in attributions),
        api_time_seconds=sum(item.latency_ms for item in attributions) / 1000.0,
    )
    context_metrics = _metric_vector(
        llm_call_count=getattr(context, "native_llm_call_count", 0),
        prompt_tokens=getattr(context, "native_prompt_tokens", 0),
        completion_tokens=getattr(context, "native_completion_tokens", 0),
        total_tokens=getattr(context, "native_total_tokens", 0),
        api_time_seconds=getattr(context, "native_api_time", 0.0),
    )
    orchestrated_metrics = _metric_vector(
        llm_call_count=getattr(context, "native_llm_call_count", 0),
        prompt_tokens=orchestrated.get("total_prompt_tokens", 0),
        completion_tokens=orchestrated.get("total_completion_tokens", 0),
        total_tokens=orchestrated.get("total_tokens", 0),
        api_time_seconds=orchestrated.get("total_api_time", 0.0),
    )
    if (
        derived is None
        or context_metrics is None
        or orchestrated_metrics is None
        or derived != context_metrics
        or derived != orchestrated_metrics
    ):
        raise _UsageAccountingError(
            observed_metrics=_observed_usage_metrics(context, orchestrated)
        )
    return tuple(item.to_safe_dict() for item in attributions)


def _canonical_digest(value: Any) -> str:
    material = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(material.encode("utf-8")).hexdigest()


def _build_evidence_attestations(
    *,
    selected_rule_ids: tuple[str, ...],
    trace_rows: Sequence[Mapping[str, Any]],
    raw_results: Sequence[Mapping[str, Any]],
    context: Any,
) -> tuple[dict[str, str], ...]:
    """把内部决策事实链压缩为逐规则opaque摘要，不返回内部材料。"""

    snapshot_pairs = tuple(getattr(context, "evidence_snapshot_rule_refs", ()) or ())
    if (
        len(snapshot_pairs) != len(selected_rule_ids)
        or tuple(str(item[0] or "").strip().upper() for item in snapshot_pairs)
        != selected_rule_ids
    ):
        raise ValueError("invalid evidence snapshot rule refs")
    snapshot_by_rule: dict[str, str] = {}
    for raw_rule_id, raw_snapshot_hash in snapshot_pairs:
        rule_id = str(raw_rule_id or "").strip().upper()
        snapshot_hash = str(raw_snapshot_hash or "").strip().lower()
        if rule_id in snapshot_by_rule or not _SHA256_RE.fullmatch(snapshot_hash):
            raise ValueError("invalid evidence snapshot rule refs")
        snapshot_by_rule[rule_id] = snapshot_hash

    if (
        len(raw_results) != len(selected_rule_ids)
        or tuple(
            str(item.get("rule_id") or "").strip().upper()
            for item in raw_results
            if isinstance(item, Mapping)
        )
        != selected_rule_ids
    ):
        raise ValueError("invalid attested result scope")
    result_by_rule = {
        str(item.get("rule_id") or "").strip().upper(): item
        for item in raw_results
    }

    traced_by_rule: dict[str, tuple[str, tuple[str, ...], str, str, str]] = {}
    expected_traced_ids = selected_rule_ids
    for trace in trace_rows:
        if not isinstance(trace, Mapping):
            raise ValueError("invalid decision trace")
        rule_id = str(trace.get("rule_id") or "").strip().upper()
        snapshot_hash = str(trace.get("snapshot_hash") or "").strip().lower()
        evaluator_version = str(trace.get("evaluator_version") or "").strip().lower()
        observed_state = str(trace.get("final_state") or "").strip().lower()
        reason_code = str(trace.get("reason_code") or "").strip().lower()
        raw_fact_refs = trace.get("fact_refs")
        if not isinstance(raw_fact_refs, (list, tuple)):
            raise ValueError("invalid decision trace")
        fact_refs = tuple(sorted(str(item or "").strip().lower() for item in raw_fact_refs))
        public_result_state = str(
            result_by_rule[rule_id].get("status") or ""
        ).strip().lower()
        if public_result_state == "uncertain":
            public_result_state = "evaluation_unknown"
        if (
            rule_id not in expected_traced_ids
            or rule_id in traced_by_rule
            or not _SHA256_RE.fullmatch(snapshot_hash)
            or snapshot_by_rule.get(rule_id) != snapshot_hash
            or len(fact_refs) != len(set(fact_refs))
            or any(not _SHA256_RE.fullmatch(item) for item in fact_refs)
            or not _VERSION_RE.fullmatch(evaluator_version)
            or observed_state not in _OBSERVED_STATES
            or not _REASON_CODE_RE.fullmatch(reason_code)
            or public_result_state != observed_state
        ):
            raise ValueError("invalid decision trace")
        traced_by_rule[rule_id] = (
            snapshot_hash,
            fact_refs,
            evaluator_version,
            observed_state,
            reason_code,
        )
    traced_rule_ids = tuple(
        rule_id for rule_id in expected_traced_ids if rule_id in traced_by_rule
    )
    if (
        traced_rule_ids != expected_traced_ids
        or len(traced_by_rule) != len(expected_traced_ids)
    ):
        raise ValueError("incomplete decision trace")

    rows: list[dict[str, str]] = []
    seen_hashes: set[str] = set()
    for rule_id in selected_rule_ids:
        (
            snapshot_hash,
            fact_refs,
            evaluator_version,
            observed_state,
            reason_code,
        ) = traced_by_rule[rule_id]
        evidence_hash = _canonical_digest(
            {
                "attestation_version": EVIDENCE_ATTESTATION_VERSION,
                "rule_id": rule_id,
                "snapshot_hash": snapshot_hash,
                "fact_refs": list(fact_refs),
                "evaluator_version": evaluator_version,
            }
        )
        if evidence_hash in seen_hashes:
            raise ValueError("duplicate evidence attestation")
        seen_hashes.add(evidence_hash)
        rows.append(
            {
                "rule_id": rule_id,
                "evidence_hash": evidence_hash,
                "observed_state": observed_state,
                "reason_code": reason_code,
            }
        )
    if len(rows) != len(selected_rule_ids):
        raise ValueError("incomplete evidence attestation")
    return tuple(rows)


def _validate_result_scope(
    results: list[Mapping[str, Any]],
    *,
    selected_rule_ids: tuple[str, ...],
) -> None:
    actual = tuple(str(item.get("rule_id") or "").strip().upper() for item in results)
    if actual != selected_rule_ids or len(actual) != len(set(actual)):
        raise ValueError("LX0609 preproduction result scope mismatch")


async def run_luxian_0609_preproduction(
    *,
    bundle: Mapping[str, Any],
    selected_customer_rule_ids: Iterable[str],
    evaluation_as_of_date: str,
    llm_client: Any,
    base_settings: Any,
    model_name: str,
    source_schema: str | None = None,
    evidence_attestation_sink: EvidenceAttestationSink | None = None,
) -> dict[str, Any]:
    """只读运行 LX0609 独立包并返回安全客户 DTO 与聚合指标。"""

    if not isinstance(bundle, Mapping):
        raise TypeError("bundle must be a mapping")
    scene = str(bundle.get("scene") or "").strip().lower()
    if scene not in {"running", "final"}:
        raise ValueError("bundle scene must be running or final")
    selected = _validate_selected_rule_ids(selected_customer_rule_ids)
    as_of_date = _validate_evaluation_as_of_date(evaluation_as_of_date)
    if base_settings is None:
        raise TypeError("base_settings is required")

    # 延迟加载，避免旧服务导入独立包时经适配器 runtime 形成环。
    # 实际运行旁路时这里只使用无 I/O 的 pure adapter。
    from ..qc_input_adapters.running_final_bundle_adapter import (
        adapt_bundle_to_sichuan_eval_args,
    )

    bundle_dict = dict(bundle)
    private_terms = _collect_private_terms(bundle_dict)
    adapted = adapt_bundle_to_sichuan_eval_args(bundle_dict, rule_ids=[])
    evidence_payload = dict(adapted.get("evidence_payload") or {})
    settings = build_full_rule_decision_settings(
        base_settings,
        preproduction=True,
    )
    started = perf_counter()
    context: Any = None
    decision_trace_rows: list[Mapping[str, Any]] = []
    orchestrated: dict[str, Any] = {
        "results": [],
        "total_prompt_tokens": 0,
        "total_completion_tokens": 0,
        "total_tokens": 0,
        "total_api_time": 0.0,
        "executor_breakdown": {},
    }
    usage_attributions: tuple[dict[str, Any], ...] = ()
    usage_complete = False
    usage_error_reason = ""
    observed_usage = _observed_usage_metrics(context, orchestrated)
    failure_reason_code = "prepare_execution_failed"
    try:
        executable_rules, context = await prepare_luxian_0609_execution(
            rule_set_key=LUXIAN_0609_RULE_SET_KEY,
            prepared_rules=[],
            visit_id=str(bundle_dict.get("visit_id") or ""),
            medical_text=str(adapted.get("content") or ""),
            evidence_payload=evidence_payload,
            llm_client=llm_client,
            settings=settings,
            institute_id=str(bundle_dict.get("institute_id") or ""),
            patient_id=str(bundle_dict.get("patient_id") or ""),
            source_schema=source_schema,
            evaluation_as_of_date=as_of_date,
            selected_customer_rule_ids=selected,
        )
        failure_reason_code = "legacy_dispatch_violation"
        if executable_rules:
            raise ValueError("preproduction runner must not dispatch legacy rules")
        failure_reason_code = "aggregate_results_failed"
        aggregate_luxian_0609_orchestrated_results(
            orchestrated=orchestrated,
            context=context,
            visit_id=str(bundle_dict.get("visit_id") or ""),
            model_name=str(model_name or ""),
            evidence_payload=evidence_payload,
            execution_rule_count=0,
            decision_trace_sink=(
                decision_trace_rows.append
                if evidence_attestation_sink is not None
                else None
            ),
        )
        failure_reason_code = "usage_accounting_mismatch"
        usage_attributions = _validate_usage_accounting(
            context=context,
            orchestrated=orchestrated,
        )
        usage_complete = True
        observed_usage = _observed_usage_metrics(context, orchestrated)
        raw_results = list(orchestrated.get("results") or [])
        failure_reason_code = "result_scope_validation_failed"
        _validate_result_scope(raw_results, selected_rule_ids=selected)
        failure_reason_code = "customer_sanitization_failed"
        results = [
            _sanitize_customer_result(item, private_terms=private_terms)
            for item in raw_results
            if isinstance(item, Mapping)
        ]
        if evidence_attestation_sink is not None:
            failure_reason_code = "evidence_attestation_failed"
            evidence_attestations = _build_evidence_attestations(
                selected_rule_ids=selected,
                trace_rows=decision_trace_rows,
                raw_results=raw_results,
                context=context,
            )
            evidence_attestation_sink(evidence_attestations)
    except Exception as exc:
        observed_usage = (
            dict(exc.observed_metrics)
            if isinstance(exc, _UsageAccountingError)
            else _observed_usage_metrics(context, orchestrated)
        )
        usage_error_reason = (
            "usage_accounting_mismatch"
            if isinstance(exc, _UsageAccountingError)
            else failure_reason_code
        )
        usage_attributions = ()
        usage_complete = False
        results = _technical_results(
            selected,
            reason_code=failure_reason_code,
        )

    elapsed_ms = round((perf_counter() - started) * 1000.0, 3)
    status_counts = Counter(str(item.get("status") or "technical_error") for item in results)
    maturity = _contract_maturity()
    metrics = {
        "wall_time_ms": elapsed_ms,
        **observed_usage,
        "usage_complete": usage_complete,
        "usage_error_reason": usage_error_reason,
        "usage_observation_complete": (
            usage_complete
            and context is not None
            and not bool(getattr(context, "native_usage_unknown_executor_keys", ()))
        ),
        "usage_unknown_executor_keys": list(
            getattr(context, "native_usage_unknown_executor_keys", ())
        ),
        "usage_attributions": list(usage_attributions),
        "unattributed_prompt_tokens": (
            0 if usage_complete else observed_usage["prompt_tokens"]
        ),
        "unattributed_completion_tokens": (
            0 if usage_complete else observed_usage["completion_tokens"]
        ),
        "unattributed_total_tokens": (
            0 if usage_complete else observed_usage["total_tokens"]
        ),
        "customer_rule_count": len(results),
        "status_counts": dict(sorted(status_counts.items())),
        "technical_error_count": int(status_counts.get("technical_error") or 0),
        **maturity,
    }
    return {
        "schema_version": PREPRODUCTION_RUNNER_SCHEMA_VERSION,
        "results": results,
        "metrics": metrics,
    }
