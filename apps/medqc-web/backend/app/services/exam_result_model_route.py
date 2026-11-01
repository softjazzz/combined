"""06-01-04应用层双模型实验；只调度请求、分区冻结及观测，不判断临床结果。"""

from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import asdict, dataclass, field, replace
import hashlib
import json
import logging
import math
import re
from typing import Any, Iterator

from ..core.settings import get_settings
from .llm_dispatch.provider_profiles import (
    ProviderConfigurationError, configured_gateway_profile, validate_gateway_profile,
)
from .llm_experiment import _validated_namespace, current_llm_experiment_namespace, llm_experiment_scope
from .llm_observability import current_llm_observation_context


logger = logging.getLogger(__name__)
RULE_ID = "LX0609-06-01-04"
ROUTE_VERSION = "exam-result-local-cascade-v1"
_LABEL = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:/-]{0,127}\Z")


@dataclass(frozen=True)
class RoutePolicy:
    mode: str
    experiment: str
    candidate_profile: str
    candidate_model: str
    candidate_revision: str
    reference_revision: str
    candidate_parameters: dict[str, float] = field(default_factory=dict)


def route_policy() -> RoutePolicy | None:
    settings = get_settings()
    raw = getattr(settings, "LLM_EXAM_RESULT_ROUTING", {})
    if not isinstance(raw, dict):
        raise ProviderConfigurationError("invalid exam-result route configuration")
    mode = raw.get("mode", "off")
    if not isinstance(mode, str):
        raise ProviderConfigurationError("invalid exam-result route mode")
    if mode == "off":
        return None
    if getattr(settings, "STRATA_CASE_CACHE_MODE", "off") == "prefix":
        raise ProviderConfigurationError("dual-model experiment requires the legacy Prompt")
    required = {"mode", "experiment", "candidate_profile", "candidate_model",
                "candidate_revision", "reference_revision"}
    if mode not in {"shadow", "cascade"} or set(raw) - required - {"candidate_parameters"} or required - set(raw):
        raise ProviderConfigurationError("invalid exam-result route configuration")
    for key in required - {"mode", "experiment"}:
        if not isinstance(raw[key], str) or not _LABEL.fullmatch(raw[key]):
            raise ProviderConfigurationError("invalid exam-result route identity")
    experiment = _validated_namespace(raw["experiment"])
    validate_gateway_profile(profile=raw["candidate_profile"], provider_code="local_openai")
    params = raw.get("candidate_parameters", {})
    if not isinstance(params, dict) or set(params) - {"temperature", "top_p"}:
        raise ProviderConfigurationError("unsupported candidate parameters")
    for key, value in params.items():
        if (isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value)
                or not 0 <= value <= (2 if key == "temperature" else 1)):
            raise ProviderConfigurationError("invalid candidate parameters")
    return RoutePolicy(**{**raw, "experiment": experiment, "candidate_parameters": dict(params)})


def route_configuration_identity() -> str | None:
    """在任务接纳阶段绑定配置；off时不改变已有任务身份形状。"""
    policy = route_policy()
    return _digest({"policy": asdict(policy), "version": ROUTE_VERSION}) if policy else None


def _digest(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
                                     allow_nan=False).encode()).hexdigest()


def _unwrap(client: Any) -> tuple[Any, list[Any]]:
    wrappers, seen = [], set()
    while client is not None and id(client) not in seen:
        seen.add(id(client))
        attrs = getattr(client, "__dict__", {})
        inner = attrs.get("delegate") or attrs.get("_inner")
        if inner is None:
            return client, wrappers
        wrappers.append(client)
        client = inner
    raise ProviderConfigurationError("exam-result reference client is unavailable")


@dataclass
class RouteSession:
    policy: RoutePolicy
    reference: Any
    identity: dict[str, Any]
    partition: str
    candidate: Any = None
    reference_only: bool = False

    def selected(self, *, input_complete: bool = True) -> tuple[Any, str]:
        if self.policy.mode == "shadow" or self.reference_only or not input_complete:
            return self.reference, "reference"
        if self.candidate is None:
            self.candidate = build_candidate(self.reference, self.policy)
        return self.candidate, "candidate"

    def upgrade(self) -> bool:
        if self.policy.mode != "cascade" or self.reference_only:
            return False
        self.reference_only = True
        return True

    def observe(self, event: str, **metrics: Any) -> None:
        """字段由调用点固定提供；不记录Prompt、应答、地址、凭据或患者原始坐标。"""
        try:
            record = current_llm_observation_context().record_key_hash
            record = record if isinstance(record, str) and re.fullmatch(r"[a-f0-9]{64}", record) else None
            allowed = {"target", "reason", "state", "expected_pairs", "recorded_pairs", "covered_pairs",
                       "logical_calls", "prompt_tokens", "completion_tokens", "total_tokens",
                       "elapsed_seconds", "budget_used", "freeze_hit", "input_complete"}
            payload = {key: value for key, value in metrics.items() if key in allowed}
            payload.update(event=event, rule_id=RULE_ID, route_version=ROUTE_VERSION,
                           mode=self.policy.mode, record_key_hash=record, partition=self.partition,
                           candidate_model=self.policy.candidate_model,
                           reference_model=(self.identity["model"] if _LABEL.fullmatch(self.identity["model"])
                                            else "unclassified"),
                           planned_target="candidate", experiment=self.policy.experiment)
            logger.info("exam_result_model_route %s", json.dumps(payload, sort_keys=True))
        except Exception:
            # 旁路观测失败不能改变请求、结果、重试或冻结。
            pass


_SESSION: ContextVar[RouteSession | None] = ContextVar("exam_result_model_route", default=None)


def current_route() -> RouteSession | None:
    return _SESSION.get()


@contextmanager
def exam_result_route_scope(reference: Any, rule_ids: Any = (RULE_ID,)) -> Iterator[RouteSession | None]:
    if RULE_ID not in rule_ids:
        yield None
        return
    active = current_route()
    if active is not None:
        yield active
        return
    policy = route_policy()
    if policy is None or reference is None:
        yield None
        return
    raw, _ = _unwrap(reference)
    from .luxian_0609.rule_decision_settings import _luxian_0609_model_identity

    identity = _luxian_0609_model_identity(raw)
    if policy.mode == "cascade" and (identity["provider"] != "strata" or identity["dispatch_mode"] != "gateway"):
        raise ProviderConfigurationError("cascade reference requires an explicit local Strata Gateway profile")
    if policy.mode == "cascade":
        settings = get_settings()
        if configured_gateway_profile(settings, "local_openai", policy.candidate_model) != policy.candidate_profile:
            raise ProviderConfigurationError("candidate Gateway mapping does not match the route policy")
    partition = _digest({"version": ROUTE_VERSION, "policy": asdict(policy), "reference": identity,
                         "outer_experiment": current_llm_experiment_namespace()})
    # 控制目录长度，兼容客户机Windows路径；完整指纹仍保存在任务身份与观测中。
    namespace = policy.experiment[:2] + "-r-" + partition[:24]
    session = RouteSession(policy, reference, identity, partition)
    token = _SESSION.set(session)
    try:
        with llm_experiment_scope(namespace):
            session.observe("scope_started")
            yield session
    finally:
        _SESSION.reset(token)


def build_candidate(reference: Any, policy: RoutePolicy) -> Any:
    """复用正式客户端、Gateway、隐私包装和观测；不会构建直连或云端出口。"""
    from .qc_llm_client import SichuanQCLLMClient
    from .luxian_0609.llm_prompt_privacy import _Luxian0609PrivacyRedactingLLMClient

    raw, wrappers = _unwrap(reference)
    candidate = SichuanQCLLMClient(
        {"provider_code": "local_openai", "model": policy.candidate_model,
         "dispatch_mode": "gateway", "gateway_profile": policy.candidate_profile,
         "model_role": "adjudicator", "allow_mock_when_unconfigured": False,
         "timeout_seconds": getattr(raw, "timeout_seconds", 120),
         "custom_parameters": {"max_tokens": getattr(raw, "max_tokens", SichuanQCLLMClient.DEFAULT_MAX_TOKENS),
                               **policy.candidate_parameters}},
        observability_recorder=getattr(raw, "_observability_recorder", None),
        gateway_dispatch_client=getattr(raw, "_gateway_dispatch_client", None),
    )
    if candidate.gateway_endpoint_sha256 != getattr(raw, "gateway_endpoint_sha256", None):
        raise ProviderConfigurationError("candidate must use the same controlled Gateway")
    for wrapper in reversed(wrappers):
        if isinstance(wrapper, _Luxian0609PrivacyRedactingLLMClient):
            candidate = replace(wrapper, delegate=candidate)
        else:
            # 未知包装可能持有旧冻结；首期不绕过它或复用跨实验应答。
            raise ProviderConfigurationError("unsupported exam-result client wrapper")
    return candidate
