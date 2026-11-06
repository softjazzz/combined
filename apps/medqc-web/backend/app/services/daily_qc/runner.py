"""后台触发循环；缺省关闭，浏览器不承担计时，多个进程由数据库领取。"""

import asyncio
import logging

from ...core.settings import get_settings
from .service import BatchAdmission, default_store, tick


logger = logging.getLogger(__name__)


def _tick_sync():
    store = default_store()
    return asyncio.run(tick(store, BatchAdmission(store)))


async def run_loop():
    while get_settings().QC_DAILY_SCHEDULER_ENABLED:
        current_tick = asyncio.create_task(asyncio.to_thread(_tick_sync))
        try:
            await asyncio.shield(current_tick)
        except asyncio.CancelledError:
            # to_thread不能靠取消Future终止。等待本轮安全落账后再关闭共享资源；
            # 强制杀进程时仍由持久租约与固定任务ID负责恢复。
            await asyncio.gather(current_tick, return_exceptions=True)
            raise
        except Exception:
            logger.error(
                "daily_qc_tick_unavailable; check migration 064 and account authorization"
            )
        await asyncio.sleep(30)


def start(app):
    if not get_settings().QC_DAILY_SCHEDULER_ENABLED:
        return
    if getattr(app.state, "daily_qc_task", None) is None:
        app.state.daily_qc_task = asyncio.create_task(run_loop())


async def stop(app):
    task = getattr(app.state, "daily_qc_task", None)
    app.state.daily_qc_task = None
    if task is not None:
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)
