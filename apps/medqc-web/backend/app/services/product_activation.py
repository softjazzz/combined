"""本地离线产品激活。

激活码由发行方使用 Ed25519 私钥签发，客户机只保存公钥并在本地验签。
本模块是产品授权的唯一业务所有者；不联网、不访问数据库，也不把完整激活码
返回给前端状态接口。
"""

from __future__ import annotations

import base64
import binascii
import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Mapping

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)
from fastapi import Depends, HTTPException, status

from ..core.security import get_current_user
from ..core.settings import Settings, get_settings


ACTIVATION_PREFIX = "MQ1"
ACTIVATION_PRODUCT = "medqc-web-customer"
ACTIVATION_SCHEMA_VERSION = "1"
_PAYLOAD_FIELDS = frozenset(
    {"version", "product", "customer", "edition", "serial", "issued_at", "expires_at"}
)
_TEXT_LIMITS = {
    "customer": 160,
    "edition": 80,
    "serial": 160,
}


class ProductActivationError(ValueError):
    """激活码或本地授权状态不合法。消息不包含原码、签名或私钥。"""

    def __init__(self, message: str, *, code: str = "invalid") -> None:
        super().__init__(message)
        self.code = code


def _b64url_encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def _b64url_decode(value: str, *, field: str) -> bytes:
    if not value or len(value) > 16384 or any(char not in "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_" for char in value):
        raise ProductActivationError(f"激活码{field}编码无效")
    try:
        return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))
    except (ValueError, binascii.Error) as exc:
        raise ProductActivationError(f"激活码{field}编码无效") from exc


def _utc_iso(value: datetime) -> str:
    return value.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _parse_utc(value: Any, *, field: str) -> datetime:
    if not isinstance(value, str) or not value.strip():
        raise ProductActivationError(f"激活码{field}无效")
    try:
        parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except ValueError as exc:
        raise ProductActivationError(f"激活码{field}无效") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ProductActivationError(f"激活码{field}必须包含时区")
    return parsed.astimezone(timezone.utc)


def _validate_payload(payload: Any, *, now: datetime) -> dict[str, str]:
    if not isinstance(payload, dict):
        raise ProductActivationError("激活码内容无效")
    if set(payload) != _PAYLOAD_FIELDS:
        raise ProductActivationError("激活码字段不完整或包含未知字段")
    if any(not isinstance(value, str) for value in payload.values()):
        raise ProductActivationError("激活码字段类型无效")
    normalized = {key: value.strip() for key, value in payload.items()}
    if normalized["version"] != ACTIVATION_SCHEMA_VERSION:
        raise ProductActivationError("激活码版本不受支持")
    if normalized["product"] != ACTIVATION_PRODUCT:
        raise ProductActivationError("激活码不属于当前产品")
    for field, limit in _TEXT_LIMITS.items():
        if not normalized[field] or len(normalized[field]) > limit:
            raise ProductActivationError(f"激活码{field}无效")
    issued_at = _parse_utc(normalized["issued_at"], field="issued_at")
    expires_at = _parse_utc(normalized["expires_at"], field="expires_at")
    current = now.astimezone(timezone.utc)
    if issued_at > current:
        # 允许小范围时钟偏差，但不接受明显尚未签发的授权。
        if (issued_at - current).total_seconds() > 300:
            raise ProductActivationError("激活码尚未生效", code="not_yet_valid")
    if expires_at <= issued_at:
        raise ProductActivationError("激活码有效期无效")
    if expires_at <= current:
        raise ProductActivationError("激活码已过期", code="expired")
    normalized["issued_at"] = _utc_iso(issued_at)
    normalized["expires_at"] = _utc_iso(expires_at)
    return normalized


def _canonical_payload_bytes(payload: Mapping[str, Any]) -> bytes:
    return json.dumps(
        dict(payload),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def build_activation_code(private_key: Ed25519PrivateKey, payload: Mapping[str, Any]) -> str:
    """供离线签发脚本使用；客户运行时不需要私钥。"""

    compact = _canonical_payload_bytes(payload)
    payload_part = _b64url_encode(compact)
    message = f"{ACTIVATION_PREFIX}.{payload_part}".encode("ascii")
    signature = private_key.sign(message)
    return f"{ACTIVATION_PREFIX}.{payload_part}.{_b64url_encode(signature)}"


class ProductActivationService:
    def __init__(
        self,
        *,
        settings: Settings | None = None,
        required: bool | None = None,
        state_path: str | Path | None = None,
        public_key_path: str | Path | None = None,
        now: Callable[[], datetime] | None = None,
    ) -> None:
        self.settings = settings
        # 离线发行已显式提供激活配置时，无需加载应用运行环境。
        if required is None or state_path is None:
            self.settings = settings or get_settings()
            if required is None:
                required = self.settings.PRODUCT_ACTIVATION_REQUIRED
            if state_path is None:
                state_path = self.settings.PRODUCT_ACTIVATION_STATE_PATH
        self.required = bool(required)
        self.state_path = Path(state_path) if state_path else self._default_state_path()
        self.public_key_path = Path(public_key_path) if public_key_path else self._default_public_key_path()
        self._now = now or (lambda: datetime.now(timezone.utc))

    @staticmethod
    def _default_public_key_path() -> Path:
        return Path(__file__).resolve().parents[1] / "data" / "product_activation_public_key.pem"

    @staticmethod
    def _default_state_path() -> Path:
        override = os.getenv("PROGRAMDATA")
        if override:
            return Path(override) / "MedQC" / "license" / "activation.json"
        return Path(__file__).resolve().parents[1] / "data" / "product_activation_state.json"

    def _read_public_key(self) -> Ed25519PublicKey:
        try:
            key = serialization.load_pem_public_key(self.public_key_path.read_bytes())
        except (OSError, ValueError, TypeError) as exc:
            raise ProductActivationError("本机未配置产品激活公钥", code="not_configured") from exc
        if not isinstance(key, Ed25519PublicKey):
            raise ProductActivationError("本机产品激活公钥类型无效", code="not_configured")
        return key

    def _validate_code(self, activation_code: str) -> dict[str, str]:
        if not isinstance(activation_code, str) or len(activation_code.strip()) > 20000:
            raise ProductActivationError("激活码格式无效")
        parts = activation_code.strip().split(".")
        if len(parts) != 3 or parts[0] != ACTIVATION_PREFIX:
            raise ProductActivationError("激活码格式无效")
        payload_part, signature_part = parts[1], parts[2]
        payload_bytes = _b64url_decode(payload_part, field="内容")
        signature = _b64url_decode(signature_part, field="签名")
        if len(signature) != 64:
            raise ProductActivationError("激活码签名无效")
        try:
            self._read_public_key().verify(signature, f"{ACTIVATION_PREFIX}.{payload_part}".encode("ascii"))
        except InvalidSignature as exc:
            raise ProductActivationError("激活码签名校验失败") from exc
        try:
            payload = json.loads(payload_bytes.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ProductActivationError("激活码内容无效") from exc
        normalized_payload = _validate_payload(payload, now=self._now())
        canonical_payload_part = _b64url_encode(
            _canonical_payload_bytes(normalized_payload)
        )
        if payload_part != canonical_payload_part:
            raise ProductActivationError("激活码内容编码不是规范格式")
        return normalized_payload

    def _read_state(self) -> dict[str, Any] | None:
        try:
            raw = json.loads(self.state_path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            return None
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            raise ProductActivationError("本地激活状态无效", code="invalid")
        if not isinstance(raw, dict) or not isinstance(raw.get("activation_code"), str):
            raise ProductActivationError("本地激活状态无效", code="invalid")
        return raw

    def _safe_status(self, state: dict[str, Any], payload: dict[str, str], status_value: str) -> dict[str, Any]:
        return {
            "status": status_value,
            "required": self.required,
            "version": payload["version"],
            "product": payload["product"],
            "customer": payload["customer"],
            "edition": payload["edition"],
            "serial": payload["serial"],
            "issued_at": payload["issued_at"],
            "expires_at": payload["expires_at"],
            "activated_at": str(state.get("activated_at") or ""),
        }

    def status(self) -> dict[str, Any]:
        if not self.required:
            return {"status": "not_required", "required": False}
        try:
            state = self._read_state()
            if state is None:
                return {"status": "missing", "required": True}
            payload = self._validate_code(str(state["activation_code"]))
            return self._safe_status(state, payload, "active")
        except ProductActivationError as exc:
            value = "expired" if exc.code == "expired" else ("not_configured" if exc.code == "not_configured" else "invalid")
            return {"status": value, "required": True}

    def enforce(self) -> None:
        if not self.required:
            return
        state = self.status()
        if state.get("status") != "active":
            raise ProductActivationError(
                "产品尚未激活，请在系统设置→产品激活中导入有效激活码",
                code=str(state.get("status") or "invalid"),
            )

    def _write_state(self, activation_code: str, payload: dict[str, str]) -> None:
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        state = {
            "activation_code": activation_code,
            "activated_at": _utc_iso(self._now()),
            "payload": payload,
        }
        fd, temp_name = tempfile.mkstemp(prefix=".activation-", suffix=".tmp", dir=str(self.state_path.parent))
        try:
            with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
                json.dump(state, handle, ensure_ascii=False, separators=(",", ":"))
                handle.write("\n")
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temp_name, self.state_path)
        finally:
            try:
                os.unlink(temp_name)
            except FileNotFoundError:
                pass

    def activate(self, activation_code: str) -> dict[str, Any]:
        payload = self._validate_code(activation_code.strip())
        self._write_state(activation_code.strip(), payload)
        return self._safe_status(
            {"activated_at": _utc_iso(self._now())}, payload, "active"
        )


def get_product_activation_service() -> ProductActivationService:
    return ProductActivationService()


async def require_product_activation(
    current_user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    try:
        get_product_activation_service().enforce()
    except ProductActivationError as exc:
        raise HTTPException(
            status_code=status.HTTP_423_LOCKED,
            detail="产品尚未激活，请在系统设置→产品激活中导入有效激活码",
            headers={"X-Product-Activation": exc.code},
        ) from exc
    return current_user
