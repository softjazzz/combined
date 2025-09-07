from fastapi import APIRouter, HTTPException
from ..schemas.ingest import LLMParseResultSave
from ..services.records_ingest_service import ingest_llm_parse_result
from ..schemas.records import MedicalRecordResponse

router = APIRouter(prefix="/api", tags=["ingest"])


@router.post("/medical-records", response_model=MedicalRecordResponse)
async def save_llm_parse_result(data: LLMParseResultSave):
    try:
        res = await ingest_llm_parse_result(data.model_dump())
        return MedicalRecordResponse(**res)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"保存失败: {e}")

