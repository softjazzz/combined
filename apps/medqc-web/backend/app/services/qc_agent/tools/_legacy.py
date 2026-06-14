from __future__ import annotations

import re
import threading
from datetime import datetime, timedelta
from difflib import SequenceMatcher
from typing import Any, Dict, Iterable, List

from fastapi import HTTPException, status
from pydantic import BaseModel
from sqlalchemy import text as sqlalchemy_text

from app.services.custom_qc_workspace_service import CustomQCWorkspaceService
from app.services.frontpage_formal_qc import Category, FrontpageFormalQC, QCResult, Severity

from ..schemas import (
    AgentToolObservation,
    DocumentScope,
    GetRecordContextInput,
    ListQCRulesInput,
    PredictDIPGroupInput,
    PredictDRGGroupInput,
    RecordSummary,
    ResolveRuleScopeInput,
    RunDocumentQCInput,
    RunFrontpageQCInput,
    SearchICDCodesInput,
    SelectRecordDocumentsInput,
    SuggestRecordICDCodesInput,
    SearchRecordsInput,
    SearchRecordsPublicData,
)
from ..tool_registry import AgentToolRegistry
from ..rule_catalog import RuleSummary, filter_rule_catalog, get_rule_catalog, get_rules_by_ids


_CDM_DOCUMENT_TABLES = (
    ("admission_record", "入院记录"),
    ("first_course_record", "首次病程记录"),
    ("daily_course_record", "日常病程记录"),
    ("senior_course_record", "上级查房记录"),
    ("consultation_record", "会诊记录"),
    ("discharge_record", "出院记录"),
    ("surgery_record", "手术记录"),
    ("transfer_in_record", "转入记录"),
    ("transfer_out_record", "转出记录"),
)
_CDM_TEXT_FIELDS = ("record_content", "content", "text", "medical_text")
_CDM_SUPPLEMENT_TEXT_FIELDS = (
    "chief_complaint",
    "present_illness",
    "history_of_present_illness",
    "diagnosis",
    "diagnosis_name",
    "treatment_course",
    "admission_condition",
    "discharge_condition",
    "discharge_order",
    "consultation_opinion",
    "surgery_name",
)
_CDM_TIME_FIELDS = (
    "record_time",
    "document_time",
    "record_datetime",
    "created_at",
    "create_time",
    "updated_at",
    "update_time",
    "modified_at",
)
_CDM_DOCUMENT_ID_FIELDS = ("document_id", "doc_id", "id")


SENSITIVE_OUTPUT_KEYS = {
    "medical_text",
    "record_content",
    "bundle",
    "structured_context",
    "text_preview",
    "frontpage_draft",
    "raw_draft",
    "draft_json",
    "raw_documents",
    "raw_document_text",
    "selected_document_texts",
    "raw_llm_output",
    "raw_response",
    "api_response",
    "embedding",
    "embeddings",
    "vector",
    "vectors",
    "vector_path",
    "api_key",
    "token",
    "access_token",
    "rule_prompt",
    "prompt",
    "custom_prompt",
    "positive_example",
    "negative_example",
    "few_shot_examples",
    "examples",
    "raw_rule",
    "raw_rule_text",
}


def _text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _record_summary(record: Dict[str, Any]) -> RecordSummary:
    return RecordSummary(
        visit_id=_text(record.get("visit_id") or record.get("record_id")),
        patient_id=_text(record.get("patient_id")),
        patient_name=_text(record.get("patient_name") or record.get("name")),
        department=_text(record.get("department")),
        doctor=_text(record.get("doctor") or record.get("attending_physician")),
        admission_date=_text(record.get("admission_date") or record.get("admission_datetime"))[:10],
        discharge_date=_text(record.get("discharge_date") or record.get("discharge_datetime"))[:10],
    )


def _record_summary_dict(record: Dict[str, Any]) -> Dict[str, Any]:
    summary = _record_summary(record).model_dump()
    summary["mr_no"] = _text(record.get("mr_no") or record.get("medical_record_no"))
    return summary


def _drop_sensitive_keys(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            key: _drop_sensitive_keys(item)
            for key, item in value.items()
            if str(key) not in SENSITIVE_OUTPUT_KEYS
        }
    if isinstance(value, list):
        return [_drop_sensitive_keys(item) for item in value]
    return value


def assert_no_sensitive_output(value: Any) -> None:
    """测试和路由防御用：确保工具输出未携带病历全文或 bundle。"""
    if isinstance(value, dict):
        forbidden = SENSITIVE_OUTPUT_KEYS.intersection({str(key) for key in value.keys()})
        if forbidden:
            raise ValueError(f"工具输出包含敏感字段: {', '.join(sorted(forbidden))}")
        for item in value.values():
            assert_no_sensitive_output(item)
    elif isinstance(value, list):
        for item in value:
            assert_no_sensitive_output(item)


def _mask_sensitive_text(text: str) -> str:
    masked = re.sub(
        r"(?<!\d)(\d{6})\d{8}(\d{3}[\dXx])(?!\d)",
        r"\1********\2",
        text,
    )
    masked = re.sub(
        r"(?<!\d)(\d{6})\d{5}(\d{4})(?!\d)",
        r"\1*****\2",
        masked,
    )
    masked = re.sub(
        r"(?<!\d)(1[3-9])\d{7}(\d{2})(?!\d)",
        r"\1*******\2",
        masked,
    )
    masked = re.sub(
        r"((?:现住址|家庭住址|联系地址|地址|住址)[:：])\s*[^\n\r，,；;]{6,80}",
        r"\1[已脱敏]",
        masked,
    )
    return masked


def _extract_document_text(document: Dict[str, Any]) -> str:
    for key in ("record_content", "content", "text", "medical_text"):
        value = document.get(key)
        if value:
            return _text(value)
    return ""


def _document_type(document: Dict[str, Any]) -> str:
    return _text(
        document.get("document_type")
        or document.get("doc_type")
        or document.get("type")
        or document.get("name")
        or "未知文书"
    )


def _document_time(document: Dict[str, Any]) -> str:
    return _text(
        document.get("updated_at")
        or document.get("record_time")
        or document.get("document_time")
        or document.get("created_at")
    )


def _document_update_time(document: Dict[str, Any]) -> str:
    return _text(document.get("updated_at") or document.get("modified_at") or document.get("update_time"))


def _document_title(document: Dict[str, Any]) -> str:
    return _text(document.get("title") or document.get("name") or document.get("document_name") or _document_type(document))


def _summarize_documents(documents: Any) -> List[Dict[str, Any]]:
    if not isinstance(documents, list):
        return []
    grouped: Dict[str, Dict[str, Any]] = {}
    for document in documents:
        if not isinstance(document, dict):
            continue
        doc_type = _document_type(document)
        source_table = _text(document.get("source_table") or document.get("table"))
        summary = grouped.setdefault(
            doc_type,
            {
                "document_type": doc_type,
                "table": source_table,
                "count": 0,
                "text_length": 0,
                "record_time": _document_time(document),
                "latest_time": "",
                "preview": _mask_sensitive_text(_extract_document_text(document))[:300] if source_table else "",
            },
        )
        summary["count"] += 1
        summary["text_length"] += len(_extract_document_text(document))
        doc_time = _document_time(document)
        if doc_time and doc_time > summary["latest_time"]:
            summary["latest_time"] = doc_time
            summary["record_time"] = doc_time
    return list(grouped.values())


def _extract_medical_text(record: Dict[str, Any]) -> str:
    for key in ("medical_text", "record_content", "text"):
        value = record.get(key)
        if value:
            return _text(value)
    documents = record.get("documents")
    if isinstance(documents, list):
        parts = [_extract_document_text(document) for document in documents if isinstance(document, dict)]
        return "\n".join(part for part in parts if part)
    return ""


def _quote_identifier(value: str) -> str:
    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", value):
        raise ValueError(f"非法 SQL 标识符: {value}")
    return f'"{value}"'


def _cdm_table_columns(session: Any, table_name: str) -> tuple[str | None, set[str]]:
    rows = (
        session.execute(
            sqlalchemy_text(
                """
                SELECT table_schema, column_name
                FROM information_schema.columns
                WHERE table_name = :table_name
                  AND table_schema = ANY (current_schemas(false))
                ORDER BY array_position(current_schemas(false), table_schema), ordinal_position
                """
            ),
            {"table_name": table_name},
        )
        .mappings()
        .all()
    )
    if not rows:
        return None, set()
    schema = _text(rows[0].get("table_schema"))
    return schema, {_text(row.get("column_name")) for row in rows if row.get("column_name")}


def _first_column_value(row: Dict[str, Any], columns: Iterable[str]) -> Any:
    for column in columns:
        value = row.get(column)
        if value not in (None, ""):
            return value
    return ""


def _build_cdm_document_text(row: Dict[str, Any]) -> str:
    parts: List[str] = []
    primary = _text(_first_column_value(row, _CDM_TEXT_FIELDS))
    if primary:
        parts.append(primary)
    for field in _CDM_SUPPLEMENT_TEXT_FIELDS:
        value = _text(row.get(field))
        if value and value not in parts:
            parts.append(f"{field}: {value}")
    return "\n".join(parts).strip()


def _documents_to_medical_text(documents: List[Dict[str, Any]]) -> str:
    parts: List[str] = []
    for document in documents:
        text = _extract_document_text(document)
        if not text:
            continue
        parts.append(f"【{_document_type(document)}】\n{text}")
    return "\n\n".join(parts)


def _read_cdm_detail_documents(visit_id: str, patient_id: str | None = None) -> tuple[List[Dict[str, Any]], List[str]]:
    warnings: List[str] = []
    documents: List[Dict[str, Any]] = []
    try:
        from app.database.connection import SessionLocal
    except Exception as exc:  # pragma: no cover - 仅在数据库模块加载异常时触发
        return [], [f"CDM 文书读取不可用: {type(exc).__name__}"]

    session = SessionLocal()
    try:
        for table_name, document_type in _CDM_DOCUMENT_TABLES:
            try:
                schema, columns = _cdm_table_columns(session, table_name)
            except Exception as exc:  # pragma: no cover - 防御数据库元数据读取异常
                warnings.append(f"跳过 CDM 文书表 {table_name}: {type(exc).__name__}")
                continue
            if not schema or not columns:
                continue
            if "visit_id" not in columns:
                warnings.append(f"跳过 CDM 文书表 {table_name}: 缺少 visit_id 字段")
                continue

            select_columns = sorted(
                {
                    "visit_id",
                    "patient_id",
                    *[field for field in _CDM_DOCUMENT_ID_FIELDS if field in columns],
                    *[field for field in _CDM_TEXT_FIELDS if field in columns],
                    *[field for field in _CDM_SUPPLEMENT_TEXT_FIELDS if field in columns],
                    *[field for field in _CDM_TIME_FIELDS if field in columns],
                }
            )
            if not any(field in columns for field in _CDM_TEXT_FIELDS + _CDM_SUPPLEMENT_TEXT_FIELDS):
                continue

            qualified_table = f"{_quote_identifier(schema)}.{_quote_identifier(table_name)}"
            where_sql = ["visit_id = :visit_id"]
            params: Dict[str, Any] = {"visit_id": visit_id}
            if patient_id and "patient_id" in columns:
                where_sql.append("patient_id = :patient_id")
                params["patient_id"] = patient_id
            order_column = next((field for field in _CDM_TIME_FIELDS if field in columns), None)
            order_sql = f" ORDER BY {_quote_identifier(order_column)} NULLS LAST" if order_column else ""
            sql = (
                "SELECT "
                + ", ".join(_quote_identifier(column) for column in select_columns)
                + f" FROM {qualified_table} WHERE {' AND '.join(where_sql)}{order_sql} LIMIT 50"
            )
            try:
                rows = session.execute(sqlalchemy_text(sql), params).mappings().all()
            except Exception as exc:
                warnings.append(f"跳过 CDM 文书表 {table_name}: {type(exc).__name__}")
                continue

            for index, row in enumerate(rows, start=1):
                row_dict = dict(row)
                document_text = _build_cdm_document_text(row_dict)
                if not document_text:
                    continue
                document_id = _text(_first_column_value(row_dict, _CDM_DOCUMENT_ID_FIELDS)) or str(index)
                documents.append(
                    {
                        "document_ref": f"{table_name}:{document_id}",
                        "document_type": document_type,
                        "title": document_type,
                        "source_table": table_name,
                        "record_time": _text(_first_column_value(row_dict, _CDM_TIME_FIELDS)),
                        "content": document_text,
                    }
                )
    finally:
        session.close()

    return documents, warnings


def _ensure_single_visit_id(visit_id: str, tool_name: str) -> None:
    if re.search(r"[,，;；|\s]+", visit_id.strip()):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"{tool_name} 只支持单个 visit_id",
        )


def _alias_keywords(alias: str | None) -> List[str]:
    aliases = {
        "ward_round": ["查房", "上级医师查房", "主任医师查房", "主治医师查房"],
        "discharge": ["出院记录", "出院小结"],
        "course": ["首次病程", "日常病程", "病程记录", "上级医师查房", "阶段小结"],
        "consultation": ["会诊记录", "多学科会诊", "MDT", "会诊"],
        "mdt": ["多学科会诊", "MDT", "会诊"],
    }
    return aliases.get(alias or "", [])


def _alias_document_types(alias: str | None) -> List[str]:
    aliases = {
        "ward_round": [
            "查房",
            "上级查房",
            "上级医师查房",
            "主任医师查房",
            "主治医师查房",
            "病程记录",
            "日常病程记录",
            "senior_course_record",
            "daily_course_record",
        ],
        "discharge": ["出院记录", "出院小结"],
        "course": [
            "首次病程",
            "日常病程",
            "病程记录",
            "阶段小结",
            "上级查房",
            "上级医师查房",
            "first_course_record",
            "daily_course_record",
            "senior_course_record",
        ],
        "consultation": ["会诊记录", "多学科会诊", "MDT"],
        "mdt": ["会诊记录", "多学科会诊", "MDT", "mdt_record"],
    }
    return aliases.get(alias or "", [])


def _contains_any(text: str, keywords: Iterable[str]) -> List[str]:
    hits: List[str] = []
    lowered = text.lower()
    for keyword in keywords:
        term = _text(keyword)
        if term and term.lower() in lowered and term not in hits:
            hits.append(term)
    return hits


def _in_date_range(record_time: str, update_time: str, date_range: Any) -> bool:
    if not date_range:
        return True
    current = (record_time or update_time)[:10]
    if not current:
        return True
    start = _text(getattr(date_range, "start", "") or "")
    end = _text(getattr(date_range, "end", "") or "")
    if start and current < start[:10]:
        return False
    if end and current > end[:10]:
        return False
    return True


def _candidate_documents(internal_context: Dict[str, Any]) -> List[Dict[str, Any]]:
    documents = internal_context.get("documents")
    candidates: List[Dict[str, Any]] = []
    if isinstance(documents, list):
        for index, document in enumerate(documents, start=1):
            if not isinstance(document, dict):
                continue
            text = _extract_document_text(document)
            if not text:
                continue
            candidates.append(
                {
                    "document_ref": _text(document.get("document_ref") or document.get("id") or f"doc-{index}"),
                    "document_type": _document_type(document),
                    "title": _document_title(document),
                    "source_table": _text(document.get("source_table") or document.get("table")),
                    "record_time": _document_time(document),
                    "update_time": _document_update_time(document),
                    "text": text,
                }
            )
    if not candidates:
        medical_text = _text(internal_context.get("medical_text"))
        if medical_text:
            candidates.append(
                {
                    "document_ref": "merged-medical-text",
                    "document_type": "合并病历文本",
                    "title": "合并病历文本",
                    "record_time": "",
                    "update_time": "",
                    "text": medical_text,
                }
            )
    return candidates


def _select_documents_from_context(
    internal_context: Dict[str, Any],
    document_scope: Any,
) -> tuple[List[Dict[str, Any]], List[str]]:
    warnings: List[str] = []
    alias = getattr(document_scope, "alias", None)
    explicit_types = list(getattr(document_scope, "document_types", None) or [])
    explicit_keywords = list(getattr(document_scope, "keywords", None) or [])
    type_terms = explicit_types + _alias_document_types(alias)
    keyword_terms = explicit_keywords + _alias_keywords(alias)
    candidates = _candidate_documents(internal_context)
    selected: List[Dict[str, Any]] = []
    for document in candidates:
        searchable = "\n".join(
            [
                document.get("document_type", ""),
                document.get("title", ""),
                document.get("source_table", ""),
                document.get("text", ""),
            ]
        )
        type_hits = _contains_any(
            f"{document.get('document_type', '')}\n{document.get('title', '')}\n{document.get('source_table', '')}",
            type_terms,
        )
        keyword_hits = _contains_any(searchable, keyword_terms)
        if type_terms and not type_hits:
            continue
        if keyword_terms and not keyword_hits:
            continue
        if not _in_date_range(
            document.get("record_time", ""),
            document.get("update_time", ""),
            getattr(document_scope, "date_range", None),
        ):
            continue
        selected.append({**document, "matched_keywords": sorted(set(type_hits + keyword_hits))})
    if not type_terms and not keyword_terms:
        selected = [{**document, "matched_keywords": []} for document in candidates]

    max_documents = getattr(document_scope, "max_documents", 10)
    selected = selected[:max_documents]
    if not selected:
        warnings.append("未命中文书")
    return selected, warnings


def _public_document(document: Dict[str, Any]) -> Dict[str, Any]:
    text = _text(document.get("text"))
    return {
        "document_ref": document.get("document_ref", ""),
        "document_type": document.get("document_type", ""),
        "title": document.get("title", ""),
        "name": document.get("title", ""),
        "record_time": document.get("record_time", ""),
        "update_time": document.get("update_time", ""),
        "text_length": len(text),
        "matched_keywords": list(document.get("matched_keywords", [])),
        "preview": _mask_sensitive_text(text)[:300],
    }


def _first_match(text: str, patterns: Iterable[str]) -> str:
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if match:
            return _text(match.group(1))
    return ""


def _parse_int(value: str) -> int | None:
    if not value:
        return None
    match = re.search(r"\d+", value)
    if not match:
        return None
    try:
        return int(match.group(0))
    except ValueError:
        return None


def _parse_float(value: str) -> float | None:
    if not value:
        return None
    match = re.search(r"\d+(?:\.\d+)?", value)
    if not match:
        return None
    try:
        return float(match.group(0))
    except ValueError:
        return None


def _normalize_datetime(value: str) -> str:
    if not value:
        return ""
    normalized = value.replace("年", "-").replace("月", "-").replace("日", "")
    normalized = re.sub(r"[/.]", "-", normalized)
    normalized = re.sub(r"\s+", " ", normalized).strip()
    if re.fullmatch(r"\d{4}-\d{1,2}-\d{1,2}", normalized):
        parts = normalized.split("-")
        return f"{parts[0]}-{int(parts[1]):02d}-{int(parts[2]):02d}"
    return normalized


def _sex_code(value: str) -> int | None:
    if value == "男":
        return 1
    if value == "女":
        return 2
    return None


def _extract_diagnoses(text: str) -> List[Dict[str, Any]]:
    main_name = _first_match(
        text,
        [
            r"出院主要诊断[:：]?\s*([^\n\r；;，,]+)",
            r"主要诊断[:：]?\s*([^\n\r；;，,]+)",
            r"出院诊断[:：]?\s*([^\n\r；;，,]+)",
        ],
    )
    main_code = _first_match(
        text,
        [
            r"主要诊断编码[:：]?\s*([A-Z]\d{2}(?:\.\d{1,4})?)",
            r"出院主要诊断.*?([A-Z]\d{2}(?:\.\d{1,4})?)",
            r"出院诊断编码[:：]?\s*([A-Z]\d{2}(?:\.\d{1,4})?)",
        ],
    )
    diagnoses: List[Dict[str, Any]] = []
    if main_name or main_code:
        diagnoses.append(
            {
                "diagnosis_name": main_name,
                "diagnosis_code": main_code,
                "diagnosis_type": "main",
                "admission_condition": _first_match(text, [r"入院病情[:：]?\s*([^\n\r；;，,]+)"]),
            }
        )

    other_line = _first_match(
        text,
        [
            r"出院其他诊断[:：]?\s*([^\n\r]+)",
            r"其他诊断[:：]?\s*([^\n\r]+)",
        ],
    )
    if other_line:
        names = [item.strip() for item in re.split(r"[；;、,，]", other_line) if item.strip()]
        codes = re.findall(r"[A-Z]\d{2}(?:\.\d{1,4})?", other_line, flags=re.IGNORECASE)
        for index, name in enumerate(names[:8]):
            clean_name = re.sub(r"[A-Z]\d{2}(?:\.\d{1,4})?", "", name, flags=re.IGNORECASE).strip(" ：:")
            diagnoses.append(
                {
                    "diagnosis_name": clean_name or name,
                    "diagnosis_code": codes[index] if index < len(codes) else "",
                    "diagnosis_type": "other",
                    "admission_condition": "",
                }
            )
    return diagnoses


def _extract_surgeries(text: str) -> List[Dict[str, Any]]:
    surgery_name = _first_match(
        text,
        [
            r"主要手术及操作[:：]?\s*([^\n\r；;，,]+)",
            r"手术名称[:：]?\s*([^\n\r；;，,]+)",
            r"手术及操作名称[:：]?\s*([^\n\r；;，,]+)",
        ],
    )
    surgery_code = _first_match(
        text,
        [
            r"主要手术及操作编码[:：]?\s*(\d{2}\.\d{2,4})",
            r"手术及操作代码[:：]?\s*(\d{2}\.\d{2,4})",
            r"手术编码[:：]?\s*(\d{2}\.\d{2,4})",
        ],
    )
    if not surgery_name and not surgery_code:
        return []
    return [
        {
            "surgery_name": surgery_name,
            "surgery_code": surgery_code,
            "surgery_date": _normalize_datetime(
                _first_match(text, [r"手术日期[:：]?\s*([0-9年月日\-/. :]+)"])
            ),
            "surgeon_name": _first_match(text, [r"术者[:：]?\s*([^\n\r；;，,]+)"]),
            "anesthesia_method": _first_match(text, [r"麻醉方式[:：]?\s*([^\n\r；;，,]+)"]),
        }
    ]


def _build_transient_frontpage_from_text(
    medical_text: str,
    record_summary: Dict[str, Any],
) -> tuple[Dict[str, Any], List[str]]:
    """构造仅供首页形式质控使用的内存首页字典，不持久化也不对外返回。"""
    warnings: List[str] = []
    patient_name = _first_match(medical_text, [r"姓名[:：]?\s*([\u4e00-\u9fa5A-Za-z·]{2,20})"])
    gender = _first_match(medical_text, [r"性别[:：]?\s*(男|女)"])
    age = _parse_int(_first_match(medical_text, [r"年龄[:：]?\s*(\d{1,3})\s*岁?"]))
    id_card = _first_match(
        medical_text,
        [
            r"身份证号(?:码)?[:：]?\s*([1-9]\d{5}(?:19|20)\d{2}(?:0[1-9]|1[0-2])(?:0[1-9]|[12]\d|3[01])\d{3}[\dXx])",
            r"患者证件号码[:：]?\s*([1-9]\d{5}(?:19|20)\d{2}(?:0[1-9]|1[0-2])(?:0[1-9]|[12]\d|3[01])\d{3}[\dXx])",
        ],
    )
    admission_datetime = _normalize_datetime(
        _first_match(medical_text, [r"入院时间[:：]?\s*([0-9年月日\-/. :]+)"])
    )
    discharge_datetime = _normalize_datetime(
        _first_match(medical_text, [r"出院时间[:：]?\s*([0-9年月日\-/. :]+)"])
    )
    diagnoses = _extract_diagnoses(medical_text)
    surgeries = _extract_surgeries(medical_text)
    if not diagnoses:
        warnings.append("未从病历文本识别到出院诊断，首页形式质控将按缺失处理")

    frontpage = {
        "visit_id": record_summary.get("visit_id", ""),
        "patient_id": record_summary.get("patient_id", ""),
        "patient_name": patient_name or record_summary.get("patient_name", ""),
        "sex": _sex_code(gender),
        "sex_text": gender,
        "age": age,
        "id_card": id_card,
        "admission_datetime": admission_datetime,
        "discharge_datetime": discharge_datetime,
        "admission_dept": _first_match(medical_text, [r"入院科(?:别|室)?[:：]?\s*([^\n\r；;，,]+)"]),
        "discharge_dept": _first_match(medical_text, [r"出院科(?:别|室)?[:：]?\s*([^\n\r；;，,]+)"]),
        "admission_route": _parse_int(_first_match(medical_text, [r"入院途径[:：]?\s*(\d)"])),
        "discharge_method": _parse_int(_first_match(medical_text, [r"离院方式[:：]?\s*(\d)"])),
        "los_days": _parse_int(_first_match(medical_text, [r"实际住院(?:天数)?[:：]?\s*(\d{1,4})\s*天"])),
        "attending_physician": _first_match(
            medical_text,
            [r"主诊医师[:：]?\s*([^\n\r；;，,]+)", r"主治医师[:：]?\s*([^\n\r；;，,]+)"],
        ) or record_summary.get("doctor", ""),
        "total_cost": _parse_float(_first_match(medical_text, [r"总费用[:：]?\s*([0-9]+(?:\.[0-9]+)?)"])),
        "coma_hours_before": _parse_int(_first_match(medical_text, [r"入院前昏迷(?:时间)?[:：]?\s*(\d+)\s*小时"])),
        "coma_hours_after": _parse_int(_first_match(medical_text, [r"入院后昏迷(?:时间)?[:：]?\s*(\d+)\s*小时"])),
        "diagnoses": diagnoses,
        "surgeries": surgeries,
    }
    return frontpage, warnings


def _normalize_rule_scope(params: RunFrontpageQCInput) -> tuple[List[Category] | None, List[Severity] | None]:
    if not params.rule_scope:
        return None, None
    categories = None
    severities = None
    if params.rule_scope.categories:
        categories = [Category(item) for item in params.rule_scope.categories]
    if params.rule_scope.severities:
        severities = [Severity(item) for item in params.rule_scope.severities]
    return categories, severities


def _qc_issue(result: QCResult) -> Dict[str, Any]:
    status_text = "通过" if result.passed else "未通过"
    suggestion = "" if result.passed else f"请核对或补充 {result.field_name}"
    return {
        "rule_id": result.rule_id,
        "rule_name": result.rule_name,
        "field_name": result.field_name,
        "severity": result.severity.value,
        "category": result.category.value,
        "message": result.message,
        "evidence_summary": f"规则 {result.rule_id} 对字段 {result.field_name} 的形式质控结果为{status_text}",
        "suggestion": suggestion,
    }


def _read_context_record(
    service: CustomQCWorkspaceService,
    record: Dict[str, Any],
) -> tuple[Dict[str, Any], str]:
    hydrate = getattr(service, "hydrate_records_with_medical_text", None)
    if not callable(hydrate):
        return record, "collect_records"
    hydrated = hydrate([record])
    if isinstance(hydrated, list) and hydrated:
        return hydrated[0], "hydrate_records_with_medical_text"
    return record, "hydrate_records_with_medical_text"


def search_records(payload: BaseModel, workspace: CustomQCWorkspaceService | None = None) -> AgentToolObservation:
    params = payload if isinstance(payload, SearchRecordsInput) else SearchRecordsInput(**payload.model_dump())
    service = workspace or CustomQCWorkspaceService()

    records = service.collect_records(
        scope=params.scope,
        department=params.department,
        doctor=params.doctor,
        date_field=params.date_field,
        start_date=params.start_date,
        end_date=params.end_date,
        keyword=params.keyword,
        record_ids=None,
    )
    total = len(records)
    start = (params.page - 1) * params.page_size
    end = start + params.page_size
    page_records = records[start:end]
    summaries = [_record_summary(record).model_dump() for record in page_records]
    public = SearchRecordsPublicData(
        records=summaries,
        total=total,
        page=params.page,
        page_size=params.page_size,
        capped=total > params.page_size,
    ).model_dump()
    internal = {
        "matched_record_count": total,
        "returned_record_count": len(summaries),
        "filters": params.model_dump(),
        "record_refs": [
            {
                "visit_id": item.get("visit_id", ""),
                "patient_id": item.get("patient_id", ""),
            }
            for item in summaries
        ],
    }
    public = _drop_sensitive_keys(public)
    internal = _drop_sensitive_keys(internal)
    assert_no_sensitive_output(public)
    assert_no_sensitive_output(internal)
    return AgentToolObservation(
        tool_name="search_records",
        status="success",
        public_data=public,
        internal_data=internal,
    )


def get_record_context(
    payload: BaseModel | Dict[str, Any],
    workspace: CustomQCWorkspaceService | None = None,
) -> AgentToolObservation:
    if isinstance(payload, GetRecordContextInput):
        params = payload
    elif isinstance(payload, dict):
        params = GetRecordContextInput(**payload)
    else:
        params = GetRecordContextInput(**payload.model_dump())
    service = workspace or CustomQCWorkspaceService()
    scope = params.scene if params.scene in {"running", "final"} else "all"
    records = service.collect_records(
        scope=scope,
        department=None,
        doctor=None,
        date_field="discharge",
        start_date=None,
        end_date=None,
        keyword=None,
        record_ids=[params.visit_id],
    )
    matched = [
        record
        for record in records
        if _text(record.get("visit_id") or record.get("record_id")) == params.visit_id
    ]
    if not matched:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"未找到病历: visit_id={params.visit_id}",
        )
    if params.patient_id:
        patient_matched = [
            record for record in matched if _text(record.get("patient_id")) == params.patient_id
        ]
        if not patient_matched:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"patient_id 不匹配: visit_id={params.visit_id}",
            )
        matched = patient_matched
    if len(matched) != 1:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"visit_id 命中多条病历，需补充 patient_id: {params.visit_id}",
        )

    record = matched[0]
    context_record, source = _read_context_record(service, record)
    medical_text = _extract_medical_text(context_record)
    documents = context_record.get("documents")
    bundle = context_record.get("bundle")
    structured_context = context_record.get("structured_context")
    warnings: List[str] = []
    if not medical_text:
        fallback_documents, fallback_warnings = _read_cdm_detail_documents(params.visit_id, params.patient_id)
        warnings.extend(fallback_warnings)
        if fallback_documents:
            documents = fallback_documents
            medical_text = _documents_to_medical_text(fallback_documents)
            source = f"{source}+cdm_detail_documents"
    document_summary = _summarize_documents(documents)
    if not medical_text:
        warnings.append("未读取到病历文本")
    if not document_summary and medical_text:
        document_summary = [
            {
                "document_type": "合并病历文本",
                "table": "",
                "count": 1,
                "text_length": len(medical_text),
                "record_time": "",
                "latest_time": "",
                "preview": _mask_sensitive_text(medical_text)[:300],
            }
        ]
    preview = ""
    if params.include_preview and medical_text:
        preview = _mask_sensitive_text(medical_text)[:500]

    public = {
        "record_summary": _record_summary_dict(context_record),
        "context_status": {
            "text_available": bool(medical_text),
            "text_length": len(medical_text),
            "bundle_available": bool(bundle or structured_context),
            "source": source,
            "scene": params.scene,
        },
        "document_summary": document_summary,
        "preview": preview,
        "warnings": warnings,
    }
    public = _drop_sensitive_keys(public)
    assert_no_sensitive_output(public)
    return AgentToolObservation(
        tool_name="get_record_context",
        status="success",
        public_data=public,
        internal_data={
            "medical_text": medical_text,
            "documents": documents,
            "bundle": bundle,
            "structured_context": structured_context,
            "record_summary": public["record_summary"],
            "scene": params.scene,
            "source": source,
        },
    )


def run_frontpage_qc(
    payload: BaseModel | Dict[str, Any],
    workspace: CustomQCWorkspaceService | None = None,
    qc_engine: FrontpageFormalQC | None = None,
) -> AgentToolObservation:
    if isinstance(payload, RunFrontpageQCInput):
        params = payload
    elif isinstance(payload, dict):
        params = RunFrontpageQCInput(**payload)
    else:
        params = RunFrontpageQCInput(**payload.model_dump())
    _ensure_single_visit_id(params.visit_id, "run_frontpage_qc")

    context = get_record_context(
        GetRecordContextInput(
            visit_id=params.visit_id,
            patient_id=params.patient_id,
            scene="frontpage",
            include_preview=False,
        ),
        workspace=workspace,
    )
    internal_context = context.internal_data or {}
    medical_text = _text(internal_context.get("medical_text"))
    record_summary = dict(internal_context.get("record_summary") or {})
    if not medical_text:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"病历上下文缺少 medical_text: visit_id={params.visit_id}",
        )

    frontpage_draft, generation_warnings = _build_transient_frontpage_from_text(
        medical_text,
        record_summary,
    )
    categories, severities = _normalize_rule_scope(params)
    engine = qc_engine or FrontpageFormalQC()
    report = engine.validate(frontpage_draft, categories=categories, severities=severities)
    selected_results = report.results if params.include_passed else [item for item in report.results if not item.passed]
    issues = [_qc_issue(item) for item in selected_results]
    pass_rate = round(report.passed / report.total_rules, 4) if report.total_rules else 1.0
    warnings = list(context.public_data.get("warnings") or []) + generation_warnings
    public = {
        "record_summary": record_summary,
        "qc_summary": {
            "total_rules": report.total_rules,
            "passed": report.passed,
            "failed": report.failed,
            "pass_rate": pass_rate,
            "issue_count": report.failed,
        },
        "issues": issues,
        "generation_status": {
            "draft_generated": True,
            "text_length": len(medical_text),
            "warnings": generation_warnings,
        },
        "warnings": warnings,
    }
    public = _drop_sensitive_keys(public)
    assert_no_sensitive_output(public)
    return AgentToolObservation(
        tool_name="run_frontpage_qc",
        status="success",
        public_data=public,
        internal_data={
            "frontpage_draft": frontpage_draft,
            "text_length": len(medical_text),
            "record_ref": {
                "visit_id": record_summary.get("visit_id", ""),
                "patient_id": record_summary.get("patient_id", ""),
            },
        },
    )


def select_record_documents(
    payload: BaseModel | Dict[str, Any],
    workspace: CustomQCWorkspaceService | None = None,
) -> AgentToolObservation:
    if isinstance(payload, SelectRecordDocumentsInput):
        params = payload
    elif isinstance(payload, dict):
        params = SelectRecordDocumentsInput(**payload)
    else:
        params = SelectRecordDocumentsInput(**payload.model_dump())
    _ensure_single_visit_id(params.visit_id, "select_record_documents")

    context = get_record_context(
        GetRecordContextInput(
            visit_id=params.visit_id,
            patient_id=params.patient_id,
            scene="final",
            include_preview=False,
        ),
        workspace=workspace,
    )
    internal_context = context.internal_data or {}
    medical_text = _text(internal_context.get("medical_text"))
    candidates = _candidate_documents(internal_context)
    if not medical_text and not candidates:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"病历上下文缺少可用文书文本: visit_id={params.visit_id}",
        )

    selected, warnings = _select_documents_from_context(internal_context, params.document_scope)
    requested_scope = params.document_scope.model_dump()
    alias_keywords = _alias_keywords(params.document_scope.alias)
    keywords = sorted(set((params.document_scope.keywords or []) + alias_keywords))
    public = {
        "record_summary": internal_context.get("record_summary") or context.public_data.get("record_summary", {}),
        "selection_summary": {
            "requested_scope": requested_scope,
            "matched_document_count": len(selected),
            "matched_document_types": sorted({document.get("document_type", "") for document in selected if document.get("document_type")}),
            "keywords": keywords,
        },
        "documents": [_public_document(document) for document in selected],
        "warnings": warnings,
    }
    public = _drop_sensitive_keys(public)
    assert_no_sensitive_output(public)
    return AgentToolObservation(
        tool_name="select_record_documents",
        status="success",
        public_data=public,
        internal_data={
            "record_summary": public["record_summary"],
            "selected_documents": selected,
            "requested_scope": requested_scope,
            "warnings": warnings,
        },
    )


def _document_qc_rule(
    *,
    rule_id: str,
    rule_name: str,
    passed: bool,
    severity: str,
    category: str,
    document_ref: str,
    evidence_summary: str,
    suggestion: str,
    matched_documents: List[Dict[str, Any]] | None = None,
) -> Dict[str, Any]:
    matched = matched_documents or []
    document_types = sorted({_text(item.get("document_type")) for item in matched if item.get("document_type")})
    source_tables = sorted({_text(item.get("source_table")) for item in matched if item.get("source_table")})
    return {
        "rule_id": rule_id,
        "rule_name": rule_name,
        "passed": passed,
        "status": "passed" if passed else "failed",
        "severity": severity,
        "category": category,
        "document_ref": document_ref,
        "document_type": "、".join(document_types),
        "source_table": "、".join(source_tables),
        "check_type": _rule_check_type(rule_id),
        "checked_target": _rule_checked_target(rule_id, category),
        "explanation": _rule_explanation(rule_id, rule_name),
        "evidence_summary": evidence_summary,
        "matched_documents": matched,
        "message": f"{'通过' if passed else '未通过'}：{rule_name}",
        "suggestion": "" if passed else suggestion,
    }


_RULE_CHECK_TYPES = {
    "WR-001": "existence",
    "WR-002": "keyword",
    "WR-003": "keyword",
    "WR-004": "structure",
    "WR-005": "keyword",
    "WR-006": "length",
    "WR-007": "time",
    "SC-048": "time",
    "SC-050": "structure",
    "SC-052": "structure",
    "CR-001": "existence",
    "CR-002": "length",
    "CR-003": "keyword",
    "DIS-001": "existence",
    "DIS-002": "length",
    "DIS-003": "structure",
    "CON-001": "existence",
    "CON-002": "keyword",
    "DG-001": "existence",
    "DG-002": "time",
}


_CATEGORY_TARGETS = {
    "ward_round": "查房记录",
    "course": "病程记录",
    "discharge": "出院记录",
    "consultation": "会诊记录",
    "document_general": "目标文书",
}


_RULE_EXPLANATIONS = {
    "WR-001": "检查是否命中查房相关文书。",
    "WR-002": "检查查房记录中是否出现上级、主任或主治医师查房意见线索。",
    "WR-003": "检查查房记录是否包含病情变化、诊疗计划或处理意见线索。",
    "WR-004": "检查查房记录是否同时具备记录时间和医师签名线索。",
    "WR-005": "检查选中文书中是否出现明确查房关键词。",
    "WR-006": "检查选中查房相关文书正文长度是否达到基础完整性阈值。",
    "WR-007": "检查查房记录时间是否存在且未明显晚于出院时间。",
    "SC-048": "检查入院后 48 小时内是否存在主治或上级医师首次查房时间线索。",
    "SC-050": "检查上级医师查房记录是否包含病情分析或诊疗意见线索。",
    "SC-052": "检查上级医师查房记录是否包含审阅或签名线索。",
    "CR-001": "检查是否命中病程类文书。",
    "CR-002": "检查病程记录正文长度是否达到基础完整性阈值。",
    "CR-003": "检查病程记录是否包含病情、处理意见或诊疗计划线索。",
    "DIS-001": "检查是否命中出院记录或出院小结。",
    "DIS-002": "检查出院记录正文长度是否达到基础完整性阈值。",
    "DIS-003": "检查出院记录是否包含出院诊断、出院情况、医嘱或随访等核心栏目线索。",
    "CON-001": "检查是否命中会诊或 MDT 文书。",
    "CON-002": "检查会诊记录是否包含会诊意见或处理建议线索。",
    "DG-001": "检查目标文书是否存在。",
    "DG-002": "检查目标文书是否有记录时间元数据。",
}


def _rule_check_type(rule_id: str) -> str:
    return _RULE_CHECK_TYPES.get(rule_id, "other")


def _rule_checked_target(rule_id: str, category: str) -> str:
    if rule_id.startswith("DIS-"):
        return "出院记录"
    if rule_id.startswith("CON-"):
        return "会诊记录"
    if rule_id.startswith("CR-"):
        return "病程记录"
    return _CATEGORY_TARGETS.get(category, "目标文书")


def _rule_explanation(rule_id: str, rule_name: str) -> str:
    return _RULE_EXPLANATIONS.get(rule_id, f"检查{rule_name}是否满足基础质控要求。")


def _matched_document_summaries(selected_documents: List[Dict[str, Any]], *, limit: int = 10) -> List[Dict[str, Any]]:
    summaries: List[Dict[str, Any]] = []
    for document in selected_documents[:limit]:
        text = _text(document.get("text"))
        summaries.append(
            {
                "document_type": _text(document.get("document_type")),
                "record_time": _text(document.get("record_time") or document.get("update_time")),
                "text_length": len(text),
                "source_table": _text(document.get("source_table")),
            }
        )
    return summaries


def _parse_datetime(value: Any) -> datetime | None:
    text = _text(value)
    if not text:
        return None
    normalized = text.replace("T", " ").replace("/", "-").replace("年", "-").replace("月", "-").replace("日", " ")
    normalized = re.sub(r"\s+", " ", normalized).strip()
    for fmt, length in (("%Y-%m-%d %H:%M:%S", 19), ("%Y-%m-%d %H:%M", 16), ("%Y-%m-%d", 10)):
        try:
            return datetime.strptime(normalized[:length], fmt)
        except ValueError:
            continue
    match = re.search(r"((?:19|20)\d{2})[-.](\d{1,2})[-.](\d{1,2})", normalized)
    if not match:
        return None
    try:
        return datetime(int(match.group(1)), int(match.group(2)), int(match.group(3)))
    except ValueError:
        return None


def _selected_text(selected_documents: List[Dict[str, Any]]) -> str:
    return "\n".join(_text(document.get("text")) for document in selected_documents)


def _document_refs(selected_documents: List[Dict[str, Any]]) -> str:
    return ",".join(_text(document.get("document_ref")) for document in selected_documents if document.get("document_ref"))


def _total_text_length(selected_documents: List[Dict[str, Any]]) -> int:
    return sum(len(_text(document.get("text"))) for document in selected_documents)


def _first_document_ref(selected_documents: List[Dict[str, Any]]) -> str:
    return selected_documents[0].get("document_ref", "") if selected_documents else ""


def _has_record_time(selected_documents: List[Dict[str, Any]]) -> bool:
    return any(_text(document.get("record_time") or document.get("update_time")) for document in selected_documents)


def _has_late_document_after_discharge(
    selected_documents: List[Dict[str, Any]],
    record_summary: Dict[str, Any] | None,
) -> bool:
    discharge_time = _parse_datetime((record_summary or {}).get("discharge_date"))
    if not discharge_time:
        return False
    threshold = discharge_time + timedelta(days=1)
    for document in selected_documents:
        document_time = _parse_datetime(document.get("record_time") or document.get("update_time"))
        if document_time and document_time > threshold:
            return True
    return False


def _has_document_text_min_length(selected_documents: List[Dict[str, Any]], min_length: int) -> bool:
    return _total_text_length(selected_documents) >= min_length


def _run_ward_round_rules(
    selected_documents: List[Dict[str, Any]],
    *,
    include_evidence: bool,
    record_summary: Dict[str, Any] | None = None,
) -> List[Dict[str, Any]]:
    joined_text = _selected_text(selected_documents)
    document_ref = _first_document_ref(selected_documents)
    document_refs = _document_refs(selected_documents)
    has_document = bool(selected_documents)
    total_length = _total_text_length(selected_documents)
    matched_documents = _matched_document_summaries(selected_documents)
    has_ward_round_keyword = bool(re.search(r"上级医师查房|主任医师查房|主治医师查房|副主任医师查房|主任查房|上级查房|查房", joined_text))
    has_superior_opinion = bool(re.search(r"上级医师|主任医师|副主任医师|主治医师|主任查房|上级查房", joined_text))
    has_plan = bool(re.search(r"病情变化|诊疗计划|治疗计划|处理意见|继续|调整|完善检查|下一步|复查|医嘱", joined_text))
    has_time = bool(re.search(r"(?:19|20)\d{2}[-年/]\d{1,2}[-月/]\d{1,2}", joined_text)) or _has_record_time(selected_documents)
    has_signature = bool(re.search(r"医师签名|医生签名|签名|记录医师|医师[:：]", joined_text))
    time_is_acceptable = has_time and not _has_late_document_after_discharge(selected_documents, record_summary)
    first_ward_round_timely = _has_first_ward_round_within_days(
        selected_documents,
        record_summary,
        max_days=2,
        senior_keywords=r"主治医师|上级医师|主任医师|副主任医师|主任查房|上级查房|查房",
    )
    evidence = {
        "exists": "命中查房相关文书" if has_document else "未命中查房相关文书",
        "superior": "文本包含上级/主任/主治医师查房线索" if has_superior_opinion else "未见上级医师查房意见线索",
        "plan": "文本包含病情变化、诊疗计划或处理意见线索" if has_plan else "未见病情变化、诊疗计划或处理意见线索",
        "time_signature": "文本包含记录时间和医师签名线索" if has_time and has_signature else "记录时间或医师签名线索不足",
        "keyword": "文本包含查房关键词线索" if has_ward_round_keyword else "未见查房关键词线索",
        "length": f"选中文书总长度 {total_length} 字" if has_document else "未命中文书",
        "time": "记录时间基础校验通过" if time_is_acceptable else "记录时间缺失或晚于出院后 1 天",
        "first_round": "入院 48 小时内存在查房时间线索" if first_ward_round_timely else "未见入院 48 小时内查房时间线索",
    }
    if not include_evidence:
        evidence = {key: "" for key in evidence}
    return [
        _document_qc_rule(
            rule_id="WR-001",
            rule_name="查房记录是否存在",
            passed=has_document,
            severity="error",
            category="ward_round",
            document_ref=document_ref,
            evidence_summary=evidence["exists"],
            suggestion="请补充查房记录或确认文书类型。",
            matched_documents=matched_documents,
        ),
        _document_qc_rule(
            rule_id="WR-002",
            rule_name="是否体现上级医师/主任医师查房意见",
            passed=has_superior_opinion,
            severity="warning",
            category="ward_round",
            document_ref=document_ref,
            evidence_summary=evidence["superior"],
            suggestion="请在查房记录中补充上级医师或主任医师查房意见。",
            matched_documents=matched_documents,
        ),
        _document_qc_rule(
            rule_id="WR-003",
            rule_name="是否包含病情变化、诊疗计划或处理意见",
            passed=has_plan,
            severity="warning",
            category="ward_round",
            document_ref=document_ref,
            evidence_summary=evidence["plan"],
            suggestion="请补充病情变化、诊疗计划或处理意见。",
            matched_documents=matched_documents,
        ),
        _document_qc_rule(
            rule_id="WR-004",
            rule_name="是否有记录时间和医师签名线索",
            passed=has_time and has_signature,
            severity="warning",
            category="ward_round",
            document_ref=document_ref,
            evidence_summary=evidence["time_signature"],
            suggestion="请补充记录时间和医师签名线索。",
            matched_documents=matched_documents,
        ),
        _document_qc_rule(
            rule_id="WR-005",
            rule_name="是否包含查房关键词线索",
            passed=has_ward_round_keyword,
            severity="warning",
            category="ward_round",
            document_ref=document_refs or document_ref,
            evidence_summary=evidence["keyword"],
            suggestion="请确认文书类型或在查房记录中补充明确查房标题/段落。",
            matched_documents=matched_documents,
        ),
        _document_qc_rule(
            rule_id="WR-006",
            rule_name="查房相关文书内容是否过短",
            passed=_has_document_text_min_length(selected_documents, 80),
            severity="warning",
            category="ward_round",
            document_ref=document_refs or document_ref,
            evidence_summary=evidence["length"],
            suggestion="请补充查房记录的病情分析、诊疗意见和处理计划。",
            matched_documents=matched_documents,
        ),
        _document_qc_rule(
            rule_id="WR-007",
            rule_name="查房记录时间基础校验",
            passed=time_is_acceptable,
            severity="warning",
            category="ward_round",
            document_ref=document_refs or document_ref,
            evidence_summary=evidence["time"],
            suggestion="请补充查房记录时间，或核对记录时间是否晚于出院后 1 天。",
            matched_documents=matched_documents,
        ),
        _document_qc_rule(
            rule_id="SC-048",
            rule_name="入院48小时内主治医师首次查房记录",
            passed=first_ward_round_timely,
            severity="error",
            category="ward_round",
            document_ref=document_refs or document_ref,
            evidence_summary=evidence["first_round"],
            suggestion="请补充入院 48 小时内主治医师或上级医师首次查房记录。",
            matched_documents=matched_documents,
        ),
        _document_qc_rule(
            rule_id="SC-050",
            rule_name="上级医师查房病情分析或诊疗意见",
            passed=has_plan and has_superior_opinion,
            severity="warning",
            category="ward_round",
            document_ref=document_refs or document_ref,
            evidence_summary=evidence["plan"] if has_superior_opinion else evidence["superior"],
            suggestion="请在上级医师查房记录中补充病情分析和诊疗意见。",
            matched_documents=matched_documents,
        ),
        _document_qc_rule(
            rule_id="SC-052",
            rule_name="上级医师查房记录审阅及签名",
            passed=has_signature,
            severity="warning",
            category="ward_round",
            document_ref=document_refs or document_ref,
            evidence_summary=evidence["time_signature"],
            suggestion="请补充上级医师审阅或签名线索。",
            matched_documents=matched_documents,
        ),
    ]


def _has_first_ward_round_within_days(
    selected_documents: List[Dict[str, Any]],
    record_summary: Dict[str, Any] | None,
    *,
    max_days: int,
    senior_keywords: str,
) -> bool:
    raw_admission_date = _text((record_summary or {}).get("admission_date"))
    admission_time = _parse_datetime(raw_admission_date)
    if not admission_time:
        return False
    threshold = admission_time + timedelta(days=max_days)
    if len(raw_admission_date) <= 10:
        threshold = threshold + timedelta(hours=23, minutes=59, seconds=59)
    for document in selected_documents:
        text_value = _text(document.get("text"))
        searchable = "\n".join(
            [
                _text(document.get("document_type")),
                _text(document.get("title")),
                _text(document.get("source_table")),
                text_value,
            ]
        )
        if not re.search(senior_keywords, searchable):
            continue
        document_time = _parse_datetime(document.get("record_time") or document.get("update_time")) or _parse_datetime(text_value)
        if document_time and admission_time <= document_time <= threshold:
            return True
    return False


def _run_course_rules(
    selected_documents: List[Dict[str, Any]],
    *,
    include_evidence: bool,
) -> List[Dict[str, Any]]:
    joined_text = _selected_text(selected_documents)
    document_ref = _document_refs(selected_documents) or _first_document_ref(selected_documents)
    has_document = bool(selected_documents)
    total_length = _total_text_length(selected_documents)
    matched_documents = _matched_document_summaries(selected_documents)
    has_care_content = bool(re.search(r"病情|诊疗计划|治疗计划|处理意见|继续|调整|完善检查|复查|医嘱", joined_text))
    evidence = {
        "exists": "命中病程类文书" if has_document else "未命中病程类文书",
        "length": f"选中文书总长度 {total_length} 字" if has_document else "未命中文书",
        "content": "文本包含病情或诊疗处理线索" if has_care_content else "未见病情或诊疗处理线索",
    }
    if not include_evidence:
        evidence = {key: "" for key in evidence}
    return [
        _document_qc_rule(
            rule_id="CR-001",
            rule_name="病程记录是否存在",
            passed=has_document,
            severity="error",
            category="course",
            document_ref=document_ref,
            evidence_summary=evidence["exists"],
            suggestion="请补充病程记录或调整文书筛选条件。",
            matched_documents=matched_documents,
        ),
        _document_qc_rule(
            rule_id="CR-002",
            rule_name="病程记录内容是否过短",
            passed=_has_document_text_min_length(selected_documents, 80),
            severity="warning",
            category="course",
            document_ref=document_ref,
            evidence_summary=evidence["length"],
            suggestion="请补充病程记录正文内容。",
            matched_documents=matched_documents,
        ),
        _document_qc_rule(
            rule_id="CR-003",
            rule_name="病程记录诊疗内容线索",
            passed=has_care_content,
            severity="warning",
            category="course",
            document_ref=document_ref,
            evidence_summary=evidence["content"],
            suggestion="请补充病情变化、处理意见或诊疗计划。",
            matched_documents=matched_documents,
        ),
    ]


def _run_discharge_rules(
    selected_documents: List[Dict[str, Any]],
    *,
    include_evidence: bool,
) -> List[Dict[str, Any]]:
    joined_text = _selected_text(selected_documents)
    document_ref = _document_refs(selected_documents) or _first_document_ref(selected_documents)
    has_document = bool(selected_documents)
    total_length = _total_text_length(selected_documents)
    matched_documents = _matched_document_summaries(selected_documents)
    has_core_sections = bool(re.search(r"出院诊断|出院情况|出院医嘱|出院带药|随访|治疗经过|住院经过", joined_text))
    evidence = {
        "exists": "命中出院记录或出院小结" if has_document else "未命中出院记录或出院小结",
        "length": f"出院文书总长度 {total_length} 字" if has_document else "未命中文书",
        "sections": "文本包含出院诊断/出院情况/医嘱/随访等线索" if has_core_sections else "未见出院记录核心栏目线索",
    }
    if not include_evidence:
        evidence = {key: "" for key in evidence}
    return [
        _document_qc_rule(
            rule_id="DIS-001",
            rule_name="出院记录是否存在",
            passed=has_document,
            severity="error",
            category="discharge",
            document_ref=document_ref,
            evidence_summary=evidence["exists"],
            suggestion="请补充出院记录或出院小结。",
            matched_documents=matched_documents,
        ),
        _document_qc_rule(
            rule_id="DIS-002",
            rule_name="出院记录正文是否过短",
            passed=_has_document_text_min_length(selected_documents, 120),
            severity="warning",
            category="discharge",
            document_ref=document_ref,
            evidence_summary=evidence["length"],
            suggestion="请补充出院记录正文、诊疗经过、出院情况和医嘱。",
            matched_documents=matched_documents,
        ),
        _document_qc_rule(
            rule_id="DIS-003",
            rule_name="出院记录核心栏目线索",
            passed=has_core_sections,
            severity="warning",
            category="discharge",
            document_ref=document_ref,
            evidence_summary=evidence["sections"],
            suggestion="请补充出院诊断、出院情况、出院医嘱或随访安排。",
            matched_documents=matched_documents,
        ),
    ]


def _run_consultation_rules(
    selected_documents: List[Dict[str, Any]],
    *,
    include_evidence: bool,
) -> List[Dict[str, Any]]:
    joined_text = _selected_text(selected_documents)
    document_ref = _document_refs(selected_documents) or _first_document_ref(selected_documents)
    has_document = bool(selected_documents)
    matched_documents = _matched_document_summaries(selected_documents)
    has_opinion = bool(re.search(r"会诊意见|会诊建议|处理意见|诊疗建议|MDT|多学科", joined_text, re.IGNORECASE))
    evidence = {
        "exists": "命中会诊或 MDT 文书" if has_document else "未命中会诊或 MDT 文书",
        "opinion": "文本包含会诊意见或处理建议线索" if has_opinion else "未见会诊意见或处理建议线索",
    }
    if not include_evidence:
        evidence = {key: "" for key in evidence}
    return [
        _document_qc_rule(
            rule_id="CON-001",
            rule_name="会诊记录是否存在",
            passed=has_document,
            severity="error",
            category="consultation",
            document_ref=document_ref,
            evidence_summary=evidence["exists"],
            suggestion="请补充会诊记录或 MDT 记录。",
            matched_documents=matched_documents,
        ),
        _document_qc_rule(
            rule_id="CON-002",
            rule_name="会诊意见线索",
            passed=has_opinion,
            severity="warning",
            category="consultation",
            document_ref=document_ref,
            evidence_summary=evidence["opinion"],
            suggestion="请补充会诊意见、处理建议或诊疗建议。",
            matched_documents=matched_documents,
        ),
    ]


def _run_document_general_rules(
    selected_documents: List[Dict[str, Any]],
    *,
    include_evidence: bool,
) -> List[Dict[str, Any]]:
    document_ref = selected_documents[0].get("document_ref", "") if selected_documents else ""
    has_document = bool(selected_documents)
    has_time = any(_text(document.get("record_time") or document.get("update_time")) for document in selected_documents)
    matched_documents = _matched_document_summaries(selected_documents)
    return [
        _document_qc_rule(
            rule_id="DG-001",
            rule_name="目标文书是否存在",
            passed=has_document,
            severity="error",
            category="document_general",
            document_ref=document_ref,
            evidence_summary=("命中文书" if has_document else "未命中文书") if include_evidence else "",
            suggestion="请补充目标文书或调整文书筛选条件。",
            matched_documents=matched_documents,
        ),
        _document_qc_rule(
            rule_id="DG-002",
            rule_name="目标文书是否有记录时间",
            passed=has_time,
            severity="warning",
            category="document_general",
            document_ref=document_ref,
            evidence_summary=("文书元数据包含记录时间" if has_time else "未见记录时间元数据") if include_evidence else "",
            suggestion="请补充文书记录时间。",
            matched_documents=matched_documents,
        ),
    ]


_AGENT_BUILTIN_RULE_FAMILIES = {
    "WR-001": "ward_round",
    "WR-002": "ward_round",
    "WR-003": "ward_round",
    "WR-004": "ward_round",
    "WR-005": "ward_round",
    "WR-006": "ward_round",
    "WR-007": "ward_round",
    "SC-048": "ward_round",
    "SC-050": "ward_round",
    "SC-052": "ward_round",
    "CR-001": "course",
    "CR-002": "course",
    "CR-003": "course",
    "DIS-001": "discharge",
    "DIS-002": "discharge",
    "DIS-003": "discharge",
    "CON-001": "consultation",
    "CON-002": "consultation",
    "DG-001": "document_general",
    "DG-002": "document_general",
}

_SAFE_PROGRAMMATIC_RULE_IDS = {
    "SC-048": "ward_round",
    "SC-050": "ward_round",
    "SC-052": "ward_round",
}


def _rule_summary_public(rule: RuleSummary) -> Dict[str, Any]:
    return rule.to_public_dict()


_SKIP_REASON_LABELS = {
    "requires_llm": "需要受控 LLM 判断",
    "unsupported_execution_mode": "暂未接入只读程序化执行器",
    "unknown_rule": "规则目录未找到",
    "not_applicable_document": "不适用于当前文书类型",
    "not_safe_readonly": "尚未确认只读安全",
}


_SKIP_REASON_NEXT_STEPS = {
    "requires_llm": "需接入受控 LLM 规则执行器后判断。",
    "unsupported_execution_mode": "需补充安全程序化 evaluator 或接入正式只读规则引擎。",
    "unknown_rule": "请核对 rule_id 或先通过规则目录重新选择规则。",
    "not_applicable_document": "请更换文书类型或选择适用于当前文书的规则。",
    "not_safe_readonly": "需完成规则执行安全审计后再开放。",
}


def _skip_reason_label(reason: str) -> str:
    return _SKIP_REASON_LABELS.get(reason, "当前阶段未执行")


def _skip_reason_next_step(reason: str) -> str:
    return _SKIP_REASON_NEXT_STEPS.get(reason, "请由质控员复核规则适用性和执行方式。")


def _skipped_rule(
    *,
    rule_id: str,
    reason: str,
    message: str,
    rule: RuleSummary | None = None,
) -> Dict[str, Any]:
    payload: Dict[str, Any] = {
        "rule_id": rule_id,
        "rule_name": "",
        "source": "",
        "reason": reason,
        "reason_label": _skip_reason_label(reason),
        "next_step": _skip_reason_next_step(reason),
        "message": message,
    }
    if rule:
        payload["rule_name"] = rule.rule_name
        payload["source"] = rule.source
        payload["severity"] = rule.severity
        payload["rule"] = _rule_summary_public(rule)
    return payload


def _unique_text_items(items: Iterable[Any]) -> List[str]:
    seen: set[str] = set()
    result: List[str] = []
    for item in items:
        text = _text(item)
        if not text or text in seen:
            continue
        seen.add(text)
        result.append(text)
    return result


def _document_scope_for_document_qc(params: RunDocumentQCInput) -> DocumentScope:
    scope = params.document_scope.model_copy(deep=True)
    if params.document_alias and params.document_alias in {"ward_round", "discharge", "course", "consultation", "mdt"}:
        scope.alias = params.document_alias
    if params.document_type:
        document_terms = list(scope.document_types or [])
        if params.document_type not in document_terms:
            document_terms.append(params.document_type)
        scope.document_types = document_terms
    return scope


def _requested_document_filters(params: RunDocumentQCInput) -> tuple[str | None, str | None]:
    document_alias = params.document_alias or params.document_scope.alias
    document_type = params.document_type
    if not document_type and params.document_scope.document_types:
        document_type = params.document_scope.document_types[0]
    return document_alias, document_type


def _resolve_document_qc_rules(params: RunDocumentQCInput) -> tuple[list[RuleSummary], list[Dict[str, Any]], list[str]]:
    explicit_rule_ids = list(params.rule_ids or params.qc_scope.rule_ids or [])
    warnings: List[str] = []
    skipped: List[Dict[str, Any]] = []
    if explicit_rule_ids:
        limited_rule_ids = explicit_rule_ids[: params.max_rules]
        if len(explicit_rule_ids) > params.max_rules:
            warnings.append(f"规则数量超过 max_rules={params.max_rules}，仅处理前 {params.max_rules} 条")
        rules, missing = get_rules_by_ids(limited_rule_ids)
        for rule_id in missing:
            skipped.append(
                _skipped_rule(
                    rule_id=rule_id,
                    reason="unknown_rule",
                    message=f"规则目录中未找到 rule_id={rule_id}",
                )
            )
        return rules, skipped, warnings

    has_new_scope = bool(params.document_alias or params.document_type or params.qc_point_type)
    if has_new_scope:
        rules, scope_warnings = filter_rule_catalog(
            document_alias=params.document_alias,
            document_type=params.document_type,
            qc_point_type=params.qc_point_type,
            limit=params.max_rules,
        )
        warnings.extend(scope_warnings)
        if not rules and not scope_warnings:
            warnings.append("未根据文书类型或质控点类型匹配到规则")
        return rules, skipped, warnings

    rule_family = params.qc_scope.rule_family or "document_general"
    if rule_family == "document_general" and params.document_scope.alias == "ward_round":
        rule_family = "ward_round"
    default_rule_ids = ["WR-001", "WR-002", "WR-003", "WR-004"] if rule_family == "ward_round" else ["DG-001", "DG-002"]
    rules, missing = get_rules_by_ids(default_rule_ids[: params.max_rules])
    for rule_id in missing:
        skipped.append(
            _skipped_rule(
                rule_id=rule_id,
                reason="unknown_rule",
                message=f"默认规则未在规则目录中找到: {rule_id}",
            )
        )
    warnings.append("未传入 rule_ids 或可解析规则范围，已使用默认文书规则集")
    return rules, skipped, warnings


def _rule_applicable_to_document(
    rule: RuleSummary,
    *,
    document_alias: str | None,
    document_type: str | None,
) -> bool:
    if document_alias and document_alias in {"ward_round", "discharge", "course", "consultation", "mdt"}:
        return document_alias in rule.document_aliases
    if document_type:
        return document_type in rule.document_types or document_type in rule.document_aliases
    return True


def _execute_agent_builtin_rules(
    rules: List[RuleSummary],
    selected_documents: List[Dict[str, Any]],
    *,
    include_evidence: bool,
    document_alias: str | None,
    document_type: str | None,
    record_summary: Dict[str, Any] | None = None,
) -> tuple[List[Dict[str, Any]], List[RuleSummary], List[Dict[str, Any]]]:
    ward_round_results = {
        item["rule_id"]: item
        for item in _run_ward_round_rules(
            selected_documents,
            include_evidence=include_evidence,
            record_summary=record_summary,
        )
    }
    course_results = {
        item["rule_id"]: item
        for item in _run_course_rules(
            selected_documents,
            include_evidence=include_evidence,
        )
    }
    discharge_results = {
        item["rule_id"]: item
        for item in _run_discharge_rules(
            selected_documents,
            include_evidence=include_evidence,
        )
    }
    consultation_results = {
        item["rule_id"]: item
        for item in _run_consultation_rules(
            selected_documents,
            include_evidence=include_evidence,
        )
    }
    general_results = {
        item["rule_id"]: item
        for item in _run_document_general_rules(
            selected_documents,
            include_evidence=include_evidence,
        )
    }
    results_by_id = {
        **general_results,
        **ward_round_results,
        **course_results,
        **discharge_results,
        **consultation_results,
    }
    executed_results: List[Dict[str, Any]] = []
    executed_rules: List[RuleSummary] = []
    skipped_rules: List[Dict[str, Any]] = []
    for rule in rules:
        rule_id = rule.rule_id
        if not _rule_applicable_to_document(rule, document_alias=document_alias, document_type=document_type):
            skipped_rules.append(
                _skipped_rule(
                    rule_id=rule_id,
                    reason="not_applicable_document",
                    message="规则不适用于当前文书类型或文书别名",
                    rule=rule,
                )
            )
            continue
        is_safe_programmatic = rule.source == "agent_builtin" or rule_id in _SAFE_PROGRAMMATIC_RULE_IDS
        if rule.requires_llm and not is_safe_programmatic:
            skipped_rules.append(
                _skipped_rule(
                    rule_id=rule_id,
                    reason="requires_llm",
                    message="本阶段不执行需要 LLM 的规则",
                    rule=rule,
                )
            )
            continue
        if not is_safe_programmatic:
            skipped_rules.append(
                _skipped_rule(
                    rule_id=rule_id,
                    reason="unsupported_execution_mode",
                    message="本阶段仅执行 Agent 内置或已安全映射的只读程序化文书规则",
                    rule=rule,
                )
            )
            continue
        if rule_id not in _AGENT_BUILTIN_RULE_FAMILIES or rule_id not in results_by_id:
            skipped_rules.append(
                _skipped_rule(
                    rule_id=rule_id,
                    reason="unsupported_execution_mode",
                    message="未找到该内置规则的程序化 evaluator",
                    rule=rule,
                )
            )
            continue
        executed_rules.append(rule)
        executed_results.append(results_by_id[rule_id])
    return executed_results, executed_rules, skipped_rules


def run_document_qc(
    payload: BaseModel | Dict[str, Any],
    workspace: CustomQCWorkspaceService | None = None,
) -> AgentToolObservation:
    if isinstance(payload, RunDocumentQCInput):
        params = payload
    elif isinstance(payload, dict):
        params = RunDocumentQCInput(**payload)
    else:
        params = RunDocumentQCInput(**payload.model_dump())
    _ensure_single_visit_id(params.visit_id, "run_document_qc")

    document_scope = _document_scope_for_document_qc(params)
    selection = select_record_documents(
        SelectRecordDocumentsInput(
            visit_id=params.visit_id,
            patient_id=params.patient_id,
            document_scope=document_scope,
        ),
        workspace=workspace,
    )
    selected_documents = list((selection.internal_data or {}).get("selected_documents") or [])
    selected_rules, skipped_rules, rule_warnings = _resolve_document_qc_rules(params)
    document_alias, document_type = _requested_document_filters(params)
    results, executed_rules, execution_skipped = _execute_agent_builtin_rules(
        selected_rules,
        selected_documents,
        include_evidence=params.qc_scope.include_evidence,
        document_alias=document_alias,
        document_type=document_type,
        record_summary=selection.public_data.get("record_summary", {}),
    )
    skipped_rules.extend(execution_skipped)
    include_passed = params.include_passed if params.include_passed is not None else params.qc_scope.include_passed
    selected_results = results if include_passed else [item for item in results if not item["passed"]]
    passed = sum(1 for item in results if item["passed"])
    failed = sum(1 for item in results if not item["passed"])
    total = len(results)
    warnings = list(selection.public_data.get("warnings") or [])
    warnings.extend(rule_warnings)
    if not selected_documents:
        warnings.append("未命中可质控文书")
    if skipped_rules:
        warnings.append(f"{len(skipped_rules)} 条规则因执行边界限制被跳过")
    warnings = _unique_text_items(warnings)
    public = {
        "record_summary": selection.public_data.get("record_summary", {}),
        "document_summary": selection.public_data.get("selection_summary", {}),
        "document_selection_summary": selection.public_data.get("selection_summary", {}),
        "selected_rules": [_rule_summary_public(rule) for rule in selected_rules],
        "executed_rules": results,
        "skipped_rules": skipped_rules,
        "qc_summary": {
            "rule_count": len(selected_rules) + len([item for item in skipped_rules if item.get("reason") == "unknown_rule"]),
            "total_rules": total,
            "passed": passed,
            "failed": failed,
            "passed_count": passed,
            "skipped_count": len(skipped_rules),
            "issue_count": failed,
            "pass_rate": round(passed / total, 4) if total else 1.0,
        },
        "issues": selected_results,
        "warnings": warnings,
    }
    public = _drop_sensitive_keys(public)
    assert_no_sensitive_output(public)
    return AgentToolObservation(
        tool_name="run_document_qc",
        status="success",
        public_data=public,
        internal_data={
            "record_summary": public["record_summary"],
            "selected_documents": selected_documents,
            "rule_results": results,
        },
    )


def list_qc_rules(payload: BaseModel | Dict[str, Any]) -> AgentToolObservation:
    if isinstance(payload, ListQCRulesInput):
        params = payload
    elif isinstance(payload, dict):
        params = ListQCRulesInput(**payload)
    else:
        params = ListQCRulesInput(**payload.model_dump())
    rules, warnings = filter_rule_catalog(**params.model_dump())
    public = {
        "total": len(get_rule_catalog()),
        "returned": len(rules),
        "filters": params.model_dump(),
        "rules": [rule.to_public_dict() for rule in rules],
        "warnings": warnings,
    }
    public = _drop_sensitive_keys(public)
    assert_no_sensitive_output(public)
    return AgentToolObservation(
        tool_name="list_qc_rules",
        status="success",
        public_data=public,
        internal_data={"candidate_rule_ids": [rule.rule_id for rule in rules]},
    )


def resolve_rule_scope(payload: BaseModel | Dict[str, Any]) -> AgentToolObservation:
    if isinstance(payload, ResolveRuleScopeInput):
        params = payload
    elif isinstance(payload, dict):
        params = ResolveRuleScopeInput(**payload)
    else:
        params = ResolveRuleScopeInput(**payload.model_dump())
    rules, warnings = filter_rule_catalog(**params.model_dump())
    rule_ids = [rule.rule_id for rule in rules]
    if not rule_ids and not warnings:
        warnings.append("未匹配到可用质控规则")
    public = {
        "rule_ids": rule_ids,
        "rule_count": len(rule_ids),
        "rules": [rule.to_public_dict() for rule in rules],
        "filters": params.model_dump(),
        "warnings": warnings,
    }
    public = _drop_sensitive_keys(public)
    assert_no_sensitive_output(public)
    return AgentToolObservation(
        tool_name="resolve_rule_scope",
        status="success",
        public_data=public,
        internal_data={"rule_ids": rule_ids},
    )


def _run_awaitable_blocking(awaitable: Any) -> Any:
    """在同步工具处理器中执行 async 服务，避免污染当前事件循环。"""
    result_box: List[Any] = []
    error_box: List[BaseException] = []

    def _runner() -> None:
        try:
            import asyncio

            result_box.append(asyncio.run(awaitable))
        except BaseException as exc:  # pragma: no cover - 透传线程内异常
            error_box.append(exc)

    thread = threading.Thread(target=_runner, daemon=True)
    thread.start()
    thread.join()
    if error_box:
        raise error_box[0]
    return result_box[0] if result_box else None


def _icd_type_to_dataset_type(code_type: str) -> str:
    if code_type == "diagnosis":
        return "icd10"
    if code_type == "procedure":
        return "icd9cm3"
    return "all"


def _icd_public_type(dataset_type: str) -> str:
    return "procedure" if dataset_type == "icd9cm3" else "diagnosis"


def _icd_match_type(query: str, item: Dict[str, Any]) -> str:
    explicit_match_type = _text(item.get("_match_type"))
    if explicit_match_type:
        return explicit_match_type
    query_lower = query.lower()
    code = _text(item.get("code")).lower()
    name = _text(item.get("name")).lower()
    if code == query_lower:
        return "exact_code"
    if code.startswith(query_lower):
        return "code_prefix"
    if name == query_lower:
        return "exact_name"
    if query_lower in name:
        return "name_contains"
    if query_lower in code:
        return "code_contains"
    return "local_fuzzy"


def _is_icd_code_query(query: str) -> bool:
    text = _text(query)
    return bool(
        re.fullmatch(r"[A-Za-z]\d{2}(?:\.[A-Za-z0-9]{1,8})?", text)
        or re.fullmatch(r"\d{2}\.\d{2,6}", text)
    )


def _normalize_icd_similarity_text(value: str) -> str:
    return re.sub(r"[\s()（）,，;；:：。.\-_/]+", "", _text(value).lower())


def _severity_rank_hints(query: str) -> set[str]:
    text = _normalize_icd_similarity_text(query)
    hints: set[str] = set()
    if any(token in text for token in ("重度", "严重", "重型", "3级", "三级", "ⅲ级", "iii级")):
        hints.update({"3级", "恶性", "危象", "急症", "极高危"})
    if any(token in text for token in ("中度", "2级", "二级", "ⅱ级", "ii级")):
        hints.update({"2级", "中危", "高危"})
    if any(token in text for token in ("轻度", "1级", "一级", "ⅰ级", "i级")):
        hints.update({"1级", "低危"})
    return hints


def _char_set_score(query: str, name: str) -> float:
    query_chars = set(_normalize_icd_similarity_text(query))
    name_chars = set(_normalize_icd_similarity_text(name))
    if not query_chars or not name_chars:
        return 0.0
    return len(query_chars & name_chars) / max(1, len(query_chars | name_chars))


def _fallback_icd10_similarity_results(query: str, *, version: str, limit: int) -> List[Dict[str, Any]]:
    try:
        from app.routers import icd_search as icd_mod

        source = (
            icd_mod._icd10_clinical_data
            if version == "clinical" and icd_mod._icd10_clinical_data
            else icd_mod._icd10_data
        )
    except Exception:
        return []
    query_norm = _normalize_icd_similarity_text(query)
    if not query_norm:
        return []
    severity_hints = _severity_rank_hints(query)
    scored: List[Dict[str, Any]] = []
    for item in source:
        name = _text(item.get("name"))
        code = _text(item.get("code"))
        if not name or not code:
            continue
        name_norm = _normalize_icd_similarity_text(name)
        ratio = SequenceMatcher(None, query_norm, name_norm).ratio()
        char_score = _char_set_score(query_norm, name_norm)
        contains_score = 0.25 if query_norm in name_norm or name_norm in query_norm else 0.0
        severity_score = 0.0
        if severity_hints and any(hint in name for hint in severity_hints):
            severity_score = 0.3
        score = min(1.0, ratio * 0.5 + char_score * 0.35 + contains_score + severity_score)
        if score <= 0:
            continue
        scored.append(
            {
                "code": code,
                "name": name,
                "type": "icd10",
                "_score": max(1, min(100, round(score * 100, 2))),
                "_match_type": "local_similarity",
            }
        )
    scored.sort(key=lambda item: -float(item.get("_score") or 0))
    return scored[: max(1, limit)]


def _semantic_icd10_results(query: str, *, version: str, limit: int) -> tuple[List[Dict[str, Any]], List[str]]:
    try:
        from app.routers import icd_search as icd_mod
        from app.services.icd_semantic_retrieval_service import get_icd_semantic_retrieval_service

        service = get_icd_semantic_retrieval_service()
        semantic_results = service.search_diagnosis(
            query,
            prefer_insurance=(version != "clinical"),
            top_k=max(1, limit),
            min_score=0.0,
        )
    except Exception as exc:
        fallback = _fallback_icd10_similarity_results(query, version=version, limit=limit)
        return fallback, [f"语义索引检索不可用，已使用本地相似度兜底: {type(exc).__name__}"]

    output: List[Dict[str, Any]] = []
    for item in semantic_results:
        code = _text(item.get("code"))
        name = _text(item.get("name"))
        if not code or not name:
            continue
        semantic_version = _text(item.get("version"))
        if version != "clinical" and semantic_version == "clinical":
            mapped = ((icd_mod._code_mapping or {}).get("clinical_to_insurance") or {}).get(code)
            if isinstance(mapped, dict) and mapped.get("code"):
                code = _text(mapped.get("code"))
                name = _text(mapped.get("name")) or name
        elif version == "clinical" and semantic_version == "insurance":
            mapped = ((icd_mod._code_mapping or {}).get("insurance_to_clinical") or {}).get(code)
            if isinstance(mapped, dict) and mapped.get("code"):
                code = _text(mapped.get("code"))
                name = _text(mapped.get("name")) or name
        score = float(item.get("score") or 0)
        output.append(
            {
                "code": code,
                "name": name,
                "type": "icd10",
                "_score": max(1, min(100, round(score * 100, 2))),
                "_match_type": "semantic",
            }
        )
    if output:
        return output, []
    fallback = _fallback_icd10_similarity_results(query, version=version, limit=limit)
    if fallback:
        return fallback, ["语义索引未返回候选，已使用本地相似度兜底"]
    return [], []


def _apply_icd_mapping(item: Dict[str, Any], version: str) -> None:
    if item.get("type") != "icd10":
        return
    try:
        from app.routers import icd_search as icd_mod

        mapping = icd_mod._code_mapping or {}
    except Exception:
        mapping = {}
    if not mapping:
        return
    code = _text(item.get("code"))
    if version == "clinical":
        mapped = (mapping.get("clinical_to_insurance") or {}).get(code)
        if mapped:
            item["mapped_code"] = _text(mapped.get("code"))
            item["mapped_name"] = _text(mapped.get("name"))
            item["mapped_version"] = "insurance"
        return
    c2i = mapping.get("clinical_to_insurance") or {}
    i2c = mapping.get("insurance_to_clinical") or {}
    if code in c2i and (c2i.get(code) or {}).get("code") == code:
        item["mapped_code"] = code
        item["mapped_name"] = _text(item.get("name"))
        item["mapped_version"] = "clinical"
    elif code in i2c:
        mapped = i2c[code]
        item["mapped_code"] = _text(mapped.get("code"))
        item["mapped_name"] = _text(mapped.get("name"))
        item["mapped_version"] = "clinical"


def _search_icd_candidates(
    *,
    query: str,
    code_type: str,
    version: str,
    limit: int,
) -> tuple[List[Dict[str, Any]], List[str]]:
    warnings: List[str] = []
    try:
        from app.routers import icd_search as icd_mod

        icd_mod._load_data()
        dataset_type = _icd_type_to_dataset_type(code_type)
        literal_results: List[Dict[str, Any]] = []
        if dataset_type in {"icd10", "all"}:
            icd10_source = (
                icd_mod._icd10_clinical_data
                if version == "clinical" and icd_mod._icd10_clinical_data
                else icd_mod._icd10_data
            )
            literal_results.extend(icd_mod._search_dataset(icd10_source, query, "icd10"))
        if dataset_type in {"icd9cm3", "all"}:
            literal_results.extend(icd_mod._search_dataset(icd_mod._icd9cm3_data, query, "icd9cm3"))

        semantic_results: List[Dict[str, Any]] = []
        if dataset_type in {"icd10", "all"} and not _is_icd_code_query(query):
            semantic_results, semantic_warnings = _semantic_icd10_results(query, version=version, limit=limit)
            warnings.extend(semantic_warnings)

        raw_results = (
            literal_results + semantic_results
            if _is_icd_code_query(query)
            else semantic_results + literal_results
        )
    except Exception as exc:
        return [], [f"本地 ICD 编码库检索失败: {type(exc).__name__}"]

    raw_results.sort(key=lambda item: -int(item.get("_score") or 0))
    candidates: List[Dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for item in raw_results:
        key = (_text(item.get("type")), _text(item.get("code")))
        if key in seen:
            continue
        seen.add(key)
        score = float(item.get("_score") or 0)
        public_item = {
            "code": _text(item.get("code")),
            "name": _text(item.get("name")),
            "type": _icd_public_type(_text(item.get("type"))),
            "version": "icd9cm3" if item.get("type") == "icd9cm3" else version,
            "mapped_code": "",
            "mapped_name": "",
            "confidence": round(min(score, 100.0) / 100.0, 4),
            "match_type": _icd_match_type(query, item),
        }
        _apply_icd_mapping(public_item | {"type": item.get("type")}, version)
        if public_item.get("type") == "diagnosis":
            mapped_probe = public_item | {"type": "icd10"}
            _apply_icd_mapping(mapped_probe, version)
            public_item["mapped_code"] = _text(mapped_probe.get("mapped_code"))
            public_item["mapped_name"] = _text(mapped_probe.get("mapped_name"))
        candidates.append(public_item)
        if len(candidates) >= limit:
            break
    if not candidates:
        warnings.append("未匹配到本地 ICD 编码候选")
    return candidates, warnings


def search_icd_codes(payload: BaseModel | Dict[str, Any]) -> AgentToolObservation:
    if isinstance(payload, SearchICDCodesInput):
        params = payload
    elif isinstance(payload, dict):
        params = SearchICDCodesInput(**payload)
    else:
        params = SearchICDCodesInput(**payload.model_dump())
    candidates, warnings = _search_icd_candidates(
        query=params.query,
        code_type=params.code_type,
        version=params.version,
        limit=params.limit,
    )
    public = {
        "query": params.query,
        "code_type": params.code_type,
        "version": params.version,
        "returned": len(candidates),
        "candidates": candidates,
        "warnings": warnings,
    }
    public = _drop_sensitive_keys(public)
    assert_no_sensitive_output(public)
    return AgentToolObservation(
        tool_name="search_icd_codes",
        status="success",
        public_data=public,
        internal_data={"candidate_count": len(candidates)},
    )


def _item_name_code(item: Dict[str, Any], name_keys: Iterable[str], code_keys: Iterable[str]) -> tuple[str, str]:
    name = _text(_first_column_value(item, name_keys))
    code = _text(_first_column_value(item, code_keys))
    return name, code


def _dedupe_coding_items(items: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
    deduped: List[Dict[str, Any]] = []
    seen: set[tuple[str, str, str]] = set()
    for item in items:
        key = (_text(item.get("name")), _text(item.get("code")), _text(item.get("type")))
        if not key[0] and not key[1]:
            continue
        if key in seen:
            continue
        seen.add(key)
        deduped.append(item)
    return deduped


def _extract_structured_coding_items(value: Any) -> tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    diagnoses: List[Dict[str, Any]] = []
    procedures: List[Dict[str, Any]] = []
    if isinstance(value, dict):
        for key, item in value.items():
            if key in {"diagnoses", "diagnosis_list", "diagnosis_candidates"}:
                child_diag, child_proc = _extract_structured_coding_items(item)
                diagnoses.extend(child_diag)
                procedures.extend(child_proc)
                continue
            if key in {"surgeries", "procedures", "procedure_list", "operations", "operation_list"}:
                child_diag, child_proc = _extract_structured_coding_items(item)
                diagnoses.extend(child_diag)
                procedures.extend(child_proc)
                continue
        diag_name, diag_code = _item_name_code(
            value,
            ("diagnosis_name", "diagnosis_text", "name", "text", "discharge_main_diagnosis_text"),
            ("diagnosis_code", "icd_code", "code", "discharge_main_icd"),
        )
        if diag_name or diag_code:
            diagnoses.append(
                {
                    "name": diag_name,
                    "code": diag_code,
                    "type": _text(value.get("diagnosis_type") or "diagnosis"),
                    "source": _text(value.get("source") or value.get("source_name") or "结构化字段"),
                    "confidence": 0.9 if diag_code else 0.75,
                }
            )
        proc_name, proc_code = _item_name_code(
            value,
            ("procedure_name", "surgery_name", "operation_name", "main_procedure_text", "name", "text"),
            ("procedure_code", "surgery_code", "operation_code", "main_procedure_code", "code"),
        )
        if proc_name or proc_code:
            procedures.append(
                {
                    "name": proc_name,
                    "code": proc_code,
                    "type": "procedure",
                    "source": _text(value.get("source") or value.get("source_name") or "结构化字段"),
                    "confidence": 0.9 if proc_code else 0.75,
                }
            )
    elif isinstance(value, list):
        for item in value:
            child_diag, child_proc = _extract_structured_coding_items(item)
            diagnoses.extend(child_diag)
            procedures.extend(child_proc)
    return diagnoses, procedures


def _extract_text_coding_items(medical_text: str) -> tuple[List[Dict[str, Any]], List[Dict[str, Any]], List[str]]:
    warnings: List[str] = []
    diagnoses = [
        {
            "name": _text(item.get("diagnosis_name")),
            "code": _text(item.get("diagnosis_code")),
            "type": _text(item.get("diagnosis_type") or "diagnosis"),
            "source": "explicit_record_field",
            "confidence": 0.65 if item.get("diagnosis_code") else 0.55,
        }
        for item in _extract_diagnoses(medical_text)
    ]
    procedures = [
        {
            "name": _text(item.get("surgery_name")),
            "code": _text(item.get("surgery_code")),
            "type": "procedure",
            "source": "explicit_record_field",
            "confidence": 0.65 if item.get("surgery_code") else 0.55,
        }
        for item in _extract_surgeries(medical_text)
    ]
    if diagnoses or procedures:
        warnings.append("部分编码建议来自病历文本显式字段，未做全文医学推断，置信度按低到中等处理")
    return diagnoses, procedures, warnings


def _candidate_recommendations(item: Dict[str, Any], *, code_type: str, limit: int) -> List[Dict[str, Any]]:
    query = _text(item.get("code") or item.get("name"))
    if not query:
        return []
    candidates, _ = _search_icd_candidates(
        query=query,
        code_type=code_type,
        version="insurance",
        limit=limit,
    )
    return candidates


def _coding_candidate(item: Dict[str, Any], *, code_type: str, limit: int) -> Dict[str, Any]:
    candidates = _candidate_recommendations(item, code_type=code_type, limit=limit)
    existing_code = _text(item.get("code"))
    return {
        "name": _text(item.get("name")),
        "existing_code": existing_code,
        "source": _text(item.get("source")),
        "confidence": item.get("confidence", 0.5),
        "low_confidence": float(item.get("confidence") or 0) < 0.7,
        "candidates": candidates,
    }


def suggest_record_icd_codes(
    payload: BaseModel | Dict[str, Any],
    workspace: CustomQCWorkspaceService | None = None,
) -> AgentToolObservation:
    if isinstance(payload, SuggestRecordICDCodesInput):
        params = payload
    elif isinstance(payload, dict):
        params = SuggestRecordICDCodesInput(**payload)
    else:
        params = SuggestRecordICDCodesInput(**payload.model_dump())
    _ensure_single_visit_id(params.visit_id, "suggest_record_icd_codes")
    context = get_record_context(
        GetRecordContextInput(
            visit_id=params.visit_id,
            patient_id=params.patient_id,
            scene="coding",
            include_preview=False,
        ),
        workspace=workspace,
    )
    internal_context = context.internal_data or {}
    record_summary = dict(internal_context.get("record_summary") or {})
    diagnoses, procedures = _extract_structured_coding_items(internal_context.get("structured_context"))
    text_diagnoses, text_procedures, extraction_warnings = _extract_text_coding_items(
        _text(internal_context.get("medical_text"))
    )
    diagnoses.extend(text_diagnoses)
    procedures.extend(text_procedures)
    diagnoses = _dedupe_coding_items(diagnoses)
    procedures = _dedupe_coding_items(procedures)
    warnings = list(context.public_data.get("warnings") or [])
    warnings.extend(extraction_warnings)
    if not diagnoses:
        warnings.append("未从结构化上下文或文本显式字段提取到诊断名称/编码")
    if params.include_procedures and not procedures:
        warnings.append("未从结构化上下文或文本显式字段提取到手术/操作名称或编码")
    public = {
        "record_summary": record_summary,
        "diagnosis_candidates": [
            _coding_candidate(item, code_type="diagnosis", limit=params.limit_per_item)
            for item in diagnoses
        ],
        "procedure_candidates": [
            _coding_candidate(item, code_type="procedure", limit=params.limit_per_item)
            for item in procedures
        ]
        if params.include_procedures
        else [],
        "warnings": _unique_text_items(warnings),
    }
    public = _drop_sensitive_keys(public)
    assert_no_sensitive_output(public)
    return AgentToolObservation(
        tool_name="suggest_record_icd_codes",
        status="success",
        public_data=public,
        internal_data={
            "record_ref": {
                "visit_id": record_summary.get("visit_id", ""),
                "patient_id": record_summary.get("patient_id", ""),
            },
            "diagnosis_item_count": len(diagnoses),
            "procedure_item_count": len(procedures),
        },
    )


def predict_dip_group(
    payload: BaseModel | Dict[str, Any],
    dip_service: Any | None = None,
) -> AgentToolObservation:
    if isinstance(payload, PredictDIPGroupInput):
        params = payload
    elif isinstance(payload, dict):
        params = PredictDIPGroupInput(**payload)
    else:
        params = PredictDIPGroupInput(**payload.model_dump())
    service = dip_service
    if service is None:
        from app.services.dip_grouping_service import DIPGrouperService

        service = DIPGrouperService()
    proc_code = params.proc_codes[0] if params.proc_codes else ""
    result = _run_awaitable_blocking(
        service.group_dip(
            city_name=params.city_name,
            pdx_code=params.pdx_code,
            adx_code=",".join(params.adx_codes),
            proc_code=proc_code,
            patient_gender=params.patient_gender or "M",
            patient_age=params.patient_age or 50,
            los=params.los or 7,
            total_fee=params.total_fee or 0,
        )
    )
    warnings: List[str] = []
    if len(params.proc_codes) > 1:
        warnings.append("当前 DIP 本地入组服务仅消费首个手术/操作编码")
    public = {
        "success": bool(result.get("success")),
        "dip_code": _text(result.get("dip_code")),
        "dip_name": _text(result.get("dip_name")),
        "dip_type": _text(result.get("dip_type")),
        "grouping_path": _text(result.get("grouping_path")),
        "input_summary": {
            "city_name": params.city_name,
            "pdx_code": params.pdx_code,
            "adx_count": len(params.adx_codes),
            "proc_count": len(params.proc_codes),
            "patient_gender": params.patient_gender or "M",
            "patient_age": params.patient_age or 50,
            "los": params.los or 7,
            "total_fee": params.total_fee or 0,
        },
        "warnings": _unique_text_items(warnings),
    }
    public = _drop_sensitive_keys(public)
    assert_no_sensitive_output(public)
    return AgentToolObservation(
        tool_name="predict_dip_group",
        status="success",
        public_data=public,
        internal_data={"pdx_code": params.pdx_code, "proc_code": proc_code},
    )


def _error_summary(value: Any) -> str:
    sanitized = _mask_sensitive_text(_text(value))
    sanitized = re.sub(r"(?i)(token|access_token|api_key|password)\s*[=:：]\s*[^,\s;；]+", r"\1=[已脱敏]", sanitized)
    sanitized = re.sub(r"(?i)(raw_response|api_response|embedding|vector)", "[已过滤]", sanitized)
    return sanitized[:300]


def predict_drg_group(
    payload: BaseModel | Dict[str, Any],
    drg_service: Any | None = None,
) -> AgentToolObservation:
    if isinstance(payload, PredictDRGGroupInput):
        params = payload
    elif isinstance(payload, dict):
        params = PredictDRGGroupInput(**payload)
    else:
        params = PredictDRGGroupInput(**payload.model_dump())
    if drg_service is None:
        from app.services.drg_grouping_service import get_drg_grouping_service

        drg_service = get_drg_grouping_service()
    warnings: List[str] = ["DRG 实时入组会调用外部分组服务，当前工具仅返回只读预测摘要"]
    try:
        result = _run_awaitable_blocking(
            drg_service.group_drg(
                primary_diagnosis=params.primary_diagnosis_code,
                secondary_diagnoses=params.secondary_diagnosis_codes,
                procedures=params.procedure_codes,
                patient_age=params.patient_age or 50,
                patient_gender=params.patient_gender or "M",
                los=params.los or 7,
                city_name=params.region or "四川省",
                total_fee=params.total_cost or 0,
            )
        )
    except Exception as exc:
        result = {
            "success": False,
            "fallback": True,
            "adrg_code": "",
            "adrg_name": "",
            "drg_code": "",
            "drg_name": "",
            "grouping_logic": "外部分组服务调用失败",
            "error_summary": f"{type(exc).__name__}: {_error_summary(exc)}",
        }
    success = bool(result.get("success"))
    fallback = bool(result.get("fallback")) or not success
    error_summary = _error_summary(result.get("error_summary") or result.get("error")) if fallback else ""
    if fallback:
        warnings.append("DRG 外部分组失败或未入组，已返回受控 fallback 摘要")
    public = {
        "success": success,
        "fallback": fallback,
        "external_call": True,
        "error_summary": error_summary,
        "input_summary": {
            "primary_diagnosis_code": params.primary_diagnosis_code,
            "secondary_diagnosis_count": len(params.secondary_diagnosis_codes),
            "procedure_count": len(params.procedure_codes),
            "patient_age": params.patient_age or 50,
            "patient_gender": params.patient_gender or "M",
            "los": params.los or 7,
            "total_cost": params.total_cost or 0,
            "region": params.region or "四川省",
        },
        "adrg_code": _text(result.get("adrg_code")),
        "adrg_name": _text(result.get("adrg_name")),
        "drg_code": _text(result.get("drg_code")),
        "drg_name": _text(result.get("drg_name")),
        "weight": result.get("weight"),
        "baseline_payment": result.get("baseline_payment"),
        "profit_margin": result.get("profit_margin"),
        "mapped_code": _text(result.get("mapped_code")),
        "mapped_code_name": _text(result.get("mapped_code_name")),
        "grouping_logic": _text(result.get("grouping_logic")),
        "warnings": _unique_text_items(warnings),
    }
    public = _drop_sensitive_keys(public)
    assert_no_sensitive_output(public)
    return AgentToolObservation(
        tool_name="predict_drg_group",
        status="success",
        public_data=public,
        internal_data={"external_call": True, "fallback": fallback},
    )


def register_default_tools(registry: AgentToolRegistry) -> AgentToolRegistry:
    registry.register(
        name="search_records",
        description="按安全筛选条件检索病历索引摘要；不返回病历全文。",
        input_model=SearchRecordsInput,
        handler=search_records,
        risk_level="low",
        writes_db=False,
        requires_confirmation=False,
        timeout_ms=5000,
        max_records=50,
    )
    registry.register(
        name="get_record_context",
        description="按 visit_id 只读获取单份病历上下文；API 仅返回摘要和脱敏预览。",
        input_model=GetRecordContextInput,
        handler=get_record_context,
        risk_level="medium",
        writes_db=False,
        requires_confirmation=False,
        timeout_ms=5000,
        max_records=1,
    )
    registry.register(
        name="run_frontpage_qc",
        description="对单份病历生成瞬态首页草稿并执行首页形式质控；不保存草稿或质控结果。",
        input_model=RunFrontpageQCInput,
        handler=run_frontpage_qc,
        risk_level="medium",
        writes_db=False,
        requires_confirmation=False,
        timeout_ms=30000,
        max_records=1,
    )
    registry.register(
        name="select_record_documents",
        description="按 visit_id 只读选择单份病历的目标文书；API 仅返回摘要和脱敏预览。",
        input_model=SelectRecordDocumentsInput,
        handler=select_record_documents,
        risk_level="medium",
        writes_db=False,
        requires_confirmation=False,
        timeout_ms=5000,
        max_records=1,
    )
    registry.register(
        name="run_document_qc",
        description="对单份病历目标文书执行内置只读文书质控；不保存质控结果。",
        input_model=RunDocumentQCInput,
        handler=run_document_qc,
        risk_level="medium",
        writes_db=False,
        requires_confirmation=False,
        timeout_ms=30000,
        max_records=1,
    )
    registry.register(
        name="list_qc_rules",
        description="只读查询可用于 Agent 的质控规则目录；仅返回规则摘要，不返回 prompt 或示例。",
        input_model=ListQCRulesInput,
        handler=list_qc_rules,
        risk_level="low",
        writes_db=False,
        requires_confirmation=False,
        timeout_ms=5000,
        max_records=1,
    )
    registry.register(
        name="resolve_rule_scope",
        description="按结构化条件解析可选 rule_ids，供后续单病历质控工具消费。",
        input_model=ResolveRuleScopeInput,
        handler=resolve_rule_scope,
        risk_level="low",
        writes_db=False,
        requires_confirmation=False,
        timeout_ms=5000,
        max_records=1,
    )
    registry.register(
        name="search_icd_codes",
        description="只读检索本地 ICD-10/ICD-9-CM-3 编码候选；不依赖向量文件。",
        input_model=SearchICDCodesInput,
        handler=search_icd_codes,
        risk_level="low",
        writes_db=False,
        requires_confirmation=False,
        timeout_ms=5000,
        max_records=50,
    )
    registry.register(
        name="suggest_record_icd_codes",
        description="按单份病历已有诊断/手术字段推荐 ICD 编码候选；不做全文医学推断。",
        input_model=SuggestRecordICDCodesInput,
        handler=suggest_record_icd_codes,
        risk_level="medium",
        writes_db=False,
        requires_confirmation=False,
        timeout_ms=10000,
        max_records=1,
    )
    registry.register(
        name="predict_dip_group",
        description="只读执行 DIP 入组预测，返回分组摘要和输入摘要。",
        input_model=PredictDIPGroupInput,
        handler=predict_dip_group,
        risk_level="medium",
        writes_db=False,
        requires_confirmation=False,
        timeout_ms=10000,
        max_records=1,
    )
    registry.register(
        name="predict_drg_group",
        description="只读执行 DRG 实时入组预测；外部失败时返回受控 fallback 摘要。",
        input_model=PredictDRGGroupInput,
        handler=predict_drg_group,
        risk_level="medium",
        writes_db=False,
        requires_confirmation=False,
        timeout_ms=30000,
        max_records=1,
    )
    return registry


def create_default_registry() -> AgentToolRegistry:
    return register_default_tools(AgentToolRegistry())


def contains_sensitive_keys(records: Iterable[Dict[str, Any]]) -> bool:
    for record in records:
        if SENSITIVE_OUTPUT_KEYS.intersection({str(key) for key in record.keys()}):
            return True
    return False
