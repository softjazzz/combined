"""手术文书族客户展示事实与旧入口证据的唯一合同。

本模块只校验执行器已经得出的 029、034–039 事实，并在旧 aggregate
直调入口保留极小的历史证据适配。实际文书选择仍由 ``fact_refs``、Binding
和公共 selected-document projector 统一完成；这里不读取资料、不重算业务判定。
"""

from __future__ import annotations

from typing import Any, Mapping


SURGERY_DOCUMENT_CUSTOMER_RULE_IDS = frozenset(
    {
        "LX0609-04-01-01",
        "LX0609-11-02-01",
        "LX0609-11-02-02",
        "LX0609-04-04-01",
        "LX0609-04-04-02",
        "LX0609-04-04-03",
        "LX0609-04-01-02",
        "LX0609-04-01-04",
        "LX0609-04-01-05",
    }
)
SURGERY_DOCUMENT_PUBLIC_FACT_REF_EVIDENCE_RULE_IDS = frozenset(
    {"LX0609-11-02-01", "LX0609-04-04-01", "LX0609-04-01-02", "LX0609-04-01-04", "LX0609-04-01-05"}
)

_CONSENT_FIELDS = (
    "patient_signature",
    "physician_signature",
    "patient_signature_time",
    "physician_signature_time",
)
_VISIT_SOURCES = ("preane_surveil_record", "postane_surveil_record")
# 按业务基线 037：术前访视含一般情况、简要病史、相关检查、拟行手术和麻醉方式、
# 适应证、注意事项、术前医嘱、签名和日期；术后48小时内至少访视1次，记录恢复、
# 清醒、拔管、术后医嘱、特殊情况、签名和时间。院方口径：术前24小时内、术后24小时内须访视。
_VISIT_FIELDS = {
    "preanesthesia_visit": (
        "preop_visit_within_24h",
        "general_condition",
        "brief_history",
        "relevant_examinations",
        "planned_procedure_and_anesthesia",
        "anesthesia_indication",
        "precautions",
        "preoperative_orders",
        "anesthetist_signature",
        "record_time",
    ),
    "postanesthesia_visit": (
        "postop_visit_within_24h",
        "recovery_status",
        "consciousness_status",
        "extubation_status",
        "postoperative_orders",
        "special_situations",
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
        rule_id == "LX0609-11-02-01"
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
        rule_id == "LX0609-11-02-02"
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
        rule_id == "LX0609-11-02-02"
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
        rule_id == "LX0609-04-04-01"
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
        rule_id == "LX0609-04-04-02"
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
        rule_id == "LX0609-04-04-02"
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


def _safe_preop_content(rule_id: str, raw: Mapping[str, Any]) -> dict[str, Any] | None:
    target = {"LX0609-04-01-04": "presurg_summary", "LX0609-04-01-05": "presurg_discussion"}[rule_id]
    allowed = {
        "LX0609-04-01-04": (
            "brief_condition", "preop_diagnosis", "surgical_indication",
            "planned_procedure", "planned_anesthesia", "precautions",
            "surgeon_preop_visit",
        ),
        "LX0609-04-01-05": (
            "preop_preparation", "surgical_indication", "surgical_plan",
            "risk_and_prevention", "participants_with_titles", "specific_opinions",
            "chair_summary", "discussion_date", "recorder_signature",
        ),
    }[rule_id]
    kind = raw.get("verification_kind")
    if (
        kind not in {
            "preop_content_complete",
            "preop_content_incomplete",
            "preop_surgery_association_ambiguous",
            "preop_discussion_content_uncertain",
            "preop_summary_content_uncertain",
            "preop_fact_extraction_invalid",
        }
        or raw.get("target_document") != target
        or raw.get("checked_fields") != list(allowed)
    ):
        return None
    if kind == "preop_fact_extraction_invalid":
        # 抽取未通过原文校验：只交付失败范围与字段名，不含任何模型引文或文书明细。
        invalid = raw.get("invalid_fields")
        scope = raw.get("failure_scope")
        if (
            set(raw) != {
                "verification_kind", "target_document", "checked_fields",
                "missing_fields", "documents", "failure_scope", "invalid_fields",
            }
            or raw.get("missing_fields") != []
            or raw.get("documents") != []
            or scope not in {"field", "document"}
            or not isinstance(invalid, list)
            or any(item not in allowed for item in invalid)
            or len(set(invalid)) != len(invalid)
            or (scope == "field" and not invalid)
        ):
            return None
        return {
            "verification_kind": kind,
            "target_document": target,
            "checked_fields": list(allowed),
            "missing_fields": [],
            "documents": [],
            "failure_scope": scope,
            "invalid_fields": list(invalid),
        }
    uncertain = raw.get("uncertain_fields", [])
    if kind == "preop_discussion_content_uncertain":
        # 内容unknown只属于079；不得夹带确认缺项、手术关联或未请求的事实。
        if (
            rule_id != "LX0609-04-01-05"
            or set(raw) != {
                "verification_kind", "target_document", "checked_fields",
                "missing_fields", "documents", "uncertain_fields",
            }
            or raw.get("missing_fields") != []
            or not isinstance(uncertain, list)
            or not uncertain
            or any(not isinstance(field, str) or field not in allowed for field in uncertain)
            or len(uncertain) != len(set(uncertain))
        ):
            return None
        documents = raw.get("documents")
        if not isinstance(documents, list) or not documents or any(
            not isinstance(item, Mapping)
            or set(item) != {"document_index", "event_index", "association_state", "missing_fields"}
            or type(item["document_index"]) is not int
            or item["document_index"] < 1
            or item["association_state"] != "not_required"
            or item["event_index"] is not None
            or item["missing_fields"] != []
            for item in documents
        ):
            return None
        if len({item["document_index"] for item in documents}) != len(documents):
            return None
    elif rule_id == "LX0609-04-01-04" and (
        kind == "preop_summary_content_uncertain" or "uncertain_fields" in raw
        or isinstance(raw.get("documents"), list) and any(
            isinstance(doc, Mapping) and "uncertain_fields" in doc for doc in raw["documents"]
        )
    ):
        # 078语义unknown与归属pending分别保留；旧已保存事实不强制补新键。
        keys = {"verification_kind", "target_document", "checked_fields", "missing_fields", "documents"}
        if set(raw) - keys - {"uncertain_fields", "pending_fields"} or not keys <= set(raw):
            return None
        if (
            not isinstance(uncertain, list)
            or any(not isinstance(field, str) or field not in allowed for field in uncertain)
            or len(uncertain) != len(set(uncertain))
            or ("uncertain_fields" in raw and (not uncertain or kind not in {"preop_summary_content_uncertain", "preop_content_incomplete"}))
            or kind == "preop_summary_content_uncertain" and (not uncertain or raw.get("missing_fields") != [])
        ):
            return None
        missing_fields = raw.get("missing_fields")
        if (
            not isinstance(missing_fields, list)
            or any(not isinstance(field, str) or field not in allowed for field in missing_fields)
            or len(missing_fields) != len(set(missing_fields))
            or set(missing_fields) & set(uncertain)
        ):
            return None
        documents = raw.get("documents")
        if not isinstance(documents, list) or not documents:
            return None
        seen: set[int] = set()
        all_unknown: set[str] = set()
        for doc in documents:
            if not isinstance(doc, Mapping) or set(doc) not in (
                {"document_index", "event_index", "association_state", "missing_fields"},
                {"document_index", "event_index", "association_state", "missing_fields", "uncertain_fields"},
            ):
                return None
            index, event, state = doc["document_index"], doc["event_index"], doc["association_state"]
            if (
                type(index) is not int or index < 1 or index in seen
                or not isinstance(state, str) or state not in {"matched", "not_required", "ambiguous"}
                or (state == "matched" and (type(event) is not int or event < 1))
                or (state != "matched" and event is not None)
            ):
                return None
            seen.add(index)
            doc_missing, doc_unknown = doc["missing_fields"], doc.get("uncertain_fields", [])
            for fields in (doc_missing, doc_unknown):
                if not isinstance(fields, list) or any(not isinstance(field, str) or field not in allowed for field in fields) or len(fields) != len(set(fields)):
                    return None
            if ("uncertain_fields" in doc and not doc_unknown) or set(doc_missing) & set(doc_unknown):
                return None
            all_unknown.update(doc_unknown)
        if not set(uncertain) <= all_unknown:
            return None
        pending_fields = raw.get("pending_fields", [])
        if not isinstance(pending_fields, list) or any(
            not isinstance(field, str) or field not in allowed or not any(
                doc["association_state"] == "ambiguous"
                and field not in doc["missing_fields"] and field not in doc.get("uncertain_fields", [])
                for doc in documents
            )
            for field in pending_fields
        ):
            return None
    elif "uncertain_fields" in raw or kind == "preop_summary_content_uncertain":
        return None
    missing = raw.get("missing_fields")
    if not isinstance(missing, list):
        return None
    safe_missing = list(dict.fromkeys(item for item in missing if item in allowed))
    if (kind == "preop_content_complete" and safe_missing) or (
        kind == "preop_content_incomplete" and not safe_missing
    ):
        return None
    pending = raw.get("pending_fields", [])
    if not isinstance(pending, list):
        return None
    safe_pending = list(dict.fromkeys(item for item in pending if item in allowed))
    if (
        len(safe_pending) != len(pending)
        # 待确认字段只属于术前小结，不能与确认缺项重叠，也不能出现在完整结论中。
        or (safe_pending and rule_id != "LX0609-04-01-04")
        or set(safe_pending) & set(safe_missing)
        or (safe_pending and kind == "preop_content_complete")
    ):
        return None
    documents = raw.get("documents")
    if not isinstance(documents, list):
        return None
    safe_documents: list[dict[str, Any]] = []
    for document in documents:
        document_keys = {"document_index", "event_index", "association_state", "missing_fields"}
        if not isinstance(document, Mapping) or not (
            set(document) == document_keys
            or rule_id == "LX0609-04-01-04" and set(document) == document_keys | {"uncertain_fields"}
        ):
            return None
        document_index = document.get("document_index")
        event_index = document.get("event_index")
        association_state = document.get("association_state")
        document_missing = document.get("missing_fields")
        if (
            not isinstance(document_index, int)
            or document_index < 1
            or event_index is not None
            and (not isinstance(event_index, int) or event_index < 1)
            or association_state not in {"matched", "not_required", "ambiguous"}
            or not isinstance(document_missing, list)
        ):
            return None
        safe_documents.append(
            {
                "document_index": document_index,
                "event_index": event_index,
                "association_state": association_state,
                "missing_fields": list(
                    dict.fromkeys(item for item in document_missing if item in allowed)
                ),
                **({"uncertain_fields": list(document["uncertain_fields"])} if "uncertain_fields" in document else {}),
            }
        )
    if kind == "preop_surgery_association_ambiguous" and not any(
        item["association_state"] == "ambiguous" for item in safe_documents
    ):
        return None
    return {
        "verification_kind": kind,
        "target_document": target,
        "checked_fields": list(allowed),
        "missing_fields": safe_missing,
        "documents": safe_documents,
        **({"uncertain_fields": list(uncertain)} if uncertain else {}),
        **({"pending_fields": safe_pending} if safe_pending else {}),
    }


def safe_surgery_document_customer_display_facts(
    *, rule_id: str, raw: Any
) -> dict[str, Any] | None:
    normalized_rule_id = str(rule_id or "").strip().upper()
    if normalized_rule_id not in SURGERY_DOCUMENT_CUSTOMER_RULE_IDS or not isinstance(raw, Mapping):
        return None
    if normalized_rule_id == "LX0609-04-01-01":
        return _safe_029(raw)
    if normalized_rule_id in {"LX0609-11-02-01", "LX0609-11-02-02"}:
        return _safe_034_035(normalized_rule_id, raw)
    if normalized_rule_id in {"LX0609-04-04-01", "LX0609-04-04-02"}:
        return _safe_036_037(normalized_rule_id, raw)
    if normalized_rule_id == "LX0609-04-04-03":
        return _safe_038(raw)
    if normalized_rule_id in {"LX0609-04-01-04", "LX0609-04-01-05"}:
        return _safe_preop_content(normalized_rule_id, raw)
    return _safe_039(raw)


def surgery_document_customer_fact_status_is_valid(
    *, rule_id: str, status: str, safe_facts: Mapping[str, Any] | None
) -> bool:
    if isinstance(safe_facts, Mapping) and safe_facts.get("verification_kind") == "preop_discussion_content_uncertain":
        return str(rule_id or "").strip().upper() == "LX0609-04-01-05" and status == "data_gap"
    if isinstance(safe_facts, Mapping) and safe_facts.get("verification_kind") == "preop_summary_content_uncertain":
        return str(rule_id or "").strip().upper() == "LX0609-04-01-04" and status == "data_gap"
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
        "preop_content_complete": "compliant",
        "preop_content_incomplete": "non_compliant",
        "preop_surgery_association_ambiguous": "data_gap",
        "preop_discussion_content_uncertain": "data_gap",
        "preop_summary_content_uncertain": "data_gap",
        "preop_fact_extraction_invalid": "data_gap",
    }.get(str(kind))
    return expected is not None and status == expected
