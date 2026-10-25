"""正式双源写入：源端只读；本地先备份、单事务补空/新增、冲突留档，无DDL/DELETE。"""

from contextlib import ExitStack
from datetime import date, datetime, timezone
from decimal import Decimal
import base64
import hashlib
import json
import os
from pathlib import Path
from uuid import UUID, uuid4

import psycopg2
from psycopg2 import sql
from psycopg2.extras import Json, RealDictCursor

from . import dual_source_sync as policy
from .dual_source_write_policy import build_write_batch


MAX_ROWS = 100000


class DualSourceWriteError(RuntimeError):
    def __init__(self, code, *, report_path="", data_committed=False):
        super().__init__(code)
        self.code, self.report_path, self.data_committed = code, report_path, data_committed


def encoded(value):
    def default(item):
        if isinstance(item, (date, datetime)):
            return item.isoformat()
        if isinstance(item, (Decimal, UUID)):
            return str(item)
        if isinstance(item, (bytes, bytearray, memoryview)):
            return {"$base64": base64.b64encode(bytes(item)).decode("ascii")}
        raise TypeError("unsupported_backup_type")
    return (json.dumps(value, ensure_ascii=False, default=default, allow_nan=False) + "\n").encode("utf-8")


def _connect(dsn, *, readonly, factory):
    conn = factory(dsn, connect_timeout=10)
    try:
        conn.set_session(readonly=readonly, isolation_level="REPEATABLE READ" if readonly else "SERIALIZABLE")
        with conn.cursor() as cur:
            cur.execute("SET LOCAL statement_timeout='60s'")
            cur.execute("SET LOCAL lock_timeout='5s'")
            cur.execute("SHOW transaction_read_only")
            if (cur.fetchone()[0] == "on") != readonly:
                raise DualSourceWriteError("transaction_mode_mismatch")
        return conn
    except BaseException:
        conn.close()
        raise


def table_meta(conn, schema, table):
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("SELECT column_name,data_type,character_maximum_length,is_nullable,column_default,"
                    "is_identity,is_generated,numeric_precision,numeric_scale FROM information_schema.columns "
                    "WHERE table_schema=%s AND table_name=%s ORDER BY ordinal_position", (schema, table))
        columns = {row["column_name"]: dict(row) for row in cur.fetchall()}
        cur.execute("SELECT a.attname FROM pg_index i JOIN pg_class c ON c.oid=i.indrelid "
                    "JOIN pg_namespace n ON n.oid=c.relnamespace "
                    "JOIN LATERAL unnest(i.indkey) WITH ORDINALITY k(attnum,ord) ON true "
                    "JOIN pg_attribute a ON a.attrelid=c.oid AND a.attnum=k.attnum "
                    "WHERE n.nspname=%s AND c.relname=%s AND i.indisprimary AND k.ord<=i.indnkeyatts ORDER BY k.ord", (schema, table))
        keys = [row["attname"] for row in cur.fetchall()]
        cur.execute("SELECT c.relkind, EXISTS(SELECT 1 FROM pg_trigger t WHERE t.tgrelid=c.oid "
                    "AND NOT t.tgisinternal AND t.tgenabled<>'D') AS custom_trigger "
                    "FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace "
                    "WHERE n.nspname=%s AND c.relname=%s", (schema, table))
        relation = cur.fetchone()
    if not columns or not keys or not set(policy.IDENTITY_FIELDS).issubset(columns):
        raise DualSourceWriteError("target_schema_or_primary_key_missing")
    if relation is None or relation["relkind"] != "r" or relation["custom_trigger"]:
        raise DualSourceWriteError("target_relation_or_trigger_requires_review")
    return {"columns": columns, "primary_keys": keys}


def read_rows(conn, schema, table, cases, *, local=False, lock=False):
    scope = []
    params = []
    for case in cases:
        keys = policy.IDENTITY_FIELDS if local else ("patient_id", "visit_id")
        scope.append(sql.SQL("(" + " AND ".join("{}=%s" for _ in keys) + ")").format(*(sql.Identifier(k) for k in keys)))
        params.extend(case[k] for k in keys)
    statement = sql.SQL("SELECT * FROM {}.{} WHERE {} LIMIT %s{}").format(
        sql.Identifier(schema), sql.Identifier(table), sql.SQL(" OR ").join(scope),
        sql.SQL(" FOR UPDATE" if lock else ""),
    )
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(statement, [*params, MAX_ROWS + 1])
        rows = [dict(row) for row in cur.fetchall()]
    if len(rows) > MAX_ROWS:
        raise DualSourceWriteError("source_or_target_row_limit_exceeded")
    return rows


def related_rows(conn, cases):
    """同时备份将被后处理更新的病例索引和Bundle，不依赖旧应用初始化。"""
    with conn.cursor() as cur:
        cur.execute("SELECT table_schema,table_name FROM information_schema.columns "
                    "WHERE table_schema IN ('public','qc') AND "
                    "(table_name LIKE '%%bundle%%' OR table_name='visit_index') "
                    "AND column_name IN ('institute_id','patient_id','visit_id') "
                    "GROUP BY table_schema,table_name HAVING count(DISTINCT column_name)=3 "
                    "ORDER BY table_schema,table_name")
        tables = cur.fetchall()
    return {schema + "." + table: read_rows(conn, schema, table, cases, local=True) for schema, table in tables}


def save_backup(path, *, cases, metadata, originals, related=None):
    payload = encoded({"format": "medqc_dual_source_scope_backup_v1", "cases": cases,
                       "metadata": metadata, "rows": originals, "related_rows": related or {}})
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("xb") as stream:
        stream.write(payload)
        stream.flush()
        os.fsync(stream.fileno())
    restored = path.read_bytes()
    if restored != payload:
        raise DualSourceWriteError("backup_verification_failed")
    return hashlib.sha256(payload).hexdigest()


def _sql_value(value, meta):
    return Json(value, dumps=lambda obj: json.dumps(obj, ensure_ascii=False)) if meta["data_type"] in {"json", "jsonb"} else value


def apply_operations(conn, schema, operations, metadata):
    with conn.cursor() as cur:
        for operation in operations:
            table, values = operation["table"], operation["values"]
            fields, pks = tuple(values), operation["primary_keys"]
            params = [_sql_value(values[f], metadata[table]["columns"][f]) for f in fields]
            if operation["before"] is None:
                query = sql.SQL("INSERT INTO {}.{} ({}) VALUES ({}) ON CONFLICT DO NOTHING").format(
                    sql.Identifier(schema), sql.Identifier(table), sql.SQL(",").join(map(sql.Identifier, fields)),
                    sql.SQL(",").join(sql.Placeholder() for _ in fields))
            else:
                guards = tuple(dict.fromkeys((*pks, *policy.IDENTITY_FIELDS, *fields)))
                query = sql.SQL("UPDATE {}.{} SET {} WHERE {}").format(
                    sql.Identifier(schema), sql.Identifier(table),
                    sql.SQL(",").join(sql.SQL("{}=%s").format(sql.Identifier(f)) for f in fields),
                    sql.SQL(" AND ").join(sql.SQL("{} IS NOT DISTINCT FROM %s").format(sql.Identifier(f)) for f in guards))
                params.extend(_sql_value(operation["before"].get(f), metadata[table]["columns"][f]) for f in guards)
            cur.execute(query, params)
            if cur.rowcount != 1:
                raise DualSourceWriteError("concurrent_target_change")


def verify_rows(original, actual, operations, primary_keys):
    def index(rows):
        indexed = {tuple(row.get(k) for k in primary_keys): row for row in rows}
        if len(indexed) != len(rows):
            raise DualSourceWriteError("duplicate_target_identity")
        return indexed
    expected = {key: dict(row) for key, row in index(original).items()}
    for operation in operations:
        row = {**(operation["before"] or {}), **operation["values"]}
        key = tuple(row.get(k) for k in primary_keys)
        expected[key] = row
    observed = index(actual)
    if set(expected) != set(observed):
        raise DualSourceWriteError("target_row_set_changed")
    for key, wanted in expected.items():
        # 新增行可有数据库默认值；原有行则检查所有字段，防止非目标字段连带变化。
        if any(observed[key].get(field) != value for field, value in wanted.items()):
            raise DualSourceWriteError("target_value_verification_failed")


def run_sync(*, local_dsn, source_dsns, cases, tables, source_institutes,
             backup_dir, report_dir, apply=False, source_tables=None, target_schema="cdm",
             source_schemas=None, approved_records=None, connection_factory=psycopg2.connect,
             progress=None):
    """正式服务和独立验收脚本共用入口；所有源先读取成功，再在本地单事务写入。"""
    tables = tuple(dict.fromkeys(tables))
    order_pair = {"inpat_drug_order", "inpat_nondrug_order"}
    read_tables = tuple(dict.fromkeys((*tables, *sorted(order_pair - set(tables))))) if order_pair.intersection(tables) else tables
    if not cases or not tables or len({tuple(c[k] for k in policy.IDENTITY_FIELDS) for c in cases}) != len(cases):
        raise DualSourceWriteError("invalid_case_scope")
    if target_schema not in {"cdm", "public"}:
        raise DualSourceWriteError("invalid_target_schema")
    if any(not c.get("sample") or not all(c.get(k) for k in policy.IDENTITY_FIELDS) for c in cases):
        raise DualSourceWriteError("incomplete_case_scope")
    if set(source_institutes) != set(policy.SOURCES) or any(not source_institutes[s] for s in policy.SOURCES):
        raise DualSourceWriteError("explicit_institution_mapping_required")
    if any(c["institute_id"] != source_institutes["local"] for c in cases):
        raise DualSourceWriteError("target_institution_mismatch")
    source_schemas = source_schemas or {"clinical_data": "public", "homology": "graph3_homology"}
    source_tables = source_tables or {}
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ") + "-" + uuid4().hex[:8]
    report_path = Path(report_dir) / ("dual-source-write-" + stamp + ".json")
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report = {"format": "medqc_dual_source_write_report_v1", "mode": "apply" if apply else "preview",
              "data_committed": False, "model_calls": 0, "qc_tasks_started": 0,
              "schema_changes": 0, "deletes": 0, "tables": [], "records": []}
    phase, commit_attempted = "source_read", False
    try:
        with ExitStack() as stack:
            snapshots = {}
            for source in ("clinical_data", "homology"):
                needed = read_tables if source == "clinical_data" else tuple(t for t in read_tables if t in policy.TABLE_KEYS)
                snapshots[source] = {}
                if not needed:
                    continue
                conn = _connect(source_dsns[source], readonly=True, factory=connection_factory)
                stack.callback(conn.close)
                for table in needed:
                    phase = "source_read:" + source + ":" + table
                    snapshots[source][table] = read_rows(conn, source_schemas[source], source_tables.get(table, table) if source == "clinical_data" else table, cases)
            phase = "target_read"
            target = _connect(local_dsn, readonly=not apply, factory=connection_factory)
            stack.callback(target.close)
            metadata = {}
            for table in tables:
                phase = "target_schema:" + table
                metadata[table] = table_meta(target, target_schema, table)
            originals = {table: read_rows(target, target_schema, table, cases, local=True, lock=apply) for table in tables}
            identity_guards = {table: read_rows(target, target_schema, table, cases, local=True, lock=apply)
                               for table in read_tables if table not in tables}
            operations = []
            review_keys = []
            for case in cases:
                phase = "plan:" + case["sample"]
                plans = []
                for table in read_tables:
                    sources = []
                    for source in policy.SOURCES:
                        rows = (originals.get(table, identity_guards.get(table, []))) if source == "local" else snapshots[source].get(table, [])
                        scoped = tuple(row for row in rows if str(row.get("patient_id")) == case["patient_id"] and str(row.get("visit_id")) == case["visit_id"])
                        sources.append(policy.SourceSnapshot(source, scoped))
                    stable_keys = tuple(k for k in metadata[table]["primary_keys"] if k not in policy.IDENTITY_FIELDS) if table in metadata else None
                    plans.append(policy.plan_table(table, case, *sources, source_institutes=source_institutes, stable_keys=stable_keys))
                policy.mark_cross_table_order_ids(plans)
                for plan in plans:
                    table = plan.table
                    if table not in tables:
                        continue
                    batch = build_write_batch(table, plan, case, metadata[table]["columns"], metadata[table]["primary_keys"],
                                              [row for row in originals[table] if all(str(row[k]) == case[k] for k in policy.IDENTITY_FIELDS)],
                                              approved_records=(approved_records or {}).get((case["sample"], table), ()))
                    operations.extend(batch.operations)
                    report["records"].extend(batch.records)
                    for candidate, record in zip(plan.candidates, batch.records):
                        if record["conflicts"] or record["skipped"]:
                            review_keys.append({"sample": case["sample"], "table": table,
                                                "record_token": record["record_token"], "source_key": candidate.key})
                    report["tables"].append({"sample": case["sample"], "table": table,
                                             "source_profile": "dual_source" if table in policy.TABLE_KEYS else "clinical_only",
                                             "quarantined_rows": plan.quarantined_rows,
                                             "quarantine_reasons": plan.quarantine_reasons, "issues": plan.issues,
                                             "source_counts": plan.source_counts,
                                             "operations": len(batch.operations)})
                if progress:
                    progress({"sample": case["sample"], "planned_operations": len(operations)})
            report["inserts"] = sum(op["before"] is None for op in operations)
            report["updated_rows"] = len(operations) - report["inserts"]
            report["filled_fields"] = sum(len(op["values"]) for op in operations if op["before"] is not None)
            report["pending_records"] = sum(bool(r["conflicts"] or r["skipped"]) for r in report["records"])
            report["quarantined_rows"] = sum(item["quarantined_rows"] for item in report["tables"])
            review_path = report_path.with_name(report_path.stem + "-review-private.json")
            review_path.write_bytes(encoded({"cases": cases, "pending_record_keys": review_keys}))
            report["review_index_path"] = str(review_path)
            if apply:
                phase = "backup"
                backup_path = Path(backup_dir) / ("dual-source-before-" + stamp + "-private.json")
                report["backup_sha256"] = save_backup(backup_path, cases=cases, metadata=metadata, originals=originals,
                                                       related=related_rows(target, cases))
                report["backup_path"] = str(backup_path)
                # 报告无法持久化时不进入写入阶段。
                report_path.write_bytes(encoded(report))
                phase = "write"
                apply_operations(target, target_schema, operations, metadata)
                phase = "verify_before_commit"
                for table in tables:
                    verify_rows(originals[table], read_rows(target, target_schema, table, cases, local=True),
                                [op for op in operations if op["table"] == table], metadata[table]["primary_keys"])
                phase = "commit"
                commit_attempted = True
                target.commit()
                report["data_committed"] = True
            else:
                target.rollback()
            phase = "post_commit_read" if apply else "completed"
            final_rows = {table: read_rows(target, target_schema, table, cases, local=True) for table in tables} if apply else originals
            report["phase"] = "completed"
            report["report_path"] = str(report_path)
            report_path.write_bytes(encoded(report))
            return {"report": report, "rows_by_table": final_rows}
    except Exception as exc:
        report.update(phase=phase, error_type=type(exc).__name__,
                      error_code=exc.code if isinstance(exc, DualSourceWriteError) else "sync_failed",
                      data_committed=None if commit_attempted and not report["data_committed"] else report["data_committed"])
        sqlstate = str(getattr(exc, "pgcode", "") or "")
        report["sqlstate"] = sqlstate if len(sqlstate) == 5 and sqlstate.isalnum() else None
        report_path.write_bytes(encoded(report))
        raise DualSourceWriteError(report["error_code"], report_path=str(report_path), data_committed=report["data_committed"]) from None
