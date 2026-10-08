"""050 疑难病例讨论规则的客户展示事实合同。

本模块只白名单化原生执行器已经裁决的展示事实：不读取文书、不复算
“诊断不明确”触发条件，也不把 ``fact_refs`` 投影成客户证据。正式主链的
文书定位始终由 ``RuleDecision.fact_refs → Binding → 公共投影`` 完成。
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime
import re
from typing import Any


DIFFICULT_CASE_CUSTOMER_RULE_ID = "LX0609-03-02-01"
_DATETIME = re.compile(
    r"\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}:\d{2}"
    r"(?:\.\d{1,6})?(?:Z|[+-]\d{2}:?\d{2})?"
)
_DISCUSSION_KIND = "uncertain_diagnosis_discussion_check"
_SCOPE_UNCERTAIN_KIND = "uncertain_diagnosis_scope_unverified"
_COURSE_TIME_GAP_KIND = "uncertain_diagnosis_course_time_gap"
_COURSE_TIME_GAP_COUNT = "candidate_course_time_gap_count"
_DISCUSSION_BODY_GAP_KIND = "uncertain_diagnosis_discussion_body_gap"
_DISCUSSION_BODY_GAP_COUNT = "discussion_body_gap_count"


def is_difficult_case_customer_rule(rule_id: str) -> bool:
    return str(rule_id or "").strip().upper() == DIFFICULT_CASE_CUSTOMER_RULE_ID


def _safe_time(value: Any) -> str:
    if not isinstance(value, str) or _DATETIME.fullmatch(value) is None:
        return ""
    try:
        datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return ""
    return value


def safe_difficult_case_customer_display_facts(
    *, rule_id: str, raw: Any
) -> dict[str, Any] | None:
    """仅输出 050 已裁决的、无文书标识的客户事实。

    未知字段（包括旧直调入口携带的原文）被明确丢弃；它们不能改变业务状态，
    也不能成为客户侧证据。
    """

    if not is_difficult_case_customer_rule(rule_id) or not isinstance(raw, Mapping):
        return None
    kind = raw.get("verification_kind")
    admission_time = _safe_time(raw.get("admission_time"))
    record_times = raw.get("uncertain_record_times")
    discussion_count = raw.get("discussion_count")
    if (
        kind not in {_DISCUSSION_KIND, _SCOPE_UNCERTAIN_KIND, _COURSE_TIME_GAP_KIND, _DISCUSSION_BODY_GAP_KIND}
        or not admission_time
        or not isinstance(record_times, (list, tuple))
        or len(record_times) > 100
        or any(not _safe_time(item) for item in record_times)
        or not isinstance(discussion_count, int)
        or isinstance(discussion_count, bool)
        or discussion_count < 0
    ):
        return None
    has_time_gap = _COURSE_TIME_GAP_COUNT in raw
    time_gap_count = raw.get(_COURSE_TIME_GAP_COUNT)
    if has_time_gap and (
        not isinstance(time_gap_count, int) or isinstance(time_gap_count, bool) or time_gap_count <= 0
        or kind == _SCOPE_UNCERTAIN_KIND
        or (kind == _DISCUSSION_KIND and not record_times)
    ):
        return None
    if kind == _COURSE_TIME_GAP_KIND and (not has_time_gap or record_times):
        return None
    has_body_gap = _DISCUSSION_BODY_GAP_COUNT in raw
    body_gap_count = raw.get(_DISCUSSION_BODY_GAP_COUNT)
    if kind == _DISCUSSION_BODY_GAP_KIND:
        if (
            not record_times or discussion_count <= 0 or not has_body_gap
            or not isinstance(body_gap_count, int) or isinstance(body_gap_count, bool)
            or body_gap_count != discussion_count
        ):
            return None
    elif has_body_gap:
        return None
    safe = {
        "verification_kind": kind,
        "admission_time": admission_time,
        "uncertain_record_times": list(record_times),
        "discussion_count": discussion_count,
    }
    if has_time_gap:
        safe[_COURSE_TIME_GAP_COUNT] = time_gap_count
    if has_body_gap:
        safe[_DISCUSSION_BODY_GAP_COUNT] = body_gap_count
    return safe


def difficult_case_customer_fact_status_is_valid(
    *, rule_id: str, status: str, safe_facts: Mapping[str, Any] | None
) -> bool:
    """只校验已裁决状态与展示事实是否自洽，不重新判断临床事实。"""

    if not is_difficult_case_customer_rule(rule_id):
        return True
    normalized_status = str(status or "").strip().lower()
    if isinstance(safe_facts, Mapping) and (
        safe_facts.get("verification_kind") in {_COURSE_TIME_GAP_KIND, _DISCUSSION_BODY_GAP_KIND}
        or _COURSE_TIME_GAP_COUNT in safe_facts or _DISCUSSION_BODY_GAP_COUNT in safe_facts
    ):
        validated = safe_difficult_case_customer_display_facts(rule_id=rule_id, raw=safe_facts)
        if validated is None:
            return False
        if validated["verification_kind"] in {_COURSE_TIME_GAP_KIND, _DISCUSSION_BODY_GAP_KIND}:
            return normalized_status == "data_gap"
        # 混合缺时摘要只能附在已有成熟检查的C/NC；仍按原事实匹配状态。
        if normalized_status not in {"compliant", "non_compliant"}:
            return False
    if normalized_status == "technical_error":
        return True
    if not isinstance(safe_facts, Mapping):
        return False
    kind = safe_facts.get("verification_kind")
    records = safe_facts.get("uncertain_record_times")
    discussion_count = safe_facts.get("discussion_count")
    if kind == _SCOPE_UNCERTAIN_KIND:
        return normalized_status == "uncertain"
    if kind != _DISCUSSION_KIND or not isinstance(records, list) or not isinstance(
        discussion_count, int
    ):
        return False
    if not records:
        return normalized_status == "not_applicable"
    if records and discussion_count == 0:
        return normalized_status == "non_compliant"
    return bool(records) and discussion_count > 0 and normalized_status == "compliant"


__all__ = [
    "DIFFICULT_CASE_CUSTOMER_RULE_ID",
    "difficult_case_customer_fact_status_is_valid",
    "is_difficult_case_customer_rule",
    "safe_difficult_case_customer_display_facts",
]
