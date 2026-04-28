from __future__ import annotations

from dataclasses import asdict, dataclass
import json
import re
from typing import Any


COMMON_META_FIELDS: tuple[str, ...] = (
    "document_id",
    "document_title",
    "record_time",
    "record_datetime",
    "round_datetime",
    "submit_datetime",
    "submit_time",
    "last_modified_datetime",
    "last_modified_time",
    "update_time",
)

_TEXT_CANDIDATES: tuple[str, ...] = (
    "record_content",
    "content",
    "note_text",
    "summary_text",
    "memo",
    "description",
    "original_text",
    "follow_up_visit_content",
)

_SPECIAL_SELECT_FIELDS: dict[str, tuple[str, ...]] = {
    "surgery_record": (
        "dept_name",
        "ward_name",
        "submitter",
        "surgeon_sign",
        "presurg_summary",
        "surgery_name",
        "surgery_code",
        "surgery_level",
        "surgical_level",
        "surgeon",
        "first_assistant",
        "second_assistant",
        "anesthesiologist",
        "anesthesia_method",
        "preoperative_diagnosis",
        "intraoperative_diagnosis",
        "postoperative_diagnosis",
        "surgery_process",
        "surgical_incisionheal_level",
        "surgery_begin_time",
        "surgery_end_time",
        "blood_loss",
        "other_content",
        "v2_schema",
    ),
    "presurg_discussion": (
        "discuss_staff",
        "host_summary",
        "host_name",
        "discuss_place",
        "discuss_time",
        "v2_schema",
    ),
    "exam_master": (
        "exam_no",
        "exam_name",
        "item_name",
        "item_code",
        "exam_type",
        "body_part",
        "request_datetime",
        "report_datetime",
        "report_time",
        "exam_result",
        "exam_impression",
        "exam_conclusion",
        "exam_findings",
        "diagnosis",
        "findings",
        "impression",
        "conclusion",
        "result",
    ),
    "labtest_master": (
        "test_id",
        "test_no",
        "labtest_subject",
        "labtest_cause",
        "specimen",
        "request_dept",
        "request_physician",
        "request_datetime",
        "report_datetime",
        "report_time",
        "reporter",
        "verifier",
        "labtest_result_status",
    ),
    "labtest_item_report": (
        "test_id",
        "test_no",
        "item_id",
        "item_name",
        "item_code",
        "item_abbreviation",
        "result",
        "unit",
        "referencevalue_min",
        "referencevalue_max",
        "reference_range",
        "abnormal_indicator",
        "report_status",
        "report_datetime",
        "report_time",
        "item_no",
    ),
    "inpat_drug_order": (
        "order_type",
        "order_class",
        "order_item_name",
        "order_item",
        "drug_name",
        "generic_name",
        "brand_name",
        "specification",
        "drug_specification",
        "dosage",
        "dose",
        "dose_unit",
        "frequency",
        "drug_frequency",
        "route",
        "drug_apply_method",
        "start_time",
        "stop_time",
        "status",
        "repeat_indicator",
        "prescribed_datetime",
        "prescribed_doctor",
        "single_dose",
        "single_dose_unit",
        "order_status",
    ),
    "inpat_nondrug_order": (
        "order_type",
        "order_class",
        "order_item_name",
        "order_item",
        "item_name",
        "order_name",
        "dosage",
        "dose",
        "dose_unit",
        "frequency",
        "route",
        "start_time",
        "stop_time",
        "status",
        "repeat_indicator",
        "prescribed_datetime",
        "prescribed_doctor",
        "quantity",
        "quantity_unit",
        "order_status",
    ),
}

_SECTION_LABELS: dict[str, str] = {
    "chief_complaint": "主诉",
    "history_of_present_illness": "现病史",
    "past_history": "既往史",
    "personal_history": "个人史",
    "marital_delivery_history": "婚育史",
    "menstrual_history": "月经史",
    "family_history": "家族史",
    "checkup": "体格检查",
    "checkup_special": "专科情况",
    "assist_exam": "辅助检查",
    "case_characteristic": "病例特点",
    "diagnose_based_on": "诊断依据",
    "differential_diagnosis": "鉴别诊断",
    "treatment_plan": "诊疗计划",
    "admission_condition": "入院情况",
    "treatment_course": "诊疗经过",
    "discharge_condition": "出院情况",
    "discharge_order": "出院医嘱",
    "generic_name": "药品名称",
    "brand_name": "商品名",
    "drug_specification": "规格",
    "drug_frequency": "频次",
    "drug_apply_method": "给药途径",
    "single_dose": "单次剂量",
    "single_dose_unit": "剂量单位",
    "repeat_indicator": "长临标识",
    "prescribed_datetime": "下达时间",
    "prescribed_doctor": "下达医生",
    "order_status": "医嘱状态",
    "order_name": "医嘱名称",
    "quantity": "数量",
    "quantity_unit": "数量单位",
}

_DOC_TYPE_LABELS: dict[str, str] = {
    "admission_record": "入院记录",
    "first_course_record": "首次病程记录",
    "daily_course_record": "日常病程记录",
    "senior_course_record": "上级医师查房记录",
    "consultation_record": "会诊记录",
    "summary_record": "阶段小结",
    "handoff_record": "交班记录",
    "handover_record": "接班记录",
    "diffcase_discussion_record": "疑难病例讨论记录",
    "surgery_record": "手术记录",
    "postsurg_firstcourse_record": "术后首次病程记录",
    "rescue_record": "抢救记录",
    "transfer_in_record": "转入记录",
    "transfer_out_record": "转出记录",
    "bloodtrans_record": "输血记录",
    "nursing_record": "护理记录",
    "discharge_record": "出院记录",
    "exam_master": "检查结果",
    "exam_item_report": "检查结果",
    "labtest_master": "检验申请单",
    "labtest_item_report": "检验明细",
    "inpat_drug_order": "长期医嘱",
    "inpat_nondrug_order": "临时医嘱",
    "exam_attention_report": "检查关注摘要",
    "lab_attention_report": "检验关注摘要",
}


@dataclass(frozen=True)
class AssemblyFieldSpec:
    key: str
    required: bool = False


@dataclass(frozen=True)
class AssembledSection:
    section_key: str
    section_label: str
    text: str
    source_field: str
    order_index: int

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class DocumentSourceField:
    source_table: str
    source_field: str
    source_path: str | None
    used: bool
    raw_value_preview: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class AssembledDocument:
    document_type: str
    document_id: str
    document_title: str
    record_time: str | None
    submit_time: str | None
    last_modified_time: str | None
    display_time: str | None
    assembled_text: str
    sections: list[AssembledSection]
    source_fields: list[DocumentSourceField]
    assembly_status: str
    data_quality_flags: list[str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "document_type": self.document_type,
            "document_id": self.document_id,
            "document_title": self.document_title,
            "record_time": self.record_time,
            "submit_time": self.submit_time,
            "last_modified_time": self.last_modified_time,
            "display_time": self.display_time,
            "assembled_text": self.assembled_text,
            "sections": [section.to_dict() for section in self.sections],
            "source_fields": [field.to_dict() for field in self.source_fields],
            "assembly_status": self.assembly_status,
            "data_quality_flags": list(self.data_quality_flags),
        }


_MULTI_FIELD_RULES: dict[str, tuple[AssemblyFieldSpec, ...]] = {
    "admission_record": (
        AssemblyFieldSpec("chief_complaint", required=True),
        AssemblyFieldSpec("history_of_present_illness", required=True),
        AssemblyFieldSpec("past_history"),
        AssemblyFieldSpec("personal_history"),
        AssemblyFieldSpec("marital_delivery_history"),
        AssemblyFieldSpec("menstrual_history"),
        AssemblyFieldSpec("family_history"),
        AssemblyFieldSpec("checkup", required=True),
        AssemblyFieldSpec("checkup_special"),
        AssemblyFieldSpec("assist_exam", required=True),
    ),
    "first_course_record": (
        AssemblyFieldSpec("case_characteristic", required=True),
        AssemblyFieldSpec("diagnose_based_on", required=True),
        AssemblyFieldSpec("differential_diagnosis", required=True),
        AssemblyFieldSpec("treatment_plan", required=True),
    ),
    "discharge_record": (
        AssemblyFieldSpec("admission_condition", required=True),
        AssemblyFieldSpec("treatment_course", required=True),
        AssemblyFieldSpec("discharge_condition", required=True),
        AssemblyFieldSpec("discharge_order", required=True),
    ),
    "inpat_drug_order": (
        AssemblyFieldSpec("repeat_indicator"),
        AssemblyFieldSpec("generic_name"),
        AssemblyFieldSpec("brand_name"),
        AssemblyFieldSpec("drug_specification"),
        AssemblyFieldSpec("single_dose"),
        AssemblyFieldSpec("single_dose_unit"),
        AssemblyFieldSpec("drug_frequency"),
        AssemblyFieldSpec("drug_apply_method"),
        AssemblyFieldSpec("prescribed_datetime"),
        AssemblyFieldSpec("prescribed_doctor"),
        AssemblyFieldSpec("order_status"),
    ),
    "inpat_nondrug_order": (
        AssemblyFieldSpec("repeat_indicator"),
        AssemblyFieldSpec("order_type"),
        AssemblyFieldSpec("order_name"),
        AssemblyFieldSpec("quantity"),
        AssemblyFieldSpec("quantity_unit"),
        AssemblyFieldSpec("frequency"),
        AssemblyFieldSpec("prescribed_datetime"),
        AssemblyFieldSpec("prescribed_doctor"),
        AssemblyFieldSpec("order_status"),
    ),
}

_SURGERY_FIELD_ORDER: tuple[tuple[str, str], ...] = (
    ("record_time", "记录时间"),
    ("dept_name", "科室"),
    ("ward_name", "病房"),
    ("submitter", "记录者"),
    ("surgeon_sign", "手术医生签名"),
    ("presurg_summary", "术前小结"),
    ("surgery_name", "手术项目"),
    ("surgery_code", "手术编码"),
    ("surgery_level", "手术等级"),
    ("surgeon", "手术医师"),
    ("first_assistant", "手术I助"),
    ("second_assistant", "手术II助"),
    ("anesthesiologist", "麻醉医师"),
    ("anesthesia_method", "麻醉方式"),
    ("preoperative_diagnosis", "术前诊断"),
    ("intraoperative_diagnosis", "术中诊断"),
    ("postoperative_diagnosis", "术后诊断"),
    ("surgery_process", "手术经过"),
    ("surgical_incisionheal_level", "切口愈合等级"),
    ("surgery_begin_time", "手术开始时间"),
    ("surgery_end_time", "手术结束时间"),
    ("blood_loss", "失血量"),
    ("other_content", "其他内容"),
    ("record_content", "记录内容"),
)


def _normalize_text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _extract_from_json_like(value: Any) -> str:
    if isinstance(value, list):
        parts = [_extract_from_json_like(item) for item in value]
        return "\n".join(item for item in parts if item).strip()
    if isinstance(value, dict):
        for key in ("original_text", "text", "content", "record_content"):
            candidate = _normalize_text(value.get(key))
            if candidate:
                return candidate
        parts = [_extract_from_json_like(item) for item in value.values()]
        return "\n".join(item for item in parts if item).strip()
    return _normalize_text(value)


def _extract_field_text(row: dict[str, Any], field_name: str) -> str:
    if field_name not in row:
        return ""
    value = row.get(field_name)
    if value is None:
        return ""
    if isinstance(value, (dict, list)):
        return _extract_from_json_like(value)
    text_value = _normalize_text(value)
    if not text_value:
        return ""
    if text_value[:1] in {"{", "["}:
        try:
            return _extract_from_json_like(json.loads(text_value))
        except Exception:
            return text_value
    return text_value


def _extract_v2_field_text(row: dict[str, Any], field_name: str) -> str:
    raw = row.get("v2_schema")
    if raw is None:
        return ""
    try:
        payload = raw if isinstance(raw, dict) else json.loads(str(raw))
    except Exception:
        return ""
    if not isinstance(payload, dict):
        return ""
    value = payload.get(field_name)
    if value is None:
        return ""
    return _extract_from_json_like(value)


def _is_non_content_placeholder(text: str) -> bool:
    value = _normalize_text(text)
    return value in {"无", "暂无", "未记录", "未填写", "N/A", "-"}


def _merge_field_text(row: dict[str, Any], *field_names: str) -> str:
    for field_name in field_names:
        direct = _extract_field_text(row, field_name)
        if direct:
            return direct
        via_v2 = _extract_v2_field_text(row, field_name)
        if via_v2:
            return via_v2
    return ""


def _assemble_surgery_record_text(payload: dict[str, Any]) -> str:
    record_content = _merge_field_text(payload, "record_content")
    surgery_process = _merge_field_text(payload, "surgery_process")
    if not surgery_process:
        # 个别数据将术中过程写入 postsurg_firstcourse，不在 surgery_record；这里保持空串即可。
        surgery_process = ""

    lines = [
        f"记录时间: {_merge_field_text(payload, 'record_time', 'record_datetime', 'submit_time', 'submit_datetime', 'last_modified_time', 'update_time')}",
        f"科室: {_merge_field_text(payload, 'dept_name')}",
        f"病房: {_merge_field_text(payload, 'ward_name', 'ward_no')}",
        f"记录者: {_merge_field_text(payload, 'submitter', 'recorder_sign')}",
        f"手术医生签名: {_merge_field_text(payload, 'surgeon_sign')}",
        f"术前小结: {_merge_field_text(payload, 'presurg_summary')}",
        f"手术项目: {_merge_field_text(payload, 'surgery_name')}",
        f"手术编码: {_merge_field_text(payload, 'surgery_code')}",
        f"手术等级: {_merge_field_text(payload, 'surgery_level', 'surgical_level')}",
        f"手术医师: {_merge_field_text(payload, 'surgeon')}",
        f"手术I助: {_merge_field_text(payload, 'first_assistant')}",
        f"手术II助: {_merge_field_text(payload, 'second_assistant')}",
        f"麻醉医师: {_merge_field_text(payload, 'anesthesiologist')}",
        f"麻醉方式: {_merge_field_text(payload, 'anesthesia_method')}",
        f"术前诊断: {_merge_field_text(payload, 'preoperative_diagnosis')}",
        f"术中诊断: {_merge_field_text(payload, 'intraoperative_diagnosis')}",
        f"术后诊断: {_merge_field_text(payload, 'postoperative_diagnosis')}",
        f"手术经过: {surgery_process}",
        f"切口愈合等级: {_merge_field_text(payload, 'surgical_incisionheal_level')}",
        f"手术开始时间: {_merge_field_text(payload, 'surgery_begin_time')}",
        f"手术结束时间: {_merge_field_text(payload, 'surgery_end_time')}",
        f"失血量: {_merge_field_text(payload, 'blood_loss')}",
        f"其他内容: {_merge_field_text(payload, 'other_content')}",
        f"记录内容: {record_content}",
    ]
    return "\n".join(lines).strip()


def _build_surgery_source_fields(payload: dict[str, Any]) -> list[DocumentSourceField]:
    fields: list[DocumentSourceField] = []
    for field_name, _label in _SURGERY_FIELD_ORDER:
        field_value = _merge_field_text(payload, field_name)
        fields.append(
            DocumentSourceField(
                source_table="surgery_record",
                source_field=field_name,
                source_path=None,
                used=True,
                raw_value_preview=field_value,
            )
        )
    return fields


def _assemble_presurg_discussion_text(payload: dict[str, Any]) -> str:
    record_content = _merge_field_text(payload, "record_content")
    if record_content:
        return record_content

    parts: list[str] = []
    for label, keys in (
        ("讨论时间", ("discuss_time", "record_time")),
        ("讨论地点", ("discuss_place", "host_name")),
        ("主持人", ("host_name",)),
        ("参与人员", ("discuss_staff",)),
        ("讨论摘要", ("host_summary",)),
    ):
        value = _merge_field_text(payload, *keys)
        if value:
            parts.append(f"{label}: {value}")
    return "\n".join(parts).strip()


def _extract_direct_text(row: dict[str, Any]) -> tuple[str, str]:
    for field_name in _TEXT_CANDIDATES:
        text_value = _extract_field_text(row, field_name)
        if text_value:
            return field_name, text_value
    return "", ""


def _resolve_title(document_type: str, row: dict[str, Any], assembled_text: str) -> tuple[str, list[str]]:
    flags: list[str] = []
    raw_title = _normalize_text(row.get("document_title"))
    if raw_title:
        return raw_title, flags
    if assembled_text:
        first_line = assembled_text.splitlines()[0].strip()
        match = re.match(r"^([^：:\n]{2,60}(?:记录|查房))(?:[:：，。,、\s]|$)", first_line)
        if not match:
            match = re.search(r"([^：:\n]{2,60}(?:记录|查房))", first_line)
        if match:
            flags.append("missing_source_title")
            return match.group(1).strip(), flags
    flags.append("missing_source_title")
    flags.append("fallback_title")
    return _DOC_TYPE_LABELS.get(document_type, document_type), flags


def _resolve_display_times(row: dict[str, Any]) -> tuple[str | None, str | None, str | None, str | None]:
    record_time = _normalize_text(
        row.get("record_time") or row.get("record_datetime") or row.get("round_datetime")
    ) or None
    submit_time = _normalize_text(row.get("submit_datetime") or row.get("submit_time")) or None
    last_modified_time = _normalize_text(
        row.get("last_modified_datetime") or row.get("last_modified_time")
    ) or None
    display_time = record_time or submit_time or last_modified_time or _normalize_text(row.get("update_time")) or None
    return record_time, submit_time, last_modified_time, display_time


def build_document_select_columns(document_type: str, available_columns: set[str]) -> list[str]:
    selected: list[str] = []
    for column_name in COMMON_META_FIELDS:
        if column_name in available_columns and column_name not in selected:
            selected.append(column_name)
    if document_type in _MULTI_FIELD_RULES:
        for spec in _MULTI_FIELD_RULES[document_type]:
            if spec.key in available_columns and spec.key not in selected:
                selected.append(spec.key)
    for field_name in _TEXT_CANDIDATES:
        if field_name in available_columns and field_name not in selected:
            selected.append(field_name)
    for field_name in _SPECIAL_SELECT_FIELDS.get(document_type, ()):
        if field_name in available_columns and field_name not in selected:
            selected.append(field_name)
    return selected


def assemble_document(document_type: str, row: dict[str, Any] | None) -> AssembledDocument:
    payload = dict(row or {})
    source_fields: list[DocumentSourceField] = []
    sections: list[AssembledSection] = []
    flags: list[str] = []

    if document_type == "surgery_record":
        assembled_text = _assemble_surgery_record_text(payload)
        source_fields.extend(_build_surgery_source_fields(payload))
        if _is_non_content_placeholder(_merge_field_text(payload, "record_content")):
            flags.append("record_content_placeholder")
    elif document_type == "presurg_discussion":
        assembled_text = _assemble_presurg_discussion_text(payload)
        source_fields.append(
            DocumentSourceField(
                source_table=document_type,
                source_field="presurg_discussion_template",
                source_path=None,
                used=bool(assembled_text),
                raw_value_preview=assembled_text[:120],
            )
        )
        sections.append(
            AssembledSection(
                section_key="presurg_discussion_template",
                section_label="正文",
                text=assembled_text,
                source_field="presurg_discussion_template",
                order_index=0,
            )
        )
    elif document_type in _MULTI_FIELD_RULES:
        texts: list[str] = []
        for index, spec in enumerate(_MULTI_FIELD_RULES[document_type]):
            text_value = _extract_field_text(payload, spec.key)
            source_fields.append(
                DocumentSourceField(
                    source_table=document_type,
                    source_field=spec.key,
                    source_path=None,
                    used=bool(text_value),
                    raw_value_preview=text_value[:120],
                )
            )
            if not text_value:
                if spec.required:
                    flags.append(f"missing_required_field:{spec.key}")
                continue
            sections.append(
                AssembledSection(
                    section_key=spec.key,
                    section_label=_SECTION_LABELS.get(spec.key, spec.key),
                    text=text_value,
                    source_field=spec.key,
                    order_index=index,
                )
            )
            texts.append(text_value)
        assembled_text = "\n".join(texts).strip()
        if not assembled_text:
            source_field, assembled_text = _extract_direct_text(payload)
            if source_field:
                source_fields.append(
                    DocumentSourceField(
                        source_table=document_type,
                        source_field=source_field,
                        source_path=None,
                        used=bool(assembled_text),
                        raw_value_preview=assembled_text[:120],
                    )
                )
                sections.append(
                    AssembledSection(
                        section_key=source_field,
                        section_label=_SECTION_LABELS.get(source_field, "正文"),
                        text=assembled_text,
                        source_field=source_field,
                        order_index=len(sections),
                    )
                )
    else:
        source_field, assembled_text = _extract_direct_text(payload)
        if source_field:
            source_fields.append(
                DocumentSourceField(
                    source_table=document_type,
                    source_field=source_field,
                    source_path=None,
                    used=bool(assembled_text),
                    raw_value_preview=assembled_text[:120],
                )
            )
            sections.append(
                AssembledSection(
                    section_key=source_field,
                    section_label=_SECTION_LABELS.get(source_field, "正文"),
                    text=assembled_text,
                    source_field=source_field,
                    order_index=0,
                )
            )
        elif payload:
            flags.append("missing_primary_text")

    title, title_flags = _resolve_title(document_type, payload, assembled_text)
    flags.extend(title_flags)

    record_time, submit_time, last_modified_time, display_time = _resolve_display_times(payload)
    if not display_time:
        flags.append("missing_display_time")

    if not assembled_text:
        status = "empty_document"
        flags.append("empty_document")
    elif any(flag.startswith("missing_required_field:") for flag in flags):
        status = "partial"
    elif any(flag in {"missing_source_title", "missing_display_time", "missing_primary_text"} for flag in flags):
        status = "partial"
    else:
        status = "assembled"

    return AssembledDocument(
        document_type=document_type,
        document_id=_normalize_text(payload.get("document_id")),
        document_title=title,
        record_time=record_time,
        submit_time=submit_time,
        last_modified_time=last_modified_time,
        display_time=display_time,
        assembled_text=assembled_text,
        sections=sections,
        source_fields=source_fields,
        assembly_status=status,
        data_quality_flags=list(dict.fromkeys(flag for flag in flags if flag)),
    )


def assemble_visit_documents(documents_by_type: dict[str, list[dict[str, Any]]]) -> list[AssembledDocument]:
    assembled: list[AssembledDocument] = []
    for document_type, rows in documents_by_type.items():
        for row in rows or []:
            assembled.append(assemble_document(document_type, row))
    assembled.sort(
        key=lambda item: (
            str(item.display_time or ""),
            str(item.document_id or ""),
            str(item.document_type or ""),
        )
    )
    return assembled
