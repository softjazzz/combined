"""单次病历执行的已发布结果旁路；不改变调度、判定或最终保存合同。"""
from contextlib import contextmanager
from contextvars import ContextVar
from collections.abc import Callable, Iterator, Mapping, Sequence
from typing import Any

ResultSink = Callable[[str, list[dict[str, Any]]], None]
CaseKey = tuple[str, str, str]
_SINK: ContextVar[ResultSink | None] = ContextVar(
    "luxian_live_result_sink", default=None,
)


@contextmanager
def live_result_scope(sink: ResultSink) -> Iterator[None]:
    token = _SINK.set(sink)
    try:
        yield
    finally:
        _SINK.reset(token)


def live_result_sink() -> ResultSink | None:
    return _SINK.get()


class LiveResultBuffer:
    """未完成病历的发布结果按三坐标和规则去重，正式结果始终优先。"""

    def __init__(self) -> None:
        self._rows: dict[tuple[str, str, str, str], dict[str, Any]] = {}
        self._finished: set[CaseKey] = set()

    @staticmethod
    def key(row: Mapping[str, Any]) -> CaseKey:
        return (str(row.get("institute_id") or ""), str(row.get("patient_id") or ""),
                str(row.get("visit_id") or ""))

    def add(self, rows: Sequence[dict[str, Any]]) -> None:
        for row in rows:
            case = self.key(row)
            if all(case) and case not in self._finished:
                self._rows[(*case, row["rule_id"])] = dict(row)

    def finish(self, case: CaseKey) -> None:
        self._finished.add(case)
        self._rows = {key: row for key, row in self._rows.items() if key[:3] != case}

    def combine(self, final_rows: Sequence[dict[str, Any]]) -> list[dict[str, Any]]:
        rows = dict(self._rows)
        for row in final_rows:
            rows[(*self.key(row), row["rule_id"])] = row
        return list(rows.values())
