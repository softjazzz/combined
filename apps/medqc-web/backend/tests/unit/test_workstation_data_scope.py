from __future__ import annotations

import pytest
from fastapi import HTTPException

from app.core.data_scope import resolve_workstation_data_scope

HOME_URL = "/api/v1/workstation/qc-home"
ANALYTICS_URL = "/api/v1/workstation/analytics/luxian-0609"
RESULT_URL = "/api/v1/workstation/qc-result-analysis/luxian-0609?care_phase=discharged"
HEADERS = {"Authorization": "Bearer test-token"}


# ---------------------------------------------------------------------------
# 范围解析
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("role", ["admin", "qc_manager", "sync_admin", "super_admin"])
def test_full_scope_roles_keep_requested_department(role):
    scope = resolve_workstation_data_scope({"roles": [role]}, " 心内科 ")
    assert scope.hospital_scope == "all"
    assert scope.department == "心内科"

    scope = resolve_workstation_data_scope({"roles": [role]}, None)
    assert scope.hospital_scope == "all"
    assert scope.department is None


def test_doctor_is_forced_to_own_department():
    user = {"roles": ["doctor"], "department": " 内科 "}
    scope = resolve_workstation_data_scope(user, None)
    assert scope.hospital_scope == "department"
    assert scope.department == "内科"
    assert resolve_workstation_data_scope(user, "内科").department == "内科"


def test_doctor_requesting_other_department_is_forbidden():
    with pytest.raises(HTTPException) as exc:
        resolve_workstation_data_scope({"roles": ["doctor"], "department": "内科"}, "外科")
    assert exc.value.status_code == 403


@pytest.mark.parametrize("department", [None, "", "  "])
def test_doctor_without_department_fails_closed(department):
    with pytest.raises(HTTPException) as exc:
        resolve_workstation_data_scope({"roles": ["doctor"], "department": department}, None)
    assert exc.value.status_code == 403


@pytest.mark.parametrize("roles", [[], ["qc_staff"], ["reviewer"], ["coder"], None])
def test_other_roles_are_forbidden(roles):
    with pytest.raises(HTTPException) as exc:
        resolve_workstation_data_scope({"roles": roles, "department": "内科"}, None)
    assert exc.value.status_code == 403


def test_full_scope_wins_for_multi_role_user():
    scope = resolve_workstation_data_scope(
        {"roles": ["doctor", "qc_manager"], "department": "内科"}, "外科"
    )
    assert scope.hospital_scope == "all"
    assert scope.department == "外科"


# ---------------------------------------------------------------------------
# 接口接入
# ---------------------------------------------------------------------------


def _login_as(monkeypatch, user: dict) -> None:
    monkeypatch.setattr(
        "app.core.security._decode_token",
        lambda _token, expected_type=None: {"sub": "u-scope"},
    )
    monkeypatch.setattr(
        "app.core.security.resolve_user_by_subject",
        lambda _subject: {"id": "u-scope", **user},
    )


def _capture_services(monkeypatch) -> dict[str, dict]:
    captured: dict[str, dict] = {}

    def recorder(name):
        def _call(**kwargs):
            captured[name] = kwargs
            return {"scope": {}}

        return _call

    monkeypatch.setattr(
        "app.routers.workstation.default_workstation_aggregation_service.get_luxian_0609_home",
        recorder("home"),
    )
    monkeypatch.setattr(
        "app.routers.workstation.default_workstation_aggregation_service.get_luxian_0609_analytics",
        recorder("analytics"),
    )
    monkeypatch.setattr(
        "app.routers.workstation.default_luxian_0609_result_analysis_service.get_analysis",
        recorder("result"),
    )
    return captured


def test_endpoints_force_doctor_department(client, monkeypatch):
    _login_as(monkeypatch, {"roles": ["doctor"], "department": "内科"})
    captured = _capture_services(monkeypatch)

    for url in (HOME_URL, ANALYTICS_URL, RESULT_URL):
        assert client.get(url, headers=HEADERS).status_code == 200

    assert captured["home"]["department"] == "内科"
    assert captured["home"]["hospital_scope"] == "department"
    assert captured["analytics"]["department"] == "内科"
    assert captured["analytics"]["hospital_scope"] == "department"
    assert captured["result"]["department"] == "内科"


def test_endpoints_reject_doctor_requesting_other_department(client, monkeypatch):
    _login_as(monkeypatch, {"roles": ["doctor"], "department": "内科"})
    captured = _capture_services(monkeypatch)

    for url in (HOME_URL, ANALYTICS_URL, RESULT_URL):
        joiner = "&" if "?" in url else "?"
        response = client.get(f"{url}{joiner}department=%E5%A4%96%E7%A7%91", headers=HEADERS)
        assert response.status_code == 403
    assert captured == {}


@pytest.mark.parametrize(
    "user",
    [
        {"roles": ["qc_staff"], "department": "质控科"},
        {"roles": ["reviewer"]},
        {"roles": ["doctor"], "department": ""},
    ],
)
def test_endpoints_forbid_users_without_scope(client, monkeypatch, user):
    _login_as(monkeypatch, user)
    captured = _capture_services(monkeypatch)

    for url in (HOME_URL, ANALYTICS_URL, RESULT_URL):
        assert client.get(url, headers=HEADERS).status_code == 403
    assert captured == {}


def test_endpoints_keep_full_scope_for_qc_manager(client, monkeypatch):
    _login_as(monkeypatch, {"roles": ["qc_manager"], "department": "质控科"})
    captured = _capture_services(monkeypatch)

    for url in (HOME_URL, ANALYTICS_URL, RESULT_URL):
        assert client.get(url, headers=HEADERS).status_code == 200

    assert captured["home"]["department"] is None
    assert captured["home"]["hospital_scope"] == "all"
    assert captured["analytics"]["hospital_scope"] == "all"
    assert captured["result"]["department"] is None
