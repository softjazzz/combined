"""任务编辑专用接口；不复用受领人开始任务的旧 PUT。"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Request
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
from ..schemas.tasks import (
    TaskDraftConfigurationUpdateRequest,
    TaskEditResponse,
    TaskMetadataUpdateRequest,
)
from ..services import task_edit_service


router = APIRouter(prefix="/api/v1/task-edits", tags=["task-edits"])
logger = logging.getLogger(__name__)


def _actor_id(current_user: dict) -> str:
    actor_id = current_user.get("id") or current_user.get("user_id")
    if not isinstance(actor_id, str) or not actor_id.strip():
        raise HTTPException(status_code=401, detail={
            "code": "task_edit_forbidden", "message": "当前用户缺少有效身份",
        })
    return actor_id.strip()


def _is_manager(current_user: dict) -> bool:
    return has_any_role(current_user, [UserRole.ADMIN, UserRole.QC_MANAGER])


def _raise_error(exc: Exception) -> None:
    if isinstance(exc, task_edit_service.TaskEditNotFound):
        status = 404
    elif isinstance(exc, task_edit_service.TaskEditForbidden):
        status = 403
    elif isinstance(exc, task_edit_service.TaskEditConflict):
        status = 409
    elif isinstance(exc, task_edit_service.TaskEditInvalid):
        status = 422
    else:
        status = 503
    code = getattr(exc, "code", "task_edit_unavailable")
    message = str(exc) if status != 503 else "任务编辑暂不可用，请稍后重试"
    raise HTTPException(status_code=status, detail={"code": code, "message": message}) from exc


def _public_result(result: dict) -> tuple[dict, list[str]]:
    data = dict(result)
    changed_fields = list(data.pop("changed_fields", []))
    try:
        data = TaskEditResponse.model_validate(data).model_dump(mode="json")
    except Exception as exc:
        raise task_edit_service.TaskEditUnavailable("任务编辑结果无法确认") from exc
    return data, changed_fields


@router.get("/{task_id}")
@require_permission(ResourceType.QC_TASKS, PermissionAction.READ)
async def get_task_edit(
    request: Request,
    task_id: str,
    current_user: dict = Depends(get_current_user),
):
    try:
        result = await run_in_threadpool(
            task_edit_service.get_task_edit,
            task_id,
            actor_id=_actor_id(current_user),
            is_manager=_is_manager(current_user),
        )
        data, _ = _public_result(result)
    except task_edit_service.TaskEditError as exc:
        if isinstance(exc, task_edit_service.TaskEditUnavailable):
            logger.warning("task_edit_read_failed error_type=%s", type(exc).__name__)
        _raise_error(exc)
    return success_response(data=data, trace_id=get_trace_id(request))


@router.put("/{task_id}/draft-configuration")
@require_permission(ResourceType.QC_TASKS, PermissionAction.UPDATE)
async def put_draft_configuration(
    request: Request,
    task_id: str,
    payload: TaskDraftConfigurationUpdateRequest,
    current_user: dict = Depends(get_current_user),
):
    configuration = payload.model_dump(mode="json", exclude={"configuration_version"})
    try:
        result = await run_in_threadpool(
            task_edit_service.replace_draft_configuration,
            task_id,
            actor_id=_actor_id(current_user),
            is_manager=_is_manager(current_user),
            expected_version=payload.configuration_version,
            configuration=configuration,
        )
        data, changed_fields = _public_result(result)
    except task_edit_service.TaskEditError as exc:
        if isinstance(exc, task_edit_service.TaskEditUnavailable):
            logger.warning("task_edit_draft_update_failed error_type=%s", type(exc).__name__)
        _raise_error(exc)
    audit_event(
        request,
        action="tasks.configuration.update",
        resource="/api/v1/task-edits/{task_id}/draft-configuration",
        outcome="success",
        current_user=current_user,
        details={
            "task_id": task_id,
            "previous_configuration_version": payload.configuration_version,
            "configuration_version": data["configuration_version"],
            "changed_fields": sorted(changed_fields),
        },
    )
    return success_response(data=data, message="任务配置已更新", trace_id=get_trace_id(request))


@router.patch("/{task_id}/metadata")
@require_permission(ResourceType.QC_TASKS, PermissionAction.UPDATE)
async def patch_metadata(
    request: Request,
    task_id: str,
    payload: TaskMetadataUpdateRequest,
    current_user: dict = Depends(get_current_user),
):
    changes = payload.model_dump(
        mode="json",
        exclude={"configuration_version"},
        exclude_unset=True,
    )
    try:
        result = await run_in_threadpool(
            task_edit_service.update_task_metadata,
            task_id,
            actor_id=_actor_id(current_user),
            is_manager=_is_manager(current_user),
            expected_version=payload.configuration_version,
            changes=changes,
        )
        data, changed_fields = _public_result(result)
    except task_edit_service.TaskEditError as exc:
        if isinstance(exc, task_edit_service.TaskEditUnavailable):
            logger.warning("task_edit_metadata_update_failed error_type=%s", type(exc).__name__)
        _raise_error(exc)
    audit_event(
        request,
        action="tasks.metadata.update",
        resource="/api/v1/task-edits/{task_id}/metadata",
        outcome="success",
        current_user=current_user,
        details={
            "task_id": task_id,
            "previous_configuration_version": payload.configuration_version,
            "configuration_version": data["configuration_version"],
            "changed_fields": sorted(changed_fields),
        },
    )
    return success_response(data=data, message="任务信息已更新", trace_id=get_trace_id(request))
