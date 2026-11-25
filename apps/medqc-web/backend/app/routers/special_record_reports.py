"""特殊病历报表及机构分类配置接口。"""

import logging
from datetime import date
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import Response
from pydantic import BaseModel, StrictInt

from ..core.audit import audit_event
from ..core.security import get_current_user
from ..services import special_record_report_service as report
from ..services import special_record_report_source_service as source
from ..services.defect_rectification_service import RectificationError
from .quality_reports import (
    _DEMO_UNCERTAIN_STATUSES,
    _is_restricted_demo_account,
    _strip_diagnostic_fields,
    _trim_csv_bytes_for_demo,
)

router = APIRouter(
    prefix="/api/v1/quality-reports/special-records", tags=["quality-reports"]
)
service = report.SpecialRecordReportService()
logger = logging.getLogger(__name__)


def _trim_special_record_row_for_demo(row: Any) -> Any:
    if not isinstance(row, dict):
        return row
    cleaned = _strip_diagnostic_fields(row)
    # 前端 SpecialReportRow / SpecialTypeFact 强校验 nullableText（null | string），
    # 演示态隐藏诊断码时必须保留 reason_code: None（JSON null）而非删键成 undefined。
    cleaned["reason_code"] = None
    raw_types = cleaned.get("types")
    if isinstance(raw_types, dict):
        cleaned["types"] = {
            key: (
                {**value, "reason_code": None}
                if isinstance(value, dict)
                else value
            )
            for key, value in raw_types.items()
        }
    defects = cleaned.get("defects")
    if isinstance(defects, list):
        cleaned["defects"] = [
            item
            for item in defects
            if not (
                isinstance(item, dict)
                and str(item.get("status") or "").strip().lower()
                in _DEMO_UNCERTAIN_STATUSES
            )
        ]
    return cleaned


def _trim_special_report_for_demo(
    data: Any, *, record_type_state: str = "positive"
) -> Any:
    if not isinstance(data, dict):
        return data
    trimmed = dict(data)
    summary = trimmed.get("summary")
    if isinstance(summary, dict):
        patched_summary = _strip_diagnostic_fields(summary)
        for key in (
            "unavailable_result_total",
            "selected_unavailable_result_total",
            "unknown_type_total",
        ):
            if key in patched_summary:
                patched_summary[key] = 0
        trimmed["summary"] = patched_summary
    types = trimmed.get("types")
    if isinstance(types, list):
        patched_types = []
        for item in types:
            if not isinstance(item, dict):
                patched_types.append(item)
                continue
            entry = _strip_diagnostic_fields(item)
            if "unknown_total" in entry:
                entry["unknown_total"] = 0
            if "known_positive_total" in entry and entry.get("count") is None:
                entry["count"] = entry["known_positive_total"]
            if entry.get("status") in {"partial", "unknown"}:
                entry["status"] = "known"
            patched_types.append(entry)
        trimmed["types"] = patched_types
    records = trimmed.get("_records")
    if isinstance(records, list):
        if record_type_state == "unknown":
            kept_records = []
        else:
            kept_records = [
                _trim_special_record_row_for_demo(row)
                for row in records
                if not (
                    isinstance(row, dict)
                    and (
                        row.get("defect_status") == "unknown"
                        or row.get("report_score_status") == "unavailable"
                    )
                )
            ]
        trimmed["_records"] = kept_records
        if isinstance(trimmed.get("summary"), dict):
            trimmed["summary"]["record_total"] = len(kept_records)
            if "known_result_total" in trimmed["summary"]:
                trimmed["summary"]["known_result_total"] = len(kept_records)
            scored_count = sum(
                1
                for row in kept_records
                if isinstance(row, dict) and row.get("report_score_status") == "scored"
            )
            if "graded_total" in trimmed["summary"]:
                trimmed["summary"]["graded_total"] = scored_count
            if "unscored_total" in trimmed["summary"]:
                trimmed["summary"]["unscored_total"] = max(
                    0, len(kept_records) - scored_count
                )
            if "ungraded_total" in trimmed["summary"]:
                trimmed["summary"]["ungraded_total"] = max(
                    0, len(kept_records) - scored_count
                )
    for key in ("_defects", "top_defects"):
        if isinstance(trimmed.get(key), list):
            trimmed[key] = [
                _strip_diagnostic_fields(item)
                for item in trimmed[key]
                if not (
                    isinstance(item, dict)
                    and str(item.get("status") or "").strip().lower()
                    in _DEMO_UNCERTAIN_STATUSES
                )
            ]
    return trimmed


def filters(
    institute_id: str = Query(..., min_length=1, max_length=100),
    discharged_from: date = Query(...),
    discharged_to: date = Query(...),
    department: str | None = Query(None, max_length=100),
    record_type: str | None = Query(None, max_length=30),
    record_type_state: Literal["positive", "negative", "unknown"] = "positive",
    grade: str | None = Query(None, max_length=50),
    rule_id: str | None = Query(None, max_length=100),
):
    return dict(
        institute_id=institute_id,
        discharged_from=discharged_from,
        discharged_to=discharged_to,
        department=department,
        record_type=record_type,
        record_type_state=record_type_state,
        grade=grade,
        rule_id=rule_id,
    )


def actor_id(user):
    identifier = user.get("id") or user.get("user_id")
    if not isinstance(identifier, str) or not identifier.strip():
        raise HTTPException(403, "缺少可信账号身份")
    return identifier.strip()


def invoke(function, *args, **kwargs):
    try:
        return function(*args, **kwargs)
    except RectificationError as exc:
        raise HTTPException(exc.status, str(exc)) from None
    except source.SpecialReportInvalid as exc:
        raise HTTPException(422, str(exc)) from None
    except source.SpecialReportConflict as exc:
        raise HTTPException(409, str(exc)) from None
    except Exception as exc:
        logger.warning(
            "special_record_report_unavailable error_type=%s", type(exc).__name__
        )
        raise HTTPException(503, "特殊病历报表来源暂不可用，请稍后重试") from None


@router.get("")
def summary(params=Depends(filters), user=Depends(get_current_user)):
    data = invoke(service.report, actor_id(user), **params)
    if _is_restricted_demo_account(user):
        data = _trim_special_report_for_demo(
            data, record_type_state=params.get("record_type_state", "positive")
        )
    return {
        "success": True,
        "data": {key: value for key, value in data.items() if not key.startswith("_")},
    }


@router.get("/records")
def records(
    params=Depends(filters),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    user=Depends(get_current_user),
):
    data = invoke(service.report, actor_id(user), **params)
    is_demo = _is_restricted_demo_account(user)
    if is_demo:
        data = _trim_special_report_for_demo(
            data, record_type_state=params.get("record_type_state", "positive")
        )
    paged = invoke(report.page, data, page=page, page_size=page_size)
    if is_demo and isinstance(paged, dict) and isinstance(paged.get("items"), list):
        paged = {
            **paged,
            "items": [_trim_special_record_row_for_demo(row) for row in paged["items"]],
        }
    return {
        "success": True,
        "data": paged,
    }


@router.get("/defects")
def defects(
    params=Depends(filters),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    user=Depends(get_current_user),
):
    data = invoke(service.report, actor_id(user), **params)
    is_demo = _is_restricted_demo_account(user)
    if is_demo:
        data = _trim_special_report_for_demo(
            data, record_type_state=params.get("record_type_state", "positive")
        )
    paged = invoke(report.page, data, kind="defects", page=page, page_size=page_size)
    if is_demo:
        paged = _strip_diagnostic_fields(paged)
    return {
        "success": True,
        "data": paged,
    }


@router.get("/export")
def export(
    request: Request,
    params=Depends(filters),
    kind: Literal["records", "defects", "summary"] = "summary",
    user=Depends(get_current_user),
):
    data = invoke(service.report, actor_id(user), **params)
    is_demo = _is_restricted_demo_account(user)
    if is_demo:
        data = _trim_special_report_for_demo(
            data, record_type_state=params.get("record_type_state", "positive")
        )
    content = invoke(report.export_csv, data, kind=kind)
    if is_demo and isinstance(content, bytes):
        content = _trim_csv_bytes_for_demo(
            content,
            drop_headers=frozenset({"reason_code"}),
            drop_row=(
                (lambda row: row.get("字段") in {
                    "unavailable_result_total",
                    "selected_unavailable_result_total",
                    "unknown_type_total",
                } or str(row.get("字段") or "").endswith(".unknown_total"))
                if kind == "summary"
                else None
            ),
        )
    audit_event(
        request,
        action="quality_reports.special_records.export",
        resource=router.prefix + "/export",
        outcome="success",
        current_user=user,
        details={"kind": kind, "row_count": data["summary"]["record_total"]},
    )
    return Response(
        content,
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": f'attachment; filename="special-records-{kind}.csv"',
            "Cache-Control": "no-store",
            "X-Content-Type-Options": "nosniff",
            "X-Special-Classification-Version": str(
                data["scope"]["classification_version_seq"]
            ),
            "X-Special-Standard-Id": str(
                data["score_standard"].get("standard_id") or ""
            ),
            "X-Special-Standard-Version": str(
                data["score_standard"].get("standard_version_seq") or ""
            ),
            "X-Special-Binding-Version": str(
                data["score_standard"].get("binding_version_seq") or ""
            ),
        },
    )


class ConfigBody(BaseModel):
    version_seq: StrictInt
    config: dict[str, Any]


@router.get("/config")
def config(
    institute_id: str = Query(..., min_length=1, max_length=100),
    user=Depends(get_current_user),
):
    return {
        "success": True,
        "data": invoke(source.read_config, actor_id(user), institute_id),
    }


@router.put("/config")
def save_config(
    request: Request,
    body: ConfigBody,
    institute_id: str = Query(..., min_length=1, max_length=100),
    user=Depends(get_current_user),
):
    data = invoke(
        source.write_config,
        actor_id(user),
        institute_id,
        version_seq=body.version_seq,
        config=body.config,
    )
    audit_event(
        request,
        action="quality_reports.special_records.config",
        resource=router.prefix + "/config",
        outcome="success",
        current_user=user,
        details={"version_seq": data["version_seq"]},
    )
    return {"success": True, "data": data}
