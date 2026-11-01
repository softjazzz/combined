"""只在显式命名的新空控制库建表；不创建全局角色，不读取业务配置。"""

from __future__ import annotations

import argparse
import importlib
import json
import sys
from contextlib import closing
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from medqc_ingest.config import PassfilePostgresSettings  # noqa: E402
from medqc_ingest.control.models import ControlError  # noqa: E402
from medqc_ingest.control.postgres import (  # noqa: E402
    initialize_control,
    validate_control_database,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--database", required=True)
    parser.add_argument("--passfile", required=True, type=Path)
    parser.add_argument("--user", default="postgres")
    parser.add_argument("--port", default=5432, type=int)
    parser.add_argument("--pg-major", default=16, type=int)
    parser.add_argument("--owner", default="medqc_owner")
    parser.add_argument("--worker-role", default="medqc_job_worker")
    parser.add_argument("--api-role", default="medqc_job_api")
    args = parser.parse_args(argv)
    try:
        validate_control_database(args.database)
        settings = PassfilePostgresSettings(
            "127.0.0.1", args.port, args.database, args.user, args.passfile
        )
        driver = importlib.import_module("psycopg2")
        with closing(
            driver.connect(
                **settings.connection_kwargs(),
                options="-c timezone=UTC -c default_transaction_read_only=off",
            )
        ) as c:
            with c.cursor() as cur:
                cur.execute(
                    "SELECT current_database(),session_user,current_user,inet_server_port(),"
                    "current_setting('server_version_num')::int"
                )
                actual = cur.fetchone()
                if (
                    actual[:4] != (args.database, args.user, args.user, args.port)
                    or actual[4] // 10000 != args.pg_major
                ):
                    raise ControlError("database_identity", "control.initialize_preflight", 400)
            c.rollback()
            initialize_control(
                c,
                args.database,
                owner=args.owner,
                worker_role=args.worker_role,
                api_role=args.api_role,
            )
        print(
            json.dumps(
                {
                    "status": "CONTROL_SCHEMA_INITIALIZED",
                    "database": args.database,
                    "created_roles": False,
                    "source_accessed": False,
                    "business_database_accessed": False,
                }
            )
        )
        return 0
    except Exception as exc:
        print(
            json.dumps(
                {
                    "status": "failed",
                    "exception_type": type(exc).__name__,
                    "code": exc.code if isinstance(exc, ControlError) else "initialize_failed",
                    "location": exc.location
                    if isinstance(exc, ControlError)
                    else "control.initialize",
                    "sqlstate": getattr(exc, "pgcode", None),
                }
            ),
            file=sys.stderr,
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
