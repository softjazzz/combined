"""061/062/063/067/068 出院文书规则的客户展示事实合同。

本模块只白名单化原生执行器已经裁决的事实，并校验其与最终状态自洽。它不
读取任何文书材料，也不生成客户证据；证据只能沿
``RuleDecision.fact_refs → Binding → 公共 selected-document projector`` 主链投影。
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime, timedelta
import math
import logging
import re
from typing import Any

from .extended_document.discharge_diagnosis_equivalence import (
    map_equivalent_diagnoses,
    valid_equivalent_pairs,
)
from .extended_document.discharge_course_content import FIELDS, PUBLISHED_SOURCES, content_state
from .extended_document.discharge_course_stages import valid_review


def _safe_course_content(raw: Mapping[str, Any]) -> dict[str, Any] | None:
    """验证原样发布的原子状态和受控文本坐标，不重读材料或修补事实。"""
    if raw.get("verification_kind") == "discharge_course_pending":
        return dict(raw) if set(raw) == {"verification_kind", "state"} and isinstance(raw.get("state"), str) and raw.get("state") in {
            "data_gap", "not_applicable",
        } else None
    expected_keys = {"verification_kind", "documents", "checks", "events"}
    if "review" in raw:
        expected_keys.add("review")
    if set(raw) != expected_keys or raw.get("verification_kind") != "discharge_course_content":
        return None
    documents, checks, events = raw["documents"], raw["checks"], raw["events"]
    if not all(isinstance(v, list) for v in (documents, checks, events)) or not 1 <= len(documents) <= 80 or len(events) > 1600:
        return None
    lookup = {}
    for index, doc in enumerate(documents, 1):
        expected = {"document_index", "source", "document_ref", "text_length"}
        if isinstance(doc, dict) and doc.get("source") == "discharge_record_diagnosis":
            expected.add("parent_document_index")
            parent = doc.get("parent_document_index")
            if type(parent) is not int or lookup.get(parent, {}).get("source") != "discharge_record":
                return None
        if (not isinstance(doc, dict) or set(doc) != expected
                or type(doc["document_index"]) is not int or doc["document_index"] != index
                or doc["source"] not in PUBLISHED_SOURCES or type(doc["text_length"]) is not int
                or not 0 < doc["text_length"] <= 60000 or not isinstance(doc["document_ref"], str)
                or re.fullmatch(r"[0-9a-f]{64}", doc["document_ref"]) is None):
            return None
        lookup[index] = doc
    discharge_ids = {i for i, d in lookup.items() if d["source"] == "discharge_record"}
    if not discharge_ids:
        return None

    def valid_span(item: Mapping[str, Any], index: int) -> bool:
        if not isinstance(item.get("state"), str) or item.get("state") not in {"present", "missing", "uncertain"}:
            return False
        start, end = item.get("start"), item.get("end")
        return (type(start) is int and type(end) is int and 0 <= start < end <= lookup[index]["text_length"]
                if item["state"] == "present" else start is None and end is None)

    seen = set()
    for check in checks:
        if not isinstance(check, dict) or set(check) != {"document_index", "field", "state", "start", "end"}:
            return None
        index, field = check["document_index"], check["field"]
        if (type(index) is not int or index not in discharge_ids or not isinstance(field, str)
                or field not in FIELDS or (index, field) in seen or not valid_span(check, index)):
            return None
        seen.add((index, field))
    if seen != {(i, f) for i in discharge_ids for f in FIELDS}:
        return None
    surgery_checked = set()
    for event in events:
        if not isinstance(event, dict) or set(event) != {"document_index", "kind", "start", "end", "matches"}:
            return None
        index = event["document_index"]
        if (type(index) is not int or index not in lookup or index in discharge_ids
                or lookup[index]["source"] == "discharge_record_diagnosis"
                or not isinstance(event["kind"], str) or event["kind"] not in {"surgery", "test", "treatment", "change"}
                or not valid_span({**event, "state": "present"}, index)
                or not isinstance(event["matches"], list)):
            return None
        if event["kind"] == "surgery":
            surgery_checked.add(index)
        matched = set()
        for match in event["matches"]:
            if not isinstance(match, dict) or set(match) != {"document_index", "state", "start", "end"}:
                return None
            target = match["document_index"]
            if type(target) is not int or target not in discharge_ids or target in matched or not valid_span(match, target):
                return None
            matched.add(target)
        if matched != discharge_ids:
            return None
    review = raw.get("review")
    if "review" in raw and not valid_review(review, lookup, checks, events):
        return None
    b_failed = isinstance(review, dict) and review["stages"]["B"] == "failed"
    if not b_failed and not {i for i, d in lookup.items() if d["source"] == "surgery_record"} <= surgery_checked:
        return None
    return dict(raw)


DISCHARGE_CUSTOMER_RULE_IDS = frozenset(
    {
        "LX0609-08-01-01",
        "LX0609-08-01-02",
        "LX0609-08-01-03",
        "LX0609-08-01-05",
        "LX0609-08-02-01",
        "LX0609-08-02-02",
    }
)

_DATE = re.compile(r"\d{4}-\d{2}-\d{2}")
_DATETIME = re.compile(
    r"\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}:\d{2}"
    r"(?:\.\d{1,6})?(?:Z|[+-]\d{2}:?\d{2})?"
)
_TIME_SOURCES = frozenset(
    {
        "inpat_registration.discharge_datetime",
        "inpat_registration.discharge_time",
        "discharge_record.discharge_datetime",
        "discharge_record.discharge_time",
        "discharge_record.discharge_date",
        "evaluation_context.horizon",
    }
)
_LEGACY_INTERNAL_KEYS = frozenset(
    {
        "source_document_id",
        "source_document_ids",
        "source_document_refs",
        "raw_record_content",
    }
)


def is_discharge_customer_rule(rule_id: str) -> bool:
    """返回由出院文书规则族拥有展示事实合同的规则。"""

    return str(rule_id or "").strip().upper() in DISCHARGE_CUSTOMER_RULE_IDS


def _safe_datetime(value: Any) -> str:
    if not isinstance(value, str) or _DATETIME.fullmatch(value) is None:
        return ""
    try:
        datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return ""
    return value


def _safe_date(value: Any) -> str:
    if not isinstance(value, str) or _DATE.fullmatch(value) is None:
        return ""
    try:
        datetime.fromisoformat(f"{value}T00:00:00")
    except ValueError:
        return ""
    return value


def _safe_number(value: Any, *, minimum: float = 0) -> float | int | None:
    if (
        not isinstance(value, (int, float))
        or isinstance(value, bool)
        or not math.isfinite(float(value))
        or value < minimum
    ):
        return None
    return round(float(value), 2) if isinstance(value, float) else value


def _safe_text_list(
    value: Any,
    *,
    minimum: int = 0,
    maximum: int = 100,
    item_maximum: int = 160,
) -> list[str] | None:
    if not isinstance(value, (list, tuple)) or not minimum <= len(value) <= maximum:
        return None
    if any(
        not isinstance(item, str)
        or not item
        or len(item) > item_maximum
        or "\n" in item
        or "\r" in item
        for item in value
    ):
        return None
    return list(value)


def _safe_061(raw: Mapping[str, Any]) -> dict[str, Any] | None:
    allowed = {
        "verification_kind",
        "discharge_time",
        "discharge_time_source",
        "record_time",
        "threshold_hours",
        "actual_interval_hours",
        "conflicting_discharge_times",
    }
    if (
        not set(raw).issubset(allowed | _LEGACY_INTERNAL_KEYS)
        or raw.get("verification_kind") != "discharge_record_timeliness_check"
        or raw.get("threshold_hours") != 24
    ):
        return None
    conflict_raw = raw.get("conflicting_discharge_times")
    if conflict_raw is not None:
        conflicts = _safe_text_list(conflict_raw, minimum=2, item_maximum=40)
        if conflicts is None:
            return None
        try:
            parsed = tuple(
                datetime.fromisoformat(item.replace("Z", "+00:00"))
                for item in conflicts
            )
        except ValueError:
            return None
        if (
            len(set(parsed)) != len(parsed)
            or tuple(sorted(parsed)) != parsed
            or raw.get("discharge_time") is not None
            or raw.get("record_time") is not None
            or raw.get("actual_interval_hours") is not None
            or raw.get("discharge_time_source") is not None
        ):
            return None
        return {
            "verification_kind": "discharge_record_timeliness_check",
            "discharge_time": None,
            "record_time": None,
            "threshold_hours": 24,
            "actual_interval_hours": None,
            "conflicting_discharge_times": conflicts,
        }
    discharge_time = _safe_datetime(raw.get("discharge_time"))
    if not discharge_time:
        return None
    record_raw = raw.get("record_time")
    record_time = None if record_raw is None else _safe_datetime(record_raw)
    if record_raw is not None and not record_time:
        return None
    interval_raw = raw.get("actual_interval_hours")
    interval = None if interval_raw is None else _safe_number(interval_raw, minimum=-math.inf)
    if interval_raw is not None and interval is None:
        return None
    # 执行器以负时间差表达权威时间冲突；保留符号和精度，避免负一秒
    # 被四舍五入成 -0.0 后误认为合规。其他规则仍使用非负数值合同。
    if interval_raw is not None and interval_raw < 0:
        interval = interval_raw
    source = raw.get("discharge_time_source")
    if source is not None and source not in _TIME_SOURCES:
        return None
    return {
        "verification_kind": "discharge_record_timeliness_check",
        "discharge_time": discharge_time,
        **({"discharge_time_source": source} if source is not None else {}),
        "record_time": record_time,
        "threshold_hours": 24,
        "actual_interval_hours": interval,
    }


def _reject_062(category: str) -> None:
    # 仅由以下固定调用点给出类别；不记录字段值、药品、文书标识或原异常。
    logging.getLogger(__name__).warning("discharge_medication facts rejected category=%s", category)


def _proven_prescription_omission(raw: Mapping[str, Any]) -> bool:
    """出院记录0项带药只在正式出院处方已核对且列出漏写药物时成立（2026-11-17 F5）。

    “没有提取到用药”由抽取待定事实承载、“确实无出院用药”为不适用，均不得走此分支。
    """
    count = raw.get("prescription_medication_count")
    names = raw.get("missing_drug_names")
    missing = raw.get("missing_fields")
    # 0项带药时不存在可核对的剂量/途径/疗程，缺项只能是药名本身。
    return (type(count) is int and count > 0 and isinstance(names, list) and bool(names)
            and missing == ["drug_name"])


def _safe_062(raw: Mapping[str, Any]) -> dict[str, Any] | None:
    if raw.get("verification_kind") == "discharge_medication_extraction_pending":
        if (set(raw) != {"verification_kind", "extraction_state"}
                or raw.get("extraction_state") not in ("unknown", "data_gap", "technical_error")):
            return _reject_062("pending_contract")
        return dict(raw)
    if raw.get("verification_kind") == "discharge_medication_prescription_identity_gap":
        if (
            set(raw) != {"verification_kind", "gap_reason", "affected_prescription_item_count"}
            or raw.get("gap_reason") not in {"source_unavailable", "identity_missing", "too_many_items"}
            or type(raw.get("affected_prescription_item_count")) is not int
            or not 0 <= raw["affected_prescription_item_count"] <= 500
            or (raw["gap_reason"] == "identity_missing" and raw["affected_prescription_item_count"] <= 0)
            or (raw["gap_reason"] == "too_many_items" and raw["affected_prescription_item_count"] <= 20)
        ):
            return _reject_062("identity_gap_contract")
        return dict(raw)
    required = ["drug_name", "dose", "route", "duration"]
    if (
        not set(raw).issubset(
            {
            "verification_kind",
            "medication_count",
            "required_fields",
            "missing_fields",
            "prescription_medication_count",
            "missing_drug_names",
            }
            | _LEGACY_INTERNAL_KEYS
        )
        or raw.get("verification_kind") != "discharge_medication_completeness_check"
    ):
        return _reject_062("field_contract")
    if (type(raw.get("medication_count")) is not int or raw["medication_count"] < 0
            or (raw["medication_count"] == 0 and not _proven_prescription_omission(raw))):
        return _reject_062("medication_count")
    if raw.get("required_fields") != required:
        return _reject_062("required_fields")
    missing = _safe_text_list(raw.get("missing_fields"), maximum=len(required))
    if missing is None or any(item not in required for item in missing):
        return _reject_062("missing_fields")
    safe = {
        "verification_kind": "discharge_medication_completeness_check",
        "medication_count": raw["medication_count"],
        "required_fields": required,
        "missing_fields": missing,
    }
    has_prescription_count = "prescription_medication_count" in raw
    has_missing_names = "missing_drug_names" in raw
    if has_prescription_count != has_missing_names:
        return _reject_062("prescription_pair")
    if has_prescription_count:
        count = raw.get("prescription_medication_count")
        names = _safe_text_list(raw.get("missing_drug_names"), maximum=20)
        if (
            type(count) is not int or not 0 <= count <= 20 or names is None
            or len(names) > count or len(names) != len(set(names))
            or (names and "drug_name" not in missing)
        ):
            return _reject_062("prescription_consistency")
        safe["prescription_medication_count"] = count
        safe["missing_drug_names"] = names
    return safe


def _safe_main_diagnosis_check(raw: Mapping[str, Any]) -> dict[str, Any] | None:
    keys = {"verification_kind", "authoritative_main", "written_main", "main_consistent"}
    if "diagnosis_scope" in raw:
        keys.add("diagnosis_scope")
    if (
        set(raw) != keys
        or any(type(raw.get(key)) is not str or not raw[key].strip() for key in ("authoritative_main", "written_main"))
        or type(raw.get("main_consistent")) is not bool
        or (raw["authoritative_main"] == raw["written_main"] and raw["main_consistent"] is not True)
    ):
        return None
    return dict(raw)


def _safe_063(raw: Mapping[str, Any]) -> dict[str, Any] | None:
    if raw.get("verification_kind") == "discharge_main_diagnosis_check":
        if "diagnosis_scope" in raw and raw["diagnosis_scope"] != "death":
            return None
        return _safe_main_diagnosis_check(raw)
    if "diagnosis_scope" in raw and (type(raw["diagnosis_scope"]) is not str or raw["diagnosis_scope"] not in {"death", "discharge"}):
        return None
    scope_gap_values = {"scope_conflict", "scope_unknown"}
    if any(type(raw.get(key)) is str and raw[key] in scope_gap_values for key in ("authoritative_gap", "written_gap")):
        if (raw.get("verification_kind") != "discharge_diagnosis_data_gap"
                or type(raw.get("authoritative_gap")) is not str
                or raw["authoritative_gap"] not in scope_gap_values
                or raw.get("written_gap") is not None or "diagnosis_scope" in raw):
            return None
    if raw.get("verification_kind") == "discharge_diagnosis_data_gap":
        allowed = {"verification_kind", "authoritative_gap", "written_gap"}
        if "diagnosis_scope" in raw:
            allowed.add("diagnosis_scope")
        gaps = (raw.get("authoritative_gap"), raw.get("written_gap"))
        if (set(raw) != allowed or not any(gaps)
                or any(value is not None and (not isinstance(value, str) or value not in {
                    "diagnoses_missing", "name_missing", "order_missing", "order_invalid", "scope_conflict", "scope_unknown",
                    "equivalence_unresolved", "version_conflict",
                }) for value in gaps)):
            return None
        return dict(raw)
    if (
        not set(raw).issubset(
            {
            "verification_kind",
            "authoritative_diagnoses",
            "written_diagnoses",
            "diagnoses_consistent",
            "order_comparable",
            "diagnosis_scope",
            "equivalent_pairs",
            }
            | _LEGACY_INTERNAL_KEYS
        )
        or raw.get("verification_kind") != "discharge_diagnosis_consistency_check"
        or type(raw.get("diagnoses_consistent")) is not bool
    ):
        return None
    authoritative = _safe_text_list(raw.get("authoritative_diagnoses"), minimum=1)
    written = _safe_text_list(raw.get("written_diagnoses"), minimum=1)
    order_comparable = raw.get("order_comparable", True)
    pairs = None
    if authoritative is not None and written is not None and "equivalent_pairs" in raw:
        pairs = valid_equivalent_pairs(raw["equivalent_pairs"], authoritative=authoritative, written=written)
        if pairs is None:
            return None
    mapped = map_equivalent_diagnoses(written or [], pairs or [])
    if (
        authoritative is None
        or written is None
        or raw["diagnoses_consistent"] != (authoritative == mapped)
        or type(order_comparable) is not bool
        or (not order_comparable and (raw["diagnoses_consistent"] or sorted(authoritative) == sorted(mapped)))
    ):
        return None
    return {
        "verification_kind": "discharge_diagnosis_consistency_check",
        "authoritative_diagnoses": authoritative,
        "written_diagnoses": written,
        "diagnoses_consistent": raw["diagnoses_consistent"],
        **({"order_comparable": order_comparable} if "order_comparable" in raw else {}),
        **({"diagnosis_scope": raw["diagnosis_scope"]} if "diagnosis_scope" in raw else {}),
        **({"equivalent_pairs": pairs} if pairs is not None else {}),
    }


def _safe_course_time_gap(raw: Mapping[str, Any]) -> dict[str, Any] | None:
    discharge = _safe_date(raw.get("discharge_date"))
    dates = _safe_text_list(raw.get("checked_dates"), minimum=2, maximum=2)
    count = raw.get("missing_time_count")
    if (not discharge or dates is None or type(count) is not int or count <= 0
        or not set(raw).issubset({"failure_kind", "discharge_date", "checked_dates", "missing_time_count"} | _LEGACY_INTERNAL_KEYS)):
        return None
    expected = [(datetime.strptime(discharge, "%Y-%m-%d") - timedelta(days=1)).date().isoformat(), discharge]
    if dates != expected:
        return None
    return {"failure_kind": raw["failure_kind"], "discharge_date": discharge,
            "checked_dates": dates, "missing_time_count": count}


def discharge_course_time_gap_display(rule_id: str, raw: Any) -> tuple[list[str], str] | None:
    kinds = {"LX0609-08-02-01": "predischarge_course_time_missing", "LX0609-08-02-02": "senior_discharge_approval_time_missing"}
    if not isinstance(raw, Mapping) or rule_id not in kinds or raw.get("failure_kind") != kinds[rule_id]:
        return None
    safe = _safe_course_time_gap(raw)
    if safe is None:
        return None
    count = safe["missing_time_count"]
    description = (f"已找到{count}份含同意出院意见的病程记录" if rule_id == "LX0609-08-02-02" else f"已读取{count}份病程记录")
    message = (f"出院日期{safe['discharge_date']}，核查窗口为{'、'.join(safe['checked_dates'])}。"
               f"{description}，但缺少有效记录时间，无法确认是否位于该窗口。请通过证据定位核对这些文书的时间。")
    return [f"相关病程记录的权威时间（{count}份）"], message


def discharge_course_body_gap_display(rule_id: str, raw: Any) -> tuple[list[str], str] | None:
    if rule_id != "LX0609-08-02-01" or not isinstance(raw, Mapping) or raw.get("failure_kind") != "predischarge_course_body_missing":
        return None
    safe = _safe_067(raw)
    if safe is None:
        return None
    count = safe["missing_body_count"]
    return (
        [f"出院前一天或当天病程记录正文（{count}份）"],
        f"出院日期{safe['discharge_date']}，核查窗口为{'、'.join(safe['checked_dates'])}。"
        f"已读取该窗口内{count}份病程记录，但正文为空或仅有签名标签，暂无法完成核对。"
        "请通过证据定位核对这些文书的正文及同步情况。",
    )


def _safe_067(raw: Mapping[str, Any]) -> dict[str, Any] | None:
    if raw.get("failure_kind") == "predischarge_course_body_missing":
        count = raw.get("missing_body_count")
        if type(count) is not int or count <= 0 or not set(raw).issubset(
            {"failure_kind", "discharge_date", "checked_dates", "missing_body_count"} | _LEGACY_INTERNAL_KEYS
        ):
            return None
        # 与既有时间缺口共用严格的出院日/前一日窗口校验，仅转换计数字段。
        checked = _safe_course_time_gap({
            "failure_kind": raw["failure_kind"], "discharge_date": raw.get("discharge_date"),
            "checked_dates": raw.get("checked_dates"), "missing_time_count": count,
        })
        if checked is None:
            return None
        checked.pop("missing_time_count")
        return {**checked, "missing_body_count": count}
    if raw.get("failure_kind") == "predischarge_course_time_missing":
        return _safe_course_time_gap(raw)
    if (
        not set(raw).issubset(
            {
            "verification_kind",
            "discharge_date",
            "checked_dates",
            "course_present",
            }
            | _LEGACY_INTERNAL_KEYS
        )
        or raw.get("verification_kind") != "predischarge_course_presence_check"
        or type(raw.get("course_present")) is not bool
    ):
        return None
    discharge_date = _safe_date(raw.get("discharge_date"))
    checked_dates = _safe_text_list(raw.get("checked_dates"), minimum=2, maximum=2)
    if (
        not discharge_date
        or checked_dates is None
        or any(not _safe_date(value) for value in checked_dates)
        or checked_dates != sorted(checked_dates)
        or len(set(checked_dates)) != 2
        or discharge_date != checked_dates[-1]
    ):
        return None
    return {
        "verification_kind": "predischarge_course_presence_check",
        "discharge_date": discharge_date,
        "checked_dates": checked_dates,
        "course_present": raw["course_present"],
    }


def _safe_068(raw: Mapping[str, Any]) -> dict[str, Any] | None:
    """复制活跃 068 合同；仅接受执行器已判定的批准路径及时间缺口。"""
    if raw.get("failure_kind") == "senior_discharge_approval_time_missing":
        return _safe_course_time_gap(raw)

    verification_kind = raw.get("verification_kind")
    failure_kind = raw.get("failure_kind")
    checked_dates = _safe_text_list(raw.get("checked_dates"), minimum=2, maximum=2)
    discharge_date = _safe_date(raw.get("discharge_date"))
    approval_present = raw.get("approval_present")
    if (
        not set(raw).issubset(
            {
                "failure_kind",
                "verification_kind",
                "discharge_date",
                "checked_dates",
                "checked_source",
                "approval_present",
                "approval_path",
                "window_course_count",
            }
            | _LEGACY_INTERNAL_KEYS
        )
        or checked_dates is None
        or any(not _safe_date(value) for value in checked_dates)
        or checked_dates != sorted(checked_dates)
        or len(set(checked_dates)) != 2
        or not discharge_date
        or discharge_date != checked_dates[-1]
        or type(approval_present) is not bool
    ):
        return None
    if verification_kind == "senior_discharge_approval_present":
        if (
            failure_kind is not None
            or raw.get("checked_source")
            not in {"daily_course_record", "senior_course_record"}
            or approval_present is not True
            or raw.get("approval_path")
            not in {"automatic_discharge", "senior_approval"}
        ):
            return None
        kind_key = "verification_kind"
        kind = verification_kind
    elif failure_kind == "senior_discharge_approval_missing":
        if (
            verification_kind is not None
            or raw.get("checked_source")
            != "daily_course_record,senior_course_record"
            or approval_present is not False
            or "approval_path" in raw
            or (
                "window_course_count" in raw
                and (type(raw["window_course_count"]) is not int or raw["window_course_count"] <= 0)
            )
        ):
            return None
        kind_key = "failure_kind"
        kind = failure_kind
    else:
        return None
    facts: dict[str, Any] = {
        kind_key: kind,
        "discharge_date": discharge_date,
        "checked_dates": checked_dates,
        "checked_source": raw["checked_source"],
        "approval_present": approval_present,
    }
    if "approval_path" in raw:
        facts["approval_path"] = raw["approval_path"]
    if "window_course_count" in raw and kind == "senior_discharge_approval_missing":
        facts["window_course_count"] = raw["window_course_count"]
    elif "window_course_count" in raw:
        return None
    return facts


def safe_discharge_customer_display_facts(
    *, rule_id: str, raw: Any
) -> dict[str, Any] | None:
    """白名单化出院文书族已经裁决的客户事实。"""

    if not isinstance(raw, Mapping):
        return None
    normalized = str(rule_id or "").strip().upper()
    if normalized == "LX0609-08-01-05":
        return _safe_course_content(raw)
    if normalized == "LX0609-08-01-01":
        return _safe_061(raw)
    if normalized == "LX0609-08-01-02":
        return _safe_062(raw)
    if normalized == "LX0609-08-01-03":
        return _safe_063(raw)
    if normalized == "LX0609-08-02-01":
        return _safe_067(raw)
    if normalized == "LX0609-08-02-02":
        return _safe_068(raw)
    return None


def _published_finite_number(value: Any) -> bool:
    if type(value) not in (int, float):
        return False
    try:
        return math.isfinite(float(value))
    except (OverflowError, ValueError):
        return False


def _published_discharge_window(raw: dict[str, Any]) -> bool:
    date = _safe_date(raw.get("discharge_date"))
    checked = _safe_text_list(raw.get("checked_dates"), minimum=2, maximum=2)
    if not date or checked is None or any(not _safe_date(item) for item in checked):
        return False
    return checked == [(datetime.strptime(date, "%Y-%m-%d") - timedelta(days=1)).date().isoformat(), date]


def _published_ordered_window(raw: dict[str, Any]) -> bool:
    date = _safe_date(raw.get("discharge_date"))
    checked = _safe_text_list(raw.get("checked_dates"), minimum=2, maximum=2)
    return bool(date and checked is not None and all(_safe_date(item) for item in checked)
                and checked == sorted(checked) and len(set(checked)) == 2 and checked[-1] == date)


def validate_published_discharge_facts(
    *, rule_id: str, raw: Any,
) -> dict[str, Any] | None:
    """验证已发布的出院文书公开 JSON，不投影、不舍入。"""

    if not isinstance(raw, dict) or any(type(key) is not str for key in raw):
        return None
    rid = str(rule_id or "").strip().upper()
    if rid == "LX0609-08-01-05":
        return _safe_course_content(raw)
    keys = set(raw)
    if rid == "LX0609-08-01-01":
        base = {"verification_kind", "discharge_time", "record_time", "threshold_hours", "actual_interval_hours"}
        if (raw.get("verification_kind") != "discharge_record_timeliness_check"
                or type(raw.get("threshold_hours")) is not int or raw["threshold_hours"] != 24):
            return None
        if keys == base | {"conflicting_discharge_times"}:
            conflicts = _safe_text_list(raw["conflicting_discharge_times"], minimum=2, item_maximum=40)
            if (conflicts is None or any(not _safe_datetime(item) for item in conflicts)
                    or any(raw[key] is not None for key in ("discharge_time", "record_time", "actual_interval_hours"))):
                return None
            try:
                parsed = [datetime.fromisoformat(item.replace("Z", "+00:00")) for item in conflicts]
                if len(set(parsed)) != len(parsed) or sorted(parsed) != parsed:
                    return None
            except (ValueError, TypeError):
                return None
        elif keys in (base, base | {"discharge_time_source"}):
            value = raw.get("actual_interval_hours")
            source = raw.get("discharge_time_source")
            if (not _safe_datetime(raw.get("discharge_time"))
                    or (raw.get("record_time") is not None and not _safe_datetime(raw["record_time"]))
                    or (value is not None and not _published_finite_number(value))
                    or (value is not None and value >= 0 and type(value) is float and value != round(value, 2))
                    or ("discharge_time_source" in raw and (type(source) is not str or source not in _TIME_SOURCES))):
                return None
        else:
            return None
    elif rid == "LX0609-08-01-02":
        if raw.get("verification_kind") == "discharge_medication_extraction_pending":
            if (keys != {"verification_kind", "extraction_state"}
                    or type(raw.get("extraction_state")) is not str
                    or raw["extraction_state"] not in {"unknown", "data_gap", "technical_error"}):
                return None
        elif raw.get("verification_kind") == "discharge_medication_prescription_identity_gap":
            if (keys != {"verification_kind", "gap_reason", "affected_prescription_item_count"}
                    or raw.get("gap_reason") not in {"source_unavailable", "identity_missing", "too_many_items"}
                    or type(raw.get("affected_prescription_item_count")) is not int
                    or not 0 <= raw["affected_prescription_item_count"] <= 500
                    or (raw["gap_reason"] == "identity_missing"
                        and raw["affected_prescription_item_count"] <= 0)
                    or (raw["gap_reason"] == "too_many_items"
                        and raw["affected_prescription_item_count"] <= 20)):
                return None
        else:
            required = ["drug_name", "dose", "route", "duration"]
            missing = _safe_text_list(raw.get("missing_fields"), maximum=4)
            legacy_keys = {"verification_kind", "medication_count", "required_fields", "missing_fields"}
            prescription_keys = {"prescription_medication_count", "missing_drug_names"}
            names = (_safe_text_list(raw.get("missing_drug_names"), maximum=20)
                     if prescription_keys <= keys else None)
            count = raw.get("prescription_medication_count")
            if (keys not in (legacy_keys, legacy_keys | prescription_keys)
                    or raw.get("verification_kind") != "discharge_medication_completeness_check"
                    or type(raw.get("medication_count")) is not int or raw["medication_count"] < 0
                    or (raw["medication_count"] == 0 and not _proven_prescription_omission(raw))
                    or raw.get("required_fields") != required or missing is None
                    or any(item not in required for item in missing)
                    or (prescription_keys <= keys and (
                        type(count) is not int or not 0 <= count <= 20 or names is None
                        or len(names) > count or len(names) != len(set(names))
                        or (names and "drug_name" not in missing)
                    ))):
                return None
    elif rid == "LX0609-08-01-03":
        if "diagnosis_scope" in raw and (type(raw["diagnosis_scope"]) is not str or raw["diagnosis_scope"] not in {"death", "discharge"}):
            return None
        scope_keys = {"diagnosis_scope"} if "diagnosis_scope" in raw else set()
        scope_gap_values = {"scope_conflict", "scope_unknown"}
        if any(type(raw.get(key)) is str and raw[key] in scope_gap_values for key in ("authoritative_gap", "written_gap")):
            if (raw.get("verification_kind") != "discharge_diagnosis_data_gap"
                    or type(raw.get("authoritative_gap")) is not str
                or raw["authoritative_gap"] not in scope_gap_values
                    or raw.get("written_gap") is not None or "diagnosis_scope" in raw):
                return None
        if raw.get("verification_kind") == "discharge_main_diagnosis_check":
            if _safe_main_diagnosis_check(raw) is None:
                return None
        elif raw.get("verification_kind") == "discharge_diagnosis_data_gap":
            gaps = (raw.get("authoritative_gap"), raw.get("written_gap"))
            allowed = {"diagnoses_missing", "name_missing", "order_missing", "order_invalid", "scope_conflict", "scope_unknown",
                       "equivalence_unresolved", "version_conflict"}
            if (keys != {"verification_kind", "authoritative_gap", "written_gap"} | scope_keys
                    or not any(gaps)
                    or any(value is not None and (type(value) is not str or value not in allowed) for value in gaps)):
                return None
        else:
            authoritative = _safe_text_list(raw.get("authoritative_diagnoses"), minimum=1)
            written = _safe_text_list(raw.get("written_diagnoses"), minimum=1)
            comparable = raw.get("order_comparable", True)
            consistent = raw.get("diagnoses_consistent")
            base = {"verification_kind", "authoritative_diagnoses", "written_diagnoses", "diagnoses_consistent"}
            pair_keys = {"equivalent_pairs"} if "equivalent_pairs" in raw else set()
            pairs = (
                valid_equivalent_pairs(raw["equivalent_pairs"], authoritative=authoritative, written=written)
                if pair_keys and authoritative is not None and written is not None
                else None
            )
            mapped = map_equivalent_diagnoses(written or [], pairs or [])
            if (keys not in (base | scope_keys | pair_keys, base | {"order_comparable"} | scope_keys | pair_keys)
                    or (pair_keys and pairs is None)
                    or raw.get("verification_kind") != "discharge_diagnosis_consistency_check"
                    or authoritative is None or written is None or type(consistent) is not bool
                    or type(comparable) is not bool or consistent != (authoritative == mapped)
                    or (not comparable and (consistent or sorted(authoritative) == sorted(mapped)))):
                return None
    elif rid in {"LX0609-08-02-01", "LX0609-08-02-02"}:
        gap_kind = ("predischarge_course_time_missing" if rid == "LX0609-08-02-01"
                    else "senior_discharge_approval_time_missing")
        if raw.get("failure_kind") == gap_kind:
            if (keys != {"failure_kind", "discharge_date", "checked_dates", "missing_time_count"}
                    or not _published_discharge_window(raw)
                    or type(raw.get("missing_time_count")) is not int or raw["missing_time_count"] <= 0):
                return None
        elif rid == "LX0609-08-02-01" and raw.get("failure_kind") == "predischarge_course_body_missing":
            if (keys != {"failure_kind", "discharge_date", "checked_dates", "missing_body_count"}
                    or not _published_discharge_window(raw)
                    or type(raw.get("missing_body_count")) is not int or raw["missing_body_count"] <= 0):
                return None
        elif rid == "LX0609-08-02-01":
            if (keys != {"verification_kind", "discharge_date", "checked_dates", "course_present"}
                    or raw.get("verification_kind") != "predischarge_course_presence_check"
                    or not _published_ordered_window(raw) or type(raw.get("course_present")) is not bool):
                return None
        else:
            base = {"discharge_date", "checked_dates", "checked_source", "approval_present"}
            if not _published_ordered_window(raw) or type(raw.get("approval_present")) is not bool:
                return None
            if raw.get("verification_kind") == "senior_discharge_approval_present":
                if (keys != base | {"verification_kind", "approval_path"}
                        or type(raw.get("checked_source")) is not str
                        or raw["checked_source"] not in {"daily_course_record", "senior_course_record"}
                        or raw["approval_present"] is not True
                        or type(raw.get("approval_path")) is not str
                        or raw["approval_path"] not in {"automatic_discharge", "senior_approval"}):
                    return None
            elif raw.get("failure_kind") == "senior_discharge_approval_missing":
                count = raw.get("window_course_count")
                if (keys not in (base | {"failure_kind"}, base | {"failure_kind", "window_course_count"})
                        or raw.get("checked_source") != "daily_course_record,senior_course_record"
                        or raw["approval_present"] is not False
                        or ("window_course_count" in raw and (type(count) is not int or count <= 0))):
                    return None
            else:
                return None
    else:
        return None
    return dict(raw)


def discharge_customer_fact_status_is_valid(
    *, rule_id: str, status: str, safe_facts: Mapping[str, Any] | None
) -> bool:
    """校验出院族事实与已裁决状态自洽，不读取资料或重做判定。"""

    if not is_discharge_customer_rule(rule_id):
        return True
    normalized_status = str(status or "").strip().lower()
    if (str(rule_id or "").strip().upper() == "LX0609-08-01-03"
            and isinstance(safe_facts, Mapping)
            and safe_facts.get("verification_kind") == "discharge_diagnosis_data_gap"
            and safe_facts.get("authoritative_gap") in {"scope_conflict", "scope_unknown"}):
        return normalized_status == "data_gap"
    if normalized_status == "technical_error":
        return True
    if not isinstance(safe_facts, Mapping):
        return False
    normalized = str(rule_id or "").strip().upper()
    if normalized == "LX0609-08-01-05":
        return normalized_status == (
            safe_facts["state"] if safe_facts.get("verification_kind") == "discharge_course_pending"
            else content_state(safe_facts)
        )
    if normalized == "LX0609-08-01-01":
        return normalized_status == (
            "data_gap"
            if safe_facts.get("actual_interval_hours") is None
            else "compliant"
            if safe_facts["actual_interval_hours"] <= 24
            else "non_compliant"
        )
    if normalized == "LX0609-08-01-02":
        if safe_facts.get("verification_kind") == "discharge_medication_extraction_pending":
            # 抽取补核后仍不确定按资料不足交付（2026-10-23）。
            return normalized_status == {
                "unknown": "data_gap", "data_gap": "data_gap", "technical_error": "technical_error",
            }.get(safe_facts.get("extraction_state"))
        if safe_facts.get("verification_kind") == "discharge_medication_prescription_identity_gap":
            return normalized_status == "data_gap"
        return normalized_status == (
            "compliant" if not safe_facts.get("missing_fields") else "non_compliant"
        )
    if normalized == "LX0609-08-01-03":
        if safe_facts.get("verification_kind") == "discharge_diagnosis_data_gap":
            return normalized_status == "data_gap"
        if safe_facts.get("verification_kind") == "discharge_main_diagnosis_check":
            return normalized_status == ("compliant" if safe_facts.get("main_consistent") is True else "non_compliant")
        return normalized_status == (
            "compliant"
            if safe_facts.get("diagnoses_consistent") is True
            else "non_compliant"
        )
    if normalized == "LX0609-08-02-01":
        if safe_facts.get("verification_kind") == "predischarge_course_presence_check":
            return normalized_status == (
                "compliant" if safe_facts.get("course_present") is True else "non_compliant"
            )
        return normalized_status == "data_gap"
    if normalized == "LX0609-08-02-02":
        return normalized_status == (
            "compliant"
            if safe_facts.get("approval_present") is True
            else "non_compliant"
            if safe_facts.get("window_course_count")
            else "data_gap"
        )
    return False


__all__ = [
    "DISCHARGE_CUSTOMER_RULE_IDS",
    "discharge_customer_fact_status_is_valid",
    "is_discharge_customer_rule",
    "safe_discharge_customer_display_facts",
    "validate_published_discharge_facts",
]
