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
    column("task_id", String),
    column("assignee_id", String),
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
