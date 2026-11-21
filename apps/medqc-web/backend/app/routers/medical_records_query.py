"""病案数据 - 查询子域。"""

import json
from datetime import date, datetime
from typing import Annotated, Any, Dict, Literal, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, ConfigDict, Field, StrictStr

from ..core.pagination import HEAVY_MAX_PAGE_SIZE, page_param, page_size_param
from ..core.security import get_current_user
from ..services.case_identity import CaseRef
from ..services.doctor_case_scope import get_doctor_case_scope
from ..services.medical_records.query_service import (
    get_departments,
    get_stats,
    get_workstation_data,
    list_medical_records,
)
from ..services.medical_records.hospitalization_status_service import (
    default_hospitalization_status_service,
)
from .medical_records_common import raise_medical_records_http_error

router = APIRouter(tags=["病案数据-查询"])


@router.post("/workstation/hospitalization-status/verify")
async def verify_workstation_hospitalization_status(
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """轻量核验病历池病例当前是否仍在院，不同步病历文书。"""

    try:
        return default_hospitalization_status_service.verify_current_statuses()
    except Exception as exc:
        raise_medical_records_http_error(exc)


@router.get("/list")
async def list_medical_records_api(
    request: Request,
    dept: Optional[str] = Query(None, description="科室筛选"),
    keyword: Optional[str] = Query(None, description="患者姓名/病案号搜索"),
    start_date: Optional[date] = Query(None, description="入院开始日期"),
    end_date: Optional[date] = Query(None, description="出院截止日期"),
    page: int = page_param(description="页码"),
    page_size: int = page_size_param(description="每页条数"),
):
    try:
        return list_medical_records(
            dept=dept,
            keyword=keyword,
            start_date=start_date,
            end_date=end_date,
            page=page,
            page_size=page_size,
            case_scope=get_doctor_case_scope(request),
        )
    except Exception as exc:
        raise_medical_records_http_error(exc)


@router.get("/stats")
async def get_stats_api(
    request: Request,
    dept: Optional[str] = Query(None, description="科室筛选"),
    start_date: Optional[date] = Query(None),
    end_date: Optional[date] = Query(None),
):
    try:
        return get_stats(dept=dept, start_date=start_date, end_date=end_date, case_scope=get_doctor_case_scope(request))
    except Exception as exc:
        raise_medical_records_http_error(exc)


@router.get("/departments")
async def get_departments_api(request: Request):
    try:
        return get_departments(case_scope=get_doctor_case_scope(request))
    except Exception as exc:
        raise_medical_records_http_error(exc)


def _workstation_filters(
    dept: Optional[str] = Query(None, description="科室筛选，不传则返回全部"),
    doctor: Optional[str] = Query(None, description="主管医师筛选，不传则返回全部"),
    keyword: Optional[str] = Query(None, description="搜索姓名/病案号"),
    start_date: Optional[date] = Query(None, description="筛选开始日期"),
    end_date: Optional[date] = Query(None, description="筛选结束日期"),
    date_field: Optional[str] = Query("visit", description="日期字段：visit/admission/discharge/updated"),
    hospital_status: Literal["all", "inpatient", "discharged", "unknown"] = Query(
        "all",
        description="住院状态：all/inpatient/discharged；按权威出院时间判定",
    ),
    sync_scope: Literal["all", "today_inpatient"] = Query(
        "all",
        description="快捷范围：today_inpatient 仅返回今日已核验且仍在院的病历",
    ),
    inpatient_sort: Literal["default", "longest", "recent"] = Query(
        "default",
        description="在院病历排序：default/longest/recent",
    ),
    analytics_job_id: Optional[UUID] = Query(None, description="统计下钻的已完成根任务 ID"),
    analytics_completed_from: Optional[datetime] = Query(None, description="统计下钻完成时间起点"),
    analytics_completed_to: Optional[datetime] = Query(None, description="统计下钻完成时间终点"),
    analytics_rule_id: Optional[str] = Query(None, description="统计下钻规则 ID"),
    analytics_result_status: Optional[
        Literal[
            "non_compliant",
            "data_gap",
            "uncertain",
            "compliant",
            "not_applicable",
            "not_executed",
            "technical_error",
        ]
    ] = Query(None, description="统计下钻 Canonical 结果状态"),
    analytics_scope: Optional[Literal["final"]] = Query(None, description="统计下钻资料范围"),
) -> dict[str, Any]:
    return dict(
        dept=dept,
        doctor=doctor,
        keyword=keyword,
        start_date=start_date,
        end_date=end_date,
        date_field=date_field,
        hospital_status=hospital_status,
        sync_scope=sync_scope,
        inpatient_sort=inpatient_sort,
        analytics_job_id=str(analytics_job_id) if analytics_job_id else None,
        analytics_completed_from=analytics_completed_from,
        analytics_completed_to=analytics_completed_to,
        analytics_rule_id=analytics_rule_id,
        analytics_result_status=analytics_result_status,
        analytics_scope=analytics_scope,
    )


def _query_workstation(request: Request, **parameters: Any):
    # CDM 和业务摘要使用同步数据库调用，交由 FastAPI 在线程池执行。
    try:
        return get_workstation_data(case_scope=get_doctor_case_scope(request), **parameters)
    except Exception as exc:
        raise_medical_records_http_error(exc)


@router.get("/workstation")
def get_workstation_data_api(
    request: Request,
    filters: dict[str, Any] = Depends(_workstation_filters),
    page: int = page_param(description="页码"),
    page_size: int = page_size_param(default=50, max_value=HEAVY_MAX_PAGE_SIZE, description="每页条数"),
    qc_summary_mode: Literal["inline", "deferred", "only"] = Query("inline"),
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    return _query_workstation(
        request, **filters, page=page, page_size=page_size, qc_summary_mode=qc_summary_mode,
    )


# 三个 100 字符的坐标即使全部被 JSON 转义也在此上限内。
_RECORD_COORDINATE_MAX_LENGTH = 100


class WorkstationQcSummaryRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    record_keys: list[Annotated[StrictStr, Field(max_length=3 * 6 * _RECORD_COORDINATE_MAX_LENGTH + 10)]] = Field(
        max_length=HEAVY_MAX_PAGE_SIZE,
    )

    def identities(self) -> tuple[CaseRef, ...]:
        identities: dict[CaseRef, None] = {}
        for key in self.record_keys:
            try:
                parts = json.loads(key)
            except (ValueError, RecursionError) as exc:
                raise HTTPException(422, "病历三坐标键无效") from exc
            if not isinstance(parts, list) or len(parts) != 3 or any(
                not isinstance(part, str) or not part.strip() or "\x00" in part
                or len(part) > _RECORD_COORDINATE_MAX_LENGTH
                for part in parts
            ):
                raise HTTPException(422, "病历三坐标键无效")
            identity = CaseRef(*parts)
            if key != identity.as_key():
                raise HTTPException(422, "病历三坐标键无效")
            identities[identity] = None
        return tuple(identities)


@router.post("/workstation/qc-summary")
def get_workstation_qc_summary_api(
    request: Request,
    body: WorkstationQcSummaryRequest,
    filters: dict[str, Any] = Depends(_workstation_filters),
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """按已显示的病历取行摘要，并按相同筛选取全集统计。"""
    return _query_workstation(
        request, **filters, qc_summary_mode="only", qc_summary_identities=body.identities(),
    )
