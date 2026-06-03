from __future__ import annotations

import re
from typing import Any, Dict, Iterable, List

from fastapi import HTTPException, status
from pydantic import BaseModel

from app.services.custom_qc_workspace_service import CustomQCWorkspaceService

from .schemas import (
    AgentToolObservation,
    GetRecordContextInput,
    RecordSummary,
    SearchRecordsInput,
    SearchRecordsPublicData,
)
from .tool_registry import AgentToolRegistry


SENSITIVE_OUTPUT_KEYS = {
    "medical_text",
    "record_content",
    "documents",
    "bundle",
    "structured_context",
    "text_preview",
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
    for key in ("content", "text", "medical_text", "record_content"):
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


def _summarize_documents(documents: Any) -> List[Dict[str, Any]]:
    if not isinstance(documents, list):
        return []
    grouped: Dict[str, Dict[str, Any]] = {}
    for document in documents:
        if not isinstance(document, dict):
            continue
        doc_type = _document_type(document)
        summary = grouped.setdefault(
            doc_type,
            {
                "document_type": doc_type,
                "count": 0,
                "text_length": 0,
                "latest_time": "",
            },
        )
        summary["count"] += 1
        summary["text_length"] += len(_extract_document_text(document))
        doc_time = _document_time(document)
        if doc_time and doc_time > summary["latest_time"]:
            summary["latest_time"] = doc_time
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
    document_summary = _summarize_documents(documents)
    warnings: List[str] = []
    if not medical_text:
        warnings.append("未读取到病历文本")
    if not document_summary and medical_text:
        document_summary = [
            {
                "document_type": "合并病历文本",
                "count": 1,
                "text_length": len(medical_text),
                "latest_time": "",
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
    return registry


def create_default_registry() -> AgentToolRegistry:
    return register_default_tools(AgentToolRegistry())


def contains_sensitive_keys(records: Iterable[Dict[str, Any]]) -> bool:
    for record in records:
        if SENSITIVE_OUTPUT_KEYS.intersection({str(key) for key in record.keys()}):
            return True
    return False
