"""助手写入开关：正式入口默认关闭，仅在环境显式设置为 1 时允许写入。

开关在每次请求时读取环境变量，部署方可无需改代码地启停；关闭时只读功能不受影响。
未启用用 HTTP 423（Locked），与授权失效的 403 区分，前端据此给出明确提示。
"""
from __future__ import annotations

import os

from fastapi import HTTPException

FEEDBACK_SWITCH = "MEDQC_AGENT_FEEDBACK_WRITE_ENABLED"
TASK_SWITCH = "MEDQC_AGENT_TASK_WRITE_ENABLED"


def enabled(name: str) -> bool:
    return os.environ.get(name, "0").strip() == "1"


def require_feedback_write() -> None:
    if not enabled(FEEDBACK_SWITCH):
        raise HTTPException(423, "当前环境未启用实名异议反馈写入；本次未提交反馈")


def require_task_write() -> None:
    if not enabled(TASK_SWITCH):
        raise HTTPException(423, "当前环境未启用助手创建质控任务；本次未提交任务，如需复检请在正式任务页面发起")
