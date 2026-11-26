from __future__ import annotations

from datetime import datetime
import re
from typing import Any

from ..document_assembly.assembler import INDEPENDENT_DOCUMENT_FIELDS, PERIOPERATIVE_DISPLAY_FIELDS

from .assembly import (
    _build_grouped_exam_reports,
    _build_grouped_lab_reports,
    assemble_domain_bundle,
    load_domain_bundle,
    load_domain_bundle_document_index,
    load_domain_bundle_for_emr_render,
    load_or_assemble_domain_bundle,
)
from .contracts import BUNDLE_SCHEMA_VERSION_CURRENT

# 只搬运业务 owner 已判定的展示字段；完整材料留在冻结副本内。
_MATERIAL_DISPLAY_FIELDS: tuple[str, ...] = (
    "source_version_key", "version_id", "source_record_identity", "source_namespace", "source_object",
    "material_state", "material_selected", "material_rule_usable", "material_source_label",
    "material_notice", "material_scope_notice",
)

_DOMAIN_LOAD_ORDER: tuple[str, ...] = (
    "admission",
    "course",
    "surgery",
    "consult_discussion",
    "terminal",
    "index_coding_settlement",
)

_COURSE_SOURCE_COVERAGE_KEYS: frozenset[str] = frozenset(
    {
        "exam_master",
        "exam_item_report",
        "labtest_master",
        "labtest_item_report",
        "pathology_exam_master",
        "pathology_exam_report",
    }
)

_GROUP_DEFS: tuple[dict[str, str], ...] = (
    {"key": "all", "label": "全部"},
    {"key": "frontpage", "label": "病案首页(临床医生)"},
    {"key": "admission", "label": "入院记录"},
    {"key": "course", "label": "病程记录"},
    {"key": "exam_attention", "label": "检查检验摘要"},
    {"key": "lab_results", "label": "检验报告"},
    {"key": "exam_results", "label": "检查结果"},
    {"key": "surgery", "label": "手术相关单据"},
    {"key": "terminal", "label": "出院记录"},
    {"key": "orders", "label": "医嘱"},
    {"key": "pdf_supplement", "label": "PDF补充待核对"},
)

_DOC_TYPE_LABELS: dict[str, str] = {
    "admission_record": "入院记录",
    "admission_record_diagnosis": "入院记录诊断",
    "discharge_record_diagnosis": "出院记录诊断",
    "first_course_record": "首次病程记录",
    "daily_course_record": "日常病程记录",
    "senior_course_record": "上级医师查房记录",
    "consultation_record": "会诊记录",
    "surgery_record": "手术记录",
    "anesthesia_record": "麻醉记录",
    "postsurg_firstcourse_record": "术后首次病程记录",
    "presurg_discussion": "术前讨论记录",
    "presurg_summary": "术前小结",
    "surgery_safecheck_record": "手术安全核查记录单",
    "discharge_record": "出院记录",
    "death_record": "死亡记录",
    "mr": "病案首页",
    "diagnosis": "诊断信息",
    "mr_surgery": "手术信息",
    "mr_cost": "费用信息",
    "medical_insurance_settlement": "医保结算",
    "medical_insurance_settlement_cost": "医保结算明细",
    "exam_attention_report": "检查关注摘要",
    "lab_attention_report": "检验关注摘要",
    "exam_master": "检查结果",
    "exam_item_report": "检查结果",
    "labtest_master": "检验申请单",
    "labtest_item_report": "检验报告",
    "inpat_drug_order": "长期医嘱",
    "inpat_nondrug_order": "临时医嘱",
}

_GROUP_BY_DOC_TYPE: dict[str, str] = {
    "mr": "frontpage",
    "diagnosis": "frontpage",
    "mr_surgery": "frontpage",
    "mr_cost": "frontpage",
    "medical_insurance_settlement": "frontpage",
    "medical_insurance_settlement_cost": "frontpage",
    "admission_record": "admission",
    "admission_record_diagnosis": "admission",
    "first_course_record": "course",
    "daily_course_record": "course",
    "senior_course_record": "course",
    "rescue_record": "course",
    "consultation_record": "course",
    "exam_attention_report": "exam_attention",
    "lab_attention_report": "exam_attention",
    "labtest_master": "lab_results",
    "labtest_item_report": "lab_results",
    "exam_master": "exam_results",
    "exam_item_report": "exam_results",
    "surgery_record": "surgery",
    "anesthesia_record": "surgery",
    "presurg_discussion": "surgery",
    "presurg_summary": "surgery",
    "postsurg_firstcourse_record": "surgery",
    "surgery_safecheck_record": "surgery",
    "consent_form": "surgery",
    "discharge_record": "terminal",
    "discharge_record_diagnosis": "terminal",
    "death_record": "terminal",
    "death_discussion": "terminal",
    "inpat_drug_order": "orders",
    "inpat_nondrug_order": "orders",
}

_ORDER_DOC_TYPES = {"inpat_drug_order", "inpat_nondrug_order"}
_PARAGRAPH_ONLY_DOC_TYPES = {"first_course_record"}
_RECORD_TIME_FALLBACK_DOC_TYPES = {
    "first_course_record",
    "daily_course_record",
    "senior_course_record",
    "postsurg_firstcourse_record",
    "rescue_record",
    "transfer_in_record",
    "transfer_out_record",
    "bloodtrans_record",
    "surgery_application",
    "presurg_summary",
    "surgery_safecheck_record",
    "discharge_record",
    "exam_master",
    "exam_item_report",
    "labtest_master",
    "labtest_item_report",
    "pathology_exam_master",
    "pathology_exam_report",
}
_SURGERY_STRUCT_DOC_TYPES: set[str] = {
    "surgery_record",
    "anesthesia_record",
    "presurg_summary",
    "presurg_discussion",
    "surgery_safecheck_record",
    "postsurg_firstcourse_record",
}

_FIELD_LABELS: dict[str, str] = {
    "record_time": "记录时间",
    "record_datetime": "记录时间",
    "submit_time": "提交时间",
    "submit_datetime": "提交时间",
    "last_modified_time": "最后修改时间",
    "department": "科室",
    "ward_name": "病区",
    "ward_no": "病房",
    "bed_no": "床号",
    "doctor_name": "医生",
    "diagnosis": "诊断",
    "chief_complaint": "主诉",
    "history_of_present_illness": "现病史",
    "past_history": "既往史",
    "checkup": "体格检查",
    "assist_exam": "辅助检查",
    "diagnosis_type": "诊断类型",
    "diagnosis_id": "诊断序号",
    "diagnosis_no": "诊断序号",
    "diagnosis_name": "诊断名称",
    "diagnosis_code": "诊断编码",
    "diagnosis_main": "是否主诊断",
    "dept_name": "科室",
    "submitter": "记录者",
    "surgeon_sign": "手术医生签名",
    "presurg_summary": "术前小结",
    "surgery_name": "手术项目",
    "surgery_code": "手术编码",
    "surgery_level": "手术等级",
    "surgical_level": "手术等级",
    "surgeon": "手术医师",
    "first_assistant": "手术I助",
    "second_assistant": "手术II助",
    "anesthesiologist": "麻醉医师",
    "anesthesia_method": "麻醉方式",
    "surgery_method": "手术方式",
    "surgery_nurse": "手术护士",
    "surgeon_statement": "手术医师陈述",
    "anesthesiologist_statement": "麻醉医师陈述",
    "surg_nurse_statement": "手术护士陈述",
    "planned_surgery": "拟实施手术",
    "surgery_bodypost": "手术体位",
    "trachea_intubate_type": "气管插管类型",
    "anesthesia_bodypost": "麻醉体位",
    "breath_type": "呼吸类型",
    "anesthesia_description": "麻醉描述",
    "anesthesia_complication_sign": "麻醉合并症",
    "treatment_course": "诊疗经过",
    "puncture_process": "穿刺过程",
    "preanes_medication": "麻醉前用药",
    "asa_level": "ASA分级",
    "anesthesia_begin_datetime": "麻醉开始时间",
    "anesthesia_end_datetime": "麻醉结束时间",
    "leave_operateroom_datetime": "离室时间",
    "application_id": "申请号",
    "assessment_datetime": "评估时间",
    "surgeon_assess_date": "手术医师评估日期",
    "anesthesiologist_assess_date": "麻醉医师评估日期",
    "preoperative_diagnosis": "术前诊断",
    "intraoperative_diagnosis": "术中诊断",
    "postoperative_diagnosis": "术后诊断",
    "surgery_process": "手术经过",
    "surgical_incisionheal_level": "切口愈合等级",
    "surgery_begin_time": "手术开始时间",
    "surgery_end_time": "手术结束时间",
    "surgery_begin_datetime": "手术开始时间（源字段）",
    "surgery_end_datetime": "手术结束时间（源字段）",
    "last_modified_datetime": "修改时间",
    "blood_loss": "失血量",
    "other_content": "其他内容",
    "discuss_staff": "参与人员",
    "host_summary": "讨论摘要",
    "host_name": "主持人",
    "discuss_place": "讨论地点",
    "discuss_time": "讨论时间",
}

_KV_TITLE_BY_DOC_TYPE: dict[str, str] = {
    "surgery_record": "手术记录",
    "anesthesia_record": "麻醉记录",
    "presurg_summary": "术前小结",
    "presurg_discussion": "术前讨论",
    "surgery_safecheck_record": "手术安全核查",
    "postsurg_firstcourse_record": "术后首次病程记录",
}

_SURGERY_TEMPLATE_FIELDS: tuple[tuple[str, str], ...] = (
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
)

_ADMISSION_DIAGNOSIS_ALLOWED_TYPES: set[str] = {"初步诊断", "入院诊断"}
_FIRST_COURSE_DIAGNOSIS_ALLOWED_TYPES: set[str] = {"初步诊断", "入院诊断"}
_DISCHARGE_DIAGNOSIS_ALLOWED_TYPES: set[str] = {"出院诊断", "出院主要诊断", "出院其他诊断"}


def _should_skip_template_source_field(source_field: str) -> bool:
    field = _safe_text(source_field).lower()
    return field.endswith("_template")


def _extract_kv_from_content(content: str, *, max_fields: int, keep_empty_value: bool) -> list[dict[str, str]]:
    fields: list[dict[str, str]] = []
    seen: set[str] = set()
    current_field: dict[str, str] | None = None
    for line in content.splitlines():
        raw = _safe_text(line)
        if not raw:
            continue
        matched = re.match(r"^([^:：]{1,36})[:：]\s*(.*)$", raw)
        if not matched:
            if current_field is not None:
                current_field["value"] = "\n".join(
                    item for item in (current_field["value"], raw) if item
                )
            continue
        key = matched.group(1).strip()
        value = matched.group(2).strip()
        if not key:
            current_field = None
            continue
        if (not keep_empty_value) and (not value):
            current_field = None
            continue
        norm_key = key.replace(" ", "_").lower()
        if norm_key in seen:
            current_field = None
            continue
        if len(fields) >= max_fields:
            break
        seen.add(norm_key)
        fields.append({"key": norm_key, "label": key, "value": value})
        current_field = fields[-1]
    return fields


def _fallback_surgery_template_fields() -> list[dict[str, str]]:
    return [{"key": key, "label": label, "value": ""} for key, label in _SURGERY_TEMPLATE_FIELDS]


def _safe_text(value: Any) -> str:
    return str(value or "").strip()


def _parse_sort_time(value: str) -> float:
    text = _safe_text(value)
    if not text:
        return float("inf")
    normalized = text.replace(" ", "T").replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(normalized).timestamp()
    except Exception:
        return float("inf")


def _infer_group_key(doc_type: str) -> str:
    if doc_type in _GROUP_BY_DOC_TYPE:
        return _GROUP_BY_DOC_TYPE[doc_type]
    if "order" in doc_type:
        return "orders"
    if "surgery" in doc_type or "anesthesia" in doc_type:
        return "surgery"
    if "discharge" in doc_type or "death" in doc_type:
        return "terminal"
    if "admission" in doc_type:
        return "admission"
    return "course"


def _friendly_doc_label(doc_type: str, title: str) -> str:
    if title:
        return title
    return _DOC_TYPE_LABELS.get(doc_type, doc_type or "病历文书")


def _friendly_field_label(field_name: str) -> str:
    normalized = _safe_text(field_name).lower()
    if normalized in _FIELD_LABELS:
        return _FIELD_LABELS[normalized]
    if not normalized:
        return "字段"
    return normalized.replace("_", " ").strip()


def _perioperative_display_fields(doc_type: str, document: dict[str, Any]) -> list[dict[str, str]]:
    return [
        {"key": field, "label": _friendly_field_label(field), "value": value}
        for field in PERIOPERATIVE_DISPLAY_FIELDS.get(doc_type, ())
        if (value := _safe_text(document.get(field)))
    ]


def _build_doc_key(doc_type: str, document_id: str, index: int) -> str:
    suffix = document_id if document_id else str(index)
    return f"{doc_type}::{suffix}"


def _source_field_preview(raw_doc: dict[str, Any], field_names: tuple[str, ...]) -> str:
    wanted = set(field_names)
    for field in raw_doc.get("source_fields") or []:
        if not isinstance(field, dict):
            continue
        if _safe_text(field.get("source_field")) not in wanted:
            continue
        value = _safe_text(field.get("raw_value_preview"))
        if value:
            return value
    return ""


def _record_display_clock(raw_doc: dict[str, Any], doc_type: str, sort_time: str) -> tuple[str, str, str]:
    record_time = _safe_text(raw_doc.get("record_time"))
    if record_time:
        return record_time, "source_record_time", ""
    submit_time = _safe_text(raw_doc.get("submit_time") or raw_doc.get("submit_datetime"))
    if submit_time:
        return submit_time, "source_submit_time", "源库未返回记录时间，当前显示提交时间。"
    if doc_type in _RECORD_TIME_FALLBACK_DOC_TYPES and sort_time:
        return sort_time, "fallback_display_time", "源库未返回记录时间，当前使用提交时间、最后修改时间或更新时间等可用时间显示。"
    return "", "", ""


def _normalize_source_document(
    *,
    raw_doc: dict[str, Any],
    index: int,
    execution_domain: str,
    include_exam_evidence_coordinates: bool = False,
) -> dict[str, Any]:
    doc_type = _safe_text(raw_doc.get("document_type") or raw_doc.get("source_table"))
    doc_id = _safe_text(raw_doc.get("document_id"))
    doc_title = _safe_text(raw_doc.get("document_title"))
    content = _safe_text(raw_doc.get("content"))
    sort_time = _safe_text(raw_doc.get("display_time") or raw_doc.get("record_time"))
    if not sort_time and doc_type in _ORDER_DOC_TYPES:
        # 已保存的旧领域包可能还没有 display_time；仅从已保存的受控字段摘要
        # 回填医嘱开始/下达时间，避免浏览历史病历时误显示“未返回时间”。
        sort_time = _source_field_preview(
            raw_doc,
            ("start_time", "order_time", "prescribed_datetime"),
        )
    submit_time = _safe_text(raw_doc.get("submit_time") or raw_doc.get("submit_datetime"))
    sort_time = sort_time or submit_time
    record_time, record_time_source, record_time_note = _record_display_clock(raw_doc, doc_type, sort_time)
    group_key = _infer_group_key(doc_type)
    label = _friendly_doc_label(doc_type, doc_title)
    doc_key = (f"{doc_type}::{raw_doc['source_record_identity']}::{raw_doc['version_id']}"
               if raw_doc.get("source_record_identity") and raw_doc.get("version_id")
               else _build_doc_key(doc_type, doc_id, index))
    normalized_id = doc_id or doc_key

    sections = list(raw_doc.get("sections") or [])
    source_fields = list(raw_doc.get("source_fields") or [])
    normalized = {
        "id": normalized_id,
        "doc_id": normalized_id,
        "doc_key": doc_key,
        "doc_type": doc_type,
        "doc_name": label,
        "type": doc_type,
        "label": label,
        "document_id": doc_id,
        "document_title": doc_title or label,
        "sort_time": sort_time,
        "record_time": record_time,
        "submit_time": submit_time,
        "record_time_source": record_time_source,
        "record_time_note": record_time_note,
        "document_status": raw_doc.get("document_status"),
        "has_content": bool(content) or bool(_perioperative_display_fields(doc_type, raw_doc)),
        "content": content or None,
        "length": len(content),
        "group_key": group_key,
        "execution_domain": execution_domain,
        "sections": sections,
        "source_fields": source_fields,
        "assembly_status": _safe_text(raw_doc.get("assembly_status")),
        "data_quality_flags": list(raw_doc.get("data_quality_flags") or []),
        "authors": list(raw_doc.get("authors") or []),
        "signatures": list(raw_doc.get("signatures") or []),
        "participants": list(raw_doc.get("participants") or []),
        "report_items": list(raw_doc.get("report_items") or []),
        "report_metadata": dict(raw_doc.get("report_metadata") or {}),
        "projection_incomplete": raw_doc.get("projection_incomplete") is True,
        "projection_notice": _safe_text(raw_doc.get("projection_notice")),
        "source": "bundle",
    }
    for key in (*_MATERIAL_DISPLAY_FIELDS, "daily_material", "daily_material_scope", "primary_material", "primary_material_scope"):
        if key in raw_doc:
            normalized[key] = raw_doc[key]
    if include_exam_evidence_coordinates and raw_doc.get("exam_evidence_coordinates"):
        normalized["exam_evidence_coordinates"] = raw_doc["exam_evidence_coordinates"]
    if raw_doc.get("chief_physician_sign_datetime") is not None:
        normalized["chief_physician_sign_datetime"] = _safe_text(raw_doc["chief_physician_sign_datetime"])
    for field_name in INDEPENDENT_DOCUMENT_FIELDS.get(doc_type, ()):
        if raw_doc.get(field_name) is not None:
            normalized[field_name] = raw_doc[field_name]
    if doc_type in _ORDER_DOC_TYPES:
        normalized.update(
            {
                f"order_{key}" if key not in {"order_id", "order_type", "order_item", "order_status"} else key: value
                for key, value in _order_display_values(raw_doc).items()
            }
        )
    return normalized


def _lab_application_subject(document: dict[str, Any]) -> str:
    return _source_field_preview(
        document,
        ("labtest_subject", "specimen", "request_dept"),
    )


def _lab_application_item_name(document: dict[str, Any]) -> str:
    content = _safe_text(document.get("content"))
    for label in ("检验项目", "检验名称", "项目名称"):
        matched = re.search(rf"(?:^|\n){label}\s*[:：]\s*([^\n]+)", content)
        if matched:
            return matched.group(1).strip()
    return "未返回检验项目"


def _collapse_labtest_master_documents(documents: list[dict[str, Any]]) -> list[dict[str, Any]]:
    applications = [item for item in documents if item.get("doc_type") == "labtest_master"]
    if len(applications) <= 1:
        return documents

    ordered = sorted(
        applications,
        key=lambda item: (
            _parse_sort_time(_safe_text(item.get("sort_time") or item.get("record_time"))),
            _safe_text(item.get("document_id")),
        ),
    )
    lines = [
        " · ".join(
            filter(
                None,
                (
                    _safe_text(item.get("sort_time") or item.get("record_time")) or "时间未返回",
                    _lab_application_subject(item),
                    _lab_application_item_name(item),
                ),
            )
        )
        for item in ordered
    ]
    content = "当前仅同步到检验申请，检验结果明细尚未同步。\n" + "\n".join(lines)
    latest_time = _safe_text(ordered[-1].get("sort_time") or ordered[-1].get("record_time"))
    summary = {
        **ordered[-1],
        "id": "labtest-master-summary",
        "doc_id": "labtest-master-summary",
        "doc_key": "labtest_master::summary",
        "doc_name": f"检验申请汇总（{len(ordered)}）",
        "document_id": "labtest-master-summary",
        "source_document_ids": [
            _safe_text(item.get("document_id"))
            for item in ordered
            if _safe_text(item.get("document_id"))
        ],
        "document_title": f"检验申请汇总（{len(ordered)}）",
        "sort_time": latest_time,
        "record_time": latest_time,
        "has_content": True,
        "content": content,
        "length": len(content),
        "sections": [],
        "source_fields": [
            {
                "source_field": "application_count",
                "raw_value_preview": str(len(ordered)),
                "used": True,
            }
        ],
    }
    return [item for item in documents if item.get("doc_type") != "labtest_master"] + [summary]


def build_documents_from_domain_bundles(
    domain_bundles: dict[str, dict[str, Any]],
    *,
    include_exam_evidence_coordinates: bool = False,
) -> list[dict[str, Any]]:
    documents: list[dict[str, Any]] = []
    seen_keys: set[str] = set()

    for domain in _DOMAIN_LOAD_ORDER:
        bundle = domain_bundles.get(domain) or {}
        source_documents = list(bundle.get("source_documents") or [])
        for idx, item in enumerate(source_documents):
            if not isinstance(item, dict):
                continue
            normalized = _normalize_source_document(
                raw_doc=item, index=idx, execution_domain=domain,
                include_exam_evidence_coordinates=include_exam_evidence_coordinates,
            )
            key = _safe_text(normalized.get("doc_key"))
            if key and key in seen_keys:
                continue
            if key:
                seen_keys.add(key)
            documents.append(normalized)

    documents = _merge_admission_diagnosis_documents(documents)
    documents = _merge_first_course_diagnosis_documents(documents)
    documents = _merge_discharge_diagnosis_documents(documents)
    documents = _collapse_labtest_master_documents(documents)
    documents.sort(
        key=lambda item: (
            _parse_sort_time(_safe_text(item.get("sort_time"))),
            _safe_text(item.get("doc_name")),
            _safe_text(item.get("doc_key")),
        )
    )
    return documents


def _has_named_diagnosis(doc: dict[str, Any], *, allowed_types: set[str]) -> bool:
    diagnosis_type = ""
    for field in doc.get("source_fields") or []:
        if not isinstance(field, dict):
            continue
        source_field = _safe_text(field.get("source_field")).lower()
        preview = _safe_text(field.get("raw_value_preview"))
        if source_field == "diagnosis_type":
            diagnosis_type = preview
    if diagnosis_type and diagnosis_type not in allowed_types:
        return False

    for field in doc.get("source_fields") or []:
        if not isinstance(field, dict):
            continue
        source_field = _safe_text(field.get("source_field")).lower()
        preview = _safe_text(field.get("raw_value_preview"))
        if source_field in {"diagnosis_name", "diagnosis_code"} and preview:
            return True
    content = _safe_text(doc.get("content"))
    if not diagnosis_type and not any(token in content for token in allowed_types):
        return False
    excluded_types = {"入院诊断", "初步诊断", "出院诊断", "出院主要诊断", "出院其他诊断", "修正诊断", "补充诊断"} - allowed_types
    if any(f"诊断类型: {excluded}" in content for excluded in excluded_types):
        return False
    return "诊断名称:" in content or "诊断编码:" in content


def _diagnosis_field(doc: dict[str, Any], field_name: str) -> str:
    wanted = _safe_text(field_name).lower()
    for field in doc.get("source_fields") or []:
        if not isinstance(field, dict):
            continue
        if _safe_text(field.get("source_field")).lower() == wanted:
            return _safe_text(field.get("raw_value_preview"))
    content = _safe_text(doc.get("content"))
    pattern = re.compile(rf"^{re.escape(_FIELD_LABELS.get(wanted, field_name))}\s*[:：]\s*(.+)$", re.MULTILINE)
    match = pattern.search(content)
    return match.group(1).strip() if match else ""


def _is_main_diagnosis(value: str) -> bool:
    normalized = _safe_text(value).lower()
    return normalized in {"是", "true", "1", "yes", "y", "主诊断"}


def _split_numbered_diagnosis_items(value: str) -> list[str]:
    text = _safe_text(value)
    if not text:
        return []
    matches = re.findall(r"(?:^|[，,；;\s]+)\d+\s*[、.．]\s*([^，,；;\n\r]+)", text)
    items = [item.strip() for item in matches if item.strip()]
    if len(items) >= 2:
        return items
    return []


def _diagnosis_sort_key(doc: dict[str, Any]) -> tuple[int, str, str]:
    raw_no = _diagnosis_field(doc, "diagnosis_no") or _diagnosis_field(doc, "diagnosis_id")
    try:
        no_value = int(raw_no)
    except ValueError:
        no_value = 9999
    return (
        no_value,
        _diagnosis_field(doc, "diagnosis_type"),
        _diagnosis_field(doc, "diagnosis_name") or _diagnosis_field(doc, "diagnosis_code"),
    )


def _format_merged_diagnosis_content(valid_docs: list[dict[str, Any]], *, section_label: str) -> str:
    main_items: list[str] = []
    other_items: list[str] = []
    diagnosis_types: list[str] = []
    diagnosis_times: list[str] = []
    first_diagnosis_fallback = section_label in {"入院记录诊断", "首次病程诊断"}

    for doc in sorted(valid_docs, key=_diagnosis_sort_key):
        diagnosis_type = _diagnosis_field(doc, "diagnosis_type")
        diagnosis_name = _diagnosis_field(doc, "diagnosis_name")
        diagnosis_code = _diagnosis_field(doc, "diagnosis_code")
        diagnosis_main = _diagnosis_field(doc, "diagnosis_main")
        diagnosis_time = _diagnosis_field(doc, "diagnosis_time") or _diagnosis_field(doc, "diagnosis_datetime")
        if diagnosis_type and diagnosis_type not in diagnosis_types:
            diagnosis_types.append(diagnosis_type)
        if diagnosis_time and diagnosis_time not in diagnosis_times:
            diagnosis_times.append(diagnosis_time)

        label = diagnosis_name or diagnosis_code
        if diagnosis_name and diagnosis_code:
            label = f"{diagnosis_name}（{diagnosis_code}）"
        if not label:
            continue
        if _is_main_diagnosis(diagnosis_main):
            main_items.append(label)
        else:
            split_items = _split_numbered_diagnosis_items(label)
            if first_diagnosis_fallback and not main_items and split_items:
                main_items.append(split_items[0])
                other_items.extend(split_items[1:])
            elif first_diagnosis_fallback and not main_items and _diagnosis_sort_key(doc)[0] == 1:
                main_items.append(label)
            else:
                other_items.append(label)

    if not main_items and not other_items:
        return ""

    lines = [section_label]
    if diagnosis_types:
        lines.append(f"诊断类型: {'；'.join(diagnosis_types)}")
    if main_items:
        main_label = "第一诊断" if first_diagnosis_fallback else "主诊断"
        lines.append(f"{main_label}: {'；'.join(main_items)}")
    if other_items:
        lines.append(f"其他诊断: {'；'.join(other_items)}")
    if diagnosis_times:
        lines.append(f"诊断时间: {'；'.join(diagnosis_times)}")
    return "\n".join(lines)


def _merge_record_diagnosis_documents(
    documents: list[dict[str, Any]],
    *,
    diagnosis_doc_type: str,
    parent_doc_type: str,
    section_label: str,
    allowed_types: set[str],
    allow_single_parent_fallback: bool = False,
) -> list[dict[str, Any]]:
    diagnosis_docs = [doc for doc in documents if _safe_text(doc.get("doc_type")) == diagnosis_doc_type]
    if not diagnosis_docs:
        return documents

    valid_docs = [doc for doc in diagnosis_docs if _has_named_diagnosis(doc, allowed_types=allowed_types)]
    other_docs = [doc for doc in documents if _safe_text(doc.get("doc_type")) != diagnosis_doc_type]
    if not valid_docs:
        return other_docs

    content = _format_merged_diagnosis_content(valid_docs, section_label=section_label)
    document_id = _safe_text(valid_docs[0].get("document_id") or valid_docs[0].get("doc_id") or diagnosis_doc_type)
    parent_document_id = document_id.split("::diagnosis::", 1)[0]
    if not content:
        return other_docs

    for doc in other_docs:
        if _safe_text(doc.get("doc_type")) != parent_doc_type:
            continue
        if _safe_text(doc.get("document_id") or doc.get("doc_id")) != parent_document_id:
            continue
        existing_content = _safe_text(doc.get("content"))
        merged_content = f"{existing_content}\n\n{content}".strip() if existing_content else content
        sections = list(doc.get("sections") or [])
        sections.append(
            {
                "section_key": diagnosis_doc_type,
                "section_label": section_label,
                "text": content,
                "source_field": diagnosis_doc_type,
                "order_index": len(sections),
            }
        )
        doc["content"] = merged_content
        doc["length"] = len(merged_content)
        doc["sections"] = sections
        doc["has_content"] = bool(merged_content)
        flags = list(doc.get("data_quality_flags") or [])
        merge_flag = f"merged:{diagnosis_doc_type}"
        if merge_flag not in flags:
            flags.append(merge_flag)
        doc["data_quality_flags"] = flags
        return other_docs

    parent_docs = [doc for doc in other_docs if _safe_text(doc.get("doc_type")) == parent_doc_type]
    if allow_single_parent_fallback and len(parent_docs) == 1:
        doc = parent_docs[0]
        existing_content = _safe_text(doc.get("content"))
        merged_content = f"{existing_content}\n\n{content}".strip() if existing_content else content
        sections = list(doc.get("sections") or [])
        sections.append(
            {
                "section_key": diagnosis_doc_type,
                "section_label": section_label,
                "text": content,
                "source_field": diagnosis_doc_type,
                "order_index": len(sections),
            }
        )
        doc["content"] = merged_content
        doc["length"] = len(merged_content)
        doc["sections"] = sections
        doc["has_content"] = bool(merged_content)
        flags = list(doc.get("data_quality_flags") or [])
        merge_flag = f"merged:{diagnosis_doc_type}"
        fallback_flag = f"merged:{diagnosis_doc_type}:single_parent_fallback"
        for flag in (merge_flag, fallback_flag):
            if flag not in flags:
                flags.append(flag)
        doc["data_quality_flags"] = flags
        return other_docs

    return other_docs


def _merge_admission_diagnosis_documents(documents: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return _merge_record_diagnosis_documents(
        documents,
        diagnosis_doc_type="admission_record_diagnosis",
        parent_doc_type="admission_record",
        section_label="入院记录诊断",
        allowed_types=_ADMISSION_DIAGNOSIS_ALLOWED_TYPES,
    )


def _merge_first_course_diagnosis_documents(documents: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return _merge_record_diagnosis_documents(
        documents,
        diagnosis_doc_type="first_course_record_diagnosis",
        parent_doc_type="first_course_record",
        section_label="首次病程诊断",
        allowed_types=_FIRST_COURSE_DIAGNOSIS_ALLOWED_TYPES,
        allow_single_parent_fallback=True,
    )


def _merge_discharge_diagnosis_documents(documents: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return _merge_record_diagnosis_documents(
        documents,
        diagnosis_doc_type="discharge_record_diagnosis",
        parent_doc_type="discharge_record",
        section_label="出院记录诊断",
        allowed_types=_DISCHARGE_DIAGNOSIS_ALLOWED_TYPES,
        allow_single_parent_fallback=True,
    )


def _documents_include_doc_type(documents: list[dict[str, Any]], doc_type: str) -> bool:
    wanted = _safe_text(doc_type)
    return any(_safe_text(item.get("doc_type") or item.get("source_table")) == wanted for item in documents)


def _course_bundle_needs_exam_lab_refresh(bundle: dict[str, Any] | None) -> bool:
    if not isinstance(bundle, dict):
        return False
    if _safe_text(bundle.get("bundle_schema_version")) != BUNDLE_SCHEMA_VERSION_CURRENT:
        return True
    structured_context = bundle.get("structured_context")
    if not isinstance(structured_context, dict):
        return True
    source_coverage = structured_context.get("source_table_coverage")
    if not isinstance(source_coverage, dict):
        return True
    return not _COURSE_SOURCE_COVERAGE_KEYS.issubset(source_coverage)


def _domain_bundle_needs_projection_refresh(bundle: dict[str, Any] | None) -> bool:
    if not isinstance(bundle, dict):
        return False
    structured_context = bundle.get("structured_context")
    if not isinstance(structured_context, dict):
        return True
    projection = structured_context.get("domain_projection")
    if not isinstance(projection, dict):
        return True
    return not isinstance(projection.get("per_source"), dict)


def _build_domain_projection_summary(
    domain_bundles: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    domains: dict[str, dict[str, Any]] = {}
    for domain, bundle in domain_bundles.items():
        structured_context = bundle.get("structured_context")
        if not isinstance(structured_context, dict):
            continue
        projection = structured_context.get("domain_projection")
        if not isinstance(projection, dict):
            continue
        per_source = projection.get("per_source")
        if not isinstance(per_source, dict):
            continue
        domains[domain] = {
            "projection_kind": "domain_documents",
            "is_evidence_source": False,
            "per_source": per_source,
        }
    return {
        "projection_kind": "domain_documents",
        "is_evidence_source": False,
        "domains": domains,
    }


def build_documents_tree(documents: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_group: dict[str, list[dict[str, Any]]] = {group["key"]: [] for group in _GROUP_DEFS}

    for doc in documents:
        node = {
            "id": _safe_text(doc.get("id") or doc.get("doc_key")),
            "doc_key": _safe_text(doc.get("doc_key")),
            "doc_type": _safe_text(doc.get("doc_type")),
            "document_id": _safe_text(doc.get("document_id")),
            "title": _safe_text(doc.get("doc_name") or doc.get("label")),
            "record_time": _safe_text(doc.get("sort_time") or doc.get("record_time")),
            "has_content": bool(doc.get("has_content")),
            "length": int(doc.get("length") or 0),
            "projection_incomplete": doc.get("projection_incomplete") is True,
            "projection_notice": _safe_text(doc.get("projection_notice")),
        }
        by_group["all"].append(node)
        group_key = _safe_text(doc.get("group_key"))
        if group_key in by_group:
            by_group[group_key].append(node)

    tree: list[dict[str, Any]] = []
    for group in _GROUP_DEFS:
        key = group["key"]
        children = by_group.get(key, [])
        if key == "pdf_supplement" and not children:
            continue
        tree.append(
            {
                "key": key,
                "label": group["label"],
                "count": len(children),
                "children": children,
            }
        )
    return tree


def _normalize_source_document_summary(
    *,
    raw_doc: dict[str, Any],
    index: int,
    execution_domain: str,
) -> dict[str, Any]:
    doc_type = _safe_text(raw_doc.get("document_type") or raw_doc.get("source_table"))
    doc_id = _safe_text(raw_doc.get("document_id"))
    title = _friendly_doc_label(doc_type, _safe_text(raw_doc.get("document_title")))
    sort_time = _safe_text(raw_doc.get("display_time") or raw_doc.get("record_time"))
    submit_time = _safe_text(raw_doc.get("submit_time") or raw_doc.get("submit_datetime"))
    sort_time = sort_time or submit_time
    record_time, record_time_source, record_time_note = _record_display_clock(raw_doc, doc_type, sort_time)
    length = max(0, int(raw_doc.get("length") or 0))
    has_content = raw_doc.get("has_content") is True or length > 0 or bool(_perioperative_display_fields(doc_type, raw_doc))
    summary = {
        "id": doc_id or _build_doc_key(doc_type, doc_id, index),
        "doc_id": doc_id or _build_doc_key(doc_type, doc_id, index),
        "doc_key": _build_doc_key(doc_type, doc_id, index),
        "doc_type": doc_type,
        "doc_name": title,
        "type": doc_type,
        "label": title,
        "document_id": doc_id,
        "document_title": title,
        "sort_time": sort_time,
        "record_time": record_time,
        "submit_time": submit_time,
        "record_time_source": record_time_source,
        "record_time_note": record_time_note,
        "has_content": has_content,
        "length": length,
        "group_key": _infer_group_key(doc_type),
        "execution_domain": execution_domain,
        "projection_incomplete": raw_doc.get("projection_incomplete") is True,
        "projection_notice": _safe_text(raw_doc.get("projection_notice")),
        "source": "bundle",
    }
    for key in (*_MATERIAL_DISPLAY_FIELDS, "exam_evidence_coordinates"):
        if key in raw_doc:
            summary[key] = raw_doc[key]
    if raw_doc.get("version_id") and raw_doc.get("source_record_identity"):
        summary["doc_key"] = f"{doc_type}::{raw_doc['source_record_identity']}::{raw_doc['version_id']}"
        item = raw_doc.get("daily_material", {})
        for key, field in (("material_state", "state"), ("material_selected", "selected"), ("material_rule_usable", "rule_usable")):
            if key not in summary and field in item:
                summary[key] = item[field]
    if raw_doc.get("chief_physician_sign_datetime") is not None:
        summary["chief_physician_sign_datetime"] = _safe_text(raw_doc["chief_physician_sign_datetime"])
    if doc_type in _ORDER_DOC_TYPES:
        for field_name in INDEPENDENT_DOCUMENT_FIELDS[doc_type]:
            if raw_doc.get(field_name) is not None:
                summary[field_name] = raw_doc[field_name]
        summary.update(
            {
                f"order_{key}" if key not in {"order_id", "order_type", "order_item", "order_status"} else key: value
                for key, value in _order_display_values(raw_doc).items()
            }
        )
    return summary


def _collapse_summary_only_documents(documents: list[dict[str, Any]]) -> list[dict[str, Any]]:
    diagnosis_types = {
        "admission_record_diagnosis",
        "first_course_record_diagnosis",
        "discharge_record_diagnosis",
    }
    visible = [doc for doc in documents if doc.get("doc_type") not in diagnosis_types]
    applications = [doc for doc in visible if doc.get("doc_type") == "labtest_master"]
    if len(applications) <= 1:
        return visible
    latest = max(
        applications,
        key=lambda item: (
            _parse_sort_time(_safe_text(item.get("sort_time") or item.get("record_time"))),
            _safe_text(item.get("document_id")),
        ),
    )
    summary = {
        **latest,
        "id": "labtest-master-summary",
        "doc_id": "labtest-master-summary",
        "doc_key": "labtest_master::summary",
        "doc_name": f"检验申请汇总（{len(applications)}）",
        "document_id": "labtest-master-summary",
        "source_document_ids": [
            _safe_text(item.get("document_id"))
            for item in applications
            if _safe_text(item.get("document_id"))
        ],
        "document_title": f"检验申请汇总（{len(applications)}）",
        "has_content": True,
        "length": sum(int(item.get("length") or 0) for item in applications),
    }
    return [doc for doc in visible if doc.get("doc_type") != "labtest_master"] + [summary]


def _restore_grouped_report_coordinates(
    documents: list[dict[str, Any]],
    *,
    doc_type: str,
    rebuilt: list[dict[str, Any]],
) -> None:
    pending = [
        doc for doc in documents
        if doc.get("doc_type") == doc_type and not doc.get("exam_evidence_coordinates")
    ]
    if not pending:
        return
    candidates: dict[str, list[dict[str, Any]]] = {}
    for report in rebuilt:
        candidates.setdefault(report["document_id"], []).append(report)
    for doc in pending:
        matches = candidates.get(doc.get("document_id"), [])
        if len(matches) != 1:
            continue
        report = matches[0]
        if report.get("exam_evidence_coordinates") and all(
            doc.get(field) == report.get(field) for field in ("content", "report_items", "report_metadata")
        ):
            doc["exam_evidence_coordinates"] = report["exam_evidence_coordinates"]


def restore_frozen_exam_evidence_coordinates(
    documents: list[dict[str, Any]], tables: dict[str, Any],
) -> None:
    """只用同份快照的表行补齐旧检查/检验报告坐标，保留当时保存的正文。"""
    if tables.get("exam_item_report") and any(
        doc.get("doc_type") == "exam_item_report" and not doc.get("exam_evidence_coordinates")
        for doc in documents
    ):
        rebuilt_exams, _ = _build_grouped_exam_reports(
            list(tables.get("exam_master") or []),
            list(tables.get("exam_item") or []),
            list(tables["exam_item_report"]),
        )
        _restore_grouped_report_coordinates(
            documents, doc_type="exam_item_report", rebuilt=rebuilt_exams,
        )
    if tables.get("labtest_item_report") and any(
        doc.get("doc_type") == "labtest_item_report" and not doc.get("exam_evidence_coordinates")
        for doc in documents
    ):
        rebuilt_labs, _ = _build_grouped_lab_reports(
            list(tables.get("labtest_master") or []),
            list(tables["labtest_item_report"]),
        )
        _restore_grouped_report_coordinates(
            documents, doc_type="labtest_item_report", rebuilt=rebuilt_labs,
        )


def summarize_frozen_documents(*, documents: list[dict[str, Any]], execution_domain: str | None = None, daily_material_status=None, primary_material_status=None) -> dict[str, Any]:
    """沿原摘要owner投影冻结材料；目录响应不携带完整正文/章节/渲染块。"""
    summaries = []
    for index, document in enumerate(documents):
        domain = str(document.get("execution_domain") or "")
        if execution_domain and domain and execution_domain != domain:
            continue
        raw = {**document, "document_type": document.get("doc_type") or document.get("document_type"),
               "document_title": document.get("document_title") or document.get("doc_name"),
               "document_id": document.get("document_id") or document.get("id"),
               "display_time": document.get("sort_time"), "length": len(str(document.get("content") or ""))}
        summary = _normalize_source_document_summary(raw_doc=raw, index=index, execution_domain=domain)
        for key in ("id", "doc_id", "doc_key", "document_id", "source_ref", "source_document_id", "source_document_aliases"):
            if document.get(key) is not None:
                summary[key] = document[key]
        summaries.append(summary)
    return {"daily_material_status":daily_material_status, "primary_material_status":primary_material_status, "layout_version":"bundle_struct_v1", "documents":summaries, "documents_tree":[],
            "empty_reason":"" if summaries else "material_documents_empty"}


def load_bundle_document_summaries(
    *,
    institute_id: str,
    patient_id: str,
    visit_id: str,
    bundle_schema: str = "public",
    execution_domain: str | None = None,
) -> dict[str, Any]:
    documents: list[dict[str, Any]] = []
    domain_hits: dict[str, bool] = {}
    seen_keys: set[str] = set()
    domains = (
        (execution_domain,)
        if execution_domain in _DOMAIN_LOAD_ORDER
        else _DOMAIN_LOAD_ORDER
    )
    for domain in domains:
        bundle = load_domain_bundle_document_index(
            execution_domain=domain,
            institute_id=institute_id,
            patient_id=patient_id,
            visit_id=visit_id,
            schema=bundle_schema,
        )
        domain_hits[domain] = bool(bundle)
        if not bundle:
            continue
        for index, item in enumerate(bundle.get("source_documents") or []):
            if not isinstance(item, dict):
                continue
            summary = _normalize_source_document_summary(
                raw_doc=item,
                index=index,
                execution_domain=domain,
            )
            key = _safe_text(summary.get("doc_key"))
            if key and key in seen_keys:
                continue
            if key:
                seen_keys.add(key)
            documents.append(summary)
    documents = _collapse_summary_only_documents(documents)
    documents.sort(
        key=lambda item: (
            _parse_sort_time(_safe_text(item.get("sort_time"))),
            _safe_text(item.get("doc_name")),
            _safe_text(item.get("doc_key")),
        )
    )
    return {
        "layout_version": "bundle_struct_v1",
        "documents": documents,
        # 前端可由同一份摘要构建分组；不在响应中重复 1,000+ 个目录节点。
        "documents_tree": [],
        "domain_bundle_hits": domain_hits,
        "empty_reason": "" if documents else "bundle_documents_empty",
    }


def load_bundle_document(
    *,
    institute_id: str,
    patient_id: str,
    visit_id: str,
    execution_domain: str,
    doc_type: str,
    doc_id: str,
    bundle_schema: str = "public",
) -> dict[str, Any] | None:
    if execution_domain not in _DOMAIN_LOAD_ORDER:
        return None
    bundle = load_domain_bundle_for_emr_render(
        execution_domain=execution_domain,
        institute_id=institute_id,
        patient_id=patient_id,
        visit_id=visit_id,
        doc_type=doc_type,
        doc_id=doc_id,
        schema=bundle_schema,
    )
    if not bundle:
        return None
    documents = build_documents_from_domain_bundles({execution_domain: bundle})
    return pick_document(documents=documents, doc_type=doc_type, doc_id=doc_id)


def load_bundle_documents(
    *,
    institute_id: str,
    patient_id: str,
    visit_id: str,
    bundle_schema: str = "public",
    include_exam_evidence_coordinates: bool = False,
) -> dict[str, Any]:
    domain_bundles: dict[str, dict[str, Any]] = {}
    domain_hits: dict[str, bool] = {}
    for domain in _DOMAIN_LOAD_ORDER:
        try:
            payload = load_domain_bundle(
                execution_domain=domain,
                institute_id=institute_id,
                patient_id=patient_id,
                visit_id=visit_id,
                schema=bundle_schema,
            )
        except Exception:
            payload = None
        domain_hits[domain] = bool(payload)
        if payload:
            domain_bundles[domain] = payload

    for domain, bundle in tuple(domain_bundles.items()):
        if not _domain_bundle_needs_projection_refresh(bundle):
            continue
        try:
            refreshed_bundle = load_or_assemble_domain_bundle(
                execution_domain=domain,
                institute_id=institute_id,
                patient_id=patient_id,
                visit_id=visit_id,
                bundle_schema=bundle_schema,
                force_refresh=True,
            )
        except Exception:
            refreshed_bundle = None
        if refreshed_bundle:
            domain_bundles[domain] = refreshed_bundle
            domain_hits[f"{domain}_projection_refresh"] = True

    course_bundle = domain_bundles.get("course")
    if _course_bundle_needs_exam_lab_refresh(course_bundle):
        try:
            refreshed_course_bundle = load_or_assemble_domain_bundle(
                execution_domain="course",
                institute_id=institute_id,
                patient_id=patient_id,
                visit_id=visit_id,
                bundle_schema=bundle_schema,
                force_refresh=True,
            )
        except Exception:
            refreshed_course_bundle = None
        if refreshed_course_bundle:
            domain_bundles["course"] = refreshed_course_bundle
            domain_hits["course_runtime_refresh"] = True

    documents = build_documents_from_domain_bundles(
        domain_bundles, include_exam_evidence_coordinates=include_exam_evidence_coordinates,
    )
    if not _documents_include_doc_type(documents, "admission_record_diagnosis"):
        try:
            admission_bundle = assemble_domain_bundle(
                execution_domain="admission",
                institute_id=institute_id,
                patient_id=patient_id,
                visit_id=visit_id,
            )
        except Exception:
            admission_bundle = None
        if admission_bundle and any(
            _safe_text(item.get("document_type") or item.get("source_table")) == "admission_record_diagnosis"
            for item in admission_bundle.get("source_documents") or []
        ):
            domain_bundles["admission"] = admission_bundle
            domain_hits["admission_runtime_overlay"] = True
            documents = build_documents_from_domain_bundles(
                domain_bundles, include_exam_evidence_coordinates=include_exam_evidence_coordinates,
            )
    if not _documents_include_doc_type(documents, "discharge_record_diagnosis"):
        try:
            terminal_bundle = assemble_domain_bundle(
                execution_domain="terminal",
                institute_id=institute_id,
                patient_id=patient_id,
                visit_id=visit_id,
            )
        except Exception:
            terminal_bundle = None
        if terminal_bundle and any(
            _safe_text(item.get("document_type") or item.get("source_table")) == "discharge_record_diagnosis"
            for item in terminal_bundle.get("source_documents") or []
        ):
            domain_bundles["terminal"] = terminal_bundle
            domain_hits["terminal_runtime_overlay"] = True
            documents = build_documents_from_domain_bundles(
                domain_bundles, include_exam_evidence_coordinates=include_exam_evidence_coordinates,
            )
    tree = build_documents_tree(documents)
    return {
        "layout_version": "bundle_struct_v1",
        "documents": documents,
        "documents_tree": tree,
        "domain_projection": _build_domain_projection_summary(domain_bundles),
        "domain_bundle_hits": domain_hits,
        "empty_reason": "" if documents else "bundle_documents_empty",
    }


def pick_document(
    *,
    documents: list[dict[str, Any]],
    doc_type: str = "",
    doc_id: str = "",
) -> dict[str, Any] | None:
    wanted_id = _safe_text(doc_id)
    wanted_type = _safe_text(doc_type)

    if wanted_id and any(doc.get("version_id") for doc in documents):
        matches = [doc for doc in documents if (not wanted_type or _safe_text(doc.get("doc_type")) == wanted_type)
                   and wanted_id in {_safe_text(doc.get(key)) for key in ("id", "doc_id", "document_id", "doc_key")}]
        if len(matches) != 1:
            return None
        return matches[0]

    if wanted_id:
        if wanted_type:
            for doc in documents:
                if _safe_text(doc.get("doc_type")) != wanted_type:
                    continue
                if wanted_id in {
                    _safe_text(doc.get("id")),
                    _safe_text(doc.get("doc_id")),
                    _safe_text(doc.get("document_id")),
                    _safe_text(doc.get("doc_key")),
                }:
                    return doc
        for doc in documents:
            if wanted_id in {
                _safe_text(doc.get("id")),
                _safe_text(doc.get("doc_id")),
                _safe_text(doc.get("document_id")),
                _safe_text(doc.get("doc_key")),
            }:
                return doc

    if wanted_type:
        for doc in documents:
            if _safe_text(doc.get("doc_type")) == wanted_type:
                return doc

    for doc in documents:
        if doc.get("has_content"):
            return doc

    return documents[0] if documents else None


def _extract_kv_fields(document: dict[str, Any]) -> list[dict[str, str]]:
    if document.get("doc_type") == "surgery_record" and not _safe_text(document.get("content")):
        return []
    source_fields = list(document.get("source_fields") or [])
    fields: list[dict[str, str]] = []
    seen: set[str] = set()
    doc_type = _safe_text(document.get("doc_type"))
    surgery_mode = doc_type in _SURGERY_STRUCT_DOC_TYPES
    if not _safe_text(document.get("content")):
        structured_fields = _perioperative_display_fields(doc_type, document)
        if structured_fields:
            return structured_fields

    for item in source_fields:
        if not isinstance(item, dict):
            continue
        used = bool(item.get("used"))
        preview = _safe_text(item.get("raw_value_preview"))
        source_field = _safe_text(item.get("source_field"))
        if _should_skip_template_source_field(source_field):
            continue
        if not used or not preview or not source_field:
            continue
        if source_field in seen:
            continue
        seen.add(source_field)
        fields.append(
            {
                "key": source_field,
                "label": _friendly_field_label(source_field),
                "value": preview,
            }
        )

    if fields and (not surgery_mode or doc_type == "surgery_record"):
        return fields

    content = _safe_text(document.get("content"))
    if not content:
        if fields:
            return fields
        if surgery_mode:
            return _fallback_surgery_template_fields()
        return fields

    parsed = _extract_kv_from_content(
        content,
        max_fields=28 if surgery_mode else 16,
        keep_empty_value=surgery_mode,
    )
    if parsed:
        return parsed
    if fields:
        return fields
    if surgery_mode:
        return _fallback_surgery_template_fields()
    return fields


def _build_order_table_block(document: dict[str, Any]) -> dict[str, Any]:
    values = _order_display_values(document)
    rows = [values] if any(values.values()) else []
    return {
        "block_id": f"{_safe_text(document.get('doc_key'))}:order_table",
        "block_type": "order_table",
        "title": "医嘱",
        "columns": [
            {"key": "start_time", "label": "开始时间"},
            {"key": "order_type", "label": "医嘱类型"},
            {"key": "order_item", "label": "医嘱项目"},
            {"key": "order_id", "label": "医嘱号"},
            {"key": "specification", "label": "规格"},
            {"key": "dosage", "label": "剂量"},
            {"key": "frequency", "label": "频次"},
            {"key": "route", "label": "用法"},
            {"key": "quantity", "label": "数量"},
            {"key": "planned_end_time", "label": "计划结束时间"},
            {"key": "stop_time", "label": "实际停止时间"},
            {"key": "order_status", "label": "医嘱状态"},
            {"key": "prescribed_doctor", "label": "下达医生"},
        ],
        "rows": rows,
        "order_mode": "long_term" if _safe_text(document.get("doc_type")) == "inpat_drug_order" else "temporary",
        "empty": len(rows) == 0,
        "empty_text": "暂无医嘱数据",
    }


def _order_source_values(document: dict[str, Any]) -> dict[str, str]:
    values: dict[str, str] = {}
    for field in list(document.get("source_fields") or []):
        if not isinstance(field, dict):
            continue
        key = _safe_text(field.get("source_field")).lower()
        value = _safe_text(field.get("raw_value_preview"))
        if key and value and key not in values:
            values[key] = value
    return values


def _order_value(document: dict[str, Any], source_values: dict[str, str], *names: str) -> str:
    for name in names:
        direct = _safe_text(document.get(name))
        if direct:
            return direct
        source = source_values.get(name)
        if source:
            return source
    return ""


def _join_order_value(value: str, unit: str) -> str:
    if value and unit:
        return f"{value}{unit}"
    return value or unit


def _order_display_values(document: dict[str, Any]) -> dict[str, str]:
    source_values = _order_source_values(document)
    order_type = _order_value(document, source_values, "order_type", "order_class")
    order_item = _order_value(
        document,
        source_values,
        "order_item",
        "order_item_name",
        "drug_name",
        "generic_name",
        "brand_name",
        "item_name",
        "order_name",
    )
    # 目录规范化后的字段已包含单位，详情再次渲染时不能重复追加。
    dosage = _order_value(document, source_values, "order_dosage")
    if not dosage:
        dosage = _join_order_value(
            _order_value(document, source_values, "dosage", "dose", "single_dose"),
            _order_value(document, source_values, "dose_unit", "single_dose_unit"),
        )
    quantity = _order_value(document, source_values, "order_quantity")
    if not quantity:
        quantity = _join_order_value(
            _order_value(document, source_values, "quantity"),
            _order_value(document, source_values, "quantity_unit"),
        )
    return {
        "start_time": _order_value(
            document, source_values, "planned_start_datetime", "order_start_time", "start_time", "order_time", "prescribed_datetime"
        ),
        "order_type": order_type,
        "order_item": order_item,
        "order_id": _order_value(document, source_values, "order_id"),
        "specification": _order_value(
            document, source_values, "order_specification", "specification", "drug_specification"
        ),
        "dosage": dosage,
        "frequency": _order_value(document, source_values, "order_frequency", "drug_frequency", "frequency"),
        "route": _order_value(document, source_values, "order_route", "drug_apply_method", "route"),
        "quantity": quantity,
        "planned_end_time": _order_value(
            document, source_values, "order_planned_end_time", "planned_end_time", "planned_end_datetime"
        ),
        "stop_time": _order_value(document, source_values, "order_stop_time", "stop_time"),
        "order_status": _order_value(document, source_values, "order_status", "status"),
        "prescribed_doctor": _order_value(
            document, source_values, "order_prescribed_doctor", "prescribed_doctor", "doctor_name"
        ),
    }


def _build_paragraph_blocks(document: dict[str, Any]) -> list[dict[str, Any]]:
    blocks: list[dict[str, Any]] = []
    sections = list(document.get("sections") or [])
    if sections:
        seen_text: dict[str, int] = {}
        for idx, section in enumerate(sections):
            if not isinstance(section, dict):
                continue
            text = _safe_text(section.get("text"))
            normalized_text = re.sub(r"\s+", "", text)
            if normalized_text and normalized_text in seen_text:
                # 部分源系统同时返回结构化章节和“正文”投影；两者可能是同一段正文。
                # 只保留一次，避免查看病历时把同一文书显示成两份。
                continue
            if normalized_text:
                seen_text[normalized_text] = idx
            blocks.append(
                {
                    "block_id": f"{_safe_text(document.get('doc_key'))}:paragraph:{idx}",
                    "block_type": "paragraph",
                    "title": _safe_text(section.get("section_label")) or "正文",
                    "text": text,
                    "source_field": _safe_text(section.get("source_field")),
                    "empty": not bool(text),
                }
            )
    else:
        text = _safe_text(document.get("content"))
        blocks.append(
            {
                "block_id": f"{_safe_text(document.get('doc_key'))}:paragraph:0",
                "block_type": "paragraph",
                "title": "正文",
                "text": text,
                "source_field": "",
                "empty": not bool(text),
            }
        )
    return blocks


def _structured_fields_cover_content(fields: list[dict[str, str]], content: str) -> bool:
    """判断结构化字段是否已经完整表达正文，避免同一内容渲染两次。"""
    if not fields or not content:
        return False
    structured = "\n".join(
        f"{_safe_text(field.get('label'))}：{_safe_text(field.get('value'))}"
        for field in fields
        if _safe_text(field.get("label")) and _safe_text(field.get("value"))
    )
    normalize = lambda value: re.sub(r"\s+", "", _safe_text(value))
    return bool(structured) and normalize(structured) == normalize(content)


def _build_highlight_anchors(
    *,
    content: str,
    render_blocks: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    anchors: list[dict[str, Any]] = []
    cursor = 0
    for block in render_blocks:
        block_type = _safe_text(block.get("block_type"))
        block_id = _safe_text(block.get("block_id"))
        if block_type == "kv_section":
            for field in list(block.get("fields") or []):
                if not isinstance(field, dict):
                    continue
                value = _safe_text(field.get("value"))
                if not value:
                    continue
                start = content.find(value)
                end = start + len(value) if start >= 0 else -1
                anchors.append(
                    {
                        "anchor_id": f"{block_id}:{_safe_text(field.get('key'))}",
                        "anchor_type": "field",
                        "block_id": block_id,
                        "field_key": _safe_text(field.get("key")),
                        "start_offset": start,
                        "end_offset": end,
                        "text_preview": value[:80],
                    }
                )
        elif block_type == "paragraph":
            text = _safe_text(block.get("text"))
            start = content.find(text, cursor) if text else -1
            if start >= 0:
                cursor = start + len(text)
            end = start + len(text) if start >= 0 else -1
            anchors.append(
                {
                    "anchor_id": block_id,
                    "anchor_type": "paragraph",
                    "block_id": block_id,
                    "field_key": _safe_text(block.get("source_field")),
                    "start_offset": start,
                    "end_offset": end,
                    "text_preview": text[:80],
                }
            )
    return anchors


def build_render_view(document: dict[str, Any] | None) -> dict[str, Any]:
    if not document:
        empty_blocks = [
            {
                "block_id": "empty:paragraph",
                "block_type": "paragraph",
                "title": "文书内容",
                "text": "",
                "source_field": "",
                "empty": True,
                "empty_text": "当前病历暂无可展示内容",
            }
        ]
        return {
            "layout_version": "bundle_struct_v1",
            "content": "",
            "content_type": "text",
            "document_meta": {
                "doc_type": "",
                "doc_name": "病历文书",
                "doc_id": "",
                "source": "bundle",
            },
            "render_blocks": empty_blocks,
            "highlight_anchors": [],
            "empty_reason": "document_not_found",
        }

    content = _safe_text(document.get("content"))
    doc_key = _safe_text(document.get("doc_key"))
    group_key = _safe_text(document.get("group_key"))
    doc_type = _safe_text(document.get("doc_type"))
    doc_name = _safe_text(document.get("doc_name") or document.get("label"))
    doc_id = _safe_text(document.get("id") or document.get("document_id"))

    render_blocks: list[dict[str, Any]] = []
    kv_fields: list[dict[str, str]] = []
    has_paragraph_sections = any(
        isinstance(section, dict) and _safe_text(section.get("text"))
        for section in list(document.get("sections") or [])
    )
    if group_key == "orders" or doc_type in _ORDER_DOC_TYPES:
        render_blocks.append(_build_order_table_block(document))
    elif (
        doc_type not in _PARAGRAPH_ONLY_DOC_TYPES
        and (doc_type in _SURGERY_STRUCT_DOC_TYPES or not has_paragraph_sections)
    ):
        # 普通叙事文书的 sections 已包含完整字段正文；source_fields 只有截断预览。
        # 二者同时渲染会形成“基础信息截断版 + 完整章节”的视觉重复。
        # 手术类结构化文书仍保留专用字段视图。
        kv_fields = _extract_kv_fields(document)
        render_blocks.append(
            {
                "block_id": f"{doc_key}:kv",
                "block_type": "kv_section",
                "title": _KV_TITLE_BY_DOC_TYPE.get(doc_type, "基础信息"),
                "fields": kv_fields,
                "empty": len(kv_fields) == 0,
            }
        )

    should_append_paragraph = not (
        doc_type in _SURGERY_STRUCT_DOC_TYPES
        and (
            len(kv_fields) >= 6
            or _structured_fields_cover_content(kv_fields, content)
        )
    )
    if should_append_paragraph:
        render_blocks.extend(_build_paragraph_blocks(document))
    anchors = _build_highlight_anchors(content=content, render_blocks=render_blocks)
    return {
        "layout_version": "bundle_struct_v1",
        "content": content,
        "content_type": "text",
        "document_meta": {
            "doc_type": doc_type,
            "doc_name": doc_name or _DOC_TYPE_LABELS.get(doc_type, "病历文书"),
            "doc_id": doc_id,
            "document_id": _safe_text(document.get("document_id")),
            "doc_key": doc_key,
            "group_key": group_key,
            "record_time": _safe_text(document.get("sort_time") or document.get("record_time")),
            "submit_time": _safe_text(document.get("submit_time")),
            "record_time_source": _safe_text(document.get("record_time_source")),
            "document_status": document.get("document_status"),
            "authors": list(document.get("authors") or []),
            "signatures": list(document.get("signatures") or []),
            "chief_physician_sign_datetime": _safe_text(document.get("chief_physician_sign_datetime")),
            "projection_incomplete": document.get("projection_incomplete") is True,
            "projection_notice": _safe_text(document.get("projection_notice")),
            **{key: document[key] for key in _MATERIAL_DISPLAY_FIELDS if key in document},
            "source": "bundle",
        },
        "render_blocks": render_blocks,
        "highlight_anchors": anchors,
        "empty_reason": "" if content or any(not bool(block.get("empty")) for block in render_blocks) else "document_empty",
    }
