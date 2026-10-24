"""V5 审核待办独立于旧版全院统计，沿用审核所有者的权限与场景。"""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.routers import dashboard_api, record_reviews
from app.services import manual_defect_review_service


PATH = "/api/v1/dashboard/review-todo-stats"


@pytest.fixture
def env(monkeypatch):
    calls = {"records": [], "manual": []}

    def records(actor_id, scene):
        calls["records"].append((actor_id, scene))
        return {"initial": 3, "recheck": 2}

    def manual(*, scene, actor_id):
        assert actor_id == "reviewer"
        calls["manual"].append(scene)
        return 4

    def legacy(*_args, **_kwargs):
        pytest.fail("审核待办不得读取旧版全院统计或 qc_results 的旧字段")

    monkeypatch.setattr(record_reviews, "count_my_record_review_todos", records)
    monkeypatch.setattr(manual_defect_review_service, "count_pending_manual_defects", manual)
    monkeypatch.setattr(dashboard_api, "_get_db_stats_by_scene", legacy)
    monkeypatch.setattr(dashboard_api, "get_supabase", legacy)
    return calls


def client(user=None):
    app = FastAPI()
    app.include_router(dashboard_api.router)
    app.dependency_overrides[dashboard_api.get_current_user] = lambda: (
        user if user is not None else {"id": "reviewer", "roles": ["qc_manager"]}
    )
    return TestClient(app)


@pytest.mark.parametrize("scene", ["all", "running", "final", "outpatient_emergency"])
def test_review_counts_do_not_depend_on_legacy_statistics(env, scene):
    response = client().get(PATH, params={"scene": scene})
    assert response.status_code == 200
    assert response.json()["data"] == {
        "record_stats": {"pending_review": 3, "pending_recheck": 2},
        "defect_stats": {"pending_review": 4},
        "scene": scene,
    }
    assert env == {"records": [("reviewer", scene)], "manual": [scene]}


def test_manual_review_requires_existing_review_permission(env):
    response = client({"id": "staff", "roles": ["qc_staff"]}).get(PATH)
    assert response.status_code == 200
    assert response.json()["data"]["defect_stats"]["pending_review"] is None
    assert env == {"records": [("staff", "all")], "manual": []}


def test_unavailable_record_source_preserves_manual_counts(env, monkeypatch):
    monkeypatch.setattr(record_reviews, "count_my_record_review_todos", lambda *_: {
        "initial": None, "recheck": None, "unavailable_reason": "review_source_unavailable",
    })
    response = client().get(PATH)
    assert response.status_code == 200
    assert response.json()["data"] == {
        "record_stats": {
            "pending_review": None, "pending_recheck": None,
            "unavailable_reason": "review_source_unavailable",
        },
        "defect_stats": {"pending_review": 4},
        "scene": "all",
    }


@pytest.mark.parametrize("source", ["records", "manual"])
def test_owner_failure_remains_redacted_503(env, monkeypatch, source):
    def failed(*_args, **_kwargs):
        raise RuntimeError("SELECT private_column FROM private_table")

    if source == "records":
        monkeypatch.setattr(record_reviews, "count_my_record_review_todos", failed)
    else:
        monkeypatch.setattr(manual_defect_review_service, "count_pending_manual_defects", failed)
    response = client().get(PATH)
    assert response.status_code == 503
    assert response.json()["detail"] == "待办统计暂不可用，请稍后重试"
    assert "private" not in response.text


def test_missing_identity_is_rejected_before_owner_reads(env):
    assert client({"roles": ["qc_manager"]}).get(PATH).status_code == 401
    assert env == {"records": [], "manual": []}


@pytest.mark.parametrize("scene", ["outpatient", "", "RUNNING"])
def test_invalid_scene_is_rejected_before_owner_reads(env, scene):
    assert client().get(PATH, params={"scene": scene}).status_code == 422
    assert env == {"records": [], "manual": []}
