from __future__ import annotations

import json
import os
import uuid
from pathlib import Path
from typing import Any, Dict, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, Query, Request, UploadFile
from pydantic import BaseModel, Field

from ..core.response import get_trace_id, success_response
from ..core.security import get_current_user, require_roles
from ..services.fast_screen_qc import EXECUTION_STRATEGY_FAST_SCREEN, EXECUTION_STRATEGY_STANDARD, get_fast_screen_full_rule_ids
from ..routers.qc_sichuan import _run_sichuan_workspace_batch_job
from ..services.custom_qc_sample_pool_service import (
    CustomQCSamplePoolService,
    load_manual_case_rows_from_excel,
)
from ..services.custom_qc_workspace_service import CustomQCWorkspaceService
from ..services.customer_rule_sets import (
    CUSTOMER_LUXIAN_RULE_SET_KEY,
    get_customer_luxian_rule_set,
)
from ..services.sample_validation_rule_sets import (
    get_sample_programmatic_rule_set,
    resolve_sample_validation_pseudo_draft,
)


router = APIRouter(
    prefix="/api/v1/qc/sample-pools",
    tags=["qc-sample-pools"],
    dependencies=[Depends(require_roles("admin", "qc_manager"))],
)

_IMPORT_UPLOAD_DIR = (
    Path(__file__).resolve().parents[2] / "data" / "sample_pool_uploads"
)
_FAST_SCREEN_FULL_RULE_ID_SET = {str(item).strip().upper() for item in get_fast_screen_full_rule_ids() if str(item).strip()}
_SHEET2_EXACT_REVIEW_ACCEPTANCE_JSON = (
    Path(__file__).resolve().parents[3] / "docs" / "0418" / "QC" / "sheet2_exact_review_acceptance_package.json"
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


class SamplePoolRunRequest(BaseModel):
    department: Optional[str] = None
    doctor: Optional[str] = None
    model_code: Optional[str] = None
    top_p: Optional[float] = None
    temperature: Optional[float] = None
    max_tokens: Optional[int] = None
    max_parallel_records: Optional[int] = Field(default=None, description="病历级并发数")
    sample_item_ids: list[str] = Field(default_factory=list, description="选中的样本项 ID")
    record_ids: list[str] = Field(default_factory=list, description="选中的真实病历 visit_id")
    validation_mode: str = Field(default="customer", description="验证模式：customer/sc/programmatic")
    rule_set_key: Optional[str] = Field(default=None, description="指定规则包 key，仅客户专项模式使用")


class SamplePoolSyncRequest(BaseModel):
    only_intrinsic: bool = Field(default=True, description="只同步内涵样本")
    include_in_batch_1: bool = Field(default=True, description="只同步首批样本")
    table_groups: list[str] = Field(
        default_factory=lambda: [
            "core_8",
            "document_extended",
            "diagnosis_extended",
            "orders_prescriptions",
            "exam_lab_pathology",
        ],
        description="同步表分组",
    )


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

    service.mark_sync_job_running(job_id=job_id)

    def emit_progress(progress: Dict[str, Any]) -> None:
        service.update_sync_job_progress(job_id=job_id, progress=progress)

    try:
        result = service.sync_pool_records(
            pool_id=pool_id,
            only_intrinsic=bool(payload.get("only_intrinsic", True)),
            include_in_batch_1=bool(payload.get("include_in_batch_1", True)),
            table_groups=payload.get("table_groups") or [],
            progress_callback=emit_progress,
        )
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
    source_sheet: str = Form(default="Sheet2", description="Sheet 名称"),
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
        source_sheet=str(source_sheet).strip() or "Sheet2",
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
    result = _service().match_pool_items(pool_id=pool_id)
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
            payload=payload.model_dump(),
        )
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
    background_tasks: BackgroundTasks,
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    service = _service()
    pool = service.get_pool(pool_id=pool_id)
    if not pool:
        raise HTTPException(status_code=404, detail="样本池不存在")

    validation_mode = str(payload.validation_mode or "customer").strip().lower() or "customer"
    if validation_mode not in {"customer", "sc", "programmatic"}:
        raise HTTPException(status_code=422, detail="未知验证模式，仅支持 customer、sc 或 programmatic")

    runnable_items = service.get_runnable_items(
        pool_id=pool_id,
        validation_mode=validation_mode,
        item_ids=payload.sample_item_ids,
        record_ids=payload.record_ids,
    )
    if not runnable_items:
        if payload.record_ids:
            raise HTTPException(status_code=422, detail="当前选中病历没有可执行的样本问题")
        if payload.sample_item_ids:
            raise HTTPException(status_code=422, detail="当前选中样本没有可执行的病历")
        raise HTTPException(status_code=422, detail="当前样本池没有可执行的样本病历")

    record_ids = sorted(
        {
            str(item.get("matched_visit_id") or "").strip()
            for item in runnable_items
            if str(item.get("matched_visit_id") or "").strip()
        }
    )
    record_rule_map: Dict[str, list[str]] = {}
    for item in runnable_items:
        record_id = str(item.get("matched_visit_id") or "").strip()
        if not record_id:
            continue
        bucket = record_rule_map.setdefault(record_id, [])
        for rule_id in list(item.get("candidate_rule_ids") or []):
            normalized_rule_id = str(rule_id or "").strip()
            if normalized_rule_id and normalized_rule_id not in bucket:
                bucket.append(normalized_rule_id)
    if not record_ids:
        raise HTTPException(status_code=422, detail="当前样本池没有已匹配的病历")

    if validation_mode == "customer":
        requested_rule_set_key = str(payload.rule_set_key or CUSTOMER_LUXIAN_RULE_SET_KEY).strip() or CUSTOMER_LUXIAN_RULE_SET_KEY
        if requested_rule_set_key != CUSTOMER_LUXIAN_RULE_SET_KEY:
            raise HTTPException(status_code=422, detail=f"未知客户规则包: {requested_rule_set_key}")
        customer_rule_set = get_customer_luxian_rule_set()
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
    else:
        programmatic_rule_set = get_sample_programmatic_rule_set()
        rule_ids = list(programmatic_rule_set.rule_ids)
        rule_set_key = programmatic_rule_set.key
        rule_set_name = programmatic_rule_set.name
        rule_set_version = programmatic_rule_set.version

    if not rule_ids:
        raise HTTPException(status_code=422, detail="当前样本池没有可执行规则")
    execution_strategy = _resolve_sample_validation_execution_strategy(
        validation_mode=validation_mode,
        rule_ids=rule_ids,
    )

    workspace = _workspace_service()
    requested_scope = str(pool.get("scene") or "running").strip().lower() or "running"
    effective_scope = requested_scope
    records = workspace.collect_records(
        scope=effective_scope,
        department=payload.department,
        doctor=payload.doctor,
        date_field="admission",
        start_date=None,
        end_date=None,
        keyword=None,
        record_ids=record_ids,
    )
    if not records and record_ids and effective_scope != "all":
        fallback_records = workspace.collect_records(
            scope="all",
            department=payload.department,
            doctor=payload.doctor,
            date_field="admission",
            start_date=None,
            end_date=None,
            keyword=None,
            record_ids=record_ids,
        )
        if fallback_records:
            records = fallback_records
            effective_scope = "all"
    if not records:
        raise HTTPException(status_code=422, detail="样本池匹配病历未同步到当前 PG，无法执行")

    pseudo_draft = resolve_sample_validation_pseudo_draft(
        validation_mode=validation_mode,
        pool_name=str(pool.get("name") or ""),
        rule_count=len(rule_ids),
    )
    job = workspace.create_batch_job(
        draft=pseudo_draft,
        created_by=_current_user_id(current_user),
        scope=effective_scope,
        filters={
            "rule_ids": rule_ids,
            "rule_set_key": rule_set_key,
            "rule_set_name": rule_set_name,
            "rule_set_version": rule_set_version,
            "execution_strategy": execution_strategy,
            "quality_profile": "throughput_v1",
            "bucket_strategy": "fixed_packs",
            "batch_output_mode": "minimal",
            "enable_selective_refine": False,
            "refine_confidence_threshold": 0.0,
            "max_refine_candidates": 0,
            "source": "manual_problem_sample_pool",
            "sample_pool_id": pool_id,
            "selected_record_ids": payload.record_ids,
            "selected_sample_item_ids": [str(item.get("id") or "").strip() for item in runnable_items if str(item.get("id") or "").strip()],
            "selected_sample_count": len(runnable_items),
            "dedup_record_count": len(record_ids),
            "record_rule_map": record_rule_map,
            "department": payload.department,
            "doctor": payload.doctor,
            "temperature": payload.temperature,
            "top_p": payload.top_p,
            "max_tokens": payload.max_tokens,
            "model_code": payload.model_code,
            "max_parallel_records": payload.max_parallel_records,
            "effective_scope": effective_scope,
            "validation_mode": validation_mode,
        },
        record_ids=record_ids,
        total_records=len(records),
        draft_ids=rule_ids,
        execution_mode="multi",
        run_mode="parallel",
        rule_count=len(rule_ids),
    )
    service.update_pool_latest_job(pool_id=pool_id, job_id=job["id"], job_status="queued")
    background_tasks.add_task(_run_sichuan_workspace_batch_job, job["id"])
    return success_response(
        data={
            "pool_id": pool_id,
            "job_id": job["id"],
            "sample_item_count": len(runnable_items),
            "selected_record_count": len(payload.record_ids or []),
            "record_count": len(record_ids),
            "rule_count": len(rule_ids),
            "record_ids": record_ids,
            "rule_ids": rule_ids,
            "validation_mode": validation_mode,
            "rule_set_key": rule_set_key,
            "rule_set_name": rule_set_name,
            "rule_set_version": rule_set_version,
        },
        message="客户样本验证任务已创建",
        trace_id=get_trace_id(request),
    )
