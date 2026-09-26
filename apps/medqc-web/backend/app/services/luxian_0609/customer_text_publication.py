"""LX0609 正式发布文案的完整性证明，供保存和公开读取共用。"""

from __future__ import annotations

import hashlib
import hmac
import json
import re
from typing import Any, Callable, Mapping

from ...core.settings import get_settings


CUSTOMER_TEXT_SEAL_KEY = "customer_text_seal"
LX0609_CUSTOMER_RESULT_CONTRACT_ERROR = (
    "LX0609 客户结果解释合同不完整，拒绝交付确定问题"
)
_SEAL_VERSION = "lx0609-customer-text-v1"
_SEAL_PATTERN = re.compile(r"lx0609-customer-text-v1:[0-9a-f]{64}\Z")


def _first_text(item: Mapping[str, Any], *keys: str) -> str:
    for key in keys:
        value = item.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def _publication_material(item: Mapping[str, Any]) -> bytes:
    rule_ids = [
        _first_text(item, key).upper()
        for key in ("rule_id", "rule_code", "qc_point_id", "customer_rule_id")
        if _first_text(item, key)
    ]
    if not rule_ids or len(set(rule_ids)) != 1:
        raise ValueError(LX0609_CUSTOMER_RESULT_CONTRACT_ERROR)
    payload = {
        "version": _SEAL_VERSION,
        "rule_id": rule_ids[0],
        "status": _first_text(item, "status").lower(),
        "conclusion": _first_text(
            item, "conclusion", "customer_conclusion", "findings"
        ),
        "suggestion": _first_text(item, "suggestion", "customer_suggestion"),
    }
    if not payload["status"]:
        raise ValueError(LX0609_CUSTOMER_RESULT_CONTRACT_ERROR)
    return json.dumps(
        payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")


def _publication_key() -> bytes:
    secret = str(get_settings().JWT_SECRET or "").strip()
    if not secret:
        raise RuntimeError("LX0609 发布文案完整性密钥未配置")
    return secret.encode("utf-8")


def operation_publication_key() -> Callable[[], bytes]:
    """返回单次操作内复用的取钥函数：首次校验时读配置，不跨操作缓存。"""

    resolved: list[bytes] = []

    def key() -> bytes:
        if not resolved:
            resolved.append(_publication_key())
        return resolved[0]

    return key


def seal_published_customer_text(
    item: Mapping[str, Any], *, key_provider: Callable[[], bytes] | None = None,
) -> str:
    """正式聚合器在最后一次文案修改后生成；不用于普通 DTO 或 Prompt。"""

    digest = hmac.new(
        (key_provider or _publication_key)(), _publication_material(item), hashlib.sha256
    ).hexdigest()
    return f"{_SEAL_VERSION}:{digest}"


def assert_published_customer_text_unchanged(
    item: Mapping[str, Any], *, key_provider: Callable[[], bytes] | None = None,
) -> None:
    """有证明但文案已改变时拒绝交付；旧无证明结果由安全回退处理。"""

    seal = item.get(CUSTOMER_TEXT_SEAL_KEY)
    if not isinstance(seal, str) or not _SEAL_PATTERN.fullmatch(seal):
        raise ValueError(LX0609_CUSTOMER_RESULT_CONTRACT_ERROR)
    expected = seal_published_customer_text(item, key_provider=key_provider)
    if not hmac.compare_digest(seal, expected):
        raise ValueError(LX0609_CUSTOMER_RESULT_CONTRACT_ERROR)
