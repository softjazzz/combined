"""病案数据 - 查询子域。"""

from datetime import date, datetime
from typing import Any, Dict, Literal, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request
from ..services.doctor_case_scope import get_doctor_case_scope

from ..core.security import get_current_user
from ..core.pagination import HEAVY_MAX_PAGE_SIZE, page_param, page_size_param
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


@router.get("/workstation")
async def get_workstation_data_api(
    request: Request,
    dept: Optional[str] = Query(None, description="科室筛选，不传则返回全部"),
    doctor: Optional[str] = Query(None, description="主管医师筛选，不传则返回全部"),
    keyword: Optional[str] = Query(None, description="搜索姓名/病案号"),
    start_date: Optional[date] = Query(None, description="筛选开始日期"),
    end_date: Optional[date] = Query(None, description="筛选结束日期"),
    date_field: Optional[str] = Query("visit", description="日期字段：visit/admission/discharge/updated"),
    hospital_status: Literal["all", "inpatient", "discharged"] = Query(
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
    page: int = page_param(description="页码"),
    page_size: int = page_size_param(default=50, max_value=HEAVY_MAX_PAGE_SIZE, description="每页条数"),
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
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    try:
        return get_workstation_data(
            dept=dept,
            doctor=doctor,
            keyword=keyword,
            start_date=start_date,
            end_date=end_date,
            date_field=date_field,
            hospital_status=hospital_status,
            sync_scope=sync_scope,
            inpatient_sort=inpatient_sort,
            page=page,
            page_size=page_size,
            analytics_job_id=str(analytics_job_id) if analytics_job_id else None,
            analytics_completed_from=analytics_completed_from,
            analytics_completed_to=analytics_completed_to,
            analytics_rule_id=analytics_rule_id,
            analytics_result_status=analytics_result_status,
            analytics_scope=analytics_scope,
            case_scope=get_doctor_case_scope(request),
        )
    except Exception as exc:
        raise_medical_records_http_error(exc)
