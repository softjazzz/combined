from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import pytest

from medqc_ingest.domain import (
    WEB_MR_SOURCE_COLUMNS,
    IngestError,
    PublishRecord,
    RunMode,
    resolve_interface,
)
from medqc_ingest.service import ExtractService, PublishService


class FakeSourceCursor:
    def __init__(self, chunks: list[list[tuple[Any, ...]]], columns: tuple[str, ...]) -> None:
        self._chunks = list(chunks)
        self._columns = columns
        self.closed = False

    @property
    def columns(self) -> tuple[str, ...]:
        return self._columns

    def fetchmany(self, size: int) -> list[tuple[Any, ...]]:
        del size
        return self._chunks.pop(0) if self._chunks else []

    def close(self) -> None:
        self.closed = True


class FakeSource:
    def __init__(self, cursor: FakeSourceCursor) -> None:
        self.cursor = cursor
        self.opened = False
        self.closed = False

    def open(self) -> None:
        self.opened = True

    def query(self, spec: Any, source_date: tuple[str, ...]) -> FakeSourceCursor:
        assert spec.name == "web.mr"
        assert source_date == ("2026-10-28",)
        return self.cursor

    def close(self) -> None:
        self.closed = True


class FakeIngestRepository:
    def __init__(self, checkpoint_advanced: bool = True) -> None:
        self.checkpoint_advanced = checkpoint_advanced
        self.calls: list[str] = []
        self.rows: list[Any] = []
        self.success: tuple[dict[str, int], str] | None = None
        self.failure: tuple[str, str] | None = None

    def connect_control(self) -> None:
        self.calls.append("connect_control")

    def acquire_lock(self, scope: str) -> bool:
        self.calls.append(f"lock:{scope}")
        return True

    def release_lock(self, scope: str) -> None:
        self.calls.append(f"unlock:{scope}")

    def start_batch(self, interface: str, start: datetime, end: datetime) -> int:
        self.calls.append("start_batch")
        return 9

    def mark_batch_succeeded(
        self, batch_id: int, counts: dict[str, int], checkpoint_state: str
    ) -> None:
        assert batch_id == 9
        self.success = (dict(counts), checkpoint_state)

    def mark_batch_failed(self, batch_id: int, kind: str, location: str) -> None:
        assert batch_id == 9
        self.failure = (kind, location)

    def begin_data(self) -> None:
        self.calls.append("begin_data")

    def write_schema(self, interface: str, schema_hash: str, columns: Any) -> None:
        self.calls.append("write_schema")

    def upsert_raw(self, *args: Any) -> dict[str, int]:
        records = args[2]
        self.rows.extend(records)
        self.calls.append("upsert_raw")
        return {"inserted": len(records), "updated": 0, "unchanged": 0}

    def advance_checkpoint(self, *args: Any) -> bool:
        self.calls.append("advance_checkpoint")
        return self.checkpoint_advanced

    def commit_data(self) -> None:
        self.calls.append("commit_data")

    def rollback_data(self) -> None:
        self.calls.append("rollback_data")

    def drop_data(self) -> None:
        self.calls.append("drop_data")

    def close(self) -> None:
        self.calls.append("close")


def _row(visit_id: str) -> tuple[str, ...]:
    values = {column: f"value-{column}" for column in WEB_MR_SOURCE_COLUMNS}
    values["institute_id"] = "I"
    values["patient_id"] = "P"
    values["visit_id"] = visit_id
    return tuple(values[column] for column in WEB_MR_SOURCE_COLUMNS)


def _times() -> tuple[datetime, datetime]:
    start = datetime(2026, 10, 28, tzinfo=timezone.utc)
    return start, datetime(2026, 10, 29, tzinfo=timezone.utc)


def test_dry_streams_without_repository() -> None:
    cursor = FakeSourceCursor([[_row("V1")], [_row("V2")]], WEB_MR_SOURCE_COLUMNS)
    source = FakeSource(cursor)
    result = ExtractService(lambda: source, None, 1).run(
        resolve_interface("web.mr"), "2026-10-28", RunMode.DRY, *_times()
    )
    assert result.counts["fetched"] == 2
    assert result.checkpoint_state == "n/a"
    assert source.closed and cursor.closed


def test_incremental_reports_held_from_actual_checkpoint_rowcount() -> None:
    cursor = FakeSourceCursor([[_row("V1")]], WEB_MR_SOURCE_COLUMNS)
    repository = FakeIngestRepository(checkpoint_advanced=False)
    result = ExtractService(lambda: FakeSource(cursor), repository, 100).run(
        resolve_interface("web.mr"), "2026-10-28", RunMode.INCREMENTAL, *_times()
    )
    assert result.checkpoint_state == "held"
    assert repository.success == (
        {"fetched": 1, "inserted": 1, "updated": 0, "unchanged": 0},
        "held",
    )


def test_replay_never_advances_checkpoint() -> None:
    repository = FakeIngestRepository()
    ExtractService(
        lambda: FakeSource(FakeSourceCursor([[_row("V1")]], WEB_MR_SOURCE_COLUMNS)),
        repository,
        100,
    ).run(resolve_interface("web.mr"), "2026-10-28", RunMode.REPLAY, *_times())
    assert "advance_checkpoint" not in repository.calls
    assert repository.success is not None and repository.success[1] == "held"


def test_cross_chunk_duplicate_rolls_back_whole_batch() -> None:
    repository = FakeIngestRepository()
    cursor = FakeSourceCursor([[_row("V1")], [_row("V1")]], WEB_MR_SOURCE_COLUMNS)
    with pytest.raises(IngestError) as exc_info:
        ExtractService(lambda: FakeSource(cursor), repository, 1).run(
            resolve_interface("web.mr"), "2026-10-28", RunMode.INCREMENTAL, *_times()
        )
    assert exc_info.value.location == "duplicate_key"
    assert "rollback_data" in repository.calls
    assert "commit_data" not in repository.calls
    assert repository.failure == ("key_validation_error", "duplicate_key")


class FakePublishCursor:
    schema_hash = "a" * 64
    source_columns = WEB_MR_SOURCE_COLUMNS

    def __init__(self, chunks: list[list[PublishRecord]]) -> None:
        self.chunks = chunks

    def fetchmany(self, size: int) -> list[PublishRecord]:
        del size
        return self.chunks.pop(0) if self.chunks else []

    def close(self) -> None:
        pass


class FakeAuditRepository:
    def __init__(self, cursor: FakePublishCursor) -> None:
        self.cursor = cursor
        self.calls: list[str] = []
        self.lineage: list[Any] = []

    def connect_control(self) -> None:
        self.calls.append("connect")

    def acquire_lock(self, scope: str) -> bool:
        return True

    def release_lock(self, scope: str) -> None:
        self.calls.append("unlock")

    def start_publish(self, interface: str) -> int:
        return 12

    def open_verified_raw(self, interface: str) -> FakePublishCursor:
        return self.cursor

    def begin_publish_data(self) -> None:
        self.calls.append("begin")

    def write_publish_lineage(self, publish_batch_id: int, rows: Any) -> None:
        self.lineage.extend(rows)

    def commit_publish_data(self) -> None:
        self.calls.append("commit")

    def rollback_publish_data(self) -> None:
        self.calls.append("rollback")

    def drop_publish_data(self) -> None:
        self.calls.append("drop")

    def mark_publish_succeeded(self, *args: Any) -> None:
        self.calls.append("succeeded")

    def mark_publish_failed(self, *args: Any) -> None:
        self.calls.append("failed")

    def close(self) -> None:
        self.calls.append("close")


class FakeCdmRepository:
    def __init__(self, fail_contract: bool = False) -> None:
        self.fail_contract = fail_contract
        self.calls: list[str] = []

    def begin(self) -> None:
        self.calls.append("begin")

    def assert_web_mr_contract(self, expected_columns: Any) -> None:
        if self.fail_contract:
            raise IngestError("publish_contract_error", "target_drift")

    def upsert_web_mr(self, rows: Any) -> int:
        self.calls.append("upsert")
        return len(rows)

    def commit(self) -> None:
        self.calls.append("commit")

    def rollback(self) -> None:
        self.calls.append("rollback")

    def close(self) -> None:
        self.calls.append("close")


def _publish_record() -> PublishRecord:
    payload = {column: f"value-{column}" for column in WEB_MR_SOURCE_COLUMNS}
    payload.update(institute_id="I", patient_id="P", visit_id="V")
    return PublishRecord(
        payload=payload,
        completed_at=datetime(2026, 10, 28, tzinfo=timezone.utc),
        source_batch_id=9,
        source_key_hash="b" * 64,
        row_hash="c" * 64,
    )


def test_publish_is_atomic_and_records_lineage() -> None:
    audit = FakeAuditRepository(FakePublishCursor([[_publish_record()]]))
    cdm = FakeCdmRepository()
    result = PublishService(audit, cdm, 100).run(resolve_interface("web.mr"))
    assert (result.selected, result.written) == (1, 1)
    assert cdm.calls == ["begin", "upsert", "commit", "close"]
    assert len(audit.lineage) == 1
    assert audit.calls.index("commit") < audit.calls.index("succeeded")


def test_publish_contract_failure_rolls_back_both_transactions() -> None:
    audit = FakeAuditRepository(FakePublishCursor([[_publish_record()]]))
    cdm = FakeCdmRepository(fail_contract=True)
    with pytest.raises(IngestError):
        PublishService(audit, cdm, 100).run(resolve_interface("web.mr"))
    assert "rollback" in cdm.calls
    assert "rollback" in audit.calls
    assert "failed" in audit.calls
