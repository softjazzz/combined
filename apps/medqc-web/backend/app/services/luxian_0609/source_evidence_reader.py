"""LX0609 受控只读来源证据：纯时间/摘要函数与显式有界查询。"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import hashlib
import json
import re
from types import MappingProxyType
from typing import Any, Mapping
from zoneinfo import ZoneInfo

from app.services.bundles import assembly as bundle_assembly
from app.services import case_material_snapshot as case_material
from app.services.discharge_time import select_discharge_time
from app.services.validation_material_source import (
    DOCUMENT_STATUS_TABLES,
    material_document_sql_filter,
    material_document_status_column,
    material_source_schema,
)

from .surgery_procedure_catalog import catalog_surgery_state
from .surgery_safecheck_evidence import SAFECHECK_FIELDS


_PERFORMED_TIME_TEXT_PATTERN = re.compile(
    r"(?P<naive>\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})(?P<offset>Z|[+-]\d{2}(?::\d{2})?)"
)
# 只接受本流水线实际会产出的两种显式写法：医院本地 `+08` 与 UTC `+00`/`Z`。
# `surgery_record` 的时间列是 text：客户 timestamptz 列经本机导入后，同一列里
# 同时存在 `+08`（148 行）与 `+00`（15 行）两种写法，两者表示同一精确时刻。
# 其它偏移（如 `+09`）在全部 445 个取值中从未出现，也不是本地导入的产物，
# 继续按“非精确时间”拒绝，避免把来历不明的时间当作已实施证据。
_PERFORMED_TIME_OFFSETS: Mapping[str, timezone] = MappingProxyType(
    {
        "Z": timezone.utc,
        "+00": timezone.utc,
        "+00:00": timezone.utc,
        "+08": timezone(timedelta(hours=8)),
        "+08:00": timezone(timedelta(hours=8)),
    }
)
_HOSPITAL_TIMEZONE = ZoneInfo("Asia/Shanghai")


def _case_source_schema(*, institute_id: str, patient_id: str, visit_id: str, source_schema: str | None) -> str:
    try:
        return material_source_schema(default_schema=bundle_assembly._default_source_schema(),
            requested_schema=source_schema, institute_id=institute_id, patient_id=patient_id,
            visit_id=visit_id, strict=True)
    except ValueError:
        raise SourceEvidenceUnavailable() from None

def _material_document_filter(
    *, schema: str, table: str, columns: set[str], institute_id: str, patient_id: str, visit_id: str,
) -> tuple[str, dict[str, Any]]:
    try:
        return material_document_sql_filter(source_schema=schema, source_table=table,
            institute_id=institute_id, patient_id=patient_id, visit_id=visit_id,
            source_columns=columns)
    except Exception:
        # 复核决定读取失败不能退回双份材料或伪装成空来源。
        raise SourceEvidenceQueryError() from None


def _with_document_status_projection(
    *, table: str, columns: set[str], selected: list[str],
) -> tuple[list[str], str | None]:
    """把文书状态以规范字段名投影；兼容物理别名 documentstatus。"""

    status_column = material_document_status_column(
        source_table=table,
        source_columns=columns,
    )
    projected = list(selected)
    if status_column and status_column not in projected:
        projected.append(status_column)
    return projected, status_column


def _select_sql_with_document_status(
    selected: list[str], status_column: str | None,
) -> str:
    return ", ".join(
        (
            f"{bundle_assembly._quote_ident(field)} AS "
            f"{bundle_assembly._quote_ident('document_status')}"
            if field == status_column and field != "document_status"
            else bundle_assembly._quote_ident(field)
        )
        for field in selected
    )


SURGERY_TIME_FIELDS = (
    "surgery_begin_time",
    "surgery_begin_datetime",
    "surgery_end_time",
    "surgery_end_datetime",
)
CURRENT_VISIT_UNSTABLE_ORDER_SOURCE_KEY = "inpat_nondrug_order.unstable_order"
CURRENT_VISIT_SEVERITY_ORDER_SOURCE_KEY = "inpat_nondrug_order.severity_order"
CURRENT_VISIT_EXAM_LAB_ORDER_SOURCE_KEY = "inpat_nondrug_order.exam_lab_order"
CURRENT_VISIT_RESCUE_ORDER_SOURCE_KEY = "inpat_nondrug_order.rescue_order"
CURRENT_VISIT_DISCHARGE_HORIZON_SOURCE_KEY = "inpat_registration.discharge_horizon"
EVALUATION_HORIZON_SOURCE_KEY = "evaluation_context.horizon"
ROUTINE_LAB_ITEM_SOURCE_KEY = "labtest_item_report.routine_panel"
AUTHORITATIVE_DOCUMENT_TIME_FIELDS = (
    "record_time",
    "record_datetime",
    "submit_time",
    "submit_datetime",
)
_SEVERITY_ORDER_TERMINAL_MARKERS = (
    "解除",
    "停止",
    "停病危",
    "停病重",
)
_SEVERITY_ORDER_CANCELLED_NAME_MARKERS = ("取消", "撤销", "作废")
_EFFECTIVE_SEVERITY_ORDER_STATUSES = frozenset(
    ("新开", "执行中", "执行", "核实", "停止", "已停止")
)
_STOPPED_SEVERITY_ORDER_STATUSES = frozenset(("停止", "已停止"))
_EXCLUDED_SEVERITY_ORDER_STATUSES = frozenset(
    ("取消", "撤销", "作废", "已取消", "已撤销", "已作废", "未执行")
)
_EXCLUDED_SEVERITY_ORDER_STATUS_PARAMS = MappingProxyType(
    {
        "cancelled_status": "取消",
        "revoked_status": "撤销",
        "voided_status": "作废",
        "already_cancelled_status": "已取消",
        "already_revoked_status": "已撤销",
        "already_voided_status": "已作废",
        "unexecuted_status": "未执行",
    }
)
_RESCUE_END_TIME_PATTERN = re.compile(
    r"(?:^|[\n\r；;])\s*抢救结束时间\s*[:：]\s*(?P<value>"
    r"\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}(?::\d{2})?"
    r"|\d{4}年\d{1,2}月\d{1,2}日\s+\d{1,2}:\d{2}(?::\d{2})?"
    r")",
    flags=re.MULTILINE,
)

_NATIVE_SOURCE_FIELDS = {
    "inpat_registration": (
        "admission_datetime",
        "admission_time",
        "discharge_datetime",
        "discharge_time",
        "discharge_status",
        "discharge_type",
        "patient_status",
        "death_datetime",
    ),
    "admission_record": (
        "document_id",
        "document_title",
        "record_time",
        "admission_datetime",
        "admission_time",
        "chief_complaint",
        "history_of_present_illness",
        "record_content",
    ),
    "admission_record_diagnosis": (
        "document_id",
        "diagnosis_id",
        "diagnosis_main",
        "diagnosis_no",
        "diagnosis_type",
        "diagnosis_name",
        "diagnosis_code",
        "diagnosis_datetime",
        "record_time",
        "update_time",
    ),
    "first_course_record": (
        "document_id",
        "document_title",
        *AUTHORITATIVE_DOCUMENT_TIME_FIELDS,
        "case_characteristic",
        "diagnose_based_on",
        "first_diagnosis",
        "primary_diagnosis",
        "initial_diagnosis",
        "differential_diagnosis",
        "treatment_plan",
        "record_content",
    ),
    "first_course_record_diagnosis": (
        "document_id",
        "diagnosis_id",
        "diagnosis_main",
        "diagnosis_no",
        "diagnosis_type",
        "diagnosis_name",
        "diagnosis_code",
        "diagnosis_datetime",
        "diagnosis_time",
        "diagnosis_uptime",
        "record_time",
        "update_time",
        "v2_schema",
    ),
    "rescue_record": (
        "document_id",
        "document_title",
        "record_time",
        "record_content",
    ),
    "mr_bloodtrans": (
        "document_id",
        "transfuse_variety",
        "blood_transfusion_volume",
        "blood_transfusion_unit",
        "transblood_reaction_sign",
        "transfution_datetime",
    ),
    "bloodtrans_record": (
        "document_id",
        "document_title",
        "record_content",
        "record_time",
    ),
    "blood_application": (
        "application_id",
        "apply_no",
        "patient_bloodtype_abo",
        "patient_bloodtype_rhd",
        "transfuse_variety",
        "transfuse_volume",
        "transfuse_volume_unit",
        "request_datetime",
        "physician_name",
        "blood_type",
        "blood_component",
        "blood_amount",
        "blood_unit",
        "apply_datetime",
        "apply_doctor",
        "transfusion_reason",
        "reason_for_blood",
        "hemoglobin",
        "hematocrit",
        "rbc",
        "prothrombin_time",
        "partial_thromboplastin_time",
        "fibrinogen",
        "albumin",
        "teg",
        "platelet_antibody",
        "rbc_antibody",
        "diagnosis",
        "record_content",
    ),
    "anesthesia_record": (
        "document_id",
        "document_title",
        *AUTHORITATIVE_DOCUMENT_TIME_FIELDS,
        "record_content",
    ),
    "preane_surveil_record": (
        "document_id",
        "document_title",
        "record_time",
        "condition_summary",
        "planned_anesthesia_method",
        "ASA_level",
        "record_content",
        "anesthetist_sign",
    ),
    "postane_surveil_record": (
        "document_id",
        "document_title",
        "record_time",
        "surgery_name",
        "anesthesia_method",
        "resume_descirption",
        "record_content",
        "anesthetist_sign",
    ),
    "mr_surgery": (
        "surgery_id",
        "surgery_code",
        "surgery_name",
        "surgeon",
        "surgeon_physician_code",
        "first_assistant",
        "second_assistant",
        "main_surgery_sign",
        "surgical_level",
        "surgial_incision_level",
        "surgical_incision_level",
        "anesthesia_method",
        "surgery_begin_datetime",
        "surgery_end_datetime",
        "record_content",
    ),
    "presurg_discussion": (
        "document_id",
        "document_title",
        "record_time",
        "submitter",
        "submitter_id",
        "physician_sign",
        "physician_sign_datetime",
        "record_content",
        "host_name",
        "host_summary",
        "discuss_staff",
        "v2_schema",
    ),
    "consultation_record": (
        "document_id",
        "document_title",
        *AUTHORITATIVE_DOCUMENT_TIME_FIELDS,
        "consultation_id",
        "application_id",
        "request_time",
        "request_datetime",
        "application_time",
        "application_datetime",
        "consultation_time",
        "record_content",
        "v2_schema",
    ),
    "daily_course_record": (
        "document_id",
        "document_title",
        *AUTHORITATIVE_DOCUMENT_TIME_FIELDS,
        "author_id",
        "author_name",
        "author_title",
        "author_department",
        "submitter",
        "submitter_id",
        "physician_sign",
        "physician_sign_datetime",
        "record_content",
        # 无记录时间文书的时间上限（用户口径 2026-10-20），不作权威记录时间。
        "last_modified_datetime",
    ),
    "senior_course_record": (
        "document_id",
        "document_title",
        *AUTHORITATIVE_DOCUMENT_TIME_FIELDS,
        "author_id",
        "author_name",
        "author_title",
        "author_department",
        "submitter",
        "submitter_id",
        "physician_sign",
        "physician_sign_datetime",
        "record_content",
        # 无记录时间文书的时间上限（用户口径 2026-10-20），不作权威记录时间。
        "last_modified_datetime",
    ),
    "exam_master": (
        "modality",
        "exam_id",
        "order_id",
        "exam_type",
        "exam_name",
        "exam_item_name",
        "item_name",
        "description",
        "impression",
        "recommendation",
        "abnormal_sign",
        "performed_dept",
        "request_time",
        "exam_time",
        "exam_datetime",
        "report_time",
        "report_datetime",
        "exam_result_status",
        "report_status",
        "record_content",
    ),
    "exam_item_report": (
        "modality",
        "document_id",
        "exam_id",
        "description",
        "item_code",
        "item_name",
        "exam_name",
        "exam_item_name",
        "exam_type",
        "report_time",
        "exam_result",
        "exam_impression",
        "exam_conclusion",
        "impression",
        "conclusion",
        "record_content",
    ),
    "labtest_master": (
        "test_id",
        "order_id",
        "labtest_subject",
        "lab_type",
        "test_type",
        "specimen",
        "request_datetime",
        "report_datetime",
        "labtest_result_status",
        "record_content",
    ),
    "labtest_item_report": (
        "labtest_subject",
        "document_id",
        "test_id",
        "test_no",
        "report_id",
        "item_code",
        "item_name",
        "lab_item_name",
        "lab_type",
        "test_type",
        "result",
        "abnormal_indicator",
        "report_datetime",
        "report_time",
        "record_content",
    ),
    "pathology_exam_master": (
        "pathology_exam_id",
        "pathology_id",
        "specimen_name",
        "surgery_name",
        "request_datetime",
        "record_content",
    ),
    "pathology_exam_report": (
        "pathology_exam_id",
        "pathology_id",
        "specimen_name",
        "diagnosis",
        "eye_findings",
        "microscope_findings",
        "report_datetime",
        "report_status",
        "record_content",
    ),
    "inpat_prescription": (
        "prescription_id", "order_type", "order_status", "is_deleted",
    ),
    "inpat_prescription_item": (
        "prescription_id", "prescription_item_id", "generic_name", "brand_name",
        "drug_apply_method", "dose_form", "is_deleted",
    ),
    "inpat_drug_order": (
        "order_id",
        "drug_code",
        "generic_name",
        "brand_name",
        "drug_type",
        "single_dose",
        "single_dose_unit",
        "drug_specification",
        "repeat_indicator",
        "dose_form",
        "medication_duration",
        "drug_apply_method",
        "drug_frequency",
        "start_time",
        "order_time",
        "prescribed_datetime",
        "planned_start_datetime",
        # 保留源字段含义；计划结束、审核、执行及撤销时间不互相代替。
        "planned_end_datetime",
        "reviewed_datetime",
        "carried_datetime",
        "canceled_datetime",
        # 028：医嘱停止时间（源库同步后启用；列不存在时不选取）。
        "stop_datetime",
        "order_stop_datetime",
        "stop_time",
        "end_datetime",
        "update_time",
        "order_status",
        "last_modified_datetime",
        "record_content",
    ),
    CURRENT_VISIT_EXAM_LAB_ORDER_SOURCE_KEY: (
        "order_id",
        "order_name",
        "order_status",
        "start_time",
        "order_time",
        "prescribed_datetime",
    ),
    "discharge_record": (
        "document_id",
        "document_title",
        "record_time",
        # 独立签署证据和完整二级结构化仅进入服务端材料，不提升为记录/提交时间。
        "chief_physician_sign_datetime",
        "v2_schema",
        # update_time 是增量同步时间，不作为 061 的出院记录完成/提交时间；
        # 保留读取供同一来源的其他既有规则使用。
        "update_time",
        "admission_date",
        "discharge_date",
        "discharge_time",
        "discharge_order",
        "discharge_medications",
        "treatment_course",
        "admission_condition",
        "positive_assist_exam",
        "discharge_condition",
        "discharge_sympton_condition",
        "condition_transform",
        "record_content",
    ),
    "postsurg_firstcourse_record": (
        "document_id",
        "document_title",
        *AUTHORITATIVE_DOCUMENT_TIME_FIELDS,
        "author_id",
        "author_name",
        "author_title",
        "author_department",
        "submitter",
        "submitter_id",
        "physician_sign",
        "physician_sign_datetime",
        "record_content",
    ),
    "death_record": (
        "document_id",
        "document_title",
        "visit_type",
        *AUTHORITATIVE_DOCUMENT_TIME_FIELDS,
        "death_datetime",
        "death_time",
        "admission_condition",
        "treatment_course",
        "death_reason",
        "record_content",
    ),
    "death_discussion": (
        "document_id",
        "document_title",
        *AUTHORITATIVE_DOCUMENT_TIME_FIELDS,
        "death_datetime",
        "death_time",
        "record_content",
    ),
    "summary_record": (
        "document_id", "document_title", *AUTHORITATIVE_DOCUMENT_TIME_FIELDS,
        "record_content",
    ),
    "handoff_record": (
        "document_id",
        "document_title",
        *AUTHORITATIVE_DOCUMENT_TIME_FIELDS,
        "handoff_time",
        "shift_time",
        "handoff_doctor",
        "physician_sign",
        "record_content",
    ),
    "handover_record": (
        "document_id",
        "document_title",
        *AUTHORITATIVE_DOCUMENT_TIME_FIELDS,
        "handover_time",
        "shift_time",
        "handover_doctor",
        "physician_sign",
        "record_content",
    ),
    "physician_change_event": (
        "event_id",
        "change_datetime",
        "handoff_datetime",
        "old_physician_id",
        "old_physician_name",
        "new_physician_id",
        "new_physician_name",
    ),
    "transfer_in_record": (
        "document_id",
        "document_title",
        *AUTHORITATIVE_DOCUMENT_TIME_FIELDS,
        "transferout_department",
        "transferin_department",
        "transfer_purpose",
        "transfer_date",
        "record_datetime",
        "physician_sign",
        "record_content",
        # 054/057 读取转入诊疗计划中的抗菌药及处置（1019 C10）。
        "transfer_treatment_plan",
    ),
    "transfer_out_record": (
        "document_id",
        "document_title",
        *AUTHORITATIVE_DOCUMENT_TIME_FIELDS,
        "transferout_department",
        "transferin_department",
        "transfer_purpose",
        "transfer_date",
        "record_datetime",
        "physician_sign",
        "record_content",
    ),
    "diagnosis": (
        "diagnosis_id",
        "document_id",
        "diagnosis_type",
        "diagnosis_no",
        "diagnosis_name",
        "diagnosis_code",
        "diagnosis_source",
        "diagnosis_datetime",
    ),
    # 063 的病案首页内部决策支持来源。仅投影诊断行身份、类型、序号和名称
    # 等判定所需字段，不把患者/就诊坐标列带入快照材料。
    "mr_diagnosis": (
        "diagnosis_id",
        "document_id",
        "diagnosis_main",
        "diagnosis_no",
        "diagnosis_type",
        "diagnosis_name",
        "diagnosis_code",
        "diagnosis_source",
        "diagnosis_datetime",
        "diagnosis_time",
        "diagnosis_uptime",
        "record_time",
        "update_time",
    ),
    "inpat_nondrug_order": (
        "order_id",
        "application_id",
        "order_type",
        "order_name",
        "start_time",
        "order_time",
        "prescribed_datetime",
        "planned_start_datetime",
        "planned_end_datetime",
        "reviewed_datetime",
        "carried_datetime",
        "canceled_datetime",
        "update_time",
        "order_status",
        "record_content",
    ),
    "surgery_record": (
        "document_id",
        "document_title",
        "record_time",
        "submitter",
        "submitter_id",
        "surgeon",
        "surgeon_physician_code",
        "surgeon_sign",
        "first_assistant",
        "second_assistant",
        "anesthesiologist",
        "anesthesiologist_code",
        "surgery_begin_time",
        "surgery_end_time",
        "surgery_name",
        "surgery_code",
        "surgery_process",
        "record_content",
    ),
    "surgery_inform_consent": (
        "document_id",
        "document_title",
        "record_time",
        "record_content",
        "patient_sign",
        "surgeon_sign",
        "planned_operation_name",
        "planned_operation_code",
    ),
    "consent_form": (
        "document_id",
        "document_title",
        "record_time",
        "record_content",
        "consent_type",
        "name",
        "patient_name",
        "diagnosis",
        "transfusion_reason",
        "blood_component",
        "risk_description",
        "alternative_plan",
        "patient_sign",
        "agent_sign",
        "physician_sign",
        "sign_datetime",
        "patient_sign_datetime",
        "physician_sign_datetime",
        "surgeon_sign",
        "planned_operation_name",
        "planned_operation_code",
    ),
    "diffcase_discussion_record": (
        "document_id",
        "document_title",
        *AUTHORITATIVE_DOCUMENT_TIME_FIELDS,
        "record_content",
    ),
    "crisis_value_record": (
        "document_id",
        "document_title",
        *AUTHORITATIVE_DOCUMENT_TIME_FIELDS,
        "record_datetime",
        "dept_name",
        "record_content",
    ),
    "discharge_record_diagnosis": (
        "diagnosis_id",
        "document_id",
        "diagnosis_main",
        "diagnosis_no",
        "diagnosis_type",
        "diagnosis_name",
        "diagnosis_code",
        "diagnosis_time",
    ),
    "inpat_bill_item": (
        "bill_item_id",
        "order_id",
        "item_type",
        "medical_catalog_code",
        "medical_catalog_name",
        "quantity",
        "quantity_unit",
        "billing_datetime",
        "record_content",
    ),
}

# 文书完成时间在客户 CDM 中可能落为 record_time、record_datetime、
# submit_time 或 submit_datetime。凡是原来已批准读取文书记录时间的来源，
# 一律同时批准这四个等价的权威时间列；读取时仍只选择实际存在的列。
# 这样同步后以 record_datetime 保存的时间不会在证据读取阶段再次被漏掉。
for _source_key, _source_fields in tuple(_NATIVE_SOURCE_FIELDS.items()):
    if "document_id" in _source_fields and any(
        field in _source_fields for field in AUTHORITATIVE_DOCUMENT_TIME_FIELDS
    ):
        _NATIVE_SOURCE_FIELDS[_source_key] = tuple(
            dict.fromkeys((*_source_fields, *AUTHORITATIVE_DOCUMENT_TIME_FIELDS))
        )
    if _source_key in DOCUMENT_STATUS_TABLES:
        _NATIVE_SOURCE_FIELDS[_source_key] = tuple(
            dict.fromkeys((*_NATIVE_SOURCE_FIELDS[_source_key], "document_status"))
        )

_SNAPSHOT_SOURCE_FIELDS = {
    source_key: _NATIVE_SOURCE_FIELDS[source_key]
    for source_key in (
        "inpat_prescription",
        "inpat_prescription_item",
        "inpat_registration",
        "admission_record",
        "admission_record_diagnosis",
        "first_course_record",
        "first_course_record_diagnosis",
        "rescue_record",
        "mr_bloodtrans",
        "bloodtrans_record",
        "blood_application",
        "anesthesia_record",
        "preane_surveil_record",
        "postane_surveil_record",
        "mr_surgery",
        "presurg_discussion",
        "consultation_record",
        "daily_course_record",
        "death_discussion",
        "death_record",
        "diagnosis",
        "mr_diagnosis",
        "handoff_record",
        "handover_record",
        "physician_change_event",
        "postsurg_firstcourse_record",
        "senior_course_record",
        "summary_record",
        "transfer_in_record",
        "transfer_out_record",
        "inpat_nondrug_order",
        "exam_master",
        "exam_item_report",
        "labtest_master",
        "labtest_item_report",
        "pathology_exam_master",
        "pathology_exam_report",
        "diagnosis",
        "inpat_drug_order",
        "discharge_record",
        "surgery_record",
        "surgery_inform_consent",
        "consent_form",
        "diffcase_discussion_record",
        "crisis_value_record",
        "discharge_record_diagnosis",
        "inpat_bill_item",
    )
}
_SNAPSHOT_SOURCE_FIELDS[CURRENT_VISIT_UNSTABLE_ORDER_SOURCE_KEY] = ("present",)
_SNAPSHOT_SOURCE_FIELDS[CURRENT_VISIT_SEVERITY_ORDER_SOURCE_KEY] = (
    "severity",
    "event_kind",
    "status_state",
    "prescribed_datetime",
    "row_ref",
)
_SNAPSHOT_SOURCE_FIELDS[CURRENT_VISIT_EXAM_LAB_ORDER_SOURCE_KEY] = (
    _NATIVE_SOURCE_FIELDS[CURRENT_VISIT_EXAM_LAB_ORDER_SOURCE_KEY]
)
_SNAPSHOT_SOURCE_FIELDS[CURRENT_VISIT_RESCUE_ORDER_SOURCE_KEY] = (
    "order_id",
    "status_state",
)
_SNAPSHOT_SOURCE_FIELDS[CURRENT_VISIT_DISCHARGE_HORIZON_SOURCE_KEY] = (
    "discharge_datetime",
    "row_ref",
)
_SNAPSHOT_SOURCE_FIELDS[EVALUATION_HORIZON_SOURCE_KEY] = (
    "horizon_date",
    "horizon_datetime",
    "basis",
    "record_scene",
    "row_ref",
)
_SNAPSHOT_SOURCE_FIELDS[ROUTINE_LAB_ITEM_SOURCE_KEY] = tuple(dict.fromkeys((
    *_NATIVE_SOURCE_FIELDS["labtest_item_report"], "report_status", "document_status", "document_title",
)))
_SNAPSHOT_SOURCE_FIELDS["inpat_nondrug_order"] = (
    "order_id",
    "order_name",
    "order_status",
    "order_type",
    "start_time",
    "order_time",
    "prescribed_datetime",
    "planned_start_datetime",
    "planned_end_datetime",
    "reviewed_datetime",
    "carried_datetime",
    "canceled_datetime",
    "update_time",
    "record_content",
)
_SNAPSHOT_SOURCE_FIELDS["surgery_application"] = (
    "order_id",
    "update_time",
    "surgery_code",
)
_SNAPSHOT_SOURCE_FIELDS["surgery_record"] = tuple(
    dict.fromkeys(
        (*_SNAPSHOT_SOURCE_FIELDS["surgery_record"], *SURGERY_TIME_FIELDS)
    )
)
_SNAPSHOT_SOURCE_FIELDS.update({
    "presurg_summary": (
        "document_id",
        "document_title",
        *AUTHORITATIVE_DOCUMENT_TIME_FIELDS,
        "document_status",
        "record_content",
    ),
    "surgery_safecheck_record": (
        "document_id",
        "document_title",
        *AUTHORITATIVE_DOCUMENT_TIME_FIELDS,
        "document_status",
        *SAFECHECK_FIELDS,
        "record_content",
    ),
})


class SourceEvidenceUnavailable(Exception):
    """受控来源或就诊绑定字段不可用。"""


class SourceEvidenceQueryError(Exception):
    """数据库连接或查询执行失败；不携带底层异常原文。"""


class SourceEvidenceTruncated(Exception):
    """受控来源超过读取上限，不能据截断结果作否定判断。"""


def parse_luxian_0609_rescue_end_time(value: Any) -> datetime | None:
    """只解析完整“抢救结束时间”标签值，不从任意正文猜测时间。"""

    match = _RESCUE_END_TIME_PATTERN.search(str(value or ""))
    if not match:
        return None
    normalized = (
        match.group("value")
        .strip()
        .replace("年", "-")
        .replace("月", "-")
        .replace("日", "")
    )
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M"):
        try:
            return datetime.strptime(normalized, fmt)
        except ValueError:
            continue
    return None


@dataclass(frozen=True)
class SnapshotSourceRows:
    """provider 内部读取结果；raw rows 不得进入客户或 safe summary。"""

    source_key: str
    rows: tuple[Mapping[str, Any], ...]
    truncated: bool
    limit_rows: int
    material_scope: Mapping[str, Any] | None = None

    @classmethod
    def create(
        cls,
        *,
        source_key: str,
        rows: Any,
        truncated: bool,
        limit_rows: int,
        material_scope: Mapping[str, Any] | None = None,
    ) -> SnapshotSourceRows:
        normalized_source = str(source_key or "").strip().lower()
        if normalized_source not in _SNAPSHOT_SOURCE_FIELDS:
            raise SourceEvidenceUnavailable()
        if isinstance(limit_rows, bool) or not isinstance(limit_rows, int) or limit_rows < 1:
            raise ValueError("limit_rows must be a positive int")
        if not isinstance(truncated, bool):
            raise TypeError("truncated must be bool")
        raw_rows = tuple(rows)
        if len(raw_rows) > limit_rows:
            raise ValueError("snapshot rows exceed declared limit")
        if truncated and not raw_rows:
            raise ValueError("truncated snapshot rows cannot be empty")
        if not all(isinstance(row, Mapping) for row in raw_rows):
            raise TypeError("snapshot rows must contain mappings")
        frozen_rows = tuple(MappingProxyType(dict(row)) for row in raw_rows)
        if material_scope is None:
            from ..automatic_material_scope import source_scope
            material_scope = source_scope(normalized_source)
        return cls(
            source_key=normalized_source,
            rows=frozen_rows,
            truncated=truncated,
            limit_rows=limit_rows,
            material_scope=_freeze_scope(material_scope),
        )


def _freeze_scope(value):
    if isinstance(value, Mapping):
        return MappingProxyType({key: _freeze_scope(item) for key, item in value.items()})
    if isinstance(value, (list, tuple)):
        return tuple(_freeze_scope(item) for item in value)
    return value


def canonical_source_evidence(value: Any) -> str:
    """纯规范化：仅供稳定排序和不可逆摘要使用。"""
    return json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":"), default=str)


def digest_source_evidence(value: Any) -> str:
    """纯不可逆摘要；调用方不得把输入原值写入输出。"""
    return hashlib.sha256(canonical_source_evidence(value).encode("utf-8")).hexdigest()


def authoritative_document_time_value(row: Mapping[str, Any]) -> Any:
    """返回文书表中优先级最高的正式记录/提交时间原值。"""

    for field in AUTHORITATIVE_DOCUMENT_TIME_FIELDS:
        value = row.get(field)
        if value is None or (isinstance(value, str) and not value.strip()):
            continue
        return value
    return None


def build_luxian_0609_course_round_timeline_from_rows(
    rows_by_source: Mapping[str, tuple[Mapping[str, Any], ...]],
) -> dict[str, list[dict[str, Any]]]:
    """把共享材料转换为005/006既有安全时间线，不读取数据库。"""

    result: dict[str, list[dict[str, Any]]] = {}
    for source_key in ("daily_course_record", "senior_course_record"):
        rows = rows_by_source.get(source_key)
        if rows is None:
            raise SourceEvidenceUnavailable()
        safe_rows: list[dict[str, Any]] = []
        for row in rows:
            title = str(row.get("document_title") or "").strip()
            record_time = authoritative_document_time_value(row)
            document_id = row.get("document_id") or row.get("id")
            safe_rows.append(
                {
                    "document_id": digest_source_evidence(
                        (source_key, document_id, record_time, title)
                    ),
                    "title": title,
                    "authored_at": record_time,
                    "source_table": source_key,
                }
            )
        result[source_key] = safe_rows
    return result


@case_material.material_query
def read_luxian_0609_course_round_timeline(
    *,
    institute_id: str,
    patient_id: str,
    visit_id: str,
    source_schema: str | None,
) -> dict[str, list[dict[str, Any]]]:
    """读取005/006所需的权威标题与时间；不读取或返回病程正文。"""

    coordinates = (institute_id, patient_id, visit_id)
    if not all(isinstance(value, str) and value.strip() for value in coordinates):
        raise SourceEvidenceUnavailable()
    trusted_schema = _case_source_schema(institute_id=institute_id, patient_id=patient_id,
        visit_id=visit_id, source_schema=source_schema)
    engine = bundle_assembly._source_engine(trusted_schema)
    if engine is None:
        raise SourceEvidenceUnavailable()

    raw_rows_by_source: dict[str, tuple[Mapping[str, Any], ...]] = {}
    for source_key in ("daily_course_record", "senior_course_record"):
        from .. import daily_material_projection as daily, primary_material_projection as primary
        projected = primary.rows(coordinates, source_key)
        if projected is None:
            projected = daily.rows(coordinates) if source_key == "daily_course_record" else None
        if projected is not None:
            if len(projected) > _source_limit(source_key):
                raise SourceEvidenceTruncated()
            raw_rows_by_source[source_key] = tuple(projected)
            continue
        columns = set(bundle_assembly._get_table_columns(trusted_schema, source_key))
        required = {
            "institute_id",
            "patient_id",
            "visit_id",
            "document_title",
        }
        available_time_fields = tuple(
            field for field in AUTHORITATIVE_DOCUMENT_TIME_FIELDS if field in columns
        )
        if not required.issubset(columns) or not available_time_fields:
            raise SourceEvidenceUnavailable()
        document_id_field = next(
            (field for field in ("document_id", "id") if field in columns),
            None,
        )
        selected = ["document_title", *available_time_fields]
        if document_id_field:
            selected.append(document_id_field)
        selected, document_status_column = _with_document_status_projection(
            table=source_key,
            columns=columns,
            selected=selected,
        )
        select_sql = _select_sql_with_document_status(selected, document_status_column)
        order_fields = list(available_time_fields)
        if document_id_field:
            order_fields.append(document_id_field)
        order_sql = ", ".join(
            f"{bundle_assembly._quote_ident(field)} ASC NULLS LAST"
            for field in order_fields
        )
        limit = _source_limit(source_key)
        document_filter, document_params = _material_document_filter(
            schema=trusted_schema, table=source_key, columns=columns,
            institute_id=institute_id, patient_id=patient_id, visit_id=visit_id,
        )
        sql = (
            f"SELECT {select_sql} "
            f"FROM {bundle_assembly._qualified_table(trusted_schema, source_key)} "
            f"WHERE {bundle_assembly._quote_ident('institute_id')} = :institute_id "
            f"AND {bundle_assembly._quote_ident('patient_id')} = :patient_id "
            f"AND {bundle_assembly._quote_ident('visit_id')} = :visit_id "
            f"{document_filter} ORDER BY {order_sql} LIMIT :limit_rows"
        )
        with case_material.source_connection(engine) as connection:
            rows = connection.execute(
                bundle_assembly.text(sql),
                {
                    "institute_id": institute_id,
                    "patient_id": patient_id,
                    "visit_id": visit_id,
                    **document_params,
                    "limit_rows": limit + 1,
                },
            ).mappings().all()
        if len(rows) > limit:
            raise SourceEvidenceTruncated()
        raw_rows_by_source[source_key] = tuple(dict(row) for row in rows)
    return build_luxian_0609_course_round_timeline_from_rows(raw_rows_by_source)


def parse_strict_performed_time(value: Any) -> datetime | None:
    """仅接受整值、带已批准显式时区且可归一为北京时间的已实施手术时间。

    `surgery_record` 的时间列是 text，客户 timestamptz 列经本机导入后同一列
    内并存 `+08` 与 `+00` 两种写法；文本带 `+00` 与 datetime 带 UTC 表示的
    是同一精确时刻，必须得到同一结果，否则真实已实施手术会被降为「未实施」，
    使 029/030/032 等规则误判为不适用。因此两条分支都先还原绝对时刻，再折算
    为医院本地（Asia/Shanghai）墙钟时间。
    未带时区、形状不完整或未经批准的偏移（如 `+09`）仍被拒绝，不作为
    「已实施」证据。
    """
    if isinstance(value, datetime):
        if value.tzinfo is None or value.utcoffset() is None:
            return None
        return value.astimezone(_HOSPITAL_TIMEZONE).replace(tzinfo=None)
    if not isinstance(value, str):
        return None
    matched = _PERFORMED_TIME_TEXT_PATTERN.fullmatch(value.strip())
    if matched is None:
        return None
    offset = _PERFORMED_TIME_OFFSETS.get(matched.group("offset"))
    if offset is None:
        return None
    try:
        naive = datetime.strptime(matched.group("naive"), "%Y-%m-%d %H:%M:%S")
    except ValueError:
        return None
    return naive.replace(tzinfo=offset).astimezone(_HOSPITAL_TIMEZONE).replace(tzinfo=None)


def has_strict_performed_time(row: Mapping[str, Any]) -> bool:
    """纯事实判定：任一批准字段具有整值已实施时间即可。"""
    return any(parse_strict_performed_time(row.get(field)) is not None for field in SURGERY_TIME_FIELDS)


def trusted_performed_surgery_times(
    *, source_key: str, row: Mapping[str, Any]
) -> tuple[datetime, ...]:
    """返回批准来源中的本次已实施手术时间；描述性字段不能触发。"""
    if source_key == "surgery_record":
        return tuple(
            parsed
            for field in SURGERY_TIME_FIELDS
            if (parsed := parse_strict_performed_time(row.get(field))) is not None
        )
    if source_key == "mr_surgery":
        return tuple(
            value
            for field in ("surgery_begin_datetime", "surgery_end_datetime")
            if isinstance((value := row.get(field)), datetime) and value.tzinfo is None
        )
    return ()


def has_trusted_performed_surgery(*, source_key: str, row: Mapping[str, Any]) -> bool:
    """仅严格手术记录时间或 mr_surgery typed 时间可证明已实施。"""
    return bool(trusted_performed_surgery_times(source_key=source_key, row=row))


def has_qualified_traditional_surgery_row(row: Mapping[str, Any]) -> bool:
    """院内目录优先确认手术；未命中目录时才保留原结构化等级回退。"""

    catalog_state = catalog_surgery_state(row)
    if catalog_state is not None:
        return catalog_state

    known_levels = {
        "一级",
        "二级",
        "三级",
        "四级",
        "1",
        "2",
        "3",
        "4",
        "Ⅰ",
        "Ⅱ",
        "Ⅲ",
        "Ⅳ",
        "I",
        "II",
        "III",
        "IV",
    }
    known_incisions = {"I", "II", "III", "IV", "Ⅰ", "Ⅱ", "Ⅲ", "Ⅳ"}
    surgical_level = str(row.get("surgical_level") or "").strip().upper()
    incision_level = str(
        row.get("surgical_incision_level")
        or row.get("surgial_incision_level")
        or ""
    ).strip().upper()
    return surgical_level in known_levels or incision_level in known_incisions


# LX0609 专用读取上限，只覆盖病历包共用值，不改其他引擎。
# 2026-10-17 1016 样本池：药品医嘱最多 827 行、非药品医嘱最多 2156 行，超出共用上限
# 700/1500（0426 冻结 258 例审计所定），约 30 项被判资料超读取范围。
# 读满上限仍标记为可能截断；医嘱送入模型的路径各有去重、分批或候选上限。
_LX0609_SOURCE_LIMIT_OVERRIDES: dict[str, int] = {
    "inpat_drug_order": 3000,
    "inpat_nondrug_order": 5000,
}


def _source_limit(source_key: str) -> int:
    if source_key in _LX0609_SOURCE_LIMIT_OVERRIDES:
        return _LX0609_SOURCE_LIMIT_OVERRIDES[source_key]
    return int(getattr(bundle_assembly, "_DOMAIN_FETCH_LIMITS", {}).get(source_key, 50))


def luxian_0609_native_source_row_limit(source_key: str) -> int:
    """返回批准来源的有界读取上限；达到上限时调用方必须视为可能截断。"""

    if str(source_key or "").strip() not in _NATIVE_SOURCE_FIELDS:
        raise SourceEvidenceUnavailable()
    return _source_limit(source_key)


@case_material.material_query
def has_luxian_0609_current_visit_unstable_order(
    *, institute_id: str, patient_id: str, visit_id: str, source_schema: str | None
) -> bool:
    """判断本次就诊是否下达过有效（含生效后停止）的病危或病重医嘱，不返回医嘱原文。"""

    trusted_schema = _case_source_schema(institute_id=institute_id, patient_id=patient_id,
        visit_id=visit_id, source_schema=source_schema)
    engine = bundle_assembly._source_engine(trusted_schema)
    if engine is None:
        raise SourceEvidenceUnavailable()
    source_key = "inpat_nondrug_order"
    try:
        columns = set(bundle_assembly._get_table_columns(trusted_schema, source_key))
    except Exception:
        raise SourceEvidenceQueryError() from None
    required = {"institute_id", "patient_id", "visit_id", "order_name"}
    if not required.issubset(columns):
        raise SourceEvidenceUnavailable()

    order_name_col = bundle_assembly._quote_ident("order_name")
    base_where = (
        f"WHERE {bundle_assembly._quote_ident('institute_id')} = :institute_id "
        f"AND {bundle_assembly._quote_ident('patient_id')} = :patient_id "
        f"AND {bundle_assembly._quote_ident('visit_id')} = :visit_id "
        f"AND ({order_name_col} LIKE :critical_name "
        f"OR {order_name_col} LIKE :serious_name) "
        f"AND {order_name_col} NOT LIKE :cancelled_name "
        f"AND {order_name_col} NOT LIKE :revoked_name "
        f"AND {order_name_col} NOT LIKE :voided_name"
    )
    base_params = {
        "institute_id": institute_id,
        "patient_id": patient_id,
        "visit_id": visit_id,
        "critical_name": "%病危%",
        "serious_name": "%病重%",
        "cancelled_name": "%取消%",
        "revoked_name": "%撤销%",
        "voided_name": "%作废%",
    }
    if "order_status" not in columns:
        sql = (
            f"SELECT 1 FROM {bundle_assembly._qualified_table(trusted_schema, source_key)} "
            f"{base_where} LIMIT 1"
        )
        try:
            with case_material.source_connection(engine) as connection:
                row = connection.execute(
                    bundle_assembly.text(sql),
                    base_params,
                ).first()
        except Exception:
            raise SourceEvidenceQueryError() from None
        return row is not None

    order_status_col = bundle_assembly._quote_ident("order_status")
    excluded_placeholders = ", ".join(
        f":{key}" for key in _EXCLUDED_SEVERITY_ORDER_STATUS_PARAMS
    )
    limit_rows = 50
    sql = (
        f"SELECT DISTINCT {order_name_col}, {order_status_col} "
        f"FROM {bundle_assembly._qualified_table(trusted_schema, source_key)} "
        f"{base_where} "
        f"AND ({order_status_col} IS NULL "
        f"OR TRIM({order_status_col}) NOT IN ({excluded_placeholders})) "
        f"LIMIT :limit_rows"
    )
    try:
        with case_material.source_connection(engine) as connection:
            raw_rows = connection.execute(
                bundle_assembly.text(sql),
                {
                    **base_params,
                    **_EXCLUDED_SEVERITY_ORDER_STATUS_PARAMS,
                    "limit_rows": limit_rows + 1,
                },
            ).mappings().all()
    except Exception:
        raise SourceEvidenceQueryError() from None

    # 区分"从未生效（取消/撤销/作废/未执行）"与"生效后停止（停止/已停止）"：
    # 生效后停止说明就诊期间曾达病危/病重，02-01-03 仍不适用；未审计/空状态保守降级为不可证明。
    has_unresolved = False
    for row in raw_rows:
        order_name = str(row.get("order_name") or "")
        if not ("病危" in order_name or "病重" in order_name):
            continue
        if any(marker in order_name for marker in _SEVERITY_ORDER_CANCELLED_NAME_MARKERS):
            continue
        order_status = row.get("order_status")
        normalized_status = (
            order_status.strip() if isinstance(order_status, str) else ""
        )
        if normalized_status in _EFFECTIVE_SEVERITY_ORDER_STATUSES:
            return True
        if normalized_status in _EXCLUDED_SEVERITY_ORDER_STATUSES:
            continue
        has_unresolved = True
    if has_unresolved or len(raw_rows) > limit_rows:
        raise SourceEvidenceUnavailable()
    return False


@case_material.material_query
def read_luxian_0609_severity_order_rows(
    *,
    institute_id: str,
    patient_id: str,
    visit_id: str,
    source_schema: str | None,
) -> SnapshotSourceRows:
    """读取病重/病危医嘱类别及生命周期时间，不返回医嘱原文。"""

    trusted_schema = _case_source_schema(institute_id=institute_id, patient_id=patient_id,
        visit_id=visit_id, source_schema=source_schema)
    engine = bundle_assembly._source_engine(trusted_schema)
    if engine is None:
        raise SourceEvidenceUnavailable()
    source_key = "inpat_nondrug_order"
    try:
        columns = set(bundle_assembly._get_table_columns(trusted_schema, source_key))
    except Exception:
        raise SourceEvidenceQueryError() from None
    required = {
        "institute_id",
        "patient_id",
        "visit_id",
        "order_name",
        "order_status",
    }
    if not required.issubset(columns):
        raise SourceEvidenceUnavailable()
    selected = ["order_name"]
    selected.extend(
        field
        for field in (
            "order_id",
            "prescribed_datetime",
            "planned_start_datetime",
            "planned_end_datetime",
            "order_status",
        )
        if field in columns
    )
    select_sql = ", ".join(bundle_assembly._quote_ident(field) for field in selected)
    order_columns = [
        field
        for field in (
            "planned_start_datetime",
            "prescribed_datetime",
            "order_id",
            "order_name",
        )
        if field in columns
    ]
    order_sql = ", ".join(
        f"{bundle_assembly._quote_ident(field)} ASC NULLS LAST"
        for field in order_columns
    )
    limit_rows = 50
    order_name_col = bundle_assembly._quote_ident("order_name")
    order_status_col = bundle_assembly._quote_ident("order_status")
    excluded_placeholders = ", ".join(
        f":{key}" for key in _EXCLUDED_SEVERITY_ORDER_STATUS_PARAMS
    )
    sql = (
        f"SELECT {select_sql} FROM {bundle_assembly._qualified_table(trusted_schema, source_key)} "
        f"WHERE {bundle_assembly._quote_ident('institute_id')} = :institute_id "
        f"AND {bundle_assembly._quote_ident('patient_id')} = :patient_id "
        f"AND {bundle_assembly._quote_ident('visit_id')} = :visit_id "
        f"AND ({order_name_col} LIKE :critical_name "
        f"OR {order_name_col} LIKE :serious_name) "
        f"AND {order_name_col} NOT LIKE :cancelled_name "
        f"AND {order_name_col} NOT LIKE :revoked_name "
        f"AND {order_name_col} NOT LIKE :voided_name "
        f"AND ({order_status_col} IS NULL "
        f"OR TRIM({order_status_col}) NOT IN ({excluded_placeholders})) "
        f"ORDER BY {order_sql} LIMIT :limit_rows"
    )
    try:
        with case_material.source_connection(engine) as connection:
            raw_rows = connection.execute(
                bundle_assembly.text(sql),
                {
                    "institute_id": institute_id,
                    "patient_id": patient_id,
                    "visit_id": visit_id,
                    "critical_name": "%病危%",
                    "serious_name": "%病重%",
                    "cancelled_name": "%取消%",
                    "revoked_name": "%撤销%",
                    "voided_name": "%作废%",
                    **_EXCLUDED_SEVERITY_ORDER_STATUS_PARAMS,
                    "limit_rows": limit_rows + 1,
                },
            ).mappings().all()
    except Exception:
        raise SourceEvidenceQueryError() from None
    safe_rows = []
    for row in raw_rows:
        order_name = str(row.get("order_name") or "")
        if any(marker in order_name for marker in _SEVERITY_ORDER_CANCELLED_NAME_MARKERS):
            continue
        has_critical = "病危" in order_name
        has_serious = "病重" in order_name
        severity = (
            "critical"
            if has_critical and not has_serious
            else "serious" if has_serious and not has_critical else "unknown"
        )
        # 停止/已停止状态表示该次医嘱曾有效，结束时间由同一行 planned_end_datetime
        # 提供。初始取消、撤销、作废、未执行行不产生触发；空值及未审计状态则保守
        # 保留为 unresolved，交由 008/009 映射为 data_gap。
        order_status = row.get("order_status")
        normalized_status = (
            order_status.strip() if isinstance(order_status, str) else ""
        )
        if normalized_status in _EFFECTIVE_SEVERITY_ORDER_STATUSES:
            status_state = "effective"
        elif normalized_status in _EXCLUDED_SEVERITY_ORDER_STATUSES:
            status_state = "excluded"
        else:
            status_state = "unresolved"
        lifecycle_state = (
            "stopped"
            if normalized_status in _STOPPED_SEVERITY_ORDER_STATUSES
            else "active" if status_state == "effective" else ""
        )
        event_kind = (
            "end"
            if any(marker in order_name for marker in _SEVERITY_ORDER_TERMINAL_MARKERS)
            else "start"
        )
        safe_rows.append(
            {
                "severity": severity,
                "event_kind": event_kind,
                "status_state": status_state,
                "lifecycle_state": lifecycle_state,
                "prescribed_datetime": row.get("prescribed_datetime"),
                "planned_start_datetime": row.get("planned_start_datetime"),
                "planned_end_datetime": row.get("planned_end_datetime"),
                "row_ref": digest_source_evidence(
                    (
                        CURRENT_VISIT_SEVERITY_ORDER_SOURCE_KEY,
                        row.get("order_id"),
                        severity,
                        event_kind,
                        status_state,
                        lifecycle_state,
                        order_status,
                        row.get("prescribed_datetime"),
                        row.get("planned_start_datetime"),
                        row.get("planned_end_datetime"),
                    )
                ),
            }
        )
    return SnapshotSourceRows.create(
        source_key=CURRENT_VISIT_SEVERITY_ORDER_SOURCE_KEY,
        rows=safe_rows[:limit_rows],
        truncated=len(safe_rows) > limit_rows,
        limit_rows=limit_rows,
    )


@case_material.material_query
def read_luxian_0609_exam_lab_order_rows(
    *,
    institute_id: str,
    patient_id: str,
    visit_id: str,
    source_schema: str | None,
) -> SnapshotSourceRows:
    """只读取当前住院 CT/MRI/培养/药敏医嘱，避免被全量医嘱截断。"""

    trusted_schema = _case_source_schema(institute_id=institute_id, patient_id=patient_id,
        visit_id=visit_id, source_schema=source_schema)
    engine = bundle_assembly._source_engine(trusted_schema)
    if engine is None:
        raise SourceEvidenceUnavailable()
    table = "inpat_nondrug_order"
    try:
        columns = set(bundle_assembly._get_table_columns(trusted_schema, table))
    except Exception:
        raise SourceEvidenceQueryError() from None
    if not {"institute_id", "patient_id", "visit_id", "order_name"}.issubset(columns):
        raise SourceEvidenceUnavailable()
    selected = [
        field
        for field in (
            "order_id", "order_name", "order_status",
            "start_time", "order_time", "prescribed_datetime",
        )
        if field in columns
    ]
    select_sql = ", ".join(bundle_assembly._quote_ident(field) for field in selected)
    order_sql = ", ".join(
        f"{bundle_assembly._quote_ident(field)} ASC NULLS LAST"
        for field in ("prescribed_datetime", "order_time", "order_id", "order_name")
        if field in columns
    )
    # 长住院 CT/MRI/培养相关医嘱可超过 50 条（1016 C02 为 51 条），截断后整个来源被判不完整；
    # 仍保留多读一行的真实截断标记。
    limit_rows = 300
    order_name = bundle_assembly._quote_ident("order_name")
    sql = (
        f"SELECT {select_sql} FROM {bundle_assembly._qualified_table(trusted_schema, table)} "
        f"WHERE {bundle_assembly._quote_ident('institute_id')} = :institute_id "
        f"AND {bundle_assembly._quote_ident('patient_id')} = :patient_id "
        f"AND {bundle_assembly._quote_ident('visit_id')} = :visit_id "
        f"AND (UPPER({order_name}) LIKE :ct_name OR UPPER({order_name}) LIKE :mri_name "
        f"OR {order_name} LIKE :magnetic_name OR {order_name} LIKE :nmr_name "
        f"OR {order_name} LIKE :culture_name OR {order_name} LIKE :ast_name) "
        f"ORDER BY {order_sql} LIMIT :limit_rows"
    )
    try:
        with case_material.source_connection(engine) as connection:
            rows = connection.execute(
                bundle_assembly.text(sql),
                {
                    "institute_id": institute_id,
                    "patient_id": patient_id,
                    "visit_id": visit_id,
                    "ct_name": "%CT%",
                    "mri_name": "%MRI%",
                    "magnetic_name": "%磁共振%",
                    "nmr_name": "%核磁%",
                    "culture_name": "%培养%",
                    "ast_name": "%药敏%",
                    "limit_rows": limit_rows + 1,
                },
            ).mappings().all()
    except Exception:
        raise SourceEvidenceQueryError() from None
    return SnapshotSourceRows.create(
        source_key=CURRENT_VISIT_EXAM_LAB_ORDER_SOURCE_KEY,
        rows=rows[:limit_rows],
        truncated=len(rows) > limit_rows,
        limit_rows=limit_rows,
    )


@case_material.material_query
def read_luxian_0609_rescue_order_rows(
    *,
    institute_id: str,
    patient_id: str,
    visit_id: str,
    source_schema: str | None,
) -> SnapshotSourceRows:
    """数据库侧只读取明确抢救医嘱及最小状态，不受普通医嘱数量影响。"""

    trusted_schema = _case_source_schema(institute_id=institute_id, patient_id=patient_id,
        visit_id=visit_id, source_schema=source_schema)
    engine = bundle_assembly._source_engine(trusted_schema)
    if engine is None:
        raise SourceEvidenceUnavailable()
    table = "inpat_nondrug_order"
    try:
        columns = set(bundle_assembly._get_table_columns(trusted_schema, table))
    except Exception:
        raise SourceEvidenceQueryError() from None
    required = {
        "institute_id",
        "patient_id",
        "visit_id",
        "order_name",
        "order_status",
    }
    if not required.issubset(columns):
        raise SourceEvidenceUnavailable()
    selected = [
        field for field in ("order_id", "order_name", "order_status") if field in columns
    ]
    select_sql = ", ".join(bundle_assembly._quote_ident(field) for field in selected)
    order_sql = ", ".join(
        f"{bundle_assembly._quote_ident(field)} ASC NULLS LAST"
        for field in ("order_id", "order_name", "order_status")
        if field in columns
    )
    limit_rows = 50
    order_name = bundle_assembly._quote_ident("order_name")
    order_status = bundle_assembly._quote_ident("order_status")
    sql = (
        f"SELECT {select_sql} FROM {bundle_assembly._qualified_table(trusted_schema, table)} "
        f"WHERE {bundle_assembly._quote_ident('institute_id')} = :institute_id "
        f"AND {bundle_assembly._quote_ident('patient_id')} = :patient_id "
        f"AND {bundle_assembly._quote_ident('visit_id')} = :visit_id "
        f"AND {order_name} IN (:small_rescue, :medium_rescue, "
        f":small_rescue_free_ascii, :small_rescue_free_full) "
        f"AND ({order_status} IS NULL OR {order_status} NOT IN "
        f"(:cancelled_status, :revoked_status, :voided_status)) "
        f"ORDER BY {order_sql} LIMIT :limit_rows"
    )
    try:
        with case_material.source_connection(engine) as connection:
            raw_rows = connection.execute(
                bundle_assembly.text(sql),
                {
                    "institute_id": institute_id,
                    "patient_id": patient_id,
                    "visit_id": visit_id,
                    "small_rescue": "小抢救",
                    "medium_rescue": "中抢救",
                    "small_rescue_free_ascii": "小抢救(无费用)",
                    "small_rescue_free_full": "小抢救（无费用）",
                    "cancelled_status": "取消",
                    "revoked_status": "撤销",
                    "voided_status": "作废",
                    "limit_rows": limit_rows + 1,
                },
            ).mappings().all()
    except Exception:
        raise SourceEvidenceQueryError() from None
    safe_rows: list[dict[str, Any]] = []
    for row in raw_rows:
        status = str(row.get("order_status") or "").strip()
        if status in {"取消", "撤销", "作废"}:
            continue
        status_state = (
            "effective"
            if status in {"新开", "执行中", "停止", "已停止"}
            else "unresolved"
        )
        safe_rows.append(
            {
                "order_id": row.get("order_id"),
                "status_state": status_state,
            }
        )
    return SnapshotSourceRows.create(
        source_key=CURRENT_VISIT_RESCUE_ORDER_SOURCE_KEY,
        rows=safe_rows[:limit_rows],
        truncated=len(safe_rows) > limit_rows,
        limit_rows=limit_rows,
    )


@case_material.material_query
def read_luxian_0609_discharge_horizon_rows(
    *,
    institute_id: str,
    patient_id: str,
    visit_id: str,
    source_schema: str | None,
) -> SnapshotSourceRows:
    """登记 > 有效出院文书；不以首页作为取材前提或时间回退。"""

    trusted_schema = _case_source_schema(institute_id=institute_id, patient_id=patient_id,
        visit_id=visit_id, source_schema=source_schema)
    engine = bundle_assembly._source_engine(trusted_schema)
    if engine is None:
        raise SourceEvidenceUnavailable()
    required = {
        "institute_id",
        "patient_id",
        "visit_id",
    }
    raw_rows: list[Mapping[str, Any]] = []
    selected_table = ""
    readable_source_found = False
    for table_name in ("inpat_registration", "discharge_record", "death_record"):
        try:
            columns = set(
                bundle_assembly._get_table_columns(trusted_schema, table_name)
            )
        except Exception:
            raise SourceEvidenceQueryError() from None
        if not required.issubset(columns):
            continue
        if table_name == "discharge_record":
            time_fields = [field for field in ("discharge_date", "discharge_time") if field in columns]
        elif table_name == "death_record":
            time_fields = ["death_datetime"] if "death_datetime" in columns else []
        else:
            time_fields = ["discharge_datetime"] if "discharge_datetime" in columns else []
        if not time_fields:
            continue
        readable_source_found = True
        document_filter, document_params = (
            _material_document_filter(schema=trusted_schema, table=table_name, columns=columns,
                institute_id=institute_id, patient_id=patient_id, visit_id=visit_id)
            if table_name in {"discharge_record", "death_record"} else ("", {})
        )
        sql = (
            f"SELECT {', '.join(bundle_assembly._quote_ident(field) for field in time_fields)} "
            f"FROM {bundle_assembly._qualified_table(trusted_schema, table_name)} "
            f"WHERE {bundle_assembly._quote_ident('institute_id')} = :institute_id "
            f"AND {bundle_assembly._quote_ident('patient_id')} = :patient_id "
            f"AND {bundle_assembly._quote_ident('visit_id')} = :visit_id "
            "AND (" + " OR ".join(
                f"NULLIF(TRIM(CAST({bundle_assembly._quote_ident(field)} AS TEXT)), '') IS NOT NULL"
                for field in time_fields
            ) + f") {document_filter}LIMIT :limit_rows"
        )
        try:
            with case_material.source_connection(engine) as connection:
                candidate_rows = connection.execute(
                    bundle_assembly.text(sql),
                    {
                        "institute_id": institute_id,
                        "patient_id": patient_id,
                        "visit_id": visit_id,
                        **document_params,
                        "limit_rows": 2,
                    },
                ).mappings().all()
        except Exception:
            # 权限/连接失败不等于空来源，不能用低优先级时间掩盖。
            raise SourceEvidenceQueryError() from None
        # 登记缺失时间时继续读取实际出院文书，首页不参与判断。
        candidate_rows = [
            row for row in candidate_rows
            if any(str(row.get(field) or "").strip() for field in time_fields)
        ]
        if candidate_rows:
            raw_rows = list(candidate_rows)
            selected_table = table_name
            break
    if not readable_source_found:
        raise SourceEvidenceUnavailable()
    safe_rows = []
    for row in raw_rows[:1]:
        selected = select_discharge_time(
            registration=row.get("discharge_datetime") if selected_table == "inpat_registration" else None,
            document_date=row.get("discharge_date"), document_time=row.get("discharge_time"),
            death_time=row.get("death_datetime") if selected_table == "death_record" else None,
        )
        value = (selected.value.isoformat(sep=" ")
                 if isinstance(selected.value, datetime) else selected.value)
        safe_rows.append({
            "discharge_datetime": value,
            "time_source": selected.source,
            **({"time_conflict": True} if selected.conflict else {}),
            "row_ref": digest_source_evidence(
                (
                    CURRENT_VISIT_DISCHARGE_HORIZON_SOURCE_KEY,
                    selected_table,
                    row,
                )
            ),
        })
    return SnapshotSourceRows.create(
        source_key=CURRENT_VISIT_DISCHARGE_HORIZON_SOURCE_KEY,
        rows=safe_rows,
        truncated=len(raw_rows) > 1,
        limit_rows=1,
    )


@case_material.material_query
def read_luxian_0609_runtime_source_rows(
    *, source_key: str, institute_id: str, patient_id: str, visit_id: str, source_schema: str | None
) -> list[dict[str, Any]]:
    """显式、有界、参数化的读侧查询；调用时才访问数据库。"""
    from .. import primary_material_projection as primary
    approved_fields = SURGERY_TIME_FIELDS if source_key == "surgery_record" else ("record_content", *AUTHORITATIVE_DOCUMENT_TIME_FIELDS)
    projected = primary.rule_rows((institute_id, patient_id, visit_id), source_key, approved_fields)
    if projected is not None:
        if len(projected) > _source_limit(source_key):
            raise SourceEvidenceTruncated()
        return projected
    trusted_schema = _case_source_schema(institute_id=institute_id, patient_id=patient_id,
        visit_id=visit_id, source_schema=source_schema)
    engine = bundle_assembly._source_engine(trusted_schema)
    if engine is None:
        raise SourceEvidenceUnavailable()
    columns = set(bundle_assembly._get_table_columns(trusted_schema, source_key))
    required = {"institute_id", "patient_id", "visit_id"}
    if not required.issubset(columns):
        raise SourceEvidenceUnavailable()

    selected = [field for field in SURGERY_TIME_FIELDS if source_key == "surgery_record" and field in columns]
    if source_key == "mr_surgery":
        if "surgery_begin_datetime" not in columns:
            raise SourceEvidenceUnavailable()
        selected.append("surgery_begin_datetime")
    if source_key == "presurg_summary":
        selected.extend(field for field in ("record_content", *AUTHORITATIVE_DOCUMENT_TIME_FIELDS) if field in columns)
    if source_key == "surgery_safecheck_record":
        selected.extend(field for field in ("record_content", *SAFECHECK_FIELDS) if field in columns)
    selected, document_status_column = _with_document_status_projection(
        table=source_key,
        columns=columns,
        selected=selected,
    )
    select_sql = (
        _select_sql_with_document_status(selected, document_status_column)
        or "1 AS row_marker"
    )

    order_candidates = (*getattr(bundle_assembly, "_ORDER_COLUMNS_PRIORITY", ()), "document_id", "id", *SURGERY_TIME_FIELDS)
    order_columns = [field for field in order_candidates if field in columns]
    order_sql = ""
    if order_columns:
        order_sql = " ORDER BY " + ", ".join(
            f"{bundle_assembly._quote_ident(field)} ASC NULLS LAST" for field in order_columns
        )
    document_filter, document_params = _material_document_filter(
        schema=trusted_schema, table=source_key, columns=columns,
        institute_id=institute_id, patient_id=patient_id, visit_id=visit_id,
    )
    sql = (
        f"SELECT {select_sql} FROM {bundle_assembly._qualified_table(trusted_schema, source_key)} "
        f"WHERE {bundle_assembly._quote_ident('institute_id')} = :institute_id "
        f"AND {bundle_assembly._quote_ident('patient_id')} = :patient_id "
        f"AND {bundle_assembly._quote_ident('visit_id')} = :visit_id "
        f"{document_filter}{order_sql} LIMIT :limit_rows"
    )
    limit = _source_limit(source_key)
    with case_material.source_connection(engine) as connection:
        rows = connection.execute(
            bundle_assembly.text(sql),
            {
                "institute_id": institute_id,
                "patient_id": patient_id,
                "visit_id": visit_id,
                **document_params,
                "limit_rows": limit + 1,
            },
        ).mappings().all()
    if len(rows) > limit:
        raise SourceEvidenceTruncated()
    return [dict(row) for row in rows]


@case_material.material_query
def read_luxian_0609_native_source_rows(
    *, source_key: str, institute_id: str, patient_id: str, visit_id: str, source_schema: str | None
) -> list[dict[str, Any]]:
    """读取原生质控批准字段；字段白名单固定，调用方不能扩大正文范围。"""
    from .. import daily_material_projection as daily, primary_material_projection as primary
    projected = primary.rule_rows((institute_id, patient_id, visit_id), source_key, _NATIVE_SOURCE_FIELDS.get(source_key, ()))
    if projected is None:
        projected = daily.rule_rows((institute_id, patient_id, visit_id), _NATIVE_SOURCE_FIELDS[source_key]) if source_key == "daily_course_record" else None
    if projected is not None:
        if len(projected) > _source_limit(source_key):
            raise SourceEvidenceTruncated()
        return projected
    approved_fields = _NATIVE_SOURCE_FIELDS.get(str(source_key or "").strip())
    if approved_fields is None:
        raise SourceEvidenceUnavailable()
    trusted_schema = _case_source_schema(institute_id=institute_id, patient_id=patient_id,
        visit_id=visit_id, source_schema=source_schema)
    engine = bundle_assembly._source_engine(trusted_schema)
    if engine is None:
        raise SourceEvidenceUnavailable()
    columns = set(bundle_assembly._get_table_columns(trusted_schema, source_key))
    required = {"institute_id", "patient_id", "visit_id"}
    if not required.issubset(columns):
        raise SourceEvidenceUnavailable()

    selected = [field for field in approved_fields if field in columns]
    selected, document_status_column = _with_document_status_projection(
        table=source_key,
        columns=columns,
        selected=selected,
    )
    if source_key == "mr_surgery" and not {"surgical_level", "surgery_begin_datetime"}.issubset(selected):
        raise SourceEvidenceUnavailable()
    if source_key == "mr_bloodtrans" and "transfution_datetime" not in selected:
        raise SourceEvidenceUnavailable()
    if source_key == "bloodtrans_record" and "record_content" not in selected:
        raise SourceEvidenceUnavailable()
    select_sql = (
        _select_sql_with_document_status(selected, document_status_column)
        or "1 AS row_marker"
    )
    order_candidates = (
        *getattr(bundle_assembly, "_ORDER_COLUMNS_PRIORITY", ()),
        "document_id",
        "pathology_exam_id",
        "pathology_id",
        "diagnosis_id",
        "order_id",
        "surgery_begin_datetime",
    )
    order_columns = [field for field in order_candidates if field in columns]
    order_sql = ""
    if order_columns:
        order_sql = " ORDER BY " + ", ".join(
            f"{bundle_assembly._quote_ident(field)} ASC NULLS LAST" for field in order_columns
        )
    document_filter, document_params = _material_document_filter(
        schema=trusted_schema, table=source_key, columns=columns,
        institute_id=institute_id, patient_id=patient_id, visit_id=visit_id,
    )
    sql = (
        f"SELECT {select_sql} FROM {bundle_assembly._qualified_table(trusted_schema, source_key)} "
        f"WHERE {bundle_assembly._quote_ident('institute_id')} = :institute_id "
        f"AND {bundle_assembly._quote_ident('patient_id')} = :patient_id "
        f"AND {bundle_assembly._quote_ident('visit_id')} = :visit_id "
        f"{document_filter}{order_sql} LIMIT :limit_rows"
    )
    limit = _source_limit(source_key)
    with case_material.source_connection(engine) as connection:
        rows = connection.execute(
            bundle_assembly.text(sql),
            {
                "institute_id": institute_id,
                "patient_id": patient_id,
                "visit_id": visit_id,
                **document_params,
                "limit_rows": limit + 1,
            },
        ).mappings().all()
    if len(rows) > limit:
        raise SourceEvidenceTruncated()
    return [dict(row) for row in rows]


def _normalize_snapshot_source_row(
    source_key: str,
    row: Mapping[str, Any],
) -> dict[str, Any]:
    """仅把已知的补充报告合成 ID 回退到同一事件业务 ID。

    部分同步数据会把检验报告落成 ``…-labtest_item_report-supp-NNN``，而
    Bundle/病历文书使用报告的 ``test_id``（如 ``LAB-009``）作为真实文书 ID。
    只有命中该明确合成格式且同一行存在业务 ID 时才回退；普通真实
    ``document_id`` 永不改写，避免把业务键猜成文书 ID。
    """

    normalized = dict(row)
    if source_key == "discharge_record":
        from .cache_document_source_adapter import enrich_discharge_document
        return enrich_discharge_document(row)
    if source_key != "labtest_item_report":
        return normalized
    document_id = str(normalized.get("document_id") or "").strip()
    if not document_id or "-labtest_item_report-supp-" not in document_id:
        return normalized
    fallback_id = next(
        (
            str(normalized.get(field) or "").strip()
            for field in ("test_id", "test_no", "report_id")
            if str(normalized.get(field) or "").strip()
        ),
        "",
    )
    if fallback_id:
        normalized["document_id"] = fallback_id
    return normalized


def _read_cache_diagnosis_source(
    *, source_key: str, institute_id: str, patient_id: str, visit_id: str,
    source_schema: str | None,
) -> SnapshotSourceRows:
    """从同一就诊已同步文书/诊断补读侧资料，不写诊断子表或伪造首页来源。"""
    from .cache_document_source_adapter import (
        DIAGNOSIS_PARENTS, document_diagnoses, homepage_diagnoses,
    )
    coordinates = dict(institute_id=institute_id, patient_id=patient_id,
                       visit_id=visit_id, source_schema=source_schema)
    if source_key == "mr_diagnosis":
        generic = read_luxian_0609_snapshot_source_rows(source_key="diagnosis", **coordinates)
        if generic.truncated:
            raise SourceEvidenceUnavailable()
        rows = homepage_diagnoses(generic.rows)
        if not rows:
            raise SourceEvidenceUnavailable()
    else:
        parent = read_luxian_0609_snapshot_source_rows(
            source_key=DIAGNOSIS_PARENTS[source_key][0], **coordinates,
        )
        if parent.truncated or not parent.rows:
            raise SourceEvidenceUnavailable()
        try:
            generic = read_luxian_0609_snapshot_source_rows(source_key="diagnosis", **coordinates)
        except SourceEvidenceUnavailable:
            generic = None
        if generic is not None and generic.truncated:
            raise SourceEvidenceUnavailable()
        try:
            rows = document_diagnoses(source_key, parent.rows, generic.rows if generic else ())
        except ValueError:
            raise SourceEvidenceUnavailable() from None
        if not rows:
            # 没有可识别诊断栏目，不等于临床未写诊断或完整空子表。
            raise SourceEvidenceUnavailable()
    limit = _source_limit(source_key)
    return SnapshotSourceRows.create(
        source_key=source_key, rows=rows[:limit], truncated=len(rows) > limit, limit_rows=limit,
    )


@case_material.material_query
def read_luxian_0609_snapshot_source_rows(
    *,
    source_key: str,
    institute_id: str,
    patient_id: str,
    visit_id: str,
    source_schema: str | None,
) -> SnapshotSourceRows:
    """为 EvidenceSnapshot 执行一次 limit+1 三坐标有界读取。"""

    from .. import daily_material_projection as daily, primary_material_projection as primary
    projected = primary.rule_rows((institute_id, patient_id, visit_id), source_key, _SNAPSHOT_SOURCE_FIELDS.get(source_key, ()))
    if projected is None:
        projected = daily.rule_rows((institute_id, patient_id, visit_id), _SNAPSHOT_SOURCE_FIELDS[source_key]) if source_key == "daily_course_record" else None
    if projected is not None:
        limit = _source_limit(source_key)
        return SnapshotSourceRows.create(source_key=source_key, rows=projected[:limit],
                                         truncated=len(projected) > limit, limit_rows=limit,
                                         material_scope=primary.scope(source_key) or daily.scope(source_key))
    coordinates = (institute_id, patient_id, visit_id)
    if not all(isinstance(value, str) and value.strip() for value in coordinates):
        raise SourceEvidenceUnavailable()
    normalized_source = str(source_key or "").strip().lower()
    if normalized_source == EVALUATION_HORIZON_SOURCE_KEY:
        # 该来源由 Evidence Session 根据权威出院源与显式任务日期派生，
        # 永远不能被解释成数据库物理表。
        raise SourceEvidenceUnavailable()
    if normalized_source == CURRENT_VISIT_DISCHARGE_HORIZON_SOURCE_KEY:
        return read_luxian_0609_discharge_horizon_rows(
            institute_id=institute_id,
            patient_id=patient_id,
            visit_id=visit_id,
            source_schema=source_schema,
        )
    if normalized_source == CURRENT_VISIT_SEVERITY_ORDER_SOURCE_KEY:
        return read_luxian_0609_severity_order_rows(
            institute_id=institute_id,
            patient_id=patient_id,
            visit_id=visit_id,
            source_schema=source_schema,
        )
    if normalized_source == CURRENT_VISIT_EXAM_LAB_ORDER_SOURCE_KEY:
        return read_luxian_0609_exam_lab_order_rows(
            institute_id=institute_id,
            patient_id=patient_id,
            visit_id=visit_id,
            source_schema=source_schema,
        )
    if normalized_source == CURRENT_VISIT_RESCUE_ORDER_SOURCE_KEY:
        return read_luxian_0609_rescue_order_rows(
            institute_id=institute_id,
            patient_id=patient_id,
            visit_id=visit_id,
            source_schema=source_schema,
        )
    if normalized_source == CURRENT_VISIT_UNSTABLE_ORDER_SOURCE_KEY:
        present = has_luxian_0609_current_visit_unstable_order(
            institute_id=institute_id,
            patient_id=patient_id,
            visit_id=visit_id,
            source_schema=source_schema,
        )
        return SnapshotSourceRows.create(
            source_key=normalized_source,
            rows=({"present": True},) if present else (),
            truncated=False,
            limit_rows=1,
        )
    approved_fields = _SNAPSHOT_SOURCE_FIELDS.get(normalized_source)
    if approved_fields is None:
        raise SourceEvidenceUnavailable()
    trusted_schema = _case_source_schema(institute_id=institute_id, patient_id=patient_id,
        visit_id=visit_id, source_schema=source_schema)
    engine = bundle_assembly._source_engine(trusted_schema)
    if engine is None:
        raise SourceEvidenceUnavailable()
    table_name = "labtest_item_report" if normalized_source == ROUTINE_LAB_ITEM_SOURCE_KEY else normalized_source
    columns = set(bundle_assembly._get_table_columns(trusted_schema, table_name))
    required = {"institute_id", "patient_id", "visit_id"}
    if not required.issubset(columns):
        if normalized_source in {
            "admission_record_diagnosis", "first_course_record_diagnosis",
            "discharge_record_diagnosis", "mr_diagnosis",
        }:
            return _read_cache_diagnosis_source(
                source_key=normalized_source, institute_id=institute_id,
                patient_id=patient_id, visit_id=visit_id, source_schema=source_schema,
            )
        raise SourceEvidenceUnavailable()
    selected = [field for field in approved_fields if field in columns]
    selected, document_status_column = _with_document_status_projection(
        table=table_name,
        columns=columns,
        selected=selected,
    )
    if not selected:
        raise SourceEvidenceUnavailable()
    order_candidates = (
        *getattr(bundle_assembly, "_ORDER_COLUMNS_PRIORITY", ()),
        "document_id",
        "pathology_exam_id",
        "pathology_id",
        "diagnosis_id",
        "order_id",
        "record_time",
        "report_datetime",
        "surgery_begin_datetime",
        "surgery_begin_time",
        "transfution_datetime",
    )
    order_columns = []
    # 优先业务主键/时间，再补齐全部批准投影字段形成稳定全序。
    # 完全相同的重复行即使数据库交换顺序，其规范化材料仍相同。
    for field in (*order_candidates, *selected):
        if field in columns and field not in order_columns:
            order_columns.append(field)
    if not order_columns:
        raise SourceEvidenceUnavailable()

    select_sql = _select_sql_with_document_status(selected, document_status_column)
    order_sql = ", ".join(
        f"{bundle_assembly._quote_ident(field)} ASC NULLS LAST"
        for field in order_columns
    )
    limit_rows = _source_limit(table_name)
    document_filter, document_params = _material_document_filter(
        schema=trusted_schema, table=table_name, columns=columns,
        institute_id=institute_id, patient_id=patient_id, visit_id=visit_id,
    )
    sql = (
        f"SELECT {select_sql} "
        f"FROM {bundle_assembly._qualified_table(trusted_schema, table_name)} "
        f"WHERE {bundle_assembly._quote_ident('institute_id')} = :institute_id "
        f"AND {bundle_assembly._quote_ident('patient_id')} = :patient_id "
        f"AND {bundle_assembly._quote_ident('visit_id')} = :visit_id "
        f"{document_filter} ORDER BY {order_sql} LIMIT :limit_rows"
    )
    try:
        with case_material.source_connection(engine) as connection:
            raw_rows = connection.execute(
                bundle_assembly.text(sql),
                {
                    "institute_id": institute_id,
                    "patient_id": patient_id,
                    "visit_id": visit_id,
                    **document_params,
                    "limit_rows": limit_rows + 1,
                },
            ).mappings().all()
    except Exception as error:
        # 仅未授权/未建的兼容子表可改读已授权父源；超时等真实故障仍保留错误。
        original = getattr(error, "orig", error)
        if (normalized_source in {
            "admission_record_diagnosis", "first_course_record_diagnosis",
            "discharge_record_diagnosis", "mr_diagnosis",
        } and getattr(original, "pgcode", None) in {"42P01", "42501"}):
            return _read_cache_diagnosis_source(
                source_key=normalized_source, institute_id=institute_id,
                patient_id=patient_id, visit_id=visit_id, source_schema=source_schema,
            )
        raise SourceEvidenceQueryError() from None
    if not raw_rows and normalized_source in {
        "admission_record_diagnosis", "first_course_record_diagnosis",
        "discharge_record_diagnosis", "mr_diagnosis",
    }:
        return _read_cache_diagnosis_source(
            source_key=normalized_source, institute_id=institute_id,
            patient_id=patient_id, visit_id=visit_id, source_schema=source_schema,
        )
    truncated = len(raw_rows) > limit_rows
    return SnapshotSourceRows.create(
        source_key=normalized_source,
        rows=[
            _normalize_snapshot_source_row(
                table_name,
                dict(row),
            )
            for row in raw_rows[:limit_rows]
        ],
        truncated=truncated,
        limit_rows=limit_rows,
    )
