"""
数据同步路由单元测试（PG-only）。
"""

from __future__ import annotations

import pytest

from app.core.access_control import enforce_default_auth
from app.core.security import get_current_user
from app.routers import sync as sync_router_module
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
                "error": "同步执行失败",
                "total_records": 0,
                "warnings": [],
                "tables": [],
            },
        )

        response = client.post(
            "/api/v1/sync/trigger",
            json={"source": "pg", "tier": "all"},
        )

        assert response.status_code == 200
        _assert_error_shell(response.json(), expected_code="SYNC_TRIGGER_FAILED")
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
