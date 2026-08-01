from __future__ import annotations

from datetime import datetime
import re
from typing import Any

from .assembly import assemble_domain_bundle, load_domain_bundle, load_or_assemble_domain_bundle
from .contracts import BUNDLE_SCHEMA_VERSION_CURRENT

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
    "preoperative_diagnosis": "术前诊断",
    "intraoperative_diagnosis": "术中诊断",
    "postoperative_diagnosis": "术后诊断",
    "surgery_process": "手术经过",
    "surgical_incisionheal_level": "切口愈合等级",
    "surgery_begin_time": "手术开始时间",
    "surgery_end_time": "手术结束时间",
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
    for line in content.splitlines():
        raw = _safe_text(line)
        if not raw:
            continue
        matched = re.match(r"^([^:：]{1,36})[:：]\s*(.*)$", raw)
        if not matched:
            continue
        key = matched.group(1).strip()
        value = matched.group(2).strip()
        if not key:
            continue
        if (not keep_empty_value) and (not value):
            continue
        norm_key = key.replace(" ", "_").lower()
        if norm_key in seen:
            continue
        seen.add(norm_key)
        fields.append({"key": norm_key, "label": key, "value": value})
        if len(fields) >= max_fields:
            break
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


def _normalize_source_document(
    *,
    raw_doc: dict[str, Any],
    index: int,
    execution_domain: str,
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
    source_record_time = _safe_text(raw_doc.get("record_time"))
    record_time_note = ""
    can_use_display_time_as_record_time = doc_type in _RECORD_TIME_FALLBACK_DOC_TYPES
    if can_use_display_time_as_record_time and not source_record_time and sort_time:
        record_time_note = "源库未返回记录时间，当前使用提交时间、最后修改时间或更新时间等可用时间显示。"
    group_key = _infer_group_key(doc_type)
    label = _friendly_doc_label(doc_type, doc_title)
    doc_key = _build_doc_key(doc_type, doc_id, index)
    normalized_id = doc_id or doc_key

    sections = list(raw_doc.get("sections") or [])
    source_fields = list(raw_doc.get("source_fields") or [])
    return {
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
        "record_time": source_record_time or (sort_time if can_use_display_time_as_record_time else ""),
        "record_time_source": "source_record_time"
        if source_record_time
        else ("fallback_display_time" if can_use_display_time_as_record_time and sort_time else ""),
        "record_time_note": record_time_note,
        "has_content": bool(content),
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
        "source": "bundle",
    }


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
) -> list[dict[str, Any]]:
    documents: list[dict[str, Any]] = []
    seen_keys: set[str] = set()

    for domain in _DOMAIN_LOAD_ORDER:
        bundle = domain_bundles.get(domain) or {}
        source_documents = list(bundle.get("source_documents") or [])
        for idx, item in enumerate(source_documents):
            if not isinstance(item, dict):
                continue
            normalized = _normalize_source_document(raw_doc=item, index=idx, execution_domain=domain)
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


def build_documents_tree(documents: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_group: dict[str, list[dict[str, Any]]] = {group["key"]: [] for group in _GROUP_DEFS}

    for doc in documents:
        node = {
            "id": _safe_text(doc.get("id") or doc.get("doc_key")),
            "doc_key": _safe_text(doc.get("doc_key")),
            "doc_type": _safe_text(doc.get("doc_type")),
            "title": _safe_text(doc.get("doc_name") or doc.get("label")),
            "record_time": _safe_text(doc.get("sort_time") or doc.get("record_time")),
            "has_content": bool(doc.get("has_content")),
            "length": int(doc.get("length") or 0),
        }
        by_group["all"].append(node)
        group_key = _safe_text(doc.get("group_key"))
        if group_key in by_group:
            by_group[group_key].append(node)

    tree: list[dict[str, Any]] = []
    for group in _GROUP_DEFS:
        key = group["key"]
        children = by_group.get(key, [])
        tree.append(
            {
                "key": key,
                "label": group["label"],
                "count": len(children),
                "children": children,
            }
        )
    return tree


def load_bundle_documents(
    *,
    institute_id: str,
    patient_id: str,
    visit_id: str,
    bundle_schema: str = "public",
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

    documents = build_documents_from_domain_bundles(domain_bundles)
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
            documents = build_documents_from_domain_bundles(domain_bundles)
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
            documents = build_documents_from_domain_bundles(domain_bundles)
    tree = build_documents_tree(documents)
    return {
        "layout_version": "bundle_struct_v1",
        "documents": documents,
        "documents_tree": tree,
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
    source_fields = list(document.get("source_fields") or [])
    fields: list[dict[str, str]] = []
    seen: set[str] = set()
    doc_type = _safe_text(document.get("doc_type"))
    surgery_mode = doc_type in _SURGERY_STRUCT_DOC_TYPES

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

    if fields and not surgery_mode:
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
    rows_payload = list(document.get("order_rows") or [])
    rows: list[dict[str, str]] = []
    for row in rows_payload:
        if not isinstance(row, dict):
            continue
        rows.append(
            {
                "start_time": _safe_text(row.get("start_time") or row.get("order_time")),
                "order_type": _safe_text(row.get("order_type") or row.get("type")),
                "order_item": _safe_text(row.get("order_item") or row.get("item_name")),
            }
        )
    return {
        "block_id": f"{_safe_text(document.get('doc_key'))}:order_table",
        "block_type": "order_table",
        "title": "医嘱",
        "columns": [
            {"key": "start_time", "label": "开始时间"},
            {"key": "order_type", "label": "医嘱类型"},
            {"key": "order_item", "label": "医嘱项目"},
        ],
        "rows": rows,
        "order_mode": "long_term" if _safe_text(document.get("doc_type")) == "inpat_drug_order" else "temporary",
        "empty": len(rows) == 0,
        "empty_text": "暂无医嘱数据",
    }


def _build_paragraph_blocks(document: dict[str, Any]) -> list[dict[str, Any]]:
    blocks: list[dict[str, Any]] = []
    sections = list(document.get("sections") or [])
    if sections:
        for idx, section in enumerate(sections):
            if not isinstance(section, dict):
                continue
            text = _safe_text(section.get("text"))
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
    if group_key == "orders" or doc_type in _ORDER_DOC_TYPES:
        render_blocks.append(_build_order_table_block(document))
    else:
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
        doc_type in _SURGERY_STRUCT_DOC_TYPES and len(kv_fields) >= 6
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
            "doc_key": doc_key,
            "group_key": group_key,
            "record_time": _safe_text(document.get("sort_time") or document.get("record_time")),
            "source": "bundle",
        },
        "render_blocks": render_blocks,
        "highlight_anchors": anchors,
        "empty_reason": "" if content or any(not bool(block.get("empty")) for block in render_blocks) else "document_empty",
    }
