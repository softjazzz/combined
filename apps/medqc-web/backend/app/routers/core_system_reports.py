"""18项核心制度报表：持久账号授权、只读筛选与安全导出。"""

import logging
from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import Response

from ..core.audit import audit_event
from ..core.security import get_current_user
from ..services.core_system_report_service import CoreSystemReportService, csv_export
from ..services.defect_rectification_service import RectificationError
from ..services.record_quality_report_service import (
    RecordQualityReportInvalid,
    RecordQualityReportTooLarge,
)

router = APIRouter(prefix="/api/v1/core-system-reports", tags=["core-system-reports"])
service = CoreSystemReportService()
logger = logging.getLogger(__name__)


def filters(
    scene: Literal["running", "final"] = "running",
    institute_id: str | None = Query(None, min_length=1, max_length=128),
    department: str | None = Query(None, max_length=100),
    doctor: str | None = Query(None, max_length=100),
    completed_from: datetime | None = None,
    completed_to: datetime | None = None,
    system_id: str | None = Query(None, max_length=20),
    rule_id: str | None = Query(None, max_length=128),
    problems_only: bool = False,
):
    return dict(
        scene=scene,
        institute_id=institute_id,
        department=department,
        doctor=doctor,
        completed_from=completed_from,
        completed_to=completed_to,
        system_id=system_id,
        rule_id=rule_id,
        problems_only=problems_only,
    )


def _read(user, params, page=1, page_size=20):
    actor_id = user.get("id") or user.get("user_id")
    if not isinstance(actor_id, str) or not actor_id.strip():
        raise HTTPException(403, "缺少可信账号身份")
    try:
        return service.report(
            actor_id.strip(), **params, page=page, page_size=page_size
        )
    except RectificationError as exc:
        raise HTTPException(exc.status, str(exc)) from None
    except (RecordQualityReportInvalid, RecordQualityReportTooLarge) as exc:
        raise HTTPException(422, str(exc)) from None
    except Exception as exc:
        logger.warning("core_system_report_failed error_type=%s", type(exc).__name__)
        raise HTTPException(503, "核心制度报表来源暂不可用，请稍后重试") from None


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
        action="quality_reports.core_system.export",
        resource="/api/v1/core-system-reports/export",
        outcome="success",
        current_user=user,
        details={
            "scene": params["scene"],
            "row_count": data["total"],
            "institution_filter_applied": bool(params["institute_id"]),
            "system_filter_applied": bool(params["system_id"]),
            "custom_date_filter_applied": bool(
                params["completed_from"] or params["completed_to"]
            ),
        },
    )
    return Response(
        csv_export(data),
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": 'attachment; filename="core-system-report.csv"',
            "Cache-Control": "no-store",
            "X-Content-Type-Options": "nosniff",
        },
    )
