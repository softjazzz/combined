"""系统配置中的真实账号维护，所有授权再次读取持久账号。"""

import logging
from datetime import datetime
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import (
    BaseModel,
    ConfigDict,
    EmailStr,
    Field,
    StringConstraints,
    field_validator,
)

from ..core.security import get_current_user
from ..services.account_management_service import AccountManagementService
from ..services.account_registration_service import AccountRegistrationService
from ..schemas.registration import RegistrationReview
from ..services.defect_rectification_service import RectificationError

router = APIRouter(prefix="/api/v1/account-management", tags=["account-management"])
service = AccountManagementService()
registration_service = AccountRegistrationService()
logger = logging.getLogger(__name__)
Role = Literal["admin", "qc_manager", "qc_staff", "doctor"]


class Binding(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    display_name: str = Field(min_length=1, max_length=100)
    institute_id: str = Field(min_length=1, max_length=128)
    department: str = Field(min_length=1, max_length=100)
    roles: list[Role] = Field(min_length=1, max_length=4)


class Create(Binding):
    username: str = Field(
        min_length=3, max_length=50, pattern=r"^[A-Za-z0-9][A-Za-z0-9_.-]+$"
    )
    email: EmailStr = Field(max_length=100)
    password: Annotated[
        str, StringConstraints(strip_whitespace=False, min_length=12, max_length=72)
    ] = Field(repr=False)

    @field_validator("password")
    @classmethod
    def password_bytes(cls, value):
        if len(value.encode("utf-8")) > 72:
            raise ValueError("口令 UTF-8 长度不得超过72字节")
        return value


class Update(Binding):
    is_active: bool = Field(strict=True)
    expected_updated_at: datetime | None


def _call(user, method, *args, **kwargs):
    actor_id = str(user.get("id") or user.get("user_id") or "")
    if not actor_id:
        raise HTTPException(403, "缺少持久账号")
    try:
        return {"success": True, "data": method(actor_id, *args, **kwargs)}
    except RectificationError as exc:
        raise HTTPException(exc.status, str(exc)) from None
    except Exception as exc:
        logger.warning("账号维护失败 error_type=%s", type(exc).__name__)
        raise HTTPException(
            503, "持久账号服务暂不可用，请刷新核对，勿重复提交"
        ) from None


@router.get("")
def list_accounts(
    keyword: str = Query("", max_length=100),
    role: Role | None = None,
    active: bool | None = None,
    page: int = Query(1, ge=1, le=10000),
    page_size: int = Query(20, ge=1, le=100),
    user=Depends(get_current_user),
):
    return _call(
        user,
        service.list,
        keyword=keyword,
        role=role,
        active=active,
        page=page,
        page_size=page_size,
    )


@router.post("")
def create(body: Create, user=Depends(get_current_user)):
    return _call(user, service.create, body.model_dump())


@router.put("/{user_id}")
def update(user_id: str, body: Update, user=Depends(get_current_user)):
    return _call(user, service.update, user_id, body.model_dump())


@router.get("/registrations/list")
def list_registrations(
    status: Literal["pending", "approved", "rejected"] = "pending",
    page: int = Query(1, ge=1, le=10000),
    page_size: int = Query(20, ge=1, le=100),
    user=Depends(get_current_user),
):
    return _call(user, registration_service.list, status=status, page=page, page_size=page_size)


@router.get("/registrations/{user_id}")
def registration_detail(user_id: str, user=Depends(get_current_user)):
    return _call(user, registration_service.detail, user_id)


@router.post("/registrations/{user_id}/review")
def review_registration(user_id: str, body: RegistrationReview, user=Depends(get_current_user)):
    return _call(user, registration_service.review, user_id, body.model_dump())
