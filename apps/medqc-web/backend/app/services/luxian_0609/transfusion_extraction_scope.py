"""单次证据快照执行内共享输血事实；不落盘、不跨病例或任务复用。"""

from __future__ import annotations

import asyncio
from contextlib import contextmanager
from contextvars import ContextVar
from copy import deepcopy
from dataclasses import dataclass, field, replace
from functools import wraps
import json
from typing import Any, Awaitable, Callable

from .rule_decision_settings import _luxian_0609_model_identity


@dataclass
class _Scope:
    active: bool = True
    pending: dict[tuple, asyncio.Future] = field(default_factory=dict)
    clients: dict[int, Any] = field(default_factory=dict)


_ACTIVE: ContextVar[_Scope | None] = ContextVar("transfusion_extraction_scope", default=None)
_RETRY = object()


@contextmanager
def transfusion_extraction_scope():
    """每次引擎调用独立建域，退出后继承此上下文的延迟调用也不能命中。"""
    scope = _Scope()
    token = _ACTIVE.set(scope)
    try:
        yield
    finally:
        scope.active = False
        for future in scope.pending.values():
            if not future.done():
                future.set_result(_RETRY)
        scope.pending.clear()
        scope.clients.clear()
        _ACTIVE.reset(token)


def with_transfusion_extraction_scope(function):
    @wraps(function)
    async def scoped(*args, **kwargs):
        with transfusion_extraction_scope():
            return await function(*args, **kwargs)
    return scoped


async def reuse_transfusion_extraction(
    *, protocol: str, material: str, client: Any,
    extract: Callable[[], Awaitable[Any]], confirmed: Callable[[Any], bool],
) -> Any:
    """共享完整校验通过的事实，实际调用用量仅归最先执行的消费者。

    首个消费者在自己的规则族任务中执行，保留隐私、观测及超时上下文；等待者
    的取消不取消它。首个任务取消或失败后不缓存错误，其他族可在自身预算内执行。
    """
    scope = _ACTIVE.get()
    if scope is None or not scope.active:
        return await extract()
    try:
        identity = _luxian_0609_model_identity(client)
    except ValueError:
        # 未声明模型配置的替身仍仅按同一个客户端实例复用，绝不跨客户端。
        identity = None
    model_key = json.dumps(identity, sort_keys=True, ensure_ascii=False, default=str)
    key = (protocol, material, id(client), model_key)
    scope.clients[id(client)] = client
    while scope.active:
        future = scope.pending.get(key)
        if future is not None:
            result = await asyncio.shield(future)
            if result is _RETRY:
                continue
            return replace(deepcopy(result), llm_call_count=0, prompt_tokens=0,
                           completion_tokens=0, total_tokens=0, api_time=0.0)
        future = asyncio.get_running_loop().create_future()
        scope.pending[key] = future
        try:
            result = await extract()
        except BaseException:
            scope.pending.pop(key, None)
            if not future.done():
                future.set_result(_RETRY)
            raise
        if confirmed(result) and scope.active:
            future.set_result(deepcopy(result))
        else:
            scope.pending.pop(key, None)
            if not future.done():
                future.set_result(_RETRY)
        return result
    return await extract()
