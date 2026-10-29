"""已验证的主要文书源列与 CDM 投影合同。

本模块只包含非 PHI 元数据。源列顺序来自三天字段研究包；任何增删或重排都应作为
schema 漂移处理，不能由名称匹配自动放行。
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Final, TypedDict

FieldMappingData = tuple[str | None, str, str]


class PublishContractData(TypedDict):
    target: str
    primary_key: tuple[str, ...]
    required_columns: tuple[str, ...]
    mappings: tuple[FieldMappingData, ...]

EVIDENCE_ZIP_SHA256: Final = (
    "019be2d92c74bd8bce0b01c31098890e7fed1df16ba7392a1e2f63c34af08d71"
)
EVIDENCE_WINDOW: Final = "2026-10-26..2026-10-28"
EVIDENCE_VERSION: Final = f"cache-field-study/{EVIDENCE_WINDOW}@sha256:{EVIDENCE_ZIP_SHA256}"

WEB_MR_SOURCE_COLUMNS: Final = (
    "institute_id",
    "patient_id",
    "visit_id",
    "visit_type",
    "document_id",
    "mr_no",
    "institute_province_code",
    "institute_city_code",
    "institute_county_code",
    "institute_code",
    "institute_county_desc",
    "medical_payment_method",
    "insurance_type",
    "insurance_no",
    "visit_cnt",
    "inpat_no",
    "name",
    "sex",
    "nationality",
    "ethnicity",
    "birthday",
    "age_year",
    "age_month",
    "age",
    "id_card_type",
    "id_card_no",
    "reason_for_missing_ID",
    "occupation_category",
    "marital_status",
    "nativeplace_province",
    "nativeplace_city",
    "nativeplace_county",
    "nativeplace_town",
    "nativeplace_village",
    "nativeplace_detail",
    "nativeplace",
    "nativeplace_postcode",
    "registeredaddress_province",
    "registeredaddress_city",
    "registeredaddress_county",
    "registeredaddress_town",
    "registeredaddress_village",
    "registeredaddress_detail",
    "registeredaddress",
    "registeredaddress_postcode",
    "contact_number",
    "birthplace_province",
    "birthplace_city",
    "birthplace_county",
    "brithplace_town",
    "birthplace_village",
    "birthplace_detail",
    "birthplace",
    "birthplace_postcode",
    "currentaddress_province",
    "currentaddress_city",
    "currentaddress_county",
    "currentaddress_town",
    "currentaddress_village",
    "currentaddress_detail",
    "currentaddress",
    "currentaddress_postcode",
    "currentaddress_phone",
    "contact_name",
    "contact_relationship",
    "contact_address",
    "contact_telephone",
    "work_unit",
    "workplace_province",
    "workplace_city",
    "workplace_county",
    "workplace_town",
    "workplace_village",
    "workplace_detail",
    "workplace",
    "workplace_postcode",
    "work_telephone",
    "admission_route",
    "admission_datetime",
    "admission_condition",
    "admission_dept_name",
    "admission_ward_name",
    "diagnosis_date",
    "transfer_dept_name",
    "discharge_datetime",
    "discharge_dept_name",
    "discharge_ward_name",
    "hospital_duration",
    "ventilator_use_time",
    "pathology_id",
    "allergy_sign",
    "allergy_history",
    "death_autopsy_sign",
    "abo_blood_code",
    "rh_blood_code",
    "deptdirector_sign",
    "deptdirector_code",
    "chief_physician_sign",
    "chief_physician_code",
    "attending_physician_sign",
    "attending_physician_code",
    "resident_physician_sign",
    "resident_physician_code",
    "responsible_nurse_sign",
    "responsible_nurse_code",
    "refresher_physician_sign",
    "intern_physician_sign",
    "coder_sign",
    "medicalrecord_quality",
    "QC_physician_sign",
    "QC_nurse_sign",
    "QC_date",
    "leaving_hospital_way",
    "planned_transder_to",
    "rehospital_with_month",
    "rehospital_with_month_purpose",
    "coma_timebefadm_d",
    "coma_timebefadm_h",
    "coma_timebefadm_min",
    "coma_timeaftadm_d",
    "coma_timeaftadm_h",
    "coma_timeaftadm_min",
    "rbc",
    "platet_volume",
    "plasma_volume",
    "whole_blood_volume",
    "autoblood_trans",
    "albumin",
    "other_cca",
    "other_wbc",
    "daily_surgery_sign",
    "transfusion_reaction_sign",
    "newborn_birthweight",
    "newborn_admitweigth",
    "newborn_birthd_efect",
    "mr_datetime",
    "record_content",
    "clinical_pathway",
    "clinic_path_implement",
    "tcm_drug_applied_sign",
    "tcm_equipment_applied_sign",
    "tcm_method_applied_sign",
    "dialectical_decision",
    "archive_sign",
    "last_modifier",
    "last_modifier_id",
    "last_modified_datetime",
    "update_time",
)

SOURCE_COLUMN_CONTRACTS: Final[Mapping[str, tuple[str, ...]]] = {
    "web.mr": WEB_MR_SOURCE_COLUMNS,
    "web.admission_record": (
        "institute_id", "patient_id", "name", "sex", "inpatno", "mrno",
        "visit_id", "visit_type", "admission_date", "id_card_type", "id_card_no",
        "discharge_date", "inpatient_duration", "documentid", "documenttitle",
        "documentstatus", "submitter", "submitterid", "submitdatetime", "recordcontent",
        "lastmodifier", "lastmodifierid", "lastmodifieddatetime", "updatetime",
        "recorddatetime",
    ),
    "web.first_course_record": (
        "institute_id", "patient_id", "name", "dept_name", "ward_name", "ward_no",
        "bed_no", "age", "sex", "inpatno", "mrno", "visit_id", "visit_type",
        "admission_date", "id_card_type", "id_card_no", "discharge_date",
        "inpatient_duration", "documentid", "documenttitle", "documentstatus",
        "submitter", "submitterid", "submitdatetime", "recordcontent", "lastmodifier",
        "lastmodifierid", "lastmodifieddatetime", "updatetime",
    ),
    "web.daily_course_record": (
        "institute_id", "patient_id", "name", "sex", "age_year", "inpatno", "mrno",
        "visit_id", "visit_type", "admission_date", "dept_name", "ward_name", "ward_no",
        "bed_no", "id_card_type", "id_card_no", "discharge_date", "inpatient_duration",
        "document_id", "document_title", "document_status", "submitter", "submitter_id",
        "submit_datetime", "tcm_diagnosis_summary", "record_content", "note",
        "record_datetime", "physician_sign", "physician_sign_datetime", "last_modifier",
        "last_modifier_id", "last_modified_datetime", "update_time",
    ),
    "web.senior_course_record": (
        "institute_id", "patient_id", "name", "sex", "inpatno", "mrno", "visit_id",
        "visit_type", "admission_date", "id_card_type", "id_card_no", "discharge_date",
        "inpatient_duration", "documentid", "documenttitle", "documentstatus", "submitter",
        "submitterid", "submitdatetime", "recordcontent", "lastmodifier", "lastmodifierid",
        "lastmodifieddatetime", "updatetime",
    ),
    "web.consultation_record": (
        "institute_id", "patient_id", "name", "sex", "inpatno", "mrno", "visit_id",
        "visit_type", "admission_date", "id_card_type", "id_card_no", "discharge_date",
        "inpatient_duration", "documentid", "documenttitle", "documentstatus", "submitter",
        "submitterid", "submitdatetime", "recordcontent", "lastmodifier", "lastmodifierid",
        "lastmodifieddatetime", "updatetime",
    ),
    "web.discharge_record": (
        "institute_id", "patient_id", "name", "dept_name", "ward_name", "ward_no",
        "bed_no", "age", "sex", "inpatno", "mrno", "visit_id", "visit_type",
        "admission_date", "id_card_type", "id_card_no", "discharge_date",
        "inpatient_duration", "document_id", "document_title", "document_status",
        "submitter", "submitter_id", "submit_datetime", "record_content", "last_modifier",
        "last_modifier_id", "last_modified_datetime", "update_time",
    ),
}

WEB_MR_TARGET_COLUMNS: Final = (
    "last_modifier", "last_modifier_id", "last_modified_datetime", "update_time",
    "inpat_no", "mr_no", "name", "sex", "age_year", "age_month", "age",
    "institute_id", "patient_id", "visit_id", "visit_type", "document_id",
    "institute_code", "institute_county_desc", "medical_payment_method", "insurance_type",
    "insurance_no", "visit_cnt", "id_card_type", "id_card_no", "birthday", "nationality",
    "ethnicity", "marital_status", "occupation_category", "nativeplace", "currentaddress",
    "contact_number", "contact_name", "contact_relationship", "contact_address",
    "contact_telephone", "work_unit", "admission_route", "admission_datetime",
    "admission_condition", "admission_dept_name", "admission_ward_name", "diagnosis_date",
    "transfer_dept_name", "discharge_datetime", "discharge_dept_name",
    "discharge_ward_name", "hospital_duration", "pathology_id", "allergy_sign",
    "allergy_history", "abo_blood_code", "rh_blood_code", "death_autopsy_sign",
    "deptdirector_sign", "chief_physician_sign", "attending_physician_sign",
    "resident_physician_sign", "responsible_nurse_sign", "coder_sign", "QC_physician_sign",
    "QC_nurse_sign", "QC_date", "medicalrecord_quality", "leaving_hospital_way",
    "planned_transder_to", "rehospital_with_month", "rehospital_with_month_purpose", "rbc",
    "platet_volume", "plasma_volume", "whole_blood_volume", "autoblood_trans",
    "clinical_pathway", "archive_sign", "mr_datetime", "local_sync_completed_at",
    "record_content",
)

_MR_DATE_FIELDS = frozenset({"birthday", "diagnosis_date", "QC_date"})
_MR_DATETIME_FIELDS = frozenset(
    {
        "last_modified_datetime", "update_time", "admission_datetime",
        "discharge_datetime", "mr_datetime", "local_sync_completed_at",
    }
)


def _mr_mappings() -> tuple[FieldMappingData, ...]:
    result: list[FieldMappingData] = []
    for target in WEB_MR_TARGET_COLUMNS:
        source = None if target == "local_sync_completed_at" else target
        kind = (
            "date"
            if target in _MR_DATE_FIELDS
            else "datetime"
            if target in _MR_DATETIME_FIELDS
            else "text"
        )
        result.append((source, target, kind))
    return tuple(result)


def _document_mappings(*, compact_aliases: bool) -> tuple[tuple[str, str, str], ...]:
    aliases = {
        "inpatno": "inpat_no",
        "mrno": "mr_no",
        "documentid": "document_id",
        "documenttitle": "document_title",
        "documentstatus": "document_status",
        "submitterid": "submitter_id",
        "submitdatetime": "submit_datetime",
        "recordcontent": "record_content",
        "lastmodifier": "last_modifier",
        "lastmodifierid": "last_modifier_id",
        "lastmodifieddatetime": "last_modified_datetime",
        "updatetime": "update_time",
    }
    targets = (
        "institute_id", "patient_id", "visit_id", "visit_type", "name", "sex",
        "inpat_no", "mr_no", "document_id", "document_title", "document_status",
        "submitter", "submitter_id", "submit_datetime", "record_content", "last_modifier",
        "last_modifier_id", "last_modified_datetime", "update_time",
    )
    reverse = {target: source for source, target in aliases.items()}
    result: list[tuple[str, str, str]] = []
    for target in targets:
        source = (
            reverse.get(target, target)
            if compact_aliases or target in {"inpat_no", "mr_no"}
            else target
        )
        kind = (
            "datetime"
            if target in {"submit_datetime", "last_modified_datetime", "update_time"}
            else "text"
        )
        result.append((source, target, kind))
    return tuple(result)


_COMPACT = _document_mappings(compact_aliases=True)
_UNDERSCORE = _document_mappings(compact_aliases=False)

PUBLISH_CONTRACTS: Final[Mapping[str, PublishContractData]] = {
    "web.mr": {
        "target": "cdm.mr",
        "primary_key": ("institute_id", "patient_id", "visit_id"),
        "required_columns": (
            "institute_id",
            "patient_id",
            "visit_id",
        ),
        "mappings": _mr_mappings(),
    },
    "web.admission_record": {
        "target": "cdm.admission_record",
        "primary_key": ("institute_id", "patient_id", "visit_id"),
        "required_columns": (
            "institute_id",
            "patient_id",
            "visit_id",
            "document_id",
            "record_content",
            "submit_datetime",
        ),
        "mappings": _COMPACT
        + (
            ("admission_date", "admission_datetime", "datetime"),
            ("recorddatetime", "record_datetime", "datetime"),
        ),
    },
    "web.first_course_record": {
        "target": "cdm.first_course_record",
        "primary_key": ("institute_id", "patient_id", "visit_id", "document_id"),
        "required_columns": (
            "institute_id",
            "patient_id",
            "visit_id",
            "document_id",
            "record_content",
            "submit_datetime",
        ),
        "mappings": _COMPACT
        + (
            ("dept_name", "dept_name", "text"),
            ("ward_name", "ward_name", "text"),
            ("ward_no", "ward_no", "text"),
            ("bed_no", "bed_no", "text"),
            ("age", "age", "text"),
        ),
    },
    "web.daily_course_record": {
        "target": "cdm.daily_course_record",
        "primary_key": ("institute_id", "patient_id", "visit_id", "document_id"),
        "required_columns": (
            "institute_id",
            "patient_id",
            "visit_id",
            "document_id",
            "record_content",
            "submit_datetime",
        ),
        "mappings": _UNDERSCORE
        + (
            ("age_year", "age_year", "text"),
            ("physician_sign", "physician_sign", "text"),
            (
                "physician_sign_datetime",
                "physician_sign_datetime",
                "timestamptz",
            ),
        ),
    },
    "web.senior_course_record": {
        "target": "cdm.senior_course_record",
        "primary_key": ("institute_id", "patient_id", "visit_id", "document_id"),
        "required_columns": (
            "institute_id",
            "patient_id",
            "visit_id",
            "document_id",
            "record_content",
            "submit_datetime",
        ),
        "mappings": _COMPACT,
    },
    "web.consultation_record": {
        "target": "cdm.consultation_record",
        "primary_key": ("institute_id", "patient_id", "visit_id", "document_id"),
        "required_columns": (
            "institute_id",
            "patient_id",
            "visit_id",
            "document_id",
            "record_content",
            "submit_datetime",
        ),
        "mappings": _COMPACT,
    },
    "web.discharge_record": {
        "target": "cdm.discharge_record",
        "primary_key": ("institute_id", "patient_id", "visit_id"),
        "required_columns": (
            "institute_id",
            "patient_id",
            "visit_id",
            "document_id",
            "record_content",
            "submit_datetime",
        ),
        "mappings": _UNDERSCORE
        + (
            ("age", "age", "text"),
            ("dept_name", "dept_name", "text"),
            ("ward_name", "ward_name", "text"),
            ("admission_date", "admission_date", "date"),
            ("discharge_date", "discharge_date", "date"),
            ("inpatient_duration", "inpatient_duration", "text"),
        ),
    },
}

RAW_KEY_FIELDS: Final[Mapping[str, tuple[str, ...]]] = {
    "web.mr": ("institute_id", "patient_id", "visit_id"),
    "web.admission_record": ("institute_id", "patient_id", "visit_id", "documentid"),
    "web.first_course_record": ("institute_id", "patient_id", "visit_id", "documentid"),
    "web.daily_course_record": ("institute_id", "patient_id", "visit_id", "document_id"),
    "web.senior_course_record": ("institute_id", "patient_id", "visit_id", "documentid"),
    "web.consultation_record": ("institute_id", "patient_id", "visit_id", "documentid"),
    "web.discharge_record": ("institute_id", "patient_id", "visit_id", "document_id"),
}


def contract_export_document(interface: str | None = None) -> dict[str, object]:
    """生成可供 DSH 复制使用的非 PHI JSON 合同。"""
    if interface is not None and interface not in SOURCE_COLUMN_CONTRACTS:
        raise KeyError(interface)
    names = (interface,) if interface is not None else tuple(SOURCE_COLUMN_CONTRACTS)
    interfaces: list[dict[str, object]] = []
    for name in names:
        publish = PUBLISH_CONTRACTS[name]
        interfaces.append(
            {
                "interface": name,
                "procedure": name,
                "argument_count": 1,
                "date_semantics": "single_day",
                "evidence_version": EVIDENCE_VERSION,
                "source_column_count": len(SOURCE_COLUMN_CONTRACTS[name]),
                "ordered_source_columns": list(SOURCE_COLUMN_CONTRACTS[name]),
                "raw_key_fields": list(RAW_KEY_FIELDS[name]),
                "publish_target": publish["target"],
                "target_primary_key": list(publish["primary_key"]),
                "required_target_columns": list(publish["required_columns"]),
                "field_mappings": [
                    {"source": source, "target": target, "target_type": target_type}
                    for source, target, target_type in publish["mappings"]
                ],
                "raw_only_source_columns": [
                    column
                    for column in SOURCE_COLUMN_CONTRACTS[name]
                    if column
                    not in {
                        source
                        for source, _target, _target_type in publish["mappings"]
                        if source is not None
                    }
                ],
            }
        )
    return {
        "contract_version": 1,
        "contains_phi": False,
        "contains_raw_values": False,
        "evidence_zip_sha256": EVIDENCE_ZIP_SHA256,
        "evidence_window": EVIDENCE_WINDOW,
        "interfaces": interfaces,
    }

if len(WEB_MR_SOURCE_COLUMNS) != 148:  # pragma: no cover - import-time evidence invariant
    raise RuntimeError("web.mr source contract must contain 148 columns")
if set(SOURCE_COLUMN_CONTRACTS) != set(PUBLISH_CONTRACTS):  # pragma: no cover
    raise RuntimeError("source and publish interface sets differ")
