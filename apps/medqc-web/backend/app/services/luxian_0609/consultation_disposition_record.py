"""只核对申请科室如何记载会诊意见的处置，不读取医嘱或推断实际执行。"""

from __future__ import annotations

from dataclasses import dataclass
import json
import logging
import re
from time import perf_counter
from typing import Any, Mapping, Sequence

from .llm_prompt_privacy import describe_luxian_0609_llm_parse_failure, redact_luxian_0609_patient_privacy
from .structured_output import structured_output_kwargs
from .transfusion_order_trigger import _json_response_object, _usage


logger = logging.getLogger(__name__)

RULE_ID = "LX0609-03-01-05"
SCHEMA_VERSION = "consultation-disposition-record-v2"
_KINDS = frozenset(
    {"performed", "planned", "declined", "generic", "missing", "unknown"}
)
_SPECIFIC = frozenset({"performed", "planned", "declined"})
_GENERIC = re.compile(
    r"^(?:以上|均|已|予以|予|现|其余|余|全部|一律|处理|治疗|继续|遵执|遵照|遵嘱|遵医嘱|遵会诊意见|遵意见|执行|按会诊意见|按意见|落实|办理|照办|同前|上述治疗|当前治疗|方案|康复理疗|康复治疗|对症|[，,。；;：:！!\s])+$"
)
_GENERIC_REMAINDER = re.compile(
    r"(?:其余|其他|余下|余)(?:建议|意见|处理|治疗)?(?:均|已|予以|予)?(?:遵嘱|遵照|遵医嘱|遵会诊意见|按会诊意见|按建议)"
)


@dataclass(frozen=True)
class DispositionRecordOutcome:
    status: str
    reason: str
    fact_refs: tuple[str, ...] = ()
    llm_call_count: int = 0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    api_time: float = 0.0


def _normalized(value: str) -> str:
    return re.sub(r"\s+", "", value)


_MIN_SPLIT_SEGMENT_CHARS = 4


def _split_into_source_segments(quote: str, source: str) -> list[str] | None:
    """把模型拼接的引文按原文顺序拆回若干逐字连续片段；无法完整拆分时返回 None。

    模型偶尔把被其他文字隔开的两段意见拼成一条引文（中间跳过本科室回应）。
    每段都从原文逐字截取、按位置递增且不少于 4 字，不接受原文没有的任何文字，
    只把一条拼接引文还原为多条连续引文，引文须逐字来自原文的合同不变。
    """

    positions = [index for index, char in enumerate(source) if not char.isspace()]
    compact_source = "".join(source[index] for index in positions)
    compact_quote = _normalized(quote)
    if not compact_quote or not compact_source:
        return None
    segments: list[str] = []
    quote_at = source_at = 0
    while quote_at < len(compact_quote):
        best_start, best_length = -1, 0
        # 在已用位置之后寻找能匹配的最长前缀，保证片段顺序与原文一致。
        for length in range(len(compact_quote) - quote_at, _MIN_SPLIT_SEGMENT_CHARS - 1, -1):
            found = compact_source.find(compact_quote[quote_at:quote_at + length], source_at)
            if found >= 0:
                best_start, best_length = found, length
                break
        if best_length < _MIN_SPLIT_SEGMENT_CHARS:
            return None
        start, end = positions[best_start], positions[best_start + best_length - 1] + 1
        segments.append(source[start:end])
        quote_at += best_length
        source_at = best_start + best_length
    return segments if len(segments) > 1 else None


def _restore_contiguous_quotes(quotes: Any, source: str) -> Any:
    """仅对不在原文中的拼接引文尝试拆分；其他输入原样返回交由原校验处理。"""

    if not isinstance(quotes, list):
        return quotes
    restored: list[Any] = []
    for quote in quotes:
        if isinstance(quote, str) and quote and _normalized(quote) not in _normalized(source):
            segments = _split_into_source_segments(quote, source)
            if segments is not None:
                restored.extend(segments)
                continue
        restored.append(quote)
    return restored


def _grounded(quote: str, source: str) -> bool:
    return bool(
        quote and len(quote) <= 240 and _normalized(quote) in _normalized(source)
    )


def _model_documents(
    documents: Sequence[Mapping[str, str]],
) -> tuple[dict[str, str], ...]:
    """Prompt 与引文核验共用同一模型可见文本；原材料引用仍由外层绑定。"""
    return tuple(
        {
            **{key: document[key] for key in ("ref", "time") if key in document},
            "text": redact_luxian_0609_patient_privacy(document["text"]),
        }
        for document in documents
    )


_ACTION_GROUPS = ("medications", "examinations", "therapies", "other_actions")


def _required_followups(opinions: Sequence[str]) -> tuple[str, ...]:
    """显式复查项目必须单独核对；不据此推断是否执行或触发条件。"""
    targets = []
    for opinion in opinions:
        for clause in re.split(r"[，,；;。]", opinion):
            for match in re.finditer(r"复查([^，,；;。]{1,80})", clause):
                if re.search(
                    r"必要时|酌情|若|如|视情况|无需|无须|不必|不需|不用|暂不|不再",
                    clause[: match.start()],
                ):
                    continue
                tail = re.split(
                    r"以便|以|了解|明确|评估|根据|结合|后|并|再", match[1], maxsplit=1
                )[0]
                targets.extend(
                    name.strip() for name in re.split(r"[、及]", tail) if name.strip()
                )
    return tuple(dict.fromkeys(targets))


def build_prompt(documents: Sequence[Mapping[str, Any]]) -> str:
    return (
        "逐项核对会诊意见的书面处置，不判断医嘱或实际执行。输入已分开会诊医师意见和本科室反馈。\n"
        "分别扫描四类动作：medications用药，examinations检查检验和复查，therapies具体治疗操作，"
        "other_actions会诊、随访及其他具体安排。每个独立动作列一项，不能遗漏没有反馈的建议。\n"
        "给予某药一周后复查CT有两个动作：给药属于medications，复查CT属于examinations；"
        "只记录加药不能证明已写复查安排。同一治疗的部位、穴位、剂量和目的不是独立动作；"
        "required_followups列出了意见中显式提出的复查项目，须逐项放入examinations核对；不能并进medications。"
        "明确二选一方案按一项核对，具体选择其中一种即可。必要时等触发条件不明的动作不纳入。\n"
        "每项action_quote取opinion_quotes中的连续原话，不超过240字；feedback_quote只取feedback_quotes中"
        "与该项对应的连续反馈原话。严禁用会诊医师的建议证明本科室已经记载处置。\n"
        "feedback_kind取performed/planned/declined/generic/missing/unknown：具体处理为performed，明确具体安排为planned，"
        "写明不采纳或暂缓项目及原因（包括患者拒绝）为declined；只写遵照执行、对症治疗、康复理疗为generic；"
        "完全未说明该项处置为missing，无法对应为unknown。安排不代表已经执行。\n"
        "继续上述药物治疗仅在所指方案唯一明确时可计入，referent_quote摘所指原话，否则为空。"
        "所有引文不超过240字，不得拼接或改写。missing的feedback_quote为空；generic须引用笼统回应；"
        "generic/missing/unknown的referent_quote为空。\n"
        "每个ref恰好一次，每项动作只放一类；非目标或无建议时四类均为空数组。"
        "\nROLE_FACTS_JSON="
        + json.dumps(
            [
                {**d, "required_followups": _required_followups(d["opinion_quotes"])}
                for d in documents
            ],
            ensure_ascii=False,
            separators=(",", ":"),
        )
        + "\n资料结束。现在只输出以下结构的JSON对象，保持字段名，不返回说明或其他结构："
        f'{{"schema_version":"{SCHEMA_VERSION}","documents":['
        '{"ref":"输入ref","medications":[],"examinations":[],"therapies":[],"other_actions":['
        '{"action_quote":"建议原话","feedback_quote":"反馈原话","feedback_kind":"generic","referent_quote":""}]}]}。'
    )


def _payload(response: Mapping[str, Any]) -> Any:
    choices = response.get("choices")
    if choices is not None:
        if choices[0].get("finish_reason") not in {None, "stop"}:
            raise ValueError("incomplete response")
        content = choices[0]["message"]["content"]
    else:
        content = response.get("content", response.get("text"))
    return _json_response_object(content)


def _in_quotes(quote: str, sources: Sequence[str]) -> bool:
    return any(_grounded(quote, source) for source in sources)


def parse_facts(
    response: Mapping[str, Any],
    documents: Sequence[Mapping[str, str]],
    roles: Mapping[str, Mapping[str, Any]],
) -> tuple[str, str, tuple[str, ...]]:
    """身份和覆盖仍整批严格校验；独立文书失败不能覆盖已核验的缺陷。"""
    payload = _payload(response)
    if (not isinstance(payload, dict)
        or set(payload) != {"schema_version", "documents"}
        or payload["schema_version"] != SCHEMA_VERSION
        or not isinstance(payload["documents"], list)):
        raise ValueError("invalid response schema")
    expected = {document["ref"]: document for document in documents}
    items = payload["documents"]
    if (not all(isinstance(item, dict) and isinstance(item.get("ref"), str) for item in items)
        or len(items) != len(expected)
        or {item["ref"] for item in items} != set(expected)):
        raise ValueError("incomplete document coverage")
    outcomes = []
    invalid = False
    for item in items:
        ref = item["ref"]
        try:
            outcomes.append(_parse_document_facts(
                {"content": json.dumps({"schema_version": SCHEMA_VERSION, "documents": [item]})},
                (expected[ref],), {ref: roles[ref]},
            ))
        except (ValueError, TypeError, KeyError, IndexError, AttributeError):
            invalid = True
    defects = tuple(dict.fromkeys(ref for status, _, refs in outcomes if status == "non_compliant" for ref in refs))
    if defects:
        return "non_compliant", "requirement_violated", defects
    if invalid:
        raise ValueError("invalid document facts")
    for state, reason in (("data_gap", "semantic_extraction_unresolved"), ("compliant", "requirement_satisfied")):
        refs = tuple(dict.fromkeys(ref for status, _, refs in outcomes if status == state for ref in refs))
        if any(status == state for status, _, _ in outcomes):
            return state, reason, refs
    return "not_applicable", "trigger_absent_complete", ()


def _parse_document_facts(
    response: Mapping[str, Any],
    documents: Sequence[Mapping[str, str]],
    roles: Mapping[str, Mapping[str, Any]],
) -> tuple[str, str, tuple[str, ...]]:
    payload = _payload(response)
    if (
        not isinstance(payload, dict)
        or set(payload) != {"schema_version", "documents"}
        or payload["schema_version"] != SCHEMA_VERSION
        or not isinstance(payload["documents"], list)
    ):
        raise ValueError("invalid response schema")
    sources = {d["ref"]: d["text"] for d in _model_documents(documents)}
    seen: set[str] = set()
    defects: list[str] = []
    applicable: list[str] = []
    unresolved = False
    for document in payload["documents"]:
        if not isinstance(document, dict) or set(document) != {"ref", *_ACTION_GROUPS}:
            raise ValueError("invalid document schema")
        ref = document["ref"]
        if not isinstance(ref, str) or ref not in sources or ref in seen:
            raise ValueError("invalid document identity")
        seen.add(ref)
        role = roles[ref]
        if not all(isinstance(document[group], list) for group in _ACTION_GROUPS):
            raise ValueError("invalid action groups")
        items = [(group, item) for group in _ACTION_GROUPS for item in document[group]]
        if role["scope"] != "ordinary" or role["suggestion_state"] != "present":
            if items:
                raise ValueError("unexpected action items")
            unresolved |= role["scope"] == "unknown" or (
                role["scope"] == "ordinary"
                and role["suggestion_state"] == "unavailable"
            )
            continue
        applicable.append(ref)
        if not items:
            unresolved = True
            continue
        if len(items) > 24:
            raise ValueError("too many action items")
        actions: set[str] = set()
        required_followups = _required_followups(role["opinion_quotes"])
        covered_followups: set[str] = set()
        for group, item in items:
            if (
                not isinstance(item, dict)
                or set(item)
                != {"action_quote", "feedback_quote", "referent_quote", "feedback_kind"}
                or not all(isinstance(value, str) for value in item.values())
            ):
                raise ValueError("invalid action schema")
            action, feedback, referent, kind = (
                item[key]
                for key in (
                    "action_quote",
                    "feedback_quote",
                    "referent_quote",
                    "feedback_kind",
                )
            )
            if kind not in _KINDS:
                unresolved = True
                continue
            if not _in_quotes(action, role["opinion_quotes"]):
                # 本科室后来新增的安排不属于本次会诊建议，不要求再次回应。
                unresolved |= not _in_quotes(action, role["feedback_quotes"])
                continue
            if (
                _in_quotes(action, role["feedback_quotes"])
                and _normalized(sources[ref]).count(_normalized(action)) < 2
            ):
                # 同一处本科室回应不能再被当作一条新会诊建议报告缺项。
                unresolved = True
                continue
            if "复查" in action and (
                group == "medications"
                or re.search(r"(?:给予|加用|服用|停用).+复查", action)
            ):
                unresolved = True
                continue
            if group == "examinations":
                covered_followups.update(
                    target
                    for target in required_followups
                    if _normalized(target) in _normalized(action)
                )
            key = _normalized(action)
            if key in actions:
                raise ValueError("duplicate action")
            actions.add(key)
            if (feedback and not _in_quotes(feedback, role["feedback_quotes"])) or (
                referent and not _in_quotes(referent, role["opinion_quotes"])
            ):
                unresolved = True
                continue
            if (
                feedback
                and _in_quotes(feedback, role["opinion_quotes"])
                and _normalized(sources[ref]).count(_normalized(feedback)) < 2
            ):
                unresolved = True
                continue
            if feedback and (
                _GENERIC.fullmatch(_normalized(feedback))
                or _GENERIC_REMAINDER.search(_normalized(feedback))
            ):
                defects.append(ref)
                continue
            if kind in _SPECIFIC:
                if not feedback:
                    unresolved = True
                    continue
            elif referent:
                unresolved = True
                continue
            if (kind == "generic" and not feedback) or (kind == "missing" and feedback):
                unresolved = True
                continue
            if kind in {"generic", "missing"}:
                defects.append(ref)
            unresolved |= kind == "unknown"
        unresolved |= not actions or set(required_followups) != covered_followups
    if seen != set(sources):
        raise ValueError("incomplete document coverage")
    if defects:
        return "non_compliant", "requirement_violated", tuple(dict.fromkeys(defects))
    if unresolved:
        return "data_gap", "semantic_extraction_unresolved", tuple(applicable)
    if applicable:
        return "compliant", "requirement_satisfied", tuple(applicable)
    return "not_applicable", "trigger_absent_complete", ()


def build_opinion_prompt(documents: Sequence[Mapping[str, str]]) -> str:
    return (
        "从会诊执行记录中区分两种说话者，只摘原文，不拆动作、不判断是否执行。\n"
        "opinion_quotes：普通专科会诊医师提出的诊治建议原文段落；不摘病史检查结果或本科室反馈。"
        "feedback_quotes：本科室对上述意见的处置回应原文段落，包括遵照执行、已处理、拟安排、患者拒绝等。"
        "注意我科处理之后通常是本科室反馈；谢邀、我科愿随访通常仍为会诊医师结语。"
        "没有我科处理等标题也可能已转入本科室回应，不能把会诊意见如下之后的全部文字都当作会诊建议。"
        "例如会诊建议甲药纠正贫血、乙药补铁，随后写患者用乙药后腹泻、暂不使用、拟加用甲药治疗："
        "前半段属于意见，后半段从患者用药反应到拟加用治疗整段属于本科室的具体处置回应；"
        "即使没有已执行字样，也必须完整摘入feedback_quotes，不能将拟加用再列为新建议。"
        "相反，会诊医师自己说建议拟加用某药仍是opinion_quotes；不能仅凭拟、建议或药名判断说话者。"
        "两组引文在正文中的位置不得重叠；同一种药分别出现在建议和回应中时，应分别摘录对应位置。"
        "两组引文都必须是正文中的连续原话，不得拼接；分别不超过4000/2400字，每组最多8段。\n"
        "scope取ordinary/non_target/unknown：普通专科会诊为ordinary，术前邀请但有具体诊治意见也算；"
        "纯麻醉耐受评估、MDT、空模板和非会诊为non_target，归属无法识别为unknown。混合正文只摘普通专科部分。"
        "suggestion_state取present/unavailable/no_action：有具体建议、意见内容缺失、仅诊断或无需具体措施。"
        "仅ordinary且present填写opinion_quotes，其余两组均为空；找不到本科室回应时feedback_quotes为空。\n"
        "每个ref恰好返回一次，只输出JSON："
        f'{{"schema_version":"{SCHEMA_VERSION}-opinions","documents":['
        '{"ref":"输入ref","scope":"ordinary","suggestion_state":"present",'
        '"opinion_quotes":["会诊医师的建议段落"],"feedback_quotes":["本科室的处置回应段落"]}]}。'
        "\nDOCUMENTS_JSON="
        + json.dumps(
            _model_documents(documents), ensure_ascii=False, separators=(",", ":")
        )
    )


def parse_opinions(
    response: Mapping[str, Any], documents: Sequence[Mapping[str, str]]
) -> dict[str, Mapping[str, Any]]:
    payload = _payload(response)
    if (
        not isinstance(payload, dict)
        or set(payload) != {"schema_version", "documents"}
        or payload["schema_version"] != SCHEMA_VERSION + "-opinions"
        or not isinstance(payload["documents"], list)
    ):
        raise ValueError("invalid opinions schema")
    sources = {d["ref"]: d["text"] for d in _model_documents(documents)}
    output: dict[str, Mapping[str, Any]] = {}
    for item in payload["documents"]:
        if not isinstance(item, dict) or set(item) != {
            "ref",
            "scope",
            "suggestion_state",
            "opinion_quotes",
            "feedback_quotes",
        }:
            raise ValueError("invalid opinion document")
        ref, scope, state = item["ref"], item["scope"], item["suggestion_state"]
        if (
            not isinstance(ref, str)
            or ref not in sources
            or ref in output
            or scope not in {"ordinary", "non_target", "unknown"}
            or state not in {"present", "unavailable", "no_action"}
        ):
            raise ValueError("invalid opinion identity")
        for key, limit in (("opinion_quotes", 4000), ("feedback_quotes", 2400)):
            quotes = _restore_contiguous_quotes(item[key], sources.get(ref, ""))
            item = {**item, key: quotes}
            if (
                not isinstance(quotes, list)
                or len(quotes) > 8
                or not all(
                    isinstance(q, str)
                    and q
                    and len(q) <= limit
                    and _normalized(q) in _normalized(sources[ref])
                    for q in quotes
                )
                or len(set(map(_normalized, quotes))) != len(quotes)
            ):
                raise ValueError("role quotes not grounded")
        if scope == "ordinary" and state == "present":
            if not item["opinion_quotes"]:
                raise ValueError("missing opinion text")
        elif item["opinion_quotes"] or item["feedback_quotes"]:
            raise ValueError("unexpected role text")
        output[ref] = item
    if set(output) != set(sources):
        raise ValueError("incomplete opinion document coverage")
    return output


async def check_disposition_record(
    *, documents: Sequence[Mapping[str, str]], llm_client: Any
) -> DispositionRecordOutcome:
    if not documents:
        return DispositionRecordOutcome("not_applicable", "trigger_absent_complete")
    if llm_client is None:
        return DispositionRecordOutcome("data_gap", "semantic_extraction_unresolved")
    prompt = build_opinion_prompt(documents)
    if len(prompt) > 60000:
        return DispositionRecordOutcome("data_gap", "source_truncated")
    totals = [0, 0, 0]
    elapsed = 0.0
    frozen: dict[str, Mapping[str, Any]] = {}

    def extraction_failure(calls: int, reason: str) -> DispositionRecordOutcome:
        # 第一阶段角色和引文已严格核验；纯笼统回应无需再靠动作抽取证明。
        refs = tuple(ref for ref, role in frozen.items()
                     if role["scope"] == "ordinary" and role["suggestion_state"] == "present"
                     and role["feedback_quotes"] and all(
                         _GENERIC.fullmatch(_normalized(quote))
                         for quote in role["feedback_quotes"]))
        return DispositionRecordOutcome(
            "non_compliant" if refs else "technical_error",
            "requirement_violated" if refs else reason,
            refs, calls, *totals, elapsed,
        )

    for attempt in range(2):
        started = perf_counter()
        try:
            options = structured_output_kwargs(llm_client)
            if attempt == 1 and options:
                # 本点第二阶段已真实复验 JSON 对象模式；不改其他规则的输出策略。
                options["response_format"] = {"type": "json_object"}
            response = await llm_client.generate(
                redact_luxian_0609_patient_privacy(prompt),
                **options,
            )
        except Exception:
            elapsed += perf_counter() - started
            return extraction_failure(attempt + 1, "model_transport_error")
        elapsed += perf_counter() - started
        try:
            usage = _usage(response)
            totals = [total + int(value) for total, value in zip(totals, usage[:3])]
            if attempt == 0:
                frozen = parse_opinions(response, documents)
                if not any(
                    item["scope"] == "ordinary"
                    and item["suggestion_state"] == "present"
                    for item in frozen.values()
                ):
                    unresolved = any(
                        item["scope"] == "unknown"
                        or (
                            item["scope"] == "ordinary"
                            and item["suggestion_state"] == "unavailable"
                        )
                        for item in frozen.values()
                    )
                    status, reason = (
                        ("data_gap", "semantic_extraction_unresolved")
                        if unresolved
                        else ("not_applicable", "trigger_absent_complete")
                    )
                    return DispositionRecordOutcome(
                        status, reason, (), 1, *totals, elapsed
                    )
                prompt = build_prompt(tuple(frozen.values()))
                if len(prompt) > 60000:
                    return DispositionRecordOutcome(
                        "data_gap", "source_truncated", (), 1, *totals, elapsed
                    )
                continue
            status, reason, refs = parse_facts(response, documents, frozen)
            return DispositionRecordOutcome(status, reason, refs, 2, *totals, elapsed)
        except (ValueError, TypeError, KeyError, IndexError, AttributeError) as error:
            logger.warning(
                "LX0609 会诊处置记录抽取输出无效: stage=%s document_count=%s %s",
                "opinion" if attempt == 0 else "action",
                len(documents),
                describe_luxian_0609_llm_parse_failure(error, response),
            )
            return extraction_failure(attempt + 1, "model_invalid_output")
    return DispositionRecordOutcome(
        "data_gap",
        "semantic_extraction_unresolved",
        llm_call_count=2,
        prompt_tokens=totals[0],
        completion_tokens=totals[1],
        total_tokens=totals[2],
        api_time=elapsed,
    )


def safe_disposition_display_facts(raw: Any) -> dict[str, Any] | None:
    """只发布已核验的不具体处置文书数量，不携带原文或身份。"""
    if (not isinstance(raw, Mapping)
        or set(raw) != {"failure_kind", "unspecific_document_count"}
        or raw.get("failure_kind") != "consultation_disposition_unspecific"
        or type(raw.get("unspecific_document_count")) is not int
        or not 1 <= raw["unspecific_document_count"] <= 10000):
        return None
    return dict(raw)
