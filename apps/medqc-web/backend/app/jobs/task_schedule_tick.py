"""一次性领取并派发到期质控计划，供外部周期调度器调用。"""

from __future__ import annotations

import json

from ..services.task_schedule_job_service import tick_due_schedules


def main() -> int:
    result = tick_due_schedules()
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
