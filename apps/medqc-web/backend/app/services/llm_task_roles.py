"""模型用途配置及调用点绑定；不修改提示词、证据或临床判定。"""

from contextlib import contextmanager
from contextvars import ContextVar
from copy import deepcopy
from functools import wraps
import hashlib
import inspect
import json
from types import SimpleNamespace

from .llm_dispatch.provider_profiles import ProviderConfigurationError


TASK_ROLES_KEY = "task_role_models"
TASK_ROLES = ("fact_extraction", "judgment_analysis", "specialty_verification")
ROUTING_VERSION = "qc-task-roles-v1"
_PARTITION: ContextVar[str | None] = ContextVar("qc_task_role_partition", default=None)


def normalize_task_roles(value):
    """继承用 null；拒绝未知角色、凭据和端点，避免配置串入请求。"""
    if value is None:
        return {role: None for role in TASK_ROLES}
    if not isinstance(value, dict) or set(value) - set(TASK_ROLES):
        raise ProviderConfigurationError("invalid task role configuration")
    result = {}
    for role in TASK_ROLES:
        spec = value.get(role)
        if spec is None:
            result[role] = None
            continue
        if not isinstance(spec, dict) or set(spec) != {"provider_code", "model_code"}:
            raise ProviderConfigurationError("invalid task role model selection")
        provider, model = spec["provider_code"], spec["model_code"]
        if (not isinstance(provider, str) or not provider.strip()
                or not isinstance(model, str) or not model.strip()
                or len(model) > 256 or any(ord(ch) < 32 for ch in model)):
            raise ProviderConfigurationError("invalid task role model identity")
        result[role] = {"provider_code": provider.strip().lower(), "model_code": model.strip()}
    return result


from .llm_endpoint_settings import pinned_runtime


@pinned_runtime
def build_task_role_runtimes(base):
    """一次构造并验证全部显式选型；仅进程内保留部署凭据。"""
    from .llm_config_loader import build_local_model_runtime_config, build_provider_runtime_config

    params = deepcopy(base.get("custom_parameters") or {})
    selections = normalize_task_roles(params.pop(TASK_ROLES_KEY, None))
    if any(spec is not None for spec in selections.values()):
        from .exam_result_model_route import route_policy

        if route_policy() is not None:
            raise ProviderConfigurationError("task role conflicts with exam experiment routing")
    runtimes = {}
    for role, spec in selections.items():
        if spec is None:
            continue
        provider = spec["provider_code"]
        if provider in {"strata", "ollama"}:
            runtime = build_local_model_runtime_config(provider, spec["model_code"], params)
        else:
            runtime = build_provider_runtime_config(provider, spec["model_code"], params)
            if not runtime.get("api_endpoint") or (
                runtime.get("dispatch_mode") != "gateway" and not runtime.get("api_key")
            ):
                raise ProviderConfigurationError("task role provider is not configured")
        # 本地病历不能因角色设置意外外发；跨本地服务切换仍须显式选择。
        if base.get("provider_code") in {"strata", "ollama"} and provider not in {"strata", "ollama"}:
            raise ProviderConfigurationError("local task roles cannot route to cloud")
        if runtime.get("dispatch_mode") == "gateway":
            from .llm_config_loader import get_settings
            from .llm_dispatch.client import GatewayDispatchClient, GatewayDispatchError

            settings = get_settings()
            endpoint_hash = hashlib.sha256(str(settings.LLM_GATEWAY_URL or "").strip().rstrip("/").encode()).hexdigest()
            try:
                GatewayDispatchClient._connection_settings(
                    expected_profile=runtime["gateway_profile"], expected_endpoint_sha256=endpoint_hash,
                    provider_code=provider, model_code=runtime["model"],
                )
            except GatewayDispatchError as exc:
                raise ProviderConfigurationError("task role gateway is not configured") from exc
            runtime["gateway_endpoint_sha256"] = endpoint_hash
        runtime.update(model_role=role, source="task_role_configuration", allow_mock_when_unconfigured=False)
        runtimes[role] = runtime
    return selections, runtimes


def task_role_identity(runtimes, base):
    """只暴露有效模型/参数和地址指纹；不把凭据或URL写入任务和冻结。"""
    if not runtimes and TASK_ROLES_KEY not in (base.get("custom_parameters") or {}):
        return None
    from .llm_config_loader import get_settings
    from .luxian_0609.llm_role_routing import parse_role_models

    legacy_routes = parse_role_models(getattr(get_settings(), "LLM_ROLE_MODELS", None))
    roles = {}
    for role, runtime in sorted({"default": base, **runtimes}.items()):
        from .llm_token_budget import freeze_identity
        from .strata_protocol import deployed_protocol

        protocol = runtime.get("strata_protocol") or deployed_protocol(
            runtime["provider_code"], runtime["model"], runtime.get("gateway_profile"), runtime.get("api_endpoint"))
        probe = SimpleNamespace(**{key: runtime.get(key) for key in (
            "provider_code", "model", "api_endpoint", "gateway_profile")},
            dispatch_mode=runtime.get("dispatch_mode", "direct"), strata_protocol=protocol)
        roles[role] = {
            **({"endpoint_config_revision": runtime["endpoint_config_revision"]} if runtime.get("endpoint_config_revision") else {}),
            "provider": runtime["provider_code"], "model": runtime["model"],
            "endpoint_sha256": hashlib.sha256(str(runtime.get("api_endpoint") or "").encode()).hexdigest(),
            "dispatch_mode": runtime.get("dispatch_mode", "direct"),
            "gateway_profile": runtime.get("gateway_profile"),
            "gateway_endpoint_sha256": runtime.get("gateway_endpoint_sha256"),
            "context_identity": freeze_identity(probe),
            "inference_parameters": {
                key: (runtime.get("custom_parameters") or {}).get(key)
                for key in ("temperature", "top_p", "top_k", "presence_penalty", "frequency_penalty",
                            "repetition_penalty", "max_tokens", "enable_thinking", "thinking_budget", "reasoning_effort")
            },
        }
    return {"version": ROUTING_VERSION, "roles": roles, "legacy_callpoint_models": legacy_routes}


def client_for_task(llm_client, role):
    if role not in TASK_ROLES:
        raise ProviderConfigurationError("unknown model task role")
    selector = getattr(llm_client, "for_task_role", None)
    return selector(role) if callable(selector) else llm_client


def current_task_role_partition():
    return _PARTITION.get()


def _identity(client):
    seen = set()
    while client is not None and id(client) not in seen:
        seen.add(id(client))
        # 复用任务有效身份，同时覆盖默认云端、分角色及旧调用点路由。
        from .luxian_0609.rule_decision_settings import _luxian_0609_model_identity
        if isinstance(getattr(client, "provider_code", None), str) and isinstance(getattr(client, "model", None), str):
            # 已有模型身份却不完整时应明确失败，不能落回未分区的旧冻结。
            return {"default_model": _luxian_0609_model_identity(client)}
        identity = getattr(client, "task_role_identity", None)
        if isinstance(identity, dict):
            return identity
        attrs = getattr(client, "__dict__", {})
        client = attrs.get("delegate") or attrs.get("_inner")
    return None


@contextmanager
def task_role_scope(client):
    identity = _identity(client)
    partition = hashlib.sha256(json.dumps(identity, sort_keys=True, ensure_ascii=False).encode()).hexdigest() if identity else _PARTITION.get()
    token = _PARTITION.set(partition)
    try:
        yield
    finally:
        _PARTITION.reset(token)


def task_role_call(role):
    """在真实函数边界绑定用途，覆盖模型调用前的外层冻结读取。"""
    def decorate(operation):
        signature = inspect.signature(operation)

        @wraps(operation)
        async def invoke(*args, **kwargs):
            bound = signature.bind(*args, **kwargs)
            client = bound.arguments.get("llm_client")
            with task_role_scope(client):
                bound.arguments["llm_client"] = client_for_task(client, role)
                return await operation(*bound.args, **bound.kwargs)
        return invoke
    return decorate
