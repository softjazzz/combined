"""查房病程规则族的客户事实合同。

本模块仅验证执行器已经裁决的 007/008/009/016/017/018 展示事实；不读取
文书、不按日期或指纹回查文书。客户证据只能由 ``RuleDecision.fact_refs``
经 Binding 与公共 selected-document projector 产生。
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime, timedelta
from math import isfinite
import re
from typing import Any


COURSE_QUALITY_CUSTOMER_RULE_IDS = frozenset({
    "LX0609-007", "LX0609-008", "LX0609-009", "LX0609-016", "LX0609-017", "LX0609-018",
})
_COURSE_SOURCES = frozenset({"daily_course_record", "senior_course_record"})
_DATETIME = re.compile(r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}")
_DATE = re.compile(r"\d{4}-\d{2}-\d{2}")
def is_course_quality_customer_rule(rule_id: str) -> bool:
    return str(rule_id or "").strip().upper() in COURSE_QUALITY_CUSTOMER_RULE_IDS


def _date(value: Any) -> bool:
    return isinstance(value, str) and _DATE.fullmatch(value) is not None


def _time(value: Any) -> bool:
    return isinstance(value, str) and _DATETIME.fullmatch(value) is not None


def _strict_copy_time(value: Any) -> str:
    if not _time(value):
        return ""
    try:
        return datetime.strptime(value, "%Y-%m-%d %H:%M:%S").strftime("%Y-%m-%d %H:%M:%S")
    except ValueError:
        return ""


def _safe_007(raw: Mapping[str, Any]) -> dict[str, Any] | None:
    kind = raw.get("failure_kind")
    if kind == "unstable_patient_order_present":
        return ({"failure_kind": kind, "stable_course_rule_applicable": False}
                if raw.get("stable_course_rule_applicable") is False else None)
    start_source, end_source = raw.get("interval_start_source"), raw.get("interval_end_source")
    dates = raw.get("recorded_dates")
    if (
        kind not in {"course_record_interval_over_72h", "course_record_interval_within_72h"}
        or start_source not in _COURSE_SOURCES | {"inpat_registration"}
        or end_source not in _COURSE_SOURCES | {"evaluation_context.horizon"}
        or start_source == "evaluation_context.horizon" or end_source == "inpat_registration"
        or not _time(raw.get("interval_start_time")) or raw.get("threshold_hours") != 72
        or not isinstance(dates, list) or len(dates) > 64 or not all(_date(item) for item in dates)
    ):
        return None
    facts: dict[str, Any] = {
        "failure_kind": kind, "interval_start_source": start_source,
        "interval_end_source": end_source, "interval_start_time": raw["interval_start_time"],
        "threshold_hours": 72, "recorded_dates": list(dates),
    }
    date_only = raw.get("interval_end_precision") == "date"
    if date_only:
        end_date = raw.get("interval_end_date")
        if (kind != "course_record_interval_over_72h" or end_source != "evaluation_context.horizon"
                or "interval_end_time" in raw or not _date(end_date)
                or raw.get("interval_hours") is not None or raw.get("interval_seconds") is not None
                or raw.get("overdue_seconds") is not None):
            return None
        try:
            if datetime.strptime(end_date, "%Y-%m-%d").date() <= (
                datetime.strptime(raw["interval_start_time"], "%Y-%m-%d %H:%M:%S") + timedelta(hours=72)
            ).date():
                return None
        except ValueError:
            return None
        facts.update({"interval_end_date": end_date, "interval_end_precision": "date"})
    else:
        interval = raw.get("interval_hours")
        if (raw.get("interval_end_precision") is not None or raw.get("interval_end_date") is not None
                or not _time(raw.get("interval_end_time")) or isinstance(interval, bool)
                or not isinstance(interval, (int, float))
                or (kind == "course_record_interval_over_72h" and float(interval) <= 72)
                or (kind == "course_record_interval_within_72h" and float(interval) > 72)):
            return None
        facts.update({"interval_end_time": raw["interval_end_time"], "interval_hours": round(float(interval), 2)})
    enhanced = {key: raw.get(key) for key in (
        "interval_start_position", "interval_end_position", "record_count", "interval_seconds", "overdue_seconds"
    )}
    if any(key in raw for key in enhanced):
        start, end, count = (enhanced[key] for key in (
            "interval_start_position", "interval_end_position", "record_count"))
        if not all(type(value) is int for value in (start, end, count)) or not 0 <= start < end <= count + 1 or end != start + 1 or count != len(dates):
            return None
        if date_only:
            if enhanced["interval_seconds"] is not None or enhanced["overdue_seconds"] is not None or end != count + 1:
                return None
            facts.update({"interval_start_position": start, "interval_end_position": end, "record_count": count})
        else:
            seconds, overdue = enhanced["interval_seconds"], enhanced["overdue_seconds"]
            if type(seconds) is not int or type(overdue) is not int:
                return None
            try:
                actual = round((datetime.strptime(raw["interval_end_time"], "%Y-%m-%d %H:%M:%S") - datetime.strptime(raw["interval_start_time"], "%Y-%m-%d %H:%M:%S")).total_seconds())
            except ValueError:
                return None
            if actual <= 0 or seconds != actual or overdue != max(0, actual - 72 * 3600) or round(actual / 3600, 2) != facts["interval_hours"]:
                return None
            facts.update({"interval_start_position": start, "interval_end_position": end, "record_count": count, "interval_seconds": seconds, "overdue_seconds": overdue})
    # interval_*_document_id 是执行器内部的选择坐标；本层不读取、不复验，也不投影。
    return facts


def _safe_008(raw: Mapping[str, Any]) -> dict[str, Any] | None:
    kind = raw.get("failure_kind")
    dates = {key: raw.get(key) for key in ("anchor_date", "horizon_date")}
    records = raw.get("recorded_dates")
    if (kind not in {"severity_course_gap_exceeded", "severity_course_interval_satisfied"}
            or raw.get("severity") != "serious" or raw.get("threshold_days") != 2
            or not all(_date(value) for value in dates.values())
            or (records is not None and (not isinstance(records, list) or len(records) > 64 or not all(_date(value) for value in records)))):
        return None
    facts: dict[str, Any] = {"failure_kind": kind, "severity": "serious", "threshold_days": 2, **dates}
    if kind == "severity_course_gap_exceeded":
        gaps = {key: raw.get(key) for key in ("gap_start_date", "gap_end_date")}
        gap_days = raw.get("gap_days")
        if not all(_date(value) for value in gaps.values()) or type(gap_days) is not int or gap_days <= 2:
            return None
        facts.update(gaps, gap_days=gap_days)
        if isinstance(records, list):
            facts["recorded_dates"] = list(records)
        return facts
    maximum = raw.get("maximum_gap_days")
    if type(maximum) is not int or not 0 <= maximum <= 2 or not isinstance(records, list):
        return None
    facts.update(maximum_gap_days=maximum, recorded_dates=list(records))
    return facts


def _safe_009_event(item: Any) -> dict[str, Any] | None:
    required = {"event_ref", "change_category", "event_time", "corresponding_course_ref", "corresponding_course_time", "deadline_time", "threshold_hours", "timely"}
    if not isinstance(item, Mapping) or set(item) != required:
        return None
    if (not isinstance(item.get("event_ref"), str) or not item["event_ref"].strip() or len(item["event_ref"]) > 256
            or not isinstance(item.get("corresponding_course_ref"), str) or len(item["corresponding_course_ref"]) > 256
            or item.get("change_category") not in {"subjective", "objective", "exam_lab", "complication", "special_state"}
            or item.get("threshold_hours") != 24 or type(item.get("timely")) is not bool
            or not _time(item.get("event_time")) or not _time(item.get("deadline_time"))
            or (item["corresponding_course_ref"] and not _time(item.get("corresponding_course_time")))
            or (not item["corresponding_course_ref"] and item.get("corresponding_course_time") != "")):
        return None
    return {key: item[key] for key in required}


def _safe_009(raw: Mapping[str, Any]) -> dict[str, Any] | None:
    kind = raw.get("failure_kind")
    if kind == "critical_change_time_unavailable":
        return {"failure_kind": kind, "threshold_hours": 24} if raw.get("threshold_hours") == 24 else None
    if kind == "critical_change_course_association_failed":
        if (raw.get("threshold_hours") != 24 or not isinstance(raw.get("event_ref"), str)
                or not raw["event_ref"].strip() or not isinstance(raw.get("corresponding_course_ref"), str)
                or not raw["corresponding_course_ref"].strip()):
            return None
        return {"failure_kind": kind, "event_ref": raw["event_ref"], "corresponding_course_ref": raw["corresponding_course_ref"], "threshold_hours": 24}
    if kind == "critical_change_window_not_mature":
        if raw.get("threshold_hours") != 24 or not isinstance(raw.get("event_ref"), str) or not raw["event_ref"].strip() or not _time(raw.get("event_time")) or not _time(raw.get("deadline_time")):
            return None
        return {"failure_kind": kind, "event_ref": raw["event_ref"], "event_time": raw["event_time"], "deadline_time": raw["deadline_time"], "threshold_hours": 24}
    if kind in {"critical_change_course_timely", "critical_change_course_not_timely"}:
        events = raw.get("change_events")
        if not isinstance(events, list) or not events or len(events) > 20 or raw.get("threshold_hours") != 24:
            return None
        safe = [_safe_009_event(item) for item in events]
        if any(item is None for item in safe):
            return None
        facts: dict[str, Any] = {"failure_kind": kind, "change_events": safe, "threshold_hours": 24}
        if kind == "critical_change_course_timely":
            return facts if all(item["timely"] for item in safe) else None
        unmet = raw.get("unmet_events")
        safe_unmet = [_safe_009_event(item) for item in unmet] if isinstance(unmet, list) and unmet else []
        if not safe_unmet or any(item is None or item["timely"] or item not in safe for item in safe_unmet):
            return None
        facts["unmet_events"] = safe_unmet
        return facts
    scope_ok = raw.get("evaluated_scope") == "critical_daily_course_coverage" and raw.get("pending_scope") == ["condition_change_course_documentation"]
    required, covered = raw.get("required_dates"), raw.get("covered_dates")
    if not scope_ok or raw.get("severity") != "critical" or not isinstance(required, list) or not isinstance(covered, list) or not all(_date(value) for value in [*required, *covered]) or not set(covered).issubset(required):
        return None
    if kind == "critical_daily_record_coverage_satisfied":
        if not required or required != covered or raw.get("missing_count") != 0 or not _date(raw.get("anchor_date")) or not _date(raw.get("horizon_date")):
            return None
        return {"failure_kind": kind, "severity": "critical", "evaluated_scope": "critical_daily_course_coverage", "pending_scope": ["condition_change_course_documentation"], "anchor_date": raw["anchor_date"], "horizon_date": raw["horizon_date"], "required_dates": list(required), "covered_dates": list(covered), "missing_count": 0}
    missing = raw.get("missing_dates")
    count = raw.get("missing_count")
    if kind != "critical_daily_record_missing" or not isinstance(missing, list) or not missing or len(missing) > 7 or not all(_date(value) for value in missing) or type(count) is not int or count < len(missing) or not _date(raw.get("missing_first_date")) or not _date(raw.get("missing_last_date")):
        return None
    facts = {"failure_kind": kind, "severity": "critical", "evaluated_scope": "critical_daily_course_coverage", "pending_scope": ["condition_change_course_documentation"], "required_dates": list(required), "covered_dates": list(covered), "missing_dates": list(missing), "missing_count": count, "missing_first_date": raw["missing_first_date"], "missing_last_date": raw["missing_last_date"]}
    for key in ("anchor_date", "horizon_date"):
        if _date(raw.get(key)):
            facts[key] = raw[key]
    return facts


def _safe_016(raw: Mapping[str, Any]) -> dict[str, Any] | None:
    kind, similarity, relation, sections = raw.get("failure_kind"), raw.get("copy_similarity"), raw.get("copy_relation"), raw.get("compared_sections")
    if (kind not in {"admission_first_course_copy_detected", "admission_first_course_not_identical"}
            or isinstance(similarity, bool) or not isinstance(similarity, (int, float)) or not 0 <= float(similarity) <= 1
            or relation not in {"completely_identical", "not_completely_identical"}
            or (relation == "completely_identical") != (float(similarity) == 1.0)
            or (kind == "admission_first_course_copy_detected") != (relation == "completely_identical")
            or sections != ["入院记录现病史", "首次病程记录病例特点"]):
        return None
    return {"failure_kind": kind, "copy_similarity": round(float(similarity), 4), "copy_relation": relation, "compared_sections": list(sections)}


def _safe_017(raw: Mapping[str, Any]) -> dict[str, Any] | None:
    kind, sources, times = raw.get("failure_kind"), raw.get("copy_document_sources"), raw.get("copy_document_record_times")
    similarity, threshold, pairs = raw.get("copy_similarity"), raw.get("copy_similarity_threshold"), raw.get("copy_match_pairs")
    if (kind not in {"copy_similarity_threshold_exceeded", "copy_similarity_within_threshold"}
            or not isinstance(sources, list) or len(sources) != 2 or any(item not in _COURSE_SOURCES for item in sources)
            or not isinstance(times, list) or len(times) != 2 or not all(_strict_copy_time(item) for item in times)
            or isinstance(similarity, bool) or not isinstance(similarity, (int, float)) or not isfinite(float(similarity)) or not 0 <= float(similarity) <= 1
            or isinstance(threshold, bool) or not isinstance(threshold, (int, float)) or not isfinite(float(threshold)) or float(threshold) != .7
            or (kind == "copy_similarity_threshold_exceeded" and float(similarity) < float(threshold))
            or (kind == "copy_similarity_within_threshold" and float(similarity) >= float(threshold) and pairs)):
        return None
    safe_pairs: list[dict[str, Any]] = []
    if pairs is not None:
        if not isinstance(pairs, list) or len(pairs) > 4:
            return None
        for pair in pairs:
            if not isinstance(pair, Mapping) or set(pair) != {"source_types", "record_times", "similarity"}:
                return None
            ps, pt, pv = pair.get("source_types"), pair.get("record_times"), pair.get("similarity")
            if (not isinstance(ps, list) or len(ps) != 2 or any(item not in _COURSE_SOURCES for item in ps)
                    or not isinstance(pt, list) or len(pt) != 2 or not all(_strict_copy_time(item) for item in pt)
                    or isinstance(pv, bool) or not isinstance(pv, (int, float)) or not 0 <= float(pv) <= 1 or float(pv) < float(threshold)):
                return None
            safe_pairs.append({"source_types": list(ps), "record_times": list(pt), "similarity": round(float(pv), 4)})
        if safe_pairs and (safe_pairs[0]["source_types"] != sources or safe_pairs[0]["record_times"] != times or safe_pairs[0]["similarity"] != round(float(similarity), 4)):
            return None
    # 指纹仅用于执行器消歧；本层不读取、不复验，也不投影。
    return {"failure_kind": kind, "copy_similarity": round(float(similarity), 4), "copy_similarity_threshold": round(float(threshold), 4), "copy_document_sources": list(sources), "copy_document_record_times": list(times), **({"copy_match_pairs": safe_pairs} if pairs is not None else {})}


def safe_course_quality_customer_display_facts(*, rule_id: str, raw: Any) -> dict[str, Any] | None:
    """白名单化客户事实，拒绝 ID、正文、指纹等执行器内部信息。"""
    normalized = str(rule_id or "").strip().upper()
    if normalized not in COURSE_QUALITY_CUSTOMER_RULE_IDS or not isinstance(raw, Mapping):
        return None
    validators = {"LX0609-007": _safe_007, "LX0609-008": _safe_008, "LX0609-009": _safe_009, "LX0609-016": _safe_016, "LX0609-017": _safe_017}
    validator = validators.get(normalized)
    if validator is None:
        # 018 由 CriterionResult 承载受控语义事实；不存在单独 facts 时不触发合同失败。
        return {} if not raw else None
    return validator(raw)


def course_quality_customer_fact_status_is_valid(*, rule_id: str, status: str, raw_facts: Any, safe_facts: Mapping[str, Any] | None) -> bool:
    """仅检查客户事实与已裁决终态是否自洽，不重新判定业务事实。"""
    if not is_course_quality_customer_rule(rule_id):
        return True
    if str(status or "").strip().lower() == "technical_error":
        return True
    if rule_id != "LX0609-017":
        return safe_facts is not None or raw_facts is None
    expected = {"non_compliant": "copy_similarity_threshold_exceeded", "compliant": "copy_similarity_within_threshold"}.get(str(status or "").strip().lower())
    kind = raw_facts.get("failure_kind") if isinstance(raw_facts, Mapping) else None
    if expected is not None:
        return safe_facts is not None and kind == expected
    return kind not in {"copy_similarity_threshold_exceeded", "copy_similarity_within_threshold"}


__all__ = [
    "COURSE_QUALITY_CUSTOMER_RULE_IDS", "course_quality_customer_fact_status_is_valid",
    "is_course_quality_customer_rule", "safe_course_quality_customer_display_facts",
]
