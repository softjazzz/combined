"""只读核对现有克隆库；不导入后端 .env，不连接 Caché，不执行迁移。"""

from __future__ import annotations

import argparse
import getpass
import importlib
import json
import sys
from contextlib import suppress
from pathlib import Path

from medqc_ingest.domain import IngestError
from medqc_ingest.verification import ACCEPTANCE_DATABASE, verify_existing_cdm


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="127.0.0.1", choices=("127.0.0.1", "localhost", "::1"))
    parser.add_argument("--port", type=int, default=5432)
    parser.add_argument("--database", required=True, choices=(ACCEPTANCE_DATABASE,))
    parser.add_argument("--user", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    if args.user in {"postgres", "medqc_owner"}:
        print("failed kind=configuration_error location=readonly_login_required", file=sys.stderr)
        return 1
    connection = None
    try:
        try:
            driver = importlib.import_module("psycopg2")
        except ImportError:
            driver = importlib.import_module("psycopg")
        password = getpass.getpass("验收库只读身份密码: ")
        connection = driver.connect(
            host=args.host,
            port=args.port,
            dbname=args.database,
            user=args.user,
            password=password,
            connect_timeout=10,
            options="-c default_transaction_read_only=on",
            application_name="medqc_readonly_projection_verification",
        )
        password = ""
        results = verify_existing_cdm(connection)
        report = {
            "verification_kind": "readonly_existing_raw_cdm_comparison",
            "contains_phi": False,
            "contains_raw_values": False,
            "source_extracted": False,
            "database_written": False,
            "formal_publish_gate_bypassed": False,
            "interfaces": results,
        }
        args.output.write_text(
            json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n"
        )
        for row in results:
            print(
                f"{row['interface']} status={row['status']} rows={row['rows_compared']} "
                f"equal={row['rows_all_fields_equal']} "
                f"blank_hash={row['raw_schema_hash_blank_rows']}"
            )
        return 0 if all(row["status"] == "verified" for row in results) else 1
    except IngestError as exc:
        print(f"failed kind={exc.kind} location={exc.location}", file=sys.stderr)
        return 1
    except Exception:
        print(
            "failed kind=unexpected_error location=readonly_projection_verification",
            file=sys.stderr,
        )
        return 1
    finally:
        if connection is not None:
            with suppress(Exception):
                connection.close()


if __name__ == "__main__":
    raise SystemExit(main())
