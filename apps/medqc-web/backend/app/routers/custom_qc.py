import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, Request
from fastapi import HTTPException
from pydantic import BaseModel, Field

from ..core.response import get_trace_id, success_response
from ..core.security import require_roles
from ..services.custom_qc_service import (
    create_custom_qc_service,
    ensure_record_medical_text,
    evaluate_inline_rule,
    generate_custom_prompt,
)
from ..services.sichuan_qc_service import SichuanQCService

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/v1/custom-qc",
    tags=["custom-qc"],
    dependencies=[Depends(require_roles("admin", "qc_manager"))],
)


async def get_custom_qc_service() -> SichuanQCService:
    return await create_custom_qc_service()


class PromptGenerateRequest(BaseModel):
    scene: str = Field(..., description="场景 running|final")
    document_type: str = Field(..., description="文书类型")
    rule_name: str = Field(..., description="质控点名称")
    description: str = Field(..., description="质控点描述")
    severity: str = Field(..., description="严重程度 critical|major|minor")


class DraftRulePayload(BaseModel):
    name: str
    description: str
    prompt_template: str
    severity: str = "major"
    document_type: str = "病程记录"
    scene: Optional[str] = None
    check_logic: Dict[str, Any] = Field(default_factory=dict)


class DraftRecordPayload(BaseModel):
    visit_id: Optional[str] = None
    record_id: str
    patient_name: Optional[str] = None
    department: Optional[str] = None
    medical_text: str


class CustomQCTestRequest(BaseModel):
    rule: DraftRulePayload
    records: List[DraftRecordPayload]
    temperature: Optional[float] = None
    top_p: Optional[float] = None
    max_tokens: Optional[int] = None


@router.post("/prompt/generate")
async def generate_prompt(request: Request, payload: PromptGenerateRequest):
    result = await generate_custom_prompt(
        scene=payload.scene,
        document_type=payload.document_type,
        rule_name=payload.rule_name,
        description=payload.description,
        severity=payload.severity,
    )
    return success_response(
        data=result,
        message="生成自定义质控 Prompt 成功",
        trace_id=get_trace_id(request),
    )


@router.post("/test")
async def test_custom_qc_single(
    request: Request,
    payload: CustomQCTestRequest,
    qc_service: SichuanQCService = Depends(get_custom_qc_service),
):
    if not payload.records:
        raise HTTPException(status_code=422, detail="至少需要提供一条病历")
    ensure_record_medical_text([record.model_dump() for record in payload.records])
    record = payload.records[0]
    result = await evaluate_inline_rule(
        qc_service=qc_service,
        rule=payload.rule.model_dump(),
        record=record.model_dump(),
        temperature=payload.temperature,
        top_p=payload.top_p,
        max_tokens=payload.max_tokens,
    )

    response = {
        "rule": payload.rule.model_dump(),
        "record": {
            "record_id": record.record_id,
            "visit_id": record.visit_id,
            "patient_name": record.patient_name,
            "department": record.department,
        },
        "result": result,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "status": "success",
    }
    return success_response(
        data=response,
        message="单病历测试完成",
        trace_id=get_trace_id(request),
    )


@router.post("/test/batch")
async def test_custom_qc_batch(
    request: Request,
    payload: CustomQCTestRequest,
    qc_service: SichuanQCService = Depends(get_custom_qc_service),
):
    if not payload.records:
        raise HTTPException(status_code=422, detail="至少需要提供一条病历")
    record_dicts = [record.model_dump() for record in payload.records]
    ensure_record_medical_text(record_dicts)

    items: List[Dict[str, Any]] = []
    failed_records: List[Dict[str, Any]] = []
    total_tokens = 0
    total_processing_time = 0.0

    for record in record_dicts:
        try:
            result = await evaluate_inline_rule(
                qc_service=qc_service,
                rule=payload.rule.model_dump(),
                record=record,
                temperature=payload.temperature,
                top_p=payload.top_p,
                max_tokens=payload.max_tokens,
            )
            total_tokens += int((result.get("performance") or {}).get("token_usage") or 0)
            total_processing_time += float(
                (result.get("performance") or {}).get("processing_time") or 0.0
            )
            items.append(result)
        except Exception as exc:
            logger.warning("custom-qc 批量测试单条病历失败: %s", exc)
            failed_item = {
                "record_id": str(record.get("record_id") or ""),
                "visit_id": str(record.get("visit_id") or ""),
                "patient_name": str(record.get("patient_name") or ""),
                "department": str(record.get("department") or ""),
                "error": str(exc),
            }
            failed_records.append(failed_item)

    summary = {
        "total_records": len(record_dicts),
        "success_count": len(items),
        "failed_count": len(failed_records),
        "issue_records": sum(1 for item in items if item.get("status") == "non_compliant"),
        "compliant_records": sum(
            1 for item in items if item.get("status") in {"compliant", "not_applicable"}
        ),
        "total_tokens": total_tokens,
        "total_processing_time": total_processing_time,
    }

    response = {
        "rule": payload.rule.model_dump(),
        "summary": summary,
        "items": items,
        "failed_records": failed_records,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "status": "success",
    }
    return success_response(
        data=response,
        message="批量病历测试完成",
        trace_id=get_trace_id(request),
    )
