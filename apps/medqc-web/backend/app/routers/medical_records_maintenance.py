"""病案数据 - 维护子域。"""

from typing import Optional

from fastapi import APIRouter, Depends, Query

from ..core.security import require_roles
from ..services.medical_records.maintenance_service import (
    get_ai_frontpage_draft,
    get_qc_results,
    resolve_maintenance_institute_scope,
    save_ai_frontpage_draft,
    save_frontpage,
    save_qc_results,
)
from .medical_records_common import raise_medical_records_http_error

router = APIRouter(tags=["病案数据-维护"])
_MAINTENANCE_ROLES = ("admin", "qc_manager", "sync_admin")


@router.put("/frontpage")
def save_frontpage_api(
    data: dict,
    current_user: dict = Depends(require_roles(*_MAINTENANCE_ROLES)),
):
    try:
        allowed_institute_id = resolve_maintenance_institute_scope(current_user)
        result = save_frontpage(data, allowed_institute_id=allowed_institute_id)
        return {"success": True, "data": result}
    except Exception as exc:
        raise_medical_records_http_error(exc)


@router.post("/ai-frontpage-draft")
def save_ai_frontpage_draft_api(
    data: dict,
    current_user: dict = Depends(require_roles(*_MAINTENANCE_ROLES)),
):
    try:
        allowed_institute_id = resolve_maintenance_institute_scope(current_user)
        result = save_ai_frontpage_draft(data, allowed_institute_id=allowed_institute_id)
        return {"success": True, **result}
    except Exception as exc:
        raise_medical_records_http_error(exc)


@router.get("/ai-frontpage-draft/{visit_id}")
def get_ai_frontpage_draft_api(
    visit_id: str,
    institute_id: Optional[str] = Query(None, description="机构号"),
    patient_id: Optional[str] = Query(None, description="患者号"),
    current_user: dict = Depends(require_roles(*_MAINTENANCE_ROLES)),
):
    try:
        allowed_institute_id = resolve_maintenance_institute_scope(current_user)
        return get_ai_frontpage_draft(
            visit_id,
            institute_id=institute_id,
            patient_id=patient_id,
            allowed_institute_id=allowed_institute_id,
        )
    except Exception as exc:
        raise_medical_records_http_error(exc)


@router.post("/qc-results")
def save_qc_results_api(
    data: dict,
    current_user: dict = Depends(require_roles(*_MAINTENANCE_ROLES)),
):
    try:
        allowed_institute_id = resolve_maintenance_institute_scope(current_user)
        count = save_qc_results(data, allowed_institute_id=allowed_institute_id)
        return {"success": True, "saved_count": count}
    except Exception as exc:
        raise_medical_records_http_error(exc)


@router.get("/qc-results/{institute_id}/{patient_id}/{visit_id}")
def get_qc_results_api(
    institute_id: str,
    patient_id: str,
    visit_id: str,
    current_user: dict = Depends(require_roles(*_MAINTENANCE_ROLES)),
):
    try:
        allowed_institute_id = resolve_maintenance_institute_scope(current_user)
        return get_qc_results(
            institute_id,
            patient_id,
            visit_id,
            allowed_institute_id=allowed_institute_id,
        )
    except Exception as exc:
        raise_medical_records_http_error(exc)

