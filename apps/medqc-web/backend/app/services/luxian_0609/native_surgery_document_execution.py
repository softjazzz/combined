"""LX0609 麻醉/术前文书族原生执行：强事实门控后逐规则裁剪判定。"""

from __future__ import annotations

from dataclasses import dataclass
import json
import re
from typing import Any, Mapping, Protocol, Sequence

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
from .fact_schema import Assertion, EventStatus
from .native_execution import build_luxian_0609_native_result
from .source_manifest import QueryStatus
from .source_registry import (
    resolve_luxian_0609_controlled_fact_source_keys,
    resolve_luxian_0609_decision_support_source_keys,
    resolve_luxian_0609_rule_sources,
)


SURGERY_DOCUMENT_RULE_IDS = (
    "LX0609-029",
    "LX0609-034",
    "LX0609-035",
    "LX0609-036",
    "LX0609-037",
    "LX0609-038",
    "LX0609-039",
)
EXECUTOR_KEY = "surgery_document"
_TYPED_DECISION_RULE_IDS = frozenset(SURGERY_DOCUMENT_RULE_IDS)
_TYPED_EVALUATOR_VERSION = "surgery-document-ruledecision-shadow-v1"
_TYPED_RULE_SOURCE_KEYS = {
    "LX0609-029": ("presurg_summary", "surgery_record", "mr_surgery"),
    "LX0609-034": ("anesthesia_record", "consent_form"),
    "LX0609-035": ("anesthesia_record", "consent_form"),
    "LX0609-036": (
        "anesthesia_record",
        "preane_surveil_record",
        "postane_surveil_record",
    ),
    "LX0609-037": (
        "anesthesia_record",
        "consent_form",
        "preane_surveil_record",
        "postane_surveil_record",
    ),
    # 客户目录把038写成consent_form，但临床适用条件仍必须先有受控麻醉事实。
    "LX0609-038": ("anesthesia_record", "consent_form"),
    "LX0609-039": (
        "surgery_record",
        "mr_surgery",
        "rescue_record",
        "presurg_discussion",
    ),
}

_ANESTHESIA_CONSENT_RULE_IDS = frozenset({"LX0609-034", "LX0609-035"})
_ANESTHESIA_VISIT_RULE_IDS = frozenset({"LX0609-036", "LX0609-037"})
_ANESTHESIA_RECORD_RULE_IDS = frozenset({"LX0609-038"})
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
    refs = tuple(
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
            "required_document_missing",
        )
    elif outcome.status == "not_applicable":
        dimensions = (
            ApplicabilityState.NOT_APPLICABLE,
            EvidenceState.SUFFICIENT,
            QcDirection.UNKNOWN,
            "performed_event_absent",
        )
    elif outcome.status == "data_gap":
        dimensions = (
            ApplicabilityState.UNKNOWN,
            EvidenceState.DATA_GAP,
            QcDirection.UNKNOWN,
            (
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
                "source_query_error"
                if outcome.reason_code == "source_query_error"
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


def _typed_terminal_outcome(
    *,
    rule_id: str,
    snapshot: Luxian0609EvidenceSnapshot,
) -> _SurgeryDocumentOutcome:
    """typed 迁移首版只做受控事实/来源四态判定，绝不回读旧 payload。"""

    if rule_id == "LX0609-039":
        performed_sources = ("surgery_record", "mr_surgery")
        binding_source_keys = _typed_binding_source_keys(rule_id)
        if not set(performed_sources).issubset(binding_source_keys):
            return _SurgeryDocumentOutcome(
                rule_id, "data_gap", "performed_surgery_source_unavailable", "program"
            )
        source_states: list[str] = []
        source_blockers: list[_SurgeryDocumentOutcome] = []
        for source_key in performed_sources:
            blocker = _typed_source_gate(
                rule_id=rule_id,
                source_key=source_key,
                snapshot=snapshot,
            )
            if blocker is not None:
                source_blockers.append(blocker)
            fact_state, _ = _typed_fact_state(
                snapshot,
                fact_types=_SURGERY_FACT_TYPES,
                source_key=source_key,
            )
            source_states.append(fact_state)

        # 任一批准来源的可信已实施事实足以进入后续急救/术前讨论判定；
        # 另一来源的缺口不能覆盖这个肯定事实。
        if "present" not in source_states:
            technical_blocker = next(
                (
                    item
                    for item in source_blockers
                    if item.status == "technical_error"
                ),
                None,
            )
            if technical_blocker is not None:
                return technical_blocker
            if source_blockers:
                return _SurgeryDocumentOutcome(
                    rule_id,
                    "data_gap",
                    "performed_surgery_source_unavailable",
                    "program",
                )
            if source_states == ["absent", "absent"]:
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
        emergency_state, _ = _typed_fact_state(
            snapshot,
            fact_types=_EMERGENCY_FACT_TYPES,
            source_key="rescue_record",
        )
        if emergency_state == "present":
            return _SurgeryDocumentOutcome(
                rule_id, "not_applicable", "emergency_rescue_exception", "program"
            )
        if emergency_state != "absent":
            return _SurgeryDocumentOutcome(
                rule_id, "data_gap", "emergency_exception_unresolved", "program"
            )
        blocker = _typed_source_gate(
            rule_id=rule_id,
            source_key="presurg_discussion",
            snapshot=snapshot,
        )
        if blocker is not None:
            return blocker
        if _typed_observation_state(snapshot, "presurg_discussion") == "empty":
            return _SurgeryDocumentOutcome(
                rule_id, "non_compliant", "preop_discussion_missing", "program"
            )
        # “术者是否参与”尚无受控身份关联，不能用姓名/正文关键词强判。
        return _SurgeryDocumentOutcome(
            rule_id, "data_gap", "surgeon_participation_unresolved", "program"
        )

    if "anesthesia_record" not in _typed_binding_source_keys(rule_id):
        return _SurgeryDocumentOutcome(
            rule_id, "data_gap", "performed_anesthesia_source_unavailable", "program"
        )
    blocker = _typed_source_gate(
        rule_id=rule_id,
        source_key="anesthesia_record",
        snapshot=snapshot,
    )
    if blocker is not None:
        return blocker
    anesthesia_state, anesthesia_method = _typed_fact_state(
        snapshot,
        fact_types=_ANESTHESIA_FACT_TYPES,
        source_key="anesthesia_record",
    )
    if anesthesia_state == "absent":
        return _SurgeryDocumentOutcome(
            rule_id, "not_applicable", "performed_anesthesia_absent", "program"
        )
    if anesthesia_state != "present":
        return _SurgeryDocumentOutcome(
            rule_id, "data_gap", "performed_anesthesia_fact_unavailable", "program"
        )
    is_local = anesthesia_method in _LOCAL_ANESTHESIA_VALUES
    if rule_id in {"LX0609-036", "LX0609-037", "LX0609-038"} and is_local:
        return _SurgeryDocumentOutcome(
            rule_id, "not_applicable", "local_anesthesia_exception", "program"
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
            return _SurgeryDocumentOutcome(
                rule_id, "non_compliant", "anesthesia_consent_missing", "program"
            )
        return _SurgeryDocumentOutcome(
            rule_id, "data_gap", "consent_semantics_unresolved", "program"
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
        if any(
            _typed_observation_state(snapshot, source_key) == "empty"
            for source_key in typed_visit_sources
        ):
            return _SurgeryDocumentOutcome(
                rule_id, "non_compliant", "anesthesia_visit_missing", "program"
            )
        if rule_id == "LX0609-036":
            return _SurgeryDocumentOutcome(
                rule_id, "compliant", "anesthesia_visits_present", "program"
            )
        return _SurgeryDocumentOutcome(
            rule_id, "data_gap", "anesthesia_visit_semantics_unresolved", "program"
        )

    # 038只判麻醉记录单存在；具体字段规范不在该客户质控点范围。
    if _typed_observation_state(snapshot, "anesthesia_record") == "available":
        return _SurgeryDocumentOutcome(
            rule_id, "compliant", "anesthesia_record_present", "program"
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


async def _typed_029_outcome(
    *,
    snapshot: Luxian0609EvidenceSnapshot,
    materials: Luxian0609EvidenceMaterialStore,
) -> tuple[_SurgeryDocumentOutcome, int, int, int, int, float]:
    """029：严格已实施手术事实触发后，只按术前小结正文存在性判定。"""

    # 029 的当前口径是纯存在性规则：严格手术 FactV2 触发后，只看术前
    # 小结正文是否为非空、非占位值。模型、标题、时间和长度均不得参与判定。
    source_states: list[str] = []
    blockers: list[_SurgeryDocumentOutcome] = []
    for source_key in ("surgery_record", "mr_surgery"):
        blocker = _typed_source_gate(
            rule_id="LX0609-029", source_key=source_key, snapshot=snapshot
        )
        if blocker is not None:
            blockers.append(blocker)
        state, _ = _typed_fact_state(
            snapshot,
            fact_types=_SURGERY_FACT_TYPES,
            source_key=source_key,
        )
        source_states.append(state)
    # 任一批准来源已经给出当前就诊已实施手术的 FactV2 时，不能让另一
    # 来源的不可用/异常覆盖这项肯定事实；后续只判术前小结正文。
    if "present" not in source_states:
        technical = next(
            (item for item in blockers if item.status == "technical_error"), None
        )
        if technical is not None:
            return technical, 0, 0, 0, 0, 0.0
        if blockers:
            return (
                _SurgeryDocumentOutcome(
                    "LX0609-029", "data_gap", "performed_surgery_source_unavailable", "program"
                ),
                0, 0, 0, 0, 0.0,
            )
        source_is_explicitly_absent = all(
            _typed_observation_state(snapshot, source_key) == "empty"
            for source_key in ("surgery_record", "mr_surgery")
        )
        if source_is_explicitly_absent:
            return (
                _SurgeryDocumentOutcome(
                    "LX0609-029", "not_applicable", "performed_surgery_absent", "program"
                ),
                0, 0, 0, 0, 0.0,
            )
        return (
            _SurgeryDocumentOutcome(
                "LX0609-029", "data_gap", "performed_surgery_fact_unavailable", "program"
            ),
            0, 0, 0, 0, 0.0,
        )
    target_gate = _typed_source_gate(
        rule_id="LX0609-029", source_key="presurg_summary", snapshot=snapshot
    )
    if target_gate is not None:
        return target_gate, 0, 0, 0, 0, 0.0
    if _typed_observation_state(snapshot, "presurg_summary") == "empty":
        return (
            _SurgeryDocumentOutcome(
                "LX0609-029", "non_compliant", "preop_summary_missing", "program"
            ),
            0, 0, 0, 0, 0.0,
        )
    try:
        summary_rows = materials.rows("presurg_summary")
    except EvidenceMaterialTruncated:
        return (
            _SurgeryDocumentOutcome(
                "LX0609-029", "data_gap", "preop_summary_source_truncated", "program"
            ),
            0, 0, 0, 0, 0.0,
        )
    except EvidenceMaterialUnavailable:
        return (
            _SurgeryDocumentOutcome(
                "LX0609-029", "data_gap", "preop_summary_source_unavailable", "program"
            ),
            0, 0, 0, 0, 0.0,
        )
    if any(_clean_presurg_body(row.get("record_content")) for row in summary_rows):
        return (
            _SurgeryDocumentOutcome(
                "LX0609-029", "compliant", "preop_summary_present", "program"
            ),
            0, 0, 0, 0, 0.0,
        )
    return (
        _SurgeryDocumentOutcome(
            "LX0609-029", "non_compliant", "preop_summary_blank", "program"
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
                "data_gap",
                "anesthesia_consent_source_unproven",
                executor_type="program",
            )
        if rule_id in _ANESTHESIA_VISIT_RULE_IDS and (
            not _substantive_rows(documents, _PREANE_SOURCES)
            or not _substantive_rows(documents, _POSTANE_SOURCES)
        ):
            return _result(
                rule_id,
                "data_gap",
                "anesthesia_visit_source_unproven",
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
        and (rule_id != "LX0609-029" or rule_id in typed_requested)
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
    llm_call_count = prompt_tokens = completion_tokens = total_tokens = 0
    api_time = 0.0

    for rule_id in selected:
        if rule_id in typed_requested:
            assert evidence_snapshot is not None
            if rule_id == "LX0609-029":
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
            else:
                outcome = _typed_terminal_outcome(
                    rule_id=rule_id,
                    snapshot=evidence_snapshot,
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
        llm_call_count=llm_call_count,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        total_tokens=total_tokens,
        api_time=api_time,
    )
