"""每日质控计划：仅持久管理账号可配置，不提供立即执行入口。"""

from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy.exc import SQLAlchemyError

from ..core.security import get_current_user
from ..core.settings import get_settings
from ..core.response import success_response
from ..services.daily_qc import service
from ..services.daily_qc.contracts import PlanInput
from ..services.daily_qc.store import PlanConflict


router = APIRouter(prefix="/api/v1/qc/daily-schedules", tags=["daily-qc-schedules"])


def store_dependency():
    try:
        return service.default_store()
    except RuntimeError as exc:
        raise HTTPException(503, "定时质控存储未配置") from exc


def authorized(current_user=Depends(get_current_user), store=Depends(store_dependency)):
    actor_id = str(current_user.get("id") or "")
    service.require_manager(store, actor_id)
    return store, actor_id


@router.get("/options")
def options(
    institute_id: str | None = None,
    scope: str = Query("final", pattern="^(running|final)$"),
    context=Depends(authorized),
):
    store, actor = context
    try:
        return success_response(
            service.options(store, actor, institute_id=institute_id, scope=scope)
        )
    except SQLAlchemyError as exc:
        raise HTTPException(503, "计划选项读取失败") from exc


@router.get("")
def list_plans(request: Request, context=Depends(authorized)):
    store, actor = context
    try:
        rows = [service.project_plan(row) for row in store.list(actor)]
    except SQLAlchemyError as exc:
        raise HTTPException(503, "定时质控存储未就绪，请先执行064迁移") from exc
    return success_response(
        {
            "items": rows,
            "scheduler_enabled": get_settings().QC_DAILY_SCHEDULER_ENABLED,
            "local_process_active": bool(
                (task := getattr(request.app.state, "daily_qc_task", None)) is not None
                and not task.done()
            ),
        }
    )


@router.post("")
def create_plan(payload: PlanInput, context=Depends(authorized)):
    store, actor = context
    service.assert_plan_institute_scope(store, actor, payload.institute_id)
    definition = service.validate_definition(store, actor, payload)
    try:
        plan_id = store.save(actor, definition, datetime.now(timezone.utc))
        return success_response(service.project_plan(store.current(plan_id)))
    except PlanConflict as exc:
        raise HTTPException(409, "计划数量已达到上限") from exc
    except SQLAlchemyError as exc:
        raise HTTPException(503, "定时质控存储未就绪，未保存计划") from exc


class PlanUpdate(BaseModel):
    revision: int = Field(ge=1)
    definition: PlanInput


@router.put("/{plan_id}")
def update_plan(plan_id: UUID, payload: PlanUpdate, context=Depends(authorized)):
    store, actor = context
    service.assert_plan_institute_scope(store, actor, payload.definition.institute_id)
    definition = service.validate_definition(store, actor, payload.definition)
    try:
        store.save(
            actor,
            definition,
            datetime.now(timezone.utc),
            str(plan_id),
            payload.revision,
        )
        return success_response(service.project_plan(store.current(str(plan_id))))
    except PlanConflict as exc:
        raise HTTPException(409, "计划已变化或无权访问，请刷新后重试") from exc
    except SQLAlchemyError as exc:
        raise HTTPException(503, "计划保存失败") from exc


@router.get("/{plan_id}/runs")
def history(plan_id: UUID, context=Depends(authorized)):
    store, actor = context
    try:
        return success_response(
            {
                "items": [
                    service.project_run(row)
                    for row in store.history(str(plan_id), actor)
                ]
            }
        )
    except KeyError as exc:
        raise HTTPException(404, "计划不存在或无权查看") from exc
    except SQLAlchemyError as exc:
        raise HTTPException(503, "触发记录读取失败") from exc
