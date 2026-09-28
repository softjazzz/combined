"""工作表现排名 HTTP 合同：响应结构、period 422、场景不可用、脱敏 503、无示例数据（SQLite 合成数据）。"""

from __future__ import annotations

from functools import partial

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.exc import OperationalError

from app.database.models.qc import QCDefect, QCDefectHistory, QCRecordReview
from app.routers import dashboard_api as routes
from app.services import performance_ranking_service as service
from tests.unit.test_performance_ranking_service import NOW, build_env

PATH = "/api/v1/dashboard/performance"
_SAMPLE_NAMES = ("王质控", "张质控", "李质控", "赵质控", "陈质控")


@pytest.fixture
def env(monkeypatch):
    engine, _factory = build_env(monkeypatch)
    monkeypatch.setattr(
        routes, "get_performance_ranking_data", partial(service.get_performance_ranking, now=NOW),
    )
    yield engine
    engine.dispose()


def client(roles=("qc_manager",)):
    app = FastAPI()
    app.include_router(routes.router)
    app.dependency_overrides[routes.get_current_user] = lambda: {"id": "u-a", "roles": list(roles)}
    return TestClient(app)


def test_response_shape(env):
    res = client().get(PATH, params={"period": "this_week"})
    assert res.status_code == 200
    data = res.json()["data"]
    assert set(data) == {
        "period", "period_label", "range", "scene",
        "defect_ranking", "record_ranking", "unavailable_reason",
    }
    assert data["period"] == "this_week" and data["period_label"] == "本周"
    assert data["scene"] == "all" and data["unavailable_reason"] is None
    assert data["range"]["start"].endswith("+08:00") and data["range"]["end"].endswith("+08:00")
    assert set(data["record_ranking"][0]) == {
        "user_id", "name", "count", "initial_count", "recheck_count", "rank",
    }
    assert set(data["defect_ranking"][0]) == {
        "user_id", "name", "count", "approved_count", "rejected_count", "rank",
    }


@pytest.mark.parametrize("period", ["recent_7_days", "", "month"])
def test_invalid_period_is_422(env, period):
    assert client().get(PATH, params={"period": period}).status_code == 422


def test_non_all_scene_returns_record_ranking_only(env):
    data = client().get(PATH, params={"scene": "running"}).json()["data"]
    assert data["defect_ranking"] is None and isinstance(data["record_ranking"], list)
    assert data["unavailable_reason"] == "scene_not_attributable"


@pytest.mark.parametrize("role", ["admin", "qc_manager", "qc_staff"])
def test_statistics_roles_can_read_performance(env, role):
    assert client((role,)).get(PATH).status_code == 200


def test_doctor_cannot_read_performance(monkeypatch):
    monkeypatch.setattr(
        routes,
        "get_performance_ranking_data",
        lambda **_kwargs: pytest.fail("权限拒绝后不得读取排名数据"),
    )
    response = client(("doctor",)).get(PATH)
    assert response.status_code == 403


def test_database_failure_is_sanitized_503(env, monkeypatch):
    def boom(*_args, **_kwargs):
        raise OperationalError("SELECT secret_column FROM qc_record_reviews", {}, Exception("pwd"))

    monkeypatch.setattr(service, "_record_ranking", boom)
    res = client().get(PATH)
    assert res.status_code == 503
    body = res.text
    assert "secret_column" not in body and "pwd" not in body and "qc_record_reviews" not in body
    assert res.json()["detail"] == routes._PERFORMANCE_UNAVAILABLE_DETAIL
    assert not any(name in body for name in _SAMPLE_NAMES)


def test_missing_session_is_503_not_sample_data(monkeypatch):
    monkeypatch.setattr(service, "SessionLocal", None)
    res = client().get(PATH)
    assert res.status_code == 503
    assert not any(name in res.text for name in _SAMPLE_NAMES)


def test_empty_database_returns_empty_arrays(monkeypatch):
    engine, factory = build_env(monkeypatch)
    with factory.begin() as session:
        for model in (QCRecordReview, QCDefectHistory, QCDefect):
            session.execute(model.__table__.delete())
    data = client().get(PATH).json()["data"]
    engine.dispose()
    assert data["defect_ranking"] == [] and data["record_ranking"] == []
    assert data["unavailable_reason"] is None
