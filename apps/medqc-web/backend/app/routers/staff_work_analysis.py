"""V3.6 质控员工作分析接口。"""

from __future__ import annotations

import logging
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import Response
from starlette.concurrency import run_in_threadpool

from ..core.audit import audit_event
from ..core.data_scope import resolve_workstation_data_scope
from ..core.response import get_trace_id, success_response
from ..core.security import require_roles
from ..services import staff_work_analysis_service as analysis_service
from ..services.defect_rectification_service import RectificationError
from .quality_reports import (
    _is_restricted_demo_account,
    _strip_diagnostic_fields,
    _trim_csv_bytes_for_demo,
)

router = APIRouter(prefix="/api/v1/quality-reports", tags=["quality-reports"])
logger = logging.getLogger(__name__)
_UNAVAILABLE_DETAIL = "质控员工作分析暂不可用，请稍后重试"


def _trim_coverage_for_demo(coverage: Any) -> Any:
    if not isinstance(coverage, dict):
        return coverage
    patched = dict(coverage)
    if "missing_initial_review_count" in patched:
        patched["missing_initial_review_count"] = 0
    return patched


def _trim_staff_work_for_demo(data: Any) -> Any:
    if not isinstance(data, dict):
        return data
    trimmed = _strip_diagnostic_fields(data)
    if "context_unavailable_count" in trimmed:
        trimmed["context_unavailable_count"] = 0
    if "filter_options_unavailable_reason" in trimmed:
        trimmed["filter_options_unavailable_reason"] = None
    if "unavailable_reason" in trimmed:
        trimmed["unavailable_reason"] = None
    if "unavailable_metrics" in trimmed:
        trimmed["unavailable_metrics"] = {}
    if "defect_snapshot_coverage" in trimmed:
        trimmed["defect_snapshot_coverage"] = _trim_coverage_for_demo(
            trimmed["defect_snapshot_coverage"]
        )
    if isinstance(trimmed.get("summary"), dict):
        summary = dict(trimmed["summary"])
        if "defect_snapshot_coverage" in summary:
            summary["defect_snapshot_coverage"] = _trim_coverage_for_demo(
                summary["defect_snapshot_coverage"]
            )
        trimmed["summary"] = summary
    if isinstance(trimmed.get("staff"), list):
        trimmed["staff"] = [
            (
                {
                    **row,
                    "defect_snapshot_coverage": _trim_coverage_for_demo(
                        row["defect_snapshot_coverage"]
                    ),
                }
                if isinstance(row, dict) and "defect_snapshot_coverage" in row
                else row
            )
            for row in trimmed["staff"]
        ]
    return trimmed


def _trim_staff_work_details_for_demo(data: Any) -> Any:
    if not isinstance(data, dict):
        return data
    trimmed = _strip_diagnostic_fields(data)
    if "unavailable_reason" in trimmed:
        trimmed["unavailable_reason"] = None
    if "defect_snapshot_coverage" in trimmed:
        trimmed["defect_snapshot_coverage"] = _trim_coverage_for_demo(
            trimmed["defect_snapshot_coverage"]
        )
    if "total_complete" in trimmed:
        trimmed["total_complete"] = True
    return trimmed


def _filter_kwargs(
    current_user: dict,
    *,
    period: str,
    scene: str,
    institute_id: str | None,
    department: str | None,
    task_id: str | None,
    start_date: str | None,
    end_date: str | None,
    as_of: str | None,
) -> dict[str, str]:
    values = {
        "actor_id": current_user.get("id") or current_user.get("user_id"),
        "period": period,
        "scene": scene,
        "institute_id": institute_id,
        "department": department,
        "task_id": task_id,
        "start_date": start_date,
        "end_date": end_date,
        "as_of": as_of,
    }
    return {key: value for key, value in values.items() if value is not None}


def _require_full_scope(current_user: dict) -> None:
    scope = resolve_workstation_data_scope(current_user, None)
    if scope.hospital_scope != "all":
        raise HTTPException(status_code=403, detail="无权查看全院质控员工作分析")


def _raise_service_error(exc: Exception) -> None:
    if isinstance(exc, RectificationError):
        raise HTTPException(status_code=exc.status, detail=str(exc)) from exc
    if isinstance(exc, analysis_service.StaffWorkAnalysisInvalid):
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    if isinstance(exc, analysis_service.StaffWorkAnalysisTooLarge):
        raise HTTPException(
            status_code=413,
            detail={
                "code": "staff_work_export_too_large",
                "message": str(exc),
                "matched_at_least": exc.matched_at_least,
                "limit": exc.limit,
            },
        ) from exc
    logger.error("staff_work_analysis_failed error_type=%s", type(exc).__name__)
    raise HTTPException(status_code=503, detail=_UNAVAILABLE_DETAIL) from None


@router.get("/staff-work")
async def get_staff_work_analysis(
    request: Request,
    rank_metric: str | None = Query(None),
    period: Literal["this_week", "last_week", "this_month"] = Query("this_week"),
    scene: Literal["all", "running", "final"] = Query("all"),
    institute_id: str | None = Query(None),
    department: str | None = Query(None),
    task_id: str | None = Query(None),
    start_date: str | None = Query(None),
    end_date: str | None = Query(None),
    as_of: str | None = Query(None),
    current_user: dict = Depends(require_roles("admin", "qc_manager", "super_admin")),
):
    _require_full_scope(current_user)
    filters = _filter_kwargs(
        current_user,
        period=period,
        scene=scene,
        institute_id=institute_id,
        department=department,
        task_id=task_id,
        start_date=start_date,
        end_date=end_date,
        as_of=as_of,
    )
    try:
        if rank_metric is not None:
            filters["rank_metric"] = rank_metric
        data = await run_in_threadpool(
            analysis_service.get_staff_work_analysis, **filters
        )
    except Exception as exc:
        _raise_service_error(exc)
    if _is_restricted_demo_account(current_user):
        data = _trim_staff_work_for_demo(data)
    return success_response(data=data, trace_id=get_trace_id(request))


@router.get("/staff-work/export")
async def export_staff_work_analysis(
    request: Request,
    rank_metric: str | None = Query(None),
    period: Literal["this_week", "last_week", "this_month"] = Query("this_week"),
    scene: Literal["all", "running", "final"] = Query("all"),
    institute_id: str | None = Query(None),
    department: str | None = Query(None),
    task_id: str | None = Query(None),
    start_date: str | None = Query(None),
    end_date: str | None = Query(None),
    as_of: str | None = Query(None),
    current_user: dict = Depends(require_roles("admin", "qc_manager", "super_admin")),
):
    _require_full_scope(current_user)
    filters = _filter_kwargs(
        current_user,
        period=period,
        scene=scene,
        institute_id=institute_id,
        department=department,
        task_id=task_id,
        start_date=start_date,
        end_date=end_date,
        as_of=as_of,
    )
    try:
        if rank_metric is not None:
            filters["rank_metric"] = rank_metric
        content, row_count = await run_in_threadpool(
            analysis_service.export_staff_work_csv,
            **filters,
        )
        if _is_restricted_demo_account(current_user) and isinstance(content, bytes):
            content = _trim_csv_bytes_for_demo(
                content,
                drop_headers=frozenset(
                    {
                        "缺少完整缺陷记录初审数",
                        "missing_initial_review_count",
                        "reason_code",
                        "qc_unavailable_total",
                        "unavailable_result_total",
                        "unavailable_records",
                        "data_gap",
                        "uncertain",
                    }
                ),
            )
    except Exception as exc:
        _raise_service_error(exc)
    audit_event(
        request,
        action="quality_reports.staff_work.export",
        resource="/api/v1/quality-reports/staff-work/export",
        outcome="success",
        details={
            "scene": scene,
            "department_filter_applied": department not in (None, ""),
            "task_filter_applied": task_id not in (None, ""),
            "custom_date_filter_applied": start_date is not None
            or end_date is not None,
            "row_count": row_count,
            "limit": analysis_service.MAX_EXPORT_ROWS,
        },
        current_user=current_user,
    )
    return Response(
        content=content,
        media_type="text/csv; charset=utf-8",
        headers={
            "Cache-Control": "no-store",
            "X-Content-Type-Options": "nosniff",
            "Content-Disposition": "attachment; filename*=UTF-8''staff-work.csv",
        },
    )


@router.get("/staff-work/{user_id}/details")
async def get_staff_work_details(
    request: Request,
    user_id: str,
    metric: str = Query(...),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=analysis_service.MAX_DETAIL_PAGE_SIZE),
    period: Literal["this_week", "last_week", "this_month"] = Query("this_week"),
    scene: Literal["all", "running", "final"] = Query("all"),
    institute_id: str | None = Query(None),
    department: str | None = Query(None),
    task_id: str | None = Query(None),
    start_date: str | None = Query(None),
    end_date: str | None = Query(None),
    as_of: str | None = Query(None),
    current_user: dict = Depends(require_roles("admin", "qc_manager", "super_admin")),
):
    _require_full_scope(current_user)
    filters = _filter_kwargs(
        current_user,
        period=period,
        scene=scene,
        institute_id=institute_id,
        department=department,
        task_id=task_id,
        start_date=start_date,
        end_date=end_date,
        as_of=as_of,
    )
    try:
        data = await run_in_threadpool(
            analysis_service.get_staff_work_details,
            user_id=user_id,
            metric=metric,
            page=page,
            page_size=page_size,
            **filters,
        )
    except Exception as exc:
        _raise_service_error(exc)
    if _is_restricted_demo_account(current_user):
        data = _trim_staff_work_details_for_demo(data)
    return success_response(data=data, trace_id=get_trace_id(request))
