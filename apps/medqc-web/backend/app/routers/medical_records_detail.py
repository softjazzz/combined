"""病案数据 - 详情子域。"""

from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from ..services.medical_records.detail_service import (
    get_cost,
    get_diagnoses,
    get_documents,
    get_frontpage,
    get_frontpage_by_mr_no,
    get_record_content,
    get_surgeries,
)
from .medical_records_common import raise_medical_records_http_error

router = APIRouter(tags=["病案数据-详情"])


@router.get("/frontpage/{institute_id}/{patient_id}/{visit_id}")
async def get_frontpage_api(institute_id: str, patient_id: str, visit_id: str):
    try:
        fp = get_frontpage(institute_id, patient_id, visit_id)
        if not fp:
            raise HTTPException(status_code=404, detail="病案首页未找到")
        return fp
    except HTTPException:
        raise
    except Exception as exc:
        raise_medical_records_http_error(exc)


@router.get("/frontpage-by-mr/{mr_no}")
async def get_frontpage_by_mr_no_api(mr_no: str):
    try:
        return get_frontpage_by_mr_no(mr_no)
    except Exception as exc:
        raise_medical_records_http_error(exc)


@router.get("/diagnoses/{institute_id}/{patient_id}/{visit_id}")
async def get_diagnoses_api(institute_id: str, patient_id: str, visit_id: str):
    try:
        return get_diagnoses(institute_id, patient_id, visit_id)
    except Exception as exc:
        raise_medical_records_http_error(exc)


@router.get("/surgeries/{institute_id}/{patient_id}/{visit_id}")
async def get_surgeries_api(institute_id: str, patient_id: str, visit_id: str):
    try:
        return get_surgeries(institute_id, patient_id, visit_id)
    except Exception as exc:
        raise_medical_records_http_error(exc)


@router.get("/cost/{institute_id}/{patient_id}/{visit_id}")
async def get_cost_api(institute_id: str, patient_id: str, visit_id: str):
    try:
        cost = get_cost(institute_id, patient_id, visit_id)
        if not cost:
            raise HTTPException(status_code=404, detail="费用数据未找到")
        return cost
    except HTTPException:
        raise
    except Exception as exc:
        raise_medical_records_http_error(exc)


@router.get("/record-content/{institute_id}/{patient_id}/{visit_id}")
async def get_record_content_api(
    institute_id: str,
    patient_id: str,
    visit_id: str,
    record_type: str = Query("admission", description="记录类型: admission/discharge"),
):
    try:
        content = get_record_content(institute_id, patient_id, visit_id, record_type)
        if not content:
            raise HTTPException(status_code=404, detail="病历记录未找到")
        return {"content": content}
    except HTTPException:
        raise
    except Exception as exc:
        raise_medical_records_http_error(exc)


@router.get("/documents/{visit_id}")
async def get_documents_api(
    visit_id: str,
    mode: Optional[str] = Query(None, description="返回模式: 默认返回列表, concat=拼接全文"),
):
    try:
        return get_documents(visit_id, mode=mode)
    except Exception as exc:
        raise_medical_records_http_error(exc)
