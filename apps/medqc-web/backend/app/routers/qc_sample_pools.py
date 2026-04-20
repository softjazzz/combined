from __future__ import annotations

import os
from typing import Any, Dict, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field

from ..core.response import get_trace_id, success_response
from ..core.security import get_current_user, require_roles
from ..routers.qc_sichuan import _run_sichuan_workspace_batch_job
from ..services.custom_qc_sample_pool_service import (
    CustomQCSamplePoolService,
    load_manual_case_rows_from_excel,
)
from ..services.custom_qc_workspace_service import CustomQCWorkspaceService


router = APIRouter(
    prefix="/api/v1/qc/sample-pools",
    tags=["qc-sample-pools"],
    dependencies=[Depends(require_roles("admin", "qc_manager"))],
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
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    pool = _service().get_pool(pool_id=pool_id)
    if not pool:
        raise HTTPException(status_code=404, detail="样本池不存在")
    try:
        result = _service().sync_pool_records(
            pool_id=pool_id,
            only_intrinsic=payload.only_intrinsic,
            include_in_batch_1=payload.include_in_batch_1,
            table_groups=payload.table_groups,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"样本病历同步失败: {exc}") from exc
    return success_response(
        data=result,
        message="样本病历定向同步完成",
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

    runnable_items = service.get_runnable_items(pool_id=pool_id)
    if not runnable_items:
        raise HTTPException(status_code=422, detail="当前样本池没有可执行的内涵样本")

    record_ids = sorted(
        {
            str(item.get("matched_visit_id") or "").strip()
            for item in runnable_items
            if str(item.get("matched_visit_id") or "").strip()
        }
    )
    rule_ids = sorted(
        {
            str(rule_id).strip()
            for item in runnable_items
            for rule_id in (item.get("candidate_rule_ids") or [])
            if str(rule_id).strip()
        }
    )
    if not record_ids:
        raise HTTPException(status_code=422, detail="当前样本池没有已匹配的病历")
    if not rule_ids:
        raise HTTPException(status_code=422, detail="当前样本池没有可执行规则")

    workspace = _workspace_service()
    records = workspace.collect_records(
        scope="running",
        department=payload.department,
        doctor=payload.doctor,
        date_field="admission",
        start_date=None,
        end_date=None,
        keyword=None,
        record_ids=record_ids,
    )
    if not records:
        raise HTTPException(status_code=422, detail="样本池匹配病历未同步到当前 PG，无法执行")

    pseudo_draft = {
        "id": "sichuan-rule-library",
        "rule_code": "SC-SAMPLE-POOL",
        "name": f"{pool['name']}内涵样本验证任务({len(rule_ids)}条规则)",
        "scene": "running",
    }
    job = workspace.create_batch_job(
        draft=pseudo_draft,
        created_by=_current_user_id(current_user),
        scope="running",
        filters={
            "rule_ids": rule_ids,
            "rule_set_key": "",
            "rule_set_name": "客户内涵样本验证",
            "rule_set_version": "running-batch-1",
            "execution_strategy": "fast_screen",
            "quality_profile": "throughput_v1",
            "bucket_strategy": "fixed_packs",
            "batch_output_mode": "minimal",
            "enable_selective_refine": False,
            "refine_confidence_threshold": 0.0,
            "max_refine_candidates": 0,
            "source": "manual_problem_sample_pool",
            "sample_pool_id": pool_id,
            "department": payload.department,
            "doctor": payload.doctor,
            "temperature": payload.temperature,
            "top_p": payload.top_p,
            "max_tokens": payload.max_tokens,
            "model_code": payload.model_code,
        },
        record_ids=record_ids,
        total_records=len(records),
        draft_ids=rule_ids,
        execution_mode="multi",
        rule_count=len(rule_ids),
    )
    service.update_pool_latest_job(pool_id=pool_id, job_id=job["id"], job_status="queued")
    background_tasks.add_task(_run_sichuan_workspace_batch_job, job["id"])
    return success_response(
        data={
            "pool_id": pool_id,
            "job_id": job["id"],
            "record_count": len(record_ids),
            "rule_count": len(rule_ids),
            "record_ids": record_ids,
            "rule_ids": rule_ids,
        },
        message="客户样本内涵验证任务已创建",
        trace_id=get_trace_id(request),
    )
