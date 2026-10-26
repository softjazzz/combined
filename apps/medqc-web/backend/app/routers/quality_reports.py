"""PR8报表只读消费子集，来源88e8f864b；不移植写入口与执行链。"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import Response
from starlette.concurrency import run_in_threadpool

from ..core.audit import audit_event
from ..core.data_scope import resolve_workstation_data_scope
from ..core.response import get_trace_id, success_response
from ..core.security import require_roles
from ..services import frontpage_quality_report_service as frontpage_report_service
from ..services import record_quality_report_service as report_service
from ..services import record_remediation_report_service as remediation_report_service
from ..services.defect_rectification_service import RectificationError

router = APIRouter(prefix="/api/v1/quality-reports", tags=["quality-reports"])
logger = logging.getLogger(__name__)
_UNAVAILABLE_DETAIL = "病历质量报表暂不可用，请稍后重试"


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
    has_veto: bool | None = Query(None),
    defect_category: str | None = Query(None),
    defect_type: str | None = Query(None),
    unknown_classification: Literal["defect_category", "defect_type"] | None = Query(
        None
    ),
) -> dict[str, Any]:
    return {
        "rule_id": rule_id,
        "document": document,
        "grade": grade,
        "has_defect": has_defect,
        "has_veto": has_veto,
        "defect_category": defect_category,
        "defect_type": defect_type,
        "unknown_classification": unknown_classification,
    }


def _raise_report_error(exc: Exception, action: str) -> None:
    if isinstance(exc, RectificationError):
        raise HTTPException(status_code=exc.status, detail=str(exc)) from exc
    if isinstance(exc, report_service.RecordQualityReportInvalid):
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    if isinstance(exc, report_service.RecordQualityReportTooLarge):
        raise HTTPException(
            status_code=422, detail={"code": "range_too_large", "message": str(exc)}
        ) from exc
    # 范围、结果及未知读取错误只记录类型，避免泄露患者资料或 SQL。
    logger.error("quality_report_%s_failed error_type=%s", action, type(exc).__name__)
    raise HTTPException(status_code=503, detail=_UNAVAILABLE_DETAIL) from None


def _authorized_params(current_user: dict, params: dict[str, Any]) -> dict[str, Any]:
    scope = resolve_workstation_data_scope(current_user, params["department"])
    return {
        **params,
        "department": scope.department,
        "actor_id": _task_actor_id(current_user),
    }


def _task_actor_id(current_user: dict) -> str:
    actor_id = current_user.get("id") or current_user.get("user_id")
    if not isinstance(actor_id, str) or not actor_id.strip():
        raise HTTPException(status_code=401, detail="当前用户缺少有效身份")
    return actor_id.strip()


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
            report_service.records_page,
            context,
            page=page,
            page_size=page_size,
            department=query["department"],
            doctor=query["doctor"],
            **drilldown,
        )
    except Exception as exc:
        _raise_report_error(exc, "records")
    return success_response(data=data, trace_id=get_trace_id(request))


@router.get("/record-quality/remediations")
async def get_record_remediations(
    request: Request,
    params: dict[str, Any] = Depends(_report_params),
    label: str | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: dict = Depends(require_roles("admin", "qc_manager")),
):
    query = _authorized_params(current_user, params)
    actor_id = _task_actor_id(current_user)
    try:
        context = await run_in_threadpool(report_service.build_report_context, **query)
        analysis = await run_in_threadpool(
            remediation_report_service.build_analysis, context, actor_id=actor_id
        )
        data = await run_in_threadpool(
            remediation_report_service.page,
            analysis,
            label=label,
            page=page,
            page_size=page_size,
        )
    except RectificationError as exc:
        raise HTTPException(exc.status, str(exc)) from None
    except Exception as exc:
        _raise_report_error(exc, "remediations")
    return success_response(data=data, trace_id=get_trace_id(request))


@router.get("/record-quality/remediations/export")
async def export_record_remediations(
    request: Request,
    params: dict[str, Any] = Depends(_report_params),
    label: str | None = Query(None),
    current_user: dict = Depends(require_roles("admin", "qc_manager")),
):
    query = _authorized_params(current_user, params)
    actor_id = _task_actor_id(current_user)
    try:
        context = await run_in_threadpool(report_service.build_report_context, **query)
        analysis = await run_in_threadpool(
            remediation_report_service.build_analysis, context, actor_id=actor_id
        )
        content = await run_in_threadpool(
            remediation_report_service.export_csv, analysis, label=label
        )
        if not isinstance(content, bytes):
            raise TypeError("整改分析导出服务未返回 CSV 字节")
    except RectificationError as exc:
        raise HTTPException(exc.status, str(exc)) from None
    except Exception as exc:
        _raise_report_error(exc, "remediations_export")
    audit_event(
        request,
        action="quality_reports.record_remediation.export",
        resource="/api/v1/quality-reports/record-quality/remediations/export",
        outcome="success",
        details={"scene": query["scene"], "bytes": len(content)},
        current_user=current_user,
    )
    return Response(
        content=content,
        media_type="text/csv; charset=utf-8",
        headers={
            "Cache-Control": "no-store",
            "X-Content-Type-Options": "nosniff",
            "Content-Disposition": f'attachment; filename="record_remediation_{query["scene"]}.csv"',
        },
    )


@router.get("/record-quality/export")
async def export_record_quality(
    request: Request,
    params: dict[str, Any] = Depends(_report_params),
    drilldown: dict[str, Any] = Depends(_drilldown_params),
    sheet: Literal["departments", "doctors", "records"] = Query(...),
    columns: str | None = Query(None),
    current_user: dict = Depends(require_roles("admin", "qc_manager")),
):
    query = _authorized_params(current_user, params)
    try:
        selected_columns = None
        if columns is not None:
            try:
                selected_columns = json.loads(columns)
            except (ValueError, TypeError) as exc:
                raise report_service.RecordQualityReportInvalid(
                    "汇总列配置无效"
                ) from exc
            if not isinstance(selected_columns, list) or any(
                not isinstance(key, str) for key in selected_columns
            ):
                raise report_service.RecordQualityReportInvalid("汇总列配置无效")
        context = await run_in_threadpool(report_service.build_report_context, **query)
        export_filters = (
            {"department": query["department"], "doctor": query["doctor"], **drilldown}
            if sheet == "records"
            else drilldown
        )
        content = await run_in_threadpool(
            report_service.export_csv,
            context,
            sheet=sheet,
            columns=selected_columns,
            **export_filters,
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


_FRONTPAGE_UNAVAILABLE_DETAIL = "病案首页统计暂不可用，请稍后重试"


def _frontpage_params(
    department: str | None = Query(None),
    doctor: str | None = Query(None),
    analyzed_from: datetime | None = Query(None),
    analyzed_to: datetime | None = Query(None),
) -> dict[str, Any]:
    return {
        "department": department,
        "doctor": doctor,
        "analyzed_from": analyzed_from,
        "analyzed_to": analyzed_to,
    }


def _frontpage_drilldown(
    source: Literal["all", "frontpage", "coding"] = Query("all"),
    rule_code: str | None = Query(None),
    problem_only: bool = Query(False),
) -> dict[str, Any]:
    return {"source": source, "rule_code": rule_code, "problem_only": problem_only}


def _raise_frontpage_error(exc: Exception, action: str) -> None:
    if isinstance(exc, RectificationError):
        raise HTTPException(status_code=exc.status, detail=str(exc)) from exc
    if isinstance(exc, frontpage_report_service.FrontpageQualityReportInvalid):
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    if isinstance(exc, frontpage_report_service.FrontpageQualityReportTooLarge):
        raise HTTPException(
            status_code=422, detail={"code": "range_too_large", "message": str(exc)}
        ) from exc
    if isinstance(
        exc, frontpage_report_service.FrontpageQualityReportSchemaUnavailable
    ):
        raise HTTPException(
            status_code=503,
            detail={"code": exc.code, "message": "首页质控现代数据源未部署"},
        ) from exc
    logger.error(
        "frontpage_quality_report_%s_failed error_type=%s", action, type(exc).__name__
    )
    raise HTTPException(status_code=503, detail=_FRONTPAGE_UNAVAILABLE_DETAIL) from None


@router.get("/frontpage-quality")
async def get_frontpage_quality(
    request: Request,
    params: dict[str, Any] = Depends(_frontpage_params),
    current_user: dict = Depends(require_roles("admin", "qc_manager")),
):
    query = _authorized_params(current_user, params)
    try:
        context = await run_in_threadpool(
            frontpage_report_service.build_report_context, **query
        )
        data = await run_in_threadpool(frontpage_report_service.summarize, context)
    except Exception as exc:
        _raise_frontpage_error(exc, "summary")
    return success_response(data=data, trace_id=get_trace_id(request))


@router.get("/frontpage-quality/records")
async def get_frontpage_quality_records(
    request: Request,
    params: dict[str, Any] = Depends(_frontpage_params),
    drilldown: dict[str, Any] = Depends(_frontpage_drilldown),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: dict = Depends(require_roles("admin", "qc_manager")),
):
    query = _authorized_params(current_user, params)
    try:
        context = await run_in_threadpool(
            frontpage_report_service.build_report_context, **query
        )
        data = await run_in_threadpool(
            frontpage_report_service.records_page,
            context,
            page=page,
            page_size=page_size,
            department=query["department"],
            **drilldown,
        )
    except Exception as exc:
        _raise_frontpage_error(exc, "records")
    return success_response(data=data, trace_id=get_trace_id(request))


@router.get("/frontpage-quality/export")
async def export_frontpage_quality(
    request: Request,
    params: dict[str, Any] = Depends(_frontpage_params),
    drilldown: dict[str, Any] = Depends(_frontpage_drilldown),
    sheet: Literal["departments", "records"] = Query(...),
    current_user: dict = Depends(require_roles("admin", "qc_manager")),
):
    query = _authorized_params(current_user, params)
    try:
        context = await run_in_threadpool(
            frontpage_report_service.build_report_context, **query
        )
        export_filters = (
            {"department": query["department"], **drilldown}
            if sheet == "records"
            else {}
        )
        content = await run_in_threadpool(
            frontpage_report_service.export_csv,
            context,
            sheet=sheet,
            **export_filters,
        )
        if not isinstance(content, bytes):
            raise TypeError("导出服务未返回 CSV 字节")
    except Exception as exc:
        _raise_frontpage_error(exc, "export")
    audit_event(
        request,
        action="quality_reports.frontpage_quality.export",
        resource="/api/v1/quality-reports/frontpage-quality/export",
        outcome="success",
        details={"sheet": sheet, "bytes": len(content)},
        current_user=current_user,
    )
    return Response(
        content=content,
        media_type="text/csv; charset=utf-8",
        headers={
            "Cache-Control": "no-store",
            "X-Content-Type-Options": "nosniff",
            "Content-Disposition": f'attachment; filename="frontpage_quality_{sheet}.csv"',
        },
    )
