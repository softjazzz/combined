"""已完成迁入/发布后的只读续跑闸门；不导入、不授权、不重做故障注入。"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from diagnose_takeover_import import SOURCE, safe_exception_chain, verify_frozen_package
from run_configured_daily import read_runtime
from takeover_resume_preflight import validate_plan

from medqc_ingest import __version__
from medqc_ingest.config import PassfilePostgresSettings
from medqc_ingest.domain import INTERFACE_REGISTRY, ErrorKind
from medqc_ingest.repositories.postgres import _connect
from medqc_ingest.takeover import EXPECTED_COUNTS

REPORTS = (
    "resume-preflight.json",
    "takeover-import.json",
    "takeover-verify.json",
    "service-acceptance.json",
    "takeover-verify-after.json",
    "takeover-import-deployment-source-diagnostic.json",
)
PROTECTED_TABLES = (
    "sync_ops.sync_checkpoint",
    "takeover_archive.source_catalog",
    "takeover_archive.source_row",
    "sync_ops.takeover_marker",
    "sync_ops.takeover_batch_map",
)


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def completed_hashes(run: Path) -> dict[str, str]:
    return {
        name: hashlib.sha256((run / "reports" / name).read_bytes()).hexdigest() for name in REPORTS
    }


def validate_completed(documents: dict) -> None:
    if documents["resume-preflight.json"].get("status") != "passed":
        raise RuntimeError("prior_preflight_not_passed")
    if documents["takeover-import.json"].get("raw_counts") != EXPECTED_COUNTS:
        raise RuntimeError("prior_import_counts")
    observed = documents["takeover-import-deployment-source-diagnostic.json"]
    if observed.get("import_succeeded") is not True:
        raise RuntimeError("prior_import_not_committed")
    for name in ("takeover-verify.json", "takeover-verify-after.json"):
        report = documents[name]
        if (
            report.get("status") != "verified"
            or report.get("raw_rows_equal") != 87201
            or report.get("history_rows_equal") != 87201
            or report.get("archives_verified") != 5
        ):
            raise RuntimeError("prior_verification_not_passed")
    service = documents["service-acceptance.json"]
    rollback = service.get("rollback_recovery", {})
    if (
        rollback.get("rollback") != "verified"
        or rollback.get("failure_audit") != "verified"
        or rollback.get("recovery") != "succeeded"
        or rollback.get("checkpoint_advanced") is not False
    ):
        raise RuntimeError("prior_recovery_not_passed")
    second = [row for row in service.get("publish_rounds", []) if row.get("round") == 2]
    fields = service.get("field_equality", [])
    if (
        len(second) != 13
        or {row.get("interface") for row in second} != set(INTERFACE_REGISTRY)
        or any(row.get("changed") != 0 for row in second)
        or len(fields) != 13
        or {row.get("interface") for row in fields} != set(INTERFACE_REGISTRY)
        or any(
            row.get("rows") != EXPECTED_COUNTS[row["interface"]]
            or row.get("all_fields_equal") != row.get("rows")
            for row in fields
        )
    ):
        raise RuntimeError("prior_publication_not_passed")


def validate_runtime(values: dict, plan: dict, run: Path, port: int) -> None:
    if (
        values.get("MEDQC_SOURCE_ADAPTER") != "odbc"
        or values.get("MEDQC_INGEST_PG_DATABASE") != plan["ingest"]
        or values.get("MEDQC_CDM_PG_DATABASE") != plan["cdm"]
        or any(values.get(f"MEDQC_{kind}_PG_USER") != "medqc_sync" for kind in ("INGEST", "CDM"))
        or any(values.get(f"MEDQC_{kind}_PG_PORT") != str(port) for kind in ("INGEST", "CDM"))
        or not Path(values.get("MEDQC_PG_PASSFILE", "")).samefile(run / "secrets/runtime.pgpass")
        or not Path(values.get("MEDQC_CACHE_PASSWORD_FILE", "")).samefile(
            run / "secrets/cache-password"
        )
    ):
        raise RuntimeError("source_resume_runtime_scope")


def verify_live_state(plan: dict, run: Path, user: str, port: int) -> None:
    for kind in ("ingest", "cdm", "restore_ingest", "restore_cdm"):
        restoring = kind.startswith("restore")
        settings = PassfilePostgresSettings(
            "127.0.0.1",
            port,
            plan[kind],
            user if restoring else "medqc_sync",
            run / "secrets" / ("deployment-admin.pgpass" if restoring else "runtime.pgpass"),
        )
        connection = _connect(
            settings, ErrorKind.INGEST_CONNECT, "source_resume_guard", readonly=True
        )
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT current_database(),current_setting('transaction_read_only')")
                if cursor.fetchone() != (plan[kind], "on"):
                    raise RuntimeError("source_resume_identity")
                if restoring:
                    cursor.execute(
                        "SELECT count(*) FROM pg_class c "
                        "JOIN pg_namespace n ON n.oid=c.relnamespace "
                        "WHERE n.nspname NOT LIKE 'pg_%' AND n.nspname<>'information_schema' "
                        "AND c.relkind IN ('r','p','v','m','S')"
                    )
                    if cursor.fetchone()[0]:
                        raise RuntimeError("restore_database_not_empty")
                elif kind == "ingest":
                    cursor.execute(
                        "SELECT interface_name,count(*) FROM cache_raw.source_record GROUP BY 1"
                    )
                    if dict(cursor.fetchall()) != EXPECTED_COUNTS:
                        raise RuntimeError("source_resume_raw_changed")
                    cursor.execute("SELECT count(*) FROM cache_raw.source_record_version")
                    if cursor.fetchone()[0] != 87201:
                        raise RuntimeError("source_resume_history_changed")
                    cursor.execute("SELECT count(*) FROM sync_ops.sync_checkpoint")
                    if cursor.fetchone()[0]:
                        raise RuntimeError("unexpected_checkpoint_before_replay")
                    cursor.execute(
                        "SELECT count(*) FROM sync_ops.sync_batch WHERE status='running'"
                    )
                    if cursor.fetchone()[0]:
                        raise RuntimeError("source_resume_running_batch")
                    cursor.execute(
                        "SELECT source_database FROM sync_ops.takeover_marker WHERE marker_id=1"
                    )
                    if cursor.fetchone() != (SOURCE,):
                        raise RuntimeError("source_resume_marker_missing")
                else:
                    for spec in INTERFACE_REGISTRY.values():
                        cursor.execute(f"SELECT count(*) FROM {spec.publish_target}")
                        if cursor.fetchone()[0] != EXPECTED_COUNTS[spec.name]:
                            raise RuntimeError("source_resume_cdm_changed")
        finally:
            connection.close()


def check_preserved(run: Path) -> None:
    saved = read_json(run / "reports/source-validation-preflight-0.3.2.json")
    if saved["completed_reports_sha256"] != completed_hashes(run):
        raise RuntimeError("completed_report_modified")
    if saved["runtime_sha256"] != hashlib.sha256((run / "runtime.json").read_bytes()).hexdigest():
        raise RuntimeError("runtime_config_modified")
    before = read_json(run / "reports/ingest-before-live-0.3.2.json")["tables"]
    after = read_json(run / "reports/ingest-before-backup.json")["tables"]
    if any(
        before.get(table) is None or before[table] != after.get(table) for table in PROTECTED_TABLES
    ):
        raise RuntimeError("archive_or_checkpoint_modified")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=("preflight", "preserve"))
    parser.add_argument("--run-root", required=True, type=Path)
    parser.add_argument("--original-package-root", type=Path)
    parser.add_argument("--user", default="postgres")
    parser.add_argument("--port", default=5432, type=int)
    args = parser.parse_args(argv)
    run = args.run_root.resolve()
    previous = {key: os.environ.get(key) for key in ("PGPASSWORD", "MEDQC_PG_DRIVER")}
    try:
        if __version__ != "0.3.2":
            raise RuntimeError("wrong_runtime_version")
        os.environ.pop("PGPASSWORD", None)
        os.environ["MEDQC_PG_DRIVER"] = "psycopg2"
        if args.mode == "preflight":
            if args.original_package_root is None:
                raise RuntimeError("original_package_required")
            verify_frozen_package(args.original_package_root.resolve())
            plan = read_json(run / "reports/database-plan.json")
            validate_plan(plan)
            documents = {name: read_json(run / "reports" / name) for name in REPORTS}
            validate_completed(documents)
            values = read_runtime(run / "runtime.json")
            validate_runtime(values, plan, run, args.port)
            verify_live_state(plan, run, args.user, args.port)
            report = {
                "completed_reports_sha256": completed_hashes(run),
                "runtime_sha256": hashlib.sha256((run / "runtime.json").read_bytes()).hexdigest(),
            }
        else:
            check_preserved(run)
            report = {
                "completed_reports_unchanged": True,
                "runtime_unchanged": True,
                "archive_unchanged": True,
                "checkpoint_unchanged": True,
            }
        report.update(
            status="passed", database_writes=False, contains_phi=False, contains_raw_values=False
        )
        with (run / "reports" / f"source-validation-{args.mode}-0.3.2.json").open(
            "x", encoding="utf-8", newline="\n"
        ) as output:
            output.write(json.dumps(report, indent=2) + "\n")
        print(f"source-validation {args.mode} passed")
        return 0
    except Exception as error:
        print(
            json.dumps(
                {
                    "status": "failed",
                    "exception_chain": safe_exception_chain(
                        error, Path(__file__).resolve().parents[1]
                    ),
                }
            )
        )
        return 1
    finally:
        for key, value in previous.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


if __name__ == "__main__":
    raise SystemExit(main())
