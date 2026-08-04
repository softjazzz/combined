from typing import List, Dict, Any, Optional, Sequence
import asyncio
import uuid
import json
import hashlib
import logging
import re
import time
from pathlib import Path
from pydantic import BaseModel
from fastapi import APIRouter, HTTPException, Query, Request, Depends
from fastapi.responses import Response, StreamingResponse
from datetime import datetime, timezone

from ..core.response import success_response, paginated_response, error_response, get_trace_id, ErrorCode, StatusCode
from ..services.sichuan_qc_service import SichuanQCService, RuleSourceGuardError
from ..services.llm_config_loader import LLMConfigLoader
from ..services.qc_input_adapters import evaluate_running_final_bundle
from ..services.qc_input_adapters.running_final_bundle_runtime import load_running_final_bundle
from ..services.fast_screen_qc import (
    EXECUTION_STRATEGY_FAST_SCREEN,
    normalize_execution_strategy,
    run_final_fast_screen,
)
from ..services.detached_task_runner import submit_detached_task
from ..services.qc_rule_sets import get_sichuan_rule_set, list_sichuan_rule_sets
from ..services.luxian_0609 import (
    LUXIAN_0609_RULE_SET_KEY,
    LUXIAN_0609_RULE_SET_NAME,
    build_luxian_0609_package_plan_from_settings,
    filter_luxian_0609_rules_by_documents,
    get_luxian_0609_rule,
    load_luxian_0609_dependency_inventory,
    load_luxian_0609_rules,
    resolve_package_rollback_execution_rule_ids,
    review_luxian_0609_batch_job,
)
from ..services.sc_rule_launch_tier import (
    load_sc_intrinsic_launch_tier_map,
    resolve_sc_intrinsic_launch_tier,
)
from ..core.supabase_client import get_supabase
from ..core.settings import get_settings
from ..core.security import require_admin, get_current_user
from ..services.custom_qc_workspace_service import (
    CustomQCWorkspaceService,
    customer_safe_projection_key,
    project_customer_safe_batch_job,
)
from ..services.sample_programmatic_evidence import build_programmatic_evidence_payload
from ..services.luxian_0609.runtime_shadow_hook import run_luxian_0609_runtime_shadow
from ..services.luxian_0609.evaluation_horizon import (
    build_record_evaluation_horizon_snapshot,
    resolve_record_evaluation_horizon_policy,
)
from ..services.luxian_0609.surgery_procedure_catalog import (
    CATALOG_VERSION as SURGERY_PROCEDURE_CATALOG_VERSION,
    OPERATION_CATEGORIES,
    SURGERY_CATEGORY,
    load_surgery_procedure_catalog,
)
from ..services.luxian_0609.rule_decision_settings import (
    resolve_mainline_rule_decision_settings,
)
from ..services.sample_validation_rule_sets import (
    apply_programmatic_rule_runtime_overrides,
    get_sample_programmatic_rule_set,
    is_workspace_batch_draft_id,
)
from ..services.qc_result_postprocessor import (
    postprocess_qc_result,
    summarize_postprocessed_results,
)
from ..services.qc_result_adjudicator import adjudicate_postprocessed_qc_results
from ..services.qc_cancellation import QCJobCancelled, raise_if_cancelled
from ..services.effect_priority_qc import (
    BATCH_OUTPUT_MODE_FULL,
    DEFAULT_MAX_REFINE_CANDIDATES,
    DEFAULT_REFINE_CONFIDENCE_THRESHOLD,
    QUALITY_PROFILE_EFFECT_PRIORITY,
    QUALITY_PROFILE_THROUGHPUT,
    normalize_batch_output_mode,
    normalize_max_refine_candidates,
)
from ..services.customer_rule_sets import CUSTOMER_LUXIAN_RULE_SET_KEY

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/qc/sichuan", tags=["qc-sichuan"])


@router.get("/surgery-procedure-catalog")
async def surgery_procedure_catalog(
    request: Request,
    keyword: str = Query(default="", max_length=100, description="手术操作编码或名称"),
    category: str = Query(default="", description="手术或操作分类"),
    effective_level: str = Query(default="", description="生效手术等级"),
    source: str = Query(default="", description="等级口径来源"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
):
    """分页查询质控引擎正在使用的手术/操作分级目录。"""

    catalog = load_surgery_procedure_catalog()
    normalized_keyword = str(keyword or "").strip().casefold()
    normalized_category = str(category or "").strip()
    normalized_level = str(effective_level or "").strip()
    normalized_source = str(source or "").strip()

    filtered = [
        item
        for item in catalog
        if (
            not normalized_keyword
            or normalized_keyword in item.code.casefold()
            or normalized_keyword in item.name.casefold()
        )
        and (
            not normalized_category
            or item.category == normalized_category
            or (
                normalized_category == "operation"
                and item.category in OPERATION_CATEGORIES
            )
        )
        and (not normalized_level or item.effective_level == normalized_level)
        and (not normalized_source or item.source == normalized_source)
    ]
    level_rank = {"四级": 4, "三级": 3, "二级": 2, "一级": 1}
    filtered.sort(
        key=lambda item: (
            item.category != SURGERY_CATEGORY,
            -level_rank.get(item.effective_level, 0),
            item.code,
        )
    )
    start = (page - 1) * page_size
    page_items = filtered[start : start + page_size]

    surgery_count = sum(item.category == SURGERY_CATEGORY for item in catalog)
    level_four_count = sum(
        item.category == SURGERY_CATEGORY and item.effective_level == "四级"
        for item in catalog
    )
    source_labels = {
        "hospital_performance": "院内绩效分配",
        "national_catalog": "2025年国家临床版目录",
    }
    return success_response(
        data={
            "version": SURGERY_PROCEDURE_CATALOG_VERSION,
            "policy": {
                "level_priority": "院内绩效分配优先于2025年国家临床版手术分级目录",
                "conditional_level_four": "条件四级按四级手术执行",
                "category_boundary": "治疗性操作、诊断性操作和介入治疗不按手术触发",
            },
            "summary": {
                "total": len(catalog),
                "surgery": surgery_count,
                "operation": len(catalog) - surgery_count,
                "level_four_surgery": level_four_count,
            },
            "filter_options": {
                "categories": [SURGERY_CATEGORY, *sorted(OPERATION_CATEGORIES)],
                "levels": ["四级", "三级", "二级", "一级"],
                "sources": [
                    {"value": key, "label": label}
                    for key, label in source_labels.items()
                ],
            },
            "items": [
                {
                    "code": item.code,
                    "name": item.name,
                    "category": item.category,
                    "effective_level": item.effective_level,
                    "raw_level": item.raw_level,
                    "source": item.source,
                    "source_label": source_labels.get(item.source, "国家目录"),
                }
                for item in page_items
            ],
            "total": len(filtered),
            "page": page,
            "page_size": page_size,
            "total_pages": (len(filtered) + page_size - 1) // page_size,
        },
        message="获取手术操作分级目录成功",
        trace_id=get_trace_id(request),
    )


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


def _luxian_0609_rollback_rule_ids(
    customer_rule_ids: List[str] | tuple[str, ...],
) -> tuple[str, ...]:
    return resolve_package_rollback_execution_rule_ids(
        inventory=load_luxian_0609_dependency_inventory(),
        selected_rule_ids=customer_rule_ids,
    )


def _luxian_0609_compatibility_rule_ids(
    customer_rule_ids: List[str] | tuple[str, ...],
    *,
    settings: Any,
) -> tuple[str, ...]:
    """按当前族开关计算仍会进入兼容链的旧执行规则。"""

    if not customer_rule_ids:
        return ()
    settings = resolve_mainline_rule_decision_settings(settings)
    if not getattr(settings, "LUXIAN_0609_CUSTOMER_AGGREGATION_ENABLED", False):
        return _luxian_0609_rollback_rule_ids(customer_rule_ids)
    plan = build_luxian_0609_package_plan_from_settings(
        inventory=load_luxian_0609_dependency_inventory(),
        selected_rule_ids=customer_rule_ids,
        settings=settings,
    )
    return plan.compatibility_execution_rule_ids

# 全局服务实例（将在启动时初始化）
service: Optional[SichuanQCService] = None
_rule_source_monitor_task: Optional[asyncio.Task] = None


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


def _build_workspace_record_scene_snapshot(
    records: Sequence[Dict[str, Any]],
    *,
    query_scope: str,
) -> List[Dict[str, str]]:
    snapshot: List[Dict[str, str]] = []
    for record in records:
        record_id = str(record.get("record_id") or record.get("visit_id") or "").strip()
        if not record_id:
            continue
        normalized_record_scene = str(record.get("scope") or "").strip().lower()
        record_scene = (
            normalized_record_scene
            if normalized_record_scene in {"running", "final"}
            else "unknown"
        )
        snapshot.append(
            {
                "record_id": record_id,
                "record_scene": record_scene,
                "resolved_scene": _resolve_workspace_bundle_scene(
                    query_scope=query_scope,
                    record_scope=normalized_record_scene,
                ),
                "discharge_snapshot": str(
                    record.get("discharge_datetime") or record.get("discharge_date") or ""
                ).strip(),
            }
        )
    return sorted(snapshot, key=lambda item: item["record_id"])


async def _rule_source_monitor_loop() -> None:
    while True:
        try:
            settings = get_settings()
            interval_seconds = max(15, int(getattr(settings, "QC_SC_RULE_SOURCE_MONITOR_INTERVAL_SECONDS", 60) or 60))
            qc_service = await get_qc_service()
            # 监控任务仅告警，不在此处阻断请求。
            qc_service.assert_sc_rule_source_ready(
                context="rules_source_monitor",
                block_batch=False,
            )
            await asyncio.sleep(interval_seconds)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            logger.error("规则来源巡检异常: %s", exc, exc_info=True)
            await asyncio.sleep(30)


def start_rule_source_monitor() -> None:
    global _rule_source_monitor_task
    settings = get_settings()
    enabled = bool(getattr(settings, "QC_SC_RULE_SOURCE_MONITOR_ENABLED", False)) or str(settings.ENV or "").strip().lower() == "production"
    if not enabled:
        return
    if _rule_source_monitor_task and not _rule_source_monitor_task.done():
        return
    loop = asyncio.get_running_loop()
    _rule_source_monitor_task = loop.create_task(_rule_source_monitor_loop(), name="qc-rule-source-monitor")
    logger.info("已启动 SC 规则来源巡检任务")


async def stop_rule_source_monitor() -> None:
    global _rule_source_monitor_task
    task = _rule_source_monitor_task
    _rule_source_monitor_task = None
    if not task:
        return
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass

async def init_qc_service():
    """初始化质控服务，从数据库加载配置"""
    global service
    try:
        # 尝试从数据库加载配置
        config = await LLMConfigLoader.load_config(config_name="default", user_id=None)
        service = SichuanQCService(config)
        logger.info(f"✅ 四川质控服务初始化成功: model={service.client.model}, source={service.client.config_source}")
    except Exception as exc:
        logger.warning(f"从数据库加载配置失败: {exc}，使用 .env 配置初始化")
        service = SichuanQCService()

async def get_qc_service() -> SichuanQCService:
    """
    依赖注入：获取配置好的质控服务实例

    Returns:
        使用数据库配置的SichuanQCService实例
    """
    global service
    if service is None:
        await init_qc_service()
    return service


class SichuanEvaluateRequest(BaseModel):
    document_id: str
    document_content: Optional[str] = None
    document_type: Optional[str] = "病程记录"
    document_types: Optional[List[str]] = None
    rule_ids: Optional[List[str]] = None
    bundle_input: Optional[Dict[str, Any]] = None
    use_multi_document_mode: Optional[bool] = False
    patient_info: Optional[Dict[str, str]] = None
    documents_by_type: Optional[Dict[str, Any]] = None
    # Optional preloaded grouped rules from frontend
    rules_by_document_type: Optional[Dict[str, List[Dict[str, Any]]]] = None
    # Optional LLM overrides for experimentation
    model: Optional[str] = None
    provider: Optional[str] = None
    # Persistence control (default on)
    persist: Optional[bool] = True
    # Prompt optimization mode (default: plan_a)
    prompt_mode: Optional[str] = "plan_a"
    # ── 质控引擎高级配置（前端高级设置面板） ──
    # 每批发给 LLM 的最大规则数（分段模式）
    max_rules_per_batch: Optional[int] = None
    # LLM 最大并发调用数（分段模式）
    max_concurrency: Optional[int] = None
    # LLM 温度参数
    temperature: Optional[float] = None
    # LLM 最大输出 token 数
    max_tokens: Optional[int] = None


class SichuanBatchDocument(BaseModel):
    document_id: str
    document_content: str
    document_type: Optional[str] = "病程记录"


class SichuanBatchRequest(BaseModel):
    documents: List[SichuanBatchDocument]


class SichuanBundleEvaluateRequest(BaseModel):
    scene: Optional[str] = None
    institute_id: Optional[str] = None
    patient_id: Optional[str] = None
    visit_id: Optional[str] = None
    bundle_input: Optional[Dict[str, Any]] = None
    rule_ids: Optional[List[str]] = None
    model: Optional[str] = None
    schema: Optional[str] = "public"


class SichuanRuleVisitEvaluateRequest(BaseModel):
    rule_id: str
    institute_id: str
    patient_id: str
    visit_id: str
    source_schema: Optional[str] = None
    bundle_schema: Optional[str] = "public"
    force_refresh_bundle: Optional[bool] = False
    model: Optional[str] = None


class SichuanWorkspaceBatchJobCreateRequest(BaseModel):
    rule_ids: Optional[List[str]] = None
    rule_set_key: Optional[str] = None
    execution_strategy: Optional[str] = None
    quality_profile: Optional[str] = None
    bucket_strategy: Optional[str] = None
    batch_output_mode: Optional[str] = None
    enable_selective_refine: Optional[bool] = None
    refine_confidence_threshold: Optional[float] = None
    max_refine_candidates: Optional[int] = None
    scope: str = "final"
    department: Optional[str] = None
    doctor: Optional[str] = None
    date_field: str = "discharge"
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    keyword: Optional[str] = None
    record_ids: Optional[List[str]] = None
    run_mode: Optional[str] = None


class SaveQCResultRequest(BaseModel):
    mode: str
    document_type: str
    rule_ids: List[str]
    medical_text: Optional[str] = None  # 原始病历文本
    medical_text_length: int
    stats: Dict[str, Any]
    performance: Dict[str, Any]
    results: Optional[List[Dict[str, Any]]] = None
    payload: Optional[Dict[str, Any]] = None
    document_id: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    model: Optional[str] = None  # 使用的模型名称


def _grade_from_rate(rate: float) -> str:
    return "A" if rate >= 90 else "B" if rate >= 75 else "C"


def _current_user_id(current_user: Dict[str, Any]) -> str:
    return (
        str(current_user.get("id") or current_user.get("user_id") or current_user.get("username") or "")
        .strip()
        or "anonymous"
    )


def _is_workspace_batch_job(job: Optional[Dict[str, Any]]) -> bool:
    if not isinstance(job, dict):
        return False
    return is_workspace_batch_draft_id(job.get("draft_id"))


def _compact_workspace_summary(summary: Dict[str, Any], rule_results: List[Dict[str, Any]]) -> Dict[str, Any]:
    compact_summary = dict(summary)
    issue_summaries: List[Dict[str, Any]] = []
    for rule_result in rule_results:
        if not isinstance(rule_result, dict):
            continue
        for item in list(rule_result.get("items") or []):
            if not isinstance(item, dict):
                continue
            status = str(item.get("status") or item.get("result_status") or "").strip().lower()
            if status not in {
                "non_compliant",
                "ai_suggested_non_compliant",
                "data_gap",
                "uncertain",
                "not_executed",
                "technical_error",
            }:
                continue
            rule_id = str(item.get("qc_point_id") or item.get("rule_code") or item.get("rule_id") or "").strip()
            conclusion = ""
            decision = item.get("decision") if isinstance(item.get("decision"), dict) else {}
            if isinstance(decision, dict):
                conclusion = str(decision.get("conclusion") or "").strip()
            if not conclusion:
                conclusion = str(item.get("findings") or item.get("rule_name") or "").strip()
            issue_summaries.append(
                {
                    "rule_id": rule_id,
                    "status": status,
                    "text": conclusion[:80],
                }
            )
            if len(issue_summaries) >= 6:
                break
        if len(issue_summaries) >= 6:
            break
    if issue_summaries:
        compact_summary["history_issue_summaries"] = issue_summaries
    compact_summary.pop("rule_results", None)
    review_report = compact_summary.get("review_report")
    if isinstance(review_report, dict):
        compact_review = dict(review_report)
        compact_review.pop("findings", None)
        compact_summary["review_report"] = compact_review
    return compact_summary


def _workspace_batch_response_item(job: Dict[str, Any], *, compact: bool = False) -> Dict[str, Any]:
    filters = job.get("filters") if isinstance(job.get("filters"), dict) else {}
    summary = job.get("summary") if isinstance(job.get("summary"), dict) else {}
    rule_set_candidates = {
        str(filters.get("rule_set_key") or "").strip(),
        str(filters.get("rule_set_id") or "").strip(),
        str(summary.get("rule_set_key") or "").strip(),
        str(summary.get("rule_set_id") or "").strip(),
        str(job.get("rule_set_key") or "").strip(),
        str(job.get("rule_set_id") or "").strip(),
        str(job.get("rule_code") or "").strip(),
    }
    if LUXIAN_0609_RULE_SET_KEY in rule_set_candidates:
        safe_job = project_customer_safe_batch_job(
            job,
            hmac_key=customer_safe_projection_key(),
        )
        if compact:
            safe_job = dict(safe_job)
            safe_job["items"] = []
            safe_job["failed_records"] = []
            safe_job["rule_results"] = []
            safe_job["children"] = []
            safe_job["child_jobs"] = []
            safe_summary = dict(safe_job.get("summary") or {})
            safe_review = safe_summary.get("review_report")
            if isinstance(safe_review, dict):
                safe_review = dict(safe_review)
                safe_review.pop("findings", None)
                safe_summary["review_report"] = safe_review
            safe_job["summary"] = safe_summary
        return safe_job
    selected_rule_ids = list(filters.get("selected_rule_ids") or [])
    rule_ids = list(filters.get("rule_ids") or [])
    response_job = dict(job)
    if compact:
        rule_results = list(response_job.get("rule_results") or [])
        response_job["summary"] = _compact_workspace_summary(summary, rule_results)
        response_job["items"] = []
        response_job["failed_records"] = []
        response_job["rule_results"] = []
        response_job["children"] = []
        response_job["child_jobs"] = []
    return {
        **response_job,
        "execution_mode": "batch",
        "rule_count": int(summary.get("rule_count") or filters.get("rule_count") or job.get("rule_count") or 0),
        "customer_rule_count": int(filters.get("customer_rule_count") or job.get("customer_rule_count") or 0),
        "execution_rule_count": int(filters.get("execution_rule_count") or job.get("execution_rule_count") or 0),
        "draft_ids": selected_rule_ids or rule_ids,
        "rule_set_key": str(filters.get("rule_set_key") or ""),
        "rule_set_name": str(filters.get("rule_set_name") or ""),
        "rule_set_version": str(filters.get("rule_set_version") or ""),
        "execution_strategy": str((summary.get("execution_strategy") or filters.get("execution_strategy")) or ""),
        "quality_profile": str((summary.get("quality_profile") or filters.get("quality_profile")) or ""),
        "bucket_strategy": str((summary.get("bucket_strategy") or filters.get("bucket_strategy")) or ""),
        "batch_output_mode": str((summary.get("batch_output_mode") or filters.get("batch_output_mode")) or ""),
        "max_refine_candidates": int((summary.get("max_refine_candidates") or filters.get("max_refine_candidates") or 0) or 0),
        "refine_summary": summary.get("refine_summary"),
    }


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


def _normalize_scope(scope: Optional[str]) -> str:
    value = str(scope or "").strip().lower()
    if value not in {"all", "running", "final"}:
        return "all"
    return value


def _normalize_date_field(date_field: Optional[str]) -> str:
    value = str(date_field or "").strip().lower()
    if value not in {"admission", "discharge"}:
        return "admission"
    return value


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
    if normalized_rule_id != "LX0609-016":
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


def _snippet_near(text: str, markers: tuple[str, ...], *, limit: int = 180) -> str:
    if not text:
        return ""
    for marker in markers:
        position = text.find(marker)
        if position < 0:
            continue
        start = max(0, position - 50)
        end = min(len(text), position + limit)
        return " ".join(text[start:end].split())
    return ""


def _consultation_evidence_items_for_batch(
    *,
    rule_id: str,
    eval_item: Dict[str, Any],
    record: Dict[str, Any],
) -> List[Dict[str, Any]]:
    normalized_rule_id = str(rule_id or eval_item.get("rule_id") or eval_item.get("rule_code") or "").strip().upper()
    if normalized_rule_id not in {"LX0609-020", "LX0609-021", "LX0609-022", "LX0609-023"}:
        existing = eval_item.get("evidence_items")
        return list(existing) if isinstance(existing, list) else []

    existing_items = [item for item in list(eval_item.get("evidence_items") or []) if isinstance(item, dict)]

    def _existing_quote(*roles: str, require_consultation_context: bool = False) -> str:
        execution_context_markers = ("遵会诊", "已遵会诊", "会诊意见", "按会诊", "采纳会诊", "执行会诊")
        for item in existing_items:
            role = str(item.get("evidence_role") or "")
            if role not in roles:
                continue
            quote = " ".join(str(item.get("quote") or "").split())
            if require_consultation_context and not any(marker in quote for marker in execution_context_markers):
                continue
            if quote:
                return quote
        return ""

    medical_text = str(record.get("medical_text") or "")
    request_quote = _snippet_near(
        medical_text,
        ("会诊申请", "申请会诊", "请会诊", "申请目的", "会诊目的", "会诊记录"),
    ) or _existing_quote("consultation_request")
    opinion_quote = _snippet_near(
        medical_text,
        ("会诊意见", "处理意见", "会诊后指出", "考虑既往感染", "继续保肝"),
    ) or _existing_quote("consultation_opinion") or str(eval_item.get("evidence") or "")[:180]
    execution_quote = _snippet_near(
        medical_text,
        ("遵会诊", "已遵会诊", "会诊意见执行", "采纳会诊", "按会诊"),
    ) or _existing_quote("consultation_execution_record", require_consultation_context=True)
    if execution_quote and not any(marker in execution_quote for marker in ("遵会诊", "已遵会诊", "会诊意见", "采纳会诊", "按会诊")):
        execution_quote = ""

    items: List[Dict[str, Any]] = []
    if request_quote:
        items.append(
            {
                "evidence_id": "CONSULT-REQUEST",
                "source_table": "consultation_record",
                "source_document_type": "会诊申请/会诊记录",
                "source_document_name": "会诊申请/会诊记录",
                "source_document_id": "",
                "record_time": "",
                "field_path": "会诊申请/目的",
                "quote": request_quote,
                "normalized_value": "",
                "evidence_role": "consultation_request",
            }
        )
    if opinion_quote:
        items.append(
            {
                "evidence_id": "CONSULT-OPINION",
                "source_table": "consultation_record",
                "source_document_type": "会诊记录",
                "source_document_name": "会诊记录",
                "source_document_id": "",
                "record_time": "",
                "field_path": "会诊意见",
                "quote": " ".join(opinion_quote.split())[:260],
                "normalized_value": "",
                "evidence_role": "consultation_opinion",
            }
        )
    items.append(
        {
            "evidence_id": "CONSULT-EXECUTION",
            "source_table": "daily_course_record",
            "source_document_type": "后续病程记录",
            "source_document_name": "后续病程记录",
            "source_document_id": "",
            "record_time": "",
            "field_path": "会诊意见执行情况",
            "quote": execution_quote or "未检索到与会诊意见对应的后续病程执行记录。",
            "normalized_value": "",
            "evidence_role": "consultation_execution_record" if execution_quote else "consultation_execution_gap",
        }
    )
    return items


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
    total_unattributed_tokens = 0
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
        total_unattributed_tokens += unattributed_tokens
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
        "first_result_latency_seconds": round(max(0.0, float(first_result_latency or 0.0)), 4),
        "llm_call_count": total_llm_calls,
        "llm_call_count_basis": "result_participation_count",
        "actual_llm_pack_call_count": int(actual_llm_pack_call_count or 0),
        "program_call_count": total_program_calls,
        "retry_count": total_retry_count,
        "provider_error_count": total_provider_errors,
        "timeout_count": total_timeouts,
        "rate_limit_count": total_rate_limits,
        "pack_retry_attempts": total_pack_retries,
        "tokens_total": total_tokens,
        "prompt_tokens": total_prompt_tokens,
        "completion_tokens": total_completion_tokens,
        "unattributed_tokens": total_unattributed_tokens,
        "token_breakdown_complete": total_unattributed_tokens == 0,
        "context_tokens_estimate": total_context_tokens,
        "rules": rules,
        "slow_rules": rules[:12],
        "slow_results": slow_results,
        "results": result_profiles,
    }
    if input_profile_summary:
        batch_profile["input_profile"] = input_profile_summary
    return batch_profile


def _build_debug_snapshot(
    job: Dict[str, Any],
    *,
    rule_job_id: Optional[str] = None,
    item_limit: int = 30,
) -> Dict[str, Any]:
    rules = list(job.get("rule_results") or [])
    if rule_job_id:
        rules = [item for item in rules if str(item.get("id") or "") == str(rule_job_id)]
    current_rule = (
        next((item for item in rules if str(item.get("status") or "").lower() == "running"), None)
        or (rules[0] if rules else None)
    )
    all_items = list(job.get("items") or [])
    all_failed = list(job.get("failed_records") or [])
    if rule_job_id:
        all_items = [item for item in all_items if str(item.get("rule_job_id") or "") == str(rule_job_id)]
        all_failed = [item for item in all_failed if str(item.get("rule_job_id") or "") == str(rule_job_id)]

    return {
        "job_id": job.get("id"),
        "status": job.get("status"),
        "scope": job.get("scope"),
        "execution_mode": job.get("execution_mode") or "batch",
        "rule_count": int((job.get("summary") or {}).get("rule_count") or len(job.get("rule_results") or [])),
        "filtered_rule_count": len(rules),
        "summary": job.get("summary") or {},
        "current_rule": {
            "rule_job_id": current_rule.get("id"),
            "rule_code": current_rule.get("rule_code"),
            "rule_name": current_rule.get("rule_name"),
            "progress": current_rule.get("progress") or {},
        } if current_rule else None,
        "rules": [
            {
                "rule_job_id": item.get("id"),
                "rule_code": item.get("rule_code"),
                "rule_name": item.get("rule_name"),
                "status": item.get("status"),
                "progress": item.get("progress") or {},
                "debug": item.get("debug") or {},
                "total_records": item.get("total_records"),
                "success_count": item.get("success_count"),
                "failed_count": item.get("failed_count"),
                "issue_records": item.get("issue_records"),
                "compliant_records": item.get("compliant_records"),
                "total_tokens": item.get("total_tokens"),
                "total_processing_time": item.get("total_processing_time"),
                "error_message": item.get("error_message"),
                "updated_at": item.get("updated_at"),
            }
            for item in rules
        ],
        "recent_items": all_items[:max(1, int(item_limit or 30))],
        "recent_failed_records": all_failed[:max(1, int(item_limit or 30))],
        "updated_at": (job.get("summary") or {}).get("updated_at") or job.get("updated_at"),
    }


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


def _extract_user_roles(current_user: Optional[Dict[str, Any]]) -> set[str]:
    if not current_user:
        return set()
    roles = current_user.get("roles")
    normalized: set[str] = set()
    if isinstance(roles, list):
        normalized.update(str(role).strip().lower() for role in roles if str(role).strip())
    role = str(current_user.get("role") or "").strip().lower()
    if role:
        normalized.add(role)
    return normalized


def _can_view_result_trace(current_user: Optional[Dict[str, Any]]) -> bool:
    return bool(_extract_user_roles(current_user).intersection({"admin", "sync_admin", "super_admin"}))


def _sanitize_trace_value(value: Any, removed_keys: set[str], *, max_text: int = 1200) -> Any:
    if isinstance(value, dict):
        sanitized: Dict[str, Any] = {}
        for key, item in value.items():
            normalized_key = str(key or "").strip().lower()
            if normalized_key in _TRACE_SENSITIVE_KEYS:
                removed_keys.add(str(key))
                continue
            sanitized[str(key)] = _sanitize_trace_value(item, removed_keys, max_text=max_text)
        return sanitized
    if isinstance(value, list):
        return [_sanitize_trace_value(item, removed_keys, max_text=max_text) for item in value[:50]]
    if isinstance(value, str):
        text = value.strip()
        if len(text) > max_text:
            return f"{text[:max_text]}...（已截断）"
        return text
    return value


def _trace_pick(item: Dict[str, Any], keys: List[str]) -> Dict[str, Any]:
    return {key: item.get(key) for key in keys if key in item and item.get(key) is not None}


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
    removed_keys: set[str] = set()
    return _sanitize_trace_value(trace, removed_keys)


def _flatten_batch_job_items(job: Dict[str, Any]) -> List[Dict[str, Any]]:
    items = [item for item in list(job.get("items") or []) if isinstance(item, dict)]
    for child_key in ("children", "child_jobs"):
        child_jobs = job.get(child_key)
        if not isinstance(child_jobs, list):
            continue
        for child in child_jobs:
            if isinstance(child, dict):
                items.extend(_flatten_batch_job_items(child))
    return items


def _matches_trace_item(
    item: Dict[str, Any],
    *,
    record_id: Optional[str] = None,
    visit_id: Optional[str] = None,
    rule_id: Optional[str] = None,
) -> bool:
    if record_id and str(item.get("record_id") or "").strip() != str(record_id).strip():
        return False
    if visit_id and str(item.get("visit_id") or "").strip() != str(visit_id).strip():
        return False
    if rule_id:
        normalized_rule_id = str(rule_id).strip().upper()
        item_rule_ids = {
            str(item.get("rule_id") or "").strip().upper(),
            str(item.get("rule_code") or "").strip().upper(),
            str(item.get("qc_point_id") or "").strip().upper(),
        }
        if normalized_rule_id not in item_rule_ids:
            return False
    return True


def _find_result_trace_item(
    job: Dict[str, Any],
    *,
    record_id: Optional[str] = None,
    visit_id: Optional[str] = None,
    rule_id: Optional[str] = None,
    item_index: Optional[int] = None,
) -> Optional[Dict[str, Any]]:
    items = _flatten_batch_job_items(job)
    if item_index is not None:
        try:
            return items[int(item_index)]
        except (IndexError, ValueError):
            return None
    return next(
        (
            item
            for item in items
            if _matches_trace_item(item, record_id=record_id, visit_id=visit_id, rule_id=rule_id)
        ),
        None,
    )


def _build_result_trace_snapshot(job: Dict[str, Any], item: Dict[str, Any]) -> Dict[str, Any]:
    removed_keys: set[str] = set()
    audit = item.get("audit") if isinstance(item.get("audit"), dict) else {}
    decision = item.get("decision") if isinstance(item.get("decision"), dict) else {}
    trigger = item.get("trigger") if isinstance(item.get("trigger"), dict) else {}
    dependencies = item.get("dependencies") if isinstance(item.get("dependencies"), dict) else {}
    metadata = item.get("metadata") if isinstance(item.get("metadata"), dict) else {}
    review = item.get("review") if isinstance(item.get("review"), dict) else {}
    diagnostic_trace = _result_diagnostic_trace(
        item,
        metadata,
        evidence_items=item.get("evidence_items") if isinstance(item.get("evidence_items"), list) else [],
        status=str(item.get("status") or ""),
    )

    source_execution_results = (
        audit.get("source_execution_results")
        or audit.get("mapped_results")
        or audit.get("bottom_results")
        or decision.get("source_execution_results")
        or decision.get("mapped_results")
        or diagnostic_trace.get("source_execution_results")
        or []
    )
    if not isinstance(source_execution_results, list):
        source_execution_results = [source_execution_results]
    if not trigger and isinstance(diagnostic_trace.get("trigger_decision"), dict):
        trigger = dict(diagnostic_trace.get("trigger_decision") or {})

    aggregation_trace = {
        "final_status": item.get("status"),
        "display_status": item.get("display_status"),
        "result_status": item.get("result_status"),
        "final_decision_source": item.get("final_decision_source") or metadata.get("final_decision_source"),
        "postprocess_label": item.get("postprocess_label"),
        "postprocess_reason": item.get("postprocess_reason") or diagnostic_trace.get("postprocess_reason"),
        "aggregation_reason": item.get("aggregation_reason") or diagnostic_trace.get("aggregation_reason"),
        "first_pass_status": item.get("first_pass_status"),
        "adjudicated_display_status": item.get("adjudicated_display_status"),
        "adjudicator_reason": item.get("adjudicator_reason"),
        "customer_display_guard": (
            metadata.get("customer_display_guard")
            or audit.get("customer_display_guard")
            or decision.get("customer_display_guard")
        ),
        "rule_requirement_match": item.get("rule_requirement_match"),
        "source_execution_count": len(source_execution_results),
    }

    final_result = _trace_pick(
        item,
        [
            "rule_id",
            "rule_code",
            "qc_point_id",
            "rule_name",
            "record_id",
            "visit_id",
            "patient_name",
            "department",
            "status",
            "display_status",
            "result_status",
            "is_compliant",
            "defect_level",
            "findings",
            "evidence",
            "suggestion",
            "target_document_type",
            "document_type",
            "rule_family",
            "trace_id",
            "model_version",
            "executor_type",
            "source_rule_id",
            "source_status",
            "source_conclusion",
            "source_evidence",
            "trigger_decision",
            "aggregation_reason",
            "postprocess_reason",
        ],
    )
    performance_profile = item.get("performance_profile")
    if not isinstance(performance_profile, dict):
        performance_profile = metadata.get("performance_profile") if isinstance(metadata.get("performance_profile"), dict) else {}
    if not performance_profile:
        performance_profile = _build_result_performance_profile(item)
    return {
        "job_id": job.get("id"),
        "job_status": job.get("status"),
        "rule_set_key": job.get("rule_set_key"),
        "rule_set_name": job.get("rule_set_name"),
        "final_result": _sanitize_trace_value(final_result, removed_keys),
        "aggregation_trace": _sanitize_trace_value(aggregation_trace, removed_keys),
        "trigger": _sanitize_trace_value(trigger, removed_keys),
        "dependencies": _sanitize_trace_value(dependencies, removed_keys),
        "decision": _sanitize_trace_value(decision, removed_keys),
        "audit": _sanitize_trace_value(audit, removed_keys),
        "review": _sanitize_trace_value(review, removed_keys),
        "evidence_items": _sanitize_trace_value(item.get("evidence_items") or [], removed_keys),
        "source_execution_results": _sanitize_trace_value(source_execution_results, removed_keys),
        "diagnostic_trace": _sanitize_trace_value(diagnostic_trace, removed_keys),
        "performance_profile": _sanitize_trace_value(performance_profile, removed_keys),
        "safety": {
            "sensitive_fields_removed": sorted(removed_keys),
            "raw_output_returned": False,
            "note": "诊断追踪仅返回聚合链路和脱敏后的证据摘要，不返回模型原始输出或完整病历正文。",
        },
    }


@router.post("/evaluate-fast")
async def evaluate_fast(
    request: Request,
    req: SichuanEvaluateRequest,
    qc_service: SichuanQCService = Depends(get_qc_service)
):
    """
    快速质控模式：一次 API 调用评估所有规则

    与 /evaluate 的区别：
    - /evaluate: 逐条规则调用 LLM（串行模式）
    - /evaluate-fast: 一次调用评估所有规则（快速模式）

    支持的 prompt_mode 参数：
    - current: 当前模式（只使用 rule_id + name + description）
    - plan_a: 方案A - 精简版（提取【检查要点】）
    - plan_b: 方案B - 完整版（使用完整 custom_prompt）
    - plan_c: 方案C - 平衡版（提取【检查要点】+【判定逻辑】）
    """
    try:
        # Allow runtime override of model
        if req.model:
            qc_service.client.model = req.model

        # 调用快速质控方法（传递 prompt_mode）
        result = await qc_service.evaluate_document_fast(
            document_id=req.document_id,
            content=req.document_content,
            document_type=req.document_type or "病程记录",
            rule_ids=req.rule_ids,
            prompt_mode=req.prompt_mode or "plan_a"
        )

        return result
    except Exception as e:
        raise HTTPException(status_code=StatusCode.INTERNAL_SERVER_ERROR, detail=f"快速质控评估失败: {e}")


@router.post("/evaluate")
async def evaluate(
    request: Request,
    req: SichuanEvaluateRequest,
    qc_service: SichuanQCService = Depends(get_qc_service)
):
    try:
        # Allow runtime override of model (for A/B testing different LLMs)
        if req.model:
            qc_service.client.model = req.model
        _enforce_sc_source_guard(
            qc_service,
            context="evaluate",
            rule_ids=req.rule_ids,
            block_batch=False,
        )
        # running/final bundle 直入旧规则链入口（不依赖独立 runtime）
        if isinstance(req.bundle_input, dict) and req.bundle_input:
            bundle_result = await evaluate_running_final_bundle(
                qc_service=qc_service,
                bundle_input=req.bundle_input,
                rule_ids=req.rule_ids,
            )
            if req.persist:
                _persist_evaluation_to_db(req.document_id, bundle_result)
            return bundle_result

        if not str(req.document_content or "").strip():
            raise HTTPException(status_code=422, detail="document_content 不能为空（bundle_input 模式除外）")

        if req.use_multi_document_mode:
            # Prefer frontend-provided grouped rules; fallback to fetching from Supabase
            rules_by_document_type = req.rules_by_document_type
            if rules_by_document_type is None and req.document_types:
                try:
                    # Get rules grouped by document type from Supabase
                    supabase = get_supabase()
                    if supabase is not None:
                        async def _exec(q):
                            try:
                                exec_async = getattr(q, "execute_async", None)
                                if callable(exec_async):
                                    return await exec_async()
                            except Exception:
                                pass
                            return q.execute()

                        resp = await _exec(supabase.table("qc_rules").select("*").eq("is_active", True).limit(1000))
                        all_rules = resp.data or []

                        # Group rules by applicable document types
                        rules_by_document_type = {}
                        for rule in all_rules:
                            # Prefer top-level field, then fallback to nested check_logic.applicable_documents
                            applicable_docs = (
                                rule.get("applicable_documents")
                                or (rule.get("check_logic") or {}).get("applicable_documents")
                                or []
                            )
                            if isinstance(applicable_docs, str):
                                applicable_docs = [d.strip() for d in applicable_docs.split(",") if d.strip()]
                            try:
                                normalized_docs = [str(d).strip() for d in (applicable_docs or [])]
                            except Exception:
                                normalized_docs = []

                            for doc_type in (req.document_types or []):
                                if doc_type and any(doc_type.lower() == d.lower() for d in normalized_docs):
                                    if doc_type not in rules_by_document_type:
                                        rules_by_document_type[doc_type] = []
                                    rules_by_document_type[doc_type].append(rule)
                except Exception as e:
                    print(f"Warning: Failed to fetch grouped rules: {e}")
                    rules_by_document_type = None
            
            md = await qc_service.evaluate_multi_document(
                document_id=req.document_id,
                document_content=req.document_content,
                document_types=req.document_types,
                preclassified_documents=req.documents_by_type,
                rules_by_document_type=rules_by_document_type,
            )

            # Build legacy-compatible response
            response = {
                "document_id": req.document_id,
                "evaluation_summary": {
                    "total_rules": md["overall_summary"]["total_rules"],
                    "compliant_rules": md["overall_summary"]["compliant_rules"],
                    "not_applicable": md["overall_summary"].get("not_applicable", 0),
                    "issues_found": md["overall_summary"].get("issues_found", md["overall_summary"]["critical_violations"]),
                    "compliance_rate": md["overall_summary"]["compliance_rate"],
                    "overall_grade": md["overall_summary"]["overall_grade"],
                    "critical_violations": md["overall_summary"]["critical_violations"],
                    "document_breakdown": md["overall_summary"]["document_breakdown"],
                },
                "performance_metrics": {
                    "processing_time": md["total_processing_time"],
                    "token_usage": md["total_token_usage"],
                    "estimated_cost": md["total_token_usage"] / 1000 * 0.002,
                },
                "evaluation_results": [
                    item
                    for d in md["document_results"].values()
                    for item in d.get("evaluation_results", [])
                ],
                "optimization_metrics": md["optimization_metrics"],
                "document_results": md["document_results"],
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "status": "success",
                "mode": "multi_document",
            }
            # Persist (best-effort)
            if req.persist:
                _persist_evaluation_to_db(req.document_id, response)
            return response
        else:
            # ── P1 收口：单文书主路径统一走 orchestrator（保持响应壳兼容） ──
            if req.temperature is not None:
                qc_service.client.temperature = req.temperature
            if req.max_tokens is not None:
                qc_service.client.max_tokens = req.max_tokens

            result = await qc_service.evaluate_document(
                document_id=req.document_id,
                content=req.document_content,
                document_type=req.document_type or "病程记录",
                rule_ids=req.rule_ids,
            )

            summary = result.get("evaluation_summary", {}) or {}
            token_usage = int(((result.get("token_usage") or {}).get("total_tokens")) or 0)
            processing_time = float(result.get("api_time") or 0.0)
            compliance_rate = float(summary.get("compliance_rate", 100.0) or 100.0)

            response = {
                "document_id": req.document_id,
                "evaluation_summary": {
                    "total_rules": summary.get("total_rules", 0),
                    "compliant_rules": summary.get("compliant_rules", 0),
                    "not_applicable": summary.get("not_applicable", 0),
                    "issues_found": summary.get("issues_found", 0),
                    "compliance_rate": round(compliance_rate, 2),
                    "overall_grade": _grade_from_rate(compliance_rate),
                    "critical_violations": summary.get("issues_found", 0),
                    "model": summary.get("model", qc_service.client.model),
                    "executor_breakdown": summary.get("executor_breakdown") or {},
                    "cache_breakdown": summary.get("cache_breakdown") or {},
                    "pack_metrics": summary.get("pack_metrics") or {},
                },
                "performance_metrics": {
                    "processing_time": processing_time,
                    "token_usage": token_usage,
                    "estimated_cost": token_usage / 1000 * 0.002,
                    "llm_calls": int((summary.get("executor_breakdown") or {}).get("llm", 0) or 0),
                },
                "evaluation_results": result.get("evaluation_results", []),
                "sections_summary": [],
                "optimization_metrics": {
                    "token_savings_rate": 0.0,
                    "estimated_original_tokens": token_usage,
                    "actual_tokens_saved": 0,
                    "cost_savings": 0.0,
                },
                "trace": result.get("trace") or [],
                "executor_breakdown": result.get("executor_breakdown") or {},
                "cache_breakdown": result.get("cache_breakdown") or {},
                "pack_metrics": result.get("pack_metrics") or {},
                "llm_info": {
                    "model": qc_service.client.model,
                    "api_endpoint": qc_service.client.api_endpoint,
                },
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "status": "success",
                "mode": "orchestrated",
            }
            if req.persist:
                _persist_evaluation_to_db(req.document_id, response)
            return response
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=StatusCode.INTERNAL_SERVER_ERROR, detail=f"四川省质控评估失败: {e}")


@router.post("/evaluate-bundle")
async def evaluate_bundle(
    request: Request,
    req: SichuanBundleEvaluateRequest,
    qc_service: SichuanQCService = Depends(get_qc_service)
):
    try:
        if req.model:
            qc_service.client.model = req.model
        _enforce_sc_source_guard(
            qc_service,
            context="evaluate_bundle",
            rule_ids=req.rule_ids,
            block_batch=False,
        )
        result = await evaluate_running_final_bundle(
            qc_service=qc_service,
            scene=req.scene,
            institute_id=req.institute_id,
            patient_id=req.patient_id,
            visit_id=req.visit_id,
            bundle_input=req.bundle_input,
            rule_ids=list(req.rule_ids or []),
            schema=str(req.schema or "public").strip() or "public",
        )
        return success_response(
            data=result,
            message="bundle 质控评估完成",
            trace_id=get_trace_id(request),
        )
    except HTTPException:
        raise
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=StatusCode.INTERNAL_SERVER_ERROR, detail=f"bundle 质控评估失败: {exc}")


@router.post("/evaluate-rule-for-visit")
async def evaluate_rule_for_visit(
    request: Request,
    req: SichuanRuleVisitEvaluateRequest,
    qc_service: SichuanQCService = Depends(get_qc_service),
):
    try:
        if req.model:
            qc_service.client.model = req.model
        _enforce_sc_source_guard(
            qc_service,
            context="evaluate_rule_for_visit",
            rule_ids=[req.rule_id],
            block_batch=False,
        )
        result = await qc_service.evaluate_rule_for_visit(
            rule_id=req.rule_id,
            institute_id=req.institute_id,
            patient_id=req.patient_id,
            visit_id=req.visit_id,
            source_schema=req.source_schema,
            bundle_schema=str(req.bundle_schema or "public").strip() or "public",
            force_refresh_bundle=bool(req.force_refresh_bundle),
        )
        return success_response(
            data=result,
            message="规则级 visit 质控评估完成",
            trace_id=get_trace_id(request),
        )
    except HTTPException:
        raise
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=StatusCode.INTERNAL_SERVER_ERROR, detail=f"规则级 visit 质控失败: {exc}")


@router.post("/evaluate/batch")
async def evaluate_batch(
    request: Request,
    req: SichuanBatchRequest,
    qc_service: SichuanQCService = Depends(get_qc_service)
):
    try:
        _enforce_sc_source_guard(
            qc_service,
            context="evaluate_batch",
            rule_ids=None,
            block_batch=False,
        )
        payloads = [
            {
                "document_id": d.document_id,
                "content": d.document_content,
                "document_type": d.document_type or "病程记录",
            }
            for d in req.documents
        ]
        results = await qc_service.evaluate_batch(payloads)

        total_documents = len(results)
        successful_evaluations = len([r for r in results])
        total_tokens = sum(int(r.get("token_usage", {}).get("total_tokens", 0)) for r in results)
        total_processing_time = sum(float(r.get("api_time", 0.0)) for r in results)

        total_rules_evaluated = 0
        total_compliant_rules = 0
        eval_summaries = []

        for r in results:
            doc_total_rules = int(r.get("total_rules", 0))
            total_rules_evaluated += doc_total_rules
            rate = float(r.get("evaluation_summary", {}).get("compliance_rate", 0.0))
            compliant = int(doc_total_rules * rate / 100.0) if doc_total_rules else 0
            total_compliant_rules += compliant
            eval_summaries.append(
                {
                    "document_id": r.get("document_id", "unknown"),
                    "total_rules": doc_total_rules,
                    "compliant_rules": compliant,
                    "compliance_rate": rate,
                    "overall_grade": _grade_from_rate(rate),
                    "processing_time": float(r.get("api_time", 0.0)),
                    "token_usage": int(r.get("token_usage", {}).get("total_tokens", 0)),
                    "critical_violations": int(r.get("evaluation_summary", {}).get("issues_found", 0)),
                }
            )

        response = {
            "batch_summary": {
                "total_documents": total_documents,
                "successful_evaluations": successful_evaluations,
                "success_rate": (successful_evaluations / total_documents * 100) if total_documents > 0 else 0,
                "total_rules_evaluated": total_rules_evaluated,
                "total_compliant_rules": total_compliant_rules,
                "overall_compliance_rate": (total_compliant_rules / total_rules_evaluated * 100) if total_rules_evaluated > 0 else 0,
            },
            "performance_metrics": {
                "total_processing_time": total_processing_time,
                "avg_processing_time": total_processing_time / successful_evaluations if successful_evaluations > 0 else 0,
                "total_token_usage": total_tokens,
                "avg_token_usage": total_tokens / successful_evaluations if successful_evaluations > 0 else 0,
                "total_estimated_cost": total_tokens / 1000 * 0.002,
            },
            "optimization_metrics": {
                "token_savings_rate": 0.80,
                "estimated_original_tokens": total_tokens * 5,
                "actual_tokens_saved": total_tokens * 4,
                "total_cost_savings": total_tokens * 4 / 1000 * 0.002,
            },
            "evaluation_results": eval_summaries,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "status": "success",
        }
        return response
    except Exception as e:
        raise HTTPException(status_code=StatusCode.INTERNAL_SERVER_ERROR, detail=f"四川省批量质控评估失败: {e}")


def _sichuan_workspace_service() -> CustomQCWorkspaceService:
    return CustomQCWorkspaceService()


async def _run_sichuan_workspace_batch_job(job_id: str) -> None:
    job_wall_started = time.perf_counter()
    workspace = _sichuan_workspace_service()
    job = workspace.get_batch_job_for_processing(job_id=job_id)
    if not job:
        return
    if str(job.get("job_kind") or "").strip().lower() == "parent":
        logger.info("跳过泸县0609父任务执行，仅执行其规则族子任务: job_id=%s", job_id)
        return

    try:
        if not workspace.mark_batch_job_running(job_id=job_id):
            return
        qc_service = await get_qc_service()
        current = workspace.get_batch_job_for_processing(job_id=job_id) or job
        filters = dict(current.get("filters") or {})
        record_evaluation_snapshot_by_id = {
            str(item.get("record_id") or "").strip(): dict(item)
            for item in list(filters.get("record_evaluation_snapshot") or [])
            if isinstance(item, dict) and str(item.get("record_id") or "").strip()
        }
        requested_rule_ids = [
            str(item).strip().upper()
            for item in (filters.get("rule_ids") or [])
            if str(item).strip()
        ]
        gate_only_customer_rule_ids_for_validation = [
            str(item).strip()
            for item in (filters.get("gate_only_customer_rule_ids") or [])
            if str(item).strip()
        ]
        if not requested_rule_ids and not gate_only_customer_rule_ids_for_validation:
            raise ValueError("批量任务缺少 rule_ids")
        rule_set_key = str(filters.get("rule_set_key") or "").strip()
        rule_set_name = str(filters.get("rule_set_name") or "").strip()
        rule_set_version = str(filters.get("rule_set_version") or "").strip()
        validation_mode = str(filters.get("validation_mode") or "").strip().lower() or "sc"
        programmatic_rule_set = get_sample_programmatic_rule_set()
        is_programmatic_mode = (
            validation_mode == "programmatic" or rule_set_key == programmatic_rule_set.key
        )
        settings = resolve_mainline_rule_decision_settings(get_settings())
        native_requested_rule_ids = _ordered_luxian_0609_customer_rule_ids(
            requested_rule_ids
        )
        is_direct_native_selection = bool(
            rule_set_key == LUXIAN_0609_RULE_SET_KEY
            and requested_rule_ids
            and len(native_requested_rule_ids) == len(set(requested_rule_ids))
        )
        native_direct_enabled = bool(
            is_direct_native_selection
            and getattr(settings, "LUXIAN_0609_CUSTOMER_AGGREGATION_ENABLED", False)
        )
        compatibility_rule_ids = (
            _luxian_0609_compatibility_rule_ids(
                native_requested_rule_ids,
                settings=settings,
            )
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
        max_parallel_records = min(4, max(1, int(filters.get("max_parallel_records") or 2)))
        if compatibility_rule_ids:
            _enforce_sc_source_guard(
                qc_service,
                context=f"workspace_batch_job:{job_id}",
                rule_ids=list(compatibility_rule_ids),
                block_batch=True,
            )

        records = workspace.collect_records(
            scope=str(current.get("scope") or "all"),
            department=filters.get("department"),
            doctor=filters.get("doctor"),
            date_field=filters.get("date_field") or "admission",
            start_date=filters.get("start_date"),
            end_date=filters.get("end_date"),
            keyword=filters.get("keyword"),
            record_ids=current.get("record_ids") or None,
        )
        hydrated_records = workspace.hydrate_records_with_medical_text(records)
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
        executor_program = 0
        executor_llm = 0
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
        refine_summary_total: Dict[str, Any] = {
            "enabled": enable_selective_refine,
            "candidate_count": 0,
            "refined_rule_count": 0,
            "refine_failed_count": 0,
            "refine_reasons": {},
        }

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
        valid_rules = [
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
            for rule_id in list(filters.get("scoped_customer_rule_ids") or [])
            if str(rule_id or "").strip()
        }
        gate_only_customer_rule_ids = {
            str(rule_id or "").strip().upper()
            for rule_id in list(filters.get("gate_only_customer_rule_ids") or [])
            if str(rule_id or "").strip()
        }
        output_rule_states: Dict[str, Dict[str, Any]] = rule_states
        output_rule_ids: List[str] = list(valid_rule_ids)
        if use_luxian_customer_results:
            output_rule_states = {}
            output_rule_ids = []
            for wrapper in load_luxian_0609_rules():
                customer_rule_id = str(wrapper.get("rule_id") or wrapper.get("rule_code") or "").strip().upper()
                if not customer_rule_id:
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
                }
            total_rules = max(1, len(output_rule_ids))
        record_rule_map_raw = dict(filters.get("record_rule_map") or {})
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

        def _is_cancelled() -> bool:
            latest = workspace.get_batch_job_for_processing(job_id=job_id)
            if not latest:
                return True
            return str(latest.get("status") or "").strip().lower() == "canceled"

        def _raise_if_cancelled() -> None:
            raise_if_cancelled(_is_cancelled)

        def _record_ids_for_item_status(status: str) -> set[str]:
            normalized_status = str(status or "").strip().lower()
            return {
                str(item.get("record_id") or "").strip()
                for item in all_items
                if str(item.get("status") or "").strip().lower() == normalized_status
                and str(item.get("record_id") or "").strip()
            }

        def _build_progress_patch(processed_records_count: int) -> Dict[str, Any]:
            record_status_counts = _build_record_status_counts(
                total_records=processed_records_count,
                issue_record_ids=issue_record_ids,
                uncertain_record_ids=uncertain_record_ids,
                data_gap_record_ids=_record_ids_for_item_status("data_gap"),
                failed_record_ids=failed_record_ids,
                not_applicable_record_ids=_record_ids_for_item_status("not_applicable"),
            )
            result_status_counts = _build_item_status_counts(all_items)
            return {
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
                "executor_breakdown": {"program": executor_program, "llm": executor_llm},
                "cache_breakdown": {"hit": cache_hit, "miss": cache_miss},
            }

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
                    str(item.get("record_id") or "").strip()
                    for item in rule_failed
                    if str(item.get("record_id") or "").strip()
                }
                confirmed_record_ids = {
                    str(item.get("record_id") or "")
                    for item in rule_items
                    if _item_is_confirmed_defect(item)
                }
                uncertain_record_ids_for_rule = {
                    str(item.get("record_id") or "")
                    for item in rule_items
                    if _item_needs_review(item)
                }
                data_gap_record_ids_for_rule = {
                    str(item.get("record_id") or "")
                    for item in rule_items
                    if _item_data_quality_gap(item)
                }
                rejected_record_ids_for_rule = {
                    str(item.get("record_id") or "")
                    for item in rule_items
                    if _item_rejected_by_system(item)
                }
                not_applicable_record_ids_for_rule = {
                    str(item.get("record_id") or "")
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
                        - len(not_applicable_record_ids_for_rule),
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

        async def _evaluate_single_record(record: Dict[str, Any]) -> Dict[str, Any]:
            _raise_if_cancelled()
            record_id = str(record.get("record_id") or record.get("visit_id") or "").strip()
            visit_id = str(record.get("visit_id") or record_id).strip()
            institute_id = str(record.get("institute_id") or "").strip()
            patient_id = str(record.get("patient_id") or "").strip()
            query_scope = str(
                filters.get("query_scope") or current.get("scope") or "all"
            ).strip().lower()
            record_evaluation_snapshot = record_evaluation_snapshot_by_id.get(record_id)
            if record_evaluation_snapshot is not None:
                evaluation_horizon_policy = resolve_record_evaluation_horizon_policy(
                    record_evaluation_snapshot
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
                list(record_rule_map.get(visit_id) or record_rule_map.get(record_id) or [])
                or list(valid_rule_ids)
            )
            active_rules = [
                dict(rule_states[rule_id]["rule"])
                for rule_id in active_rule_ids
                if isinstance(rule_states[rule_id].get("rule"), dict)
            ]
            result_rule_ids = output_rule_ids if use_luxian_customer_results else active_rule_ids
            result_rule_states = output_rule_states if use_luxian_customer_results else rule_states
            items_by_rule: Dict[str, List[Dict[str, Any]]] = {rule_id: [] for rule_id in result_rule_ids}
            failed_by_rule: Dict[str, List[Dict[str, Any]]] = {rule_id: [] for rule_id in result_rule_ids}
            rule_stats: Dict[str, Dict[str, Any]] = {
                rule_id: {
                    "total_tokens": 0,
                    "total_processing_time": 0.0,
                    "executor_program": 0,
                    "executor_llm": 0,
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
                record_first_result_latency = 0.0
                record_first_result_source = ""
                record_pack_metrics: Dict[str, Any] = {}
                record_cot_summary: Dict[str, Any] = {}
                record_refine_summary: Dict[str, Any] = {}
                record_luxian_0609_input_profile: Dict[str, Any] = {}
                bundle_scene = ""
                bundle_payload: Optional[Dict[str, Any]] = None
                attempted_bundle_scenes: List[str] = []
                runtime_shadow_summary: Optional[Dict[str, Any]] = None

                async def _evaluate_rule_level_visit_bundle() -> bool:
                    nonlocal eval_items
                    nonlocal record_total_tokens
                    nonlocal record_total_prompt_tokens
                    nonlocal record_total_completion_tokens
                    nonlocal record_total_api_time
                    nonlocal record_first_result_latency
                    nonlocal record_first_result_source
                    nonlocal record_pack_metrics

                    if not (institute_id and patient_id and visit_id and active_rule_ids):
                        return False

                    aggregated_items: List[Dict[str, Any]] = []
                    aggregated_tokens = 0
                    aggregated_api_time = 0.0
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
                        per_rule_items = list(
                            single_result.get("evaluation_results")
                            or single_result.get("parsed_evaluation_results")
                            or []
                        )
                        if not per_rule_items:
                            raise ValueError(f"规则级 visit 评估未返回结果: {single_rule_id}")
                        aggregated_items.extend(per_rule_items)
                        token_usage = dict(single_result.get("token_usage") or {})
                        aggregated_tokens += int(token_usage.get("total_tokens") or 0)
                        aggregated_api_time += float(single_result.get("api_time") or 0.0)
                        if first_latency <= 0:
                            first_latency = float(single_result.get("api_time") or 0.0)
                            first_source = "rule_for_visit"

                    eval_items = aggregated_items
                    record_total_tokens = aggregated_tokens
                    record_total_prompt_tokens = 0
                    record_total_completion_tokens = 0
                    record_total_api_time = aggregated_api_time
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
                            evaluation_as_of_date=evaluation_as_of_date or None,
                            evaluation_horizon_policy=evaluation_horizon_policy,
                            cancellation_check=_is_cancelled,
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
                    record_total_api_time = float(result.get("api_time") or 0.0)
                    record_first_result_latency = float(result.get("first_result_latency") or 0.0)
                    record_first_result_source = str(result.get("first_result_source") or "")
                    record_pack_metrics = dict(result.get("pack_metrics") or {})
                    record_cot_summary = dict(result.get("cot_summary") or {})
                    record_refine_summary = dict(result.get("refine_summary") or {})
                    record_luxian_0609_input_profile = dict(result.get("luxian_0609_input_profile") or {})
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
                        record_total_api_time = float(single_result.get("api_time") or 0.0)
                        record_first_result_latency = float(single_result.get("first_result_latency") or 0.0)
                        record_first_result_source = str(single_result.get("first_result_source") or "")
                        record_pack_metrics = dict(single_result.get("pack_metrics") or {})
                        record_cot_summary = dict(single_result.get("cot_summary") or {})
                        record_refine_summary = dict(single_result.get("refine_summary") or {})
                        record_luxian_0609_input_profile = dict(
                            single_result.get("luxian_0609_input_profile") or {}
                        )
                    except Exception as bundle_exc:
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
                    record_total_api_time = float(result.get("api_time") or 0.0)
                    record_first_result_latency = float(result.get("first_result_latency") or 0.0)
                    record_first_result_source = str(result.get("first_result_source") or "")
                    record_pack_metrics = dict(result.get("pack_metrics") or {})
                    record_cot_summary = dict(result.get("cot_summary") or {})
                    record_refine_summary = dict(result.get("refine_summary") or {})
                    record_luxian_0609_input_profile = dict(result.get("luxian_0609_input_profile") or {})
                    eval_items = list(result.get("evaluation_results") or [])

                eval_map: Dict[str, Dict[str, Any]] = {}
                for eval_item in eval_items:
                    key = str(eval_item.get("rule_id") or eval_item.get("rule_code") or "").strip().upper()
                    if key and key not in eval_map:
                        eval_map[key] = dict(eval_item)

                local_total_tokens = 0
                local_total_processing_time = 0.0
                local_executor_program = 0
                local_executor_llm = 0
                local_cache_hit = 0
                local_cache_miss = 0
                has_issue = False
                has_uncertain = False
                record_issue_items: List[Dict[str, Any]] = []
                record_status_items: List[Dict[str, Any]] = []

                fallback_tokens_per_rule = int(record_total_tokens / max(1, len(result_rule_ids)))
                fallback_prompt_tokens_per_rule = int(record_total_prompt_tokens / max(1, len(result_rule_ids)))
                fallback_completion_tokens_per_rule = int(
                    record_total_completion_tokens / max(1, len(result_rule_ids))
                )
                fallback_api_per_rule = float(record_total_api_time / max(1, len(result_rule_ids)))

                for rule_id in result_rule_ids:
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
                        if not is_gate_only_missing:
                            failed_by_rule[rule_id].append(
                                {
                                    "rule_job_id": rule_job_id,
                                    "rule_id": rule_id,
                                    "rule_code": rule_code,
                                    "rule_name": rule_name,
                                    "record_id": record_id,
                                    "visit_id": str(record.get("visit_id") or ""),
                                    "patient_name": str(record.get("patient_name") or ""),
                                    "department": str(record.get("department") or ""),
                                    "error_phase": "result_missing",
                                    "error": "规则执行未返回结果",
                                }
                            )
                        if use_luxian_customer_results:
                            if is_gate_only_missing:
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

                    status = str(eval_item.get("status") or "").strip().lower()
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
                    evidence_items = _consultation_evidence_items_for_batch(
                        rule_id=normalized_rule_id,
                        eval_item=eval_item,
                        record=record,
                    )
                    metadata = dict(eval_item.get("metadata") or {})
                    metadata.setdefault("tokens_used", fallback_tokens_per_rule)
                    metadata.setdefault("prompt_tokens", fallback_prompt_tokens_per_rule)
                    metadata.setdefault("completion_tokens", fallback_completion_tokens_per_rule)
                    metadata.setdefault("input_tokens", fallback_prompt_tokens_per_rule)
                    metadata.setdefault("output_tokens", fallback_completion_tokens_per_rule)
                    metadata.setdefault("api_time", fallback_api_per_rule)
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
                    local_total_tokens += tokens_used
                    local_total_processing_time += api_time
                    rule_stats[rule_id]["total_tokens"] = int(rule_stats[rule_id]["total_tokens"] or 0) + tokens_used
                    rule_stats[rule_id]["total_processing_time"] = (
                        float(rule_stats[rule_id]["total_processing_time"] or 0.0) + api_time
                    )

                    executor_type = str(metadata.get("executor_type") or "llm").lower()
                    if executor_type == "program":
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

                    issue_item = {
                        "rule_job_id": rule_job_id,
                        "rule_id": str(eval_item.get("rule_id") or rule_id),
                        "rule_code": rule_code,
                        "rule_name": str(eval_item.get("rule_name") or rule_name),
                        "record_id": record_id,
                        "institute_id": institute_id,
                        "patient_id": patient_id,
                        "visit_id": str(record.get("visit_id") or ""),
                        "patient_name": str(record.get("patient_name") or ""),
                        "department": str(record.get("department") or ""),
                        "status": status,
                        **(
                            {
                                "result_status": str(
                                    eval_item.get("result_status") or status
                                )
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
                        issue_item["customer_display_facts"] = _sanitize_trace_value(
                            customer_display_facts,
                            set(),
                            max_text=120,
                        )
                    if use_luxian_customer_results:
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

                return {
                    "record_id": record_id,
                    "visit_id": visit_id,
                    "items_by_rule": items_by_rule,
                    "failed_by_rule": failed_by_rule,
                    "rule_stats": rule_stats,
                    "issue_record": has_issue,
                    "uncertain_record": has_uncertain,
                    "failed_record": any(bool(value) for value in failed_by_rule.values()),
                    "total_tokens": local_total_tokens,
                    "total_prompt_tokens": record_total_prompt_tokens,
                    "total_completion_tokens": record_total_completion_tokens,
                    "total_processing_time": local_total_processing_time,
                    "first_result_latency": record_first_result_latency,
                    "first_result_source": record_first_result_source,
                    "executor_program": local_executor_program,
                    "executor_llm": local_executor_llm,
                    "cache_hit": local_cache_hit,
                    "cache_miss": local_cache_miss,
                    "pack_metrics": record_pack_metrics,
                    "cot_summary": record_cot_summary,
                    "refine_summary": record_refine_summary,
                }
            except QCJobCancelled:
                raise
            except Exception as exc:
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
                            "error": str(exc),
                        }
                    )
                return {
                    "record_id": record_id,
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
                    "total_processing_time": 0.0,
                    "first_result_latency": 0.0,
                    "first_result_source": "",
                    "executor_program": 0,
                    "executor_llm": 0,
                    "cache_hit": 0,
                    "cache_miss": 0,
                    "pack_metrics": {},
                    "cot_summary": {},
                    "refine_summary": {},
                }

        def _merge_record_result(record_result: Dict[str, Any], processed_records_count: int) -> None:
            nonlocal total_tokens
            nonlocal total_prompt_tokens
            nonlocal total_completion_tokens
            nonlocal total_processing_time
            nonlocal first_result_latency
            nonlocal first_result_source
            nonlocal executor_program
            nonlocal executor_llm
            nonlocal cache_hit
            nonlocal cache_miss
            nonlocal total_pack_count
            nonlocal total_pack_size_weighted
            nonlocal total_pack_fallback_count
            nonlocal total_pack_parse_retry_count
            nonlocal total_single_rule_retries
            nonlocal total_context_tokens_estimate
            nonlocal total_refined_rule_count

            record_id = str(record_result.get("record_id") or "").strip()
            if record_result.get("issue_record") is True:
                issue_record_ids.add(record_id)
            if record_result.get("uncertain_record") is True:
                uncertain_record_ids.add(record_id)
            if record_result.get("failed_record") is True:
                failed_record_ids.add(record_id)

            total_tokens += int(record_result.get("total_tokens") or 0)
            total_prompt_tokens += int(record_result.get("total_prompt_tokens") or 0)
            total_completion_tokens += int(record_result.get("total_completion_tokens") or 0)
            total_processing_time += float(record_result.get("total_processing_time") or 0.0)
            executor_program += int(record_result.get("executor_program") or 0)
            executor_llm += int(record_result.get("executor_llm") or 0)
            cache_hit += int(record_result.get("cache_hit") or 0)
            cache_miss += int(record_result.get("cache_miss") or 0)

            record_first_result_latency = float(record_result.get("first_result_latency") or 0.0)
            if record_first_result_latency > 0 and first_result_latency is None:
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
                for item in list(items_by_rule.get(rule_id) or []):
                    state["items"].append(item)
                    all_items.append(item)
                for failed in list(failed_by_rule.get(rule_id) or []):
                    state["failed_records"].append(failed)
                    all_failed_records.append(failed)

            summary_patch = _build_progress_patch(processed_records_count)
            update_kwargs: Dict[str, Any] = {}
            if enable_incremental_results:
                summary_patch = {
                    **summary_patch,
                    "rule_results": _build_rule_results_snapshot(
                        processed_records_count=processed_records_count,
                        final=False,
                    ),
                    "stream_state": _build_stream_state(record_result, processed_records_count),
                    "updated_at": datetime.now(timezone.utc).isoformat(),
                }
                update_kwargs = {
                    "items": list(all_items),
                    "failed_records": list(all_failed_records),
                }

            workspace.update_batch_job_progress(
                job_id=job_id,
                step_key="run",
                rule_index=len(output_rule_ids) if output_rule_ids else 0,
                rule_count=total_rules,
                processed_records=processed_records_count,
                total_records=total_records,
                summary_patch=summary_patch,
                **update_kwargs,
            )

        initial_progress_patch = _build_progress_patch(0)
        if enable_incremental_results:
            initial_progress_patch = {
                **initial_progress_patch,
                "rule_results": _build_rule_results_snapshot(processed_records_count=0, final=False),
                "stream_state": {
                    "enabled": True,
                    "processed_records": 0,
                    "total_records": total_records,
                    "latest_record_id": "",
                    "latest_visit_id": "",
                    "latest_result_count": 0,
                    "partial_item_count": 0,
                    "partial_rule_result_count": len(output_rule_ids),
                    "started_at": job_started_at.isoformat(),
                    "updated_at": datetime.now(timezone.utc).isoformat(),
                },
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }

        workspace.update_batch_job_progress(
            job_id=job_id,
            step_key="filter",
            rule_index=0,
            rule_count=total_rules,
            processed_records=0,
            total_records=total_records,
            summary_patch=initial_progress_patch,
        )

        if run_mode == "parallel" and total_records > 1:
            semaphore = asyncio.Semaphore(max_parallel_records)

            async def _evaluate_with_limit(record: Dict[str, Any]) -> Dict[str, Any]:
                async with semaphore:
                    return await _evaluate_single_record(record)

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
                for task in tasks:
                    if not task.done():
                        task.cancel()
                await asyncio.gather(*tasks, return_exceptions=True)
                logger.info("四川批量任务 %s 已取消，停止执行", job_id)
                return
            finally:
                await asyncio.gather(*tasks, return_exceptions=True)
        else:
            for processed_index, record in enumerate(hydrated_records, start=1):
                try:
                    _raise_if_cancelled()
                    record_result = await _evaluate_single_record(record)
                except QCJobCancelled:
                    logger.info("四川批量任务 %s 已取消，停止执行", job_id)
                    return
                _merge_record_result(record_result, processed_index)

        rule_results = _build_rule_results_snapshot(
            processed_records_count=total_records,
            final=True,
        )

        postprocess_summary = summarize_postprocessed_results(all_items) if should_postprocess_job else {}
        display_status_counts = dict(postprocess_summary.get("display_status_counts") or {})
        postprocess_label_counts = dict(postprocess_summary.get("postprocess_label_counts") or {})
        data_quality_gap_record_ids = {
            str(item.get("record_id") or "")
            for item in all_items
            if (
                str(item.get("status") or "") == "data_gap"
                or str(item.get("display_status") or "") == "data_quality_gap"
            )
            and str(item.get("record_id") or "")
        }
        technical_error_record_ids = {
            str(item.get("record_id") or "")
            for item in all_items
            if str(item.get("display_status") or "") == "technical_error_internal" and str(item.get("record_id") or "")
        }
        rejected_by_system_record_ids = {
            str(item.get("record_id") or "")
            for item in all_items
            if str(item.get("display_status") or "") == "rejected_by_system" and str(item.get("record_id") or "")
        }
        not_applicable_record_ids = {
            str(item.get("record_id") or "")
            for item in all_items
            if str(item.get("status") or "").strip().lower() == "not_applicable"
            and str(item.get("record_id") or "")
        }
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
        )

        summary = {
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
        workspace.update_batch_job_progress(
            job_id=job_id,
            step_key="aggregate",
            rule_index=len(output_rule_ids),
            rule_count=total_rules,
            processed_records=total_records,
            total_records=total_records,
            summary_patch=summary,
        )
        workspace.complete_batch_job(
            job_id=job_id,
            summary=summary,
            items=all_items,
            failed_records=all_failed_records,
        )
    except QCJobCancelled:
        logger.info("四川规则批量任务 %s 已取消，后台执行已停止", job_id)
    except Exception as exc:
        logger.exception("四川规则批量任务执行失败: %s", exc)
        workspace.fail_batch_job(job_id=job_id, error_message=str(exc))


@router.post("/workspace/batch-jobs")
async def create_workspace_batch_job(
    request: Request,
    payload: SichuanWorkspaceBatchJobCreateRequest,
    qc_service: SichuanQCService = Depends(get_qc_service),
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    requested_rule_set = get_sichuan_rule_set(payload.rule_set_key)
    if payload.rule_set_key and not requested_rule_set:
        raise HTTPException(status_code=422, detail=f"未知规则集: {payload.rule_set_key}")

    requested_payload_rule_ids = [
        str(item or "").strip().upper()
        for item in (payload.rule_ids or [])
        if str(item or "").strip()
    ]
    requested_rule_set_rule_ids = list(
        requested_payload_rule_ids
        or (requested_rule_set.rule_ids if requested_rule_set else ())
    )
    direct_native_rule_ids = _ordered_luxian_0609_customer_rule_ids(
        requested_rule_set_rule_ids
    )
    is_direct_native_selection = bool(
        requested_rule_set
        and requested_rule_set.key == LUXIAN_0609_RULE_SET_KEY
        and requested_rule_set_rule_ids
        and len(direct_native_rule_ids) == len(set(requested_rule_set_rule_ids))
    )
    if (
        requested_rule_set
        and requested_rule_set.key == LUXIAN_0609_RULE_SET_KEY
        and requested_payload_rule_ids
        and not is_direct_native_selection
    ):
        raise HTTPException(status_code=422, detail="LX0609规则集只接受客户质控点ID")

    if requested_rule_set:
        rule_ids = (
            list(direct_native_rule_ids)
            if is_direct_native_selection
            else list(requested_rule_set.rule_ids)
        )
        effective_scope = (
            payload.scope
            if is_direct_native_selection
            else requested_rule_set.scope or payload.scope
        )
        rule_set_key = requested_rule_set.key
        rule_set_name = requested_rule_set.name
        rule_set_version = requested_rule_set.version
        execution_strategy = normalize_execution_strategy(requested_rule_set.execution_strategy)
        quality_profile = requested_rule_set.quality_profile
        bucket_strategy = requested_rule_set.bucket_strategy
        batch_output_mode = requested_rule_set.batch_output_mode
        enable_selective_refine = requested_rule_set.enable_selective_refine
        refine_confidence_threshold = requested_rule_set.refine_confidence_threshold
        max_refine_candidates = requested_rule_set.max_refine_candidates
    else:
        rule_ids = [str(item).strip() for item in (payload.rule_ids or []) if str(item).strip()]
        effective_scope = payload.scope
        rule_set_key = ""
        rule_set_name = ""
        rule_set_version = ""
        execution_strategy = normalize_execution_strategy(payload.execution_strategy)
        quality_profile = _normalize_quality_profile(payload.quality_profile)
        bucket_strategy = _normalize_bucket_strategy(payload.bucket_strategy)
        batch_output_mode = _normalize_batch_output_mode(
            payload.batch_output_mode,
            quality_profile=quality_profile,
        )
        enable_selective_refine = bool(payload.enable_selective_refine is True)
        refine_confidence_threshold = _normalize_refine_threshold(payload.refine_confidence_threshold)
        max_refine_candidates = _normalize_max_refine_candidates(payload.max_refine_candidates)

    if not rule_ids:
        raise HTTPException(status_code=422, detail="rule_ids 不能为空")
    compatibility_rule_ids = (
        _luxian_0609_compatibility_rule_ids(
            direct_native_rule_ids,
            settings=get_settings(),
        )
        if is_direct_native_selection
        else tuple(rule_ids)
    )
    if compatibility_rule_ids:
        _enforce_sc_source_guard(
            qc_service,
            context="workspace_batch_create",
            rule_ids=list(compatibility_rule_ids),
            block_batch=True,
        )

    workspace = _sichuan_workspace_service()
    normalized_scope = _normalize_scope(effective_scope)
    run_mode = _normalize_run_mode(payload.run_mode) if payload.run_mode else "parallel"
    records = workspace.collect_records(
        scope=normalized_scope,
        department=payload.department,
        doctor=payload.doctor,
        date_field=_normalize_date_field(payload.date_field),
        start_date=payload.start_date,
        end_date=payload.end_date,
        keyword=payload.keyword,
        record_ids=payload.record_ids or None,
    )
    if not records:
        raise HTTPException(status_code=422, detail="当前筛选条件下没有可执行病历")

    effective_record_ids = sorted(
        {
            str(record.get("record_id") or record.get("visit_id") or "").strip()
            for record in records
            if str(record.get("record_id") or record.get("visit_id") or "").strip()
        }
    )
    record_scene_snapshot = _build_workspace_record_scene_snapshot(
        records,
        query_scope=normalized_scope,
    )
    task_frozen_date = (
        datetime.now().astimezone().date().isoformat()
        if is_direct_native_selection
        else ""
    )
    record_evaluation_snapshot = (
        build_record_evaluation_horizon_snapshot(
            records,
            task_frozen_date=task_frozen_date,
        )
        if task_frozen_date
        else []
    )
    idempotency_payload = {
        "scope": normalized_scope,
        "query_scope": normalized_scope,
        "department": payload.department or "",
        "doctor": payload.doctor or "",
        "date_field": _normalize_date_field(payload.date_field),
        "start_date": payload.start_date or "",
        "end_date": payload.end_date or "",
        "keyword": payload.keyword or "",
        "record_ids": effective_record_ids,
        "record_scene_snapshot": record_scene_snapshot,
        "rule_set_key": rule_set_key,
        "rule_ids": sorted({str(rule_id).strip().upper() for rule_id in rule_ids if str(rule_id).strip()}),
        "execution_strategy": execution_strategy,
        "quality_profile": quality_profile,
        "bucket_strategy": bucket_strategy,
        "batch_output_mode": batch_output_mode,
        "run_mode": run_mode,
        **({"task_frozen_date": task_frozen_date} if task_frozen_date else {}),
        **(
            {"record_evaluation_snapshot": record_evaluation_snapshot}
            if record_evaluation_snapshot
            else {}
        ),
    }
    idempotency_digest = hashlib.sha256(
        json.dumps(idempotency_payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
    ).hexdigest()[:24]
    idempotency_key = f"sichuan-workspace-run:{idempotency_digest}"
    created_by = _current_user_id(current_user)
    for active_status in ("queued", "running"):
        active_jobs = workspace.list_batch_jobs(
            created_by=created_by,
            status=active_status,
            page=1,
            page_size=100,
        )
        for active_job in list(getattr(active_jobs, "items", []) or []):
            active_filters = dict(active_job.get("filters") or {})
            if active_filters.get("idempotency_key") == idempotency_key:
                return success_response(
                    data={
                        **active_job,
                        "execution_mode": "batch",
                        "rule_count": len(rule_ids),
                        "draft_ids": rule_ids,
                        "rule_set_key": rule_set_key,
                        "rule_set_name": rule_set_name,
                        "rule_set_version": rule_set_version,
                        "execution_strategy": execution_strategy,
                        "quality_profile": quality_profile,
                        "bucket_strategy": bucket_strategy,
                        "batch_output_mode": batch_output_mode,
                        "max_refine_candidates": max_refine_candidates,
                        "run_mode": run_mode,
                        "refine_summary": (active_job.get("summary") or {}).get("refine_summary"),
                        "idempotency_reused": True,
                    },
                    message="已复用运行中的四川规则批量任务",
                    trace_id=get_trace_id(request),
                )

    pseudo_draft = {
        "id": "sichuan-rule-library",
        "rule_code": "SC-BATCH",
        "name": f"{rule_set_name or '四川规则库'}批量任务({len(rule_ids)}条规则)",
        "scene": "running" if normalized_scope == "running" else "final",
    }
    job = workspace.create_batch_job(
        draft=pseudo_draft,
        created_by=created_by,
        scope=normalized_scope,
        filters={
            "department": payload.department,
            "doctor": payload.doctor,
            "date_field": _normalize_date_field(payload.date_field),
            "start_date": payload.start_date,
            "end_date": payload.end_date,
            "keyword": payload.keyword,
            "query_scope": normalized_scope,
            "rule_ids": rule_ids,
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
            "source": "sichuan_rule_workspace",
            "run_mode": run_mode,
            **({"task_frozen_date": task_frozen_date} if task_frozen_date else {}),
            "idempotency_key": idempotency_key,
            "idempotency_payload": idempotency_payload,
            "record_scene_snapshot": record_scene_snapshot,
            **(
                {"record_evaluation_snapshot": record_evaluation_snapshot}
                if record_evaluation_snapshot
                else {}
            ),
            **(
                {
                    "selected_rule_ids": list(direct_native_rule_ids),
                    "scoped_customer_rule_ids": list(direct_native_rule_ids),
                    "record_rule_map": {
                        record_id: list(direct_native_rule_ids)
                        for record_id in effective_record_ids
                    },
                    "validation_mode": "programmatic",
                    "customer_rule_count": len(direct_native_rule_ids),
                    "execution_rule_count": len(direct_native_rule_ids),
                }
                if is_direct_native_selection
                else {}
            ),
        },
        record_ids=payload.record_ids or [],
        total_records=len(records),
        draft_ids=rule_ids,
        execution_mode="multi",
        run_mode=run_mode,
        rule_count=len(rule_ids),
    )
    submit_detached_task(
        "sichuan_workspace_batch_job",
        _run_sichuan_workspace_batch_job,
        job["id"],
    )
    return success_response(
        data={
            **job,
            "execution_mode": "batch",
            "rule_count": len(rule_ids),
            "draft_ids": rule_ids,
            "rule_set_key": rule_set_key,
            "rule_set_name": rule_set_name,
            "rule_set_version": rule_set_version,
            "execution_strategy": execution_strategy,
            "quality_profile": quality_profile,
            "bucket_strategy": bucket_strategy,
            "batch_output_mode": batch_output_mode,
            "max_refine_candidates": max_refine_candidates,
            "run_mode": run_mode,
            "refine_summary": None,
            "idempotency_reused": False,
        },
        message="四川规则批量任务已创建",
        trace_id=get_trace_id(request),
    )


@router.get("/workspace/rule-sets")
async def list_workspace_rule_sets(request: Request, current_user: Dict[str, Any] = Depends(get_current_user)):
    return success_response(
        data={"items": list_sichuan_rule_sets()},
        message="获取四川规则集成功",
        trace_id=get_trace_id(request),
    )


@router.get("/workspace/batch-jobs")
async def list_workspace_batch_jobs(
    request: Request,
    status: Optional[str] = Query(None),
    scope: Optional[str] = Query(None),
    q: Optional[str] = Query(None),
    executor_type: Optional[str] = Query(None),
    cache_hit: Optional[str] = Query(None),
    created_start_date: Optional[str] = Query(None),
    created_end_date: Optional[str] = Query(None),
    record_id: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    workspace = _sichuan_workspace_service()
    executor_filter = str(executor_type or "").strip().lower() or None
    cache_hit_filter: Optional[bool] = None
    cache_hit_value = str(cache_hit or "").strip().lower()
    if cache_hit_value in {"hit", "true", "1", "yes"}:
        cache_hit_filter = True
    elif cache_hit_value in {"miss", "false", "0", "no"}:
        cache_hit_filter = False

    list_kwargs = {
        "created_by": _current_user_id(current_user),
        "draft_id": None,
        "status": status,
        "scope": scope,
        "executor_type": executor_filter,
        "cache_hit": cache_hit_filter,
        "created_start_date": created_start_date,
        "created_end_date": created_end_date,
        "record_id": record_id,
        "page": page,
        "page_size": page_size,
    }
    try:
        result = workspace.list_batch_jobs(
            **list_kwargs,
            query=q,
        )
    except TypeError:
        result = workspace.list_batch_jobs(
            **list_kwargs,
            q=q,
        )
    items = [
        _workspace_batch_response_item(item, compact=True)
        for item in result.items
        if _is_workspace_batch_job(item)
    ]
    return success_response(
        data={
            "items": items,
            "total": result.total,
            "page": result.page,
            "page_size": result.page_size,
        },
        message="获取四川规则批量任务成功",
        trace_id=get_trace_id(request),
    )


@router.get("/workspace/batch-jobs/{job_id}")
async def get_workspace_batch_job(
    request: Request,
    job_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    workspace = _sichuan_workspace_service()
    job = workspace.get_batch_job(job_id=job_id, created_by=_current_user_id(current_user))
    if not _is_workspace_batch_job(job):
        raise HTTPException(status_code=404, detail="批量任务不存在或无权限")
    return success_response(
        data=_workspace_batch_response_item(job),
        message="获取四川规则批量任务详情成功",
        trace_id=get_trace_id(request),
    )


@router.get("/workspace/records/{record_id}/latest-result")
async def get_latest_workspace_record_result(
    request: Request,
    record_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """返回当前用户可访问的单病历最新 LX0609 保存结果。"""

    workspace = _sichuan_workspace_service()
    result = workspace.get_latest_luxian_0609_record_result(
        created_by=_current_user_id(current_user),
        record_id=record_id,
    )
    if str(result.get("state") or "") == "not_found":
        raise HTTPException(status_code=404, detail="该病历暂无已保存质控结果或无访问权限")
    return success_response(
        data=result,
        message="获取单病历最新质控结果成功",
        trace_id=get_trace_id(request),
    )


@router.post("/workspace/batch-jobs/{job_id}/review")
async def review_workspace_batch_job(
    request: Request,
    job_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    workspace = _sichuan_workspace_service()
    created_by = _current_user_id(current_user)
    job = workspace.get_batch_job(job_id=job_id, created_by=created_by)
    if not _is_workspace_batch_job(job):
        raise HTTPException(status_code=404, detail="批量任务不存在或无权限")
    review_report = review_luxian_0609_batch_job(job)
    if review_report.get("scope") != LUXIAN_0609_RULE_SET_KEY:
        raise HTTPException(status_code=422, detail="当前复核 Loop 仅支持泸县0609质控任务")
    updated_job = workspace.update_batch_job_review_report(
        job_id=job_id,
        created_by=created_by,
        review_report=review_report,
    )
    if not _is_workspace_batch_job(updated_job):
        raise HTTPException(status_code=404, detail="批量任务不存在或无权限")
    return success_response(
        data={
            "job": _workspace_batch_response_item(updated_job),
            "review_report": review_report,
        },
        message="泸县0609结果复核完成",
        trace_id=get_trace_id(request),
    )


@router.post("/workspace/batch-jobs/{job_id}/cancel")
async def cancel_workspace_batch_job(
    request: Request,
    job_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    workspace = _sichuan_workspace_service()
    job = workspace.cancel_batch_job(job_id=job_id, created_by=_current_user_id(current_user))
    if not _is_workspace_batch_job(job):
        raise HTTPException(status_code=404, detail="批量任务不存在或无权限")
    return success_response(
        data=job,
        message="批量任务已取消",
        trace_id=get_trace_id(request),
    )


@router.post("/workspace/batch-jobs/{job_id}/retry")
async def retry_workspace_batch_job(
    request: Request,
    job_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    workspace = _sichuan_workspace_service()
    job = workspace.retry_batch_job(job_id=job_id, created_by=_current_user_id(current_user))
    if not _is_workspace_batch_job(job):
        raise HTTPException(status_code=404, detail="批量任务不存在或无权限")
    if str(job.get("job_kind") or "").strip().lower() == "parent":
        child_jobs = list(job.get("child_jobs") or job.get("children") or [])
        if not child_jobs:
            child_jobs = workspace.get_child_batch_jobs(parent_job_id=job_id, created_by=_current_user_id(current_user))
        for child_job in child_jobs:
            child_job_id = str(child_job.get("id") or "").strip()
            if child_job_id:
                submit_detached_task(
                    "sichuan_workspace_child_batch_job_retry",
                    _run_sichuan_workspace_batch_job,
                    child_job_id,
                )
    else:
        submit_detached_task(
            "sichuan_workspace_batch_job_retry",
            _run_sichuan_workspace_batch_job,
            job_id,
        )
    return success_response(
        data=job,
        message="批量任务已重新入队",
        trace_id=get_trace_id(request),
    )


@router.get("/workspace/batch-jobs/{job_id}/debug")
async def get_workspace_batch_job_debug(
    request: Request,
    job_id: str,
    rule_job_id: Optional[str] = Query(None),
    item_limit: int = Query(30, ge=1, le=200),
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    workspace = _sichuan_workspace_service()
    job = workspace.get_batch_job(job_id=job_id, created_by=_current_user_id(current_user))
    if not _is_workspace_batch_job(job):
        raise HTTPException(status_code=404, detail="批量任务不存在或无权限")
    return success_response(
        data=_build_debug_snapshot(job, rule_job_id=rule_job_id, item_limit=item_limit),
        message="获取批量任务调试快照成功",
        trace_id=get_trace_id(request),
    )


@router.get("/workspace/batch-jobs/{job_id}/trace")
async def get_workspace_batch_job_result_trace(
    request: Request,
    job_id: str,
    record_id: Optional[str] = Query(None),
    visit_id: Optional[str] = Query(None),
    rule_id: Optional[str] = Query(None),
    item_index: Optional[int] = Query(None, ge=0),
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    if not _can_view_result_trace(current_user):
        raise HTTPException(status_code=403, detail="当前账号无权查看诊断追踪")
    workspace = _sichuan_workspace_service()
    job = workspace.get_batch_job(job_id=job_id, created_by=_current_user_id(current_user))
    if not _is_workspace_batch_job(job):
        raise HTTPException(status_code=404, detail="批量任务不存在或无权限")
    trace_item = _find_result_trace_item(
        job,
        record_id=record_id,
        visit_id=visit_id,
        rule_id=rule_id,
        item_index=item_index,
    )
    if not trace_item:
        raise HTTPException(status_code=404, detail="未找到匹配的质控结果")
    return success_response(
        data=_build_result_trace_snapshot(job, trace_item),
        message="获取质控诊断追踪成功",
        trace_id=get_trace_id(request),
    )


@router.get("/workspace/batch-jobs/{job_id}/export")
async def export_workspace_batch_job(
    request: Request,
    job_id: str,
    format: str = Query("xlsx"),
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    workspace = _sichuan_workspace_service()
    job = workspace.get_batch_job(job_id=job_id, created_by=_current_user_id(current_user))
    if not _is_workspace_batch_job(job):
        raise HTTPException(status_code=404, detail="批量任务不存在或无权限")
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    normalized_format = str(format or "").lower()
    if normalized_format == "html":
        content = workspace.export_batch_job_html(job=job)
        filename = f"sichuan_rules_{job_id}_{timestamp}.html"
        return Response(
            content=content,
            media_type="text/html",
            headers={"Content-Disposition": f"attachment; filename={filename}"},
        )
    if normalized_format == "csv":
        content = workspace.export_batch_job_csv(job=job)
        filename = f"sichuan_rules_{job_id}_{timestamp}.csv"
        return StreamingResponse(
            iter([content.getvalue().encode("utf-8-sig")]),
            media_type="text/csv; charset=utf-8",
            headers={"Content-Disposition": f"attachment; filename={filename}"},
        )
    workbook = workspace.export_batch_job_workbook(job=job)
    filename = f"sichuan_rules_{job_id}_{timestamp}.xlsx"
    return StreamingResponse(
        workbook,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@router.post("/results/save")
async def save_qc_result(request: Request, req: SaveQCResultRequest):
    try:
        base_dir = Path(__file__).resolve().parent.parent / "storage" / "qc_results"
        base_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        result_id = str(uuid.uuid4())
        filename = f"{result_id}_{req.mode}_{timestamp}.json"
        filepath = base_dir / filename

        payload = {
            "id": result_id,
            "mode": req.mode,
            "document_type": req.document_type,
            "document_id": req.document_id,
            "rule_ids": req.rule_ids,
            "medical_text": req.medical_text,  # 保存原始病历文本
            "medical_text_length": req.medical_text_length,
            "stats": req.stats,
            "performance": req.performance,
            "results": req.results,
            "payload": req.payload,
            "metadata": req.metadata,
            "model": req.model,  # 保存使用的模型名称
            "created_at": datetime.now(timezone.utc).isoformat()
        }

        with filepath.open("w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)

        return success_response(
            data={"id": result_id, "path": str(filepath)},
            message="质控结果保存成功",
            trace_id=get_trace_id(request),
        )
    except Exception as e:
        raise HTTPException(status_code=StatusCode.INTERNAL_SERVER_ERROR, detail=f"保存质控结果失败: {e}")


@router.get("/results/history")
async def get_qc_history(
    request: Request,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    document_type: Optional[str] = Query(None),
    mode: Optional[str] = Query(None),  # 新增：质控模式筛选 (optimized_batch/sequential_batch)
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    has_issues: Optional[bool] = Query(None)
):
    """获取质控结果历史列表"""
    try:
        base_dir = Path(__file__).resolve().parent.parent / "storage" / "qc_results"
        if not base_dir.exists():
            return success_response(
                data={
                    "records": [],
                    "total": 0,
                    "page": page,
                    "page_size": page_size,
                },
                message="暂无历史记录",
                trace_id=get_trace_id(request),
            )

        # 读取所有JSON文件
        all_files = sorted(base_dir.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
        records = []

        for filepath in all_files:
            try:
                with filepath.open("r", encoding="utf-8") as f:
                    data = json.load(f)

                # 提取摘要信息
                stats = data.get("stats", {})
                metadata = data.get("metadata", {})
                payload = data.get("payload", {})
                evaluation_summary = payload.get("evaluation_summary", {})

                # 应用筛选条件
                if document_type and data.get("document_type") != document_type:
                    continue

                if mode and data.get("mode") != mode:
                    continue

                created_at = data.get("created_at") or data.get("saved_at")
                if start_date and created_at < start_date:
                    continue
                if end_date and created_at > end_date:
                    continue

                # 优先从 evaluation_summary 获取合规率和问题数量，否则从 stats 获取
                compliance_rate = evaluation_summary.get("compliance_rate") or stats.get("compliance_rate", 0)
                issues_count = evaluation_summary.get("issues_found") or stats.get("issues", 0)

                if has_issues is not None:
                    if has_issues and issues_count == 0:
                        continue
                    if not has_issues and issues_count > 0:
                        continue

                # 优先从 evaluation_summary 获取 total_rules
                total_rules = evaluation_summary.get("total_rules") or stats.get("total", len(data.get("rule_ids", [])))

                # 获取模型名称（优先从 evaluation_summary，其次顶层 model，最后从 llm_info 中获取）
                llm_info = payload.get("llm_info") or data.get("llm_info") or {}
                model = (
                    evaluation_summary.get("model")
                    or data.get("model")
                    or llm_info.get("model")
                )

                record = {
                    "id": data.get("id", filepath.stem),
                    "document_id": data.get("document_id"),
                    "document_type": data.get("document_type"),
                    "mode": data.get("mode"),
                    "model": model,
                    "prompt_mode": metadata.get("prompt_mode"),
                    "compliance_rate": compliance_rate,
                    "issues_count": issues_count,
                    "total_rules": total_rules,
                    "created_at": created_at,
                    "stats": stats,
                    "performance": data.get("performance"),
                    "metadata": metadata
                }
                records.append(record)
            except Exception as e:
                logger.warning(f"读取质控结果文件失败 {filepath}: {e}")
                continue

        # 分页
        total = len(records)
        start_idx = (page - 1) * page_size
        end_idx = start_idx + page_size
        paginated_records = records[start_idx:end_idx]

        return success_response(
            data={
                "records": paginated_records,
                "total": total,
                "page": page,
                "page_size": page_size,
            },
            message="获取质控历史成功",
            trace_id=get_trace_id(request),
        )
    except Exception as e:
        raise HTTPException(status_code=StatusCode.INTERNAL_SERVER_ERROR, detail=f"获取质控历史失败: {e}")


@router.get("/results/latest")
async def get_latest_qc_result(request: Request):
    """获取最新一次质控结果"""
    try:
        base_dir = Path(__file__).resolve().parent.parent / "storage" / "qc_results"
        if not base_dir.exists():
            raise HTTPException(status_code=StatusCode.NOT_FOUND, detail="暂无质控结果")

        # 获取最新的文件
        all_files = sorted(base_dir.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
        if not all_files:
            raise HTTPException(status_code=StatusCode.NOT_FOUND, detail="暂无质控结果")

        latest_file = all_files[0]
        with latest_file.open("r", encoding="utf-8") as f:
            data = json.load(f)

        return success_response(
            data=data,
            message="获取最新质控结果成功",
            trace_id=get_trace_id(request),
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=StatusCode.INTERNAL_SERVER_ERROR, detail=f"获取最新质控结果失败: {e}")


@router.get("/results/{result_id:path}")
async def get_qc_result_detail(request: Request, result_id: str):
    """获取指定ID的质控结果详情"""
    try:
        base_dir = Path(__file__).resolve().parent.parent / "storage" / "qc_results"
        if not base_dir.exists():
            raise HTTPException(status_code=StatusCode.NOT_FOUND, detail="质控结果不存在")

        # 首先尝试直接匹配文件名（result_id.json）
        direct_match = base_dir / f"{result_id}.json"
        if direct_match.exists():
            with direct_match.open("r", encoding="utf-8") as f:
                data = json.load(f)

            payload = data.get("payload", {})
            evaluation_summary = payload.get("evaluation_summary", {})
            llm_info = payload.get("llm_info") or data.get("llm_info") or {}
            model = (
                data.get("model")
                or evaluation_summary.get("model")
                or llm_info.get("model")
            )
            if model and not data.get("model"):
                data["model"] = model

            return success_response(
                data=data,
                message="获取质控结果详情成功",
                trace_id=get_trace_id(request),
            )

        # 如果直接匹配失败，尝试查找以result_id开头的文件（result_id_*.json）
        matching_files = list(base_dir.glob(f"{result_id}_*.json"))
        if not matching_files:
            # 最后尝试查找包含result_id的文件
            matching_files = [f for f in base_dir.glob("*.json") if result_id in f.stem]

        if not matching_files:
            raise HTTPException(status_code=StatusCode.NOT_FOUND, detail=f"质控结果不存在: {result_id}")

        filepath = matching_files[0]
        with filepath.open("r", encoding="utf-8") as f:
            data = json.load(f)

        payload = data.get("payload", {})
        evaluation_summary = payload.get("evaluation_summary", {})
        llm_info = payload.get("llm_info") or data.get("llm_info") or {}
        model = (
            data.get("model")
            or evaluation_summary.get("model")
            or llm_info.get("model")
        )
        if model and not data.get("model"):
            data["model"] = model

        return success_response(
            data=data,
            message="获取质控结果详情成功",
            trace_id=get_trace_id(request),
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=StatusCode.INTERNAL_SERVER_ERROR, detail=f"获取质控结果详情失败: {e}")


@router.get("/stats")
async def stats(
    request: Request,
    qc_service: SichuanQCService = Depends(get_qc_service)
):
    try:
        st = qc_service.stats()
        s = get_settings()
        response = {
            "service_statistics": {
                "total_calls": st.get("total_calls", 0),
                "success_calls": st.get("success_calls", 0),
                "error_calls": st.get("error_calls", 0),
                "success_rate": st.get("success_rate", 0.0),
            },
            "performance_metrics": {
                "avg_api_time": st.get("avg_api_time", 0.0),
                "total_api_time": st.get("total_api_time", 0.0),
                "total_tokens": st.get("total_tokens", 0),
            },
            "optimization_achievements": {
                "token_savings_rate": 0.80,
                "estimated_original_tokens": st.get("total_tokens", 0) * 5,
                "actual_tokens_saved": st.get("total_tokens", 0) * 4,
                "total_cost_savings": st.get("total_tokens", 0) * 4 / 1000 * 0.002,
            },
            "real_time_status": {
                "service_health": "healthy",
                "api_endpoint": str(s.LLM_API_ENDPOINT) if s.LLM_API_ENDPOINT else None,
                "model": s.LLM_MODEL,
                "last_updated": datetime.now(timezone.utc).isoformat(),
            },
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "status": "success",
        }
        return response
    except Exception as e:
        raise HTTPException(status_code=StatusCode.INTERNAL_SERVER_ERROR, detail=f"获取四川省质控统计失败: {e}")


@router.get("/rules")
async def rules(
    request: Request,
    document_type: Optional[str] = Query(default=None, description="单个文书类型（中文）"),
    document_types: Optional[str] = Query(default=None, description="逗号分隔的文书类型（中文）"),
    grouped: Optional[bool] = Query(default=False, description="是否按文书类型分组返回"),
    rule_set_key: Optional[str] = Query(default=None, description="规则集 key"),
):
    """
    返回四川省质控规则。
    优先从 Supabase 的 `qc_rules` 表读取；如果未配置或查询失败，则回退到内置示例规则。
    """
    wanted_docs: set[str] = set()
    if document_type:
        wanted_docs.add(document_type.strip())
    if document_types:
        for t in document_types.split(","):
            t = t.strip()
            if t:
                wanted_docs.add(t)

    normalized_rule_set_key = str(rule_set_key or "").strip()
    if normalized_rule_set_key == LUXIAN_0609_RULE_SET_KEY:
        data = filter_luxian_0609_rules_by_documents(
            load_luxian_0609_rules(),
            wanted_docs=wanted_docs,
        )

        if grouped:
            by_type: dict[str, list[dict[str, Any]]] = {}
            for rule in data:
                docs = rule.get("applicable_document_labels") or rule.get("applicable_documents") or []
                if not docs:
                    docs = ["通用文书"]
                for doc_type_item in docs:
                    by_type.setdefault(str(doc_type_item), []).append(rule)
            return success_response(
                data={
                    "rules_by_document_type": by_type,
                    "document_types": list(sorted(by_type.keys())),
                    "total_rules": sum(len(items) for items in by_type.values()),
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "status": "success",
                    "source": "luxian_0609_rules_v1",
                    "rule_set_key": LUXIAN_0609_RULE_SET_KEY,
                    "rule_set_name": LUXIAN_0609_RULE_SET_NAME,
                },
                message="获取规则成功",
                trace_id=get_trace_id(request),
            )

        complexity_distribution: dict[str, int] = {}
        defect_level_distribution: dict[str, int] = {}
        for rule in data:
            complexity = str(rule.get("complexity") or "未知")
            defect_level = str(rule.get("defect_level") or "未知")
            complexity_distribution[complexity] = complexity_distribution.get(complexity, 0) + 1
            defect_level_distribution[defect_level] = defect_level_distribution.get(defect_level, 0) + 1

        return success_response(
            data={
                "rules": data,
                "total_rules": len(data),
                "document_type_filter": list(wanted_docs) if wanted_docs else None,
                "rule_categories": list(sorted({rule.get("category", "泸县0609质控点") for rule in data})),
                "complexity_distribution": complexity_distribution,
                "defect_level_distribution": defect_level_distribution,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "status": "success",
                "source": "luxian_0609_rules_v1",
                "rule_set_key": LUXIAN_0609_RULE_SET_KEY,
                "rule_set_name": LUXIAN_0609_RULE_SET_NAME,
            },
            message="获取规则成功",
            trace_id=get_trace_id(request),
        )

    # 临时：强制使用 JSON 文件中的 146 条规则，待规则稳定后再批量导入 Supabase
    supabase = None  # get_supabase()
    records: list[dict[str, Any]] | None = None

    if supabase is not None:
        try:
            # 取启用的规则，最多1000条
            async def _exec(q):
                try:
                    exec_async = getattr(q, "execute_async", None)
                    if callable(exec_async):
                        return await exec_async()
                except Exception:
                    pass
                return q.execute()

            resp = await _exec(supabase.table("qc_rules").select("*").eq("is_active", True).limit(1000))
            records = resp.data or []
        except Exception:
            records = None

    data: list[dict[str, Any]]
    source = "fallback"
    launch_tier_map = load_sc_intrinsic_launch_tier_map()

    def enrich_launch_tier(item: dict[str, Any]) -> dict[str, Any]:
        rule_id = str(item.get("rule_id") or item.get("rule_code") or "").strip()
        tier = resolve_sc_intrinsic_launch_tier(rule_id, launch_tier_map=launch_tier_map)
        tier_label_map = {
            "A": "默认启用",
            "B": "灰度",
            "C": "观察",
            "UNKNOWN": "未分层",
        }
        enriched = dict(item)
        enriched["launch_tier"] = tier
        enriched["launch_tier_label"] = tier_label_map.get(tier, "未分层")
        return enriched

    if records is not None and len(records) > 0:
        def normalize(rec: dict[str, Any]) -> dict[str, Any]:
            # 统一字段到前端所需格式
            # 业务主键优先使用规则库中的可读规则编号，避免回传数据库内部 id 影响后续接口
            # 优先级：rule_id(如 SC-001) > rule_code(如 SC-001/3.1.1) > id(内部主键兜底)
            rule_id = rec.get("rule_id") or rec.get("rule_code") or rec.get("id") or ""
            rule_code = rec.get("rule_code") or rec.get("rule_id") or rec.get("id") or ""
            name = rec.get("name") or rec.get("rule_name") or "未命名规则"
            description = rec.get("description") or rec.get("desc") or ""
            category = rec.get("category") or rec.get("rule_category") or "基础"
            # 复杂度/缺陷级别可能为英文，保持原样，前端已做兼容
            complexity = rec.get("complexity") or rec.get("rule_complexity") or "中复杂度"
            defect_level = rec.get("defect_level") or rec.get("severity") or "一般缺陷"
            score_deduction = rec.get("score_deduction") or rec.get("deduction_score") or 0
            # 文书类型来源优先级：top-level applicable_documents -> document_types -> check_logic.applicable_documents
            docs = (
                rec.get("applicable_documents")
                or rec.get("document_types")
                or (rec.get("check_logic") or {}).get("applicable_documents")
                or []
            )
            if isinstance(docs, str):
                # 简单拆分字符串形式
                docs = [d.strip() for d in docs.split(",") if d.strip()]
            return enrich_launch_tier({
                "rule_id": rule_id,
                "rule_code": rule_code,
                "name": name,
                "description": description,
                "category": category,
                "complexity": complexity,
                "defect_level": defect_level,
                "score_deduction": score_deduction,
                "applicable_documents": docs,
                "medical_domain": rec.get("medical_domain") or rec.get("domain") or "通用",
                "requires_rag": bool(rec.get("requires_rag") or rec.get("need_rag") or False),
                "requires_cot": bool(rec.get("requires_cot") or rec.get("need_cot") or False),
            })

        data = [normalize(r) for r in records]
        source = "supabase"
    elif records is None or len(records) == 0:
        # 回退到完整的146条四川规则（从JSON文件加载）
        import json
        from pathlib import Path

        rules_file = Path(__file__).parent.parent / "data" / "sichuan_rules_146.json"
        try:
            with open(rules_file, "r", encoding="utf-8") as f:
                full_rules = json.load(f)

            # 英文→中文 文书类型映射，保持与服务侧一致
            doc_type_mapping = {
                "admission_record": "入院记录",
                "progress_note": "病程记录",
                "course_record": "病程记录",
                "operation_record": "手术记录",
                "discharge_record": "出院记录",
                "discharge_summary": "出院记录",
                "consent_form": "知情同意书",
                "examination_report": "检查报告",
                "lab_report": "检查报告",
                "medical_order": "医嘱",
                "consultation_record": "病程记录",
                "case_discussion": "病程记录",
                "anesthesia_record": "手术记录",
                "transfusion_record": "病程记录",
                "informed_consent": "知情同意书",
            }

            # 转换格式
            data = []
            for rule in full_rules:
                docs = [doc_type_mapping.get(d, d) for d in (rule.get("applicable_documents", []) or [])]
                data.append(enrich_launch_tier({
                    "rule_id": rule.get("rule_id", ""),
                    "rule_code": rule.get("rule_code", rule.get("rule_id", "")),
                    "name": rule.get("name", ""),
                    "category": rule.get("category", ""),
                    "defect_level": rule.get("defect_level", "一般缺陷"),
                    "complexity": rule.get("complexity", "中复杂度"),
                    "applicable_documents": docs,
                    "score_deduction": rule.get("score_deduction", ""),
                    "medical_domain": "通用",
                    "requires_rag": False,
                    "requires_cot": False,
                    "description": rule.get("description", "")
                }))
            source = "json_file"
            logger.info("Loaded %s Sichuan rules from JSON file", len(data))
        except Exception as e:
            logger.warning("Failed to load Sichuan rules JSON file, fallback to minimal sample: %s", e)
            data = [
                enrich_launch_tier({"rule_id": "sc-001", "name": "入院记录完整性", "category": "基础", "defect_level": "major", "complexity": "medium", "applicable_documents": ["入院记录"], "score_deduction": 2, "medical_domain": "通用", "requires_rag": False, "requires_cot": False, "description": "检查入院记录结构是否完整"}),
            ]
    else:
        # Supabase 查询成功但无数据：返回空数组，不再回退
        data = []
        source = "supabase"

    # 可选过滤/分组
    def _match_doc(rule_docs: list[str], wanted: set[str]) -> bool:
        if not wanted:
            return True
        rd = {str(x).strip() for x in (rule_docs or [])}
        # 大小写/空白宽松匹配（中文一般直接等值）
        return bool(rd.intersection(wanted))

    filtered = [d for d in data if _match_doc(d.get("applicable_documents") or [], wanted_docs)]

    if grouped:
        by_type: dict[str, list[dict[str, Any]]] = {}
        for r in filtered:
            docs = r.get("applicable_documents") or []
            if not docs:
                docs = ["通用文书"]
            for dt in docs:
                by_type.setdefault(str(dt), []).append(r)
        return success_response(
            data={
                "rules_by_document_type": by_type,
                "document_types": list(sorted(by_type.keys())),
                "total_rules": sum(len(v) for v in by_type.values()),
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "status": "success",
                "source": source,
            },
            message="获取规则成功",
            trace_id=get_trace_id(request),
        )

    return success_response(
        data={
            "rules": filtered,
            "total_rules": len(filtered),
            "document_type_filter": list(wanted_docs) if wanted_docs else None,
            "rule_categories": list(sorted({d.get("category", "基础") for d in filtered})),
            "complexity_distribution": {},
            "defect_level_distribution": {},
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "status": "success",
            "source": source,
        },
        message="获取规则成功",
        trace_id=get_trace_id(request),
    )


# ------------------------- Persistence Helpers -------------------------

def _is_uuid_like(s: str) -> bool:
    try:
        uuid.UUID(str(s))
        return True
    except Exception:
        return False


def _persist_evaluation_to_db(document_id: str, result: Dict[str, Any]) -> None:
    """Best-effort persistence into medical_documents and document_qc_results.
    - Skips silently if Supabase not configured or document_id not UUID.
    - Updates qc_* fields and inserts rule-level rows.
    """
    if not _is_uuid_like(document_id):
        return

    sb = get_supabase()
    if sb is None:
        return

    try:
        summary = (result.get("evaluation_summary") or result.get("overall_summary") or {})
        compliance_rate = float(summary.get("compliance_rate", 0.0))
        critical = int(summary.get("critical_violations", 0)) if "critical_violations" in summary else 0
        qc_status = (
            "passed" if compliance_rate >= 90 and critical == 0 else
            ("warning" if compliance_rate >= 60 else "failed")
        )

        # Update medical_documents
        sb.table("medical_documents").update({
            "qc_status": qc_status,
            "qc_score": round(compliance_rate, 2),
            "qc_last_analyzed": datetime.now(timezone.utc).isoformat(),
            "qc_analysis_version": "sichuan-1.0",
        }).eq("id", document_id).execute()

        # Insert rule-level results (if any)
        items: List[Dict[str, Any]] = result.get("evaluation_results") or []
        payloads: List[Dict[str, Any]] = []
        for it in items[:200]:
            passed = bool(it.get("is_compliant") is True)
            payloads.append({
                "document_id": document_id,
                "rule_id": it.get("rule_id") or "unknown",
                "result_status": "passed" if passed else "failed",
                "score": 0,
                "max_score": 100,
                "confidence_score": float(it.get("confidence", 0)) if it.get("confidence") is not None else None,
                "issue_category": None,
                "issue_description": it.get("findings") or "",
                "evidence_text": it.get("evidence") or "",
                "evidence_location": None,
                "suggestions": None,
                "ai_reasoning": None,
                "ai_model_used": None,
                "analysis_time_ms": None,
            })

        if payloads:
            # Bulk insert; ignore errors per-row by inserting one-by-one to keep simple
            for row in payloads:
                try:
                    sb.table("document_qc_results").insert(row).execute()
                except Exception:
                    continue
    except Exception:
        # Best-effort: never raise from persistence
        return


# ------------------------- Single Rule Testing -------------------------

class TestRuleRequest(BaseModel):
    rule_id: str
    medical_text: str


def _load_single_test_rule(qc_service: SichuanQCService, rule_id: str) -> tuple[Optional[Dict[str, Any]], bool]:
    normalized_rule_id = str(rule_id or "").strip().upper()
    if normalized_rule_id.startswith("LX0609-"):
        rule = get_luxian_0609_rule(normalized_rule_id)
        if rule:
            # 泸县0609是客户专项包装规则，单条测试应按客户质控点口径执行。
            # 这里不复用底层 SC/LX/CL 的单文书适用性门控，避免跨文书质控点被提前判为不适用。
            rule["applicable_documents"] = []
            rule["rule_code"] = rule.get("rule_code") or rule.get("rule_id")
            rule["defect_level"] = rule.get("defect_level") or "一般缺陷"
            rule["complexity"] = rule.get("complexity") or "中复杂度"
            return rule, True
    return qc_service.get_rule_by_id(rule_id), False


def _parse_luxian_datetime(value: str) -> Optional[datetime]:
    text = str(value or "").strip()
    patterns = (
        "%Y-%m-%d %H:%M",
        "%Y-%m-%d %H:%M:%S",
        "%Y年%m月%d日 %H:%M",
        "%Y年%m月%d日%H:%M",
    )
    for pattern in patterns:
        try:
            return datetime.strptime(text, pattern)
        except ValueError:
            continue
    return None


def _extract_labeled_luxian_time(text: str, labels: tuple[str, ...]) -> Optional[datetime]:
    for label in labels:
        pattern = rf"{re.escape(label)}\s*[:：]\s*(\d{{4}}[-年]\d{{1,2}}[-月]\d{{1,2}}(?:日)?\s+\d{{1,2}}:\d{{2}}(?::\d{{2}})?)"
        match = re.search(pattern, text)
        if match:
            parsed = _parse_luxian_datetime(
                match.group(1).replace("年", "-").replace("月", "-").replace("日", "")
            )
            if parsed:
                return parsed
    return None


def _apply_luxian_time_rule(result: Dict[str, Any], medical_text: str) -> Optional[Dict[str, Any]]:
    rule_id = str(result.get("rule_id") or "").strip().upper()
    configs = {
        "LX0609-001": (("入院时间",), ("记录时间",), 24),
        "LX0609-002": (("入院时间",), ("记录时间",), 8),
        "LX0609-003": (("手术结束时间",), ("记录时间",), 24),
        "LX0609-004": (("抢救结束时间",), ("记录时间",), 6),
    }
    config = configs.get(rule_id)
    if not config:
        return None
    start_labels, end_labels, limit_hours = config
    start_time = _extract_labeled_luxian_time(medical_text, start_labels)
    end_time = _extract_labeled_luxian_time(medical_text, end_labels)
    if rule_id == "LX0609-003" and not start_time:
        surgery_time_match = re.search(
            r"手术时间\s*[:：]\s*"
            r"(\d{4}[-年]\d{1,2}[-月]\d{1,2}(?:日)?)\s+\d{1,2}:\d{2}"
            r"\s*[至-]\s*"
            r"(?:(\d{4}[-年]\d{1,2}[-月]\d{1,2}(?:日)?)\s+)?(\d{1,2}:\d{2})",
            medical_text,
        )
        if surgery_time_match:
            end_date = surgery_time_match.group(2) or surgery_time_match.group(1)
            date_part = end_date.replace("年", "-").replace("月", "-").replace("日", "")
            start_time = _parse_luxian_datetime(f"{date_part} {surgery_time_match.group(3)}")
    if not start_time or not end_time:
        return None
    elapsed_hours = (end_time - start_time).total_seconds() / 3600
    normalized = dict(result)
    normalized["is_compliant"] = elapsed_hours <= limit_hours
    normalized["status"] = "compliant" if normalized["is_compliant"] else "non_compliant"
    normalized["not_applicable"] = False
    normalized["applicability"] = {"is_applicable": True, "reason": "", "method": "luxian_time_rule"}
    metadata = dict(normalized.get("metadata") or {})
    metadata["engine"] = "luxian_time_rule"
    normalized["metadata"] = metadata
    normalized["confidence"] = max(float(normalized.get("confidence") or 0), 0.98)
    start_label = start_labels[0]
    end_label = end_labels[0]
    if rule_id == "LX0609-003":
        start_label = "手术结束时间"
    elapsed_text = f"{elapsed_hours:.1f}".rstrip("0").rstrip(".")
    evidence = (
        f"{start_label}: {start_time.strftime('%Y-%m-%d %H:%M')}；"
        f"{end_label}: {end_time.strftime('%Y-%m-%d %H:%M')}；"
        f"间隔 {elapsed_text} 小时。"
    )
    normalized["evidence"] = normalized.get("evidence") or evidence
    if normalized["is_compliant"]:
        normalized["findings"] = normalized.get("findings") or (
            f"{evidence}未超过 {limit_hours} 小时限制，符合规则要求。"
        )
        normalized["suggestion"] = normalized.get("suggestion") or ""
        normalized["issues"] = []
    else:
        normalized["findings"] = normalized.get("findings") or (
            f"{evidence}超过 {limit_hours} 小时限制，存在超时缺陷。"
        )
        normalized["suggestion"] = normalized.get("suggestion") or (
            f"请按病历书写规范在 {limit_hours} 小时内完成对应记录，并补充逾期原因说明。"
        )
        normalized["issues"] = normalized.get("issues") or [
            {"description": f"记录完成时间超过 {limit_hours} 小时限制", "evidence": evidence}
        ]
    return normalized


def _extract_luxian_section(text: str, title: str, next_titles: tuple[str, ...] = ()) -> str:
    start = text.find(title)
    if start < 0:
        return ""
    end_candidates = [text.find(next_title, start + len(title)) for next_title in next_titles]
    end_candidates = [index for index in end_candidates if index >= 0]
    end = min(end_candidates) if end_candidates else len(text)
    return text[start:end]


def _apply_luxian_preop_surgeon_rule(result: Dict[str, Any], medical_text: str) -> Optional[Dict[str, Any]]:
    rule_id = str(result.get("rule_id") or "").strip().upper()
    if rule_id != "LX0609-039":
        return None

    preop_section = _extract_luxian_section(
        medical_text,
        "文书标题：术前讨论记录",
        ("文书标题：手术医嘱", "文书标题：手术记录"),
    )
    surgery_section = _extract_luxian_section(medical_text, "文书标题：手术记录")
    if not preop_section or not surgery_section:
        return None

    surgeon_match = re.search(r"术者[：:]\s*([^。；，,\n]+)", surgery_section)
    if not surgeon_match:
        return None
    surgeon = surgeon_match.group(1).strip()
    is_emergency_rescue = bool(re.search(r"(?<!非)急诊抢救|抢救生命", medical_text))
    if is_emergency_rescue:
        return None

    normalized = dict(result)
    surgeon_in_preop = surgeon in preop_section
    normalized["is_compliant"] = surgeon_in_preop
    normalized["status"] = "compliant" if surgeon_in_preop else "non_compliant"
    normalized["not_applicable"] = False
    normalized["applicability"] = {"is_applicable": True, "reason": "", "method": "luxian_preop_surgeon_rule"}
    metadata = dict(normalized.get("metadata") or {})
    metadata["engine"] = "luxian_preop_surgeon_rule"
    normalized["metadata"] = metadata
    normalized["confidence"] = max(float(normalized.get("confidence") or 0), 0.98)
    normalized["evidence"] = (
        f"手术记录术者：{surgeon}；"
        f"术前讨论记录签名/参加人员片段：{preop_section[-180:]}"
    )
    if surgeon_in_preop:
        normalized["findings"] = f"术前讨论记录中包含拟任术者 {surgeon}，符合规则要求。"
        normalized["suggestion"] = normalized.get("suggestion") or ""
        normalized["issues"] = []
    else:
        normalized["findings"] = (
            f"手术记录显示术者为 {surgeon}，但术前讨论记录的参加人员或签名中未见该术者，"
            "不符合非急诊手术术者应参加术前讨论的要求。"
        )
        normalized["suggestion"] = "请补充术者参加术前讨论的记录、讨论意见和签名，或完善术前讨论记录。"
        normalized["issues"] = [
            {"description": "术者未参加术前讨论", "evidence": normalized["evidence"]}
        ]
    return normalized


def _apply_luxian_local_rule(result: Dict[str, Any], medical_text: str) -> Optional[Dict[str, Any]]:
    return (
        _apply_luxian_time_rule(result, medical_text)
        or _apply_luxian_preop_surgeon_rule(result, medical_text)
    )


def _normalize_luxian_single_test_result(result: Dict[str, Any], medical_text: str) -> Dict[str, Any]:
    """修正泸县0609单条测试中 LLM JSON 字段与文字结论自相矛盾的情况。

    仅用于规则管理页正反例测试，不进入正式批量质控链路。
    """
    normalized = dict(result)
    raw_output = str(normalized.get("llm_raw_output") or "")
    findings = str(normalized.get("findings") or "")
    evidence = str(normalized.get("evidence") or "")
    suggestion = str(normalized.get("suggestion") or "")
    haystack = f"{findings}\n{evidence}\n{suggestion}\n{raw_output}"

    local_rule_result = _apply_luxian_local_rule(normalized, medical_text)
    if local_rule_result:
        return local_rule_result

    raw_declares_non_compliant = bool(
        re.search(r'"is_compliant"\s*:\s*false', raw_output, flags=re.IGNORECASE)
    )
    non_compliant_patterns = (
        r"属于不合规",
        r"判定为不合规",
        r"不符合(?:规则|要求|规定)",
        r"不合规情形",
        r"严重缺陷",
        r"缺陷",
        r"未[^。；，,]*(?:记录|分析|完成|签名|说明)",
        r"无[^。；，,]*(?:记录|分析|签名|说明)",
        r"存在[^。；，,]*违规情形",
        r"出现[^。；，,]*违规情形",
        r"已超时",
        r"超时未",
        r"超出[^。；，,]*时限",
        r"已超过[^。；，,]*时限",
        r"(?<!未)超过了[^。；，,]*时限",
        r"(?<!未)超过[^。；，,]*限制",
        r"记录时间[^。；，,]*晚于",
        r"患者签名[:：][^。；，,]*未签",
        r"待补签",
        r"收费中[^。；，,]*不一致",
        r"与医嘱[^。；，,]*不一致",
        r"(?<!未)(?:存在|出现|发现|构成|属于)[^。；，,]*(?:完全相同|逐字复制)",
    )
    has_non_compliant_text = any(re.search(pattern, haystack) for pattern in non_compliant_patterns)
    compliant_patterns = (
        r"符合[^。；，,]*规则",
        r"符合[^。；，,]*质控",
        r"符合规定",
        r"未发现[^。；，,]*(?:违规|不合规|缺陷|问题)",
        r"不存在[^。；，,]*(?:不一致|缺失|缺少)",
        r"(?:未出现|并未出现|未发现)[^。；，,]*(?:完全相同|逐字复制)",
        r"未超过[^。；，,]*(?:时限|限制)",
        r"记录齐全",
    )
    has_compliant_text = any(re.search(pattern, findings) for pattern in compliant_patterns)

    if raw_declares_non_compliant or has_non_compliant_text:
        normalized["is_compliant"] = False
        normalized["status"] = "non_compliant"
        normalized["not_applicable"] = False
        applicability = dict(normalized.get("applicability") or {})
        applicability["is_applicable"] = True
        normalized["applicability"] = applicability
        if not normalized.get("issues") and findings:
            normalized["issues"] = [{"description": "命中质控点", "evidence": findings[:120]}]
    elif has_compliant_text:
        normalized["is_compliant"] = True
        normalized["status"] = "compliant"
        normalized["not_applicable"] = False
        normalized["issues"] = []
        applicability = dict(normalized.get("applicability") or {})
        applicability["is_applicable"] = True
        normalized["applicability"] = applicability
    return normalized


@router.post("/test-rule")
async def test_rule(
    request: Request,
    req: TestRuleRequest,
    qc_service: SichuanQCService = Depends(get_qc_service)
):
    """测试单条质控规则的有效性和正确性"""
    try:
        target_rule, is_luxian_wrapper = _load_single_test_rule(qc_service, req.rule_id)
        if target_rule is None:
            raise HTTPException(
                status_code=404, detail=f"未找到规则 ID: {req.rule_id}"
            )

        if is_luxian_wrapper:
            local_rule_result = _apply_luxian_local_rule(
                {
                    "rule_id": target_rule.get("rule_id") or req.rule_id,
                    "rule_name": target_rule.get("name") or target_rule.get("rule_name"),
                    "is_compliant": True,
                    "issues": [],
                    "findings": "",
                    "evidence": "",
                    "suggestion": "",
                    "confidence": 0,
                    "llm_raw_output": None,
                    "status": "compliant",
                    "applicability": {"is_applicable": True, "reason": "", "method": "luxian_time_rule"},
                    "not_applicable": False,
                    "not_applicable_reason": None,
                    "evidence_verified": True,
                    "evidence_span": None,
                    "token_usage": {"total_tokens": 0},
                    "metadata": {"engine": "luxian_time_rule"},
                },
                req.medical_text,
            )
            if local_rule_result:
                return success_response(
                    data=local_rule_result,
                    message="规则测试完成",
                    trace_id=get_trace_id(request),
                )

        engine_result = await qc_service.rule_engine.evaluate(
            rule=target_rule,
            medical_record={
                "id": req.rule_id,
                "content": req.medical_text,
                "document_type": "" if is_luxian_wrapper else target_rule.get("category") or "",
            }
        )

        # 统一的响应结构，确保前端字段兼容
        metadata = engine_result.get("metadata", {}) or {}
        response_data = {
            "rule_id": engine_result.get("rule_id"),
            "rule_name": engine_result.get("rule_name"),
            "is_compliant": engine_result.get("is_compliant", True),
            "issues": engine_result.get("issues", []),
            "findings": engine_result.get("findings", ""),
            "evidence": engine_result.get("evidence", ""),
            "suggestion": engine_result.get("suggestion", ""),
            "confidence": engine_result.get("confidence", 0.7),
            "llm_raw_output": engine_result.get("llm_raw_output"),
            "status": engine_result.get("status"),
            "applicability": engine_result.get("applicability"),
            "not_applicable": not engine_result.get("applicability", {}).get("is_applicable", True),
            "not_applicable_reason": engine_result.get("applicability", {}).get("reason"),
            "evidence_verified": engine_result.get("evidence_verified", True),
            "evidence_span": engine_result.get("evidence_span"),
            "token_usage": {"total_tokens": metadata.get("tokens_used", 0)},
            "metadata": metadata,
        }
        if is_luxian_wrapper:
            response_data = _normalize_luxian_single_test_result(response_data, req.medical_text)

        return success_response(
            data=response_data,
            message="规则测试完成",
            trace_id=get_trace_id(request)
        )
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        traceback.print_exc()
        return error_response(
            code=ErrorCode.INTERNAL_ERROR,
            message=f"规则测试失败: {str(e)}",
            trace_id=get_trace_id(request)
        )

# ==================== 提示词管理接口（仅系统管理员） ====================

class UpdatePromptRequest(BaseModel):
    custom_prompt: Optional[str] = None


class RuleVersionActionRequest(BaseModel):
    version_no: int
    reason: Optional[str] = None


class RuleRegistryBootstrapRequest(BaseModel):
    mark_published: bool = True


@router.get("/rules/source")
async def get_rule_source(
    request: Request,
    qc_service: SichuanQCService = Depends(get_qc_service),
):
    """
    获取当前四川规则来源与版本摘要（PG 治理表 / JSON 回退）。
    """
    try:
        overview = qc_service.get_rule_source_overview()
        return success_response(
            data=overview,
            message="获取规则来源成功",
            trace_id=get_trace_id(request),
        )
    except Exception as e:
        return error_response(
            code=ErrorCode.INTERNAL_ERROR,
            message=f"获取规则来源失败: {str(e)}",
            trace_id=get_trace_id(request),
        )


@router.get("/rules/consistency-check")
async def check_rule_consistency(
    request: Request,
    include_custom_rules: bool = Query(default=True),
    sample_limit: int = Query(default=100, ge=10, le=500),
    admin_user: dict = Depends(require_admin),
    qc_service: SichuanQCService = Depends(get_qc_service),
):
    """
    发布前后规则一致性校验：
    对比治理表 active 规则与本地基线 JSON（SC + 可选 LX/LXE）。
    """
    try:
        result = qc_service.check_rule_registry_consistency(
            include_custom_rules=bool(include_custom_rules),
            sample_limit=sample_limit,
        )
        return success_response(
            data=result,
            message="规则一致性校验完成",
            trace_id=get_trace_id(request),
        )
    except Exception as e:
        return error_response(
            code=ErrorCode.INTERNAL_ERROR,
            message=f"规则一致性校验失败: {str(e)}",
            trace_id=get_trace_id(request),
        )


@router.post("/rules/bootstrap")
async def bootstrap_rules_to_registry(
    request: Request,
    req: RuleRegistryBootstrapRequest,
    admin_user: dict = Depends(require_admin),
    qc_service: SichuanQCService = Depends(get_qc_service),
):
    """
    将本地 JSON 规则（SC + LX/LXE）增量导入治理表（幂等）。
    """
    try:
        result = await qc_service.bootstrap_rule_registry(
            operator=_current_user_id(admin_user),
            mark_published=bool(req.mark_published),
        )
        return success_response(
            data=result,
            message="规则导入治理表完成",
            trace_id=get_trace_id(request),
        )
    except Exception as e:
        return error_response(
            code=ErrorCode.INTERNAL_ERROR,
            message=f"规则导入治理表失败: {str(e)}",
            trace_id=get_trace_id(request),
        )


@router.get("/rules/{rule_id}/versions")
async def list_rule_versions(
    request: Request,
    rule_id: str,
    limit: int = Query(default=20, ge=1, le=200),
    admin_user: dict = Depends(require_admin),
    qc_service: SichuanQCService = Depends(get_qc_service),
):
    try:
        versions = qc_service.list_rule_versions(rule_id=rule_id, limit=limit)
        return success_response(
            data={
                "rule_id": rule_id,
                "items": versions,
                "total": len(versions),
            },
            message="获取规则版本成功",
            trace_id=get_trace_id(request),
        )
    except Exception as e:
        return error_response(
            code=ErrorCode.INTERNAL_ERROR,
            message=f"获取规则版本失败: {str(e)}",
            trace_id=get_trace_id(request),
        )


@router.get("/rules/{rule_id}/publish-history")
async def list_rule_publish_history(
    request: Request,
    rule_id: str,
    limit: int = Query(default=50, ge=1, le=500),
    admin_user: dict = Depends(require_admin),
    qc_service: SichuanQCService = Depends(get_qc_service),
):
    try:
        history = qc_service.list_rule_publish_history(rule_id=rule_id, limit=limit)
        return success_response(
            data={
                "rule_id": rule_id,
                "items": history,
                "total": len(history),
            },
            message="获取发布历史成功",
            trace_id=get_trace_id(request),
        )
    except Exception as e:
        return error_response(
            code=ErrorCode.INTERNAL_ERROR,
            message=f"获取发布历史失败: {str(e)}",
            trace_id=get_trace_id(request),
        )


@router.post("/rules/{rule_id}/publish")
async def publish_rule_version(
    request: Request,
    rule_id: str,
    req: RuleVersionActionRequest,
    admin_user: dict = Depends(require_admin),
    qc_service: SichuanQCService = Depends(get_qc_service),
):
    try:
        ok = qc_service.publish_rule_version(
            rule_id=rule_id,
            version_no=req.version_no,
            operator=_current_user_id(admin_user),
            reason=str(req.reason or "manual publish"),
        )
        if not ok:
            raise HTTPException(status_code=404, detail=f"规则版本不存在或发布失败: {rule_id} v{req.version_no}")
        return success_response(
            data={"rule_id": rule_id, "version_no": req.version_no},
            message="发布规则版本成功",
            trace_id=get_trace_id(request),
        )
    except HTTPException:
        raise
    except Exception as e:
        return error_response(
            code=ErrorCode.INTERNAL_ERROR,
            message=f"发布规则版本失败: {str(e)}",
            trace_id=get_trace_id(request),
        )


@router.post("/rules/{rule_id}/rollback")
async def rollback_rule_version(
    request: Request,
    rule_id: str,
    req: RuleVersionActionRequest,
    admin_user: dict = Depends(require_admin),
    qc_service: SichuanQCService = Depends(get_qc_service),
):
    try:
        ok = qc_service.rollback_rule_version(
            rule_id=rule_id,
            version_no=req.version_no,
            operator=_current_user_id(admin_user),
            reason=str(req.reason or "manual rollback"),
        )
        if not ok:
            raise HTTPException(status_code=404, detail=f"规则版本不存在或回滚失败: {rule_id} v{req.version_no}")
        return success_response(
            data={"rule_id": rule_id, "version_no": req.version_no},
            message="回滚规则版本成功",
            trace_id=get_trace_id(request),
        )
    except HTTPException:
        raise
    except Exception as e:
        return error_response(
            code=ErrorCode.INTERNAL_ERROR,
            message=f"回滚规则版本失败: {str(e)}",
            trace_id=get_trace_id(request),
        )


@router.get("/rules/{rule_id}/prompt")
async def get_rule_prompt(
    request: Request,
    rule_id: str,
    admin_user: dict = Depends(require_admin),
    qc_service: SichuanQCService = Depends(get_qc_service)
):
    """
    获取规则的提示词（仅系统管理员）

    Args:
        rule_id: 规则ID（如 "SC-010"）
        admin_user: 管理员用户（由 require_admin 依赖注入）

    Returns:
        规则的提示词（自定义或默认）
    """
    try:
        # 获取规则
        rule = qc_service.get_rule_by_id(rule_id)
        if not rule:
            raise HTTPException(
                status_code=404,
                detail=f"未找到规则 ID: {rule_id}"
            )

        # 获取自定义提示词或返回默认提示词标记
        custom_prompt = rule.get("custom_prompt")

        # 构建默认提示词（与 test_rule 中的一致）
        default_prompt = f"""你是一名经验丰富的病历质控专家，具有丰富的临床经验和质控标准知识。

请根据以下质控规则，对病历文本进行全面、深入的质控评估。

**质控规则信息：**
- 规则ID: {rule.get('rule_id')}
- 规则名称: {rule.get('name')}
- 规则描述: {rule.get('description')}
- 适用文书: {', '.join(rule.get('applicable_documents', []))}
- 缺陷级别: {rule.get('defect_level')}
- 复杂度: {rule.get('complexity')}

**病历文本：**
{{medical_text}}

**评估要求（请从以下多个维度进行全面分析）：**

1. **时间一致性**：检查主诉时间与现病史时间节点是否匹配，是否存在时间逻辑错误

2. **症状完整性**：验证主诉中的所有症状是否在现病史中得到详细描述和阐述

3. **症状矛盾性**：⚠️ 重点检查现病史中是否存在明确否定主诉症状的表述
   - 例如：主诉"胸痛"，但现病史中出现"无胸痛"、"否认胸痛"等否定表述
   - 这种明确的矛盾是严重的质控缺陷

4. **系统一致性**：分析主诉症状、现病史描述、入院诊断是否涉及同一器官系统
   - 例如：主诉为心血管症状，现病史却主要描述消化系统问题，诊断又是心血管疾病
   - 检查是否存在跨系统的逻辑错误

5. **诊断支撑性**：评估现病史是否为入院诊断提供了充分的临床证据
   - 诊断依据是否充分
   - 病史描述是否支持诊断结论

6. **逻辑闭环性**：验证"主诉 → 现病史 → 入院诊断"是否形成完整、合理的逻辑链条
   - 三者之间是否存在逻辑断裂
   - 是否存在多维度的不一致

**分析方法：**
- 逐字逐句仔细阅读病历文本
- 特别注意否定词："无"、"否认"、"未见"、"未诉"等
- 识别症状所属的器官系统（如心血管系统、消化系统、呼吸系统等）
- 评估时间线的合理性和连贯性
- 综合判断整体逻辑的一致性

**输出格式（JSON）：**
{{{{
  "is_compliant": true/false,
  "findings": "详细描述发现的所有问题，包括时间矛盾、症状否定矛盾、系统不一致、诊断支撑不足等各个维度的问题。如果合规则说明符合哪些要求",
  "evidence": "从病历中提取的相关文本片段，特别要引用包含否定词、时间信息、诊断信息的关键句子",
  "suggestion": "针对发现的问题提供改进建议，如果合规可以为空",
  "confidence": 0.85
}}}}

请直接输出 JSON，不要包含其他文字："""

        return success_response(
            data={
                "rule_id": rule_id,
                "has_custom_prompt": custom_prompt is not None,
                "prompt": custom_prompt if custom_prompt else default_prompt,
                "is_default": custom_prompt is None
            },
            message="获取提示词成功",
            trace_id=get_trace_id(request)
        )

    except HTTPException:
        raise
    except Exception as e:
        import traceback
        traceback.print_exc()
        return error_response(
            code=ErrorCode.INTERNAL_ERROR,
            message=f"获取提示词失败: {str(e)}",
            trace_id=get_trace_id(request)
        )


@router.put("/rules/{rule_id}/prompt")
async def update_rule_prompt(
    request: Request,
    rule_id: str,
    req: UpdatePromptRequest,
    admin_user: dict = Depends(require_admin),
    qc_service: SichuanQCService = Depends(get_qc_service)
):
    """
    更新规则的自定义提示词（仅系统管理员）

    Args:
        rule_id: 规则ID
        req: 包含 custom_prompt 的请求体（None 表示恢复默认）
        admin_user: 管理员用户

    Returns:
        更新结果
    """
    try:
        # 更新提示词
        success = qc_service.update_rule_prompt(
            rule_id,
            req.custom_prompt,
            operator=_current_user_id(admin_user),
        )

        if not success:
            raise HTTPException(
                status_code=404,
                detail=f"未找到规则 ID: {rule_id}"
            )

        action = "恢复为默认提示词" if req.custom_prompt is None else "更新自定义提示词"

        return success_response(
            data={
                "rule_id": rule_id,
                "has_custom_prompt": req.custom_prompt is not None
            },
            message=f"{action}成功",
            trace_id=get_trace_id(request)
        )

    except HTTPException:
        raise
    except Exception as e:
        import traceback
        traceback.print_exc()
        return error_response(
            code=ErrorCode.INTERNAL_ERROR,
            message=f"更新提示词失败: {str(e)}",
            trace_id=get_trace_id(request)
        )


@router.post("/reload-config")
async def reload_llm_config(
    request: Request,
    config_name: str = Query(default="default"),
    user_id: Optional[str] = Query(default=None)
):
    """
    重新加载 LLM 配置（从数据库）

    当前端修改了 LLM 配置后，调用此接口让四川质控服务重新加载配置
    无需重启后端服务

    Args:
        config_name: 配置名称，默认为 "default"
        user_id: 用户 ID，如果为 None 则加载全局配置

    Returns:
        重新加载结果
    """
    try:
        qc_service = await get_qc_service()
        success = await qc_service.reload_config(config_name, user_id)

        if success:
            return success_response(
                data={
                    "config_name": config_name,
                    "user_id": user_id,
                    "current_model": qc_service.client.model,
                    "config_source": qc_service.client.config_source,
                    "reloaded_at": datetime.now(timezone.utc).isoformat()
                },
                message="LLM 配置重新加载成功",
                trace_id=get_trace_id(request)
            )
        else:
            return error_response(
                code=ErrorCode.INTERNAL_ERROR,
                message="LLM 配置重新加载失败",
                trace_id=get_trace_id(request)
            )
    except Exception as e:
        import traceback
        traceback.print_exc()
        return error_response(
            code=ErrorCode.INTERNAL_ERROR,
            message=f"重新加载配置失败: {str(e)}",
            trace_id=get_trace_id(request)
        )


@router.get("/current-config")
async def get_current_config(request: Request):
    """
    获取当前使用的 LLM 配置信息

    Returns:
        当前配置信息
    """
    try:
        qc_service = await get_qc_service()
        return success_response(
            data={
                "model": qc_service.client.model,
                "api_endpoint": qc_service.client.api_endpoint,
                "config_source": qc_service.client.config_source,
                "timeout_seconds": qc_service.client.timeout_seconds,
                "stats": qc_service.client.stats()
            },
            message="获取当前配置成功",
            trace_id=get_trace_id(request)
        )
    except Exception as e:
        return error_response(
            code=ErrorCode.INTERNAL_ERROR,
            message=f"获取当前配置失败: {str(e)}",
            trace_id=get_trace_id(request)
        )
