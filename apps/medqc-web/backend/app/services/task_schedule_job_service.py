"""定时任务的持久领取、子任务生成与真实抽样执行。"""

from __future__ import annotations

import asyncio
import inspect
import json
import logging
import threading
import uuid
from datetime import date, datetime, timedelta, timezone
from typing import Any, Callable
from zoneinfo import ZoneInfo

from sqlalchemy import DateTime, Integer, String, column, insert, select, table, update

from ..database.connection import SessionLocal
from ..schemas.task_schedules import TaskScheduleRunResponse
from .detached_task_runner import submit_detached_task
from .qc_rule_sets import get_sichuan_rule_set
from .rule_set_version_service import (
    RuleSetVersionNotFound,
    RuleSetVersionUnavailable,
    resolve_rule_set_version,
)
from .task_sampling_persistence import save_task_sample
from .task_sampling_service import TaskSamplingService


logger = logging.getLogger(__name__)

_LEASE_SECONDS = 300
_HEARTBEAT_SECONDS = 30
_DEFAULT_TICK_LIMIT = 50
_HOSPITAL_TZ = ZoneInfo("Asia/Shanghai")
_DISPATCH_LOCK = threading.Lock()
_INFLIGHT_RUN_IDS: set[str] = set()
_TASK_CONFIG_FIELDS = frozenset({
    "date_range",
    "department_filter",
    "sampling_method",
    "sampling_config",
    "assign_method",
    "assignee_config",
})

_SCHEDULES = table(
    "qc_task_schedules",
    column("id", String),
    column("source_task_id", String),
    column("owner_id", String),
    column("name", String),
    column("scene", String),
    column("rule_set_key", String),
    column("rule_set_version", String),
    column("task_config_json", String),
    column("timing_config_json", String),
    column("state", String),
    column("next_fire_at", DateTime),
    column("last_fire_at", DateTime),
    column("version", Integer),
    column("created_at", DateTime),
    column("updated_at", DateTime),
)
_RUNS = table(
    "qc_task_schedule_runs",
    column("id", String),
    column("schedule_id", String),
    column("trigger_type", String),
    column("scheduled_fire_at", DateTime),
    column("idempotency_key", String),
    column("status", String),
    column("generated_task_id", String),
    column("async_job_id", String),
    column("attempt_count", Integer),
    column("lease_owner", String),
    column("heartbeat_at", DateTime),
    column("started_at", DateTime),
    column("finished_at", DateTime),
    column("error_code", String),
    column("error_message", String),
    column("created_at", DateTime),
    column("updated_at", DateTime),
)
_TASKS = table(
    "qc_tasks",
    column("id", String),
    column("task_number", String),
    column("task_name", String),
    column("task_type", String),
    column("scene", String),
    column("rule_set_key", String),
    column("rule_set_version", String),
    column("schedule_config", String),
    column("date_range", String),
    column("department_filter", String),
    column("record_ids", String),
    column("record_refs"),
    column("sampling_method", String),
    column("sampling_config", String),
    column("assign_method", String),
    column("assignee_config", String),
    column("status", String),
    column("configuration_version", Integer),
    column("progress"),
    column("total_records", Integer),
    column("completed_records", Integer),
    column("attempt_count", Integer),
    column("creator_id", String),
    column("creator_name", String),
    column("deadline", String),
    column("created_at", DateTime),
    column("updated_at", DateTime),
)


class TaskScheduleJobError(Exception):
    code = "task_schedule_unavailable"


class TaskScheduleJobNotFound(TaskScheduleJobError, LookupError):
    code = "task_schedule_not_found"


class TaskScheduleJobForbidden(TaskScheduleJobError, PermissionError):
    code = "task_schedule_forbidden"


class TaskScheduleJobConflict(TaskScheduleJobError, ValueError):
    def __init__(self, message: str, *, code: str = "state_conflict") -> None:
        super().__init__(message)
        self.code = code


class TaskScheduleJobInvalid(TaskScheduleJobError, ValueError):
    code = "task_schedule_invalid"


class TaskScheduleJobUnavailable(TaskScheduleJobError, RuntimeError):
    code = "task_schedule_unavailable"


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _utc_naive(value: datetime | None, *, field: str) -> datetime:
    if not isinstance(value, datetime):
        raise TaskScheduleJobInvalid(f"{field} 无效")
    if value.tzinfo is not None:
        return value.astimezone(timezone.utc).replace(tzinfo=None)
    return value


def _clean_id(value: Any, *, field: str, maximum: int = 36) -> str:
    if not isinstance(value, str) or not value.strip() or len(value.strip()) > maximum:
        raise TaskScheduleJobInvalid(f"{field} 无效")
    return value.strip()


def _actor_id(value: Any) -> str:
    if not isinstance(value, str) or not value.strip() or len(value.strip()) > 64:
        raise TaskScheduleJobForbidden("当前用户缺少有效身份")
    return value.strip()


def _request_id(value: Any) -> str:
    request_id = _clean_id(value, field="Idempotency-Key", maximum=128)
    if any(ord(char) < 33 or ord(char) > 126 for char in request_id):
        raise TaskScheduleJobInvalid("Idempotency-Key 必须是可见 ASCII 字符")
    return request_id


def _factory(session_factory: Any = None) -> Any:
    factory = session_factory or SessionLocal
    if factory is None:
        raise TaskScheduleJobUnavailable("定时任务数据库不可用")
    return factory


def _decode_object(value: Any, *, field: str) -> dict[str, Any]:
    try:
        decoded = json.loads(value) if isinstance(value, str) else value
    except (TypeError, ValueError) as exc:
        raise TaskScheduleJobConflict(f"{field} 已损坏", code="run_conflict") from exc
    if not isinstance(decoded, dict):
        raise TaskScheduleJobConflict(f"{field} 已损坏", code="run_conflict")
    return decoded


def _task_config(schedule: dict[str, Any]) -> dict[str, Any]:
    config = _decode_object(schedule.get("task_config_json"), field="任务快照")
    if set(config) != _TASK_CONFIG_FIELDS:
        raise TaskScheduleJobConflict("任务快照字段不完整", code="run_conflict")
    scene = schedule.get("scene")
    sampling_config = config.get("sampling_config")
    expected_scope = {"running": "active", "final": "discharged"}.get(scene)
    if expected_scope is None:
        raise TaskScheduleJobConflict("定时任务场景不可用", code="state_conflict")
    if not isinstance(sampling_config, dict) or sampling_config.get("case_scope") != expected_scope:
        raise TaskScheduleJobConflict("定时任务病例范围与场景不匹配", code="run_conflict")
    if config.get("date_range") is not None:
        raise TaskScheduleJobConflict("定时任务暂不支持固定日期范围", code="run_conflict")
    timing = _decode_object(schedule.get("timing_config_json"), field="时间配置")
    if scene == "final" and timing.get("kind") not in {"daily", "weekly", "monthly"}:
        raise TaskScheduleJobConflict("终末定时抽样周期不可用", code="run_conflict")
    return config


def _final_discharge_range(schedule: dict[str, Any], fire_at: datetime) -> dict[str, str] | None:
    """把上一完整周期的左闭右开窗口映射为现有日期闭区间合同。"""
    if schedule.get("scene") != "final":
        return None
    timing = _decode_object(schedule.get("timing_config_json"), field="时间配置")
    kind = timing.get("kind")
    local_day = _utc_naive(fire_at, field="scheduled_fire_at").replace(
        tzinfo=timezone.utc,
    ).astimezone(_HOSPITAL_TZ).date()
    if kind == "daily":
        exclusive_end = local_day
        start = exclusive_end - timedelta(days=1)
    elif kind == "weekly":
        exclusive_end = local_day - timedelta(days=local_day.isoweekday() - 1)
        start = exclusive_end - timedelta(days=7)
    elif kind == "monthly":
        exclusive_end = local_day.replace(day=1)
        previous_month_end = exclusive_end - timedelta(days=1)
        start = date(previous_month_end.year, previous_month_end.month, 1)
    else:
        raise TaskScheduleJobConflict("终末定时抽样周期不可用", code="run_conflict")
    return {
        "start": start.isoformat(),
        "end": (exclusive_end - timedelta(days=1)).isoformat(),
    }


def _authorize(schedule: dict[str, Any], actor_id: str, is_manager: bool) -> None:
    owner_id = schedule.get("owner_id")
    if not isinstance(owner_id, str) or not owner_id.strip():
        raise TaskScheduleJobForbidden("计划缺少可核实的创建人")
    if not is_manager and owner_id != actor_id:
        raise TaskScheduleJobForbidden("仅计划创建人或管理员可执行")


def _iso(value: Any) -> Any:
    if isinstance(value, datetime):
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
    return value


def _run_view(run: dict[str, Any]) -> dict[str, Any]:
    data = {
        key: _iso(run.get(key))
        for key in (
            "id",
            "schedule_id",
            "trigger_type",
            "scheduled_fire_at",
            "idempotency_key",
            "status",
            "generated_task_id",
            "async_job_id",
            "attempt_count",
            "heartbeat_at",
            "started_at",
            "finished_at",
            "error_code",
            "error_message",
            "created_at",
            "updated_at",
        )
    }
    return TaskScheduleRunResponse.model_validate(data).model_dump(mode="json")


def _stable_id(namespace: str, identity: str) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"medqc:{namespace}:{identity}"))


def _run_values(
    *, schedule_id: str, trigger_type: str, fire_at: datetime, idempotency_key: str,
    now: datetime,
) -> dict[str, Any]:
    return {
        "id": _stable_id("task-schedule-run", idempotency_key),
        "schedule_id": schedule_id,
        "trigger_type": trigger_type,
        "scheduled_fire_at": fire_at,
        "idempotency_key": idempotency_key,
        "status": "queued",
        "generated_task_id": None,
        "async_job_id": None,
        "attempt_count": 0,
        "lease_owner": None,
        "heartbeat_at": None,
        "started_at": None,
        "finished_at": None,
        "error_code": None,
        "error_message": None,
        "created_at": now,
        "updated_at": now,
    }


def _dispatch(run_id: str, dispatch: Callable[[str], Any] | None) -> bool:
    if dispatch is not None:
        dispatch(run_id)
        return True

    with _DISPATCH_LOCK:
        if run_id in _INFLIGHT_RUN_IDS:
            return False
        _INFLIGHT_RUN_IDS.add(run_id)
    try:
        future = submit_detached_task("task_schedule_run", run_schedule_job, run_id)
    except Exception:
        with _DISPATCH_LOCK:
            _INFLIGHT_RUN_IDS.discard(run_id)
        raise

    def _release(_done: Any) -> None:
        with _DISPATCH_LOCK:
            _INFLIGHT_RUN_IDS.discard(run_id)

    future.add_done_callback(_release)
    return True


def enqueue_manual_schedule_run(
    *, schedule_id: str, request_id: str, actor_id: str, is_manager: bool = False,
    dispatch: Callable[[str], Any] | None = None, session_factory: Any = None,
) -> dict[str, Any]:
    """创建或重放同一 Idempotency-Key 的手动运行回执。"""
    schedule_id = _clean_id(schedule_id, field="schedule_id")
    request_id = _request_id(request_id)
    actor_id = _actor_id(actor_id)
    factory = _factory(session_factory)
    idempotency_key = f"qc_task_schedule_manual:{schedule_id}:{request_id}"
    if len(idempotency_key) > 200:
        raise TaskScheduleJobInvalid("Idempotency-Key 过长")
    with factory() as session:
        with session.begin():
            schedule_row = session.execute(
                select(_SCHEDULES).where(_SCHEDULES.c.id == schedule_id).with_for_update()
            ).mappings().first()
            if schedule_row is None:
                raise TaskScheduleJobNotFound("定时计划不存在")
            schedule = dict(schedule_row)
            _authorize(schedule, actor_id, bool(is_manager))
            existing = session.execute(
                select(_RUNS).where(_RUNS.c.idempotency_key == idempotency_key)
            ).mappings().first()
            if existing is None:
                if schedule.get("state") not in {"active", "paused"}:
                    raise TaskScheduleJobConflict("当前计划状态不允许立即运行")
                _task_config(schedule)
                now = _now()
                values = _run_values(
                    schedule_id=schedule_id,
                    trigger_type="manual",
                    fire_at=now,
                    idempotency_key=idempotency_key,
                    now=now,
                )
                session.execute(insert(_RUNS).values(**values))
                run = values
            else:
                run = dict(existing)
                if run.get("schedule_id") != schedule_id or run.get("trigger_type") != "manual":
                    raise TaskScheduleJobConflict("幂等运行身份冲突", code="run_conflict")
            public_run = _run_view(run)
    if run["status"] == "queued" and schedule.get("state") != "cancelled":
        try:
            _dispatch(str(run["id"]), dispatch)
        except Exception as exc:
            raise TaskScheduleJobUnavailable("运行已入队但后台派发失败，请使用相同请求键重试") from exc
    return public_run


def retry_schedule_run(
    *, run_id: str, actor_id: str, is_manager: bool = False,
    dispatch: Callable[[str], Any] | None = None, session_factory: Any = None,
) -> dict[str, Any]:
    """把失败回执重新排队；复用原 run 和原 child。"""
    run_id = _clean_id(run_id, field="run_id")
    actor_id = _actor_id(actor_id)
    factory = _factory(session_factory)
    with factory() as session:
        with session.begin():
            run_row = session.execute(
                select(_RUNS).where(_RUNS.c.id == run_id).with_for_update()
            ).mappings().first()
            if run_row is None:
                raise TaskScheduleJobNotFound("计划运行不存在")
            run = dict(run_row)
            schedule_row = session.execute(
                select(_SCHEDULES).where(_SCHEDULES.c.id == run["schedule_id"]).with_for_update()
            ).mappings().first()
            if schedule_row is None:
                raise TaskScheduleJobConflict("计划运行缺少所属计划", code="run_conflict")
            schedule = dict(schedule_row)
            _authorize(schedule, actor_id, bool(is_manager))
            if schedule.get("state") == "cancelled":
                raise TaskScheduleJobConflict("已取消计划不能重试运行")
            if run.get("status") != "failed":
                raise TaskScheduleJobConflict("仅失败运行可重试")
            child_id = run.get("generated_task_id")
            if child_id:
                child_status = session.execute(
                    select(_TASKS.c.status).where(_TASKS.c.id == child_id)
                ).scalar_one_or_none()
                if child_status not in {"draft", "sampling"}:
                    raise TaskScheduleJobConflict("运行子任务状态不允许重试", code="run_conflict")
            now = _now()
            changed = session.execute(
                update(_RUNS)
                .where(_RUNS.c.id == run_id, _RUNS.c.status == "failed")
                .values(
                    status="queued",
                    lease_owner=None,
                    heartbeat_at=None,
                    started_at=None,
                    finished_at=None,
                    error_code=None,
                    error_message=None,
                    updated_at=now,
                )
            )
            if changed.rowcount != 1:
                raise TaskScheduleJobConflict("运行状态已变化，请刷新后重试", code="run_conflict")
            run.update({
                "status": "queued",
                "lease_owner": None,
                "heartbeat_at": None,
                "started_at": None,
                "finished_at": None,
                "error_code": None,
                "error_message": None,
                "updated_at": now,
            })
            public_run = _run_view(run)
    try:
        _dispatch(run_id, dispatch)
    except Exception as exc:
        raise TaskScheduleJobUnavailable("运行已重新入队但后台派发失败，请重试") from exc
    return public_run


def tick_due_schedules(
    *, now: datetime | None = None, limit: int = _DEFAULT_TICK_LIMIT,
    dispatch: Callable[[str], Any] | None = None, session_factory: Any = None,
    calculate_next: Callable[..., datetime | None] | None = None,
) -> dict[str, Any]:
    """领取一批到期计划并派发；一次调用不常驻、不补跑所有错过批次。"""
    if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 500:
        raise TaskScheduleJobInvalid("tick limit 无效")
    now = _utc_naive(now or _now(), field="now")
    factory = _factory(session_factory)
    if calculate_next is None:
        from .task_schedule_service import calculate_next_fire

        calculate_next = calculate_next_fire
    created_ids: list[str] = []
    with factory() as session:
        with session.begin():
            due = session.execute(
                select(_SCHEDULES)
                .where(
                    _SCHEDULES.c.state == "active",
                    _SCHEDULES.c.next_fire_at.is_not(None),
                    _SCHEDULES.c.next_fire_at <= now,
                )
                .order_by(_SCHEDULES.c.next_fire_at, _SCHEDULES.c.id)
                .limit(limit)
                .with_for_update(skip_locked=True)
            ).mappings().all()
            for row in due:
                schedule = dict(row)
                fire_at = _utc_naive(schedule.get("next_fire_at"), field="next_fire_at")
                fire_iso = fire_at.replace(tzinfo=timezone.utc).isoformat()
                idem = f"qc_task_schedule:{schedule['id']}:{fire_iso}"
                run_id = _stable_id("task-schedule-run", idem)
                existing = session.execute(
                    select(_RUNS.c.id).where(
                        _RUNS.c.schedule_id == schedule["id"],
                        _RUNS.c.scheduled_fire_at == fire_at,
                    )
                ).scalar_one_or_none()
                if existing is None:
                    session.execute(insert(_RUNS).values(**_run_values(
                        schedule_id=str(schedule["id"]),
                        trigger_type="scheduled",
                        fire_at=fire_at,
                        idempotency_key=idem,
                        now=now,
                    )))
                    created_ids.append(run_id)
                timing = _decode_object(schedule.get("timing_config_json"), field="时间配置")
                next_fire = calculate_next(timing, after_utc=max(now, fire_at))
                if next_fire is not None:
                    next_fire = _utc_naive(next_fire, field="next_fire_at")
                    if next_fire <= now:
                        raise TaskScheduleJobConflict("下次运行时间未向前推进", code="run_conflict")
                session.execute(
                    update(_SCHEDULES)
                    .where(
                        _SCHEDULES.c.id == schedule["id"],
                        _SCHEDULES.c.state == "active",
                        _SCHEDULES.c.next_fire_at == fire_at,
                    )
                    .values(
                        last_fire_at=fire_at,
                        next_fire_at=next_fire,
                        state="active" if next_fire is not None else "ended",
                        version=int(schedule["version"]) + 1,
                        updated_at=now,
                    )
                )
    cutoff = now - timedelta(seconds=_LEASE_SECONDS)
    with factory() as session:
        dispatch_rows = session.execute(
            select(_RUNS.c.id)
            .where(
                (_RUNS.c.status == "queued")
                | (
                    (_RUNS.c.status == "running")
                    & ((_RUNS.c.heartbeat_at.is_(None)) | (_RUNS.c.heartbeat_at <= cutoff))
                )
            )
            .order_by(_RUNS.c.scheduled_fire_at, _RUNS.c.id)
            .limit(limit)
        ).scalars().all()
    dispatched = 0
    for run_id in dict.fromkeys([*created_ids, *(str(item) for item in dispatch_rows)]):
        try:
            if _dispatch(run_id, dispatch):
                dispatched += 1
        except Exception:
            logger.exception("定时任务运行派发失败 run_id=%s", run_id)
    return {
        "as_of": _iso(now),
        "created_run_count": len(created_ids),
        "dispatched_run_count": dispatched,
        "created_run_ids": created_ids,
    }


def _claim_run(factory: Any, run_id: str, lease_token: str, now: datetime) -> dict[str, Any] | None:
    cutoff = now - timedelta(seconds=_LEASE_SECONDS)
    with factory() as session:
        with session.begin():
            run_row = session.execute(
                select(_RUNS).where(_RUNS.c.id == run_id).with_for_update()
            ).mappings().first()
            if run_row is None:
                raise TaskScheduleJobNotFound("计划运行不存在")
            run = dict(run_row)
            if run.get("status") == "running":
                heartbeat = run.get("heartbeat_at") or run.get("started_at")
                if isinstance(heartbeat, datetime) and heartbeat > cutoff:
                    return None
            elif run.get("status") != "queued":
                return None
            schedule_row = session.execute(
                select(_SCHEDULES).where(_SCHEDULES.c.id == run["schedule_id"]).with_for_update()
            ).mappings().first()
            if schedule_row is None:
                raise TaskScheduleJobConflict("计划运行缺少所属计划", code="run_conflict")
            schedule = dict(schedule_row)
            if run.get("status") == "queued" and schedule.get("state") == "cancelled":
                session.execute(
                    update(_RUNS).where(_RUNS.c.id == run_id, _RUNS.c.status == "queued").values(
                        status="cancelled", finished_at=now, updated_at=now,
                    )
                )
                return None
            expected_status = str(run["status"])
            changed = session.execute(
                update(_RUNS)
                .where(_RUNS.c.id == run_id, _RUNS.c.status == expected_status)
                .values(
                    status="running",
                    lease_owner=lease_token,
                    heartbeat_at=now,
                    started_at=now,
                    finished_at=None,
                    error_code=None,
                    error_message=None,
                    attempt_count=int(run.get("attempt_count") or 0) + 1,
                    updated_at=now,
                )
            )
            if changed.rowcount != 1:
                return None
            return {**run, **{
                "status": "running",
                "lease_owner": lease_token,
                "heartbeat_at": now,
                "started_at": now,
                "attempt_count": int(run.get("attempt_count") or 0) + 1,
            }, "schedule": schedule}


def _heartbeat(factory: Any, run_id: str, lease_token: str, stop: threading.Event, lost: threading.Event) -> None:
    while not stop.wait(_HEARTBEAT_SECONDS):
        try:
            now = _now()
            with factory.begin() as session:
                changed = session.execute(
                    update(_RUNS)
                    .where(
                        _RUNS.c.id == run_id,
                        _RUNS.c.status == "running",
                        _RUNS.c.lease_owner == lease_token,
                    )
                    .values(heartbeat_at=now, updated_at=now)
                )
            if changed.rowcount != 1:
                lost.set()
                return
        except Exception:
            logger.exception("定时任务运行心跳失败 run_id=%s", run_id)
            lost.set()
            return


def _renew_lease(factory: Any, run_id: str, lease_token: str) -> bool:
    """在不可逆的抽样持久化前同步续租并验证 fencing token。"""
    try:
        now = _now()
        with factory.begin() as session:
            changed = session.execute(
                update(_RUNS)
                .where(
                    _RUNS.c.id == run_id,
                    _RUNS.c.status == "running",
                    _RUNS.c.lease_owner == lease_token,
                )
                .values(heartbeat_at=now, updated_at=now)
            )
        return changed.rowcount == 1
    except Exception:
        logger.exception("定时任务运行续租失败 run_id=%s", run_id)
        return False


def _guard_claim(session: Any, run_id: str, lease_token: str) -> None:
    """在抽样持久事务内持有 run 行锁，阻止旧 claim 与新 worker 并发写 child。"""
    claimed = session.execute(
        select(_RUNS.c.id)
        .where(
            _RUNS.c.id == run_id,
            _RUNS.c.status == "running",
            _RUNS.c.lease_owner == lease_token,
        )
        .with_for_update()
    ).scalar_one_or_none()
    if claimed is None:
        raise TaskScheduleJobConflict("运行租约已失效", code="run_conflict")


def _child_snapshot(factory: Any, claimed: dict[str, Any], lease_token: str) -> dict[str, Any]:
    schedule = claimed["schedule"]
    run_id = str(claimed["id"])
    child_id = str(claimed.get("generated_task_id") or _stable_id("task-schedule-child", run_id))
    with factory() as session:
        with session.begin():
            locked_run = session.execute(
                select(_RUNS).where(_RUNS.c.id == run_id).with_for_update()
            ).mappings().first()
            if (
                locked_run is None
                or locked_run.get("status") != "running"
                or locked_run.get("lease_owner") != lease_token
            ):
                raise TaskScheduleJobConflict("运行租约已失效", code="run_conflict")
            existing_child_id = locked_run.get("generated_task_id")
            if existing_child_id and existing_child_id != child_id:
                raise TaskScheduleJobConflict("运行子任务身份冲突", code="run_conflict")
            child_row = session.execute(
                select(_TASKS).where(_TASKS.c.id == child_id).with_for_update()
            ).mappings().first()
            if child_row is None:
                if existing_child_id:
                    raise TaskScheduleJobConflict("运行子任务不存在", code="run_conflict")
                config = _task_config(schedule)
                date_range = _final_discharge_range(schedule, claimed["scheduled_fire_at"])
                now = _now()
                fire_local = claimed["scheduled_fire_at"].replace(
                    tzinfo=timezone.utc,
                ).astimezone(_HOSPITAL_TZ)
                name = f"{schedule['name']} {fire_local:%Y-%m-%d %H:%M}"[:200]
                child = {
                    "id": child_id,
                    "task_number": f"SCH-{run_id.replace('-', '')[:32]}",
                    "task_name": name,
                    "task_type": "one_time",
                    "scene": schedule["scene"],
                    "rule_set_key": schedule["rule_set_key"],
                    "rule_set_version": schedule["rule_set_version"],
                    "schedule_config": None,
                    "date_range": (
                        json.dumps(date_range, ensure_ascii=False) if date_range is not None else None
                    ),
                    "department_filter": json.dumps(config["department_filter"], ensure_ascii=False),
                    "record_ids": json.dumps([], ensure_ascii=False),
                    "record_refs": None,
                    "sampling_method": config["sampling_method"],
                    "sampling_config": json.dumps(config["sampling_config"], ensure_ascii=False),
                    "assign_method": config["assign_method"],
                    "assignee_config": json.dumps(config["assignee_config"], ensure_ascii=False),
                    "status": "draft",
                    "configuration_version": 1,
                    "progress": 0,
                    "total_records": 0,
                    "completed_records": 0,
                    "attempt_count": 0,
                    "creator_id": schedule["owner_id"],
                    "creator_name": "",
                    "deadline": None,
                    "created_at": now,
                    "updated_at": now,
                }
                session.execute(insert(_TASKS).values(**child))
                session.execute(
                    update(_RUNS)
                    .where(
                        _RUNS.c.id == run_id,
                        _RUNS.c.status == "running",
                        _RUNS.c.lease_owner == lease_token,
                        _RUNS.c.generated_task_id.is_(None),
                    )
                    .values(generated_task_id=child_id, updated_at=now)
                )
                return child
            child = _decode_child(dict(child_row))
            config = _task_config(schedule)
            date_range = _final_discharge_range(schedule, claimed["scheduled_fire_at"])
            if (
                child.get("task_type") != "one_time"
                or child.get("scene") != schedule.get("scene")
                or child.get("rule_set_key") != schedule.get("rule_set_key")
                or child.get("rule_set_version") != schedule.get("rule_set_version")
                or child.get("creator_id") != schedule.get("owner_id")
                or child.get("deadline") is not None
                or child.get("date_range") != date_range
                or child.get("department_filter") != config.get("department_filter")
                or child.get("record_ids") != []
                or child.get("record_refs") is not None
                or child.get("sampling_method") != config.get("sampling_method")
                or child.get("sampling_config") != config.get("sampling_config")
                or child.get("assign_method") != config.get("assign_method")
                or child.get("assignee_config") != config.get("assignee_config")
            ):
                raise TaskScheduleJobConflict("运行子任务冻结字段已漂移", code="run_conflict")
            if child.get("status") not in {"draft", "sampling"}:
                raise TaskScheduleJobConflict("运行子任务状态不允许继续抽样", code="run_conflict")
            return child


def _decode_child(child: dict[str, Any]) -> dict[str, Any]:
    decoded = dict(child)
    for field, default in (
        ("date_range", None),
        ("department_filter", []),
        ("record_ids", []),
        ("sampling_config", {}),
        ("assignee_config", {}),
    ):
        value = decoded.get(field)
        if value is None:
            decoded[field] = default
        elif isinstance(value, str):
            try:
                decoded[field] = json.loads(value)
            except (TypeError, ValueError) as exc:
                raise TaskScheduleJobConflict("运行子任务配置已损坏", code="run_conflict") from exc
    record_refs = decoded.get("record_refs")
    if isinstance(record_refs, str):
        try:
            decoded["record_refs"] = json.loads(record_refs)
        except (TypeError, ValueError) as exc:
            raise TaskScheduleJobConflict("运行子任务配置已损坏", code="run_conflict") from exc
    return decoded


def _sample_child(
    child: dict[str, Any], *, sample_func: Callable[[dict[str, Any]], Any] | None,
    persist_func: Callable[..., dict[str, Any]], before_persist: Callable[[], bool],
    transaction_guard: Callable[[Any], None],
) -> dict[str, Any]:
    child = _decode_child(child)
    scene = child.get("scene")
    expected_scope = {"running": "active", "final": "discharged"}.get(scene)
    if (
        expected_scope is None
        or (scene == "running" and child.get("date_range") is not None)
        or (scene == "final" and not isinstance(child.get("date_range"), dict))
        or not isinstance(child.get("sampling_config"), dict)
        or child["sampling_config"].get("case_scope") != expected_scope
    ):
        raise TaskScheduleJobConflict("运行子任务配置已漂移", code="run_conflict")
    if child.get("status") == "draft":
        sampler = sample_func or TaskSamplingService().sample
        sampled = sampler(child)
        if inspect.isawaitable(sampled):
            sampled = asyncio.run(sampled)
        if not isinstance(sampled, list) or not sampled:
            raise TaskScheduleJobConflict("本次计划未抽取到病历，可稍后重试", code="empty_sample")
    elif child.get("status") == "sampling":
        sampled = []
    else:
        raise TaskScheduleJobConflict("运行子任务状态不允许抽样", code="run_conflict")
    if not before_persist():
        raise TaskScheduleJobConflict("运行租约已失效", code="run_conflict")
    result = persist_func(
        child,
        sampled,
        actor_id=child["creator_id"],
        transaction_guard=transaction_guard,
    )
    if (
        not isinstance(result, dict)
        or result.get("task_id") != child["id"]
        or isinstance(result.get("sampled_count"), bool)
        or not isinstance(result.get("sampled_count"), int)
        or result["sampled_count"] <= 0
        or not isinstance(result.get("records"), list)
        or result.get("record_id_semantics") != "association_id_not_medical_record_id"
    ):
        raise TaskScheduleJobConflict("抽样持久化结果无法确认", code="run_conflict")
    return result


def _finish_run(
    factory: Any, run_id: str, lease_token: str, *, status: str,
    error_code: str | None = None, error_message: str | None = None,
) -> bool:
    now = _now()
    with factory.begin() as session:
        changed = session.execute(
            update(_RUNS)
            .where(
                _RUNS.c.id == run_id,
                _RUNS.c.status == "running",
                _RUNS.c.lease_owner == lease_token,
            )
            .values(
                status=status,
                lease_owner=None,
                heartbeat_at=now,
                finished_at=now,
                error_code=error_code,
                error_message=error_message,
                updated_at=now,
            )
        )
    return changed.rowcount == 1


def run_schedule_job(
    run_id: str, *, session_factory: Any = None,
    sample_func: Callable[[dict[str, Any]], Any] | None = None,
    persist_func: Callable[..., dict[str, Any]] = save_task_sample,
    resolve_version_func: Callable[[Any, Any], dict[str, Any]] = resolve_rule_set_version,
) -> dict[str, Any] | None:
    """执行一个持久 run；succeeded 仅表示 child 已完成非空抽样持久化。"""
    run_id = _clean_id(run_id, field="run_id")
    factory = _factory(session_factory)
    lease_token = str(uuid.uuid4())
    claimed = _claim_run(factory, run_id, lease_token, _now())
    if claimed is None:
        return None
    stop = threading.Event()
    lost = threading.Event()
    heartbeat = threading.Thread(
        target=_heartbeat,
        args=(factory, run_id, lease_token, stop, lost),
        daemon=True,
    )
    heartbeat.start()
    try:
        if not claimed.get("generated_task_id"):
            schedule = claimed["schedule"]
            scheduled_rule_set = get_sichuan_rule_set(schedule.get("rule_set_key"))
            if scheduled_rule_set is None or scheduled_rule_set.scope != schedule.get("scene"):
                raise TaskScheduleJobConflict("冻结规则集与任务场景不匹配", code="run_conflict")
            resolve_version_func(scheduled_rule_set.key, schedule.get("rule_set_version"))
        child = _child_snapshot(factory, claimed, lease_token)
        child = _decode_child(child)
        rule_set = get_sichuan_rule_set(child.get("rule_set_key"))
        if rule_set is None or rule_set.scope != child.get("scene"):
            raise TaskScheduleJobConflict("冻结规则集与任务场景不匹配", code="run_conflict")
        if claimed.get("generated_task_id"):
            resolve_version_func(rule_set.key, child.get("rule_set_version"))
        if lost.is_set():
            return None
        _sample_child(
            child,
            sample_func=sample_func,
            persist_func=persist_func,
            before_persist=lambda: not lost.is_set()
            and _renew_lease(factory, run_id, lease_token),
            transaction_guard=lambda session: _guard_claim(
                session,
                run_id,
                lease_token,
            ),
        )
        if lost.is_set() or not _finish_run(factory, run_id, lease_token, status="succeeded"):
            return None
    except Exception as exc:
        if isinstance(exc, TaskScheduleJobConflict):
            error_code = exc.code
        elif isinstance(exc, RuleSetVersionNotFound):
            error_code = "rule_set_version_missing"
        elif isinstance(exc, RuleSetVersionUnavailable):
            error_code = "rule_set_version_unavailable"
        else:
            error_code = "schedule_run_failed"
        logger.warning("定时任务运行失败 run_id=%s error_type=%s", run_id, type(exc).__name__)
        _finish_run(
            factory,
            run_id,
            lease_token,
            status="failed",
            error_code=error_code,
            error_message="定时任务抽样失败，请核对后重试",
        )
    finally:
        stop.set()
        heartbeat.join(timeout=1)
    with factory() as session:
        row = session.execute(select(_RUNS).where(_RUNS.c.id == run_id)).mappings().first()
    return _run_view(dict(row)) if row is not None else None


__all__ = [
    "TaskScheduleJobConflict",
    "TaskScheduleJobError",
    "TaskScheduleJobForbidden",
    "TaskScheduleJobInvalid",
    "TaskScheduleJobNotFound",
    "TaskScheduleJobUnavailable",
    "enqueue_manual_schedule_run",
    "retry_schedule_run",
    "run_schedule_job",
    "tick_due_schedules",
]
