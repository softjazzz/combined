"""只对独立接管库执行真实事务验收；不连接 Caché，也不构造规则输入。"""

from __future__ import annotations

import hashlib
from collections.abc import Sequence
from typing import Any

from medqc_ingest.config import PostgresSettings
from medqc_ingest.domain import (
    INTERFACE_REGISTRY,
    ErrorKind,
    IngestError,
    RunMode,
    canonical_json,
    normalize,
    project_record,
    resolve_interface,
)
from medqc_ingest.repositories.postgres import (
    PostgresCdmRepository,
    PostgresIngestRepository,
    _connect,
    _ident,
)
from medqc_ingest.service import ExtractService, PublishService
from medqc_ingest.takeover import legacy_window, validate_target_database

INGEST_FINGERPRINT_TABLES = (
    "cache_raw.source_record",
    "cache_raw.source_record_version",
    "sync_ops.source_schema",
    "sync_ops.sync_checkpoint",
    "sync_ops.sync_batch",
    "sync_ops.publish_batch",
    "sync_ops.publish_lineage",
    "takeover_archive.source_catalog",
    "takeover_archive.source_row",
    "sync_ops.takeover_marker",
    "sync_ops.takeover_batch_map",
)


def fingerprints(settings: PostgresSettings, kind: str = "ingest") -> dict[str, Any]:
    if kind not in {"ingest", "cdm"}:
        raise IngestError(ErrorKind.CONFIGURATION, "fingerprint_kind")
    # restore 名称只用于恢复演练，不成为抽取/发布目的地。
    role = "restore" if settings.database.startswith("medqc_restore_") else kind
    validate_target_database(settings.database, role)
    tables = (
        INGEST_FINGERPRINT_TABLES
        if kind == "ingest"
        else tuple(str(spec.publish_target) for spec in INTERFACE_REGISTRY.values())
    )
    connection = _connect(settings, ErrorKind.INGEST_CONNECT, "fingerprint_connect", readonly=True)
    try:
        with connection.cursor() as cursor:
            cursor.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY")
            cursor.execute("SET LOCAL timezone='Asia/Shanghai'")
            cursor.execute("SELECT current_database()")
            if cursor.fetchone()[0] != settings.database:
                raise IngestError(ErrorKind.CONFIGURATION, "fingerprint_database")
        result = {}
        for table in tables:
            digest, count = hashlib.sha256(), 0
            qualified = ".".join(_ident(part) for part in table.split("."))
            with connection.cursor(name="medqc_fingerprint") as cursor:
                # 指纹采用完整行文本确定顺序，不依赖物理扫描顺序。
                cursor.execute(
                    f'SELECT to_jsonb(t) FROM {qualified} t ORDER BY to_jsonb(t)::text COLLATE "C"'
                )
                while rows := cursor.fetchmany(1000):
                    for row in rows:
                        digest.update((canonical_json(row[0]) + "\n").encode())
                        count += 1
            result[table] = {"rows": count, "sha256": digest.hexdigest()}
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT schemaname,sequencename,start_value,min_value,max_value,increment_by,"
                "cycle,cache_size,last_value FROM pg_sequences WHERE schemaname=ANY(%s) "
                'ORDER BY schemaname COLLATE "C",sequencename COLLATE "C"',
                (["cache_raw", "sync_ops"] if kind == "ingest" else ["cdm"],),
            )
            sequences = cursor.fetchall()
        result["__sequences__"] = {
            "rows": len(sequences),
            "sha256": hashlib.sha256(canonical_json(sequences).encode()).hexdigest(),
        }
        return result
    finally:
        connection.close()


class _RowsCursor:
    def __init__(self, payloads: Sequence[dict[str, Any]]) -> None:
        self.columns = resolve_interface("web.mr").source_columns
        self.source_types = tuple("stored_snapshot" for _ in self.columns)
        self.rows = [tuple(payload[column] for column in self.columns) for payload in payloads]
        for payload, row in zip(payloads, self.rows, strict=True):
            if {column: normalize(row[i]) for i, column in enumerate(self.columns)} != payload:
                raise IngestError(ErrorKind.PUBLISH_CONTRACT, "probe_source_type_not_reversible")

    def fetchmany(self, size: int) -> Any:
        rows, self.rows = self.rows[:size], self.rows[size:]
        return rows

    def close(self) -> None:
        pass


class _RowsSource:
    def __init__(self, payloads: Sequence[dict[str, Any]]) -> None:
        self.cursor = _RowsCursor(payloads)

    def open(self) -> None:
        pass

    def query(self, spec: Any, arguments: Sequence[str]) -> _RowsCursor:
        if spec.name != "web.mr" or tuple(arguments) != ("2026-10-28",):
            raise IngestError(ErrorKind.CONFIGURATION, "probe_source_scope")
        return self.cursor

    def close(self) -> None:
        pass


class _FailBeforeCommit(PostgresIngestRepository):
    def commit_data(self) -> None:
        # 已执行真实 schema/raw/version/checkpoint SQL 后主动失败，交给正式编排回滚。
        raise IngestError(ErrorKind.INGEST_WRITE, "deployment_injected_before_commit")


def rollback_and_recovery(settings: PostgresSettings) -> dict[str, Any]:
    validate_target_database(settings.database)
    before = fingerprints(settings)
    if before["sync_ops.sync_checkpoint"]["rows"]:
        raise IngestError(ErrorKind.PUBLISH_CONTRACT, "probe_requires_no_checkpoint")
    spec = resolve_interface("web.mr")
    payloads = []
    for index in range(2):
        payload = dict.fromkeys(spec.source_columns)
        payload.update(
            institute_id="deployment-probe",
            patient_id="deployment-probe",
            visit_id=f"rollback-{index}",
            record_content="deployment transaction probe",
        )
        payloads.append(payload)
    window = legacy_window("2026-10-28", "2026-10-28")
    try:
        ExtractService(lambda: _RowsSource(payloads), _FailBeforeCommit(settings), 1).run(
            spec, "2026-10-28", RunMode.INCREMENTAL, *window
        )
    except IngestError as exc:
        if exc.location != "deployment_injected_before_commit":
            raise
    else:
        raise IngestError(ErrorKind.PUBLISH_CONTRACT, "probe_failure_not_injected")
    after = fingerprints(settings)
    if after["sync_ops.sync_batch"]["rows"] != before["sync_ops.sync_batch"]["rows"] + 1:
        raise IngestError(ErrorKind.PUBLISH_CONTRACT, "probe_failure_audit_count")
    for table in (
        "cache_raw.source_record",
        "cache_raw.source_record_version",
        "sync_ops.source_schema",
        "sync_ops.sync_checkpoint",
    ):
        if before[table] != after[table]:
            raise IngestError(ErrorKind.PUBLISH_CONTRACT, "probe_transaction_not_rolled_back")
    connection = _connect(settings, ErrorKind.INGEST_CONNECT, "probe_recovery_read", readonly=True)
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT status,error_location FROM sync_ops.sync_batch "
                "ORDER BY batch_id DESC LIMIT 1"
            )
            if cursor.fetchone() != ("failed", "deployment_injected_before_commit"):
                raise IngestError(ErrorKind.PUBLISH_CONTRACT, "probe_failure_audit_missing")
            cursor.execute(
                "SELECT payload FROM cache_raw.source_record WHERE interface_name='web.mr' "
                "AND source_window_start=%s ORDER BY source_key_hash",
                (window[0],),
            )
            original_payloads = [row[0] for row in cursor.fetchall()]
    finally:
        connection.close()
    if not original_payloads:
        raise IngestError(ErrorKind.PUBLISH_CONTRACT, "probe_recovery_source_missing")
    recovered = ExtractService(
        lambda: _RowsSource(original_payloads),
        PostgresIngestRepository(settings),
        1000,
    ).run(spec, "2026-10-28", RunMode.REPLAY, *window)
    if (
        recovered.counts["inserted"]
        or recovered.counts["updated"]
        or recovered.counts["unchanged"] != len(original_payloads)
    ):
        raise IngestError(ErrorKind.PUBLISH_CONTRACT, "probe_recovery_changed_content")
    return {
        "rollback": "verified",
        "failure_audit": "verified",
        "recovery": "succeeded",
        "recovery_unchanged_rows": len(original_payloads),
        "checkpoint_advanced": False,
    }


def publish_twice(ingest: PostgresSettings, cdm: PostgresSettings) -> list[dict[str, Any]]:
    validate_target_database(ingest.database)
    validate_target_database(cdm.database, "cdm")
    result = []
    for round_no in (1, 2):
        for spec in INTERFACE_REGISTRY.values():
            published = PublishService(
                PostgresIngestRepository(ingest),
                PostgresCdmRepository(cdm),
                1000,
            ).run(spec)
            if round_no == 2 and published.written:
                raise IngestError(ErrorKind.PUBLISH_CONTRACT, "publish_second_round_changed")
            result.append(
                {
                    "round": round_no,
                    "interface": spec.name,
                    "selected": published.selected,
                    "changed": published.written,
                }
            )
    return result


def verify_published(ingest: PostgresSettings, cdm: PostgresSettings) -> list[dict[str, Any]]:
    validate_target_database(ingest.database)
    validate_target_database(cdm.database, "cdm")
    source = _connect(ingest, ErrorKind.INGEST_CONNECT, "verify_ingest", readonly=True)
    target = None
    try:
        target = _connect(cdm, ErrorKind.CDM_CONNECT, "verify_cdm", readonly=True)
        for connection in (source, target):
            with connection.cursor() as cursor:
                cursor.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY")
                cursor.execute("SET LOCAL timezone='Asia/Shanghai'")
        result = []
        for spec in INTERFACE_REGISTRY.values():
            publish = spec.publish
            assert publish is not None
            count = equal = 0
            table = f"{_ident(publish.schema)}.{_ident(publish.table)}"
            columns = ",".join(_ident(column) for column in publish.target_columns)
            key_columns = ",".join(_ident(column) for column in publish.primary_key)
            with source.cursor(name="medqc_verify_publish") as raw, target.cursor() as actual:
                raw.execute(
                    "SELECT payload,local_sync_completed_at FROM cache_raw.source_record "
                    "WHERE interface_name=%s ORDER BY source_key_hash",
                    (spec.name,),
                )
                actual.execute(f"SELECT count(*) FROM {table}")
                target_count = int(actual.fetchone()[0])
                while rows := raw.fetchmany(1000):
                    projected = [project_record(spec, row[0], row[1]) for row in rows]
                    keys = [
                        tuple(row[column] for column in publish.primary_key) for row in projected
                    ]
                    placeholder = "(" + ",".join("%s" for _ in publish.primary_key) + ")"
                    actual.execute(
                        f"SELECT {columns} FROM {table} WHERE ({key_columns}) IN ("
                        + ",".join(placeholder for _ in keys)
                        + ")",
                        tuple(v for key in keys for v in key),
                    )
                    found = {}
                    for values in actual.fetchall():
                        row = dict(zip(publish.target_columns, values, strict=True))
                        found[tuple(row[column] for column in publish.primary_key)] = row
                    count += len(rows)
                    equal += sum(
                        found.get(key) == row for key, row in zip(keys, projected, strict=True)
                    )
            if count != equal or count != target_count or count == 0:
                raise IngestError(ErrorKind.PUBLISH_CONTRACT, "published_field_mismatch")
            result.append({"interface": spec.name, "rows": count, "all_fields_equal": equal})
        return result
    finally:
        source.close()
        if target is not None:
            target.close()
