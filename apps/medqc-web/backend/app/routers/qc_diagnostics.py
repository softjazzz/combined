"""历史质控诊断包入口；仅管理员且必须是所选任务创建人。"""

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, ConfigDict, Field

from ..core.security import require_roles
from ..core.audit import audit_event
from ..services.qc_diagnostics.contracts import DiagnosticPackageError
from ..services.qc_diagnostics.history_delivery import HistoryDelivery
from ..services.qc_diagnostics import support_store

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


def _capture_job(job_id: str, user: dict) -> dict:
    job = _workspace().get_batch_job(job_id=job_id, created_by=_owner(user))
    if not job or (job.get("filters") or {}).get("diagnostic_capture") is not True:
        raise HTTPException(404, "未找到当前用户的排障采集任务")
    return job


@router.post("/capture/start")
async def start_capture(body: PrepareHistory, request: Request, user: dict = Depends(_admin)):
    from .qc_sichuan import (SichuanWorkspaceBatchJobCreateRequest,
                             create_workspace_batch_job, get_qc_service)
    workspace = _workspace()
    job = workspace.get_batch_job(job_id=body.job_id, created_by=_owner(user))
    if not job:
        raise HTTPException(404, "未找到当前用户的原质控任务")
    result = workspace.get_latest_luxian_0609_record_result(
        institute_id=body.institute_id, patient_id=body.patient_id, visit_id=body.visit_id)
    if (result.get("state") != "ready" or result.get("job_id") != body.job_id
            or result.get("record_ref") != body.record_ref):
        raise HTTPException(409, "质控结果已变化，请重新打开当前病历结果")
    payload = SichuanWorkspaceBatchJobCreateRequest(
        diagnostic_capture=True, rule_set_key="luxian_0609_qc_v1",
        rule_ids=[item["rule_id"] for item in result.get("items", [])],
        scope=job.get("scope") or "final",
        record_refs=[{"institute_id": body.institute_id, "patient_id": body.patient_id,
                      "visit_id": body.visit_id}],
    )
    response = await create_workspace_batch_job(request, payload, user, await get_qc_service())
    audit_event(request, action="qc.diagnostic.capture", resource="qc-diagnostics/capture",
                outcome="success", details={"mode": "execution_capture"}, current_user=user)
    return {"job_id": response["data"]["id"]}


@router.get("/capture/{job_id}")
def capture_status(job_id: str, response: Response, user: dict = Depends(_admin)):
    job = _workspace().get_batch_job(job_id=job_id, created_by=_owner(user))
    if not job:
        raise HTTPException(404, "未找到当前用户的质控任务")
    response.headers["Cache-Control"] = "no-store"
    if (job.get("filters") or {}).get("diagnostic_capture") is not True:
        return {"state": "unavailable", "error_code": "capture_not_recorded"}
    try:
        return support_store.status(job_id, job.get("status", ""))
    except DiagnosticPackageError as error:
        _error(error)


@router.post("/capture/{job_id}/download")
def download_capture(job_id: str, body: ConfirmHistory, request: Request, user: dict = Depends(_admin)):
    _capture_job(job_id, user)
    if body.confirmed is not True:
        raise HTTPException(409, "请先复核排障包包含医疗正文及隐私提示")
    try:
        content = support_store.download(job_id)
    except DiagnosticPackageError as error:
        _error(error)
    audit_event(request, action="qc.diagnostic.download", resource="qc-diagnostics/capture",
                outcome="success", details={"mode": "execution_capture"}, current_user=user)
    return Response(content, media_type="application/zip", headers={
        "Content-Disposition": "attachment; filename=qc-troubleshooting.zip",
        "Cache-Control": "no-store", "X-Content-Type-Options": "nosniff",
    })
