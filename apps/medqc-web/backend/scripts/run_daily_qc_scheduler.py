"""独立每日调度进程；同样需要显式开启，不能绕过默认关闭设置。"""

import asyncio
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.settings import get_settings  # noqa: E402
from app.services.daily_qc.runner import run_loop  # noqa: E402


if __name__ == "__main__":
    if not get_settings().QC_DAILY_SCHEDULER_ENABLED:
        print("每日质控调度未启用；未读取计划、创建任务或调用模型。")
    else:
        try:
            asyncio.run(run_loop())
        except KeyboardInterrupt:
            pass
