"""Gateway 单活动实例与已发出请求的生命周期。"""

from __future__ import annotations

import asyncio
from collections.abc import Coroutine
from datetime import datetime, timezone
import os
from pathlib import Path
from typing import Any


RESTART_INFLIGHT_POLICY = "unknown_until_operator_reconciles_sentinel"
SENTINEL_FILENAME = "llm-gateway-active.sentinel"


class SingleInstanceError(RuntimeError):
    """同一 state_dir 已有活动实例，或上次异常退出未完成人工确认。"""


class LifecycleClosedError(RuntimeError):
    pass


class SingleInstanceSentinel:
    """O_EXCL 持久标记。

    它只保护同一台机器、同一 state_dir。异常退出不删除标记，
    因此不会根据 PID 消失就无证据地宣称 Provider/GPU 已停止。
    """

    def __init__(self, state_dir: Path) -> None:
        self._state_dir = state_dir
        self.path = state_dir / SENTINEL_FILENAME
        self._acquired = False

    def acquire(self) -> None:
        try:
            self._state_dir.mkdir(parents=True, exist_ok=True)
            fd = os.open(self.path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        except FileExistsError:
            raise SingleInstanceError("gateway instance state requires operator reconciliation") from None
        except OSError:
            raise SingleInstanceError("gateway instance state is unavailable") from None
        try:
            payload = (
                "state=active_or_unknown\n"
                f"created_at={datetime.now(timezone.utc).isoformat()}\n"
                "recovery=operator_must_verify_provider_inflight_before_removal\n"
            ).encode("utf-8")
            os.write(fd, payload)
            os.fsync(fd)
        except OSError:
            try:
                os.close(fd)
            finally:
                try:
                    self.path.unlink()
                except OSError:
                    pass
            raise SingleInstanceError("gateway instance state is unavailable") from None
        else:
            os.close(fd)
            self._acquired = True

    def release_after_clean_drain(self) -> None:
        if not self._acquired:
            return
        try:
            self.path.unlink()
        except OSError as exc:
            raise SingleInstanceError("gateway instance state could not be cleared") from exc
        self._acquired = False


class RequestLifecycle:
    """当调用方取消时，仍持有已发出 HTTP task 直到它真正结束。"""

    def __init__(self) -> None:
        self._tasks: set[asyncio.Task[Any]] = set()
        self._accepting = True
        self._remote_inflight_unknown = False

    @property
    def accepting(self) -> bool:
        return self._accepting

    def stop_accepting(self) -> None:
        self._accepting = False

    @property
    def remote_inflight_unknown(self) -> bool:
        return self._remote_inflight_unknown

    def mark_remote_inflight_unknown(self) -> None:
        self._remote_inflight_unknown = True

    def create_provider_task(self, coroutine: Coroutine[Any, Any, Any]) -> asyncio.Task[Any]:
        if not self._accepting:
            coroutine.close()
            raise LifecycleClosedError("gateway lifecycle is closed")
        task = asyncio.create_task(coroutine)
        self._tasks.add(task)
        task.add_done_callback(self._task_done)
        return task

    def _task_done(self, task: asyncio.Task[Any]) -> None:
        self._tasks.discard(task)
        if not task.cancelled():
            # 主请求若已断开，在这里安全消费异常，不记录可能敏感的文本。
            task.exception()

    async def drain(self, grace_seconds: float) -> bool:
        self.stop_accepting()
        tasks = set(self._tasks)
        if not tasks:
            return True
        _done, pending = await asyncio.wait(tasks, timeout=grace_seconds)
        if not pending:
            return True
        # 进程需要退出时只能停止本地 HTTP；这不证明远程 GPU 已停止。
        for task in pending:
            task.cancel()
        await asyncio.gather(*pending, return_exceptions=True)
        return False


__all__ = [
    "LifecycleClosedError",
    "RESTART_INFLIGHT_POLICY",
    "RequestLifecycle",
    "SENTINEL_FILENAME",
    "SingleInstanceError",
    "SingleInstanceSentinel",
]
