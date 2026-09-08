"""单个已授权任务的诊断生命周期；原件不进入全局注册表或下载接口。

由服务端授权入口创建并传给 worker。consume 必须是本地脱敏/检查函数，
不能把它替换成写原件、网络发送或客户自定义回调。
"""

from __future__ import annotations

import asyncio
from contextlib import contextmanager
from functools import wraps
import inspect
import threading
import time
from typing import Awaitable, Callable

from .capture import _Capture, _CURRENT
from .contracts import DiagnosticPackageError


class DiagnosticJobCapture:
    def __init__(self, *, job_id: str, record_identity: tuple[str, str, str],
                 consume: Callable[[dict, dict], None], max_bytes: int = 20 * 1024 * 1024,
                 ttl_seconds: int = 1800):
        if (type(record_identity) is not tuple or len(record_identity) != 3
                or any(type(value) is not str or not value.strip() or len(value) > 128 for value in record_identity)):
            raise DiagnosticPackageError("invalid_capture_identity")
        if (not callable(consume) or inspect.iscoroutinefunction(consume)
                or inspect.iscoroutinefunction(getattr(consume, "__call__", None))):
            raise DiagnosticPackageError("invalid_capture_consumer")
        self.job_id = job_id
        self._record_identity: tuple[str, str, str] | None = record_identity
        self._capture = _Capture(max_bytes, ttl_seconds, job_id)
        self._consume = consume
        self._deadline = time.monotonic() + ttl_seconds
        self._lock = threading.Lock()
        self._started = False
        self._record_finished = False
        self._finished = False
        self._claimed = False
        self._errors: set[str] = set()

    def __repr__(self) -> str:
        return "DiagnosticJobCapture(raw_contents_hidden=True)"

    def claim(self, job_id: str) -> bool:
        """一次授权对象仅交给一个 worker，重复派发不能释放首个 worker 的原件。"""
        with self._lock:
            if self._claimed or self._finished or job_id != self.job_id:
                return False
            self._claimed = True
            return True

    @contextmanager
    def record_scope(self, identity: tuple[str, str, str]):
        selected = False
        with self._lock:
            if identity == self._record_identity and not self._finished:
                if self._started:
                    self._errors.add("duplicate_record_execution")
                else:
                    self._started = True
                    selected = True
        # 明确屏蔽非选中病例继承的 ambient context，不能串入同一个采集器。
        token = _CURRENT.set(self._capture if selected else None)
        try:
            yield
        finally:
            _CURRENT.reset(token)
            if selected:
                with self._lock:
                    self._record_finished = True

    @contextmanager
    def result_scope(self):
        with self._lock:
            ready = self._record_finished and not self._finished and not self._errors
        token = _CURRENT.set(self._capture if ready else None)
        try:
            yield
        finally:
            _CURRENT.reset(token)

    def summary(self) -> dict:
        with self._lock:
            errors = set(self._errors)
        summary = self._capture.summary()
        return {**summary, "missing_reasons": sorted(set(summary["missing_reasons"]) | errors)}

    def finish(self, *, deliver: bool) -> None:
        with self._lock:
            if self._finished:
                return
            self._finished = True
        try:
            if deliver and not self._errors:
                data = self._capture.read_internal()
                if data["execution_inputs"] is not None and data["saved_result"] is not None:
                    self._consume(data, self.summary())
                else:
                    self._errors.add("saved_capture_unavailable")
        except Exception:
            # 不回显可能包含患者原件的异常，也不影响正式质控状态。
            self._errors.add("diagnostic_delivery_failed")
        finally:
            self._capture.close()
            self._consume = lambda *_: None
            self._record_identity = None

    def expire(self) -> None:
        self._errors.add("expired")
        self.finish(deliver=False)


def diagnostic_job_lifecycle(worker: Callable[..., Awaitable[None]]) -> Callable[..., Awaitable[None]]:
    """覆盖 worker 的所有提前返回、取消和异常出口，不重写其任务调度。"""
    @wraps(worker)
    async def wrapped(job_id: str, *, diagnostic_capture: DiagnosticJobCapture | None = None, **kwargs):
        capture = diagnostic_capture
        if capture is not None and not capture.claim(job_id):
            capture = None
        timer = None
        finished = False
        token = _CURRENT.set(None)
        try:
            if capture is not None:
                timer = asyncio.get_running_loop().call_later(
                    max(0, capture._deadline - time.monotonic()), capture.expire,
                )
            await worker(job_id, diagnostic_capture=capture, **kwargs)
            finished = True
        finally:
            if timer is not None:
                timer.cancel()
            if capture is not None:
                capture.finish(deliver=finished)
            _CURRENT.reset(token)
    return wrapped
