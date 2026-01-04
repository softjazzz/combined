from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from ..services.drg_demo_store import get_demo_drg_store

router = APIRouter(prefix="/api/v1/drg", tags=["drg"])


class DRGPredictRequest(BaseModel):
    admission_id: str
    region: Optional[str] = None


class HandleSuggestionRequest(BaseModel):
    suggestion_id: int
    action: str  # accept / reject
    handled_by: Optional[str] = None


class HandleAlertRequest(BaseModel):
    alert_id: int
    action: str  # acknowledge / resolve
    handled_by: Optional[str] = None


@router.post("/predict")
async def predict_drg_grouping(payload: DRGPredictRequest) -> Dict[str, Any]:
    from ..services.drg_grouping_service import get_drg_grouping_service
    
    store = get_demo_drg_store()
    case = store.get_case_detail(payload.admission_id)
    if not case:
        raise HTTPException(status_code=404, detail=f"未找到住院号 {payload.admission_id} 的病案首页")

    # 从病案首页提取分组所需信息
    primary_diagnosis = case.get("principal_diagnosis_code", "I10.x00")
    secondary_diagnoses = case.get("secondary_diagnosis_codes", [])
    procedures = case.get("procedure_codes", [])
    patient_age = case.get("patient_age", 58)
    patient_gender = case.get("patient_gender", "M")
    los = case.get("hospital_days", 7)
    total_cost = float(case.get("total_cost") or 0.0)
    
    # 调用真实 DRG 分组 API
    service = get_drg_grouping_service()
    result = await service.group_drg(
        primary_diagnosis=primary_diagnosis,
        secondary_diagnoses=secondary_diagnoses,
        procedures=procedures,
        patient_age=patient_age,
        patient_gender=patient_gender,
        los=los,
        city_name=payload.region or "四川省",
        total_fee=total_cost
    )
    
    # 计算盈亏
    baseline_payment = result.get("baseline_payment", 0)
    profit_margin = round((baseline_payment - total_cost) / baseline_payment, 4) if baseline_payment else 0.0
    result["actual_cost"] = total_cost
    result["profit_margin"] = profit_margin
    
    # 记录分组历史
    store.append_grouping_history(payload.admission_id, result)

    return {"data": result, "message": "分组成功" if result.get("success") else "分组失败（降级模式）"}


@router.get("/grouping/{admission_id}/history")
async def get_grouping_history(admission_id: str) -> Dict[str, Any]:
    store = get_demo_drg_store()
    history = store.get_grouping_history(admission_id)
    return {"history": history, "total": len(history)}


@router.get("/suggestions")
async def list_coding_suggestions(
    admission_id: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
) -> Dict[str, Any]:
    store = get_demo_drg_store()
    items = store.list_suggestions(admission_id=admission_id, status=status, limit=limit)
    return {"suggestions": items, "total": len(items)}


@router.post("/suggestions/handle")
async def handle_coding_suggestion(payload: HandleSuggestionRequest) -> Dict[str, Any]:
    store = get_demo_drg_store()
    new_status = "accepted" if payload.action == "accept" else "rejected"
    ok = store.update_suggestion_status(payload.suggestion_id, new_status)
    if not ok:
        raise HTTPException(status_code=404, detail="建议未找到或更新失败")
    return {"success": True, "message": "建议已处理"}


@router.get("/alerts")
async def get_drg_alerts(
    admission_id: Optional[str] = Query(None),
    alert_level: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
) -> Dict[str, Any]:
    store = get_demo_drg_store()
    items = store.list_alerts(admission_id=admission_id, alert_level=alert_level, status=status, limit=limit)
    return {"alerts": items, "total": len(items)}


@router.post("/alerts/handle")
async def handle_drg_alert(payload: HandleAlertRequest) -> Dict[str, Any]:
    store = get_demo_drg_store()
    new_status = "acknowledged" if payload.action == "acknowledge" else "resolved"
    ok = store.update_alert_status(payload.alert_id, new_status)
    if not ok:
        raise HTTPException(status_code=404, detail="预警未找到或更新失败")
    return {"success": True, "message": "预警已处理"}


@router.get("/demo/story-cases")
async def get_demo_story_cases() -> Dict[str, Any]:
    store = get_demo_drg_store()
    cases = store.story_cases
    if not cases:
        return {"cases": []}
    return {
        "cases": [
            {"name": "高风险亏损", "admission_id": cases.high_risk_loss},
            {"name": "编码冲突", "admission_id": cases.coding_conflict},
            {"name": "高费用预警", "admission_id": cases.high_cost_alert},
        ]
    }
