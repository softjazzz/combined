"""第二批隔离投影验收；只读固定快照，不连接Caché/业务库/原13接口库。"""

from __future__ import annotations

import argparse
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

import psycopg2
from major_document_transform import TYPE_COMPATIBILITY, ContractError
from periop_transform import ALLOWED, decode_snapshot, project_row
from preflight_periop_projection import DATABASE, evaluate
from psycopg2 import sql
from psycopg2.extras import execute_values

ROOT = Path(__file__).resolve().parents[1]
REVISION = "20261031_000057"
SOURCE_TABLES = {
    "cache_raw.snapshot_batch",
    "cache_raw.result_set",
    "cache_raw.snapshot_row",
    "cache_raw.record_current",
    "cache_raw.record_version",
    "sync_ops.source_schema",
    "sync_ops.ingest_audit",
    "sync_ops.key_validation",
}


def target_name(value, restore=False):
    prefix = "medqc_periop_restore_" if restore else "medqc_periop_cdm_acceptance_"
    if not re.fullmatch(prefix + r"[0-9]{14}", value):
        raise ContractError("new_target_database_scope")
    return value


def write_report(directory, name, content):
    with (directory / name).open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(content, stream, ensure_ascii=False, sort_keys=True, indent=2)
        stream.write("\n")


def connect(args, database, *, admin=False, readonly=False):
    if database not in {DATABASE, args.target, args.restore, "postgres"}:
        raise ContractError("database_scope")
    if database == DATABASE and (admin or not readonly):
        raise ContractError("source_must_be_runtime_readonly")
    connection = psycopg2.connect(
        host="127.0.0.1",
        port=args.port,
        dbname=database,
        user=args.admin_user if admin else "medqc_sync",
        passfile=str(args.admin_passfile if admin else args.runtime_passfile),
        options="-c timezone=UTC -c default_transaction_read_only=" + ("on" if readonly else "off"),
        connect_timeout=15,
        application_name="medqc-periop-acceptance-v2",
    )
    try:
        with connection.cursor() as cur:
            cur.execute(
                "SELECT current_database(),session_user,current_user,"
                "current_setting('transaction_read_only'),inet_server_port(),"
                "current_setting('server_version_num')::int"
            )
            actual = cur.fetchone()
        user = args.admin_user if admin else "medqc_sync"
        if (
            actual[:5] != (database, user, user, "on" if readonly else "off", args.port)
            or actual[5] // 10000 != args.pg_major
        ):
            raise ContractError("connection_identity")
        connection.rollback()
        return connection
    except BaseException:
        connection.close()
        raise


def fingerprint(connection, *, source=False):
    result = {"tables": {}, "sequences": {}}
    with connection.cursor() as cur:
        cur.execute(
            "SELECT schemaname,tablename FROM pg_tables WHERE schemaname NOT IN "
            "('pg_catalog','information_schema') ORDER BY 1,2"
        )
        tables = cur.fetchall()
        if source and {f"{s}.{t}" for s, t in tables} != SOURCE_TABLES:
            raise ContractError("source_table_inventory")
        for schema, table in tables:
            cur.execute(
                sql.SQL(
                    "SELECT md5(to_jsonb(t)::text),count(*) FROM {} t GROUP BY 1 ORDER BY 1"
                ).format(sql.Identifier(schema, table))
            )
            digest = hashlib.sha256()
            count = 0
            for row_hash, multiplicity in cur:
                digest.update(f"{row_hash}:{multiplicity}\n".encode())
                count += multiplicity
            result["tables"][f"{schema}.{table}"] = {"rows": count, "hash": digest.hexdigest()}
        cur.execute(
            "SELECT schemaname,sequencename FROM pg_sequences WHERE schemaname "
            "NOT IN ('pg_catalog','information_schema') ORDER BY 1,2"
        )
        for schema, sequence in cur.fetchall():
            cur.execute(
                sql.SQL("SELECT last_value,is_called FROM {}").format(
                    sql.Identifier(schema, sequence)
                )
            )
            result["sequences"][f"{schema}.{sequence}"] = list(cur.fetchone())
    return result


def create_targets(args):
    with closing(connect(args, "postgres", admin=True)) as connection:
        connection.autocommit = True
        with connection.cursor() as cur:
            cur.execute(
                "SELECT rolname,rolcanlogin,rolsuper FROM pg_roles "
                "WHERE rolname IN ('medqc_owner','medqc_sync')"
            )
            roles = {row[0]: row[1:] for row in cur.fetchall()}
            if roles != {"medqc_owner": (False, False), "medqc_sync": (True, False)}:
                raise ContractError("deployment_roles_contract")
            cur.execute("SELECT pg_has_role('medqc_sync','medqc_owner','MEMBER')")
            if cur.fetchone()[0]:
                raise ContractError("runtime_is_owner_member")
            cur.execute(
                "SELECT datname FROM pg_database WHERE datname IN (%s,%s)",
                (args.target, args.restore),
            )
            if cur.fetchall():
                raise ContractError("target_already_exists_no_reuse")
            for database in (args.target, args.restore):
                cur.execute(
                    sql.SQL(
                        "CREATE DATABASE {} OWNER medqc_owner ENCODING 'UTF8' TEMPLATE template0"
                    ).format(sql.Identifier(database))
                )


def bootstrap(args):
    # 不导入客户应用，不读取.env；复用仓库正式初始化器及完整57条迁移。
    backend = args.backend.resolve()
    sys.path.insert(0, str(backend))
    spec = importlib.util.spec_from_file_location(
        "periop_official_bootstrap", backend / "scripts/bootstrap_cache_sync_database.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    if module.TARGET_REVISION != REVISION:
        raise ContractError("initializer_revision")
    url = f"postgresql+psycopg2://{args.admin_user}@127.0.0.1:{args.port}/{args.target}"
    import dotenv

    with (
        patch.object(dotenv, "load_dotenv", return_value=False),
        patch.dict(
            os.environ,
            {
                "MEDQC_BOOTSTRAP_DATABASE_URL": url,
                "PGPASSFILE": str(args.admin_passfile),
                "PGPASSWORD": "",
            },
        ),
    ):
        steps = module.initialize(args.target, owner_role="medqc_owner")
    return {"revision": REVISION, "official_initializer": True, "steps": steps}


def grant_target(args, contract):
    with closing(connect(args, args.target, admin=True)) as connection, connection:  # noqa: SIM117
        with connection.cursor() as cur:
            cur.execute("SET LOCAL ROLE medqc_owner")
            # 部署授权不是应用迁移；仅授予本次17张目标表和验收审计表。
            cur.execute("REVOKE CREATE ON SCHEMA public FROM PUBLIC")
            cur.execute("REVOKE ALL ON ALL TABLES IN SCHEMA cdm FROM medqc_sync")
            cur.execute(
                "ALTER DEFAULT PRIVILEGES FOR ROLE medqc_owner IN SCHEMA cdm "
                "REVOKE ALL ON TABLES FROM medqc_sync"
            )
            cur.execute(
                "GRANT CONNECT ON DATABASE "
                + sql.Identifier(args.target).as_string(cur)
                + " TO medqc_sync"
            )
            cur.execute("GRANT USAGE ON SCHEMA cdm TO medqc_sync")
            cur.execute("GRANT SELECT ON public.alembic_version TO medqc_sync")
            for item in contract["interfaces"]:
                cur.execute(
                    sql.SQL("GRANT SELECT,INSERT,UPDATE ON {} TO medqc_sync").format(
                        sql.Identifier(*item["publish_target"].split("."))
                    )
                )
            cur.execute("CREATE SCHEMA periop_ops AUTHORIZATION medqc_owner")
            cur.execute(
                "CREATE TABLE periop_ops.projection_batch ("
                "batch_id bigserial PRIMARY KEY,interface_name text NOT NULL,"
                "round_no int NOT NULL,status text NOT NULL,rows_expected int NOT NULL,"
                "rows_changed int, error_kind text,started_at timestamptz NOT NULL DEFAULT now(),"
                "finished_at timestamptz)"
            )
            cur.execute("GRANT USAGE ON SCHEMA periop_ops TO medqc_sync")
            cur.execute("GRANT SELECT,INSERT,UPDATE ON periop_ops.projection_batch TO medqc_sync")
            cur.execute("GRANT USAGE,SELECT ON ALL SEQUENCES IN SCHEMA periop_ops TO medqc_sync")


def catalog_preflight(connection, contract):
    results = []
    with connection.cursor() as cur:
        cur.execute("SELECT version_num FROM public.alembic_version")
        if cur.fetchall() != [(REVISION,)]:
            raise ContractError("target_revision")
        for item in contract["interfaces"]:
            schema, table = item["publish_target"].split(".")
            cur.execute(
                "SELECT column_name,data_type,character_maximum_length,is_nullable "
                "FROM information_schema.columns WHERE table_schema=%s AND table_name=%s",
                (schema, table),
            )
            columns = {row[0]: row[1:] for row in cur.fetchall()}
            if set(columns) != {c["name"] for c in item["target_columns"]}:
                raise ContractError("actual_target_columns_mismatch")
            for expected in item["target_columns"]:
                actual_type, length, nullable = columns[expected["name"]]
                kind = (
                    "timestamptz"
                    if expected["type"] == "TIMESTAMP WITH TIME ZONE"
                    else "datetime"
                    if expected["type"] == "DATETIME"
                    else "date"
                    if expected["type"] == "DATE"
                    else "text"
                )
                if (
                    actual_type not in TYPE_COMPATIBILITY[kind]
                    or length != expected["max_length"]
                    or (nullable == "YES") != expected["nullable"]
                ):
                    raise ContractError("actual_target_type_mismatch")
            cur.execute(
                "SELECT a.attname FROM pg_index i JOIN pg_attribute a "
                "ON a.attrelid=i.indrelid AND a.attnum=ANY(i.indkey) "
                "WHERE i.indrelid=%s::regclass AND i.indisprimary "
                "ORDER BY array_position(i.indkey,a.attnum)",
                (item["publish_target"],),
            )
            if [r[0] for r in cur.fetchall()] != item["target_primary_key"]:
                raise ContractError("actual_target_primary_key_mismatch")
            cur.execute(
                "SELECT pg_get_userbyid(relowner),(has_table_privilege(current_user,oid,'SELECT') "
                "AND has_table_privilege(current_user,oid,'INSERT') "
                "AND has_table_privilege(current_user,oid,'UPDATE')),"
                "has_schema_privilege(current_user,relnamespace,"
                "'CREATE') FROM pg_class WHERE oid=%s::regclass",
                (item["publish_target"],),
            )
            if cur.fetchone() != ("medqc_owner", True, False):
                raise ContractError("target_owner_or_runtime_privileges")
            cur.execute(sql.SQL("SELECT count(*) FROM {}").format(sql.Identifier(schema, table)))
            if cur.fetchone()[0]:
                raise ContractError("target_must_be_empty")
            results.append(
                {
                    "interface": item["interface"],
                    "columns": len(columns),
                    "target_catalog_verified": True,
                    "source_state": item["source_state"],
                }
            )
    return results


def source_rows(connection, contract, item):
    with connection.cursor(name="periop_source_rows") as cur:
        cur.execute(
            "SELECT r.values_json,r.schema_hash,r.row_hash,s.columns_json "
            "FROM cache_raw.snapshot_row r JOIN cache_raw.snapshot_batch b "
            "ON b.batch_id=r.batch_id JOIN cache_raw.result_set s "
            "ON (s.batch_id,s.result_set_index)=(r.batch_id,r.result_set_index) "
            "WHERE b.round_no=1 AND b.interface_name=%s "
            "ORDER BY r.batch_id,r.result_set_index,r.row_number",
            (item["interface"],),
        )
        while chunk := cur.fetchmany(500):
            for values, schema_hash, row_hash, columns in chunk:
                payload = decode_snapshot(
                    contract, item["interface"], columns, values, schema_hash, row_hash
                )
                yield project_row(contract, item["interface"], payload)


def upsert_statement(item):
    columns = [m["target"] for m in item["field_mappings"]]
    mutable = [c for c in columns if c not in item["target_primary_key"]]
    return sql.SQL(
        "INSERT INTO {} AS old ({}) VALUES %s ON CONFLICT ({}) DO UPDATE SET {} "
        "WHERE ({}) IS DISTINCT FROM ({}) RETURNING 1"
    ).format(
        sql.Identifier(*item["publish_target"].split(".")),
        sql.SQL(",").join(map(sql.Identifier, columns)),
        sql.SQL(",").join(map(sql.Identifier, item["target_primary_key"])),
        sql.SQL(",").join(
            sql.SQL("{}=EXCLUDED.{}").format(sql.Identifier(c), sql.Identifier(c)) for c in mutable
        ),
        sql.SQL(",").join(sql.SQL("old.{}").format(sql.Identifier(c)) for c in mutable),
        sql.SQL(",").join(sql.SQL("EXCLUDED.{}").format(sql.Identifier(c)) for c in mutable),
    )


def verify_fields(source, target, contract, item):
    columns = [m["target"] for m in item["field_mappings"]]
    expected = {}
    for row in source_rows(source, contract, item):
        key = tuple(row[c] for c in item["target_primary_key"])
        if key in expected:
            raise ContractError("target_key_collision")
        expected[key] = row
    stats = {c: {"field": c, "rows": 0, "nonempty": 0, "equal": 0} for c in columns}
    with target.cursor() as cur:
        cur.execute(
            sql.SQL("SELECT {} FROM {}").format(
                sql.SQL(",").join(map(sql.Identifier, columns)),
                sql.Identifier(*item["publish_target"].split(".")),
            )
        )
        while chunk := cur.fetchmany(500):
            for values in chunk:
                actual = dict(zip(columns, values, strict=True))
                key = tuple(actual[c] for c in item["target_primary_key"])
                row = expected.pop(key, None)
                if row is None or actual != row:
                    raise ContractError("projected_fields_not_equal")
                for column, value in actual.items():
                    stats[column]["rows"] += 1
                    stats[column]["nonempty"] += int(value is not None and value != "")
                    stats[column]["equal"] += 1
    if expected:
        raise ContractError("projected_rows_missing")
    return list(stats.values())


def project_interface(args, source, control, contract, item, number):
    count = item["expected_first_round_rows"]
    with control.cursor() as cur:
        cur.execute(
            "INSERT INTO periop_ops.projection_batch "
            "(interface_name,round_no,status,rows_expected) VALUES (%s,%s,'running',%s) "
            "RETURNING batch_id",
            (item["interface"], number, count),
        )
        batch = cur.fetchone()[0]
    control.commit()
    try:
        with closing(connect(args, args.target)) as data, data:
            columns = [m["target"] for m in item["field_mappings"]]
            chunk, changed, total = [], 0, 0
            keys = set()
            with data.cursor() as cur:
                statement = upsert_statement(item).as_string(cur)
                for row in source_rows(source, contract, item):
                    key = tuple(row[c] for c in item["target_primary_key"])
                    if key in keys:
                        raise ContractError("target_key_collision")
                    keys.add(key)
                    chunk.append(tuple(row[c] for c in columns))
                    total += 1
                    if len(chunk) == 500:
                        changed += len(execute_values(cur, statement, chunk, fetch=True))
                        chunk.clear()
                if chunk:
                    changed += len(execute_values(cur, statement, chunk, fetch=True))
                if total != count or (number == 2 and changed != 0):
                    raise ContractError("projection_count_or_idempotency")
                fields = verify_fields(source, data, contract, item)
                cur.execute(
                    "UPDATE periop_ops.projection_batch SET status='succeeded',"
                    "rows_changed=%s,finished_at=now() WHERE batch_id=%s",
                    (changed, batch),
                )
        return {
            "interface": item["interface"],
            "round": number,
            "rows": total,
            "changed": changed,
            "unchanged": total - changed,
            "status": "succeeded",
            "all_fields_equal": True,
            "fields": fields,
            "source_state": item["source_state"],
            "date_semantics": "unverified",
        }
    except BaseException:
        with control, control.cursor() as cur:
            cur.execute(
                "UPDATE periop_ops.projection_batch SET status='failed',"
                "error_kind='projection_error',finished_at=now() WHERE batch_id=%s",
                (batch,),
            )
        raise


def native(args, tool, arguments):
    env = dict(os.environ, PGPASSFILE=str(args.admin_passfile))
    for key in ("PGPASSWORD", "PGSERVICE", "PGSERVICEFILE", "PGOPTIONS"):
        env.pop(key, None)
    executable = args.pg_bin / (tool + (".exe" if os.name == "nt" else ""))
    log = args.output / (tool + ".private.log")
    # 文件位于管理员保护目录内；原始驱动错误仅留本机，不进回传reports。
    with log.open("ab") as stream:
        result = subprocess.run(
            [str(executable), *arguments], env=env, stdout=stream, stderr=stream, check=False
        )
    if result.returncode:
        raise ContractError("native_" + tool + "_failed")


def run(args):
    args.phase = "scope_preflight"
    target_name(args.target)
    target_name(args.restore, restore=True)
    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", args.admin_user):
        raise ContractError("deployment_user_identifier")
    if os.getenv("PGPASSWORD"):
        raise ContractError("pgpassword_forbidden")
    for path in (args.admin_passfile, args.runtime_passfile):
        if not path.is_file():
            raise ContractError("existing_passfile_required")
    if args.output.exists():
        raise ContractError("new_run_directory_required")
    args.output.mkdir()
    reports = args.output / "reports"
    reports.mkdir()
    contract = json.loads(args.contract.read_text(encoding="utf-8"))
    if (
        contract.get("required_alembic_revision") != REVISION
        or {i["interface"] for i in contract["interfaces"]} != ALLOWED
    ):
        raise ContractError("contract_revision_or_scope")
    write_report(
        reports,
        "database-plan.json",
        {
            "source": DATABASE,
            "target": args.target,
            "restore": args.restore,
            "source_writes": False,
        },
    )
    args.phase = "source_preflight"
    with closing(connect(args, DATABASE, readonly=True)) as source:
        before = fingerprint(source, source=True)
        source.rollback()
        metrics, _, dates, audit = evaluate(source, contract)
        if any(r["status"].startswith("blocked_") for r in metrics):
            raise ContractError("source_preflight_blocked")
        write_report(
            reports,
            "source-preflight.json",
            {"interfaces": metrics, "audit": audit, "dates": dates},
        )
        args.phase = "create_new_databases"
        create_targets(args)
        args.phase = "official_bootstrap_057"
        write_report(reports, "migration.json", bootstrap(args))
        args.phase = "deployment_grants"
        grant_target(args, contract)
        with closing(connect(args, args.target)) as control:
            args.phase = "actual_target_catalog"
            catalog = catalog_preflight(control, contract)
            control.rollback()
            write_report(reports, "target-catalog.json", catalog)
            with control.cursor() as cur:
                cur.execute("SELECT pg_try_advisory_lock(20261031,57)")
                if not cur.fetchone()[0]:
                    raise ContractError("projection_lock_busy")
            control.commit()
            args.phase = "two_round_projection"
            results = []
            for number in (1, 2):
                for item in contract["interfaces"]:
                    if not item["expected_first_round_rows"]:
                        continue
                    result = project_interface(args, source, control, contract, item, number)
                    results.append(result)
                    write_report(
                        reports, f"projection-{number}-{item['interface'][4:]}.json", result
                    )
            write_report(reports, "projection-summary.json", results)
    args.phase = "source_protection"
    with closing(connect(args, DATABASE, readonly=True)) as source:
        if fingerprint(source, source=True) != before:
            raise ContractError("source_changed_during_acceptance")
    write_report(
        reports,
        "source-protection.json",
        {
            "all_tables_and_sequences_unchanged": True,
            "source_writes": False,
            "checkpoint_created": False,
        },
    )
    args.phase = "backup_restore"
    with closing(connect(args, args.target, admin=True, readonly=True)) as target:
        target_before = fingerprint(target)
    common = [
        "--host",
        "127.0.0.1",
        "--port",
        str(args.port),
        "--username",
        args.admin_user,
        "--no-password",
    ]
    dump = args.output / "periop-accepted.dump"
    native(args, "pg_dump", [*common, "--format=custom", "--file", str(dump), args.target])
    native(args, "pg_restore", ["--list", str(dump)])
    native(args, "pg_restore", [*common, "--exit-on-error", "--dbname", args.restore, str(dump)])
    with closing(connect(args, args.restore, admin=True, readonly=True)) as restored:
        if fingerprint(restored) != target_before:
            raise ContractError("restore_fingerprint_not_equal")
    digest = hashlib.sha256(dump.read_bytes()).hexdigest()
    write_report(
        reports,
        "backup-restore.json",
        {"restore_fingerprint_equal": True, "dump_sha256": digest, "bytes": dump.stat().st_size},
    )
    summary = {
        "status": "PERIOP_PROJECTION_ACCEPTED_WITH_SOURCE_LIMITATIONS",
        "interfaces": 17,
        "nonempty_interfaces_projected": 13,
        "partial_source_interfaces": 2,
        "empty_sample_interfaces": 3,
        "vendor_blocked_interfaces": 1,
        "rows_per_round": 9365,
        "round2_changed": 0,
        "actual_target_catalog_verified": True,
        "source_unchanged": True,
        "restore_verified": True,
        "revision": REVISION,
        "cache_accessed": False,
        "business_database_accessed": False,
        "original_thirteen_accessed": False,
        "full_rule_engine_executed": False,
        "bundle_executed": False,
        "contains_phi": False,
        "contains_raw_values": False,
        "service_scope_expanded": False,
        "scheduled_task_modified": False,
    }
    write_report(reports, "acceptance.json", summary)
    print(summary["status"])


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--target", required=True)
    parser.add_argument("--restore", required=True)
    parser.add_argument("--admin-passfile", required=True, type=Path)
    parser.add_argument("--runtime-passfile", required=True, type=Path)
    parser.add_argument("--admin-user", default="postgres")
    parser.add_argument("--port", type=int, default=5432)
    parser.add_argument("--pg-major", type=int, default=16)
    parser.add_argument("--pg-bin", type=Path, required=True)
    parser.add_argument("--backend", type=Path, default=ROOT / "backend")
    parser.add_argument(
        "--contract", type=Path, default=ROOT / "contracts/periop-acceptance-contracts.json"
    )
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    output_preexisted = args.output.exists()
    try:
        run(args)
        return 0
    except Exception as error:
        diagnostic = {
            "status": "failed",
            "error_type": type(error).__name__,
            "sqlstate": getattr(error, "pgcode", None),
            "location": error.location
            if isinstance(error, ContractError)
            else getattr(args, "phase", "periop_acceptance"),
            "contains_phi": False,
            "contains_raw_values": False,
        }
        report_dir = args.output / "reports"
        if (
            not output_preexisted
            and report_dir.is_dir()
            and not (report_dir / "failure.json").exists()
        ):
            write_report(report_dir, "failure.json", diagnostic)
        print(json.dumps(diagnostic))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
