"""任务抽样结果的单事务持久化。"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timedelta
from typing import Any, Callable

from sqlalchemy import DateTime, Integer, String, column, func, insert, literal_column, select, table, update

from ..database.connection import SessionLocal


class SamplingTaskNotFound(LookupError):
    """抽样保存时任务已不存在。"""


class SamplingConflict(ValueError):
    """任务状态或抽样快照不允许保存。"""


class SamplingForbidden(PermissionError):
    """当前用户不是任务创建人。"""


_TASKS = table(
    "qc_tasks",
    column("id", String),
    column("creator_id", String),
    column("scene", String),
    column("status", String),
    column("total_records", Integer),
    column("date_range"),
    column("department_filter"),
    column("record_ids"),
    column("record_refs"),
    column("sampling_method", String),
    column("sampling_config"),
    column("updated_at", DateTime),
)
_TASK_RECORDS = table(
    "qc_task_records",
    column("id", String),
    column("task_id", String),
    column("record_id", String),
    column("institute_id", String),
    column("patient_id", String),
    column("visit_id", String),
    column("assignee_id", String),
    column("assignee_name", String),
    column("status", String),
    column("defect_count", Integer),
    column("created_at", DateTime),
    column("department", String),
)
_SNAPSHOT_FIELDS = (
    "scene",
    "date_range",
    "department_filter",
    "record_ids",
    "sampling_method",
    "sampling_config",
)
_JSON_FIELDS = {"date_range", "department_filter", "record_ids", "record_refs", "sampling_config"}
_CASE_COORDINATES = ("institute_id", "patient_id", "visit_id")
_MODERN_SCENES = frozenset({"outpatient", "running", "final"})
_MODERN_RESPONSE = {"record_id_semantics": "association_id_not_medical_record_id"}


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


def _ensure_snapshot_unchanged(
    task_snapshot: dict[str, Any], locked_task: dict[str, Any], *, modern: bool = False
) -> None:
    changed_fields = [
        field
        for field in _SNAPSHOT_FIELDS
        if _normalize_snapshot_value(field, task_snapshot.get(field))
        != _normalize_snapshot_value(field, locked_task.get(field))
    ]
    if changed_fields:
        raise SamplingConflict(f"任务抽样配置已变化，请刷新后重试：{', '.join(changed_fields)}")
    if modern:
        if "record_refs" not in locked_task or "record_refs" not in task_snapshot:
            raise SamplingConflict("任务缺少三坐标配置列或快照，请先完成迁移并刷新任务")
        if _normalize_snapshot_value("record_refs", task_snapshot["record_refs"]) != _normalize_snapshot_value(
            "record_refs", locked_task["record_refs"]
        ):
            raise SamplingConflict("任务抽样配置已变化，请刷新后重试：record_refs")


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


def _replay_saved_sample(
    session, task_id: str, locked_task: dict[str, Any], *, modern: bool = False
) -> dict[str, Any]:
    actual_count = _record_count(session, task_id)
    try:
        expected_count = int(locked_task.get("total_records"))
    except (TypeError, ValueError) as exc:
        raise SamplingConflict("任务抽样数量无效，无法重放") from exc
    if actual_count != expected_count:
        raise SamplingConflict("任务抽样数量与已保存关联不一致，请人工核对")
    records = _saved_records(session, task_id)
    if modern:
        _require_coordinate_columns(session)
        _validate_saved_modern_records(session, task_id, _configured_case_identities(locked_task))
    return {
        "task_id": task_id,
        "sampled_count": actual_count,
        "records": records,
        **(_MODERN_RESPONSE if modern else {}),
    }


def _case_identity(value: Any) -> tuple[str, str, str]:
    if not isinstance(value, dict):
        raise SamplingConflict("候选病历缺少完整三坐标")
    coordinates: list[str] = []
    for field in _CASE_COORDINATES:
        coordinate = value.get(field)
        if not isinstance(coordinate, str) or not coordinate.strip() or len(coordinate.strip()) > 100:
            raise SamplingConflict("候选病历缺少有效三坐标")
        coordinates.append(coordinate.strip())
    return coordinates[0], coordinates[1], coordinates[2]


def _configured_case_identities(locked_task: dict[str, Any]) -> set[tuple[str, str, str]] | None:
    configured = _normalize_snapshot_value("record_refs", locked_task["record_refs"])
    if configured is None or configured == []:
        return None
    if not isinstance(configured, list):
        raise SamplingConflict("任务三坐标配置无效")
    identities = [_case_identity(item) for item in configured]
    if len(identities) != len(set(identities)):
        raise SamplingConflict("任务三坐标配置包含重复病例")
    return set(identities)


def _require_coordinate_columns(session) -> None:
    # 读零行即可使旧库缺列在写入前失败，不能降级为 legacy 身份。
    session.execute(select(*(_TASK_RECORDS.c[field] for field in _CASE_COORDINATES)).limit(0))


def _validate_saved_modern_records(session, task_id: str, expected: set[tuple[str, str, str]] | None = None) -> None:
    rows = session.execute(
        select(_TASK_RECORDS.c.id, _TASK_RECORDS.c.record_id,
               *(_TASK_RECORDS.c[field] for field in _CASE_COORDINATES))
        .where(_TASK_RECORDS.c.task_id == task_id)
    ).all()
    if any(row.id != row.record_id for row in rows):
        raise SamplingConflict("任务已保存病例的兼容标识不符合三坐标合同，请人工核对")
    identities = [_case_identity(dict(zip(_CASE_COORDINATES, row[2:]))) for row in rows]
    if len(identities) != len(set(identities)):
        raise SamplingConflict("任务已保存病例存在重复三坐标，请人工核对")
    if expected is not None and set(identities) != expected:
        raise SamplingConflict("指定病历固定集合与已保存病例不一致")


def _candidate_department(record: dict[str, Any]) -> str | None:
    """候选科室去空白后持久化；空值写 NULL，超长失败关闭而不截断。"""
    department = record.get("department")
    if not isinstance(department, str) or not department.strip():
        return None
    department = department.strip()
    if len(department) > 100:
        raise SamplingConflict("候选病历科室名称超过 100 字符")
    return department


def _build_modern_task_records(
    task_id: str, sampled_records: list[dict[str, Any]], allowed: set[tuple[str, str, str]] | None
) -> list[dict[str, Any]]:
    task_records: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str]] = set()
    created_at = datetime.now()
    for index, record in enumerate(sampled_records):
        identity = _case_identity(record)
        if identity in seen:
            raise SamplingConflict("候选病历三坐标重复")
        if allowed is not None and identity not in allowed:
            raise SamplingConflict("候选病历不属于任务指定的三坐标范围")
        seen.add(identity)
        association_id = str(uuid.uuid4())
        task_records.append(
            {
                "id": association_id,
                "task_id": task_id,
                # 旧列不可空；现代路径中仅是关联标识，绝不可作为病历 ID 查询。
                "record_id": association_id,
                "institute_id": identity[0],
                "patient_id": identity[1],
                "visit_id": identity[2],
                "assignee_id": None,
                "assignee_name": None,
                "status": "pending",
                "defect_count": 0,
                "created_at": created_at + timedelta(microseconds=index),
                "department": _candidate_department(record),
            }
        )
    if allowed is not None and seen != allowed:
        raise SamplingConflict("指定病历必须完整保存，不允许二次抽样")
    return task_records


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


def save_task_sample(
    task_snapshot: dict[str, Any],
    sampled_records: list[dict[str, Any]],
    *,
    actor_id: str,
    transaction_guard: Callable[[Any], None] | None = None,
) -> dict[str, Any]:
    """锁定任务并原子保存；可选 guard 与抽样写入共享同一事务。"""
    task_id = task_snapshot.get("id")
    if not isinstance(task_id, str) or not task_id.strip():
        raise SamplingConflict("任务ID无效")
    if SessionLocal is None:
        raise RuntimeError("数据库会话不可用")

    session = SessionLocal()
    try:
        with session.begin():
            if transaction_guard is not None:
                transaction_guard(session)
            row = session.execute(_lock_task_statement(task_id)).mappings().first()
            if row is None:
                raise SamplingTaskNotFound(f"任务 {task_id} 不存在")
            locked_task = dict(row)
            if not actor_id or not str(actor_id).strip() or locked_task.get("creator_id") != actor_id:
                raise SamplingForbidden("仅任务创建人可执行抽样")
            if task_snapshot.get("creator_id") != locked_task["creator_id"]:
                raise SamplingConflict("任务创建人已变化，请刷新后重试")
            scene = locked_task.get("scene")
            if scene is not None and scene not in _MODERN_SCENES:
                raise SamplingConflict("场景抽样暂不可用：尚未接通可验证的病历场景范围")
            modern = scene in _MODERN_SCENES
            if modern:
                _ensure_snapshot_unchanged(task_snapshot, locked_task, modern=True)
                from .task_sampling_service import validate_specified_case_sampling
                try:
                    validate_specified_case_sampling(
                        locked_task.get("sampling_method"),
                        _normalize_snapshot_value("sampling_config", locked_task.get("sampling_config")),
                        _normalize_snapshot_value("record_refs", locked_task.get("record_refs")),
                    )
                except ValueError as exc:
                    raise SamplingConflict(str(exc)) from exc
                if _normalize_snapshot_value("record_ids", locked_task.get("record_ids")):
                    raise SamplingConflict("三坐标任务不得混用旧 record_ids")
                _require_coordinate_columns(session)

            status = locked_task.get("status")
            if status == "sampling":
                result = _replay_saved_sample(session, task_id, locked_task, modern=modern)
            elif status != "draft":
                raise SamplingConflict(f"任务状态 {status or 'unknown'} 不允许执行抽样")
            else:
                if task_snapshot.get("status") != "draft":
                    raise SamplingConflict("任务状态已变化，请刷新后重试")
                if _record_count(session, task_id):
                    raise SamplingConflict("草稿任务已存在抽样关联，请人工核对")
                if not modern:
                    _ensure_snapshot_unchanged(task_snapshot, locked_task)
                task_records = (
                    _build_modern_task_records(
                        task_id, sampled_records, _configured_case_identities(locked_task)
                    )
                    if modern else _build_task_records(task_id, sampled_records)
                )
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
                    **(_MODERN_RESPONSE if modern else {}),
                }
        return result
    finally:
        session.close()
