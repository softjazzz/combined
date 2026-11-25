"""人工质控报表只读接口；统计口径为明确标注的待确认假设。"""

import logging
from collections import Counter
from datetime import date
from typing import Any, Literal

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
from .quality_reports import (
    _DEMO_UNCERTAIN_STATUSES,
    _is_restricted_demo_account,
    _strip_diagnostic_fields,
    _trim_csv_bytes_for_demo,
)

router = APIRouter(
    prefix="/api/v1/manual-quality-reports", tags=["manual-quality-reports"]
)
service = ManualQualityReportService()
logger = logging.getLogger(__name__)
_DEMO_HIDDEN_MANUAL_STATES = frozenset({"unknown", "source_unknown", "history_unknown"}) | _DEMO_UNCERTAIN_STATUSES


def _trim_manual_quality_report_for_demo(
    data: Any, *, page: int = 1, page_size: int = 20
) -> Any:
    if not isinstance(data, dict):
        return data
    trimmed = dict(data)
    source_rows = trimmed.get("_export_rows")
    if not isinstance(source_rows, list):
        source_rows = trimmed.get("items") if isinstance(trimmed.get("items"), list) else []
    kept_rows = [
        _strip_diagnostic_fields(row)
        for row in source_rows
        if isinstance(row, dict)
        and row.get("source_verified") is not False
        and str(row.get("review_status") or "").strip().lower()
        not in _DEMO_HIDDEN_MANUAL_STATES
        and str(row.get("rectification_status") or "").strip().lower()
        not in _DEMO_HIDDEN_MANUAL_STATES
    ]
    trimmed["_export_rows"] = kept_rows
    trimmed["total"] = len(kept_rows)
    start = max(0, (page - 1) * page_size)
    trimmed["items"] = kept_rows[start : start + page_size]
    summary = trimmed.get("summary")
    if isinstance(summary, dict):
        patched_summary = _strip_diagnostic_fields(summary)
        patched_summary["entered"] = len(kept_rows)
        if isinstance(patched_summary.get("review"), dict):
            review_counts = Counter(row.get("review_status") for row in kept_rows)
            patched_summary["review"] = {
                key: (0 if key in _DEMO_HIDDEN_MANUAL_STATES else review_counts[key])
                for key in patched_summary["review"]
            }
        if isinstance(patched_summary.get("rectification"), dict):
            rect_counts = Counter(row.get("rectification_status") for row in kept_rows)
            patched_summary["rectification"] = {
                key: (0 if key in _DEMO_HIDDEN_MANUAL_STATES else rect_counts[key])
                for key in patched_summary["rectification"]
            }
        trimmed["summary"] = patched_summary
    return trimmed


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
    if _is_restricted_demo_account(user):
        data = _trim_manual_quality_report_for_demo(
            data, page=page, page_size=page_size
        )
    data.pop("_export_rows", None)
    return {"success": True, "data": data}


@router.get("/export")
def export(request: Request, params=Depends(filters), user=Depends(get_current_user)):
    data = _read(user, params)
    is_demo = _is_restricted_demo_account(user)
    if is_demo:
        data = _trim_manual_quality_report_for_demo(data)
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
    content = csv_export(data["_export_rows"], data.get("as_of"))
    if is_demo:
        content_bytes = content.encode("utf-8") if isinstance(content, str) else content
        content = _trim_csv_bytes_for_demo(
            content_bytes,
            drop_headers=frozenset({"source_verified", "reason_code"}),
        )
    return Response(
        content,
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": 'attachment; filename="manual-quality-report.csv"',
            "Cache-Control": "no-store",
            "X-Content-Type-Options": "nosniff",
        },
    )
