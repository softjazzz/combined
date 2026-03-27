"""病案数据 - 查询子域。"""

from datetime import date
from typing import Optional

from fastapi import APIRouter, Query

from ..core.pagination import HEAVY_MAX_PAGE_SIZE, page_param, page_size_param
from ..services.medical_records.query_service import (
    get_departments,
    get_stats,
    get_workstation_data,
    list_medical_records,
)
from .medical_records_common import raise_medical_records_http_error

router = APIRouter(tags=["病案数据-查询"])


@router.get("/list")
async def list_medical_records_api(
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
        )
    except Exception as exc:
        raise_medical_records_http_error(exc)


@router.get("/stats")
async def get_stats_api(
    dept: Optional[str] = Query(None, description="科室筛选"),
    start_date: Optional[date] = Query(None),
    end_date: Optional[date] = Query(None),
):
    try:
        return get_stats(dept=dept, start_date=start_date, end_date=end_date)
    except Exception as exc:
        raise_medical_records_http_error(exc)


@router.get("/departments")
async def get_departments_api():
    try:
        return get_departments()
    except Exception as exc:
        raise_medical_records_http_error(exc)


@router.get("/workstation")
async def get_workstation_data_api(
    dept: Optional[str] = Query(None, description="科室筛选，不传则返回全部"),
    keyword: Optional[str] = Query(None, description="搜索姓名/病案号"),
    page: int = page_param(description="页码"),
    page_size: int = page_size_param(default=50, max_value=HEAVY_MAX_PAGE_SIZE, description="每页条数"),
):
    try:
        return get_workstation_data(dept=dept, keyword=keyword, page=page, page_size=page_size)
    except Exception as exc:
        raise_medical_records_http_error(exc)
