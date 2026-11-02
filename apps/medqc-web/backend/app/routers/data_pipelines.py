"""双抽取链路设置与独立同步任务；不创建质控任务。"""
from __future__ import annotations

from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, ConfigDict, Field
from starlette.concurrency import run_in_threadpool

from ..core.audit import audit_event
from ..core.response import success_response
from ..core.security import get_current_user
from ..database.connection import SessionLocal
from ..services import data_pipeline_settings as settings
from ..services import sync_control_client as control
from ..services.defect_rectification_service import RectificationError, _person
from ..services.product_activation import require_product_activation

router = APIRouter(prefix="/api/v1/sync/pipelines", tags=["data-pipelines"])


def require_pipeline_admin(current: dict = Depends(get_current_user)) -> dict:
    """外部控制面token是全局能力，必须由有效的持久全局管理员持有应用入口。"""
    if SessionLocal is None:
        raise HTTPException(503, "data_pipeline_account_owner_unavailable")
    actor_id = current.get("id") or current.get("user_id")
    if not isinstance(actor_id, str) or not actor_id.strip():
        raise HTTPException(403, "data_pipeline_admin_required")
    try:
        with SessionLocal() as session:
            person = _person(session, actor_id)
        if not person["roles"] & {"admin", "sync_admin", "super_admin"}:
            raise HTTPException(403, "data_pipeline_admin_required")
        return person
    except RectificationError as error:
        raise HTTPException(error.status, "data_pipeline_admin_required") from None
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(503, "data_pipeline_account_owner_unavailable") from None


def load_configuration() -> settings.PipelineSettings:
    if SessionLocal is None:
        raise settings.PipelineError("data_pipeline_configuration_unavailable")
    try:
        with SessionLocal() as session:
            return settings.load(session)[0]
    except settings.PipelineError:
        raise
    except Exception:
        raise settings.PipelineError("data_pipeline_configuration_unavailable") from None


def enabled() -> settings.PipelineSettings:
    value = load_configuration()
    if not value.independent_enabled:
        raise settings.PipelineError("independent_pipeline_disabled", 409)
    return value


def error_response(error: settings.PipelineError) -> HTTPException:
    return HTTPException(error.status, error.code)


def configuration_payload(value: settings.PipelineSettings) -> dict:
    return {"settings": value.model_dump(), "runtime": settings.runtime_status()}


@router.get("")
def get_configuration(_actor: dict = Depends(require_pipeline_admin)):
    try:
        return success_response(data=configuration_payload(load_configuration()))
    except settings.PipelineError as error:
        raise error_response(error) from None


@router.put("")
def put_configuration(payload: settings.PipelineSettings, request: Request,
                      actor: dict = Depends(require_pipeline_admin)):
    try:
        if SessionLocal is None:
            raise settings.PipelineError("data_pipeline_configuration_unavailable")
        with SessionLocal() as session:
            value = settings.save(session, payload, actor["id"])
    except settings.PipelineError as error:
        raise error_response(error) from None
    except Exception:
        raise HTTPException(503, "data_pipeline_configuration_unavailable") from None
    audit_event(request, action="sync.pipelines.configure", resource="sync/pipelines", outcome="success",
                details={"default_pipeline": value.default_pipeline, "independent_enabled": value.independent_enabled})
    return success_response(data=configuration_payload(value))


@router.post("/independent/check")
async def check_independent(_actor: dict = Depends(require_pipeline_admin)):
    # 显式只读检查可在未启用链路时进行；不访问源库，不抽取资料。
    try:
        return success_response(data=await control.catalog())
    except settings.PipelineError as error:
        raise error_response(error) from None


class CreateJob(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    operation_id: str = Field(min_length=36, max_length=36)
    start_date: str = Field(min_length=10, max_length=10)
    end_date: str = Field(min_length=10, max_length=10)
    interfaces: list[str] = Field(min_length=1, max_length=100)
    mode: Literal["dry", "replay"] = "dry"
    publish: bool = False


@router.post("/independent/jobs", status_code=202, dependencies=[Depends(require_product_activation)])
async def create_job(payload: CreateJob, request: Request, actor: dict = Depends(require_pipeline_admin)):
    try:
        UUID(payload.operation_id)
    except ValueError:
        raise HTTPException(422, "invalid_operation_id") from None
    try:
        await run_in_threadpool(enabled)
        normalized = control.prepare_job(start_date=payload.start_date, end_date=payload.end_date,
            interfaces=payload.interfaces, publish=payload.publish, dry=payload.mode == "dry")
        job = await control.submit(normalized, actor["id"], payload.operation_id)
    except settings.PipelineError as error:
        audit_event(request, action="sync.independent.submit", resource="sync/pipelines", outcome="failed",
                    details={"reason": error.code})
        raise error_response(error) from None
    audit_event(request, action="sync.independent.submit", resource=job["job_id"], outcome="success",
                details={"mode": payload.mode, "publish": payload.publish})
    return success_response(data=job)


@router.get("/independent/jobs")
async def list_jobs(limit: int = Query(20, ge=1, le=100), _actor: dict = Depends(require_pipeline_admin)):
    try:
        raw = await control.request("GET", f"/v1/jobs?limit={limit}")
        items = raw.get("jobs")
        if not isinstance(items, list):
            raise settings.PipelineError("sync_control_invalid_job_response", 502)
        profile = control.deployment()[2]
        jobs = [control.public_job(job) for job in items if isinstance(job, dict)
                and isinstance(job.get("request"), dict) and job["request"].get("profile") == profile]
        return success_response(data={"jobs": jobs})
    except settings.PipelineError as error:
        raise error_response(error) from None


async def bound_job(job_id: UUID) -> dict:
    raw = await control.request("GET", f"/v1/jobs/{job_id}")
    if not isinstance(raw.get("request"), dict) or raw["request"].get("profile") != control.deployment()[2]:
        raise settings.PipelineError("sync_control_job_outside_profile", 403)
    return raw


@router.get("/independent/jobs/{job_id}")
async def get_job(job_id: UUID, _actor: dict = Depends(require_pipeline_admin)):
    try:
        return success_response(data=control.public_job(await bound_job(job_id)))
    except settings.PipelineError as error:
        raise error_response(error) from None


@router.post("/independent/jobs/{job_id}/{action}", dependencies=[Depends(require_product_activation)])
async def job_action(job_id: UUID, action: Literal["cancel", "retry"], request: Request,
                     _actor: dict = Depends(require_pipeline_admin)):
    try:
        if action == "retry":
            await run_in_threadpool(enabled)
        await bound_job(job_id)
        job = control.public_job(await control.request("POST", f"/v1/jobs/{job_id}/{action}"))
    except settings.PipelineError as error:
        raise error_response(error) from None
    audit_event(request, action=f"sync.independent.{action}", resource=str(job_id), outcome="success")
    return success_response(data=job)
