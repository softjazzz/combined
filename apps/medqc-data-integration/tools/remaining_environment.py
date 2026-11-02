"""集中验收的固定四库环境；不连接历史验收库或业务库。"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import re
import subprocess
import sys
from contextlib import closing
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from medqc_ingest.config import PassfilePostgresSettings  # noqa: E402
from medqc_ingest.domain import ErrorKind, IngestError  # noqa: E402

ROLES = ("ingest", "cdm", "restore_ingest", "restore_cdm")
REVISION = "20261101_000058"


def load_combined_profile(path=None):
    """复用两份冻结合同，仅在本次隔离验收中探查零样本来源，不启用生产来源。"""
    from medqc_ingest.domain import (
        DerivedDocumentId,
        FieldMapping,
        InterfaceSpec,
        PublishSpec,
        canonical_json,
        sha256_hex,
    )
    from medqc_ingest.periop_replay import load_profile as load_periop
    from medqc_ingest.remaining_contracts import load_profile

    contract, specs = load_profile(path)
    periop, active = load_periop(ROOT / "contracts/periop-acceptance-contracts.json")
    specs.update(active)
    items = list(contract["interfaces"])
    for source in periop["interfaces"]:
        item = dict(
            source,
            source_columns=source["ordered_source_columns"],
            mappings=source["field_mappings"],
            validation_group="periop17",
        )
        if item["interface"] not in specs and item["ordered_source_columns"]:
            derived = item["derived_document_id"]
            schema, table = item["publish_target"].split(".")
            target = PublishSpec(
                schema,
                table,
                tuple(item["target_primary_key"]),
                tuple(item["required_target_columns"]),
                tuple(
                    FieldMapping(m["source"], m["target"], m["target_type"])
                    for m in item["field_mappings"]
                ),
                DerivedDocumentId(tuple(derived["fields"]), derived["prefix"]) if derived else None,
            )
            specs[item["interface"]] = InterfaceSpec(
                item["interface"],
                item["interface"],
                item["argument_count"],
                tuple(item["raw_key_fields"]),
                item["publish_target"],
                tuple(item["ordered_source_columns"]),
                "remaining-isolated-sample-probe;contract:" + sha256_hex(canonical_json(item)),
                target,
            )
        items.append(item)
    from medqc_ingest.domain import INTERFACE_REGISTRY

    require(
        len(items) == 42 and not ({i["interface"] for i in items} & set(INTERFACE_REGISTRY)),
        "remaining_combined_scope",
    )
    return dict(
        contract, scope="remaining25_periop17", interfaces=items, production_registry_modified=False
    ), specs


def require(value, location):
    if not value:
        raise IngestError(ErrorKind.CONFIGURATION, location)


def write_json(path, value):
    temporary = path.with_suffix(path.suffix + ".pending")
    with temporary.open("w", encoding="utf-8", newline="\n") as stream:
        json.dump(value, stream, ensure_ascii=False, sort_keys=True, indent=2)
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, path)


def fingerprint(connection):
    from psycopg2 import sql

    result = {"tables": {}, "sequences": {}}
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT schemaname,tablename FROM pg_tables WHERE schemaname NOT IN "
            "('pg_catalog','information_schema') ORDER BY 1,2"
        )
        for schema, table in cursor.fetchall():
            digest, rows = hashlib.sha256(), 0
            cursor.execute(
                sql.SQL(
                    "SELECT md5(to_jsonb(t)::text),count(*) FROM {} t GROUP BY 1 ORDER BY 1"
                ).format(sql.Identifier(schema, table))
            )
            for value, count in cursor:
                digest.update(f"{value}:{count}\n".encode())
                rows += count
            result["tables"][f"{schema}.{table}"] = {"rows": rows, "sha256": digest.hexdigest()}
        cursor.execute("SELECT schemaname,sequencename FROM pg_sequences ORDER BY 1,2")
        for schema, sequence in cursor.fetchall():
            cursor.execute(
                sql.SQL("SELECT last_value,is_called FROM {}").format(
                    sql.Identifier(schema, sequence)
                )
            )
            result["sequences"][f"{schema}.{sequence}"] = list(cursor.fetchone())
    return result


class Environment:
    def __init__(self, args, contract=None, specs=None):
        require(re.fullmatch(r"[0-9]{14}", args.suffix) is not None, "remaining_suffix")
        self.args, self.contract, self.specs = args, contract or {"interfaces": []}, specs or {}
        self.databases = {role: f"medqc_remaining_{role}_{args.suffix}" for role in ROLES}
        self.path = args.output / "environment-progress.json"
        self.state = {"databases": self.databases, "stages": {}}
        if self.path.is_file():
            self.state = json.loads(self.path.read_text(encoding="utf-8"))
            require(self.state.get("databases") == self.databases, "remaining_environment_identity")

    def settings(self, role, *, admin=False):
        require(role in ROLES or role == "postgres", "remaining_role_scope")
        database = self.databases[role] if role in ROLES else "postgres"
        return PassfilePostgresSettings(
            "127.0.0.1",
            self.args.port,
            database,
            self.args.admin_user if admin else "medqc_sync",
            self.args.admin_passfile if admin else self.args.runtime_passfile,
        )

    def connect(self, role="ingest", *, admin=False, readonly=False):
        import psycopg2

        require(role != "postgres" or admin, "remaining_admin_database_only")
        settings = self.settings(role, admin=admin)
        connection = psycopg2.connect(
            **settings.connection_kwargs(),
            application_name="medqc_remaining_acceptance",
            options="-c timezone=UTC -c default_transaction_read_only="
            + ("on" if readonly else "off"),
        )
        try:
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT current_database(),session_user,current_user,inet_server_port(),"
                    "current_setting('server_version_num')::int,"
                    "current_setting('transaction_read_only'),current_setting('cluster_name')"
                )
                row = cursor.fetchone()
            require(
                row[:4] == (settings.database, settings.user, settings.user, self.args.port)
                and row[4] // 10000 == self.args.pg_major
                and row[5] == ("on" if readonly else "off"),
                "remaining_connection_identity",
            )
            if getattr(self.args, "synthetic", False):
                require(
                    row[6] == "medqc_remaining_synthetic" and self.args.port != 5432,
                    "remaining_synthetic_guard",
                )
            else:
                require(self.args.pg_major == 16, "remaining_customer_pg16")
            connection.rollback()
            return connection
        except BaseException:
            connection.close()
            raise

    def _save(self):
        write_json(self.path, self.state)

    def _stage(self, name, operation, verify=None):
        status = self.state["stages"].get(name)
        if status == "done":
            return
        if status == "running":
            require(verify is not None and verify(), "remaining_environment_reconcile_required")
        else:
            self.state["stages"][name] = "running"
            self._save()
            operation()
        self.state["stages"][name] = "done"
        self._save()

    def _empty(self, role):
        with (
            closing(self.connect(role, admin=True, readonly=True)) as connection,
            connection.cursor() as cursor,
        ):
            cursor.execute(
                "SELECT count(*) FROM pg_tables WHERE schemaname NOT IN "
                "('pg_catalog','information_schema')"
            )
            return cursor.fetchone()[0] == 0

    def _ingest_ready(self):
        with (
            closing(self.connect("ingest", admin=True, readonly=True)) as connection,
            connection.cursor() as cursor,
        ):
            cursor.execute("SELECT to_regclass('sync_ops.remaining_environment_marker')")
            if cursor.fetchone()[0] is None:
                return False
            cursor.execute("SELECT revision FROM sync_ops.remaining_environment_marker")
            return cursor.fetchall() == [(REVISION,)]

    def _cdm_ready(self):
        with (
            closing(self.connect("cdm", admin=True, readonly=True)) as connection,
            connection.cursor() as cursor,
        ):
            cursor.execute("SELECT to_regclass('public.alembic_version')")
            if cursor.fetchone()[0] is None:
                return False
            cursor.execute("SELECT version_num FROM public.alembic_version")
            return cursor.fetchall() == [(REVISION,)]

    def prepare(self):
        from psycopg2 import sql

        for folder in (
            self.args.output,
            self.args.output / "reports",
            self.args.output / "backups",
            self.args.output / "private-logs",
        ):
            folder.mkdir(exist_ok=True)
        if not self.path.exists():
            with (
                closing(self.connect("postgres", admin=True, readonly=True)) as connection,
                connection.cursor() as cursor,
            ):
                cursor.execute(
                    "SELECT datname FROM pg_database WHERE datname=ANY(%s)",
                    (list(self.databases.values()),),
                )
                require(not cursor.fetchall(), "remaining_databases_must_be_new")
            self._save()
        for role, database in self.databases.items():

            def create(database=database):
                with closing(self.connect("postgres", admin=True)) as connection:
                    connection.autocommit = True
                    with connection.cursor() as cursor:
                        cursor.execute(
                            "SELECT rolname,rolcanlogin,rolsuper,rolcreatedb,rolcreaterole,"
                            "rolreplication,rolbypassrls FROM pg_roles WHERE rolname IN "
                            "('medqc_owner','medqc_sync')"
                        )
                        require(
                            {r[0]: r[1:] for r in cursor.fetchall()}
                            == {
                                "medqc_owner": (False,) * 6,
                                "medqc_sync": (True, False, False, False, False, False),
                            },
                            "remaining_roles",
                        )
                        cursor.execute("SELECT pg_has_role('medqc_sync','medqc_owner','MEMBER')")
                        require(not cursor.fetchone()[0], "remaining_runtime_not_owner")
                        cursor.execute(
                            sql.SQL(
                                "CREATE DATABASE {} OWNER medqc_owner "
                                "TEMPLATE template0 ENCODING 'UTF8'"
                            ).format(sql.Identifier(database))
                        )

            self._stage("create_" + role, create, lambda role=role: self._empty(role))
        self._stage("ingest_migrate", self._initialize_ingest, self._ingest_ready)
        self._stage("cdm_migrate", self._initialize_cdm, self._cdm_ready)
        self._stage("runtime_grants", self._grants, lambda: False)
        return {
            "databases": self.databases,
            "revision": REVISION,
            "official_initializer": True,
            "source_database_accessed": False,
        }

    def _initialize_ingest(self):
        require(self._empty("ingest"), "remaining_ingest_must_be_empty")
        with (
            closing(self.connect("ingest", admin=True)) as connection,
            connection,
            connection.cursor() as cursor,
        ):
            cursor.execute("SET LOCAL ROLE medqc_owner")
            for path in sorted((ROOT / "migrations").glob("[0-9][0-9][0-9]_*.sql")):
                body = path.read_text(encoding="utf-8")
                require(
                    body.lstrip().startswith(("BEGIN;", "--"))
                    and body.rstrip().endswith("COMMIT;"),
                    "remaining_ingest_migration",
                )
                # 官方五个文件合成单一初始化事务，避免每文件COMMIT留下半初始化。
                begin = body.index("BEGIN;")
                cursor.execute(body[begin + len("BEGIN;") :].rstrip()[: -len("COMMIT;")])
            cursor.execute(
                "CREATE TABLE sync_ops.remaining_environment_marker (revision text PRIMARY KEY)"
            )
            cursor.execute(
                "INSERT INTO sync_ops.remaining_environment_marker VALUES (%s)", (REVISION,)
            )

    def _initialize_cdm(self):
        require(self._empty("cdm"), "remaining_cdm_must_be_empty")
        backend = self.args.backend.resolve()
        sys.path.insert(0, str(backend))
        module_spec = importlib.util.spec_from_file_location(
            "remaining_official_bootstrap", backend / "scripts/bootstrap_cache_sync_database.py"
        )
        require(
            module_spec is not None and module_spec.loader is not None, "remaining_bootstrap_file"
        )
        module = importlib.util.module_from_spec(module_spec)
        module_spec.loader.exec_module(module)
        require(module.TARGET_REVISION == REVISION, "remaining_bootstrap_revision")
        import dotenv

        database = self.databases["cdm"]
        url = f"postgresql+psycopg2://{self.args.admin_user}@127.0.0.1:{self.args.port}/{database}"
        with (
            patch.object(dotenv, "load_dotenv", return_value=False),
            patch.dict(
                os.environ,
                {
                    "MEDQC_BOOTSTRAP_DATABASE_URL": url,
                    "PGPASSFILE": str(self.args.admin_passfile),
                    "PGPASSWORD": "",
                    "PYTHONPATH": str(backend),
                },
            ),
        ):
            module.initialize(database, owner_role="medqc_owner")

    def _grants(self):
        from psycopg2 import sql
        from psycopg2.extras import Json

        with (
            closing(self.connect("ingest", admin=True)) as connection,
            connection,
            connection.cursor() as cursor,
        ):
            cursor.execute("SET LOCAL ROLE medqc_owner")
            # 只在新环境中登记新scope；旧13仅为正式迁移的历史种子，显式关闭。
            cursor.execute("UPDATE sync_ops.source_interface SET is_enabled=false")
            for item in self.contract["interfaces"]:
                name = item["interface"]
                spec = self.specs.get(name)
                cursor.execute(
                    "INSERT INTO sync_ops.source_interface(interface_name,procedure_name,"
                    "argument_count,key_fields,publish_target,is_enabled,evidence_version) "
                    "VALUES(%s,%s,%s,%s,%s,%s,%s) ON CONFLICT(interface_name) DO UPDATE SET "
                    "key_fields=EXCLUDED.key_fields,publish_target=EXCLUDED.publish_target,"
                    "is_enabled=EXCLUDED.is_enabled,evidence_version=EXCLUDED.evidence_version",
                    (
                        name,
                        name,
                        item["argument_count"],
                        Json(list(spec.key_fields) if spec else []),
                        spec.publish_target if spec else None,
                        spec is not None,
                        "remaining-explicit-validation-v1",
                    ),
                )
            cursor.execute("REVOKE CREATE ON SCHEMA public FROM PUBLIC")
            cursor.execute("GRANT USAGE ON SCHEMA cache_raw,sync_ops TO medqc_sync")
            cursor.execute(
                "GRANT SELECT,INSERT,UPDATE ON ALL TABLES IN SCHEMA cache_raw,"
                "sync_ops TO medqc_sync"
            )
            cursor.execute(
                "GRANT USAGE,SELECT ON ALL SEQUENCES IN SCHEMA cache_raw,sync_ops TO medqc_sync"
            )
        with (
            closing(self.connect("cdm", admin=True)) as connection,
            connection,
            connection.cursor() as cursor,
        ):
            cursor.execute("SET LOCAL ROLE medqc_owner")
            cursor.execute("REVOKE CREATE ON SCHEMA public FROM PUBLIC")
            cursor.execute("REVOKE ALL ON ALL TABLES IN SCHEMA cdm FROM medqc_sync")
            cursor.execute("GRANT USAGE ON SCHEMA cdm TO medqc_sync")
            cursor.execute("GRANT SELECT ON public.alembic_version TO medqc_sync")
            for item in self.contract["interfaces"]:
                target = item.get("publish_target")
                if target:
                    require(
                        re.fullmatch(r"cdm\.[a-z_]+", target) is not None,
                        "remaining_target_identifier",
                    )
                    cursor.execute(
                        sql.SQL("GRANT SELECT,INSERT,UPDATE ON {} TO medqc_sync").format(
                            sql.Identifier(*target.split("."))
                        )
                    )

    def fingerprint(self, role):
        with closing(self.connect(role, admin=True, readonly=True)) as connection:
            return fingerprint(connection)

    def _native(self, tool, values):
        binary = self.args.pg_bin / (tool + (".exe" if os.name == "nt" else ""))
        require(binary.is_file(), "remaining_pg_binary_missing")
        command = [
            str(binary),
            "-h",
            "127.0.0.1",
            "-p",
            str(self.args.port),
            "-U",
            self.args.admin_user,
            "--no-password",
            *values,
        ]
        env = dict(os.environ, PGPASSFILE=str(self.args.admin_passfile))
        env.pop("PGPASSWORD", None)
        result = subprocess.run(
            command,
            env=env,
            capture_output=True,
            check=False,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        if result.returncode:
            # 失败原文仅留新保护目录，不能把可能含字段值的pg错误打进公开报告。
            private = self.args.output / "private-logs" / (tool + ".stderr")
            private.write_bytes(result.stderr)
            raise IngestError(ErrorKind.INGEST_WRITE, "remaining_backup_native")

    def backup_restore(self):
        report_path = self.args.output / "reports" / "backup-restore.json"
        previous = None
        if report_path.exists():
            previous = json.loads(report_path.read_text(encoding="utf-8"))
        report = {"databases": {}, "restore_fingerprint_equal": True}
        for role in ("ingest", "cdm"):
            restore_role = "restore_" + role
            before = self.fingerprint(role)
            version = hashlib.sha256(json.dumps(before, sort_keys=True).encode()).hexdigest()
            dump = self.args.output / "backups" / (role + "-" + version + ".dump")
            if not dump.exists():
                pending = dump.with_suffix(".pending")
                self._native("pg_dump", ["-Fc", "-f", str(pending), self.databases[role]])
                os.replace(pending, dump)
            empty = self._empty(restore_role)
            actual = None if empty else self.fingerprint(restore_role)
            clean = False
            if actual is not None and actual != before:
                require(
                    previous is not None and actual == previous["databases"][role]["fingerprint"],
                    "remaining_restore_not_our_prior_backup",
                )
                clean = True
            if empty or clean:
                self._native(
                    "pg_restore",
                    [
                        "--exit-on-error",
                        "--single-transaction",
                        *(["--clean", "--if-exists"] if clean else []),
                        "-d",
                        self.databases[restore_role],
                        str(dump),
                    ],
                )
            restored = self.fingerprint(restore_role)
            require(restored == before, "remaining_restore_fingerprint_mismatch")
            report["databases"][role] = {
                "dump_bytes": dump.stat().st_size,
                "dump_sha256": hashlib.sha256(dump.read_bytes()).hexdigest(),
                "restore_fingerprint_equal": True,
                "fingerprint": before,
            }
        write_json(report_path, report)
        return report

    def backup_revision(self):
        current = {role: self.fingerprint(role) for role in ("ingest", "cdm")}
        return hashlib.sha256(json.dumps(current, sort_keys=True).encode()).hexdigest()
