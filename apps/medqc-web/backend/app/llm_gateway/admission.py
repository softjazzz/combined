"""物理资源的有界准入：最早可执行者优先，同病例不占两个推理槽。"""

from __future__ import annotations

import asyncio
from collections import deque
from dataclasses import dataclass
import time
from typing import Iterable

from app.services.llm_dispatch.contracts import GatewayErrorCode

from .config import ResourceConfig


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
    def __init__(self, config: ResourceConfig) -> None:
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

    async def acquire(self, *, monotonic_deadline: float, case_key: str | None = None) -> AdmissionLease:
        loop = asyncio.get_running_loop()
        queued_at = time.monotonic()
        async with self._lock:
            if not self._accepting:
                if self._quarantined:
                    raise ResourceQuarantinedError()
                raise GatewayShuttingDownError()
            if monotonic_deadline <= loop.time():
                raise AdmissionDeadlineError()
            # 先服务最早可执行者；同病例阻塞的队首不应闲置另一物理槽。
            self._grant_waiters_locked()
            if self._inflight < self._effective_max_inflight and self._case_available(case_key):
                self._occupy(case_key)
                return AdmissionLease(self, 0.0, case_key)
            if len(self._waiters) >= self.max_queue:
                raise QueueFullError()
            waiter = _Waiter(future=loop.create_future(), queued_at=queued_at, case_key=case_key)
            self._waiters.append(waiter)

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
            return AdmissionLease(self, time.monotonic() - queued_at, case_key)
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
                self._grant_waiters_locked()
                return
            if not waiter.claimed:
                # 位置已授予，但调用方在观察到之前取消；当场归还。
                self._inflight -= 1
                if waiter.case_key is not None:
                    self._active_cases.discard(waiter.case_key)
                self._grant_waiters_locked()

    async def _release(self, case_key: str | None = None) -> None:
        async with self._lock:
            if self._inflight <= 0:
                raise RuntimeError("admission slot released more than once")
            self._inflight -= 1
            if case_key is not None:
                self._active_cases.discard(case_key)
            self._grant_waiters_locked()

    def _grant_waiters_locked(self) -> None:
        while self._accepting and self._inflight < self._effective_max_inflight and self._waiters:
            self._waiters = deque(waiter for waiter in self._waiters if not waiter.future.done())
            waiter = next((item for item in self._waiters if self._case_available(item.case_key)), None)
            if waiter is None:
                break
            self._waiters.remove(waiter)
            waiter.granted = True
            self._occupy(waiter.case_key)
            waiter.future.set_result(None)

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
            # 不清理关闭/远端未知隔离状态，调容量不能当作恢复GPU的证据。
            self._grant_waiters_locked()

    async def close(self) -> None:
        async with self._lock:
            self._accepting = False
            while self._waiters:
                waiter = self._waiters.popleft()
                if not waiter.future.done():
                    waiter.future.set_exception(GatewayShuttingDownError())

    async def quarantine(self) -> None:
        async with self._lock:
            self._accepting = False
            self._quarantined = True
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
                "accepting": self._accepting,
                "unknown_inflight": self._quarantined,
            }


class AdmissionManager:
    def __init__(self, resources: Iterable[ResourceConfig]) -> None:
        self._pools = {item.resource_id: ResourceAdmissionPool(item) for item in resources}

    async def acquire(self, resource_id: str, *, monotonic_deadline: float, case_key: str | None = None) -> AdmissionLease:
        # profile 在启动时已检查引用，运行期不接受任意 resource_id。
        pool = self._pools.get(resource_id)
        if pool is None:
            raise GatewayShuttingDownError()
        return await pool.acquire(monotonic_deadline=monotonic_deadline, case_key=case_key)

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
