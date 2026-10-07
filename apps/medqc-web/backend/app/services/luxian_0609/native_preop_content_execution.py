"""LX0609-04-01-04、LX0609-04-01-05 术前文书内容完整性。

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
    "LX0609-04-01-04": (
        "brief_condition",
        "preop_diagnosis",
        "surgical_indication",
        "planned_procedure",
        "planned_anesthesia",
        "precautions",
        "surgeon_preop_visit",
    ),
    "LX0609-04-01-05": (
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
RULE_SOURCES = {"LX0609-04-01-04": "presurg_summary", "LX0609-04-01-05": "presurg_discussion"}
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
    return f"""你是病历质控原子事实抽取器。只从每份给定术前文书的受控文本或结构字段投影中摘取字段值；术前小结没有明确的连续输入片段时填 null，术前讨论按下述三态合同返回。禁止总结、推断、跨文书补全，不得输出状态、建议或未请求字段。

按 source_type 使用字段全集：{schemas}
术前讨论presurg_discussion的每项返回对象：{{"state":"present|missing|unknown","quote":"连续原文或null","reviewed_all_sections":true或false}}。
present必须有对应原文；missing仅在检查该文书全部输入（正文、主持人小结、讨论建议及结构字段）后仍无对应内容时使用，quote为null且reviewed_all_sections为true。未抽到、含义不明或无法完整核查用unknown，绝不能以未抽到代替确认缺失。一个原文片段可以支持多个不同检查项，不因位于主持人小结就只能用于chair_summary。
九项定义：preop_preparation=已完成或拟实施的术前检查、准备及禁忌评估；surgical_indication=疾病、症状、保守治疗效果等手术理由；surgical_plan=拟行术式和方案；risk_and_prevention=可能风险及对应防范措施；participants_with_titles=参加者姓名及职称；specific_opinions=参加者具体讨论意见；chair_summary=主持人总结意见；discussion_date=讨论日期；recorder_signature=记录者签名。按内容识别，不要求固定栏目标题。
术前小结presurg_summary仍返回连续原文或null，不使用上述对象。
specific_opinions是参加讨论者的具体意见，chair_summary是主持人总结，两者分别抽取；仅有参加人员名单、拟行术式或主持人同意手术，不能代替具体讨论意见。“略”、空白和仅有栏目标题均填null，不算实质内容。
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
            if source == "presurg_discussion" and isinstance(quote, Mapping):
                if set(quote) != {"state", "quote", "reviewed_all_sections"}:
                    return None
                state, excerpt = quote["state"], quote["quote"]
                if state not in {"present", "missing", "unknown"} or type(quote["reviewed_all_sections"]) is not bool:
                    return None
                if state == "present":
                    if not isinstance(excerpt, str) or not clean_text(excerpt) or clean_text(excerpt) not in original:
                        return None
                elif excerpt is not None or (state == "missing" and not quote["reviewed_all_sections"]):
                    return None
                continue
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
            rule_id == "LX0609-04-01-05"
            and field == "recorder_signature"
            and _has_structured_recorder_signature(row)
        )
        and (
            values.get(field) is None if rule_id == "LX0609-04-01-04"
            else isinstance(values.get(field), Mapping) and values[field].get("state") == "missing"
        )
    }


# 术前小结模板中紧随“拟施手术名称和方式”之后的固定标签。模型取术式引文时可能把
# 下一个标签的开头字（如“拟施 麻醉方式”中的“拟施”）带进引文末尾。
_SUMMARY_TEMPLATE_LABELS = (
    "拟施麻醉方式",
    "拟诊手术日期",
    "拟施手术日期",
    "麻醉方式",
    "手术要点",
    "术前准备",
    "手术医师签名",
)


def _procedure_name_for_association(quote: Any, document_text: str) -> Any:
    """仅为手术事件关联生成比较值；原始引文及其原文校验保持不变。

    受限规范化只做两件事，且都必须由原文证明：
    1. 去掉引文开头的标签分隔冒号；
    2. 引文末尾若是下一个固定模板标签的开头部分，而原文中紧接其后的正是该标签
       的其余部分，则去掉这段标签残留。
    引文在原文中出现不唯一、或末尾不构成标签残留时原样返回，不做任意删字。
    """

    if not isinstance(quote, str):
        return quote
    cleaned = clean_text(quote)
    text = clean_text(document_text)
    if not cleaned or text.count(cleaned) != 1:
        return quote
    following = re.sub(r"\s+", "", text[text.index(cleaned) + len(cleaned):])
    candidate = re.sub(r"^[:：\s]+", "", cleaned)
    for label in _SUMMARY_TEMPLATE_LABELS:
        for size in range(len(label) - 1, 0, -1):
            residue = label[:size]
            if candidate.endswith(residue) and (residue + following).startswith(label):
                stripped = candidate[: -len(residue)].strip()
                return stripped or quote
    return candidate or quote


def _association_state_for_rule(
    *,
    rule_id: str,
    records: Sequence[tuple[str, Mapping[str, Any], str]],
    parsed: Mapping[tuple[str, str], Mapping[str, Any]],
    events: Sequence[SurgeryEvent],
) -> tuple[set[str], bool, list[Mapping[str, Any]], set[str]]:
    """078按手术事件聚合；079逐份核对，返回确认缺项、歧义、安全展示和待确认字段。

    归属不明但不能排除属于本手术的文书（``ambiguous``），只能阻止错误的
    “确认缺少”断言：字段在已匹配文书中缺失、而无法归属文书中有记录时，
    该字段列为待确认，不计入确认缺项，也不会补齐字段或证明合规。
    不同手术的已匹配文书互不参与。
    """

    source = RULE_SOURCES[rule_id]
    grouped: dict[int, list[tuple[Mapping[str, Any], Mapping[str, Any]]]] = {}
    ambiguous_values: list[Mapping[str, Any]] = []
    ambiguous_documents: list[tuple[Mapping[str, Any], Mapping[str, Any]]] = []
    display_documents: list[Mapping[str, Any]] = []
    for document_index, (_ref, row, _text) in enumerate(records, start=1):
        values = parsed[(source, _document_id(row))]
        if rule_id == "LX0609-04-01-05":
            # 079 只核对每份术前讨论记录自身的九项内容，不跨文书补字段；
            # 文书归属哪台手术不改变这些内容是否完整。
            association_state, event_index = "not_required", None
            if any(
                (value is None or isinstance(value, Mapping) and value.get("state") == "unknown")
                and not (field == "recorder_signature" and _has_structured_recorder_signature(row))
                for field, value in values.items()
            ):
                ambiguous_values.append(values)
            grouped.setdefault(document_index, []).append((row, values))
        else:
            association = associate_preop_document_to_surgery_event(
                events=events,
                procedure_name=_procedure_name_for_association(
                    values.get("planned_procedure"), _text
                ),
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
                # 尚无实际手术事件时逐份检查；不能把同住院的不同拟行手术
                # 合并成事件0，让一份小结替另一份补齐缺项。
                grouped.setdefault(-document_index, []).append((row, values))
            else:
                ambiguous_values.append(values)
                ambiguous_documents.append((row, values))
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
    pending_fields: set[str] = set()
    if rule_id == "LX0609-04-01-04":
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
                if any(
                    field not in _missing_fields_for_document(
                        rule_id=rule_id, row=row, values=values
                    )
                    for row, values in ambiguous_documents
                ):
                    # 无法归属的文书记载了该项：不能据此补齐，也不能断言缺少。
                    pending_fields.add(field)
                    continue
                confirmed_missing.add(field)
        pending_fields -= confirmed_missing
    else:
        # 讨论记录不跨文书补字段；即使同一事件也必须逐份自洽。
        for documents in grouped.values():
            for row, values in documents:
                confirmed_missing.update(
                    _missing_fields_for_document(
                        rule_id=rule_id, row=row, values=values
                    )
                )

    return confirmed_missing, bool(ambiguous_values), display_documents, pending_fields


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
        if "LX0609-04-01-04" in active
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
                    *(event_refs if rule == "LX0609-04-01-04" else ()),
                }
            )
        )
        if rule == "LX0609-04-01-04" and events is None:
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
        missing, has_ambiguous, documents, pending = _association_state_for_rule(
            rule_id=rule,
            records=records[rule],
            parsed=parsed,
            events=events or (),
        )
        if has_ambiguous and not missing:
            status, reason = "data_gap", (
                "source_readiness_unproven" if rule == "LX0609-04-01-05" else "association_failed"
            )
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
                    **({"pending_fields": sorted(pending)} if pending else {}),
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
