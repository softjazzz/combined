"""Manual defect HTTP contract and permission tests without a business database."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.routers import tasks
from app.services import task_manual_defect_service as service


DEFECT_ID = "00000000-0000-4000-8000-000000000001"
PATH = "/api/v1/tasks/task-1/records/record-a/manual-defects"


def payload(**changes):
    body = {
        "defect_id": DEFECT_ID, "run_number": 1,
        "rule_name": "合成规则", "description": "合成缺陷说明",
        "severity": "warning", "suggestion": "合成整改建议", "evidence": "合成证据",
    }
    body.update(changes)
    return body


def test_document_options_requires_create_permission_and_receives_run(monkeypatch):
    calls = []
    def read(**query):
        calls.append(query)
        return {"documents": [], "job_id": "job-1"}
    monkeypatch.setattr(service, "list_task_manual_document_options", read)
    http, _ = client(monkeypatch)
    path = PATH.replace("manual-defects", "manual-document-options")
    assert http.get(path, params={"run_number": 1}).status_code == 200
    assert {key: value for key, value in calls[0].items() if key != "workspace_factory"} == {
        "task_id": "task-1", "task_record_id": "record-a", "actor_id": "qc-1", "run_number": 1}
    denied, _ = client(monkeypatch, roles=["unknown"])
    assert denied.get(path, params={"run_number": 1}).status_code == 403
    assert len(calls) == 1


def response():
    return {
        "id": DEFECT_ID, "task_id": "task-1", "task_record_id": "record-a",
        "run_number": 1, "rule_name": "合成规则", "description": "合成缺陷说明",
        "severity": "warning", "suggestion": "合成整改建议", "evidence": "合成证据",
        "manual_review_status": "pending", "created_at": datetime.now(timezone.utc),
        "idempotent": False,
    }


def client(monkeypatch, *, roles=None):
    app = FastAPI()
    app.include_router(tasks.router)
    app.dependency_overrides[tasks.get_current_user] = lambda: {
        "id": "qc-1", "roles": ["qc_staff"] if roles is None else roles,
    }
    audits = []
    monkeypatch.setattr(tasks, "audit_event", lambda *args, **kwargs: audits.append(kwargs))
    return TestClient(app), audits


def test_create_strict_dto_permission_and_audit(monkeypatch):
    calls = []

    def create(**kwargs):
        calls.append(kwargs)
        return response()

    monkeypatch.setattr(tasks, "create_task_manual_defect", create)
    http, audits = client(monkeypatch)
    invalid = [
        {}, payload(defect_id="not-a-uuid"), payload(run_number=0),
        payload(run_number=True), payload(run_number="1"),
        payload(rule_name=" "), payload(description=" "),
        payload(severity="urgent"), payload(unexpected="value"),
    ]
    for body in invalid:
        assert http.post(PATH, json=body).status_code == 422
    assert calls == []

    result = http.post(PATH, json=payload())
    assert result.status_code == 200
    assert result.json()["data"]["manual_review_status"] == "pending"
    assert len(calls) == 1
    assert {key: value for key, value in calls[0].items() if key != "workspace_factory"} == {
        "task_id": "task-1", "task_record_id": "record-a", "actor_id": "qc-1",
        **payload(),
        "document_anchor": None,
    }
    assert callable(calls[0]["workspace_factory"])
    assert audits[0]["action"] == "tasks.records.manual_defects.create"
    assert "patient" not in str(audits)

    forbidden, _ = client(monkeypatch, roles=["unknown"])
    assert forbidden.post(PATH, json=payload()).status_code == 403
    assert len(calls) == 1


def test_list_pagination_permission_and_exact_scope(monkeypatch):
    calls = []

    def list_items(**kwargs):
        calls.append(kwargs)
        return {"items": [response()], "total": 1, "limit": kwargs["limit"],
                "offset": kwargs["offset"]}

    monkeypatch.setattr(tasks, "list_task_manual_defects", list_items)
    http, audits = client(monkeypatch)
    for query in ("?offset=-1", "?limit=0", "?limit=51"):
        assert http.get(PATH + query).status_code == 422
    assert calls == []
    result = http.get(PATH + "?limit=1&offset=3")
    assert result.status_code == 200
    assert result.json()["data"]["total"] == 1
    assert calls == [{
        "task_id": "task-1", "task_record_id": "record-a", "actor_id": "qc-1",
        "limit": 1, "offset": 3,
    }]
    assert audits[0]["action"] == "tasks.records.manual_defects.read"
    assert "patient" not in str(audits)

    forbidden, _ = client(monkeypatch, roles=["unknown"])
    assert forbidden.get(PATH).status_code == 403
    assert len(calls) == 1


@pytest.mark.parametrize("error,status", [
    (service.TaskManualDefectNotFound("不存在"), 404),
    (service.TaskManualDefectForbidden("无权"), 403),
    (service.TaskManualDefectConflict("冲突"), 409),
    (service.TaskManualDefectUnavailable("暂不可用"), 503),
    (RuntimeError("private patient detail"), 503),
])
@pytest.mark.parametrize("method", ["post", "get"])
def test_errors_are_mapped_and_private_failures_redacted(monkeypatch, error, status, method):
    def fail(**_):
        raise error

    monkeypatch.setattr(tasks, "create_task_manual_defect", fail)
    monkeypatch.setattr(tasks, "list_task_manual_defects", fail)
    http, audits = client(monkeypatch)
    result = http.post(PATH, json=payload()) if method == "post" else http.get(PATH)
    assert result.status_code == status
    assert "private patient detail" not in result.text
    assert audits == []
