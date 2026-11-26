"""18项核心制度报表：持久账号授权、只读筛选与安全导出。"""

import logging
from datetime import datetime
from typing import Any, Literal

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
from .quality_reports import (
    _DEMO_UNCERTAIN_STATUSES,
    _is_restricted_demo_account,
    _strip_diagnostic_fields,
)

router = APIRouter(prefix="/api/v1/core-system-reports", tags=["core-system-reports"])
service = CoreSystemReportService()
logger = logging.getLogger(__name__)


def _trim_core_system_row_for_demo(row: Any) -> dict | None:
    if not isinstance(row, dict):
        return None
    if row.get("coverage") == "unavailable":
        return None
    cleaned = _strip_diagnostic_fields(row)
    points = cleaned.get("points")
    if isinstance(points, list):
        kept_points = [
            _strip_diagnostic_fields(point)
            for point in points
            if isinstance(point, dict)
            and str(point.get("status") or "").strip().lower()
            not in _DEMO_UNCERTAIN_STATUSES
            and point.get("system_ids") is not None
        ]
        cleaned["points"] = kept_points
        if cleaned.get("coverage") == "unknown":
            if not kept_points:
                return None
            cleaned["coverage"] = "known"
    return cleaned


def _trim_core_system_report_for_demo(
    data: Any, *, system_id: str | None = None, page: int = 1, page_size: int = 20
) -> Any:
    if not isinstance(data, dict):
        return data
    trimmed = dict(data)
    summary = trimmed.get("summary")
    if isinstance(summary, dict):
        patched_summary = _strip_diagnostic_fields(summary)
        for key in (
            "unavailable_records",
            "unknown_records",
            "unknown_points",
            "unknown_defects",
        ):
            if key in patched_summary:
                patched_summary[key] = 0
        trimmed["summary"] = patched_summary
    source_rows = trimmed.get("_export_rows")
    if not isinstance(source_rows, list):
        source_rows = trimmed.get("items") if isinstance(trimmed.get("items"), list) else []
    if system_id == "unknown":
        kept_rows = []
    else:
        kept_rows = [
            cleaned
            for row in source_rows
            if (cleaned := _trim_core_system_row_for_demo(row)) is not None
        ]
    trimmed["_export_rows"] = kept_rows
    trimmed["total"] = len(kept_rows)
    start = max(0, (page - 1) * page_size)
    trimmed["items"] = kept_rows[start : start + page_size]
    if isinstance(trimmed.get("systems"), list):
        trimmed["systems"] = [_strip_diagnostic_fields(s) for s in trimmed["systems"]]
    return trimmed


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
    if _is_restricted_demo_account(user):
        data = _trim_core_system_report_for_demo(
            data, system_id=params.get("system_id"), page=page, page_size=page_size
        )
    data.pop("_export_rows", None)
    return {"success": True, "data": data}


@router.get("/export")
def export(request: Request, params=Depends(filters), user=Depends(get_current_user)):
    data = _read(user, params)
    if _is_restricted_demo_account(user):
        data = _trim_core_system_report_for_demo(
            data, system_id=params.get("system_id")
        )
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
