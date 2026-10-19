"""定向补全已验证的病理诊断和死亡正文；源库只读，本地备份后事务更新。"""

from __future__ import annotations

import argparse
from contextlib import redirect_stderr, redirect_stdout
from datetime import datetime, timezone
import io
import json
import logging
import os
from pathlib import Path
import re
import sys

import verify_report_sync as check


def identifier(value):
    if not re.fullmatch(r"[a-z_][a-z0-9_]*", value):
        raise check.CheckError("invalid_identifier")
    return f'"{value}"'


def plan_updates(etl, conn, table, rows, refs, death_fields):
    """使用验证过的投影，只计划单字段更新；锁定原行以便备份和并发核对。"""
    from sqlalchemy import text

    schema, preview = check.preview_upsert(etl, table, rows, refs, conn, death_fields)
    _, _, keys = etl._get_local_table_meta(conn, table)
    if not {"institute_id", "patient_id", "visit_id"}.issubset(keys):
        raise check.CheckError("target_identity_key_missing", table=table)
    limits = dict(conn.execute(text(
        "SELECT column_name, character_maximum_length FROM information_schema.columns "
        "WHERE table_schema=:s AND table_name=:t AND character_maximum_length IS NOT NULL"
    ), {"s": schema, "t": table}).all())
    check.validate_lengths(preview.rows, limits, table)
    field = "diagnosis" if table == "pathology_exam_report" else "record_content"
    target = f"{identifier(schema)}.{identifier(table)}"
    planned = {tuple(str(row[k]) for k in keys): row for row in preview.rows}
    if len(planned) != len(preview.rows):
        raise check.CheckError("duplicate_projected_key", table=table)
    original, updates = [], []
    for ref in refs:
        stored = list(conn.execute(text(
            f"SELECT * FROM {target} WHERE institute_id=:i AND patient_id=:p AND visit_id=:v FOR UPDATE"
        ), dict(zip(("i", "p", "v"), ref))).mappings())
        original.extend(dict(row) for row in stored)
    existing = {tuple(str(row[k]) for k in keys): row for row in original}
    if len(existing) != len(original) or set(existing) != set(planned):
        raise check.CheckError("local_report_identity_mismatch", table=table)
    for key, projected in planned.items():
        old = existing[key]
        value = projected[field]
        if not str(value or "").strip():
            raise check.CheckError("projected_content_empty", table=table)
        if table == "pathology_exam_report" and (
            str(old.get("pathology_id") or "") != str(projected.get("pathology_id") or "")
            or check.hospital_time(old.get("report_time")) != check.hospital_time(projected.get("report_time"))
            or old.get("report_status") != projected.get("report_status")
        ):
            raise check.CheckError("local_pathology_identity_changed")
        if old.get(field) == value:
            continue
        if str(old.get(field) or "").strip():
            raise check.CheckError("existing_content_conflict", table=table, field=field)
        updates.append({"keys": {k: old[k] for k in keys}, "value": value})
    return {"table": table, "schema": schema, "field": field, "keys": keys,
            "original_rows": original, "projected_rows": list(planned.values()), "updates": updates}


def write_backup(plans, directory):
    directory.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    path = directory / f"report-sync-before-{stamp}-private.json"
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump({"created_at_utc": stamp, "tables": [
            {k: p[k] for k in ("table", "schema", "field", "keys", "original_rows")}
            for p in plans
        ]}, stream, ensure_ascii=False, default=str)
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())
    return path


def update_fields(conn, plans):
    from sqlalchemy import text

    count = 0
    for plan in plans:
        target = f"{identifier(plan['schema'])}.{identifier(plan['table'])}"
        field = identifier(plan["field"])
        where = " AND ".join(f"{identifier(k)}=:k{n}" for n, k in enumerate(plan["keys"]))
        for update in plan["updates"]:
            params = {f"k{n}": update["keys"][k] for n, k in enumerate(plan["keys"])}
            result = conn.execute(text(f"UPDATE {target} SET {field}=:new_value WHERE {where}"),
                                  {**params, "new_value": update["value"]})
            if result.rowcount != 1:
                raise check.CheckError("unexpected_update_count", table=plan["table"])
            actual = conn.execute(text(f"SELECT {field} FROM {target} WHERE {where}"), params).scalar_one()
            if actual != update["value"]:
                raise check.CheckError("saved_value_mismatch", table=plan["table"])
            count += 1
    return count


def verify_bundles(assembly, plans):
    """核对已保存domain bundle的原字段，不运行规则或模型。"""
    for plan in plans:
        domain = "exam_results" if plan["table"] == "pathology_exam_report" else "terminal"
        cases = {}
        for row in plan["projected_rows"]:
            key = tuple(row[k] for k in ("institute_id", "patient_id", "visit_id"))
            cases.setdefault(key, []).append(row)
        for key, rows in cases.items():
            bundle = assembly.load_domain_bundle(execution_domain=domain,
                                                **dict(zip(("institute_id", "patient_id", "visit_id"), key)))
            docs = ((bundle or {}).get("structured_context") or {}).get("documents") or {}
            saved = {tuple(str(r.get(k) or "") for k in plan["keys"]): r
                     for r in docs.get(plan["table"], [])}
            for row in rows:
                match = saved.get(tuple(str(row[k]) for k in plan["keys"]))
                if match is None or match.get(plan["field"]) != row[plan["field"]]:
                    raise check.CheckError("bundle_content_not_updated", table=plan["table"])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--backend", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--backup-dir", type=Path, required=True)
    parser.add_argument("--apply", action="store_true", required=True)
    args = parser.parse_args()
    backup_dir = args.backup_dir.resolve()
    output_path = args.output.resolve()
    logging.disable(logging.CRITICAL)
    committed = False
    updated = 0
    phase = "load_backend"
    with output_path.open("w", encoding="utf-8", newline="\n") as output:
        def emit(event, **details):
            line = json.dumps({"event": event, **details}, ensure_ascii=False)
            print(line, flush=True)
            output.write(line + "\n")
            output.flush()

        try:
            backend = Path(args.backend).resolve()
            sys.path.insert(0, str(backend))
            os.chdir(backend)
            from dotenv import load_dotenv

            load_dotenv(backend / ".env", override=True)
            scope = json.loads(Path(__file__).with_name("report-sync-scope-private.json").read_text(encoding="utf-8"))
            with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
                from app.services import etl_sync as etl
                from app.services.case_identity import CaseRef
                from app.database.connection import engine
                from app.services.bundles import assembly
            if engine is None or engine.dialect.name != "postgresql":
                raise check.CheckError("local_postgresql_required")
            from psycopg2.extensions import make_dsn
            from sqlalchemy import text

            adapter = check.load_adapter(Path(__file__).with_name("homology_sync.py"))
            os.environ.update({"HOMOLOGY_PATHOLOGY_REPORT_SYNC_ENABLED": "true",
                               "HOMOLOGY_DATABASE": "homology", "HOMOLOGY_SCHEMA": "graph3_homology",
                               "HOMOLOGY_SOURCE_INSTITUTE_ID": scope["source_institute_id"],
                               "HOMOLOGY_TARGET_INSTITUTE_ID": scope["target_institute_id"]})
            refs_by_table = {table: [CaseRef(scope["target_institute_id"], r["patient_id"], r["visit_id"])
                                    for r in scope[key]] for table, key in (
                ("pathology_exam_report", "pathology_cases"), ("death_record", "death_cases"))}
            phase = "read_sources"
            remote = etl.get_remote_db_url()
            route = adapter.resolve_homology_source(table_name="pathology_exam_report", remote_url=remote)
            clinical = make_dsn(remote, dbname="clinical_data")
            refs = refs_by_table[route.table]
            source = check.fetch_source(route.remote_url, route.schema, route.table, route.source_case_refs(refs))
            check.compare_pathology(source, check.fetch_source(clinical, "public", route.table, refs),
                                    scope["pathology_reports"])
            death = check.fetch_source(clinical, "public", "death_record", refs_by_table["death_record"])
            if len(source) != 5 or len(death) != 5 or {
                CaseRef.from_mapping(r) for r in death
            } != set(refs_by_table["death_record"]):
                raise check.CheckError("source_scope_changed")
            rows_by_table = {route.table: route.adapt_rows(source, refs), "death_record": death}
            phase = "backup_and_update"
            with engine.begin() as conn:
                conn.execute(text("SET LOCAL lock_timeout = '10s'"))
                conn.execute(text("SET LOCAL statement_timeout = '30s'"))
                plans = [plan_updates(etl, conn, table, rows, refs_by_table[table], scope["death_record_fields"])
                         for table, rows in rows_by_table.items()]
                backup = write_backup(plans, backup_dir)
                emit("backup_saved", path=str(backup), records=sum(len(p["original_rows"]) for p in plans))
                updated = update_fields(conn, plans)
            committed = True
            emit("data_committed", updated_rows=updated, checked_rows=10, model_calls=0)
            phase = "refresh_bundles"
            all_refs = [r for refs in refs_by_table.values() for r in refs]
            stats = etl._refresh_all_bundle_variants_after_sync(case_refs=[tuple(r) for r in all_refs],
                                                               policy_version="")
            emit("bundle_refresh", counts={group: stats.get(group) for group in ("scenes", "domains")})
            phase = "verify_bundles"
            verify_bundles(assembly, plans)
            emit("done", data_committed=True, updated_rows=updated, checked_rows=10,
                 bundle_verified=True, model_calls=0, clinical_results_saved=False,
                 runtime_files_changed=False)
            return 0
        except Exception as exc:
            emit("error", phase=phase, data_committed=committed, updated_rows=updated if committed else 0,
                 error_type=type(exc).__name__, code=exc.code if isinstance(exc, check.CheckError) else None,
                 details=exc.details if isinstance(exc, check.CheckError) else {}, model_calls=0)
            return 1


if __name__ == "__main__":
    sys.exit(main())
