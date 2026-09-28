"""任务编辑的授权、状态守卫与配置版本 CAS。

任务身份、场景和冻结规则集不属于本模块的可编辑接口。草稿规划仅能在单次任务尚未
物化任何病历或运行记录时整表替换；抽样后的任务只允许修改名称和截止时间。
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from pydantic import ValidationError
from sqlalchemy import JSON, DateTime, Integer, String, column, func, select, table, update

from ..database.connection import SessionLocal
from ..schemas.tasks import (
    TaskDraftConfigurationUpdateRequest,
    TaskEditResponse,
    TaskMetadataUpdateRequest,
    TaskTemplateConfig,
)
from .task_sampling_service import validate_active_running_date_range, validate_scoped_sampling_config


class TaskEditError(Exception):
    code = "task_edit_unavailable"


class TaskEditNotFound(TaskEditError, LookupError):
    code = "task_not_found"


class TaskEditForbidden(TaskEditError, PermissionError):
    code = "task_edit_forbidden"


class TaskEditConflict(TaskEditError, ValueError):
    def __init__(self, message: str, *, code: str = "state_conflict") -> None:
        super().__init__(message)
        self.code = code


class TaskEditInvalid(TaskEditError, ValueError):
    code = "task_edit_invalid"


class TaskEditUnavailable(TaskEditError, RuntimeError):
    code = "task_edit_unavailable"


_TASKS = table(
    "qc_tasks",
    column("id", String),
    column("task_number", String),
    column("task_name", String),
    column("task_type", String),
    column("scene", String),
    column("rule_set_key", String),
    column("rule_set_version", String),
    column("deadline", String),
    column("date_range"),
    column("department_filter"),
    column("record_ids"),
    column("record_refs", JSON),
    column("sampling_method", String),
    column("sampling_config"),
    column("assign_method", String),
    column("assignee_config"),
    column("status", String),
    column("creator_id", String),
    column("configuration_version", Integer),
    column("updated_at", DateTime),
)
_TASK_RECORDS = table(
    "qc_task_records",
    column("task_id", String),
)
_TASK_RUNS = table(
    "task_qc_runs",
    column("task_id", String),
)

_FULL_EDITABLE_FIELDS = (
    "task_name",
    "deadline",
    "date_range",
    "department_filter",
    "record_refs",
    "sampling_method",
    "sampling_config",
    "assign_method",
    "assignee_config",
)
_METADATA_FIELDS = ("task_name", "deadline")
_METADATA_STATUSES = frozenset({"draft", "sampling", "assigned", "in_progress"})
_JSON_LIST_FIELDS = ("department_filter", "record_ids", "record_refs")


def _actor_id(value: Any) -> str:
    if not isinstance(value, str) or not value.strip() or len(value.strip()) > 64:
        raise TaskEditForbidden("当前用户缺少有效身份")
    return value.strip()


def _task_id(value: Any) -> str:
    if not isinstance(value, str) or not value.strip() or len(value.strip()) > 100:
        raise TaskEditNotFound("任务不存在")
    return value.strip()


def _version(value: Any) -> int:
    if type(value) is not int or value < 1:
        raise TaskEditInvalid("configuration_version 无效")
    return value


def _decode_json(value: Any, *, field: str, expected: type, default: Any) -> Any:
    if value is None:
        return default
    decoded = value
    if isinstance(value, str):
        try:
            decoded = json.loads(value)
        except (TypeError, json.JSONDecodeError) as exc:
            raise TaskEditUnavailable(f"任务字段 {field} 已损坏") from exc
    if not isinstance(decoded, expected):
        raise TaskEditUnavailable(f"任务字段 {field} 已损坏")
    return decoded


def _normalized_row(row: Any) -> dict[str, Any]:
    task = dict(row)
    task["date_range"] = _decode_json(
        task.get("date_range"), field="date_range", expected=dict, default=None,
    )
    for field in ("sampling_config", "assignee_config"):
        task[field] = _decode_json(task.get(field), field=field, expected=dict, default=None)
    for field in _JSON_LIST_FIELDS:
        task[field] = _decode_json(task.get(field), field=field, expected=list, default=None)
    version = task.get("configuration_version")
    if type(version) is not int or version < 1:
        raise TaskEditUnavailable("任务配置版本无效")
    return task


def _relation_counts(session: Any, task_id: str) -> tuple[int, int]:
    record_count = int(session.execute(
        select(func.count()).select_from(_TASK_RECORDS).where(_TASK_RECORDS.c.task_id == task_id)
    ).scalar_one())
    run_count = int(session.execute(
        select(func.count()).select_from(_TASK_RUNS).where(_TASK_RUNS.c.task_id == task_id)
    ).scalar_one())
    return record_count, run_count


def _authorize(task: dict[str, Any], actor_id: str, is_manager: bool) -> None:
    creator_id = task.get("creator_id")
    if not isinstance(creator_id, str) or not creator_id.strip():
        raise TaskEditForbidden("任务缺少可核实的创建人，不能编辑")
    if not is_manager and creator_id != actor_id:
        raise TaskEditForbidden("仅任务创建人或管理员可编辑任务")


def _editable_fields(task: dict[str, Any], record_count: int, run_count: int) -> list[str]:
    status = task.get("status")
    if (
        task.get("task_type") == "one_time"
        and status == "draft"
        and record_count == 0
        and run_count == 0
        and task.get("scene") in {"running", "final", "outpatient"}
        and isinstance(task.get("rule_set_key"), str)
        and bool(task["rule_set_key"].strip())
        and isinstance(task.get("rule_set_version"), str)
        and bool(task["rule_set_version"].strip())
        and not task.get("record_ids")
    ):
        return list(_FULL_EDITABLE_FIELDS)
    if status in _METADATA_STATUSES:
        return list(_METADATA_FIELDS)
    return []


def _response(task: dict[str, Any], record_count: int, run_count: int) -> dict[str, Any]:
    updated_at = task.get("updated_at")
    if isinstance(updated_at, datetime):
        if updated_at.tzinfo is None:
            updated_at = updated_at.replace(tzinfo=timezone.utc)
        updated_at = updated_at.isoformat()
    data = {
        "id": task.get("id"),
        "task_number": task.get("task_number"),
        "task_name": task.get("task_name"),
        "task_type": task.get("task_type"),
        "status": task.get("status"),
        "scene": task.get("scene"),
        "rule_set_key": task.get("rule_set_key"),
        "rule_set_version": task.get("rule_set_version"),
        "deadline": task.get("deadline"),
        "date_range": task.get("date_range") or None,
        "department_filter": task.get("department_filter"),
        "record_refs": task.get("record_refs"),
        "sampling_method": task.get("sampling_method"),
        "sampling_config": task.get("sampling_config"),
        "assign_method": task.get("assign_method"),
        "assignee_config": task.get("assignee_config"),
        "configuration_version": task.get("configuration_version"),
        "editable_fields": _editable_fields(task, record_count, run_count),
        "updated_at": updated_at,
    }
    try:
        return TaskEditResponse.model_validate(data).model_dump(mode="json")
    except ValidationError as exc:
        raise TaskEditUnavailable("任务编辑响应合同无法确认") from exc


def _read_task(session: Any, task_id: str, *, lock: bool) -> dict[str, Any] | None:
    statement = select(_TASKS).where(_TASKS.c.id == task_id)
    if lock:
        statement = statement.with_for_update()
    row = session.execute(statement).mappings().first()
    return _normalized_row(row) if row is not None else None


def _session() -> Any:
    if SessionLocal is None:
        raise TaskEditUnavailable("任务编辑服务暂不可用")
    return SessionLocal()


def get_task_edit(task_id: str, *, actor_id: str, is_manager: bool = False) -> dict[str, Any]:
    task_id = _task_id(task_id)
    actor_id = _actor_id(actor_id)
    try:
        with _session() as session:
            task = _read_task(session, task_id, lock=False)
            if task is None:
                raise TaskEditNotFound("任务不存在")
            _authorize(task, actor_id, bool(is_manager))
            record_count, run_count = _relation_counts(session, task_id)
            return _response(task, record_count, run_count)
    except TaskEditError:
        raise
    except Exception as exc:
        raise TaskEditUnavailable("任务编辑信息暂不可用") from exc


def _validate_configuration(task: dict[str, Any], configuration: Any) -> dict[str, Any]:
    if not isinstance(configuration, dict):
        raise TaskEditInvalid("任务配置无效")
    if set(configuration) != set(_FULL_EDITABLE_FIELDS):
        raise TaskEditInvalid("任务配置字段不完整或含不支持字段")
    try:
        parsed_request = TaskDraftConfigurationUpdateRequest.model_validate({
            "configuration_version": 1,
            **configuration,
        })
    except ValidationError as exc:
        first = exc.errors(include_url=False)[0] if exc.errors() else {}
        message = str(first.get("msg") or "任务配置无效").removeprefix("Value error, ")
        raise TaskEditInvalid(message) from exc
    configuration = parsed_request.model_dump(mode="json", exclude={"configuration_version"})
    scene = task.get("scene")
    rule_set_key = task.get("rule_set_key")
    rule_set_version = task.get("rule_set_version")
    if scene not in {"running", "final", "outpatient"}:
        raise TaskEditConflict("任务缺少可核实的冻结场景", code="state_conflict")
    if not isinstance(rule_set_key, str) or not rule_set_key.strip() or not isinstance(rule_set_version, str) or not rule_set_version.strip():
        raise TaskEditConflict("任务缺少可核实的冻结规则集", code="state_conflict")
    reusable = {
        "scene": scene,
        "rule_set_key": rule_set_key,
        **{key: configuration[key] for key in (
            "date_range", "department_filter", "sampling_method", "sampling_config",
            "assign_method", "assignee_config",
        )},
    }
    try:
        normalized = TaskTemplateConfig.model_validate(reusable).model_dump(mode="json")
        validate_scoped_sampling_config(scene, normalized["sampling_method"], normalized["sampling_config"])
        if scene == "running":
            validate_active_running_date_range(normalized.get("date_range"))
    except (ValidationError, ValueError, KeyError) as exc:
        if isinstance(exc, ValidationError) and exc.errors():
            message = str(exc.errors(include_url=False)[0].get("msg") or "任务配置无效")
            message = message.removeprefix("Value error, ")
        else:
            message = str(exc) or "任务配置无效"
        raise TaskEditInvalid(message) from exc
    return {
        "task_name": configuration["task_name"],
        "deadline": configuration["deadline"],
        "date_range": normalized["date_range"],
        "department_filter": normalized["department_filter"],
        "record_refs": configuration["record_refs"],
        "sampling_method": normalized["sampling_method"],
        "sampling_config": normalized["sampling_config"],
        "assign_method": normalized["assign_method"],
        "assignee_config": normalized["assignee_config"],
    }


def _changed_fields(task: dict[str, Any], values: dict[str, Any]) -> list[str]:
    return sorted(key for key, value in values.items() if task.get(key) != value)


def replace_draft_configuration(
    task_id: str,
    *,
    actor_id: str,
    is_manager: bool,
    expected_version: int,
    configuration: dict[str, Any],
) -> dict[str, Any]:
    task_id = _task_id(task_id)
    actor_id = _actor_id(actor_id)
    expected_version = _version(expected_version)
    try:
        with _session() as session:
            with session.begin():
                task = _read_task(session, task_id, lock=True)
                if task is None:
                    raise TaskEditNotFound("任务不存在")
                _authorize(task, actor_id, bool(is_manager))
                if task["configuration_version"] != expected_version:
                    raise TaskEditConflict("任务已被修改，请刷新后重试", code="version_conflict")
                if task.get("task_type") != "one_time" or task.get("status") != "draft":
                    raise TaskEditConflict("仅尚未抽样的单次草稿可修改完整规划", code="state_conflict")
                record_count, run_count = _relation_counts(session, task_id)
                if record_count or run_count:
                    raise TaskEditConflict("任务已有关联病历或运行记录，不能修改规划", code="association_conflict")
                if task.get("record_ids"):
                    raise TaskEditConflict("历史单键病例范围不能通过现代编辑入口修改", code="association_conflict")
                values = _validate_configuration(task, configuration)
                changed_fields = _changed_fields(task, values)
                if not changed_fields:
                    raise TaskEditInvalid("任务配置没有变化")
                now = datetime.now(timezone.utc).replace(tzinfo=None)
                changed = session.execute(
                    update(_TASKS)
                    .where(
                        _TASKS.c.id == task_id,
                        _TASKS.c.status == "draft",
                        _TASKS.c.configuration_version == expected_version,
                    )
                    .values(
                        task_name=values["task_name"],
                        deadline=values["deadline"],
                        date_range=json.dumps(values["date_range"], ensure_ascii=False) if values["date_range"] else None,
                        department_filter=json.dumps(values["department_filter"], ensure_ascii=False),
                        record_ids=json.dumps([], ensure_ascii=False),
                        record_refs=values["record_refs"],
                        sampling_method=values["sampling_method"],
                        sampling_config=json.dumps(values["sampling_config"], ensure_ascii=False),
                        assign_method=values["assign_method"],
                        assignee_config=json.dumps(values["assignee_config"], ensure_ascii=False),
                        configuration_version=expected_version + 1,
                        updated_at=now,
                    )
                )
                if changed.rowcount != 1:
                    raise TaskEditConflict("任务状态或版本已变化，请刷新后重试", code="version_conflict")
                refreshed = _read_task(session, task_id, lock=False)
                if refreshed is None or refreshed["configuration_version"] != expected_version + 1:
                    raise TaskEditUnavailable("任务更新结果无法确认")
                refreshed_records, refreshed_runs = _relation_counts(session, task_id)
                if refreshed_records or refreshed_runs:
                    raise TaskEditUnavailable("任务关联在编辑期间发生变化")
                result = _response(refreshed, refreshed_records, refreshed_runs)
                result["changed_fields"] = changed_fields
                return result
    except TaskEditError:
        raise
    except Exception as exc:
        raise TaskEditUnavailable("任务编辑暂不可用") from exc


def update_task_metadata(
    task_id: str,
    *,
    actor_id: str,
    is_manager: bool,
    expected_version: int,
    changes: dict[str, Any],
) -> dict[str, Any]:
    task_id = _task_id(task_id)
    actor_id = _actor_id(actor_id)
    expected_version = _version(expected_version)
    if not isinstance(changes, dict):
        raise TaskEditInvalid("任务元数据变更无效")
    if not changes or set(changes) - set(_METADATA_FIELDS):
        raise TaskEditInvalid("任务元数据变更无效")
    try:
        parsed_request = TaskMetadataUpdateRequest.model_validate({
            "configuration_version": expected_version,
            **changes,
        })
    except ValidationError as exc:
        first = exc.errors(include_url=False)[0] if exc.errors() else {}
        message = str(first.get("msg") or "任务元数据变更无效").removeprefix("Value error, ")
        raise TaskEditInvalid(message) from exc
    changes = parsed_request.model_dump(
        mode="json", exclude={"configuration_version"}, exclude_unset=True,
    )
    try:
        with _session() as session:
            with session.begin():
                task = _read_task(session, task_id, lock=True)
                if task is None:
                    raise TaskEditNotFound("任务不存在")
                _authorize(task, actor_id, bool(is_manager))
                if task["configuration_version"] != expected_version:
                    raise TaskEditConflict("任务已被修改，请刷新后重试", code="version_conflict")
                if task.get("status") not in _METADATA_STATUSES:
                    raise TaskEditConflict("任务当前状态不允许编辑", code="state_conflict")
                changed_fields = _changed_fields(task, changes)
                if not changed_fields:
                    raise TaskEditInvalid("任务元数据没有变化")
                now = datetime.now(timezone.utc).replace(tzinfo=None)
                changed = session.execute(
                    update(_TASKS)
                    .where(
                        _TASKS.c.id == task_id,
                        _TASKS.c.status == task["status"],
                        _TASKS.c.configuration_version == expected_version,
                    )
                    .values(
                        **changes,
                        configuration_version=expected_version + 1,
                        updated_at=now,
                    )
                )
                if changed.rowcount != 1:
                    raise TaskEditConflict("任务状态或版本已变化，请刷新后重试", code="version_conflict")
                refreshed = _read_task(session, task_id, lock=False)
                if refreshed is None or refreshed["configuration_version"] != expected_version + 1:
                    raise TaskEditUnavailable("任务更新结果无法确认")
                record_count, run_count = _relation_counts(session, task_id)
                result = _response(refreshed, record_count, run_count)
                result["changed_fields"] = changed_fields
                return result
    except TaskEditError:
        raise
    except Exception as exc:
        raise TaskEditUnavailable("任务编辑暂不可用") from exc


__all__ = [
    "TaskEditConflict",
    "TaskEditForbidden",
    "TaskEditInvalid",
    "TaskEditNotFound",
    "TaskEditUnavailable",
    "get_task_edit",
    "replace_draft_configuration",
    "update_task_metadata",
]
