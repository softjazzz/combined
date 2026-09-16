"""Luxian0916 独立病历包读取入口。

只复用通用 bundle 装配设施，不经过四川质控服务或任何既有规则包。
"""

from __future__ import annotations

import json
from typing import Any

from ...database.connection import engine
from ..bundles import load_or_assemble_scene_bundle


_SUPPORTED_SCENES = frozenset({"running", "final"})


def _json_value(value: Any) -> Any:
    if isinstance(value, (dict, list)):
        return value
    if isinstance(value, str):
        try:
            return json.loads(value)
        except (TypeError, ValueError):
            return {}
    return {}


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
    return result


__all__ = ["load_luxian_0916_bundle"]
