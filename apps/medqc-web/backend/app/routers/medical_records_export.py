"""病案数据 - 导出子域。"""

from typing import Optional

from fastapi import APIRouter, Query

from ..core.pagination import page_param, page_size_param
from ..services.medical_records.export_service import (
    get_frontpage_sheet,
    get_schema,
    get_table_data,
)
from .medical_records_common import raise_medical_records_http_error

router = APIRouter(tags=["病案数据-导出"])


@router.get("/schema")
async def get_schema_api():
    try:
        return get_schema()
    except Exception as exc:
        raise_medical_records_http_error(exc)


@router.get("/table-data/{table_name}")
async def get_table_data_api(
    table_name: str,
    page: int = page_param(),
    page_size: int = page_size_param(),
):
    try:
        return get_table_data(table_name, page=page, page_size=page_size)
    except Exception as exc:
        raise_medical_records_http_error(exc)


@router.get("/frontpage-sheet/{patient_id}/{visit_id}")
async def get_frontpage_sheet_api(
    patient_id: str,
    visit_id: str,
    institute_id: Optional[str] = Query(
        None,
        description="机构号；缺省时仅在 patient+visit 唯一时可读，命中多机构按定位不唯一拒绝",
    ),
):
    try:
        return get_frontpage_sheet(patient_id, visit_id, institute_id=institute_id)
    except Exception as exc:
        raise_medical_records_http_error(exc)
