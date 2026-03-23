"""
数据同步路由单元测试
"""

from __future__ import annotations

from dataclasses import asdict

import pytest

from app.core.security import get_current_user
from app.services.etl_config import MongoSyncConfig


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
        assert saved_holder["value"]["lookback_minutes"] == 15
        assert saved_holder["value"]["rescan_recent_days"] == 5
        assert saved_holder["value"]["enabled"] is True

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

        def _fake_save_db_config(cfg):
            saved_holder["value"] = dict(cfg)
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
        body = resp.json()
        assert body["success"] is True
        assert saved_holder["value"]["remote_host"] == "10.10.10.8"
        assert saved_holder["value"]["remote_port"] == "5433"
        # 空密码应保留旧密码
        assert saved_holder["value"]["remote_password"] == "secret"
        assert body["config"]["remote_password_set"] is True

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
        body = resp.json()
        assert body["connected_count"] == 2
        assert body["all_connected"] is False
        assert body["mongo"]["connected"] is True

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
        body = resp.json()
        assert body["executable"] is False
        assert any("总开关已关闭" in item for item in body["blockers"])
        assert any("mongo_uri 未配置" in item for item in body["blockers"])

    def test_preflight_pg_success(self, client, monkeypatch):
        _override_user(client, ["admin"])
        monkeypatch.setattr("app.services.etl_sync.test_remote_connection", lambda: {"connected": True, "error": ""})
        monkeypatch.setattr("app.services.etl_sync.test_local_connection", lambda: {"connected": True, "error": ""})
        monkeypatch.setattr("app.services.etl_sync.get_sync_state", lambda: {"total_records_synced": 123})

        resp = client.post("/api/v1/sync/preflight", json={"source": "pg", "tables": ["mr"]})
        assert resp.status_code == 200
        body = resp.json()
        assert body["source"] == "pg"
        assert body["executable"] is True
        assert body["estimated_impact"] == 123

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
        assert body["success"] is False
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
        assert resp.json()["success"] is True
        assert captured["record"]["source"] == "mongo"
        assert captured["record"]["tier"] == "tier1"
        assert captured["record"]["status"] == "success"
        assert captured["record"]["operator"]["email"] == "sync@test.local"

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
        body = resp.json()
        assert body["total"] == 1
        assert body["limit"] == 20
        assert body["items"][0]["source"] == "mongo"
        assert body["items"][0]["tier"] == "tier2"
