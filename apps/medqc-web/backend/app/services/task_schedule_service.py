"""独立定时计划定义与管理状态。

计划冻结一条合格的单次草稿，不修改也不执行源任务；执行服务为每个触发时点
创建全新的单次子任务。
"""

from __future__ import annotations

import json
from datetime import date, datetime, time, timedelta, timezone
from typing import Any
from uuid import uuid4
from zoneinfo import ZoneInfo

from pydantic import TypeAdapter, ValidationError
from sqlalchemy import func, insert, select, update
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from ..database.connection import SessionLocal
from ..database.models.qc import (
    QCTask,
    QCTaskQCRun,
    QCTaskRecord,
    QCTaskSchedule,
    QCTaskScheduleRun,
)
from ..schemas.task_schedules import (
    ScheduleRunStatus,
    ScheduleState,
    TaskScheduleListResponse,
    TaskScheduleResponse,
    TaskScheduleRunListResponse,
    TaskScheduleRunResponse,
    TaskScheduleTimingConfig,
)
from ..schemas.tasks import TaskTemplateConfig
from .qc_rule_sets import get_sichuan_rule_set
from .rule_set_version_service import (
    RuleSetVersionNotFound,
    RuleSetVersionUnavailable,
    SOURCE_BUILTIN,
    STATUS_PUBLISHED,
    _resolve_in_session,
)
from .task_sampling_service import validate_scoped_sampling_config


MAX_PAGE_SIZE = 100
SHANGHAI = ZoneInfo("Asia/Shanghai")
_TIMING_ADAPTER = TypeAdapter(TaskScheduleTimingConfig)
_SCHEDULES = QCTaskSchedule.__table__
_RUNS = QCTaskScheduleRun.__table__
_TASKS = QCTask.__table__
_TASK_RECORDS = QCTaskRecord.__table__
_TASK_QC_RUNS = QCTaskQCRun.__table__


class TaskScheduleError(Exception):
    code = "schedule_error"


class TaskScheduleNotFound(TaskScheduleError, LookupError):
    code = "schedule_not_found"


class TaskScheduleForbidden(TaskScheduleError, PermissionError):
    code = "schedule_forbidden"


class TaskScheduleInvalid(TaskScheduleError, ValueError):
    code = "schedule_invalid"


class TaskScheduleConflict(TaskScheduleError, ValueError):
    def __init__(self, message: str, *, code: str = "state_conflict") -> None:
        super().__init__(message)
        self.code = code


class TaskScheduleUnavailable(TaskScheduleError, RuntimeError):
    code = "schedule_unavailable"


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _utc_naive(value: datetime, *, field: str) -> datetime:
    if not isinstance(value, datetime):
        raise TaskScheduleInvalid(f"{field} 无效")
    if value.tzinfo is None or value.utcoffset() is None:
        return value
    return value.astimezone(timezone.utc).replace(tzinfo=None)


def _actor_id(value: Any) -> str:
    if not isinstance(value, str):
        raise TaskScheduleForbidden("当前用户缺少稳定身份")
    normalized = value.strip()
    if not normalized or len(normalized) > 64:
        raise TaskScheduleForbidden("当前用户缺少稳定身份")
    return normalized


def _request_id(value: Any) -> str:
    if not isinstance(value, str):
        raise TaskScheduleInvalid("Idempotency-Key 无效")
    if not 1 <= len(value) <= 128 or any(not 0x21 <= ord(char) <= 0x7E for char in value):
        raise TaskScheduleInvalid("Idempotency-Key 必须为 1 至 128 个可见 ASCII 字符")
    return value


def _identifier(value: Any, *, field: str, maximum: int = 36) -> str:
    if not isinstance(value, str):
        raise TaskScheduleInvalid(f"{field} 无效")
    normalized = value.strip()
    if not normalized or len(normalized) > maximum:
        raise TaskScheduleInvalid(f"{field} 无效")
    return normalized


def _version(value: Any) -> int:
    if type(value) is not int or value < 1:
        raise TaskScheduleInvalid("version 无效")
    return value


def _pagination(page: Any, page_size: Any) -> tuple[int, int]:
    if type(page) is not int or page < 1:
        raise TaskScheduleInvalid("page 无效")
    if type(page_size) is not int or not 1 <= page_size <= MAX_PAGE_SIZE:
        raise TaskScheduleInvalid(f"page_size 必须为 1 到 {MAX_PAGE_SIZE}")
    return page, page_size


def _parse_timing(value: Any) -> Any:
    try:
        return _TIMING_ADAPTER.validate_python(value)
    except ValidationError as exc:
        first = exc.errors(include_url=False)[0] if exc.errors() else {}
        message = str(first.get("msg") or "定时配置无效").removeprefix("Value error, ")
        raise TaskScheduleInvalid(message) from exc


def _timing_dict(value: Any) -> dict[str, Any]:
    return _parse_timing(value).model_dump(mode="json")


def calculate_next_fire(timing_config: Any, *, after_utc: datetime) -> datetime | None:
    """返回严格晚于 ``after_utc`` 的首个 UTC 无时区触发时间。

    暂停和服务中断期间错过的批次会被跳过，不做追补。
    """

    timing = _parse_timing(timing_config)
    after = _utc_naive(after_utc, field="after_utc")
    if timing.kind == "once":
        candidate = timing.run_at.astimezone(timezone.utc).replace(tzinfo=None)
        return candidate if candidate > after else None

    hour, minute = (int(part) for part in timing.time.split(":"))
    after_local = after.replace(tzinfo=timezone.utc).astimezone(SHANGHAI)
    candidate_date = max(timing.start_date, after_local.date())
    end_date: date | None = timing.end_date
    if end_date is not None and candidate_date > end_date:
        return None

    # 周计划最多检查七天即可找到下次时点；八次覆盖首日已过时点的边界。
    for offset in range(8):
        current_date = candidate_date + timedelta(days=offset)
        if end_date is not None and current_date > end_date:
            return None
        if timing.kind == "weekly" and current_date.isoweekday() not in timing.weekdays:
            continue
        local_candidate = datetime.combine(
            current_date,
            time(hour=hour, minute=minute),
            tzinfo=SHANGHAI,
        )
        utc_candidate = local_candidate.astimezone(timezone.utc).replace(tzinfo=None)
        if utc_candidate > after:
            return utc_candidate
    return None


def _decode_json(raw: Any, *, field: str, expected: type, default: Any) -> Any:
    if raw is None:
        return default
    if isinstance(raw, expected):
        return raw
    if not isinstance(raw, str):
        raise TaskScheduleInvalid(f"源草稿 {field} 已损坏")
    try:
        decoded = json.loads(raw)
    except (TypeError, json.JSONDecodeError) as exc:
        raise TaskScheduleInvalid(f"源草稿 {field} 已损坏") from exc
    if not isinstance(decoded, expected):
        raise TaskScheduleInvalid(f"源草稿 {field} 已损坏")
    return decoded


def _source_task_config(source: Any) -> dict[str, Any]:
    if source.date_range is not None:
        raise TaskScheduleInvalid("定时计划源草稿必须清空固定日期范围")
    if source.deadline is not None:
        raise TaskScheduleInvalid("定时计划源草稿必须清空固定截止时间")
    if source.schedule_config is not None:
        raise TaskScheduleInvalid("定时计划源草稿不能包含旧定时配置")
    record_ids = _decode_json(source.record_ids, field="record_ids", expected=list, default=[])
    record_refs = _decode_json(source.record_refs, field="record_refs", expected=list, default=[])
    if record_ids or record_refs:
        raise TaskScheduleInvalid("定时计划源草稿不能指定固定病例")

    department_filter = _decode_json(
        source.department_filter,
        field="department_filter",
        expected=list,
        default=[],
    )
    sampling_config = _decode_json(
        source.sampling_config,
        field="sampling_config",
        expected=dict,
        default={},
    )
    assignee_config = _decode_json(
        source.assignee_config,
        field="assignee_config",
        expected=dict,
        default={},
    )
    candidate = {
        "scene": source.scene,
        "rule_set_key": source.rule_set_key,
        "date_range": None,
        "department_filter": department_filter,
        "sampling_method": source.sampling_method,
        "sampling_config": sampling_config,
        "assign_method": source.assign_method,
        "assignee_config": assignee_config,
    }
    try:
        normalized = TaskTemplateConfig.model_validate(candidate).model_dump(mode="json")
        validate_scoped_sampling_config(
            normalized["scene"],
            normalized["sampling_method"],
            normalized["sampling_config"],
        )
    except (ValidationError, ValueError) as exc:
        raise TaskScheduleInvalid(f"源草稿配置不可用于定时计划：{exc}") from exc
    return {
        "date_range": None,
        "department_filter": normalized["department_filter"],
        "sampling_method": normalized["sampling_method"],
        "sampling_config": normalized["sampling_config"],
        "assign_method": normalized["assign_method"],
        "assignee_config": normalized["assignee_config"],
    }


def _authorize_owner(owner_id: Any, actor_id: str, is_manager: bool) -> str:
    if not isinstance(owner_id, str) or not owner_id.strip() or len(owner_id.strip()) > 64:
        raise TaskScheduleForbidden("计划缺少可核实的所有者")
    owner = owner_id.strip()
    if not is_manager and owner != actor_id:
        raise TaskScheduleForbidden("仅计划所有者或管理员可操作")
    return owner


def _json_dump(value: dict[str, Any]) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _json_load(raw: Any, *, field: str) -> dict[str, Any]:
    if not isinstance(raw, str):
        raise TaskScheduleUnavailable(f"计划 {field} 无法确认")
    try:
        decoded = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise TaskScheduleUnavailable(f"计划 {field} 无法确认") from exc
    if not isinstance(decoded, dict):
        raise TaskScheduleUnavailable(f"计划 {field} 无法确认")
    return decoded


def _aware_utc(value: Any) -> Any:
    if not isinstance(value, datetime):
        return value
    if value.tzinfo is None or value.utcoffset() is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _schedule_response(row: Any) -> dict[str, Any]:
    data = dict(row._mapping if hasattr(row, "_mapping") else row)
    payload = {
        "id": data.get("id"),
        "source_task_id": data.get("source_task_id"),
        "owner_id": data.get("owner_id"),
        "name": data.get("name"),
        "scene": data.get("scene"),
        "rule_set_key": data.get("rule_set_key"),
        "rule_set_version": data.get("rule_set_version"),
        "task_config": _json_load(data.get("task_config_json"), field="任务配置"),
        "timing_config": _json_load(data.get("timing_config_json"), field="时间配置"),
        "state": data.get("state"),
        "next_fire_at": _aware_utc(data.get("next_fire_at")),
        "last_fire_at": _aware_utc(data.get("last_fire_at")),
        "version": data.get("version"),
        "created_at": _aware_utc(data.get("created_at")),
        "updated_at": _aware_utc(data.get("updated_at")),
    }
    try:
        return TaskScheduleResponse.model_validate(payload).model_dump(mode="json")
    except ValidationError as exc:
        raise TaskScheduleUnavailable("计划响应合同无法确认") from exc


def _run_response(row: Any) -> dict[str, Any]:
    data = dict(row._mapping if hasattr(row, "_mapping") else row)
    payload = {field: data.get(field) for field in TaskScheduleRunResponse.model_fields}
    for field in (
        "scheduled_fire_at",
        "heartbeat_at",
        "started_at",
        "finished_at",
        "created_at",
        "updated_at",
    ):
        payload[field] = _aware_utc(payload.get(field))
    try:
        return TaskScheduleRunResponse.model_validate(payload).model_dump(mode="json")
    except ValidationError as exc:
        raise TaskScheduleUnavailable("计划运行响应合同无法确认") from exc


def _session_factory() -> Any:
    if SessionLocal is None:
        raise TaskScheduleUnavailable("定时计划存储不可用")
    return SessionLocal


def _read_schedule(session: Any, schedule_id: str, *, lock: bool) -> Any:
    statement = select(_SCHEDULES).where(_SCHEDULES.c.id == schedule_id)
    if lock:
        statement = statement.with_for_update()
    return session.execute(statement).first()


def _read_creation_request(session: Any, actor_id: str, request_id: str) -> Any:
    return session.execute(
        select(_SCHEDULES).where(
            _SCHEDULES.c.creation_actor_id == actor_id,
            _SCHEDULES.c.creation_request_id == request_id,
        )
    ).first()


def _creation_replay(
    row: Any,
    *,
    actor_id: str,
    is_manager: bool,
    source_task_id: str,
    source_configuration_version: int,
    timing_json: str,
) -> dict[str, Any]:
    existing = row._mapping
    _authorize_owner(existing.get("owner_id"), actor_id, is_manager)
    if (
        existing.get("source_task_id") != source_task_id
        or existing.get("source_configuration_version") != source_configuration_version
        or existing.get("timing_config_json") != timing_json
    ):
        raise TaskScheduleConflict(
            "Idempotency-Key 已用于其他定时计划请求",
            code="request_conflict",
        )
    return _schedule_response(row)


def create_task_schedule(
    *,
    actor_id: str,
    is_manager: bool,
    request_id: str,
    source_task_id: str,
    source_configuration_version: int,
    timing_config: Any,
) -> dict[str, Any]:
    actor = _actor_id(actor_id)
    request = _request_id(request_id)
    source_id = _identifier(source_task_id, field="source_task_id")
    expected_version = _version(source_configuration_version)
    timing = _timing_dict(timing_config)
    timing_json = _json_dump(timing)
    factory = _session_factory()
    try:
        with factory() as session:
            existing = _read_creation_request(session, actor, request)
            if existing is not None:
                return _creation_replay(
                    existing,
                    actor_id=actor,
                    is_manager=bool(is_manager),
                    source_task_id=source_id,
                    source_configuration_version=expected_version,
                    timing_json=timing_json,
                )
    except TaskScheduleError:
        raise
    except SQLAlchemyError as exc:
        raise TaskScheduleUnavailable("定时计划幂等请求读取失败") from exc

    now = _now()
    next_fire = calculate_next_fire(timing, after_utc=now)
    if next_fire is None:
        raise TaskScheduleInvalid("定时计划没有未来执行时间")
    schedule_id = str(uuid4())
    try:
        with factory() as session:
            with session.begin():
                source = session.execute(
                    select(_TASKS).where(_TASKS.c.id == source_id).with_for_update()
                ).first()
                if source is None:
                    raise TaskScheduleNotFound("源草稿不存在")
                existing = _read_creation_request(session, actor, request)
                if existing is not None:
                    return _creation_replay(
                        existing,
                        actor_id=actor,
                        is_manager=bool(is_manager),
                        source_task_id=source_id,
                        source_configuration_version=expected_version,
                        timing_json=timing_json,
                    )
                source = source._mapping
                owner = _authorize_owner(source.get("creator_id"), actor, bool(is_manager))
                if source.get("task_type") != "one_time" or source.get("status") != "draft":
                    raise TaskScheduleInvalid("源任务必须是未启动的单次草稿")
                if source.get("configuration_version") != expected_version:
                    raise TaskScheduleConflict("源草稿已被修改，请刷新后重试", code="version_conflict")
                record_count = session.execute(
                    select(func.count()).select_from(_TASK_RECORDS).where(
                        _TASK_RECORDS.c.task_id == source_id
                    )
                ).scalar_one()
                run_count = session.execute(
                    select(func.count()).select_from(_TASK_QC_RUNS).where(
                        _TASK_QC_RUNS.c.task_id == source_id
                    )
                ).scalar_one()
                if int(record_count) or int(run_count):
                    raise TaskScheduleConflict(
                        "源草稿已有病例或执行记录，不能创建定时计划",
                        code="state_conflict",
                    )
                if source.get("scene") != "running":
                    raise TaskScheduleInvalid("定时计划当前仅支持运行病历")
                rule_key = source.get("rule_set_key")
                rule_version = source.get("rule_set_version")
                rule_set = get_sichuan_rule_set(rule_key)
                if rule_set is None or rule_set.scope != "running":
                    raise TaskScheduleInvalid("源草稿冻结的规则集版本不存在或不可用")
                try:
                    resolution = _resolve_in_session(session, rule_set, rule_version)
                except RuleSetVersionNotFound as exc:
                    raise TaskScheduleInvalid("源草稿冻结的规则集版本不存在或不可用") from exc
                except RuleSetVersionUnavailable as exc:
                    raise TaskScheduleUnavailable("规则集版本暂不可用") from exc
                if resolution.get("source") not in {SOURCE_BUILTIN, STATUS_PUBLISHED}:
                    raise TaskScheduleInvalid("源草稿冻结的规则集版本已停用")
                name = source.get("task_name")
                if not isinstance(name, str) or not name.strip() or len(name.strip()) > 200:
                    raise TaskScheduleInvalid("源草稿名称无效")
                task_config = _source_task_config(source)
                session.execute(insert(_SCHEDULES).values(
                    id=schedule_id,
                    source_task_id=source_id,
                    source_configuration_version=expected_version,
                    owner_id=owner,
                    creation_actor_id=actor,
                    creation_request_id=request,
                    name=name.strip(),
                    scene="running",
                    rule_set_key=rule_set.key,
                    rule_set_version=resolution["version"],
                    task_config_json=_json_dump(task_config),
                    timing_config_json=timing_json,
                    state="active",
                    next_fire_at=next_fire,
                    last_fire_at=None,
                    version=1,
                    created_at=now,
                    updated_at=now,
                ))
                row = _read_schedule(session, schedule_id, lock=False)
                if row is None:
                    raise TaskScheduleUnavailable("定时计划保存结果无法确认")
                result = _schedule_response(row)
    except TaskScheduleError:
        raise
    except IntegrityError as exc:
        try:
            with factory() as session:
                existing = _read_creation_request(session, actor, request)
                if existing is not None:
                    return _creation_replay(
                        existing,
                        actor_id=actor,
                        is_manager=bool(is_manager),
                        source_task_id=source_id,
                        source_configuration_version=expected_version,
                        timing_json=timing_json,
                    )
        except TaskScheduleError:
            raise
        except SQLAlchemyError as read_exc:
            raise TaskScheduleUnavailable("定时计划幂等结果读取失败") from read_exc
        raise TaskScheduleConflict("定时计划创建冲突") from exc
    except SQLAlchemyError as exc:
        raise TaskScheduleUnavailable("定时计划创建失败") from exc
    return result


def get_task_schedule(
    schedule_id: str,
    *,
    actor_id: str,
    is_manager: bool = False,
) -> dict[str, Any]:
    schedule_id = _identifier(schedule_id, field="schedule_id")
    actor = _actor_id(actor_id)
    factory = _session_factory()
    try:
        with factory() as session:
            row = _read_schedule(session, schedule_id, lock=False)
            if row is None:
                raise TaskScheduleNotFound("定时计划不存在")
            _authorize_owner(row._mapping.get("owner_id"), actor, bool(is_manager))
            return _schedule_response(row)
    except TaskScheduleError:
        raise
    except SQLAlchemyError as exc:
        raise TaskScheduleUnavailable("定时计划读取失败") from exc


def list_task_schedules(
    *,
    actor_id: str,
    is_manager: bool = False,
    state: ScheduleState | None = None,
    page: int = 1,
    page_size: int = 20,
) -> dict[str, Any]:
    actor = _actor_id(actor_id)
    page, page_size = _pagination(page, page_size)
    if state is not None and state not in {"active", "paused", "ended", "cancelled"}:
        raise TaskScheduleInvalid("state 无效")
    predicates = []
    if not is_manager:
        predicates.append(_SCHEDULES.c.owner_id == actor)
    if state is not None:
        predicates.append(_SCHEDULES.c.state == state)
    factory = _session_factory()
    try:
        with factory() as session:
            total = int(session.execute(
                select(func.count()).select_from(_SCHEDULES).where(*predicates)
            ).scalar_one())
            rows = session.execute(
                select(_SCHEDULES)
                .where(*predicates)
                .order_by(_SCHEDULES.c.created_at.desc(), _SCHEDULES.c.id.desc())
                .offset((page - 1) * page_size)
                .limit(page_size)
            ).all()
            payload = {
                "items": [_schedule_response(row) for row in rows],
                "total": total,
                "page": page,
                "page_size": page_size,
            }
            return TaskScheduleListResponse.model_validate(payload).model_dump(mode="json")
    except TaskScheduleError:
        raise
    except (SQLAlchemyError, ValidationError) as exc:
        raise TaskScheduleUnavailable("定时计划列表读取失败") from exc


def _transition(
    schedule_id: str,
    *,
    actor_id: str,
    is_manager: bool,
    expected_version: int,
    action: str,
    now_utc: datetime | None = None,
) -> dict[str, Any]:
    schedule_id = _identifier(schedule_id, field="schedule_id")
    actor = _actor_id(actor_id)
    version = _version(expected_version)
    now = _now() if now_utc is None else _utc_naive(now_utc, field="now_utc")
    factory = _session_factory()
    try:
        with factory() as session:
            with session.begin():
                row = _read_schedule(session, schedule_id, lock=True)
                if row is None:
                    raise TaskScheduleNotFound("定时计划不存在")
                current = row._mapping
                _authorize_owner(current.get("owner_id"), actor, bool(is_manager))
                if current.get("version") != version:
                    raise TaskScheduleConflict("定时计划已被修改，请刷新后重试", code="version_conflict")
                state = current.get("state")
                values: dict[str, Any]
                if action == "pause":
                    if state != "active":
                        raise TaskScheduleConflict("只有启用中的计划可以暂停")
                    values = {"state": "paused"}
                elif action == "resume":
                    if state != "paused":
                        raise TaskScheduleConflict("只有已暂停的计划可以恢复")
                    timing = _json_load(current.get("timing_config_json"), field="时间配置")
                    next_fire = calculate_next_fire(timing, after_utc=now)
                    values = {
                        "state": "active" if next_fire is not None else "ended",
                        "next_fire_at": next_fire,
                    }
                elif action == "cancel":
                    if state not in {"active", "paused"}:
                        raise TaskScheduleConflict("当前计划状态不能取消")
                    values = {"state": "cancelled", "next_fire_at": None}
                else:
                    raise TaskScheduleInvalid("计划操作无效")
                changed = session.execute(
                    update(_SCHEDULES)
                    .where(
                        _SCHEDULES.c.id == schedule_id,
                        _SCHEDULES.c.version == version,
                        _SCHEDULES.c.state == state,
                    )
                    .values(**values, version=version + 1, updated_at=now)
                )
                if changed.rowcount != 1:
                    raise TaskScheduleConflict("定时计划已被修改，请刷新后重试", code="version_conflict")
                saved = _read_schedule(session, schedule_id, lock=False)
                if saved is None:
                    raise TaskScheduleUnavailable("定时计划保存结果无法确认")
                result = _schedule_response(saved)
    except TaskScheduleError:
        raise
    except SQLAlchemyError as exc:
        raise TaskScheduleUnavailable("定时计划状态保存失败") from exc
    return result


def pause_task_schedule(
    schedule_id: str,
    *,
    actor_id: str,
    is_manager: bool,
    expected_version: int,
) -> dict[str, Any]:
    return _transition(
        schedule_id,
        actor_id=actor_id,
        is_manager=is_manager,
        expected_version=expected_version,
        action="pause",
    )


def resume_task_schedule(
    schedule_id: str,
    *,
    actor_id: str,
    is_manager: bool,
    expected_version: int,
    now_utc: datetime | None = None,
) -> dict[str, Any]:
    return _transition(
        schedule_id,
        actor_id=actor_id,
        is_manager=is_manager,
        expected_version=expected_version,
        action="resume",
        now_utc=now_utc,
    )


def cancel_task_schedule(
    schedule_id: str,
    *,
    actor_id: str,
    is_manager: bool,
    expected_version: int,
) -> dict[str, Any]:
    return _transition(
        schedule_id,
        actor_id=actor_id,
        is_manager=is_manager,
        expected_version=expected_version,
        action="cancel",
    )


def list_task_schedule_runs(
    schedule_id: str,
    *,
    actor_id: str,
    is_manager: bool = False,
    status: ScheduleRunStatus | None = None,
    page: int = 1,
    page_size: int = 20,
) -> dict[str, Any]:
    schedule_id = _identifier(schedule_id, field="schedule_id")
    actor = _actor_id(actor_id)
    page, page_size = _pagination(page, page_size)
    if status is not None and status not in {"queued", "running", "succeeded", "failed", "cancelled"}:
        raise TaskScheduleInvalid("status 无效")
    factory = _session_factory()
    try:
        with factory() as session:
            schedule = _read_schedule(session, schedule_id, lock=False)
            if schedule is None:
                raise TaskScheduleNotFound("定时计划不存在")
            _authorize_owner(schedule._mapping.get("owner_id"), actor, bool(is_manager))
            predicates = [_RUNS.c.schedule_id == schedule_id]
            if status is not None:
                predicates.append(_RUNS.c.status == status)
            total = int(session.execute(
                select(func.count()).select_from(_RUNS).where(*predicates)
            ).scalar_one())
            rows = session.execute(
                select(_RUNS)
                .where(*predicates)
                .order_by(_RUNS.c.created_at.desc(), _RUNS.c.id.desc())
                .offset((page - 1) * page_size)
                .limit(page_size)
            ).all()
            payload = {
                "items": [_run_response(row) for row in rows],
                "total": total,
                "page": page,
                "page_size": page_size,
            }
            return TaskScheduleRunListResponse.model_validate(payload).model_dump(mode="json")
    except TaskScheduleError:
        raise
    except (SQLAlchemyError, ValidationError) as exc:
        raise TaskScheduleUnavailable("定时计划运行历史读取失败") from exc
