"""LX0609 规则族执行器注册表。

注册表只负责 ``executor_key`` 到执行器的解析和依赖声明，不读取数据库，
也不包含任何临床规则分支。
"""

from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any, Iterable, Protocol, TYPE_CHECKING

if TYPE_CHECKING:
    from .engine import FamilyExecutionContext


_EXECUTOR_KEY_PATTERN = re.compile(r"^[a-z][a-z0-9_]*$")


class Luxian0609FamilyExecutor(Protocol):
    async def evaluate(self, context: FamilyExecutionContext) -> Any:
        """执行一个规则族；临床结果契约由后续 exactly-once 层校验。"""


@dataclass(frozen=True)
class ExecutorRegistration:
    executor_key: str
    executor: Luxian0609FamilyExecutor
    depends_on: tuple[str, ...] = ()
    deadline_seconds: float | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.executor_key, str) or not _EXECUTOR_KEY_PATTERN.fullmatch(
            self.executor_key
        ):
            raise ValueError("invalid executor_key")
        if not callable(getattr(self.executor, "evaluate", None)):
            raise TypeError("executor must provide evaluate")
        if (
            not isinstance(self.depends_on, tuple)
            or len(self.depends_on) != len(set(self.depends_on))
            or any(
                not isinstance(item, str)
                or not _EXECUTOR_KEY_PATTERN.fullmatch(item)
                or item == self.executor_key
                for item in self.depends_on
            )
        ):
            raise ValueError("invalid executor dependency")
        if self.deadline_seconds is not None and (
            isinstance(self.deadline_seconds, bool)
            or not isinstance(self.deadline_seconds, (int, float))
            or self.deadline_seconds <= 0
        ):
            raise ValueError("deadline_seconds must be positive")


class Luxian0609ExecutorRegistry:
    """进程内不可猜测的执行器注册表；重复和未知 key 均 fail-closed。"""

    def __init__(
        self,
        registrations: Iterable[ExecutorRegistration] = (),
    ) -> None:
        self._registrations: dict[str, ExecutorRegistration] = {}
        for registration in registrations:
            self.register(registration)

    def register(self, registration: ExecutorRegistration) -> None:
        if not isinstance(registration, ExecutorRegistration):
            raise TypeError("registration must be ExecutorRegistration")
        if registration.executor_key in self._registrations:
            raise ValueError("duplicate executor_key")
        self._registrations[registration.executor_key] = registration

    def resolve(self, executor_key: str) -> ExecutorRegistration:
        normalized = str(executor_key or "").strip()
        try:
            return self._registrations[normalized]
        except KeyError:
            raise KeyError("unregistered executor_key") from None

    @property
    def executor_keys(self) -> tuple[str, ...]:
        return tuple(self._registrations)
