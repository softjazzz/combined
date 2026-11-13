"""只读兼容196c4cf64的diagnosis-change-trace-v1；不引入该分支的规则执行器。

只承认已发布的白名单、计数、脱敏引用与摘录位置合同。日期仅校验，不补时间；
不连接当前CDM，也不据历史明细重算医学结论。未知版本继续拒绝。
"""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime
import re
from typing import Any

TRACE_VERSION = "diagnosis-change-trace-v1"
_LOCATION_FIELDS = (
    "record_content", "discharge_order", "document_title", "diagnosis_name",
    "admission_record_diagnosis.diagnosis_name",
)


def validated_legacy_diagnosis_trace(value: Any, *, count: Any) -> dict[str, Any] | None:
    """发布/读取只校验形状、位置和计数合同，不重新判医学状态。"""
    if (type(value) is not dict or set(value) != {"schema_version", "count_basis", "observed_document_count", "entries"}
            or value.get("schema_version") != TRACE_VERSION
            or type(value.get("count_basis")) is not str or value["count_basis"] not in {"structured_transitions", "declared_diagnoses", "document_mentions"}
            or type(value.get("observed_document_count")) is not int or value["observed_document_count"] < 0):
        return None
    entries = value["entries"]
    if type(entries) is not list or not entries or len(entries) > 5000:
        return None
    if value["count_basis"] == "structured_transitions":
        if type(count) is not int or count != len(entries):
            return None
    elif count is not None:
        return None

    def nullable_text(text, limit):
        return text is None or (type(text) is str and 0 < len(text) <= limit)

    def timestamp(text):
        if text is None:
            return True
        if type(text) is not str:
            return False
        try:
            datetime.fromisoformat(text)
        except ValueError:
            return False
        return len(text) <= 35

    document_refs = set()
    unlocated_count = 0
    for entry in entries:
        if (type(entry) is not dict or set(entry) != {"change_time", "original_diagnosis", "changed_diagnosis", "reason_state", "basis_state", "documents"}
                or not timestamp(entry["change_time"])
                or not all(nullable_text(entry[key], 4000) for key in ("original_diagnosis", "changed_diagnosis"))
                or any(type(entry[key]) is not str or entry[key] not in {"present", "missing", "unknown"} for key in ("reason_state", "basis_state"))
                or type(entry["documents"]) is not list or len(entry["documents"]) > 100):
            return None
        if value["count_basis"] == "structured_transitions" and any(entry[key] is None for key in ("change_time", "original_diagnosis", "changed_diagnosis")):
            return None
        for doc in entry["documents"]:
            if (type(doc) is not dict or set(doc) != {"source_ref", "source_type", "record_time", "snippets"}
                    or not (doc["source_ref"] is None or (type(doc["source_ref"]) is str and re.fullmatch(r"src_[0-9a-f]{24}", doc["source_ref"])))
                    or type(doc["source_type"]) is not str or doc["source_type"] not in {"diagnosis", "admission_record", "admission_record_diagnosis", "daily_course_record", "senior_course_record"}
                    or not timestamp(doc["record_time"])
                    or type(doc["snippets"]) is not list or len(doc["snippets"]) > 4):
                return None
            if doc["source_ref"] and doc["source_type"] in {"daily_course_record", "senior_course_record"}:
                document_refs.add((doc["source_type"], doc["source_ref"]))
            elif doc["source_type"] in {"daily_course_record", "senior_course_record"}:
                unlocated_count += 1
            for snippet in doc["snippets"]:
                if (type(snippet) is not dict or set(snippet) != {"role", "field_path", "start", "end", "text", "truncated"}
                        or type(snippet["role"]) is not str or snippet["role"] not in {"change", "reason", "basis"} or type(snippet["field_path"]) is not str or snippet["field_path"] not in _LOCATION_FIELDS
                        or type(snippet["start"]) is not int or snippet["start"] < 0 or type(snippet["end"]) is not int
                        or type(snippet["text"]) is not str or not 0 < len(snippet["text"]) <= 2000
                        or snippet["end"] - snippet["start"] != len(snippet["text"])
                        or type(snippet["truncated"]) is not bool):
                    return None
    if len(document_refs) + unlocated_count != value["observed_document_count"]:
        return None
    return deepcopy(value)
