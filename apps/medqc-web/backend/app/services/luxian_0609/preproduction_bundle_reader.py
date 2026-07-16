"""LX0609 准生产入口的持久化病例包只读读取器。"""

from __future__ import annotations

import json
from typing import Any

from sqlalchemy import text

from ...database.connection import engine


_SCENE_TABLES = {
    "running": "public.running_record_bundle",
    "final": "public.final_record_bundle",
}
_JSON_DEFAULTS: dict[str, Any] = {
    "structured_context": {},
    "document_hits": {},
    "data_quality_flags": [],
    "source_doc_priority": [],
}
_PROJECTION = (
    "institute_id",
    "patient_id",
    "visit_id",
    "scene",
    "department",
    "admission_datetime",
    "discharge_datetime",
    "medical_text",
    "structured_context",
    "document_hits",
    "text_available",
    "data_quality_flags",
    "source_doc_priority",
    "compat_strategy",
    "bundle_schema_version",
    "policy_version",
    "bundle_updated_at",
)


def _parse_json_field(value: Any, *, default: Any) -> Any:
    if isinstance(value, (dict, list)):
        return value
    if not isinstance(value, str) or not value.strip():
        return default.copy()
    try:
        parsed = json.loads(value)
    except (TypeError, ValueError):
        return default.copy()
    return parsed if isinstance(parsed, (dict, list)) else default.copy()


def read_luxian_0609_preproduction_bundle(
    *,
    scene: str,
    institute_id: str,
    patient_id: str,
    visit_id: str,
    schema: str = "public",
) -> dict[str, Any]:
    """按三坐标读取一条已持久化 running/final 病例包。"""

    normalized_scene = str(scene or "").strip().lower()
    if str(schema or "").strip().lower() != "public":
        raise ValueError("unsupported preproduction schema")
    table_name = _SCENE_TABLES.get(normalized_scene)
    if table_name is None:
        raise ValueError("unsupported preproduction scene")
    if engine is None:
        raise RuntimeError("preproduction bundle database is unavailable")

    projection = ", ".join(f'"{field}"' for field in _PROJECTION)
    statement = text(
        f"SELECT {projection} "
        f"FROM {table_name} "
        'WHERE "institute_id" = :institute_id '
        'AND "patient_id" = :patient_id '
        'AND "visit_id" = :visit_id '
        'ORDER BY "bundle_updated_at" DESC '
        "LIMIT 1"
    )
    params = {
        "institute_id": str(institute_id or "").strip(),
        "patient_id": str(patient_id or "").strip(),
        "visit_id": str(visit_id or "").strip(),
    }
    with engine.connect() as connection:
        row = connection.execute(statement, params).mappings().first()
    if row is None:
        raise LookupError("preproduction bundle not found")

    payload = dict(row)
    for field_name, default in _JSON_DEFAULTS.items():
        payload[field_name] = _parse_json_field(
            payload.get(field_name),
            default=default,
        )
    return payload
