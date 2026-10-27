"""LX0609 麻醉/术前文书族原生执行：强事实门控后逐规则裁剪判定。"""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime
import json
import re
from typing import Any, Mapping, Protocol, Sequence

from .anesthesia_visit_fact_extraction import (
    VisitDocument,
    extract_anesthesia_visit_facts,
    visit_document_scope_issue,
)
from .surgery_document_result_mapping import _VISIT_FIELDS
from .decision_model import (
    ApplicabilityState,
    EvidenceState,
    QcDirection,
    RuleDecision,
)
from .evidence_material import (
    EvidenceMaterialTruncated,
    EvidenceMaterialUnavailable,
    Luxian0609EvidenceMaterialStore,
)
from .evidence_snapshot import Luxian0609EvidenceSnapshot, SourceCompleteness
from .evidence_snapshot_provider import classify_current_visit_surgery_order_rows
from .fact_schema import Assertion, EventStatus
from .native_execution import build_luxian_0609_native_result
from .native_preop_content_execution import evaluate_preop_content_rules
from .planner import PlannedRule
from .source_manifest import QueryStatus
from .source_evidence_reader import (
    authoritative_document_time_value,
    has_qualified_traditional_surgery_row,
)
from .surgery_event_association import (
    associate_preop_document_to_surgery_event,
    build_surgery_document_events,
    count_associated_performed_surgery_events,
    group_surgery_rows_by_start,
    summary_surgery_name_from_row,
    summary_planned_surgery_time_from_row,
)
from .surgery_applicability import resolve_surgery_applicability
from .surgery_procedure_catalog import normalize_surgery_level
from .source_registry import (
    resolve_luxian_0609_controlled_fact_source_keys,
    resolve_luxian_0609_decision_support_source_keys,
    resolve_luxian_0609_rule_sources,
)


SURGERY_DOCUMENT_RULE_IDS = (
    "LX0609-04-01-01",
    "LX0609-11-02-01",
    "LX0609-11-02-02",
    "LX0609-04-04-01",
    "LX0609-04-04-02",
    "LX0609-04-04-03",
    "LX0609-04-01-02",
    "LX0609-04-01-04",
    "LX0609-04-01-05",
)
EXECUTOR_KEY = "surgery_document"
_TYPED_DECISION_RULE_IDS = frozenset(SURGERY_DOCUMENT_RULE_IDS)
_TYPED_EVALUATOR_VERSION = "surgery-document-ruledecision-known-defects-v3"
_TYPED_RULE_SOURCE_KEYS = {
    "LX0609-04-01-01": (
        "presurg_summary",
        "inpat_nondrug_order",
        "surgery_record",
        "mr_surgery",
    ),
    "LX0609-11-02-01": ("anesthesia_record", "mr_surgery", "consent_form"),
    "LX0609-11-02-02": ("anesthesia_record", "mr_surgery", "consent_form"),
    "LX0609-04-04-01": (
        "anesthesia_record",
        "mr_surgery",
        "preane_surveil_record",
        "postane_surveil_record",
    ),
    "LX0609-04-04-02": (
        "anesthesia_record",
        "mr_surgery",
        "consent_form",
        "preane_surveil_record",
        "postane_surveil_record",
    ),
    # 客户目录把038写成consent_form，但临床适用条件仍必须先有受控麻醉事实。
    "LX0609-04-04-03": ("anesthesia_record", "mr_surgery", "consent_form"),
    "LX0609-04-01-02": (
        "surgery_record",
        "mr_surgery",
        "rescue_record",
        "presurg_discussion",
    ),
    "LX0609-04-01-04": ("presurg_summary", "surgery_record"),
    "LX0609-04-01-05": ("presurg_discussion", "surgery_record"),
}

# 技术错误原因码原样保留；其余（快照或绑定异常）归为 snapshot_mismatch。
_PASSTHROUGH_TECHNICAL_REASONS = frozenset({
    "source_query_error", "model_transport_error", "model_timeout", "model_invalid_output",
    "privacy_guard_blocked", "execution_program_error",
})
_ANESTHESIA_CONSENT_RULE_IDS = frozenset({"LX0609-11-02-01", "LX0609-11-02-02"})
_ANESTHESIA_VISIT_RULE_IDS = frozenset({"LX0609-04-04-01", "LX0609-04-04-02"})
_ANESTHESIA_RECORD_RULE_IDS = frozenset({"LX0609-04-04-03"})
_ANESTHESIA_RULE_IDS = (
    _ANESTHESIA_CONSENT_RULE_IDS
    | _ANESTHESIA_VISIT_RULE_IDS
    | _ANESTHESIA_RECORD_RULE_IDS
)

_ANESTHESIA_FACT_TYPES = frozenset(
    {
        "current_visit_anesthesia_performed",
        "current_visit_anesthesia_confirmed",
    }
)
_SURGERY_FACT_TYPES = frozenset({"current_visit_surgery_confirmed"})
_EMERGENCY_FACT_TYPES = frozenset(
    {
        "current_visit_emergency_rescue_surgery",
        "current_visit_lifesaving_emergency_surgery",
    }
)
_PRESENT_STATES = frozenset({"present", "performed", "confirmed", "available"})
_LOCAL_ANESTHESIA_VALUES = frozenset({"局麻", "局部麻醉", "表面麻醉", "局部浸润麻醉", "局部浸润"})
_ANESTHESIA_METHOD_LABEL_PATTERN = re.compile(
    r"麻醉方式\s*[：:]\s*([^\s，,；;。]{1,32})"
)

_CONSENT_SOURCES = ("anesthesia_consent", "anesthesia_consent_form", "consent_form")
_PREANE_SOURCES = ("preane_surveil_record", "preanesthesia_visit")
_POSTANE_SOURCES = ("postane_surveil_record", "postanesthesia_visit")
_MAX_ROWS_PER_SOURCE = 6
_MAX_ROW_CHARS = 1800
_MAX_CONTEXT_CHARS = 14000
_MIN_SUBSTANTIVE_CHARS = 16
_MAPPING_LINE_PATTERN = re.compile(r"^.*(?:主执行规则|映射执行规则).*$", re.MULTILINE)
_PLACEHOLDER_PATTERN = re.compile(
    r"^(?:无|暂无|空|空白|待填|未填|模板|空模板|\[\]|\{\}|-)+$",
    re.IGNORECASE,
)
_STRUCTURED_ABSENT_VALUE_PATTERN = re.compile(
    r"^(?:-|—|--|/|\\|无|暂无|空|空白|不详|未知|"
    r"待(?:填|填写|补充|完善|评估|签名|签字|记录|处理)?|"
    r"未(?:填|填写|补充|完成|评估|签名|签字|记录|进行|行)?|"
    r"尚未(?:完成|评估|签名|签字|记录|进行|填写)?)$",
    re.IGNORECASE,
)
_ANESTHESIA_CONSENT_PATTERN = re.compile(
    r"麻醉[\s\S]{0,40}(?:同意|告知|签名)|(?:同意|告知)[\s\S]{0,40}麻醉"
)
_PRESURG_PLACEHOLDER_VALUES = frozenset({"[]", "{}", "null", "none"})

_CONTROLLED_MESSAGES = {
    "compliant": ("麻醉或术前文书满足该项要求。", ""),
    "non_compliant": (
        "麻醉或术前文书未满足该项要求。",
        "请按该质控点补充或修正相关文书。",
    ),
    "not_applicable": ("当前就诊不符合该项适用条件。", ""),
    "data_gap": (
        "当前麻醉或术前文书资料不足，暂不能形成可靠结论。",
        "请补齐相关资料后重新质控。",
    ),
}


class SurgeryDocumentLLMClient(Protocol):
    async def generate(self, prompt: str) -> dict[str, Any]:
        ...


@dataclass(frozen=True)
class NativeSurgeryDocumentExecutionResult:
    results: tuple[dict[str, Any], ...]
    planned_rule_ids: tuple[str, ...]
    decisions: tuple[RuleDecision, ...] = ()
    customer_display_facts: tuple[tuple[str, Mapping[str, Any]], ...] = ()
    llm_call_count: int = 0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    api_time: float = 0.0


@dataclass(frozen=True)
class _SurgeryDocumentOutcome:
    rule_id: str
    status: str
    reason_code: str
    executor_type: str
    customer_display_facts: Mapping[str, Any] | None = None
    fact_refs: tuple[str, ...] = ()


def _typed_binding_source_keys(rule_id: str) -> frozenset[str]:
    entries = resolve_luxian_0609_rule_sources((rule_id,))[rule_id]
    return frozenset(
        {
            *(entry.document_type for entry in entries),
            *(source_key for entry in entries for source_key in entry.source_keys),
            *resolve_luxian_0609_controlled_fact_source_keys((rule_id,)),
            *resolve_luxian_0609_decision_support_source_keys((rule_id,)),
        }
    )


def _typed_decision_from_outcome(
    *,
    outcome: _SurgeryDocumentOutcome,
    snapshot: Luxian0609EvidenceSnapshot,
) -> RuleDecision:
    source_keys = _typed_binding_source_keys(outcome.rule_id).intersection(
        _TYPED_RULE_SOURCE_KEYS[outcome.rule_id]
    )
    refs = outcome.fact_refs or tuple(
        observation.snapshot_ref.removeprefix("sha256:")
        for observation in snapshot.observations
        if observation.source_key in source_keys
    )
    if outcome.status in {"compliant", "non_compliant", "not_applicable"} and not refs:
        raise ValueError("typed surgery document decision requires evidence refs")

    if outcome.status == "compliant":
        dimensions = (
            ApplicabilityState.APPLICABLE,
            EvidenceState.SUFFICIENT,
            QcDirection.SATISFIED,
            "requirement_satisfied",
        )
    elif outcome.status == "non_compliant":
        dimensions = (
            ApplicabilityState.APPLICABLE,
            EvidenceState.SUFFICIENT,
            QcDirection.DEFECT,
            (
                "defect_proven"
                if outcome.reason_code == "preop_summary_blank"
                else "required_document_missing"
                if outcome.reason_code
                in {
                    "preop_summary_missing",
                    "anesthesia_consent_missing",
                    "anesthesia_visit_missing",
                    "anesthesia_record_missing",
                    "preop_discussion_missing",
                }
                else "requirement_violated"
            ),
        )
    elif outcome.status == "not_applicable":
        dimensions = (
            ApplicabilityState.NOT_APPLICABLE,
            EvidenceState.SUFFICIENT,
            QcDirection.UNKNOWN,
            (
                "eligibility_not_met"
                if outcome.reason_code
                in {
                    "anesthesia_visit_absent",
                    "local_anesthesia_exception",
                    "emergency_rescue_exception",
                    "endoscopic_procedure_exception",
                }
                else "evaluation_window_not_mature"
                if outcome.reason_code == "evaluation_window_not_mature"
                else "performed_event_absent"
            ),
        )
    elif outcome.status == "data_gap":
        controlled_reason = (
            outcome.reason_code
            if (outcome.rule_id == "LX0609-04-04-02" and outcome.reason_code in {
                "semantic_extraction_unresolved", "candidate_scope_incomplete", "source_readiness_unproven",
            })
            or outcome.reason_code
            in {
                "source_unavailable",
                "source_empty",
                "source_truncated",
                "required_field_missing",
                "authoritative_time_missing",
                "association_failed",
                "applicability_source_gap",
            }
            else None
        )
        dimensions = (
            ApplicabilityState.UNKNOWN,
            EvidenceState.DATA_GAP,
            QcDirection.UNKNOWN,
            controlled_reason or (
                "source_unavailable"
                if "source" in outcome.reason_code
                else "applicability_source_gap"
            ),
        )
    elif outcome.status == "technical_error":
        dimensions = (
            ApplicabilityState.ERROR,
            EvidenceState.TECHNICAL_ERROR,
            QcDirection.UNKNOWN,
            (
                outcome.reason_code
                if outcome.reason_code in _PASSTHROUGH_TECHNICAL_REASONS
                else "snapshot_mismatch"
            ),
        )
    else:
        raise ValueError("unsupported surgery document final state")

    applicability, evidence_state, qc_direction, reason_code = dimensions
    return RuleDecision(
        rule_id=outcome.rule_id,
        snapshot_hash=snapshot.snapshot_hash,
        applicability=applicability,
        evidence_state=evidence_state,
        qc_direction=qc_direction,
        reason_code=reason_code,
        fact_refs=refs,
        evaluator_version=_TYPED_EVALUATOR_VERSION,
        confidence=None,
    )


def _clean(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def _documents(evidence_payload: Mapping[str, Any] | None) -> Mapping[str, Any] | None:
    if not isinstance(evidence_payload, Mapping):
        return None
    timeline = evidence_payload.get("programmatic_timeline")
    if not isinstance(timeline, Mapping):
        return None
    documents = timeline.get("documents")
    return documents if isinstance(documents, Mapping) else None


def _timeline_facts(evidence_payload: Mapping[str, Any] | None) -> Sequence[Any] | None:
    if not isinstance(evidence_payload, Mapping):
        return None
    facts = evidence_payload.get("timeline_facts")
    return facts if isinstance(facts, list) else None


def _row_text(row: Mapping[str, Any]) -> str:
    return _clean(
        row.get("content")
        or row.get("record_content")
        or row.get("assembled_text")
        or row.get("raw_text")
        or row.get("content_preview")
        or row.get("text_preview")
    )


def _source_rows(
    documents: Mapping[str, Any], source_keys: Sequence[str]
) -> list[tuple[str, int, str]]:
    rows: list[tuple[str, int, str]] = []
    for source_key in source_keys:
        raw_rows = documents.get(source_key)
        if not isinstance(raw_rows, list):
            continue
        for index, raw_row in enumerate(raw_rows[:_MAX_ROWS_PER_SOURCE], start=1):
            if not isinstance(raw_row, Mapping):
                continue
            text = _row_text(raw_row)
            if text:
                rows.append((source_key, index, text[:_MAX_ROW_CHARS]))
    return rows


def _substantive_rows(
    documents: Mapping[str, Any], source_keys: Sequence[str]
) -> list[tuple[str, int, str]]:
    return [
        row
        for row in _source_rows(documents, source_keys)
        if len(row[2]) >= _MIN_SUBSTANTIVE_CHARS
        and not _PLACEHOLDER_PATTERN.fullmatch(row[2])
    ]


def _consent_rows(documents: Mapping[str, Any]) -> list[tuple[str, int, str]]:
    dedicated = _substantive_rows(
        documents, ("anesthesia_consent", "anesthesia_consent_form")
    )
    generic = [
        row
        for row in _substantive_rows(documents, ("consent_form",))
        if _ANESTHESIA_CONSENT_PATTERN.search(row[2])
    ]
    return [*dedicated, *generic]


def _fact_value(fact: Mapping[str, Any], key: str) -> str:
    direct = _clean(fact.get(key))
    if direct:
        return direct
    normalized = fact.get("normalized_value")
    if isinstance(normalized, Mapping):
        return _clean(normalized.get(key))
    return ""


def _matching_facts(
    facts: Sequence[Any], *, fact_types: frozenset[str], source_keys: frozenset[str]
) -> list[Mapping[str, Any]]:
    matched: list[Mapping[str, Any]] = []
    for raw_fact in facts:
        if (
            not isinstance(raw_fact, Mapping)
            or raw_fact.get("current_visit_bound") is not True
        ):
            continue
        fact_type = _clean(raw_fact.get("fact_type")).lower()
        source_key = _clean(raw_fact.get("source_key")).lower()
        state = _clean(raw_fact.get("state") or raw_fact.get("event_status")).lower()
        if (
            fact_type in fact_types
            and source_key in source_keys
            and state in _PRESENT_STATES
        ):
            matched.append(raw_fact)
    return matched


def _anesthesia_state(facts: Sequence[Any]) -> str:
    matched = _matching_facts(
        facts,
        fact_types=_ANESTHESIA_FACT_TYPES,
        source_keys=frozenset({"anesthesia_record"}),
    )
    if not matched:
        return "absent"
    methods = {
        _fact_value(fact, "anesthesia_method") or _fact_value(fact, "method")
        for fact in matched
    }
    methods.discard("")
    if not methods:
        return "performed_unknown_method"
    if all(method in _LOCAL_ANESTHESIA_VALUES for method in methods):
        return "local"
    if any(method in _LOCAL_ANESTHESIA_VALUES for method in methods):
        return "unknown"
    return "nonlocal"


def _has_performed_surgery(facts: Sequence[Any]) -> bool:
    return bool(
        _matching_facts(
            facts,
            fact_types=_SURGERY_FACT_TYPES,
            source_keys=frozenset({"surgery_record"}),
        )
    )


def _has_emergency_exception(facts: Sequence[Any]) -> bool:
    return bool(
        _matching_facts(
            facts,
            fact_types=_EMERGENCY_FACT_TYPES,
            source_keys=frozenset({"surgery_record", "rescue_record"}),
        )
    )


def _typed_fact_state(
    snapshot: Luxian0609EvidenceSnapshot,
    *,
    fact_types: frozenset[str],
    source_key: str,
) -> tuple[str, str]:
    """只接受同一快照中的明确肯定/否定事实，并返回受控麻醉方式。"""

    states: set[str] = set()
    methods: set[str] = set()
    for fact in snapshot.facts:
        if fact.fact_type not in fact_types or fact.source_key != source_key:
            continue
        if fact.assertion is Assertion.NEGATED:
            states.add("absent")
            continue
        if (
            fact.assertion is Assertion.AFFIRMED
            and fact.event_status is EventStatus.PERFORMED
        ):
            states.add("present")
            normalized = fact.normalized_value
            if isinstance(normalized, Mapping):
                method = _clean(
                    normalized.get("anesthesia_method") or normalized.get("method")
                )
                if method:
                    methods.add(method)
    if len(states) != 1:
        return "unknown", ""
    method = next(iter(methods)) if len(methods) == 1 else ""
    return next(iter(states)), method


def _typed_source_gate(
    *,
    rule_id: str,
    source_key: str,
    snapshot: Luxian0609EvidenceSnapshot,
) -> _SurgeryDocumentOutcome | None:
    observation = next(
        (
            item
            for item in snapshot.observations
            if item.source_key == source_key
        ),
        None,
    )
    if observation is None:
        return _SurgeryDocumentOutcome(
            rule_id, "data_gap", "required_source_missing", "program"
        )
    if observation.query_state is QueryStatus.ERROR:
        return _SurgeryDocumentOutcome(
            rule_id, "technical_error", "source_query_error", "program"
        )
    if (
        observation.query_state is QueryStatus.UNAVAILABLE
        or observation.completeness is SourceCompleteness.UNPROVEN
        or observation.completeness is SourceCompleteness.TRUNCATED
    ):
        return _SurgeryDocumentOutcome(
            rule_id, "data_gap", "required_source_unavailable", "program"
        )
    return None


def _typed_observation_state(
    snapshot: Luxian0609EvidenceSnapshot, source_key: str
) -> str:
    observation = next(
        (
            item
            for item in snapshot.observations
            if item.source_key == source_key
        ),
        None,
    )
    if observation is None:
        return "missing"
    return observation.query_state.value


def _typed_anesthesia_trigger(
    snapshot: Luxian0609EvidenceSnapshot,
    materials: Luxian0609EvidenceMaterialStore | None,
) -> tuple[str, str, str]:
    """以同一快照材料确认麻醉事实，避免目标文书缺失时自证不适用。"""

    candidates: list[tuple[str, str, str]] = []
    for source_key in ("mr_surgery", "anesthesia_record"):
        state, method = _typed_fact_state(
            snapshot,
            fact_types=_ANESTHESIA_FACT_TYPES,
            source_key=source_key,
        )
        if state == "present":
            candidates.append((state, method, source_key))
    if materials is not None:
        try:
            surgery_rows = materials.rows("mr_surgery")
        except (EvidenceMaterialUnavailable, EvidenceMaterialTruncated):
            surgery_rows = ()
        qualified_methods = {
            _clean(row.get("anesthesia_method"))
            for row in surgery_rows
            if has_qualified_traditional_surgery_row(row)
            and _clean(row.get("anesthesia_method"))
        }
        if len(qualified_methods) == 1:
            candidates.append(("present", next(iter(qualified_methods)), "mr_surgery"))

        # 麻醉记录本身存在即可证明实施过麻醉；其结构化方式字段可作为
        # 手术主表方式的同级受控来源，不能依赖下游文本猜测。
        try:
            anesthesia_record_rows = materials.rows("anesthesia_record")
        except (EvidenceMaterialUnavailable, EvidenceMaterialTruncated):
            anesthesia_record_rows = ()
        anesthesia_record_methods: set[str] = set()
        for row in anesthesia_record_rows:
            structured_method = _clean(
                row.get("anesthesia_method") or row.get("method")
            )
            if structured_method:
                anesthesia_record_methods.add(structured_method)
                continue
            labeled_methods = {
                _clean(value)
                for value in _ANESTHESIA_METHOD_LABEL_PATTERN.findall(
                    _clean(row.get("record_content"))
                )
                if _clean(value) not in {"无", "未填", "未知", "-"}
            }
            if len(labeled_methods) == 1:
                anesthesia_record_methods.update(labeled_methods)
        if len(anesthesia_record_methods) == 1:
            candidates.append(
                (
                    "present",
                    next(iter(anesthesia_record_methods)),
                    "anesthesia_record",
                )
            )

        # 麻醉记录存在但方式字段没有可靠值时，只能证明“已实施”，不能
        # 把未知方式擅自视为非局部麻醉。
        if _typed_observation_state(snapshot, "anesthesia_record") == "available":
            candidates.append(("present", "", "anesthesia_record"))
    if not candidates:
        return "absent", "", ""
    methods = {method for _, method, _ in candidates if method}
    if len(methods) > 1:
        return "unknown", "", ""
    method = next(iter(methods)) if methods else ""
    source_key = (
        "mr_surgery"
        if any(item[2] == "mr_surgery" for item in candidates)
        else candidates[0][2]
    )
    return "present", method, source_key


def _qualified_traditional_surgery_present(
    materials: Luxian0609EvidenceMaterialStore | None,
) -> bool | None:
    """复用院内目录口径，目录未命中时才回退结构化等级。"""

    if materials is None:
        return None
    try:
        rows = materials.rows("mr_surgery")
    except (EvidenceMaterialUnavailable, EvidenceMaterialTruncated):
        return None
    return any(has_qualified_traditional_surgery_row(row) for row in rows)


_PERSON_SPLIT_PATTERN = re.compile(r"[\s、,，;；/|]+")
_PERSON_ROLE_PATTERN = re.compile(
    r"^(?:科主任|科副主任|术者|主刀|主持人|记录人|参加人员|讨论人员|医师|医生)\s*[:：]?\s*"
)
_PERSON_ROLE_SUFFIX_PATTERN = re.compile(
    r"[（(]\s*(?:术者|主刀|主持人|记录人|医师|医生|主任|副主任)\s*[)）]$"
)
_PERSON_TITLE_SUFFIX_PATTERN = re.compile(
    r"(?:[（(]\s*)?(?:副主任医师|主任医师|主治医师|住院医师|执业医师|"
    r"副主任医生|主任医生|主治医生|住院医生|医师|医生)(?:\s*[)）])?$"
)
_NON_PERSON_VALUES = frozenset(
    {"有", "无", "是", "否", "已签名", "签名", "已参加", "参加", "未知", "暂无"}
)


def _person_names(value: Any) -> set[str]:
    if value is None:
        return set()
    if isinstance(value, Mapping):
        names: set[str] = set()
        for key in ("name", "doctor_name", "physician_name", "staff_name"):
            names.update(_person_names(value.get(key)))
        if names:
            return names
        for nested in value.values():
            names.update(_person_names(nested))
        return names
    if isinstance(value, (list, tuple, set)):
        names: set[str] = set()
        for nested in value:
            names.update(_person_names(nested))
        return names

    text = _clean(value)
    if not text:
        return set()
    if text[:1] in {"[", "{"}:
        try:
            return _person_names(json.loads(text))
        except (TypeError, ValueError, json.JSONDecodeError):
            pass

    names: set[str] = set()
    for raw_name in _PERSON_SPLIT_PATTERN.split(text):
        name = _PERSON_ROLE_PATTERN.sub("", raw_name).strip(" :：()（）[]【】")
        name = _PERSON_ROLE_SUFFIX_PATTERN.sub("", name).strip()
        name = _PERSON_TITLE_SUFFIX_PATTERN.sub("", name.rstrip("。.")).strip(" :：()（）[]【】")
        if name and name not in _NON_PERSON_VALUES:
            names.add(name)
    return names


def _surgery_and_discussion_people(
    materials: Luxian0609EvidenceMaterialStore | None,
) -> tuple[set[str], set[str]] | None:
    if materials is None:
        return None
    try:
        formal_rows = tuple(materials.rows("surgery_record"))
        mr_rows = tuple(materials.rows("mr_surgery"))
        discussion_rows = materials.rows("presurg_discussion")
    except (EvidenceMaterialUnavailable, EvidenceMaterialTruncated):
        return None

    formal_names_by_row = tuple(
        _person_names(row.get("surgeon")) for row in formal_rows
    )
    if formal_names_by_row and any(formal_names_by_row):
        if any(not names for names in formal_names_by_row):
            return None
        surgeons = set().union(*formal_names_by_row)
    else:
        levelled_rows = [
            (normalize_surgery_level(row.get("surgical_level")), row)
            for row in mr_rows
        ]
        recognised_levels = [rank for rank, _row in levelled_rows if rank]
        if recognised_levels:
            highest = max(recognised_levels)
            selected_rows = [
                row for rank, row in levelled_rows if rank == highest
            ]
        else:
            selected_rows = list(mr_rows)
        names_by_row = tuple(
            _person_names(row.get("surgeon")) for row in selected_rows
        )
        if any(not names for names in names_by_row):
            return None
        surgeons = set().union(*names_by_row) if names_by_row else set()

    participants: set[str] = set()
    for row in discussion_rows:
        for field_name in (
            "discuss_staff",
            "host_name",
            "submitter",
            "physician_sign",
        ):
            participants.update(_person_names(row.get(field_name)))
    return surgeons, participants


def _unique_material_document_id(
    materials: Luxian0609EvidenceMaterialStore | None,
    source_key: str,
) -> str:
    """只接受单行、显式 document_id 的触发依据，不能猜测定位目标。"""

    if materials is None:
        return ""
    try:
        rows = materials.rows(source_key)
    except (EvidenceMaterialUnavailable, EvidenceMaterialTruncated):
        return ""
    if len(rows) != 1:
        return ""
    document_id = rows[0].get("document_id")
    return document_id.strip() if isinstance(document_id, str) else ""


def _with_trigger_document_id(
    facts: Mapping[str, Any],
    *,
    materials: Luxian0609EvidenceMaterialStore | None,
    source_keys: Sequence[str],
) -> dict[str, Any]:
    """把唯一可确认的触发文书 ID 留给内部聚合器，客户 DTO 会做安全投影。"""

    enriched = dict(facts)
    for source_key in source_keys:
        document_id = _unique_material_document_id(materials, source_key)
        if document_id:
            enriched["source_document_id"] = document_id
            enriched["source_document_type"] = source_key
            break
    return enriched


def _anesthesia_consent_rows(
    materials: Luxian0609EvidenceMaterialStore | None,
) -> tuple[Mapping[str, Any], ...] | None:
    """只保留可明确识别为麻醉知情同意书的结构化行。"""

    if not isinstance(materials, Luxian0609EvidenceMaterialStore):
        return None
    try:
        rows = tuple(materials.rows("consent_form"))
    except (EvidenceMaterialTruncated, EvidenceMaterialUnavailable):
        return None
    matched = []
    for row in rows:
        identity = _clean(
            " ".join(
                str(row.get(key) or "")
                for key in ("consent_type", "document_title", "record_content")
            )
        )
        if _ANESTHESIA_CONSENT_PATTERN.search(identity):
            matched.append(row)
    return tuple(matched)


def _minute_signature_state(value: Any) -> str:
    text = _clean(value)
    if not text:
        return "missing"
    if isinstance(value, datetime):
        return "present"
    # 同时验证分钟精度和日期时间有效性；保留中文日期分隔符。
    text = re.sub(r"\s+", " ", text.replace("年", "-").replace("月", "-").replace("日", " ")).strip()
    if not re.fullmatch(
        r"\d{4}[-/]\d{1,2}[-/]\d{1,2}[ T]\d{1,2}:\d{2}"
        r"(?::\d{2}(?:\.\d{1,6})?)?(?:Z|[+-]\d{2}:?\d{2})?",
        text,
    ):
        return "invalid"
    candidate = text.replace("/", "-").replace("Z", "+00:00")
    try:
        datetime.fromisoformat(candidate)
    except ValueError:
        # Preserve the existing single-digit month/day/hour input forms.
        for format_ in ("%Y-%m-%d %H:%M", "%Y-%m-%d %H:%M:%S"):
            try:
                datetime.strptime(candidate.replace("T", " "), format_)
                return "present"
            except ValueError:
                continue
        return "invalid"
    return "present"


def _consent_signature_value_present(value: Any) -> bool:
    text = _clean(value).strip("。.;；")
    return bool(text) and not (
        _STRUCTURED_ABSENT_VALUE_PATTERN.fullmatch(text)
        or re.fullmatch(r"[-—_/\\\s]+|null|none|n/?a|\[\]|\{\}|缺失", text, re.IGNORECASE)
        or re.match(r"^(?:未签|尚未签|未见签|拒绝签|拒签|无签)", text)
    )


def _anesthesia_consent_completeness(
    rows: Sequence[Mapping[str, Any]],
) -> tuple[str, list[str]]:
    """035 仅核对已确认麻醉同意书的患者/医师签名和分钟级时间。"""

    if len(rows) != 1:
        return "association_failed", []
    row = rows[0]
    missing: list[str] = []
    if not _consent_signature_value_present(row.get("patient_sign")):
        missing.append("patient_signature")
    if not _consent_signature_value_present(
        row.get("physician_sign") or row.get("surgeon_sign")
    ):
        missing.append("physician_signature")
    if _minute_signature_state(row.get("patient_sign_datetime")) != "present":
        missing.append("patient_signature_time")
    if _minute_signature_state(row.get("physician_sign_datetime")) != "present":
        missing.append("physician_signature_time")
    return ("incomplete" if missing else "complete"), missing


# 用户口径（2026-10-20，1019 C15）：急诊介入属于039急诊抢救例外。病程只认“急诊”
# 直接修饰介入/冠脉造影的写法，排除既往史；泛化的“急诊科”“急诊抢救后转入”不算。
_COURSE_EMERGENCY_INTERVENTION_PATTERN = re.compile(
    r"(?<![既往曾])急诊(?:行|下|予|予以)?"
    r"(?:冠脉造影|冠状动脉造影|PCI|经皮冠状动脉|冠脉介入|介入治疗|介入手术)"
)
_COURSE_HISTORY_PREFIX_PATTERN = re.compile(r"(?:既往|曾|年前|月前)[^。；;]{0,12}$")


def _course_records_emergency_intervention(
    materials: Luxian0609EvidenceMaterialStore | None,
) -> bool:
    rows = _anesthesia_visit_rows(materials, "daily_course_record") or ()
    for row in rows:
        text = str(row.get("record_content") or "")
        for match in _COURSE_EMERGENCY_INTERVENTION_PATTERN.finditer(text):
            if not _COURSE_HISTORY_PREFIX_PATTERN.search(text[max(0, match.start() - 16):match.start()]):
                return True
    return False


def _anesthesia_visit_rows(
    materials: Luxian0609EvidenceMaterialStore | None,
    source_key: str,
) -> tuple[Mapping[str, Any], ...] | None:
    if not isinstance(materials, Luxian0609EvidenceMaterialStore):
        return None
    try:
        return tuple(materials.rows(source_key))
    except (EvidenceMaterialTruncated, EvidenceMaterialUnavailable):
        return None


def _row_has_any(
    row: Mapping[str, Any],
    *,
    structured_fields: Sequence[str] = (),
    text_markers: Sequence[str] = (),
    negative_text_patterns: Sequence[str] = (),
) -> bool:
    """仅接受结构化非空值或未被局部否定的文本字段事实。"""

    if any(
        (value := _clean(row.get(field)))
        and not _STRUCTURED_ABSENT_VALUE_PATTERN.fullmatch(value)
        for field in structured_fields
    ):
        return True
    text = _row_text(row)
    if not text:
        return False
    # 不能将一处“未完成/未告知”扩散到同一文书的所有字段；按最小分句
    # 核对每一个标记，并只拒绝该标记所在分句的明确缺失表述。
    # 只在已知访视字段标签前切分紧连文本，不能把“清醒”等值切给下一字段。
    # 未知标签仍由空白/标点分隔；单字段空标签校验不依赖前缀词表。
    label = (
        r"(?:术前|术后|既往)?(?:ASA(?:分级|评估)?|气道(?:评估)?|禁食禁饮|禁食|禁饮|"
        r"麻醉手术史|麻醉史|麻醉风险告知|麻醉风险|风险告知|围术期风险|"
        r"麻醉医师签名|医师签名|意识|神志|呼吸系统|呼吸|循环|并发症|恶心呕吐|咽痛|特殊情况|备注)"
        r"\s*[:：]"
    )
    segments = tuple(
        segment.strip()
        for clause in re.split(r"[。；;，,\n]+", text)
        for segment in re.split(r"\s+(?=[^\s:：]+[:：])|(?=" + label + r")", clause)
        if segment.strip()
    )
    return any(
        marker in segment
        # 空值只否定该标签自身；后续未知标签的冒号不能抹掉前面已填的值。
        and not (
            (empty_label := re.search(label + r"[\s_—/\-（）()]*$", segment))
            and marker in empty_label.group(0)
        )
        # 空表单标题不能证明字段已经填写；仍保留“无并发症”等有效阴性。
        and not re.fullmatch(
            r"(?:分级|评估|情况|状态|记录|告知|签名|禁食|禁饮|[\s:：_—/\-（）()])*",
            segment.replace(marker, "", 1),
        )
        and not any(re.search(pattern, segment) for pattern in negative_text_patterns)
        for marker in text_markers
        for segment in segments
    )


def _anesthesia_visit_completeness(
    materials: Luxian0609EvidenceMaterialStore | None,
) -> tuple[str, dict[str, list[str]]]:
    """按已确认的最小口径核对术前、术后麻醉访视必填项。"""

    rows_by_source: dict[str, tuple[Mapping[str, Any], ...]] = {}
    for source_key in ("preane_surveil_record", "postane_surveil_record"):
        rows = _anesthesia_visit_rows(materials, source_key)
        if rows is None:
            return "unavailable", {}
        if not rows:
            return "association_failed", {}
        # 仅当分段行明确共享同一文书/业务 ID 时才允许合并；不同手术事件
        # 没有可靠关联键必须保持资料待核实，不能跨事件拼接字段。
        identity_fields = ("application_id", "anesthesia_id", "surgery_id", "document_id")
        identities = {
            _clean(row.get(field))
            for row in rows
            for field in identity_fields
            if _clean(row.get(field))
        }
        row_identity_sets = [
            {
                _clean(row.get(field))
                for field in identity_fields
                if _clean(row.get(field))
            }
            for row in rows
        ]
        common_identities = set.intersection(*row_identity_sets) if row_identity_sets else set()
        if len(rows) > 1 and not identities:
            return "association_failed", {}
        if len(rows) > 1 and not common_identities:
            return "association_failed", {}
        merged: dict[str, Any] = {}
        for row in sorted(rows, key=lambda item: len(_row_text(item)), reverse=True):
            for key, value in row.items():
                existing = _clean(merged.get(key))
                if (
                    existing
                    and not _STRUCTURED_ABSENT_VALUE_PATTERN.fullmatch(existing)
                ) or not _clean(value):
                    continue
                merged[key] = value
        texts = [_row_text(row) for row in rows if _row_text(row)]
        if texts:
            merged["record_content"] = "；".join(dict.fromkeys(texts))
        rows_by_source[source_key] = (merged,)

    pre = rows_by_source["preane_surveil_record"][0]
    post = rows_by_source["postane_surveil_record"][0]
    # 文书ID在不同来源本应不同；只用同名业务键识别明确事件冲突。
    # 保留无业务键单事件资料的既有语义，不能用A事件术前补B事件术后。
    try:
        anesthesia_rows = tuple(materials.rows("anesthesia_record")) if materials else ()
    except (EvidenceMaterialTruncated, EvidenceMaterialUnavailable):
        return "unavailable", {}
    for field in ("application_id", "anesthesia_id", "surgery_id"):
        identities = {
            value for row in (pre, post, *anesthesia_rows)
            if (value := _clean(row.get(field)))
        }
        if len(identities) > 1:
            return "association_failed", {}
    pre_checks = {
        "asa_level": _row_has_any(
            pre,
            structured_fields=("ASA_level", "asa_level"),
            text_markers=("ASA",),
            negative_text_patterns=(
                r"ASA(?:分级|评估)?(?:尚未|未)(?:完成|评估|分级|记录|填写)",
                r"(?:尚未|未|待)(?:完成|进行|行|填写|记录|评估|分级)?\s*ASA(?:分级|评估)?",
                r"(?:无|未见|未作|未行|未进行)\s*ASA(?:分级|评估)?",
                r"ASA(?:分级|评估)?\s*(?:无|未见|未作|未行|未进行)",
            ),
        ),
        "airway_assessment": _row_has_any(
            pre,
            text_markers=("气道",),
            negative_text_patterns=(
                r"气道(?:评估)?(?:尚未|未)(?:完成|评估|进行|记录|填写)",
                r"气道(?:评估)?(?:缺少|缺失|不全|不完整)",
                r"(?:尚未|未|待)(?:完成|进行|行|填写|记录|评估)?\s*气道(?:评估)?",
                r"(?:无|未见|未作|未行|未进行)\s*气道(?:评估)?",
                r"气道(?:评估)?\s*(?:无|未见|未作|未行|未进行)",
            ),
        ),
        "fasting_status": _row_has_any(pre, text_markers=("禁食", "禁饮")),
        "anesthesia_history": _row_has_any(
            pre,
            text_markers=("麻醉史", "麻醉手术史"),
            negative_text_patterns=(
                r"(?:麻醉史|麻醉手术史)(?:尚未|未)(?:询问|记录|评估)",
                r"(?:尚未|未|待)(?:完成|进行|行|询问|记录|评估)?\s*(?:麻醉史|麻醉手术史)",
            ),
        ),
        "risk_discussion": _row_has_any(
            pre,
            text_markers=("风险告知", "麻醉风险", "围术期风险"),
            negative_text_patterns=(
                r"(?:麻醉风险|围术期风险)(?:尚未|未)(?:告知|讨论|评估|记录)",
                r"风险告知(?:尚未|未)(?:完成|进行|记录)",
                r"(?:尚未|未|待)(?:完成|进行|行|告知|讨论|评估|记录)?\s*(?:麻醉风险|围术期风险|风险告知)",
                r"(?:无|未见|未作|未行|未进行)\s*(?:麻醉风险|围术期风险|风险告知)",
                r"(?:麻醉风险|围术期风险|风险告知)\s*(?:无|未见|未作|未行|未进行)",
            ),
        ),
        "anesthetist_signature": _row_has_any(
            pre,
            structured_fields=("anesthetist_sign",),
            text_markers=("医师签名",),
        ),
        "record_time": _minute_signature_state(authoritative_document_time_value(pre)) == "present",
    }
    post_checks = {
        "consciousness_status": _row_has_any(
            post, text_markers=("神志", "意识", "清醒")
        ),
        "respiratory_status": _row_has_any(post, text_markers=("呼吸",)),
        "circulatory_status": _row_has_any(post, text_markers=("循环",)),
        "complication_assessment": _row_has_any(
            post, text_markers=("并发症", "恶心呕吐", "咽痛", "特殊情况")
        ),
        "anesthetist_signature": _row_has_any(
            post,
            structured_fields=("anesthetist_sign",),
            text_markers=("医师签名",),
        ),
        "record_time": _minute_signature_state(authoritative_document_time_value(post)) == "present",
    }
    missing = {
        "preanesthesia_visit": [name for name, present in pre_checks.items() if not present],
        "postanesthesia_visit": [name for name, present in post_checks.items() if not present],
    }
    missing = {source: fields for source, fields in missing.items() if fields}
    return ("incomplete" if missing else "complete"), missing


# 结构化列可能承载模板内容而正文缺失；送检时以“标签：值”并入正文，避免误判未记载。
_VISIT_STRUCTURED_TEXT_FIELDS = {
    "preane_surveil_record": (
        ("condition_summary", "病情摘要"),
        ("planned_anesthesia_method", "拟施麻醉方式"),
        ("ASA_level", "ASA分级"),
    ),
    "postane_surveil_record": (
        ("surgery_name", "手术名称"),
        ("anesthesia_method", "麻醉方式"),
        ("resume_descirption", "恢复情况"),
    ),
}
# 院方口径：术前和术后24小时内须访视（替代基线的术后48小时）。
_POSTANESTHESIA_VISIT_WINDOW_SECONDS = 24 * 3600


def _visit_document_body(row: Mapping[str, Any], source: str) -> Any:
    body = row.get("record_content")
    if body is not None and not isinstance(body, str):
        return body
    structured = [
        f"{label}：{value}"
        for key, label in _VISIT_STRUCTURED_TEXT_FIELDS.get(source, ())
        if (value := _clean(row.get(key))) and not _STRUCTURED_ABSENT_VALUE_PATTERN.fullmatch(value)
    ]
    if body is None and not structured:
        return None
    return "\n".join([*structured, *([body] if body else [])])


def _visit_datetime(value: Any) -> datetime | None:
    from .extended_document.shared import _LX0609_HOSPITAL_TIMEZONE, _parse_datetime

    if isinstance(value, datetime):
        # 带时区的时刻统一换算为医院本地墙钟，与无时区的病历时间可比。
        return value.astimezone(_LX0609_HOSPITAL_TIMEZONE).replace(tzinfo=None) if value.tzinfo else value
    return _parse_datetime(value)


def _surgery_times(
    materials: Luxian0609EvidenceMaterialStore,
) -> tuple[tuple[datetime, datetime], ...] | None:
    """本次住院非局麻手术的 (开始, 结束) 时间；无法可靠取得时返回 None。

    运行病历质控时病案首页（mr_surgery）通常尚未生成，优先用手术记录的起止时间；
    手术记录缺失或任一份起止时间不全时，才回退到病案首页。
    """

    def rows(source_key: str) -> tuple[Mapping[str, Any], ...]:
        try:
            return tuple(materials.rows(source_key))
        except (EvidenceMaterialTruncated, EvidenceMaterialUnavailable, KeyError):
            return ()

    def first_time(row: Mapping[str, Any], fields: Sequence[str]) -> datetime | None:
        return next((parsed for key in fields if (parsed := _visit_datetime(row.get(key))) is not None), None)

    candidates = (
        ("surgery_record", ("surgery_begin_time", "surgery_begin_datetime"), ("surgery_end_time", "surgery_end_datetime")),
        ("mr_surgery", ("surgery_begin_datetime",), ("surgery_end_datetime",)),
    )
    for source_key, begin_fields, end_fields in candidates:
        surgeries = [
            row for row in rows(source_key)
            if _clean(row.get("anesthesia_method")) not in _LOCAL_ANESTHESIA_VALUES
        ]
        if not surgeries:
            continue
        times = [(first_time(row, begin_fields), first_time(row, end_fields)) for row in surgeries]
        if all(begin is not None and end is not None and begin <= end for begin, end in times):
            return tuple(times)  # type: ignore[arg-type]
    return None


def _surgery_end_times(materials: Luxian0609EvidenceMaterialStore) -> tuple[datetime, ...] | None:
    times = _surgery_times(materials)
    return tuple(end for _begin, end in times) if times else None


def _visit_window_states(
    materials: Luxian0609EvidenceMaterialStore, snapshot: Luxian0609EvidenceSnapshot,
) -> tuple[str, str]:
    """院方口径：每台非局麻手术开始前24小时内须有术前访视、结束后24小时内须有术后访视。"""

    times = _surgery_times(materials)
    if not times:
        return "unknown", "unknown"

    def visit_times(source_key: str) -> list[datetime]:
        return [
            visit_time
            for _ref, row in materials.document_rows(source_key, snapshot=snapshot)
            if (visit_time := _visit_datetime(authoritative_document_time_value(row))) is not None
        ]

    pre_visits, post_visits = visit_times("preane_surveil_record"), visit_times("postane_surveil_record")
    window = _POSTANESTHESIA_VISIT_WINDOW_SECONDS
    pre = all(any(0 <= (begin - visit).total_seconds() <= window for visit in pre_visits) for begin, _end in times)
    post = all(any(0 <= (visit - end).total_seconds() <= window for visit in post_visits) for _begin, end in times)
    return ("present" if pre else "absent"), ("present" if post else "absent")


def _postanesthesia_window_mature(materials: Luxian0609EvidenceMaterialStore) -> bool | None:
    """评价截止时间是否已过所有手术结束后24小时；无法判断时返回 None。"""

    end_times = _surgery_end_times(materials)
    if not end_times:
        return None
    try:
        horizon_rows = tuple(materials.rows("evaluation_context.horizon"))
    except (EvidenceMaterialTruncated, EvidenceMaterialUnavailable, KeyError):
        return None
    if len(horizon_rows) != 1:
        return None
    horizon = _visit_datetime(horizon_rows[0].get("horizon_datetime"))
    if horizon is None:
        horizon_date = _clean(horizon_rows[0].get("horizon_date"))
        try:
            # 仅有日期时按当日零点计，宁可暂不评价也不提前判缺陷。
            horizon = datetime.fromisoformat(horizon_date) if horizon_date else None
        except ValueError:
            horizon = None
    if horizon is None:
        return None
    return all((horizon - end).total_seconds() >= _POSTANESTHESIA_VISIT_WINDOW_SECONDS for end in end_times)


async def _typed_037_controlled_outcome(
    *, outcome: _SurgeryDocumentOutcome, snapshot: Luxian0609EvidenceSnapshot,
    materials: Luxian0609EvidenceMaterialStore, llm_client: SurgeryDocumentLLMClient | None,
) -> tuple[_SurgeryDocumentOutcome, int, int, int, int, float]:
    if outcome.reason_code not in {"anesthesia_visits_complete", "anesthesia_visit_incomplete"}:
        return outcome, 0, 0, 0, 0, 0.0
    pre_window, post_window = _visit_window_states(materials, snapshot)
    if "unknown" in (pre_window, post_window):
        # 无法取得手术起止时间时不能核对术前/术后24小时内访视，不送模、不作确定结论。
        return _SurgeryDocumentOutcome(outcome.rule_id, "data_gap", "authoritative_time_missing", "program"), 0, 0, 0, 0, 0.0
    documents = []
    reliable: dict[str, dict[str, str]] = {}
    group_keys: dict[str, tuple[str, str]] = {}
    sources = (("preane_surveil_record", "preanesthesia_visit"), ("postane_surveil_record", "postanesthesia_visit"))
    for source, visit in sources:
        for ref, row in materials.document_rows(source, snapshot=snapshot):
            states = {"record_time": "present" if (_minute_signature_state(authoritative_document_time_value(row)) == "present") else "absent"}
            signature = _clean(row.get("anesthetist_sign"))
            if signature and not _STRUCTURED_ABSENT_VALUE_PATTERN.fullmatch(signature):
                states["anesthetist_signature"] = "present"
            if visit == "preanesthesia_visit":
                states["preop_visit_within_24h"] = pre_window
            else:
                states["postop_visit_within_24h"] = post_window
            reliable[ref] = states
            group_keys[ref] = (source, _clean(row.get("document_id")) or _clean(row.get("id")) or ref)
            scope = "source_truncated" if any(row.get(key) is True for key in ("truncated", "content_truncated", "record_content_truncated")) else (
                "source_readiness_unproven" if any(row.get(key) is False for key in ("content_complete", "record_content_complete")) else "")
            documents.append(VisitDocument(ref, source, _visit_document_body(row, source),
                tuple(name for name in _VISIT_FIELDS[visit] if name not in states), scope))
    scope_issue = visit_document_scope_issue(documents)
    if scope_issue:
        return _SurgeryDocumentOutcome(outcome.rule_id, "data_gap", scope_issue, "program"), 0, 0, 0, 0, 0.0
    # 仅明确同一实际文书的分段行可共同取证；业务事件ID不能合并正文。
    groups: dict[tuple[str, str], list[VisitDocument]] = {}
    for doc in documents:
        groups.setdefault(group_keys[doc.document_ref], []).append(doc)
    grouped = []
    for (source, _identity), parts in groups.items():
        ref = parts[0].document_ref
        states = {name: ("present" if any(reliable[part.document_ref].get(name) == "present" for part in parts) else "absent")
            for name in {name for part in parts for name in reliable[part.document_ref]}}
        reliable[ref] = states
        visit = next(visit for key, visit in sources if key == source)
        grouped.append(VisitDocument(ref, source, "\n".join(dict.fromkeys(part.body for part in parts)),
            tuple(name for name in _VISIT_FIELDS[visit] if name not in states)))
    documents = grouped
    extraction = await extract_anesthesia_visit_facts(documents, llm_client)
    metrics = (extraction.llm_call_count, extraction.prompt_tokens, extraction.completion_tokens, extraction.total_tokens, extraction.api_time)
    if extraction.state == "technical_error":
        return _SurgeryDocumentOutcome(outcome.rule_id, "technical_error", extraction.reason_code, "llm"), *metrics
    if extraction.state != "ready":
        return _SurgeryDocumentOutcome(outcome.rule_id, "data_gap", extraction.reason_code, "llm" if extraction.llm_call_count else "program"), *metrics
    states_by_ref = {doc.document_ref: {**reliable[doc.document_ref], **extraction.fields.get(doc.document_ref, {})} for doc in documents}
    has_unknown = any("unknown" in states.values() for states in states_by_ref.values())
    missing = {}
    for source, visit in sources:
        rows = [states_by_ref[doc.document_ref] for doc in documents if doc.source_type == source]
        # 不适用（如未插管时的拔管情况）视同已满足。
        # 每份独立访视须自洽；另一文书的unknown不抹掉已确认的absent，也不充当缺项。
        fields = [name for name in _VISIT_FIELDS[visit] if any(row.get(name) == "absent" for row in rows)]
        if fields:
            missing[visit] = fields
    if not missing and has_unknown:
        return _SurgeryDocumentOutcome(outcome.rule_id, "data_gap", "semantic_extraction_unresolved", "llm"), *metrics
    facts = ({"failure_kind": "anesthesia_visit_incomplete", "performed_anesthesia_confirmed": True, "missing_fields_by_visit": missing}
        if missing else {"verification_kind": "anesthesia_visits_complete", "performed_anesthesia_confirmed": True,
            "checked_sources": [source for source, _ in sources], "checked_fields_by_visit": {visit: list(_VISIT_FIELDS[visit]) for _, visit in sources}})
    return _SurgeryDocumentOutcome(outcome.rule_id, "non_compliant" if missing else "compliant",
        "anesthesia_visit_incomplete" if missing else "anesthesia_visits_complete", "llm" if extraction.llm_call_count else "program", facts), *metrics


def _source_row_count(
    materials: Luxian0609EvidenceMaterialStore | None,
    source_key: str,
) -> int | None:
    if not isinstance(materials, Luxian0609EvidenceMaterialStore):
        return None
    try:
        return len(tuple(materials.rows(source_key)))
    except (EvidenceMaterialTruncated, EvidenceMaterialUnavailable):
        return None


def _anesthesia_record_association_state(
    materials: Luxian0609EvidenceMaterialStore | None,
) -> str:
    """多条麻醉记录仅在共享同一业务/文书 ID 时视为同一事件。"""

    if materials is None:
        return "unknown"
    try:
        rows = tuple(materials.rows("anesthesia_record"))
    except (EvidenceMaterialTruncated, EvidenceMaterialUnavailable):
        return "unknown"
    if len(rows) <= 1:
        return "unique"
    identity_fields = ("application_id", "anesthesia_id", "surgery_id", "document_id")
    identity_sets = [
        {_clean(row.get(field)) for field in identity_fields if _clean(row.get(field))}
        for row in rows
    ]
    common = set.intersection(*identity_sets) if identity_sets else set()
    return "unique" if common else "ambiguous"


def _anesthesia_surgery_begin_time(row: Mapping[str, Any]) -> tuple[datetime | None, bool]:
    """仅采用结构化或明确标签的手术开始时间，提交时间不证明手术归属。"""
    values = {
        parsed for field in ("surgery_begin_time", "surgery_begin_datetime")
        if (parsed := _visit_datetime(row.get(field))) is not None
    }
    for match in re.finditer(
        r"手术开始时间\s*[:：]\s*(\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}(?::\d{2}(?:\.\d{1,6})?)?(?:Z|[+-]\d{2}(?::?\d{2})?)?)",
        _clean(row.get("record_content")),
    ):
        if (parsed := _visit_datetime(match.group(1))) is not None:
            values.add(parsed)
    return (next(iter(values)), False) if len(values) == 1 else (None, bool(values))


def _typed_038_session_outcome(
    materials: Luxian0609EvidenceMaterialStore | None,
) -> _SurgeryDocumentOutcome | None:
    """主控代定口径（2026-10-18，待客户复核），基线038：按台核对麻醉记录。"""
    if materials is None:
        return None
    try:
        rows = tuple(materials.rows("anesthesia_record"))
        master_rows = tuple(
            row for row in materials.rows("mr_surgery")
            if has_qualified_traditional_surgery_row(row)
        )
    except (EvidenceMaterialTruncated, EvidenceMaterialUnavailable):
        return None
    # 无台次材料或原有单事件路径继续使用原受控麻醉事实；本分支解决逐台覆盖。
    if not master_rows or (len(master_rows) <= 1 and len(rows) <= 1):
        return None
    rule_id = "LX0609-04-04-03"
    groups = group_surgery_rows_by_start("mr_surgery", master_rows)
    if groups is None:
        return _SurgeryDocumentOutcome(rule_id, "data_gap", "association_failed", "program")
    required: set[int] = set()
    for index, group in enumerate(groups):
        methods = {
            method for row in group if (method := _clean(row.get("anesthesia_method")))
            and not _STRUCTURED_ABSENT_VALUE_PATTERN.fullmatch(method)
        }
        if len(methods) != 1:
            return _SurgeryDocumentOutcome(rule_id, "data_gap", "anesthesia_method_unavailable", "program")
        if next(iter(methods)) not in _LOCAL_ANESTHESIA_VALUES:
            required.add(index)
    if not required:
        return _SurgeryDocumentOutcome(rule_id, "not_applicable", "local_anesthesia_exception", "program")
    begins = [group[0]["surgery_begin_datetime"] for group in groups]
    covered: set[int] = set()
    for row in rows:
        begin, time_conflict = _anesthesia_surgery_begin_time(row)
        if time_conflict:
            return _SurgeryDocumentOutcome(rule_id, "data_gap", "association_failed", "program")
        candidates: set[int] = set()
        for index, group in enumerate(groups):
            business_match = any(
                _clean(row.get(field)) and _clean(row.get(field)) == _clean(component.get(field))
                for component in group for field in ("surgery_id", "application_id", "anesthesia_id")
            )
            event_begin = begins[index]
            time_match = begin is not None and (
                begin == event_begin
                or event_begin.time() == datetime.min.time()
                and begin.date() == event_begin.date()
                and sum(value.date() == begin.date() for value in begins) == 1
            )
            if business_match and begin is not None and not time_match:
                return _SurgeryDocumentOutcome(rule_id, "data_gap", "association_failed", "program")
            if business_match or time_match:
                candidates.add(index)
        if len(candidates) == 1:
            covered.update(candidates)
        elif len(groups) == len(rows) == 1 and begin is None:
            # 唯一台次、唯一记录保留既有存在性口径；多份记录仍需各自关联证据。
            covered.add(0)
        elif candidates or begin is None:
            return _SurgeryDocumentOutcome(rule_id, "data_gap", "association_failed", "program")
    missing = bool(required - covered)
    kind = "anesthesia_record_missing" if missing else "anesthesia_record_present"
    return _SurgeryDocumentOutcome(
        rule_id, "non_compliant" if missing else "compliant", kind, "program",
        {"failure_kind" if missing else "verification_kind": kind,
         "performed_anesthesia_confirmed": True, "checked_sources": ["anesthesia_record"]},
    )


def _typed_terminal_outcome(
    *,
    rule_id: str,
    snapshot: Luxian0609EvidenceSnapshot,
    materials: Luxian0609EvidenceMaterialStore | None = None,
) -> _SurgeryDocumentOutcome:
    """typed 迁移首版只做受控事实/来源四态判定，绝不回读旧 payload。"""

    if rule_id == "LX0609-04-01-02":
        performed_sources = ("surgery_record", "mr_surgery")
        binding_source_keys = _typed_binding_source_keys(rule_id)
        if not set(performed_sources).issubset(binding_source_keys):
            return _SurgeryDocumentOutcome(
                rule_id, "data_gap", "performed_surgery_source_unavailable", "program"
            )
        source_state_by_key: dict[str, str] = {}
        for source_key in performed_sources:
            fact_state, _ = _typed_fact_state(
                snapshot,
                fact_types=_SURGERY_FACT_TYPES,
                source_key=source_key,
            )
            source_state_by_key[source_key] = fact_state
        if (
            source_state_by_key.get("surgery_record") == "absent"
            and source_state_by_key.get("mr_surgery") == "present"
            and _qualified_traditional_surgery_present(materials) is False
        ):
            source_state_by_key["mr_surgery"] = "absent"
        if "present" not in source_state_by_key.values():
            if isinstance(snapshot, Luxian0609EvidenceSnapshot):
                applicability = resolve_surgery_applicability(
                    snapshot=snapshot,
                    materials=(
                        materials
                        if isinstance(materials, Luxian0609EvidenceMaterialStore)
                        else None
                    ),
                )
                if applicability.state == "technical_error":
                    return _SurgeryDocumentOutcome(
                        rule_id, "technical_error", "source_query_error", "program"
                    )
                if applicability.state == "not_applicable":
                    return _SurgeryDocumentOutcome(
                        rule_id, "not_applicable", "performed_surgery_absent", "program"
                    )
                return _SurgeryDocumentOutcome(
                    rule_id, "data_gap", applicability.reason_code, "program"
                )
            if set(source_state_by_key.values()) == {"absent"}:
                return _SurgeryDocumentOutcome(
                    rule_id, "not_applicable", "performed_surgery_absent", "program"
                )
            return _SurgeryDocumentOutcome(
                rule_id, "data_gap", "performed_surgery_fact_unavailable", "program"
            )
        if "rescue_record" not in _typed_binding_source_keys(rule_id):
            return _SurgeryDocumentOutcome(
                rule_id, "data_gap", "emergency_exception_source_unavailable", "program"
            )
        blocker = _typed_source_gate(
            rule_id=rule_id,
            source_key="rescue_record",
            snapshot=snapshot,
        )
        if blocker is not None:
            return blocker
        if isinstance(snapshot, Luxian0609EvidenceSnapshot):
            emergency_states = {
                state
                for source_key in ("surgery_record", "mr_surgery", "rescue_record")
                if (
                    state := _typed_fact_state(
                        snapshot,
                        fact_types=_EMERGENCY_FACT_TYPES,
                        source_key=source_key,
                    )[0]
                )
                != "unknown"
            }
            # 院方口径（2026-10-10）：文书未写急诊即视为非急诊；仅来源间明确冲突时未知。
            emergency_state = (
                next(iter(emergency_states))
                if len(emergency_states) == 1
                else "absent"
                if not emergency_states
                else "unknown"
            )
        else:
            # 保留纯函数单测/旧调用桩的既有边界；正式运行只走上面的同快照聚合。
            emergency_state, _ = _typed_fact_state(
                snapshot,
                fact_types=_EMERGENCY_FACT_TYPES,
                source_key="rescue_record",
            )
        if emergency_state == "absent" and _course_records_emergency_intervention(materials):
            emergency_state = "present"
        if emergency_state == "present":
            return _SurgeryDocumentOutcome(
                rule_id, "not_applicable", "emergency_rescue_exception", "program"
            )
        emergency_exception_unknown = emergency_state != "absent"
        blocker = _typed_source_gate(
            rule_id=rule_id,
            source_key="presurg_discussion",
            snapshot=snapshot,
        )
        if blocker is not None:
            return blocker
        if _typed_observation_state(snapshot, "presurg_discussion") == "empty":
            if emergency_exception_unknown:
                return _SurgeryDocumentOutcome(
                    rule_id,
                    "data_gap",
                    "surgeon_participation_unresolved",
                    "program",
                )
            facts = _with_trigger_document_id(
                {
                    "failure_kind": "preop_discussion_missing",
                    "performed_surgery_confirmed": True,
                    "emergency_rescue_exception_absent": True,
                    "checked_sources": ["presurg_discussion"],
                },
                materials=materials,
                source_keys=tuple(
                    source_key
                    for source_key in performed_sources
                    if source_state_by_key.get(source_key) == "present"
                ),
            )
            return _SurgeryDocumentOutcome(
                rule_id,
                "non_compliant",
                "preop_discussion_missing",
                "program",
                facts,
            )
        people = _surgery_and_discussion_people(materials)
        if people is None:
            return _SurgeryDocumentOutcome(
                rule_id, "data_gap", "surgeon_participation_unresolved", "program"
            )
        surgeons, discussion_participants = people
        if not surgeons or not discussion_participants:
            return _SurgeryDocumentOutcome(
                rule_id, "data_gap", "surgeon_participation_unresolved", "program"
            )
        matched_surgeons = surgeons & discussion_participants
        all_surgeons_matched = bool(surgeons) and surgeons.issubset(
            discussion_participants
        )
        if emergency_exception_unknown and not all_surgeons_matched:
            return _SurgeryDocumentOutcome(
                rule_id, "data_gap", "surgeon_participation_unresolved", "program"
            )
        identity_facts = {
            "surgeons": sorted(surgeons),
            "discussion_participants": sorted(discussion_participants),
            "matched_surgeons": sorted(matched_surgeons),
            "performed_surgery_confirmed": True,
            "discussion_state": "present",
            "surgeon_participation_state": (
                "confirmed" if all_surgeons_matched else "absent"
            ),
        }
        if not emergency_exception_unknown:
            identity_facts["emergency_rescue_exception_absent"] = True
        if all_surgeons_matched:
            identity_facts["verification_kind"] = (
                "preop_discussion_surgeon_participation_confirmed"
            )
            return _SurgeryDocumentOutcome(
                rule_id,
                "compliant",
                "surgeon_participation_confirmed",
                "program",
                identity_facts if not emergency_exception_unknown else None,
            )
        return _SurgeryDocumentOutcome(
            rule_id,
            "non_compliant",
            "surgeon_not_in_preop_discussion",
            "program",
            _with_trigger_document_id(
                {
                    "failure_kind": "surgeon_not_in_preop_discussion",
                    **identity_facts,
                },
                materials=materials,
                source_keys=tuple(
                    source_key
                    for source_key in performed_sources
                    if source_state_by_key.get(source_key) == "present"
                ),
            ),
        )

    # 034/035只核对麻醉知情同意书，不依赖麻醉方式；保持它们既有的
    # anesthesia_record 门控。036-038还要依赖方式和手术主表，二者共同
    # 构成受控资料链，查询失败不能被另一个来源掩盖。
    required_source_keys = ["anesthesia_record"]
    if rule_id in {"LX0609-04-04-01", "LX0609-04-04-02", "LX0609-04-04-03"}:
        required_source_keys.append("mr_surgery")
    for source_key in required_source_keys:
        blocker = _typed_source_gate(
            rule_id=rule_id,
            source_key=source_key,
            snapshot=snapshot,
        )
        if blocker is not None:
            return blocker
    if rule_id == "LX0609-04-04-03":
        session_outcome = _typed_038_session_outcome(materials)
        if session_outcome is not None:
            return session_outcome
    anesthesia_state, anesthesia_method, anesthesia_trigger_source = (
        _typed_anesthesia_trigger(snapshot, materials)
    )
    if anesthesia_state == "absent":
        return _SurgeryDocumentOutcome(
            rule_id, "not_applicable", "performed_anesthesia_absent", "program"
        )
    if anesthesia_state != "present":
        return _SurgeryDocumentOutcome(
            rule_id, "data_gap", "performed_anesthesia_fact_unavailable", "program"
        )
    if _anesthesia_record_association_state(materials) == "ambiguous":
        return _SurgeryDocumentOutcome(rule_id, "data_gap", "association_failed", "program")
    is_local = anesthesia_method in _LOCAL_ANESTHESIA_VALUES
    if rule_id in {"LX0609-04-04-01", "LX0609-04-04-02", "LX0609-04-04-03"}:
        if is_local:
            return _SurgeryDocumentOutcome(
                rule_id, "not_applicable", "local_anesthesia_exception", "program"
            )
        if not anesthesia_method:
            return _SurgeryDocumentOutcome(
                rule_id, "data_gap", "anesthesia_method_unavailable", "program"
            )

    if rule_id in _ANESTHESIA_CONSENT_RULE_IDS:
        blocker = _typed_source_gate(
            rule_id=rule_id,
            source_key="consent_form",
            snapshot=snapshot,
        )
        if blocker is not None:
            return blocker
        if _typed_observation_state(snapshot, "consent_form") == "empty":
            if rule_id == "LX0609-11-02-02":
                return _SurgeryDocumentOutcome(
                    rule_id, "not_applicable", "anesthesia_consent_absent", "program"
                )
            facts = _with_trigger_document_id(
                {
                    "failure_kind": "anesthesia_consent_missing",
                    "performed_anesthesia_confirmed": True,
                    "consent_state": "missing",
                    "checked_sources": ["consent_form"],
                },
                materials=materials,
                source_keys=(anesthesia_trigger_source,),
            )
            return _SurgeryDocumentOutcome(
                rule_id,
                "non_compliant",
                "anesthesia_consent_missing",
                "program",
                facts,
            )
        consent_rows = _anesthesia_consent_rows(materials)
        if consent_rows is None:
            return _SurgeryDocumentOutcome(
                rule_id, "data_gap", "required_field_missing", "program"
            )
        if not consent_rows:
            if rule_id == "LX0609-11-02-02":
                return _SurgeryDocumentOutcome(
                    rule_id, "not_applicable", "anesthesia_consent_absent", "program"
                )
            return _SurgeryDocumentOutcome(
                rule_id,
                "non_compliant",
                "anesthesia_consent_missing",
                "program",
                {
                    "failure_kind": "anesthesia_consent_missing",
                    "performed_anesthesia_confirmed": True,
                    "consent_state": "missing",
                    "checked_sources": ["consent_form"],
                },
            )
        if rule_id == "LX0609-11-02-01":
            return _SurgeryDocumentOutcome(
                rule_id,
                "compliant",
                "anesthesia_consent_present",
                "program",
                {
                    "verification_kind": "anesthesia_consent_present",
                    "performed_anesthesia_confirmed": True,
                    "checked_sources": ["consent_form"],
                },
            )
        completeness, missing_fields = _anesthesia_consent_completeness(consent_rows)
        if completeness == "association_failed":
            return _SurgeryDocumentOutcome(
                rule_id, "data_gap", "association_failed", "program"
            )
        if completeness == "complete":
            return _SurgeryDocumentOutcome(
                rule_id,
                "compliant",
                "anesthesia_consent_complete",
                "program",
                {
                    "verification_kind": "anesthesia_consent_complete",
                    "performed_anesthesia_confirmed": True,
                    "checked_fields": [
                        "patient_signature",
                        "physician_signature",
                        "patient_signature_time",
                        "physician_signature_time",
                    ],
                },
            )
        return _SurgeryDocumentOutcome(
            rule_id,
            "non_compliant",
            "anesthesia_consent_incomplete",
            "program",
            {
                "failure_kind": "anesthesia_consent_incomplete",
                "performed_anesthesia_confirmed": True,
                "missing_fields": missing_fields,
            },
        )

    if rule_id in _ANESTHESIA_VISIT_RULE_IDS:
        typed_visit_sources = (
            "preane_surveil_record",
            "postane_surveil_record",
        )
        for source_key in typed_visit_sources:
            blocker = _typed_source_gate(
                rule_id=rule_id,
                source_key=source_key,
                snapshot=snapshot,
            )
            if blocker is not None:
                return blocker
        missing_visit_sources = tuple(
            source_key
            for source_key in typed_visit_sources
            if _typed_observation_state(snapshot, source_key) == "empty"
        )
        if missing_visit_sources == ("postane_surveil_record",) and _postanesthesia_window_mature(materials) is False:
            # 只缺术后访视且手术结束尚未满24小时：访视时限未到，不提前判缺失。
            return _SurgeryDocumentOutcome(rule_id, "not_applicable", "evaluation_window_not_mature", "program")
        if missing_visit_sources:
            facts = _with_trigger_document_id(
                {
                    "failure_kind": "anesthesia_visit_missing",
                    "performed_anesthesia_confirmed": True,
                    "missing_visit_sources": list(missing_visit_sources),
                },
                materials=materials,
                source_keys=(anesthesia_trigger_source,),
            )
            if rule_id == "LX0609-04-04-02":
                # 037 同时核对术前、术后访视的完整性。来源查询已经完成、且
                # 已确认实施非局部麻醉时，任一访视缺失就是本规则的明确缺陷；
                # 036 的存在性检查不能把 037 的缺失改写成“不适用”。
                return _SurgeryDocumentOutcome(
                    rule_id,
                    "non_compliant",
                    "anesthesia_visit_missing",
                    "program",
                    facts,
                )
            return _SurgeryDocumentOutcome(
                rule_id,
                "non_compliant",
                "anesthesia_visit_missing",
                "program",
                facts,
            )
        if rule_id == "LX0609-04-04-01":
            return _SurgeryDocumentOutcome(
                rule_id,
                "compliant",
                "anesthesia_visits_present",
                "program",
                {
                    "verification_kind": "anesthesia_visits_present",
                    "performed_anesthesia_confirmed": True,
                    "checked_sources": list(typed_visit_sources),
                },
            )
        completeness, missing_fields = _anesthesia_visit_completeness(materials)
        if completeness == "unavailable":
            return _SurgeryDocumentOutcome(
                rule_id, "data_gap", "required_field_missing", "program"
            )
        if completeness == "association_failed":
            return _SurgeryDocumentOutcome(
                rule_id, "data_gap", "association_failed", "program"
            )
        if completeness == "incomplete":
            return _SurgeryDocumentOutcome(
                rule_id,
                "non_compliant",
                "anesthesia_visit_incomplete",
                "program",
                {
                    "failure_kind": "anesthesia_visit_incomplete",
                    "performed_anesthesia_confirmed": True,
                    "missing_fields_by_visit": missing_fields,
                },
            )
        return _SurgeryDocumentOutcome(
            rule_id,
            "compliant",
            "anesthesia_visits_complete",
            "program",
            {
                "verification_kind": "anesthesia_visits_complete",
                "performed_anesthesia_confirmed": True,
                "checked_sources": list(typed_visit_sources),
                "checked_fields_by_visit": {
                    "preanesthesia_visit": [
                        "asa_level",
                        "airway_assessment",
                        "fasting_status",
                        "anesthesia_history",
                        "risk_discussion",
                        "anesthetist_signature",
                        "record_time",
                    ],
                    "postanesthesia_visit": [
                        "consciousness_status",
                        "respiratory_status",
                        "circulatory_status",
                        "complication_assessment",
                        "anesthetist_signature",
                        "record_time",
                    ],
                },
            },
        )

    # 038只判麻醉记录单存在；具体字段规范不在该客户质控点范围。
    anesthesia_record_state = _typed_observation_state(snapshot, "anesthesia_record")
    if anesthesia_record_state == "available":
        return _SurgeryDocumentOutcome(
            rule_id,
            "compliant",
            "anesthesia_record_present",
            "program",
            {
                "verification_kind": "anesthesia_record_present",
                "performed_anesthesia_confirmed": True,
                "checked_sources": ["anesthesia_record"],
            },
        )
    if (
        anesthesia_record_state == "empty"
        and anesthesia_trigger_source == "mr_surgery"
        and anesthesia_method
        and not is_local
    ):
        return _SurgeryDocumentOutcome(
            rule_id,
            "non_compliant",
            "anesthesia_record_missing",
            "program",
            {
                "failure_kind": "anesthesia_record_missing",
                "performed_anesthesia_confirmed": True,
                "checked_sources": ["anesthesia_record"],
            },
        )
    if anesthesia_record_state == "empty":
        return _SurgeryDocumentOutcome(
            rule_id, "not_applicable", "qualified_nonlocal_anesthesia_absent", "program"
        )
    return _SurgeryDocumentOutcome(
        rule_id, "data_gap", "anesthesia_record_fact_conflict", "program"
    )


def _clean_presurg_body(value: Any) -> str:
    if not isinstance(value, str):
        return ""
    candidate = value.strip()
    if not candidate or candidate.casefold() in _PRESURG_PLACEHOLDER_VALUES:
        return ""
    return candidate


def _associate_presurg_summaries_to_surgeries(
    *,
    summary_rows: Sequence[Mapping[str, Any]],
    materials: Luxian0609EvidenceMaterialStore,
) -> tuple[int, int] | None:
    """主控代定口径（2026-10-18，待客户复核），基线029：逐台关联非空小结。"""
    events, _reason = build_surgery_document_events(materials)
    if not events:
        return None
    covered: set[int] = set()
    for row in summary_rows:
        if not _clean_presurg_body(row.get("record_content")):
            continue
        association = associate_preop_document_to_surgery_event(
            events=events, procedure_name=summary_surgery_name_from_row(row),
            record_time=_visit_datetime(authoritative_document_time_value(row)),
            planned_surgery_time=summary_planned_surgery_time_from_row(row),
        )
        if association.state != "matched" or association.event_index is None:
            return None
        covered.add(association.event_index)
    return (len(events), len(covered)) if covered else None


def _typed_029_order_trigger(
    *,
    snapshot: Luxian0609EvidenceSnapshot,
    materials: Luxian0609EvidenceMaterialStore,
) -> tuple[str, tuple[str, ...]]:
    """按 Planner 声明的医嘱 alternative 读取029触发事实。"""

    planned_rule = PlannedRule.for_rule_id("LX0609-04-01-01")
    order_requirement = next(
        requirement
        for requirement in planned_rule.trigger_requirements
        if requirement.fact_type == "current_visit_surgery_order_confirmed"
    )
    order_facts = tuple(
        fact
        for fact in snapshot.facts
        if fact.fact_type == order_requirement.fact_type
        and fact.source_key in order_requirement.allowed_source_keys
        and fact.trigger_scope.value == order_requirement.trigger_scope
        and fact.current_visit_relevance.value
        == order_requirement.current_visit_relevance
    )
    positive_facts = tuple(
        fact
        for fact in order_facts
        if fact.assertion is Assertion.AFFIRMED
        and fact.event_status.value in order_requirement.allowed_event_statuses
    )
    if positive_facts:
        # FactV2 只表达来源整体状态；逐条阳性医嘱由 provider 的同一严格谓词
        # 在冻结材料中选择，再交给公共证据投影还原真实医嘱 ID。
        try:
            observation = next(
                (
                    item
                    for item in snapshot.observations
                    if item.source_key == "inpat_nondrug_order"
                ),
                None,
            )
            if observation is None:
                return "data_gap", ()
            document_rows = materials.document_rows(
                "inpat_nondrug_order", snapshot=snapshot
            )
            assertion, selected_ids = classify_current_visit_surgery_order_rows(
                rows=tuple(row for _, row in document_rows),
                completeness=observation.completeness,
            )
            if assertion != "affirmed":
                return "data_gap", ()
            selected_id_set = set(selected_ids)
            selected_refs = tuple(
                document_ref
                for document_ref, row in document_rows
                if next(
                    (
                        str(row.get(field) or "").strip()
                        for field in ("order_id", "document_id", "id")
                        if str(row.get(field) or "").strip()
                    ),
                    "",
                )
                in selected_id_set
            )
        except (EvidenceMaterialUnavailable, EvidenceMaterialTruncated, ValueError):
            selected_refs = ()
        # Fact ref proves Planner-contract applicability; material refs are the sole
        # customer-document coordinate input. The former intentionally has no ID.
        return "applicable", tuple(
            sorted({*(fact.fact_id for fact in positive_facts), *selected_refs})
        )

    observation = next(
        (
            item
            for item in snapshot.observations
            if item.source_key == "inpat_nondrug_order"
        ),
        None,
    )
    if observation is None:
        return "data_gap", ()
    if observation.query_state is QueryStatus.ERROR:
        return "technical_error", ()
    if (
        observation.query_state is QueryStatus.UNAVAILABLE
        or observation.completeness is not SourceCompleteness.COMPLETE
    ):
        return "data_gap", ()
    if any(fact.assertion is Assertion.UNCERTAIN for fact in order_facts):
        return "data_gap", ()
    if observation.query_state is QueryStatus.EMPTY or any(
        fact.assertion is Assertion.NEGATED for fact in order_facts
    ):
        return "not_applicable", ()
    return "data_gap", ()


def _typed_document_refs(
    *,
    materials: Luxian0609EvidenceMaterialStore,
    snapshot: Luxian0609EvidenceSnapshot,
    source_key: str,
) -> tuple[str, ...]:
    """复用公共材料投影返回本次已核验的文书坐标。"""

    try:
        return tuple(
            document_ref
            for document_ref, _ in materials.document_rows(
                source_key, snapshot=snapshot
            )
        )
    except (EvidenceMaterialUnavailable, EvidenceMaterialTruncated, ValueError):
        return ()


def _typed_precise_source_refs(
    *,
    snapshot: Luxian0609EvidenceSnapshot,
    materials: Luxian0609EvidenceMaterialStore,
    source_keys: Sequence[str],
) -> tuple[str, ...]:
    """只绑定本次结论实际使用的事实与逐行材料，不回退到全来源快照。"""

    selected_keys = frozenset(source_keys)
    refs = [
        fact.fact_id
        for fact in snapshot.facts
        if fact.source_key in selected_keys
    ]
    for source_key in source_keys:
        refs.extend(
            _typed_document_refs(
                materials=materials,
                snapshot=snapshot,
                source_key=source_key,
            )
        )
    return tuple(dict.fromkeys(refs))


def _typed_precise_terminal_refs(
    *,
    outcome: _SurgeryDocumentOutcome,
    snapshot: Luxian0609EvidenceSnapshot,
    materials: Luxian0609EvidenceMaterialStore,
) -> tuple[str, ...]:
    """按规则已使用的触发和目标资料选择证据，绝不由下游补全来源。"""

    rule_id = outcome.rule_id
    if rule_id == "LX0609-04-01-01":
        facts = outcome.customer_display_facts or {}
        source_keys: list[str] = []
        # 医嘱触发的阳性行已在 outcome.fact_refs 中，不能追加整表无关医嘱。
        if facts.get("surgery_trigger_kind") == "performed_surgery":
            source_keys.extend(
                source_key
                for source_key in ("surgery_record", "mr_surgery")
                if _typed_fact_state(
                    snapshot,
                    fact_types=_SURGERY_FACT_TYPES,
                    source_key=source_key,
                )[0]
                == "present"
            )
        if _typed_observation_state(snapshot, "presurg_summary") != "empty":
            source_keys.append("presurg_summary")
        refs = tuple(
            dict.fromkeys(
                (
                    *outcome.fact_refs,
                    *_typed_precise_source_refs(
                        snapshot=snapshot,
                        materials=materials,
                        source_keys=source_keys,
                    ),
                )
            )
        )
        if refs or outcome.status != "not_applicable":
            return refs
        # 没有手术医嘱且未实施手术时，只有来源级的明确空结果可证明不适用；
        # 仍限定为本规则实际使用的三类触发来源。
        return tuple(
            observation.snapshot_ref.removeprefix("sha256:")
            for observation in snapshot.observations
            if observation.source_key
            in {"inpat_nondrug_order", "surgery_record", "mr_surgery"}
        )

    if rule_id in {"LX0609-11-02-01", "LX0609-11-02-02", "LX0609-04-04-01", "LX0609-04-04-02"}:
        _state, _method, trigger_source = _typed_anesthesia_trigger(snapshot, materials)
        source_keys = [trigger_source] if trigger_source else []
        if rule_id in {"LX0609-11-02-01", "LX0609-11-02-02"}:
            if _typed_observation_state(snapshot, "consent_form") != "empty":
                source_keys.append("consent_form")
        else:
            source_keys.extend(
                source_key
                for source_key in ("preane_surveil_record", "postane_surveil_record")
                if _typed_observation_state(snapshot, source_key) != "empty"
            )
        return _typed_precise_source_refs(
            snapshot=snapshot, materials=materials, source_keys=source_keys
        )

    if rule_id == "LX0609-04-04-03":
        source_keys = (
            ("anesthesia_record",)
            if outcome.reason_code == "anesthesia_record_present"
            else ("mr_surgery",)
        )
        return _typed_precise_source_refs(
            snapshot=snapshot, materials=materials, source_keys=source_keys
        )

    if rule_id == "LX0609-04-01-02":
        source_keys = [
            source_key
            for source_key in ("surgery_record", "mr_surgery")
            if _typed_fact_state(
                snapshot,
                fact_types=_SURGERY_FACT_TYPES,
                source_key=source_key,
            )[0]
            == "present"
        ]
        for source_key in ("rescue_record", "presurg_discussion"):
            if _typed_observation_state(snapshot, source_key) != "empty":
                source_keys.append(source_key)
        return _typed_precise_source_refs(
            snapshot=snapshot, materials=materials, source_keys=source_keys
        )
    return outcome.fact_refs


def _typed_029_trigger_display_facts(*, performed_triggered: bool) -> dict[str, object]:
    """仅把实际触发来源投影为展示事实，禁止医嘱触发伪称已实施。"""

    if performed_triggered:
        return {
            "surgery_trigger_kind": "performed_surgery",
            "performed_surgery_confirmed": True,
        }
    return {
        "surgery_trigger_kind": "surgery_order",
        "surgery_order_confirmed": True,
    }


# 院方口径（2026-10-10）：纤维支气管镜下活检、内镜下息肉切除等自然腔道内镜操作不需要
# 术前小结；腹腔镜、胸腔镜、关节镜等镜下手术仍按手术核对。
_ENDOSCOPIC_PROCEDURE_PATTERN = re.compile(r"支气管镜|纤支镜|胃镜|肠镜|十二指肠镜|内镜|内窥镜")
_SURGICAL_SCOPE_PATTERN = re.compile(r"腹腔镜|胸腔镜|关节镜|宫腔镜|膀胱镜|输尿管镜|椎间孔镜|鼻内镜|耳内镜")


def _only_endoscopic_procedures(materials: Luxian0609EvidenceMaterialStore) -> bool:
    names: list[str] = []
    for source_key in ("surgery_record", "mr_surgery"):
        try:
            rows = materials.rows(source_key)
        except (EvidenceMaterialUnavailable, EvidenceMaterialTruncated, KeyError, ValueError):
            return False
        names.extend(
            _clean(row.get("surgery_name") or row.get("operation_name") or row.get("procedure_name"))
            for row in rows
        )
    return bool(names) and all(
        name
        and _ENDOSCOPIC_PROCEDURE_PATTERN.search(name)
        and not _SURGICAL_SCOPE_PATTERN.search(name)
        for name in names
    )


async def _typed_029_outcome(
    *,
    snapshot: Luxian0609EvidenceSnapshot,
    materials: Luxian0609EvidenceMaterialStore,
) -> tuple[_SurgeryDocumentOutcome, int, int, int, int, float]:
    """029：确认手术事件覆盖后，核对每台手术的术前小结存在性。"""

    if _only_endoscopic_procedures(materials):
        return (
            _SurgeryDocumentOutcome(
                "LX0609-04-01-01", "not_applicable", "endoscopic_procedure_exception", "program"
            ),
            0, 0, 0, 0, 0.0,
        )

    # 029 是纯存在性规则：已证明仅一台手术时，只看术前小结正文是否为
    # 非空、非占位值。多台手术缺少稳定关联时不得让任一小结覆盖全部事件。
    # 模型、标题、时间和长度均不得参与正文存在性判定。
    order_state, order_refs = _typed_029_order_trigger(
        snapshot=snapshot,
        materials=materials,
    )
    performed_applicability = resolve_surgery_applicability(
        snapshot=snapshot,
        materials=materials,
    )
    performed_triggered = performed_applicability.state == "applicable"
    if order_state != "applicable" and not performed_triggered:
        if (
            order_state == "technical_error"
            or performed_applicability.state == "technical_error"
        ):
            outcome = _SurgeryDocumentOutcome(
                "LX0609-04-01-01", "technical_error", "source_query_error", "program"
            )
        elif (
            order_state == "not_applicable"
            and performed_applicability.state == "not_applicable"
        ):
            outcome = _SurgeryDocumentOutcome(
                "LX0609-04-01-01", "not_applicable", "performed_surgery_absent", "program"
            )
        else:
            outcome = _SurgeryDocumentOutcome(
                "LX0609-04-01-01", "data_gap", "applicability_source_gap", "program"
            )
        return (
            outcome,
            0, 0, 0, 0, 0.0,
        )
    trigger_display_facts = _typed_029_trigger_display_facts(
        performed_triggered=performed_triggered
    )
    target_gate = _typed_source_gate(
        rule_id="LX0609-04-01-01", source_key="presurg_summary", snapshot=snapshot
    )
    if target_gate is not None:
        return replace(target_gate, fact_refs=order_refs), 0, 0, 0, 0, 0.0
    if _typed_observation_state(snapshot, "presurg_summary") == "empty":
        return (
            _SurgeryDocumentOutcome(
                "LX0609-04-01-01",
                "non_compliant",
                "preop_summary_missing",
                "program",
                {
                    "failure_kind": "surgery_document_missing",
                    "target_document": "presurg_summary",
                    **trigger_display_facts,
                },
                order_refs,
            ),
            0, 0, 0, 0, 0.0,
        )
    try:
        summary_rows = materials.rows("presurg_summary")
    except EvidenceMaterialTruncated:
        return (
            _SurgeryDocumentOutcome(
                "LX0609-04-01-01",
                "data_gap",
                "preop_summary_source_truncated",
                "program",
                None,
                order_refs,
            ),
            0, 0, 0, 0, 0.0,
        )
    except EvidenceMaterialUnavailable:
        return (
            _SurgeryDocumentOutcome(
                "LX0609-04-01-01",
                "data_gap",
                "preop_summary_source_unavailable",
                "program",
                None,
                order_refs,
            ),
            0, 0, 0, 0, 0.0,
        )
    summary_refs = _typed_document_refs(
        materials=materials, snapshot=snapshot, source_key="presurg_summary"
    )
    # 旧已实施手术路径仍使用 snapshot 坐标，保持没有传入 material store 的
    # 既有绑定调用兼容；新增医嘱触发路径才输出已验证的逐文书坐标。
    selected_refs = (
        tuple(sorted({*order_refs, *summary_refs}))
        if order_state == "applicable"
        else ()
    )
    performed_event_count: int | None = 0
    count_reason = ""
    if performed_triggered:
        performed_event_count, count_reason = count_associated_performed_surgery_events(
            materials
        )
        if performed_event_count is None:
            return (
                _SurgeryDocumentOutcome(
                    "LX0609-04-01-01", "data_gap", count_reason, "program", None,
                    selected_refs,
                ),
                0, 0, 0, 0, 0.0,
            )
    if performed_triggered and performed_event_count is not None and performed_event_count > 1:
        associated_counts = _associate_presurg_summaries_to_surgeries(
            summary_rows=summary_rows,
            materials=materials,
        )
        if associated_counts is not None:
            performed_event_count, associated_summary_count = associated_counts
            if associated_summary_count < performed_event_count:
                return (
                    _SurgeryDocumentOutcome(
                        "LX0609-04-01-01",
                        "non_compliant",
                        "preop_summary_missing",
                        "program",
                        {
                            "failure_kind": "surgery_document_missing",
                            "target_document": "presurg_summary",
                            **trigger_display_facts,
                        },
                        selected_refs,
                    ),
                    0, 0, 0, 0, 0.0,
                )
        else:
            # 仅有行数或无法唯一归属的非空小结，不能证明逐台覆盖或逐台缺失。
            return (
                _SurgeryDocumentOutcome(
                    "LX0609-04-01-01",
                    "data_gap",
                    "association_failed",
                    "program",
                    None,
                    selected_refs,
                ),
                0, 0, 0, 0, 0.0,
            )
    if any(_clean_presurg_body(row.get("record_content")) for row in summary_rows):
        return (
            _SurgeryDocumentOutcome(
                "LX0609-04-01-01",
                "compliant",
                "preop_summary_present",
                "program",
                {
                    "verification_kind": "surgery_document_present",
                    "target_document": "presurg_summary",
                    **trigger_display_facts,
                },
                selected_refs,
            ),
            0, 0, 0, 0, 0.0,
        )
    return (
        _SurgeryDocumentOutcome(
            "LX0609-04-01-01",
            "non_compliant",
            "preop_summary_blank",
            "program",
            {
                "failure_kind": "surgery_document_blank",
                "target_document": "presurg_summary",
                **trigger_display_facts,
            },
            selected_refs,
        ),
        0, 0, 0, 0, 0.0,
    )

def _context(
    documents: Mapping[str, Any], source_groups: Sequence[Sequence[str]]
) -> str:
    parts: list[str] = []
    seen: set[tuple[str, int]] = set()
    for group in source_groups:
        rows = (
            _consent_rows(documents)
            if tuple(group) == _CONSENT_SOURCES
            else _substantive_rows(documents, group)
        )
        for source_key, index, text in rows:
            key = (source_key, index)
            if key in seen:
                continue
            seen.add(key)
            parts.append(f"[{source_key}-{index}] {text}")
    return "\n".join(parts)[:_MAX_CONTEXT_CHARS]


def _prompt(wrapper: Mapping[str, Any], *, context: str) -> str:
    custom_prompt = _MAPPING_LINE_PATTERN.sub(
        "", str(wrapper.get("custom_prompt") or "")
    )
    return (
        custom_prompt.replace("{defect_level}", str(wrapper.get("defect_level") or ""))
        .replace("{medical_text}", context)
        .strip()
    )


def _response_text(response: Mapping[str, Any]) -> str:
    choices = response.get("choices")
    if isinstance(choices, list) and choices and isinstance(choices[0], Mapping):
        message = choices[0].get("message")
        if isinstance(message, Mapping):
            return str(message.get("content") or "")
    return str(response.get("content") or response.get("text") or "")


def _parse_is_compliant(response: Mapping[str, Any]) -> bool | None:
    cleaned = re.sub(
        r"<think>[\s\S]*?</think>",
        "",
        _response_text(response),
        flags=re.IGNORECASE,
    ).strip()
    match = re.search(r"\{[\s\S]*\}", cleaned)
    if not match:
        return None
    try:
        payload = json.loads(match.group(0))
    except (TypeError, ValueError):
        return None
    value = payload.get("is_compliant") if isinstance(payload, Mapping) else None
    return value if isinstance(value, bool) else None


def _usage(response: Mapping[str, Any]) -> tuple[int, int, int, float]:
    usage = response.get("usage")
    usage = usage if isinstance(usage, Mapping) else {}
    prompt = int(usage.get("prompt_tokens") or 0)
    completion = int(usage.get("completion_tokens") or 0)
    total = int(usage.get("total_tokens") or prompt + completion)
    return prompt, completion, total, float(response.get("_api_time") or 0.0)


def _result(
    rule_id: str,
    status: str,
    reason_code: str,
    *,
    executor_type: str,
    prompt_tokens: int = 0,
    completion_tokens: int = 0,
    total_tokens: int = 0,
    api_time: float = 0.0,
) -> dict[str, Any]:
    item = build_luxian_0609_native_result(
        rule_id=rule_id,
        final_state=status,
        finding_kind="requirement_satisfied" if status == "compliant" else status,
        reason_code=reason_code,
    )
    findings, suggestion = _CONTROLLED_MESSAGES[status]
    item["findings"] = findings
    item["suggestion"] = suggestion
    metadata = dict(item.get("metadata") or {})
    metadata.update(
        {
            "executor_type": executor_type,
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": total_tokens,
            "api_time": api_time,
        }
    )
    item["metadata"] = metadata
    return item


def _terminal_result(
    rule_id: str,
    *,
    facts: Sequence[Any],
    documents: Mapping[str, Any],
) -> dict[str, Any] | None:
    if rule_id in _ANESTHESIA_RULE_IDS:
        anesthesia_state = _anesthesia_state(facts)
        anesthesia_rows = _substantive_rows(documents, ("anesthesia_record",))
        if anesthesia_state == "absent":
            # 文书沉默、拟请、空模板或仅麻醉方式都不能证明“未实施麻醉”。
            return _result(
                rule_id,
                "data_gap",
                "anesthesia_performed_fact_unavailable",
                executor_type="program",
            )
        if anesthesia_state == "unknown" or not anesthesia_rows:
            return _result(
                rule_id,
                "data_gap",
                "anesthesia_performed_fact_unavailable",
                executor_type="program",
            )
        if rule_id in (_ANESTHESIA_VISIT_RULE_IDS | _ANESTHESIA_RECORD_RULE_IDS):
            if anesthesia_state == "local":
                return _result(
                    rule_id,
                    "not_applicable",
                    "local_anesthesia_exception",
                    executor_type="program",
                )
            if anesthesia_state != "nonlocal":
                return _result(
                    rule_id,
                    "data_gap",
                    "anesthesia_method_unavailable",
                    executor_type="program",
                )
        if rule_id in _ANESTHESIA_CONSENT_RULE_IDS and not _consent_rows(documents):
            return _result(
                rule_id,
                "not_applicable" if rule_id == "LX0609-11-02-02" else "data_gap",
                (
                    "anesthesia_consent_absent"
                    if rule_id == "LX0609-11-02-02"
                    else "anesthesia_consent_source_unproven"
                ),
                executor_type="program",
            )
        if rule_id in _ANESTHESIA_VISIT_RULE_IDS and (
            not _substantive_rows(documents, _PREANE_SOURCES)
            or not _substantive_rows(documents, _POSTANE_SOURCES)
        ):
            return _result(
                rule_id,
                "non_compliant" if rule_id == "LX0609-04-04-02" else "data_gap",
                (
                    "anesthesia_visit_missing"
                    if rule_id == "LX0609-04-04-02"
                    else "anesthesia_visit_source_unproven"
                ),
                executor_type="program",
            )
        return None

    if not _has_performed_surgery(facts):
        return _result(
            rule_id,
            "data_gap",
            "performed_surgery_fact_unavailable",
            executor_type="program",
        )
    if _has_emergency_exception(facts):
        return _result(
            rule_id,
            "not_applicable",
            "emergency_rescue_exception",
            executor_type="program",
        )
    if not _substantive_rows(documents, ("presurg_discussion",)):
        return _result(
            rule_id,
            "data_gap",
            "preop_discussion_source_unproven",
            executor_type="program",
        )
    return None


def _context_groups(rule_id: str) -> tuple[tuple[str, ...], ...]:
    if rule_id in _ANESTHESIA_CONSENT_RULE_IDS:
        return (("anesthesia_record",), _CONSENT_SOURCES)
    if rule_id in _ANESTHESIA_VISIT_RULE_IDS:
        return (("anesthesia_record",), _PREANE_SOURCES, _POSTANE_SOURCES)
    if rule_id in _ANESTHESIA_RECORD_RULE_IDS:
        return (("anesthesia_record",),)
    return (("surgery_record",), ("presurg_discussion",))


async def execute_luxian_0609_native_surgery_document_rules(
    *,
    rule_ids: Sequence[str],
    wrapper_rules: Sequence[Mapping[str, Any]],
    evidence_payload: Mapping[str, Any] | None,
    llm_client: SurgeryDocumentLLMClient | None,
    evidence_materials: Luxian0609EvidenceMaterialStore | None = None,
    evidence_snapshot: Luxian0609EvidenceSnapshot | None = None,
    decision_rule_ids: Sequence[str] = (),
) -> NativeSurgeryDocumentExecutionResult:
    """按客户目录顺序执行；强事实不足时零模型并保守降级。"""

    requested = {str(rule_id or "").strip().upper() for rule_id in rule_ids}
    typed_requested = frozenset(
        str(rule_id or "").strip().upper() for rule_id in decision_rule_ids
    )
    # 029 没有 typed evidence session 时必须留给旧兼容链，避免同一规则重复执行。
    selected = tuple(
        rule_id
        for rule_id in SURGERY_DOCUMENT_RULE_IDS
        if rule_id in requested
        and (rule_id != "LX0609-04-01-01" or rule_id in typed_requested)
    )
    if (
        not typed_requested.issubset(_TYPED_DECISION_RULE_IDS)
        or not typed_requested.issubset(set(selected))
    ):
        raise ValueError("unsupported typed surgery document rule scope")
    if typed_requested and (
        type(evidence_snapshot) is not Luxian0609EvidenceSnapshot
        or type(evidence_materials) is not Luxian0609EvidenceMaterialStore
        or evidence_materials.snapshot_hash != evidence_snapshot.snapshot_hash
    ):
        raise ValueError("typed surgery document rules require one evidence session")
    if not selected:
        return NativeSurgeryDocumentExecutionResult((), ())

    legacy_selected = tuple(
        rule_id for rule_id in selected if rule_id not in typed_requested
    )
    documents = _documents(evidence_payload) if legacy_selected else None
    facts = _timeline_facts(evidence_payload) if legacy_selected else None

    wrappers_by_id = {
        str(wrapper.get("rule_id") or wrapper.get("rule_code") or "")
        .strip()
        .upper(): wrapper
        for wrapper in wrapper_rules
        if isinstance(wrapper, Mapping)
    }
    results: list[dict[str, Any]] = []
    decisions: list[RuleDecision] = []
    customer_display_facts: list[tuple[str, Mapping[str, Any]]] = []
    llm_call_count = prompt_tokens = completion_tokens = total_tokens = 0
    api_time = 0.0

    preop_content_rule_ids = tuple(
        rule_id
        for rule_id in selected
        if rule_id in {"LX0609-04-01-04", "LX0609-04-01-05"}
        and rule_id in typed_requested
    )
    preop_content_by_rule_id: dict[str, RuleDecision] = {}
    preop_content_facts_by_rule_id: dict[str, Mapping[str, Any]] = {}
    if preop_content_rule_ids:
        assert evidence_snapshot is not None and evidence_materials is not None
        preop_content = await evaluate_preop_content_rules(
            rule_ids=preop_content_rule_ids,
            snapshot=evidence_snapshot,
            materials=evidence_materials,
            llm_client=llm_client,
        )
        preop_content_by_rule_id = {
            decision.rule_id: decision for decision in preop_content.decisions
        }
        preop_content_facts_by_rule_id = dict(preop_content.customer_display_facts)
        llm_call_count += preop_content.llm_call_count
        prompt_tokens += preop_content.prompt_tokens
        completion_tokens += preop_content.completion_tokens
        total_tokens += preop_content.total_tokens
        api_time += preop_content.api_time

    for rule_id in selected:
        if rule_id in typed_requested:
            if rule_id in preop_content_by_rule_id:
                decisions.append(preop_content_by_rule_id[rule_id])
                safe_facts = preop_content_facts_by_rule_id.get(rule_id)
                if safe_facts is not None:
                    customer_display_facts.append((rule_id, safe_facts))
                continue
            assert evidence_snapshot is not None
            if rule_id == "LX0609-04-01-01":
                assert evidence_materials is not None
                (
                    outcome,
                    calls,
                    prompt,
                    completion,
                    total,
                    elapsed,
                ) = await _typed_029_outcome(
                    snapshot=evidence_snapshot,
                    materials=evidence_materials,
                )
                llm_call_count += calls
                prompt_tokens += prompt
                completion_tokens += completion
                total_tokens += total
                api_time += elapsed
                if outcome.customer_display_facts is not None:
                    customer_display_facts.append(
                        (rule_id, outcome.customer_display_facts)
                    )
            else:
                outcome = _typed_terminal_outcome(
                    rule_id=rule_id,
                    snapshot=evidence_snapshot,
                    materials=evidence_materials,
                )
                if rule_id == "LX0609-04-04-02":
                    assert evidence_materials is not None
                    outcome, calls, prompt, completion, total, elapsed = await _typed_037_controlled_outcome(
                        outcome=outcome, snapshot=evidence_snapshot, materials=evidence_materials, llm_client=llm_client,
                    )
                    llm_call_count += calls
                    prompt_tokens += prompt
                    completion_tokens += completion
                    total_tokens += total
                    api_time += elapsed
                if (
                    outcome.customer_display_facts is not None
                ):
                    customer_display_facts.append(
                        (rule_id, outcome.customer_display_facts)
                    )
            assert evidence_materials is not None
            outcome = replace(
                outcome,
                fact_refs=_typed_precise_terminal_refs(
                    outcome=outcome,
                    snapshot=evidence_snapshot,
                    materials=evidence_materials,
                ),
            )
            decisions.append(
                _typed_decision_from_outcome(
                    outcome=outcome,
                    snapshot=evidence_snapshot,
                )
            )
            continue
        if documents is None or facts is None:
            results.append(
                _result(
                    rule_id,
                    "data_gap",
                    "surgery_document_projection_unavailable",
                    executor_type="program",
                )
            )
            continue
        terminal = _terminal_result(rule_id, facts=facts, documents=documents)
        if terminal is not None:
            results.append(terminal)
            continue
        context = _context(documents, _context_groups(rule_id))
        wrapper = wrappers_by_id.get(rule_id)
        if wrapper is None or not _clean(wrapper.get("custom_prompt")) or not context:
            results.append(
                _result(
                    rule_id,
                    "data_gap",
                    "surgery_document_prompt_input_unavailable",
                    executor_type="program",
                )
            )
            continue
        if llm_client is None:
            results.append(
                _result(
                    rule_id,
                    "data_gap",
                    "surgery_document_llm_unavailable",
                    executor_type="program",
                )
            )
            continue

        llm_call_count += 1
        try:
            response = await llm_client.generate(_prompt(wrapper, context=context))
        except Exception:
            results.append(
                _result(
                    rule_id,
                    "data_gap",
                    "surgery_document_llm_failure",
                    executor_type="llm",
                )
            )
            continue
        prompt, completion, total, elapsed = _usage(response)
        prompt_tokens += prompt
        completion_tokens += completion
        total_tokens += total
        api_time += elapsed
        is_compliant = _parse_is_compliant(response)
        if is_compliant is None:
            results.append(
                _result(
                    rule_id,
                    "data_gap",
                    "surgery_document_llm_invalid_output",
                    executor_type="llm",
                    prompt_tokens=prompt,
                    completion_tokens=completion,
                    total_tokens=total,
                    api_time=elapsed,
                )
            )
            continue
        status = "compliant" if is_compliant else "non_compliant"
        results.append(
            _result(
                rule_id,
                status,
                "surgery_document_customer_prompt",
                executor_type="llm",
                prompt_tokens=prompt,
                completion_tokens=completion,
                total_tokens=total,
                api_time=elapsed,
            )
        )

    return NativeSurgeryDocumentExecutionResult(
        results=tuple(results),
        planned_rule_ids=selected,
        decisions=tuple(decisions),
        customer_display_facts=tuple(customer_display_facts),
        llm_call_count=llm_call_count,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        total_tokens=total_tokens,
        api_time=api_time,
    )
