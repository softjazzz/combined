"""会诊族两阶段事实合同：模型只抽取事实，Python 合成 020-023。"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import re
from types import MappingProxyType
from typing import Any, Mapping, Sequence


RULE_IDS = ("LX0609-03-01-01", "LX0609-03-01-02", "LX0609-03-01-03", "LX0609-03-01-04")
SOURCES = frozenset(
    {
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
)
ROLES = frozenset(
    {
        "application",
        "opinion",
        "embedded_execution",
        "course_execution",
        "history",
        "planned",
        "template",
        "other",
        "unknown",
    }
)
APPLICATION_STATES = frozenset({"clear", "vague", "missing", "unknown"})
OPINION_STATES = frozenset({"clear", "vague", "missing", "unknown"})
QUALITIES = frozenset({"specific", "vague", "unknown"})
CONFIDENCES = frozenset({"high", "medium", "low"})
_TARGET_ROLES = frozenset({"application", "opinion", "embedded_execution"})
_EXECUTION_ROLES = frozenset({"embedded_execution", "course_execution"})
_NON_TARGET_ROLES = frozenset({"history", "planned", "template", "other"})
_FACT_KEYS = frozenset(
    {
        "ref",
        "source",
        "roles",
        "episode_ref",
        "application_state",
        "opinion_state",
        "confidence",
    }
)
_LINK_KEYS = frozenset({"episode_ref", "execution_ref", "quality", "confidence"})
_REF_RE = re.compile(
    r"^("
    r"consultation_record|daily_course_record|senior_course_record|"
    r"inpat_drug_order|inpat_nondrug_order|exam_master|exam_item_report|"
    r"labtest_master|labtest_item_report|surgery_record"
    r"):[0-9a-f]{64}$"
)


class FactContractError(ValueError):
    """模型事实输出不满足闭合合同。"""


@dataclass(frozen=True)
class ConsultationInputDocument:
    ref: str
    source: str
    record_time: str | datetime | None = None


@dataclass(frozen=True)
class ConsultationDocumentFact:
    ref: str
    source: str
    roles: frozenset[str]
    episode_ref: str | None
    application_state: str
    opinion_state: str
    confidence: str


@dataclass(frozen=True)
class ConsultationExecutionLink:
    episode_ref: str
    execution_ref: str
    quality: str
    confidence: str


@dataclass(frozen=True)
class ConsultationFactSet:
    documents: tuple[ConsultationInputDocument, ...]
    document_facts: tuple[ConsultationDocumentFact, ...]
    execution_links: tuple[ConsultationExecutionLink, ...]


@dataclass(frozen=True)
class ConsultationRuleState:
    status: str
    reason_code: str


@dataclass(frozen=True)
class ConsultationSemanticFact:
    ref: str
    roles: frozenset[str]
    application_state: str
    opinion_state: str
    confidence: str


@dataclass(frozen=True)
class ConsultationSemanticFactSet:
    facts: tuple[ConsultationSemanticFact, ...]


@dataclass(frozen=True)
class ConsultationExecutionEpisode:
    episode_ref: str
    opinion_refs: tuple[str, ...]
    confidence: str
    links: tuple[ConsultationExecutionLink, ...]


@dataclass(frozen=True)
class ConsultationExecutionFactSet:
    episodes: tuple[ConsultationExecutionEpisode, ...]
    unresolved_refs: frozenset[str]


@dataclass(frozen=True)
class ConsultationRuleFact:
    rule_id: str
    fact: str
    evidence_refs: tuple[str, ...]
    confidence: str


_HOSPITAL_TIMEZONE = timezone(timedelta(hours=8))


def _text(value: Any) -> str:
    return str(value or "").strip()


def _datetime(value: str | datetime | None) -> datetime | None:
    if isinstance(value, datetime):
        parsed = value
    else:
        candidate = _text(value)
        if not candidate:
            return None
        if candidate.endswith(("Z", "z")):
            candidate = f"{candidate[:-1]}+00:00"
        try:
            parsed = datetime.fromisoformat(candidate)
        except ValueError as exc:
            raise FactContractError("invalid record_time") from exc
    if parsed.utcoffset() is not None:
        return parsed.astimezone(_HOSPITAL_TIMEZONE).replace(tzinfo=None)
    return parsed


def _require_exact_keys(raw: Mapping[str, Any], expected: frozenset[str]) -> None:
    if frozenset(raw) != expected:
        raise FactContractError("unexpected fact contract fields")


def _parse_documents(
    documents: Sequence[ConsultationInputDocument],
) -> tuple[
    tuple[ConsultationInputDocument, ...], dict[str, ConsultationInputDocument]
]:
    accepted: list[ConsultationInputDocument] = []
    by_ref: dict[str, ConsultationInputDocument] = {}
    for raw in documents:
        if type(raw) is not ConsultationInputDocument:
            raise FactContractError("invalid input document")
        ref, source = _text(raw.ref), _text(raw.source)
        match = _REF_RE.fullmatch(ref)
        if source not in SOURCES or match is None or match.group(1) != source:
            raise FactContractError("invalid stable input ref")
        if ref in by_ref:
            raise FactContractError("duplicate input ref")
        document = ConsultationInputDocument(ref, source, raw.record_time)
        _datetime(document.record_time)
        accepted.append(document)
        by_ref[ref] = document
    return tuple(accepted), by_ref


def _parse_fact(
    raw: Any,
    documents_by_ref: Mapping[str, ConsultationInputDocument],
) -> ConsultationDocumentFact:
    if isinstance(raw, list) and len(raw) == 6:
        document = documents_by_ref.get(_text(raw[0]))
        raw = {
            "ref": raw[0],
            "source": document.source if document is not None else "",
            "roles": raw[1],
            "episode_ref": raw[2],
            "application_state": raw[3],
            "opinion_state": raw[4],
            "confidence": raw[5],
        }
    if not isinstance(raw, Mapping):
        raise FactContractError("document fact must be an object")
    _require_exact_keys(raw, _FACT_KEYS)
    ref, source = _text(raw.get("ref")), _text(raw.get("source"))
    document = documents_by_ref.get(ref)
    if document is None or source != document.source:
        raise FactContractError("unknown ref or source mismatch")
    raw_roles = raw.get("roles")
    if not isinstance(raw_roles, list) or not raw_roles:
        raise FactContractError("roles must be a non-empty array")
    roles = tuple(_text(item) for item in raw_roles)
    if len(set(roles)) != len(roles) or not set(roles).issubset(ROLES):
        raise FactContractError("invalid or duplicate role")
    role_set = frozenset(roles)
    if "unknown" in role_set and len(role_set) != 1:
        raise FactContractError("unknown role cannot be combined")
    if role_set & {"template", "other"} and len(role_set) != 1:
        raise FactContractError("template/other role cannot be combined")
    if source == "consultation_record":
        if "course_execution" in role_set:
            raise FactContractError("consultation source cannot be course execution")
    elif role_set & {"application", "opinion", "embedded_execution"}:
        # 病程中常会复述申请或意见。来源边界优先：它不能因此建立新的
        # consultation episode，只保留是否属于执行、计划或既往提及。
        if "course_execution" in role_set:
            role_set = frozenset({"course_execution"})
        elif "planned" in role_set:
            role_set = frozenset({"planned"})
        else:
            role_set = frozenset({"history"})

    raw_episode_ref = raw.get("episode_ref")
    episode_ref = None if raw_episode_ref is None else _text(raw_episode_ref)
    application_state = _text(raw.get("application_state"))
    opinion_state = _text(raw.get("opinion_state"))
    confidence = _text(raw.get("confidence"))
    if (
        application_state not in APPLICATION_STATES
        or opinion_state not in OPINION_STATES
    ):
        raise FactContractError("invalid semantic state")
    if confidence not in CONFIDENCES:
        raise FactContractError("invalid document confidence")
    if "application" not in role_set and application_state != "unknown":
        raise FactContractError("application_state requires application role")
    if "opinion" not in role_set and opinion_state != "unknown":
        raise FactContractError("opinion_state requires opinion role")
    if role_set & _TARGET_ROLES:
        anchor = documents_by_ref.get(episode_ref or "")
        if anchor is None or anchor.source != "consultation_record":
            raise FactContractError("target fact requires stable episode anchor")
    else:
        # 非目标角色携带episode_ref只是一项冗余模型输出；丢弃它不会制造
        # 正向事实，且可避免格式噪声让整病例失效。
        episode_ref = None
        application_state = "unknown"
        opinion_state = "unknown"
    return ConsultationDocumentFact(
        ref,
        source,
        role_set,
        episode_ref,
        application_state,
        opinion_state,
        confidence,
    )


def _parse_link(
    raw: Any,
    *,
    documents_by_ref: Mapping[str, ConsultationInputDocument],
    facts_by_ref: Mapping[str, ConsultationDocumentFact],
    episode_opinion_refs: Mapping[str, tuple[str, ...]],
) -> ConsultationExecutionLink:
    if isinstance(raw, list) and len(raw) == 4:
        raw = {
            "episode_ref": raw[0],
            "execution_ref": raw[1],
            "quality": raw[2],
            "confidence": raw[3],
        }
    if not isinstance(raw, Mapping):
        raise FactContractError("execution link must be an object")
    _require_exact_keys(raw, _LINK_KEYS)
    episode_ref = _text(raw.get("episode_ref"))
    execution_ref = _text(raw.get("execution_ref"))
    quality = _text(raw.get("quality"))
    confidence = _text(raw.get("confidence"))
    if episode_ref not in episode_opinion_refs:
        raise FactContractError("execution link requires an opinion episode")
    execution_document = documents_by_ref.get(execution_ref)
    execution_fact = facts_by_ref.get(execution_ref)
    if execution_document is None or execution_fact is None:
        raise FactContractError("execution link has unknown ref")
    if not (execution_fact.roles & _EXECUTION_ROLES):
        raise FactContractError("execution_ref is not an execution fact")
    if quality not in QUALITIES or confidence not in CONFIDENCES:
        raise FactContractError("invalid execution relation")
    if "embedded_execution" in execution_fact.roles:
        if (
            execution_document.source != "consultation_record"
            or execution_fact.episode_ref != episode_ref
        ):
            raise FactContractError("embedded execution must stay in its episode")
    elif execution_document.source not in SOURCES - {"consultation_record"}:
        raise FactContractError("course execution has invalid source")

    structural_same_document = (
        tuple(episode_opinion_refs[episode_ref]) == (execution_ref,)
        and "embedded_execution" in execution_fact.roles
    )
    opinion_times = [
        _datetime(documents_by_ref[ref].record_time)
        for ref in episode_opinion_refs[episode_ref]
    ]
    known_opinion_times = [item for item in opinion_times if item is not None]
    execution_time = _datetime(execution_document.record_time)
    if confidence == "high" and not structural_same_document and (
        len(known_opinion_times) != len(opinion_times) or execution_time is None
    ):
        raise FactContractError("high-confidence link requires timestamps")
    if known_opinion_times and execution_time is not None:
        latest_opinion_time = max(known_opinion_times)
        if execution_time < latest_opinion_time:
            raise FactContractError("execution does not follow the episode opinion")
    return ConsultationExecutionLink(episode_ref, execution_ref, quality, confidence)


def validate_consultation_fact_payload(
    payload: Mapping[str, Any],
    documents: Sequence[ConsultationInputDocument],
) -> ConsultationFactSet:
    parsed_documents, documents_by_ref = _parse_documents(documents)
    if isinstance(payload, Mapping) and frozenset(payload) == {
        "episodes",
        "non_target_refs",
        "unresolved_refs",
    }:
        payload = _expand_episode_payload(payload, documents_by_ref)
    if not isinstance(payload, Mapping) or frozenset(payload) != {
        "document_facts",
        "execution_links",
    }:
        raise FactContractError(
            "model may only return document facts and execution links"
        )
    raw_facts = payload.get("document_facts")
    raw_links = payload.get("execution_links")
    if not isinstance(raw_facts, list) or not isinstance(raw_links, list):
        raise FactContractError("fact collections must be arrays")
    facts = tuple(_parse_fact(raw, documents_by_ref) for raw in raw_facts)
    facts_by_ref: dict[str, ConsultationDocumentFact] = {}
    for fact in facts:
        if fact.ref in facts_by_ref:
            raise FactContractError("duplicate document fact ref")
        facts_by_ref[fact.ref] = fact
    unknown_refs = set(facts_by_ref) - set(documents_by_ref)
    if unknown_refs:
        raise FactContractError("document facts contain unknown refs")
    # 模型漏回一份输入时补成unknown，而不是丢弃整病例；unknown不会产生
    # 合规/不合规事实，并会在相关规则上保守落到evaluation_unknown。
    for ref, document in documents_by_ref.items():
        if ref in facts_by_ref:
            continue
        facts_by_ref[ref] = ConsultationDocumentFact(
            ref,
            document.source,
            frozenset({"unknown"}),
            None,
            "unknown",
            "unknown",
            "low",
        )
    facts = tuple(facts_by_ref[document.ref] for document in parsed_documents)

    episode_refs = frozenset(
        fact.episode_ref for fact in facts if fact.episode_ref is not None
    )
    for episode_ref in episode_refs:
        anchor_fact = facts_by_ref.get(episode_ref)
        if anchor_fact is None or anchor_fact.episode_ref != episode_ref:
            raise FactContractError("episode anchor must be a fact in the same episode")
    episode_opinion_refs = {
        episode_ref: tuple(
            fact.ref
            for fact in facts
            if fact.episode_ref == episode_ref and "opinion" in fact.roles
        )
        for episode_ref in episode_refs
    }
    episode_opinion_refs = {
        key: value for key, value in episode_opinion_refs.items() if value
    }
    links = tuple(
        _parse_link(
            raw,
            documents_by_ref=documents_by_ref,
            facts_by_ref=facts_by_ref,
            episode_opinion_refs=episode_opinion_refs,
        )
        for raw in raw_links
    )
    seen_links: set[tuple[str, str]] = set()
    for link in links:
        key = (link.episode_ref, link.execution_ref)
        if key in seen_links:
            raise FactContractError("duplicate execution link")
        seen_links.add(key)
    return ConsultationFactSet(parsed_documents, facts, links)


def _expand_episode_payload(
    payload: Mapping[str, Any],
    documents_by_ref: Mapping[str, ConsultationInputDocument],
) -> Mapping[str, Any]:
    """将模型的紧凑episode合同展开为内部逐文书事实合同。"""

    raw_episodes = payload.get("episodes")
    raw_non_target = payload.get("non_target_refs")
    raw_unresolved = payload.get("unresolved_refs")
    if not all(isinstance(item, list) for item in (raw_episodes, raw_non_target, raw_unresolved)):
        raise FactContractError("episode fact collections must be arrays")

    universe = set(documents_by_ref)
    non_target = {_text(ref) for ref in raw_non_target}
    unresolved = {_text(ref) for ref in raw_unresolved}
    if (
        len(non_target) != len(raw_non_target)
        or len(unresolved) != len(raw_unresolved)
        or not non_target.issubset(universe)
        or not unresolved.issubset(universe)
        or non_target & unresolved
    ):
        raise FactContractError("invalid non-target or unresolved refs")

    roles_by_ref: dict[str, set[str]] = {ref: set() for ref in universe}
    episode_by_ref: dict[str, str] = {}
    application_by_ref: dict[str, str] = {}
    opinion_by_ref: dict[str, str] = {}
    confidence_by_ref: dict[str, str] = {}
    links: list[dict[str, str]] = []

    for raw in raw_episodes:
        if not isinstance(raw, list) or len(raw) != 7:
            raise FactContractError("episode item must contain seven values")
        (
            raw_episode_ref,
            raw_application_refs,
            raw_opinion_refs,
            application_state,
            opinion_state,
            confidence,
            raw_links,
        ) = raw
        episode_ref = _text(raw_episode_ref)
        if (
            not isinstance(raw_application_refs, list)
            or not isinstance(raw_opinion_refs, list)
            or not isinstance(raw_links, list)
            or application_state not in APPLICATION_STATES
            or opinion_state not in OPINION_STATES
            or confidence not in CONFIDENCES
        ):
            raise FactContractError("invalid episode values")
        application_refs = tuple(_text(ref) for ref in raw_application_refs)
        opinion_refs = tuple(_text(ref) for ref in raw_opinion_refs)
        consultation_refs = set(application_refs) | set(opinion_refs)
        if (
            episode_ref not in consultation_refs
            or not consultation_refs
            or not consultation_refs.issubset(universe)
            or any(documents_by_ref[ref].source != "consultation_record" for ref in consultation_refs)
        ):
            raise FactContractError("episode has invalid consultation refs")
        for ref in consultation_refs:
            prior = episode_by_ref.setdefault(ref, episode_ref)
            if prior != episode_ref:
                raise FactContractError("consultation ref belongs to multiple episodes")
            confidence_by_ref[ref] = confidence
        for ref in application_refs:
            roles_by_ref[ref].add("application")
            application_by_ref[ref] = application_state
        for ref in opinion_refs:
            roles_by_ref[ref].add("opinion")
            opinion_by_ref[ref] = opinion_state
        for raw_link in raw_links:
            if not isinstance(raw_link, list) or len(raw_link) != 3:
                raise FactContractError("episode execution link must contain three values")
            execution_ref, quality, link_confidence = map(_text, raw_link)
            document = documents_by_ref.get(execution_ref)
            if (
                document is None
                or quality not in QUALITIES
                or link_confidence not in CONFIDENCES
            ):
                raise FactContractError("invalid episode execution link")
            roles_by_ref[execution_ref].add(
                "embedded_execution"
                if document.source == "consultation_record"
                else "course_execution"
            )
            if document.source == "consultation_record":
                prior = episode_by_ref.setdefault(execution_ref, episode_ref)
                if prior != episode_ref:
                    raise FactContractError("embedded execution crossed episodes")
            confidence_by_ref.setdefault(execution_ref, link_confidence)
            links.append(
                {
                    "episode_ref": episode_ref,
                    "execution_ref": execution_ref,
                    "quality": quality,
                    "confidence": link_confidence,
                }
            )

    used = {ref for ref, roles in roles_by_ref.items() if roles}
    if (used & non_target) or (used & unresolved):
        raise FactContractError("classified ref also marked non-target or unresolved")
    facts: list[dict[str, Any]] = []
    for ref, document in documents_by_ref.items():
        roles = roles_by_ref[ref]
        if not roles:
            roles = {"history"} if ref in non_target else {"unknown"}
        facts.append(
            {
                "ref": ref,
                "source": document.source,
                "roles": sorted(roles),
                "episode_ref": episode_by_ref.get(ref),
                "application_state": application_by_ref.get(ref, "unknown"),
                "opinion_state": opinion_by_ref.get(ref, "unknown"),
                "confidence": confidence_by_ref.get(
                    ref,
                    "high" if ref in non_target else "low",
                ),
            }
        )
    return {"document_facts": facts, "execution_links": links}


def _state(status: str, reason_code: str) -> ConsultationRuleState:
    return ConsultationRuleState(status, reason_code)


def validate_consultation_semantic_payload(
    payload: Mapping[str, Any],
    documents: Sequence[ConsultationInputDocument],
) -> ConsultationSemanticFactSet:
    parsed_documents, documents_by_ref = _parse_documents(documents)
    if any(item.source != "consultation_record" for item in parsed_documents):
        raise FactContractError("semantic payload only accepts consultation records")
    if not isinstance(payload, Mapping) or frozenset(payload) != {"documents"}:
        raise FactContractError("invalid consultation semantic payload")
    raw_facts = payload.get("documents")
    if not isinstance(raw_facts, list):
        raise FactContractError("semantic documents must be an array")
    by_ref: dict[str, ConsultationSemanticFact] = {}
    allowed_roles = {
        "application",
        "opinion",
        "history",
        "planned",
        "template",
        "other",
        "unknown",
    }
    for raw in raw_facts:
        if not isinstance(raw, list) or len(raw) != 5:
            raise FactContractError("semantic document must contain five values")
        ref = _text(raw[0])
        raw_roles = raw[1]
        application_state = _text(raw[2])
        opinion_state = _text(raw[3])
        confidence = _text(raw[4])
        if ref not in documents_by_ref or ref in by_ref:
            raise FactContractError("semantic document has unknown or duplicate ref")
        if not isinstance(raw_roles, list) or not raw_roles:
            raise FactContractError("semantic roles must be non-empty")
        roles = tuple(_text(role) for role in raw_roles)
        role_set = frozenset(roles)
        if len(role_set) != len(roles) or not role_set.issubset(allowed_roles):
            raise FactContractError("invalid semantic roles")
        if "unknown" in role_set and len(role_set) != 1:
            raise FactContractError("unknown semantic role cannot be combined")
        if role_set & {"template", "other"} and len(role_set) != 1:
            raise FactContractError("template/other semantic role cannot be combined")
        if (
            application_state not in APPLICATION_STATES
            or opinion_state not in OPINION_STATES
            or confidence not in CONFIDENCES
        ):
            raise FactContractError("invalid semantic state")
        if "application" not in role_set:
            application_state = "unknown"
        if "opinion" not in role_set:
            opinion_state = "unknown"
        by_ref[ref] = ConsultationSemanticFact(
            ref,
            role_set,
            application_state,
            opinion_state,
            confidence,
        )
    for document in parsed_documents:
        by_ref.setdefault(
            document.ref,
            ConsultationSemanticFact(
                document.ref,
                frozenset({"unknown"}),
                "unknown",
                "unknown",
                "low",
            ),
        )
    return ConsultationSemanticFactSet(
        tuple(by_ref[document.ref] for document in parsed_documents)
    )


def synthesize_consultation_semantic_states(
    facts: ConsultationSemanticFactSet,
    *,
    consultation_source_complete: bool,
) -> Mapping[str, ConsultationRuleState]:
    if type(facts) is not ConsultationSemanticFactSet:
        raise TypeError("validated ConsultationSemanticFactSet required")
    def resolve(kind: str) -> ConsultationRuleState:
        role = "application" if kind == "purpose" else "opinion"
        target = tuple(fact for fact in facts.facts if role in fact.roles)
        other_target = tuple(
            fact
            for fact in facts.facts
            if ("opinion" if role == "application" else "application") in fact.roles
        )
        uncertain = any(
            "unknown" in fact.roles
            or (
                fact.confidence != "high"
                and not fact.roles.issubset(
                    {"history", "planned", "template", "other"}
                )
            )
            for fact in facts.facts
        )
        if target:
            values = [
                fact.application_state if role == "application" else fact.opinion_state
                for fact in target
            ]
            if not consultation_source_complete:
                return _state("data_gap", f"{role}_unresolved")
            if "missing" in values:
                return _state("non_compliant", f"{kind}_missing")
            if "vague" in values:
                return _state("non_compliant", f"{kind}_vague")
            if uncertain or "unknown" in values:
                return _state("evaluation_unknown", "semantic_low_confidence")
            return _state("compliant", f"{kind}_clear")
        if other_target or uncertain:
            return _state(
                "evaluation_unknown" if consultation_source_complete else "data_gap",
                "semantic_low_confidence" if consultation_source_complete else f"{role}_unresolved",
            )
        return _state(
            "not_applicable" if consultation_source_complete else "data_gap",
            "consultation_absent" if consultation_source_complete else f"{role}_unresolved",
        )

    return MappingProxyType(
        {
            "LX0609-03-01-02": resolve("purpose"),
            "LX0609-03-01-03": resolve("opinion"),
        }
    )


def validate_consultation_execution_payload(
    payload: Mapping[str, Any],
    documents: Sequence[ConsultationInputDocument],
) -> ConsultationExecutionFactSet:
    parsed_documents, documents_by_ref = _parse_documents(documents)
    if not isinstance(payload, Mapping) or frozenset(payload) != {
        "episodes",
        "non_target_refs",
        "unresolved_refs",
    }:
        raise FactContractError("invalid consultation execution payload")
    raw_episodes = payload.get("episodes")
    raw_non_target = payload.get("non_target_refs")
    raw_unresolved = payload.get("unresolved_refs")
    if not all(isinstance(item, list) for item in (raw_episodes, raw_non_target, raw_unresolved)):
        raise FactContractError("execution fact collections must be arrays")
    universe = set(documents_by_ref)
    non_target = {_text(ref) for ref in raw_non_target}
    unresolved = {_text(ref) for ref in raw_unresolved}
    if (
        len(non_target) != len(raw_non_target)
        or len(unresolved) != len(raw_unresolved)
        or not non_target.issubset(universe)
        or not unresolved.issubset(universe)
        or non_target & unresolved
    ):
        raise FactContractError("invalid execution ref partition")
    used_consultation_refs: set[str] = set()
    linked_refs: set[str] = set()
    episodes: list[ConsultationExecutionEpisode] = []
    for raw in raw_episodes:
        if not isinstance(raw, list) or len(raw) != 4:
            raise FactContractError("execution episode must contain four values")
        episode_ref = _text(raw[0])
        raw_opinion_refs = raw[1]
        confidence = _text(raw[2])
        raw_links = raw[3]
        if (
            not isinstance(raw_opinion_refs, list)
            or not isinstance(raw_links, list)
            or confidence not in CONFIDENCES
        ):
            raise FactContractError("invalid execution episode values")
        opinion_refs = tuple(_text(ref) for ref in raw_opinion_refs)
        if (
            not opinion_refs
            or episode_ref not in opinion_refs
            or any(
                ref not in documents_by_ref
                or documents_by_ref[ref].source != "consultation_record"
                for ref in opinion_refs
            )
        ):
            raise FactContractError("invalid opinion episode refs")
        if used_consultation_refs.intersection(opinion_refs):
            raise FactContractError("opinion ref belongs to multiple episodes")
        used_consultation_refs.update(opinion_refs)
        links: list[ConsultationExecutionLink] = []
        opinion_times = [_datetime(documents_by_ref[ref].record_time) for ref in opinion_refs]
        known_opinion_times = [item for item in opinion_times if item is not None]
        latest_opinion_time = max(known_opinion_times) if known_opinion_times else None
        for raw_link in raw_links:
            if not isinstance(raw_link, list) or len(raw_link) != 3:
                raise FactContractError("execution link must contain three values")
            execution_ref, quality, link_confidence = map(_text, raw_link)
            execution_document = documents_by_ref.get(execution_ref)
            if (
                execution_document is None
                or quality not in QUALITIES
                or link_confidence not in CONFIDENCES
            ):
                raise FactContractError("invalid execution link values")
            execution_time = _datetime(execution_document.record_time)
            structural_same_document = (
                execution_ref in opinion_refs
                and execution_document.source == "consultation_record"
            )
            if link_confidence == "high" and not structural_same_document and (
                latest_opinion_time is None or execution_time is None
            ):
                link_confidence = "medium"
            if latest_opinion_time is not None and execution_time is not None and execution_time < latest_opinion_time:
                raise FactContractError("execution precedes episode opinion")
            links.append(
                ConsultationExecutionLink(
                    episode_ref,
                    execution_ref,
                    quality,
                    link_confidence,
                )
            )
            linked_refs.add(execution_ref)
        episodes.append(
            ConsultationExecutionEpisode(
                episode_ref,
                opinion_refs,
                confidence,
                tuple(links),
            )
        )
    used = used_consultation_refs | linked_refs
    if used & non_target or used & unresolved:
        raise FactContractError("execution ref classified twice")
    missing = universe - used - non_target - unresolved
    unresolved.update(missing)
    return ConsultationExecutionFactSet(tuple(episodes), frozenset(unresolved))


def synthesize_consultation_execution_states(
    facts: ConsultationExecutionFactSet,
    *,
    consultation_source_complete: bool,
    course_source_complete: bool,
) -> Mapping[str, ConsultationRuleState]:
    if type(facts) is not ConsultationExecutionFactSet:
        raise TypeError("validated ConsultationExecutionFactSet required")
    episodes = facts.episodes
    if not episodes:
        state = _state(
            (
                "evaluation_unknown"
                if facts.unresolved_refs
                else (
                    "not_applicable"
                    if consultation_source_complete
                    else "data_gap"
                )
            ),
            (
                "semantic_low_confidence"
                if facts.unresolved_refs
                else (
                    "consultation_absent"
                    if consultation_source_complete
                    else "execution_source_incomplete"
                )
            ),
        )
        return MappingProxyType({"LX0609-03-01-01": state, "LX0609-03-01-04": state})

    all_links = tuple(link for episode in episodes for link in episode.links)
    covered = {
        episode.episode_ref
        for episode in episodes
        if any(
            link.confidence == "high" and link.quality in {"specific", "vague"}
            for link in episode.links
        )
    }
    uncertain = (
        bool(facts.unresolved_refs)
        or any(episode.confidence != "high" for episode in episodes)
        or any(
            link.confidence != "high" or link.quality == "unknown"
            for link in all_links
        )
    )
    if len(covered) == len(episodes) and consultation_source_complete:
        result_020 = _state("compliant", "execution_specific")
    elif uncertain:
        result_020 = _state("evaluation_unknown", "semantic_low_confidence")
    elif consultation_source_complete and course_source_complete:
        result_020 = _state("non_compliant", "execution_missing")
    else:
        result_020 = _state("data_gap", "execution_source_incomplete")

    if any(link.quality == "vague" for link in all_links):
        result_023 = _state("non_compliant", "execution_vague_or_copied")
    elif uncertain:
        result_023 = _state("evaluation_unknown", "semantic_low_confidence")
    elif all_links:
        result_023 = _state(
            "compliant"
            if consultation_source_complete and course_source_complete
            else "data_gap",
            "execution_specific_summarized"
            if consultation_source_complete and course_source_complete
            else "execution_source_incomplete",
        )
    else:
        result_023 = _state(
            "not_applicable"
            if consultation_source_complete and course_source_complete
            else "data_gap",
            "execution_record_missing"
            if consultation_source_complete and course_source_complete
            else "execution_source_incomplete",
        )
    return MappingProxyType(
        {"LX0609-03-01-01": result_020, "LX0609-03-01-04": result_023}
    )


_SIMPLE_FACT_STATES = {
    "LX0609-03-01-01": frozenset(
        {"execution_all_present", "execution_missing", "no_completed_opinion", "unknown"}
    ),
    "LX0609-03-01-02": frozenset(
        {"purpose_clear", "purpose_vague", "purpose_missing", "no_application", "unknown"}
    ),
    "LX0609-03-01-03": frozenset(
        {"opinion_clear", "opinion_vague", "opinion_missing", "no_completed_opinion", "unknown"}
    ),
    "LX0609-03-01-04": frozenset({"execution_specific", "execution_vague", "execution_absent", "unknown"}),
}
_SIMPLE_FACT_REF_SOURCES = {
    "LX0609-03-01-01": SOURCES,
    "LX0609-03-01-02": frozenset({"consultation_record"}),
    "LX0609-03-01-03": frozenset({"consultation_record"}),
    "LX0609-03-01-04": SOURCES,
}


def validate_consultation_rule_fact_payload(
    payload: Mapping[str, Any],
    documents: Sequence[ConsultationInputDocument],
    *,
    selected_rule_ids: Sequence[str],
) -> Mapping[str, ConsultationRuleFact]:
    parsed_documents, documents_by_ref = _parse_documents(documents)
    del parsed_documents
    selected = tuple(str(rule_id or "").strip().upper() for rule_id in selected_rule_ids)
    if (
        not selected
        or len(set(selected)) != len(selected)
        or not set(selected).issubset(RULE_IDS)
    ):
        raise FactContractError("invalid consultation rule fact scope")
    if not isinstance(payload, Mapping) or frozenset(payload) != {"facts"}:
        raise FactContractError("invalid consultation rule fact payload")
    raw_facts = payload.get("facts")
    if not isinstance(raw_facts, Mapping) or set(raw_facts) != set(selected):
        raise FactContractError("consultation rule facts must match selected scope")
    accepted: dict[str, ConsultationRuleFact] = {}
    for rule_id in selected:
        raw = raw_facts.get(rule_id)
        if not isinstance(raw, Mapping) or frozenset(raw) != {
            "fact",
            "evidence_refs",
            "confidence",
        }:
            raise FactContractError("invalid consultation rule fact fields")
        fact = _text(raw.get("fact"))
        confidence = _text(raw.get("confidence"))
        raw_refs = raw.get("evidence_refs")
        if (
            fact not in _SIMPLE_FACT_STATES[rule_id]
            or confidence not in CONFIDENCES
            or not isinstance(raw_refs, list)
        ):
            raise FactContractError("invalid consultation rule fact value")
        evidence_refs = tuple(_text(ref) for ref in raw_refs)
        if (
            len(set(evidence_refs)) != len(evidence_refs)
            or any(ref not in documents_by_ref for ref in evidence_refs)
        ):
            raise FactContractError("consultation rule fact has invalid evidence refs")
        if fact != "unknown" and not evidence_refs:
            raise FactContractError("determinate consultation fact requires evidence refs")
        if any(
            documents_by_ref[ref].source not in _SIMPLE_FACT_REF_SOURCES[rule_id]
            for ref in evidence_refs
        ):
            raise FactContractError("consultation rule fact ref has invalid source")
        accepted[rule_id] = ConsultationRuleFact(
            rule_id,
            fact,
            evidence_refs,
            confidence,
        )
    return MappingProxyType(accepted)


def synthesize_consultation_rule_fact_states(
    facts: Mapping[str, ConsultationRuleFact],
    *,
    consultation_source_complete: bool,
    course_source_complete: bool,
) -> Mapping[str, ConsultationRuleState]:
    outcomes: dict[str, ConsultationRuleState] = {}
    for rule_id, item in facts.items():
        if item.confidence != "high" or item.fact == "unknown":
            outcomes[rule_id] = _state(
                "evaluation_unknown", "semantic_low_confidence"
            )
            continue
        if rule_id == "LX0609-03-01-01":
            if item.fact == "no_completed_opinion":
                outcomes[rule_id] = _state(
                    "not_applicable" if consultation_source_complete else "data_gap",
                    "no_completed_opinion"
                    if consultation_source_complete
                    else "opinion_unresolved",
                )
            elif item.fact == "execution_missing":
                outcomes[rule_id] = _state(
                    "non_compliant"
                    if consultation_source_complete and course_source_complete
                    else "evaluation_unknown",
                    "execution_missing"
                    if consultation_source_complete and course_source_complete
                    else "semantic_low_confidence",
                )
            else:
                outcomes[rule_id] = _state(
                    "compliant" if consultation_source_complete else "data_gap",
                    "all_completed_opinions_have_execution"
                    if consultation_source_complete
                    else "execution_source_incomplete",
                )
        elif rule_id == "LX0609-03-01-02":
            if item.fact == "no_application":
                outcomes[rule_id] = _state(
                    "not_applicable" if consultation_source_complete else "data_gap",
                    "no_application"
                    if consultation_source_complete
                    else "application_unresolved",
                )
            elif item.fact == "purpose_clear":
                outcomes[rule_id] = _state(
                    "compliant" if consultation_source_complete else "data_gap",
                    "purpose_clear" if consultation_source_complete else "application_unresolved",
                )
            else:
                outcomes[rule_id] = _state(
                    "non_compliant" if consultation_source_complete else "data_gap",
                    item.fact
                    if consultation_source_complete
                    else "application_unresolved",
                )
        elif rule_id == "LX0609-03-01-03":
            if item.fact == "no_completed_opinion":
                outcomes[rule_id] = _state(
                    "not_applicable" if consultation_source_complete else "data_gap",
                    "no_completed_opinion"
                    if consultation_source_complete
                    else "opinion_unresolved",
                )
            elif item.fact == "opinion_clear":
                outcomes[rule_id] = _state(
                    "compliant" if consultation_source_complete else "data_gap",
                    "opinion_clear" if consultation_source_complete else "opinion_unresolved",
                )
            else:
                outcomes[rule_id] = _state(
                    "non_compliant" if consultation_source_complete else "data_gap",
                    item.fact if consultation_source_complete else "opinion_unresolved",
                )
        else:
            if item.fact == "execution_vague":
                outcomes[rule_id] = _state(
                    "non_compliant", "execution_vague_or_copied"
                )
            elif item.fact == "execution_absent":
                outcomes[rule_id] = _state(
                    "not_applicable"
                    if consultation_source_complete and course_source_complete
                    else "evaluation_unknown",
                    "execution_record_missing"
                    if consultation_source_complete and course_source_complete
                    else "semantic_low_confidence",
                )
            else:
                outcomes[rule_id] = _state(
                    "compliant"
                    if consultation_source_complete and course_source_complete
                    else "data_gap",
                    "execution_specific_summarized"
                    if consultation_source_complete and course_source_complete
                    else "execution_source_incomplete",
                )
    return MappingProxyType(outcomes)


def _semantic_summary(
    facts: Sequence[ConsultationDocumentFact], *, kind: str
) -> tuple[str, bool]:
    values = [getattr(fact, f"{kind}_state") for fact in facts]
    if "missing" in values:
        return "missing", True
    if "vague" in values:
        return "vague", True
    uncertain = any(fact.confidence != "high" for fact in facts) or "unknown" in values
    if uncertain:
        return "unknown", False
    return "clear", False


def synthesize_consultation_rule_states(
    facts: ConsultationFactSet,
    *,
    consultation_source_complete: bool,
    course_source_complete: bool,
) -> Mapping[str, ConsultationRuleState]:
    if type(facts) is not ConsultationFactSet:
        raise TypeError("validated ConsultationFactSet required")
    document_facts = facts.document_facts
    application_facts = tuple(
        fact for fact in document_facts if "application" in fact.roles
    )
    opinion_facts = tuple(
        fact for fact in document_facts if "opinion" in fact.roles
    )
    uncertain_consultation = any(
        fact.source == "consultation_record"
        and ("unknown" in fact.roles or fact.confidence != "high")
        for fact in document_facts
    )
    outcomes: dict[str, ConsultationRuleState] = {}

    if application_facts:
        value, known_defect = _semantic_summary(
            application_facts, kind="application"
        )
        if known_defect:
            outcomes["LX0609-03-01-02"] = _state(
                "non_compliant", f"purpose_{value}"
            )
        elif not consultation_source_complete:
            outcomes["LX0609-03-01-02"] = _state(
                "data_gap", "application_unresolved"
            )
        elif value == "unknown" or uncertain_consultation:
            outcomes["LX0609-03-01-02"] = _state(
                "evaluation_unknown", "semantic_low_confidence"
            )
        else:
            outcomes["LX0609-03-01-02"] = _state("compliant", "purpose_clear")
    elif opinion_facts:
        outcomes["LX0609-03-01-02"] = _state(
            "evaluation_unknown" if consultation_source_complete else "data_gap",
            (
                "semantic_low_confidence"
                if consultation_source_complete
                else "application_unresolved"
            ),
        )
    else:
        outcomes["LX0609-03-01-02"] = _state(
            (
                "evaluation_unknown"
                if uncertain_consultation
                else (
                    "not_applicable"
                    if consultation_source_complete
                    else "data_gap"
                )
            ),
            (
                "semantic_low_confidence"
                if uncertain_consultation
                else (
                    "consultation_absent"
                    if consultation_source_complete
                    else "application_unresolved"
                )
            ),
        )

    if opinion_facts:
        value, known_defect = _semantic_summary(opinion_facts, kind="opinion")
        if known_defect:
            outcomes["LX0609-03-01-03"] = _state(
                "non_compliant", f"opinion_{value}"
            )
        elif not consultation_source_complete:
            outcomes["LX0609-03-01-03"] = _state("data_gap", "opinion_unresolved")
        elif value == "unknown" or uncertain_consultation:
            outcomes["LX0609-03-01-03"] = _state(
                "evaluation_unknown", "semantic_low_confidence"
            )
        else:
            outcomes["LX0609-03-01-03"] = _state("compliant", "opinion_clear")
    else:
        outcomes["LX0609-03-01-03"] = _state(
            (
                "evaluation_unknown"
                if uncertain_consultation
                else (
                    "not_applicable"
                    if consultation_source_complete
                    else "data_gap"
                )
            ),
            (
                "semantic_low_confidence"
                if uncertain_consultation
                else (
                    "consultation_absent"
                    if consultation_source_complete
                    else "opinion_unresolved"
                )
            ),
        )

    opinion_episodes = frozenset(
        fact.episode_ref for fact in opinion_facts if fact.episode_ref is not None
    )
    relevant_links = tuple(
        link
        for link in facts.execution_links
        if link.episode_ref in opinion_episodes
    )
    uncertain_opinion = any(fact.confidence != "high" for fact in opinion_facts)
    uncertain_execution_material = uncertain_consultation or any(
        fact.source in {"daily_course_record", "senior_course_record"}
        and ("unknown" in fact.roles or fact.confidence != "high")
        for fact in document_facts
    )
    uncertain_links = tuple(
        link
        for link in relevant_links
        if link.confidence != "high" or link.quality == "unknown"
    )
    # 同一执行材料被模型同时归属于多个会诊时，不能把它复制计入每个
    # episode；这种跨会诊归属本身是不确定事实。保留链接供 023 的
    # “明确空泛”判定使用，但对具体执行应降级为 evaluation_unknown。
    execution_owners: dict[str, set[str]] = {}
    for link in relevant_links:
        execution_owners.setdefault(link.execution_ref, set()).add(link.episode_ref)
    ambiguous_execution_refs = {
        execution_ref
        for execution_ref, owners in execution_owners.items()
        if len(owners) > 1
    }
    if ambiguous_execution_refs:
        uncertain_links = tuple(
            link
            for link in relevant_links
            if link.execution_ref in ambiguous_execution_refs
            or link.confidence != "high"
            or link.quality == "unknown"
        )
    covered_episodes = frozenset(
        link.episode_ref
        for link in relevant_links
        if link.execution_ref not in ambiguous_execution_refs
        and link.confidence == "high"
        and link.quality in {"specific", "vague"}
    )
    if not opinion_episodes:
        outcomes["LX0609-03-01-01"] = _state(
            (
                "evaluation_unknown"
                if uncertain_consultation
                else (
                    "not_applicable"
                    if consultation_source_complete
                    else "data_gap"
                )
            ),
            (
                "semantic_low_confidence"
                if uncertain_consultation
                else (
                    "consultation_absent"
                    if consultation_source_complete
                    else "execution_source_incomplete"
                )
            ),
        )
    elif uncertain_consultation or uncertain_opinion:
        outcomes["LX0609-03-01-01"] = _state(
            "evaluation_unknown", "semantic_low_confidence"
        )
    elif opinion_episodes <= covered_episodes:
        outcomes["LX0609-03-01-01"] = _state(
            "compliant" if consultation_source_complete else "data_gap",
            (
                "execution_specific"
                if consultation_source_complete
                else "execution_source_incomplete"
            ),
        )
    elif uncertain_execution_material or uncertain_links:
        outcomes["LX0609-03-01-01"] = _state(
            "evaluation_unknown", "semantic_low_confidence"
        )
    elif consultation_source_complete and course_source_complete:
        outcomes["LX0609-03-01-01"] = _state("non_compliant", "execution_missing")
    else:
        outcomes["LX0609-03-01-01"] = _state(
            "evaluation_unknown", "semantic_low_confidence"
        )

    # 关联置信度回答“属于哪次会诊”，quality 回答“这条执行记录是否空泛”。
    # 即使归属仍有歧义，已经明确空泛的执行记录仍可形成 023 缺陷。
    known_vague = any(link.quality == "vague" for link in relevant_links)
    if known_vague:
        outcomes["LX0609-03-01-04"] = _state(
            "non_compliant", "execution_vague_or_copied"
        )
    elif uncertain_execution_material or uncertain_links or uncertain_opinion:
        outcomes["LX0609-03-01-04"] = _state(
            "evaluation_unknown", "semantic_low_confidence"
        )
    elif relevant_links:
        sources_complete = consultation_source_complete and course_source_complete
        outcomes["LX0609-03-01-04"] = _state(
            "compliant" if sources_complete else "data_gap",
            (
                "execution_specific_summarized"
                if sources_complete
                else "execution_source_incomplete"
            ),
        )
    elif consultation_source_complete and course_source_complete:
        outcomes["LX0609-03-01-04"] = _state(
            "not_applicable", "execution_record_missing"
        )
    else:
        outcomes["LX0609-03-01-04"] = _state(
            "evaluation_unknown", "semantic_low_confidence"
        )
    return MappingProxyType(
        {rule_id: outcomes[rule_id] for rule_id in RULE_IDS}
    )
