"""LX0609-04-01-04、LX0609-04-01-05 术前文书内容完整性。

029、039 负责文书存在性。本模块只在同一证据快照已取得实质正文后，
以一次受控的原子事实抽取核对每份文书自身的字段，禁止跨文书拼接。
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
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
    surgery_event_begin_time,
)
from .source_evidence_reader import authoritative_document_time_value


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


def _has_structured_discussion_date(row: Mapping[str, Any]) -> bool:
    """同一讨论记录的 record_time 已映射为讨论日期；只证明存在，不推断时限。"""

    value = row.get("record_time")
    if isinstance(value, date):
        return True
    if not isinstance(value, str):
        return False
    value = value.strip()
    if not re.fullmatch(
        r"\d{4}-\d{2}-\d{2}(?:[ T]\d{2}:\d{2}(?::\d{2}(?:\.\d+)?)?(?:Z|[+-]\d{2}:?\d{2})?)?",
        value,
    ):
        return False
    try:
        if len(value) == 10:
            date.fromisoformat(value)
        else:
            datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return False
    return True


def _has_structured_field(rule_id: str, row: Mapping[str, Any], field: str) -> bool:
    return rule_id == "LX0609-04-01-05" and (
        field == "recorder_signature" and _has_structured_recorder_signature(row)
        or field == "discussion_date" and _has_structured_discussion_date(row)
    )


def _document_spans(text: str, document_index: int) -> dict[str, str]:
    """保留受控原文的每个字符；编号只在本次完整 prompt 内有效。"""

    return {
        f"d{document_index}:s{index}": match.group()
        for index, match in enumerate(
            re.finditer(r"[^。！？\n]+[。！？]?|[。！？]|\n", text), start=1
        )
    }


def _resolve_span_fact(
    value: Any, spans: Mapping[str, str], field: str
) -> Any:
    """新引用只回取同文书单片段；旧引文不修复，继续走原校验。"""

    if not isinstance(value, Mapping) or "span_id" not in value:
        return value
    if field == "planned_procedure" or set(value) != {
        "state", "span_id", "reviewed_all_sections"
    }:
        return value
    state, span_id = value["state"], value["span_id"]
    if state == "present":
        if not isinstance(span_id, str) or span_id not in spans or not spans[span_id].strip():
            return value
        quote = spans[span_id]
    elif state in ("missing", "unknown") and span_id is None:
        quote = None
    else:
        return value
    return {"state": state, "quote": quote, "reviewed_all_sections": value["reviewed_all_sections"]}


def _prompt(documents: Sequence[tuple[str, str, str]], selected: Sequence[str]) -> str:
    schemas = {rule_id: list(RULE_FIELDS[rule_id]) for rule_id in selected}
    rendered = json.dumps({"documents": [
        {"document_id": doc_id, "source_type": source,
         "spans": [{"span_id": span_id, "text": excerpt} for span_id, excerpt in
                   _document_spans(text, index).items()]}
        for index, (doc_id, source, text) in enumerate(documents, start=1)
    ]}, ensure_ascii=False)
    response_example = json.dumps({"documents": [{
        "document_id": "原document_id", "source_type": "presurg_summary或presurg_discussion",
        "items": {"字段": {"state": "present|missing|unknown", "span_id": "d1:s1或null", "reviewed_all_sections": True}},
    }]}, ensure_ascii=False)
    return f"""你是病历质控原子事实抽取器。只从每份给定术前文书的受控文本或结构字段投影中摘取字段值；术前小结与术前讨论均按下述三态合同返回。禁止总结、推断、跨文书补全，不得输出状态、建议或未请求字段。

按 source_type 使用字段全集：{schemas}
两类文书除planned_procedure外，每项均返回对象：{{"state":"present|missing|unknown","span_id":"本doc单个片段编号或null","reviewed_all_sections":true或false}}。planned_procedure专用合同为{{"state":"present|missing|unknown","quote":"最小连续术式短引文或null","reviewed_all_sections":true或false}}，只摘录拟行手术名称及方式，不附带同句其他术式、病情或注意事项，保留原文，不得总结改写。
present必须选本doc能直接支持该项的单个span_id，不输出quote或重写原文；missing仅在检查该文书全部输入（正文、主持人小结、讨论建议及结构字段）后仍无对应内容时使用，span_id为null且reviewed_all_sections为true（planned_procedure的quote为null）。先通读本doc全部片段并核对候选依据，再选三态：完整核查后仅未找到对应内容，应返回missing；材料不全、无法完成核查、候选含义不明或上下文冲突时才返回unknown。unknown不是“尚未搜索”的替代，missing也不能由未完成核查推得。一个原文片段可以支持多个不同检查项，不因位于主持人小结就只能用于chair_summary。
九项定义：preop_preparation=已完成或拟实施的术前检查、准备及禁忌评估；surgical_indication=疾病、症状、保守治疗效果等手术理由；surgical_plan=拟行术式和方案；risk_and_prevention=可能风险及对应防范措施；participants_with_titles=参加者姓名及职称；specific_opinions=参加者具体讨论意见；chair_summary=主持人总结意见；discussion_date=讨论日期；recorder_signature=记录者签名。按内容识别，不要求固定栏目标题。
术前小结七项定义：brief_condition=患者本次手术相关的简要病情；preop_diagnosis=术前诊断；surgical_indication=拟行手术的理由或指征；planned_procedure=拟施手术名称和方式；planned_anesthesia=拟施麻醉方式；precautions=拟行手术相关的注意事项或具体防范措施，可位于手术要点等段落；合适的术式常规具体措施也可支持该项，不要求患者个体独有；surgeon_preop_visit=术者术前查看患者的情况。按完整内容语义识别，不按固定栏目标题或单个注意词判存在，不能把泛称“手术要点”或空标题当内容。
字段语义边界：surgeon_preop_visit核对术者已经查看患者的情况，必须有相应行为及患者情况的叙述依据；仅有医师签名或参加名单不能证明已经查看，拟查看、请术者查看不能证明已经查看。签名只说明署名，不推断查看行为；通读后无对应叙述按上述三态处理。
preop_diagnosis核对医生在本次手术前对患者疾病的诊断表述，不要求专名栏目或固定措辞；其他栏目中的明确诊断，或医生结合检查明确采纳为本次术前诊断，均可作为依据。单独的影像所见、检查提示或既往诊断不能自动等同本次术前诊断；应结合完整上下文区分医生诊断与检查发现，归属确实不清时保留unknown，不强行补成诊断。
片段编号合法只证明引用来自本doc，不证明它支持这个字段；引用须结合完整上下文核对其所支持的内容。
每个present仅选一个能直接支持该项的最小连续片段编号；不得返回多个ID或拼接编号，其他文书的ID不能引用，不得输出自由引文。不同字段可共用同一个编号。按完整ordered spans顺序通读原文，核对上下文、否定和跨句关系，不能把片段脱离完整语境作判断；一个片段不足以确认时返回unknown且span_id=null，不能组合片段。planned_procedure仍按上述短quote例外。只有reviewed_all_sections=true且确认该项未记载时可返回missing；语义仍由你抽取，不能用null表示确认缺项。
讨论日期只指日期是否已记录，不判断讨论及时性；输入中的同文书“讨论日期”结构投影也必须核对，不可因正文未重复日期报missing。
specific_opinions是参加讨论者的具体意见，chair_summary是主持人总结，两者分别抽取；仅有参加人员名单、拟行术式或主持人同意手术，不能代替具体讨论意见。“略”、空白和仅有栏目标题不算实质内容；完整核查确认无对应内容才返回missing，不能确定时返回unknown。
只输出 JSON：{response_example}。

文书：
{rendered}"""


def _field_value_valid(source: str, quote: Any, original: str) -> bool:
    """单个字段值的形状与原文校验；不修复、不改写模型输出。"""

    if isinstance(quote, Mapping):
        if set(quote) != {"state", "quote", "reviewed_all_sections"}:
            return False
        state, excerpt = quote["state"], quote["quote"]
        if not isinstance(state, str) or state not in {"present", "missing", "unknown"} or type(quote["reviewed_all_sections"]) is not bool:
            return False
        if state == "present":
            return isinstance(excerpt, str) and bool(clean_text(excerpt)) and clean_text(excerpt) in original
        return excerpt is None and not (state == "missing" and not quote["reviewed_all_sections"])
    if quote is None:
        return True
    return isinstance(quote, str) and bool(clean_text(quote)) and clean_text(quote) in original


@dataclass(frozen=True)
class _ValidatedResponse:
    """共享抽取响应按规则隔离后的校验结果。

    - 整体结构错误、文书身份不在本病例输入中、重复身份：整份响应拒绝（返回 None）；
    - 某份文书的字段集合不符（文书级）或字段值/引文不合格（字段级）：只使该文书所属
      规则失败，失败规则不得被判合规，也不把失败字段改写为 unknown；
    - 某规则所需文书缺失（覆盖不全）：只使该规则失败。
    本模块的抽取不含事件归属字段，事件关联由 Python 在通过校验的事实上确定。
    """

    parsed: dict[tuple[str, str], Mapping[str, Any]]
    rule_failures: dict[str, tuple[str, tuple[str, ...]]]


def _validate_response(
    payload: Mapping[str, Any],
    expected: Mapping[tuple[str, str], str],
    selected: Sequence[str],
) -> _ValidatedResponse | None:
    raw = payload.get("documents")
    if not isinstance(raw, list):
        return None
    parsed: dict[tuple[str, str], Mapping[str, Any]] = {}
    span_catalog = {key: _document_spans(text, index) for index, (key, text) in enumerate(expected.items(), start=1)}
    seen: set[tuple[str, str]] = set()
    failures: dict[str, tuple[str, tuple[str, ...]]] = {}

    def fail(rule: str, scope: str, fields: Sequence[str] = ()) -> None:
        previous = failures.get(rule)
        merged = tuple(dict.fromkeys((*(previous[1] if previous else ()), *fields)))
        # 文书级失败优先于字段级（影响范围更大）。
        failure_scope = "document" if scope == "document" or (previous and previous[0] == "document") else scope
        failures[rule] = (failure_scope, merged)

    for item in raw:
        if not isinstance(item, Mapping):
            return None
        doc_id, source = (
            clean_text(item.get("document_id")),
            clean_text(item.get("source_type")),
        )
        key = (source, doc_id)
        original = expected.get(key)
        rule_id = next((rule for rule in selected if RULE_SOURCES[rule] == source), "")
        if not original or not rule_id or key in seen:
            return None
        seen.add(key)
        facts = item.get("items")
        if not isinstance(facts, Mapping) or set(facts) != set(RULE_FIELDS[rule_id]):
            fail(rule_id, "document")
            continue
        facts = {field: _resolve_span_fact(value, span_catalog[key], field) for field, value in facts.items()}
        invalid = [
            field
            for field, quote in facts.items()
            if not _field_value_valid(source, quote, original)
        ]
        if invalid:
            fail(rule_id, "field", invalid)
            continue
        parsed[key] = facts
    for rule_id in selected:
        required = {key for key in expected if key[0] == RULE_SOURCES[rule_id]}
        if rule_id not in failures and not required <= set(parsed):
            fail(rule_id, "document")
    return _ValidatedResponse(
        parsed={
            key: facts
            for key, facts in parsed.items()
            if next(rule for rule in selected if RULE_SOURCES[rule] == key[0]) not in failures
        },
        rule_failures=failures,
    )


def _validated_items(
    payload: Mapping[str, Any],
    expected: Mapping[tuple[str, str], str],
    selected: Sequence[str],
) -> dict[tuple[str, str], Mapping[str, Any]] | None:
    """兼容入口：任一规则失败即返回 None（与旧语义一致）。"""

    validated = _validate_response(payload, expected, selected)
    if validated is None or validated.rule_failures:
        return None
    return validated.parsed if set(validated.parsed) == set(expected) else None


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


def _field_state(value: Any) -> str:
    """兼容已核验的旧引文；旧null没有确认缺失声明，仅表示未确定。"""

    if isinstance(value, Mapping):
        return str(value["state"])
    return "unknown" if value is None else "present"


def _field_quote(value: Any) -> Any:
    return value.get("quote") if isinstance(value, Mapping) else value


# 用户口径（2026-10-11）：078“术者术前查看患者”一项，认可同一台手术、手术开始前完成的
# 《术前主刀医师查房记录》；其余六项仍只看术前小结。查房时限由 064 单独核对，此处不卡24小时。
PREOP_SURGEON_ROUND_SOURCE = "senior_course_record"
_PREOP_SURGEON_ROUND_TITLE = re.compile(r"术前.{0,4}(?:主刀|术者).{0,16}查房|(?:主刀|术者).{0,16}术前.{0,4}查房")


def _preop_surgeon_round_events(
    events: Sequence[SurgeryEvent], round_rows: Sequence[Mapping[str, Any]],
) -> frozenset[int]:
    """返回有术前主刀查房记录覆盖的手术事件序号。

    查房完成时间须早于该台手术开始，且晚于上一台手术开始（否则属于上一台）；
    任一相关手术缺可靠开始时间时不作归属，保持原判定。
    """

    ordered = [(event, surgery_event_begin_time(event)) for event in events]
    covered: set[int] = set()
    for row in round_rows:
        if not _PREOP_SURGEON_ROUND_TITLE.search(clean_text(row.get("document_title"))):
            continue
        if not clean_text(row.get("record_content")):
            continue
        done = _document_record_time({"record_time": authoritative_document_time_value(row)})
        if done is None:
            continue
        previous: datetime | None = None
        for event, begin in sorted(ordered, key=lambda item: item[1] or datetime.max):
            if begin is None:
                break
            if done < begin and (previous is None or done > previous):
                covered.add(event.event_index)
                break
            previous = begin
    return frozenset(covered)


def _field_is_present(rule_id: str, row: Mapping[str, Any], values: Mapping[str, Any], field: str) -> bool:
    return _has_structured_field(rule_id, row, field) or _field_state(values[field]) == "present"


def _uncertain_fields_for_document(rule_id: str, row: Mapping[str, Any], values: Mapping[str, Any]) -> set[str]:
    return {
        field for field in RULE_FIELDS[rule_id]
        if not _has_structured_field(rule_id, row, field) and _field_state(values[field]) == "unknown"
    }


def _missing_fields_for_document(
    *, rule_id: str, row: Mapping[str, Any], values: Mapping[str, Any]
) -> set[str]:
    return {
        field for field in RULE_FIELDS[rule_id]
        if not _has_structured_field(rule_id, row, field) and _field_state(values[field]) == "missing"
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
    preop_round_events: frozenset[int] = frozenset(),
) -> tuple[set[str], bool, list[Mapping[str, Any]], set[str], set[str]]:
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
                and not _has_structured_field(rule_id, row, field)
                for field, value in values.items()
            ):
                ambiguous_values.append(values)
            grouped.setdefault(document_index, []).append((row, values))
        else:
            association = associate_preop_document_to_surgery_event(
                events=events,
                procedure_name=_procedure_name_for_association(
                    _field_quote(values.get("planned_procedure")), _text
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
                **({"uncertain_fields": sorted(unknown)} if rule_id == "LX0609-04-01-04"
                   and (unknown := _uncertain_fields_for_document(rule_id, row, values)) else {}),
            }
        )

    confirmed_missing: set[str] = set()
    pending_fields: set[str] = set()
    content_uncertain: set[str] = set()
    if rule_id == "LX0609-04-01-04":
        # 保留原同事件合并：只有明确present可覆盖同事件的另一份文书，unknown不能补齐。
        for group_key, documents in grouped.items():
            for field in RULE_FIELDS[rule_id]:
                if any(_field_is_present(rule_id, row, values, field) for row, values in documents):
                    continue
                if field == "surgeon_preop_visit" and group_key in preop_round_events:
                    continue
                unknown = any(_field_state(values[field]) == "unknown" for _row, values in documents)
                if unknown:
                    content_uncertain.add(field)
                if any(_field_is_present(rule_id, row, values, field) for row, values in ambiguous_documents):
                    pending_fields.add(field)
                    continue
                if unknown or any(_field_state(values[field]) == "unknown" for _row, values in ambiguous_documents):
                    content_uncertain.add(field)
                    continue
                confirmed_missing.add(field)
        if not grouped:
            for row, values in ambiguous_documents:
                content_uncertain.update(_uncertain_fields_for_document(rule_id, row, values))
        # 另一事件确认缺项仍成立；对应文书unknown已在documents保留，不被全局present删除。
        pending_fields -= confirmed_missing
        content_uncertain -= confirmed_missing
    else:
        # 讨论记录逐份自洽，结构化日期/签名仅能覆盖同一来源行的对应字段。
        for documents in grouped.values():
            for row, values in documents:
                confirmed_missing.update(_missing_fields_for_document(rule_id=rule_id, row=row, values=values))

    return confirmed_missing, bool(ambiguous_values), display_documents, pending_fields, content_uncertain


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
    if len(expected) != len(documents):
        # 重复同源身份不能确定编号所属正文；与整体身份错误一致，拒绝本次抽取。
        return PreopContentExecution(tuple(
            terminal.get(rule) or _decision(
                snapshot, rule, "data_gap", "source_readiness_unproven",
                tuple(ref for ref, _, _ in records[rule]),
            ) for rule in selected
        ))
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
    validated = _validate_response(payload, expected, active) if payload else None
    parsed = validated.parsed if validated is not None else None
    rule_failures = validated.rule_failures if validated is not None else {}
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
    preop_round_events: frozenset[int] = frozenset()
    if "LX0609-04-01-04" in active and events:
        try:
            round_rows = tuple(
                row for _ref, row in materials.document_rows(PREOP_SURGEON_ROUND_SOURCE, snapshot=snapshot)
            )
        except (EvidenceMaterialTruncated, EvidenceMaterialUnavailable):
            # 查房来源不可用只是少一条补证途径，不改变术前小结本身的判定。
            round_rows = ()
        preop_round_events = _preop_surgeon_round_events(events, round_rows)
    if preop_round_events:
        event_refs = (*event_refs, *_observation_refs(snapshot, PREOP_SURGEON_ROUND_SOURCE))
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
        if rule in rule_failures:
            # 本规则所需事实未通过校验：如实返回资料不足，不改写为 unknown，
            # 不判合规；无效引文不进入公开事实或证据（证据只引用文书本身）。
            failure_scope, invalid_fields = rule_failures[rule]
            decisions.append(
                _decision(snapshot, rule, "data_gap", "required_field_missing", refs)
            )
            display.append(
                (
                    rule,
                    {
                        "verification_kind": "preop_fact_extraction_invalid",
                        "target_document": RULE_SOURCES[rule],
                        "checked_fields": list(RULE_FIELDS[rule]),
                        "missing_fields": [],
                        "documents": [],
                        "failure_scope": failure_scope,
                        "invalid_fields": [
                            field for field in RULE_FIELDS[rule] if field in invalid_fields
                        ],
                    },
                )
            )
            continue
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
        missing, has_ambiguous, documents, pending, summary_uncertain = _association_state_for_rule(
            rule_id=rule,
            records=records[rule],
            parsed=parsed,
            events=events or (),
            preop_round_events=preop_round_events if rule == "LX0609-04-01-04" else frozenset(),
        )
        if (has_ambiguous or summary_uncertain) and not missing:
            status, reason = "data_gap", (
                "source_readiness_unproven" if rule == "LX0609-04-01-05" or summary_uncertain else "association_failed"
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
        # 079的字段unknown与手术归属无关；仅公开待确认字段，不伪造关联状态。
        uncertain_fields = sorted({
            field
            for _ref, row, _text in records[rule]
            for field, value in parsed[(RULE_SOURCES[rule], _document_id(row))].items()
            if (value is None or isinstance(value, Mapping) and value.get("state") == "unknown")
            and not _has_structured_field(rule, row, field)
        }) if rule == "LX0609-04-01-05" and status == "data_gap" else sorted(summary_uncertain)
        display.append(
            (
                rule,
                {
                    "verification_kind": (
                        "preop_discussion_content_uncertain"
                        if rule == "LX0609-04-01-05" and status == "data_gap"
                        else "preop_summary_content_uncertain"
                        if rule == "LX0609-04-01-04" and status == "data_gap" and summary_uncertain
                        else "preop_surgery_association_ambiguous"
                        if status == "data_gap"
                        else "preop_content_complete"
                        if not missing
                        else "preop_content_incomplete"
                    ),
                    "target_document": RULE_SOURCES[rule],
                    "checked_fields": list(RULE_FIELDS[rule]),
                    "missing_fields": sorted(missing),
                    "documents": documents,
                    **({"uncertain_fields": uncertain_fields} if uncertain_fields else {}),
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
