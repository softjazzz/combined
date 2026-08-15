from __future__ import annotations

import html
import hashlib
import hmac
import json
import os
import re
import uuid
from dataclasses import dataclass
from datetime import date, datetime
from io import BytesIO, StringIO
from functools import lru_cache
from typing import Any, Callable, Dict, Iterable, List, Mapping, Optional, Sequence

import sqlalchemy as sa
from sqlalchemy import (
    JSON,
    MetaData,
    Table,
    and_,
    asc,
    desc,
    func,
    or_,
    select,
    text,
    tuple_,
    update,
)
from sqlalchemy.orm import Session

from ..core.settings import get_settings
from .document_domain_alignment import (
    align_document_domain_fields,
    normalize_document_label,
)
from .luxian_0609.customer_renderer import RULE_SET_VERSION
from .luxian_0609.record_result_read_model import (
    _generation_key,
    _rule_set_value,
    select_latest_authoritative_record_result_job,
)
from .luxian_0609_rule_catalog import (
    LUXIAN_0609_RULE_SET_KEY,
    get_luxian_0609_rule,
    load_luxian_0609_rules,
)
from .luxian_0609_rule_master import load_luxian_0609_rule_master
from .luxian_0609_result_aggregator import safe_luxian_0609_customer_display_facts
from .luxian_0609_result_schema import CANONICAL_RESULT_STATUSES
from .luxian_0609_result_export_service import customer_evidence_summary
from .luxian_0609.customer_renderer import compliant_customer_finding
from .bundles.emr_view import load_bundle_documents
from .case_identity import CaseRef, CaseRefInput, normalize_case_refs
from ..database.connection import DB_SCHEMA_MODE, SessionLocal, engine
from ..database.models.cdm import (
    AdmissionRecord,
    DischargeRecord,
    InpatRegistration,
    MedicalRecordFrontpage,
)


DEFAULT_DOCUMENT_TYPE = "日常病程记录"
DEFAULT_COMPLEXITY = "中复杂度"
DEFAULT_DEFECT_LEVEL = "一般缺陷"
DEFAULT_BATCH_JOB_PAGE_SIZE = 10

SEVERITY_TO_DEFECT_LEVEL = {
    "critical": "严重缺陷",
    "major": "一般缺陷",
    "minor": "提示性缺陷",
}

DEFECT_LEVEL_TO_SEVERITY = {
    "严重缺陷": "critical",
    "一般缺陷": "major",
    "提示性缺陷": "minor",
}

_CUSTOMER_RESULT_SCHEMA = "customer-qc-result-v1"
_RECORD_RESULT_ENVELOPE_SCHEMA = "lx0609-record-result-envelope-v1"
_CANONICAL_RESULT_DELIVERY_MODE = "canonical_straight_through"
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
_REASON_CODE_PATTERN = re.compile(r"^[a-z][a-z0-9]*(?:_[a-z0-9]+)*$")
_SAFE_SOURCE_TYPE_PATTERN = re.compile(r"^[a-z][a-z0-9]*(?:_[a-z0-9]+)*$")
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


def _canonical_envelope_items_are_consistent(items: Any) -> bool:
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
            True
            if status == "compliant"
            else False
            if status == "non_compliant"
            else None
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


_GENERIC_CUSTOMER_TEXT = {
    "compliant": ("未发现该质控点对应的明确问题。", "无需处理。"),
    "non_compliant": ("发现该质控点对应的明确问题。", "请按质控要求补充或修正。"),
    "ai_suggested_compliant": ("AI判断暂未发现明确问题。", "建议结合病历资料确认。"),
    "ai_suggested_non_compliant": ("AI建议结合病历资料进一步确认。", "请确认后再决定是否整改。"),
    "data_gap": ("当前受控数据不足以形成确定结论。", "请补充或同步所需数据后重新评估。"),
    "not_applicable": ("当前病历不适用该质控点。", "无需处理。"),
    "not_executed": ("该质控点未完成执行。", "请确认执行条件后重新评估。"),
    "technical_error": ("本次质控未能形成有效结论。", "请稍后重试或联系管理员。"),
    "uncertain": ("现有证据无法形成确定结论。", "建议结合病历资料进一步确认。"),
}
_CUSTOMER_TEXT_FORBIDDEN = re.compile(
    r"(LLM|prompt|raw_response|medical_text|record_content|documents|bundle|embedding|"
    r"\braw\b|\bevidence\b)",
    re.IGNORECASE,
)


def _now_utc() -> datetime:
    return datetime.utcnow()


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
        parsed = json.loads(text)
        return parsed
    except Exception:
        return default


def _sanitize_canonical_facts(value: Any) -> Any:
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
            key: _sanitize_canonical_facts(item)
            for key, item in value.items()
            if key not in internal_keys
        }
    if isinstance(value, list):
        return [_sanitize_canonical_facts(item) for item in value]
    return value


def customer_safe_projection_key() -> str:
    """返回仅用于客户结果不可逆引用的服务端密钥。"""

    secret = _safe_text(get_settings().JWT_SECRET)
    if not secret:
        raise RuntimeError("客户结果安全引用密钥未配置")
    return secret


def _keyed_ref(prefix: str, value: Any, *, hmac_key: str) -> str:
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


def build_customer_safe_source_ref(value: Any) -> str:
    """为受控文书生成与结果证据完全一致的不可逆引用。"""

    return _keyed_ref("src", value, hmac_key=customer_safe_projection_key())


def _canonical_customer_status(item: Dict[str, Any]) -> str:
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


def _canonical_reason_code(item: Dict[str, Any]) -> str:
    candidates = [item.get("reason_code")]
    for key in ("decision", "metadata", "audit"):
        nested = item.get(key)
        if isinstance(nested, dict):
            candidates.append(nested.get("reason_code"))
    for candidate in candidates:
        value = _safe_text(candidate)
        if value and len(value) <= 64 and _REASON_CODE_PATTERN.fullmatch(value):
            return value
    return "reason_unavailable"


def _explicit_customer_text(item: Dict[str, Any], keys: Sequence[str], fallback: str) -> str:
    private_values = {
        _safe_text(item.get(key))
        for key in (
            "record_id",
            "visit_id",
            "patient_id",
            "institute_id",
            "mr_no",
            "patient_name",
            "name",
            "phone",
            "id_card",
            "certificate_no",
        )
        if _safe_text(item.get(key))
    }
    for key in keys:
        value = _safe_text(item.get(key))
        if not value or _CUSTOMER_TEXT_FORBIDDEN.search(value):
            continue
        if any(private_value in value for private_value in private_values):
            continue
        return _truncate_export_text(value, 360)
    return fallback


def _safe_evidence_rows(item: Dict[str, Any], *, hmac_key: str) -> List[Dict[str, str]]:
    candidates: List[Any] = []
    for key in ("customer_evidence", "evidence_items", "evidence_refs", "evidence"):
        value = item.get(key)
        if isinstance(value, list):
            candidates.extend(value)
    rows: List[Dict[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for candidate in candidates:
        if not isinstance(candidate, dict):
            continue
        source_type = _safe_text(
            candidate.get("source_type")
            or candidate.get("source_table")
            or candidate.get("document_type")
        ).lower()
        if not _SAFE_SOURCE_TYPE_PATTERN.fullmatch(source_type):
            source_type = "document"
        source_material = (
            candidate.get("source_ref")
            or candidate.get("document_ref")
            or candidate.get("fact_ref")
            or candidate.get("source_document_id")
        )
        if not _safe_text(source_material):
            continue
        source_ref = _safe_text(source_material)
        if not re.fullmatch(r"src_[0-9a-f]{24}", source_ref):
            source_ref = _keyed_ref("src", source_material, hmac_key=hmac_key)
        identity = (source_type, source_ref)
        if identity in seen:
            continue
        seen.add(identity)
        row = {"source_type": source_type, "source_ref": source_ref}
        # 字段路径不是病历正文，只用于让单病历页在已授权文书内定位结构化章节。
        # 只允许普通字段名，禁止把任意模型输出或正文透传为字段路径。
        field_path = _safe_text(
            candidate.get("field_path") or candidate.get("source_field")
        ).lower()
        if re.fullmatch(r"[a-z][a-z0-9_]{0,63}", field_path):
            row["field_path"] = field_path
        # Canonical 中已经绑定到安全 src_ref 的授权短摘录可以用于离线核查；
        # 这里只保留固定长度摘录和受控层级，不接受任意正文或定位对象。
        excerpt = _compact_authorized_evidence_excerpt(
            candidate.get("evidence_excerpt")
        )
        excerpt_kind = _safe_text(candidate.get("excerpt_kind"))
        if excerpt and excerpt_kind in {"字段级依据", "文书级依据"}:
            row["evidence_excerpt"] = excerpt
            row["excerpt_kind"] = excerpt_kind
        record_time = _safe_text(candidate.get("record_time"))
        if re.fullmatch(
            r"\d{4}-\d{2}-\d{2}(?:[ T]\d{2}:\d{2}(?::\d{2})?(?:[+-]\d{2}:?\d{2})?)?",
            record_time,
        ):
            row["record_time"] = record_time
        rows.append(row)
        if len(rows) >= 8:
            break
    return rows


def _compact_authorized_evidence_excerpt(value: Any, *, limit: int = 300) -> str:
    """把已授权文书的短文本收敛为单病历结果卡片可用的摘录。"""

    compact = re.sub(r"\s+", " ", _safe_text(value)).strip()
    if not compact:
        return ""
    return compact[:limit] + ("…" if len(compact) > limit else "")


def _authorized_document_excerpt(
    document: Dict[str, Any],
    *,
    field_path: str = "",
) -> tuple[str, str]:
    """返回精确字段摘录或明确标注的文书级摘录；不做正文相似匹配。"""

    normalized_field = _safe_text(field_path).lower()
    if normalized_field:
        matches = [
            section
            for section in list(document.get("sections") or [])
            if isinstance(section, dict)
            and _safe_text(section.get("source_field") or section.get("key")).lower()
            == normalized_field
        ]
        if len(matches) == 1:
            excerpt = _compact_authorized_evidence_excerpt(matches[0].get("text"))
            if excerpt:
                return excerpt, "字段级依据"

    # 缺失字段类结论没有“缺失字段原文”；只能呈现同一 src_ref 已绑定文书的
    # 文书级摘录，且明确标识，避免客户误解为精确命中片段。
    for section in list(document.get("sections") or []):
        if not isinstance(section, dict):
            continue
        excerpt = _compact_authorized_evidence_excerpt(section.get("text"))
        if excerpt:
            return excerpt, "文书级依据"
    return _compact_authorized_evidence_excerpt(document.get("content")), "文书级依据"


def attach_authorized_evidence_excerpts(
    items: Sequence[Dict[str, Any]],
    *,
    institute_id: str,
    patient_id: str,
    visit_id: str,
) -> None:
    """在单病历任务已授权的边界内，为精确 source_ref 附加短摘录。

    本函数只由 ``build_latest_single_record_result_dto`` 调用。它不服务批量接口、
    导出或日志，也不以标题、正文相似度或 source_type 猜测文书。
    """

    if not all((_safe_text(institute_id), _safe_text(patient_id), _safe_text(visit_id))):
        return
    try:
        bundle = load_bundle_documents(
            institute_id=_safe_text(institute_id),
            patient_id=_safe_text(patient_id),
            visit_id=_safe_text(visit_id),
            bundle_schema="public",
        )
    except Exception:
        # 单病历原文辅助能力失败不得改变已保存的质控结论。
        return

    documents_by_ref: Dict[str, List[Dict[str, Any]]] = {}
    for document in list(bundle.get("documents") or []):
        if not isinstance(document, dict):
            continue
        source_document_id = _safe_text(document.get("document_id"))
        if not source_document_id:
            continue
        source_ref = build_customer_safe_source_ref(source_document_id)
        documents_by_ref.setdefault(source_ref, []).append(document)

    for item in items:
        if not isinstance(item, dict):
            continue
        for evidence in list(item.get("evidence") or []):
            if not isinstance(evidence, dict):
                continue
            source_ref = _safe_text(evidence.get("source_ref"))
            matches = documents_by_ref.get(source_ref) or []
            # 同一 src_ref 对应零份或多份文书时 fail-closed，绝不返回摘录。
            if len(matches) != 1:
                continue
            excerpt, excerpt_kind = _authorized_document_excerpt(
                matches[0],
                field_path=_safe_text(evidence.get("field_path")),
            )
            if excerpt:
                evidence["evidence_excerpt"] = excerpt
                evidence["excerpt_kind"] = excerpt_kind


def _safe_customer_display_facts(
    item: Dict[str, Any],
    *,
    rule_id: str,
) -> Dict[str, Any]:
    """只允许规则专属枚举和计数进入客户 DTO，拒绝自由文本与病历原文。"""

    raw = item.get("customer_display_facts")
    if not isinstance(raw, dict):
        return {}
    # 结果聚合与持久化/API 投影必须使用同一套字段白名单。过去这里维护了
    # 第二份子集，导致聚合层已经生成的时限、检查检验等解释在保存后被丢弃。
    shared = safe_luxian_0609_customer_display_facts(rule_id=rule_id, raw=raw)
    if shared is not None:
        return shared
    if rule_id == "LX0609-025":
        missing_fields = raw.get("missing_fields")
        result = {
            "failure_kind": "implant_information_incomplete",
            "source_label": "手术记录",
        }
        if isinstance(missing_fields, list):
            result["missing_fields"] = [
                value
                for value in dict.fromkeys(missing_fields)
                if isinstance(value, str) and value in _LX025_MISSING_FIELDS
            ]
        return result
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


def _safe_criterion_results(item: Dict[str, Any]) -> List[Dict[str, Any]]:
    """透传 reducer/renderer 生成的通用子结论，不在 API 层重算业务规则。"""

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
                or isinstance(value, str) and len(value) <= 120
                or value is None
            ):
                row[key] = value
        dimensions = raw.get("dimensions")
        if isinstance(dimensions, list):
            row["dimensions"] = [
                value
                for value in dict.fromkeys(dimensions)
                if isinstance(value, str)
                and value in _LX018_DIAGNOSTIC_DIMENSIONS
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


def _single_record_model_analysis(item: Dict[str, Any]) -> str:
    """保留规则执行器提供的医学分析，不在展示层二次概括或推断。"""

    return _safe_text(item.get("model_analysis") or item.get("medical_analysis"))[:8000]


def project_customer_safe_result_item(
    item: Dict[str, Any],
    *,
    hmac_key: str,
) -> Dict[str, Any]:
    """把任意内部结果投影为唯一、可审计且不含病历原文/身份的客户 DTO。"""

    raw = dict(item or {})
    status = _canonical_customer_status(raw)
    record_material = "|".join(
        _safe_text(raw.get(key))
        for key in ("institute_id", "patient_id", "visit_id", "record_id", "mr_no")
    )
    existing_record_ref = _safe_text(raw.get("record_ref"))
    record_ref = (
        existing_record_ref
        if re.fullmatch(r"rec_[0-9a-f]{24}", existing_record_ref)
        else _keyed_ref("rec", record_material, hmac_key=hmac_key)
    )
    is_safe_dto = _safe_text(raw.get("schema_version")) == _CUSTOMER_RESULT_SCHEMA
    rule_id = _safe_text(
        raw.get("customer_rule_id")
        or raw.get("qc_point_id")
        or raw.get("rule_id")
        or raw.get("rule_code")
    ).upper()
    customer_display_facts = _safe_customer_display_facts(raw, rule_id=rule_id)
    criterion_results = _safe_criterion_results(raw)
    # 不允许无规则专属事实或子结论的结果，以通用“发现问题”文案作为客户确定缺陷。
    # 这只收紧客户投影；原始执行状态仍留在持久化记录中，供内部追溯。
    explanation_incomplete = (
        status == "non_compliant"
        and not customer_display_facts
        and not criterion_results
    )
    if explanation_incomplete:
        status = "uncertain"
    generic_conclusion, generic_suggestion = _GENERIC_CUSTOMER_TEXT[status]
    # 原始执行结果中的 customer_* 字段仍可能混入病历句子。只有已经通过本投影器
    # 生成的 DTO 才允许复用客户文案；首次投影一律按状态生成固定安全表述。
    # 一旦确定性结论因缺少规则事实被降级，就绝不能继续复用历史 DTO 的
    # “发现问题”类文案；否则状态和客户可见结论会彼此矛盾。
    reuse_saved_customer_text = is_safe_dto and not explanation_incomplete
    conclusion = _explicit_customer_text(
        raw,
        (
            "conclusion",
            "customer_conclusion",
            "customer_message",
            "customer_summary",
        )
        if reuse_saved_customer_text
        else (),
        generic_conclusion,
    )
    if status == "compliant" and rule_id.startswith("LX0609-"):
        # Canonical Envelope 在此唯一生成。合规说明只取规则身份和已经过
        # 白名单校验的子结论，不能复用任意上游自由文本。
        conclusion = compliant_customer_finding(
            rule_id=rule_id,
            criterion_results=criterion_results,
        )
    suggestion = _explicit_customer_text(
        raw,
        (
            "suggestion",
            "customer_suggestion",
            "customer_recommendation",
            "customer_action",
        )
        if reuse_saved_customer_text
        else (),
        generic_suggestion,
    )
    rule_name = _explicit_customer_text(
        raw,
        ("customer_rule_name", "rule_name"),
        rule_id,
    )
    projected = {
        "schema_version": _CUSTOMER_RESULT_SCHEMA,
        "record_ref": record_ref,
        "rule_id": rule_id,
        "rule_code": rule_id,
        "qc_point_id": rule_id,
        "rule_name": rule_name,
        "status": status,
        "result_status": status,
        "display_status": status,
        "is_compliant": True if status == "compliant" else False if status == "non_compliant" else None,
        "is_confirmed_issue": status == "non_compliant",
        "reason_code": (
            "customer_explanation_incomplete"
            if explanation_incomplete
            else _canonical_reason_code(raw)
        ),
        "rule_version": _safe_text(raw.get("rule_version")),
        "conclusion": conclusion,
        "findings": conclusion,
        "customer_conclusion": conclusion,
        "suggestion": suggestion,
        "customer_suggestion": suggestion,
        "evidence": _safe_evidence_rows(raw, hmac_key=hmac_key),
    }
    if customer_display_facts:
        projected["customer_display_facts"] = customer_display_facts
    if criterion_results:
        projected["criterion_results"] = criterion_results
    model_analysis = _single_record_model_analysis(raw)
    if model_analysis:
        projected["model_analysis"] = model_analysis
    return projected


def _is_current_rule_contract_result(item: Dict[str, Any]) -> bool:
    """带结构化 criteria 的规则只展示当前规则版本，旧结果需重新质控。"""

    rule_id = _safe_text(
        item.get("customer_rule_id")
        or item.get("qc_point_id")
        or item.get("rule_id")
        or item.get("rule_code")
    ).upper()
    rule = get_luxian_0609_rule(rule_id)
    if not rule or not isinstance(rule.get("criteria"), list):
        return True
    current_version = _safe_text(rule.get("rule_version"))
    return bool(current_version) and _safe_text(item.get("rule_version")) == current_version


def iter_unique_customer_result_source_items(
    job: Dict[str, Any],
    *,
    hmac_key: str,
) -> List[Dict[str, Any]]:
    """按统一优先级返回供 API、复核和导出共用的去重原始行集。"""

    children = [
        child
        for child in list(job.get("child_jobs") or job.get("children") or [])
        if isinstance(child, dict)
    ]
    sources = children or [job]
    raw_items: List[Dict[str, Any]] = []
    for source in sources:
        raw_items.extend(item for item in list(source.get("items") or []) if isinstance(item, dict))
    if not raw_items:
        summary = job.get("summary") if isinstance(job.get("summary"), dict) else {}
        for rule_result in list(summary.get("rule_results") or job.get("rule_results") or []):
            if isinstance(rule_result, dict):
                raw_items.extend(
                    item for item in list(rule_result.get("items") or []) if isinstance(item, dict)
                )
    # 同一父任务的分族子任务、重试残留或兼容路径都可能带来同一
    # record_ref + rule_id 的多条结果。客户结果必须是“一病历一规则一结论”，
    # 不能因为状态或原因码不同而把旧、新结论并排展示。
    unique_by_rule: Dict[tuple[str, str], tuple[tuple[int, int], Dict[str, Any]]] = {}
    for index, item in enumerate(raw_items):
        if not _is_current_rule_contract_result(item):
            continue
        projected = project_customer_safe_result_item(item, hmac_key=hmac_key)
        identity = (
            _safe_text(projected.get("record_ref")),
            _safe_text(projected.get("rule_id")),
        )
        # 规则专属事实/子结论比空泛历史状态更有权威性；在解释能力相同的
        # 情况下，保留输入序列中较后的候选，以适配同一任务内重跑后的追加结果。
        authority = (
            int(bool(projected.get("customer_display_facts") or projected.get("criterion_results"))),
            index,
        )
        current = unique_by_rule.get(identity)
        if current is None or authority > current[0]:
            unique_by_rule[identity] = (authority, item)
    return [item for _, item in unique_by_rule.values()]


def flatten_customer_safe_result_items(
    job: Dict[str, Any],
    *,
    hmac_key: str,
) -> List[Dict[str, Any]]:
    """按内部结果原顺序生成供 API、复核和全部导出共用的唯一行集。"""

    return [
        project_customer_safe_result_item(item, hmac_key=hmac_key)
        for item in iter_unique_customer_result_source_items(job, hmac_key=hmac_key)
    ]


def _safe_operational_progress(value: Any) -> Dict[str, Any]:
    if not isinstance(value, dict):
        return {}
    allowed = {
        "step_key",
        "step_label",
        "progress_percent",
        "processed_records",
        "total_records",
        "max_parallel_records",
        "active_record_count",
        "queued_record_count",
        "rule_count",
        "completed",
        "total",
        "remaining",
    }
    projected = {
        key: value.get(key)
        for key in allowed
        if isinstance(value.get(key), (str, int, float, bool)) and value.get(key) is not None
    }
    processed_rule_count = value.get("processed_rule_count")
    if processed_rule_count is None:
        processed_rule_count = value.get("rule_index")
    if isinstance(processed_rule_count, (str, int, float)) and not isinstance(
        processed_rule_count, bool
    ):
        projected["processed_rule_count"] = processed_rule_count
    return projected


def _safe_review_report(value: Any, *, hmac_key: str) -> Optional[Dict[str, Any]]:
    if not isinstance(value, dict):
        return None
    findings: List[Dict[str, Any]] = []
    for raw_finding in list(value.get("findings") or []):
        if not isinstance(raw_finding, dict):
            continue
        projected = project_customer_safe_result_item(
            {
                **raw_finding,
                "result_status": raw_finding.get("original_status")
                or raw_finding.get("canonical_status")
                or raw_finding.get("status"),
                "reason_code": raw_finding.get("original_reason_code")
                or raw_finding.get("reason_code"),
            },
            hmac_key=hmac_key,
        )
        existing_ref = _safe_text(raw_finding.get("record_ref"))
        if re.fullmatch(r"rec_[0-9a-f]{24}", existing_ref):
            projected["record_ref"] = existing_ref
        severity = _safe_text(raw_finding.get("severity")).upper()
        risk_type = _safe_text(raw_finding.get("risk_type")).lower()
        suggested = _canonical_customer_status(
            {"status": raw_finding.get("suggested_status")}
        )
        findings.append(
            {
                "finding_ref": _keyed_ref(
                    "finding",
                    raw_finding.get("finding_key")
                    or f"{projected['record_ref']}:{projected['rule_id']}:{risk_type}",
                    hmac_key=hmac_key,
                ),
                "record_ref": projected["record_ref"],
                "rule_id": projected["rule_id"],
                "rule_name": projected["rule_name"],
                "canonical_status": projected["status"],
                "reason_code": projected["reason_code"],
                "suggested_status": suggested,
                "severity": severity if severity in {"P0", "P1", "P2"} else "P2",
                "risk_type": (
                    risk_type
                    if _REASON_CODE_PATTERN.fullmatch(risk_type)
                    else "review_finding"
                ),
                "customer_message": _GENERIC_CUSTOMER_TEXT[suggested][0],
                "requires_human_review": bool(
                    raw_finding.get("requires_human_review", True)
                ),
            }
        )
    summary = {"total_findings": len(findings), "p0": 0, "p1": 0, "p2": 0}
    for finding in findings:
        summary[finding["severity"].lower()] += 1
    return {
        "review_status": _safe_text(value.get("review_status"), "completed"),
        "reviewed_at": _safe_text(value.get("reviewed_at")),
        "scope": _safe_text(value.get("scope")),
        "summary": summary,
        "findings": findings,
        "llm_review_status": _safe_text(value.get("llm_review_status"), "skipped"),
    }


def project_customer_safe_batch_job(
    job: Dict[str, Any],
    *,
    hmac_key: str,
) -> Dict[str, Any]:
    """生成 API/复核共用的客户任务 DTO，不回传原始 filters/summary 技术对象。"""

    items = flatten_customer_safe_result_items(job, hmac_key=hmac_key)
    status_counts: Dict[str, int] = {}
    for item in items:
        status = _safe_text(item.get("status"), "uncertain")
        status_counts[status] = status_counts.get(status, 0) + 1
    issue_refs = {
        _safe_text(item.get("record_ref"))
        for item in items
        if item.get("is_confirmed_issue") is True
    }
    raw_summary = job.get("summary") if isinstance(job.get("summary"), dict) else {}
    filters = job.get("filters") if isinstance(job.get("filters"), dict) else {}
    progress = _safe_operational_progress(
        raw_summary.get("progress") or job.get("progress")
    )
    review_report = _safe_review_report(
        raw_summary.get("review_report"),
        hmac_key=hmac_key,
    )
    safe_summary: Dict[str, Any] = {
        "total_records": _to_int(raw_summary.get("total_records"), _to_int(job.get("total_records"))),
        "success_count": _to_int(raw_summary.get("success_count"), _to_int(job.get("success_count"))),
        "failed_count": _to_int(raw_summary.get("failed_count"), _to_int(job.get("failed_count"))),
        "compliant_records": len(
            {
                _safe_text(item.get("record_ref"))
                for item in items
                if item.get("status") == "compliant"
            }
        ),
        "result_count": len(items),
        "issue_records": len(issue_refs),
        "status_counts": status_counts,
        "status_breakdown": status_counts,
        "display_status_counts": status_counts,
        "uncertain_records": len(
            {
                _safe_text(item.get("record_ref"))
                for item in items
                if item.get("status")
                in {"ai_suggested_non_compliant", "ai_suggested_compliant", "uncertain"}
            }
        ),
        "progress": progress,
        "progress_percent": progress.get("progress_percent", 0),
        "rule_count": _to_int(raw_summary.get("rule_count"), _to_int(job.get("rule_count"))),
        "customer_rule_count": _to_int(
            raw_summary.get("customer_rule_count")
            or filters.get("customer_rule_count")
            or job.get("customer_rule_count")
        ),
        "execution_rule_count": _to_int(
            raw_summary.get("execution_rule_count")
            or filters.get("execution_rule_count")
            or job.get("execution_rule_count")
        ),
        "processed_rule_count": _to_int(
            progress.get("processed_rule_count"),
            _to_int(raw_summary.get("processed_rule_count")),
        ),
        "retryable_rule_count": _to_int(raw_summary.get("retryable_rule_count")),
        "total_tokens": _to_int(raw_summary.get("total_tokens"), _to_int(job.get("total_tokens"))),
        "total_processing_time": _to_float(
            raw_summary.get("total_processing_time"),
            _to_float(job.get("total_processing_time")),
        ),
        "wall_clock_time": _to_float(
            raw_summary.get("wall_clock_time"),
            _to_float(job.get("wall_clock_time")),
        ),
        "history_issue_summaries": [
            {
                "rule_id": _safe_text(item.get("rule_id")),
                "status": _safe_text(item.get("status")),
                "text": _safe_text(item.get("conclusion")),
            }
            for item in items
            if item.get("status") == "non_compliant"
        ][:6],
    }
    raw_profile = (
        raw_summary.get("performance_profile")
        if isinstance(raw_summary.get("performance_profile"), dict)
        else {}
    )
    numeric_profile_keys = (
        "tokens_total",
        "prompt_tokens",
        "completion_tokens",
        "unattributed_tokens",
        "wall_clock_time_seconds",
        "total_processing_time_seconds",
        "llm_call_count",
        "program_call_count",
        "actual_llm_pack_call_count",
        "retry_count",
        "latency_p50_ms",
        "latency_p95_ms",
        "processing_p50_ms",
        "processing_p95_ms",
    )
    safe_performance_profile = {
        key: _to_float(raw_profile.get(key))
        if key.endswith(("_seconds", "_ms"))
        else _to_int(raw_profile.get(key))
        for key in numeric_profile_keys
        if raw_profile.get(key) is not None
    }
    if isinstance(raw_profile.get("token_breakdown_complete"), bool):
        safe_performance_profile["token_breakdown_complete"] = raw_profile[
            "token_breakdown_complete"
        ]
    safe_summary["performance_profile"] = safe_performance_profile
    safe_summary["total_tokens"] = _to_int(
        safe_performance_profile.get("tokens_total"),
        safe_summary["total_tokens"],
    )
    safe_summary["prompt_tokens"] = _to_int(
        safe_performance_profile.get("prompt_tokens"),
        _to_int(raw_summary.get("prompt_tokens")),
    )
    safe_summary["completion_tokens"] = _to_int(
        safe_performance_profile.get("completion_tokens"),
        _to_int(raw_summary.get("completion_tokens")),
    )
    safe_summary["unattributed_tokens"] = _to_int(
        safe_performance_profile.get("unattributed_tokens"),
        _to_int(raw_summary.get("unattributed_tokens")),
    )
    safe_summary["llm_call_count"] = _to_int(
        safe_performance_profile.get("llm_call_count"),
        _to_int(raw_summary.get("llm_call_count")),
    )
    safe_summary["retry_count"] = _to_int(
        safe_performance_profile.get("retry_count"),
        _to_int(raw_summary.get("retry_count")),
    )
    if review_report:
        safe_summary["review_report"] = review_report
    safe_rule_results: List[Dict[str, Any]] = []
    for raw_rule in list(job.get("rule_results") or []):
        if not isinstance(raw_rule, dict):
            continue
        raw_rule_items = [
            project_customer_safe_result_item(item, hmac_key=hmac_key)
            for item in list(raw_rule.get("items") or [])
            if isinstance(item, dict) and _is_current_rule_contract_result(item)
        ]
        safe_rule_results.append(
            {
                "id": _safe_text(raw_rule.get("id")),
                "job_id": _safe_text(raw_rule.get("job_id")),
                "rule_code": _safe_text(raw_rule.get("rule_code")).upper(),
                "rule_name": _safe_text(raw_rule.get("rule_name")),
                "status": _safe_text(raw_rule.get("status")).lower(),
                "progress": _safe_operational_progress(raw_rule.get("progress")),
                "items": raw_rule_items,
                "total_records": _to_int(raw_rule.get("total_records")),
                "success_count": _to_int(raw_rule.get("success_count")),
                "failed_count": _to_int(raw_rule.get("failed_count")),
                "issue_records": len(
                    {
                        _safe_text(item.get("record_ref"))
                        for item in raw_rule_items
                        if item.get("is_confirmed_issue") is True
                    }
                ),
            }
        )
    safe_children = [
        project_customer_safe_batch_job(child, hmac_key=hmac_key)
        for child in list(job.get("child_jobs") or job.get("children") or [])
        if isinstance(child, dict)
    ]
    failed_records = [
        {
            "record_ref": project_customer_safe_result_item(
                {
                    **item,
                    "status": "technical_error",
                    "reason_code": "record_execution_failed",
                },
                hmac_key=hmac_key,
            )["record_ref"],
            "status": "technical_error",
            "reason_code": "record_execution_failed",
        }
        for item in list(job.get("failed_records") or [])
        if isinstance(item, dict)
    ]
    item_record_refs = {
        _safe_text(item.get("record_ref"))
        for item in items
        if _safe_text(item.get("record_ref"))
    }
    safe_record_focus = (
        {"record_ref": next(iter(item_record_refs))}
        if len(item_record_refs) == 1
        else None
    )
    execution_scope_hash = _safe_text(filters.get("execution_scope_hash")).lower()
    if not re.fullmatch(r"[0-9a-f]{64}", execution_scope_hash):
        execution_scope_hash = ""
    return {
        "schema_version": "customer-qc-job-v1",
        "id": _safe_text(job.get("id")),
        "job_id": _safe_text(job.get("id")),
        "operation_ref": _keyed_ref("op", job.get("id"), hmac_key=hmac_key),
        "execution_scope_hash": execution_scope_hash,
        "deduplicated": bool(filters.get("deduplicated") or job.get("idempotency_reused")),
        "status": _safe_text(job.get("status")).lower(),
        "draft_id": _safe_text(job.get("draft_id")),
        "job_kind": _safe_text(job.get("job_kind")),
        "parent_job_id": _safe_text(job.get("parent_job_id")),
        "child_job_ids": [
            _safe_text(value)
            for value in list(job.get("child_job_ids") or [])
            if _safe_text(value)
        ],
        "rule_code": _safe_text(job.get("rule_code")).upper(),
        "rule_name": _safe_text(job.get("rule_name")),
        "scene": _safe_text(job.get("scene")),
        "scope": _safe_text(job.get("scope")),
        "execution_mode": _safe_text(job.get("execution_mode"), "batch"),
        "progress": progress,
        "created_at": _safe_text(job.get("created_at")),
        "started_at": _safe_text(job.get("started_at")),
        "finished_at": _safe_text(job.get("finished_at")),
        "updated_at": _safe_text(job.get("updated_at")),
        "total_records": safe_summary["total_records"],
        "success_count": safe_summary["success_count"],
        "failed_count": safe_summary["failed_count"],
        "issue_records": safe_summary["issue_records"],
        "compliant_records": safe_summary["compliant_records"],
        "rule_count": safe_summary["rule_count"],
        "customer_rule_count": safe_summary["customer_rule_count"],
        "execution_rule_count": safe_summary["execution_rule_count"],
        "total_tokens": safe_summary["total_tokens"],
        "prompt_tokens": safe_summary["prompt_tokens"],
        "completion_tokens": safe_summary["completion_tokens"],
        "unattributed_tokens": safe_summary["unattributed_tokens"],
        "llm_call_count": safe_summary["llm_call_count"],
        "retry_count": safe_summary["retry_count"],
        "total_processing_time": safe_summary["total_processing_time"],
        "wall_clock_time": safe_summary["wall_clock_time"],
        "rule_set_key": _safe_text(
            filters.get("rule_set_key")
            or filters.get("rule_set_id")
            or job.get("rule_set_key")
            or job.get("rule_set_id")
            or raw_summary.get("rule_set_key")
            or raw_summary.get("rule_set_id")
        ),
        "rule_set_name": _safe_text(
            filters.get("rule_set_name") or raw_summary.get("rule_set_name")
        ),
        "rule_set_version": _safe_text(
            filters.get("rule_set_version") or raw_summary.get("rule_set_version")
        ),
        "draft_ids": [
            _safe_text(value)
            for value in list(
                filters.get("selected_rule_ids")
                or filters.get("rule_ids")
                or job.get("draft_ids")
                or []
            )
            if _safe_text(value)
        ],
        "summary": safe_summary,
        "items": items,
        "failed_records": failed_records,
        "rule_results": safe_rule_results,
        "child_jobs": safe_children,
        "children": safe_children,
        "record_focus": safe_record_focus,
    }


def _is_luxian_0609_export_job(job: Dict[str, Any]) -> bool:
    filters = job.get("filters") if isinstance(job.get("filters"), dict) else {}
    summary = job.get("summary") if isinstance(job.get("summary"), dict) else {}
    return "luxian_0609_qc_v1" in {
        _safe_text(filters.get("rule_set_key")),
        _safe_text(filters.get("rule_set_id")),
        _safe_text(summary.get("rule_set_key")),
        _safe_text(summary.get("rule_set_id")),
        _safe_text(job.get("rule_set_key")),
        _safe_text(job.get("rule_set_id")),
        _safe_text(job.get("rule_code")),
    }


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        if value is None or value == "":
            return default
        return int(float(value))
    except Exception:
        return default


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None or value == "":
            return default
        return float(value)
    except Exception:
        return default


def _as_date(value: Optional[str]) -> Optional[date]:
    if not value:
        return None
    text = value.strip()
    if not text:
        return None
    try:
        return datetime.strptime(text[:10], "%Y-%m-%d").date()
    except Exception:
        return None


def _to_iso_date(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    return str(value)[:10]


def _to_iso_datetime(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, datetime):
        return value.isoformat(sep=" ", timespec="seconds")
    return str(value).strip()


def _draft_schema() -> Optional[str]:
    return "qc" if DB_SCHEMA_MODE == "split" else None


def _value_for_column(column: Any, value: Any) -> Any:
    if value is None:
        return None
    col_type_name = column.type.__class__.__name__.lower()
    if isinstance(value, (dict, list)):
        if "json" in col_type_name:
            return value
        return _safe_json_dumps(value)
    return value


def _map_severity_to_defect_level(severity: Optional[str]) -> str:
    return SEVERITY_TO_DEFECT_LEVEL.get(_safe_text(severity).lower(), DEFAULT_DEFECT_LEVEL)


def _map_defect_level_to_severity(defect_level: Optional[str]) -> str:
    return DEFECT_LEVEL_TO_SEVERITY.get(_safe_text(defect_level), "major")


def _normalize_scope(scope: Optional[str]) -> str:
    normalized = _safe_text(scope, "all").lower()
    if normalized not in {"all", "running", "final"}:
        return "all"
    return normalized


def _normalize_date_field(date_field: Optional[str]) -> str:
    normalized = _safe_text(date_field, "admission").lower()
    if normalized not in {"visit", "admission", "discharge"}:
        return "admission"
    return normalized


def _date_range_condition(column: Any, start: Optional[date], end: Optional[date]):
    conditions = []
    date_column = func.date(column)
    if start:
        conditions.append(date_column >= start)
    if end:
        conditions.append(date_column <= end)
    return and_(*conditions) if conditions else None


def _record_date_range_condition(
    *,
    date_field: str,
    admission_column: Any,
    discharge_column: Any,
    start: Optional[date],
    end: Optional[date],
):
    if not start and not end:
        return None
    if date_field == "visit":
        return or_(
            _date_range_condition(admission_column, start, end),
            _date_range_condition(discharge_column, start, end),
        )
    return _date_range_condition(
        admission_column if date_field == "admission" else discharge_column,
        start,
        end,
    )


def _record_dates_match_range(
    *,
    date_field: str,
    admission_datetime: Any,
    discharge_datetime: Any,
    start: Optional[date],
    end: Optional[date],
) -> bool:
    if not start and not end:
        return True
    candidates = (
        (admission_datetime, discharge_datetime)
        if date_field == "visit"
        else (admission_datetime,)
        if date_field == "admission"
        else (discharge_datetime,)
    )
    for value in candidates:
        candidate = _as_date(_to_iso_date(value))
        if candidate is None:
            continue
        if start and candidate < start:
            continue
        if end and candidate > end:
            continue
        return True
    return False


def _normalize_execution_mode(execution_mode: Optional[str]) -> str:
    value = _safe_text(execution_mode, "single").lower()
    return "multi" if value == "multi" else "single"


def _normalize_run_mode(run_mode: Optional[str]) -> str:
    value = _safe_text(run_mode, "serial").lower()
    return "serial" if value != "parallel" else "parallel"


def _normalize_string_list(values: Any) -> List[str]:
    if not isinstance(values, list):
        return []
    normalized: List[str] = []
    for item in values:
        text = _safe_text(item)
        if text:
            normalized.append(text)
    return normalized


@lru_cache(maxsize=1)
def _drafts_table() -> Table:
    if engine is None:
        raise RuntimeError("DATABASE_URL is not configured; custom qc workspace unavailable")
    metadata = MetaData()
    schema = _draft_schema()
    table = Table(
        "custom_qc_rule_drafts",
        metadata,
        # 主键与核心字段
        # schema 在 split 模式下写入 qc
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("rule_code", sa.String(32), nullable=False, unique=True, index=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("description", sa.Text, nullable=False),
        sa.Column("source_requirement", sa.Text, nullable=False),
        sa.Column("prompt_template", sa.Text, nullable=False),
        sa.Column("document_type", sa.String(64), nullable=False),
        sa.Column("applicable_documents", sa.Text, nullable=False),
        sa.Column("severity", sa.String(20), nullable=False, default="major"),
        sa.Column("defect_level", sa.String(32), nullable=False, default=DEFAULT_DEFECT_LEVEL),
        sa.Column("complexity", sa.String(32), nullable=False, default=DEFAULT_COMPLEXITY),
        sa.Column("scene", sa.String(20), nullable=False, default="running"),
        sa.Column("generation_mode", sa.String(32), nullable=False, default="fallback_template"),
        sa.Column("examples", sa.Text, nullable=False, default="[]"),
        sa.Column("check_logic", sa.Text, nullable=False, default="{}"),
        sa.Column("last_test_summary", sa.Text),
        sa.Column("status", sa.String(20), nullable=False, default="draft"),
        sa.Column("published_rule_id", sa.String(64)),
        sa.Column("created_by", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime, nullable=False),
        sa.Column("updated_at", sa.DateTime, nullable=False),
        schema=schema,
    )
    metadata.create_all(bind=engine, checkfirst=True)
    return table


@lru_cache(maxsize=1)
def _batch_jobs_table() -> Table:
    if engine is None:
        raise RuntimeError("DATABASE_URL is not configured; custom qc workspace unavailable")
    metadata = MetaData()
    schema = _draft_schema()
    table = Table(
        "custom_qc_batch_jobs",
        metadata,
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("draft_id", sa.String(36), nullable=False, index=True),
        sa.Column("rule_code", sa.String(32), nullable=False, index=True),
        sa.Column("rule_name", sa.String(200), nullable=False),
        sa.Column("scene", sa.String(20), nullable=False, default="final"),
        sa.Column("scope", sa.String(20), nullable=False, default="final"),
        sa.Column("status", sa.String(20), nullable=False, default="queued"),
        sa.Column("filters_json", sa.Text, nullable=False, default="{}"),
        sa.Column("record_ids_json", sa.Text, nullable=False, default="[]"),
        sa.Column("summary_json", sa.Text),
        sa.Column("items_json", sa.Text),
        sa.Column("failed_records_json", sa.Text),
        sa.Column("error_message", sa.Text),
        sa.Column("created_by", sa.String(64), nullable=False, index=True),
        sa.Column("created_at", sa.DateTime, nullable=False),
        sa.Column("started_at", sa.DateTime),
        sa.Column("finished_at", sa.DateTime),
        sa.Column("updated_at", sa.DateTime, nullable=False),
        sa.Column("total_records", sa.Integer, nullable=False, default=0),
        sa.Column("success_count", sa.Integer, nullable=False, default=0),
        sa.Column("failed_count", sa.Integer, nullable=False, default=0),
        sa.Column("issue_records", sa.Integer, nullable=False, default=0),
        sa.Column("compliant_records", sa.Integer, nullable=False, default=0),
        sa.Column("total_tokens", sa.Integer, nullable=False, default=0),
        sa.Column("total_processing_time", sa.Float, nullable=False, default=0.0),
        sa.Column("job_kind", sa.String(20), nullable=False, default="leaf"),
        sa.Column("parent_job_id", sa.String(36), index=True),
        sa.Column("child_job_ids_json", sa.Text),
        sa.Column("child_summary_json", sa.Text),
        sa.Column("family_key", sa.String(64)),
        sa.Column("family_name", sa.String(64)),
        schema=schema,
    )
    metadata.create_all(bind=engine, checkfirst=True)
    _sync_batch_job_parent_columns(schema=schema)
    return table


@lru_cache(maxsize=1)
def _record_result_envelopes_table() -> Table:
    """单病历结果交付 Envelope 的显式表定义。

    这张表由 Alembic migration 创建，刻意不在运行时 ``create_all``。这样可以
    避免单病历结果交付链再次依赖旧任务表的隐式建表/补列行为。
    """

    metadata = MetaData()
    return Table(
        "luxian_0609_record_result_envelopes",
        metadata,
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("job_id", sa.String(36), nullable=False, index=True),
        sa.Column("root_job_id", sa.String(36), nullable=False, index=True),
        sa.Column("created_by", sa.String(64), nullable=False, index=True),
        sa.Column("record_id", sa.String(128), nullable=False, index=True),
        sa.Column("institute_id", sa.String(128), nullable=False),
        sa.Column("patient_id", sa.String(128), nullable=False),
        sa.Column("visit_id", sa.String(128), nullable=False),
        sa.Column("rule_set_key", sa.String(96), nullable=False),
        sa.Column("rule_set_version", sa.String(96), nullable=False),
        sa.Column("envelope_json", sa.Text, nullable=False),
        sa.Column("result_count", sa.Integer, nullable=False, default=0),
        sa.Column("created_at", sa.DateTime, nullable=False),
        sa.Column("updated_at", sa.DateTime, nullable=False),
        schema=_draft_schema(),
    )


def _sync_batch_job_parent_columns(*, schema: Optional[str]) -> None:
    if engine is None:
        return
    table_prefix = f"{schema}." if schema else ""
    column_sql = {
        "job_kind": "VARCHAR(20) DEFAULT 'leaf'",
        "parent_job_id": "VARCHAR(36)",
        "child_job_ids_json": "TEXT",
        "child_summary_json": "TEXT",
        "family_key": "VARCHAR(64)",
        "family_name": "VARCHAR(64)",
    }
    with engine.begin() as conn:
        for column_name, column_type in column_sql.items():
            conn.execute(
                text(
                    f"ALTER TABLE {table_prefix}custom_qc_batch_jobs "
                    f"ADD COLUMN IF NOT EXISTS {column_name} {column_type}"
                )
            )
        conn.execute(
            text(
                f"CREATE INDEX IF NOT EXISTS idx_custom_qc_batch_jobs_parent_job_id "
                f"ON {table_prefix}custom_qc_batch_jobs(parent_job_id)"
            )
        )


@lru_cache(maxsize=8)
def _autoload_table(table_name: str, schemas: tuple[Optional[str], ...]) -> Table:
    if engine is None:
        raise RuntimeError("DATABASE_URL is not configured; custom qc workspace unavailable")
    metadata = MetaData()
    last_error: Exception | None = None
    for schema in schemas:
        try:
            return Table(table_name, metadata, schema=schema, autoload_with=engine)
        except Exception as exc:
            last_error = exc
    if last_error is not None:
        raise last_error
    raise RuntimeError(f"unable to load table {table_name}")


def _qc_rules_table() -> Table:
    schema_candidates: tuple[Optional[str], ...]
    if DB_SCHEMA_MODE == "split":
        schema_candidates = ("qc", None)
    else:
        schema_candidates = (None, "qc")
    return _autoload_table("qc_rules", schema_candidates)


def _row_to_draft(row: Dict[str, Any]) -> Dict[str, Any]:
    check_logic = _safe_json_loads(row.get("check_logic"), {})
    examples = _safe_json_loads(row.get("examples"), [])
    applicable_documents = _safe_json_loads(row.get("applicable_documents"), [])
    document_type = normalize_document_label(row.get("document_type"), DEFAULT_DOCUMENT_TYPE)
    last_test_summary = _safe_json_loads(row.get("last_test_summary"), None)
    return {
        "id": _safe_text(row.get("id")),
        "rule_code": _safe_text(row.get("rule_code")),
        "name": _safe_text(row.get("name")),
        "description": _safe_text(row.get("description")),
        "source_requirement": _safe_text(row.get("source_requirement")),
        "prompt_template": _safe_text(row.get("prompt_template")),
        "document_type": document_type,
        "applicable_documents": applicable_documents if isinstance(applicable_documents, list) else [],
        "severity": _safe_text(row.get("severity"), "major"),
        "defect_level": _safe_text(row.get("defect_level"), DEFAULT_DEFECT_LEVEL),
        "complexity": _safe_text(row.get("complexity"), DEFAULT_COMPLEXITY),
        "scene": _safe_text(row.get("scene"), "running"),
        "generation_mode": _safe_text(row.get("generation_mode"), "fallback_template"),
        "examples": examples if isinstance(examples, list) else [],
        "check_logic": check_logic if isinstance(check_logic, dict) else {},
        "last_test_summary": last_test_summary,
        "status": _safe_text(row.get("status"), "draft"),
        "published_rule_id": _safe_text(row.get("published_rule_id")),
        "created_by": _safe_text(row.get("created_by")),
        "created_at": row.get("created_at"),
        "updated_at": row.get("updated_at"),
    }


def _row_to_batch_job(row: Dict[str, Any], *, include_items: bool = True) -> Dict[str, Any]:
    filters = _safe_json_loads(row.get("filters_json"), {})
    record_ids = _safe_json_loads(row.get("record_ids_json"), [])
    summary = _safe_json_loads(row.get("summary_json"), None)
    items = _safe_json_loads(row.get("items_json"), []) if include_items else []
    failed_records = _safe_json_loads(row.get("failed_records_json"), []) if include_items else []
    child_job_ids = _safe_json_loads(row.get("child_job_ids_json"), [])
    child_summary = _safe_json_loads(row.get("child_summary_json"), {})
    filters_dict = filters if isinstance(filters, dict) else {}
    summary_dict = summary if isinstance(summary, dict) else None
    draft_ids = _normalize_string_list(filters_dict.get("draft_ids"))
    if not draft_ids:
        draft_id = _safe_text(row.get("draft_id"))
        if draft_id:
            draft_ids = [draft_id]
    execution_mode = _normalize_execution_mode(filters_dict.get("execution_mode"))
    if execution_mode == "single" and len(draft_ids) > 1:
        execution_mode = "multi"
    run_mode = _normalize_run_mode(filters_dict.get("run_mode"))
    progress = {}
    if summary_dict is not None:
        progress_candidate = summary_dict.get("progress")
        if isinstance(progress_candidate, dict):
            progress = progress_candidate
    rule_count = int((summary_dict or {}).get("rule_count") or 0)
    if rule_count <= 0:
        rule_count = max(1, len(draft_ids))
    normalized_items: List[Dict[str, Any]] = []
    if isinstance(items, list):
        for raw_item in items:
            if isinstance(raw_item, dict):
                normalized_items.append(
                    {
                        **raw_item,
                        "rule_code": _safe_text(raw_item.get("rule_code")) or _safe_text(row.get("rule_code")),
                        "rule_name": _safe_text(raw_item.get("rule_name")) or _safe_text(row.get("rule_name")),
                    }
                )
    rule_results: List[Dict[str, Any]] = []
    if summary_dict is not None:
        candidate = summary_dict.get("rule_results")
        if isinstance(candidate, list):
            rule_results = candidate
    status_value = _safe_text(row.get("status"), "queued")
    return {
        "id": _safe_text(row.get("id")),
        "draft_id": _safe_text(row.get("draft_id")),
        "draft_ids": draft_ids,
        "rule_code": _safe_text(row.get("rule_code")),
        "rule_name": _safe_text(row.get("rule_name")),
        "scene": _safe_text(row.get("scene"), "final"),
        "scope": _safe_text(row.get("scope"), "final"),
        "status": status_value,
        "execution_mode": execution_mode,
        "rule_count": int(rule_count),
        "run_mode": run_mode,
        "filters": filters_dict,
        "record_ids": record_ids if isinstance(record_ids, list) else [],
        "record_refs": (
            list(filters_dict.get("record_refs") or [])
            if isinstance(filters_dict.get("record_refs"), list)
            else []
        ),
        "summary": summary_dict,
        "progress": progress,
        "items": normalized_items,
        "failed_records": failed_records if isinstance(failed_records, list) else [],
        "rule_results": rule_results,
        "cancellable": status_value in {"queued", "running"},
        "error_message": _safe_text(row.get("error_message")),
        "created_by": _safe_text(row.get("created_by")),
        "created_at": row.get("created_at"),
        "started_at": row.get("started_at"),
        "finished_at": row.get("finished_at"),
        "updated_at": row.get("updated_at"),
        "total_records": int(row.get("total_records") or 0),
        "success_count": int(row.get("success_count") or 0),
        "failed_count": int(row.get("failed_count") or 0),
        "issue_records": int(row.get("issue_records") or 0),
        "compliant_records": int(row.get("compliant_records") or 0),
        "total_tokens": int(row.get("total_tokens") or 0),
        "total_processing_time": float(row.get("total_processing_time") or 0.0),
        "job_kind": _safe_text(row.get("job_kind"), "leaf") or "leaf",
        "parent_job_id": _safe_text(row.get("parent_job_id")),
        "child_job_ids": child_job_ids if isinstance(child_job_ids, list) else [],
        "child_summary": child_summary if isinstance(child_summary, dict) else {},
        "family_key": _safe_text(row.get("family_key")),
        "family_name": _safe_text(row.get("family_name")),
    }


def _extract_rule_code_number(rule_code: str) -> int:
    match = re.match(r"^LXE-(\d{1,})$", rule_code.strip().upper())
    if not match:
        return 0
    try:
        return int(match.group(1))
    except Exception:
        return 0


def _session() -> Session:
    if SessionLocal is None:
        raise RuntimeError("DATABASE_URL is not configured; custom qc workspace unavailable")
    return SessionLocal()


def _to_int(value: Any, default: int = 0) -> int:
    try:
        if value is None:
            return default
        return int(value)
    except Exception:
        return default


def _to_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None:
            return default
        return float(value)
    except Exception:
        return default


def _normalize_export_performance_profile(summary: Dict[str, Any], job: Dict[str, Any]) -> Dict[str, Any]:
    raw_profile = summary.get("performance_profile") if isinstance(summary.get("performance_profile"), dict) else {}
    tokens_total = _to_int(
        raw_profile.get("tokens_total"),
        _to_int(summary.get("total_tokens"), _to_int(job.get("total_tokens"))),
    )
    prompt_tokens = _to_int(raw_profile.get("prompt_tokens"))
    completion_tokens = _to_int(raw_profile.get("completion_tokens"))
    unattributed_tokens = _to_int(raw_profile.get("unattributed_tokens"))
    if unattributed_tokens <= 0 and tokens_total > 0:
        unattributed_tokens = max(0, tokens_total - prompt_tokens - completion_tokens)
    token_breakdown_complete = raw_profile.get("token_breakdown_complete")
    if token_breakdown_complete is None:
        token_breakdown_complete = unattributed_tokens == 0
    return {
        "tokens_total": tokens_total,
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "unattributed_tokens": unattributed_tokens,
        "token_breakdown_complete": bool(token_breakdown_complete),
        "wall_clock_time_seconds": _to_float(raw_profile.get("wall_clock_time_seconds")),
        "total_processing_time_seconds": _to_float(
            raw_profile.get("total_processing_time_seconds"),
            _to_float(summary.get("total_processing_time"), _to_float(job.get("total_processing_time"))),
        ),
        "llm_call_count": _to_int(raw_profile.get("llm_call_count")),
        "actual_llm_pack_call_count": _to_int(raw_profile.get("actual_llm_pack_call_count")),
    }


def _format_export_integer(value: Any) -> str:
    return f"{_to_int(value):,}"


def _map_scene_label(scene: Any) -> str:
    mapping = {
        "running": "运行病历",
        "final": "终末病历",
        "all": "全病历",
    }
    key = _safe_text(scene).lower()
    return mapping.get(key, _safe_text(scene, "-"))


def _map_scope_label(scope: Any) -> str:
    return _map_scene_label(scope)


def _map_job_status_label(status: Any) -> str:
    mapping = {
        "queued": "排队中",
        "running": "执行中",
        "completed": "已完成",
        "failed": "执行失败",
        "canceled": "已取消",
    }
    key = _safe_text(status).lower()
    return mapping.get(key, _safe_text(status, "-"))


def _map_item_status_label(status: Any, is_compliant: Any) -> str:
    key = _safe_text(status).lower()
    if key == "non_compliant":
        return "不合规"
    if key == "ai_suggested_non_compliant":
        return "AI判断：疑似问题"
    if key == "ai_suggested_compliant":
        return "AI判断：未见问题"
    if key == "data_gap":
        return "数据不足"
    if key == "not_applicable":
        return "不适用"
    if key == "not_executed":
        return "未执行"
    if key == "technical_error":
        return "技术异常"
    if key == "uncertain":
        return "AI判断"
    if key == "compliant":
        return "合规"
    if key == "failed":
        return "失败"
    if is_compliant is True:
        return "合规"
    if is_compliant is False:
        return "不合规"
    return _safe_text(status, "未判定")


def _build_filter_text(filters: Dict[str, Any]) -> str:
    if not isinstance(filters, dict):
        return "未设置筛选条件"
    parts: List[str] = []
    department = _safe_text(filters.get("department"))
    doctor = _safe_text(filters.get("doctor"))
    keyword = _safe_text(filters.get("keyword"))
    start_date = _safe_text(filters.get("start_date"))
    end_date = _safe_text(filters.get("end_date"))
    date_field = _safe_text(filters.get("date_field"))

    if department:
        parts.append(f"科室：{department}")
    if doctor:
        parts.append(f"医生：{doctor}")
    if keyword:
        parts.append(f"关键字：{keyword}")
    if start_date or end_date:
        date_field_zh = {
            "visit": "入出院日期",
            "discharge": "出院日期",
        }.get(date_field, "入院日期")
        parts.append(f"{date_field_zh}：{start_date or '-'} ~ {end_date or '-'}")
    if not parts:
        return "未设置筛选条件"
    return "；".join(parts)


_HTML_EXPORT_SENSITIVE_TOKENS = {
    "prompt",
    "raw_response",
    "embedding",
    "medical_text",
    "record_content",
    "documents",
    "bundle",
    "llm_raw_output",
}

_HTML_EXPORT_INTERNAL_LABELS = (
    "LLM 语义规则",
    "LLM语义规则",
    "证据模板",
    "映射执行规则",
    "来源未标注",
    "raw_response",
    "prompt",
    "embedding",
    "medical_text",
    "record_content",
    "documents",
    "bundle",
    "llm_raw_output",
)


def _html_escape(value: Any) -> str:
    return html.escape(_safe_text(value), quote=True)


def _truncate_export_text(value: Any, limit: int = 360) -> str:
    text_value = re.sub(r"\s+", " ", _safe_text(value)).strip()
    if len(text_value) <= limit:
        return text_value
    return text_value[:limit].rstrip() + "..."


def _sanitize_export_text(value: Any, limit: int = 420) -> str:
    text_value = _safe_text(value)
    if not text_value:
        return ""
    # 旧证据字符串经常把内部模板、规则映射和可读证据拼在一起；导出时只保留客户可理解的证据段。
    for marker in ("执行证据：", "关键证据：", "证据："):
        if marker in text_value:
            text_value = text_value.split(marker, 1)[1]
            break
    text_value = text_value.replace("来源未标注 · evidence：", "")
    parts = re.split(r"[；;\n]+", text_value)
    kept: List[str] = []
    for part in parts:
        normalized = _safe_text(part)
        if not normalized:
            continue
        if any(label in normalized for label in _HTML_EXPORT_INTERNAL_LABELS):
            continue
        kept.append(normalized)
    if kept:
        text_value = "；".join(kept)
    for token in _HTML_EXPORT_SENSITIVE_TOKENS:
        text_value = re.sub(re.escape(token), "", text_value, flags=re.IGNORECASE)
    review_replacements = (
        ("待人工复核", "AI判断后建议确认"),
        ("待人工核对", "AI判断后建议确认"),
        ("建议人工复核", "建议结合原文确认"),
        ("建议人工核对", "建议结合原文确认"),
        ("需人工复核", "需结合原文确认"),
        ("需人工核对", "需结合原文确认"),
        ("需要人工复核", "需要结合原文确认"),
        ("需要人工核对", "需要结合原文确认"),
        ("人工复核", "结合原文确认"),
        ("人工核对", "结合原文确认"),
    )
    for source, target in review_replacements:
        text_value = text_value.replace(source, target)
    return _truncate_export_text(text_value, limit=limit)


def _extract_export_customer_evidence_text(value: Any) -> str:
    raw = _safe_text(value)
    if not raw:
        return ""
    for marker in ("执行证据：", "关键证据：", "证据："):
        if marker in raw:
            raw = raw.split(marker, 1)[1]
            break
    return _sanitize_export_text(raw, limit=720)


def _normalize_export_evidence_label(value: str) -> str:
    label = _safe_text(value)
    label_map = {
        "authored_at": "记录时间",
        "record_time": "记录时间",
        "submit_time": "提交时间",
        "submitted_at": "提交时间",
        "admission_time": "入院时间",
        "discharge_time": "出院时间",
        "deadline": "截止时间",
        "elapsed": "间隔",
        "delta": "差值",
    }
    return label_map.get(label, label)


def _parse_export_evidence_parts(value: Any, *, limit: int = 8) -> List[Dict[str, str]]:
    text_value = _extract_export_customer_evidence_text(value)
    if not text_value:
        return []
    parts: List[Dict[str, str]] = []
    for raw_part in re.split(r"[；;\n]+", text_value):
        raw_part = _safe_text(raw_part)
        if len(raw_part) < 4 or "：" not in raw_part:
            continue
        segments = [segment.strip() for segment in raw_part.split("：") if segment.strip()]
        if len(segments) < 2:
            continue
        first = _normalize_export_evidence_label(segments[0])
        second_is_field = len(segments) >= 3 and re.match(r"^[a-z_]+$", segments[1] or "", flags=re.IGNORECASE)
        label = f"{first} · {_normalize_export_evidence_label(segments[1])}" if second_is_field else first
        value_text = "：".join(segments[2:] if second_is_field else segments[1:]).strip()
        if not label or not value_text:
            continue
        if any(internal in label for internal in _HTML_EXPORT_INTERNAL_LABELS):
            continue
        parts.append({"label": label, "value": _truncate_export_text(value_text, 180)})
        if len(parts) >= limit:
            break
    return parts


def _export_item_status_key(item: Dict[str, Any]) -> str:
    status_key = _safe_text((item or {}).get("status")).lower()
    is_compliant = (item or {}).get("is_compliant")
    if status_key:
        if status_key == "failed":
            return "technical_error"
        return status_key
    if is_compliant is True:
        return "compliant"
    if is_compliant is False:
        return "non_compliant"
    return "uncertain"


def _status_tone_class(status_key: str) -> str:
    if status_key == "non_compliant":
        return "danger"
    if status_key in {
        "ai_suggested_non_compliant",
        "data_gap",
        "uncertain",
        "technical_error",
        "not_executed",
    }:
        return "warning"
    if status_key in {"compliant", "ai_suggested_compliant"}:
        return "success"
    if status_key == "not_applicable":
        return "neutral"
    return "muted"


def _extract_structured_evidence(item: Dict[str, Any]) -> List[Dict[str, str]]:
    evidence_candidates: List[Any] = []
    for key in ("evidence_items", "evidence_chain", "evidence_chains", "evidences", "evidence_details"):
        raw = item.get(key)
        if isinstance(raw, list):
            evidence_candidates.extend(raw)
    rows: List[Dict[str, str]] = []
    for raw in evidence_candidates:
        if not isinstance(raw, dict):
            continue
        quote = _sanitize_export_text(raw.get("quote") or raw.get("text") or raw.get("snippet") or raw.get("value"), 220)
        source = _safe_text(
            raw.get("source_document")
            or raw.get("source_table")
            or raw.get("document_type")
            or raw.get("source")
            or raw.get("source_field")
        )
        field = _safe_text(raw.get("source_field") or raw.get("field"))
        threshold = _safe_text(raw.get("threshold"))
        actual = _safe_text(raw.get("actual_value") or raw.get("actual"))
        delta = _safe_text(raw.get("delta") or raw.get("difference"))
        if not any([quote, source, field, threshold, actual, delta]):
            continue
        rows.append(
            {
                "source": source,
                "field": field,
                "quote": quote,
                "threshold": threshold,
                "actual": actual,
                "delta": delta,
            }
        )
    return rows[:4]


def _format_rule_code_list(values: Any, limit: int = 8) -> str:
    if not isinstance(values, list):
        return "-"
    cleaned = [_safe_text(item) for item in values if _safe_text(item)]
    if not cleaned:
        return "-"
    preview = "、".join(cleaned[:limit])
    if len(cleaned) > limit:
        preview += f" +{len(cleaned) - limit}"
    return preview


_CUSTOMER_EXPORT_HEADERS = [
    "病历引用",
    "质控点编码",
    "质控点名称",
    "判定结果",
    "原因码",
    "质控结论",
    "处理建议",
    "证据引用",
]


def _customer_export_rows(
    job: Dict[str, Any],
    *,
    hmac_key: str,
) -> tuple[List[Dict[str, Any]], List[List[str]], Dict[str, Any]]:
    items = flatten_customer_safe_result_items(job, hmac_key=hmac_key)
    rows: List[List[str]] = []
    for item in items:
        evidence_text = customer_evidence_summary(list(item.get("evidence") or []))
        rows.append(
            [
                _safe_text(item.get("record_ref")),
                _safe_text(item.get("rule_id")),
                _safe_text(item.get("rule_name")),
                _map_item_status_label(item.get("status"), item.get("status") == "compliant"),
                _safe_text(item.get("reason_code")),
                _safe_text(item.get("conclusion")),
                _safe_text(item.get("suggestion")),
                evidence_text,
            ]
        )
    issue_refs = {
        _safe_text(item.get("record_ref"))
        for item in items
        if item.get("is_confirmed_issue") is True
    }
    status_counts: Dict[str, int] = {}
    for item in items:
        status = _safe_text(item.get("status"), "uncertain")
        status_counts[status] = status_counts.get(status, 0) + 1
    return items, rows, {
        "operation_ref": _keyed_ref("op", job.get("id"), hmac_key=hmac_key),
        "record_count": len(
            {
                _safe_text(item.get("record_ref"))
                for item in items
                if _safe_text(item.get("record_ref"))
            }
        ),
        "result_count": len(items),
        "issue_records": len(issue_refs),
        "status_counts": status_counts,
    }


def _export_customer_safe_workbook(job: Dict[str, Any], *, hmac_key: str) -> BytesIO:
    from openpyxl import Workbook

    items, rows, summary = _customer_export_rows(job, hmac_key=hmac_key)
    output = BytesIO()
    workbook = Workbook()
    ws_summary = workbook.active
    ws_summary.title = "管理摘要"
    ws_summary.append(["报告项", "内容"])
    ws_summary.append(["任务引用", summary["operation_ref"]])
    ws_summary.append(["结果总数", summary["result_count"]])
    ws_summary.append(["确定问题病历数", summary["issue_records"]])
    for status, count in summary["status_counts"].items():
        ws_summary.append([f"状态-{status}", count])

    ws_issues = workbook.create_sheet("问题明细")
    ws_issues.append(_CUSTOMER_EXPORT_HEADERS)
    for item, row in zip(items, rows):
        if item.get("is_confirmed_issue") is True:
            ws_issues.append(row)

    ws_all = workbook.create_sheet("全部明细")
    ws_all.append(_CUSTOMER_EXPORT_HEADERS)
    for row in rows:
        ws_all.append(row)
    ws_issues.freeze_panes = "A2"
    ws_all.freeze_panes = "A2"
    workbook.save(output)
    output.seek(0)
    return output


def _export_customer_safe_csv(job: Dict[str, Any], *, hmac_key: str) -> StringIO:
    import csv

    _items, rows, summary = _customer_export_rows(job, hmac_key=hmac_key)
    output = StringIO()
    writer = csv.writer(output)
    writer.writerow(["管理摘要"])
    writer.writerow(["任务引用", summary["operation_ref"]])
    writer.writerow(["结果总数", summary["result_count"]])
    writer.writerow(["确定问题病历数", summary["issue_records"]])
    writer.writerow([])
    writer.writerow(["全部明细"])
    writer.writerow(_CUSTOMER_EXPORT_HEADERS)
    writer.writerows(rows)
    output.seek(0)
    return output


def _export_customer_safe_html(
    job: Dict[str, Any],
    *,
    hmac_key: str,
    canonical_items: Sequence[Dict[str, Any]],
) -> str:
    canonical_job = {"id": job.get("id"), "items": list(canonical_items)}
    items, rows, summary = _customer_export_rows(canonical_job, hmac_key=hmac_key)
    # HTML 是客户报告，不展示内部原因码；CSV/XLSX 的现有结构保持不变。
    html_columns = (0, 1, 2, 3, 5, 6, 7)
    headers = "".join(
        f"<th>{html.escape(_CUSTOMER_EXPORT_HEADERS[index])}</th>"
        for index in html_columns
    )
    groups: Dict[str, Dict[str, Any]] = {}
    for item, row in zip(items, rows):
        record_ref = _safe_text(item.get("record_ref"))
        group = groups.setdefault(record_ref, {"rows": [], "status_counts": {}})
        group["rows"].append(row)
        status = _safe_text(item.get("status"), "uncertain")
        status_counts = group["status_counts"]
        status_counts[status] = status_counts.get(status, 0) + 1

    status_order = (
        "non_compliant",
        "ai_suggested_non_compliant",
        "data_gap",
        "uncertain",
        "ai_suggested_compliant",
        "compliant",
        "not_applicable",
        "not_executed",
        "technical_error",
    )
    record_sections: List[str] = []
    for record_ref, group in groups.items():
        body_rows = "".join(
            "<tr data-result-row>"
            + "".join(
                f"<td>{html.escape(row[index], quote=True)}</td>"
                for index in html_columns
            )
            + "</tr>"
            for row in group["rows"]
        )
        status_badges = "".join(
            '<span class="status-pill">'
            f"{html.escape(_map_item_status_label(status, status == 'compliant'))} "
            f"{group['status_counts'][status]}"
            "</span>"
            for status in status_order
            if group["status_counts"].get(status)
        )
        record_sections.append(
            f"""<section class="record-group" data-record-group>
    <header class="record-heading">
      <div>
        <span class="eyebrow">病历引用</span>
        <h2>{html.escape(record_ref, quote=True)}</h2>
      </div>
      <div class="status-counts">{status_badges}</div>
    </header>
    <div class="table-wrap">
      <table>
        <thead><tr>{headers}</tr></thead>
        <tbody>{body_rows}</tbody>
      </table>
    </div>
  </section>"""
        )
    result_content = "".join(record_sections)
    if not result_content:
        result_content = (
            '<section class="empty-state">'
            "<h2>暂无质控结果</h2>"
            "<p>本次任务没有可导出的质控结果。</p>"
            "</section>"
        )
    document = f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>质控结果</title>
  <style>
    body {{ margin: 0; padding: 24px; background: #f6f8fb; color: #1f2937; font-family: "Microsoft YaHei", sans-serif; }}
    main {{ max-width: 1180px; margin: 0 auto; }}
    section {{ margin-bottom: 18px; border: 1px solid #e5e7eb; border-radius: 14px; background: #fff; padding: 18px; }}
    h1, h2, p {{ margin-top: 0; }}
    h1 {{ margin-bottom: 14px; font-size: 24px; }}
    h2 {{ margin-bottom: 0; font-size: 17px; overflow-wrap: anywhere; }}
    .metrics {{ display: flex; gap: 12px 24px; flex-wrap: wrap; color: #475569; }}
    .record-heading {{ display: flex; align-items: flex-start; justify-content: space-between; gap: 16px; margin-bottom: 14px; }}
    .eyebrow {{ display: block; margin-bottom: 5px; color: #64748b; font-size: 12px; }}
    .status-counts {{ display: flex; justify-content: flex-end; gap: 8px; flex-wrap: wrap; }}
    .status-pill {{ border: 1px solid #dbeafe; border-radius: 999px; background: #eff6ff; color: #1d4ed8; padding: 4px 9px; font-size: 12px; white-space: nowrap; }}
    .table-wrap {{ overflow-x: auto; }}
    table {{ width: 100%; border-collapse: collapse; font-size: 13px; }}
    th, td {{ border-bottom: 1px solid #e5e7eb; padding: 9px; text-align: left; vertical-align: top; }}
    th {{ color: #4b5563; background: #f8fafc; }}
    .empty-state {{ padding: 42px 18px; text-align: center; color: #64748b; }}
    .empty-state h2 {{ margin-bottom: 8px; color: #334155; }}
  </style>
</head>
<body>
<main>
  <section>
    <h1>批量质控结果</h1>
    <div class="metrics">
      <span>任务引用：{html.escape(summary["operation_ref"])}</span>
      <span>病历数：{summary["record_count"]}</span>
      <span>结果总数：{summary["result_count"]}</span>
      <span>确定问题病历数：{summary["issue_records"]}</span>
    </div>
  </section>
  {result_content}
</main>
</body>
</html>"""
    return "\ufeff" + document


@dataclass
class WorkspaceListResult:
    items: List[Dict[str, Any]]
    total: int
    page: int
    page_size: int


@dataclass
class WorkspaceBatchJobListResult:
    items: List[Dict[str, Any]]
    total: int
    page: int
    page_size: int


class CustomQCWorkspaceService:
    def __init__(self) -> None:
        if engine is None:
            raise RuntimeError("DATABASE_URL is not configured; custom qc workspace unavailable")
        self._draft_table = _drafts_table()
        self._batch_job_table = _batch_jobs_table()
        self._record_result_envelope_table = _record_result_envelopes_table()

    @staticmethod
    def _aggregate_child_input_profiles(child_profiles: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
        input_profiles = [
            dict(profile.get("input_profile") or {})
            for profile in child_profiles
            if isinstance(profile.get("input_profile"), dict) and profile.get("input_profile")
        ]
        if not input_profiles:
            return {}

        source_table_counts: Dict[str, int] = {}
        source_table_text_lengths: Dict[str, int] = {}
        available_family_contexts = set()
        family_profiles: Dict[str, Dict[str, Any]] = {}
        for profile in input_profiles:
            for key, value in dict(profile.get("source_table_counts") or {}).items():
                source_table_counts[str(key)] = source_table_counts.get(str(key), 0) + _safe_int(value)
            for key, value in dict(profile.get("source_table_text_lengths") or {}).items():
                source_table_text_lengths[str(key)] = source_table_text_lengths.get(str(key), 0) + _safe_int(value)
            for family in list(profile.get("available_family_contexts") or []):
                if str(family or "").strip():
                    available_family_contexts.add(str(family).strip())
            for family, family_profile in dict(profile.get("family_profiles") or {}).items():
                family_key = str(family or "").strip()
                if not family_key or not isinstance(family_profile, dict):
                    continue
                target = family_profiles.setdefault(
                    family_key,
                    {
                        "family": family_key,
                        "ready_record_count": 0,
                        "document_count": 0,
                        "text_char_count": 0,
                        "present_source_table_count": 0,
                        "missing_source_table_count": 0,
                    },
                )
                for numeric_key in (
                    "ready_record_count",
                    "document_count",
                    "text_char_count",
                    "present_source_table_count",
                    "missing_source_table_count",
                ):
                    target[numeric_key] = _safe_int(target.get(numeric_key)) + _safe_int(
                        family_profile.get(numeric_key)
                    )

        return {
            "schema_version": "luxian_0609_parent_input_perf_summary_v1",
            "basis": "child_job_input_profile_summary",
            "child_input_profile_count": len(input_profiles),
            "record_count_sum": sum(_safe_int(profile.get("record_count")) for profile in input_profiles),
            "document_count_sum": sum(_safe_int(profile.get("document_count")) for profile in input_profiles),
            "primary_text_char_count_sum": sum(
                _safe_int(profile.get("primary_text_char_count")) for profile in input_profiles
            ),
            "medical_text_char_count_sum": sum(
                _safe_int(profile.get("medical_text_char_count")) for profile in input_profiles
            ),
            "source_table_counts": dict(sorted(source_table_counts.items())),
            "source_table_text_lengths": dict(sorted(source_table_text_lengths.items())),
            "available_family_contexts": sorted(available_family_contexts),
            "family_profiles": dict(sorted(family_profiles.items())),
        }

    @staticmethod
    def _aggregate_child_performance_profiles(child_jobs: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
        child_profiles = [
            dict((child.get("summary") or {}).get("performance_profile") or {})
            for child in child_jobs
            if isinstance((child.get("summary") or {}).get("performance_profile"), dict)
        ]
        child_profiles = [profile for profile in child_profiles if profile]
        if not child_profiles:
            return {}

        status_breakdown: Dict[str, int] = {}
        for child in child_jobs:
            for key, value in dict((child.get("summary") or {}).get("status_breakdown") or {}).items():
                status_breakdown[str(key)] = status_breakdown.get(str(key), 0) + _safe_int(value)

        profile = {
            "schema_version": "luxian_0609_parent_job_perf_v1",
            "basis": "child_job_performance_profiles",
            "child_job_count": len(child_jobs),
            "profiled_child_job_count": len(child_profiles),
            "total_records": sum(_safe_int(profile.get("total_records")) for profile in child_profiles),
            "customer_rule_count": sum(_safe_int(profile.get("customer_rule_count")) for profile in child_profiles),
            "execution_rule_count": sum(_safe_int(profile.get("execution_rule_count")) for profile in child_profiles),
            "result_count": sum(_safe_int(profile.get("result_count")) for profile in child_profiles),
            "wall_clock_time_seconds": sum(
                _safe_float(profile.get("wall_clock_time_seconds")) for profile in child_profiles
            ),
            "sum_rule_duration_seconds": sum(
                _safe_float(profile.get("sum_rule_duration_seconds")) for profile in child_profiles
            ),
            "llm_call_count": sum(_safe_int(profile.get("llm_call_count")) for profile in child_profiles),
            "program_call_count": sum(_safe_int(profile.get("program_call_count")) for profile in child_profiles),
            "actual_llm_pack_call_count": sum(
                _safe_int(profile.get("actual_llm_pack_call_count")) for profile in child_profiles
            ),
            "retry_count": sum(_safe_int(profile.get("retry_count")) for profile in child_profiles),
            "provider_error_count": sum(_safe_int(profile.get("provider_error_count")) for profile in child_profiles),
            "timeout_count": sum(_safe_int(profile.get("timeout_count")) for profile in child_profiles),
            "rate_limit_count": sum(_safe_int(profile.get("rate_limit_count")) for profile in child_profiles),
            "pack_retry_attempts": sum(_safe_int(profile.get("pack_retry_attempts")) for profile in child_profiles),
            "tokens_total": sum(_safe_int(profile.get("tokens_total")) for profile in child_profiles),
            "prompt_tokens": sum(_safe_int(profile.get("prompt_tokens")) for profile in child_profiles),
            "completion_tokens": sum(_safe_int(profile.get("completion_tokens")) for profile in child_profiles),
            "unattributed_tokens": sum(
                _safe_int(
                    profile.get("unattributed_tokens"),
                    max(
                        0,
                        _safe_int(profile.get("tokens_total"))
                        - _safe_int(profile.get("prompt_tokens"))
                        - _safe_int(profile.get("completion_tokens")),
                    ),
                )
                for profile in child_profiles
            ),
            "context_tokens_estimate": sum(
                _safe_int(profile.get("context_tokens_estimate")) for profile in child_profiles
            ),
            "status_breakdown": dict(sorted(status_breakdown.items())),
            "children": [
                {
                    "job_id": str(child.get("id") or ""),
                    "status": str(child.get("status") or ""),
                    "rule_family": str((child.get("filters") or {}).get("luxian_rule_family") or ""),
                    "performance_profile": dict((child.get("summary") or {}).get("performance_profile") or {}),
                }
                for child in child_jobs
            ],
            "input_profile": CustomQCWorkspaceService._aggregate_child_input_profiles(child_profiles),
        }
        profile["token_breakdown_complete"] = _safe_int(profile.get("unattributed_tokens")) == 0
        return profile

    def _aggregate_parent_job(
        self,
        session: Session,
        parent_job: Dict[str, Any],
        *,
        include_items: bool = True,
    ) -> Dict[str, Any]:
        if str(parent_job.get("job_kind") or "").strip().lower() != "parent":
            return parent_job
        child_job_ids = [
            str(item or "").strip()
            for item in list(parent_job.get("child_job_ids") or [])
            if str(item or "").strip()
        ]
        if child_job_ids:
            child_rows = (
                session.execute(
                    select(self._batch_job_table)
                    .where(self._batch_job_table.c.id.in_(child_job_ids))
                    .order_by(asc(self._batch_job_table.c.created_at))
                )
                .mappings()
                .all()
            )
        else:
            child_rows = (
                session.execute(
                    select(self._batch_job_table)
                    .where(self._batch_job_table.c.parent_job_id == parent_job.get("id"))
                    .order_by(asc(self._batch_job_table.c.created_at))
                )
                .mappings()
                .all()
            )
        child_jobs = [_row_to_batch_job(dict(row), include_items=include_items) for row in child_rows]
        if not child_jobs:
            return parent_job

        statuses = [str(item.get("status") or "queued").strip().lower() for item in child_jobs]
        completed = sum(1 for item in statuses if item == "completed")
        failed = sum(1 for item in statuses if item == "failed")
        canceled = sum(1 for item in statuses if item == "canceled")
        running = sum(1 for item in statuses if item == "running")
        queued = sum(1 for item in statuses if item == "queued")
        if running or queued:
            aggregate_status = "running" if running else "queued"
        elif failed:
            aggregate_status = "failed"
        elif canceled == len(child_jobs):
            aggregate_status = "canceled"
        else:
            aggregate_status = "completed"

        status_breakdown: Dict[str, int] = {}
        total_tokens = 0
        total_processing_time = 0.0
        issue_records = 0
        compliant_records = 0
        failed_count = 0
        success_count = 0
        for child in child_jobs:
            child_summary = child.get("summary") or {}
            for key, value in dict(child_summary.get("status_breakdown") or {}).items():
                status_breakdown[str(key)] = status_breakdown.get(str(key), 0) + int(value or 0)
            total_tokens += int(child.get("total_tokens") or child_summary.get("total_tokens") or 0)
            total_processing_time += float(child.get("total_processing_time") or child_summary.get("total_processing_time") or 0.0)
            issue_records += int(child.get("issue_records") or child_summary.get("issue_records") or 0)
            compliant_records += int(child.get("compliant_records") or child_summary.get("compliant_records") or 0)
            failed_count += int(child.get("failed_count") or child_summary.get("failed_count") or 0)
            success_count += int(child.get("success_count") or child_summary.get("success_count") or 0)

        parent_summary = dict(parent_job.get("summary") or {})
        parent_performance_profile = self._aggregate_child_performance_profiles(child_jobs)
        parent_summary.update(
            {
                "child_job_count": len(child_jobs),
                "completed_child_count": completed,
                "failed_child_count": failed,
                "canceled_child_count": canceled,
                "running_child_count": running,
                "queued_child_count": queued,
                "status_breakdown": status_breakdown,
                "progress": {
                    **(parent_summary.get("progress") if isinstance(parent_summary.get("progress"), dict) else {}),
                    "step_key": aggregate_status,
                    "processed_records": completed + failed + canceled,
                    "total_records": len(child_jobs),
                    "completed_children": completed,
                    "total_children": len(child_jobs),
                },
            }
        )
        if parent_performance_profile:
            parent_summary["performance_profile"] = parent_performance_profile
        return {
            **parent_job,
            "status": aggregate_status,
            "summary": parent_summary,
            "progress": parent_summary.get("progress") or {},
            "children": child_jobs,
            "child_jobs": child_jobs,
            "cancellable": any(status in {"queued", "running"} for status in statuses),
            "success_count": success_count,
            "failed_count": failed_count,
            "issue_records": issue_records,
            "compliant_records": compliant_records,
            "total_tokens": total_tokens,
            "total_processing_time": total_processing_time,
        }

    def refresh_parent_batch_job(self, *, parent_job_id: Optional[str]) -> None:
        """将规则族子任务的实际状态回写到父任务，供“已完成任务”查询使用。"""
        normalized_parent_id = _safe_text(parent_job_id)
        if not normalized_parent_id:
            return
        session = _session()
        try:
            row = session.execute(
                select(self._batch_job_table).where(self._batch_job_table.c.id == normalized_parent_id)
            ).mappings().first()
            if not row:
                return
            parent_job = _row_to_batch_job(dict(row))
            if str(parent_job.get("job_kind") or "").strip().lower() != "parent":
                return
            aggregate = self._aggregate_parent_job(session, parent_job, include_items=True)
            status = _safe_text(aggregate.get("status"), "queued")
            now = _now_utc()
            values: Dict[str, Any] = {
                "status": status,
                "summary_json": _safe_json_dumps(aggregate.get("summary") or {}),
                "success_count": int(aggregate.get("success_count") or 0),
                "failed_count": int(aggregate.get("failed_count") or 0),
                "issue_records": int(aggregate.get("issue_records") or 0),
                "compliant_records": int(aggregate.get("compliant_records") or 0),
                "total_tokens": int(aggregate.get("total_tokens") or 0),
                "total_processing_time": float(aggregate.get("total_processing_time") or 0.0),
                "updated_at": now,
            }
            if status in {"completed", "failed", "canceled"}:
                values["finished_at"] = now
            session.execute(
                update(self._batch_job_table)
                .where(
                    and_(
                        self._batch_job_table.c.id == normalized_parent_id,
                        self._batch_job_table.c.status != "canceled",
                    )
                )
                .values(**values)
            )
            if status == "completed":
                canonical_items = [
                    item
                    for child in list(aggregate.get("children") or [])
                    if isinstance(child, dict)
                    for item in list(child.get("items") or [])
                    if isinstance(item, dict)
                ]
                self._write_record_result_envelopes(
                    session,
                    job_row=dict(row),
                    items=canonical_items,
                    now=now,
                )
            session.commit()
        finally:
            session.close()

    def _next_rule_code(self, session: Session) -> str:
        max_num = 0
        draft_codes = session.execute(select(self._draft_table.c.rule_code)).scalars().all()
        for code in draft_codes:
            max_num = max(max_num, _extract_rule_code_number(_safe_text(code)))

        try:
            qc_rules_table = _qc_rules_table()
            qc_codes = session.execute(select(qc_rules_table.c.rule_code)).scalars().all()
            for code in qc_codes:
                max_num = max(max_num, _extract_rule_code_number(_safe_text(code)))
        except Exception:
            pass
        return f"LXE-{str(max_num + 1).zfill(4)}"

    def _build_records_query(
        self,
        session: Session,
        *,
        scope: str,
        department: Optional[str],
        doctor: Optional[str],
        date_field: str,
        start_date: Optional[str],
        end_date: Optional[str],
        keyword: Optional[str],
        record_ids: Optional[Sequence[str]] = None,
    ):
        scope_value = _normalize_scope(scope)
        date_field_value = _normalize_date_field(date_field)
        start = _as_date(start_date)
        end = _as_date(end_date)
        dept_expr = func.coalesce(
            MedicalRecordFrontpage.discharge_dept_name,
            MedicalRecordFrontpage.admission_dept_name,
            DischargeRecord.dept_name,
            AdmissionRecord.dept_name,
        )
        discharge_dt_expr = func.coalesce(
            MedicalRecordFrontpage.discharge_datetime,
            DischargeRecord.discharge_date,
            DischargeRecord.update_time,
        )
        admission_dt_expr = func.coalesce(
            MedicalRecordFrontpage.admission_datetime,
            AdmissionRecord.admission_datetime,
            AdmissionRecord.update_time,
        )
        query = (
            session.query(
                MedicalRecordFrontpage,
                discharge_dt_expr.label("effective_discharge_datetime"),
                admission_dt_expr.label("effective_admission_datetime"),
            )
            .outerjoin(
                DischargeRecord,
                and_(
                    DischargeRecord.institute_id == MedicalRecordFrontpage.institute_id,
                    DischargeRecord.patient_id == MedicalRecordFrontpage.patient_id,
                    DischargeRecord.visit_id == MedicalRecordFrontpage.visit_id,
                ),
            )
            .outerjoin(
                AdmissionRecord,
                and_(
                    AdmissionRecord.institute_id == MedicalRecordFrontpage.institute_id,
                    AdmissionRecord.patient_id == MedicalRecordFrontpage.patient_id,
                    AdmissionRecord.visit_id == MedicalRecordFrontpage.visit_id,
                ),
            )
        )

        if scope_value == "final":
            query = query.filter(discharge_dt_expr.is_not(None))
        elif scope_value == "running":
            query = query.filter(discharge_dt_expr.is_(None))

        if department:
            query = query.filter(dept_expr == department)
        if doctor:
            query = query.filter(MedicalRecordFrontpage.attending_physician_sign == doctor)

        if keyword:
            kw = f"%{keyword.strip()}%"
            query = query.filter(
                or_(
                    MedicalRecordFrontpage.visit_id.ilike(kw),
                    MedicalRecordFrontpage.name.ilike(kw),
                    MedicalRecordFrontpage.mr_no.ilike(kw),
                    MedicalRecordFrontpage.inpat_no.ilike(kw),
                )
            )

        if record_ids:
            normalized_ids = [_safe_text(item) for item in record_ids if _safe_text(item)]
            if normalized_ids:
                query = query.filter(MedicalRecordFrontpage.visit_id.in_(normalized_ids))

        date_condition = _record_date_range_condition(
            date_field=date_field_value,
            admission_column=admission_dt_expr,
            discharge_column=discharge_dt_expr,
            start=start,
            end=end,
        )
        if date_condition is not None:
            query = query.filter(date_condition)
        return query

    def _serialize_record_row(self, row: Any) -> Dict[str, Any]:
        source_row = row
        effective_discharge_datetime = None
        effective_admission_datetime = None
        if isinstance(row, tuple):
            source_row = row[0]
            if len(row) > 1:
                effective_discharge_datetime = row[1]
            if len(row) > 2:
                effective_admission_datetime = row[2]
        effective_discharge_datetime = effective_discharge_datetime or source_row.discharge_datetime
        effective_admission_datetime = effective_admission_datetime or source_row.admission_datetime
        item_scope = "final" if effective_discharge_datetime else "running"
        item_department = _safe_text(source_row.discharge_dept_name or source_row.admission_dept_name)
        return {
            "record_id": _safe_text(source_row.visit_id),
            "visit_id": _safe_text(source_row.visit_id),
            "patient_name": _safe_text(source_row.name),
            "mr_no": _safe_text(source_row.mr_no),
            "inpat_no": _safe_text(source_row.inpat_no),
            "scope": item_scope,
            "department": item_department,
            "doctor": _safe_text(source_row.attending_physician_sign),
            "admission_date": _to_iso_date(effective_admission_datetime),
            "discharge_date": _to_iso_date(effective_discharge_datetime),
            "status": "completed" if item_scope == "final" else "running",
            "medical_text_length": len(_safe_text(source_row.record_content)),
        }

    def _collect_explicit_anchor_records(
        self,
        session: Session,
        *,
        record_ids: Sequence[str],
        excluded_record_ids: set[str],
        scope: str,
        department: Optional[str],
        doctor: Optional[str],
        date_field: str,
        start_date: Optional[str],
        end_date: Optional[str],
        keyword: Optional[str],
    ) -> List[Dict[str, Any]]:
        """为没有病案首页的在院病例补充本地执行锚点。"""
        missing_ids = list(
            dict.fromkeys(
                _safe_text(record_id)
                for record_id in record_ids
                if _safe_text(record_id)
                and _safe_text(record_id) not in excluded_record_ids
            )
        )
        if not missing_ids:
            return []

        discharge_rows = (
            session.query(DischargeRecord)
            .filter(DischargeRecord.visit_id.in_(missing_ids))
            .all()
        )
        discharge_by_visit = {
            _safe_text(row.visit_id): row
            for row in discharge_rows
            if _safe_text(getattr(row, "visit_id", ""))
        }
        registration_rows = (
            session.query(InpatRegistration)
            .filter(InpatRegistration.visit_id.in_(missing_ids))
            .all()
        )
        admission_rows = (
            session.query(AdmissionRecord)
            .filter(AdmissionRecord.visit_id.in_(missing_ids))
            .all()
        )

        anchor_by_visit: Dict[str, Any] = {}
        for row in registration_rows:
            visit_id = _safe_text(getattr(row, "visit_id", ""))
            if visit_id and visit_id not in anchor_by_visit:
                anchor_by_visit[visit_id] = row
        for row in admission_rows:
            visit_id = _safe_text(getattr(row, "visit_id", ""))
            if visit_id and visit_id not in anchor_by_visit:
                anchor_by_visit[visit_id] = row

        scope_value = _normalize_scope(scope)
        date_field_value = _normalize_date_field(date_field)
        start = _as_date(start_date)
        end = _as_date(end_date)
        records: List[Dict[str, Any]] = []
        for visit_id in missing_ids:
            source = anchor_by_visit.get(visit_id)
            if source is None:
                continue
            discharge_source = discharge_by_visit.get(visit_id)
            discharge_datetime = (
                getattr(source, "discharge_datetime", None)
                or getattr(discharge_source, "discharge_date", None)
            )
            item_scope = "final" if discharge_datetime else "running"
            if scope_value != "all" and item_scope != scope_value:
                continue

            item_department = _safe_text(
                getattr(source, "discharge_dept_name", None)
                or getattr(source, "admission_dept_name", None)
                or getattr(source, "dept_name", None)
                or getattr(discharge_source, "dept_name", None)
            )
            item_doctor = _safe_text(
                getattr(source, "attending_physician_sign", None)
                or getattr(source, "submitter", None)
            )
            if department and item_department != department:
                continue
            if doctor and item_doctor != doctor:
                continue
            if keyword:
                normalized_keyword = keyword.strip().lower()
                searchable_values = (
                    visit_id,
                    _safe_text(getattr(source, "name", "")),
                    _safe_text(getattr(source, "mr_no", "")),
                    _safe_text(getattr(source, "inpat_no", "")),
                )
                if normalized_keyword and not any(
                    normalized_keyword in value.lower()
                    for value in searchable_values
                    if value
                ):
                    continue

            admission_datetime = getattr(source, "admission_datetime", None)
            if not _record_dates_match_range(
                date_field=date_field_value,
                admission_datetime=admission_datetime,
                discharge_datetime=discharge_datetime,
                start=start,
                end=end,
            ):
                continue

            medical_text = _safe_text(getattr(source, "record_content", None))
            records.append(
                {
                    "institute_id": _safe_text(getattr(source, "institute_id", "")),
                    "patient_id": _safe_text(getattr(source, "patient_id", "")),
                    "record_id": visit_id,
                    "visit_id": visit_id,
                    "patient_name": _safe_text(getattr(source, "name", "")),
                    "mr_no": _safe_text(getattr(source, "mr_no", "")),
                    "inpat_no": _safe_text(getattr(source, "inpat_no", "")),
                    "scope": item_scope,
                    "department": item_department,
                    "doctor": item_doctor,
                    "admission_date": _to_iso_date(admission_datetime),
                    "discharge_date": _to_iso_date(discharge_datetime),
                    "admission_datetime": _to_iso_datetime(admission_datetime),
                    "discharge_datetime": _to_iso_datetime(discharge_datetime),
                    "status": "completed" if item_scope == "final" else "running",
                    "medical_text": medical_text,
                    "medical_text_length": len(medical_text),
                }
            )
        return records

    def _collect_explicit_anchor_records_by_refs(
        self,
        session: Session,
        *,
        record_refs: Sequence[CaseRefInput],
        excluded_record_refs: set[CaseRef],
        scope: str,
        department: Optional[str],
        doctor: Optional[str],
        date_field: str,
        start_date: Optional[str],
        end_date: Optional[str],
        keyword: Optional[str],
    ) -> List[Dict[str, Any]]:
        """按三坐标补充没有病案首页的执行锚点，禁止按 visit 串病例。"""

        missing_refs = [
            ref for ref in normalize_case_refs(record_refs) if ref not in excluded_record_refs
        ]
        if not missing_refs:
            return []

        def exact_clause(model: Any):
            return or_(
                *(
                    and_(
                        model.institute_id == ref.institute_id,
                        model.patient_id == ref.patient_id,
                        model.visit_id == ref.visit_id,
                    )
                    for ref in missing_refs
                )
            )

        discharge_rows = session.query(DischargeRecord).filter(exact_clause(DischargeRecord)).all()
        registration_rows = (
            session.query(InpatRegistration).filter(exact_clause(InpatRegistration)).all()
        )
        admission_rows = session.query(AdmissionRecord).filter(exact_clause(AdmissionRecord)).all()
        discharge_by_ref = {
            CaseRef.from_mapping(row.__dict__): row for row in discharge_rows
        }
        anchor_by_ref: Dict[CaseRef, Any] = {}
        for row in [*registration_rows, *admission_rows]:
            ref = CaseRef.from_mapping(row.__dict__)
            anchor_by_ref.setdefault(ref, row)

        scope_value = _normalize_scope(scope)
        date_field_value = _normalize_date_field(date_field)
        start = _as_date(start_date)
        end = _as_date(end_date)
        records: List[Dict[str, Any]] = []
        for ref in missing_refs:
            source = anchor_by_ref.get(ref)
            if source is None:
                continue
            discharge_source = discharge_by_ref.get(ref)
            discharge_datetime = (
                getattr(source, "discharge_datetime", None)
                or getattr(discharge_source, "discharge_date", None)
            )
            item_scope = "final" if discharge_datetime else "running"
            if scope_value != "all" and item_scope != scope_value:
                continue
            item_department = _safe_text(
                getattr(source, "discharge_dept_name", None)
                or getattr(source, "admission_dept_name", None)
                or getattr(source, "dept_name", None)
                or getattr(discharge_source, "dept_name", None)
            )
            item_doctor = _safe_text(
                getattr(source, "attending_physician_sign", None)
                or getattr(source, "submitter", None)
            )
            if department and item_department != department:
                continue
            if doctor and item_doctor != doctor:
                continue
            if keyword:
                normalized_keyword = keyword.strip().lower()
                searchable_values = (
                    ref.visit_id,
                    _safe_text(getattr(source, "name", "")),
                    _safe_text(getattr(source, "mr_no", "")),
                    _safe_text(getattr(source, "inpat_no", "")),
                )
                if normalized_keyword and not any(
                    normalized_keyword in value.lower()
                    for value in searchable_values
                    if value
                ):
                    continue
            admission_datetime = getattr(source, "admission_datetime", None)
            if not _record_dates_match_range(
                date_field=date_field_value,
                admission_datetime=admission_datetime,
                discharge_datetime=discharge_datetime,
                start=start,
                end=end,
            ):
                continue
            medical_text = _safe_text(getattr(source, "record_content", None))
            records.append(
                {
                    **ref.as_dict(),
                    "record_id": ref.visit_id,
                    "record_key": ref.as_key(),
                    "patient_name": _safe_text(getattr(source, "name", "")),
                    "mr_no": _safe_text(getattr(source, "mr_no", "")),
                    "inpat_no": _safe_text(getattr(source, "inpat_no", "")),
                    "scope": item_scope,
                    "department": item_department,
                    "doctor": item_doctor,
                    "admission_date": _to_iso_date(admission_datetime),
                    "discharge_date": _to_iso_date(discharge_datetime),
                    "admission_datetime": _to_iso_datetime(admission_datetime),
                    "discharge_datetime": _to_iso_datetime(discharge_datetime),
                    "status": "completed" if item_scope == "final" else "running",
                    "medical_text": medical_text,
                    "medical_text_length": len(medical_text),
                }
            )
        return records

    def list_drafts(
        self,
        *,
        created_by: str,
        status: Optional[str],
        query: Optional[str],
        page: int,
        page_size: int,
    ) -> WorkspaceListResult:
        session = _session()
        try:
            clauses = [self._draft_table.c.created_by == created_by]
            if status and status in {"draft", "published"}:
                clauses.append(self._draft_table.c.status == status)
            if query:
                keyword = f"%{query.strip()}%"
                clauses.append(
                    or_(
                        self._draft_table.c.rule_code.ilike(keyword),
                        self._draft_table.c.name.ilike(keyword),
                        self._draft_table.c.description.ilike(keyword),
                    )
                )

            where_clause = and_(*clauses)
            total_stmt = select(func.count()).select_from(self._draft_table).where(where_clause)
            total = int(session.execute(total_stmt).scalar() or 0)

            stmt = (
                select(self._draft_table)
                .where(where_clause)
                .order_by(desc(self._draft_table.c.updated_at), desc(self._draft_table.c.created_at))
                .offset(max(page - 1, 0) * page_size)
                .limit(page_size)
            )
            rows = session.execute(stmt).mappings().all()
            items = [_row_to_draft(dict(row)) for row in rows]
            return WorkspaceListResult(items=items, total=total, page=page, page_size=page_size)
        finally:
            session.close()

    def get_draft(self, *, draft_id: str, created_by: str) -> Optional[Dict[str, Any]]:
        session = _session()
        try:
            stmt = select(self._draft_table).where(
                and_(self._draft_table.c.id == draft_id, self._draft_table.c.created_by == created_by)
            )
            row = session.execute(stmt).mappings().first()
            if not row:
                return None
            return _row_to_draft(dict(row))
        finally:
            session.close()

    def create_draft(self, *, created_by: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        session = _session()
        try:
            now = _now_utc()
            severity = _safe_text(payload.get("severity"), "major").lower()
            document_type, applicable_documents, check_logic = align_document_domain_fields(
                document_type=payload.get("document_type"),
                applicable_documents=payload.get("applicable_documents"),
                check_logic=payload.get("check_logic") or {},
            )
            draft_id = str(uuid.uuid4())
            row_payload = {
                "id": draft_id,
                "rule_code": self._next_rule_code(session),
                "name": _safe_text(payload.get("name"), "未命名规则"),
                "description": _safe_text(payload.get("description"), ""),
                "source_requirement": _safe_text(
                    payload.get("source_requirement") or payload.get("description"), ""
                ),
                "prompt_template": _safe_text(payload.get("prompt_template"), ""),
                "document_type": document_type,
                "applicable_documents": _safe_json_dumps(applicable_documents),
                "severity": severity if severity in {"critical", "major", "minor"} else "major",
                "defect_level": _safe_text(
                    payload.get("defect_level"), _map_severity_to_defect_level(severity)
                ),
                "complexity": _safe_text(payload.get("complexity"), DEFAULT_COMPLEXITY),
                "scene": _safe_text(payload.get("scene"), "running"),
                "generation_mode": _safe_text(payload.get("generation_mode"), "fallback_template"),
                "examples": _safe_json_dumps(payload.get("examples") or []),
                "check_logic": _safe_json_dumps(check_logic),
                "last_test_summary": _safe_json_dumps(payload.get("last_test_summary") or None),
                "status": "draft",
                "published_rule_id": None,
                "created_by": created_by,
                "created_at": now,
                "updated_at": now,
            }
            session.execute(self._draft_table.insert().values(**row_payload))
            session.commit()
            return self.get_draft(draft_id=draft_id, created_by=created_by) or _row_to_draft(row_payload)
        finally:
            session.close()

    def update_draft(self, *, draft_id: str, created_by: str, payload: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        session = _session()
        try:
            existing_stmt = select(self._draft_table).where(
                and_(self._draft_table.c.id == draft_id, self._draft_table.c.created_by == created_by)
            )
            existing = session.execute(existing_stmt).mappings().first()
            if not existing:
                return None

            patch: Dict[str, Any] = {"updated_at": _now_utc()}
            editable_fields = {
                "name",
                "description",
                "source_requirement",
                "prompt_template",
                "document_type",
                "severity",
                "defect_level",
                "complexity",
                "scene",
                "generation_mode",
                "published_rule_id",
                "status",
            }
            for key in editable_fields:
                if key in payload and payload[key] is not None:
                    patch[key] = payload[key]

            existing_check_logic = _safe_json_loads(existing.get("check_logic"), {})
            aligned_document_type, aligned_applicable_documents, aligned_check_logic = align_document_domain_fields(
                document_type=patch.get("document_type", existing.get("document_type")),
                applicable_documents=(
                    payload.get("applicable_documents")
                    if "applicable_documents" in payload
                    else _safe_json_loads(existing.get("applicable_documents"), [])
                ),
                check_logic=(
                    payload.get("check_logic")
                    if "check_logic" in payload
                    else existing_check_logic
                ),
            )
            patch["document_type"] = aligned_document_type
            patch["applicable_documents"] = _safe_json_dumps(aligned_applicable_documents)
            patch["check_logic"] = _safe_json_dumps(aligned_check_logic)

            if "examples" in payload:
                patch["examples"] = _safe_json_dumps(payload.get("examples") or [])
            if "last_test_summary" in payload:
                patch["last_test_summary"] = _safe_json_dumps(payload.get("last_test_summary"))

            if "severity" in patch and "defect_level" not in patch:
                patch["defect_level"] = _map_severity_to_defect_level(_safe_text(patch.get("severity")))

            session.execute(
                update(self._draft_table)
                .where(and_(self._draft_table.c.id == draft_id, self._draft_table.c.created_by == created_by))
                .values(**patch)
            )
            session.commit()
            return self.get_draft(draft_id=draft_id, created_by=created_by)
        finally:
            session.close()

    def delete_draft(self, *, draft_id: str, created_by: str) -> bool:
        session = _session()
        try:
            result = session.execute(
                self._draft_table.delete().where(
                    and_(self._draft_table.c.id == draft_id, self._draft_table.c.created_by == created_by)
                )
            )
            session.commit()
            return bool(result.rowcount and result.rowcount > 0)
        finally:
            session.close()

    def _build_records_query(
        self,
        session: Session,
        *,
        scope: str,
        department: Optional[str],
        doctor: Optional[str],
        date_field: str,
        start_date: Optional[str],
        end_date: Optional[str],
        keyword: Optional[str],
        record_ids: Optional[Sequence[str]] = None,
        record_refs: Optional[Sequence[CaseRefInput]] = None,
    ):
        scope_value = _normalize_scope(scope)
        date_field_value = _normalize_date_field(date_field)
        start = _as_date(start_date)
        end = _as_date(end_date)
        dept_expr = func.coalesce(
            MedicalRecordFrontpage.discharge_dept_name,
            MedicalRecordFrontpage.admission_dept_name,
            DischargeRecord.dept_name,
            AdmissionRecord.dept_name,
        )
        discharge_dt_expr = func.coalesce(
            MedicalRecordFrontpage.discharge_datetime,
            DischargeRecord.discharge_date,
            DischargeRecord.update_time,
        )
        admission_dt_expr = func.coalesce(
            MedicalRecordFrontpage.admission_datetime,
            AdmissionRecord.admission_datetime,
            AdmissionRecord.update_time,
        )
        query = (
            session.query(
                MedicalRecordFrontpage,
                discharge_dt_expr.label("effective_discharge_datetime"),
                admission_dt_expr.label("effective_admission_datetime"),
            )
            .outerjoin(
                DischargeRecord,
                and_(
                    DischargeRecord.institute_id == MedicalRecordFrontpage.institute_id,
                    DischargeRecord.patient_id == MedicalRecordFrontpage.patient_id,
                    DischargeRecord.visit_id == MedicalRecordFrontpage.visit_id,
                ),
            )
            .outerjoin(
                AdmissionRecord,
                and_(
                    AdmissionRecord.institute_id == MedicalRecordFrontpage.institute_id,
                    AdmissionRecord.patient_id == MedicalRecordFrontpage.patient_id,
                    AdmissionRecord.visit_id == MedicalRecordFrontpage.visit_id,
                ),
            )
        )

        if scope_value == "final":
            query = query.filter(discharge_dt_expr.is_not(None))
        elif scope_value == "running":
            query = query.filter(discharge_dt_expr.is_(None))

        if department:
            query = query.filter(dept_expr == department)
        if doctor:
            query = query.filter(MedicalRecordFrontpage.attending_physician_sign == doctor)

        if keyword:
            kw = f"%{keyword.strip()}%"
            query = query.filter(
                or_(
                    MedicalRecordFrontpage.visit_id.ilike(kw),
                    MedicalRecordFrontpage.name.ilike(kw),
                    MedicalRecordFrontpage.mr_no.ilike(kw),
                    MedicalRecordFrontpage.inpat_no.ilike(kw),
                )
            )

        if record_refs:
            normalized_refs = normalize_case_refs(record_refs)
            query = query.filter(
                or_(
                    *(
                        and_(
                            MedicalRecordFrontpage.institute_id == ref.institute_id,
                            MedicalRecordFrontpage.patient_id == ref.patient_id,
                            MedicalRecordFrontpage.visit_id == ref.visit_id,
                        )
                        for ref in normalized_refs
                    )
                )
            )
        elif record_ids:
            normalized_ids = [_safe_text(item) for item in record_ids if _safe_text(item)]
            if normalized_ids:
                query = query.filter(MedicalRecordFrontpage.visit_id.in_(normalized_ids))

        date_condition = _record_date_range_condition(
            date_field=date_field_value,
            admission_column=admission_dt_expr,
            discharge_column=discharge_dt_expr,
            start=start,
            end=end,
        )
        if date_condition is not None:
            query = query.filter(date_condition)
        return query

    def _serialize_record_row(self, row: Any) -> Dict[str, Any]:
        source_row = row
        effective_discharge_datetime = None
        effective_admission_datetime = None
        if isinstance(row, tuple) or (
            hasattr(row, "_mapping") and not hasattr(row, "visit_id")
        ):
            source_row = row[0]
            if len(row) > 1:
                effective_discharge_datetime = row[1]
            if len(row) > 2:
                effective_admission_datetime = row[2]
        effective_discharge_datetime = (
            effective_discharge_datetime or source_row.discharge_datetime
        )
        effective_admission_datetime = (
            effective_admission_datetime or source_row.admission_datetime
        )
        item_scope = "final" if effective_discharge_datetime else "running"
        item_department = _safe_text(
            source_row.discharge_dept_name or source_row.admission_dept_name
        )
        return {
            "institute_id": _safe_text(getattr(source_row, "institute_id", "")),
            "patient_id": _safe_text(getattr(source_row, "patient_id", "")),
            "record_id": _safe_text(source_row.visit_id),
            "visit_id": _safe_text(source_row.visit_id),
            "record_key": CaseRef(
                _safe_text(getattr(source_row, "institute_id", "")),
                _safe_text(getattr(source_row, "patient_id", "")),
                _safe_text(source_row.visit_id),
            ).as_key(),
            "patient_name": _safe_text(source_row.name),
            "mr_no": _safe_text(source_row.mr_no),
            "inpat_no": _safe_text(source_row.inpat_no),
            "scope": item_scope,
            "department": item_department,
            "doctor": _safe_text(source_row.attending_physician_sign),
            "admission_date": _to_iso_date(effective_admission_datetime),
            "discharge_date": _to_iso_date(effective_discharge_datetime),
            "admission_datetime": _to_iso_datetime(effective_admission_datetime),
            "discharge_datetime": _to_iso_datetime(effective_discharge_datetime),
            "status": "completed" if item_scope == "final" else "running",
            "medical_text": _safe_text(source_row.record_content),
            "medical_text_length": len(_safe_text(source_row.record_content)),
        }

    def list_records(
        self,
        *,
        scope: str,
        department: Optional[str],
        doctor: Optional[str],
        date_field: str,
        start_date: Optional[str],
        end_date: Optional[str],
        keyword: Optional[str],
        page: int,
        page_size: int,
    ) -> WorkspaceListResult:
        session = _session()
        try:
            query = self._build_records_query(
                session,
                scope=scope,
                department=department,
                doctor=doctor,
                date_field=date_field,
                start_date=start_date,
                end_date=end_date,
                keyword=keyword,
            )
            total = int(query.count())
            rows = (
                query.order_by(
                    desc(MedicalRecordFrontpage.discharge_datetime),
                    desc(MedicalRecordFrontpage.admission_datetime),
                )
                .offset(max(page - 1, 0) * page_size)
                .limit(page_size)
                .all()
            )
            items = [self._serialize_record_row(row) for row in rows]
            return WorkspaceListResult(items=items, total=total, page=page, page_size=page_size)
        finally:
            session.close()

    def get_record_filters(
        self,
        *,
        scope: str,
        department: Optional[str],
    ) -> Dict[str, Any]:
        session = _session()
        try:
            dept_expr = func.coalesce(
                MedicalRecordFrontpage.discharge_dept_name, MedicalRecordFrontpage.admission_dept_name
            )
            base_query = self._build_records_query(
                session,
                scope=scope,
                department=None,
                doctor=None,
                date_field="admission",
                start_date=None,
                end_date=None,
                keyword=None,
            )

            dept_query = base_query.with_entities(dept_expr.label("department")).filter(
                dept_expr.is_not(None), dept_expr != ""
            )
            departments = [row.department for row in dept_query.distinct().order_by(asc("department")).all()]

            doctor_query = base_query.with_entities(
                MedicalRecordFrontpage.attending_physician_sign.label("doctor")
            ).filter(
                MedicalRecordFrontpage.attending_physician_sign.is_not(None),
                MedicalRecordFrontpage.attending_physician_sign != "",
            )
            if department:
                doctor_query = doctor_query.filter(dept_expr == department)
            doctors = [row.doctor for row in doctor_query.distinct().order_by(asc("doctor")).all()]

            date_bounds = base_query.with_entities(
                func.min(MedicalRecordFrontpage.admission_datetime).label("min_admission"),
                func.max(MedicalRecordFrontpage.admission_datetime).label("max_admission"),
                func.min(MedicalRecordFrontpage.discharge_datetime).label("min_discharge"),
                func.max(MedicalRecordFrontpage.discharge_datetime).label("max_discharge"),
            ).first()

            return {
                "departments": [d for d in departments if _safe_text(d)],
                "doctors": [d for d in doctors if _safe_text(d)],
                "date_bounds": {
                    "admission": {
                        "min": _to_iso_date(getattr(date_bounds, "min_admission", None)),
                        "max": _to_iso_date(getattr(date_bounds, "max_admission", None)),
                    },
                    "discharge": {
                        "min": _to_iso_date(getattr(date_bounds, "min_discharge", None)),
                        "max": _to_iso_date(getattr(date_bounds, "max_discharge", None)),
                    },
                },
            }
        finally:
            session.close()

    def collect_records(
        self,
        *,
        scope: str,
        department: Optional[str],
        doctor: Optional[str],
        date_field: str,
        start_date: Optional[str],
        end_date: Optional[str],
        keyword: Optional[str],
        record_ids: Optional[Sequence[str]] = None,
        record_refs: Optional[Sequence[CaseRefInput]] = None,
    ) -> List[Dict[str, Any]]:
        session = _session()
        try:
            query = self._build_records_query(
                session,
                scope=scope,
                department=department,
                doctor=doctor,
                date_field=date_field,
                start_date=start_date,
                end_date=end_date,
                keyword=keyword,
                record_ids=record_ids,
                record_refs=record_refs,
            )
            rows = query.order_by(
                desc(MedicalRecordFrontpage.discharge_datetime),
                desc(MedicalRecordFrontpage.admission_datetime),
            ).all()
            records = [self._serialize_record_row(row) for row in rows]
            if record_refs:
                records.extend(
                    self._collect_explicit_anchor_records_by_refs(
                        session,
                        record_refs=record_refs,
                        excluded_record_refs={
                            CaseRef.from_mapping(item)
                            for item in records
                            if all(CaseRef.from_mapping(item))
                        },
                        scope=scope,
                        department=department,
                        doctor=doctor,
                        date_field=date_field,
                        start_date=start_date,
                        end_date=end_date,
                        keyword=keyword,
                    )
                )
            elif record_ids:
                records.extend(
                    self._collect_explicit_anchor_records(
                        session,
                        record_ids=record_ids,
                        excluded_record_ids={
                            _safe_text(item.get("visit_id"))
                            for item in records
                            if _safe_text(item.get("visit_id"))
                        },
                        scope=scope,
                        department=department,
                        doctor=doctor,
                        date_field=date_field,
                        start_date=start_date,
                        end_date=end_date,
                        keyword=keyword,
                    )
                )
            return records
        finally:
            session.close()

    def count_records(
        self,
        *,
        scope: str,
        department: Optional[str],
        doctor: Optional[str],
        date_field: str,
        start_date: Optional[str],
        end_date: Optional[str],
        keyword: Optional[str],
        record_ids: Optional[Sequence[str]] = None,
        record_refs: Optional[Sequence[CaseRefInput]] = None,
    ) -> int:
        if record_ids or record_refs:
            records = self.collect_records(
                scope=scope,
                department=department,
                doctor=doctor,
                date_field=date_field,
                start_date=start_date,
                end_date=end_date,
                keyword=keyword,
                record_ids=record_ids,
                record_refs=record_refs,
            )
            return len(
                {
                    CaseRef.from_mapping(item)
                    for item in records
                    if all(CaseRef.from_mapping(item))
                }
            )

        session = _session()
        try:
            query = self._build_records_query(
                session,
                scope=scope,
                department=department,
                doctor=doctor,
                date_field=date_field,
                start_date=start_date,
                end_date=end_date,
                keyword=keyword,
                record_ids=record_ids,
                record_refs=record_refs,
            )
            identity_rows = (
                query.with_entities(
                    MedicalRecordFrontpage.institute_id,
                    MedicalRecordFrontpage.patient_id,
                    MedicalRecordFrontpage.visit_id,
                )
                .distinct()
                .subquery()
            )
            return int(
                session.query(func.count()).select_from(identity_rows).scalar() or 0
            )
        finally:
            session.close()

    def hydrate_records_with_medical_text(
        self,
        records: Sequence[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        visit_ids = {
            _safe_text(item.get("visit_id") or item.get("record_id"))
            for item in records
            if _safe_text(item.get("visit_id") or item.get("record_id"))
        }
        if not visit_ids:
            return []

        exact_refs = {
            CaseRef.from_mapping(item)
            for item in records
            if all(CaseRef.from_mapping(item))
        }
        use_exact_refs = bool(records) and all(
            all(CaseRef.from_mapping(item)) for item in records
        )

        session = _session()
        try:
            dept_expr = func.coalesce(
                MedicalRecordFrontpage.discharge_dept_name, MedicalRecordFrontpage.admission_dept_name
            )
            query = session.query(
                    MedicalRecordFrontpage.institute_id,
                    MedicalRecordFrontpage.patient_id,
                    MedicalRecordFrontpage.visit_id,
                    MedicalRecordFrontpage.name,
                    dept_expr.label("department"),
                    MedicalRecordFrontpage.attending_physician_sign,
                    MedicalRecordFrontpage.record_content,
                )
            if use_exact_refs:
                query = query.filter(
                    or_(
                        *(
                            and_(
                                MedicalRecordFrontpage.institute_id == ref.institute_id,
                                MedicalRecordFrontpage.patient_id == ref.patient_id,
                                MedicalRecordFrontpage.visit_id == ref.visit_id,
                            )
                            for ref in exact_refs
                        )
                    )
                )
            else:
                query = query.filter(MedicalRecordFrontpage.visit_id.in_(visit_ids))
            rows = query.all()
            row_map: Dict[CaseRef, Any] = {
                CaseRef(str(row.institute_id), str(row.patient_id), str(row.visit_id)): row
                for row in rows
            }
            legacy_rows: Dict[str, List[Any]] = {}
            for row in rows:
                legacy_rows.setdefault(str(row.visit_id), []).append(row)
        finally:
            session.close()

        hydrated: List[Dict[str, Any]] = []
        for item in records:
            visit_id = _safe_text(item.get("visit_id") or item.get("record_id"))
            item_ref = CaseRef.from_mapping(item)
            source = row_map.get(item_ref) if all(item_ref) else None
            if source is None and not all(item_ref):
                candidates = legacy_rows.get(visit_id) or []
                # 升级前任务仅有 visit_id；同 visit 命中多病例时失败关闭，禁止任取一条。
                source = candidates[0] if len(candidates) == 1 else None
            medical_text = _safe_text(item.get("medical_text"))
            if not medical_text and source is not None:
                medical_text = _safe_text(source.record_content)
            hydrated_item = dict(item)
            hydrated_item.update(
                {
                    "institute_id": _safe_text(item.get("institute_id") or (source.institute_id if source else "")),
                    "patient_id": _safe_text(item.get("patient_id") or (source.patient_id if source else "")),
                    "record_id": _safe_text(item.get("record_id") or visit_id),
                    "visit_id": visit_id,
                    "record_key": (
                        CaseRef(
                            _safe_text(item.get("institute_id") or (source.institute_id if source else "")),
                            _safe_text(item.get("patient_id") or (source.patient_id if source else "")),
                            visit_id,
                        ).as_key()
                        if visit_id
                        else ""
                    ),
                    "patient_name": _safe_text(item.get("patient_name") or (source.name if source else "")),
                    "department": _safe_text(item.get("department") or (source.department if source else "")),
                    "doctor": _safe_text(item.get("doctor") or (source.attending_physician_sign if source else "")),
                    "medical_text": medical_text,
                }
            )
            hydrated.append(hydrated_item)
        return hydrated

    def save_last_test_summary(
        self,
        *,
        draft_id: str,
        created_by: str,
        summary: Dict[str, Any],
    ) -> None:
        session = _session()
        try:
            session.execute(
                update(self._draft_table)
                .where(and_(self._draft_table.c.id == draft_id, self._draft_table.c.created_by == created_by))
                .values(
                    last_test_summary=_safe_json_dumps(summary),
                    updated_at=_now_utc(),
                )
            )
            session.commit()
        finally:
            session.close()

    def create_batch_job(
        self,
        *,
        draft: Dict[str, Any],
        created_by: str,
        scope: str,
        filters: Dict[str, Any],
        record_ids: Sequence[str],
        total_records: int,
        record_refs: Optional[Sequence[CaseRefInput]] = None,
        draft_ids: Optional[Sequence[str]] = None,
        execution_mode: str = "single",
        run_mode: str = "serial",
        rule_count: int = 1,
        job_kind: str = "leaf",
        parent_job_id: Optional[str] = None,
        child_job_ids: Optional[Sequence[str]] = None,
        child_summary: Optional[Dict[str, Any]] = None,
        family_key: Optional[str] = None,
        family_name: Optional[str] = None,
    ) -> Dict[str, Any]:
        session = _session()
        try:
            now = _now_utc()
            job_id = str(uuid.uuid4())
            normalized_draft_ids = [item for item in _normalize_string_list(list(draft_ids or [])) if item]
            if not normalized_draft_ids:
                current_draft_id = _safe_text(draft.get("id"))
                if current_draft_id:
                    normalized_draft_ids = [current_draft_id]
            normalized_execution_mode = _normalize_execution_mode(execution_mode)
            if normalized_execution_mode == "single" and len(normalized_draft_ids) > 1:
                normalized_execution_mode = "multi"
            normalized_run_mode = _normalize_run_mode(run_mode)
            normalized_record_refs = (
                normalize_case_refs(record_refs)
                if record_refs
                else normalize_case_refs(filters.get("record_refs"))
                if isinstance(filters.get("record_refs"), list) and filters.get("record_refs")
                else ()
            )
            effective_record_ids = (
                [ref.visit_id for ref in normalized_record_refs]
                if normalized_record_refs
                else list(record_ids)
            )
            filters_payload = {
                **(filters or {}),
                "draft_ids": normalized_draft_ids,
                "execution_mode": normalized_execution_mode,
                "run_mode": normalized_run_mode,
                **(
                    {"record_refs": [ref.as_dict() for ref in normalized_record_refs]}
                    if normalized_record_refs
                    else {}
                ),
            }
            summary_payload = {
                "rule_count": max(1, int(rule_count or len(normalized_draft_ids) or 1)),
                "progress": {
                    "step_key": "queued",
                    "rule_index": 0,
                    "rule_count": max(1, int(rule_count or len(normalized_draft_ids) or 1)),
                    "processed_records": 0,
                    "total_records": int(total_records or 0),
                },
                "updated_at": now.isoformat(),
            }
            row_payload = {
                "id": job_id,
                "draft_id": _safe_text(draft.get("id")),
                "rule_code": _safe_text(draft.get("rule_code")),
                "rule_name": _safe_text(draft.get("name"), "未命名规则"),
                "scene": _safe_text(draft.get("scene"), "final"),
                "scope": _normalize_scope(scope),
                "status": "queued",
                "filters_json": _safe_json_dumps(filters_payload),
                # 仅保留给升级前读取/展示；新任务的权威身份在 filters.record_refs。
                "record_ids_json": _safe_json_dumps(effective_record_ids),
                "summary_json": _safe_json_dumps(summary_payload),
                "items_json": None,
                "failed_records_json": None,
                "error_message": None,
                "created_by": created_by,
                "created_at": now,
                "started_at": None,
                "finished_at": None,
                "updated_at": now,
                "total_records": int(total_records or 0),
                "success_count": 0,
                "failed_count": 0,
                "issue_records": 0,
                "compliant_records": 0,
                "total_tokens": 0,
                "total_processing_time": 0.0,
                "job_kind": _safe_text(job_kind, "leaf") or "leaf",
                "parent_job_id": _safe_text(parent_job_id) or None,
                "child_job_ids_json": _safe_json_dumps(list(child_job_ids or [])),
                "child_summary_json": _safe_json_dumps(child_summary or {}),
                "family_key": _safe_text(family_key) or None,
                "family_name": _safe_text(family_name) or None,
            }
            session.execute(self._batch_job_table.insert().values(**row_payload))
            session.commit()
            return self.get_batch_job(job_id=job_id, created_by=created_by) or _row_to_batch_job(row_payload)
        finally:
            session.close()

    def update_parent_child_jobs(
        self,
        *,
        parent_job_id: str,
        created_by: str,
        child_job_ids: Sequence[str],
        child_summary: Optional[Dict[str, Any]] = None,
    ) -> Optional[Dict[str, Any]]:
        session = _session()
        try:
            now = _now_utc()
            session.execute(
                update(self._batch_job_table)
                .where(
                    and_(
                        self._batch_job_table.c.id == parent_job_id,
                        self._batch_job_table.c.created_by == created_by,
                    )
                )
                .values(
                    child_job_ids_json=_safe_json_dumps(list(child_job_ids or [])),
                    child_summary_json=_safe_json_dumps(child_summary or {}),
                    updated_at=now,
                )
            )
            session.commit()
            return self.get_batch_job(job_id=parent_job_id, created_by=created_by)
        finally:
            session.close()

    def get_batch_job(self, *, job_id: str, created_by: str) -> Optional[Dict[str, Any]]:
        session = _session()
        try:
            row = session.execute(
                select(self._batch_job_table).where(
                    and_(self._batch_job_table.c.id == job_id, self._batch_job_table.c.created_by == created_by)
                )
            ).mappings().first()
            if not row:
                return None
            return self._aggregate_parent_job(session, _row_to_batch_job(dict(row)))
        finally:
            session.close()

    def update_batch_job_review_report(
        self,
        *,
        job_id: str,
        created_by: str,
        review_report: Dict[str, Any],
    ) -> Optional[Dict[str, Any]]:
        session = _session()
        try:
            row = session.execute(
                select(self._batch_job_table).where(
                    and_(self._batch_job_table.c.id == job_id, self._batch_job_table.c.created_by == created_by)
                )
            ).mappings().first()
            if not row:
                return None
            current_summary = _safe_json_loads(row.get("summary_json"), {})
            if not isinstance(current_summary, dict):
                current_summary = {}
            now = _now_utc()
            next_summary = {
                **current_summary,
                "review_report": review_report,
                "reviewed_at": review_report.get("reviewed_at") or now.isoformat(),
                "updated_at": now.isoformat(),
            }
            session.execute(
                update(self._batch_job_table)
                .where(and_(self._batch_job_table.c.id == job_id, self._batch_job_table.c.created_by == created_by))
                .values(summary_json=_safe_json_dumps(next_summary), updated_at=now)
            )
            session.commit()
            return self.get_batch_job(job_id=job_id, created_by=created_by)
        finally:
            session.close()

    def get_batch_job_for_processing(self, *, job_id: str) -> Optional[Dict[str, Any]]:
        session = _session()
        try:
            row = session.execute(
                select(self._batch_job_table).where(self._batch_job_table.c.id == job_id)
            ).mappings().first()
            if not row:
                return None
            return self._aggregate_parent_job(session, _row_to_batch_job(dict(row)))
        finally:
            session.close()

    def list_batch_jobs(
        self,
        *,
        created_by: str,
        draft_id: Optional[str] = None,
        status: Optional[str] = None,
        scope: Optional[str] = None,
        query: Optional[str] = None,
        executor_type: Optional[str] = None,
        cache_hit: Optional[bool] = None,
        created_start_date: Optional[str] = None,
        created_end_date: Optional[str] = None,
        record_id: Optional[str] = None,
        include_children: bool = False,
        page: int = 1,
        page_size: int = DEFAULT_BATCH_JOB_PAGE_SIZE,
    ) -> WorkspaceBatchJobListResult:
        session = _session()
        try:
            clauses = [self._batch_job_table.c.created_by == created_by]
            if not include_children:
                clauses.append(
                    or_(
                        self._batch_job_table.c.parent_job_id.is_(None),
                        self._batch_job_table.c.parent_job_id == "",
                    )
                )
            if draft_id:
                clauses.append(self._batch_job_table.c.draft_id == draft_id)
            status_value = _safe_text(status).lower()
            if status_value:
                clauses.append(self._batch_job_table.c.status == status_value)
            scope_value = _safe_text(scope).lower()
            if scope_value:
                clauses.append(self._batch_job_table.c.scope == _normalize_scope(scope_value))
            query_value = _safe_text(query)
            if query_value:
                clauses.append(
                    or_(
                        self._batch_job_table.c.rule_code.ilike(f"%{query_value}%"),
                        self._batch_job_table.c.rule_name.ilike(f"%{query_value}%"),
                    )
                )
            start = _as_date(created_start_date)
            end = _as_date(created_end_date)
            if start:
                clauses.append(func.date(self._batch_job_table.c.created_at) >= start)
            if end:
                clauses.append(func.date(self._batch_job_table.c.created_at) <= end)
            record_id_value = _safe_text(record_id)
            if record_id_value:
                escaped_record_id = (
                    record_id_value
                    .replace("\\", "\\\\")
                    .replace("%", "\\%")
                    .replace("_", "\\_")
                    .replace('"', '\\"')
                )
                clauses.append(
                    self._batch_job_table.c.record_ids_json.ilike(
                        f'%"{escaped_record_id}"%',
                        escape="\\",
                    )
                )
            where_clause = and_(*clauses)
            executor_value = _safe_text(executor_type).lower()
            enable_runtime_filter = executor_value in {"program", "llm"} or cache_hit is not None

            if not enable_runtime_filter:
                total = int(
                    session.execute(
                        select(func.count()).select_from(self._batch_job_table).where(where_clause)
                    ).scalar()
                    or 0
                )
                rows = (
                    session.execute(
                        select(self._batch_job_table)
                        .where(where_clause)
                        .order_by(desc(self._batch_job_table.c.created_at))
                        .offset(max(page - 1, 0) * page_size)
                        .limit(page_size)
                    )
                    .mappings()
                    .all()
                )
                items = [
                    self._aggregate_parent_job(
                        session,
                        _row_to_batch_job(dict(row), include_items=False),
                        include_items=False,
                    )
                    for row in rows
                ]
                return WorkspaceBatchJobListResult(items=items, total=total, page=page, page_size=page_size)

            rows = (
                session.execute(
                    select(self._batch_job_table)
                    .where(where_clause)
                    .order_by(desc(self._batch_job_table.c.created_at))
                )
                .mappings()
                .all()
            )
            all_items = [
                self._aggregate_parent_job(
                    session,
                    _row_to_batch_job(dict(row), include_items=False),
                    include_items=False,
                )
                for row in rows
            ]

            filtered_items = all_items
            if executor_value in {"program", "llm"}:
                filtered_items = [
                    item
                    for item in filtered_items
                    if int(
                        (((item.get("summary") or {}).get("executor_breakdown") or {}).get(executor_value) or 0)
                    )
                    > 0
                ]
            if cache_hit is not None:
                expected = bool(cache_hit)
                filtered_items = [
                    item
                    for item in filtered_items
                    if (
                        (int((((item.get("summary") or {}).get("cache_breakdown") or {}).get("hit") or 0) or 0) > 0)
                        == expected
                    )
                ]

            total = len(filtered_items)
            offset = max(page - 1, 0) * page_size
            items = filtered_items[offset : offset + page_size]
            return WorkspaceBatchJobListResult(items=items, total=total, page=page, page_size=page_size)
        finally:
            session.close()

    def build_latest_single_record_result_dto(
        self,
        *,
        institute_id: str,
        patient_id: str,
        visit_id: str,
        rule_set_key: str = LUXIAN_0609_RULE_SET_KEY,
        rule_set_version: str = RULE_SET_VERSION,
        expected_rule_ids: Optional[Sequence[str]] = None,
    ) -> Dict[str, Any]:
        """读取一份病历当前规则代次的唯一客户结果。

        这是单病历结果页唯一允许使用的读取入口。候选首先由三坐标
        ``institute_id + patient_id + visit_id`` 限定，再从全院所有创建者的
        已完成任务中选择当前规则代次最新的唯一根任务；不得以结果状态、
        文案丰富度、证据数量或完整度来替换较新的任务。
        """

        normalized_institute_id = _safe_text(institute_id)
        normalized_patient_id = _safe_text(patient_id)
        normalized_visit_id = _safe_text(visit_id)
        normalized_rule_set_key = _safe_text(rule_set_key)
        normalized_rule_set_version = _safe_text(rule_set_version)
        if not all(
            (
                normalized_institute_id,
                normalized_patient_id,
                normalized_visit_id,
                normalized_rule_set_key,
                normalized_rule_set_version,
            )
        ):
            raise ValueError("单病历结果读取缺少三坐标身份或规则集参数")

        session = _session()
        try:
            root_rows = (
                session.execute(
                    select(self._batch_job_table)
                    .join(
                        self._record_result_envelope_table,
                        self._record_result_envelope_table.c.root_job_id
                        == self._batch_job_table.c.id,
                    )
                    .where(
                        and_(
                            self._batch_job_table.c.status == "completed",
                            or_(
                                self._batch_job_table.c.parent_job_id.is_(None),
                                self._batch_job_table.c.parent_job_id == "",
                            ),
                            self._record_result_envelope_table.c.institute_id
                            == normalized_institute_id,
                            self._record_result_envelope_table.c.patient_id
                            == normalized_patient_id,
                            self._record_result_envelope_table.c.visit_id == normalized_visit_id,
                            self._record_result_envelope_table.c.rule_set_key
                            == normalized_rule_set_key,
                            self._record_result_envelope_table.c.rule_set_version
                            == normalized_rule_set_version,
                        )
                    )
                    .distinct()
                    .order_by(
                        desc(self._batch_job_table.c.finished_at),
                        desc(self._batch_job_table.c.created_at),
                    )
                )
                .mappings()
                .all()
            )
            candidates = [
                self._aggregate_parent_job(session, _row_to_batch_job(dict(row)))
                for row in root_rows
            ]
            selection = select_latest_authoritative_record_result_job(
                candidates,
                record_id=normalized_visit_id,
                rule_set_key=normalized_rule_set_key,
                rule_set_version=normalized_rule_set_version,
            )
            if selection.state != "ready" or not isinstance(selection.job, dict):
                return {
                    "schema_version": "lx0609-single-record-result-v1",
                    "state": selection.state,
                    "reason_code": selection.reason_code,
                    "record_ref": "",
                    "job_id": "",
                    "items": [],
                    "expected_rule_count": len(
                        list(expected_rule_ids or []) or load_luxian_0609_rules()
                    ),
                    "result_rule_count": 0,
                    "is_complete": False,
                }

            selected_job = selection.job
            envelope = self._load_record_result_envelope_items(
                session,
                job_id=_safe_text(selected_job.get("id")),
                created_by=_safe_text(selected_job.get("created_by")),
                institute_id=normalized_institute_id,
                patient_id=normalized_patient_id,
                visit_id=normalized_visit_id,
                rule_set_key=normalized_rule_set_key,
                rule_set_version=normalized_rule_set_version,
            )
            if not envelope:
                return {
                    "schema_version": "lx0609-single-record-result-v1",
                    "state": "technical_error",
                    "reason_code": "canonical_result_envelope_missing",
                    "data_origin": "canonical_result_envelope",
                    "record_ref": "",
                    "job_id": _safe_text(selected_job.get("id")),
                    "items": [],
                    "expected_rule_count": len(
                        list(expected_rule_ids or []) or load_luxian_0609_rules()
                    ),
                    "result_rule_count": 0,
                    "is_complete": False,
                }
            raw_items = envelope.get("items")
            resolved_expected_rule_ids = list(
                dict.fromkeys(
                    _safe_text(rule_id).upper()
                    for rule_id in list(expected_rule_ids or [])
                    if _safe_text(rule_id)
                )
            )
            if not resolved_expected_rule_ids:
                resolved_expected_rule_ids = [
                    _safe_text(item.get("rule_id") or item.get("rule_code")).upper()
                    for item in load_luxian_0609_rules()
                    if _safe_text(item.get("rule_id") or item.get("rule_code"))
                ]
            expected_rule_id_set = set(resolved_expected_rule_ids)
            if not _canonical_envelope_items_are_consistent(raw_items):
                return {
                    "schema_version": "lx0609-single-record-result-v1",
                    "state": "technical_error",
                    "reason_code": "canonical_result_envelope_invalid",
                    "data_origin": "canonical_result_envelope",
                    "record_ref": "",
                    "job_id": _safe_text(selected_job.get("id")),
                    "items": [],
                    "expected_rule_count": len(resolved_expected_rule_ids),
                    "result_rule_count": 0,
                    "is_complete": False,
                }
            items = [dict(item) for item in raw_items]
            delivered_rule_ids = [
                _safe_text(item.get("rule_id") or item.get("rule_code")).upper()
                for item in items
            ]
            valid_rule_ids = [rule_id for rule_id in delivered_rule_ids if rule_id]
            conflicting_rule_ids = sorted(
                rule_id
                for rule_id in set(valid_rule_ids)
                if valid_rule_ids.count(rule_id) > 1
            )
            rule_master_by_id = {
                entry.rule_id: entry for entry in load_luxian_0609_rule_master()
            }
            projected_items = []
            for item, rule_id in zip(items, valid_rule_ids):
                projected_item = dict(item)
                master_entry = rule_master_by_id.get(rule_id)
                if master_entry is not None:
                    projected_item["source_document"] = master_entry.source_document
                    projected_item["qc_point"] = master_entry.qc_point
                projected_items.append(projected_item)

            missing_rule_ids = [
                rule_id for rule_id in resolved_expected_rule_ids if rule_id not in set(valid_rule_ids)
            ]
            return {
                "schema_version": "lx0609-single-record-result-v1",
                "state": "ready",
                "reason_code": "",
                "data_origin": "canonical_result_envelope",
                "record_ref": _safe_text(envelope.get("record_ref")),
                "job_id": _safe_text(selected_job.get("id")),
                "rule_set_key": normalized_rule_set_key,
                "rule_set_version": normalized_rule_set_version,
                "items": projected_items,
                "expected_rule_count": len(resolved_expected_rule_ids),
                "result_rule_count": len(items),
                "is_complete": not missing_rule_ids and not conflicting_rule_ids,
                "missing_rule_ids": missing_rule_ids,
                "conflicting_rule_ids": sorted(conflicting_rule_ids),
            }
        finally:
            session.close()

    def build_luxian_0609_completed_record_result_summaries(
        self,
        *,
        record_refs: Sequence[Mapping[str, Any]],
        rule_set_key: str = LUXIAN_0609_RULE_SET_KEY,
        rule_set_version: str = RULE_SET_VERSION,
        session_factory: Optional[Callable[[], Session]] = None,
        include_items: bool = False,
    ) -> Dict[tuple[str, str, str], Dict[str, Any]]:
        """批量读取病历池可展示的最新 Canonical 结果摘要。

        只读取完成的根任务及其显式 Envelope。它不会读取 legacy items、Bundle
        或 QCResult；无法以三坐标确认的结果不允许进入 ``ready`` 状态。
        """

        identities = {
            (
                _safe_text(ref.get("institute_id")),
                _safe_text(ref.get("patient_id")),
                _safe_text(ref.get("visit_id")),
            )
            for ref in record_refs
            if isinstance(ref, Mapping)
        }
        identities = {identity for identity in identities if all(identity)}
        if not identities:
            return {}

        normalized_rule_set_key = _safe_text(rule_set_key)
        normalized_rule_set_version = _safe_text(rule_set_version)
        if not normalized_rule_set_key or not normalized_rule_set_version:
            raise ValueError("病历池结果摘要缺少规则集身份")

        visit_ids = sorted({identity[2] for identity in identities})
        escaped_visit_ids = {
            visit_id: visit_id.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_").replace('"', '\\"')
            for visit_id in visit_ids
        }
        record_id_conditions = [
            self._batch_job_table.c.record_ids_json.ilike(
                f'%"{escaped_visit_ids[visit_id]}"%',
                escape="\\",
            )
            for visit_id in visit_ids
        ]
        # 规则集身份仍由 Python 做精确校验；这里仅以文本预筛掉与当前 LX0609
        # 代次无关的历史任务，避免全院首页解析大批无关 filters/summary JSON。
        # 两处都保留，是为了维持读取模型“filters 优先、summary 兼容回退”的合同。
        rule_set_candidate = or_(
            self._batch_job_table.c.filters_json.ilike(f"%{normalized_rule_set_key}%"),
            self._batch_job_table.c.summary_json.ilike(f"%{normalized_rule_set_key}%"),
        )
        rule_version_candidate = or_(
            self._batch_job_table.c.filters_json.ilike(f"%{normalized_rule_set_version}%"),
            self._batch_job_table.c.summary_json.ilike(f"%{normalized_rule_set_version}%"),
        )
        session = (session_factory or _session)()
        try:
            job_rows = (
                session.execute(
                    select(
                        self._batch_job_table.c.id,
                        self._batch_job_table.c.status,
                        self._batch_job_table.c.created_at,
                        self._batch_job_table.c.finished_at,
                        self._batch_job_table.c.filters_json,
                        self._batch_job_table.c.record_ids_json,
                        self._batch_job_table.c.summary_json,
                    ).where(
                        and_(
                            self._batch_job_table.c.status == "completed",
                            or_(
                                self._batch_job_table.c.parent_job_id.is_(None),
                                self._batch_job_table.c.parent_job_id == "",
                            ),
                            or_(*record_id_conditions),
                            rule_set_candidate,
                            rule_version_candidate,
                        )
                    )
                )
                .mappings()
                .all()
            )
            # 首页/病历池只需要“选择当前 Canonical 结果”的最小任务字段。
            # 不能为每个候选完整反序列化 items、子任务和运行摘要；真实全院范围
            # 会把同一批任务 JSON 反复解析数十万次，且不会增加任何判定事实。
            jobs_by_id: Dict[str, Dict[str, Any]] = {}
            current_jobs_by_visit: Dict[str, list[Dict[str, Any]]] = {}
            requested_visit_ids = set(visit_ids)
            for raw_row in job_rows:
                row = dict(raw_row)
                job_id = _safe_text(row.get("id"))
                if not job_id:
                    continue
                raw_filters = row.get("filters")
                raw_summary = row.get("summary")
                raw_filters_text = _safe_text(row.get("filters_json"))
                raw_summary_text = _safe_text(row.get("summary_json"))
                if (
                    not isinstance(raw_filters, dict)
                    and not isinstance(raw_summary, dict)
                    and (
                        normalized_rule_set_key not in raw_filters_text
                        and normalized_rule_set_key not in raw_summary_text
                        or normalized_rule_set_version not in raw_filters_text
                        and normalized_rule_set_version not in raw_summary_text
                    )
                ):
                    continue
                filters = (
                    raw_filters
                    if isinstance(raw_filters, dict)
                    else _safe_json_loads(row.get("filters_json"), {})
                )
                filters_dict = filters if isinstance(filters, dict) else {}
                filter_rule_set_key = _safe_text(filters_dict.get("rule_set_key"))
                filter_rule_set_version = _safe_text(filters_dict.get("rule_set_version"))
                if (
                    (
                        filter_rule_set_key
                        and filter_rule_set_key != normalized_rule_set_key
                    )
                    or (
                        filter_rule_set_version
                        and filter_rule_set_version != normalized_rule_set_version
                    )
                ):
                    continue
                summary = (
                    raw_summary
                    if isinstance(raw_summary, dict)
                    # filters 已具备当前规则集身份时，summary 不会参与读取模型的
                    # 选择；避免解析其中可能很大的运行态/明细 JSON。
                    else (
                        None
                        if (
                            filter_rule_set_key == normalized_rule_set_key
                            and filter_rule_set_version == normalized_rule_set_version
                        )
                        else _safe_json_loads(row.get("summary_json"), None)
                    )
                )
                raw_record_ids = row.get("record_ids")
                record_ids = (
                    raw_record_ids
                    if isinstance(raw_record_ids, list)
                    else _safe_json_loads(row.get("record_ids_json"), [])
                )
                job = {
                    "id": job_id,
                    "status": _safe_text(row.get("status"), "queued"),
                    "created_at": row.get("created_at"),
                    "finished_at": row.get("finished_at"),
                    "record_ids": record_ids if isinstance(record_ids, list) else [],
                    "filters": filters if isinstance(filters, dict) else {},
                    "summary": summary if isinstance(summary, dict) else None,
                }
                jobs_by_id[job_id] = job
                if (
                    _rule_set_value(job, "rule_set_key") != normalized_rule_set_key
                    or _rule_set_value(job, "rule_set_version") != normalized_rule_set_version
                ):
                    continue
                for visit_id in set(_safe_text(value) for value in job["record_ids"]):
                    if visit_id in requested_visit_ids:
                        current_jobs_by_visit.setdefault(visit_id, []).append(job)
            if not jobs_by_id:
                return {identity: {"status": "not_run"} for identity in identities}

            envelope_rows = (
                session.execute(
                    select(self._record_result_envelope_table).where(
                        and_(
                            self._record_result_envelope_table.c.root_job_id.in_(list(jobs_by_id)),
                            self._record_result_envelope_table.c.visit_id.in_(visit_ids),
                        )
                    )
                )
                .mappings()
                .all()
            )
            envelopes_by_identity: Dict[tuple[str, str, str], Dict[str, list[Dict[str, Any]]]] = {}
            current_envelopes_by_job_visit: Dict[tuple[str, str], list[Dict[str, Any]]] = {}
            for raw_row in envelope_rows:
                row = dict(raw_row)
                identity = (
                    _safe_text(row.get("institute_id")),
                    _safe_text(row.get("patient_id")),
                    _safe_text(row.get("visit_id")),
                )
                job_id = _safe_text(row.get("root_job_id"))
                if not job_id or not all(identity):
                    continue
                if (
                    _safe_text(row.get("rule_set_key")) == normalized_rule_set_key
                    and _safe_text(row.get("rule_set_version")) == normalized_rule_set_version
                ):
                    current_envelopes_by_job_visit.setdefault((job_id, identity[2]), []).append(row)
                    if identity in identities:
                        envelopes_by_identity.setdefault(identity, {}).setdefault(job_id, []).append(row)

            ambiguous_current_jobs_by_visit: Dict[str, list[Dict[str, Any]]] = {}
            for visit_id, candidates in current_jobs_by_visit.items():
                ambiguous_current_jobs_by_visit[visit_id] = [
                    job
                    for job in candidates
                    if not current_envelopes_by_job_visit.get((_safe_text(job.get("id")), visit_id), [])
                ]

            projections: Dict[tuple[str, str, str], Dict[str, Any]] = {}
            for identity in identities:
                _, _, visit_id = identity
                exact_envelopes = envelopes_by_identity.get(identity, {})
                ready_candidates = [
                    jobs_by_id[job_id]
                    for job_id in exact_envelopes
                    if job_id in jobs_by_id
                ]
                ready_selection = select_latest_authoritative_record_result_job(
                    ready_candidates,
                    record_id=visit_id,
                    rule_set_key=normalized_rule_set_key,
                    rule_set_version=normalized_rule_set_version,
                )
                # 只有当前规则版本、且没有任何当前版本同 visit Envelope 的根任务
                # 才是无法确认三坐标归属的缺失候选。旧版本 Envelope 完全不参与
                # 当前代次选择，也不能遮蔽当前版本的交付缺口。
                ambiguous_candidates = ambiguous_current_jobs_by_visit.get(visit_id, [])
                if ready_selection.state == "technical_error":
                    projections[identity] = {
                        "status": "technical_error",
                        "reason_code": "generation_conflict",
                    }
                    continue
                if ready_selection.state == "ready" and isinstance(ready_selection.job, dict):
                    ready_generation = _generation_key(ready_selection.job)
                    ambiguous_generation = max(
                        (_generation_key(job) for job in ambiguous_candidates),
                        default=None,
                    )
                    if ambiguous_generation is not None and ambiguous_generation >= ready_generation:
                        projections[identity] = {
                            "status": "technical_error",
                            "reason_code": "canonical_envelope_missing",
                        }
                        continue
                    selected_job_id = _safe_text(ready_selection.job.get("id"))
                    selected_envelopes = exact_envelopes.get(selected_job_id, [])
                    if len(selected_envelopes) != 1:
                        projections[identity] = {
                            "status": "technical_error",
                            "reason_code": "canonical_result_envelope_invalid",
                        }
                        continue
                    projections[identity] = self._summarize_completed_record_result_envelope(
                        envelope_row=selected_envelopes[0],
                        completed_at=ready_selection.job.get("finished_at"),
                        include_items=include_items,
                    )
                    continue

                # 仅以 visit_id 保存的历史根任务不能形成 ready。若该任务已有同
                # visit 的其他三坐标 Envelope，明确排除，避免把别的病历标记为缺失。
                ambiguous_selection = select_latest_authoritative_record_result_job(
                    ambiguous_candidates,
                    record_id=visit_id,
                    rule_set_key=normalized_rule_set_key,
                    rule_set_version=normalized_rule_set_version,
                )
                if ambiguous_selection.state == "technical_error":
                    projections[identity] = {
                        "status": "technical_error",
                        "reason_code": "generation_conflict",
                    }
                elif ambiguous_selection.state == "ready":
                    projections[identity] = {
                        "status": "technical_error",
                        "reason_code": "canonical_envelope_missing",
                    }
                else:
                    projections[identity] = {"status": "not_run"}
            return projections
        finally:
            session.close()

    @staticmethod
    def _summarize_completed_record_result_envelope(
        *,
        envelope_row: Mapping[str, Any],
        completed_at: Any,
        include_items: bool = False,
    ) -> Dict[str, Any]:
        """把一份通过结构校验的 Canonical Envelope 缩减为病历池摘要。"""

        envelope = _safe_json_loads(envelope_row.get("envelope_json"), {})
        if (
            not isinstance(envelope, dict)
            or envelope.get("schema_version") != _RECORD_RESULT_ENVELOPE_SCHEMA
            or envelope.get("delivery_mode") != _CANONICAL_RESULT_DELIVERY_MODE
            or not isinstance(envelope.get("items"), list)
        ):
            return {
                "status": "technical_error",
                "reason_code": "canonical_result_envelope_invalid",
            }

        if not _canonical_envelope_items_are_consistent(envelope["items"]):
            return {
                "status": "technical_error",
                "reason_code": "canonical_result_envelope_invalid",
            }

        status_counts: Dict[str, int] = {}
        for item in envelope["items"]:
            status = _safe_text(item.get("status"))
            status_counts[status] = status_counts.get(status, 0) + 1
        if isinstance(completed_at, datetime):
            completed_at_value = completed_at.isoformat()
        else:
            completed_at_value = _safe_text(completed_at)
        result: Dict[str, Any] = {
            "status": "ready",
            "completed_at": completed_at_value or None,
            "total_rule_count": len(envelope["items"]),
            "status_counts": dict(sorted(status_counts.items())),
        }
        if include_items:
            rule_master_by_id = {
                entry.rule_id: entry for entry in load_luxian_0609_rule_master()
            }
            projected_items: List[Dict[str, Any]] = []
            for item in envelope["items"]:
                projected_item = dict(item)
                rule_id = _safe_text(
                    projected_item.get("rule_id") or projected_item.get("rule_code")
                ).upper()
                master_entry = rule_master_by_id.get(rule_id)
                if master_entry is not None:
                    projected_item["source_document"] = master_entry.source_document
                    projected_item["qc_point"] = master_entry.qc_point
                projected_items.append(projected_item)
            result.update(
                {
                    "record_ref": _safe_text(envelope.get("record_ref")),
                    "items": projected_items,
                }
            )
        return result

    def build_latest_luxian_0609_record_result_dtos(
        self,
        *,
        record_refs: Sequence[Mapping[str, Any]],
        rule_set_key: str = LUXIAN_0609_RULE_SET_KEY,
        rule_set_version: str = RULE_SET_VERSION,
        session_factory: Optional[Callable[[], Session]] = None,
    ) -> Dict[tuple[str, str, str], Dict[str, Any]]:
        """一次读取一组病历的最新 Canonical 完整结果，供服务端全量导出。"""

        projections = self.build_luxian_0609_completed_record_result_summaries(
            record_refs=record_refs,
            rule_set_key=rule_set_key,
            rule_set_version=rule_set_version,
            session_factory=session_factory,
            include_items=True,
        )
        expected_rule_ids = [
            _safe_text(item.get("rule_id") or item.get("rule_code")).upper()
            for item in load_luxian_0609_rules()
            if _safe_text(item.get("rule_id") or item.get("rule_code"))
        ]
        results: Dict[tuple[str, str, str], Dict[str, Any]] = {}
        for identity, projection in projections.items():
            status = _safe_text(projection.get("status"))
            if status != "ready":
                results[identity] = {
                    "schema_version": "lx0609-single-record-result-v1",
                    "state": "not_found" if status == "not_run" else "technical_error",
                    "reason_code": _safe_text(projection.get("reason_code")),
                    "record_ref": "",
                    "items": [],
                    "expected_rule_count": len(expected_rule_ids),
                    "result_rule_count": 0,
                    "is_complete": False,
                }
                continue
            items = [
                dict(item)
                for item in projection.get("items") or []
                if isinstance(item, dict)
            ]
            delivered_rule_ids = {
                _safe_text(item.get("rule_id") or item.get("rule_code")).upper()
                for item in items
                if _safe_text(item.get("rule_id") or item.get("rule_code"))
            }
            missing_rule_ids = [
                rule_id for rule_id in expected_rule_ids if rule_id not in delivered_rule_ids
            ]
            results[identity] = {
                "schema_version": "lx0609-single-record-result-v1",
                "state": "ready",
                "data_origin": "canonical_result_envelope",
                "record_ref": _safe_text(projection.get("record_ref")),
                "rule_set_key": rule_set_key,
                "rule_set_version": rule_set_version,
                "items": items,
                "expected_rule_count": len(expected_rule_ids),
                "result_rule_count": len(items),
                "is_complete": not missing_rule_ids,
                "missing_rule_ids": missing_rule_ids,
            }
        return results

    def find_terminal_reevaluation_candidates(
        self,
        *,
        record_refs: Sequence[CaseRefInput],
        rule_set_key: str = LUXIAN_0609_RULE_SET_KEY,
        rule_set_version: str = RULE_SET_VERSION,
        session_factory: Optional[Callable[[], Session]] = None,
    ) -> tuple[CaseRef, ...]:
        """筛出已有运行期结果、且尚未启动终末复评的出院病历。"""

        normalized_refs = normalize_case_refs(record_refs)
        if not normalized_refs:
            return ()
        normalized_rule_set_key = _safe_text(rule_set_key)
        normalized_rule_set_version = _safe_text(rule_set_version)
        if not normalized_rule_set_key or not normalized_rule_set_version:
            raise ValueError("终末复评候选读取缺少规则集参数")

        identities = [
            (ref.institute_id, ref.patient_id, ref.visit_id) for ref in normalized_refs
        ]
        session = (session_factory or _session)()
        try:
            completed_rows = (
                session.execute(
                    select(
                        self._batch_job_table.c.id,
                        self._batch_job_table.c.scope,
                        self._batch_job_table.c.status,
                        self._batch_job_table.c.created_at,
                        self._batch_job_table.c.finished_at,
                        self._batch_job_table.c.filters_json,
                        self._record_result_envelope_table.c.institute_id,
                        self._record_result_envelope_table.c.patient_id,
                        self._record_result_envelope_table.c.visit_id,
                    )
                    .join(
                        self._record_result_envelope_table,
                        self._record_result_envelope_table.c.root_job_id
                        == self._batch_job_table.c.id,
                    )
                    .where(
                        and_(
                            self._batch_job_table.c.status == "completed",
                            or_(
                                self._batch_job_table.c.parent_job_id.is_(None),
                                self._batch_job_table.c.parent_job_id == "",
                            ),
                            self._record_result_envelope_table.c.rule_set_key
                            == normalized_rule_set_key,
                            self._record_result_envelope_table.c.rule_set_version
                            == normalized_rule_set_version,
                            tuple_(
                                self._record_result_envelope_table.c.institute_id,
                                self._record_result_envelope_table.c.patient_id,
                                self._record_result_envelope_table.c.visit_id,
                            ).in_(identities),
                        )
                    )
                    .order_by(
                        desc(self._batch_job_table.c.finished_at),
                        desc(self._batch_job_table.c.created_at),
                    )
                )
                .mappings()
                .all()
            )
            active_final_rows = (
                session.execute(
                    select(
                        self._batch_job_table.c.scope,
                        self._batch_job_table.c.status,
                        self._batch_job_table.c.filters_json,
                    ).where(
                        and_(
                            self._batch_job_table.c.status.in_(["queued", "running"]),
                            self._batch_job_table.c.filters_json.ilike(
                                f"%{normalized_rule_set_key}%"
                            ),
                            self._batch_job_table.c.filters_json.ilike(
                                f"%{normalized_rule_set_version}%"
                            ),
                            or_(
                                self._batch_job_table.c.parent_job_id.is_(None),
                                self._batch_job_table.c.parent_job_id == "",
                            ),
                        )
                    )
                )
                .mappings()
                .all()
            )

            active_final_identities: set[tuple[str, str, str]] = set()

            def _record_scene(
                filters: Mapping[str, Any],
                identity: tuple[str, str, str],
                fallback_scope: Any,
            ) -> str:
                for raw_snapshot in filters.get("record_scene_snapshot") or []:
                    if not isinstance(raw_snapshot, Mapping):
                        continue
                    snapshot_identity = (
                        _safe_text(raw_snapshot.get("institute_id")),
                        _safe_text(raw_snapshot.get("patient_id")),
                        _safe_text(raw_snapshot.get("visit_id")),
                    )
                    if snapshot_identity != identity:
                        continue
                    scene = _safe_text(
                        raw_snapshot.get("resolved_scene")
                        or raw_snapshot.get("record_scene")
                    ).lower()
                    if scene in {"running", "final"}:
                        return scene
                fallback = _safe_text(fallback_scope).lower()
                return fallback if fallback in {"running", "final"} else "unknown"

            for row in active_final_rows:
                filters = _safe_json_loads(row.get("filters_json"), {})
                if not isinstance(filters, dict):
                    continue
                if _safe_text(filters.get("rule_set_key")) != normalized_rule_set_key:
                    continue
                if _safe_text(filters.get("rule_set_version")) != normalized_rule_set_version:
                    continue
                try:
                    active_refs = normalize_case_refs(filters.get("record_refs") or [])
                except (TypeError, ValueError):
                    continue
                for ref in active_refs:
                    identity = (ref.institute_id, ref.patient_id, ref.visit_id)
                    if _record_scene(filters, identity, row.get("scope")) == "final":
                        active_final_identities.add(identity)

            rows_by_identity: Dict[tuple[str, str, str], List[Dict[str, Any]]] = {}
            for raw_row in completed_rows:
                row = dict(raw_row)
                identity = (
                    _safe_text(row.get("institute_id")),
                    _safe_text(row.get("patient_id")),
                    _safe_text(row.get("visit_id")),
                )
                if all(identity):
                    rows_by_identity.setdefault(identity, []).append(row)

            eligible: List[CaseRef] = []
            for ref in normalized_refs:
                identity = (ref.institute_id, ref.patient_id, ref.visit_id)
                if identity in active_final_identities:
                    continue
                rows = rows_by_identity.get(identity) or []
                if not rows:
                    continue
                latest_key = max(_generation_key(row) for row in rows)
                latest_rows = [row for row in rows if _generation_key(row) == latest_key]
                if len({_safe_text(row.get("id")) for row in latest_rows}) != 1:
                    continue
                latest_filters = _safe_json_loads(
                    latest_rows[0].get("filters_json"),
                    {},
                )
                if not isinstance(latest_filters, dict):
                    continue
                if _record_scene(
                    latest_filters,
                    identity,
                    latest_rows[0].get("scope"),
                ) != "running":
                    continue
                eligible.append(ref)
            return tuple(eligible)
        finally:
            session.close()

    def get_latest_luxian_0609_record_result(
        self,
        *,
        institute_id: str,
        patient_id: str,
        visit_id: str,
        expected_rule_ids: Optional[Sequence[str]] = None,
        rule_set_key: str = LUXIAN_0609_RULE_SET_KEY,
        rule_set_version: str = RULE_SET_VERSION,
    ) -> Dict[str, Any]:
        """单病历结果接口的唯一服务入口。"""

        return self.build_latest_single_record_result_dto(
            institute_id=institute_id,
            patient_id=patient_id,
            visit_id=visit_id,
            rule_set_key=rule_set_key,
            rule_set_version=rule_set_version,
            expected_rule_ids=expected_rule_ids,
        )

    @staticmethod
    def _result_item_belongs_to_record(item: Dict[str, Any], record_id: str) -> bool:
        """只接受原始结果明确携带的病历标识，禁止按文本或相似内容关联。"""

        normalized_record_id = _safe_text(record_id)
        return normalized_record_id in {
            _safe_text(item.get("record_id")),
            _safe_text(item.get("visit_id")),
        }

    @staticmethod
    def _single_record_result_source_items(
        job: Dict[str, Any],
        *,
        created_by: str,
    ) -> List[Dict[str, Any]]:
        """提取一个已选任务的原始结果行，不在此处做展示优先级去重。"""

        children = [
            child
            for child in list(job.get("child_jobs") or job.get("children") or [])
            if isinstance(child, dict) and _safe_text(child.get("created_by")) == _safe_text(created_by)
        ]
        sources = children or [job]
        items: List[Dict[str, Any]] = []
        for source in sources:
            items.extend(
                item for item in list(source.get("items") or []) if isinstance(item, dict)
            )
        if items:
            return items
        for source in sources:
            summary = source.get("summary") if isinstance(source.get("summary"), dict) else {}
            for rule_result in list(summary.get("rule_results") or source.get("rule_results") or []):
                if isinstance(rule_result, dict):
                    items.extend(
                        item for item in list(rule_result.get("items") or []) if isinstance(item, dict)
                    )
        return items

    def cancel_batch_job(self, *, job_id: str, created_by: str) -> Optional[Dict[str, Any]]:
        session = _session()
        try:
            row = session.execute(
                select(self._batch_job_table).where(
                    and_(self._batch_job_table.c.id == job_id, self._batch_job_table.c.created_by == created_by)
                )
            ).mappings().first()
            if not row:
                return None
            current = _row_to_batch_job(dict(row))
            if current.get("status") in {"completed", "failed", "canceled"}:
                return current
            current_summary = _safe_json_loads(row.get("summary_json"), {})
            if not isinstance(current_summary, dict):
                current_summary = {}
            now = _now_utc()
            cancelled_progress = (
                current_summary.get("progress")
                if isinstance(current_summary.get("progress"), dict)
                else {}
            )
            session.execute(
                update(self._batch_job_table)
                .where(
                    and_(self._batch_job_table.c.id == job_id, self._batch_job_table.c.created_by == created_by)
                )
                .values(
                    status="canceled",
                    summary_json=_safe_json_dumps(
                        {
                            **current_summary,
                            "progress": {
                                **cancelled_progress,
                                "step_key": "canceled",
                                "step_label": "已停止",
                            },
                            "user_cancelled": True,
                            "cancelled_by": created_by,
                            "cancelled_at": now.isoformat(),
                            "updated_at": now.isoformat(),
                        }
                    ),
                    error_message="user_cancelled: 任务已取消",
                    finished_at=now,
                    updated_at=now,
                )
            )
            if str(current.get("job_kind") or "").strip().lower() == "parent":
                child_ids = [
                    str(item or "").strip()
                    for item in list(current.get("child_job_ids") or [])
                    if str(item or "").strip()
                ]
                child_where = self._batch_job_table.c.parent_job_id == job_id
                if child_ids:
                    child_where = or_(child_where, self._batch_job_table.c.id.in_(child_ids))
                session.execute(
                    update(self._batch_job_table)
                    .where(
                        and_(
                            child_where,
                            self._batch_job_table.c.created_by == created_by,
                            self._batch_job_table.c.status.in_(["queued", "running"]),
                        )
                    )
                    .values(
                        status="canceled",
                        error_message="parent_cancelled: 总任务已取消",
                        finished_at=now,
                        updated_at=now,
                    )
                )
            session.commit()
            return self.get_batch_job(job_id=job_id, created_by=created_by)
        finally:
            session.close()

    def retry_batch_job(self, *, job_id: str, created_by: str) -> Optional[Dict[str, Any]]:
        session = _session()
        try:
            row = session.execute(
                select(self._batch_job_table).where(
                    and_(self._batch_job_table.c.id == job_id, self._batch_job_table.c.created_by == created_by)
                )
            ).mappings().first()
            if not row:
                return None
            current = _row_to_batch_job(dict(row))
            rule_count = int(current.get("rule_count") or 1)
            total_records = int(current.get("total_records") or 0)
            now = _now_utc()
            reset_values = dict(
                status="queued",
                summary_json=_safe_json_dumps(
                    {
                        "rule_count": max(1, rule_count),
                        "progress": {
                            "step_key": "queued",
                            "rule_index": 0,
                            "rule_count": max(1, rule_count),
                            "processed_records": 0,
                            "total_records": total_records,
                        },
                        "updated_at": now.isoformat(),
                    }
                ),
                items_json=None,
                failed_records_json=None,
                error_message=None,
                started_at=None,
                finished_at=None,
                updated_at=now,
                success_count=0,
                failed_count=0,
                issue_records=0,
                compliant_records=0,
                total_tokens=0,
                total_processing_time=0.0,
            )
            session.execute(
                update(self._batch_job_table)
                .where(
                    and_(self._batch_job_table.c.id == job_id, self._batch_job_table.c.created_by == created_by)
                )
                .values(**reset_values)
            )
            if str(current.get("job_kind") or "").strip().lower() == "parent":
                child_ids = [
                    str(item or "").strip()
                    for item in list(current.get("child_job_ids") or [])
                    if str(item or "").strip()
                ]
                child_where = self._batch_job_table.c.parent_job_id == job_id
                if child_ids:
                    child_where = or_(child_where, self._batch_job_table.c.id.in_(child_ids))
                session.execute(
                    update(self._batch_job_table)
                    .where(
                        and_(
                            child_where,
                            self._batch_job_table.c.created_by == created_by,
                        )
                    )
                    .values(**reset_values)
                )
            session.commit()
            return self.get_batch_job(job_id=job_id, created_by=created_by)
        finally:
            session.close()

    def get_child_batch_jobs(self, *, parent_job_id: str, created_by: Optional[str] = None) -> List[Dict[str, Any]]:
        session = _session()
        try:
            clauses = [self._batch_job_table.c.parent_job_id == parent_job_id]
            if created_by:
                clauses.append(self._batch_job_table.c.created_by == created_by)
            rows = (
                session.execute(
                    select(self._batch_job_table)
                    .where(and_(*clauses))
                    .order_by(asc(self._batch_job_table.c.created_at))
                )
                .mappings()
                .all()
            )
            return [_row_to_batch_job(dict(row)) for row in rows]
        finally:
            session.close()

    def mark_batch_job_running(self, *, job_id: str) -> bool:
        session = _session()
        try:
            row = session.execute(
                select(self._batch_job_table).where(self._batch_job_table.c.id == job_id)
            ).mappings().first()
            if not row:
                return False
            current = _row_to_batch_job(dict(row))
            if current.get("status") in {"canceled", "completed", "failed"}:
                return False
            current_summary = _safe_json_loads(row.get("summary_json"), {})
            if not isinstance(current_summary, dict):
                current_summary = {}
            progress_value = current_summary.get("progress")
            if not isinstance(progress_value, dict):
                progress_value = {}
            now = _now_utc()
            session.execute(
                update(self._batch_job_table)
                .where(self._batch_job_table.c.id == job_id)
                .values(
                    status="running",
                    started_at=now,
                    updated_at=now,
                    error_message=None,
                    summary_json=_safe_json_dumps(
                        {
                            **current_summary,
                            "progress": {
                                **progress_value,
                                "step_key": "prepare",
                            },
                            "updated_at": now.isoformat(),
                        }
                    ),
                )
            )
            session.commit()
            return True
        finally:
            session.close()

    def update_batch_job_progress(
        self,
        *,
        job_id: str,
        step_key: str,
        rule_index: int,
        rule_count: int,
        processed_records: int,
        total_records: int,
        summary_patch: Optional[Dict[str, Any]] = None,
        progress_patch: Optional[Dict[str, Any]] = None,
        items: Optional[List[Dict[str, Any]]] = None,
        failed_records: Optional[List[Dict[str, Any]]] = None,
    ) -> Optional[Dict[str, Any]]:
        session = _session()
        try:
            row = session.execute(
                select(self._batch_job_table).where(self._batch_job_table.c.id == job_id)
            ).mappings().first()
            if not row:
                return None
            current = _row_to_batch_job(dict(row))
            if current.get("status") == "canceled":
                return current

            current_summary = _safe_json_loads(row.get("summary_json"), {})
            if not isinstance(current_summary, dict):
                current_summary = {}
            merged_summary = {**current_summary, **(summary_patch or {})}
            merged_summary["rule_count"] = max(1, int(merged_summary.get("rule_count") or rule_count or 1))
            current_progress = (
                current_summary.get("progress")
                if isinstance(current_summary.get("progress"), dict)
                else {}
            )
            runtime_progress: Dict[str, int] = {}
            for key in (
                "max_parallel_records",
                "active_record_count",
                "queued_record_count",
            ):
                value = (progress_patch or {}).get(key, current_progress.get(key))
                if isinstance(value, (int, float)) and not isinstance(value, bool):
                    runtime_progress[key] = max(0, int(value))
            merged_summary["progress"] = {
                **runtime_progress,
                "step_key": _safe_text(step_key) or "run",
                "rule_index": max(0, int(rule_index or 0)),
                "rule_count": max(1, int(rule_count or merged_summary.get("rule_count") or 1)),
                "processed_records": max(0, int(processed_records or 0)),
                "total_records": max(0, int(total_records or 0)),
            }
            now = _now_utc()
            merged_summary["updated_at"] = now.isoformat()

            values: Dict[str, Any] = {
                "summary_json": _safe_json_dumps(merged_summary),
                "updated_at": now,
                "total_records": int(merged_summary.get("total_records") or total_records or 0),
                "success_count": int(merged_summary.get("success_count") or 0),
                "failed_count": int(merged_summary.get("failed_count") or 0),
                "issue_records": int(merged_summary.get("issue_records") or 0),
                "compliant_records": int(merged_summary.get("compliant_records") or 0),
                "total_tokens": int(merged_summary.get("total_tokens") or 0),
                "total_processing_time": float(merged_summary.get("total_processing_time") or 0.0),
            }
            if items is not None:
                values["items_json"] = _safe_json_dumps(items)
            if failed_records is not None:
                values["failed_records_json"] = _safe_json_dumps(failed_records)

            session.execute(
                update(self._batch_job_table)
                .where(and_(self._batch_job_table.c.id == job_id, self._batch_job_table.c.status != "canceled"))
                .values(**values)
            )
            session.commit()
            return self.get_batch_job_for_processing(job_id=job_id)
        finally:
            session.close()

    def complete_batch_job(
        self,
        *,
        job_id: str,
        summary: Dict[str, Any],
        items: List[Dict[str, Any]],
        failed_records: List[Dict[str, Any]],
    ) -> None:
        session = _session()
        try:
            row = session.execute(
                select(self._batch_job_table).where(self._batch_job_table.c.id == job_id)
            ).mappings().first()
            if not row:
                return
            parent_job_id = _safe_text(row.get("parent_job_id"))
            now = _now_utc()
            merged_summary = {
                **(summary or {}),
                "progress": {
                    **(
                        summary.get("progress")
                        if isinstance(summary.get("progress"), dict)
                        else {}
                    ),
                    "step_key": "completed",
                    "processed_records": int((summary or {}).get("total_records") or 0),
                    "total_records": int((summary or {}).get("total_records") or 0),
                },
                "updated_at": now.isoformat(),
            }
            session.execute(
                update(self._batch_job_table)
                .where(and_(self._batch_job_table.c.id == job_id, self._batch_job_table.c.status != "canceled"))
                .values(
                    status="completed",
                    summary_json=_safe_json_dumps(merged_summary),
                    items_json=_safe_json_dumps(items),
                    failed_records_json=_safe_json_dumps(failed_records),
                    total_records=int(summary.get("total_records") or 0),
                    success_count=int(summary.get("success_count") or 0),
                    failed_count=int(summary.get("failed_count") or 0),
                    issue_records=int(summary.get("issue_records") or 0),
                    compliant_records=int(summary.get("compliant_records") or 0),
                    total_tokens=int(summary.get("total_tokens") or 0),
                    total_processing_time=float(summary.get("total_processing_time") or 0.0),
                    finished_at=now,
                    updated_at=now,
                )
            )
            self._write_record_result_envelopes(
                session,
                job_row=dict(row),
                items=items,
                now=now,
            )
            session.commit()
            self.refresh_parent_batch_job(parent_job_id=parent_job_id)
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    @staticmethod
    def _envelope_item_from_rule_result(item: Dict[str, Any]) -> Dict[str, Any]:
        """截取 RuleDecision 交付所需字段，避免 Envelope 变成任务调试日志。"""

        allowed_keys = {
            "schema_version",
            "record_id",
            "institute_id",
            "patient_id",
            "visit_id",
            "mr_no",
            "record_ref",
            "customer_rule_id",
            "qc_point_id",
            "rule_id",
            "rule_code",
            "rule_name",
            "rule_version",
            "status",
            "result_status",
            "display_status",
            "is_compliant",
            "reason_code",
            "reason",
            "reason_detail",
            "reason_details",
            "conclusion",
            "findings",
            "detail",
            "actual",
            "standard",
            "suggestion",
            "customer_conclusion",
            "customer_suggestion",
            "customer_message",
            "customer_display_facts",
            "criterion_results",
            "decision_facts",
            "customer_evidence",
            "evidence_items",
            "evidence_refs",
            "evidence",
            "model_analysis",
            "medical_analysis",
            "semantic_analysis",
            "llm_analysis",
            "model_suggestion",
            "llm_suggestion",
            # data_gap / evaluation_unknown 不能只剩一个状态码。以下字段均来自
            # RuleDecision 已有事实或来源可用性，不在此处推断或补造医学结论。
            "data_gap_details",
            "missing_sources",
            "missing_fields",
            "required_sources",
            "unavailable_sources",
            "missing_evidence",
            "source_availability",
            "source_status",
            "evidence_availability",
        }
        result = {
            key: item.get(key)
            for key in allowed_keys
            if key in item and (item.get(key) is not None or key == "is_compliant")
        }
        if not isinstance(result.get("decision_facts"), dict) and isinstance(
            result.get("customer_display_facts"), dict
        ):
            result["decision_facts"] = result["customer_display_facts"]
        if not isinstance(result.get("customer_display_facts"), dict) and isinstance(
            result.get("decision_facts"), dict
        ):
            result["customer_display_facts"] = result["decision_facts"]

        # 单病历读模型已约定 conclusion/detail/actual/standard/suggestion；这里仅把
        # 同一 RuleDecision 的历史别名投影到该固定字段，不改结论、状态或规则语义。
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
                # reason_details 在少数旧执行器中可能是结构体；不把 Python repr
                # 当作客户说明。结构体仍会作为 data_gap_details 原样交付。
                value = _safe_text(raw_value) if isinstance(raw_value, str) else ""
                if value:
                    result["detail"] = value
                    break

        # LLM 事实提取器在不同规则族中历史命名并不完全一致。Envelope 统一为
        # ``model_analysis``，前端才能稳定展示“医学分析”折叠区；不以 findings
        # 等规则结论充数，避免把模板文案误标为模型分析。
        if not _safe_text(result.get("model_analysis")):
            for key in ("medical_analysis", "semantic_analysis", "llm_analysis"):
                value = _safe_text(item.get(key))
                if value:
                    result["model_analysis"] = value
                    break

        # 资料不足/待确认的“缺什么”必须随结果交付。只聚合已有的受控字段，保留
        # 原值结构，便于前端按来源、字段或时间展示；没有来源字段时不凭空编造。
        item_status = _safe_text(
            result.get("status") or result.get("result_status") or result.get("display_status")
        )
        if item_status in {"data_gap", "evaluation_unknown", "uncertain"}:
            gap_details = result.get("data_gap_details")
            if not isinstance(gap_details, dict):
                gap_details = {}
            for key in (
                "reason_code",
                "missing_sources",
                "missing_fields",
                "required_sources",
                "unavailable_sources",
                "missing_evidence",
                "source_availability",
                "source_status",
                "evidence_availability",
            ):
                value = result.get(key)
                if value not in (None, "", [], {}):
                    gap_details.setdefault(key, value)
            if gap_details:
                result["data_gap_details"] = gap_details

        # Canonical Envelope 是客户交付边界：业务判定字段保持不变，只把内部身份
        # 和文书主键转换为不可逆授权引用。读取 API 不再重复执行该步骤。
        hmac_key = customer_safe_projection_key()
        record_id = _safe_text(item.get("record_id") or item.get("visit_id"))
        if record_id:
            result["record_ref"] = _keyed_ref("rec", record_id, hmac_key=hmac_key)
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
                    else _keyed_ref("src", source_material, hmac_key=hmac_key)
                )
                evidence_rows.append(row)
        for key in ("customer_evidence", "evidence_items", "evidence_refs"):
            result.pop(key, None)
        result["evidence"] = evidence_rows
        for key in ("customer_display_facts", "decision_facts"):
            if isinstance(result.get(key), (dict, list)):
                result[key] = _sanitize_canonical_facts(result[key])
        return result

    def _write_record_result_envelopes(
        self,
        session: Session,
        *,
        job_row: Dict[str, Any],
        items: Sequence[Dict[str, Any]],
        now: datetime,
    ) -> None:
        """将每个病历的原生结果写入独立交付 Envelope。

        任务 ``items_json`` 仍保留给历史批量任务和导出使用；单病历结果页的新任务
        不再从它读取事实、子结论或模型分析。
        """

        filters = _safe_json_loads(job_row.get("filters_json"), {})
        filters = filters if isinstance(filters, dict) else {}
        rule_set_key = _safe_text(filters.get("rule_set_key"), LUXIAN_0609_RULE_SET_KEY)
        rule_set_version = _safe_text(filters.get("rule_set_version"), RULE_SET_VERSION)
        job_id = _safe_text(job_row.get("id"))
        root_job_id = _safe_text(job_row.get("parent_job_id")) or job_id
        created_by = _safe_text(job_row.get("created_by"))
        grouped: Dict[CaseRef, List[Dict[str, Any]]] = {}
        for raw_item in items:
            if not isinstance(raw_item, dict):
                continue
            record_ref = CaseRef.from_mapping(raw_item)
            if all(record_ref):
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
        for record_ref, record_items in grouped.items():
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
            if not _canonical_envelope_items_are_consistent(record_items):
                raise ValueError("Canonical Envelope 状态字段不一致，拒绝完成质控任务")

        for record_ref, record_items in grouped.items():
            record_id = record_ref.visit_id
            envelope = {
                "schema_version": _RECORD_RESULT_ENVELOPE_SCHEMA,
                "delivery_mode": _CANONICAL_RESULT_DELIVERY_MODE,
                "record_id": record_id,
                "record_ref": _keyed_ref(
                    "rec",
                    record_ref.as_key(),
                    hmac_key=customer_safe_projection_key(),
                ),
                "job_id": job_id,
                "root_job_id": root_job_id,
                "rule_set_key": rule_set_key,
                "rule_set_version": rule_set_version,
                "items": [self._envelope_item_from_rule_result(item) for item in record_items],
            }
            session.execute(
                self._record_result_envelope_table.delete().where(
                    and_(
                        self._record_result_envelope_table.c.job_id == job_id,
                        self._record_result_envelope_table.c.institute_id == record_ref.institute_id,
                        self._record_result_envelope_table.c.patient_id == record_ref.patient_id,
                        self._record_result_envelope_table.c.visit_id == record_ref.visit_id,
                    )
                )
            )
            session.execute(
                self._record_result_envelope_table.insert().values(
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
                    result_count=len(record_items),
                    created_at=now,
                    updated_at=now,
                )
            )

    def _load_record_result_envelope_items(
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
        """读取已选定任务唯一的 Canonical Envelope，不拼接、不回退。"""

        try:
            rows = (
                session.execute(
                    select(self._record_result_envelope_table)
                    .where(
                        and_(
                            self._record_result_envelope_table.c.job_id == job_id,
                            self._record_result_envelope_table.c.created_by == created_by,
                            self._record_result_envelope_table.c.record_id == visit_id,
                            self._record_result_envelope_table.c.institute_id == institute_id,
                            self._record_result_envelope_table.c.patient_id == patient_id,
                            self._record_result_envelope_table.c.visit_id == visit_id,
                            self._record_result_envelope_table.c.rule_set_key == rule_set_key,
                            self._record_result_envelope_table.c.rule_set_version == rule_set_version,
                        )
                    )
                )
                .mappings()
                .all()
            )
        except (sa.exc.ProgrammingError, sa.exc.OperationalError):
            # 兼容尚未运行 migration 的环境；不允许因为结果交付表缺失而让质控任务失败。
            return {}

        if len(rows) != 1:
            return {}
        envelope = _safe_json_loads(rows[0].get("envelope_json"), {})
        if (
            not isinstance(envelope, dict)
            or envelope.get("schema_version") != _RECORD_RESULT_ENVELOPE_SCHEMA
            or envelope.get("delivery_mode") != _CANONICAL_RESULT_DELIVERY_MODE
            or not isinstance(envelope.get("items"), list)
        ):
            return {}
        return envelope

    def fail_batch_job(self, *, job_id: str, error_message: str) -> None:
        session = _session()
        try:
            row = session.execute(
                select(self._batch_job_table).where(self._batch_job_table.c.id == job_id)
            ).mappings().first()
            if not row:
                return
            parent_job_id = _safe_text(row.get("parent_job_id"))
            current_summary = _safe_json_loads(row.get("summary_json"), {})
            if not isinstance(current_summary, dict):
                current_summary = {}
            now = _now_utc()
            session.execute(
                update(self._batch_job_table)
                .where(and_(self._batch_job_table.c.id == job_id, self._batch_job_table.c.status != "canceled"))
                .values(
                    status="failed",
                    summary_json=_safe_json_dumps(
                        {
                            **current_summary,
                            "progress": {
                                **(
                                    current_summary.get("progress")
                                    if isinstance(current_summary.get("progress"), dict)
                                    else {}
                                ),
                                "step_key": "failed",
                            },
                            "updated_at": now.isoformat(),
                        }
                    ),
                    error_message=_safe_text(error_message),
                    finished_at=now,
                    updated_at=now,
                )
            )
            session.commit()
            self.refresh_parent_batch_job(parent_job_id=parent_job_id)
        finally:
            session.close()

    def export_batch_job_workbook(self, *, job: Dict[str, Any]) -> BytesIO:
        if _is_luxian_0609_export_job(job):
            return _export_customer_safe_workbook(
                job,
                hmac_key=customer_safe_projection_key(),
            )
        return self._export_batch_job_workbook_legacy(job=job)

    def _export_batch_job_workbook_legacy(self, *, job: Dict[str, Any]) -> BytesIO:
        from openpyxl import Workbook

        output = BytesIO()
        workbook = Workbook()
        summary = job.get("summary") or {}
        items = job.get("items") or []
        failed_records = job.get("failed_records") or []
        status_breakdown = summary.get("status_breakdown") or {}
        rule_name_map: Dict[str, str] = {}
        for rr in summary.get("rule_results") or []:
            if not isinstance(rr, dict):
                continue
            rule_code = _safe_text(rr.get("rule_code"))
            rule_name = _safe_text(rr.get("rule_name"))
            if rule_code and rule_name:
                rule_name_map[rule_code] = rule_name

        issue_items: List[Dict[str, Any]] = []
        for item in items:
            status_key = _safe_text((item or {}).get("status")).lower()
            is_compliant = (item or {}).get("is_compliant")
            if status_key in {"non_compliant", "ai_suggested_non_compliant", "uncertain"} or is_compliant is False:
                issue_items.append(item or {})

        # 1) 管理摘要（面向行政管理）
        ws_summary = workbook.active
        ws_summary.title = "管理摘要"
        ws_summary.append(["报告项", "内容"])
        summary_rows = [
            ("任务编号", _safe_text(job.get("id"), "-")),
            ("任务名称", _safe_text(job.get("rule_name"), "终末病历批量质控任务")),
            ("规则集", _safe_text(summary.get("rule_set_name") or (job.get("filters") or {}).get("rule_set_name"), "手工选择规则")),
            ("执行策略", _safe_text(summary.get("quality_profile") or (job.get("filters") or {}).get("quality_profile"), "-")),
            ("分桶策略", _safe_text(summary.get("bucket_strategy") or (job.get("filters") or {}).get("bucket_strategy"), "-")),
            ("精审规则数", _to_int(summary.get("refined_rule_count"))),
            ("适用场景", _map_scene_label(job.get("scene"))),
            ("覆盖范围", _map_scope_label(job.get("scope"))),
            ("当前状态", _map_job_status_label(job.get("status"))),
            ("发起时间", str(job.get("created_at") or "-")),
            ("开始执行时间", str(job.get("started_at") or "-")),
            ("完成时间", str(job.get("finished_at") or "-")),
            ("筛选范围说明", _build_filter_text(job.get("filters") or {})),
            ("纳入病历数", _to_int(summary.get("total_records"), _to_int(job.get("total_records")))),
            ("完成病历数", _to_int(summary.get("success_count"), _to_int(job.get("success_count")))),
            ("执行失败病历数", _to_int(summary.get("failed_record_count"), _to_int(job.get("failed_count")))),
            ("发现问题病历数", _to_int(summary.get("issue_records"), _to_int(job.get("issue_records")))),
            ("AI判断病历数", _to_int(summary.get("uncertain_records"), _to_int(status_breakdown.get("uncertain")))),
            ("合规病历数", _to_int(summary.get("compliant_records"), _to_int(job.get("compliant_records")))),
            ("执行规则数", _to_int(summary.get("rule_count"), 1)),
        ]
        for label, value in summary_rows:
            ws_summary.append([label, value])
        ws_summary.column_dimensions["A"].width = 24
        ws_summary.column_dimensions["B"].width = 80

        # 2) 问题明细（业务重点）
        ws_items = workbook.create_sheet("问题明细")
        ws_items.append(
            [
                "病历号",
                "患者姓名",
                "科室",
                "质控点编码",
                "质控点名称",
                "文书域",
                "规则族",
                "判定结果",
                "问题结论",
                "整改建议",
                "证据摘要",
                "置信度",
                "是否精审",
            ]
        )
        for item in issue_items:
            ws_items.append(
                [
                    item.get("record_id") or "",
                    item.get("patient_name") or "",
                    item.get("department") or "",
                    item.get("rule_code") or "",
                    item.get("rule_name") or rule_name_map.get(_safe_text(item.get("rule_code")), ""),
                    item.get("document_type") or "",
                    item.get("rule_family") or "",
                    _map_item_status_label(item.get("status"), item.get("is_compliant")),
                    item.get("findings") or "",
                    item.get("suggestion") or "",
                    item.get("evidence") or "",
                    _to_float(item.get("confidence"), 0.0),
                    "是" if item.get("refined") is True else "否",
                ]
            )
        ws_items.freeze_panes = "A2"
        ws_items.column_dimensions["A"].width = 16
        ws_items.column_dimensions["B"].width = 14
        ws_items.column_dimensions["C"].width = 14
        ws_items.column_dimensions["D"].width = 12
        ws_items.column_dimensions["E"].width = 32
        ws_items.column_dimensions["F"].width = 16
        ws_items.column_dimensions["G"].width = 20
        ws_items.column_dimensions["H"].width = 10
        ws_items.column_dimensions["I"].width = 42
        ws_items.column_dimensions["J"].width = 38
        ws_items.column_dimensions["K"].width = 38
        ws_items.column_dimensions["L"].width = 10
        ws_items.column_dimensions["M"].width = 10

        # 3) 全部明细（含合规、AI判断、不合规）
        ws_all = workbook.create_sheet("全部明细")
        ws_all.append(
            [
                "病历号",
                "患者姓名",
                "科室",
                "质控点编码",
                "质控点名称",
                "文书域",
                "规则族",
                "判定结果",
                "是否合规",
                "问题结论",
                "整改建议",
                "证据摘要",
                "置信度",
                "是否精审",
            ]
        )
        for item in items:
            ws_all.append(
                [
                    item.get("record_id") or "",
                    item.get("patient_name") or "",
                    item.get("department") or "",
                    item.get("rule_code") or "",
                    item.get("rule_name") or rule_name_map.get(_safe_text(item.get("rule_code")), ""),
                    item.get("document_type") or "",
                    item.get("rule_family") or "",
                    _map_item_status_label(item.get("status"), item.get("is_compliant")),
                    "是" if item.get("is_compliant") is True else "否",
                    item.get("findings") or "",
                    item.get("suggestion") or "",
                    item.get("evidence") or "",
                    _to_float(item.get("confidence"), 0.0),
                    "是" if item.get("refined") is True else "否",
                ]
            )
        ws_all.freeze_panes = "A2"

        # 4) 失败明细
        ws_failed = workbook.create_sheet("失败明细")
        ws_failed.append(["病历号", "患者姓名", "科室", "失败原因"])
        for item in failed_records:
            ws_failed.append(
                [
                    item.get("record_id") or "",
                    item.get("patient_name") or "",
                    item.get("department") or "",
                    item.get("error") or "",
                ]
            )
        ws_failed.freeze_panes = "A2"
        ws_failed.column_dimensions["A"].width = 16
        ws_failed.column_dimensions["B"].width = 14
        ws_failed.column_dimensions["C"].width = 14
        ws_failed.column_dimensions["D"].width = 64

        # 5) 技术信息（默认不看，给研发定位问题）
        ws_tech = workbook.create_sheet("技术信息")
        ws_tech.append(["技术字段", "值"])
        performance_profile = _normalize_export_performance_profile(summary, job)
        tech_rows = [
            ("任务ID", _safe_text(job.get("id"), "-")),
            ("规则编码", _safe_text(job.get("rule_code"), "-")),
            ("规则集(raw)", _safe_text(summary.get("rule_set_key") or (job.get("filters") or {}).get("rule_set_key"), "-")),
            ("精审摘要(raw)", _safe_json_dumps(summary.get("refine_summary") or {})),
            ("场景(raw)", _safe_text(job.get("scene"), "-")),
            ("范围(raw)", _safe_text(job.get("scope"), "-")),
            ("状态(raw)", _safe_text(job.get("status"), "-")),
            ("总 token", performance_profile["tokens_total"]),
            ("输入 token", performance_profile["prompt_tokens"]),
            ("输出 token", performance_profile["completion_tokens"]),
            ("未归因 token", performance_profile["unattributed_tokens"]),
            ("token 拆分完整", "是" if performance_profile["token_breakdown_complete"] else "否"),
            ("总耗时(秒)", round(_to_float(summary.get("total_processing_time"), _to_float(job.get("total_processing_time"))), 4)),
            ("筛选条件(raw)", _safe_json_dumps(job.get("filters") or {})),
            ("summary(raw)", _safe_json_dumps(summary)),
        ]
        for label, value in tech_rows:
            ws_tech.append([label, value])
        ws_tech.column_dimensions["A"].width = 24
        ws_tech.column_dimensions["B"].width = 96

        workbook.save(output)
        output.seek(0)
        return output

    def export_batch_job_csv(self, *, job: Dict[str, Any]) -> StringIO:
        if _is_luxian_0609_export_job(job):
            return _export_customer_safe_csv(
                job,
                hmac_key=customer_safe_projection_key(),
            )
        return self._export_batch_job_csv_legacy(job=job)

    def _export_batch_job_csv_legacy(self, *, job: Dict[str, Any]) -> StringIO:
        import csv

        output = StringIO()
        writer = csv.writer(output)
        summary = job.get("summary") or {}
        items = job.get("items") or []
        rule_name_map: Dict[str, str] = {}
        for rr in summary.get("rule_results") or []:
            if not isinstance(rr, dict):
                continue
            rule_code = _safe_text(rr.get("rule_code"))
            rule_name = _safe_text(rr.get("rule_name"))
            if rule_code and rule_name:
                rule_name_map[rule_code] = rule_name
        issue_items: List[Dict[str, Any]] = []
        for item in items:
            status_key = _safe_text((item or {}).get("status")).lower()
            is_compliant = (item or {}).get("is_compliant")
            if status_key in {"non_compliant", "ai_suggested_non_compliant", "uncertain"} or is_compliant is False:
                issue_items.append(item or {})

        writer.writerow(["管理摘要"])
        writer.writerow(["任务编号", _safe_text(job.get("id"), "-")])
        writer.writerow(["任务名称", _safe_text(job.get("rule_name"), "终末病历批量质控任务")])
        writer.writerow(["规则集", _safe_text(summary.get("rule_set_name") or (job.get("filters") or {}).get("rule_set_name"), "手工选择规则")])
        writer.writerow(["执行策略", _safe_text(summary.get("quality_profile") or (job.get("filters") or {}).get("quality_profile"), "-")])
        writer.writerow(["分桶策略", _safe_text(summary.get("bucket_strategy") or (job.get("filters") or {}).get("bucket_strategy"), "-")])
        writer.writerow(["精审规则数", _to_int(summary.get("refined_rule_count"))])
        writer.writerow(["适用场景", _map_scene_label(job.get("scene"))])
        writer.writerow(["覆盖范围", _map_scope_label(job.get("scope"))])
        writer.writerow(["当前状态", _map_job_status_label(job.get("status"))])
        writer.writerow(["纳入病历数", _to_int(summary.get("total_records"), _to_int(job.get("total_records")))])
        writer.writerow(["发现问题病历数", _to_int(summary.get("issue_records"), _to_int(job.get("issue_records")))])
        writer.writerow(["AI判断病历数", _to_int(summary.get("uncertain_records"))])
        writer.writerow(["合规病历数", _to_int(summary.get("compliant_records"), _to_int(job.get("compliant_records")))])
        writer.writerow(["执行规则数", _to_int(summary.get("rule_count"), 1)])
        writer.writerow([])
        writer.writerow(["问题明细"])
        writer.writerow(["病历号", "患者姓名", "科室", "质控点编码", "质控点名称", "文书域", "规则族", "判定结果", "问题结论", "整改建议", "证据摘要", "置信度", "是否精审"])
        for item in issue_items:
            writer.writerow([
                item.get("record_id") or "",
                item.get("patient_name") or "",
                item.get("department") or "",
                item.get("rule_code") or "",
                item.get("rule_name") or rule_name_map.get(_safe_text(item.get("rule_code")), ""),
                item.get("document_type") or "",
                item.get("rule_family") or "",
                _map_item_status_label(item.get("status"), item.get("is_compliant")),
                item.get("findings") or "",
                item.get("suggestion") or "",
                item.get("evidence") or "",
                _to_float(item.get("confidence"), 0.0),
                "是" if item.get("refined") is True else "否",
            ])
        writer.writerow([])
        writer.writerow(["失败明细"])
        writer.writerow(["病历号", "患者姓名", "科室", "失败原因"])
        for item in job.get("failed_records") or []:
            writer.writerow([
                item.get("record_id") or "",
                item.get("patient_name") or "",
                item.get("department") or "",
                item.get("error") or "",
            ])
        output.seek(0)
        return output

    def _load_batch_job_canonical_items(
        self,
        *,
        job: Dict[str, Any],
        session_factory: Optional[Callable[[], Session]] = None,
    ) -> List[Dict[str, Any]]:
        """按任务身份一次读取 Canonical Envelope，禁止回退任务明细。"""

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
        if total_records > 0 and (
            not expected_refs or len(expected_refs) != total_records
        ):
            raise ValueError("批量质控任务缺少完整的冻结病历范围")

        session = (session_factory or _session)()
        try:
            envelope_rows = (
                session.execute(
                    select(self._record_result_envelope_table).where(
                        and_(
                            self._record_result_envelope_table.c.root_job_id == job_id,
                            self._record_result_envelope_table.c.created_by == created_by,
                            self._record_result_envelope_table.c.rule_set_key == rule_set_key,
                            self._record_result_envelope_table.c.rule_set_version == rule_set_version,
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
                or envelope.get("schema_version") != _RECORD_RESULT_ENVELOPE_SCHEMA
                or envelope.get("delivery_mode") != _CANONICAL_RESULT_DELIVERY_MODE
                or _safe_text(envelope.get("root_job_id")) != job_id
                or not isinstance(envelope.get("items"), list)
            ):
                raise ValueError("批量质控 Canonical Envelope 结构无效")
            record_ref = _safe_text(envelope.get("record_ref"))
            if not re.fullmatch(r"rec_[0-9a-f]{24}", record_ref):
                raise ValueError("批量质控 Canonical Envelope 病历引用无效")
            if not _canonical_envelope_items_are_consistent(envelope["items"]):
                raise ValueError("canonical_result_envelope_invalid")
            for raw_item in envelope["items"]:
                canonical_items.append({**raw_item, "record_ref": record_ref})

        actual_refs = set(rows_by_ref)
        if expected_refs and actual_refs != expected_refs:
            raise ValueError("批量质控 Canonical Envelope 病历集合不完整")
        if not envelope_rows and int(job.get("total_records") or 0) > 0:
            raise ValueError("批量质控 Canonical Envelope 缺失")
        return canonical_items

    def export_batch_job_html(self, *, job: Dict[str, Any]) -> str:
        if _is_luxian_0609_export_job(job):
            return _export_customer_safe_html(
                job,
                hmac_key=customer_safe_projection_key(),
                canonical_items=self._load_batch_job_canonical_items(job=job),
            )
        return self._export_batch_job_html_legacy(job=job)

    def _export_batch_job_html_legacy(self, *, job: Dict[str, Any]) -> str:
        summary = job.get("summary") if isinstance(job.get("summary"), dict) else {}
        filters = job.get("filters") if isinstance(job.get("filters"), dict) else {}
        child_jobs = job.get("child_jobs") or job.get("children") or []
        export_jobs = [child for child in child_jobs if isinstance(child, dict)] or [job]

        all_items: List[Dict[str, Any]] = []
        failed_records: List[Dict[str, Any]] = []
        for source_job in export_jobs:
            for item in source_job.get("items") or []:
                if isinstance(item, dict):
                    all_items.append(item)
            for item in source_job.get("failed_records") or []:
                if isinstance(item, dict):
                    failed_records.append(item)

        status_counts: Dict[str, int] = {}
        for source in (
            summary.get("display_status_counts"),
            summary.get("status_breakdown"),
        ):
            if isinstance(source, dict):
                for key, value in source.items():
                    status_counts[_safe_text(key).lower()] = status_counts.get(_safe_text(key).lower(), 0) + _to_int(value)
        if not status_counts:
            for item in all_items:
                key = _export_item_status_key(item)
                status_counts[key] = status_counts.get(key, 0) + 1

        record_groups: Dict[str, Dict[str, Any]] = {}
        for item in all_items:
            record_id = _safe_text(item.get("record_id") or item.get("visit_id") or item.get("mr_no") or "未返回病历号")
            group = record_groups.setdefault(
                record_id,
                {
                    "record_id": record_id,
                    "patient_name": _safe_text(item.get("patient_name"), "-"),
                    "department": _safe_text(item.get("department"), "-"),
                    "items": [],
                    "status_counts": {},
                },
            )
            if group.get("patient_name") in {"", "-"} and _safe_text(item.get("patient_name")):
                group["patient_name"] = _safe_text(item.get("patient_name"))
            if group.get("department") in {"", "-"} and _safe_text(item.get("department")):
                group["department"] = _safe_text(item.get("department"))
            group["items"].append(item)
            status_key = _export_item_status_key(item)
            group["status_counts"][status_key] = group["status_counts"].get(status_key, 0) + 1

        status_order = [
            "non_compliant",
            "ai_suggested_non_compliant",
            "data_gap",
            "uncertain",
            "not_executed",
            "technical_error",
            "not_applicable",
            "ai_suggested_compliant",
            "compliant",
        ]
        status_cards = []
        for key in status_order:
            value = _to_int(status_counts.get(key))
            status_cards.append(
                f'<div class="metric metric-{_status_tone_class(key)}"><span>{_html_escape(_map_item_status_label(key, None))}</span><strong>{value}</strong></div>'
            )

        selected_rule_ids = (
            filters.get("selected_rule_ids")
            or filters.get("scoped_customer_rule_ids")
            or summary.get("selected_rule_ids")
            or summary.get("scoped_customer_rule_ids")
            or []
        )
        customer_rule_count = _to_int(
            job.get("customer_rule_count"),
            _to_int(summary.get("customer_rule_count"), _to_int(summary.get("rule_count"), _to_int(job.get("rule_count")))),
        )
        execution_rule_count = _to_int(
            job.get("execution_rule_count"),
            _to_int(summary.get("execution_rule_count"), _to_int(summary.get("rule_count"), _to_int(job.get("rule_count")))),
        )
        total_records = _to_int(summary.get("total_records"), _to_int(job.get("total_records"), len(record_groups)))
        rule_set_name = _safe_text(
            summary.get("rule_set_name") or filters.get("rule_set_name") or job.get("rule_set_name") or job.get("rule_name"),
            "质控任务",
        )
        generated_at = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
        performance_profile = _normalize_export_performance_profile(summary, job)
        performance_block = (
            '<div class="performance-metrics">'
            f'<div class="performance-metric"><span>总 Token</span><strong>{_format_export_integer(performance_profile["tokens_total"])}</strong></div>'
            f'<div class="performance-metric"><span>输入 Token</span><strong>{_format_export_integer(performance_profile["prompt_tokens"])}</strong></div>'
            f'<div class="performance-metric"><span>输出 Token</span><strong>{_format_export_integer(performance_profile["completion_tokens"])}</strong></div>'
            f'<div class="performance-metric performance-metric-warn"><span>未归因 Token</span><strong>{_format_export_integer(performance_profile["unattributed_tokens"])}</strong></div>'
            f'<div class="performance-metric"><span>Token 拆分</span><strong>{"完整" if performance_profile["token_breakdown_complete"] else "有未归因"}</strong></div>'
            "</div>"
            '<p class="performance-note">未归因 Token 表示模型服务返回了总量，但未能拆分到输入或输出的部分；用于性能剖析和成本排查。</p>'
        )

        toc_rows = []
        record_sections = []
        for index, group in enumerate(record_groups.values(), start=1):
            anchor = f"record-{index}"
            issue_count = sum(
                _to_int(group["status_counts"].get(key))
                for key in (
                    "non_compliant",
                    "ai_suggested_non_compliant",
                    "data_gap",
                    "uncertain",
                    "not_executed",
                    "technical_error",
                )
            )
            toc_rows.append(
                "<tr>"
                f'<td><a href="#{anchor}">{_html_escape(group.get("record_id"))}</a></td>'
                f"<td>{_html_escape(group.get('patient_name'))}</td>"
                f"<td>{_html_escape(group.get('department'))}</td>"
                f"<td>{len(group.get('items') or [])}</td>"
                f"<td>{issue_count}</td>"
                "</tr>"
            )

            item_cards = []
            sorted_items = sorted(
                group.get("items") or [],
                key=lambda item: (
                    0
                    if _export_item_status_key(item)
                    in {
                        "non_compliant",
                        "ai_suggested_non_compliant",
                        "data_gap",
                        "uncertain",
                        "technical_error",
                        "not_executed",
                    }
                    else 1,
                    _safe_text(item.get("rule_code")),
                ),
            )
            for item in sorted_items:
                status_key = _export_item_status_key(item)
                status_label = _map_item_status_label(status_key, item.get("is_compliant"))
                conclusion = _sanitize_export_text(item.get("findings") or item.get("conclusion") or item.get("summary"), 520)
                suggestion = _sanitize_export_text(item.get("suggestion") or item.get("recommendation"), 360)
                evidence_part_rows = []
                for part in _parse_export_evidence_parts(item.get("evidence")):
                    evidence_part_rows.append(
                        '<div class="evidence-fact">'
                        f"<span>{_html_escape(part.get('label') or '-')}</span>"
                        f"<strong>{_html_escape(part.get('value') or '-')}</strong>"
                        "</div>"
                    )
                evidence_rows = []
                for evidence in _extract_structured_evidence(item):
                    evidence_rows.append(
                        "<div class=\"evidence-row\">"
                        f"<div><span>来源</span><strong>{_html_escape(evidence.get('source') or '-')}</strong></div>"
                        f"<div><span>字段</span><strong>{_html_escape(evidence.get('field') or '-')}</strong></div>"
                        f"<div class=\"evidence-quote\"><span>片段</span><strong>{_html_escape(evidence.get('quote') or '-')}</strong></div>"
                        f"<div><span>阈值</span><strong>{_html_escape(evidence.get('threshold') or '-')}</strong></div>"
                        f"<div><span>实际</span><strong>{_html_escape(evidence.get('actual') or '-')}</strong></div>"
                        f"<div><span>差值</span><strong>{_html_escape(evidence.get('delta') or '-')}</strong></div>"
                        "</div>"
                    )
                if not evidence_rows and not evidence_part_rows:
                    legacy_evidence = _sanitize_export_text(
                        item.get("evidence")
                        or item.get("evidence_text")
                        or item.get("evidence_summary")
                        or item.get("quote"),
                        520,
                    )
                    if legacy_evidence:
                        evidence_rows.append(f'<p class="legacy-evidence">{_html_escape(legacy_evidence)}</p>')
                    else:
                        evidence_rows.append('<p class="legacy-evidence muted">未返回可导出的证据摘要。</p>')
                missing_sources = item.get("missing_sources") or item.get("missing_fields") or item.get("data_gap")
                missing_text = ""
                if isinstance(missing_sources, list):
                    missing_text = "、".join(_safe_text(value) for value in missing_sources if _safe_text(value))
                elif missing_sources:
                    missing_text = _safe_text(missing_sources)
                missing_block = (
                    f'<div class="missing-block">缺失字段/来源：{_html_escape(_truncate_export_text(missing_text, 220))}</div>'
                    if missing_text
                    else ""
                )
                item_cards.append(
                    f'<article class="issue-card issue-{_status_tone_class(status_key)}">'
                    '<div class="issue-head">'
                    f"<h4>{_html_escape(item.get('rule_code'))} · {_html_escape(item.get('rule_name'))}</h4>"
                    f'<span class="status-pill status-{_status_tone_class(status_key)}">{_html_escape(status_label)}</span>'
                    "</div>"
                    '<div class="issue-meta">'
                    f"<span>{_html_escape(item.get('document_type') or '文书未标注')}</span>"
                    f"<span>{_html_escape(item.get('defect_level') or '缺陷等级未标注')}</span>"
                    f"<span>复核状态：{_html_escape(item.get('review_status') or '未处理')}</span>"
                    "</div>"
                    '<div class="issue-grid">'
                    f'<section><label>质控结论</label><p>{_html_escape(conclusion or "-")}</p></section>'
                    f'<section><label>关键证据</label>{"".join(evidence_part_rows)}{"".join(evidence_rows)}{missing_block}</section>'
                    f'<section><label>处理建议</label><p>{_html_escape(suggestion or "请结合病历原文确认。")}</p></section>'
                    "</div>"
                    "</article>"
                )

            record_sections.append(
                f'<section id="{anchor}" class="record-section">'
                '<div class="record-head">'
                "<div>"
                f"<h3>{_html_escape(group.get('record_id'))} · {_html_escape(group.get('patient_name'))}</h3>"
                f"<p>{_html_escape(group.get('department'))} · {len(group.get('items') or [])} 条质控结果</p>"
                "</div>"
                f'<span class="record-issue-count">需关注 {issue_count}</span>'
                "</div>"
                f"{''.join(item_cards)}"
                "</section>"
            )

        if not record_sections:
            record_sections.append('<section class="empty-state">当前任务暂无可导出的质控明细。</section>')

        review_block = ""
        review_report = summary.get("review_report") if isinstance(summary.get("review_report"), dict) else {}
        if review_report:
            review_summary = review_report.get("summary") if isinstance(review_report.get("summary"), dict) else {}
            review_findings = review_report.get("findings") if isinstance(review_report.get("findings"), list) else []
            review_rows = []
            for finding in review_findings[:12]:
                if not isinstance(finding, dict):
                    continue
                review_rows.append(
                    "<tr>"
                    f"<td>{_html_escape(finding.get('severity') or '-')}</td>"
                    f"<td>{_html_escape(finding.get('record_id') or '-')}</td>"
                    f"<td>{_html_escape(finding.get('rule_id') or '-')}</td>"
                    f"<td>{_html_escape(_sanitize_export_text(finding.get('customer_message') or finding.get('reason'), 220))}</td>"
                    f"<td>{_html_escape(_map_item_status_label(finding.get('suggested_status'), None))}</td>"
                    "</tr>"
                )
            review_table_html = (
                '<table class="review-table"><thead><tr><th>级别</th><th>病历</th><th>质控点</th><th>复核建议</th><th>建议口径</th></tr></thead>'
                f"<tbody>{''.join(review_rows)}</tbody></table>"
                if review_rows
                else '<p class="muted">已完成复核，暂无高风险复核建议。</p>'
            )
            review_block = (
                '<section class="panel review-section"><h2>结果复核建议</h2>'
                '<div class="review-summary">'
                f"<span>建议总数 <strong>{_to_int(review_summary.get('total_findings'))}</strong></span>"
                f"<span>P0 <strong>{_to_int(review_summary.get('p0'))}</strong></span>"
                f"<span>P1 <strong>{_to_int(review_summary.get('p1'))}</strong></span>"
                f"<span>P2 <strong>{_to_int(review_summary.get('p2'))}</strong></span>"
                "</div>"
                f"{review_table_html}</section>"
            )

        failed_block = ""
        if failed_records:
            failed_rows = []
            for item in failed_records:
                failed_rows.append(
                    "<tr>"
                    f"<td>{_html_escape(item.get('record_id') or item.get('visit_id'))}</td>"
                    f"<td>{_html_escape(item.get('patient_name'))}</td>"
                    f"<td>{_html_escape(item.get('department'))}</td>"
                    f"<td>{_html_escape(_sanitize_export_text(item.get('error'), 240))}</td>"
                    "</tr>"
                )
            failed_block = (
                '<section class="failed-section"><h2>执行失败病历</h2>'
                '<table><thead><tr><th>病历号</th><th>患者</th><th>科室</th><th>失败原因</th></tr></thead>'
                f"<tbody>{''.join(failed_rows)}</tbody></table></section>"
            )

        html_text = f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>{_html_escape(rule_set_name)} - 质控明细</title>
  <style>
    body {{ margin: 0; background: #f5f5f7; color: #1d1d1f; font-family: "Source Han Sans SC", "Microsoft YaHei UI", "Microsoft YaHei", system-ui, sans-serif; }}
    .page {{ max-width: 1180px; margin: 0 auto; padding: 28px; }}
    .hero, .panel, .record-section, .failed-section {{ border: 1px solid rgba(0,0,0,.08); border-radius: 18px; background: rgba(255,255,255,.94); box-shadow: 0 10px 30px rgba(15,23,42,.06); }}
    .hero {{ padding: 24px; }}
    .eyebrow {{ margin: 0 0 8px; color: rgba(29,29,31,.58); font-size: 13px; }}
    h1 {{ margin: 0; font-size: 26px; line-height: 34px; }}
    h2 {{ margin: 0 0 14px; font-size: 18px; }}
    h3 {{ margin: 0; font-size: 17px; }}
    h4 {{ margin: 0; font-size: 15px; line-height: 22px; }}
    .hero-meta, .issue-meta {{ display: flex; flex-wrap: wrap; gap: 8px; margin-top: 14px; color: rgba(29,29,31,.62); font-size: 13px; }}
    .hero-meta span, .issue-meta span {{ border-radius: 999px; background: #f3f6fb; padding: 5px 10px; }}
    .metrics {{ display: grid; grid-template-columns: repeat(7, minmax(0, 1fr)); gap: 10px; margin-top: 18px; }}
    .metric {{ border-radius: 14px; border: 1px solid rgba(0,0,0,.08); padding: 12px; background: #fff; }}
    .metric span {{ display: block; color: rgba(29,29,31,.56); font-size: 12px; }}
    .metric strong {{ display: block; margin-top: 6px; font-size: 22px; }}
    .metric-danger strong {{ color: #dc2626; }} .metric-warning strong {{ color: #b45309; }} .metric-success strong {{ color: #0066cc; }}
    .performance-metrics {{ display: grid; grid-template-columns: repeat(5, minmax(0, 1fr)); gap: 10px; margin-top: 14px; }}
    .performance-metric {{ border-radius: 14px; border: 1px solid #dbe5f3; background: #f8fafc; padding: 10px 12px; }}
    .performance-metric span {{ display: block; color: rgba(29,29,31,.56); font-size: 12px; }}
    .performance-metric strong {{ display: block; margin-top: 5px; font-size: 18px; }}
    .performance-metric-warn strong {{ color: #b45309; }}
    .performance-note {{ margin: 8px 0 0; color: rgba(29,29,31,.56); font-size: 12px; line-height: 20px; }}
    .panel, .failed-section {{ margin-top: 18px; padding: 18px; }}
    .review-section {{ border-color: #bfdbfe; background: #f8fbff; }}
    .review-summary {{ display: flex; flex-wrap: wrap; gap: 8px; margin-bottom: 12px; }}
    .review-summary span {{ border-radius: 999px; background: #eff6ff; color: #1d4ed8; padding: 6px 10px; font-size: 13px; }}
    .review-summary strong {{ margin-left: 4px; }}
    table {{ width: 100%; border-collapse: collapse; font-size: 13px; }}
    th, td {{ border-bottom: 1px solid rgba(0,0,0,.08); padding: 10px 8px; text-align: left; vertical-align: top; }}
    th {{ color: rgba(29,29,31,.58); font-weight: 700; }}
    a {{ color: #0066cc; text-decoration: none; }}
    .record-section {{ margin-top: 18px; padding: 18px; scroll-margin-top: 18px; }}
    .record-head {{ display: flex; justify-content: space-between; gap: 16px; align-items: flex-start; margin-bottom: 14px; }}
    .record-head p {{ margin: 6px 0 0; color: rgba(29,29,31,.58); }}
    .record-issue-count {{ border-radius: 999px; background: #fff7ed; color: #b45309; padding: 6px 10px; font-size: 13px; font-weight: 700; }}
    .issue-card {{ border: 1px solid rgba(0,0,0,.08); border-left-width: 5px; border-radius: 14px; background: #fff; padding: 14px; margin-top: 12px; }}
    .issue-danger {{ border-left-color: #ef4444; }} .issue-warning {{ border-left-color: #f59e0b; }} .issue-success {{ border-left-color: #0066cc; }} .issue-neutral, .issue-muted {{ border-left-color: #94a3b8; }}
    .issue-head {{ display: flex; justify-content: space-between; gap: 12px; align-items: flex-start; }}
    .status-pill {{ flex: 0 0 auto; border-radius: 999px; padding: 4px 9px; font-size: 12px; font-weight: 700; }}
    .status-danger {{ background: #fef2f2; color: #dc2626; }} .status-warning {{ background: #fff7ed; color: #b45309; }} .status-success {{ background: #eaf2ff; color: #0066cc; }} .status-neutral, .status-muted {{ background: #f1f5f9; color: #475569; }}
    .issue-grid {{ display: grid; grid-template-columns: 1fr 1.25fr 1fr; gap: 12px; margin-top: 12px; }}
    section label {{ display: block; margin-bottom: 6px; color: rgba(29,29,31,.58); font-size: 12px; font-weight: 700; }}
    section p {{ margin: 0; font-size: 13px; line-height: 21px; }}
    .evidence-fact {{ display: grid; grid-template-columns: 96px minmax(0, 1fr); gap: 10px; align-items: center; border: 1px solid #d7e7ff; border-radius: 10px; background: #f3f8ff; padding: 8px 10px; font-size: 12px; }}
    .evidence-fact + .evidence-fact, .evidence-fact + .evidence-row, .evidence-fact + .legacy-evidence {{ margin-top: 8px; }}
    .evidence-fact span {{ color: #375f8f; font-weight: 600; }}
    .evidence-fact strong {{ color: #111827; font-weight: 700; line-height: 18px; }}
    .evidence-row {{ display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 8px; border-radius: 12px; background: #f8fafc; padding: 10px; font-size: 12px; }}
    .evidence-row + .evidence-row {{ margin-top: 8px; }}
    .evidence-row span {{ display: block; color: rgba(29,29,31,.52); }}
    .evidence-row strong {{ display: block; margin-top: 3px; font-weight: 600; line-height: 18px; }}
    .evidence-quote {{ grid-column: span 3; }}
    .legacy-evidence {{ border-radius: 12px; background: #f8fafc; padding: 10px; }}
    .missing-block {{ margin-top: 8px; border-radius: 10px; background: #fff7ed; color: #9a3412; padding: 8px 10px; font-size: 12px; }}
    .notice {{ margin-top: 18px; color: rgba(29,29,31,.58); font-size: 12px; line-height: 20px; }}
    .empty-state {{ margin-top: 18px; border-radius: 16px; background: #fff; padding: 28px; color: rgba(29,29,31,.58); text-align: center; }}
    @media print {{ .page {{ padding: 0; }} .hero, .panel, .record-section, .failed-section {{ box-shadow: none; }} }}
  </style>
</head>
<body>
  <main class="page">
    <section class="hero">
      <p class="eyebrow">质控明细导出 · 生成时间 {generated_at}</p>
      <h1>{_html_escape(rule_set_name)}</h1>
      <div class="hero-meta">
        <span>任务ID：{_html_escape(job.get("id"))}</span>
        <span>状态：{_html_escape(_map_job_status_label(job.get("status")))}</span>
        <span>病历数：{total_records}</span>
        <span>客户质控点数：{customer_rule_count}</span>
        <span>底层执行规则数：{execution_rule_count}</span>
        <span>选择质控点：{_html_escape(_format_rule_code_list(selected_rule_ids))}</span>
      </div>
      <div class="metrics">{"".join(status_cards)}</div>
      {performance_block}
      <p class="notice">本文件仅用于质控明细查看和质控确认，不作为病历归档、医保结算、绩效扣分或正式质控结论依据。文件不包含完整病历全文、模型原始输出或向量数据。</p>
    </section>

    <section class="panel">
      <h2>病历目录</h2>
      <table>
        <thead><tr><th>病历号</th><th>患者</th><th>科室</th><th>结果数</th><th>需关注</th></tr></thead>
        <tbody>{"".join(toc_rows) or '<tr><td colspan="5">暂无病历结果</td></tr>'}</tbody>
      </table>
    </section>

    {review_block}
    {"".join(record_sections)}
    {failed_block}
  </main>
</body>
</html>
"""
        return "\ufeff" + html_text

    def publish_draft(self, *, draft_id: str, created_by: str) -> Dict[str, Any]:
        session = _session()
        try:
            stmt = select(self._draft_table).where(
                and_(self._draft_table.c.id == draft_id, self._draft_table.c.created_by == created_by)
            )
            row = session.execute(stmt).mappings().first()
            if not row:
                raise ValueError("草稿不存在或无权限")

            draft = _row_to_draft(dict(row))
            last_test_summary = draft.get("last_test_summary") or {}
            success_count = 0
            if isinstance(last_test_summary, dict):
                success_count = int(last_test_summary.get("success_count") or 0)
            if success_count <= 0:
                raise ValueError("请至少完成一次成功测试后再发布")

            qc_rules_table = _qc_rules_table()
            now = _now_utc()
            draft_check_logic = dict(draft.get("check_logic") or {})
            aligned_document_type, aligned_applicable_documents, aligned_check_logic = align_document_domain_fields(
                document_type=draft.get("document_type"),
                applicable_documents=draft.get("applicable_documents"),
                check_logic=draft_check_logic,
            )
            check_logic = {
                **aligned_check_logic,
                "source": "custom_rule_workspace",
                "workspace_draft_id": draft["id"],
                "applicable_documents": aligned_applicable_documents,
                "generation_mode": draft.get("generation_mode") or "fallback_template",
                "examples": draft.get("examples") or [],
                "last_test_summary": draft.get("last_test_summary"),
                "document_type": aligned_document_type,
                "scene": draft.get("scene"),
            }
            values: Dict[str, Any] = {
                "id": str(uuid.uuid4()),
                "rule_code": draft["rule_code"],
                "name": draft["name"],
                "description": draft["description"],
                "category": "consistency",
                "severity": draft.get("severity") or _map_defect_level_to_severity(draft.get("defect_level")),
                "rule_type": "semantic",
                "scope": "global",
                "status": "published",
                "version": "1.0",
                "priority": 0,
                "is_active": True,
                "prompt_template": draft.get("prompt_template"),
                "check_logic": check_logic,
                "applicable_documents": aligned_applicable_documents,
                "metadata": {
                    "source": "custom_rule_workspace",
                    "workspace_draft_id": draft["id"],
                },
                "created_by": created_by,
                "updated_by": created_by,
                "created_at": now,
                "updated_at": now,
            }

            existing_stmt = select(qc_rules_table).where(qc_rules_table.c.rule_code == draft["rule_code"]).limit(1)
            existing = session.execute(existing_stmt).mappings().first()
            filtered_values = {
                key: _value_for_column(qc_rules_table.c[key], value)
                for key, value in values.items()
                if key in qc_rules_table.c
            }
            if existing:
                session.execute(
                    update(qc_rules_table)
                    .where(qc_rules_table.c.rule_code == draft["rule_code"])
                    .values(**{k: v for k, v in filtered_values.items() if k != "id"})
                )
                published_rule_id = _safe_text(existing.get("id")) or draft["rule_code"]
            else:
                session.execute(qc_rules_table.insert().values(**filtered_values))
                inserted = session.execute(existing_stmt).mappings().first()
                published_rule_id = _safe_text((inserted or {}).get("id")) or draft["rule_code"]

            session.execute(
                update(self._draft_table)
                .where(and_(self._draft_table.c.id == draft_id, self._draft_table.c.created_by == created_by))
                .values(
                    status="published",
                    published_rule_id=published_rule_id,
                    updated_at=now,
                )
            )
            session.commit()
            return {
                "draft_id": draft_id,
                "rule_code": draft["rule_code"],
                "published_rule_id": published_rule_id,
                "status": "published",
            }
        finally:
            session.close()


# SQLAlchemy is imported lazily here to avoid polluting top-level namespace usage above.
