"""客户源库 CDM 结构与同步映射的只读盘点工具。

默认模式只读取 PostgreSQL 元数据；``profile`` 模式也只返回汇总统计，
不查询、输出或落盘患者、住院号、文书正文等原始记录。
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping, Sequence
from urllib.parse import urlsplit

import psycopg2
from dotenv import load_dotenv


_IDENTIFIER_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_MODES = frozenset({"metadata", "coverage", "profile"})
_TIME_CANDIDATES = (
    "update_time",
    "last_modified_time",
    "record_time",
    "record_datetime",
    "submit_datetime",
    "submit_time",
    "report_time",
    "report_datetime",
    "exam_time",
    "exam_datetime",
)


def resolve_backend_root(*, search_start: str | Path | None = None) -> Path:
    """兼容 `backend/scripts` 与 `backend/app/scripts` 两种客户机放置路径。"""

    anchor = Path(search_start or __file__).resolve()
    directory = anchor if anchor.is_dir() else anchor.parent
    for candidate_dir in (directory, *directory.parents):
        if (candidate_dir / "app").is_dir():
            return candidate_dir
    raise RuntimeError("无法定位后端根目录；请将脚本放在 backend/scripts 或 backend/app/scripts")


def load_backend_env(*, search_start: str | Path | None = None) -> Path | None:
    """从脚本所在目录向上查找后端 `.env`，且不覆盖显式环境变量。"""

    anchor = Path(search_start or __file__).resolve()
    directory = anchor if anchor.is_dir() else anchor.parent
    seen: set[Path] = set()
    for candidate_dir in (directory, *directory.parents):
        if candidate_dir in seen:
            continue
        seen.add(candidate_dir)
        env_path = candidate_dir / ".env"
        if env_path.is_file():
            load_dotenv(env_path, override=False)
            return env_path
    return None


def _safe_identifier(value: str, *, field: str) -> str:
    normalized = str(value or "").strip()
    if not _IDENTIFIER_RE.fullmatch(normalized):
        raise ValueError(f"{field} 不是合法 PostgreSQL 标识符")
    return normalized


def _quoted_identifier(value: str, *, field: str) -> str:
    return f'"{_safe_identifier(value, field=field)}"'


def _redacted_connection(remote_url: str) -> dict[str, str]:
    parsed = urlsplit(str(remote_url or ""))
    return {
        "scheme": parsed.scheme or "postgresql",
        "host": parsed.hostname or "",
        "port": str(parsed.port or ""),
        "database": (parsed.path or "").lstrip("/"),
        "password": "[REDACTED]",
    }


def _load_runtime_sync_tables() -> list[dict[str, Any]]:
    from app.services.etl_sync import list_sync_tables

    return [dict(item) for item in list_sync_tables()]


def _load_formal_source_registry() -> Mapping[str, Any]:
    from app.services.luxian_0609.source_registry import load_luxian_0609_source_registry

    return load_luxian_0609_source_registry()


def _metadata(
    cursor: Any,
    *,
    remote_schema: str,
) -> tuple[
    dict[str, dict[str, Any]],
    dict[str, list[str]],
    dict[str, list[dict[str, str]]],
    dict[str, int | None],
]:
    cursor.execute(
        """
        SELECT table_name, table_type
        FROM information_schema.tables
        WHERE table_schema = %s
        ORDER BY table_name
        """,
        (remote_schema,),
    )
    tables = {
        str(table_name): {"table_type": str(table_type), "columns": []}
        for table_name, table_type in cursor.fetchall()
    }

    cursor.execute(
        """
        SELECT table_name, column_name, data_type, ordinal_position, is_nullable
        FROM information_schema.columns
        WHERE table_schema = %s
        ORDER BY table_name, ordinal_position
        """,
        (remote_schema,),
    )
    for table_name, column_name, data_type, ordinal_position, is_nullable in cursor.fetchall():
        item = tables.setdefault(str(table_name), {"table_type": "UNKNOWN", "columns": []})
        item["columns"].append(
            {
                "name": str(column_name),
                "type": str(data_type),
                "ordinal_position": int(ordinal_position),
                "nullable": str(is_nullable).upper() == "YES",
            }
        )

    cursor.execute(
        """
        SELECT tc.table_name, kcu.column_name, kcu.ordinal_position
        FROM information_schema.table_constraints tc
        JOIN information_schema.key_column_usage kcu
          ON tc.constraint_name = kcu.constraint_name
         AND tc.table_schema = kcu.table_schema
        WHERE tc.table_schema = %s
          AND tc.constraint_type = 'PRIMARY KEY'
        ORDER BY tc.table_name, kcu.ordinal_position
        """,
        (remote_schema,),
    )
    primary_keys: dict[str, list[str]] = defaultdict(list)
    for table_name, column_name, _ordinal in cursor.fetchall():
        primary_keys[str(table_name)].append(str(column_name))

    cursor.execute(
        """
        SELECT tablename, indexname, indexdef
        FROM pg_indexes
        WHERE schemaname = %s
        ORDER BY tablename, indexname
        """,
        (remote_schema,),
    )
    indexes: dict[str, list[dict[str, str]]] = defaultdict(list)
    for table_name, index_name, index_def in cursor.fetchall():
        indexes[str(table_name)].append(
            {"name": str(index_name), "definition": str(index_def)}
        )

    cursor.execute(
        """
        SELECT rel.relname, COALESCE(stat.n_live_tup, rel.reltuples)::bigint
        FROM pg_class rel
        JOIN pg_namespace namespace ON namespace.oid = rel.relnamespace
        LEFT JOIN pg_stat_user_tables stat
          ON stat.relid = rel.oid
        WHERE namespace.nspname = %s
          AND rel.relkind = 'r'
        ORDER BY rel.relname
        """,
        (remote_schema,),
    )
    estimates = {str(table_name): int(count) for table_name, count in cursor.fetchall()}

    return tables, primary_keys, indexes, estimates


def _coverage_rows(
    *,
    sync_tables: Sequence[Mapping[str, Any]],
    source_tables: Mapping[str, Mapping[str, Any]],
    primary_keys: Mapping[str, Sequence[str]],
    estimates: Mapping[str, int | None],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for config in sync_tables:
        name = str(config.get("name") or "").strip()
        if not name:
            continue
        source_table = str(config.get("source_table") or name).strip()
        enabled = bool(config.get("enabled", True))
        metadata = source_tables.get(source_table)
        fields = {
            str(column.get("name") or "")
            for column in list(metadata.get("columns") or [])
        } if metadata else set()
        key_fields = [str(field) for field in config.get("key_fields") or [] if str(field)]
        missing_identity_fields = [field for field in key_fields if field not in fields]
        time_candidates = [
            field
            for field in (
                str(config.get("date_field") or ""),
                str(config.get("fallback_date_field") or ""),
                *_TIME_CANDIDATES,
            )
            if field and field in fields
        ]
        if not enabled:
            status = "disabled"
        elif metadata is None:
            status = "source_table_missing"
        elif missing_identity_fields:
            status = "field_gap"
        else:
            status = "ready"
        rows.append(
            {
                "name": name,
                "label": str(config.get("label") or name),
                "enabled": enabled,
                "source_table": source_table,
                "procedure": str(config.get("procedure") or ""),
                "incremental_strategy": str(
                    config.get("incremental_strategy") or "full_visit_reload"
                ),
                "status": status,
                "key_fields": key_fields,
                "missing_identity_fields": missing_identity_fields,
                "primary_key": list(primary_keys.get(source_table) or []),
                "time_candidates": list(dict.fromkeys(time_candidates)),
                "estimated_row_count": estimates.get(source_table),
            }
        )
    return rows


def _formal_source_coverage(
    *,
    source_tables: Mapping[str, Mapping[str, Any]],
    coverage: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    configured_sources = {
        str(row.get("name") or ""): str(row.get("status") or "")
        for row in coverage
    }
    registry = _load_formal_source_registry()
    output: list[dict[str, Any]] = []
    for document_type, entry in registry.items():
        source_keys = [str(item) for item in entry.source_keys]
        source_states = {
            key: configured_sources.get(
                key,
                "not_configured" if key not in source_tables else "not_proven",
            )
            for key in source_keys
        }
        if any(state == "ready" for state in source_states.values()):
            status = "available"
        elif any(state in {"source_table_missing", "field_gap"} for state in source_states.values()):
            status = "source_capability_gap"
        else:
            status = "not_proven"
        output.append(
            {
                "document_type": str(document_type),
                "source_keys": source_keys,
                "source_states": source_states,
                "status": status,
            }
        )
    return output


def _profile_rows(
    cursor: Any,
    *,
    remote_schema: str,
    coverage: Sequence[Mapping[str, Any]],
    source_tables: Mapping[str, Mapping[str, Any]],
    exact_count: bool,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for coverage_row in coverage:
        if coverage_row.get("status") != "ready":
            continue
        table_name = str(coverage_row["source_table"])
        metadata = source_tables[table_name]
        column_names = {str(column["name"]) for column in metadata.get("columns") or []}
        identity = [
            field for field in coverage_row.get("key_fields") or [] if field in column_names
        ]
        time_column = next(
            (field for field in coverage_row.get("time_candidates") or [] if field in column_names),
            None,
        )
        schema_sql = _quoted_identifier(remote_schema, field="remote_schema")
        table_sql = _quoted_identifier(table_name, field="source_table")
        identity_sql = " AND ".join(
            f"NULLIF(BTRIM(CAST({_quoted_identifier(field, field='column')} AS text)), '') IS NOT NULL"
            for field in identity
        ) or "TRUE"
        select_columns = [f"COUNT(*) FILTER (WHERE {identity_sql}) AS identity_complete_count"]
        if time_column:
            select_columns.append(
                f"MAX({_quoted_identifier(time_column, field='column')}) AS latest_business_time"
            )
        if exact_count:
            select_columns.insert(0, "COUNT(*) AS exact_count")
        cursor.execute(
            f"SELECT {', '.join(select_columns)} FROM {schema_sql}.{table_sql}"
        )
        result_rows = cursor.fetchall()
        values = result_rows[0] if result_rows else ()
        item = {
            "name": coverage_row["name"],
            "source_table": table_name,
            "exact_count": None,
            "identity_complete_count": None,
            "latest_business_time": None,
            "candidate_time_column": time_column,
        }
        offset = 0
        if exact_count and values:
            item["exact_count"] = values[offset]
            offset += 1
        if values:
            item["identity_complete_count"] = values[offset]
            offset += 1
            if time_column:
                item["latest_business_time"] = _json_value(values[offset])
        rows.append(item)
    return rows


def _json_value(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.astimezone(timezone.utc).isoformat()
    return value


def audit_remote_schema(
    *,
    remote_url: str,
    remote_schema: str,
    mode: str = "metadata",
    sync_tables: Sequence[Mapping[str, Any]] | None = None,
    statement_timeout_ms: int = 30_000,
    exact_count: bool = False,
    connector: Callable[[str], Any] = psycopg2.connect,
) -> dict[str, Any]:
    """从客户源 PostgreSQL 生成无原始病人数据的只读结构报告。"""

    normalized_mode = str(mode or "metadata").strip().lower()
    if normalized_mode not in _MODES:
        raise ValueError("mode 仅允许 metadata、coverage 或 profile")
    schema = _safe_identifier(remote_schema, field="remote_schema")
    if int(statement_timeout_ms) <= 0:
        raise ValueError("statement_timeout_ms 必须大于0")
    resolved_sync_tables = (
        [dict(item) for item in sync_tables]
        if sync_tables is not None
        else _load_runtime_sync_tables()
    )
    connection = connector(str(remote_url))
    try:
        with connection.cursor() as cursor:
            cursor.execute("BEGIN TRANSACTION READ ONLY")
            cursor.execute("SET LOCAL statement_timeout = %s", (int(statement_timeout_ms),))
            tables, primary_keys, indexes, estimates = _metadata(
                cursor, remote_schema=schema
            )
            coverage = _coverage_rows(
                sync_tables=resolved_sync_tables,
                source_tables=tables,
                primary_keys=primary_keys,
                estimates=estimates,
            )
            formal_coverage = _formal_source_coverage(
                source_tables=tables, coverage=coverage
            )
            profile = []
            if normalized_mode == "profile":
                profile = _profile_rows(
                    cursor,
                    remote_schema=schema,
                    coverage=coverage,
                    source_tables=tables,
                    exact_count=bool(exact_count),
                )
            source_tables = [
                {
                    "name": table_name,
                    "table_type": metadata["table_type"],
                    "columns": metadata["columns"],
                    "primary_key": list(primary_keys.get(table_name) or []),
                    "indexes": list(indexes.get(table_name) or []),
                    "estimated_row_count": estimates.get(table_name),
                }
                for table_name, metadata in sorted(tables.items())
            ]
    finally:
        try:
            connection.rollback()
        finally:
            connection.close()

    statuses = [str(item["status"]) for item in coverage]
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "remote_schema": schema,
        "connection": _redacted_connection(remote_url),
        "mode": normalized_mode,
        "read_only": True,
        "patient_data_returned": False,
        "summary": {
            "source_table_count": len(source_tables),
            "configured_tables": len(coverage),
            "ready_tables": statuses.count("ready"),
            "source_table_missing": statuses.count("source_table_missing"),
            "field_gap": statuses.count("field_gap"),
            "disabled_tables": statuses.count("disabled"),
        },
        "sync_table_coverage": coverage,
        "formal_source_coverage": formal_coverage,
        "profile": profile,
        "source_tables": source_tables,
    }


def render_markdown(report: Mapping[str, Any]) -> str:
    summary = dict(report.get("summary") or {})
    lines = [
        "# 客户源库 CDM 只读盘点报告",
        "",
        f"- 生成时间（UTC）：{report.get('generated_at')}",
        f"- 源 schema：`{report.get('remote_schema')}`",
        "- 执行方式：只读事务；不输出患者、住院号、文书正文或原始记录。",
        "",
        "## 总览",
        "",
        f"- 源表数：{summary.get('source_table_count', 0)}",
        f"- 已配置同步逻辑表：{summary.get('configured_tables', 0)}",
        f"- 可执行：{summary.get('ready_tables', 0)}",
        f"- 缺源表：{summary.get('source_table_missing', 0)}",
        f"- 缺关键字段：{summary.get('field_gap', 0)}",
        "",
        "## 同步映射差异",
        "",
        "|逻辑表|物理源表|状态|缺主键字段|可用时间字段|",
        "|---|---|---|---|---|",
    ]
    for item in report.get("sync_table_coverage") or []:
        lines.append(
            "|{name}|{source}|{status}|{missing}|{times}|".format(
                name=item.get("name") or "",
                source=item.get("source_table") or "",
                status=item.get("status") or "",
                missing=", ".join(item.get("missing_identity_fields") or []) or "-",
                times=", ".join(item.get("time_candidates") or []) or "-",
            )
        )
    lines.extend(
        [
            "",
            "## LX0609 来源覆盖",
            "",
            "|逻辑来源|状态|受控来源键|",
            "|---|---|---|",
        ]
    )
    for item in report.get("formal_source_coverage") or []:
        lines.append(
            "|{document_type}|{status}|{source_keys}|".format(
                document_type=item.get("document_type") or "",
                status=item.get("status") or "",
                source_keys=", ".join(item.get("source_keys") or []),
            )
        )
    if report.get("profile"):
        lines.extend(
            [
                "",
                "## 数据概要（无原始数据）",
                "",
                "|逻辑表|物理源表|精确行数|主键完整行数|最新业务时间|",
                "|---|---|---:|---:|---|",
            ]
        )
        for item in report["profile"]:
            lines.append(
                "|{name}|{source}|{exact}|{identity}|{time}|".format(
                    name=item.get("name") or "",
                    source=item.get("source_table") or "",
                    exact=item.get("exact_count") if item.get("exact_count") is not None else "未执行",
                    identity=item.get("identity_complete_count") if item.get("identity_complete_count") is not None else "-",
                    time=item.get("latest_business_time") or "-",
                )
            )
    return "\n".join(lines) + "\n"


def write_report(
    report: Mapping[str, Any],
    *,
    output_dir: str | Path,
    stamp: str | None = None,
) -> dict[str, Path]:
    directory = Path(output_dir).resolve()
    directory.mkdir(parents=True, exist_ok=True)
    normalized_stamp = stamp or datetime.now().strftime("%Y%m%d-%H%M%S")
    json_path = directory / f"remote-cdm-schema-audit-{normalized_stamp}.json"
    markdown_path = directory / f"remote-cdm-schema-audit-{normalized_stamp}.md"
    json_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, default=_json_value),
        encoding="utf-8",
    )
    markdown_path.write_text(render_markdown(report), encoding="utf-8")
    return {"json": json_path, "markdown": markdown_path}


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="只读盘点客户源库 CDM 结构与同步映射")
    parser.add_argument("--remote-url", default=os.getenv("REMOTE_DB_URL", ""))
    parser.add_argument("--remote-schema", default=os.getenv("REMOTE_SCHEMA", "public"))
    parser.add_argument("--mode", choices=sorted(_MODES), default="metadata")
    parser.add_argument("--output-dir", default="reports/remote-schema-audit")
    parser.add_argument("--statement-timeout-ms", type=int, default=30_000)
    parser.add_argument(
        "--exact-count",
        action="store_true",
        help="仅 profile 模式有效；对每张可执行源表执行 COUNT(*)，大表可能较慢。",
    )
    return parser


def main(argv: Iterable[str] | None = None) -> int:
    backend_root = resolve_backend_root()
    if str(backend_root) not in sys.path:
        sys.path.insert(0, str(backend_root))
    load_backend_env(search_start=backend_root)
    args = _parser().parse_args(list(argv) if argv is not None else None)
    if not str(args.remote_url).strip():
        raise SystemExit("缺少 REMOTE_DB_URL；请传入 --remote-url 或配置环境变量")
    report = audit_remote_schema(
        remote_url=str(args.remote_url),
        remote_schema=str(args.remote_schema),
        mode=str(args.mode),
        statement_timeout_ms=int(args.statement_timeout_ms),
        exact_count=bool(args.exact_count),
    )
    paths = write_report(report, output_dir=args.output_dir)
    print(f"JSON报告: {paths['json']}")
    print(f"Markdown报告: {paths['markdown']}")
    print(json.dumps(report["summary"], ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
