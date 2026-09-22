"""任务抽样结果的单事务持久化。"""

from __future__ import annotations

import json
import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, Integer, String, column, func, insert, literal_column, select, table, update

from ..database.connection import SessionLocal


class SamplingTaskNotFound(LookupError):
    """抽样保存时任务已不存在。"""


class SamplingConflict(ValueError):
    """任务状态或抽样快照不允许保存。"""


_TASKS = table(
    "qc_tasks",
    column("id", String),
    column("scene", String),
    column("status", String),
    column("total_records", Integer),
    column("date_range"),
    column("department_filter"),
    column("record_ids"),
    column("sampling_method", String),
    column("sampling_config"),
    column("updated_at", DateTime),
)
_TASK_RECORDS = table(
    "qc_task_records",
    column("id", String),
    column("task_id", String),
    column("record_id", String),
    column("assignee_id", String),
    column("assignee_name", String),
    column("status", String),
    column("defect_count", Integer),
    column("created_at", DateTime),
)
_SNAPSHOT_FIELDS = (
    "scene",
    "date_range",
    "department_filter",
    "record_ids",
    "sampling_method",
    "sampling_config",
)
_JSON_FIELDS = {"date_range", "department_filter", "record_ids", "sampling_config"}


def _lock_task_statement(task_id: str):
    return (
        select(literal_column("*"))
        .select_from(_TASKS)
        .where(_TASKS.c.id == task_id)
        .with_for_update()
    )


def _normalize_snapshot_value(field: str, value: Any) -> Any:
    if field not in _JSON_FIELDS or not isinstance(value, str):
        return value
    try:
        return json.loads(value)
    except (TypeError, json.JSONDecodeError):
        return value


def _ensure_snapshot_unchanged(task_snapshot: dict[str, Any], locked_task: dict[str, Any]) -> None:
    changed_fields = [
        field
        for field in _SNAPSHOT_FIELDS
        if _normalize_snapshot_value(field, task_snapshot.get(field))
        != _normalize_snapshot_value(field, locked_task.get(field))
    ]
    if changed_fields:
        raise SamplingConflict(f"任务抽样配置已变化，请刷新后重试：{', '.join(changed_fields)}")


def _record_count(session, task_id: str) -> int:
    statement = select(func.count()).select_from(_TASK_RECORDS).where(
        _TASK_RECORDS.c.task_id == task_id
    )
    return int(session.execute(statement).scalar_one())


def _saved_records(session, task_id: str, limit: int = 20) -> list[dict[str, Any]]:
    statement = (
        select(literal_column("*"))
        .select_from(_TASK_RECORDS)
        .where(_TASK_RECORDS.c.task_id == task_id)
        .order_by(_TASK_RECORDS.c.created_at, _TASK_RECORDS.c.id)
        .limit(limit)
    )
    return [dict(row) for row in session.execute(statement).mappings().all()]


def _replay_saved_sample(session, task_id: str, locked_task: dict[str, Any]) -> dict[str, Any]:
    actual_count = _record_count(session, task_id)
    try:
        expected_count = int(locked_task.get("total_records"))
    except (TypeError, ValueError) as exc:
        raise SamplingConflict("任务抽样数量无效，无法重放") from exc
    if actual_count != expected_count:
        raise SamplingConflict("任务抽样数量与已保存关联不一致，请人工核对")
    return {
        "task_id": task_id,
        "sampled_count": actual_count,
        "records": _saved_records(session, task_id),
    }


def _build_task_records(task_id: str, sampled_records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    task_records: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    created_at = datetime.now()
    for record in sampled_records:
        record_id = record.get("id", record.get("record_id"))
        if not isinstance(record_id, str) or not record_id.strip():
            raise SamplingConflict("候选病历缺少有效ID")
        if record_id in seen_ids:
            raise SamplingConflict(f"候选病历ID重复：{record_id}")
        seen_ids.add(record_id)
        task_records.append(
            {
                "id": str(uuid.uuid4()),
                "task_id": task_id,
                "record_id": record_id,
                "assignee_id": None,
                "assignee_name": None,
                "status": "pending",
                "defect_count": 0,
                "created_at": created_at,
            }
        )
    return task_records


def save_task_sample(task_snapshot: dict[str, Any], sampled_records: list[dict[str, Any]]) -> dict[str, Any]:
    """锁定任务并原子保存抽样关联与任务状态。"""
    task_id = task_snapshot.get("id")
    if not isinstance(task_id, str) or not task_id.strip():
        raise SamplingConflict("任务ID无效")
    if SessionLocal is None:
        raise RuntimeError("数据库会话不可用")

    session = SessionLocal()
    try:
        with session.begin():
            row = session.execute(_lock_task_statement(task_id)).mappings().first()
            if row is None:
                raise SamplingTaskNotFound(f"任务 {task_id} 不存在")
            locked_task = dict(row)
            if locked_task.get("scene") is not None:
                raise SamplingConflict("场景抽样暂不可用：尚未接通可验证的病历场景范围")

            status = locked_task.get("status")
            if status == "sampling":
                result = _replay_saved_sample(session, task_id, locked_task)
            elif status != "draft":
                raise SamplingConflict(f"任务状态 {status or 'unknown'} 不允许执行抽样")
            else:
                if task_snapshot.get("status") != "draft":
                    raise SamplingConflict("任务状态已变化，请刷新后重试")
                if _record_count(session, task_id):
                    raise SamplingConflict("草稿任务已存在抽样关联，请人工核对")
                _ensure_snapshot_unchanged(task_snapshot, locked_task)
                task_records = _build_task_records(task_id, sampled_records)
                if task_records:
                    inserted = session.execute(insert(_TASK_RECORDS), task_records)
                    if inserted.rowcount != len(task_records):
                        raise RuntimeError("抽样关联写入数量不完整")
                updated = session.execute(
                    update(_TASKS)
                    .where(_TASKS.c.id == task_id, _TASKS.c.status == "draft")
                    .values(
                        status="sampling",
                        total_records=len(task_records),
                        updated_at=datetime.now(),
                    )
                )
                if updated.rowcount != 1:
                    raise RuntimeError("任务抽样状态更新失败")
                result = {
                    "task_id": task_id,
                    "sampled_count": len(task_records),
                    "records": _saved_records(session, task_id),
                }
        return result
    finally:
        session.close()
