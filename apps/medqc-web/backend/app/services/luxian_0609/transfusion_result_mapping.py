"""输血规则的安全客户事实合同。

本模块只校验执行器已经得出的 041–048 客户展示事实，并剥离内部文书标识。
逐文书证据仍由 ``RuleDecision.fact_refs`` 经 Binding 和公共投影生成；这里不读取
资料、不重新判定状态，也不构造客户证据 DTO。
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Mapping


TRANSFUSION_CUSTOMER_RULE_IDS = frozenset(
    f"LX0609-{number:03d}" for number in range(41, 49)
)

_SYSTEM_GAP_REASONS = {
    "LX0609-041": "consent_source_unavailable",
    "LX0609-042": "consent_signature_contract_unavailable",
    "LX0609-043": "pretransfusion_item_contract_unavailable",
    "LX0609-044": "pretransfusion_assessment_source_unavailable",
    "LX0609-048": "transfusion_comparison_fields_unavailable",
}


def is_transfusion_customer_rule(rule_id: str) -> bool:
    """返回由输血规则族拥有展示事实合同的规则。"""

    return str(rule_id or "").strip().upper() in TRANSFUSION_CUSTOMER_RULE_IDS


def _controlled_list(
    value: Any, *, allowed: set[str] | None = None
) -> list[str] | None:
    if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
        return None
    values = list(value)
    if allowed is not None and any(item not in allowed for item in values):
        return None
    return values


def _safe_system_gap(*, rule_id: str, raw: Mapping[str, Any]) -> dict[str, Any] | None:
    expected_reason = _SYSTEM_GAP_REASONS.get(rule_id)
    if expected_reason is None or raw.get("failure_kind") != "system_data_contract_gap":
        return None
    allowed_keys = {
        "failure_kind",
        "system_gap_reason",
        "gap_owner",
        "conclusion",
        "handling_suggestion",
    }
    conclusion = raw.get("conclusion")
    suggestion = raw.get("handling_suggestion")
    if (
        set(raw) != allowed_keys
        or raw.get("system_gap_reason") != expected_reason
        or raw.get("gap_owner") != "system_integration"
        or not isinstance(conclusion, str)
        or not conclusion.strip()
        or len(conclusion) > 500
        or "\n" in conclusion
        or not isinstance(suggestion, str)
        or not suggestion.strip()
        or len(suggestion) > 500
        or "\n" in suggestion
    ):
        return None
    return {
        "failure_kind": "system_data_contract_gap",
        "system_gap_reason": expected_reason,
        "gap_owner": "system_integration",
    }


def _safe_041(raw: Mapping[str, Any]) -> dict[str, Any] | None:
    if (
        raw.get("verification_kind") == "transfusion_consent_present"
        and raw.get("performed_transfusion_confirmed") is True
        and isinstance(raw.get("consent_count"), int)
    ):
        return {
            "verification_kind": "transfusion_consent_present",
            "performed_transfusion_confirmed": True,
            "consent_count": raw["consent_count"],
        }
    if (
        raw.get("failure_kind") == "transfusion_consent_missing"
        and raw.get("performed_transfusion_confirmed") is True
        and raw.get("checked_source") == "blood_transfusion_consent"
    ):
        return {
            "failure_kind": "transfusion_consent_missing",
            "performed_transfusion_confirmed": True,
            "checked_source": "blood_transfusion_consent",
        }
    return None


def _safe_042(raw: Mapping[str, Any]) -> dict[str, Any] | None:
    allowed_fields = {
        "patient_information", "diagnosis", "indication", "component", "risks",
        "alternatives", "patient_or_agent_signature", "physician_signature", "signed_time",
    }
    if (
        raw.get("verification_kind") == "transfusion_consent_complete"
        and raw.get("performed_transfusion_confirmed") is True
        and (fields := _controlled_list(raw.get("checked_fields"), allowed=allowed_fields))
        is not None
    ):
        return {
            "verification_kind": "transfusion_consent_complete",
            "performed_transfusion_confirmed": True,
            "checked_fields": fields,
        }
    if (
        raw.get("failure_kind") == "transfusion_consent_incomplete"
        and raw.get("performed_transfusion_confirmed") is True
        and (fields := _controlled_list(raw.get("missing_fields"), allowed=allowed_fields))
        is not None
    ):
        return {
            "failure_kind": "transfusion_consent_incomplete",
            "performed_transfusion_confirmed": True,
            "missing_fields": fields,
        }
    return None


def _safe_043(raw: Mapping[str, Any]) -> dict[str, Any] | None:
    allowed_items = {"hbsag", "hbsab", "hbeag", "hbeab", "hbcab", "hcv", "hiv", "syphilis", "alt"}
    kind = raw.get("verification_kind") or raw.get("failure_kind")
    if kind == "pretransfusion_items_complete":
        checked = _controlled_list(raw.get("checked_items"), allowed=allowed_items)
        if (
            checked is None
            or raw.get("performed_transfusion_confirmed") is not True
            or not isinstance(raw.get("latest_test_time"), str)
            or not isinstance(raw.get("transfusion_time"), str)
            or any(
                not isinstance(raw.get(key), bool)
                for key in ("abo_present", "rh_present", "antibody_screen_present")
            )
        ):
            return None
        return {
            "verification_kind": kind,
            "performed_transfusion_confirmed": True,
            "checked_items": checked,
            "latest_test_time": raw["latest_test_time"],
            "transfusion_time": raw["transfusion_time"],
            "abo_present": raw["abo_present"],
            "rh_present": raw["rh_present"],
            "antibody_screen_present": raw["antibody_screen_present"],
        }
    list_key = {
        "pretransfusion_items_incomplete": "missing_items",
        "pretransfusion_tests_after_transfusion": "late_items",
        "pretransfusion_test_time_missing": "missing_time_items",
    }.get(str(kind))
    if list_key is None:
        return None
    values = _controlled_list(raw.get(list_key), allowed=allowed_items)
    if values is None:
        return None
    result: dict[str, Any] = {"failure_kind": str(kind), list_key: values}
    if raw.get("performed_transfusion_confirmed") is True:
        result["performed_transfusion_confirmed"] = True
    if isinstance(raw.get("transfusion_time"), str):
        result["transfusion_time"] = raw["transfusion_time"]
    if kind == "pretransfusion_items_incomplete":
        required = _controlled_list(raw.get("required_items"), allowed=allowed_items)
        if required is None:
            return None
        result["required_items"] = required
    return result


def _safe_044(raw: Mapping[str, Any]) -> dict[str, Any] | None:
    kind = raw.get("verification_kind") or raw.get("failure_kind")
    if kind not in {
        "pretransfusion_assessment_complete",
        "pretransfusion_assessment_incomplete",
        "pretransfusion_assessment_missing",
        "pretransfusion_assessment_time_conflict",
        "pretransfusion_assessment_time_unavailable",
    }:
        return None
    legacy_fields = {"indication", "laboratory_indicator", "risk_history_or_status"}
    application_fields = {"application_reason", "laboratory_indicator"}
    checked = _controlled_list(raw.get("checked_fields"), allowed=legacy_fields | application_fields)
    missing = _controlled_list(raw.get("missing_fields"), allowed=legacy_fields | application_fields)
    expected_fields = sorted(
        application_fields if checked == sorted(application_fields) else legacy_fields
    )
    if (
        missing is None
        or raw.get("performed_transfusion_confirmed") is not True
        or (kind != "pretransfusion_assessment_time_unavailable" and checked != expected_fields)
        or (kind == "pretransfusion_assessment_complete" and missing)
        or (kind in {"pretransfusion_assessment_incomplete", "pretransfusion_assessment_missing"} and not missing)
    ):
        return None
    result: dict[str, Any] = {
        "verification_kind" if kind == "pretransfusion_assessment_complete" else "failure_kind": kind,
        "performed_transfusion_confirmed": True,
        "checked_fields": checked or [],
        "missing_fields": missing,
    }
    for time_key in ("application_time", "transfusion_time"):
        value = raw.get(time_key)
        if value is None:
            continue
        if not isinstance(value, str):
            return None
        try:
            datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
        result[time_key] = value
    elapsed_minutes = raw.get("elapsed_minutes")
    if elapsed_minutes is not None:
        if type(elapsed_minutes) not in {int, float} or not 0 <= elapsed_minutes <= 525600:
            return None
        result["elapsed_minutes"] = elapsed_minutes
    missing_time_fields = _controlled_list(
        raw.get("missing_time_fields"), allowed={"application_time", "transfusion_time"}
    )
    if missing_time_fields is not None:
        result["missing_time_fields"] = missing_time_fields
    return result


def _safe_045(raw: Mapping[str, Any]) -> dict[str, Any] | None:
    kind = raw.get("verification_kind") or raw.get("failure_kind")
    if kind not in {"transfusion_course_record_present", "transfusion_course_record_missing"}:
        return None
    sources = _controlled_list(
        raw.get("checked_sources"), allowed={"bloodtrans_record", "daily_course_record"}
    )
    if sources is None or raw.get("performed_transfusion_confirmed") is not True:
        return None
    result: dict[str, Any] = {
        "verification_kind" if str(kind).endswith("present") else "failure_kind": kind,
        "performed_transfusion_confirmed": True,
        "checked_sources": sources,
    }
    if isinstance(raw.get("record_count"), int):
        result["record_count"] = raw["record_count"]
    return result


def _safe_046(raw: Mapping[str, Any]) -> dict[str, Any] | None:
    kind = raw.get("verification_kind") or raw.get("failure_kind")
    if kind not in {"transfusion_course_record_complete", "transfusion_course_record_incomplete"}:
        return None
    allowed_fields = {
        "reason_or_indication", "start_and_end_time", "component", "dose",
        "process_observation", "reaction_and_handling",
    }
    checked = _controlled_list(raw.get("checked_fields"), allowed=allowed_fields)
    missing = _controlled_list(raw.get("missing_fields"), allowed=allowed_fields)
    record_count = raw.get("record_count")
    if (
        checked is None
        or missing is None
        or raw.get("performed_transfusion_confirmed") is not True
        or type(record_count) is not int
        or record_count < 0
    ):
        return None
    result: dict[str, Any] = {
        "verification_kind" if kind == "transfusion_course_record_complete" else "failure_kind": kind,
        "performed_transfusion_confirmed": True,
        "record_count": record_count,
        "checked_fields": checked,
        "missing_fields": missing,
    }
    incomplete_count = raw.get("incomplete_record_count")
    raw_missing_counts = raw.get("missing_field_record_counts")
    if incomplete_count is not None or raw_missing_counts is not None:
        if (
            type(incomplete_count) is not int
            or incomplete_count < 0
            or incomplete_count > record_count
            or not isinstance(raw_missing_counts, Mapping)
            or set(raw_missing_counts) != set(missing)
            or any(
                key not in allowed_fields
                or type(value) is not int
                or value < 1
                or value > incomplete_count
                for key, value in raw_missing_counts.items()
            )
            or (kind == "transfusion_course_record_complete" and incomplete_count != 0)
            or (kind == "transfusion_course_record_incomplete" and incomplete_count < 1)
        ):
            return None
        result["incomplete_record_count"] = incomplete_count
        result["missing_field_record_counts"] = {
            key: raw_missing_counts[key] for key in missing
        }
    return result


def _safe_047(raw: Mapping[str, Any]) -> dict[str, Any] | None:
    kind = raw.get("verification_kind") or raw.get("failure_kind")
    if kind not in {"posttransfusion_evaluation_complete", "posttransfusion_evaluation_missing"}:
        return None
    sources = _controlled_list(
        raw.get("checked_sources"), allowed={"bloodtrans_record", "daily_course_record"}
    )
    if (
        sources is None
        or raw.get("performed_transfusion_confirmed") is not True
        or raw.get("threshold_hours") != 24
    ):
        return None
    result: dict[str, Any] = {
        "verification_kind" if kind == "posttransfusion_evaluation_complete" else "failure_kind": kind,
        "performed_transfusion_confirmed": True,
        "threshold_hours": 24,
        "checked_sources": sources,
    }
    for key in ("transfusion_end_time", "evaluation_time"):
        if isinstance(raw.get(key), str):
            result[key] = raw[key]
    if isinstance(raw.get("elapsed_hours"), (int, float)):
        result["elapsed_hours"] = raw["elapsed_hours"]
    return result


def _safe_048(raw: Mapping[str, Any]) -> dict[str, Any] | None:
    kind = raw.get("verification_kind") or raw.get("failure_kind")
    source_types = {"surgery_record", "anesthesia_record", "postsurg_firstcourse_record"}
    if kind == "intraoperative_transfusion_absent":
        sources = _controlled_list(raw.get("checked_sources"), allowed={"surgery_record", "anesthesia_record"})
        return {"verification_kind": kind, "checked_sources": sources} if sources is not None else None
    if kind in {"transfusion_comparison_material_missing", "transfusion_comparison_fields_missing"}:
        result: dict[str, Any] = {"failure_kind": str(kind)}
        if str(kind).endswith("material_missing"):
            sources = _controlled_list(raw.get("missing_sources"), allowed=source_types)
            if sources is None:
                return None
            result["missing_sources"] = sources
        else:
            missing = raw.get("missing_fields_by_source")
            if not isinstance(missing, Mapping):
                return None
            safe_missing: dict[str, list[str]] = {}
            for source, values in missing.items():
                if source not in source_types:
                    return None
                fields = _controlled_list(values, allowed={"components", "doses"})
                if fields is None:
                    return None
                safe_missing[str(source)] = fields
            result["missing_fields_by_source"] = safe_missing
        return result
    if kind not in {"transfusion_records_consistent", "transfusion_records_inconsistent"}:
        return None
    matrix = raw.get("comparison_matrix")
    if not isinstance(matrix, Mapping):
        return None
    safe_matrix: dict[str, dict[str, list[str]]] = {}
    for source in ("surgery_record", "anesthesia_record", "postsurg_firstcourse_record"):
        fields = matrix.get(source)
        if not isinstance(fields, Mapping):
            return None
        components = _controlled_list(fields.get("components"))
        doses = _controlled_list(fields.get("doses"))
        if components is None or doses is None:
            return None
        safe_matrix[source] = {"components": components, "doses": doses}
    field_key = "checked_fields" if kind == "transfusion_records_consistent" else "differing_fields"
    values = _controlled_list(raw.get(field_key), allowed={"components", "doses"})
    if values is None:
        return None
    return {
        "verification_kind" if kind == "transfusion_records_consistent" else "failure_kind": kind,
        "performed_intraoperative_transfusion_confirmed": True,
        "comparison_matrix": safe_matrix,
        field_key: values,
    }


def _safe_requirement_missing(rule_id: str, raw: Mapping[str, Any]) -> dict[str, Any] | None:
    expected = {
        "LX0609-044": ("pretransfusion_assessment", ["bloodtrans_record", "blood_application", "course_record"]),
        "LX0609-046": ("purpose_or_indication", ["bloodtrans_record"]),
        "LX0609-047": ("posttransfusion_evaluation", ["bloodtrans_record", "course_record"]),
        "LX0609-048": ("postop_first_course_transfusion", ["surgery_record", "postsurg_firstcourse_record"]),
    }.get(rule_id)
    if expected is None:
        return None
    requirement, sources = expected
    if (
        raw.get("failure_kind") != "transfusion_requirement_not_documented"
        or raw.get("requirement") != requirement
        or raw.get("checked_sources") != sources
    ):
        return None
    return {
        "failure_kind": "transfusion_requirement_not_documented",
        "requirement": requirement,
        "checked_sources": list(sources),
    }


def safe_transfusion_customer_display_facts(
    *, rule_id: str, raw: Any
) -> dict[str, Any] | None:
    """返回输血族客户可见 facts，拒绝内部文书 ID 与不完整合同。"""

    normalized_rule_id = str(rule_id or "").strip().upper()
    if normalized_rule_id not in TRANSFUSION_CUSTOMER_RULE_IDS or not isinstance(raw, Mapping):
        return None
    system_gap = _safe_system_gap(rule_id=normalized_rule_id, raw=raw)
    if system_gap is not None:
        return system_gap
    checker = {
        "LX0609-041": _safe_041,
        "LX0609-042": _safe_042,
        "LX0609-043": _safe_043,
        "LX0609-044": _safe_044,
        "LX0609-045": _safe_045,
        "LX0609-046": _safe_046,
        "LX0609-047": _safe_047,
        "LX0609-048": _safe_048,
    }.get(normalized_rule_id)
    safe = checker(raw) if checker is not None else None
    return safe if safe is not None else _safe_requirement_missing(normalized_rule_id, raw)


def transfusion_customer_fact_status_is_valid(
    *, rule_id: str, status: str, safe_facts: Mapping[str, Any] | None
) -> bool:
    """验证输血 facts 与执行器已确定终态不冲突。"""

    normalized_rule_id = str(rule_id or "").strip().upper()
    if normalized_rule_id not in TRANSFUSION_CUSTOMER_RULE_IDS:
        return True
    if not isinstance(safe_facts, Mapping):
        return False
    kind = safe_facts.get("verification_kind") or safe_facts.get("failure_kind")
    if safe_facts.get("failure_kind") == "system_data_contract_gap":
        return status == "data_gap"
    expected_status = {
        "pretransfusion_assessment_complete": "compliant",
        "pretransfusion_assessment_incomplete": "non_compliant",
        "pretransfusion_assessment_missing": "non_compliant",
        "pretransfusion_assessment_time_conflict": "non_compliant",
    }.get(str(kind))
    return expected_status is None or status == expected_status
