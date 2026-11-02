"""独立的异步任务受理API；不导入业务应用或创建数据源连接。"""

from __future__ import annotations

import re
from collections.abc import Callable
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any
from uuid import UUID

from medqc_ingest.control.admission import AdmissionService
from medqc_ingest.control.auth import TokenAuth
from medqc_ingest.control.models import Actor, ControlError
from medqc_ingest.control.ports import ControlRepository
from medqc_ingest.control.profiles import ProfileCatalog
from medqc_ingest.control.scheduler import normalize_schedule_config

if TYPE_CHECKING:
    from fastapi import FastAPI
    from starlette.responses import JSONResponse

_JOB_FIELDS = frozenset(
    {
        "job_id",
        "status",
        "source",
        "actor_id",
        "cancel_requested",
        "created_at",
        "updated_at",
        "started_at",
        "finished_at",
        "attempt_count",
        "next_retry_at",
    }
)
_UNIT_FIELDS = frozenset(
    {
        "unit_id",
        "sequence",
        "interface_name",
        "source_date",
        "phase",
        "status",
        "started_at",
        "finished_at",
    }
)
_RESULT_FIELDS = frozenset(
    {
        "counts",
        "batch_id",
        "source_batch_id",
        "publish_batch_id",
        "selected",
        "written",
        "checkpoint_state",
        "schema_hash",
        "source_limited",
    }
)
_COUNT_FIELDS = frozenset(
    {
        "fetched",
        "inserted",
        "updated",
        "unchanged",
        "selected",
        "written",
        "units_total",
        "units_completed",
        "units_failed",
        "units_limited",
    }
)


def _id(value: str) -> str:
    try:
        return str(UUID(value))
    except (ValueError, TypeError, AttributeError):
        raise ControlError("invalid_identifier", "control_identifier", 422) from None


def _error(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        return {}
    result = {}
    for key in ("code", "location", "error_kind", "error_location"):
        item = value.get(key)
        if isinstance(item, str) and re.fullmatch(r"[a-z][a-z0-9_.:-]{0,127}", item):
            result[key] = item
    if isinstance(value.get("sqlstate"), str) and re.fullmatch(r"[0-9A-Z]{5}", value["sqlstate"]):
        result["sqlstate"] = value["sqlstate"]
    if type(value.get("native")) is int:
        result["native"] = value["native"]
    return result


def _counts(value: Any) -> dict[str, int]:
    if not isinstance(value, dict):
        return {}
    return {key: item for key, item in value.items() if key in _COUNT_FIELDS and type(item) is int}


def _request(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        return {}
    return {
        key: value[key]
        for key in ("profile", "interfaces", "mode", "publish", "start_date", "end_date")
        if key in value
    }


def public_unit(unit: dict[str, Any]) -> dict[str, Any]:
    result = {key: value for key, value in unit.items() if key in _UNIT_FIELDS}
    raw = unit.get("result")
    if isinstance(raw, dict):
        result["result"] = {
            key: value for key, value in raw.items() if key in _RESULT_FIELDS and key != "counts"
        }
        if "counts" in raw:
            result["result"]["counts"] = _counts(raw["counts"])
        result["result"].update(_error(raw))
    if "error" in unit:
        result["error"] = _error(unit["error"])
    return result


def public_job(job: dict[str, Any]) -> dict[str, Any]:
    result = {key: value for key, value in job.items() if key in _JOB_FIELDS}
    result["request"] = _request(job.get("request"))
    if "counts" in job:
        result["counts"] = _counts(job["counts"])
    if "error" in job:
        result["error"] = _error(job["error"])
    return result


def public_schedule(schedule: dict[str, Any]) -> dict[str, Any]:
    result = {
        key: value
        for key, value in schedule.items()
        if key
        in {
            "schedule_id",
            "version",
            "enabled",
            "next_fire_at",
            "created_at",
            "updated_at",
            "actor_id",
        }
    }
    config = schedule.get("config")
    if isinstance(config, dict):
        result["config"] = {
            key: value
            for key, value in config.items()
            if key in {"frequency", "local_time", "weekday", "window_days", "timezone"}
        }
        result["config"]["request"] = _request(config.get("request"))
    return result


def _version(value: Any) -> int:
    if type(value) is not int or value < 1:
        raise ControlError("invalid_schedule", "schedule_version", 422)
    return int(value)


def create_app(
    admission: AdmissionService,
    repository: ControlRepository,
    auth: TokenAuth,
    catalog: ProfileCatalog,
    *,
    clock: Callable[[], datetime] | None = None,
) -> FastAPI:
    # FastAPI是可选依赖；CLI/worker导入该模块不会加载框架、配置或驱动。
    from fastapi import Body, Depends, FastAPI, Header, Query
    from fastapi.exceptions import RequestValidationError
    from starlette.responses import JSONResponse

    app = FastAPI(title="MedQC Sync Control", docs_url=None, redoc_url=None, openapi_url=None)
    now = clock or (lambda: datetime.now(timezone.utc))

    authorization_header = Header(default=None)
    idempotency_header = Header(default=None, alias="Idempotency-Key")
    request_body = Body(...)
    list_limit = Query(default=50, ge=1, le=100)

    def actor(authorization: str | None = authorization_header) -> Actor:
        return auth.authenticate(authorization)

    actor_dependency = Depends(actor)

    def reader(current: Actor = actor_dependency) -> Actor:
        current.require("read")
        return current

    def runner(current: Actor = actor_dependency) -> Actor:
        current.require("run")
        return current

    def planner(current: Actor = actor_dependency) -> Actor:
        current.require("schedule")
        return current

    reader_dependency, runner_dependency, planner_dependency = (
        Depends(reader),
        Depends(runner),
        Depends(planner),
    )

    @app.exception_handler(ControlError)
    async def control_error(_request: Any, error: ControlError) -> JSONResponse:
        return JSONResponse(
            {"error": {"code": error.code, "location": error.location}},
            status_code=error.status_code,
        )

    @app.exception_handler(RequestValidationError)
    async def invalid_request(_request: Any, _error: RequestValidationError) -> JSONResponse:
        # 默认框架错误可能回显提交的秘密或临床内容，统一改为静态错误。
        return JSONResponse(
            {"error": {"code": "invalid_request", "location": "control_http"}}, status_code=422
        )

    @app.exception_handler(Exception)
    async def unexpected_error(_request: Any, _error: Exception) -> JSONResponse:
        return JSONResponse(
            {"error": {"code": "control_unavailable", "location": "control_http"}}, status_code=503
        )

    @app.get("/health/live")
    def live() -> dict[str, bool]:
        return {"live": True}

    @app.get("/health/ready")
    def ready(_current: Actor = reader_dependency) -> dict[str, bool]:
        repository.list_jobs(limit=1)
        return {"ready": True}

    @app.get("/v1/interfaces")
    def interfaces(_current: Actor = reader_dependency) -> dict[str, Any]:
        return {"profiles": catalog.describe()}

    @app.post("/v1/jobs", status_code=202)
    def submit_job(
        payload: dict[str, Any] = request_body,
        current: Actor = runner_dependency,
        idempotency_key: str | None = idempotency_header,
    ) -> dict[str, Any]:
        if idempotency_key is None:
            raise ControlError("invalid_job_request", "admission_idempotency_key", 422)
        return public_job(admission.submit(payload, current, idempotency_key))

    @app.get("/v1/jobs")
    def list_jobs(limit: int = list_limit, _current: Actor = reader_dependency) -> dict[str, Any]:
        return {"jobs": [public_job(job) for job in repository.list_jobs(limit)]}

    @app.get("/v1/jobs/{job_id}")
    def get_job(job_id: str, _current: Actor = reader_dependency) -> dict[str, Any]:
        identifier = _id(job_id)
        job = repository.get_job(identifier)
        if job is None:
            raise ControlError("not_found", "control_job", 404)
        result = public_job(job)
        result["units"] = [public_unit(unit) for unit in repository.units(identifier)]
        return result

    @app.post("/v1/jobs/{job_id}/retry", status_code=202)
    def retry(job_id: str, current: Actor = runner_dependency) -> dict[str, Any]:
        identifier = _id(job_id)
        job = repository.get_job(identifier)
        if job is None:
            raise ControlError("not_found", "control_job", 404)
        request = job["request"]
        catalog.validate(
            request["profile"], request["interfaces"], request["mode"], job.get("source", "manual")
        )
        return public_job(repository.retry(identifier, current.actor_id))

    @app.post("/v1/jobs/{job_id}/cancel")
    def cancel(job_id: str, current: Actor = runner_dependency) -> dict[str, Any]:
        return public_job(repository.cancel(_id(job_id), current.actor_id))

    @app.get("/v1/schedules")
    def list_schedules(_current: Actor = reader_dependency) -> dict[str, Any]:
        return {"schedules": [public_schedule(item) for item in repository.list_schedules()]}

    @app.post("/v1/schedules", status_code=201)
    def create_schedule(
        payload: dict[str, Any] = request_body, current: Actor = planner_dependency
    ) -> dict[str, Any]:
        config = normalize_schedule_config(payload, admission, current, now())
        return public_schedule(repository.create_schedule(config, current.actor_id))

    @app.get("/v1/schedules/{schedule_id}")
    def get_schedule(schedule_id: str, _current: Actor = reader_dependency) -> dict[str, Any]:
        item = repository.get_schedule(_id(schedule_id))
        if item is None:
            raise ControlError("not_found", "control_schedule", 404)
        return public_schedule(item)

    @app.patch("/v1/schedules/{schedule_id}")
    def update_schedule(
        schedule_id: str,
        payload: dict[str, Any] = request_body,
        current: Actor = planner_dependency,
    ) -> dict[str, Any]:
        if set(payload) != {"version", "changes"} or not isinstance(payload["changes"], dict):
            raise ControlError("invalid_schedule", "schedule_update", 422)
        identifier = _id(schedule_id)
        item = repository.get_schedule(identifier)
        if item is None:
            raise ControlError("not_found", "control_schedule", 404)
        merged = dict(item["config"], **payload["changes"])
        if payload["changes"].get("frequency") == "daily" and "weekday" not in payload["changes"]:
            merged.pop("weekday", None)
        config = normalize_schedule_config(merged, admission, current, now())
        return public_schedule(
            repository.update_schedule(
                identifier, _version(payload["version"]), config, current.actor_id
            )
        )

    def toggle(
        schedule_id: str, payload: dict[str, Any], current: Actor, enabled: bool
    ) -> dict[str, Any]:
        if set(payload) != {"version"}:
            raise ControlError("invalid_schedule", "schedule_update", 422)
        identifier = _id(schedule_id)
        if enabled:
            item = repository.get_schedule(identifier)
            if item is None:
                raise ControlError("not_found", "control_schedule", 404)
            normalize_schedule_config(item["config"], admission, current, now())
        return public_schedule(
            repository.set_schedule_enabled(
                identifier, _version(payload["version"]), enabled, current.actor_id
            )
        )

    @app.post("/v1/schedules/{schedule_id}/enable")
    def enable(
        schedule_id: str,
        payload: dict[str, Any] = request_body,
        current: Actor = planner_dependency,
    ) -> dict[str, Any]:
        return toggle(schedule_id, payload, current, True)

    @app.post("/v1/schedules/{schedule_id}/disable")
    def disable(
        schedule_id: str,
        payload: dict[str, Any] = request_body,
        current: Actor = planner_dependency,
    ) -> dict[str, Any]:
        return toggle(schedule_id, payload, current, False)

    return app
