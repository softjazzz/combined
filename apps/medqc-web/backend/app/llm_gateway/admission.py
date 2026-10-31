"""物理资源的有界准入：最早可执行者优先，同病例不占两个推理槽。"""

from __future__ import annotations

import asyncio
from collections import deque
from dataclasses import dataclass
import time
from typing import Callable, Iterable

from app.services.llm_dispatch.contracts import GatewayErrorCode

from .config import ResourceConfig, CaseContinuationConfig
from .continuation import CaseContinuationPolicy


class AdmissionError(RuntimeError):
    code = GatewayErrorCode.SHUTTING_DOWN.value
    status_code = 503
    retryable = True


class QueueFullError(AdmissionError):
    code = GatewayErrorCode.QUEUE_FULL.value
    status_code = 429


class AdmissionDeadlineError(AdmissionError):
    code = GatewayErrorCode.DEADLINE_EXCEEDED.value
    status_code = 504
    retryable = False


class GatewayShuttingDownError(AdmissionError):
    code = GatewayErrorCode.SHUTTING_DOWN.value
    status_code = 503


class ResourceQuarantinedError(AdmissionError):
    code = GatewayErrorCode.RESOURCE_QUARANTINED.value
    status_code = 503
    retryable = False


@dataclass(slots=True)
class _Waiter:
    future: asyncio.Future[None]
    queued_at: float
    case_key: str | None = None
    package_key: str | None = None
    granted: bool = False
    claimed: bool = False


class AdmissionLease:
    """一个必须由实际 HTTP 生命周期 owner 释放的位置。"""

    __slots__ = ("_pool", "queue_seconds", "_released", "_case_key")

    def __init__(self, pool: "ResourceAdmissionPool", queue_seconds: float, case_key: str | None = None) -> None:
        self._pool = pool
        self.queue_seconds = max(0.0, queue_seconds)
        self._released = False
        self._case_key = case_key

    async def release(self) -> None:
        if self._released:
            return
        self._released = True
        await self._pool._release(self._case_key)

    async def __aenter__(self) -> "AdmissionLease":
        return self

    async def __aexit__(self, *_args: object) -> None:
        await self.release()


class ResourceAdmissionPool:
    def __init__(self, config: ResourceConfig, *, continuation: CaseContinuationConfig | None = None,
                 clock: Callable[[], float] = time.monotonic) -> None:
        self.resource_id = config.resource_id
        self.max_inflight = config.max_inflight
        self._effective_max_inflight = config.max_inflight
        self.max_queue = config.max_queue
        self._inflight = 0
        self._waiters: deque[_Waiter] = deque()
        self._accepting = True
        self._quarantined = False
        self._lock = asyncio.Lock()
        self._active_cases: set[str] = set()
        self._clock = clock
        self._continuation = CaseContinuationPolicy(continuation) if continuation and continuation.enabled else None
        self._wake_handle: asyncio.TimerHandle | None = None
        self._wake_task: asyncio.Task | None = None

    async def acquire(self, *, monotonic_deadline: float, case_key: str | None = None,
                      package_key: str | None = None) -> AdmissionLease:
        loop = asyncio.get_running_loop()
        queued_at = self._clock()
        async with self._lock:
            if not self._accepting:
                if self._quarantined:
                    raise ResourceQuarantinedError()
                raise GatewayShuttingDownError()
            if monotonic_deadline <= loop.time():
                raise AdmissionDeadlineError()
            # 新请求与旧等待者一起选择，不能绕过短间隙或老化保护。
            waiter = _Waiter(future=loop.create_future(), queued_at=queued_at,
                             case_key=case_key, package_key=package_key)
            self._waiters.append(waiter)
            self._grant_waiters_locked()
            if waiter.granted:
                waiter.claimed = True
                return AdmissionLease(self, max(0, self._clock() - queued_at), case_key)
            if len(self._waiters) > self.max_queue:
                self._waiters.remove(waiter)
                waiter.future.cancel()
                self._grant_waiters_locked()
                raise QueueFullError()

        remaining = monotonic_deadline - loop.time()
        try:
            # Python3.10 wait_for在内部future恰好完成时可能吞掉外部取消。
            # wait不取消池拥有的future，随后统一由_withdraw归还病例/物理槽。
            done, _ = await asyncio.wait({waiter.future}, timeout=max(0.0, remaining))
            if not done:
                raise asyncio.TimeoutError()
            waiter.future.result()
            if loop.time() >= monotonic_deadline:
                raise asyncio.TimeoutError()
            # await 与这次同步赋值之间没有新的 await，取消无法插入。
            waiter.claimed = True
            return AdmissionLease(self, self._clock() - queued_at, case_key)
        except asyncio.TimeoutError:
            await self._withdraw(waiter)
            raise AdmissionDeadlineError() from None
        except asyncio.CancelledError:
            await self._withdraw(waiter)
            raise

    async def _withdraw(self, waiter: _Waiter) -> None:
        async with self._lock:
            if not waiter.granted:
                try:
                    self._waiters.remove(waiter)
                except ValueError:
                    pass
                if not waiter.future.done():
                    waiter.future.cancel()
                if self._continuation and waiter.case_key not in self._active_cases:
                    self._continuation.forget(waiter.case_key)
                self._grant_waiters_locked()
                return
            if not waiter.claimed:
                # 位置已授予，但调用方在观察到之前取消；当场归还。
                self._inflight -= 1
                if waiter.case_key is not None:
                    self._active_cases.discard(waiter.case_key)
                if self._continuation:
                    self._continuation.forget(waiter.case_key)
                self._grant_waiters_locked()

    async def _release(self, case_key: str | None = None) -> None:
        async with self._lock:
            if self._inflight <= 0:
                raise RuntimeError("admission slot released more than once")
            self._inflight -= 1
            if case_key is not None:
                self._active_cases.discard(case_key)
            if self._continuation:
                self._continuation.released(case_key, self._clock())
            self._grant_waiters_locked()

    def _grant_waiters_locked(self) -> None:
        self._cancel_wakeup_locked()
        while self._accepting and self._inflight < self._effective_max_inflight and self._waiters:
            self._waiters = deque(waiter for waiter in self._waiters if not waiter.future.done())
            eligible = [item for item in self._waiters if self._case_available(item.case_key)]
            if self._continuation:
                waiter, wake_at = self._continuation.choose(eligible, self._active_cases, self._clock(),
                                                           capacity=self._effective_max_inflight)
                if waiter is None and wake_at is not None:
                    self._wake_handle = asyncio.get_running_loop().call_later(
                        max(0, wake_at - self._clock()), self._schedule_wakeup)
            else:
                waiter = eligible[0] if eligible else None
            if waiter is None:
                break
            self._waiters.remove(waiter)
            waiter.granted = True
            self._occupy(waiter.case_key)
            if self._continuation:
                self._continuation.granted(waiter.case_key, waiter.package_key, self._clock(),
                                           capacity=self._effective_max_inflight)
            waiter.future.set_result(None)

    def _cancel_wakeup_locked(self):
        if self._wake_handle is not None:
            self._wake_handle.cancel()
            self._wake_handle = None

    def _schedule_wakeup(self):
        self._wake_handle = None
        self._wake_task = asyncio.create_task(self._wake())

    async def _wake(self):
        try:
            async with self._lock:
                self._grant_waiters_locked()
        finally:
            self._wake_task = None

    def _case_available(self, case_key: str | None) -> bool:
        return case_key is None or case_key not in self._active_cases

    def _occupy(self, case_key: str | None) -> None:
        self._inflight += 1
        if case_key is not None:
            self._active_cases.add(case_key)

    async def set_capacity(self, capacity: int) -> None:
        """可信容量owner的内部入口；降容不撤销在途lease，0仅暂停新发放。"""
        if type(capacity) is not int or not 0 <= capacity <= self.max_inflight:
            raise ValueError("invalid effective resource capacity")
        async with self._lock:
            self._effective_max_inflight = capacity
            if self._continuation:
                self._continuation.clear()
            # 不清理关闭/远端未知隔离状态，调容量不能当作恢复GPU的证据。
            self._grant_waiters_locked()

    async def close(self) -> None:
        async with self._lock:
            self._accepting = False
            self._cancel_wakeup_locked()
            if self._continuation:
                self._continuation.clear()
            while self._waiters:
                waiter = self._waiters.popleft()
                if not waiter.future.done():
                    waiter.future.set_exception(GatewayShuttingDownError())
            wake_task = self._wake_task
        if wake_task is not None:
            wake_task.cancel()
            await asyncio.gather(wake_task, return_exceptions=True)

    async def quarantine(self) -> None:
        async with self._lock:
            self._accepting = False
            self._quarantined = True
            self._cancel_wakeup_locked()
            if self._continuation:
                self._continuation.clear()
            while self._waiters:
                waiter = self._waiters.popleft()
                if not waiter.future.done():
                    waiter.future.set_exception(ResourceQuarantinedError())

    async def snapshot(self) -> dict[str, int | bool | str]:
        async with self._lock:
            return {
                "resource_id": self.resource_id,
                "max_inflight": self.max_inflight,
                "effective_max_inflight": self._effective_max_inflight,
                "max_queue": self.max_queue,
                "inflight": self._inflight,
                "queued": len(self._waiters),
                "active_cases": len(self._active_cases),
                "continuation_enabled": self._continuation is not None,
                "continuation_cases": self._continuation.case_count if self._continuation else 0,
                "continuation_wakeup_pending": self._wake_handle is not None,
                "accepting": self._accepting,
                "unknown_inflight": self._quarantined,
            }


class AdmissionManager:
    def __init__(self, resources: Iterable[ResourceConfig], *, continuation_resources: set[str] | None = None,
                 continuation: CaseContinuationConfig | None = None) -> None:
        self._pools = {item.resource_id: ResourceAdmissionPool(item,
            continuation=continuation if item.resource_id in (continuation_resources or set()) else None)
            for item in resources}

    async def acquire(self, resource_id: str, *, monotonic_deadline: float, case_key: str | None = None,
                      package_key: str | None = None) -> AdmissionLease:
        # profile 在启动时已检查引用，运行期不接受任意 resource_id。
        pool = self._pools.get(resource_id)
        if pool is None:
            raise GatewayShuttingDownError()
        return await pool.acquire(monotonic_deadline=monotonic_deadline, case_key=case_key, package_key=package_key)

    async def set_capacity(self, resource_id: str, capacity: int) -> None:
        pool = self._pools.get(resource_id)
        if pool is None:
            raise GatewayShuttingDownError()
        await pool.set_capacity(capacity)

    async def close(self) -> None:
        await asyncio.gather(*(pool.close() for pool in self._pools.values()))

    async def quarantine(self, resource_id: str) -> None:
        pool = self._pools.get(resource_id)
        if pool is not None:
            await pool.quarantine()

    async def snapshots(self) -> list[dict[str, int | bool | str]]:
        return await asyncio.gather(*(pool.snapshot() for pool in self._pools.values()))


__all__ = [
    "AdmissionDeadlineError",
    "AdmissionError",
    "AdmissionLease",
    "AdmissionManager",
    "GatewayShuttingDownError",
    "QueueFullError",
    "ResourceQuarantinedError",
    "ResourceAdmissionPool",
]
