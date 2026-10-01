"""人工缺陷审核 HTTP 合同：权限、状态码、脱敏 503（SQLite 合成数据，不连真实库）。"""

from __future__ import annotations

import json
from datetime import datetime, timedelta

import pytest
import sqlalchemy as sa
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database.models.qc import QCDefect, QCDefectHistory
from app.routers import manual_defect_reviews as routes
from app.services import manual_defect_review_service as service

LIST = "/api/v1/manual-defects"
BASE_TIME = datetime(2026, 9, 1, 8, 0, 0)


def review_path(defect_id: str) -> str:
    return f"/api/v1/manual-defects/{defect_id}/review"


def _defect(
    defect_id, minutes, *, created_by="qc-1", review="pending", origin="manual", scene=None,
):
    return {
        "id": defect_id, "record_id": "record-a", "identity_version": 1,
        "source_key": "task_assigned_qc", "institute_id": "hospital-A",
        "patient_id": "patient", "visit_id": "visit", "rule_name": "合成规则",
        "description": "合成缺陷说明", "severity": "warning", "evidence": "合成证据",
        "status": "pending", "origin": origin,
        "scene": scene,
        "manual_review_status": review if origin == "manual" else None,
        "manual_created_by": created_by if origin == "manual" else None,
        "deduct_score": 0.0,
        "created_at": BASE_TIME + timedelta(minutes=minutes),
        "updated_at": BASE_TIME + timedelta(minutes=minutes),
    }


@pytest.fixture
def sessions(monkeypatch):
    engine = sa.create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool,
    )
    QCDefect.__table__.create(engine)
    QCDefectHistory.__table__.create(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    with factory.begin() as session:
        session.execute(QCDefect.__table__.insert(), [
            _defect("m-1", 1, scene="running"),
            _defect("m-2", 2, scene="final"),
            _defect("m-3", 3, scene="outpatient_emergency"),
            _defect("m-own", 4, created_by="mgr-1"),
            _defect("m-done", 5, review="approved"),
            _defect("auto-1", 6, origin="auto"),
        ])
        session.execute(QCDefectHistory.__table__.insert(), [
            {"id": f"h-{i}", "defect_id": i, "action": "manual_create",
             "actor_id": "mgr-1" if i == "m-own" else "qc-1",
             "details": json.dumps({"task_id": "task-1", "task_record_id": "record-a",
                                    "run_number": 3, "job_id": "job-3"}),
             "created_at": BASE_TIME}
            for i in ("m-1", "m-2", "m-3", "m-own", "m-done")
        ])
    monkeypatch.setattr(service, "SessionLocal", factory)
    yield factory
    engine.dispose()


def client(monkeypatch, *, user_id="mgr-1", roles=("qc_manager",)):
    app = FastAPI()
    app.include_router(routes.router)
    app.dependency_overrides[routes.get_current_user] = lambda: {
        "id": user_id, "roles": list(roles),
    }
    audits = []
    monkeypatch.setattr(routes, "audit_event", lambda *a, **kw: audits.append(kw))
    return TestClient(app), audits


def _status(factory, defect_id):
    with factory() as session:
        return session.execute(sa.select(QCDefect.manual_review_status).where(
            QCDefect.id == defect_id)).scalar_one()


def test_approve_and_reject_flow(sessions, monkeypatch):
    http, audits = client(monkeypatch)
    ok = http.post(review_path("m-1"), json={"decision": "approved",
                                             "expected_status": "pending"})
    assert ok.status_code == 200
    data = ok.json()["data"]
    assert data["id"] == "m-1" and data["manual_review_status"] == "approved"
    assert data["previous_status"] == "pending" and data["reviewer_id"] == "mgr-1"
    assert audits[-1]["action"] == "manual_defects.review"
    assert "patient" not in str(audits)

    missing_reason = http.post(review_path("m-2"), json={
        "decision": "rejected", "reason": "   ", "expected_status": "pending"})
    assert missing_reason.status_code == 422
    assert _status(sessions, "m-2") == "pending"
    rejected = http.post(review_path("m-2"), json={
        "decision": "rejected", "reason": "证据不足", "expected_status": "pending"})
    assert rejected.status_code == 200
    assert _status(sessions, "m-2") == "rejected"


def test_request_body_is_strict(sessions, monkeypatch):
    http, _ = client(monkeypatch)
    for body in ({}, {"decision": "approved"},
                 {"decision": "pending", "expected_status": "pending"},
                 {"decision": "approved", "expected_status": "approved"},
                 {"decision": "approved", "expected_status": "pending", "extra": 1}):
        assert http.post(review_path("m-1"), json=body).status_code == 422
    assert _status(sessions, "m-1") == "pending"


def test_self_review_forbidden(sessions, monkeypatch):
    http, _ = client(monkeypatch)
    res = http.post(review_path("m-own"), json={"decision": "approved",
                                                "expected_status": "pending"})
    assert res.status_code == 403
    assert _status(sessions, "m-own") == "pending"


def test_without_review_permission_forbidden(sessions, monkeypatch):
    http, _ = client(monkeypatch, user_id="qc-2", roles=("qc_staff",))
    assert http.get(LIST).status_code == 403
    res = http.post(review_path("m-1"), json={"decision": "approved",
                                              "expected_status": "pending"})
    assert res.status_code == 403
    # 无权限时不泄露存在性：不存在的 id 同样 403
    assert http.post(review_path("nope"), json={
        "decision": "approved", "expected_status": "pending"}).status_code == 403
    assert _status(sessions, "m-1") == "pending"


@pytest.mark.parametrize("defect_id", ["auto-1", "does-not-exist"])
def test_non_manual_or_missing_is_404(sessions, monkeypatch, defect_id):
    http, _ = client(monkeypatch)
    res = http.post(review_path(defect_id), json={"decision": "approved",
                                                  "expected_status": "pending"})
    assert res.status_code == 404
    assert res.json()["detail"] == "人工缺陷不存在"


def test_second_review_is_409_not_pending(sessions, monkeypatch):
    http, _ = client(monkeypatch)
    body = {"decision": "approved", "expected_status": "pending"}
    assert http.post(review_path("m-3"), json=body).status_code == 200
    again = http.post(review_path("m-3"), json=body)
    assert again.status_code == 409
    assert again.json()["detail"]["code"] == "not_pending"
    assert http.post(review_path("m-done"), json=body).status_code == 409


def test_list_filters_total_pagination_and_task_fields(sessions, monkeypatch):
    http, _ = client(monkeypatch)
    res = http.get(LIST, params={"review_status": "pending", "page": 1, "page_size": 2})
    assert res.status_code == 200
    data = res.json()["data"]
    assert data["total"] == 4 and data["page"] == 1 and data["page_size"] == 2
    assert data["scene"] == "all"
    assert [i["id"] for i in data["items"]] == ["m-own", "m-3"]
    item = data["items"][1]
    assert (item["task_id"], item["task_record_id"], item["run_number"]) == (
        "task-1", "record-a", 3)
    assert "evidence" not in item and "status" not in item
    page3 = http.get(LIST, params={"page": 3, "page_size": 2}).json()["data"]
    assert page3["items"] == [] and page3["total"] == 4
    approved = http.get(LIST, params={"review_status": "approved"}).json()["data"]
    assert [i["id"] for i in approved["items"]] == ["m-done"]
    assert http.get(LIST, params={"page_size": 101}).status_code == 422
    assert http.get(LIST, params={"review_status": "all"}).status_code == 422
    assert http.get(LIST, params={"page": 0}).status_code == 422


def test_count_matches_list_pending_total(sessions, monkeypatch):
    http, _ = client(monkeypatch)
    total = http.get(LIST).json()["data"]["total"]
    assert routes.count_pending_manual_defects() == total == 4


def test_list_and_count_use_same_scene_and_response_echoes_it(sessions, monkeypatch):
    http, _ = client(monkeypatch)
    data = http.get(LIST, params={"scene": "running"}).json()["data"]
    assert data["scene"] == "running"
    assert data["total"] == 1
    assert [item["id"] for item in data["items"]] == ["m-1"]
    assert routes.count_pending_manual_defects(scene="running") == data["total"]
    assert http.get(LIST, params={"scene": "outpatient"}).status_code == 422


def test_database_errors_are_sanitized_503(monkeypatch):
    engine = sa.create_engine("sqlite://", poolclass=StaticPool)  # 空库：SQL 必然失败
    monkeypatch.setattr(service, "SessionLocal", sessionmaker(bind=engine))
    http, _ = client(monkeypatch)
    for res in (
        http.get(LIST),
        http.post(review_path("m-1"), json={"decision": "approved",
                                            "expected_status": "pending"}),
    ):
        assert res.status_code == 503
        text = res.text
        assert "qc_defects" not in text and "no such table" not in text.lower()
        assert res.json()["detail"] == "人工缺陷审核服务暂不可用，请稍后重试"

    def unexpected(**kwargs):
        raise RuntimeError("SELECT secret FROM qc_defects")

    monkeypatch.setattr(routes, "review_manual_defect", unexpected)
    res = http.post(review_path("m-1"), json={"decision": "approved",
                                              "expected_status": "pending"})
    assert res.status_code == 503 and "secret" not in res.text


CASE = "/api/v1/manual-defects/case"
CASE_PARAMS = {"institute_id": "hospital-A", "patient_id": "patient", "visit_id": "visit"}


def test_case_http_pagination_keeps_exact_scope(sessions, monkeypatch):
    http, _ = client(monkeypatch)
    result = http.get(CASE, params={**CASE_PARAMS, "offset": 2, "limit": 2})
    assert result.status_code == 200
    data = result.json()["data"]
    assert data["total"] == 5 and data["offset"] == 2 and data["limit"] == 2
    assert [row["id"] for row in data["items"]] == ["m-3", "m-2"]
    for params in ({"offset": -1}, {"limit": 201}, {"limit": 0}):
        assert http.get(CASE, params={**CASE_PARAMS, **params}).status_code == 422


def test_case_list_returns_all_review_states_for_exact_identity(sessions, monkeypatch):
    """按三坐标读取全部审核状态的人工缺陷；自动缺陷与其他病例不出现，total 精确。"""
    with sessions.begin() as session:
        other = _defect("m-other", 7)
        other["institute_id"] = "hospital-B"  # 同患者/就诊号、不同机构
        session.execute(QCDefect.__table__.insert(), [other])
    http, _ = client(monkeypatch)
    res = http.get(CASE, params=CASE_PARAMS)
    assert res.status_code == 200
    data = res.json()["data"]
    assert data["total"] == 5 and data["limit"] == 200
    assert [i["id"] for i in data["items"]] == ["m-done", "m-own", "m-3", "m-2", "m-1"]
    assert {i["manual_review_status"] for i in data["items"]} == {"pending", "approved"}
    assert all(i["institute_id"] == "hospital-A" for i in data["items"])
    assert data["items"][0]["task_id"] == "task-1"


@pytest.mark.parametrize(
    ("scene", "expected_id"),
    [("running", "m-1"), ("final", "m-2"), ("outpatient_emergency", "m-3")],
)
def test_case_list_filters_same_identity_by_scene(sessions, monkeypatch, scene, expected_id):
    http, _ = client(monkeypatch)
    res = http.get(CASE, params={**CASE_PARAMS, "scene": scene})
    assert res.status_code == 200
    data = res.json()["data"]
    assert data["total"] == 1
    assert [item["id"] for item in data["items"]] == [expected_id]


def test_case_list_requires_review_permission_and_identity(sessions, monkeypatch):
    http, _ = client(monkeypatch, user_id="qc-2", roles=("qc_staff",))
    assert http.get(CASE, params=CASE_PARAMS).status_code == 403
    http, _ = client(monkeypatch)
    assert http.get(CASE, params={**CASE_PARAMS, "visit_id": ""}).status_code == 422
    assert http.get(CASE, params={"institute_id": "hospital-A"}).status_code == 422
    assert http.get(CASE, params={**CASE_PARAMS, "patient_id": " patient"}).status_code == 422


def test_case_list_database_error_is_sanitized_503(monkeypatch):
    engine = sa.create_engine("sqlite://", poolclass=StaticPool)
    monkeypatch.setattr(service, "SessionLocal", sessionmaker(bind=engine))
    http, _ = client(monkeypatch)
    res = http.get(CASE, params=CASE_PARAMS)
    assert res.status_code == 503
    assert "qc_defects" not in res.text
