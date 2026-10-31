"""LLM Gateway 的独立、失败关闭配置。"""

from __future__ import annotations

from dataclasses import dataclass, field
import json
import os
from pathlib import Path
import re
from typing import Any, Mapping
from urllib.parse import urlsplit, urlunsplit


_PROFILE_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,63}$")
_RESOURCE_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,63}$")
_SUPPORTED_PROVIDERS = frozenset(
    {"strata", "alibaba", "bailian", "deepseek", "siliconflow", "ollama", "openai_compatible"}
)


class GatewayConfigurationError(RuntimeError):
    """启动配置不安全或不完整。

    异常文本只使用固定描述，避免在启动日志中泄露端点或密钥。
    """


@dataclass(frozen=True, slots=True)
class ResourceConfig:
    resource_id: str
    max_inflight: int = 2
    max_queue: int = 4


@dataclass(frozen=True, slots=True)
class ProfileConfig:
    name: str
    resource_id: str
    provider_code: str
    model: str
    api_endpoint: str
    api_key: str | None = None


@dataclass(frozen=True, slots=True)
class CaseContinuationConfig:
    enabled: bool = True
    burst_requests: int = 4
    turn_seconds: float = 30.0
    fair_wait_seconds: float = 30.0
    idle_grace_seconds: float = 0.05

    def __post_init__(self):
        if type(self.enabled) is not bool:
            raise GatewayConfigurationError("case continuation enabled must be boolean")
        _positive_int(self.burst_requests, "case burst", 64)
        for name, value, maximum in (("turn_seconds", self.turn_seconds, 300),
                                     ("fair_wait_seconds", self.fair_wait_seconds, 300),
                                     ("idle_grace_seconds", self.idle_grace_seconds, 1)):
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise GatewayConfigurationError("case continuation duration must be numeric")
            normalized = _parse_bounded_float(value, name=name,
                minimum=0 if name == "idle_grace_seconds" else 0.01, maximum=maximum)
            object.__setattr__(self, name, normalized)
        if self.idle_grace_seconds > min(self.turn_seconds, self.fair_wait_seconds):
            raise GatewayConfigurationError("case idle grace exceeds fairness budget")


@dataclass(frozen=True, slots=True)
class GatewaySettings:
    token: str
    resources: dict[str, ResourceConfig]
    profiles: dict[str, ProfileConfig]
    allowed_hosts: frozenset[str]
    state_dir: Path
    startup_isolation_seconds: float = 30.0
    shutdown_grace_seconds: float = 30.0
    cache_enabled: bool = False
    cache_deployment_version: str | None = None
    cache_ttl_seconds: float = 60.0
    cache_max_entries: int = 64
    strata_case_sequential: bool = True
    continuation: CaseContinuationConfig = field(default_factory=CaseContinuationConfig)

    def __post_init__(self) -> None:
        if not isinstance(self.continuation, CaseContinuationConfig):
            raise GatewayConfigurationError("invalid case continuation configuration")
        if type(self.strata_case_sequential) is not bool:
            raise GatewayConfigurationError("strata_case_sequential must be boolean")
        if type(self.cache_enabled) is not bool:
            raise GatewayConfigurationError("cache_enabled must be boolean")
        if self.cache_enabled and (
            not isinstance(self.cache_deployment_version, str)
            or not _PROFILE_RE.fullmatch(self.cache_deployment_version)
        ):
            raise GatewayConfigurationError("cache deployment version is required")
        _parse_bounded_float(self.cache_ttl_seconds, name="cache ttl", minimum=1, maximum=3600)
        _positive_int(self.cache_max_entries, "cache_max_entries", 1024)
        if len(self.token) < 32 or self.token.strip() != self.token:
            raise GatewayConfigurationError("LLM Gateway token is not safely configured")
        if not self.resources or not self.profiles or not self.allowed_hosts:
            raise GatewayConfigurationError("LLM Gateway configuration is incomplete")
        local_profiles = [profile for profile in self.profiles.values() if profile.provider_code == "strata"]
        if len({profile.resource_id for profile in local_profiles}) > 1 or len({profile.api_endpoint for profile in local_profiles}) > 1:
            raise GatewayConfigurationError("Strata profiles must share one physical resource and API endpoint")
        for name, profile in self.profiles.items():
            if name != profile.name or not _PROFILE_RE.fullmatch(name):
                raise GatewayConfigurationError("profile configuration has an invalid name")
            resource = self.resources.get(profile.resource_id)
            if resource is None:
                raise GatewayConfigurationError("profile references an unknown resource")
            if profile.provider_code not in _SUPPORTED_PROVIDERS:
                raise GatewayConfigurationError("profile has an unsupported provider")
            if not _profile_matches_provider(profile.name, profile.provider_code):
                raise GatewayConfigurationError("profile name and provider do not match")
            if profile.provider_code not in {"strata", "ollama"} and not profile.api_key:
                raise GatewayConfigurationError("cloud profile API key is required")
            if profile.provider_code == "strata" and resource.max_inflight > 2:
                raise GatewayConfigurationError("Strata resource capacity exceeds the M1 limit")
            if _validated_endpoint(profile.api_endpoint, self.allowed_hosts) != profile.api_endpoint:
                raise GatewayConfigurationError("profile endpoint must be normalized")

    @classmethod
    def from_env(cls, environ: Mapping[str, str] | None = None) -> "GatewaySettings":
        env = os.environ if environ is None else environ
        token = str(env.get("LLM_GATEWAY_TOKEN") or "")
        if len(token) < 32 or token.strip() != token:
            raise GatewayConfigurationError("LLM Gateway token is not safely configured")

        resources_raw = _load_json(env, "LLM_GATEWAY_RESOURCES_JSON")
        profiles_raw = _load_json(env, "LLM_GATEWAY_PROFILES_JSON")
        allowed_raw = _load_json(env, "LLM_GATEWAY_ALLOWED_HOSTS")
        resources = _parse_resources(resources_raw)
        allowed_hosts = _parse_allowed_hosts(allowed_raw)
        profiles = _parse_profiles(profiles_raw, resources, allowed_hosts)

        state_dir_value = str(env.get("LLM_GATEWAY_STATE_DIR") or "").strip()
        if not state_dir_value:
            raise GatewayConfigurationError("LLM_GATEWAY_STATE_DIR is required")
        state_dir = Path(state_dir_value)
        startup_isolation_seconds = _parse_bounded_float(
            env.get("LLM_GATEWAY_STARTUP_ISOLATION_SECONDS", "30"),
            name="startup isolation",
            minimum=0,
            maximum=3600,
        )
        shutdown_grace_seconds = _parse_bounded_float(
            env.get("LLM_GATEWAY_SHUTDOWN_GRACE_SECONDS", "30"),
            name="shutdown grace",
            minimum=0.1,
            maximum=3600,
        )
        return cls(
            token=token,
            resources=resources,
            profiles=profiles,
            allowed_hosts=allowed_hosts,
            state_dir=state_dir,
            startup_isolation_seconds=startup_isolation_seconds,
            shutdown_grace_seconds=shutdown_grace_seconds,
            cache_enabled=_parse_cache_enabled(env.get("STRATA_CASE_CACHE_ENABLED", "false")),
            cache_deployment_version=env.get("STRATA_CASE_CACHE_DEPLOYMENT_VERSION"),
            cache_ttl_seconds=_parse_bounded_float(env.get("STRATA_CASE_CACHE_TTL_SECONDS", "60"), name="cache ttl", minimum=1, maximum=3600),
            cache_max_entries=_positive_int_env(env.get("STRATA_CASE_CACHE_MAX_ENTRIES", "64")),
            strata_case_sequential=_parse_case_sequential(env.get("STRATA_CASE_MODEL_SEQUENTIAL", "true")),
            continuation=CaseContinuationConfig(
                enabled=_parse_case_sequential(env.get("STRATA_CASE_CONTINUATION_ENABLED", "true")),
                burst_requests=_positive_int_env(env.get("STRATA_CASE_BURST_REQUESTS", "4")),
                turn_seconds=_parse_bounded_float(env.get("STRATA_CASE_TURN_SECONDS", "30"), name="case turn", minimum=.01, maximum=300),
                fair_wait_seconds=_parse_bounded_float(env.get("STRATA_CASE_FAIR_WAIT_SECONDS", "30"), name="case fair wait", minimum=.01, maximum=300),
                idle_grace_seconds=_parse_bounded_float(env.get("STRATA_CASE_IDLE_GRACE_SECONDS", ".05"), name="case idle grace", minimum=0, maximum=1),
            ),
        )


def _parse_case_sequential(raw):
    if raw not in ("true", "false"):
        raise GatewayConfigurationError("strata_case_sequential must be true or false")
    return raw == "true"


def _parse_cache_enabled(raw):
    if raw not in ("true", "false"):
        raise GatewayConfigurationError("cache_enabled must be true or false")
    return raw == "true"


def _positive_int_env(raw):
    try:
        value = int(raw)
    except (TypeError, ValueError):
        raise GatewayConfigurationError("invalid cache capacity") from None
    return _positive_int(value, "cache capacity", 1024)


def _load_json(env: Mapping[str, str], name: str) -> Any:
    raw = env.get(name)
    if raw is None or not str(raw).strip():
        raise GatewayConfigurationError(f"{name} is required")
    try:
        return json.loads(raw)
    except (TypeError, json.JSONDecodeError) as exc:
        raise GatewayConfigurationError(f"{name} is invalid") from exc


def _named_entries(value: Any, *, id_field: str, config_name: str) -> list[dict[str, Any]]:
    if isinstance(value, dict):
        entries: list[dict[str, Any]] = []
        for key, item in value.items():
            if not isinstance(item, dict):
                raise GatewayConfigurationError(f"{config_name} has an invalid entry")
            copied = dict(item)
            explicit = copied.get(id_field)
            if explicit is not None and explicit != key:
                raise GatewayConfigurationError(f"{config_name} has conflicting identifiers")
            copied[id_field] = key
            entries.append(copied)
        return entries
    if isinstance(value, list) and all(isinstance(item, dict) for item in value):
        return [dict(item) for item in value]
    raise GatewayConfigurationError(f"{config_name} must be an object or list")


def _parse_resources(value: Any) -> dict[str, ResourceConfig]:
    result: dict[str, ResourceConfig] = {}
    for item in _named_entries(value, id_field="resource_id", config_name="resource configuration"):
        allowed = {"resource_id", "max_inflight", "max_queue", "capacity_class"}
        if set(item) - allowed:
            raise GatewayConfigurationError("resource configuration has unsupported fields")
        resource_id = item.get("resource_id")
        if not isinstance(resource_id, str) or not _RESOURCE_RE.fullmatch(resource_id):
            raise GatewayConfigurationError("resource configuration has an invalid identifier")
        if resource_id in result:
            raise GatewayConfigurationError("resource configuration has duplicate identifiers")

        capacity_class = str(item.get("capacity_class") or "strata").strip().lower()
        if capacity_class not in {"strata", "bailian"}:
            raise GatewayConfigurationError("resource configuration has an invalid capacity class")
        default_inflight = 40 if capacity_class == "bailian" else 2
        max_inflight = _positive_int(item.get("max_inflight", default_inflight), "max_inflight", 1000)
        max_queue = _nonnegative_int(item.get("max_queue", 4), "max_queue", 10000)
        result[resource_id] = ResourceConfig(
            resource_id=resource_id,
            max_inflight=max_inflight,
            max_queue=max_queue,
        )
    if not result:
        raise GatewayConfigurationError("at least one resource must be explicitly configured")
    return result


def _parse_allowed_hosts(value: Any) -> frozenset[str]:
    if not isinstance(value, list) or not value:
        raise GatewayConfigurationError("allowed hosts must be a non-empty JSON list")
    result: set[str] = set()
    for raw in value:
        if not isinstance(raw, str):
            raise GatewayConfigurationError("allowed hosts contains an invalid host")
        host = raw.strip().lower()
        if not host or "/" in host or "@" in host or "?" in host or "#" in host:
            raise GatewayConfigurationError("allowed hosts contains an invalid host")
        result.add(host)
    return frozenset(result)


def _parse_profiles(
    value: Any,
    resources: Mapping[str, ResourceConfig],
    allowed_hosts: frozenset[str],
) -> dict[str, ProfileConfig]:
    result: dict[str, ProfileConfig] = {}
    for item in _named_entries(value, id_field="profile", config_name="profile configuration"):
        allowed = {"profile", "resource_id", "provider_code", "model", "api_endpoint", "api_key"}
        if set(item) - allowed:
            raise GatewayConfigurationError("profile configuration has unsupported fields")
        name = item.get("profile")
        resource_id = item.get("resource_id")
        provider_code = item.get("provider_code")
        model = item.get("model")
        endpoint = item.get("api_endpoint")
        api_key = item.get("api_key")
        if not isinstance(name, str) or not _PROFILE_RE.fullmatch(name):
            raise GatewayConfigurationError("profile configuration has an invalid name")
        if name in result:
            raise GatewayConfigurationError("profile configuration has duplicate names")
        if not isinstance(resource_id, str) or resource_id not in resources:
            raise GatewayConfigurationError("profile references an unknown resource")
        if not isinstance(provider_code, str) or provider_code.strip().lower() not in _SUPPORTED_PROVIDERS:
            raise GatewayConfigurationError("profile has an unsupported provider")
        normalized_provider = provider_code.strip().lower()
        if not _profile_matches_provider(name, normalized_provider):
            raise GatewayConfigurationError("profile name and provider do not match")
        if not isinstance(model, str) or not model.strip() or len(model) > 256:
            raise GatewayConfigurationError("profile has an invalid model")
        if api_key is not None and (not isinstance(api_key, str) or not api_key.strip()):
            raise GatewayConfigurationError("profile has an invalid API key")
        if normalized_provider not in {"strata", "ollama"} and not api_key:
            raise GatewayConfigurationError("cloud profile API key is required")
        if normalized_provider == "strata" and resources[resource_id].max_inflight > 2:
            raise GatewayConfigurationError("Strata resource capacity exceeds the M1 limit")
        normalized_endpoint = _validated_endpoint(endpoint, allowed_hosts)
        result[name] = ProfileConfig(
            name=name,
            resource_id=resource_id,
            provider_code=normalized_provider,
            model=model.strip(),
            api_endpoint=normalized_endpoint,
            api_key=api_key.strip() if api_key is not None else None,
        )
    if not result:
        raise GatewayConfigurationError("at least one profile must be explicitly configured")
    return result


def _profile_matches_provider(profile: str, provider_code: str) -> bool:
    lowered = profile.lower()
    return lowered == provider_code or any(
        lowered.startswith(f"{provider_code}{separator}")
        for separator in ("_", "-", ".")
    )


def _validated_endpoint(value: Any, allowed_hosts: frozenset[str]) -> str:
    if not isinstance(value, str) or not value.strip():
        raise GatewayConfigurationError("profile endpoint is required")
    try:
        parsed = urlsplit(value.strip())
        port = parsed.port
    except ValueError as exc:
        raise GatewayConfigurationError("profile endpoint is invalid") from exc
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise GatewayConfigurationError("profile endpoint is invalid")
    if parsed.username is not None or parsed.password is not None or parsed.query or parsed.fragment:
        raise GatewayConfigurationError("profile endpoint is invalid")
    exact_host = parsed.hostname.lower()
    if port is not None:
        exact_host = f"{exact_host}:{port}"
    if exact_host not in allowed_hosts:
        raise GatewayConfigurationError("profile endpoint host is not allowed")

    path = parsed.path.rstrip("/")
    if not path.endswith("/chat/completions"):
        path = f"{path}/chat/completions" if path else "/chat/completions"
    return urlunsplit((parsed.scheme.lower(), parsed.netloc.lower(), path, "", ""))


def _positive_int(value: Any, name: str, maximum: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0 or value > maximum:
        raise GatewayConfigurationError(f"resource {name} is invalid")
    return value


def _nonnegative_int(value: Any, name: str, maximum: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0 or value > maximum:
        raise GatewayConfigurationError(f"resource {name} is invalid")
    return value


def _parse_bounded_float(value: Any, *, name: str, minimum: float, maximum: float) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError) as exc:
        raise GatewayConfigurationError(f"{name} is invalid") from exc
    if not minimum <= parsed <= maximum:
        raise GatewayConfigurationError(f"{name} is invalid")
    return parsed


__all__ = [
    "GatewayConfigurationError",
    "GatewaySettings",
    "ProfileConfig",
    "ResourceConfig",
]
