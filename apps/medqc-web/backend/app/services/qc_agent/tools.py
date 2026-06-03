from __future__ import annotations

from typing import Any, Dict, Iterable, List

from pydantic import BaseModel

from app.services.custom_qc_workspace_service import CustomQCWorkspaceService

from .schemas import AgentToolObservation, RecordSummary, SearchRecordsInput, SearchRecordsPublicData
from .tool_registry import AgentToolRegistry


SENSITIVE_OUTPUT_KEYS = {
    "medical_text",
    "record_content",
    "documents",
    "bundle",
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
    return registry


def create_default_registry() -> AgentToolRegistry:
    return register_default_tools(AgentToolRegistry())


def contains_sensitive_keys(records: Iterable[Dict[str, Any]]) -> bool:
    for record in records:
        if SENSITIVE_OUTPUT_KEYS.intersection({str(key) for key in record.keys()}):
            return True
    return False

