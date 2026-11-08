from __future__ import annotations

from .clinical_sources import bound_job

import asyncio
from contextlib import nullcontext
from copy import deepcopy
from datetime import datetime, timezone
import logging
import re
import threading
import time
from typing import Any, Awaitable, Callable, Dict, List, Optional
import uuid

from fastapi import HTTPException

from ..core.settings import get_settings
from ..core.execution_timing import current_timing_snapshot, finish_current_timing, observe_worker_timing, timed
from .luxian_0609.phase_scope import frozen_luxian_0609_delivery_scope
from .luxian_0609.live_results import LiveResultBuffer, live_result_scope
from .qc_workspace.canonical_result_store import validated_customer_explanation
from .luxian_0609.privacy_identity_context import _Luxian0609IdentityCollector
from .luxian_0609.privacy_request_scope import luxian_0609_case_identity_scope
from .case_identity import CaseRef, case_refs_from_records, normalize_case_refs
from .qc_workspace.record_timing import summarize_record_timings
from .custom_qc_workspace_service import (
    CustomQCWorkspaceService,
    LX0609_ATTEMPT_FILTER_KEY,
    LX0609_LEASE_FILTER_KEY,
)
from .customer_rule_sets import CUSTOMER_LUXIAN_RULE_SET_KEY
from .effect_priority_qc import (
    DEFAULT_MAX_REFINE_CANDIDATES,
    DEFAULT_REFINE_CONFIDENCE_THRESHOLD,
    QUALITY_PROFILE_EFFECT_PRIORITY,
    QUALITY_PROFILE_THROUGHPUT,
    normalize_batch_output_mode,
    normalize_max_refine_candidates,
)
from .fast_screen_qc import (
    EXECUTION_STRATEGY_FAST_SCREEN,
    normalize_execution_strategy,
    run_final_fast_screen,
)
from .llm_observability import llm_observation_context
from .qc_diagnostics.job_capture import DiagnosticJobCapture, diagnostic_job_lifecycle
from .luxian_0609 import (
    LUXIAN_0609_RULE_SET_KEY,
    build_luxian_0609_package_plan_from_settings,
    get_luxian_0609_rule,
    load_luxian_0609_dependency_inventory,
    load_luxian_0609_rules,
    resolve_package_rollback_execution_rule_ids,
)
from .luxian_0609.evaluation_horizon import (
    resolve_record_evaluation_horizon_policy,
    resolve_record_evaluation_horizon_unavailable_reason,
)
from .luxian_0609.native_package import (
    assert_luxian_0609_formal_package_plan_native_only,
)
from .luxian_0609.rule_decision_settings import (
    LX0609_TASK_SETTINGS_FILTER_KEY,
    LX0609_TASK_RUNTIME_FILTER_KEY,
    assert_luxian_0609_task_settings_match,
    assert_luxian_0609_task_runtime_match,
    assert_luxian_0609_customer_native_delivery_ready,
    resolve_mainline_rule_decision_settings,
)
from .luxian_0609.runtime_shadow_hook import run_luxian_0609_runtime_shadow
from .luxian_0609.shadow_audit_summary import (
    merge_luxian_0609_shadow_summaries,
)
from .qc_cancellation import QCJobCancelled, raise_if_cancelled
from .qc_llm_client_runtime import SichuanQCLLMClient
from .llm_dispatch.provider_profiles import ProviderConfigurationError
from .qc_input_adapters import evaluate_running_final_bundle
from .qc_input_adapters.running_final_bundle_runtime import load_running_final_bundle
from .qc_result_adjudicator import adjudicate_postprocessed_qc_results
from .qc_result_postprocessor import postprocess_qc_result, summarize_postprocessed_results
from .product_activation import get_product_activation_service
from .sample_programmatic_evidence import build_programmatic_evidence_payload
from .sample_validation_rule_sets import (
    LUXIAN_0609_CUSTOMER_EXCLUDED_RULE_IDS,
    apply_programmatic_rule_runtime_overrides,
    get_sample_programmatic_rule_set,
)
from .luxian_0609.phase_scope import (
    build_luxian_0609_pending_definition_result,
    partition_luxian_0609_rule_scope,
)
from .sichuan_qc_service import RuleSourceGuardError, SichuanQCService


from .qc_workspace.execution_failure import (
    _build_luxian_execution_failure_record,
    _build_luxian_model_execution_summary,
    _extract_luxian_model_execution_stats,
    _is_luxian_execution_failure,
    _merge_luxian_model_execution_stats,
    _normalize_luxian_model_execution_stats,
)
from .qc_workspace.failed_rule_retry import (
    FAILED_RULE_RETRY_FILTER_KEY,
    FAILED_RULE_RETRY_SCHEMA_VERSION,
    build_failed_rule_auto_retry_plan,
    merge_failed_rule_retry_results,
    merge_failed_rule_retry_rule_results,
)
from .qc_dispatch.contracts import qc_dispatch_mode_from_filters

logger = logging.getLogger(__name__)


def _enqueue_automatic_failed_rule_retry(
    *,
    workspace: CustomQCWorkspaceService,
    job_id: str,
    created_by: str,
    expected_attempt_filters_json: str | None,
    retry_delay_seconds: float | None = None,
) -> Optional[Dict[str, Any]]:
    """实际入队成功后才发布 queued；失败用同代次 CAS 撤销 planned。"""

    retry_method = getattr(workspace, "retry_batch_job", None)
    mark_failed = getattr(workspace, "mark_failed_rule_auto_retry_enqueue_failed", None)

    def _mark_failed() -> None:
        if callable(mark_failed) and expected_attempt_filters_json is not None:
            mark_failed(
                job_id=job_id,
                expected_attempt_filters_json=expected_attempt_filters_json,
            )

    if not created_by or not callable(retry_method):
        _mark_failed()
        return None
    try:
        retried_job = retry_method(
            job_id=job_id,
            created_by=created_by,
            automatic=True,
            **(
                {"expected_attempt_filters_json": expected_attempt_filters_json}
                if expected_attempt_filters_json is not None
                else {}
            ),
            **(
                {"retry_delay_seconds": retry_delay_seconds}
                if retry_delay_seconds is not None
                else {}
            ),
        )
    except Exception:
        _mark_failed()
        raise
    if not retried_job or str(retried_job.get("status") or "") != "queued":
        _mark_failed()
        return None
    return retried_job


def _ordered_luxian_0609_customer_rule_ids(
    requested_rule_ids: List[str] | tuple[str, ...],
) -> tuple[str, ...]:
    """只接受完整的客户规则 ID，并按独立包目录顺序返回。"""

    requested = {
        str(rule_id or "").strip().upper()
        for rule_id in requested_rule_ids
        if str(rule_id or "").strip()
    }
    if not requested:
        return ()
    inventory = load_luxian_0609_dependency_inventory()
    by_id = {item.rule_id for item in inventory}
    if any(rule_id not in by_id for rule_id in requested):
        return ()
    return tuple(item.rule_id for item in inventory if item.rule_id in requested)


def _assert_luxian_0609_formal_customer_rule_ids(
    *,
    rule_set_key: str,
    rule_ids: List[str] | tuple[str, ...],
    context: str,
) -> tuple[str, ...]:
    """正式LX0609任务只允许独立包目录内的客户规则ID。"""

    if str(rule_set_key or "").strip() != LUXIAN_0609_RULE_SET_KEY:
        return ()
    normalized = {
        str(rule_id or "").strip().upper()
        for rule_id in rule_ids
        if str(rule_id or "").strip()
    }
    ordered = _ordered_luxian_0609_customer_rule_ids(tuple(normalized))
    rejected = sorted(normalized.difference(ordered))
    if rejected:
        raise ValueError(
            "LX0609正式规则集只接受LX0609客户质控点ID，"
            f"禁止旧或未知规则ID：{','.join(rejected)}（入口：{context}）。"
        )
    return ordered


def _luxian_0609_rollback_rule_ids(
    customer_rule_ids: List[str] | tuple[str, ...],
) -> tuple[str, ...]:
    return resolve_package_rollback_execution_rule_ids(
        inventory=load_luxian_0609_dependency_inventory(),
        selected_rule_ids=customer_rule_ids,
    )


def _should_guard_sc_source(rule_ids: Optional[List[str]]) -> bool:
    normalized = [str(item or "").strip().upper() for item in (rule_ids or []) if str(item or "").strip()]
    if not normalized:
        # 未显式传 rule_ids，默认会走 SC 规则集，仍需校验来源。
        return True
    return any(item.startswith("SC-") for item in normalized)


def _enforce_sc_source_guard(
    qc_service: SichuanQCService,
    *,
    context: str,
    rule_ids: Optional[List[str]] = None,
    block_batch: bool = False,
) -> Dict[str, Any]:
    if not _should_guard_sc_source(rule_ids):
        return {}
    try:
        return qc_service.assert_sc_rule_source_ready(context=context, block_batch=block_batch)
    except RuleSourceGuardError as exc:
        raise HTTPException(status_code=503, detail=str(exc))


def _resolve_workspace_bundle_scene(*, query_scope: str, record_scope: str) -> str:
    normalized_query = str(query_scope or "").strip().lower()
    normalized_record = str(record_scope or "").strip().lower()
    if normalized_record in {"running", "final"}:
        return normalized_record
    if normalized_query in {"running", "final"}:
        return normalized_query
    return ""


def _workspace_bundle_scene_candidates(*, query_scope: str, record_scope: str) -> List[str]:
    preferred_scene = _resolve_workspace_bundle_scene(
        query_scope=query_scope,
        record_scope=record_scope,
    )
    if preferred_scene == "final":
        return ["final", "running"]
    return ["running", "final"]


def _workspace_scene_resolution_status(
    *,
    record_scope: str,
    resolved_scene: str,
    loaded_scene: str,
) -> str:
    normalized_record = str(record_scope or "").strip().lower()
    if not loaded_scene:
        return "unavailable"
    if normalized_record not in {"running", "final"}:
        return "uncertain_fallback"
    if loaded_scene != resolved_scene:
        return "fallback"
    return "matched"


def _normalize_quality_profile(value: Any) -> str:
    normalized = str(value or "").strip().lower()
    if normalized == QUALITY_PROFILE_EFFECT_PRIORITY:
        return QUALITY_PROFILE_EFFECT_PRIORITY
    return QUALITY_PROFILE_THROUGHPUT


def _normalize_bucket_strategy(value: Any) -> str:
    normalized = str(value or "").strip().lower()
    if normalized == "domain_family":
        return "domain_family"
    if normalized == "fixed_packs":
        return "fixed_packs"
    return "domain_only"


def _normalize_refine_threshold(value: Any) -> float:
    try:
        number = float(value)
    except Exception:
        return DEFAULT_REFINE_CONFIDENCE_THRESHOLD
    if number <= 0 or number > 1:
        return DEFAULT_REFINE_CONFIDENCE_THRESHOLD
    return number


def _normalize_batch_output_mode(value: Any, *, quality_profile: Any = QUALITY_PROFILE_THROUGHPUT) -> str:
    return normalize_batch_output_mode(value, quality_profile=quality_profile)


def _normalize_max_refine_candidates(value: Any, *, default: int = DEFAULT_MAX_REFINE_CANDIDATES) -> int:
    return normalize_max_refine_candidates(value, default=default)


def _normalize_run_mode(run_mode: Optional[str]) -> str:
    value = str(run_mode or "").strip().lower()
    return "parallel" if value == "parallel" else "serial"


def _resolve_document_type(scope: str, record_scope: Optional[str]) -> str:
    if scope == "running":
        return "病程记录"
    if scope == "final":
        return "出院记录"
    return "出院记录" if str(record_scope or "").strip().lower() == "final" else "病程记录"


def _resolve_luxian_target_document_type(rule: Dict[str, Any]) -> str:
    """返回 LX0609 规则目录声明的目标文书域，不能被运行场景覆盖。"""
    if not isinstance(rule, dict):
        return ""
    explicit = str(rule.get("target_document_type") or rule.get("document_type") or "").strip()
    if explicit:
        return explicit
    labels = rule.get("applicable_document_labels") or rule.get("applicable_documents") or []
    if not isinstance(labels, (list, tuple)):
        return ""
    resolved: list[str] = []
    for item in labels:
        label = str(item or "").strip()
        if label and label not in resolved:
            resolved.append(label)
    return "、".join(resolved)


def _build_cluster_key(item: Dict[str, Any]) -> str:
    status = str(item.get("status") or "").strip().lower()
    if status == "non_compliant":
        status_label = "不合规"
    elif status == "ai_suggested_non_compliant":
        status_label = "AI判断"
    elif status == "ai_suggested_compliant":
        status_label = "AI判断"
    elif status == "uncertain":
        status_label = "AI判断"
    else:
        status_label = "其他"
    evidence = _sanitize_result_aggregation_text(str(item.get("evidence") or "").strip())
    findings = str(item.get("findings") or "").strip()
    base = evidence or findings or str(item.get("rule_name") or item.get("rule_code") or "命中项")
    return f"[{status_label}] {base[:64]}"


_RESULT_AGGREGATION_INTERNAL_PATTERNS = (
    re.compile(r"^证据模板[:：].*$"),
    re.compile(r"^映射执行规则[:：].*$"),
    re.compile(r"^应包含证据要素[:：].*$"),
    re.compile(r"^触发状态[:：].*$"),
    re.compile(r"^触发说明[:：].*$"),
)


def _sanitize_result_aggregation_text(text: str, *, limit: int = 120) -> str:
    """清理任务聚合摘要中的内部执行话术，避免进入历史任务和导出摘要。"""
    cleaned_lines: List[str] = []
    seen: set[str] = set()
    for raw_line in str(text or "").replace("；", "\n").splitlines():
        line = " ".join(raw_line.strip().split())
        if not line:
            continue
        if any(pattern.search(line) for pattern in _RESULT_AGGREGATION_INTERNAL_PATTERNS):
            continue
        if line.startswith("判定依据："):
            if "未发现与本质控点直接相关的适用事件" in line:
                line = "适用性：未发现与本质控点直接相关的触发事实。"
            elif "自动判定所需字段不完整" in line:
                line = "数据不足：已发现相关事件，但缺少自动判定所需字段。"
            else:
                continue
        line = re.sub(r"^(来源未标注\s*[·:：]\s*)?evidence\s*[·:：]\s*", "", line, flags=re.IGNORECASE)
        dedupe_key = line.rstrip("。；; ")
        if not line or dedupe_key in seen:
            continue
        seen.add(dedupe_key)
        cleaned_lines.append(line)
    cleaned = "；".join(cleaned_lines)
    return cleaned[:limit]


def _to_breakdown_list(counter: Dict[str, int], top_n: int = 8) -> List[Dict[str, Any]]:
    ranked = sorted(counter.items(), key=lambda it: it[1], reverse=True)[:top_n]
    return [{"key": key, "count": int(count)} for key, count in ranked if key]


def _safe_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return str(value or "").strip().lower() in {"1", "true", "yes", "y", "是"}


def _should_postprocess_formal_qc_results(
    *,
    rule_set_key: str,
    validation_mode: str,
    current_scope: str,
    execution_strategy: str,
    bucket_strategy: str,
) -> bool:
    normalized_rule_set = str(rule_set_key or "").strip()
    normalized_mode = str(validation_mode or "").strip().lower()
    normalized_scope = str(current_scope or "").strip().lower()
    normalized_execution = str(execution_strategy or "").strip().lower()
    normalized_bucket = str(bucket_strategy or "").strip().lower()
    return (
        normalized_rule_set == "sc_content_full_v1"
        or normalized_mode == "formal_fast_screen_full"
        or (
            normalized_scope == "final"
            and normalized_execution == EXECUTION_STRATEGY_FAST_SCREEN
            and normalized_bucket == "fixed_packs"
            and normalized_rule_set.startswith("sc_content_")
        )
    )


def _has_meaningful_first_course_text_for_batch(*, eval_item: Dict[str, Any], record: Dict[str, Any]) -> bool:
    def _meaningful(text: Any) -> bool:
        normalized = "".join(str(text or "").split())
        return bool(normalized and normalized not in {"首次病程记录", "首次病程"} and len(normalized) >= 20)

    metadata = eval_item.get("metadata") if isinstance(eval_item.get("metadata"), dict) else {}
    timeline = metadata.get("programmatic_timeline") if isinstance(metadata, dict) else None
    if isinstance(timeline, dict):
        docs = timeline.get("documents")
        if isinstance(docs, dict):
            first_courses = [item for item in list(docs.get("first_course_record") or []) if isinstance(item, dict)]
            if not first_courses:
                return False
            return any(
                _meaningful(
                    "\n".join(
                        str(item.get(key) or "").strip()
                        for key in (
                            "case_characteristic",
                            "content",
                            "raw_text",
                            "content_preview",
                        )
                        if str(item.get(key) or "").strip()
                    )
                )
                for item in first_courses
            )

    medical_text = str(record.get("medical_text") or "")
    for marker in ("首次病程记录", "首次病程"):
        start = 0
        while True:
            position = medical_text.find(marker, start)
            if position < 0:
                break
            window = medical_text[position: position + 600]
            cleaned = re.sub(r"(首次病程记录|首次病程|记录时间|提交时间|正文|文书类型|文书编号|[:：\s\d\-T]+)", "", window)
            if _meaningful(cleaned):
                return True
            start = position + len(marker)
    return False


def _guard_luxian_copy_result_for_batch(
    *,
    rule_id: str,
    eval_item: Dict[str, Any],
    record: Dict[str, Any],
) -> Dict[str, Any]:
    normalized_rule_id = str(rule_id or eval_item.get("rule_id") or eval_item.get("rule_code") or "").strip().upper()
    if normalized_rule_id != "LX0609-12-01-01":
        return eval_item
    display_facts = eval_item.get("customer_display_facts")
    if (
        isinstance(display_facts, dict)
        and display_facts.get("failure_kind")
        == "admission_first_course_copy_detected"
    ):
        return eval_item
    if _has_meaningful_first_course_text_for_batch(eval_item=eval_item, record=record):
        return eval_item
    guarded = dict(eval_item)
    metadata = dict(guarded.get("metadata") or {})
    metadata.update(
        {
            "executor_type": "program",
            "copy_rule_priority_guard": "first_course_missing",
            "data_gap_reason": "首次病程记录缺失或正文为空，无法进行复制病历比对",
        }
    )
    guarded.update(
        {
            "rule_id": normalized_rule_id,
            "rule_code": normalized_rule_id,
            "status": "data_gap",
            "is_compliant": False,
            "findings": "首次病程记录缺失或正文为空，无法判断是否存在复制病历内容。",
            "evidence": "数据缺口：首次病程记录正文为空；复制病历比对未执行。",
            "suggestion": "请先补齐首次病程记录正文，再复核是否与入院记录或其他病程存在复制。",
            "confidence": max(float(guarded.get("confidence") or 0.0), 0.9),
            "metadata": metadata,
        }
    )
    return guarded


def _build_result_aggregation(items: List[Dict[str, Any]]) -> Dict[str, Any]:
    clusters: Dict[str, Dict[str, Any]] = {}
    rule_counter: Dict[str, int] = {}
    executor_counter: Dict[str, int] = {}
    doc_counter: Dict[str, int] = {}
    defect_counter: Dict[str, int] = {}
    status_counter: Dict[str, int] = {}

    for item in items:
        cluster_key = _build_cluster_key(item)
        cluster = clusters.setdefault(
            cluster_key,
            {
                "cluster_key": cluster_key,
                "sample_evidence": _sanitize_result_aggregation_text(str(item.get("evidence") or "")),
                "records": 0,
                "rules": {},
                "document_types": {},
                "executor_types": {},
                "defect_levels": {},
                "status_breakdown": {},
            },
        )
        cluster["records"] += 1
        rule_id = str(item.get("rule_id") or item.get("rule_code") or "").strip()
        rule_name = str(item.get("rule_name") or rule_id or "未知规则").strip()
        if rule_id:
            cluster["rules"][rule_id] = {"rule_id": rule_id, "rule_name": rule_name}
            rule_counter[rule_id] = int(rule_counter.get(rule_id) or 0) + 1
        doc_type = str(item.get("document_type") or "").strip()
        if doc_type:
            cluster["document_types"][doc_type] = int(cluster["document_types"].get(doc_type) or 0) + 1
            doc_counter[doc_type] = int(doc_counter.get(doc_type) or 0) + 1
        executor_type = str(item.get("executor_type") or "").strip().lower() or "llm"
        cluster["executor_types"][executor_type] = int(cluster["executor_types"].get(executor_type) or 0) + 1
        executor_counter[executor_type] = int(executor_counter.get(executor_type) or 0) + 1
        defect_level = str(item.get("defect_level") or "").strip()
        if defect_level:
            cluster["defect_levels"][defect_level] = int(cluster["defect_levels"].get(defect_level) or 0) + 1
            defect_counter[defect_level] = int(defect_counter.get(defect_level) or 0) + 1
        status = str(item.get("status") or "").strip().lower() or "unknown"
        cluster["status_breakdown"][status] = int(cluster["status_breakdown"].get(status) or 0) + 1
        status_counter[status] = int(status_counter.get(status) or 0) + 1

    cluster_list: List[Dict[str, Any]] = []
    for cluster in clusters.values():
        cluster_list.append(
            {
                "cluster_key": cluster["cluster_key"],
                "sample_evidence": cluster["sample_evidence"],
                "records": int(cluster["records"]),
                "rules": list(cluster["rules"].values()),
                "document_types": cluster["document_types"],
                "executor_types": cluster["executor_types"],
                "defect_levels": cluster["defect_levels"],
                "status_breakdown": cluster["status_breakdown"],
            }
        )
    cluster_list.sort(key=lambda it: int(it.get("records") or 0), reverse=True)

    return {
        "cluster_count": len(cluster_list),
        "duplicate_hits": max(0, len(items) - len(cluster_list)),
        "clusters": cluster_list[:20],
        "rule_breakdown": [
            {
                "rule_id": rule_id,
                "rule_name": rule_id,
                "hits": int(hits),
            }
            for rule_id, hits in sorted(rule_counter.items(), key=lambda it: it[1], reverse=True)[:12]
        ],
        "executor_breakdown": _to_breakdown_list(executor_counter, top_n=6),
        "document_breakdown": _to_breakdown_list(doc_counter, top_n=8),
        "defect_level_breakdown": _to_breakdown_list(defect_counter, top_n=8),
        "status_breakdown": _to_breakdown_list(status_counter, top_n=6),
    }


def _records_with_only_status(items: List[Dict[str, Any]], status: str) -> set[str]:
    """所有项目都是该状态的病历（如“全部不适用”），而不是含任一该状态项目的病历。"""
    normalized = str(status or "").strip().lower()
    statuses: Dict[str, set[str]] = {}
    for item in items:
        record_id = str(item.get("record_key") or item.get("record_id") or "").strip()
        if record_id:
            statuses.setdefault(record_id, set()).add(str(item.get("status") or "").strip().lower())
    return {record_id for record_id, values in statuses.items() if values == {normalized}}


def _build_record_status_counts(
    *,
    total_records: int,
    issue_record_ids: set[str],
    uncertain_record_ids: set[str],
    data_gap_record_ids: set[str],
    failed_record_ids: set[str],
    not_applicable_record_ids: Optional[set[str]] = None,
) -> Dict[str, int]:
    issue_ids = {str(item or "").strip() for item in issue_record_ids if str(item or "").strip()}
    uncertain_ids = {str(item or "").strip() for item in uncertain_record_ids if str(item or "").strip()}
    data_gap_ids = {str(item or "").strip() for item in data_gap_record_ids if str(item or "").strip()}
    failed_ids = {str(item or "").strip() for item in failed_record_ids if str(item or "").strip()}
    not_applicable_ids = {
        str(item or "").strip()
        for item in (not_applicable_record_ids or set())
        if str(item or "").strip()
    }
    # 按病历互斥分类（失败 > 确定缺陷 > 待核 > 资料不足 > 全部不适用 > 合规），各类之和等于总数。
    issue_ids.difference_update(failed_ids)
    uncertain_ids.difference_update(failed_ids, issue_ids)
    data_gap_ids.difference_update(failed_ids, issue_ids, uncertain_ids)
    not_applicable_ids.difference_update(issue_ids, uncertain_ids, data_gap_ids, failed_ids)
    compliant_records = max(
        0,
        int(total_records or 0)
        - len(issue_ids)
        - len(uncertain_ids)
        - len(data_gap_ids)
        - len(failed_ids)
        - len(not_applicable_ids),
    )
    return {
        "non_compliant": len(issue_ids),
        "uncertain": len(uncertain_ids),
        "data_gap": len(data_gap_ids),
        "not_applicable": len(not_applicable_ids),
        "failed": len(failed_ids),
        "compliant": compliant_records,
    }


def _build_item_status_counts(items: List[Dict[str, Any]]) -> Dict[str, int]:
    status_keys = [
        "non_compliant",
        "ai_suggested_non_compliant",
        "ai_suggested_compliant",
        "compliant",
        "not_applicable",
        "data_gap",
        "uncertain",
        "not_executed",
        "technical_error",
        "failed",
    ]
    counts = {key: 0 for key in status_keys}
    for item in items:
        status = str(item.get("status") or "").strip().lower()
        display_status = str(item.get("display_status") or "").strip().lower()
        if status in counts:
            counts[status] += 1
        elif display_status == "data_quality_gap":
            counts["data_gap"] += 1
        elif display_status == "technical_error_internal":
            counts["technical_error"] += 1
        elif display_status in {"unsupported", "not_run", "not_executed"}:
            counts["not_executed"] += 1
        elif display_status == "rejected_by_system":
            counts["not_applicable"] += 1
    return counts


def _performance_int(value: Any) -> int:
    try:
        return int(float(value or 0))
    except (TypeError, ValueError):
        return 0


def _performance_float(value: Any) -> float:
    try:
        return float(value or 0.0)
    except (TypeError, ValueError):
        return 0.0


def _performance_dict(value: Any) -> Dict[str, Any]:
    return dict(value) if isinstance(value, dict) else {}


def _sum_int_maps(target: Dict[str, int], source: Any) -> None:
    if not isinstance(source, dict):
        return
    for raw_key, raw_value in source.items():
        key = str(raw_key or "").strip()
        if not key:
            continue
        target[key] = int(target.get(key) or 0) + _performance_int(raw_value)


def _summarize_luxian_input_profile(raw_profile: Any) -> Dict[str, Any]:
    profile = _performance_dict(raw_profile)
    if not profile:
        return {}
    family_profiles = _performance_dict(profile.get("family_profiles"))
    summarized_families: Dict[str, Dict[str, Any]] = {}
    for raw_family, raw_family_profile in family_profiles.items():
        family = str(raw_family or "").strip()
        family_profile = _performance_dict(raw_family_profile)
        if not family or not family_profile:
            continue
        summarized_families[family] = {
            "document_count": _performance_int(family_profile.get("document_count")),
            "text_char_count": _performance_int(family_profile.get("text_char_count")),
            "ready_for_trimmed_context": bool(family_profile.get("ready_for_trimmed_context") is True),
            "present_source_table_count": len(list(family_profile.get("present_source_tables") or [])),
            "missing_source_table_count": len(list(family_profile.get("missing_source_tables") or [])),
        }
    return {
        "schema_version": "luxian_0609_input_profile_v1",
        "mode": str(profile.get("mode") or "").strip(),
        "basis": str(profile.get("basis") or "").strip(),
        "visit_id": str(profile.get("visit_id") or "").strip(),
        "evidence_payload_available": bool(profile.get("evidence_payload_available") is True),
        "primary_text_char_count": _performance_int(profile.get("primary_text_char_count")),
        "medical_text_char_count": _performance_int(profile.get("medical_text_char_count")),
        "document_count": _performance_int(profile.get("document_count")),
        "source_table_count": _performance_int(profile.get("source_table_count")),
        "source_table_counts": {
            str(key): _performance_int(value)
            for key, value in _performance_dict(profile.get("source_table_counts")).items()
            if str(key or "").strip()
        },
        "source_table_text_lengths": {
            str(key): _performance_int(value)
            for key, value in _performance_dict(profile.get("source_table_text_lengths")).items()
            if str(key or "").strip()
        },
        "available_family_contexts": sorted(
            str(item).strip()
            for item in list(profile.get("available_family_contexts") or [])
            if str(item or "").strip()
        ),
        "family_profiles": summarized_families,
    }


def _build_batch_input_profile_summary(result_profiles: List[Dict[str, Any]]) -> Dict[str, Any]:
    profiles_by_visit: Dict[str, Dict[str, Any]] = {}
    for result_profile in result_profiles:
        input_profile = _performance_dict(result_profile.get("input_profile"))
        if not input_profile:
            continue
        visit_id = str(input_profile.get("visit_id") or result_profile.get("visit_id") or "").strip()
        key = visit_id or f"profile-{len(profiles_by_visit) + 1}"
        profiles_by_visit.setdefault(key, input_profile)

    if not profiles_by_visit:
        return {}

    source_table_counts: Dict[str, int] = {}
    source_table_text_lengths: Dict[str, int] = {}
    family_contexts: set[str] = set()
    family_summary: Dict[str, Dict[str, Any]] = {}
    total_document_count = 0
    total_primary_chars = 0
    total_medical_chars = 0
    evidence_payload_available_count = 0

    for input_profile in profiles_by_visit.values():
        total_document_count += _performance_int(input_profile.get("document_count"))
        total_primary_chars += _performance_int(input_profile.get("primary_text_char_count"))
        total_medical_chars += _performance_int(input_profile.get("medical_text_char_count"))
        if input_profile.get("evidence_payload_available") is True:
            evidence_payload_available_count += 1
        _sum_int_maps(source_table_counts, input_profile.get("source_table_counts"))
        _sum_int_maps(source_table_text_lengths, input_profile.get("source_table_text_lengths"))
        family_contexts.update(
            str(item).strip()
            for item in list(input_profile.get("available_family_contexts") or [])
            if str(item or "").strip()
        )
        for family_key, family_profile_raw in _performance_dict(input_profile.get("family_profiles")).items():
            family_profile = _performance_dict(family_profile_raw)
            family = str(family_key or "").strip()
            if not family or not family_profile:
                continue
            summary = family_summary.setdefault(
                family,
                {
                    "ready_record_count": 0,
                    "document_count": 0,
                    "text_char_count": 0,
                    "present_source_table_count": 0,
                    "missing_source_table_count": 0,
                },
            )
            if family_profile.get("ready_for_trimmed_context") is True:
                summary["ready_record_count"] = int(summary["ready_record_count"] or 0) + 1
            summary["document_count"] = int(summary["document_count"] or 0) + _performance_int(
                family_profile.get("document_count")
            )
            summary["text_char_count"] = int(summary["text_char_count"] or 0) + _performance_int(
                family_profile.get("text_char_count")
            )
            summary["present_source_table_count"] = int(summary["present_source_table_count"] or 0) + _performance_int(
                family_profile.get("present_source_table_count")
            )
            summary["missing_source_table_count"] = int(summary["missing_source_table_count"] or 0) + _performance_int(
                family_profile.get("missing_source_table_count")
            )

    return {
        "schema_version": "luxian_0609_input_perf_summary_v1",
        "basis": "unique_visit_input_profile",
        "record_count": len(profiles_by_visit),
        "evidence_payload_available_count": evidence_payload_available_count,
        "document_count": total_document_count,
        "primary_text_char_count": total_primary_chars,
        "medical_text_char_count": total_medical_chars,
        "source_table_counts": dict(sorted(source_table_counts.items())),
        "source_table_text_lengths": dict(sorted(source_table_text_lengths.items())),
        "available_family_contexts": sorted(family_contexts),
        "family_profiles": dict(sorted(family_summary.items())),
    }


def _distribute_non_negative_int(total: int, count: int) -> List[int]:
    safe_total = max(0, int(total or 0))
    safe_count = max(1, int(count or 0))
    quotient, remainder = divmod(safe_total, safe_count)
    return [
        quotient + (1 if index < remainder else 0)
        for index in range(safe_count)
    ]


def _attributed_llm_call_count(result: Dict[str, Any]) -> Optional[int]:
    breakdown = result.get("executor_breakdown")
    if not isinstance(breakdown, dict) or "llm" not in breakdown:
        return None
    return _performance_int(breakdown.get("llm"))


def _build_result_performance_profile(item: Dict[str, Any]) -> Dict[str, Any]:
    metadata = item.get("metadata") if isinstance(item.get("metadata"), dict) else {}
    executor_type = str(item.get("executor_type") or metadata.get("executor_type") or "llm").strip().lower()
    tokens_total = _performance_int(metadata.get("tokens_used") or item.get("tokens_used"))
    prompt_tokens = _performance_int(metadata.get("prompt_tokens") or item.get("prompt_tokens"))
    completion_tokens = _performance_int(metadata.get("completion_tokens") or item.get("completion_tokens"))
    input_tokens = _performance_int(metadata.get("input_tokens") or prompt_tokens)
    output_tokens = _performance_int(metadata.get("output_tokens") or completion_tokens)
    if tokens_total <= 0:
        tokens_total = prompt_tokens + completion_tokens
    unattributed_tokens = max(0, tokens_total - prompt_tokens - completion_tokens)
    duration_seconds = _performance_float(
        metadata.get("api_time")
        or item.get("api_time")
        or metadata.get("total_processing_time")
        or item.get("total_processing_time")
    )
    provider_error_count = _performance_int(metadata.get("provider_error_count") or item.get("provider_error_count"))
    timeout_count = _performance_int(metadata.get("timeout_count") or item.get("timeout_count"))
    rate_limit_count = _performance_int(metadata.get("rate_limit_count") or item.get("rate_limit_count"))
    pack_retry_attempts = _performance_int(metadata.get("pack_retry_attempts") or item.get("pack_retry_attempts"))
    retry_count = provider_error_count + timeout_count + rate_limit_count + pack_retry_attempts
    llm_call_count = 0
    program_call_count = 0
    if executor_type == "program":
        program_call_count = 1
    elif tokens_total > 0 or duration_seconds > 0 or _safe_bool(metadata.get("llm_fallback")):
        llm_call_count = 1
    input_profile = _summarize_luxian_input_profile(
        item.get("luxian_0609_input_profile") or metadata.get("luxian_0609_input_profile")
    )

    profile = {
        "schema_version": "luxian_0609_rule_perf_v1",
        "rule_id": str(item.get("rule_id") or item.get("rule_code") or "").strip(),
        "rule_code": str(item.get("rule_code") or "").strip(),
        "rule_name": str(item.get("rule_name") or "").strip(),
        "source_rule_id": str(item.get("source_rule_id") or metadata.get("selected_execution_rule_id") or "").strip(),
        "record_id": str(item.get("record_id") or "").strip(),
        "visit_id": str(item.get("visit_id") or "").strip(),
        "final_status": str(item.get("status") or item.get("display_status") or "").strip().lower(),
        "executor_type": executor_type or "llm",
        "duration_seconds": round(max(0.0, duration_seconds), 4),
        "duration_basis": str(metadata.get("api_time_basis") or "reported_result_metadata"),
        "llm_call_count": llm_call_count,
        "program_call_count": program_call_count,
        "retry_count": retry_count,
        "provider_error_count": provider_error_count,
        "timeout_count": timeout_count,
        "rate_limit_count": rate_limit_count,
        "pack_retry_attempts": pack_retry_attempts,
        "tokens_total": tokens_total,
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "unattributed_tokens": unattributed_tokens,
        "token_breakdown_complete": unattributed_tokens == 0,
        "context_tokens_estimate": _performance_int(
            metadata.get("context_tokens_estimate") or item.get("context_tokens_estimate")
        ),
        "first_result_latency_seconds": round(
            max(0.0, _performance_float(metadata.get("first_result_latency") or item.get("first_result_latency"))),
            4,
        ),
        "pack_size": _performance_int(metadata.get("pack_size") or item.get("pack_size")),
        "pack_id": str(metadata.get("pack_id") or item.get("pack_id") or "").strip(),
        "cache_hit": bool(metadata.get("cache_hit") is True or item.get("cache_hit") is True),
        "trace_id": str(metadata.get("trace_id") or item.get("trace_id") or "").strip(),
    }
    if input_profile:
        profile["input_profile"] = input_profile
    return profile


def _attach_result_performance_profile(item: Dict[str, Any]) -> Dict[str, Any]:
    profile = _build_result_performance_profile(item)
    item["performance_profile"] = profile
    metadata = item.get("metadata") if isinstance(item.get("metadata"), dict) else {}
    metadata = dict(metadata)
    metadata["performance_profile"] = profile
    item["metadata"] = _sanitize_trace_value(metadata, set(), max_text=1200)
    return item


_LUXIAN_NATIVE_CUSTOMER_HIDDEN_FIELDS = frozenset(
    {
        "prompt_version",
        "model_name",
        "model_version",
        "prompt_strategy",
        "prompt_tokens",
        "completion_tokens",
        "cot_mode",
        "requested_enable_thinking",
        "thinking_heuristic_applied",
        "llm_fallback",
        "performance_profile",
    }
)


def _strip_luxian_native_customer_diagnostics(
    item: Dict[str, Any], *, native_result: bool = False
) -> Dict[str, Any]:
    """0609 原生结果不向客户任务详情暴露无意义的模型诊断字段。"""
    metadata = dict(item.get("metadata") or {})
    if not native_result and str(metadata.get("execution_source") or "").strip() != "lx0609_native":
        return item
    for key in _LUXIAN_NATIVE_CUSTOMER_HIDDEN_FIELDS:
        item.pop(key, None)
        metadata.pop(key, None)
    audit = dict(item.get("audit") or {})
    for key in _LUXIAN_NATIVE_CUSTOMER_HIDDEN_FIELDS:
        audit.pop(key, None)
    item["metadata"] = metadata
    if audit:
        item["audit"] = audit
    else:
        item.pop("audit", None)
    return item


def _build_batch_performance_profile(
    *,
    job_id: str,
    items: List[Dict[str, Any]],
    total_records: int,
    customer_rule_count: int,
    execution_rule_count: int,
    wall_clock_time: float,
    first_result_latency: float,
    actual_llm_pack_call_count: int = 0,
    actual_llm_call_count: Optional[int] = None,
    actual_total_tokens: Optional[int] = None,
    actual_prompt_tokens: Optional[int] = None,
    actual_completion_tokens: Optional[int] = None,
) -> Dict[str, Any]:
    result_profiles = [
        dict(item.get("performance_profile") or _build_result_performance_profile(item))
        for item in items
        if isinstance(item, dict)
    ]
    rule_map: Dict[str, Dict[str, Any]] = {}
    total_duration = 0.0
    total_llm_calls = 0
    total_program_calls = 0
    total_retry_count = 0
    total_provider_errors = 0
    total_timeouts = 0
    total_rate_limits = 0
    total_pack_retries = 0
    total_tokens = 0
    total_prompt_tokens = 0
    total_completion_tokens = 0
    total_context_tokens = 0

    for profile in result_profiles:
        rule_id = str(profile.get("rule_id") or profile.get("rule_code") or "unknown").strip() or "unknown"
        duration = _performance_float(profile.get("duration_seconds"))
        llm_calls = _performance_int(profile.get("llm_call_count"))
        program_calls = _performance_int(profile.get("program_call_count"))
        retry_count = _performance_int(profile.get("retry_count"))
        provider_errors = _performance_int(profile.get("provider_error_count"))
        timeouts = _performance_int(profile.get("timeout_count"))
        rate_limits = _performance_int(profile.get("rate_limit_count"))
        pack_retries = _performance_int(profile.get("pack_retry_attempts"))
        tokens = _performance_int(profile.get("tokens_total"))
        prompt_tokens = _performance_int(profile.get("prompt_tokens"))
        completion_tokens = _performance_int(profile.get("completion_tokens"))
        unattributed_tokens = _performance_int(
            profile.get("unattributed_tokens") or max(0, tokens - prompt_tokens - completion_tokens)
        )
        context_tokens = _performance_int(profile.get("context_tokens_estimate"))
        total_duration += duration
        total_llm_calls += llm_calls
        total_program_calls += program_calls
        total_retry_count += retry_count
        total_provider_errors += provider_errors
        total_timeouts += timeouts
        total_rate_limits += rate_limits
        total_pack_retries += pack_retries
        total_tokens += tokens
        total_prompt_tokens += prompt_tokens
        total_completion_tokens += completion_tokens
        total_context_tokens += context_tokens

        rule_profile = rule_map.setdefault(
            rule_id,
            {
                "rule_id": rule_id,
                "rule_name": str(profile.get("rule_name") or "").strip(),
                "result_count": 0,
                "status_breakdown": {},
                "duration_seconds": 0.0,
                "llm_call_count": 0,
                "program_call_count": 0,
                "retry_count": 0,
                "provider_error_count": 0,
                "timeout_count": 0,
                "rate_limit_count": 0,
                "pack_retry_attempts": 0,
                "tokens_total": 0,
                "prompt_tokens": 0,
                "completion_tokens": 0,
                "unattributed_tokens": 0,
                "context_tokens_estimate": 0,
            },
        )
        rule_profile["result_count"] = int(rule_profile["result_count"] or 0) + 1
        status = str(profile.get("final_status") or "unknown").strip().lower() or "unknown"
        status_breakdown = dict(rule_profile.get("status_breakdown") or {})
        status_breakdown[status] = int(status_breakdown.get(status) or 0) + 1
        rule_profile["status_breakdown"] = status_breakdown
        rule_profile["duration_seconds"] = round(float(rule_profile["duration_seconds"] or 0.0) + duration, 4)
        rule_profile["llm_call_count"] = int(rule_profile["llm_call_count"] or 0) + llm_calls
        rule_profile["program_call_count"] = int(rule_profile["program_call_count"] or 0) + program_calls
        rule_profile["retry_count"] = int(rule_profile["retry_count"] or 0) + retry_count
        rule_profile["provider_error_count"] = int(rule_profile["provider_error_count"] or 0) + provider_errors
        rule_profile["timeout_count"] = int(rule_profile["timeout_count"] or 0) + timeouts
        rule_profile["rate_limit_count"] = int(rule_profile["rate_limit_count"] or 0) + rate_limits
        rule_profile["pack_retry_attempts"] = int(rule_profile["pack_retry_attempts"] or 0) + pack_retries
        rule_profile["tokens_total"] = int(rule_profile["tokens_total"] or 0) + tokens
        rule_profile["prompt_tokens"] = int(rule_profile["prompt_tokens"] or 0) + prompt_tokens
        rule_profile["completion_tokens"] = int(rule_profile["completion_tokens"] or 0) + completion_tokens
        rule_profile["unattributed_tokens"] = int(rule_profile["unattributed_tokens"] or 0) + unattributed_tokens
        rule_profile["context_tokens_estimate"] = int(rule_profile["context_tokens_estimate"] or 0) + context_tokens

    rules = list(rule_map.values())
    for rule_profile in rules:
        result_count = max(1, int(rule_profile.get("result_count") or 0))
        rule_profile["avg_duration_seconds"] = round(float(rule_profile.get("duration_seconds") or 0.0) / result_count, 4)
        rule_profile["avg_tokens_total"] = round(float(rule_profile.get("tokens_total") or 0) / result_count, 2)
        rule_profile["token_breakdown_complete"] = _performance_int(rule_profile.get("unattributed_tokens")) == 0
    rules.sort(
        key=lambda item: (
            float(item.get("duration_seconds") or 0.0),
            int(item.get("tokens_total") or 0),
            int(item.get("retry_count") or 0),
        ),
        reverse=True,
    )
    slow_results = sorted(
        result_profiles,
        key=lambda item: (
            _performance_float(item.get("duration_seconds")),
            _performance_int(item.get("tokens_total")),
            _performance_int(item.get("retry_count")),
        ),
        reverse=True,
    )[:20]
    input_profile_summary = _build_batch_input_profile_summary(result_profiles)
    authoritative_llm_calls = (
        total_llm_calls
        if actual_llm_call_count is None
        else _performance_int(actual_llm_call_count)
    )
    authoritative_tokens = (
        total_tokens
        if actual_total_tokens is None
        else _performance_int(actual_total_tokens)
    )
    authoritative_prompt_tokens = (
        total_prompt_tokens
        if actual_prompt_tokens is None
        else _performance_int(actual_prompt_tokens)
    )
    authoritative_completion_tokens = (
        total_completion_tokens
        if actual_completion_tokens is None
        else _performance_int(actual_completion_tokens)
    )
    authoritative_unattributed_tokens = max(
        0,
        authoritative_tokens
        - authoritative_prompt_tokens
        - authoritative_completion_tokens,
    )

    batch_profile = {
        "schema_version": "luxian_0609_job_perf_v1",
        "job_id": job_id,
        "basis": "per_result_metadata",
        "total_records": int(total_records or 0),
        "customer_rule_count": int(customer_rule_count or 0),
        "execution_rule_count": int(execution_rule_count or 0),
        "result_count": len(result_profiles),
        "wall_clock_time_seconds": round(max(0.0, float(wall_clock_time or 0.0)), 4),
        "sum_rule_duration_seconds": round(total_duration, 4),
        # 兼容历史分摊值，但禁止把它当作独立规则的实测耗时排名。
        "rule_duration_basis": "allocated_or_reported_metadata",
        "slow_rule_ranking_is_measured": False,
        "first_result_latency_seconds": round(max(0.0, float(first_result_latency or 0.0)), 4),
        "llm_call_count": authoritative_llm_calls,
        "llm_call_count_basis": (
            "record_execution_attribution"
            if actual_llm_call_count is not None
            else "result_participation_count"
        ),
        "actual_llm_pack_call_count": int(actual_llm_pack_call_count or 0),
        "program_call_count": total_program_calls,
        "retry_count": total_retry_count,
        "provider_error_count": total_provider_errors,
        "timeout_count": total_timeouts,
        "rate_limit_count": total_rate_limits,
        "pack_retry_attempts": total_pack_retries,
        "tokens_total": authoritative_tokens,
        "prompt_tokens": authoritative_prompt_tokens,
        "completion_tokens": authoritative_completion_tokens,
        "unattributed_tokens": authoritative_unattributed_tokens,
        "token_breakdown_complete": authoritative_unattributed_tokens == 0,
        "context_tokens_estimate": total_context_tokens,
        "rules": rules,
        "slow_rules": rules[:12],
        "slow_results": slow_results,
        "results": result_profiles,
    }
    if input_profile_summary:
        batch_profile["input_profile"] = input_profile_summary
    return batch_profile


_TRACE_SENSITIVE_KEYS = {
    "prompt",
    "raw_response",
    "raw_output",
    "llm_raw_output",
    "provider_response",
    "embedding",
    "medical_text",
    "record_content",
    "documents",
    "bundle",
    "internal_data",
    "vector",
}


def _sanitize_trace_value(
    value: Any,
    removed_keys: set[str],
    *,
    max_text: int = 1200,
    list_limit: int = 50,
    list_limits: Optional[Dict[str, int]] = None,
) -> Any:
    if isinstance(value, dict):
        sanitized: Dict[str, Any] = {}
        for key, item in value.items():
            normalized_key = str(key or "").strip().lower()
            if normalized_key in _TRACE_SENSITIVE_KEYS:
                removed_keys.add(str(key))
                continue
            child_list_limit = (
                list_limits.get(normalized_key, list_limit)
                if list_limits is not None
                else list_limit
            )
            sanitized[str(key)] = _sanitize_trace_value(
                item,
                removed_keys,
                max_text=max_text,
                list_limit=child_list_limit,
                list_limits=list_limits,
            )
        return sanitized
    if isinstance(value, list):
        return [
            _sanitize_trace_value(
                item,
                removed_keys,
                max_text=max_text,
                list_limit=list_limit,
                list_limits=list_limits,
            )
            for item in value[:list_limit]
        ]
    if isinstance(value, str):
        text = value.strip()
        if len(text) > max_text:
            return f"{text[:max_text]}...（已截断）"
        return text
    return value


def _result_diagnostic_trace(
    item: Dict[str, Any],
    metadata: Dict[str, Any],
    *,
    evidence_items: Optional[List[Dict[str, Any]]] = None,
    status: Optional[str] = None,
) -> Dict[str, Any]:
    existing = item.get("diagnostic_trace")
    if not isinstance(existing, dict):
        existing = metadata.get("diagnostic_trace") if isinstance(metadata.get("diagnostic_trace"), dict) else {}
    source_evidence = (
        item.get("source_evidence")
        or existing.get("source_evidence")
        or (evidence_items if evidence_items else None)
        or item.get("evidence")
        or ""
    )
    trigger_decision = (
        item.get("trigger_decision")
        or existing.get("trigger_decision")
        or metadata.get("trigger_decision")
        or {
            key: metadata.get(key)
            for key in (
                "trigger_gate_status",
                "trigger_gate_reason",
                "trigger_gate_matched_keywords",
                "data_gap_fields",
            )
            if metadata.get(key) is not None
        }
    )
    source_results = (
        existing.get("source_execution_results")
        or metadata.get("source_execution_results")
        or item.get("source_execution_results")
        or []
    )
    if source_results and not isinstance(source_results, list):
        source_results = [source_results]
    source_rule_id = str(
        item.get("source_rule_id")
        or existing.get("source_rule_id")
        or metadata.get("selected_execution_rule_id")
        or item.get("rule_id")
        or item.get("rule_code")
        or ""
    ).strip()
    source_status = str(
        item.get("source_status")
        or existing.get("source_status")
        or status
        or item.get("status")
        or ""
    ).strip()
    source_conclusion = str(
        item.get("source_conclusion")
        or existing.get("source_conclusion")
        or item.get("findings")
        or item.get("conclusion")
        or ""
    ).strip()
    trace = {
        **existing,
        "source_rule_id": source_rule_id,
        "source_status": source_status,
        "source_conclusion": source_conclusion,
        "source_evidence": source_evidence,
        "trigger_decision": trigger_decision if isinstance(trigger_decision, dict) else {},
        "aggregation_reason": str(
            item.get("aggregation_reason")
            or existing.get("aggregation_reason")
            or metadata.get("aggregation_reason")
            or metadata.get("aggregation_source")
            or ""
        ),
        "postprocess_reason": str(
            item.get("postprocess_reason")
            or existing.get("postprocess_reason")
            or metadata.get("postprocess_reason")
            or ""
        ),
        "source_execution_results": source_results,
    }
    semantic_snapshot = metadata.get("diagnostic_semantic_snapshot")
    if isinstance(semantic_snapshot, dict):
        trace["semantic_fact_snapshot"] = semantic_snapshot
    removed_keys: set[str] = set()
    return _sanitize_trace_value(trace, removed_keys)


LX0609_LEASE_HEARTBEAT_SECONDS = 30


async def _cancel_pending_batch_tasks(tasks: List[asyncio.Task[Any]]) -> None:
    """取消并回收批内病例任务，避免父协程退出后继续发起模型调用。"""

    for task in tasks:
        if not task.done():
            task.cancel()
    await asyncio.gather(*tasks, return_exceptions=True)


def _renew_luxian_0609_lease_until_stopped(
    *, workspace: CustomQCWorkspaceService, job_id: str,
    attempt_filters_json: str, stopped: threading.Event,
) -> None:
    """独立于模型请求事件循环续约；失去当前代次后停止心跳。"""

    while not stopped.wait(LX0609_LEASE_HEARTBEAT_SECONDS):
        try:
            if not workspace.renew_luxian_0609_batch_job_lease(
                job_id=job_id, attempt_filters_json=attempt_filters_json,
            ):
                return
        except Exception:
            logger.exception("LX0609 任务续约失败: job_id=%s", job_id)


@observe_worker_timing
@diagnostic_job_lifecycle
@bound_job
async def run_sichuan_workspace_batch_job(
    job_id: str,
    *,
    workspace: CustomQCWorkspaceService,
    qc_service_provider: Callable[[], Awaitable[SichuanQCService]],
    diagnostic_capture: DiagnosticJobCapture | None = None,
    record_concurrency_limit: int | None = None,
    external_cancellation_check: Callable[[], bool] | None = None,
    expected_dispatch_generation: int | None = None,
) -> None:
    job_wall_started = time.perf_counter()
    job = workspace.get_batch_job_for_processing(job_id=job_id)
    if not job:
        return
    if str(job.get("job_kind") or "").strip().lower() == "parent":
        logger.info("跳过泸县0609父任务执行，仅执行其规则族子任务: job_id=%s", job_id)
        return

    formal_0609_job = (job.get("filters") or {}).get("rule_set_key") == LUXIAN_0609_RULE_SET_KEY
    claim_filters_json = job.get("_claim_filters_json")
    attempt_filters_json: str | None = None
    attempt_kwargs: dict[str, str] = {}
    lease_stop: threading.Event | None = None
    identity_collector: _Luxian0609IdentityCollector | None = None
    try:
        # HTTP 门禁之外在所有实际质控 Worker 入口统一验签，阻止旧队列或内部调用绕过授权。
        # 不存在的任务及父任务已在上方返回，不触发授权检查。
        get_product_activation_service().enforce()
        claim = workspace.mark_batch_job_running(
            job_id=job_id,
            **(
                {"expected_dispatch_generation": expected_dispatch_generation}
                if expected_dispatch_generation is not None
                else {}
            ),
        )
        if not claim:
            return
        if isinstance(claim, str):
            attempt_filters_json = claim
            attempt_kwargs = {"attempt_filters_json": claim}
            if callable(getattr(workspace, "renew_luxian_0609_batch_job_lease", None)):
                lease_stop = threading.Event()
                threading.Thread(
                    target=_renew_luxian_0609_lease_until_stopped,
                    kwargs={
                        "workspace": workspace,
                        "job_id": job_id,
                        "attempt_filters_json": claim,
                        "stopped": lease_stop,
                    },
                    name="lx0609-task-lease",
                    daemon=True,
                ).start()
        raise_if_cancelled(external_cancellation_check)
        qc_service = await qc_service_provider()
        raise_if_cancelled(external_cancellation_check)
        if attempt_filters_json is not None and workspace.is_batch_job_canceled_or_missing(
            job_id=job_id, **attempt_kwargs
        ):
            return
        current = workspace.get_batch_job_for_processing(job_id=job_id) or job
        filters = dict(current.get("filters") or {})
        if filters.get("rule_set_key") == LUXIAN_0609_RULE_SET_KEY:
            filters["scoped_customer_rule_ids"] = frozen_luxian_0609_delivery_scope(filters)
        filters.pop(LX0609_ATTEMPT_FILTER_KEY, None)
        filters.pop(LX0609_LEASE_FILTER_KEY, None)
        failed_rule_retry_scope = (
            dict(filters.get(FAILED_RULE_RETRY_FILTER_KEY) or {})
            if isinstance(filters.get(FAILED_RULE_RETRY_FILTER_KEY), dict)
            else {}
        )
        is_failed_rule_retry = (
            failed_rule_retry_scope.get("schema_version")
            == FAILED_RULE_RETRY_SCHEMA_VERSION
        )
        if (
            filters.get("rule_set_key") == LUXIAN_0609_RULE_SET_KEY
            and is_failed_rule_retry
            and not set(failed_rule_retry_scope.get("rule_ids") or []).issubset(
                filters["scoped_customer_rule_ids"]
            )
        ):
            raise ValueError("失败规则超出原任务冻结范围，请新建质控任务")
        retry_base_items = list(current.get("items") or []) if is_failed_rule_retry else []
        retry_base_failures = (
            list(current.get("failed_records") or []) if is_failed_rule_retry else []
        )
        retry_base_summary = (
            dict(current.get("summary") or {}) if is_failed_rule_retry else {}
        )
        record_evaluation_snapshot_by_id = {
            str(item.get("record_key") or item.get("record_id") or "").strip(): dict(item)
            for item in list(filters.get("record_evaluation_snapshot") or [])
            if isinstance(item, dict)
            and str(item.get("record_key") or item.get("record_id") or "").strip()
        }
        requested_rule_ids = [
            str(item).strip().upper()
            for item in (
                failed_rule_retry_scope.get("rule_ids")
                if is_failed_rule_retry
                else filters.get("rule_ids")
            ) or []
            if str(item).strip()
        ]
        gate_only_customer_rule_ids_for_validation = [
            str(item).strip()
            for item in (filters.get("gate_only_customer_rule_ids") or [])
            if str(item).strip()
        ]
        paused_customer_rule_ids_for_validation = [
            str(item).strip()
            for item in (filters.get("paused_customer_rule_ids") or [])
            if str(item).strip()
        ]
        if (
            not requested_rule_ids
            and not gate_only_customer_rule_ids_for_validation
            and not paused_customer_rule_ids_for_validation
        ):
            raise ValueError("批量任务缺少 rule_ids")
        rule_set_key = str(filters.get("rule_set_key") or "").strip()
        if rule_set_key == LUXIAN_0609_RULE_SET_KEY:
            identity_collector = _Luxian0609IdentityCollector()
        rule_set_name = str(filters.get("rule_set_name") or "").strip()
        rule_set_version = str(filters.get("rule_set_version") or "").strip()
        _assert_luxian_0609_formal_customer_rule_ids(
            rule_set_key=rule_set_key,
            rule_ids=tuple(
                requested_rule_ids
                + gate_only_customer_rule_ids_for_validation
                + paused_customer_rule_ids_for_validation
            ),
            context=f"workspace_batch_job:{job_id}",
        )
        validation_mode = str(filters.get("validation_mode") or "").strip().lower() or "sc"
        programmatic_rule_set = get_sample_programmatic_rule_set()
        is_programmatic_mode = (
            validation_mode == "programmatic" or rule_set_key == programmatic_rule_set.key
        )
        settings = resolve_mainline_rule_decision_settings(get_settings())
        if rule_set_key == LUXIAN_0609_RULE_SET_KEY:
            # 正式服务由路由共享并允许热重载。领取后复制客户端，保证本任务运行期间
            # 一审、二审模型及推理参数不会被另一个请求原地改写。测试替身仍由注入方负责。
            if isinstance(qc_service, SichuanQCService) and isinstance(
                getattr(qc_service, "client", None), SichuanQCLLMClient
            ):
                qc_service = qc_service.isolated_luxian_0609_runtime(
                    # 按原接纳范围判断，批量补跑剩一份时仍保留批量预算。
                    single_record=bool(
                        filters.get("sample_pool_id")
                        and len(filters.get("record_refs") or []) == 1
                        and not current.get("parent_job_id")
                    ),
                )
            assert_luxian_0609_task_settings_match(
                filters.get(LX0609_TASK_SETTINGS_FILTER_KEY), settings,
            )
            assert_luxian_0609_task_runtime_match(
                filters.get(LX0609_TASK_RUNTIME_FILTER_KEY), qc_service,
            )
            assert_luxian_0609_customer_native_delivery_ready(
                settings,
                context=f"workspace_batch_job:{job_id}",
            )
        native_requested_rule_ids = _ordered_luxian_0609_customer_rule_ids(
            requested_rule_ids
        )
        is_direct_native_selection = bool(
            rule_set_key == LUXIAN_0609_RULE_SET_KEY
            and requested_rule_ids
            and len(native_requested_rule_ids) == len(set(requested_rule_ids))
        )
        formal_package_plan = None
        if is_direct_native_selection:
            formal_package_plan = build_luxian_0609_package_plan_from_settings(
                inventory=load_luxian_0609_dependency_inventory(),
                selected_rule_ids=native_requested_rule_ids,
                settings=settings,
            )
            assert_luxian_0609_formal_package_plan_native_only(
                formal_package_plan,
                context=f"workspace_batch_job:{job_id}",
            )
        native_direct_enabled = bool(
            is_direct_native_selection
            and getattr(settings, "LUXIAN_0609_CUSTOMER_AGGREGATION_ENABLED", False)
        )
        compatibility_rule_ids = (
            formal_package_plan.compatibility_execution_rule_ids
            if is_direct_native_selection
            else ()
        )
        rule_ids = (
            list(native_requested_rule_ids)
            if native_direct_enabled
            else list(_luxian_0609_rollback_rule_ids(native_requested_rule_ids))
            if is_direct_native_selection
            else requested_rule_ids
        )
        execution_strategy = normalize_execution_strategy(filters.get("execution_strategy"))
        quality_profile = _normalize_quality_profile(filters.get("quality_profile"))
        bucket_strategy = _normalize_bucket_strategy(filters.get("bucket_strategy"))
        batch_output_mode = _normalize_batch_output_mode(
            filters.get("batch_output_mode"),
            quality_profile=quality_profile,
        )
        enable_selective_refine = bool(filters.get("enable_selective_refine") is True)
        refine_confidence_threshold = _normalize_refine_threshold(filters.get("refine_confidence_threshold"))
        max_refine_candidates = _normalize_max_refine_candidates(filters.get("max_refine_candidates"))
        run_mode = _normalize_run_mode(current.get("run_mode") or filters.get("run_mode"))
        configured_record_concurrency = max(
            1,
            int(
                getattr(
                    getattr(qc_service, "client", None),
                    "max_parallel_records",
                    getattr(settings, "QC_BATCH_RECORD_MAX_CONCURRENCY", 16),
                )
            ),
        )
        max_parallel_records = min(
            configured_record_concurrency,
            max(
                1,
                int(
                    filters.get("max_parallel_records")
                    or configured_record_concurrency
                ),
            ),
        )
        if record_concurrency_limit is not None:
            max_parallel_records = min(
                max_parallel_records,
                max(1, int(record_concurrency_limit)),
            )
        if compatibility_rule_ids:
            _enforce_sc_source_guard(
                qc_service,
                context=f"workspace_batch_job:{job_id}",
                rule_ids=list(compatibility_rule_ids),
                block_batch=True,
            )

        persisted_record_refs = (
            failed_rule_retry_scope.get("record_refs")
            if is_failed_rule_retry
            else filters.get("record_refs")
        )
        has_persisted_record_refs = isinstance(persisted_record_refs, list) and bool(
            persisted_record_refs
        )
        is_sample_pool_job = bool(str(filters.get("sample_pool_id") or "").strip())
        if is_sample_pool_job and not has_persisted_record_refs:
            raise ValueError(
                "样本池任务缺少 filters.record_refs，拒绝按 record_ids 回退"
            )
        records = workspace.collect_records(
            scope=str(current.get("scope") or "all"),
            department=filters.get("department"),
            doctor=filters.get("doctor"),
            date_field=filters.get("date_field") or "admission",
            start_date=filters.get("start_date"),
            end_date=filters.get("end_date"),
            keyword=filters.get("keyword"),
            record_ids=None if has_persisted_record_refs else current.get("record_ids") or None,
            record_refs=persisted_record_refs if has_persisted_record_refs else None,
            **({"_private_identity_collector": identity_collector.capture} if identity_collector is not None else {}),
        )
        if rule_set_key == LUXIAN_0609_RULE_SET_KEY and has_persisted_record_refs:
            accepted_refs = set(normalize_case_refs(persisted_record_refs))
            collected_refs = set(case_refs_from_records(records)) if records else set()
            if collected_refs != accepted_refs:
                raise ValueError("已接纳病例范围与当前重取结果不一致，拒绝执行部分病历")
        workspace.update_batch_job_progress(
            job_id=job_id,
            **attempt_kwargs,
            step_key="prepare",
            rule_index=0,
            rule_count=max(1, len(rule_ids)),
            processed_records=0,
            total_records=len(records),
            summary_patch={
                "rule_count": max(1, len(rule_ids)),
                "total_records": len(records),
            },
        )
        hydrated_records = workspace.hydrate_records_with_medical_text(records)
        if identity_collector is not None:
            for record in hydrated_records:
                identity_collector.capture_hydrated_record(record)
        total_records = len(hydrated_records)
        if total_records == 0:
            raise ValueError("批量任务未收集到可执行病历，请确认样本病历已同步到当前病历库")
        total_rules = max(1, len(rule_ids))

        all_items: List[Dict[str, Any]] = []
        all_failed_records: List[Dict[str, Any]] = []
        issue_record_ids: set[str] = set()
        uncertain_record_ids: set[str] = set()
        failed_record_ids: set[str] = set()
        total_tokens = 0
        total_prompt_tokens = 0
        total_completion_tokens = 0
        total_processing_time = 0.0
        first_result_latency: Optional[float] = None
        first_result_source = ""
        if is_failed_rule_retry and retry_base_summary.get("first_result_source") in {
            "validated_family_write", "validated_record_write",
        }:
            prior_latency = float(retry_base_summary.get("first_result_latency") or 0.0)
            if prior_latency > 0:
                first_result_latency = prior_latency
                first_result_source = retry_base_summary["first_result_source"]
        live_buffer = LiveResultBuffer()
        last_live_flush = {"result": 0.0, "phase": 0.0}
        executor_program = 0
        executor_llm = 0
        executor_native = 0
        actual_llm_call_count = 0
        cache_hit = 0
        cache_miss = 0
        cot_summary_total = {
            "explicit_calls": 0,
            "implicit_calls": 0,
            "disabled_calls": 0,
            "thinking_heuristic_calls": 0,
            "response_has_think_tags_calls": 0,
            "response_has_reasoning_content_calls": 0,
        }
        total_pack_count = 0
        total_pack_size_weighted = 0
        total_pack_fallback_count = 0
        total_pack_parse_retry_count = 0
        total_single_rule_retries = 0
        total_context_tokens_estimate = 0
        total_refined_rule_count = 0
        model_execution_stats_total: Optional[Dict[str, int]] = None
        usage_observation_complete: Optional[bool] = None
        usage_unknown_executor_keys: set[str] = set()
        refine_summary_total: Dict[str, Any] = {
            "enabled": enable_selective_refine,
            "candidate_count": 0,
            "refined_rule_count": 0,
            "refine_failed_count": 0,
            "refine_reasons": {},
        }
        shadow_evaluation_summary: Dict[str, Dict[str, Any]] = {}

        # 预加载规则，后续按病历一次性评估全部规则，再回填到每条规则结果。
        # 这样可触发 orchestrator 的分桶并发，避免规则级外层串行瓶颈。
        rule_states: Dict[str, Dict[str, Any]] = {}
        valid_rule_ids: List[str] = []
        for rule_id in rule_ids:
            rule = (
                get_luxian_0609_rule(rule_id)
                if native_direct_enabled and rule_id in set(native_requested_rule_ids)
                else qc_service.get_rule_by_id(rule_id)
            )
            if rule and is_programmatic_mode:
                rule = apply_programmatic_rule_runtime_overrides(rule)
            rule_name = str((rule or {}).get("name") or rule_id)
            rule_code = str((rule or {}).get("rule_code") or rule_id)
            rule_job_id = str(uuid.uuid4())
            state = {
                "rule_id": rule_id,
                "rule": rule,
                "rule_name": rule_name,
                "rule_code": rule_code,
                "rule_job_id": rule_job_id,
                "items": [],
                "failed_records": [],
                "total_tokens": 0,
                "total_processing_time": 0.0,
                "executor_program": 0,
                "executor_llm": 0,
                "executor_native": 0,
            }
            if not rule:
                state["failed_records"].append(
                    {
                        "rule_job_id": rule_job_id,
                        "rule_id": rule_id,
                        "rule_code": rule_code,
                        "rule_name": rule_name,
                        "error_phase": "rule_lookup",
                        "error": f"未找到规则: {rule_id}",
                    }
                )
            else:
                valid_rule_ids.append(rule_id)
            rule_states[rule_id] = state
        valid_rules = [  # noqa: F841 - 保留迁移前的完整规则快照构造行为
            dict(rule_states[rule_id]["rule"])
            for rule_id in valid_rule_ids
            if isinstance(rule_states[rule_id].get("rule"), dict)
        ]
        use_luxian_customer_results = bool(
            rule_set_key == LUXIAN_0609_RULE_SET_KEY
            and settings.LUXIAN_0609_CUSTOMER_AGGREGATION_ENABLED
        )
        scoped_customer_rule_ids = {
            str(rule_id or "").strip().upper()
            for rule_id in list(
                failed_rule_retry_scope.get("rule_ids")
                if is_failed_rule_retry
                else filters.get("scoped_customer_rule_ids")
                or []
            )
            if str(rule_id or "").strip()
        }
        gate_only_customer_rule_ids = {
            str(rule_id or "").strip().upper()
            for rule_id in list(filters.get("gate_only_customer_rule_ids") or [])
            if str(rule_id or "").strip()
        }
        paused_customer_rule_ids = {
            str(rule_id or "").strip().upper()
            for rule_id in list(filters.get("paused_customer_rule_ids") or [])
            if str(rule_id or "").strip()
        }
        if use_luxian_customer_results:
            _, phase_pending_rule_ids = partition_luxian_0609_rule_scope(
                tuple(
                    str(wrapper.get("rule_id") or wrapper.get("rule_code") or "").strip().upper()
                    for wrapper in load_luxian_0609_rules()
                    if str(wrapper.get("rule_id") or wrapper.get("rule_code") or "").strip()
                )
            )
            paused_customer_rule_ids.update(phase_pending_rule_ids)
        output_rule_states: Dict[str, Dict[str, Any]] = rule_states
        output_rule_ids: List[str] = list(valid_rule_ids)
        if use_luxian_customer_results:
            output_rule_states = {}
            output_rule_ids = []
            for wrapper in load_luxian_0609_rules():
                customer_rule_id = str(wrapper.get("rule_id") or wrapper.get("rule_code") or "").strip().upper()
                if not customer_rule_id:
                    continue
                if customer_rule_id in LUXIAN_0609_CUSTOMER_EXCLUDED_RULE_IDS:
                    continue
                if scoped_customer_rule_ids and customer_rule_id not in scoped_customer_rule_ids:
                    continue
                output_rule_ids.append(customer_rule_id)
                output_rule_states[customer_rule_id] = {
                    "rule_id": customer_rule_id,
                    "rule": wrapper,
                    "rule_name": str(wrapper.get("name") or wrapper.get("rule_name") or customer_rule_id),
                    "rule_code": customer_rule_id,
                    "rule_job_id": str(uuid.uuid4()),
                    "items": [],
                    "failed_records": [],
                    "total_tokens": 0,
                    "total_processing_time": 0.0,
                    "executor_program": 0,
                    "executor_llm": 0,
                    "executor_native": 0,
                }
            total_rules = max(1, len(output_rule_ids))
        record_rule_map_raw = dict(
            failed_rule_retry_scope.get("record_rule_map")
            if is_failed_rule_retry
            else filters.get("record_rule_map")
            or {}
        )
        record_rule_map: Dict[str, List[str]] = {}
        for raw_record_id, raw_rule_ids in record_rule_map_raw.items():
            normalized_record_id = str(raw_record_id or "").strip()
            if not normalized_record_id:
                continue
            requested_record_rule_ids = [
                str(item or "").strip().upper()
                for item in list(raw_rule_ids or [])
                if str(item or "").strip()
            ]
            if is_direct_native_selection and not native_direct_enabled:
                requested_record_rule_ids = list(
                    _luxian_0609_rollback_rule_ids(requested_record_rule_ids)
                )
            normalized_rule_ids = [
                rule_id
                for rule_id in (
                    str(item or "").strip().upper()
                    for item in requested_record_rule_ids
                )
                if rule_id in rule_states
            ]
            if normalized_rule_ids:
                record_rule_map[normalized_record_id] = normalized_rule_ids
        if rule_set_key == LUXIAN_0609_RULE_SET_KEY and record_rule_map_raw:
            for record in hydrated_records:
                record_id = str(record.get("record_id") or record.get("visit_id") or "").strip()
                visit_id = str(record.get("visit_id") or record_id).strip()
                record_ref = CaseRef(
                    str(record.get("institute_id") or "").strip(),
                    str(record.get("patient_id") or "").strip(),
                    visit_id,
                )
                record_key = record_ref.as_key() if all(record_ref) else record_id
                if not any(
                    key in record_rule_map for key in (record_key, visit_id, record_id)
                ):
                    raise ValueError("LX0609任务逐病例规则范围不完整，拒绝回退为整批规则")
        prefer_rule_level_visit_eval = (
            validation_mode == "sc"
            and (
                str(filters.get("source") or "").strip().lower().startswith("manual_problem_sample_pool")
                or bool(record_rule_map)
            )
        )
        should_postprocess_job = _should_postprocess_formal_qc_results(
            rule_set_key=rule_set_key,
            validation_mode=validation_mode,
            current_scope=str(current.get("scope") or "all"),
            execution_strategy=execution_strategy,
            bucket_strategy=bucket_strategy,
        )
        enable_incremental_results = bool(filters.get("sample_pool_id"))
        job_started_at = datetime.now(timezone.utc)
        completed_records_state = {"count": 0}
        active_records_state = {"count": 0}
        effective_parallel_records = (
            min(max_parallel_records, total_records)
            if run_mode == "parallel" and total_records > 1
            else 1
        )

        def _record_runtime_progress(processed_records_count: int) -> Dict[str, int]:
            processed_count = min(total_records, max(0, int(processed_records_count)))
            active_count = min(
                max(0, total_records - processed_count),
                max(0, int(active_records_state["count"])),
            )
            return {
                "max_parallel_records": effective_parallel_records,
                "active_record_count": active_count,
                "queued_record_count": max(
                    0,
                    total_records - processed_count - active_count,
                ),
            }

        def _is_cancelled() -> bool:
            if external_cancellation_check is not None and bool(
                external_cancellation_check()
            ):
                return True
            lightweight_check = getattr(
                workspace,
                "is_batch_job_canceled_or_missing",
                None,
            )
            if callable(lightweight_check):
                return bool(lightweight_check(job_id=job_id, **attempt_kwargs))
            latest = workspace.get_batch_job_for_processing(job_id=job_id)
            if not latest:
                return True
            return str(latest.get("status") or "").strip().lower() == "canceled"

        def _raise_if_cancelled() -> None:
            raise_if_cancelled(_is_cancelled)

        def _record_ids_for_item_status(status: str) -> set[str]:
            normalized_status = str(status or "").strip().lower()
            return {
                str(item.get("record_key") or item.get("record_id") or "").strip()
                for item in all_items
                if str(item.get("status") or "").strip().lower() == normalized_status
                and str(item.get("record_key") or item.get("record_id") or "").strip()
            }

        def _build_progress_patch(processed_records_count: int) -> Dict[str, Any]:
            record_status_counts = _build_record_status_counts(
                total_records=processed_records_count,
                issue_record_ids=issue_record_ids,
                uncertain_record_ids=uncertain_record_ids,
                data_gap_record_ids=_record_ids_for_item_status("data_gap"),
                failed_record_ids=failed_record_ids,
                not_applicable_record_ids=_records_with_only_status(all_items, "not_applicable"),
            )
            result_status_counts = _build_item_status_counts(all_items)
            patch: Dict[str, Any] = {
                "rule_set_key": rule_set_key,
                "rule_set_name": rule_set_name,
                "rule_set_version": rule_set_version,
                "execution_strategy": execution_strategy,
                "quality_profile": quality_profile,
                "bucket_strategy": bucket_strategy,
                "batch_output_mode": batch_output_mode,
                "enable_selective_refine": enable_selective_refine,
                "refine_confidence_threshold": refine_confidence_threshold,
                "max_refine_candidates": max_refine_candidates,
                "run_mode": run_mode,
                "rule_count": total_rules,
                "total_records": total_records,
                "success_count": max(0, processed_records_count - len(failed_record_ids)),
                "failed_count": len(all_failed_records),
                "failed_record_count": len(failed_record_ids),
                "issue_records": len(issue_record_ids),
                "uncertain_records": len(uncertain_record_ids),
                "data_quality_gap_records": record_status_counts["data_gap"],
                "not_applicable_records": record_status_counts["not_applicable"],
                "compliant_records": record_status_counts["compliant"],
                "record_status_breakdown": record_status_counts,
                "status_breakdown": result_status_counts,
                "total_tokens": int(total_tokens),
                "total_processing_time": float(total_processing_time),
                "executor_breakdown": {
                    "program": executor_program,
                    "llm": executor_llm,
                    "native": executor_native,
                },
                "cache_breakdown": {"hit": cache_hit, "miss": cache_miss},
            }
            model_execution_summary = _build_luxian_model_execution_summary(
                model_execution_stats_total
            )
            if model_execution_summary is not None:
                patch["model_execution_stats"] = model_execution_summary
            if use_luxian_customer_results and isinstance(usage_observation_complete, bool):
                patch["luxian_0609_usage_observation_complete"] = usage_observation_complete
                patch["luxian_0609_usage_unknown_executor_keys"] = sorted(usage_unknown_executor_keys)
            return patch

        def _item_is_confirmed_defect(item: Dict[str, Any]) -> bool:
            if should_postprocess_job:
                return _safe_bool(item.get("can_show_as_defect")) or str(item.get("display_status") or "") == "confirmed_defect"
            # AI 建议态只进入待复核，不得混入客户确认缺陷统计。
            return str(item.get("status") or "") == "non_compliant"

        def _item_needs_review(item: Dict[str, Any]) -> bool:
            if should_postprocess_job:
                return False
            return str(item.get("status") or "") in {
                "uncertain",
                "ai_suggested_non_compliant",
            }

        def _item_data_quality_gap(item: Dict[str, Any]) -> bool:
            if str(item.get("status") or "") == "data_gap":
                return True
            return should_postprocess_job and str(item.get("display_status") or "") == "data_quality_gap"

        def _item_rejected_by_system(item: Dict[str, Any]) -> bool:
            return should_postprocess_job and str(item.get("display_status") or "") == "rejected_by_system"

        def _build_rule_results_snapshot(
            *,
            processed_records_count: int,
            final: bool = False,
        ) -> List[Dict[str, Any]]:
            effective_total_records = total_records if final else max(0, processed_records_count)
            rule_results_snapshot: List[Dict[str, Any]] = []
            for rule_index, rule_id in enumerate(output_rule_ids):
                state = output_rule_states[rule_id]
                rule_items = list(state.get("items") or [])
                rule_failed = list(state.get("failed_records") or [])
                rule_failed_record_ids = {
                    str(item.get("record_key") or item.get("record_id") or "").strip()
                    for item in rule_failed
                    if str(item.get("record_key") or item.get("record_id") or "").strip()
                }
                confirmed_record_ids = {
                    str(item.get("record_key") or item.get("record_id") or "")
                    for item in rule_items
                    if _item_is_confirmed_defect(item)
                }
                uncertain_record_ids_for_rule = {
                    str(item.get("record_key") or item.get("record_id") or "")
                    for item in rule_items
                    if _item_needs_review(item)
                }
                data_gap_record_ids_for_rule = {
                    str(item.get("record_key") or item.get("record_id") or "")
                    for item in rule_items
                    if _item_data_quality_gap(item)
                }
                rejected_record_ids_for_rule = {
                    str(item.get("record_key") or item.get("record_id") or "")
                    for item in rule_items
                    if _item_rejected_by_system(item)
                }
                not_applicable_record_ids_for_rule = {
                    str(item.get("record_key") or item.get("record_id") or "")
                    for item in rule_items
                    if str(item.get("status") or "").strip().lower() == "not_applicable"
                }
                not_applicable_record_ids_for_rule.difference_update(
                    confirmed_record_ids,
                    uncertain_record_ids_for_rule,
                    data_gap_record_ids_for_rule,
                    rejected_record_ids_for_rule,
                    rule_failed_record_ids,
                )
                # 策略暂停是未执行，不是成功的医学合规结论。
                not_executed_record_ids_for_rule = {
                    str(item.get("record_key") or item.get("record_id") or "")
                    for item in rule_items
                    if str(item.get("status") or "").strip().lower() == "not_executed"
                }
                not_executed_record_ids_for_rule.difference_update(
                    confirmed_record_ids, uncertain_record_ids_for_rule,
                    data_gap_record_ids_for_rule, rejected_record_ids_for_rule,
                    not_applicable_record_ids_for_rule, rule_failed_record_ids,
                )
                rule_summary = {
                    "total_records": effective_total_records,
                    "success_count": max(0, effective_total_records - len(rule_failed)),
                    "failed_count": len(rule_failed),
                    "issue_records": len(confirmed_record_ids),
                    "uncertain_records": len(uncertain_record_ids_for_rule),
                    "data_quality_gap_records": len(data_gap_record_ids_for_rule),
                    "rejected_by_system_records": len(rejected_record_ids_for_rule),
                    "not_applicable_records": len(not_applicable_record_ids_for_rule),
                    "compliant_records": max(
                        0,
                        effective_total_records
                        - len(rule_failed)
                        - len(confirmed_record_ids)
                        - len(uncertain_record_ids_for_rule)
                        - len(data_gap_record_ids_for_rule)
                        - len(rejected_record_ids_for_rule)
                        - len(not_applicable_record_ids_for_rule)
                        - len(not_executed_record_ids_for_rule),
                    ),
                    "total_tokens": int(state.get("total_tokens") or 0),
                    "total_processing_time": float(state.get("total_processing_time") or 0.0),
                }
                has_valid_rule = state.get("rule") is not None
                failed_threshold = effective_total_records if effective_total_records > 0 else total_records
                rule_status = (
                    "failed"
                    if (not has_valid_rule or (rule_failed and len(rule_failed) >= failed_threshold))
                    else ("completed" if final else "running")
                )
                rule_results_snapshot.append(
                    {
                        "id": state.get("rule_job_id"),
                        "job_id": job_id,
                        "rule_code": state.get("rule_code"),
                        "rule_name": state.get("rule_name"),
                        "status": rule_status,
                        "items": rule_items,
                        "failed_records": rule_failed,
                        "total_records": rule_summary["total_records"],
                        "success_count": rule_summary["success_count"],
                        "failed_count": rule_summary["failed_count"],
                        "issue_records": rule_summary["issue_records"],
                        "uncertain_records": rule_summary["uncertain_records"],
                        "data_quality_gap_records": rule_summary["data_quality_gap_records"],
                        "rejected_by_system_records": rule_summary["rejected_by_system_records"],
                        "not_applicable_records": rule_summary["not_applicable_records"],
                        "compliant_records": rule_summary["compliant_records"],
                        "total_tokens": rule_summary["total_tokens"],
                        "total_processing_time": rule_summary["total_processing_time"],
                        "updated_at": datetime.now(timezone.utc).isoformat(),
                        "progress": {
                            "rule_index": rule_index + 1,
                            "rule_count": len(output_rule_ids),
                            "processed_records": effective_total_records,
                        },
                        "debug": {
                            "executor_breakdown": {
                                "program": int(state.get("executor_program") or 0),
                                "llm": int(state.get("executor_llm") or 0),
                                "native": int(state.get("executor_native") or 0),
                            }
                        },
                    }
                )
            return rule_results_snapshot

        def _build_stream_state(
            record_result: Dict[str, Any],
            processed_records_count: int,
        ) -> Dict[str, Any]:
            items_by_rule = dict(record_result.get("items_by_rule") or {})
            latest_result_count = sum(len(list(value or [])) for value in items_by_rule.values())
            return {
                "enabled": True,
                "processed_records": processed_records_count,
                "total_records": total_records,
                "latest_record_id": str(record_result.get("record_id") or ""),
                "latest_visit_id": str(record_result.get("visit_id") or ""),
                "latest_result_count": latest_result_count,
                "partial_item_count": len(all_items),
                "partial_rule_result_count": len(output_rule_ids),
                "started_at": job_started_at.isoformat(),
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }

        def _live_items():
            rows = live_buffer.combine(all_items)
            if is_failed_rule_retry:
                rows, _ = merge_failed_rule_retry_results(
                    base_items=retry_base_items, base_failures=retry_base_failures,
                    retry_items=rows, retry_failures=all_failed_records,
                )
            return rows

        def _publish_family(record, executor_key, published):
            nonlocal first_result_latency, first_result_source
            if not enable_incremental_results or not native_direct_enabled:
                return
            record_id = str(record.get("record_id") or record.get("visit_id") or "").strip()
            case = CaseRef(str(record.get("institute_id") or "").strip(),
                str(record.get("patient_id") or "").strip(), str(record.get("visit_id") or record_id).strip())
            allowed = set(record_rule_map.get(case.as_key()) or record_rule_map.get(case.visit_id)
                or record_rule_map.get(record_id) or valid_rule_ids)
            rows = []
            for raw in published:
                rule_id = raw.get("rule_id")
                if (rule_id not in allowed or rule_id not in output_rule_states
                        or raw.get("schema_version") != "lx0609-customer-result-v2"
                        or raw.get("status") in {"technical_error", "uncertain"}):
                    continue
                validated_customer_explanation(raw, rule_id=rule_id, status=raw["status"])
                rows.append({**deepcopy(raw), "record_id": record_id, "record_key": case.as_key(),
                    "institute_id": case.institute_id, "patient_id": case.patient_id, "visit_id": case.visit_id,
                    "patient_name": str(record.get("patient_name") or ""),
                    "department": str(record.get("department") or ""),
                    "rule_job_id": output_rule_states[rule_id]["rule_job_id"],
                    "rule_code": rule_id,
                    "target_document_type": _resolve_luxian_target_document_type(output_rule_states[rule_id]["rule"]),
                })
            if not rows:
                return
            live_buffer.add(rows)
            now = time.perf_counter()
            if last_live_flush["result"] and now - last_live_flush["result"] < 1.0:
                return
            preview = _live_items()
            processed = int(completed_records_state["count"])
            result = workspace.update_batch_job_progress(
                job_id=job_id, **attempt_kwargs, step_key="run", rule_index=0,
                rule_count=total_rules, processed_records=processed, total_records=total_records,
                summary_patch={**_build_progress_patch(processed), "stream_state": {
                    "enabled": True, "kind": "native_executor_phase", "event": "published",
                    "executor_key": executor_key, "partial_item_count": len(preview),
                }}, progress_patch=_record_runtime_progress(processed), items=preview,
            )
            if result is not None and result.get("status") != "canceled":
                if first_result_latency is None and not is_failed_rule_retry:
                    first_result_latency = max(0.0, time.perf_counter() - job_wall_started)
                    first_result_source = "validated_family_write"
                last_live_flush["result"] = now

        async def _evaluate_single_record_impl(record: Dict[str, Any]) -> Dict[str, Any]:
            _raise_if_cancelled()
            record_id = str(record.get("record_id") or record.get("visit_id") or "").strip()
            visit_id = str(record.get("visit_id") or record_id).strip()
            institute_id = str(record.get("institute_id") or "").strip()
            patient_id = str(record.get("patient_id") or "").strip()
            record_ref = CaseRef(institute_id, patient_id, visit_id)
            record_key = record_ref.as_key() if all(record_ref) else record_id
            query_scope = str(
                filters.get("query_scope") or current.get("scope") or "all"
            ).strip().lower()
            record_evaluation_snapshot = (
                record_evaluation_snapshot_by_id.get(record_key)
                or record_evaluation_snapshot_by_id.get(visit_id)
                or record_evaluation_snapshot_by_id.get(record_id)
            )
            if record_evaluation_snapshot is not None:
                evaluation_horizon_policy = resolve_record_evaluation_horizon_policy(
                    record_evaluation_snapshot
                )
                evaluation_horizon_unavailable_reason = (
                    resolve_record_evaluation_horizon_unavailable_reason(
                        record_evaluation_snapshot
                    )
                )
                evaluation_as_of_date = (
                    str(record_evaluation_snapshot.get("evaluation_horizon") or "").strip()
                    if (
                        str(record_evaluation_snapshot.get("resolution_status") or "").strip()
                        == "resolved"
                        and str(record_evaluation_snapshot.get("evaluation_basis") or "").strip()
                        == "task_frozen_date"
                    )
                    else ""
                )
            else:
                # 兼容升级前已排队任务；新任务均使用逐病例快照。
                evaluation_horizon_policy = None
                evaluation_horizon_unavailable_reason = None
                evaluation_as_of_date = str(
                    filters.get("evaluation_as_of_date") or ""
                ).strip()
            should_postprocess_formal_results = _should_postprocess_formal_qc_results(
                rule_set_key=rule_set_key,
                validation_mode=validation_mode,
                current_scope=query_scope,
                execution_strategy=execution_strategy,
                bucket_strategy=bucket_strategy,
            )
            document_type = _resolve_document_type(query_scope, str(record.get("scope") or ""))
            active_rule_ids = (
                list(
                    record_rule_map.get(record_key)
                    or record_rule_map.get(visit_id)
                    or record_rule_map.get(record_id)
                    or []
                )
                or list(valid_rule_ids)
            )
            execution_trace_sink = None
            if native_direct_enabled:
                try:
                    executor_batches = tuple(
                        build_luxian_0609_package_plan_from_settings(
                            inventory=load_luxian_0609_dependency_inventory(),
                            selected_rule_ids=tuple(active_rule_ids),
                            settings=settings,
                        ).native_executor_batches
                    )
                except Exception:
                    # 阶段展示仅是安全旁路；无法生成批次计划时不影响质控主链。
                    logger.exception("LX0609 执行阶段计划解析失败: job_id=%s", job_id)
                    executor_batches = ()

                trace_state = {
                    "completed_batches": 0,
                    "completed_executor_keys": set(),
                    "finished_executor_keys": set(),
                    "active_executor_keys": set(),
                    "total_batches": len(executor_batches),
                    "completed_rule_count": 0,
                    "total_rule_count": len(active_rule_ids),
                    "terminal_state_persisted": False,
                }

                def _execution_trace_sink(trace: Dict[str, Any]) -> None:
                    """族阶段先在内存合并，每份病历只持久化一次终态。"""
                    try:
                        event = str((trace or {}).get("event") or "").strip().lower()
                        executor_key = str(
                            (trace or {}).get("executor_key") or ""
                        ).strip()
                        if event not in {"started", "completed", "failed"} or not executor_key:
                            return
                        if event == "started":
                            trace_state["active_executor_keys"].add(executor_key)
                        elif event == "completed":
                            trace_state["active_executor_keys"].discard(executor_key)
                            trace_state["finished_executor_keys"].add(executor_key)
                            if executor_key not in trace_state["completed_executor_keys"]:
                                trace_state["completed_executor_keys"].add(executor_key)
                                trace_state["completed_batches"] = min(
                                    trace_state["total_batches"],
                                    trace_state["completed_batches"] + 1,
                                )
                                try:
                                    rule_count = max(
                                        0, int((trace or {}).get("rule_count") or 0)
                                    )
                                except (TypeError, ValueError):
                                    rule_count = 0
                                trace_state["completed_rule_count"] = min(
                                    trace_state["total_rule_count"],
                                    trace_state["completed_rule_count"] + rule_count,
                                )
                        else:
                            # failed 只是可见的执行失败阶段，绝不能伪装为完成进度。
                            trace_state["active_executor_keys"].discard(executor_key)
                            trace_state["finished_executor_keys"].add(executor_key)
                        should_persist_terminal_state = bool(
                            not trace_state["terminal_state_persisted"]
                            and trace_state["total_batches"] > 0
                            and len(trace_state["finished_executor_keys"])
                            >= trace_state["total_batches"]
                        )
                        now = time.perf_counter()
                        phase_due = enable_incremental_results and now - last_live_flush["phase"] >= 1.0
                        if not should_persist_terminal_state and not phase_due:
                            return
                        trace_state["terminal_state_persisted"] = should_persist_terminal_state
                        last_live_flush["phase"] = now
                        workspace.update_batch_job_progress(
                            job_id=job_id,
                            **attempt_kwargs,
                            step_key="run",
                            rule_index=int(trace_state["completed_rule_count"]),
                            rule_count=int(trace_state["total_rule_count"]),
                            processed_records=int(completed_records_state["count"]),
                            total_records=total_records,
                            summary_patch={
                                "stream_state": {
                                    "enabled": True,
                                    "kind": "native_executor_phase",
                                    "event": event,
                                    "executor_key": executor_key,
                                    "completed_batches": int(
                                        trace_state["completed_batches"]
                                    ),
                                    "total_batches": int(trace_state["total_batches"]),
                                    "active_executor_keys": sorted(
                                        trace_state["active_executor_keys"]
                                    ),
                                    "record_id": record_id,
                                    "updated_at": datetime.now(timezone.utc).isoformat(),
                                    "current_rule_count": max(
                                        0, int((trace or {}).get("rule_count") or 0)
                                    ),
                                    "completed_rule_count": int(
                                        trace_state["completed_rule_count"]
                                    ),
                                    "total_rule_count": int(
                                        trace_state["total_rule_count"]
                                    ),
                                },
                                "updated_at": datetime.now(timezone.utc).isoformat(),
                            },
                        )
                    except Exception:
                        # 回调数据库失败不能反向影响原生执行或客户结果。
                        logger.exception("LX0609 执行阶段回写失败: job_id=%s", job_id)

                execution_trace_sink = _execution_trace_sink

            active_rules = [
                dict(rule_states[rule_id]["rule"])
                for rule_id in active_rule_ids
                if isinstance(rule_states[rule_id].get("rule"), dict)
            ]
            result_rule_ids = (
                active_rule_ids
                if use_luxian_customer_results and is_failed_rule_retry
                else output_rule_ids
                if use_luxian_customer_results
                else active_rule_ids
            )
            result_rule_states = output_rule_states if use_luxian_customer_results else rule_states
            items_by_rule: Dict[str, List[Dict[str, Any]]] = {rule_id: [] for rule_id in result_rule_ids}
            failed_by_rule: Dict[str, List[Dict[str, Any]]] = {rule_id: [] for rule_id in result_rule_ids}
            rule_stats: Dict[str, Dict[str, Any]] = {
                rule_id: {
                    "total_tokens": 0,
                    "total_processing_time": 0.0,
                    "executor_program": 0,
                    "executor_llm": 0,
                    "executor_native": 0,
                }
                for rule_id in result_rule_ids
            }
            try:
                used_bundle_path = False
                bundle_fallback_reason = ""
                eval_items: List[Dict[str, Any]] = []
                record_total_tokens = 0
                record_total_prompt_tokens = 0
                record_total_completion_tokens = 0
                record_total_api_time = 0.0
                record_llm_call_count: Optional[int] = None
                record_first_result_latency = 0.0
                record_first_result_source = ""
                record_pack_metrics: Dict[str, Any] = {}
                record_cot_summary: Dict[str, Any] = {}
                record_refine_summary: Dict[str, Any] = {}
                record_luxian_0609_input_profile: Dict[str, Any] = {}
                record_luxian_0609_shadow_evaluations: Dict[str, Any] = {}
                record_model_execution_stats: Optional[Dict[str, int]] = None
                record_usage_observation_complete: Optional[bool] = None
                record_usage_unknown_executor_keys: set[str] = set()
                bundle_scene = ""
                bundle_payload: Optional[Dict[str, Any]] = None
                attempted_bundle_scenes: List[str] = []
                runtime_shadow_summary: Optional[Dict[str, Any]] = None
                if record.get("_case_material_error"):
                    raise RuntimeError(record["_case_material_error"])

                def _capture_usage_observation(payload: Dict[str, Any]) -> None:
                    nonlocal record_usage_observation_complete
                    observed = payload.get("luxian_0609_usage_observation_complete")
                    if isinstance(observed, bool):
                        record_usage_observation_complete = (
                            observed if record_usage_observation_complete is None
                            else record_usage_observation_complete and observed
                        )
                    unknown_keys = payload.get("luxian_0609_usage_unknown_executor_keys")
                    if isinstance(unknown_keys, (list, tuple)):
                        record_usage_unknown_executor_keys.update(
                            key for key in unknown_keys if isinstance(key, str) and key
                        )

                async def _evaluate_rule_level_visit_bundle() -> bool:
                    nonlocal eval_items
                    nonlocal record_total_tokens
                    nonlocal record_total_prompt_tokens
                    nonlocal record_total_completion_tokens
                    nonlocal record_total_api_time
                    nonlocal record_llm_call_count
                    nonlocal record_first_result_latency
                    nonlocal record_first_result_source
                    nonlocal record_pack_metrics
                    nonlocal record_model_execution_stats

                    if not (institute_id and patient_id and visit_id and active_rule_ids):
                        return False

                    aggregated_items: List[Dict[str, Any]] = []
                    aggregated_tokens = 0
                    aggregated_api_time = 0.0
                    aggregated_llm_calls = 0
                    has_llm_call_attribution = True
                    first_latency = 0.0
                    first_source = ""
                    for single_rule_id in active_rule_ids:
                        _raise_if_cancelled()
                        single_result = await qc_service.evaluate_rule_for_visit(
                            rule_id=single_rule_id,
                            institute_id=institute_id,
                            patient_id=patient_id,
                            visit_id=visit_id,
                            source_schema="cdm",
                            bundle_schema="public",
                            cancellation_check=_is_cancelled,
                        )
                        _capture_usage_observation(single_result)
                        per_rule_items = list(
                            single_result.get("evaluation_results")
                            or single_result.get("parsed_evaluation_results")
                            or []
                        )
                        if not per_rule_items:
                            raise ValueError(f"规则级 visit 评估未返回结果: {single_rule_id}")
                        aggregated_items.extend(per_rule_items)
                        record_model_execution_stats = _merge_luxian_model_execution_stats(
                            record_model_execution_stats,
                            _extract_luxian_model_execution_stats(single_result),
                        )
                        token_usage = dict(single_result.get("token_usage") or {})
                        aggregated_tokens += int(token_usage.get("total_tokens") or 0)
                        aggregated_api_time += float(single_result.get("api_time") or 0.0)
                        single_llm_calls = _attributed_llm_call_count(single_result)
                        if single_llm_calls is None:
                            has_llm_call_attribution = False
                        else:
                            aggregated_llm_calls += single_llm_calls
                        if first_latency <= 0:
                            first_latency = float(single_result.get("api_time") or 0.0)
                            first_source = "rule_for_visit"

                    eval_items = aggregated_items
                    record_total_tokens = aggregated_tokens
                    record_total_prompt_tokens = 0
                    record_total_completion_tokens = 0
                    record_total_api_time = aggregated_api_time
                    record_llm_call_count = (
                        aggregated_llm_calls if has_llm_call_attribution else None
                    )
                    record_first_result_latency = first_latency
                    record_first_result_source = first_source
                    record_pack_metrics = {
                        "total_packs": len(active_rule_ids),
                        "avg_pack_size": 1.0,
                        "fallback_packs": 0,
                        "single_rule_retries": 0,
                        "pack_parse_retry_count": 0,
                        "context_tokens_estimate": 0,
                    }
                    return True

                if use_luxian_customer_results and not active_rule_ids:
                    record_usage_observation_complete = True
                    used_bundle_path = True
                    bundle_fallback_reason = "仅包含适用性门控质控点，无需调用底层执行规则"
                    eval_items = []
                    record_pack_metrics = {
                        "total_packs": 0,
                        "avg_pack_size": 0.0,
                        "fallback_packs": 0,
                        "single_rule_retries": 0,
                        "pack_parse_retry_count": 0,
                        "context_tokens_estimate": 0,
                    }

                if (
                    (is_programmatic_mode or native_direct_enabled)
                    and not (use_luxian_customer_results and not active_rule_ids)
                ):
                    bundle_payload = None
                    if institute_id and patient_id and visit_id:
                        record_scope = str(record.get("scope") or "").strip().lower()
                        candidate_scenes = _workspace_bundle_scene_candidates(
                            query_scope=query_scope,
                            record_scope=record_scope,
                        )
                        for scene in candidate_scenes:
                            attempted_bundle_scenes.append(scene)
                            try:
                                bundle_payload = load_running_final_bundle(
                                    scene=scene,
                                    institute_id=institute_id,
                                    patient_id=patient_id,
                                    visit_id=visit_id,
                                    schema="public",
                                )
                                bundle_scene = scene
                                break
                            except Exception:
                                continue
                    used_bundle_path = bundle_payload is not None
                    if not used_bundle_path and institute_id and patient_id and visit_id:
                        bundle_fallback_reason = "未加载到 running/final bundle，回退 medical_text + timeline_missing"
                    evidence_payload = build_programmatic_evidence_payload(
                        bundle=bundle_payload,
                        medical_text=str(record.get("medical_text") or ""),
                    )
                    if (
                        rule_set_key == LUXIAN_0609_RULE_SET_KEY
                        and bool(getattr(settings, "LUXIAN_0609_RUNTIME_SHADOW_ENABLED", False))
                    ):
                        # 当前 router 没有查询四态和结构化事实真值；只附加安全影子摘要。
                        runtime_shadow_summary = run_luxian_0609_runtime_shadow(
                            visit_ref=visit_id,
                            selected_rule_ids=filters.get("selected_rule_ids", ()),
                            scoped_customer_rule_ids=filters.get("scoped_customer_rule_ids") or (),
                            record_rule_map=filters.get("record_rule_map") or {},
                            evidence_payload=evidence_payload,
                            source_query_observations=None,
                            extraction_inputs=None,
                            institute_id=institute_id,
                            patient_id=patient_id,
                            settings=settings,
                        )
                    primary_document_text = str(
                        evidence_payload.get("primary_document_text")
                        or (bundle_payload or {}).get("medical_text")
                        or record.get("medical_text")
                        or ""
                    )
                    if native_direct_enabled:
                        package_bundle = dict(bundle_payload or {})
                        resolved_record_scene = _resolve_workspace_bundle_scene(
                            query_scope=query_scope,
                            record_scope=str(record.get("scope") or ""),
                        )
                        package_bundle["scene"] = (
                            bundle_scene or resolved_record_scene or "running"
                        )
                        package_bundle["scene_resolution"] = {
                            "query_scope": query_scope,
                            "record_scene": str(record.get("scope") or "").strip().lower() or "unknown",
                            "resolved_scene": resolved_record_scene,
                            "attempted_scenes": list(attempted_bundle_scenes),
                            "loaded_scene": bundle_scene,
                            "used_fallback": bool(
                                bundle_scene
                                and resolved_record_scene
                                and bundle_scene != resolved_record_scene
                            ),
                            "resolution_status": _workspace_scene_resolution_status(
                                record_scope=str(record.get("scope") or ""),
                                resolved_scene=resolved_record_scene,
                                loaded_scene=bundle_scene,
                            ),
                        }
                        if record_evaluation_snapshot is not None:
                            package_bundle["evaluation_horizon_snapshot"] = dict(
                                record_evaluation_snapshot
                            )
                        package_bundle.setdefault("institute_id", institute_id)
                        package_bundle.setdefault("patient_id", patient_id)
                        package_bundle.setdefault("visit_id", visit_id or record_id)
                        package_bundle.setdefault("medical_text", primary_document_text)
                        package_bundle.setdefault("structured_context", {})
                        package_bundle.setdefault("document_hits", {})
                        package_bundle.setdefault(
                            "data_quality_flags",
                            [] if bundle_payload is not None else ["bundle_unavailable"],
                        )
                        package_bundle.setdefault("source_doc_priority", [])
                        package_bundle.setdefault(
                            "text_available", bool(primary_document_text)
                        )
                        result = await qc_service.evaluate_running_final_bundle_input(
                            bundle=package_bundle,
                            rule_ids=active_rule_ids,
                            bucket_strategy=bucket_strategy,
                            quality_profile=quality_profile,
                            batch_output_mode=batch_output_mode,
                            enable_selective_refine=enable_selective_refine,
                            refine_confidence_threshold=refine_confidence_threshold,
                            max_refine_candidates=max_refine_candidates,
                            rule_set_key=rule_set_key,
                            **(
                                {"task_settings": settings}
                                if rule_set_key == LUXIAN_0609_RULE_SET_KEY
                                else {}
                            ),
                            evaluation_as_of_date=evaluation_as_of_date or None,
                            evaluation_horizon_policy=evaluation_horizon_policy,
                            evaluation_horizon_unavailable_reason=(
                                evaluation_horizon_unavailable_reason
                            ),
                            cancellation_check=_is_cancelled,
                            execution_trace_sink=execution_trace_sink,
                        )
                        used_bundle_path = True
                    else:
                        result = await qc_service.evaluate_document_with_rules(
                            document_id=record_id or "unknown",
                            content=primary_document_text,
                            document_type=document_type,
                            rules=active_rules,
                            evidence_source="timeline" if used_bundle_path else "medical_text_fallback",
                            evidence_payload=evidence_payload,
                            bucket_strategy=bucket_strategy,
                            quality_profile=quality_profile,
                            batch_output_mode=batch_output_mode,
                            enable_selective_refine=enable_selective_refine,
                            refine_confidence_threshold=refine_confidence_threshold,
                            max_refine_candidates=max_refine_candidates,
                            rule_set_key=rule_set_key,
                            source_institute_id=institute_id,
                            source_patient_id=patient_id,
                            source_visit_id=visit_id,
                            source_schema=(
                                str((bundle_payload or {}).get("source_schema") or "").strip()
                                or None
                            ),
                            cancellation_check=_is_cancelled,
                        )
                    token_usage = dict(result.get("token_usage") or {})
                    record_total_tokens = int(token_usage.get("total_tokens") or 0)
                    record_total_prompt_tokens = int(token_usage.get("prompt_tokens") or 0)
                    record_total_completion_tokens = int(token_usage.get("completion_tokens") or 0)
                    record_llm_call_count = _attributed_llm_call_count(result)
                    record_total_api_time = float(result.get("api_time") or 0.0)
                    record_first_result_latency = float(result.get("first_result_latency") or 0.0)
                    record_first_result_source = str(result.get("first_result_source") or "")
                    record_pack_metrics = dict(result.get("pack_metrics") or {})
                    record_cot_summary = dict(result.get("cot_summary") or {})
                    record_refine_summary = dict(result.get("refine_summary") or {})
                    record_luxian_0609_input_profile = dict(result.get("luxian_0609_input_profile") or {})
                    record_model_execution_stats = _extract_luxian_model_execution_stats(result)
                    _capture_usage_observation(result)
                    record_luxian_0609_shadow_evaluations = dict(
                        result.get("luxian_0609_shadow_evaluations") or {}
                    )
                    eval_items = list(result.get("evaluation_results") or [])
                    if runtime_shadow_summary is not None:
                        for eval_item in eval_items:
                            if isinstance(eval_item, dict):
                                metadata = dict(eval_item.get("metadata") or {})
                                metadata["luxian_0609_runtime_shadow"] = runtime_shadow_summary
                                eval_item["metadata"] = metadata
                else:
                    bundle_scene = _resolve_workspace_bundle_scene(
                        query_scope=query_scope,
                        record_scope=str(record.get("scope") or ""),
                    )

                if (
                    not is_programmatic_mode
                    and not native_direct_enabled
                    and not (use_luxian_customer_results and not active_rule_ids)
                    and prefer_rule_level_visit_eval
                    and len(active_rule_ids) == 1
                    and institute_id
                    and patient_id
                    and visit_id
                ):
                    used_bundle_path = await _evaluate_rule_level_visit_bundle()
                elif (
                    not is_programmatic_mode
                    and not native_direct_enabled
                    and not (use_luxian_customer_results and not active_rule_ids)
                    and bundle_scene
                    and institute_id
                    and patient_id
                    and visit_id
                ):
                    used_bundle_path = True
                    try:
                        _raise_if_cancelled()
                        use_sc_fixed_fast_screen = (
                            bundle_scene == "final"
                            and execution_strategy == EXECUTION_STRATEGY_FAST_SCREEN
                            and validation_mode != "customer"
                            and rule_set_key != CUSTOMER_LUXIAN_RULE_SET_KEY
                        )
                        if use_sc_fixed_fast_screen:
                            single_result = await run_final_fast_screen(
                                qc_service=qc_service,
                                institute_id=institute_id,
                                patient_id=patient_id,
                                visit_id=visit_id,
                                source_schema="cdm",
                                rule_ids=active_rule_ids,
                                quality_profile=quality_profile,
                                batch_output_mode=batch_output_mode,
                                cancellation_check=_is_cancelled,
                            )
                        else:
                            single_result = await evaluate_running_final_bundle(
                                qc_service=qc_service,
                                scene=bundle_scene,
                                institute_id=institute_id,
                                patient_id=patient_id,
                                visit_id=visit_id,
                                rule_ids=active_rule_ids,
                                schema="public",
                                bucket_strategy=bucket_strategy,
                                quality_profile=quality_profile,
                                batch_output_mode=batch_output_mode,
                                enable_selective_refine=enable_selective_refine,
                                refine_confidence_threshold=refine_confidence_threshold,
                                max_refine_candidates=max_refine_candidates,
                                rule_set_key=rule_set_key,
                                cancellation_check=_is_cancelled,
                            )
                        eval_items = list(
                            single_result.get("evaluation_results")
                            or single_result.get("parsed_evaluation_results")
                            or []
                        )
                        if not eval_items:
                            raise ValueError("evaluate_running_final_bundle 未返回 evaluation_results")
                        token_usage = dict(single_result.get("token_usage") or {})
                        record_total_tokens = int(token_usage.get("total_tokens") or 0)
                        record_total_prompt_tokens = int(token_usage.get("prompt_tokens") or 0)
                        record_total_completion_tokens = int(token_usage.get("completion_tokens") or 0)
                        record_llm_call_count = _attributed_llm_call_count(single_result)
                        record_total_api_time = float(single_result.get("api_time") or 0.0)
                        record_first_result_latency = float(single_result.get("first_result_latency") or 0.0)
                        record_first_result_source = str(single_result.get("first_result_source") or "")
                        record_pack_metrics = dict(single_result.get("pack_metrics") or {})
                        record_cot_summary = dict(single_result.get("cot_summary") or {})
                        record_refine_summary = dict(single_result.get("refine_summary") or {})
                        record_luxian_0609_input_profile = dict(
                            single_result.get("luxian_0609_input_profile") or {}
                        )
                        record_model_execution_stats = _extract_luxian_model_execution_stats(single_result)
                        _capture_usage_observation(single_result)
                    except Exception as bundle_exc:
                        if use_luxian_customer_results:
                            record_usage_observation_complete = False
                        if prefer_rule_level_visit_eval and len(active_rule_ids) == 1:
                            try:
                                used_bundle_path = await _evaluate_rule_level_visit_bundle()
                                bundle_fallback_reason = f"scene bundle 评估失败，已回退 rule_for_visit: {bundle_exc}"
                            except Exception:
                                used_bundle_path = False
                                bundle_fallback_reason = f"bundle 一次性评估失败: {bundle_exc}"
                                logger.warning(
                                    "批量任务 %s 病历 %s bundle 一次性评估失败(scene=%s)，规则级 visit 回退也失败，最终回退长文本评估",
                                    job_id,
                                    record_id or visit_id or "unknown",
                                    bundle_scene,
                                    exc_info=True,
                                )
                        else:
                            used_bundle_path = False
                            bundle_fallback_reason = f"bundle 一次性评估失败: {bundle_exc}"
                            logger.warning(
                                "批量任务 %s 病历 %s bundle 一次性评估失败(scene=%s)，回退长文本评估",
                                job_id,
                                record_id or visit_id or "unknown",
                                bundle_scene,
                                exc_info=True,
                            )
                elif (
                    not native_direct_enabled
                    and query_scope in {"final", "all"}
                    and not (use_luxian_customer_results and not active_rule_ids)
                ):
                    bundle_fallback_reason = "缺少 bundle 主键(institute_id/patient_id/visit_id)"

                if not used_bundle_path:
                    _raise_if_cancelled()
                    result = await qc_service.evaluate_document(
                        document_id=record_id or "unknown",
                        content=str(record.get("medical_text") or ""),
                        document_type=document_type,
                        rule_ids=active_rule_ids,
                        bucket_strategy=bucket_strategy,
                        quality_profile=quality_profile,
                        batch_output_mode=batch_output_mode,
                        enable_selective_refine=enable_selective_refine,
                        refine_confidence_threshold=refine_confidence_threshold,
                        max_refine_candidates=max_refine_candidates,
                        rule_set_key=rule_set_key,
                        source_institute_id=institute_id,
                        source_patient_id=patient_id,
                        source_visit_id=visit_id,
                        source_schema=(
                            str((bundle_payload or {}).get("source_schema") or "").strip()
                            or None
                        ),
                        cancellation_check=_is_cancelled,
                    )
                    token_usage = dict(result.get("token_usage") or {})
                    record_total_tokens = int(token_usage.get("total_tokens") or 0)
                    record_total_prompt_tokens = int(token_usage.get("prompt_tokens") or 0)
                    record_total_completion_tokens = int(token_usage.get("completion_tokens") or 0)
                    record_llm_call_count = _attributed_llm_call_count(result)
                    record_total_api_time = float(result.get("api_time") or 0.0)
                    record_first_result_latency = float(result.get("first_result_latency") or 0.0)
                    record_first_result_source = str(result.get("first_result_source") or "")
                    record_pack_metrics = dict(result.get("pack_metrics") or {})
                    record_cot_summary = dict(result.get("cot_summary") or {})
                    record_refine_summary = dict(result.get("refine_summary") or {})
                    record_luxian_0609_input_profile = dict(result.get("luxian_0609_input_profile") or {})
                    record_model_execution_stats = _extract_luxian_model_execution_stats(result)
                    _capture_usage_observation(result)
                    record_luxian_0609_shadow_evaluations = dict(
                        result.get("luxian_0609_shadow_evaluations") or {}
                    )
                    eval_items = list(result.get("evaluation_results") or [])

                eval_map: Dict[str, Dict[str, Any]] = {}
                for eval_item in eval_items:
                    key = str(eval_item.get("rule_id") or eval_item.get("rule_code") or "").strip().upper()
                    if key and key not in eval_map:
                        eval_map[key] = dict(eval_item)

                local_total_processing_time = 0.0
                local_executor_program = 0
                local_executor_llm = 0
                local_executor_native = 0
                local_cache_hit = 0
                local_cache_miss = 0
                has_issue = False
                has_uncertain = False
                record_issue_items: List[Dict[str, Any]] = []
                record_status_items: List[Dict[str, Any]] = []

                result_rule_count = max(1, len(result_rule_ids))
                fallback_prompt_tokens = _distribute_non_negative_int(
                    record_total_prompt_tokens,
                    result_rule_count,
                )
                fallback_completion_tokens = _distribute_non_negative_int(
                    record_total_completion_tokens,
                    result_rule_count,
                )
                if record_total_tokens == (
                    record_total_prompt_tokens + record_total_completion_tokens
                ):
                    fallback_total_tokens = [
                        prompt + completion
                        for prompt, completion in zip(
                            fallback_prompt_tokens,
                            fallback_completion_tokens,
                        )
                    ]
                else:
                    fallback_total_tokens = _distribute_non_negative_int(
                        record_total_tokens,
                        result_rule_count,
                    )
                fallback_api_per_rule = float(record_total_api_time / max(1, len(result_rule_ids)))

                for rule_index, rule_id in enumerate(result_rule_ids):
                    normalized_rule_id = str(rule_id).strip().upper()
                    state = result_rule_states[rule_id]
                    rule = state["rule"]
                    rule_name = str(state["rule_name"])
                    rule_code = str(state["rule_code"])
                    rule_job_id = str(state["rule_job_id"])
                    luxian_target_document_type = (
                        _resolve_luxian_target_document_type(rule)
                        if use_luxian_customer_results
                        else ""
                    )
                    eval_item = eval_map.get(normalized_rule_id) or {}
                    if not eval_item:
                        is_gate_only_missing = (
                            use_luxian_customer_results
                            and normalized_rule_id in gate_only_customer_rule_ids
                        )
                        is_paused_customer_rule = (
                            use_luxian_customer_results
                            and normalized_rule_id in paused_customer_rule_ids
                        )
                        if not is_gate_only_missing and not is_paused_customer_rule:
                            failed_by_rule[rule_id].append(
                                {
                                    "rule_job_id": rule_job_id,
                                    "rule_id": rule_id,
                                    "rule_code": rule_code,
                                    "rule_name": rule_name,
                                    "record_id": record_id,
                                    "record_key": record_key,
                                    "institute_id": institute_id,
                                    "patient_id": patient_id,
                                    "visit_id": visit_id,
                                    "patient_name": str(record.get("patient_name") or ""),
                                    "department": str(record.get("department") or ""),
                                    "error_phase": "result_missing",
                                    "error": "规则执行未返回结果",
                                }
                            )
                        if use_luxian_customer_results:
                            if is_paused_customer_rule:
                                eval_item = {
                                    **build_luxian_0609_pending_definition_result(
                                        normalized_rule_id
                                    ),
                                    "rule_name": rule_name,
                                }
                            elif is_gate_only_missing:
                                eval_item = {
                                    "rule_id": rule_id,
                                    "rule_name": rule_name,
                                    "status": "not_applicable",
                                    "is_compliant": True,
                                    "findings": "未发现该质控点所需的明确触发事实，本次不进入缺陷判定。",
                                    "evidence": "适用性：该质控点当前没有可执行底层映射规则，按适用性门控判定为不适用。",
                                    "suggestion": "无需整改；如病历存在相关事件，请补充结构化文书或医嘱后重新质控。",
                                    "confidence": 0,
                                    "metadata": {
                                        "executor_type": "program",
                                        "result_fallback": "gate_only_not_applicable",
                                    },
                                }
                            else:
                                eval_item = {
                                    "rule_id": rule_id,
                                    "rule_name": rule_name,
                                    "status": "not_executed",
                                    "is_compliant": False,
                                    "findings": "该质控点未返回执行结果。",
                                    "evidence": "当前质控点没有返回可展示结果。",
                                    "suggestion": "建议重新执行本质控点，或由质控员结合原文确认。",
                                    "confidence": 0,
                                    "metadata": {
                                        "executor_type": "program",
                                        "result_fallback": "missing_customer_result",
                                    },
                                }
                        else:
                            continue
                    if not use_luxian_customer_results:
                        eval_item = _guard_luxian_copy_result_for_batch(
                            rule_id=normalized_rule_id,
                            eval_item=eval_item,
                            record=record,
                        )

                    raw_status = str(
                        eval_item.get("status")
                        or eval_item.get("result_status")
                        or eval_item.get("display_status")
                        or ""
                    ).strip().lower()
                    status = raw_status
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
                        status = "compliant" if eval_item.get("is_compliant") else "non_compliant"
                    evidence_items = (
                        list(eval_item.get("evidence_items") or [])
                        if isinstance(eval_item.get("evidence_items"), list)
                        else []
                    )
                    metadata = dict(eval_item.get("metadata") or {})
                    metadata.setdefault("tokens_used", fallback_total_tokens[rule_index])
                    metadata.setdefault("prompt_tokens", fallback_prompt_tokens[rule_index])
                    metadata.setdefault("completion_tokens", fallback_completion_tokens[rule_index])
                    metadata.setdefault("input_tokens", fallback_prompt_tokens[rule_index])
                    metadata.setdefault("output_tokens", fallback_completion_tokens[rule_index])
                    if "api_time" not in metadata:
                        metadata["api_time"] = fallback_api_per_rule
                        metadata["api_time_basis"] = "allocated_record_api_time"
                    metadata.setdefault("first_result_latency", record_first_result_latency)
                    metadata.setdefault("first_result_source", record_first_result_source)
                    metadata.setdefault("execution_domain", str((rule or {}).get("execution_domain") or ""))
                    metadata.setdefault("doc_scope", str((rule or {}).get("doc_scope") or ""))
                    metadata.setdefault("rule_family", str((rule or {}).get("rule_family") or ""))
                    metadata.setdefault("executor_type", str((rule or {}).get("executor_type") or "llm"))
                    metadata.setdefault(
                        "prompt_strategy", str(record_pack_metrics.get("prompt_strategy") or "batch_compact_v1")
                    )
                    metadata.setdefault("pack_size", int(record_pack_metrics.get("selected_pack_size") or 1))
                    metadata.setdefault("quality_profile", quality_profile)
                    metadata.setdefault("bucket_strategy", bucket_strategy)
                    if record_luxian_0609_input_profile:
                        metadata.setdefault("luxian_0609_input_profile", record_luxian_0609_input_profile)
                    if query_scope == "final" and not used_bundle_path:
                        metadata.setdefault("bundle_fallback", True)
                        if bundle_fallback_reason:
                            metadata.setdefault("bundle_fallback_reason", bundle_fallback_reason)
                        metadata.setdefault("evidence_source", "medical_text_fallback")

                    tokens_used = int(metadata.get("tokens_used") or 0)
                    api_time = float(metadata.get("api_time") or 0.0)
                    local_total_processing_time += api_time
                    rule_stats[rule_id]["total_tokens"] = int(rule_stats[rule_id]["total_tokens"] or 0) + tokens_used
                    rule_stats[rule_id]["total_processing_time"] = (
                        float(rule_stats[rule_id]["total_processing_time"] or 0.0) + api_time
                    )

                    executor_key = str(metadata.get("executor_key") or "").strip()
                    executor_type = str(metadata.get("executor_type") or "llm").lower()
                    if native_direct_enabled and executor_key:
                        local_executor_native += 1
                        rule_stats[rule_id]["executor_native"] = (
                            int(rule_stats[rule_id]["executor_native"] or 0) + 1
                        )
                    elif executor_type == "program":
                        local_executor_program += 1
                        rule_stats[rule_id]["executor_program"] = (
                            int(rule_stats[rule_id]["executor_program"] or 0) + 1
                        )
                    else:
                        local_executor_llm += 1
                        rule_stats[rule_id]["executor_llm"] = int(rule_stats[rule_id]["executor_llm"] or 0) + 1
                    if metadata.get("cache_hit") is True:
                        local_cache_hit += 1
                    else:
                        local_cache_miss += 1

                    diagnostic_trace = _result_diagnostic_trace(
                        eval_item,
                        metadata,
                        evidence_items=evidence_items,
                        status=status,
                    )
                    metadata["diagnostic_trace"] = diagnostic_trace
                    metadata["source_execution_results"] = diagnostic_trace.get("source_execution_results") or []
                    metadata["trigger_decision"] = diagnostic_trace.get("trigger_decision") or {}
                    metadata["postprocess_reason"] = diagnostic_trace.get("postprocess_reason") or ""

                    if use_luxian_customer_results and _is_luxian_execution_failure(
                        raw_status=raw_status,
                        eval_item=eval_item,
                        metadata=metadata,
                    ):
                        if not failed_by_rule[rule_id]:
                            failed_by_rule[rule_id].append(
                                _build_luxian_execution_failure_record(
                                    rule_job_id=rule_job_id,
                                    rule_id=normalized_rule_id,
                                    rule_code=rule_code,
                                    rule_name=rule_name,
                                    record_id=record_id,
                                    record_key=record_key,
                                    institute_id=institute_id,
                                    patient_id=patient_id,
                                    visit_id=visit_id,
                                    raw_status=raw_status,
                                    eval_item=eval_item,
                                    metadata=metadata,
                                )
                            )
                        continue

                    issue_item = {
                        "rule_job_id": rule_job_id,
                        "rule_id": str(eval_item.get("rule_id") or rule_id),
                        "rule_code": rule_code,
                        "rule_name": str(eval_item.get("rule_name") or rule_name),
                        "record_id": record_id,
                        "record_key": record_key,
                        "institute_id": institute_id,
                        "patient_id": patient_id,
                        "visit_id": str(record.get("visit_id") or ""),
                        "patient_name": str(record.get("patient_name") or ""),
                        "department": str(record.get("department") or ""),
                        "status": status,
                        **(
                            {
                                "schema_version": str(
                                    eval_item.get("schema_version") or ""
                                ),
                                "result_status": str(
                                    eval_item.get("result_status") or status
                                ),
                                "display_status": str(
                                    eval_item.get("display_status") or status
                                ),
                            }
                            if use_luxian_customer_results
                            else {}
                        ),
                        "reason_code": str(
                            eval_item.get("reason_code")
                            or metadata.get("reason_code")
                            or ""
                        ),
                        "is_compliant": (
                            eval_item.get("is_compliant")
                            if use_luxian_customer_results
                            else bool(eval_item.get("is_compliant") is True)
                        ),
                        "findings": str(eval_item.get("findings") or ""),
                        "evidence": str(eval_item.get("evidence") or ""),
                        "evidence_items": evidence_items,
                        "suggestion": str(eval_item.get("suggestion") or ""),
                        "confidence": float(eval_item.get("confidence") or 0),
                        "metadata": _sanitize_trace_value(metadata, set(), max_text=1200),
                        "diagnostic_trace": diagnostic_trace,
                        "source_rule_id": str(diagnostic_trace.get("source_rule_id") or ""),
                        "source_status": str(diagnostic_trace.get("source_status") or ""),
                        "source_conclusion": str(diagnostic_trace.get("source_conclusion") or ""),
                        "source_evidence": diagnostic_trace.get("source_evidence") or "",
                        "trigger_decision": diagnostic_trace.get("trigger_decision") or {},
                        "postprocess_reason": str(diagnostic_trace.get("postprocess_reason") or ""),
                        "executor_type": executor_type,
                        # 原生聚合结果将当前规则契约版本置于顶层；若此处只从
                        # metadata 读取，带 criterion_results 的结果会在单病历
                        # 读取端被误判为旧契约并过滤。兼容旧链的 metadata 回退。
                        "rule_version": str(
                            eval_item.get("rule_version")
                            or metadata.get("rule_version")
                            or ""
                        ),
                        "prompt_version": str(metadata.get("prompt_version") or ""),
                        "model_version": str(metadata.get("model_version") or ""),
                        "evidence_source": str(metadata.get("evidence_source") or ""),
                        "cache_hit": bool(metadata.get("cache_hit") is True),
                        "trace_id": str(metadata.get("trace_id") or ""),
                        "cache_key": str(metadata.get("cache_key") or ""),
                        "execution_domain": str(metadata.get("execution_domain") or ""),
                        "doc_scope": str(metadata.get("doc_scope") or ""),
                        "rule_family": str(metadata.get("rule_family") or ""),
                        "cost_class": str(metadata.get("cost_class") or ""),
                        "prompt_strategy": str(metadata.get("prompt_strategy") or ""),
                        "quality_profile": str(metadata.get("quality_profile") or ""),
                        "bucket_strategy": str(metadata.get("bucket_strategy") or ""),
                        "pack_size": int(metadata.get("pack_size") or 1),
                        "pack_id": str(metadata.get("pack_id") or ""),
                        "pack_fallback": bool(metadata.get("pack_fallback") is True),
                        "context_tokens_estimate": int(metadata.get("context_tokens_estimate") or 0),
                        "prompt_tokens": int(metadata.get("prompt_tokens") or 0),
                        "completion_tokens": int(metadata.get("completion_tokens") or 0),
                        "first_result_latency": float(metadata.get("first_result_latency") or 0.0),
                        "first_result_source": str(metadata.get("first_result_source") or ""),
                        "cot_mode": str(metadata.get("cot_mode") or "disabled"),
                        "requested_enable_thinking": bool(metadata.get("requested_enable_thinking") is True),
                        "thinking_heuristic_applied": bool(
                            metadata.get("thinking_heuristic_applied") is True
                        ),
                        "refined": bool(metadata.get("refined") is True),
                        "refine_reason": str(metadata.get("refine_reason") or ""),
                        "screening_status": str(metadata.get("screening_status") or ""),
                        "final_decision_source": str(metadata.get("final_decision_source") or ""),
                        "provider_error_count": int(metadata.get("provider_error_count") or 0),
                        "timeout_count": int(metadata.get("timeout_count") or 0),
                        "rate_limit_count": int(metadata.get("rate_limit_count") or 0),
                        "pack_retry_attempts": int(metadata.get("pack_retry_attempts") or 0),
                        "pack_retry_success": bool(metadata.get("pack_retry_success") is True),
                        "pack_retry_reason": str(metadata.get("pack_retry_reason") or ""),
                        "technical_error_internal": bool(metadata.get("technical_error_internal") is True),
                        "document_type": str(
                            luxian_target_document_type
                            or eval_item.get("_document_type")
                            or eval_item.get("document_type")
                            or metadata.get("document_type")
                            or document_type
                        ),
                        "target_document_type": str(
                            luxian_target_document_type
                            or eval_item.get("target_document_type")
                            or metadata.get("target_document_type")
                            or eval_item.get("_document_type")
                            or eval_item.get("document_type")
                            or metadata.get("document_type")
                            or document_type
                        ),
                        "defect_level": str((rule or {}).get("defect_level") or ""),
                        "llm_fallback": bool(metadata.get("llm_fallback") is True),
                    }
                    customer_display_facts = eval_item.get("customer_display_facts")
                    if isinstance(customer_display_facts, dict):
                        # 正式发布事实由规则族合同校验；任务装配只复制，不能套用
                        # trace 清洗（会删除 documents 明细并截断列表/字符串）。
                        issue_item["customer_display_facts"] = (
                            deepcopy(customer_display_facts)
                            if use_luxian_customer_results
                            else _sanitize_trace_value(
                                customer_display_facts,
                                set(),
                                max_text=120,
                                list_limits={"recommendation_evidence": 96},
                            )
                        )
                    if use_luxian_customer_results:
                        # 服务层仅对正式发布结果提供这些文案字段；此处原样搬运，
                        # 不在任务装配时丢失或重写发布结论与建议。
                        for published_key in (
                            "conclusion", "customer_conclusion", "customer_suggestion",
                        ):
                            if published_key in eval_item:
                                issue_item[published_key] = eval_item[published_key]
                        customer_message = eval_item.get("customer_message")
                        if isinstance(customer_message, str) and customer_message.strip():
                            issue_item["customer_message"] = customer_message.strip()
                        for gap_key in ("missing_sources", "missing_fields"):
                            gap_values = eval_item.get(gap_key)
                            if isinstance(gap_values, list):
                                issue_item[gap_key] = list(gap_values)
                        data_gap_details = eval_item.get("data_gap_details")
                        if isinstance(data_gap_details, dict):
                            issue_item["data_gap_details"] = _sanitize_trace_value(
                                data_gap_details,
                                set(),
                                max_text=240,
                            )
                    # 单病历新结果 Envelope 必须保留原生已生成的子结论和证据。
                    # 这里不把 document_id/raw text 直接作为客户输出；workspace
                    # 读取投影会对证据签名、对白名单字段做最终裁剪。
                    criterion_results = eval_item.get("criterion_results")
                    if isinstance(criterion_results, list):
                        issue_item["criterion_results"] = criterion_results
                    customer_evidence = eval_item.get("customer_evidence")
                    if isinstance(customer_evidence, list):
                        issue_item["customer_evidence"] = customer_evidence
                    model_analysis = eval_item.get("model_analysis") or eval_item.get("medical_analysis")
                    if isinstance(model_analysis, str) and model_analysis.strip():
                        issue_item["model_analysis"] = model_analysis
                    if should_postprocess_formal_results:
                        issue_item = postprocess_qc_result(
                            issue_item,
                            mode="formal_final_online",
                        )
                        post_metadata = dict(issue_item.get("metadata") or {})
                        post_diagnostic_trace = _result_diagnostic_trace(
                            issue_item,
                            post_metadata,
                            evidence_items=issue_item.get("evidence_items")
                            if isinstance(issue_item.get("evidence_items"), list)
                            else [],
                            status=str(issue_item.get("status") or ""),
                        )
                        post_metadata["diagnostic_trace"] = post_diagnostic_trace
                        post_metadata["postprocess_reason"] = post_diagnostic_trace.get("postprocess_reason") or ""
                        post_metadata.pop("aggregation_reason", None)
                        issue_item["metadata"] = _sanitize_trace_value(post_metadata, set(), max_text=1200)
                        issue_item["diagnostic_trace"] = post_diagnostic_trace
                        issue_item["source_rule_id"] = str(post_diagnostic_trace.get("source_rule_id") or "")
                        issue_item["source_status"] = str(post_diagnostic_trace.get("source_status") or "")
                        issue_item["source_conclusion"] = str(post_diagnostic_trace.get("source_conclusion") or "")
                        issue_item["source_evidence"] = post_diagnostic_trace.get("source_evidence") or ""
                        issue_item["trigger_decision"] = post_diagnostic_trace.get("trigger_decision") or {}
                        issue_item["postprocess_reason"] = str(post_diagnostic_trace.get("postprocess_reason") or "")
                    if runtime_shadow_summary is not None:
                        persisted_metadata = dict(issue_item.get("metadata") or {})
                        persisted_metadata["luxian_0609_runtime_shadow"] = runtime_shadow_summary
                        issue_item["metadata"] = persisted_metadata
                    if not should_postprocess_formal_results and issue_item["status"] in {
                        "non_compliant",
                        "ai_suggested_non_compliant",
                    }:
                        has_issue = True
                    elif not should_postprocess_formal_results and issue_item["status"] == "uncertain":
                        has_uncertain = True
                    if issue_item["status"] in {
                        "non_compliant",
                        "ai_suggested_non_compliant",
                        "data_gap",
                        "uncertain",
                        "technical_error",
                    }:
                        record_issue_items.append(issue_item)
                    elif issue_item["status"] in {"not_applicable", "not_executed"} or (
                        use_luxian_customer_results and issue_item["status"] in {"compliant", "ai_suggested_compliant"}
                    ):
                        record_status_items.append(issue_item)

                if should_postprocess_formal_results and record_issue_items:
                    adjudicator_client = getattr(qc_service, "adjudicator_client", None) or getattr(qc_service, "client", None)
                    record_issue_items = await adjudicate_postprocessed_qc_results(
                        record_issue_items,
                        rules_by_id={
                            rule_id: dict(rule_states[rule_id]["rule"])
                            for rule_id in active_rule_ids
                            if isinstance(rule_states[rule_id].get("rule"), dict)
                        },
                        llm_generate=getattr(adjudicator_client, "generate", None),
                        adjudicator_model_metadata={
                            "first_pass_model": getattr(getattr(qc_service, "client", None), "model", ""),
                            "adjudicator_model": getattr(adjudicator_client, "model", ""),
                            "model_role": "adjudicator",
                            "adjudicator_model_source": getattr(adjudicator_client, "adjudicator_model_source", "")
                            or getattr(adjudicator_client, "config_source", ""),
                        },
                        mode="formal_final_online",
                    )

                for final_item in [*record_issue_items, *record_status_items]:
                    _attach_result_performance_profile(final_item)
                    final_rule_id = str(final_item.get("rule_id") or "").strip().upper()
                    _strip_luxian_native_customer_diagnostics(
                        final_item,
                        native_result=(
                            native_direct_enabled
                            and final_rule_id in set(native_requested_rule_ids)
                        ),
                    )
                    if final_rule_id not in items_by_rule:
                        continue
                    if should_postprocess_formal_results:
                        if _safe_bool(final_item.get("can_show_as_defect")):
                            has_issue = True
                    items_by_rule[final_rule_id].append(final_item)

                if record_llm_call_count is None:
                    record_llm_call_count = local_executor_llm
                return {
                    "record_id": record_id,
                    "record_key": record_key,
                    "visit_id": visit_id,
                    "items_by_rule": items_by_rule,
                    "failed_by_rule": failed_by_rule,
                    "rule_stats": rule_stats,
                    "issue_record": has_issue,
                    "uncertain_record": has_uncertain,
                    "failed_record": any(bool(value) for value in failed_by_rule.values()),
                    "total_tokens": record_total_tokens,
                    "total_prompt_tokens": record_total_prompt_tokens,
                    "total_completion_tokens": record_total_completion_tokens,
                    "llm_call_count": record_llm_call_count,
                    "total_processing_time": local_total_processing_time,
                    "first_result_latency": record_first_result_latency,
                    "first_result_source": record_first_result_source,
                    "executor_program": local_executor_program,
                    "executor_llm": local_executor_llm,
                    "executor_native": local_executor_native,
                    "cache_hit": local_cache_hit,
                    "cache_miss": local_cache_miss,
                    "pack_metrics": record_pack_metrics,
                    "cot_summary": record_cot_summary,
                    "refine_summary": record_refine_summary,
                    "luxian_0609_shadow_evaluations": record_luxian_0609_shadow_evaluations,
                    "model_execution_stats": record_model_execution_stats,
                    "luxian_0609_usage_observation_complete": record_usage_observation_complete,
                    "luxian_0609_usage_unknown_executor_keys": sorted(record_usage_unknown_executor_keys),
                }
            except QCJobCancelled:
                raise
            except Exception as exc:
                failure_error = str(exc)
                failure_rule_id = str(getattr(exc, "rule_id", "") or "").strip().upper()
                if re.fullmatch(r"LX0609-(?!00)\d{2}-(?!00)\d{2}-(?!00)\d{2}", failure_rule_id):
                    failure_error = f"{failure_error} [{failure_rule_id}]"
                for rule_id in result_rule_ids:
                    state = result_rule_states[rule_id]
                    failed_by_rule[rule_id].append(
                        {
                            "rule_job_id": str(state["rule_job_id"]),
                            "rule_id": rule_id,
                            "rule_code": str(state["rule_code"]),
                            "rule_name": str(state["rule_name"]),
                            "record_id": record_id,
                            "visit_id": str(record.get("visit_id") or ""),
                            "patient_name": str(record.get("patient_name") or ""),
                            "department": str(record.get("department") or ""),
                            "error_phase": "evaluate_document",
                            "error": failure_error,
                        }
                    )
                return {
                    "record_id": record_id,
                    "record_key": record_key,
                    "visit_id": visit_id,
                    "items_by_rule": items_by_rule,
                    "failed_by_rule": failed_by_rule,
                    "rule_stats": rule_stats,
                    "issue_record": False,
                    "uncertain_record": False,
                    "failed_record": True,
                    "total_tokens": 0,
                    "total_prompt_tokens": 0,
                    "total_completion_tokens": 0,
                    "llm_call_count": 0,
                    "total_processing_time": 0.0,
                    "first_result_latency": 0.0,
                    "first_result_source": "",
                    "executor_program": 0,
                    "executor_llm": 0,
                    "executor_native": 0,
                    "cache_hit": 0,
                    "cache_miss": 0,
                    "pack_metrics": {},
                    "cot_summary": {},
                    "refine_summary": {},
                    "luxian_0609_shadow_evaluations": {},
                    "model_execution_stats": None,
                    "luxian_0609_usage_observation_complete": (
                        False if use_luxian_customer_results else None
                    ),
                    "luxian_0609_usage_unknown_executor_keys": sorted(record_usage_unknown_executor_keys),
                }

        record_timing_attempts = list(
            (retry_base_summary.get("record_timing") or {}).get("attempts") or []
        )

        @timed("record_execution")
        async def _evaluate_single_record(record: Dict[str, Any]) -> Dict[str, Any]:
            institute_id = str(record.get("institute_id") or "").strip()
            patient_id = str(record.get("patient_id") or "").strip()
            visit_id = str(
                record.get("visit_id") or record.get("record_id") or ""
            ).strip()
            root_job_id = str(
                current.get("parent_job_id")
                or filters.get("parent_job_id")
                or job_id
            ).strip()
            identity_scope = (
                luxian_0609_case_identity_scope(
                    case_coordinates=(institute_id, patient_id, visit_id),
                    identity_provider=identity_collector.provider_for_case(CaseRef(institute_id, patient_id, visit_id)),
                )
                if identity_collector is not None else nullcontext()
            )
            with identity_scope:
                with llm_observation_context(
                    business_scene="luxian_0609_qc",
                    root_job_id=root_job_id,
                    record_identity=(institute_id, patient_id, visit_id),
                    rule_set_key=rule_set_key,
                    rule_set_version=rule_set_version,
                    executor_key="legacy_orchestrated",
                ):
                    with diagnostic_capture.record_scope((institute_id, patient_id, visit_id)) if diagnostic_capture else nullcontext():
                        started_at = datetime.now(timezone.utc).isoformat()
                        started_clock = time.perf_counter()
                        result = None
                        try:
                            with live_result_scope(
                                lambda key, rows: _publish_family(record, key, rows)
                            ) if enable_incremental_results and native_direct_enabled else nullcontext():
                                from . import case_material_snapshot as materials
                                from .case_material_capture import obtain
                                from .validation_material_source import is_material_copy
                                from .bundles import assembly as material_assembly
                                from ..database import clinical_connection as material_clinical
                                identity = (institute_id, patient_id, visit_id)
                                backed_by_pg = getattr(getattr(material_assembly.engine, "dialect", None), "name", "") == "postgresql"
                                frozen = None
                                if all(identity) and not is_material_copy(patient_id, visit_id) and (material_clinical.configured() or backed_by_pg):
                                    try:
                                        frozen = await asyncio.to_thread(obtain, root_job_id, identity,
                                            retry=is_failed_rule_retry, cancellation_check=_raise_if_cancelled)
                                    except materials.MaterialSnapshotError as error:
                                        record = {**record, "_case_material_error": str(error)}
                                with materials.activate(frozen):
                                    if frozen is not None:
                                        scene = "final" if str(record.get("scope") or filters.get("query_scope") or current.get("scope")) == "final" else "running"
                                        try:
                                            inputs = material_assembly._assemble_scene_bundle(scene=scene, source_schema=frozen["schema"],
                                                institute_id=institute_id, patient_id=patient_id, visit_id=visit_id)
                                            record = {**record, "medical_text": inputs["medical_text"]}
                                        except Exception:
                                            record = {**record, "_case_material_error": "material_projection_failed"}
                                    result = await _evaluate_single_record_impl(record)
                                    if frozen is not None:
                                        result["case_material_fingerprint"] = frozen["fingerprint"]
                            result["_live_case"] = (institute_id, patient_id, visit_id)
                            return result
                        finally:
                            record_timing_attempts.append({
                                "record_key": CaseRef(institute_id, patient_id, visit_id).as_key(),
                                "attempt_kind": "retry" if is_failed_rule_retry else "initial",
                                "started_at": started_at,
                                "finished_at": datetime.now(timezone.utc).isoformat(),
                                "execution_seconds": round(max(0.0, time.perf_counter() - started_clock), 4),
                                "completed": bool(result is not None and not result.get("failed_record")
                                                  and not any(result.get("failed_by_rule", {}).values())),
                            })

        def _merge_record_result(record_result: Dict[str, Any], processed_records_count: int) -> None:
            nonlocal total_tokens
            nonlocal total_prompt_tokens
            nonlocal total_completion_tokens
            nonlocal total_processing_time
            nonlocal first_result_latency
            nonlocal first_result_source
            nonlocal executor_program
            nonlocal executor_llm
            nonlocal executor_native
            nonlocal actual_llm_call_count
            nonlocal cache_hit
            nonlocal cache_miss
            nonlocal total_pack_count
            nonlocal total_pack_size_weighted
            nonlocal total_pack_fallback_count
            nonlocal total_pack_parse_retry_count
            nonlocal total_single_rule_retries
            nonlocal total_context_tokens_estimate
            nonlocal total_refined_rule_count
            nonlocal model_execution_stats_total
            nonlocal usage_observation_complete

            completed_records_state["count"] = max(
                int(completed_records_state["count"]), processed_records_count
            )

            record_id = str(
                record_result.get("record_key") or record_result.get("record_id") or ""
            ).strip()
            if record_result.get("issue_record") is True:
                issue_record_ids.add(record_id)
            if record_result.get("uncertain_record") is True:
                uncertain_record_ids.add(record_id)
            if record_result.get("failed_record") is True:
                failed_record_ids.add(record_id)

            total_tokens += int(record_result.get("total_tokens") or 0)
            total_prompt_tokens += int(record_result.get("total_prompt_tokens") or 0)
            total_completion_tokens += int(record_result.get("total_completion_tokens") or 0)
            actual_llm_call_count += int(record_result.get("llm_call_count") or 0)
            total_processing_time += float(record_result.get("total_processing_time") or 0.0)
            executor_program += int(record_result.get("executor_program") or 0)
            executor_llm += int(record_result.get("executor_llm") or 0)
            executor_native += int(record_result.get("executor_native") or 0)
            cache_hit += int(record_result.get("cache_hit") or 0)
            cache_miss += int(record_result.get("cache_miss") or 0)
            model_execution_stats_total = _merge_luxian_model_execution_stats(
                model_execution_stats_total,
                _normalize_luxian_model_execution_stats(
                    record_result.get("model_execution_stats")
                ),
            )
            record_observed = record_result.get("luxian_0609_usage_observation_complete")
            if isinstance(record_observed, bool):
                usage_observation_complete = (
                    record_observed if usage_observation_complete is None
                    else usage_observation_complete and record_observed
                )
            record_unknown_keys = record_result.get("luxian_0609_usage_unknown_executor_keys")
            if isinstance(record_unknown_keys, (list, tuple)):
                usage_unknown_executor_keys.update(
                    key for key in record_unknown_keys if isinstance(key, str) and key
                )

            record_first_result_latency = float(record_result.get("first_result_latency") or 0.0)
            if (record_first_result_latency > 0 and first_result_latency is None
                    and not (enable_incremental_results and native_direct_enabled)):
                first_result_latency = record_first_result_latency
                first_result_source = str(record_result.get("first_result_source") or "")

            record_cot_summary = dict(record_result.get("cot_summary") or {})
            for cot_key, cot_value in record_cot_summary.items():
                cot_summary_total[cot_key] = int(cot_summary_total.get(cot_key) or 0) + int(cot_value or 0)

            record_refine_summary = dict(record_result.get("refine_summary") or {})
            if record_refine_summary:
                refine_summary_total["enabled"] = bool(record_refine_summary.get("enabled") is True)
                refine_summary_total["candidate_count"] = int(
                    refine_summary_total.get("candidate_count") or 0
                ) + int(record_refine_summary.get("candidate_count") or 0)
                refine_summary_total["refined_rule_count"] = int(
                    refine_summary_total.get("refined_rule_count") or 0
                ) + int(record_refine_summary.get("refined_rule_count") or 0)
                refine_summary_total["refine_failed_count"] = int(
                    refine_summary_total.get("refine_failed_count") or 0
                ) + int(record_refine_summary.get("refine_failed_count") or 0)
                total_refined_rule_count += int(record_refine_summary.get("refined_rule_count") or 0)
                reasons = dict(record_refine_summary.get("refine_reasons") or {})
                target_reasons = dict(refine_summary_total.get("refine_reasons") or {})
                for reason_key, reason_count in reasons.items():
                    key = str(reason_key or "").strip() or "unknown"
                    target_reasons[key] = int(target_reasons.get(key) or 0) + int(reason_count or 0)
                refine_summary_total["refine_reasons"] = target_reasons

            record_pack_metrics = dict(record_result.get("pack_metrics") or {})
            pack_count = int(record_pack_metrics.get("total_packs") or 0)
            avg_pack_size = float(record_pack_metrics.get("avg_pack_size") or 0.0)
            total_pack_count += pack_count
            total_pack_size_weighted += (avg_pack_size * pack_count)
            total_pack_fallback_count += int(record_pack_metrics.get("fallback_packs") or 0)
            total_pack_parse_retry_count += int(record_pack_metrics.get("pack_parse_retry_count") or 0)
            total_single_rule_retries += int(record_pack_metrics.get("single_rule_retries") or 0)
            total_context_tokens_estimate += int(record_pack_metrics.get("context_tokens_estimate") or 0)

            merge_luxian_0609_shadow_summaries(
                shadow_evaluation_summary,
                record_result.get("luxian_0609_shadow_evaluations") or {},
            )

            items_by_rule = dict(record_result.get("items_by_rule") or {})
            failed_by_rule = dict(record_result.get("failed_by_rule") or {})
            rule_stats = dict(record_result.get("rule_stats") or {})
            for rule_id in output_rule_ids:
                state = output_rule_states[rule_id]
                stats = dict(rule_stats.get(rule_id) or {})
                state["total_tokens"] = int(state.get("total_tokens") or 0) + int(
                    stats.get("total_tokens") or 0
                )
                state["total_processing_time"] = float(state.get("total_processing_time") or 0.0) + float(
                    stats.get("total_processing_time") or 0.0
                )
                state["executor_program"] = int(state.get("executor_program") or 0) + int(
                    stats.get("executor_program") or 0
                )
                state["executor_llm"] = int(state.get("executor_llm") or 0) + int(
                    stats.get("executor_llm") or 0
                )
                state["executor_native"] = int(state.get("executor_native") or 0) + int(
                    stats.get("executor_native") or 0
                )
                for item in list(items_by_rule.get(rule_id) or []):
                    state["items"].append(item)
                    all_items.append(item)
                for failed in list(failed_by_rule.get(rule_id) or []):
                    state["failed_records"].append(failed)
                    all_failed_records.append(failed)

            live_buffer.finish(record_result.get("_live_case", ()))
            summary_patch = _build_progress_patch(processed_records_count)
            update_kwargs: Dict[str, Any] = {}
            if enable_incremental_results:
                progress_items = live_buffer.combine(all_items)
                progress_failures = list(all_failed_records)
                if is_failed_rule_retry:
                    progress_items, progress_failures = merge_failed_rule_retry_results(
                        base_items=retry_base_items,
                        base_failures=retry_base_failures,
                        retry_items=all_items,
                        retry_failures=all_failed_records,
                    )
                summary_patch = {
                    **summary_patch,
                    "stream_state": _build_stream_state(record_result, processed_records_count),
                    "updated_at": datetime.now(timezone.utc).isoformat(),
                }
                if is_failed_rule_retry:
                    summary_patch["stream_state"] = {
                        **dict(summary_patch.get("stream_state") or {}),
                        "partial_item_count": len(progress_items),
                    }
                update_kwargs = {
                    "items": progress_items,
                    "failed_records": progress_failures,
                }

            write_result = workspace.update_batch_job_progress(
                job_id=job_id,
                **attempt_kwargs,
                step_key="run",
                rule_index=len(output_rule_ids) if output_rule_ids else 0,
                rule_count=total_rules,
                processed_records=processed_records_count,
                total_records=total_records,
                summary_patch=summary_patch,
                progress_patch=_record_runtime_progress(processed_records_count),
                **update_kwargs,
            )

            if (enable_incremental_results and not is_failed_rule_retry and first_result_latency is None and all_items
                    and write_result is not None and write_result.get("status") != "canceled"):
                first_result_latency = max(0.0, time.perf_counter() - job_wall_started)
                first_result_source = "validated_record_write"

        initial_progress_patch = _build_progress_patch(0)
        if enable_incremental_results:
            initial_progress_patch = {
                **initial_progress_patch,
                "stream_state": {
                    "enabled": True,
                    "processed_records": 0,
                    "total_records": total_records,
                    "latest_record_id": "",
                    "latest_visit_id": "",
                    "latest_result_count": 0,
                    "partial_item_count": len(retry_base_items)
                    if is_failed_rule_retry
                    else 0,
                    "partial_rule_result_count": len(output_rule_ids),
                    "started_at": job_started_at.isoformat(),
                    "updated_at": datetime.now(timezone.utc).isoformat(),
                },
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }
            if is_failed_rule_retry:
                # 自动补跑期间页面仍可从顶层 items 读取已完成结果；清空历史
                # 嵌套副本和性能明细，避免每次进度更新重复序列化几十 MB。
                # retry_base_summary 已在本次执行内存中保留，最终汇总会完整恢复。
                initial_progress_patch["rule_results"] = []
                initial_progress_patch["performance_profile"] = {}
                initial_progress_patch["last_retry_performance_profile"] = {}

        workspace.update_batch_job_progress(
            job_id=job_id,
            **attempt_kwargs,
            step_key="run",
            rule_index=0,
            rule_count=total_rules,
            processed_records=0,
            total_records=total_records,
            summary_patch=initial_progress_patch,
            progress_patch=_record_runtime_progress(0),
        )

        if run_mode == "parallel" and total_records > 1:
            semaphore = asyncio.Semaphore(max_parallel_records)

            async def _evaluate_with_limit(record: Dict[str, Any]) -> Dict[str, Any]:
                async with semaphore:
                    active_records_state["count"] += 1
                    processed_count = int(completed_records_state["count"])
                    workspace.update_batch_job_progress(
                        job_id=job_id,
                        **attempt_kwargs,
                        step_key="run",
                        rule_index=0,
                        rule_count=total_rules,
                        processed_records=processed_count,
                        total_records=total_records,
                        summary_patch=_build_progress_patch(processed_count),
                        progress_patch=_record_runtime_progress(processed_count),
                    )
                    try:
                        return await _evaluate_single_record(record)
                    finally:
                        active_records_state["count"] = max(
                            0,
                            int(active_records_state["count"]) - 1,
                        )

            tasks = [
                asyncio.create_task(
                    _evaluate_with_limit(record),
                    name=f"sichuan-batch-{job_id}-{idx + 1}",
                )
                for idx, record in enumerate(hydrated_records)
            ]
            completed_count = 0
            try:
                for future in asyncio.as_completed(tasks):
                    _raise_if_cancelled()
                    record_result = await future
                    completed_count += 1
                    _merge_record_result(record_result, completed_count)
            except QCJobCancelled:
                await _cancel_pending_batch_tasks(tasks)
                logger.info("四川批量任务 %s 已取消，停止执行", job_id)
                return
            except asyncio.CancelledError:
                # 独立 consumer 断连、恢复 owner 失败或进程关闭时，不能在父协程
                # 已取消后由 finally 等待其余病例继续发起模型调用。先取消全部子任务
                # 并回收，再把取消传播给进程生命周期 owner。
                await _cancel_pending_batch_tasks(tasks)
                raise
            finally:
                await asyncio.gather(*tasks, return_exceptions=True)
        else:
            for processed_index, record in enumerate(hydrated_records, start=1):
                active_records_state["count"] = 1
                processed_count = int(completed_records_state["count"])
                workspace.update_batch_job_progress(
                    job_id=job_id,
                    **attempt_kwargs,
                    step_key="run",
                    rule_index=0,
                    rule_count=total_rules,
                    processed_records=processed_count,
                    total_records=total_records,
                    summary_patch=_build_progress_patch(processed_count),
                    progress_patch=_record_runtime_progress(processed_count),
                )
                try:
                    _raise_if_cancelled()
                    record_result = await _evaluate_single_record(record)
                except QCJobCancelled:
                    logger.info("四川批量任务 %s 已取消，停止执行", job_id)
                    return
                finally:
                    active_records_state["count"] = 0
                _merge_record_result(record_result, processed_index)

        rule_results = _build_rule_results_snapshot(
            processed_records_count=total_records,
            final=True,
        )
        if is_failed_rule_retry:
            all_items, all_failed_records = merge_failed_rule_retry_results(
                base_items=retry_base_items,
                base_failures=retry_base_failures,
                retry_items=all_items,
                retry_failures=all_failed_records,
            )
            total_records = int(
                retry_base_summary.get("total_records")
                or current.get("total_records")
                or total_records
            )
            rule_results = merge_failed_rule_retry_rule_results(
                base_rule_results=list(retry_base_summary.get("rule_results") or []),
                retry_rule_results=rule_results,
                merged_items=all_items,
                merged_failures=all_failed_records,
                total_records=total_records,
            )
            issue_record_ids = {
                str(item.get("record_key") or item.get("record_id") or "").strip()
                for item in all_items
                if str(item.get("status") or "").strip().lower()
                in {"non_compliant", "ai_suggested_non_compliant"}
                and str(item.get("record_key") or item.get("record_id") or "").strip()
            }
            uncertain_record_ids = {
                str(item.get("record_key") or item.get("record_id") or "").strip()
                for item in all_items
                if str(item.get("status") or "").strip().lower() == "uncertain"
                and str(item.get("record_key") or item.get("record_id") or "").strip()
            }
            failed_record_ids = {
                str(item.get("record_key") or item.get("record_id") or "").strip()
                for item in all_failed_records
                if str(item.get("record_key") or item.get("record_id") or "").strip()
            }
            total_tokens += int(retry_base_summary.get("total_tokens") or 0)
            total_prompt_tokens += int(retry_base_summary.get("total_prompt_tokens") or 0)
            total_completion_tokens += int(retry_base_summary.get("total_completion_tokens") or 0)
            total_processing_time += float(
                retry_base_summary.get("total_processing_time") or 0.0
            )
            base_executor_breakdown = dict(
                retry_base_summary.get("executor_breakdown") or {}
            )
            executor_program += int(base_executor_breakdown.get("program") or 0)
            executor_llm += int(base_executor_breakdown.get("llm") or 0)
            executor_native += int(base_executor_breakdown.get("native") or 0)
            base_cache_breakdown = dict(retry_base_summary.get("cache_breakdown") or {})
            cache_hit += int(base_cache_breakdown.get("hit") or 0)
            cache_miss += int(base_cache_breakdown.get("miss") or 0)
            model_execution_stats_total = _merge_luxian_model_execution_stats(
                _normalize_luxian_model_execution_stats(
                    retry_base_summary.get("model_execution_stats")
                ),
                model_execution_stats_total,
            )
            base_observed = retry_base_summary.get("luxian_0609_usage_observation_complete")
            if isinstance(base_observed, bool):
                usage_observation_complete = (
                    base_observed if usage_observation_complete is None
                    else usage_observation_complete and base_observed
                )
            base_unknown_keys = retry_base_summary.get("luxian_0609_usage_unknown_executor_keys")
            if isinstance(base_unknown_keys, (list, tuple)):
                usage_unknown_executor_keys.update(
                    key for key in base_unknown_keys if isinstance(key, str) and key
                )

        if (
            use_luxian_customer_results and failed_record_ids and all_failed_records
            and any(
                failure.get("error_phase") not in {"result_status", "result_missing"}
                for failure in all_failed_records
            )
        ):
            first_failure_error = str(
                all_failed_records[0].get("error") or ""
            ).strip()
            # 正式客户结果在任一病例失败时必须停止进入 Canonical，但不能丢失
            # 失败定位信息；否则任务只会留下一个无法调试的“执行失败”。
            failure_diagnostics: list[dict[str, str]] = []
            seen_failure_diagnostics: set[tuple[str, str, str]] = set()
            for failed in all_failed_records:
                diagnostic = {
                    "record_id": str(failed.get("record_id") or "").strip(),
                    "visit_id": str(failed.get("visit_id") or "").strip(),
                    "rule_id": str(failed.get("rule_id") or "").strip().upper(),
                    "error_phase": str(failed.get("error_phase") or "").strip(),
                    "error": str(failed.get("error") or "").strip()[:240],
                }
                key = (
                    diagnostic["record_id"],
                    diagnostic["rule_id"],
                    diagnostic["error"],
                )
                if key in seen_failure_diagnostics:
                    continue
                seen_failure_diagnostics.add(key)
                failure_diagnostics.append(diagnostic)
                if len(failure_diagnostics) >= 40:
                    break
            workspace.update_batch_job_progress(
                job_id=job_id,
                **attempt_kwargs,
                step_key="failed",
                rule_index=len(output_rule_ids),
                rule_count=total_rules,
                processed_records=total_records,
                total_records=total_records,
                summary_patch={
                    "failed_record_count": len(failed_record_ids),
                    "failed_count": len(all_failed_records),
                    "failure_diagnostics": failure_diagnostics,
                },
                progress_patch=_record_runtime_progress(total_records),
            )
            logger.error(
                "LX0609正式质控未形成可交付结果，停止进入Canonical: first_error=%s",
                first_failure_error or "unknown",
            )
            invalid_facts_match = re.fullmatch(
                r"invalid customer display facts(?: \[(LX0609-(?!00)\d{2}-(?!00)\d{2}-(?!00)\d{2})\])?",
                first_failure_error,
            )
            customer_safe_reason = "规则执行失败"
            if invalid_facts_match:
                customer_safe_reason = (
                    "客户展示事实不符合交付合同（invalid customer display facts）"
                )
                if invalid_facts_match.group(1):
                    customer_safe_reason += f"；质控点 {invalid_facts_match.group(1)}"
            raise ValueError(
                f"病历质控未形成可交付结果：{customer_safe_reason}"
            )

        postprocess_summary = summarize_postprocessed_results(all_items) if should_postprocess_job else {}
        display_status_counts = dict(postprocess_summary.get("display_status_counts") or {})
        postprocess_label_counts = dict(postprocess_summary.get("postprocess_label_counts") or {})
        data_quality_gap_record_ids = {
            str(item.get("record_key") or item.get("record_id") or "")
            for item in all_items
            if (
                str(item.get("status") or "") == "data_gap"
                or str(item.get("display_status") or "") == "data_quality_gap"
            )
            and str(item.get("record_key") or item.get("record_id") or "")
        }
        technical_error_record_ids = {
            str(item.get("record_key") or item.get("record_id") or "")
            for item in all_items
            if str(item.get("display_status") or "") == "technical_error_internal"
            and str(item.get("record_key") or item.get("record_id") or "")
        }
        rejected_by_system_record_ids = {
            str(item.get("record_key") or item.get("record_id") or "")
            for item in all_items
            if str(item.get("display_status") or "") == "rejected_by_system"
            and str(item.get("record_key") or item.get("record_id") or "")
        }
        not_applicable_record_ids = _records_with_only_status(all_items, "not_applicable")
        record_status_counts = _build_record_status_counts(
            total_records=total_records,
            issue_record_ids=issue_record_ids,
            uncertain_record_ids=uncertain_record_ids,
            data_gap_record_ids=data_quality_gap_record_ids,
            failed_record_ids=failed_record_ids,
            not_applicable_record_ids=not_applicable_record_ids,
        )
        result_status_counts = _build_item_status_counts(all_items)
        final_wall_clock_time = max(0.0, time.perf_counter() - job_wall_started)
        performance_profile = _build_batch_performance_profile(
            job_id=job_id,
            items=all_items,
            total_records=total_records,
            customer_rule_count=len(output_rule_ids),
            execution_rule_count=len(rule_ids),
            wall_clock_time=final_wall_clock_time,
            first_result_latency=float(first_result_latency or 0.0),
            actual_llm_pack_call_count=total_pack_count,
            actual_llm_call_count=actual_llm_call_count,
            actual_total_tokens=total_tokens,
            actual_prompt_tokens=total_prompt_tokens,
            actual_completion_tokens=total_completion_tokens,
        )
        performance_profile["stage_timing"] = current_timing_snapshot()

        summary = {
            "record_timing": summarize_record_timings(record_timing_attempts),
            "rule_set_key": rule_set_key,
            "rule_set_name": rule_set_name,
            "rule_set_version": rule_set_version,
            "execution_strategy": execution_strategy,
            "quality_profile": quality_profile,
            "bucket_strategy": bucket_strategy,
            "batch_output_mode": batch_output_mode,
            "enable_selective_refine": enable_selective_refine,
            "refine_confidence_threshold": refine_confidence_threshold,
            "max_refine_candidates": max_refine_candidates,
            "run_mode": run_mode,
            "total_records": total_records,
            "success_count": max(0, total_records - len(failed_record_ids)),
            "failed_record_count": len(failed_record_ids),
            "failed_count": len(all_failed_records),
            "issue_records": len(issue_record_ids),
            "uncertain_records": len(uncertain_record_ids),
            "compliant_records": record_status_counts["compliant"],
            "postprocess_summary": postprocess_summary,
            "confirmed_defect_count": int(postprocess_summary.get("confirmed_defect_count") or len(issue_record_ids)),
            "qc_review_candidate_count": int(postprocess_summary.get("qc_review_candidate_count") or 0),
            "needs_review_count": int(postprocess_summary.get("needs_review_count") or 0),
            "data_quality_gap_count": int(postprocess_summary.get("data_quality_gap_count") or 0),
            "rejected_by_system_count": int(postprocess_summary.get("rejected_by_system_count") or 0),
            "technical_error_internal_count": int(postprocess_summary.get("technical_error_internal_count") or 0),
            "non_compliant_downgraded_count": int(postprocess_summary.get("non_compliant_downgraded_count") or 0),
            "display_status_counts": display_status_counts,
            "postprocess_label_counts": postprocess_label_counts,
            "data_quality_gap_records": len(data_quality_gap_record_ids),
            "not_applicable_records": record_status_counts["not_applicable"],
            "rejected_by_system_records": len(rejected_by_system_record_ids),
            "technical_error_records": len(technical_error_record_ids),
            "record_status_breakdown": record_status_counts,
            "status_breakdown": result_status_counts,
            "total_tokens": int(total_tokens),
            "total_prompt_tokens": int(total_prompt_tokens),
            "total_completion_tokens": int(total_completion_tokens),
            "total_processing_time": float(total_processing_time),
            "wall_clock_time": final_wall_clock_time,
            "first_result_latency": round(float(first_result_latency or 0.0), 4),
            "first_result_source": first_result_source,
            "rule_count": len(output_rule_ids),
            "execution_rule_count": len(rule_ids),
            "processed_rule_count": len(rule_results),
            "executor_breakdown": {
                "program": executor_program,
                "llm": executor_llm,
                "native": executor_native,
            },
            "cache_breakdown": {
                "hit": cache_hit,
                "miss": cache_miss,
            },
            "pack_metrics": {
                "quality_profile": quality_profile,
                "bucket_strategy": bucket_strategy,
                "batch_output_mode": batch_output_mode,
                "total_packs": total_pack_count,
                "avg_pack_size": round((total_pack_size_weighted / total_pack_count), 2) if total_pack_count else 0.0,
                "fallback_packs": total_pack_fallback_count,
                "single_rule_retries": total_single_rule_retries,
                "pack_parse_retry_count": total_pack_parse_retry_count,
                "context_tokens_estimate": int(total_context_tokens_estimate / total_pack_count) if total_pack_count else 0,
            },
            "refine_summary": refine_summary_total,
            "refined_rule_count": total_refined_rule_count,
            "cot_summary": cot_summary_total,
            "result_aggregation": _build_result_aggregation(all_items),
            "performance_profile": performance_profile,
            "luxian_0609_shadow_evaluations": shadow_evaluation_summary,
            "rule_results": rule_results,
            "stream_state": {
                "enabled": enable_incremental_results,
                "processed_records": total_records,
                "total_records": total_records,
                "latest_record_id": "",
                "latest_visit_id": "",
                "latest_result_count": 0,
                "partial_item_count": len(all_items),
                "partial_rule_result_count": len(output_rule_ids),
                "started_at": job_started_at.isoformat(),
                "updated_at": datetime.now(timezone.utc).isoformat(),
            },
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        if use_luxian_customer_results:
            summary.update({
                "execution_status": (
                    "partial_failed" if all_items else "failed"
                ) if all_failed_records else "completed",
                "completed_rule_count": len(all_items),
                "failed_rule_count": len(all_failed_records),
                "failed_rule_ids": sorted({
                    str(item.get("rule_id") or "").strip().upper()
                    for item in all_failed_records
                    if item.get("rule_id")
                }),
            })
        model_execution_summary = _build_luxian_model_execution_summary(model_execution_stats_total)
        if model_execution_summary is not None:
            summary["model_execution_stats"] = model_execution_summary
        if use_luxian_customer_results:
            if usage_observation_complete is None:
                usage_observation_complete = total_records == 0
            summary["luxian_0609_usage_observation_complete"] = usage_observation_complete
            summary["luxian_0609_usage_unknown_executor_keys"] = sorted(usage_unknown_executor_keys)
        automatic_retry_plan = build_failed_rule_auto_retry_plan(
            summary=summary,
            failures=all_failed_records,
            retry_scope=failed_rule_retry_scope,
        )
        summary["automatic_failed_rule_retry"] = automatic_retry_plan
        if is_failed_rule_retry:
            original_rule_count = int(
                retry_base_summary.get("rule_count")
                or len(retry_base_summary.get("rule_results") or [])
                or len(rule_results)
            )
            summary.update(
                {
                    "rule_count": original_rule_count,
                    "execution_rule_count": int(
                        retry_base_summary.get("execution_rule_count")
                        or original_rule_count
                    ),
                    "processed_rule_count": original_rule_count,
                    "rule_results": rule_results,
                    "retry_status": "completed"
                    if not all_failed_records
                    else "partial_failed",
                    "retry_attempt": int(failed_rule_retry_scope.get("attempt") or 1),
                    "retry_pending_count": int(
                        failed_rule_retry_scope.get("pending_count") or 0
                    ),
                    "retry_remaining_count": len(all_failed_records),
                    "retry_recovered_count": max(
                        0,
                        int(failed_rule_retry_scope.get("pending_count") or 0)
                        - sum(
                            str(failure.get("rule_id") or "") in
                            (failed_rule_retry_scope.get("record_rule_map") or {}).get(
                                CaseRef.from_mapping(failure).as_key(), ())
                            for failure in all_failed_records
                        ),
                    ),
                    "last_retry_performance_profile": performance_profile,
                    "performance_profile": retry_base_summary.get("performance_profile")
                    or performance_profile,
                    "stream_state": {
                        **dict(summary.get("stream_state") or {}),
                        "processed_records": total_records,
                        "total_records": total_records,
                        "partial_item_count": len(all_items),
                        "partial_rule_result_count": original_rule_count,
                    },
                }
            )
        aggregate_progress_summary = {
            key: value
            for key, value in summary.items()
            if key
            not in {
                "rule_results",
                "performance_profile",
                "last_retry_performance_profile",
            }
        }
        workspace.update_batch_job_progress(
            job_id=job_id,
            **attempt_kwargs,
            step_key="aggregate",
            rule_index=len(output_rule_ids),
            rule_count=total_rules,
            processed_records=total_records,
            total_records=total_records,
            summary_patch={
                **aggregate_progress_summary,
                "rule_results": [],
                "performance_profile": {},
                "last_retry_performance_profile": {},
            },
            progress_patch=_record_runtime_progress(total_records),
        )
        with diagnostic_capture.result_scope() if diagnostic_capture else nullcontext():
            completed = workspace.complete_batch_job(
                job_id=job_id,
                **attempt_kwargs,
                summary=summary,
                items=all_items,
                failed_records=all_failed_records,
            )
        if attempt_filters_json is not None and completed is not True:
            return
        if automatic_retry_plan.get("should_retry") is True:
            created_by = str(current.get("created_by") or "").strip()
            delay_seconds = max(
                0.0,
                float(automatic_retry_plan.get("delay_seconds") or 0.0),
            )
            is_rabbitmq_dispatch = (
                qc_dispatch_mode_from_filters(filters) == "rabbitmq"
            )
            retried_job = _enqueue_automatic_failed_rule_retry(
                workspace=workspace,
                job_id=job_id,
                created_by=created_by,
                expected_attempt_filters_json=attempt_filters_json,
                retry_delay_seconds=(delay_seconds if is_rabbitmq_dispatch else None),
            )
            if not retried_job or str(retried_job.get("status") or "") != "queued":
                logger.error(
                    "部分失败任务无法自动补跑: job_id=%s created_by_present=%s",
                    job_id,
                    bool(created_by),
                )
                return
            logger.warning(
                "部分失败任务自动补跑: job_id=%s attempt=%s/%s failed_items=%s delay_seconds=%.1f",
                job_id,
                automatic_retry_plan.get("next_attempt"),
                automatic_retry_plan.get("max_attempts"),
                len(all_failed_records),
                delay_seconds,
            )
            if identity_collector is not None:
                identity_collector.close()
            finish_current_timing()
            # RabbitMQ 任务的下一代消息已由 retry_batch_job 与状态更新同事务写入
            # Outbox。当前 delivery 只需返回给 consumer 复核新代次后 ACK，不能在
            # 进程内 sleep/递归占住唯一批任务槽位，也不能另开第二事务补 Outbox。
            if is_rabbitmq_dispatch:
                return
            if delay_seconds:
                await asyncio.sleep(delay_seconds)
            await run_sichuan_workspace_batch_job(
                job_id,
                workspace=workspace,
                qc_service_provider=qc_service_provider,
                record_concurrency_limit=record_concurrency_limit,
                external_cancellation_check=external_cancellation_check,
                expected_dispatch_generation=expected_dispatch_generation,
            )
    except QCJobCancelled:
        logger.info("四川规则批量任务 %s 已取消，后台执行已停止", job_id)
    except ProviderConfigurationError:
        # Provider/Gateway 身份损坏必须让独立进程失败关闭；不能吞成普通任务
        # 失败后继续消费，也不能回退另一个云 Provider。
        raise
    except Exception as exc:
        logger.exception("四川规则批量任务执行失败: %s", exc)
        workspace.fail_batch_job(
            job_id=job_id, error_message=str(exc),
            **(
                attempt_kwargs if attempt_filters_json is not None
                else {
                    "queued_only": True,
                    "expected_queued_filters_json": claim_filters_json,
                } if formal_0609_job else {}
            ),
        )
    finally:
        if identity_collector is not None:
            identity_collector.close()
        if lease_stop is not None:
            lease_stop.set()
