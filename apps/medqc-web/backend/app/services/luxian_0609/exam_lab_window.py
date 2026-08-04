"""检查检验规则的评价窗口纯判断。"""

from __future__ import annotations

from datetime import datetime, timedelta
from enum import Enum

from .exam_lab_fact_extraction import ExamLabTextProjection


class EvaluationWindowState(str, Enum):
    MATURE = "mature"
    NOT_MATURE = "not_mature"
    MISSING = "missing"
    CONFLICT = "conflict"


def resolve_evaluation_window_state(
    *, projection: ExamLabTextProjection, event_time: datetime
) -> EvaluationWindowState:
    """使用受控评价终点判断24小时窗口，不回读原始住院时间。"""

    if projection.horizon_conflict:
        return EvaluationWindowState.CONFLICT
    deadline = event_time + timedelta(hours=24)
    if projection.precise_horizon is not None:
        if projection.precise_horizon < event_time:
            return EvaluationWindowState.CONFLICT
        return (
            EvaluationWindowState.MATURE
            if projection.precise_horizon >= deadline
            else EvaluationWindowState.NOT_MATURE
        )
    if projection.horizon_date is not None:
        if projection.horizon_date < event_time.date():
            return EvaluationWindowState.CONFLICT
        return (
            EvaluationWindowState.MATURE
            if projection.horizon_date > deadline.date()
            else EvaluationWindowState.NOT_MATURE
        )
    if projection.horizon_unavailable_reason == "authoritative_time_conflict":
        return EvaluationWindowState.CONFLICT
    return EvaluationWindowState.MISSING


def _evaluation_window_gap_reason(state: EvaluationWindowState) -> str:
    if state is EvaluationWindowState.NOT_MATURE:
        return "evaluation_window_not_mature"
    if state is EvaluationWindowState.CONFLICT:
        return "authoritative_time_conflict"
    return "authoritative_time_missing"


__all__ = [
    "EvaluationWindowState",
    "resolve_evaluation_window_state",
]
