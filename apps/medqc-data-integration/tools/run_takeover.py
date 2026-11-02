"""部署身份的一次性初始化/接管/核对。口令只用独立 PGPASSFILE。"""

from __future__ import annotations

import argparse
import json
import re
import sys
from contextlib import suppress
from pathlib import Path

from medqc_ingest.config import PassfilePostgresSettings
from medqc_ingest.domain import INTERFACE_REGISTRY, ErrorKind, IngestError
from medqc_ingest.repositories.postgres import _connect, _ident, _read_cdm_contract
from medqc_ingest.takeover import import_legacy, validate_target_database, verify_takeover
from medqc_ingest.verification import ACCEPTANCE_DATABASE

ROOT = Path(__file__).resolve().parents[1]


def initialize(connection, database: str, runtime_user: str) -> None:
    validate_target_database(database)
    with connection.cursor() as cursor:
        cursor.execute("SELECT current_database()")
        if cursor.fetchone()[0] != database:
            raise IngestError(ErrorKind.CONFIGURATION, "init_database")
        cursor.execute(
            "SELECT count(*) FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace "
            "WHERE n.nspname NOT LIKE 'pg_%' AND n.nspname<>'information_schema' "
            "AND c.relkind IN ('r','p','v','m','S')"
        )
        if cursor.fetchone()[0]:
            raise IngestError(ErrorKind.PUBLISH_CONTRACT, "init_database_not_empty")
        cursor.execute(
            "SELECT pg_get_userbyid(datdba) FROM pg_database WHERE datname=current_database()"
        )
        owner = str(cursor.fetchone()[0])
        cursor.execute(f"SET LOCAL ROLE {_ident(owner)}")
        for name in (
            "001_ingest_contract.sql",
            "002_major_document_contracts.sql",
            "003_daily_record_datetime_contract.sql",
            "004_orders_lab_exam_and_versions.sql",
            "005_takeover_audit.sql",
        ):
            sql = (ROOT / "migrations" / name).read_text(encoding="utf-8")
            if not sql.rstrip().endswith("COMMIT;"):
                raise IngestError(ErrorKind.PUBLISH_CONTRACT, "init_migration_wrapper")
            body = re.sub(r"(?m)^BEGIN;\s*$", "", sql, count=1).rstrip()
            cursor.execute(body[: -len("COMMIT;")])
        user = _ident(runtime_user)
        cursor.execute(f"GRANT CONNECT ON DATABASE {_ident(database)} TO {user}")
        cursor.execute(f"GRANT USAGE ON SCHEMA cache_raw,sync_ops,takeover_archive TO {user}")
        cursor.execute(
            f"GRANT SELECT ON ALL TABLES IN SCHEMA cache_raw,sync_ops,takeover_archive TO {user}"
        )
        for table in (
            "cache_raw.source_record",
            "sync_ops.source_schema",
            "sync_ops.sync_batch",
            "sync_ops.sync_checkpoint",
            "sync_ops.publish_batch",
            "sync_ops.publish_lineage",
        ):
            cursor.execute(f"GRANT INSERT,UPDATE ON {table} TO {user}")
        cursor.execute(f"GRANT INSERT ON cache_raw.source_record_version TO {user}")
        cursor.execute(
            f"GRANT USAGE,SELECT ON ALL SEQUENCES IN SCHEMA cache_raw,sync_ops TO {user}"
        )
    connection.commit()


def grant_cdm(connection, database: str, runtime_user: str) -> None:
    validate_target_database(database, "cdm")
    with connection.cursor() as cursor:
        cursor.execute("SELECT current_database()")
        if cursor.fetchone()[0] != database:
            raise IngestError(ErrorKind.CONFIGURATION, "grant_cdm_database")
        for spec in INTERFACE_REGISTRY.values():
            target = spec.publish
            assert target is not None
            columns, primary_key = _read_cdm_contract(connection, target)
            if tuple(primary_key) != target.primary_key or set(target.required_columns) - set(
                columns
            ):
                raise IngestError(ErrorKind.PUBLISH_CONTRACT, "grant_cdm_contract")
        user = _ident(runtime_user)
        cursor.execute(f"GRANT CONNECT ON DATABASE {_ident(database)} TO {user}")
        cursor.execute(f"GRANT USAGE ON SCHEMA cdm TO {user}")
        for spec in INTERFACE_REGISTRY.values():
            assert spec.publish is not None
            table = f"{_ident(spec.publish.schema)}.{_ident(spec.publish.table)}"
            cursor.execute(f"GRANT SELECT,INSERT,UPDATE ON TABLE {table} TO {user}")
    connection.commit()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=("init", "grant-cdm", "import", "verify"))
    parser.add_argument("--database", required=True)
    parser.add_argument("--user", required=True)
    parser.add_argument("--passfile", required=True, type=Path)
    parser.add_argument("--runtime-user", default="medqc_sync")
    parser.add_argument("--source-user", default="medqc_sync")
    parser.add_argument("--source-passfile", type=Path)
    parser.add_argument("--port", default=5432, type=int)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    connections = []
    try:
        validate_target_database(args.database, "cdm" if args.mode == "grant-cdm" else "ingest")
        setting = PassfilePostgresSettings(
            "127.0.0.1", args.port, args.database, args.user, args.passfile
        )
        target = _connect(
            setting,
            ErrorKind.INGEST_CONNECT,
            "takeover_target_connect",
            readonly=args.mode == "verify",
        )
        connections.append(target)
        if args.mode == "init":
            initialize(target, args.database, args.runtime_user)
            report = {"status": "initialized"}
        elif args.mode == "grant-cdm":
            grant_cdm(target, args.database, args.runtime_user)
            report = {"status": "granted_13_targets"}
        elif args.mode == "import":
            if args.source_passfile is None:
                raise IngestError(ErrorKind.CONFIGURATION, "source_passfile_required")
            source_settings = PassfilePostgresSettings(
                "127.0.0.1", args.port, ACCEPTANCE_DATABASE, args.source_user, args.source_passfile
            )
            source = _connect(
                source_settings, ErrorKind.INGEST_CONNECT, "takeover_source_connect", readonly=True
            )
            connections.append(source)
            report = import_legacy(source, target, args.database)
        else:
            report = verify_takeover(target, args.database)
        if args.output is not None:
            args.output.write_text(
                json.dumps(report, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
                newline="\n",
            )
        print(f"{args.mode} succeeded")
        return 0
    except IngestError as exc:
        print(f"failed kind={exc.kind} location={exc.location}", file=sys.stderr)
        return 1
    except Exception:
        print("failed kind=unexpected_error location=takeover_tool", file=sys.stderr)
        return 1
    finally:
        for connection in connections:
            with suppress(Exception):
                connection.close()


if __name__ == "__main__":
    raise SystemExit(main())
