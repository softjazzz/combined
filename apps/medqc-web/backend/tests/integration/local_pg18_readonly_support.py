"""仅显式获准的本机两库；不能用于CI或业务运行配置。"""

from contextlib import ExitStack, contextmanager
from pathlib import Path
import re
from unittest.mock import patch

import psycopg2
from psycopg2.extensions import parse_dsn, connection, cursor
from tests.scheduler_support import OfflineIsolation, OfflineIsolationError

IDENTITIES = {
    "medqc_ingest_takeover_20261030114502": "medqc_local_ingest_ro_20261105",
    "medqc_cdm_takeover_20261030114502": "medqc_local_cdm_ro_20261105",
}


class ReadonlyGuard:
    def __init__(self, contract):
        assert contract["host"] == "127.0.0.1" and contract["port"] == 5432
        self.roles = {r["database"]: r for r in contract["roles"]}
        assert {db: r["role"] for db, r in self.roles.items()} == IDENTITIES
        self.counts = dict(
            connections=0,
            forbidden_connections=0,
            write_attempts=0,
            model_attempts=0,
            external_transport_attempts=0,
        )

    def validate(self, params):
        role = self.roles.get(params.get("dbname"))
        if (
            role is None
            or params.get("host") != "127.0.0.1"
            or int(params.get("port", 0)) != 5432
            or params.get("user") != role["role"]
            or any(params.get(k) for k in ("password", "service", "hostaddr"))
            or params.get("options", "")
            not in ("", "-c default_transaction_read_only=on")
            or params.get("sslmode", "prefer") != "prefer"
            or Path(params.get("passfile", "")).resolve()
            != Path(role["passfile"]).resolve()
        ):
            self.counts["forbidden_connections"] += 1
            raise OfflineIsolationError("local_readonly_connection_not_authorized")
        return role

    @contextmanager
    def activate(self):
        original = psycopg2.connect
        guard = self

        class GuardCursor(cursor):
            def execute(self, statement, params=None):
                sql = str(statement).strip()
                allowed = sql.upper().startswith(
                    (
                        "SELECT",
                        "SHOW",
                        "SET TRANSACTION READ ONLY",
                        "SET LOCAL STATEMENT_TIMEOUT",
                    )
                )
                if not allowed or re.search(r"\bpg_database\b", sql, re.I):
                    guard.counts["write_attempts"] += 1
                    raise OfflineIsolationError("local_readonly_sql_rejected")
                for schema, table in re.findall(
                    r'\b(?:FROM|JOIN)\s+"?(\w+)"?\."?(\w+)"?', sql, re.I
                ):
                    if schema not in {"pg_catalog", "information_schema"}:
                        role = guard.roles[self.connection.info.dbname]
                        if schema + "." + table not in role["table_select_whitelist"]:
                            raise OfflineIsolationError(
                                "local_readonly_table_not_authorized"
                            )
                return super().execute(statement, params)

        class GuardConnection(connection):
            def cursor(self, *args, **kwargs):
                kwargs["cursor_factory"] = GuardCursor
                return super().cursor(*args, **kwargs)

        def guarded(dsn=None, *args, **kwargs):
            params = {**(parse_dsn(dsn) if dsn else {}), **kwargs}
            guard.validate(params)
            conn = original(dsn, *args, connection_factory=GuardConnection, **kwargs)
            try:
                with conn.cursor() as c:
                    c.execute(
                        "SELECT current_database(),current_user,host(inet_server_addr()),inet_server_port(),current_setting('transaction_read_only'),current_setting('server_version_num')::int"
                    )
                    db, user, host, port, readonly, version = c.fetchone()
                    if (
                        IDENTITIES.get(db) != user
                        or host != "127.0.0.1"
                        or port != 5432
                        or readonly != "on"
                        or not 180000 <= version < 190000
                    ):
                        problem = OfflineIsolationError(
                            "local_readonly_runtime_identity_mismatch"
                        )
                        problem.identity = dict(
                            zip(
                                (
                                    "database",
                                    "role",
                                    "server_address",
                                    "server_port",
                                    "readonly",
                                    "version",
                                ),
                                map(str, (db, user, host, port, readonly, version)),
                            )
                        )
                        raise problem
                conn.rollback()
                guard.counts["connections"] += 1
                return conn
            except BaseException:
                conn.close()
                raise

        def sqlalchemy_guard(dialect, record, args, kwargs):
            if dialect.name != "postgresql":
                raise OfflineIsolationError("local_readonly_non_postgresql")
            guard.validate({**(parse_dsn(args[0]) if args else {}), **kwargs})

        with ExitStack() as stack:
            offline = OfflineIsolation()
            offline._sqlite_listener = sqlalchemy_guard
            stack.enter_context(offline)
            stack.enter_context(patch.object(psycopg2, "connect", guarded))
            import httpx
            from app.services.qc_llm_client import SichuanQCLLMClient

            def deny_model(*a, **k):
                guard.counts["model_attempts"] += 1
                raise OfflineIsolationError("local_readonly_model_forbidden")

            def deny_http(*a, **k):
                guard.counts["external_transport_attempts"] += 1
                raise OfflineIsolationError("local_readonly_http_forbidden")

            stack.enter_context(
                patch.object(SichuanQCLLMClient, "generate", deny_model)
            )
            stack.enter_context(patch.object(httpx.Client, "send", deny_http))
            stack.enter_context(patch.object(httpx.AsyncClient, "send", deny_http))
            yield
