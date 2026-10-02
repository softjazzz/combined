"""只删除没有病例和运行历史的草稿任务。"""

from __future__ import annotations

from typing import Any

from sqlalchemy import String, column, delete, exists, inspect, select, table, text

from ..database.connection import SessionLocal


class TaskDeleteNotFound(LookupError):
    pass


class TaskDeleteConflict(ValueError):
    pass


class TaskDeleteForbidden(PermissionError):
    pass


_TASKS = table("qc_tasks", column("id", String), column("status", String), column("creator_id", String))
_RECORDS = table("qc_task_records", column("task_id", String))
_RUNS = table("task_qc_runs", column("task_id", String))
_ALEMBIC_VERSION = table("alembic_version", column("version_num", String))
_PRE_RUN_HISTORY_REVISIONS = frozenset({
    "20260915_000044",
    "20260922_000045",
    "20260923_000046",
    "20260923_000047",
    "20260923_000048",
})


def _lock_association_tables(session: Any) -> bool:
    inspector = inspect(session.connection())
    if not inspector.has_table("qc_task_records"):
        raise RuntimeError("任务病例表缺失")
    has_runs = inspector.has_table("task_qc_runs")
    if not has_runs:
        revision = session.execute(select(_ALEMBIC_VERSION.c.version_num)).scalar_one()
        if revision not in _PRE_RUN_HISTORY_REVISIONS:
            raise RuntimeError("任务运行历史表缺失")

    if session.bind.dialect.name == "postgresql":
        # 病例表没有 task_id 外键；行锁本身无法阻止另一个事务并发插入。
        session.execute(text("LOCK TABLE qc_task_records IN SHARE MODE"))
        if has_runs:
            session.execute(text("LOCK TABLE task_qc_runs IN SHARE MODE"))
    return has_runs


def delete_empty_draft_task(*, task_id: str, actor_id: str) -> None:
    if not isinstance(actor_id, str) or not actor_id.strip():
        raise TaskDeleteForbidden("当前用户缺少有效身份")
    if SessionLocal is None:
        raise RuntimeError("数据库会话不可用")

    with SessionLocal() as session:
        with session.begin():
            task = session.execute(
                select(_TASKS.c.status, _TASKS.c.creator_id).where(_TASKS.c.id == task_id).with_for_update()
            ).first()
            if task is None:
                raise TaskDeleteNotFound("任务不存在")
            if not task.creator_id or task.creator_id != actor_id:
                raise TaskDeleteForbidden("仅任务创建人可删除任务")
            if task.status != "draft":
                raise TaskDeleteConflict("仅可删除草稿任务")

            has_runs = _lock_association_tables(session)
            has_records = session.execute(
                select(exists(select(_RECORDS.c.task_id).where(_RECORDS.c.task_id == task_id)))
            ).scalar_one()
            if has_records:
                raise TaskDeleteConflict("任务已有病例，不允许删除")
            if has_runs and session.execute(
                select(exists(select(_RUNS.c.task_id).where(_RUNS.c.task_id == task_id)))
            ).scalar_one():
                raise TaskDeleteConflict("任务已有质控运行记录，不允许删除")

            changed = session.execute(
                delete(_TASKS).where(_TASKS.c.id == task_id, _TASKS.c.status == "draft")
            )
            if changed.rowcount != 1:
                raise TaskDeleteConflict("任务状态已变化，请刷新后重试")
