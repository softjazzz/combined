"""肿瘤病理规则族的客户展示事实合同。

本模块只验证肿瘤病理执行器已裁决的展示事实，不读取文书，
不推断病理、化疗或出院计划，也不生成客户证据。正式主链的证据只能由
``RuleDecision.fact_refs → Binding → 公共 selected-document projector`` 产生。
"""

from __future__ import annotations

from collections.abc import Mapping
import re
from typing import Any


TUMOR_PATHOLOGY_CUSTOMER_RULE_IDS = frozenset(
    {"LX0609-06-02-01", "LX0609-06-02-03", "LX0609-06-02-02", "LX0609-05-02-01", "LX0609-08-01-04"}
)
_PATHOLOGY_SOURCES = frozenset({"pathology_exam_master", "pathology_exam_report"})
_TARGET_SOURCES = ("surgery_record", "daily_course_record")
_LX019_TARGET_SOURCES = (*_TARGET_SOURCES, "senior_course_record")
_DATETIME = re.compile(r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}")
_DOCUMENT_REF = re.compile(r"[a-f0-9]{64}")
_COMPLETENESS_STATUSES = frozenset({"compliant", "non_compliant", "not_applicable", "data_gap"})
_COMPLETENESS_EVENT_REASONS = frozenset({
    "pathology_business_key_missing", "pathology_business_key_ambiguous",
    "pathology_execution_conflict", "pathology_report_present",
    "pathology_report_content_unproven", "pathology_event_not_performed",
    "pathology_execution_unproven", "pathology_report_source_unavailable",
    "pathology_report_linkage_unresolved", "target_report_missing",
})


def is_tumor_pathology_customer_rule(rule_id: str) -> bool:
    return str(rule_id or "").strip().upper() in TUMOR_PATHOLOGY_CUSTOMER_RULE_IDS


def _safe_sources(value: Any, *, allowed: frozenset[str], required: bool) -> list[str] | None:
    if not isinstance(value, list) or (required and not value):
        return None
    if any(item not in allowed for item in value):
        return None
    return list(dict.fromkeys(value))


def _safe_checked_sources(
    value: Any, *, expected: tuple[str, ...] = _TARGET_SOURCES
) -> list[dict[str, str]] | None:
    if not isinstance(value, list) or len(value) != len(expected):
        return None
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


def _safe_report_completeness(
    raw: Mapping[str, Any], *, published: bool = False,
) -> dict[str, Any] | None:
    """只校验执行器的逐事件合同，不重读报告或按数量决定合规。"""

    counters = (
        "event_count", "report_count", "missing_report_count",
        "unresolved_event_count", "excluded_event_count",
    )
    if (
        raw.get("verification_kind") != "pathology_report_completeness"
        or not isinstance(raw.get("decision_status"), str)
        or raw["decision_status"] not in _COMPLETENESS_STATUSES
        or any(type(raw.get(key)) is not int or raw[key] < 0 for key in counters)
    ):
        return None
    sources = raw.get("checked_sources")
    events = raw.get("events")
    if not isinstance(sources, list) or len(sources) != 2 or not isinstance(events, list):
        return None
    safe_sources: list[dict[str, str]] = []
    for source, item in zip(("pathology_exam_master", "pathology_exam_report"), sources):
        if (
            not isinstance(item, Mapping)
            or item.get("source") != source
            or not isinstance(item.get("state"), str)
            or item["state"] not in {"present", "empty", "unavailable", "error", "truncated"}
            or not isinstance(item.get("completeness"), str)
            or item["completeness"] not in {"complete", "unproven", "truncated"}
        ):
            return None
        safe_sources.append({key: item[key] for key in ("source", "state", "completeness")})
    safe_events: list[dict[str, Any]] = []
    safe_event_keys = {
        "event_index", "status", "reason_code", "execution_confirmed",
        "report_count",
    }
    for index, item in enumerate(events, start=1):
        if not isinstance(item, Mapping):
            return None
        current_shape = (
            "safe" if set(item) == safe_event_keys else
            "raw" if "fact_refs" in item else None
        )
        if current_shape != ("safe" if published else "raw"):
            return None
        if (
            type(item.get("event_index")) is not int or item["event_index"] != index
            or not isinstance(item.get("status"), str)
            or item["status"] not in _COMPLETENESS_STATUSES
            or not isinstance(item.get("reason_code"), str)
            or item["reason_code"] not in _COMPLETENESS_EVENT_REASONS
            or type(item.get("execution_confirmed")) is not bool
            or type(item.get("report_count")) is not int or item["report_count"] not in {0, 1}
            or (current_shape == "raw" and (
                not isinstance(item.get("fact_refs"), list)
                or any(
                    not isinstance(ref, str) or _DOCUMENT_REF.fullmatch(ref) is None
                    for ref in item["fact_refs"]
                )
            ))
        ):
            return None
        safe_events.append({
            key: item[key]
            for key in (
                "event_index",
                "status",
                "reason_code",
                "execution_confirmed",
                "report_count",
            )
        })
    if (
        raw["event_count"] != len(safe_events)
        or raw["report_count"] != sum(item["report_count"] for item in safe_events)
        or raw["missing_report_count"] != sum(item["reason_code"] == "target_report_missing" for item in safe_events)
        or raw["unresolved_event_count"] != sum(item["status"] == "data_gap" for item in safe_events)
        or raw["excluded_event_count"] != sum(item["status"] == "not_applicable" for item in safe_events)
    ):
        return None
    return {
        "verification_kind": "pathology_report_completeness",
        "decision_status": raw["decision_status"],
        **{key: raw[key] for key in counters},
        "checked_sources": safe_sources,
        "events": safe_events,
    }


def validate_published_pathology_report_completeness_facts(
    raw: Any,
) -> dict[str, Any] | None:
    """公开结果只能包含报告完整性的受控字段。"""

    if not isinstance(raw, Mapping):
        return None
    validated = _safe_report_completeness(raw, published=True)
    return validated if validated is not None and dict(raw) == validated else None


def _safe_013(raw: Mapping[str, Any]) -> dict[str, Any] | None:
    if raw.get("verification_kind") == "pathology_report_field_gap":
        report_gaps = raw.get("report_gaps")
        if not isinstance(report_gaps, list) or not report_gaps:
            return None
        safe_gaps: list[dict[str, str]] = []
        for item in report_gaps:
            if not isinstance(item, Mapping) or set(item) != {
                "final_diagnosis_state",
                "report_time_state",
            }:
                return None
            diagnosis_state = item.get("final_diagnosis_state")
            time_state = item.get("report_time_state")
            if (
                not isinstance(diagnosis_state, str)
                or not isinstance(time_state, str)
                or diagnosis_state not in {"confirmed", "missing", "pending"}
                or time_state not in {"valid", "missing"}
                or (diagnosis_state == "confirmed" and time_state == "valid")
            ):
                return None
            safe_gaps.append(
                {
                    "final_diagnosis_state": str(diagnosis_state),
                    "report_time_state": str(time_state),
                }
            )
        return {
            "verification_kind": "pathology_report_field_gap",
            "report_gaps": safe_gaps,
        }

    triggers = _safe_sources(
        raw.get("pathology_trigger_sources"), allowed=_PATHOLOGY_SOURCES, required=True
    )
    raw_checked = raw.get("checked_target_sources")
    checked = _safe_checked_sources(
        raw_checked,
        expected=(*_TARGET_SOURCES, "senior_course_record")
        if isinstance(raw_checked, list) and len(raw_checked) == 3 else _TARGET_SOURCES,
    )
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
    if raw.get("verification_kind") == "pathology_report_field_gap":
        return _safe_013(raw)
    raw_checked = raw.get("checked_target_sources")
    checked = _safe_checked_sources(
        raw_checked,
        expected=(
            _LX019_TARGET_SOURCES
            if isinstance(raw_checked, list) and len(raw_checked) == 3
            # 有手术记录时 019 只核对手术记录。
            else ("surgery_record",)
            if isinstance(raw_checked, list) and len(raw_checked) == 1
            else _TARGET_SOURCES
        ),
    )
    if raw.get("verification_kind") == "pathology_sampling_documentation_check":
        triggers = _safe_sources(
            raw.get("pathology_trigger_sources"),
            allowed=_PATHOLOGY_SOURCES,
            required=True,
        )
        documented = _safe_sources(
            raw.get("documented_sources"),
            allowed=frozenset(
                item["source"] for item in checked
            ) if checked is not None else frozenset(),
            required=True,
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
    missing_event_count = raw.get("missing_order_event_count", 0)
    counted_missing_events = "missing_order_event_count" in raw
    unresolved = raw.get("unresolved_event_count", 0)
    missing_course = raw.get("missing_course_event_count", 0)
    unknown_time = raw.get("unknown_time_event_count", 0)
    confirmed = raw.get("confirmed_mismatch_event_count", 0)
    if (
        raw.get("verification_kind") != "chemotherapy_order_course_comparison"
        or type(raw.get("order_count")) is not int
        or raw["order_count"] < 1
        or type(unresolved) is not int
        or not 0 <= unresolved <= raw["order_count"]
        or type(missing_course) is not int
        or type(unknown_time) is not int
        or missing_course < 0
        or unknown_time < 0
        or type(missing_event_count) is not int
        or not 0 <= missing_event_count <= raw["order_count"]
        or type(confirmed) is not int
        or confirmed < 0
        or (confirmed > 0 and "mismatched" not in (fields.values() if isinstance(fields, Mapping) else ()))
        or unresolved + missing_course + unknown_time + missing_event_count + confirmed > raw["order_count"]
        or not isinstance(fields, Mapping)
        or set(fields) != allowed
        or any(value not in {"matched", "mismatched", "unknown"} for value in fields.values())
        or not isinstance(missing, list)
        or any(value not in allowed for value in missing)
        # 新事实按互斥事件计数表达缺字段与另一完整事件的比较；旧事实保持原合同。
        or (counted_missing_events and bool(missing) != (missing_event_count > 0))
        or (missing_event_count > 0 and "matched" in fields.values())
        or (missing_event_count == raw["order_count"] and any(value != "unknown" for value in fields.values()))
        # 受控计数区分未记录目标药和真正时间未知，不从unknown反推缺口原因。
        or (bool(missing) and not counted_missing_events and (missing_course > 0 or unknown_time > 0))
        or (missing_course > 0 and (fields["drug_name"] != "mismatched" or "matched" in fields.values()))
        or (missing_course > 0 and "unknown_time_event_count" not in raw)
        or (unknown_time > 0 and fields["time"] == "matched")
        or (missing_course == raw["order_count"] and any(fields[key] != "unknown" for key in ("dose", "route", "time")))
        # 关联缺口不能携带matched；全未关联事件只能是unknown。
        or (unresolved > 0 and ((bool(missing) and not counted_missing_events) or "matched" in fields.values()))
        or (
            unresolved == raw["order_count"]
            and any(value != "unknown" for value in fields.values())
        )
    ):
        return None
    return {
        "verification_kind": "chemotherapy_order_course_comparison",
        "order_count": raw["order_count"],
        "field_results": {key: fields[key] for key in ("drug_name", "dose", "route", "time")},
        "missing_order_fields": list(dict.fromkeys(missing)),
        **({"missing_order_event_count": missing_event_count} if counted_missing_events else {}),
        **({"unresolved_event_count": unresolved} if "unresolved_event_count" in raw else {}),
        **({"missing_course_event_count": missing_course} if "missing_course_event_count" in raw else {}),
        **({"unknown_time_event_count": unknown_time} if "unknown_time_event_count" in raw else {}),
        **({"confirmed_mismatch_event_count": confirmed} if "confirmed_mismatch_event_count" in raw else {}),
    }


def _safe_027(raw: Mapping[str, Any]) -> dict[str, Any] | None:
    if raw.get("verification_kind") == "malignant_diagnosis_applicability_uncertain":
        count = raw.get("uncertain_diagnosis_count")
        if raw.get("malignancy_state") != "unknown" or type(count) is not int or count <= 0:
            return None
        return {"verification_kind": "malignant_diagnosis_applicability_uncertain",
                "malignancy_state": "unknown", "uncertain_diagnosis_count": count}
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
        "LX0609-06-02-01": _safe_report_completeness,
        "LX0609-06-02-03": _safe_013,
        "LX0609-06-02-02": _safe_019,
        "LX0609-05-02-01": _safe_026,
        "LX0609-08-01-04": _safe_027,
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
    if normalized_rule_id == "LX0609-06-02-01":
        return (
            normalized_status in _COMPLETENESS_STATUSES
            and safe_facts.get("verification_kind") == "pathology_report_completeness"
            and normalized_status == safe_facts.get("decision_status")
        )
    if normalized_rule_id == "LX0609-08-01-04" and safe_facts.get("verification_kind") == "malignant_diagnosis_applicability_uncertain":
        # M17：该事实同时允许 `uncertain` 与 `data_gap`。
        # 027 的客户契约不允许交付 `uncertain`（catalog 027 行 allowed_result_statuses
        # = hit; not_hit; data_quality_gap; not_applicable; needs_manual_review），
        # 故「诊断恶性性质未决」只能以 `data_gap` 交付；此前这里只接受 `uncertain`，
        # 于是执行器只能丢弃该事实（客户看不到未决线索），一旦携带就被本校验判为
        # 不自洽 → finalizer 升级为 `technical_error/model_invalid_output`。
        # 该事实是**纯展示事实**，不参与判定，故接受 `data_gap` 不放松任何判据。
        # 作用域仅限 `LX0609-08-01-04`，`013`/`019`/`026` 不受影响。
        return normalized_status in {"uncertain", "data_gap"}
    if normalized_rule_id in {"LX0609-06-02-03", "LX0609-08-01-04"}:
        if (
            normalized_rule_id == "LX0609-06-02-03"
            and safe_facts.get("verification_kind") == "pathology_report_field_gap"
        ):
            return normalized_status == "data_gap"
        requirement_met = safe_facts.get("requirement_met")
        return (
            normalized_status in {"compliant", "non_compliant"}
            and isinstance(requirement_met, bool)
            and requirement_met == (normalized_status == "compliant")
        )
    if normalized_rule_id == "LX0609-06-02-02":
        if safe_facts.get("verification_kind") == "pathology_report_field_gap":
            return normalized_status == "data_gap"
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
    if normalized_rule_id == "LX0609-05-02-01":
        safe_facts = _safe_026(safe_facts)
        if safe_facts is None:
            return False
        if safe_facts.get("missing_order_event_count", 0) > 0:
            # 新执行始终提供确认计数（含零），只接受独立可靠缺陷；无计数的已保存事实
            # 保持原合同，不能因本轮收紧而改判或失读。白名单投影必须保留显式零。
            independent = (
                safe_facts.get("confirmed_mismatch_event_count", 0) > 0
                or safe_facts.get("missing_course_event_count", 0) > 0
            ) if "confirmed_mismatch_event_count" in safe_facts else (
                "mismatched" in safe_facts["field_results"].values()
            )
            expected_status = (
                "non_compliant"
                if independent
                else "data_gap"
            )
            return normalized_status == expected_status
        # 正关联缺口已禁止matched。另一事件未决时，只有可独立成立的确定不一致（时间已核实的
        # 给药不一致、明确停用，或完整病程中未记录）才交付缺陷，否则保持资料不足。
        if (
            safe_facts.get("unresolved_event_count", 0) > 0
            or safe_facts.get("unknown_time_event_count", 0) > 0
        ):
            independent = (
                safe_facts.get("confirmed_mismatch_event_count", 0) > 0
                or safe_facts.get("missing_course_event_count", 0) > 0
            )
            return normalized_status == ("non_compliant" if independent else "data_gap")
        if safe_facts.get("missing_course_event_count", 0) > 0:
            return normalized_status == "non_compliant"
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


def pathology_report_gap_missing_fields(
    safe_facts: Mapping[str, Any] | None,
) -> list[str] | None:
    """把已校验的逐报告缺口汇总为稳定客户字段名。"""

    if not isinstance(safe_facts, Mapping):
        return None
    normalized = _safe_013(safe_facts)
    if (
        normalized is None
        or normalized.get("verification_kind") != "pathology_report_field_gap"
    ):
        return None
    report_gaps = normalized["report_gaps"]
    missing_diagnosis_count = sum(
        item.get("final_diagnosis_state") == "missing" for item in report_gaps
    )
    pending_diagnosis_count = sum(
        item.get("final_diagnosis_state") == "pending" for item in report_gaps
    )
    missing_time_count = sum(
        item.get("report_time_state") == "missing" for item in report_gaps
    )
    fields: list[str] = []
    if missing_diagnosis_count:
        fields.append(f"病理最终诊断（{missing_diagnosis_count}份报告）")
    if pending_diagnosis_count:
        fields.append(
            f"已确认的病理最终诊断（{pending_diagnosis_count}份报告尚未确认）"
        )
    if missing_time_count:
        fields.append(f"有效病理报告时间（{missing_time_count}份报告）")
    return fields or None


__all__ = [
    "TUMOR_PATHOLOGY_CUSTOMER_RULE_IDS",
    "is_tumor_pathology_customer_rule",
    "pathology_report_gap_missing_fields",
    "safe_tumor_pathology_customer_display_facts",
    "tumor_pathology_customer_fact_status_is_valid",
]
