"""定时质控任务计划的独立管理接口。"""

from __future__ import annotations

import logging
from typing import Literal, NoReturn

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, status
from starlette.concurrency import run_in_threadpool

from ..core.audit import audit_event
from ..core.permissions import (
    PermissionAction,
    ResourceType,
    UserRole,
    has_any_role,
    require_permission,
)
from ..core.response import get_trace_id, success_response
from ..core.security import get_current_user
from ..schemas.task_schedules import (
    TaskScheduleActionRequest,
    TaskScheduleCreateRequest,
    TaskScheduleListResponse,
    TaskScheduleResponse,
    TaskScheduleRunListResponse,
    TaskScheduleRunResponse,
)
from ..services import task_schedule_job_service, task_schedule_service


router = APIRouter(prefix="/api/v1/task-schedules", tags=["task-schedules"])
logger = logging.getLogger(__name__)

_MANAGER_ROLES = [UserRole.ADMIN, UserRole.QC_MANAGER]
_SCHEDULE_ERROR_MESSAGES = {
    "schedule_not_found": "定时计划不存在",
    "schedule_forbidden": "无权访问该定时计划",
    "schedule_invalid": "定时计划请求无效",
    "version_conflict": "定时计划版本已变化，请刷新后重试",
    "state_conflict": "定时计划当前状态不允许此操作",
    "request_conflict": "请求编号已用于其他定时计划",
    "schedule_unavailable": "定时计划暂不可用，请稍后重试",
}
_JOB_ERROR_MESSAGES = {
    "task_schedule_not_found": "定时计划或运行记录不存在",
    "task_schedule_forbidden": "无权操作该定时计划",
    "task_schedule_invalid": "定时计划执行请求无效",
    "version_conflict": "定时计划版本已变化，请刷新后重试",
    "state_conflict": "定时计划当前状态不允许执行",
    "run_conflict": "该计划运行当前状态不允许重试",
    "task_schedule_unavailable": "定时计划执行暂不可用，请稍后重试",
}


def _request_context(current_user: dict) -> tuple[str, bool]:
    actor_id = current_user.get("id") or current_user.get("user_id")
    if not isinstance(actor_id, str) or not actor_id.strip():
        raise HTTPException(
            status_code=401,
            detail={"code": "schedule_forbidden", "message": "当前用户缺少有效身份"},
        )
    is_manager = has_any_role(current_user, _MANAGER_ROLES)
    if not is_manager:
        raise HTTPException(
            status_code=403,
            detail={"code": "schedule_forbidden", "message": "仅管理员和质控主管可管理定时计划"},
        )
    return actor_id.strip(), is_manager


def _reject_unexpected_query(request: Request, allowed: set[str]) -> None:
    if set(request.query_params).difference(allowed):
        raise HTTPException(
            status_code=422,
            detail={"code": "schedule_invalid", "message": "包含不支持的查询参数"},
        )


def _raise_service_error(exc: Exception, *, job: bool = False) -> NoReturn:
    service = task_schedule_job_service if job else task_schedule_service
    if isinstance(exc, service.TaskScheduleNotFound if not job else service.TaskScheduleJobNotFound):
        status_code = 404
    elif isinstance(exc, service.TaskScheduleForbidden if not job else service.TaskScheduleJobForbidden):
        status_code = 403
    elif isinstance(exc, service.TaskScheduleInvalid if not job else service.TaskScheduleJobInvalid):
        status_code = 422
    elif isinstance(exc, service.TaskScheduleConflict if not job else service.TaskScheduleJobConflict):
        status_code = 409
    else:
        status_code = 503
    fallback_code = "task_schedule_unavailable" if job else "schedule_unavailable"
    code = getattr(exc, "code", fallback_code)
    messages = _JOB_ERROR_MESSAGES if job else _SCHEDULE_ERROR_MESSAGES
    invalid_type = service.TaskScheduleJobInvalid if job else service.TaskScheduleInvalid
    conflict_type = service.TaskScheduleJobConflict if job else service.TaskScheduleConflict
    if code == "request_conflict":
        message = _SCHEDULE_ERROR_MESSAGES[code]
    elif isinstance(exc, (invalid_type, conflict_type)):
        message = str(exc)
    else:
        message = messages.get(code, messages[fallback_code])
    raise HTTPException(status_code=status_code, detail={"code": code, "message": message}) from exc


def _raise_unavailable(exc: Exception, *, event: str, job: bool = False) -> NoReturn:
    code = "task_schedule_unavailable" if job else "schedule_unavailable"
    messages = _JOB_ERROR_MESSAGES if job else _SCHEDULE_ERROR_MESSAGES
    logger.error("%s error_type=%s", event, type(exc).__name__)
    raise HTTPException(status_code=503, detail={"code": code, "message": messages[code]}) from None


def _schedule_data(result: dict) -> dict:
    try:
        return TaskScheduleResponse.model_validate(result).model_dump(mode="json")
    except Exception as exc:
        raise task_schedule_service.TaskScheduleUnavailable("计划响应无法确认") from exc


def _schedule_list_data(result: dict) -> dict:
    try:
        return TaskScheduleListResponse.model_validate(result).model_dump(mode="json")
    except Exception as exc:
        raise task_schedule_service.TaskScheduleUnavailable("计划列表响应无法确认") from exc


def _run_data(result: dict) -> dict:
    try:
        return TaskScheduleRunResponse.model_validate(result).model_dump(mode="json")
    except Exception as exc:
        raise task_schedule_job_service.TaskScheduleJobUnavailable("运行响应无法确认") from exc


def _run_list_data(result: dict) -> dict:
    try:
        return TaskScheduleRunListResponse.model_validate(result).model_dump(mode="json")
    except Exception as exc:
        raise task_schedule_service.TaskScheduleUnavailable("运行列表响应无法确认") from exc


def _validate_idempotency_key(value: str, *, code: str = "task_schedule_invalid") -> str:
    if not 1 <= len(value) <= 128 or any(not 0x21 <= ord(char) <= 0x7E for char in value):
        raise HTTPException(
            status_code=422,
            detail={"code": code, "message": "Idempotency-Key 必须为 1 至 128 个可见 ASCII 字符"},
        )
    return value


@router.post("", status_code=status.HTTP_201_CREATED)
@require_permission(ResourceType.QC_TASKS, PermissionAction.CREATE)
async def create_task_schedule(
    request: Request,
    payload: TaskScheduleCreateRequest,
    idempotency_key: str = Header(..., alias="Idempotency-Key"),
    current_user: dict = Depends(get_current_user),
):
    _reject_unexpected_query(request, set())
    actor_id, is_manager = _request_context(current_user)
    request_id = _validate_idempotency_key(idempotency_key, code="schedule_invalid")
    try:
        result = await run_in_threadpool(
            task_schedule_service.create_task_schedule,
            actor_id=actor_id,
            is_manager=is_manager,
            request_id=request_id,
            source_task_id=payload.source_task_id,
            source_configuration_version=payload.source_configuration_version,
            timing_config=payload.timing_config.model_dump(mode="json"),
        )
        data = _schedule_data(result)
    except task_schedule_service.TaskScheduleError as exc:
        if isinstance(exc, task_schedule_service.TaskScheduleUnavailable):
            logger.warning("task_schedule_create_failed error_type=%s", type(exc).__name__)
        _raise_service_error(exc)
    except Exception as exc:
        _raise_unavailable(exc, event="task_schedule_create_failed")
    audit_event(
        request,
        action="task_schedules.create",
        resource="/api/v1/task-schedules",
        outcome="success",
        current_user=current_user,
        details={"schedule_id": data["id"], "source_task_id": data["source_task_id"], "version": data["version"]},
    )
    return success_response(data=data, message="定时计划已创建", trace_id=get_trace_id(request))


@router.get("")
@require_permission(ResourceType.QC_TASKS, PermissionAction.READ)
async def list_task_schedules(
    request: Request,
    state: Literal["active", "paused", "ended", "cancelled"] | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: dict = Depends(get_current_user),
):
    _reject_unexpected_query(request, {"state", "page", "page_size"})
    actor_id, is_manager = _request_context(current_user)
    try:
        result = await run_in_threadpool(
            task_schedule_service.list_task_schedules,
            actor_id=actor_id,
            is_manager=is_manager,
            state=state,
            page=page,
            page_size=page_size,
        )
        data = _schedule_list_data(result)
    except task_schedule_service.TaskScheduleError as exc:
        if isinstance(exc, task_schedule_service.TaskScheduleUnavailable):
            logger.warning("task_schedule_list_failed error_type=%s", type(exc).__name__)
        _raise_service_error(exc)
    except Exception as exc:
        _raise_unavailable(exc, event="task_schedule_list_failed")
    return success_response(data=data, trace_id=get_trace_id(request))


@router.post("/runs/{run_id}/retry")
@require_permission(ResourceType.QC_TASKS, PermissionAction.UPDATE)
async def retry_task_schedule_run(
    request: Request,
    run_id: str,
    current_user: dict = Depends(get_current_user),
):
    _reject_unexpected_query(request, set())
    actor_id, is_manager = _request_context(current_user)
    try:
        result = await run_in_threadpool(
            task_schedule_job_service.retry_schedule_run,
            run_id=run_id,
            actor_id=actor_id,
            is_manager=is_manager,
        )
        data = _run_data(result)
    except task_schedule_job_service.TaskScheduleJobError as exc:
        if isinstance(exc, task_schedule_job_service.TaskScheduleJobUnavailable):
            logger.warning("task_schedule_retry_failed error_type=%s", type(exc).__name__)
        _raise_service_error(exc, job=True)
    except Exception as exc:
        _raise_unavailable(exc, event="task_schedule_retry_failed", job=True)
    audit_event(
        request,
        action="task_schedules.runs.retry",
        resource="/api/v1/task-schedules/runs/{run_id}/retry",
        outcome="success",
        current_user=current_user,
        details={"run_id": data["id"], "schedule_id": data["schedule_id"], "status": data["status"]},
    )
    return success_response(data=data, message="计划运行已重新入队", trace_id=get_trace_id(request))


@router.get("/{schedule_id}")
@require_permission(ResourceType.QC_TASKS, PermissionAction.READ)
async def get_task_schedule(
    request: Request,
    schedule_id: str,
    current_user: dict = Depends(get_current_user),
):
    _reject_unexpected_query(request, set())
    actor_id, is_manager = _request_context(current_user)
    try:
        result = await run_in_threadpool(
            task_schedule_service.get_task_schedule,
            schedule_id,
            actor_id=actor_id,
            is_manager=is_manager,
        )
        data = _schedule_data(result)
    except task_schedule_service.TaskScheduleError as exc:
        if isinstance(exc, task_schedule_service.TaskScheduleUnavailable):
            logger.warning("task_schedule_read_failed error_type=%s", type(exc).__name__)
        _raise_service_error(exc)
    except Exception as exc:
        _raise_unavailable(exc, event="task_schedule_read_failed")
    return success_response(data=data, trace_id=get_trace_id(request))


async def _change_schedule_state(
    *,
    request: Request,
    schedule_id: str,
    payload: TaskScheduleActionRequest,
    current_user: dict,
    action: Literal["pause", "resume", "cancel"],
) -> dict:
    _reject_unexpected_query(request, set())
    actor_id, is_manager = _request_context(current_user)
    operation = getattr(task_schedule_service, f"{action}_task_schedule")
    try:
        result = await run_in_threadpool(
            operation,
            schedule_id,
            actor_id=actor_id,
            is_manager=is_manager,
            expected_version=payload.version,
        )
        data = _schedule_data(result)
    except task_schedule_service.TaskScheduleError as exc:
        if isinstance(exc, task_schedule_service.TaskScheduleUnavailable):
            logger.warning("task_schedule_%s_failed error_type=%s", action, type(exc).__name__)
        _raise_service_error(exc)
    except Exception as exc:
        _raise_unavailable(exc, event=f"task_schedule_{action}_failed")
    audit_event(
        request,
        action=f"task_schedules.{action}",
        resource=f"/api/v1/task-schedules/{{schedule_id}}/{action}",
        outcome="success",
        current_user=current_user,
        details={
            "schedule_id": data["id"],
            "previous_version": payload.version,
            "version": data["version"],
            "state": data["state"],
        },
    )
    return success_response(data=data, message="定时计划状态已更新", trace_id=get_trace_id(request))


@router.patch("/{schedule_id}/pause")
@require_permission(ResourceType.QC_TASKS, PermissionAction.UPDATE)
async def pause_task_schedule(
    request: Request,
    schedule_id: str,
    payload: TaskScheduleActionRequest,
    current_user: dict = Depends(get_current_user),
):
    return await _change_schedule_state(
        request=request, schedule_id=schedule_id, payload=payload, current_user=current_user, action="pause",
    )


@router.patch("/{schedule_id}/resume")
@require_permission(ResourceType.QC_TASKS, PermissionAction.UPDATE)
async def resume_task_schedule(
    request: Request,
    schedule_id: str,
    payload: TaskScheduleActionRequest,
    current_user: dict = Depends(get_current_user),
):
    return await _change_schedule_state(
        request=request, schedule_id=schedule_id, payload=payload, current_user=current_user, action="resume",
    )


@router.patch("/{schedule_id}/cancel")
@require_permission(ResourceType.QC_TASKS, PermissionAction.UPDATE)
async def cancel_task_schedule(
    request: Request,
    schedule_id: str,
    payload: TaskScheduleActionRequest,
    current_user: dict = Depends(get_current_user),
):
    return await _change_schedule_state(
        request=request, schedule_id=schedule_id, payload=payload, current_user=current_user, action="cancel",
    )


@router.post("/{schedule_id}/run-now")
@require_permission(ResourceType.QC_TASKS, PermissionAction.UPDATE)
async def run_task_schedule_now(
    request: Request,
    schedule_id: str,
    idempotency_key: str = Header(..., alias="Idempotency-Key"),
    current_user: dict = Depends(get_current_user),
):
    _reject_unexpected_query(request, set())
    actor_id, is_manager = _request_context(current_user)
    request_id = _validate_idempotency_key(idempotency_key)
    try:
        result = await run_in_threadpool(
            task_schedule_job_service.enqueue_manual_schedule_run,
            schedule_id=schedule_id,
            request_id=request_id,
            actor_id=actor_id,
            is_manager=is_manager,
        )
        data = _run_data(result)
    except task_schedule_job_service.TaskScheduleJobError as exc:
        if isinstance(exc, task_schedule_job_service.TaskScheduleJobUnavailable):
            logger.warning("task_schedule_run_now_failed error_type=%s", type(exc).__name__)
        _raise_service_error(exc, job=True)
    except Exception as exc:
        _raise_unavailable(exc, event="task_schedule_run_now_failed", job=True)
    audit_event(
        request,
        action="task_schedules.run_now",
        resource="/api/v1/task-schedules/{schedule_id}/run-now",
        outcome="success",
        current_user=current_user,
        details={"schedule_id": data["schedule_id"], "run_id": data["id"], "status": data["status"]},
    )
    return success_response(data=data, message="计划运行已入队", trace_id=get_trace_id(request))


@router.get("/{schedule_id}/runs")
@require_permission(ResourceType.QC_TASKS, PermissionAction.READ)
async def list_task_schedule_runs(
    request: Request,
    schedule_id: str,
    status_filter: Literal["queued", "running", "succeeded", "failed", "cancelled"] | None = Query(
        None, alias="status",
    ),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: dict = Depends(get_current_user),
):
    _reject_unexpected_query(request, {"status", "page", "page_size"})
    actor_id, is_manager = _request_context(current_user)
    try:
        result = await run_in_threadpool(
            task_schedule_service.list_task_schedule_runs,
            schedule_id,
            actor_id=actor_id,
            is_manager=is_manager,
            status=status_filter,
            page=page,
            page_size=page_size,
        )
        data = _run_list_data(result)
    except task_schedule_service.TaskScheduleError as exc:
        if isinstance(exc, task_schedule_service.TaskScheduleUnavailable):
            logger.warning("task_schedule_runs_list_failed error_type=%s", type(exc).__name__)
        _raise_service_error(exc)
    except Exception as exc:
        _raise_unavailable(exc, event="task_schedule_runs_list_failed")
    return success_response(data=data, trace_id=get_trace_id(request))
