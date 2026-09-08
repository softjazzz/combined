"""历史质控诊断包入口；仅管理员且必须是所选任务创建人。"""

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, ConfigDict, Field

from ..core.security import require_roles
from ..core.audit import audit_event
from ..services.qc_diagnostics.contracts import DiagnosticPackageError
from ..services.qc_diagnostics.history_delivery import HistoryDelivery

router = APIRouter(prefix="/api/v1/qc/diagnostics", tags=["qc-diagnostics"])
_delivery = HistoryDelivery()
_admin = require_roles("admin", "super_admin")


class PrepareHistory(BaseModel):
    model_config = ConfigDict(extra="forbid")
    job_id: str = Field(min_length=1, max_length=64)
    record_ref: str = Field(min_length=1, max_length=96)
    institute_id: str = Field(min_length=1, max_length=128)
    patient_id: str = Field(min_length=1, max_length=128)
    visit_id: str = Field(min_length=1, max_length=128)


class ConfirmHistory(BaseModel):
    model_config = ConfigDict(extra="forbid")
    confirmed: bool = Field(strict=True)


def _owner(user: dict) -> str:
    owner = str(user.get("id") or user.get("user_id") or user.get("username") or "").strip()
    if not owner or owner == "anonymous":
        raise HTTPException(403, "无诊断导出权限")
    return owner


def _error(error: DiagnosticPackageError) -> None:
    raise HTTPException(409, detail={"code": error.code, "message": "诊断包不可用，请刷新所选结果或重新准备。"}) from None


def _workspace():
    from .qc_sichuan import _sichuan_workspace_service
    return _sichuan_workspace_service()


@router.post("/history/prepare")
def prepare_history(body: PrepareHistory, request: Request, response: Response, user: dict = Depends(_admin)):
    response.headers["Cache-Control"] = "no-store"
    try:
        prepared = _delivery.prepare(workspace=_workspace(), owner=_owner(user), **body.model_dump())
        audit_event(request, action="qc.diagnostic.prepare", resource="qc-diagnostics/history", outcome="success",
                    details={"mode": "history_partial"}, current_user=user)
        return prepared
    except DiagnosticPackageError as error:
        _error(error)


@router.post("/history/{token}/download")
def download_history(token: str, body: ConfirmHistory, request: Request, user: dict = Depends(_admin)):
    try:
        content = _delivery.download(owner=_owner(user), token=token, confirmed=body.confirmed)
    except DiagnosticPackageError as error:
        _error(error)
    audit_event(request, action="qc.diagnostic.download", resource="qc-diagnostics/history", outcome="success",
                details={"mode": "history_partial"}, current_user=user)
    return Response(content, media_type="application/zip", headers={
        "Content-Disposition": "attachment; filename=qc-diagnostic-history.zip",
        "Cache-Control": "no-store", "X-Content-Type-Options": "nosniff",
    })


@router.delete("/history/{token}", status_code=204)
def discard_history(token: str, user: dict = Depends(_admin)):
    _delivery.discard(owner=_owner(user), token=token)
    return Response(status_code=204)
