"""061/062/063/067/068 出院文书规则的客户展示事实合同。

本模块只白名单化原生执行器已经裁决的事实，并校验其与最终状态自洽。它不
读取任何文书材料，也不生成客户证据；证据只能沿
``RuleDecision.fact_refs → Binding → 公共 selected-document projector`` 主链投影。
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime, timedelta
import math
import re
from typing import Any


DISCHARGE_CUSTOMER_RULE_IDS = frozenset(
    {
        "LX0609-061",
        "LX0609-062",
        "LX0609-063",
        "LX0609-067",
        "LX0609-068",
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


def _safe_062(raw: Mapping[str, Any]) -> dict[str, Any] | None:
    if raw.get("verification_kind") == "discharge_medication_extraction_pending":
        if (set(raw) != {"verification_kind", "extraction_state"}
                or raw.get("extraction_state") not in ("unknown", "data_gap", "technical_error")):
            return None
        return dict(raw)
    required = ["drug_name", "dose", "route", "duration"]
    if (
        not set(raw).issubset(
            {
            "verification_kind",
            "medication_count",
            "required_fields",
            "missing_fields",
            }
            | _LEGACY_INTERNAL_KEYS
        )
        or raw.get("verification_kind") != "discharge_medication_completeness_check"
        or type(raw.get("medication_count")) is not int
        or raw["medication_count"] <= 0
        or raw.get("required_fields") != required
    ):
        return None
    missing = _safe_text_list(raw.get("missing_fields"), maximum=len(required))
    if missing is None or any(item not in required for item in missing):
        return None
    return {
        "verification_kind": "discharge_medication_completeness_check",
        "medication_count": raw["medication_count"],
        "required_fields": required,
        "missing_fields": missing,
    }


def _safe_063(raw: Mapping[str, Any]) -> dict[str, Any] | None:
    if raw.get("verification_kind") == "discharge_diagnosis_data_gap":
        allowed = {"verification_kind", "authoritative_gap", "written_gap"}
        gaps = (raw.get("authoritative_gap"), raw.get("written_gap"))
        if (set(raw) != allowed or not any(gaps)
                or any(value is not None and (not isinstance(value, str) or value not in {
                    "diagnoses_missing", "name_missing", "order_missing", "order_invalid"
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
    if (
        authoritative is None
        or written is None
        or raw["diagnoses_consistent"] != (authoritative == written)
        or type(order_comparable) is not bool
        or (not order_comparable and (raw["diagnoses_consistent"] or sorted(authoritative) == sorted(written)))
    ):
        return None
    return {
        "verification_kind": "discharge_diagnosis_consistency_check",
        "authoritative_diagnoses": authoritative,
        "written_diagnoses": written,
        "diagnoses_consistent": raw["diagnoses_consistent"],
        **({"order_comparable": order_comparable} if "order_comparable" in raw else {}),
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
    kinds = {"LX0609-067": "predischarge_course_time_missing", "LX0609-068": "senior_discharge_approval_time_missing"}
    if not isinstance(raw, Mapping) or rule_id not in kinds or raw.get("failure_kind") != kinds[rule_id]:
        return None
    safe = _safe_course_time_gap(raw)
    if safe is None:
        return None
    count = safe["missing_time_count"]
    description = (f"已找到{count}份含同意出院意见的病程记录" if rule_id == "LX0609-068" else f"已读取{count}份病程记录")
    message = (f"出院日期{safe['discharge_date']}，核查窗口为{'、'.join(safe['checked_dates'])}。"
               f"{description}，但缺少有效记录时间，无法确认是否位于该窗口。请通过证据定位核对这些文书的时间。")
    return [f"相关病程记录的权威时间（{count}份）"], message


def discharge_course_body_gap_display(rule_id: str, raw: Any) -> tuple[list[str], str] | None:
    if rule_id != "LX0609-067" or not isinstance(raw, Mapping) or raw.get("failure_kind") != "predischarge_course_body_missing":
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
    return facts


def safe_discharge_customer_display_facts(
    *, rule_id: str, raw: Any
) -> dict[str, Any] | None:
    """白名单化出院文书族已经裁决的客户事实。"""

    if not isinstance(raw, Mapping):
        return None
    normalized = str(rule_id or "").strip().upper()
    if normalized == "LX0609-061":
        return _safe_061(raw)
    if normalized == "LX0609-062":
        return _safe_062(raw)
    if normalized == "LX0609-063":
        return _safe_063(raw)
    if normalized == "LX0609-067":
        return _safe_067(raw)
    if normalized == "LX0609-068":
        return _safe_068(raw)
    return None


def discharge_customer_fact_status_is_valid(
    *, rule_id: str, status: str, safe_facts: Mapping[str, Any] | None
) -> bool:
    """校验出院族事实与已裁决状态自洽，不读取资料或重做判定。"""

    if not is_discharge_customer_rule(rule_id):
        return True
    normalized_status = str(status or "").strip().lower()
    if normalized_status == "technical_error":
        return True
    if not isinstance(safe_facts, Mapping):
        return False
    normalized = str(rule_id or "").strip().upper()
    if normalized == "LX0609-061":
        return normalized_status == (
            "data_gap"
            if safe_facts.get("actual_interval_hours") is None
            or safe_facts["actual_interval_hours"] < 0
            else "compliant"
            if safe_facts["actual_interval_hours"] <= 24
            else "non_compliant"
        )
    if normalized == "LX0609-062":
        if safe_facts.get("verification_kind") == "discharge_medication_extraction_pending":
            return normalized_status == {
                "unknown": "uncertain", "data_gap": "data_gap", "technical_error": "technical_error",
            }.get(safe_facts.get("extraction_state"))
        return normalized_status == (
            "compliant" if not safe_facts.get("missing_fields") else "non_compliant"
        )
    if normalized == "LX0609-063":
        if safe_facts.get("verification_kind") == "discharge_diagnosis_data_gap":
            return normalized_status == "data_gap"
        return normalized_status == (
            "compliant"
            if safe_facts.get("diagnoses_consistent") is True
            else "non_compliant"
        )
    if normalized == "LX0609-067":
        return normalized_status == (
            "compliant" if safe_facts.get("course_present") is True else "data_gap"
        )
    if normalized == "LX0609-068":
        return normalized_status == (
            "compliant" if safe_facts.get("approval_present") is True else "data_gap"
        )
    return False


__all__ = [
    "DISCHARGE_CUSTOMER_RULE_IDS",
    "discharge_customer_fact_status_is_valid",
    "is_discharge_customer_rule",
    "safe_discharge_customer_display_facts",
]
