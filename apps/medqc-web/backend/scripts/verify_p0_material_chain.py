"""只读五类材料固定验收；不创建 Bundle、不调用模型、不更新质控任务。"""

from __future__ import annotations

import argparse
from contextlib import ExitStack
from datetime import datetime, timezone
import importlib.util
import hashlib
import json
import logging
import os
from pathlib import Path
import sys
import traceback
import zipfile


def emit(event, **values):
    print(json.dumps({"event": event, **values}, ensure_ascii=True, default=str), flush=True)


def read_only(dsn):
    import psycopg2
    connection = psycopg2.connect(dsn, connect_timeout=5, options="-c default_transaction_read_only=on -c statement_timeout=60000 -c lock_timeout=3000")
    connection.set_session(readonly=True, isolation_level="REPEATABLE READ")
    return connection


def source_dsns(connection, cfg):
    from psycopg2.extensions import make_dsn
    url = str(cfg.get("REMOTE_DB_URL") or "").replace("postgresql+psycopg2://", "postgresql://")
    if not url:
        with connection.cursor() as cursor:
            cursor.execute("SELECT payload_json FROM qc.sync_config_registry WHERE namespace='sync' AND config_key='pg_source_config'")
            row = cursor.fetchone()
        payload = json.loads(row[0]) if row and isinstance(row[0], str) else row[0] if row else {}
        reference = str(payload.get("remote_password_ref") or "env:REMOTE_DB_PASSWORD")
        if not reference.startswith("env:"):
            raise ValueError("unsupported_source_secret_reference")
        password = cfg.get(reference[4:]) or payload.get("remote_password")
        if not payload.get("remote_host") or not password:
            raise ValueError("source_configuration_missing")
        url = make_dsn(host=payload["remote_host"], port=payload.get("remote_port") or 5432,
                       user=payload["remote_username"], password=password, dbname="clinical_data")
    return {source: make_dsn(url, dbname=source) for source in ("clinical_data", "homology")}


def table_rows(connection, schema, table, cases, *, exact):
    from psycopg2 import sql
    from psycopg2.extras import RealDictCursor
    with connection.cursor() as cursor:
        cursor.execute("SELECT column_name FROM information_schema.columns WHERE table_schema=%s AND table_name=%s", (schema, table))
        columns = {row[0] for row in cursor.fetchall()}
    fields = ("institute_id", "patient_id", "visit_id") if exact else ("patient_id", "visit_id")
    if not set(fields).issubset(columns):
        return None
    predicate = sql.SQL(" OR ").join(sql.SQL("(" + " AND ".join("{}=%s" for _ in fields) + ")").format(*(sql.Identifier(field) for field in fields)) for _ in cases)
    statement = sql.SQL("SELECT * FROM {}.{} WHERE {} LIMIT 100001").format(sql.Identifier(schema), sql.Identifier(table), predicate)
    with connection.cursor(cursor_factory=RealDictCursor) as cursor:
        cursor.execute(statement, [case[field] for case in cases for field in fields])
        rows = [dict(row) for row in cursor.fetchall()]
    if len(rows) > 100000:
        raise ValueError("source_row_limit_exceeded")
    return rows


def bundle_documents(connection, table, case):
    from psycopg2 import sql
    with connection.cursor() as cursor:
        cursor.execute("SELECT column_name FROM information_schema.columns WHERE table_schema='public' AND table_name=%s", (table,))
        columns = {row[0] for row in cursor.fetchall()}
        if "source_documents" in columns:
            expression = sql.SQL("source_documents")
        elif "structured_context" in columns:
            expression = sql.SQL("structured_context::jsonb->'document_inventory'")
        else:
            return None
        cursor.execute(sql.SQL("SELECT {}, structured_context FROM public.{} WHERE institute_id=%s AND patient_id=%s AND visit_id=%s").format(expression, sql.Identifier(table)), [case[k] for k in ("institute_id", "patient_id", "visit_id")])
        values = cursor.fetchall()
    if len(values) != 1:
        return None
    documents = json.loads(values[0][0]) if isinstance(values[0][0], str) else values[0][0]
    context = json.loads(values[0][1]) if isinstance(values[0][1], str) else values[0][1] or {}
    projection = context.get("scene_projection") or context.get("domain_projection") or {}
    return (documents, projection) if isinstance(documents, list) and all(isinstance(row, dict) for row in documents) else None


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--backend", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--sample-set", default="1022")
    parser.add_argument("--source-export", type=Path)
    parser.add_argument("--env-file", type=Path)
    args = parser.parse_args(argv)
    backend = args.backend.resolve()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    report_path = args.output_dir / ("p0-material-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ") + "-private.json")
    report = {"passed": False, "database_writes": 0, "model_calls": 0, "qc_tasks_started": 0,
              "captured_at_utc": datetime.now(timezone.utc).isoformat(),
              "source_mode": "frozen_export" if args.source_export else "live_readonly", "checks": []}
    phase = "configuration"
    logging.disable(logging.CRITICAL)
    try:
        from dotenv import dotenv_values
        from psycopg2.extensions import parse_dsn
        cfg = dotenv_values(args.env_file or backend / ".env")
        for key, value in cfg.items():
            if value is not None:
                os.environ[key] = value
        dsn = str(cfg.get("DATABASE_URL") or "").replace("postgresql+psycopg2://", "postgresql://")
        params = parse_dsn(dsn)
        if params.get("host") not in ("localhost", "127.0.0.1", "::1") or params.get("dbname") != "medqc":
            raise ValueError("local_medqc_required")
        os.environ.update(DATABASE_URL=dsn, DB_SCHEMA_MODE="split", DB_SEARCH_PATH=str(cfg.get("DB_SEARCH_PATH") or "public,qc,sys,cdm,legacy"))
        sys.path.insert(0, str(backend))
        from sqlalchemy import event
        from sqlalchemy.engine import Engine

        @event.listens_for(Engine, "do_connect")
        def readonly_engine(dialect, record, cargs, cparams):
            if cparams.get("host") not in ("localhost", "127.0.0.1", "::1") or cparams.get("dbname", cparams.get("database")) != "medqc":
                raise ValueError("unexpected_rule_reader_database")
            cparams["options"] = "-c default_transaction_read_only=on -c statement_timeout=60000 -c search_path=public,qc,sys,cdm,legacy"

        import httpx
        def no_http(*a, **kw):
            raise RuntimeError("network_model_calls_forbidden")
        httpx.Client.send = no_http
        httpx.AsyncClient.send = no_http
        owner_file = Path(__file__).with_name("material_chain_acceptance.py")
        if owner_file.exists():
            name = "app.services.qc_workspace.material_chain_acceptance"
            spec = importlib.util.spec_from_file_location(name, owner_file)
            module = importlib.util.module_from_spec(spec)
            sys.modules[name] = module
            spec.loader.exec_module(module)
        from app.services.qc_workspace.material_chain_acceptance import SPECS, check_table_chain, summarize_checks
        from app.services import dual_source_sync as sync
        from app.services.luxian_0609 import source_evidence_reader as reader
        with ExitStack() as stack:
            local = read_only(dsn)
            stack.callback(local.close)
            phase = "sample_scope"
            with local.cursor() as cursor:
                cursor.execute("SELECT i.row_no,i.matched_institute_id,i.matched_patient_id,i.matched_visit_id FROM qc.manual_problem_sample_pool_items i JOIN qc.manual_problem_sample_pools p ON p.id=i.pool_id WHERE p.name=%s ORDER BY i.row_no", (args.sample_set,))
                cases = [dict(zip(("sample", "institute_id", "patient_id", "visit_id"), (f"C{row[0]:02}", *row[1:]))) for row in cursor.fetchall()]
            if len(cases) != 27 or len({tuple(case[k] for k in sync.IDENTITY_FIELDS) for case in cases}) != 27 or any(not all(case[k] for k in sync.IDENTITY_FIELDS) for case in cases):
                raise ValueError("requires_27_unique_complete_cases")
            report["scope_digest"] = hashlib.sha256(json.dumps(cases, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
            phase = "source_read"
            source_data = {}
            if args.source_export:
                with zipfile.ZipFile(args.source_export) as archive:
                    export_cases = json.loads(archive.read("case_refs.json"))
                    if {(r["sample"], *(r[k] for k in sync.IDENTITY_FIELDS)) for r in export_cases} != {(r["sample"], *(r[k] for k in sync.IDENTITY_FIELDS)) for r in cases}:
                        raise ValueError("source_export_case_scope_mismatch")
                    for source in ("clinical_data", "homology"):
                        for item in SPECS:
                            name = f"sources/{source}/{item.table}.jsonl"
                            source_data[source, item.table] = [json.loads(line) for line in archive.read(name).decode("utf8").splitlines() if line.strip()] if name in archive.namelist() else None
            else:
                for source, url in source_dsns(local, cfg).items():
                    connection = read_only(url)
                    stack.callback(connection.close)
                    schema = "public" if source == "clinical_data" else str(cfg.get("HOMOLOGY_SCHEMA") or "graph3_homology")
                    for item in SPECS:
                        source_data[source, item.table] = table_rows(connection, schema, item.table, cases, exact=False)
            local_data = {item.table: table_rows(local, "cdm", item.table, cases, exact=True) for item in SPECS}
            for case in cases:
                phase = "layers:" + case["sample"]
                stored = {name: bundle_documents(local, table, case) for name, table in {
                    "final": "final_record_bundle", "course": "course_domain_bundle", "surgery": "surgery_domain_bundle",
                    "terminal": "terminal_domain_bundle", "consult_discussion": "consult_discussion_domain_bundle",
                }.items()}
                bundles = {name: value[0] if value else None for name, value in stored.items()}
                projections = {name: value[1] if value else {} for name, value in stored.items()}
                coordinates = {key: case[key] for key in sync.IDENTITY_FIELDS}
                def belongs(row):
                    return all(str(row.get(key) or "") == case[key] for key in ("patient_id", "visit_id"))
                for item in SPECS:
                    snapshots = []
                    for source in ("clinical_data", "homology"):
                        rows = source_data[source, item.table]
                        snapshots.append(sync.SourceSnapshot(source, tuple(row for row in (rows or []) if belongs(row)), status="ok" if rows is not None else "table_unavailable"))
                    rule_rows = {}
                    for mode in ("native", "snapshot"):
                        try:
                            method = reader.read_luxian_0609_native_source_rows if mode == "native" else reader.read_luxian_0609_snapshot_source_rows
                            result = method(source_key=item.table, source_schema="cdm", **coordinates)
                            rule_rows[mode] = list(result if mode == "native" else result.rows)
                        except Exception as exc:
                            rule_rows[mode] = None
                            emit("rule_reader_unavailable", sample=case["sample"], table=item.table, mode=mode, error_type=type(exc).__name__)
                    check = check_table_chain(spec=item, sample=case["sample"], case=case, clinical=snapshots[0], homology=snapshots[1],
                        local_rows=[row for row in (local_data[item.table] or []) if belongs(row) and str(row.get("institute_id")) == case["institute_id"]],
                        source_institutes={"clinical_data": case["institute_id"], "homology": str(cfg.get("HOMOLOGY_SOURCE_INSTITUTE_ID") or "机构号"), "local": case["institute_id"]},
                        bundles=bundles, rules=rule_rows, projections=projections)
                    report["checks"].append(check)
                emit("case_checked", sample=case["sample"], database_writes=0, model_calls=0)
            report.update(summarize_checks(report["checks"], cases=len(cases)))
    except Exception as exc:
        report.update(error_phase=phase, error_type=type(exc).__name__)
        report_path.with_suffix(".error-private.txt").write_text(traceback.format_exc(), encoding="utf8")
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2, default=str), encoding="utf8")
    emit("material_chain_done", **{key: value for key, value in report.items() if key != "checks"}, report=str(report_path))
    return 0 if report["passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
