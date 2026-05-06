from __future__ import annotations

import argparse
import csv
import json
import os
import sys
from pathlib import Path
from typing import Any

import psycopg2
import psycopg2.extras
import sqlalchemy as sa
from sqlalchemy import text

SCRIPT_DIR = Path(__file__).resolve().parent
BACKEND_ROOT = SCRIPT_DIR.parent
REPO_ROOT = BACKEND_ROOT.parents[2]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.database.connection import DATABASE_URL, engine as local_engine  # noqa: E402
from app.services.bundles.assembly import (  # noqa: E402
    BUNDLE_SCHEMA_VERSION_CURRENT,
    _DOMAIN_BUNDLE_TABLE,
    _DOMAIN_DOC_PRIORITY,
    _SCENE_BUNDLE_TABLE,
    _SCENE_DOC_PRIORITY,
)
from app.services.document_assembly import assemble_document  # noqa: E402
from app.services.etl_sync import expand_table_groups, get_remote_db_url  # noqa: E402

DEFAULT_OUTPUT_JSON = REPO_ROOT / "apps" / "medqc-web" / "docs" / "0418" / "QC" / "sample_source_coverage_audit.json"
DEFAULT_OUTPUT_CSV = REPO_ROOT / "apps" / "medqc-web" / "docs" / "0418" / "QC" / "sample_source_coverage_audit.csv"

DEFAULT_VISIT_IDS = (
    "1915580",
    "1966656",
    "1991072",
    "2024757",
    "2038297",
    "2033353",
    "2041227",
    "2042774",
    "2052129",
    "2059847",
    "2063648",
    "2068229",
    "2097628",
    "2104525",
    "2110349",
    "2113971",
    "2115142",
    "2123539",
    "2144246",
    "2153245",
    "2172686",
    "2191940",
    "2198524",
    "2200664",
    "2208257",
    "2209066",
    "2209876",
    "2243538",
    "2246915",
    "2259144",
    "2268187",
    "2276701",
    "2283295",
    "2287309",
    "2295919",
    "2297786",
    "2306811",
    "2307974",
    "2311318",
    "2313364",
    "2327691",
    "2330104",
    "2337741",
    "2333807",
)

SOURCE_ONLY_AUDIT_TABLES = (
    "inpat_execution_record",
)


def _safe_text(value: Any) -> str:
    return str(value or "").strip()


def _safe_identifier(value: str) -> str:
    if not value or not all(ch.isalnum() or ch == "_" for ch in value):
        raise ValueError(f"非法标识符: {value}")
    return value


def _read_visit_ids(path: str) -> list[str]:
    if not path:
        return list(DEFAULT_VISIT_IDS)
    source = Path(path)
    values: list[str] = []
    for line in source.read_text(encoding="utf-8", errors="ignore").splitlines():
        text_value = line.strip().strip(",")
        if not text_value:
            continue
        values.append(text_value)
    return list(dict.fromkeys(values))


def _table_columns_pg(conn, *, schema: str, table: str) -> list[dict[str, str]]:
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cursor:
        cursor.execute(
            """
            SELECT column_name, data_type
            FROM information_schema.columns
            WHERE table_schema = %s AND table_name = %s
            ORDER BY ordinal_position
            """,
            (schema, table),
        )
        return [dict(row) for row in cursor.fetchall() or []]


def _table_columns_local(conn: sa.Connection, *, table: str) -> tuple[str, list[dict[str, str]]]:
    rows = conn.execute(
        text(
            """
            SELECT table_schema
            FROM information_schema.tables
            WHERE table_schema IN ('cdm', 'public')
              AND table_name = :table
            ORDER BY CASE WHEN table_schema = 'cdm' THEN 0 ELSE 1 END
            LIMIT 1
            """
        ),
        {"table": table},
    ).mappings().all()
    if not rows:
        return "", []
    schema = _safe_text(rows[0]["table_schema"])
    columns = conn.execute(
        text(
            """
            SELECT column_name, data_type
            FROM information_schema.columns
            WHERE table_schema = :schema AND table_name = :table
            ORDER BY ordinal_position
            """
        ),
        {"schema": schema, "table": table},
    ).mappings().all()
    return schema, [dict(row) for row in columns]


def _count_rows_pg(conn, *, schema: str, table: str, visit_ids: list[str]) -> dict[str, int]:
    if not visit_ids:
        return {}
    schema_ident = _safe_identifier(schema)
    table_ident = _safe_identifier(table)
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cursor:
        cursor.execute(
            f"""
            SELECT visit_id::text AS visit_id, count(*) AS cnt
            FROM {schema_ident}.{table_ident}
            WHERE visit_id::text = ANY(%s)
            GROUP BY visit_id::text
            """,
            (visit_ids,),
        )
        return {_safe_text(row["visit_id"]): int(row["cnt"]) for row in cursor.fetchall() or []}


def _count_rows_local(conn: sa.Connection, *, schema: str, table: str, visit_ids: list[str]) -> dict[str, int]:
    if not visit_ids or not schema:
        return {}
    rows = conn.execute(
        text(
            f"""
            SELECT visit_id::text AS visit_id, count(*) AS cnt
            FROM {_safe_identifier(schema)}.{_safe_identifier(table)}
            WHERE visit_id::text = ANY(:visit_ids)
            GROUP BY visit_id::text
            """
        ),
        {"visit_ids": visit_ids},
    ).mappings().all()
    return {_safe_text(row["visit_id"]): int(row["cnt"]) for row in rows}


def _local_visit_keys(conn: sa.Connection, *, visit_ids: list[str]) -> dict[str, dict[str, str]]:
    if not visit_ids:
        return {}
    for table in ("mr", "admission_record"):
        schema, columns = _table_columns_local(conn, table=table)
        column_names = {item["column_name"] for item in columns}
        if not schema or not {"institute_id", "patient_id", "visit_id"}.issubset(column_names):
            continue
        rows = conn.execute(
            text(
                f"""
                SELECT institute_id::text AS institute_id, patient_id::text AS patient_id, visit_id::text AS visit_id
                FROM {_safe_identifier(schema)}.{_safe_identifier(table)}
                WHERE visit_id::text = ANY(:visit_ids)
                """
            ),
            {"visit_ids": visit_ids},
        ).mappings().all()
        result = {
            _safe_text(row["visit_id"]): {
                "institute_id": _safe_text(row["institute_id"]),
                "patient_id": _safe_text(row["patient_id"]),
                "visit_id": _safe_text(row["visit_id"]),
            }
            for row in rows
            if _safe_text(row["visit_id"])
        }
        if result:
            return result
    return {}


def _json_value(value: Any, default: Any) -> Any:
    if value is None:
        return default
    if isinstance(value, (dict, list)):
        return value
    try:
        return json.loads(str(value))
    except Exception:
        return default


def _table_exists_local(conn: sa.Connection, *, schema: str, table: str) -> bool:
    row = conn.execute(
        text(
            """
            SELECT 1
            FROM information_schema.tables
            WHERE table_schema = :schema AND table_name = :table
            LIMIT 1
            """
        ),
        {"schema": schema, "table": table},
    ).first()
    return bool(row)


def _bundle_rows_for_visit_ids(
    conn: sa.Connection,
    *,
    bundle_schema: str,
    bundle_table: str,
    visit_ids: list[str],
) -> list[dict[str, Any]]:
    if not visit_ids or not _table_exists_local(conn, schema=bundle_schema, table=bundle_table):
        return []
    rows = conn.execute(
        text(
            f"""
            SELECT visit_id::text AS visit_id, bundle_schema_version, bundle_updated_at,
                   structured_context, document_hits
            FROM {_safe_identifier(bundle_schema)}.{_safe_identifier(bundle_table)}
            WHERE visit_id::text = ANY(:visit_ids)
            """
        ),
        {"visit_ids": visit_ids},
    ).mappings().all()
    return [dict(row) for row in rows]


def _build_persistent_bundle_probe(
    conn: sa.Connection,
    *,
    table_names: list[str],
    visit_ids: list[str],
    bundle_schema: str,
) -> dict[str, dict[str, Any]]:
    probe = {
        table: {
            "scene_bundles": {},
            "domain_bundles": {},
            "bundle_hit_visit_count": 0,
            "bundle_assembled_visit_count": 0,
            "stale_bundle_count": 0,
        }
        for table in table_names
    }
    table_set = set(table_names)

    for scene, priority in _SCENE_DOC_PRIORITY.items():
        target_tables = [table for table in priority if table in table_set]
        if not target_tables:
            continue
        rows = _bundle_rows_for_visit_ids(
            conn,
            bundle_schema=bundle_schema,
            bundle_table=_SCENE_BUNDLE_TABLE[scene],
            visit_ids=visit_ids,
        )
        for table in target_tables:
            hit_visits: set[str] = set()
            assembled_visits: set[str] = set()
            stale_count = 0
            for row in rows:
                visit_id = _safe_text(row.get("visit_id"))
                if _safe_text(row.get("bundle_schema_version")) != BUNDLE_SCHEMA_VERSION_CURRENT:
                    stale_count += 1
                structured = _json_value(row.get("structured_context"), {})
                source_coverage = dict((structured or {}).get("source_table_coverage") or {})
                assembly_coverage = dict((structured or {}).get("assembly_coverage") or {})
                if int((source_coverage.get(table) or {}).get("row_count") or 0) > 0:
                    hit_visits.add(visit_id)
                if int((assembly_coverage.get(table) or {}).get("assembled_count") or 0) > 0:
                    assembled_visits.add(visit_id)
            probe[table]["scene_bundles"][scene] = {
                "bundle_rows": len(rows),
                "hit_visit_count": len(hit_visits),
                "assembled_visit_count": len(assembled_visits),
                "stale_bundle_count": stale_count,
            }
            probe[table]["bundle_hit_visit_count"] += len(hit_visits)
            probe[table]["bundle_assembled_visit_count"] += len(assembled_visits)
            probe[table]["stale_bundle_count"] += stale_count

    for domain, priority in _DOMAIN_DOC_PRIORITY.items():
        target_tables = [table for table in priority if table in table_set]
        if not target_tables:
            continue
        rows = _bundle_rows_for_visit_ids(
            conn,
            bundle_schema=bundle_schema,
            bundle_table=_DOMAIN_BUNDLE_TABLE[domain],
            visit_ids=visit_ids,
        )
        for table in target_tables:
            hit_visits: set[str] = set()
            assembled_visits: set[str] = set()
            stale_count = 0
            for row in rows:
                visit_id = _safe_text(row.get("visit_id"))
                if _safe_text(row.get("bundle_schema_version")) != BUNDLE_SCHEMA_VERSION_CURRENT:
                    stale_count += 1
                structured = _json_value(row.get("structured_context"), {})
                source_coverage = dict((structured or {}).get("source_table_coverage") or {})
                assembly_coverage = dict((structured or {}).get("assembly_coverage") or {})
                if int((source_coverage.get(table) or {}).get("row_count") or 0) > 0:
                    hit_visits.add(visit_id)
                if int((assembly_coverage.get(table) or {}).get("assembled_count") or 0) > 0:
                    assembled_visits.add(visit_id)
            probe[table]["domain_bundles"][domain] = {
                "bundle_rows": len(rows),
                "hit_visit_count": len(hit_visits),
                "assembled_visit_count": len(assembled_visits),
                "stale_bundle_count": stale_count,
            }
            probe[table]["bundle_hit_visit_count"] += len(hit_visits)
            probe[table]["bundle_assembled_visit_count"] += len(assembled_visits)
            probe[table]["stale_bundle_count"] += stale_count

    for table, item in probe.items():
        item["bundle_status"] = "not_in_bundle_priority"
        if item["scene_bundles"] or item["domain_bundles"]:
            item["bundle_status"] = "covered" if item["bundle_hit_visit_count"] > 0 else "bundle_missing_or_empty"
    return probe


def _assembly_probe(conn: sa.Connection, *, schema: str, table: str, visit_ids: list[str], limit: int) -> dict[str, Any]:
    if not schema or not visit_ids:
        return {"sample_count": 0, "assembled_count": 0, "statuses": {}, "used_source_fields": [], "data_quality_flags": []}
    rows = conn.execute(
        text(
            f"""
            SELECT *
            FROM {_safe_identifier(schema)}.{_safe_identifier(table)}
            WHERE visit_id::text = ANY(:visit_ids)
            LIMIT :limit_rows
            """
        ),
        {"visit_ids": visit_ids, "limit_rows": max(1, int(limit))},
    ).mappings().all()
    statuses: dict[str, int] = {}
    used_fields: set[str] = set()
    flags: set[str] = set()
    assembled_count = 0
    for row in rows:
        assembled = assemble_document(table, dict(row))
        statuses[assembled.assembly_status] = statuses.get(assembled.assembly_status, 0) + 1
        if assembled.assembled_text:
            assembled_count += 1
        for field in assembled.source_fields:
            if field.used:
                used_fields.add(field.source_field)
        flags.update(assembled.data_quality_flags)
    return {
        "sample_count": len(rows),
        "assembled_count": assembled_count,
        "statuses": statuses,
        "used_source_fields": sorted(used_fields),
        "data_quality_flags": sorted(flags),
    }


def build_audit(*, visit_ids: list[str], group_ids: list[str], remote_schema: str, sample_limit: int) -> dict[str, Any]:
    table_names, missing_groups = expand_table_groups(group_ids)
    audit_tables = list(dict.fromkeys([*table_names, *SOURCE_ONLY_AUDIT_TABLES]))
    remote_url = get_remote_db_url()
    if not remote_url:
        raise RuntimeError("REMOTE_DB_URL 未配置，无法审计源库")

    report_rows: list[dict[str, Any]] = []
    with psycopg2.connect(remote_url, connect_timeout=10) as remote_conn:
        remote_conn.set_session(readonly=True, autocommit=True)
        local_conn_ctx = local_engine.connect() if DATABASE_URL and local_engine is not None else None
        try:
            local_visit_keys = _local_visit_keys(local_conn_ctx, visit_ids=visit_ids) if local_conn_ctx is not None else {}
            bundle_probe = (
                _build_persistent_bundle_probe(
                    local_conn_ctx,
                    table_names=audit_tables,
                    visit_ids=visit_ids,
                    bundle_schema="public",
                )
                if local_conn_ctx is not None
                else {}
            )
            for table in audit_tables:
                remote_columns = _table_columns_pg(remote_conn, schema=remote_schema, table=table)
                remote_column_names = {row["column_name"] for row in remote_columns}
                remote_exists = bool(remote_columns)
                source_counts = (
                    _count_rows_pg(remote_conn, schema=remote_schema, table=table, visit_ids=visit_ids)
                    if remote_exists and "visit_id" in remote_column_names
                    else {}
                )

                local_schema = ""
                local_columns: list[dict[str, str]] = []
                local_counts: dict[str, int] = {}
                assembly = {
                    "sample_count": 0,
                    "assembled_count": 0,
                    "statuses": {},
                    "used_source_fields": [],
                    "data_quality_flags": [],
                }
                if local_conn_ctx is not None:
                    local_schema, local_columns = _table_columns_local(local_conn_ctx, table=table)
                    local_column_names = {row["column_name"] for row in local_columns}
                    if local_schema and "visit_id" in local_column_names:
                        local_counts = _count_rows_local(
                            local_conn_ctx,
                            schema=local_schema,
                            table=table,
                            visit_ids=visit_ids,
                        )
                        assembly = _assembly_probe(
                            local_conn_ctx,
                            schema=local_schema,
                            table=table,
                            visit_ids=visit_ids,
                            limit=sample_limit,
                        )
                else:
                    local_column_names = set()

                report_rows.append(
                    {
                        "table_name": table,
                        "remote_exists": remote_exists,
                        "local_exists": bool(local_columns),
                        "local_schema": local_schema,
                        "source_hit_visit_count": len(source_counts),
                        "source_total_rows": sum(source_counts.values()),
                        "local_hit_visit_count": len(local_counts),
                        "local_total_rows": sum(local_counts.values()),
                        "source_only_columns": sorted(remote_column_names - local_column_names),
                        "local_only_columns": sorted(local_column_names - remote_column_names),
                        "common_column_count": len(remote_column_names & local_column_names),
                        "missing_visit_ids_in_source": [item for item in visit_ids if item not in source_counts],
                        "missing_visit_ids_in_local": [item for item in visit_ids if item not in local_counts],
                        "assembly": assembly,
                        "persistent_bundle_coverage": bundle_probe.get(table, {}),
                        "source_only_audit": table in SOURCE_ONLY_AUDIT_TABLES,
                    }
                )
        finally:
            if local_conn_ctx is not None:
                local_conn_ctx.close()

    return {
        "remote_schema": remote_schema,
        "group_ids": group_ids,
        "missing_group_ids": missing_groups,
        "visit_count": len(visit_ids),
        "local_visit_key_count": len(local_visit_keys) if "local_visit_keys" in locals() else 0,
        "tables": report_rows,
    }


def write_reports(report: dict[str, Any], *, output_json: Path, output_csv: Path) -> None:
    output_json.parent.mkdir(parents=True, exist_ok=True)
    output_json.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    fieldnames = [
        "table_name",
        "remote_exists",
        "local_exists",
        "local_schema",
        "source_hit_visit_count",
        "source_total_rows",
        "local_hit_visit_count",
        "local_total_rows",
        "common_column_count",
        "source_only_audit",
        "bundle_status",
        "bundle_hit_visit_count",
        "bundle_assembled_visit_count",
        "stale_bundle_count",
    ]
    with output_csv.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        for row in report["tables"]:
            bundle = row.get("persistent_bundle_coverage") or {}
            csv_row = {field: row.get(field, "") for field in fieldnames}
            csv_row.update(
                {
                    "bundle_status": bundle.get("bundle_status", ""),
                    "bundle_hit_visit_count": bundle.get("bundle_hit_visit_count", ""),
                    "bundle_assembled_visit_count": bundle.get("bundle_assembled_visit_count", ""),
                    "stale_bundle_count": bundle.get("stale_bundle_count", ""),
                }
            )
            writer.writerow(csv_row)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="只读审计客户源库/本地 CDM/正文拼装/持久化 bundle 覆盖")
    parser.add_argument("--visit-ids-file", default="", help="每行一个 visit_id；默认使用 Sheet2 当前目标样本")
    parser.add_argument("--group-id", action="append", default=[], help="同步表组，可重复；默认 sample_full_domain")
    parser.add_argument("--remote-schema", default="public")
    parser.add_argument("--sample-limit", type=int, default=20)
    parser.add_argument("--output-json", default=str(DEFAULT_OUTPUT_JSON))
    parser.add_argument("--output-csv", default=str(DEFAULT_OUTPUT_CSV))
    parser.add_argument("--write-report", action="store_true", help="写出 JSON/CSV 报告；默认只打印摘要")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    visit_ids = _read_visit_ids(args.visit_ids_file)
    report = build_audit(
        visit_ids=visit_ids,
        group_ids=[_safe_text(item) for item in (args.group_id or ["sample_full_domain"]) if _safe_text(item)],
        remote_schema=_safe_text(args.remote_schema) or "public",
        sample_limit=args.sample_limit,
    )
    summary = {
        "remote_schema": report["remote_schema"],
        "group_ids": report["group_ids"],
        "visit_count": report["visit_count"],
        "table_count": len(report["tables"]),
        "source_tables_with_rows": sum(1 for row in report["tables"] if int(row["source_total_rows"] or 0) > 0),
        "local_tables_with_rows": sum(1 for row in report["tables"] if int(row["local_total_rows"] or 0) > 0),
    }
    if args.write_report:
        write_reports(
            report,
            output_json=Path(args.output_json).resolve(),
            output_csv=Path(args.output_csv).resolve(),
        )
        summary["output_json"] = str(Path(args.output_json).resolve())
        summary["output_csv"] = str(Path(args.output_csv).resolve())
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
