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
    "LX0609-02-01-03", "LX0609-02-01-04", "LX0609-02-01-05", "LX0609-12-01-01", "LX0609-12-01-02", "LX0609-01-01-02",
})
_COURSE_SOURCES = frozenset({"daily_course_record", "senior_course_record"})
_017_THRESHOLD_EXCEEDED_KIND = "copy_similarity_threshold_exceeded"
_017_WITHIN_THRESHOLD_KIND = "copy_similarity_within_threshold"
_017_SEMANTIC_REVIEW_PASSED_KIND = "copy_semantic_review_passed"
_017_TEMPLATE_SHELL_ONLY_KIND = "copy_template_shell_only"
_017_DUPLICATE_SAVE_SUSPECTED_KIND = "copy_duplicate_save_suspected"
_017_HIGH_SIMILARITY_PASS_KINDS = frozenset({
    _017_SEMANTIC_REVIEW_PASSED_KIND,
    _017_TEMPLATE_SHELL_ONLY_KIND,
    _017_DUPLICATE_SAVE_SUSPECTED_KIND,
})
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


def course_007_gap_display(raw: Any) -> tuple[list[str], list[str], str] | None:
    if not isinstance(raw, Mapping) or raw.get("failure_kind") != "course_interval_source_gap":
        return None
    safe = _safe_007(raw)
    if safe is None:
        return None
    source = safe["gap_source"]
    labels = {"inpat_registration": ("本次住院登记", "入院时间"),
              "evaluation_context.horizon": ("质控观察截止资料", "观察截止时间"),
              "daily_course_record": ("日常病程记录", "查房记录时间"),
              "senior_course_record": ("上级医师病程记录", "查房记录时间")}
    label, field = labels[source]
    gap = safe["gap_kind"]
    message = {
        "empty": f"未读取到{label}，无法取得{field}，暂时无法完成查房间隔核对。",
        "unavailable": f"{label}数据源本次不可用，暂时无法完成查房间隔核对。",
        "truncated": f"{label}读取不完整，暂时无法完成查房间隔核对。",
        "ambiguous": f"{label}存在多条记录，无法确定唯一的{field}，暂时无法完成查房间隔核对。",
        "time_missing": f"已读取{label}，但缺少有效的{field}，暂时无法完成查房间隔核对。",
    }[gap]
    if "missing_time_count" in safe:
        label = "上级医师查房记录" if source == "senior_course_record" else "日常查房记录"
        count = safe["missing_time_count"]
        message = f"已读取{safe['record_count']}份{label}，其中{count}份缺少有效的查房记录时间，暂时无法完成查房间隔核对。请通过证据定位核对缺时间文书。"
        field = f"{label}的权威时间（{count}份）"
    return ([label] if gap in {"empty", "unavailable", "truncated"} else [],
            [field] if gap in {"empty", "ambiguous", "time_missing"} else [], message)


def _safe_007(raw: Mapping[str, Any]) -> dict[str, Any] | None:
    kind = raw.get("failure_kind")
    if kind == "course_interval_source_gap":
        source, gap = raw.get("gap_source"), raw.get("gap_kind")
        if (not isinstance(source, str) or source not in {"inpat_registration", "evaluation_context.horizon", "daily_course_record", "senior_course_record"}
            or not isinstance(gap, str) or gap not in {"empty", "ambiguous", "time_missing", "unavailable", "truncated"}):
            return None
        facts = {"failure_kind": kind, "gap_source": source, "gap_kind": gap}
        if "record_count" in raw or "missing_time_count" in raw:
            count, missing = raw.get("record_count"), raw.get("missing_time_count")
            if (source not in _COURSE_SOURCES or gap != "time_missing"
                or type(count) is not int or type(missing) is not int or not 0 < missing <= count):
                return None
            facts.update(record_count=count, missing_time_count=missing)
        return facts
    if kind == "course_interval_capacity_exceeded":
        start = _strict_copy_time(raw.get("admission_time"))
        end = _strict_copy_time(raw.get("horizon_lower_bound_time"))
        precision = raw.get("horizon_precision")
        known, missing, required = (raw.get(key) for key in (
            "known_record_count", "missing_time_count", "minimum_required_records"))
        if (not start or not end or start >= end
            or precision not in {"datetime", "date"}
            or (precision == "date" and not end.endswith("00:00:00"))
            or not all(type(value) is int for value in (known, missing, required))
            or known < 0 or not 0 < missing < required
            or type(raw.get("threshold_hours")) is not int or raw["threshold_hours"] != 72):
            return None
        return {"failure_kind": kind, "admission_time": start,
                "horizon_lower_bound_time": end, "horizon_precision": precision,
                "known_record_count": known, "missing_time_count": missing,
                "minimum_required_records": required, "threshold_hours": 72}
    if kind == "unstable_patient_order_present":
        return ({"failure_kind": kind, "stable_course_rule_applicable": False}
                if raw.get("stable_course_rule_applicable") is False else None)
    start_source, end_source = raw.get("interval_start_source"), raw.get("interval_end_source")
    dates = raw.get("recorded_dates")
    if (
        kind not in {"course_record_interval_over_72h", "course_record_interval_within_72h"}
        or start_source not in _COURSE_SOURCES | {"inpat_registration", "admission_record"}
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
        # 带秒事实以精确秒核对阈值；下方仍验证原始时间、秒与展示小时一致。
        duration = raw.get("interval_seconds")
        threshold = 72 * 3600
        if type(duration) is not int:
            duration, threshold = interval, 72
        if (raw.get("interval_end_precision") is not None or raw.get("interval_end_date") is not None
                or not _time(raw.get("interval_end_time")) or isinstance(interval, bool)
                or not isinstance(interval, (int, float))
                or (kind == "course_record_interval_over_72h" and duration <= threshold)
                or (kind == "course_record_interval_within_72h" and duration > threshold)):
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


def validate_published_course_007_facts(raw: Any) -> dict[str, Any] | None:
    """只校验 007 已发布 JSON 事实，不重新投影或舍入。"""

    if not isinstance(raw, dict) or any(type(key) is not str for key in raw):
        return None
    kind = raw.get("failure_kind")
    if type(kind) is not str:
        return None
    keys = set(raw)
    if kind == "unstable_patient_order_present":
        return dict(raw) if keys == {"failure_kind", "stable_course_rule_applicable"} and raw["stable_course_rule_applicable"] is False else None
    if kind == "course_interval_source_gap":
        base = {"failure_kind", "gap_source", "gap_kind"}
        counts = {"record_count", "missing_time_count"}
        source, gap = raw.get("gap_source"), raw.get("gap_kind")
        if (type(source) is not str or source not in {"inpat_registration", "evaluation_context.horizon", "daily_course_record", "senior_course_record"}
                or type(gap) is not str or gap not in {"empty", "ambiguous", "time_missing", "unavailable", "truncated"}
                or (keys != base and keys != base | counts)):
            return None
        if keys == base | counts and (
            source not in _COURSE_SOURCES or gap != "time_missing"
            or type(raw["record_count"]) is not int or type(raw["missing_time_count"]) is not int
            or not 0 < raw["missing_time_count"] <= raw["record_count"]
        ):
            return None
        return dict(raw)
    if kind == "course_interval_capacity_exceeded":
        expected = {"failure_kind", "admission_time", "horizon_lower_bound_time", "horizon_precision",
                    "known_record_count", "missing_time_count", "minimum_required_records", "threshold_hours"}
        known, missing, required = (raw.get(key) for key in (
            "known_record_count", "missing_time_count", "minimum_required_records"))
        if (keys != expected or not _strict_copy_time(raw.get("admission_time"))
                or not _strict_copy_time(raw.get("horizon_lower_bound_time"))
                or raw["admission_time"] >= raw["horizon_lower_bound_time"]
                or type(raw.get("horizon_precision")) is not str
                or raw["horizon_precision"] not in {"datetime", "date"}
                or (raw["horizon_precision"] == "date" and not raw["horizon_lower_bound_time"].endswith("00:00:00"))
                or not all(type(value) is int for value in (known, missing, required))
                or known < 0 or not 0 < missing < required
                or type(raw.get("threshold_hours")) is not int or raw["threshold_hours"] != 72):
            return None
        return dict(raw)

    if kind not in {"course_record_interval_over_72h", "course_record_interval_within_72h"}:
        return None
    base = {"failure_kind", "interval_start_source", "interval_end_source", "interval_start_time",
            "threshold_hours", "recorded_dates"}
    dated = base | {"interval_end_date", "interval_end_precision"}
    timed = base | {"interval_end_time", "interval_hours"}
    enhanced = {"interval_start_position", "interval_end_position", "record_count",
                "interval_seconds", "overdue_seconds"}
    if keys not in (dated, dated | (enhanced - {"interval_seconds", "overdue_seconds"}), timed, timed | enhanced):
        return None
    start_source, end_source = raw.get("interval_start_source"), raw.get("interval_end_source")
    dates = raw.get("recorded_dates")
    if (type(start_source) is not str or start_source not in _COURSE_SOURCES | {"inpat_registration", "admission_record"}
            or type(end_source) is not str or end_source not in _COURSE_SOURCES | {"evaluation_context.horizon"}
            or not _time(raw.get("interval_start_time"))
            or type(raw.get("threshold_hours")) is not int or raw["threshold_hours"] != 72
            or not isinstance(dates, list) or len(dates) > 64
            or not all(_date(item) for item in dates)):
        return None
    date_only = "interval_end_date" in keys
    if date_only:
        if (kind != "course_record_interval_over_72h" or end_source != "evaluation_context.horizon"
                or raw.get("interval_end_precision") != "date" or not _date(raw.get("interval_end_date"))):
            return None
        try:
            if datetime.strptime(raw["interval_end_date"], "%Y-%m-%d").date() <= (
                datetime.strptime(raw["interval_start_time"], "%Y-%m-%d %H:%M:%S") + timedelta(hours=72)
            ).date():
                return None
        except ValueError:
            return None
    else:
        hours = raw.get("interval_hours")
        try:
            finite_hours = type(hours) in {int, float} and isfinite(float(hours))
        except (OverflowError, ValueError):
            finite_hours = False
        if (not _time(raw.get("interval_end_time")) or not finite_hours
                or hours < 0 or hours != round(float(hours), 2)
                or (kind == "course_record_interval_within_72h" and hours > 72)):
            return None
    if keys - (dated if date_only else timed):
        start, end, count = (raw.get(key) for key in (
            "interval_start_position", "interval_end_position", "record_count"))
        if (not all(type(value) is int for value in (start, end, count))
                or not 0 <= start < end <= count + 1 or end != start + 1
                or count != len(dates) or (date_only and end != count + 1)):
            return None
        if not date_only:
            seconds, overdue = raw.get("interval_seconds"), raw.get("overdue_seconds")
            if type(seconds) is not int or type(overdue) is not int:
                return None
            try:
                actual = round((datetime.strptime(raw["interval_end_time"], "%Y-%m-%d %H:%M:%S")
                                - datetime.strptime(raw["interval_start_time"], "%Y-%m-%d %H:%M:%S")).total_seconds())
            except ValueError:
                return None
            if (actual <= 0 or seconds != actual or overdue != max(0, actual - 72 * 3600)
                    or round(actual / 3600, 2) != raw["interval_hours"]):
                return None
    return dict(raw)


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
    if (kind not in {
                _017_THRESHOLD_EXCEEDED_KIND,
                _017_WITHIN_THRESHOLD_KIND,
                *_017_HIGH_SIMILARITY_PASS_KINDS,
            }
            or not isinstance(sources, list) or len(sources) != 2 or any(item not in _COURSE_SOURCES for item in sources)
            or not isinstance(times, list) or len(times) != 2 or not all(_strict_copy_time(item) for item in times)
            or isinstance(similarity, bool) or not isinstance(similarity, (int, float)) or not isfinite(float(similarity)) or not 0 <= float(similarity) <= 1
            or isinstance(threshold, bool) or not isinstance(threshold, (int, float)) or not isfinite(float(threshold)) or float(threshold) != .7
            or (kind in {
                _017_THRESHOLD_EXCEEDED_KIND,
                *_017_HIGH_SIMILARITY_PASS_KINDS,
            } and float(similarity) < float(threshold))
            or (kind == _017_WITHIN_THRESHOLD_KIND and float(similarity) >= float(threshold))):
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


def _published_number(value: Any, places: int) -> bool:
    if type(value) not in {int, float}:
        return False
    try:
        return isfinite(value) and 0 <= value <= 1 and value == round(value, places)
    except (OverflowError, ValueError):
        return False


def _published_dates(value: Any, *, maximum: int | None = 64) -> bool:
    return (type(value) is list and (maximum is None or len(value) <= maximum)
            and all(_date(item) for item in value))


def _published_009_event(item: Any) -> bool:
    keys = {"event_ref", "change_category", "event_time", "corresponding_course_ref",
            "corresponding_course_time", "deadline_time", "threshold_hours", "timely"}
    if type(item) is not dict or set(item) != keys:
        return False
    event_ref, course_ref = item["event_ref"], item["corresponding_course_ref"]
    return (type(event_ref) is str and bool(event_ref.strip()) and len(event_ref) <= 256
            and type(course_ref) is str and len(course_ref) <= 256
            and type(item["change_category"]) is str
            and item["change_category"] in {"subjective", "objective", "exam_lab", "complication", "special_state"}
            and _time(item["event_time"]) and _time(item["deadline_time"])
            and (_time(item["corresponding_course_time"])
                 if course_ref else item["corresponding_course_time"] == "")
            and type(item["threshold_hours"]) is int and item["threshold_hours"] == 24
            and type(item["timely"]) is bool)


def _published_008(raw: dict[str, Any]) -> bool:
    kind = raw.get("failure_kind")
    base = {"failure_kind", "severity", "threshold_days", "anchor_date", "horizon_date"}
    if (type(kind) is not str or kind not in {"severity_course_gap_exceeded", "severity_course_interval_satisfied"}
            or raw.get("severity") != "serious" or type(raw.get("threshold_days")) is not int
            or raw["threshold_days"] != 2 or not _date(raw.get("anchor_date"))
            or not _date(raw.get("horizon_date"))):
        return False
    if kind == "severity_course_gap_exceeded":
        gap = {"gap_start_date", "gap_end_date", "gap_days"}
        if set(raw) not in (base | gap, base | gap | {"recorded_dates"}):
            return False
        return (_date(raw["gap_start_date"]) and _date(raw["gap_end_date"])
                and type(raw["gap_days"]) is int and raw["gap_days"] > 2
                and ("recorded_dates" not in raw or _published_dates(raw["recorded_dates"])))
    return (set(raw) == base | {"maximum_gap_days", "recorded_dates"}
            and type(raw["maximum_gap_days"]) is int and 0 <= raw["maximum_gap_days"] <= 2
            and _published_dates(raw["recorded_dates"]))


def _published_009(raw: dict[str, Any]) -> bool:
    kind = raw.get("failure_kind")
    if type(kind) is not str:
        return False
    if kind.startswith("critical_change_") and (
        type(raw.get("threshold_hours")) is not int or raw["threshold_hours"] != 24
    ):
        return False
    if kind == "critical_change_time_unavailable":
        return set(raw) == {"failure_kind", "threshold_hours"}
    if kind == "critical_change_course_association_failed":
        return (set(raw) == {"failure_kind", "event_ref", "corresponding_course_ref", "threshold_hours"}
                and all(type(raw[key]) is str and raw[key].strip() for key in ("event_ref", "corresponding_course_ref")))
    if kind == "critical_change_window_not_mature":
        return (set(raw) == {"failure_kind", "event_ref", "event_time", "deadline_time", "threshold_hours"}
                and type(raw["event_ref"]) is str and bool(raw["event_ref"].strip())
                and _time(raw["event_time"]) and _time(raw["deadline_time"]))
    if kind in {"critical_change_course_timely", "critical_change_course_not_timely"}:
        base = {"failure_kind", "change_events", "threshold_hours"}
        if set(raw) != (base if kind == "critical_change_course_timely" else base | {"unmet_events"}):
            return False
        events = raw["change_events"]
        if type(events) is not list or not 0 < len(events) <= 20 or not all(_published_009_event(item) for item in events):
            return False
        if kind == "critical_change_course_timely":
            return all(item["timely"] for item in events)
        unmet = raw["unmet_events"]
        return (type(unmet) is list and bool(unmet)
                and all(_published_009_event(item) and item["timely"] is False and item in events for item in unmet))
    base = {"failure_kind", "severity", "evaluated_scope", "pending_scope", "required_dates", "covered_dates", "missing_count"}
    if (kind not in {"critical_daily_record_coverage_satisfied", "critical_daily_record_missing"}
            or raw.get("severity") != "critical" or raw.get("evaluated_scope") != "critical_daily_course_coverage"
            or raw.get("pending_scope") != ["condition_change_course_documentation"]
            or not _published_dates(raw.get("required_dates"), maximum=None)
            or not _published_dates(raw.get("covered_dates"), maximum=None)
            or not set(raw["covered_dates"]).issubset(raw["required_dates"])):
        return False
    if kind == "critical_daily_record_coverage_satisfied":
        return (set(raw) == base | {"anchor_date", "horizon_date"}
                and bool(raw["required_dates"]) and raw["required_dates"] == raw["covered_dates"]
                and type(raw["missing_count"]) is int and raw["missing_count"] == 0
                and _date(raw["anchor_date"]) and _date(raw["horizon_date"]))
    optional = {"anchor_date", "horizon_date"}
    required = base | {"missing_dates", "missing_first_date", "missing_last_date"}
    missing = raw.get("missing_dates")
    return (required <= set(raw) <= required | optional
            and _published_dates(missing, maximum=7) and bool(missing)
            and type(raw["missing_count"]) is int and raw["missing_count"] >= len(missing)
            and _date(raw["missing_first_date"]) and _date(raw["missing_last_date"])
            and all(_date(raw[key]) for key in optional & set(raw)))


def _published_016(raw: dict[str, Any]) -> bool:
    kind, relation, similarity = raw.get("failure_kind"), raw.get("copy_relation"), raw.get("copy_similarity")
    return (set(raw) == {"failure_kind", "copy_similarity", "copy_relation", "compared_sections"}
            and type(kind) is str and kind in {"admission_first_course_copy_detected", "admission_first_course_not_identical"}
            and _published_number(similarity, 4)
            and type(relation) is str and relation in {"completely_identical", "not_completely_identical"}
            and (relation == "completely_identical") == (similarity == 1)
            and (kind == "admission_first_course_copy_detected") == (relation == "completely_identical")
            and type(raw["compared_sections"]) is list
            and raw["compared_sections"] == ["入院记录现病史", "首次病程记录病例特点"])


def _published_017_pair(pair: Any) -> bool:
    return (type(pair) is dict and set(pair) == {"source_types", "record_times", "similarity"}
            and type(pair["source_types"]) is list and len(pair["source_types"]) == 2
            and all(type(item) is str and item in _COURSE_SOURCES for item in pair["source_types"])
            and type(pair["record_times"]) is list and len(pair["record_times"]) == 2
            and all(_strict_copy_time(item) for item in pair["record_times"])
            and _published_number(pair["similarity"], 4) and pair["similarity"] >= .7)


def _published_017(raw: dict[str, Any]) -> bool:
    base = {"failure_kind", "copy_similarity", "copy_similarity_threshold", "copy_document_sources", "copy_document_record_times"}
    kind = raw.get("failure_kind")
    if (set(raw) not in (base, base | {"copy_match_pairs"}) or type(kind) is not str
            or kind not in {_017_THRESHOLD_EXCEEDED_KIND, _017_WITHIN_THRESHOLD_KIND, *_017_HIGH_SIMILARITY_PASS_KINDS}
            or not _published_number(raw["copy_similarity"], 4)
            or not _published_number(raw["copy_similarity_threshold"], 4)
            or raw["copy_similarity_threshold"] != .7
            or type(raw["copy_document_sources"]) is not list or len(raw["copy_document_sources"]) != 2
            or any(type(item) is not str or item not in _COURSE_SOURCES for item in raw["copy_document_sources"])
            or type(raw["copy_document_record_times"]) is not list or len(raw["copy_document_record_times"]) != 2
            or not all(_strict_copy_time(item) for item in raw["copy_document_record_times"])):
        return False
    similarity = raw["copy_similarity"]
    if (kind == _017_WITHIN_THRESHOLD_KIND) != (similarity < .7):
        return False
    if "copy_match_pairs" in raw:
        pairs = raw["copy_match_pairs"]
        if (type(pairs) is not list or len(pairs) > 4 or not all(_published_017_pair(pair) for pair in pairs)):
            return False
        if pairs and (pairs[0]["source_types"] != raw["copy_document_sources"]
                      or pairs[0]["record_times"] != raw["copy_document_record_times"]
                      or pairs[0]["similarity"] != similarity):
            return False
    return True


def validate_published_course_quality_facts(
    *, rule_id: str, raw: Any, status: str = "", reason_code: str = "",
) -> tuple[bool, dict[str, Any] | None]:
    """返回合同是否有效及原值；仅明确的无触发终态可缺少独立 facts。"""
    normalized = str(rule_id or "").strip().upper()
    # 007 执行器在观察窗尚未成熟时直接短路，尚无病程区间事实可发布。
    # 仅接受这一明确终态；其他状态和原因仍执行原事实合同。
    if (
        normalized == "LX0609-02-01-03"
        and (raw is None or raw == {})
        and status == "not_applicable"
        and reason_code == "evaluation_window_not_mature"
    ):
        return True, None
    # 016 的目标段落不可读时没有可发布的相似度；仅接受已知资料不足终态。
    # 确定结论及非空残缺 facts 仍须通过原比较事实合同。
    if (
        normalized in {"LX0609-12-01-01", "LX0609-12-01-02"}
        and (raw is None or raw == {})
        and status == "data_gap"
        and reason_code == "required_field_missing"
    ):
        return True, None
    if normalized == "LX0609-01-01-02" and raw is None:
        return True, None
    if (
        normalized in {
            "LX0609-02-01-04", "LX0609-02-01-05",
            "LX0609-12-01-01", "LX0609-12-01-02",
        }
        and (raw is None or raw == {})
        and status == "not_applicable"
        and (
            reason_code == "trigger_absent_complete"
            or (normalized == "LX0609-12-01-02" and reason_code == "eligibility_not_met")
        )
    ):
        # 无触发事件时无需构造病程区间或复制比对事实；确定问题仍必须带事实。
        return True, None
    if type(raw) is not dict or any(type(key) is not str for key in raw):
        return False, None
    if normalized == "LX0609-02-01-03":
        validated = validate_published_course_007_facts(raw)
        return validated is not None, validated
    if normalized == "LX0609-01-01-02":
        return (True, {}) if not raw else (False, None)
    validators = {"LX0609-02-01-04": _published_008, "LX0609-02-01-05": _published_009,
                  "LX0609-12-01-01": _published_016, "LX0609-12-01-02": _published_017}
    validator = validators.get(normalized)
    if validator is None or not validator(raw):
        return False, None
    if normalized == "LX0609-12-01-02" and (
        status not in {"compliant", "non_compliant", "data_gap", "not_applicable"}
        or not course_quality_customer_fact_status_is_valid(
            rule_id=normalized, status=status, raw_facts=raw, safe_facts=raw,
        )
    ):
        return False, None
    return True, dict(raw)


def safe_course_quality_customer_display_facts(*, rule_id: str, raw: Any) -> dict[str, Any] | None:
    """白名单化客户事实，拒绝 ID、正文、指纹等执行器内部信息。"""
    normalized = str(rule_id or "").strip().upper()
    if normalized not in COURSE_QUALITY_CUSTOMER_RULE_IDS or not isinstance(raw, Mapping):
        return None
    validators = {"LX0609-02-01-03": _safe_007, "LX0609-02-01-04": _safe_008, "LX0609-02-01-05": _safe_009, "LX0609-12-01-01": _safe_016, "LX0609-12-01-02": _safe_017}
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
        return rule_id != "LX0609-12-01-02" or safe_facts is None
    if rule_id == "LX0609-02-01-03" and isinstance(raw_facts, Mapping) and raw_facts.get("failure_kind") == "course_interval_source_gap":
        return safe_facts is not None and status == "data_gap"
    if rule_id == "LX0609-02-01-03" and isinstance(raw_facts, Mapping) and raw_facts.get("failure_kind") == "course_interval_capacity_exceeded":
        return safe_facts is not None and status == "non_compliant"
    if rule_id != "LX0609-12-01-02":
        return safe_facts is not None or raw_facts is None
    normalized_status = str(status or "").strip().lower()
    kind = raw_facts.get("failure_kind") if isinstance(raw_facts, Mapping) else None
    if normalized_status == "non_compliant":
        return safe_facts is not None and kind == _017_THRESHOLD_EXCEEDED_KIND
    if normalized_status == "compliant":
        if safe_facts is None:
            return False
        safe_kind = safe_facts.get("failure_kind")
        similarity = safe_facts.get("copy_similarity")
        threshold = safe_facts.get("copy_similarity_threshold")
        if not isinstance(similarity, (int, float)) or not isinstance(threshold, (int, float)):
            return False
        if safe_kind == _017_WITHIN_THRESHOLD_KIND:
            return kind == safe_kind and float(similarity) < float(threshold)
        return (
            kind == safe_kind
            and safe_kind in _017_HIGH_SIMILARITY_PASS_KINDS
            and float(similarity) >= float(threshold)
        )
    return kind not in {
        _017_THRESHOLD_EXCEEDED_KIND,
        _017_WITHIN_THRESHOLD_KIND,
        *_017_HIGH_SIMILARITY_PASS_KINDS,
    }


__all__ = [
    "COURSE_QUALITY_CUSTOMER_RULE_IDS", "course_quality_customer_fact_status_is_valid",
    "is_course_quality_customer_rule", "safe_course_quality_customer_display_facts",
    "validate_published_course_quality_facts", "validate_published_course_007_facts",
]
