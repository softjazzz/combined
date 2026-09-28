from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import os
import uuid
from contextlib import contextmanager
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Annotated, Any, Dict, Iterator, Literal, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, Query, Request, UploadFile
from fastapi.responses import FileResponse, Response
from pydantic import BaseModel, ConfigDict, Field, StringConstraints
from sqlalchemy import create_engine, text
from sqlalchemy.pool import NullPool
from starlette.concurrency import run_in_threadpool

from ..core.audit import audit_event
from ..core.response import get_trace_id, success_response
from ..core.security import get_current_user, require_roles
from ..database.connection import SessionLocal
from ..services.product_activation import require_product_activation
from ..services.fast_screen_qc import EXECUTION_STRATEGY_FAST_SCREEN, EXECUTION_STRATEGY_STANDARD, get_fast_screen_full_rule_ids
from ..routers.qc_sichuan import (
    _build_workspace_record_scene_snapshot,
    _run_sichuan_workspace_batch_job,
)
from ..services.custom_qc_sample_pool_service import (
    CustomerTestRecordConflictError,
    CustomerTestRecordNotFoundError,
    CustomQCSamplePoolService,
    SampleSyncJobConflictError,
    build_sample_validation_execution_scope_hash,
    load_manual_case_rows_from_excel,
)
from ..services.custom_qc_workspace_service import CustomQCWorkspaceService
from ..services.case_identity import CaseRef, normalize_case_refs
from ..services.customer_rule_sets import (
    CUSTOMER_LUXIAN_RULE_SET_KEY,
    get_customer_luxian_rule_set,
)
from ..services.detached_task_runner import submit_detached_task
from ..services.luxian_0609_rule_catalog import LUXIAN_0609_RULE_SET_KEY
from ..services.rule_set_version_service import (
    RuleSetVersionNotFound,
    RuleSetVersionUnavailable,
    current_version as _current_rule_set_version,
    resolve_rule_set_version,
)
from ..services.luxian_0609 import (
    build_family_scopes as _build_luxian_0609_family_scopes,
    normalize_customer_rule_ids as _normalize_rule_id_list,
    resolve_execution_scope as _resolve_luxian_0609_execution_scope,
)
from ..services.luxian_0609.evaluation_horizon import (
    build_record_evaluation_horizon_snapshot,
)
from ..services.sample_validation_rule_sets import (
    FORMAL_FAST_SCREEN_FULL_MODE,
    FORMAL_FAST_SCREEN_FULL_RULE_SET_KEY,
    LUXIAN_0609_QC_RULE_SET_KEY,
    LUXIAN_0916_QC_RULE_SET_KEY,
    get_sample_programmatic_rule_set,
    list_sample_validation_rule_sets,
    resolve_sample_validation_rule_set_by_key,
    resolve_sample_validation_pseudo_draft,
)
from ..services.luxian_0609.phase_scope import load_luxian_0609_phase_scope
from ..services.qc_rule_sets import get_sichuan_rule_set
from ..services.test_record_import_service import (
    MAX_UPLOAD_BYTES,
    TestRecordImportValidationError,
    build_test_record_import_template,
    parse_test_record_import,
)
from ..services.test_record_transfer_service import (
    CustomerTestRecordCopyResultUnknown,
    EXPORT_FILENAME as TEST_RECORD_EXPORT_FILENAME,
    copy_customer_test_record,
    export_customer_test_records,
)
from ..services.llm_config_loader import LLMConfigLoader
from ..services.llm_execution_concurrency import concurrency_from_custom_parameters


router = APIRouter(
    prefix="/api/v1/qc/sample-pools",
    tags=["qc-sample-pools"],
    dependencies=[Depends(require_roles("admin", "qc_manager", "sync_admin"))],
)

_IMPORT_UPLOAD_DIR = (
    Path(__file__).resolve().parents[2] / "data" / "sample_pool_uploads"
)
_FAST_SCREEN_FULL_RULE_ID_SET = {str(item).strip().upper() for item in get_fast_screen_full_rule_ids() if str(item).strip()}
_SHEET2_EXACT_REVIEW_ACCEPTANCE_JSON = (
    Path(__file__).resolve().parents[3] / "docs" / "0418" / "QC" / "sheet2_exact_review_acceptance_package.json"
)
_LUXIAN_0609_REPORT_DIR = Path(__file__).resolve().parents[3] / "docs" / "0602"
_LUXIAN_0609_REPORT_FILES = {
    "md": ("泸县0609质控点评估报告.md", "text/markdown; charset=utf-8"),
    "csv": ("luxian_0609_qc_eval.csv", "text/csv; charset=utf-8"),
    "json": ("luxian_0609_qc_eval.json", "application/json; charset=utf-8"),
}
_SAMPLE_VALIDATION_DEDUP_WINDOW = timedelta(minutes=2)
_SAMPLE_VALIDATION_DEDUP_STATUSES = {"queued", "running"}
_ACTIVE_TEST_RECORD_IMPORTS: set[str] = set()
_ACTIVE_TEST_RECORD_IMPORTS_LOCK = asyncio.Lock()
# 阶段冻结规则保留在客户结果集合中，由 worker 统一投影为 not_executed。
_LUXIAN_0609_PAUSED_CUSTOMER_RULE_IDS = frozenset(
    entry.rule_id
    for entry in load_luxian_0609_phase_scope()
    if entry.phase_status != "phase_1_target"
)


def _service() -> CustomQCSamplePoolService:
    return CustomQCSamplePoolService()


def _workspace_service() -> CustomQCWorkspaceService:
    return CustomQCWorkspaceService()


def _current_user_id(current_user: Dict[str, Any]) -> str:
    return (
        str(current_user.get("id") or current_user.get("user_id") or current_user.get("username") or "")
        .strip()
        or "anonymous"
    )


def _sample_validation_operation_ref() -> str:
    return f"sample-op-{uuid.uuid4().hex[:24]}"


def _as_utc_naive_datetime(value: Any) -> Optional[datetime]:
    if isinstance(value, datetime):
        parsed = value
    else:
        text = str(value or "").strip()
        if not text:
            return None
        try:
            parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
        except ValueError:
            return None
    if parsed.tzinfo is not None:
        return parsed.astimezone(timezone.utc).replace(tzinfo=None)
    return parsed


def _find_recent_sample_validation_job(
    *,
    workspace: Any,
    created_by: str,
    execution_scope_hash: str,
    now: Optional[datetime] = None,
) -> Optional[Dict[str, Any]]:
    try:
        page = workspace.list_batch_jobs(
            created_by=created_by,
            include_children=False,
            page=1,
            page_size=100,
        )
    except (AttributeError, TypeError):
        return None
    cutoff = (now or datetime.utcnow()) - _SAMPLE_VALIDATION_DEDUP_WINDOW
    for job in list(getattr(page, "items", None) or []):
        if str(job.get("status") or "").strip().lower() not in _SAMPLE_VALIDATION_DEDUP_STATUSES:
            continue
        created_at = _as_utc_naive_datetime(job.get("created_at"))
        if created_at is None or created_at < cutoff:
            continue
        filters = job.get("filters") if isinstance(job.get("filters"), dict) else {}
        if str(filters.get("execution_scope_hash") or "").strip() == execution_scope_hash:
            return job
    return None


def _resolve_sample_validation_execution_strategy(*, validation_mode: str, rule_ids: list[str]) -> str:
    if str(validation_mode or "").strip().lower() != "sc":
        return EXECUTION_STRATEGY_FAST_SCREEN
    normalized_rule_ids = {
        str(rule_id or "").strip().upper()
        for rule_id in list(rule_ids or [])
        if str(rule_id or "").strip()
    }
    if normalized_rule_ids and normalized_rule_ids.issubset(_FAST_SCREEN_FULL_RULE_ID_SET):
        return EXECUTION_STRATEGY_FAST_SCREEN
    return EXECUTION_STRATEGY_STANDARD


class SamplePoolImportRequest(BaseModel):
    pool_name: str = Field(..., description="样本池名称")
    source_file: str = Field(..., description="Excel 文件路径")
    source_sheet: str = Field(default="Sheet2", description="Sheet 名称")
    description: Optional[str] = Field(default=None, description="备注")
    scene: str = Field(default="running", description="目标场景")


NonEmptySampleRecordCoordinate = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1),
]


class SamplePoolRunRecordRef(BaseModel):
    model_config = ConfigDict(extra="forbid")

    institute_id: NonEmptySampleRecordCoordinate
    patient_id: NonEmptySampleRecordCoordinate
    visit_id: NonEmptySampleRecordCoordinate


class SamplePoolRunRequest(BaseModel):
    department: Optional[str] = None
    doctor: Optional[str] = None
    model_code: Optional[str] = None
    top_p: Optional[float] = None
    temperature: Optional[float] = None
    max_tokens: Optional[int] = None
    max_parallel_records: Optional[int] = Field(default=None, description="病历级并发数")
    sample_item_ids: list[str] = Field(default_factory=list, description="选中的样本项 ID")
    record_refs: list[SamplePoolRunRecordRef] = Field(default_factory=list, description="选中病历的完整三坐标")
    # 仅保留旧客户端的明确失败提示；新运行请求不得以 visit_id 授权病例范围。
    record_ids: list[str] = Field(default_factory=list, description="选中的真实病历 visit_id")
    selected_rule_ids: list[str] = Field(default_factory=list, description="仅验证这些客户质控点 ID")
    group_by_luxian_family: bool = Field(default=False, description="泸县0609按规则族创建父子任务")
    validation_mode: str = Field(default="customer", description="验证模式：customer/sc/programmatic/formal_fast_screen_full")
    rule_set_key: Optional[str] = Field(default=None, description="指定规则包 key")


class SamplePoolSyncRequest(BaseModel):
    only_intrinsic: bool = Field(default=True, description="只同步内涵样本")
    include_in_batch_1: bool = Field(default=True, description="只同步首批样本")
    table_groups: list[str] = Field(
        default_factory=list,
        description="同步表分组；为空时使用样本验证服务默认组 sample_full_domain",
    )


class SamplePoolAdmissionSyncRequest(BaseModel):
    start_date: date = Field(..., description="入院日期开始，含当天")
    end_date: date = Field(..., description="入院日期结束，含当天")
    departments: list[str] = Field(default_factory=list, description="入院科室；为空表示全部科室")


class SamplePoolHospitalizationScopeRequest(BaseModel):
    scope_mode: str = Field(
        default="active_and_discharged",
        description="住院范围：active/discharged/active_and_discharged",
    )
    as_of_date: date = Field(..., description="当前在院统计日期")
    discharge_start_date: Optional[date] = Field(default=None, description="出院日期开始，含当天")
    discharge_end_date: Optional[date] = Field(default=None, description="出院日期结束，含当天")
    departments: list[str] = Field(default_factory=list, description="有效科室；为空表示全部科室")


def _normalize_hospitalization_scope_payload(
    payload: SamplePoolHospitalizationScopeRequest,
) -> Dict[str, Any]:
    scope_mode = str(payload.scope_mode or "").strip().lower()
    if scope_mode not in {"active", "discharged", "active_and_discharged"}:
        raise HTTPException(status_code=422, detail="住院范围仅支持当前在院、期间出院或两者合并")
    needs_discharge_range = scope_mode in {"discharged", "active_and_discharged"}
    if needs_discharge_range and (
        payload.discharge_start_date is None or payload.discharge_end_date is None
    ):
        raise HTTPException(status_code=422, detail="期间出院范围必须填写出院开始日期和结束日期")
    if (
        payload.discharge_start_date
        and payload.discharge_end_date
        and payload.discharge_start_date > payload.discharge_end_date
    ):
        raise HTTPException(status_code=422, detail="出院开始日期不能晚于结束日期")
    if (
        payload.discharge_start_date
        and payload.discharge_end_date
        and (payload.discharge_end_date - payload.discharge_start_date).days > 30
    ):
        raise HTTPException(status_code=422, detail="出院日期范围最多 31 天")
    departments = list(
        dict.fromkeys(item.strip() for item in payload.departments if item.strip())
    )
    return {
        "mode": scope_mode,
        "as_of_date": payload.as_of_date.isoformat(),
        "discharge_start_date": payload.discharge_start_date.isoformat()
        if payload.discharge_start_date
        else None,
        "discharge_end_date": payload.discharge_end_date.isoformat()
        if payload.discharge_end_date
        else None,
        "departments": departments,
    }


class TestRecordBasicInfo(BaseModel):
    patient_name: str = Field(..., description="患者姓名")
    sex: str = Field(default="男", description="性别")
    age: int = Field(default=45, ge=0, le=120, description="年龄")
    mr_no: Optional[str] = Field(default=None, description="住院号")
    department: str = Field(..., description="科室")
    admission_time: datetime = Field(..., description="入院时间")
    discharge_time: Optional[datetime] = Field(default=None, description="出院时间")
    main_diagnosis: Optional[str] = Field(default=None, description="主要诊断")
    other_diagnoses: list[str] = Field(default_factory=list, description="其他诊断")
    doctor_name: Optional[str] = Field(default=None, description="默认记录医师")
    contact_number: Optional[str] = Field(default=None, description="联系电话")
    address: Optional[str] = Field(default=None, description="住址")


class TestRecordDocument(BaseModel):
    document_type: str = Field(..., description="文书类型")
    title: str = Field(..., description="文书标题")
    record_time: Optional[datetime] = Field(default=None, description="记录/报告/医嘱时间")
    submit_time: Optional[datetime] = Field(default=None, description="提交时间")
    content: str = Field(..., description="文书内容")
    doctor_name: Optional[str] = Field(default=None, description="记录医师")
    doctor_code: Optional[str] = Field(default=None, description="医师代码")
    enabled: bool = Field(default=True, description="是否写入")


class TestRecordGoldenAnswer(BaseModel):
    qc_point_id: str = Field(..., description="客户质控点 ID，如 LX0609-001")
    expected_status: Literal[
        "non_compliant",
        "ai_suggested_non_compliant",
        "ai_suggested_compliant",
        "compliant",
        "not_applicable",
        "data_gap",
        "uncertain",
    ] = Field(
        ..., description="人工预期状态"
    )
    trigger_facts: list[str] = Field(default_factory=list, description="触发事实")
    evidence_keywords: list[str] = Field(default_factory=list, description="证据关键词")
    human_reason: Optional[str] = Field(default=None, description="人工判定理由")


class TestRecordSourceMeta(BaseModel):
    type: str = Field(default="customer_source_editable_copy", description="来源类型")
    source_pool_id: Optional[str] = Field(default=None, description="来源样本池 ID")
    source_pool_name: Optional[str] = Field(default=None, description="来源样本池名称")
    source_record_id: Optional[str] = Field(default=None, description="来源病历聚合记录 ID")
    source_item_ids: list[str] = Field(default_factory=list, description="来源样本行 ID")
    source_visit_id: Optional[str] = Field(default=None, description="来源 visit_id")
    source_mr_no: Optional[str] = Field(default=None, description="来源病案号")
    source_patient_name: Optional[str] = Field(default=None, description="来源患者姓名")
    source_department: Optional[str] = Field(default=None, description="来源科室")
    created_from: Optional[str] = Field(default=None, description="创建来源入口")
    supersedes_item_id: Optional[str] = Field(
        default=None, description="编辑测试病历时被替换的旧条目 ID（仅限客户自建测试病历固定池）"
    )
    supersedes_updated_at: Optional[str] = Field(
        default=None, description="被替换旧条目的 updated_at，用于 CAS 防并发覆盖"
    )


class TestRecordCreateRequest(BaseModel):
    case_title: str = Field(..., description="测试病历名称")
    basic_info: TestRecordBasicInfo
    documents: list[TestRecordDocument] = Field(..., min_length=1, description="文书列表")
    selected_rule_ids: list[str] = Field(default_factory=list, description="重点验证规则")
    manual_issue_text: Optional[str] = Field(default=None, description="样本说明")
    template_key: Optional[str] = Field(default=None, description="使用的测试病历模板 key")
    golden_answers: list[TestRecordGoldenAnswer] = Field(default_factory=list, description="人工预期结果")
    source: Optional[TestRecordSourceMeta] = Field(default=None, description="派生测试病历来源记录")


class TestRecordRulesUpdateRequest(BaseModel):
    rule_ids: list[str] = Field(default_factory=list, description="关联的质控点 rule_id")
    updated_at: str = Field(..., min_length=1, description="条目当前 updated_at，用于 CAS")


class TestRecordExportRequest(BaseModel):
    item_ids: list[str] = Field(..., min_length=1, max_length=20)


class TestRecordCopyRequest(BaseModel):
    updated_at: str = Field(..., min_length=1, description="源条目 updated_at，用于 CAS")
    case_title: Optional[str] = Field(default=None, max_length=200)


def _raise_test_record_error(exc: Exception) -> None:
    if isinstance(exc, CustomerTestRecordNotFoundError):
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    if isinstance(exc, CustomerTestRecordConflictError):
        # 与本路由其余 409 一致用字符串 detail，前端错误信封可直接展示。
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    raise exc


def _current_version_rule_ids() -> set[str]:
    """当前规则集版本的全部规则（active、paused、excluded 合集）。"""
    try:
        resolution = resolve_rule_set_version(
            LUXIAN_0609_RULE_SET_KEY, _current_rule_set_version(LUXIAN_0609_RULE_SET_KEY)
        )
    except (RuleSetVersionNotFound, RuleSetVersionUnavailable) as exc:
        raise HTTPException(status_code=503, detail="当前规则集版本读取失败") from exc
    return {
        *resolution["active_rule_ids"],
        *resolution["paused_rule_ids"],
        *resolution["excluded_rule_ids"],
    }


@contextmanager
def _sample_sync_write_lock() -> Iterator[bool]:
    """用独立 PG 连接串行化共享 CDM/Bundle 写入，不占应用连接池。"""
    bind = SessionLocal.kw.get("bind") if SessionLocal is not None else None
    if bind is None or bind.dialect.name != "postgresql":
        yield True
        return
    from ..services.task_record_sync_job_service import _GLOBAL_LOCK_KEY

    lock_engine = create_engine(bind.url, poolclass=NullPool, connect_args={"connect_timeout": 5})
    try:
        with lock_engine.connect() as connection:
            acquired = bool(connection.execute(
                text("SELECT pg_try_advisory_lock(:key)"), {"key": _GLOBAL_LOCK_KEY},
            ).scalar_one())
            connection.commit()
            try:
                yield acquired
            finally:
                if acquired:
                    try:
                        connection.execute(
                            text("SELECT pg_advisory_unlock(:key)"), {"key": _GLOBAL_LOCK_KEY},
                        )
                        connection.commit()
                    except Exception:
                        logging.getLogger(__name__).exception("样本池同步写锁释放失败，强制失效连接")
                        try:
                            connection.invalidate()
                        except Exception:
                            logging.getLogger(__name__).exception("样本池同步写锁连接失效失败")
    finally:
        lock_engine.dispose()


def _run_sample_pool_sync_job(job_id: str) -> None:
    service = _service()
    job = service.get_sync_job(job_id=job_id)
    if not job:
        return
    payload = job.get("payload") or {}
    pool_id = str(job.get("pool_id") or "").strip()
    if not pool_id:
        service.fail_sync_job(job_id=job_id, error_message="同步任务缺少样本池标识")
        return

    terminal_persisted = False
    try:
        with _sample_sync_write_lock() as acquired:
            if not acquired:
                service.fail_sync_job(job_id=job_id, error_message="病历资料同步资源忙，请稍后重新发起")
                terminal_persisted = True
                return
            _run_sample_pool_sync_job_locked(service, job_id, payload, pool_id)
            terminal_persisted = True
    except Exception as exc:
        if terminal_persisted:
            logging.getLogger(__name__).exception("样本池同步终态已持久化，但写锁清理失败")
        else:
            service.fail_sync_job(job_id=job_id, error_message=f"病历资料同步执行或锁获取失败：{type(exc).__name__}")


def _run_sample_pool_sync_job_locked(
    service: CustomQCSamplePoolService, job_id: str, payload: Dict[str, Any], pool_id: str,
) -> None:

    service.mark_sync_job_running(job_id=job_id)

    def emit_progress(progress: Dict[str, Any]) -> None:
        service.update_sync_job_progress(job_id=job_id, progress=progress)

    try:
        hospitalization_scope = payload.get("hospitalization_scope")
        hospitalization_summary: Dict[str, Any] = {}
        admission_filter = payload.get("admission_filter")
        admission_summary: Dict[str, Any] = {}
        item_ids = None
        if isinstance(hospitalization_scope, dict):
            scope_mode = str(hospitalization_scope.get("mode") or "").strip().lower()
            as_of_date = date.fromisoformat(str(hospitalization_scope.get("as_of_date") or ""))
            discharge_start_raw = hospitalization_scope.get("discharge_start_date")
            discharge_end_raw = hospitalization_scope.get("discharge_end_date")
            discharge_start_date = (
                date.fromisoformat(str(discharge_start_raw)) if discharge_start_raw else None
            )
            discharge_end_date = (
                date.fromisoformat(str(discharge_end_raw)) if discharge_end_raw else None
            )
            hospitalization_summary = service.append_pool_items_by_hospitalization_scope(
                pool_id=pool_id,
                scope_mode=scope_mode,
                as_of_date=as_of_date,
                discharge_start_date=discharge_start_date,
                discharge_end_date=discharge_end_date,
                departments=list(hospitalization_scope.get("departments") or []),
            )
            item_ids = list(hospitalization_summary.get("sync_item_ids") or [])
            emit_progress(
                {
                    "step_key": "selected",
                    "step_label": "已按住院范围筛选病历",
                    "total_candidates": len(item_ids),
                    "eligible_visits": len(item_ids),
                    "record_progress": {
                        "total": len(item_ids),
                        "completed": 0,
                        "remaining": len(item_ids),
                        "basis": "hospitalization_scope",
                        "label": "住院范围病历",
                    },
                    "processed_tables": 0,
                    "total_tables": 0,
                    "current_table": "住院范围",
                    "remaining_tables": 0,
                }
            )
            if not item_ids:
                service.finish_sync_job(
                    job_id=job_id,
                    summary={
                        "pool_id": pool_id,
                        "hospitalization_scope": hospitalization_summary,
                        "eligible_visits": 0,
                        "total_rows_pulled": 0,
                        "total_rows_upserted": 0,
                        "record_progress": {
                            "total": 0,
                            "completed": 0,
                            "remaining": 0,
                            "basis": "hospitalization_scope",
                            "label": "住院范围病历",
                        },
                    },
                )
                return
        elif isinstance(admission_filter, dict):
            start_date = date.fromisoformat(str(admission_filter.get("start_date") or ""))
            end_date = date.fromisoformat(str(admission_filter.get("end_date") or ""))
            admission_summary = service.append_pool_items_by_admission_filter(
                pool_id=pool_id,
                start_date=start_date,
                end_date=end_date,
                departments=list(admission_filter.get("departments") or []),
            )
            item_ids = list(admission_summary.get("sync_item_ids") or [])
            emit_progress(
                {
                    "step_key": "selected",
                    "step_label": "已按入院日期和科室筛选病历",
                    "total_candidates": len(item_ids),
                    "eligible_visits": len(item_ids),
                    "record_progress": {
                        "total": len(item_ids),
                        "completed": 0,
                        "remaining": len(item_ids),
                        "basis": "admission_filter",
                        "label": "条件筛选病历",
                    },
                    "processed_tables": 0,
                    "total_tables": 0,
                    "current_table": "inpat_registration",
                    "remaining_tables": 0,
                }
            )
            if not item_ids:
                service.finish_sync_job(
                    job_id=job_id,
                    summary={
                        "pool_id": pool_id,
                        "admission_filter": admission_summary,
                        "eligible_visits": 0,
                        "total_rows_pulled": 0,
                        "total_rows_upserted": 0,
                        "record_progress": {
                            "total": 0,
                            "completed": 0,
                            "remaining": 0,
                            "basis": "admission_filter",
                            "label": "条件筛选病历",
                        },
                    },
                )
                return
        result = service.sync_pool_records(
            pool_id=pool_id,
            only_intrinsic=bool(payload.get("only_intrinsic", True)),
            include_in_batch_1=bool(payload.get("include_in_batch_1", True)),
            table_groups=payload.get("table_groups") or None,
            item_ids=item_ids,
            progress_callback=emit_progress,
        )
        if hospitalization_summary:
            result["hospitalization_scope"] = hospitalization_summary
        elif admission_summary:
            result["admission_filter"] = admission_summary
        service.finish_sync_job(job_id=job_id, summary=result)
    except Exception as exc:
        service.fail_sync_job(job_id=job_id, error_message=str(exc))


@router.get("")
async def list_sample_pools(
    request: Request,
    q: Optional[str] = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    result = _service().list_pools(page=page, page_size=page_size, query=q)
    return success_response(
        data={
            "items": result.items,
            "total": result.total,
            "page": result.page,
            "page_size": result.page_size,
        },
        message="获取客户样本池成功",
        trace_id=get_trace_id(request),
    )


@router.post("/test-records")
async def create_test_record(
    request: Request,
    payload: TestRecordCreateRequest,
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    try:
        result = _service().create_customer_test_record(
            payload=payload.model_dump(mode="json"),
            created_by=_current_user_id(current_user),
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except (CustomerTestRecordNotFoundError, CustomerTestRecordConflictError) as exc:
        _raise_test_record_error(exc)
    return success_response(
        data=result,
        message="客户自建测试病历已创建",
        trace_id=get_trace_id(request),
    )


@router.post("/test-records/export")
async def export_test_records(
    request: Request,
    payload: TestRecordExportRequest,
    current_user: Dict[str, Any] = Depends(require_roles("admin", "qc_manager")),
):
    try:
        content, row_count = await run_in_threadpool(
            export_customer_test_records,
            item_ids=payload.item_ids,
            allowed_rule_ids=_current_version_rule_ids(),
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=422,
            detail={"code": "invalid_test_record_export", "message": str(exc)},
        ) from exc
    except CustomerTestRecordNotFoundError as exc:
        raise HTTPException(
            status_code=404,
            detail={"code": "test_record_not_found", "message": str(exc)},
        ) from exc
    except CustomerTestRecordConflictError as exc:
        raise HTTPException(
            status_code=409,
            detail={"code": exc.code, "message": str(exc)},
        ) from exc
    except Exception as exc:
        logging.getLogger(__name__).error(
            "test_record_export_failed error_type=%s", type(exc).__name__,
        )
        raise HTTPException(status_code=503, detail="测试病历导出暂不可用，请稍后重试") from None
    audit_event(
        request,
        action="qc.sample_pools.test_records.export",
        resource="qc_sample_pool_item",
        outcome="success",
        details={"selected_count": len(payload.item_ids), "exported_count": row_count},
        current_user=current_user,
    )
    return Response(
        content=content,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={
            "Content-Disposition": f"attachment; filename*=UTF-8''{TEST_RECORD_EXPORT_FILENAME}",
            "Cache-Control": "no-store",
            "X-Content-Type-Options": "nosniff",
        },
    )


@router.post("/test-records/{item_id}/copy")
async def copy_test_record(
    request: Request,
    item_id: str,
    payload: TestRecordCopyRequest,
    current_user: Dict[str, Any] = Depends(require_roles("admin", "qc_manager")),
):
    actor_id = str(current_user.get("id") or current_user.get("user_id") or "").strip()
    if not actor_id or actor_id.lower() == "anonymous":
        raise HTTPException(status_code=403, detail="当前用户缺少稳定标识，无法复制测试病历")
    try:
        result = await run_in_threadpool(
            copy_customer_test_record,
            item_id=item_id,
            expected_updated_at=payload.updated_at,
            case_title=payload.case_title,
            created_by=actor_id,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=422,
            detail={"code": "invalid_test_record_copy", "message": str(exc)},
        ) from exc
    except CustomerTestRecordNotFoundError as exc:
        raise HTTPException(
            status_code=404,
            detail={"code": "test_record_not_found", "message": str(exc)},
        ) from exc
    except CustomerTestRecordConflictError as exc:
        raise HTTPException(
            status_code=409,
            detail={"code": exc.code, "message": str(exc)},
        ) from exc
    except CustomerTestRecordCopyResultUnknown as exc:
        logging.getLogger(__name__).warning(
            "test_record_copy_result_unknown source_item_id=%s", item_id,
        )
        try:
            audit_event(
                request,
                action="qc.sample_pools.test_records.copy",
                resource="qc_sample_pool_item",
                outcome="unknown",
                details={"source_item_id": item_id},
                current_user=current_user,
            )
        except Exception:
            logging.getLogger(__name__).exception(
                "test_record_copy_unknown_audit_failed source_item_id=%s", item_id,
            )
        raise HTTPException(
            status_code=503,
            detail={"code": "copy_result_unknown", "message": str(exc)},
        ) from None
    except Exception as exc:
        logging.getLogger(__name__).error(
            "test_record_copy_failed error_type=%s", type(exc).__name__,
        )
        raise HTTPException(
            status_code=503,
            detail="测试病历复制结果未知，请刷新列表核对后再操作",
        ) from None
    audit_event(
        request,
        action="qc.sample_pools.test_records.copy",
        resource="qc_sample_pool_item",
        outcome="success",
        details={
            "source_item_id": item_id,
            "created_item_id": str((result.get("item") or {}).get("id") or ""),
        },
        current_user=current_user,
    )
    return success_response(
        data=result,
        message="测试病历副本已创建",
        trace_id=get_trace_id(request),
    )


@router.get("/test-records")
async def list_test_records(
    request: Request,
    include_removed: bool = Query(default=False, description="同时列出已移除与已被替换的条目"),
    q: Optional[str] = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    del current_user
    result = _service().list_customer_test_records(
        include_removed=include_removed, query=q, page=page, page_size=page_size,
    )
    return success_response(
        data={
            "items": result.items,
            "total": result.total,
            "page": result.page,
            "page_size": result.page_size,
        },
        message="获取测试病历成功",
        trace_id=get_trace_id(request),
    )


@router.get("/test-records/import-template")
async def download_test_record_import_template(
    current_user: Dict[str, Any] = Depends(require_roles("admin", "qc_manager")),
):
    del current_user
    content = await run_in_threadpool(build_test_record_import_template)
    return Response(
        content=content,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={
            "Content-Disposition": "attachment; filename*=UTF-8''V3.6-test-record-import-template.xlsx",
            "Cache-Control": "no-store",
            "X-Content-Type-Options": "nosniff",
        },
    )


@router.post("/test-records/import")
async def import_test_records(
    request: Request,
    file: UploadFile = File(..., description="V3.6 测试病历 .xlsx 模板"),
    current_user: Dict[str, Any] = Depends(require_roles("admin", "qc_manager")),
):
    filename = str(file.filename or "").strip()
    if Path(filename).suffix.lower() != ".xlsx":
        raise HTTPException(
            status_code=422,
            detail={
                "code": "invalid_test_record_import",
                "message": "测试病历导入仅支持 .xlsx 模板",
                "errors": [
                    {"sheet": "文件", "row": 0, "field": "文件", "message": "仅支持 .xlsx 文件"},
                ],
            },
        )
    actor_id = str(current_user.get("id") or current_user.get("user_id") or "").strip()
    if not actor_id or actor_id.lower() == "anonymous":
        raise HTTPException(status_code=403, detail="当前用户缺少稳定标识，无法导入测试病历")
    content = await file.read(MAX_UPLOAD_BYTES + 1)
    file_sha256 = hashlib.sha256(content).hexdigest()
    guard_key = f"{actor_id}:{file_sha256}"
    async with _ACTIVE_TEST_RECORD_IMPORTS_LOCK:
        if guard_key in _ACTIVE_TEST_RECORD_IMPORTS:
            raise HTTPException(status_code=409, detail="相同文件正在导入，请等待当前请求完成")
        _ACTIVE_TEST_RECORD_IMPORTS.add(guard_key)
    try:
        try:
            parsed_records = await run_in_threadpool(
                parse_test_record_import,
                content,
                allowed_rule_ids=_current_version_rule_ids(),
                file_sha256=file_sha256,
            )
        except TestRecordImportValidationError as exc:
            raise HTTPException(
                status_code=422,
                detail={
                    "code": "invalid_test_record_import",
                    "message": "模板校验失败，请按行修正后重新导入",
                    "errors": [item.as_dict() for item in exc.errors],
                },
            ) from exc

        results: list[dict[str, Any]] = []
        created_count = 0
        unknown_count = 0
        service = _service()
        for record in parsed_records:
            try:
                created = await run_in_threadpool(
                    service.create_customer_test_record,
                    payload=record.payload,
                    created_by=actor_id,
                )
                item = created.get("item") if isinstance(created.get("item"), dict) else {}
                receipt = {
                    "item_id": str(item.get("id") or "").strip(),
                    "institute_id": str(item.get("matched_institute_id") or "").strip(),
                    "patient_id": str(created.get("patient_id") or "").strip(),
                    "visit_id": str(created.get("visit_id") or "").strip(),
                }
                if not all(receipt.values()):
                    results.append(
                        {
                            "case_key": record.case_key,
                            "case_row": record.case_row,
                            "document_rows": list(record.document_rows),
                            "status": "unknown",
                            "message": "创建回执不完整，结果未知，请勿盲目重试；请刷新测试病历列表核对",
                        }
                    )
                    unknown_count += 1
                    continue
                bundle_error = bool(str(created.get("bundle_error") or "").strip())
                results.append(
                    {
                        "case_key": record.case_key,
                        "case_row": record.case_row,
                        "document_rows": list(record.document_rows),
                        "status": "created",
                        "message": (
                            "病历已创建，资料视图仍在准备，请稍后刷新"
                            if bundle_error or created.get("bundle_status") != "ready"
                            else "病历已创建"
                        ),
                        **receipt,
                        "bundle_status": str(created.get("bundle_status") or "pending"),
                    }
                )
                created_count += 1
            except Exception:
                logging.getLogger(__name__).warning(
                    "test_record_excel_import_result_unknown code=create_exception case_row=%s",
                    record.case_row,
                )
                results.append(
                    {
                        "case_key": record.case_key,
                        "case_row": record.case_row,
                        "document_rows": list(record.document_rows),
                        "status": "unknown",
                        "message": "创建结果未知，请勿盲目重试；请刷新测试病历列表并按名称核对",
                    }
                )
                unknown_count += 1

        audit_event(
            request,
            action="qc.sample_pools.test_records.import",
            resource="qc_sample_pool_item",
            outcome="success" if unknown_count == 0 else "partial",
            details={
                "file_sha256_prefix": file_sha256[:16],
                "total": len(parsed_records),
                "created": created_count,
                "unknown": unknown_count,
            },
            current_user=current_user,
        )
        return success_response(
            data={
                "total": len(parsed_records),
                "created": created_count,
                "unknown": unknown_count,
                "results": results,
            },
            message=(
                "测试病历导入已完成"
                if unknown_count == 0
                else "测试病历导入已结束，部分病例结果未知，请刷新列表核对"
            ),
            trace_id=get_trace_id(request),
        )
    finally:
        async with _ACTIVE_TEST_RECORD_IMPORTS_LOCK:
            _ACTIVE_TEST_RECORD_IMPORTS.discard(guard_key)


@router.put("/test-records/{item_id}/rules")
async def update_test_record_rules(
    request: Request,
    item_id: str,
    payload: TestRecordRulesUpdateRequest,
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    del current_user
    allowed_rule_ids = _current_version_rule_ids()
    try:
        item = _service().update_customer_test_record_rules(
            item_id=item_id,
            rule_ids=payload.rule_ids,
            expected_updated_at=payload.updated_at,
            allowed_rule_ids=allowed_rule_ids,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except (CustomerTestRecordNotFoundError, CustomerTestRecordConflictError) as exc:
        _raise_test_record_error(exc)
    return success_response(
        data=item,
        message="测试病历关联质控点已更新",
        trace_id=get_trace_id(request),
    )


@router.delete("/test-records/{item_id}")
async def remove_test_record(
    request: Request,
    item_id: str,
    updated_at: str = Query(..., min_length=1, description="条目当前 updated_at，用于 CAS"),
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    actor_id = str(current_user.get("id") or current_user.get("user_id") or "").strip()
    audit_details = {"item_id": item_id, "expected_updated_at": updated_at}
    if not actor_id or actor_id.lower() == "anonymous":
        audit_event(
            request,
            action="qc.sample_pools.test_records.remove",
            resource="qc_sample_pool_item",
            outcome="rejected",
            details={**audit_details, "code": "missing_actor"},
            current_user=current_user,
        )
        raise HTTPException(status_code=403, detail="当前用户缺少稳定标识，无法移除测试病历")
    try:
        item = _service().remove_customer_test_record(
            item_id=item_id,
            expected_updated_at=updated_at,
            actor_id=actor_id,
        )
    except CustomerTestRecordNotFoundError as exc:
        audit_event(
            request,
            action="qc.sample_pools.test_records.remove",
            resource="qc_sample_pool_item",
            outcome="rejected",
            details={**audit_details, "code": "not_found"},
            current_user=current_user,
        )
        _raise_test_record_error(exc)
    except CustomerTestRecordConflictError as exc:
        outcome = "conflict" if exc.code in {"stale", "inactive"} else "rejected"
        audit_event(
            request,
            action="qc.sample_pools.test_records.remove",
            resource="qc_sample_pool_item",
            outcome=outcome,
            details={**audit_details, "code": exc.code},
            current_user=current_user,
        )
        _raise_test_record_error(exc)
    audit_event(
        request,
        action="qc.sample_pools.test_records.remove",
        resource="qc_sample_pool_item",
        outcome="success",
        details={"item_id": item_id, "prior_updated_at": updated_at},
        current_user=current_user,
    )
    return success_response(
        data=item,
        message="测试病历已移除",
        trace_id=get_trace_id(request),
    )


@router.post("/import-manual-sheet")
async def import_manual_sheet(
    request: Request,
    payload: SamplePoolImportRequest,
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    file_path = os.path.abspath(payload.source_file)
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail=f"文件不存在: {file_path}")
    rows = load_manual_case_rows_from_excel(file_path=file_path, sheet_name=payload.source_sheet)
    if not rows:
        raise HTTPException(status_code=422, detail="Sheet 中未读取到有效样本行")
    pool = _service().create_pool_with_items(
        name=payload.pool_name,
        source_file=file_path,
        source_sheet=payload.source_sheet,
        created_by=_current_user_id(current_user),
        rows=rows,
        description=payload.description,
        scene=payload.scene,
    )
    return success_response(
        data={**pool, "imported_rows": len(rows)},
        message="客户样本池导入成功",
        trace_id=get_trace_id(request),
    )


@router.post("/import-upload")
async def import_manual_sheet_upload(
    request: Request,
    pool_name: str = Form(..., description="样本池名称"),
    source_sheet: str = Form(default="", description="Sheet 名称；为空时自动读取第一个工作表"),
    description: Optional[str] = Form(default=None, description="备注"),
    scene: str = Form(default="running", description="目标场景"),
    file: UploadFile = File(..., description="Excel 模板文件"),
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    filename = str(file.filename or "").strip()
    suffix = Path(filename).suffix.lower()
    if suffix not in {".xls", ".xlsx"}:
        raise HTTPException(status_code=422, detail="仅支持导入 .xls 或 .xlsx 模板文件")

    _IMPORT_UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    safe_stem = "".join(ch if ch.isalnum() or ch in ("-", "_") else "_" for ch in Path(filename).stem).strip("_")
    safe_stem = safe_stem or "manual_case_pool"
    saved_path = _IMPORT_UPLOAD_DIR / f"{safe_stem}-{uuid.uuid4().hex[:8]}{suffix}"

    content = await file.read()
    if not content:
        raise HTTPException(status_code=422, detail="上传文件为空")
    saved_path.write_bytes(content)

    rows = load_manual_case_rows_from_excel(file_path=str(saved_path), sheet_name=source_sheet)
    if not rows:
        raise HTTPException(status_code=422, detail="模板中未读取到有效样本行，请检查 Sheet 与表头格式")

    pool = _service().create_pool_with_items(
        name=str(pool_name).strip(),
        source_file=str(saved_path),
        source_sheet=str(source_sheet).strip() or "自动识别",
        created_by=_current_user_id(current_user),
        rows=rows,
        description=(description or "").strip() or None,
        scene=str(scene).strip() or "running",
    )
    return success_response(
        data={**pool, "imported_rows": len(rows)},
        message="客户样本模板导入成功",
        trace_id=get_trace_id(request),
    )


@router.get("/sheet2-exact-review/acceptance-package")
async def get_sheet2_exact_review_acceptance_package(
    request: Request,
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    if not _SHEET2_EXACT_REVIEW_ACCEPTANCE_JSON.exists():
        raise HTTPException(status_code=404, detail="Sheet2 精确复核验收包尚未生成")
    payload = json.loads(_SHEET2_EXACT_REVIEW_ACCEPTANCE_JSON.read_text(encoding="utf-8"))
    return success_response(
        data=payload,
        message="获取 Sheet2 精确复核验收包成功",
        trace_id=get_trace_id(request),
    )


@router.get("/rule-sets")
async def list_sample_validation_rule_set_catalog(
    request: Request,
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    return success_response(
        data={"items": list_sample_validation_rule_sets()},
        message="获取客户样本验证规则集成功",
        trace_id=get_trace_id(request),
    )


@router.get("/reports/luxian-0609")
async def download_luxian_0609_evaluation_report(
    request: Request,
    format: str = Query(default="md", description="导出格式：md/csv/json"),
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    normalized_format = str(format or "md").strip().lower()
    if normalized_format not in _LUXIAN_0609_REPORT_FILES:
        raise HTTPException(status_code=422, detail="仅支持导出 md、csv 或 json 格式")
    filename, media_type = _LUXIAN_0609_REPORT_FILES[normalized_format]
    file_path = _LUXIAN_0609_REPORT_DIR / filename
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="泸县0609质控点评估报告尚未生成")
    return FileResponse(
        path=str(file_path),
        media_type=media_type,
        filename=filename,
    )


@router.get("/source-admission-departments")
async def list_source_admission_departments(
    request: Request,
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    del current_user
    departments = _service().list_remote_admission_departments()
    return success_response(
        data={"items": departments},
        message="获取入院科室成功",
        trace_id=get_trace_id(request),
    )


@router.get("/{pool_id}")
async def get_sample_pool(
    request: Request,
    pool_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    pool = _service().get_pool(pool_id=pool_id)
    if not pool:
        raise HTTPException(status_code=404, detail="样本池不存在")
    return success_response(
        data=pool,
        message="获取客户样本池成功",
        trace_id=get_trace_id(request),
    )


@router.delete("/{pool_id}")
async def delete_sample_pool(
    request: Request,
    pool_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    del current_user
    result = _service().delete_pool(pool_id=pool_id)
    reason = str(result.get("reason") or "")
    if reason == "not_found":
        raise HTTPException(status_code=404, detail="样本池不存在或已删除")
    if reason == "protected_pool":
        raise HTTPException(status_code=409, detail="客户自建测试病历为系统样本池，不能删除")
    if reason == "active_sync_job":
        raise HTTPException(status_code=409, detail="该样本池仍有同步任务正在执行，请完成或停止后再删除")
    if reason == "active_qc_job":
        raise HTTPException(status_code=409, detail="该样本池仍有质控任务正在执行，请完成或停止后再删除")
    return success_response(
        data=result,
        message="样本池已删除",
        trace_id=get_trace_id(request),
    )


@router.get("/{pool_id}/items")
async def list_sample_pool_items(
    request: Request,
    pool_id: str,
    coverage_type: Optional[str] = Query(default=None),
    match_status: Optional[str] = Query(default=None),
    include_in_batch_1: Optional[bool] = Query(default=None),
    q: Optional[str] = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=200),
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    pool = _service().get_pool(pool_id=pool_id)
    if not pool:
        raise HTTPException(status_code=404, detail="样本池不存在")
    result = _service().list_pool_items(
        pool_id=pool_id,
        coverage_type=coverage_type,
        match_status=match_status,
        include_in_batch_1=include_in_batch_1,
        query=q,
        page=page,
        page_size=page_size,
    )
    return success_response(
        data={
            "pool": pool,
            "items": result.items,
            "total": result.total,
            "page": result.page,
            "page_size": result.page_size,
        },
        message="获取客户样本明细成功",
        trace_id=get_trace_id(request),
    )


@router.get("/{pool_id}/records")
async def list_sample_pool_records(
    request: Request,
    pool_id: str,
    coverage_type: Optional[str] = Query(default=None),
    match_status: Optional[str] = Query(default=None),
    include_in_batch_1: Optional[bool] = Query(default=None),
    q: Optional[str] = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=200),
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    pool = _service().get_pool(pool_id=pool_id)
    if not pool:
        raise HTTPException(status_code=404, detail="样本池不存在")
    result = _service().list_pool_records(
        pool_id=pool_id,
        coverage_type=coverage_type,
        match_status=match_status,
        include_in_batch_1=include_in_batch_1,
        query=q,
        page=page,
        page_size=page_size,
    )
    return success_response(
        data={
            "pool": pool,
            "items": result.items,
            "total": result.total,
            "page": result.page,
            "page_size": result.page_size,
        },
        message="获取客户样本病历列表成功",
        trace_id=get_trace_id(request),
    )


@router.post("/{pool_id}/match")
async def match_sample_pool(
    request: Request,
    pool_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    pool = _service().get_pool(pool_id=pool_id)
    if not pool:
        raise HTTPException(status_code=404, detail="样本池不存在")
    try:
        result = _service().match_pool_items_from_source(pool_id=pool_id)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"源库病历匹配失败: {exc}") from exc
    return success_response(
        data=result,
        message="客户样本病历匹配完成",
        trace_id=get_trace_id(request),
    )


@router.post("/{pool_id}/sync-records")
async def sync_sample_pool_records(
    request: Request,
    pool_id: str,
    payload: SamplePoolSyncRequest,
    background_tasks: BackgroundTasks,
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    pool = _service().get_pool(pool_id=pool_id)
    if not pool:
        raise HTTPException(status_code=404, detail="样本池不存在")
    try:
        job = _service().create_sync_job(
            pool_id=pool_id,
            created_by=_current_user_id(current_user),
            payload=payload.model_dump(exclude_unset=True),
        )
    except SampleSyncJobConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    background_tasks.add_task(_run_sample_pool_sync_job, job["id"])
    return success_response(
        data={
            "job_id": job["id"],
            "pool_id": pool_id,
            "status": job["status"],
            "summary": job["summary"],
        },
        message="样本病历定向同步任务已创建",
        trace_id=get_trace_id(request),
    )


@router.post("/{pool_id}/hospitalization-scope/preview")
async def preview_sample_pool_hospitalization_scope(
    request: Request,
    pool_id: str,
    payload: SamplePoolHospitalizationScopeRequest,
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    del current_user
    service = _service()
    pool = service.get_pool(pool_id=pool_id)
    if not pool:
        raise HTTPException(status_code=404, detail="样本池不存在")
    normalized = _normalize_hospitalization_scope_payload(payload)
    try:
        result = service.preview_hospitalization_scope(
            pool_id=pool_id,
            scope_mode=normalized["mode"],
            as_of_date=date.fromisoformat(normalized["as_of_date"]),
            discharge_start_date=date.fromisoformat(normalized["discharge_start_date"])
            if normalized["discharge_start_date"]
            else None,
            discharge_end_date=date.fromisoformat(normalized["discharge_end_date"])
            if normalized["discharge_end_date"]
            else None,
            departments=normalized["departments"],
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return success_response(
        data=result,
        message="住院范围预览已更新",
        trace_id=get_trace_id(request),
    )


@router.post("/{pool_id}/sync-by-hospitalization")
async def sync_sample_pool_by_hospitalization(
    request: Request,
    pool_id: str,
    payload: SamplePoolHospitalizationScopeRequest,
    background_tasks: BackgroundTasks,
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    service = _service()
    pool = service.get_pool(pool_id=pool_id)
    if not pool:
        raise HTTPException(status_code=404, detail="样本池不存在")
    normalized = _normalize_hospitalization_scope_payload(payload)
    job_payload = {
        "only_intrinsic": False,
        "include_in_batch_1": False,
        "hospitalization_scope": normalized,
    }
    try:
        job = service.create_sync_job(
            pool_id=pool_id,
            created_by=_current_user_id(current_user),
            payload=job_payload,
        )
    except SampleSyncJobConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    background_tasks.add_task(_run_sample_pool_sync_job, job["id"])
    return success_response(
        data={
            "job_id": job["id"],
            "pool_id": pool_id,
            "status": job["status"],
            "summary": job["summary"],
        },
        message="住院范围同步任务已创建",
        trace_id=get_trace_id(request),
    )


@router.post("/{pool_id}/sync-by-admission", deprecated=True)
async def sync_sample_pool_by_admission(
    request: Request,
    pool_id: str,
    payload: SamplePoolAdmissionSyncRequest,
    background_tasks: BackgroundTasks,
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    if payload.start_date > payload.end_date:
        raise HTTPException(status_code=422, detail="入院开始日期不能晚于结束日期")
    if (payload.end_date - payload.start_date).days > 30:
        raise HTTPException(status_code=422, detail="入院日期范围最多 31 天")
    pool = _service().get_pool(pool_id=pool_id)
    if not pool:
        raise HTTPException(status_code=404, detail="样本池不存在")
    departments = list(dict.fromkeys(item.strip() for item in payload.departments if item.strip()))
    job_payload = {
        "only_intrinsic": False,
        "include_in_batch_1": False,
        "admission_filter": {
            "start_date": payload.start_date.isoformat(),
            "end_date": payload.end_date.isoformat(),
            "departments": departments,
        },
    }
    try:
        job = _service().create_sync_job(
            pool_id=pool_id,
            created_by=_current_user_id(current_user),
            payload=job_payload,
        )
    except SampleSyncJobConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    background_tasks.add_task(_run_sample_pool_sync_job, job["id"])
    return success_response(
        data={
            "job_id": job["id"],
            "pool_id": pool_id,
            "status": job["status"],
            "summary": job["summary"],
        },
        message="按条件同步病历任务已创建",
        trace_id=get_trace_id(request),
    )


@router.get("/{pool_id}/sync-jobs/latest")
async def get_latest_sample_pool_sync_job(
    request: Request,
    pool_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    pool = _service().get_pool(pool_id=pool_id)
    if not pool:
        raise HTTPException(status_code=404, detail="样本池不存在")
    job = _service().get_latest_sync_job(pool_id=pool_id)
    return success_response(
        data=job,
        message="获取样本同步任务成功",
        trace_id=get_trace_id(request),
    )


@router.get("/sync-jobs/{job_id}")
async def get_sample_pool_sync_job(
    request: Request,
    job_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    job = _service().get_sync_job(job_id=job_id)
    if not job:
        raise HTTPException(status_code=404, detail="同步任务不存在")
    return success_response(
        data=job,
        message="获取样本同步任务成功",
        trace_id=get_trace_id(request),
    )


@router.post("/{pool_id}/run")
async def run_sample_pool_intrinsic_validation(
    request: Request,
    pool_id: str,
    payload: SamplePoolRunRequest,
    current_user: Dict[str, Any] = Depends(get_current_user),
    _: Dict[str, Any] = Depends(require_product_activation),
):
    if payload.record_ids:
        raise HTTPException(
            status_code=422,
            detail="record_ids 已停止用于新质控任务，请提交完整 record_refs 三坐标",
        )
    service = _service()
    pool = service.get_pool(pool_id=pool_id)
    if not pool:
        raise HTTPException(status_code=404, detail="样本池不存在")

    requested_rule_set_key = str(payload.rule_set_key or "").strip()
    resolved_rule_set = None
    validation_mode = str(payload.validation_mode or "customer").strip().lower() or "customer"
    if requested_rule_set_key:
        try:
            resolved = resolve_sample_validation_rule_set_by_key(requested_rule_set_key)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        validation_mode = str(resolved["validation_mode"])
        resolved_rule_set = resolved["rule_set"]
    if validation_mode not in {"customer", "sc", "programmatic", FORMAL_FAST_SCREEN_FULL_MODE}:
        raise HTTPException(status_code=422, detail="未知验证模式，仅支持 customer、sc、programmatic 或 formal_fast_screen_full")
    is_formal_fast_screen_full = validation_mode == FORMAL_FAST_SCREEN_FULL_MODE
    requested_selected_rule_ids = _normalize_rule_id_list(payload.selected_rule_ids)
    explicit_fields = set(getattr(payload, "model_fields_set", set()) or set())
    if "selected_rule_ids" in explicit_fields and not requested_selected_rule_ids:
        raise HTTPException(status_code=422, detail="所选质控点不能为空")
    selected_customer_delivery_rule_ids = list(requested_selected_rule_ids)
    if requested_selected_rule_ids and validation_mode != "customer":
        raise HTTPException(status_code=422, detail="selected_rule_ids 仅支持客户专项规则验证模式")
    requested_record_ref_values = [
        CaseRef(item.institute_id, item.patient_id, item.visit_id)
        for item in list(payload.record_refs or [])
    ]
    requested_record_refs = (
        normalize_case_refs(requested_record_ref_values)
        if requested_record_ref_values
        else ()
    )
    if len(requested_record_refs) != len(requested_record_ref_values):
        raise HTTPException(status_code=422, detail="所选病历三坐标存在重复")
    requested_sample_item_ids = [
        str(item_id or "").strip()
        for item_id in list(payload.sample_item_ids or [])
        if str(item_id or "").strip()
    ]
    if "sample_item_ids" in explicit_fields and payload.sample_item_ids and not requested_sample_item_ids:
        raise HTTPException(status_code=422, detail="所选样本不能为空")
    if len(set(requested_sample_item_ids)) != len(requested_sample_item_ids):
        raise HTTPException(status_code=422, detail="所选样本存在重复")
    if bool(requested_sample_item_ids) != bool(requested_record_refs):
        raise HTTPException(
            status_code=422,
            detail="显式选择病历时必须同时提交 sample_item_ids 与 record_refs",
        )
    requires_explicit_sample_selection = (
        is_formal_fast_screen_full
        or requested_rule_set_key in {
            LUXIAN_0609_QC_RULE_SET_KEY,
            LUXIAN_0916_QC_RULE_SET_KEY,
        }
    )
    if requires_explicit_sample_selection and not (
        requested_sample_item_ids or requested_record_refs
    ):
        selection_name = (
            "正式84条质控"
            if is_formal_fast_screen_full
            else "Luxian0916质控"
            if requested_rule_set_key == LUXIAN_0916_QC_RULE_SET_KEY
            else "泸县0609质控"
        )
        raise HTTPException(status_code=422, detail=f"{selection_name}请先选择病历")

    if requested_sample_item_ids or not requested_record_refs:
        readiness = service.inspect_run_selection(
            pool_id=pool_id,
            validation_mode=validation_mode,
            item_ids=requested_sample_item_ids,
            record_ids=[],
        )
        if not bool(readiness.get("ready")):
            readiness_messages = {
                "missing_item": "所选样本不存在或不属于当前样本池",
                "missing_record": "所选病历未匹配到当前样本池",
                "selection_mismatch": "所选样本与病历范围不一致",
                "ambiguous": "所选样本的病历匹配存在歧义",
                "unmatched": "所选样本包含未匹配病历",
                "not_synced": "所选样本尚未同步到本地",
                "bundle_not_ready": "所选样本的病历包尚未就绪",
                "empty_selection": "当前样本池没有可执行样本",
            }
            reason_code = str(readiness.get("reason_code") or "empty_selection")
            raise HTTPException(
                status_code=422,
                detail=readiness_messages.get(reason_code, "所选样本当前不可执行"),
            )

    runnable_items = service.get_runnable_items(
        pool_id=pool_id,
        validation_mode=validation_mode,
        item_ids=requested_sample_item_ids,
        record_ids=[],
    )
    if requested_sample_item_ids:
        runnable_item_ids = {
            str(item.get("id") or "").strip()
            for item in runnable_items
            if str(item.get("id") or "").strip()
        }
        if runnable_item_ids != set(requested_sample_item_ids):
            raise HTTPException(status_code=422, detail="所选样本范围已变化，请刷新后重试")
    if not runnable_items:
        if requested_record_refs:
            raise HTTPException(status_code=422, detail="当前选中病历没有可执行的样本问题")
        if requested_sample_item_ids:
            raise HTTPException(status_code=422, detail="当前选中样本没有可执行的病历")
        raise HTTPException(status_code=422, detail="当前样本池没有可执行的样本病历")

    candidate_record_refs = [
        CaseRef(
            str(item.get("matched_institute_id") or "").strip(),
            str(item.get("matched_patient_id") or "").strip(),
            str(item.get("matched_visit_id") or "").strip(),
        )
        for item in runnable_items
    ]
    if not candidate_record_refs or not all(all(ref) for ref in candidate_record_refs):
        raise HTTPException(status_code=422, detail="样本病历缺少完整三坐标，无法创建质控任务")
    record_refs = normalize_case_refs(candidate_record_refs)
    if requested_record_refs and set(record_refs) != set(requested_record_refs):
        raise HTTPException(status_code=422, detail="所选样本与病历三坐标范围不一致，请刷新后重试")
    record_ids = sorted({record_ref.visit_id for record_ref in record_refs})
    selected_record_count = len(record_refs) if requested_record_refs or requested_sample_item_ids else 0
    record_rule_map: Dict[str, list[str]] = {}
    if not is_formal_fast_screen_full and resolved_rule_set is None:
        for item in runnable_items:
            record_ref = CaseRef(
                str(item.get("matched_institute_id") or "").strip(),
                str(item.get("matched_patient_id") or "").strip(),
                str(item.get("matched_visit_id") or "").strip(),
            )
            record_map_key = record_ref.as_key()
            bucket = record_rule_map.setdefault(record_map_key, [])
            for rule_id in list(item.get("candidate_rule_ids") or []):
                normalized_rule_id = str(rule_id or "").strip()
                if normalized_rule_id and normalized_rule_id not in bucket:
                    bucket.append(normalized_rule_id)
    if not record_refs:
        raise HTTPException(status_code=422, detail="当前样本池没有已匹配的病历")

    if resolved_rule_set is not None:
        rule_ids = [str(rule_id).strip() for rule_id in resolved_rule_set.rule_ids if str(rule_id).strip()]
        rule_set_key = resolved_rule_set.key
        rule_set_name = resolved_rule_set.name
        rule_set_version = resolved_rule_set.version
    elif validation_mode == "customer":
        effective_rule_set_key = requested_rule_set_key or CUSTOMER_LUXIAN_RULE_SET_KEY
        if effective_rule_set_key == CUSTOMER_LUXIAN_RULE_SET_KEY:
            customer_rule_set = get_customer_luxian_rule_set()
        else:
            raise HTTPException(status_code=422, detail=f"未知客户规则包: {effective_rule_set_key}")
        rule_ids = sorted({str(rule_id).strip() for rule_id in customer_rule_set.rule_ids if str(rule_id).strip()})
        rule_set_key = customer_rule_set.key
        rule_set_name = customer_rule_set.name
        rule_set_version = customer_rule_set.version
    elif validation_mode == "sc":
        rule_ids = sorted(
            {
                str(rule_id).strip()
                for item in runnable_items
                for rule_id in (item.get("candidate_rule_ids") or [])
                if str(rule_id).strip()
            }
        )
        rule_set_key = ""
        rule_set_name = "SC样本规则模式"
        rule_set_version = "running-batch-1"
    elif validation_mode == "programmatic":
        programmatic_rule_set = get_sample_programmatic_rule_set()
        rule_ids = list(programmatic_rule_set.rule_ids)
        rule_set_key = programmatic_rule_set.key
        rule_set_name = programmatic_rule_set.name
        rule_set_version = programmatic_rule_set.version
    else:
        requested_rule_set_key = requested_rule_set_key or FORMAL_FAST_SCREEN_FULL_RULE_SET_KEY
        if requested_rule_set_key != FORMAL_FAST_SCREEN_FULL_RULE_SET_KEY:
            raise HTTPException(status_code=422, detail=f"正式质控 84 条仅支持规则集: {FORMAL_FAST_SCREEN_FULL_RULE_SET_KEY}")
        formal_rule_set = get_sichuan_rule_set(FORMAL_FAST_SCREEN_FULL_RULE_SET_KEY)
        if not formal_rule_set:
            raise HTTPException(status_code=422, detail=f"未知规则集: {FORMAL_FAST_SCREEN_FULL_RULE_SET_KEY}")
        rule_ids = [str(rule_id).strip() for rule_id in formal_rule_set.rule_ids if str(rule_id).strip()]
        rule_set_key = formal_rule_set.key
        rule_set_name = formal_rule_set.name
        rule_set_version = formal_rule_set.version

    if rule_set_key == LUXIAN_0609_QC_RULE_SET_KEY:
        paused_selected_rule_ids = [
            rule_id
            for rule_id in requested_selected_rule_ids
            if rule_id in _LUXIAN_0609_PAUSED_CUSTOMER_RULE_IDS
        ]
        requested_selected_rule_ids = [
            rule_id
            for rule_id in requested_selected_rule_ids
            if rule_id not in _LUXIAN_0609_PAUSED_CUSTOMER_RULE_IDS
        ]
        rule_ids = [
            rule_id
            for rule_id in rule_ids
            if str(rule_id).strip().upper() not in _LUXIAN_0609_PAUSED_CUSTOMER_RULE_IDS
        ]
        if paused_selected_rule_ids and not requested_selected_rule_ids:
            raise HTTPException(
                status_code=422,
                detail="所选质控点当前均暂不执行，请调整质控范围",
            )
        # 目录仍展示全部 75 条规则；将本次未进入执行器的规则明确传给 worker，
        # 避免客户结果层把“策略暂停”误投影为“未返回执行结果”。
        paused_customer_rule_ids = (
            paused_selected_rule_ids
            if requested_selected_rule_ids
            else sorted(_LUXIAN_0609_PAUSED_CUSTOMER_RULE_IDS)
        )
    else:
        paused_customer_rule_ids = []

    selected_execution_rule_ids: list[str] = []
    if requested_selected_rule_ids:
        if rule_set_key != LUXIAN_0609_QC_RULE_SET_KEY:
            raise HTTPException(status_code=422, detail="selected_rule_ids 当前仅支持泸县0609质控点验证")
        allowed_rule_ids = {str(rule_id or "").strip().upper() for rule_id in list(rule_ids or [])}
        execution_rule_ids, invalid_rule_ids, gate_only_customer_rule_ids = _resolve_luxian_0609_execution_scope(
            requested_selected_rule_ids,
            allowed_rule_ids=allowed_rule_ids,
        )
        if invalid_rule_ids:
            raise HTTPException(
                status_code=422,
                detail=f"所选质控点不属于当前规则集: {', '.join(invalid_rule_ids)}",
            )
        rule_ids = execution_rule_ids
        selected_execution_rule_ids = list(execution_rule_ids)
        record_rule_map = (
            {record_ref.as_key(): list(execution_rule_ids) for record_ref in record_refs}
            if execution_rule_ids
            else {}
        )
    else:
        gate_only_customer_rule_ids = []

    if not rule_ids and not gate_only_customer_rule_ids:
        raise HTTPException(status_code=422, detail="当前样本池没有可执行规则")
    customer_rule_count = (
        len(selected_customer_delivery_rule_ids)
        if selected_customer_delivery_rule_ids
        else len(rule_ids) + len(paused_customer_rule_ids)
        if rule_set_key == LUXIAN_0609_QC_RULE_SET_KEY
        else len(rule_ids)
    )
    execution_strategy = (
        EXECUTION_STRATEGY_FAST_SCREEN
        if is_formal_fast_screen_full
        else _resolve_sample_validation_execution_strategy(
            validation_mode=validation_mode,
            rule_ids=rule_ids,
        )
    )

    workspace = _workspace_service()
    runtime_config = await LLMConfigLoader.load_config(config_name="default", user_id=None)
    execution_concurrency = concurrency_from_custom_parameters(
        (runtime_config or {}).get("custom_parameters") or {}
    )
    # 单次任务可以选择更低值，但不能突破系统模型设置中的病历并发上限。
    # 规则族子任务沿用该有效值，避免拆分后意外退化为单病历串行。
    effective_max_parallel_records = min(
        execution_concurrency.max_parallel_records,
        max(
            1,
            int(
                payload.max_parallel_records
                or execution_concurrency.max_parallel_records
            ),
        ),
    )
    requested_scope = "final" if is_formal_fast_screen_full else str(pool.get("scene") or "running").strip().lower() or "running"
    effective_scope = requested_scope
    selected_records = workspace.collect_records(
        scope=effective_scope,
        department=payload.department,
        doctor=payload.doctor,
        date_field="admission",
        start_date=None,
        end_date=None,
        keyword=None,
        record_ids=None,
        record_refs=record_refs,
    )
    record_count = len(selected_records)
    if record_count == 0 and is_formal_fast_screen_full:
        raise HTTPException(status_code=422, detail="选中病历未同步为终末病历，无法发起正式终末质控")

    def _workspace_record_refs(records: list[Dict[str, Any]]) -> tuple[CaseRef, ...]:
        candidates = [CaseRef.from_mapping(record) for record in records]
        if candidates and not all(all(ref) for ref in candidates):
            raise HTTPException(status_code=422, detail="样本病历缺少完整三坐标，无法创建质控任务")
        refs = normalize_case_refs(candidates) if candidates else ()
        if len(refs) != len(candidates):
            raise HTTPException(status_code=422, detail="样本病历三坐标关联不唯一，无法创建质控任务")
        return refs

    selected_record_refs = _workspace_record_refs(selected_records)
    if set(selected_record_refs) != set(record_refs) and effective_scope != "all":
        fallback_records = workspace.collect_records(
            scope="all",
            department=payload.department,
            doctor=payload.doctor,
            date_field="admission",
            start_date=None,
            end_date=None,
            keyword=None,
            record_ids=None,
            record_refs=record_refs,
        )
        fallback_record_refs = _workspace_record_refs(fallback_records)
        if set(fallback_record_refs) == set(record_refs):
            record_count = len(fallback_records)
            effective_scope = "all"
            selected_records = fallback_records
            selected_record_refs = fallback_record_refs
    if record_count == 0:
        raise HTTPException(status_code=422, detail="样本池匹配病历未同步到当前 PG，无法执行")
    if set(selected_record_refs) != set(record_refs):
        raise HTTPException(status_code=422, detail="样本病历三坐标未完整命中当前病历池，请刷新后重试")
    if effective_scope in {"final", "all"}:
        raise HTTPException(
            status_code=422,
            detail="final_archive_unverified: 归档状态未核验，终末或包含终末的混合范围暂不能执行质控任务",
        )
    record_refs = selected_record_refs
    if selected_execution_rule_ids:
        record_rule_map = {
            record_ref.as_key(): list(selected_execution_rule_ids)
            for record_ref in record_refs
        }
    elif record_rule_map:
        exact_rule_map = dict(record_rule_map)
        mapped_rule_map: dict[str, list[str]] = {}
        for record_ref in record_refs:
            mapped_rules = list(exact_rule_map.get(record_ref.as_key()) or [])
            if mapped_rules:
                mapped_rule_map[record_ref.as_key()] = mapped_rules
        record_rule_map = mapped_rule_map
    record_scene_snapshot = _build_workspace_record_scene_snapshot(
        selected_records,
        query_scope=effective_scope,
    )
    task_frozen_date = (
        datetime.now().astimezone().date().isoformat()
        if rule_set_key == LUXIAN_0609_QC_RULE_SET_KEY
        else ""
    )
    record_evaluation_snapshot = (
        build_record_evaluation_horizon_snapshot(
            selected_records,
            task_frozen_date=task_frozen_date,
        )
        if task_frozen_date
        else []
    )

    pseudo_draft = resolve_sample_validation_pseudo_draft(
        validation_mode=validation_mode,
        pool_name=str(pool.get("name") or ""),
        rule_count=len(rule_ids),
        rule_set_key=rule_set_key,
        rule_set_name=rule_set_name,
    )
    job_filters = {
        "rule_ids": rule_ids,
        "rule_set_key": rule_set_key,
        "rule_set_name": rule_set_name,
        "rule_set_version": rule_set_version,
        "rule_count": len(rule_ids),
        "customer_rule_count": customer_rule_count,
        "execution_rule_count": len(rule_ids),
        "gate_only_customer_rule_ids": gate_only_customer_rule_ids,
        "gate_only_customer_rule_count": len(gate_only_customer_rule_ids),
        "paused_customer_rule_ids": paused_customer_rule_ids,
        "paused_customer_rule_count": len(paused_customer_rule_ids),
        "execution_strategy": execution_strategy,
        "quality_profile": "throughput_v1",
        "bucket_strategy": "fixed_packs",
        "batch_output_mode": "minimal",
        "enable_selective_refine": False,
        "refine_confidence_threshold": 0.0,
        "max_refine_candidates": 0,
        "source": "manual_sample_formal_fast_screen_full" if is_formal_fast_screen_full else "manual_problem_sample_pool",
        "sample_pool_id": pool_id,
        "selected_rule_ids": requested_selected_rule_ids,
        "selected_record_ids": record_ids if selected_record_count else [],
        "scoped_customer_rule_ids": selected_customer_delivery_rule_ids,
        "selected_sample_item_ids": [str(item.get("id") or "").strip() for item in runnable_items if str(item.get("id") or "").strip()],
        "selected_sample_count": len(runnable_items),
        "dedup_record_count": len(record_refs),
        "department": payload.department,
        "doctor": payload.doctor,
        "temperature": payload.temperature,
        "top_p": payload.top_p,
        "max_tokens": payload.max_tokens,
        "model_code": payload.model_code,
        "max_parallel_records": effective_max_parallel_records,
        "effective_scope": effective_scope,
        "query_scope": effective_scope,
        "validation_mode": validation_mode,
        "record_scene_snapshot": record_scene_snapshot,
        **({"task_frozen_date": task_frozen_date} if task_frozen_date else {}),
        **(
            {"record_evaluation_snapshot": record_evaluation_snapshot}
            if record_evaluation_snapshot
            else {}
        ),
    }
    if rule_set_key == LUXIAN_0916_QC_RULE_SET_KEY:
        job_filters["bucket_strategy"] = "domain_only"
        for legacy_scope_key in (
            "selected_rule_ids",
            "scoped_customer_rule_ids",
            "gate_only_customer_rule_ids",
            "gate_only_customer_rule_count",
            "paused_customer_rule_ids",
            "paused_customer_rule_count",
        ):
            job_filters.pop(legacy_scope_key, None)
    if record_rule_map:
        job_filters["record_rule_map"] = record_rule_map

    luxian_family_scopes: list[dict[str, Any]] = []
    paused_rule_ids_by_family: dict[str, list[str]] = {}
    if payload.group_by_luxian_family and rule_set_key == LUXIAN_0609_QC_RULE_SET_KEY:
        luxian_scope_rule_ids = selected_customer_delivery_rule_ids
        if not luxian_scope_rule_ids:
            luxian_scope_rule_ids = _normalize_rule_id_list(rule_ids)
        luxian_family_scopes = _build_luxian_0609_family_scopes(luxian_scope_rule_ids)
        paused_rule_ids_by_family = {
            str(scope.get("key") or "").strip(): _normalize_rule_id_list(
                list(scope.get("rule_ids") or [])
            )
            for scope in _build_luxian_0609_family_scopes(paused_customer_rule_ids)
            if str(scope.get("key") or "").strip()
        }

    selected_sample_item_ids = [
        str(item.get("id") or "").strip()
        for item in runnable_items
        if str(item.get("id") or "").strip()
    ]
    if rule_set_key in {CUSTOMER_LUXIAN_RULE_SET_KEY, LUXIAN_0609_QC_RULE_SET_KEY}:
        identity_rule_ids = selected_customer_delivery_rule_ids or (
            _normalize_rule_id_list(rule_ids + paused_customer_rule_ids)
            if rule_set_key == LUXIAN_0609_QC_RULE_SET_KEY
            else _normalize_rule_id_list(rule_ids)
        )
    else:
        identity_rule_ids = list(rule_ids)
    created_by = _current_user_id(current_user)
    execution_scope_hash = build_sample_validation_execution_scope_hash(
        created_by=created_by,
        pool_id=pool_id,
        validation_mode=validation_mode,
        rule_set_key=rule_set_key,
        selected_rule_ids=identity_rule_ids,
        record_ids=record_ids,
        record_refs=record_refs,
        sample_item_ids=selected_sample_item_ids,
        group_by_luxian_family=bool(payload.group_by_luxian_family),
        effective_scope=effective_scope,
        execution_options={
            "model_code": payload.model_code,
            "temperature": payload.temperature,
            "top_p": payload.top_p,
            "max_tokens": payload.max_tokens,
            "max_parallel_records": effective_max_parallel_records,
            "rule_set_version": rule_set_version,
            "record_scene_snapshot": record_scene_snapshot,
            **(
                {"record_evaluation_snapshot": record_evaluation_snapshot}
                if record_evaluation_snapshot
                else {}
            ),
            **({"task_frozen_date": task_frozen_date} if task_frozen_date else {}),
        },
    )
    duplicate_job = _find_recent_sample_validation_job(
        workspace=workspace,
        created_by=created_by,
        execution_scope_hash=execution_scope_hash,
    )
    if duplicate_job is not None:
        duplicate_filters = duplicate_job.get("filters") if isinstance(duplicate_job.get("filters"), dict) else {}
        return success_response(
            data={
                "pool_id": pool_id,
                "job_id": str(duplicate_job.get("id") or "").strip(),
                "job_kind": str(duplicate_job.get("job_kind") or "leaf").strip() or "leaf",
                "child_job_ids": list(duplicate_job.get("child_job_ids") or []),
                "family_scopes": luxian_family_scopes,
                "sample_item_count": len(runnable_items),
                "selected_record_count": selected_record_count,
                "record_count": record_count,
                "rule_count": len(rule_ids),
                "customer_rule_count": customer_rule_count,
                "execution_rule_count": len(rule_ids),
                "gate_only_customer_rule_ids": gate_only_customer_rule_ids,
                "gate_only_customer_rule_count": len(gate_only_customer_rule_ids),
                "selected_rule_ids": requested_selected_rule_ids,
                "scoped_customer_rule_ids": selected_customer_delivery_rule_ids,
                "record_rule_map": record_rule_map,
                "record_ids": record_ids,
                "rule_ids": rule_ids,
                "validation_mode": validation_mode,
                "rule_set_key": rule_set_key,
                "rule_set_name": rule_set_name,
                "rule_set_version": rule_set_version,
                "operation_ref": str(duplicate_filters.get("operation_ref") or "").strip(),
                "execution_scope_hash": execution_scope_hash,
                "deduplicated": True,
            },
            message="相同样本与规则范围的近期任务已存在，已复用原任务",
            trace_id=get_trace_id(request),
        )

    operation_ref = _sample_validation_operation_ref()
    job_filters["operation_ref"] = operation_ref
    job_filters["execution_scope_hash"] = execution_scope_hash

    if len(luxian_family_scopes) > 1:
        parent_filters = {
            **job_filters,
            "group_by_luxian_family": True,
            "family_scopes": luxian_family_scopes,
            "selected_rule_ids": [
                rule_id
                for family_scope in luxian_family_scopes
                for rule_id in list(family_scope.get("rule_ids") or [])
            ],
            "scoped_customer_rule_ids": [
                rule_id
                for family_scope in luxian_family_scopes
                for rule_id in list(family_scope.get("rule_ids") or [])
            ],
        }
        parent_job = workspace.create_batch_job(
            draft=pseudo_draft,
            created_by=created_by,
            scope=effective_scope,
            filters=parent_filters,
            record_ids=record_ids,
            total_records=record_count,
            record_refs=record_refs,
            draft_ids=parent_filters["scoped_customer_rule_ids"],
            execution_mode="multi",
            run_mode="parallel",
            rule_count=len(parent_filters["scoped_customer_rule_ids"]),
            job_kind="parent",
            child_summary={
                "mode": "luxian_0609_family_parallel",
                "family_count": len(luxian_family_scopes),
            },
        )
        parent_job_id = str(parent_job.get("id") or "").strip()
        allowed_execution_rule_ids = {str(rule_id or "").strip().upper() for rule_id in list(rule_ids or [])}
        child_jobs: list[dict[str, Any]] = []
        child_job_ids: list[str] = []
        for family_scope in luxian_family_scopes:
            family_rule_ids = _normalize_rule_id_list(list(family_scope.get("rule_ids") or []))
            family_key = str(family_scope.get("key") or "").strip()
            family_paused_rule_ids = paused_rule_ids_by_family.get(family_key, [])
            family_delivery_rule_ids = _normalize_rule_id_list(
                [
                    *family_rule_ids,
                    *family_paused_rule_ids,
                ]
            )
            family_execution_rule_ids, invalid_family_rule_ids, family_gate_only_rule_ids = (
                _resolve_luxian_0609_execution_scope(
                    family_rule_ids,
                    allowed_rule_ids=allowed_execution_rule_ids,
                )
            )
            if invalid_family_rule_ids:
                raise HTTPException(
                    status_code=422,
                    detail=f"{family_scope.get('name') or '规则族'}包含无效质控点: {', '.join(invalid_family_rule_ids)}",
                )
            if not family_execution_rule_ids and not family_gate_only_rule_ids:
                raise HTTPException(
                    status_code=422,
                    detail=f"{family_scope.get('name') or '规则族'}当前没有可执行的映射规则",
                )
            family_record_rule_map = (
                {
                    record_ref.as_key(): list(family_execution_rule_ids)
                    for record_ref in record_refs
                }
                if family_execution_rule_ids
                else {}
            )
            child_filters = {
                **job_filters,
                "rule_ids": family_execution_rule_ids,
                "rule_count": len(family_execution_rule_ids),
                "customer_rule_count": len(family_delivery_rule_ids),
                "execution_rule_count": len(family_execution_rule_ids),
                "gate_only_customer_rule_ids": family_gate_only_rule_ids,
                "gate_only_customer_rule_count": len(family_gate_only_rule_ids),
                "paused_customer_rule_ids": family_paused_rule_ids,
                "paused_customer_rule_count": len(family_paused_rule_ids),
                "selected_rule_ids": family_rule_ids,
                "scoped_customer_rule_ids": family_delivery_rule_ids,
                "record_rule_map": family_record_rule_map,
                "group_by_luxian_family": False,
                "parent_job_id": parent_job_id,
                "family_key": family_key,
                "family_name": str(family_scope.get("name") or "").strip(),
                "max_parallel_records": effective_max_parallel_records,
            }
            child_job = workspace.create_batch_job(
                draft=pseudo_draft,
                created_by=created_by,
                scope=effective_scope,
                filters=child_filters,
                record_ids=record_ids,
                total_records=record_count,
                record_refs=record_refs,
                draft_ids=family_execution_rule_ids,
                execution_mode="multi",
                run_mode="parallel",
                rule_count=len(family_rule_ids),
                job_kind="child",
                parent_job_id=parent_job_id,
                family_key=str(family_scope.get("key") or "").strip(),
                family_name=str(family_scope.get("name") or "").strip(),
            )
            child_jobs.append(child_job)
            child_job_ids.append(str(child_job.get("id") or "").strip())

        parent_job = workspace.update_parent_child_jobs(
            parent_job_id=parent_job_id,
            created_by=created_by,
            child_job_ids=child_job_ids,
            child_summary={
                "mode": "luxian_0609_family_parallel",
                "family_count": len(luxian_family_scopes),
                "families": [
                    {
                        "key": str(family_scope.get("key") or "").strip(),
                        "name": str(family_scope.get("name") or "").strip(),
                        "rule_ids": list(family_scope.get("rule_ids") or []),
                        "job_id": child_job_ids[index] if index < len(child_job_ids) else "",
                    }
                    for index, family_scope in enumerate(luxian_family_scopes)
                ],
            },
        ) or parent_job
        service.update_pool_latest_job(pool_id=pool_id, job_id=parent_job_id, job_status="queued")
        for child_job_id in child_job_ids:
            submit_detached_task(
                "sample_pool_luxian_family_child_batch_job",
                _run_sichuan_workspace_batch_job,
                child_job_id,
            )
        return success_response(
            data={
                "pool_id": pool_id,
                "job_id": parent_job_id,
                "job_kind": "parent",
                "child_job_ids": child_job_ids,
                "child_jobs": child_jobs,
                "family_scopes": luxian_family_scopes,
                "sample_item_count": len(runnable_items),
                "selected_record_count": selected_record_count,
                "record_count": record_count,
                "rule_count": len(rule_ids),
                "customer_rule_count": len(parent_filters["scoped_customer_rule_ids"]),
                "execution_rule_count": len(rule_ids),
                "gate_only_customer_rule_ids": parent_filters.get("gate_only_customer_rule_ids") or [],
                "gate_only_customer_rule_count": int(parent_filters.get("gate_only_customer_rule_count") or 0),
                "selected_rule_ids": parent_filters["selected_rule_ids"],
                "scoped_customer_rule_ids": parent_filters["scoped_customer_rule_ids"],
                "record_rule_map": parent_filters.get("record_rule_map"),
                "record_ids": record_ids,
                "rule_ids": rule_ids,
                "validation_mode": validation_mode,
                "rule_set_key": rule_set_key,
                "rule_set_name": rule_set_name,
                "rule_set_version": rule_set_version,
                "operation_ref": operation_ref,
                "execution_scope_hash": execution_scope_hash,
                "deduplicated": False,
            },
            message="泸县0609总任务已创建，规则族子任务已并发入队",
            trace_id=get_trace_id(request),
        )

    job = workspace.create_batch_job(
        draft=pseudo_draft,
        created_by=_current_user_id(current_user),
        scope=effective_scope,
        filters=job_filters,
        record_ids=record_ids,
        total_records=record_count,
        record_refs=record_refs,
        draft_ids=rule_ids,
        execution_mode="multi",
        run_mode="parallel",
        rule_count=len(rule_ids),
    )
    service.update_pool_latest_job(pool_id=pool_id, job_id=job["id"], job_status="queued")
    submit_detached_task(
        "sample_pool_sichuan_workspace_batch_job",
        _run_sichuan_workspace_batch_job,
        job["id"],
    )
    return success_response(
        data={
            "pool_id": pool_id,
            "job_id": job["id"],
            "sample_item_count": len(runnable_items),
            "selected_record_count": selected_record_count,
            "record_count": record_count,
            "rule_count": len(rule_ids),
            "customer_rule_count": customer_rule_count,
            "execution_rule_count": len(rule_ids),
            "gate_only_customer_rule_ids": gate_only_customer_rule_ids,
            "gate_only_customer_rule_count": len(gate_only_customer_rule_ids),
            "selected_rule_ids": requested_selected_rule_ids,
            "scoped_customer_rule_ids": selected_customer_delivery_rule_ids,
            "record_rule_map": record_rule_map,
            "record_ids": record_ids,
            "rule_ids": rule_ids,
            "validation_mode": validation_mode,
            "rule_set_key": rule_set_key,
            "rule_set_name": rule_set_name,
            "rule_set_version": rule_set_version,
            "operation_ref": operation_ref,
            "execution_scope_hash": execution_scope_hash,
            "deduplicated": False,
        },
        message="正式质控任务已创建" if is_formal_fast_screen_full else "客户样本验证任务已创建",
        trace_id=get_trace_id(request),
    )
