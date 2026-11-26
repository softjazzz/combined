import logging
from typing import Dict, Any
from datetime import datetime

from fastapi import APIRouter, Request, HTTPException, status, Depends

from ..core.response import success_response, get_trace_id
from ..core.supabase_client import get_supabase, async_execute
from ..core.settings import get_settings
from ..storage.memory import medical_records_db
from ..schemas.records import MedicalRecordResponse
from ..core.security import require_roles
from ..services.medical_records.detail_service import (
    enforce_institute_access,
    resolve_non_global_institute_scope,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/medical-records", tags=["medical-records-compat"])

_COMPAT_ROLES = ("admin", "qc_manager", "sync_admin", "super_admin")


def _normalize_record(rec: Dict[str, Any]) -> Dict[str, Any]:
    patient_info = rec.get("patient_info") or {}
    return {
        "id": rec.get("id") or rec.get("record_id") or rec.get("uuid") or "unknown",
        "patient_name": rec.get("patient_name") or patient_info.get("name") or rec.get("name") or "未识别",
        "patient_age": int(rec.get("patient_age") or patient_info.get("age") or 0),
        "patient_gender": rec.get("patient_gender") or patient_info.get("gender") or "未识别",
        "department": rec.get("department") or rec.get("department_name") or "未识别",
        "admission_date": rec.get("admission_date") or rec.get("admit_date") or datetime.utcnow().strftime("%Y-%m-%d"),
        "record_type": rec.get("record_type") or rec.get("type") or rec.get("document_type") or "病程记录",
        "content": rec.get("content") or rec.get("raw_text") or rec.get("text") or rec.get("document_content") or "",
        "status": rec.get("status") or "pending",
        "created_at": rec.get("created_at") or datetime.utcnow().isoformat() + "Z",
        "updated_at": rec.get("updated_at") or datetime.utcnow().isoformat() + "Z",
        "created_by": rec.get("created_by") or rec.get("user_id") or "system",
        "file_url": rec.get("file_url"),
    }


@router.get("/{record_id}", response_model=MedicalRecordResponse)
async def get_record_public(
    request: Request,
    record_id: str,
    current_user: dict = Depends(require_roles(*_COMPAT_ROLES)),
):
    """兼容老接口：受控获取单条医疗记录（需角色鉴权与机构隔离）。"""
    del request
    inst_scope = resolve_non_global_institute_scope(current_user)
    settings = get_settings()
    supabase = get_supabase()

    # Supabase 优先
    if supabase is not None:
        try:
            resp = await async_execute(
                supabase.table(settings.RECORDS_TABLE).select("*").eq("id", record_id).limit(1)
            )  # type: ignore[attr-defined]
            rows = resp.data or []
            if rows:
                row = rows[0]
                enforce_institute_access(inst_scope, row.get("institute_id"))
                return MedicalRecordResponse(**_normalize_record(row))
        except HTTPException:
            raise
        except Exception:
            logger.warning("get_record_public supabase query failed, falling back to memory", exc_info=True)

    # 内存回退
    rec = medical_records_db.get(record_id)
    if not rec:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="医疗记录不存在")
    enforce_institute_access(inst_scope, rec.get("institute_id"))
    return MedicalRecordResponse(**_normalize_record(rec))


@router.delete("/{record_id}")
async def delete_record_compat(
    request: Request,
    record_id: str,
    current_user: dict = Depends(require_roles(*_COMPAT_ROLES)),
):
    """兼容老接口：删除医疗记录，需角色鉴权与机构隔离。"""
    inst_scope = resolve_non_global_institute_scope(current_user)
    rec = medical_records_db.get(record_id)
    if rec is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="医疗记录不存在")
    enforce_institute_access(inst_scope, rec.get("institute_id"))
    del medical_records_db[record_id]
    return success_response(data={}, message="医疗记录删除成功", trace_id=get_trace_id(request))
