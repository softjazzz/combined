"""先备份，仅补两条药品医嘱的空时间；源库只读，不更改其他业务数据。"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import logging
import os
from pathlib import Path

import preview_order_time_fill as check


TABLE = "inpat_drug_order"
SCHEMA = "cdm"
TYPES = {
    "planned_end_datetime": "timestamp with time zone",
    "reviewed_datetime": "timestamp without time zone",
    "carried_datetime": "timestamp without time zone",
    "canceled_datetime": "timestamp without time zone",
}


def metadata(conn):
    from psycopg2.extras import RealDictCursor

    with conn.cursor(cursor_factory=RealDictCursor) as cursor:
        cursor.execute(
            "SELECT column_name,data_type,is_nullable,column_default,ordinal_position "
            "FROM information_schema.columns WHERE table_schema=%s AND table_name=%s "
            "ORDER BY ordinal_position", (SCHEMA, TABLE),
        )
        return [dict(row) for row in cursor.fetchall()]


def target_row(conn, institute, case, *, lock=False):
    from psycopg2.extras import RealDictCursor

    query = ('SELECT * FROM cdm.inpat_drug_order WHERE institute_id=%s AND patient_id=%s '
             'AND visit_id=%s AND order_id=%s LIMIT 2')
    if lock:
        query += ' FOR UPDATE'
    with conn.cursor(cursor_factory=RealDictCursor) as cursor:
        cursor.execute(query, (institute, case["patient_id"], case["visit_id"], case["order_id"]))
        rows = cursor.fetchall()
    if len(rows) != 1:
        raise check.PreviewError("local_order_missing_or_not_unique")
    return dict(rows[0])


def plan_fill(source, local):
    blockers = check.identity_checks(source, local)
    if blockers:
        raise check.PreviewError("identity_conflict:" + ",".join(blockers))
    changes = {}
    for field in check.FIELDS:
        if field not in source:
            raise check.PreviewError("source_column_missing:" + field)
        action = check.compare_field(source[field], local.get(field))
        if action == "conflict":
            raise check.PreviewError("nonempty_time_conflict:" + field)
        if action == "fill_candidate":
            value = check.parse_time(source[field])
            # datetime 列仍保存医院本地无时区时间；计划列保留 +08:00。
            changes[field] = value if field == "planned_end_datetime" else value.replace(tzinfo=None)
    return changes


def validate_types(meta, *, require_all=False):
    actual = {row["column_name"]: row["data_type"] for row in meta}
    if not set(check.KEYS).issubset(actual):
        raise check.PreviewError("local_identity_columns_missing")
    if require_all and set(TYPES) - set(actual):
        raise check.PreviewError("saved_time_columns_missing")
    for name, expected in TYPES.items():
        if name in actual and actual[name] != expected:
            raise check.PreviewError("existing_time_column_type_conflict:" + name)


def save_backup(directory, meta, plans):
    directory.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    path = directory / f"order-times-before-{stamp}-private.json"
    payload = {
        "created_at_utc": stamp, "schema": SCHEMA, "table": TABLE,
        "original_columns": meta, "rows": [p["original"] for p in plans],
        "source_times": [
            {"sample": p["case"]["sample"], **{f: p["source"].get(f) for f in check.FIELDS}}
            for p in plans
        ],
    }
    raw = (json.dumps(payload, ensure_ascii=False, default=str, indent=2) + "\n").encode("utf-8")
    with path.open("xb") as stream:
        stream.write(raw)
        stream.flush()
        os.fsync(stream.fileno())
    if path.read_bytes() != raw:
        raise check.PreviewError("backup_verification_failed")
    return path, hashlib.sha256(raw).hexdigest()


def apply_changes(conn, meta, plans, institute):
    from psycopg2 import sql

    existing = {row["column_name"] for row in meta}
    added = []
    with conn.cursor() as cursor:
        for field, column_type in TYPES.items():
            if field in existing:
                continue
            cursor.execute(sql.SQL("ALTER TABLE cdm.inpat_drug_order ADD COLUMN {} {} NULL").format(
                sql.Identifier(field), sql.SQL(column_type),
            ))
            added.append(field)
        for plan in plans:
            changes = plan["changes"]
            if not changes:
                continue
            fields = sorted(changes)
            # 四坐标精确更新；只填 NULL，在并发冲突时不覆盖新值。
            query = sql.SQL("UPDATE cdm.inpat_drug_order SET {} WHERE {} AND {}").format(
                sql.SQL(", ").join(sql.SQL("{}=%s").format(sql.Identifier(f)) for f in fields),
                sql.SQL(" AND ").join(sql.SQL("{}=%s").format(sql.Identifier(k)) for k in check.KEYS),
                sql.SQL(" AND ").join(sql.SQL("{} IS NULL").format(sql.Identifier(f)) for f in fields),
            )
            case = plan["case"]
            cursor.execute(query, [changes[f] for f in fields] + [
                institute, case["patient_id"], case["visit_id"], case["order_id"],
            ])
            if cursor.rowcount != 1:
                raise check.PreviewError("unexpected_update_count")
    return added


def verify_row(original, actual, source):
    for field, value in original.items():
        if field not in check.FIELDS and actual.get(field) != value:
            raise check.PreviewError("non_target_field_changed:" + field)
    for field in check.FIELDS:
        old, src, saved = original.get(field), source.get(field), actual.get(field)
        expected = old if check.parse_time(old) is not None else src
        if check.parse_time(saved) != check.parse_time(expected):
            raise check.PreviewError("saved_time_mismatch:" + field)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--backend", required=True, type=Path)
    parser.add_argument("--scope", type=Path, default=Path(__file__).with_name("order-time-scope-private.json"))
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--backup-dir", required=True, type=Path)
    parser.add_argument("--apply", required=True, action="store_true")
    args = parser.parse_args(argv)
    backend, scope_path = args.backend.resolve(), args.scope.resolve()
    output_path, backup_dir = args.output.resolve(), args.backup_dir.resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    logging.disable(logging.CRITICAL)
    source_conn = local_conn = None
    phase, committed, commit_attempted = "configuration", False, False
    with output_path.open("x", encoding="utf-8", newline="\n") as output:
        def emit(event, **details):
            line = json.dumps({"event": event, **details}, ensure_ascii=False)
            print(line, flush=True)
            output.write(line + "\n")
            output.flush()

        try:
            scope = json.loads(scope_path.read_text(encoding="utf-8-sig"))
            cases = check.validate_scope(scope)
            local_dsn, source_dsn = check.connection_dsns(backend)
            emit("scope", cases=2, table="cdm.inpat_drug_order", model_calls=0,
                 updates_only_empty_times=True, changes_order_status=False)
            phase = "source_readonly"
            source_conn = check.connect_readonly(source_dsn)
            source_cols = check.columns(source_conn, scope["source_schema"])
            source_rows = []
            for case in cases:
                row, aliases = check.fetch_order(source_conn, scope["source_schema"], source_cols,
                                                 scope["source_institute_id"], case)
                if set(check.FIELDS) - set(aliases):
                    raise check.PreviewError("source_time_columns_missing")
                source_rows.append(row)
            phase = "local_preflight"
            import psycopg2

            local_conn = psycopg2.connect(local_dsn, connect_timeout=10)
            local_conn.set_session(isolation_level="SERIALIZABLE")
            with local_conn.cursor() as cursor:
                cursor.execute("SET LOCAL lock_timeout = '5s'")
                cursor.execute("SET LOCAL statement_timeout = '30s'")
                # 修改字段前确保表结构/原始两行与备份一致；短超时避免阻塞工作台。
                cursor.execute("LOCK TABLE cdm.inpat_drug_order IN ACCESS EXCLUSIVE MODE")
                cursor.execute("SELECT count(*) FROM pg_trigger WHERE tgrelid="
                               "'cdm.inpat_drug_order'::regclass AND NOT tgisinternal AND tgenabled<>'D'")
                if cursor.fetchone()[0]:
                    raise check.PreviewError("custom_trigger_requires_review")
            meta = metadata(local_conn)
            validate_types(meta)
            plans = []
            for case, source in zip(cases, source_rows):
                original = target_row(local_conn, scope["target_institute_id"], case, lock=True)
                changes = plan_fill(source, original)
                plans.append({"case": case, "source": source, "original": original, "changes": changes})
            phase = "backup"
            backup, digest = save_backup(backup_dir, meta, plans)
            emit("backup_saved", path=str(backup), rows=2, schema_saved=True, sha256=digest)
            phase = "apply_and_verify"
            added = apply_changes(local_conn, meta, plans, scope["target_institute_id"])
            validate_types(metadata(local_conn), require_all=True)
            for plan in plans:
                actual = target_row(local_conn, scope["target_institute_id"], plan["case"])
                verify_row(plan["original"], actual, plan["source"])
                emit("verified", sample=plan["case"]["sample"],
                     filled_fields=sorted(plan["changes"]), non_target_fields_unchanged=True)
            phase = "commit"
            commit_attempted = True
            local_conn.commit()
            committed = True
            emit("done", data_committed=True, added_columns=added,
                 updated_rows=sum(bool(p["changes"]) for p in plans),
                 filled_time_fields=sum(len(p["changes"]) for p in plans),
                 checked_rows=2, model_calls=0, source_database_writes=0,
                 bundles_refreshed=False, alembic_version_changed=False)
            return 0
        except Exception as exc:
            rolled_back = False
            if local_conn is not None and not committed:
                try:
                    local_conn.rollback()
                    rolled_back = not commit_attempted
                except Exception:
                    pass
            outcome = None if commit_attempted and not committed else committed
            emit("error", phase=phase, data_committed=outcome,
                 error_type=type(exc).__name__, sqlstate=getattr(exc, "pgcode", None),
                 code=str(exc) if isinstance(exc, check.PreviewError) else None,
                 rolled_back=rolled_back, model_calls=0)
            return 1
        finally:
            for conn in (source_conn, local_conn):
                if conn is not None:
                    conn.close()


if __name__ == "__main__":
    raise SystemExit(main())
