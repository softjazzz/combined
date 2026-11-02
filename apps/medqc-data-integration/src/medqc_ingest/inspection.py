"""隔离快照检查编排；不触碰正式 raw、checkpoint 或业务库。"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from contextlib import suppress
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any, Protocol

from medqc_ingest.catalog import CandidateInterface, DateSemantics
from medqc_ingest.domain import (
    ErrorKind,
    IngestError,
    InterfaceSpec,
    canonical_json,
    normalize,
    schema_signature,
    sha256_hex,
    validate_interface_columns,
)
from medqc_ingest.ports import SourceAdapter

CASE_FIELDS = ("institute_id", "patient_id", "visit_id")


@dataclass(frozen=True)
class InspectionCall:
    start: date
    end: date
    arguments: tuple[str, ...]


@dataclass(frozen=True)
class SnapshotRecord:
    ordinal: int
    payload: Mapping[str, Any]
    source_key: Mapping[str, Any] | None
    source_key_hash: str | None
    case_key_hash: str | None
    key_complete: bool


@dataclass(frozen=True)
class InspectionResult:
    batch_id: int
    succeeded: int
    failed: int
    blocked: int


class InspectionRepository(Protocol):
    def connect_control(self) -> None: ...

    def acquire_lock(self, scope: str) -> bool: ...

    def release_lock(self, scope: str) -> None: ...

    def start_inspection(self, start: date, end: date) -> int: ...

    def record_inspection_run(
        self,
        batch_id: int,
        interface: str,
        start: date,
        end: date,
        status: str,
        row_count: int,
        schema_hash: str | None,
        error_kind: str | None,
        error_location: str | None,
    ) -> None: ...

    def begin_snapshot(self) -> None: ...

    def write_inspection_schema(
        self,
        batch_id: int,
        interface: str,
        schema_hash: str,
        columns: Sequence[str],
        source_types: Sequence[str],
    ) -> None: ...

    def write_snapshot(
        self,
        batch_id: int,
        interface: str,
        start: date,
        end: date,
        schema_hash: str,
        rows: Sequence[SnapshotRecord],
    ) -> None: ...

    def commit_snapshot(self) -> None: ...

    def rollback_snapshot(self) -> None: ...

    def finish_inspection(self, batch_id: int, status: str) -> None: ...

    def close(self) -> None: ...


def plan_inspection_calls(
    metadata: CandidateInterface, start: date, end: date
) -> tuple[InspectionCall, ...]:
    if end < start:
        raise IngestError(ErrorKind.CONFIGURATION, "inspection_date_range")
    if metadata.date_semantics is DateSemantics.UNKNOWN:
        raise IngestError(ErrorKind.CONFIGURATION, "unverified_date_semantics")
    if metadata.date_semantics is DateSemantics.RANGE_INCLUSIVE:
        if metadata.argument_count != 2:
            raise IngestError(ErrorKind.CONFIGURATION, "inspection_argument_contract")
        return (InspectionCall(start, end, (start.isoformat(), end.isoformat())),)
    if metadata.argument_count != 1:
        raise IngestError(ErrorKind.CONFIGURATION, "inspection_argument_contract")
    calls: list[InspectionCall] = []
    current = start
    while current <= end:
        calls.append(InspectionCall(current, current, (current.isoformat(),)))
        current += timedelta(days=1)
    return tuple(calls)


def build_snapshot_records(
    spec: InterfaceSpec,
    columns: Sequence[str],
    rows: Sequence[Sequence[Any]],
    ordinal_start: int,
) -> tuple[SnapshotRecord, ...]:
    result: list[SnapshotRecord] = []
    for offset, row in enumerate(rows):
        if len(row) != len(columns):
            raise IngestError(ErrorKind.SCHEMA, "snapshot_row_width")
        payload = {column: normalize(row[index]) for index, column in enumerate(columns)}
        source_key = {
            field: payload[field]
            for field in spec.key_fields
            if payload.get(field) not in (None, "")
        }
        key_complete = len(source_key) == len(spec.key_fields)
        case_key = {
            field: payload[field]
            for field in CASE_FIELDS
            if payload.get(field) not in (None, "")
        }
        result.append(
            SnapshotRecord(
                ordinal=ordinal_start + offset,
                payload=payload,
                source_key=source_key or None,
                source_key_hash=(
                    sha256_hex(canonical_json(source_key)) if key_complete else None
                ),
                case_key_hash=(
                    sha256_hex(canonical_json(case_key))
                    if len(case_key) == len(CASE_FIELDS)
                    else None
                ),
                key_complete=key_complete,
            )
        )
    return tuple(result)


class InspectionService:
    def __init__(
        self,
        source_factory: Callable[[], SourceAdapter],
        repository: InspectionRepository,
        chunk_size: int,
    ) -> None:
        self._source_factory = source_factory
        self._repository = repository
        self._chunk_size = chunk_size

    def run_all(
        self,
        registered: Mapping[str, InterfaceSpec],
        candidates: Mapping[str, CandidateInterface],
        start: date,
        end: date,
    ) -> InspectionResult:
        self._repository.connect_control()
        if not self._repository.acquire_lock("inspection"):
            self._repository.close()
            raise IngestError(ErrorKind.LOCK, "inspection_lock_busy")
        batch_id = -1
        succeeded = failed = blocked = 0
        try:
            batch_id = self._repository.start_inspection(start, end)
            for name, metadata in candidates.items():
                spec = registered.get(name)
                if spec is None:
                    blocked += 1
                    self._repository.record_inspection_run(
                        batch_id,
                        name,
                        start,
                        end,
                        "blocked",
                        0,
                        None,
                        ErrorKind.INTERFACE.value,
                        "candidate_not_registered",
                    )
                    continue
                try:
                    calls = plan_inspection_calls(metadata, start, end)
                except IngestError as exc:
                    blocked += 1
                    self._repository.record_inspection_run(
                        batch_id,
                        name,
                        start,
                        end,
                        "blocked",
                        0,
                        None,
                        exc.kind,
                        exc.location,
                    )
                    continue
                for call in calls:
                    ok = self._run_call(batch_id, spec, call)
                    succeeded += int(ok)
                    failed += int(not ok)
            status = "succeeded" if failed == 0 else "completed_with_failures"
            self._repository.finish_inspection(batch_id, status)
            return InspectionResult(batch_id, succeeded, failed, blocked)
        finally:
            self._repository.release_lock("inspection")
            self._repository.close()

    def _run_call(self, batch_id: int, spec: InterfaceSpec, call: InspectionCall) -> bool:
        source: SourceAdapter | None = None
        cursor = None
        snapshot_started = False
        try:
            source = self._source_factory()
            source.open()
            cursor = source.query(spec, call.arguments)
            columns = validate_interface_columns(spec, cursor.columns)
            schema_hash, columns = schema_signature(columns)
            source_types = tuple(cursor.source_types)
            if len(source_types) != len(columns):
                source_types = tuple("unknown" for _ in columns)
            self._repository.begin_snapshot()
            snapshot_started = True
            self._repository.write_inspection_schema(
                batch_id, spec.name, schema_hash, columns, source_types
            )
            ordinal = 1
            while True:
                chunk = cursor.fetchmany(self._chunk_size)
                if not chunk:
                    break
                records = build_snapshot_records(spec, columns, chunk, ordinal)
                self._repository.write_snapshot(
                    batch_id,
                    spec.name,
                    call.start,
                    call.end,
                    schema_hash,
                    records,
                )
                ordinal += len(records)
            self._repository.commit_snapshot()
            snapshot_started = False
            self._repository.record_inspection_run(
                batch_id,
                spec.name,
                call.start,
                call.end,
                "succeeded",
                ordinal - 1,
                schema_hash,
                None,
                None,
            )
            return True
        except IngestError as exc:
            if snapshot_started:
                with suppress(Exception):
                    self._repository.rollback_snapshot()
            self._repository.record_inspection_run(
                batch_id,
                spec.name,
                call.start,
                call.end,
                "failed",
                0,
                None,
                exc.kind,
                exc.location,
            )
            return False
        except Exception:
            if snapshot_started:
                with suppress(Exception):
                    self._repository.rollback_snapshot()
            self._repository.record_inspection_run(
                batch_id,
                spec.name,
                call.start,
                call.end,
                "failed",
                0,
                None,
                ErrorKind.UNEXPECTED.value,
                "inspection_call",
            )
            return False
        finally:
            if cursor is not None:
                cursor.close()
            if source is not None:
                source.close()
