"""请求内的安全阶段计时；累计并行/嵌套耗时不等于任务墙钟时间。"""

from __future__ import annotations

import asyncio
from contextlib import contextmanager
from contextvars import ContextVar
from functools import wraps
import inspect
import json
import logging
import math
import re
from threading import Lock
from time import perf_counter


logger = logging.getLogger(__name__)
STAGES = frozenset({
    "record_execution", "bundle_read", "evidence_snapshot", "family_queue",
    "family_execution", "extended_group", "http_wait", "http_request",
    "result_assembly", "result_write", "final_save",
})
_ACTIVE = ContextVar("qc_execution_timing", default=None)
_FAMILY = ContextVar("qc_timing_family", default="")
_UNIT = ContextVar("qc_timing_unit", default="")
_LABEL = re.compile(r"[a-z][a-z0-9_]{0,63}\Z")


class ExecutionTiming:
    def __init__(self):
        self.started = perf_counter()
        self.finished = None
        self._lock = Lock()
        self._metrics = {}
        self._pending_http = 0

    def http_submitted(self):
        with self._lock:
            self._pending_http += 1

    def http_finished(self, _future):
        with self._lock:
            self._pending_http -= 1

    def add(self, stage, seconds, *, failed=False, canceled=False):
        if stage not in STAGES:
            return
        family, unit = _FAMILY.get(), _UNIT.get()
        with self._lock:
            for bucket in ("stages", f"family:{family}" if family else "", f"unit:{unit}" if unit else ""):
                if not bucket:
                    continue
                metric = self._metrics.setdefault(bucket, {}).setdefault(stage, {
                    "count": 0, "total_seconds": 0.0, "max_seconds": 0.0,
                    "failed_count": 0, "canceled_count": 0,
                })
                metric["count"] += 1
                metric["total_seconds"] += max(0.0, seconds)
                metric["max_seconds"] = max(metric["max_seconds"], seconds)
                metric["failed_count"] += int(failed)
                metric["canceled_count"] += int(canceled)

    def snapshot(self, *, complete=False):
        with self._lock:
            pending_http = self._pending_http
            metrics = {
                bucket: {stage: {key: round(value, 6) if isinstance(value, float) else value
                                  for key, value in metric.items()}
                         for stage, metric in stages.items()}
                for bucket, stages in self._metrics.items()
            }
        return {
            "schema_version": "qc_stage_timing_v1",
            "scope": "current_worker_attempt",
            "complete": complete and pending_http == 0,
            "boundary": "worker_return" if complete else "before_final_save",
            "pending_http_calls": pending_http,
            "wall_clock_seconds": round(max(0.0, (self.finished if self.finished is not None else perf_counter()) - self.started), 6),
            "stages": metrics.get("stages", {}),
            "families": {key[7:]: value for key, value in metrics.items() if key.startswith("family:")},
            "units": {key[5:]: value for key, value in metrics.items() if key.startswith("unit:")},
        }


@contextmanager
def timing_scope():
    """每次 worker（含补跑）独立统计，不复用上一轮或并发任务的收集器。"""
    timing = ExecutionTiming()
    token = _ACTIVE.set(timing)
    try:
        yield timing
    finally:
        _ACTIVE.reset(token)


@contextmanager
def timing_labels(*, family=None, unit=None):
    tokens = []
    for variable, value in ((_FAMILY, family), (_UNIT, unit)):
        if value is not None and _LABEL.fullmatch(value):
            tokens.append((variable, variable.set(value)))
    try:
        yield
    finally:
        for variable, token in reversed(tokens):
            variable.reset(token)


@contextmanager
def measure_stage(stage):
    timing = _ACTIVE.get()
    if timing is None:
        yield
        return
    started = perf_counter()
    failed = canceled = False
    try:
        yield
    except BaseException as error:
        canceled = isinstance(error, asyncio.CancelledError)
        failed = not canceled
        raise
    finally:
        timing.add(stage, perf_counter() - started, failed=failed, canceled=canceled)


def timed(stage):
    def decorate(function):
        if inspect.iscoroutinefunction(function):
            @wraps(function)
            async def async_call(*args, **kwargs):
                with measure_stage(stage):
                    return await function(*args, **kwargs)
            return async_call

        @wraps(function)
        def sync_call(*args, **kwargs):
            with measure_stage(stage):
                return function(*args, **kwargs)
        return sync_call
    return decorate


def current_timing_snapshot():
    timing = _ACTIVE.get()
    return timing.snapshot() if timing is not None else None


def finish_current_timing():
    """在递归自动补跑及其等待之前封住本轮墙钟，不将下一轮算入本轮。"""
    timing = _ACTIVE.get()
    if timing is not None and timing.finished is None:
        timing.finished = perf_counter()


def record_stage_duration(stage, seconds):
    timing = _ACTIVE.get()
    if timing is not None:
        timing.add(stage, seconds)


def track_http_future(future):
    timing = _ACTIVE.get()
    if timing is not None:
        timing.http_submitted()
        future.add_done_callback(timing.http_finished)


def observe_worker_timing(function):
    @wraps(function)
    async def run(*args, **kwargs):
        with timing_scope() as timing:
            try:
                return await function(*args, **kwargs)
            finally:
                # 最后提交本身只能返回后计时，不能预写为0或为计时另发一次数据库更新。
                try:
                    snapshot = timing.snapshot(complete=True)
                    job_id = kwargs.get("job_id", args[0] if args else "")
                    if isinstance(job_id, str) and re.fullmatch(r"[0-9a-f-]{36}", job_id):
                        snapshot["job_id"] = job_id
                    logger.info("qc_stage_timing %s", json.dumps(snapshot, separators=(",", ":")))
                except Exception:
                    # 观测旁路故障不能改变既有结果、异常或取消语义。
                    pass
    return run


def project_stage_timing(raw):
    """公开读取只搬运明确安全的阶段指标；不透传任意 trace/病例标识。"""
    if not isinstance(raw, dict) or raw.get("schema_version") != "qc_stage_timing_v1":
        return None

    def metrics(value):
        safe = {}
        for stage, metric in (value.items() if isinstance(value, dict) else ()):
            if stage not in STAGES or not isinstance(metric, dict):
                continue
            safe[stage] = {
                key: number for key, number in metric.items()
                if key in {"count", "total_seconds", "max_seconds", "failed_count", "canceled_count"}
                and isinstance(number, (int, float)) and not isinstance(number, bool)
                and math.isfinite(number) and number >= 0
            }
        return safe

    wall = raw.get("wall_clock_seconds")
    if not isinstance(wall, (int, float)) or isinstance(wall, bool) or not math.isfinite(wall) or wall < 0:
        return None
    return {
        "schema_version": "qc_stage_timing_v1", "scope": "current_worker_attempt",
        "complete": raw.get("complete") is True,
        "boundary": "worker_return" if raw.get("boundary") == "worker_return" else "before_final_save",
        "pending_http_calls": raw.get("pending_http_calls", 0) if type(raw.get("pending_http_calls", 0)) is int and raw.get("pending_http_calls", 0) >= 0 else 0,
        "wall_clock_seconds": wall, "stages": metrics(raw.get("stages")),
        **{group: {label: metrics(value) for label, value in raw.get(group, {}).items()
                   if isinstance(label, str) and _LABEL.fullmatch(label)}
           for group in ("families", "units") if isinstance(raw.get(group), dict)},
    }
