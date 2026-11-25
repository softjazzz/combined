import logging

from fastapi import APIRouter, Depends, HTTPException, Request

from ..core.response import StatusCode
from ..core.security import require_roles
from ..schemas.ingest import LLMParseResultSave
from ..schemas.records import MedicalRecordResponse
from ..services.medical_records.detail_service import (
    enforce_institute_access,
    resolve_non_global_institute_scope,
)
from ..services.records_ingest_service import ingest_llm_parse_result
from ..storage.memory import medical_records_db

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1", tags=["ingest"])

_INGEST_ROLES = ("admin", "qc_manager", "sync_admin", "super_admin")


@router.post("/medical-records", response_model=MedicalRecordResponse)
async def save_llm_parse_result(
    request: Request,
    data: LLMParseResultSave,
    current_user: dict = Depends(require_roles(*_INGEST_ROLES)),
):
    del request
    inst_scope = resolve_non_global_institute_scope(current_user)
    payload = data.model_dump()

    meta = payload.get("parse_metadata")
    requested_inst = ""
    if isinstance(meta, dict):
        requested_inst = str(meta.get("institute_id") or "").strip()
    if inst_scope is not None:
        if requested_inst:
            enforce_institute_access(inst_scope, requested_inst)
        payload["institute_id"] = inst_scope
        if isinstance(meta, dict):
            meta["institute_id"] = inst_scope

    try:
        res = await ingest_llm_parse_result(payload)
        rec_id = res.get("id")
        if rec_id and rec_id in medical_records_db:
            if inst_scope is not None:
                medical_records_db[rec_id]["institute_id"] = inst_scope
            elif requested_inst:
                medical_records_db[rec_id]["institute_id"] = requested_inst
            actor_id = str(current_user.get("id") or current_user.get("user_id") or "").strip()
            if actor_id:
                medical_records_db[rec_id]["created_by"] = actor_id
        return MedicalRecordResponse(**res)
    except HTTPException:
        raise
    except Exception:
        logger.exception("save_llm_parse_result failed")
        raise HTTPException(
            status_code=StatusCode.INTERNAL_SERVER_ERROR,
            detail="保存病历解析结果失败",
        ) from None
