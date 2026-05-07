from __future__ import annotations

import pytest
from sqlalchemy import create_engine

from app.services import etl_sync, mongo_sync, sync_run_history


class _ScalarResult:
    def __init__(self, value):
        self._value = value

    def scalar(self):
        return self._value


def test_run_sync_rejects_when_advisory_lock_not_acquired(monkeypatch):
    class _FakeConn:
        def execute(self, stmt, params=None):
            sql = str(stmt)
            if "pg_try_advisory_lock" in sql:
                return _ScalarResult(False)
            raise AssertionError(f"unexpected SQL: {sql}")

        def close(self):
            return None

    class _FakeEngine:
        def connect(self):
            return _FakeConn()

    monkeypatch.setattr(etl_sync, "engine", _FakeEngine())
    monkeypatch.setattr(etl_sync, "_upsert_sync_job_state", lambda _state: None)
    result = etl_sync.run_sync(sync_date="2026-03-25", tables=["mr", "admission_record", "discharge_record"])
    assert result["success"] is False
    assert "同步正在进行中" in result["error"]


def test_run_sync_updates_state_and_unlocks(monkeypatch):
    calls: list[str] = []
    state_snapshots: list[dict] = []

    class _FakeConn:
        def execute(self, stmt, params=None):
            sql = str(stmt)
            calls.append(sql)
            if "pg_try_advisory_lock" in sql:
                return _ScalarResult(True)
            if "pg_advisory_unlock" in sql:
                return _ScalarResult(True)
            raise AssertionError(f"unexpected SQL: {sql}")

        def close(self):
            calls.append("close")
            return None

    class _FakeEngine:
        def connect(self):
            return _FakeConn()

    monkeypatch.setattr(etl_sync, "engine", _FakeEngine())
    monkeypatch.setattr(
        etl_sync,
        "validate_pg_sync_plan",
        lambda **_kwargs: {
            "executable": True,
            "remote_schema": "public",
            "table_validations": [
                {"table": "mr", "source": "public.mr", "source_table": "mr", "local_primary_keys": ["institute_id", "patient_id", "visit_id"]},
                {
                    "table": "admission_record",
                    "source": "public.admission_record",
                    "source_table": "admission_record",
                    "local_primary_keys": ["institute_id", "patient_id", "visit_id"],
                },
                {
                    "table": "discharge_record",
                    "source": "public.discharge_record",
                    "source_table": "discharge_record",
                    "local_primary_keys": ["institute_id", "patient_id", "visit_id"],
                },
            ],
        },
    )
    monkeypatch.setattr(etl_sync, "load_sync_policy", lambda: {"schedule": {"minutes": 30}, "mirror_delay_base_minutes": 30})
    monkeypatch.setattr(
        etl_sync,
        "_resolve_pg_extract_window",
        lambda **_kwargs: (__import__("datetime").date(2026, 3, 25), __import__("datetime").date(2026, 3, 25), ["*"], ""),
    )
    monkeypatch.setattr(etl_sync, "collect_visit_keys_by_policy", lambda **_kwargs: [("p1", "v1")])
    monkeypatch.setattr(
        etl_sync,
        "fetch_remote_rows_by_visit_keys",
        lambda **kwargs: [{"institute_id": "A", "patient_id": "p1", "visit_id": "v1"}] if kwargs["source_table"] == "mr" else [],
    )
    monkeypatch.setattr(etl_sync, "upsert_to_local", lambda *_args, **_kwargs: 1)

    def _capture_state(state):
        state_snapshots.append(
            {
                "is_running": state.is_running,
                "last_sync_status": state.last_sync_status,
                "total_records_synced": state.total_records_synced,
            }
        )

    monkeypatch.setattr(etl_sync, "_upsert_sync_job_state", _capture_state)

    result = etl_sync.run_sync(sync_date="2026-03-25", tables=["mr", "admission_record", "discharge_record"])
    assert result["success"] is True
    assert result["total_records"] == 3
    assert any("pg_try_advisory_lock" in item for item in calls)
    assert any("pg_advisory_unlock" in item for item in calls)
    assert state_snapshots[0]["is_running"] is True
    assert state_snapshots[-1]["is_running"] is False
    assert state_snapshots[-1]["last_sync_status"] == "success"
    assert state_snapshots[-1]["total_records_synced"] == 3


def test_upsert_to_local_uses_real_local_primary_keys(monkeypatch):
    executed_sql: list[str] = []

    class _FakeSession:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def execute(self, stmt, params=None):
            executed_sql.append(str(stmt))
            return None

        def commit(self):
            return None

    monkeypatch.setattr(etl_sync, "Session", lambda _engine: _FakeSession())
    monkeypatch.setattr(
        etl_sync,
        "_get_local_table_meta",
        lambda _session, _table_name: ("cdm", ["institute_id", "patient_id", "visit_id", "name"], ["institute_id", "patient_id", "visit_id"]),
    )

    count = etl_sync.upsert_to_local(
        table_name="mr",
        records=[
            {
                "institute_id": "A",
                "patient_id": "P1",
                "visit_id": "V1",
                "name": "张三",
            }
        ],
        primary_keys=["patient_id", "visit_id"],
    )

    assert count == 1
    assert len(executed_sql) == 1
    assert "ON CONFLICT (institute_id, patient_id, visit_id)" in executed_sql[0]


def test_upsert_to_local_derives_labtest_document_id_from_source_keys(monkeypatch):
    executed_params: list[dict] = []

    class _FakeSession:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def execute(self, stmt, params=None):
            executed_params.append(dict(params or {}))
            return None

        def commit(self):
            return None

    monkeypatch.setattr(etl_sync, "Session", lambda _engine: _FakeSession())
    monkeypatch.setattr(
        etl_sync,
        "_get_local_table_meta",
        lambda _session, _table_name: (
            "cdm",
            [
                "institute_id",
                "patient_id",
                "visit_id",
                "document_id",
                "test_no",
                "item_no",
                "item_name",
                "result",
                "unit",
                "record_content",
            ],
            ["institute_id", "patient_id", "visit_id", "document_id"],
        ),
    )

    count = etl_sync.upsert_to_local(
        table_name="labtest_item_report",
        records=[
            {
                "institute_id": "A",
                "patient_id": "P1",
                "visit_id": "V1",
                "test_no": "T100",
                "item_no": "I2",
                "item_name": "白细胞计数",
                "result": "12.5",
                "unit": "10^9/L",
            }
        ],
        primary_keys=["patient_id", "visit_id", "test_no", "item_no"],
    )

    assert count == 1
    assert executed_params[0]["document_id"] == "lab:T100:I2"
    assert executed_params[0]["record_content"] == "白细胞计数：12.5 10^9/L"


def test_upsert_to_local_derives_exam_document_id_from_source_keys(monkeypatch):
    executed_params: list[dict] = []

    class _FakeSession:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def execute(self, stmt, params=None):
            executed_params.append(dict(params or {}))
            return None

        def commit(self):
            return None

    monkeypatch.setattr(etl_sync, "Session", lambda _engine: _FakeSession())
    monkeypatch.setattr(
        etl_sync,
        "_get_local_table_meta",
        lambda _session, _table_name: (
            "cdm",
            [
                "institute_id",
                "patient_id",
                "visit_id",
                "document_id",
                "exam_no",
                "item_no",
                "exam_name",
                "exam_conclusion",
                "record_content",
            ],
            ["institute_id", "patient_id", "visit_id", "document_id"],
        ),
    )

    count = etl_sync.upsert_to_local(
        table_name="exam_item_report",
        records=[
            {
                "institute_id": "A",
                "patient_id": "P1",
                "visit_id": "V1",
                "exam_no": "E100",
                "item_no": "1",
                "exam_name": "胸部CT",
                "exam_conclusion": "双肺炎症",
            }
        ],
        primary_keys=["patient_id", "visit_id", "exam_no", "item_no"],
    )

    assert count == 1
    assert executed_params[0]["document_id"] == "exam:E100:1"
    assert executed_params[0]["record_content"] == "双肺炎症"


def test_upsert_to_local_raises_when_records_cannot_match_local_primary_keys(monkeypatch):
    class _FakeSession:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def execute(self, stmt, params=None):
            raise AssertionError("missing primary key rows must not be inserted")

        def commit(self):
            return None

    monkeypatch.setattr(etl_sync, "Session", lambda _engine: _FakeSession())
    monkeypatch.setattr(
        etl_sync,
        "_get_local_table_meta",
        lambda _session, _table_name: (
            "cdm",
            ["institute_id", "patient_id", "visit_id", "document_id", "record_content"],
            ["institute_id", "patient_id", "visit_id", "document_id"],
        ),
    )

    with pytest.raises(ValueError, match="缺少本地主键字段"):
        etl_sync.upsert_to_local(
            table_name="daily_course_record",
            records=[
                {
                    "institute_id": "A",
                    "patient_id": "P1",
                    "visit_id": "V1",
                    "record_content": "有正文但缺 document_id",
                }
            ],
            primary_keys=["patient_id", "visit_id", "document_id"],
        )


def test_sync_run_history_persists_and_caps_records(monkeypatch):
    db_engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    monkeypatch.setattr(sync_run_history, "engine", db_engine)

    for idx in range(3):
        sync_run_history.append_sync_run_record(
            {
                "id": f"run-{idx}",
                "source": "pg",
                "tier": "all",
                "tables": ["mr"],
                "status": "success",
                "started_at": f"2026-03-25T10:0{idx}:00+00:00",
                "finished_at": f"2026-03-25T10:0{idx}:10+00:00",
                "duration_ms": 1000,
                "total_records": 10 + idx,
                "error": "",
                "operator": {"email": "admin@medqc.com"},
            },
            max_items=2,
        )

    listed = sync_run_history.list_sync_run_records(source="pg", tier="all", limit=10)
    assert listed["total"] == 2
    assert listed["limit"] == 10
    assert len(listed["items"]) == 2
    returned_ids = {item["id"] for item in listed["items"]}
    assert returned_ids.issubset({"run-0", "run-1", "run-2"})


def test_sync_health_stats_aggregates_failure_rate_and_lag(monkeypatch):
    db_engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    monkeypatch.setattr(sync_run_history, "engine", db_engine)

    sync_run_history.append_sync_run_record(
        {
            "id": "run-success",
            "source": "pg",
            "tier": "all",
            "tables": ["mr"],
            "status": "success",
            "started_at": "2026-03-25T10:00:00+00:00",
            "finished_at": "2026-03-25T10:00:20+00:00",
            "duration_ms": 20000,
            "total_records": 100,
            "error": "",
            "operator": {"email": "admin@medqc.com"},
        },
        max_items=10,
    )
    sync_run_history.append_sync_run_record(
        {
            "id": "run-failed",
            "source": "pg",
            "tier": "all",
            "tables": ["mr"],
            "status": "failed",
            "started_at": "2026-03-25T10:05:00+00:00",
            "finished_at": "2026-03-25T10:05:10+00:00",
            "duration_ms": 10000,
            "total_records": 0,
            "error": "boom",
            "operator": {"email": "admin@medqc.com"},
        },
        max_items=10,
    )

    stats = sync_run_history.get_sync_health_stats(window_minutes=60 * 24 * 365 * 2, sample_limit=50)
    assert stats["window_total_runs"] == 2
    assert stats["window_failed_runs"] == 1
    assert stats["window_failure_rate"] == 0.5
    assert stats["last_run_at"] is not None
    assert stats["last_success_at"] is not None
    assert stats["last_run_lag_seconds"] >= 0
    assert stats["last_success_lag_seconds"] >= 0


def test_run_mongo_sync_rejects_when_advisory_lock_not_acquired(monkeypatch):
    class _Cfg:
        enabled = True
        mongo_uri = "mongodb://127.0.0.1:27017/admin"
        mongo_database = "admin"
        read_preference = "secondaryPreferred"
        max_concurrent = 2
        query_timeout_s = 5
        connect_timeout_ms = 1000

    class _FakeConn:
        def execute(self, stmt, params=None):
            sql = str(stmt)
            if "pg_try_advisory_lock" in sql:
                return _ScalarResult(False)
            raise AssertionError(f"unexpected SQL: {sql}")

        def close(self):
            return None

    class _FakeEngine:
        def connect(self):
            return _FakeConn()

    monkeypatch.setattr("app.services.etl_config.load_mongo_config", lambda: _Cfg())
    monkeypatch.setattr(mongo_sync, "engine", _FakeEngine())
    monkeypatch.setattr(mongo_sync, "_upsert_mongo_sync_state", lambda _state: None)
    result = mongo_sync.run_mongo_sync("tier1")
    assert result["success"] is False
    assert "同步正在进行中" in result["error"]


def test_run_mongo_sync_unlocks_on_early_failure(monkeypatch):
    calls: list[str] = []

    class _Cfg:
        enabled = True
        mongo_uri = "mongodb://127.0.0.1:27017/admin"
        mongo_database = "admin"
        read_preference = "secondaryPreferred"
        max_concurrent = 2
        query_timeout_s = 5
        connect_timeout_ms = 1000

    class _FakeConn:
        def execute(self, stmt, params=None):
            sql = str(stmt)
            calls.append(sql)
            if "pg_try_advisory_lock" in sql:
                return _ScalarResult(True)
            if "pg_advisory_unlock" in sql:
                return _ScalarResult(True)
            raise AssertionError(f"unexpected SQL: {sql}")

        def close(self):
            calls.append("close")
            return None

    class _FakeEngine:
        def connect(self):
            return _FakeConn()

    class _FakeConnector:
        def __init__(self, *args, **kwargs):
            pass

        def test_connection(self):
            return {"connected": False, "error": "mongo down"}

        def close(self):
            calls.append("connector.close")
            return None

    monkeypatch.setattr("app.services.etl_config.load_mongo_config", lambda: _Cfg())
    monkeypatch.setattr(mongo_sync, "engine", _FakeEngine())
    monkeypatch.setattr(mongo_sync, "MongoConnector", _FakeConnector)
    monkeypatch.setattr(mongo_sync, "_upsert_mongo_sync_state", lambda _state: None)

    result = mongo_sync.run_mongo_sync("tier1")
    assert result["success"] is False
    assert result["error"] == "mongo down"
    assert any("pg_try_advisory_lock" in item for item in calls)
    assert any("pg_advisory_unlock" in item for item in calls)
    assert "connector.close" in calls


def test_mongo_sync_state_persisted_in_database(monkeypatch):
    db_engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    monkeypatch.setattr(mongo_sync, "engine", db_engine)

    state = mongo_sync.MongoSyncState(
        is_running=True,
        last_sync_time="2026-03-26T10:00:00Z",
        last_sync_status="success",
        connected=True,
        connection_error="",
        tier1_last_run="2026-03-26T10:00:00Z",
        tier1_discovered=11,
        tier2_last_run="2026-03-26T10:05:00Z",
        tier2_synced=7,
        tier3_last_run="2026-03-26T10:10:00Z",
        tier3_synced=5,
        logs=[{"event": "ok"}],
    )
    mongo_sync._upsert_mongo_sync_state(state)
    loaded = mongo_sync.get_mongo_sync_state()
    assert loaded["is_running"] is True
    assert loaded["last_sync_status"] == "success"
    assert loaded["tier1_discovered"] == 11
    assert loaded["tier2_synced"] == 7
    assert loaded["tier3_synced"] == 5
