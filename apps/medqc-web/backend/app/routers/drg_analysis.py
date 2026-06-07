from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse

from ..services.drg import analysis_service
from ..services import drg_batch_store

router = APIRouter()


def _drg_router():
    from . import drg as drg_router

    return drg_router


@router.get("/analysis")
async def get_drg_analysis(
    dimension: str = Query(
        "hospital",
        description="分析维度: hospital/department/ward/attending_group/person/diagnosis_group/drg，doctor 兼容为 person",
    ),
    start_date: Optional[str] = Query(None, description="开始日期"),
    end_date: Optional[str] = Query(None, description="结束日期"),
    filter_id: Optional[str] = Query(None, description="筛选ID"),
    session_id: Optional[str] = Query(None, description="Session ID（有则优先分析上传数据）"),
    batch_id: Optional[str] = Query(None, description="批次ID"),
    department: Optional[str] = Query(None, description="科室筛选"),
    doctor: Optional[str] = Query(None, description="医师筛选"),
) -> Dict[str, Any]:
    normalized_dimension = dimension.strip().lower()
    if normalized_dimension == "doctor":
        normalized_dimension = "person"
    if normalized_dimension not in {
        "hospital",
        "department",
        "ward",
        "attending_group",
        "person",
        "diagnosis_group",
        "drg",
    }:
        raise HTTPException(status_code=400, detail="dimension 参数非法")
    try:
        payload = analysis_service.build_analysis_payload(
            dimension=normalized_dimension,
            start_date=start_date,
            end_date=end_date,
            filter_id=filter_id,
            session_id=session_id,
            batch_id=batch_id,
            department=department,
            doctor=doctor,
            batch_store=drg_batch_store,
            demo_store=_drg_router().get_demo_drg_store(),
        )
        return {"success": True, "data": payload}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/analysis/export/{file_format}")
async def export_drg_analysis(
    file_format: str,
    dimension: str = Query("hospital"),
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    filter_id: Optional[str] = Query(None),
    session_id: Optional[str] = Query(None),
    batch_id: Optional[str] = Query(None),
    department: Optional[str] = Query(None),
    doctor: Optional[str] = Query(None),
    version_id: Optional[str] = Query(None, description="分析版本标识"),
) -> StreamingResponse:
    normalized_dimension = dimension.strip().lower()
    if normalized_dimension == "doctor":
        normalized_dimension = "person"
    return analysis_service.build_analysis_export_response(
        file_format=file_format,
        dimension=normalized_dimension,
        start_date=start_date,
        end_date=end_date,
        filter_id=filter_id,
        session_id=session_id,
        batch_id=batch_id,
        department=department,
        doctor=doctor,
        version_id=version_id,
        batch_store=drg_batch_store,
        demo_store=_drg_router().get_demo_drg_store(),
    )
