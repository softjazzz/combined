#!/usr/bin/env python3
from __future__ import annotations

import csv
import json
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Any


BACKEND_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = BACKEND_ROOT.parents[2]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from sqlalchemy import inspect as sa_inspect, text  # noqa: E402

from app.database.connection import Base, engine  # noqa: E402
from app.database.models import cdm as _cdm_models  # noqa: F401,E402
from app.services.document_assembly import assemble_document  # noqa: E402

try:  # noqa: SIM105
    from app.services.etl_sync import SYNC_TABLES
except Exception:  # pragma: no cover - audit fallback
    SYNC_TABLES = []

try:  # noqa: SIM105
    from app.services.bundles.assembly import _DOMAIN_DOC_PRIORITY, _FINAL_DOC_PRIORITY
except Exception:  # pragma: no cover - audit fallback
    _FINAL_DOC_PRIORITY = ()
    _DOMAIN_DOC_PRIORITY = {}


DOCS_DIR = REPO_ROOT / "apps" / "medqc-web" / "docs" / "0508"
OUTPUT_CSV = DOCS_DIR / "sc099_pathology_specimen_gate_probe.csv"
OUTPUT_JSON = DOCS_DIR / "sc099_pathology_specimen_gate_probe.json"
OUTPUT_MD = DOCS_DIR / "SC099术中取材病理适用性门控只读回放报告.md"

SOURCE_FILES = (
    "formal_qc_random10_original_chain_issue_review.csv",
    "formal_qc_random10_batch2_original_chain_issue_review.csv",
    "formal_qc_random10_batch3_original_chain_issue_review.csv",
    "formal_qc_random10_confirmed_second_pass_review.csv",
    "formal_qc_random10_batch2_confirmed_second_pass_review.csv",
    "formal_qc_random10_batch3_confirmed_second_pass_review.csv",
    "formal_qc_confirmed_second_pass_manual_review_sample.csv",
    "formal_qc_aliyun_bailian_10_visit_issue_review.csv",
    "formal_qc_aliyun_bailian_10_visit_after_evidence_enrichment_issue_review.csv",
)

TARGET_TABLES = (
    "surgery_record",
    "pathology_exam_master",
    "pathology_exam_report",
    "postsurg_firstcourse_record",
    "mr_surgery",
    "surgery_application",
)

STRONG_TRIGGER_PATTERN = re.compile(
    r"取材|标本|送病理|送检|活检|穿刺活检|快速病理|冰冻病理|术中病理|病理检查|病理结果|病理诊断"
)
WEAK_NAME_PATTERN = re.compile(r"切除|肿物|肿块|息肉|病损|包块|占位|活检")
HEADER_ONLY_PATTERN = re.compile(r"^(?:【当前文书】)?\s*(?:记录时间[:：])?\s*\d{4}[-/年]\d{1,2}[-/月]\d{1,2}")

FIELD_HINTS: dict[str, tuple[str, ...]] = {
    "visit": ("visit_id",),
    "name": ("name", "patient_name"),
    "surgery_name": ("surgery_name", "operation_name", "procedure_name", "planned_operation_name"),
    "specimen": ("specimen_name", "sample_name", "pathology_id", "pathology_exam_id"),
    "pathology": (
        "specimen_name",
        "eye_findings",
        "microscope_findings",
        "diagnosis",
        "clinical_history",
        "pathology_id",
        "record_content",
    ),
    "surgery_text": (
        "record_content",
        "surgery_process",
        "surgery_name",
        "preoperative_diagnosis",
        "intraoperative_diagnosis",
        "postoperative_diagnosis",
        "other_content",
    ),
    "course_text": ("record_content", "course_content", "content", "record_text"),
    "time": ("record_time", "record_datetime", "request_datetime", "report_datetime", "surgery_begin_time"),
}


def _safe_text(value: Any) -> str:
    return str(value or "").strip()


def _compact(value: str) -> str:
    return re.sub(r"\s+", "", _safe_text(value))


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
    sanitized_rows: list[dict[str, Any]] = []
    for row in rows:
        sanitized_rows.append(
            {
                key: "\n".join(line.rstrip() for line in value.splitlines()) if isinstance(value, str) else value
                for key, value in row.items()
            }
        )
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=fieldnames or ["message"],
            extrasaction="ignore",
            lineterminator="\n",
        )
        writer.writeheader()
        writer.writerows(sanitized_rows)


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _rule_id(row: dict[str, str]) -> str:
    return _safe_text(row.get("rule_id") or row.get("rule_code")).upper()


def _is_sc099(row: dict[str, str]) -> bool:
    rule_id = _rule_id(row)
    rule_name = _safe_text(row.get("rule_name") or row.get("rule_title"))
    if rule_id:
        return rule_id == "SC-099"
    return any(term in rule_name for term in ("术中取材", "病理结果", "标本", "快速病理", "送病理"))


def _collect_sc099_rows() -> list[dict[str, str]]:
    collected: list[dict[str, str]] = []
    for file_name in SOURCE_FILES:
        path = DOCS_DIR / file_name
        for row in _read_csv(path):
            if not _is_sc099(row):
                continue
            copied = dict(row)
            copied["source_file"] = file_name
            collected.append(copied)

    selected: dict[tuple[str, str], dict[str, str]] = {}
    priority = {
        "confirmed_defect": 5,
        "non_compliant": 4,
        "data_quality_gap": 3,
        "rejected_by_system": 2,
        "technical_error_internal": 1,
    }
    for row in collected:
        visit_id = _safe_text(row.get("visit_id"))
        key = (visit_id, _rule_id(row) or "SC-099")
        status = _safe_text(row.get("display_status") or row.get("second_pass_status") or row.get("status"))
        score = priority.get(status, 0)
        existing = selected.get(key)
        existing_status = _safe_text((existing or {}).get("display_status") or (existing or {}).get("second_pass_status") or (existing or {}).get("status"))
        if existing is None or score > priority.get(existing_status, 0):
            selected[key] = row
    return list(selected.values())


def _table_columns_from_orm(table_name: str) -> list[str]:
    table = Base.metadata.tables.get(table_name)
    if table is None:
        return []
    return [column.name for column in table.columns]


def _db_table_schema(table_name: str) -> tuple[str, list[str]] | None:
    if engine is None:
        return None
    inspector = sa_inspect(engine)
    for schema in ("cdm", "public", None):
        try:
            if inspector.has_table(table_name, schema=schema):
                return schema or "", [column["name"] for column in inspector.get_columns(table_name, schema=schema)]
        except Exception:
            continue
    return None


def _qualified_table(schema: str, table_name: str) -> str:
    if schema:
        return f'"{schema}"."{table_name}"'
    return f'"{table_name}"'


def _fields_for(columns: list[str], group: str) -> list[str]:
    lower_to_real = {column.lower(): column for column in columns}
    result: list[str] = []
    for hint in FIELD_HINTS[group]:
        if hint in lower_to_real:
            result.append(lower_to_real[hint])
    return result


def _row_text(row: dict[str, Any], fields: list[str]) -> str:
    parts = [_safe_text(row.get(field)) for field in fields if _safe_text(row.get(field))]
    return "\n".join(parts)


def _fetch_visit_rows(
    conn: Any | None,
    table_info: dict[str, Any],
    visit_id: str,
    fields: list[str],
) -> tuple[int | None, list[dict[str, Any]]]:
    if conn is None:
        return None, []
    schema = _safe_text(table_info.get("db_schema"))
    table_name = _safe_text(table_info.get("table_name"))
    columns = list(table_info.get("columns") or [])
    if not schema or "visit_id" not in columns:
        return None, []
    try:
        count = int(
            conn.execute(
                text(f'SELECT COUNT(*) FROM {_qualified_table(schema, table_name)} WHERE "visit_id" = :visit_id'),
                {"visit_id": visit_id},
            ).scalar()
            or 0
        )
    except Exception:
        count = None
    selected_fields = [field for field in dict.fromkeys(["visit_id", *fields]) if field in columns]
    if not selected_fields:
        return count, []
    select_sql = ", ".join(f'"{field}"' for field in selected_fields)
    try:
        rows = conn.execute(
            text(
                f'SELECT {select_sql} FROM {_qualified_table(schema, table_name)} '
                'WHERE "visit_id" = :visit_id LIMIT 30'
            ),
            {"visit_id": visit_id},
        ).mappings()
        return count, [dict(row) for row in rows]
    except Exception:
        return count, []


def _assembled_text(table_name: str, row: dict[str, Any]) -> str:
    try:
        assembled = assemble_document(table_name, row)
        text_value = _safe_text(getattr(assembled, "assembled_text", ""))
        if text_value:
            return text_value
    except Exception:
        pass
    return ""


def _quote_around(text_value: str, pattern: re.Pattern[str], window: int = 120) -> str:
    match = pattern.search(text_value)
    if not match:
        return _safe_text(text_value)[:260]
    start = max(0, match.start() - window)
    end = min(len(text_value), match.end() + window)
    return text_value[start:end]


def _looks_like_short_fragment(text_value: str) -> bool:
    compact = _compact(text_value)
    return not compact or len(compact) <= 60 or bool(HEADER_ONLY_PATTERN.search(compact))


def _build_table_coverage() -> tuple[list[dict[str, Any]], dict[str, dict[str, Any]], dict[str, Any]]:
    sync_map = {str(item.get("name") or ""): item for item in SYNC_TABLES if isinstance(item, dict)}
    final_priority = set(_FINAL_DOC_PRIORITY)
    domain_priority = {domain: set(tables) for domain, tables in dict(_DOMAIN_DOC_PRIORITY).items()}
    table_rows: list[dict[str, Any]] = []
    table_map: dict[str, dict[str, Any]] = {}
    for table_name in TARGET_TABLES:
        db_info = _db_table_schema(table_name)
        orm_columns = _table_columns_from_orm(table_name)
        if db_info:
            schema, columns = db_info
            source_status = "local_table_present"
        else:
            schema, columns = "", orm_columns
            source_status = "orm_only" if orm_columns else "local_table_missing"
        domains = [domain for domain, tables in domain_priority.items() if table_name in tables]
        row = {
            "table_name": table_name,
            "source_status": source_status,
            "db_schema": schema,
            "columns": columns,
            "sync_config_present": table_name in sync_map,
            "sync_enabled": bool((sync_map.get(table_name) or {}).get("enabled")) if sync_map.get(table_name) else False,
            "in_final_bundle_priority": table_name in final_priority,
            "domain_bundle_domains": domains,
            "has_visit_id": "visit_id" in columns,
            "has_specimen": bool(_fields_for(columns, "specimen")),
            "has_pathology_fields": bool(_fields_for(columns, "pathology")),
            "has_surgery_text": bool(_fields_for(columns, "surgery_text")),
        }
        table_rows.append(row)
        table_map[table_name] = row
    summary = {
        "target_tables_present": {
            table: (table_map.get(table) or {}).get("source_status") == "local_table_present"
            for table in TARGET_TABLES
        },
        "target_tables_sync_config": {
            table: bool((table_map.get(table) or {}).get("sync_config_present"))
            for table in TARGET_TABLES
        },
        "target_tables_final_bundle_priority": {
            table: bool((table_map.get(table) or {}).get("in_final_bundle_priority"))
            for table in TARGET_TABLES
        },
        "target_tables_domain_bundle_domains": {
            table: list((table_map.get(table) or {}).get("domain_bundle_domains") or [])
            for table in TARGET_TABLES
        },
    }
    return table_rows, table_map, summary


def _table_context(
    conn: Any | None,
    table_map: dict[str, dict[str, Any]],
    table_name: str,
    visit_id: str,
    field_group: str,
) -> dict[str, Any]:
    info = table_map.get(table_name) or {}
    columns = list(info.get("columns") or [])
    fields = [
        *_fields_for(columns, field_group),
        *_fields_for(columns, "time"),
        *_fields_for(columns, "surgery_name"),
        *_fields_for(columns, "specimen"),
    ]
    row_count, rows = _fetch_visit_rows(conn, info, visit_id, list(dict.fromkeys(fields)))
    combined_parts: list[str] = []
    assembled_count = 0
    for row in rows:
        assembled = _assembled_text(table_name, row)
        if assembled:
            assembled_count += 1
            combined_parts.append(assembled)
        combined_parts.append(_row_text(row, list(dict.fromkeys(fields))))
    combined_text = "\n".join(part for part in dict.fromkeys(combined_parts) if _safe_text(part))
    trigger_count = len(STRONG_TRIGGER_PATTERN.findall(combined_text))
    weak_count = len(WEAK_NAME_PATTERN.findall(combined_text))
    return {
        "row_count": row_count,
        "sample_row_count": len(rows),
        "assembled_nonempty_count": assembled_count,
        "assembled_text_chars": sum(len(_assembled_text(table_name, row)) for row in rows),
        "text_chars": len(_safe_text(combined_text)),
        "strong_trigger_count": trigger_count,
        "weak_name_count": weak_count,
        "quote": _quote_around(combined_text, STRONG_TRIGGER_PATTERN),
    }


def _bundle_context(conn: Any | None, visit_id: str) -> dict[str, Any]:
    if conn is None:
        return {}
    bundle_tables = {
        "final_record_bundle": "public",
        "course_domain_bundle": "public",
        "surgery_domain_bundle": "public",
    }
    result: dict[str, Any] = {}
    for table_name, schema in bundle_tables.items():
        select_fields = "structured_context, medical_text" if table_name == "final_record_bundle" else "structured_context"
        try:
            row = conn.execute(
                text(
                    f"SELECT {select_fields} FROM {_qualified_table(schema, table_name)} "
                    'WHERE "visit_id" = :visit_id '
                    "ORDER BY bundle_updated_at DESC NULLS LAST LIMIT 1"
                ),
                {"visit_id": visit_id},
            ).mappings().first()
        except Exception:
            row = None
        if not row:
            result[table_name] = {"exists_for_visit": False}
            continue
        structured_value = row.get("structured_context")
        if isinstance(structured_value, dict):
            structured = structured_value
        else:
            try:
                structured = json.loads(structured_value or "{}")
            except Exception:
                structured = {}
        inventory = structured.get("document_inventory") if isinstance(structured, dict) else []
        if not isinstance(inventory, list):
            inventory = []
        source_tables = [
            _safe_text(item.get("source_table") or item.get("document_type"))
            for item in inventory
            if isinstance(item, dict)
        ]
        result[table_name] = {
            "exists_for_visit": True,
            "target_hits": {table: table in source_tables for table in TARGET_TABLES},
            "medical_text_chars": len(_safe_text(row.get("medical_text"))),
        }
    return result


def _source_text(row: dict[str, str]) -> str:
    keys = (
        "evidence",
        "original_evidence",
        "supporting_quote",
        "source_quote",
        "adjudicator_supporting_quote",
        "conclusion",
        "original_conclusion",
        "findings",
        "suggestion",
        "second_pass_reason",
    )
    return "\n".join(dict.fromkeys(_safe_text(row.get(key)) for key in keys if _safe_text(row.get(key))))


def _decide_gate(
    source_row: dict[str, str],
    surgery_ctx: dict[str, Any],
    master_ctx: dict[str, Any],
    report_ctx: dict[str, Any],
    postsurg_ctx: dict[str, Any],
) -> dict[str, Any]:
    source_text = _source_text(source_row)
    evidence_compact = _compact(source_text)
    surgery_text_available = bool(surgery_ctx.get("row_count") and surgery_ctx.get("text_chars"))
    surgery_record_short = surgery_text_available and int(surgery_ctx.get("text_chars") or 0) < 120
    pathology_rows = int(master_ctx.get("row_count") or 0) + int(report_ctx.get("row_count") or 0)
    pathology_trigger_from_source = bool(pathology_rows)
    surgery_strong_trigger = bool(surgery_ctx.get("strong_trigger_count"))
    postsurg_strong_trigger = bool(postsurg_ctx.get("strong_trigger_count"))
    weak_trigger = bool(WEAK_NAME_PATTERN.search(evidence_compact)) or bool(surgery_ctx.get("weak_name_count"))

    if not surgery_ctx.get("row_count"):
        return {
            "pathology_trigger_status": "unknown",
            "trigger_strength": "unknown",
            "trigger_source": "surgery_record_missing",
            "gate_decision": "data_quality_gap",
            "gate_reason": "缺手术记录，无法判断本次手术是否存在术中取材/送病理触发。",
            "needs_second_pass_gate": False,
            "evidence_quote": source_text[:260],
        }
    if surgery_record_short:
        return {
            "pathology_trigger_status": "unknown",
            "trigger_strength": "unknown",
            "trigger_source": "surgery_record_short_fragment",
            "gate_decision": "data_quality_gap",
            "gate_reason": "手术记录覆盖不足或仅有短片段，不能据此判断取材/病理记录是否缺失。",
            "needs_second_pass_gate": False,
            "evidence_quote": surgery_ctx.get("quote") or source_text[:260],
        }

    if pathology_trigger_from_source or surgery_strong_trigger or postsurg_strong_trigger:
        if pathology_trigger_from_source and not surgery_strong_trigger:
            return {
                "pathology_trigger_status": "present",
                "trigger_strength": "strong",
                "trigger_source": "pathology_exam_source",
                "gate_decision": "pass_to_second_gate",
                "gate_reason": "存在病理申请/报告来源，但手术记录未明确取材/送检/病理结果，需要二轮核对是否属于缺陷或数据缺口。",
                "needs_second_pass_gate": True,
                "evidence_quote": master_ctx.get("quote") or report_ctx.get("quote") or source_text[:260],
            }
        return {
            "pathology_trigger_status": "present",
            "trigger_strength": "strong",
            "trigger_source": "surgery_or_postsurg_record_explicit_specimen_pathology",
            "gate_decision": "pass_to_second_gate",
            "gate_reason": "手术/术后记录存在取材、标本或送病理触发，需二轮核对手术记录是否完整记录取材情况和病理结果。",
            "needs_second_pass_gate": True,
            "evidence_quote": surgery_ctx.get("quote") or postsurg_ctx.get("quote") or source_text[:260],
        }

    if weak_trigger:
        return {
            "pathology_trigger_status": "present",
            "trigger_strength": "contextual_weak",
            "trigger_source": "surgery_name_or_weak_text_only",
            "gate_decision": "data_quality_gap",
            "gate_reason": "仅手术名称或弱文本提示可能涉及取材/病理，缺明确取材、标本或送病理证据，不得判缺陷。",
            "needs_second_pass_gate": False,
            "evidence_quote": surgery_ctx.get("quote") or source_text[:260],
        }

    return {
        "pathology_trigger_status": "absent",
        "trigger_strength": "absent",
        "trigger_source": "no_specimen_or_pathology_trigger",
        "gate_decision": "rejected_by_system",
        "gate_reason": "手术记录和病理来源均未发现取材、标本、送病理、快速病理等触发条件，SC-099 不适用。",
        "needs_second_pass_gate": False,
        "evidence_quote": surgery_ctx.get("quote") or source_text[:260],
    }


def _source_or_sync_gap_reason(
    surgery_ctx: dict[str, Any],
    master_ctx: dict[str, Any],
    report_ctx: dict[str, Any],
    final_bundle: dict[str, Any],
    surgery_bundle: dict[str, Any],
    course_bundle: dict[str, Any],
) -> str:
    reasons: list[str] = []
    if not surgery_ctx.get("row_count"):
        reasons.append("source_no_data:surgery_record")
    if surgery_ctx.get("row_count") and not surgery_ctx.get("assembled_text_chars"):
        reasons.append("text_assembly_missing:surgery_record")
    if not master_ctx.get("row_count"):
        reasons.append("source_no_data:pathology_exam_master")
    if not report_ctx.get("row_count"):
        reasons.append("source_no_data:pathology_exam_report")
    if master_ctx.get("row_count") and not master_ctx.get("assembled_text_chars"):
        reasons.append("text_assembly_missing:pathology_exam_master")
    if report_ctx.get("row_count") and not report_ctx.get("assembled_text_chars"):
        reasons.append("text_assembly_missing:pathology_exam_report")

    final_hits = final_bundle.get("target_hits") if isinstance(final_bundle, dict) else {}
    surgery_hits = surgery_bundle.get("target_hits") if isinstance(surgery_bundle, dict) else {}
    course_hits = course_bundle.get("target_hits") if isinstance(course_bundle, dict) else {}
    final_hits = final_hits if isinstance(final_hits, dict) else {}
    surgery_hits = surgery_hits if isinstance(surgery_hits, dict) else {}
    course_hits = course_hits if isinstance(course_hits, dict) else {}
    for table_name in ("surgery_record", "pathology_exam_master", "pathology_exam_report"):
        if final_bundle and not final_hits.get(table_name):
            reasons.append(f"bundle_missing:final.{table_name}")
    for table_name in ("surgery_record", "pathology_exam_master", "pathology_exam_report"):
        if surgery_bundle and not surgery_hits.get(table_name):
            reasons.append(f"bundle_missing:surgery.{table_name}")
    for table_name in ("pathology_exam_master", "pathology_exam_report"):
        if course_bundle and not course_hits.get(table_name):
            reasons.append(f"bundle_missing:course.{table_name}")
    return ",".join(dict.fromkeys(reasons))


def _audit_samples(table_map: dict[str, dict[str, Any]]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    source_rows = _collect_sc099_rows()
    output_rows: list[dict[str, Any]] = []
    db_available = engine is not None
    db_error = ""
    conn = None
    if db_available:
        try:
            conn = engine.connect()
        except Exception as exc:
            db_available = False
            db_error = str(exc)[:300]

    try:
        for row in source_rows:
            visit_id = _safe_text(row.get("visit_id"))
            surgery_ctx = _table_context(conn, table_map, "surgery_record", visit_id, "surgery_text")
            master_ctx = _table_context(conn, table_map, "pathology_exam_master", visit_id, "pathology")
            report_ctx = _table_context(conn, table_map, "pathology_exam_report", visit_id, "pathology")
            postsurg_ctx = _table_context(conn, table_map, "postsurg_firstcourse_record", visit_id, "course_text")
            bundle = _bundle_context(conn, visit_id) if db_available else {}
            decision = _decide_gate(row, surgery_ctx, master_ctx, report_ctx, postsurg_ctx)
            final_bundle = bundle.get("final_record_bundle") or {}
            surgery_bundle = bundle.get("surgery_domain_bundle") or {}
            course_bundle = bundle.get("course_domain_bundle") or {}
            source_gap_reason = _source_or_sync_gap_reason(
                surgery_ctx,
                master_ctx,
                report_ctx,
                final_bundle,
                surgery_bundle,
                course_bundle,
            )
            output_rows.append(
                {
                    "visit_id": visit_id,
                    "patient_name": _safe_text(row.get("patient_name")),
                    "rule_id": _rule_id(row) or "SC-099",
                    "rule_name": _safe_text(row.get("rule_name") or row.get("rule_title")),
                    "original_status": _safe_text(row.get("display_status") or row.get("status")),
                    "second_pass_status": _safe_text(row.get("second_pass_status")),
                    "source_file": _safe_text(row.get("source_file")),
                    "original_conclusion": _safe_text(row.get("conclusion") or row.get("original_conclusion") or row.get("findings")),
                    "original_evidence": _safe_text(row.get("evidence") or row.get("original_evidence") or row.get("supporting_quote")),
                    "surgery_record_coverage": (
                        "present"
                        if surgery_ctx.get("row_count") and surgery_ctx.get("text_chars")
                        else "missing_or_empty"
                    ),
                    "pathology_source_coverage": (
                        "present"
                        if (master_ctx.get("row_count") or report_ctx.get("row_count"))
                        else "no_pathology_rows"
                    ),
                    "pathology_trigger_status": decision["pathology_trigger_status"],
                    "trigger_strength": decision["trigger_strength"],
                    "trigger_source": decision["trigger_source"],
                    "specimen_terms_detected": ",".join(
                        sorted(set(STRONG_TRIGGER_PATTERN.findall(_source_text(row) + str(surgery_ctx.get("quote")))))
                    ),
                    "pathology_record_count": int(master_ctx.get("row_count") or 0) + int(report_ctx.get("row_count") or 0),
                    "surgery_record_rows": surgery_ctx.get("row_count"),
                    "surgery_record_assembled_len": surgery_ctx.get("assembled_text_chars"),
                    "surgery_record_text_chars": surgery_ctx.get("text_chars"),
                    "postsurg_firstcourse_record_rows": postsurg_ctx.get("row_count"),
                    "pathology_exam_master_rows": master_ctx.get("row_count"),
                    "pathology_exam_report_rows": report_ctx.get("row_count"),
                    "pathology_master_assembled_len": master_ctx.get("assembled_text_chars"),
                    "pathology_report_assembled_len": report_ctx.get("assembled_text_chars"),
                    "final_bundle_has_surgery_record": bool((final_bundle.get("target_hits") or {}).get("surgery_record")),
                    "final_bundle_has_pathology_exam_master": bool((final_bundle.get("target_hits") or {}).get("pathology_exam_master")),
                    "final_bundle_has_pathology_exam_report": bool((final_bundle.get("target_hits") or {}).get("pathology_exam_report")),
                    "surgery_domain_has_surgery_record": bool((surgery_bundle.get("target_hits") or {}).get("surgery_record")),
                    "surgery_domain_has_pathology_exam_master": bool((surgery_bundle.get("target_hits") or {}).get("pathology_exam_master")),
                    "surgery_domain_has_pathology_exam_report": bool((surgery_bundle.get("target_hits") or {}).get("pathology_exam_report")),
                    "course_domain_has_pathology_exam_master": bool((course_bundle.get("target_hits") or {}).get("pathology_exam_master")),
                    "course_domain_has_pathology_exam_report": bool((course_bundle.get("target_hits") or {}).get("pathology_exam_report")),
                    "surgery_record_specimen_quote": surgery_ctx.get("quote"),
                    "pathology_report_quote": report_ctx.get("quote") or master_ctx.get("quote"),
                    "gate_decision": decision["gate_decision"],
                    "gate_reason": decision["gate_reason"],
                    "evidence_quote": decision["evidence_quote"],
                    "source_or_sync_gap_reason": source_gap_reason,
                    "data_source": "history_issue_review+local_cdm_bundle_readonly" if db_available else "history_issue_review_only",
                    "needs_second_pass_gate": decision["needs_second_pass_gate"],
                }
            )
    finally:
        if conn is not None:
            conn.close()

    summary = {
        "sample_count": len(output_rows),
        "db_available": db_available,
        "db_error": db_error,
        "gate_decision_counts": dict(Counter(row["gate_decision"] for row in output_rows)),
        "trigger_strength_counts": dict(Counter(row["trigger_strength"] for row in output_rows)),
        "pathology_trigger_status_counts": dict(Counter(row["pathology_trigger_status"] for row in output_rows)),
        "original_status_counts": dict(Counter(row["original_status"] for row in output_rows)),
        "pathology_source_present_count": sum(1 for row in output_rows if row["pathology_source_coverage"] == "present"),
        "surgery_record_present_count": sum(1 for row in output_rows if row["surgery_record_coverage"] == "present"),
        "source_or_sync_gap_counts": dict(
            Counter(
                reason
                for row in output_rows
                for reason in _safe_text(row.get("source_or_sync_gap_reason")).split(",")
                if reason
            )
        ),
    }
    return output_rows, summary


def _write_report(
    sample_rows: list[dict[str, Any]],
    sample_summary: dict[str, Any],
    table_rows: list[dict[str, Any]],
    table_summary: dict[str, Any],
) -> None:
    lines = [
        "# SC099 术中取材病理适用性门控只读回放报告",
        "",
        "## 审计范围",
        "",
        "- 本轮只读验证 SC-099 术中取材/病理结果规则的 applicability gate。",
        "- 未注册 SC-099 gate，未改 postprocessor/adjudicator，未写数据库，未调用 LLM。",
        "- 样本来自三批随机 10 病历、二轮 confirmed gate、阿里云百炼 10 病历及补强后 issue review 中的 SC-099 记录，按 visit_id + rule_id 去重。",
        "",
        "## 数据源覆盖",
        "",
    ]
    for row in table_rows:
        lines.append(
            f"- `{row['table_name']}`：{row['source_status']}，sync={row['sync_config_present']}，"
            f"final_bundle={row['in_final_bundle_priority']}，domain={','.join(row['domain_bundle_domains']) or 'N/A'}，"
            f"specimen_fields={row['has_specimen']}，pathology_fields={row['has_pathology_fields']}，surgery_text={row['has_surgery_text']}。"
        )
    lines.extend(
        [
            "",
            "## 门控分流统计",
            "",
            f"- 样本数：{sample_summary['sample_count']}",
            f"- DB 可用：{sample_summary['db_available']}",
            f"- 原始状态分布：{json.dumps(sample_summary['original_status_counts'], ensure_ascii=False)}",
            f"- gate 分流：{json.dumps(sample_summary['gate_decision_counts'], ensure_ascii=False)}",
            f"- trigger 强度：{json.dumps(sample_summary['trigger_strength_counts'], ensure_ascii=False)}",
            f"- pathology_trigger_status：{json.dumps(sample_summary['pathology_trigger_status_counts'], ensure_ascii=False)}",
            f"- surgery_record 覆盖样本数：{sample_summary['surgery_record_present_count']}",
            f"- pathology 来源覆盖样本数：{sample_summary['pathology_source_present_count']}",
            f"- 缺口分布：{json.dumps(sample_summary['source_or_sync_gap_counts'], ensure_ascii=False)}",
            "",
            "## 典型逐样本结论",
            "",
        ]
    )
    for row in sample_rows:
        lines.append(
            f"- {row['visit_id']} {row['patient_name']}：original={row['original_status'] or 'N/A'}，"
            f"trigger={row['trigger_strength']}({row['trigger_source']})，decision={row['gate_decision']}，"
            f"pathology_rows={row['pathology_record_count']}，reason={row['gate_reason']}"
        )
    lines.extend(
        [
            "",
            "## 补强前后对比",
            "",
            "- 补强前：`pathology_exam_master` / `pathology_exam_report` 不在 final bundle priority，也不在 domain bundle priority。",
            "- 补强后：两张病理表已进入 final bundle priority，并同时进入 `course` 与 `surgery` domain priority；`assemble_document` 已能拼装病理申请和病理报告关键字段。",
            "- 本轮为只读回放，未写库刷新既有 `final_record_bundle` / domain bundle，因此当前持久化 bundle 的 `document_inventory` 仍显示 pathology 与部分 surgery source 未命中。",
            "- 17 条样本中本地 `pathology_exam_master/report` 行数仍为 0，`surgery_record` 仅 1 条可读；因此 data_quality_gap 未下降，strong trigger 未增加。",
            "",
            "## 结论",
            "",
            "- SC-099 适合程序化 applicability gate：它必须先证明本次手术存在取材、标本、送病理、快速/冰冻病理或病理申请/报告来源。",
            "- 没有取材/病理触发的手术不应要求记录术中取材和病理结果，应分流为 rejected_by_system/not_applicable。",
            "- 缺手术记录、手术记录只有短片段，或只有一审文本提到病理但本地病理/手术记录无法核对时，应分流 data_quality_gap。",
            "- strong trigger 候选仍只应进入 pass_to_second_gate，不得由程序化 gate 直接 confirmed。",
            "- 手术名称中的“切除/肿物/病损”等只能作为 contextual_weak，不得单独作为 strong trigger。",
            "- 本轮已将 pathology_exam_master/pathology_exam_report 纳入 final priority，并同时纳入 course/surgery domain priority；既有持久化 bundle 需刷新后才会体现 document_inventory 命中变化。",
            "",
            "## 正式接入建议",
            "",
            "- 第一阶段可只接入不适用和证据不足分流，阻止所有手术默认套用 SC-099。",
            "- confirmed 暂缓开放；即便存在病理来源或手术记录取材触发，也应交给二轮 LLM gate 核对完整手术记录和病理对照。",
            "- 若正式接入前要提高 confirmed 可靠性，需要确保 pathology_exam_master/report 进入相关 bundle，且 surgery_record 拼装能保留取材、送检、术中病理字段。",
        ]
    )
    OUTPUT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    table_rows, table_map, table_summary = _build_table_coverage()
    sample_rows, sample_summary = _audit_samples(table_map)
    payload = {
        "summary": {
            **table_summary,
            **sample_summary,
        },
        "table_coverage": table_rows,
        "sample_rows": sample_rows,
    }
    _write_csv(OUTPUT_CSV, sample_rows)
    _write_json(OUTPUT_JSON, payload)
    _write_report(sample_rows, sample_summary, table_rows, table_summary)
    print(json.dumps(payload["summary"], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
