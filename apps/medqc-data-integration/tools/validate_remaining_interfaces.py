"""剩余接口一次性显式日期验收；源数据只进独立 PG，报告只含元数据。"""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import re
import sys
from contextlib import closing, suppress
from dataclasses import asdict, replace
from datetime import date, datetime, timezone
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from medqc_ingest.adapters.cache import _DbApiSourceCursor  # noqa: E402
from medqc_ingest.control.pipeline import BoundedOdbcSource  # noqa: E402
from medqc_ingest.domain import (  # noqa: E402
    ErrorKind,
    IngestError,
    InterfaceSpec,
    KeyTracker,
    RunMode,
    build_records,
    canonical_json,
    normalize,
    project_record,
    schema_signature,
    sha256_hex,
    validate_columns,
)
from medqc_ingest.inspection import build_snapshot_records  # noqa: E402
from medqc_ingest.periop_live import safe_odbc_diagnostic, source_settings  # noqa: E402
from medqc_ingest.periop_replay import explicit_window  # noqa: E402
from medqc_ingest.repositories.postgres import (  # noqa: E402
    PostgresCdmRepository,
    PostgresIngestRepository,
    _read_cdm_contract,
)
from medqc_ingest.service import ExtractService, PublishService  # noqa: E402

DATES = ("2026-10-26", "2026-10-27", "2026-10-28")
VERSION = "remaining-explicit-validation-v1"


def require(value, location):
    if not value:
        raise IngestError(ErrorKind.CONFIGURATION, location)


def error_metadata(error):
    """不输出异常正文、SQL、参数或病人值。"""
    diagnostic = safe_odbc_diagnostic(error)
    current, visited = error, set()
    while current is not None and id(current) not in visited:
        visited.add(id(current))
        pgcode = getattr(current, "pgcode", None)
        if isinstance(pgcode, str) and re.fullmatch(r"[0-9A-Z]{5}", pgcode):
            diagnostic["sqlstate"] = pgcode
            break
        current = current.__cause__ or current.__context__
    return {
        "error_kind": error.kind if isinstance(error, IngestError) else "unexpected_error",
        "error_location": error.location
        if isinstance(error, IngestError)
        else "remaining_boundary",
        **diagnostic,
    }


def isolatable(error):
    """权限、连接、凭据、磁盘和未知故障不可被接口隔离吞掉。"""
    if not isinstance(error, IngestError):
        return False
    state = error_metadata(error)["sqlstate"]
    if error_metadata(error)["native"] == 417:
        return False
    if state and (state[:2] in {"08", "28", "53", "57", "58"} or state == "42501"):
        return False
    if error.kind == ErrorKind.SOURCE_QUERY.value:
        return (state == "HY000" and error_metadata(error)["native"] == 400) or (
            state is not None and state.startswith("42")
        )
    if error.kind in {
        ErrorKind.SCHEMA.value,
        ErrorKind.KEY.value,
        ErrorKind.PUBLISH_CONTRACT.value,
    }:
        return True
    return (
        error.kind == ErrorKind.CDM_WRITE.value and state is not None and state[:2] in {"22", "23"}
    )


class Journal:
    """先持久化进行中状态；提交不明时拒绝自动重跑。"""

    def __init__(self, path, identity):
        self.path = path
        self.events = path.with_suffix(".jsonl")
        if path.exists():
            self.document = json.loads(path.read_text(encoding="utf-8"))
            require(self.document.get("identity") == identity, "remaining_resume_identity")
        else:
            self.document = {"version": VERSION, "identity": identity, "stages": {}}
            self.save()
        if self.events.exists():
            for line in self.events.read_text(encoding="utf-8").splitlines():
                event = json.loads(line)
                self.document["stages"][event["key"]] = event["value"]

    def save(self):
        with self.path.open("x", encoding="utf-8", newline="\n") as output:
            json.dump(self.document, output, ensure_ascii=False, sort_keys=True, indent=2)
            output.write("\n")
            output.flush()
            os.fsync(output.fileno())

    def record(self, key, value):
        with self.events.open("a", encoding="utf-8", newline="\n") as output:
            output.write(json.dumps({"key": key, "value": value}, ensure_ascii=False) + "\n")
            output.flush()
            os.fsync(output.fileno())
        self.document["stages"][key] = value

    def annotate(self, key, metadata):
        self.record(key, {"status": "running", "metadata": metadata})

    def stage(self, key, action, reconcile=None, *, readonly=False):
        prior = self.document["stages"].get(key)
        if prior:
            if prior["status"] == "done":
                if not (readonly and prior["result"].get("status") == "blocked"):
                    return prior["result"]
                # 软件修复后只复核已失败的纯读闸门；已成功阶段和源失败窗口不重跑。
            elif readonly:
                pass  # 仅SELECT或纯函数阶段可安全重做，不触发源端调用或事务写入。
            elif reconcile is not None:
                result = reconcile(prior.get("metadata", {}))
                if result is not None:
                    if result.get("retry_prequery"):
                        self.record(
                            key,
                            {
                                "status": "retry_prequery_verified",
                                "proof": result,
                                "metadata": prior.get("metadata", {}),
                            },
                        )
                    else:
                        self.record(key, {"status": "done", "result": result})
                        return result
                else:
                    require(False, "remaining_resume_reconciliation_required")
            else:
                require(False, "remaining_resume_reconciliation_required")
        self.record(key, {"status": "running"})
        try:
            result = action()
        except Exception as error:
            if not isolatable(error):
                raise
            result = {"status": "blocked", **error_metadata(error)}
        self.record(key, {"status": "done", "result": result})
        return result


def restore_value(value):
    """快照回放严格逆转规范化；不把 JSON 类型标记当临床文本发布。"""
    if not isinstance(value, dict):
        return value
    kind = value.get("$type")
    if kind == "bytes":
        result = base64.b64decode(value["b64"], validate=True)
    elif kind == "decimal":
        result = Decimal(value["text"])
    elif kind == "datetime":
        result = datetime.fromisoformat(value["iso"])
    elif kind == "date":
        result = date.fromisoformat(value["iso"])
    elif kind == "float":
        result = float(value["text"])
    else:
        raise IngestError(ErrorKind.SCHEMA, "remaining_snapshot_type_not_reversible")
    if normalize(result) != value:
        raise IngestError(ErrorKind.SCHEMA, "remaining_snapshot_type_roundtrip")
    return result


class SnapshotSource:
    """只读已完整提交的本地快照，正式引擎回放时不再访问 Caché。"""

    def __init__(self, environment, snapshot):
        self.environment, self.snapshot = environment, snapshot
        self.connection, self.cursor = None, None
        self.seen = 0

    def open(self):
        self.connection = self.environment.connect("ingest", readonly=True)

    def query(self, spec, arguments):
        require(spec.name == self.snapshot["interface"], "remaining_snapshot_interface")
        require(
            tuple(arguments) == (self.snapshot["date"],) * spec.argument_count,
            "remaining_snapshot_arguments",
        )
        self.cursor = self.connection.cursor(name="remaining_snapshot_read")
        self.cursor.execute(
            "SELECT payload FROM cache_raw.source_snapshot WHERE inspection_batch_id=%s "
            "AND interface_name=%s ORDER BY ordinal",
            (self.snapshot["inspection_batch_id"], spec.name),
        )
        return self

    @property
    def columns(self):
        return tuple(self.snapshot["columns"])

    @property
    def source_types(self):
        return tuple(self.snapshot["source_types"])

    def fetchmany(self, size):
        rows = self.cursor.fetchmany(size)
        self.seen += len(rows)
        require(self.seen <= self.snapshot["rows"], "remaining_snapshot_excess")
        if not rows:
            require(self.seen == self.snapshot["rows"], "remaining_snapshot_missing")
        return [
            tuple(restore_value(payload[column]) for column in self.columns) for (payload,) in rows
        ]

    def close(self):
        if self.cursor is not None:
            self.cursor.close()
        if self.connection is not None:
            self.connection.close()


class RemainingOdbcCursor(_DbApiSourceCursor):
    def nextset(self):
        try:
            for _ in range(32):
                if not self._cursor.nextset():
                    return False
                if self._cursor.description:
                    refreshed = _DbApiSourceCursor(self._cursor)
                    self._columns = tuple(refreshed.columns)
                    self._source_types = tuple(refreshed.source_types)
                    return True
            raise IngestError(ErrorKind.SCHEMA, "remaining_nonrow_result_set_limit")
        except IngestError:
            raise
        except Exception:
            raise IngestError(ErrorKind.SOURCE_QUERY, "remaining_odbc_nextset") from None


class RemainingOdbcSource(BoundedOdbcSource):
    def query(self, spec, arguments):
        inner = super().query(spec, arguments)
        return RemainingOdbcCursor(inner._cursor)


class Operations:
    def __init__(self, environment, source_factory, chunk_size=500):
        self.environment, self.source_factory, self.chunk_size = (
            environment,
            source_factory,
            chunk_size,
        )
        self.progress = lambda _metadata: None

    def capture(self, spec, day):
        repository = PostgresIngestRepository(self.environment.settings("ingest"))
        source, cursor, batch_id, transaction = None, None, None, False
        base_metadata = {"interface": spec.name, "date": day, "source_called": False}
        self.progress(base_metadata)
        try:
            repository.connect_control()
            require(repository.acquire_lock("remaining_snapshot"), "remaining_snapshot_lock")
            batch_id = repository.start_inspection(date.fromisoformat(day), date.fromisoformat(day))
            base_metadata = dict(base_metadata, inspection_batch_id=batch_id)
            self.progress(base_metadata)
            source = self.source_factory(spec, day)
            base_metadata = dict(base_metadata, source_called=True)
            self.progress(base_metadata)
            source.open()
            cursor = source.query(spec, (day,) * spec.argument_count)
            repository.begin_snapshot()
            transaction = True
            rows, result_sets, digest = 0, [], hashlib.sha256()
            while True:
                if len(result_sets) >= 16:
                    raise IngestError(ErrorKind.SCHEMA, "remaining_result_set_limit")
                columns = validate_columns(cursor.columns, ())
                schema_hash, columns = schema_signature(columns)
                source_types = tuple(cursor.source_types)
                if len(source_types) != len(columns):
                    source_types = ("unknown",) * len(columns)
                repository.write_inspection_schema(
                    batch_id, spec.name, schema_hash, columns, source_types
                )
                before = rows
                while chunk := cursor.fetchmany(self.chunk_size):
                    # 快照标识仅批次/ordinal；内容hash绝不冒充业务键。
                    records = tuple(
                        replace(record, source_key=None, source_key_hash=None, key_complete=False)
                        for record in build_snapshot_records(
                            replace(spec, key_fields=()), columns, chunk, rows + 1
                        )
                    )
                    repository.write_snapshot(
                        batch_id,
                        spec.name,
                        date.fromisoformat(day),
                        date.fromisoformat(day),
                        schema_hash,
                        records,
                    )
                    for record in records:
                        digest.update(
                            canonical_json([schema_hash, record.ordinal, record.payload]).encode()
                        )
                        digest.update(b"\n")
                    rows += len(records)
                result_sets.append(
                    {
                        "columns": columns,
                        "source_types": source_types,
                        "schema_hash": schema_hash,
                        "rows": rows - before,
                    }
                )
                if not hasattr(cursor, "nextset") or not cursor.nextset():
                    break
            captured = {
                "status": "captured",
                "interface": spec.name,
                "date": day,
                "rows": rows,
                "schema_hash": result_sets[0]["schema_hash"],
                "columns": result_sets[0]["columns"],
                "source_types": result_sets[0]["source_types"],
                "result_sets": result_sets,
                "inspection_batch_id": batch_id,
                "complete": True,
                "snapshot_fingerprint": digest.hexdigest(),
            }
            # 提交前先fsync描述；恢复只能按此ID+结构+数量+全快照指纹确认。
            self.progress(dict(base_metadata, captured=captured))
            repository.commit_snapshot()
            transaction = False
            repository.record_inspection_run(
                batch_id,
                spec.name,
                date.fromisoformat(day),
                date.fromisoformat(day),
                "succeeded",
                rows,
                captured["schema_hash"],
                None,
                None,
            )
            repository.finish_inspection(batch_id, "succeeded")
            return captured
        except Exception as error:
            if transaction:
                repository.rollback_snapshot()
            metadata = error_metadata(error)
            self.progress(dict(base_metadata, failure=metadata, isolated=isolatable(error)))
            if batch_id is not None:
                repository.record_inspection_run(
                    batch_id,
                    spec.name,
                    date.fromisoformat(day),
                    date.fromisoformat(day),
                    "failed",
                    0,
                    None,
                    metadata["error_kind"],
                    metadata["error_location"],
                )
                repository.finish_inspection(batch_id, "completed_with_failures")
            raise
        finally:
            if cursor is not None:
                cursor.close()
            if source is not None:
                source.close()
            with suppress(Exception):
                repository.release_lock("remaining_snapshot")
            repository.close()

    def reconcile_capture(self, spec, day, metadata):
        if (metadata.get("interface"), metadata.get("date")) != (spec.name, day):
            return None
        failure = metadata.get("failure", {})
        if (
            metadata.get("source_called") is False
            and "inspection_batch_id" not in metadata
            and failure.get("error_kind") == ErrorKind.CONFIGURATION.value
            and failure.get("error_location")
            in {"psycopg_not_installed", "postgres_driver_invalid"}
        ):
            return {
                "retry_prequery": True,
                "proof": "local_driver_failed_before_database_or_source",
            }
        with (
            closing(self.environment.connect("ingest", readonly=True)) as connection,
            connection.cursor() as cursor,
        ):
            cursor.execute(
                "SELECT r.status,r.row_count,r.schema_hash,b.status "
                "FROM sync_ops.inspection_run r JOIN sync_ops.inspection_batch b "
                "USING(inspection_batch_id) WHERE r.inspection_batch_id=%s "
                "AND r.interface_name=%s AND r.window_start=%s AND r.window_end=%s",
                (metadata.get("inspection_batch_id"), spec.name, day, day),
            )
            audit = cursor.fetchall()
            if len(audit) != 1:
                return None
            status, count, schema_hash, batch_status = audit[0]
            if status == "failed" and batch_status == "completed_with_failures":
                if metadata.get("isolated") and metadata.get("failure"):
                    return {"status": "blocked", **metadata["failure"]}
                return None
            expected = metadata.get("captured")
            if not (
                expected
                and status == batch_status == "succeeded"
                and count == expected["rows"]
                and schema_hash == expected["schema_hash"]
            ):
                return None
            cursor.execute(
                "SELECT schema_hash,column_names,source_types FROM sync_ops.inspection_schema "
                "WHERE inspection_batch_id=%s AND interface_name=%s",
                (metadata["inspection_batch_id"], spec.name),
            )
            actual = {digest: (columns, types) for digest, columns, types in cursor.fetchall()}
            for result_set in expected["result_sets"]:
                if actual.get(result_set["schema_hash"]) != (
                    result_set["columns"],
                    result_set["source_types"],
                ):
                    return None
            digest, seen = hashlib.sha256(), 0
            cursor.execute(
                "SELECT schema_hash,ordinal,payload FROM cache_raw.source_snapshot "
                "WHERE inspection_batch_id=%s AND interface_name=%s ORDER BY ordinal",
                (metadata["inspection_batch_id"], spec.name),
            )
            while rows := cursor.fetchmany(self.chunk_size):
                for source_hash, ordinal, payload in rows:
                    digest.update(canonical_json([source_hash, ordinal, payload]).encode())
                    digest.update(b"\n")
                    seen += 1
            if seen != count or digest.hexdigest() != expected["snapshot_fingerprint"]:
                return None
        return expected

    def preflight(self, spec):
        target = spec.publish
        require(target is not None, "remaining_preflight_target")
        with (
            closing(self.environment.connect("cdm", readonly=True)) as connection,
            connection.cursor() as cursor,
        ):
            columns, keys = _read_cdm_contract(connection, target)
            cursor.execute(
                "SELECT column_name,character_maximum_length "
                "FROM information_schema.columns WHERE table_schema=%s AND table_name=%s "
                "AND character_maximum_length IS NOT NULL",
                (target.schema, target.table),
            )
            maximums = dict(cursor.fetchall())
        types = {
            "text": {"text", "character varying", "character"},
            "date": {"date"},
            "datetime": {"timestamp without time zone"},
            "timestamptz": {"timestamp with time zone"},
        }
        missing = [mapping.target for mapping in target.mappings if mapping.target not in columns]
        incompatible = [
            mapping.target
            for mapping in target.mappings
            if mapping.target in columns
            and columns[mapping.target] not in types[mapping.target_type]
        ]
        ok = tuple(keys) == target.primary_key and not missing and not incompatible
        return {
            "status": "verified" if ok else "blocked",
            "target_catalog_verified": ok,
            "actual_primary_key": keys,
            "missing_target_columns": missing,
            "incompatible_target_columns": incompatible,
            "maximum_lengths": maximums,
        }

    def validate_keys(self, spec, snapshots, metadata=None):
        target_sources = {}
        for snapshot in snapshots:
            if len(snapshot.get("result_sets", [None])) != 1:
                raise IngestError(ErrorKind.SCHEMA, "remaining_multiple_result_sets")
            if tuple(snapshot["columns"]) != spec.source_columns:
                raise IngestError(ErrorKind.SCHEMA, "remaining_frozen_schema_changed")
            tracker = KeyTracker()
            source = SnapshotSource(self.environment, snapshot)
            try:
                source.open()
                cursor = source.query(spec, (snapshot["date"],) * spec.argument_count)
                while rows := cursor.fetchmany(self.chunk_size):
                    records = build_records(spec.source_columns, rows, spec.key_fields)
                    tracker.extend(record.source_key_hash for record in records)
                    for record in records:
                        projected = project_record(
                            spec, record.payload, datetime(2026, 10, 29, tzinfo=timezone.utc)
                        )
                        for field, maximum in (metadata or {}).get("maximum_lengths", {}).items():
                            value = projected.get(field)
                            if isinstance(value, str) and len(value) > maximum:
                                raise IngestError(
                                    ErrorKind.PUBLISH_CONTRACT, "target_text_too_long"
                                )
                        target = spec.publish
                        require(target is not None, "remaining_publish_contract")
                        target_key = sha256_hex(
                            canonical_json({k: projected[k] for k in target.primary_key})
                        )
                        previous = target_sources.setdefault(target_key, record.source_key_hash)
                        if previous != record.source_key_hash:
                            raise IngestError(ErrorKind.KEY, "remaining_target_key_collision")
            finally:
                source.close()
        return {"status": "verified", "target_unique_keys": len(target_sources)}

    def promote(self, spec, snapshot):
        repository = PostgresIngestRepository(self.environment.settings("ingest"))
        result = ExtractService(
            lambda: SnapshotSource(self.environment, snapshot), repository, self.chunk_size
        ).run(spec, snapshot["date"], RunMode.REPLAY, *explicit_window(snapshot["date"]))
        require(result.checkpoint_state == "held", "remaining_checkpoint_not_held")
        return {"status": "promoted", **asdict(result)}

    def reconcile_engine(self, spec, phase, snapshot=None):
        table, key = (
            ("sync_ops.sync_batch", "batch_id")
            if phase == "raw"
            else ("sync_ops.publish_batch", "publish_batch_id")
        )
        fields = (
            "rows_fetched,rows_inserted,rows_updated,rows_unchanged,checkpoint_state"
            if phase == "raw"
            else "schema_hash,rows_selected,rows_written"
        )
        with (
            closing(self.environment.connect("ingest", readonly=True)) as connection,
            connection.cursor() as cursor,
        ):
            cursor.execute(
                f"SELECT {key},status,error_kind,error_location,{fields} FROM {table} "
                "WHERE interface_name=%s AND evidence_version=%s",
                (spec.name, spec.evidence_version),
            )
            audit = cursor.fetchall()
            if len(audit) != 1:
                return None
            row = audit[0]
            if row[1] == "failed" and row[2] in {
                ErrorKind.SCHEMA.value,
                ErrorKind.KEY.value,
                ErrorKind.PUBLISH_CONTRACT.value,
            }:
                return {"status": "blocked", "error_kind": row[2], "error_location": row[3]}
            if row[1] != "succeeded":
                return None
            if phase == "raw":
                fetched, inserted, updated, unchanged, checkpoint = row[4:]
                if not (
                    snapshot
                    and fetched == snapshot["rows"]
                    and checkpoint == "held"
                    and inserted + updated + unchanged == fetched
                ):
                    return None
                source = SnapshotSource(self.environment, snapshot)
                try:
                    source.open()
                    source.query(spec, (snapshot["date"],) * spec.argument_count)
                    while rows := source.fetchmany(self.chunk_size):
                        records = build_records(spec.source_columns, rows, spec.key_fields)
                        for record in records:
                            cursor.execute(
                                "SELECT row_hash,schema_hash,last_batch_id FROM "
                                "cache_raw.source_record WHERE interface_name=%s "
                                "AND source_key_hash=%s",
                                (spec.name, record.source_key_hash),
                            )
                            if cursor.fetchall() != [
                                (record.row_hash, snapshot["schema_hash"], row[0])
                            ]:
                                return None
                finally:
                    source.close()
                return {
                    "status": "promoted",
                    "batch_id": row[0],
                    "schema_hash": snapshot["schema_hash"],
                    "checkpoint_state": "held",
                    "counts": {
                        "fetched": fetched,
                        "inserted": inserted,
                        "updated": updated,
                        "unchanged": unchanged,
                    },
                }
        verified = self.verify(spec)
        if verified["rows"] != row[5]:
            return None
        return {
            "status": "published",
            "publish_batch_id": row[0],
            "schema_hash": row[4],
            "selected": row[5],
            "written": row[6],
        }

    def publish(self, spec, number):
        result = PublishService(
            PostgresIngestRepository(self.environment.settings("ingest")),
            PostgresCdmRepository(self.environment.settings("cdm")),
            self.chunk_size,
        ).run(spec)
        if number == 2 and result.written != 0:
            raise IngestError(ErrorKind.PUBLISH_CONTRACT, "remaining_second_publish_changed")
        return {"status": "published", **asdict(result)}

    def verify(self, spec):
        from psycopg2 import sql

        target = spec.publish
        require(target is not None, "remaining_verify_target")
        repository = PostgresIngestRepository(self.environment.settings("ingest"))
        cursor = repository.open_verified_raw(spec.name, target.source_key_fields)
        count = 0
        try:
            with (
                closing(self.environment.connect("cdm", readonly=True)) as connection,
                connection.cursor() as output,
            ):
                while rows := cursor.fetchmany(self.chunk_size):
                    for record in rows:
                        expected = project_record(spec, record.payload, record.completed_at)
                        output.execute(
                            sql.SQL("SELECT {} FROM {} WHERE {}").format(
                                sql.SQL(",").join(map(sql.Identifier, target.target_columns)),
                                sql.Identifier(target.schema, target.table),
                                sql.SQL(" AND ").join(
                                    sql.SQL("{}=%s").format(sql.Identifier(k))
                                    for k in target.primary_key
                                ),
                            ),
                            tuple(expected[k] for k in target.primary_key),
                        )
                        actual = output.fetchall()
                        if (
                            len(actual) != 1
                            or tuple(expected[k] for k in target.target_columns) != actual[0]
                        ):
                            raise IngestError(
                                ErrorKind.PUBLISH_CONTRACT, "remaining_field_equality"
                            )
                        count += 1
                output.execute(
                    sql.SQL("SELECT count(*) FROM {}").format(
                        sql.Identifier(target.schema, target.table)
                    )
                )
                if output.fetchone()[0] != count:
                    raise IngestError(ErrorKind.PUBLISH_CONTRACT, "remaining_target_row_count")
        finally:
            cursor.close()
            repository.close()
        return {"status": "verified", "rows": count, "all_fields_equal": True}


def probe_spec(item):
    name = item["interface"]
    require(re.fullmatch(r"web\.[a-z][a-z0-9_]*", name), "remaining_probe_procedure")
    count = item["argument_count"]
    require(count in (1, 2), "remaining_probe_arguments")
    return InterfaceSpec(name, name, count, (), None, (), VERSION, None)


def run(args, *, environment=None, operations=None, source_factory=None, profile=None):
    # 客户离线依赖固定为psycopg2；不能继承通用核心的psycopg3默认值。
    os.environ["MEDQC_PG_DRIVER"] = "psycopg2"
    if profile is None:
        from remaining_environment import load_combined_profile

        profile = load_combined_profile(args.contract)
    contract, specs = profile
    items = contract["interfaces"]
    expected = 42 if contract.get("scope") == "remaining25_periop17" else 25
    require(
        len(items) == expected and len({item["interface"] for item in items}) == expected,
        "remaining_exact_scope",
    )
    require(not os.getenv("PGPASSWORD"), "remaining_pgpassword_forbidden")
    synthetic = getattr(args, "synthetic", False)
    require(
        not (source_factory is not None or operations is not None) or synthetic,
        "remaining_source_override_guard",
    )
    require(
        not synthetic or source_factory is not None or operations is not None,
        "remaining_synthetic_source_required",
    )
    timeout = getattr(args, "statement_timeout_seconds", 120)
    require(type(timeout) is int and 1 <= timeout <= 3600, "remaining_statement_timeout")
    if environment is None:
        from remaining_environment import Environment

        environment = Environment(args, contract, specs)
    identity = {
        "databases": environment.databases,
        "dates": list(DATES),
        "contract_sha256": sha256_hex(canonical_json(contract)),
    }
    progress = args.output / "reports/remaining-progress.json"
    # 恢复身份先核验，再允许环境准备器做任何动作。
    journal = Journal(progress, identity) if progress.exists() else None
    environment.prepare()
    journal = journal or Journal(progress, identity)
    if operations is None:
        config = source_settings(args.source_config)
        operations = Operations(
            environment,
            source_factory or (lambda _spec, _day: RemainingOdbcSource(config, timeout)),
        )

    def capture_stage(spec, day):
        key = f"snapshot:{spec.name}:{day}"

        def capture():
            operations.progress = lambda metadata: journal.annotate(key, metadata)
            return operations.capture(spec, day)

        reconcile = getattr(operations, "reconcile_capture", None)
        return journal.stage(
            key, capture, (lambda metadata: reconcile(spec, day, metadata)) if reconcile else None
        )

    def stage_spec(spec, key):
        return replace(
            spec,
            evidence_version=VERSION + ":" + sha256_hex(canonical_json(identity))[:16] + ":" + key,
        )

    def reconcile_engine(spec, phase, snapshot=None):
        callback = getattr(operations, "reconcile_engine", None)
        return (lambda _metadata: callback(spec, phase, snapshot)) if callback else None

    outcomes = []
    for item in items:
        name = item["interface"]
        spec = specs.get(name)
        reader_spec = spec or probe_spec(item)
        snapshots, blocked = [], []
        for day in DATES:
            captured = capture_stage(reader_spec, day)
            if captured["status"] == "captured":
                snapshots.append(captured)
            else:
                blocked.append({"date": day, **captured})
        rows = sum(snapshot["rows"] for snapshot in snapshots)
        if snapshots and not rows and not blocked:
            # 仅全三日零样本接口扩一次短窗；首个非空日立即停止，绝不扩成历史回补。
            for day_number in range(19, 26):
                day = f"2026-10-{day_number:02d}"
                captured = capture_stage(reader_spec, day)
                if captured["status"] == "captured":
                    snapshots.append(captured)
                    rows += captured["rows"]
                    if captured["rows"]:
                        break
                else:
                    blocked.append({"date": day, **captured})
        outcome = {
            "interface": name,
            "snapshot_rows": rows,
            "failed_windows": blocked,
            "source_complete": not blocked,
            "date_semantics": "unverified",
        }
        catalog = (
            journal.stage(
                f"catalog:{name}", lambda spec=spec: operations.preflight(spec), readonly=True
            )
            if spec is not None
            else None
        )
        outcome["target_catalog"] = catalog
        if spec is None:
            outcome["status"] = (
                "snapshot_only_no_publish_contract" if snapshots else "source_blocked"
            )
        elif catalog["status"] == "blocked":
            outcome["status"] = "target_catalog_blocked"
        elif not rows:
            outcome["status"] = "schema_verified_no_sample" if snapshots else "source_blocked"
            outcome["schema_matches"] = all(
                tuple(s["columns"]) == spec.source_columns for s in snapshots
            )
            if not outcome["schema_matches"]:
                outcome["status"] = "snapshot_only_contract_blocked"
        else:
            key_check = journal.stage(
                f"key:{name}",
                lambda spec=spec, snapshots=snapshots, catalog=catalog: operations.validate_keys(
                    spec, snapshots, catalog
                ),
                readonly=True,
            )
            if key_check["status"] == "blocked":
                outcome.update(status="snapshot_only_contract_blocked", key_check=key_check)
            else:
                good = True
                for snapshot in snapshots:
                    key = f"raw:{name}:{snapshot['date']}"
                    correlated = stage_spec(spec, key)
                    promoted = journal.stage(
                        key,
                        lambda snapshot=snapshot, spec=correlated: operations.promote(
                            spec, snapshot
                        ),
                        reconcile_engine(correlated, "raw", snapshot),
                    )
                    if promoted["status"] == "blocked":
                        outcome.update(status="raw_promotion_blocked", raw_failure=promoted)
                        good = False
                        break
                if good:
                    rounds = []
                    for number in (1, 2):
                        key = f"publish:{name}:{number}"
                        correlated = stage_spec(spec, key)
                        published = journal.stage(
                            key,
                            lambda number=number, spec=correlated: operations.publish(spec, number),
                            reconcile_engine(correlated, "publish"),
                        )
                        rounds.append(published)
                        if published["status"] == "blocked":
                            good = False
                            break
                    outcome["publish_rounds"] = rounds
                    if good:
                        verified = journal.stage(
                            f"verify:{name}",
                            lambda spec=spec: operations.verify(spec),
                            readonly=True,
                        )
                        outcome.update(
                            status="accepted"
                            if verified["status"] == "verified"
                            else "field_verification_blocked",
                            equality=verified,
                        )
                    else:
                        outcome["status"] = "projection_blocked"
        outcomes.append(outcome)
    backup_revision = getattr(environment, "backup_revision", None)
    backup_key = "backup_restore:" + backup_revision() if backup_revision else "backup_restore"
    restored = journal.stage(
        backup_key, environment.backup_restore, lambda _metadata: environment.backup_restore()
    )
    report = {
        "version": VERSION,
        "status": "REMAINING_VALIDATION_COMPLETE_WITH_COVERAGE",
        "required_alembic_revision": contract.get("required_alembic_revision"),
        "interfaces": outcomes,
        "backup_restore": restored,
        "explicit_dates": list(DATES),
        "automatic_incremental": False,
        "scheduled_task_created": False,
        "old_databases_accessed": False,
        "business_database_accessed": False,
        "cache_accessed": not getattr(args, "synthetic", False),
        "synthetic": getattr(args, "synthetic", False),
        "postgres_major": getattr(args, "pg_major", None),
        "production_enabled": False,
        "contains_phi": False,
        "contains_raw_values": False,
        "contains_keys": False,
    }
    path = args.output / "reports/remaining-acceptance.json"
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return report


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--contract", type=Path, default=ROOT / "contracts/remaining-acceptance-contracts.json"
    )
    for name in (
        "output",
        "source-config",
        "admin-passfile",
        "runtime-passfile",
        "pg-bin",
        "backend",
    ):
        parser.add_argument("--" + name, required=True, type=Path)
    parser.add_argument("--suffix", required=True)
    parser.add_argument("--port", type=int, default=5432)
    parser.add_argument("--pg-major", type=int, default=16)
    parser.add_argument("--admin-user", default="postgres")
    parser.add_argument("--statement-timeout-seconds", type=int, default=120)
    args = parser.parse_args(argv)
    args.synthetic = False
    try:
        run(args)
    except Exception as error:
        print(json.dumps({"status": "STOPPED", **error_metadata(error)}))
        return 1
    print("REMAINING_VALIDATION_COMPLETE_WITH_COVERAGE")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
