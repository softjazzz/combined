from __future__ import annotations

import argparse
import csv
import json
import os
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import insert as pg_insert

REPO_ROOT = Path(__file__).resolve().parents[4]
BACKEND_ROOT = REPO_ROOT / "apps" / "medqc-web" / "backend"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.database.connection import DATABASE_URL  # noqa: E402
from app.services.document_assembly.assembler import assemble_document  # noqa: E402

SOURCE_TXT = REPO_ROOT / "apps" / "medqc-web" / "docs" / "0418" / "缺失文书.txt"
QC_DIR = REPO_ROOT / "apps" / "medqc-web" / "docs" / "0418" / "QC"
REPORT_JSON = QC_DIR / "sheet2_missing_documents_import_report.json"
REPORT_CSV = QC_DIR / "sheet2_missing_documents_import_report.csv"

TARGET_TABLES = {
    "first_course_record",
    "daily_course_record",
    "senior_course_record",
    "consultation_record",
    "surgery_record",
}

COMMON_COLUMNS = [
    "institute_id",
    "patient_id",
    "visit_id",
    "document_id",
    "visit_type",
    "record_content",
    "last_modifier",
    "last_modifier_id",
    "last_modified_datetime",
    "update_time",
    "document_title",
    "document_status",
    "submitter",
    "submitter_id",
    "submit_datetime",
    "inpat_no",
    "mr_no",
    "name",
    "sex",
    "age_year",
    "age_month",
    "age",
]


def _safe_text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _parse_datetime(value: Any) -> datetime | None:
    text = _safe_text(value)
    if not text:
        return None
    text = text.replace("T", " ").replace("Z", "")
    if "+" in text:
        text = text.split("+", 1)[0].strip()
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M:%S.%f", "%Y-%m-%d"):
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            continue
    return None


def _extract_line_json_objects(source: Path) -> list[dict[str, Any]]:
    decoder = json.JSONDecoder()
    objects: list[dict[str, Any]] = []
    for line_no, line in enumerate(source.read_text(encoding="utf-8", errors="ignore").splitlines(), start=1):
        if not line.startswith("{"):
            continue
        try:
            payload, _end = decoder.raw_decode(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(payload, dict):
            continue
        payload["_source_line_no"] = line_no
        objects.append(payload)
    return objects


def _contains_consultation_text(payload: dict[str, Any]) -> bool:
    text = json.dumps(payload.get("record_content") or payload.get("original_text") or payload, ensure_ascii=False)
    return "会诊" in text and ("医师" in text or "谢邀" in text or "已执行" in text)


def _classify_table(payload: dict[str, Any]) -> str:
    title = _safe_text(payload.get("document_title"))
    if "首次病程" in title:
        return "first_course_record"
    if "查房" in title:
        return "senior_course_record"
    if "病程" in title:
        return "daily_course_record"
    if payload.get("surgery_name") or payload.get("surgery_process") or payload.get("surgery_begin_time"):
        return "surgery_record"
    if _contains_consultation_text(payload):
        return "consultation_record"
    if payload.get("record_content") or payload.get("record_time"):
        return "daily_course_record"
    return ""


def _row_for_insert(table_name: str, payload: dict[str, Any]) -> dict[str, Any]:
    assembled = assemble_document(table_name, payload)
    document_title = _safe_text(payload.get("document_title") or assembled.document_title)
    return {
        "institute_id": _safe_text(payload.get("institute_id")) or "泸县人民医院",
        "patient_id": _safe_text(payload.get("patient_id")),
        "visit_id": _safe_text(payload.get("visit_id")),
        "document_id": _safe_text(payload.get("document_id")),
        "visit_type": _safe_text(payload.get("visit_type")) or _safe_text(payload.get("visit_type_code")) or "住院",
        "record_content": assembled.assembled_text or json.dumps(payload, ensure_ascii=False),
        "last_modifier": _safe_text(payload.get("last_modifier")),
        "last_modifier_id": _safe_text(payload.get("last_modifier_id")),
        "last_modified_datetime": _parse_datetime(payload.get("last_modified_time") or payload.get("last_modified_datetime")),
        "update_time": _parse_datetime(payload.get("update_time") or payload.get("sys_source_time")) or datetime.utcnow(),
        "document_title": document_title,
        "document_status": _safe_text(payload.get("document_status")),
        "submitter": _safe_text(payload.get("submitter")),
        "submitter_id": _safe_text(payload.get("submitter_id")),
        "submit_datetime": _parse_datetime(payload.get("submit_time") or payload.get("submit_datetime")),
        "inpat_no": _safe_text(payload.get("inpat_no")),
        "mr_no": _safe_text(payload.get("mr_no")),
        "name": _safe_text(payload.get("name")),
        "sex": _safe_text(payload.get("sex")),
        "age_year": _safe_text(payload.get("age_year")),
        "age_month": _safe_text(payload.get("age_month")),
        "age": _safe_text(payload.get("age")),
    }


def build_import_rows() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for payload in _extract_line_json_objects(SOURCE_TXT):
        table_name = _classify_table(payload)
        if table_name not in TARGET_TABLES:
            continue
        row = _row_for_insert(table_name, payload)
        if not all(row.get(key) for key in ("institute_id", "patient_id", "visit_id", "document_id")):
            continue
        rows.append(
            {
                "source_line_no": payload.get("_source_line_no"),
                "target_table": table_name,
                "primary_key": "|".join(str(row[key]) for key in ("institute_id", "patient_id", "visit_id", "document_id")),
                "visit_id": row["visit_id"],
                "patient_id": row["patient_id"],
                "patient_name": row["name"],
                "document_id": row["document_id"],
                "document_title": row["document_title"],
                "record_content_preview": _safe_text(row["record_content"])[:160],
                "insert_row": row,
            }
        )
    return rows


def _table_object(engine: sa.Engine, metadata: sa.MetaData, table_name: str) -> sa.Table:
    return sa.Table(table_name, metadata, autoload_with=engine)


def _existing_keys(engine: sa.Engine, rows: list[dict[str, Any]]) -> set[tuple[str, str, str, str, str]]:
    if not rows:
        return set()
    existing: set[tuple[str, str, str, str, str]] = set()
    metadata = sa.MetaData()
    grouped: dict[str, list[dict[str, Any]]] = {}
    for item in rows:
        grouped.setdefault(item["target_table"], []).append(item["insert_row"])
    with engine.connect() as conn:
        for table_name, table_rows in grouped.items():
            table = _table_object(engine, metadata, table_name)
            for row in table_rows:
                exists = conn.execute(
                    sa.select(table.c.institute_id)
                    .where(table.c.institute_id == row["institute_id"])
                    .where(table.c.patient_id == row["patient_id"])
                    .where(table.c.visit_id == row["visit_id"])
                    .where(table.c.document_id == row["document_id"])
                    .limit(1)
                ).first()
                if exists:
                    existing.add((table_name, row["institute_id"], row["patient_id"], row["visit_id"], row["document_id"]))
    return existing


def write_reports(report: dict[str, Any]) -> None:
    QC_DIR.mkdir(parents=True, exist_ok=True)
    REPORT_JSON.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    fieldnames = [
        "source_line_no",
        "target_table",
        "action",
        "visit_id",
        "patient_id",
        "patient_name",
        "document_id",
        "document_title",
        "record_content_preview",
    ]
    with REPORT_CSV.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        for item in report["rows"]:
            writer.writerow({key: item.get(key, "") for key in fieldnames})


def apply_writeback(engine: sa.Engine, rows: list[dict[str, Any]]) -> None:
    metadata = sa.MetaData()
    grouped: dict[str, list[dict[str, Any]]] = {}
    for item in rows:
        grouped.setdefault(item["target_table"], []).append(item["insert_row"])
    with engine.begin() as conn:
        for table_name, table_rows in grouped.items():
            table = _table_object(engine, metadata, table_name)
            stmt = pg_insert(table).values(table_rows)
            update_columns = {
                column: getattr(stmt.excluded, column)
                for column in COMMON_COLUMNS
                if column not in {"institute_id", "patient_id", "visit_id", "document_id"}
            }
            stmt = stmt.on_conflict_do_update(
                index_elements=["institute_id", "patient_id", "visit_id", "document_id"],
                set_=update_columns,
            )
            conn.execute(stmt)


def main() -> None:
    global SOURCE_TXT
    parser = argparse.ArgumentParser(description="导入 Sheet2 源库导出的缺失文书到项目 PG")
    parser.add_argument("--writeback", action="store_true", help="实际写入 PG；默认仅 dry-run")
    parser.add_argument("--source", default=str(SOURCE_TXT))
    args = parser.parse_args()

    SOURCE_TXT = Path(args.source)
    rows = build_import_rows()
    if not DATABASE_URL:
        raise RuntimeError("DATABASE_URL 未配置")
    engine = sa.create_engine(DATABASE_URL)
    existing = _existing_keys(engine, rows)
    for item in rows:
        row = item["insert_row"]
        key = (item["target_table"], row["institute_id"], row["patient_id"], row["visit_id"], row["document_id"])
        item["action"] = "update" if key in existing else "insert"

    if args.writeback:
        apply_writeback(engine, rows)

    report_rows = [{key: value for key, value in item.items() if key != "insert_row"} for item in rows]
    report = {
        "mode": "writeback" if args.writeback else "dry-run",
        "source": str(SOURCE_TXT.relative_to(REPO_ROOT)),
        "row_count": len(rows),
        "table_counts": dict(Counter(item["target_table"] for item in rows)),
        "action_counts": dict(Counter(item["action"] for item in rows)),
        "rows": report_rows,
    }
    write_reports(report)
    print(json.dumps({key: report[key] for key in ("mode", "row_count", "table_counts", "action_counts")}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
