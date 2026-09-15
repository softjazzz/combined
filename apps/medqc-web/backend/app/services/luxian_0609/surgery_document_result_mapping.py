"""手术文书族客户展示事实与旧入口证据的唯一合同。

本模块只校验执行器已经得出的 029、034–039 事实，并在旧 aggregate
直调入口保留极小的历史证据适配。实际文书选择仍由 ``fact_refs``、Binding
和公共 selected-document projector 统一完成；这里不读取资料、不重算业务判定。
"""

from __future__ import annotations

from typing import Any, Mapping


SURGERY_DOCUMENT_CUSTOMER_RULE_IDS = frozenset(
    {
        "LX0609-029",
        "LX0609-034",
        "LX0609-035",
        "LX0609-036",
        "LX0609-037",
        "LX0609-038",
        "LX0609-039",
    }
)
SURGERY_DOCUMENT_PUBLIC_FACT_REF_EVIDENCE_RULE_IDS = frozenset(
    {"LX0609-034", "LX0609-036", "LX0609-039"}
)

_CONSENT_FIELDS = (
    "patient_signature",
    "physician_signature",
    "patient_signature_time",
    "physician_signature_time",
)
_VISIT_SOURCES = ("preane_surveil_record", "postane_surveil_record")
_VISIT_FIELDS = {
    "preanesthesia_visit": (
        "asa_level",
        "airway_assessment",
        "fasting_status",
        "anesthesia_history",
        "risk_discussion",
        "anesthetist_signature",
        "record_time",
    ),
    "postanesthesia_visit": (
        "consciousness_status",
        "respiratory_status",
        "circulatory_status",
        "complication_assessment",
        "anesthetist_signature",
        "record_time",
    ),
}


def is_surgery_document_customer_rule(rule_id: str) -> bool:
    return str(rule_id or "").strip().upper() in SURGERY_DOCUMENT_CUSTOMER_RULE_IDS


def is_surgery_document_public_fact_ref_evidence_rule(rule_id: str) -> bool:
    """返回已冻结为公共逐行 fact_refs 证据的手术文书规则。"""

    return (
        str(rule_id or "").strip().upper()
        in SURGERY_DOCUMENT_PUBLIC_FACT_REF_EVIDENCE_RULE_IDS
    )


def _safe_029(raw: Mapping[str, Any]) -> dict[str, Any] | None:
    trigger_kind = raw.get("surgery_trigger_kind")
    if trigger_kind == "surgery_order":
        trigger_fact = {"surgery_order_confirmed": True}
    elif trigger_kind == "performed_surgery":
        trigger_fact = {"performed_surgery_confirmed": True}
    else:
        return None
    present_keys = {
        "verification_kind", "target_document", "surgery_trigger_kind", *trigger_fact
    }
    if (
        raw.get("verification_kind") == "surgery_document_present"
        and raw.get("target_document") == "presurg_summary"
        and all(raw.get(key) == value for key, value in trigger_fact.items())
        and set(raw) == present_keys
    ):
        return {
            "verification_kind": "surgery_document_present",
            "target_document": "presurg_summary",
            "surgery_trigger_kind": trigger_kind,
            **trigger_fact,
        }
    failure_kind = raw.get("failure_kind")
    failure_keys = {
        "failure_kind", "target_document", "surgery_trigger_kind", *trigger_fact
    }
    if (
        failure_kind not in {"surgery_document_missing", "surgery_document_blank"}
        or raw.get("target_document") != "presurg_summary"
        or not all(raw.get(key) == value for key, value in trigger_fact.items())
        or set(raw) != failure_keys
    ):
        return None
    return {
        "failure_kind": failure_kind,
        "target_document": "presurg_summary",
        "surgery_trigger_kind": trigger_kind,
        **trigger_fact,
    }


def _safe_034_035(rule_id: str, raw: Mapping[str, Any]) -> dict[str, Any] | None:
    if (
        rule_id == "LX0609-034"
        and raw.get("verification_kind") == "anesthesia_consent_present"
        and raw.get("performed_anesthesia_confirmed") is True
        and raw.get("checked_sources") == ["consent_form"]
    ):
        return {
            "verification_kind": "anesthesia_consent_present",
            "performed_anesthesia_confirmed": True,
            "checked_sources": ["consent_form"],
        }
    if (
        rule_id == "LX0609-035"
        and raw.get("verification_kind") == "anesthesia_consent_complete"
        and raw.get("performed_anesthesia_confirmed") is True
        and raw.get("checked_fields") == list(_CONSENT_FIELDS)
    ):
        return {
            "verification_kind": "anesthesia_consent_complete",
            "performed_anesthesia_confirmed": True,
            "checked_fields": list(_CONSENT_FIELDS),
        }
    if (
        rule_id == "LX0609-035"
        and raw.get("failure_kind") == "anesthesia_consent_incomplete"
        and raw.get("performed_anesthesia_confirmed") is True
        and isinstance(raw.get("missing_fields"), list)
    ):
        missing = list(
            dict.fromkeys(field for field in raw["missing_fields"] if field in _CONSENT_FIELDS)
        )
        if missing:
            return {
                "failure_kind": "anesthesia_consent_incomplete",
                "performed_anesthesia_confirmed": True,
                "missing_fields": missing,
            }
    if (
        raw.get("failure_kind") != "anesthesia_consent_missing"
        or raw.get("performed_anesthesia_confirmed") is not True
        or raw.get("consent_state") != "missing"
        or raw.get("checked_sources") != ["consent_form"]
    ):
        return None
    return {
        "failure_kind": "anesthesia_consent_missing",
        "performed_anesthesia_confirmed": True,
        "consent_state": "missing",
        "checked_sources": ["consent_form"],
    }


def _safe_036_037(rule_id: str, raw: Mapping[str, Any]) -> dict[str, Any] | None:
    if (
        rule_id == "LX0609-036"
        and raw.get("verification_kind") == "anesthesia_visits_present"
        and raw.get("performed_anesthesia_confirmed") is True
        and raw.get("checked_sources") == list(_VISIT_SOURCES)
    ):
        return {
            "verification_kind": "anesthesia_visits_present",
            "performed_anesthesia_confirmed": True,
            "checked_sources": list(_VISIT_SOURCES),
        }
    if (
        rule_id == "LX0609-037"
        and raw.get("verification_kind") == "anesthesia_visits_complete"
        and raw.get("performed_anesthesia_confirmed") is True
        and raw.get("checked_sources") == list(_VISIT_SOURCES)
        and raw.get("checked_fields_by_visit")
        == {key: list(value) for key, value in _VISIT_FIELDS.items()}
    ):
        return {
            "verification_kind": "anesthesia_visits_complete",
            "performed_anesthesia_confirmed": True,
            "checked_sources": list(_VISIT_SOURCES),
            "checked_fields_by_visit": {
                key: list(value) for key, value in _VISIT_FIELDS.items()
            },
        }
    if (
        rule_id == "LX0609-037"
        and raw.get("failure_kind") == "anesthesia_visit_incomplete"
        and raw.get("performed_anesthesia_confirmed") is True
        and isinstance(raw.get("missing_fields_by_visit"), Mapping)
    ):
        missing: dict[str, list[str]] = {}
        for visit, allowed in _VISIT_FIELDS.items():
            values = raw["missing_fields_by_visit"].get(visit)
            if not isinstance(values, list):
                continue
            safe_values = list(dict.fromkeys(field for field in values if field in allowed))
            if safe_values:
                missing[visit] = safe_values
        if missing:
            return {
                "failure_kind": "anesthesia_visit_incomplete",
                "performed_anesthesia_confirmed": True,
                "missing_fields_by_visit": missing,
            }
    missing_sources = raw.get("missing_visit_sources")
    if (
        raw.get("failure_kind") != "anesthesia_visit_missing"
        or raw.get("performed_anesthesia_confirmed") is not True
        or not isinstance(missing_sources, list)
    ):
        return None
    safe_sources = list(dict.fromkeys(source for source in missing_sources if source in _VISIT_SOURCES))
    return (
        {
            "failure_kind": "anesthesia_visit_missing",
            "performed_anesthesia_confirmed": True,
            "missing_visit_sources": safe_sources,
        }
        if safe_sources
        else None
    )


def _safe_038(raw: Mapping[str, Any]) -> dict[str, Any] | None:
    kind_key = "verification_kind" if raw.get("verification_kind") else "failure_kind"
    kind = raw.get(kind_key)
    if (
        kind not in {"anesthesia_record_present", "anesthesia_record_missing"}
        or raw.get("performed_anesthesia_confirmed") is not True
        or raw.get("checked_sources") != ["anesthesia_record"]
    ):
        return None
    return {
        kind_key: kind,
        "performed_anesthesia_confirmed": True,
        "checked_sources": ["anesthesia_record"],
    }


def _safe_039(raw: Mapping[str, Any]) -> dict[str, Any] | None:
    common = {
        "performed_surgery_confirmed": True,
        "emergency_rescue_exception_absent": True,
    }
    if (
        raw.get("verification_kind")
        == "preop_discussion_surgeon_participation_confirmed"
        and all(raw.get(key) == value for key, value in common.items())
        and raw.get("discussion_state") == "present"
        and raw.get("surgeon_participation_state") == "confirmed"
    ):
        return {
            "verification_kind": "preop_discussion_surgeon_participation_confirmed",
            **common,
            "discussion_state": "present",
            "surgeon_participation_state": "confirmed",
        }
    if (
        raw.get("failure_kind") == "surgeon_not_in_preop_discussion"
        and all(raw.get(key) == value for key, value in common.items())
        and raw.get("discussion_state") == "present"
        and raw.get("surgeon_participation_state") == "absent"
    ):
        return {
            "failure_kind": "surgeon_not_in_preop_discussion",
            **common,
            "discussion_state": "present",
            "surgeon_participation_state": "absent",
        }
    if (
        raw.get("failure_kind") != "preop_discussion_missing"
        or not all(raw.get(key) == value for key, value in common.items())
        or raw.get("checked_sources") != ["presurg_discussion"]
    ):
        return None
    return {
        "failure_kind": "preop_discussion_missing",
        **common,
        "checked_sources": ["presurg_discussion"],
    }


def safe_surgery_document_customer_display_facts(
    *, rule_id: str, raw: Any
) -> dict[str, Any] | None:
    normalized_rule_id = str(rule_id or "").strip().upper()
    if normalized_rule_id not in SURGERY_DOCUMENT_CUSTOMER_RULE_IDS or not isinstance(raw, Mapping):
        return None
    if normalized_rule_id == "LX0609-029":
        return _safe_029(raw)
    if normalized_rule_id in {"LX0609-034", "LX0609-035"}:
        return _safe_034_035(normalized_rule_id, raw)
    if normalized_rule_id in {"LX0609-036", "LX0609-037"}:
        return _safe_036_037(normalized_rule_id, raw)
    if normalized_rule_id == "LX0609-038":
        return _safe_038(raw)
    return _safe_039(raw)


def surgery_document_customer_fact_status_is_valid(
    *, rule_id: str, status: str, safe_facts: Mapping[str, Any] | None
) -> bool:
    if not is_surgery_document_customer_rule(rule_id):
        return True
    if not isinstance(safe_facts, Mapping):
        return False
    kind = safe_facts.get("verification_kind") or safe_facts.get("failure_kind")
    expected = {
        "surgery_document_present": "compliant",
        "surgery_document_missing": "non_compliant",
        "surgery_document_blank": "non_compliant",
        "anesthesia_consent_present": "compliant",
        "anesthesia_consent_complete": "compliant",
        "anesthesia_consent_incomplete": "non_compliant",
        "anesthesia_consent_missing": "non_compliant",
        "anesthesia_visits_present": "compliant",
        "anesthesia_visits_complete": "compliant",
        "anesthesia_visit_incomplete": "non_compliant",
        "anesthesia_visit_missing": "non_compliant",
        "anesthesia_record_present": "compliant",
        "anesthesia_record_missing": "non_compliant",
        "preop_discussion_surgeon_participation_confirmed": "compliant",
        "surgeon_not_in_preop_discussion": "non_compliant",
        "preop_discussion_missing": "non_compliant",
    }.get(str(kind))
    return expected is not None and status == expected
