"""旧评分阈值写接口需要 admin/qc_manager；其他登录角色 403，且不触达存储。"""

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.routers import scoring_config as routes


def _client(roles):
    app = FastAPI()
    app.include_router(routes.router)
    app.dependency_overrides[routes.get_current_user] = lambda: {"id": "u-1", "roles": list(roles)}
    return TestClient(app)


def test_non_manager_cannot_update_scoring_config(monkeypatch):
    touched = []
    monkeypatch.setattr(routes, "_ensure_db", lambda: touched.append("db") or (_ for _ in ()).throw(AssertionError("不应访问存储")))
    for roles in (("qc_staff",), ("doctor",), ()):
        response = _client(roles).put(routes.router.prefix, json={"grade_a_threshold": 90})
        assert response.status_code == 403, roles
    assert touched == []
