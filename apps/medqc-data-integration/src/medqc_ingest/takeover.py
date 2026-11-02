"""固定十三来源的单次接管；旧库只读，目标必须是独立的空 ingest 验收库。"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping
from datetime import date, datetime, time, timedelta, timezone
from typing import Any

from medqc_ingest.domain import (
    INTERFACE_REGISTRY,
    ErrorKind,
    IngestError,
    canonical_json,
    resolve_interface,
    schema_signature,
    sha256_hex,
)
from medqc_ingest.orders_lab_exam_contracts import MORE_ARGUMENT_COUNTS
from medqc_ingest.repositories.postgres import _ident, _json
from medqc_ingest.verification import ACCEPTANCE_DATABASE

EXPECTED_COUNTS = {
    "web.mr": 169,
    "web.admission_record": 201,
    "web.first_course_record": 201,
    "web.daily_course_record": 263,
    "web.senior_course_record": 791,
    "web.consultation_record": 1,
    "web.discharge_record": 177,
    "web.inpat_drug_order": 8622,
    "web.inpat_nondrug_order": 24616,
    "web.labtest_master": 3269,
    "web.labtest_item": 5601,
    "web.labtest_item_report": 42391,
    "web.exam_item_report": 899,
}
ARCHIVE_TABLES = (
    "sync_ops.source_interface",
    "sync_ops.source_schema",
    "sync_ops.sync_batch",
    "cache_raw.source_record",
    "cache_raw.source_record_version",
)
_SHANGHAI = timezone(timedelta(hours=8))


def validate_target_database(name: str, role: str = "ingest") -> None:
    if role not in {"ingest", "cdm", "restore"} or not re.fullmatch(
        rf"medqc_{role}_takeover_[0-9]{{14}}", name
    ):
        raise IngestError(ErrorKind.CONFIGURATION, "takeover_target_database")


def legacy_window(start: Any, end: Any) -> tuple[datetime, datetime]:
    """旧接口窗口是单日查询参数；规范化为上海时区半开区间，原值另存归档。"""
    try:

        def parse(value: Any) -> tuple[date, datetime | None]:
            text = str(value)
            if len(text) == 10:
                return date.fromisoformat(text), None
            timestamp = datetime.fromisoformat(text.replace("Z", "+00:00"))
            timestamp = (
                timestamp.astimezone(_SHANGHAI)
                if timestamp.tzinfo
                else timestamp.replace(tzinfo=_SHANGHAI)
            )
            return timestamp.date(), timestamp

        first, _start_time = parse(start)
        last, end_time = parse(end)
    except (TypeError, ValueError):
        raise IngestError(ErrorKind.PUBLISH_CONTRACT, "takeover_window") from None
    one_day = last == first or (
        last == first + timedelta(days=1) and end_time is not None and end_time.time() == time.min
    )
    if not one_day or not date(2026, 10, 26) <= first <= date(2026, 10, 28):
        raise IngestError(ErrorKind.PUBLISH_CONTRACT, "takeover_window")
    beginning = datetime(first.year, first.month, first.day, tzinfo=_SHANGHAI)
    return beginning, beginning + timedelta(days=1)


def validate_legacy_record(
    row: Mapping[str, Any], *, history: bool = False
) -> tuple[str, dict[str, Any]]:
    name = str(row.get("interface_name", ""))
    if name not in EXPECTED_COUNTS:
        raise IngestError(ErrorKind.INTERFACE, "takeover_interface")
    spec = resolve_interface(name)
    payload = row.get("payload")
    if not isinstance(payload, dict) or set(payload) != set(spec.source_columns):
        raise IngestError(ErrorKind.SCHEMA, "takeover_payload_columns")
    key: dict[str, Any] = {}
    for field in spec.key_fields:
        value = payload.get(field)
        if not isinstance(value, str) or not value.strip():
            raise IngestError(ErrorKind.KEY, "takeover_source_key")
        key[field] = value
    if sha256_hex(canonical_json(key)) != row.get("source_key_hash"):
        raise IngestError(ErrorKind.KEY, "takeover_key_hash")
    if "source_key" in row and row["source_key"] != key:
        raise IngestError(ErrorKind.KEY, "takeover_source_key_payload_mismatch")
    if sha256_hex(canonical_json(payload)) != row.get("row_hash"):
        raise IngestError(ErrorKind.SCHEMA, "takeover_row_hash")
    expected_hash = schema_signature(spec.source_columns)[0]
    original_hash = row.get("schema_hash")
    if not history:
        if original_hash is None or not str(original_hash).strip():
            if name not in MORE_ARGUMENT_COUNTS:
                raise IngestError(ErrorKind.SCHEMA, "takeover_blank_schema_outside_scope")
        elif original_hash != expected_hash:
            raise IngestError(ErrorKind.SCHEMA, "takeover_schema_hash")
    return expected_hash, key


def _table_name(qualified: str) -> str:
    return ".".join(_ident(part) for part in qualified.split("."))


def _rows(connection: Any, table: str, chunk_size: int) -> Any:
    ordering = {
        "sync_ops.source_interface": "interface_name",
        "sync_ops.source_schema": "interface_name,schema_hash",
        "sync_ops.sync_batch": "batch_id",
        "cache_raw.source_record": "interface_name,source_key_hash",
        "cache_raw.source_record_version": "interface_name,source_key_hash,batch_id,row_hash",
    }[table]
    with connection.cursor(name="medqc_takeover_read") as cursor:
        cursor.execute(f"SELECT to_jsonb(t) FROM {_table_name(table)} t ORDER BY {ordering}")
        while chunk := cursor.fetchmany(chunk_size):
            yield [row[0] for row in chunk]


def _identity(connection: Any) -> tuple[str, str]:
    with connection.cursor() as cursor:
        cursor.execute("SELECT current_database(),current_setting('transaction_read_only')")
        row = cursor.fetchone()
        return str(row[0]), str(row[1])


def _archive_table(source: Any, target: Any, table: str, chunk_size: int) -> tuple[int, str]:
    schema, name = table.split(".")
    with source.cursor() as cursor:
        cursor.execute(
            "SELECT column_name,data_type,udt_name,is_nullable,column_default "
            "FROM information_schema.columns WHERE table_schema=%s AND table_name=%s "
            "ORDER BY ordinal_position",
            (schema, name),
        )
        columns = cursor.fetchall()
    if not columns:
        raise IngestError(ErrorKind.SCHEMA, "takeover_archive_table_missing")
    count, digest = 0, hashlib.sha256()
    with target.cursor() as cursor:
        cursor.execute(
            "INSERT INTO takeover_archive.source_catalog(source_table,columns_json) "
            "VALUES (%s,%s::jsonb)",
            (table, _json(columns)),
        )
        for chunk in _rows(source, table, chunk_size):
            values = []
            for row in chunk:
                count += 1
                text = canonical_json(row)
                row_hash = sha256_hex(text)
                digest.update((row_hash + "\n").encode())
                values.append((table, count, text, row_hash))
            cursor.executemany(
                "INSERT INTO takeover_archive.source_row "
                "(source_table,row_number,record_json,record_hash) VALUES (%s,%s,%s::jsonb,%s)",
                values,
            )
    return count, digest.hexdigest()


def _archive_read(target: Any, table: str, chunk_size: int) -> Any:
    with target.cursor(name="medqc_takeover_archive") as cursor:
        cursor.execute(
            "SELECT record_json,record_hash FROM takeover_archive.source_row "
            "WHERE source_table=%s ORDER BY row_number",
            (table,),
        )
        while chunk := cursor.fetchmany(chunk_size):
            if any(sha256_hex(canonical_json(row[0])) != row[1] for row in chunk):
                raise IngestError(ErrorKind.SCHEMA, "takeover_archive_row_hash")
            yield [row[0] for row in chunk]


def _preflight_source(source: Any) -> None:
    with source.cursor() as cursor:
        cursor.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY")
        cursor.execute("SET LOCAL statement_timeout='120s'")
        cursor.execute("SET LOCAL timezone='Asia/Shanghai'")
    actual, readonly = _identity(source)
    if actual != ACCEPTANCE_DATABASE or readonly != "on":
        raise IngestError(ErrorKind.CONFIGURATION, "takeover_source_identity")
    with source.cursor() as cursor:
        cursor.execute("SELECT interface_name,count(*) FROM cache_raw.source_record GROUP BY 1")
        if {str(r[0]): int(r[1]) for r in cursor.fetchall()} != EXPECTED_COUNTS:
            raise IngestError(ErrorKind.PUBLISH_CONTRACT, "takeover_source_counts")
        cursor.execute("SELECT status,count(*) FROM sync_ops.sync_batch GROUP BY 1")
        if cursor.fetchall() != [("succeeded", 78)]:
            raise IngestError(ErrorKind.PUBLISH_CONTRACT, "takeover_source_batches")


def import_legacy(
    source: Any, target: Any, target_database: str, chunk_size: int = 1000
) -> dict[str, Any]:
    """所有归档、转换、来源映射与完成标记一次提交；失败回滚整个接管。"""
    validate_target_database(target_database)
    if chunk_size <= 0:
        raise IngestError(ErrorKind.CONFIGURATION, "takeover_chunk_size")
    try:
        _preflight_source(source)
        actual, readonly = _identity(target)
        if actual != target_database or readonly != "off":
            raise IngestError(ErrorKind.CONFIGURATION, "takeover_target_identity")
        with target.cursor() as cursor:
            cursor.execute("SELECT pg_try_advisory_xact_lock(20261030,13)")
            if not cursor.fetchone()[0]:
                raise IngestError(ErrorKind.LOCK, "takeover_lock_busy")
            cursor.execute("SELECT report_json FROM sync_ops.takeover_marker WHERE marker_id=1")
            if cursor.fetchone() is not None:
                raise IngestError(
                    ErrorKind.PUBLISH_CONTRACT, "takeover_already_completed_verify_only"
                )
            for table in (
                "cache_raw.source_record",
                "cache_raw.source_record_version",
                "sync_ops.sync_batch",
                "sync_ops.sync_checkpoint",
                "sync_ops.publish_batch",
                "sync_ops.publish_lineage",
                "takeover_archive.source_row",
                "takeover_archive.source_catalog",
                "sync_ops.takeover_batch_map",
            ):
                cursor.execute(f"SELECT count(*) FROM {_table_name(table)}")
                if cursor.fetchone()[0] != 0:
                    raise IngestError(ErrorKind.PUBLISH_CONTRACT, "takeover_target_not_empty")
        archived = {}
        for table in ARCHIVE_TABLES:
            count, digest = _archive_table(source, target, table, chunk_size)
            archived[table] = {"rows": count, "digest": digest}
        report = _normalize_archive(target, archived, chunk_size)
        with target.cursor() as cursor:
            cursor.execute(
                "INSERT INTO sync_ops.takeover_marker(marker_id,source_database,report_json) "
                "VALUES (1,%s,%s::jsonb)",
                (ACCEPTANCE_DATABASE, _json(report)),
            )
        target.commit()
        return report
    except IngestError:
        target.rollback()
        raise
    except Exception:
        target.rollback()
        raise IngestError(ErrorKind.INGEST_WRITE, "takeover_import") from None


def _normalize_archive(target: Any, archived: dict[str, Any], chunk_size: int) -> dict[str, Any]:
    batches: dict[int, tuple[int, datetime, datetime, str]] = {}
    known_schemas: set[str] = set()
    with target.cursor() as cursor:
        for chunk in _archive_read(target, "sync_ops.source_schema", chunk_size):
            for row in chunk:
                name = str(row.get("interface_name", ""))
                if name not in INTERFACE_REGISTRY:
                    raise IngestError(ErrorKind.SCHEMA, "takeover_metadata_interface")
                columns = row.get("column_names_json", row.get("column_names"))
                if isinstance(columns, str):
                    columns = json.loads(columns)
                spec = resolve_interface(name)
                digest = schema_signature(spec.source_columns)[0]
                if columns != list(spec.source_columns) or row.get("schema_hash") != digest:
                    raise IngestError(ErrorKind.SCHEMA, "takeover_ordered_metadata")
                known_schemas.add(name)
        if known_schemas != set(INTERFACE_REGISTRY):
            raise IngestError(ErrorKind.SCHEMA, "takeover_metadata_missing")
        for name, spec in INTERFACE_REGISTRY.items():
            cursor.execute(
                "INSERT INTO sync_ops.source_schema "
                "(interface_name,schema_hash,schema_hash_version,column_count,column_names) "
                "VALUES (%s,%s,'ordered-column-names-v1',%s,%s::jsonb)",
                (
                    name,
                    schema_signature(spec.source_columns)[0],
                    len(spec.source_columns),
                    _json(spec.source_columns),
                ),
            )
        for chunk in _archive_read(target, "sync_ops.sync_batch", chunk_size):
            for row in chunk:
                old_id, name = int(row["batch_id"]), str(row["interface_name"])
                if (
                    name not in INTERFACE_REGISTRY
                    or row["status"] != "succeeded"
                    or old_id in batches
                ):
                    raise IngestError(ErrorKind.PUBLISH_CONTRACT, "takeover_batch_contract")
                start, end = legacy_window(row["window_start"], row["window_end"])
                cursor.execute(
                    "INSERT INTO sync_ops.sync_batch "
                    "(interface_name,window_start,window_end,status,finished_at,evidence_version,"
                    "rows_fetched,rows_inserted,rows_updated,rows_unchanged,checkpoint_state) "
                    "VALUES (%s,%s,%s,'succeeded',now(),%s,%s,%s,%s,%s,'held') RETURNING batch_id",
                    (
                        name,
                        start,
                        end,
                        f"{INTERFACE_REGISTRY[name].evidence_version};takeover-v1:{old_id}",
                        int(row.get("rows_fetched") or 0),
                        int(row.get("rows_inserted") or 0),
                        int(row.get("rows_updated") or 0),
                        int(row.get("rows_unchanged") or 0),
                    ),
                )
                new_id = int(cursor.fetchone()[0])
                batches[old_id] = new_id, start, end, name
                cursor.execute(
                    "INSERT INTO sync_ops.takeover_batch_map VALUES (%s,%s)", (old_id, new_id)
                )
        raw_counts = dict.fromkeys(INTERFACE_REGISTRY, 0)
        blank_counts = dict.fromkeys(INTERFACE_REGISTRY, 0)
        for chunk in _archive_read(target, "cache_raw.source_record", chunk_size):
            values: list[tuple[Any, ...]] = []
            for row in chunk:
                digest, key = validate_legacy_record(row)
                name = str(row["interface_name"])
                first = batches.get(int(row["first_batch_id"]))
                last = batches.get(int(row["last_batch_id"]))
                if first is None or last is None or first[3] != name or last[3] != name:
                    raise IngestError(ErrorKind.PUBLISH_CONTRACT, "takeover_batch_reference")
                start, end = legacy_window(row["source_window_start"], row["source_window_end"])
                completed = row.get("local_sync_completed_at") or row.get("first_seen_at")
                if not completed:
                    raise IngestError(
                        ErrorKind.PUBLISH_CONTRACT, "takeover_completion_time_missing"
                    )
                raw_counts[name] += 1
                blank_counts[name] += int(not str(row.get("schema_hash") or "").strip())
                values.append(
                    (
                        name,
                        row["source_key_hash"],
                        _json(key),
                        _json(row["payload"]),
                        digest,
                        row["row_hash"],
                        start,
                        end,
                        first[0],
                        last[0],
                        completed,
                    )
                )
            cursor.executemany(
                "INSERT INTO cache_raw.source_record "
                "(interface_name,source_key_hash,source_key,payload,schema_hash,schema_hash_version,"
                "row_hash,source_window_start,source_window_end,first_batch_id,last_batch_id,"
                "local_sync_completed_at) "
                "VALUES (%s,%s,%s::jsonb,%s::jsonb,%s,'ordered-column-names-v1',%s,%s,%s,%s,%s,%s)",
                values,
            )
        history_count = 0
        for chunk in _archive_read(target, "cache_raw.source_record_version", chunk_size):
            values = []
            for row in chunk:
                digest, key = validate_legacy_record(row, history=True)
                name = str(row["interface_name"])
                batch = batches.get(int(row["batch_id"]))
                if batch is None or batch[3] != name:
                    raise IngestError(ErrorKind.PUBLISH_CONTRACT, "takeover_history_batch")
                history_count += 1
                values.append(
                    (
                        name,
                        row["source_key_hash"],
                        batch[0],
                        digest,
                        row["row_hash"],
                        _json(key),
                        _json(row["payload"]),
                    )
                )
            cursor.executemany(
                "INSERT INTO cache_raw.source_record_version "
                "(interface_name,source_key_hash,batch_id,schema_hash,schema_hash_version,"
                "row_hash,source_key,payload) "
                "VALUES (%s,%s,%s,%s,'ordered-column-names-v1',%s,%s::jsonb,%s::jsonb)",
                values,
            )
        if (
            raw_counts != EXPECTED_COUNTS
            or history_count != archived["cache_raw.source_record_version"]["rows"]
        ):
            raise IngestError(ErrorKind.PUBLISH_CONTRACT, "takeover_final_counts")
        cursor.execute(
            "SELECT count(*) FROM cache_raw.source_record r WHERE NOT EXISTS "
            "(SELECT 1 FROM cache_raw.source_record_version v "
            "WHERE v.interface_name=r.interface_name "
            "AND v.source_key_hash=r.source_key_hash AND v.row_hash=r.row_hash)"
        )
        if cursor.fetchone()[0]:
            raise IngestError(ErrorKind.PUBLISH_CONTRACT, "takeover_current_history_missing")
    source_windows = {
        name: max(batch[2] for batch in batches.values() if batch[3] == name).isoformat()
        for name in INTERFACE_REGISTRY
    }
    return {
        "source_database": ACCEPTANCE_DATABASE,
        "archives": archived,
        "raw_counts": raw_counts,
        "history_rows": history_count,
        "imported_batches": len(batches),
        "original_blank_schema_rows": blank_counts,
        "checkpoint_created": False,
        "schema_authority": "migration_revalidated_v1",
        "contains_phi": False,
        "contains_raw_values": False,
        "source_windows": source_windows,
    }


def verify_takeover(target: Any, target_database: str, chunk_size: int = 1000) -> dict[str, Any]:
    """重跑走只读核对，不重新接管；历史归档与当前规范化内容分别核查。"""
    validate_target_database(target_database)
    if chunk_size <= 0:
        raise IngestError(ErrorKind.CONFIGURATION, "takeover_chunk_size")
    with target.cursor() as cursor:
        cursor.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY")
        if _identity(target) != (target_database, "on"):
            raise IngestError(ErrorKind.CONFIGURATION, "takeover_verify_identity")
        cursor.execute("SELECT report_json FROM sync_ops.takeover_marker WHERE marker_id=1")
        row = cursor.fetchone()
        if not row:
            raise IngestError(ErrorKind.PUBLISH_CONTRACT, "takeover_marker_missing")
        marker = row[0]
    for table in ARCHIVE_TABLES:
        count, archive_digest = 0, hashlib.sha256()
        for chunk in _archive_read(target, table, chunk_size):
            for record in chunk:
                count += 1
                archive_digest.update((sha256_hex(canonical_json(record)) + "\n").encode())
        if marker["archives"][table] != {"rows": count, "digest": archive_digest.hexdigest()}:
            raise IngestError(ErrorKind.PUBLISH_CONTRACT, "takeover_archive_fingerprint")
    with target.cursor() as cursor:
        cursor.execute("SELECT interface_name,count(*) FROM cache_raw.source_record GROUP BY 1")
        if {str(r[0]): int(r[1]) for r in cursor.fetchall()} != EXPECTED_COUNTS:
            raise IngestError(ErrorKind.PUBLISH_CONTRACT, "takeover_verify_counts")
        cursor.execute("SELECT count(*) FROM cache_raw.source_record_version")
        if cursor.fetchone()[0] != marker["history_rows"]:
            raise IngestError(ErrorKind.PUBLISH_CONTRACT, "takeover_verify_history_count")
        matched = 0
        for chunk in _archive_read(target, "cache_raw.source_record", chunk_size):
            placeholders = ",".join("(%s,%s)" for _ in chunk)
            cursor.execute(
                "SELECT interface_name,source_key_hash,payload,row_hash,schema_hash "
                "FROM cache_raw.source_record WHERE (interface_name,source_key_hash) IN ("
                + placeholders
                + ")",
                tuple(
                    v
                    for record in chunk
                    for v in (record["interface_name"], record["source_key_hash"])
                ),
            )
            actual = {(r[0], r[1]): (r[2], r[3], r[4]) for r in cursor.fetchall()}
            for record in chunk:
                digest, _key = validate_legacy_record(record)
                key = record["interface_name"], record["source_key_hash"]
                expected = record["payload"], record["row_hash"], digest
                if actual.get(key) != expected:
                    raise IngestError(ErrorKind.PUBLISH_CONTRACT, "takeover_verify_content")
                matched += 1
        # 每份旧历史都必须有映射后的同键同内容版本；不得用只比数量替代。
        history_matched = 0
        cursor.execute("SELECT legacy_batch_id,batch_id FROM sync_ops.takeover_batch_map")
        batch_map = dict(cursor.fetchall())
        for chunk in _archive_read(target, "cache_raw.source_record_version", chunk_size):
            keys = [
                (r["interface_name"], r["source_key_hash"], batch_map[r["batch_id"]]) for r in chunk
            ]
            cursor.execute(
                "SELECT interface_name,source_key_hash,batch_id,payload,row_hash,schema_hash "
                "FROM cache_raw.source_record_version "
                "WHERE (interface_name,source_key_hash,batch_id) IN ("
                + ",".join("(%s,%s,%s)" for _ in keys)
                + ")",
                tuple(v for key in keys for v in key),
            )
            actual_history = {(r[0], r[1], r[2]): (r[3], r[4], r[5]) for r in cursor.fetchall()}
            for record, history_key in zip(chunk, keys, strict=True):
                digest, _key = validate_legacy_record(record, history=True)
                if actual_history.get(history_key) != (
                    record["payload"],
                    record["row_hash"],
                    digest,
                ):
                    raise IngestError(ErrorKind.PUBLISH_CONTRACT, "takeover_verify_history_content")
                history_matched += 1
    return {
        "status": "verified",
        "raw_rows_equal": matched,
        "history_rows_equal": history_matched,
        "archives_verified": len(ARCHIVE_TABLES),
        "database_written": False,
        "contains_phi": False,
        "contains_raw_values": False,
    }
