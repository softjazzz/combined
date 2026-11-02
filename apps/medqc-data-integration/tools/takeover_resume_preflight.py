"""原失败现场的续跑闸门；所有数据库连接只读，不创建或授权任何对象。"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path

from diagnose_takeover_import import SOURCE, safe_exception_chain, verify_frozen_package


def validate_plan(plan: dict) -> None:
    stamp = str(plan.get("ingest", "")).removeprefix("medqc_ingest_takeover_")
    if (
        not re.fullmatch(r"[0-9]{14}", stamp)
        or plan.get("source") != SOURCE
        or plan.get("cdm") != f"medqc_cdm_takeover_{stamp}"
        or plan.get("restore_ingest") != f"medqc_restore_takeover_{stamp}"
        or not re.fullmatch(r"medqc_restore_takeover_[0-9]{14}", plan.get("restore_cdm", ""))
        or len({plan.get(key) for key in ("ingest", "cdm", "restore_ingest", "restore_cdm")}) != 4
    ):
        raise RuntimeError("resume_database_plan")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--package-root", required=True, type=Path)
    parser.add_argument("--run-root", required=True, type=Path)
    parser.add_argument("--user", default="postgres")
    parser.add_argument("--port", default=5432, type=int)
    args = parser.parse_args(argv)
    root, run = args.package_root.resolve(), args.run_root.resolve()
    connections = []
    prior = {name: os.environ.get(name) for name in ("PGPASSWORD", "MEDQC_PG_DRIVER")}
    report = {"database_writes": False, "source_writes": False, "contains_phi": False}
    try:
        verify_frozen_package(root)
        plan = json.loads((run / "reports/database-plan.json").read_text(encoding="utf-8"))
        validate_plan(plan)
        os.environ.pop("PGPASSWORD", None)
        os.environ["MEDQC_PG_DRIVER"] = "psycopg2"
        sys.path.insert(0, str(root / "src"))
        from medqc_ingest.config import PassfilePostgresSettings
        from medqc_ingest.domain import ErrorKind
        from medqc_ingest.repositories.postgres import _connect
        from medqc_ingest.takeover import _preflight_source

        for kind in ("source", "ingest", "cdm", "restore_ingest", "restore_cdm"):
            report["phase"] = kind
            settings = PassfilePostgresSettings(
                "127.0.0.1",
                args.port,
                plan[kind],
                args.user,
                run / "secrets/deployment-admin.pgpass",
            )
            connection = _connect(
                settings, ErrorKind.INGEST_CONNECT, "resume_preflight", readonly=True
            )
            connections.append(connection)
            if kind == "source":
                _preflight_source(connection)
            else:
                with connection.cursor() as cursor:
                    cursor.execute(
                        "SELECT current_database(),current_setting('transaction_read_only')"
                    )
                    if cursor.fetchone() != (plan[kind], "on"):
                        raise RuntimeError("resume_identity")
                    if kind.startswith("restore"):
                        cursor.execute(
                            "SELECT count(*) FROM pg_class c "
                            "JOIN pg_namespace n ON n.oid=c.relnamespace "
                            "WHERE n.nspname NOT LIKE 'pg_%' AND n.nspname<>'information_schema' "
                            "AND c.relkind IN ('r','p','v','m','S')"
                        )
                        if cursor.fetchone()[0]:
                            raise RuntimeError("resume_restore_not_empty")
                    elif kind == "ingest":
                        for table in (
                            "cache_raw.source_record",
                            "cache_raw.source_record_version",
                            "sync_ops.sync_batch",
                            "sync_ops.sync_checkpoint",
                            "sync_ops.publish_batch",
                            "sync_ops.publish_lineage",
                            "sync_ops.takeover_marker",
                            "sync_ops.takeover_batch_map",
                            "takeover_archive.source_row",
                            "takeover_archive.source_catalog",
                        ):
                            cursor.execute(f"SELECT count(*) FROM {table}")
                            if cursor.fetchone()[0]:
                                raise RuntimeError("resume_ingest_not_empty")
                    else:
                        for table, expected in (
                            ("cache_raw.source_record", 87201),
                            ("sync_ops.sync_batch", 78),
                        ):
                            cursor.execute(f"SELECT count(*) FROM {table}")
                            if cursor.fetchone()[0] != expected:
                                raise RuntimeError("resume_cdm_clone_changed")
        report["status"] = "passed"
        with (run / "reports/resume-preflight.json").open(
            "x", encoding="utf-8", newline="\n"
        ) as output:
            output.write(json.dumps(report, indent=2) + "\n")
        print("RESUME_PREFLIGHT_PASS; database connections were read-only")
        return 0
    except Exception as error:
        report.update(status="failed", exception_chain=safe_exception_chain(error, root))
        print(json.dumps(report))
        return 1
    finally:
        for connection in connections:
            connection.close()
        for name, value in prior.items():
            if value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = value


if __name__ == "__main__":
    raise SystemExit(main())
