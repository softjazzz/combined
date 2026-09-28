"""V3.6 病历质量分析报表接口。"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import Response
from starlette.concurrency import run_in_threadpool

from ..core.audit import audit_event
from ..core.data_scope import resolve_workstation_data_scope
from ..core.response import get_trace_id, success_response
from ..core.permissions import (
    PermissionAction,
    ResourceType,
    UserRole,
    has_any_role,
    require_permission,
)
from ..core.security import get_current_user, require_roles
from ..services import record_quality_report_service as report_service
from ..services import task_analysis_service

router = APIRouter(prefix="/api/v1/quality-reports", tags=["quality-reports"])
logger = logging.getLogger(__name__)

_UNAVAILABLE_DETAIL = "病历质量报表暂不可用，请稍后重试"
_TASK_ANALYSIS_UNAVAILABLE_DETAIL = "任务分析暂不可用，请稍后重试"


def _report_params(
    scene: Literal["running", "final"] = Query(...),
    department: str | None = Query(None),
    doctor: str | None = Query(None),
    completed_from: datetime | None = Query(None),
    completed_to: datetime | None = Query(None),
    defect_source: Literal["all", "auto", "manual"] = Query("all"),
) -> dict[str, Any]:
    return {
        "scene": scene,
        "department": department,
        "doctor": doctor,
        "completed_from": completed_from,
        "completed_to": completed_to,
        "defect_source": defect_source,
    }


def _drilldown_params(
    rule_id: str | None = Query(None),
    document: str | None = Query(None),
    grade: str | None = Query(None),
    has_defect: bool | None = Query(None),
) -> dict[str, Any]:
    return {
        "rule_id": rule_id,
        "document": document,
        "grade": grade,
        "has_defect": has_defect,
    }


def _raise_report_error(exc: Exception, action: str) -> None:
    if isinstance(exc, report_service.RecordQualityReportInvalid):
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    if isinstance(exc, report_service.RecordQualityReportTooLarge):
        raise HTTPException(status_code=422, detail={"code": "range_too_large", "message": str(exc)}) from exc
    if isinstance(exc, report_service.RecordQualityReportBlocked):
        raise HTTPException(status_code=409, detail={"code": exc.code, "message": str(exc)}) from exc
    # 范围、结果及未知读取错误只记录类型，避免泄露患者资料或 SQL。
    logger.error("quality_report_%s_failed error_type=%s", action, type(exc).__name__)
    raise HTTPException(status_code=503, detail=_UNAVAILABLE_DETAIL) from None


def _authorized_params(current_user: dict, params: dict[str, Any]) -> dict[str, Any]:
    scope = resolve_workstation_data_scope(current_user, params["department"])
    return {**params, "department": scope.department}


def _task_actor_id(current_user: dict) -> str:
    actor_id = current_user.get("id") or current_user.get("user_id")
    if not isinstance(actor_id, str) or not actor_id.strip():
        raise HTTPException(status_code=401, detail="当前用户缺少有效身份")
    return actor_id.strip()


@router.get("/tasks/{task_id}")
@require_permission(ResourceType.QC_TASKS, PermissionAction.READ)
async def get_task_analysis(
    request: Request,
    task_id: str,
    current_user: dict = Depends(get_current_user),
):
    """读取单个任务分析；权限与整任务进度一致。"""
    actor_id = _task_actor_id(current_user)
    is_manager = has_any_role(current_user, [UserRole.ADMIN, UserRole.QC_MANAGER])
    try:
        data = await run_in_threadpool(
            task_analysis_service.get_task_analysis,
            task_id=task_id,
            actor_id=actor_id,
            is_manager=is_manager,
        )
    except task_analysis_service.TaskAnalysisInvalid as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except task_analysis_service.TaskAnalysisNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except task_analysis_service.TaskAnalysisForbidden as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except Exception as exc:
        logger.error("task_analysis_read_failed error_type=%s", type(exc).__name__)
        raise HTTPException(status_code=503, detail=_TASK_ANALYSIS_UNAVAILABLE_DETAIL) from None
    return success_response(data=data, trace_id=get_trace_id(request))


@router.get("/record-quality")
async def get_record_quality(
    request: Request,
    params: dict[str, Any] = Depends(_report_params),
    current_user: dict = Depends(require_roles("admin", "qc_manager")),
):
    query = _authorized_params(current_user, params)
    try:
        context = await run_in_threadpool(report_service.build_report_context, **query)
        data = await run_in_threadpool(report_service.summarize, context)
    except Exception as exc:
        _raise_report_error(exc, "summary")
    return success_response(data=data, trace_id=get_trace_id(request))


@router.get("/record-quality/records")
async def get_record_quality_records(
    request: Request,
    params: dict[str, Any] = Depends(_report_params),
    drilldown: dict[str, Any] = Depends(_drilldown_params),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: dict = Depends(require_roles("admin", "qc_manager")),
):
    query = _authorized_params(current_user, params)
    try:
        context = await run_in_threadpool(report_service.build_report_context, **query)
        data = await run_in_threadpool(
            report_service.records_page, context,
            page=page, page_size=page_size, department=query["department"],
            doctor=query["doctor"], **drilldown,
        )
    except Exception as exc:
        _raise_report_error(exc, "records")
    return success_response(data=data, trace_id=get_trace_id(request))


@router.get("/record-quality/export")
async def export_record_quality(
    request: Request,
    params: dict[str, Any] = Depends(_report_params),
    drilldown: dict[str, Any] = Depends(_drilldown_params),
    sheet: Literal["departments", "doctors", "records"] = Query(...),
    current_user: dict = Depends(require_roles("admin", "qc_manager")),
):
    query = _authorized_params(current_user, params)
    try:
        context = await run_in_threadpool(report_service.build_report_context, **query)
        export_filters = (
            {"department": query["department"], "doctor": query["doctor"], **drilldown}
            if sheet == "records" else drilldown
        )
        content = await run_in_threadpool(
            report_service.export_csv, context,
            sheet=sheet, **export_filters,
        )
        if not isinstance(content, bytes):
            raise TypeError("导出服务未返回 CSV 字节")
    except Exception as exc:
        _raise_report_error(exc, "export")
    audit_event(
        request,
        action="quality_reports.record_quality.export",
        resource="/api/v1/quality-reports/record-quality/export",
        outcome="success",
        details={"scene": query["scene"], "sheet": sheet, "bytes": len(content)},
        current_user=current_user,
    )
    return Response(
        content=content,
        media_type="text/csv; charset=utf-8",
        headers={
            "Cache-Control": "no-store",
            "X-Content-Type-Options": "nosniff",
            "Content-Disposition": f'attachment; filename="record_quality_{query["scene"]}_{sheet}.csv"',
        },
    )
