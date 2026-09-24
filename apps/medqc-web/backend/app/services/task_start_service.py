"""受领人开始任务的原子状态转换。"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import DateTime, String, column, exists, select, table, update

from ..database.connection import SessionLocal


class TaskStartNotFound(LookupError):
    pass


class TaskStartForbidden(PermissionError):
    pass


class TaskStartConflict(ValueError):
    pass


# 这里只读取 revision 44 已有字段，避免后续 ORM 新列把旧库启动操作锁死。
_TASKS = table(
    "qc_tasks",
    column("id", String),
    column("status", String),
    column("updated_at", DateTime(timezone=True)),
)
_RECORDS = table(
    "qc_task_records",
    column("id", String),
    column("task_id", String),
    column("assignee_id", String),
    column("status", String),
)


def _is_assignee(task_id: str, actor_id: str):
    return exists(
        select(_RECORDS.c.task_id).where(
            _RECORDS.c.task_id == task_id,
            _RECORDS.c.assignee_id == actor_id,
        )
    )


def start_assigned_task(*, task_id: str, actor_id: str) -> dict[str, Any]:
    if SessionLocal is None:
        raise RuntimeError("数据库会话不可用")

    with SessionLocal() as session:
        with session.begin():
            now = datetime.now(timezone.utc)
            changed = session.execute(
                update(_TASKS)
                .where(
                    _TASKS.c.id == task_id,
                    _TASKS.c.status == "assigned",
                    _is_assignee(task_id, actor_id),
                )
                .values(status="in_progress", updated_at=now)
            )
            if changed.rowcount == 1:
                return {"id": task_id, "status": "in_progress", "updated_at": now.isoformat()}

            task_row = session.execute(
                select(_TASKS.c.status, _TASKS.c.updated_at).where(_TASKS.c.id == task_id)
            ).mappings().first()
            if task_row is None:
                raise TaskStartNotFound("任务不存在")
            has_assignment = session.execute(
                select(_is_assignee(task_id, actor_id))
            ).scalar_one()
            if not has_assignment:
                raise TaskStartForbidden("当前用户未受领该任务")
            if task_row["status"] == "in_progress":
                updated_at = task_row["updated_at"]
                return {
                    "id": task_id,
                    "status": "in_progress",
                    "updated_at": updated_at.isoformat() if updated_at else None,
                    "idempotent": True,
                }
            raise TaskStartConflict("任务当前状态不允许开始")


def _record_start_update(task_id: str, task_record_id: str, actor_id: str):
    active_task = exists(
        select(_TASKS.c.id).where(
            _TASKS.c.id == task_id,
            _TASKS.c.status == "in_progress",
        )
    )
    return (
        update(_RECORDS)
        .where(
            _RECORDS.c.id == task_record_id,
            _RECORDS.c.task_id == task_id,
            _RECORDS.c.assignee_id == actor_id,
            _RECORDS.c.status == "pending",
            active_task,
        )
        .values(status="in_progress")
    )


def _task_start_lock(task_id: str):
    return select(_TASKS.c.status).where(_TASKS.c.id == task_id).with_for_update()


def start_assigned_task_record(*, task_id: str, task_record_id: str, actor_id: str) -> dict[str, Any]:
    """受领人开始单份病历；任务与记录状态在同一条 UPDATE 中共同约束。"""
    if not isinstance(actor_id, str) or not actor_id.strip() or len(actor_id) > 64:
        raise TaskStartForbidden("当前用户缺少有效身份")
    if SessionLocal is None:
        raise RuntimeError("数据库会话不可用")

    with SessionLocal() as session:
        with session.begin():
            # 取消任务也更新此行；PostgreSQL 行锁令两种操作按事务顺序生效。
            task_status = session.execute(_task_start_lock(task_id)).scalar_one_or_none()
            if task_status is None:
                raise TaskStartNotFound("任务不存在")
            changed = session.execute(_record_start_update(task_id, task_record_id, actor_id))
            if changed.rowcount == 1:
                return {
                    "task_id": task_id,
                    "task_record_id": task_record_id,
                    "status": "in_progress",
                    "idempotent": False,
                }

            record = session.execute(
                select(_RECORDS.c.assignee_id, _RECORDS.c.status).where(
                    _RECORDS.c.id == task_record_id,
                    _RECORDS.c.task_id == task_id,
                )
            ).mappings().first()
            if record is None:
                raise TaskStartNotFound("任务病历不存在")
            if record["assignee_id"] != actor_id:
                raise TaskStartForbidden("当前用户未受领该病历")
            if task_status != "in_progress":
                raise TaskStartConflict("任务当前状态不允许开始病历")
            if record["status"] == "in_progress":
                return {
                    "task_id": task_id,
                    "task_record_id": task_record_id,
                    "status": "in_progress",
                    "idempotent": True,
                }
            raise TaskStartConflict("病历当前状态不允许开始")
