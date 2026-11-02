"""第二批真实ODBC显式日期验证；旧接管库只读，所有写入四个全新独立库。"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from contextlib import closing
from dataclasses import asdict
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import psycopg2  # noqa: E402
from accept_periop_projection import fingerprint  # noqa: E402
from prepare_periop_takeover import (  # noqa: E402
    check_acl,
    native,
    safe_exception_chain,
    setting,
    write_report,
)
from psycopg2 import sql  # noqa: E402

from medqc_ingest.domain import (  # noqa: E402
    IngestError,
    RunMode,
    project_record,
)
from medqc_ingest.periop_live import (  # noqa: E402
    BASELINE_CDM,
    BASELINE_INGEST,
    LIVE_PROFILE,
    StrictLiveSource,
    known_vendor_failure,
    live_database_names,
    live_spec,
    safe_odbc_diagnostic,
    source_settings,
    verify_baseline_evidence,
)
from medqc_ingest.periop_replay import (  # noqa: E402
    DISABLED,
    EXPECTED_COUNTS,
    PeriopRepository,
    explicit_window,
    load_profile,
    require,
)
from medqc_ingest.repositories.postgres import PostgresCdmRepository  # noqa: E402
from medqc_ingest.service import ExtractService, PublishService  # noqa: E402


def connect(args, database, *, admin=False, readonly=False):
    require(
        database in {"postgres", BASELINE_INGEST, BASELINE_CDM, *args.databases.values()},
        "periop_live_connection_scope",
    )
    require(
        database not in {BASELINE_INGEST, BASELINE_CDM} or readonly, "periop_live_baseline_readonly"
    )
    config = setting(args, database, admin=admin)
    connection = psycopg2.connect(
        **config.connection_kwargs(),
        application_name=LIVE_PROFILE,
        options="-c timezone=UTC -c default_transaction_read_only=" + ("on" if readonly else "off"),
    )
    try:
        with connection.cursor() as cur:
            cur.execute(
                "SELECT current_database(),session_user,current_user,"
                "current_setting('transaction_read_only'),inet_server_port(),"
                "current_setting('server_version_num')::int,current_setting('cluster_name')"
            )
            row = cur.fetchone()
        require(
            row[:5] == (database, config.user, config.user, "on" if readonly else "off", args.port)
            and row[5] // 10000 == args.pg_major,
            "periop_live_connection_identity",
        )
        if args.synthetic:
            require(
                row[6] == "medqc_periop_synthetic" and args.port != 5432,
                "periop_live_synthetic_guard",
            )
        connection.rollback()
        return connection
    except BaseException:
        connection.close()
        raise


def fp(args, database):
    with closing(connect(args, database, admin=True, readonly=True)) as connection:
        return fingerprint(connection)


def baseline_preflight(args, specs):
    with (
        closing(connect(args, BASELINE_INGEST, readonly=True)) as connection,
        connection.cursor() as cur,
    ):
        cur.execute("SELECT interface_name,count(*) FROM cache_raw.source_record GROUP BY 1")
        require(dict(cur.fetchall()) == EXPECTED_COUNTS, "periop_live_baseline_counts")
        cur.execute("SELECT count(*) FROM cache_raw.source_record_version")
        require(cur.fetchone()[0] == 9365, "periop_live_baseline_history")
        cur.execute("SELECT count(*) FROM sync_ops.sync_checkpoint")
        require(cur.fetchone()[0] == 0, "periop_live_baseline_checkpoint")
        cur.execute("SELECT interface_name FROM sync_ops.source_interface WHERE is_enabled")
        require({r[0] for r in cur.fetchall()} == set(specs), "periop_live_baseline_interfaces")
        cur.execute("SELECT report_json FROM sync_ops.takeover_marker WHERE marker_id=1")
        row = cur.fetchone()
        require(
            row is not None and row[0]["raw_rows"] == 9365 and row[0]["mapped_batches"] == 74,
            "periop_live_baseline_marker",
        )
    with (
        closing(connect(args, BASELINE_CDM, readonly=True)) as connection,
        connection.cursor() as cur,
    ):
        cur.execute("SELECT version_num FROM public.alembic_version")
        require(cur.fetchall() == [("20261031_000057",)], "periop_live_revision")


def create_clones(args):
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
                "periop_live_existing_roles",
            )
            cur.execute("SELECT pg_has_role('medqc_sync','medqc_owner','MEMBER')")
            require(not cur.fetchone()[0], "periop_live_runtime_not_owner")
            cur.execute(
                "SELECT datname FROM pg_database WHERE datname=ANY(%s)",
                (list(args.databases.values()),),
            )
            require(not cur.fetchall(), "periop_live_new_databases_required")
            for name in args.databases.values():
                cur.execute(
                    sql.SQL(
                        "CREATE DATABASE {} OWNER medqc_owner ENCODING 'UTF8' TEMPLATE template0"
                    ).format(sql.Identifier(name))
                )
    for role, baseline in (("ingest", BASELINE_INGEST), ("cdm", BASELINE_CDM)):
        backup = args.output / "backups" / ("baseline-" + role + ".dump")
        native(args, "pg_dump", ["-Fc", "-d", baseline, "-f", str(backup)], readonly=True)
        native(args, "pg_restore", ["--exit-on-error", "-d", args.databases[role], str(backup)])
        require(
            fp(args, args.databases[role]) == args.baseline_before[baseline],
            "periop_live_clone_fingerprint",
        )


def publish(args, spec):
    return PublishService(
        PeriopRepository(setting(args, args.databases["ingest"]), spec),
        PostgresCdmRepository(setting(args, args.databases["cdm"])),
        500,
    ).run(spec)


def verify_fields(args, spec):
    repository = PeriopRepository(setting(args, args.databases["ingest"]), spec)
    cursor = repository.open_verified_raw(spec.name, spec.publish.source_key_fields)
    fields, keys = spec.publish.target_columns, spec.publish.primary_key
    count = 0
    try:
        with (
            closing(connect(args, args.databases["cdm"], readonly=True)) as target,
            target.cursor() as cur,
        ):
            while chunk := cursor.fetchmany(500):
                expected = [
                    project_record(spec, record.payload, record.completed_at) for record in chunk
                ]
                key_values = [tuple(row[k] for k in keys) for row in expected]
                statement = sql.SQL("SELECT {} FROM {} WHERE ({}) IN ({})").format(
                    sql.SQL(",").join(map(sql.Identifier, fields)),
                    sql.Identifier(*spec.publish_target.split(".")),
                    sql.SQL(",").join(map(sql.Identifier, keys)),
                    sql.SQL(",").join(
                        sql.SQL("({})").format(sql.SQL(",").join(sql.Placeholder() for _ in keys))
                        for _ in expected
                    ),
                )
                cur.execute(statement, tuple(v for key in key_values for v in key))
                actual = [dict(zip(fields, row, strict=True)) for row in cur.fetchall()]
                indexed = {tuple(row[k] for k in keys): row for row in actual}
                require(
                    len(indexed) == len(expected)
                    and all(
                        indexed.get(key) == row
                        for key, row in zip(key_values, expected, strict=True)
                    ),
                    "periop_live_field_equality",
                )
                count += len(expected)
            cur.execute(
                sql.SQL("SELECT count(*) FROM {}").format(
                    sql.Identifier(*spec.publish_target.split("."))
                )
            )
            require(cur.fetchone()[0] == count, "periop_live_target_row_count")
    finally:
        cursor.close()
        repository.close()
    return {"interface": spec.name, "rows": count, "fields": len(fields), "all_fields_equal": True}


def protected_ingest(value):
    selected = {
        "takeover_archive.source_catalog",
        "takeover_archive.source_row",
        "sync_ops.takeover_marker",
        "sync_ops.takeover_batch_map",
        "sync_ops.sync_checkpoint",
    }
    return {table: data for table, data in value["tables"].items() if table in selected}


def audit_state(args):
    with (
        closing(connect(args, args.databases["ingest"], readonly=True)) as connection,
        connection.cursor() as cur,
    ):
        cur.execute("SELECT count(*) FROM sync_ops.sync_checkpoint")
        require(cur.fetchone()[0] == 0, "periop_live_checkpoint_not_advanced")
        cur.execute("SELECT count(*) FROM sync_ops.sync_batch WHERE status='running'")
        require(cur.fetchone()[0] == 0, "periop_live_running_batches")
        cur.execute(
            "SELECT count(*) FROM sync_ops.sync_batch WHERE evidence_version LIKE %s "
            "AND status='failed'",
            (LIVE_PROFILE + ";%",),
        )
        return int(cur.fetchone()[0])


def target_preflight(args, specs):
    for spec in specs.values():
        repository = PostgresCdmRepository(setting(args, args.databases["cdm"]))
        try:
            repository.begin()
            repository.prepare_target_contract(spec.publish)
        finally:
            repository.rollback()
            repository.close()
    write_report(args, "target-preflight.json", {"interfaces": 13, "target_catalog_verified": True})


def check_protection(args):
    require(
        all(fp(args, db) == value for db, value in args.baseline_before.items()),
        "periop_live_baseline_changed",
    )
    require(
        args.source_config.read_bytes() == args.source_config_before,
        "periop_live_source_config_changed",
    )
    return {
        "baseline_unchanged": True,
        "source_config_unchanged": True,
        "baseline_writes": False,
        "old13_database_accessed": False,
        "business_database_accessed": False,
    }


def run(args, *, source_factory=None):
    args.owns_output = False
    args.phase = "scope_preflight"
    explicit_window(args.date)
    require(not os.getenv("PGPASSWORD"), "periop_live_pgpassword_forbidden")
    require(not args.output.exists(), "periop_live_new_run_directory")
    require((source_factory is None) == (not args.synthetic), "periop_live_source_override_guard")
    require(
        args.pg_major == 16 and os.name == "nt" or args.synthetic, "periop_live_customer_platform"
    )
    args.databases = live_database_names(args.suffix)
    contract, old_specs = load_profile(ROOT / "contracts/periop-acceptance-contracts.json")
    specs = {name: live_spec(spec) for name, spec in old_specs.items()}
    items = {item["interface"]: item for item in contract["interfaces"]}
    require(not args.synthetic or args.port != 5432, "periop_live_synthetic_port")
    if not args.synthetic:
        for path in (
            args.output.parent,
            args.admin_passfile,
            args.runtime_passfile,
            args.source_config,
        ):
            check_acl(path)
    source_config = source_settings(args.source_config)
    if not args.synthetic:
        verify_baseline_evidence(
            json.loads((ROOT / "evidence/baseline-acceptance.json").read_text(encoding="utf-8")),
            json.loads((ROOT / "evidence/baseline-database-plan.json").read_text(encoding="utf-8")),
        )
    if not args.synthetic:
        check_acl(source_config.password_file)
    args.source_config_before = args.source_config.read_bytes()
    args.output.mkdir()
    args.owns_output = True
    for folder in ("reports", "backups", "private-logs"):
        (args.output / folder).mkdir()
    write_report(
        args,
        "database-plan.json",
        {
            "databases": args.databases,
            "explicit_date": args.date,
            "disabled": DISABLED,
            "automatic_incremental": False,
            "profile": LIVE_PROFILE,
        },
    )
    args.phase = "baseline_readonly"
    baseline_preflight(args, specs)
    args.baseline_before = {db: fp(args, db) for db in (BASELINE_INGEST, BASELINE_CDM)}
    args.phase = "isolated_clones"
    create_clones(args)
    target_preflight(args, specs)
    protected_before = protected_ingest(fp(args, args.databases["ingest"]))
    with (
        closing(connect(args, args.databases["ingest"], admin=True)) as connection,
        connection,
        connection.cursor() as cur,
    ):
        for spec in specs.values():
            cur.execute(
                "UPDATE sync_ops.source_interface SET evidence_version=%s WHERE interface_name=%s",
                (spec.evidence_version, spec.name),
            )
    make_source = source_factory or (lambda spec, phase: StrictLiveSource(source_config))
    args.phase = "live_dry"
    dry_before = {role: fp(args, args.databases[role]) for role in ("ingest", "cdm")}
    dry = []
    try:
        for spec in specs.values():
            try:
                result = ExtractService(lambda spec=spec: make_source(spec, "dry"), None, 500).run(
                    spec, args.date, RunMode.DRY, *explicit_window(args.date)
                )
                dry.append({"interface": spec.name, "status": "succeeded", **asdict(result)})
            except IngestError as error:
                if not known_vendor_failure(error, items[spec.name], args.date):
                    raise
                dry.append(
                    {
                        "interface": spec.name,
                        "status": "known_source_failure",
                        "sqlstate": "HY000",
                        "native": 400,
                    }
                )
    finally:
        dry_after = {role: fp(args, args.databases[role]) for role in ("ingest", "cdm")}
        require(dry_before == dry_after, "periop_live_dry_database_changed")
        write_report(
            args,
            "dry.json",
            {
                "interfaces": dry,
                "database_unchanged": True,
                "cache_accessed": not args.synthetic,
                "synthetic": args.synthetic,
            },
        )
    args.phase = "live_replay_publish"
    outcomes, fresh = [], set()
    for item in dry:
        spec = specs[item["interface"]]
        if item["status"] == "known_source_failure":
            outcomes.append({"interface": spec.name, "status": "not_replayed_source_failed_dry"})
            continue
        try:
            result = ExtractService(
                lambda spec=spec: make_source(spec, "replay"),
                PeriopRepository(setting(args, args.databases["ingest"]), spec),
                500,
            ).run(spec, args.date, RunMode.REPLAY, *explicit_window(args.date))
        except IngestError as error:
            if not known_vendor_failure(error, items[spec.name], args.date):
                raise
            outcomes.append(
                {
                    "interface": spec.name,
                    "status": "known_source_failure",
                    "sqlstate": "HY000",
                    "native": 400,
                }
            )
            continue
        require(result.checkpoint_state == "held", "periop_live_replay_checkpoint")
        published = publish(args, spec)
        fresh.add(spec.name)
        outcomes.append(
            {
                "interface": spec.name,
                "status": "succeeded",
                **asdict(result),
                "initial_publish": asdict(published),
            }
        )
    write_report(args, "replay.json", {"interfaces": outcomes, "checkpoint_advanced": False})
    args.phase = "publish_idempotency_fields"
    rounds = []
    for number in (1, 2):
        for spec in specs.values():
            result = publish(args, spec)
            require(result.written == 0, "periop_live_second_publish_not_idempotent")
            rounds.append(
                {
                    "interface": spec.name,
                    "round": number,
                    "fresh_read": spec.name in fresh,
                    **asdict(result),
                }
            )
    equality = [verify_fields(args, spec) for spec in specs.values()]
    failed_replays = audit_state(args)
    require(
        failed_replays == sum(row["status"] == "known_source_failure" for row in outcomes),
        "periop_live_failed_replay_audit",
    )
    require(
        protected_ingest(fp(args, args.databases["ingest"])) == protected_before,
        "periop_live_archive_or_checkpoint_changed",
    )
    write_report(args, "publish.json", {"rounds": rounds, "field_equality": equality})
    args.phase = "backup_restore"
    restored = {}
    for role in ("ingest", "cdm"):
        origin = args.databases[role]
        before = fp(args, origin)
        path = args.output / "backups" / (role + ".dump")
        native(args, "pg_dump", ["-Fc", "-d", origin, "-f", str(path)], readonly=True)
        native(
            args,
            "pg_restore",
            ["--exit-on-error", "-d", args.databases["restore_" + role], str(path)],
        )
        require(
            fp(args, args.databases["restore_" + role]) == before, "periop_live_restore_fingerprint"
        )
        restored[role] = {
            "fingerprint_equal": True,
            "bytes": path.stat().st_size,
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        }
    write_report(args, "backup-restore.json", restored)
    args.phase = "baseline_and_config_protection"
    write_report(args, "protection.json", check_protection(args))
    not_refreshed = sorted(set(specs) - fresh)
    status = "PERIOP_LIVE_SOURCE_VALIDATION_ACCEPTED" + (
        "_WITH_SOURCE_LIMITATIONS" if not_refreshed else ""
    )
    write_report(
        args,
        "acceptance.json",
        {
            "status": status,
            "explicit_date": args.date,
            "active_interfaces": 13,
            "fresh_interfaces": len(fresh),
            "not_refreshed_due_to_source_failure": not_refreshed,
            "disabled_interfaces": DISABLED,
            "partial_source_interfaces": [
                name for name in specs if items[name]["source_state"] == "partial_source"
            ],
            "date_semantics": "unverified",
            "raw_rows": sum(row["rows"] for row in equality),
            "source_config_unchanged": True,
            "baseline_unchanged": True,
            "archive_unchanged": True,
            "checkpoint_advanced": False,
            "old13_database_accessed": False,
            "business_database_accessed": False,
            "cache_accessed": not args.synthetic,
            "synthetic": args.synthetic,
            "postgres_major": args.pg_major,
            "automatic_incremental": False,
            "scheduled_task_created": False,
            "full_rule_engine_executed": False,
            "production_enabled": False,
        },
    )
    print(status)


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", required=True)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--source-config", required=True, type=Path)
    parser.add_argument("--admin-passfile", required=True, type=Path)
    parser.add_argument("--runtime-passfile", required=True, type=Path)
    parser.add_argument("--pg-bin", required=True, type=Path)
    parser.add_argument("--admin-user", default="postgres")
    parser.add_argument("--port", type=int, default=5432)
    parser.add_argument("--pg-major", type=int, default=16)
    parser.add_argument("--suffix", default=datetime.now().strftime("%Y%m%d%H%M%S"))
    args = parser.parse_args(argv)
    args.synthetic = False  # 客户CLI没有虚构来源开关；合成测试只通过程序注入并核验独立集群。
    args.owns_output = False
    os.environ["MEDQC_PG_DRIVER"] = "psycopg2"
    try:
        run(args)
        return 0
    except Exception as error:
        result = {
            "status": "failed",
            "phase": getattr(args, "phase", "arguments"),
            "location": error.location if isinstance(error, IngestError) else None,
            "exception_chain": safe_exception_chain(error),
            "odbc": safe_odbc_diagnostic(error),
        }
        if args.owns_output and (args.output / "reports").is_dir():
            if hasattr(args, "baseline_before"):
                try:
                    preservation = check_protection(args)
                except Exception as check_error:
                    preservation = {
                        "status": "not_verified",
                        "exception_chain": safe_exception_chain(check_error),
                    }
                write_report(args, "protection-on-failure.json", preservation)
            write_report(args, "failure.json", result)
        print(json.dumps(result), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
