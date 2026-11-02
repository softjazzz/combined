"""本机管理API的文件令牌鉴权；只保留令牌摘要，不信任HTTP发起人字段。"""

from __future__ import annotations

import hashlib
import hmac
import json
import re
from collections.abc import Mapping
from pathlib import Path

from medqc_ingest.control.models import Actor, ControlError

_PERMISSIONS = frozenset({"read", "run", "schedule"})


def require_permission(actor: Actor, permission: str) -> None:
    allowed = set(actor.permissions)
    if "schedule" in allowed:
        allowed.update({"read", "run"})
    if "run" in allowed:
        allowed.add("read")
    if permission not in _PERMISSIONS or permission not in allowed:
        raise ControlError("forbidden", "control_permission", 403)


class TokenAuth:
    def __init__(self, tokens: Mapping[str, Actor]) -> None:
        if not tokens or len(tokens) > 32:
            raise ControlError("configuration_error", "control_token_config", 503)
        self._bindings: list[tuple[bytes, Actor]] = []
        for token, actor in tokens.items():
            if (
                not isinstance(token, str)
                or not 32 <= len(token) <= 1024
                or any(ch.isspace() for ch in token)
                or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.:@-]{0,127}", actor.actor_id)
                or not actor.permissions
                or actor.permissions - _PERMISSIONS
            ):
                raise ControlError("configuration_error", "control_token_config", 503)
            self._bindings.append((hashlib.sha256(token.encode()).digest(), actor))

    @classmethod
    def from_file(cls, path: Path) -> TokenAuth:
        try:
            if not path.is_absolute() or not path.is_file() or path.stat().st_size > 65536:
                raise ValueError
            document = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(document, dict) or set(document) != {"tokens"}:
                raise ValueError
            rows = document["tokens"]
            if not isinstance(rows, list):
                raise ValueError
            tokens = {}
            for row in rows:
                if not isinstance(row, dict) or set(row) != {"token", "actor_id", "permissions"}:
                    raise ValueError
                if (
                    not isinstance(row["token"], str)
                    or row["token"] in tokens
                    or not isinstance(row["actor_id"], str)
                    or not isinstance(row["permissions"], list)
                    or any(not isinstance(p, str) for p in row["permissions"])
                ):
                    raise ValueError
                tokens[row["token"]] = Actor(row["actor_id"], frozenset(row["permissions"]))
            return cls(tokens)
        except (OSError, UnicodeError, ValueError, TypeError, KeyError, ControlError):
            raise ControlError("configuration_error", "control_token_file", 503) from None

    def authenticate(self, authorization: str | None) -> Actor:
        if (
            not authorization
            or len(authorization) > 1031
            or not authorization.startswith("Bearer ")
        ):
            raise ControlError("unauthenticated", "control_bearer", 401)
        token = authorization[7:]
        if not token or any(ch.isspace() for ch in token):
            raise ControlError("unauthenticated", "control_bearer", 401)
        digest = hashlib.sha256(token.encode()).digest()
        matched = None
        for expected, actor in self._bindings:
            if hmac.compare_digest(digest, expected):
                matched = actor
        if matched is None:
            raise ControlError("unauthenticated", "control_bearer", 401)
        return matched
