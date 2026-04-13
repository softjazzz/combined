from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal


BUNDLE_SCHEMA_VERSION_CURRENT = "bundle-v2"
BUNDLE_SCHEMA_VERSION_PREVIOUS = "bundle-v1"
BUNDLE_SCHEMA_COMPAT_READABLE_VERSIONS = {
    BUNDLE_SCHEMA_VERSION_CURRENT,
    BUNDLE_SCHEMA_VERSION_PREVIOUS,
    "bundle-v0",
}

BUNDLE_SCENES = {
    "running",
    "final",
    "frontpage",
    "coding",
    "settlement",
}

BUNDLE_DOMAINS = {
    "admission",
    "course",
    "surgery",
    "consult_discussion",
    "terminal",
    "index_coding_settlement",
}

RUNNING_FINAL_CONTRACT_FREEZE_VERSION = "running-final-contract-v1"
RUNNING_FINAL_CONTRACT_FREEZE_DATE = "2026-04-03"

BundleName = Literal[
    "RunningRecordBundle",
    "FinalRecordBundle",
    "FrontpageBundle",
    "CodingBundle",
    "SettlementBundle",
]


@dataclass(frozen=True)
class BundleFieldContract:
    name: str
    field_type: str
    required: bool
    source_tables: tuple[str, ...]
    source_priority: tuple[str, ...]
    fallback: str
    masked: bool
    include_in_prompt: bool


_COMMON_FIELDS: tuple[BundleFieldContract, ...] = (
    BundleFieldContract(
        name="bundle_schema_version",
        field_type="string",
        required=True,
        source_tables=("system",),
        source_priority=("constant",),
        fallback="none",
        masked=False,
        include_in_prompt=False,
    ),
    BundleFieldContract(
        name="policy_version",
        field_type="string",
        required=True,
        source_tables=("sync_policy",),
        source_priority=("policy_version",),
        fallback="policy-legacy-v1",
        masked=False,
        include_in_prompt=False,
    ),
    BundleFieldContract(
        name="scene",
        field_type="string",
        required=True,
        source_tables=("visit_index",),
        source_priority=("scene_current",),
        fallback="unknown",
        masked=False,
        include_in_prompt=False,
    ),
    BundleFieldContract(
        name="institute_id",
        field_type="string",
        required=True,
        source_tables=("visit_index",),
        source_priority=("institute_id",),
        fallback="blocked",
        masked=False,
        include_in_prompt=False,
    ),
    BundleFieldContract(
        name="patient_id",
        field_type="string",
        required=True,
        source_tables=("visit_index",),
        source_priority=("patient_id",),
        fallback="blocked",
        masked=False,
        include_in_prompt=False,
    ),
    BundleFieldContract(
        name="visit_id",
        field_type="string",
        required=True,
        source_tables=("visit_index",),
        source_priority=("visit_id",),
        fallback="blocked",
        masked=False,
        include_in_prompt=False,
    ),
    BundleFieldContract(
        name="department",
        field_type="string",
        required=False,
        source_tables=("admission_record", "discharge_record", "mr"),
        source_priority=("admission_dept_name", "discharge_dept_name", "dept_name"),
        fallback="empty",
        masked=False,
        include_in_prompt=True,
    ),
    BundleFieldContract(
        name="medical_text",
        field_type="string",
        required=False,
        source_tables=("multiple_docs",),
        source_priority=("scene_priority_doc_text",),
        fallback="empty",
        masked=True,
        include_in_prompt=True,
    ),
    BundleFieldContract(
        name="structured_context",
        field_type="object",
        required=False,
        source_tables=("multiple_tables",),
        source_priority=("scene_structured_fields",),
        fallback="{}",
        masked=True,
        include_in_prompt=True,
    ),
    BundleFieldContract(
        name="document_hits",
        field_type="object",
        required=True,
        source_tables=("multiple_tables",),
        source_priority=("table_hit_map",),
        fallback="{}",
        masked=False,
        include_in_prompt=False,
    ),
    BundleFieldContract(
        name="text_available",
        field_type="boolean",
        required=True,
        source_tables=("multiple_docs",),
        source_priority=("non_empty_text_fields",),
        fallback="false",
        masked=False,
        include_in_prompt=False,
    ),
    BundleFieldContract(
        name="data_quality_flags",
        field_type="array[string]",
        required=True,
        source_tables=("system",),
        source_priority=("assembly_warnings",),
        fallback="[]",
        masked=False,
        include_in_prompt=False,
    ),
    BundleFieldContract(
        name="patient_name_masked",
        field_type="string",
        required=False,
        source_tables=("patient_information", "mr"),
        source_priority=("patient_name",),
        fallback="empty",
        masked=True,
        include_in_prompt=False,
    ),
    BundleFieldContract(
        name="mobile_masked",
        field_type="string",
        required=False,
        source_tables=("patient_information",),
        source_priority=("mobile", "phone"),
        fallback="empty",
        masked=True,
        include_in_prompt=False,
    ),
    BundleFieldContract(
        name="id_card_masked",
        field_type="string",
        required=False,
        source_tables=("patient_information",),
        source_priority=("id_card", "identity_no"),
        fallback="empty",
        masked=True,
        include_in_prompt=False,
    ),
)


_BUNDLE_DOC_PRIORITY: dict[BundleName, tuple[str, ...]] = {
    "RunningRecordBundle": (
        "admission_record",
        "first_course_record",
        "daily_course_record",
        "senior_course_record",
        "rescue_record",
        "consultation_record",
    ),
    "FinalRecordBundle": (
        "discharge_record",
        "death_record",
        "death_discussion",
        "admission_record",
        "first_course_record",
    ),
    "FrontpageBundle": (
        "mr",
        "diagnosis",
        "mr_surgery",
        "mr_cost",
        "admission_record",
        "discharge_record",
    ),
    "CodingBundle": (
        "mr",
        "diagnosis",
        "mr_surgery",
        "admission_record",
        "discharge_record",
    ),
    "SettlementBundle": (
        "medical_insurance_settlement",
        "mr_cost",
        "mr",
        "diagnosis",
    ),
}

_BUNDLE_EXTRA_FIELDS: dict[BundleName, tuple[BundleFieldContract, ...]] = {
    "RunningRecordBundle": (
        BundleFieldContract(
            name="source_doc_priority",
            field_type="array[string]",
            required=True,
            source_tables=_BUNDLE_DOC_PRIORITY["RunningRecordBundle"],
            source_priority=_BUNDLE_DOC_PRIORITY["RunningRecordBundle"],
            fallback="[]",
            masked=False,
            include_in_prompt=False,
        ),
        BundleFieldContract(
            name="compat_strategy",
            field_type="string",
            required=True,
            source_tables=("system",),
            source_priority=("dual-read-single-write",),
            fallback="dual-read-single-write",
            masked=False,
            include_in_prompt=False,
        ),
    ),
    "FinalRecordBundle": (
        BundleFieldContract(
            name="source_doc_priority",
            field_type="array[string]",
            required=True,
            source_tables=_BUNDLE_DOC_PRIORITY["FinalRecordBundle"],
            source_priority=_BUNDLE_DOC_PRIORITY["FinalRecordBundle"],
            fallback="[]",
            masked=False,
            include_in_prompt=False,
        ),
        BundleFieldContract(
            name="compat_strategy",
            field_type="string",
            required=True,
            source_tables=("system",),
            source_priority=("dual-read-single-write",),
            fallback="dual-read-single-write",
            masked=False,
            include_in_prompt=False,
        ),
    ),
    "FrontpageBundle": (
        BundleFieldContract(
            name="source_doc_priority",
            field_type="array[string]",
            required=True,
            source_tables=_BUNDLE_DOC_PRIORITY["FrontpageBundle"],
            source_priority=_BUNDLE_DOC_PRIORITY["FrontpageBundle"],
            fallback="[]",
            masked=False,
            include_in_prompt=False,
        ),
        BundleFieldContract(
            name="compat_strategy",
            field_type="string",
            required=True,
            source_tables=("system",),
            source_priority=("dual-read-single-write",),
            fallback="dual-read-single-write",
            masked=False,
            include_in_prompt=False,
        ),
    ),
    "CodingBundle": (
        BundleFieldContract(
            name="source_doc_priority",
            field_type="array[string]",
            required=True,
            source_tables=_BUNDLE_DOC_PRIORITY["CodingBundle"],
            source_priority=_BUNDLE_DOC_PRIORITY["CodingBundle"],
            fallback="[]",
            masked=False,
            include_in_prompt=False,
        ),
        BundleFieldContract(
            name="compat_strategy",
            field_type="string",
            required=True,
            source_tables=("system",),
            source_priority=("dual-read-single-write",),
            fallback="dual-read-single-write",
            masked=False,
            include_in_prompt=False,
        ),
    ),
    "SettlementBundle": (
        BundleFieldContract(
            name="source_doc_priority",
            field_type="array[string]",
            required=True,
            source_tables=_BUNDLE_DOC_PRIORITY["SettlementBundle"],
            source_priority=_BUNDLE_DOC_PRIORITY["SettlementBundle"],
            fallback="[]",
            masked=False,
            include_in_prompt=False,
        ),
        BundleFieldContract(
            name="compat_strategy",
            field_type="string",
            required=True,
            source_tables=("system",),
            source_priority=("dual-read-single-write",),
            fallback="dual-read-single-write",
            masked=False,
            include_in_prompt=False,
        ),
    ),
}

_RUNNING_FINAL_STRUCTURED_CONTEXT_FIELDS: tuple[dict[str, Any], ...] = (
    {"name": "anchor_table", "field_type": "string", "required": True, "fallback": "scene_default"},
    {"name": "primary_document_type", "field_type": "string", "required": True, "fallback": "scene_first_priority"},
    {"name": "anchor_time", "field_type": "string", "required": False, "fallback": "empty"},
    {"name": "admission_datetime", "field_type": "string", "required": False, "fallback": "empty"},
    {"name": "discharge_datetime", "field_type": "string", "required": False, "fallback": "empty"},
    {"name": "department", "field_type": "string", "required": False, "fallback": "empty"},
    {"name": "document_rows", "field_type": "object", "required": True, "fallback": "{}"},
    {"name": "text_available_tables", "field_type": "array[string]", "required": True, "fallback": "[]"},
    {"name": "missing_required_docs", "field_type": "array[string]", "required": True, "fallback": "[]"},
    {"name": "record_quality_summary.status", "field_type": "string", "required": True, "fallback": "text_unavailable"},
    {"name": "record_quality_summary.available_doc_count", "field_type": "integer", "required": True, "fallback": "0"},
    {"name": "record_quality_summary.missing_doc_count", "field_type": "integer", "required": True, "fallback": "0"},
    {"name": "documents.<table>[].text_preview", "field_type": "string", "required": False, "fallback": "empty"},
    {"name": "documents.<table>[].update_time", "field_type": "string", "required": False, "fallback": "empty"},
)

_SETTLEMENT_STRUCTURED_CONTEXT_FIELDS: tuple[dict[str, Any], ...] = (
    {"name": "anchor_table", "field_type": "string", "required": True, "fallback": "medical_insurance_settlement"},
    {"name": "primary_document_type", "field_type": "string", "required": True, "fallback": "medical_insurance_settlement"},
    {"name": "department", "field_type": "string", "required": False, "fallback": "empty"},
    {"name": "document_rows", "field_type": "object", "required": True, "fallback": "{}"},
    {"name": "text_available_tables", "field_type": "array[string]", "required": True, "fallback": "[]"},
    {"name": "record_quality_summary.status", "field_type": "string", "required": True, "fallback": "text_unavailable"},
    {"name": "settlement_payload", "field_type": "object", "required": True, "fallback": "{}"},
    {"name": "settlement_payload.diagnoses[]", "field_type": "array[object]", "required": False, "fallback": "[]"},
    {"name": "settlement_payload.surgeries[]", "field_type": "array[object]", "required": False, "fallback": "[]"},
    {"name": "settlement_payload.cost_summary", "field_type": "object", "required": False, "fallback": "{}"},
    {"name": "settlement_payload.cost_details[]", "field_type": "array[object]", "required": False, "fallback": "[]"},
)


def is_bundle_schema_readable(version: str) -> bool:
    return str(version or "").strip() in BUNDLE_SCHEMA_COMPAT_READABLE_VERSIONS


def get_bundle_contract(bundle_name: BundleName) -> list[dict[str, Any]]:
    if bundle_name not in _BUNDLE_DOC_PRIORITY:
        raise ValueError(f"Unsupported bundle name: {bundle_name}")
    result: list[dict[str, Any]] = [field.__dict__.copy() for field in _COMMON_FIELDS]
    result.extend(field.__dict__.copy() for field in _BUNDLE_EXTRA_FIELDS[bundle_name])
    return result


def get_running_final_structured_context_contract(scene: Literal["running", "final"]) -> list[dict[str, Any]]:
    if scene not in {"running", "final"}:
        raise ValueError(f"Unsupported scene: {scene}")
    return [item.copy() for item in _RUNNING_FINAL_STRUCTURED_CONTEXT_FIELDS]


def get_settlement_structured_context_contract() -> list[dict[str, Any]]:
    return [item.copy() for item in _SETTLEMENT_STRUCTURED_CONTEXT_FIELDS]


def get_running_final_contract_freeze_meta() -> dict[str, str]:
    return {
        "freeze_version": RUNNING_FINAL_CONTRACT_FREEZE_VERSION,
        "freeze_date": RUNNING_FINAL_CONTRACT_FREEZE_DATE,
        "bundle_schema_version": BUNDLE_SCHEMA_VERSION_CURRENT,
    }
