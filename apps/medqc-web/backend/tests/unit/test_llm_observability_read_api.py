from __future__ import annotations

import asyncio
from datetime import datetime, timezone

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.security import get_current_user
from app.routers.llm_observability_read import (
    get_llm_observability_read_service,
    router,
)
from app.services.llm_observability_read import (
    LLMObservabilityReadService,
    LLMObservabilityUnavailableError,
    PostgresLLMCallEventReader,
)


def _dt(value: str) -> datetime:
    return datetime.fromisoformat(value).replace(tzinfo=timezone.utc)


class _StaticEventReader:
    def __init__(self, rows: list[dict]):
        self.rows = rows
        self.filters: list[dict] = []

    async def fetch_events(self, **filters) -> list[dict]:
        self.filters.append(filters)
        return list(self.rows)


def _client(rows: list[dict], *, roles: list[str] | None = None, email: str = "ops@test.local"):
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_current_user] = lambda: {
        "id": "u-observability",
        "email": email,
        "roles": roles or ["admin"],
    }
    app.dependency_overrides[get_llm_observability_read_service] = lambda: (
        LLMObservabilityReadService(reader=_StaticEventReader(rows))
    )
    return TestClient(app)


def _event(**overrides) -> dict:
    row = {
        "event_id": "event-1",
        "logical_call_id": "logical-1",
        "attempt_no": 1,
        "started_at": _dt("2026-08-10T00:00:00"),
        "finished_at": _dt("2026-08-10T00:00:01"),
        "business_scene": "luxian_0609_qc",
        "root_job_id": "job-1",
        "record_key_hash": "record-hash-1",
        "rule_set_key": "luxian_0609_qc",
        "rule_set_version": "2026-06-09",
        "executor_key": "LX0609-025",
        "provider_code": "alibaba",
        "model": "qwen-plus",
        "model_role": "qc_fact_extractor",
        "status": "success",
        "safe_error_kind": None,
        "usage_state": "known",
        "input_tokens": 10,
        "output_tokens": 5,
        "total_tokens": 15,
        "latency_ms": 100,
        "worker_id": "worker-a",
    }
    row.update(overrides)
    return row


def test_overview_counts_logical_calls_attempts_unknown_usage_and_peak_concurrency():
    rows = [
        _event(),
        _event(
            event_id="event-2",
            attempt_no=2,
            started_at=_dt("2026-08-10T00:00:00.500000"),
            finished_at=_dt("2026-08-10T00:00:02"),
            status="timeout",
            safe_error_kind="timeout",
            usage_state="unknown",
            input_tokens=None,
            output_tokens=None,
            total_tokens=None,
            latency_ms=200,
        ),
        _event(
            event_id="event-3",
            logical_call_id="logical-2",
            record_key_hash="record-hash-2",
            started_at=_dt("2026-08-10T00:00:01.500000"),
            finished_at=_dt("2026-08-10T00:00:03"),
            usage_state="unknown",
            input_tokens=None,
            output_tokens=None,
            total_tokens=None,
            latency_ms=300,
        ),
    ]

    with _client(rows) as client:
        response = client.get("/api/v1/system/llm-observability/overview")

    assert response.status_code == 200
    kpis = response.json()["data"]["kpis"]
    assert kpis == {
        "logical_calls": 2,
        "http_attempts": 3,
        "record_count": 2,
        "input_tokens": 10,
        "output_tokens": 5,
        "total_tokens": 15,
        "avg_latency_ms": 200.0,
        "p95_latency_ms": 300,
        "peak_concurrency": 2,
        "retry_attempts": 1,
        "successful_attempts": 2,
        "failed_attempts": 1,
        "unknown_usage_attempts": 2,
    }


def test_overview_returns_frozen_sections_model_role_and_paginated_records():
    rows = [
        _event(record_key_hash="record-hash-1"),
        _event(
            event_id="event-2",
            logical_call_id="logical-2",
            record_key_hash="record-hash-2",
            provider_code="openai",
            model="gpt-5-mini",
            model_role="coding_assistant",
            started_at=_dt("2026-08-10T01:00:00"),
            finished_at=_dt("2026-08-10T01:00:01"),
        ),
    ]

    with _client(rows) as client:
        response = client.get(
            "/api/v1/system/llm-observability/overview",
            params={"page": 1, "page_size": 1},
        )

    assert response.status_code == 200
    data = response.json()["data"]
    assert set(data) == {"range", "kpis", "trends", "models", "safe_errors", "records"}
    assert {item["model_role"] for item in data["models"]} == {
        "qc_fact_extractor",
        "coding_assistant",
    }
    assert data["records"]["total"] == 2
    assert data["records"]["page"] == 1
    assert data["records"]["page_size"] == 1
    assert len(data["records"]["items"]) == 1
    assert data["range"]["timezone"] == "Asia/Shanghai"


def test_overview_keeps_token_totals_null_when_provider_reports_no_usage():
    rows = [
        _event(
            usage_state="unknown",
            input_tokens=None,
            output_tokens=None,
            total_tokens=None,
        )
    ]

    with _client(rows) as client:
        response = client.get("/api/v1/system/llm-observability/overview")

    assert response.status_code == 200
    kpis = response.json()["data"]["kpis"]
    assert kpis["input_tokens"] is None
    assert kpis["output_tokens"] is None
    assert kpis["total_tokens"] is None
    assert kpis["unknown_usage_attempts"] == 1


def test_empty_overview_reports_zero_volume_without_faking_unknown_usage():
    with _client([]) as client:
        response = client.get("/api/v1/system/llm-observability/overview")

    assert response.status_code == 200
    kpis = response.json()["data"]["kpis"]
    assert kpis["logical_calls"] == 0
    assert kpis["http_attempts"] == 0
    assert kpis["record_count"] == 0
    assert kpis["input_tokens"] == 0
    assert kpis["output_tokens"] == 0
    assert kpis["total_tokens"] == 0
    assert kpis["unknown_usage_attempts"] == 0


def test_record_calls_are_paginated_and_only_return_safe_attempt_fields():
    first = _event(
        prompt="不得返回的提示词",
        response="不得返回的模型正文",
        endpoint="https://secret.example/v1",
        api_key="secret-key",
        error_detail="数据库异常原文",
        patient_id="patient-raw",
        visit_id="visit-raw",
        institute_id="hospital-raw",
    )
    second = _event(
        event_id="event-2",
        logical_call_id="logical-2",
        started_at=_dt("2026-08-10T01:00:00"),
        finished_at=_dt("2026-08-10T01:00:01"),
        usage_state="unknown",
        input_tokens=None,
        output_tokens=None,
        total_tokens=None,
    )

    with _client([first, second]) as client:
        response = client.get(
            "/api/v1/system/llm-observability/records/record-hash-1/calls",
            params={"page": 1, "page_size": 1},
        )

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["total"] == 2
    assert data["page"] == 1
    assert data["page_size"] == 1
    assert len(data["items"]) == 1
    item = data["items"][0]
    assert set(item) == {
        "logical_call_id",
        "attempt_no",
        "business_scene",
        "root_job_id",
        "executor_key",
        "provider_code",
        "model",
        "model_role",
        "status",
        "safe_error_kind",
        "usage_state",
        "input_tokens",
        "output_tokens",
        "total_tokens",
        "latency_ms",
        "started_at",
        "finished_at",
    }
    assert item["input_tokens"] is None
    assert item["output_tokens"] is None
    assert item["total_tokens"] is None
    serialized = str(data)
    for forbidden in (
        "不得返回的提示词",
        "不得返回的模型正文",
        "secret.example",
        "secret-key",
        "数据库异常原文",
        "patient-raw",
        "visit-raw",
        "hospital-raw",
    ):
        assert forbidden not in serialized


def test_records_endpoint_returns_only_hashed_record_summaries_with_filters():
    rows = [
        _event(record_key_hash="record-hash-1"),
        _event(
            event_id="event-2",
            logical_call_id="logical-2",
            record_key_hash="record-hash-2",
            started_at=_dt("2026-08-10T01:00:00"),
            finished_at=_dt("2026-08-10T01:00:01"),
        ),
    ]

    with _client(rows) as client:
        response = client.get(
            "/api/v1/system/llm-observability/records",
            params={
                "business_scene": "luxian_0609_qc",
                "model": "qwen-plus",
                "page": 2,
                "page_size": 1,
            },
        )

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["range"]["business_scene"] == "luxian_0609_qc"
    assert data["range"]["model"] == "qwen-plus"
    assert data["total"] == 2
    assert data["page"] == 2
    assert data["page_size"] == 1
    assert len(data["items"]) == 1
    assert set(data["items"][0]) >= {
        "record_key_hash",
        "logical_calls",
        "http_attempts",
        "total_tokens",
        "last_called_at",
        "status",
    }


def test_stale_running_attempts_are_projected_as_abandoned_without_fake_overlap():
    rows = [
        _event(
            event_id="event-stale-1",
            logical_call_id="logical-stale-1",
            status="running",
            safe_error_kind=None,
            started_at=_dt("2000-01-01T00:00:00"),
            finished_at=None,
            latency_ms=None,
            usage_state="unknown",
            input_tokens=None,
            output_tokens=None,
            total_tokens=None,
        ),
        _event(
            event_id="event-stale-2",
            logical_call_id="logical-stale-2",
            status="running",
            safe_error_kind=None,
            started_at=_dt("2000-01-01T01:00:00"),
            finished_at=None,
            latency_ms=None,
            usage_state="unknown",
            input_tokens=None,
            output_tokens=None,
            total_tokens=None,
        ),
    ]

    with _client(rows) as client:
        overview_response = client.get("/api/v1/system/llm-observability/overview")
        detail_response = client.get(
            "/api/v1/system/llm-observability/records/record-hash-1/calls"
        )

    assert overview_response.status_code == 200
    overview = overview_response.json()["data"]
    assert overview["kpis"]["failed_attempts"] == 2
    assert overview["kpis"]["peak_concurrency"] == 1
    assert overview["safe_errors"] == [
        {"status": "abandoned", "safe_error_kind": "stale_running", "count": 2}
    ]
    assert overview["records"]["items"][0]["status"] == "failed"

    detail = detail_response.json()["data"]
    assert {item["status"] for item in detail["items"]} == {"abandoned"}
    assert {item["safe_error_kind"] for item in detail["items"]} == {"stale_running"}
    assert all(item["finished_at"] is None for item in detail["items"])


def test_permissions_allow_only_non_demo_system_administrators():
    for role in ("admin", "sync_admin", "super_admin"):
        with _client([], roles=[role], email=f"{role}@hospital.local") as client:
            assert client.get("/api/v1/system/llm-observability/overview").status_code == 200

    for role in ("qc_manager", "doctor"):
        with _client([], roles=[role], email=f"{role}@hospital.local") as client:
            assert client.get("/api/v1/system/llm-observability/overview").status_code == 403

    with _client([], roles=["admin"], email="  ADMIN@MEDQC.COM ") as client:
        assert client.get("/api/v1/system/llm-observability/overview").status_code == 403


def test_overview_forwards_supported_filters_and_rejects_inverted_range():
    reader = _StaticEventReader([])
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_current_user] = lambda: {
        "id": "u-observability",
        "email": "admin@hospital.local",
        "roles": ["admin"],
    }
    app.dependency_overrides[get_llm_observability_read_service] = lambda: (
        LLMObservabilityReadService(reader=reader)
    )

    with TestClient(app) as client:
        response = client.get(
            "/api/v1/system/llm-observability/overview",
            params={
                "start_at": "2026-08-01T00:00:00Z",
                "end_at": "2026-08-10T00:00:00Z",
                "business_scene": "luxian_0609_qc",
                "model": "qwen-plus",
                "root_job_id": "job-1",
            },
        )
        invalid = client.get(
            "/api/v1/system/llm-observability/overview",
            params={
                "start_at": "2026-08-11T00:00:00Z",
                "end_at": "2026-08-10T00:00:00Z",
            },
        )

    assert response.status_code == 200
    assert reader.filters == [
        {
            "start_at": _dt("2026-08-01T00:00:00"),
            "end_at": _dt("2026-08-10T00:00:00"),
            "business_scene": "luxian_0609_qc",
            "model": "qwen-plus",
            "root_job_id": "job-1",
            "record_key_hash": None,
        }
    ]
    assert invalid.status_code == 422


def test_mixed_naive_and_aware_query_times_are_normalized_to_utc():
    reader = _StaticEventReader([])
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_current_user] = lambda: {
        "id": "u-observability",
        "email": "admin@hospital.local",
        "roles": ["admin"],
    }
    app.dependency_overrides[get_llm_observability_read_service] = lambda: (
        LLMObservabilityReadService(reader=reader)
    )

    with TestClient(app) as client:
        response = client.get(
            "/api/v1/system/llm-observability/overview",
            params={
                "start_at": "2026-08-01T00:00:00",
                "end_at": "2026-08-10T00:00:00Z",
            },
        )

    assert response.status_code == 200
    assert reader.filters[0]["start_at"] == _dt("2026-08-01T00:00:00")
    assert reader.filters[0]["end_at"] == _dt("2026-08-10T00:00:00")


def test_postgres_reader_uses_explicit_sys_table_and_parameterized_filters(monkeypatch):
    captured: dict = {}

    class _Result:
        def __iter__(self):
            return iter(())

    class _Connection:
        def execute(self, statement, params):
            captured["sql"] = str(statement)
            captured["params"] = dict(params)
            return _Result()

    class _ConnectionContext:
        def __enter__(self):
            return _Connection()

        def __exit__(self, exc_type, exc, tb):
            captured["closed"] = True

    class _Engine:
        def connect(self):
            return _ConnectionContext()

    monkeypatch.setattr(
        "app.services.llm_observability_read.database_connection.engine",
        _Engine(),
    )

    rows = asyncio.run(
        PostgresLLMCallEventReader().fetch_events(
            start_at=_dt("2026-08-01T00:00:00"),
            end_at=_dt("2026-08-10T00:00:00"),
            business_scene="scene'; DROP TABLE sys.llm_call_events; --",
            model="qwen-plus",
            root_job_id="job-1",
            record_key_hash=None,
        )
    )

    assert rows == []
    assert "FROM sys.llm_call_events" in captured["sql"]
    assert "DROP TABLE" not in captured["sql"]
    assert captured["params"]["business_scene"] == "scene'; DROP TABLE sys.llm_call_events; --"
    assert captured["closed"] is True


def test_store_failure_maps_to_stable_503_without_exception_or_sql_text():
    class _FailingReader:
        async def fetch_events(self, **_filters):
            raise LLMObservabilityUnavailableError(
                "psycopg2 password=secret SELECT * FROM sys.llm_call_events"
            )

    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_current_user] = lambda: {
        "id": "u-observability",
        "email": "admin@hospital.local",
        "roles": ["admin"],
    }
    app.dependency_overrides[get_llm_observability_read_service] = lambda: (
        LLMObservabilityReadService(reader=_FailingReader())
    )

    with TestClient(app) as client:
        response = client.get("/api/v1/system/llm-observability/overview")

    assert response.status_code == 503
    serialized = response.text
    assert "模型性能观测数据暂不可用" in serialized
    assert "password" not in serialized
    assert "SELECT" not in serialized
    assert "psycopg2" not in serialized
