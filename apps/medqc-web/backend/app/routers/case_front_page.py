from __future__ import annotations

from typing import Any, Dict, List

from fastapi import APIRouter, HTTPException, Query

from ..services.drg_demo_store import get_demo_drg_store

router = APIRouter(prefix="/api/v1/case-front-page", tags=["drg_case_front_page"])


@router.get("")
async def list_case_front_pages(limit: int = Query(100, ge=1, le=500)) -> List[Dict[str, Any]]:
    store = get_demo_drg_store()
    return store.list_cases(limit=limit)


@router.get("/{admission_id}")
async def get_case_front_page_detail(admission_id: str) -> Dict[str, Any]:
    store = get_demo_drg_store()
    item = store.get_case_detail(admission_id)
    if not item:
        raise HTTPException(status_code=404, detail=f"未找到住院号 {admission_id} 的病案首页")
    return item


@router.post("")
async def upsert_case_front_page(payload: Dict[str, Any]) -> Dict[str, Any]:
    admission_id = payload.get("admission_id")
    if not admission_id or not isinstance(admission_id, str):
        raise HTTPException(status_code=400, detail="admission_id is required")

    store = get_demo_drg_store()
    return store.upsert_case(admission_id=admission_id, patch=payload)


from pydantic import BaseModel

class ExtractCodingRequest(BaseModel):
    medical_text: str
    patient_age: int = 0
    patient_gender: str = "M"

@router.post("/extract-coding")
async def extract_coding(payload: ExtractCodingRequest) -> Dict[str, Any]:
    from ..services.external_coding_service import get_external_coding_service
    
    service = get_external_coding_service()
    
    try:
        result = await service.extract_coding(
            medical_text=payload.medical_text,
            patient_context={
                "age": payload.patient_age,
                "gender": payload.patient_gender
            }
        )
        return {
            "success": True,
            "data": result
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
