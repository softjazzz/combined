from __future__ import annotations

import json
import logging
from typing import Any

from fastapi import Request

from .response import get_trace_id

logger = logging.getLogger("app.audit")

_SENSITIVE_KEYWORDS = {"password", "token", "secret", "credential", "authorization", "api_key"}


def _is_sensitive_key(key: str) -> bool:
    normalized = key.strip().lower()
    return any(marker in normalized for marker in _SENSITIVE_KEYWORDS)


def _sanitize_value(key: str, value: Any) -> Any:
    if _is_sensitive_key(key):
        return "***"
    if isinstance(value, dict):
        return {str(k): _sanitize_value(str(k), v) for k, v in value.items()}
    if isinstance(value, list):
        return [_sanitize_value(key, item) for item in value]
    return value


def _resolve_actor(current_user: Any) -> tuple[str, str]:
    if not isinstance(current_user, dict):
        return "anonymous", "-"
    actor = str(
        current_user.get("email")
        or current_user.get("id")
        or current_user.get("user_id")
        or "unknown"
    )
    roles_raw = current_user.get("roles")
    if isinstance(roles_raw, list):
        roles = ",".join(sorted(str(item) for item in roles_raw if str(item)))
    else:
        single_role = str(current_user.get("role") or "").strip()
        roles = single_role if single_role else "-"
    return actor, roles or "-"


def audit_event(
    request: Request,
    *,
    action: str,
    resource: str,
    outcome: str,
    details: dict[str, Any] | None = None,
    current_user: dict[str, Any] | None = None,
) -> None:
    actor, roles = _resolve_actor(current_user or getattr(request.state, "current_user", None))
    safe_details = _sanitize_value("details", details or {})
    details_json = json.dumps(safe_details, ensure_ascii=False, sort_keys=True, default=str)
    logger.info(
        "audit.event action=%s resource=%s outcome=%s actor=%s roles=%s trace_id=%s details=%s",
        action,
        resource,
        outcome,
        actor,
        roles,
        get_trace_id(request),
        details_json,
    )
