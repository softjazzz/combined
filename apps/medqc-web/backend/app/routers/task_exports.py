"""全部任务列表导出接口。"""

from __future__ import annotations

import logging
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import Response
from starlette.concurrency import run_in_threadpool

from ..core.audit import audit_event
from ..core.permissions import (
    PermissionAction,
    ResourceType,
    UserRole,
    has_any_role,
    require_permission,
)
from ..core.security import get_current_user
from ..services import task_export_service

router = APIRouter(prefix="/api/v1/task-exports", tags=["task-exports"])
logger = logging.getLogger(__name__)

_UNAVAILABLE_DETAIL = "任务导出暂不可用，请稍后重试"


@router.get("")
@require_permission(ResourceType.QC_TASKS, PermissionAction.READ)
async def export_tasks(
    request: Request,
    scene: Literal["running", "final", "outpatient", "unclassified"] | None = Query(None),
    status: str | None = Query(None),
    keyword: str | None = Query(None),
    department: str | None = Query(None),
    created_start: str | None = Query(None),
    created_end: str | None = Query(None),
    current_user: dict = Depends(get_current_user),
):
    """按全部任务页的真实筛选条件导出，不受当前分页影响。"""
    unexpected = set(request.query_params).difference({
        "scene", "status", "keyword", "department", "created_start", "created_end",
    })
    if unexpected:
        raise HTTPException(status_code=422, detail="包含尚未生效的任务筛选参数")
    actor_id = current_user.get("id") or current_user.get("user_id")
    if not isinstance(actor_id, str) or not actor_id.strip():
        raise HTTPException(status_code=401, detail="当前用户缺少有效身份")
    if not has_any_role(current_user, [UserRole.ADMIN, UserRole.QC_MANAGER]):
        raise HTTPException(status_code=403, detail="仅管理员和质控主管可导出全部任务")

    try:
        result = await run_in_threadpool(
            task_export_service.export_all_tasks,
            scene=scene,
            status=status,
            keyword=keyword,
            department=department,
            created_start=created_start,
            created_end=created_end,
        )
    except task_export_service.TaskExportInvalid as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except task_export_service.TaskExportTooLarge as exc:
        raise HTTPException(
            status_code=413,
            detail={
                "code": "task_export_too_large",
                "message": str(exc),
                "matched_at_least": exc.matched_at_least,
                "limit": exc.limit,
            },
        ) from exc
    except Exception as exc:
        logger.error("task_export_failed error_type=%s", type(exc).__name__)
        raise HTTPException(status_code=503, detail=_UNAVAILABLE_DETAIL) from None

    audit_event(
        request,
        action="tasks.export",
        resource="/api/v1/task-exports",
        outcome="success",
        details={
            "scene": scene,
            "status": status,
            "keyword_applied": keyword not in (None, ""),
            "department_applied": department not in (None, ""),
            "created_start": created_start,
            "created_end": created_end,
            "total_rows": result.row_count,
            "limit": task_export_service.MAX_EXPORT_ROWS,
        },
        current_user=current_user,
    )
    return Response(
        content=result.content,
        media_type="text/csv; charset=utf-8",
        headers={
            "Cache-Control": "no-store",
            "X-Content-Type-Options": "nosniff",
            "Content-Disposition": "attachment; filename*=UTF-8''task-list.csv",
        },
    )
