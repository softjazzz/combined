"""管理员维护账号医院＋科室；二者共同决定医生申诉范围。"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, ConfigDict, Field

from ..core.audit import audit_event
from ..core.response import get_trace_id, success_response
from ..core.security import get_current_user
from ..services.admin_user_service import (
    DEPARTMENT_MAX_LENGTH,
    INSTITUTE_ID_MAX_LENGTH,
    AdminUserConflict,
    AdminUserForbidden,
    AdminUserInvalid,
    AdminUserNotFound,
    AdminUserService,
    AdminUserUnavailable,
)

router = APIRouter(
    prefix="/api/v1/admin/users",
    tags=["admin-users"],
)


def get_admin_user_service() -> AdminUserService:
    try:
        return AdminUserService()
    except AdminUserUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


async def require_durable_admin(
    current_user: Dict[str, Any] = Depends(get_current_user),
    service: AdminUserService = Depends(get_admin_user_service),
) -> Dict[str, Any]:
    try:
        return service.require_durable_admin(current_user.get("id") or current_user.get("user_id"))
    except AdminUserForbidden as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except AdminUserUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


class UserDepartmentUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    institute_id: Optional[str] = Field(..., max_length=INSTITUTE_ID_MAX_LENGTH)
    department: Optional[str] = Field(..., max_length=DEPARTMENT_MAX_LENGTH)
    expected_updated_at: datetime


@router.get("/scope-options")
async def list_user_scope_options(
    request: Request,
    _actor: Dict[str, Any] = Depends(require_durable_admin),
    service: AdminUserService = Depends(get_admin_user_service),
):
    try:
        data = service.list_scope_options()
    except AdminUserUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return success_response(data=data, message="获取机构科室选项成功", trace_id=get_trace_id(request))


@router.get("")
async def list_admin_users(
    request: Request,
    q: Optional[str] = Query(None, max_length=100),
    department: Optional[str] = Query(None, max_length=DEPARTMENT_MAX_LENGTH),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    _actor: Dict[str, Any] = Depends(require_durable_admin),
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
    current_user: Dict[str, Any] = Depends(require_durable_admin),
    service: AdminUserService = Depends(get_admin_user_service),
):
    try:
        updated = service.set_scope(
            user_id=user_id,
            institute_id=payload.institute_id,
            department=payload.department,
            expected_updated_at=payload.expected_updated_at,
        )
    except AdminUserNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except AdminUserConflict as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except AdminUserInvalid as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except AdminUserUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    audit_event(
        request,
        action="admin_user_scope_update",
        resource=f"sys_user:{user_id}",
        outcome="success",
        details={
            "previous_institute_id": updated.get("previous_institute_id"),
            "previous_department": updated.get("previous_department"),
            "institute_id": updated.get("institute_id"),
            "department": updated.get("department"),
        },
        current_user=current_user,
    )
    return success_response(data=updated, message="账号医院与科室已更新", trace_id=get_trace_id(request))
