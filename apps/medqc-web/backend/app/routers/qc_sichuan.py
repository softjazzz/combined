from typing import List, Dict, Any, Literal, Optional, Sequence

import asyncio
import uuid
import json
import hashlib
import logging
import os
import stat
from pathlib import Path
from pydantic import BaseModel, ValidationError
from fastapi import APIRouter, Body, HTTPException, Query, Request, Depends
from fastapi.responses import Response, StreamingResponse
from starlette.concurrency import run_in_threadpool
from datetime import datetime, timedelta, timezone

from ..services.luxian_0609.phase_scope import get_luxian_0609_acceptance_only_rule_ids
from ..services.sample_validation_rule_sets import get_luxian_0609_customer_delivery_rule_ids
from ..core.response import success_response, error_response, get_trace_id, ErrorCode, StatusCode
from ..core.audit import audit_event
from ..services.sichuan_qc_service import SichuanQCService
from ..services.llm_config_loader import LLMConfigLoader
from ..services.qc_input_adapters import evaluate_running_final_bundle
from ..services.fast_screen_qc import (
    normalize_execution_strategy,
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
    review_luxian_0609_batch_job,
)
from ..services.luxian_0609_rule_catalog import attach_luxian_0609_customer_policy
from ..services.sc_rule_launch_tier import (
    load_sc_intrinsic_launch_tier_map,
    resolve_sc_intrinsic_launch_tier,
)
from ..core.supabase_client import get_supabase
from ..core.settings import get_settings
from ..core.security import require_admin, require_roles, get_current_user
from ..services.product_activation import require_product_activation
from ..services.custom_qc_workspace_service import (
    CustomQCWorkspaceService,
    LX0609_CUSTOMER_RESULT_CONTRACT_ERROR,
    customer_safe_projection_key,
    project_customer_safe_batch_job,
)
from ..services.luxian_0609_result_export_service import (
    export_filtered_record_results_workbook,
    export_single_record_result_html,
)
from ..services.custom_qc_sample_pool_service import CustomQCSamplePoolService
from ..services.luxian_0609.remediation_draft import generate_remediation_draft
from ..schemas.qc_sichuan import QcResultFeedbackRequest
from ..services.qc_workspace.result_feedback_demo_store import (
    ResultFeedbackDemoConflict,
    ResultFeedbackDemoNotFound,
    ResultFeedbackDemoStore,
    ResultFeedbackDemoStoreUnavailable,
    contains_sensitive_feedback_text,
)
from ..services.case_identity import CaseRef, case_refs_from_records
from ..services.luxian_0609.evaluation_horizon import (
    build_record_evaluation_horizon_snapshot,
)
from ..services.luxian_0609.surgery_procedure_catalog import (
    CATALOG_VERSION as SURGERY_PROCEDURE_CATALOG_VERSION,
    OPERATION_CATEGORIES,
    SURGERY_CATEGORY,
    load_surgery_procedure_catalog,
)
from ..services.luxian_0609.rule_decision_settings import (
    assert_luxian_0609_customer_native_delivery_ready,
    capture_luxian_0609_task_settings,
    capture_luxian_0609_task_runtime,
    LX0609_TASK_SETTINGS_FILTER_KEY,
    LX0609_TASK_RUNTIME_FILTER_KEY,
    resolve_mainline_rule_decision_settings,
)
from ..services.luxian_0609.native_package import (
    assert_luxian_0609_formal_package_plan_native_only,
)
from ..services.luxian_0609.phase_scope import partition_luxian_0609_rule_scope
from ..services.sample_validation_rule_sets import (
    LUXIAN_0609_CUSTOMER_EXCLUDED_RULE_IDS,
    LUXIAN_0916_QC_RULE_SET_KEY,
    is_workspace_batch_draft_id,
)
from ..services.sichuan_workspace_batch_worker import (
    _assert_luxian_0609_formal_customer_rule_ids,
    _luxian_0609_rollback_rule_ids,
    _enforce_sc_source_guard,
    _resolve_workspace_bundle_scene,
    _normalize_quality_profile,
    _normalize_bucket_strategy,
    _normalize_refine_threshold,
    _normalize_batch_output_mode,
    _normalize_max_refine_candidates,
    _normalize_run_mode,
    _build_record_status_counts as _build_record_status_counts,
    _build_result_performance_profile,
    _sanitize_trace_value,
    _result_diagnostic_trace,
    run_sichuan_workspace_batch_job,
)

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
        record_ref = CaseRef.from_mapping(record)
        normalized_record_scene = str(record.get("scope") or "").strip().lower()
        record_scene = (
            normalized_record_scene
            if normalized_record_scene in {"running", "final"}
            else "unknown"
        )
        snapshot.append(
            {
                "record_id": record_id,
                **(
                    {
                        **record_ref.as_dict(),
                        "record_key": record_ref.as_key(),
                    }
                    if all(record_ref)
                    else {}
                ),
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
    return sorted(snapshot, key=lambda item: item.get("record_key") or item["record_id"])


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
    diagnostic_capture: bool = False
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
    sync_scope: Literal["all", "today_inpatient"] = "all"
    department: Optional[str] = None
    doctor: Optional[str] = None
    date_field: str = "discharge"
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    keyword: Optional[str] = None
    record_ids: Optional[List[str]] = None
    record_refs: Optional[List[Dict[str, str]]] = None
    run_mode: Optional[str] = None


class Luxian0609RecordResultExportRequest(BaseModel):
    scope: Literal["all", "running", "final"] = "all"
    department: Optional[str] = None
    doctor: Optional[str] = None
    date_field: Literal["visit", "admission", "discharge"] = "admission"
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    keyword: Optional[str] = None
    record_refs: Optional[List[Dict[str, str]]] = None


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


_SAVED_QC_RESULT_ADMIN_ROLES = {"admin", "sync_admin", "super_admin"}


def _saved_qc_results_directory() -> Path:
    """文件型历史质控结果的唯一存储根目录。"""

    return Path(__file__).resolve().parent.parent / "storage" / "qc_results"


def _normalize_saved_qc_result_id(value: str) -> str:
    """仅接受服务端生成的规范 UUID，杜绝把路由参数当作路径或 glob。"""

    normalized = str(value or "").strip().lower()
    try:
        parsed = str(uuid.UUID(normalized))
    except (TypeError, ValueError, AttributeError) as exc:
        raise HTTPException(status_code=404, detail="质控结果不存在") from exc
    if parsed != normalized:
        raise HTTPException(status_code=404, detail="质控结果不存在")
    return parsed


def _can_read_all_saved_qc_results(current_user: Optional[Dict[str, Any]]) -> bool:
    return bool(_extract_user_roles(current_user).intersection(_SAVED_QC_RESULT_ADMIN_ROLES))


def _can_read_saved_qc_result(data: Dict[str, Any], current_user: Dict[str, Any]) -> bool:
    if _can_read_all_saved_qc_results(current_user):
        return True
    owner_id = str(data.get("created_by") or "").strip()
    return bool(owner_id) and owner_id == _current_user_id(current_user)


def _saved_qc_result_payload(data: Dict[str, Any]) -> Dict[str, Any]:
    """兼容历史空值，避免保存了 ``payload: null`` 的旧文件导致读取 500。"""

    payload = data.get("payload")
    return payload if isinstance(payload, dict) else {}


def _saved_qc_result_model(data: Dict[str, Any]) -> Optional[str]:
    payload = _saved_qc_result_payload(data)
    evaluation_summary = payload.get("evaluation_summary")
    evaluation_summary = evaluation_summary if isinstance(evaluation_summary, dict) else {}
    llm_info = payload.get("llm_info") or data.get("llm_info") or {}
    llm_info = llm_info if isinstance(llm_info, dict) else {}
    return data.get("model") or evaluation_summary.get("model") or llm_info.get("model")


def _is_saved_qc_result_file_within_directory(filepath: Path, base_dir: Path) -> bool:
    try:
        # 结果目录内的符号链接或 Windows 重解析点也不得作为可读取结果入口，
        # 即使其解析后仍落在目录内。
        file_stat = filepath.lstat()
        if filepath.is_symlink() or (
            getattr(file_stat, "st_file_attributes", 0) & stat.FILE_ATTRIBUTE_REPARSE_POINT
        ):
            return False
        return stat.S_ISREG(file_stat.st_mode) and filepath.parent.resolve() == base_dir.resolve()
    except OSError:
        return False


def _saved_qc_result_file_identity(file_stat: os.stat_result) -> tuple[int, int]:
    """返回打开前后必须保持一致的目录项身份。"""

    return (file_stat.st_dev, file_stat.st_ino)


def _read_saved_qc_result_file(filepath: Path, base_dir: Path) -> Any:
    """从已绑定身份的描述符读取历史结果，阻止检查后路径被替换。

    ``detail``、``history``、``latest`` 共用这一边界：先拒绝链接、重解析点、
    非普通文件和目录外路径；随后以 ``lstat -> open -> fstat/lstat`` 绑定初始
    目录项、打开描述符和当前目录项为同一文件，最后才解析 JSON。
    """

    initial_stat = filepath.lstat()
    if filepath.is_symlink() or (
        getattr(initial_stat, "st_file_attributes", 0) & stat.FILE_ATTRIBUTE_REPARSE_POINT
    ):
        raise OSError("历史质控结果不允许使用链接或重解析点")
    if not stat.S_ISREG(initial_stat.st_mode):
        raise OSError("历史质控结果必须是普通文件")
    if filepath.parent.resolve() != base_dir.resolve():
        raise OSError("历史质控结果位于存储目录之外")

    open_flags = os.O_RDONLY
    if hasattr(os, "O_NOFOLLOW"):
        open_flags |= os.O_NOFOLLOW
    file_descriptor = os.open(filepath, open_flags)
    try:
        opened_stat = os.fstat(file_descriptor)
        current_stat = filepath.lstat()
        if filepath.is_symlink() or (
            getattr(current_stat, "st_file_attributes", 0) & stat.FILE_ATTRIBUTE_REPARSE_POINT
        ):
            raise OSError("历史质控结果在读取期间变为链接或重解析点")
        if not stat.S_ISREG(opened_stat.st_mode) or not stat.S_ISREG(current_stat.st_mode):
            raise OSError("历史质控结果在读取期间不再是普通文件")
        initial_identity = _saved_qc_result_file_identity(initial_stat)
        if (
            _saved_qc_result_file_identity(opened_stat) != initial_identity
            or _saved_qc_result_file_identity(current_stat) != initial_identity
        ):
            raise OSError("历史质控结果在读取期间被替换")

        with os.fdopen(file_descriptor, "r", encoding="utf-8", closefd=False) as file:
            return json.load(file)
    finally:
        os.close(file_descriptor)


def _saved_qc_result_sort_mtime(filepath: Path) -> float:
    """排序不得跟随链接；并发消失的目录项排到末尾后由受控读取跳过。"""

    try:
        return filepath.lstat().st_mtime
    except OSError:
        return float("-inf")


def _load_saved_qc_result_by_id(result_id: str) -> Optional[Dict[str, Any]]:
    """在唯一根目录内按规范 UUID 精确定位，不使用用户输入拼接路径。"""

    base_dir = _saved_qc_results_directory()
    if not base_dir.exists():
        return None
    candidates = [base_dir / f"{result_id}.json"]
    candidates.extend(
        sorted(
            base_dir.glob(f"{result_id}_*.json"),
            key=_saved_qc_result_sort_mtime,
            reverse=True,
        )
    )
    for candidate in candidates:
        try:
            data = _read_saved_qc_result_file(candidate, base_dir)
        except (OSError, json.JSONDecodeError) as exc:
            logger.warning("读取质控结果文件失败 %s: %s", candidate, exc)
            continue
        if not isinstance(data, dict):
            continue
        if str(data.get("id") or "").strip().lower() == result_id:
            return data
    return None


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


def _project_customer_safe_batch_job_or_409(job: Dict[str, Any]) -> Dict[str, Any]:
    try:
        return project_customer_safe_batch_job(
            job,
            hmac_key=customer_safe_projection_key(),
        )
    except ValueError as exc:
        if str(exc) != LX0609_CUSTOMER_RESULT_CONTRACT_ERROR:
            raise
        raise HTTPException(
            status_code=409,
            detail="历史质控结果交付合同不完整，无法安全展示",
        ) from exc


def _hydrate_luxian_canonical_batch_job_or_409(
    *, workspace: Any, job: Dict[str, Any]
) -> Dict[str, Any]:
    """详情读取只消费通过 Envelope 校验的 Canonical 结果。"""

    status = str(job.get("status") or "").strip().lower()
    summary = job.get("summary") if isinstance(job.get("summary"), dict) else {}
    allow_partial = (
        status == "failed"
        and str(summary.get("execution_status") or "").strip().lower() == "partial_failed"
    )
    if status != "completed" and not allow_partial:
        return job
    try:
        canonical_items = workspace._load_batch_job_canonical_items(
            job=job,
            allow_partial=allow_partial,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=409,
            detail="批量质控 Canonical 结果不完整，无法安全展示",
        ) from exc
    hydrated = dict(job)
    hydrated["items"] = canonical_items
    hydrated["rule_results"] = []
    hydrated_summary = dict(hydrated.get("summary") or {})
    hydrated_summary.pop("rule_results", None)
    hydrated["summary"] = hydrated_summary
    hydrated["children"] = []
    hydrated["child_jobs"] = []
    return hydrated


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
        safe_job = _project_customer_safe_batch_job_or_409(job)
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


def _project_luxian_0916_shared_job(job: Dict[str, Any]) -> Dict[str, Any]:
    """共享只读视图仅移除任务私有元数据，0916 规则结果字段保持原样。"""

    response = dict(_workspace_batch_response_item(job))
    for private_key in ("created_by", "filters", "rule_results", "children", "child_jobs"):
        response.pop(private_key, None)
    response["read_only"] = True
    return response












def _normalize_scope(scope: Optional[str]) -> str:
    value = str(scope or "").strip().lower()
    if value not in {"all", "running", "final"}:
        return "all"
    return value


def _normalize_date_field(date_field: Optional[str]) -> str:
    value = str(date_field or "").strip().lower()
    if value not in {"visit", "admission", "discharge"}:
        return "admission"
    return value
























































def _debug_evidence_projection(item: Dict[str, Any]) -> Dict[str, Any]:
    """为调试快照保留两种结构化证据字段，并避免投影时丢失定位信息。"""

    projected = dict(item)
    evidence_items = item.get("evidence_items")
    customer_evidence = item.get("customer_evidence")
    canonical = evidence_items if isinstance(evidence_items, list) else []
    customer = customer_evidence if isinstance(customer_evidence, list) else []
    generic_evidence = item.get("evidence")
    if not canonical and not customer and isinstance(generic_evidence, list):
        canonical = generic_evidence
        customer = generic_evidence
    # Canonical 结果和客户 Envelope 的历史任务可能只保存其中一侧；
    # 调试快照补齐缺失侧，但不改写已有数组或业务状态。
    if not canonical and customer:
        canonical = customer
    if not customer and canonical:
        customer = canonical
    removed_keys: set[str] = set()
    projected["evidence_items"] = _sanitize_trace_value(canonical, removed_keys)
    projected["customer_evidence"] = _sanitize_trace_value(customer, removed_keys)
    return projected


def _debug_snapshot_items(job: Dict[str, Any]) -> List[Dict[str, Any]]:
    """按批量任务真实结果来源收集调试条目（父任务优先使用子任务）。"""

    children = [
        child
        for child in list(job.get("child_jobs") or job.get("children") or [])
        if isinstance(child, dict)
    ]
    sources = children or [job]
    items: List[Dict[str, Any]] = []
    for source in sources:
        items.extend(item for item in list(source.get("items") or []) if isinstance(item, dict))
    if not items:
        # 兼容尚未把 rule_results 展平到 items_json 的历史任务。
        for source in sources:
            for rule_result in list(source.get("rule_results") or []):
                if isinstance(rule_result, dict):
                    for raw_item in list(rule_result.get("items") or []):
                        if not isinstance(raw_item, dict):
                            continue
                        item = dict(raw_item)
                        item.setdefault("rule_job_id", rule_result.get("id"))
                        item.setdefault("rule_code", rule_result.get("rule_code"))
                        item.setdefault("rule_name", rule_result.get("rule_name"))
                        items.append(item)
    if not items:
        summary = job.get("summary") if isinstance(job.get("summary"), dict) else {}
        for rule_result in list(summary.get("rule_results") or []):
            if isinstance(rule_result, dict):
                for raw_item in list(rule_result.get("items") or []):
                    if not isinstance(raw_item, dict):
                        continue
                    item = dict(raw_item)
                    item.setdefault("rule_job_id", rule_result.get("id"))
                    item.setdefault("rule_code", rule_result.get("rule_code"))
                    item.setdefault("rule_name", rule_result.get("rule_name"))
                    items.append(item)
    return [_debug_evidence_projection(item) for item in items]


_DEBUG_SNAPSHOT_SUMMARY_FIELDS = (
    "rule_set_key",
    "rule_set_name",
    "rule_set_version",
    "execution_status",
    "execution_strategy",
    "quality_profile",
    "bucket_strategy",
    "batch_output_mode",
    "run_mode",
    "progress",
    "status_breakdown",
    "record_status_breakdown",
    "executor_breakdown",
    "cache_breakdown",
    "cot_summary",
    "automatic_failed_rule_retry",
    "refine_summary",
    "total_records",
    "success_count",
    "failed_count",
    "failed_record_count",
    "issue_records",
    "compliant_records",
    "not_applicable_records",
    "uncertain_records",
    "data_quality_gap_count",
    "rejected_by_system_count",
    "technical_error_internal_count",
    "semantic_llm_call_count",
    "semantic_extraction_invalid_count",
    "semantic_extraction_failures",
    "total_tokens",
    "total_prompt_tokens",
    "total_completion_tokens",
    "total_processing_time",
    "wall_clock_time",
    "first_result_latency",
    "completed_rule_count",
    "failed_rule_count",
    "retry_status",
    "retry_attempt",
    "retry_pending_count",
    "retry_remaining_count",
    "retry_recovered_count",
    "updated_at",
)


def _debug_snapshot_summary(job: Dict[str, Any]) -> Dict[str, Any]:
    """只返回调试页消费的汇总，避免把规则结果和逐病例性能明细重复传输。"""

    summary = job.get("summary") if isinstance(job.get("summary"), dict) else {}
    removed_keys: set[str] = set()
    return {
        field: _sanitize_trace_value(summary[field], removed_keys)
        for field in _DEBUG_SNAPSHOT_SUMMARY_FIELDS
        if field in summary
    }


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
    all_items = _debug_snapshot_items(job)
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
        "summary": _debug_snapshot_summary(job),
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


def _can_export_record_results(current_user: Optional[Dict[str, Any]]) -> bool:
    if not current_user:
        return False
    return bool(
        _extract_user_roles(current_user).intersection(
            {"admin", "qc_manager", "sync_admin", "super_admin"}
        )
    )




def _trace_pick(item: Dict[str, Any], keys: List[str]) -> Dict[str, Any]:
    return {key: item.get(key) for key in keys if key in item and item.get(key) is not None}




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


def get_result_feedback_demo_store() -> ResultFeedbackDemoStore:
    """反馈演示版 Store 依赖。

    这里不在应用启动时访问反馈表；表未迁移时只在反馈请求期间返回 503，
    保证质控结果读取链不被新功能拖垮。
    """

    return ResultFeedbackDemoStore()


def _project_demo_feedback_record_context(
    items: Sequence[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    identities: Dict[tuple[str, str, str], Dict[str, str]] = {}
    for item in items:
        identity = item.get("_record_identity")
        if not isinstance(identity, dict):
            continue
        key = (
            str(identity.get("institute_id") or "").strip(),
            str(identity.get("patient_id") or "").strip(),
            str(identity.get("visit_id") or "").strip(),
        )
        if all(key):
            identities[key] = {
                "institute_id": key[0],
                "patient_id": key[1],
                "visit_id": key[2],
            }

    records_by_identity: Dict[tuple[str, str, str], Dict[str, Any]] = {}
    if identities:
        try:
            records = _sichuan_workspace_service().collect_records(
                scope="all",
                department=None,
                doctor=None,
                date_field="admission",
                start_date=None,
                end_date=None,
                keyword=None,
                record_refs=list(identities.values()),
            )
        except Exception:
            logger.warning("读取质控反馈病例展示信息失败", exc_info=True)
            records = []
        for record in records:
            key = (
                str(record.get("institute_id") or "").strip(),
                str(record.get("patient_id") or "").strip(),
                str(record.get("visit_id") or record.get("record_id") or "").strip(),
            )
            if all(key):
                records_by_identity[key] = record

    projected: List[Dict[str, Any]] = []
    for item in items:
        identity = item.get("_record_identity")
        identity_key = (
            str(identity.get("institute_id") or "").strip(),
            str(identity.get("patient_id") or "").strip(),
            str(identity.get("visit_id") or "").strip(),
        ) if isinstance(identity, dict) else ("", "", "")
        record = records_by_identity.get(identity_key, {})
        visit_id = str(record.get("visit_id") or identity_key[2] or "").strip()
        safe_item = {
            key: value
            for key, value in item.items()
            if not str(key).startswith("_")
        }
        safe_item.update(
            {
                "patient_name": str(record.get("patient_name") or "").strip(),
                "record_number": str(
                    record.get("inpat_no")
                    or record.get("mr_no")
                    or visit_id
                    or ""
                ).strip(),
                "visit_id": visit_id,
                "department": str(record.get("department") or "").strip(),
                "care_phase": str(record.get("scope") or "").strip(),
            }
        )
        projected.append(safe_item)
    return projected


def _require_demo_feedback_account(current_user: Dict[str, Any]) -> Dict[str, Any]:
    """只允许固定功能演示账号，不能仅凭 admin 角色放行。"""

    user_id = str(current_user.get("id") or current_user.get("user_id") or "").strip()
    email = str(current_user.get("email") or "").strip().lower()
    if user_id != "admin-001" or email != "admin@medqc.com":
        raise HTTPException(status_code=403, detail="当前账号不支持质控结果反馈演示")
    return current_user


def _parse_demo_feedback_payload(body: Dict[str, Any]) -> QcResultFeedbackRequest:
    """把校验错误收敛为安全文案，避免 422 回显用户输入。"""

    try:
        payload = QcResultFeedbackRequest.model_validate(body)
    except ValidationError as exc:
        raise HTTPException(status_code=400, detail="反馈参数不符合要求") from exc
    if contains_sensitive_feedback_text(payload.comment):
        raise HTTPException(status_code=400, detail="说明中不能填写患者身份或联系方式")
    return payload


def _raise_demo_feedback_store_error(exc: Exception) -> None:
    if isinstance(exc, ResultFeedbackDemoStoreUnavailable):
        raise HTTPException(status_code=503, detail="反馈功能暂不可用") from exc
    if isinstance(exc, ResultFeedbackDemoNotFound):
        raise HTTPException(status_code=404, detail="质控结果不存在") from exc
    if isinstance(exc, ResultFeedbackDemoConflict):
        raise HTTPException(status_code=409, detail="质控结果无法唯一确认") from exc
    raise exc


def _shared_sample_pool_service() -> CustomQCSamplePoolService:
    return CustomQCSamplePoolService()


_SHARED_SAMPLE_JOB_READ_ROLES = frozenset({"admin", "qc_manager", "sync_admin"})
_SHARED_SAMPLE_JOB_SOURCES = frozenset(
    {"manual_problem_sample_pool", "manual_sample_formal_fast_screen_full"}
)


def _resolve_shared_sample_pool_latest_job(
    *,
    workspace: CustomQCWorkspaceService,
    job_id: str,
    current_user: Dict[str, Any],
) -> Optional[Dict[str, Any]]:
    if not _extract_user_roles(current_user).intersection(_SHARED_SAMPLE_JOB_READ_ROLES):
        return None
    resolved = _shared_sample_pool_service().resolve_unique_pool_id_for_latest_job(
        job_id=job_id
    )
    if not resolved:
        return None
    pool_id, job_created_by = resolved
    job = workspace.get_batch_job(job_id=job_id, created_by=job_created_by)
    if not _is_workspace_batch_job(job):
        return None
    filters = job.get("filters") if isinstance(job.get("filters"), dict) else {}
    if str(filters.get("sample_pool_id") or "").strip() != pool_id:
        return None
    source = str(filters.get("source") or "").strip().lower()
    if source not in _SHARED_SAMPLE_JOB_SOURCES:
        return None
    return job


async def _run_sichuan_workspace_batch_job(job_id: str) -> None:
    from ..services.qc_diagnostics.support_store import capture_for_job, finalize
    workspace = _sichuan_workspace_service()
    capture = capture_for_job(workspace, job_id)
    try:
        get_batch_job_for_processing = getattr(workspace, "get_batch_job_for_processing", None)
        job = (
            get_batch_job_for_processing(job_id=job_id)
            if callable(get_batch_job_for_processing)
            else {}
        )
        filters = job.get("filters") if isinstance(job, dict) and isinstance(job.get("filters"), dict) else {}
        if str(filters.get("rule_set_key") or "").strip() == LUXIAN_0916_QC_RULE_SET_KEY:
            from ..services.luxian_0916.batch_worker import run_luxian_0916_batch_job

            qc_service = await get_qc_service()
            await run_luxian_0916_batch_job(
                job_id,
                workspace=workspace,
                # 0916 每份病历只发一次受控语义提取请求，直接复用系统全局
                # HTTP 槽位；不再维护质控集专属的并发配置。
                max_record_concurrency=qc_service.client.http_max_concurrency,
            )
        else:
            await run_sichuan_workspace_batch_job(
                job_id, workspace=workspace, qc_service_provider=get_qc_service,
                diagnostic_capture=capture,
            )
    finally:
        if capture is not None:
            finalize(job_id)


def resume_queued_luxian_0609_workspace_jobs() -> int:
    """应用重启时重投持久化队列；多进程重复投递由正式 Worker 的领取 CAS 拦截。"""

    job_ids = _sichuan_workspace_service().list_queued_luxian_0609_batch_job_ids()
    for job_id in job_ids:
        submit_detached_task(
            "sichuan_workspace_batch_job_startup_resume",
            _run_sichuan_workspace_batch_job,
            job_id,
        )
    if job_ids:
        logger.info("重新投递 %d 个尚未领取的 LX0609 批量质控任务", len(job_ids))
    return len(job_ids)


_LX0609_RECOVERY_MONITOR: asyncio.Task[None] | None = None
_LX0609_RECOVERY_SCAN_SECONDS = 30
_LX0609_LEASE_STALE_AFTER = timedelta(minutes=3)


async def _monitor_luxian_0609_stale_attempts() -> None:
    while True:
        await asyncio.sleep(_LX0609_RECOVERY_SCAN_SECONDS)
        try:
            expired = await asyncio.to_thread(
                _sichuan_workspace_service().fail_stale_luxian_0609_running_jobs,
                stale_before=datetime.utcnow() - _LX0609_LEASE_STALE_AFTER,
            )
            if expired:
                logger.warning("已停止 %d 个续约过期的 LX0609 执行尝试", len(expired))
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("LX0609 任务续约巡检失败")


def start_luxian_0609_task_recovery_monitor() -> None:
    global _LX0609_RECOVERY_MONITOR
    if _LX0609_RECOVERY_MONITOR is None or _LX0609_RECOVERY_MONITOR.done():
        _LX0609_RECOVERY_MONITOR = asyncio.create_task(_monitor_luxian_0609_stale_attempts())


async def stop_luxian_0609_task_recovery_monitor() -> None:
    global _LX0609_RECOVERY_MONITOR
    task = _LX0609_RECOVERY_MONITOR
    _LX0609_RECOVERY_MONITOR = None
    if task is not None:
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)


@router.post("/workspace/batch-jobs")
async def create_workspace_batch_job(
    request: Request,
    payload: SichuanWorkspaceBatchJobCreateRequest,
    current_user: Dict[str, Any] = Depends(require_product_activation),
    qc_service: SichuanQCService = Depends(get_qc_service),
):
    requested_rule_set = get_sichuan_rule_set(payload.rule_set_key)
    if payload.diagnostic_capture:
        if not set(current_user.get("roles", [])).intersection({"admin", "super_admin"}):
            raise HTTPException(403, "仅管理员可采集完整排障包")
        if payload.rule_set_key != LUXIAN_0609_RULE_SET_KEY or len(payload.record_refs or []) != 1:
            raise HTTPException(422, "排障采集仅支持单病历泸县0609质控")
    if payload.rule_set_key and not requested_rule_set:
        raise HTTPException(status_code=422, detail=f"未知规则集: {payload.rule_set_key}")

    requested_payload_rule_ids = [
        str(item or "").strip().upper()
        for item in (payload.rule_ids or [])
        if str(item or "").strip()
    ]
    acceptance_only = get_luxian_0609_acceptance_only_rule_ids()
    if acceptance_only.intersection(requested_payload_rule_ids):
        raise HTTPException(422, "待验收规则仅支持客户样本验证显式选择")
    requested_rule_set_rule_ids = list(
        requested_payload_rule_ids
        or (requested_rule_set.rule_ids if requested_rule_set else ())
    )
    if requested_rule_set and requested_rule_set.key == LUXIAN_0609_RULE_SET_KEY:
        if not requested_payload_rule_ids:
            requested_rule_set_rule_ids = list(get_luxian_0609_customer_delivery_rule_ids())
        requested_rule_set_rule_ids = [
            rule_id
            for rule_id in requested_rule_set_rule_ids
            if str(rule_id).strip().upper() not in LUXIAN_0609_CUSTOMER_EXCLUDED_RULE_IDS
            and (requested_payload_rule_ids or str(rule_id).strip().upper() not in acceptance_only)
        ]
        if requested_payload_rule_ids and not requested_rule_set_rule_ids:
            raise HTTPException(status_code=422, detail="所选规则不在当前客户运行范围")
    try:
        direct_native_rule_ids = _assert_luxian_0609_formal_customer_rule_ids(
            rule_set_key=(requested_rule_set.key if requested_rule_set else ""),
            rule_ids=tuple(requested_rule_set_rule_ids),
            context="workspace_batch_create",
        )
    except ValueError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    is_direct_native_selection = bool(
        requested_rule_set
        and requested_rule_set.key == LUXIAN_0609_RULE_SET_KEY
        and requested_rule_set_rule_ids
        and len(direct_native_rule_ids) == len(set(requested_rule_set_rule_ids))
    )
    active_customer_rule_ids, pending_customer_rule_ids = (
        partition_luxian_0609_rule_scope(direct_native_rule_ids)
        if is_direct_native_selection
        else ((), ())
    )

    if requested_rule_set:
        rule_ids = (
            list(active_customer_rule_ids)
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
    if is_direct_native_selection and payload.record_ids:
        raise HTTPException(
            status_code=422,
            detail="LX0609质控任务不接受 record_ids，请改用 record_refs",
        )
    task_settings_snapshot = None
    task_runtime_snapshot = None
    if is_direct_native_selection:
        effective_settings = resolve_mainline_rule_decision_settings(get_settings())
        try:
            assert_luxian_0609_customer_native_delivery_ready(
                effective_settings,
                context="workspace_batch_create",
            )
            formal_package_plan = build_luxian_0609_package_plan_from_settings(
                inventory=load_luxian_0609_dependency_inventory(),
                selected_rule_ids=direct_native_rule_ids,
                settings=effective_settings,
            )
            assert_luxian_0609_formal_package_plan_native_only(
                formal_package_plan,
                context="workspace_batch_create",
            )
            task_settings_snapshot = capture_luxian_0609_task_settings(effective_settings)
            task_runtime_snapshot = capture_luxian_0609_task_runtime(qc_service)
        except ValueError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc
    compatibility_rule_ids = (
        formal_package_plan.compatibility_execution_rule_ids
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
    try:
        requested_record_refs = (
            case_refs_from_records(payload.record_refs or []) if payload.record_refs else ()
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    if payload.record_refs and len(requested_record_refs) != len(payload.record_refs):
        raise HTTPException(status_code=422, detail="record_refs 不可重复")
    collect_kwargs: Dict[str, Any] = dict(
        scope=normalized_scope,
        department=payload.department,
        doctor=payload.doctor,
        date_field=_normalize_date_field(payload.date_field),
        start_date=payload.start_date,
        end_date=payload.end_date,
        keyword=payload.keyword,
        record_ids=None if requested_record_refs else payload.record_ids or None,
        record_refs=requested_record_refs or None,
    )
    if payload.sync_scope == "today_inpatient":
        collect_kwargs["sync_scope"] = payload.sync_scope
    records = workspace.collect_records(**collect_kwargs)
    if not records:
        raise HTTPException(status_code=422, detail="当前筛选条件下没有可执行病历")

    try:
        effective_record_refs = case_refs_from_records(records)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail="病历缺少完整三坐标，无法创建质控任务") from exc
    if requested_record_refs and set(effective_record_refs) != set(requested_record_refs):
        raise HTTPException(status_code=422, detail="所选病历与服务端匹配结果不一致，请刷新后重试")
    if payload.record_ids and not requested_record_refs:
        refs_by_visit: Dict[str, set[CaseRef]] = {}
        for ref in effective_record_refs:
            refs_by_visit.setdefault(ref.visit_id, set()).add(ref)
        ambiguous_visit_ids = sorted(
            visit_id for visit_id, refs in refs_by_visit.items() if len(refs) > 1
        )
        if ambiguous_visit_ids:
            raise HTTPException(
                status_code=422,
                detail="所选住院号对应多份病历，请使用三坐标重新选择",
            )
    effective_record_ids = sorted({ref.visit_id for ref in effective_record_refs})
    effective_record_ref_payload = [ref.as_dict() for ref in effective_record_refs]
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
        **({LX0609_TASK_SETTINGS_FILTER_KEY: task_settings_snapshot} if task_settings_snapshot is not None else {}),
        **({LX0609_TASK_RUNTIME_FILTER_KEY: task_runtime_snapshot} if task_runtime_snapshot is not None else {}),
        **({"diagnostic_capture": True} if payload.diagnostic_capture else {}),
        "scope": normalized_scope,
        "query_scope": normalized_scope,
        **(
            {"sync_scope": payload.sync_scope}
            if payload.sync_scope == "today_inpatient"
            else {}
        ),
        "department": payload.department or "",
        "doctor": payload.doctor or "",
        "date_field": _normalize_date_field(payload.date_field),
        "start_date": payload.start_date or "",
        "end_date": payload.end_date or "",
        "keyword": payload.keyword or "",
        "record_refs": effective_record_ref_payload,
        "record_scene_snapshot": record_scene_snapshot,
        "rule_set_key": rule_set_key,
        "rule_ids": sorted({str(rule_id).strip().upper() for rule_id in rule_ids if str(rule_id).strip()}),
        **(
            {
                "customer_rule_ids": sorted(
                    {str(rule_id).strip().upper() for rule_id in direct_native_rule_ids if str(rule_id).strip()}
                )
            }
            if is_direct_native_selection
            else {}
        ),
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
            **(
                {"sync_scope": payload.sync_scope}
                if payload.sync_scope == "today_inpatient"
                else {}
            ),
            "date_field": _normalize_date_field(payload.date_field),
            "start_date": payload.start_date,
            "end_date": payload.end_date,
            "keyword": payload.keyword,
            "record_refs": effective_record_ref_payload,
            "query_scope": normalized_scope,
            "rule_ids": rule_ids,
            "paused_customer_rule_ids": list(pending_customer_rule_ids),
            "rule_set_key": rule_set_key,
            **({LX0609_TASK_SETTINGS_FILTER_KEY: task_settings_snapshot} if task_settings_snapshot is not None else {}),
            **({LX0609_TASK_RUNTIME_FILTER_KEY: task_runtime_snapshot} if task_runtime_snapshot is not None else {}),
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
            **({"diagnostic_capture": True} if payload.diagnostic_capture else {}),
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
                    "active_customer_rule_ids": list(active_customer_rule_ids),
                    "pending_customer_rule_ids": list(pending_customer_rule_ids),
                    "record_rule_map": {
                        ref.as_key(): list(direct_native_rule_ids)
                        for ref in effective_record_refs
                    },
                    "validation_mode": "programmatic",
                    "customer_rule_count": len(direct_native_rule_ids),
                    "execution_rule_count": len(active_customer_rule_ids),
                    "pending_rule_count": len(pending_customer_rule_ids),
                }
                if is_direct_native_selection
                else {}
            ),
        },
        record_ids=effective_record_ids,
        total_records=len(records),
        record_refs=effective_record_refs,
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


def _workspace_batch_list_item(job: Dict[str, Any]) -> Dict[str, Any]:
    """历史结果损坏只隔离本行，列表不交付未经校验的医学结果。"""
    try:
        return _workspace_batch_response_item(job, compact=True)
    except HTTPException as exc:
        if exc.status_code != 409 or exc.detail != "历史质控结果交付合同不完整，无法安全展示":
            raise
    # 只取任务元数据；不透传嵌套结果、原始摘要或旧结果文案。
    metadata = {
        key: job[key]
        for key in (
            "id", "status", "rule_code", "rule_name", "scope", "scene",
            "rule_set_key", "rule_set_id", "job_kind", "parent_job_id",
            "created_at", "started_at", "completed_at", "total_records",
            "success_count", "failed_count",
        )
        if key in job
    }
    metadata["rule_set_key"] = LUXIAN_0609_RULE_SET_KEY
    safe = _workspace_batch_response_item(metadata, compact=True)
    for container in (safe, safe["summary"]):
        for key in (
            "issue_records", "compliant_records", "uncertain_records",
            "result_count", "display_status_counts", "history_issue_summaries",
        ):
            container.pop(key, None)
    safe["error_message"] = "历史质控结果交付合同不完整，无法安全展示；请重新运行质控"
    return safe


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
        _workspace_batch_list_item(item)
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
    shared_read = False
    job = await run_in_threadpool(
        workspace.get_batch_job,
        job_id=job_id,
        created_by=_current_user_id(current_user),
    )
    if not job:
        job = await run_in_threadpool(
            _resolve_shared_sample_pool_latest_job,
            workspace=workspace,
            job_id=job_id,
            current_user=current_user,
        )
        shared_read = job is not None
    if not _is_workspace_batch_job(job):
        raise HTTPException(status_code=404, detail="批量任务不存在或无权限")
    filters = job.get("filters") if isinstance(job.get("filters"), dict) else {}
    if str(filters.get("rule_set_key") or "").strip() == LUXIAN_0609_RULE_SET_KEY:
        job = await run_in_threadpool(
            _hydrate_luxian_canonical_batch_job_or_409,
            workspace=workspace,
            job=job,
        )
    if shared_read:
        if str(filters.get("rule_set_key") or "").strip() == LUXIAN_0916_QC_RULE_SET_KEY:
            response_data = _project_luxian_0916_shared_job(job)
        else:
            response_data = {
                **await run_in_threadpool(_project_customer_safe_batch_job_or_409, job),
                "read_only": True,
            }
    else:
        response_data = await run_in_threadpool(_workspace_batch_response_item, job)
    return success_response(
        data=response_data,
        message="获取四川规则批量任务详情成功",
        trace_id=get_trace_id(request),
    )


@router.get("/workspace/records/{record_id}/latest-result")
async def get_latest_workspace_record_result(
    request: Request,
    record_id: str,
    institute_id: str = Query(..., min_length=1, description="机构标识"),
    patient_id: str = Query(..., min_length=1, description="患者标识"),
    current_user: Dict[str, Any] = Depends(
        require_roles("admin", "qc_manager", "sync_admin", "super_admin")
    ),
):
    """返回全院范围内、同一三坐标病历的最新 LX0609 保存结果。"""

    workspace = _sichuan_workspace_service()
    result = await run_in_threadpool(
        workspace.get_latest_luxian_0609_record_result,
        institute_id=institute_id,
        patient_id=patient_id,
        visit_id=record_id,
    )
    if str(result.get("state") or "") == "not_found":
        raise HTTPException(status_code=404, detail="该病历暂无已保存质控结果或无访问权限")
    return success_response(
        data=result,
        message="获取单病历最新质控结果成功",
        trace_id=get_trace_id(request),
    )


@router.post("/workspace/records/{record_id}/latest-result/remediation-draft")
async def create_latest_workspace_record_remediation_draft(
    request: Request,
    record_id: str,
    body: Dict[str, Any] = Body(...),
    institute_id: str = Query(..., min_length=1, description="机构标识"),
    patient_id: str = Query(..., min_length=1, description="患者标识"),
    current_user: Dict[str, Any] = Depends(
        require_roles("admin", "qc_manager", "sync_admin", "super_admin")
    ),
):
    """按需生成单条规则的整改草稿。

    只读取该病历已保存的最新结果，草稿不落库，也不改写质控结论与权威建议。
    """

    rule_id = str((body or {}).get("rule_id") or "").strip().upper()
    if not rule_id:
        raise HTTPException(status_code=400, detail="缺少规则编号")

    workspace = _sichuan_workspace_service()
    result = await run_in_threadpool(
        workspace.get_latest_luxian_0609_record_result,
        institute_id=institute_id,
        patient_id=patient_id,
        visit_id=record_id,
    )
    if str(result.get("state") or "") == "not_found":
        raise HTTPException(status_code=404, detail="该病历暂无已保存质控结果或无访问权限")

    item = next(
        (
            candidate
            for candidate in list(result.get("items") or [])
            if str(candidate.get("rule_id") or "").strip().upper() == rule_id
        ),
        None,
    )
    if item is None:
        raise HTTPException(status_code=404, detail="该病历最新结果中没有这条质控点")

    draft = await generate_remediation_draft(item=item)
    return success_response(
        data=draft,
        message="整改草稿生成完成" if draft.get("available") else "该结果暂不提供整改草稿",
        trace_id=get_trace_id(request),
    )


@router.get("/workspace/result-feedback-demo")
async def get_demo_result_feedback(
    request: Request,
    root_job_id: str = Query(..., min_length=1, max_length=64),
    record_ref: str = Query(..., min_length=1, max_length=96),
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """读取演示账号在当前病历上的反馈，不读取或返回病历身份。"""

    _require_demo_feedback_account(current_user)
    try:
        items = get_result_feedback_demo_store().list_for_record(
            root_job_id=root_job_id,
            record_ref=record_ref,
            created_by="admin-001",
        )
    except Exception as exc:
        _raise_demo_feedback_store_error(exc)
    return success_response(
        data={
            "root_job_id": root_job_id,
            "record_ref": record_ref,
            "items": items,
        },
        message="获取质控结果反馈成功",
        trace_id=get_trace_id(request),
    )


@router.get("/workspace/result-feedback-demo/all")
async def list_demo_result_feedbacks(
    request: Request,
    limit: int = Query(default=200, ge=1, le=500),
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """汇总反馈及客户可识别的病历标签，不返回三坐标或病历正文。"""

    _require_demo_feedback_account(current_user)
    try:
        stored_items = get_result_feedback_demo_store().list_all(
            created_by="admin-001",
            limit=limit,
        )
        items = _project_demo_feedback_record_context(stored_items)
    except Exception as exc:
        _raise_demo_feedback_store_error(exc)
    return success_response(
        data={"items": items, "total": len(items)},
        message="获取质控反馈记录成功",
        trace_id=get_trace_id(request),
    )


@router.put("/workspace/result-feedback-demo/{rule_id}")
async def save_demo_result_feedback(
    request: Request,
    rule_id: str,
    body: Dict[str, Any] = Body(...),
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """保存演示账号对当前规则结果的反馈，不改变 Canonical。"""

    _require_demo_feedback_account(current_user)
    payload = _parse_demo_feedback_payload(body)
    if payload.root_job_id and payload.root_job_id != str(payload.root_job_id).strip():
        raise HTTPException(status_code=400, detail="反馈参数不符合要求")
    try:
        result = get_result_feedback_demo_store().save(
            root_job_id=payload.root_job_id,
            record_ref=payload.record_ref,
            rule_id=rule_id,
            created_by="admin-001",
            payload=payload,
        )
    except Exception as exc:
        _raise_demo_feedback_store_error(exc)
    return success_response(
        data=result,
        message="质控结果反馈已保存",
        trace_id=get_trace_id(request),
    )


@router.get("/workspace/records/{record_id}/latest-result/export")
async def export_latest_workspace_record_result_html(
    request: Request,
    record_id: str,
    institute_id: str = Query(..., min_length=1, description="机构标识"),
    patient_id: str = Query(..., min_length=1, description="患者标识"),
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """导出一份三坐标病历的最新 Canonical HTML 结果。"""

    if not _can_export_record_results(current_user):
        raise HTTPException(status_code=403, detail="当前账号无权导出质控结果")
    workspace = _sichuan_workspace_service()
    result = workspace.get_latest_luxian_0609_record_result(
        institute_id=institute_id,
        patient_id=patient_id,
        visit_id=record_id,
    )
    result_state = str(result.get("state") or "")
    if result_state == "technical_error":
        raise HTTPException(status_code=409, detail="质控结果校验异常，请联系管理员复核")
    if result_state != "ready":
        raise HTTPException(status_code=404, detail="该病历暂无可导出的最终质控结果")
    records = workspace.collect_records(
        scope="all",
        department=None,
        doctor=None,
        date_field="admission",
        start_date=None,
        end_date=None,
        keyword=None,
        record_refs=[
            {
                "institute_id": institute_id,
                "patient_id": patient_id,
                "visit_id": record_id,
            }
        ],
    )
    record = next(
        (
            item
            for item in records
            if str(item.get("institute_id") or "").strip() == institute_id.strip()
            and str(item.get("patient_id") or "").strip() == patient_id.strip()
            and str(item.get("visit_id") or "").strip() == record_id.strip()
        ),
        {
            "institute_id": institute_id,
            "patient_id": patient_id,
            "visit_id": record_id,
        },
    )
    content = export_single_record_result_html(result=result, record=record)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    audit_event(
        request,
        action="qc.record_result.export_html",
        resource="/api/v1/qc/sichuan/workspace/records/{record_id}/latest-result/export",
        outcome="success",
        details={"record_count": 1, "result_rule_count": result.get("result_rule_count", 0)},
        current_user=current_user,
    )
    return Response(
        content=content,
        media_type="text/html; charset=utf-8",
        headers={
            "Content-Disposition": f"attachment; filename=qc_record_result_{timestamp}.html"
        },
    )


@router.post("/workspace/records/export")
async def export_filtered_workspace_record_results(
    request: Request,
    payload: Luxian0609RecordResultExportRequest,
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """按服务端完整筛选范围导出病历最新 Canonical 结果。"""

    if not _can_export_record_results(current_user):
        raise HTTPException(status_code=403, detail="当前账号无权导出质控结果")
    workspace = _sichuan_workspace_service()
    filters = {
        "scope": payload.scope,
        "department": str(payload.department or "").strip() or None,
        "doctor": str(payload.doctor or "").strip() or None,
        "date_field": payload.date_field,
        "start_date": str(payload.start_date or "").strip() or None,
        "end_date": str(payload.end_date or "").strip() or None,
        "keyword": str(payload.keyword or "").strip() or None,
    }
    requested_record_refs: tuple[CaseRef, ...] = ()
    if payload.record_refs is not None:
        try:
            requested_record_refs = case_refs_from_records(payload.record_refs)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail="所选病历身份不完整，请重新勾选") from exc
        if len(requested_record_refs) != len(payload.record_refs):
            raise HTTPException(status_code=422, detail="所选病历存在重复，请重新勾选")
        if len(requested_record_refs) > 1000:
            raise HTTPException(status_code=422, detail="所选病历超过1000份，请缩小范围后导出")

    if requested_record_refs:
        record_refs = [case_ref.as_dict() for case_ref in requested_record_refs]
        records = workspace.collect_records(
            scope=payload.scope,
            department=None,
            doctor=None,
            date_field=payload.date_field,
            start_date=None,
            end_date=None,
            keyword=None,
            record_refs=record_refs,
        )
        try:
            actual_record_refs = case_refs_from_records(records)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail="所选病历无法完整读取，已停止导出") from exc
        if (
            len(actual_record_refs) != len(records)
            or set(actual_record_refs) != set(requested_record_refs)
        ):
            raise HTTPException(status_code=422, detail="所选病历范围已变化，请重新勾选后导出")
        export_filters = {**filters, "export_mode": "selected"}
    else:
        record_count = workspace.count_records(**filters)
        if record_count > 1000:
            raise HTTPException(status_code=422, detail="当前筛选超过1000份病历，请缩小范围后导出")
        records = workspace.collect_records(**filters)
        if len(records) > 1000:
            raise HTTPException(status_code=422, detail="当前筛选超过1000份病历，请缩小范围后导出")
        export_filters = filters

    identities: set[tuple[str, str, str]] = set()
    canonical_record_refs: List[Dict[str, str]] = []
    for record in records:
        identity = (
            str(record.get("institute_id") or "").strip(),
            str(record.get("patient_id") or "").strip(),
            str(record.get("visit_id") or "").strip(),
        )
        if not all(identity) or identity in identities:
            raise HTTPException(status_code=422, detail="当前筛选存在不完整或重复病历身份，已停止导出")
        identities.add(identity)
        canonical_record_refs.append(
            {
                "institute_id": identity[0],
                "patient_id": identity[1],
                "visit_id": identity[2],
            }
        )
    results = workspace.build_latest_luxian_0609_record_result_dtos(
        record_refs=canonical_record_refs,
    )
    workbook = export_filtered_record_results_workbook(
        records=records,
        results=results,
        filters=export_filters,
    )
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    audit_event(
        request,
        action="qc.record_results.export_xlsx",
        resource="/api/v1/qc/sichuan/workspace/records/export",
        outcome="success",
        details={
            "record_count": len(records),
            "scope": payload.scope,
            "mode": "selected" if requested_record_refs else "filtered",
        },
        current_user=current_user,
    )
    return StreamingResponse(
        workbook,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={
            "Content-Disposition": f"attachment; filename=qc_record_results_{timestamp}.xlsx"
        },
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
    filters = job.get("filters") if isinstance(job.get("filters"), dict) else {}
    if str(filters.get("rule_set_key") or "").strip() == LUXIAN_0609_RULE_SET_KEY:
        job = _hydrate_luxian_canonical_batch_job_or_409(
            workspace=workspace,
            job=job,
        )
    try:
        review_report = review_luxian_0609_batch_job(job)
    except ValueError as exc:
        if str(exc) != LX0609_CUSTOMER_RESULT_CONTRACT_ERROR:
            raise
        raise HTTPException(
            status_code=409,
            detail="历史质控结果交付合同不完整，无法安全展示",
        ) from exc
    if review_report.get("scope") != LUXIAN_0609_RULE_SET_KEY:
        raise HTTPException(status_code=422, detail="当前复核 Loop 仅支持泸县0609质控任务")
    updated_job = workspace.update_batch_job_review_report(
        job_id=job_id,
        created_by=created_by,
        review_report=review_report,
    )
    if not _is_workspace_batch_job(updated_job):
        raise HTTPException(status_code=404, detail="批量任务不存在或无权限")
    updated_filters = (
        updated_job.get("filters")
        if isinstance(updated_job.get("filters"), dict)
        else {}
    )
    if (
        str(updated_filters.get("rule_set_key") or "").strip()
        == LUXIAN_0609_RULE_SET_KEY
    ):
        updated_job = _hydrate_luxian_canonical_batch_job_or_409(
            workspace=workspace,
            job=updated_job,
        )
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
    current_user: Dict[str, Any] = Depends(require_product_activation),
):
    workspace = _sichuan_workspace_service()
    try:
        job = workspace.retry_batch_job(job_id=job_id, created_by=_current_user_id(current_user))
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    if not _is_workspace_batch_job(job):
        existing = workspace.get_batch_job(job_id=job_id, created_by=_current_user_id(current_user))
        if _is_workspace_batch_job(existing) and (
            (existing.get("filters") or {}).get("rule_set_key") == LUXIAN_0609_RULE_SET_KEY
        ):
            raise HTTPException(status_code=409, detail="任务已在排队或执行中，不能重复入队")
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
        data=_workspace_batch_response_item(job),
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
    if not _can_export_record_results(current_user):
        raise HTTPException(status_code=403, detail="当前账号无权导出质控结果")
    workspace = _sichuan_workspace_service()
    job = workspace.get_batch_job(job_id=job_id, created_by=_current_user_id(current_user))
    if not _is_workspace_batch_job(job):
        raise HTTPException(status_code=404, detail="批量任务不存在或无权限")
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    normalized_format = str(format or "").lower()
    if normalized_format == "html":
        try:
            content = workspace.export_batch_job_html(job=job)
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        audit_event(
            request,
            action="qc.batch_result.export",
            resource="/api/v1/qc/sichuan/workspace/batch-jobs/{job_id}/export",
            outcome="success",
            details={
                "format": "html",
                "record_count": int(job.get("total_records") or 0),
            },
            current_user=current_user,
        )
        filename = f"sichuan_rules_{job_id}_{timestamp}.html"
        return Response(
            content=content,
            media_type="text/html",
            headers={"Content-Disposition": f"attachment; filename={filename}"},
        )
    if normalized_format == "csv":
        try:
            content = workspace.export_batch_job_csv(job=job)
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        filename = f"sichuan_rules_{job_id}_{timestamp}.csv"
        return StreamingResponse(
            iter([content.getvalue().encode("utf-8-sig")]),
            media_type="text/csv; charset=utf-8",
            headers={"Content-Disposition": f"attachment; filename={filename}"},
        )
    try:
        workbook = workspace.export_batch_job_workbook(job=job)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    filename = f"sichuan_rules_{job_id}_{timestamp}.xlsx"
    return StreamingResponse(
        workbook,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@router.post("/results/save")
async def save_qc_result(
    request: Request,
    req: SaveQCResultRequest,
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    try:
        base_dir = _saved_qc_results_directory()
        base_dir.mkdir(parents=True, exist_ok=True)
        result_id = str(uuid.uuid4())
        filename = f"{result_id}.json"
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
            "created_by": _current_user_id(current_user),
            "created_at": datetime.now(timezone.utc).isoformat()
        }

        with filepath.open("w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)

        return success_response(
            # 保持既有字段形状，但不再泄露服务器文件系统绝对路径。
            data={"id": result_id, "path": f"/api/v1/qc/sichuan/results/{result_id}"},
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
    has_issues: Optional[bool] = Query(None),
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """获取质控结果历史列表"""
    try:
        base_dir = _saved_qc_results_directory()
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
        all_files = sorted(
            base_dir.glob("*.json"),
            key=_saved_qc_result_sort_mtime,
            reverse=True,
        )
        records = []

        for filepath in all_files:
            try:
                data = _read_saved_qc_result_file(filepath, base_dir)
                if not isinstance(data, dict) or not _can_read_saved_qc_result(data, current_user):
                    continue

                # 提取摘要信息
                stats = data.get("stats", {})
                stats = stats if isinstance(stats, dict) else {}
                metadata = data.get("metadata", {})
                metadata = metadata if isinstance(metadata, dict) else {}
                payload = _saved_qc_result_payload(data)
                evaluation_summary = payload.get("evaluation_summary", {})
                evaluation_summary = evaluation_summary if isinstance(evaluation_summary, dict) else {}

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
                model = _saved_qc_result_model(data)

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
async def get_latest_qc_result(
    request: Request,
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """获取最新一次质控结果"""
    try:
        base_dir = _saved_qc_results_directory()
        if not base_dir.exists():
            raise HTTPException(status_code=StatusCode.NOT_FOUND, detail="暂无质控结果")

        all_files = sorted(
            base_dir.glob("*.json"),
            key=_saved_qc_result_sort_mtime,
            reverse=True,
        )
        for filepath in all_files:
            try:
                data = _read_saved_qc_result_file(filepath, base_dir)
            except (OSError, json.JSONDecodeError) as exc:
                logger.warning("读取质控结果文件失败 %s: %s", filepath, exc)
                continue
            if not isinstance(data, dict) or not _can_read_saved_qc_result(data, current_user):
                continue
            return success_response(
                data=data,
                message="获取最新质控结果成功",
                trace_id=get_trace_id(request),
            )
        raise HTTPException(status_code=StatusCode.NOT_FOUND, detail="暂无质控结果")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=StatusCode.INTERNAL_SERVER_ERROR, detail=f"获取最新质控结果失败: {e}")


@router.get("/results/{result_id}")
async def get_qc_result_detail(
    request: Request,
    result_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """获取指定ID的质控结果详情"""
    try:
        normalized_result_id = _normalize_saved_qc_result_id(result_id)
        data = _load_saved_qc_result_by_id(normalized_result_id)
        if not data or not _can_read_saved_qc_result(data, current_user):
            raise HTTPException(status_code=StatusCode.NOT_FOUND, detail="质控结果不存在")
        model = _saved_qc_result_model(data)
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
        data = [
            rule
            for rule in data
            if str(rule.get("rule_id") or rule.get("rule_code") or "").strip().upper()
            not in LUXIAN_0609_CUSTOMER_EXCLUDED_RULE_IDS
        ]
        data = attach_luxian_0609_customer_policy(data)

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
            raise HTTPException(
                status_code=422,
                detail=(
                    "LX0609 规则必须通过客户样本验证或正式单规则入口执行；"
                    "纯文本测试无法提供所需的结构化事件和关联字段。"
                ),
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
    user_id: Optional[str] = Query(default=None),
    system_config_user: dict = Depends(
        require_roles("admin", "sync_admin", "super_admin")
    ),
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
    del system_config_user
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
                    "execution_concurrency": {
                        "max_parallel_records": qc_service.client.max_parallel_records,
                        "family_max_concurrency": qc_service.client.family_max_concurrency,
                        "http_max_concurrency": qc_service.client.http_max_concurrency,
                    },
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
