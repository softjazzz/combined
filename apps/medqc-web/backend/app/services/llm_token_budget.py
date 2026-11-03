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
from functools import wraps
from typing import Callable, Literal

from pydantic import BaseModel, ConfigDict, Field

from .llm_dispatch.provider_profiles import ProviderConfigurationError
from .llm_context_contract import CONTEXT_REASON_CODES, CONTEXT_FAILURE_REASON_CODES

logger = logging.getLogger(__name__)
LOCAL = frozenset({"strata", "ollama", "local_openai"})
PROTOCOL = "lx0609-token-batches-p5b-v1"


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
    verified: bool = False
    thinking_semantics: Literal["unknown", "included_in_max_output"] = "unknown"


@dataclass(frozen=True)
class CounterIdentity:
    model: str
    model_revision: str
    tokenizer_id: str
    tokenizer_revision: str
    chat_template_id: str
    chat_template_revision: str


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


class BudgetError(ProviderConfigurationError):
    retryable = False
    status_code = 400

    def __init__(self, verdict: BudgetVerdict):
        self.verdict = verdict
        self.code = CONTEXT_REASON_CODES.get(verdict.status, CONTEXT_REASON_CODES["BUDGET_EXHAUSTED"])
        super().__init__(self.code)


# 由未来DSH部署适配器显式注册真实计量实现；本轮不提供字符估算或伪分词器。
_COUNTERS: dict[tuple[str, str], tuple[CounterIdentity, Callable[[dict], int]]] = {}
_FAILURES = ContextVar("llm_context_budget_failures", default=None)
_FREEZE_IDENTITY = ContextVar("llm_context_freeze_identity", default=None)


def freeze_identity(client) -> str | None:
    if client is None or not (strict_enabled() or split_enabled()):
        return None
    from .exam_result_model_route import _unwrap
    base, _ = _unwrap(client)
    provider = getattr(base, "provider_code", "")
    if provider not in LOCAL or not (strict_enabled() or split_enabled()):
        return None
    model = str(getattr(base, "model", ""))
    profile, cap = deployed_capability(provider, model, getattr(base, "gateway_profile", None), getattr(base, "api_endpoint", None))
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
    return json.dumps({"protocol": PROTOCOL, "provider": provider, "model": model, "profile": profile,
        "route_capabilities": route_capabilities,
        "capability": cap.model_dump() if cap else None, "strict": strict_enabled(), "split": split_enabled()}, sort_keys=True)


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
    failures = []
    token = _FAILURES.set(failures)
    try:
        yield failures
    finally:
        _FAILURES.reset(token)


def context_budget_failed() -> bool:
    return bool(_FAILURES.get())


def budget_guarded_executor(function):
    """非检查族旧catch可能吞掉配置异常；执行器边界关闭该族，不改临床状态所有者。"""
    @wraps(function)
    async def run(*args, **kwargs):
        failures = []
        token = _FAILURES.set(failures)
        escaped = None
        try:
            with token_freeze_scope(kwargs.get("llm_client")):
                result = await function(*args, **kwargs)
            if failures:
                raise failures[0]
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
    if (name, revision) in _COUNTERS or not callable(counter):
        raise ValueError("counter identity already registered or invalid")
    _COUNTERS[name, revision] = (identity, counter)


@contextmanager
def counter_scope(name: str, revision: str, identity: CounterIdentity, counter: Callable[[dict], int]):
    """固定应答验收/部署装配的独立生命周期，不把Mock能力写入配置。"""
    register_counter(name, revision, identity, counter)
    try:
        yield
    finally:
        _COUNTERS.pop((name, revision), None)


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
    thinking_values = [value for value in (payload.get("thinking_budget"),
        (payload.get("chat_template_kwargs") or {}).get("thinking_budget")) if value is not None]
    if any(type(thinking) is not int or thinking < 0 or thinking > reserve for thinking in thinking_values):
        return verdict("CAPABILITY_UNVERIFIED", "thinking_output_semantics_unverified", **metadata)
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


def deployed_capability(provider: str, model: str, profile: str | None, endpoint: str | None) -> tuple[str, BudgetCapability | None]:
    """复用既有Gateway部署Profile目录，直接HTTP也须绑定同一真实部署身份。"""
    try:
        raw = json.loads(os.getenv("LLM_GATEWAY_PROFILES_JSON", "[]"))
        if isinstance(raw, dict):
            entries = [{"profile": key, **item} for key, item in raw.items()]
        else:
            entries = raw
        matches = [item for item in entries if isinstance(item, dict) and item.get("provider_code") == provider
            and item.get("model") == model and (not profile or item.get("profile") == profile)
            and str(item.get("api_endpoint", "")).rstrip("/").removesuffix("/chat/completions")
                == str(endpoint or "").rstrip("/").removesuffix("/chat/completions")]
        if len(matches) != 1:
            return profile or "unbound", None
        item = matches[0]
        value = BudgetCapability.model_validate(item["context_budget"]) if item.get("context_budget") else None
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
