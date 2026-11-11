"""surgery_gate 执行器客户事实的唯一安全合同。

该模块只校验 executor 已得出的状态所附事实，绝不推导手术、植入物、
给药或签名结论。文书坐标由 Binding 的 fact_refs 和公共 projector 处理。
"""

from __future__ import annotations

from math import isfinite
import re
from typing import Any, Mapping


SURGERY_GATE_CUSTOMER_RULE_IDS = frozenset(
    {
        "LX0609-04-02-01",
        "LX0609-04-02-03",
        "LX0609-04-02-04",
        "LX0609-05-01-01",
        "LX0609-04-02-05",
        "LX0609-11-01-01",
    }
)
_IMPLANT_FIELDS = (
    "implant_name",
    "implant_type",
    "implant_specification",
    "implant_material",
    "implant_quantity",
)
_TIMESTAMP = re.compile(r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}")


def is_surgery_gate_customer_rule(rule_id: str) -> bool:
    return rule_id in SURGERY_GATE_CUSTOMER_RULE_IDS


def requires_missing_facts_status_validation(rule_id: str) -> bool:
    """只有025的确定终态需要在缺事实时继续验证精确例外。"""
    return rule_id == "LX0609-04-02-04"


def _document_id(value: Any) -> str:
    candidate = str(value or "").strip()
    return candidate if candidate and len(candidate) <= 256 and "\n" not in candidate and "\r" not in candidate else ""


def _implant_names(value: Any, *, allow_empty: bool = False) -> list[str] | None:
    if value is None:
        return []
    # 保持迁移前合同：字段缺省值 None 可表示“未提供可展示名称”，但调用方
    # 显式提交空数组会被视为非法事实，不能把空列表包装成已核验结果。
    if (
        not isinstance(value, list)
        or (not value and not allow_empty)
        or len(value) > 12
    ):
        return None
    result: list[str] = []
    for item in value:
        if (
            not isinstance(item, str)
            or not 1 <= len(item.strip()) <= 80
            or any(ord(char) < 32 for char in item)
            or item.strip() in result
        ):
            return None
        result.append(item.strip())
    return result


def _missing_implant_fields(value: Any) -> list[str] | None:
    if not isinstance(value, list) or not value:
        return None
    safe = [field for field in _IMPLANT_FIELDS if field in value]
    return safe if value == safe else None


def _safe_003(raw: Mapping[str, Any]) -> dict[str, Any] | None:
    kind = raw.get("failure_kind")
    if kind == "surgery_timeliness_data_gap":
        fields = raw.get("missing_fields")
        reason = raw.get("gap_reason")
        if (reason not in {"authoritative_time_missing", "authoritative_time_conflict", "association_failed"}
            or not isinstance(fields, list)
            or any(item not in {"surgery_end_time", "record_time", "surgery_record_association"} for item in fields)
            or (not fields and reason != "authoritative_time_conflict")):
            return None
        result = {"failure_kind": kind, "gap_reason": reason, "missing_fields": list(dict.fromkeys(fields))}
        if "conflicting_end_fields" in raw:
            if raw["conflicting_end_fields"] is not True or reason != "authoritative_time_conflict":
                return None
            result["conflicting_end_fields"] = True
        return result
    if kind == "surgery_record_missing":
        surgery_time = raw.get("surgery_time")
        if (
            raw.get("performed_surgery_confirmed") is not True
            or raw.get("threshold_hours") != 24
            or raw.get("surgery_time_kind") not in {"end", "begin"}
            or not (surgery_time is None or isinstance(surgery_time, str) and len(surgery_time) <= 32)
        ):
            return None
        return {
            "failure_kind": kind,
            "performed_surgery_confirmed": True,
            "surgery_time": surgery_time,
            "surgery_time_kind": raw["surgery_time_kind"],
            "threshold_hours": 24,
            "source_label": "手术记录",
        }
    if kind in {"qualified_surgery_absent", "surgery_not_performed"}:
        return (
            {"failure_kind": kind, "performed_surgery_confirmed": False}
            if raw.get("performed_surgery_confirmed") is False
            else None
        )
    end_time, record_time, elapsed = (
        raw.get("surgery_end_time"), raw.get("record_time"), raw.get("elapsed_hours")
    )
    # 新事实用精确秒校验裁决；两位小时仍保留为展示值，旧事实沿用原合同。
    precise_hours = elapsed
    if "elapsed_seconds" in raw:
        seconds = raw["elapsed_seconds"]
        if type(seconds) not in {int, float}:
            return None
        try:
            if not isfinite(seconds) or seconds < 0 or round(seconds / 3600, 2) != elapsed:
                return None
        except (OverflowError, ValueError):
            return None
        precise_hours = seconds / 3600
    if (
        kind not in {"surgery_record_late", "surgery_record_within_threshold"}
        or raw.get("performed_surgery_confirmed") is not True
        or not isinstance(end_time, str)
        or not isinstance(record_time, str)
        or not isinstance(elapsed, (int, float))
        or raw.get("threshold_hours") != 24
        or (kind == "surgery_record_late" and precise_hours <= 24)
        or (kind == "surgery_record_within_threshold" and not 0 <= precise_hours <= 24)
    ):
        return None
    facts = {
        "failure_kind": kind,
        "performed_surgery_confirmed": True,
        "surgery_end_time": end_time,
        "record_time": record_time,
        "elapsed_hours": round(float(elapsed), 2),
        "threshold_hours": 24,
        "source_label": "手术记录",
    }
    if "elapsed_seconds" in raw:
        facts["elapsed_seconds"] = raw["elapsed_seconds"]
    return facts


def surgery_timeliness_gap_display(facts: Any) -> tuple[list[str], str] | None:
    """把执行器明确的缺口枚举翻译为展示文字，不重新判定资料。"""
    if not isinstance(facts, Mapping) or facts.get("failure_kind") != "surgery_timeliness_data_gap":
        return None
    safe = _safe_003(facts)
    if safe is None:
        return None
    labels = {"surgery_end_time": "手术结束时间", "record_time": "手术记录权威完成时间",
              "surgery_record_association": "单台手术与手术记录的关联信息"}
    missing = [labels[key] for key in safe["missing_fields"]]
    if safe.get("conflicting_end_fields") is True:
        return missing, "手术结束时间字段存在冲突，暂时无法完成术后24小时时限核对。"
    message = ("手术记录时间早于手术结束时间，暂时无法完成时限核对。"
               if safe["gap_reason"] == "authoritative_time_conflict"
               else f"已找到手术记录，但缺少{'、'.join(missing)}，暂时无法判断是否在术后24小时内完成。")
    return missing, message


def _safe_024(raw: Mapping[str, Any]) -> dict[str, Any] | None:
    if raw.get("failure_kind") == "colon_pathology_lymph_node_items_missing":
        missing = raw.get("missing_items")
        if (
            raw.get("performed_surgery_confirmed") is not True
            or raw.get("malignant_surgery_confirmed") is not True
            or not isinstance(missing, list)
            or not missing
            or any(item not in {"lymph_node_count", "pathologic_stage"} for item in missing)
        ):
            return None
        return {
            "failure_kind": "colon_pathology_lymph_node_items_missing",
            "performed_surgery_confirmed": True,
            "malignant_surgery_confirmed": True,
            "missing_items": list(dict.fromkeys(missing)),
        }
    checked = raw.get("checked_sources")
    if (
        raw.get("failure_kind") != "lymph_node_dissection_not_documented"
        or raw.get("performed_surgery_confirmed") is not True
        or raw.get("malignant_surgery_confirmed") is not True
        or not isinstance(checked, list)
    ):
        return None
    safe = list(dict.fromkeys(
        item for item in checked
        if item in {"surgery_record", "pathology_exam_master", "pathology_exam_report"}
    ))
    return (
        {
            "failure_kind": "lymph_node_dissection_not_documented",
            "performed_surgery_confirmed": True,
            "malignant_surgery_confirmed": True,
            "checked_sources": safe,
        }
        if safe else None
    )


def _safe_025(raw: Mapping[str, Any]) -> dict[str, Any] | None:
    if (
        raw.get("verification_kind") == "implant_not_used"
        and raw.get("performed_surgery_confirmed") is True
        and set(raw) == {"verification_kind", "performed_surgery_confirmed", "source_label"}
        and raw.get("source_label") == "手术记录"
    ):
        return {
            "verification_kind": "implant_not_used",
            "performed_surgery_confirmed": True,
            "source_label": "手术记录",
        }
    source_type = raw.get("source_document_type")
    if source_type != "surgery_record" or raw.get("source_label") != "手术记录":
        return None
    identified_implants = raw.get("identified_implants")
    names = _implant_names(identified_implants)
    if names is None or (identified_implants is not None and not names):
        return None
    if (
        raw.get("verification_kind") == "implant_information_complete"
        and raw.get("performed_surgery_confirmed") is True
        and raw.get("checked_fields") == list(_IMPLANT_FIELDS)
        and _document_id(raw.get("source_document_id"))
        and set(raw) == {
            "verification_kind", "performed_surgery_confirmed", "checked_fields",
            "identified_implants", "source_label", "source_document_type", "source_document_id",
        }
    ):
        return {
            "verification_kind": "implant_information_complete",
            "performed_surgery_confirmed": True,
            "checked_fields": list(_IMPLANT_FIELDS),
            "source_label": "手术记录",
            "source_document_type": "surgery_record",
            **({"identified_implants": names} if names else {}),
        }
    missing = _missing_implant_fields(raw.get("missing_fields"))
    details = raw.get("implant_event_details")
    if (
        raw.get("failure_kind") != "implant_information_incomplete"
        or raw.get("performed_surgery_confirmed") is not True
        or missing is None
        or not isinstance(details, list)
        or not 1 <= len(details) <= 12
        or set(raw) - {
            "failure_kind", "performed_surgery_confirmed", "missing_fields", "identified_implants",
            "implant_event_details", "source_label", "source_document_type", "source_document_id",
        }
    ):
        return None
    safe_events: list[dict[str, Any]] = []
    document_ids: list[str] = []
    seen_refs: set[str] = set()
    union_missing: set[str] = set()
    for position, event in enumerate(details, start=1):
        if not isinstance(event, Mapping) or set(event) != {
            "event_ref", "missing_fields", "implant_names", "source_document_id"
        }:
            return None
        event_ref = str(event.get("event_ref") or "").strip()
        document_id = _document_id(event.get("source_document_id"))
        event_missing = _missing_implant_fields(event.get("missing_fields"))
        event_names = _implant_names(event.get("implant_names"), allow_empty=True)
        if (
            not event_ref or len(event_ref) > 64 or "\n" in event_ref or "\r" in event_ref
            or event_ref in seen_refs or not document_id or document_id in document_ids
            or event_missing is None or event_names is None
        ):
            return None
        seen_refs.add(event_ref)
        document_ids.append(document_id)
        union_missing.update(event_missing)
        safe_events.append({
            "event_position": position,
            "missing_fields": event_missing,
            "implant_names": event_names,
        })
    if missing != [field for field in _IMPLANT_FIELDS if field in union_missing] or _document_id(raw.get("source_document_id")) != document_ids[0]:
        return None
    return {
        "failure_kind": "implant_information_incomplete",
        "performed_surgery_confirmed": True,
        "source_label": "手术记录",
        "source_document_type": "surgery_record",
        "missing_fields": missing,
        "implant_event_details": safe_events,
        **({"identified_implants": names} if names else {}),
    }


_028_GAP_KINDS = frozenset({
    "incision_class_unavailable", "order_stop_time_unavailable", "order_start_time_unavailable",
    "surgery_time_unavailable", "infection_evidence_unresolved",
})
_028_CHECK_KEYS = frozenset({
    "verification_kind", "incision_class", "cardiac_surgery", "threshold_hours", "duration_hours",
    "anchor", "anchor_time", "last_antibacterial_time", "infection_evidence", "requirement_met",
})


def _safe_028_check(raw: Mapping[str, Any]) -> dict[str, Any] | None:
    """院方口径（2026-10-11）：Ⅰ类心脏48h、其余24h；超时须病程记录感染证据。"""
    if raw.get("verification_kind") != "prophylaxis_duration_check":
        if set(raw) == {"failure_kind"} and raw.get("failure_kind") in _028_GAP_KINDS:
            return {"failure_kind": raw["failure_kind"]}
        return None
    duration, threshold, evidence, met = (
        raw.get("duration_hours"), raw.get("threshold_hours"), raw.get("infection_evidence"), raw.get("requirement_met"),
    )
    # 可选 stop_time_unknown：停药时间未知、时长为已证明下限，只能与已超时同现。
    stop_unknown = "stop_time_unknown" in raw
    if (
        set(raw) - {"stop_time_unknown"} != _028_CHECK_KEYS
        or (stop_unknown and (raw["stop_time_unknown"] is not True or evidence == "not_required"))
        or raw.get("incision_class") not in {"I", "II"}
        or type(raw.get("cardiac_surgery")) is not bool
        or threshold != (48 if raw.get("cardiac_surgery") else 24)
        or (raw.get("cardiac_surgery") and raw.get("incision_class") != "I")
        or isinstance(duration, bool) or not isinstance(duration, (int, float)) or duration < 0
        or raw.get("anchor") not in {"surgery_end", "surgery_begin"}
        or any(not isinstance(raw.get(key), str) or not _TIMESTAMP.fullmatch(raw[key])
               for key in ("anchor_time", "last_antibacterial_time"))
        or type(met) is not bool
        or evidence not in {"not_required", "recorded", "not_recorded"}
        or (evidence == "not_required") != (duration <= threshold)
        or met != (evidence != "not_recorded")
    ):
        return None
    return {key: raw[key] for key in sorted(set(raw))}


def _safe_028(raw: Mapping[str, Any]) -> dict[str, Any] | None:
    if "verification_kind" in raw or set(raw) == {"failure_kind"}:
        return _safe_028_check(raw)
    kind, start, end, duration, threshold = (
        raw.get("failure_kind"), raw.get("start_time"), raw.get("end_time"),
        raw.get("duration_hours"), raw.get("threshold_hours"),
    )
    if (
        kind not in {"prophylaxis_duration_over_48h", "prophylaxis_extension_reason_missing"}
        or raw.get("incision_class") not in {"I", "II"}
        or not isinstance(start, str) or not isinstance(end, str)
        or not _TIMESTAMP.fullmatch(start) or not _TIMESTAMP.fullmatch(end)
        or not isinstance(duration, (int, float)) or duration <= 24
        or threshold not in {24, 48}
        or (kind == "prophylaxis_duration_over_48h" and (threshold != 48 or duration <= 48))
        or (kind == "prophylaxis_extension_reason_missing" and (threshold != 24 or duration > 48))
    ):
        return None
    return {
        "failure_kind": kind,
        "incision_class": raw["incision_class"],
        "start_time": start,
        "end_time": end,
        "duration_hours": round(float(duration), 2),
        "threshold_hours": threshold,
    }


def _safe_031(raw: Mapping[str, Any]) -> dict[str, Any] | None:
    kind_key = "verification_kind" if raw.get("verification_kind") else "failure_kind"
    kind = raw.get(kind_key)
    if kind not in {
        "surgery_signature_confirmed", "surgery_signature_fields_missing", "surgery_signer_not_qualified"
    }:
        return None
    events = raw.get("surgery_events")
    if kind == "surgery_signature_confirmed" and events is None:
        allowed = {"verification_kind", "performed_surgery_confirmed", "surgeon_signature_matches", "first_assistant_exception_used"}
        return dict(raw) if set(raw) == allowed and raw.get("performed_surgery_confirmed") is True and raw.get("surgeon_signature_matches") is True else None
    if kind == "surgery_signer_not_qualified" and events is None:
        allowed = {
            "failure_kind",
            "performed_surgery_confirmed",
            "surgeon_signature_matches",
        }
        return (
            dict(raw)
            if set(raw) == allowed
            and raw.get("performed_surgery_confirmed") is True
            and raw.get("surgeon_signature_matches") is False
            else None
        )
    if (
        raw.get("performed_surgery_confirmed") is not True
        or not isinstance(events, (list, tuple)) or not events or len(events) > 100
        or set(raw) - {"failure_kind", "verification_kind", "performed_surgery_confirmed", "surgeon_signature_matches", "first_assistant_exception_used", "surgery_events"}
    ):
        return None
    safe_events: list[dict[str, Any]] = []
    for event in events:
        if not isinstance(event, Mapping) or set(event) - {"document_id", "surgery_name", "surgeon", "signer", "missing_fields"}:
            return None
        surgery_name, surgeon, signer, missing = (
            event.get("surgery_name") or "", event.get("surgeon") or "", event.get("signer") or "", event.get("missing_fields")
        )
        if (
            any(not isinstance(value, str) or len(value) > 160 or "\n" in value for value in (surgery_name, surgeon, signer))
            or not isinstance(missing, list) or any(value not in {"surgeon", "surgeon_sign"} for value in missing)
        ):
            return None
        safe_events.append({"surgery_name": surgery_name, "surgeon": surgeon, "signer": signer, "missing_fields": list(dict.fromkeys(missing))})
    result: dict[str, Any] = {kind_key: kind, "performed_surgery_confirmed": True, "surgery_events": safe_events}
    if kind == "surgery_signer_not_qualified":
        if raw.get("surgeon_signature_matches") is not False:
            return None
        result["surgeon_signature_matches"] = False
    elif raw.get("first_assistant_exception_used") is True:
        result["first_assistant_exception_used"] = True
    return result


def _safe_033(raw: Mapping[str, Any]) -> dict[str, Any] | None:
    if (
        raw.get("verification_kind") == "surgery_consent_complete"
        and raw.get("performed_surgery_confirmed") is True
        and raw.get("checked_signature_roles") == ["patient", "surgeon"]
    ):
        return {"verification_kind": "surgery_consent_complete", "performed_surgery_confirmed": True, "checked_signature_roles": ["patient", "surgeon"]}
    kind, state = raw.get("failure_kind"), raw.get("consent_state")
    if kind == "source_query_error":
        labels = raw.get("source_labels")
        if raw.get("performed_surgery_confirmed") is not True or not isinstance(labels, list) or not labels or len(labels) != len(set(labels)) or any(label not in {"手术记录", "手术知情同意书"} for label in labels):
            return None
        return {"failure_kind": kind, "source_labels": list(labels), "performed_surgery_confirmed": True}
    if raw.get("performed_surgery_confirmed") is not True or (kind, state) not in {
        ("surgery_consent_document_missing", "missing"), ("surgery_consent_body_missing", "blank"),
        ("surgery_consent_signature_missing", "signature_missing"), ("surgery_consent_source_unproven", "source_unproven"),
    }:
        return None
    result: dict[str, Any] = {"failure_kind": kind, "consent_state": state, "performed_surgery_confirmed": True}
    if state == "signature_missing":
        roles = raw.get("missing_signature_roles")
        safe = [role for role in roles if role in {"patient", "surgeon"}] if isinstance(roles, list) else []
        if not safe:
            return None
        result["missing_signature_roles"] = safe
    return result


def safe_surgery_gate_customer_display_facts(*, rule_id: str, raw: Any) -> dict[str, Any] | None:
    if not isinstance(raw, Mapping):
        return None
    handlers = {
        "LX0609-04-02-01": _safe_003, "LX0609-04-02-03": _safe_024, "LX0609-04-02-04": _safe_025,
        "LX0609-05-01-01": _safe_028, "LX0609-04-02-05": _safe_031, "LX0609-11-01-01": _safe_033,
    }
    handler = handlers.get(rule_id)
    return handler(raw) if handler else None


def surgery_gate_customer_fact_status_is_valid(*, rule_id: str, status: str, reason_code: str, raw_facts: Any, safe_facts: Mapping[str, Any] | None) -> bool:
    """状态与 executor facts 的既有一致性合同，供 Finalizer fail-closed 使用。"""
    if rule_id == "LX0609-04-02-01" and isinstance(safe_facts, Mapping):
        if safe_facts.get("failure_kind") == "surgery_timeliness_data_gap":
            return status == "data_gap" and reason_code == safe_facts.get("gap_reason")
        expected = {
            "qualified_surgery_absent": "not_applicable", "surgery_not_performed": "not_applicable",
            "surgery_record_late": "non_compliant", "surgery_record_within_threshold": "compliant",
            "surgery_record_missing": "non_compliant",
        }.get(str(safe_facts.get("verification_kind") or safe_facts.get("failure_kind") or ""))
        return expected is None or status == expected
    if rule_id == "LX0609-05-01-01" and isinstance(safe_facts, Mapping):
        if safe_facts.get("verification_kind") == "prophylaxis_duration_check":
            return status == ("compliant" if safe_facts.get("requirement_met") else "non_compliant")
        if safe_facts.get("failure_kind") in _028_GAP_KINDS:
            return status == "data_gap"
        return True
    if rule_id != "LX0609-04-02-04":
        return True
    expected = {"non_compliant": "implant_information_incomplete", "compliant": "implant_information_complete", "not_applicable": "implant_not_used"}.get(status)
    if raw_facts is None:
        return expected is None or (status == "not_applicable" and reason_code == "performed_event_absent")
    if expected is None:
        return True
    return safe_facts is not None and safe_facts.get("verification_kind") == expected or safe_facts is not None and safe_facts.get("failure_kind") == expected


def legacy_surgery_gate_contract_error(
    *,
    rule_id: str,
    status: str,
    reason_code: str,
    raw_facts: Any,
    safe_facts: Mapping[str, Any] | None,
) -> str:
    """保留迁移前公共聚合入口对 003/025 非法合同的拒绝语义。"""

    if rule_id == "LX0609-04-02-01" and isinstance(safe_facts, Mapping):
        if not surgery_gate_customer_fact_status_is_valid(
            rule_id=rule_id,
            status=status,
            reason_code=reason_code,
            raw_facts=raw_facts,
            safe_facts=safe_facts,
        ):
            return "invalid customer display fact status"
        return ""
    if rule_id == "LX0609-04-02-04" and not surgery_gate_customer_fact_status_is_valid(
        rule_id=rule_id,
        status=status,
        reason_code=reason_code,
        raw_facts=raw_facts,
        safe_facts=safe_facts,
    ):
        return "lx0609_025_display_fact_status_mismatch"
    return ""
