"""
数据同步路由单元测试（PG-only）。
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from threading import Event, Lock

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.core.access_control import enforce_default_auth
from app.core.security import get_current_user
from app.routers import sync as sync_router_module
from app.services import sync_idempotency
from app.services.sync_idempotency import SyncTriggerReservation


def _assert_success_shell(body: dict) -> dict:
    assert body["success"] is True
    assert isinstance(body.get("trace_id"), str) and body["trace_id"]
    assert "data" in body
    return body["data"]


def _assert_error_shell(body: dict, expected_code: str | None = None) -> None:
    assert body["success"] is False
    assert isinstance(body.get("trace_id"), str) and body["trace_id"]
    assert isinstance(body.get("error"), str) and body["error"]
    if expected_code:
        assert body.get("code") == expected_code


def _override_user(
    client,
    roles: list[str],
    *,
    email: str = "sync@test.local",
) -> None:
    user = {
        "id": f"u-{email.split('@', maxsplit=1)[0]}",
        "email": email,
        "display_name": "Sync Tester",
        "department": "信息科",
        "roles": roles,
    }
    client.app.dependency_overrides[get_current_user] = lambda: user


@pytest.fixture(autouse=True)
def _clear_dependency_overrides(client):
    async def _noop_auth_gate():
        return None

    client.app.dependency_overrides[enforce_default_auth] = _noop_auth_gate
    yield
    client.app.dependency_overrides.clear()


@pytest.mark.unit
@pytest.mark.api
class TestSyncRouter:
    def test_builtin_sync_admin_login_success(self, client):
        response = client.post(
            "/api/v1/auth/login",
            json={"email": "sync_admin@medqc.com", "password": "sync888"},
        )

        assert response.status_code == 200
        login_data = response.json()
        assert login_data["access_token"]

        me_response = client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {login_data['access_token']}"},
        )
        assert me_response.status_code == 200
        me_data = me_response.json()
        assert me_data["email"] == "sync_admin@medqc.com"
        assert me_data["roles"] == ["sync_admin"]

    def test_read_permission_matrix(self, client, monkeypatch):
        monkeypatch.setattr(
            "app.services.etl_sync.get_sync_state",
            lambda: {"is_running": False, "logs": [], "total_records_synced": 0},
        )

        _override_user(client, ["admin"])
        assert client.get("/api/v1/sync/status").status_code == 200

        _override_user(client, ["qc_manager"])
        assert client.get("/api/v1/sync/status").status_code == 200

        _override_user(client, ["sync_admin"])
        assert client.get("/api/v1/sync/status").status_code == 200

        _override_user(client, ["super_admin"])
        assert client.get("/api/v1/sync/status").status_code == 200

        _override_user(client, ["doctor"])
        assert client.get("/api/v1/sync/status").status_code == 403

    def test_write_permission_matrix(self, client, monkeypatch):
        monkeypatch.setattr("app.services.etl_sync.test_remote_connection", lambda: {"connected": True})
        monkeypatch.setattr("app.services.etl_sync.test_local_connection", lambda: {"connected": True})
        monkeypatch.setattr(
            "app.services.etl_sync.validate_pg_sync_plan",
            lambda tables=None, include_disabled=False: {
                "mode": "table",
                "remote_schema": "public",
                "blockers": [],
                "warnings": [],
                "table_validations": [],
                "target_tables": [],
                "matrix_scope": "enabled" if not include_disabled else "all",
            },
        )
        monkeypatch.setattr(
            "app.services.etl_sync.estimate_pg_sync_impact",
            lambda **kwargs: {"estimated_impact": 1, "estimate_basis": "eligible_visit_count"},
        )

        _override_user(client, ["qc_manager"])
        resp = client.post("/api/v1/sync/preflight", json={"source": "pg", "tier": "all"})
        assert resp.status_code == 403
        resp = client.put("/api/v1/sync/config/policy", json={})
        assert resp.status_code == 403

        _override_user(client, ["sync_admin"])
        resp = client.post("/api/v1/sync/preflight", json={"source": "pg", "tier": "all"})
        assert resp.status_code == 200

        _override_user(client, ["super_admin"])
        resp = client.post("/api/v1/sync/preflight", json={"source": "pg", "tier": "all"})
        assert resp.status_code == 200

    def test_get_status_and_statistics(self, client, monkeypatch):
        _override_user(client, ["admin"])
        monkeypatch.setattr(
            "app.services.etl_sync.get_sync_state",
            lambda: {
                "is_running": True,
                "last_sync_status": "partial",
                "total_records_synced": 123,
                "logs": [
                    {"status": "success"},
                    {"status": "failed"},
                ],
            },
        )

        status_resp = client.get("/api/v1/sync/status")
        assert status_resp.status_code == 200
        status_data = _assert_success_shell(status_resp.json())
        assert status_data["pg_sync"]["is_running"] is True

        stats_resp = client.get("/api/v1/sync/statistics")
        assert stats_resp.status_code == 200
        stats_data = _assert_success_shell(stats_resp.json())
        assert stats_data["PENDING"] == 1
        assert stats_data["PARTIAL"] == 1
        assert stats_data["SYNCED"] == 123
        assert stats_data["FAILED"] == 1

    def test_update_pg_config(self, client, monkeypatch):
        _override_user(client, ["admin"])
        base_cfg = {
            "remote_host": "127.0.0.1",
            "remote_port": "5432",
            "remote_database": "dhc-app",
            "remote_username": "tester",
            "remote_password": "secret",
            "remote_schema": "public",
            "default_institute_id": "LOCAL-HOSPITAL",
            "sync_mode": "table",
        }
        saved_holder: dict[str, object] = {}
        audit_calls: list[dict] = []

        monkeypatch.setattr("app.services.etl_sync.load_db_config", lambda: dict(base_cfg))
        monkeypatch.setattr("app.services.etl_sync.test_remote_connection", lambda: {"connected": True, "error": ""})
        monkeypatch.setattr(
            "app.routers.sync.audit_event",
            lambda _request, **kwargs: audit_calls.append(kwargs),
        )

        def _fake_save_db_config(cfg, runtime_password=None):
            saved_holder["value"] = dict(cfg)
            saved_holder["runtime_password"] = runtime_password
            return dict(cfg)

        monkeypatch.setattr("app.services.etl_sync.save_db_config", _fake_save_db_config)

        resp = client.put(
            "/api/v1/sync/config/pg",
            json={
                "remote_host": "10.10.10.8",
                "remote_port": 5433,
                "remote_password": "",
                "default_institute_id": "HOSPITAL-A",
            },
        )
        assert resp.status_code == 200
        data = _assert_success_shell(resp.json())
        assert saved_holder["value"]["remote_host"] == "10.10.10.8"
        assert saved_holder["value"]["remote_port"] == "5433"
        assert saved_holder["value"]["default_institute_id"] == "HOSPITAL-A"
        assert saved_holder["value"]["remote_password"] == "secret"
        assert saved_holder["runtime_password"] is None
        assert data["config"]["remote_password_set"] is True
        assert any(call.get("action") == "sync.config.pg.update" for call in audit_calls)

    def test_pg_config_exposes_placeholder_as_unconfigured(self, client, monkeypatch):
        _override_user(client, ["sync_admin"])
        monkeypatch.setattr(
            "app.services.etl_sync.load_db_config",
            lambda: {
                "remote_schema": "public",
                "default_institute_id": "LOCAL-HOSPITAL",
            },
        )

        response = client.get("/api/v1/sync/config/pg")

        assert response.status_code == 200
        data = _assert_success_shell(response.json())
        assert data["default_institute_id"] == ""
        assert data["default_institute_configured"] is False

    def test_update_pg_config_rejects_placeholder_institute(self, client, monkeypatch):
        _override_user(client, ["sync_admin"])
        save_calls: list[dict] = []
        monkeypatch.setattr(
            "app.services.etl_sync.load_db_config",
            lambda: {
                "remote_schema": "public",
                "default_institute_id": "LOCAL-HOSPITAL",
            },
        )
        monkeypatch.setattr(
            "app.services.etl_sync.save_db_config",
            lambda cfg, runtime_password=None: save_calls.append(dict(cfg)),
        )

        response = client.put(
            "/api/v1/sync/config/pg",
            json={"default_institute_id": "LOCAL-HOSPITAL"},
        )

        assert response.status_code == 422
        assert save_calls == []

    def test_sync_policy_get_and_update(self, client, monkeypatch):
        _override_user(client, ["admin"])
        monkeypatch.setattr(
            "app.services.sync_policy.load_sync_policy",
            lambda: {
                "scope": "both",
                "target_departments": ["*"],
                "start_date": "",
                "end_date": "",
                "schedule": {"mode": "interval", "minutes": 30},
                "night_window": {"start": "22:00", "end": "06:00"},
                "mirror_delay_base_minutes": 30,
                "policy_version": "policy-legacy-v1",
            },
        )

        captured: dict[str, object] = {}

        def _fake_save(payload, keep_policy_version=False):
            captured["payload"] = payload
            captured["keep_policy_version"] = keep_policy_version
            return {
                "scope": payload.get("scope", "both"),
                "target_departments": payload.get("target_departments", ["*"]),
                "start_date": payload.get("start_date", ""),
                "end_date": payload.get("end_date", ""),
                "schedule": payload.get("schedule", {"mode": "interval", "minutes": 30}),
                "night_window": payload.get("night_window", {"start": "22:00", "end": "06:00"}),
                "mirror_delay_base_minutes": payload.get("mirror_delay_base_minutes", 30),
                "policy_version": "policy-20260415T000000Z",
            }

        monkeypatch.setattr("app.services.sync_policy.save_sync_policy", _fake_save)

        get_resp = client.get("/api/v1/sync/config/policy")
        assert get_resp.status_code == 200
        _assert_success_shell(get_resp.json())

        put_resp = client.put(
            "/api/v1/sync/config/policy",
            json={
                "scope": "final",
                "target_departments": ["骨科"],
                "schedule": {"mode": "interval", "minutes": 60},
                "keep_policy_version": False,
            },
        )
        assert put_resp.status_code == 200
        data = _assert_success_shell(put_resp.json())
        assert data["scope"] == "final"
        assert captured["keep_policy_version"] is False

    def test_departments_value_error_maps_422(self, client, monkeypatch):
        _override_user(client, ["admin"])
        monkeypatch.setattr(
            "app.services.etl_sync.list_remote_departments",
            lambda limit=500: (_ for _ in ()).throw(ValueError("远端 PG 未配置")),
        )
        resp = client.get("/api/v1/sync/departments")
        assert resp.status_code == 422
        body = resp.json()
        assert "远端 PG 未配置" in str(body.get("error", "") or body.get("detail", ""))

    def test_test_connection_all(self, client, monkeypatch):
        _override_user(client, ["admin"])
        monkeypatch.setattr("app.services.etl_sync.test_remote_connection", lambda: {"connected": True})
        monkeypatch.setattr("app.services.etl_sync.test_local_connection", lambda: {"connected": False})

        resp = client.post("/api/v1/sync/test-connection/all")
        assert resp.status_code == 200
        data = _assert_success_shell(resp.json())
        assert data["connected_count"] == 1
        assert data["all_connected"] is False

    def test_preflight_pg_success(self, client, monkeypatch):
        _override_user(client, ["admin"])
        monkeypatch.setattr("app.services.etl_sync.test_remote_connection", lambda: {"connected": True, "error": ""})
        monkeypatch.setattr("app.services.etl_sync.test_local_connection", lambda: {"connected": True, "error": ""})
        monkeypatch.setattr(
            "app.services.etl_sync.estimate_pg_sync_impact",
            lambda **_kwargs: {
                "estimated_impact": 7,
                "estimate_basis": "eligible_visit_count",
                "date_window": {"start": "2026-06-01", "end": "2026-06-02"},
                "target_departments": ["骨科"],
            },
        )
        monkeypatch.setattr(
            "app.services.etl_sync.validate_pg_sync_plan",
            lambda tables=None, include_disabled=False: {
                "mode": "table",
                "remote_schema": "public",
                "matrix_scope": "enabled" if not include_disabled else "all",
                "blockers": [],
                "warnings": [],
                "table_validations": [{"table": "mr", "executable": True, "blockers": []}],
                "target_tables": ["mr"],
            },
        )

        resp = client.post(
            "/api/v1/sync/preflight",
            json={
                "source": "pg",
                "tables": ["mr"],
                "date_window": {"start": "2026-06-01", "end": "2026-06-02"},
                "target_departments": ["骨科"],
            },
        )
        assert resp.status_code == 200
        data = _assert_success_shell(resp.json())
        assert data["source"] == "pg"
        assert data["executable"] is True
        assert data["estimated_impact"] == 7
        assert data["estimate_basis"] == "eligible_visit_count"
        assert data["date_window"] == {"start": "2026-06-01", "end": "2026-06-02"}
        assert data["target_departments"] == ["骨科"]
        assert isinstance(data["preflight_fingerprint"], str)
        assert len(data["preflight_fingerprint"]) == 64

    def test_preflight_pg_preserves_explicit_all_hospital_scope(self, client, monkeypatch):
        _override_user(client, ["admin"])
        captured = []
        monkeypatch.setattr(
            "app.services.etl_sync.test_remote_connection",
            lambda: {"connected": True, "error": ""},
        )
        monkeypatch.setattr(
            "app.services.etl_sync.test_local_connection",
            lambda: {"connected": True, "error": ""},
        )

        def _estimate(**kwargs):
            captured.append(kwargs)
            return {
                "estimated_impact": 42,
                "estimate_basis": "case_ref_count",
                "date_window": {"start": "2026-08-07", "end": "2026-08-13"},
                "target_departments": ["*"],
            }

        monkeypatch.setattr("app.services.etl_sync.estimate_pg_sync_impact", _estimate)
        monkeypatch.setattr(
            "app.services.etl_sync.validate_pg_sync_plan",
            lambda tables=None, include_disabled=False: {
                "mode": "table",
                "remote_schema": "public",
                "matrix_scope": "enabled" if not include_disabled else "all",
                "blockers": [],
                "warnings": [],
                "table_validations": [{"table": "mr", "executable": True, "blockers": []}],
                "target_tables": ["mr"],
            },
        )

        resp = client.post(
            "/api/v1/sync/preflight",
            json={
                "source": "pg",
                "tables": ["mr"],
                "date_window": {"start": "2026-08-07", "end": "2026-08-13"},
                "target_departments": ["*"],
            },
        )

        assert resp.status_code == 200
        data = _assert_success_shell(resp.json())
        assert data["target_departments"] == ["*"]
        assert captured[0]["target_departments"] == ["*"]

    def test_preflight_pg_zero_candidates_should_block_sync(self, client, monkeypatch):
        _override_user(client, ["admin"])
        monkeypatch.setattr("app.services.etl_sync.test_remote_connection", lambda: {"connected": True, "error": ""})
        monkeypatch.setattr("app.services.etl_sync.test_local_connection", lambda: {"connected": True, "error": ""})
        monkeypatch.setattr(
            "app.services.etl_sync.estimate_pg_sync_impact",
            lambda **_kwargs: {
                "estimated_impact": 0,
                "estimate_basis": "eligible_visit_count",
                "date_window": {"start": "2026-06-01", "end": "2026-06-02"},
                "target_departments": ["骨科"],
            },
        )
        monkeypatch.setattr(
            "app.services.etl_sync.validate_pg_sync_plan",
            lambda tables=None, include_disabled=False: {
                "mode": "table",
                "remote_schema": "public",
                "matrix_scope": "enabled" if not include_disabled else "all",
                "blockers": [],
                "warnings": [],
                "table_validations": [{"table": "mr", "executable": True, "blockers": []}],
                "target_tables": ["mr"],
            },
        )

        resp = client.post(
            "/api/v1/sync/preflight",
            json={
                "source": "pg",
                "tables": ["mr"],
                "date_window": {"start": "2026-06-01", "end": "2026-06-02"},
                "target_departments": ["骨科"],
            },
        )
        assert resp.status_code == 200
        data = _assert_success_shell(resp.json())
        assert data["executable"] is False
        assert data["estimated_impact"] == 0
        assert any("未找到可同步病历" in item for item in data["blockers"])
        assert any("候选病历数为 0" in item for item in data["warnings"])
        assert data["risk_level"] == "high"

    def test_preflight_running_scene_uses_authoritative_case_scope(self, client, monkeypatch):
        _override_user(client, ["admin"])
        monkeypatch.setattr("app.services.etl_sync.test_remote_connection", lambda: {"connected": True, "error": ""})
        monkeypatch.setattr("app.services.etl_sync.test_local_connection", lambda: {"connected": True, "error": ""})
        monkeypatch.setattr(
            "app.services.etl_sync.validate_pg_sync_plan",
            lambda tables=None, include_disabled=False: {
                "mode": "table",
                "remote_schema": "public",
                "matrix_scope": "enabled" if not include_disabled else "all",
                "blockers": [],
                "warnings": [],
                "table_validations": [{"table": "mr", "executable": True, "blockers": []}],
                "target_tables": ["mr"],
            },
        )
        impact_calls = []
        monkeypatch.setattr(
            "app.services.etl_sync.estimate_pg_sync_impact",
            lambda **kwargs: impact_calls.append(kwargs)
            or {
                "estimated_impact": 2,
                "estimate_basis": "case_ref_count",
                "date_window": {"end": "2026-07-31"},
                "target_departments": ["重症医学科(ICU)"],
            },
        )

        resp = client.post(
            "/api/v1/sync/preflight",
            json={
                "source": "pg",
                "tables": ["mr"],
                "scene": "running",
                "target_departments": ["重症医学科(ICU)"],
            },
        )
        assert resp.status_code == 200
        data = _assert_success_shell(resp.json())
        assert data["executable"] is True
        assert data["scene"] == "running"
        assert data["blockers"] == []
        assert data["estimated_impact"] == 2
        assert data["estimate_basis"] == "case_ref_count"
        assert data["risk_level"] == "low"
        assert impact_calls == [
            {
                "scene": "running",
                "date_window": None,
                "target_departments": ["重症医学科(ICU)"],
            }
        ]

    def test_trigger_rejects_stale_preflight_fingerprint(self, client, monkeypatch):
        _override_user(client, ["admin"])
        calls = {"run": 0}

        def _fake_run_sync(**_kwargs):
            calls["run"] += 1
            return {"success": True, "total_records": 1}

        monkeypatch.setattr("app.services.etl_sync.run_sync", _fake_run_sync)

        resp = client.post(
            "/api/v1/sync/trigger",
            json={
                "source": "pg",
                "tier": "all",
                "scene": "both",
                "date_window": {"start": "2026-06-01", "end": "2026-06-02"},
                "target_departments": ["骨科"],
                "preflight_fingerprint": "stale",
            },
        )
        assert resp.status_code == 409
        assert "预检结果已过期" in str(resp.json())
        assert calls["run"] == 0

    @pytest.mark.parametrize("scene", ("both", "frontpage"))
    def test_trigger_rejects_auto_qc_for_unsupported_scene_before_sync(
        self,
        client,
        monkeypatch,
        scene,
    ):
        _override_user(client, ["admin"])
        calls = {"run": 0}

        monkeypatch.setattr(
            "app.services.sync_idempotency.reserve_sync_trigger",
            lambda **_kwargs: SyncTriggerReservation(
                created=True,
                run_id="syncrun-invalid-auto-qc-scene",
                status="pending",
            ),
        )
        monkeypatch.setattr(
            "app.services.sync_idempotency.complete_sync_trigger",
            lambda **_kwargs: None,
        )
        monkeypatch.setattr(
            "app.services.sync_run_history.append_sync_run_record",
            lambda _record: None,
        )

        def _fake_run_sync(**_kwargs):
            calls["run"] += 1
            return {
                "success": False,
                "status": "failed",
                "scene": scene,
                "error": "不应执行同步",
            }

        monkeypatch.setattr("app.services.etl_sync.run_sync", _fake_run_sync)

        response = client.post(
            "/api/v1/sync/trigger",
            json={
                "source": "pg",
                "tier": "all",
                "scene": scene,
                "auto_qc_after_sync": True,
                "auto_qc_workflow_token": "workflow-invalid-scene",
            },
        )

        assert response.status_code == 422
        assert "自动质控" in str(response.json())
        assert calls["run"] == 0

    @pytest.mark.parametrize("workflow_token", (None, "short", "bad token"))
    def test_trigger_auto_qc_requires_valid_workflow_token_before_sync(
        self,
        client,
        monkeypatch,
        workflow_token,
    ):
        _override_user(client, ["admin"])
        calls = {"run": 0}
        monkeypatch.setattr(
            "app.services.etl_sync.run_sync",
            lambda **_kwargs: calls.__setitem__("run", calls["run"] + 1),
        )
        payload = {
            "source": "pg",
            "tier": "all",
            "scene": "running",
            "auto_qc_after_sync": True,
        }
        if workflow_token is not None:
            payload["auto_qc_workflow_token"] = workflow_token

        response = client.post("/api/v1/sync/trigger", json=payload)

        assert response.status_code == 422
        assert "流程标识" in str(response.json())
        assert calls["run"] == 0

    @pytest.mark.parametrize("role", ("admin", "qc_manager"))
    @pytest.mark.parametrize(
        "date_window",
        (
            None,
            {},
            {"start_date": "2026-08-01"},
            {"end_date": "2026-08-18"},
            {"start_date": " ", "end_date": "2026-08-18"},
        ),
    )
    def test_trigger_auto_final_requires_complete_explicit_date_window_before_sync(
        self,
        client,
        monkeypatch,
        role,
        date_window,
    ):
        _override_user(client, [role])
        monkeypatch.setattr(sync_router_module, "enforce_rate_limit", lambda *_args, **_kwargs: None)
        calls = {"run": 0}
        monkeypatch.setattr(
            "app.services.etl_sync.run_sync",
            lambda **_kwargs: calls.__setitem__("run", calls["run"] + 1),
        )
        payload = {
            "source": "pg",
            "tier": "all",
            "scene": "final",
            "auto_qc_after_sync": True,
            "auto_qc_workflow_token": "workflow-final-window-invalid",
        }
        if date_window is not None:
            payload["date_window"] = date_window

        response = client.post("/api/v1/sync/trigger", json=payload)

        assert response.status_code == 422
        assert "终末病历" in str(response.json())
        assert "日期范围" in str(response.json())
        assert calls["run"] == 0

    @pytest.mark.parametrize(
        ("role", "date_window", "expected_detail"),
        (
            (
                "admin",
                {"start_date": "2026-08-01", "end_date": "2026-09-01"},
                "最多 31 个自然日",
            ),
            (
                "qc_manager",
                {"start_date": "2026-08-31", "end_date": "2026-08-01"},
                "开始日期不得晚于结束日期",
            ),
            (
                "admin",
                {"start_date": "2026-02-30", "end_date": "2026-03-01"},
                "YYYY-MM-DD",
            ),
        ),
    )
    def test_trigger_auto_final_rejects_invalid_date_range_before_sync(
        self,
        client,
        monkeypatch,
        role,
        date_window,
        expected_detail,
    ):
        _override_user(client, [role])
        monkeypatch.setattr(sync_router_module, "enforce_rate_limit", lambda *_args, **_kwargs: None)
        calls = {"run": 0}
        monkeypatch.setattr(
            "app.services.etl_sync.run_sync",
            lambda **_kwargs: calls.__setitem__("run", calls["run"] + 1),
        )

        response = client.post(
            "/api/v1/sync/trigger",
            json={
                "source": "pg",
                "tier": "all",
                "scene": "final",
                "date_window": date_window,
                "auto_qc_after_sync": True,
                "auto_qc_workflow_token": "workflow-final-window-range-invalid",
            },
        )

        assert response.status_code == 422
        assert expected_detail in str(response.json())
        assert calls["run"] == 0

    @pytest.mark.parametrize(
        ("role", "date_window", "expected_window"),
        (
            (
                "admin",
                {"start_date": "2026-08-01", "end_date": "2026-08-31"},
                {"start": "2026-08-01", "end": "2026-08-31"},
            ),
            (
                "qc_manager",
                {"start_date": "2026-08-01", "end_date": "2026-08-31"},
                {"start": "2026-08-01", "end": "2026-08-31"},
            ),
            (
                "admin",
                {"start": "2026-08-01", "end": "2026-08-18"},
                {"start": "2026-08-01", "end": "2026-08-18"},
            ),
            (
                "qc_manager",
                {"start": "2026-08-01", "end": "2026-08-18"},
                {"start": "2026-08-01", "end": "2026-08-18"},
            ),
            ("admin", None, None),
        ),
    )
    def test_trigger_final_date_window_contract_keeps_plain_fallback(
        self,
        client,
        monkeypatch,
        role,
        date_window,
        expected_window,
    ):
        _override_user(client, [role])
        captured: list[dict] = []
        monkeypatch.setattr(
            "app.services.sync_idempotency.reserve_sync_trigger",
            lambda **_kwargs: SyncTriggerReservation(
                created=True,
                run_id="syncrun-final-date-window",
                status="pending",
            ),
        )
        monkeypatch.setattr(
            "app.services.sync_idempotency.complete_sync_trigger",
            lambda **_kwargs: None,
        )
        monkeypatch.setattr(
            "app.services.sync_run_history.append_sync_run_record",
            lambda _record: None,
        )

        def _fake_run_sync(**kwargs):
            captured.append(kwargs)
            return {
                "success": True,
                "status": "success",
                "scene": "final",
                "total_records": 0,
                "_internal_synced_case_refs": [],
            }

        monkeypatch.setattr("app.services.etl_sync.run_sync", _fake_run_sync)
        payload = {"source": "pg", "tier": "all", "scene": "final"}
        if date_window is not None:
            payload.update(
                {
                    "date_window": date_window,
                    "auto_qc_after_sync": True,
                    "auto_qc_workflow_token": "workflow-final-window-valid",
                }
            )

        response = client.post("/api/v1/sync/trigger", json=payload)

        assert response.status_code == 200
        assert captured[0]["date_window"] == expected_window

    @pytest.mark.parametrize("role", ("admin", "qc_manager"))
    def test_trigger_auto_running_rejects_date_window_before_sync(
        self,
        client,
        monkeypatch,
        role,
    ):
        _override_user(client, [role])
        monkeypatch.setattr(sync_router_module, "enforce_rate_limit", lambda *_args, **_kwargs: None)
        calls = {"run": 0}
        monkeypatch.setattr(
            "app.services.etl_sync.run_sync",
            lambda **_kwargs: calls.__setitem__("run", calls["run"] + 1),
        )

        response = client.post(
            "/api/v1/sync/trigger",
            json={
                "source": "pg",
                "tier": "all",
                "scene": "running",
                "date_window": {"start": "2026-08-01", "end": "2026-08-18"},
                "auto_qc_after_sync": True,
                "auto_qc_workflow_token": "workflow-running-window-invalid",
            },
        )

        assert response.status_code == 422
        assert "运行病历" in str(response.json())
        assert "日期范围" in str(response.json())
        assert calls["run"] == 0

    def test_trigger_running_rejected(self, client, monkeypatch):
        _override_user(client, ["admin"])
        monkeypatch.setattr(
            "app.services.sync_idempotency.reserve_sync_trigger",
            lambda **_kwargs: SyncTriggerReservation(
                created=True,
                run_id="syncrun-fixed-id",
                status="pending",
            ),
        )
        monkeypatch.setattr("app.services.sync_idempotency.complete_sync_trigger", lambda **_kwargs: None)
        monkeypatch.setattr(
            "app.services.etl_sync.run_sync",
            lambda **_kwargs: {"success": False, "error": "同步正在进行中，请稍后再试"},
        )

        resp = client.post("/api/v1/sync/trigger", json={"source": "pg", "tier": "all"})
        assert resp.status_code == 200
        _assert_error_shell(resp.json(), expected_code="SYNC_ALREADY_RUNNING")

    def test_trigger_runs_blocking_sync_in_worker_thread(self, client, monkeypatch):
        _override_user(client, ["admin"])
        calls: list[dict] = []

        monkeypatch.setattr(
            "app.services.sync_idempotency.reserve_sync_trigger",
            lambda **_kwargs: SyncTriggerReservation(
                created=True,
                run_id="syncrun-worker-thread",
                status="pending",
            ),
        )
        monkeypatch.setattr(
            "app.services.sync_idempotency.complete_sync_trigger",
            lambda **_kwargs: None,
        )
        monkeypatch.setattr(
            "app.services.sync_run_history.append_sync_run_record",
            lambda _record: None,
        )

        async def _fake_run_in_threadpool(func, **kwargs):
            calls.append({"func": func, "kwargs": kwargs})
            return func(**kwargs)

        monkeypatch.setattr(sync_router_module, "run_in_threadpool", _fake_run_in_threadpool)
        monkeypatch.setattr(
            "app.services.etl_sync.run_sync",
            lambda **_kwargs: {"success": True, "status": "success", "total_records": 1},
        )

        response = client.post(
            "/api/v1/sync/trigger",
            json={"source": "pg", "tier": "all"},
        )

        assert response.status_code == 200
        assert len(calls) == 1
        assert calls[0]["func"].__name__ == "<lambda>"
        assert calls[0]["kwargs"]["run_id"] == "syncrun-worker-thread"

    def test_trigger_enqueues_terminal_qc_after_discharge_without_leaking_case_refs(
        self,
        client,
        monkeypatch,
    ):
        _override_user(client, ["admin"])
        monkeypatch.setattr(
            "app.services.sync_idempotency.reserve_sync_trigger",
            lambda **_kwargs: SyncTriggerReservation(
                created=True,
                run_id="syncrun-discharge-transition",
                status="pending",
            ),
        )
        monkeypatch.setattr(
            "app.services.sync_idempotency.complete_sync_trigger",
            lambda **_kwargs: None,
        )
        monkeypatch.setattr(
            "app.services.sync_run_history.append_sync_run_record",
            lambda _record: None,
        )
        case_ref = {
            "institute_id": "inst-1",
            "patient_id": "patient-1",
            "visit_id": "visit-1",
        }
        monkeypatch.setattr(
            "app.services.etl_sync.run_sync",
            lambda **_kwargs: {
                "success": True,
                "status": "success",
                "scene": "both",
                "total_records": 3,
                "_internal_synced_case_refs": [case_ref],
            },
        )
        from app.routers import qc_sichuan
        from app.services.case_identity import CaseRef

        captured: list[dict] = []

        class _Workspace:
            def find_terminal_reevaluation_candidates(self, *, record_refs):
                captured.extend(record_refs)
                return (CaseRef(**case_ref),)

        async def _fake_get_qc_service():
            return object()

        async def _fake_create_workspace_batch_job(*, payload, **_kwargs):
            assert payload.scope == "final"
            assert payload.date_field == "discharge"
            assert payload.record_refs == [case_ref]
            return {
                "success": True,
                "data": {"id": "job-final-1", "idempotency_reused": False},
            }

        monkeypatch.setattr(qc_sichuan, "_sichuan_workspace_service", lambda: _Workspace())
        monkeypatch.setattr(qc_sichuan, "get_qc_service", _fake_get_qc_service)
        monkeypatch.setattr(
            qc_sichuan,
            "create_workspace_batch_job",
            _fake_create_workspace_batch_job,
        )

        response = client.post(
            "/api/v1/sync/trigger",
            json={"source": "pg", "tier": "all", "scene": "both"},
        )

        assert response.status_code == 200
        data = _assert_success_shell(response.json())
        assert captured == [case_ref]
        assert data["auto_terminal_qc"] == {
            "status": "queued",
            "eligible_records": 1,
            "queued_records": 1,
            "job_id": "job-final-1",
        }
        assert data["auto_qc"] == {
            "scene": "final",
            **data["auto_terminal_qc"],
        }
        assert "_internal_synced_case_refs" not in data

    def test_trigger_explicit_final_auto_qc_uses_all_visible_synced_case_refs(
        self,
        client,
        monkeypatch,
    ):
        _override_user(client, ["admin"])
        monkeypatch.setattr(
            "app.services.sync_idempotency.reserve_sync_trigger",
            lambda **_kwargs: SyncTriggerReservation(
                created=True,
                run_id="syncrun-final-auto-qc",
                status="pending",
            ),
        )
        monkeypatch.setattr(
            "app.services.sync_idempotency.complete_sync_trigger",
            lambda **_kwargs: None,
        )
        monkeypatch.setattr(
            "app.services.sync_run_history.append_sync_run_record",
            lambda _record: None,
        )
        case_refs = [
            {
                "institute_id": "inst-1",
                "patient_id": "patient-1",
                "visit_id": "visit-1",
            },
            {
                "institute_id": "inst-1",
                "patient_id": "patient-2",
                "visit_id": "visit-2",
            },
        ]
        monkeypatch.setattr(
            "app.services.etl_sync.run_sync",
            lambda **_kwargs: {
                "success": True,
                "status": "success",
                "scene": "final",
                "total_records": 2,
                "_internal_synced_case_refs": case_refs,
            },
        )
        from app.routers import qc_sichuan

        class _Workspace:
            def find_terminal_reevaluation_candidates(self, **_kwargs):
                raise AssertionError("显式终末一键质控不得只筛转场复评候选")

        captured_payloads: list[object] = []

        async def _fake_get_qc_service():
            return object()

        async def _fake_create_workspace_batch_job(*, payload, **_kwargs):
            captured_payloads.append(payload)
            return {
                "success": True,
                "data": {"id": "job-final-all-1", "idempotency_reused": False},
            }

        monkeypatch.setattr(qc_sichuan, "_sichuan_workspace_service", lambda: _Workspace())
        monkeypatch.setattr(qc_sichuan, "get_qc_service", _fake_get_qc_service)
        monkeypatch.setattr(
            qc_sichuan,
            "create_workspace_batch_job",
            _fake_create_workspace_batch_job,
        )

        response = client.post(
            "/api/v1/sync/trigger",
            json={
                "source": "pg",
                "tier": "all",
                "scene": "final",
                "date_window": {"start_date": "2026-08-01", "end_date": "2026-08-18"},
                "auto_qc_after_sync": True,
                "auto_qc_workflow_token": "workflow-final-visible",
            },
        )

        assert response.status_code == 200
        data = _assert_success_shell(response.json())
        assert len(captured_payloads) == 1
        payload = captured_payloads[0]
        assert payload.rule_set_key == qc_sichuan.LUXIAN_0609_RULE_SET_KEY
        assert payload.scope == "final"
        assert payload.date_field == "discharge"
        assert payload.record_refs == case_refs
        assert data["auto_qc"] == {
            "scene": "final",
            "status": "queued",
            "eligible_records": 2,
            "queued_records": 2,
            "job_id": "job-final-all-1",
        }
        assert "auto_terminal_qc" not in data
        assert "_internal_synced_case_refs" not in data

    def test_trigger_running_sync_never_enqueues_terminal_qc(self, client, monkeypatch):
        _override_user(client, ["admin"])
        monkeypatch.setattr(
            "app.services.sync_idempotency.reserve_sync_trigger",
            lambda **_kwargs: SyncTriggerReservation(
                created=True,
                run_id="syncrun-running-only",
                status="pending",
            ),
        )
        monkeypatch.setattr(
            "app.services.sync_idempotency.complete_sync_trigger",
            lambda **_kwargs: None,
        )
        monkeypatch.setattr(
            "app.services.sync_run_history.append_sync_run_record",
            lambda _record: None,
        )
        monkeypatch.setattr(
            "app.services.etl_sync.run_sync",
            lambda **_kwargs: {
                "success": True,
                "status": "success",
                "scene": "running",
                "total_records": 1,
                "_internal_synced_case_refs": [
                    {
                        "institute_id": "inst-1",
                        "patient_id": "patient-1",
                        "visit_id": "visit-1",
                    }
                ],
            },
        )

        async def _unexpected_enqueue(**_kwargs):
            raise AssertionError("在院同步不得创建终末质控任务")

        monkeypatch.setattr(
            sync_router_module,
            "_enqueue_terminal_reevaluation_after_sync",
            _unexpected_enqueue,
        )

        response = client.post(
            "/api/v1/sync/trigger",
            json={"source": "pg", "tier": "all", "scene": "running"},
        )

        assert response.status_code == 200
        data = _assert_success_shell(response.json())
        assert "auto_terminal_qc" not in data
        assert "_internal_synced_case_refs" not in data

    def test_trigger_running_auto_qc_enqueues_visible_case_refs(self, client, monkeypatch):
        _override_user(client, ["admin"])
        monkeypatch.setattr(
            "app.services.sync_idempotency.reserve_sync_trigger",
            lambda **_kwargs: SyncTriggerReservation(
                created=True,
                run_id="syncrun-running-auto-qc",
                status="pending",
            ),
        )
        monkeypatch.setattr(
            "app.services.sync_idempotency.complete_sync_trigger",
            lambda **_kwargs: None,
        )
        monkeypatch.setattr(
            "app.services.sync_run_history.append_sync_run_record",
            lambda _record: None,
        )
        case_ref = {
            "institute_id": "inst-1",
            "patient_id": "patient-1",
            "visit_id": "visit-1",
        }
        monkeypatch.setattr(
            "app.services.etl_sync.run_sync",
            lambda **_kwargs: {
                "success": True,
                "status": "success",
                "scene": "running",
                "total_records": 1,
                "_internal_synced_case_refs": [case_ref],
            },
        )
        from app.routers import qc_sichuan

        captured_payloads: list[object] = []

        async def _fake_get_qc_service():
            return object()

        async def _fake_create_workspace_batch_job(*, payload, **_kwargs):
            captured_payloads.append(payload)
            return {
                "success": True,
                "data": {"id": "job-running-1", "idempotency_reused": False},
            }

        monkeypatch.setattr(qc_sichuan, "get_qc_service", _fake_get_qc_service)
        monkeypatch.setattr(
            qc_sichuan,
            "create_workspace_batch_job",
            _fake_create_workspace_batch_job,
        )

        response = client.post(
            "/api/v1/sync/trigger",
            json={
                "source": "pg",
                "tier": "all",
                "scene": "running",
                "auto_qc_after_sync": True,
                "auto_qc_workflow_token": "workflow-running-visible",
            },
        )

        assert response.status_code == 200
        data = _assert_success_shell(response.json())
        assert len(captured_payloads) == 1
        payload = captured_payloads[0]
        assert payload.rule_set_key == qc_sichuan.LUXIAN_0609_RULE_SET_KEY
        assert payload.scope == "running"
        assert payload.date_field == "admission"
        assert payload.record_refs == [case_ref]
        assert data["auto_qc"] == {
            "scene": "running",
            "status": "queued",
            "eligible_records": 1,
            "queued_records": 1,
            "job_id": "job-running-1",
        }
        assert "auto_terminal_qc" not in data
        assert "_internal_synced_case_refs" not in data

    @pytest.mark.asyncio
    @pytest.mark.parametrize("qc_scope", ["running", "final"])
    async def test_enqueue_qc_without_deliverable_records_is_not_applicable(self, qc_scope):
        summary = await sync_router_module._enqueue_qc_after_sync(
            request=None,
            current_user={},
            record_refs=[],
            qc_scope=qc_scope,
            explicit_request=True,
        )

        assert summary == {
            "scene": qc_scope,
            "status": "not_applicable",
            "reason_code": "no_deliverable_records",
            "eligible_records": 0,
            "queued_records": 0,
            "job_id": "",
        }

    def test_trigger_partial_auto_qc_does_not_enqueue(self, client, monkeypatch):
        _override_user(client, ["admin"])
        monkeypatch.setattr(
            "app.services.sync_idempotency.reserve_sync_trigger",
            lambda **_kwargs: SyncTriggerReservation(
                created=True,
                run_id="syncrun-partial-auto-qc",
                status="pending",
            ),
        )
        monkeypatch.setattr(
            "app.services.sync_idempotency.complete_sync_trigger",
            lambda **_kwargs: None,
        )
        monkeypatch.setattr(
            "app.services.sync_run_history.append_sync_run_record",
            lambda _record: None,
        )
        monkeypatch.setattr(
            "app.services.etl_sync.run_sync",
            lambda **_kwargs: {
                "success": False,
                "status": "partial",
                "scene": "running",
                "total_records": 1,
                "warnings": ["部分资料同步失败"],
                "_internal_synced_case_refs": [
                    {
                        "institute_id": "inst-1",
                        "patient_id": "patient-1",
                        "visit_id": "visit-1",
                    }
                ],
            },
        )
        from app.routers import qc_sichuan

        async def _unexpected_create_workspace_batch_job(**_kwargs):
            raise AssertionError("同步未完整成功时不得创建质控任务")

        monkeypatch.setattr(
            qc_sichuan,
            "create_workspace_batch_job",
            _unexpected_create_workspace_batch_job,
        )

        response = client.post(
            "/api/v1/sync/trigger",
            json={
                "source": "pg",
                "tier": "all",
                "scene": "running",
                "auto_qc_after_sync": True,
                "auto_qc_workflow_token": "workflow-partial-sync",
            },
        )

        assert response.status_code == 200
        data = _assert_success_shell(response.json())
        assert data["status"] == "partial"
        assert data["auto_qc"] == {
            "scene": "running",
            "status": "not_created",
            "reason_code": "sync_partial",
            "eligible_records": 0,
            "queued_records": 0,
            "job_id": "",
        }
        assert "_internal_synced_case_refs" not in data

    def test_qc_manager_one_click_is_idempotent_per_user_and_keeps_job_ownership(
        self,
        client,
        monkeypatch,
    ):
        reservations: dict[str, dict[str, object]] = {}
        reservation_calls: list[dict[str, object]] = []
        calls = {"run": 0, "qc": 0, "created_by": []}
        case_ref = {
            "institute_id": "inst-1",
            "patient_id": "patient-1",
            "visit_id": "visit-1",
        }

        def _fake_reserve(**kwargs):
            reservation_calls.append(dict(kwargs))
            key = str(kwargs["idempotency_key"])
            existing = reservations.get(key)
            if existing is not None:
                return SyncTriggerReservation(
                    created=False,
                    run_id=str(existing["run_id"]),
                    status=str(existing["status"]),
                    result=existing.get("result"),
                )
            run_id = f"syncrun-qcm-{len(reservations) + 1}"
            reservations[key] = {"run_id": run_id, "status": "pending", "result": None}
            return SyncTriggerReservation(created=True, run_id=run_id, status="pending")

        def _fake_complete(**kwargs):
            entry = reservations[str(kwargs["idempotency_key"])]
            entry["status"] = kwargs["status"]
            entry["result"] = kwargs["result"]

        def _fake_run_sync(**_kwargs):
            calls["run"] += 1
            return {
                "success": True,
                "status": "success",
                "scene": "running",
                "total_records": 1,
                "_internal_synced_case_refs": [case_ref],
            }

        monkeypatch.setattr(
            "app.services.sync_idempotency.reserve_sync_trigger",
            _fake_reserve,
        )
        monkeypatch.setattr(
            "app.services.sync_idempotency.complete_sync_trigger",
            _fake_complete,
        )
        monkeypatch.setattr(
            "app.services.sync_run_history.append_sync_run_record",
            lambda _record: None,
        )
        monkeypatch.setattr("app.services.etl_sync.run_sync", _fake_run_sync)
        from app.routers import qc_sichuan

        async def _fake_get_qc_service():
            return object()

        async def _fake_create_workspace_batch_job(**_kwargs):
            calls["qc"] += 1
            calls["created_by"].append(_kwargs["current_user"]["email"])
            return {
                "success": True,
                "data": {
                    "id": f"job-qcm-{calls['qc']}",
                    "idempotency_reused": False,
                },
            }

        monkeypatch.setattr(qc_sichuan, "get_qc_service", _fake_get_qc_service)
        monkeypatch.setattr(
            qc_sichuan,
            "create_workspace_batch_job",
            _fake_create_workspace_batch_job,
        )
        request_body = {
            "source": "pg",
            "tier": "all",
            "scene": "running",
            "target_departments": ["骨科"],
            "auto_qc_after_sync": True,
            "auto_qc_workflow_token": "workflow-qcm-shared",
        }

        _override_user(client, ["qc_manager"], email="manager-a@test.local")
        first = client.post("/api/v1/sync/trigger", json=request_body)
        assert first.status_code == 200
        first_data = _assert_success_shell(first.json())
        assert first_data["idempotent_reused"] is False

        _override_user(client, ["qc_manager"], email="manager-b@test.local")
        second = client.post("/api/v1/sync/trigger", json=request_body)
        assert second.status_code == 200
        second_data = _assert_success_shell(second.json())
        assert second_data["idempotent_reused"] is False
        assert first_data["auto_qc"]["job_id"] == "job-qcm-1"
        assert second_data["auto_qc"]["job_id"] == "job-qcm-2"

        repeated = client.post("/api/v1/sync/trigger", json=request_body)
        assert repeated.status_code == 200
        repeated_data = _assert_success_shell(repeated.json())
        assert repeated_data["idempotent_reused"] is True
        assert repeated_data["auto_qc"] == second_data["auto_qc"]
        assert calls == {
            "run": 2,
            "qc": 2,
            "created_by": ["manager-a@test.local", "manager-b@test.local"],
        }
        assert [call["operator_email"] for call in reservation_calls] == [
            "manager-a@test.local",
            "manager-b@test.local",
            "manager-b@test.local",
        ]
        assert reservation_calls[0]["idempotency_key"] != reservation_calls[1]["idempotency_key"]
        assert reservation_calls[1]["idempotency_key"] == reservation_calls[2]["idempotency_key"]

    def test_qc_manager_one_click_rejects_unrestricted_sync_inputs(self):
        current_user = {"roles": ["qc_manager"]}
        blocked_requests = (
            sync_router_module.TriggerRequest(scene="running"),
            sync_router_module.TriggerRequest(
                scene="both",
                auto_qc_after_sync=True,
            ),
            sync_router_module.TriggerRequest(
                scene="running",
                auto_qc_after_sync=True,
                tables=["mr"],
            ),
            sync_router_module.TriggerRequest(
                scene="running",
                auto_qc_after_sync=True,
                table_groups=["core_8"],
            ),
            sync_router_module.TriggerRequest(
                scene="running",
                auto_qc_after_sync=True,
                sync_date="2026-08-18",
            ),
            sync_router_module.TriggerRequest(
                scene="running",
                auto_qc_after_sync=True,
                policy_version="operator-selected-policy",
            ),
            sync_router_module.TriggerRequest(
                scene="final",
                auto_qc_after_sync=True,
                preflight_fingerprint="stale-preflight-result",
            ),
        )

        for request in blocked_requests:
            with pytest.raises(HTTPException) as exc_info:
                sync_router_module._assert_qc_manager_one_click_request(
                    request,
                    current_user,
                )
            assert exc_info.value.status_code == 403

    def test_trigger_retries_failed_auto_qc_enqueue_without_rerunning_sync_or_leaking_refs(
        self,
        client,
        monkeypatch,
    ):
        _override_user(client, ["admin"])
        reservations: dict[str, dict[str, object]] = {}
        calls = {"run": 0, "qc": 0}
        case_ref = {
            "institute_id": "inst-1",
            "patient_id": "patient-1",
            "visit_id": "visit-1",
        }

        def _fake_reserve(**kwargs):
            key = str(kwargs["idempotency_key"])
            existing = reservations.get(key)
            if existing is not None:
                return SyncTriggerReservation(
                    created=False,
                    run_id=str(existing["run_id"]),
                    status=str(existing["status"]),
                    result=existing.get("result"),
                )
            reservations[key] = {
                "run_id": "syncrun-qc-retry",
                "status": "pending",
                "result": None,
            }
            return SyncTriggerReservation(
                created=True,
                run_id="syncrun-qc-retry",
                status="pending",
            )

        def _fake_complete(**kwargs):
            entry = reservations[str(kwargs["idempotency_key"])]
            entry["status"] = kwargs["status"]
            entry["result"] = kwargs["result"]

        def _fake_claim(idempotency_key: str):
            result = reservations[idempotency_key].get("result")
            if not isinstance(result, dict):
                return None
            auto_qc = result.get("auto_qc")
            raw_record_refs = result.get("_internal_synced_case_refs")
            if (
                not isinstance(auto_qc, dict)
                or auto_qc.get("status") != "enqueue_failed"
                or not isinstance(raw_record_refs, list)
            ):
                return None
            record_refs = [dict(item) for item in raw_record_refs if isinstance(item, dict)]
            if not record_refs:
                return None
            result["auto_qc"] = {
                **auto_qc,
                "status": "enqueueing",
                "claimed_at": datetime.now(timezone.utc).isoformat(),
            }
            result["auto_qc"].pop("reason_code", None)
            return record_refs

        monkeypatch.setattr(
            "app.services.sync_idempotency.claim_sync_auto_qc_retry",
            _fake_claim,
        )

        def _fake_run_sync(**_kwargs):
            calls["run"] += 1
            return {
                "success": True,
                "status": "success",
                "scene": "running",
                "total_records": 1,
                "_internal_synced_case_refs": [case_ref],
            }

        monkeypatch.setattr(
            "app.services.sync_idempotency.reserve_sync_trigger",
            _fake_reserve,
        )
        monkeypatch.setattr(
            "app.services.sync_idempotency.complete_sync_trigger",
            _fake_complete,
        )
        monkeypatch.setattr(
            "app.services.sync_run_history.append_sync_run_record",
            lambda _record: None,
        )
        monkeypatch.setattr("app.services.etl_sync.run_sync", _fake_run_sync)
        from app.routers import qc_sichuan

        async def _fake_get_qc_service():
            return object()

        async def _fake_create_workspace_batch_job(**_kwargs):
            calls["qc"] += 1
            if calls["qc"] in {1, 2}:
                return {
                    "success": True,
                    "data": {"id": "", "idempotency_reused": False},
                }
            return {
                "success": True,
                "data": {"id": "job-recovered", "idempotency_reused": False},
            }

        monkeypatch.setattr(qc_sichuan, "get_qc_service", _fake_get_qc_service)
        monkeypatch.setattr(
            qc_sichuan,
            "create_workspace_batch_job",
            _fake_create_workspace_batch_job,
        )
        request_body = {
            "source": "pg",
            "tier": "all",
            "scene": "running",
            "auto_qc_after_sync": True,
            "auto_qc_workflow_token": "workflow-retry-enqueue",
        }

        first = client.post("/api/v1/sync/trigger", json=request_body)
        assert first.status_code == 200
        first_data = _assert_success_shell(first.json())
        assert first_data["auto_qc"] == {
            "scene": "running",
            "status": "enqueue_failed",
            "reason_code": "enqueue_failed",
            "eligible_records": 0,
            "queued_records": 0,
            "job_id": "",
        }
        assert "_internal_synced_case_refs" not in first_data
        assert first_data["warnings"] == [
            sync_router_module._AUTO_QC_ENQUEUE_FAILED_WARNING
        ]
        stored_after_failure = next(iter(reservations.values()))["result"]
        assert stored_after_failure["_internal_synced_case_refs"] == [case_ref]

        second = client.post("/api/v1/sync/trigger", json=request_body)
        assert second.status_code == 200
        second_data = _assert_success_shell(second.json())
        assert second_data["idempotent_reused"] is True
        assert second_data["auto_qc"] == {
            "scene": "running",
            "status": "enqueue_failed",
            "reason_code": "enqueue_failed",
            "eligible_records": 0,
            "queued_records": 0,
            "job_id": "",
        }
        assert "_internal_synced_case_refs" not in second_data
        assert "_internal_synced_case_refs" not in second_data["result"]
        stored_after_retry_failure = next(iter(reservations.values()))["result"]
        assert stored_after_retry_failure["_internal_synced_case_refs"] == [case_ref]
        assert "claimed_at" not in stored_after_retry_failure["auto_qc"]

        third = client.post("/api/v1/sync/trigger", json=request_body)
        assert third.status_code == 200
        third_data = _assert_success_shell(third.json())
        assert third_data["idempotent_reused"] is True
        assert third_data["auto_qc"] == {
            "scene": "running",
            "status": "queued",
            "eligible_records": 1,
            "queued_records": 1,
            "job_id": "job-recovered",
        }
        assert "_internal_synced_case_refs" not in third_data["result"]
        stored_after_recovery = next(iter(reservations.values()))["result"]
        assert "_internal_synced_case_refs" not in stored_after_recovery

        fourth = client.post("/api/v1/sync/trigger", json=request_body)
        assert fourth.status_code == 200
        fourth_data = _assert_success_shell(fourth.json())
        assert fourth_data["idempotent_reused"] is True
        assert fourth_data["auto_qc"] == third_data["auto_qc"]
        assert calls == {"run": 1, "qc": 3}

    def test_concurrent_auto_qc_retry_only_one_request_enqueues_job(
        self,
        client,
        monkeypatch,
    ):
        _override_user(client, ["admin"])
        monkeypatch.setattr(sync_idempotency, "engine", None)
        sync_idempotency.reset_sync_idempotency_for_testing()
        calls = {"run": 0, "qc": 0}
        case_ref = {
            "institute_id": "inst-1",
            "patient_id": "patient-1",
            "visit_id": "visit-1",
        }
        retry_enqueue_entered = Event()
        release_retry_enqueue = Event()
        duplicate_enqueue_seen = Event()
        calls_lock = Lock()

        def _fake_run_sync(**_kwargs):
            calls["run"] += 1
            return {
                "success": True,
                "status": "success",
                "scene": "running",
                "total_records": 1,
                "_internal_synced_case_refs": [case_ref],
            }

        monkeypatch.setattr(
            "app.services.sync_run_history.append_sync_run_record",
            lambda _record: None,
        )
        monkeypatch.setattr("app.services.etl_sync.run_sync", _fake_run_sync)
        from app.routers import qc_sichuan

        async def _fake_get_qc_service():
            return object()

        async def _fake_create_workspace_batch_job(**_kwargs):
            with calls_lock:
                calls["qc"] += 1
                attempt = calls["qc"]
            if attempt == 1:
                return {
                    "success": True,
                    "data": {"id": "", "idempotency_reused": False},
                }
            if attempt == 2:
                retry_enqueue_entered.set()
                assert release_retry_enqueue.wait(timeout=3)
                return {
                    "success": True,
                    "data": {"id": "job-concurrent-recovered", "idempotency_reused": False},
                }
            duplicate_enqueue_seen.set()
            return {
                "success": True,
                "data": {"id": "job-duplicate", "idempotency_reused": False},
            }

        monkeypatch.setattr(qc_sichuan, "get_qc_service", _fake_get_qc_service)
        monkeypatch.setattr(
            qc_sichuan,
            "create_workspace_batch_job",
            _fake_create_workspace_batch_job,
        )
        request_body = {
            "source": "pg",
            "tier": "all",
            "scene": "running",
            "auto_qc_after_sync": True,
            "auto_qc_workflow_token": "workflow-concurrent-retry",
        }

        failed = client.post("/api/v1/sync/trigger", json=request_body)
        assert failed.status_code == 200
        assert _assert_success_shell(failed.json())["auto_qc"]["status"] == "enqueue_failed"

        with TestClient(client.app) as owner_client, TestClient(client.app) as observer_client:
            with ThreadPoolExecutor(max_workers=2) as executor:
                owner_future = executor.submit(
                    lambda: owner_client.post("/api/v1/sync/trigger", json=request_body)
                )
                assert retry_enqueue_entered.wait(timeout=3)
                observer_future = executor.submit(
                    lambda: observer_client.post("/api/v1/sync/trigger", json=request_body)
                )
                try:
                    observer = observer_future.result(timeout=3)
                finally:
                    release_retry_enqueue.set()
                owner = owner_future.result(timeout=3)

        assert owner.status_code == 200
        assert observer.status_code == 200
        owner_data = _assert_success_shell(owner.json())
        observer_data = _assert_success_shell(observer.json())
        assert owner_data["auto_qc"] == {
            "scene": "running",
            "status": "queued",
            "eligible_records": 1,
            "queued_records": 1,
            "job_id": "job-concurrent-recovered",
        }
        assert observer_data["auto_qc"] == {
            "scene": "running",
            "status": "enqueueing",
            "eligible_records": 0,
            "queued_records": 0,
            "job_id": "",
        }
        assert duplicate_enqueue_seen.is_set() is False
        assert calls == {"run": 1, "qc": 2}

    def test_expired_auto_qc_enqueueing_lease_is_reclaimed_without_resync(
        self,
        client,
        monkeypatch,
    ):
        _override_user(client, ["admin"])
        monkeypatch.setattr(sync_idempotency, "engine", None)
        sync_idempotency.reset_sync_idempotency_for_testing()
        calls = {"run": 0, "qc": 0}
        case_ref = {
            "institute_id": "inst-1",
            "patient_id": "patient-1",
            "visit_id": "visit-1",
        }

        def _fake_run_sync(**_kwargs):
            calls["run"] += 1
            return {
                "success": True,
                "status": "success",
                "scene": "running",
                "total_records": 1,
                "_internal_synced_case_refs": [case_ref],
            }

        monkeypatch.setattr(
            "app.services.sync_run_history.append_sync_run_record",
            lambda _record: None,
        )
        monkeypatch.setattr("app.services.etl_sync.run_sync", _fake_run_sync)
        from app.routers import qc_sichuan

        async def _fake_get_qc_service():
            return object()

        async def _fake_create_workspace_batch_job(**_kwargs):
            calls["qc"] += 1
            if calls["qc"] == 1:
                return {
                    "success": True,
                    "data": {"id": "", "idempotency_reused": False},
                }
            return {
                "success": True,
                "data": {"id": "job-after-lease", "idempotency_reused": False},
            }

        monkeypatch.setattr(qc_sichuan, "get_qc_service", _fake_get_qc_service)
        monkeypatch.setattr(
            qc_sichuan,
            "create_workspace_batch_job",
            _fake_create_workspace_batch_job,
        )
        request_body = {
            "source": "pg",
            "tier": "all",
            "sync_date": "2026-08-18",
            "scene": "running",
            "auto_qc_after_sync": True,
            "auto_qc_workflow_token": "workflow-expired-lease",
        }

        failed = client.post("/api/v1/sync/trigger", json=request_body)
        assert failed.status_code == 200
        failed_data = _assert_success_shell(failed.json())
        assert failed_data["auto_qc"]["status"] == "enqueue_failed"
        idempotency_key = failed_data["idempotency_key"]

        assert sync_idempotency.claim_sync_auto_qc_retry(idempotency_key) == [case_ref]
        reserved = sync_idempotency.reserve_sync_trigger(
            idempotency_key=idempotency_key,
            source="pg",
            tier="all",
            sync_date="2026-08-18",
            operator_email="sync@test.local",
        )
        assert reserved.result is not None
        expired_result = dict(reserved.result)
        expired_result["auto_qc"] = {
            **reserved.result["auto_qc"],
            "claimed_at": (datetime.now(timezone.utc) - timedelta(seconds=121)).isoformat(),
        }
        sync_idempotency.complete_sync_trigger(
            idempotency_key=idempotency_key,
            status="success",
            result=expired_result,
        )

        recovered = client.post("/api/v1/sync/trigger", json=request_body)
        assert recovered.status_code == 200
        recovered_data = _assert_success_shell(recovered.json())
        assert recovered_data["idempotent_reused"] is True
        assert recovered_data["auto_qc"] == {
            "scene": "running",
            "status": "queued",
            "eligible_records": 1,
            "queued_records": 1,
            "job_id": "job-after-lease",
        }
        assert "claimed_at" not in recovered_data["result"]["auto_qc"]
        assert calls == {"run": 1, "qc": 2}

    def test_trigger_idempotency_reuse(self, client, monkeypatch):
        _override_user(client, ["admin"])
        calls = {"reserve": 0, "run": 0, "append": 0}

        def _fake_reserve(**_kwargs):
            calls["reserve"] += 1
            if calls["reserve"] == 1:
                return SyncTriggerReservation(
                    created=True,
                    run_id="syncrun-fixed-id",
                    status="pending",
                )
            return SyncTriggerReservation(
                created=False,
                run_id="syncrun-fixed-id",
                status="success",
                result={
                    "success": True,
                    "total_records": 2,
                    "auto_terminal_qc": {
                        "status": "queued",
                        "eligible_records": 1,
                        "queued_records": 1,
                        "job_id": "job-final-reused",
                    },
                    "auto_qc": {
                        "scene": "final",
                        "status": "queued",
                        "eligible_records": 1,
                        "queued_records": 1,
                        "job_id": "job-final-reused",
                    },
                },
            )

        monkeypatch.setattr("app.services.sync_idempotency.reserve_sync_trigger", _fake_reserve)
        monkeypatch.setattr("app.services.sync_idempotency.complete_sync_trigger", lambda **_kwargs: None)
        monkeypatch.setattr(
            "app.services.sync_run_history.append_sync_run_record",
            lambda _record: calls.__setitem__("append", calls["append"] + 1),
        )

        def _fake_run_sync(**_kwargs):
            calls["run"] += 1
            return {"success": True, "total_records": 2, "tables": []}

        monkeypatch.setattr("app.services.etl_sync.run_sync", _fake_run_sync)

        first = client.post("/api/v1/sync/trigger", json={"source": "pg", "tier": "all"})
        assert first.status_code == 200
        first_data = _assert_success_shell(first.json())
        assert first_data["run_id"] == "syncrun-fixed-id"
        assert first_data["idempotent_reused"] is False

        second = client.post("/api/v1/sync/trigger", json={"source": "pg", "tier": "all"})
        assert second.status_code == 200
        second_data = _assert_success_shell(second.json())
        assert second_data["run_id"] == "syncrun-fixed-id"
        assert second_data["idempotent_reused"] is True
        assert second_data["auto_terminal_qc"] == {
            "status": "queued",
            "eligible_records": 1,
            "queued_records": 1,
            "job_id": "job-final-reused",
        }
        assert second_data["auto_qc"]["job_id"] == "job-final-reused"
        assert calls["run"] == 1
        assert calls["append"] == 1

    def test_trigger_auto_qc_idempotency_is_distinct_and_reuses_qc_summary(
        self,
        client,
        monkeypatch,
    ):
        _override_user(client, ["admin"])
        reservations: dict[str, dict[str, object]] = {}
        calls = {"run": 0, "qc": 0}
        case_ref = {
            "institute_id": "inst-1",
            "patient_id": "patient-1",
            "visit_id": "visit-1",
        }

        def _fake_reserve(**kwargs):
            key = str(kwargs["idempotency_key"])
            existing = reservations.get(key)
            if existing is not None:
                return SyncTriggerReservation(
                    created=False,
                    run_id=str(existing["run_id"]),
                    status=str(existing["status"]),
                    result=existing.get("result"),
                )
            run_id = f"syncrun-auto-qc-{len(reservations) + 1}"
            reservations[key] = {"run_id": run_id, "status": "pending", "result": None}
            return SyncTriggerReservation(created=True, run_id=run_id, status="pending")

        def _fake_complete(**kwargs):
            entry = reservations[str(kwargs["idempotency_key"])]
            entry["status"] = kwargs["status"]
            entry["result"] = kwargs["result"]

        def _fake_run_sync(**_kwargs):
            calls["run"] += 1
            return {
                "success": True,
                "status": "success",
                "scene": "running",
                "total_records": 1,
                "_internal_synced_case_refs": [case_ref],
            }

        monkeypatch.setattr(
            "app.services.sync_idempotency.reserve_sync_trigger",
            _fake_reserve,
        )
        monkeypatch.setattr(
            "app.services.sync_idempotency.complete_sync_trigger",
            _fake_complete,
        )
        monkeypatch.setattr(
            "app.services.sync_run_history.append_sync_run_record",
            lambda _record: None,
        )
        monkeypatch.setattr("app.services.etl_sync.run_sync", _fake_run_sync)
        from app.routers import qc_sichuan

        async def _fake_get_qc_service():
            return object()

        async def _fake_create_workspace_batch_job(**_kwargs):
            calls["qc"] += 1
            return {
                "success": True,
                "data": {"id": "job-running-idempotent", "idempotency_reused": False},
            }

        monkeypatch.setattr(qc_sichuan, "get_qc_service", _fake_get_qc_service)
        monkeypatch.setattr(
            qc_sichuan,
            "create_workspace_batch_job",
            _fake_create_workspace_batch_job,
        )

        plain = client.post(
            "/api/v1/sync/trigger",
            json={"source": "pg", "tier": "all", "scene": "running"},
        )
        assert plain.status_code == 200
        plain_data = _assert_success_shell(plain.json())
        assert plain_data["idempotent_reused"] is False
        assert "auto_qc" not in plain_data

        automatic = client.post(
            "/api/v1/sync/trigger",
            json={
                "source": "pg",
                "tier": "all",
                "scene": "running",
                "auto_qc_after_sync": True,
                "auto_qc_workflow_token": "workflow-idempotent-a",
            },
        )
        assert automatic.status_code == 200
        automatic_data = _assert_success_shell(automatic.json())
        assert automatic_data["idempotent_reused"] is False
        assert automatic_data["auto_qc"] == {
            "scene": "running",
            "status": "queued",
            "eligible_records": 1,
            "queued_records": 1,
            "job_id": "job-running-idempotent",
        }

        repeated = client.post(
            "/api/v1/sync/trigger",
            json={
                "source": "pg",
                "tier": "all",
                "scene": "running",
                "auto_qc_after_sync": True,
                "auto_qc_workflow_token": "workflow-idempotent-a",
            },
        )
        assert repeated.status_code == 200
        repeated_data = _assert_success_shell(repeated.json())
        assert repeated_data["idempotent_reused"] is True
        assert repeated_data["auto_qc"] == automatic_data["auto_qc"]

        later_click = client.post(
            "/api/v1/sync/trigger",
            json={
                "source": "pg",
                "tier": "all",
                "scene": "running",
                "auto_qc_after_sync": True,
                "auto_qc_workflow_token": "workflow-idempotent-b",
            },
        )
        assert later_click.status_code == 200
        later_click_data = _assert_success_shell(later_click.json())
        assert later_click_data["idempotent_reused"] is False
        assert later_click_data["auto_qc"]["job_id"] == "job-running-idempotent"
        assert automatic_data["idempotency_key"] != later_click_data["idempotency_key"]
        assert calls == {"run": 3, "qc": 2}

    def test_idempotency_key_includes_policy_scope_inputs(self):
        base = {
            "source": "pg",
            "tier": "all",
            "sync_date": "2026-05-25",
            "operator": "admin@example.com",
            "scene": "both",
            "date_window": {"start": "2026-05-25", "end": "2026-05-25"},
            "target_departments": ["普通外科"],
            "tables": ["mr", "discharge_record"],
            "table_groups": ["sample_full_domain"],
            "policy_version": "policy-a",
        }

        key_a = sync_router_module._build_idempotency_key(**base)
        key_b = sync_router_module._build_idempotency_key(
            **{
                **base,
                "target_departments": ["骨科"],
            }
        )
        key_c = sync_router_module._build_idempotency_key(
            **{
                **base,
                "date_window": {"start": "2026-05-26", "end": "2026-05-26"},
            }
        )
        key_d = sync_router_module._build_idempotency_key(
            **{
                **base,
                "table_groups": ["core_8"],
            }
        )

        assert key_a != key_b
        assert key_a != key_c
        assert key_a != key_d

    def test_idempotency_key_without_auto_qc_keeps_legacy_fingerprint(self):
        base_kwargs = {
            "source": "pg",
            "tier": "all",
            "sync_date": "2026-05-25",
            "operator": "admin@example.com",
            "scene": "running",
            "date_window": {"start": "2026-05-25", "end": "2026-05-25"},
            "target_departments": ["orthopedics"],
            "tables": ["mr"],
            "table_groups": ["core_8"],
            "policy_version": "policy-a",
        }
        expected_key = "pg:all:2026-05-25:admin@example.com:353dbf60fc0cf0d3fabb448b"
        assert sync_router_module._build_idempotency_key(**base_kwargs) == expected_key
        assert sync_router_module._build_idempotency_key(
            **{
                **base_kwargs,
                "auto_qc_workflow_token": "workflow-ignored-for-plain-sync",
            }
        ) == expected_key

    def test_idempotency_key_includes_workflow_token_only_for_auto_qc(self):
        base_kwargs = {
            "source": "pg",
            "tier": "all",
            "sync_date": "2026-05-25",
            "operator": "admin@example.com",
            "scene": "running",
            "date_window": {"start": "2026-05-25", "end": "2026-05-25"},
            "target_departments": ["orthopedics"],
            "tables": ["mr"],
            "table_groups": ["core_8"],
            "policy_version": "policy-a",
            "auto_qc_after_sync": True,
        }
        assert sync_router_module._build_idempotency_key(
            **{**base_kwargs, "auto_qc_workflow_token": "workflow-token-a"}
        ) == sync_router_module._build_idempotency_key(
            **{**base_kwargs, "auto_qc_workflow_token": "workflow-token-a"}
        )
        assert sync_router_module._build_idempotency_key(
            **{**base_kwargs, "auto_qc_workflow_token": "workflow-token-a"}
        ) != sync_router_module._build_idempotency_key(
            **{**base_kwargs, "auto_qc_workflow_token": "workflow-token-b"}
        )

    def test_trigger_idempotency_reuse_partial_result_is_success_shell(self, client, monkeypatch):
        _override_user(client, ["admin"])
        monkeypatch.setattr(
            "app.services.sync_idempotency.reserve_sync_trigger",
            lambda **_kwargs: SyncTriggerReservation(
                created=False,
                run_id="syncrun-partial-id",
                status="partial",
                result={
                    "success": True,
                    "status": "partial",
                    "warnings": ["同步部分完成：部分病历缺少 mr 主记录，病历池暂不可见"],
                },
            ),
        )

        resp = client.post("/api/v1/sync/trigger", json={"source": "pg", "tier": "all"})
        assert resp.status_code == 200
        data = _assert_success_shell(resp.json())
        assert data["success"] is True
        assert data["status"] == "partial"
        assert data["idempotent_reused"] is True
        assert data["warnings"] == ["同步部分完成：部分病历缺少 mr 主记录，病历池暂不可见"]

    def test_trigger_fresh_partial_result_keeps_partial_success_envelope(
        self,
        client,
        monkeypatch,
    ):
        _override_user(client, ["admin"])
        completion: dict[str, object] = {}
        history: list[dict] = []
        warnings = ["同步部分完成：1份病例缺少可见主记录"]
        monkeypatch.setattr(
            "app.services.sync_idempotency.reserve_sync_trigger",
            lambda **_kwargs: SyncTriggerReservation(
                created=True,
                run_id="syncrun-fresh-partial",
                status="pending",
            ),
        )
        monkeypatch.setattr(
            "app.services.sync_idempotency.complete_sync_trigger",
            lambda **kwargs: completion.update(kwargs),
        )
        monkeypatch.setattr(
            "app.services.sync_run_history.append_sync_run_record",
            lambda record: history.append(record),
        )
        monkeypatch.setattr(
            "app.services.etl_sync.run_sync",
            lambda **_kwargs: {
                "success": False,
                "status": "partial",
                "total_records": 7,
                "warnings": warnings,
                "_internal_synced_case_refs": [
                    {
                        "institute_id": "inst-1",
                        "patient_id": "patient-1",
                        "visit_id": "visit-1",
                    }
                ],
                "tables": [
                    {"table_name": "mr", "status": "success"},
                    {"table_name": "daily_course_record", "status": "failed"},
                ],
            },
        )

        async def _unexpected_enqueue(**_kwargs):
            raise AssertionError("资料同步不完整时不得自动创建终末质控")

        monkeypatch.setattr(
            sync_router_module,
            "_enqueue_terminal_reevaluation_after_sync",
            _unexpected_enqueue,
        )

        response = client.post(
            "/api/v1/sync/trigger",
            json={"source": "pg", "tier": "all"},
        )

        assert response.status_code == 200
        data = _assert_success_shell(response.json())
        assert data["status"] == "partial"
        assert data["idempotent_reused"] is False
        assert data["warnings"] == warnings
        assert "auto_terminal_qc" not in data
        assert "_internal_synced_case_refs" not in data
        assert completion["status"] == "partial"
        assert completion["error"] == ""
        assert history[0]["status"] == "partial"

    def test_trigger_fresh_failed_result_remains_error_envelope(self, client, monkeypatch):
        _override_user(client, ["admin"])
        completion: dict[str, object] = {}
        history: list[dict] = []
        monkeypatch.setattr(
            "app.services.sync_idempotency.reserve_sync_trigger",
            lambda **_kwargs: SyncTriggerReservation(
                created=True,
                run_id="syncrun-fresh-failed",
                status="pending",
            ),
        )
        monkeypatch.setattr(
            "app.services.sync_idempotency.complete_sync_trigger",
            lambda **kwargs: completion.update(kwargs),
        )
        monkeypatch.setattr(
            "app.services.sync_run_history.append_sync_run_record",
            lambda record: history.append(record),
        )
        monkeypatch.setattr(
            "app.services.etl_sync.run_sync",
            lambda **_kwargs: {
                "success": False,
                "status": "failed",
                "scene": "running",
                "error": "同步执行失败",
                "total_records": 0,
                "warnings": [],
                "tables": [],
                "_internal_synced_case_refs": [
                    {
                        "institute_id": "inst-1",
                        "patient_id": "patient-1",
                        "visit_id": "visit-1",
                    }
                ],
            },
        )

        async def _unexpected_enqueue(**_kwargs):
            raise AssertionError("同步失败时不得创建质控任务")

        monkeypatch.setattr(
            sync_router_module,
            "_enqueue_qc_after_sync",
            _unexpected_enqueue,
        )

        response = client.post(
            "/api/v1/sync/trigger",
            json={
                "source": "pg",
                "tier": "all",
                "scene": "running",
                "auto_qc_after_sync": True,
                "auto_qc_workflow_token": "workflow-failed-sync",
            },
        )

        assert response.status_code == 200
        body = response.json()
        _assert_error_shell(body, expected_code="SYNC_TRIGGER_FAILED")
        assert body["data"]["auto_qc"] == {
            "scene": "running",
            "status": "not_created",
            "reason_code": "sync_failed",
            "eligible_records": 0,
            "queued_records": 0,
            "job_id": "",
        }
        assert "_internal_synced_case_refs" not in body["data"]
        assert completion["status"] == "failed"
        assert history[0]["status"] == "failed"

    def test_get_runs(self, client, monkeypatch):
        _override_user(client, ["qc_manager"])
        monkeypatch.setattr(
            "app.services.sync_run_history.list_sync_run_records",
            lambda source=None, tier=None, limit=50, page=1, page_size=None: {
                "items": [{"id": "r1", "source": source or "pg", "tier": tier or "all"}],
                "total": 1,
                "limit": page_size or limit,
                "page": page,
                "page_size": page_size or limit,
                "total_pages": 1,
            },
        )

        resp = client.get("/api/v1/sync/runs", params={"source": "pg", "tier": "tier2", "limit": 20})
        assert resp.status_code == 200
        data = _assert_success_shell(resp.json())
        assert data["items"][0]["source"] == "pg"
        assert data["items"][0]["tier"] == "tier2"

    def test_templates_permission_and_apply(self, client, monkeypatch):
        _override_user(client, ["qc_manager"])
        assert client.get("/api/v1/sync/templates").status_code == 200

        _override_user(client, ["doctor"])
        assert client.get("/api/v1/sync/templates").status_code == 403

        _override_user(client, ["admin"])
        monkeypatch.setattr(
            "app.services.sync_templates.list_sync_templates",
            lambda: [
                {
                    "id": "hospital_standard",
                    "name": "全院标准",
                    "description": "desc",
                    "risk_tip": "tip",
                    "requires_departments": False,
                    "allow_multi_departments": False,
                    "defaults": {"target_departments": ["*"], "tier1_interval_minutes": 30},
                }
            ],
        )
        monkeypatch.setattr(
            "app.services.sync_policy.save_sync_policy",
            lambda payload, keep_policy_version=False: {
                "scope": "both",
                "target_departments": payload.get("target_departments", ["*"]),
                "schedule": payload.get("schedule", {"mode": "interval", "minutes": 30}),
                "night_window": payload.get("night_window", {"start": "22:00", "end": "06:00"}),
                "policy_version": "policy-20260415T010203Z",
            },
        )

        resp = client.post("/api/v1/sync/templates/apply", json={"template_id": "hospital_standard"})
        assert resp.status_code == 200
        data = _assert_success_shell(resp.json())
        assert data["template_id"] == "hospital_standard"
        assert data["policy"]["policy_version"] == "policy-20260415T010203Z"
