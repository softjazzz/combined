"""客户机病理/死亡记录同步只读演练；不调用模型，不执行数据库写入。"""

from __future__ import annotations

import argparse
from contextlib import redirect_stderr, redirect_stdout
from datetime import datetime, timedelta, timezone
import importlib.util
import inspect
import io
import json
import logging
import os
from pathlib import Path
import sys


class CheckError(Exception):
    def __init__(self, code, **details):
        super().__init__(code)
        self.code = code
        self.details = details


class PreviewSession:
    """元数据 SELECT 交给只读连接；入库和删除语句仅保留在内存。"""

    def __init__(self, connection):
        self.connection = connection
        self.rows = []
        self.replacements = 0

    def execute(self, statement, params=None):
        command = str(statement).lstrip().split(None, 1)[0].upper()
        if command == "SELECT":
            return self.connection.execute(statement, params or {})
        batch = params if isinstance(params, list) else [params]
        if command == "INSERT":
            self.rows.extend(dict(row) for row in batch)
        elif command == "DELETE":
            self.replacements += len(batch)
        else:
            raise CheckError("unexpected_sql_in_preview", command=command)
        return None


def preview_upsert(etl, table, rows, refs, connection, death_fields):
    parameters = inspect.signature(etl.upsert_to_local).parameters
    if not {"session", "replace_case_refs"}.issubset(parameters):
        raise CheckError("client_upsert_api_too_old")
    schema, columns, keys = etl._get_local_table_meta(connection, table)
    field = "diagnosis" if table == "pathology_exam_report" else "record_content"
    if not schema or field not in columns:
        raise CheckError("target_field_missing", table=table, field=field)
    preview = PreviewSession(connection)
    previous = etl._STRUCTURED_DOCUMENT_CONTENT_FIELDS.get("death_record")
    try:
        if table == "death_record":
            etl._STRUCTURED_DOCUMENT_CONTENT_FIELDS[table] = tuple(
                (label, tuple(names)) for label, names in death_fields
            )
        kwargs = {"table_name": table, "records": rows, "primary_keys": keys,
                  "session": preview, "replace_case_refs": refs}
        if "required_columns" in parameters:
            kwargs["required_columns"] = (field,)
        count = etl.upsert_to_local(**kwargs)
    finally:
        if previous is None:
            etl._STRUCTURED_DOCUMENT_CONTENT_FIELDS.pop("death_record", None)
        else:
            etl._STRUCTURED_DOCUMENT_CONTENT_FIELDS["death_record"] = previous
    if count != len(rows) or len(preview.rows) != len(rows):
        raise CheckError("upsert_dropped_rows", table=table)
    planned = {tuple(str(row.get(k) or "") for k in keys): row for row in preview.rows}
    for row in rows:
        normalized = etl._apply_sync_column_aliases(
            table_name=table, record=row, existing_columns=set(columns)
        )
        saved = planned.get(tuple(str(normalized.get(k) or "") for k in keys))
        if saved is None or (table == "pathology_exam_report" and saved.get(field) != normalized.get(field)):
            raise CheckError("projected_content_changed", table=table)
        if table == "death_record":
            original = etl._first_non_empty(row, ("record_content",))
            if original and original not in str(saved.get(field) or ""):
                raise CheckError("death_original_content_dropped")
            for label, names in death_fields:
                value = etl._first_non_empty(row, tuple(names))
                if value and f"{label}：{value}" not in str(saved.get(field) or ""):
                    raise CheckError("death_section_dropped", section=label)
    return schema, preview


def validate_lengths(rows, limits, table):
    for row in rows:
        for field, maximum in limits.items():
            value = row.get(field)
            if isinstance(value, str) and len(value) > maximum:
                raise CheckError("target_value_too_long", table=table, field=field,
                                 allowed=maximum, actual=len(value))


def hospital_time(value):
    if not value:
        return ""
    if isinstance(value, str):
        value = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    if value.tzinfo is not None:
        value = value.astimezone(timezone(timedelta(hours=8))).replace(tzinfo=None)
    return value.isoformat(timespec="seconds")


def compare_pathology(upstream, downstream, expected):
    def identity(row):
        return tuple(str(row.get(k) or "").strip() for k in (
            "patient_id", "visit_id", "pathology_exam_id", "pathology_id"
        ))

    source = {identity(row): row for row in upstream}
    target = {identity(row): row for row in downstream}
    wanted = {tuple(item[k] for k in (
        "patient_id", "visit_id", "pathology_exam_id", "pathology_id"
    )) for item in expected}
    if (len(source) != len(upstream) or len(target) != len(downstream)
            or set(source) != wanted or set(target) != wanted):
        raise CheckError("pathology_report_identity_mismatch")
    for key, row in source.items():
        baseline = target[key]
        if hospital_time(row.get("report_datetime")) != hospital_time(baseline.get("report_time")):
            raise CheckError("pathology_report_time_mismatch")
        if row.get("report_status") != baseline.get("report_status"):
            raise CheckError("pathology_report_status_mismatch")
        if not str(row.get("diagnosis") or "").strip():
            raise CheckError("source_diagnosis_empty")


def fetch_source(url, schema, table, refs):
    import psycopg2
    import psycopg2.extras

    if (schema, table) not in {
        ("graph3_homology", "pathology_exam_report"),
        ("public", "pathology_exam_report"), ("public", "death_record"),
    }:
        raise CheckError("unexpected_source_table")
    conn = psycopg2.connect(url, connect_timeout=10)
    try:
        conn.set_session(readonly=True)
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cursor:
            cursor.execute("SET LOCAL statement_timeout = '30s'")
            placeholders = ",".join(["(%s,%s,%s)"] * len(refs))
            cursor.execute(
                f'SELECT * FROM "{schema}"."{table}" '
                f"WHERE (institute_id::text, patient_id::text, visit_id::text) IN ({placeholders})",
                [value for ref in refs for value in ref],
            )
            return [dict(row) for row in cursor.fetchall()]
    finally:
        conn.close()


def load_adapter(path):
    name = "app.services._verified_report_sync_adapter"
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--backend", required=True)
    parser.add_argument("--scope", type=Path, default=Path(__file__).with_name("report-sync-scope-private.json"))
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.scope = args.scope.resolve()
    logging.disable(logging.CRITICAL)
    output = args.output.open("w", encoding="utf-8", newline="\n")

    def emit(event, **details):
        line = json.dumps({"event": event, **details}, ensure_ascii=False)
        print(line, flush=True)
        output.write(line + "\n")
        output.flush()

    phase = "load_backend"
    try:
        backend = Path(args.backend).resolve()
        sys.path.insert(0, str(backend))
        os.chdir(backend)
        from dotenv import load_dotenv

        load_dotenv(backend / ".env", override=True)
        scope = json.loads(args.scope.read_text(encoding="utf-8"))
        with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
            from app.services import etl_sync as etl
            from app.services.case_identity import CaseRef
            from app.database.connection import engine
        if engine is None or engine.dialect.name != "postgresql":
            raise CheckError("local_postgresql_required")
        from psycopg2.extensions import make_dsn
        from sqlalchemy import text

        adapter = load_adapter(Path(__file__).with_name("homology_sync.py"))
        os.environ.update({"HOMOLOGY_PATHOLOGY_REPORT_SYNC_ENABLED": "true",
                           "HOMOLOGY_DATABASE": "homology", "HOMOLOGY_SCHEMA": "graph3_homology",
                           "HOMOLOGY_SOURCE_INSTITUTE_ID": scope["source_institute_id"],
                           "HOMOLOGY_TARGET_INSTITUTE_ID": scope["target_institute_id"]})
        remote = etl.get_remote_db_url()
        route = adapter.resolve_homology_source(table_name="pathology_exam_report", remote_url=remote)
        clinical_url = make_dsn(remote, dbname="clinical_data")
        refs_by_table = {
            name: [CaseRef(scope["target_institute_id"], c["patient_id"], c["visit_id"])
                   for c in scope[key]]
            for name, key in (("pathology_exam_report", "pathology_cases"), ("death_record", "death_cases"))
        }
        emit("scope", pathology_cases=len(refs_by_table["pathology_exam_report"]),
             death_cases=len(refs_by_table["death_record"]), database_writes=0, model_calls=0)
        installed = etl._STRUCTURED_DOCUMENT_CONTENT_FIELDS.get("death_record")
        verified = tuple((label, tuple(names)) for label, names in scope["death_record_fields"])
        emit("verification_rules", pathology_adapter="bundled_production_adapter",
             death_mapping="bundled_production_fields", installed_death_mapping_matches=(installed == verified),
             modifies_installed_code=False)
        phase = "read_homology_pathology"
        path_rows = fetch_source(route.remote_url, route.schema, route.table,
                                 route.source_case_refs(refs_by_table[route.table]))
        phase = "compare_clinical_pathology"
        baseline = fetch_source(clinical_url, "public", route.table, refs_by_table[route.table])
        compare_pathology(path_rows, baseline, scope["pathology_reports"])
        rows_by_table = {route.table: route.adapt_rows(path_rows, refs_by_table[route.table])}
        phase = "read_clinical_death"
        rows_by_table["death_record"] = fetch_source(
            clinical_url, "public", "death_record", refs_by_table["death_record"]
        )
        for table, rows in rows_by_table.items():
            phase = f"preview_{table}"
            refs = refs_by_table[table]
            if table == "death_record" and (
                len(rows) != len(refs) or {CaseRef.from_mapping(r) for r in rows} != set(refs)
            ):
                raise CheckError("death_source_scope_changed")
            with engine.connect() as conn:
                conn.execute(text("SET TRANSACTION READ ONLY"))
                schema, preview = preview_upsert(etl, table, rows, refs, conn, scope["death_record_fields"])
                limits = dict(conn.execute(text(
                    "SELECT column_name, character_maximum_length FROM information_schema.columns "
                    "WHERE table_schema=:schema AND table_name=:table AND character_maximum_length IS NOT NULL"
                ), {"schema": schema, "table": table}).all())
                validate_lengths(preview.rows, limits, table)
                sql = (f'SELECT * FROM "{schema}"."{table}" WHERE institute_id=:i '
                       "AND patient_id=:p AND visit_id=:v")
                mapping = {tuple(ref): case for ref, case in zip(refs, scope[
                    "pathology_cases" if table == "pathology_exam_report" else "death_cases"
                ])}
                for ref in refs:
                    stored = list(conn.execute(text(sql), dict(zip(("i", "p", "v"), ref))).mappings())
                    planned = [r for r in preview.rows if CaseRef.from_mapping(r) == ref]
                    field = "diagnosis" if table == "pathology_exam_report" else "record_content"
                    if any(not str(r.get(field) or "").strip() for r in planned):
                        raise CheckError("projected_content_empty", table=table)
                    emit("case_preview", case=mapping[tuple(ref)]["sample"], table=table,
                         local_rows=len(stored), local_nonempty=sum(bool(str(r.get(field) or "").strip()) for r in stored),
                         projected_rows=len(planned), projected_nonempty=len(planned),
                         projected_lengths=sorted(len(r[field]) for r in planned), database_writes=0)
                emit("table_pass", table=table, source_rows=len(rows), dry_run_upsert_rows=len(preview.rows),
                     planned_case_replacements=preview.replacements, database_writes=0)
        emit("done", check_passed=True, database_writes=0, model_calls=0,
             clinical_results_saved=False, runtime_files_changed=False)
        return 0
    except Exception as exc:
        emit("error", phase=phase, error_type=type(exc).__name__,
             code=exc.code if isinstance(exc, CheckError) else None,
             details=exc.details if isinstance(exc, CheckError) else {},
             pgcode=getattr(exc, "pgcode", None), database_writes=0)
        return 1
    finally:
        output.close()


if __name__ == "__main__":
    sys.exit(main())
