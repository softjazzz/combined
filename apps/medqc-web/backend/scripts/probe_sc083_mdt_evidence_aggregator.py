#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from sqlalchemy import inspect as sa_inspect, text


BACKEND_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = BACKEND_ROOT.parents[2]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.database.connection import Base, engine  # noqa: E402
from app.database.models import cdm as _cdm_models  # noqa: F401,E402
from app.services.qc_applicability_gates.sc083_mdt_evidence_aggregator import (  # noqa: E402
    MdtEvidenceDocument,
    SurgeryCodeGateContext,
    aggregate_sc083_mdt_evidence,
)


DOCS_DIR = REPO_ROOT / "apps" / "medqc-web" / "docs" / "0508"
SURGERY_DIR = DOCS_DIR / "surgery_level_catalog"
CODE_PROBE_CSV = SURGERY_DIR / "sc083_code_gated_second_pass_probe.csv"
OUTPUT_CSV = DOCS_DIR / "sc083_mdt_evidence_aggregator_probe.csv"
OUTPUT_JSON = DOCS_DIR / "sc083_mdt_evidence_aggregator_probe.json"
REPORT_MD = DOCS_DIR / "SC083多学科讨论证据聚合器只读回放报告.md"

DEFAULT_VISIT_IDS = [
    "2142472",
    "2214679",
    "2278814",
    "2287309",
    "2246915",
    "2311318",
    "2200664",
    "1966656",
    "1870471",
    "2268187",
    "2298532",
]
EVIDENCE_TABLES = [
    "consultation_record",
    "presurg_discussion",
    "daily_course_record",
    "senior_course_record",
]
TEXT_FIELDS = [
    "record_content",
    "document_title",
    "v2_schema",
    "submitter",
    "host_name",
    "discuss_staff",
]
TIME_FIELDS = [
    "record_datetime",
    "record_time",
    "submit_datetime",
    "last_modified_datetime",
    "update_time",
]


def _safe_text(value: Any) -> str:
    return str(value or "").strip()


def _read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def _json_for_csv(value: Any) -> str:
    if isinstance(value, (list, dict)):
        return json.dumps(value, ensure_ascii=False, sort_keys=True)
    if isinstance(value, bool):
        return "true" if value else "false"
    return _safe_text(value)


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames: list[str] = []
    for row in rows:
        for key in row:
            if key not in fieldnames:
                fieldnames.append(key)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames or ["message"], extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({key: _json_for_csv(value) for key, value in row.items()})


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _qualified(schema: str, table_name: str) -> str:
    return f'"{schema}"."{table_name}"' if schema else f'"{table_name}"'


def _table_schema(table_name: str) -> tuple[str, list[str]] | None:
    if engine is None:
        return None
    inspector = sa_inspect(engine)
    for schema in ("cdm", "public", ""):
        try:
            if inspector.has_table(table_name, schema=schema or None):
                columns = [column["name"] for column in inspector.get_columns(table_name, schema=schema or None)]
                return schema, columns
        except Exception:
            continue
    table = Base.metadata.tables.get(table_name)
    if table is not None:
        return "", [column.name for column in table.columns]
    return None


def _fetch_evidence_documents(visit_ids: set[str]) -> tuple[dict[str, list[MdtEvidenceDocument]], dict[str, Any]]:
    grouped: dict[str, list[MdtEvidenceDocument]] = defaultdict(list)
    table_meta: dict[str, Any] = {}
    if engine is None:
        return grouped, {"db_available": False, "tables": {}}

    for table_name in EVIDENCE_TABLES:
        info = _table_schema(table_name)
        if not info:
            table_meta[table_name] = {"exists": False, "row_count": 0}
            continue
        schema, columns = info
        selected = ["visit_id"]
        for field in ["document_id", "document_title", "submitter", "host_name", "discuss_staff", "v2_schema", "record_content"]:
            if field in columns:
                selected.append(field)
        for field in TIME_FIELDS:
            if field in columns:
                selected.append(field)
                break
        selected = list(dict.fromkeys(selected))
        select_sql = ", ".join(f'"{field}"' for field in selected)
        sql = f'SELECT {select_sql} FROM {_qualified(schema, table_name)} WHERE CAST("visit_id" AS TEXT) = ANY(:visit_ids)'
        try:
            with engine.connect() as conn:
                db_rows = [dict(row) for row in conn.execute(text(sql), {"visit_ids": list(visit_ids)}).mappings().all()]
        except Exception as exc:
            table_meta[table_name] = {"exists": True, "schema": schema, "row_count": 0, "error": str(exc)[:300]}
            continue
        table_meta[table_name] = {"exists": True, "schema": schema, "row_count": len(db_rows), "columns": selected}
        time_field = next((field for field in TIME_FIELDS if field in selected), "")
        for row in db_rows:
            visit_id = _safe_text(row.get("visit_id"))
            if not visit_id:
                continue
            grouped[visit_id].append(
                MdtEvidenceDocument(
                    visit_id=visit_id,
                    source_table=table_name,
                    document_id=_safe_text(row.get("document_id")),
                    document_title=_safe_text(row.get("document_title")),
                    record_time=_safe_text(row.get(time_field)) if time_field else "",
                    record_content=_safe_text(row.get("record_content")),
                    submitter=_safe_text(row.get("submitter")),
                    host_name=_safe_text(row.get("host_name")),
                    discuss_staff=_safe_text(row.get("discuss_staff")),
                    v2_schema=_safe_text(row.get("v2_schema")),
                )
            )
    return grouped, {"db_available": True, "tables": table_meta}


def _best_code_context(visit_id: str, rows: list[dict[str, str]]) -> SurgeryCodeGateContext:
    if not rows:
        return SurgeryCodeGateContext(visit_id=visit_id, sc083_applicability="level4_applicability_data_gap")
    strong_rows = [
        row
        for row in rows
        if _safe_text(row.get("row_matched_level")) == "4"
        and _safe_text(row.get("row_match_type")) in {"code_exact", "code_normalized"}
    ]
    first = rows[0]
    best = strong_rows[0] if strong_rows else first
    return SurgeryCodeGateContext(
        visit_id=visit_id,
        patient_name=_safe_text(first.get("patient_name")),
        department=_safe_text(first.get("department")),
        visit_max_level=_safe_text(first.get("visit_max_level")) or _safe_text(best.get("row_matched_level")),
        visit_level4_evidence_code=_safe_text(first.get("visit_level4_evidence_code") or best.get("row_surgery_code")),
        visit_level4_evidence_name=_safe_text(first.get("visit_level4_evidence_name") or best.get("row_surgery_name")),
        visit_level4_evidence_source_table=_safe_text(first.get("visit_level4_evidence_source_table") or best.get("row_source_table")),
        strong_match_type=_safe_text(best.get("row_match_type")),
        sc083_applicability=_safe_text(first.get("sc083_applicability")),
    )


def _collect_visit_ids(explicit_visit_ids: list[str]) -> list[str]:
    visit_ids = set(explicit_visit_ids or DEFAULT_VISIT_IDS)
    for row in _read_csv(CODE_PROBE_CSV):
        if _safe_text(row.get("visit_id")) and _safe_text(row.get("rule_id") or "SC-083"):
            visit_ids.add(_safe_text(row.get("visit_id")))
    return sorted(visit_ids)


def _code_rows_by_visit(visit_ids: set[str]) -> dict[str, list[dict[str, str]]]:
    grouped: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in _read_csv(CODE_PROBE_CSV):
        visit_id = _safe_text(row.get("visit_id"))
        if visit_id in visit_ids:
            grouped[visit_id].append(row)
    return grouped


def _summary(rows: list[dict[str, Any]], source_meta: dict[str, Any]) -> dict[str, Any]:
    return {
        "visit_count": len(rows),
        "mdt_evidence_status_counts": dict(Counter(row["mdt_evidence_status"] for row in rows)),
        "suggested_gate_decision_counts": dict(Counter(row["suggested_gate_decision"] for row in rows)),
        "code_gate_passed_count": sum(1 for row in rows if row["code_gate_passed"]),
        "strong_mdt_count": sum(1 for row in rows if row["mdt_evidence_status"] == "level4_applicable_mdt_evidence_strong"),
        "policy_pending_count": sum(
            1 for row in rows if row["mdt_evidence_status"] == "level4_applicable_multidept_consult_policy_pending"
        ),
        "db_source_meta": source_meta,
        "no_dedicated_mdt_record_table": True,
    }


def _report(rows: list[dict[str, Any]], summary: dict[str, Any]) -> str:
    status_counts = summary["mdt_evidence_status_counts"]
    decision_counts = summary["suggested_gate_decision_counts"]
    strong_rows = [row for row in rows if row["mdt_evidence_status"] == "level4_applicable_mdt_evidence_strong"]
    pending_rows = [row for row in rows if row["mdt_evidence_status"] == "level4_applicable_multidept_consult_policy_pending"]
    incomplete_rows = [
        row
        for row in rows
        if row["mdt_evidence_status"]
        in {"level4_applicable_discussion_evidence_incomplete", "level4_applicable_mdt_evidence_missing"}
    ]
    lines = [
        "# SC083 多学科讨论证据聚合器只读回放报告",
        "",
        "## 范围",
        "",
        "- 本轮只做 SC-083 四级手术 MDT/多学科讨论证据聚合器只读回放。",
        "- 不注册 SC-083 gate，不接页面，不写正式 QC 结果表，不开放程序化 confirmed。",
        "- 本地 CDM 未发现专门 `mdt_record` 表；证据从 `consultation_record`、`presurg_discussion`、`daily_course_record`、`senior_course_record` 聚合。",
        "",
        "## 总览",
        "",
        f"- 回放病历数：{summary['visit_count']}",
        f"- code gate 通过数：{summary['code_gate_passed_count']}",
        f"- mdt_evidence_status 分布：`{json.dumps(status_counts, ensure_ascii=False, sort_keys=True)}`",
        f"- 建议分流分布：`{json.dumps(decision_counts, ensure_ascii=False, sort_keys=True)}`",
        "",
        "## 关键口径",
        "",
        "- `consultation_record` 可能包含多科室证据：既可能标题为“多学科会诊记录”，也可能正文中出现多个科室意见。",
        "- 普通多科会诊/联合会诊是否等同正式 MDT：客户口径待确认，本轮不等同，只标记 `policy_pending`。",
        "- 四级手术编码只能证明 SC-083 适用性，不能证明缺陷成立。",
        "- `level4_applicable_mdt_evidence_missing` 最多进入二轮候选，不得程序化 confirmed。",
        "",
        "## 强 MDT/多学科证据样本",
        "",
    ]
    if strong_rows:
        for row in strong_rows[:20]:
            lines.append(
                f"- `{row['visit_id']}` / {row['patient_name']}：{row['strongest_quote']}；sources={row['evidence_source_tables']}"
            )
    else:
        lines.append("- 本轮未发现同时具备 MDT/多学科关键词、主持/原因/结论的强证据样本。")
    lines.extend(["", "## 普通多科室会诊 policy_pending 样本", ""])
    if pending_rows:
        for row in pending_rows[:20]:
            lines.append(
                f"- `{row['visit_id']}` / {row['patient_name']}：departments={row['departments_detected']}；quote={row['strongest_quote']}"
            )
    else:
        lines.append("- 本轮未聚合到普通多科室会诊 policy_pending 样本。")
    lines.extend(["", "## 四级适用但讨论证据不足样本", ""])
    if incomplete_rows:
        for row in incomplete_rows[:20]:
            lines.append(
                f"- `{row['visit_id']}` / {row['patient_name']}：status={row['mdt_evidence_status']}；reason={row['reason']}"
            )
    else:
        lines.append("- 本轮未发现四级适用但讨论证据不足样本。")
    lines.extend(
        [
            "",
            "## 是否建议生产接入",
            "",
            "- 建议暂不生产注册 SC-083 gate。",
            "- 如果后续接入，第一阶段只允许写入 metadata，并做 `data_quality_gap/rejected_by_system` 保守分流；不得开放 confirmed。",
            "- 普通多科会诊是否可替代正式 MDT 必须先由客户确认口径。",
        ]
    )
    return "\n".join(lines) + "\n"


def run(visit_ids: list[str]) -> dict[str, Any]:
    selected = _collect_visit_ids(visit_ids)
    selected_set = set(selected)
    code_rows = _code_rows_by_visit(selected_set)
    documents_by_visit, source_meta = _fetch_evidence_documents(selected_set)

    output_rows: list[dict[str, Any]] = []
    for visit_id in selected:
        code_context = _best_code_context(visit_id, code_rows.get(visit_id, []))
        aggregation = aggregate_sc083_mdt_evidence(code_context, documents_by_visit.get(visit_id, []))
        row = aggregation.to_dict()
        row["source_document_count"] = len(documents_by_visit.get(visit_id, []))
        row["code_probe_row_count"] = len(code_rows.get(visit_id, []))
        output_rows.append(row)

    summary = _summary(output_rows, source_meta)
    payload = {"summary": summary, "rows": output_rows}
    _write_csv(OUTPUT_CSV, output_rows)
    _write_json(OUTPUT_JSON, payload)
    REPORT_MD.write_text(_report(output_rows, summary), encoding="utf-8")
    return payload


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="SC-083 MDT/多学科讨论证据聚合器只读回放。")
    parser.add_argument("--visit-ids", default="", help="逗号分隔 visit_id；默认使用既有 SC-083 样本和固定样本。")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    visit_ids = [item.strip() for item in args.visit_ids.split(",") if item.strip()]
    payload = run(visit_ids)
    print(json.dumps(payload["summary"], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
