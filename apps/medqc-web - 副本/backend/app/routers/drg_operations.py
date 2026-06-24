from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, File, HTTPException, Query, Request, UploadFile
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from ..core.security import get_current_user
from ..services import drg_batch_store
from ..services.drg import batch_service, batch_task_service, case_service

router = APIRouter()


def _drg_router():
    from . import drg as drg_router

    return drg_router


class DRGPredictRequest(BaseModel):
    admission_id: str
    region: Optional[str] = None


class RealtimeDRGRequest(BaseModel):
    primary_diagnosis_code: str
    primary_diagnosis_text: Optional[str] = None
    secondary_diagnosis_codes: Optional[List[str]] = None
    procedure_codes: Optional[List[str]] = None
    patient_age: int = 50
    patient_gender: str = "M"
    los: int = 7
    total_cost: float = 0
    region: str = "四川省"


class HandleSuggestionRequest(BaseModel):
    suggestion_id: int
    action: str
    handled_by: Optional[str] = None


class HandleAlertRequest(BaseModel):
    alert_id: int
    action: str
    handled_by: Optional[str] = None


@router.post("/predict-realtime")
async def predict_drg_realtime(payload: RealtimeDRGRequest) -> Dict[str, Any]:
    service = _drg_router().get_drg_grouping_service()
    return await case_service.predict_realtime(
        service,
        primary_diagnosis_code=payload.primary_diagnosis_code,
        secondary_diagnosis_codes=payload.secondary_diagnosis_codes,
        procedure_codes=payload.procedure_codes,
        patient_age=payload.patient_age,
        patient_gender=payload.patient_gender,
        los=payload.los,
        region=payload.region,
        total_cost=payload.total_cost,
    )


@router.post("/predict")
async def predict_drg_grouping(payload: DRGPredictRequest) -> Dict[str, Any]:
    store = _drg_router().get_demo_drg_store()
    service = _drg_router().get_drg_grouping_service()
    try:
        return await case_service.predict_from_case(
            store,
            service,
            admission_id=payload.admission_id,
            region=payload.region,
        )
    except case_service.DRGCaseNotFoundError:
        raise HTTPException(status_code=404, detail=f"未找到住院号 {payload.admission_id} 的病案首页")


@router.get("/grouping/{admission_id}/history")
async def get_grouping_history(admission_id: str) -> Dict[str, Any]:
    store = _drg_router().get_demo_drg_store()
    return case_service.get_grouping_history(store, admission_id=admission_id)


@router.get("/suggestions")
async def list_coding_suggestions(
    admission_id: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
) -> Dict[str, Any]:
    store = _drg_router().get_demo_drg_store()
    return case_service.list_suggestions(store, admission_id=admission_id, status=status, limit=limit)


@router.post("/suggestions/handle")
async def handle_coding_suggestion(payload: HandleSuggestionRequest) -> Dict[str, Any]:
    store = _drg_router().get_demo_drg_store()
    try:
        return case_service.handle_suggestion(store, suggestion_id=payload.suggestion_id, action=payload.action)
    except case_service.DRGCaseNotFoundError:
        raise HTTPException(status_code=404, detail="建议未找到或更新失败")


@router.get("/alerts")
async def get_drg_alerts(
    admission_id: Optional[str] = Query(None),
    alert_level: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
) -> Dict[str, Any]:
    store = _drg_router().get_demo_drg_store()
    return case_service.list_alerts(store, admission_id=admission_id, alert_level=alert_level, status=status, limit=limit)


@router.post("/alerts/handle")
async def handle_drg_alert(payload: HandleAlertRequest) -> Dict[str, Any]:
    store = _drg_router().get_demo_drg_store()
    try:
        return case_service.handle_alert(store, alert_id=payload.alert_id, action=payload.action)
    except case_service.DRGCaseNotFoundError:
        raise HTTPException(status_code=404, detail="预警未找到或更新失败")


@router.get("/demo/story-cases")
async def get_demo_story_cases() -> Dict[str, Any]:
    store = _drg_router().get_demo_drg_store()
    return case_service.get_demo_story_cases(store)


@router.post("/batch-upload")
async def batch_upload_drg(
    request: Request,
    file: UploadFile = File(...),
    current_user: dict = Depends(get_current_user),
) -> Dict[str, Any]:
    drg_router = _drg_router()
    drg_router.enforce_rate_limit(request, bucket="drg_batch_upload", max_requests=10, window_seconds=60)

    contents = await file.read()
    drg_router.validate_uploaded_file(
        request=request,
        file=file,
        content=contents,
        allowed_extensions={".csv", ".xlsx", ".xls"},
        allowed_content_types={
            "text/csv",
            "application/csv",
            "text/plain",
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            "application/vnd.ms-excel",
        },
        max_bytes=50 * 1024 * 1024,
    )

    try:
        task = batch_task_service.submit_batch_upload_task(
            contents=contents,
            filename=file.filename or "upload.xlsx",
            grouping_service=drg_router.get_drg_grouping_service(),
            batch_store=drg_batch_store,
            current_user=current_user,
        )
        return {
            "success": True,
            "task_id": task["task_id"],
            "status": task["status"],
            "stage": task["stage"],
            "progress": task["progress"],
            "session_id": task.get("session_id"),
            "batch_id": task.get("batch_id"),
            "total_records": task.get("total_records") or 0,
            "success_count": task.get("success_count", 0),
            "failed_count": task.get("failed_count", 0),
            "results": [],
            "message": "批量任务已受理，正在后台处理",
        }
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"批量处理失败: {str(exc)}")


@router.get("/batch-tasks")
async def list_batch_tasks(
    current_user: dict = Depends(get_current_user),
    status: Optional[str] = Query(None, description="任务状态筛选"),
    sort_by: str = Query("created_at", description="排序字段: created_at / updated_at"),
    order: str = Query("desc", description="排序方向: asc / desc"),
    limit: int = Query(100, ge=1, le=500),
) -> Dict[str, Any]:
    tasks = batch_task_service.list_batch_tasks(
        current_user=current_user,
        status_filter=status,
        sort_by=sort_by,
        order=order,
        limit=limit,
    )
    return {"success": True, "data": tasks}


@router.get("/batch-tasks/{task_id}")
async def get_batch_task_detail(task_id: str, current_user: dict = Depends(get_current_user)) -> Dict[str, Any]:
    task = batch_task_service.get_batch_task_detail(task_id)
    owner_id = str(current_user.get("id") or current_user.get("user_id") or current_user.get("email") or "unknown")
    if task.get("owner_id") != owner_id:
        raise HTTPException(status_code=404, detail=f"任务不存在: {task_id}")
    return {"success": True, "data": task}


@router.get("/batch-tasks/{task_id}/result")
async def get_batch_task_result(task_id: str, current_user: dict = Depends(get_current_user)) -> Dict[str, Any]:
    task = batch_task_service.get_batch_task_detail(task_id)
    owner_id = str(current_user.get("id") or current_user.get("user_id") or current_user.get("email") or "unknown")
    if task.get("owner_id") != owner_id:
        raise HTTPException(status_code=404, detail=f"任务不存在: {task_id}")
    return batch_task_service.get_batch_task_result(task_id)


@router.get("/statistics")
async def get_drg_statistics(
    session_id: str = Query(..., description="Session ID"),
    batch_id: Optional[str] = Query(None, description="批次ID"),
    start_date: Optional[str] = Query(None, description="开始日期"),
    end_date: Optional[str] = Query(None, description="结束日期"),
    department: Optional[str] = Query(None, description="科室代码"),
    doctor: Optional[str] = Query(None, description="医生姓名"),
) -> Dict[str, Any]:
    return batch_service.get_statistics(
        session_id=session_id,
        batch_id=batch_id,
        start_date=start_date,
        end_date=end_date,
        department=department,
        doctor=doctor,
        batch_store=drg_batch_store,
    )


@router.get("/drill-down")
async def drg_drill_down(
    session_id: str = Query(..., description="Session ID"),
    dimension: str = Query(..., description="钻取维度: department/doctor/drg/mdc"),
    value: str = Query(..., description="维度值"),
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    batch_id: Optional[str] = Query(None),
) -> Dict[str, Any]:
    return batch_service.get_drill_down(
        session_id=session_id,
        dimension=dimension,
        value=value,
        page=page,
        per_page=per_page,
        batch_id=batch_id,
        batch_store=drg_batch_store,
    )


@router.get("/batches")
async def list_batches(session_id: str = Query(..., description="Session ID")) -> Dict[str, Any]:
    return batch_service.list_batches(session_id=session_id, batch_store=drg_batch_store)


@router.delete("/session/{session_id}")
async def delete_session(session_id: str) -> Dict[str, Any]:
    return batch_service.delete_session(session_id=session_id, batch_store=drg_batch_store)


@router.post("/cleanup-sessions")
async def cleanup_expired_sessions() -> Dict[str, Any]:
    return batch_service.cleanup_expired_sessions(batch_store=drg_batch_store)


@router.get("/sessions")
async def list_active_sessions() -> Dict[str, Any]:
    return batch_service.list_active_sessions(batch_store=drg_batch_store)


@router.get("/template")
async def download_template() -> StreamingResponse:
    return batch_service.build_template_response()


@router.get("/export/excel")
async def export_excel_report(
    session_id: str = Query(..., description="Session ID"),
    batch_id: Optional[str] = Query(None),
    days: int = Query(30),
) -> StreamingResponse:
    return batch_service.export_excel_report(session_id=session_id, batch_id=batch_id, days=days, batch_store=drg_batch_store)


@router.post("/notify")
async def trigger_notification(
    batch_id: str = Query(...),
    notification_type: str = Query("batch_complete"),
) -> Dict[str, Any]:
    return batch_service.trigger_notification(batch_id=batch_id, notification_type=notification_type, batch_store=drg_batch_store)


@router.get("/export/pdf")
async def export_pdf_report(
    session_id: str = Query(..., description="Session ID"),
    batch_id: Optional[str] = Query(None),
    days: int = Query(30),
) -> StreamingResponse:
    return batch_service.export_pdf_report(session_id=session_id, batch_id=batch_id, days=days, batch_store=drg_batch_store)


@router.get("/export/word")
async def export_word_report(
    session_id: str = Query(..., description="Session ID"),
    batch_id: Optional[str] = Query(None),
    days: int = Query(30),
) -> StreamingResponse:
    return batch_service.export_word_report(session_id=session_id, batch_id=batch_id, days=days, batch_store=drg_batch_store)
