"""任务取消的权限、运行保护与原子状态转换。"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import DateTime, String, column, exists, inspect, select, table, update

from ..database.connection import SessionLocal


class TaskCancelNotFound(LookupError):
    pass


class TaskCancelForbidden(PermissionError):
    pass


class TaskCancelConflict(ValueError):
    pass


_TASKS = table(
    "qc_tasks",
    column("id", String),
    column("creator_id", String),
    column("status", String),
    column("updated_at", DateTime(timezone=True)),
)
_RUNS = table(
    "task_qc_runs",
    column("task_id", String),
)
_ALEMBIC_VERSION = table("alembic_version", column("version_num", String))
_CANCELLABLE = frozenset({"draft", "sampling", "assigned"})
_PRE_RUN_HISTORY_REVISIONS = frozenset({
    "20260915_000044",
    "20260922_000045",
    "20260923_000046",
    "20260923_000047",
    "20260923_000048",
})


def _has_run_history(session: Any, task_id: str) -> bool:
    inspector = inspect(session.connection())
    if not inspector.has_table("task_qc_runs"):
        # 仅确认是迁移 49 之前的版本才允许没有关联表；其他 schema 漂移不能当作空历史。
        revision = session.execute(select(_ALEMBIC_VERSION.c.version_num)).scalar_one()
        if revision not in _PRE_RUN_HISTORY_REVISIONS:
            raise RuntimeError("任务运行历史表缺失，数据库版本与取消合同不一致")
        return False
    return bool(session.execute(
        select(exists(select(_RUNS.c.task_id).where(_RUNS.c.task_id == task_id)))
    ).scalar_one())


def cancel_task(*, task_id: str, actor_id: str, is_manager: bool = False) -> dict[str, Any]:
    """仅取消尚未开始且没有 workspace 运行记录的任务。"""
    if not isinstance(actor_id, str) or not actor_id.strip() or len(actor_id) > 64:
        raise TaskCancelForbidden("当前用户缺少有效身份")
    if SessionLocal is None:
        raise RuntimeError("数据库会话不可用")

    with SessionLocal() as session:
        with session.begin():
            task = session.execute(
                select(_TASKS.c.creator_id, _TASKS.c.status, _TASKS.c.updated_at)
                .where(_TASKS.c.id == task_id)
                .with_for_update()
            ).mappings().first()
            if task is None:
                raise TaskCancelNotFound("任务不存在")

            creator_id = task["creator_id"]
            if not creator_id or creator_id != actor_id:
                raise TaskCancelForbidden("仅任务创建人可取消任务")
            if task["status"] == "cancelled":
                updated_at = task["updated_at"]
                if updated_at is not None and updated_at.tzinfo is None:
                    updated_at = updated_at.replace(tzinfo=timezone.utc)
                return {
                    "task_id": task_id,
                    "status": "cancelled",
                    "updated_at": updated_at.isoformat() if updated_at else None,
                    "idempotent": True,
                }
            if task["status"] not in _CANCELLABLE:
                raise TaskCancelConflict("任务当前状态不允许取消")

            if _has_run_history(session, task_id):
                raise TaskCancelConflict("任务已有质控运行记录，请先处理关联 job")

            now = datetime.now(timezone.utc)
            changed = session.execute(
                update(_TASKS)
                .where(_TASKS.c.id == task_id, _TASKS.c.status == task["status"])
                .values(status="cancelled", updated_at=now)
            )
            if changed.rowcount != 1:
                raise TaskCancelConflict("任务状态已变化，请刷新后重试")
            return {
                "task_id": task_id,
                "status": "cancelled",
                "updated_at": now.isoformat(),
                "idempotent": False,
            }
