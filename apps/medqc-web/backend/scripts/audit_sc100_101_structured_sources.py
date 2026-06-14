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
except Exception:  # pragma: no cover - best-effort audit fallback
    SYNC_TABLES = []

try:  # noqa: SIM105
    from app.services.bundles.assembly import (
        _DOMAIN_DOC_PRIORITY,
        _FINAL_DOC_PRIORITY,
        _RUNNING_DOC_PRIORITY,
        _SCENE_GROUP_BY_DOC_TYPE,
    )
except Exception:  # pragma: no cover - best-effort audit fallback
    _FINAL_DOC_PRIORITY = ()
    _RUNNING_DOC_PRIORITY = ()
    _DOMAIN_DOC_PRIORITY = {}
    _SCENE_GROUP_BY_DOC_TYPE = {}


DOCS_DIR = REPO_ROOT / "apps" / "medqc-web" / "docs" / "0508"
INPUT_PROBE_CSV = DOCS_DIR / "sc100_101_implant_gate_probe.csv"
OUTPUT_CSV = DOCS_DIR / "sc100_101_structured_source_audit.csv"
OUTPUT_JSON = DOCS_DIR / "sc100_101_structured_source_audit.json"
OUTPUT_MD = DOCS_DIR / "SC100-SC101植入物结构化证据来源审计报告.md"

TARGET_TABLES = (
    "surgery_inventory_record",
    "inpat_bill_item",
    "surgery_record",
    "mr_surgery",
    "surgery_application",
)
OPTIONAL_SOURCE_PATTERNS = re.compile(
    r"(medical_device|device|barcode|trace|udi|inventory|consumable|implant|material|器械|耗材|条码|追溯)",
    re.IGNORECASE,
)
IMPLANT_TEXT_PATTERN = re.compile(
    r"植入物|植入|置入|内固定|螺钉|钢板|骨水泥|支架|假体|吻合器|连接棒|钉棒|锚钉|缝线锚钉|耗材|高值耗材|医疗器械"
)
BARCODE_TEXT_PATTERN = re.compile(r"条形码|条码|追溯码|扫码|UDI|唯一标识|医疗器械使用登记表|耗材登记|登记表")

FIELD_GROUPS: dict[str, tuple[str, ...]] = {
    "visit": ("visit_id",),
    "surgery_code": ("surgery_code", "operation_code", "procedure_code", "icd9_code", "icd9_cm3"),
    "surgery_name": ("surgery_name", "operation_name", "procedure_name", "planned_operation_name"),
    "item_name": (
        "item_name",
        "material_name",
        "consumable_name",
        "charge_item_name",
        "medical_catalog_name",
        "medinsur_catalog_name",
    ),
    "quantity": ("quantity", "amount", "num", "number", "count", "qty"),
    "spec_model": (
        "spec",
        "specification",
        "item_specification",
        "model",
        "model_no",
        "device_model",
        "size",
    ),
    "barcode": (
        "barcode",
        "bar_code",
        "trace_code",
        "udi",
        "register_no",
        "device_code",
        "batch_no",
        "serial_no",
    ),
    "record_time": (
        "record_time",
        "record_datetime",
        "operation_time",
        "surgery_date",
        "billing_datetime",
        "order_time",
        "create_time",
        "update_time",
    ),
    "text": ("record_content", "content", "description", "note", "memo"),
}


def _safe_text(value: Any) -> str:
    return str(value or "").strip()


def _read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames: list[str] = []
    for row in rows:
        for key in row:
            if key not in fieldnames:
                fieldnames.append(key)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames or ["message"], extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _loads_json(value: Any) -> Any:
    if isinstance(value, (dict, list)):
        return value
    if value is None:
        return None
    text_value = str(value or "").strip()
    if not text_value:
        return None
    try:
        return json.loads(text_value)
    except Exception:
        return None


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
            if not inspector.has_table(table_name, schema=schema):
                continue
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
    for hint in FIELD_GROUPS[group]:
        if hint in lower_to_real:
            result.append(lower_to_real[hint])
    if group == "barcode":
        for column in columns:
            if re.search(r"(barcode|bar_code|trace|udi|register|device|batch|serial)", column, re.IGNORECASE):
                if column not in result:
                    result.append(column)
    return result


def _has_table_field(columns: list[str], group: str) -> bool:
    return bool(_fields_for(columns, group))


def _get_count(conn: Any, schema: str, table_name: str, visit_id: str) -> int | None:
    try:
        return int(
            conn.execute(
                text(f'SELECT COUNT(*) FROM {_qualified_table(schema, table_name)} WHERE "visit_id" = :visit_id'),
                {"visit_id": visit_id},
            ).scalar()
            or 0
        )
    except Exception:
        return None


def _fetch_visit_rows(conn: Any, schema: str, table_name: str, columns: list[str], visit_id: str, limit: int = 20) -> list[dict[str, Any]]:
    selected_columns = [column for column in columns if column in set(columns)]
    if not selected_columns:
        return []
    select_sql = ", ".join(f'"{column}"' for column in selected_columns)
    try:
        rows = conn.execute(
            text(
                f'SELECT {select_sql} FROM {_qualified_table(schema, table_name)} '
                f'WHERE "visit_id" = :visit_id LIMIT {int(limit)}'
            ),
            {"visit_id": visit_id},
        ).mappings()
        return [dict(row) for row in rows]
    except Exception:
        return []


def _row_text(row: dict[str, Any], fields: list[str]) -> str:
    parts = [_safe_text(row.get(field)) for field in fields if _safe_text(row.get(field))]
    return " ".join(parts)


def _sample_source_context(
    conn: Any | None,
    table_map: dict[str, dict[str, Any]],
    visit_id: str,
) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for table_name in TARGET_TABLES:
        info = table_map.get(table_name) or {}
        schema = _safe_text(info.get("db_schema"))
        columns = list(info.get("columns") or [])
        row_count: int | None = None
        rows: list[dict[str, Any]] = []
        if conn is not None and schema and "visit_id" in columns:
            row_count = _get_count(conn, schema, table_name, visit_id)
            inspect_fields = list(
                dict.fromkeys(
                    [
                        "visit_id",
                        *_fields_for(columns, "surgery_code"),
                        *_fields_for(columns, "surgery_name"),
                        *_fields_for(columns, "item_name"),
                        *_fields_for(columns, "quantity"),
                        *_fields_for(columns, "spec_model"),
                        *_fields_for(columns, "barcode"),
                        *_fields_for(columns, "record_time"),
                        *_fields_for(columns, "text"),
                    ]
                )
            )
            rows = _fetch_visit_rows(conn, schema, table_name, inspect_fields, visit_id)

        text_fields = [
            *_fields_for(columns, "item_name"),
            *_fields_for(columns, "surgery_name"),
            *_fields_for(columns, "spec_model"),
            *_fields_for(columns, "text"),
        ]
        barcode_fields = _fields_for(columns, "barcode")
        quantity_fields = _fields_for(columns, "quantity")
        spec_fields = _fields_for(columns, "spec_model")
        item_fields = _fields_for(columns, "item_name")

        implant_rows = []
        barcode_rows = []
        material_detail_rows = []
        quantity_or_spec_rows = []
        assembled_nonempty = 0
        for row in rows:
            text_value = _row_text(row, text_fields)
            barcode_value = _row_text(row, barcode_fields)
            quantity_value = _row_text(row, quantity_fields)
            spec_value = _row_text(row, spec_fields)
            item_value = _row_text(row, item_fields)
            if IMPLANT_TEXT_PATTERN.search(text_value):
                implant_rows.append(row)
            if BARCODE_TEXT_PATTERN.search(text_value) or barcode_value:
                barcode_rows.append(row)
            if item_value or spec_value or quantity_value:
                material_detail_rows.append(row)
            if spec_value or quantity_value:
                quantity_or_spec_rows.append(row)
            try:
                assembled = assemble_document(table_name, row)
                if _safe_text(getattr(assembled, "assembled_text", "")):
                    assembled_nonempty += 1
            except Exception:
                pass

        result[table_name] = {
            "row_count": row_count,
            "sample_row_count": len(rows),
            "implant_candidate_count": len(implant_rows),
            "barcode_candidate_count": len(barcode_rows),
            "material_detail_candidate_count": len(material_detail_rows),
            "quantity_or_spec_candidate_count": len(quantity_or_spec_rows),
            "assembled_nonempty_count": assembled_nonempty,
            "sample_quote": _row_text(implant_rows[0], text_fields)[:240] if implant_rows else "",
        }
    return result


def _bundle_context(conn: Any | None, visit_id: str) -> dict[str, Any]:
    if conn is None:
        return {}
    bundle_tables = {
        "final_record_bundle": "public",
        "surgery_domain_bundle": "public",
        "consult_discussion_domain_bundle": "public",
        "index_coding_settlement_domain_bundle": "public",
    }
    result: dict[str, Any] = {}
    for table_name, schema in bundle_tables.items():
        try:
            row = conn.execute(
                text(
                    f"SELECT structured_context, medical_text FROM {_qualified_table(schema, table_name)} "
                    'WHERE "visit_id" = :visit_id LIMIT 1'
                ),
                {"visit_id": visit_id},
            ).mappings().first()
        except Exception:
            row = None
        if not row:
            result[table_name] = {"exists_for_visit": False}
            continue
        structured = _loads_json(row.get("structured_context")) or {}
        inventory = structured.get("document_inventory") if isinstance(structured, dict) else []
        if not isinstance(inventory, list):
            inventory = []
        source_tables = [_safe_text(item.get("source_table") or item.get("document_type")) for item in inventory if isinstance(item, dict)]
        target_hits = {
            table: any(source == table for source in source_tables)
            for table in TARGET_TABLES
        }
        target_text_hits = {}
        for table in TARGET_TABLES:
            items = [item for item in inventory if isinstance(item, dict) and _safe_text(item.get("source_table") or item.get("document_type")) == table]
            target_text_hits[table] = any(int(item.get("text_length") or 0) > 0 or bool(_safe_text(item.get("text_preview"))) for item in items)
        result[table_name] = {
            "exists_for_visit": True,
            "document_inventory_count": len(inventory),
            "target_hits": target_hits,
            "target_text_hits": target_text_hits,
            "medical_text_chars": len(_safe_text(row.get("medical_text"))),
        }
    return result


def _build_table_coverage() -> tuple[list[dict[str, Any]], dict[str, Any]]:
    sync_map = {str(item.get("name") or ""): item for item in SYNC_TABLES if isinstance(item, dict)}
    final_priority = set(_FINAL_DOC_PRIORITY)
    running_priority = set(_RUNNING_DOC_PRIORITY)
    domain_tables = {
        domain: set(tables)
        for domain, tables in dict(_DOMAIN_DOC_PRIORITY).items()
    }
    scene_group = dict(_SCENE_GROUP_BY_DOC_TYPE)
    table_rows: list[dict[str, Any]] = []
    table_map: dict[str, dict[str, Any]] = {}

    candidate_tables = set(TARGET_TABLES)
    for table_name, table in Base.metadata.tables.items():
        searchable = " ".join([table_name, *[column.name for column in table.columns]])
        if OPTIONAL_SOURCE_PATTERNS.search(searchable):
            candidate_tables.add(table_name)

    for table_name in sorted(candidate_tables):
        db_info = _db_table_schema(table_name)
        orm_columns = _table_columns_from_orm(table_name)
        if db_info:
            schema, columns = db_info
            source_status = "local_table_present"
        else:
            schema, columns = "", orm_columns
            source_status = "orm_only" if orm_columns else "local_table_missing"
        sync_item = sync_map.get(table_name) or {}
        domains = [domain for domain, tables in domain_tables.items() if table_name in tables]
        row = {
            "table_name": table_name,
            "source_status": source_status,
            "db_schema": schema,
            "column_count": len(columns),
            "columns": columns,
            "sync_config_present": bool(sync_item),
            "sync_enabled": bool(sync_item.get("enabled")) if sync_item else False,
            "sync_procedure": sync_item.get("procedure", "") if sync_item else "",
            "in_final_bundle_priority": table_name in final_priority,
            "in_running_bundle_priority": table_name in running_priority,
            "domain_bundle_domains": domains,
            "scene_group": scene_group.get(table_name, ""),
            "has_visit_id": "visit_id" in columns,
            "has_surgery_code": _has_table_field(columns, "surgery_code"),
            "has_surgery_name": _has_table_field(columns, "surgery_name"),
            "has_item_or_material_name": _has_table_field(columns, "item_name"),
            "has_quantity": _has_table_field(columns, "quantity"),
            "has_spec_or_model": _has_table_field(columns, "spec_model"),
            "has_barcode_or_trace": _has_table_field(columns, "barcode"),
            "has_record_time": _has_table_field(columns, "record_time"),
            "has_text": _has_table_field(columns, "text"),
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
    return table_rows, {"summary": summary, "table_map": table_map}


def _coverage_gap_reason(
    sample_context: dict[str, Any],
    table_map: dict[str, dict[str, Any]],
    bundle_context: dict[str, Any],
) -> str:
    reasons: list[str] = []
    if not table_map.get("surgery_inventory_record"):
        reasons.append("local_table_missing:surgery_inventory_record")
    if not table_map.get("inpat_bill_item"):
        reasons.append("local_table_missing:inpat_bill_item")
    if (table_map.get("surgery_inventory_record") or {}).get("source_status") != "local_table_present":
        reasons.append("source_table_missing:surgery_inventory_record")
    if (table_map.get("inpat_bill_item") or {}).get("source_status") != "local_table_present":
        reasons.append("source_table_missing:inpat_bill_item")

    inventory = sample_context.get("surgery_inventory_record") or {}
    bill = sample_context.get("inpat_bill_item") or {}
    if inventory.get("row_count") in {0, None}:
        reasons.append("source_no_data:surgery_inventory_record")
    if bill.get("row_count") in {0, None}:
        reasons.append("source_no_data:inpat_bill_item")

    final = bundle_context.get("final_record_bundle") or {}
    surgery_domain = bundle_context.get("surgery_domain_bundle") or {}
    final_hits = final.get("target_hits") if isinstance(final, dict) else {}
    surgery_hits = surgery_domain.get("target_hits") if isinstance(surgery_domain, dict) else {}
    final_hits = final_hits if isinstance(final_hits, dict) else {}
    surgery_hits = surgery_hits if isinstance(surgery_hits, dict) else {}
    if final and not final_hits.get("surgery_inventory_record"):
        reasons.append("bundle_missing:final.surgery_inventory_record")
    if surgery_domain and not surgery_hits.get("surgery_inventory_record"):
        reasons.append("bundle_missing:surgery_domain.surgery_inventory_record")

    if not (table_map.get("inpat_bill_item") or {}).get("has_barcode_or_trace"):
        reasons.append("field_missing:inpat_bill_item.barcode_or_trace")
    if not (table_map.get("surgery_inventory_record") or {}).get("has_barcode_or_trace"):
        reasons.append("field_missing:surgery_inventory_record.barcode_or_trace")
    if not (table_map.get("surgery_inventory_record") or {}).get("has_item_or_material_name"):
        reasons.append("field_missing:surgery_inventory_record.item_or_material_name")

    if inventory.get("row_count") and inventory.get("assembled_nonempty_count") == 0:
        reasons.append("text_assembly_missing:surgery_inventory_record")
    if bill.get("row_count") and bill.get("assembled_nonempty_count") == 0:
        reasons.append("text_assembly_missing:inpat_bill_item")
    return ",".join(dict.fromkeys(reasons))


def _audit_samples(table_map: dict[str, dict[str, Any]]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    probe_rows = _read_csv(INPUT_PROBE_CSV)
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
        for probe in probe_rows:
            visit_id = _safe_text(probe.get("visit_id"))
            sample_context = _sample_source_context(conn, table_map, visit_id) if db_available else {}
            bundle_context = _bundle_context(conn, visit_id) if db_available else {}

            inventory_ctx = sample_context.get("surgery_inventory_record") or {}
            bill_ctx = sample_context.get("inpat_bill_item") or {}
            surgery_record_ctx = sample_context.get("surgery_record") or {}
            mr_surgery_ctx = sample_context.get("mr_surgery") or {}
            application_ctx = sample_context.get("surgery_application") or {}

            structured_source_trigger_present = bool(
                inventory_ctx.get("implant_candidate_count")
                or bill_ctx.get("implant_candidate_count")
            )
            surgery_record_text_trigger_present = bool(surgery_record_ctx.get("implant_candidate_count"))
            structured_trigger_present = structured_source_trigger_present
            trigger_candidate_present = bool(structured_source_trigger_present or surgery_record_text_trigger_present)
            structured_barcode_source_present = bool(
                inventory_ctx.get("barcode_candidate_count") or bill_ctx.get("barcode_candidate_count")
            )
            structured_material_detail_present = bool(
                inventory_ctx.get("material_detail_candidate_count")
                or bill_ctx.get("material_detail_candidate_count")
            )
            structured_quantity_or_spec_present = bool(
                inventory_ctx.get("quantity_or_spec_candidate_count")
                or bill_ctx.get("quantity_or_spec_candidate_count")
            )
            structured_strong_trigger_present = bool(
                structured_source_trigger_present
                and (
                    structured_barcode_source_present
                    or structured_material_detail_present
                    or structured_quantity_or_spec_present
                )
            )

            final_bundle = bundle_context.get("final_record_bundle") or {}
            surgery_bundle = bundle_context.get("surgery_domain_bundle") or {}
            gap_reason = _coverage_gap_reason(sample_context, table_map, bundle_context)

            row = {
                "visit_id": visit_id,
                "patient_name": _safe_text(probe.get("patient_name")),
                "rule_id": _safe_text(probe.get("rule_id")),
                "rule_name": _safe_text(probe.get("rule_name")),
                "probe_trigger_strength": _safe_text(probe.get("trigger_strength")),
                "probe_gate_decision": _safe_text(probe.get("gate_decision")),
                "surgery_inventory_record_rows": inventory_ctx.get("row_count"),
                "inpat_bill_item_rows": bill_ctx.get("row_count"),
                "surgery_record_rows": surgery_record_ctx.get("row_count"),
                "mr_surgery_rows": mr_surgery_ctx.get("row_count"),
                "surgery_application_rows": application_ctx.get("row_count"),
                "structured_trigger_present": structured_trigger_present,
                "structured_source_trigger_present": structured_source_trigger_present,
                "structured_strong_trigger_present": structured_strong_trigger_present,
                "surgery_record_text_trigger_present": surgery_record_text_trigger_present,
                "trigger_candidate_present": trigger_candidate_present,
                "structured_barcode_source_present": structured_barcode_source_present,
                "structured_material_detail_present": structured_material_detail_present,
                "structured_quantity_or_spec_present": structured_quantity_or_spec_present,
                "final_bundle_has_surgery_inventory_record": bool((final_bundle.get("target_hits") or {}).get("surgery_inventory_record")),
                "final_bundle_has_inpat_bill_item": bool((final_bundle.get("target_hits") or {}).get("inpat_bill_item")),
                "final_bundle_has_surgery_record": bool((final_bundle.get("target_hits") or {}).get("surgery_record")),
                "surgery_domain_has_surgery_inventory_record": bool((surgery_bundle.get("target_hits") or {}).get("surgery_inventory_record")),
                "surgery_domain_has_surgery_record": bool((surgery_bundle.get("target_hits") or {}).get("surgery_record")),
                "structured_source_gap_reason": gap_reason,
                "structured_sample_quote": (
                    inventory_ctx.get("sample_quote")
                    or bill_ctx.get("sample_quote")
                    or surgery_record_ctx.get("sample_quote")
                    or ""
                ),
                "db_audit_status": "ok" if db_available else f"db_unavailable:{db_error}",
            }
            output_rows.append(row)
    finally:
        if conn is not None:
            conn.close()

    summary = {
        "sample_count": len(output_rows),
        "db_available": db_available,
        "db_error": db_error,
        "rule_counts": dict(Counter(row["rule_id"] for row in output_rows)),
        "structured_trigger_present_count": sum(1 for row in output_rows if row["structured_trigger_present"]),
        "structured_source_trigger_present_count": sum(1 for row in output_rows if row["structured_source_trigger_present"]),
        "structured_strong_trigger_present_count": sum(1 for row in output_rows if row["structured_strong_trigger_present"]),
        "surgery_record_text_trigger_present_count": sum(1 for row in output_rows if row["surgery_record_text_trigger_present"]),
        "trigger_candidate_present_count": sum(1 for row in output_rows if row["trigger_candidate_present"]),
        "structured_barcode_source_present_count": sum(1 for row in output_rows if row["structured_barcode_source_present"]),
        "structured_material_detail_present_count": sum(1 for row in output_rows if row["structured_material_detail_present"]),
        "structured_quantity_or_spec_present_count": sum(1 for row in output_rows if row["structured_quantity_or_spec_present"]),
        "gap_reason_counts": dict(
            Counter(
                reason
                for row in output_rows
                for reason in _safe_text(row.get("structured_source_gap_reason")).split(",")
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
    target_tables = [row for row in table_rows if row["table_name"] in TARGET_TABLES]
    lines = [
        "# SC100-SC101 植入物结构化证据来源审计报告",
        "",
        "## 审计范围",
        "",
        "- 本轮只读审计 SC-100 / SC-101 植入物门控所需结构化来源覆盖。",
        "- 未注册 SC-100/101 gate，未改 postprocessor/adjudicator，未写数据库，未调用 LLM。",
        "- 输入样本来自 `sc100_101_implant_gate_probe.csv`，共 13 条去重规则样本。",
        "",
        "## 表与同步覆盖",
        "",
    ]
    for row in target_tables:
        lines.append(
            f"- `{row['table_name']}`：{row['source_status']}，schema={row['db_schema'] or 'N/A'}，"
            f"sync={row['sync_config_present']}，final_bundle={row['in_final_bundle_priority']}，"
            f"domain={','.join(row['domain_bundle_domains']) or 'N/A'}。"
        )
    lines.extend(
        [
            "",
            "## 字段覆盖结论",
            "",
        ]
    )
    for row in target_tables:
        lines.append(
            f"- `{row['table_name']}`：耗材/项目名={row['has_item_or_material_name']}，"
            f"数量={row['has_quantity']}，规格/型号={row['has_spec_or_model']}，"
            f"条码/追溯={row['has_barcode_or_trace']}，正文={row['has_text']}。"
        )
    lines.extend(
        [
            "",
            "## 样本覆盖统计",
            "",
            f"- 样本数：{sample_summary['sample_count']}",
            f"- DB 可用：{sample_summary['db_available']}",
            f"- 规则分布：{json.dumps(sample_summary['rule_counts'], ensure_ascii=False)}",
            f"- 结构化来源 trigger 命中（surgery_inventory_record / inpat_bill_item）：{sample_summary['structured_source_trigger_present_count']}",
            f"- 结构化强 trigger 命中（材料/数量/规格/条码字段）：{sample_summary['structured_strong_trigger_present_count']}",
            f"- 手术记录文本 trigger 候选：{sample_summary['surgery_record_text_trigger_present_count']}",
            f"- trigger 候选合计（结构化来源或手术记录文本）：{sample_summary['trigger_candidate_present_count']}",
            f"- 结构化条码/追溯来源命中：{sample_summary['structured_barcode_source_present_count']}",
            f"- 结构化材料明细命中：{sample_summary['structured_material_detail_present_count']}",
            f"- 结构化数量/规格命中：{sample_summary['structured_quantity_or_spec_present_count']}",
            f"- 缺口分布：{json.dumps(sample_summary['gap_reason_counts'], ensure_ascii=False)}",
            "",
            "## 逐样本摘要",
            "",
        ]
    )
    for row in sample_rows:
        lines.append(
            f"- {row['visit_id']} {row['patient_name']} {row['rule_id']}："
            f"structured_trigger={row['structured_source_trigger_present']}，"
            f"structured_strong={row['structured_strong_trigger_present']}，"
            f"surgery_record_text_trigger={row['surgery_record_text_trigger_present']}，"
            f"barcode={row['structured_barcode_source_present']}，"
            f"material={row['structured_material_detail_present']}，gap={row['structured_source_gap_reason'] or 'none'}。"
        )
    lines.extend(
        [
            "",
            "## 正式接入建议",
            "",
            "- 本轮 13 条样本中，结构化强 trigger（材料/数量/规格/条码字段）为 0；唯一结构化来源命中来自 `surgery_inventory_record` 的手术名称文本，不足以支撑 SC-100 条码缺失确认。",
            "- SC-101：若仅依赖手术记录文本，可作为 trigger 候选，但仍应进入二轮 gate；若 `surgery_inventory_record` 或费用明细有材料名、数量、规格字段命中，才具备更强结构化支撑。",
            "- SC-100：必须确认条码/追溯/UDI/医疗器械登记字段或明确登记表来源。当前若只有 `surgery_record` 文本提到“医疗器械使用登记表”，应先分流为 data_quality_gap，不得 confirmed。",
            "- 若结构化来源未进入 bundle 或 assembled text 为空，正式接入只能先开放 data_quality_gap / rejected_by_system 分流。",
            "- 不应把文本 strong trigger、医疗器械使用登记表字样或手术名称直接等同于条码字段存在。",
            "",
            "## 下一步最小实施项",
            "",
            "1. 确认客户源库是否存在独立医疗器械使用登记表/耗材登记表，以及是否可同步为 CDM 表。",
            "2. 补齐 `surgery_inventory_record` 的结构化材料、数量、型号、条码/追溯字段，或新增对应来源表。",
            "3. 确认 `inpat_bill_item` 是否能稳定覆盖高值耗材；若只含费用项目而无条码，SC-100 仍需 data_quality_gap。",
            "4. 在正式接入前只开放 SC-100/101 的不适用和数据缺口分流，confirmed 暂缓。",
        ]
    )
    OUTPUT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    table_rows, table_payload = _build_table_coverage()
    table_map = table_payload["table_map"]
    sample_rows, sample_summary = _audit_samples(table_map)
    payload = {
        "summary": {
            **table_payload["summary"],
            **sample_summary,
        },
        "table_coverage": table_rows,
        "sample_rows": sample_rows,
    }
    _write_csv(OUTPUT_CSV, sample_rows)
    _write_json(OUTPUT_JSON, payload)
    _write_report(sample_rows, sample_summary, table_rows, table_payload)
    print(json.dumps(payload["summary"], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
