"""把已抽样任务与四川 workspace 批量 job 原子关联。"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Callable

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..database.connection import SessionLocal
from ..database.models.qc import QCTask, QCTaskQCRun, QCTaskRecord
from .qc_rule_sets import get_sichuan_rule_set
from .sichuan_workspace_batch_prepare import (
    SichuanWorkspaceBatchJobCreateRequest,
    prepare_workspace_batch_job,
)


logger = logging.getLogger(__name__)


class TaskQCRunNotFound(LookupError):
    pass


class TaskQCRunForbidden(PermissionError):
    pass


class TaskQCRunConflict(ValueError):
    pass


class TaskQCRunDispatchError(RuntimeError):
    def __init__(self, job_id: str):
        super().__init__(f"批量质控任务 {job_id} 已创建，但后台派发失败")
        self.job_id = job_id


def _task_and_refs(
    session: Session, task_id: str, actor_id: str, run_scope: str,
) -> tuple[dict[str, Any], list[dict[str, str]]]:
    task_row = session.execute(
        select(QCTask.__table__)
        .where(QCTask.id == task_id)
        .with_for_update()
    ).mappings().first()
    if task_row is None:
        raise TaskQCRunNotFound("任务不存在")
    task = dict(task_row)
    if run_scope == "all" and task.get("creator_id") != actor_id:
        raise TaskQCRunForbidden("仅任务创建人可启动整批质控")
    scene = task.get("scene")
    if scene == "outpatient":
        raise TaskQCRunConflict("门急诊场景尚无可执行的规则集与 workspace 资料链")
    if scene not in ("running", "final"):
        raise TaskQCRunConflict("历史任务尚无完整三坐标执行合同")
    allowed_statuses = {"sampling", "assigned", "in_progress", "completed"} if run_scope == "all" else {
        "assigned", "in_progress", "completed",
    }
    if task.get("status") not in allowed_statuses:
        raise TaskQCRunConflict("任务未完成抽样或已取消")
    rule_set_key = task.get("rule_set_key")
    rule_set = get_sichuan_rule_set(rule_set_key) if rule_set_key else None
    if rule_set is None or rule_set.scope != scene:
        raise TaskQCRunConflict("任务规则集已失效或与场景不匹配")

    rows = session.execute(
        select(QCTaskRecord.__table__)
        .where(QCTaskRecord.task_id == task_id)
        .order_by(QCTaskRecord.created_at, QCTaskRecord.id)
    ).mappings().all()
    try:
        expected_count = int(task.get("total_records"))
    except (TypeError, ValueError) as exc:
        raise TaskQCRunConflict("任务抽样数量无效") from exc
    if expected_count <= 0 or len(rows) != expected_count:
        raise TaskQCRunConflict("任务抽样关联与数量不一致")

    refs: list[dict[str, str]] = []
    assigned_refs: list[dict[str, str]] = []
    seen: set[tuple[str, str, str]] = set()
    for row in rows:
        identity = tuple(str(row.get(key) or "").strip() for key in ("institute_id", "patient_id", "visit_id"))
        if any(not value or len(value) > 100 for value in identity):
            raise TaskQCRunConflict("任务病历缺少完整三坐标")
        if row["record_id"] != row["id"] or identity in seen:
            raise TaskQCRunConflict("任务病历身份不符合三坐标抽样合同")
        if run_scope == "assigned" and not str(row.get("assignee_id") or "").strip():
            raise TaskQCRunConflict("任务病历尚未完成分配")
        seen.add(identity)
        ref = dict(zip(("institute_id", "patient_id", "visit_id"), identity))
        refs.append(ref)
        if row.get("assignee_id") == actor_id:
            assigned_refs.append(ref)
    if run_scope == "assigned":
        if not assigned_refs:
            raise TaskQCRunForbidden("当前用户未获分配此任务病历")
        return task, assigned_refs
    return task, refs


def _next_run_number(session: Session, task_id: str, workspace: Any) -> int:
    previous = session.execute(
        select(QCTaskQCRun.__table__)
        .where(QCTaskQCRun.task_id == task_id)
        .order_by(QCTaskQCRun.run_number.desc())
        .limit(1)
    ).mappings().first()
    if previous is None:
        return 1
    job = workspace.get_batch_job(job_id=previous["job_id"], created_by=previous["triggered_by"])
    if job is None:
        raise TaskQCRunConflict("上次质控 job 不可读取，请先核对运行历史")
    if job.get("status") not in {"completed", "failed", "canceled", "cancelled"}:
        raise TaskQCRunConflict("任务已有运行中或状态未知的质控 job")
    return int(previous["run_number"]) + 1


def create_task_qc_run(
    *,
    task_id: str,
    actor_id: str,
    current_user: dict[str, Any],
    workspace_factory: Callable[[], Any],
    qc_service: Any,
    dispatch: Callable[[str], Any],
    run_scope: str = "all",
) -> dict[str, Any]:
    """任务行锁串行化重跑；job 和运行关联同一事务，提交后才派发。"""
    if SessionLocal is None:
        raise RuntimeError("数据库会话不可用")
    if not actor_id or len(actor_id) > 64:
        raise TaskQCRunForbidden("当前用户缺少有效身份")
    if run_scope not in {"all", "assigned"}:
        raise TaskQCRunConflict("运行范围无效")

    with SessionLocal() as session:
        with session.begin():
            task, refs = _task_and_refs(session, task_id, actor_id, run_scope)
            workspace = workspace_factory()
            run_number = _next_run_number(session, task_id, workspace)
            payload = SichuanWorkspaceBatchJobCreateRequest(
                rule_set_key=task["rule_set_key"],
                scope=task["scene"],
                record_refs=refs,
            )
            prepared = prepare_workspace_batch_job(
                payload,
                current_user=current_user,
                qc_service=qc_service,
                workspace=workspace,
                task_run_context={"task_id": task_id, "run_number": str(run_number)},
            )
            job = workspace.create_batch_job(
                created_by=actor_id,
                session=session,
                **prepared.create_kwargs,
            )
            job_id = str(job.get("id") or "").strip()
            if not job_id:
                raise RuntimeError("workspace job 创建未返回有效 ID")
            session.add(QCTaskQCRun(
                task_id=task_id,
                run_number=run_number,
                job_id=job_id,
                triggered_by=actor_id,
                run_scope=run_scope,
                created_at=datetime.now(timezone.utc).replace(tzinfo=None),
            ))
        # 事务已提交，worker 现在才能读到完整 job 与关联。
    try:
        dispatch(job_id)
    except Exception as exc:
        logger.exception("任务质控 job 派发失败: %s", job_id)
        try:
            workspace.fail_batch_job(job_id=job_id, error_message="后台派发失败，请重试任务质控")
        except Exception:
            logger.exception("无法标记派发失败的 job: %s", job_id)
        raise TaskQCRunDispatchError(job_id) from exc
    return {"task_id": task_id, "run_number": run_number, "job_id": job_id,
            "run_scope": run_scope, "status": "queued"}


def list_task_qc_runs(*, task_id: str, actor_id: str, run_scope: str = "all") -> list[dict[str, Any]]:
    """只返回请求范围内本人可见的 run；job 状态由 workspace 接口提供。"""
    if SessionLocal is None:
        raise RuntimeError("数据库会话不可用")
    if not actor_id or len(actor_id) > 64:
        raise TaskQCRunForbidden("当前用户缺少有效身份")
    if run_scope not in {"all", "assigned"}:
        raise TaskQCRunConflict("运行范围无效")
    with SessionLocal() as session:
        task = session.execute(
            select(QCTask.id, QCTask.creator_id).where(QCTask.id == task_id)
        ).mappings().first()
        if task is None:
            raise TaskQCRunNotFound("任务不存在")
        if run_scope == "all" and task["creator_id"] != actor_id:
            raise TaskQCRunForbidden("仅任务创建人可查看整批质控运行历史")
        if run_scope == "assigned":
            is_assignee = session.execute(
                select(QCTaskRecord.id).where(
                    QCTaskRecord.task_id == task_id,
                    QCTaskRecord.assignee_id == actor_id,
                ).limit(1)
            ).first() is not None
            has_history = session.execute(
                select(QCTaskQCRun.job_id).where(
                    QCTaskQCRun.task_id == task_id,
                    QCTaskQCRun.run_scope == "assigned",
                    QCTaskQCRun.triggered_by == actor_id,
                ).limit(1)
            ).first() is not None
            if not is_assignee and not has_history:
                raise TaskQCRunForbidden("当前用户未获分配此任务病历")
        statement = (
            select(QCTaskQCRun.__table__)
            .where(QCTaskQCRun.task_id == task_id, QCTaskQCRun.run_scope == run_scope)
            .order_by(QCTaskQCRun.run_number.desc())
        )
        if run_scope == "assigned":
            statement = statement.where(QCTaskQCRun.triggered_by == actor_id)
        rows = session.execute(statement).mappings().all()
        return [dict(row) for row in rows]
