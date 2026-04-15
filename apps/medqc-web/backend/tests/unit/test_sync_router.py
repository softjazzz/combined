"""
数据同步路由单元测试（PG-only）。
"""

from __future__ import annotations

import pytest

from app.core.access_control import enforce_default_auth
from app.core.security import get_current_user
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


def _override_user(client, roles: list[str]) -> None:
    user = {
        "id": "u-sync-test",
        "email": "sync@test.local",
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
    def test_read_permission_matrix(self, client, monkeypatch):
        monkeypatch.setattr(
            "app.services.etl_sync.get_sync_state",
            lambda: {"is_running": False, "logs": [], "total_records_synced": 0},
        )

        _override_user(client, ["admin"])
        assert client.get("/api/v1/sync/status").status_code == 200

        _override_user(client, ["qc_manager"])
        assert client.get("/api/v1/sync/status").status_code == 200

        _override_user(client, ["doctor"])
        assert client.get("/api/v1/sync/status").status_code == 403

    def test_write_permission_matrix(self, client):
        _override_user(client, ["qc_manager"])
        resp = client.post("/api/v1/sync/preflight", json={"source": "pg", "tier": "all"})
        assert resp.status_code == 403

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
            json={"remote_host": "10.10.10.8", "remote_port": 5433, "remote_password": ""},
        )
        assert resp.status_code == 200
        data = _assert_success_shell(resp.json())
        assert saved_holder["value"]["remote_host"] == "10.10.10.8"
        assert saved_holder["value"]["remote_port"] == "5433"
        assert saved_holder["value"]["remote_password"] == "secret"
        assert saved_holder["runtime_password"] is None
        assert data["config"]["remote_password_set"] is True
        assert any(call.get("action") == "sync.config.pg.update" for call in audit_calls)

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
        monkeypatch.setattr("app.services.etl_sync.get_sync_state", lambda: {"total_records_synced": 888})
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

        resp = client.post("/api/v1/sync/preflight", json={"source": "pg", "tables": ["mr"]})
        assert resp.status_code == 200
        data = _assert_success_shell(resp.json())
        assert data["source"] == "pg"
        assert data["executable"] is True
        assert data["estimated_impact"] == 888

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
                result={"success": True, "total_records": 2},
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
        assert calls["run"] == 1
        assert calls["append"] == 1

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
