from fastapi import APIRouter, HTTPException, Request
from ..core.response import success_response, paginated_response, error_response, get_trace_id, ErrorCode, StatusCode
from ..schemas.ingest import LLMParseResultSave
from ..services.records_ingest_service import ingest_llm_parse_result
from ..schemas.records import MedicalRecordResponse

router = APIRouter(prefix="/api/v1", tags=["ingest"])


@router.post("/medical-records", response_model=MedicalRecordResponse)
async def save_llm_parse_result(
    request: Request,data: LLMParseResultSave):
    try:
        res = await ingest_llm_parse_result(data.model_dump())
        return MedicalRecordResponse(**res)
    except Exception as e:
        raise HTTPException(status_code=StatusCode.INTERNAL_SERVER_ERROR, detail=f"保存失败: {e}")

