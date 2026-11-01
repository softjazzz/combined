"""控制HTTP只受理任务，不运行源读取；全部使用内存仓储与虚构凭据。"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
from uuid import uuid4

import pytest

pytest.importorskip("fastapi")
from fastapi.testclient import TestClient  # noqa: E402

from medqc_ingest.control.admission import AdmissionService  # noqa: E402
from medqc_ingest.control.api import create_app, public_unit  # noqa: E402
from medqc_ingest.control.auth import TokenAuth  # noqa: E402
from medqc_ingest.control.memory import MemoryJobRepository  # noqa: E402
from medqc_ingest.control.models import Actor, ControlError  # noqa: E402
from medqc_ingest.control.profiles import ProfileCatalog  # noqa: E402

NOW = datetime(2026, 10, 29, 0, 0, tzinfo=timezone.utc)
TOKENS = {
    name: (name + "-fictional-token-").ljust(40, "x") for name in ("reader", "runner", "planner")
}


@pytest.fixture
def context():
    repository = MemoryJobRepository(clock=lambda: NOW)
    catalog = ProfileCatalog()
    admission = AdmissionService(catalog, repository, clock=lambda: NOW)
    auth = TokenAuth(
        {
            TOKENS[name]: Actor(name, frozenset({permission}))
            for name, permission in (("reader", "read"), ("runner", "run"), ("planner", "schedule"))
        }
    )
    app = create_app(admission, repository, auth, catalog, clock=lambda: NOW)
    return TestClient(app, raise_server_exceptions=False), repository


def headers(role="runner", key=None):
    result = {"Authorization": "Bearer " + TOKENS[role]}
    if key is not None:
        result["Idempotency-Key"] = key
    return result


def payload():
    return {
        "profile": "core13",
        "interfaces": ["web.mr"],
        "mode": "replay",
        "start_date": "2026-10-26",
        "end_date": "2026-10-28",
        "publish": True,
    }


def schedule():
    return {
        "request": {
            "profile": "core13",
            "interfaces": ["web.mr"],
            "mode": "replay",
            "publish": True,
        },
        "frequency": "daily",
        "local_time": "01:00",
        "window_days": 1,
        "timezone": "Asia/Shanghai",
    }


def test_health_has_no_source_probe_and_readiness_requires_auth(context):
    client, repo = context
    assert client.get("/health/live").json() == {"live": True}
    assert client.get("/health/ready").status_code == 401
    assert client.get("/health/ready", headers=headers("reader")).json() == {"ready": True}
    assert repo.list_jobs() == []


def test_submit_async_idempotent_and_no_job_execution(context):
    client, repo = context
    first = client.post("/v1/jobs", json=payload(), headers=headers(key="request-1"))
    second = client.post("/v1/jobs", json=payload(), headers=headers(key="request-1"))
    assert first.status_code == second.status_code == 202
    assert first.json()["job_id"] == second.json()["job_id"]
    assert first.json()["status"] == "queued"
    assert len(repo.list_jobs()) == 1
    assert all(unit["status"] == "queued" for unit in repo.units(first.json()["job_id"]))


def test_same_idempotency_key_different_request_is_conflict(context):
    client, _ = context
    assert (
        client.post("/v1/jobs", json=payload(), headers=headers(key="same-key")).status_code == 202
    )
    changed = dict(payload(), end_date="2026-10-27")
    assert client.post("/v1/jobs", json=changed, headers=headers(key="same-key")).status_code == 409


def test_reader_cannot_mutate_and_actor_header_is_not_trusted(context):
    client, repo = context
    assert (
        client.post("/v1/jobs", json=payload(), headers=headers("reader", "deny")).status_code
        == 403
    )
    allowed = dict(headers(key="allow"), **{"X-Actor-Id": "spoofed"})
    result = client.post("/v1/jobs", json=payload(), headers=allowed)
    assert result.status_code == 202
    assert repo.get_job(result.json()["job_id"])["actor_id"] == "runner"
    assert (
        client.post("/v1/schedules", json=schedule(), headers=headers("runner")).status_code == 403
    )


def test_unsafe_fields_rejected_without_echoing_values(context):
    client, repo = context
    data = dict(payload(), password="fictional-private-password", payload="fictional-patient-body")
    result = client.post("/v1/jobs", json=data, headers=headers(key="unsafe"))
    assert result.status_code == 400
    assert "fictional-private" not in result.text and "fictional-patient" not in result.text
    assert repo.list_jobs() == []


def test_framework_validation_and_json_error_do_not_echo_input(context):
    client, _ = context
    for body in ('["fictional-private-password"]', '{"secret":"fictional-private-password"'):
        result = client.post(
            "/v1/jobs",
            content=body,
            headers=dict(headers(key="bad-json"), **{"Content-Type": "application/json"}),
        )
        assert result.status_code == 422
        assert "fictional-private-password" not in result.text


def test_job_detail_omits_internal_tokens_and_raw_fields(context):
    client, repo = context
    result = client.post("/v1/jobs", json=payload(), headers=headers(key="detail"))
    identifier = result.json()["job_id"]
    claimed = repo.claim("worker")
    assert claimed["lease_token"]
    detail = client.get("/v1/jobs/" + identifier, headers=headers("reader"))
    assert detail.status_code == 200
    assert "lease_token" not in detail.text and "request_hash" not in detail.text
    assert len(detail.json()["units"]) == 4
    assert client.get("/v1/jobs/" + str(uuid4()), headers=headers("reader")).status_code == 404


def test_cancel_is_audited_but_retry_of_active_is_rejected(context):
    client, _ = context
    result = client.post("/v1/jobs", json=payload(), headers=headers(key="cancel"))
    identifier = result.json()["job_id"]
    assert client.post(f"/v1/jobs/{identifier}/retry", headers=headers()).status_code == 409
    cancelled = client.post(f"/v1/jobs/{identifier}/cancel", headers=headers())
    assert cancelled.status_code == 200
    assert cancelled.json()["status"] == "cancelled"


def test_schedule_creation_disabled_enable_versions_and_no_auto_job(context):
    client, repo = context
    response = client.post("/v1/schedules", json=schedule(), headers=headers("planner"))
    assert response.status_code == 201
    created = response.json()
    assert created["enabled"] is False and created["next_fire_at"] is None
    identifier = created["schedule_id"]
    enabled = client.post(
        f"/v1/schedules/{identifier}/enable", json={"version": 1}, headers=headers("planner")
    )
    assert enabled.status_code == 200
    assert enabled.json()["enabled"] is True and enabled.json()["next_fire_at"]
    assert (
        client.post(
            f"/v1/schedules/{identifier}/disable", json={"version": 1}, headers=headers("planner")
        ).status_code
        == 409
    )
    assert repo.list_jobs() == []


def test_schedule_weekly_daily_transition_removes_stale_weekday(context):
    client, _ = context
    weekly = dict(schedule(), frequency="weekly", weekday=2)
    created = client.post("/v1/schedules", json=weekly, headers=headers("planner")).json()
    identifier = created["schedule_id"]
    changed = client.patch(
        f"/v1/schedules/{identifier}",
        json={"version": 1, "changes": {"frequency": "daily"}},
        headers=headers("planner"),
    )
    assert changed.status_code == 200
    assert "weekday" not in changed.json()["config"]
    weekly_again = client.patch(
        f"/v1/schedules/{identifier}",
        json={"version": 2, "changes": {"frequency": "weekly", "weekday": 4}},
        headers=headers("planner"),
    )
    assert weekly_again.status_code == 200
    assert weekly_again.json()["config"]["weekday"] == 4


def test_schedule_rejects_unapproved_interfaces_or_enable_on_create(context):
    client, _ = context
    for config in (
        dict(schedule(), enabled=True),
        dict(schedule(), request={"profile": "core13", "interfaces": ["web.admission_record"]}),
        dict(schedule(), local_time="25:00"),
        dict(schedule(), window_days=60),
    ):
        result = client.post("/v1/schedules", json=config, headers=headers("planner"))
        assert result.status_code in {400, 422}


def test_weekly_mr_sixty_day_replay_is_configurable_but_still_disabled(context):
    client, repo = context
    configuration = dict(schedule(), frequency="weekly", weekday=6, window_days=60)
    result = client.post("/v1/schedules", json=configuration, headers=headers("planner"))
    assert result.status_code == 201
    assert result.json()["config"]["window_days"] == 60
    assert result.json()["enabled"] is False and result.json()["next_fire_at"] is None
    assert repo.list_jobs() == []
    assert (
        client.post(
            "/v1/schedules", json=dict(configuration, window_days=61), headers=headers("planner")
        ).status_code
        == 422
    )


def test_generic_repository_errors_do_not_leak_messages(context, monkeypatch):
    client, repo = context

    def unavailable(*_args, **_kwargs):
        raise RuntimeError("fictional-private-password body DSN")

    monkeypatch.setattr(repo, "list_jobs", unavailable)
    result = client.get("/v1/jobs", headers=headers("reader"))
    assert result.status_code == 503
    assert "fictional-private" not in result.text


def test_token_file_binds_roles_without_retaining_raw_token():
    with TemporaryDirectory() as root:
        path = Path(root) / "tokens.json"
        path.write_text(
            json.dumps(
                {
                    "tokens": [
                        {"token": TOKENS["reader"], "actor_id": "operator", "permissions": ["read"]}
                    ]
                }
            ),
            encoding="utf-8",
        )
        auth = TokenAuth.from_file(path)
        assert auth.authenticate("Bearer " + TOKENS["reader"]).actor_id == "operator"
        assert TOKENS["reader"] not in repr(auth.__dict__)
        with pytest.raises(ControlError):
            auth.authenticate("Bearer fictional-invalid-token")
        path.write_text(json.dumps({"tokens": [{"token": "secret"}]}), encoding="utf-8")
        with pytest.raises(ControlError) as caught:
            TokenAuth.from_file(path)
        assert "secret" not in str(caught.value)


def test_bad_token_and_identifier_paths_are_controlled(context):
    client, _ = context
    assert client.get("/v1/jobs", headers={"Authorization": "Bearer no"}).status_code == 401
    assert client.get("/v1/jobs/not-a-uuid", headers=headers("reader")).status_code == 422
    assert client.get("/v1/jobs?limit=10000", headers=headers("reader")).status_code == 422


def test_failed_unit_exposes_controlled_codes_without_raw_exception():
    value = public_unit(
        {
            "unit_id": str(uuid4()),
            "status": "source_limited",
            "result": {
                "error_kind": "source_query_error",
                "error_location": "odbc_call",
                "sqlstate": "HY000",
                "native": 400,
                "source_limited": True,
                "message": "fictional-private-patient-body",
            },
        }
    )
    assert value["result"]["sqlstate"] == "HY000"
    assert value["result"]["error_kind"] == "source_query_error"
    assert "fictional-private" not in json.dumps(value)
