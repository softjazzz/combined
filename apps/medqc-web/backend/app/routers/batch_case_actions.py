"""病历列表批量动作的逐例适配，不拥有审核或沟通状态。"""

from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, ConfigDict, Field

from ..core.security import get_current_user
from ..core.audit import audit_event
from ..services import record_review_service as reviews
from ..services.case_communication_service import SOURCE_FIELDS, CaseCommunicationService, _manager
from ..services.defect_rectification_service import RectificationError
from .case_communications import _call

router = APIRouter(prefix="/api/v1/record-reviews/case/batch-item", tags=["record-reviews"])


class Identity(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    institute_id: str = Field(min_length=1, max_length=128)
    patient_id: str = Field(min_length=1, max_length=128)
    visit_id: str = Field(min_length=1, max_length=128)
    scene: Literal["running", "final"]


class Approval(Identity):
    job_id: str = Field(min_length=1, max_length=36)
    envelope_id: str = Field(min_length=1, max_length=36)
    request_id: UUID


class BatchCaseActions:
    def __init__(self, communications=None, review_owner=None):
        self.communications = communications or CaseCommunicationService()
        self.reviews = review_owner or reviews

    def prepare(self, actor, data):
        identity = {key: data[key] for key in ("institute_id", "patient_id", "visit_id")}
        # 先核验持久化角色与病例范围，才读取审核记录。
        with self.communications.sessions() as session:
            _manager(self.communications.person(session, actor), identity["institute_id"])
            self.communications.department(session, tuple(identity.values()))
        review = self.reviews.get_case_review(**identity, actor_id=actor)
        job_id = review["result"]["job_id"]
        if not job_id:
            raise RectificationError("当前病历没有可操作的最新质控结果", 409)
        candidates = self.communications.candidates(actor, {
            **identity, "scene": data["scene"], "root_job_id": job_id,
        })
        if candidates["source"]["envelope_id"] != review["result"]["envelope_id"]:
            raise RectificationError("病例质控结果已变化，请重新准备", 409)
        return {"review": review, "source": {key: candidates["source"][key] for key in SOURCE_FIELDS},
                "doctors": candidates["doctors"]}

    def approve(self, actor, data):
        prepared = self.prepare(actor, data)
        source = prepared["source"]
        if source["root_job_id"] != data["job_id"] or source["envelope_id"] != data["envelope_id"]:
            raise RectificationError("病例质控结果已变化，请重新准备", 409)
        return self.reviews.submit_case_review(
            **{key: data[key] for key in ("institute_id", "patient_id", "visit_id", "job_id", "envelope_id")},
            actor_id=actor, request_id=str(data["request_id"]), decision="approved", reason=None,
        )


service = BatchCaseActions()


def _invoke(user, method, data):
    def guarded(actor, payload):
        try:
            return method(actor, payload)
        except reviews.RecordReviewForbidden as exc:
            raise RectificationError("无权审核该病例", 403) from exc
    return _call(user, guarded, data)


@router.post("/prepare")
def prepare(body: Identity, user=Depends(get_current_user)):
    return _invoke(user, service.prepare, body.model_dump())


@router.post("/approve")
def approve(body: Approval, request: Request, user=Depends(get_current_user)):
    response = _invoke(user, service.approve, body.model_dump())
    audit_event(request, action="record_reviews.case.batch_item.approve", resource="qc_record_review",
                outcome="success", details={"review_id": response["data"].get("id"),
                                            "request_id": str(body.request_id)}, current_user=user)
    return response
