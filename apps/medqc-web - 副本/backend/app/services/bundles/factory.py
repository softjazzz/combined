from __future__ import annotations

from typing import Any

from .contracts import (
    BUNDLE_SCHEMA_VERSION_CURRENT,
    BUNDLE_SCENES,
)
from .masking import mask_id_card, mask_mobile, mask_name


def _normalize_scene(scene: str) -> str:
    normalized = str(scene or "").strip().lower()
    if normalized not in BUNDLE_SCENES:
        return "unknown"
    return normalized


def _base_bundle(
    *,
    scene: str,
    policy_version: str,
    institute_id: str,
    patient_id: str,
    visit_id: str,
    department: str = "",
    medical_text: str = "",
    structured_context: dict[str, Any] | None = None,
    document_hits: dict[str, bool] | None = None,
    data_quality_flags: list[str] | None = None,
    patient_name: str = "",
    mobile: str = "",
    id_card: str = "",
) -> dict[str, Any]:
    scene_name = _normalize_scene(scene)
    return {
        "bundle_schema_version": BUNDLE_SCHEMA_VERSION_CURRENT,
        "policy_version": str(policy_version or "policy-legacy-v1"),
        "scene": scene_name,
        "institute_id": str(institute_id or ""),
        "patient_id": str(patient_id or ""),
        "visit_id": str(visit_id or ""),
        "department": str(department or ""),
        "medical_text": str(medical_text or ""),
        "structured_context": dict(structured_context or {}),
        "document_hits": dict(document_hits or {}),
        "text_available": bool(str(medical_text or "").strip()),
        "data_quality_flags": list(data_quality_flags or []),
        "patient_name_masked": mask_name(patient_name),
        "mobile_masked": mask_mobile(mobile),
        "id_card_masked": mask_id_card(id_card),
    }


def build_running_record_bundle(**kwargs: Any) -> dict[str, Any]:
    kwargs["scene"] = "running"
    return _base_bundle(**kwargs)


def build_final_record_bundle(**kwargs: Any) -> dict[str, Any]:
    kwargs["scene"] = "final"
    return _base_bundle(**kwargs)


def build_frontpage_bundle(**kwargs: Any) -> dict[str, Any]:
    kwargs["scene"] = "frontpage"
    return _base_bundle(**kwargs)


def build_coding_bundle(**kwargs: Any) -> dict[str, Any]:
    kwargs["scene"] = "coding"
    return _base_bundle(**kwargs)


def build_settlement_bundle(**kwargs: Any) -> dict[str, Any]:
    kwargs["scene"] = "settlement"
    return _base_bundle(**kwargs)

