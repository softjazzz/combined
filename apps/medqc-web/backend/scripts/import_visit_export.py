from __future__ import annotations

import argparse
import ast
import csv
import json
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import sqlalchemy as sa
from sqlalchemy import inspect, text
from sqlalchemy.orm import sessionmaker

from app.database.connection import DATABASE_URL
from app.services.case_identity import CaseRef
from app.services.bundles import refresh_domain_bundles_for_rows, refresh_scene_bundles_for_rows
from app.services.bundles.publication import (
    assert_complete_bundle_refresh,
    invalidate_bundle_variants,
    new_bundle_staging_token,
    publish_bundle_variants,
)
from app.services.task_record_sync_job_service import _GLOBAL_LOCK_KEY


_DOMAINS = (
    "admission", "course", "surgery", "consult_discussion", "terminal",
    "index_coding_settlement",
)


@contextmanager
def _bundle_write_lock(engine: sa.Engine):
    if engine.dialect.name != "postgresql":
        yield
        return
    with engine.connect() as conn:
        conn.execute(text("SELECT pg_advisory_lock(:key)"), {"key": _GLOBAL_LOCK_KEY})
        try:
            yield
        finally:
            conn.rollback()
            conn.execute(text("SELECT pg_advisory_unlock(:key)"), {"key": _GLOBAL_LOCK_KEY})
            conn.commit()


def _quote_ident(value: str) -> str:
    if not value or any(ch not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_" for ch in value):
        raise ValueError(f"非法标识符: {value}")
    return f'"{value}"'


def _qualified_table(schema: str, table: str) -> str:
    return f"{_quote_ident(schema)}.{_quote_ident(table)}"


def _resolve_csv_target(path: Path, *, default_schema: str) -> tuple[str, str]:
    stem = path.name[:-4]
    if "." in stem:
        schema, table = stem.split(".", 1)
        return schema, table
    return default_schema, stem


def _read_csv_rows(path: Path) -> tuple[list[str], list[dict[str, Any]]]:
    last_error: Exception | None = None
    for encoding in ("utf-8-sig", "utf-8", "gb18030", "gbk"):
        try:
            with path.open("r", encoding=encoding, newline="") as handle:
                reader = csv.DictReader(handle)
                fieldnames = [
                    str(item or "").strip()
                    for item in list(reader.fieldnames or [])
                    if str(item or "").strip()
                ]
                rows = []
                for raw in reader:
                    normalized = {}
                    for field in fieldnames:
                        value = raw.get(field)
                        text_value = str(value).strip() if value is not None else ""
                        normalized[field] = text_value if text_value != "" else None
                    rows.append(normalized)
            return fieldnames, rows
        except UnicodeDecodeError as exc:
            last_error = exc
            continue
    if last_error is not None:
        raise last_error
    raise RuntimeError(f"无法读取 CSV 文件: {path}")


def _ensure_schema(conn: sa.Connection, schema: str) -> None:
    conn.execute(text(f"CREATE SCHEMA IF NOT EXISTS {_quote_ident(schema)}"))


def _create_lightweight_table(
    conn: sa.Connection,
    *,
    schema: str,
    table: str,
    columns: list[str],
) -> None:
    column_defs = ",\n    ".join(f'{_quote_ident(name)} TEXT NULL' for name in columns)
    sql = f"""
    CREATE TABLE IF NOT EXISTS {_qualified_table(schema, table)} (
        {column_defs}
    )
    """
    conn.execute(text(sql))
    if "visit_id" in columns:
        conn.execute(
            text(
                f'CREATE INDEX IF NOT EXISTS {_quote_ident(f"ix_{table}_visit_id")} '
                f'ON {_qualified_table(schema, table)} ({_quote_ident("visit_id")})'
            )
        )
    if "patient_id" in columns and "visit_id" in columns:
        conn.execute(
            text(
                f'CREATE INDEX IF NOT EXISTS {_quote_ident(f"ix_{table}_patient_visit")} '
                f'ON {_qualified_table(schema, table)} ({_quote_ident("patient_id")}, {_quote_ident("visit_id")})'
            )
        )


def _ensure_table_columns(
    conn: sa.Connection,
    *,
    schema: str,
    table: str,
    existing_columns: list[str],
    csv_columns: list[str],
) -> list[str]:
    missing_columns = [col for col in csv_columns if col not in existing_columns]
    supports_if_not_exists = conn.dialect.name not in {"sqlite"}
    for column in missing_columns:
        if_clause = " IF NOT EXISTS" if supports_if_not_exists else ""
        conn.execute(
            text(
                f"ALTER TABLE {_qualified_table(schema, table)} "
                f"ADD COLUMN{if_clause} {_quote_ident(column)} TEXT NULL"
            )
        )
    return missing_columns


def _visit_ids(rows: list[dict[str, Any]]) -> list[str]:
    seen = []
    for row in rows:
        visit_id = str(row.get("visit_id") or "").strip()
        if visit_id and visit_id not in seen:
            seen.append(visit_id)
    return seen


def _collect_refresh_keys(rows: list[dict[str, Any]]) -> list[dict[str, str]]:
    seen: set[tuple[str, str, str]] = set()
    out: list[dict[str, str]] = []
    for row in rows:
        institute_id = str(row.get("institute_id") or "").strip()
        patient_id = str(row.get("patient_id") or "").strip()
        visit_id = str(row.get("visit_id") or "").strip()
        if not institute_id or not patient_id or not visit_id:
            continue
        key = (institute_id, patient_id, visit_id)
        if key in seen:
            continue
        seen.add(key)
        out.append(
            {
                "institute_id": institute_id,
                "patient_id": patient_id,
                "visit_id": visit_id,
            }
        )
    return out


def _delete_existing_rows(
    conn: sa.Connection,
    *,
    schema: str,
    table: str,
    visit_ids: list[str],
) -> None:
    if not visit_ids:
        return
    sql = text(
        f"DELETE FROM {_qualified_table(schema, table)} "
        f"WHERE {_quote_ident('visit_id')} IN :visit_ids"
    ).bindparams(sa.bindparam("visit_ids", expanding=True))
    conn.execute(sql, {"visit_ids": visit_ids})


def _insert_rows(
    conn: sa.Connection,
    *,
    schema: str,
    table: str,
    columns: list[str],
    column_types: dict[str, Any],
    rows: list[dict[str, Any]],
) -> int:
    if not rows:
        return 0
    cols_sql = ", ".join(_quote_ident(col) for col in columns)
    vals_sql = ", ".join(f":{col}" for col in columns)
    sql = text(
        f"INSERT INTO {_qualified_table(schema, table)} ({cols_sql}) VALUES ({vals_sql})"
    )
    payload = [
        {
            col: _coerce_value_for_column(row.get(col), column_types.get(col))
            for col in columns
        }
        for row in rows
    ]
    conn.execute(sql, payload)
    return len(payload)


def _coerce_value_for_column(value: Any, column_type: Any) -> Any:
    if value in (None, ""):
        return None
    type_name = str(column_type).lower()
    if "json" in type_name:
        if isinstance(value, (dict, list)):
            return json.dumps(value, ensure_ascii=False)
        text_value = str(value).strip()
        try:
            return json.dumps(json.loads(text_value), ensure_ascii=False)
        except Exception:
            pass
        try:
            return json.dumps(ast.literal_eval(text_value), ensure_ascii=False)
        except Exception:
            return json.dumps(text_value, ensure_ascii=False)
    return value


def import_visit_export(
    *,
    export_dir: Path,
    create_missing_tables: bool = True,
    rebuild_bundles: bool = True,
    default_schema: str = "cdm",
) -> dict[str, Any]:
    if not DATABASE_URL:
        raise RuntimeError("DATABASE_URL 未配置，无法导入 visit export")

    engine = sa.create_engine(DATABASE_URL)
    inspector = inspect(engine)
    csv_files = sorted(export_dir.glob("*.csv"))
    if not csv_files:
        raise FileNotFoundError(f"未在目录中发现 CSV 文件: {export_dir}")
    with _bundle_write_lock(engine):
        return _import_visit_export_locked(
            engine=engine,
            inspector=inspector,
            csv_files=csv_files,
            export_dir=export_dir,
            create_missing_tables=create_missing_tables,
            rebuild_bundles=rebuild_bundles,
            default_schema=default_schema,
        )


def _import_visit_export_locked(
    *,
    engine: sa.Engine,
    inspector: Any,
    csv_files: list[Path],
    export_dir: Path,
    create_missing_tables: bool,
    rebuild_bundles: bool,
    default_schema: str,
) -> dict[str, Any]:

    imported_tables: list[dict[str, Any]] = []
    missing_created: list[str] = []
    altered_tables: list[dict[str, Any]] = []
    all_visit_ids: list[str] = []
    refresh_keys: list[dict[str, str]] = []
    refresh_seen: set[tuple[str, str, str]] = set()
    parsed_files = []
    for path in csv_files:
        schema, table = _resolve_csv_target(path, default_schema=default_schema)
        columns, rows = _read_csv_rows(path)
        parsed_files.append((schema, table, columns, rows))
        for row in rows:
            if not all(str(row.get(name) or "").strip() for name in ("institute_id", "patient_id", "visit_id")):
                raise RuntimeError(f"{path.name} 缺少完整病例三坐标，未开始导入")
        for key in _collect_refresh_keys(rows):
            dedupe_key = (key["institute_id"], key["patient_id"], key["visit_id"])
            if dedupe_key not in refresh_seen:
                refresh_seen.add(dedupe_key)
                refresh_keys.append(key)

    if not refresh_keys:
        raise RuntimeError("未解析出 institute_id/patient_id/visit_id，未开始导入")
    refs = [CaseRef.from_mapping(key) for key in refresh_keys]
    session_factory = sessionmaker(bind=engine)
    invalidate_bundle_variants(refs, session_factory=session_factory)
    staging_token = new_bundle_staging_token()

    with engine.begin() as conn:
        for schema, table, columns, rows in parsed_files:
            visit_ids = _visit_ids(rows)
            for visit_id in visit_ids:
                if visit_id not in all_visit_ids:
                    all_visit_ids.append(visit_id)

            exists = inspector.has_table(table, schema=schema)
            created_now = False
            if not exists:
                if not create_missing_tables:
                    imported_tables.append(
                        {
                            "table": f"{schema}.{table}",
                            "status": "skipped_missing_table",
                            "rows": 0,
                        }
                    )
                    continue
                _ensure_schema(conn, schema)
                _create_lightweight_table(conn, schema=schema, table=table, columns=columns)
                missing_created.append(f"{schema}.{table}")
                exists = True
                created_now = True

            reflected_columns = [] if created_now else inspector.get_columns(table, schema=schema)
            table_columns = columns if created_now else [col["name"] for col in reflected_columns]
            column_types = {col["name"]: col.get("type") for col in reflected_columns}
            if created_now:
                column_types = {col: "text" for col in columns}
            else:
                added_columns = _ensure_table_columns(
                    conn,
                    schema=schema,
                    table=table,
                    existing_columns=table_columns,
                    csv_columns=columns,
                )
                if added_columns:
                    altered_tables.append(
                        {
                            "table": f"{schema}.{table}",
                            "added_columns": added_columns,
                        }
                    )
                    table_columns = [*table_columns, *added_columns]
                    for column in added_columns:
                        column_types[column] = "text"
            insert_columns = [col for col in columns if col in table_columns]
            if "visit_id" not in table_columns:
                raise RuntimeError(f"{schema}.{table} 缺少 visit_id，当前脚本不支持导入")

            _delete_existing_rows(conn, schema=schema, table=table, visit_ids=visit_ids)
            inserted = _insert_rows(conn, schema=schema, table=table, columns=insert_columns, column_types=column_types, rows=rows)
            imported_tables.append(
                {
                    "table": f"{schema}.{table}",
                    "status": "imported",
                    "rows": inserted,
                }
            )

    bundle_results = []
    if rebuild_bundles:
        running_stats = refresh_scene_bundles_for_rows(
            scene="running",
            rows=refresh_keys,
            policy_version=staging_token,
            source_schema="cdm",
            bundle_schema="public",
            trigger_source="visit_export_import",
            continue_on_error=False,
        )
        final_stats = refresh_scene_bundles_for_rows(
            scene="final",
            rows=refresh_keys,
            policy_version=staging_token,
            source_schema="cdm",
            bundle_schema="public",
            trigger_source="visit_export_import",
            continue_on_error=False,
        )
        domain_stats = {
            domain: refresh_domain_bundles_for_rows(
                rows=refresh_keys,
                policy_version=staging_token,
                source_schema="cdm",
                bundle_schema="public",
                trigger_source="visit_export_import",
                continue_on_error=False,
                domains=(domain,),
            )
            for domain in _DOMAINS
        }
        assert_complete_bundle_refresh(
            SimpleNamespace(bundle_refresh={
                "scenes": {"running": running_stats, "final": final_stats},
                "domains": domain_stats,
            }),
            len(refs),
        )
        publish_bundle_variants(
            refs,
            staging_token=staging_token,
            published_policy_version="",
            session_factory=session_factory,
        )
        domain_totals = {
            name: sum(stats.get(name, 0) for stats in domain_stats.values())
            for name in ("processed", "updated", "failed", "skipped")
        }
        for key in refresh_keys:
            bundle_results.append(
                {
                    "visit_id": key["visit_id"],
                    "patient_id": key["patient_id"],
                    "institute_id": key["institute_id"],
                    "running_refresh": running_stats,
                    "final_refresh": final_stats,
                    "domain_refresh": domain_totals,
                }
            )

    return {
        "export_dir": str(export_dir),
        "visit_ids": all_visit_ids,
        "refresh_key_count": len(refresh_keys),
        "created_tables": missing_created,
        "altered_tables": altered_tables,
        "tables": imported_tables,
        "bundle_results": bundle_results,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="导入单个 visit_export 目录中的多表 CSV")
    parser.add_argument("export_dir", help="visit_export 目录")
    parser.add_argument("--no-create-missing", action="store_true", help="缺表时跳过，不自动创建")
    parser.add_argument("--no-rebuild-bundles", action="store_true", help="导入后不重建 running/final bundle")
    parser.add_argument("--default-schema", default="cdm", help="CSV 文件名不带 schema 时使用的默认 schema")
    args = parser.parse_args()

    result = import_visit_export(
        export_dir=Path(args.export_dir).resolve(),
        create_missing_tables=not bool(args.no_create_missing),
        rebuild_bundles=not bool(args.no_rebuild_bundles),
        default_schema=str(args.default_schema or "cdm").strip() or "cdm",
    )
    import json
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
