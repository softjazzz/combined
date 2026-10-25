"""客户机小范围双源验收：默认只读，Apply先备份再补空/新增，不部署、不调用模型。"""

import argparse
import json
import os
from pathlib import Path
import subprocess
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.services.dual_source_case_service import as_dsn
from app.services.dual_source_write import DualSourceWriteError, encoded, run_sync, _connect


def emit(event, **data):
    print(json.dumps({"event": event, **data}, ensure_ascii=True), flush=True)


def configuration(backend):
    from dotenv import dotenv_values
    import psycopg2
    from psycopg2.extensions import make_dsn, parse_dsn
    env = dict(dotenv_values(backend / ".env"))
    local = as_dsn(env.get("DATABASE_URL", ""))
    parsed = parse_dsn(local)
    if parsed.get("host") not in {"127.0.0.1", "localhost", "::1"} or parsed.get("dbname") != "medqc":
        raise ValueError("customer_local_medqc_required")
    if env.get("REMOTE_DB_URL"):
        remote = as_dsn(env["REMOTE_DB_URL"])
    else:
        conn = _connect(local, readonly=True, factory=psycopg2.connect)
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT payload_json FROM qc.sync_config_registry WHERE namespace=%s AND config_key=%s LIMIT 1",
                            ("sync", "pg_source_config"))
                row = cur.fetchone()
                if not row:
                    raise ValueError("source_configuration_missing")
                cfg = row[0] if isinstance(row[0], dict) else json.loads(row[0])
            ref = str(cfg.get("remote_password_ref") or "env:REMOTE_DB_PASSWORD")
            if not ref.startswith("env:"):
                raise ValueError("unsupported_password_reference")
            password = env.get(ref[4:]) or cfg.get("remote_password")
            if not cfg.get("remote_host") or not cfg.get("remote_username") or not password:
                raise ValueError("source_configuration_incomplete")
            remote = make_dsn(host=cfg["remote_host"], port=cfg.get("remote_port") or 5432,
                              user=cfg["remote_username"], password=password)
        finally:
            conn.close()
    return local, {"clinical_data": make_dsn(remote, dbname="clinical_data"),
                   "homology": make_dsn(remote, dbname="homology")}, env


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--backend", required=True, type=Path)
    parser.add_argument("--scope", required=True, type=Path)
    parser.add_argument("--samples", default="C17,C18,C22")
    parser.add_argument("--tables", default="inpat_drug_order,inpat_nondrug_order,bloodtrans_record,discharge_record")
    parser.add_argument("--backup-dir", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args(argv)
    result = None
    phase = "configuration"
    try:
        scope = json.loads(args.scope.read_text(encoding="utf-8-sig"))
        aliases = tuple(dict.fromkeys(value.strip() for value in args.samples.split(",") if value.strip()))
        if not 1 <= len(aliases) <= 3:
            raise ValueError("acceptance_scope_maximum_three_cases")
        cases = [case for case in scope["cases"] if case["sample"] in aliases]
        if len(cases) != len(aliases):
            raise ValueError("unknown_sample_alias")
        tables = tuple(dict.fromkeys(value.strip() for value in args.tables.split(",") if value.strip()))
        from app.services.dual_source_sync import TABLE_KEYS
        if not tables or set(tables) - set(TABLE_KEYS):
            raise ValueError("unsupported_acceptance_table")
        local, sources, env = configuration(args.backend.resolve())
        approvals = {}
        for item in scope.get("reviewed_documents", []):
            if item["sample"] in aliases and item["table"] in tables:
                approvals.setdefault((item["sample"], item["table"]), {})[tuple(item["key"])] = item["source_digest"]
        emit("scope", cases=len(cases), tables=list(tables), mode="apply" if args.apply else "preview",
             model_calls=0, qc_tasks_started=0, changes_installed_code=False)
        phase = "sync"
        result = run_sync(local_dsn=local, source_dsns=sources, cases=cases, tables=tables,
                          source_institutes=scope["source_institutes"], backup_dir=args.backup_dir,
                          report_dir=args.output_dir, apply=args.apply, approved_records=approvals,
                          target_schema="cdm" if env.get("DB_SCHEMA_MODE", "split") == "split" else "public",
                          progress=lambda value: emit("plan", **value))
        report = result["report"]
        if args.apply:
            phase = "bundle_refresh"
            child = Path(__file__).with_name("verify_dual_source_bundles.py")
            request = {"backend": str(args.backend.resolve()), "cases": cases, "tables": tables}
            completed = subprocess.run([sys.executable, "-X", "utf8", str(child)], input=json.dumps(request),
                                       text=True, encoding="utf-8", errors="replace", capture_output=True,
                                       cwd=args.backend.resolve(), timeout=180,
                                       env={**os.environ, "PYTHONIOENCODING": "utf-8", "PYTHONUTF8": "1"})
            lines = [line for line in completed.stdout.splitlines() if line.startswith('{"event": "bundle_result"')]
            bundle = json.loads(lines[-1]) if lines else {"ok": False, "code": "bundle_verification_no_result"}
            report["bundle_refresh"] = bundle
            report["bundle_verified"] = completed.returncode == 0 and bundle.get("ok") is True
            Path(report["report_path"]).write_bytes(encoded(report))
            if not report["bundle_verified"]:
                raise DualSourceWriteError("data_committed_bundle_verification_failed", report_path=report["report_path"], data_committed=True)
        emit("done", data_committed=report["data_committed"], inserts=report["inserts"],
             updated_rows=report["updated_rows"], filled_fields=report["filled_fields"],
             pending_records=report["pending_records"], report=report["report_path"],
             quarantined_rows=report["quarantined_rows"], review_index=report["review_index_path"],
             backup=report.get("backup_path"), bundle_verified=report.get("bundle_verified", False),
             database_writes=0 if not args.apply else report["inserts"] + report["updated_rows"],
             model_calls=0, qc_tasks_started=0)
        return 0
    except Exception as exc:
        if result:
            result["report"].update(phase=phase, error_type=type(exc).__name__)
            Path(result["report"]["report_path"]).write_bytes(encoded(result["report"]))
        emit("error", phase=phase, error_type=type(exc).__name__,
             code=exc.code if isinstance(exc, DualSourceWriteError) else "configuration_or_acceptance_failed",
             data_committed=exc.data_committed if isinstance(exc, DualSourceWriteError) else bool(result and result["report"]["data_committed"]),
             report=exc.report_path if isinstance(exc, DualSourceWriteError) else result["report"]["report_path"] if result else None,
             model_calls=0, qc_tasks_started=0)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
