"""Workstation V4 aggregated worklist and snapshot APIs."""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Literal, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request

from ..core.pagination import HEAVY_MAX_PAGE_SIZE, page_param, page_size_param
from ..core.response import get_trace_id, success_response
from ..core.security import get_current_user
from ..services.workstation.worklist_service import default_workstation_aggregation_service
from ..services.workstation.luxian_0609_result_analysis_service import (
    default_luxian_0609_result_analysis_service,
)

router = APIRouter(prefix="/api/v1/workstation", tags=["workstation"])
logger = logging.getLogger(__name__)


def _current_user_id(current_user: dict | None) -> Optional[str]:
    if not current_user:
        return None
    return current_user.get("id") or current_user.get("user_id")


def _raise_workstation_http_error(exc: Exception) -> None:
    if isinstance(exc, ValueError):
        raise HTTPException(status_code=422, detail=str(exc))
    if isinstance(exc, HTTPException):
        raise exc
    logger.error("工作台聚合接口异常: %s", exc)
    raise HTTPException(status_code=500, detail=f"工作台聚合失败: {str(exc)}")


@router.get("/home")
async def get_workstation_home(
    request: Request,
    date: Optional[str] = Query(None, description="统计日期 YYYY-MM-DD"),
    department: Optional[str] = Query(None, description="科室筛选"),
    severity: Optional[str] = Query(None, description="严重度筛选"),
    workflow_type: Optional[str] = Query(None, description="workflow 类型筛选"),
    keyword: Optional[str] = Query(None, description="患者姓名/病案号/住院号/visit 搜索"),
    hotspot_limit: int = Query(50, ge=1, le=200),
    todo_limit: int = Query(12, ge=1, le=100),
    current_user: dict = Depends(get_current_user),
):
    try:
        data = default_workstation_aggregation_service.get_home(
            target_date=date,
            department=department,
            severity=severity,
            workflow_type=workflow_type,
            keyword=keyword,
            recipient_id=_current_user_id(current_user),
            hotspot_limit=hotspot_limit,
            todo_limit=todo_limit,
        )
        return success_response(data=data, trace_id=get_trace_id(request))
    except Exception as exc:
        _raise_workstation_http_error(exc)


@router.get("/qc-home")
async def get_luxian_0609_home(
    request: Request,
    department: Optional[str] = Query(None, description="科室筛选"),
    keyword: Optional[str] = Query(None, description="患者姓名/病案号/住院号/visit 搜索"),
    priority_limit: int = Query(20, ge=1, le=200),
    current_user: dict = Depends(get_current_user),
):
    """当前全病历质控首页的轻量读取入口。"""

    try:
        data = default_workstation_aggregation_service.get_luxian_0609_home(
            department=department,
            keyword=keyword,
            priority_limit=priority_limit,
        )
        return success_response(data=data, trace_id=get_trace_id(request))
    except Exception as exc:
        _raise_workstation_http_error(exc)


@router.get("/analytics/luxian-0609")
async def get_luxian_0609_analytics(
    request: Request,
    completed_from: Optional[datetime] = Query(None, description="质控完成时间起点（闭区间）"),
    completed_to: Optional[datetime] = Query(None, description="质控完成时间终点（闭区间）"),
    department: Optional[str] = Query(None, description="科室筛选"),
    job_id: Optional[UUID] = Query(None, description="已完成根任务 ID"),
    current_user: dict = Depends(get_current_user),
):
    """全院临时范围内的泸县 Canonical 终末质控统计。"""

    try:
        data = default_workstation_aggregation_service.get_luxian_0609_analytics(
            completed_from=completed_from,
            completed_to=completed_to,
            department=department,
            job_id=str(job_id) if job_id else None,
        )
        return success_response(data=data, trace_id=get_trace_id(request))
    except Exception as exc:
        _raise_workstation_http_error(exc)


@router.get("/qc-result-analysis/luxian-0609")
async def get_luxian_0609_result_analysis(
    request: Request,
    care_phase: Literal["inpatient", "discharged"] = Query(..., description="病历范围：在院/已出院"),
    department: Optional[str] = Query(None, description="科室筛选"),
    doctor: Optional[str] = Query(None, description="主管医师筛选"),
    rule_id: Optional[str] = Query(None, description="LX0609 质控点编码"),
    result_status: Optional[
        Literal[
            "non_compliant",
            "data_gap",
            "uncertain",
            "compliant",
            "not_applicable",
            "not_executed",
        ]
    ] = Query(None, description="客户可见的质控结果状态"),
    completed_from: Optional[datetime] = Query(None, description="质控完成时间起点（闭区间）"),
    completed_to: Optional[datetime] = Query(None, description="质控完成时间终点（闭区间）"),
    page: int = Query(1, ge=1, description="病历下钻页码"),
    page_size: int = Query(20, ge=1, le=100, description="病历下钻每页条数"),
    current_user: dict = Depends(get_current_user),
):
    """读取当前范围中每份病历最新 Canonical 结果的规则下钻统计。"""

    try:
        data = default_luxian_0609_result_analysis_service.get_analysis(
            care_phase=care_phase,
            department=department,
            doctor=doctor,
            rule_id=rule_id,
            result_status=result_status,
            completed_from=completed_from,
            completed_to=completed_to,
            page=page,
            page_size=page_size,
        )
        return success_response(data=data, trace_id=get_trace_id(request))
    except Exception as exc:
        _raise_workstation_http_error(exc)


@router.get("/home/hotspots")
async def get_workstation_home_hotspots(
    request: Request,
    date: Optional[str] = Query(None, description="统计日期 YYYY-MM-DD"),
    department: Optional[str] = Query(None, description="科室筛选"),
    severity: Optional[str] = Query(None, description="严重度筛选"),
    workflow_type: Optional[str] = Query(None, description="workflow 类型筛选"),
    keyword: Optional[str] = Query(None, description="患者姓名/病案号/住院号/visit 搜索"),
    limit: int = Query(50, ge=1, le=200),
    current_user: dict = Depends(get_current_user),
):
    try:
        data = default_workstation_aggregation_service.get_home_hotspots(
            target_date=date,
            department=department,
            severity=severity,
            workflow_type=workflow_type,
            keyword=keyword,
            recipient_id=_current_user_id(current_user),
            limit=limit,
        )
        return success_response(data=data, trace_id=get_trace_id(request))
    except Exception as exc:
        _raise_workstation_http_error(exc)


@router.get("/home/todos")
async def get_workstation_home_todos(
    request: Request,
    department: Optional[str] = Query(None, description="科室筛选"),
    workflow_type: Optional[str] = Query(None, description="workflow 类型筛选"),
    keyword: Optional[str] = Query(None, description="患者姓名/病案号/住院号/visit 搜索"),
    limit: int = Query(20, ge=1, le=100),
    current_user: dict = Depends(get_current_user),
):
    try:
        data = default_workstation_aggregation_service.get_home_todos(
            department=department,
            workflow_type=workflow_type,
            keyword=keyword,
            recipient_id=_current_user_id(current_user),
            limit=limit,
        )
        return success_response(data=data, trace_id=get_trace_id(request))
    except Exception as exc:
        _raise_workstation_http_error(exc)


@router.get("/frontpage-qc/worklist")
async def get_frontpage_worklist(
    request: Request,
    department: Optional[str] = Query(None, description="科室筛选"),
    keyword: Optional[str] = Query(None, description="患者姓名/病案号/住院号/visit 搜索"),
    queue_status: Optional[str] = Query(None, description="队列状态筛选"),
    page: int = page_param(description="页码"),
    page_size: int = page_size_param(default=50, max_value=HEAVY_MAX_PAGE_SIZE, description="每页条数"),
    sort_by: Optional[str] = Query(None, description="排序字段"),
    sort_order: Optional[str] = Query(None, description="排序方向 asc/desc"),
    current_user: dict = Depends(get_current_user),
):
    try:
        data = default_workstation_aggregation_service.get_frontpage_worklist(
            department=department,
            keyword=keyword,
            queue_status=queue_status,
            page=page,
            page_size=page_size,
            sort_by=sort_by,
            sort_order=sort_order,
            recipient_id=_current_user_id(current_user),
        )
        return success_response(data=data, trace_id=get_trace_id(request))
    except Exception as exc:
        _raise_workstation_http_error(exc)


@router.get("/coding-qc/worklist")
async def get_coding_worklist(
    request: Request,
    department: Optional[str] = Query(None, description="科室筛选"),
    keyword: Optional[str] = Query(None, description="患者姓名/病案号/住院号/visit 搜索"),
    queue_status: Optional[str] = Query(None, description="队列状态筛选"),
    page: int = page_param(description="页码"),
    page_size: int = page_size_param(default=50, max_value=HEAVY_MAX_PAGE_SIZE, description="每页条数"),
    sort_by: Optional[str] = Query(None, description="排序字段"),
    sort_order: Optional[str] = Query(None, description="排序方向 asc/desc"),
    current_user: dict = Depends(get_current_user),
):
    try:
        data = default_workstation_aggregation_service.get_coding_worklist(
            department=department,
            keyword=keyword,
            queue_status=queue_status,
            page=page,
            page_size=page_size,
            sort_by=sort_by,
            sort_order=sort_order,
            recipient_id=_current_user_id(current_user),
        )
        return success_response(data=data, trace_id=get_trace_id(request))
    except Exception as exc:
        _raise_workstation_http_error(exc)


@router.get("/settlement-qc/worklist")
async def get_settlement_worklist(
    request: Request,
    department: Optional[str] = Query(None, description="科室筛选"),
    keyword: Optional[str] = Query(None, description="患者姓名/病案号/住院号/visit 搜索"),
    queue_status: Optional[str] = Query(None, description="队列状态筛选"),
    page: int = page_param(description="页码"),
    page_size: int = page_size_param(default=50, max_value=HEAVY_MAX_PAGE_SIZE, description="每页条数"),
    sort_by: Optional[str] = Query(None, description="排序字段"),
    sort_order: Optional[str] = Query(None, description="排序方向 asc/desc"),
    current_user: dict = Depends(get_current_user),
):
    try:
        data = default_workstation_aggregation_service.get_settlement_worklist(
            department=department,
            keyword=keyword,
            queue_status=queue_status,
            page=page,
            page_size=page_size,
            sort_by=sort_by,
            sort_order=sort_order,
            recipient_id=_current_user_id(current_user),
        )
        return success_response(data=data, trace_id=get_trace_id(request))
    except Exception as exc:
        _raise_workstation_http_error(exc)


@router.get("/frontpage-qc/{visit_id}/snapshot")
async def get_frontpage_snapshot(
    request: Request,
    visit_id: str,
    current_user: dict = Depends(get_current_user),
):
    try:
        data = default_workstation_aggregation_service.get_frontpage_snapshot(
            visit_id,
            recipient_id=_current_user_id(current_user),
        )
        return success_response(data=data, trace_id=get_trace_id(request))
    except Exception as exc:
        _raise_workstation_http_error(exc)


@router.get("/coding-qc/{visit_id}/snapshot")
async def get_coding_snapshot(
    request: Request,
    visit_id: str,
    current_user: dict = Depends(get_current_user),
):
    try:
        data = default_workstation_aggregation_service.get_coding_snapshot(
            visit_id,
            recipient_id=_current_user_id(current_user),
        )
        return success_response(data=data, trace_id=get_trace_id(request))
    except Exception as exc:
        _raise_workstation_http_error(exc)


@router.get("/settlement-qc/{visit_id}/snapshot")
async def get_settlement_snapshot(
    request: Request,
    visit_id: str,
    current_user: dict = Depends(get_current_user),
):
    try:
        data = default_workstation_aggregation_service.get_settlement_snapshot(
            visit_id,
            recipient_id=_current_user_id(current_user),
        )
        return success_response(data=data, trace_id=get_trace_id(request))
    except Exception as exc:
        _raise_workstation_http_error(exc)
