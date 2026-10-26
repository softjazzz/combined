"""PDF验证材料的纯映射：不连接数据库，不运行模型，不按患者或病例特判。"""

from __future__ import annotations

import copy
import hashlib
import json
import re
import uuid
from typing import Any

from refine_pdf_supplement import signatures

COORDINATES = ("institute_id", "patient_id", "visit_id")
# 这些是临床实体关联，不包含医师、科室、药品编码及证件号码。
BUSINESS_IDS = frozenset({
    "document_id", "order_id", "test_id", "test_item_id", "test_no", "report_id", "exam_id",
    "application_id", "group_id", "pathology_exam_id", "pathology_id", "diagnosis_id",
    "surgery_id", "bloodtrans_id", "icu_id", "bill_item_id", "prescription_id",
    "prescription_item_id", "medinsur_receipt_id", "medinsur_serial_item_id",
})


def digest(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, default=str,
                                    separators=(",", ":")).encode()).hexdigest()


def new_id(namespace: str, kind: str, value: str) -> str:
    return str(uuid.uuid5(uuid.UUID(namespace), kind+":"+value))


def normalized_key(key: str) -> str:
    return re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", key).lower()


def identity_map(*, batch_id: str, case: dict, rows: dict[str, list[dict]], catalog: dict) -> dict:
    keys = set(BUSINESS_IDS)
    for name, info in catalog.items():
        if rows.get(name):
            keys.update(set(info["primary_key"]) - set(COORDINATES))
    values = {str(value) for records in rows.values() for row in records for key,value in row.items()
              if key in keys and value is not None and str(value).strip()}
    result = {"institute_id": case["institute_id"],
              "patient_id": "pdfp_"+new_id(batch_id, "patient", case["institute_id"]+":"+case["patient_id"]).replace("-", "")[:24],
              "visit_id": "pdfv_"+new_id(batch_id, "visit", ":".join(str(case[k]) for k in COORDINATES)).replace("-", "")[:24],
              "id_fields": sorted(keys),
              "entities": {value:new_id(batch_id, "entity", ":".join(str(case[k]) for k in COORDINATES)+":"+value) for value in sorted(values)}}
    return result


def map_json(value: Any, mapping: dict, source: dict, key: str = "") -> Any:
    if isinstance(value, dict):
        mapped = {}
        for child_key, child in value.items():
            # JSON对象以真实编号作键时也需保留关联，短数字键可能是数组式序号，不改。
            out_key = mapping["entities"].get(child_key, child_key) if len(child_key) >= 8 else child_key
            mapped[out_key] = map_json(child, mapping, source, child_key)
        return mapped
    if isinstance(value, list):
        return [map_json(child, mapping, source, key) for child in value]
    normalized = normalized_key(key)
    normalized = normalized[:-1] if normalized.endswith("_ids") else normalized
    if normalized in ("patient_id", "visit_id") and value is not None:
        if str(value) != str(source[normalized]):
            raise ValueError("foreign_case_reference_in_json")
        return mapping[normalized]
    if normalized in mapping["id_fields"] and value is not None and str(value).strip():
        if str(value) not in mapping["entities"]:
            raise ValueError("unresolved_local_entity_reference_in_json")
        return mapping["entities"][str(value)]
    return value


def clone_rows(rows: dict, *, case: dict, mapping: dict, catalog: dict) -> dict:
    result = {}
    for table, records in rows.items():
        output = []
        for original in records:
            if str(original.get("institute_id")) != str(case["institute_id"]):
                raise ValueError("source_row_institute_mismatch")
            row = copy.deepcopy(original)
            for key,value in list(row.items()):
                if key in ("patient_id", "visit_id"):
                    if str(value) != str(case[key]):
                        raise ValueError("source_row_case_identity_mismatch")
                    row[key] = mapping[key]
                elif key in mapping["id_fields"] and value is not None and str(value).strip():
                    row[key] = mapping["entities"][str(value)]
                elif catalog[table]["columns"][key]["type"] in ("json", "jsonb"):
                    row[key] = map_json(value, mapping, case)
                elif key == "v2_schema" and isinstance(value, str) and value.strip():
                    try:
                        parsed = json.loads(value)
                    except ValueError:
                        raise ValueError("invalid_source_v2_schema") from None
                    row[key] = json.dumps(map_json(parsed, mapping, case), ensure_ascii=False)
            output.append(row)
        result[table] = output
    return result


def validate_column_lengths(rows: dict, catalog: dict) -> None:
    # jsonb_populate_recordset 的显式varchar转换可能截断；必须在交给PG前拒绝超长。
    for table,records in rows.items():
        for row in records:
            for key,value in row.items():
                length = catalog[table]["columns"][key].get("length")
                if value is not None and length is not None and len(str(value)) > length:
                    raise ValueError("mapped_value_exceeds_target_column_length")


def apply_documents(*, documents: list[dict], rows: dict, source_rows: dict, mapping: dict,
                    catalog: dict, common: dict, batch_id: str) -> list[dict]:
    """只在新副本中补空字段或新增明确类型，版本差异仍是非活动候选。"""
    provenance = []
    for doc in documents:
        verdict = doc["refinement"]
        action = verdict["action"]
        table = verdict["proposed_table"]
        linked = verdict["matches"][0]["document_id"] if verdict["matches"] else None
        target_id = mapping["entities"].get(str(linked)) if linked is not None else None
        if action == "new_candidate":
            if table not in catalog or not doc.get("record_time") or not doc.get("table") and verdict["mapping_basis"] != "course_with_original_title":
                raise ValueError("new_document_not_write_ready")
            cols = catalog[table]["columns"]
            target_id = new_id(batch_id, "pdf_document", doc["candidate_id"])
            row = {key:value for key,value in common.items() if key in cols}
            row.update(institute_id=mapping["institute_id"], patient_id=mapping["patient_id"], visit_id=mapping["visit_id"])
            row.update(document_id=target_id, document_title=doc["title"], record_content=doc["content"])
            if "record_time" not in cols:
                raise ValueError("new_document_record_time_column_missing")
            row["record_time"] = doc["record_time"]
            names = signatures(doc["content"])
            if names and "physician_sign" in cols:
                row["physician_sign"] = " ".join(names)
            for key,info in cols.items():
                if not info["nullable"] and not info["generated"] and row.get(key) is None:
                    raise ValueError("new_document_required_field_missing")
            rows.setdefault(table, []).append(row)
        elif action == "supplement_candidate":
            candidates = [row for row in rows.get(table, []) if row.get("document_id") == target_id]
            if len(candidates) != 1:
                raise ValueError("supplement_document_not_unique")
            row = candidates[0]
            if "record_time_missing_in_database" in verdict["differences"]:
                if row.get("record_time") or row.get("record_datetime") or not doc.get("record_time"):
                    raise ValueError("supplement_would_overwrite_time")
                row["record_time"] = doc["record_time"]
            if "explicit_signatures_missing_in_database" in verdict["differences"]:
                names = signatures(doc["content"])
                if not names or row.get("physician_sign"):
                    raise ValueError("supplement_signature_conflict")
                if "physician_sign" in catalog[table]["columns"]:
                    row["physician_sign"] = " ".join(names)
                else:
                    # 无独立签名字段时只能保留PDF候选，不擅自拼接原正文。
                    action = "version_review"
        if linked is not None and action in ("same_body", "supplement_candidate", "version_review"):
            if not any(str(row.get("document_id")) == str(linked) for row in source_rows.get(table, [])):
                raise ValueError("linked_source_document_missing")
        provenance.append(dict(candidate_id=doc["candidate_id"], file_id=doc["source_file_id"],
            title=doc["title"], page_start=doc["page_start"], page_end=doc["page_end"],
            record_time_text=doc.get("record_time"), content=doc["content"], state=action,
            target_table=table, target_document_id=target_id,
            provenance={"source_document_id":linked, "refinement":verdict, "time_precision":doc.get("time_precision"),
                        "content_sha256":hashlib.sha256(doc["content"].encode()).hexdigest()}))
    return provenance
