"""病案数据 - 详情子域。"""

from functools import lru_cache
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, HTTPException, Query, Request

from ..services.medical_records import detail_service as medical_records_detail_service
from ..services.medical_records.detail_service import (
    get_cost,
    get_diagnoses,
    get_frontpage,
    get_frontpage_by_mr_no,
    get_record_content,
    get_surgeries,
)
from .medical_records_common import raise_medical_records_http_error

router = APIRouter(tags=["病案数据-详情"])


@lru_cache(maxsize=1)
def _load_detail_service_py_module():
    module_path = Path(__file__).resolve().parents[1] / "services" / "medical_records" / "detail_service.py"
    package_root = __name__.split(".", 1)[0] or "app"
    spec = spec_from_file_location(
        f"{package_root}.services.medical_records.detail_service_py_runtime",
        str(module_path),
    )
    if spec is None or spec.loader is None:
        raise RuntimeError(f"无法加载 detail_service.py: {module_path}")
    module = module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _get_documents_runtime_callable():
    # 生产环境可能优先加载 Cython .pyd；当前版本在 RowMapping 入参上存在严格类型问题，
    # 路由层优先切换到 .py 实现，确保文书列表可正常返回。
    module_file = str(getattr(medical_records_detail_service, "__file__", "")).lower()
    if module_file.endswith(".pyd"):
        return _load_detail_service_py_module().get_documents
    return medical_records_detail_service.get_documents


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
    request: Request,
    visit_id: str,
    mode: Optional[str] = Query(None, description="返回模式: 默认返回列表, concat=拼接全文"),
):
    try:
        own_identity = getattr(request.state, "doctor_case_identity", None)
        if own_identity:
            from ..services.bundles.current_view import load_current_documents

            result = load_current_documents(**own_identity)
            if mode == "concat":
                content = "\n\n".join(doc.get("content", "") for doc in result["documents"])
                return {"text": content, "visit_id": visit_id, "mode": "concat", "total_length": len(content),
                        "document_count": sum(bool(doc.get("has_content")) for doc in result["documents"])}
            return result
        get_documents_impl = _get_documents_runtime_callable()
        return get_documents_impl(visit_id, mode=mode)
    except Exception as exc:
        raise_medical_records_http_error(exc)
