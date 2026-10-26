"""人工质控报表只读接口；统计口径为明确标注的待确认假设。"""

import logging
from datetime import date
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import Response

from ..core.audit import audit_event
from ..core.security import get_current_user
from ..services.defect_rectification_service import RectificationError
from ..services.manual_defect_review_service import ManualDefectReviewInvalid
from ..services.manual_quality_report_service import (
    ManualQualityReportService,
    csv_export,
)

router = APIRouter(
    prefix="/api/v1/manual-quality-reports", tags=["manual-quality-reports"]
)
service = ManualQualityReportService()
logger = logging.getLogger(__name__)


def filters(
    start_date: date,
    end_date: date,
    institute_id: str | None = Query(None, min_length=1, max_length=128),
    department: str | None = Query(None, min_length=1, max_length=100),
    creator_id: str | None = Query(None, min_length=1, max_length=64),
    task_id: str | None = Query(None, min_length=1, max_length=36),
    scene: Literal["all", "running", "final", "outpatient_emergency"] = "all",
):
    return dict(
        start_date=start_date,
        end_date=end_date,
        institute_id=institute_id,
        department=department,
        creator_id=creator_id,
        task_id=task_id,
        scene=scene,
    )


def _read(user, params, page=1, page_size=20):
    actor = user.get("id") or user.get("user_id")
    if not isinstance(actor, str) or not actor.strip():
        raise HTTPException(403, "缺少可信账号身份")
    try:
        return service.report(actor, **params, page=page, page_size=page_size)
    except RectificationError as exc:
        raise HTTPException(exc.status, str(exc)) from None
    except ManualDefectReviewInvalid as exc:
        raise HTTPException(422, str(exc)) from None
    except Exception as exc:
        logger.warning("manual_quality_report_failed error_type=%s", type(exc).__name__)
        raise HTTPException(503, "人工质控报表来源暂不可用，请稍后重试") from None


@router.get("")
def report(
    params=Depends(filters),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    user=Depends(get_current_user),
):
    data = _read(user, params, page, page_size)
    data.pop("_export_rows", None)
    return {"success": True, "data": data}


@router.get("/export")
def export(request: Request, params=Depends(filters), user=Depends(get_current_user)):
    data = _read(user, params)
    audit_event(
        request,
        action="quality_reports.manual_quality.export",
        resource="/api/v1/manual-quality-reports/export",
        outcome="success",
        details={
            "scene": params["scene"],
            "row_count": len(data["_export_rows"]),
            "institute_filter_applied": bool(params["institute_id"]),
            "department_filter_applied": bool(params["department"]),
            "creator_filter_applied": bool(params["creator_id"]),
            "task_filter_applied": bool(params["task_id"]),
            "custom_date_filter_applied": True,
        },
        current_user=user,
    )
    return Response(
        csv_export(data["_export_rows"], data.get("as_of")),
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": 'attachment; filename="manual-quality-report.csv"',
            "Cache-Control": "no-store",
            "X-Content-Type-Options": "nosniff",
        },
    )
