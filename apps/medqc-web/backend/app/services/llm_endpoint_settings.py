"""超级管理员连接配置：独立持久目录、加密密钥、原子版本与脱敏审计。

读取不创建文件；不存在覆盖配置时完全沿用部署配置。Gateway由原部署合同管理。
"""
from contextlib import contextmanager
from contextvars import ContextVar
from copy import deepcopy
from datetime import datetime, timezone
from functools import wraps
import inspect
import ipaddress
import json
import os
from pathlib import Path
import socket
import tempfile
from urllib.parse import urlsplit

from cryptography.fernet import Fernet
from pydantic import BaseModel, ConfigDict, Field, SecretStr, ValidationError, ValidationInfo, field_validator

from ..core.http import (
    _BLOCKED_LOOPBACK_HOSTS,
    _BLOCKED_METADATA_HOSTS,
    is_unsafe_ssrf_ip,
    parse_ip_literal,
)
from .llm_dispatch.provider_profiles import ProviderConfigurationError

PROVIDERS = {
    "alibaba": ("阿里云百炼", "DASHSCOPE_BASE_URL", "DASHSCOPE_API_KEY"),
    "deepseek": ("DeepSeek", "DEEPSEEK_API_ENDPOINT", "DEEPSEEK_API_KEY"),
    "siliconflow": ("SiliconFlow", "SILICONFLOW_API_ENDPOINT", "SILICONFLOW_API_KEY"),
    "ollama": ("本地 OpenAI 兼容服务 / Ollama", "OLLAMA_API_ENDPOINT", "OLLAMA_API_KEY"),
}
_LOCAL_INTRANET_PROVIDERS = frozenset({"ollama"})
_RFC1918_NETWORKS = (
    ipaddress.IPv4Network("10.0.0.0/8"),
    ipaddress.IPv4Network("172.16.0.0/12"),
    ipaddress.IPv4Network("192.168.0.0/16"),
)
_ALIBABA_METADATA_IP = ipaddress.IPv4Address("100.100.100.200")
_OLLAMA_LOCAL_LOOPBACK_HOSTS = frozenset({"localhost", "ip6-localhost", "ip6-loopback"})
_HOST_NOT_ALLOWED_CODE = "llm_endpoint_host_not_allowed"
_CONFIG_INVALID_CODE = "llm_endpoint_configuration_invalid"
_SNAPSHOT = ContextVar("llm_endpoint_settings", default=None)


class EndpointSettingsError(ProviderConfigurationError):
    def __init__(self, code, status=503):
        super().__init__(code)
        self.status = status


def _is_outbound_allowlisted(hostname: str) -> bool:
    try:
        from ..core.settings import get_settings

        allow = [
            str(h).strip().lower().rstrip(".")
            for h in (getattr(get_settings(), "OUTBOUND_ALLOWLIST", None) or [])
            if str(h).strip()
        ]
    except Exception:
        allow = []
    host = str(hostname or "").strip().lower().rstrip(".")
    if not host:
        return False
    for entry in allow:
        if host == entry:
            return True
        if "." in entry and parse_ip_literal(entry) is None and host.endswith("." + entry):
            return True
    return False


def _parse_standard_ip_literal(host: str) -> ipaddress.IPv4Address | ipaddress.IPv6Address | None:
    """仅解析标准字面 IP（拒绝整数/八进制/十六进制混淆及 zone ID）。"""
    candidate = str(host or "").strip()
    if candidate.startswith("[") and candidate.endswith("]"):
        candidate = candidate[1:-1]
    if not candidate or "%" in candidate:
        return None
    try:
        return ipaddress.ip_address(candidate)
    except ValueError:
        return None


def _is_ollama_allowed_private_ip(ip_obj: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    """本地 Ollama 允许标准回环与 RFC1918 院内私网段，但始终阻断云元数据/link-local/0.0.0.0/保留段/IPv4-mapped 混淆。"""
    if isinstance(ip_obj, ipaddress.IPv6Address):
        if ip_obj.ipv4_mapped is not None:
            return False
        return ip_obj == ipaddress.IPv6Address("::1")
    if ip_obj == _ALIBABA_METADATA_IP:
        return False
    if ip_obj.is_link_local or ip_obj.is_unspecified or ip_obj.is_multicast or ip_obj.is_reserved:
        return False
    if ip_obj.is_loopback:
        return True
    return any(ip_obj in net for net in _RFC1918_NETWORKS)


def _is_unsafe_endpoint_host(hostname: str, *, allow_local_intranet: bool = False) -> bool:
    """拒绝云元数据、link-local、保留段与未授权内网地址；仅对显式本地 Ollama 放行本机回环及 RFC1918 院内网段。"""
    host = str(hostname or "").strip().lower()
    stripped = host.rstrip(".")
    if not stripped:
        return True
    if stripped in _BLOCKED_METADATA_HOSTS:
        return True
    if _is_outbound_allowlisted(stripped):
        return False
    if stripped in _BLOCKED_LOOPBACK_HOSTS or stripped.endswith(".localhost"):
        if allow_local_intranet and stripped in _OLLAMA_LOCAL_LOOPBACK_HOSTS:
            return False
        return True
    literal_ip = parse_ip_literal(host)
    if literal_ip is not None:
        if allow_local_intranet:
            standard_ip = _parse_standard_ip_literal(host)
            if standard_ip is not None and _is_ollama_allowed_private_ip(standard_ip):
                return False
        return is_unsafe_ssrf_ip(literal_ip)
    try:
        infos = socket.getaddrinfo(stripped, None)
    except OSError:
        # 离线单测域名（如 new.test）无法解析时不误杀，实际外呼由 core/http.py 二次拦截
        return False
    for _family, _, _, _, sockaddr in infos:
        ip_obj = parse_ip_literal(sockaddr[0])
        if ip_obj is None:
            return True
        if allow_local_intranet and _is_ollama_allowed_private_ip(ip_obj):
            continue
        if is_unsafe_ssrf_ip(ip_obj):
            return True
    return False


def _sanitize_endpoint_syntax(value: str) -> tuple[str, str]:
    """校验 HTTP(S) 基础格式并拒绝凭据、查询参数、片段与控制字符。"""
    cleaned = str(value or "").strip().rstrip("/")
    if not cleaned:
        return "", ""
    try:
        parsed = urlsplit(cleaned)
        valid = bool(
            parsed.scheme in {"http", "https"}
            and parsed.hostname
            and not parsed.username
            and not parsed.password
            and not parsed.query
            and not parsed.fragment
            and parsed.port != 0
            and not any(ch.isspace() or ord(ch) < 32 for ch in cleaned)
        )
    except ValueError:
        valid = False
    if not valid:
        raise ValueError(_CONFIG_INVALID_CODE)
    return cleaned, str(parsed.hostname)


def validate_endpoint_value(value: str, *, provider: str | None = None) -> str:
    cleaned, hostname = _sanitize_endpoint_syntax(value)
    if not cleaned:
        return ""
    allow_local_intranet = str(provider or "").strip().lower() in _LOCAL_INTRANET_PROVIDERS
    if _is_unsafe_endpoint_host(hostname, allow_local_intranet=allow_local_intranet):
        raise ValueError(_HOST_NOT_ALLOWED_CODE)
    return cleaned


def classify_validation_error(exc: ValidationError) -> str:
    """将 Pydantic 校验错误归类为安全错误码，绝不回显原始输入或密钥。"""
    for err in exc.errors():
        msg = str(err.get("msg") or "")
        if _HOST_NOT_ALLOWED_CODE in msg:
            return _HOST_NOT_ALLOWED_CODE
    return _CONFIG_INVALID_CODE


def _endpoint_origin(value: str) -> tuple[str, str, int | None]:
    parsed = urlsplit(value.strip().rstrip("/"))
    scheme = (parsed.scheme or "").lower()
    host = (parsed.hostname or "").lower()
    port = parsed.port
    if port is None:
        if scheme == "http":
            port = 80
        elif scheme == "https":
            port = 443
    return (scheme, host, port)


class EndpointUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    version: int = Field(ge=0)
    use_deployment: bool = False
    enabled: bool = False
    endpoint: str = Field(default="", max_length=2048)
    api_key: SecretStr | None = Field(default=None, max_length=8192)
    clear_key: bool = False

    @field_validator("endpoint")
    @classmethod
    def valid_endpoint(cls, value, info: ValidationInfo):
        provider = info.context.get("provider") if isinstance(info.context, dict) else None
        return validate_endpoint_value(value, provider=provider)


def directory():
    configured = os.getenv("LLM_ENDPOINT_CONFIG_DIR", "").strip()
    if configured:
        return Path(configured)
    from ..core.settings import get_settings
    settings = get_settings()
    configured = str(getattr(settings, "LLM_ENDPOINT_CONFIG_DIR", "") or "").strip()
    if configured:
        return Path(configured)
    dispatch = str(getattr(settings, "QC_DISPATCH_STATE_DIR", "") or "").strip()
    root = Path(dispatch).parent if dispatch else Path(__file__).resolve().parents[2] / "data"
    return root / "llm-endpoints"


def _read():
    path = directory() / "settings.json"
    if not path.exists():
        return {"version": 0, "providers": {}, "audit": []}
    try:
        if path.is_symlink():
            raise ValueError()
        data = json.loads(path.read_text(encoding="utf-8"))
        if (type(data.get("version")) is not int or data["version"] < 0
                or not isinstance(data.get("providers"), dict)
                or set(data["providers"]) - set(PROVIDERS)
                or not isinstance(data.get("audit"), list)):
            raise ValueError()
        for code, row in data["providers"].items():
            if (type(row.get("enabled")) is not bool or type(row.get("revision")) is not int
                    or not isinstance(row.get("key_ciphertext"), str)
                    or validate_endpoint_value(row["endpoint"], provider=code) != row["endpoint"]):
                raise ValueError()
        return data
    except Exception:
        raise EndpointSettingsError("llm_endpoint_configuration_unavailable") from None


def snapshot():
    pinned = _SNAPSHOT.get()
    return deepcopy(pinned if pinned is not None else _read())


@contextmanager
def scope(state):
    token = _SNAPSHOT.set(state)
    try:
        yield
    finally:
        _SNAPSHOT.reset(token)


def pinned_runtime(operation):
    """裁决及分角色构造共用默认客户端已经取得的连接快照。"""
    signature = inspect.signature(operation)
    @wraps(operation)
    def invoke(*args, **kwargs):
        bound = signature.bind_partial(*args, **kwargs)
        base = next(iter(bound.arguments.values()), None) or {}
        state = base.get("endpoint_settings_snapshot")
        with scope(state if state is not None else snapshot()):
            return operation(*args, **kwargs)
    return invoke


def _cipher(create=False):
    path = directory() / "key"
    try:
        if path.is_symlink():
            raise ValueError()
        if create and not path.exists():
            fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(fd, "wb") as handle:
                handle.write(Fernet.generate_key())
                handle.flush()
                os.fsync(handle.fileno())
        if os.name != "nt" and path.stat().st_mode & 0o077:
            raise ValueError()
        return Fernet(path.read_bytes())
    except Exception:
        raise EndpointSettingsError("llm_endpoint_encryption_key_unavailable") from None


def _decrypt(value):
    if not value:
        return None
    try:
        return _cipher().decrypt(value.encode()).decode()
    except Exception:
        raise EndpointSettingsError("llm_endpoint_secret_unavailable") from None


@contextmanager
def _locked():
    root = directory()
    root.mkdir(mode=0o700, parents=True, exist_ok=True)
    path = root / "write.lock"
    if root.is_symlink() or path.is_symlink():
        raise EndpointSettingsError("llm_endpoint_storage_invalid")
    fd = os.open(path, os.O_RDWR | os.O_CREAT, 0o600)
    with os.fdopen(fd, "r+b") as lock:
        if os.name == "nt":
            import msvcrt
            lock.seek(0)
            msvcrt.locking(lock.fileno(), msvcrt.LK_LOCK, 1)
        else:
            import fcntl
            fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            if os.name == "nt":
                lock.seek(0)
                msvcrt.locking(lock.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(lock.fileno(), fcntl.LOCK_UN)


def save(provider, proposed, actor, settings):
    if provider not in PROVIDERS:
        raise EndpointSettingsError("llm_endpoint_provider_unsupported", 422)
    if not proposed.use_deployment and proposed.endpoint:
        try:
            validate_endpoint_value(proposed.endpoint, provider=provider)
        except ValueError as exc:
            code = _HOST_NOT_ALLOWED_CODE if _HOST_NOT_ALLOWED_CODE in str(exc) else _CONFIG_INVALID_CODE
            raise EndpointSettingsError(code, 422) from None
    # Gateway调用使用自己的URL、令牌及profile，不允许保存一个实际不会生效的直连地址。
    if getattr(settings, "LLM_DISPATCH_MODE", "direct") != "direct":
        raise EndpointSettingsError("llm_endpoint_gateway_deployment_managed", 409)
    with _locked():
        current = _read()
        if current["version"] != proposed.version:
            raise EndpointSettingsError("llm_endpoint_configuration_changed", 409)
        version = current["version"] + 1
        key = proposed.api_key.get_secret_value() if proposed.api_key else ""
        if key and proposed.clear_key:
            raise EndpointSettingsError("llm_endpoint_key_action_conflict", 422)
        if proposed.use_deployment:
            current["providers"].pop(provider, None)
        else:
            old = current["providers"].get(provider)
            cipher = old["key_ciphertext"] if old else ""
            dep_endpoint, dep_key = deployment_values(provider, settings)
            previous_endpoint = old["endpoint"] if old else (dep_endpoint or "")
            had_previous_key = bool(cipher) if old else bool(dep_key)
            endpoint_origin_changed = bool(proposed.endpoint) and (
                not previous_endpoint
                or _endpoint_origin(previous_endpoint) != _endpoint_origin(proposed.endpoint)
            )
            if had_previous_key and not key and not proposed.clear_key and endpoint_origin_changed:
                # 无论首次编辑还是后续编辑，只要更换端点主机/端口且存在旧密钥，必须显式重新确认密钥或清除密钥。
                raise EndpointSettingsError("llm_endpoint_key_reconfirmation_required", 422)
            if not old and not key and not proposed.clear_key:
                # 同源首次编辑留空，沿用原有效部署密钥；之后同源留空保留已保存密钥。
                key = dep_key or ""
            if key:
                cipher = _cipher(create=True).encrypt(key.encode()).decode()
            if proposed.clear_key:
                cipher = ""
            if proposed.enabled and (not proposed.endpoint or (provider != "ollama" and not cipher)):
                raise EndpointSettingsError("llm_endpoint_configuration_incomplete", 422)
            current["providers"][provider] = dict(enabled=proposed.enabled,
                endpoint=proposed.endpoint, key_ciphertext=cipher, revision=version)
        current["version"] = version
        current["audit"].append(dict(version=version, provider=provider, actor=actor,
            at=datetime.now(timezone.utc).isoformat(), action="deployment" if proposed.use_deployment else "save",
            enabled=None if proposed.use_deployment else proposed.enabled,
            key_action="clear" if proposed.clear_key else "replace" if key else "keep"))
        fd, name = tempfile.mkstemp(prefix="settings-", dir=directory())
        try:
            with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
                json.dump(current, handle, ensure_ascii=False)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(name, directory() / "settings.json")
        finally:
            if os.path.exists(name):
                os.unlink(name)
    return current


def deployment_values(provider, settings):
    _, endpoint_field, key_field = PROVIDERS[provider]
    endpoint = getattr(settings, endpoint_field, None)
    key = getattr(settings, key_field, None)
    if provider == str(getattr(settings, "LLM_DEFAULT_PROVIDER", "")):
        endpoint = endpoint or getattr(settings, "LLM_API_ENDPOINT", None)
        key = key or getattr(settings, "LLM_API_KEY", None)
    return str(endpoint or ""), key


def enabled_codes(deployed, state=None):
    rows = (state if state is not None else snapshot())["providers"]
    return tuple(dict.fromkeys([code for code in deployed if code not in rows or rows[code]["enabled"]]
        + [code for code, row in rows.items() if row["enabled"]]))


def apply(runtime, state):
    row = state["providers"].get(runtime["provider_code"])
    if row:
        if not row["enabled"]:
            raise EndpointSettingsError("llm_endpoint_provider_disabled")
        if runtime["dispatch_mode"] != "direct":
            raise EndpointSettingsError("llm_endpoint_gateway_deployment_managed")
        runtime.update(api_endpoint=row["endpoint"], api_key=_decrypt(row["key_ciphertext"]),
                       endpoint_config_revision=row["revision"], allow_mock_when_unconfigured=False)
    runtime["endpoint_settings_snapshot"] = deepcopy(state)
    return runtime


def public_view(settings, deployed):
    state = _read()
    rows = []
    for code, (name, _, _) in PROVIDERS.items():
        saved = state["providers"].get(code)
        endpoint, key = deployment_values(code, settings)
        try:
            endpoint, _ = _sanitize_endpoint_syntax(endpoint)
        except ValueError:
            # 旧部署URL若把令牌塞入query/userinfo，不在管理接口暴露它。
            endpoint = ""
        effective_endpoint = saved["endpoint"] if saved else endpoint
        host_allowed = True
        if effective_endpoint:
            try:
                validate_endpoint_value(effective_endpoint, provider=code)
            except ValueError:
                host_allowed = False
        rows.append(dict(provider_code=code, name=name,
            source="saved" if saved else "deployment",
            endpoint=effective_endpoint,
            enabled=saved["enabled"] if saved else code in deployed,
            key_configured=bool(saved["key_ciphertext"]) if saved else bool(key),
            host_allowed=host_allowed))
    return dict(version=state["version"], providers=rows, audit=state["audit"][-20:],
                editable=getattr(settings, "LLM_DISPATCH_MODE", "direct") == "direct")
