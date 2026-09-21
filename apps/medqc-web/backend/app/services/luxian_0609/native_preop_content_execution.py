"""LX0609-078/079 术前文书内容完整性。

029、039 负责文书存在性。本模块只在同一证据快照已取得实质正文后，
以一次受控的原子事实抽取核对每份文书自身的字段，禁止跨文书拼接。
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import json
import re
from typing import Any, Mapping, Protocol, Sequence
from zoneinfo import ZoneInfo

from .course_quality.shared import clean_text, response_json_payload
from .decision_model import ApplicabilityState, EvidenceState, QcDirection, RuleDecision
from .evidence_material import (
    EvidenceMaterialTruncated,
    EvidenceMaterialUnavailable,
    Luxian0609EvidenceMaterialStore,
)
from .evidence_snapshot import Luxian0609EvidenceSnapshot
from .source_manifest import QueryStatus
from .surgery_event_association import (
    SurgeryEvent,
    associate_preop_document_to_surgery_event,
    build_performed_surgery_events,
    summary_planned_surgery_time_from_row,
)


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


def _document_record_time(row: Mapping[str, Any]) -> datetime | None:
    """仅使用术前文书自身可靠的 record_time，绝不以提交时间猜测。"""

    value = row.get("record_time")
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value
        return value.astimezone(ZoneInfo("Asia/Shanghai")).replace(tzinfo=None)
    if not isinstance(value, str):
        return None
    normalized = value.strip().replace("Z", "+00:00")
    if not re.fullmatch(
        r"\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:[+-]\d{2}:?\d{2})?",
        normalized,
    ):
        return None
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed
    return parsed.astimezone(ZoneInfo("Asia/Shanghai")).replace(tzinfo=None)


def _missing_fields_for_document(
    *, rule_id: str, row: Mapping[str, Any], values: Mapping[str, Any]
) -> set[str]:
    return {
        field
        for field in RULE_FIELDS[rule_id]
        if not (
            rule_id == "LX0609-079"
            and field == "recorder_signature"
            and _has_structured_recorder_signature(row)
        )
        and values.get(field) is None
    }


def _association_state_for_rule(
    *,
    rule_id: str,
    records: Sequence[tuple[str, Mapping[str, Any], str]],
    parsed: Mapping[tuple[str, str], Mapping[str, Any]],
    events: Sequence[SurgeryEvent],
) -> tuple[set[str], bool, list[Mapping[str, Any]]]:
    """078按手术事件聚合；079逐份核对，返回缺项、歧义和安全展示。"""

    source = RULE_SOURCES[rule_id]
    grouped: dict[int, list[tuple[Mapping[str, Any], Mapping[str, Any]]]] = {}
    ambiguous_values: list[Mapping[str, Any]] = []
    display_documents: list[Mapping[str, Any]] = []
    for document_index, (_ref, row, _text) in enumerate(records, start=1):
        values = parsed[(source, _document_id(row))]
        if rule_id == "LX0609-079":
            # 079 只核对每份术前讨论记录自身的九项内容，不跨文书补字段；
            # 文书归属哪台手术不改变这些内容是否完整。
            association_state, event_index = "not_required", None
            grouped.setdefault(document_index, []).append((row, values))
        else:
            association = associate_preop_document_to_surgery_event(
                events=events,
                procedure_name=values.get("planned_procedure"),
                record_time=_document_record_time(row),
                planned_surgery_time=summary_planned_surgery_time_from_row(row),
            )
            association_state, event_index = (
                association.state,
                association.event_index,
            )
            if association.state == "matched" and association.event_index is not None:
                grouped.setdefault(association.event_index, []).append((row, values))
            elif association.state == "not_required":
                # 没有已实施手术事件时保持既有内容核对语义，不凭此新增错误结论。
                grouped.setdefault(0, []).append((row, values))
            else:
                ambiguous_values.append(values)
        display_documents.append(
            {
                "document_index": document_index,
                "event_index": event_index,
                "association_state": association_state,
                "missing_fields": sorted(
                    _missing_fields_for_document(
                        rule_id=rule_id, row=row, values=values
                    )
                ),
            }
        )

    confirmed_missing: set[str] = set()
    if rule_id == "LX0609-078":
        # 客户来源存在“核心小结 + 术者术前查看”两行同属一台手术的稳定模式；
        # 仅在已唯一关联的同一事件内部合并原子事实。
        for documents in grouped.values():
            for field in RULE_FIELDS[rule_id]:
                if any(
                    field not in _missing_fields_for_document(
                        rule_id=rule_id, row=row, values=values
                    )
                    for row, values in documents
                ):
                    continue
                confirmed_missing.add(field)
    else:
        # 讨论记录不跨文书补字段；即使同一事件也必须逐份自洽。
        for documents in grouped.values():
            for row, values in documents:
                confirmed_missing.update(
                    _missing_fields_for_document(
                        rule_id=rule_id, row=row, values=values
                    )
                )

    return confirmed_missing, bool(ambiguous_values), display_documents


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
            max_completion_tokens=4096,
            allow_length_retry=False,
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
    events, event_reason = (
        build_performed_surgery_events(materials)
        if "LX0609-078" in active
        else ((), "")
    )
    # 运行病历仅以正式手术记录形成事件，不能依赖终末阶段才可能形成的
    # mr_surgery；证据引用也只保留本次实际读取的来源。
    event_refs = tuple(
        ref
        for source_key in ("surgery_record",)
        for ref in _observation_refs(snapshot, source_key)
    )
    decisions: list[RuleDecision] = []
    display: list[tuple[str, Mapping[str, Any]]] = []
    for rule in selected:
        if rule in terminal:
            decisions.append(terminal[rule])
            continue
        refs = tuple(
            sorted(
                {
                    *(ref for ref, _, _ in records[rule]),
                    *(event_refs if rule == "LX0609-078" else ()),
                }
            )
        )
        if rule == "LX0609-078" and events is None:
            decisions.append(
                _decision(
                    snapshot,
                    rule,
                    "data_gap",
                    event_reason or "association_failed",
                    refs,
                )
            )
            continue
        missing, has_ambiguous, documents = _association_state_for_rule(
            rule_id=rule,
            records=records[rule],
            parsed=parsed,
            events=events or (),
        )
        if has_ambiguous and not missing:
            status, reason = "data_gap", "association_failed"
        elif missing:
            status, reason = "non_compliant", "requirement_violated"
        else:
            status, reason = "compliant", "requirement_satisfied"
        decisions.append(
            _decision(
                snapshot,
                rule,
                status,
                reason,
                refs,
            )
        )
        display.append(
            (
                rule,
                {
                    "verification_kind": (
                        "preop_surgery_association_ambiguous"
                        if status == "data_gap"
                        else "preop_content_complete"
                        if not missing
                        else "preop_content_incomplete"
                    ),
                    "target_document": RULE_SOURCES[rule],
                    "checked_fields": list(RULE_FIELDS[rule]),
                    "missing_fields": sorted(missing),
                    "documents": documents,
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
