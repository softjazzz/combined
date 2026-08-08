"""LX0609 单病历已保存结果的确定性读取模型。

该模块只处理“哪一次任务是当前病历的权威结果”。它不解释医学结论、
不按文案完整度挑选候选，也不修改已有 RuleDecision / 聚合结果。
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Iterable, Mapping, Optional


@dataclass(frozen=True)
class LatestRecordResultJobSelection:
    """单病历读取任务选择的安全结果。"""

    state: str
    reason_code: str
    job: Optional[dict[str, Any]] = None
    candidate_count: int = 0


def _text(value: Any) -> str:
    return str(value or "").strip()


def _record_ids(job: Mapping[str, Any]) -> set[str]:
    return {
        _text(value)
        for value in list(job.get("record_ids") or [])
        if _text(value)
    }


def _filters(job: Mapping[str, Any]) -> Mapping[str, Any]:
    value = job.get("filters")
    return value if isinstance(value, Mapping) else {}


def _summary(job: Mapping[str, Any]) -> Mapping[str, Any]:
    value = job.get("summary")
    return value if isinstance(value, Mapping) else {}


def _rule_set_value(job: Mapping[str, Any], key: str) -> str:
    """规则集身份先取持久化 filters，兼容已聚合父任务的 summary。"""

    return _text(_filters(job).get(key) or _summary(job).get(key) or job.get(key))


def _datetime_key(value: Any) -> datetime:
    if isinstance(value, datetime):
        return value
    text = _text(value)
    if not text:
        return datetime.min
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
        if parsed.tzinfo is not None:
            return parsed.astimezone(timezone.utc).replace(tzinfo=None)
        return parsed
    except ValueError:
        return datetime.min


def _generation_key(job: Mapping[str, Any]) -> tuple[datetime, datetime]:
    """以任务实际完成时间为主、创建时间为次确定当前代次。"""

    return (_datetime_key(job.get("finished_at")), _datetime_key(job.get("created_at")))


def select_latest_authoritative_record_result_job(
    candidates: Iterable[Mapping[str, Any]],
    *,
    record_id: str,
    rule_set_key: str,
    rule_set_version: str,
) -> LatestRecordResultJobSelection:
    """按任务身份选唯一权威任务，不以状态、文案或解释完整度裁决。

    上游已使用三坐标把候选限制为同一病历；本函数再只保留已完成、明确
    包含目标就诊号、且规则集与当前版本完全一致的任务。全院质控视图按
    跨创建者的最新完成代次选择；完成时间与创建时间均并列时无法确定当前
    代次，必须 fail-closed。
    """

    normalized_record_id = _text(record_id)
    normalized_rule_set_key = _text(rule_set_key)
    normalized_rule_set_version = _text(rule_set_version)
    if not all(
        (
            normalized_record_id,
            normalized_rule_set_key,
            normalized_rule_set_version,
        )
    ):
        raise ValueError("record_id、rule_set_key、rule_set_version 均不能为空")

    eligible: list[dict[str, Any]] = []
    for candidate in candidates:
        if not isinstance(candidate, Mapping):
            continue
        if _text(candidate.get("status")).lower() != "completed":
            continue
        if normalized_record_id not in _record_ids(candidate):
            continue
        if _rule_set_value(candidate, "rule_set_key") != normalized_rule_set_key:
            continue
        if _rule_set_value(candidate, "rule_set_version") != normalized_rule_set_version:
            continue
        eligible.append(dict(candidate))

    if not eligible:
        return LatestRecordResultJobSelection(
            state="not_found",
            reason_code="record_result_not_found",
            candidate_count=0,
        )

    newest_generation = max(_generation_key(candidate) for candidate in eligible)
    newest = [candidate for candidate in eligible if _generation_key(candidate) == newest_generation]
    if len(newest) != 1:
        return LatestRecordResultJobSelection(
            state="technical_error",
            reason_code="record_result_task_generation_conflict",
            candidate_count=len(newest),
        )
    return LatestRecordResultJobSelection(
        state="ready",
        reason_code="",
        job=newest[0],
        candidate_count=len(eligible),
    )
