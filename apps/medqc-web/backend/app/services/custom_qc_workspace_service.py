from __future__ import annotations

import html
import hashlib
import json
import logging
import re
import uuid
import weakref

from ..core.execution_timing import project_stage_timing, timed
from ..core.settings import get_settings

from collections import OrderedDict
from copy import deepcopy
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from io import BytesIO, StringIO
from functools import lru_cache, partial
from threading import RLock
from time import monotonic
from typing import Any, Callable, Dict, List, Mapping, Optional, Sequence
from zoneinfo import ZoneInfo

import sqlalchemy as sa
from sqlalchemy import (
    MetaData,
    Table,
    and_,
    asc,
    case,
    desc,
    func,
    or_,
    select,
    text,
    tuple_,
    update,
)
from sqlalchemy.orm import Session
from .luxian_0609.phase_scope import frozen_luxian_0609_delivery_scope
from .qc_diagnostics.capture import capture_committed_results, diagnostic_capture_enabled
from .qc_dispatch.contracts import (
    DISPATCH_FILTER_KEY,
    dispatch_filter_payload,
    qc_dispatch_mode_from_filters,
)
from .qc_dispatch.repository import QCDispatchRepository
from .qc_dispatch.control import DispatchControlError, effective_dispatch_mode
from .qc_dispatch.dispatcher import QCDispatchEntrypointError, assert_new_qc_task_dispatch_ready
from .luxian_0609.rule_decision_settings import LX0609_TASK_RUNTIME_FILTER_KEY

from .document_domain_alignment import (
    align_document_domain_fields,
    normalize_document_label,
)
from .luxian_0609.customer_renderer import (
    CUSTOMER_SCHEMA_VERSION as LUXIAN_0609_CUSTOMER_SCHEMA_VERSION,
    RULE_SET_VERSION,
)
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
from .luxian_0609_result_export_service import customer_evidence_summary
from .luxian_0916.execution_integrity import (
    LUXIAN_0916_RULE_IDS,
    LUXIAN_0916_RULE_SET_KEY,
    validate_luxian_0916_task_delivery,
)
from .luxian_0609.customer_renderer import (
    compliant_customer_finding,
    customer_finding_from_controlled_facts,
)
from .qc_workspace.export_service import (
    append_complete_workbook_row,
    map_item_status_label as _map_item_status_label,
    render_customer_safe_csv,
    render_customer_safe_html,
    render_customer_safe_workbook,
)
from .qc_workspace.canonical_result_store import (
    CANONICAL_RESULT_DELIVERY_MODE as _CANONICAL_RESULT_DELIVERY_MODE,
    LX0609_CUSTOMER_RESULT_CONTRACT_ERROR as _LX0609_CUSTOMER_RESULT_CONTRACT_ERROR,
    RECORD_RESULT_ENVELOPE_SCHEMA as _RECORD_RESULT_ENVELOPE_SCHEMA,
    CanonicalResultStore,
    canonical_customer_status as _canonical_customer_status,
    canonical_envelope_items_are_consistent as _canonical_envelope_items_are_consistent,
    customer_safe_projection_key,
    envelope_item_from_rule_result,
    keyed_ref as _keyed_ref,
    validated_customer_explanation as _validated_customer_explanation,
)
from .qc_workspace.partial_record_delivery import select_complete_record_items
from .qc_workspace.partial_record_read import (
    MATERIAL_PREPARATION_FAILURE_STAGES,
    read_saved_partial_record_row,
    SavedPartialRecordBatch,
    saved_record_rule_scope,
)
from .qc_workspace.record_repository import RecordRepository, WorkspaceListResult
from .qc_workspace.execution_failure import (
    validate_failed_task_items,
    _normalize_luxian_model_execution_stats,
    _build_luxian_model_execution_summary,
    _merge_luxian_model_execution_stats,
)
from .qc_workspace.failed_rule_retry import (
    FAILED_RULE_RETRY_FILTER_KEY,
    build_failed_rule_retry_scope,
)
from .sample_validation_rule_sets import LUXIAN_0609_CUSTOMER_EXCLUDED_RULE_IDS
from .bundles.emr_view import load_bundle_documents
from .case_identity import CaseRef, CaseRefInput, normalize_case_refs
from .luxian_0609.decision_model import _MAX_FACT_REFS
from ..database.connection import DB_SCHEMA_MODE, SessionLocal, engine


DEFAULT_DOCUMENT_TYPE = "日常病程记录"
DEFAULT_COMPLEXITY = "中复杂度"
DEFAULT_DEFECT_LEVEL = "一般缺陷"
DEFAULT_BATCH_JOB_PAGE_SIZE = 10
LX0609_CUSTOMER_RESULT_CONTRACT_ERROR = _LX0609_CUSTOMER_RESULT_CONTRACT_ERROR
LX0609_ATTEMPT_FILTER_KEY = "_lx0609_attempt_id"
LX0609_LEASE_FILTER_KEY = "_lx0609_lease_v1"


def _batch_job_write_scope(
    table: Table, *, job_id: str, attempt_filters_json: str | None,
    observed_filters_json: str | None = None, queued_only: bool = False,
) -> Any:
    if attempt_filters_json is None:
        observed = _safe_json_loads(observed_filters_json, {})
        if isinstance(observed, dict) and LX0609_ATTEMPT_FILTER_KEY in observed and not queued_only:
            return sa.false()
        formal_0609 = isinstance(observed, dict) and observed.get("rule_set_key") == LUXIAN_0609_RULE_SET_KEY
        return and_(
            table.c.id == job_id,
            table.c.status == "queued" if queued_only else table.c.status != "canceled",
            table.c.filters_json == observed_filters_json if formal_0609 else sa.true(),
        )
    return and_(
        table.c.id == job_id,
        table.c.status == "running",
        table.c.filters_json == attempt_filters_json,
    )

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
_REASON_CODE_PATTERN = re.compile(r"^[a-z][a-z0-9]*(?:_[a-z0-9]+)*$")
_SAFE_SOURCE_TYPE_PATTERN = re.compile(r"^[a-z][a-z0-9]*(?:_[a-z0-9]+)*$")


def _luxian_0609_catalog_rule_ids() -> frozenset[str]:
    """返回总表登记的全部 LX0609 规则身份，供历史 Envelope 做身份校验。

    客户交付层会过滤明确排除的来源规则，但这些规则仍属于已知历史目录。
    因此身份校验必须针对完整目录，不能把“客户不展示”误当成“未知规则”。
    同理，规则停止注册进可执行目录只禁止新执行，不能让其已保存的合法
    历史结果变成未知规则；执行范围仍由可执行目录与 phase_scope 控制。
    """

    return frozenset(entry.rule_id for entry in load_luxian_0609_rule_master())


def _customer_result_rule_id(item: Any) -> str:
    if not isinstance(item, dict):
        return ""
    return _safe_text(
        item.get("customer_rule_id")
        or item.get("qc_point_id")
        or item.get("rule_id")
        or item.get("rule_code")
    ).upper()


def _iter_luxian_batch_sources(job: Dict[str, Any]):
    """遍历批量任务自身及子任务，供客户结果合同校验使用。"""

    pending: List[Dict[str, Any]] = [job]
    seen: set[int] = set()
    while pending:
        source = pending.pop()
        if not isinstance(source, dict) or id(source) in seen:
            continue
        seen.add(id(source))
        yield source
        for child in list(source.get("child_jobs") or source.get("children") or []):
            if isinstance(child, dict):
                pending.append(child)


def _iter_luxian_batch_result_items(job: Dict[str, Any]):
    for source in _iter_luxian_batch_sources(job):
        for item in list(source.get("items") or []):
            if isinstance(item, dict):
                yield item
        for raw_rule in list(source.get("rule_results") or []):
            if not isinstance(raw_rule, dict):
                continue
            for item in list(raw_rule.get("items") or []):
                if isinstance(item, dict):
                    yield item
        summary = source.get("summary")
        if not isinstance(summary, dict):
            continue
        for raw_rule in list(summary.get("rule_results") or []):
            if not isinstance(raw_rule, dict):
                continue
            for item in list(raw_rule.get("items") or []):
                if isinstance(item, dict):
                    yield item


def _validate_luxian_batch_rule_ids(job: Dict[str, Any]) -> None:
    """LX 客户边界只接受当前完整目录中的规则身份。"""

    catalog = _luxian_0609_catalog_rule_ids()
    for item in _iter_luxian_batch_result_items(job):
        rule_id = _customer_result_rule_id(item)
        if not rule_id or rule_id not in catalog:
            raise ValueError(LX0609_CUSTOMER_RESULT_CONTRACT_ERROR)
    # 规则分组可能没有明细项；其身份仍然必须经过同一份完整目录校验，
    # 否则空的旧/未知分组会绕过客户投影边界。
    for source in _iter_luxian_batch_sources(job):
        raw_rule_results = list(source.get("rule_results") or [])
        summary = source.get("summary")
        if isinstance(summary, dict):
            raw_rule_results.extend(list(summary.get("rule_results") or []))
        for raw_rule in raw_rule_results:
            if not isinstance(raw_rule, dict):
                raise ValueError(LX0609_CUSTOMER_RESULT_CONTRACT_ERROR)
            rule_id = _customer_result_rule_id(raw_rule)
            if rule_id:
                if rule_id not in catalog:
                    raise ValueError(LX0609_CUSTOMER_RESULT_CONTRACT_ERROR)
                continue
            # 旧复核快照可能省略分组级 rule_code，但明细项仍带有
            # 可验证的 rule_id。只有“单一且非空”的明细身份可以安全继承；
            # 空分组或多规则混合分组一律拒绝，避免模糊结果进入客户输出。
            item_rule_ids = {
                _customer_result_rule_id(item)
                for item in list(raw_rule.get("items") or [])
                if isinstance(item, dict) and _customer_result_rule_id(item)
            }
            if len(item_rule_ids) != 1 or not item_rule_ids.issubset(catalog):
                raise ValueError(LX0609_CUSTOMER_RESULT_CONTRACT_ERROR)


def _is_visible_luxian_customer_item(item: Dict[str, Any], *, enabled: bool) -> bool:
    if not enabled:
        return True
    rule_id = _customer_result_rule_id(item)
    if not rule_id or rule_id not in _luxian_0609_catalog_rule_ids():
        raise ValueError(LX0609_CUSTOMER_RESULT_CONTRACT_ERROR)
    return rule_id not in LUXIAN_0609_CUSTOMER_EXCLUDED_RULE_IDS


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


def _now_utc_aware() -> datetime:
    return datetime.now(timezone.utc)


_SPREADSHEET_FORMULA_PREFIXES = ("=", "+", "-", "@")
_SPREADSHEET_CONTROL_PREFIXES = ("\t", "\r", "\n")


def _sanitize_spreadsheet_cell(value: Any) -> Any:
    """中和 CSV/Excel 公式注入，保持数值和空白原样。"""
    if value is None or isinstance(value, (bool, int, float)):
        return value
    if isinstance(value, (list, tuple, dict)):
        text = json.dumps(value, ensure_ascii=False, default=str)
    elif isinstance(value, str):
        text = value
    else:
        text = str(value)
    if not text:
        return text
    if (
        text.startswith(_SPREADSHEET_CONTROL_PREFIXES)
        or text.lstrip().startswith(_SPREADSHEET_FORMULA_PREFIXES)
    ):
        return "'" + text
    return text


def _sanitize_spreadsheet_row(values: Sequence[Any]) -> List[Any]:
    return [_sanitize_spreadsheet_cell(value) for value in values]


def _sanitize_spreadsheet_rows(rows: Sequence[Sequence[Any]]) -> List[List[Any]]:
    return [_sanitize_spreadsheet_row(row) for row in rows]


def _sanitize_spreadsheet_summary(summary: Dict[str, Any]) -> Dict[str, Any]:
    sanitized = dict(summary)
    if "operation_ref" in sanitized:
        sanitized["operation_ref"] = _sanitize_spreadsheet_cell(sanitized["operation_ref"])
    status_counts = sanitized.get("status_counts")
    if isinstance(status_counts, dict):
        sanitized["status_counts"] = {
            str(_sanitize_spreadsheet_cell(k)): v for k, v in status_counts.items()
        }
    return sanitized


def _safe_text(value: Any, default: str = "") -> str:
    if value is None:
        return default
    return str(value).strip()


# 病历级统计的统一合同（批处理 Worker 与客户 DTO 共用）：
# 有问题状态的病历不算合规；只有中性状态的病历不算合规，其中全部不适用归“不适用”，
# 含暂停未执行（全部暂停或暂停与不适用混合）归“未执行”（用户口径 2026-11-08）；其余为合规。
# 单条规则的原始状态保持不变，这里只做病历级分类。
RECORD_PROBLEM_STATUSES = frozenset({
    "non_compliant", "ai_suggested_non_compliant", "uncertain", "data_gap", "technical_error",
})
RECORD_NEUTRAL_STATUSES = frozenset({"not_applicable", "not_executed"})


def _record_statuses(items: Any, key_fields: tuple[str, ...]) -> Dict[str, set[str]]:
    statuses: Dict[str, set[str]] = {}
    for item in items or ():
        ref = next((_safe_text(item.get(field)) for field in key_fields if _safe_text(item.get(field))), "")
        if ref:
            statuses.setdefault(ref, set()).add(_safe_text(item.get("status")).lower())
    return statuses


def classify_neutral_records(
    items: Any, key_fields: tuple[str, ...] = ("record_key", "record_id"),
) -> tuple[set[str], set[str]]:
    """只有中性状态的病历：返回（全部不适用, 含暂停未执行）两组病历。"""
    not_applicable: set[str] = set()
    not_executed: set[str] = set()
    for ref, values in _record_statuses(items, key_fields).items():
        if values and values <= RECORD_NEUTRAL_STATUSES:
            (not_executed if "not_executed" in values else not_applicable).add(ref)
    return not_applicable, not_executed


def _compliant_record_refs(items: Any) -> set[str]:
    """合规病历：没有任何问题状态，且不只是中性状态。"""
    return {
        ref for ref, values in _record_statuses(items, ("record_ref",)).items()
        if not values & RECORD_PROBLEM_STATUSES and not values <= RECORD_NEUTRAL_STATUSES
    }


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


def build_customer_safe_source_ref(value: Any) -> str:
    """为受控文书生成与结果证据完全一致的不可逆引用。"""

    return _keyed_ref("src", value, hmac_key=customer_safe_projection_key())


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


_CUSTOMER_TEXT_PRIVATE_KEYS = (
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
_CUSTOMER_CONCLUSION_KEYS = (
    "conclusion", "customer_conclusion", "customer_message", "customer_summary",
)
_CUSTOMER_SUGGESTION_KEYS = (
    "suggestion", "customer_suggestion", "customer_recommendation", "customer_action",
)


def _customer_text_is_safe(value: str, *, identity: Mapping[str, Any]) -> bool:
    """客户文本过滤合同：不含内部术语，也不含本病例的身份值。"""

    if not value or _CUSTOMER_TEXT_FORBIDDEN.search(value):
        return False
    private_values = {
        _safe_text(identity.get(key))
        for key in _CUSTOMER_TEXT_PRIVATE_KEYS
        if _safe_text(identity.get(key))
    }
    return not any(private_value in value for private_value in private_values)


def _explicit_customer_text(
    item: Dict[str, Any], keys: Sequence[str], fallback: str, *, preserve_length: bool = False,
) -> str:
    for key in keys:
        value = _safe_text(item.get(key))
        if not _customer_text_is_safe(value, identity=item):
            continue
        # 正式发布文案保留换行和空白；上面的归一化文本仅用于安全检查。
        return str(item.get(key)).strip() if preserve_length else _truncate_export_text(value, 360)
    return fallback


def _safe_evidence_rows(item: Dict[str, Any], *, hmac_key: str) -> List[Dict[str, Any]]:
    candidates: List[Any] = []
    for key in ("customer_evidence", "evidence_items", "evidence_refs", "evidence"):
        value = item.get(key)
        if isinstance(value, list):
            candidates.extend(value)
    rows: List[Dict[str, Any]] = []
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
        row: Dict[str, Any] = {"source_type": source_type, "source_ref": source_ref}
        if "decision_reference_positions" in candidate:
            positions = candidate["decision_reference_positions"]
            if (not isinstance(positions, list) or not positions or len(positions) > _MAX_FACT_REFS
                    or any(type(value) is not int or not 1 <= value <= _MAX_FACT_REFS for value in positions)
                    or len(positions) != len(set(positions))):
                raise ValueError(LX0609_CUSTOMER_RESULT_CONTRACT_ERROR)
            # 执行器引用顺序已在Finalizer绑定至授权文书，此处仅搬运定位。
            row["decision_reference_positions"] = list(positions)
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
        # 保留执行器选定的全部安全定位，不能按顺序截掉判定所需的时间锚点。
        rows.append(row)
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
    discussion = _safe_text(document.get("document_type")).lower() == "presurg_discussion"
    if discussion and normalized_field == "presurg_discussion_template":
        return "", ""
    if normalized_field:
        matches = [
            section
            for section in list(document.get("sections") or [])
            if isinstance(section, dict)
            and (not discussion or isinstance(section.get("text"), str))
            and _safe_text(section.get("source_field") or section.get("key")).lower()
            == normalized_field
        ]
        if len(matches) == 1:
            excerpt = _compact_authorized_evidence_excerpt(matches[0].get("text"))
            if excerpt:
                return excerpt, "字段级依据"

    if discussion:
        # Missing/ambiguous explicit fields and synthetic display templates cannot
        # become evidence for another field. Without a field coordinate only an
        # actual content string section can supply a document-level excerpt.
        if not normalized_field:
            for section in list(document.get("sections") or []):
                if (isinstance(section, dict)
                        and section.get("source_field") in {
                            "record_content", "content", "host_summary", "discuss_staff",
                        }
                        and isinstance(section.get("text"), str)):
                    excerpt = _compact_authorized_evidence_excerpt(section["text"])
                    if excerpt:
                        return excerpt, "文书级依据"
        return "", ""

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
            if re.fullmatch(r"record_content_span_[0-9]{1,5}_[0-9]{1,5}", _safe_text(evidence.get("field_path"))):
                # 此定位只对原任务冻结的正文版本有效。
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


def _single_record_model_analysis(item: Dict[str, Any]) -> str:
    """保留规则执行器提供的医学分析，不在展示层二次概括或推断。"""

    return _safe_text(item.get("model_analysis") or item.get("medical_analysis"))[:8000]


def _customer_record_ref(item: Dict[str, Any], *, hmac_key: str) -> str:
    """结果与失败清单共用病例引用，不为生成引用校验临床结论。"""
    existing_ref = _safe_text(item.get("record_ref"))
    if re.fullmatch(r"rec_[0-9a-f]{24}", existing_ref):
        return existing_ref
    material = "|".join(
        _safe_text(item.get(key))
        for key in ("institute_id", "patient_id", "visit_id", "record_id", "mr_no")
    )
    return _keyed_ref("rec", material, hmac_key=hmac_key)


def project_customer_safe_result_item(
    item: Dict[str, Any],
    *,
    hmac_key: str,
) -> Dict[str, Any]:
    """把任意内部结果投影为唯一、可审计且不含病历原文/身份的客户 DTO。"""

    raw = dict(item or {})
    rule_id = _safe_text(
        raw.get("customer_rule_id")
        or raw.get("qc_point_id")
        or raw.get("rule_id")
        or raw.get("rule_code")
    ).upper()
    record_ref = _customer_record_ref(raw, hmac_key=hmac_key)
    is_luxian = rule_id.startswith("LX0609-")
    # 客户安全 DTO 可能再次进入列表投影/导出；二次投影仍须校验状态与公开事实。
    is_current_luxian_result = (
        is_luxian
        and _safe_text(raw.get("schema_version")) in {
            LUXIAN_0609_CUSTOMER_SCHEMA_VERSION, _CUSTOMER_RESULT_SCHEMA,
        }
        and bool(_safe_text(raw.get("status")))
        and bool(_safe_text(raw.get("result_status")))
    )
    if is_current_luxian_result:
        status = _safe_text(raw.get("status")).lower()
        result_status = _safe_text(raw.get("result_status")).lower()
        display_status = _safe_text(raw.get("display_status")).lower()
        expected_is_compliant = (
            True if status == "compliant" else False if status == "non_compliant" else None
        )
        if (
            status not in _GENERIC_CUSTOMER_TEXT
            or result_status != status
            or (display_status and display_status != status)
            or raw.get("is_compliant") is not expected_is_compliant
        ):
            raise ValueError(LX0609_CUSTOMER_RESULT_CONTRACT_ERROR)
    else:
        status = _canonical_customer_status(raw)

    if (
        is_luxian
        and not is_current_luxian_result
        and status == "technical_error"
        and _safe_text(raw.get("reason_code")) == "canonical_result_envelope_invalid"
    ):
        # 旧内部项已被任务读取边界隔离为技术异常；不能再要求它满足
        # 当前规则的事实合同，否则单条旧项会中断整个历史任务详情。
        customer_display_facts, criterion_results = {}, []
    else:
        customer_display_facts, criterion_results = _validated_customer_explanation(
            raw,
            rule_id=rule_id,
            status=status,
        )
    generic_conclusion, generic_suggestion = _GENERIC_CUSTOMER_TEXT[status]
    # 当前 Canonical 文案由执行器/Renderer 已生成。读取层只做敏感裁剪，
    # 不得按规则、事实或 status 再次生成结论。
    reuse_saved_customer_text = (
        is_current_luxian_result
        or _safe_text(raw.get("schema_version")) == _CUSTOMER_RESULT_SCHEMA
    )
    # 当前 LX0609 正式结果（v2 发布合同或其客户 DTO，且状态合同已校验）
    # 保留发布文案全文；其他规则集和旧形态继续走原有 360 字裁剪。
    preserve_published_text = is_current_luxian_result
    conclusion = _explicit_customer_text(
        raw,
        _CUSTOMER_CONCLUSION_KEYS
        if reuse_saved_customer_text
        else (),
        generic_conclusion,
        preserve_length=preserve_published_text,
    )
    if (
        is_luxian
        and not is_current_luxian_result
        and _safe_text(raw.get("schema_version")) != _CUSTOMER_RESULT_SCHEMA
    ):
        # 兼容测试/复核中的旧内部投影形状；正式 LX0609 批详情在进入此函数前
        # 已隔离为 technical_error，不能沿用这条旧的结论重建分支。
        if status == "compliant":
            conclusion = compliant_customer_finding(
                rule_id=rule_id,
                criterion_results=criterion_results,
            )
        else:
            controlled_finding = customer_finding_from_controlled_facts(
                rule_id=rule_id,
                facts=customer_display_facts,
            )
            if controlled_finding:
                conclusion = controlled_finding
    suggestion = _explicit_customer_text(
        raw,
        _CUSTOMER_SUGGESTION_KEYS
        if reuse_saved_customer_text
        else (),
        generic_suggestion,
        preserve_length=preserve_published_text,
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
        "result_status": result_status if is_current_luxian_result else status,
        "display_status": (
            display_status or status if is_current_luxian_result else status
        ),
        "is_compliant": raw.get("is_compliant") if is_current_luxian_result else (
            True if status == "compliant" else False if status == "non_compliant" else None
        ),
        "is_confirmed_issue": status == "non_compliant",
        "reason_code": _canonical_reason_code(raw),
        "rule_version": _safe_text(raw.get("rule_version")),
        "conclusion": conclusion,
        "findings": conclusion,
        "customer_conclusion": conclusion,
        "suggestion": suggestion,
        "customer_suggestion": suggestion,
        "evidence": _safe_evidence_rows(raw, hmac_key=hmac_key),
    }
    if is_luxian:
        from .history_evidence_audit import read_projection
        projected.update(read_projection(raw))
    if customer_display_facts:
        projected["customer_display_facts"] = customer_display_facts
    if criterion_results:
        projected["criterion_results"] = criterion_results
    model_analysis = _single_record_model_analysis(raw)
    if model_analysis:
        projected["model_analysis"] = model_analysis
    return projected


def _customer_filtered_saved_text(
    item: Dict[str, Any], *, identity: Mapping[str, Any],
) -> Dict[str, Any]:
    """已保存条目原样返回；主显示结论、建议与客户投影使用同一别名优先级、
    安全检查和回退选择，不重生成、不截断正常文本。"""

    filtered = dict(item)
    from .history_evidence_audit import read_projection
    filtered.update(read_projection(item))
    generic = _GENERIC_CUSTOMER_TEXT.get(_canonical_customer_status(item))
    if generic is None:
        return filtered
    probe_identity = {**item, **identity}
    for keys, extra_aliases, fallback in (
        (_CUSTOMER_CONCLUSION_KEYS, ("findings",), generic[0]),
        (_CUSTOMER_SUGGESTION_KEYS, (), generic[1]),
    ):
        aliases = (*keys, *extra_aliases)
        if not any(
            isinstance(filtered.get(key), str) and filtered[key].strip() for key in aliases
        ):
            # 未保存任何该类文案时保持原样，不在读取层补写新文案。
            continue
        # 与批详情/导出相同：主字段禁止时继续选合法备用别名，全部禁止才回退。
        selected = _explicit_customer_text(probe_identity, keys, fallback, preserve_length=True)
        filtered[keys[0]] = selected
        for key in (*keys[1:], *extra_aliases):
            value = filtered.get(key)
            if isinstance(value, str) and value.strip() and not _customer_text_is_safe(
                _safe_text(value), identity=probe_identity,
            ):
                # 其余公开别名不得重新输出禁止内容，统一为已选的安全主文案。
                filtered[key] = selected
    return filtered


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
    _validate_luxian: Optional[bool] = None,
) -> List[Dict[str, Any]]:
    """按统一优先级返回供 API、复核和导出共用的去重原始行集。"""

    validate_luxian = (
        _is_luxian_0609_export_job(job)
        if _validate_luxian is None
        else _validate_luxian
    )
    if validate_luxian:
        _validate_luxian_batch_rule_ids(job)

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
        if not _is_visible_luxian_customer_item(item, enabled=validate_luxian):
            continue
        if not _is_current_rule_contract_result(item):
            continue
        # 已投影的客户 DTO 是安全读模型，重入时不应误判成旧内部结果。
        is_current_luxian_result = (
            _safe_text(item.get("rule_id") or item.get("rule_code")).startswith("LX0609-")
            and _safe_text(item.get("schema_version")) in {
                LUXIAN_0609_CUSTOMER_SCHEMA_VERSION, _CUSTOMER_RESULT_SCHEMA,
            }
            and bool(_safe_text(item.get("status")))
            and bool(_safe_text(item.get("result_status")))
        )
        if validate_luxian and not is_current_luxian_result:
            # 旧批任务项没有 Canonical 交付合同。读取 API 明确隔离为既有
            # technical_error，绝不在此重算状态或客户结论，也不让单条旧项
            # 中断整个任务详情。
            source_item = {
                **item,
                "status": "technical_error",
                "result_status": "technical_error",
                "is_compliant": None,
                "reason_code": "canonical_result_envelope_invalid",
            }
        else:
            source_item = item
        projected = project_customer_safe_result_item(source_item, hmac_key=hmac_key)
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
            unique_by_rule[identity] = (authority, source_item)
    return [item for _, item in unique_by_rule.values()]


def flatten_customer_safe_result_items(
    job: Dict[str, Any],
    *,
    hmac_key: str,
    _validate_luxian: Optional[bool] = None,
) -> List[Dict[str, Any]]:
    """按内部结果原顺序生成供 API、复核和全部导出共用的唯一行集。"""

    return [
        project_customer_safe_result_item(item, hmac_key=hmac_key)
        for item in iter_unique_customer_result_source_items(
            job,
            hmac_key=hmac_key,
            _validate_luxian=_validate_luxian,
        )
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


def _safe_live_execution_state(value: Any) -> Dict[str, Any]:
    """只投影受控阶段和计数，不公开患者坐标、原始异常或任意trace字段。"""
    if not isinstance(value, dict) or value.get("kind") != "native_executor_phase":
        return {}
    event = value.get("event")
    if event not in {"started", "completed", "failed", "published"}:
        return {}
    from .luxian_0609.executor_registry import LEGACY_NATIVE_EXECUTION_ORDER
    key = value.get("executor_key")
    if key not in LEGACY_NATIVE_EXECUTION_ORDER:
        return {}
    return {
        "kind": "native_executor_phase", "event": event, "executor_key": key,
        **{name: max(0, _to_int(value.get(name))) for name in (
            "completed_batches", "total_batches", "partial_item_count",
            "current_rule_count", "completed_rule_count", "total_rule_count",
        )},
    }


def _safe_review_report(
    value: Any,
    *,
    hmac_key: str,
    _validate_luxian: bool = False,
) -> Optional[Dict[str, Any]]:
    if not isinstance(value, dict):
        return None
    findings: List[Dict[str, Any]] = []
    for raw_finding in list(value.get("findings") or []):
        if not isinstance(raw_finding, dict):
            continue
        # 复核 finding 是审核元数据，不是规则执行结果。直接投影其受控身份和
        # 状态字段，避免为了生成引用而伪造一条缺少解释事实的规则结果。
        rule_id = _customer_result_rule_id(raw_finding)
        if _validate_luxian:
            if not rule_id or rule_id not in _luxian_0609_catalog_rule_ids():
                raise ValueError(LX0609_CUSTOMER_RESULT_CONTRACT_ERROR)
            if rule_id in LUXIAN_0609_CUSTOMER_EXCLUDED_RULE_IDS:
                continue
        rule = get_luxian_0609_rule(rule_id) or {}
        canonical_status = _canonical_customer_status(
            {
                "status": raw_finding.get("original_status")
                or raw_finding.get("canonical_status")
                or raw_finding.get("status")
            }
        )
        existing_ref = _safe_text(raw_finding.get("record_ref"))
        record_ref = (
            existing_ref
            if re.fullmatch(r"rec_[0-9a-f]{24}", existing_ref)
            else _keyed_ref(
                "rec",
                raw_finding.get("finding_key") or rule_id,
                hmac_key=hmac_key,
            )
        )
        reason_code = _canonical_reason_code(
            {
                "reason_code": raw_finding.get("original_reason_code")
                or raw_finding.get("reason_code")
            }
        )
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
                    or f"{record_ref}:{rule_id}:{risk_type}",
                    hmac_key=hmac_key,
                ),
                "record_ref": record_ref,
                "rule_id": rule_id,
                "rule_name": _safe_text(
                    rule.get("rule_name") or rule.get("name"),
                    rule_id,
                ),
                "canonical_status": canonical_status,
                "reason_code": reason_code,
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


def project_batch_job_overview(job: Dict[str, Any]) -> Dict[str, Any]:
    """质控记录列表的一行：任务元数据、范围与病历进度，不含任何结果计数、结论或证据。

    只白名单输出；filters 原始对象不透传。
    ``has_results`` 只表示失败任务是否已有可打开查看的结果，不代表结果条数。
    """

    filters = job.get("filters") if isinstance(job.get("filters"), dict) else {}
    # 与完整投影同一取法（选定规则优先，其次规则范围），列表“选定 N 个质控点”口径不变。
    raw_rule_ids = filters.get("selected_rule_ids") or filters.get("rule_ids") or []
    rule_ids = [
        _safe_text(value)
        for value in (raw_rule_ids if isinstance(raw_rule_ids, list) else [])
        if _safe_text(value)
    ]
    total_records = _to_int(job.get("total_records"))
    success_count = _to_int(job.get("success_count"))
    customer_rule_count = _to_int(filters.get("customer_rule_count"))
    return {
        "schema_version": "customer-qc-job-overview-v1",
        "id": _safe_text(job.get("id")),
        "status": _safe_text(job.get("status")).lower(),
        "job_kind": _safe_text(job.get("job_kind")),
        "rule_code": _safe_text(job.get("rule_code")).upper(),
        "rule_name": _safe_text(job.get("rule_name")),
        "rule_set_key": _safe_text(filters.get("rule_set_key")),
        "rule_set_name": _safe_text(filters.get("rule_set_name")),
        "scene": _safe_text(job.get("scene")),
        "scope": _safe_text(job.get("scope")),
        "created_at": _safe_text(job.get("created_at")),
        "started_at": _safe_text(job.get("started_at")),
        "finished_at": _safe_text(job.get("finished_at")),
        "updated_at": _safe_text(job.get("updated_at")),
        "total_records": total_records,
        "success_count": success_count,
        "failed_count": _to_int(job.get("failed_count")),
        "customer_rule_count": customer_rule_count,
        "draft_ids": rule_ids,
        "has_results": bool(job.get("has_results")),
        "summary": {
            "total_records": total_records,
            "success_count": success_count,
            "customer_rule_count": customer_rule_count,
        },
    }


def _safe_retry_lineage(filters: Mapping[str, Any]) -> Dict[str, Any]:
    raw = filters.get("retry_lineage")
    if not isinstance(raw, dict) or raw.get("schema_version") != "qc-retry-lineage-v1":
        return {}
    source = _safe_text(raw.get("source_job_id"))
    root = _safe_text(raw.get("root_job_id"))
    if not all(re.fullmatch(r"[A-Za-z0-9_-]{1,64}", value) for value in (source, root)):
        return {}
    return {"source_job_id": source, "root_job_id": root,
            "source_attempt": _safe_text(raw.get("source_attempt"))
            if re.fullmatch(r"[0-9a-f]{32}", _safe_text(raw.get("source_attempt"))) else "",
            "attempt": max(1, _to_int(raw.get("attempt"), 1))}


def _safe_failed_task_diagnostic(item: Dict[str, Any]) -> Dict[str, Any]:
    """保留已定义的失败码与阶段；不返回原始异常、供应商响应或任意文本。"""
    from .material_admission import MESSAGES

    from .qc_execution_errors import safe_failure_projection
    code = _safe_text(item.get("reason_code"))
    if not code and item.get("error_phase") == "material_capture":
        # 历史取材失败以 error 保存受控码，只允许精确命中材料错误合同。
        candidate = _safe_text(item.get("error"))
        if candidate in MESSAGES:
            code = candidate
    diagnostic = safe_failure_projection({**item, "reason_code": code})
    phase = _safe_text(item.get("error_phase"))
    if phase in {"material_capture", "material_assembly", "evaluate_document", "result_write"}:
        diagnostic["error_phase"] = phase
    return diagnostic


def project_customer_safe_batch_job(
    job: Dict[str, Any],
    *,
    hmac_key: str,
    _validate_luxian: Optional[bool] = None,
) -> Dict[str, Any]:
    """生成 API/复核共用的客户任务 DTO，不回传原始 filters/summary 技术对象。"""

    validate_luxian = (
        _is_luxian_0609_export_job(job)
        if _validate_luxian is None
        else _validate_luxian
    )
    if validate_luxian:
        _validate_luxian_batch_rule_ids(job)
    items = flatten_customer_safe_result_items(
        job,
        hmac_key=hmac_key,
        _validate_luxian=validate_luxian,
    )
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
    raw_timing = raw_summary.get("record_timing")
    raw_timing = raw_timing if isinstance(raw_timing, dict) else {}
    filters = job.get("filters") if isinstance(job.get("filters"), dict) else {}
    progress = _safe_operational_progress(
        raw_summary.get("progress") or job.get("progress")
    )
    review_report = _safe_review_report(
        raw_summary.get("review_report"),
        hmac_key=hmac_key,
        _validate_luxian=validate_luxian,
    )
    safe_summary: Dict[str, Any] = {
        "record_timing": {
            "measured_record_count": _to_int(raw_timing.get("measured_record_count")),
            "completed_timed_record_count": _to_int(raw_timing.get("completed_timed_record_count")),
            "average_complete_seconds": (
                _to_float(raw_timing["average_complete_seconds"])
                if raw_timing.get("average_complete_seconds") is not None else None
            ),
        },
        "total_records": _to_int(raw_summary.get("total_records"), _to_int(job.get("total_records"))),
        "success_count": _to_int(raw_summary.get("success_count"), _to_int(job.get("success_count"))),
        "failed_count": _to_int(raw_summary.get("failed_count"), _to_int(job.get("failed_count"))),
        "compliant_records": len(_compliant_record_refs(items)),
        "not_applicable_records": len(classify_neutral_records(items, ("record_ref",))[0]),
        "not_executed_records": len(classify_neutral_records(items, ("record_ref",))[1]),
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
    if isinstance(raw_summary.get("material_failure"), dict):
        from .material_admission import safe_material_failure
        safe_summary["material_failure"] = safe_material_failure(raw_summary["material_failure"].get("code"))
        safe_summary["material_failed_record_count"] = _to_int(raw_summary.get("material_failed_record_count"))
        safe_summary["failed_rule_count"] = _to_int(raw_summary.get("failed_rule_count"))
    live_state = _safe_live_execution_state(raw_summary.get("stream_state"))
    if live_state:
        safe_summary["stream_state"] = live_state
    first_latency = raw_summary.get("first_result_latency")
    if isinstance(first_latency, (float, int)) and not isinstance(first_latency, bool) and first_latency > 0:
        safe_summary["first_result_latency"] = first_latency
    if raw_summary.get("execution_status") in {"completed", "partial_failed", "failed"}:
        safe_summary["execution_status"] = raw_summary["execution_status"]
        for count_key in ("completed_rule_count", "failed_rule_count"):
            safe_summary[count_key] = max(0, _to_int(raw_summary.get(count_key)))
        safe_summary["failed_rule_ids"] = sorted({
            _safe_text(rule_id).upper()
            for rule_id in (raw_summary.get("failed_rule_ids") or [])
            if re.fullmatch(r"LX0609-(?!00)\d{2}-(?!00)\d{2}-(?!00)\d{2}", _safe_text(rule_id).upper())
        })
    raw_automatic_retry = (
        raw_summary.get("automatic_failed_rule_retry")
        if isinstance(raw_summary.get("automatic_failed_rule_retry"), dict)
        else {}
    )
    automatic_retry_status = _safe_text(raw_automatic_retry.get("status")).lower()
    if automatic_retry_status in {
        "planned",
        "queued",
        "running",
        "enqueue_failed",
        "interrupted",
        "completed",
        "exhausted",
        "not_applicable",
        "not_retryable",
    }:
        safe_automatic_retry: Dict[str, Any] = {
            "status": automatic_retry_status,
            "max_attempts": max(0, _to_int(raw_automatic_retry.get("max_attempts"))),
            "completed_attempts": max(
                0,
                _to_int(raw_automatic_retry.get("completed_attempts")),
            ),
            "remaining_failure_count": max(
                0,
                _to_int(raw_automatic_retry.get("remaining_failure_count")),
            ),
        }
        if isinstance(raw_automatic_retry.get("should_retry"), bool):
            safe_automatic_retry["should_retry"] = raw_automatic_retry["should_retry"]
        if raw_automatic_retry.get("next_attempt") is not None:
            safe_automatic_retry["next_attempt"] = max(
                0,
                _to_int(raw_automatic_retry.get("next_attempt")),
            )
        if raw_automatic_retry.get("delay_seconds") is not None:
            safe_automatic_retry["delay_seconds"] = max(
                0.0,
                _to_float(raw_automatic_retry.get("delay_seconds")),
            )
        if (
            automatic_retry_status == "enqueue_failed"
            and raw_automatic_retry.get("reason_code") == "retry_enqueue_failed"
        ):
            safe_automatic_retry["reason_code"] = "retry_enqueue_failed"
        if (
            automatic_retry_status == "interrupted"
            and raw_automatic_retry.get("reason_code")
            in {"retry_start_interrupted", "retry_execution_interrupted"}
        ):
            safe_automatic_retry["reason_code"] = raw_automatic_retry["reason_code"]
        safe_summary["automatic_failed_rule_retry"] = safe_automatic_retry
    model_counts = _normalize_luxian_model_execution_stats(raw_summary.get("model_execution_stats"))
    if model_counts is not None:
        safe_summary["model_execution_stats"] = _build_luxian_model_execution_summary(model_counts)
    usage_observed = raw_summary.get("luxian_0609_usage_observation_complete")
    if isinstance(usage_observed, bool):
        safe_summary["luxian_0609_usage_observation_complete"] = usage_observed
        raw_unknown_keys = raw_summary.get("luxian_0609_usage_unknown_executor_keys")
        safe_summary["luxian_0609_usage_unknown_executor_keys"] = sorted({
            key for raw_key in (
                raw_unknown_keys if isinstance(raw_unknown_keys, (list, tuple)) else []
            )
            if (key := _safe_text(raw_key)) and re.fullmatch(r"[a-z][a-z0-9_]{0,63}", key)
        })[:30]
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
    stage_timing = project_stage_timing(raw_profile.get("stage_timing"))
    if stage_timing is not None:
        safe_performance_profile["stage_timing"] = stage_timing
    if raw_profile.get("rule_duration_basis") == "allocated_or_reported_metadata":
        safe_performance_profile["rule_duration_basis"] = "allocated_or_reported_metadata"
        safe_performance_profile["slow_rule_ranking_is_measured"] = False
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
        raw_rule_id = _customer_result_rule_id(raw_rule)
        if validate_luxian:
            if not raw_rule_id or raw_rule_id not in _luxian_0609_catalog_rule_ids():
                raise ValueError(LX0609_CUSTOMER_RESULT_CONTRACT_ERROR)
            if raw_rule_id in LUXIAN_0609_CUSTOMER_EXCLUDED_RULE_IDS:
                continue
        raw_rule_items = [
            project_customer_safe_result_item(item, hmac_key=hmac_key)
            for item in list(raw_rule.get("items") or [])
            if isinstance(item, dict)
            and _is_visible_luxian_customer_item(item, enabled=validate_luxian)
            and _is_current_rule_contract_result(item)
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
        project_customer_safe_batch_job(
            child,
            hmac_key=hmac_key,
            _validate_luxian=validate_luxian,
        )
        for child in list(job.get("child_jobs") or job.get("children") or [])
        if isinstance(child, dict)
    ]
    failed_records = [
        {
            "record_ref": _customer_record_ref(item, hmac_key=hmac_key),
            "status": "technical_error",
            **_safe_failed_task_diagnostic(item),
            "rule_id": _safe_text(item.get("rule_id")).upper()
            if re.fullmatch(r"LX0609-(?!00)\d{2}-(?!00)\d{2}-(?!00)\d{2}", _safe_text(item.get("rule_id")).upper()) else "",
        }
        for item in list(job.get("failed_records") or [])
        if isinstance(item, dict)
    ]
    failed_refs = {failure["record_ref"] for failure in failed_records}
    if safe_summary.get("execution_status") in {"partial_failed", "failed"} or failed_refs:
        # 与批处理 Worker 同一合同：执行失败的病历优先归失败，不再计入合规、不适用或未执行。
        neutral_na, neutral_paused = classify_neutral_records(items, ("record_ref",))
        safe_summary["compliant_records"] = len(_compliant_record_refs(items) - failed_refs)
        safe_summary["not_applicable_records"] = len(neutral_na - failed_refs)
        safe_summary["not_executed_records"] = len(neutral_paused - failed_refs)
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
    # 仅投影保存时的展示快照；不按当前发布配置重算，也不暴露内部filters。
    acceptance_snapshot = filters.get("acceptance_only_rule_ids")
    acceptance_rule_ids = sorted({
        value for value in acceptance_snapshot
        if isinstance(value, str) and value in _luxian_0609_catalog_rule_ids()
    }) if isinstance(acceptance_snapshot, list) else []
    execution_scope_hash = _safe_text(filters.get("execution_scope_hash")).lower()
    if not re.fullmatch(r"[0-9a-f]{64}", execution_scope_hash):
        execution_scope_hash = ""
    retry_lineage = _safe_retry_lineage(filters)
    if isinstance(raw_summary.get("execution_error"), dict):
        from .qc_execution_errors import safe_failure_projection
        safe_summary["execution_error"] = safe_failure_projection(raw_summary["execution_error"])
    return {
        "schema_version": "customer-qc-job-v1",
        "retry_lineage": retry_lineage or None,
        "retry_of_job_id": retry_lineage.get("source_job_id", ""),
        "retry_root_job_id": retry_lineage.get("root_job_id", ""),
        "retry_attempt": retry_lineage.get("attempt", 0),
        "acceptance_only_rule_ids": acceptance_rule_ids,
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


_TASK_DATE_TIMEZONE = ZoneInfo("Asia/Shanghai")


def _task_date_utc_boundary(day: date, *, next_day: bool = False) -> datetime:
    if not next_day and day == date.min:
        return datetime.min
    # 先换算到 UTC，避免最大日期在北京时间上推进一天时溢出。
    if next_day and day == date.max:
        last_local = datetime.combine(day, time.max, _TASK_DATE_TIMEZONE)
        return last_local.astimezone(timezone.utc).replace(tzinfo=None) + timedelta(microseconds=1)
    boundary_day = day + timedelta(days=1) if next_day else day
    local_midnight = datetime.combine(boundary_day, time.min, _TASK_DATE_TIMEZONE)
    return local_midnight.astimezone(timezone.utc).replace(tzinfo=None)


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


@lru_cache(maxsize=2)
def _drafts_table(*, readonly: bool = False) -> Table:
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
    if not readonly:
        metadata.create_all(bind=engine, checkfirst=True)
    return table


@lru_cache(maxsize=2)
def _batch_jobs_table(*, readonly: bool = False) -> Table:
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
    if not readonly:
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
    inspector = sa.inspect(engine)
    columns = {
        column["name"] for column in inspector.get_columns("custom_qc_batch_jobs", schema=schema)
    }
    indexes = {
        index["name"] for index in inspector.get_indexes("custom_qc_batch_jobs", schema=schema)
    }
    # 已齐备的库不重复发DDL；缺项时保留既有迁移职责。
    if column_sql.keys() <= columns and "idx_custom_qc_batch_jobs_parent_job_id" in indexes:
        return
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
    filters_dict = dict(filters) if isinstance(filters, dict) else {}
    filters_dict.pop(LX0609_ATTEMPT_FILTER_KEY, None)
    filters_dict.pop(LX0609_LEASE_FILTER_KEY, None)
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
                        "rule_code": _safe_text(raw_item.get("rule_code")) or (
                            _safe_text(raw_item.get("rule_id"))
                            if filters_dict.get("rule_set_key") == LUXIAN_0609_RULE_SET_KEY
                            else _safe_text(row.get("rule_code"))
                        ),
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


def _customer_export_rows(
    job: Dict[str, Any],
    *,
    hmac_key: str,
) -> tuple[List[Dict[str, Any]], List[List[str]], Dict[str, Any]]:
    source_items = iter_unique_customer_result_source_items(job, hmac_key=hmac_key)
    items: List[Dict[str, Any]] = []
    for source_item in source_items:
        # 正式发布文案原样导出，不在读取层重生成建议或资料缺口结论。
        projected = project_customer_safe_result_item(source_item, hmac_key=hmac_key)
        items.append(projected)
    rows: List[List[str]] = []
    for item in items:
        evidence_text = customer_evidence_summary(
            list(item.get("evidence") or []), facts=item.get("customer_display_facts"),
        )
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
    items, rows, summary = _customer_export_rows(job, hmac_key=hmac_key)
    return render_customer_safe_workbook(
        items=items,
        rows=_sanitize_spreadsheet_rows(rows),
        summary=_sanitize_spreadsheet_summary(summary),
    )


def _export_customer_safe_csv(job: Dict[str, Any], *, hmac_key: str) -> StringIO:
    _items, rows, summary = _customer_export_rows(job, hmac_key=hmac_key)
    return render_customer_safe_csv(
        rows=_sanitize_spreadsheet_rows(rows),
        summary=_sanitize_spreadsheet_summary(summary),
    )


def _canonical_customer_export_rows(
    job: Dict[str, Any],
    *,
    hmac_key: str,
    canonical_items: Sequence[Dict[str, Any]],
) -> tuple[List[Dict[str, Any]], List[List[str]], Dict[str, Any]]:
    canonical_job = {
        "id": job.get("id"),
        "filters": {"rule_set_key": LUXIAN_0609_RULE_SET_KEY},
        "items": list(canonical_items),
    }
    return _customer_export_rows(
        canonical_job,
        hmac_key=hmac_key,
    )


def _export_customer_safe_html(
    job: Dict[str, Any],
    *,
    hmac_key: str,
    canonical_items: Sequence[Dict[str, Any]],
) -> str:
    items, rows, summary = _canonical_customer_export_rows(
        job, hmac_key=hmac_key, canonical_items=canonical_items,
    )
    return render_customer_safe_html(items=items, rows=rows, summary=summary)


class PreviousRecordResultAnchorChanged(Exception):
    """历史视图的锚点不再是该病例最近一次资料准备失败的轮次。"""


class PreviousRecordResultConflict(Exception):
    """当前账号可核验的历史候选无法选出唯一轮次。"""


def _record_result_completed_at(job: Mapping[str, Any]) -> Optional[str]:
    value = job.get("finished_at")
    if isinstance(value, datetime):
        return value.isoformat()
    return _safe_text(value) or None


def _record_result_unselected(state: str, reason_code: str, expected_rule_ids: Sequence[str]) -> Dict[str, Any]:
    return {
        "schema_version": "lx0609-single-record-result-v1",
        "state": state,
        "reason_code": reason_code,
        "record_ref": "",
        "job_id": "",
        "items": [],
        "expected_rule_count": len(expected_rule_ids),
        "result_rule_count": 0,
        "is_complete": False,
    }


@dataclass
class WorkspaceBatchJobListResult:
    items: List[Dict[str, Any]]
    total: int
    page: int
    page_size: int


_SUMMARY_CACHE_LOCK = RLock()
_WATERMARK_SUMMARY_CACHE: "OrderedDict[tuple[Any, ...], Dict[tuple[str, str, str], Dict[str, Any]]]" = OrderedDict()
_WATERMARK_SUMMARY_CACHE_MAX = 32
_ENVELOPE_SUMMARY_CACHE: "OrderedDict[tuple[Any, ...], Dict[str, Any]]" = OrderedDict()
_ENVELOPE_SUMMARY_CACHE_MAX = 4096
_PARTIAL_SUMMARY_CACHE: "OrderedDict[tuple[Any, ...], Dict[str, Any]]" = OrderedDict()
_PARTIAL_SUMMARY_CACHE_MAX = 2048
_RECORD_ID_ILIKE_SQL_THRESHOLD = 50
_TRACKED_CACHE_SCOPE_KEYS: set[str] = set()
_SCOPE_EVICTION_CALLBACKS: list[Callable[[str], None]] = []


def register_summary_cache_scope_eviction_callback(callback: Callable[[str], None]) -> None:
    """注册随数据库作用域（bind GC）同步失效的下游缓存回调。"""
    with _SUMMARY_CACHE_LOCK:
        if callback not in _SCOPE_EVICTION_CALLBACKS:
            _SCOPE_EVICTION_CALLBACKS.append(callback)


def _evict_summary_caches_for_scope(scope_key: str) -> None:
    with _SUMMARY_CACHE_LOCK:
        for cache in (
            _WATERMARK_SUMMARY_CACHE,
            _ENVELOPE_SUMMARY_CACHE,
            _PARTIAL_SUMMARY_CACHE,
        ):
            stale_keys = [key for key in cache if key and key[0] == scope_key]
            for key in stale_keys:
                cache.pop(key, None)
        _TRACKED_CACHE_SCOPE_KEYS.discard(scope_key)
        callbacks = tuple(_SCOPE_EVICTION_CALLBACKS)
    for callback in callbacks:
        try:
            callback(scope_key)
        except Exception:
            pass


def _register_scope_key_finalizer(bind_obj: Any, scope_key: str) -> None:
    with _SUMMARY_CACHE_LOCK:
        if scope_key in _TRACKED_CACHE_SCOPE_KEYS:
            return
        try:
            weakref.finalize(bind_obj, _evict_summary_caches_for_scope, scope_key)
            _TRACKED_CACHE_SCOPE_KEYS.add(scope_key)
        except TypeError:
            pass


def clear_luxian_0609_summary_caches() -> None:
    """清空基于不可变版本键的质控摘要缓存（供测试或运维手动重置）。"""
    with _SUMMARY_CACHE_LOCK:
        _WATERMARK_SUMMARY_CACHE.clear()
        _ENVELOPE_SUMMARY_CACHE.clear()
        _PARTIAL_SUMMARY_CACHE.clear()


def _watermark_bucket_get(
    bucket_key: tuple[Any, ...],
    identities: set[tuple[str, str, str]],
) -> tuple[Dict[tuple[str, str, str], Dict[str, Any]], set[tuple[str, str, str]]]:
    with _SUMMARY_CACHE_LOCK:
        bucket = _WATERMARK_SUMMARY_CACHE.get(bucket_key)
        if bucket is None:
            return {}, set(identities)
        _WATERMARK_SUMMARY_CACHE.move_to_end(bucket_key)
        hits: Dict[tuple[str, str, str], Dict[str, Any]] = {}
        missing: set[tuple[str, str, str]] = set()
        for identity in identities:
            cached = bucket.get(identity)
            if cached is not None:
                hits[identity] = deepcopy(cached)
            else:
                missing.add(identity)
        return hits, missing


def _watermark_bucket_merge(
    bucket_key: tuple[Any, ...],
    projections: Mapping[tuple[str, str, str], Dict[str, Any]],
) -> None:
    if not projections:
        return
    with _SUMMARY_CACHE_LOCK:
        bucket = _WATERMARK_SUMMARY_CACHE.get(bucket_key)
        if bucket is None:
            bucket = {}
            _WATERMARK_SUMMARY_CACHE[bucket_key] = bucket
        for identity, value in projections.items():
            bucket[identity] = deepcopy(value)
        _WATERMARK_SUMMARY_CACHE.move_to_end(bucket_key)
        while len(_WATERMARK_SUMMARY_CACHE) > _WATERMARK_SUMMARY_CACHE_MAX:
            _WATERMARK_SUMMARY_CACHE.popitem(last=False)


def _session_cache_scope_key(session: Session) -> Optional[str]:
    bind = session.get_bind() if hasattr(session, "get_bind") else None
    if bind is None:
        return None
    bind_obj = getattr(bind, "engine", bind)
    dialect_name = getattr(getattr(bind_obj, "dialect", None), "name", "")
    if dialect_name == "sqlite":
        scope_key = f"sqlite:{id(bind_obj)}"
        _register_scope_key_finalizer(bind_obj, scope_key)
        return scope_key
    url = getattr(bind_obj, "url", None)
    if url is not None and hasattr(url, "render_as_string"):
        return f"{dialect_name}:{url.render_as_string(hide_password=True)}"
    scope_key = f"{dialect_name}:{id(bind_obj)}"
    _register_scope_key_finalizer(bind_obj, scope_key)
    return scope_key


def _lru_cache_get(
    cache: "OrderedDict[tuple[Any, ...], Dict[str, Any]]",
    key: tuple[Any, ...],
) -> Optional[Dict[str, Any]]:
    with _SUMMARY_CACHE_LOCK:
        cached = cache.get(key)
        if cached is None:
            return None
        cache.move_to_end(key)
        return deepcopy(cached)


def _lru_cache_put(
    cache: "OrderedDict[tuple[Any, ...], Dict[str, Any]]",
    key: tuple[Any, ...],
    value: Dict[str, Any],
    max_size: int,
) -> None:
    with _SUMMARY_CACHE_LOCK:
        cache[key] = deepcopy(value)
        cache.move_to_end(key)
        while len(cache) > max_size:
            cache.popitem(last=False)


class CustomQCWorkspaceService:
    def __init__(self, *, readonly: bool = False) -> None:
        if engine is None:
            raise RuntimeError("DATABASE_URL is not configured; custom qc workspace unavailable")
        # 新只读入口仅构造表定义；旧写入口仍保留既有兼容初始化行为。
        self._draft_table = _drafts_table(readonly=True) if readonly else _drafts_table()
        self._batch_job_table = _batch_jobs_table(readonly=True) if readonly else _batch_jobs_table()
        self._record_result_envelope_table = _record_result_envelopes_table()
        # 这里只构造表定义，不访问或创建迁移表；legacy 路径不会调用 repository。
        self._qc_dispatch = QCDispatchRepository(
            _session, self._batch_job_table, _draft_schema()
        )

    def _sync_mq_dispatch_status(
        self,
        session: Session,
        *,
        job_id: str,
        filters: Mapping[str, Any],
        to_status: str,
        from_statuses: Sequence[str],
    ) -> None:
        """与业务任务同事务同步 MQ 轻量状态；legacy 不访问新表。"""

        if DISPATCH_FILTER_KEY not in filters:
            return
        if qc_dispatch_mode_from_filters(filters) != "rabbitmq":
            return
        dispatch = self._qc_dispatch.get_dispatch(job_id, session=session)
        if dispatch is None:
            raise RuntimeError("MQ任务缺少持久调度身份")
        if dispatch.status == to_status:
            return
        if not self._qc_dispatch.transition_dispatch(
            job_id=job_id,
            generation=dispatch.generation,
            from_statuses=from_statuses,
            to_status=to_status,
            session=session,
        ):
            raise RuntimeError("MQ任务状态与业务任务状态不同步")

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
        parent_status = str(parent_job.get("status") or "").strip().lower()
        # 父任务已取消时，子任务的迟到收尾只能保留子任务自身结果；
        # 父任务读取投影不得重新将其解释为 completed。
        if parent_status == "canceled":
            aggregate_status = "canceled"
        elif running or queued:
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
        child_summaries = [child.get("summary") or {} for child in child_jobs]
        child_usage_states = [
            summary.get("luxian_0609_usage_observation_complete")
            for summary in child_summaries
        ]
        formal_luxian_parent = (
            (parent_job.get("filters") or {}).get("rule_set_key") == LUXIAN_0609_RULE_SET_KEY
        )
        if formal_luxian_parent and aggregate_status in {"completed", "failed"}:
            if include_items:
                filters = parent_job.get("filters") or {}
                scoped_rule_ids = list(filters.get("scoped_customer_rule_ids") or [])
                expected_rule_ids = [
                    *(scoped_rule_ids or list(filters.get("rule_ids") or [])),
                    *list(filters.get("gate_only_customer_rule_ids") or []),
                    *list(filters.get("paused_customer_rule_ids") or []),
                ]
                _, complete_refs = select_complete_record_items(
                    items=[
                        item for child in child_jobs for item in list(child.get("items") or [])
                    ],
                    failures=[
                        failure for child in child_jobs
                        for failure in list(child.get("failed_records") or [])
                    ],
                    expected_rule_ids=expected_rule_ids,
                )
                success_count = len(complete_refs)
                failed_count = max(
                    0, int(parent_job.get("total_records") or 0) - success_count
                )
            else:
                # 列表不加载结果项；使用父任务终态事务保存的病历计数。
                success_count = int(parent_job.get("success_count") or 0)
                failed_count = int(parent_job.get("failed_count") or 0)
        if any(isinstance(state, bool) for state in child_usage_states) or (
            formal_luxian_parent and canceled
        ):
            parent_summary["luxian_0609_usage_observation_complete"] = (
                len(child_usage_states) == len(child_jobs)
                and all(state is True for state in child_usage_states)
                and canceled == 0
            )
            parent_summary["luxian_0609_usage_unknown_executor_keys"] = sorted({
                key for summary in child_summaries
                for unknown_keys in [summary.get("luxian_0609_usage_unknown_executor_keys")]
                if isinstance(unknown_keys, (list, tuple))
                for key in unknown_keys if isinstance(key, str) and key
            })
        if any("execution_status" in summary for summary in child_summaries):
            completed_rules = sum(_to_int(summary.get("completed_rule_count")) for summary in child_summaries)
            failed_rules = sum(_to_int(summary.get("failed_rule_count")) for summary in child_summaries)
            parent_summary.update(completed_rule_count=completed_rules, failed_rule_count=failed_rules)
            if aggregate_status in {"failed", "completed"}:
                parent_summary["execution_status"] = (
                    "partial_failed" if completed_rules else "failed"
                ) if aggregate_status == "failed" else "completed"
            model_counts = None
            for child_summary in child_summaries:
                model_counts = _merge_luxian_model_execution_stats(
                    model_counts, _normalize_luxian_model_execution_stats(child_summary.get("model_execution_stats"))
                )
            if model_counts is not None:
                parent_summary["model_execution_stats"] = _build_luxian_model_execution_summary(model_counts)
        return {
            **parent_job,
            "status": aggregate_status,
            "summary": parent_summary,
            "progress": parent_summary.get("progress") or {},
            "children": child_jobs,
            "child_jobs": child_jobs,
            "cancellable": parent_status != "canceled" and any(
                status in {"queued", "running"} for status in statuses
            ),
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
            formal_luxian_parent = (
                (parent_job.get("filters") or {}).get("rule_set_key") == LUXIAN_0609_RULE_SET_KEY
            )
            canonical_items = [
                item
                for child in list(aggregate.get("children") or [])
                if isinstance(child, dict)
                for item in list(child.get("items") or [])
                if isinstance(item, dict)
            ] if status in {"completed", "failed"} else []
            partial_items: tuple[dict[str, Any], ...] = ()
            partial_refs: tuple[CaseRef, ...] = ()
            if formal_luxian_parent and status == "failed":
                filters = parent_job.get("filters") or {}
                scoped_rule_ids = list(filters.get("scoped_customer_rule_ids") or [])
                expected_rule_ids = [
                    *(scoped_rule_ids or list(filters.get("rule_ids") or [])),
                    *list(filters.get("gate_only_customer_rule_ids") or []),
                    *list(filters.get("paused_customer_rule_ids") or []),
                ]
                failures = [
                    failure
                    for child in list(aggregate.get("children") or [])
                    if isinstance(child, dict)
                    for failure in list(child.get("failed_records") or [])
                ]
                partial_items, partial_refs = select_complete_record_items(
                    items=canonical_items,
                    failures=failures,
                    expected_rule_ids=expected_rule_ids,
                )
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
            parent_conditions = [
                self._batch_job_table.c.id == normalized_parent_id,
                self._batch_job_table.c.status != "canceled",
            ]
            if formal_luxian_parent:
                parent_conditions.extend((
                    self._batch_job_table.c.status == row["status"],
                    self._batch_job_table.c.filters_json == row["filters_json"],
                    self._batch_job_table.c.summary_json == row["summary_json"],
                ))
            parent_update = session.execute(
                update(self._batch_job_table)
                .where(and_(*parent_conditions))
                .values(**values)
            )
            # 与子任务完成相同，父任务取消与最后一个子任务收尾可能竞争。
            # 只有状态条件更新成功，才允许在同一事务内写入正式 Envelope；
            # 否则不得由迟到刷新重新交付父任务结果。
            if getattr(parent_update, "rowcount", 0) != 1:
                session.rollback()
                return
            if formal_luxian_parent and status in {"completed", "failed"}:
                # 子任务写入时已完成合同校验；父任务终态只交付完整病历。
                # 删除与父任务发布在同一事务内，避免同一 root 下重复病例。
                session.execute(
                    self._record_result_envelope_table.delete().where(and_(
                        self._record_result_envelope_table.c.root_job_id == normalized_parent_id,
                        self._record_result_envelope_table.c.created_by == row["created_by"],
                        self._record_result_envelope_table.c.rule_set_key == LUXIAN_0609_RULE_SET_KEY,
                    ))
                )
            if status == "completed":
                self._write_record_result_envelopes(
                    session,
                    job_row=dict(row),
                    items=canonical_items,
                    now=now,
                )
                if canonical_items:
                    self._notify_saved_result(session, job_row=dict(row), now=now)
            elif formal_luxian_parent and status == "failed" and partial_items:
                self._write_record_result_envelopes(
                    session,
                    job_row=dict(row),
                    items=partial_items,
                    now=now,
                    expected_record_refs=partial_refs,
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

    @staticmethod
    def _record_repository() -> RecordRepository:
        return RecordRepository(session_factory=_session)

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
        institute_id: Optional[str] = None,
    ) -> WorkspaceListResult:
        return self._record_repository().list_records(
            scope=scope,
            department=department,
            doctor=doctor,
            date_field=date_field,
            start_date=start_date,
            end_date=end_date,
            keyword=keyword,
            page=page,
            page_size=page_size,
            **({"institute_id": institute_id} if institute_id is not None else {}),
        )

    def get_record_filters(
        self,
        *,
        scope: str,
        department: Optional[str],
        institute_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        return self._record_repository().get_record_filters(
            scope=scope,
            department=department,
            **({"institute_id": institute_id} if institute_id is not None else {}),
        )

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
        sync_scope: Optional[str] = None,
        institute_id: Optional[str] = None,
        _private_identity_collector: Callable[[str, Any], None] | None = None,
    ) -> List[Dict[str, Any]]:
        return self._record_repository().collect_records(
            scope=scope,
            department=department,
            doctor=doctor,
            date_field=date_field,
            start_date=start_date,
            end_date=end_date,
            keyword=keyword,
            record_ids=record_ids,
            record_refs=record_refs,
            sync_scope=sync_scope,
            **({"institute_id": institute_id} if institute_id is not None else {}),
            **({"_private_identity_collector": _private_identity_collector} if _private_identity_collector is not None else {}),
        )

    def collect_records_for_admission(self, **filters: Any) -> tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        """只读预检：不先丢弃场景不符病例，不创建任务；返回逐选择项受控原因。"""
        from .clinical_scene_admission import scene_rejection
        from .luxian_0609.clinical_material_policy import clinical_record_scene
        scope = filters["scope"]
        # 显式选择才保留不匹配行作逐例解释；纯筛选任务不能纳入范围外病例。
        read_scope = "all" if filters.get("record_refs") or filters.get("record_ids") else scope
        records = self.collect_records(**{**filters, "scope": read_scope})
        requested = list(normalize_case_refs(filters["record_refs"])) if filters.get("record_refs") else []
        positions = {ref: index for index, ref in enumerate(requested)}
        rejections = []
        for index, record in enumerate(records):
            code = scene_rejection(record, scope)
            if code:
                rejections.append({"selection_index": positions.get(CaseRef.from_mapping(record), index),
                    "code": code, "scene": clinical_record_scene(record) if record.get("qc_scope") in {"unknown", "running", "final"} else "unknown",
                    "discharge_state": (record.get("qc_discharge_state")
                        if record.get("qc_discharge_state") in {"inpatient", "discharged"} else "unknown"),
                    "discharge_time_status": (record.get("qc_discharge_time_status")
                        if record.get("qc_discharge_time_status") in {"missing", "present", "conflict"} else "unknown")})
        return records, rejections

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
        institute_id: Optional[str] = None,
    ) -> int:
        return self._record_repository().count_records(
            scope=scope,
            department=department,
            doctor=doctor,
            date_field=date_field,
            start_date=start_date,
            end_date=end_date,
            keyword=keyword,
            record_ids=record_ids,
            record_refs=record_refs,
            **({"institute_id": institute_id} if institute_id is not None else {}),
        )

    def hydrate_records_with_medical_text(
        self,
        records: Sequence[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        return self._record_repository().hydrate_records_with_medical_text(records)

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
        scheduled_run_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        session = _session()
        try:
            now = _now_utc()
            job_id = str(uuid.uuid4())
            if scheduled_run_id is not None:
                from .daily_qc.contracts import job_identity

                if (filters.get("daily_schedule") or {}).get("run_id") != scheduled_run_id:
                    raise ValueError("scheduled_job_identity_mismatch")
                job_id = job_identity(scheduled_run_id)
                existing = self.get_scheduled_batch_job(scheduled_run_id=scheduled_run_id)
                if existing:
                    if existing["created_by"] != created_by:
                        raise ValueError("scheduled_job_owner_mismatch")
                    return {**existing, "schedule_submission_reused": True}
            normalized_draft_ids = [item for item in _normalize_string_list(list(draft_ids or [])) if item]
            if not normalized_draft_ids:
                current_draft_id = _safe_text(draft.get("id"))
                if current_draft_id:
                    normalized_draft_ids = [current_draft_id]
            normalized_execution_mode = _normalize_execution_mode(execution_mode)
            if normalized_execution_mode == "single" and len(normalized_draft_ids) > 1:
                normalized_execution_mode = "multi"
            normalized_run_mode = _normalize_run_mode(run_mode)
            normalized_job_kind = _safe_text(job_kind, "leaf").lower() or "leaf"
            base_filters = dict(filters or {})
            if "retry_lineage" in base_filters:
                raise ValueError("retry_lineage 由任务服务生成，调用方不得注入")
            if record_refs:
                base_filters["record_refs"]=[ref.as_dict() for ref in normalize_case_refs(record_refs)]
            from .clinical_sources import freeze
            freeze(base_filters)
            from .material_admission import preflight_new_task
            preflight_new_task(base_filters)
            if DISPATCH_FILTER_KEY in base_filters:
                raise ValueError("qc_dispatch 由任务服务冻结，调用方不得注入")
            formal_0609 = base_filters.get("rule_set_key") == LUXIAN_0609_RULE_SET_KEY
            settings = get_settings()
            try:
                dispatch_mode = effective_dispatch_mode(settings) if formal_0609 else "legacy"
            except DispatchControlError as exc:
                raise QCDispatchEntrypointError(str(exc)) from None
            if dispatch_mode == "rabbitmq":
                # 创建阶段重新读取开关并验证实际模型身份，防止入口检查后热切换漏校验。
                assert_new_qc_task_dispatch_ready(
                    eligible_for_rabbitmq=True,
                    family_parent=normalized_job_kind == "parent",
                    task_runtime_snapshot=base_filters.get(LX0609_TASK_RUNTIME_FILTER_KEY),
                    settings=settings, resolved_mode=dispatch_mode,
                )
                # 必须在业务任务 insert 前确认迁移完整；不能先创建任务再补 Outbox。
                self._qc_dispatch.assert_ready(session)
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
                **base_filters,
                "draft_ids": normalized_draft_ids,
                "execution_mode": normalized_execution_mode,
                "run_mode": normalized_run_mode,
                **(
                    {DISPATCH_FILTER_KEY: dispatch_filter_payload("rabbitmq")}
                    if dispatch_mode == "rabbitmq"
                    else {}
                ),
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
                "job_kind": normalized_job_kind,
                "parent_job_id": _safe_text(parent_job_id) or None,
                "child_job_ids_json": _safe_json_dumps(list(child_job_ids or [])),
                "child_summary_json": _safe_json_dumps(child_summary or {}),
                "family_key": _safe_text(family_key) or None,
                "family_name": _safe_text(family_name) or None,
            }
            session.execute(self._batch_job_table.insert().values(**row_payload))
            if dispatch_mode == "rabbitmq":
                self._qc_dispatch.add_dispatch(
                    session,
                    job_id=job_id,
                    mode="rabbitmq",
                    enqueue_leaf=normalized_job_kind != "parent",
                )
            session.commit()
            return self.get_batch_job(job_id=job_id, created_by=created_by) or _row_to_batch_job(row_payload)
        except sa.exc.IntegrityError:
            session.rollback()
            if scheduled_run_id is not None:
                existing = self.get_scheduled_batch_job(scheduled_run_id=scheduled_run_id)
                if existing and existing["created_by"] == created_by:
                    return {**existing, "schedule_submission_reused": True}
            raise
        finally:
            session.close()

    def get_scheduled_batch_job(self, *, scheduled_run_id: str) -> Optional[Dict[str, Any]]:
        """恢复只读任务身份和状态，不载入结果大JSON。"""
        from .daily_qc.contracts import job_identity

        with _session() as session:
            row = session.execute(select(self._batch_job_table.c.id, self._batch_job_table.c.status,
                self._batch_job_table.c.created_by, self._batch_job_table.c.filters_json).where(
                self._batch_job_table.c.id == job_identity(scheduled_run_id))).mappings().first()
            if not row:
                return None
            filters = _safe_json_loads(row["filters_json"], {})
            if (filters.get("daily_schedule") or {}).get("run_id") != scheduled_run_id:
                raise ValueError("scheduled_job_identity_mismatch")
            return {"id": row["id"], "status": row["status"], "created_by": row["created_by"], "filters": filters}

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
            job = self._aggregate_parent_job(session, _row_to_batch_job(dict(row)))
            return {**job, "_claim_filters_json": row.get("filters_json")}
        finally:
            session.close()

    def list_queued_luxian_0609_batch_job_ids(
        self, *, dispatch_mode: str = "legacy"
    ) -> tuple[str, ...]:
        """按冻结调度身份列出正式 LX0609 执行任务。"""

        if dispatch_mode not in {"legacy", "rabbitmq"}:
            raise ValueError("invalid qc dispatch mode")

        session = _session()
        try:
            rows = session.execute(
                select(
                    self._batch_job_table.c.id,
                    self._batch_job_table.c.job_kind,
                    self._batch_job_table.c.filters_json,
                )
                .where(self._batch_job_table.c.status == "queued")
                .order_by(asc(self._batch_job_table.c.created_at))
            ).mappings().all()
            job_ids: list[str] = []
            for row in rows:
                if _safe_text(row.get("job_kind")).lower() == "parent":
                    continue
                filters = _safe_json_loads(row.get("filters_json"), {})
                if not isinstance(filters, dict) or filters.get("rule_set_key") != LUXIAN_0609_RULE_SET_KEY:
                    continue
                if qc_dispatch_mode_from_filters(filters) == dispatch_mode:
                    job_ids.append(str(row["id"]))
            return tuple(job_ids)
        finally:
            session.close()

    def list_recent_batch_job_candidates(
        self, *, created_by: str, cutoff: datetime,
    ) -> List[Dict[str, Any]]:
        """提交去重仅读取身份、状态及范围，不加载历史结果大对象。"""
        session = _session()
        table = self._batch_job_table
        try:
            rows = session.execute(
                select(table.c.id, table.c.status, table.c.created_at, table.c.filters_json)
                .where(and_(
                    table.c.created_by == created_by,
                    table.c.created_at >= cutoff,
                    or_(table.c.parent_job_id.is_(None), table.c.parent_job_id == ""),
                ))
                .order_by(desc(table.c.created_at)).limit(100)
            ).mappings().all()
            return [{
                "id": row["id"], "status": row["status"], "created_at": row["created_at"],
                "filters": _safe_json_loads(row["filters_json"], {}),
            } for row in rows]
        finally:
            session.close()

    def _batch_job_list_where(
        self,
        *,
        created_by: str,
        draft_id: Optional[str] = None,
        status: Optional[str] = None,
        scope: Optional[str] = None,
        query: Optional[str] = None,
        created_start_date: Optional[str] = None,
        created_end_date: Optional[str] = None,
        record_id: Optional[str] = None,
        include_children: bool = False,
    ):
        """任务列表的筛选条件；完整列表与概览列表共用，保证两者筛选口径一致。"""

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
        # 筛选日期按北京时间解释，任务时间戳按无时区 UTC 存储。
        if start:
            clauses.append(self._batch_job_table.c.created_at >= _task_date_utc_boundary(start))
        if end:
            clauses.append(self._batch_job_table.c.created_at < _task_date_utc_boundary(end, next_day=True))
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
        return and_(*clauses)

    def list_batch_job_overviews(
        self,
        *,
        created_by: str,
        status: Optional[str] = None,
        scope: Optional[str] = None,
        query: Optional[str] = None,
        created_start_date: Optional[str] = None,
        created_end_date: Optional[str] = None,
        record_id: Optional[str] = None,
        page: int = 1,
        page_size: int = DEFAULT_BATCH_JOB_PAGE_SIZE,
    ) -> WorkspaceBatchJobListResult:
        """质控记录页的轻量任务列表：只读任务元数据，不读取结果明细与完整摘要。

        完整摘要（含全部规则结果）单个可达数十 MB；仅读取或在库内解析一次就要数秒，
        列表逐行做客户安全投影要十余秒。概览因此完全不读 summary_json / items_json，
        进度取自病历计数列；失败任务只用结果计数列判断“是否已有结果”，不返回计数本身。
        """

        table = self._batch_job_table
        where_clause = self._batch_job_list_where(
            created_by=created_by,
            status=status,
            scope=scope,
            query=query,
            created_start_date=created_start_date,
            created_end_date=created_end_date,
            record_id=record_id,
        )
        columns = (
            table.c.id,
            table.c.draft_id,
            table.c.rule_code,
            table.c.rule_name,
            table.c.scene,
            table.c.scope,
            table.c.status,
            table.c.job_kind,
            table.c.filters_json,
            table.c.created_at,
            table.c.started_at,
            table.c.finished_at,
            table.c.updated_at,
            table.c.total_records,
            table.c.success_count,
            table.c.failed_count,
            table.c.issue_records,
            table.c.compliant_records,
        )
        session = _session()
        try:
            total = int(
                session.execute(select(func.count()).select_from(table).where(where_clause)).scalar()
                or 0
            )
            rows = (
                session.execute(
                    select(*columns)
                    .where(where_clause)
                    .order_by(desc(table.c.created_at))
                    .offset(max(page - 1, 0) * page_size)
                    .limit(page_size)
                )
                .mappings()
                .all()
            )
        finally:
            session.close()
        items: List[Dict[str, Any]] = []
        for raw_row in rows:
            row = dict(raw_row)
            filters = _safe_json_loads(row.get("filters_json"), {})
            items.append(
                {
                    "id": _safe_text(row.get("id")),
                    "draft_id": _safe_text(row.get("draft_id")),
                    "rule_code": _safe_text(row.get("rule_code")),
                    "rule_name": _safe_text(row.get("rule_name")),
                    "scene": _safe_text(row.get("scene")),
                    "scope": _safe_text(row.get("scope")),
                    "status": _safe_text(row.get("status"), "queued").lower(),
                    "job_kind": _safe_text(row.get("job_kind")),
                    "filters": filters if isinstance(filters, dict) else {},
                    "has_results": _to_int(row.get("issue_records")) > 0
                    or _to_int(row.get("compliant_records")) > 0,
                    "created_at": row.get("created_at"),
                    "started_at": row.get("started_at"),
                    "finished_at": row.get("finished_at"),
                    "updated_at": row.get("updated_at"),
                    "total_records": _to_int(row.get("total_records")),
                    "success_count": _to_int(row.get("success_count")),
                    "failed_count": _to_int(row.get("failed_count")),
                }
            )
        return WorkspaceBatchJobListResult(items=items, total=total, page=page, page_size=page_size)

    @staticmethod
    def _batch_job_matches_institute_scope(
        job: Mapping[str, Any],
        institute_scope: Optional[str],
    ) -> bool:
        if institute_scope is None:
            return True
        if not isinstance(job, Mapping):
            return False
        filters = job.get("filters") if isinstance(job.get("filters"), Mapping) else {}
        record_refs = filters.get("record_refs")
        items = job.get("items")
        checked = False
        if isinstance(record_refs, list) and record_refs:
            for ref in record_refs:
                if not isinstance(ref, Mapping):
                    return False
                ref_inst = ref.get("institute_id")
                if not isinstance(ref_inst, str) or not ref_inst.strip() or ref_inst != institute_scope:
                    return False
            checked = True
        if isinstance(items, list) and items:
            for item in items:
                if not isinstance(item, Mapping):
                    return False
                item_inst = item.get("institute_id")
                if item_inst is not None:
                    if not isinstance(item_inst, str) or not item_inst.strip() or item_inst != institute_scope:
                        return False
                    checked = True
                elif not checked:
                    return False
        if checked:
            return True
        filter_inst = filters.get("institute_id")
        if isinstance(filter_inst, str) and filter_inst.strip() and filter_inst == institute_scope:
            if int(job.get("total_records") or 0) == 0:
                return True
        return False

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
        institute_id: Optional[str] = None,
        page: int = 1,
        page_size: int = DEFAULT_BATCH_JOB_PAGE_SIZE,
    ) -> WorkspaceBatchJobListResult:
        session = _session()
        try:
            where_clause = self._batch_job_list_where(
                created_by=created_by,
                draft_id=draft_id,
                status=status,
                scope=scope,
                query=query,
                created_start_date=created_start_date,
                created_end_date=created_end_date,
                record_id=record_id,
                include_children=include_children,
            )
            executor_value = _safe_text(executor_type).lower()
            institute_scope = _safe_text(institute_id) or None
            enable_runtime_filter = (
                executor_value in {"program", "llm"}
                or cache_hit is not None
                or institute_scope is not None
            )

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
            if institute_scope is not None:
                filtered_items = [
                    item
                    for item in filtered_items
                    if self._batch_job_matches_institute_scope(item, institute_scope)
                ]
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
        require_donghua_proof: bool = False,
    ) -> Dict[str, Any]:
        """读取一份病历当前规则代次的唯一客户结果。

        三坐标、规则版本及任务冻结范围共同约束候选；定向子集不得替代全量任务。
        完整结果沿用 Canonical Envelope，最新失败全量任务则只读展示同次已保存、
        通过逐条合同校验的结果及独立失败提示，不与其他任务拼接或标为完整交付。
        """

        request = self._luxian_0609_record_result_request(
            institute_id=institute_id,
            patient_id=patient_id,
            visit_id=visit_id,
            rule_set_key=rule_set_key,
            rule_set_version=rule_set_version,
            expected_rule_ids=expected_rule_ids,
        )
        expected_rule_ids_for_count = request["expected_rule_ids_for_count"]
        session = _session()
        try:
            candidates = self._luxian_0609_record_result_candidates(session, request)
            selection = select_latest_authoritative_record_result_job(
                candidates,
                record_id=request["visit_id"],
                rule_set_key=request["rule_set_key"],
                rule_set_version=request["rule_set_version"],
                prefer_full_scope=True,
            )
            if selection.state != "ready" or not isinstance(selection.job, dict):
                if require_donghua_proof:
                    from fastapi import HTTPException
                    raise HTTPException(403, "缺少可核验的历史结果机构归属")
                return _record_result_unselected(selection.state, selection.reason_code, expected_rule_ids_for_count)
            return self._luxian_0609_record_result_for_job(
                session, request, selection.job, require_donghua_proof=require_donghua_proof,
            )
        finally:
            session.close()

    def _luxian_0609_record_result_request(
        self,
        *,
        institute_id: str,
        patient_id: str,
        visit_id: str,
        rule_set_key: str,
        rule_set_version: str,
        expected_rule_ids: Optional[Sequence[str]],
    ) -> Dict[str, Any]:
        """单病历结果读取的身份与规则范围归一化；默认视图与历史视图共用。"""

        normalized_institute_id = _safe_text(institute_id)
        normalized_patient_id = _safe_text(patient_id)
        normalized_visit_id = _safe_text(visit_id)
        normalized_rule_set_key = _safe_text(rule_set_key)
        normalized_rule_set_version = _safe_text(rule_set_version)
        expected_rule_ids_for_count = [
            _safe_text(rule_id).upper()
            for rule_id in list(expected_rule_ids or [])
            if _safe_text(rule_id)
            and _safe_text(rule_id).upper() not in LUXIAN_0609_CUSTOMER_EXCLUDED_RULE_IDS
        ]
        if not expected_rule_ids_for_count:
            expected_rule_ids_for_count = [
                _safe_text(item.get("rule_id") or item.get("rule_code")).upper()
                for item in load_luxian_0609_rules()
                if _safe_text(item.get("rule_id") or item.get("rule_code"))
                and _safe_text(item.get("rule_id") or item.get("rule_code")).upper()
                not in LUXIAN_0609_CUSTOMER_EXCLUDED_RULE_IDS
            ]
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

        return {
            "institute_id": normalized_institute_id,
            "patient_id": normalized_patient_id,
            "visit_id": normalized_visit_id,
            "rule_set_key": normalized_rule_set_key,
            "rule_set_version": normalized_rule_set_version,
            "expected_rule_ids": expected_rule_ids,
            "expected_rule_ids_for_count": expected_rule_ids_for_count,
            "case_ref": CaseRef(normalized_institute_id, normalized_patient_id, normalized_visit_id),
        }

    def _luxian_0609_record_result_candidates(
        self, session: Session, request: Mapping[str, Any],
    ) -> List[Dict[str, Any]]:
        """按三坐标、规则版本与冻结范围列出可选轮次，只读轻量字段。"""

        normalized_institute_id = request["institute_id"]
        normalized_patient_id = request["patient_id"]
        normalized_visit_id = request["visit_id"]
        normalized_rule_set_key = request["rule_set_key"]
        normalized_rule_set_version = request["rule_set_version"]
        case_ref = request["case_ref"]
        root_rows = (
            session.execute(
                select(
                    self._batch_job_table.c.id,
                    self._batch_job_table.c.filters_json,
                    self._batch_job_table.c.record_ids_json,
                    self._batch_job_table.c.finished_at,
                    self._batch_job_table.c.created_at,
                    self._batch_job_table.c.status,
                    sa.literal(False).label("saved_partial_attempt"),
                )
                .join(
                    self._record_result_envelope_table,
                    self._record_result_envelope_table.c.root_job_id
                    == self._batch_job_table.c.id,
                )
                .where(
                    and_(
                        self._batch_job_table.c.status.in_(
                            ("completed", "failed", "running", "queued", "canceled")
                        ),
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
                .union_all(
                    select(
                        self._batch_job_table.c.id,
                        self._batch_job_table.c.filters_json,
                        self._batch_job_table.c.record_ids_json,
                        self._batch_job_table.c.finished_at,
                        self._batch_job_table.c.created_at,
                        self._batch_job_table.c.status,
                        sa.literal(True).label("saved_partial_attempt"),
                    ).where(and_(
                        self._batch_job_table.c.status == "failed",
                        or_(self._batch_job_table.c.parent_job_id.is_(None),
                            self._batch_job_table.c.parent_job_id == ""),
                        self._batch_job_table.c.record_ids_json.contains(
                            json.dumps(normalized_visit_id, ensure_ascii=False), autoescape=True,
                        ),
                    ))
                )
                .order_by(
                    desc("finished_at"), desc("created_at"),
                )
            )
            .mappings()
            .all()
        )
        candidates = []
        canonical_job_ids = {row["id"] for row in root_rows if not row.get("saved_partial_attempt")}
        for row in root_rows:
            # 先用轻量身份与冻结范围选轮，只加载选中任务的结果大字段。
            candidate = _row_to_batch_job(dict(row))
            filters = candidate.get("filters") or {}
            from .clinical_sources import job_matches
            if not job_matches(filters, normalized_patient_id, normalized_visit_id):
                continue
            saved_partial_attempt = bool(row.get("saved_partial_attempt"))
            if saved_partial_attempt:
                if row["id"] in canonical_job_ids:
                    continue
                # SQL 仅作就诊号预筛；无 Envelope 时必须由持久三坐标证明归属。
                refs = filters.get("record_refs")
                if not isinstance(refs, list) or case_ref not in {
                    CaseRef.from_mapping(ref) for ref in refs if isinstance(ref, Mapping)
                }:
                    continue
            try:
                scope = saved_record_rule_scope(filters, case_ref)
            except (ValueError, TypeError):
                if saved_partial_attempt:
                    continue
                scope = []  # 无冻结范围的旧 Envelope 保留原合同兼容读取。
            candidate["result_rule_scope"] = scope
            candidate["saved_partial_attempt"] = saved_partial_attempt
            if saved_partial_attempt:
                candidate["saved_filters_json"] = row["filters_json"]
            candidate["result_scope_kind"] = (
                "targeted" if filters.get("selected_rule_ids") or filters.get("record_rule_map")
                else "full" if "selected_rule_ids" in filters else "unknown"
            )
            if not all(filters.get(key) for key in ("rule_set_key", "rule_set_version")):
                # 仅旧任务缺少 filters 身份时加载 summary，保留逐字段兼容回退。
                summary_rows = session.execute(
                    select(self._batch_job_table.c.summary_json)
                    .where(self._batch_job_table.c.id == candidate["id"])
                ).mappings().all()
                summary = _safe_json_loads(
                    summary_rows[0].get("summary_json") if summary_rows else None, None
                )
                candidate["summary"] = summary if isinstance(summary, dict) else None
            if _safe_text(candidate.get("status")).lower() != "completed":
                # 选择器使用 completed 表示可选读。独立 Envelope 或失败任务的
                # 结果校验在后面分别完成；部分失败通过 execution_status 明示，
                # 不修改持久任务状态或声称整例已经交付。
                candidate = {**candidate, "status": "completed"}
            candidates.append(candidate)
        return candidates

    def _luxian_0609_record_result_for_job(
        self,
        session: Session,
        request: Mapping[str, Any],
        selected_job: Dict[str, Any],
        *,
        require_donghua_proof: bool = False,
    ) -> Dict[str, Any]:
        """读取并校验一个已选轮次的该病例结果；授权失败抛 403，不换读其他轮次。"""

        normalized_institute_id = request["institute_id"]
        normalized_patient_id = request["patient_id"]
        normalized_visit_id = request["visit_id"]
        normalized_rule_set_key = request["rule_set_key"]
        normalized_rule_set_version = request["rule_set_version"]
        case_ref = request["case_ref"]
        expected_rule_ids = request["expected_rule_ids"]
        expected_rule_ids_for_count = list(request["expected_rule_ids_for_count"])
        if require_donghua_proof:
            from .saved_result_access import require_selected_donghua_job
            require_selected_donghua_job(session, self._batch_job_table, selected_job["id"], tuple(case_ref))
        if not expected_rule_ids and selected_job.get("result_rule_scope"):
            expected_rule_ids_for_count = [
                rule_id for rule_id in selected_job["result_rule_scope"]
                if rule_id not in LUXIAN_0609_CUSTOMER_EXCLUDED_RULE_IDS
            ]
        partial_details: Dict[str, Any] = {}
        try:
            envelope = self._load_record_result_envelope_items(
                session,
                root_job_id=_safe_text(selected_job.get("id")),
                institute_id=normalized_institute_id,
                patient_id=normalized_patient_id,
                visit_id=normalized_visit_id,
                rule_set_key=normalized_rule_set_key,
                rule_set_version=normalized_rule_set_version,
            )
            if not envelope and selected_job.get("saved_partial_attempt"):
                saved = session.execute(select(
                    self._batch_job_table.c.items_json,
                    self._batch_job_table.c.summary_json,
                    self._batch_job_table.c.failed_records_json,
                ).where(and_(
                    self._batch_job_table.c.id == selected_job["id"],
                    self._batch_job_table.c.status == "failed",
                    self._batch_job_table.c.filters_json == selected_job["saved_filters_json"],
                ))).mappings().one_or_none()
                if saved is None:
                    raise ValueError("saved_partial_task_changed")
                projection_key = customer_safe_projection_key()
                partial_details = read_saved_partial_record_row(
                    saved, ref=case_ref, expected_rules=selected_job["result_rule_scope"],
                    projection_key=projection_key,
                    projector=lambda item: self._envelope_item_from_rule_result(item, hmac_key=projection_key),
                )
                if partial_details.get("failure_stage"):
                    return {
                        **_record_result_unselected(
                            "technical_error", partial_details["reason_code"], expected_rule_ids_for_count,
                        ),
                        "failure_stage": partial_details["failure_stage"],
                        "data_origin": "saved_partial_task",
                        "job_id": _safe_text(selected_job.get("id")),
                        "completed_at": _record_result_completed_at(selected_job),
                    }
                envelope = partial_details
        except ValueError as exc:
            # 已发布合同损坏沿用既有结构化失败，不变成未找到，也不吞其他错误。
            if str(exc) != LX0609_CUSTOMER_RESULT_CONTRACT_ERROR and not str(exc).startswith("saved_partial_"):
                raise
            return {
                "schema_version": "lx0609-single-record-result-v1",
                "state": "technical_error",
                "reason_code": "saved_partial_result_invalid" if selected_job.get("saved_partial_attempt") else "canonical_result_envelope_invalid",
                "data_origin": "saved_partial_task" if selected_job.get("saved_partial_attempt") else "canonical_result_envelope",
                "record_ref": "",
                "job_id": _safe_text(selected_job.get("id")),
                "items": [],
                "expected_rule_count": len(expected_rule_ids_for_count),
                "result_rule_count": 0,
                "is_complete": False,
            }
        if not envelope:
            return {
                "schema_version": "lx0609-single-record-result-v1",
                "state": "technical_error",
                "reason_code": "canonical_result_envelope_missing",
                "data_origin": "canonical_result_envelope",
                "record_ref": "",
                "job_id": _safe_text(selected_job.get("id")),
                "items": [],
                "expected_rule_count": len(expected_rule_ids_for_count),
                "result_rule_count": 0,
                "is_complete": False,
            }
        raw_items = envelope.get("items")
        resolved_expected_rule_ids = list(
            dict.fromkeys(
                _safe_text(rule_id).upper()
                for rule_id in expected_rule_ids_for_count
                if _safe_text(rule_id)
            )
        )
        if not resolved_expected_rule_ids:
            resolved_expected_rule_ids = [
                _safe_text(item.get("rule_id") or item.get("rule_code")).upper()
                for item in load_luxian_0609_rules()
                if _safe_text(item.get("rule_id") or item.get("rule_code"))
                and _safe_text(item.get("rule_id") or item.get("rule_code")).upper()
                not in LUXIAN_0609_CUSTOMER_EXCLUDED_RULE_IDS
            ]
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
        raw_rule_ids = [
            _safe_text(item.get("rule_id") or item.get("rule_code")).upper()
            for item in raw_items
        ]
        if normalized_rule_set_key == LUXIAN_0609_RULE_SET_KEY:
            unexpected_rule_ids = sorted(
                set(raw_rule_ids) - _luxian_0609_catalog_rule_ids()
            )
            if unexpected_rule_ids:
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
        items = [
            dict(item)
            for item in raw_items
            if _safe_text(item.get("rule_id") or item.get("rule_code")).upper()
            not in LUXIAN_0609_CUSTOMER_EXCLUDED_RULE_IDS
        ]
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
        # 单病历结果页面向客户展示结论与建议：沿用与批详情、导出相同的
        # 客户文本过滤合同；坐标仅用于比对，不写入响应。
        case_identity = {
            "institute_id": normalized_institute_id,
            "patient_id": normalized_patient_id,
            "visit_id": normalized_visit_id,
        }
        for item, rule_id in zip(items, valid_rule_ids):
            projected_item = _customer_filtered_saved_text(item, identity=case_identity)
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
            "data_origin": "saved_partial_task" if partial_details else "canonical_result_envelope",
            "record_ref": _safe_text(envelope.get("record_ref")),
            "job_id": _safe_text(selected_job.get("id")),
            "completed_at": _record_result_completed_at(selected_job),
            "rule_set_key": normalized_rule_set_key,
            "rule_set_version": normalized_rule_set_version,
            "result_scope": selected_job.get("result_scope_kind", "unknown"),
            "items": projected_items,
            "expected_rule_count": len(resolved_expected_rule_ids),
            "result_rule_count": len(items),
            "is_complete": not partial_details and not missing_rule_ids and not conflicting_rule_ids,
            "missing_rule_ids": missing_rule_ids,
            "conflicting_rule_ids": sorted(conflicting_rule_ids),
            **{key: value for key, value in partial_details.items() if key not in {"items", "record_ref"}},
        }

    def build_previous_valid_record_result_dto(
        self,
        *,
        institute_id: str,
        patient_id: str,
        visit_id: str,
        anchor_job_id: str = "",
        rule_set_key: str = LUXIAN_0609_RULE_SET_KEY,
        rule_set_version: str = RULE_SET_VERSION,
        expected_rule_ids: Optional[Sequence[str]] = None,
        require_donghua_proof: bool = False,
    ) -> Dict[str, Any]:
        """查找同一病例原轮次保存的有效结果与可读冻结材料。"""

        request = self._luxian_0609_record_result_request(
            institute_id=institute_id,
            patient_id=patient_id,
            visit_id=visit_id,
            rule_set_key=rule_set_key,
            rule_set_version=rule_set_version,
            expected_rule_ids=expected_rule_ids,
        )
        anchor = _safe_text(anchor_job_id)

        def select(pool: Sequence[Dict[str, Any]]):
            return select_latest_authoritative_record_result_job(
                pool,
                record_id=request["visit_id"],
                rule_set_key=request["rule_set_key"],
                rule_set_version=request["rule_set_version"],
                prefer_full_scope=True,
            )

        from .saved_result_access import require_selected_donghua_job, selected_history_material_is_available

        session = _session()
        try:
            identity = tuple(request["case_ref"])
            remaining = self._luxian_0609_record_result_candidates(session, request)
            saved_results: dict[str, dict[str, Any] | None] = {}

            def available_result(candidate: Dict[str, Any]) -> dict[str, Any] | None:
                job_id = candidate["id"]
                if job_id not in saved_results:
                    saved_results[job_id] = None
                    if selected_history_material_is_available(
                        session, self._batch_job_table, job_id, identity,
                        require_donghua_proof=require_donghua_proof,
                    ):
                        result = self._luxian_0609_record_result_for_job(session, request, candidate)
                        if result.get("state") == "ready" and result.get("items") and result.get("record_ref"):
                            saved_results[job_id] = result
                        elif not result.get("failure_stage"):
                            logging.getLogger(__name__).warning(
                                "LX0609 历史结果跳过不可用轮次 job_id=%s state=%s reason_code=%s",
                                job_id, result.get("state"), result.get("reason_code"),
                            )
                return saved_results[job_id]

            latest = select(remaining)

            if latest.state == "ready" and isinstance(latest.job, dict):
                latest_job_id = latest.job["id"]
                if anchor:
                    if latest_job_id != anchor:
                        if require_donghua_proof:
                            require_selected_donghua_job(session, self._batch_job_table, anchor, identity)
                        raise PreviousRecordResultAnchorChanged()
                    latest_result = self._luxian_0609_record_result_for_job(
                        session, request, latest.job, require_donghua_proof=require_donghua_proof,
                    )
                    if latest_result.get("failure_stage") not in MATERIAL_PREPARATION_FAILURE_STAGES:
                        raise PreviousRecordResultAnchorChanged()
                # 以默认轮次为界，即使无锚点也不把正常的最新结果标成历史。
                latest_generation = _generation_key(latest.job)
                remaining = [candidate for candidate in remaining if _generation_key(candidate) < latest_generation]
            elif anchor:
                if require_donghua_proof:
                    # 无法核验的选轮分歧不能向当前账号显示，也不能以猜测的锚点继续。
                    require_selected_donghua_job(session, self._batch_job_table, anchor, identity)
                raise PreviousRecordResultAnchorChanged()

            while remaining:
                selection = select(remaining)
                if selection.state == "technical_error":
                    # 只有当前账号可核验且实际保存了有效结果的轮次参与历史冲突。
                    remaining = [candidate for candidate in remaining if available_result(candidate)]
                    selection = select(remaining)
                    if selection.state == "technical_error":
                        raise PreviousRecordResultConflict(selection.reason_code)
                if selection.state != "ready" or not isinstance(selection.job, dict):
                    break
                job_id = selection.job["id"]
                remaining = [candidate for candidate in remaining if candidate["id"] != job_id]
                result = available_result(selection.job)
                if result is not None:
                    return {**result, "result_view": "previous_valid", "read_only": True}
            return {
                **_record_result_unselected(
                    "not_found", "previous_record_result_not_found", request["expected_rule_ids_for_count"],
                ),
                "result_view": "previous_valid",
                "read_only": True,
            }
        finally:
            session.close()

    def _read_luxian_summary_watermark(
        self,
        session: Session,
    ) -> Optional[tuple[Any, ...]]:
        """读取质控任务与信封表的每行版本水印，零 TOAST 读取且感知任意历史行更新。"""
        try:
            from ..database import clinical_connection as _clinical_conn

            active_sel = _clinical_conn.current_selection()
            clinical_binding = (
                None if active_sel is None else str(active_sel.get("binding") or "")
            )
            bind = session.get_bind() if hasattr(session, "get_bind") else None
            dialect_name = getattr(getattr(bind, "dialect", None), "name", "")

            job_col_names = (
                "id",
                "status",
                "updated_at",
                "finished_at",
                "created_at",
                "total_records",
                "success_count",
                "failed_count",
                "issue_records",
                "compliant_records",
            )
            env_col_names = (
                "id",
                "root_job_id",
                "institute_id",
                "patient_id",
                "visit_id",
                "rule_set_key",
                "rule_set_version",
                "updated_at",
            )
            job_cols = [
                self._batch_job_table.c[name]
                for name in job_col_names
                if name in self._batch_job_table.c
            ]
            env_cols = [
                self._record_result_envelope_table.c[name]
                for name in env_col_names
                if name in self._record_result_envelope_table.c
            ]
            if not job_cols or not env_cols:
                return None

            def _read_signatures() -> Optional[tuple[Any, ...]]:
                if dialect_name == "postgresql":
                    def _pg_row_digest(table: Table, cols: list[Any]) -> Optional[tuple[str, ...]]:
                        row_sig = sa.func.concat_ws(
                            "|",
                            *(sa.func.coalesce(sa.cast(col, sa.String), "") for col in cols),
                        )
                        row_hash = sa.func.hashtext(row_sig)
                        agg = session.execute(
                            select(
                                sa.func.count().label("cnt"),
                                sa.func.coalesce(
                                    sa.func.sum(sa.cast(row_hash, sa.BigInteger)),
                                    0,
                                ).label("sum_hash"),
                                sa.func.coalesce(
                                    sa.func.bit_xor(row_hash),
                                    0,
                                ).label("xor_hash"),
                            ).select_from(table)
                        ).first()
                        if agg is None:
                            return None
                        return tuple(str(v) if v is not None else "" for v in agg)

                    job_sig = _pg_row_digest(self._batch_job_table, job_cols)
                    env_sig = _pg_row_digest(self._record_result_envelope_table, env_cols)
                    if job_sig is None or env_sig is None:
                        return None
                    return (clinical_binding, job_sig, env_sig)

                def _python_row_digest(table: Table, cols: list[Any]) -> tuple[str, ...]:
                    rows = session.execute(
                        select(*cols).order_by(table.c.id.asc())
                    ).all()
                    hasher = hashlib.blake2b(digest_size=16)
                    for row in rows:
                        hasher.update(
                            "|".join("" if v is None else str(v) for v in row).encode("utf-8")
                        )
                        hasher.update(b"\n")
                    return (str(len(rows)), hasher.hexdigest())

                return (
                    clinical_binding,
                    _python_row_digest(self._batch_job_table, job_cols),
                    _python_row_digest(self._record_result_envelope_table, env_cols),
                )

            # 在 SAVEPOINT 内读取水印，防止缺表、旧版 PG 缺 bit_xor 或权限异常毒化主事务。
            begin_nested = getattr(session, "begin_nested", None)
            if callable(begin_nested):
                with begin_nested():
                    return _read_signatures()
            return _read_signatures()
        except Exception:
            return None

    def build_luxian_0609_completed_record_result_summaries(
        self,
        *,
        record_refs: Sequence[Mapping[str, Any]],
        rule_set_key: str = LUXIAN_0609_RULE_SET_KEY,
        rule_set_version: str = RULE_SET_VERSION,
        session_factory: Optional[Callable[[], Session]] = None,
        include_items: bool = False,
        include_rule_set_context: bool = False,
        include_latest_partial: bool = False,
        log_read_timing: bool = False,
    ) -> Dict[tuple[str, str, str], Dict[str, Any]]:
        """批量读取病历池可展示的最新 Canonical 结果摘要。

        默认只读取完成的根任务及其显式 Envelope。批量最新结果导出可显式纳入
        最新失败任务的同轮成功项；仍不读取 legacy Bundle/QCResult，也不跨轮拼接。
        """

        started = monotonic()
        query_seconds = result_parse_seconds = 0.0
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
        requested_identities_count = len(identities)

        normalized_rule_set_key = _safe_text(rule_set_key)
        normalized_rule_set_version = _safe_text(rule_set_version)
        if not normalized_rule_set_key or not normalized_rule_set_version:
            raise ValueError("病历池结果摘要缺少规则集身份")

        # 规则集身份仍由 Python 做精确校验；这里仅以文本预筛掉与当前 LX0609
        # 代次无关的历史任务，避免全院首页解析大批无关 filters/summary JSON。
        # 两处都保留，是为了维持读取模型“filters 优先、summary 兼容回退”的合同。
        filters_rule_set_candidate = self._batch_job_table.c.filters_json.ilike(
            f"%{normalized_rule_set_key}%"
        )
        filters_rule_version_candidate = self._batch_job_table.c.filters_json.ilike(
            f"%{normalized_rule_set_version}%"
        )
        summary_rule_set_candidate = self._batch_job_table.c.summary_json.ilike(
            f"%{normalized_rule_set_key}%"
        )
        summary_rule_version_candidate = self._batch_job_table.c.summary_json.ilike(
            f"%{normalized_rule_set_version}%"
        )
        rule_set_candidate = or_(filters_rule_set_candidate, summary_rule_set_candidate)
        rule_version_candidate = or_(filters_rule_version_candidate, summary_rule_version_candidate)
        session = (session_factory or _session)()
        try:
            cache_scope_key = _session_cache_scope_key(session) if not include_items else None
            watermark_bucket_key: Optional[tuple[Any, ...]] = None
            cached_watermark_hits: Dict[tuple[str, str, str], Dict[str, Any]] = {}
            if cache_scope_key is not None:
                wm_started = monotonic()
                watermark = self._read_luxian_summary_watermark(session)
                query_seconds += monotonic() - wm_started
                if watermark is not None:
                    watermark_bucket_key = (
                        cache_scope_key,
                        normalized_rule_set_key,
                        normalized_rule_set_version,
                        bool(include_rule_set_context),
                        bool(include_latest_partial),
                        watermark,
                    )
                    cached_watermark_hits, missing_identities = _watermark_bucket_get(
                        watermark_bucket_key,
                        identities,
                    )
                    if not missing_identities:
                        return cached_watermark_hits
                    identities = missing_identities

            visit_ids = sorted({identity[2] for identity in identities})
            use_record_id_ilike = len(visit_ids) <= _RECORD_ID_ILIKE_SQL_THRESHOLD
            record_id_conditions = []
            if use_record_id_ilike:
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
            base_predicates = [
                self._batch_job_table.c.status.in_(
                    ("completed", "failed", "running", "queued", "canceled")
                ),
                or_(
                    self._batch_job_table.c.parent_job_id.is_(None),
                    self._batch_job_table.c.parent_job_id == "",
                ),
            ]
            if record_id_conditions:
                base_predicates.append(or_(*record_id_conditions))
            base_job_predicate = and_(*base_predicates)
            job_columns = (
                self._batch_job_table.c.id,
                self._batch_job_table.c.status,
                self._batch_job_table.c.created_at,
                self._batch_job_table.c.updated_at,
                self._batch_job_table.c.finished_at,
                self._batch_job_table.c.filters_json,
                self._batch_job_table.c.record_ids_json,
                # filters_json 已包含当前规则集身份时，避免读取可能很大的
                # summary_json TOAST 值；旧任务才保留摘要兼容回退。
                case(
                    (
                        and_(filters_rule_set_candidate, filters_rule_version_candidate),
                        None,
                    ),
                    else_=self._batch_job_table.c.summary_json,
                ).label("summary_json"),
            )
            # 新任务的规则集身份保存在 filters_json。病历池只需要选择字段，
            # 只有 filters_json 不完整的旧任务才会通过 CASE 读取 summary_json。
            query_started = monotonic()
            job_rows = (
                session.execute(
                    select(*job_columns).where(
                        and_(base_job_predicate, rule_set_candidate, rule_version_candidate)
                    )
                )
                .mappings()
                .all()
            )
            query_seconds += monotonic() - query_started
            # 首页/病历池只需要“选择当前 Canonical 结果”的最小任务字段。
            # 不能为每个候选完整反序列化 items、子任务和运行摘要；真实全院范围
            # 会把同一批任务 JSON 反复解析数十万次，且不会增加任何判定事实。
            jobs_by_id: Dict[str, Dict[str, Any]] = {}
            current_jobs_by_visit: Dict[str, list[Dict[str, Any]]] = {}
            failed_jobs_by_identity: Dict[tuple[str, str, str], list[Dict[str, Any]]] = {}
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
                from .clinical_sources import job_matches
                if not job_matches(filters_dict):
                    continue
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
                    "updated_at": row.get("updated_at"),
                    "finished_at": row.get("finished_at"),
                    "record_ids": record_ids if isinstance(record_ids, list) else [],
                    "filters": filters if isinstance(filters, dict) else {},
                    "filters_json": row.get("filters_json"),
                    "summary": summary if isinstance(summary, dict) else None,
                }
                jobs_by_id[job_id] = job
                if (
                    _rule_set_value(job, "rule_set_key") != normalized_rule_set_key
                    or _rule_set_value(job, "rule_set_version") != normalized_rule_set_version
                ):
                    continue
                job_visit_ids = {_safe_text(value) for value in job["record_ids"]}
                for visit_id in job_visit_ids:
                    if (
                        visit_id in requested_visit_ids
                        and _safe_text(job.get("status")).lower() == "completed"
                    ):
                        current_jobs_by_visit.setdefault(visit_id, []).append(job)
                if include_latest_partial and _safe_text(job.get("status")).lower() == "failed":
                    for raw_ref in filters_dict.get("record_refs") or []:
                        if not isinstance(raw_ref, Mapping):
                            continue
                        exact_ref = CaseRef.from_mapping(raw_ref)
                        identity = tuple(exact_ref)
                        if (
                            all(exact_ref)
                            and identity in identities
                            and exact_ref.visit_id in job_visit_ids
                        ):
                            failed_jobs_by_identity.setdefault(identity, []).append(job)
            if not jobs_by_id:
                empty_projections = {identity: {"status": "not_run"} for identity in identities}
                if watermark_bucket_key is not None:
                    _watermark_bucket_merge(watermark_bucket_key, empty_projections)
                if cached_watermark_hits:
                    empty_projections.update(cached_watermark_hits)
                return empty_projections

            envelope_columns = self._record_result_envelope_table.c
            envelope_selection_columns = (
                envelope_columns.id, envelope_columns.root_job_id, envelope_columns.institute_id,
                envelope_columns.patient_id, envelope_columns.visit_id, envelope_columns.rule_set_key,
                envelope_columns.rule_set_version, envelope_columns.updated_at,
            )
            job_ids = list(jobs_by_id)
            envelope_batch_size = 500
            envelope_rows: list[Any] = []
            query_started = monotonic()
            for job_offset in range(0, len(job_ids), envelope_batch_size):
                job_chunk = job_ids[job_offset : job_offset + envelope_batch_size]
                visit_batch_size = min(envelope_batch_size, max(1, 999 - len(job_chunk)))
                for visit_offset in range(0, len(visit_ids), visit_batch_size):
                    visit_chunk = visit_ids[visit_offset : visit_offset + visit_batch_size]
                    envelope_rows.extend(
                        session.execute(
                            select(*envelope_selection_columns).where(
                                and_(
                                    envelope_columns.root_job_id.in_(job_chunk),
                                    envelope_columns.visit_id.in_(visit_chunk),
                                )
                            )
                        )
                        .mappings()
                        .all()
                    )
            query_seconds += monotonic() - query_started
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
            saved_partial_batches: dict[str, SavedPartialRecordBatch | str] = {}
            selected_canonical = []
            for identity in identities:
                _, _, visit_id = identity
                exact_envelopes = envelopes_by_identity.get(identity, {})
                ready_candidates: list[Dict[str, Any]] = []
                for job_id, record_envelopes in exact_envelopes.items():
                    if job_id not in jobs_by_id:
                        continue
                    candidate = dict(jobs_by_id[job_id])
                    filters = candidate.get("filters") or {}
                    try:
                        candidate["result_rule_scope"] = saved_record_rule_scope(filters, CaseRef(*identity))
                    except (ValueError, TypeError):
                        candidate["result_rule_scope"] = []
                    candidate["result_scope_kind"] = (
                        "targeted" if filters.get("selected_rule_ids") or filters.get("record_rule_map")
                        else "full" if "selected_rule_ids" in filters else "unknown"
                    )
                    if _safe_text(candidate.get("status")).lower() != "completed":
                        # Canonical Envelope 的存在只代表这一份病历已经完整交付。
                        # 选择器仍坚持 completed 合同，因此在本次单病历选择范围内
                        # 将任务投影为完成，并用 Envelope 写入时间作为完成时间。
                        delivered_at = [
                            envelope.get("updated_at")
                            for envelope in record_envelopes
                            if envelope.get("updated_at") is not None
                        ]
                        candidate["status"] = "completed"
                        if delivered_at:
                            candidate["finished_at"] = max(
                                delivered_at,
                                key=lambda value: str(value),
                            )
                    ready_candidates.append(candidate)
                if include_latest_partial:
                    for job in failed_jobs_by_identity.get(identity, []):
                        job_id = _safe_text(job.get("id"))
                        if job_id in exact_envelopes:
                            continue
                        candidate = dict(job)
                        filters = candidate.get("filters") or {}
                        try:
                            candidate["result_rule_scope"] = saved_record_rule_scope(
                                filters,
                                CaseRef(*identity),
                            )
                        except (ValueError, TypeError):
                            continue
                        candidate["result_scope_kind"] = (
                            "targeted"
                            if filters.get("selected_rule_ids") or filters.get("record_rule_map")
                            else "full" if "selected_rule_ids" in filters else "unknown"
                        )
                        candidate["saved_partial_attempt"] = True
                        candidate["saved_filters_json"] = candidate.get("filters_json")
                        candidate["status"] = "completed"
                        ready_candidates.append(candidate)
                ready_selection = select_latest_authoritative_record_result_job(
                    ready_candidates,
                    record_id=visit_id,
                    rule_set_key=normalized_rule_set_key,
                    rule_set_version=normalized_rule_set_version,
                    prefer_full_scope=True,
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
                            **(
                                {
                                    "result_rule_scope": list(
                                        ready_selection.job.get("result_rule_scope") or []
                                    )
                                }
                                if include_latest_partial
                                else {}
                            ),
                        }
                        continue
                    if ready_selection.job.get("saved_partial_attempt"):
                        selected_job = ready_selection.job
                        selected_job_id = _safe_text(selected_job.get("id"))
                        partial_cache_key: Optional[tuple[Any, ...]] = None
                        if cache_scope_key is not None:
                            filters_digest = hashlib.sha256(
                                str(selected_job.get("saved_filters_json") or "").encode("utf-8")
                            ).hexdigest()
                            partial_cache_key = (
                                cache_scope_key,
                                selected_job_id,
                                str(selected_job.get("updated_at") or ""),
                                str(selected_job.get("finished_at") or ""),
                                filters_digest,
                                identity,
                                tuple(selected_job["result_rule_scope"]),
                            )
                            cached_partial = _lru_cache_get(_PARTIAL_SUMMARY_CACHE, partial_cache_key)
                            if cached_partial is not None:
                                projections[identity] = cached_partial
                                continue
                        if selected_job_id not in saved_partial_batches:
                            query_started = monotonic()
                            saved_row = session.execute(select(
                                self._batch_job_table.c.items_json,
                                self._batch_job_table.c.summary_json,
                                self._batch_job_table.c.failed_records_json,
                            ).where(and_(
                                self._batch_job_table.c.id == selected_job_id,
                                self._batch_job_table.c.status == "failed",
                                self._batch_job_table.c.filters_json
                                == selected_job.get("saved_filters_json"),
                            ))).mappings().one_or_none()
                            query_seconds += monotonic() - query_started
                            if saved_row is None:
                                saved_partial_batches[selected_job_id] = "saved_partial_task_changed"
                            else:
                                parse_started = monotonic()
                                try:
                                    saved_partial_batches[selected_job_id] = SavedPartialRecordBatch.from_row(saved_row)
                                except ValueError:
                                    saved_partial_batches[selected_job_id] = "saved_partial_result_invalid"
                                finally:
                                    result_parse_seconds += monotonic() - parse_started
                        saved = saved_partial_batches[selected_job_id]
                        if isinstance(saved, str):
                            projections[identity] = {
                                "status": "technical_error",
                                "reason_code": saved,
                                "result_rule_scope": list(
                                    selected_job["result_rule_scope"]
                                ),
                            }
                            continue
                        projection_key = customer_safe_projection_key()
                        parse_started = monotonic()
                        try:
                            partial = saved.read(
                                ref=CaseRef(*identity),
                                expected_rules=selected_job["result_rule_scope"],
                                projection_key=projection_key,
                                projector=lambda item: self._envelope_item_from_rule_result(
                                    item,
                                    hmac_key=projection_key,
                                ),
                            )
                        except ValueError as exc:
                            if not str(exc).startswith("saved_partial_"):
                                raise
                            projections[identity] = {
                                "status": "technical_error",
                                "reason_code": "saved_partial_result_invalid",
                                "result_rule_scope": list(
                                    selected_job["result_rule_scope"]
                                ),
                            }
                            continue
                        finally:
                            result_parse_seconds += monotonic() - parse_started
                        if partial.get("failure_stage"):
                            projection_result = {
                                "status": "technical_error",
                                "data_origin": "saved_partial_task",
                                "job_id": selected_job_id,
                                "completed_at": _record_result_completed_at(selected_job),
                                "result_rule_scope": list(selected_job["result_rule_scope"]),
                                **partial,
                            }
                            if partial_cache_key is not None:
                                _lru_cache_put(
                                    _PARTIAL_SUMMARY_CACHE,
                                    partial_cache_key,
                                    projection_result,
                                    _PARTIAL_SUMMARY_CACHE_MAX,
                                )
                            projections[identity] = projection_result
                            continue
                        excluded_rule_ids = (
                            LUXIAN_0609_CUSTOMER_EXCLUDED_RULE_IDS
                            if normalized_rule_set_key == LUXIAN_0609_RULE_SET_KEY
                            else frozenset()
                        )
                        visible_partial_items = [
                            item
                            for item in partial["items"]
                            if _safe_text(
                                item.get("rule_id") or item.get("rule_code")
                            ).upper()
                            not in excluded_rule_ids
                        ]
                        status_counts: Dict[str, int] = {}
                        for item in visible_partial_items:
                            item_status = _safe_text(item.get("status"), "unknown")
                            status_counts[item_status] = status_counts.get(item_status, 0) + 1
                        projection_result = {
                            "status": "ready" if visible_partial_items else "failed",
                            "completed_at": (
                                selected_job.get("finished_at").isoformat()
                                if isinstance(selected_job.get("finished_at"), datetime)
                                else _safe_text(selected_job.get("finished_at")) or None
                            ),
                            "total_rule_count": len(visible_partial_items),
                            "status_counts": dict(sorted(status_counts.items())),
                            "data_origin": "saved_partial_task",
                            "job_id": selected_job_id,
                            "result_rule_scope": list(selected_job["result_rule_scope"]),
                            "result_scope_kind": selected_job.get(
                                "result_scope_kind", "unknown"
                            ),
                            **partial,
                            "execution_status": (
                                "partial_failed" if visible_partial_items else "failed"
                            ),
                            "completed_rule_count": len(visible_partial_items),
                            "items": visible_partial_items,
                        }
                        if not include_items:
                            # 摘要模式下统一剥离大体积明细，避免污染 _PARTIAL_SUMMARY_CACHE 与 _WATERMARK_SUMMARY_CACHE。
                            projection_result.pop("items", None)
                        if partial_cache_key is not None:
                            _lru_cache_put(
                                _PARTIAL_SUMMARY_CACHE,
                                partial_cache_key,
                                projection_result,
                                _PARTIAL_SUMMARY_CACHE_MAX,
                            )
                        projections[identity] = projection_result
                        continue
                    selected_job_id = _safe_text(ready_selection.job.get("id"))
                    selected_envelopes = exact_envelopes.get(selected_job_id, [])
                    projections[identity] = {
                        "status": "technical_error",
                        "reason_code": "canonical_result_envelope_invalid",
                    }
                    if len(selected_envelopes) == 1:
                        selected_canonical.append((identity, ready_selection.job, selected_envelopes[0]))
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

            # 选轮只读取元数据；摘要模式先命中不可变版本键缓存，仅对未命中行加载信封正文。
            uncached_selected: list[tuple[tuple[str, str, str], Dict[str, Any], Dict[str, Any], Optional[tuple[Any, ...]]]] = []
            for identity, job, selected_row in selected_canonical:
                env_cache_key: Optional[tuple[Any, ...]] = None
                if cache_scope_key is not None:
                    env_cache_key = (
                        cache_scope_key,
                        _safe_text(selected_row.get("id")),
                        str(selected_row.get("updated_at") or ""),
                        normalized_rule_set_key,
                        normalized_rule_set_version,
                        str(job.get("finished_at") or ""),
                    )
                    cached_summary = _lru_cache_get(_ENVELOPE_SUMMARY_CACHE, env_cache_key)
                    if cached_summary is not None:
                        if include_rule_set_context and cached_summary.get("status") == "ready":
                            cached_summary.update({
                                "root_job_id": _safe_text(job.get("id")),
                                "envelope_id": _safe_text(selected_row.get("id")),
                                "rule_set_key": normalized_rule_set_key,
                                "rule_set_version": _rule_set_value(job, "rule_set_version"),
                                "result_rule_scope": list(job.get("result_rule_scope") or []),
                                "result_scope_kind": job.get("result_scope_kind", "unknown"),
                            })
                        projections[identity] = cached_summary
                        continue
                uncached_selected.append((identity, job, selected_row, env_cache_key))

            batch_size = 500
            for offset in range(0, len(uncached_selected), batch_size):
                selected_batch = uncached_selected[offset:offset + batch_size]
                query_started = monotonic()
                rows = session.execute(select(
                    *envelope_selection_columns, envelope_columns.envelope_json,
                ).where(envelope_columns.id.in_([row["id"] for _, _, row, _ in selected_batch]))).mappings().all()
                query_seconds += monotonic() - query_started
                bodies_by_id = {row["id"]: row for row in rows}
                for identity, job, selected_row, env_cache_key in selected_batch:
                    body = bodies_by_id.get(selected_row["id"])
                    if body is None or any(body[key] != value for key, value in selected_row.items()):
                        continue
                    parse_started = monotonic()
                    summary = self._summarize_completed_record_result_envelope(
                        envelope_row=body,
                        completed_at=job.get("finished_at"),
                        include_items=include_items,
                        rule_set_key=normalized_rule_set_key,
                    )
                    result_parse_seconds += monotonic() - parse_started
                    if env_cache_key is not None:
                        _lru_cache_put(
                            _ENVELOPE_SUMMARY_CACHE,
                            env_cache_key,
                            summary,
                            _ENVELOPE_SUMMARY_CACHE_MAX,
                        )
                    if include_rule_set_context and summary.get("status") == "ready":
                        summary.update({
                            "root_job_id": _safe_text(job.get("id")),
                            "envelope_id": _safe_text(selected_row.get("id")),
                            "rule_set_key": normalized_rule_set_key,
                            "rule_set_version": _rule_set_value(job, "rule_set_version"),
                            "result_rule_scope": list(job.get("result_rule_scope") or []),
                            "result_scope_kind": job.get("result_scope_kind", "unknown"),
                        })
                    projections[identity] = summary
            if watermark_bucket_key is not None:
                _watermark_bucket_merge(watermark_bucket_key, projections)
            if cached_watermark_hits:
                projections.update(cached_watermark_hits)
            return projections
        finally:
            session.close()
            elapsed = monotonic() - started
            if log_read_timing and elapsed >= 2:
                logging.getLogger(__name__).warning(
                    "workstation_qc_summary_slow query_ms=%d result_parse_ms=%d other_ms=%d total_ms=%d matched=%d",
                    query_seconds * 1000, result_parse_seconds * 1000,
                    max(0.0, elapsed - query_seconds - result_parse_seconds) * 1000,
                    elapsed * 1000, requested_identities_count,
                )

    @staticmethod
    def _summarize_completed_record_result_envelope(
        *,
        envelope_row: Mapping[str, Any],
        completed_at: Any,
        include_items: bool = False,
        rule_set_key: str = LUXIAN_0609_RULE_SET_KEY,
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

        if _safe_text(rule_set_key) == LUXIAN_0609_RULE_SET_KEY:
            envelope_rule_ids = {
                _safe_text(item.get("rule_id") or item.get("rule_code")).upper()
                for item in envelope["items"]
            }
            if envelope_rule_ids - _luxian_0609_catalog_rule_ids():
                return {
                    "status": "technical_error",
                    "reason_code": "canonical_result_envelope_invalid",
                }

        excluded_rule_ids = (
            LUXIAN_0609_CUSTOMER_EXCLUDED_RULE_IDS
            if _safe_text(rule_set_key) == LUXIAN_0609_RULE_SET_KEY
            else frozenset()
        )
        visible_items = [
            item
            for item in envelope["items"]
            if _safe_text(item.get("rule_id") or item.get("rule_code")).upper()
            not in excluded_rule_ids
        ]

        status_counts: Dict[str, int] = {}
        for item in visible_items:
            status = _safe_text(item.get("status"))
            status_counts[status] = status_counts.get(status, 0) + 1
        if isinstance(completed_at, datetime):
            completed_at_value = completed_at.isoformat()
        else:
            completed_at_value = _safe_text(completed_at)
        result: Dict[str, Any] = {
            "status": "ready",
            "completed_at": completed_at_value or None,
            "total_rule_count": len(visible_items),
            "status_counts": dict(sorted(status_counts.items())),
        }
        if include_items:
            rule_master_by_id = {
                entry.rule_id: entry for entry in load_luxian_0609_rule_master()
            }
            projected_items: List[Dict[str, Any]] = []
            for item in visible_items:
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
        """按单病历同一选轮合同批量读取最新结果，供服务端全量导出。"""

        projections = self.build_luxian_0609_completed_record_result_summaries(
            record_refs=record_refs,
            rule_set_key=rule_set_key,
            rule_set_version=rule_set_version,
            session_factory=session_factory,
            include_items=True,
            include_rule_set_context=True,
            include_latest_partial=True,
        )
        expected_rule_ids = [
            _safe_text(item.get("rule_id") or item.get("rule_code")).upper()
            for item in load_luxian_0609_rules()
            if _safe_text(item.get("rule_id") or item.get("rule_code"))
            and _safe_text(item.get("rule_id") or item.get("rule_code")).upper()
            not in LUXIAN_0609_CUSTOMER_EXCLUDED_RULE_IDS
        ]
        results: Dict[tuple[str, str, str], Dict[str, Any]] = {}
        for identity, projection in projections.items():
            selected_expected_rule_ids = [
                _safe_text(rule_id).upper()
                for rule_id in projection.get("result_rule_scope") or expected_rule_ids
                if _safe_text(rule_id)
                and _safe_text(rule_id).upper()
                not in LUXIAN_0609_CUSTOMER_EXCLUDED_RULE_IDS
            ]
            status = _safe_text(projection.get("status"))
            if status != "ready" and not (
                status == "failed" and projection.get("data_origin") == "saved_partial_task"
            ):
                results[identity] = {
                    "schema_version": "lx0609-single-record-result-v1",
                    "state": "not_found" if status == "not_run" else "technical_error",
                    "reason_code": _safe_text(projection.get("reason_code")),
                    **(
                        {key: projection[key] for key in ("failure_stage", "data_origin", "job_id", "completed_at")}
                        if projection.get("failure_stage") else {}
                    ),
                    "record_ref": "",
                    "items": [],
                    "expected_rule_count": len(selected_expected_rule_ids),
                    "result_rule_count": 0,
                    "is_complete": False,
                }
                continue
            items = [
                dict(item)
                for item in projection.get("items") or []
                if isinstance(item, dict)
                and _safe_text(item.get("rule_id") or item.get("rule_code")).upper()
                not in LUXIAN_0609_CUSTOMER_EXCLUDED_RULE_IDS
            ]
            delivered_rule_ids = {
                _safe_text(item.get("rule_id") or item.get("rule_code")).upper()
                for item in items
                if _safe_text(item.get("rule_id") or item.get("rule_code"))
            }
            missing_rule_ids = [
                rule_id
                for rule_id in selected_expected_rule_ids
                if rule_id not in delivered_rule_ids
            ]
            is_partial = _safe_text(projection.get("data_origin")) == "saved_partial_task"
            results[identity] = {
                "schema_version": "lx0609-single-record-result-v1",
                "state": "ready",
                "data_origin": (
                    "saved_partial_task" if is_partial else "canonical_result_envelope"
                ),
                "record_ref": _safe_text(projection.get("record_ref")),
                "job_id": _safe_text(
                    projection.get("job_id") or projection.get("root_job_id")
                ),
                "rule_set_key": rule_set_key,
                "rule_set_version": rule_set_version,
                "items": items,
                "expected_rule_count": len(selected_expected_rule_ids),
                "result_rule_count": len(items),
                "is_complete": not is_partial and not missing_rule_ids,
                "missing_rule_ids": missing_rule_ids,
                **(
                    {
                        key: projection[key]
                        for key in (
                            "execution_status",
                            "failed_rule_ids",
                            "failed_rule_count",
                            "failed_rules",
                            "completed_rule_count",
                        )
                        if key in projection
                    }
                    if is_partial
                    else {}
                ),
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
        require_donghua_proof: bool = False,
    ) -> Dict[str, Any]:
        """单病历结果接口的唯一服务入口。"""

        return self.build_latest_single_record_result_dto(
            institute_id=institute_id,
            patient_id=patient_id,
            visit_id=visit_id,
            rule_set_key=rule_set_key,
            rule_set_version=rule_set_version,
            expected_rule_ids=expected_rule_ids,
            **({"require_donghua_proof": True} if require_donghua_proof else {}),
        )

    def get_previous_valid_luxian_0609_record_result(
        self,
        *,
        institute_id: str,
        patient_id: str,
        visit_id: str,
        anchor_job_id: str = "",
        require_donghua_proof: bool = False,
    ) -> Dict[str, Any]:
        """单病历历史结果接口的唯一服务入口。"""

        return self.build_previous_valid_record_result_dto(
            institute_id=institute_id,
            patient_id=patient_id,
            visit_id=visit_id,
            anchor_job_id=anchor_job_id,
            require_donghua_proof=require_donghua_proof,
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
                ).with_for_update()
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
            running_luxian_attempt = (
                current.get("status") == "running"
                and (current.get("filters") or {}).get("rule_set_key") == LUXIAN_0609_RULE_SET_KEY
            )
            cancellation_update = session.execute(
                update(self._batch_job_table)
                .where(
                    and_(
                        self._batch_job_table.c.id == job_id,
                        self._batch_job_table.c.created_by == created_by,
                        self._batch_job_table.c.status.in_(["queued", "running"]),
                    )
                )
                .values(
                    status="canceled",
                    summary_json=_safe_json_dumps(
                        {
                            **current_summary,
                            **({"luxian_0609_usage_observation_complete": False}
                               if running_luxian_attempt else {}),
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
            # 取消请求读取任务后可能等待完成事务释放行锁。若完成事务先提交，
            # 条件更新必须保持 completed/failed 终态，不能再覆盖为 canceled。
            if getattr(cancellation_update, "rowcount", 0) != 1:
                session.rollback()
                return self.get_batch_job(job_id=job_id, created_by=created_by)
            self._sync_mq_dispatch_status(
                session,
                job_id=job_id,
                filters=current.get("filters") or {},
                to_status="canceled",
                from_statuses=("queued", "running"),
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
                active_child_scope = and_(
                    child_where,
                    self._batch_job_table.c.created_by == created_by,
                    self._batch_job_table.c.status.in_(["queued", "running"]),
                )
                child_cancel_values = {
                    "status": "canceled",
                    "error_message": "parent_cancelled: 总任务已取消",
                    "finished_at": now,
                    "updated_at": now,
                }
                if (current.get("filters") or {}).get("rule_set_key") == LUXIAN_0609_RULE_SET_KEY:
                    child_rows = session.execute(
                        select(self._batch_job_table).where(active_child_scope).with_for_update()
                    ).mappings().all()
                    for child_row in child_rows:
                        child_summary = _safe_json_loads(child_row.get("summary_json"), {})
                        if not isinstance(child_summary, dict):
                            child_summary = {}
                        child_cancelled = session.execute(
                            update(self._batch_job_table)
                            .where(and_(
                                self._batch_job_table.c.id == child_row["id"],
                                self._batch_job_table.c.created_by == created_by,
                                self._batch_job_table.c.status.in_(["queued", "running"]),
                            ))
                            .values(
                                **child_cancel_values,
                                summary_json=_safe_json_dumps({
                                    **child_summary,
                                    "luxian_0609_usage_observation_complete": False,
                                }),
                            )
                        )
                        if getattr(child_cancelled, "rowcount", 0) == 1:
                            child_filters = _safe_json_loads(child_row.get("filters_json"), {})
                            self._sync_mq_dispatch_status(
                                session,
                                job_id=str(child_row["id"]),
                                filters=(child_filters if isinstance(child_filters, dict) else {}),
                                to_status="canceled",
                                from_statuses=("queued", "running"),
                            )
                else:
                    session.execute(
                        update(self._batch_job_table)
                        .where(active_child_scope)
                        .values(**child_cancel_values)
                    )
            session.commit()
            return self.get_batch_job(job_id=job_id, created_by=created_by)
        finally:
            session.close()

    def _create_retry_attempt(
        self, session: Session, *, row: Mapping[str, Any], current: Dict[str, Any],
        retry_scope_result: Optional[tuple[Dict[str, Any], List[Dict[str, Any]]]],
        automatic: bool, retry_delay_seconds: float,
        task_runtime_snapshot: Optional[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """新尝试只保存本轮产出；原任务、材料及结果信封保持不变。"""
        if _safe_text(current.get("job_kind")) == "parent":
            raise ValueError("new_task_required_preserve_history：父任务请新建，原任务、结果与材料已保留")
        from .material_job_lineage import resolve_material_job_id
        def lookup_material_job(candidate_id):
            candidate = session.execute(select(self._batch_job_table).where(
                self._batch_job_table.c.id == candidate_id)).mappings().first()
            return dict(candidate) if candidate is not None else None
        material_job_id = resolve_material_job_id(row, lookup_material_job)
        source_id = str(row["id"])
        source_hash = hashlib.sha256(str(row["filters_json"]).encode("utf-8")).hexdigest()
        # 同一个源尝试只能派生一个后继；再次重试应针对返回的新任务。
        new_id = str(uuid.uuid5(uuid.NAMESPACE_URL, f"medqc:retry:v1:{source_id}:{source_hash}"))
        existing = session.execute(select(self._batch_job_table).where(
            self._batch_job_table.c.id == new_id)).mappings().first()
        if existing:
            if existing["created_by"] != row["created_by"]:
                raise ValueError("retry_identity_owner_mismatch")
            return {**_row_to_batch_job(dict(existing)), "idempotency_reused": True}
        filters = dict(current["filters"])
        previous = filters.get("retry_lineage")
        previous = previous or {}
        lineage = {
            "schema_version": "qc-retry-lineage-v1",
            "source_job_id": source_id,
            "root_job_id": previous.get("root_job_id") or source_id,
            "material_job_id": material_job_id,
            "source_attempt": _safe_json_loads(row["filters_json"], {}).get(LX0609_ATTEMPT_FILTER_KEY) or "",
            "source_filters_sha256": source_hash,
            "attempt": max(0, _to_int(previous.get("attempt"))) + 1,
            "trigger": "automatic" if automatic else "manual",
        }
        filters["retry_lineage"] = lineage
        filters[LX0609_ATTEMPT_FILTER_KEY] = uuid.uuid4().hex
        filters.pop(LX0609_LEASE_FILTER_KEY, None)
        filters.pop("parent_job_id", None)
        # 重试不是新的每日计划回执，也不继承旧聚合/范围哈希。
        filters.pop("daily_schedule", None)
        filters.pop("execution_scope_hash", None)
        filters.pop("deduplicated", None)
        if task_runtime_snapshot is not None:
            filters[LX0609_TASK_RUNTIME_FILTER_KEY] = task_runtime_snapshot
        if retry_scope_result is not None:
            retry_scope, _ = retry_scope_result
            if not set(retry_scope["rule_ids"]).issubset(filters["scoped_customer_rule_ids"]):
                raise ValueError("失败规则超出原任务冻结范围，请新建质控任务")
            filters[FAILED_RULE_RETRY_FILTER_KEY] = retry_scope
            filters["record_refs"] = retry_scope["record_refs"]
            filters["rule_ids"] = retry_scope["rule_ids"]
            filters["selected_rule_ids"] = retry_scope["rule_ids"]
            filters["record_rule_map"] = retry_scope["record_rule_map"]
            filters["scoped_customer_rule_ids"] = retry_scope["rule_ids"]
            filters["paused_customer_rule_ids"] = []
            filters["gate_only_customer_rule_ids"] = []
        else:
            filters.pop(FAILED_RULE_RETRY_FILTER_KEY, None)
        refs = normalize_case_refs(filters.get("record_refs") or [])
        if not refs:
            raise ValueError("重试任务缺少原始病历三坐标，请新建质控任务")
        from .luxian_0609.phase_scope import get_luxian_0609_phase_scope
        paused_ids = []
        for rule_id in filters["scoped_customer_rule_ids"]:
            phase = get_luxian_0609_phase_scope(rule_id)
            if phase is None:
                raise ValueError("重试规则范围无法恢复，请新建质控任务")
            if phase.phase_status == "pending_definition":
                paused_ids.append(rule_id)
        if retry_scope_result is not None and len(paused_ids) == len(filters["scoped_customer_rule_ids"]):
            raise ValueError("retry_rule_scope_paused：失败规则当前已暂停，请按当前可执行范围新建任务")
        # 保留交付范围，暂停项由当前执行器交付“未启用”，不能借旧冻结范围执行。
        filters["paused_customer_rule_ids"] = paused_ids
        now = _now_utc()
        rule_count = len(filters["scoped_customer_rule_ids"])
        summary = {"rule_count": rule_count, "total_records": len(refs),
                   "retry_status": "queued", "retry_attempt": lineage["attempt"],
                   "retry_trigger": lineage["trigger"],
                   "progress": {"step_key": "queued", "rule_index": 0,
                                "rule_count": rule_count, "processed_records": 0, "total_records": len(refs)},
                   "updated_at": now.isoformat()}
        auto_plan = (current.get("summary") or {}).get("automatic_failed_rule_retry")
        if automatic and isinstance(auto_plan, dict):
            summary["automatic_failed_rule_retry"] = {**auto_plan, "status": "queued", "queued_at": now.isoformat()}
        payload = dict(row)
        payload.update(id=new_id, filters_json=_safe_json_dumps(filters), status="queued",
                       record_ids_json=_safe_json_dumps([ref.visit_id for ref in refs]),
                       summary_json=_safe_json_dumps(summary), items_json=None, failed_records_json=None,
                       error_message=None, created_at=now, updated_at=now, started_at=None, finished_at=None,
                       total_records=len(refs), success_count=0, failed_count=0, issue_records=0,
                       compliant_records=0, total_tokens=0, total_processing_time=0.0,
                       job_kind="leaf", parent_job_id=None, child_job_ids_json="[]", child_summary_json="{}")
        try:
            session.execute(self._batch_job_table.insert().values(**payload))
        except sa.exc.IntegrityError:
            # SQLite无行锁；唯一主键同样裁决并发创建，失败事务不得留下半个attempt。
            session.rollback()
            winner = session.execute(select(self._batch_job_table).where(and_(
                self._batch_job_table.c.id == new_id,
                self._batch_job_table.c.created_by == row["created_by"],
            ))).mappings().first()
            if winner is None:
                raise
            return {**_row_to_batch_job(dict(winner)), "idempotency_reused": True}
        if qc_dispatch_mode_from_filters(filters) == "rabbitmq":
            self._qc_dispatch.assert_ready(session)
            self._qc_dispatch.add_dispatch(session, job_id=new_id, mode="rabbitmq", enqueue_leaf=True,
                                           available_at=_now_utc_aware() + timedelta(seconds=retry_delay_seconds))
            source_dispatch = self._qc_dispatch.get_dispatch(source_id, session=session)
            self._qc_dispatch.link_retry_successor(
                session, source_job_id=source_id, source_generation=source_dispatch.generation,
                successor_job_id=new_id, automatic=automatic,
            )
        session.commit()
        return _row_to_batch_job(payload)

    def retry_batch_job(
        self,
        *,
        job_id: str,
        created_by: str,
        automatic: bool = False,
        expected_attempt_filters_json: str | None = None,
        retry_delay_seconds: float = 0.0,
        task_runtime_snapshot: Optional[Dict[str, Any]] = None,
    ) -> Optional[Dict[str, Any]]:
        if retry_delay_seconds < 0:
            raise ValueError("retry_delay_seconds must not be negative")
        session = _session()
        try:
            row = session.execute(
                select(self._batch_job_table).where(
                    and_(self._batch_job_table.c.id == job_id, self._batch_job_table.c.created_by == created_by)
                ).with_for_update()
            ).mappings().first()
            if not row:
                return None
            raw_filters = _safe_json_loads(row.get("filters_json"), None)
            if not isinstance(raw_filters, dict):
                raise ValueError("任务调度身份不可读，禁止按legacy重试")
            persisted_mode = qc_dispatch_mode_from_filters(raw_filters)
            if persisted_mode == "rabbitmq" and (
                raw_filters.get("rule_set_key") != LUXIAN_0609_RULE_SET_KEY
            ):
                raise ValueError("MQ任务缺少正式LX0609规则集身份")
            if (
                DISPATCH_FILTER_KEY not in raw_filters
                and self._qc_dispatch.schema_is_available(session=session)
            ):
                linked_dispatch = self._qc_dispatch.get_dispatch(job_id, session=session)
                if linked_dispatch is not None:
                    raise ValueError("MQ任务持久调度身份损坏，禁止回退legacy重试")
            current = _row_to_batch_job(dict(row))
            formal_0609 = (current.get("filters") or {}).get("rule_set_key") == LUXIAN_0609_RULE_SET_KEY
            if formal_0609:
                from .saved_result_access import require_retry_record_institutes
                require_retry_record_institutes(created_by, current["filters"].get("record_refs"))
            dispatch_mode = (
                persisted_mode
                if formal_0609
                else "legacy"
            )
            dispatch_record = None
            if dispatch_mode == "rabbitmq":
                dispatch_record = self._qc_dispatch.get_dispatch(job_id, session=session)
                if dispatch_record is None:
                    raise RuntimeError("MQ任务缺少持久调度身份")
            original_filters_json = row.get("filters_json")
            if current.get("status") not in {"canceled", "completed", "failed"}:
                return None
            if formal_0609 and automatic and original_filters_json != expected_attempt_filters_json:
                return None
            if formal_0609:
                current["filters"]["scoped_customer_rule_ids"] = frozen_luxian_0609_delivery_scope(current["filters"])
            parent_job_id = _safe_text(current.get("parent_job_id"))
            rule_count = int(current.get("rule_count") or 1)
            total_records = int(current.get("total_records") or 0)
            now = _now_utc()
            if automatic and formal_0609:
                from .qc_execution_errors import task_error_blocks_automatic_retry
                # 行锁内复核；已登记的恢复意图不能覆盖后保存的任务级拒绝。
                if task_error_blocks_automatic_retry(current.get("summary")):
                    return None
            retry_scope_result = build_failed_rule_retry_scope(current)
            if automatic and formal_0609 and retry_scope_result is None:
                # 仅持久恢复 owner 已登记的空产出 MQ 失败可自动完整重试。
                # 请求 filters 不提供恢复权限；任务行锁与原始 attempt CAS 仍在上方裁决。
                summary = current.get("summary") or {}
                bounded_unstarted = (
                    dispatch_record is not None
                    and dispatch_record.status == "failed"
                    and dispatch_record.recovery_kind == "unstarted"
                    and dispatch_record.recovery_reason_code == "no_saved_results_after_stale_attempt"
                    and dispatch_record.recovery_registered_at is not None
                    and 0 <= dispatch_record.failure_count < dispatch_record.failure_budget
                    and current.get("status") == "failed"
                    and str(current.get("job_kind") or "").lower() != "parent"
                    and not current.get("items")
                    and not current.get("failed_records")
                    and not current.get("rule_results")
                    and not summary.get("rule_results")
                    and int(current.get("success_count") or 0) == 0
                    and int(summary.get("completed_rule_count") or 0) == 0
                )
                if not bounded_unstarted:
                    return None
                # 与新身份创建共用事务，直接查原信封，不能只凭 items_json 为空放行。
                envelope = self._record_result_envelope_table
                saved_envelope = session.execute(select(envelope.c.id).where(or_(
                    envelope.c.job_id == job_id,
                    envelope.c.root_job_id == (parent_job_id or job_id),
                )).limit(1)).first()
                if saved_envelope is not None:
                    return None
            if automatic and retry_scope_result is not None:
                retry_scope_result = build_failed_rule_retry_scope(current, automatic_only=True)
                if retry_scope_result is None:
                    return None
            if formal_0609:
                if automatic and str(current.get("job_kind") or "").lower() == "parent":
                    return None
                return self._create_retry_attempt(
                    session, row=row, current=current, retry_scope_result=retry_scope_result,
                    automatic=automatic, retry_delay_seconds=retry_delay_seconds,
                    task_runtime_snapshot=task_runtime_snapshot,
                )
            if (
                dispatch_record is not None
                and str(current.get("job_kind") or "").strip().lower() != "parent"
                and retry_scope_result is None
                and (
                    bool(current.get("items"))
                    or int(current.get("success_count") or 0) > 0
                    or bool((current.get("summary") or {}).get("rule_results"))
                )
            ):
                # M3 检查点前，没有明确失败 scope 时不能清空已有成功结果全量重跑。
                self._qc_dispatch.register_recovery(
                    job_id,
                    dispatch_record.generation,
                    recovery_kind="manual_scope_required",
                    reason_code="manual_scope_required",
                    session=session,
                )
                session.commit()
                return None
            if (
                dispatch_record is not None
                and str(current.get("job_kind") or "").strip().lower() == "parent"
            ):
                child_ids = [
                    str(item or "").strip()
                    for item in list(current.get("child_job_ids") or [])
                    if str(item or "").strip()
                ]
                child_where = self._batch_job_table.c.parent_job_id == job_id
                if child_ids:
                    child_where = or_(child_where, self._batch_job_table.c.id.in_(child_ids))
                child_rows = session.execute(
                    select(self._batch_job_table).where(and_(
                        child_where,
                        self._batch_job_table.c.created_by == created_by,
                    ))
                ).mappings().all()
                retryable_children = 0
                manual_scope_children = 0
                due_at = _now_utc_aware() + timedelta(seconds=retry_delay_seconds)
                for child_row in child_rows:
                    child = _row_to_batch_job(dict(child_row))
                    if child.get("status") == "completed":
                        # 已成功的子任务及其结果保持原样。
                        continue
                    if child.get("status") not in {"failed", "canceled"}:
                        session.rollback()
                        return None
                    child_filters = dict(child.get("filters") or {})
                    if qc_dispatch_mode_from_filters(child_filters) != "rabbitmq":
                        raise RuntimeError("父子任务调度身份不一致")
                    child_dispatch = self._qc_dispatch.get_dispatch(
                        str(child["id"]), session=session
                    )
                    if child_dispatch is None:
                        raise RuntimeError("MQ子任务缺少持久调度身份")
                    child_scope_result = build_failed_rule_retry_scope(child)
                    if automatic and child_scope_result is not None:
                        child_scope_result = build_failed_rule_retry_scope(
                            child, automatic_only=True
                        )
                    if child_scope_result is None and (
                        bool(child.get("items"))
                        or int(child.get("success_count") or 0) > 0
                        or bool((child.get("summary") or {}).get("rule_results"))
                    ):
                        self._qc_dispatch.register_recovery(
                            str(child["id"]),
                            child_dispatch.generation,
                            recovery_kind="manual_scope_required",
                            reason_code="manual_scope_required",
                            session=session,
                        )
                        manual_scope_children += 1
                        continue

                    child_filters.pop(LX0609_ATTEMPT_FILTER_KEY, None)
                    child_filters[LX0609_ATTEMPT_FILTER_KEY] = uuid.uuid4().hex
                    child_summary = dict(child.get("summary") or {})
                    if child_scope_result is not None:
                        child_retry_scope, child_failures = child_scope_result
                        if not set(child_retry_scope["rule_ids"]).issubset(
                            frozen_luxian_0609_delivery_scope(child_filters)
                        ):
                            raise ValueError("失败规则超出原任务冻结范围，请新建质控任务")
                        child_filters[FAILED_RULE_RETRY_FILTER_KEY] = child_retry_scope
                        child_rule_count = len(child_retry_scope["rule_ids"])
                        child_record_count = len(child_retry_scope["record_refs"])
                        child_values = dict(
                            status="queued",
                            filters_json=_safe_json_dumps(child_filters),
                            summary_json=_safe_json_dumps({
                                **child_summary,
                                "retry_status": "queued",
                                "retry_trigger": "automatic" if automatic else "manual",
                                "retry_attempt": child_retry_scope["attempt"],
                                "retry_pending_count": child_retry_scope["pending_count"],
                                "progress": {
                                    "step_key": "queued",
                                    "rule_index": 0,
                                    "rule_count": child_rule_count,
                                    "processed_records": 0,
                                    "total_records": child_record_count,
                                },
                                "updated_at": now.isoformat(),
                            }),
                            failed_records_json=_safe_json_dumps(child_failures),
                            error_message=None,
                            started_at=None,
                            finished_at=None,
                            updated_at=now,
                        )
                    else:
                        # 仅“完全未产出任何结果”的子任务允许有限全量重排。
                        child_filters.pop(FAILED_RULE_RETRY_FILTER_KEY, None)
                        child_values = dict(
                            status="queued",
                            filters_json=_safe_json_dumps(child_filters),
                            summary_json=_safe_json_dumps({
                                "rule_count": max(1, int(child.get("rule_count") or 1)),
                                "progress": {
                                    "step_key": "queued",
                                    "rule_index": 0,
                                    "rule_count": max(1, int(child.get("rule_count") or 1)),
                                    "processed_records": 0,
                                    "total_records": int(child.get("total_records") or 0),
                                },
                                "updated_at": now.isoformat(),
                            }),
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
                    changed = session.execute(
                        update(self._batch_job_table)
                        .where(and_(
                            self._batch_job_table.c.id == child["id"],
                            self._batch_job_table.c.status == child_row["status"],
                            self._batch_job_table.c.filters_json == child_row["filters_json"],
                        ))
                        .values(**child_values)
                    )
                    if getattr(changed, "rowcount", 0) != 1:
                        session.rollback()
                        return None
                    self._qc_dispatch.advance_generation(
                        session,
                        job_id=str(child["id"]),
                        expected_generation=child_dispatch.generation,
                        available_at=due_at,
                    )
                    retryable_children += 1

                if retryable_children == 0:
                    if manual_scope_children:
                        session.commit()
                    return None
                parent_filters = dict(current.get("filters") or {})
                parent_filters.pop(LX0609_ATTEMPT_FILTER_KEY, None)
                parent_filters[LX0609_ATTEMPT_FILTER_KEY] = uuid.uuid4().hex
                parent_summary = dict(current.get("summary") or {})
                parent_changed = session.execute(
                    update(self._batch_job_table)
                    .where(and_(
                        self._batch_job_table.c.id == job_id,
                        self._batch_job_table.c.status == current.get("status"),
                        self._batch_job_table.c.filters_json == original_filters_json,
                    ))
                    .values(
                        status="queued",
                        filters_json=_safe_json_dumps(parent_filters),
                        summary_json=_safe_json_dumps({
                            **parent_summary,
                            "retry_status": "queued",
                            "retry_trigger": "automatic" if automatic else "manual",
                            "retry_pending_count": retryable_children,
                            "updated_at": now.isoformat(),
                        }),
                        error_message=None,
                        started_at=None,
                        finished_at=None,
                        updated_at=now,
                    )
                )
                if getattr(parent_changed, "rowcount", 0) != 1:
                    session.rollback()
                    return None
                self._qc_dispatch.advance_generation(
                    session,
                    job_id=job_id,
                    expected_generation=dispatch_record.generation,
                    available_at=due_at,
                    enqueue=False,
                )
                session.commit()
                self.refresh_parent_batch_job(parent_job_id=job_id)
                return self.get_batch_job(job_id=job_id, created_by=created_by)
            if retry_scope_result is not None:
                retry_scope, normalized_failures = retry_scope_result
                if formal_0609 and not set(retry_scope["rule_ids"]).issubset(
                    current["filters"]["scoped_customer_rule_ids"]
                ):
                    raise ValueError("失败规则超出原任务冻结范围，请新建质控任务")
                current_filters = dict(current.get("filters") or {})
                current_filters.pop(LX0609_ATTEMPT_FILTER_KEY, None)
                if formal_0609:
                    current_filters[LX0609_ATTEMPT_FILTER_KEY] = uuid.uuid4().hex
                current_filters[FAILED_RULE_RETRY_FILTER_KEY] = retry_scope
                current_summary = dict(current.get("summary") or {})
                automatic_retry_plan = current_summary.get("automatic_failed_rule_retry")
                if (
                    automatic
                    and isinstance(automatic_retry_plan, dict)
                    and automatic_retry_plan.get("should_retry") is True
                    and _safe_text(automatic_retry_plan.get("status")).lower() == "planned"
                ):
                    automatic_retry_plan = {
                        **automatic_retry_plan,
                        "status": "queued",
                        "queued_at": now.isoformat(),
                    }
                retry_rule_count = len(retry_scope["rule_ids"])
                retry_record_count = len(retry_scope["record_refs"])
                reset_values = dict(
                    status="queued",
                    filters_json=_safe_json_dumps(current_filters),
                    summary_json=_safe_json_dumps(
                        {
                            **current_summary,
                            "retry_status": "queued",
                            "retry_trigger": "automatic" if automatic else "manual",
                            **(
                                {"automatic_failed_rule_retry": automatic_retry_plan}
                                if automatic and isinstance(automatic_retry_plan, dict)
                                else {}
                            ),
                            "retry_attempt": retry_scope["attempt"],
                            "retry_pending_count": retry_scope["pending_count"],
                            "progress": {
                                "step_key": "queued",
                                "rule_index": 0,
                                "rule_count": retry_rule_count,
                                "processed_records": 0,
                                "total_records": retry_record_count,
                            },
                            "updated_at": now.isoformat(),
                        }
                    ),
                    failed_records_json=_safe_json_dumps(normalized_failures),
                    error_message=None,
                    started_at=None,
                    finished_at=None,
                    updated_at=now,
                )
            else:
                current_filters = dict(current.get("filters") or {})
                current_filters.pop(LX0609_ATTEMPT_FILTER_KEY, None)
                if formal_0609:
                    current_filters[LX0609_ATTEMPT_FILTER_KEY] = uuid.uuid4().hex
                current_filters.pop(FAILED_RULE_RETRY_FILTER_KEY, None)
                reset_values = dict(
                    status="queued",
                    filters_json=_safe_json_dumps(current_filters),
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
            retry_update = session.execute(
                update(self._batch_job_table)
                .where(
                    and_(
                        self._batch_job_table.c.id == job_id,
                        self._batch_job_table.c.created_by == created_by,
                        self._batch_job_table.c.status == current.get("status"),
                        self._batch_job_table.c.filters_json == original_filters_json,
                    ) if formal_0609 else and_(
                        self._batch_job_table.c.id == job_id,
                        self._batch_job_table.c.created_by == created_by,
                        self._batch_job_table.c.status == current.get("status"),
                    )
                )
                .values(**reset_values)
            )
            if getattr(retry_update, "rowcount", 0) != 1:
                session.rollback()
                return None
            if (
                dispatch_record is not None
                and str(current.get("job_kind") or "").strip().lower() != "parent"
            ):
                self._qc_dispatch.advance_generation(
                    session,
                    job_id=job_id,
                    expected_generation=dispatch_record.generation,
                    available_at=_now_utc_aware() + timedelta(seconds=retry_delay_seconds),
                )
            # 子任务单独重试也会废弃父聚合的旧读取快照；与父刷新争用同一父行。
            if formal_0609 and parent_job_id:
                parent_row = session.execute(
                    select(self._batch_job_table).where(
                        and_(self._batch_job_table.c.id == parent_job_id,
                             self._batch_job_table.c.created_by == created_by)
                    )
                ).mappings().first()
                if parent_row:
                    parent_filters = _safe_json_loads(parent_row.get("filters_json"), {})
                    if isinstance(parent_filters, dict) and parent_filters.get("rule_set_key") == LUXIAN_0609_RULE_SET_KEY:
                        parent_filters = dict(parent_filters)
                        parent_filters[LX0609_ATTEMPT_FILTER_KEY] = uuid.uuid4().hex
                        invalidated = session.execute(
                            update(self._batch_job_table)
                            .where(and_(
                                self._batch_job_table.c.id == parent_job_id,
                                self._batch_job_table.c.status == parent_row["status"],
                                self._batch_job_table.c.filters_json == parent_row["filters_json"],
                            ))
                            .values(filters_json=_safe_json_dumps(parent_filters), updated_at=now)
                        )
                        if getattr(invalidated, "rowcount", 0) != 1:
                            session.rollback()
                            return None
            if str(current.get("job_kind") or "").strip().lower() == "parent":
                child_ids = [
                    str(item or "").strip()
                    for item in list(current.get("child_job_ids") or [])
                    if str(item or "").strip()
                ]
                child_where = self._batch_job_table.c.parent_job_id == job_id
                if child_ids:
                    child_where = or_(child_where, self._batch_job_table.c.id.in_(child_ids))
                child_scope = and_(child_where, self._batch_job_table.c.created_by == created_by)
                child_reset = {key: value for key, value in reset_values.items() if key != "filters_json"}
                if formal_0609:
                    child_rows = session.execute(
                        select(self._batch_job_table).where(child_scope)
                    ).mappings().all()
                    for child_row in child_rows:
                        if child_row["status"] not in {"canceled", "completed", "failed"}:
                            session.rollback()
                            return None
                        child_filters = _safe_json_loads(child_row.get("filters_json"), {})
                        child_filters = dict(child_filters) if isinstance(child_filters, dict) else {}
                        child_filters["scoped_customer_rule_ids"] = frozen_luxian_0609_delivery_scope(child_filters)
                        # 父任务已清空子任务基准结果，本轮必须按原计划全量执行。
                        child_filters.pop(FAILED_RULE_RETRY_FILTER_KEY, None)
                        child_filters[LX0609_ATTEMPT_FILTER_KEY] = uuid.uuid4().hex
                        child_update = session.execute(
                            update(self._batch_job_table)
                            .where(and_(
                                self._batch_job_table.c.id == child_row["id"],
                                self._batch_job_table.c.status == child_row["status"],
                                self._batch_job_table.c.filters_json == child_row["filters_json"],
                            ))
                            .values(**child_reset, filters_json=_safe_json_dumps(child_filters))
                        )
                        if getattr(child_update, "rowcount", 0) != 1:
                            session.rollback()
                            return None
                else:
                    child_rows = session.execute(
                        select(self._batch_job_table).where(child_scope)
                    ).mappings().all()
                    for child_row in child_rows:
                        if child_row["status"] not in {"canceled", "completed", "failed"}:
                            session.rollback()
                            return None
                        child_update = session.execute(
                            update(self._batch_job_table)
                            .where(and_(
                                self._batch_job_table.c.id == child_row["id"],
                                self._batch_job_table.c.status == child_row["status"],
                            ))
                            .values(**child_reset)
                        )
                        if getattr(child_update, "rowcount", 0) != 1:
                            session.rollback()
                            return None
            session.commit()
            self.refresh_parent_batch_job(parent_job_id=parent_job_id)
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

    def mark_batch_job_running(
        self, *, job_id: str, expected_dispatch_generation: int | None = None
    ) -> bool | str:
        session = _session()
        try:
            row = session.execute(
                select(self._batch_job_table).where(self._batch_job_table.c.id == job_id)
            ).mappings().first()
            if not row:
                return False
            current = _row_to_batch_job(dict(row))
            current_filters = current.get("filters") or {}
            formal_0609 = current_filters.get("rule_set_key") == LUXIAN_0609_RULE_SET_KEY
            dispatch_mode = qc_dispatch_mode_from_filters(current_filters) if formal_0609 else "legacy"
            dispatch_record = None
            if dispatch_mode == "rabbitmq":
                dispatch_record = self._qc_dispatch.get_dispatch(job_id, session=session)
                if dispatch_record is None or dispatch_record.status != "queued":
                    raise RuntimeError("MQ任务缺少可领取的持久调度身份")
                if (
                    expected_dispatch_generation is not None
                    and dispatch_record.generation != expected_dispatch_generation
                ):
                    session.rollback()
                    return False
            if current.get("status") != "queued":
                return False
            current_summary = _safe_json_loads(row.get("summary_json"), {})
            if not isinstance(current_summary, dict):
                current_summary = {}
            automatic_retry_plan = current_summary.get("automatic_failed_rule_retry")
            if (
                isinstance(automatic_retry_plan, dict)
                and automatic_retry_plan.get("should_retry") is True
                and _safe_text(automatic_retry_plan.get("status")).lower() == "queued"
            ):
                current_summary = {
                    **current_summary,
                    "automatic_failed_rule_retry": {
                        **automatic_retry_plan,
                        "status": "running",
                    },
                }
            progress_value = current_summary.get("progress")
            if not isinstance(progress_value, dict):
                progress_value = {}
            now = _now_utc()
            original_filters_json = row.get("filters_json")
            next_filters_json = (
                _safe_json_dumps({
                    **current_filters,
                    LX0609_ATTEMPT_FILTER_KEY: uuid.uuid4().hex,
                    LX0609_LEASE_FILTER_KEY: 1,
                })
                if formal_0609 else original_filters_json
            )
            running_update = session.execute(
                update(self._batch_job_table)
                .where(
                    and_(
                        self._batch_job_table.c.id == job_id,
                        self._batch_job_table.c.status == "queued",
                        self._batch_job_table.c.filters_json == original_filters_json,
                    ) if formal_0609 else and_(
                        self._batch_job_table.c.id == job_id,
                        self._batch_job_table.c.status == "queued",
                    )
                )
                .values(
                    status="running",
                    started_at=now,
                    **({"filters_json": next_filters_json} if formal_0609 else {}),
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
            if getattr(running_update, "rowcount", 0) != 1:
                session.rollback()
                return False
            if dispatch_record is not None and not self._qc_dispatch.transition_dispatch(
                job_id=job_id,
                generation=dispatch_record.generation,
                from_statuses=("queued",),
                to_status="running",
                session=session,
            ):
                session.rollback()
                return False
            session.commit()
            return next_filters_json if formal_0609 else True
        finally:
            session.close()

    def mark_failed_rule_auto_retry_enqueue_failed(
        self,
        *,
        job_id: str,
        expected_attempt_filters_json: str,
    ) -> bool:
        """CAS 撤销未真正入队的自动补跑计划，不改动既有结果和尝试范围。"""

        session = _session()
        try:
            row = session.execute(
                select(
                    self._batch_job_table.c.status,
                    self._batch_job_table.c.filters_json,
                    self._batch_job_table.c.summary_json,
                ).where(self._batch_job_table.c.id == job_id)
            ).mappings().first()
            if (
                row is None
                or _safe_text(row.get("status")).lower() != "failed"
                or row.get("filters_json") != expected_attempt_filters_json
            ):
                return False
            summary = _safe_json_loads(row.get("summary_json"), {})
            if not isinstance(summary, dict):
                return False
            retry_plan = summary.get("automatic_failed_rule_retry")
            if (
                not isinstance(retry_plan, dict)
                or retry_plan.get("should_retry") is not True
                or _safe_text(retry_plan.get("status")).lower() != "planned"
            ):
                return False
            now = _now_utc()
            updated_summary = {
                **summary,
                "automatic_failed_rule_retry": {
                    **retry_plan,
                    "status": "enqueue_failed",
                    "should_retry": False,
                    "reason_code": "retry_enqueue_failed",
                },
                "updated_at": now.isoformat(),
            }
            changed = session.execute(
                update(self._batch_job_table)
                .where(and_(
                    self._batch_job_table.c.id == job_id,
                    self._batch_job_table.c.status == "failed",
                    self._batch_job_table.c.filters_json == expected_attempt_filters_json,
                    self._batch_job_table.c.summary_json == row.get("summary_json"),
                ))
                .values(summary_json=_safe_json_dumps(updated_summary), updated_at=now)
            )
            if getattr(changed, "rowcount", 0) != 1:
                session.rollback()
                return False
            session.commit()
            return True
        finally:
            session.close()

    def renew_luxian_0609_batch_job_lease(
        self, *, job_id: str, attempt_filters_json: str,
    ) -> bool:
        """只续当前0609执行代次；不读写可能很大的病例结果及进度摘要。"""

        filters = _safe_json_loads(attempt_filters_json, {})
        if not isinstance(filters, dict) or type(filters.get(LX0609_LEASE_FILTER_KEY)) is not int:
            return False
        if filters.get(LX0609_LEASE_FILTER_KEY) != 1:
            return False
        session = _session()
        try:
            renewed = session.execute(
                update(self._batch_job_table)
                .where(_batch_job_write_scope(
                    self._batch_job_table,
                    job_id=job_id,
                    attempt_filters_json=attempt_filters_json,
                ))
                .values(updated_at=_now_utc())
            )
            if getattr(renewed, "rowcount", 0) != 1:
                session.rollback()
                return False
            session.commit()
            return True
        finally:
            session.close()

    def fail_stale_luxian_0609_running_jobs(
        self, *, stale_before: datetime, dispatch_mode: str = "legacy"
    ) -> tuple[str, ...]:
        """仅将续约协议内、超过期限的执行尝试受控失败；不重跑医学判断。"""

        if dispatch_mode not in {"legacy", "rabbitmq"}:
            raise ValueError("invalid qc dispatch mode")

        session = _session()
        failed_ids: list[str] = []
        affected_parents: set[str] = set()
        try:
            rows = session.execute(
                select(
                    self._batch_job_table.c.id,
                    self._batch_job_table.c.job_kind,
                    self._batch_job_table.c.parent_job_id,
                    self._batch_job_table.c.filters_json,
                    self._batch_job_table.c.summary_json,
                    self._batch_job_table.c.updated_at,
                ).where(and_(
                    self._batch_job_table.c.status == "running",
                    self._batch_job_table.c.updated_at < stale_before,
                ))
            ).mappings().all()
            for row in rows:
                filters = _safe_json_loads(row.get("filters_json"), {})
                if not isinstance(filters, dict) or filters.get("rule_set_key") != LUXIAN_0609_RULE_SET_KEY:
                    continue
                if qc_dispatch_mode_from_filters(filters) != dispatch_mode:
                    continue
                if (
                    _safe_text(row.get("job_kind")).lower() == "parent"
                    or type(filters.get(LX0609_LEASE_FILTER_KEY)) is not int
                    or filters.get(LX0609_LEASE_FILTER_KEY) != 1
                ):
                    continue
                summary = _safe_json_loads(row.get("summary_json"), {})
                summary = dict(summary) if isinstance(summary, dict) else {}
                progress = summary.get("progress")
                progress = dict(progress) if isinstance(progress, dict) else {}
                now = _now_utc()
                expired = session.execute(
                    update(self._batch_job_table)
                    .where(and_(
                        self._batch_job_table.c.id == row["id"],
                        self._batch_job_table.c.status == "running",
                        self._batch_job_table.c.filters_json == row["filters_json"],
                        self._batch_job_table.c.updated_at == row["updated_at"],
                        self._batch_job_table.c.updated_at < stale_before,
                    ))
                    .values(
                        status="failed",
                        error_message="执行尝试续约已过期，结果写入已停止；请重试任务",
                        finished_at=now,
                        updated_at=now,
                        summary_json=_safe_json_dumps({
                            **summary,
                            "luxian_0609_usage_observation_complete": False,
                            "progress": {**progress, "step_key": "failed"},
                            "updated_at": now.isoformat(),
                        }),
                    )
                )
                if getattr(expired, "rowcount", 0) == 1:
                    if dispatch_mode == "rabbitmq":
                        dispatch = self._qc_dispatch.get_dispatch(str(row["id"]), session=session)
                        if dispatch is None or not self._qc_dispatch.transition_dispatch(
                            job_id=str(row["id"]),
                            generation=dispatch.generation,
                            from_statuses=("running",),
                            to_status="failed",
                            session=session,
                        ):
                            raise RuntimeError("MQ失联任务的调度身份无法同步失败")
                    failed_ids.append(str(row["id"]))
                    parent_id = _safe_text(row.get("parent_job_id"))
                    if parent_id:
                        affected_parents.add(parent_id)
            session.commit()
        finally:
            session.close()
        for parent_id in affected_parents:
            self.refresh_parent_batch_job(parent_job_id=parent_id)
        return tuple(failed_ids)

    @timed("result_write")
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
        attempt_filters_json: str | None = None,
    ) -> Optional[Dict[str, Any]]:
        session = _session()
        try:
            row = session.execute(
                select(
                    self._batch_job_table.c.id,
                    self._batch_job_table.c.status,
                    self._batch_job_table.c.summary_json,
                    self._batch_job_table.c.filters_json,
                ).where(self._batch_job_table.c.id == job_id)
            ).mappings().first()
            if not row:
                return None
            current_status = _safe_text(row.get("status"))
            if current_status == "canceled":
                return {"id": job_id, "status": current_status}

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

            progress_update = session.execute(
                update(self._batch_job_table)
                .where(_batch_job_write_scope(
                    self._batch_job_table, job_id=job_id, attempt_filters_json=attempt_filters_json,
                    observed_filters_json=row.get("filters_json"),
                ))
                .values(**values)
            )
            if getattr(progress_update, "rowcount", 0) != 1 and (
                attempt_filters_json is not None
                or LX0609_ATTEMPT_FILTER_KEY in _safe_json_loads(row.get("filters_json"), {})
            ):
                session.rollback()
                return None
            session.commit()
            # 进度写入是高频热路径。调用方只关心写入是否成功，不应在每次
            # commit 后重新读取并反序列化可能达到几十 MB 的完整任务结果。
            return {
                "id": job_id,
                "status": current_status,
                "summary": merged_summary,
            }
        finally:
            session.close()

    def is_batch_job_canceled_or_missing(self, *, job_id: str, attempt_filters_json: str | None = None) -> bool:
        """取消轮询只读取状态列，避免反序列化完整批量结果。"""

        session = _session()
        try:
            if attempt_filters_json is None:
                status = session.execute(
                    select(self._batch_job_table.c.status).where(self._batch_job_table.c.id == job_id)
                ).scalar_one_or_none()
                return status is None or _safe_text(status) == "canceled"
            row = session.execute(
                select(self._batch_job_table.c.status, self._batch_job_table.c.filters_json).where(
                    self._batch_job_table.c.id == job_id
                )
            ).mappings().first()
            if row is None:
                return True
            return _safe_text(row["status"]) != "running" or row["filters_json"] != attempt_filters_json
        finally:
            session.close()

    @timed("final_save")
    def complete_batch_job(
        self,
        *,
        job_id: str,
        summary: Dict[str, Any],
        items: List[Dict[str, Any]],
        failed_records: List[Dict[str, Any]],
        persist_record_envelopes: bool = True,
        attempt_filters_json: str | None = None,
        recovery_baseline: Dict[str, Any] | None = None,
    ) -> bool | None:
        session = _session()
        try:
            statement = select(self._batch_job_table).where(self._batch_job_table.c.id == job_id)
            if recovery_baseline is not None:
                statement = statement.with_for_update()
            row = session.execute(statement).mappings().first()
            if not row:
                return
            recovery_refs = None
            if recovery_baseline is not None:
                from .qc_workspace.offline_failure_recovery import validate_recovery_merge
                # 在原任务锁内复核备份基线，避免覆盖并发恢复、取消或新一轮任务。
                for field in ("id", "created_by", "status", "filters_json", "items_json", "failed_records_json", "summary_json", "updated_at"):
                    if row.get(field) != recovery_baseline.get(field):
                        raise ValueError("recovery_baseline_changed")
                recovery_refs = validate_recovery_merge(recovery_baseline, items=items, failures=failed_records)
            parent_job_id = _safe_text(row.get("parent_job_id"))
            now = _now_utc()
            execution_failed = summary.get("execution_status") in {"partial_failed", "failed"}
            filters = _safe_json_loads(row.get("filters_json"), {})
            filters = filters if isinstance(filters, dict) else {}
            rule_set_key = _safe_text(filters.get("rule_set_key"))
            if rule_set_key == LUXIAN_0916_RULE_SET_KEY:
                configured_rule_ids = filters.get("rule_ids")
                expected_rule_ids = (
                    configured_rule_ids
                    if isinstance(configured_rule_ids, list) and configured_rule_ids
                    else LUXIAN_0916_RULE_IDS
                )
                configured_record_refs = filters.get("record_refs")
                expected_record_refs = (
                    configured_record_refs
                    if isinstance(configured_record_refs, list)
                    else []
                )
                validate_luxian_0916_task_delivery(
                    summary=summary,
                    items=items,
                    failures=failed_records,
                    expected_rule_ids=expected_rule_ids,
                    expected_record_refs=expected_record_refs,
                )
            elif execution_failed:
                validate_failed_task_items(summary, items, failed_records)
            merged_summary = {
                **(summary or {}),
                "progress": {
                    **(
                        summary.get("progress")
                        if isinstance(summary.get("progress"), dict)
                        else {}
                    ),
                    "step_key": "failed" if execution_failed else "completed",
                    "processed_records": int((summary or {}).get("total_records") or 0),
                    "total_records": int((summary or {}).get("total_records") or 0),
                },
                "updated_at": now.isoformat(),
            }
            completion_update = session.execute(
                update(self._batch_job_table)
                .where(and_(
                    self._batch_job_table.c.id == job_id,
                    self._batch_job_table.c.status == "failed",
                    self._batch_job_table.c.filters_json == row.get("filters_json"),
                ) if recovery_refs is not None else _batch_job_write_scope(
                    self._batch_job_table, job_id=job_id, attempt_filters_json=attempt_filters_json,
                    observed_filters_json=row.get("filters_json"),
                ))
                .values(
                    status="failed" if execution_failed else "completed",
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
            # 取消请求可能在本次完成写入前已提交。此时 WHERE 不会命中，
            # 不能让迟到的执行结果继续写入 Canonical Envelope。
            if getattr(completion_update, "rowcount", 0) != 1:
                session.rollback()
                if attempt_filters_json is None and rule_set_key != LUXIAN_0609_RULE_SET_KEY:
                    self.refresh_parent_batch_job(parent_job_id=parent_job_id)
                return False if attempt_filters_json is not None else None
            self._sync_mq_dispatch_status(
                session,
                job_id=job_id,
                filters=filters,
                to_status="failed" if execution_failed else "completed",
                from_statuses=("queued", "running", "failed"),
            )
            # 原始 0609 叶子根任务没有父任务刷新兜底：本次尝试的正式结果必须整体替换
            # 该 root 的旧 Canonical，否则上一代已交付、本次未交付（含本次零交付）的病历
            # 仍会被读取为当前交付。父任务 root 的整体替换由 refresh_parent_batch_job
            # 负责，子任务保持逐病例写入，其它规则集不变；即使调用方本次不写
            # Canonical（persist_record_envelopes=False）也不得留下上一代正式结果。
            if rule_set_key == LUXIAN_0609_RULE_SET_KEY and not parent_job_id and recovery_refs is None:
                session.execute(
                    self._record_result_envelope_table.delete().where(and_(
                        self._record_result_envelope_table.c.root_job_id == job_id,
                        self._record_result_envelope_table.c.created_by == row.get("created_by"),
                        self._record_result_envelope_table.c.rule_set_key == LUXIAN_0609_RULE_SET_KEY,
                    ))
                )
            envelope_items: Sequence[Dict[str, Any]] = (
                items if persist_record_envelopes and not execution_failed else ()
            )
            envelope_record_refs: Optional[Sequence[CaseRef]] = None
            if execution_failed:
                if _safe_text(filters.get("rule_set_key")) == LUXIAN_0609_RULE_SET_KEY:
                    scoped_rule_ids = list(filters.get("scoped_customer_rule_ids") or [])
                    expected_rule_ids = [
                        *(scoped_rule_ids or list(filters.get("rule_ids") or [])),
                        *list(filters.get("gate_only_customer_rule_ids") or []),
                        *list(filters.get("paused_customer_rule_ids") or []),
                    ]
                    envelope_items, envelope_record_refs = select_complete_record_items(
                        items=items,
                        failures=failed_records,
                        expected_rule_ids=expected_rule_ids,
                    )
            if recovery_refs is not None:
                # 只为本次补齐且已完整交付的病历写信封；其他成功病历的信封原行不动。
                envelope_items = [item for item in envelope_items if tuple(str(item.get(key) or "") for key in ("institute_id", "patient_id", "visit_id")) in recovery_refs]
                envelope_record_refs = list(dict.fromkeys(CaseRef.from_mapping(item) for item in envelope_items))
            diagnostic_receipts = (
                self._write_record_result_envelopes(
                    session,
                    job_row=dict(row),
                    items=envelope_items,
                    now=now,
                    expected_record_refs=envelope_record_refs,
                )
                if envelope_items
                else ()
            )
            if envelope_items and not execution_failed:
                self._notify_saved_result(session, job_row=dict(row), now=now)
            session.commit()
            if getattr(completion_update, "rowcount", None) == 1:
                capture_committed_results(diagnostic_receipts)
            self.refresh_parent_batch_job(parent_job_id=parent_job_id)
            return True if attempt_filters_json is not None else None
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    @staticmethod
    def _envelope_item_from_rule_result(
        item: Dict[str, Any], *, hmac_key: str | None = None,
    ) -> Dict[str, Any]:
        return envelope_item_from_rule_result(item, hmac_key=hmac_key)

    def _notify_saved_result(self, session: Session, *, job_row: Dict[str, Any], now: datetime) -> None:
        from .qc_result_ready_notification import publish_result_ready

        publish_result_ready(
            session, job_row=job_row, jobs=self._batch_job_table,
            envelopes=self._record_result_envelope_table, now=now,
        )

    def _write_record_result_envelopes(
        self,
        session: Session,
        *,
        job_row: Dict[str, Any],
        items: Sequence[Dict[str, Any]],
        now: datetime,
        expected_record_refs: Optional[Sequence[CaseRef]] = None,
    ) -> tuple[tuple[CaseRef, str], ...]:
        # 一次保存使用同一份配置，下一次操作仍读取最新密钥。
        projection_key = customer_safe_projection_key()
        envelope_job_row = job_row
        if expected_record_refs is not None:
            filters = _safe_json_loads(job_row.get("filters_json"), {})
            filters = dict(filters) if isinstance(filters, dict) else {}
            filters["record_refs"] = [record_ref.as_dict() for record_ref in expected_record_refs]
            envelope_job_row = {
                **job_row,
                "filters_json": _safe_json_dumps(filters),
            }
        return CanonicalResultStore(self._record_result_envelope_table).replace_for_job(
            session,
            job_row=envelope_job_row,
            items=items,
            now=now,
            projector=partial(self._envelope_item_from_rule_result, hmac_key=projection_key),
            collect_receipts=diagnostic_capture_enabled(),
            projection_key=projection_key,
        )

    def list_record_result_case_refs(self, *, job_id: str, limit: int = 500) -> List[CaseRef]:
        """按任务读取正式结果信封的病历三坐标（结果页身份回查用），按首次写入顺序去重。"""
        table = self._record_result_envelope_table
        session = _session()
        try:
            rows = session.execute(
                select(table.c.institute_id, table.c.patient_id, table.c.visit_id)
                .where(or_(table.c.root_job_id == job_id, table.c.job_id == job_id))
                .order_by(table.c.created_at, table.c.id)
            ).all()
        finally:
            session.close()
        refs: List[CaseRef] = []
        for row in rows:
            ref = CaseRef(_safe_text(row[0]), _safe_text(row[1]), _safe_text(row[2]))
            if all(ref) and ref not in refs:
                refs.append(ref)
                if len(refs) >= limit:
                    break
        return refs

    def _load_record_result_envelope_items(
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
        return CanonicalResultStore(self._record_result_envelope_table).load_selected(
            session,
            root_job_id=root_job_id,
            institute_id=institute_id,
            patient_id=patient_id,
            visit_id=visit_id,
            rule_set_key=rule_set_key,
            rule_set_version=rule_set_version,
        )

    def fail_batch_job(
        self, *, job_id: str, error_message: str,
        attempt_filters_json: str | None = None, queued_only: bool = False,
        execution_error: Optional[Mapping[str, Any]] = None,
        expected_queued_filters_json: str | None = None,
    ) -> None:
        session = _session()
        try:
            row = session.execute(
                select(self._batch_job_table).where(self._batch_job_table.c.id == job_id)
            ).mappings().first()
            if not row:
                return
            if queued_only and expected_queued_filters_json is None and (
                (_safe_json_loads(row.get("filters_json"), {}) or {}).get("rule_set_key")
                == LUXIAN_0609_RULE_SET_KEY
            ):
                return
            if queued_only and expected_queued_filters_json is not None and (
                row.get("filters_json") != expected_queued_filters_json
            ):
                return
            parent_job_id = _safe_text(row.get("parent_job_id"))
            row_filters = _safe_json_loads(row.get("filters_json"), {})
            row_filters = row_filters if isinstance(row_filters, dict) else {}
            current_summary = _safe_json_loads(row.get("summary_json"), {})
            if not isinstance(current_summary, dict):
                current_summary = {}
            if execution_error is not None:
                from .qc_execution_errors import safe_failure_projection
                current_summary["execution_error"] = safe_failure_projection(execution_error)
            failed_running_luxian_attempt = (
                row.get("status") == "running"
                and (_safe_json_loads(row.get("filters_json"), {}) or {}).get("rule_set_key")
                == LUXIAN_0609_RULE_SET_KEY
            )
            failed_active_luxian_retry = (
                row.get("status") in {"queued", "running"}
                and (_safe_json_loads(row.get("filters_json"), {}) or {}).get("rule_set_key")
                == LUXIAN_0609_RULE_SET_KEY
            )
            automatic_retry_plan = current_summary.get("automatic_failed_rule_retry")
            if (
                failed_active_luxian_retry
                and isinstance(automatic_retry_plan, dict)
                and automatic_retry_plan.get("should_retry") is True
                and _safe_text(automatic_retry_plan.get("status")).lower()
                in {"queued", "running"}
            ):
                current_summary = {
                    **current_summary,
                    "automatic_failed_rule_retry": {
                        **automatic_retry_plan,
                        "status": "interrupted",
                        "should_retry": False,
                        "reason_code": (
                            "retry_execution_interrupted"
                            if row.get("status") == "running"
                            else "retry_start_interrupted"
                        ),
                    },
                }
            now = _now_utc()
            failure_update = session.execute(
                update(self._batch_job_table)
                .where(_batch_job_write_scope(
                    self._batch_job_table, job_id=job_id, attempt_filters_json=attempt_filters_json,
                    observed_filters_json=row.get("filters_json"), queued_only=queued_only,
                ))
                .where(
                    self._batch_job_table.c.filters_json == expected_queued_filters_json
                    if queued_only and expected_queued_filters_json is not None else sa.true()
                )
                .values(
                    status="failed",
                    summary_json=_safe_json_dumps(
                        {
                            **current_summary,
                            **({"luxian_0609_usage_observation_complete": False}
                               if failed_running_luxian_attempt else {}),
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
            if getattr(failure_update, "rowcount", 0) != 1:
                session.rollback()
                if attempt_filters_json is None and (
                    (_safe_json_loads(row.get("filters_json"), {}) or {}).get("rule_set_key")
                    != LUXIAN_0609_RULE_SET_KEY
                ):
                    self.refresh_parent_batch_job(parent_job_id=parent_job_id)
                return
            self._sync_mq_dispatch_status(
                session,
                job_id=job_id,
                filters=row_filters,
                to_status="failed",
                from_statuses=("queued", "running"),
            )
            session.commit()
            self.refresh_parent_batch_job(parent_job_id=parent_job_id)
        finally:
            session.close()

    def export_batch_job_workbook(self, *, job: Dict[str, Any]) -> BytesIO:
        if _is_luxian_0609_export_job(job):
            items, rows, summary = _canonical_customer_export_rows(
                job,
                hmac_key=customer_safe_projection_key(),
                canonical_items=self._load_batch_job_export_items(job=job),
            )
            return render_customer_safe_workbook(
                items=items,
                rows=_sanitize_spreadsheet_rows(rows),
                summary=_sanitize_spreadsheet_summary(summary),
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
            ws_summary.append(_sanitize_spreadsheet_row([label, value]))
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
            append_complete_workbook_row(
                ws_items,
                _sanitize_spreadsheet_row([
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
                ]),
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
            append_complete_workbook_row(
                ws_all,
                _sanitize_spreadsheet_row([
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
                ]),
            )
        ws_all.freeze_panes = "A2"

        # 4) 失败明细
        ws_failed = workbook.create_sheet("失败明细")
        ws_failed.append(["病历号", "患者姓名", "科室", "失败原因"])
        for item in failed_records:
            ws_failed.append(
                _sanitize_spreadsheet_row([
                    item.get("record_id") or "",
                    item.get("patient_name") or "",
                    item.get("department") or "",
                    item.get("error") or "",
                ])
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
            ws_tech.append(_sanitize_spreadsheet_row([label, value]))
        ws_tech.column_dimensions["A"].width = 24
        ws_tech.column_dimensions["B"].width = 96

        workbook.save(output)
        output.seek(0)
        return output

    def export_batch_job_csv(self, *, job: Dict[str, Any]) -> StringIO:
        if _is_luxian_0609_export_job(job):
            _items, rows, summary = _canonical_customer_export_rows(
                job,
                hmac_key=customer_safe_projection_key(),
                canonical_items=self._load_batch_job_export_items(job=job),
            )
            return render_customer_safe_csv(
                rows=_sanitize_spreadsheet_rows(rows),
                summary=_sanitize_spreadsheet_summary(summary),
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
        writer.writerow(_sanitize_spreadsheet_row(["任务编号", _safe_text(job.get("id"), "-")]))
        writer.writerow(_sanitize_spreadsheet_row(["任务名称", _safe_text(job.get("rule_name"), "终末病历批量质控任务")]))
        writer.writerow(_sanitize_spreadsheet_row(["规则集", _safe_text(summary.get("rule_set_name") or (job.get("filters") or {}).get("rule_set_name"), "手工选择规则")]))
        writer.writerow(_sanitize_spreadsheet_row(["执行策略", _safe_text(summary.get("quality_profile") or (job.get("filters") or {}).get("quality_profile"), "-")]))
        writer.writerow(_sanitize_spreadsheet_row(["分桶策略", _safe_text(summary.get("bucket_strategy") or (job.get("filters") or {}).get("bucket_strategy"), "-")]))
        writer.writerow(_sanitize_spreadsheet_row(["精审规则数", _to_int(summary.get("refined_rule_count"))]))
        writer.writerow(_sanitize_spreadsheet_row(["适用场景", _map_scene_label(job.get("scene"))]))
        writer.writerow(_sanitize_spreadsheet_row(["覆盖范围", _map_scope_label(job.get("scope"))]))
        writer.writerow(_sanitize_spreadsheet_row(["当前状态", _map_job_status_label(job.get("status"))]))
        writer.writerow(_sanitize_spreadsheet_row(["纳入病历数", _to_int(summary.get("total_records"), _to_int(job.get("total_records")))]))
        writer.writerow(_sanitize_spreadsheet_row(["发现问题病历数", _to_int(summary.get("issue_records"), _to_int(job.get("issue_records")))]))
        writer.writerow(_sanitize_spreadsheet_row(["AI判断病历数", _to_int(summary.get("uncertain_records"))]))
        writer.writerow(_sanitize_spreadsheet_row(["合规病历数", _to_int(summary.get("compliant_records"), _to_int(job.get("compliant_records")))]))
        writer.writerow(_sanitize_spreadsheet_row(["执行规则数", _to_int(summary.get("rule_count"), 1)]))
        writer.writerow([])
        writer.writerow(["问题明细"])
        writer.writerow(["病历号", "患者姓名", "科室", "质控点编码", "质控点名称", "文书域", "规则族", "判定结果", "问题结论", "整改建议", "证据摘要", "置信度", "是否精审"])
        for item in issue_items:
            writer.writerow(_sanitize_spreadsheet_row([
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
            ]))
        writer.writerow([])
        writer.writerow(["失败明细"])
        writer.writerow(["病历号", "患者姓名", "科室", "失败原因"])
        for item in job.get("failed_records") or []:
            writer.writerow(_sanitize_spreadsheet_row([
                item.get("record_id") or "",
                item.get("patient_name") or "",
                item.get("department") or "",
                item.get("error") or "",
            ]))
        output.seek(0)
        return output

    def _load_batch_job_canonical_items(
        self,
        *,
        job: Dict[str, Any],
        session_factory: Optional[Callable[[], Session]] = None,
        allow_partial: bool = False,
    ) -> List[Dict[str, Any]]:
        return CanonicalResultStore(
            getattr(self, "_record_result_envelope_table", None)
        ).load_root_job_items(
            job=job,
            session_factory=session_factory or _session,
            allow_partial=allow_partial,
        )

    def _load_batch_job_export_items(self, *, job: Dict[str, Any]) -> List[Dict[str, Any]]:
        summary = job.get("summary") if isinstance(job.get("summary"), dict) else {}
        allow_partial = (
            _safe_text(job.get("status")) == "failed"
            and _safe_text(summary.get("execution_status")) == "partial_failed"
        )
        return self._load_batch_job_canonical_items(job=job, allow_partial=allow_partial)

    def export_batch_job_html(self, *, job: Dict[str, Any]) -> str:
        if _is_luxian_0609_export_job(job):
            return _export_customer_safe_html(
                job,
                hmac_key=customer_safe_projection_key(),
                canonical_items=self._load_batch_job_export_items(job=job),
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
            _invalidate_in_process_rule_caches()
            return {
                "draft_id": draft_id,
                "rule_code": draft["rule_code"],
                "published_rule_id": published_rule_id,
                "status": "published",
            }
        finally:
            session.close()


def _invalidate_in_process_rule_caches() -> None:
    """发布自定义规则后联动清理进程内规则缓存，失败仅记录日志不影响发布结果。"""
    log = logging.getLogger(__name__)
    try:
        from . import sichuan_qc_service as _sichuan_svc_mod

        fn = getattr(_sichuan_svc_mod, "invalidate_rule_cache", None)
        if callable(fn):
            fn()
    except Exception:
        log.debug("跳过 sichuan_qc_service.invalidate_rule_cache 清理", exc_info=True)

    try:
        from ..routers import qc_sichuan as _qc_sichuan_router

        singleton = getattr(_qc_sichuan_router, "service", None)
        if singleton is not None:
            inv = getattr(singleton, "invalidate_rule_cache", None)
            if callable(inv):
                inv()
    except Exception:
        log.debug("跳过 qc_sichuan.service.invalidate_rule_cache 清理", exc_info=True)

    try:
        from .customer_rule_sets import invalidate_customer_rule_set_cache

        invalidate_customer_rule_set_cache()
    except Exception:
        log.debug("跳过 invalidate_customer_rule_set_cache 清理", exc_info=True)


# SQLAlchemy is imported lazily here to avoid polluting top-level namespace usage above.
