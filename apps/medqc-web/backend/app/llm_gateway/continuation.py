"""有限病例/规则包优先权；不持有队列、物理lease或医学判断。"""

from dataclasses import dataclass
from typing import Protocol, Sequence, TypeVar

from .config import CaseContinuationConfig


class Candidate(Protocol):
    case_key: str | None
    package_key: str | None
    queued_at: float


T = TypeVar("T", bound=Candidate)


@dataclass
class _Turn:
    package_key: str
    started_at: float
    requests: int = 1
    idle_until: float = 0
    inflight: bool = True


class CaseContinuationPolicy:
    def __init__(self, config: CaseContinuationConfig):
        self.config = config
        self._turns: dict[str, _Turn] = {}

    @property
    def case_count(self):
        return len(self._turns)

    def clear(self):
        self._turns.clear()

    def forget(self, case_key):
        self._turns.pop(case_key, None)

    def granted(self, case_key, package_key, now, *, capacity):
        if not self.config.enabled or not case_key or not package_key:
            self.forget(case_key)
            return
        turn = self._turns.get(case_key)
        if turn and (
            turn.requests >= self.config.burst_requests
            or now - turn.started_at >= self.config.turn_seconds
        ):
            self.forget(case_key)
            turn = None
        if turn is None:
            # 只保留有效容量以内的活动/近期病例；选择新病例时替换空闲优先权。
            while len(self._turns) >= capacity:
                idle = next(
                    (key for key, value in self._turns.items() if not value.inflight),
                    None,
                )
                if idle is None:
                    return
                self.forget(idle)
            self._turns[case_key] = _Turn(package_key, now)
        else:
            turn.requests += 1
            turn.package_key = package_key
            turn.inflight = True

    def released(self, case_key, now):
        turn = self._turns.get(case_key)
        if turn:
            turn.inflight = False
            turn.idle_until = now + self.config.idle_grace_seconds

    def choose(
        self,
        candidates: Sequence[T],
        active_cases: set[str],
        now: float,
        *,
        capacity: int,
    ) -> tuple[T | None, float | None]:
        if not candidates:
            return None, None
        if not self.config.enabled:
            return candidates[0], None
        waiting_cases = {item.case_key for item in candidates}
        yielded = set()
        for key, turn in list(self._turns.items()):
            turn.inflight = key in active_cases
            if turn.inflight:
                continue
            exhausted = (
                turn.requests >= self.config.burst_requests
                or now - turn.started_at >= self.config.turn_seconds
            )
            if exhausted or (now >= turn.idle_until and key not in waiting_cases):
                if exhausted:
                    yielded.add(key)
                self.forget(key)
        # 无包身份的旧调用保持FIFO，不能根据Prompt猜包或被新协议无限越过。
        if candidates[0].package_key is None:
            return candidates[0], None
        outsiders = [
            item
            for item in candidates
            if item.case_key not in self._turns and item.case_key not in yielded
        ]
        if yielded and outsiders:
            return outsiders[0], None
        aged = next(
            (
                item
                for item in outsiders
                if now - item.queued_at >= self.config.fair_wait_seconds
            ),
            None,
        )
        if aged is not None:
            return aged, None
        same_package = next(
            (
                item
                for item in candidates
                if item.case_key in self._turns
                and self._turns[item.case_key].package_key == item.package_key
            ),
            None,
        )
        if same_package is not None:
            return same_package, None
        next_package = next(
            (
                item
                for item in candidates
                if item.case_key in self._turns
                and now >= self._turns[item.case_key].idle_until
            ),
            None,
        )
        if next_package is not None:
            return next_package, None
        if len(self._turns) < capacity:
            available = next(
                (item for item in candidates if item.case_key not in self._turns), None
            )
            if available is not None:
                return available, None
        wake = min(
            (
                value.idle_until
                for key, value in self._turns.items()
                if key not in active_cases and value.idle_until > now
            ),
            default=None,
        )
        if wake is not None:
            age_at = min(
                (item.queued_at + self.config.fair_wait_seconds for item in outsiders),
                default=wake,
            )
            return None, min(wake, age_at)
        return candidates[0], None
