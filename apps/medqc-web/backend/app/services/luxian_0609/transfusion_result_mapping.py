"""输血规则的安全客户事实合同。

本模块只校验执行器已经得出的 041–048、070 客户展示事实，并剥离内部文书标识。
逐文书证据仍由 ``RuleDecision.fact_refs`` 经 Binding 和公共投影生成；这里不读取
资料、不重新判定状态，也不构造客户证据 DTO。
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Mapping


TRANSFUSION_CUSTOMER_RULE_IDS = frozenset(
    {
        "LX0609-11-03-01",
        "LX0609-11-03-02",
        "LX0609-07-01-01",
        "LX0609-07-01-02",
        "LX0609-07-02-01",
        "LX0609-07-02-02",
        "LX0609-07-03-01",
        "LX0609-07-04-01",
        "LX0609-07-01-03",
    }
)

_PRETRANSFUSION_ALLOWED_ITEMS = {
    "hbsag", "hbsab", "hbeag", "hbeab", "hbcab", "hcv", "hiv", "syphilis", "alt"
}

# 043 现按血型、抗体筛查加八项感染筛查核对；仍接受 alt，旧版九项口径已保存的结果读取时不被判为非法事实。
_PRETRANSFUSION_REGULAR_ALLOWED_ITEMS = _PRETRANSFUSION_ALLOWED_ITEMS | {"abo", "rh", "antibody_screen"}

_SYSTEM_GAP_REASONS = {
    "LX0609-11-03-01": "consent_source_unavailable",
    "LX0609-11-03-02": "consent_signature_contract_unavailable",
    "LX0609-07-01-01": "pretransfusion_item_contract_unavailable",
    "LX0609-07-01-02": "pretransfusion_assessment_source_unavailable",
    "LX0609-07-02-01": frozenset({
        "transfusion_course_source_unavailable",
        "transfusion_course_record_content_unavailable",
    }),
    "LX0609-07-02-02": frozenset({
        "transfusion_course_source_unavailable",
        "transfusion_course_record_content_unavailable",
    }),
    "LX0609-07-04-01": "transfusion_comparison_fields_unavailable",
}


def is_transfusion_customer_rule(rule_id: str) -> bool:
    """返回由输血规则族拥有展示事实合同的规则。"""

    return str(rule_id or "").strip().upper() in TRANSFUSION_CUSTOMER_RULE_IDS


def is_transfusion_public_fact_ref_evidence_rule(rule_id: str) -> bool:
    """070 的客户证据只允许经过公共逐行 fact_refs 投影。"""

    return str(rule_id or "").strip().upper() == "LX0609-07-01-03"


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
    if isinstance(expected_reason, frozenset):
        reason = raw.get("system_gap_reason")
        if not isinstance(reason, str) or reason not in expected_reason:
            return None
        expected_reason = reason
    if rule_id in {"LX0609-07-01-02", "LX0609-07-02-01", "LX0609-07-02-02"} and "transfusion_order_present" in raw:
        if raw["transfusion_order_present"] is not True:
            return None
        raw = {key: value for key, value in raw.items() if key != "transfusion_order_present"}
    # Finalizer 已剥离文案后的公开形状仍须能通过保存/读取时的同一校验。
    # 只接受精确字段及本规则原因；不接收任意宽松子集。
    # 所有登记了系统缺口原因的规则都会被 Finalizer 剥离成同一公开形状，不能只放行部分规则。
    public_keys = {"failure_kind", "system_gap_reason", "gap_owner"}
    if (
        set(raw) == public_keys
        and raw.get("system_gap_reason") == expected_reason
        and raw.get("gap_owner") == "system_integration"
    ):
        return {key: raw[key] for key in public_keys}
    allowed_keys = public_keys | {"conclusion", "handling_suggestion"}
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
    kind = raw.get("verification_kind") or raw.get("failure_kind")
    if kind == "pretransfusion_items_complete":
        checked = _controlled_list(
            raw.get("checked_items"), allowed=_PRETRANSFUSION_REGULAR_ALLOWED_ITEMS
        )
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
    values = _controlled_list(raw.get(list_key), allowed=_PRETRANSFUSION_REGULAR_ALLOWED_ITEMS)
    if values is None:
        return None
    result: dict[str, Any] = {"failure_kind": str(kind), list_key: values}
    if raw.get("performed_transfusion_confirmed") is True:
        result["performed_transfusion_confirmed"] = True
    if isinstance(raw.get("transfusion_time"), str):
        result["transfusion_time"] = raw["transfusion_time"]
    if kind == "pretransfusion_items_incomplete":
        required = _controlled_list(
            raw.get("required_items"), allowed=_PRETRANSFUSION_REGULAR_ALLOWED_ITEMS
        )
        if required is None:
            return None
        result["required_items"] = required
    return result


def _safe_070(raw: Mapping[str, Any]) -> dict[str, Any] | None:
    """保留 070 既有逐笔输血事实白名单，不解释检验业务。"""

    def controlled_event_checks(value: Any) -> list[dict[str, Any]] | None:
        if not isinstance(value, list) or not value or len(value) > 100:
            return None
        safe_events: list[dict[str, Any]] = []
        for item in value:
            if not isinstance(item, Mapping):
                return None
            transfusion_time = item.get("transfusion_time")
            latest_valid_test_time = item.get("latest_valid_test_time")
            if (
                not isinstance(transfusion_time, str)
                or len(transfusion_time) > 160
                or "\n" in transfusion_time
                or (
                    latest_valid_test_time is not None
                    and (
                        not isinstance(latest_valid_test_time, str)
                        or len(latest_valid_test_time) > 160
                        or "\n" in latest_valid_test_time
                    )
                )
            ):
                return None
            safe_event: dict[str, Any] = {
                "transfusion_time": transfusion_time,
                "latest_valid_test_time": latest_valid_test_time,
            }
            for key in (
                "missing_items",
                "missing_time_items",
                "late_items",
                "outside_current_stay_items",
            ):
                values = _controlled_list(
                    item.get(key), allowed=_PRETRANSFUSION_ALLOWED_ITEMS
                )
                if values is None:
                    return None
                safe_event[key] = values
            safe_events.append(safe_event)
        return safe_events

    def append_event_facts(result: dict[str, Any]) -> dict[str, Any] | None:
        unknown_count = raw.get("unconfirmed_record_count")
        if "unconfirmed_record_count" in raw:
            if (type(unknown_count) is not int or not 1 <= unknown_count <= 100
                    or raw.get("failure_kind") not in {"pretransfusion_items_incomplete", "pretransfusion_tests_after_transfusion", "pretransfusion_tests_outside_current_stay"}
                    or not all(raw.get(key) is not None for key in ("transfusion_event_count", "checked_transfusion_times", "event_checks"))):
                return None
            result["unconfirmed_record_count"] = unknown_count
        event_count = raw.get("transfusion_event_count")
        event_times = _controlled_list(raw.get("checked_transfusion_times"))
        event_checks = controlled_event_checks(raw.get("event_checks"))
        # 兼容逐笔 facts 尚未产生的历史结果；三项若仅出现部分则 fail-closed。
        if (
            raw.get("transfusion_event_count") is None
            and raw.get("checked_transfusion_times") is None
            and raw.get("event_checks") is None
        ):
            return result
        if (
            not isinstance(event_count, int)
            or isinstance(event_count, bool)
            or event_count <= 0
            or event_times is None
            or event_checks is None
            or event_count != len(event_times)
            or event_count != len(event_checks)
        ):
            return None
        result.update(
            {
                "transfusion_event_count": event_count,
                "checked_transfusion_times": event_times,
                "event_checks": event_checks,
            }
        )
        for key in ("failed_transfusion_times", "admission_time"):
            value = raw.get(key)
            if value is None:
                continue
            if key == "failed_transfusion_times":
                values = _controlled_list(value)
                if values is None:
                    return None
                result[key] = values
            elif isinstance(value, str) and len(value) <= 160 and "\n" not in value:
                result[key] = value
            else:
                return None
        outside_items = _controlled_list(
            raw.get("outside_current_stay_items"), allowed=_PRETRANSFUSION_ALLOWED_ITEMS
        )
        if outside_items is not None:
            result["outside_current_stay_items"] = outside_items
        elif raw.get("outside_current_stay_items") is not None:
            return None
        return result

    kind = raw.get("verification_kind") or raw.get("failure_kind")
    if kind == "pretransfusion_items_complete":
        checked = _controlled_list(
            raw.get("checked_items"), allowed=_PRETRANSFUSION_ALLOWED_ITEMS
        )
        if (
            checked is None
            or raw.get("performed_transfusion_confirmed") is not True
            or not isinstance(raw.get("latest_test_time"), str)
            or not isinstance(raw.get("transfusion_time"), str)
            or any(
                not isinstance(raw.get(key), bool)
                for key in (
                    "abo_present",
                    "rh_present",
                    "antibody_screen_present",
                )
            )
        ):
            return None
        return append_event_facts(
            {
                "verification_kind": str(kind),
                "performed_transfusion_confirmed": True,
                "checked_items": checked,
                "latest_test_time": raw["latest_test_time"],
                "transfusion_time": raw["transfusion_time"],
                "abo_present": raw["abo_present"],
                "rh_present": raw["rh_present"],
                "antibody_screen_present": raw["antibody_screen_present"],
            }
        )
    list_key = {
        "pretransfusion_items_incomplete": "missing_items",
        "pretransfusion_tests_after_transfusion": "late_items",
        "pretransfusion_test_time_missing": "missing_time_items",
        "pretransfusion_tests_outside_current_stay": "outside_current_stay_items",
    }.get(str(kind))
    if list_key is None:
        return None
    values = _controlled_list(raw.get(list_key), allowed=_PRETRANSFUSION_ALLOWED_ITEMS)
    if values is None:
        return None
    result: dict[str, Any] = {"failure_kind": str(kind), list_key: values}
    if raw.get("performed_transfusion_confirmed") is True:
        result["performed_transfusion_confirmed"] = True
    if isinstance(raw.get("transfusion_time"), str):
        result["transfusion_time"] = raw["transfusion_time"]
    if kind in {"pretransfusion_items_incomplete", "pretransfusion_tests_outside_current_stay"}:
        required = _controlled_list(
            raw.get("required_items"), allowed=_PRETRANSFUSION_ALLOWED_ITEMS
        )
        if required is None:
            return None
        result["required_items"] = required
    return append_event_facts(result)


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
    checked = _controlled_list(
        raw.get("checked_fields"), allowed=legacy_fields | application_fields
    )
    missing = _controlled_list(
        raw.get("missing_fields"), allowed=legacy_fields | application_fields
    )
    expected_fields = sorted(
        application_fields if checked == sorted(application_fields) else legacy_fields
    )
    if (
        missing is None
        or raw.get("transfusion_order_present") is not True
        or (kind != "pretransfusion_assessment_time_unavailable" and checked != expected_fields)
        or (kind == "pretransfusion_assessment_complete" and missing)
        or (kind in {"pretransfusion_assessment_incomplete", "pretransfusion_assessment_missing"} and not missing)
    ):
        return None
    result: dict[str, Any] = {
        "verification_kind" if kind == "pretransfusion_assessment_complete" else "failure_kind": kind,
        "transfusion_order_present": True,
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
    if sources is None or raw.get("transfusion_order_present") is not True:
        return None
    result: dict[str, Any] = {
        "verification_kind" if str(kind).endswith("present") else "failure_kind": kind,
        "transfusion_order_present": True,
        "checked_sources": sources,
    }
    if isinstance(raw.get("record_count"), int):
        result["record_count"] = raw["record_count"]
    return result


def _safe_046(raw: Mapping[str, Any]) -> dict[str, Any] | None:
    kind = raw.get("verification_kind") or raw.get("failure_kind")
    if kind == "transfusion_component_unresolved":
        record_count = raw.get("record_count")
        unresolved = raw.get("unresolved_component_record_count")
        if (set(raw) != {"failure_kind", "transfusion_order_present", "record_count", "unresolved_component_record_count"}
                or raw.get("transfusion_order_present") is not True
                or type(record_count) is not int or record_count < 1
                or type(unresolved) is not int or not 1 <= unresolved <= record_count):
            return None
        return dict(raw)
    if kind not in {"transfusion_course_record_complete", "transfusion_course_record_incomplete"}:
        return None
    allowed_fields = {
        "reason_or_indication", "start_and_end_time", "component", "dose",
        "process_observation", "reaction_and_handling", "clinical_effect",
    }
    checked = _controlled_list(raw.get("checked_fields"), allowed=allowed_fields)
    missing = _controlled_list(raw.get("missing_fields"), allowed=allowed_fields)
    record_count = raw.get("record_count")
    if (
        checked is None
        or missing is None
        or raw.get("transfusion_order_present") is not True
        or type(record_count) is not int
        or record_count < 0
    ):
        return None
    result: dict[str, Any] = {
        "verification_kind" if kind == "transfusion_course_record_complete" else "failure_kind": kind,
        "transfusion_order_present": True,
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
    if "unresolved_component_record_count" in raw:
        unresolved = raw["unresolved_component_record_count"]
        if (kind != "transfusion_course_record_incomplete"
                or type(unresolved) is not int or not 0 <= unresolved <= record_count):
            return None
        # 同份记录可同时缺指征且成分待核，两个计数不要求互斥。
        result["unresolved_component_record_count"] = unresolved
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
    safe_matrix: dict[str, dict[str, Any]] = {}
    for source in ("surgery_record", "anesthesia_record", "postsurg_firstcourse_record"):
        fields = matrix.get(source)
        if not isinstance(fields, Mapping):
            return None
        components = _controlled_list(fields.get("components"))
        doses = _controlled_list(fields.get("doses"))
        if components is None or doses is None:
            return None
        safe_matrix[source] = {"components": components, "doses": doses}
        raw_items = fields.get("transfusion_items")
        if raw_items is not None:
            import re
            from decimal import Decimal

            if not isinstance(raw_items, list) or not 1 <= len(raw_items) <= 128:
                return None
            safe_items: list[dict[str, str]] = []
            for item in raw_items:
                if (
                    not isinstance(item, Mapping)
                    or not isinstance(item.get("component"), str)
                    or item.get("component") not in {"红细胞", "血浆", "血小板", "冷沉淀", "全血", "白蛋白", "粒细胞"}
                    or not isinstance(item.get("quantity"), str)
                    or re.fullmatch(r"\d+(?:\.\d+)?", item["quantity"]) is None
                    or not isinstance(item.get("unit"), str)
                    or item.get("unit") not in {"u", "ml", "袋", "治疗量"}
                    or not isinstance(item.get("original_dose"), str)
                    or re.fullmatch(r"\d+(?:\.\d+)?\s*(?:U|单位|m[lL]|毫升|袋|(?:个)?治疗量)",
                                    item["original_dose"], re.IGNORECASE) is None
                ):
                    return None
                # 新增配对明细只校验同一剂量内部自洽，历史 matrix 不重新判业务状态。
                dose_match = re.fullmatch(
                    r"(?P<quantity>\d+(?:\.\d+)?)\s*(?P<unit>U|单位|m[lL]|毫升|袋|(?:个)?治疗量)",
                    item["original_dose"], re.IGNORECASE,
                )
                unit_aliases = {"u": "u", "单位": "u", "ml": "ml", "毫升": "ml",
                                "袋": "袋", "治疗量": "治疗量", "个治疗量": "治疗量"}
                if (
                    dose_match is None
                    or Decimal(item["quantity"]) != Decimal(dose_match.group("quantity"))
                    or item["unit"] != unit_aliases[dose_match.group("unit").lower()]
                ):
                    return None
                safe_item = {key: item[key] for key in ("component", "quantity", "unit", "original_dose")}
                event_time = item.get("event_time", "")
                if not isinstance(event_time, str):
                    return None
                if event_time:
                    try:
                        datetime.fromisoformat(event_time)
                    except ValueError:
                        return None
                safe_item["event_time"] = event_time
                safe_items.append(safe_item)
            safe_matrix[source]["transfusion_items"] = safe_items
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
        "LX0609-07-01-02": ("pretransfusion_assessment", ["bloodtrans_record", "blood_application", "course_record"]),
        "LX0609-07-02-02": ("purpose_or_indication", ["bloodtrans_record"]),
        "LX0609-07-03-01": ("posttransfusion_evaluation", ["bloodtrans_record", "course_record"]),
        "LX0609-07-04-01": ("postop_first_course_transfusion", ["surgery_record", "postsurg_firstcourse_record"]),
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
        "LX0609-11-03-01": _safe_041,
        "LX0609-11-03-02": _safe_042,
        "LX0609-07-01-01": _safe_043,
        "LX0609-07-01-02": _safe_044,
        "LX0609-07-02-01": _safe_045,
        "LX0609-07-02-02": _safe_046,
        "LX0609-07-03-01": _safe_047,
        "LX0609-07-04-01": _safe_048,
        "LX0609-07-01-03": _safe_070,
    }.get(normalized_rule_id)
    safe = checker(raw) if checker is not None else None
    return safe if safe is not None else _safe_requirement_missing(normalized_rule_id, raw)


def transfusion_customer_fact_status_is_valid(
    *, rule_id: str, status: str, safe_facts: Mapping[str, Any] | None,
    reason_code: str | None = None,
) -> bool:
    """验证输血 facts 与执行器已确定终态不冲突。"""

    normalized_rule_id = str(rule_id or "").strip().upper()
    if normalized_rule_id not in TRANSFUSION_CUSTOMER_RULE_IDS:
        return True
    if normalized_rule_id == "LX0609-07-01-02":
        if not isinstance(safe_facts, Mapping):
            return False
        kind = safe_facts.get("verification_kind") or safe_facts.get("failure_kind")
        expected = {
            "system_data_contract_gap": "data_gap",
            "pretransfusion_assessment_time_unavailable": "data_gap",
            "pretransfusion_assessment_complete": "compliant",
            "pretransfusion_assessment_incomplete": "non_compliant",
            "pretransfusion_assessment_missing": "non_compliant",
            "pretransfusion_assessment_time_conflict": "non_compliant",
            "transfusion_requirement_not_documented": "non_compliant",
        }.get(str(kind))
        return expected is not None and status == expected
    if normalized_rule_id == "LX0609-07-01-03":
        if status == "technical_error":
            return True
        if safe_facts is None:
            # 未触发输血或资料源不可用时，执行器本来就不产生展示 facts。
            return status in {"data_gap", "not_applicable"}
        kind = safe_facts.get("verification_kind") or safe_facts.get("failure_kind")
        if "unconfirmed_record_count" in safe_facts and status != "non_compliant":
            return False
        expected_status = {
            "pretransfusion_items_complete": "compliant",
            "pretransfusion_items_incomplete": "non_compliant",
            "pretransfusion_tests_outside_current_stay": "non_compliant",
            "pretransfusion_tests_after_transfusion": "non_compliant",
            "pretransfusion_test_time_missing": "data_gap",
        }.get(str(kind))
        return expected_status is not None and status == expected_status
    if not isinstance(safe_facts, Mapping):
        return False
    kind = safe_facts.get("verification_kind") or safe_facts.get("failure_kind")
    if safe_facts.get("failure_kind") == "system_data_contract_gap":
        return status == "data_gap"
    if normalized_rule_id == "LX0609-07-02-02":
        if kind == "transfusion_component_unresolved":
            return status == "data_gap" and reason_code == "semantic_extraction_unresolved"
        expected_status = {
            "transfusion_course_record_complete": "compliant",
            "transfusion_course_record_incomplete": "non_compliant",
            "transfusion_requirement_not_documented": "non_compliant",
        }.get(str(kind))
        return expected_status is not None and status == expected_status
    expected_status = {
        "pretransfusion_assessment_complete": "compliant",
        "pretransfusion_assessment_incomplete": "non_compliant",
        "pretransfusion_assessment_missing": "non_compliant",
        "pretransfusion_assessment_time_conflict": "non_compliant",
    }.get(str(kind))
    return expected_status is None or status == expected_status
