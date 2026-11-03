"""检查族有限恢复与Token事件分批；不判断医学事实，不裁剪任何正文。"""
from __future__ import annotations

import asyncio
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from functools import wraps
import logging
import time

from ..llm_token_budget import BudgetError, BudgetVerdict, LOCAL, client_probe, split_enabled, note_budget_failure

logger = logging.getLogger(__name__)
_CURRENT = ContextVar("exam_context_recovery", default=None)
_CALL = ContextVar("exam_context_call_attempts", default=None)


@dataclass
class RecoveryBudget:
    max_requests: int = 16
    max_depth: int = 8
    max_recoveries: int = 8
    seconds: float = 240
    used: int = 0
    recoveries: int = 0
    started: float = 0

    def __post_init__(self):
        self.started = time.monotonic()

    def remaining(self):
        return self.seconds - (time.monotonic() - self.started)

    def take(self, *, recovery=False):
        if self.used >= self.max_requests or self.remaining() <= 0 or recovery and self.recoveries >= self.max_recoveries:
            refuse(BudgetVerdict("BUDGET_EXHAUSTED", "recovery_budget_exhausted", "exam", "bounded"))
        self.used += 1
        self.recoveries += int(recovery)


def refuse(verdict):
    error = BudgetError(verdict)
    note_budget_failure(error)
    raise error


def current_budget():
    return _CURRENT.get()


def full_evidence_mode():
    return split_enabled() and _CURRENT.get() is not None


def active(client):
    if client is None or not split_enabled():
        return False
    from ..exam_result_model_route import _unwrap
    base, _ = _unwrap(client)
    return split_enabled() and getattr(base, "provider_code", None) in LOCAL


@contextmanager
def recovery_scope():
    if _CURRENT.get() is not None:
        yield _CURRENT.get()
        return
    budget = RecoveryBudget()
    token = _CURRENT.set(budget)
    try:
        yield budget
    finally:
        _CURRENT.reset(token)


@contextmanager
def model_call_scope(*, recovery=False):
    if _CALL.get() is not None:
        yield
        return
    token = _CALL.set([0, recovery])
    try:
        yield
    finally:
        _CALL.reset(token)


def take_http_attempt(client):
    budget = _CURRENT.get()
    if budget is None or not active(client):
        return
    state = _CALL.get()
    budget.take(recovery=bool(state and (state[0] or state[1])))
    if state is not None:
        state[0] += 1


def exam_recovery_executor(function):
    @wraps(function)
    async def run(*args, **kwargs):
        if not active(kwargs.get("llm_client")):
            return await function(*args, **kwargs)
        with recovery_scope() as budget:
            return await asyncio.wait_for(function(*args, **kwargs), max(.001, budget.remaining()))
    return run


async def generate(client, prompt, *, recovery=False, **kwargs):
    if not active(client):
        return await client.generate(prompt, **kwargs)
    from ..exam_result_model_route import _unwrap
    base, _ = _unwrap(client)
    if getattr(base, "strata_observation_mode", "off") == "prefix":
        # Gateway远程Prime不能共享进程内子请求预算；未有协议前不假装已受同一上限保护。
        refuse(BudgetVerdict("CAPABILITY_UNVERIFIED", "split_prefix_budget_not_supported", "exam", str(base.model)))
    # 不补默认输出上限：未指定时沿用实际客户端配置，超限就明确拒绝。
    kwargs["allow_length_retry"] = False
    verdict = client_probe(client, prompt, **kwargs)
    if verdict is None or verdict.status != "ACCEPT":
        refuse(verdict or BudgetVerdict("CAPABILITY_UNVERIFIED", "no_probe", "exam", "unbound"))
    with recovery_scope() as budget:
        # 真实客户端在每个HTTP尝试处扣款，不能被隐私包装器的传输重试乘算绕过。
        if not getattr(base, "owns_context_attempt_budget", False):
            budget.take(recovery=recovery)  # 固定应答替身的单次调用。
        try:
            with model_call_scope(recovery=recovery):
                return await asyncio.wait_for(client.generate(prompt, **kwargs), max(.001, budget.remaining()))
        except asyncio.TimeoutError:
            error = BudgetError(BudgetVerdict("BUDGET_EXHAUSTED", "recovery_deadline_exceeded", "exam", str(getattr(client, "model", "unbound"))))
            error.request_started = True
            note_budget_failure(error)
            raise error from None


def plan_events(projection, event_keys, rule_ids, client, prompt_builder):
    from .exam_lab_projection_batching import select_exam_lab_projection_batch
    from .exam_lab_fact_extraction import build_exam_lab_fact_response_format, events_for_family, EXAM_RULE_IDS
    accepted, rejected = [], []
    planned_nodes = 0
    with recovery_scope() as budget:
        def visit(keys, depth):
            nonlocal planned_nodes
            planned_nodes += 1
            current = select_exam_lab_projection_batch(projection, keys)
            scoped_rules = tuple(rule for rule in rule_ids if events_for_family(current.projection, "exam" if rule in EXAM_RULE_IDS else "culture"))
            kwargs = {}
            supports = getattr(client, "supports_strict_json_schema", None)
            if callable(supports) and supports() is True:
                kwargs["response_format"] = build_exam_lab_fact_response_format(selected_rule_ids=scoped_rules, projection=current.projection)
            if planned_nodes > 2 * budget.max_requests or budget.remaining() <= 0:
                rejected.append((current, BudgetVerdict("BUDGET_EXHAUSTED", "plan_budget_exhausted", "exam", "bounded")))
                return
            result = client_probe(client, prompt_builder(current.projection, scoped_rules), **kwargs)
            if result is not None and result.status == "ACCEPT":
                accepted.append(current)
                return
            if (result is not None and result.status == "OVER_BUDGET" and len(keys) > 1
                    and depth < budget.max_depth and budget.remaining() > 0
                    and budget.recoveries < budget.max_recoveries):
                budget.recoveries += 1
                middle = len(keys) // 2
                visit(keys[:middle], depth + 1)
                visit(keys[middle:], depth + 1)
            else:
                rejected.append((current, result or BudgetVerdict("CAPABILITY_UNVERIFIED", "no_probe", "exam", "unbound")))
        visit(tuple(event_keys), 0)
    logger.info("exam_context_plan accepted_batches=%s rejected_batches=%s event_count=%s", len(accepted), len(rejected), len(event_keys))
    return accepted, rejected
