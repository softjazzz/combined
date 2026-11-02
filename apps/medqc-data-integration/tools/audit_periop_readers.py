"""只读第二批独立CDM库，调用原样正式bundle/LX0609入口；不扩注册、不运行规则。"""

from __future__ import annotations

import argparse
import hashlib
import importlib
import json
import os
import re
import sys
from collections import Counter
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import patch

import dotenv
import sqlalchemy as sa
from periop_reader_regression import (
    ReaderRegressionError,
    compare_baseline,
    verify_directory_metadata,
)
from sqlalchemy.engine import URL, Engine

ROOT = Path(__file__).resolve().parents[1]
DATABASE = "medqc_periop_cdm_acceptance_20261031212605"
REVISION = "20261031_000057"
EXPECTED_RESULT_SHA256 = "417d530eb4eb6eb226546ee0a01c6828b467e8fa122d662650bdef119f3a2b91"


class AuditError(Exception):
    """仅含受控位置码；不包含SQL参数或原始异常消息。"""


def report(folder, name, content):
    with (folder / name).open("x", encoding="utf-8", newline="\n") as f:
        json.dump(content, f, ensure_ascii=False, sort_keys=True, indent=2)
        f.write("\n")


def digest_rows(rows, fields):
    # 仅在内存比较；逐行内容及hash均不导出。
    return Counter(
        json.dumps(
            {key: row.get(key) for key in fields}, sort_keys=True, ensure_ascii=False, default=str
        )
        for row in rows
    )


def compare_read_rows(expected, actual, *, truncated=False):
    fields = sorted(set().union(*(set(row) for row in actual)))
    if any(set(row) != set(fields) for row in actual):
        raise AuditError("inconsistent_reader_fields")
    if fields and any(not set(fields).issubset(row) for row in expected):
        raise AuditError("reader_returned_non_source_field")
    a, b = digest_rows(expected, fields), digest_rows(actual, fields)
    if (not truncated and a != b) or (truncated and any(n > a[k] for k, n in b.items())):
        raise AuditError("reader_values_or_multiplicity_mismatch")
    return fields


def field_profile(table, channel, expected, actual, all_fields, available, *, truncated=False):
    profiles = []
    for field in all_fields:
        nonempty = sum(row.get(field) is not None and row.get(field) != "" for row in expected)
        present = field in available
        returned = sum(row.get(field) is not None and row.get(field) != "" for row in actual)
        profiles.append(
            {
                "table": table,
                "channel": channel,
                "field": field,
                "cdm_nonempty": nonempty,
                "returned_nonempty": returned,
                "field_selected": present,
                "truncated": truncated,
                "status": "not_exposed" if not present else "exposed_values_verified",
            }
        )
    return profiles


def fingerprint(connection):
    result = {"tables": {}, "sequences": {}}
    tables = connection.exec_driver_sql(
        "SELECT schemaname,tablename FROM pg_tables WHERE "
        "schemaname NOT IN ('pg_catalog','information_schema') ORDER BY 1,2"
    ).all()
    for schema, table in tables:
        # 元数据标识使用方言quote，不拼接临床值。
        quote = connection.dialect.identifier_preparer.quote_identifier
        qualified = quote(schema) + "." + quote(table)
        rows = connection.exec_driver_sql(
            "SELECT md5(to_jsonb(t)::text),count(*) FROM " + qualified + " t GROUP BY 1 ORDER BY 1"
        )
        digest = hashlib.sha256()
        count = 0
        for value, n in rows:
            digest.update(f"{value}:{n}\n".encode())
            count += n
        result["tables"][f"{schema}.{table}"] = {"rows": count, "hash": digest.hexdigest()}
    sequences = connection.exec_driver_sql(
        "SELECT schemaname,sequencename FROM pg_sequences "
        "WHERE schemaname NOT IN ('pg_catalog','information_schema') ORDER BY 1,2"
    ).all()
    for schema, name in sequences:
        quote = connection.dialect.identifier_preparer.quote_identifier
        result["sequences"][f"{schema}.{name}"] = list(
            connection.exec_driver_sql(
                "SELECT last_value,is_called FROM " + quote(schema) + "." + quote(name)
            ).one()
        )
    return result


@contextmanager
def official_readers(args):
    if args.database != DATABASE or not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", args.user):
        raise AuditError("database_or_user_scope")
    if not args.passfile.is_absolute() or not args.passfile.is_file() or os.getenv("PGPASSWORD"):
        raise AuditError("protected_passfile_required_no_pgpassword")
    url = URL.create(
        "postgresql+psycopg2",
        username=args.user,
        host="127.0.0.1",
        port=args.port,
        database=DATABASE,
    )
    options = "-c default_transaction_read_only=on -c timezone=UTC"

    def guard(_dialect, _record, _parameters, kwargs):
        if (
            kwargs.get("dbname") != DATABASE
            or kwargs.get("host") != "127.0.0.1"
            or kwargs.get("user") != args.user
            or int(kwargs.get("port", 0)) != args.port
            or kwargs.get("options") != options
            or kwargs.get("passfile") != str(args.passfile)
        ):
            raise AuditError("engine_connection_outside_scope")

    def sql_guard(_connection, _cursor, statement, _parameters, _context, _many):
        if not re.match(r"^\s*(SELECT|SHOW|WITH)\b", statement, re.I):
            raise AuditError("non_readonly_sql_blocked")

    sa.event.listen(Engine, "do_connect", guard)
    sa.event.listen(Engine, "before_cursor_execute", sql_guard)
    engine = sa.create_engine(
        url,
        connect_args={"passfile": str(args.passfile), "options": options, "connect_timeout": 15},
        pool_size=2,
        max_overflow=0,
        pool_pre_ping=True,
    )

    def identity(connection, _record):
        with connection.cursor() as cur:
            cur.execute(
                "SELECT current_database(),session_user,current_user,"
                "current_setting('transaction_read_only'),inet_server_port(),"
                "current_setting('server_version_num')::int"
            )
            result = cur.fetchone()
            if (
                result[:5] != (DATABASE, args.user, args.user, "on", args.port)
                or result[5] // 10000 != args.pg_major
            ):
                raise AuditError("readonly_identity")
        connection.rollback()

    sa.event.listen(engine, "connect", identity)
    before_path = list(sys.path)
    try:
        args.phase = "import_formal_readers"
        sys.path.insert(0, str(args.backend.resolve()))
        with (
            patch.object(dotenv, "load_dotenv", return_value=False),
            patch.dict(
                os.environ,
                {
                    "DATABASE_URL": "",
                    "REMOTE_DB_URL": "",
                    "DB_SCHEMA_MODE": "split",
                    "DB_SEARCH_PATH": "public,qc,sys,cdm,legacy",
                    "MEDQC_ALLOW_REAL_LLM": "0",
                },
            ),
        ):
            db = importlib.import_module("app.database.connection")
            with patch.object(db, "engine", engine):
                bundle = importlib.import_module("app.services.bundles.assembly")
                reader = importlib.import_module("app.services.luxian_0609.source_evidence_reader")
                with patch.object(bundle, "engine", engine):
                    bundle._get_table_columns.cache_clear()
                    yield engine, bundle, reader
    finally:
        sys.path[:] = before_path
        engine.dispose()
        sa.event.remove(Engine, "do_connect", guard)
        sa.event.remove(Engine, "before_cursor_execute", sql_guard)


def read_case(connection, table, coordinates):
    # table只来自经过白名单核验的17接口合同。
    return [
        dict(row)
        for row in connection.execute(
            sa.text(
                f'SELECT * FROM cdm."{table}" WHERE institute_id=:institute_id '
                "AND patient_id=:patient_id AND visit_id=:visit_id"
            ),
            coordinates,
        ).mappings()
    ]


def choose_cohort(connection, items, maximum=20):
    if maximum != 20:
        raise AuditError("fixed_cohort_bound")
    chosen = []
    candidates = []
    for item in items:
        table = item["publish_target"].split(".")[1]
        rows = connection.exec_driver_sql(
            f"SELECT institute_id,patient_id,visit_id,count(*) "
            f'FROM cdm."{table}" GROUP BY 1,2,3 ORDER BY count(*) DESC,1,2,3 LIMIT 20'
        ).all()
        # 每个有数据接口先选一个；再补最多20例，不只按护理数量挑选。
        if rows and tuple(rows[0][:3]) not in chosen:
            chosen.append(tuple(rows[0][:3]))
        candidates.extend(tuple(r[:3]) for r in rows)
    for key in candidates:
        if key not in chosen and len(chosen) < maximum:
            chosen.append(key)
    if len(chosen) > maximum:
        raise AuditError("cohort_limit")
    return [
        dict(zip(("institute_id", "patient_id", "visit_id"), key, strict=True)) for key in chosen
    ]


def audit(args):
    if args.output.exists():
        raise AuditError("new_output_directory_required")
    args.output.mkdir()
    contract = json.loads(args.contract.read_text(encoding="utf-8"))
    from periop_transform import ALLOWED

    if {i["interface"] for i in contract["interfaces"]} != ALLOWED or contract.get(
        "required_alembic_revision"
    ) != REVISION:
        raise AuditError("contract_scope")
    spec_path = getattr(args, "fix_spec", ROOT / "contracts/periop-reader-metadata-fix.json")
    spec = json.loads(spec_path.read_text(encoding="utf-8"))
    metadata_stats = Counter()
    with official_readers(args) as (engine, bundle, reader):
        args.phase = "fingerprint_and_cohort"
        with engine.connect() as c:
            before = fingerprint(c)
            if (
                c.exec_driver_sql("SELECT version_num FROM public.alembic_version").scalar_one()
                != REVISION
            ):
                raise AuditError("revision_mismatch")
            for item in contract["interfaces"]:
                if (
                    before["tables"][item["publish_target"]]["rows"]
                    != item["expected_first_round_rows"]
                ):
                    raise AuditError("target_row_count_changed")
                table = item["publish_target"].split(".")[1]
                actual_columns = {
                    col["name"] for col in sa.inspect(c).get_columns(table, schema="cdm")
                }
                if actual_columns != {col["name"] for col in item["target_columns"]}:
                    raise AuditError("target_columns_changed")
            cohort = choose_cohort(c, contract["interfaces"])
        totals = Counter()
        profiles = []
        time_stats = Counter()
        registrations = []
        cache = {}
        args.phase = "official_readers"
        for case in cohort:
            domains = {
                domain
                for item in contract["interfaces"]
                for domain, tables in bundle._DOMAIN_DOC_PRIORITY.items()
                if item["publish_target"].split(".")[1] in tables
            }
            cache[tuple(case.values())] = {
                domain: bundle.assemble_domain_bundle(
                    execution_domain=domain, source_schema="cdm", **case
                )
                for domain in sorted(domains)
            }
        totals["bundle_calls"] = sum(len(domains) for domains in cache.values())
        for item in contract["interfaces"]:
            table = item["publish_target"].split(".")[1]
            domains = [d for d, ts in bundle._DOMAIN_DOC_PRIORITY.items() if table in ts]
            registered = table in reader._SNAPSHOT_SOURCE_FIELDS
            registration = {
                "table": table,
                "source_state": item["source_state"],
                "source_rows": item["expected_first_round_rows"],
                "bundle_domains": domains,
                "lx0609_registered": registered,
            }
            registrations.append(registration)
            summary = {
                "table": table,
                "source_state": item["source_state"],
                "sampled_cdm_rows": 0,
                "bundle_calls": 0,
                "lx0609_calls": 0,
                "bundle_truncated_cases": 0,
                "lx0609_truncated_cases": 0,
            }
            field_rows = []
            for case in cohort:
                with engine.connect() as c:
                    expected = read_case(c, table, case)
                summary["sampled_cdm_rows"] += len(expected)
                fields = [col["name"] for col in item["target_columns"]]
                if domains:
                    # 多领域有相同表时只选第一个比较，避免重复计数。
                    result = cache[tuple(case.values())][domains[0]]
                    actual = [
                        {k: v for k, v in row.items() if k != "__document_type"}
                        for row in result["structured_context"]["documents"][table]
                    ]
                    projection = result["structured_context"]["domain_projection"]["per_source"][
                        table
                    ]
                    truncated = projection["has_more"]
                    available = compare_read_rows(expected, actual, truncated=truncated)
                    summary["bundle_calls"] += 1
                    summary["bundle_truncated_cases"] += int(truncated)
                    field_rows += field_profile(
                        table, "bundle", expected, actual, fields, available, truncated=truncated
                    )
                    totals["bundle_rows_compared"] += len(actual)
                    # 目录content是正式装配文本，不冒充raw正文；原文比较走documents.record_content。
                    inventory = [
                        r for r in result["source_documents"] if r["source_table"] == table
                    ]
                    if len(inventory) != len(actual):
                        raise AuditError("inventory_count_mismatch")
                    for entry, row in zip(inventory, actual, strict=True):
                        for field in verify_directory_metadata(
                            entry, row, spec["metadata_fields"].get(table, ())
                        ):
                            metadata_stats[(table, field)] += 1
                        if row.get("record_datetime") is not None:
                            time_stats["bundle_record_datetime_nonempty"] += 1
                            if entry["record_time"] != str(row["record_datetime"]).strip():
                                raise AuditError("inventory_record_time_mismatch")
                            time_stats["bundle_record_datetime_equal"] += 1
                else:
                    field_rows += field_profile(table, "bundle", expected, [], fields, [])
                if registered:
                    rows = reader.read_luxian_0609_snapshot_source_rows(
                        source_key=table, source_schema="cdm", **case
                    )
                    actual = [dict(row) for row in rows.rows]
                    available = compare_read_rows(expected, actual, truncated=rows.truncated)
                    summary["lx0609_calls"] += 1
                    totals["lx0609_calls"] += 1
                    summary["lx0609_truncated_cases"] += int(rows.truncated)
                    field_rows += field_profile(
                        table,
                        "lx0609",
                        expected,
                        actual,
                        fields,
                        available,
                        truncated=rows.truncated,
                    )
                    totals["lx0609_rows_compared"] += len(actual)
                    for row in actual:
                        if row.get("record_datetime") is not None:
                            time_stats["lx0609_record_datetime_nonempty"] += 1
                            if (
                                reader.authoritative_document_time_value(row)
                                != row["record_datetime"]
                            ):
                                raise AuditError("authoritative_time_mismatch")
                            time_stats["lx0609_record_datetime_equal"] += 1
                else:
                    field_rows += field_profile(table, "lx0609", expected, [], fields, [])
            if item["expected_first_round_rows"] and not summary["sampled_cdm_rows"]:
                raise AuditError("cohort_did_not_cover_source")
            # 空病例没有字段返回，不能抵销有样本病例的可见性；按实际比较的样本聚合。
            merged = {}
            for field in field_rows:
                key = (field["channel"], field["field"])
                value = merged.setdefault(
                    key,
                    {
                        **field,
                        "cdm_nonempty": 0,
                        "returned_nonempty": 0,
                        "observed_selected": False,
                        "truncated": False,
                    },
                )
                value["cdm_nonempty"] += field["cdm_nonempty"]
                value["returned_nonempty"] += field["returned_nonempty"]
                value["observed_selected"] |= field["field_selected"]
                value["truncated"] |= field["truncated"]
            for value in merged.values():
                value.pop("field_selected")
                value["status"] = (
                    "exposed_values_verified" if value["observed_selected"] else "not_exposed"
                )
            profiles.extend(merged.values())
            report(args.output, table + ".json", {**summary, "capabilities": registration})
        args.phase = "final_protection"
        with engine.connect() as c:
            if fingerprint(c) != before:
                raise AuditError("database_changed")
        report(args.output, "field-visibility.json", profiles)
        report(args.output, "source-registration.json", registrations)
        report(args.output, "time-equality.json", dict(time_stats))
        gaps = [p for p in profiles if p["cdm_nonempty"] and not p["observed_selected"]]
        report(args.output, "reader-gaps.json", gaps)
        report(
            args.output,
            "independent-metadata.json",
            [
                {"table": table, "field": field, "directory_values_equal": count}
                for (table, field), count in sorted(metadata_stats.items())
            ],
        )
        baseline_root = getattr(args, "baseline", None)
        regression = None
        if baseline_root is not None:
            baseline = json.loads(
                (baseline_root / "field-visibility.json").read_text(encoding="utf-8")
            )
            regression = compare_baseline(baseline, profiles, spec)
            for filename, value in [
                ("source-registration.json", registrations),
                ("time-equality.json", dict(time_stats)),
            ]:
                if json.loads((baseline_root / filename).read_text(encoding="utf-8")) != value:
                    raise ReaderRegressionError("registrations_or_record_times_changed")
            original = json.loads((baseline_root / "manifest.json").read_text(encoding="utf-8"))
            if original["sampled_rows_by_channel"] != dict(totals) or original[
                "cohort_cases"
            ] != len(cohort):
                raise ReaderRegressionError("cohort_aggregate_or_call_counts_changed")
            report(args.output, "metadata-regression.json", regression)
        summary = {
            "status": "PERIOP_METADATA_READER_REGRESSION_PASS"
            if regression is not None
            else "READONLY_READER_AUDIT_COMPLETE_WITH_COVERAGE_REPORT",
            "metadata_regression_verified": regression is not None,
            "database": DATABASE,
            "cohort_cases": len(cohort),
            "interfaces": 17,
            "sampled_rows_by_channel": dict(totals),
            "nonempty_field_gaps": len(gaps),
            "unregistered_lx0609_sources": [
                r["table"] for r in registrations if not r["lx0609_registered"]
            ],
            "real_rule_source_executed": totals["lx0609_calls"] > 0,
            "bundle_executed": totals["bundle_calls"] > 0,
            "database_unchanged": True,
            "database_writes": False,
            "cache_accessed": False,
            "original_thirteen_accessed": False,
            "business_database_accessed": False,
            "full_rule_engine_executed": False,
            "contains_phi": False,
            "contains_raw_values": False,
            "prior_projection_result_sha256": EXPECTED_RESULT_SHA256,
        }
        report(args.output, "manifest.json", summary)
        checks = "".join(
            f"{hashlib.sha256(p.read_bytes()).hexdigest()}  {p.name}\n"
            for p in sorted(args.output.glob("*.json"))
        )
        (args.output / "CHECKSUMS.txt").write_text(checks, encoding="utf-8", newline="\n")
        print(summary["status"])


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", choices=(DATABASE,), default=DATABASE)
    parser.add_argument("--passfile", type=Path, required=True)
    parser.add_argument("--user", default="postgres")
    parser.add_argument("--port", type=int, default=5432)
    parser.add_argument("--pg-major", type=int, default=16)
    parser.add_argument("--backend", type=Path, default=ROOT / "backend")
    parser.add_argument(
        "--contract", type=Path, default=ROOT / "contracts/periop-acceptance-contracts.json"
    )
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--baseline", type=Path, default=ROOT / "baseline" if (ROOT / "baseline").is_dir() else None
    )
    parser.add_argument(
        "--fix-spec", type=Path, default=ROOT / "contracts/periop-reader-metadata-fix.json"
    )
    args = parser.parse_args(argv)
    try:
        audit(args)
        return 0
    except Exception as error:
        original = getattr(error, "orig", error)
        print(
            json.dumps(
                {
                    "status": "failed",
                    "type": type(error).__name__,
                    "sqlstate": getattr(original, "pgcode", None),
                    "location": str(error)
                    if isinstance(error, (AuditError, ReaderRegressionError))
                    else getattr(args, "phase", "reader_audit"),
                    "missing_module": error.name
                    if isinstance(error, ModuleNotFoundError)
                    and re.fullmatch(r"[A-Za-z_][A-Za-z0-9_.]*", error.name or "")
                    else None,
                    "contains_phi": False,
                }
            )
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
