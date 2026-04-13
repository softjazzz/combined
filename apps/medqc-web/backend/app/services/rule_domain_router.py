from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from app.constants.doc_types import DOC_TYPE_CN_TO_EN, DOC_TYPE_FULL_MAP, DOC_TYPE_MAP


DOMAIN_DOC_PRIORITY: dict[str, tuple[str, ...]] = {
    "admission": (
        "admission_record",
    ),
    "course": (
        "first_course_record",
        "daily_course_record",
        "senior_course_record",
        "rescue_record",
    ),
    "surgery": (
        "presurg_summary",
        "presurg_discussion",
        "surgery_record",
        "anesthesia_record",
        "consent_form",
        "postsurg_firstcourse_record",
        "surgery_safecheck_record",
    ),
    "consult_discussion": (
        "consultation_record",
        "diffcase_discussion_record",
        "death_discussion",
        "handoff_record",
        "handover_record",
    ),
    "terminal": (
        "discharge_record",
        "death_record",
    ),
    "index_coding_settlement": (
        "mr",
        "diagnosis",
        "mr_surgery",
        "mr_cost",
        "medical_insurance_settlement",
        "medical_insurance_settlement_cost",
    ),
}

_DOC_TO_DOMAIN: dict[str, str] = {
    doc_type: domain
    for domain, priorities in DOMAIN_DOC_PRIORITY.items()
    for doc_type in priorities
}

_DOMAIN_PRIORITY: tuple[str, ...] = (
    "admission",
    "course",
    "surgery",
    "consult_discussion",
    "terminal",
    "index_coding_settlement",
)


@dataclass(frozen=True)
class RuleRoutingDecision:
    execution_domain: str
    primary_doc_types: tuple[str, ...]
    aux_doc_types: tuple[str, ...]
    strict_primary_required: bool

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class RuleExecutionInput:
    rule_id: str
    document_type: str
    execution_domain: str
    primary_medical_text: str
    supporting_evidence: list[dict[str, Any]]
    timeline_facts: list[dict[str, Any]]
    source_documents: list[dict[str, Any]]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class EvidencePayload:
    primary_document_text: str
    supporting_documents: list[dict[str, Any]]
    timeline_facts: list[dict[str, Any]]
    document_hits: dict[str, Any]
    data_quality_flags: list[str]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _normalize_doc_type(document_type: str) -> str:
    value = str(document_type or "").strip()
    if not value:
        return ""
    if value in _DOC_TO_DOMAIN:
        return value
    if value in DOC_TYPE_CN_TO_EN:
        return DOC_TYPE_CN_TO_EN[value]
    mapped = DOC_TYPE_FULL_MAP.get(value)
    if mapped and mapped in DOC_TYPE_CN_TO_EN:
        return DOC_TYPE_CN_TO_EN[mapped]
    return value


def _normalize_rule_docs(rule: dict[str, Any]) -> tuple[str, ...]:
    normalized: list[str] = []
    for raw_doc in rule.get("applicable_documents") or []:
        doc_type = _normalize_doc_type(str(raw_doc or ""))
        if doc_type:
            normalized.append(doc_type)
    seen: set[str] = set()
    unique: list[str] = []
    for doc_type in normalized:
        if doc_type not in seen:
            seen.add(doc_type)
            unique.append(doc_type)
    return tuple(unique)


def route_rule_to_domain(rule: dict[str, Any]) -> RuleRoutingDecision:
    rule_docs = _normalize_rule_docs(rule)
    if not rule_docs:
        return RuleRoutingDecision(
            execution_domain="course",
            primary_doc_types=DOMAIN_DOC_PRIORITY["course"],
            aux_doc_types=(),
            strict_primary_required=False,
        )

    candidate_domains = {
        _DOC_TO_DOMAIN[doc_type]
        for doc_type in rule_docs
        if doc_type in _DOC_TO_DOMAIN
    }
    execution_domain = next(
        (
            domain
            for domain in _DOMAIN_PRIORITY
            if domain in candidate_domains
        ),
        "course",
    )

    domain_priority = DOMAIN_DOC_PRIORITY[execution_domain]
    matched_in_domain = tuple(doc for doc in domain_priority if doc in rule_docs)
    primary_doc_types = matched_in_domain[:1] or domain_priority[:1]
    aux_doc_types = tuple(doc for doc in matched_in_domain if doc not in primary_doc_types)
    if not aux_doc_types:
        aux_doc_types = tuple(doc for doc in domain_priority if doc not in primary_doc_types)[:3]

    return RuleRoutingDecision(
        execution_domain=execution_domain,
        primary_doc_types=primary_doc_types,
        aux_doc_types=aux_doc_types,
        strict_primary_required=True,
    )


def display_name_for_doc_type(document_type: str) -> str:
    normalized = _normalize_doc_type(document_type)
    return DOC_TYPE_MAP.get(normalized, normalized or str(document_type or ""))


def render_rule_execution_medical_text(rule_input: RuleExecutionInput) -> str:
    blocks = [
        f"【主文书类型】{rule_input.document_type}",
        "【主文书正文】",
        rule_input.primary_medical_text or "（无）",
    ]
    if rule_input.supporting_evidence:
        evidence_lines = []
        for item in rule_input.supporting_evidence:
            source_type = str(item.get("document_type") or "")
            evidence = str(item.get("evidence_text") or "")
            evidence_lines.append(f"- {source_type}: {evidence}")
        blocks.extend(["【同域辅助证据】", "\n".join(evidence_lines)])
    if rule_input.timeline_facts:
        timeline_lines = []
        for item in rule_input.timeline_facts:
            timeline_lines.append(
                f"- {item.get('source_table') or item.get('document_type')}: "
                f"{item.get('field')}={item.get('value')}"
            )
        blocks.extend(["【时间锚点】", "\n".join(timeline_lines)])
    if rule_input.source_documents:
        inventory_lines = []
        for item in rule_input.source_documents:
            inventory_lines.append(
                f"- {item.get('document_type')} hit={item.get('hit')} "
                f"doc_id={item.get('document_id') or ''}"
            )
        blocks.extend(["【文书清单】", "\n".join(inventory_lines)])
    return "\n".join(blocks)


def build_evidence_payload_from_rule_input(
    *,
    rule_input: RuleExecutionInput,
    document_hits: dict[str, Any] | None = None,
    data_quality_flags: list[str] | None = None,
) -> EvidencePayload:
    supporting_documents: list[dict[str, Any]] = []
    for item in rule_input.supporting_evidence:
        supporting_documents.append(
            {
                "document_type": str(item.get("document_type") or ""),
                "source_table": str(item.get("source_table") or ""),
                "document_id": str(item.get("document_id") or ""),
                "document_title": str(item.get("document_title") or ""),
                "display_time": str(item.get("display_time") or ""),
                "evidence_text": str(item.get("evidence_text") or ""),
                "sections": list(item.get("sections") or []),
                "source_fields": list(item.get("source_fields") or []),
            }
        )
    return EvidencePayload(
        primary_document_text=str(rule_input.primary_medical_text or ""),
        supporting_documents=supporting_documents,
        timeline_facts=list(rule_input.timeline_facts or []),
        document_hits=dict(document_hits or {}),
        data_quality_flags=[str(item) for item in (data_quality_flags or []) if str(item).strip()],
    )
