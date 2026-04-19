from __future__ import annotations

import argparse
import ast
import csv
import json
from pathlib import Path
from typing import Any

import sqlalchemy as sa
from sqlalchemy import inspect, text

from app.database.connection import DATABASE_URL
from app.services.bundles import refresh_scene_bundles_for_rows


def _quote_ident(value: str) -> str:
    if not value or any(ch not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_" for ch in value):
        raise ValueError(f"非法标识符: {value}")
    return f'"{value}"'


def _qualified_table(schema: str, table: str) -> str:
    return f"{_quote_ident(schema)}.{_quote_ident(table)}"


def _read_csv_rows(path: Path) -> tuple[list[str], list[dict[str, Any]]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        fieldnames = [str(item or "").strip() for item in list(reader.fieldnames or []) if str(item or "").strip()]
        rows = []
        for raw in reader:
            normalized = {}
            for field in fieldnames:
                value = raw.get(field)
                text_value = str(value).strip() if value is not None else ""
                normalized[field] = text_value if text_value != "" else None
            rows.append(normalized)
    return fieldnames, rows


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


def _visit_ids(rows: list[dict[str, Any]]) -> list[str]:
    seen = []
    for row in rows:
        visit_id = str(row.get("visit_id") or "").strip()
        if visit_id and visit_id not in seen:
            seen.append(visit_id)
    return seen


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
        f"WHERE {_quote_ident('visit_id')} = ANY(:visit_ids)"
    )
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
) -> dict[str, Any]:
    if not DATABASE_URL:
        raise RuntimeError("DATABASE_URL 未配置，无法导入 visit export")

    engine = sa.create_engine(DATABASE_URL)
    inspector = inspect(engine)
    csv_files = sorted(export_dir.glob("*.csv"))
    if not csv_files:
        raise FileNotFoundError(f"未在目录中发现 CSV 文件: {export_dir}")

    imported_tables: list[dict[str, Any]] = []
    missing_created: list[str] = []
    all_visit_ids: list[str] = []
    institute_id = ""
    patient_id = ""

    with engine.begin() as conn:
        for path in csv_files:
            stem = path.name[:-4]
            schema, table = stem.split(".", 1)
            columns, rows = _read_csv_rows(path)
            visit_ids = _visit_ids(rows)
            for visit_id in visit_ids:
                if visit_id not in all_visit_ids:
                    all_visit_ids.append(visit_id)
            if rows and not institute_id:
                institute_id = str(rows[0].get("institute_id") or "").strip()
            if rows and not patient_id:
                patient_id = str(rows[0].get("patient_id") or "").strip()

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
        if not institute_id or not patient_id or not all_visit_ids:
            raise RuntimeError("导入完成，但未解析出 institute_id/patient_id/visit_id，无法重建 bundle")
        refresh_rows = [
            {
                "institute_id": institute_id,
                "patient_id": patient_id,
                "visit_id": visit_id,
            }
            for visit_id in all_visit_ids
        ]
        running_stats = refresh_scene_bundles_for_rows(
            scene="running",
            rows=refresh_rows,
            source_schema="cdm",
            bundle_schema="public",
            trigger_source="visit_export_import",
        )
        final_stats = refresh_scene_bundles_for_rows(
            scene="final",
            rows=refresh_rows,
            source_schema="cdm",
            bundle_schema="public",
            trigger_source="visit_export_import",
        )
        for visit_id in all_visit_ids:
            bundle_results.append(
                {
                    "visit_id": visit_id,
                    "running_refresh": running_stats,
                    "final_refresh": final_stats,
                }
            )

    return {
        "export_dir": str(export_dir),
        "institute_id": institute_id,
        "patient_id": patient_id,
        "visit_ids": all_visit_ids,
        "created_tables": missing_created,
        "tables": imported_tables,
        "bundle_results": bundle_results,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="导入单个 visit_export 目录中的多表 CSV")
    parser.add_argument("export_dir", help="visit_export 目录")
    parser.add_argument("--no-create-missing", action="store_true", help="缺表时跳过，不自动创建")
    parser.add_argument("--no-rebuild-bundles", action="store_true", help="导入后不重建 running/final bundle")
    args = parser.parse_args()

    result = import_visit_export(
        export_dir=Path(args.export_dir).resolve(),
        create_missing_tables=not bool(args.no_create_missing),
        rebuild_bundles=not bool(args.no_rebuild_bundles),
    )
    import json
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
