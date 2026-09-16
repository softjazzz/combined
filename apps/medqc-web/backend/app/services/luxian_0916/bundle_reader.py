"""Luxian0916 独立病历包读取入口。

只复用通用 bundle 装配设施，不经过四川质控服务或任何既有规则包。
"""

from __future__ import annotations

import json
from typing import Any

from sqlalchemy import text

from ...database.connection import engine
from ..bundles import load_or_assemble_scene_bundle


_SUPPORTED_SCENES = frozenset({"running", "final"})
_PATIENT_AGE_QUERY = text(
    """
    SELECT age_year, age_month, age
    FROM cdm.admission_record
    WHERE institute_id = :institute_id
      AND patient_id = :patient_id
      AND visit_id = :visit_id
    ORDER BY record_datetime DESC NULLS LAST, document_id DESC
    LIMIT 1
    """
)


def _json_value(value: Any) -> Any:
    if isinstance(value, (dict, list)):
        return value
    if isinstance(value, str):
        try:
            return json.loads(value)
        except (TypeError, ValueError):
            return {}
    return {}


def _load_luxian_0916_patient_facts(
    *, institute_id: str, patient_id: str, visit_id: str
) -> dict[str, Any]:
    """只读读取 0916 专属年龄事实；查询失败时保持未知。"""

    if engine is None:
        return {}
    try:
        with engine.connect() as connection:
            row = connection.execute(
                _PATIENT_AGE_QUERY,
                {
                    "institute_id": institute_id,
                    "patient_id": patient_id,
                    "visit_id": visit_id,
                },
            ).mappings().first()
    except Exception:  # noqa: BLE001 - 年龄事实不可用时由规则返回数据缺口
        return {}
    if row is None:
        return {}
    return {
        key: row[key]
        for key in ("age_year", "age_month", "age")
        if row.get(key) is not None and str(row[key]).strip()
    }


def load_luxian_0916_bundle(
    *,
    scene: str,
    institute_id: str,
    patient_id: str,
    visit_id: str,
    schema: str = "public",
) -> dict[str, Any]:
    """按三坐标读取可用于 0916 的通用场景病历包。"""

    normalized_scene = str(scene or "").strip().lower()
    if normalized_scene not in _SUPPORTED_SCENES:
        raise ValueError(f"unsupported Luxian0916 bundle scene: {scene}")
    if engine is None:
        raise RuntimeError("DATABASE_URL is not configured; bundle loading unavailable")
    coordinates = tuple(
        str(value or "").strip() for value in (institute_id, patient_id, visit_id)
    )
    if not all(coordinates):
        raise ValueError("Luxian0916 bundle coordinates are incomplete")
    payload = load_or_assemble_scene_bundle(
        scene=normalized_scene,
        institute_id=coordinates[0],
        patient_id=coordinates[1],
        visit_id=coordinates[2],
        bundle_schema=schema,
        force_refresh=False,
        force_refresh_if_empty=True,
    )
    if not payload:
        raise LookupError(
            f"Luxian0916 bundle not found: {normalized_scene} "
            f"{coordinates[0]}/{coordinates[1]}/{coordinates[2]}"
        )
    result = dict(payload)
    for key in (
        "structured_context",
        "document_hits",
        "data_quality_flags",
        "source_doc_priority",
    ):
        result[key] = _json_value(result.get(key))
    patient_facts = _load_luxian_0916_patient_facts(
        institute_id=coordinates[0],
        patient_id=coordinates[1],
        visit_id=coordinates[2],
    )
    if patient_facts:
        structured = dict(result["structured_context"])
        luxian_facts = _json_value(structured.get("luxian_0916_facts"))
        luxian_facts["patient"] = {
            **_json_value(luxian_facts.get("patient")),
            **patient_facts,
        }
        structured["luxian_0916_facts"] = luxian_facts
        result["structured_context"] = structured
    return result


__all__ = ["load_luxian_0916_bundle"]
