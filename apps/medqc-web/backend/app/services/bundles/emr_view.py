from __future__ import annotations

from datetime import datetime
import re
from typing import Any

from .assembly import load_domain_bundle

_DOMAIN_LOAD_ORDER: tuple[str, ...] = (
    "admission",
    "course",
    "surgery",
    "consult_discussion",
    "terminal",
    "index_coding_settlement",
)

_GROUP_DEFS: tuple[dict[str, str], ...] = (
    {"key": "all", "label": "全部"},
    {"key": "frontpage", "label": "病案首页(临床医生)"},
    {"key": "admission", "label": "入院记录"},
    {"key": "course", "label": "病程记录"},
    {"key": "surgery", "label": "手术相关单据"},
    {"key": "terminal", "label": "出院记录"},
    {"key": "orders", "label": "医嘱"},
)

_DOC_TYPE_LABELS: dict[str, str] = {
    "admission_record": "入院记录",
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
    "first_course_record": "course",
    "daily_course_record": "course",
    "senior_course_record": "course",
    "rescue_record": "course",
    "consultation_record": "course",
    "surgery_record": "surgery",
    "anesthesia_record": "surgery",
    "presurg_discussion": "surgery",
    "presurg_summary": "surgery",
    "postsurg_firstcourse_record": "surgery",
    "surgery_safecheck_record": "surgery",
    "consent_form": "surgery",
    "discharge_record": "terminal",
    "death_record": "terminal",
    "death_discussion": "terminal",
    "inpat_drug_order": "orders",
    "inpat_nondrug_order": "orders",
}

_ORDER_DOC_TYPES = {"inpat_drug_order", "inpat_nondrug_order"}
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
        "record_time": _safe_text(raw_doc.get("record_time")),
        "has_content": bool(content),
        "content": content or None,
        "length": len(content),
        "group_key": group_key,
        "execution_domain": execution_domain,
        "sections": sections,
        "source_fields": source_fields,
        "assembly_status": _safe_text(raw_doc.get("assembly_status")),
        "data_quality_flags": list(raw_doc.get("data_quality_flags") or []),
        "source": "bundle",
    }


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

    documents.sort(
        key=lambda item: (
            _parse_sort_time(_safe_text(item.get("sort_time"))),
            _safe_text(item.get("doc_name")),
            _safe_text(item.get("doc_key")),
        )
    )
    return documents


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
