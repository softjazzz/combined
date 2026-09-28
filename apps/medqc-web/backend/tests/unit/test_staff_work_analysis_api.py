"""质控员工作分析 HTTP 合同；服务替换为内存桩。"""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.security import get_current_user
from app.routers import staff_work_analysis as routes
from app.services import staff_work_analysis_service as service


BASE = "/api/v1/quality-reports/staff-work"


def _client(roles=("qc_manager",)) -> TestClient:
    app = FastAPI()
    app.include_router(routes.router)
    app.dependency_overrides[get_current_user] = lambda: {"id": "qc-1", "roles": list(roles)}
    return TestClient(app)


def test_authorized_request_passes_period_and_scene(monkeypatch):
    captured = {}
    expected = {
        "period": "last_week", "scene": "all", "summary": {"record_review_count": 3},
        "staff": [{"user_id": "qc-1", "record_review_count": 3}], "unavailable_reason": None,
        "unavailable_metrics": {},
    }

    def get_analysis(**kwargs):
        captured.update(kwargs)
        return expected

    monkeypatch.setattr(service, "get_staff_work_analysis", get_analysis)
    response = _client().get(BASE, params={"period": "last_week", "scene": "all"})
    assert response.status_code == 200
    assert response.json()["data"] == expected
    assert captured == {"period": "last_week", "scene": "all"}


def test_scene_unavailable_contract_preserves_nulls(monkeypatch):
    monkeypatch.setattr(service, "get_staff_work_analysis", lambda **_kwargs: {
        "period": "this_week", "scene": "final", "summary": None, "staff": None,
        "unavailable_reason": "scene_not_attributable",
    })
    response = _client().get(BASE, params={"scene": "final"})
    assert response.status_code == 200
    assert response.json()["data"]["staff"] is None
    assert response.json()["data"]["unavailable_reason"] == "scene_not_attributable"


def test_scene_field_level_unknown_contract_preserves_real_rows(monkeypatch):
    expected = {
        "period": "this_week", "scene": "running",
        "summary": {"record_review_count": 2, "appeal_approved_count": None,
                    "appeal_rejected_count": None},
        "staff": [{"user_id": "qc-1", "record_review_count": 2,
                  "appeal_approved_count": None, "appeal_rejected_count": None}],
        "unavailable_reason": None,
        "unavailable_metrics": {
            "appeal_approved_count": "scene_not_attributable",
            "appeal_rejected_count": "scene_not_attributable",
        },
    }
    monkeypatch.setattr(service, "get_staff_work_analysis", lambda **_kwargs: expected)
    response = _client().get(BASE, params={"scene": "running"})
    assert response.status_code == 200
    assert response.json()["data"] == expected


@pytest.mark.parametrize("roles", [("doctor",), ("qc_staff",), ()])
def test_non_manager_roles_are_forbidden_before_read(monkeypatch, roles):
    monkeypatch.setattr(service, "get_staff_work_analysis", lambda **_kwargs: pytest.fail("不应读取分析"))
    assert _client(roles).get(BASE).status_code == 403


@pytest.mark.parametrize("params", [{"period": "next_week"}, {"scene": "outpatient_emergency"}])
def test_invalid_query_is_422(params):
    assert _client().get(BASE, params=params).status_code == 422


def test_service_invalid_is_422(monkeypatch):
    monkeypatch.setattr(service, "get_staff_work_analysis", lambda **_kwargs: (_ for _ in ()).throw(
        service.StaffWorkAnalysisInvalid("时间范围无效")
    ))
    assert _client().get(BASE).status_code == 422


def test_read_failure_is_redacted(monkeypatch):
    monkeypatch.setattr(service, "get_staff_work_analysis", lambda **_kwargs: (_ for _ in ()).throw(
        RuntimeError("patient P001 SQL secret")
    ))
    response = _client().get(BASE)
    assert response.status_code == 503
    assert response.json()["detail"] == "质控员工作分析暂不可用，请稍后重试"
    assert "P001" not in response.text and "secret" not in response.text
