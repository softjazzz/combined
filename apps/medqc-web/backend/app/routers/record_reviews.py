"""V5 运行/终末病历初审复审独立入口。"""

import logging
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field

from ..core.security import get_current_user
from ..services.defect_rectification_service import RectificationError
from ..services.record_review_workflow_service import RecordReviewWorkflowService

router = APIRouter(prefix="/api/v1/record-reviews", tags=["record-reviews"])
service = RecordReviewWorkflowService()
logger = logging.getLogger(__name__)


class Source(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    institute_id: str = Field(min_length=1, max_length=128)
    patient_id: str = Field(min_length=1, max_length=128)
    visit_id: str = Field(min_length=1, max_length=128)
    scene: Literal["running", "final"]
    root_job_id: str = Field(min_length=1, max_length=36)
    envelope_id: str = Field(min_length=1, max_length=36)
    rule_set_key: str = Field(min_length=1, max_length=96)
    rule_set_version: str = Field(min_length=1, max_length=96)


class Decision(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    source: Source
    expected_state: Literal["pending_review", "pending_recheck"]
    decision: Literal["approved", "doubtful"]
    reason: str = Field(default="", max_length=2000)
    request_id: str = Field(min_length=36, max_length=36)


def _call(user, method, *args, **kwargs):
    if not user.get("id"):
        raise HTTPException(403, "缺少持久账号")
    try:
        return method(str(user["id"]), *args, **kwargs)
    except RectificationError as exc:
        raise HTTPException(exc.status, str(exc)) from exc
    except Exception as exc:
        logger.exception("病历审核操作失败")
        raise HTTPException(503, "审核服务暂不可用，请刷新核对") from exc


@router.get("")
def listing(
    state: Literal[
        "open", "history", "pending_review", "pending_recheck", "approved", "doubtful"
    ] = "open",
    scene: Literal["running", "final"] | None = None,
    page: int = Query(default=1, ge=1, le=10000),
    page_size: int = Query(default=10, ge=1, le=100),
    user=Depends(get_current_user),
):
    return _call(
        user, service.list, state=state, scene=scene, page=page, page_size=page_size
    )


@router.get("/current")
def current(source: Source = Depends(), user=Depends(get_current_user)):
    return _call(user, service.current, source=source.model_dump())


@router.get("/{review_id}")
def history(review_id: str, user=Depends(get_current_user)):
    return _call(user, service.history, review_id)


@router.post("")
def submit(body: Decision, user=Depends(get_current_user)):
    return _call(user, service.submit, **body.model_dump())
