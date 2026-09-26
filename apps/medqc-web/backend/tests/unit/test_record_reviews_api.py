"""病历审核 HTTP 合同：路径挂载、权限、DTO、错误映射与 503 脱敏。"""

from __future__ import annotations

from datetime import datetime

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.exc import OperationalError

from app.routers import record_reviews
from app.services import record_review_service as service

PATH = "/api/v1/tasks/task-1/records/rec-a/review"
TODO = "/api/v1/record-reviews/todo"
REQUEST_ID = "00000000-0000-4000-8000-000000000001"


def body(**changes):
    data = {"run_number": 1, "decision": "approved", "request_id": REQUEST_ID, "envelope_id": "env-a1"}
    data.update(changes)
    return data


def saved():
    return {
        "id": "review-1", "request_id": REQUEST_ID, "task_id": "task-1", "task_record_id": "rec-a",
        "run_number": 1, "job_id": "job-1", "envelope_id": "env-a1", "rule_set_key": "k",
        "rule_set_version": "v", "stage": "initial", "decision": "approved", "reason": None,
        "reviewer_id": "qc-1", "created_at": datetime(2026, 9, 26), "state": "approved", "idempotent": False,
    }


def client(monkeypatch, roles=("qc_staff",)):
    app = FastAPI()
    app.include_router(record_reviews.router)
    app.dependency_overrides[record_reviews.get_current_user] = lambda: {"id": "qc-1", "roles": list(roles)}
    audits = []
    monkeypatch.setattr(record_reviews, "audit_event", lambda *args, **kwargs: audits.append(kwargs))
    return TestClient(app), audits


def test_paths_are_mounted_with_full_prefix():
    paths = {(route.path, method) for route in record_reviews.router.routes for method in route.methods}
    assert paths == {
        ("/api/v1/tasks/{task_id}/records/{task_record_id}/review", "GET"),
        ("/api/v1/tasks/{task_id}/records/{task_record_id}/review", "POST"),
        ("/api/v1/record-reviews/todo", "GET"),
    }


def test_get_review_passes_actor_and_workspace(monkeypatch):
    calls = []

    def fake(**kwargs):
        calls.append(kwargs)
        return {"state": "pending_review", "stage": "initial"}

    monkeypatch.setattr(service, "get_record_review", fake)
    http, _ = client(monkeypatch)
    assert http.get(PATH).status_code == 422  # run_number 必填
    response = http.get(PATH, params={"run_number": 1})
    assert response.status_code == 200
    assert response.json()["data"]["state"] == "pending_review"
    assert calls[0]["actor_id"] == "qc-1" and calls[0]["run_number"] == 1
    assert calls[0]["workspace_factory"] is record_reviews._sichuan_workspace_service


def test_post_dto_permission_and_audit(monkeypatch):
    calls = []

    def fake(**kwargs):
        calls.append(kwargs)
        return saved()

    monkeypatch.setattr(service, "submit_record_review", fake)
    http, audits = client(monkeypatch)
    for invalid in (
        {}, body(decision="rejected"), body(decision="doubtful"), body(decision="doubtful", reason="  "),
        body(request_id="bad"), body(run_number=0), body(run_number="1"), body(envelope_id=" "),
        body(stage="recheck"),
    ):
        assert http.post(PATH, json=invalid).status_code == 422
    assert calls == []
    response = http.post(PATH, json=body(decision="doubtful", reason=" 原因 "))
    assert response.status_code == 200
    assert calls[0]["reason"] == "原因" and calls[0]["request_id"] == REQUEST_ID
    assert calls[0]["actor_id"] == "qc-1" and calls[0]["task_record_id"] == "rec-a"
    assert audits[0]["action"] == "tasks.records.review.submit"
    assert "P1" not in str(audits)

    doctor, _ = client(monkeypatch, roles=("doctor",))
    assert doctor.post(PATH, json=body()).status_code == 403
    assert len(calls) == 1


@pytest.mark.parametrize("error,status,detail", [
    (service.RecordReviewNotFound("任务不存在"), 404, "任务不存在"),
    (service.RecordReviewForbidden("当前用户未受领该病历"), 403, "当前用户未受领该病历"),
    (service.RecordReviewInvalid("存疑必须填写原因"), 422, "存疑必须填写原因"),
    (service.RecordReviewConflict("result_changed", "已替换"), 409, {"code": "result_changed", "message": "已替换"}),
    (service.RecordReviewConflict("already_decided", "已决定"), 409, {"code": "already_decided", "message": "已决定"}),
    (service.RecordReviewConflict("idempotency_conflict", "冲突"), 409,
     {"code": "idempotency_conflict", "message": "冲突"}),
])
def test_post_error_mapping(monkeypatch, error, status, detail):
    def fake(**kwargs):
        raise error

    monkeypatch.setattr(service, "submit_record_review", fake)
    http, audits = client(monkeypatch)
    response = http.post(PATH, json=body())
    assert response.status_code == status
    assert response.json()["detail"] == detail
    assert audits == []


@pytest.mark.parametrize("error", [
    OperationalError("SELECT secret_column FROM qc_record_reviews", {}, Exception("password=x")),
    service.RecordReviewUnavailable("内部细节"),
    RuntimeError("workspace SELECT leak"),
])
def test_unavailable_is_fixed_and_sanitized(monkeypatch, error):
    def fake(**kwargs):
        raise error

    for name in ("submit_record_review", "get_record_review", "list_my_record_review_todos"):
        monkeypatch.setattr(service, name, fake)
    http, _ = client(monkeypatch)
    for response in (
        http.post(PATH, json=body()), http.get(PATH, params={"run_number": 1}), http.get(TODO),
    ):
        assert response.status_code == 503
        assert response.json()["detail"] == record_reviews._UNAVAILABLE_DETAIL
        assert "SELECT" not in response.text and "secret" not in response.text


def test_real_service_database_failure_is_sanitized(monkeypatch):
    class Broken:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def execute(self, *args, **kwargs):
            raise OperationalError("SELECT secret FROM qc_tasks", {}, Exception("boom"))

    monkeypatch.setattr(service, "SessionLocal", lambda: Broken())
    http, _ = client(monkeypatch)
    response = http.get(TODO)
    assert response.status_code == 503 and "secret" not in response.text


def test_todo_query_validation_and_passthrough(monkeypatch):
    calls = []

    def fake(**kwargs):
        calls.append(kwargs)
        return {"items": [], "total": 0, "page": kwargs["page"], "page_size": kwargs["page_size"]}

    monkeypatch.setattr(service, "list_my_record_review_todos", fake)
    http, _ = client(monkeypatch)
    for params in ({"stage": "other"}, {"page": 0}, {"page_size": 101}, {"scene": "outpatient"}):
        assert http.get(TODO, params=params).status_code == 422
    response = http.get(TODO, params={"stage": "recheck", "scene": "final", "page": 2, "page_size": 5})
    assert response.status_code == 200
    assert calls == [{
        "actor_id": "qc-1", "stage": "recheck", "scene": "final", "page": 2, "page_size": 5,
        "workspace_factory": record_reviews._sichuan_workspace_service,
    }]
    assert http.get(TODO).status_code == 200
    assert calls[-1]["scene"] == "all" and calls[-1]["stage"] is None


def test_count_helper_binds_workspace(monkeypatch):
    calls = []

    def fake(actor_id, scene=None, workspace_factory=None):
        calls.append((actor_id, scene, workspace_factory))
        return {"initial": 1, "recheck": 2}

    monkeypatch.setattr(service, "count_my_record_review_todos", fake)
    assert record_reviews.count_my_record_review_todos("qc-1", scene="running") == {"initial": 1, "recheck": 2}
    assert calls == [("qc-1", "running", record_reviews._sichuan_workspace_service)]
