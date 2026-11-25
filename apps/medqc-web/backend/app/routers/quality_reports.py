"""PR8报表只读消费子集，来源88e8f864b；不移植写入口与执行链。"""

from __future__ import annotations

import csv
import io
import json
import logging
from datetime import datetime
from typing import Any, Callable, Literal

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
_DEMO_PRIVILEGED_ROLES = frozenset({"sync_admin", "super_admin", "developer"})
_DEMO_HIDDEN_REMEDIATION_STATES = frozenset({"source_unknown", "history_unknown"})
_DEMO_UNCERTAIN_STATUSES = frozenset({"data_gap", "uncertain", "technical_error"})
_DEMO_ZERO_KEYS = frozenset(
    {
        "qc_unavailable_total",
        "unavailable_result_total",
        "selected_unavailable_result_total",
        "unavailable_records",
        "source_unknown",
        "history_unknown",
        "data_gap",
        "uncertain",
        "data_gap_count",
        "uncertain_count",
        "data_gap_record_total",
        "uncertain_record_total",
        "records_with_data_gap",
        "canonical_invalid_or_missing_total",
    }
)
_DEMO_DROP_KEYS = frozenset({"reason_code", "source_reason"})


def _is_restricted_demo_account(current_user: dict | None) -> bool:
    """仅对显式 is_demo_account is True 且非特权角色的受限演示账号生效。"""
    if not isinstance(current_user, dict):
        return False
    if current_user.get("is_demo_account") is not True:
        return False
    roles = {
        str(role).strip().lower()
        for role in (current_user.get("roles") or [])
        if isinstance(role, str) and role.strip()
    }
    single_role = current_user.get("role")
    if isinstance(single_role, str) and single_role.strip():
        roles.add(single_role.strip().lower())
    return not bool(roles & _DEMO_PRIVILEGED_ROLES)


def _strip_diagnostic_fields(value: Any) -> Any:
    if isinstance(value, dict):
        cleaned: dict[str, Any] = {}
        for key, item in value.items():
            if key in _DEMO_DROP_KEYS:
                continue
            if (
                key in _DEMO_ZERO_KEYS
                and isinstance(item, (int, float))
                and not isinstance(item, bool)
            ):
                cleaned[key] = 0
            else:
                cleaned[key] = _strip_diagnostic_fields(item)
        return cleaned
    if isinstance(value, list):
        return [_strip_diagnostic_fields(item) for item in value]
    return value


def _trim_csv_bytes_for_demo(
    content: bytes,
    *,
    drop_headers: frozenset[str] = frozenset(),
    drop_row: Callable[[dict[str, str]], bool] | None = None,
) -> bytes:
    has_bom = content.startswith(b"\xef\xbb\xbf")
    text = content.decode("utf-8-sig") if has_bom else content.decode("utf-8")
    rows = list(csv.reader(io.StringIO(text)))
    if not rows:
        return content
    headers = rows[0]
    keep_indices = [
        idx for idx, header in enumerate(headers) if header not in drop_headers
    ]
    out = io.StringIO(newline="")
    writer = csv.writer(out)
    writer.writerow([headers[idx] for idx in keep_indices])
    for row in rows[1:]:
        row_map = {
            headers[idx]: (row[idx] if idx < len(row) else "")
            for idx in range(len(headers))
        }
        if drop_row is not None and drop_row(row_map):
            continue
        writer.writerow([row[idx] if idx < len(row) else "" for idx in keep_indices])
    encoded = out.getvalue().encode("utf-8")
    return (b"\xef\xbb\xbf" + encoded) if has_bom else encoded


def _trim_record_quality_summary_for_demo(data: Any) -> Any:
    if not isinstance(data, dict):
        return data
    trimmed = _strip_diagnostic_fields(data)
    kpis = trimmed.get("kpis")
    if isinstance(kpis, dict):
        kpis = dict(kpis)
        if "qc_unavailable_total" in kpis:
            kpis["qc_unavailable_total"] = 0
        trimmed["kpis"] = kpis
    classification_unknown = trimmed.get("classification_unknown")
    if isinstance(classification_unknown, dict):
        trimmed["classification_unknown"] = {
            key: (
                0
                if isinstance(val, (int, float)) and not isinstance(val, bool)
                else val
            )
            for key, val in classification_unknown.items()
        }
    if "unavailable_dimensions" in trimmed:
        trimmed["unavailable_dimensions"] = []
    return trimmed


def _trim_record_quality_records_for_demo(
    data: Any, *, unknown_classification: str | None = None
) -> Any:
    if not isinstance(data, dict):
        return data
    trimmed = _strip_diagnostic_fields(data)
    if unknown_classification is not None:
        trimmed["items"] = []
        if "total" in trimmed:
            trimmed["total"] = 0
    return trimmed


def _trim_remediation_analysis_for_demo(analysis: Any) -> Any:
    if not isinstance(analysis, dict):
        return analysis
    trimmed = dict(analysis)
    state_counts = trimmed.get("state_counts")
    if isinstance(state_counts, dict):
        patched_counts = dict(state_counts)
        for hidden_state in _DEMO_HIDDEN_REMEDIATION_STATES:
            if hidden_state in patched_counts:
                patched_counts[hidden_state] = 0
        trimmed["state_counts"] = patched_counts
    rows = trimmed.get("rows")
    if isinstance(rows, list):
        trimmed["rows"] = [
            _strip_diagnostic_fields(row)
            for row in rows
            if not (
                isinstance(row, dict)
                and row.get("rectification_state") in _DEMO_HIDDEN_REMEDIATION_STATES
            )
        ]
    return trimmed


def _trim_remediation_page_for_demo(data: Any, *, label: str | None = None) -> Any:
    if not isinstance(data, dict):
        return data
    trimmed = _strip_diagnostic_fields(data)
    state_counts = trimmed.get("state_counts")
    if isinstance(state_counts, dict):
        patched_counts = dict(state_counts)
        for hidden_state in _DEMO_HIDDEN_REMEDIATION_STATES:
            if hidden_state in patched_counts:
                patched_counts[hidden_state] = 0
        trimmed["state_counts"] = patched_counts
    if label in _DEMO_HIDDEN_REMEDIATION_STATES:
        if "items" in trimmed:
            trimmed["items"] = []
        if "total" in trimmed:
            trimmed["total"] = 0
        return trimmed
    items = trimmed.get("items")
    if isinstance(items, list):
        kept = [
            item
            for item in items
            if not (
                isinstance(item, dict)
                and item.get("rectification_state") in _DEMO_HIDDEN_REMEDIATION_STATES
            )
        ]
        if len(kept) != len(items):
            removed = len(items) - len(kept)
            trimmed["items"] = kept
            if isinstance(trimmed.get("total"), int):
                trimmed["total"] = max(0, trimmed["total"] - removed)
    return trimmed


def _trim_frontpage_payload_for_demo(data: Any) -> Any:
    return _strip_diagnostic_fields(data)


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
    current_user: dict = Depends(require_roles("admin", "super_admin", "qc_manager")),
):
    query = _authorized_params(current_user, params)
    try:
        context = await run_in_threadpool(report_service.build_report_context, **query)
        data = await run_in_threadpool(report_service.summarize, context)
    except Exception as exc:
        _raise_report_error(exc, "summary")
    if _is_restricted_demo_account(current_user):
        data = _trim_record_quality_summary_for_demo(data)
    return success_response(data=data, trace_id=get_trace_id(request))


@router.get("/record-quality/records")
async def get_record_quality_records(
    request: Request,
    params: dict[str, Any] = Depends(_report_params),
    drilldown: dict[str, Any] = Depends(_drilldown_params),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: dict = Depends(require_roles("admin", "super_admin", "qc_manager")),
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
    if _is_restricted_demo_account(current_user):
        data = _trim_record_quality_records_for_demo(
            data, unknown_classification=drilldown.get("unknown_classification")
        )
    return success_response(data=data, trace_id=get_trace_id(request))


@router.get("/record-quality/remediations")
async def get_record_remediations(
    request: Request,
    params: dict[str, Any] = Depends(_report_params),
    label: str | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: dict = Depends(require_roles("admin", "super_admin", "qc_manager")),
):
    query = _authorized_params(current_user, params)
    actor_id = _task_actor_id(current_user)
    is_demo = _is_restricted_demo_account(current_user)
    try:
        context = await run_in_threadpool(report_service.build_report_context, **query)
        analysis = await run_in_threadpool(
            remediation_report_service.build_analysis, context, actor_id=actor_id
        )
        if is_demo:
            analysis = _trim_remediation_analysis_for_demo(analysis)
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
    if is_demo:
        data = _trim_remediation_page_for_demo(data, label=label)
    return success_response(data=data, trace_id=get_trace_id(request))


@router.get("/record-quality/remediations/export")
async def export_record_remediations(
    request: Request,
    params: dict[str, Any] = Depends(_report_params),
    label: str | None = Query(None),
    current_user: dict = Depends(require_roles("admin", "super_admin", "qc_manager")),
):
    query = _authorized_params(current_user, params)
    actor_id = _task_actor_id(current_user)
    is_demo = _is_restricted_demo_account(current_user)
    try:
        context = await run_in_threadpool(report_service.build_report_context, **query)
        analysis = await run_in_threadpool(
            remediation_report_service.build_analysis, context, actor_id=actor_id
        )
        if is_demo:
            analysis = _trim_remediation_analysis_for_demo(analysis)
        content = await run_in_threadpool(
            remediation_report_service.export_csv, analysis, label=label
        )
        if not isinstance(content, bytes):
            raise TypeError("整改分析导出服务未返回 CSV 字节")
        if is_demo:
            content = _trim_csv_bytes_for_demo(
                content,
                drop_headers=frozenset({"reason_code", "source_reason"}),
                drop_row=lambda row: (
                    label in _DEMO_HIDDEN_REMEDIATION_STATES
                    or row.get("rectification_state") in _DEMO_HIDDEN_REMEDIATION_STATES
                ),
            )
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
    current_user: dict = Depends(require_roles("admin", "super_admin", "qc_manager")),
):
    query = _authorized_params(current_user, params)
    is_demo = _is_restricted_demo_account(current_user)
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
        if is_demo:
            hide_all_rows = (
                sheet == "records"
                and drilldown.get("unknown_classification") is not None
            )
            content = _trim_csv_bytes_for_demo(
                content,
                drop_headers=frozenset(
                    {
                        "qc_unavailable_total",
                        "unavailable_result_total",
                        "reason_code",
                        "data_gap",
                        "uncertain",
                    }
                ),
                drop_row=(lambda _row: True) if hide_all_rows else None,
            )
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
    current_user: dict = Depends(require_roles("admin", "super_admin", "qc_manager")),
):
    query = _authorized_params(current_user, params)
    try:
        context = await run_in_threadpool(
            frontpage_report_service.build_report_context, **query
        )
        data = await run_in_threadpool(frontpage_report_service.summarize, context)
    except Exception as exc:
        _raise_frontpage_error(exc, "summary")
    if _is_restricted_demo_account(current_user):
        data = _trim_frontpage_payload_for_demo(data)
    return success_response(data=data, trace_id=get_trace_id(request))


@router.get("/frontpage-quality/records")
async def get_frontpage_quality_records(
    request: Request,
    params: dict[str, Any] = Depends(_frontpage_params),
    drilldown: dict[str, Any] = Depends(_frontpage_drilldown),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: dict = Depends(require_roles("admin", "super_admin", "qc_manager")),
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
    if _is_restricted_demo_account(current_user):
        data = _trim_frontpage_payload_for_demo(data)
    return success_response(data=data, trace_id=get_trace_id(request))


@router.get("/frontpage-quality/export")
async def export_frontpage_quality(
    request: Request,
    params: dict[str, Any] = Depends(_frontpage_params),
    drilldown: dict[str, Any] = Depends(_frontpage_drilldown),
    sheet: Literal["departments", "records"] = Query(...),
    current_user: dict = Depends(require_roles("admin", "super_admin", "qc_manager")),
):
    query = _authorized_params(current_user, params)
    is_demo = _is_restricted_demo_account(current_user)
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
        if is_demo:
            content = _trim_csv_bytes_for_demo(
                content,
                drop_headers=frozenset(
                    {
                        "qc_unavailable_total",
                        "unavailable_result_total",
                        "reason_code",
                        "data_gap",
                        "uncertain",
                    }
                ),
            )
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
