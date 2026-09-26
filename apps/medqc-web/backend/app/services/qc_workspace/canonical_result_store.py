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
from ..luxian_0609.canonical_result_finalizer import (
    validate_luxian_0609_published_customer_display_facts,
)
from ..luxian_0609.rule_contracts import CRITERION_KINDS
from ..luxian_0609_result_schema import (
    CANONICAL_RESULT_DELIVERY_MODE,
    CANONICAL_RESULT_STATUSES,
    CUSTOMER_SCHEMA_VERSION,
    RULE_SET_VERSION,
)
from ..luxian_0609_rule_catalog import (
    LUXIAN_0609_RULE_SET_KEY,
    get_luxian_0609_rule,
)


RECORD_RESULT_ENVELOPE_SCHEMA = "lx0609-record-result-envelope-v1"
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
# 运行时仍需保留这两种状态来表达执行/诊断失败，但正式 Canonical Envelope 不得交付。
_CANONICAL_UNDELIVERABLE_STATUSES = frozenset({"uncertain", "technical_error"})
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


LX0609_CUSTOMER_RESULT_CONTRACT_ERROR = (
    "LX0609 客户结果解释合同不完整，拒绝交付确定问题"
)
# 已取消的结果文案签章字段；历史 Envelope 中若存在，读取时丢弃。
_DEPRECATED_TEXT_SEAL_FIELD = "customer_text_seal"


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
        if rule_id.startswith("LX0609-"):
            # 正式结果只接收目录中的唯一新身份；历史转换在离线迁移完成。
            if get_luxian_0609_rule(rule_id) is None:
                return False
            if any(
                _safe_text(item.get(key)).upper() not in {"", rule_id}
                for key in ("rule_code", "qc_point_id", "customer_rule_id")
            ):
                return False
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
            or status in _CANONICAL_UNDELIVERABLE_STATUSES
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


def _assert_consistent_lx0609_rule_identity(item: Dict[str, Any]) -> None:
    """同一结果的 LX0609 规则身份字段必须指向同一规则，不能各取其一。"""

    identities = {
        _safe_text(item.get(key)).upper()
        for key in ("customer_rule_id", "qc_point_id", "rule_id", "rule_code")
    }
    if len({value for value in identities if value.startswith("LX0609-")}) > 1:
        raise ValueError(LX0609_CUSTOMER_RESULT_CONTRACT_ERROR)


def _envelope_visit_matches_row(envelope: Dict[str, Any], visit_id: str) -> bool:
    """Envelope 明文 record_id（保存时即本行 visit_id）须与数据库行一致。

    record_ref 是按保存时服务密钥生成的不可逆引用，读取时不以当前密钥重算，
    否则密钥轮换会使历史合法结果不可读；机构、患者层面的归属因此无法仅凭
    Envelope 独立证明，由行坐标与任务冻结病例集合约束。
    """

    return _safe_text(envelope.get("record_id")) == _safe_text(visit_id)


def safe_customer_display_facts(
    item: Dict[str, Any],
    *,
    rule_id: str,
) -> Dict[str, Any]:
    """仅透传 Finalizer 已验证的客户展示事实。"""

    _assert_consistent_lx0609_rule_identity(item)
    raw = item.get("customer_display_facts")
    has_result_status = any(
        _safe_text(item.get(key)) for key in ("status", "result_status", "display_status")
    ) or item.get("is_compliant") is not None
    shared = validate_luxian_0609_published_customer_display_facts(
        rule_id=rule_id,
        raw=raw,
        status=canonical_customer_status(item) if has_result_status else "",
        reason_code=_safe_text(item.get("reason_code")),
    )
    return dict(shared) if isinstance(shared, dict) else {}


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
            or kind not in CRITERION_KINDS
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


def envelope_item_from_rule_result(
    item: Dict[str, Any], *, hmac_key: str | None = None,
) -> Dict[str, Any]:
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

    if hmac_key is None:
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
        collect_receipts: bool = False,
        projection_key: str | None = None,
    ) -> tuple[tuple[CaseRef, str], ...]:
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
            envelope_record_ref = keyed_ref(
                "rec",
                record_ref.as_key(),
                hmac_key=(
                    projection_key
                    if projection_key is not None
                    else customer_safe_projection_key()
                ),
            )
            projected_items = []
            for item in record_items:
                projected_item = dict(projector(item))
                # 病历引用由 Envelope 的三坐标身份统一生成，不能由规则项只按 visit_id 另算。
                projected_item["record_ref"] = envelope_record_ref
                projected_items.append(projected_item)
            envelope = {
                "schema_version": RECORD_RESULT_ENVELOPE_SCHEMA,
                "delivery_mode": CANONICAL_RESULT_DELIVERY_MODE,
                "record_id": record_id,
                "record_ref": envelope_record_ref,
                "job_id": job_id,
                "root_job_id": root_job_id,
                "rule_set_key": rule_set_key,
                "rule_set_version": rule_set_version,
                "items": projected_items,
            }
            prepared_envelopes.append((record_ref, envelope))

        receipts: list[tuple[CaseRef, str]] = []
        receipt_bytes = 0
        for record_ref, envelope in prepared_envelopes:
            record_id = record_ref.visit_id
            envelope_json = _safe_json_dumps(envelope)
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
                    envelope_json=envelope_json,
                    result_count=len(envelope["items"]),
                    created_at=now,
                    updated_at=now,
                )
            )
            if collect_receipts:
                receipt_bytes += len(envelope_json.encode("utf-8"))
                if receipt_bytes <= 4 * 1024 * 1024:
                    receipts.append((record_ref, envelope_json))
                else:
                    # 提交前的诊断回执也必须有界；超限不影响正式保存，
                    # 丢弃整组以免残缺回执被误认为完整批次。
                    receipts.clear()
                    collect_receipts = False
        # 尚未 commit；只能由事务所有者在提交成功后交给诊断旁路。
        return tuple(receipts)

    def load_selected(
        self,
        session: Session,
        *,
        root_job_id: str,
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
                            table.c.root_job_id == root_job_id,
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
        # 保存时已校验不代表读取的行与 Envelope 仍属同一就诊；按明文 visit 复核。
        if not _envelope_visit_matches_row(envelope, visit_id):
            raise ValueError(LX0609_CUSTOMER_RESULT_CONTRACT_ERROR)
        for item in envelope["items"]:
            if not isinstance(item, dict):
                raise ValueError(LX0609_CUSTOMER_RESULT_CONTRACT_ERROR)
            # 历史结果可能带已废弃的文案签章字段：读取时丢弃，不校验、不外传。
            item.pop(_DEPRECATED_TEXT_SEAL_FIELD, None)
            rule_id = _safe_text(item.get("rule_id") or item.get("rule_code")).upper()
            safe_customer_display_facts(item, rule_id=rule_id)
        return envelope

    def load_root_job_items(
        self,
        *,
        job: Dict[str, Any],
        session_factory: Callable[[], Session],
        allow_partial: bool = False,
    ) -> List[Dict[str, Any]]:
        job_id = _safe_text(job.get("id"))
        created_by = _safe_text(job.get("created_by"))
        status = _safe_text(job.get("status"))
        summary = job.get("summary") if isinstance(job.get("summary"), dict) else {}
        is_partial_failure = (
            allow_partial
            and status == "failed"
            and _safe_text(summary.get("execution_status")) == "partial_failed"
        )
        if not job_id or not created_by or (status != "completed" and not is_partial_failure):
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
        case_by_record_ref: Dict[str, CaseRef] = {}
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
            if (
                not re.fullmatch(r"rec_[0-9a-f]{24}", record_ref)
                or not _envelope_visit_matches_row(envelope, case_ref.visit_id)
                # 同一任务内不同病例不得共用同一病历引用。
                or case_by_record_ref.setdefault(record_ref, case_ref) != case_ref
            ):
                raise ValueError("批量质控 Canonical Envelope 病历引用无效")
            if not canonical_envelope_items_are_consistent(envelope["items"]):
                raise ValueError("canonical_result_envelope_invalid")
            for raw_item in envelope["items"]:
                raw_item.pop(_DEPRECATED_TEXT_SEAL_FIELD, None)
                # Envelope 已通过 schema、delivery_mode 和逐项状态合同校验；
                # 旧候选包的条目级 schema 标记曾在批任务落盘时被遗漏。读取时
                # 只继承已验证的 Envelope 合同，不重新解释任何业务状态。
                normalized_item = {
                    **raw_item,
                    "schema_version": CUSTOMER_SCHEMA_VERSION,
                    "record_ref": record_ref,
                    # 保存时已移除病例坐标；读取时按本行补回，供客户投影既有的
                    # 本病例身份值过滤使用。投影输出不包含这些字段。
                    "institute_id": case_ref.institute_id,
                    "patient_id": case_ref.patient_id,
                    "visit_id": case_ref.visit_id,
                }
                if not _safe_text(normalized_item.get("rule_version")):
                    catalog_rule = get_luxian_0609_rule(
                        _safe_text(normalized_item.get("rule_id"))
                    )
                    if catalog_rule is not None:
                        normalized_item["rule_version"] = _safe_text(
                            catalog_rule.get("rule_version")
                        )
                canonical_items.append(normalized_item)

        actual_refs = set(rows_by_ref)
        if expected_refs and (
            (not is_partial_failure and actual_refs != expected_refs)
            or (is_partial_failure and not actual_refs.issubset(expected_refs))
        ):
            raise ValueError("批量质控 Canonical Envelope 病历集合不完整")
        if is_partial_failure and len(actual_refs) != _to_int(job.get("success_count")):
            raise ValueError("批量质控 Canonical Envelope 成功病历数量不一致")
        if (
            not envelope_rows
            and int(job.get("total_records") or 0) > 0
            and not (is_partial_failure and _to_int(job.get("success_count")) == 0)
        ):
            raise ValueError("批量质控 Canonical Envelope 缺失")
        return canonical_items
