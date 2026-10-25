"""病历沟通路由；异常不泄露来源或连接信息。"""

import logging
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field, model_validator

from ..core.security import get_current_user
from ..services.case_communication_service import CaseCommunicationService
from ..services.defect_rectification_service import RectificationError

router = APIRouter(prefix="/api/v1/case-communications", tags=["case-communications"])
service = CaseCommunicationService()
logger = logging.getLogger(__name__)


class CandidateSource(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    institute_id: str = Field(min_length=1, max_length=128)
    patient_id: str = Field(min_length=1, max_length=128)
    visit_id: str = Field(min_length=1, max_length=128)
    root_job_id: str = Field(min_length=1, max_length=36)


class Source(CandidateSource):
    scene: Literal["running", "final"]


class Create(Source):
    envelope_id: str = Field(min_length=1, max_length=36)
    rule_set_key: str = Field(min_length=1, max_length=100)
    rule_set_version: str = Field(min_length=1, max_length=100)
    recipient_id: str = Field(min_length=1, max_length=36)
    action: Literal["urge", "opinion", "withdraw"]
    content: str = Field(min_length=1, max_length=2000)
    request_id: str = Field(min_length=1, max_length=36)
    related_event_id: str | None = Field(None, min_length=1, max_length=36)

    @model_validator(mode="after")
    def withdrawal(self):
        if (self.action == "withdraw") != (self.related_event_id is not None):
            raise ValueError("撤回须且仅须提供原催办事件")
        return self


def _call(user, method, *args):
    actor = str(user.get("id") or user.get("user_id") or "").strip()
    if not actor:
        raise HTTPException(403, "缺少账号身份")
    try:
        return {"success": True, "data": method(actor, *args)}
    except RectificationError as exc:
        raise HTTPException(exc.status, str(exc)) from None
    except Exception as exc:
        logger.warning("病历沟通失败 error_type=%s", type(exc).__name__)
        raise HTTPException(
            503, "病历沟通暂不可用；写入结果请刷新核对，勿重复提交"
        ) from None


@router.post("/candidates")
def candidates(body: CandidateSource, user=Depends(get_current_user)):
    return _call(user, service.candidates, body.model_dump())


@router.post("")
def create(body: Create, user=Depends(get_current_user)):
    return _call(user, service.create, body.model_dump())


@router.get("/inbox")
def inbox(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    user=Depends(get_current_user),
):
    return _call(user, service.inbox, page, page_size)


@router.post("/{event_id}/read")
def read(event_id: str, user=Depends(get_current_user)):
    return _call(user, service.read, event_id)


@router.get("/{event_id}")
def detail(event_id: str, user=Depends(get_current_user)):
    return _call(user, service.detail, event_id)
