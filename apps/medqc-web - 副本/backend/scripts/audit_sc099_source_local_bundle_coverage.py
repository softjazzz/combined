#!/usr/bin/env python3
from __future__ import annotations

import csv
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any

from sqlalchemy import inspect as sa_inspect, text


BACKEND_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = BACKEND_ROOT.parents[2]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.database.connection import engine  # noqa: E402
from app.database.models import cdm as _cdm_models  # noqa: F401,E402
from app.services.bundles.assembly import (  # noqa: E402
    assemble_domain_bundle,
    assemble_final_record_bundle,
)


DOCS_DIR = REPO_ROOT / "apps" / "medqc-web" / "docs" / "0508"
SC099_PROBE_CSV = DOCS_DIR / "sc099_pathology_specimen_gate_probe.csv"
OUTPUT_CSV = DOCS_DIR / "sc099_source_local_bundle_coverage.csv"
OUTPUT_JSON = DOCS_DIR / "sc099_source_local_bundle_coverage.json"
OUTPUT_MD = DOCS_DIR / "SC099源库本地bundle覆盖验证报告.md"

SOURCE_SCHEMA = "public"
LOCAL_SCHEMA = "cdm"
TARGET_TABLES = (
    "pathology_exam_master",
    "pathology_exam_report",
    "surgery_record",
    "postsurg_firstcourse_record",
)
BUNDLE_TABLES = {
    "final": "final_record_bundle",
    "course": "course_domain_bundle",
    "surgery": "surgery_domain_bundle",
}


def _safe_text(value: Any) -> str:
    return str(value or "").strip()


def _read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames: list[str] = []
    for row in rows:
        for key in row:
            if key not in fieldnames:
                fieldnames.append(key)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=fieldnames or ["message"],
            extrasaction="ignore",
            lineterminator="\n",
        )
        writer.writeheader()
        writer.writerows(rows)


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _quote(schema: str, table_name: str) -> str:
    return f'"{schema}"."{table_name}"'


def _json_load(value: Any) -> Any:
    if value is None:
        return {}
    if isinstance(value, (dict, list)):
        return value
    if isinstance(value, str):
        try:
            return json.loads(value)
        except Exception:
            return {}
    return {}


def _collect_sc099_visits() -> list[dict[str, str]]:
    rows = _read_csv(SC099_PROBE_CSV)
    visits: dict[str, dict[str, str]] = {}
    for row in rows:
        visit_id = _safe_text(row.get("visit_id"))
        if not visit_id:
            continue
        visits.setdefault(
            visit_id,
            {
                "visit_id": visit_id,
                "patient_name": _safe_text(row.get("patient_name")),
                "rule_id": _safe_text(row.get("rule_id") or "SC-099"),
            },
        )
    return list(visits.values())


def _schema_has_table(inspector: Any, schema: str, table_name: str) -> bool:
    try:
        return bool(inspector.has_table(table_name, schema=schema))
    except Exception:
        return False


def _columns(inspector: Any, schema: str, table_name: str) -> list[str]:
    try:
        return [str(column["name"]) for column in inspector.get_columns(table_name, schema=schema)]
    except Exception:
        return []


def _count_rows_by_visit(
    conn: Any,
    *,
    inspector: Any,
    schema: str,
    table_name: str,
    visit_ids: list[str],
) -> dict[str, Any]:
    if not _schema_has_table(inspector, schema, table_name):
        return {
            "schema": schema,
            "table_name": table_name,
            "table_exists": False,
            "columns": [],
            "counts_by_visit": {},
            "total_rows": None,
            "error": "",
        }
    columns = _columns(inspector, schema, table_name)
    if "visit_id" not in columns:
        return {
            "schema": schema,
            "table_name": table_name,
            "table_exists": True,
            "columns": columns,
            "counts_by_visit": {},
            "total_rows": None,
            "error": "missing_visit_id_column",
        }
    if not visit_ids:
        return {
            "schema": schema,
            "table_name": table_name,
            "table_exists": True,
            "columns": columns,
            "counts_by_visit": {},
            "total_rows": 0,
            "error": "",
        }
    params = {f"v{i}": visit_id for i, visit_id in enumerate(visit_ids)}
    placeholders = ", ".join(f":v{i}" for i in range(len(visit_ids)))
    sql = text(
        f'SELECT "visit_id", COUNT(*) AS row_count '
        f"FROM {_quote(schema, table_name)} "
        f'WHERE "visit_id" IN ({placeholders}) '
        f'GROUP BY "visit_id"'
    )
    try:
        counts = {
            _safe_text(row["visit_id"]): int(row["row_count"] or 0)
            for row in conn.execute(sql, params).mappings()
        }
    except Exception as exc:
        return {
            "schema": schema,
            "table_name": table_name,
            "table_exists": True,
            "columns": columns,
            "counts_by_visit": {},
            "total_rows": None,
            "error": f"query_failed:{type(exc).__name__}",
        }
    return {
        "schema": schema,
        "table_name": table_name,
        "table_exists": True,
        "columns": columns,
        "counts_by_visit": counts,
        "total_rows": sum(counts.values()),
        "error": "",
    }


def _first_row(
    conn: Any,
    *,
    inspector: Any,
    schema: str,
    table_name: str,
    visit_id: str,
    wanted_columns: tuple[str, ...],
) -> dict[str, Any] | None:
    if not _schema_has_table(inspector, schema, table_name):
        return None
    columns = set(_columns(inspector, schema, table_name))
    if "visit_id" not in columns:
        return None
    selected = [column for column in wanted_columns if column in columns]
    if not selected:
        return None
    select_sql = ", ".join(f'"{column}"' for column in selected)
    try:
        row = conn.execute(
            text(
                f"SELECT {select_sql} FROM {_quote(schema, table_name)} "
                'WHERE "visit_id" = :visit_id LIMIT 1'
            ),
            {"visit_id": visit_id},
        ).mappings().first()
    except Exception:
        return None
    return dict(row) if row else None


def _resolve_identity(conn: Any, inspector: Any, visit_id: str) -> dict[str, str]:
    for table_name in (
        "mr",
        "surgery_record",
        "pathology_exam_master",
        "pathology_exam_report",
        "postsurg_firstcourse_record",
        "mr_surgery",
        "surgery_application",
    ):
        row = _first_row(
            conn,
            inspector=inspector,
            schema=LOCAL_SCHEMA,
            table_name=table_name,
            visit_id=visit_id,
            wanted_columns=("institute_id", "patient_id", "visit_id", "name", "patient_name"),
        )
        if not row:
            continue
        institute_id = _safe_text(row.get("institute_id"))
        patient_id = _safe_text(row.get("patient_id"))
        if institute_id and patient_id:
            return {
                "institute_id": institute_id,
                "patient_id": patient_id,
                "patient_name": _safe_text(row.get("name") or row.get("patient_name")),
                "identity_source_table": table_name,
            }
    return {"institute_id": "", "patient_id": "", "patient_name": "", "identity_source_table": ""}


def _inventory_tables(context: dict[str, Any]) -> Counter[str]:
    inventory = list(context.get("document_inventory") or [])
    counter: Counter[str] = Counter()
    for item in inventory:
        if isinstance(item, dict):
            table_name = _safe_text(item.get("source_table") or item.get("document_type"))
            if table_name:
                counter[table_name] += 1
    return counter


def _assembly_counts(context: dict[str, Any]) -> dict[str, int]:
    coverage = context.get("assembly_coverage") or {}
    if not isinstance(coverage, dict):
        return {}
    result: dict[str, int] = {}
    for table_name, value in coverage.items():
        if isinstance(value, dict):
            result[_safe_text(table_name)] = int(value.get("assembled_count") or value.get("count") or 0)
        elif isinstance(value, (int, float)):
            result[_safe_text(table_name)] = int(value)
    return result


def _bundle_context_from_row(row: dict[str, Any] | None) -> dict[str, Any]:
    if not row:
        return {}
    context = _json_load(row.get("structured_context"))
    return context if isinstance(context, dict) else {}


def _load_persisted_bundle_context(
    conn: Any,
    *,
    inspector: Any,
    bundle_table: str,
    visit_id: str,
) -> dict[str, Any]:
    if not _schema_has_table(inspector, SOURCE_SCHEMA, bundle_table):
        return {}
    try:
        row = conn.execute(
            text(
                f"SELECT structured_context FROM {_quote(SOURCE_SCHEMA, bundle_table)} "
                "WHERE visit_id = :visit_id "
                "ORDER BY bundle_updated_at DESC NULLS LAST LIMIT 1"
            ),
            {"visit_id": visit_id},
        ).mappings().first()
    except Exception:
        return {}
    return _bundle_context_from_row(dict(row) if row else None)


def _dry_run_bundle_context(
    *,
    bundle_type: str,
    institute_id: str,
    patient_id: str,
    visit_id: str,
) -> tuple[dict[str, Any], str]:
    try:
        if bundle_type == "final":
            bundle = assemble_final_record_bundle(
                institute_id=institute_id,
                patient_id=patient_id,
                visit_id=visit_id,
                source_schema=LOCAL_SCHEMA,
            )
        else:
            bundle = assemble_domain_bundle(
                execution_domain=bundle_type,
                institute_id=institute_id,
                patient_id=patient_id,
                visit_id=visit_id,
                source_schema=LOCAL_SCHEMA,
            )
        context = dict(bundle.get("structured_context") or {})
        return context, ""
    except Exception as exc:
        return {}, f"{type(exc).__name__}:{_safe_text(exc)[:180]}"


def _source_presence_summary(
    *,
    visit_ids: list[str],
    source_counts: dict[str, dict[str, Any]],
    local_counts: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for table_name in TARGET_TABLES:
        source = source_counts[table_name]
        local = local_counts[table_name]
        source_by_visit = dict(source.get("counts_by_visit") or {})
        local_by_visit = dict(local.get("counts_by_visit") or {})
        source_missing = [visit_id for visit_id in visit_ids if int(source_by_visit.get(visit_id) or 0) == 0]
        local_missing = [visit_id for visit_id in visit_ids if int(local_by_visit.get(visit_id) or 0) == 0]
        if source.get("table_exists") and int(source.get("total_rows") or 0) > 0 and int(local.get("total_rows") or 0) == 0:
            root_cause = "sync_gap"
        elif source.get("table_exists") and int(source.get("total_rows") or 0) == 0 and int(local.get("total_rows") or 0) == 0:
            root_cause = "source_no_data"
        elif source.get("table_exists") and int(source.get("total_rows") or 0) == 0 and int(local.get("total_rows") or 0) > 0:
            root_cause = "source_schema_empty_local_available"
        elif not source.get("table_exists") and int(local.get("total_rows") or 0) == 0:
            root_cause = "remote_unavailable_or_source_table_missing"
        elif int(local.get("total_rows") or 0) > 0:
            root_cause = "local_available"
        else:
            root_cause = "needs_review"
        rows.append(
            {
                "row_type": "source_local_table",
                "table_name": table_name,
                "source_schema": SOURCE_SCHEMA,
                "local_schema": LOCAL_SCHEMA,
                "source_table_exists": source.get("table_exists"),
                "local_table_exists": local.get("table_exists"),
                "source_hit_visit_count": len(visit_ids) - len(source_missing),
                "source_total_rows": source.get("total_rows"),
                "local_hit_visit_count": len(visit_ids) - len(local_missing),
                "local_total_rows": local.get("total_rows"),
                "missing_visit_ids_in_source": ",".join(source_missing),
                "missing_visit_ids_in_local": ",".join(local_missing),
                "source_error": source.get("error"),
                "local_error": local.get("error"),
                "root_cause": root_cause,
            }
        )
    return rows


def _bundle_row(
    *,
    visit: dict[str, str],
    source_counts: dict[str, dict[str, Any]],
    local_counts: dict[str, dict[str, Any]],
    persisted_contexts: dict[str, dict[str, Any]],
    dry_run_contexts: dict[str, dict[str, Any]],
    dry_run_errors: dict[str, str],
    identity: dict[str, str],
) -> dict[str, Any]:
    visit_id = visit["visit_id"]
    row: dict[str, Any] = {
        "row_type": "visit_bundle_dry_run",
        "visit_id": visit_id,
        "patient_name": visit.get("patient_name") or identity.get("patient_name"),
        "institute_id": identity.get("institute_id"),
        "patient_id": identity.get("patient_id"),
        "identity_source_table": identity.get("identity_source_table"),
    }

    for table_name in TARGET_TABLES:
        row[f"source_{table_name}_rows"] = int((source_counts[table_name].get("counts_by_visit") or {}).get(visit_id) or 0)
        row[f"local_{table_name}_rows"] = int((local_counts[table_name].get("counts_by_visit") or {}).get(visit_id) or 0)

    for bundle_type in ("final", "course", "surgery"):
        persisted_inventory = _inventory_tables(persisted_contexts.get(bundle_type) or {})
        dry_inventory = _inventory_tables(dry_run_contexts.get(bundle_type) or {})
        dry_assembly = _assembly_counts(dry_run_contexts.get(bundle_type) or {})
        prefix = f"{bundle_type}_bundle"
        row[f"{prefix}_persisted_has_surgery_record"] = persisted_inventory.get("surgery_record", 0) > 0
        row[f"{prefix}_persisted_has_pathology_exam_master"] = persisted_inventory.get("pathology_exam_master", 0) > 0
        row[f"{prefix}_persisted_has_pathology_exam_report"] = persisted_inventory.get("pathology_exam_report", 0) > 0
        row[f"{prefix}_dryrun_has_surgery_record"] = dry_inventory.get("surgery_record", 0) > 0
        row[f"{prefix}_dryrun_has_pathology_exam_master"] = dry_inventory.get("pathology_exam_master", 0) > 0
        row[f"{prefix}_dryrun_has_pathology_exam_report"] = dry_inventory.get("pathology_exam_report", 0) > 0
        row[f"{prefix}_dryrun_surgery_record_assembled_count"] = dry_assembly.get("surgery_record", 0)
        row[f"{prefix}_dryrun_pathology_assembled_count"] = dry_assembly.get("pathology_exam_master", 0) + dry_assembly.get(
            "pathology_exam_report", 0
        )
        row[f"{prefix}_dryrun_error"] = dry_run_errors.get(bundle_type, "")

    pathology_local_rows = row["local_pathology_exam_master_rows"] + row["local_pathology_exam_report_rows"]
    pathology_dryrun_rows = (
        row["final_bundle_dryrun_pathology_assembled_count"]
        + row["course_bundle_dryrun_pathology_assembled_count"]
        + row["surgery_bundle_dryrun_pathology_assembled_count"]
    )
    pathology_persisted_hit = any(
        bool(row.get(key))
        for key in (
            "final_bundle_persisted_has_pathology_exam_master",
            "final_bundle_persisted_has_pathology_exam_report",
            "course_bundle_persisted_has_pathology_exam_master",
            "course_bundle_persisted_has_pathology_exam_report",
            "surgery_bundle_persisted_has_pathology_exam_master",
            "surgery_bundle_persisted_has_pathology_exam_report",
        )
    )
    surgery_local_rows = row["local_surgery_record_rows"]
    surgery_dryrun_rows = (
        row["final_bundle_dryrun_surgery_record_assembled_count"]
        + row["surgery_bundle_dryrun_surgery_record_assembled_count"]
    )

    if pathology_local_rows > 0 and pathology_dryrun_rows > 0 and not pathology_persisted_hit:
        root_cause = "persisted_bundle_stale_for_pathology"
    elif pathology_local_rows > 0 and pathology_dryrun_rows == 0:
        root_cause = "pathology_assembly_or_bundle_gap"
    elif pathology_local_rows == 0 and surgery_local_rows > 0:
        root_cause = "local_surgery_only_pathology_source_missing"
    elif surgery_local_rows == 0:
        root_cause = "source_or_local_no_data"
    elif surgery_local_rows > 0 and surgery_dryrun_rows == 0:
        root_cause = "surgery_assembly_or_bundle_gap"
    elif pathology_local_rows > 0 and pathology_persisted_hit and pathology_dryrun_rows > 0:
        root_cause = "persisted_bundle_already_current"
    elif surgery_local_rows > 0:
        root_cause = "local_surgery_only_pathology_source_missing"
    else:
        root_cause = "needs_review"
    row["root_cause"] = root_cause
    return row


def _build_report(payload: dict[str, Any]) -> str:
    summary = payload["summary"]
    table_rows = payload["table_coverage"]
    visit_rows = payload["visit_bundle_rows"]
    root_counter = Counter(_safe_text(row.get("root_cause")) for row in visit_rows)
    dryrun_counts = summary["dryrun_bundle_hit_counts"]
    persisted_counts = summary["persisted_bundle_hit_counts"]

    lines = [
        "# SC099源库本地bundle覆盖验证报告",
        "",
        "## 结论",
        "",
        f"- 本轮覆盖 SC-099 样本 `{summary['visit_count']}` 份。",
        f"- source schema 状态：`{summary['source_schema_status']}`。",
        f"- dry-run bundle 组装方式：`{summary['bundle_replay_mode']}`，未写正式质控结果表。",
        f"- public schema 对目标 visit 的 source 行数合计为 `{summary['source_total_rows_all_tables']}`；cdm/local 行数合计为 `{summary['local_total_rows_all_tables']}`。",
        "- 本轮未证明客户真实远端源库覆盖；`public` 只是本机 source schema，当前目标表存在但样本行数为 0。",
        "- 本轮只证明本机 `cdm/local` 与 bundle dry-run 覆盖闭环。",
        f"- pathology local 命中 `{summary['pathology_local_hit_visit_count']}` 份，dry-run bundle 命中 `{summary['pathology_dryrun_hit_visit_count']}` 份，persisted bundle 命中 `{summary['pathology_persisted_hit_visit_count']}` 份。",
        f"- surgery local 命中 `{summary['surgery_local_hit_visit_count']}` 份，dry-run bundle 命中 `{summary['surgery_dryrun_hit_visit_count']}` 份，persisted bundle 命中 `{summary['surgery_persisted_hit_visit_count']}` 份。",
        "- 本轮只验证 source/local/bundle 覆盖，不注册 SC-099 gate，不开放 confirmed。",
        "",
        "## 表级 source/local 覆盖",
        "",
        "| table | source_hit_visit_count | source_total_rows | local_hit_visit_count | local_total_rows | root_cause |",
        "| --- | ---: | ---: | ---: | ---: | --- |",
    ]
    for row in table_rows:
        lines.append(
            "| {table_name} | {source_hit_visit_count} | {source_total_rows} | {local_hit_visit_count} | {local_total_rows} | {root_cause} |".format(
                **row
            )
        )

    lines.extend(
        [
            "",
            "## persisted bundle 与 dry-run bundle 对比",
            "",
            "| bundle/source_table | persisted_hit_visit_count | dryrun_hit_visit_count |",
            "| --- | ---: | ---: |",
        ]
    )
    for key in sorted(dryrun_counts):
        lines.append(f"| {key} | {persisted_counts.get(key, 0)} | {dryrun_counts.get(key, 0)} |")

    lines.extend(
        [
            "",
            "## 逐病历 dry-run bundle 覆盖",
            "",
            "| root_cause | count |",
            "| --- | ---: |",
        ]
    )
    for key, count in sorted(root_counter.items()):
        lines.append(f"| {key} | {count} |")

    lines.extend(
        [
            "",
            "## 根因判定",
            "",
            "- `sync_gap`：source 有数据但 cdm/local 无数据，下一步修同步。",
            "- `source_schema_empty_local_available`：public 目标表存在但样本无行，cdm/local 有行；该 public schema 不能作为有效远端源库覆盖结论。",
            "- `persisted_bundle_stale_for_pathology`：pathology local 有行且 dry-run bundle 能命中，但 persisted bundle 未命中，下一步刷新目标 visit bundle 缓存。",
            "- `local_surgery_only_pathology_source_missing`：本地有 surgery_record，但没有 pathology local 记录；SC-099 缺少病理对照来源，不能 confirmed。",
            "- `pathology_assembly_or_bundle_gap` / `surgery_assembly_or_bundle_gap`：local 有数据但 dry-run bundle 未命中，下一步修 priority 或拼装。",
            "- `source_or_local_no_data` / `source_no_data`：源和本地均无对应病理/手术记录，SC-099 只能 data_quality_gap/rejected 分流，不能 confirmed。",
            "",
            "## 关键样本",
            "",
            "| visit_id | patient_name | local_surgery_record_rows | local_pathology_rows | final_dryrun_surgery | final_dryrun_pathology | root_cause |",
            "| --- | --- | ---: | ---: | ---: | ---: | --- |",
        ]
    )
    for row in visit_rows:
        pathology_rows = int(row.get("local_pathology_exam_master_rows") or 0) + int(row.get("local_pathology_exam_report_rows") or 0)
        lines.append(
            "| {visit_id} | {patient_name} | {surgery_rows} | {pathology_rows} | {final_surgery} | {final_pathology} | {root_cause} |".format(
                visit_id=row.get("visit_id", ""),
                patient_name=row.get("patient_name", ""),
                surgery_rows=row.get("local_surgery_record_rows", 0),
                pathology_rows=pathology_rows,
                final_surgery=row.get("final_bundle_dryrun_surgery_record_assembled_count", 0),
                final_pathology=row.get("final_bundle_dryrun_pathology_assembled_count", 0),
                root_cause=row.get("root_cause", ""),
            )
        )

    lines.extend(
        [
            "",
            "## 收口建议",
            "",
            "- 不应把历史 LLM issue evidence 中的“送病检/冰冻病理”当作源文书证据。",
            "- 对于已有 pathology local 数据的样本，主因是 persisted bundle 未刷新。",
            "- 对于没有 pathology local 数据的样本，仍是病理源数据缺口，不能 confirmed。",
            "- SC-099 下一步应先刷新目标 visit 的 final/course/surgery bundle，再重跑 SC-099 只读 gate。",
            "- 在 SC-099 gate 正式接入前，仍应只开放不适用/证据不足分流，不开放 direct confirmed。",
        ]
    )
    return "\n".join(lines) + "\n"


def _bundle_hit_counts(rows: list[dict[str, Any]], *, prefix: str) -> dict[str, int]:
    keys = (
        "final_bundle_{prefix}_has_surgery_record",
        "final_bundle_{prefix}_has_pathology_exam_master",
        "final_bundle_{prefix}_has_pathology_exam_report",
        "course_bundle_{prefix}_has_pathology_exam_master",
        "course_bundle_{prefix}_has_pathology_exam_report",
        "surgery_bundle_{prefix}_has_surgery_record",
        "surgery_bundle_{prefix}_has_pathology_exam_master",
        "surgery_bundle_{prefix}_has_pathology_exam_report",
    )
    counts: dict[str, int] = {}
    for template in keys:
        key = template.format(prefix=prefix)
        counts[key.replace(f"_{prefix}_", "_")] = sum(1 for row in rows if bool(row.get(key)))
    return counts


def _visit_hit_counts(rows: list[dict[str, Any]]) -> dict[str, int]:
    def pathology_local_hit(row: dict[str, Any]) -> bool:
        return int(row.get("local_pathology_exam_master_rows") or 0) + int(row.get("local_pathology_exam_report_rows") or 0) > 0

    def pathology_dryrun_hit(row: dict[str, Any]) -> bool:
        return (
            int(row.get("final_bundle_dryrun_pathology_assembled_count") or 0)
            + int(row.get("course_bundle_dryrun_pathology_assembled_count") or 0)
            + int(row.get("surgery_bundle_dryrun_pathology_assembled_count") or 0)
            > 0
        )

    def pathology_persisted_hit(row: dict[str, Any]) -> bool:
        return any(
            bool(row.get(key))
            for key in (
                "final_bundle_persisted_has_pathology_exam_master",
                "final_bundle_persisted_has_pathology_exam_report",
                "course_bundle_persisted_has_pathology_exam_master",
                "course_bundle_persisted_has_pathology_exam_report",
                "surgery_bundle_persisted_has_pathology_exam_master",
                "surgery_bundle_persisted_has_pathology_exam_report",
            )
        )

    def surgery_local_hit(row: dict[str, Any]) -> bool:
        return int(row.get("local_surgery_record_rows") or 0) > 0

    def surgery_dryrun_hit(row: dict[str, Any]) -> bool:
        return (
            int(row.get("final_bundle_dryrun_surgery_record_assembled_count") or 0)
            + int(row.get("surgery_bundle_dryrun_surgery_record_assembled_count") or 0)
            > 0
        )

    def surgery_persisted_hit(row: dict[str, Any]) -> bool:
        return bool(row.get("final_bundle_persisted_has_surgery_record")) or bool(
            row.get("surgery_bundle_persisted_has_surgery_record")
        )

    return {
        "pathology_local_hit_visit_count": sum(1 for row in rows if pathology_local_hit(row)),
        "pathology_dryrun_hit_visit_count": sum(1 for row in rows if pathology_dryrun_hit(row)),
        "pathology_persisted_hit_visit_count": sum(1 for row in rows if pathology_persisted_hit(row)),
        "surgery_local_hit_visit_count": sum(1 for row in rows if surgery_local_hit(row)),
        "surgery_dryrun_hit_visit_count": sum(1 for row in rows if surgery_dryrun_hit(row)),
        "surgery_persisted_hit_visit_count": sum(1 for row in rows if surgery_persisted_hit(row)),
    }


def main() -> None:
    visits = _collect_sc099_visits()
    visit_ids = [visit["visit_id"] for visit in visits]
    if not visits:
        raise SystemExit(f"未找到 SC-099 样本：{SC099_PROBE_CSV}")
    if engine is None:
        raise SystemExit("DATABASE_URL is not configured")

    inspector = sa_inspect(engine)
    with engine.connect() as conn:
        source_counts = {
            table_name: _count_rows_by_visit(
                conn,
                inspector=inspector,
                schema=SOURCE_SCHEMA,
                table_name=table_name,
                visit_ids=visit_ids,
            )
            for table_name in TARGET_TABLES
        }
        local_counts = {
            table_name: _count_rows_by_visit(
                conn,
                inspector=inspector,
                schema=LOCAL_SCHEMA,
                table_name=table_name,
                visit_ids=visit_ids,
            )
            for table_name in TARGET_TABLES
        }

        table_rows = _source_presence_summary(
            visit_ids=visit_ids,
            source_counts=source_counts,
            local_counts=local_counts,
        )
        source_tables_exist = any(source_counts[table_name].get("table_exists") for table_name in TARGET_TABLES)
        source_total_rows_all_tables = sum(
            int(source_counts[table_name].get("total_rows") or 0) for table_name in TARGET_TABLES
        )
        if source_tables_exist and source_total_rows_all_tables == 0:
            source_schema_status = "local_public_schema_exists_but_empty"
        elif source_tables_exist:
            source_schema_status = "local_public_schema_has_target_rows"
        else:
            source_schema_status = "remote_unavailable"

        visit_bundle_rows: list[dict[str, Any]] = []
        for visit in visits:
            visit_id = visit["visit_id"]
            identity = _resolve_identity(conn, inspector, visit_id)
            persisted_contexts = {
                bundle_type: _load_persisted_bundle_context(
                    conn,
                    inspector=inspector,
                    bundle_table=bundle_table,
                    visit_id=visit_id,
                )
                for bundle_type, bundle_table in BUNDLE_TABLES.items()
            }
            dry_run_contexts: dict[str, dict[str, Any]] = {}
            dry_run_errors: dict[str, str] = {}
            if identity.get("institute_id") and identity.get("patient_id"):
                for bundle_type in ("final", "course", "surgery"):
                    dry_run_contexts[bundle_type], dry_run_errors[bundle_type] = _dry_run_bundle_context(
                        bundle_type=bundle_type,
                        institute_id=_safe_text(identity.get("institute_id")),
                        patient_id=_safe_text(identity.get("patient_id")),
                        visit_id=visit_id,
                    )
            else:
                dry_run_errors = {bundle_type: "identity_missing" for bundle_type in ("final", "course", "surgery")}
            visit_bundle_rows.append(
                _bundle_row(
                    visit=visit,
                    source_counts=source_counts,
                    local_counts=local_counts,
                    persisted_contexts=persisted_contexts,
                    dry_run_contexts=dry_run_contexts,
                    dry_run_errors=dry_run_errors,
                    identity=identity,
                )
            )

    rows = [*table_rows, *visit_bundle_rows]
    visit_hit_counts = _visit_hit_counts(visit_bundle_rows)
    summary = {
        "visit_count": len(visits),
        "source_schema_status": source_schema_status,
        "bundle_replay_mode": "dry_run_assemble_only_no_persisted_write",
        "source_total_rows_all_tables": sum(int(row.get("source_total_rows") or 0) for row in table_rows),
        "local_total_rows_all_tables": sum(int(row.get("local_total_rows") or 0) for row in table_rows),
        "table_root_cause_counts": dict(Counter(_safe_text(row.get("root_cause")) for row in table_rows)),
        "visit_root_cause_counts": dict(Counter(_safe_text(row.get("root_cause")) for row in visit_bundle_rows)),
        "persisted_bundle_hit_counts": _bundle_hit_counts(visit_bundle_rows, prefix="persisted"),
        "dryrun_bundle_hit_counts": _bundle_hit_counts(visit_bundle_rows, prefix="dryrun"),
        **visit_hit_counts,
    }
    payload = {
        "summary": summary,
        "table_coverage": table_rows,
        "visit_bundle_rows": visit_bundle_rows,
    }
    _write_csv(OUTPUT_CSV, rows)
    _write_json(OUTPUT_JSON, payload)
    OUTPUT_MD.write_text(_build_report(payload), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
