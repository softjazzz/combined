"""抽取、发布与只读检查的应用编排。"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from contextlib import suppress
from dataclasses import dataclass
from datetime import datetime

from medqc_ingest.domain import (
    WEB_MR_TARGET_COLUMNS,
    ErrorKind,
    IngestError,
    InterfaceSpec,
    KeyTracker,
    PublishLineage,
    RunMode,
    build_records,
    project_web_mr,
    schema_signature,
    validate_interface_columns,
)
from medqc_ingest.ports import (
    CdmRepository,
    CheckRepository,
    IngestRepository,
    PublishAuditRepository,
    SourceAdapter,
)


@dataclass(frozen=True)
class ExtractResult:
    batch_id: int | None
    counts: dict[str, int]
    schema_hash: str
    checkpoint_state: str


@dataclass(frozen=True)
class PublishResult:
    publish_batch_id: int
    schema_hash: str
    selected: int
    written: int


class ExtractService:
    def __init__(
        self,
        source_factory: Callable[[], SourceAdapter],
        repository: IngestRepository | None,
        chunk_size: int,
    ) -> None:
        self._source_factory = source_factory
        self._repository = repository
        self._chunk_size = chunk_size

    def run(
        self,
        spec: InterfaceSpec,
        source_date: str,
        mode: RunMode,
        window_start: datetime,
        window_end: datetime,
    ) -> ExtractResult:
        if mode.writes_raw and self._repository is None:
            raise IngestError(ErrorKind.CONFIGURATION, "ingest_repository_required")

        repository = self._repository
        source: SourceAdapter | None = None
        cursor = None
        batch_id: int | None = None
        locked = False
        data_started = False
        counts = {"fetched": 0, "inserted": 0, "updated": 0, "unchanged": 0}
        schema_hash = ""
        checkpoint_state = "n/a" if mode is RunMode.DRY else "held"

        try:
            if repository is not None:
                repository.connect_control()
                if not repository.acquire_lock(f"extract:{spec.name}"):
                    raise IngestError(ErrorKind.LOCK, "extract_lock_busy")
                locked = True
                batch_id = repository.start_batch(spec.name, window_start, window_end)

            source = self._source_factory()
            source.open()
            cursor = source.query(spec, (source_date,))
            columns = validate_interface_columns(spec, cursor.columns)
            schema_hash, columns = schema_signature(columns)

            if repository is not None:
                repository.begin_data()
                data_started = True
                repository.write_schema(spec.name, schema_hash, columns)

            tracker = KeyTracker()
            while True:
                rows = cursor.fetchmany(self._chunk_size)
                if not rows:
                    break
                records = build_records(columns, rows, spec.key_fields)
                tracker.extend(record.source_key_hash for record in records)
                counts["fetched"] += len(records)
                if repository is not None and batch_id is not None:
                    part = repository.upsert_raw(
                        spec.name,
                        schema_hash,
                        records,
                        batch_id,
                        window_start,
                        window_end,
                    )
                    for name in ("inserted", "updated", "unchanged"):
                        counts[name] += int(part[name])

            if repository is not None and batch_id is not None:
                if mode.advances_checkpoint:
                    advanced = repository.advance_checkpoint(
                        spec.name, window_start, window_end, batch_id
                    )
                    checkpoint_state = "advanced" if advanced else "held"
                repository.commit_data()
                data_started = False
                repository.mark_batch_succeeded(batch_id, counts, checkpoint_state)

            return ExtractResult(batch_id, counts, schema_hash, checkpoint_state)
        except IngestError as exc:
            self._record_extract_failure(repository, batch_id, data_started, exc)
            raise
        except Exception:
            controlled = IngestError(ErrorKind.UNEXPECTED, "extract_run")
            self._record_extract_failure(repository, batch_id, data_started, controlled)
            raise controlled from None
        finally:
            if cursor is not None:
                cursor.close()
            if source is not None:
                source.close()
            if repository is not None:
                repository.drop_data()
                if locked:
                    repository.release_lock(f"extract:{spec.name}")
                repository.close()

    @staticmethod
    def _record_extract_failure(
        repository: IngestRepository | None,
        batch_id: int | None,
        data_started: bool,
        exc: IngestError,
    ) -> None:
        if repository is None:
            return
        if data_started:
            with suppress(Exception):
                repository.rollback_data()
        if batch_id is not None:
            with suppress(Exception):
                repository.mark_batch_failed(batch_id, exc.kind, exc.location)


class PublishService:
    def __init__(
        self,
        audit_repository: PublishAuditRepository,
        cdm_repository: CdmRepository,
        chunk_size: int,
    ) -> None:
        self._audit = audit_repository
        self._cdm = cdm_repository
        self._chunk_size = chunk_size

    def run(self, spec: InterfaceSpec) -> PublishResult:
        if spec.publish_target != "cdm.mr":
            raise IngestError(ErrorKind.PUBLISH_CONTRACT, "unsupported_publish_target")

        publish_batch_id: int | None = None
        cursor = None
        locked = False
        audit_data_started = False
        cdm_started = False
        selected = 0
        written = 0
        schema_hash = ""

        try:
            self._audit.connect_control()
            if not self._audit.acquire_lock(f"publish:{spec.name}"):
                raise IngestError(ErrorKind.LOCK, "publish_lock_busy")
            locked = True
            publish_batch_id = self._audit.start_publish(spec.name)
            cursor = self._audit.open_verified_raw(spec.name)
            schema_hash = cursor.schema_hash
            if tuple(cursor.source_columns) != spec.source_columns:
                raise IngestError(ErrorKind.PUBLISH_CONTRACT, "raw_schema_mismatch")

            self._audit.begin_publish_data()
            audit_data_started = True
            self._cdm.begin()
            cdm_started = True
            self._cdm.assert_web_mr_contract(WEB_MR_TARGET_COLUMNS)

            while True:
                records = cursor.fetchmany(self._chunk_size)
                if not records:
                    break
                projected = [
                    project_web_mr(record.payload, record.completed_at) for record in records
                ]
                lineage = [
                    PublishLineage(
                        source_batch_id=record.source_batch_id,
                        source_key_hash=record.source_key_hash,
                        row_hash=record.row_hash,
                    )
                    for record in records
                ]
                selected += len(records)
                written += self._cdm.upsert_web_mr(projected)
                self._audit.write_publish_lineage(publish_batch_id, lineage)

            self._cdm.commit()
            cdm_started = False
            self._audit.commit_publish_data()
            audit_data_started = False
            self._audit.mark_publish_succeeded(
                publish_batch_id, schema_hash, selected, written
            )
            return PublishResult(publish_batch_id, schema_hash, selected, written)
        except IngestError as exc:
            self._record_publish_failure(
                publish_batch_id, audit_data_started, cdm_started, exc
            )
            raise
        except Exception:
            controlled = IngestError(ErrorKind.UNEXPECTED, "publish_run")
            self._record_publish_failure(
                publish_batch_id, audit_data_started, cdm_started, controlled
            )
            raise controlled from None
        finally:
            if cursor is not None:
                cursor.close()
            self._audit.drop_publish_data()
            if locked:
                self._audit.release_lock(f"publish:{spec.name}")
            self._cdm.close()
            self._audit.close()

    def _record_publish_failure(
        self,
        publish_batch_id: int | None,
        audit_data_started: bool,
        cdm_started: bool,
        exc: IngestError,
    ) -> None:
        if cdm_started:
            with suppress(Exception):
                self._cdm.rollback()
        if audit_data_started:
            with suppress(Exception):
                self._audit.rollback_publish_data()
        if publish_batch_id is not None:
            with suppress(Exception):
                self._audit.mark_publish_failed(publish_batch_id, exc.kind, exc.location)


class CheckService:
    def __init__(self, repository: CheckRepository, stale_minutes: int) -> None:
        self._repository = repository
        self._stale_minutes = stale_minutes

    def run(self) -> Sequence[tuple[str, bool, str]]:
        try:
            ingest = self._repository.check_ingest_contract(self._stale_minutes)
            cdm = self._repository.check_cdm_contract(WEB_MR_TARGET_COLUMNS)
            return tuple(ingest) + tuple(cdm)
        finally:
            self._repository.close()
