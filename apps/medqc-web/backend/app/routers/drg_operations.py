from __future__ import annotations

import logging
import os
import re
import threading
from typing import Any, Dict, List, Optional, Tuple

from fastapi import APIRouter, Depends, File, HTTPException, Query, Request, UploadFile
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from ..core.security import require_roles
from ..services import async_job_store, drg_batch_store
from ..services.drg import batch_service, batch_task_service, case_service
from ..services.medical_records.detail_service import inspect_institute_scope

logger = logging.getLogger(__name__)
router = APIRouter()

_DRG_OPS_ROLES = ("admin", "qc_manager", "sync_admin", "super_admin")
_DRG_ADMIN_ROLES = ("admin", "sync_admin", "super_admin")

DRG_BATCH_MAX_BYTES = 50 * 1024 * 1024  # 50 MB
_STREAM_CHUNK_SIZE = 1024 * 1024  # 1 MB
_SAFE_ID_PATTERN = re.compile(r"^[A-Za-z0-9_-]{1,80}\Z")

_owner_lock = threading.RLock()
_task_owners: Dict[str, Tuple[str, str]] = {}
_session_owners: Dict[str, Tuple[str, str]] = {}
_batch_owners: Dict[str, Tuple[str, str]] = {}


def _drg_router():
    from . import drg as drg_router

    return drg_router


def _actor_id(current_user: Dict[str, Any]) -> str:
    return str(
        current_user.get("id")
        or current_user.get("user_id")
        or current_user.get("email")
        or ""
    ).strip()


def _resolve_scope(current_user: Dict[str, Any]) -> tuple[bool, Optional[str]]:
    scope = inspect_institute_scope(current_user)
    if scope.kind == "global":
        return True, None
    if scope.kind == "institute" and scope.institute_id:
        return False, scope.institute_id
    raise HTTPException(status_code=403, detail="账号缺少可信机构范围")


def _validate_safe_identifier(value: str, label: str) -> str:
    if not isinstance(value, str) or not _SAFE_ID_PATTERN.fullmatch(value):
        raise HTTPException(status_code=400, detail=f"无效的 {label}")
    return value


def _sanitize_upload_filename(filename: Optional[str], default: str = "upload.xlsx") -> str:
    raw = str(filename or "").replace("\\", "/")
    base = os.path.basename(raw)
    cleaned = re.sub(r"[\x00-\x1f\x7f]", "", base).strip()
    if not cleaned or cleaned in {".", ".."} or "/" in cleaned or "\\" in cleaned:
        return default
    return cleaned


def _human_readable_size(size_bytes: int) -> str:
    if size_bytes >= 1024 * 1024:
        return f"{size_bytes / 1024 / 1024:.1f}MB"
    if size_bytes >= 1024:
        return f"{size_bytes / 1024:.1f}KB"
    return f"{size_bytes}B"


async def _read_upload_limited(file: UploadFile, max_bytes: int) -> bytes:
    """流式分块读取上传内容，超限立即 413 截断。"""
    limit = max(1, int(max_bytes))
    chunk_size = min(_STREAM_CHUNK_SIZE, limit + 1)
    chunks: list[bytes] = []
    total = 0
    while True:
        chunk = await file.read(chunk_size)
        if not chunk:
            break
        total += len(chunk)
        if total > limit:
            raise HTTPException(
                status_code=413,
                detail=f"文件大小不能超过 {_human_readable_size(limit)}",
            )
        chunks.append(chunk)
    return b"".join(chunks)


def _lookup_owner_institute(owner_id: str) -> str:
    if not owner_id:
        return ""
    try:
        scope = inspect_institute_scope({"id": owner_id, "roles": []})
        if scope.kind == "institute" and scope.institute_id:
            return scope.institute_id
    except Exception:
        pass
    return ""


def _record_task_ownership(
    task_id: str,
    *,
    owner_id: str,
    institute_id: str,
    session_id: Optional[str] = None,
    batch_id: Optional[str] = None,
) -> None:
    with _owner_lock:
        if task_id:
            _task_owners[task_id] = (owner_id, institute_id)
        if session_id:
            _session_owners[session_id] = (owner_id, institute_id)
        if batch_id:
            _batch_owners[batch_id] = (owner_id, institute_id)


def _sync_owners_from_tasks() -> None:
    try:
        manager = batch_task_service.get_batch_task_manager()
        with manager._lock:
            records = list(manager._tasks.values())
    except Exception:
        records = []

    with _owner_lock:
        for rec in records:
            known_owner, known_inst = _task_owners.get(rec.task_id, (rec.owner_id, ""))
            owner = rec.owner_id or known_owner
            inst = known_inst or _lookup_owner_institute(owner)
            if rec.task_id and owner:
                _task_owners[rec.task_id] = (owner, inst)
            if rec.session_id and owner:
                _session_owners[rec.session_id] = (owner, inst)
            if rec.batch_id and owner:
                _batch_owners[rec.batch_id] = (owner, inst)


def _resolve_owner_from_store(*, session_id: Optional[str] = None, batch_id: Optional[str] = None) -> Optional[Tuple[str, str]]:
    _sync_owners_from_tasks()
    with _owner_lock:
        if session_id and session_id in _session_owners:
            return _session_owners[session_id]
        if batch_id and batch_id in _batch_owners:
            return _batch_owners[batch_id]

    try:
        rows = async_job_store.list_jobs(
            job_type=batch_task_service.DRG_BATCH_JOB_TYPE,
            limit=500,
        ).get("items", [])
    except Exception:
        rows = []

    for row in rows:
        payload = row.get("payload") or {}
        row_session = str(payload.get("session_id") or "").strip()
        row_batch = str(payload.get("batch_id") or "").strip()
        owner_id = str(row.get("requested_by") or payload.get("owner_id") or "").strip()
        if not owner_id:
            continue
        inst = str(payload.get("institute_id") or "").strip() or _lookup_owner_institute(owner_id)
        if session_id and row_session == session_id:
            _record_task_ownership(
                str(row.get("id") or ""),
                owner_id=owner_id,
                institute_id=inst,
                session_id=row_session,
                batch_id=row_batch or None,
            )
            return (owner_id, inst)
        if batch_id and row_batch == batch_id:
            _record_task_ownership(
                str(row.get("id") or ""),
                owner_id=owner_id,
                institute_id=inst,
                session_id=row_session or None,
                batch_id=row_batch,
            )
            return (owner_id, inst)
    return None


def _assert_session_access(
    current_user: Dict[str, Any],
    *,
    session_id: Optional[str] = None,
    batch_id: Optional[str] = None,
) -> None:
    if session_id is not None:
        _validate_safe_identifier(session_id, "session_id")
    if batch_id is not None:
        _validate_safe_identifier(batch_id, "batch_id")

    is_global, actor_institute = _resolve_scope(current_user)
    if is_global:
        return

    actor = _actor_id(current_user)
    if not actor:
        raise HTTPException(status_code=403, detail="缺少可信账号身份")

    owner_info = _resolve_owner_from_store(session_id=session_id, batch_id=batch_id)
    if owner_info is None:
        raise HTTPException(status_code=403, detail="无权访问该 DRG 会话或批次")

    owner_id, owner_institute = owner_info
    if owner_id != actor:
        raise HTTPException(status_code=403, detail="无权访问他人的 DRG 会话或批次")
    if not owner_institute or owner_institute != actor_institute:
        raise HTTPException(status_code=403, detail="无权访问其他机构的 DRG 会话或批次")


def _assert_task_access(current_user: Dict[str, Any], task: Dict[str, Any]) -> None:
    is_global, actor_institute = _resolve_scope(current_user)
    if is_global:
        return

    actor = _actor_id(current_user)
    task_id = str(task.get("task_id") or "")
    task_owner = str(task.get("owner_id") or "").strip()
    if not actor or task_owner != actor:
        raise HTTPException(status_code=403, detail="无权访问他人的 DRG 批任务")

    with _owner_lock:
        _known_owner, known_inst = _task_owners.get(task_id, (task_owner, ""))
    owner_inst = known_inst or _lookup_owner_institute(task_owner)
    if owner_inst and owner_inst != actor_institute:
        raise HTTPException(status_code=403, detail="无权访问其他机构的 DRG 批任务")

    if task.get("session_id") or task.get("batch_id"):
        _record_task_ownership(
            task_id,
            owner_id=task_owner,
            institute_id=owner_inst or (actor_institute or ""),
            session_id=task.get("session_id"),
            batch_id=task.get("batch_id"),
        )


def _raise_sanitized_http_error(exc: Exception, *, fallback_detail: str) -> None:
    if isinstance(exc, HTTPException):
        if exc.status_code >= 500:
            logger.error("DRG operation error (%s): %s", exc.status_code, exc.detail)
            raise HTTPException(status_code=exc.status_code, detail=fallback_detail) from None
        raise exc
    logger.exception("DRG operation unexpected failure")
    raise HTTPException(status_code=500, detail=fallback_detail) from None


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
async def predict_drg_realtime(
    payload: RealtimeDRGRequest,
    current_user: dict = Depends(require_roles(*_DRG_OPS_ROLES)),
) -> Dict[str, Any]:
    _resolve_scope(current_user)
    service = _drg_router().get_drg_grouping_service()
    try:
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
    except Exception as exc:
        _raise_sanitized_http_error(exc, fallback_detail="DRG 实时分组失败")


@router.post("/predict")
async def predict_drg_grouping(
    payload: DRGPredictRequest,
    current_user: dict = Depends(require_roles(*_DRG_OPS_ROLES)),
) -> Dict[str, Any]:
    _resolve_scope(current_user)
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
        raise HTTPException(status_code=404, detail="未找到指定住院号的病案首页")
    except Exception as exc:
        _raise_sanitized_http_error(exc, fallback_detail="DRG 分组预测失败")


@router.get("/grouping/{admission_id}/history")
async def get_grouping_history(
    admission_id: str,
    current_user: dict = Depends(require_roles(*_DRG_OPS_ROLES)),
) -> Dict[str, Any]:
    _resolve_scope(current_user)
    store = _drg_router().get_demo_drg_store()
    try:
        return case_service.get_grouping_history(store, admission_id=admission_id)
    except Exception as exc:
        _raise_sanitized_http_error(exc, fallback_detail="查询 DRG 分组历史失败")


@router.get("/suggestions")
async def list_coding_suggestions(
    admission_id: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    current_user: dict = Depends(require_roles(*_DRG_OPS_ROLES)),
) -> Dict[str, Any]:
    _resolve_scope(current_user)
    store = _drg_router().get_demo_drg_store()
    try:
        return case_service.list_suggestions(store, admission_id=admission_id, status=status, limit=limit)
    except Exception as exc:
        _raise_sanitized_http_error(exc, fallback_detail="查询编码建议失败")


@router.post("/suggestions/handle")
async def handle_coding_suggestion(
    payload: HandleSuggestionRequest,
    current_user: dict = Depends(require_roles(*_DRG_OPS_ROLES)),
) -> Dict[str, Any]:
    _resolve_scope(current_user)
    store = _drg_router().get_demo_drg_store()
    try:
        return case_service.handle_suggestion(store, suggestion_id=payload.suggestion_id, action=payload.action)
    except case_service.DRGCaseNotFoundError:
        raise HTTPException(status_code=404, detail="建议未找到或更新失败")
    except Exception as exc:
        _raise_sanitized_http_error(exc, fallback_detail="处理编码建议失败")


@router.get("/alerts")
async def get_drg_alerts(
    admission_id: Optional[str] = Query(None),
    alert_level: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    current_user: dict = Depends(require_roles(*_DRG_OPS_ROLES)),
) -> Dict[str, Any]:
    _resolve_scope(current_user)
    store = _drg_router().get_demo_drg_store()
    try:
        return case_service.list_alerts(store, admission_id=admission_id, alert_level=alert_level, status=status, limit=limit)
    except Exception as exc:
        _raise_sanitized_http_error(exc, fallback_detail="查询 DRG 预警失败")


@router.post("/alerts/handle")
async def handle_drg_alert(
    payload: HandleAlertRequest,
    current_user: dict = Depends(require_roles(*_DRG_OPS_ROLES)),
) -> Dict[str, Any]:
    _resolve_scope(current_user)
    store = _drg_router().get_demo_drg_store()
    try:
        return case_service.handle_alert(store, alert_id=payload.alert_id, action=payload.action)
    except case_service.DRGCaseNotFoundError:
        raise HTTPException(status_code=404, detail="预警未找到或更新失败")
    except Exception as exc:
        _raise_sanitized_http_error(exc, fallback_detail="处理 DRG 预警失败")


@router.get("/demo/story-cases")
async def get_demo_story_cases(
    current_user: dict = Depends(require_roles(*_DRG_OPS_ROLES)),
) -> Dict[str, Any]:
    _resolve_scope(current_user)
    store = _drg_router().get_demo_drg_store()
    try:
        return case_service.get_demo_story_cases(store)
    except Exception as exc:
        _raise_sanitized_http_error(exc, fallback_detail="获取示例病例失败")


@router.post("/batch-upload")
async def batch_upload_drg(
    request: Request,
    file: UploadFile = File(...),
    current_user: dict = Depends(require_roles(*_DRG_OPS_ROLES)),
) -> Dict[str, Any]:
    _is_global, actor_institute = _resolve_scope(current_user)
    drg_router = _drg_router()
    drg_router.enforce_rate_limit(request, bucket="drg_batch_upload", max_requests=10, window_seconds=60)

    safe_filename = _sanitize_upload_filename(file.filename, default="upload.xlsx")
    contents = await _read_upload_limited(file, max_bytes=DRG_BATCH_MAX_BYTES)
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
        max_bytes=DRG_BATCH_MAX_BYTES,
    )

    try:
        task = batch_task_service.submit_batch_upload_task(
            contents=contents,
            filename=safe_filename,
            grouping_service=drg_router.get_drg_grouping_service(),
            batch_store=drg_batch_store,
            current_user=current_user,
        )
        _record_task_ownership(
            str(task.get("task_id") or ""),
            owner_id=_actor_id(current_user),
            institute_id=actor_institute or "",
            session_id=task.get("session_id"),
            batch_id=task.get("batch_id"),
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
    except Exception as exc:
        _raise_sanitized_http_error(exc, fallback_detail="批量处理失败，请稍后重试")


@router.get("/batch-tasks")
async def list_batch_tasks(
    current_user: dict = Depends(require_roles(*_DRG_OPS_ROLES)),
    status: Optional[str] = Query(None, description="任务状态筛选"),
    sort_by: str = Query("created_at", description="排序字段: created_at / updated_at"),
    order: str = Query("desc", description="排序方向: asc / desc"),
    limit: int = Query(100, ge=1, le=500),
) -> Dict[str, Any]:
    _resolve_scope(current_user)
    try:
        tasks = batch_task_service.list_batch_tasks(
            current_user=current_user,
            status_filter=status,
            sort_by=sort_by,
            order=order,
            limit=limit,
        )
        return {"success": True, "data": tasks}
    except Exception as exc:
        _raise_sanitized_http_error(exc, fallback_detail="查询批量任务列表失败")


@router.get("/batch-tasks/{task_id}")
async def get_batch_task_detail(
    task_id: str,
    current_user: dict = Depends(require_roles(*_DRG_OPS_ROLES)),
) -> Dict[str, Any]:
    try:
        task = batch_task_service.get_batch_task_detail(task_id)
        _assert_task_access(current_user, task)
        return {"success": True, "data": task}
    except Exception as exc:
        _raise_sanitized_http_error(exc, fallback_detail="查询批量任务详情失败")


@router.get("/batch-tasks/{task_id}/result")
async def get_batch_task_result(
    task_id: str,
    current_user: dict = Depends(require_roles(*_DRG_OPS_ROLES)),
) -> Dict[str, Any]:
    try:
        task = batch_task_service.get_batch_task_detail(task_id)
        _assert_task_access(current_user, task)
        return batch_task_service.get_batch_task_result(task_id)
    except Exception as exc:
        _raise_sanitized_http_error(exc, fallback_detail="查询批量任务结果失败")


@router.get("/statistics")
async def get_drg_statistics(
    session_id: str = Query(..., description="Session ID"),
    batch_id: Optional[str] = Query(None, description="批次ID"),
    start_date: Optional[str] = Query(None, description="开始日期"),
    end_date: Optional[str] = Query(None, description="结束日期"),
    department: Optional[str] = Query(None, description="科室代码"),
    doctor: Optional[str] = Query(None, description="医生姓名"),
    current_user: dict = Depends(require_roles(*_DRG_OPS_ROLES)),
) -> Dict[str, Any]:
    _assert_session_access(current_user, session_id=session_id, batch_id=batch_id)
    try:
        return batch_service.get_statistics(
            session_id=session_id,
            batch_id=batch_id,
            start_date=start_date,
            end_date=end_date,
            department=department,
            doctor=doctor,
            batch_store=drg_batch_store,
        )
    except Exception as exc:
        _raise_sanitized_http_error(exc, fallback_detail="获取 DRG 统计数据失败")


@router.get("/drill-down")
async def drg_drill_down(
    session_id: str = Query(..., description="Session ID"),
    dimension: str = Query(..., description="钻取维度: department/doctor/drg/mdc"),
    value: str = Query(..., description="维度值"),
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    batch_id: Optional[str] = Query(None),
    current_user: dict = Depends(require_roles(*_DRG_OPS_ROLES)),
) -> Dict[str, Any]:
    _assert_session_access(current_user, session_id=session_id, batch_id=batch_id)
    try:
        return batch_service.get_drill_down(
            session_id=session_id,
            dimension=dimension,
            value=value,
            page=page,
            per_page=per_page,
            batch_id=batch_id,
            batch_store=drg_batch_store,
        )
    except Exception as exc:
        _raise_sanitized_http_error(exc, fallback_detail="查询 DRG 钻取明细失败")


@router.get("/batches")
async def list_batches(
    session_id: str = Query(..., description="Session ID"),
    current_user: dict = Depends(require_roles(*_DRG_OPS_ROLES)),
) -> Dict[str, Any]:
    _assert_session_access(current_user, session_id=session_id)
    try:
        return batch_service.list_batches(session_id=session_id, batch_store=drg_batch_store)
    except Exception as exc:
        _raise_sanitized_http_error(exc, fallback_detail="查询 DRG 批次列表失败")


@router.delete("/session/{session_id}")
async def delete_session(
    session_id: str,
    current_user: dict = Depends(require_roles(*_DRG_OPS_ROLES)),
) -> Dict[str, Any]:
    _assert_session_access(current_user, session_id=session_id)
    try:
        result = batch_service.delete_session(session_id=session_id, batch_store=drg_batch_store)
        with _owner_lock:
            _session_owners.pop(session_id, None)
        return result
    except Exception as exc:
        _raise_sanitized_http_error(exc, fallback_detail="删除 DRG 会话失败")


@router.post("/cleanup-sessions")
async def cleanup_expired_sessions(
    current_user: dict = Depends(require_roles(*_DRG_ADMIN_ROLES)),
) -> Dict[str, Any]:
    is_global, _actor_institute = _resolve_scope(current_user)
    if not is_global:
        raise HTTPException(status_code=403, detail="仅全局管理员可执行全局会话清理")
    try:
        return batch_service.cleanup_expired_sessions(batch_store=drg_batch_store)
    except Exception as exc:
        _raise_sanitized_http_error(exc, fallback_detail="清理过期会话失败")


@router.get("/sessions")
async def list_active_sessions(
    current_user: dict = Depends(require_roles(*_DRG_OPS_ROLES)),
) -> Dict[str, Any]:
    is_global, actor_institute = _resolve_scope(current_user)
    try:
        result = batch_service.list_active_sessions(batch_store=drg_batch_store)
        if is_global:
            return result
        actor = _actor_id(current_user)
        _sync_owners_from_tasks()
        filtered = []
        for item in result.get("data") or []:
            sid = str(item.get("session_id") or "")
            owner_info = _resolve_owner_from_store(session_id=sid)
            if owner_info and owner_info[0] == actor and owner_info[1] == actor_institute:
                filtered.append(item)
        return {"success": True, "data": filtered}
    except Exception as exc:
        _raise_sanitized_http_error(exc, fallback_detail="查询活跃会话列表失败")


@router.get("/template")
async def download_template(
    current_user: dict = Depends(require_roles(*_DRG_OPS_ROLES)),
) -> StreamingResponse:
    _resolve_scope(current_user)
    try:
        return batch_service.build_template_response()
    except Exception as exc:
        _raise_sanitized_http_error(exc, fallback_detail="生成 DRG 模板失败")


@router.get("/export/excel")
async def export_excel_report(
    session_id: str = Query(..., description="Session ID"),
    batch_id: Optional[str] = Query(None),
    days: int = Query(30),
    current_user: dict = Depends(require_roles(*_DRG_OPS_ROLES)),
) -> StreamingResponse:
    _assert_session_access(current_user, session_id=session_id, batch_id=batch_id)
    try:
        return batch_service.export_excel_report(
            session_id=session_id,
            batch_id=batch_id,
            days=days,
            batch_store=drg_batch_store,
        )
    except Exception as exc:
        _raise_sanitized_http_error(exc, fallback_detail="导出 Excel 报告失败")


@router.post("/notify")
async def trigger_notification(
    batch_id: str = Query(...),
    notification_type: str = Query("batch_complete"),
    current_user: dict = Depends(require_roles(*_DRG_OPS_ROLES)),
) -> Dict[str, Any]:
    _assert_session_access(current_user, batch_id=batch_id)
    try:
        return batch_service.trigger_notification(
            batch_id=batch_id,
            notification_type=notification_type,
            batch_store=drg_batch_store,
        )
    except Exception as exc:
        _raise_sanitized_http_error(exc, fallback_detail="触发批次通知失败")


@router.get("/export/pdf")
async def export_pdf_report(
    session_id: str = Query(..., description="Session ID"),
    batch_id: Optional[str] = Query(None),
    days: int = Query(30),
    current_user: dict = Depends(require_roles(*_DRG_OPS_ROLES)),
) -> StreamingResponse:
    _assert_session_access(current_user, session_id=session_id, batch_id=batch_id)
    try:
        return batch_service.export_pdf_report(
            session_id=session_id,
            batch_id=batch_id,
            days=days,
            batch_store=drg_batch_store,
        )
    except Exception as exc:
        _raise_sanitized_http_error(exc, fallback_detail="导出 PDF 报告失败")


@router.get("/export/word")
async def export_word_report(
    session_id: str = Query(..., description="Session ID"),
    batch_id: Optional[str] = Query(None),
    days: int = Query(30),
    current_user: dict = Depends(require_roles(*_DRG_OPS_ROLES)),
) -> StreamingResponse:
    _assert_session_access(current_user, session_id=session_id, batch_id=batch_id)
    try:
        return batch_service.export_word_report(
            session_id=session_id,
            batch_id=batch_id,
            days=days,
            batch_store=drg_batch_store,
        )
    except Exception as exc:
        _raise_sanitized_http_error(exc, fallback_detail="导出 Word 报告失败")
