from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Mapping, Sequence


class Consultation020ContractError(ValueError):
    """020 专用事实输出不符合受控合同。"""


_SOURCES = {
    "consultation_record",
    "daily_course_record",
    "senior_course_record",
}
_ROLES = {
    "completed_opinion",
    "request_only",
    "template_or_history",
    "unknown",
}
_RELATIONS = {"linked", "missing", "ambiguous", "not_applicable"}
_LINK_BASES = {
    "same_document_explicit",
    "later_document_explicit",
    "later_document_semantic",
    "none",
}
_LINK_SCOPES = {"single_episode", "explicit_multi_episode"}
_CONFIDENCES = {"high", "medium", "low"}
_ITEM_KEYS = {
    "episode_ref",
    "member_refs",
    "opinion_ref",
    "role",
    "execution_relation",
    "execution_refs",
    "link_basis",
    "link_scope",
    "confidence",
}


@dataclass(frozen=True)
class Consultation020InputDocument:
    ref: str
    source: str
    record_time: str | None
    content: str = ""

    def __post_init__(self) -> None:
        if not self.ref or self.source not in _SOURCES:
            raise Consultation020ContractError("invalid input document")
        if self.record_time is not None and str(self.record_time).strip():
            _parse_time(self.record_time)


@dataclass(frozen=True)
class Consultation020EpisodeFact:
    episode_ref: str
    member_refs: tuple[str, ...]
    opinion_ref: str | None
    role: str
    execution_relation: str
    execution_refs: tuple[str, ...]
    link_basis: str
    link_scope: str
    confidence: str


@dataclass(frozen=True)
class Consultation020RelationFacts:
    episodes: tuple[Consultation020EpisodeFact, ...]
    consultation_source_complete: bool
    daily_source_complete: bool
    senior_source_complete: bool
    projection_complete: bool


@dataclass(frozen=True)
class Consultation020DecisionState:
    status: str
    reason_code: str
    evidence_refs: tuple[str, ...] = ()


def _parse_time(value: str) -> datetime:
    try:
        return datetime.fromisoformat(str(value).strip())
    except (TypeError, ValueError) as exc:
        raise Consultation020ContractError("invalid record time") from exc


def _string_tuple(value: Any, *, field: str) -> tuple[str, ...]:
    if not isinstance(value, list) or any(
        not isinstance(item, str) or not item.strip() for item in value
    ):
        raise Consultation020ContractError(f"invalid {field}")
    normalized = tuple(item.strip() for item in value)
    if len(normalized) != len(set(normalized)):
        raise Consultation020ContractError(f"duplicate {field}")
    return normalized


def validate_consultation_020_relation_payload(
    payload: Mapping[str, Any],
    documents: Sequence[Consultation020InputDocument],
    *,
    consultation_source_complete: bool = True,
    daily_source_complete: bool = True,
    senior_source_complete: bool = True,
    projection_complete: bool = True,
) -> Consultation020RelationFacts:
    """校验 LLM 的逐会诊关联事实，不接受客户状态或原文输出。"""

    if not isinstance(payload, Mapping) or set(payload) != {"consultations"}:
        raise Consultation020ContractError("invalid payload shape")
    raw_items = payload.get("consultations")
    if not isinstance(raw_items, list):
        raise Consultation020ContractError("invalid consultations")

    by_ref: dict[str, Consultation020InputDocument] = {}
    for document in documents:
        if not isinstance(document, Consultation020InputDocument):
            raise Consultation020ContractError("invalid input document type")
        if document.ref in by_ref:
            raise Consultation020ContractError("duplicate input ref")
        by_ref[document.ref] = document
    consultation_refs = {
        ref
        for ref, document in by_ref.items()
        if document.source == "consultation_record"
    }

    episodes: list[Consultation020EpisodeFact] = []
    partitioned_refs: list[str] = []
    linked_usage: dict[str, list[Consultation020EpisodeFact]] = {}
    for raw in raw_items:
        if not isinstance(raw, Mapping) or set(raw) != _ITEM_KEYS:
            raise Consultation020ContractError("invalid consultation item shape")
        episode_ref = str(raw["episode_ref"] or "").strip()
        member_refs = _string_tuple(raw["member_refs"], field="member_refs")
        role = str(raw["role"] or "").strip()
        relation = str(raw["execution_relation"] or "").strip()
        execution_refs = _string_tuple(raw["execution_refs"], field="execution_refs")
        basis = str(raw["link_basis"] or "").strip()
        scope = str(raw["link_scope"] or "").strip()
        confidence = str(raw["confidence"] or "").strip()
        raw_opinion_ref = raw["opinion_ref"]
        opinion_ref = (
            str(raw_opinion_ref).strip()
            if isinstance(raw_opinion_ref, str) and raw_opinion_ref.strip()
            else None
        )

        if (
            role not in _ROLES
            or relation not in _RELATIONS
            or basis not in _LINK_BASES
            or scope not in _LINK_SCOPES
            or confidence not in _CONFIDENCES
        ):
            raise Consultation020ContractError("invalid controlled value")
        if not member_refs or any(ref not in consultation_refs for ref in member_refs):
            raise Consultation020ContractError("invalid consultation member ref")
        if episode_ref != min(member_refs):
            raise Consultation020ContractError("episode_ref must be the first member ref")
        partitioned_refs.extend(member_refs)

        if role == "completed_opinion":
            if opinion_ref not in member_refs:
                raise Consultation020ContractError("invalid opinion_ref")
            if relation == "not_applicable":
                raise Consultation020ContractError("completed opinion needs relation")
        else:
            if opinion_ref is not None:
                raise Consultation020ContractError("non-target cannot have opinion_ref")
            if relation not in {"not_applicable", "ambiguous"}:
                raise Consultation020ContractError("non-target cannot have execution result")

        if relation in {"linked", "ambiguous"}:
            if not execution_refs or basis == "none":
                raise Consultation020ContractError("linked relation requires evidence")
        elif execution_refs or basis != "none":
            raise Consultation020ContractError("non-linked relation cannot have evidence")
        if scope == "explicit_multi_episode" and (
            relation != "linked"
            or basis != "later_document_explicit"
            or confidence != "high"
        ):
            raise Consultation020ContractError("invalid explicit multi-episode link")

        opinion_document = by_ref[opinion_ref] if opinion_ref else None
        opinion_time = (
            _parse_time(str(opinion_document.record_time))
            if opinion_document is not None
            and opinion_document.record_time is not None
            and str(opinion_document.record_time).strip()
            else None
        )
        if role == "completed_opinion" and opinion_time is None:
            raise Consultation020ContractError("completed opinion time is unavailable")
        for ref in execution_refs:
            document = by_ref.get(ref)
            if document is None:
                raise Consultation020ContractError("unknown execution ref")
            if basis == "same_document_explicit":
                if ref not in member_refs:
                    raise Consultation020ContractError("invalid same-document link")
            elif document.source not in {
                "daily_course_record",
                "senior_course_record",
            }:
                raise Consultation020ContractError("invalid execution source")
            execution_time = (
                _parse_time(str(document.record_time))
                if document.record_time is not None and str(document.record_time).strip()
                else None
            )
            if (
                basis != "same_document_explicit"
                and execution_time is None
                and relation == "linked"
            ):
                raise Consultation020ContractError("linked execution time is unavailable")
            if opinion_time is not None and execution_time is not None and execution_time < opinion_time:
                raise Consultation020ContractError("execution time precedes opinion time")

        episode = Consultation020EpisodeFact(
            episode_ref=episode_ref,
            member_refs=member_refs,
            opinion_ref=opinion_ref,
            role=role,
            execution_relation=relation,
            execution_refs=execution_refs,
            link_basis=basis,
            link_scope=scope,
            confidence=confidence,
        )
        episodes.append(episode)
        if relation == "linked":
            for ref in execution_refs:
                linked_usage.setdefault(ref, []).append(episode)

    if len(partitioned_refs) != len(set(partitioned_refs)) or set(partitioned_refs) != consultation_refs:
        raise Consultation020ContractError("consultation refs must form one partition")
    for ref, owners in linked_usage.items():
        if len(owners) <= 1:
            continue
        if any(owner.link_scope != "explicit_multi_episode" for owner in owners):
            raise Consultation020ContractError(f"duplicate execution assignment: {ref}")

    return Consultation020RelationFacts(
        episodes=tuple(sorted(episodes, key=lambda item: item.episode_ref)),
        consultation_source_complete=bool(consultation_source_complete),
        daily_source_complete=bool(daily_source_complete),
        senior_source_complete=bool(senior_source_complete),
        projection_complete=bool(projection_complete),
    )


def reduce_consultation_020_relation(
    facts: Consultation020RelationFacts,
) -> Consultation020DecisionState:
    """只由受控事实生成 020 状态，绝不从正文或关键词补结论。"""

    refs = tuple(
        ref
        for episode in facts.episodes
        for ref in (episode.episode_ref, *episode.execution_refs)
    )
    if not facts.consultation_source_complete:
        return Consultation020DecisionState(
            "data_gap", "consultation_source_incomplete", refs
        )

    completed = tuple(
        episode for episode in facts.episodes if episode.role == "completed_opinion"
    )
    missing = tuple(
        episode
        for episode in completed
        if episode.execution_relation == "missing" and episode.confidence == "high"
    )
    if missing:
        if (
            facts.daily_source_complete
            and facts.senior_source_complete
            and facts.projection_complete
        ):
            return Consultation020DecisionState(
                "non_compliant", "completed_opinion_execution_missing", refs
            )
        return Consultation020DecisionState(
            "data_gap", "execution_source_incomplete", refs
        )

    if any(
        episode.role == "unknown"
        or episode.execution_relation == "ambiguous"
        or episode.confidence != "high"
        for episode in facts.episodes
    ):
        return Consultation020DecisionState(
            "evaluation_unknown", "consultation_execution_relation_ambiguous", refs
        )
    if not completed:
        return Consultation020DecisionState(
            "not_applicable", "completed_consultation_opinion_absent", refs
        )
    linked_usage: dict[str, int] = {}
    for episode in completed:
        if episode.execution_relation != "linked":
            continue
        for ref in episode.execution_refs:
            linked_usage[ref] = linked_usage.get(ref, 0) + 1
    if any(count > 1 for count in linked_usage.values()):
        return Consultation020DecisionState(
            "evaluation_unknown", "multi_consultation_execution_link_ambiguous", refs
        )
    if all(episode.execution_relation == "linked" for episode in completed):
        return Consultation020DecisionState(
            "compliant", "all_completed_opinions_have_execution", refs
        )
    return Consultation020DecisionState(
        "evaluation_unknown", "consultation_execution_relation_ambiguous", refs
    )
