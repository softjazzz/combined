"""部署Profile级Context准入。无默认估算器、不连接数据库或Token服务。"""
from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
from copy import deepcopy
from dataclasses import asdict, dataclass
import json
import hashlib
import logging
import os
import time
import threading
from functools import wraps
from typing import Callable, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from .llm_dispatch.provider_profiles import ProviderConfigurationError
from .llm_context_contract import CONTEXT_REASON_CODES, CONTEXT_FAILURE_REASON_CODES

logger = logging.getLogger(__name__)
LOCAL = frozenset({"strata", "ollama", "local_openai"})
PROTOCOL = "lx0609-token-batches-p5b-v2"


class BudgetCapability(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)
    profile: str = Field(min_length=1, max_length=64)
    provider: str = Field(min_length=1)
    model: str = Field(min_length=1)
    model_revision: str = Field(min_length=1)
    context_tokens: int = Field(gt=0, le=2097152)
    safety_margin: int = Field(default=128, ge=0)
    tokenizer_id: str = Field(min_length=1)
    tokenizer_revision: str = Field(min_length=1)
    chat_template_id: str = Field(min_length=1)
    chat_template_revision: str = Field(min_length=1)
    counter_id: str = Field(min_length=1)
    counter_revision: str = Field(min_length=1)
    verified_message_shapes: tuple[str, ...] = ()
    verified: bool = False
    thinking_semantics: Literal["unknown", "included_in_max_output"] = "unknown"

    @field_validator('verified_message_shapes', mode='before')
    @classmethod
    def require_explicit_role_sequences(cls, value):
        # JSON列表显式转为不可变合同；例如user与system|user是不同验证形态。
        if not isinstance(value, (list, tuple)) or len(value) > 16:
            raise ValueError('invalid verified message shapes')
        for shape in value:
            if (not isinstance(shape, str) or len(shape) > 127
                    or any(role not in {'system', 'user', 'assistant'} for role in shape.split('|'))):
                raise ValueError('invalid verified message shape')
        return tuple(dict.fromkeys(value))


@dataclass(frozen=True)
class CounterIdentity:
    model: str
    model_revision: str
    tokenizer_id: str
    tokenizer_revision: str
    chat_template_id: str
    chat_template_revision: str
    verified_message_shapes: tuple[str, ...] = ()


@dataclass(frozen=True)
class BudgetVerdict:
    status: str
    reason: str
    profile: str
    model: str
    input_tokens: int | None = None
    output_reserve: int | None = None
    context_tokens: int | None = None
    safety_margin: int | None = None
    counter: str | None = None
    counting_seconds: float = 0
    message_shape: str | None = None


class BudgetError(ProviderConfigurationError):
    retryable = False
    status_code = 400

    def __init__(self, verdict: BudgetVerdict):
        self.verdict = verdict
        self.code = CONTEXT_REASON_CODES.get(verdict.status, CONTEXT_REASON_CODES["BUDGET_EXHAUSTED"])
        super().__init__(self.code)


# 由未来DSH部署适配器显式注册真实计量实现；本轮不提供字符估算或伪分词器。
_COUNTERS: dict[tuple[str, str], tuple[CounterIdentity, Callable[[dict], int]]] = {}
_COUNTERS_LOCK = threading.RLock()
_FAILURES = ContextVar("llm_context_budget_failures", default=None)
_FREEZE_IDENTITY = ContextVar("llm_context_freeze_identity", default=None)


class _BudgetFailures(list):
    """已由规则所有者承接的错误仍阻止冻结，但不再抹去同族返回值。"""
    def __init__(self):
        super().__init__()
        self.handled = set()

    def unhandled(self):
        return [error for error in self if id(error) not in self.handled]


def freeze_identity(client) -> str | None:
    if client is None:
        return None
    from .exam_result_model_route import _unwrap
    base, _ = _unwrap(client)
    provider = getattr(base, "provider_code", "")
    from .strata_protocol import is_p9_client
    p9 = is_p9_client(base)
    if provider not in LOCAL or not (strict_enabled() or split_enabled() or p9):
        return None
    model = str(getattr(base, "model", ""))
    profile, cap = deployed_capability(provider, model, getattr(base, "gateway_profile", None), getattr(base, "api_endpoint", None),
                                      dispatch_mode=getattr(base, 'dispatch_mode', 'direct'))
    # 双模型路由的候选Profile能力版本也须隔离，不能只绑定参考模型。
    from .exam_result_model_route import current_route
    route = current_route()
    route_capabilities = []
    if route is not None:
        try:
            entries = json.loads(os.getenv("LLM_GATEWAY_PROFILES_JSON", "[]"))
            if isinstance(entries, dict):
                entries = [{"profile": key, **item} for key, item in entries.items()]
            for item in entries:
                if (item.get("profile") == route.policy.candidate_profile
                        and item.get("provider_code") == route.policy.candidate_provider
                        and item.get("model") == route.policy.candidate_model):
                    candidate_cap = BudgetCapability.model_validate(item["context_budget"])
                    route_capabilities.append(candidate_cap.model_dump())
        except (ValueError, TypeError, KeyError, AttributeError):
            route_capabilities = ["unverified"]
    transport = {}
    if p9:
        from .strata_protocol import PROTOCOL_VERSION, deployed_identity
        identity = deployed_identity(provider, model, profile, getattr(base, 'api_endpoint', None))
        transport = {'strata_transport_protocol': PROTOCOL_VERSION,
                     'model_identity': identity.model_dump() if identity else None}
    return json.dumps({**transport, "protocol": PROTOCOL, "provider": provider, "model": model, "profile": profile,
        "route_capabilities": route_capabilities,
        "capability": cap.model_dump() if cap else None, "strict": strict_enabled() or p9, "split": split_enabled()}, sort_keys=True)


@contextmanager
def token_freeze_scope(client):
    token = _FREEZE_IDENTITY.set(freeze_identity(client))
    try:
        yield
    finally:
        _FREEZE_IDENTITY.reset(token)


def freeze_namespace():
    identity = _FREEZE_IDENTITY.get()
    return hashlib.sha256(identity.encode()).hexdigest() if identity is not None else None


@contextmanager
def budget_failure_scope():
    failures = _BudgetFailures()
    token = _FAILURES.set(failures)
    try:
        yield failures
    finally:
        _FAILURES.reset(token)


def context_budget_failed() -> bool:
    return bool(_FAILURES.get())


@contextmanager
def budget_rule_scope(on_failure):
    """规则所有者显式承接局部失败；未知/未承接错误仍沿原保守边界抛出。"""
    parent = _FAILURES.get()
    with budget_failure_scope() as failures:
        try:
            yield
        except BaseException as error:
            if not is_budget_error(error):
                raise
            note_budget_failure(error)
        finally:
            if failures:
                # 回调由执行器生成技术结果，不在基础设施层重判临床状态。
                # 若回调失败，错误不得被标为已承接。
                if parent is not None:
                    parent.extend(error for error in failures if error not in parent)
                on_failure(failures[0])
                if isinstance(parent, _BudgetFailures):
                    parent.handled.update(id(error) for error in failures)


def budget_guarded_executor(function):
    """仅未由具体规则承接的旧catch异常在执行器边界失败关闭。"""
    @wraps(function)
    async def run(*args, **kwargs):
        failures = _BudgetFailures()
        token = _FAILURES.set(failures)
        escaped = None
        try:
            with token_freeze_scope(kwargs.get("llm_client")):
                result = await function(*args, **kwargs)
            if failures.unhandled():
                raise failures.unhandled()[0]
            return result
        except BaseException as error:
            if is_budget_error(error):
                escaped = error
            raise
        finally:
            _FAILURES.reset(token)
            if escaped is not None:
                note_budget_failure(escaped)
    return run


def is_budget_error(error) -> bool:
    return isinstance(error, BudgetError) or str(getattr(error, "code", "")) in CONTEXT_FAILURE_REASON_CODES


def note_budget_failure(error):
    if is_budget_error(error) and _FAILURES.get() is not None and error not in _FAILURES.get():
        _FAILURES.get().append(error)


def register_counter(name: str, revision: str, identity: CounterIdentity, counter: Callable[[dict], int]) -> None:
    with _COUNTERS_LOCK:
        if (name, revision) in _COUNTERS or not callable(counter):
            raise ValueError("counter identity already registered or invalid")
        _COUNTERS[name, revision] = (identity, counter)


def unregister_counter(name, revision, owner) -> bool:
    """只卸载自己的实例，防止关闭一个Runtime误删别人的注册。"""
    with _COUNTERS_LOCK:
        entry = _COUNTERS.get((name, revision))
        if entry is None or entry[1] is not owner:
            return False
        del _COUNTERS[name, revision]
        return True


@contextmanager
def counter_scope(name: str, revision: str, identity: CounterIdentity, counter: Callable[[dict], int]):
    """固定应答验收/部署装配的独立生命周期，不把Mock能力写入配置。"""
    register_counter(name, revision, identity, counter)
    try:
        yield
    finally:
        unregister_counter(name, revision, counter)


def _flag(name):
    value = os.getenv(name, "false").strip().lower()
    if value not in {"true", "false"}:
        raise BudgetError(BudgetVerdict("CAPABILITY_UNVERIFIED", "invalid_feature_flag", "unbound", "unbound"))
    return value == "true"


def strict_enabled() -> bool:
    return _flag("LLM_LOCAL_TOKEN_BUDGET_ENABLED")


def split_enabled() -> bool:
    return _flag("LX0609_TOKEN_SPLIT_ENABLED")


def assess_payload(provider: str, profile: str, payload: dict, capability: BudgetCapability | None,
                   *, enabled: bool) -> BudgetVerdict:
    model = str(payload.get("model", ""))
    def verdict(status, reason, **kw):
        return BudgetVerdict(status, reason, profile, model, **kw)
    if not enabled or provider not in LOCAL:
        return verdict("ACCEPT", "legacy_or_cloud")
    cap = capability
    if (cap is None or not cap.verified or cap.profile != profile or cap.provider != provider or cap.model != model
            or cap.thinking_semantics != "included_in_max_output"):
        return verdict("CAPABILITY_UNVERIFIED", "profile_model_or_semantics_unverified")
    metadata = dict(context_tokens=cap.context_tokens, safety_margin=cap.safety_margin,
                    counter=cap.counter_id + ":" + cap.counter_revision)
    values = [payload[k] for k in ("max_tokens", "max_completion_tokens") if k in payload]
    if not values or any(type(v) is not int or v <= 0 for v in values) or len(set(values)) != 1:
        return verdict("CAPABILITY_UNVERIFIED", "output_reserve_not_explicit", **metadata)
    reserve = values[0]
    metadata["output_reserve"] = reserve
    messages = payload.get('messages')
    # 首期仅承认明确验证过的纯文本角色序列，不顺带放行工具或富媒体协议。
    if (not isinstance(messages, list) or not messages or payload.get('tools') or payload.get('tool_choice')
            or any(not isinstance(item, dict) or set(item) != {'role', 'content'}
                   or not isinstance(item.get('role'), str)
                   or item['role'] not in {'system', 'user', 'assistant'}
                   or not isinstance(item.get('content'), str) for item in messages)):
        return verdict('CAPABILITY_UNVERIFIED', 'message_shape_unverified', **metadata)
    shape = '|'.join(item['role'] for item in messages)
    metadata['message_shape'] = shape
    if shape not in cap.verified_message_shapes:
        return verdict('CAPABILITY_UNVERIFIED', 'message_shape_unverified', **metadata)
    thinking_values = [value for value in (payload.get("thinking_budget"),
        (payload.get("chat_template_kwargs") or {}).get("thinking_budget")) if value is not None]
    if any(type(thinking) is not int or thinking < 0 or thinking > reserve for thinking in thinking_values):
        return verdict("CAPABILITY_UNVERIFIED", "thinking_output_semantics_unverified", **metadata)
    with _COUNTERS_LOCK:
        entry = _COUNTERS.get((cap.counter_id, cap.counter_revision))
    expected = CounterIdentity(**{key: getattr(cap, key) for key in CounterIdentity.__dataclass_fields__})
    if entry is None:
        return verdict("COUNT_UNAVAILABLE", "counter_not_installed", **metadata)
    if entry[0] != expected:
        return verdict("CAPABILITY_UNVERIFIED", "counter_model_template_mismatch", **metadata)
    started = time.monotonic()
    try:
        # 计量器不得修改实际请求；包括全部messages/模板与特殊Token，不能扣cached。
        measured = entry[1](deepcopy(payload))
        if type(measured) is not int or measured < 0:
            raise ValueError
    except Exception:
        return verdict("COUNT_UNAVAILABLE", "counter_failed", counting_seconds=time.monotonic() - started, **metadata)
    status = "ACCEPT" if measured + reserve + cap.safety_margin <= cap.context_tokens else "OVER_BUDGET"
    return verdict(status, "fits" if status == "ACCEPT" else "context_capacity_exceeded", input_tokens=measured,
                   counting_seconds=time.monotonic() - started, **metadata)


def guard_payload(provider: str, profile: str, payload: dict, capability: BudgetCapability | None,
                  *, enabled: bool, phase: str = "provider_send", attribution: dict | None = None) -> BudgetVerdict:
    result = assess_payload(provider, profile, payload, capability, enabled=enabled)
    if enabled and provider in LOCAL:
        # 只写低基数能力/计数元数据，无正文、端点、凭据或患者标识。
        logger.info("llm_context_admission %s", json.dumps({**asdict(result), "phase": phase,
            "provider_http_started": False, "protocol": PROTOCOL, **(attribution or {})}, ensure_ascii=False))
    if result.status != "ACCEPT":
        error = BudgetError(result)
        if _FAILURES.get() is not None:
            _FAILURES.get().append(error)
        raise error
    return result


def deployed_capability(provider: str, model: str, profile: str | None, endpoint: str | None,
                        *, dispatch_mode: str = 'direct') -> tuple[str, BudgetCapability | None]:
    """复用既有Gateway部署Profile目录，直接HTTP也须绑定同一真实部署身份。"""
    try:
        raw = json.loads(os.getenv("LLM_GATEWAY_PROFILES_JSON", "[]"))
        if isinstance(raw, dict):
            entries = [{"profile": key, **item} for key, item in raw.items()]
        else:
            entries = raw
        if dispatch_mode not in {'direct', 'gateway'} or dispatch_mode == 'gateway' and not profile:
            return profile or 'unbound', None
        matches = [item for item in entries if isinstance(item, dict) and item.get("provider_code") == provider
            and item.get("model") == model and (not profile or item.get("profile") == profile)
            and (dispatch_mode == 'gateway' or
                 str(item.get("api_endpoint", "")).rstrip("/").removesuffix("/chat/completions")
                 == str(endpoint or "").rstrip("/").removesuffix("/chat/completions"))]
        if len(matches) != 1:
            return profile or "unbound", None
        item = matches[0]
        value = BudgetCapability.model_validate(item["context_budget"]) if item.get("context_budget") else None
        if provider == 'strata' and model == 'qwen3.6-35b-a3b':
            from .strata_handoff import configured_root, load_handoff
            root = configured_root()
            if root:
                expected = load_handoff(root).capability(item['profile'])
                if value is not None and value != expected:
                    return item['profile'], None
                value = expected
        return item["profile"], value
    except (ValueError, TypeError, KeyError, AttributeError):
        return profile or "unbound", None


def client_probe(client, prompt: str, **kwargs) -> BudgetVerdict | None:
    """由实际包装器公开计量边界，保留隐私变换，不越过未知包装器猜测payload。"""
    from .exam_result_model_route import _unwrap
    base, _ = _unwrap(client)
    provider = getattr(base, "provider_code", None)
    if split_enabled() and not strict_enabled() and provider in LOCAL:
        return BudgetVerdict("CAPABILITY_UNVERIFIED", "split_requires_strict_budget", "unbound", str(getattr(base, "model", "")))
    method = getattr(client, "probe_context_budget", None)
    if callable(method):
        result = method(prompt, **kwargs)
        if result is not None:
            return result
    if split_enabled() and provider in LOCAL:
        return BudgetVerdict("CAPABILITY_UNVERIFIED", "client_probe_unavailable", "unbound", str(getattr(base, "model", "")))
    return None
