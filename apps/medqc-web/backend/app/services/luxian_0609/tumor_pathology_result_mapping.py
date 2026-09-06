"""肿瘤病理规则族的客户展示事实合同。

本模块只验证 013/019/026/027 执行器已裁决的展示事实，不读取文书，
不推断病理、化疗或出院计划，也不生成客户证据。正式主链的证据只能由
``RuleDecision.fact_refs → Binding → 公共 selected-document projector`` 产生。
"""

from __future__ import annotations

from collections.abc import Mapping
import re
from typing import Any


TUMOR_PATHOLOGY_CUSTOMER_RULE_IDS = frozenset(
    {"LX0609-013", "LX0609-019", "LX0609-026", "LX0609-027"}
)
_PATHOLOGY_SOURCES = frozenset({"pathology_exam_master", "pathology_exam_report"})
_TARGET_SOURCES = frozenset({"surgery_record", "daily_course_record"})
_DATETIME = re.compile(r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}")


def is_tumor_pathology_customer_rule(rule_id: str) -> bool:
    return str(rule_id or "").strip().upper() in TUMOR_PATHOLOGY_CUSTOMER_RULE_IDS


def _safe_sources(value: Any, *, allowed: frozenset[str], required: bool) -> list[str] | None:
    if not isinstance(value, list) or (required and not value):
        return None
    if any(item not in allowed for item in value):
        return None
    return list(dict.fromkeys(value))


def _safe_checked_sources(value: Any) -> list[dict[str, str]] | None:
    if not isinstance(value, list) or len(value) != 2:
        return None
    expected = ("surgery_record", "daily_course_record")
    result: list[dict[str, str]] = []
    for source, item in zip(expected, value):
        if (
            not isinstance(item, Mapping)
            or set(item) != {"source", "state"}
            or item.get("source") != source
            or item.get("state") not in {"present", "empty"}
        ):
            return None
        result.append({"source": source, "state": str(item["state"])})
    return result


def _safe_013(raw: Mapping[str, Any]) -> dict[str, Any] | None:
    triggers = _safe_sources(
        raw.get("pathology_trigger_sources"), allowed=_PATHOLOGY_SOURCES, required=True
    )
    checked = _safe_checked_sources(raw.get("checked_target_sources"))
    if (
        raw.get("verification_kind") != "pathology_result_documentation_check"
        or triggers is None
        or checked is None
        or not isinstance(raw.get("requirement_met"), bool)
    ):
        return None
    facts: dict[str, Any] = {
        "verification_kind": "pathology_result_documentation_check",
        "pathology_trigger_sources": triggers,
        "checked_target_sources": checked,
        "requirement_met": raw["requirement_met"],
    }
    report_time = raw.get("report_time")
    if report_time is not None:
        if not isinstance(report_time, str) or _DATETIME.fullmatch(report_time) is None:
            return None
        facts["report_time"] = report_time
    return facts


def _safe_019(raw: Mapping[str, Any]) -> dict[str, Any] | None:
    checked = _safe_checked_sources(raw.get("checked_target_sources"))
    if raw.get("verification_kind") == "pathology_sampling_documentation_check":
        triggers = _safe_sources(
            raw.get("pathology_trigger_sources"),
            allowed=_PATHOLOGY_SOURCES,
            required=True,
        )
        documented = _safe_sources(
            raw.get("documented_sources"), allowed=_TARGET_SOURCES, required=True
        )
        if (
            triggers is None
            or checked is None
            or documented is None
            or raw.get("requirement_met") is not True
        ):
            return None
        return {
            "verification_kind": "pathology_sampling_documentation_check",
            "pathology_trigger_sources": triggers,
            "checked_target_sources": checked,
            "documented_sources": documented,
            "requirement_met": True,
        }
    raw_triggers = raw.get("pathology_trigger_sources")
    if not isinstance(raw_triggers, list):
        return None
    # 保持旧直调入口的既有安全收敛：未知来源不输出，但已知病理来源仍可
    # 作为缺失采样记录的客户事实；不据此反查或生成文书坐标。
    triggers = list(dict.fromkeys(item for item in raw_triggers if item in _PATHOLOGY_SOURCES))
    if (
        raw.get("failure_kind") != "pathology_sampling_not_documented"
        or triggers is None
        or not triggers
        or checked is None
    ):
        return None
    return {
        "failure_kind": "pathology_sampling_not_documented",
        "pathology_trigger_sources": triggers,
        "checked_target_sources": checked,
    }


def _safe_026(raw: Mapping[str, Any]) -> dict[str, Any] | None:
    fields = raw.get("field_results")
    missing = raw.get("missing_order_fields")
    allowed = {"drug_name", "dose", "route", "time"}
    if (
        raw.get("verification_kind") != "chemotherapy_order_course_comparison"
        or not isinstance(raw.get("order_count"), int)
        or raw["order_count"] < 1
        or not isinstance(fields, Mapping)
        or set(fields) != allowed
        or any(value not in {"matched", "mismatched", "unknown"} for value in fields.values())
        or not isinstance(missing, list)
        or any(value not in allowed for value in missing)
    ):
        return None
    return {
        "verification_kind": "chemotherapy_order_course_comparison",
        "order_count": raw["order_count"],
        "field_results": {key: fields[key] for key in ("drug_name", "dose", "route", "time")},
        "missing_order_fields": list(dict.fromkeys(missing)),
    }


def _safe_027(raw: Mapping[str, Any]) -> dict[str, Any] | None:
    plan_items = raw.get("plan_items")
    required = ("future_plan", "tumor_treatment", "follow_up")
    if (
        raw.get("verification_kind") != "malignant_discharge_plan_check"
        or raw.get("malignant_diagnosis_present") is not True
        or not isinstance(plan_items, Mapping)
        or set(plan_items) != set(required)
        or any(not isinstance(value, bool) for value in plan_items.values())
        or not isinstance(raw.get("requirement_met"), bool)
    ):
        return None
    return {
        "verification_kind": "malignant_discharge_plan_check",
        "malignant_diagnosis_present": True,
        "plan_items": {key: plan_items[key] for key in required},
        "requirement_met": raw["requirement_met"],
    }


def safe_tumor_pathology_customer_display_facts(
    *, rule_id: str, raw: Any
) -> dict[str, Any] | None:
    """白名单化已裁决客户事实，拒绝内部标识和正文。"""

    normalized = str(rule_id or "").strip().upper()
    if normalized not in TUMOR_PATHOLOGY_CUSTOMER_RULE_IDS or not isinstance(raw, Mapping):
        return None
    return {
        "LX0609-013": _safe_013,
        "LX0609-019": _safe_019,
        "LX0609-026": _safe_026,
        "LX0609-027": _safe_027,
    }[normalized](raw)


def tumor_pathology_customer_fact_status_is_valid(
    *, rule_id: str, status: str, safe_facts: Mapping[str, Any] | None
) -> bool:
    """校验已裁决终态与肿瘤病理展示事实自洽，不重做业务判定。"""

    if not is_tumor_pathology_customer_rule(rule_id):
        return True
    normalized_status = str(status or "").strip().lower()
    if normalized_status == "technical_error":
        return True
    if not isinstance(safe_facts, Mapping):
        return False
    normalized_rule_id = str(rule_id or "").strip().upper()
    if normalized_rule_id in {"LX0609-013", "LX0609-027"}:
        requirement_met = safe_facts.get("requirement_met")
        return (
            normalized_status in {"compliant", "non_compliant"}
            and isinstance(requirement_met, bool)
            and requirement_met == (normalized_status == "compliant")
        )
    if normalized_rule_id == "LX0609-019":
        if (
            safe_facts.get("verification_kind")
            == "pathology_sampling_documentation_check"
        ):
            documented_sources = safe_facts.get("documented_sources")
            return (
                normalized_status == "compliant"
                and safe_facts.get("requirement_met") is True
                and isinstance(documented_sources, list)
                and bool(documented_sources)
            )
        return (
            normalized_status == "non_compliant"
            and safe_facts.get("failure_kind") == "pathology_sampling_not_documented"
        )
    if normalized_rule_id == "LX0609-026":
        field_results = safe_facts.get("field_results")
        missing_fields = safe_facts.get("missing_order_fields")
        if not isinstance(field_results, Mapping) or not isinstance(
            missing_fields, list
        ):
            return False
        values = tuple(field_results.values())
        if missing_fields or "unknown" in values:
            return normalized_status == "data_gap"
        if "mismatched" in values:
            return normalized_status == "non_compliant"
        return (
            values
            and all(value == "matched" for value in values)
            and normalized_status == "compliant"
        )
    return False


__all__ = [
    "TUMOR_PATHOLOGY_CUSTOMER_RULE_IDS",
    "is_tumor_pathology_customer_rule",
    "safe_tumor_pathology_customer_display_facts",
    "tumor_pathology_customer_fact_status_is_valid",
]
