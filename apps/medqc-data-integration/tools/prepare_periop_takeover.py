"""第二批一次性独立接管验收：只读两个固定源库，不连接Caché，不修改原13接口。"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
from contextlib import closing
from dataclasses import asdict, replace
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import psycopg2  # noqa: E402
from accept_periop_projection import SOURCE_TABLES, fingerprint, verify_fields  # noqa: E402
from preflight_periop_projection import evaluate  # noqa: E402
from psycopg2 import sql  # noqa: E402
from psycopg2.extras import execute_values  # noqa: E402

from medqc_ingest.config import PassfilePostgresSettings  # noqa: E402
from medqc_ingest.domain import (  # noqa: E402
    ErrorKind,
    IngestError,
    RunMode,
    canonical_json,
    sha256_hex,
)
from medqc_ingest.periop_replay import (  # noqa: E402
    CDM_SOURCE_DATABASE,
    DISABLED,
    EXPECTED_COUNTS,
    PROFILE,
    SOURCE_DATABASE,
    PeriopRepository,
    SnapshotSource,
    explicit_window,
    load_profile,
    require,
    validate_database,
)
from medqc_ingest.repositories.postgres import PostgresCdmRepository  # noqa: E402
from medqc_ingest.service import ExtractService, PublishService  # noqa: E402


def check_acl(path):
    """拒绝额外主体、继承规则和非FullControl；只读检查，不重写既有凭据ACL。"""
    require(path.is_absolute() and path.exists(), "periop_protected_path_missing")
    script = r"""
$ErrorActionPreference='Stop'
$a=Get-Acl -LiteralPath $env:MEDQC_ACL_PATH
$r=@($a.Access | ForEach-Object {
 @{sid=$_.IdentityReference.Translate([System.Security.Principal.SecurityIdentifier]).Value;
 rights=[int]$_.FileSystemRights; inherited=$_.IsInherited; type=[int]$_.AccessControlType}
})
@{protected=$a.AreAccessRulesProtected;rules=$r}|ConvertTo-Json -Depth 4 -Compress
"""
    result = subprocess.run(
        ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", script],
        env=dict(os.environ, MEDQC_ACL_PATH=str(path)),
        capture_output=True,
        check=False,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    require(result.returncode == 0, "periop_acl_query_failed")
    doc = json.loads(result.stdout.decode("utf-8-sig"))
    rules = doc["rules"]
    require(
        doc["protected"]
        and len(rules) == 2
        and {r["sid"] for r in rules} == {"S-1-5-18", "S-1-5-32-544"}
        and all(r["rights"] == 2032127 and not r["inherited"] and r["type"] == 0 for r in rules),
        "periop_acl_not_restricted",
    )


def names(suffix):
    return {
        role: validate_database(f"medqc_periop_{role}_takeover_{suffix}", role)
        for role in ("ingest", "cdm", "restore_ingest", "restore_cdm")
    }


def connect(args, database, *, admin=False, readonly=False):
    allowed = {"postgres", SOURCE_DATABASE, CDM_SOURCE_DATABASE, *args.databases.values()}
    require(database in allowed, "periop_connection_database_scope")
    require(
        database not in {SOURCE_DATABASE, CDM_SOURCE_DATABASE} or readonly,
        "periop_source_readonly_required",
    )
    settings = setting(args, database, admin=admin)
    connection = psycopg2.connect(
        **settings.connection_kwargs(),
        options="-c timezone=UTC -c default_transaction_read_only=" + ("on" if readonly else "off"),
        application_name="medqc-periop-independent-takeover",
    )
    try:
        with connection.cursor() as cur:
            cur.execute(
                "SELECT current_database(),session_user,current_user,"
                "current_setting('transaction_read_only'),inet_server_port(),"
                "current_setting('server_version_num')::int, current_setting('cluster_name')"
            )
            actual = cur.fetchone()
        require(
            actual[:5]
            == (database, settings.user, settings.user, "on" if readonly else "off", args.port)
            and actual[5] // 10000 == args.pg_major,
            "periop_connection_identity",
        )
        if args.synthetic:
            require(
                args.port != 5432 and actual[6] == "medqc_periop_synthetic",
                "periop_synthetic_cluster_guard",
            )
        connection.rollback()
        return connection
    except BaseException:
        connection.close()
        raise


def setting(args, database, *, admin=False):
    return PassfilePostgresSettings(
        "127.0.0.1",
        args.port,
        database,
        args.admin_user if admin else "medqc_sync",
        args.admin_passfile if admin else args.runtime_passfile,
    )


def write_report(args, name, content):
    content = dict(content, contains_phi=False, contains_raw_values=False, contains_keys=False)
    with (args.output / "reports" / name).open("x", encoding="utf-8", newline="\n") as f:
        json.dump(content, f, ensure_ascii=False, indent=2, sort_keys=True)
        f.write("\n")


def safe_exception_chain(error):
    result, visited = [], set()
    while error is not None and id(error) not in visited and len(result) < 5:
        visited.add(id(error))
        code = getattr(error, "pgcode", None)
        result.append(
            {
                "exception_type": type(error).__name__,
                "sqlstate": code
                if isinstance(code, str) and re.fullmatch(r"[0-9A-Z]{5}", code)
                else None,
            }
        )
        error = error.__cause__ or error.__context__
    return result


def read_fingerprint(args, database, *, source=False):
    with closing(connect(args, database, admin=True, readonly=True)) as connection:
        return fingerprint(connection, source=source)


def native(args, tool, arguments, *, readonly=False):
    env = dict(os.environ, PGPASSFILE=str(args.admin_passfile))
    for name in ("PGPASSWORD", "PGSERVICE", "PGSERVICEFILE", "PGOPTIONS", "PGDATABASE"):
        env.pop(name, None)
    if readonly:
        env["PGOPTIONS"] = "-c default_transaction_read_only=on"
    executable = args.pg_bin / (tool + (".exe" if os.name == "nt" else ""))
    with (args.output / "private-logs" / (tool + ".log")).open("ab") as stream:
        result = subprocess.run(
            [
                str(executable),
                "-h",
                "127.0.0.1",
                "-p",
                str(args.port),
                "-U",
                args.admin_user,
                *arguments,
            ],
            env=env,
            stdout=stream,
            stderr=stream,
            check=False,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
    require(result.returncode == 0, "periop_native_" + tool)


def create_databases(args):
    with closing(connect(args, "postgres", admin=True)) as connection:
        connection.autocommit = True
        with connection.cursor() as cur:
            cur.execute(
                "SELECT rolname,rolcanlogin,rolsuper FROM pg_roles "
                "WHERE rolname IN ('medqc_owner','medqc_sync')"
            )
            require(
                {r[0]: r[1:] for r in cur.fetchall()}
                == {"medqc_owner": (False, False), "medqc_sync": (True, False)},
                "periop_existing_roles",
            )
            cur.execute("SELECT pg_has_role('medqc_sync','medqc_owner','MEMBER')")
            require(not cur.fetchone()[0], "periop_runtime_owner_membership")
            cur.execute(
                "SELECT datname FROM pg_database WHERE datname=ANY(%s)",
                (list(args.databases.values()),),
            )
            require(not cur.fetchall(), "periop_target_exists_no_reuse")
            for name in args.databases.values():
                cur.execute(
                    sql.SQL(
                        "CREATE DATABASE {} OWNER medqc_owner ENCODING 'UTF8' TEMPLATE template0"
                    ).format(sql.Identifier(name))
                )


def initialize(args, specs):
    with (
        closing(connect(args, args.databases["ingest"], admin=True)) as connection,
        connection,
        connection.cursor() as cur,
    ):
        cur.execute("SET LOCAL ROLE medqc_owner")
        migrations = sorted((ROOT / "migrations").glob("00[1-5]_*.sql"))
        require(len(migrations) == 5, "periop_storage_migration_inventory")
        for path in migrations:
            body = path.read_text(encoding="utf-8")
            require(
                len(re.findall(r"(?m)^BEGIN;\s*$", body)) == 1
                and body.rstrip().endswith("COMMIT;"),
                "periop_storage_migration",
            )
            body = re.sub(r"(?m)^BEGIN;\s*$", "", body, count=1)
            cur.execute(body.rstrip()[: -len("COMMIT;")])
        # 仅全新空库：移除通用迁移的默认种子，单独注册第二批。
        cur.execute("DELETE FROM sync_ops.source_interface")
        for spec in specs.values():
            cur.execute(
                "INSERT INTO sync_ops.source_interface (interface_name,procedure_name,"
                "argument_count,key_fields,publish_target,is_enabled,evidence_version) "
                "VALUES (%s,%s,1,%s::jsonb,%s,true,%s)",
                (
                    spec.name,
                    spec.procedure,
                    canonical_json(spec.key_fields),
                    spec.publish_target,
                    spec.evidence_version,
                ),
            )
        cur.execute(
            "CREATE INDEX periop_archive_batch ON takeover_archive.source_row "
            "(source_table,((record_json->>'batch_id')::bigint))"
        )
        cur.execute("GRANT USAGE ON SCHEMA cache_raw,sync_ops,takeover_archive TO medqc_sync")
        cur.execute(
            "GRANT SELECT ON ALL TABLES IN SCHEMA cache_raw,sync_ops,takeover_archive TO medqc_sync"
        )
        for table in (
            "cache_raw.source_record",
            "sync_ops.source_schema",
            "sync_ops.sync_batch",
            "sync_ops.publish_batch",
            "sync_ops.publish_lineage",
        ):
            cur.execute(
                sql.SQL("GRANT INSERT,UPDATE ON {} TO medqc_sync").format(
                    sql.Identifier(*table.split("."))
                )
            )
        cur.execute("GRANT INSERT ON cache_raw.source_record_version TO medqc_sync")
        cur.execute(
            "GRANT USAGE,SELECT ON ALL SEQUENCES IN SCHEMA cache_raw,sync_ops TO medqc_sync"
        )


def archive(args):
    result = {}
    with (
        closing(connect(args, SOURCE_DATABASE, readonly=True)) as source,
        closing(connect(args, args.databases["ingest"], admin=True)) as target,
        target,
    ):
        with source.cursor() as cur:
            cur.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY")
        for table in sorted(SOURCE_TABLES):
            with source.cursor() as cur:
                cur.execute(
                    "SELECT column_name,data_type,udt_name,is_nullable,column_default "
                    "FROM information_schema.columns WHERE table_schema=%s "
                    "AND table_name=%s ORDER BY ordinal_position",
                    table.split("."),
                )
                columns = cur.fetchall()
            with target.cursor() as cur:
                cur.execute(
                    "INSERT INTO takeover_archive.source_catalog VALUES (%s,%s::jsonb)",
                    (table, canonical_json(columns)),
                )
                digest, count = hashlib.sha256(), 0
                with source.cursor(name="periop_archive_table") as rows:
                    rows.execute(
                        sql.SQL("SELECT to_jsonb(t) FROM {} t ORDER BY to_jsonb(t)::text").format(
                            sql.Identifier(*table.split("."))
                        )
                    )
                    while chunk := rows.fetchmany(500):
                        values = []
                        for (record,) in chunk:
                            count += 1
                            text = canonical_json(record)
                            row_hash = sha256_hex(text)
                            digest.update((row_hash + "\n").encode())
                            values.append((table, count, text, row_hash))
                        execute_values(
                            cur,
                            "INSERT INTO takeover_archive.source_row VALUES %s",
                            values,
                            template="(%s,%s,%s::jsonb,%s)",
                        )
                result[table] = {"rows": count, "digest": digest.hexdigest()}
    require(
        result["cache_raw.record_current"]["rows"] == 9365
        and result["cache_raw.record_version"]["rows"] == 9365
        and result["cache_raw.snapshot_row"]["rows"] == 18730,
        "periop_archive_inventory",
    )
    verify_archive(args, result)
    return result


def verify_archive(args, expected):
    result = {}
    with closing(connect(args, args.databases["ingest"], readonly=True)) as connection:
        for table in sorted(SOURCE_TABLES):
            digest, count = hashlib.sha256(), 0
            with connection.cursor(name="periop_archive_verify") as cur:
                cur.execute(
                    "SELECT record_json,record_hash FROM takeover_archive.source_row "
                    "WHERE source_table=%s ORDER BY row_number",
                    (table,),
                )
                while chunk := cur.fetchmany(500):
                    for record, row_hash in chunk:
                        require(
                            sha256_hex(canonical_json(record)) == row_hash,
                            "periop_archive_row_hash",
                        )
                        digest.update((row_hash + "\n").encode())
                        count += 1
            result[table] = {"rows": count, "digest": digest.hexdigest()}
    require(result == expected, "periop_archive_fingerprint")


def archived_batches(args):
    with (
        closing(connect(args, args.databases["ingest"], readonly=True)) as connection,
        connection.cursor() as cur,
    ):
        cur.execute(
            "SELECT record_json,record_hash FROM takeover_archive.source_row "
            "WHERE source_table='cache_raw.snapshot_batch' "
            "ORDER BY (record_json->>'round_no')::int,"
            "(record_json->>'batch_id')::bigint"
        )
        records = cur.fetchall()
    require(len(records) == 95, "periop_archived_batch_inventory")
    for record, digest in records:
        require(sha256_hex(canonical_json(record)) == digest, "periop_archive_batch_hash")
    return [row for row, _ in records]


def replay(args, spec, batch, *, fail_after=None):
    spec = replace(spec, evidence_version=spec.evidence_version + f";legacy:{batch['batch_id']}")
    source = lambda: SnapshotSource(  # noqa: E731 - 延迟打开独立只读连接
        lambda: connect(args, args.databases["ingest"], readonly=True),
        batch,
        fail_after,
    )
    return ExtractService(
        source, PeriopRepository(setting(args, args.databases["ingest"]), spec), 500
    ).run(spec, batch["source_date"], RunMode.REPLAY, *explicit_window(batch["source_date"]))


def publish(args, spec):
    return PublishService(
        PeriopRepository(setting(args, args.databases["ingest"]), spec),
        PostgresCdmRepository(setting(args, args.databases["cdm"])),
        500,
    ).run(spec)


def verify_counts(args):
    with (
        closing(connect(args, args.databases["ingest"], readonly=True)) as connection,
        connection.cursor() as cur,
    ):
        for table in ("cache_raw.source_record", "cache_raw.source_record_version"):
            cur.execute(
                sql.SQL("SELECT interface_name,count(*) FROM {} GROUP BY 1").format(
                    sql.Identifier(*table.split("."))
                )
            )
            require(dict(cur.fetchall()) == EXPECTED_COUNTS, "periop_formal_row_counts")
        cur.execute("SELECT count(*) FROM sync_ops.sync_checkpoint")
        require(cur.fetchone()[0] == 0, "periop_checkpoint_must_be_empty")
        cur.execute("SELECT count(*) FROM sync_ops.sync_batch WHERE status='running'")
        require(cur.fetchone()[0] == 0, "periop_running_batch")


def link_legacy_batch(args, spec, batch):
    evidence = spec.evidence_version + f";legacy:{batch['batch_id']}"
    with (
        closing(connect(args, args.databases["ingest"], admin=True)) as connection,
        connection,
        connection.cursor() as cur,
    ):
        cur.execute(
            "SELECT batch_id,status FROM sync_ops.sync_batch WHERE evidence_version=%s", (evidence,)
        )
        rows = cur.fetchall()
        require(
            len(rows) == 1
            and rows[0][1] == ("failed" if batch["status"] == "failed" else "succeeded"),
            "periop_origin_batch_link",
        )
        cur.execute(
            "INSERT INTO sync_ops.takeover_batch_map VALUES (%s,%s)",
            (batch["batch_id"], rows[0][0]),
        )


def grant_cdm(args, specs):
    with (
        closing(connect(args, args.databases["cdm"], admin=True)) as connection,
        connection,
        connection.cursor() as cur,
    ):
        cur.execute("SELECT version_num FROM public.alembic_version")
        require(cur.fetchall() == [("20261031_000057",)], "periop_cdm_revision")
        cur.execute("REVOKE ALL ON SCHEMA cdm FROM medqc_sync")
        cur.execute("REVOKE ALL ON ALL TABLES IN SCHEMA cdm FROM medqc_sync")
        cur.execute("GRANT USAGE ON SCHEMA cdm TO medqc_sync")
        for spec in specs.values():
            cur.execute(
                sql.SQL("GRANT SELECT,INSERT,UPDATE ON {} TO medqc_sync").format(
                    sql.Identifier(*spec.publish_target.split("."))
                )
            )


def data_fingerprint(args):
    all_data = read_fingerprint(args, args.databases["ingest"])
    return {
        t: v
        for t, v in all_data["tables"].items()
        if t
        in {
            "cache_raw.source_record",
            "cache_raw.source_record_version",
            "sync_ops.source_schema",
            "sync_ops.sync_checkpoint",
        }
    }


def run(args):
    args.phase = "scope_and_acl"
    require(not os.getenv("PGPASSWORD"), "periop_pgpassword_forbidden")
    require(
        re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", args.admin_user) is not None,
        "periop_admin_identifier",
    )
    args.databases = names(args.suffix)
    require(not args.output.exists(), "periop_new_run_directory_required")
    contract, specs = load_profile(ROOT / "contracts/periop-acceptance-contracts.json")
    if not args.synthetic:
        require(os.name == "nt" and args.pg_major == 16, "periop_customer_platform")
        for path in (args.admin_passfile, args.runtime_passfile, args.output.parent):
            check_acl(path)
    else:
        # 此标志只放宽合成环境ACL/版本；所有连接另核验独立集群名和非5432端口。
        require(args.port != 5432, "periop_synthetic_port")
    for path in (args.admin_passfile, args.runtime_passfile):
        require(path.is_file(), "periop_existing_passfile")
    args.output.mkdir()
    for folder in ("reports", "backups", "private-logs"):
        (args.output / folder).mkdir()
    write_report(
        args,
        "database-plan.json",
        {
            "databases": args.databases,
            "profile": PROFILE,
            "disabled": DISABLED,
            "cache_accessed": False,
            "automatic_incremental": False,
        },
    )
    args.phase = "source_readonly_preflight"
    before = {
        db: read_fingerprint(args, db, source=db == SOURCE_DATABASE)
        for db in (SOURCE_DATABASE, CDM_SOURCE_DATABASE)
    }
    with closing(connect(args, SOURCE_DATABASE, readonly=True)) as source:
        preflight = evaluate(source, contract)
    require(
        all(
            row["status"] in {"candidate_ready", "candidate_ready_partial_source"}
            for row in preflight[0]
            if row["interface"] in specs
        ),
        "periop_source_preflight_blocked",
    )
    write_report(
        args,
        "source-preflight.json",
        {"status": "passed", "source_writes": False, "details": preflight},
    )
    args.phase = "create_isolated_databases"
    create_databases(args)
    initialize(args, specs)
    backup = args.output / "backups/source-cdm.dump"
    native(args, "pg_dump", ["-Fc", "-d", CDM_SOURCE_DATABASE, "-f", str(backup)], readonly=True)
    native(args, "pg_restore", ["--exit-on-error", "-d", args.databases["cdm"], str(backup)])
    require(
        read_fingerprint(args, args.databases["cdm"]) == before[CDM_SOURCE_DATABASE],
        "periop_initial_clone_fingerprint",
    )
    grant_cdm(args, specs)
    args.phase = "archive_and_normalize"
    archived = archive(args)
    write_report(
        args,
        "archive.json",
        {
            "tables": archived,
            "legacy_hashes_preserved": True,
            "new_hash_format": "canonical-dictionary-v1",
        },
    )
    batches, imported, failures = archived_batches(args), [], 0
    for batch in batches:
        if batch["interface_name"] not in specs:
            continue
        try:
            result = replay(args, specs[batch["interface_name"]], batch)
            require(
                batch["status"] != "failed"
                and result.counts["fetched"] == batch["row_count"]
                and result.checkpoint_state == "held",
                "periop_normalize_counts",
            )
            if batch["round_no"] == 2:
                require(
                    result.counts["inserted"] == result.counts["updated"] == 0,
                    "periop_round2_idempotency",
                )
            imported.append(
                {
                    "interface": batch["interface_name"],
                    "source_date": batch["source_date"],
                    "round": batch["round_no"],
                    **asdict(result),
                }
            )
        except IngestError as exc:
            if batch["status"] != "failed" or exc.location != "periop_preserved_vendor_failure":
                raise
            failures += 1
        link_legacy_batch(args, specs[batch["interface_name"]], batch)
    require(len(imported) == 70 and failures == 4, "periop_historical_batch_totals")
    verify_counts(args)
    with (
        closing(connect(args, args.databases["ingest"], admin=True)) as connection,
        connection,
        connection.cursor() as cur,
    ):
        cur.execute(
            "INSERT INTO sync_ops.takeover_marker(marker_id,source_database,report_json) "
            "VALUES (1,%s,%s::jsonb)",
            (
                SOURCE_DATABASE,
                canonical_json(
                    {
                        "profile": PROFILE,
                        "archives": archived,
                        "raw_rows": 9365,
                        "history_rows": 9365,
                        "mapped_batches": 74,
                        "historical_source_failures": 4,
                        "source_writes": False,
                    }
                ),
            ),
        )
    write_report(
        args,
        "import.json",
        {
            "successes": imported,
            "historical_source_failures": failures,
            "excluded_batches_archived": 21,
            "raw_rows": 9365,
            "history_rows": 9365,
        },
    )
    args.phase = "two_round_publish"
    projected = []
    for number in (1, 2):
        for spec in specs.values():
            result = publish(args, spec)
            require(
                result.selected == EXPECTED_COUNTS[spec.name] and result.written == 0,
                "periop_publish_existing_clone_changed",
            )
            projected.append({"interface": spec.name, "round": number, **asdict(result)})
    with (
        closing(connect(args, SOURCE_DATABASE, readonly=True)) as source,
        closing(connect(args, args.databases["cdm"], readonly=True)) as target,
    ):
        equality = [
            {
                "interface": item["interface"],
                "all_fields_equal": True,
                "fields": verify_fields(source, target, contract, item),
            }
            for item in contract["interfaces"]
            if item["interface"] in specs
        ]
    write_report(args, "publish.json", {"rounds": projected, "field_equality": equality})
    args.phase = "failure_rollback_and_recovery"
    batch = next(
        b
        for b in batches
        if b["interface_name"] == "web.nursing_record"
        and b["round_no"] == 1
        and b["row_count"] > 500
    )
    stable = data_fingerprint(args)
    try:
        replay(args, specs[batch["interface_name"]], batch, fail_after=500)
        raise IngestError(ErrorKind.PUBLISH_CONTRACT, "periop_injection_did_not_fail")
    except IngestError as exc:
        require(exc.location == "periop_injected_fetch_failure", "periop_injection_wrong_failure")
    require(data_fingerprint(args) == stable, "periop_rollback_data_changed")
    result = replay(args, specs[batch["interface_name"]], batch)
    require(
        result.counts["inserted"] == result.counts["updated"] == 0, "periop_recovery_idempotency"
    )
    require(publish(args, specs[batch["interface_name"]]).written == 0, "periop_recovery_publish")
    with (
        closing(connect(args, args.databases["ingest"], readonly=True)) as connection,
        connection.cursor() as cur,
    ):
        cur.execute(
            "SELECT error_location,count(*) FROM sync_ops.sync_batch "
            "WHERE status='failed' GROUP BY 1"
        )
        require(
            dict(cur.fetchall())
            == {"periop_preserved_vendor_failure": 4, "periop_injected_fetch_failure": 1},
            "periop_failure_audit",
        )
    verify_counts(args)
    verify_archive(args, archived)
    write_report(
        args,
        "recovery.json",
        {
            "rollback_verified": True,
            "recovery_verified": True,
            "historical_source_failures": 4,
            "intentional_injected_failures": 1,
        },
    )
    args.phase = "backup_restore"
    restore_reports = {}
    for role in ("ingest", "cdm"):
        origin, restored = args.databases[role], args.databases["restore_" + role]
        snapshot = read_fingerprint(args, origin)
        path = args.output / "backups" / (role + ".dump")
        native(args, "pg_dump", ["-Fc", "-d", origin, "-f", str(path)], readonly=True)
        native(args, "pg_restore", ["--exit-on-error", "-d", restored, str(path)])
        require(read_fingerprint(args, restored) == snapshot, "periop_restore_fingerprint")
        restore_reports[role] = {
            "fingerprint_equal": True,
            "bytes": path.stat().st_size,
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        }
    write_report(args, "backup-restore.json", restore_reports)
    args.phase = "source_protection"
    after = {db: read_fingerprint(args, db, source=db == SOURCE_DATABASE) for db in before}
    require(before == after, "periop_source_changed")
    runtime = {
        "profile": PROFILE,
        "databases": args.databases,
        "port": args.port,
        "runtime_passfile": str(args.runtime_passfile),
        "contract_sha256": hashlib.sha256(
            (ROOT / "contracts/periop-acceptance-contracts.json").read_bytes()
        ).hexdigest(),
        "date_semantics": "unverified",
        "source": "archive",
        "automatic_incremental": False,
    }
    with (args.output / "runtime.json").open("x", encoding="utf-8", newline="\n") as f:
        json.dump(runtime, f, indent=2)
        f.write("\n")
    write_report(
        args,
        "acceptance.json",
        {
            "status": "PERIOP_ARCHIVE_TAKEOVER_ACCEPTED",
            "profile": PROFILE,
            "active_interfaces": 13,
            "disabled_interfaces": DISABLED,
            "raw_rows": 9365,
            "history_rows": 9365,
            "source_unchanged": True,
            "source_writes": False,
            "cache_accessed": False,
            "checkpoint_created": False,
            "old13_accessed": False,
            "business_database_accessed": False,
            "automatic_incremental": False,
            "scheduled_task_created": False,
            "synthetic": args.synthetic,
            "postgres_major": args.pg_major,
            "historical_source_failures": 4,
            "intentional_injected_failures": 1,
            "limitations": [
                "date_semantics_unverified",
                "no_live_cache_reextract",
                "partial_source_windows_preserved",
                "not_production_enabled",
            ],
        },
    )
    print("PERIOP_ARCHIVE_TAKEOVER_ACCEPTED")


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--admin-passfile", required=True, type=Path)
    parser.add_argument("--runtime-passfile", required=True, type=Path)
    parser.add_argument("--pg-bin", required=True, type=Path)
    parser.add_argument("--admin-user", default="postgres")
    parser.add_argument("--port", type=int, default=5432)
    parser.add_argument("--pg-major", type=int, default=16)
    parser.add_argument("--suffix", default=datetime.now().strftime("%Y%m%d%H%M%S"))
    parser.add_argument("--synthetic", action="store_true", help="仅独立标记的合成集群可用")
    args = parser.parse_args(argv)
    os.environ["MEDQC_PG_DRIVER"] = "psycopg2"
    try:
        run(args)
        return 0
    except Exception as exc:
        # 保留可诊断的类型/SQLSTATE，不打印可能包含正文或口令的原始消息。
        report = {
            "status": "failed",
            "phase": getattr(args, "phase", "arguments"),
            "exception_type": type(exc).__name__,
            "sqlstate": getattr(exc, "pgcode", None),
            "location": exc.location if isinstance(exc, IngestError) else None,
            "exception_chain": safe_exception_chain(exc),
        }
        if (args.output / "reports").is_dir():
            write_report(args, "failure.json", report)
        print(json.dumps(report), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
