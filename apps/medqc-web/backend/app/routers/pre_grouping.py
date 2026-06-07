from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from ..core.response import get_trace_id, success_response
from ..core.security import get_current_user
from ..services.pre_grouping_event_service import (
    PreGroupingEventService,
    get_pre_grouping_history,
)
from ..services.grouping_correction_service import GroupingCorrectionService


router = APIRouter(prefix="/api/v1/pre-grouping", tags=["pre-grouping"])


class AdmissionNoteCompletedRequest(BaseModel):
    visit_id: str = Field(..., min_length=1)
    document_id: str = Field(..., min_length=1)
    patient_id: Optional[str] = None
    medical_text: str = Field(..., min_length=1)


class AdmissionNoteCompletedFromVisitRequest(BaseModel):
    visit_id: str = Field(..., min_length=1)
    document_id: str = Field(..., min_length=1)
    patient_id: Optional[str] = None


class GroupingCorrectionRequest(BaseModel):
    pdx_code: str = ""
    proc_codes: list[str] = Field(default_factory=list)
    grouping_result: Dict[str, Any] = Field(default_factory=dict)
    diagnosis_candidates: list[str] = Field(default_factory=list)
    procedure_candidates: list[str] = Field(default_factory=list)


@router.post("/admission-note-completed")
async def admission_note_completed(
    request: Request,
    payload: AdmissionNoteCompletedRequest,
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """入院记录完成后触发只读事前模拟入组。"""
    _ = current_user
    try:
        result = await PreGroupingEventService().on_admission_note_completed(
            visit_id=payload.visit_id,
            patient_id=payload.patient_id or "",
            document_id=payload.document_id,
            medical_text=payload.medical_text,
        )
        return success_response(data=result, trace_id=get_trace_id(request))
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))


@router.post("/admission-note-completed/from-visit")
async def admission_note_completed_from_visit(
    request: Request,
    payload: AdmissionNoteCompletedFromVisitRequest,
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """根据 visit_id 读取真实病历文书后触发只读事前模拟入组。"""
    _ = current_user
    from ..services.frontpage_extraction_service import FrontPageExtractionService

    medical_text = await FrontPageExtractionService()._get_medical_text(
        payload.visit_id,
        allow_demo_fallback=False,
    )
    if not medical_text.strip():
        raise HTTPException(
            status_code=422,
            detail="visit_id 未能读取到真实病历文书，无法触发自动预入组",
        )
    try:
        result = await PreGroupingEventService().on_admission_note_completed(
            visit_id=payload.visit_id,
            patient_id=payload.patient_id or "",
            document_id=payload.document_id,
            medical_text=medical_text,
        )
        return success_response(data=result, trace_id=get_trace_id(request))
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))


@router.get("/{visit_id}/history")
async def pre_grouping_history(
    request: Request,
    visit_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """查询指定病历的只读模拟入组历史。"""
    _ = current_user
    return success_response(
        data={
            "visit_id": visit_id,
            "items": get_pre_grouping_history(visit_id),
        },
        trace_id=get_trace_id(request),
    )


@router.post("/corrections")
async def grouping_corrections(
    request: Request,
    payload: GroupingCorrectionRequest,
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """生成 DRG/DIP 预入组修正建议，只读返回，不写正式业务表。"""
    _ = current_user
    result = GroupingCorrectionService().suggest_corrections(
        pdx_code=payload.pdx_code,
        proc_codes=payload.proc_codes,
        grouping_result=payload.grouping_result,
        diagnosis_candidates=payload.diagnosis_candidates,
        procedure_candidates=payload.procedure_candidates,
    )
    return success_response(data=result, trace_id=get_trace_id(request))
