"""请求内的执行时间预算；不包含规则判断，也不为无预算调用改变超时。"""

from contextlib import contextmanager
from contextvars import ContextVar
from time import monotonic
from typing import Any


_DEADLINE: ContextVar[float | None] = ContextVar('lx0609_execution_deadline', default=None)
CONSULTATION_RULE_BUDGET_SECONDS = 300.0
CONSULTATION_FAMILY_WATCHDOG_SECONDS = 330.0


@contextmanager
def execution_time_budget(seconds: float):
    parent = _DEADLINE.get()
    deadline = monotonic() + seconds
    token = _DEADLINE.set(min(parent, deadline) if parent is not None else deadline)
    try:
        yield
    finally:
        _DEADLINE.reset(token)


def remaining_seconds() -> float | None:
    deadline = _DEADLINE.get()
    return None if deadline is None else max(0.0, deadline - monotonic())


def request_timeout(maximum: float) -> float:
    remaining = remaining_seconds()
    if remaining is None:
        return maximum
    if remaining <= 0:
        raise TimeoutError('execution budget exhausted')
    return min(maximum, remaining)


def retry_fits(*, delay_seconds: float, attempt_seconds: float) -> bool:
    remaining = remaining_seconds()
    return remaining is None or remaining > delay_seconds + attempt_seconds


def model_timeout_seconds(client: Any, default: float = 120.0) -> float:
    """沿包装链（应答冻结 _inner、隐私包装 delegate）找真实客户端的单次请求超时。

    只读实例自身属性，避免包装器 __getattr__ 透传把中间层误当成配置所在层。
    """
    seen: set[int] = set()
    current = client
    while current is not None and id(current) not in seen:
        seen.add(id(current))
        attributes = getattr(current, '__dict__', {})
        value = attributes.get('timeout_seconds')
        if isinstance(value, (int, float)) and not isinstance(value, bool) and value > 0:
            return float(value)
        current = attributes.get('_inner') or attributes.get('delegate')
    return default


def follow_up_fits(client: Any) -> bool:
    """补核、补问、复核前调用：剩余预算放不下一次完整请求时不再发起，按该处既有失败路径处理。"""
    return retry_fits(delay_seconds=0.0, attempt_seconds=model_timeout_seconds(client))
