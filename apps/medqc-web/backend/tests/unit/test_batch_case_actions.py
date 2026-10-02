"""批量适配只用注入的合成owner，不创建数据库连接。"""
from contextlib import nullcontext
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.routers import batch_case_actions as router_module
from app.routers.batch_case_actions import BatchCaseActions
from app.services import record_review_service as reviews
from app.services.defect_rectification_service import RectificationError


def setup():
    data = dict(institute_id="I", patient_id="P", visit_id="V", scene="running")
    source = dict(**data, root_job_id="J", envelope_id="E", rule_set_key="k")
    communications = SimpleNamespace(
        sessions=lambda: nullcontext(object()),
        person=Mock(return_value={"roles": {"qc_manager"}, "institute_id": "I"}),
        department=Mock(return_value="科室"),
        candidates=Mock(return_value={"source": source, "doctors": []}),
    )
    reviews = SimpleNamespace(
        get_case_review=Mock(return_value={"result": {"job_id": "J", "envelope_id": "E"}}),
        submit_case_review=Mock(return_value={"state": "approved"}),
    )
    return BatchCaseActions(communications, reviews), data


def test_no_recipient_does_not_block_approval_and_owner_receives_frozen_identity():
    service, data = setup()
    assert service.prepare("actor", data)["doctors"] == []
    assert "rule_set_key" not in service.prepare("actor", data)["source"]
    assert service.approve("actor", dict(**data, job_id="J", envelope_id="E", request_id="R")) == {"state": "approved"}
    service.reviews.submit_case_review.assert_called_once_with(
        institute_id="I", patient_id="P", visit_id="V", job_id="J", envelope_id="E",
        actor_id="actor", request_id="R", decision="approved", reason=None,
    )


@pytest.mark.parametrize("person", [
    {"roles": {"qc_manager"}, "institute_id": "OTHER"},
    {"roles": {"doctor"}, "institute_id": "I"},
])
def test_persistent_role_or_cross_institute_rejected_before_review_read(person):
    service, data = setup()
    service.communications.person.return_value = person
    with pytest.raises(RectificationError) as error:
        service.prepare("actor", data)
    assert error.value.status == 403
    service.reviews.get_case_review.assert_not_called()


@pytest.mark.parametrize("field", ["job_id", "envelope_id"])
def test_changed_result_never_calls_owner(field):
    service, data = setup()
    payload = dict(**data, job_id="J", envelope_id="E", request_id="R")
    payload[field] = "stale"
    with pytest.raises(RectificationError):
        service.approve("actor", payload)
    service.reviews.submit_case_review.assert_not_called()


def test_approve_rechecks_permission_and_propagates_owner_conflict():
    service, data = setup()
    service.prepare("actor", data)
    service.communications.department.side_effect = RectificationError("病例不可访问", 403)
    with pytest.raises(RectificationError):
        service.approve("actor", dict(**data, job_id="J", envelope_id="E", request_id="R"))
    service.reviews.submit_case_review.assert_not_called()


def test_scene_failure_from_source_owner_does_not_submit():
    service, data = setup()
    service.communications.candidates.side_effect = RectificationError("场景不一致", 409)
    with pytest.raises(RectificationError):
        service.approve("actor", dict(**data, job_id="J", envelope_id="E", request_id="R"))
    service.reviews.submit_case_review.assert_not_called()


@pytest.mark.parametrize("error,status", [
    (reviews.RecordReviewForbidden("private"), 403),
    (reviews.RecordReviewConflict("result_changed", "private"), 409),
    (RuntimeError("private SQL detail"), 503),
])
def test_http_failures_are_precise_and_sanitized(monkeypatch, error, status):
    app = FastAPI()
    app.include_router(router_module.router)
    app.dependency_overrides[router_module.get_current_user] = lambda: {"id": "actor"}
    monkeypatch.setattr(router_module.service, "prepare", Mock(side_effect=error))
    _, data = setup()
    response = TestClient(app).post("/api/v1/record-reviews/case/batch-item/prepare", json=data)
    assert response.status_code == status
    assert "private" not in response.text
