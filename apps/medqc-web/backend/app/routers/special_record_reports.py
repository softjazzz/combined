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

router = APIRouter(
    prefix="/api/v1/quality-reports/special-records", tags=["quality-reports"]
)
service = report.SpecialRecordReportService()
logger = logging.getLogger(__name__)


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
    return {
        "success": True,
        "data": invoke(report.page, data, page=page, page_size=page_size),
    }


@router.get("/defects")
def defects(
    params=Depends(filters),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    user=Depends(get_current_user),
):
    data = invoke(service.report, actor_id(user), **params)
    return {
        "success": True,
        "data": invoke(
            report.page, data, kind="defects", page=page, page_size=page_size
        ),
    }


@router.get("/export")
def export(
    request: Request,
    params=Depends(filters),
    kind: Literal["records", "defects", "summary"] = "summary",
    user=Depends(get_current_user),
):
    data = invoke(service.report, actor_id(user), **params)
    content = invoke(report.export_csv, data, kind=kind)
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
