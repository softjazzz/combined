"""只用内存SQLite和HTTP固定应答；由严格离线入口运行。"""
from __future__ import annotations

import asyncio
import json
from uuid import uuid4

from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
import httpx
import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database.models.v36_reports import SysUser
from app.routers import data_pipelines as api
from app.services import data_pipeline_settings as settings
from app.services import sync_control_client as control

JOB_ID = "00112233-4455-6677-8899-aabbccddeeff"


def capabilities(**changes):
    return {"permissions": ["read", "run", "schedule"], "timezone": "Asia/Shanghai",
            "last_complete_date": "2026-11-09", "max_manual_days": 7,
            "features": {"schedule_drafts": True, "schedule_controls": False, "date_recovery_profiles": []}, **changes}


@pytest.fixture(autouse=True)
def environment(monkeypatch):
    monkeypatch.setenv("SYNC_CONTROL_API_URL", "http://sync.invalid:8766")
    monkeypatch.setenv("SYNC_CONTROL_API_TOKEN", "test-only-private-token")
    monkeypatch.setenv("SYNC_CONTROL_PROFILE", "accepted_manual")
    monkeypatch.delenv("CDM_DATABASE_URL", raising=False)
    monkeypatch.delenv("CDM_PGPASSFILE", raising=False)


@pytest.fixture
def database(monkeypatch):
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    sessions = sessionmaker(bind=engine)
    SysUser.__table__.create(engine)
    with engine.begin() as connection:
        connection.execute(text("""CREATE TABLE sync_config_registry
            (namespace TEXT, config_key TEXT, payload_json TEXT, updated_by TEXT, source TEXT,
            change_reason TEXT, updated_at TEXT, PRIMARY KEY(namespace,config_key))"""))
    monkeypatch.setattr(settings, "TABLE", "sync_config_registry")
    monkeypatch.setattr(api, "SessionLocal", sessions)
    monkeypatch.setattr(api, "audit_event", lambda *a, **kw: None)
    with sessions() as session:
        for name, roles, active in [("manager", '["qc_manager"]', True), ("doctor", '["doctor"]', True),
            ("sync", '["sync_admin"]', True), ("admin", '["admin"]', True),
            ("broken", '{bad', True), ("disabled", '["admin"]', False)]:
            session.add(SysUser(id=name, username=name, display_name=name, role="admin", roles_json=roles, is_active=active))
        session.commit()
    yield sessions
    engine.dispose()


def client_for(actor="admin"):
    app = FastAPI()
    app.include_router(api.router)
    app.dependency_overrides[api.get_current_user] = lambda: {"id": actor, "roles": ["admin", "sync_admin"]}
    app.dependency_overrides[api.require_product_activation] = lambda: None
    return TestClient(app)


def raw_job(**changes):
    return {"job_id": JOB_ID, "status": "queued", "request": {"profile": "accepted_manual", "mode": "replay", "publish": True}, **changes}


def test_default_does_not_enable_or_probe_either_service(database, monkeypatch):
    async def forbidden(*a, **kw):
        pytest.fail("配置读取/保存不能发起网络")
    monkeypatch.setattr(control, "request", forbidden)
    with client_for() as client:
        result = client.get("/api/v1/sync/pipelines").json()["data"]
        assert result["settings"] == {"version": 0, "default_pipeline": "legacy_pg", "independent_enabled": False}
        assert result["runtime"]["clinical_read_source"] == "business_cdm"
        assert result["runtime"]["automatic_extraction"] is False
        assert result["runtime"]["automatic_qc"] is False
        saved = client.put("/api/v1/sync/pipelines", json={"version": 0, "default_pipeline": "independent_cdm", "independent_enabled": True})
        assert saved.status_code == 200
        assert saved.json()["data"]["settings"]["version"] == 1
        assert saved.json()["data"]["runtime"]["clinical_read_source"] == "business_cdm"
        assert "test-only-private-token" not in saved.text


@pytest.mark.parametrize("actor", ["manager", "doctor", "broken", "disabled", "missing"])
def test_http_admin_claim_cannot_override_persistent_account(database, actor):
    with client_for(actor) as client:
        assert client.get("/api/v1/sync/pipelines").status_code == 403
        assert client.post("/api/v1/sync/pipelines/independent/check").status_code == 403


def test_persistent_sync_admin_has_configuration_permission(database):
    assert api.require_pipeline_admin({"id": "sync", "roles": []})["id"] == "sync"


def test_missing_account_owner_fails_closed(monkeypatch):
    monkeypatch.setattr(api, "SessionLocal", None)
    with pytest.raises(HTTPException) as exc:
        api.require_pipeline_admin({"id": "admin"})
    assert exc.value.status_code == 503


def test_invalid_cdm_config_is_visible_and_not_reported_as_old_database(monkeypatch):
    monkeypatch.setenv("CDM_PGPASSFILE", "/missing/private/passfile")
    status = settings.runtime_status()
    assert status["clinical_read_source"] == "independent_cdm"
    assert status["cdm_configuration_valid"] is False
    assert status["cdm_url_configured"] is False


def test_corrupt_configuration_is_not_legacy_default(database):
    with database() as session:
        session.execute(text("INSERT INTO sync_config_registry(namespace,config_key,payload_json) VALUES ('sync','data_pipelines_v1','{bad')"))
        session.commit()
    with client_for() as client:
        assert client.get("/api/v1/sync/pipelines").status_code == 503


def test_compare_and_swap_and_invalid_enablement(database, monkeypatch):
    with client_for() as client:
        assert client.put("/api/v1/sync/pipelines", json={"default_pipeline": "independent_cdm"}).status_code == 422
        assert client.put("/api/v1/sync/pipelines", json={"independent_enabled": True}).status_code == 200
        assert client.put("/api/v1/sync/pipelines", json={"version": 0}).status_code == 409
        monkeypatch.delenv("SYNC_CONTROL_API_TOKEN")
        assert client.put("/api/v1/sync/pipelines", json={"version": 1, "independent_enabled": True}).status_code == 503


@pytest.mark.parametrize("url", ["https://u:secret@sync.invalid", "file:///private", "http://sync.invalid/?token=private", "http://sync.invalid/#private", "http://sync.invalid/v1", "http://sync.invalid:bad"])
def test_fixed_deployment_url_rejects_credentials_and_override_paths(monkeypatch, url):
    monkeypatch.setenv("SYNC_CONTROL_API_URL", url)
    with pytest.raises(settings.PipelineError) as exc:
        control.deployment()
    assert "secret" not in str(exc.value)


def test_strict_request_shape_disabled_route_never_calls_remote(database, monkeypatch):
    async def forbidden(*a, **kw):
        pytest.fail("关闭链路不能提交任务")
    monkeypatch.setattr(control, "submit", forbidden)
    payload = {"operation_id": str(uuid4()), "start_date": "2020-10-26", "end_date": "2020-10-28", "interfaces": ["web.mr"]}
    with client_for() as client:
        assert client.post("/api/v1/sync/pipelines/independent/jobs", json=payload).status_code == 409
        assert client.post("/api/v1/sync/pipelines/independent/jobs", json={**payload, "auto_qc": True}).status_code == 422
        assert client.post("/api/v1/sync/pipelines/independent/jobs", json={**payload, "operation_id": "x" * 36}).status_code == 422


@pytest.mark.parametrize("start,end", [("2020-01-01", "2020-01-08"), ("2020-01-02", "2020-01-01"), ("2099-01-01", "2099-01-01"), ("2020-02-30", "2020-03-01")])
def test_date_scope_keeps_manual_seven_day_contract(start, end):
    with pytest.raises(settings.PipelineError):
        control.prepare_job(start_date=start, end_date=end, interfaces=["web.mr"], publish=True, dry=False, capabilities=capabilities())


def test_submit_reuses_remote_idempotency_key_and_respects_interface_allowlist(monkeypatch):
    calls = []
    async def fake(method, path, **kwargs):
        calls.append((method, path, kwargs))
        if path == "/v1/session":
            return capabilities()
        return {"profiles": [{"profile": "accepted_manual", "interfaces": ["web.mr"]}]} if path == "/v1/interfaces" else raw_job()
    monkeypatch.setattr(control, "request", fake)
    payload = control.prepare_job(start_date="2020-01-01", end_date="2020-01-02", interfaces=["web.mr"], publish=True, dry=False, capabilities=capabilities())
    operation_id = str(uuid4())
    asyncio.run(control.submit(payload, "admin", operation_id))
    asyncio.run(control.submit(payload, "admin", operation_id))
    posts = [entry for entry in calls if entry[0] == "POST"]
    assert len(posts) == 2 and posts[0][2]["key"] == posts[1][2]["key"]
    assert posts[0][2]["payload"] == payload
    assert "auto_qc" not in payload and "department" not in payload
    with pytest.raises(settings.PipelineError):
        asyncio.run(control.submit({**payload, "interfaces": ["web.unapproved"]}, "admin", operation_id))
    assert len([entry for entry in calls if entry[0] == "POST"]) == 2


@pytest.mark.parametrize("status", ["failed", "completed_with_source_limitations", "recovery_required", "running"])
def test_job_status_is_preserved_and_not_reinterpreted_as_success(status):
    result = control.public_job(raw_job(status=status, record_content="private", error={"code": "source_limited", "message": "private"}))
    assert result["status"] == status
    assert "private" not in json.dumps(result)
    assert result["error"]["code"] == "source_limited"


def test_profile_scope_cancel_and_retry_are_kept_separate(database, monkeypatch):
    calls = []
    profile = "accepted_manual"
    async def fake(method, path, **kwargs):
        calls.append((method, path))
        if path == "/v1/session":
            return capabilities()
        job = raw_job(request={"profile": profile})
        return {"jobs": [job, raw_job(request={"profile": "other"})]} if path.startswith("/v1/jobs?") else job
    monkeypatch.setattr(control, "request", fake)
    with client_for() as client:
        assert len(client.get("/api/v1/sync/pipelines/independent/jobs").json()["data"]["jobs"]) == 1
        assert client.post(f"/api/v1/sync/pipelines/independent/jobs/{JOB_ID}/retry").status_code == 409
        assert client.post(f"/api/v1/sync/pipelines/independent/jobs/{JOB_ID}/cancel").status_code == 200
        profile = "other"
        assert client.get(f"/api/v1/sync/pipelines/independent/jobs/{JOB_ID}").status_code == 403
    assert len([call for call in calls if call[0] == "POST"]) == 1


@pytest.mark.parametrize("scenario", ["ok", "timeout", "redirect", "upstream_500", "invalid_json", "oversize"])
def test_http_transport_is_bounded_sanitized_and_never_retried(monkeypatch, scenario):
    real_client = httpx.AsyncClient
    calls, client_options = [], []
    def handler(request):
        calls.append(request)
        assert request.headers["Authorization"] == "Bearer test-only-private-token"
        if scenario == "timeout":
            raise httpx.ReadTimeout("private server token", request=request)
        if scenario == "redirect":
            return httpx.Response(302, headers={"Location": "http://other.invalid/private"})
        if scenario == "upstream_500":
            return httpx.Response(500, text="private server token")
        if scenario == "invalid_json":
            return httpx.Response(200, text="private server token")
        if scenario == "oversize":
            return httpx.Response(200, content=b"x" * (control.MAX_RESPONSE_BYTES + 1))
        return httpx.Response(200, json={"ready": True})
    def factory(**kwargs):
        client_options.append(kwargs)
        return real_client(**kwargs, transport=httpx.MockTransport(handler))
    monkeypatch.setattr(control.httpx, "AsyncClient", factory)
    if scenario == "ok":
        assert asyncio.run(control.request("GET", "/health/ready")) == {"ready": True}
    else:
        with pytest.raises(settings.PipelineError) as exc:
            asyncio.run(control.request("POST", "/v1/jobs", payload={}, key="same-operation"))
        assert "private" not in str(exc.value)
    assert len(calls) == 1
    assert client_options[0]["trust_env"] is False
    assert client_options[0]["follow_redirects"] is False


def test_total_deadline_cancels_one_attempt_and_caller_cancel_is_not_swallowed(monkeypatch):
    calls, cancelled = [], []
    async def blocked(*args, **kwargs):
        calls.append(1)
        try:
            await asyncio.Event().wait()
        finally:
            cancelled.append(True)
    monkeypatch.setattr(control, "_request_once", blocked)
    monkeypatch.setattr(control, "TOTAL_REQUEST_TIMEOUT", 0.01)
    with pytest.raises(settings.PipelineError) as exc:
        asyncio.run(control.request("GET", "/v1/interfaces"))
    assert exc.value.status == 504 and len(calls) == 1 and cancelled == [True]
    async def caller_cancel():
        task = asyncio.create_task(control.request("GET", "/v1/interfaces"))
        await asyncio.sleep(0)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
    asyncio.run(caller_cancel())


def test_session_controls_dates_and_recovery_plan_without_local_seven_day_limit(monkeypatch):
    calls = []
    async def fake(method, path, **kwargs):
        calls.append((method, path, kwargs))
        if path == "/v1/session":
            return capabilities(max_manual_days=10, features={"date_recovery_profiles": ["accepted_manual"]})
        if path == "/v1/interfaces":
            return {"profiles": [{"profile": "accepted_manual", "interfaces": ["web.mr"]}]}
        return raw_job()
    monkeypatch.setattr(control, "request", fake)
    payload = {"start_date": "2026-11-01", "end_date": "2026-11-09", "interfaces": ["web.mr"], "mode": "replay", "publish": True}
    asyncio.run(control.submit(payload, "admin", str(uuid4())))
    posts = [c for c in calls if c[0] == "POST"]
    assert len(posts) == 1
    assert posts[0][2]["payload"]["plan_version"] == 2
    with pytest.raises(settings.PipelineError):
        control.prepare_job(**{k: v for k, v in payload.items() if k != "mode"}, dry=False,
            capabilities=capabilities(max_manual_days=2))


@pytest.mark.parametrize("change", [{"max_manual_days": 0}, {"last_complete_date": "bad"}, {"features": []}, {"permissions": ["owner"]}])
def test_invalid_capabilities_fail_closed(monkeypatch, change):
    async def fake(*a, **kw):
        return capabilities(**change)
    monkeypatch.setattr(control, "request", fake)
    with pytest.raises(settings.PipelineError, match="invalid_session"):
        asyncio.run(control.session())


def test_read_only_token_cannot_use_business_admin_to_run_or_save_draft(database, monkeypatch):
    writes = []
    async def fake(method, path, **kwargs):
        if method != "GET":
            writes.append(path)
        return capabilities(permissions=["read"]) if path == "/v1/session" else {"profiles": [{"profile": "accepted_manual", "interfaces": ["web.mr"]}]}
    monkeypatch.setattr(control, "request", fake)
    with client_for() as client:
        assert client.put("/api/v1/sync/pipelines", json={"independent_enabled": True}).status_code == 200
        assert client.post("/api/v1/sync/pipelines/independent/jobs", json={
            "operation_id": str(uuid4()), "start_date": "2020-01-01", "end_date": "2020-01-01", "interfaces": ["web.mr"],
        }).status_code == 403
        assert client.put(f"/api/v1/sync/pipelines/independent/schedule-drafts/{JOB_ID}", json=draft_payload()).status_code == 403
    assert writes == []


def draft_payload(version=None):
    return {"version": version, "config": {"frequency": "daily", "local_time": "02:00", "window_days": 2, "interfaces": ["web.mr"]}}


def schedule_row(enabled=False, version=1, profile="accepted_manual"):
    return {"schedule_id": JOB_ID, "version": version, "enabled": enabled, "next_fire_at": None,
            "config": {"frequency": "daily", "local_time": "02:00", "window_days": 2, "timezone": "Asia/Shanghai",
                       "request": {"profile": profile, "interfaces": ["web.mr"], "mode": "replay", "publish": True}}}


def test_disabled_draft_cas_and_admin_audit_without_enable_route(database, monkeypatch):
    calls, audits = [], []
    def audit(*args, **kwargs):
        audits.append(kwargs)
    monkeypatch.setattr(api, "audit_event", audit)
    async def fake(method, path, **kwargs):
        calls.append((method, path, kwargs))
        if path == "/v1/session":
            return capabilities()
        if path == "/v1/interfaces":
            return {"profiles": [{"profile": "accepted_manual", "interfaces": ["web.mr"]}]}
        return schedule_row(version=2 if method == "PUT" else 1)
    monkeypatch.setattr(control, "request", fake)
    with client_for() as client:
        result = client.put(f"/api/v1/sync/pipelines/independent/schedule-drafts/{JOB_ID}", json=draft_payload(1))
        assert result.status_code == 200, result.text
        assert result.json()["data"]["enabled"] is False
        assert client.post(f"/api/v1/sync/pipelines/independent/schedules/{JOB_ID}/enable").status_code in {404, 405}
        assert client.put(f"/api/v1/sync/pipelines/independent/schedule-drafts/{JOB_ID}", json={**draft_payload(), "enabled": True}).status_code == 422
    writes = [c for c in calls if c[0] != "GET"]
    assert len(writes) == 1
    assert writes[0][1] == f"/v1/schedule-drafts/{JOB_ID}"
    assert writes[0][2]["payload"]["version"] == 1
    assert "enabled" not in writes[0][2]["payload"]
    assert audits[-1]["current_user"]["id"] == "admin"
    assert audits[-1]["resource"] == JOB_ID


@pytest.mark.parametrize("scenario,expected", [("enabled", 409), ("other_profile", 403), ("conflict", 409)])
def test_draft_never_overwrites_enabled_foreign_or_conflicting_version(database, monkeypatch, scenario, expected):
    writes = []
    async def fake(method, path, **kwargs):
        if path == "/v1/session":
            return capabilities()
        if path == "/v1/interfaces":
            return {"profiles": [{"profile": "accepted_manual", "interfaces": ["web.mr"]}]}
        if method == "PUT":
            writes.append(kwargs["payload"])
            raise settings.PipelineError("schedule_version_conflict", 409)
        return schedule_row(enabled=scenario == "enabled", profile="other" if scenario == "other_profile" else "accepted_manual")
    monkeypatch.setattr(control, "request", fake)
    with client_for() as client:
        result = client.put(f"/api/v1/sync/pipelines/independent/schedule-drafts/{JOB_ID}", json=draft_payload(1))
        assert result.status_code == expected
    assert len(writes) == (1 if scenario == "conflict" else 0)


def test_detail_preserves_date_units_and_errors_but_never_clinical_text(database, monkeypatch):
    raw = raw_job(units=[{"unit_id": JOB_ID, "sequence": 1, "source_date": "2026-11-01", "interface_name": "web.mr",
        "status": "failed", "phase": "extract", "execution_attempts": 2, "record_content": "private body",
        "error": {"code": "source_error", "location": "extract", "retry_policy": "retryable", "message": "private body"},
        "result": {"counts": {"fetched": 0, "private": 1}, "raw": "private body"}}])
    async def fake(*a, **kw):
        return raw
    monkeypatch.setattr(control, "request", fake)
    with client_for() as client:
        result = client.get(f"/api/v1/sync/pipelines/independent/jobs/{JOB_ID}")
    assert result.status_code == 200
    unit = result.json()["data"]["units"][0]
    assert unit["source_date"] == "2026-11-01" and unit["result"]["counts"]["fetched"] == 0
    assert unit["error"]["retry_policy"] == "retryable"
    assert "private" not in result.text


def test_http_conflict_and_safe_error_are_not_swallowed_or_retried(monkeypatch):
    real = httpx.AsyncClient
    calls = []
    def handler(req):
        calls.append(req)
        return httpx.Response(409, json={"error": {"code": "schedule_version_conflict", "location": "schedule", "message": "private"}})
    monkeypatch.setattr(control.httpx, "AsyncClient", lambda **kw: real(**kw, transport=httpx.MockTransport(handler)))
    with pytest.raises(settings.PipelineError) as exc:
        asyncio.run(control.request("PUT", f"/v1/schedule-drafts/{JOB_ID}", payload=draft_payload(1)))
    assert exc.value.status == 409
    assert exc.value.public_details == {"code": "schedule_version_conflict", "location": "schedule"}
    assert len(calls) == 1


@pytest.mark.parametrize("change", [{"next_fire_at": 123}, {"enabled": "false"}, {"version": True}])
def test_malformed_draft_state_cannot_be_reported_as_saved_disabled(change):
    with pytest.raises(settings.PipelineError):
        control.public_schedule({**schedule_row(), **change})


def test_schedule_list_is_profile_bound_and_non_admin_cannot_access(database, monkeypatch):
    calls = []
    async def fake(method, path, **kw):
        calls.append(path)
        return {"schedules": [schedule_row(), schedule_row(profile="foreign")]}
    monkeypatch.setattr(control, "request", fake)
    with client_for() as client:
        result = client.get("/api/v1/sync/pipelines/independent/schedules")
        assert result.status_code == 200
        assert len(result.json()["data"]["schedules"]) == 1
    calls.clear()
    with client_for("doctor") as client:
        assert client.get("/api/v1/sync/pipelines/independent/schedules").status_code == 403
        assert client.put(f"/api/v1/sync/pipelines/independent/schedule-drafts/{JOB_ID}", json=draft_payload()).status_code == 403
    assert calls == []


def test_draft_missing_next_fire_at_remains_unconfirmed(database, monkeypatch):
    """复审反例：显式null能通过，字段缺失不能被投影补成已确认状态。"""
    async def fake(method, path, **kwargs):
        if path == "/v1/session":
            return capabilities()
        if path == "/v1/interfaces":
            return {"profiles": [{"profile": "accepted_manual", "interfaces": ["web.mr"]}]}
        row = schedule_row()
        row.pop("next_fire_at")
        return row
    monkeypatch.setattr(control, "request", fake)
    with client_for() as client:
        result = client.put(f"/api/v1/sync/pipelines/independent/schedule-drafts/{JOB_ID}", json=draft_payload())
    assert result.status_code == 502
    assert "invalid_schedule_response" in result.text


@pytest.mark.parametrize("counts", [{"selected": 12, "written": 0}, {"selected": 0, "written": 0}])
def test_publish_unit_top_level_counts_survive_detail(database, monkeypatch, counts):
    async def fake(*args, **kwargs):
        return raw_job(units=[{"unit_id": JOB_ID, "interface_name": "web.mr", "source_date": "2026-11-01",
            "phase": "publish", "status": "succeeded", "result": {**counts, "record_content": "private"}}])
    monkeypatch.setattr(control, "request", fake)
    with client_for() as client:
        result = client.get(f"/api/v1/sync/pipelines/independent/jobs/{JOB_ID}")
    assert result.status_code == 200
    assert result.json()["data"]["units"][0]["result"] == counts
    assert "private" not in result.text


def test_missing_or_invalid_publish_counts_are_not_fabricated_as_zero():
    for raw in ({}, {"selected": True, "written": -1}, {"selected": "12", "written": None}):
        result = control.public_unit({"phase": "publish", "result": raw})["result"]
        assert "selected" not in result and "written" not in result
