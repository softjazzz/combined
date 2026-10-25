"""现代申诉独立入口，旧主键申诉不进入 V5 主链。"""

import logging
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field

from ..core.security import get_current_user
from ..services.defect_rectification_service import RectificationError
from ..services.modern_appeal_service import ModernAppealService

router = APIRouter(prefix="/api/v1/modern-appeals", tags=["modern-appeals"])
service = ModernAppealService()
logger = logging.getLogger(__name__)


class Create(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    rectification_id: str = Field(min_length=1, max_length=36)
    reason: str = Field(min_length=10, max_length=2000)


class Action(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    expected_status: Literal["pending", "reviewing"]
    action: Literal["withdraw", "approve", "reject"]
    comment: str = Field(min_length=10, max_length=2000)


def _call(user, method, *args, **kwargs):
    if not user.get("id"):
        raise HTTPException(403, "缺少持久账号")
    try:
        return method(str(user["id"]), *args, **kwargs)
    except RectificationError as exc:
        raise HTTPException(exc.status, str(exc)) from exc
    except Exception as exc:
        logger.exception("现代申诉操作失败")
        raise HTTPException(503, "申诉服务暂不可用，请刷新核对") from exc


@router.post("")
def create(body: Create, user=Depends(get_current_user)):
    return _call(user, service.create, **body.model_dump())


@router.get("")
def listing(
    state: Literal["open", "pending", "reviewing", "approved", "rejected", "withdrawn"]
    | None = None,
    scene: Literal["running", "final"] | None = None,
    page: int = Query(default=1, ge=1, le=10000),
    page_size: int = Query(default=10, ge=1, le=100),
    user=Depends(get_current_user),
):
    return _call(
        user, service.list, state=state, scene=scene, page=page, page_size=page_size
    )


@router.get("/{appeal_id}")
def detail(appeal_id: str, user=Depends(get_current_user)):
    return _call(user, service.detail, appeal_id)


@router.post("/{appeal_id}/actions")
def action(appeal_id: str, body: Action, user=Depends(get_current_user)):
    return _call(user, service.transition, appeal_id, **body.model_dump())
