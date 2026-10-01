"""现代缺陷整改：角色来自持久账号，数据库或来源故障失败关闭。"""

import logging
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field

from ..core.security import get_current_user
from ..services.defect_rectification_service import DefectRectificationService, RectificationError
from ..services.appeal_workspace_target_service import (
    AppealWorkspaceTargetConflict, AppealWorkspaceTargetInvalid, AppealWorkspaceTargetNotFound,
)
from ..services.appeal_manual_target_service import AppealManualTargetConflict, AppealManualTargetNotFound

router = APIRouter(prefix="/api/v1/defect-rectifications", tags=["defect-rectifications"])
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
    action: Literal["submit", "approve", "reject", "urge"]
    comment: str = Field(min_length=10, max_length=2000)


def _call(user, method, *args, **kwargs):
    actor_id = str(user.get("id") or user.get("user_id") or "")
    if not actor_id:
        raise HTTPException(403, "缺少账号身份")
    try:
        return {"success": True, "data": method(actor_id, *args, **kwargs)}
    except RectificationError as exc:
        raise HTTPException(exc.status, str(exc)) from None
    except (AppealWorkspaceTargetNotFound, AppealManualTargetNotFound):
        raise HTTPException(404, "缺陷来源不存在") from None
    except (AppealWorkspaceTargetConflict, AppealManualTargetConflict):
        raise HTTPException(409, "缺陷来源已变化，请刷新后重试") from None
    except AppealWorkspaceTargetInvalid:
        raise HTTPException(422, "缺陷来源参数无效") from None
    except Exception as exc:
        logger.warning("现代整改请求失败 error_type=%s", type(exc).__name__)
        raise HTTPException(503, "整改服务暂不可用；写入结果请刷新核对，勿重复提交") from None


@router.post("")
def create(body: Create, user=Depends(get_current_user)):
    return _call(user, service.create, body.model_dump())


@router.get("")
def list_tasks(state: str | None = None, page: int = Query(1, ge=1),
               page_size: int = Query(20, ge=1, le=100), user=Depends(get_current_user)):
    return _call(user, service.list, state=state, page=page, page_size=page_size)


@router.get("/candidates")
def candidates(institute_id: str = Query(min_length=1, max_length=128),
               patient_id: str = Query(min_length=1, max_length=128),
               visit_id: str = Query(min_length=1, max_length=128),
               expected_job_id: str = Query(min_length=1, max_length=36),
               user=Depends(get_current_user)):
    return _call(user, service.candidates, institute_id=institute_id, patient_id=patient_id,
                 visit_id=visit_id, expected_job_id=expected_job_id)


@router.get("/{task_id}")
def detail(task_id: str, user=Depends(get_current_user)):
    return _call(user, service.detail, task_id)


@router.post("/{task_id}/actions")
def action(task_id: str, body: Action, user=Depends(get_current_user)):
    return _call(user, service.transition, task_id, **body.model_dump())
