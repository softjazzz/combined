"""只读审计客户样本同步表的增量能力。

脚本只读取 ``list_sync_tables`` 配置及信息架构/CSV 表头，不连接时不会写库。
推荐策略只是下一阶段的输入，不会改变当前同步行为。
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence


SCRIPT_DIR = Path(__file__).resolve().parent
BACKEND_ROOT = SCRIPT_DIR.parent
REPO_ROOT = BACKEND_ROOT.parent
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

DEFAULT_REPORT = REPO_ROOT / "docs" / "reports" / "customer-sample-sync-incremental-capabilities.md"

INCREMENTAL_STRATEGIES = {
    "updated_at",
    "append_only_record_time",
    "full_visit_reload",
}
REQUIRED_PRIMARY_VISIBILITY_TABLES = (
    "mr",
    "inpat_registration",
    "admission_record",
)
UPDATE_COLUMN_CANDIDATES = (
    "update_time",
    "modify_time",
    "updated_at",
    "last_modified_datetime",
    "last_modified_time",
)
RECORD_TIME_COLUMN_CANDIDATES = (
    "record_time",
    "record_datetime",
    "report_datetime",
    "report_time",
    "submit_datetime",
    "request_datetime",
    "prescribed_datetime",
    "diagnosis_datetime",
    "billing_datetime",
)
SOFT_DELETE_COLUMN_CANDIDATES = (
    "is_deleted",
    "delete_flag",
    "deleted_at",
    "invalid_flag",
)
VISIT_IDENTITY_COLUMNS = {"institute_id", "patient_id", "visit_id", "visit_type"}


def _safe_text(value: Any) -> str:
    return str(value or "").strip()


def _first_present(candidates: Iterable[str], columns: set[str]) -> str:
    return next((candidate for candidate in candidates if candidate in columns), "")


def _stable_key(
    configured_keys: Sequence[str],
    primary_keys: Sequence[str],
    columns: set[str],
) -> tuple[bool, list[str]]:
    keys = [_safe_text(item) for item in (primary_keys or configured_keys) if _safe_text(item)]
    exists = bool(keys) and all(key in columns for key in keys)
    distinguishes_rows = any(key not in VISIT_IDENTITY_COLUMNS for key in keys)
    return exists and distinguishes_rows, keys


def audit_table_capability(
    *,
    table_config: Mapping[str, Any],
    columns: Iterable[str],
    primary_keys: Sequence[str],
) -> dict[str, Any]:
    """根据真实列结构与显式契约推荐受控增量策略。"""

    name = _safe_text(table_config.get("name"))
    source_table = _safe_text(table_config.get("source_table")) or name
    column_set = {_safe_text(item) for item in columns if _safe_text(item)}
    configured_keys = [
        _safe_text(item) for item in table_config.get("key_fields", []) if _safe_text(item)
    ]
    stable_key, resolved_keys = _stable_key(configured_keys, primary_keys, column_set)
    update_column = _first_present(UPDATE_COLUMN_CANDIDATES, column_set)
    record_time_column = _first_present(RECORD_TIME_COLUMN_CANDIDATES, column_set)
    soft_delete_columns = [
        candidate for candidate in SOFT_DELETE_COLUMN_CANDIDATES if candidate in column_set
    ]
    explicit_strategy = _safe_text(table_config.get("incremental_strategy"))
    configured_date_field = _safe_text(table_config.get("date_field"))
    risks: list[str] = []

    if update_column:
        strategy = "updated_at"
        watermark_column = update_column
        risks.append("需验证该更新时间字段在新增和每次修改时均可靠更新")
    elif (
        explicit_strategy == "append_only_record_time"
        and stable_key
        and record_time_column
    ):
        strategy = "append_only_record_time"
        watermark_column = record_time_column
        risks.append("仅适用于已由院方确认只增不改的源表")
    else:
        strategy = "full_visit_reload"
        watermark_column = ""
        if record_time_column and stable_key and explicit_strategy != "append_only_record_time":
            risks.append("存在记录时间，但需院方确认只增不改后才能启用时间水位")
        if not stable_key:
            risks.append("缺少可区分同一病历多行记录的稳定主键")
        if not column_set:
            risks.append("未取得表结构，需补充源表字段清单")

    if configured_date_field and configured_date_field not in column_set:
        risks.append(f"配置声明的时间字段不存在：{configured_date_field}")
    if strategy != "full_visit_reload" and not soft_delete_columns:
        risks.append("未发现软删除标记，无法通过水位识别物理删除")
    if explicit_strategy and explicit_strategy not in INCREMENTAL_STRATEGIES:
        risks.append(f"发现非受控策略声明：{explicit_strategy}")

    return {
        "name": name,
        "source_table": source_table,
        "contract_status": "configured",
        "columns_observed": len(column_set),
        "key_fields": resolved_keys or configured_keys,
        "stable_key": stable_key,
        "update_column": update_column,
        "record_time_column": record_time_column,
        "soft_delete_columns": soft_delete_columns,
        "incremental_strategy": strategy,
        "watermark_column": watermark_column,
        "risks": "；".join(dict.fromkeys(risks)) or "未发现额外风险",
    }


def audit_tables(
    *,
    table_configs: Sequence[Mapping[str, Any]],
    schemas: Mapping[str, Mapping[str, Sequence[str]]],
) -> list[dict[str, Any]]:
    """审计契约内表，并显式补出第一阶段必需但契约缺失的表。"""

    results: list[dict[str, Any]] = []
    configured_names: set[str] = set()
    for config in table_configs:
        name = _safe_text(config.get("name"))
        if not name:
            continue
        configured_names.add(name)
        source_table = _safe_text(config.get("source_table")) or name
        schema = schemas.get(source_table) or schemas.get(name) or {}
        results.append(
            audit_table_capability(
                table_config=config,
                columns=schema.get("columns", []),
                primary_keys=list(schema.get("primary_keys", [])),
            )
        )

    for table_name in REQUIRED_PRIMARY_VISIBILITY_TABLES:
        if table_name in configured_names:
            continue
        schema = schemas.get(table_name) or {}
        gap = audit_table_capability(
            table_config={
                "name": table_name,
                "source_table": table_name,
                "key_fields": ["patient_id", "visit_id"],
            },
            columns=schema.get("columns", []),
            primary_keys=list(schema.get("primary_keys", [])),
        )
        gap["contract_status"] = "missing_from_sync_contract"
        gap["risks"] = (
            "第一阶段必需表尚未纳入 list_sync_tables；需在 Task 3 正式加入同步表契约；"
            + gap["risks"]
        )
        results.append(gap)

    return sorted(results, key=lambda item: item["name"])


def load_csv_schema_directory(path: Path) -> dict[str, dict[str, list[str]]]:
    """仅读取客户导出 CSV 的首行字段，不读取病历正文。"""

    schemas: dict[str, dict[str, list[str]]] = {}
    for csv_path in sorted(path.glob("*.csv")):
        table_name = csv_path.stem.split(".", 1)[-1]
        with csv_path.open("r", encoding="utf-8-sig", newline="") as handle:
            header = next(csv.reader(handle), [])
        schemas[table_name] = {
            "columns": [_safe_text(item) for item in header if _safe_text(item)],
            "primary_keys": [],
        }
    return schemas


def load_json_schema_snapshot(path: Path) -> dict[str, dict[str, list[str]]]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError("结构快照必须是按表名索引的 JSON 对象")
    return {
        _safe_text(table): {
            "columns": list((meta or {}).get("columns", [])),
            "primary_keys": list((meta or {}).get("primary_keys", [])),
        }
        for table, meta in raw.items()
        if _safe_text(table) and isinstance(meta, dict)
    }


def _sanitized_source_summary(source_summary: Mapping[str, Any]) -> dict[str, str]:
    allowed_keys = {"mode", "schema", "table_count", "evidence"}
    return {
        key: _safe_text(value)
        for key, value in source_summary.items()
        if key in allowed_keys and _safe_text(value)
    }


def render_markdown_report(
    results: Sequence[Mapping[str, Any]],
    *,
    source_summary: Mapping[str, Any],
) -> str:
    summary = _sanitized_source_summary(source_summary)
    counts = Counter(_safe_text(item.get("incremental_strategy")) for item in results)
    contract_gaps = [
        item for item in results if item.get("contract_status") == "missing_from_sync_contract"
    ]
    lines = [
        "# 客户样本同步源表增量能力审计",
        "",
        "> 本报告为只读结构审计结果，不会改变当前同步行为。字段存在不等于业务语义可靠，",
        "> `updated_at` 策略仍须以客户源库更新行为验证为准。",
        "",
        "## 审计范围",
        "",
        f"- 证据方式：{summary.get('mode', '未说明')}",
        f"- 结构证据：{summary.get('evidence', '未说明')}",
        f"- 已取得结构的表：{summary.get('table_count', '0')} 张",
        f"- 同步契约表及显式缺口：{len(results)} 张",
        "",
        "## 策略汇总",
        "",
        f"- `updated_at`：{counts['updated_at']} 张",
        f"- `append_only_record_time`：{counts['append_only_record_time']} 张",
        f"- `full_visit_reload`：{counts['full_visit_reload']} 张",
        f"- 第一阶段契约缺口：{len(contract_gaps)} 张",
        "",
        "## 关键结论",
        "",
        "- 不能把 `list_sync_tables()` 默认的 `date_field=update_time` 当作字段真实存在的证明。",
        "- 仅有记录/报告时间不能证明表只增不改；未有显式受控声明时一律整病历重拉。",
        "- 更新时间字段存在的表仍需验证：旧记录修改时该字段是否同步变化、是否单调且非空。",
        "- 第一版不承诺识别源库物理删除；存在软删除字段时才可同步删除状态。",
    ]
    if contract_gaps:
        lines.extend(
            [
                "- `inpat_registration` 是第一阶段病历可见性的必需表，但当前未纳入 "
                "`list_sync_tables`；Task 3 必须正式补入同步表契约。",
            ]
        )
    lines.extend(
        [
            "",
            "## 逐表结果",
            "",
            "| 表名 | 契约状态 | 观测列数 | 主键/业务键 | 更新时间 | 记录时间 | 删除标记 | 推荐策略 | 风险与待确认 |",
            "| --- | --- | ---: | --- | --- | --- | --- | --- | --- |",
        ]
    )
    for item in results:
        values = [
            item.get("name"),
            item.get("contract_status"),
            item.get("columns_observed"),
            ", ".join(item.get("key_fields") or []) or "—",
            item.get("update_column") or "—",
            item.get("record_time_column") or "—",
            ", ".join(item.get("soft_delete_columns") or []) or "—",
            item.get("incremental_strategy"),
            item.get("risks"),
        ]
        escaped = [str(value).replace("|", "\\|").replace("\r", " ").replace("\n", " ") for value in values]
        lines.append("| " + " | ".join(escaped) + " |")
    lines.extend(
        [
            "",
            "## Task 2/3 前置确认",
            "",
            "1. 对所有推荐 `updated_at` 的表，用一条旧记录修改实验验证水位字段确实变化。",
            "2. 只有院方书面确认“只增不改”的表，才允许配置 `append_only_record_time`。",
            "3. 明确各表软删除字段；无删除标记的表纳入出院收口全量核对。",
            "4. Task 3 将 `inpat_registration` 纳入第一阶段同步契约，并补齐业务键。",
            "",
        ]
    )
    return "\n".join(lines)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="只读审计客户样本同步表增量能力")
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--csv-dir", type=Path, help="客户导出 CSV 目录（只读首行）")
    source.add_argument("--schema-json", type=Path, help="脱敏后的表结构 JSON")
    parser.add_argument("--output", type=Path, default=DEFAULT_REPORT)
    return parser


def main() -> int:
    args = _build_parser().parse_args()
    if args.csv_dir:
        schemas = load_csv_schema_directory(args.csv_dir)
        source_mode = "customer_csv_headers"
        evidence = "客户导出 CDM CSV 表头（仅字段名）"
    else:
        schemas = load_json_schema_snapshot(args.schema_json)
        source_mode = "schema_snapshot"
        evidence = "脱敏后的信息架构快照"

    from app.services.etl_sync import list_sync_tables

    results = audit_tables(table_configs=list_sync_tables(), schemas=schemas)
    report = render_markdown_report(
        results,
        source_summary={
            "mode": source_mode,
            "evidence": evidence,
            "table_count": len(schemas),
        },
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(report, encoding="utf-8", newline="\n")
    counts = Counter(item["incremental_strategy"] for item in results)
    print(
        json.dumps(
            {
                "tables": len(results),
                "contract_gaps": sum(
                    item["contract_status"] == "missing_from_sync_contract"
                    for item in results
                ),
                "strategies": dict(counts),
                "output": str(args.output),
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
