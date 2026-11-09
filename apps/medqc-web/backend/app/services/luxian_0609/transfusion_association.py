"""同一证据会话内的逐次输血文书关联；不判临床合规、不查库、不调用模型。

输血记录为锚点，单份记录的多袋输注仍保留为同一组。显式关联键、血袋、
输注时刻及次数必须相互一致；先按实际起止时间检索，临床完整性由执行器另行核对。
结束时间解析由既有输血执行器注入，避免另建一个结束时间事实所有者。
"""
from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import date, datetime, timedelta, timezone
import re
from typing import Any, Callable, Literal, Mapping, Sequence

from .source_evidence_reader import authoritative_document_time_value

DocumentRef = tuple[str, str]
EndEvidence = Callable[[str], tuple[tuple[tuple[datetime, int, int], ...], bool]]
_DATE = re.compile(
    r"(?<!\d)(?P<year>\d{4})[年/-](?P<month>\d{1,2})[月/-](?P<day>\d{1,2})日?"
    r"[\sT]*(?P<hour>\d{1,2})[:：时](?P<minute>\d{1,2})分?"
    r"(?::(?P<second>\d{2}))?"
)
_ORDINAL = re.compile(r"第\s*([一二三四五六七八九十百\d]+)\s*次\s*输血")
_BAG = re.compile(r"(?:血袋(?:号|编号)|血液编号)\s*[:：]?\s*([A-Za-z0-9]{8,30})")
_INLINE_BAG = re.compile(r"(?:输入|输注)\s*([0-9]{10,24})(?=[ABO](?:型|Rh))", re.I)
_KEYS = ("bloodtrans_id", "transfusion_id", "application_id", "order_id")
_SCOPE = ("institute_id", "patient_id", "visit_id")
PRE_SEARCH_HOURS = 48  # 检索首选范围，不是规范规定的评估有效期或超时判据。
_HOSPITAL_TIMEZONE = timezone(timedelta(hours=8))
_CLOCK_PRECISION = re.compile(
    r"(?:[ T]\d{1,2}[:：]\d{2}|日\s*\d{1,2}(?::\d{2}|时\d{1,2}))"
)


def document_ref(source: str, row: Mapping[str, Any], index: int) -> DocumentRef:
    """缺编号的旧内部行仅用位置定位；@row编号不可作为对外证据坐标。"""
    return source, str(row.get("document_id") or row.get("application_id") or row.get("id") or f"@row:{index}")


def row_text(row: Mapping[str, Any]) -> str:
    return str(next((row[key] for key in ("record_content", "content", "assembled_text", "raw_text") if row.get(key)), ""))


def is_pre_assessment_document(row: Mapping[str, Any]) -> bool:
    """普通病程不作前评估候选；兼容旧材料缺题名但正文以专门评估题头开头。"""
    title = str(row.get("document_title") or row.get("title") or "").strip()
    if title:
        return bool(re.search(r"输血前(?:评估|评价)", title))
    return bool(re.match(r"\s*输血前(?:评估|评价)\s*[:：]?", row_text(row)))


def is_post_evaluation_document(row: Mapping[str, Any]) -> bool:
    """只认专门后评价题名；普通病程或输血记录提及评价不改变文书类型。"""
    title = str(row.get("document_title") or row.get("title") or "").strip()
    return bool(re.fullmatch(r"输血后(?:效果|疗效)?评价(?:记录)?", title))


def parse_precise_transfusion_datetime(value: Any) -> datetime | None:
    """输血关联与 047 共用的精确文书时间。

    有时区值先换算为医院 +08:00 时间；无时区值继续视为本地时间。
    纯日期不能冒充当日 00:00 参与小时级时限判定。
    """

    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, str):
        candidate = value.strip()
        if not candidate or _CLOCK_PRECISION.search(candidate) is None:
            return None
        try:
            parsed = datetime.fromisoformat(candidate.replace("Z", "+00:00"))
        except ValueError:
            match = _DATE.fullmatch(candidate)
            if match is None:
                return None
            try:
                parsed = datetime(
                    int(match["year"]),
                    int(match["month"]),
                    int(match["day"]),
                    int(match["hour"]),
                    int(match["minute"]),
                    int(match["second"] or 0),
                )
            except (TypeError, ValueError):
                return None
    else:
        return None
    if parsed.tzinfo is not None:
        parsed = parsed.astimezone(_HOSPITAL_TIMEZONE).replace(tzinfo=None)
    return parsed


def parse_transfusion_document_date(value: Any) -> date | None:
    """保留文书时间的日精度，仅用于排除不可能的关联。"""

    precise = parse_precise_transfusion_datetime(value)
    if precise is not None:
        return precise.date()
    if isinstance(value, date):
        return value
    if not isinstance(value, str):
        return None
    try:
        return date.fromisoformat(value.strip())
    except ValueError:
        return None


def authoritative_posttransfusion_time_value(row: Mapping[str, Any]) -> Any:
    """047 与 post 关联共用的权威记录/提交时间原值。"""

    explicit_time = authoritative_document_time_value(row)
    if explicit_time:
        return explicit_time
    if str(row.get("time_basis") or "").strip() == "record_time":
        return row.get("authored_at")
    return None


def _date_may_fall_in_post_window(value: date, event: TransfusionEvent) -> bool:
    if event.end is None or event.time_unresolved:
        return True
    day_start = datetime.combine(value, datetime.min.time())
    day_end = day_start + timedelta(days=1)
    return day_end > event.end and day_start <= event.end + timedelta(hours=24)


def _datetime(value: Any) -> datetime | None:
    try:
        parsed = value if isinstance(value, datetime) else datetime.fromisoformat(
            str(value).replace("Z", "+00:00")
        )
    except (ValueError, TypeError):
        return None
    if parsed.tzinfo is not None:
        parsed = parsed.astimezone(_HOSPITAL_TIMEZONE).replace(tzinfo=None)
    return parsed


def source_start_times(row: Mapping[str, Any]) -> tuple[datetime, ...]:
    return tuple(parsed for key in ("transfution_datetime", "transfusion_datetime", "start_time", "transfusion_start_time")
                 if (parsed := _datetime(row.get(key))) is not None)


def _time_mentions(text: str) -> tuple[tuple[datetime, str], ...]:
    found = []
    for match in _DATE.finditer(text):
        prefix = text[max(0, match.start() - 18):match.start()]
        suffix = text[match.end():match.end() + 20].lstrip()
        if re.search(r"预计|计划|拟于|拟在|预定", prefix):
            continue
        role = ""
        if re.match(r"开始(?:输入|输注|输血)", suffix) or re.search(r"(?:开始输血|输血开始|输注开始)(?:时间)?\s*[:：]?\s*$", prefix):
            role = "start"
        elif re.match(r"(?:输血|输注)(?:完毕|结束|完成)|输毕", suffix) or re.search(r"(?:输血|输注)(?:结束|完成)时间\s*[:：]?\s*$", prefix):
            role = "end"
        elif re.match(r"输注(?!完毕|结束|完成)|输入", suffix) or re.search(r"输血时间\s*[:：]?\s*$", prefix):
            role = "reference"
        if not role:
            continue
        try:
            value = datetime(**{key: int(match[key] or 0) for key in ("year", "month", "day", "hour", "minute", "second")})
        except ValueError:
            continue
        found.append((value, role))
    return tuple(found)


def _ordinals(text: str) -> frozenset[str]:
    # 次数仅作原文标识，不按文书顺序补号；同一标识命中多组时保持歧义。
    digits = dict(zip("一二三四五六七八九", range(1, 10)))
    def normalize(value: str) -> str:
        if value.isdigit():
            return str(int(value))
        if value in digits:
            return str(digits[value])
        if value == "十":
            return "10"
        return value
    return frozenset(normalize(value) for value in _ORDINAL.findall(text))


def _bags(text: str) -> frozenset[str]:
    return frozenset(value.upper() for value in (*_BAG.findall(text), *_INLINE_BAG.findall(text)))


def _components(text: str) -> frozenset[str]:
    # 只取输注动作后的血液成分，不能把实验室“血小板低”等当作拟输成分。
    return frozenset(re.findall(r"(?:输注|输入|拟输|备输|补充)[^。；;]{0,70}?(红细胞|血小板|血浆|冷沉淀|全血)", text))


@dataclass(frozen=True)
class TransfusionEvent:
    record_ref: DocumentRef
    start_times: tuple[datetime, ...]
    end_times: tuple[datetime, ...]
    ordinals: frozenset[str]
    bags: frozenset[str]
    components: frozenset[str]
    keys: tuple[tuple[str, str], ...]
    time_unresolved: bool = False

    @property
    def start(self) -> datetime | None:
        return min(self.start_times, default=None)

    @property
    def end(self) -> datetime | None:
        return max(self.end_times, default=None)


@dataclass(frozen=True)
class TransfusionAssociation:
    document_ref: DocumentRef
    stage: Literal["pre", "post"]
    state: str
    event_refs: tuple[DocumentRef, ...]
    basis: tuple[str, ...]
    document_time: datetime | None
    possible_event_refs: tuple[DocumentRef, ...] = ()

    @property
    def explicit(self) -> bool:
        return any(value in {"source_key", "blood_bag", "recorded_ordinal", "transfusion_time", "conflicting_anchors"} for value in self.basis)


@dataclass(frozen=True)
class TransfusionAssociations:
    events: tuple[TransfusionEvent, ...]
    documents: tuple[TransfusionAssociation, ...]

    def find(self, ref: DocumentRef, stage: str) -> TransfusionAssociation | None:
        return next((item for item in self.documents if item.document_ref == ref and item.stage == stage), None)

    @property
    def pending_documents(self) -> tuple[TransfusionAssociation, ...]:
        return tuple(item for item in self.documents if item.state not in {"linked", "ignored"})

    @property
    def events_without_pre_assessment(self) -> tuple[TransfusionEvent, ...]:
        matched = {item.event_refs[0] for item in self.documents
                   if item.stage == "pre" and item.state == "linked" and len(item.event_refs) == 1}
        return tuple(event for event in self.events if event.record_ref not in matched)


def _latest_pre_assessments(events: Sequence[TransfusionEvent], links: Sequence[TransfusionAssociation]) -> tuple[TransfusionAssociation, ...]:
    """每次只选输血开始前最近一份专门评估；多写的材料不形成待核义务。"""
    selected: dict[DocumentRef, TransfusionAssociation] = {}
    ties: set[DocumentRef] = set()
    covered = set()
    for event in events:
        candidates = [item for item in links if item.stage == "pre" and item.state in {"linked", "candidate", "component_conflict"}
                      and item.event_refs == (event.record_ref,) and item.document_time is not None
                      and event.start is not None and item.document_time < event.start]
        if not candidates:
            continue
        latest_time = max(item.document_time for item in candidates)
        latest = [item for item in candidates if item.document_time == latest_time]
        if len(latest) > 1:
            ties.update(item.document_ref for item in latest)
            continue
        item = latest[0]
        selected[item.document_ref] = replace(item, state="component_conflict" if item.state == "component_conflict" else "linked",
                                              basis=(*item.basis, "latest_pre_assessment"))
        covered.add(event.record_ref)
    result = []
    for item in links:
        if item.stage != "pre":
            result.append(item)
        elif item.document_ref in selected:
            result.append(selected[item.document_ref])
        elif item.document_ref in ties:
            result.append(replace(item, state="ambiguous", basis=(*item.basis, "latest_time_tie")))
        elif item.state in {"ambiguous", "time_conflict", "time_unavailable"} and any(ref not in covered for ref in item.event_refs):
            result.append(item)
        else:
            result.append(replace(item, state="ignored", basis=(*item.basis, "unused_pre_assessment")))
    return tuple(result)


def _associate(source: str, row: Mapping[str, Any], index: int, stage: Literal["pre", "post"], events: Sequence[TransfusionEvent]) -> TransfusionAssociation:
    text = row_text(row)
    value = row.get("request_datetime") or row.get("request_time") if source == "blood_application" else None
    raw_moment = value or (
        authoritative_posttransfusion_time_value(row)
        if stage == "post"
        else authoritative_document_time_value(row)
    )
    document_date = parse_transfusion_document_date(raw_moment)
    moment = parse_precise_transfusion_datetime(raw_moment)
    constraints: list[set[int]] = []
    basis = []
    keys = {key: str(row[key]) for key in _KEYS if row.get(key) and any(key in dict(event.keys) for event in events)}
    if keys:
        constraints.append({i for i, event in enumerate(events) if set(keys.items()).intersection(event.keys) and all(key not in dict(event.keys) or dict(event.keys)[key] == value for key, value in keys.items())})
        basis.append("source_key")
    bags = _bags(text)
    if bags:
        constraints.append({i for i, event in enumerate(events) if bags.issubset(event.bags)})
        basis.append("blood_bag")
    ordinals = _ordinals(text)
    if ordinals:
        constraints.append({i for i, event in enumerate(events) if ordinals == event.ordinals})
        basis.append("recorded_ordinal")
    mentions = _time_mentions(text)
    for value, role in mentions:
        constraints.append({i for i, event in enumerate(events) if value in (event.start_times if role == "start" else event.end_times if role == "end" else (*event.start_times, *event.end_times))})
        basis.append("transfusion_time")
    if constraints:
        candidates = set.intersection(*constraints)
        nonempty_constraints = [constraint for constraint in constraints if constraint]
        possible_candidates = (
            set.intersection(*nonempty_constraints)
            if nonempty_constraints
            else set(range(len(events)))
        )
        state = "linked" if len(candidates) == 1 else "ambiguous" if candidates else "unmatched"
        # 不同强证据各命中不同事件：明确保留冲突，而不是借其中一个强配。
        if not candidates and all(constraints):
            candidates = set.union(*constraints)
            state = "ambiguous"
            basis.append("conflicting_anchors")
    else:
        candidates = {i for i, event in enumerate(events) if moment is not None and (
            (event.start is not None and 0 < (event.start - moment).total_seconds() <= PRE_SEARCH_HOURS * 3600
             and not any(other.start is not None and moment < other.start < event.start for other in events))
            if stage == "pre" else (event.end is not None and 0 <= (moment - event.end).total_seconds() <= 24 * 3600))}
        possible_candidates = set(candidates)
        if not possible_candidates:
            possible_candidates = (
                {
                    i
                    for i, event in enumerate(events)
                    if _date_may_fall_in_post_window(document_date, event)
                }
                if moment is None and stage == "post" and document_date is not None
                else set(range(len(events)))
                if moment is None
                else {
                    i for i, event in enumerate(events)
                    if event.end is None or event.time_unresolved
                }
            )
        basis.append("time_window")
        state = "linked" if len(candidates) == 1 else "ambiguous" if candidates else "unmatched"
        if stage == "pre" and not candidates and moment is not None:
            # 首选范围之外仍保留回查候选，不能因超过48小时直接判缺失/超时。
            candidates = {i for i, event in enumerate(events) if event.start is not None and moment < event.start
                          and not any(other.start is not None and moment < other.start < event.start for other in events)}
            if candidates:
                state = "candidate"
                basis.append("expanded_search")
    components = _components(text)
    if components and possible_candidates:
        possible_candidates = {
            i for i in possible_candidates
            if not events[i].components or components.intersection(events[i].components)
        }
    if components and candidates:
        compatible = {i for i in candidates if not events[i].components or components.intersection(events[i].components)}
        if compatible != candidates:
            basis.append("blood_component")
            if stage == "pre" and not compatible:
                # 最近评估成分不符时保留问题，不能偷偷退回更早的一份合适评估。
                state = "component_conflict"
            else:
                candidates = compatible
                state = "unmatched" if not candidates else "candidate" if "expanded_search" in basis else "linked" if len(candidates) == 1 else "ambiguous"
    if candidates:
        possible_candidates = set(candidates)
    if state == "linked":
        event = events[next(iter(candidates))]
        boundary = event.start if stage == "pre" else event.end
        if moment is None or boundary is None or event.time_unresolved:
            state = "time_unavailable"
        elif (stage == "pre" and moment >= boundary) or (stage == "post" and moment < boundary):
            state = "time_conflict"
    return TransfusionAssociation(
        document_ref(source, row, index),
        stage,
        state,
        tuple(events[i].record_ref for i in sorted(candidates)),
        tuple(dict.fromkeys(basis)),
        moment,
        tuple(events[i].record_ref for i in sorted(possible_candidates)),
    )


def build_transfusion_associations(
    documents: Mapping[str, Any], *, end_evidence: EndEvidence,
    post_document_refs: frozenset[DocumentRef] = frozenset(),
) -> TransfusionAssociations:
    """生成可审阅关联，不改变原文书；未对应/歧义不等于临床文书缺失。

    后评价仅关联专门题名的文书；post_document_refs不能把普通病程升级为后评价单据。
    显式坐标不一致时拒绝整组，不能让跨机构同号文书参与匹配。
    """
    sources = ("bloodtrans_record", "blood_application", "daily_course_record", "senior_course_record")
    rows = {source: [row for row in (documents.get(source) or ()) if isinstance(row, Mapping)] for source in sources}
    for key in _SCOPE:
        if len({str(row[key]) for values in rows.values() for row in values if row.get(key)}) > 1:
            raise ValueError("mixed transfusion evidence scope")
    events = []
    for index, row in enumerate(rows["bloodtrans_record"]):
        text = row_text(row)
        ends, unresolved = end_evidence(text)
        starts = {value for value, role in _time_mentions(text) if role == "start"}
        starts.update(source_start_times(row))
        events.append(TransfusionEvent(document_ref("bloodtrans_record", row, index), tuple(sorted(starts)),
            tuple(sorted({value for value, _, _ in ends})), _ordinals(text), _bags(text), _components(text),
            tuple((key, str(row[key])) for key in _KEYS if row.get(key)),
            unresolved or bool(starts and ends and min(starts) > max(value for value, _, _ in ends))))
    links = []
    for source in sources[1:]:
        for index, row in enumerate(rows[source]):
            if source == "blood_application" or is_pre_assessment_document(row):
                links.append(_associate(source, row, index, "pre", events))
            if is_post_evaluation_document(row):
                links.append(_associate(source, row, index, "post", events))
    return TransfusionAssociations(tuple(events), _latest_pre_assessments(events, links))
