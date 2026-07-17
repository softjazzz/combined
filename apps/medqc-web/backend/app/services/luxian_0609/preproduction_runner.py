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
import re
from time import perf_counter
from typing import Any, Callable, Iterable, Mapping, Sequence

from .customer_rule_package import LUXIAN_0609_RULE_SET_KEY
from .execution import (
    aggregate_luxian_0609_orchestrated_results,
    prepare_luxian_0609_execution,
)
from .rule_contracts import load_luxian_0609_rule_contracts


PREPRODUCTION_RUNNER_SCHEMA_VERSION = "lx0609-preproduction-runner-v1"
EVIDENCE_ATTESTATION_VERSION = "lx0609-evidence-attestation-v1"

_ADAPTER_RULE_IDS = frozenset({"LX0609-029", "LX0609-030", "LX0609-032"})
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

_SETTING_OVERRIDES = {
    "LUXIAN_0609_CUSTOMER_AGGREGATION_ENABLED": True,
    "LUXIAN_0609_TRIGGER_GATE_ENABLED": False,
    "LUXIAN_0609_LLM_TRIGGER_GATE_ENABLED": False,
    "LUXIAN_0609_EVIDENCE_FORMATTER_ENABLED": False,
    "LUXIAN_0609_NATIVE_EXECUTION_ENABLED": True,
    "LUXIAN_0609_NATIVE_BASIC_TIMELINESS_ENABLED": True,
    "LUXIAN_0609_NATIVE_CONSULTATION_ENABLED": True,
    "LUXIAN_0609_NATIVE_EXAM_LAB_ENABLED": True,
    "LUXIAN_0609_NATIVE_TRANSFUSION_ENABLED": True,
    "LUXIAN_0609_NATIVE_TUMOR_PATHOLOGY_ENABLED": True,
    "LUXIAN_0609_NATIVE_COURSE_QUALITY_ENABLED": True,
    "LUXIAN_0609_NATIVE_SURGERY_GATE_ENABLED": True,
    "LUXIAN_0609_NATIVE_SURGERY_DOCUMENT_ENABLED": True,
    "LUXIAN_0609_NATIVE_MDT_040_ENABLED": True,
    "LUXIAN_0609_EVIDENCE_SNAPSHOT_SIDECAR_ENABLED": True,
    "LUXIAN_0609_UNIFIED_ENGINE_ENABLED": True,
    "LUXIAN_0609_RULE_DECISION_007_ENABLED": True,
    "LUXIAN_0609_RULE_DECISION_BASIC_TIMELINESS_ENABLED": True,
    "LUXIAN_0609_RULE_DECISION_COURSE_SEVERITY_ENABLED": True,
    "LUXIAN_0609_RULE_DECISION_TRANSFUSION_ENABLED": True,
    "LUXIAN_0609_RULE_DECISION_CONSULTATION_ENABLED": True,
    "LUXIAN_0609_RULE_DECISION_COURSE_COPY_ENABLED": True,
    "LUXIAN_0609_RULE_DECISION_COURSE_ADMISSION_ENABLED": True,
    "LUXIAN_0609_RULE_DECISION_TUMOR_PATHOLOGY_ENABLED": True,
    "LUXIAN_0609_RULE_DECISION_MDT_040_ENABLED": True,
    "LUXIAN_0609_RULE_DECISION_SURGERY_TIMELINESS_ENABLED": True,
    "LUXIAN_0609_RULE_DECISION_SURGERY_GATE_REMAINING_ENABLED": True,
    "LUXIAN_0609_RULE_DECISION_EXAM_LAB_ENABLED": True,
    "LUXIAN_0609_RULE_DECISION_SURGERY_DOCUMENT_ENABLED": True,
    "LUXIAN_0609_RUNTIME_SHADOW_ENABLED": False,
}

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
    "prompt_tokens",
    "completion_tokens",
    "total_tokens",
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
_MIN_PRIVATE_FRAGMENT_CHARS = 12


class _ReadOnlySettingsOverlay:
    """仅覆盖本次旁路运行开关，不修改基础设置或进程环境。"""

    __slots__ = ("_base",)

    def __init__(self, base: Any) -> None:
        object.__setattr__(self, "_base", base)

    def __getattr__(self, name: str) -> Any:
        if name in _SETTING_OVERRIDES:
            return _SETTING_OVERRIDES[name]
        return getattr(self._base, name)

    def __setattr__(self, name: str, value: Any) -> None:
        raise AttributeError("preproduction settings overlay is read-only")


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
    typed_rule_count = sum(item.contract_version != "v1" for item in contracts)
    typed_source_count = sum(
        item.source_contract_state == "typed_shadow_v1" for item in contracts
    )
    return {
        "rule_decision_count": typed_rule_count,
        "typed_shadow_adapter_count": max(0, typed_source_count - typed_rule_count),
        "legacy_projection_count": sum(
            item.source_contract_state == "legacy_projection_v1"
            for item in contracts
        ),
    }


def _technical_results(rule_ids: tuple[str, ...]) -> list[dict[str, Any]]:
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
                "reason_code": "preproduction_runner_failed",
                "customer_rule_id": rule_id,
            },
        }
        for rule_id in rule_ids
    ]


def _canonical_digest(value: Any) -> str:
    material = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(material.encode("utf-8")).hexdigest()


def _adapter_evaluator_version(rule_id: str) -> str:
    contract = next(
        (item for item in load_luxian_0609_rule_contracts() if item.rule_id == rule_id),
        None,
    )
    if contract is None or rule_id not in _ADAPTER_RULE_IDS:
        raise ValueError("missing trusted adapter contract")
    identity = (
        f"adapter-{contract.executor_key}-{contract.contract_version}-"
        f"{contract.rule_version}"
    )
    if not _VERSION_RE.fullmatch(identity):
        raise ValueError("invalid trusted adapter contract")
    return identity


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
    expected_traced_ids = tuple(
        rule_id for rule_id in selected_rule_ids if rule_id not in _ADAPTER_RULE_IDS
    )
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
            or str(result_by_rule[rule_id].get("status") or "").strip().lower()
            != observed_state
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
        if rule_id in _ADAPTER_RULE_IDS:
            snapshot_hash = snapshot_by_rule[rule_id]
            fact_refs: tuple[str, ...] = ()
            evaluator_version = _adapter_evaluator_version(rule_id)
            raw_result = result_by_rule[rule_id]
            observed_state = str(raw_result.get("status") or "").strip().lower()
            raw_metadata = raw_result.get("metadata")
            reason_code = (
                str(raw_metadata.get("reason_code") or "").strip().lower()
                if isinstance(raw_metadata, Mapping)
                else ""
            )
            if (
                observed_state not in _OBSERVED_STATES
                or not _REASON_CODE_RE.fullmatch(reason_code)
            ):
                raise ValueError("invalid adapter attestation result")
        else:
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
    settings = _ReadOnlySettingsOverlay(base_settings)
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
        if executable_rules:
            raise ValueError("preproduction runner must not dispatch legacy rules")
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
        raw_results = list(orchestrated.get("results") or [])
        _validate_result_scope(raw_results, selected_rule_ids=selected)
        results = [
            _sanitize_customer_result(item, private_terms=private_terms)
            for item in raw_results
            if isinstance(item, Mapping)
        ]
        if evidence_attestation_sink is not None:
            evidence_attestations = _build_evidence_attestations(
                selected_rule_ids=selected,
                trace_rows=decision_trace_rows,
                raw_results=raw_results,
                context=context,
            )
            evidence_attestation_sink(evidence_attestations)
    except Exception:
        results = _technical_results(selected)
        orchestrated = {
            "total_prompt_tokens": 0,
            "total_completion_tokens": 0,
            "total_tokens": 0,
            "total_api_time": 0.0,
        }

    elapsed_ms = round((perf_counter() - started) * 1000.0, 3)
    status_counts = Counter(str(item.get("status") or "technical_error") for item in results)
    maturity = _contract_maturity()
    context_prompt_tokens = int(getattr(context, "native_prompt_tokens", 0) or 0)
    context_completion_tokens = int(
        getattr(context, "native_completion_tokens", 0) or 0
    )
    context_total_tokens = int(getattr(context, "native_total_tokens", 0) or 0)
    context_api_time = float(getattr(context, "native_api_time", 0.0) or 0.0)
    metrics = {
        "wall_time_ms": elapsed_ms,
        "llm_call_count": int(getattr(context, "native_llm_call_count", 0) or 0),
        "prompt_tokens": max(
            context_prompt_tokens,
            int(orchestrated.get("total_prompt_tokens") or 0),
        ),
        "completion_tokens": max(
            context_completion_tokens,
            int(orchestrated.get("total_completion_tokens") or 0),
        ),
        "total_tokens": max(
            context_total_tokens,
            int(orchestrated.get("total_tokens") or 0),
        ),
        "api_time_seconds": round(
            max(context_api_time, float(orchestrated.get("total_api_time") or 0.0)),
            6,
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
