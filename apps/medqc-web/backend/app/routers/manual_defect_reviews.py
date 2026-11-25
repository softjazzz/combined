"""V5人工缺陷入口；复用任务录入、审核及正式结果owner。"""
import logging
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from starlette.concurrency import run_in_threadpool

from ..core.audit import audit_event
from ..core.permissions import PermissionAction, ResourceType, has_permission
from ..core.response import get_trace_id, success_response
from ..core.security import get_current_user
from ..database.connection import SessionLocal
from ..database.models.v36_reports import QCTask, QCTaskRecord, QCTaskQCRun
from ..services import manual_defect_review_service as review
from ..services import task_manual_defect_service as entry
from ..services.defect_rectification_service import RectificationError, _person

router = APIRouter(prefix="/api/v1/manual-defects", tags=["manual-defects"])
logger = logging.getLogger(__name__)


class EntryRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    defect_id: UUID
    task_id: str = Field(min_length=1, max_length=36)
    task_record_id: str = Field(min_length=1, max_length=36)
    run_number: int = Field(gt=0)
    rule_name: str = Field(min_length=1, max_length=200)
    description: str = Field(min_length=1, max_length=4000)
    severity: Literal["info", "warning", "error", "critical"]
    suggestion: str | None = Field(default=None, max_length=2000)
    evidence: str | None = Field(default=None, max_length=2000)


class ReviewRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    decision: Literal["approved", "rejected"]
    expected_status: Literal["pending"]
    reason: str | None = Field(default=None, max_length=2000)


def _actor(user, action):
    actor = user.get("id") or user.get("user_id")
    if not actor or not has_permission(user, ResourceType.QC_RESULTS, action):
        raise HTTPException(403, "没有人工缺陷操作权限")
    return str(actor)


async def _call(function, **kwargs):
    try:
        return await run_in_threadpool(function, **kwargs)
    except (review.ManualDefectReviewForbidden, entry.TaskManualDefectForbidden) as exc:
        raise HTTPException(403, str(exc)) from exc
    except (review.ManualDefectReviewNotFound, entry.TaskManualDefectNotFound) as exc:
        raise HTTPException(404, str(exc)) from exc
    except review.ManualDefectReviewInvalid as exc:
        raise HTTPException(422, str(exc)) from exc
    except (review.ManualDefectReviewConflict, entry.TaskManualDefectConflict) as exc:
        raise HTTPException(409, str(exc)) from exc
    except RectificationError as exc:
        raise HTTPException(exc.status, str(exc)) from exc
    except Exception as exc:
        logger.error("manual_defect_workflow_failed error_type=%s", type(exc).__name__)
        raise HTTPException(503, "人工缺陷服务暂不可用，请刷新核对") from None


def _entry_contexts(actor_id, scene, page):
    with SessionLocal() as session:
        actor = _person(session, actor_id)
        if not actor["roles"] & {"admin", "super_admin", "qc_manager", "qc_staff"}:
            raise entry.TaskManualDefectForbidden("仅质控人员可录入")
        statement = (
            select(QCTaskRecord, QCTask)
            .join(QCTask, QCTask.id == QCTaskRecord.task_id)
            .where(
                QCTaskRecord.assignee_id == actor_id,
                QCTaskRecord.status == "in_progress",
                QCTask.status == "in_progress",
                QCTask.scene.in_(["running", "final"]),
            )
        )
        is_global = ("sync_admin" in actor["roles"]) or (
            bool(actor["roles"] & {"admin", "super_admin"}) and not actor["institute_id"]
        )
        if not is_global:
            if not actor["institute_id"]:
                raise entry.TaskManualDefectForbidden("账号缺少机构范围")
            statement = statement.where(
                QCTaskRecord.institute_id == actor["institute_id"]
            )
        if scene != "all":
            statement = statement.where(QCTask.scene == scene)
        rows = session.execute(
            statement.order_by(QCTask.created_at.desc(), QCTaskRecord.id)
            .offset((page - 1) * 20)
            .limit(21)
        ).all()
        candidates = []
        for record, task in rows[:20]:
            run = session.scalar(
                select(QCTaskQCRun)
                .where(
                    QCTaskQCRun.task_id == task.id,
                    QCTaskQCRun.triggered_by == actor_id,
                    QCTaskQCRun.run_scope == "assigned",
                )
                .order_by(QCTaskQCRun.run_number.desc())
                .limit(1)
            )
            candidates.append(
                dict(
                    task_id=task.id,
                    task_record_id=record.id,
                    task_name=task.task_name,
                    scene=task.scene,
                    institute_id=record.institute_id,
                    patient_id=record.patient_id,
                    visit_id=record.visit_id,
                    run_number=run.run_number if run else None,
                    job_id=run.job_id if run else None,
                )
            )
    for row in candidates:
        row.update(available=False, reason="尚无本人受领运行结果")
        if row["run_number"]:
            try:
                job, envelope = entry._verified_result(
                    task_id=row["task_id"],
                    task_record_id=row["task_record_id"],
                    actor_id=actor_id,
                    run_number=row["run_number"],
                    workspace_factory=None,
                )
                row.update(available=True, reason=None, envelope_id=envelope)
            except (
                entry.TaskManualDefectConflict,
                entry.TaskManualDefectNotFound,
                entry.TaskManualDefectForbidden,
            ) as exc:
                row["reason"] = str(exc)
    return {"items": candidates, "page": page, "has_more": len(rows) > 20}


@router.get("/entry-contexts")
async def entry_contexts(
    request: Request,
    scene: Literal["all", "running", "final"] = "all",
    page: int = Query(1, ge=1),
    user: dict = Depends(get_current_user),
):
    data = await _call(
        _entry_contexts,
        actor_id=_actor(user, PermissionAction.CREATE),
        scene=scene,
        page=page,
    )
    return success_response(data=data, trace_id=get_trace_id(request))


@router.get("/pending-count")
async def pending_count(
    request: Request,
    scene: Literal["all", "running", "final"] = "all",
    user: dict = Depends(get_current_user),
):
    count = await _call(
        review.count_pending_manual_defects,
        actor_id=_actor(user, PermissionAction.REVIEW),
        scene=scene,
    )
    return success_response(
        data={"total": count, "scene": scene}, trace_id=get_trace_id(request)
    )


@router.get("")
async def list_reviews(
    request: Request,
    review_status: Literal["pending", "approved", "rejected"] = "pending",
    scene: Literal["all", "running", "final"] = "all",
    page: int = Query(1, ge=1),
    user: dict = Depends(get_current_user),
):
    data = await _call(
        review.list_manual_defects,
        actor_id=_actor(user, PermissionAction.REVIEW),
        review_status=review_status,
        scene=scene,
        page=page,
        page_size=20,
    )
    return success_response(data=data, trace_id=get_trace_id(request))


@router.post("")
async def create(
    request: Request, body: EntryRequest, user: dict = Depends(get_current_user)
):
    actor = _actor(user, PermissionAction.CREATE)
    payload = body.model_dump()
    payload["defect_id"] = str(body.defect_id)
    data = await _call(
        entry.create_task_manual_defect,
        **payload,
        actor_id=actor,
        workspace_factory=None
    )
    audit_event(
        request,
        action="manual_defects.create",
        resource="qc_defect",
        outcome="success",
        current_user=user,
        details={"defect_id": data["id"], "task_id": body.task_id},
    )
    return success_response(data=data, trace_id=get_trace_id(request))


@router.get("/entries/{task_id}/{task_record_id}")
async def own_entries(
    request: Request,
    task_id: str,
    task_record_id: str,
    offset: int = Query(0, ge=0),
    user: dict = Depends(get_current_user),
):
    data = await _call(
        entry.list_task_manual_defects,
        task_id=task_id,
        task_record_id=task_record_id,
        actor_id=_actor(user, PermissionAction.CREATE),
        offset=offset,
        limit=50,
    )
    return success_response(data=data, trace_id=get_trace_id(request))


@router.post("/{defect_id}/review")
async def decide(
    request: Request,
    defect_id: str,
    body: ReviewRequest,
    user: dict = Depends(get_current_user),
):
    data = await _call(
        review.review_manual_defect,
        defect_id=defect_id,
        reviewer_id=_actor(user, PermissionAction.REVIEW),
        **body.model_dump()
    )
    audit_event(
        request,
        action="manual_defects.review",
        resource="qc_defect",
        outcome="success",
        current_user=user,
        details={"defect_id": defect_id, "decision": body.decision},
    )
    return success_response(data=data, trace_id=get_trace_id(request))
