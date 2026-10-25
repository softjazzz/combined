"""27例医嘱：源端只读，备份后仅补确认身份的已有行空字段，冲突跳过。"""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from datetime import datetime, timezone
import hashlib
import json
import logging
import os
from pathlib import Path

import preview_orders27 as preview
import preview_order_time_fill as check


TIME_TYPES = {
    "planned_end_datetime": "timestamp with time zone",
    "reviewed_datetime": "timestamp without time zone",
    "carried_datetime": "timestamp without time zone",
    "canceled_datetime": "timestamp without time zone",
}
COMMON_FILL = {"inpat_no", "dept_name", "prescribed_datetime", "planned_start_datetime", *TIME_TYPES}
DRUG_FILL = {"brand_name", "drug_specification", "firm", "single_dose", "single_dose_unit",
             "drug_frequency", "drug_apply_method", "medication_duration"}
NONDRUG_FILL = {"quantity", "quantity_unit", "frequency"}
TEXT_TYPES = {"character varying", "character", "text"}


def read_meta(conn, table):
    from psycopg2.extras import RealDictCursor
    with conn.cursor(cursor_factory=RealDictCursor) as cursor:
        cursor.execute("SELECT column_name,data_type,is_nullable,column_default,character_maximum_length "
                       "FROM information_schema.columns WHERE table_schema='cdm' AND table_name=%s "
                       "ORDER BY ordinal_position", (table,))
        meta = {row["column_name"]: dict(row) for row in cursor.fetchall()}
    if not set(check.KEYS).issubset(meta):
        raise check.PreviewError("local_table_or_keys_missing:" + table)
    return meta


def local_case(conn, table, case):
    from psycopg2 import sql
    from psycopg2.extras import RealDictCursor
    with conn.cursor(cursor_factory=RealDictCursor) as cursor:
        cursor.execute(sql.SQL("SELECT * FROM cdm.{} WHERE institute_id=%s AND patient_id=%s AND visit_id=%s").format(
            sql.Identifier(table)), (case["institute_id"], case["patient_id"], case["visit_id"]))
        return [dict(row) for row in cursor.fetchall()]


def excluded_order(row):
    if str(row.get("is_deleted") or "").strip().lower() in {"1", "true", "t", "yes"}:
        return True
    status = str(row.get("order_status") or "").strip().lower()
    return any(word in status for word in ("撤销", "取消", "作废", "cancel", "void", "delete"))


def strong_identity(table, source, local):
    if preview.identity_issues(table, source, local):
        return False
    # 两侧开立时间均须可用并相同，不以相同名称单独认定同一医嘱。
    for row in (source, local):
        if preview.blank(row.get("prescribed_datetime")):
            return False
    if check.parse_time(source["prescribed_datetime"]) != check.parse_time(local["prescribed_datetime"]):
        return False
    if table == preview.TABLES[0]:
        left, right = source.get("drug_code"), local.get("drug_code")
        if preview.blank(left) or preview.blank(right) or str(left).strip() != str(right).strip():
            return False
    return True


def convert_value(field, value, column):
    kind = column["data_type"]
    if field.endswith("_datetime"):
        parsed = check.parse_time(value)
        if kind == "timestamp with time zone":
            return parsed
        if kind == "timestamp without time zone":
            return parsed.replace(tzinfo=None)
        raise check.PreviewError("unsupported_time_type")
    if kind not in TEXT_TYPES:
        raise check.PreviewError("unsupported_field_type")
    text = str(value)
    maximum = column.get("character_maximum_length")
    if maximum is not None and len(text) > maximum:
        raise check.PreviewError("source_value_too_long")
    return text


def field_plan(table, source, local, meta):
    allowed = COMMON_FILL | (DRUG_FILL if table == preview.TABLES[0] else NONDRUG_FILL)
    changes, skipped = {}, Counter()
    regimen = ({"single_dose", "single_dose_unit", "drug_frequency", "drug_apply_method", "medication_duration"}
               if table == preview.TABLES[0] else {"quantity", "quantity_unit", "frequency"})
    regimen_conflict = any(
        not preview.blank(source.get(f)) and not preview.blank(local.get(f))
        and preview.comparable(f, source[f]) != preview.comparable(f, local[f]) for f in regimen)
    for field in sorted(allowed):
        src, old = source.get(field), local.get(field)
        if preview.blank(src):
            continue
        if not preview.blank(old):
            try:
                if preview.comparable(field, src) != preview.comparable(field, old):
                    skipped["nonempty_conflict:" + field] += 1
            except (ValueError, check.PreviewError):
                skipped["invalid_time:" + field] += 1
            continue
        if field in regimen and regimen_conflict:
            skipped["regimen_conflict:" + field] += 1
            continue
        if field not in meta:
            skipped["target_column_missing:" + field] += 1
            continue
        try:
            changes[field] = convert_value(field, src, meta[field])
        except (ValueError, check.PreviewError) as exc:
            code = str(exc) if isinstance(exc, check.PreviewError) else "invalid_time"
            skipped[code + ":" + field] += 1
    return changes, skipped


def plan_case(case, source, original, metas):
    local = {t: [preview.canonical(r, preview.mapping(t)) for r in original[t]] for t in preview.TABLES}
    si = {t: preview.index_rows(source[t]) for t in preview.TABLES}
    li = {t: preview.index_rows(local[t]) for t in preview.TABLES}
    raw = {t: preview.index_rows(original[t]) for t in preview.TABLES}
    plans, skipped = [], Counter()
    for table in preview.TABLES:
        other = next(t for t in preview.TABLES if t != table)
        for oid in sorted(set(si[table]) | set(li[table])):
            sr, lr = si[table].get(oid, []), li[table].get(oid, [])
            if not oid or len(sr) > 1 or len(lr) > 1:
                skipped["empty_or_duplicate_id"] += 1
                continue
            if si[other].get(oid) or li[other].get(oid):
                skipped["cross_table_id"] += 1
                continue
            if not sr or not lr:
                skipped["source_only_no_insert" if sr else "local_only_keep"] += 1
                continue
            if excluded_order(sr[0]) or excluded_order(lr[0]):
                skipped["cancelled_or_deleted_keep"] += 1
                continue
            try:
                if not strong_identity(table, sr[0], lr[0]):
                    skipped["identity_unconfirmed"] += 1
                    continue
            except (ValueError, check.PreviewError):
                skipped["identity_time_invalid"] += 1
                continue
            # 原始编号须与规范编号完全一致，不根据去空白后的编号写入。
            old = raw[table].get(oid, [])
            if len(old) != 1 or old[0]["order_id"] != oid:
                skipped["raw_order_id_not_exact"] += 1
                continue
            changes, reasons = field_plan(table, sr[0], old[0], metas[table])
            skipped.update(reasons)
            if changes:
                plans.append({"sample": case["sample"], "table": table,
                              "keys": {k: old[0][k] for k in check.KEYS}, "changes": changes})
    return plans, skipped


def save_backup(path, metas, originals):
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {"scope": "27 admissions; cdm drug/nondrug orders only", "original_schema": metas,
               "original_cases": originals}
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(payload, stream, ensure_ascii=False, default=str)
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())
    raw = path.read_bytes()
    restored = json.loads(raw)
    if len(restored["original_cases"]) != 27:
        raise check.PreviewError("backup_verification_failed")
    return hashlib.sha256(raw).hexdigest()


def update_plans(conn, plans, originals):
    from psycopg2 import sql
    from psycopg2.extras import execute_batch
    groups = defaultdict(list)
    for plan in plans:
        groups[(plan["table"], tuple(sorted(plan["changes"])))].append(plan)
    old_by_key = {}
    for original in originals:
        for table, rows in original["rows"].items():
            for row in rows:
                old_by_key[(table, *(row[k] for k in check.KEYS))] = row
    with conn.cursor() as cursor:
        for (table, fields), batch in groups.items():
            statement = sql.SQL("UPDATE cdm.{} SET {} WHERE {} AND {}").format(
                sql.Identifier(table),
                sql.SQL(", ").join(sql.SQL("{}=%s").format(sql.Identifier(f)) for f in fields),
                sql.SQL(" AND ").join(sql.SQL("{}=%s").format(sql.Identifier(k)) for k in check.KEYS),
                sql.SQL(" AND ").join(sql.SQL("{} IS NOT DISTINCT FROM %s").format(sql.Identifier(f)) for f in fields),
            )
            params = []
            for plan in batch:
                keys = [plan["keys"][k] for k in check.KEYS]
                old = old_by_key[(table, *keys)]
                params.append([plan["changes"][f] for f in fields] + keys + [old.get(f) for f in fields])
            execute_batch(cursor, statement, params, page_size=200)


def verify_case(before, after, plans):
    for table in preview.TABLES:
        def grouped(rows):
            result = defaultdict(list)
            for row in rows:
                result[tuple(row[k] for k in check.KEYS)].append(row)
            return result
        left, right = grouped(before[table]), grouped(after[table])
        if set(left) != set(right):
            raise check.PreviewError("row_scope_changed")
        expected_changes = {tuple(p["keys"][k] for k in check.KEYS): p["changes"]
                            for p in plans if p["table"] == table}
        for identity, old_rows in left.items():
            changes = expected_changes.get(identity, {})
            if len(old_rows) != len(right[identity]) or (len(old_rows) > 1 and changes):
                raise check.PreviewError("duplicate_rows_changed")
            remaining = list(right[identity])
            for old in old_rows:
                expected = {**old, **changes}
                for field in TIME_TYPES:
                    if field not in expected and any(field in r for r in remaining):
                        expected[field] = None
                match = next((n for n, row in enumerate(remaining) if row == expected), None)
                if match is None:
                    raise check.PreviewError("post_write_row_verification_failed")
                remaining.pop(match)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--backend", required=True, type=Path)
    parser.add_argument("--scope", type=Path, default=Path(__file__).with_name("cases27-private.json"))
    parser.add_argument("--backup-dir", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--apply", required=True, action="store_true")
    args = parser.parse_args(argv)
    backend, scope_path = args.backend.resolve(), args.scope.resolve()
    output_dir, backup_dir = args.output_dir.resolve(), args.backup_dir.resolve()
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    output_dir.mkdir(parents=True, exist_ok=True)
    report_path = output_dir / f"orders27-fill-{stamp}.jsonl"
    backup_path = backup_dir / f"orders27-before-{stamp}-private.json"
    logging.disable(logging.CRITICAL)
    source_conn = conn = None
    committed = attempted = False
    phase = "configuration"
    with report_path.open("x", encoding="utf-8", newline="\n") as report:
        def emit(event, **data):
            line = json.dumps({"event": event, **data}, ensure_ascii=True)
            print(line, flush=True)
            report.write(line + "\n")
            report.flush()
        try:
            cases = preview.scope_cases(json.loads(scope_path.read_text(encoding="utf-8-sig")))
            local_dsn, source_dsn = check.connection_dsns(backend)
            emit("scope", cases=27, tables=list(preview.TABLES), inserts=0, deletes=0, model_calls=0)
            phase = "source_readonly"
            source_conn = check.connect_readonly(source_dsn)
            source_cols = {t: set(preview.table_columns(source_conn, "graph3_homology", t)) for t in preview.TABLES}
            sources = []
            for case in cases:
                rows = {}
                for table in preview.TABLES:
                    rows[table], _ = preview.read_case(source_conn, "graph3_homology", table,
                                                      source_cols[table], "机构号", case)
                sources.append(rows)
                emit("source_read", sample=case["sample"], rows=sum(map(len, rows.values())))
            source_conn.rollback()
            phase = "local_lock"
            import psycopg2
            from psycopg2 import sql
            conn = psycopg2.connect(local_dsn, connect_timeout=10)
            conn.set_session(isolation_level="SERIALIZABLE")
            with conn.cursor() as cursor:
                cursor.execute("SET LOCAL lock_timeout='5s'")
                cursor.execute("SET LOCAL statement_timeout='30s'")
                cursor.execute("LOCK TABLE cdm.inpat_drug_order,cdm.inpat_nondrug_order IN ACCESS EXCLUSIVE MODE")
                cursor.execute("SELECT count(*) FROM pg_trigger WHERE tgrelid IN "
                               "('cdm.inpat_drug_order'::regclass,'cdm.inpat_nondrug_order'::regclass) "
                               "AND NOT tgisinternal AND tgenabled<>'D'")
                if cursor.fetchone()[0]:
                    raise check.PreviewError("custom_trigger_requires_review")
            metas = {t: read_meta(conn, t) for t in preview.TABLES}
            effective = {t: {**metas[t], **{f: {"column_name": f, "data_type": typ}
                                         for f, typ in TIME_TYPES.items() if f not in metas[t]}}
                         for t in preview.TABLES}
            originals, plans, skip_counts = [], [], Counter()
            phase = "plan"
            for case, source in zip(cases, sources):
                old = {t: local_case(conn, t, case) for t in preview.TABLES}
                originals.append({"sample": case["sample"], "rows": old})
                current, skips = plan_case(case, source, old, effective)
                plans.extend(current)
                skip_counts.update(skips)
            phase = "backup"
            digest = save_backup(backup_path, metas, originals)
            emit("backup_saved", path=str(backup_path), sha256=digest, schema_saved=True,
                 rows=sum(len(rows) for original in originals for rows in original["rows"].values()))
            phase = "add_columns_and_fill"
            added = []
            with conn.cursor() as cursor:
                for table in preview.TABLES:
                    for field, kind in TIME_TYPES.items():
                        if field not in metas[table]:
                            cursor.execute(sql.SQL("ALTER TABLE cdm.{} ADD COLUMN {} {} NULL").format(
                                sql.Identifier(table), sql.Identifier(field), sql.SQL(kind)))
                            added.append(table + "." + field)
            update_plans(conn, plans, originals)
            phase = "verify"
            for case, original in zip(cases, originals):
                after = {t: local_case(conn, t, case) for t in preview.TABLES}
                case_plans = [p for p in plans if p["sample"] == case["sample"]]
                verify_case(original["rows"], after, case_plans)
                emit("case_verified", sample=case["sample"], updated_rows=len(case_plans),
                     filled_fields=sum(len(p["changes"]) for p in case_plans))
            phase = "commit"
            attempted = True
            conn.commit()
            committed = True
            fields = Counter((p["table"] + "." + f) for p in plans for f in p["changes"])
            emit("done", data_committed=True, updated_rows=len(plans), filled_fields=sum(fields.values()),
                 filled_by_field=dict(fields), skipped=dict(skip_counts), added_columns=added,
                 inserts=0, deletes=0, model_calls=0, source_database_writes=0,
                 bundles_refreshed=False, alembic_version_changed=False, report=str(report_path))
            return 0
        except Exception as exc:
            rollback_ok = False
            if conn is not None and not committed:
                try:
                    conn.rollback()
                    rollback_ok = not attempted
                except Exception:
                    pass
            emit("error", phase=phase, data_committed=None if attempted and not committed else committed,
                 rolled_back=rollback_ok, error_type=type(exc).__name__, sqlstate=getattr(exc, "pgcode", None),
                 code=str(exc) if isinstance(exc, check.PreviewError) else None, model_calls=0)
            return 1
        finally:
            for connection in (source_conn, conn):
                if connection is not None:
                    connection.close()


if __name__ == "__main__":
    raise SystemExit(main())
