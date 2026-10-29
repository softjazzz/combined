"""psycopg v3 的 ingest、发布与只读检查仓储。"""

from __future__ import annotations

import importlib
import json
from collections.abc import Mapping, Sequence
from contextlib import suppress
from datetime import date, datetime
from typing import Any

from medqc_ingest.config import PostgresSettings
from medqc_ingest.domain import (
    INTERFACE_REGISTRY,
    ErrorKind,
    IngestError,
    PublishLineage,
    PublishRecord,
    PublishSpec,
    RawRecord,
    advisory_lock_key,
)
from medqc_ingest.inspection import SnapshotRecord
from medqc_ingest.profiling import ProfileSnapshotRow


def _psycopg() -> Any:
    try:
        return importlib.import_module("psycopg")
    except ImportError:
        raise IngestError(ErrorKind.CONFIGURATION, "psycopg_not_installed") from None


def _connect(
    settings: PostgresSettings,
    kind: ErrorKind,
    location: str,
    *,
    readonly: bool = False,
) -> Any:
    kwargs = settings.connection_kwargs()
    kwargs["application_name"] = "medqc_data_integration"
    if readonly:
        kwargs["options"] = "-c default_transaction_read_only=on"
    try:
        return _psycopg().connect(**kwargs)
    except IngestError:
        raise
    except Exception:
        raise IngestError(kind, location) from None


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True)


def _ident(name: str) -> str:
    return '"' + name.replace('"', '""') + '"'


def _json_field(name: str) -> str:
    if not name or any(not (character.isalnum() or character == "_") for character in name):
        raise IngestError(ErrorKind.PUBLISH_CONTRACT, "unsafe_contract_field")
    return "'" + name + "'"


class PostgresIngestRepository:
    def __init__(self, settings: PostgresSettings) -> None:
        self._settings = settings
        self._control: Any = None
        self._data: Any = None
        self._publish_read: Any = None
        self._publish_data: Any = None
        self._profile_read: Any = None

    def connect_control(self) -> None:
        if self._control is not None:
            return
        self._control = _connect(
            self._settings, ErrorKind.INGEST_CONNECT, "ingest_control_connect"
        )
        self._control.autocommit = True

    def acquire_lock(self, scope: str) -> bool:
        try:
            with self._control.cursor() as cursor:
                cursor.execute("SELECT pg_try_advisory_lock(%s)", (advisory_lock_key(scope),))
                row = cursor.fetchone()
                return bool(row and row[0])
        except Exception:
            raise IngestError(ErrorKind.INGEST_WRITE, "advisory_lock") from None

    def release_lock(self, scope: str) -> None:
        if self._control is None:
            return
        try:
            with self._control.cursor() as cursor:
                cursor.execute("SELECT pg_advisory_unlock(%s)", (advisory_lock_key(scope),))
        except Exception:
            pass

    def start_batch(
        self, interface: str, start: datetime, end: datetime, evidence_version: str
    ) -> int:
        try:
            with self._control.cursor() as cursor:
                cursor.execute(
                    "INSERT INTO sync_ops.sync_batch "
                    "(interface_name, window_start, window_end, evidence_version, status) "
                    "VALUES (%s,%s,%s,%s,'running') RETURNING batch_id",
                    (interface, start, end, evidence_version),
                )
                row = cursor.fetchone()
                if row is None:
                    raise RuntimeError
                return int(row[0])
        except Exception:
            raise IngestError(ErrorKind.INGEST_WRITE, "start_batch") from None

    def mark_batch_succeeded(
        self, batch_id: int, counts: Mapping[str, int], checkpoint_state: str
    ) -> None:
        try:
            with self._control.cursor() as cursor:
                cursor.execute(
                    "UPDATE sync_ops.sync_batch SET status='succeeded', finished_at=now(), "
                    "rows_fetched=%s, rows_inserted=%s, rows_updated=%s, rows_unchanged=%s, "
                    "checkpoint_state=%s WHERE batch_id=%s AND status='running'",
                    (
                        counts["fetched"],
                        counts["inserted"],
                        counts["updated"],
                        counts["unchanged"],
                        checkpoint_state,
                        batch_id,
                    ),
                )
        except Exception:
            raise IngestError(ErrorKind.INGEST_WRITE, "mark_batch_succeeded") from None

    def mark_batch_failed(self, batch_id: int, kind: str, location: str) -> None:
        try:
            with self._control.cursor() as cursor:
                cursor.execute(
                    "UPDATE sync_ops.sync_batch SET status='failed', finished_at=now(), "
                    "error_kind=%s, error_location=%s "
                    "WHERE batch_id=%s AND status='running'",
                    (kind, location, batch_id),
                )
        except Exception:
            raise IngestError(ErrorKind.INGEST_WRITE, "mark_batch_failed") from None

    def begin_data(self) -> None:
        self._data = _connect(
            self._settings, ErrorKind.INGEST_CONNECT, "ingest_data_connect"
        )
        self._data.autocommit = False

    def write_schema(self, interface: str, schema_hash: str, columns: Sequence[str]) -> None:
        try:
            with self._data.cursor() as cursor:
                cursor.execute(
                    "INSERT INTO sync_ops.source_schema "
                    "(interface_name,schema_hash,schema_hash_version,column_count,column_names) "
                    "VALUES (%s,%s,'ordered-column-names-v1',%s,%s::jsonb) "
                    "ON CONFLICT (interface_name,schema_hash) DO UPDATE SET "
                    "last_seen_at=now(), column_count=EXCLUDED.column_count, "
                    "column_names=EXCLUDED.column_names",
                    (interface, schema_hash, len(columns), _json(list(columns))),
                )
        except Exception:
            raise IngestError(ErrorKind.INGEST_WRITE, "write_schema") from None

    def upsert_raw(
        self,
        interface: str,
        schema_hash: str,
        records: Sequence[RawRecord],
        batch_id: int,
        start: datetime,
        end: datetime,
    ) -> Mapping[str, int]:
        if not records:
            return {"inserted": 0, "updated": 0, "unchanged": 0}
        try:
            hashes = [record.source_key_hash for record in records]
            with self._data.cursor() as cursor:
                cursor.execute(
                    "SELECT source_key_hash,row_hash FROM cache_raw.source_record "
                    "WHERE interface_name=%s AND source_key_hash = ANY(%s)",
                    (interface, hashes),
                )
                existing = {str(row[0]): str(row[1]) for row in cursor.fetchall()}
                counts = {"inserted": 0, "updated": 0, "unchanged": 0}
                values: list[tuple[Any, ...]] = []
                for record in records:
                    previous = existing.get(record.source_key_hash)
                    if previous is None:
                        counts["inserted"] += 1
                    elif previous == record.row_hash:
                        counts["unchanged"] += 1
                    else:
                        counts["updated"] += 1
                    values.append(
                        (
                            interface,
                            record.source_key_hash,
                            _json(record.source_key),
                            _json(record.payload),
                            schema_hash,
                            "ordered-column-names-v1",
                            record.row_hash,
                            start,
                            end,
                            batch_id,
                            batch_id,
                        )
                    )
                cursor.executemany(
                    "INSERT INTO cache_raw.source_record "
                    "(interface_name,source_key_hash,source_key,payload,schema_hash,"
                    "schema_hash_version,row_hash,"
                    "source_window_start,source_window_end,first_batch_id,last_batch_id,"
                    "local_sync_completed_at) "
                    "VALUES (%s,%s,%s::jsonb,%s::jsonb,%s,%s,%s,%s,%s,%s,%s,now()) "
                    "ON CONFLICT (interface_name,source_key_hash) DO UPDATE SET "
                    "source_key=EXCLUDED.source_key,payload=EXCLUDED.payload,"
                    "schema_hash=EXCLUDED.schema_hash,"
                    "schema_hash_version=EXCLUDED.schema_hash_version,"
                    "row_hash=EXCLUDED.row_hash,"
                    "source_window_start=EXCLUDED.source_window_start,"
                    "source_window_end=EXCLUDED.source_window_end,"
                    "last_batch_id=EXCLUDED.last_batch_id,last_seen_at=now(),"
                    "local_sync_completed_at=now()",
                    values,
                )
                return counts
        except Exception:
            raise IngestError(ErrorKind.INGEST_WRITE, "upsert_raw") from None

    def advance_checkpoint(
        self, interface: str, start: datetime, end: datetime, batch_id: int
    ) -> bool:
        try:
            with self._data.cursor() as cursor:
                cursor.execute(
                    "INSERT INTO sync_ops.sync_checkpoint "
                    "(interface_name,last_window_start,last_window_end,last_batch_id,"
                    "records_total) "
                    "VALUES (%s,%s,%s,%s,(SELECT count(*) FROM cache_raw.source_record "
                    "WHERE interface_name=%s)) "
                    "ON CONFLICT (interface_name) DO UPDATE SET "
                    "last_window_start=EXCLUDED.last_window_start,"
                    "last_window_end=EXCLUDED.last_window_end,"
                    "last_batch_id=EXCLUDED.last_batch_id,"
                    "records_total=EXCLUDED.records_total,updated_at=now() "
                    "WHERE sync_ops.sync_checkpoint.last_window_end IS NULL OR "
                    "EXCLUDED.last_window_end > sync_ops.sync_checkpoint.last_window_end",
                    (interface, start, end, batch_id, interface),
                )
                return bool(cursor.rowcount > 0)
        except Exception:
            raise IngestError(ErrorKind.INGEST_WRITE, "advance_checkpoint") from None

    def commit_data(self) -> None:
        try:
            self._data.commit()
        except Exception:
            raise IngestError(ErrorKind.INGEST_WRITE, "commit_data") from None
        finally:
            self._close_attr("_data")

    def rollback_data(self) -> None:
        if self._data is None:
            return
        try:
            self._data.rollback()
        finally:
            self._close_attr("_data")

    def drop_data(self) -> None:
        self._close_attr("_data")

    def start_publish(self, interface: str, evidence_version: str) -> int:
        try:
            with self._control.cursor() as cursor:
                cursor.execute(
                    "INSERT INTO sync_ops.publish_batch "
                    "(interface_name,evidence_version,status) "
                    "VALUES (%s,%s,'running') RETURNING publish_batch_id",
                    (interface, evidence_version),
                )
                row = cursor.fetchone()
                if row is None:
                    raise RuntimeError
                return int(row[0])
        except Exception:
            raise IngestError(ErrorKind.INGEST_WRITE, "start_publish") from None

    def start_inspection(self, start: date, end: date) -> int:
        try:
            with self._control.cursor() as cursor:
                cursor.execute(
                    "INSERT INTO sync_ops.inspection_batch "
                    "(window_start,window_end,status) VALUES (%s,%s,'running') "
                    "RETURNING inspection_batch_id",
                    (start, end),
                )
                row = cursor.fetchone()
                if row is None:
                    raise RuntimeError
                return int(row[0])
        except Exception:
            raise IngestError(ErrorKind.INGEST_WRITE, "start_inspection") from None

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
    ) -> None:
        try:
            with self._control.cursor() as cursor:
                cursor.execute(
                    "INSERT INTO sync_ops.inspection_run "
                    "(inspection_batch_id,interface_name,window_start,window_end,status,"
                    "row_count,schema_hash,error_kind,error_location) "
                    "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s) "
                    "ON CONFLICT (inspection_batch_id,interface_name,window_start,window_end) "
                    "DO UPDATE SET status=EXCLUDED.status,row_count=EXCLUDED.row_count,"
                    "schema_hash=EXCLUDED.schema_hash,error_kind=EXCLUDED.error_kind,"
                    "error_location=EXCLUDED.error_location",
                    (
                        batch_id,
                        interface,
                        start,
                        end,
                        status,
                        row_count,
                        schema_hash,
                        error_kind,
                        error_location,
                    ),
                )
        except Exception:
            raise IngestError(ErrorKind.INGEST_WRITE, "record_inspection_run") from None

    def begin_snapshot(self) -> None:
        self.begin_data()

    def write_inspection_schema(
        self,
        batch_id: int,
        interface: str,
        schema_hash: str,
        columns: Sequence[str],
        source_types: Sequence[str],
    ) -> None:
        try:
            with self._data.cursor() as cursor:
                cursor.execute(
                    "INSERT INTO sync_ops.inspection_schema "
                    "(inspection_batch_id,interface_name,schema_hash,column_names,source_types) "
                    "VALUES (%s,%s,%s,%s::jsonb,%s::jsonb) ON CONFLICT DO NOTHING",
                    (
                        batch_id,
                        interface,
                        schema_hash,
                        _json(list(columns)),
                        _json(list(source_types)),
                    ),
                )
        except Exception:
            raise IngestError(ErrorKind.INGEST_WRITE, "write_inspection_schema") from None

    def write_snapshot(
        self,
        batch_id: int,
        interface: str,
        start: date,
        end: date,
        schema_hash: str,
        rows: Sequence[SnapshotRecord],
    ) -> None:
        try:
            with self._data.cursor() as cursor:
                cursor.executemany(
                    "INSERT INTO cache_raw.source_snapshot "
                    "(inspection_batch_id,interface_name,window_start,window_end,ordinal,"
                    "source_key,source_key_hash,case_key_hash,key_complete,schema_hash,payload) "
                    "VALUES (%s,%s,%s,%s,%s,%s::jsonb,%s,%s,%s,%s,%s::jsonb)",
                    [
                        (
                            batch_id,
                            interface,
                            start,
                            end,
                            row.ordinal,
                            _json(row.source_key) if row.source_key is not None else None,
                            row.source_key_hash,
                            row.case_key_hash,
                            row.key_complete,
                            schema_hash,
                            _json(row.payload),
                        )
                        for row in rows
                    ],
                )
        except Exception:
            raise IngestError(ErrorKind.INGEST_WRITE, "write_snapshot") from None

    def commit_snapshot(self) -> None:
        self.commit_data()

    def rollback_snapshot(self) -> None:
        self.rollback_data()

    def finish_inspection(self, batch_id: int, status: str) -> None:
        try:
            with self._control.cursor() as cursor:
                cursor.execute(
                    "UPDATE sync_ops.inspection_batch SET status=%s,finished_at=now() "
                    "WHERE inspection_batch_id=%s AND status='running'",
                    (status, batch_id),
                )
        except Exception:
            raise IngestError(ErrorKind.INGEST_WRITE, "finish_inspection") from None

    def load_inspection_schemas(
        self, batch_id: int
    ) -> Mapping[str, tuple[Sequence[str], Sequence[str]]]:
        connection = _connect(
            self._settings, ErrorKind.INGEST_CONNECT, "profile_schema_connect", readonly=True
        )
        self._profile_read = connection
        try:
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT interface_name,column_names,source_types "
                    "FROM sync_ops.inspection_schema WHERE inspection_batch_id=%s",
                    (batch_id,),
                )
                return {
                    str(row[0]): (
                        tuple(str(value) for value in row[1]),
                        tuple(str(value) for value in row[2]),
                    )
                    for row in cursor.fetchall()
                }
        except Exception:
            raise IngestError(ErrorKind.INGEST_WRITE, "load_profile_schemas") from None

    def open_profile_rows(self, batch_id: int) -> PostgresProfileCursor:
        if self._profile_read is None:
            self._profile_read = _connect(
                self._settings,
                ErrorKind.INGEST_CONNECT,
                "profile_read_connect",
                readonly=True,
            )
        try:
            cursor = self._profile_read.cursor(name="medqc_profile_stream")
            cursor.execute(
                "SELECT interface_name,payload,source_key_hash,case_key_hash,key_complete "
                "FROM cache_raw.source_snapshot WHERE inspection_batch_id=%s "
                "ORDER BY interface_name,window_start,ordinal",
                (batch_id,),
            )
            return PostgresProfileCursor(cursor)
        except Exception:
            raise IngestError(ErrorKind.INGEST_WRITE, "open_profile_rows") from None

    def replace_profiles(
        self,
        batch_id: int,
        columns: Sequence[Mapping[str, Any]],
        relations: Sequence[Mapping[str, Any]],
    ) -> None:
        connection = _connect(
            self._settings, ErrorKind.INGEST_CONNECT, "profile_write_connect"
        )
        try:
            with connection.cursor() as cursor:
                cursor.execute(
                    "DELETE FROM sync_ops.source_column_profile "
                    "WHERE inspection_batch_id=%s",
                    (batch_id,),
                )
                cursor.execute(
                    "DELETE FROM sync_ops.source_relation_profile "
                    "WHERE inspection_batch_id=%s",
                    (batch_id,),
                )
                cursor.executemany(
                    "INSERT INTO sync_ops.source_column_profile "
                    "(inspection_batch_id,interface_name,ordinal,column_name,source_type,"
                    "row_count,non_null_count,non_null_rate,distinct_count,"
                    "distinct_is_approx,safe_types,"
                    "min_length,max_length,min_date,max_date,candidate_key_missing_count) "
                    "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s::jsonb,%s,%s,%s,%s,%s)",
                    [
                        (
                            batch_id,
                            row["interface"],
                            row["ordinal"],
                            row["column_name"],
                            row["source_type"],
                            row["row_count"],
                            row["non_null_count"],
                            row["non_null_rate"],
                            row["distinct_count"],
                            row["distinct_is_approx"],
                            _json(
                                [
                                    value
                                    for value in str(row["safe_type_categories"]).split("|")
                                    if value
                                ]
                            ),
                            row["min_length"] or None,
                            row["max_length"] or None,
                            row["min_date"] or None,
                            row["max_date"] or None,
                            row["candidate_key_missing_count"],
                        )
                        for row in columns
                    ],
                )
                cursor.executemany(
                    "INSERT INTO sync_ops.source_relation_profile "
                    "(inspection_batch_id,interface_name,relation_name,relation_fields,"
                    "anchor_interface,row_count,complete_rows,missing_rows,matched_rows,"
                    "orphan_rows,duplicate_rows) "
                    "VALUES (%s,%s,%s,%s::jsonb,%s,%s,%s,%s,%s,%s,%s)",
                    [
                        (
                            batch_id,
                            row["interface"],
                            row["relation_name"],
                            _json(list(row["relation_fields"])),
                            (
                                row["interface"]
                                if row["relation_name"] == "candidate_key"
                                else "web.mr"
                            ),
                            row["row_count"],
                            row["complete_rows"],
                            row["missing_rows"],
                            row["matched_rows"],
                            row["orphan_rows"],
                            row["duplicate_rows"],
                        )
                        for row in relations
                    ],
                )
            connection.commit()
        except Exception:
            with suppress(Exception):
                connection.rollback()
            raise IngestError(ErrorKind.INGEST_WRITE, "replace_profiles") from None
        finally:
            with suppress(Exception):
                connection.close()

    def open_verified_raw(
        self, interface: str, target_key_fields: Sequence[str]
    ) -> PostgresRawPublishCursor:
        self._publish_read = _connect(
            self._settings, ErrorKind.INGEST_CONNECT, "publish_read_connect", readonly=True
        )
        try:
            with self._publish_read.cursor() as metadata:
                metadata.execute(
                    "SELECT DISTINCT schema_hash FROM cache_raw.source_record "
                    "WHERE interface_name=%s",
                    (interface,),
                )
                hashes = [str(row[0]) for row in metadata.fetchall()]
                if len(hashes) != 1:
                    raise IngestError(
                        ErrorKind.PUBLISH_CONTRACT, "raw_schema_hash_not_unique"
                    )
                schema_hash = hashes[0]
                metadata.execute(
                    "SELECT column_names FROM sync_ops.source_schema "
                    "WHERE interface_name=%s AND schema_hash=%s",
                    (interface, schema_hash),
                )
                row = metadata.fetchone()
                if row is None or not isinstance(row[0], list):
                    raise IngestError(ErrorKind.PUBLISH_CONTRACT, "raw_schema_missing")
                columns = tuple(str(value) for value in row[0])
                key_expressions = ",".join(
                    f"payload->>{_json_field(field)}" for field in target_key_fields
                )
                metadata.execute(
                    "SELECT 1 FROM cache_raw.source_record "
                    "WHERE interface_name=%s AND schema_hash=%s "
                    f"GROUP BY {key_expressions} HAVING count(*)>1 LIMIT 1",
                    (interface, schema_hash),
                )
                if metadata.fetchone() is not None:
                    raise IngestError(
                        ErrorKind.PUBLISH_CONTRACT, "target_key_not_unique"
                    )
            cursor = self._publish_read.cursor(name="medqc_publish_stream")
            cursor.execute(
                "SELECT payload,local_sync_completed_at,last_batch_id,"
                "source_key_hash,row_hash FROM cache_raw.source_record "
                "WHERE interface_name=%s AND schema_hash=%s ORDER BY source_key_hash",
                (interface, schema_hash),
            )
            return PostgresRawPublishCursor(cursor, schema_hash, columns)
        except IngestError:
            self._close_attr("_publish_read")
            raise
        except Exception:
            self._close_attr("_publish_read")
            raise IngestError(ErrorKind.INGEST_WRITE, "open_verified_raw") from None

    def begin_publish_data(self) -> None:
        self._publish_data = _connect(
            self._settings, ErrorKind.INGEST_CONNECT, "publish_lineage_connect"
        )
        self._publish_data.autocommit = False

    def write_publish_lineage(
        self, publish_batch_id: int, rows: Sequence[PublishLineage]
    ) -> None:
        try:
            with self._publish_data.cursor() as cursor:
                cursor.executemany(
                    "INSERT INTO sync_ops.publish_lineage "
                    "(publish_batch_id,source_batch_id,source_key_hash,row_hash) "
                    "VALUES (%s,%s,%s,%s) ON CONFLICT DO NOTHING",
                    [
                        (
                            publish_batch_id,
                            row.source_batch_id,
                            row.source_key_hash,
                            row.row_hash,
                        )
                        for row in rows
                    ],
                )
        except Exception:
            raise IngestError(ErrorKind.INGEST_WRITE, "write_publish_lineage") from None

    def commit_publish_data(self) -> None:
        try:
            self._publish_data.commit()
        except Exception:
            raise IngestError(ErrorKind.INGEST_WRITE, "commit_publish_lineage") from None
        finally:
            self._close_attr("_publish_data")

    def rollback_publish_data(self) -> None:
        if self._publish_data is None:
            return
        try:
            self._publish_data.rollback()
        finally:
            self._close_attr("_publish_data")

    def drop_publish_data(self) -> None:
        self._close_attr("_publish_data")
        self._close_attr("_publish_read")

    def mark_publish_succeeded(
        self, publish_batch_id: int, schema_hash: str, selected: int, written: int
    ) -> None:
        try:
            with self._control.cursor() as cursor:
                cursor.execute(
                    "UPDATE sync_ops.publish_batch SET status='succeeded',finished_at=now(),"
                    "schema_hash=%s,rows_selected=%s,rows_written=%s "
                    "WHERE publish_batch_id=%s AND status='running'",
                    (schema_hash, selected, written, publish_batch_id),
                )
        except Exception:
            raise IngestError(ErrorKind.INGEST_WRITE, "mark_publish_succeeded") from None

    def mark_publish_failed(self, publish_batch_id: int, kind: str, location: str) -> None:
        try:
            with self._control.cursor() as cursor:
                cursor.execute(
                    "UPDATE sync_ops.publish_batch SET status='failed',finished_at=now(),"
                    "error_kind=%s,error_location=%s "
                    "WHERE publish_batch_id=%s AND status='running'",
                    (kind, location, publish_batch_id),
                )
        except Exception:
            raise IngestError(ErrorKind.INGEST_WRITE, "mark_publish_failed") from None

    def close(self) -> None:
        self.drop_data()
        self.drop_publish_data()
        self._close_attr("_profile_read")
        self._close_attr("_control")

    def _close_attr(self, name: str) -> None:
        connection = getattr(self, name)
        setattr(self, name, None)
        if connection is not None:
            with suppress(Exception):
                connection.close()


class PostgresProfileCursor:
    def __init__(self, cursor: Any) -> None:
        self._cursor = cursor

    def fetchmany(self, size: int) -> Sequence[ProfileSnapshotRow]:
        try:
            return tuple(
                ProfileSnapshotRow(
                    interface=str(row[0]),
                    payload=row[1],
                    source_key_hash=str(row[2]) if row[2] is not None else None,
                    case_key_hash=str(row[3]) if row[3] is not None else None,
                    key_complete=bool(row[4]),
                )
                for row in self._cursor.fetchmany(size)
            )
        except Exception:
            raise IngestError(ErrorKind.INGEST_WRITE, "profile_fetchmany") from None

    def close(self) -> None:
        with suppress(Exception):
            self._cursor.close()


class PostgresRawPublishCursor:
    def __init__(self, cursor: Any, schema_hash: str, source_columns: Sequence[str]) -> None:
        self._cursor = cursor
        self._schema_hash = schema_hash
        self._source_columns = tuple(source_columns)

    @property
    def schema_hash(self) -> str:
        return self._schema_hash

    @property
    def source_columns(self) -> Sequence[str]:
        return self._source_columns

    def fetchmany(self, size: int) -> Sequence[PublishRecord]:
        try:
            return tuple(
                PublishRecord(
                    payload=row[0],
                    completed_at=row[1],
                    source_batch_id=int(row[2]),
                    source_key_hash=str(row[3]),
                    row_hash=str(row[4]),
                )
                for row in self._cursor.fetchmany(size)
            )
        except Exception:
            raise IngestError(ErrorKind.INGEST_WRITE, "publish_fetchmany") from None

    def close(self) -> None:
        with suppress(Exception):
            self._cursor.close()


class PostgresCdmRepository:
    def __init__(self, settings: PostgresSettings) -> None:
        self._settings = settings
        self._connection: Any = None

    def begin(self) -> None:
        self._connection = _connect(
            self._settings, ErrorKind.CDM_CONNECT, "cdm_connect"
        )
        self._connection.autocommit = False

    def prepare_target_contract(self, target: PublishSpec) -> PublishSpec:
        try:
            columns, primary_key = _read_cdm_contract(self._connection, target)
        except IngestError:
            raise
        except Exception:
            raise IngestError(ErrorKind.CDM_WRITE, "read_cdm_contract") from None
        if tuple(primary_key) != target.primary_key:
            raise IngestError(ErrorKind.PUBLISH_CONTRACT, "cdm_primary_key_mismatch")
        compatible = tuple(
            mapping
            for mapping in target.mappings
            if mapping.target in columns
            and columns[mapping.target]
            in _TARGET_TYPE_COMPATIBILITY[mapping.target_type]
        )
        compatible_names = {mapping.target for mapping in compatible}
        if set(target.required_columns) - compatible_names:
            raise IngestError(ErrorKind.PUBLISH_CONTRACT, "cdm_required_columns_missing")
        return PublishSpec(
            schema=target.schema,
            table=target.table,
            primary_key=target.primary_key,
            required_columns=target.required_columns,
            mappings=compatible,
        )

    def upsert_target(
        self, target: PublishSpec, rows: Sequence[Mapping[str, Any]]
    ) -> int:
        if not rows:
            return 0
        columns = target.target_columns
        keys = frozenset(target.primary_key)
        insert_columns = ",".join(_ident(column) for column in columns)
        placeholders = ",".join("%s" for _ in columns)
        update = ",".join(
            f"{_ident(column)}=EXCLUDED.{_ident(column)}"
            for column in columns
            if column not in keys
        )
        conflict = ",".join(_ident(column) for column in target.primary_key)
        sql = (
            f"INSERT INTO {_ident(target.schema)}.{_ident(target.table)} "
            f"({insert_columns}) VALUES ({placeholders}) "
            f"ON CONFLICT ({conflict}) DO UPDATE SET {update}"
        )
        try:
            with self._connection.cursor() as cursor:
                cursor.executemany(sql, [tuple(row[column] for column in columns) for row in rows])
            return len(rows)
        except Exception:
            raise IngestError(ErrorKind.CDM_WRITE, "upsert_cdm_target") from None

    def commit(self) -> None:
        try:
            self._connection.commit()
        except Exception:
            raise IngestError(ErrorKind.CDM_WRITE, "commit_cdm") from None

    def rollback(self) -> None:
        if self._connection is not None:
            with suppress(Exception):
                self._connection.rollback()

    def close(self) -> None:
        connection, self._connection = self._connection, None
        if connection is not None:
            with suppress(Exception):
                connection.close()


_TARGET_TYPE_COMPATIBILITY = {
    "text": frozenset({"character varying", "character", "text"}),
    "date": frozenset({"date"}),
    "datetime": frozenset({"timestamp without time zone"}),
    "timestamptz": frozenset({"timestamp with time zone"}),
}


def _read_cdm_contract(
    connection: Any, target: PublishSpec
) -> tuple[dict[str, str], list[str]]:
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT column_name,data_type FROM information_schema.columns "
            "WHERE table_schema=%s AND table_name=%s ORDER BY ordinal_position",
            (target.schema, target.table),
        )
        columns = {str(row[0]): str(row[1]) for row in cursor.fetchall()}
        cursor.execute(
            "SELECT a.attname FROM pg_index i "
            "JOIN pg_class c ON c.oid=i.indrelid "
            "JOIN pg_namespace n ON n.oid=c.relnamespace "
            "JOIN unnest(i.indkey) WITH ORDINALITY AS k(attnum,ord) ON true "
            "JOIN pg_attribute a ON a.attrelid=c.oid AND a.attnum=k.attnum "
            "WHERE n.nspname=%s AND c.relname=%s AND i.indisprimary "
            "ORDER BY k.ord",
            (target.schema, target.table),
        )
        primary_key = [str(row[0]) for row in cursor.fetchall()]
    return columns, primary_key


class PostgresCheckRepository:
    def __init__(self, ingest: PostgresSettings, cdm: PostgresSettings) -> None:
        self._ingest_settings = ingest
        self._cdm_settings = cdm
        self._connections: list[Any] = []

    def check_ingest_contract(self, stale_minutes: int) -> Sequence[tuple[str, bool, str]]:
        connection = _connect(
            self._ingest_settings,
            ErrorKind.INGEST_CONNECT,
            "check_ingest_connect",
            readonly=True,
        )
        self._connections.append(connection)
        try:
            with connection.cursor() as cursor:
                expected = (
                    "cache_raw.source_record",
                    "cache_raw.source_snapshot",
                    "sync_ops.source_interface",
                    "sync_ops.source_schema",
                    "sync_ops.sync_batch",
                    "sync_ops.sync_checkpoint",
                    "sync_ops.publish_batch",
                    "sync_ops.publish_lineage",
                    "sync_ops.inspection_batch",
                    "sync_ops.inspection_run",
                    "sync_ops.inspection_schema",
                    "sync_ops.source_column_profile",
                    "sync_ops.source_relation_profile",
                    "sync_ops.source_target_contract",
                )
                missing: list[str] = []
                for relation in expected:
                    cursor.execute("SELECT to_regclass(%s)", (relation,))
                    row = cursor.fetchone()
                    if row is None or row[0] is None:
                        missing.append(relation)
                if missing:
                    return (
                        ("ingest_contract", False, "missing_relations"),
                        ("interface_registry", False, "unavailable"),
                        ("checkpoint", False, "unavailable"),
                        ("stale_running", False, "unavailable"),
                    )
                cursor.execute(
                    "SELECT interface_name,procedure_name,argument_count,key_fields,"
                    "publish_target,is_enabled FROM sync_ops.source_interface "
                    "WHERE is_enabled=true"
                )
                rows = cursor.fetchall()
                actual = {
                    str(row[0]): (
                        str(row[1]),
                        int(row[2]),
                        tuple(str(value) for value in row[3]),
                        str(row[4]),
                        bool(row[5]),
                    )
                    for row in rows
                }
                expected_registry = {
                    name: (
                        spec.procedure,
                        spec.argument_count,
                        spec.key_fields,
                        str(spec.publish_target),
                        True,
                    )
                    for name, spec in INTERFACE_REGISTRY.items()
                }
                registry_ok = actual == expected_registry
                cursor.execute(
                    "SELECT count(*) FROM sync_ops.sync_checkpoint WHERE interface_name='web.mr'"
                )
                checkpoint_count = int(cursor.fetchone()[0])
                cursor.execute(
                    "SELECT count(*) FROM sync_ops.sync_batch "
                    "WHERE status='running' AND started_at < now()-(%s*interval '1 minute')",
                    (stale_minutes,),
                )
                stale_count = int(cursor.fetchone()[0])
            return (
                ("ingest_contract", True, "ok"),
                ("interface_registry", registry_ok, "ok" if registry_ok else "mismatch"),
                ("checkpoint", checkpoint_count <= 1, f"entries={checkpoint_count}"),
                ("stale_running", stale_count == 0, f"count={stale_count}"),
            )
        except IngestError:
            raise
        except Exception:
            raise IngestError(ErrorKind.INGEST_WRITE, "check_ingest_contract") from None

    def check_cdm_contract(
        self, targets: Sequence[PublishSpec]
    ) -> Sequence[tuple[str, bool, str]]:
        connection = _connect(
            self._cdm_settings,
            ErrorKind.CDM_CONNECT,
            "check_cdm_connect",
            readonly=True,
        )
        self._connections.append(connection)
        try:
            results: list[tuple[str, bool, str]] = []
            for target in targets:
                columns, primary_key = _read_cdm_contract(connection, target)
                expected_types = {
                    mapping.target: mapping.target_type for mapping in target.mappings
                }
                compatible = {
                    column
                    for column, target_type in expected_types.items()
                    if column in columns
                    and columns[column] in _TARGET_TYPE_COMPATIBILITY[target_type]
                }
                columns_ok = not (set(target.required_columns) - compatible)
                optional_raw_only = set(expected_types) - compatible
                key_ok = tuple(primary_key) == target.primary_key
                prefix = f"cdm_{target.table}"
                results.extend(
                    (
                        (
                            f"{prefix}_columns",
                            columns_ok,
                            f"owned={len(compatible)},raw_only={len(optional_raw_only)}",
                        ),
                        (f"{prefix}_primary_key", key_ok, "ok" if key_ok else "mismatch"),
                    )
                )
            return tuple(results)
        except Exception:
            raise IngestError(ErrorKind.CDM_WRITE, "check_cdm_contract") from None

    def close(self) -> None:
        while self._connections:
            connection = self._connections.pop()
            with suppress(Exception):
                connection.close()
