from __future__ import annotations

from typing import Any

from .shadow_fact_bundle import FactShadowBundle
from .source_manifest import DocumentManifest


_FAMILY_SOURCE_TABLES: dict[str, tuple[str, ...]] = {
    "basic_timeliness": (
        "admission_record",
        "first_course_record",
        "rescue_record",
        "senior_course_record",
    ),
    "course_quality": (
        "admission_record",
        "first_course_record",
        "daily_course_record",
        "senior_course_record",
        "inpat_drug_order",
    ),
    "exam_lab": (
        "exam_master",
        "exam_item_report",
        "labtest_master",
        "labtest_item_report",
        "daily_course_record",
    ),
    "consultation_quality": (
        "consultation_record",
        "daily_course_record",
    ),
    "surgery_anesthesia": (
        "presurg_discussion",
        "presurg_summary",
        "surgery_record",
        "surgery_safecheck_record",
        "anesthesia_record",
        "postsurg_firstcourse_record",
        "surgery_application",
        "surgery_inform_consent",
        "inpat_drug_order",
    ),
    "transfusion": (
        "blood_application",
        "bloodtrans_record",
        "inpat_drug_order",
        "inpat_nondrug_order",
        "inpat_bill_item",
    ),
    "tumor_pathology": (
        "pathology_exam_master",
        "pathology_exam_report",
        "surgery_record",
        "daily_course_record",
        "inpat_drug_order",
    ),
}


def _safe_text(value: Any) -> str:
    return str(value or "").strip()


def _safe_dict(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, dict) else {}


def _safe_list(value: Any) -> list[Any]:
    return list(value) if isinstance(value, list) else []


def _document_text_length(item: dict[str, Any]) -> int:
    text = _safe_text(
        item.get("content")
        or item.get("raw_text")
        or item.get("content_preview")
        or item.get("text_preview")
    )
    return len(text)


def _collect_document_stats(evidence_payload: dict[str, Any]) -> tuple[dict[str, int], dict[str, int]]:
    timeline = _safe_dict(evidence_payload.get("programmatic_timeline"))
    documents = _safe_dict(timeline.get("documents"))
    source_table_counts: dict[str, int] = {}
    source_table_text_lengths: dict[str, int] = {}
    for raw_table, raw_items in documents.items():
        table = _safe_text(raw_table).lower()
        if not table:
            continue
        items = [_safe_dict(item) for item in _safe_list(raw_items) if _safe_dict(item)]
        source_table_counts[table] = len(items)
        source_table_text_lengths[table] = sum(_document_text_length(item) for item in items)
    return source_table_counts, source_table_text_lengths


def _family_profiles(
    *,
    source_table_counts: dict[str, int],
    source_table_text_lengths: dict[str, int],
) -> dict[str, dict[str, Any]]:
    profiles: dict[str, dict[str, Any]] = {}
    for family_key, required_tables in _FAMILY_SOURCE_TABLES.items():
        present_tables = [table for table in required_tables if source_table_counts.get(table, 0) > 0]
        missing_tables = [table for table in required_tables if source_table_counts.get(table, 0) <= 0]
        profiles[family_key] = {
            "present_source_tables": present_tables,
            "missing_source_tables": missing_tables,
            "document_count": sum(source_table_counts.get(table, 0) for table in required_tables),
            "text_char_count": sum(source_table_text_lengths.get(table, 0) for table in required_tables),
            "ready_for_trimmed_context": bool(present_tables),
        }
    return profiles


def build_luxian_0609_input_profile(
    *,
    visit_id: str,
    medical_text: str,
    evidence_payload: dict[str, Any] | None,
    source_manifest_shadow: DocumentManifest | None = None,
    fact_bundle_shadow: FactShadowBundle | None = None,
) -> dict[str, Any]:
    """Build an observable input profile for future LX0609 fact-gate work.

    The current execution path still uses the original full-text/evidence payload.
    This profile only records what structured facts are available and which family
    contexts could be trimmed later.
    """

    payload = _safe_dict(evidence_payload)
    source_table_counts, source_table_text_lengths = _collect_document_stats(payload)
    primary_text = _safe_text(payload.get("primary_document_text"))
    medical_text_value = _safe_text(medical_text)
    family_profiles = _family_profiles(
        source_table_counts=source_table_counts,
        source_table_text_lengths=source_table_text_lengths,
    )
    available_families = [
        family_key
        for family_key, profile in family_profiles.items()
        if bool(profile.get("ready_for_trimmed_context"))
    ]

    profile = {
        "mode": "full_text_compat",
        "basis": "programmatic_evidence_payload",
        "visit_id": _safe_text(visit_id),
        "evidence_payload_available": bool(payload),
        "payload_keys": sorted(str(key) for key in payload.keys()),
        "primary_text_char_count": len(primary_text),
        "medical_text_char_count": len(medical_text_value),
        "document_count": sum(source_table_counts.values()),
        "source_table_count": len([count for count in source_table_counts.values() if count > 0]),
        "source_table_counts": source_table_counts,
        "source_table_text_lengths": source_table_text_lengths,
        "available_family_contexts": available_families,
        "family_profiles": family_profiles,
    }
    if source_manifest_shadow is None:
        if fact_bundle_shadow is not None:
            raise ValueError("fact bundle shadow requires source manifest shadow")
        return profile
    if not isinstance(source_manifest_shadow, DocumentManifest):
        raise TypeError("source_manifest_shadow must be DocumentManifest or None")
    if source_manifest_shadow.visit_ref != profile["visit_id"]:
        raise ValueError("source manifest visit_ref does not match input profile visit_id")
    profile["source_manifest_shadow"] = {
        "mode": "shadow_only",
        "manifest_schema_version": source_manifest_shadow.manifest_schema_version,
        "visit_ref": source_manifest_shadow.visit_ref,
        "fingerprint": source_manifest_shadow.fingerprint(),
        "source_snapshot_hash": source_manifest_shadow.source_snapshot_hash,
        "entries": [entry.to_dict() for entry in source_manifest_shadow.entries],
    }
    if fact_bundle_shadow is None:
        return profile
    if not isinstance(fact_bundle_shadow, FactShadowBundle):
        raise TypeError("fact_bundle_shadow must be FactShadowBundle or None")
    if fact_bundle_shadow.visit_ref != profile["visit_id"]:
        raise ValueError("fact bundle visit_ref does not match input profile visit_id")
    if fact_bundle_shadow.manifest_fingerprint != source_manifest_shadow.fingerprint():
        raise ValueError("fact bundle manifest fingerprint mismatch")
    if fact_bundle_shadow.source_snapshot_hash != source_manifest_shadow.source_snapshot_hash:
        raise ValueError("fact bundle source snapshot mismatch")
    profile["fact_bundle_shadow"] = {
        "mode": "shadow_only",
        "bundle_schema_version": fact_bundle_shadow.bundle_schema_version,
        "fingerprint": fact_bundle_shadow.fingerprint(),
        "manifest_fingerprint": fact_bundle_shadow.manifest_fingerprint,
        "source_snapshot_hash": fact_bundle_shadow.source_snapshot_hash,
        "fact_count": fact_bundle_shadow.fact_count,
        "fact_ids": [item.fact.fact_id for item in fact_bundle_shadow.items],
        "pair_refs": [item.pair_ref for item in fact_bundle_shadow.items],
    }
    return profile
