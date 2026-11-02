"""控制面的无驱动模型与受控错误；不承载临床数据或连接秘密。"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

JsonObject = dict[str, Any]

JOB_STATES = frozenset(
    {
        "queued",
        "running",
        "recovery_required",
        "succeeded",
        "completed_with_source_limitations",
        "failed",
        "cancelled",
    }
)
UNIT_STATES = frozenset({"queued", "running", "succeeded", "source_limited", "failed", "cancelled"})
TERMINAL_JOB_STATES = frozenset(
    {"succeeded", "completed_with_source_limitations", "failed", "cancelled"}
)
PERMISSIONS = frozenset({"read", "run", "schedule"})


class ControlError(Exception):
    """只保留静态代码/位置；不把原始输入或驱动异常变成输出文本。"""

    def __init__(self, code: str, location: str, status_code: int = 400) -> None:
        self.code = code if re.fullmatch(r"[a-z][a-z0-9_]{0,63}", code) else "control_error"
        self.location = (
            location if re.fullmatch(r"[a-z][a-z0-9_.:-]{0,127}", location) else "control_boundary"
        )
        self.status_code = (
            status_code if status_code in {400, 401, 403, 404, 409, 422, 429, 500, 503} else 500
        )
        super().__init__(f"{self.code} at {self.location}")


class SourceLimited(ControlError):
    """执行侧已核验的源限制，不能用于包裹未经分类的任意异常。"""

    def __init__(self, location: str = "source_query", result: JsonObject | None = None) -> None:
        super().__init__("source_limited", location, 409)
        self.result = dict(result or {}, source_limited=True)


@dataclass(frozen=True)
class Actor:
    actor_id: str
    permissions: frozenset[str]

    def __post_init__(self) -> None:
        if (
            not isinstance(self.actor_id, str)
            or not 1 <= len(self.actor_id) <= 128
            or any(ord(char) < 32 or ord(char) == 127 for char in self.actor_id)
            or not isinstance(self.permissions, frozenset)
            or not self.permissions <= PERMISSIONS
        ):
            raise ControlError("invalid_actor", "actor")

    def has(self, permission: str) -> bool:
        if permission not in PERMISSIONS:
            return False
        return (
            permission in self.permissions
            or permission == "read"
            and bool(self.permissions & {"run", "schedule"})
            or permission == "run"
            and "schedule" in self.permissions
        )

    def require(self, permission: str) -> None:
        if not self.has(permission):
            raise ControlError("forbidden", "actor_permission", 403)
