"""LX0609-05-01-01（028）Ⅰ、Ⅱ类切口手术预防用抗菌药物时长。

院方口径（2026-10-11，依据《抗菌药物临床应用指导原则（2015年版）》）：
- Ⅰ类切口心脏手术预防用药不超过48小时，其余Ⅰ、Ⅱ类切口不超过24小时；指导原则
  没有超过48小时的预防用药情形。
- 超过时限仍在用抗菌药物的：病程记录了感染相关客观证据的视为转为治疗用药，合规；
  未记录的不合规。高龄、糖尿病、手术创伤大、留置引流管不能作为延长理由。

程序负责：手术事件、切口等级、心脏手术、全身用抗菌药物识别、围术期用药链与时长。
模型只在超时后抽取感染事件、发生/记录时间、原文与逐台关联，程序校验引用、身份和覆盖。
时长从手术结束时刻计（缺结束时间时以开始时间计并在事实中标明）至围术期连续用药的
最后停用时刻；医嘱停止时间是必需字段，缺失时资料不足，不以更新时间替代。
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime, timedelta
import re
from typing import Any
from zoneinfo import ZoneInfo

from .extended_document.shared import order_repeat_kind
from .llm_prompt_privacy import redact_luxian_0609_patient_privacy
from .infection_surgery_extraction import (
    INFECTION_SURGERY_CONTRACT_VERSION,
    MAX_COMPLETION_TOKENS as MAX_COMPLETION_TOKENS,
    MAX_EVIDENCE_DOCUMENTS as MAX_EVIDENCE_DOCUMENTS,
    InfectionDocument, InfectionFacts, SurgeryIdentity, extract_infection_surgery_facts, private_infection_audit,
    freeze_completed_infection_facts,
)

RULE_ID = "LX0609-05-01-01"
SCHEMA_VERSION = INFECTION_SURGERY_CONTRACT_VERSION
MAX_DOCUMENT_CHARS = 3000
STOP_TIME_FIELDS = ("stop_datetime", "order_stop_datetime", "stop_time", "end_datetime")
_START_TIME_FIELDS = ("planned_start_datetime", "start_time", "prescribed_datetime", "order_time")
_PERIOPERATIVE_WINDOW = timedelta(hours=24)
_CHAIN_GAP = timedelta(hours=24)
_HOSPITAL_TIMEZONE = ZoneInfo("Asia/Shanghai")

# 全身用抗菌（抗细菌）药物：按通用名词干识别；抗肿瘤抗生素、抗真菌药、免疫抑制剂排除。
_ANTIBACTERIAL = re.compile(
    r"西林|头孢|培南|曲南|霉素|沙星|硝唑|环素|磺胺|唑胺|拉宁|[黏粘]菌素|磷霉素|夫西地酸|"
    r"呋喃妥因|呋喃唑酮|米星|卡星|巴坦|甲氧苄啶|利福|达托"
)
_NON_ANTIBACTERIAL = re.compile(
    r"比星|博来霉素|丝裂霉素|放线菌素|平阳霉素|普卡霉素|光辉霉素|制霉菌素|两性霉素|"
    r"雷帕霉素|西罗莫司|他克莫司"
)
# 外用、局部及吸入制剂不计入全身预防用药。
_NON_SYSTEMIC = re.compile(r"外用|滴眼|眼膏|眼用|滴耳|耳用|软膏|乳膏|凝胶|栓|含漱|阴道|局部|涂|雾化|冲洗")
_SINGLE_DOSE = re.compile(r"^(?:st|stat|once|立即|术中|一次)$", re.IGNORECASE)
_CANCELLED = re.compile(r"取消|作废|撤销")
_INCISION_LABEL = re.compile(
    r"切口(?:等级|类别|分类|类型)\s*[:：]?\s*(?P<value>Ⅰ|Ⅱ|Ⅲ|Ⅳ|IV|III|II|I|[0-4]|[一二三四])\s*类?"
)
_CARDIAC_CODE = re.compile(r"^\s*3[5-7]\.")
_CARDIAC_NAME = re.compile(r"心脏|瓣膜置换|瓣膜成形|冠状动脉旁路|冠脉搭桥|房间隔|室间隔|法洛")
_PURPOSE_SEGMENT = re.compile(r"[。！？!?；;\r\n]+")
_PROPHYLACTIC_PURPOSE = re.compile(r"预防|防治")
_SPECIFIC_INFECTION = (
    r"(?:肺部感染|肺炎|呼吸道感染|尿路感染|泌尿系感染|腹腔感染|胆道感染|切口感染|"
    r"血流感染|导管相关感染|败血症|脓毒症)"
)
_THERAPEUTIC_ACTION = r"(?:予|给予|使用|应用|选用|改用|继续使用|建议使用|建议)"
_NEGATED_INFECTION = rf"(?:未见|排除|未提示|不考虑|无).{{0,4}}{_SPECIFIC_INFECTION}"
_NEGATED_DRUG_ACTION = r"(?:停用|未使用|未予|未给予|不使用|无需使用|暂不使用)"
_DRUG_NAME_PARENS = re.compile(r"[（(][^（）()]*[）)]")
_DRUG_NAME_PREFIX = re.compile(r"^(?:注射用|口服|静脉滴注用|静滴用)+")
_DRUG_NAME_SUFFIX = re.compile(
    r"(?:氯化钠注射液|葡萄糖注射液|注射液|冻干粉针剂?|粉针剂?|颗粒剂?|胶囊剂?|片剂?|"
    r"分散片|缓释片|肠溶片|盐酸盐|盐酸|钠盐|钠)$"
)


@dataclass(frozen=True)
class SurgeryEventInput:
    begin: datetime | None
    end: datetime | None
    incision_class: str  # "I" / "II" / "outside" / "unknown"
    cardiac: bool
    identity: SurgeryIdentity | None = None


@dataclass(frozen=True)
class ProphylaxisOutcome:
    status: str
    reason_code: str
    display_facts: Mapping[str, Any] | None = None
    order_rows: tuple[Mapping[str, Any], ...] = ()
    course_rows: tuple[tuple[str, Mapping[str, Any]], ...] = ()
    llm_call_count: int = 0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    api_time: float = 0.0
    diagnostic_semantic_snapshot: Mapping[str, Any] | None = field(default=None, repr=False)


@dataclass
class _EventResult:
    status: str
    reason_code: str
    facts: dict[str, Any] = field(default_factory=dict)
    orders: tuple[Mapping[str, Any], ...] = ()
    anchor: datetime | None = None
    last_use: datetime | None = None
    # 链内有长期医嘱缺停止时间时，last_use 只是已证明的下限，实际停药时刻未知。
    stop_unknown: bool = False


def _clean(value: Any) -> str:
    return re.sub(r"\s+", "", str(value or ""))


def parse_time(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        return value if value.tzinfo is None else value.astimezone(_HOSPITAL_TIMEZONE).replace(tzinfo=None)
    text = str(value or "").strip()
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}(?::\d{2}(?:\.\d+)?)?(?:Z|[+-]\d{2}(?::?\d{2})?)?", text):
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo is None else parsed.astimezone(_HOSPITAL_TIMEZONE).replace(tzinfo=None)


def incision_class_value(value: Any) -> str:
    """病案首页/手术记录切口等级归一；0 类（自然腔道、经皮腔镜）及Ⅲ、Ⅳ类不在本条范围。"""

    text = _clean(value).upper().rstrip("类")
    if text in {"Ⅰ", "I", "1", "一"}:
        return "I"
    if text in {"Ⅱ", "II", "2", "二"}:
        return "II"
    if text in {"Ⅲ", "III", "3", "三", "Ⅳ", "IV", "4", "四", "0"}:
        return "outside"
    return "unknown"


def incision_class_from_text(text: Any) -> str:
    values = {incision_class_value(item["value"]) for item in _INCISION_LABEL.finditer(str(text or ""))}
    return next(iter(values)) if len(values) == 1 else "unknown"


def is_cardiac_surgery(codes: Sequence[Any], names: Sequence[Any]) -> bool:
    return any(_CARDIAC_CODE.match(str(code or "")) for code in codes) or any(
        _CARDIAC_NAME.search(_clean(name)) for name in names
    )


def is_local_route_drug_order(row: Mapping[str, Any]) -> bool:
    """滴眼、外用、冲洗、雾化等局部用药（药名或给药途径）；用户口径：局部用药不算抗菌药使用。"""

    name = _clean(" ".join(str(row.get(key) or "") for key in ("generic_name", "brand_name", "order_name")))
    return bool(_NON_SYSTEMIC.search(name + _clean(row.get("drug_apply_method"))))


def is_systemic_antibacterial(row: Mapping[str, Any]) -> bool:
    if _CANCELLED.search(str(row.get("order_status") or "")):
        return False
    name = _clean(" ".join(str(row.get(key) or "") for key in ("generic_name", "brand_name", "order_name")))
    route = _clean(row.get("drug_apply_method"))
    return bool(
        _ANTIBACTERIAL.search(name)
        and not _NON_ANTIBACTERIAL.search(name)
        and not _NON_SYSTEMIC.search(name + route)
    )


def order_start(row: Mapping[str, Any]) -> datetime | None:
    return next((value for key in _START_TIME_FIELDS if (value := parse_time(row.get(key))) is not None), None)


def order_stop(row: Mapping[str, Any]) -> datetime | None:
    """临时/单次医嘱以开始时刻为止；长期医嘱必须有停止时间，不以更新时间替代。"""

    start = order_start(row)
    if order_repeat_kind(row) == "temporary" or _SINGLE_DOSE.fullmatch(
        _clean(row.get("drug_frequency"))
    ):
        return start
    return next((value for key in STOP_TIME_FIELDS if (value := parse_time(row.get(key))) is not None), None)


def _drug_name_aliases(row: Mapping[str, Any]) -> tuple[str, ...]:
    """生成足够具体的药名别名，只用于把目的表述绑定到单条药品医嘱。"""

    aliases: list[str] = []
    for key in ("generic_name", "brand_name", "order_name"):
        name = _clean(row.get(key))
        if not name:
            continue
        without_parens = _DRUG_NAME_PARENS.sub("", name)
        base = _DRUG_NAME_PREFIX.sub("", without_parens)
        previous = ""
        while base != previous:
            previous = base
            base = _DRUG_NAME_SUFFIX.sub("", base)
        for candidate in (without_parens, base):
            if len(candidate) >= 4 and candidate not in aliases:
                aliases.append(candidate)
    return tuple(aliases)


def _linked_name_fragments(text: Any, aliases: Sequence[str]) -> tuple[str, ...]:
    """截取药名附近的目的表述，避免同句另一种药的感染用途串到本药。"""

    compact = _clean(text)
    fragments: list[str] = []
    for alias in aliases:
        offset = 0
        while (index := compact.find(alias, offset)) >= 0:
            fragment = compact[max(index - 20, 0):index + len(alias) + 20]
            if fragment not in fragments:
                fragments.append(fragment)
            offset = index + len(alias)
    return tuple(fragments)


def _purpose_texts_for_order(
    row: Mapping[str, Any],
    course_rows: Sequence[tuple[str, Mapping[str, Any]]],
) -> tuple[str, ...]:
    """只收集与该药名明确同句、且时间邻近该医嘱的目的表述。"""

    aliases = _drug_name_aliases(row)
    if not aliases:
        return ()
    start = order_start(row)
    stop = order_stop(row)
    texts: list[str] = []
    order_text = str(row.get("record_content") or "")
    for segment in _PURPOSE_SEGMENT.split(order_text):
        texts.extend(_linked_name_fragments(segment, aliases))
    if start is None:
        return tuple(texts)
    lower = start - _CHAIN_GAP
    upper = (stop or start + timedelta(hours=72)) + _CHAIN_GAP
    for _key, course_row in course_rows:
        course_time = parse_time(
            course_row.get("record_time") or course_row.get("record_datetime")
            or course_row.get("submit_datetime") or course_row.get("submit_time")
        )
        if course_time is None or not lower <= course_time <= upper:
            continue
        for segment in _PURPOSE_SEGMENT.split(str(course_row.get("record_content") or "")):
            texts.extend(_linked_name_fragments(segment, aliases))
    return tuple(texts)


def _has_linked_therapeutic_purpose(text: str, aliases: Sequence[str]) -> bool:
    """只接受“具体感染适应证 + 该药治疗动作”的局部绑定。"""

    for alias in aliases:
        drug = re.escape(alias)
        if re.search(_NEGATED_INFECTION, text) or re.search(
            rf"{_NEGATED_DRUG_ACTION}.{{0,8}}{drug}|{drug}.{{0,4}}(?:停用|不再使用)", text,
        ):
            continue
        patterns = (
            rf"{_THERAPEUTIC_ACTION}.{{0,8}}{drug}.{{0,12}}(?:用于|针对|控制|治疗|抗)?{_SPECIFIC_INFECTION}",
            rf"{drug}.{{0,8}}(?:用于|针对|控制|治疗|抗感染).{{0,12}}{_SPECIFIC_INFECTION}",
            rf"{_SPECIFIC_INFECTION}.{{0,16}}{drug}.{{0,8}}(?:用于|针对|控制|治疗|抗感染)",
        )
        if any(re.search(pattern, text) for pattern in patterns):
            return True
    return False


def _antimicrobial_intent(
    row: Mapping[str, Any],
    course_rows: Sequence[tuple[str, Mapping[str, Any]]],
) -> str:
    """返回单条药品医嘱的明确目的；不明确或预防/治疗并存时均不得排除。"""

    texts = _purpose_texts_for_order(row, course_rows)
    prophylactic = any(_PROPHYLACTIC_PURPOSE.search(text) for text in texts)
    aliases = _drug_name_aliases(row)
    therapeutic = any(_has_linked_therapeutic_purpose(text, aliases) for text in texts)
    if therapeutic and not prophylactic:
        return "therapeutic"
    if prophylactic and therapeutic:
        return "both"
    if prophylactic:
        return "prophylactic"
    return "unknown"


def _format(value: datetime) -> str:
    return value.strftime("%Y-%m-%d %H:%M:%S")


def _evaluate_event(event: SurgeryEventInput, orders: Sequence[Mapping[str, Any]]) -> _EventResult:
    anchor = event.end or event.begin
    if anchor is None:
        return _EventResult("data_gap", "surgery_time_unavailable", {"failure_kind": "surgery_time_unavailable"})
    window_start = (event.begin or anchor) - _PERIOPERATIVE_WINDOW
    timed = sorted(
        ((start, row) for row in orders if (start := order_start(row)) is not None),
        key=lambda item: item[0],
    )
    perioperative = [(start, row) for start, row in timed if window_start <= start <= anchor + _PERIOPERATIVE_WINDOW]
    if not perioperative:
        if any(order_start(row) is None for row in orders):
            # 有全身抗菌药物医嘱却无开始时间，不能断言围术期未用药。
            return _EventResult(
                "data_gap", "required_field_missing", {"failure_kind": "order_start_time_unavailable"}
            )
        return _EventResult("not_applicable", "trigger_absent_complete")
    if event.incision_class == "outside":
        return _EventResult("not_applicable", "incision_class_outside_scope")
    if event.incision_class != "I" and event.incision_class != "II":
        return _EventResult(
            "data_gap", "required_field_missing", {"failure_kind": "incision_class_unavailable"}
        )
    used: list[Mapping[str, Any]] = []
    last_use: datetime | None = None
    stop_unknown = False
    first_start = perioperative[0][0]
    perioperative_end = anchor + _PERIOPERATIVE_WINDOW
    for start, row in timed:
        if start < first_start:
            continue
        # 围术期窗口内开始的医嘱全部计入；窗口后的医嘱只在与前一段相隔不超过24小时时视为续开。
        if start > perioperative_end and last_use is not None and start > last_use + _CHAIN_GAP:
            break
        stop = order_stop(row)
        if stop is None:
            # 停止时间未知：只取已证明的下限（已知最后停用与本医嘱开始中较晚者），不编造停药时刻；
            # 后续医嘱是否属于同一链无法确认，不再续接。
            used.append(row)
            last_use = max(start, last_use) if last_use is not None else start
            stop_unknown = True
            break
        used.append(row)
        last_use = max(stop, last_use) if last_use is not None else stop
    assert last_use is not None
    threshold = 48 if event.incision_class == "I" and event.cardiac else 24
    duration = max((last_use - anchor).total_seconds() / 3600, 0.0)
    if stop_unknown and duration <= threshold:
        return _EventResult(
            "data_gap", "required_field_missing", {"failure_kind": "order_stop_time_unavailable"},
            orders=tuple(used),
        )
    facts = {
        "verification_kind": "prophylaxis_duration_check",
        "incision_class": event.incision_class,
        "cardiac_surgery": event.cardiac and event.incision_class == "I",
        "threshold_hours": threshold,
        "duration_hours": round(duration, 2),
        "anchor": "surgery_end" if event.end is not None else "surgery_begin",
        "anchor_time": _format(anchor),
        "last_antibacterial_time": _format(last_use),
    }
    if stop_unknown:
        facts["stop_time_unknown"] = True
    if duration <= threshold:
        return _EventResult(
            "compliant", "requirement_satisfied",
            {**facts, "infection_evidence": "not_required", "requirement_met": True},
            tuple(used), anchor, last_use,
        )
    return _EventResult("pending_evidence", "", facts, tuple(used), anchor, last_use, stop_unknown)


def _in_proven_evidence_window(result: _EventResult, time: datetime) -> bool:
    """已证明用药期间（含 24 小时续接）内的病程，可作为本次手术延长用药的感染证据。"""

    if result.anchor is None or result.last_use is None or time < result.anchor:
        return False
    return time <= result.last_use + _CHAIN_GAP


def _in_evidence_window(result: _EventResult, time: datetime) -> bool:
    """停药时间未知时实际用药可能延续到之后，术后全部病程都需送检，以免漏看感染证据。

    复审 P1-2：已证明期间之外的感染证据无法关联到本次手术/用药（可能属于后续另一手术），
    只能使结论待核，不能放行（见 _in_proven_evidence_window 的使用）。
    """

    if result.anchor is None or result.last_use is None or time < result.anchor:
        return False
    return result.stop_unknown or _in_proven_evidence_window(result, time)


_STATUS_RANK = {"non_compliant": 4, "technical_error": 3, "data_gap": 2, "compliant": 1, "not_applicable": 0}


async def evaluate_prophylactic_antimicrobial_duration(
    *, events: Sequence[SurgeryEventInput], drug_order_rows: Sequence[Mapping[str, Any]],
    course_rows: Sequence[tuple[str, Mapping[str, Any]]], llm_client: Any, course_scope_complete: bool = True,
) -> ProphylaxisOutcome:
    """药链由本模块计算；语义抽取仅提供经校验的逐台感染证据。"""
    if not events:
        return ProphylaxisOutcome("not_applicable", "trigger_absent_complete")
    orders = tuple(row for row in drug_order_rows if is_systemic_antibacterial(row)
                   and _antimicrobial_intent(row, course_rows) != "therapeutic")
    evaluated = [(event, _evaluate_event(event, orders)) for event in events]
    pending = [(event, result) for event, result in evaluated if result.status == "pending_evidence"]
    identities = tuple(event.identity for event in events if event.identity is not None)
    identity_complete = len(identities) == len(events) and all(item.resolved for item in identities)
    identity_complete = identity_complete and len({item.surgery_ref for item in identities}) == len(identities)
    candidate_times_complete = course_scope_complete and all(not str(row.get("record_content") or "").strip() or parse_time(
        row.get("record_time") or row.get("record_datetime") or row.get("submit_datetime") or row.get("submit_time")) is not None
        for _, row in course_rows)
    candidates = [(key, row, parse_time(row.get("record_time") or row.get("record_datetime") or row.get("submit_datetime") or row.get("submit_time")))
                  for key, row in course_rows if str(row.get("record_content") or "").strip()]
    timed_course = sorted(((key, row, time) for key, row, time in candidates
        if pending and (time is None or any(_in_evidence_window(result, time) for _, result in pending))),
        key=lambda item: (item[2] or datetime.max, item[0]))
    documents = tuple(InfectionDocument(key,
        str(row.get("record_time") or row.get("record_datetime") or row.get("submit_datetime") or row.get("submit_time")) if time is not None else None,
        redact_luxian_0609_patient_privacy(str(row.get("record_content") or "")),
        next((field for field in ("record_time", "record_datetime", "submit_datetime", "submit_time") if row.get(field)), ""),
        str(row.get("record_content") or "")) for key, row, time in timed_course)
    extraction = InfectionFacts(complete=not documents)
    if pending and identity_complete and documents:
        extraction = await extract_infection_surgery_facts(surgeries=identities,
            targets=tuple(event.identity.surgery_ref for event, _ in pending), documents=documents, llm_client=llm_client,
            scope_complete=candidate_times_complete,
            material_scope={"orders": tuple(drug_order_rows), "use_windows": {event.identity.surgery_ref: {
                "anchor": result.anchor, "last_use": result.last_use, "stop_unknown": result.stop_unknown}
                for event, result in pending}})
    for event, result in pending:
        positive, unknown, failed = False, not identity_complete or not candidate_times_complete, ""
        if extraction.reason_code and not extraction.invalid_refs:
            failed = extraction.reason_code
        target = event.identity.surgery_ref if event.identity is not None else None
        for key, _row, time in timed_course:
            if time is None and key in extraction.invalid_refs:
                # 缺记录时钟不能把真实协议失败伪装为临床资料不足。
                failed = extraction.reason_code or "model_invalid_output"
            if time is None or not _in_evidence_window(result, time):
                continue
            if key in extraction.invalid_refs:
                failed = extraction.reason_code or "model_invalid_output"
            document = extraction.documents.get(key)
            if document is None:
                continue
            unknown = unknown or document["state"] == "unknown"
            for fact in document["events"]:
                for relation in fact["relations"]:
                    if relation["target_surgery_ref"] != target:
                        continue
                    state = relation["validated_state"]
                    if state == "present":
                        if _in_proven_evidence_window(result, time):
                            positive = True
                        else:
                            unknown = True
                    elif state == "unknown":
                        unknown = True
        # 一份独立有效正面足够，未知/失败不得抹掉它；确定否定须相关候选全部核完。
        if positive:
            result.status, result.reason_code = "compliant", "requirement_satisfied"
            result.facts.update(infection_evidence="recorded", requirement_met=True)
        elif failed:
            result.status, result.reason_code, result.facts = "technical_error", failed, {}
        elif unknown:
            result.status, result.reason_code = "data_gap", "candidate_scope_incomplete" if not candidate_times_complete else "required_field_missing"
            result.facts = {"failure_kind": "infection_evidence_unresolved"}
        else:
            result.status, result.reason_code = "non_compliant", "requirement_violated"
            result.facts.update(infection_evidence="not_recorded", requirement_met=False)
    results = [result for _, result in evaluated]
    worst = max(results, key=lambda result: _STATUS_RANK[result.status])
    used_orders = {id(row): row for result in results for row in result.orders}
    audit = {"rule_id": RULE_ID, "schema_version": INFECTION_SURGERY_CONTRACT_VERSION,
        "complete": identity_complete and candidate_times_complete and extraction.complete
                    and all(result.status not in {"data_gap", "technical_error"} for result in results),
        "surgery_events": {event.identity.surgery_ref: {"material_refs": dict.fromkeys(event.identity.material_refs, True),
            "status": result.status, "reason_code": result.reason_code, "duration_facts": result.facts}
            for event, result in evaluated if event.identity is not None},
        "infection_events": private_infection_audit(extraction, documents),
        "invalid_source_refs": dict.fromkeys(extraction.invalid_refs, True), "failure_reason": extraction.reason_code}
    freeze_completed_infection_facts(extraction, complete=audit["complete"])
    return ProphylaxisOutcome(worst.status, worst.reason_code, worst.facts or None, tuple(used_orders.values()),
        tuple((key, row) for key, row, _ in timed_course), extraction.llm_call_count, extraction.prompt_tokens,
        extraction.completion_tokens, extraction.total_tokens, extraction.api_time, audit)
