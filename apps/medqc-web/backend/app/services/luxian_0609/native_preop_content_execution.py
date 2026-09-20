"""LX0609-078/079 术前文书内容完整性。

029、039 负责文书存在性。本模块只在同一证据快照已取得实质正文后，
以一次受控的原子事实抽取核对每份文书自身的字段，禁止跨文书拼接。
"""

from __future__ import annotations

from dataclasses import dataclass
import json
import re
from typing import Any, Mapping, Protocol, Sequence

from .course_quality.shared import clean_text, response_json_payload
from .decision_model import ApplicabilityState, EvidenceState, QcDirection, RuleDecision
from .evidence_material import (
    EvidenceMaterialTruncated,
    EvidenceMaterialUnavailable,
    Luxian0609EvidenceMaterialStore,
)
from .evidence_snapshot import Luxian0609EvidenceSnapshot
from .source_manifest import QueryStatus


RULE_FIELDS = {
    "LX0609-078": (
        "brief_condition",
        "preop_diagnosis",
        "surgical_indication",
        "planned_procedure",
        "planned_anesthesia",
        "precautions",
        "surgeon_preop_visit",
    ),
    "LX0609-079": (
        "preop_preparation",
        "surgical_indication",
        "surgical_plan",
        "risk_and_prevention",
        "participants_with_titles",
        "specific_opinions",
        "chair_summary",
        "discussion_date",
        "recorder_signature",
    ),
}
RULE_SOURCES = {"LX0609-078": "presurg_summary", "LX0609-079": "presurg_discussion"}
_SUBSTANTIVE = 16
_PLACEHOLDER = re.compile(
    r"^(?:无|暂无|空|空白|待填|未填|模板|空模板|\[\]|\{\}|-)+$", re.I
)


class PreopContentLLMClient(Protocol):
    async def generate(self, prompt: str, **kwargs: Any) -> Mapping[str, Any]: ...


@dataclass(frozen=True)
class PreopContentExecution:
    decisions: tuple[RuleDecision, ...]
    customer_display_facts: tuple[tuple[str, Mapping[str, Any]], ...] = ()
    llm_call_count: int = 0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    api_time: float = 0.0


def _usage(response: Mapping[str, Any]) -> tuple[int, int, int, float]:
    usage = response.get("usage") if isinstance(response.get("usage"), Mapping) else {}
    prompt = int(usage.get("prompt_tokens") or 0)
    completion = int(usage.get("completion_tokens") or 0)
    return (
        prompt,
        completion,
        int(usage.get("total_tokens") or prompt + completion),
        float(response.get("_api_time") or response.get("response_time") or 0.0),
    )


def _observation_refs(
    snapshot: Luxian0609EvidenceSnapshot, source_key: str
) -> tuple[str, ...]:
    return tuple(
        item.snapshot_ref.removeprefix("sha256:")
        for item in snapshot.observations
        if item.source_key == source_key
    )


def _decision(
    snapshot: Luxian0609EvidenceSnapshot,
    rule_id: str,
    status: str,
    reason: str,
    refs: Sequence[str],
) -> RuleDecision:
    dimensions = {
        "compliant": (
            ApplicabilityState.APPLICABLE,
            EvidenceState.SUFFICIENT,
            QcDirection.SATISFIED,
            1.0,
        ),
        "non_compliant": (
            ApplicabilityState.APPLICABLE,
            EvidenceState.SUFFICIENT,
            QcDirection.DEFECT,
            1.0,
        ),
        "not_applicable": (
            ApplicabilityState.NOT_APPLICABLE,
            EvidenceState.SUFFICIENT,
            QcDirection.UNKNOWN,
            None,
        ),
        "data_gap": (
            ApplicabilityState.UNKNOWN,
            EvidenceState.DATA_GAP,
            QcDirection.UNKNOWN,
            None,
        ),
    }
    applicability, evidence, direction, confidence = dimensions[status]
    return RuleDecision(
        rule_id=rule_id,
        snapshot_hash=snapshot.snapshot_hash,
        applicability=applicability,
        evidence_state=evidence,
        qc_direction=direction,
        reason_code=reason,
        fact_refs=tuple(sorted(set(refs))),
        evaluator_version="preop-content-v1",
        confidence=confidence,
    )


def _source_text(source: str, row: Mapping[str, Any]) -> str:
    """仅拼装同一来源行的受控字段，保留字段标签以便逐项定位。"""

    values = [clean_text(row.get("record_content") or row.get("content"))]
    if source == "presurg_discussion":
        values.extend(
            f"{label}：{value}"
            for label, field in (
                ("主持人", "host_name"),
                ("主持人小结", "host_summary"),
                ("参加讨论者", "discuss_staff"),
                ("讨论日期", "record_time"),
            )
            if (value := clean_text(row.get(field)))
        )
        # 仅白名单投影同一来源行中的业务内容，不能把整段 v2_schema（可能含
        # 人员、患者标识等）交给模型。
        if suggestion := _discussion_suggestion(row.get("v2_schema")):
            values.append(f"讨论建议：{suggestion}")
    return "\n".join(values)


def _discussion_suggestion(raw: Any) -> str:
    """读取讨论扩展字段时只允许 ``discuss_suggestion`` 这一业务键。"""

    value = raw
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except json.JSONDecodeError:
            return ""
    return clean_text(value.get("discuss_suggestion")) if isinstance(value, Mapping) else ""


def _substantive(source: str, row: Mapping[str, Any]) -> str:
    value = _source_text(source, row)
    return (
        value
        if len(value) >= _SUBSTANTIVE and not _PLACEHOLDER.fullmatch(value)
        else ""
    )


def _document_id(row: Mapping[str, Any]) -> str:
    return clean_text(row.get("document_id"))


def _has_structured_recorder_signature(row: Mapping[str, Any]) -> bool:
    """客户确认 submitter 即术前讨论记录者的电子签名。"""

    return bool(clean_text(row.get("submitter")))


def _prompt(documents: Sequence[tuple[str, str, str]], selected: Sequence[str]) -> str:
    schemas = {rule_id: list(RULE_FIELDS[rule_id]) for rule_id in selected}
    rendered = "\n\n".join(
        f"[document_id={doc_id}; source_type={source}]\n{text}"
        for doc_id, source, text in documents
    )
    return f"""你是病历质控原子事实抽取器。只从每份给定术前文书的受控文本或结构字段投影中摘取字段值；没有明确的连续输入片段时填 null。禁止总结、推断、跨文书补全，不得输出状态、建议或未请求字段。

按 source_type 使用字段全集：{schemas}
只输出 JSON：{{\"documents\":[{{\"document_id\":\"原document_id\",\"source_type\":\"presurg_summary或presurg_discussion\",\"items\":{{\"字段\":\"输入中的连续片段或null\"}}}}]}}。

文书：
{rendered}"""


def _validated_items(
    payload: Mapping[str, Any],
    expected: Mapping[tuple[str, str], str],
    selected: Sequence[str],
) -> dict[tuple[str, str], Mapping[str, Any]] | None:
    raw = payload.get("documents")
    if not isinstance(raw, list) or len(raw) != len(expected):
        return None
    parsed: dict[tuple[str, str], Mapping[str, Any]] = {}
    for item in raw:
        if not isinstance(item, Mapping):
            return None
        doc_id, source = (
            clean_text(item.get("document_id")),
            clean_text(item.get("source_type")),
        )
        key = (source, doc_id)
        original = expected.get(key)
        facts = item.get("items")
        rule_id = next((rule for rule in selected if RULE_SOURCES[rule] == source), "")
        if (
            not original
            or not rule_id
            or key in parsed
            or not isinstance(facts, Mapping)
            or set(facts) != set(RULE_FIELDS[rule_id])
        ):
            return None
        for field, quote in facts.items():
            if quote is not None and (
                not isinstance(quote, str)
                or not clean_text(quote)
                or clean_text(quote) not in original
            ):
                return None
        parsed[key] = facts
    return parsed if set(parsed) == set(expected) else None


async def evaluate_preop_content_rules(
    *,
    rule_ids: Sequence[str],
    snapshot: Luxian0609EvidenceSnapshot,
    materials: Luxian0609EvidenceMaterialStore,
    llm_client: PreopContentLLMClient | None,
) -> PreopContentExecution:
    selected = tuple(rule_id for rule_id in RULE_FIELDS if rule_id in set(rule_ids))
    if not selected:
        return PreopContentExecution(())
    records: dict[str, list[tuple[str, Mapping[str, Any], str]]] = {}
    terminal: dict[str, RuleDecision] = {}
    for rule_id in selected:
        source = RULE_SOURCES[rule_id]
        refs = _observation_refs(snapshot, source)
        observation = next(
            (item for item in snapshot.observations if item.source_key == source), None
        )
        if observation is None or observation.query_state is QueryStatus.UNAVAILABLE:
            terminal[rule_id] = _decision(
                snapshot, rule_id, "data_gap", "source_unavailable", refs
            )
            continue
        if observation.query_state is QueryStatus.ERROR:
            terminal[rule_id] = _decision(
                snapshot, rule_id, "data_gap", "source_readiness_unproven", refs
            )
            continue
        try:
            rows = materials.document_rows(source, snapshot=snapshot)
        except EvidenceMaterialTruncated:
            terminal[rule_id] = _decision(
                snapshot, rule_id, "data_gap", "source_truncated", refs
            )
            continue
        except EvidenceMaterialUnavailable:
            terminal[rule_id] = _decision(
                snapshot, rule_id, "data_gap", "source_unavailable", refs
            )
            continue
        substantive = [
            (ref, row, _substantive(source, row))
            for ref, row in rows
            if _substantive(source, row) and _document_id(row)
        ]
        if not substantive:
            terminal[rule_id] = _decision(
                snapshot, rule_id, "not_applicable", "eligibility_not_met", refs
            )
            continue
        records[rule_id] = substantive
    active = tuple(rule for rule in selected if rule not in terminal)
    if not active:
        return PreopContentExecution(tuple(terminal[rule] for rule in selected))
    if llm_client is None:
        return PreopContentExecution(
            tuple(
                terminal.get(rule)
                or _decision(
                    snapshot,
                    rule,
                    "data_gap",
                    "source_readiness_unproven",
                    tuple(ref for ref, _, _ in records[rule]),
                )
                for rule in selected
            )
        )
    documents = [
        (str(_document_id(row)), RULE_SOURCES[rule], text)
        for rule in active
        for _ref, row, text in records[rule]
    ]
    expected = {(source, doc_id): text for doc_id, source, text in documents}
    try:
        response = await llm_client.generate(
            _prompt(documents, active),
            max_completion_tokens=900,
            allow_length_retry=False,
            temperature=0,
            top_p=1,
            enable_thinking=False,
        )
    except TimeoutError:
        return PreopContentExecution(
            tuple(
                terminal.get(rule)
                or _decision(
                    snapshot,
                    rule,
                    "data_gap",
                    "source_readiness_unproven",
                    tuple(ref for ref, _, _ in records[rule]),
                )
                for rule in selected
            ),
            llm_call_count=1,
        )
    except Exception:
        return PreopContentExecution(
            tuple(
                terminal.get(rule)
                or _decision(
                    snapshot,
                    rule,
                    "data_gap",
                    "source_readiness_unproven",
                    tuple(ref for ref, _, _ in records[rule]),
                )
                for rule in selected
            ),
            llm_call_count=1,
        )
    prompt_tokens, completion_tokens, total_tokens, api_time = _usage(response)
    payload = response_json_payload(response)
    parsed = _validated_items(payload, expected, active) if payload else None
    if parsed is None:
        return PreopContentExecution(
            tuple(
                terminal.get(rule)
                or _decision(
                    snapshot,
                    rule,
                    "data_gap",
                    "source_readiness_unproven",
                    tuple(ref for ref, _, _ in records[rule]),
                )
                for rule in selected
            ),
            llm_call_count=1,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
            api_time=api_time,
        )
    decisions: list[RuleDecision] = []
    display: list[tuple[str, Mapping[str, Any]]] = []
    for rule in selected:
        if rule in terminal:
            decisions.append(terminal[rule])
            continue
        missing: list[str] = []
        refs = tuple(ref for ref, _, _ in records[rule])
        for _ref, row, _text in records[rule]:
            values = parsed[(RULE_SOURCES[rule], _document_id(row))]
            for field in RULE_FIELDS[rule]:
                if (
                    rule == "LX0609-079"
                    and field == "recorder_signature"
                    and _has_structured_recorder_signature(row)
                ):
                    continue
                if values.get(field) is not None:
                    continue
                missing.append(field)
        status = (
            "non_compliant"
            if missing
            else "compliant"
        )
        decisions.append(
            _decision(
                snapshot,
                rule,
                status,
                "requirement_violated"
                if missing
                else "requirement_satisfied",
                refs,
            )
        )
        if status != "data_gap":
            display.append(
                (
                    rule,
                    {
                        "verification_kind": "preop_content_complete"
                        if not missing
                        else "preop_content_incomplete",
                        "target_document": RULE_SOURCES[rule],
                        "checked_fields": list(RULE_FIELDS[rule]),
                        "missing_fields": list(dict.fromkeys(missing)),
                    },
                )
            )
    return PreopContentExecution(
        tuple(decisions),
        tuple(display),
        1,
        prompt_tokens,
        completion_tokens,
        total_tokens,
        api_time,
    )
