"""
数据同步路由单元测试
"""

from __future__ import annotations

from dataclasses import asdict

import pytest

from app.core.access_control import enforce_default_auth
from app.core.security import get_current_user
from app.services.etl_config import MongoSyncConfig
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
    if expected_code is not None:
        assert body.get("code") == expected_code


def _override_user(client, roles: list[str]):
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
        monkeypatch.setattr("app.services.etl_sync.get_sync_state", lambda: {"is_running": False})
        monkeypatch.setattr("app.services.mongo_sync.get_mongo_sync_state", lambda: {"connected": True})

        _override_user(client, ["admin"])
        resp_admin = client.get("/api/v1/sync/status")
        assert resp_admin.status_code == 200

        _override_user(client, ["qc_manager"])
        resp_manager = client.get("/api/v1/sync/status")
        assert resp_manager.status_code == 200

        _override_user(client, ["doctor"])
        resp_doctor = client.get("/api/v1/sync/status")
        assert resp_doctor.status_code == 403

        client.app.dependency_overrides.clear()
        resp_anonymous = client.get("/api/v1/sync/status")
        assert resp_anonymous.status_code in (401, 403)

    def test_write_permission_matrix(self, client):
        _override_user(client, ["qc_manager"])
        resp_manager = client.post("/api/v1/sync/trigger", json={"source": "mongo", "tier": "all"})
        assert resp_manager.status_code == 403

    def test_update_mongo_config_fields_and_validation(self, client, monkeypatch):
        _override_user(client, ["admin"])

        invalid_resp = client.put("/api/v1/sync/config/mongo", json={"lookback_minutes": -1})
        assert invalid_resp.status_code == 422

        saved_holder = {}

        monkeypatch.setattr("app.services.etl_config.load_mongo_config", lambda: MongoSyncConfig())

        def _fake_save_mongo_config(cfg):
            saved_holder["value"] = asdict(cfg)
            return asdict(cfg)

        monkeypatch.setattr("app.services.etl_config.save_mongo_config", _fake_save_mongo_config)

        payload = {
            "connect_timeout_ms": 8000,
            "lookback_minutes": 15,
            "rescan_recent_days": 5,
            "tier1_interval_minutes": 20,
            "tier2_interval_minutes": 90,
            "tier3_cron": "0 1 * * *",
            "max_batch_size": 120,
            "inter_request_delay_ms": 250,
            "night_window_start": "23:00",
            "night_window_end": "05:00",
            "enabled": True,
        }
        resp = client.put("/api/v1/sync/config/mongo", json=payload)
        assert resp.status_code == 200
        data = _assert_success_shell(resp.json())
        assert saved_holder["value"]["lookback_minutes"] == 15
        assert saved_holder["value"]["rescan_recent_days"] == 5
        assert saved_holder["value"]["enabled"] is True
        assert "config" in data

    def test_update_pg_config(self, client, monkeypatch):
        _override_user(client, ["admin"])

        base_cfg = {
            "remote_host": "127.0.0.1",
            "remote_port": "5432",
            "remote_database": "dhc-app",
            "remote_username": "tester",
            "remote_password": "secret",
        }
        saved_holder = {}

        monkeypatch.setattr("app.services.etl_sync.load_db_config", lambda: dict(base_cfg))
        monkeypatch.setattr("app.services.etl_sync.test_remote_connection", lambda: {"connected": True, "error": ""})
        audit_calls: list[dict] = []
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
            },
        )
        assert resp.status_code == 200
        data = _assert_success_shell(resp.json())
        assert saved_holder["value"]["remote_host"] == "10.10.10.8"
        assert saved_holder["value"]["remote_port"] == "5433"
        # 空密码应保留旧密码
        assert saved_holder["value"]["remote_password"] == "secret"
        assert saved_holder["runtime_password"] is None
        assert data["config"]["remote_password_set"] is True
        assert any(
            call.get("action") == "sync.config.pg.update"
            and call.get("resource") == "/api/v1/sync/config/pg"
            for call in audit_calls
        )

    def test_test_connection_all(self, client, monkeypatch):
        _override_user(client, ["admin"])

        monkeypatch.setattr(
            "app.services.etl_config.load_mongo_config",
            lambda: MongoSyncConfig(mongo_uri="mongodb://127.0.0.1:27017/admin", enabled=True),
        )

        class _FakeMongoConnector:
            def __init__(self, *args, **kwargs):
                pass

            def test_connection(self):
                return {"connected": True, "version": "7.0"}

            def close(self):
                return None

        monkeypatch.setattr("app.services.mongo_sync.MongoConnector", _FakeMongoConnector)
        monkeypatch.setattr("app.services.etl_sync.test_remote_connection", lambda: {"connected": True})
        monkeypatch.setattr("app.services.etl_sync.test_local_connection", lambda: {"connected": False, "error": "local down"})

        resp = client.post("/api/v1/sync/test-connection/all")
        assert resp.status_code == 200
        data = _assert_success_shell(resp.json())
        assert data["connected_count"] == 2
        assert data["all_connected"] is False
        assert data["mongo"]["connected"] is True

    def test_preflight_mongo_blockers(self, client, monkeypatch):
        _override_user(client, ["admin"])

        monkeypatch.setattr(
            "app.services.etl_config.load_mongo_config",
            lambda: MongoSyncConfig(
                mongo_uri="",
                enabled=False,
                tier3_cron="",
            ),
        )
        monkeypatch.setattr("app.services.mongo_sync.get_sync_statistics", lambda: {"PENDING": 10, "PARTIAL": 2, "STALE": 1, "FAILED": 0})
        monkeypatch.setattr("app.services.mongo_sync.get_mongo_sync_state", lambda: {"is_running": False})

        resp = client.post("/api/v1/sync/preflight", json={"source": "mongo", "tier": "tier3"})
        assert resp.status_code == 200
        data = _assert_success_shell(resp.json())
        assert data["executable"] is False
        assert any("总开关已关闭" in item for item in data["blockers"])
        assert any("mongo_uri 未配置" in item for item in data["blockers"])

    def test_preflight_pg_success(self, client, monkeypatch):
        _override_user(client, ["admin"])
        monkeypatch.setattr("app.services.etl_sync.test_remote_connection", lambda: {"connected": True, "error": ""})
        monkeypatch.setattr("app.services.etl_sync.test_local_connection", lambda: {"connected": True, "error": ""})
        monkeypatch.setattr("app.services.etl_sync.get_sync_state", lambda: {"total_records_synced": 123})

        resp = client.post("/api/v1/sync/preflight", json={"source": "pg", "tables": ["mr"]})
        assert resp.status_code == 200
        data = _assert_success_shell(resp.json())
        assert data["source"] == "pg"
        assert data["executable"] is True
        assert data["estimated_impact"] == 123

    def test_trigger_concurrency_guard_passthrough(self, client, monkeypatch):
        _override_user(client, ["admin"])
        append_called = {"value": False}

        def _fake_append(_record):
            append_called["value"] = True

        monkeypatch.setattr("app.services.sync_run_history.append_sync_run_record", _fake_append)
        monkeypatch.setattr("app.services.mongo_sync.run_mongo_sync", lambda tier="all": {"success": False, "error": "同步正在进行中"})

        resp = client.post("/api/v1/sync/trigger", json={"source": "mongo", "tier": "all"})
        assert resp.status_code == 200
        body = resp.json()
        _assert_error_shell(body, expected_code="SYNC_ALREADY_RUNNING")
        assert "同步正在进行中" in body["error"]
        assert append_called["value"] is False

    def test_trigger_write_history(self, client, monkeypatch):
        _override_user(client, ["admin"])
        captured = {}

        def _fake_append(record):
            captured["record"] = record

        monkeypatch.setattr("app.services.sync_run_history.append_sync_run_record", _fake_append)
        monkeypatch.setattr(
            "app.services.mongo_sync.run_mongo_sync",
            lambda tier="all": {"success": True, "results": {"tier1": {"synced": 2}}},
        )

        resp = client.post("/api/v1/sync/trigger", json={"source": "mongo", "tier": "tier1"})
        assert resp.status_code == 200
        data = _assert_success_shell(resp.json())
        assert data["success"] is True
        assert captured["record"]["source"] == "mongo"
        assert captured["record"]["tier"] == "tier1"
        assert captured["record"]["status"] == "success"
        assert captured["record"]["operator"]["email"] == "sync@test.local"

    def test_trigger_idempotency_reuses_existing_run_id(self, client, monkeypatch):
        _override_user(client, ["admin"])
        calls = {"reserve": 0, "run": 0}
        audit_calls: list[dict] = []

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
                result={"success": True, "results": {"tier1": {"synced": 2}}},
            )

        monkeypatch.setattr("app.services.sync_idempotency.reserve_sync_trigger", _fake_reserve)
        monkeypatch.setattr("app.services.sync_idempotency.complete_sync_trigger", lambda **_kwargs: None)
        monkeypatch.setattr("app.services.sync_run_history.append_sync_run_record", lambda _record: None)
        monkeypatch.setattr(
            "app.routers.sync.audit_event",
            lambda _request, **kwargs: audit_calls.append(kwargs),
        )

        def _fake_run_mongo_sync(tier="all"):
            calls["run"] += 1
            return {"success": True, "results": {"tier1": {"synced": 2}}}

        monkeypatch.setattr("app.services.mongo_sync.run_mongo_sync", _fake_run_mongo_sync)

        first = client.post("/api/v1/sync/trigger", json={"source": "mongo", "tier": "tier1"})
        assert first.status_code == 200
        first_data = _assert_success_shell(first.json())
        assert first_data["run_id"] == "syncrun-fixed-id"
        assert first_data["idempotent_reused"] is False

        second = client.post("/api/v1/sync/trigger", json={"source": "mongo", "tier": "tier1"})
        assert second.status_code == 200
        second_data = _assert_success_shell(second.json())
        assert second_data["run_id"] == "syncrun-fixed-id"
        assert second_data["idempotent_reused"] is True
        assert calls["run"] == 1
        assert any(call.get("outcome") == "success" for call in audit_calls)
        assert any(call.get("outcome") == "reused" for call in audit_calls)

    def test_get_runs(self, client, monkeypatch):
        _override_user(client, ["qc_manager"])

        monkeypatch.setattr(
            "app.services.sync_run_history.list_sync_run_records",
            lambda source=None, tier=None, limit=50: {
                "items": [{"id": "r1", "source": source or "mongo", "tier": tier or "all"}],
                "total": 1,
                "limit": limit,
            },
        )

        resp = client.get("/api/v1/sync/runs", params={"source": "mongo", "tier": "tier2", "limit": 20})
        assert resp.status_code == 200
        data = _assert_success_shell(resp.json())
        assert data["total"] == 1
        assert data["limit"] == 20
        assert data["items"][0]["source"] == "mongo"
        assert data["items"][0]["tier"] == "tier2"

    def test_get_templates_permissions(self, client):
        _override_user(client, ["qc_manager"])
        resp_manager = client.get("/api/v1/sync/templates")
        assert resp_manager.status_code == 200

        _override_user(client, ["doctor"])
        resp_doctor = client.get("/api/v1/sync/templates")
        assert resp_doctor.status_code == 403

    def test_apply_template_success(self, client, monkeypatch):
        _override_user(client, ["admin"])
        saved_holder = {}

        monkeypatch.setattr("app.services.etl_config.load_mongo_config", lambda: MongoSyncConfig())

        def _fake_save_mongo_config(cfg):
            saved_holder["value"] = asdict(cfg)
            return asdict(cfg)

        monkeypatch.setattr("app.services.etl_config.save_mongo_config", _fake_save_mongo_config)

        resp = client.post(
            "/api/v1/sync/templates/apply",
            json={
                "template_id": "single_department_focus",
                "departments": ["心内科"],
            },
        )
        assert resp.status_code == 200
        data = _assert_success_shell(resp.json())
        assert data["template_id"] == "single_department_focus"
        assert saved_holder["value"]["target_departments"] == ["心内科"]

    def test_apply_template_validation(self, client):
        _override_user(client, ["admin"])

        resp_empty = client.post(
            "/api/v1/sync/templates/apply",
            json={
                "template_id": "multi_department_joint",
                "departments": [],
            },
        )
        assert resp_empty.status_code == 422

        resp_mixed_star = client.post(
            "/api/v1/sync/templates/apply",
            json={
                "template_id": "multi_department_joint",
                "departments": ["*", "心内科"],
            },
        )
        assert resp_mixed_star.status_code == 422

    def test_get_departments_from_mongo(self, client, monkeypatch):
        _override_user(client, ["qc_manager"])

        monkeypatch.setattr(
            "app.services.etl_config.load_mongo_config",
            lambda: MongoSyncConfig(mongo_uri="mongodb://127.0.0.1:27017/admin", enabled=True),
        )

        class _FakeCollection:
            @staticmethod
            def distinct(_field):
                return ["心内科", "", None, "呼吸内科", "心内科"]

        class _FakeDb(dict):
            def __getitem__(self, item):
                if item == "mr":
                    return _FakeCollection()
                raise KeyError(item)

        class _FakeMongoConnector:
            def __init__(self, *args, **kwargs):
                pass

            def get_db(self):
                return _FakeDb()

            def close(self):
                return None

        monkeypatch.setattr("app.services.mongo_sync.MongoConnector", _FakeMongoConnector)

        resp = client.get("/api/v1/sync/departments")
        assert resp.status_code == 200
        data = _assert_success_shell(resp.json())
        assert data["total"] == 2
        assert data["items"] == ["呼吸内科", "心内科"]

    def test_get_departments_requires_mongo_uri(self, client, monkeypatch):
        _override_user(client, ["admin"])
        monkeypatch.setattr(
            "app.services.etl_config.load_mongo_config",
            lambda: MongoSyncConfig(mongo_uri="", enabled=True),
        )
        resp = client.get("/api/v1/sync/departments")
        assert resp.status_code == 422
