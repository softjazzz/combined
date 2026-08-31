from __future__ import annotations

import hashlib
import hmac
import json
import re
import uuid
from datetime import datetime
from typing import Any, Callable, Dict, List, Mapping, Optional, Sequence

import sqlalchemy as sa
from sqlalchemy import Table, and_, select
from sqlalchemy.orm import Session

from ...core.settings import get_settings
from ..case_identity import CaseRef
from ..luxian_0609.customer_renderer import RULE_SET_VERSION
from ..luxian_0609_result_aggregator import safe_luxian_0609_customer_display_facts
from ..luxian_0609_result_schema import CANONICAL_RESULT_STATUSES
from ..luxian_0609_rule_catalog import LUXIAN_0609_RULE_SET_KEY


RECORD_RESULT_ENVELOPE_SCHEMA = "lx0609-record-result-envelope-v1"
CANONICAL_RESULT_DELIVERY_MODE = "canonical_straight_through"
LX0609_CUSTOMER_RESULT_CONTRACT_ERROR = (
    "LX0609 客户结果解释合同不完整，拒绝交付确定问题"
)
_LX025_MISSING_FIELDS = {
    "implant_name",
    "implant_type",
    "implant_specification",
    "implant_material",
    "implant_quantity",
    "implant_barcode",
}
_LX018_DIAGNOSTIC_DIMENSIONS = {
    "anatomic_site",
    "laterality",
    "symptom_pattern",
    "disease_course",
    "disease_direction",
}
_STATUS_ALIASES = {
    "confirmed_defect": "non_compliant",
    "data_quality_gap": "data_gap",
    "technical_error_internal": "technical_error",
    "rejected_by_system": "technical_error",
    "evaluation_unknown": "uncertain",
    "failed": "technical_error",
}
_CUSTOMER_STATUSES = {
    "compliant",
    "non_compliant",
    "ai_suggested_compliant",
    "ai_suggested_non_compliant",
    "data_gap",
    "not_applicable",
    "not_executed",
    "technical_error",
    "uncertain",
}
_RECOMMENDATION_EVIDENCE_SOURCE_TYPES = {
    "consultation_record",
    "daily_course_record",
    "senior_course_record",
    "inpat_drug_order",
    "inpat_nondrug_order",
    "exam_master",
    "exam_item_report",
    "labtest_master",
    "labtest_item_report",
    "surgery_record",
}


def _safe_text(value: Any, default: str = "") -> str:
    if value is None:
        return default
    return str(value).strip()


def _safe_json_dumps(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, default=str)


def _safe_json_loads(value: Any, default: Any) -> Any:
    if value is None:
        return default
    if isinstance(value, (dict, list)):
        return value
    text = str(value).strip()
    if not text:
        return default
    try:
        return json.loads(text)
    except Exception:
        return default


def _to_int(value: Any, default: int = 0) -> int:
    try:
        if value is None:
            return default
        return int(value)
    except Exception:
        return default


def canonical_envelope_items_are_consistent(items: Any) -> bool:
    """校验 Canonical 交付项的唯一身份与冻结状态语义。"""

    if not isinstance(items, list):
        return False
    delivered_rule_ids: set[str] = set()
    for item in items:
        if not isinstance(item, dict):
            return False
        rule_id = _safe_text(item.get("rule_id") or item.get("rule_code")).upper()
        status = _safe_text(item.get("status"))
        result_status = _safe_text(item.get("result_status"))
        display_status = _safe_text(item.get("display_status"))
        expected_is_compliant = (
            True if status == "compliant" else False if status == "non_compliant" else None
        )
        if (
            not rule_id
            or rule_id in delivered_rule_ids
            or status not in CANONICAL_RESULT_STATUSES
            or result_status != status
            or (display_status and display_status != status)
            or item.get("is_compliant") is not expected_is_compliant
        ):
            return False
        delivered_rule_ids.add(rule_id)
    return True


def sanitize_canonical_facts(value: Any) -> Any:
    """移除 Canonical 交付事实中的内部身份主键，保留医学事实和值。"""

    internal_keys = {
        "record_id",
        "visit_id",
        "patient_id",
        "institute_id",
        "mr_no",
        "source_document_id",
        "document_id",
    }
    if isinstance(value, dict):
        return {
            key: sanitize_canonical_facts(item)
            for key, item in value.items()
            if key not in internal_keys
        }
    if isinstance(value, list):
        return [sanitize_canonical_facts(item) for item in value]
    return value


def _validate_recommendation_evidence_facts(value: Any) -> None:
    """Canonical 只接受已签名的逐建议证据引用。"""

    if not isinstance(value, dict) or "recommendation_evidence" not in value:
        return
    entries = value.get("recommendation_evidence")
    recommendation_count = value.get("recommendation_count")
    if (
        not isinstance(entries, list)
        or len(entries) > 96
        or type(recommendation_count) is not int
        or len(entries) != recommendation_count
    ):
        raise ValueError("invalid recommendation evidence")
    seen: set[tuple[int, int]] = set()
    for expected_index, entry in enumerate(entries, start=1):
        if not isinstance(entry, dict) or set(entry) != {
            "episode_index",
            "recommendation_index",
            "execution_state",
            "opinion_evidence",
            "execution_evidence",
        }:
            raise ValueError("invalid recommendation evidence")
        episode_index = entry.get("episode_index")
        recommendation_index = entry.get("recommendation_index")
        if (
            type(episode_index) is not int
            or type(recommendation_index) is not int
            or episode_index < 1
            or recommendation_index != expected_index
            or (episode_index, recommendation_index) in seen
        ):
            raise ValueError("invalid recommendation evidence")
        seen.add((episode_index, recommendation_index))
        if entry.get("execution_state") not in {"specific", "generic", "missing", "unknown"}:
            raise ValueError("invalid recommendation evidence")
        for key in ("opinion_evidence", "execution_evidence"):
            refs = entry.get(key)
            if not isinstance(refs, list) or len(refs) > 8:
                raise ValueError("invalid recommendation evidence")
            seen_refs: set[tuple[str, str]] = set()
            for ref in refs:
                if not isinstance(ref, dict) or set(ref) != {"source_type", "source_ref"}:
                    raise ValueError("invalid recommendation evidence")
                source_type = _safe_text(ref.get("source_type"))
                source_ref = _safe_text(ref.get("source_ref"))
                identity = (source_type, source_ref)
                if (
                    not source_type
                    or source_type not in _RECOMMENDATION_EVIDENCE_SOURCE_TYPES
                    or re.fullmatch(r"src_[0-9a-f]{24}", source_ref) is None
                    or identity in seen_refs
                ):
                    raise ValueError("invalid recommendation evidence")
                seen_refs.add(identity)


def customer_safe_projection_key() -> str:
    """返回仅用于客户结果不可逆引用的服务端密钥。"""

    secret = _safe_text(get_settings().JWT_SECRET)
    if not secret:
        raise RuntimeError("客户结果安全引用密钥未配置")
    return secret


def keyed_ref(prefix: str, value: Any, *, hmac_key: str) -> str:
    secret = _safe_text(hmac_key)
    if not secret:
        raise ValueError("hmac_key is required")
    material = _safe_text(value) or "missing"
    digest = hmac.new(
        secret.encode("utf-8"),
        f"{prefix}:{material}".encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    return f"{prefix}_{digest[:24]}"


def canonical_customer_status(item: Dict[str, Any]) -> str:
    for key in ("result_status", "status", "display_status"):
        raw = _safe_text(item.get(key)).lower()
        if not raw:
            continue
        normalized = _STATUS_ALIASES.get(raw, raw)
        if normalized in _CUSTOMER_STATUSES:
            return normalized
    if item.get("is_compliant") is True:
        return "compliant"
    if item.get("is_compliant") is False:
        return "non_compliant"
    return "uncertain"


def safe_customer_display_facts(
    item: Dict[str, Any],
    *,
    rule_id: str,
) -> Dict[str, Any]:
    """只允许规则专属枚举和计数进入客户 DTO，拒绝自由文本与病历原文。"""

    raw = item.get("customer_display_facts")
    if not isinstance(raw, dict):
        return {}
    shared = safe_luxian_0609_customer_display_facts(rule_id=rule_id, raw=raw)
    if shared is not None:
        if rule_id == "LX0609-025" and not shared.get("missing_fields"):
            return {}
        return shared
    if rule_id == "LX0609-025":
        missing_fields = raw.get("missing_fields")
        if not isinstance(missing_fields, list):
            return {}
        safe_missing_fields = [
            value
            for value in dict.fromkeys(missing_fields)
            if isinstance(value, str) and value in _LX025_MISSING_FIELDS
        ]
        if not safe_missing_fields:
            return {}
        return {
            "failure_kind": "implant_information_incomplete",
            "source_label": "手术记录",
            "missing_fields": safe_missing_fields,
        }
    if rule_id == "LX0609-024":
        checked_sources = raw.get("checked_sources")
        if (
            raw.get("failure_kind") != "lymph_node_dissection_not_documented"
            or raw.get("performed_surgery_confirmed") is not True
            or raw.get("malignant_surgery_confirmed") is not True
            or not isinstance(checked_sources, list)
        ):
            return {}
        sources = list(
            dict.fromkeys(
                value
                for value in checked_sources
                if value
                in {
                    "surgery_record",
                    "pathology_exam_master",
                    "pathology_exam_report",
                }
            )
        )
        if not sources:
            return {}
        return {
            "failure_kind": "lymph_node_dissection_not_documented",
            "performed_surgery_confirmed": True,
            "malignant_surgery_confirmed": True,
            "checked_sources": sources,
        }
    if rule_id == "LX0609-028":
        failure_kind = _safe_text(raw.get("failure_kind"))
        start_time = _safe_text(raw.get("start_time"))
        end_time = _safe_text(raw.get("end_time"))
        duration_hours = raw.get("duration_hours")
        threshold_hours = raw.get("threshold_hours")
        if (
            failure_kind
            not in {
                "prophylaxis_duration_over_48h",
                "prophylaxis_extension_reason_missing",
            }
            or raw.get("incision_class") not in {"I", "II"}
            or not re.fullmatch(r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}", start_time)
            or not re.fullmatch(r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}", end_time)
            or not isinstance(duration_hours, (int, float))
            or duration_hours <= 24
            or threshold_hours not in {24, 48}
        ):
            return {}
        if failure_kind == "prophylaxis_duration_over_48h" and (
            threshold_hours != 48 or duration_hours <= 48
        ):
            return {}
        if failure_kind == "prophylaxis_extension_reason_missing" and (
            threshold_hours != 24 or duration_hours > 48
        ):
            return {}
        return {
            "failure_kind": failure_kind,
            "incision_class": raw.get("incision_class"),
            "start_time": start_time,
            "end_time": end_time,
            "duration_hours": round(float(duration_hours), 2),
            "threshold_hours": threshold_hours,
        }
    if rule_id in {"LX0609-034", "LX0609-035"}:
        checked_sources = raw.get("checked_sources")
        if (
            raw.get("failure_kind") != "anesthesia_consent_missing"
            or raw.get("performed_anesthesia_confirmed") is not True
            or raw.get("consent_state") != "missing"
            or checked_sources != ["consent_form"]
        ):
            return {}
        return {
            "failure_kind": "anesthesia_consent_missing",
            "performed_anesthesia_confirmed": True,
            "consent_state": "missing",
            "checked_sources": ["consent_form"],
        }
    if rule_id in {"LX0609-036", "LX0609-037"}:
        missing_sources = raw.get("missing_visit_sources")
        if (
            raw.get("failure_kind") != "anesthesia_visit_missing"
            or raw.get("performed_anesthesia_confirmed") is not True
            or not isinstance(missing_sources, list)
        ):
            return {}
        safe_sources = list(
            dict.fromkeys(
                source
                for source in missing_sources
                if source in {"preane_surveil_record", "postane_surveil_record"}
            )
        )
        if not safe_sources:
            return {}
        return {
            "failure_kind": "anesthesia_visit_missing",
            "performed_anesthesia_confirmed": True,
            "missing_visit_sources": safe_sources,
        }
    if rule_id == "LX0609-039":
        checked_sources = raw.get("checked_sources")
        if (
            raw.get("failure_kind") != "preop_discussion_missing"
            or raw.get("performed_surgery_confirmed") is not True
            or raw.get("emergency_rescue_exception_absent") is not True
            or checked_sources != ["presurg_discussion"]
        ):
            return {}
        return {
            "failure_kind": "preop_discussion_missing",
            "performed_surgery_confirmed": True,
            "emergency_rescue_exception_absent": True,
            "checked_sources": ["presurg_discussion"],
        }
    surgery_document_targets = {
        "LX0609-029": "presurg_summary",
        "LX0609-030": "surgery_record",
        "LX0609-032": "surgery_safecheck_record",
    }
    target_document = surgery_document_targets.get(rule_id)
    if target_document is not None:
        failure_kind = _safe_text(raw.get("failure_kind"))
        if (
            failure_kind not in {"surgery_document_missing", "surgery_document_blank"}
            or _safe_text(raw.get("target_document")) != target_document
            or raw.get("performed_surgery_confirmed") is not True
        ):
            return {}
        return {
            "failure_kind": failure_kind,
            "target_document": target_document,
            "performed_surgery_confirmed": True,
        }
    return {}


def safe_criterion_results(item: Dict[str, Any]) -> List[Dict[str, Any]]:
    """透传 reducer/renderer 生成的通用子结论，不在持久化层重算业务规则。"""

    raw_rows = item.get("criterion_results")
    if not isinstance(raw_rows, list):
        return []
    rows: List[Dict[str, Any]] = []
    for raw in raw_rows[:8]:
        if not isinstance(raw, dict):
            continue
        criterion_id = _safe_text(raw.get("criterion_id"))
        kind = _safe_text(raw.get("kind"))
        status = _safe_text(raw.get("status"))
        reason_code = _safe_text(raw.get("reason_code"))
        if (
            not re.fullmatch(r"[a-z][a-z0-9_]{1,63}", criterion_id)
            or kind not in {"text_length", "semantic_relation"}
            or status not in {"passed", "failed", "unknown"}
            or not re.fullmatch(r"[a-z][a-z0-9_]{1,63}", reason_code)
        ):
            continue
        row: Dict[str, Any] = {
            "criterion_id": criterion_id,
            "kind": kind,
            "status": status,
            "reason_code": reason_code,
        }
        for key in ("source_fact", "left_fact", "right_fact"):
            value = _safe_text(raw.get(key))
            if value and re.fullmatch(r"[a-z][a-z0-9_.]{1,95}", value):
                row[key] = value
        for key in ("operator", "unit", "rationale_code"):
            value = _safe_text(raw.get(key))
            if value and re.fullmatch(r"[a-z][a-z0-9_]{0,63}", value):
                row[key] = value
        for key in ("actual_value", "expected_value"):
            value = raw.get(key)
            if (
                isinstance(value, (int, bool))
                and not isinstance(value, float)
                or isinstance(value, str)
                and len(value) <= 120
                or value is None
            ):
                row[key] = value
        dimensions = raw.get("dimensions")
        if isinstance(dimensions, list):
            row["dimensions"] = [
                value
                for value in dict.fromkeys(dimensions)
                if isinstance(value, str) and value in _LX018_DIAGNOSTIC_DIMENSIONS
            ][:8]
        fact_refs = raw.get("fact_refs")
        if isinstance(fact_refs, list):
            row["fact_refs"] = [
                value
                for value in dict.fromkeys(fact_refs)
                if isinstance(value, str) and re.fullmatch(r"[0-9a-f]{64}", value)
            ][:16]
        analysis = _safe_text(raw.get("medical_analysis"))
        if analysis:
            row["medical_analysis"] = analysis[:2000]
        rows.append(row)
    return rows


def validated_customer_explanation(
    item: Dict[str, Any],
    *,
    rule_id: str,
    status: str,
) -> tuple[Dict[str, Any], List[Dict[str, Any]]]:
    """校验确定问题具备可审计解释；投影与Canonical写入共用同一合同。"""

    customer_display_facts = safe_customer_display_facts(item, rule_id=rule_id)
    criterion_results = safe_criterion_results(item)
    has_failed_criterion = any(row.get("status") == "failed" for row in criterion_results)
    if (
        status == "non_compliant"
        and rule_id.startswith("LX0609-")
        and not customer_display_facts
        and not has_failed_criterion
    ):
        raise ValueError(LX0609_CUSTOMER_RESULT_CONTRACT_ERROR)
    return customer_display_facts, criterion_results


def envelope_item_from_rule_result(item: Dict[str, Any]) -> Dict[str, Any]:
    """截取 RuleDecision 交付所需字段，避免 Envelope 变成任务调试日志。"""

    allowed_keys = {
        "schema_version", "record_id", "institute_id", "patient_id", "visit_id",
        "mr_no", "record_ref", "customer_rule_id", "qc_point_id", "rule_id",
        "rule_code", "rule_name", "rule_version", "status", "result_status",
        "display_status", "is_compliant", "reason_code", "reason", "reason_detail",
        "reason_details", "conclusion", "findings", "detail", "actual", "standard",
        "suggestion", "customer_conclusion", "customer_suggestion", "customer_message",
        "customer_display_facts", "criterion_results", "decision_facts",
        "customer_evidence", "evidence_items", "evidence_refs", "evidence",
        "model_analysis", "medical_analysis", "semantic_analysis", "llm_analysis",
        "model_suggestion", "llm_suggestion", "data_gap_details", "missing_sources",
        "missing_fields", "required_sources", "unavailable_sources", "missing_evidence",
        "source_availability", "source_status", "evidence_availability",
    }
    result = {
        key: item.get(key)
        for key in allowed_keys
        if key in item and (item.get(key) is not None or key == "is_compliant")
    }
    _validate_recommendation_evidence_facts(result.get("customer_display_facts"))
    if not isinstance(result.get("decision_facts"), dict) and isinstance(
        result.get("customer_display_facts"), dict
    ):
        result["decision_facts"] = result["customer_display_facts"]
    if not isinstance(result.get("customer_display_facts"), dict) and isinstance(
        result.get("decision_facts"), dict
    ):
        result["customer_display_facts"] = result["decision_facts"]
    _validate_recommendation_evidence_facts(result.get("customer_display_facts"))

    if not _safe_text(result.get("conclusion")):
        for key in ("customer_conclusion", "findings"):
            value = _safe_text(item.get(key))
            if value:
                result["conclusion"] = value
                break
    if not _safe_text(result.get("suggestion")):
        for key in ("customer_suggestion", "model_suggestion", "llm_suggestion"):
            value = _safe_text(item.get(key))
            if value:
                result["suggestion"] = value
                break
    if not _safe_text(result.get("detail")):
        for key in ("reason_detail", "reason", "reason_details"):
            raw_value = item.get(key)
            value = _safe_text(raw_value) if isinstance(raw_value, str) else ""
            if value:
                result["detail"] = value
                break
    if not _safe_text(result.get("model_analysis")):
        for key in ("medical_analysis", "semantic_analysis", "llm_analysis"):
            value = _safe_text(item.get(key))
            if value:
                result["model_analysis"] = value
                break

    item_status = _safe_text(
        result.get("status") or result.get("result_status") or result.get("display_status")
    )
    if item_status in {"data_gap", "evaluation_unknown", "uncertain"}:
        gap_details = result.get("data_gap_details")
        if not isinstance(gap_details, dict):
            gap_details = {}
        for key in (
            "reason_code", "missing_sources", "missing_fields", "required_sources",
            "unavailable_sources", "missing_evidence", "source_availability",
            "source_status", "evidence_availability",
        ):
            value = result.get(key)
            if value not in (None, "", [], {}):
                gap_details.setdefault(key, value)
        if gap_details:
            result["data_gap_details"] = gap_details

    hmac_key = customer_safe_projection_key()
    record_id = _safe_text(item.get("record_id") or item.get("visit_id"))
    if record_id:
        result["record_ref"] = keyed_ref("rec", record_id, hmac_key=hmac_key)
    for key in ("record_id", "institute_id", "patient_id", "visit_id", "mr_no"):
        result.pop(key, None)

    evidence_rows: List[Dict[str, Any]] = []
    for key in ("customer_evidence", "evidence_items", "evidence_refs", "evidence"):
        candidates = item.get(key)
        if not isinstance(candidates, list):
            continue
        for candidate in candidates:
            if not isinstance(candidate, dict):
                continue
            source_material = (
                candidate.get("source_ref")
                or candidate.get("document_ref")
                or candidate.get("fact_ref")
                or candidate.get("source_document_id")
            )
            if not _safe_text(source_material):
                continue
            row = {
                key: value
                for key, value in candidate.items()
                if key not in {"source_document_id", "document_id", "fact_ref", "document_ref"}
            }
            source_ref = _safe_text(source_material)
            row["source_ref"] = (
                source_ref
                if re.fullmatch(r"src_[0-9a-f]{24}", source_ref)
                else keyed_ref("src", source_material, hmac_key=hmac_key)
            )
            evidence_rows.append(row)
    for key in ("customer_evidence", "evidence_items", "evidence_refs"):
        result.pop(key, None)
    result["evidence"] = evidence_rows
    for key in ("customer_display_facts", "decision_facts"):
        if isinstance(result.get(key), (dict, list)):
            result[key] = sanitize_canonical_facts(result[key])
    return result


class CanonicalResultStore:
    """Canonical Envelope 的唯一校验、写入与精确读取模块。"""

    def __init__(self, table: Optional[Table]) -> None:
        self.table = table

    def _require_table(self) -> Table:
        if self.table is None:
            raise AttributeError("Canonical Result Envelope table is unavailable")
        return self.table

    def replace_for_job(
        self,
        session: Session,
        *,
        job_row: Dict[str, Any],
        items: Sequence[Dict[str, Any]],
        now: datetime,
        projector: Callable[[Dict[str, Any]], Dict[str, Any]],
    ) -> None:
        table = self._require_table()
        filters = _safe_json_loads(job_row.get("filters_json"), {})
        filters = filters if isinstance(filters, dict) else {}
        rule_set_key = _safe_text(filters.get("rule_set_key"), LUXIAN_0609_RULE_SET_KEY)
        rule_set_version = _safe_text(filters.get("rule_set_version"), RULE_SET_VERSION)
        job_id = _safe_text(job_row.get("id"))
        root_job_id = _safe_text(job_row.get("parent_job_id")) or job_id
        created_by = _safe_text(job_row.get("created_by"))
        normalized_items: List[Dict[str, Any]] = []
        for raw_item in items:
            if not isinstance(raw_item, Mapping):
                raise ValueError("Canonical Envelope 结果项格式非法，拒绝完成质控任务")
            normalized_items.append(dict(raw_item))

        grouped: Dict[CaseRef, List[Dict[str, Any]]] = {}
        for raw_item in normalized_items:
            if not all(
                _safe_text(raw_item.get(key))
                for key in ("institute_id", "patient_id", "visit_id")
            ):
                raise ValueError("Canonical Envelope 病例三坐标不完整，拒绝完成质控任务")
            record_ref = CaseRef.from_mapping(raw_item)
            grouped.setdefault(record_ref, []).append(raw_item)

        expected_record_refs: set[CaseRef] = set()
        for raw_ref in list(filters.get("record_refs") or []):
            if not isinstance(raw_ref, Mapping):
                continue
            record_ref = CaseRef.from_mapping(raw_ref)
            if all(record_ref):
                expected_record_refs.add(record_ref)
        if (
            rule_set_key == LUXIAN_0609_RULE_SET_KEY
            and expected_record_refs
            and set(grouped) != expected_record_refs
        ):
            raise ValueError("Canonical Envelope 病例集合不完整，拒绝完成质控任务")

        scoped_rule_ids = list(filters.get("scoped_customer_rule_ids") or [])
        expected_delivery_rule_ids = {
            _safe_text(rule_id).upper()
            for rule_id in [
                *(scoped_rule_ids or list(filters.get("rule_ids") or [])),
                *list(filters.get("gate_only_customer_rule_ids") or []),
                *list(filters.get("paused_customer_rule_ids") or []),
            ]
            if _safe_text(rule_id)
        }
        for record_items in grouped.values():
            # 历史/兼容执行器可能只留下“确定问题”状态，却没有可审计事实。
            # 在写入 Canonical 前安全降级为资料待核实，避免整批任务失败，
            # 同时禁止无证据的确定问题进入客户结果。
            for record_item in record_items:
                candidate_rule_id = _safe_text(
                    record_item.get("customer_rule_id")
                    or record_item.get("qc_point_id")
                    or record_item.get("rule_id")
                    or record_item.get("rule_code")
                ).upper()
                candidate_status = canonical_customer_status(record_item)
                if (
                    candidate_status == "non_compliant"
                    and candidate_rule_id.startswith("LX0609-")
                    and not record_item.get("customer_display_facts")
                    and not record_item.get("criterion_results")
                ):
                    record_item["status"] = "data_gap"
                    record_item["result_status"] = "data_gap"
                    record_item["display_status"] = "data_gap"
                    record_item["is_compliant"] = None
                    record_item["reason_code"] = "historical_evidence_missing"

            delivered_rule_ids = [
                _safe_text(item.get("rule_id") or item.get("rule_code")).upper()
                for item in record_items
            ]
            if (
                rule_set_key == LUXIAN_0609_RULE_SET_KEY
                and expected_delivery_rule_ids
                and (
                    any(not rule_id for rule_id in delivered_rule_ids)
                    or len(delivered_rule_ids) != len(set(delivered_rule_ids))
                    or set(delivered_rule_ids) != expected_delivery_rule_ids
                )
            ):
                raise ValueError("Canonical Envelope 规则集合不完整，拒绝完成质控任务")
            if not canonical_envelope_items_are_consistent(record_items):
                raise ValueError("Canonical Envelope 状态字段不一致，拒绝完成质控任务")
            for record_item in record_items:
                rule_id = _safe_text(
                    record_item.get("customer_rule_id")
                    or record_item.get("qc_point_id")
                    or record_item.get("rule_id")
                    or record_item.get("rule_code")
                ).upper()
                validated_customer_explanation(
                    record_item,
                    rule_id=rule_id,
                    status=canonical_customer_status(record_item),
                )

        prepared_envelopes: List[tuple[CaseRef, Dict[str, Any]]] = []
        for record_ref, record_items in grouped.items():
            record_id = record_ref.visit_id
            envelope = {
                "schema_version": RECORD_RESULT_ENVELOPE_SCHEMA,
                "delivery_mode": CANONICAL_RESULT_DELIVERY_MODE,
                "record_id": record_id,
                "record_ref": keyed_ref(
                    "rec",
                    record_ref.as_key(),
                    hmac_key=customer_safe_projection_key(),
                ),
                "job_id": job_id,
                "root_job_id": root_job_id,
                "rule_set_key": rule_set_key,
                "rule_set_version": rule_set_version,
                "items": [projector(item) for item in record_items],
            }
            prepared_envelopes.append((record_ref, envelope))

        for record_ref, envelope in prepared_envelopes:
            record_id = record_ref.visit_id
            session.execute(
                table.delete().where(
                    and_(
                        table.c.job_id == job_id,
                        table.c.institute_id == record_ref.institute_id,
                        table.c.patient_id == record_ref.patient_id,
                        table.c.visit_id == record_ref.visit_id,
                    )
                )
            )
            session.execute(
                table.insert().values(
                    id=str(uuid.uuid4()),
                    job_id=job_id,
                    root_job_id=root_job_id,
                    created_by=created_by,
                    record_id=record_id,
                    institute_id=record_ref.institute_id,
                    patient_id=record_ref.patient_id,
                    visit_id=record_ref.visit_id,
                    rule_set_key=rule_set_key,
                    rule_set_version=rule_set_version,
                    envelope_json=_safe_json_dumps(envelope),
                    result_count=len(envelope["items"]),
                    created_at=now,
                    updated_at=now,
                )
            )

    def load_selected(
        self,
        session: Session,
        *,
        job_id: str,
        created_by: str,
        institute_id: str,
        patient_id: str,
        visit_id: str,
        rule_set_key: str,
        rule_set_version: str,
    ) -> Dict[str, Any]:
        table = self._require_table()
        try:
            rows = (
                session.execute(
                    select(table).where(
                        and_(
                            table.c.job_id == job_id,
                            table.c.created_by == created_by,
                            table.c.record_id == visit_id,
                            table.c.institute_id == institute_id,
                            table.c.patient_id == patient_id,
                            table.c.visit_id == visit_id,
                            table.c.rule_set_key == rule_set_key,
                            table.c.rule_set_version == rule_set_version,
                        )
                    )
                )
                .mappings()
                .all()
            )
        except (sa.exc.ProgrammingError, sa.exc.OperationalError):
            return {}
        if len(rows) != 1:
            return {}
        envelope = _safe_json_loads(rows[0].get("envelope_json"), {})
        if (
            not isinstance(envelope, dict)
            or envelope.get("schema_version") != RECORD_RESULT_ENVELOPE_SCHEMA
            or envelope.get("delivery_mode") != CANONICAL_RESULT_DELIVERY_MODE
            or not isinstance(envelope.get("items"), list)
        ):
            return {}
        return envelope

    def load_root_job_items(
        self,
        *,
        job: Dict[str, Any],
        session_factory: Callable[[], Session],
    ) -> List[Dict[str, Any]]:
        job_id = _safe_text(job.get("id"))
        created_by = _safe_text(job.get("created_by"))
        if not job_id or not created_by or _safe_text(job.get("status")) != "completed":
            raise ValueError("批量质控任务尚未形成可导出的 Canonical 结果")
        filters = job.get("filters") if isinstance(job.get("filters"), dict) else {}
        rule_set_key = _safe_text(filters.get("rule_set_key"), LUXIAN_0609_RULE_SET_KEY)
        rule_set_version = _safe_text(filters.get("rule_set_version"), RULE_SET_VERSION)
        expected_refs = {
            CaseRef.from_mapping(ref)
            for ref in list(filters.get("record_refs") or [])
            if isinstance(ref, Mapping) and all(CaseRef.from_mapping(ref))
        }
        total_records = _to_int(job.get("total_records"))
        if total_records > 0 and (not expected_refs or len(expected_refs) != total_records):
            raise ValueError("批量质控任务缺少完整的冻结病历范围")

        table = self._require_table()
        session = session_factory()
        try:
            envelope_rows = (
                session.execute(
                    select(table).where(
                        and_(
                            table.c.root_job_id == job_id,
                            table.c.created_by == created_by,
                            table.c.rule_set_key == rule_set_key,
                            table.c.rule_set_version == rule_set_version,
                        )
                    )
                )
                .mappings()
                .all()
            )
        finally:
            session.close()

        rows_by_ref: Dict[CaseRef, Dict[str, Any]] = {}
        canonical_items: List[Dict[str, Any]] = []
        for raw_row in envelope_rows:
            row = dict(raw_row)
            case_ref = CaseRef.from_mapping(row)
            if not all(case_ref) or case_ref in rows_by_ref:
                raise ValueError("批量质控 Canonical Envelope 病历身份无效")
            rows_by_ref[case_ref] = row
            envelope = _safe_json_loads(row.get("envelope_json"), {})
            if (
                not isinstance(envelope, dict)
                or envelope.get("schema_version") != RECORD_RESULT_ENVELOPE_SCHEMA
                or envelope.get("delivery_mode") != CANONICAL_RESULT_DELIVERY_MODE
                or _safe_text(envelope.get("root_job_id")) != job_id
                or not isinstance(envelope.get("items"), list)
            ):
                raise ValueError("批量质控 Canonical Envelope 结构无效")
            record_ref = _safe_text(envelope.get("record_ref"))
            if not re.fullmatch(r"rec_[0-9a-f]{24}", record_ref):
                raise ValueError("批量质控 Canonical Envelope 病历引用无效")
            if not canonical_envelope_items_are_consistent(envelope["items"]):
                raise ValueError("canonical_result_envelope_invalid")
            for raw_item in envelope["items"]:
                canonical_items.append({**raw_item, "record_ref": record_ref})

        actual_refs = set(rows_by_ref)
        if expected_refs and actual_refs != expected_refs:
            raise ValueError("批量质控 Canonical Envelope 病历集合不完整")
        if not envelope_rows and int(job.get("total_records") or 0) > 0:
            raise ValueError("批量质控 Canonical Envelope 缺失")
        return canonical_items
