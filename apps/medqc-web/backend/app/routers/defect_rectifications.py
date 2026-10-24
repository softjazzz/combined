"""现代缺陷整改：角色来自持久账号，数据库或来源故障失败关闭。"""

import logging
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field, model_validator

from ..core.security import get_current_user
from ..services.defect_rectification_service import (
    DefectRectificationService,
    RectificationError,
)

router = APIRouter(
    prefix="/api/v1/defect-rectifications", tags=["defect-rectifications"]
)
logger = logging.getLogger(__name__)
service = DefectRectificationService()


class Create(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    institute_id: str = Field(min_length=1, max_length=128)
    patient_id: str = Field(min_length=1, max_length=128)
    visit_id: str = Field(min_length=1, max_length=128)
    scene: Literal["running", "final", "outpatient_emergency"]
    target_kind: Literal["canonical_defect", "task_manual_defect"]
    target_id: str = Field(min_length=1, max_length=100)
    root_job_id: str = Field(min_length=1, max_length=36)
    envelope_id: str = Field(min_length=1, max_length=36)
    assignee_id: str = Field(min_length=1, max_length=36)
    requirement: str = Field(min_length=10, max_length=2000)


class Action(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    version: int = Field(strict=True, ge=1)
    action: Literal["submit", "approve", "reject", "urge", "withdraw_urge"]
    comment: str = Field(min_length=10, max_length=2000)
    urge_event_id: str | None = Field(default=None, min_length=1, max_length=36)

    @model_validator(mode="after")
    def validate_urge_reference(self):
        if (self.action == "withdraw_urge") != (self.urge_event_id is not None):
            raise ValueError("撤回催办须且仅须提供原催办事件")
        return self


def _call(user, method, *args, **kwargs):
    actor_id = str(user.get("id") or user.get("user_id") or "")
    if not actor_id:
        raise HTTPException(403, "缺少账号身份")
    try:
        return {"success": True, "data": method(actor_id, *args, **kwargs)}
    except RectificationError as exc:
        raise HTTPException(exc.status, str(exc)) from None
    except Exception as exc:
        logger.warning("现代整改请求失败 error_type=%s", type(exc).__name__)
        raise HTTPException(
            503, "整改服务暂不可用；写入结果请刷新核对，勿重复提交"
        ) from None


@router.post("")
def create(body: Create, user=Depends(get_current_user)):
    return _call(user, service.create, body.model_dump())


@router.get("")
def list_tasks(
    state: str | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    institute_id: str | None = None,
    patient_id: str | None = None,
    visit_id: str | None = None,
    scene: str | None = None,
    target_kind: str | None = None,
    target_id: str | None = None,
    root_job_id: str | None = None,
    envelope_id: str | None = None,
    user=Depends(get_current_user),
):
    source = dict(
        institute_id=institute_id,
        patient_id=patient_id,
        visit_id=visit_id,
        scene=scene,
        target_kind=target_kind,
        target_id=target_id,
        root_job_id=root_job_id,
        envelope_id=envelope_id,
    )
    return _call(
        user,
        service.list,
        state=state,
        page=page,
        page_size=page_size,
        source=source if any(value is not None for value in source.values()) else None,
    )


@router.get("/candidates")
def candidates(
    institute_id: str = Query(min_length=1, max_length=128),
    patient_id: str = Query(min_length=1, max_length=128),
    visit_id: str = Query(min_length=1, max_length=128),
    expected_job_id: str = Query(min_length=1, max_length=36),
    user=Depends(get_current_user),
):
    return _call(
        user,
        service.candidates,
        institute_id=institute_id,
        patient_id=patient_id,
        visit_id=visit_id,
        expected_job_id=expected_job_id,
    )


@router.get("/{task_id}")
def detail(task_id: str, user=Depends(get_current_user)):
    return _call(user, service.detail, task_id)


@router.post("/{task_id}/actions")
def action(task_id: str, body: Action, user=Depends(get_current_user)):
    return _call(user, service.transition, task_id, **body.model_dump())


@router.get("/{task_id}/comparison")
def comparison(
    task_id: str,
    event_id: str = Query(min_length=1, max_length=36),
    user=Depends(get_current_user),
):
    return _call(user, service.comparison, task_id, event_id)
