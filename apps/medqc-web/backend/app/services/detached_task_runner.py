from __future__ import annotations

import asyncio
import inspect
import logging
import os
from concurrent.futures import Future, ThreadPoolExecutor
from typing import Any, Callable


logger = logging.getLogger(__name__)


def _resolve_worker_count() -> int:
    raw_value = os.getenv("MEDQC_DETACHED_TASK_WORKERS", "4")
    try:
        return max(1, int(raw_value))
    except (TypeError, ValueError):
        return 4


_EXECUTOR = ThreadPoolExecutor(
    max_workers=_resolve_worker_count(),
    thread_name_prefix="medqc-detached",
)


def _run_task(func: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
    result = func(*args, **kwargs)
    if inspect.isawaitable(result):
        return asyncio.run(result)
    return result


def submit_detached_task(
    name: str,
    func: Callable[..., Any],
    *args: Any,
    **kwargs: Any,
) -> Future[Any]:
    """在线程池中启动后台任务，避免 FastAPI BackgroundTasks 拖住响应。"""

    task_name = str(name or getattr(func, "__name__", "detached_task")).strip() or "detached_task"
    future = _EXECUTOR.submit(_run_task, func, *args, **kwargs)

    def _log_result(done: Future[Any]) -> None:
        try:
            done.result()
        except Exception:
            logger.exception("后台任务执行失败: %s", task_name)

    future.add_done_callback(_log_result)
    return future
