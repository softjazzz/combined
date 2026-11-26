"""双抽取链路设置与独立同步任务；不创建质控任务。"""
from __future__ import annotations

from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, ConfigDict, Field
from starlette.concurrency import run_in_threadpool

from ..core.audit import audit_event
from ..core.response import success_response
from ..core.security import get_current_user, is_global_system_admin_principal
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
        if not is_global_system_admin_principal(person["roles"], person.get("institute_id")):
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
    safe = getattr(error, "public_details", {})
    return HTTPException(error.status, {"code": error.code, "upstream": safe} if safe else error.code)


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
        normalized = payload.model_dump(exclude={"operation_id"})
        job = await control.submit(normalized, actor["id"], payload.operation_id)
    except settings.PipelineError as error:
        audit_event(request, action="sync.independent.submit", resource="sync/pipelines", outcome="failed",
                    details={"reason": error.code, "operation_id": payload.operation_id}, current_user=actor)
        raise error_response(error) from None
    audit_event(request, action="sync.independent.submit", resource=job["job_id"], outcome="success",
                details={"mode": payload.mode, "publish": payload.publish, "operation_id": payload.operation_id}, current_user=actor)
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
                     actor: dict = Depends(require_pipeline_admin)):
    try:
        if action == "retry":
            await run_in_threadpool(enabled)
        control.require_permission(await control.session(), "run")
        await bound_job(job_id)
        job = control.public_job(await control.request("POST", f"/v1/jobs/{job_id}/{action}"))
    except settings.PipelineError as error:
        audit_event(request, action=f"sync.independent.{action}", resource=str(job_id), outcome="failed",
                    details={"reason": error.code}, current_user=actor)
        raise error_response(error) from None
    audit_event(request, action=f"sync.independent.{action}", resource=str(job_id), outcome="success", current_user=actor)
    return success_response(data=job)


class DraftRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    interfaces: list[str] = Field(min_length=1, max_length=100)
    frequency: Literal["daily", "weekly"]
    local_time: str = Field(pattern=r"^(?:[01][0-9]|2[0-3]):[0-5][0-9]$")
    window_days: int = Field(ge=1, le=60)
    weekday: int | None = Field(default=None, ge=0, le=6)


class SaveDraft(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    version: int | None = Field(default=None, ge=1)
    config: DraftRequest


async def bound_schedule(schedule_id: UUID) -> dict:
    raw = await control.request("GET", f"/v1/schedules/{schedule_id}")
    config = raw.get("config")
    if not isinstance(config, dict) or not isinstance(config.get("request"), dict) or config["request"].get("profile") != control.deployment()[2]:
        raise settings.PipelineError("sync_control_schedule_outside_profile", 403)
    return raw


@router.get("/independent/schedules")
async def list_schedules(_actor: dict = Depends(require_pipeline_admin)):
    try:
        raw = await control.request("GET", "/v1/schedules")
        if not isinstance(raw.get("schedules"), list):
            raise settings.PipelineError("sync_control_invalid_schedule_response", 502)
        profile = control.deployment()[2]
        return success_response(data={"schedules": [control.public_schedule(row) for row in raw["schedules"]
            if isinstance(row, dict) and isinstance(row.get("config"), dict)
            and isinstance(row["config"].get("request"), dict) and row["config"]["request"].get("profile") == profile]})
    except settings.PipelineError as error:
        raise error_response(error) from None


@router.get("/independent/schedules/{schedule_id}")
async def get_schedule(schedule_id: UUID, _actor: dict = Depends(require_pipeline_admin)):
    try:
        return success_response(data=control.public_schedule(await bound_schedule(schedule_id)))
    except settings.PipelineError as error:
        raise error_response(error) from None


@router.put("/independent/schedule-drafts/{schedule_id}", dependencies=[Depends(require_product_activation)])
async def save_draft(schedule_id: UUID, payload: SaveDraft, request: Request,
                     actor: dict = Depends(require_pipeline_admin)):
    try:
        allowed = await control.catalog()
        control.require_permission(allowed["session"], "schedule")
        if not allowed["session"]["features"]["schedule_drafts"]:
            raise settings.PipelineError("sync_control_drafts_unavailable", 409)
        if not set(payload.config.interfaces) <= set(allowed["interfaces"]) or len(set(payload.config.interfaces)) != len(payload.config.interfaces):
            raise settings.PipelineError("sync_control_interface_not_approved", 422)
        if payload.version is not None:
            existing = await bound_schedule(schedule_id)
            if existing.get("enabled") is not False:
                raise settings.PipelineError("sync_control_enabled_schedule_read_only", 409)
        config = payload.config.model_dump(exclude={"interfaces", "weekday"})
        if payload.config.frequency == "weekly":
            if payload.config.weekday is None:
                raise settings.PipelineError("sync_control_weekday_required", 422)
            config["weekday"] = payload.config.weekday
        config.update(timezone="Asia/Shanghai", request={"profile": allowed["profile"],
            "interfaces": sorted(payload.config.interfaces), "mode": "replay", "publish": True})
        saved = control.public_schedule(await control.request("PUT", f"/v1/schedule-drafts/{schedule_id}",
            payload={"version": payload.version, "config": config}))
        if (saved["schedule_id"] != str(schedule_id) or saved["config"]["request"].get("profile") != allowed["profile"]
                or saved["enabled"] is not False or saved["next_fire_at"] is not None):
            raise settings.PipelineError("sync_control_draft_state_unconfirmed", 502)
    except settings.PipelineError as error:
        audit_event(request, action="sync.schedule.draft", resource=str(schedule_id), outcome="failed",
                    details={"reason": error.code, "version": payload.version}, current_user=actor)
        raise error_response(error) from None
    audit_event(request, action="sync.schedule.draft", resource=str(schedule_id), outcome="success",
                details={"version": saved["version"]}, current_user=actor)
    return success_response(data=saved)
