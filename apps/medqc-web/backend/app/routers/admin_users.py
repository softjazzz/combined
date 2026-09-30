"""管理员维护账号科室；科室是医生数据范围与申诉授权的依据。"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, ConfigDict, Field

from ..core.audit import audit_event
from ..core.response import get_trace_id, success_response
from ..core.security import get_current_user, require_roles
from ..services.admin_user_service import (
    DEPARTMENT_MAX_LENGTH,
    AdminUserConflict,
    AdminUserInvalid,
    AdminUserNotFound,
    AdminUserService,
    AdminUserUnavailable,
)

router = APIRouter(
    prefix="/api/v1/admin/users",
    tags=["admin-users"],
    dependencies=[Depends(require_roles("admin"))],
)


def get_admin_user_service() -> AdminUserService:
    try:
        return AdminUserService()
    except AdminUserUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


class UserDepartmentUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    department: Optional[str] = Field(None, max_length=DEPARTMENT_MAX_LENGTH)
    expected_updated_at: datetime


@router.get("")
async def list_admin_users(
    request: Request,
    q: Optional[str] = Query(None, max_length=100),
    department: Optional[str] = Query(None, max_length=DEPARTMENT_MAX_LENGTH),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    service: AdminUserService = Depends(get_admin_user_service),
):
    try:
        data = service.list_users(query=q, department=department, page=page, page_size=page_size)
    except Exception as exc:
        raise HTTPException(status_code=503, detail="账号列表暂不可用") from exc
    return success_response(data=data, message="获取账号列表成功", trace_id=get_trace_id(request))


@router.put("/{user_id}/department")
async def update_user_department(
    request: Request,
    user_id: str,
    payload: UserDepartmentUpdateRequest,
    current_user: Dict[str, Any] = Depends(get_current_user),
    service: AdminUserService = Depends(get_admin_user_service),
):
    try:
        updated = service.set_department(
            user_id=user_id,
            department=payload.department,
            expected_updated_at=payload.expected_updated_at,
        )
    except AdminUserNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except AdminUserConflict as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except AdminUserInvalid as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    audit_event(
        request,
        action="admin_user_department_update",
        resource=f"sys_user:{user_id}",
        outcome="success",
        details={
            "previous_department": updated.get("previous_department"),
            "department": updated.get("department"),
        },
        current_user=current_user,
    )
    return success_response(data=updated, message="科室已更新", trace_id=get_trace_id(request))
