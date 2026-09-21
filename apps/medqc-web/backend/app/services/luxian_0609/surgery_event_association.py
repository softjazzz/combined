"""LX0609 已实施手术事件的受控计数与跨来源关联。"""

from __future__ import annotations

from datetime import date, datetime
import re
from typing import Any, Mapping, Sequence
from zoneinfo import ZoneInfo

from .evidence_material import (
    EvidenceMaterialTruncated,
    EvidenceMaterialUnavailable,
    Luxian0609EvidenceMaterialStore,
)
from .source_evidence_reader import (
    has_qualified_traditional_surgery_row,
    has_trusted_performed_surgery,
    parse_strict_performed_time,
    trusted_performed_surgery_times,
)

_RECORD_CONTENT_PLACEHOLDERS = frozenset({"无", "无。", "-", "不详", "未记录"})
_HOSPITAL_TIMEZONE = ZoneInfo("Asia/Shanghai")
_PLANNED_SURGERY_TIME_TEXT = re.compile(
    r"\d{4}-\d{2}-\d{2}(?:[ T]\d{2}:\d{2}(?::\d{2}(?:\.\d{1,6})?)?)?(?:Z|[+-]\d{2}:?\d{2})?"
)


class SurgeryEvent:
    """已实施手术的受控事件视图，仅在原生执行器内部使用。"""

    __slots__ = ("event_index", "source_key", "row")

    def __init__(
        self, *, event_index: int, source_key: str, row: Mapping[str, Any]
    ) -> None:
        self.event_index = event_index
        self.source_key = source_key
        self.row = row

    @property
    def surgery_name(self) -> str:
        return _clean(self.row.get("surgery_name"))


class PreopDocumentAssociation:
    """术前文书与单台已实施手术的受控关联结果。"""

    __slots__ = ("state", "event_index")

    def __init__(self, *, state: str, event_index: int | None = None) -> None:
        self.state = state
        self.event_index = event_index


def normalize_surgery_name(value: Any) -> str:
    """统一029与术前内容规则的术式名称比较语义。"""

    normalized = re.sub(
        r"[\s、，,。；;：:（）()\[\]【】]+", "", str(value or "")
    ).casefold()
    return normalized.replace("置入术", "植入术")


def procedure_matches_surgery(procedure_name: Any, surgery_name: Any) -> bool:
    """以术式事实作主键的保守匹配，避免单一短词误关联。"""

    left = normalize_surgery_name(procedure_name)
    right = normalize_surgery_name(surgery_name)
    if not left or not right:
        return False
    if left == right or left in right:
        return True
    # 原子事实必须是连续原文片段，常会保留“拟行/手术方案”等前缀；
    # 仅当完整术式本身具有足够辨识度时允许反向包含。
    if len(right) >= 5 and right in left:
        return True
    components = [part for part in re.split(r"[+＋、，,；;]", left) if len(part) >= 4]
    if not components:
        return False

    def component_matches(part: str) -> bool:
        if part in right:
            return True
        suffixes = [part[index:] for index in range(1, len(part) - 4)]
        return any(len(suffix) >= 5 and suffix in right for suffix in suffixes)

    matched = sum(1 for part in components if component_matches(part))
    return matched >= 2 and matched * 2 >= len(components)


def summary_surgery_name_from_row(row: Mapping[str, Any]) -> str:
    """读取029与078共用的术前小结术式名称，正文仅作最后回退。"""

    for field in (
        "planned_surgery_name",
        "surgery_name",
        "planned_surgery",
        "surgery_method",
    ):
        value = _preop_text(row.get(field))
        if value:
            return value
    text = _preop_text(row.get("record_content"))
    if not text:
        return ""
    match = re.search(
        r"(?:手术名称|手术方式)\s*[:：]\s*(.*?)(?=\s*(?:手术时间|麻醉方式|手术医师|术者签名|医师签名)\s*[:：]|$)",
        text,
    )
    return (match.group(1) if match else "").strip()


def summary_planned_surgery_time_from_row(
    row: Mapping[str, Any],
) -> datetime | None:
    """读取术前小结拟行手术时间，结构化字段优先、正文标签仅作回退。

    该时间只用于在同名多台手术之间收窄候选。它不是已实施手术的证据，
    因此允许源端日期型 ``00:00:00`` 值，但拒绝“今日急诊”等描述性文本。
    """

    for field in (
        "planned_surgery_time",
        "planned_surgery_datetime",
        "surgery_datetime",
        "surgery_time",
    ):
        if (parsed := _parse_planned_surgery_time(row.get(field))) is not None:
            return parsed

    text = _preop_text(row.get("record_content"))
    if not text:
        return None
    match = re.search(
        r"(?:^|[\r\n])\s*手术时间\s*[:：]\s*(?P<value>[^\r\n]+)",
        text,
    )
    return _parse_planned_surgery_time(match.group("value")) if match else None


def _parse_planned_surgery_time(value: Any) -> datetime | None:
    """将源端计划时间归一为医院本地无时区墙钟时间。"""

    if isinstance(value, datetime):
        return (
            value.replace(tzinfo=None)
            if value.tzinfo is None
            else value.astimezone(_HOSPITAL_TIMEZONE).replace(tzinfo=None)
        )
    if isinstance(value, date):
        return datetime.combine(value, datetime.min.time())
    if not isinstance(value, str):
        return None
    matched = _PLANNED_SURGERY_TIME_TEXT.fullmatch(value.strip())
    if matched is None:
        return None
    normalized = matched.group(0).replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        return None
    return (
        parsed.replace(tzinfo=None)
        if parsed.tzinfo is None
        else parsed.astimezone(_HOSPITAL_TIMEZONE).replace(tzinfo=None)
    )


def _preop_text(value: Any) -> str:
    if not isinstance(value, str):
        return ""
    candidate = value.strip()
    return "" if candidate.casefold() in _RECORD_CONTENT_PLACEHOLDERS else candidate


def count_associated_performed_surgery_events(
    materials: Luxian0609EvidenceMaterialStore,
) -> tuple[int | None, str]:
    """返回可逐台计数的已实施手术数及无法计数时的受控原因。

    单来源仅依据自己的稳定主键去重。两来源同时存在时，优先按手术编码（或
    完整手术名称）与严格的实际手术时间做双射匹配；若唯一实质正式手术记录
    对应同日复合组件，则按自然日收拢为一台事件。绝不比较不同来源的物理主键。
    """

    try:
        surgery_record_rows = tuple(materials.rows("surgery_record"))
    except EvidenceMaterialTruncated:
        return None, "source_truncated"
    except EvidenceMaterialUnavailable:
        return None, "source_unavailable"

    surgery_record_events = tuple(
        row
        for row in surgery_record_rows
        if has_trusted_performed_surgery(source_key="surgery_record", row=row)
    )
    try:
        mr_surgery_rows = tuple(materials.rows("mr_surgery"))
    except EvidenceMaterialTruncated:
        return None, "source_truncated"
    except EvidenceMaterialUnavailable:
        return None, "source_unavailable"
    qualified_mr_surgery_rows = tuple(
        row
        for row in mr_surgery_rows
        if has_qualified_traditional_surgery_row(row)
    )
    mr_surgery_events = tuple(
        row
        for row in qualified_mr_surgery_rows
        if has_trusted_performed_surgery(source_key="mr_surgery", row=row)
    )

    surgery_records = _deduplicated_source_events(
        "surgery_record",
        _remove_duplicate_time_shells(surgery_record_events),
    )
    mr_surgeries = _deduplicated_source_events("mr_surgery", mr_surgery_events)
    if surgery_records is None or mr_surgeries is None:
        return None, "association_failed"
    if surgery_records and mr_surgeries:
        surgery_records = _remove_confirmed_unmatched_sparse_time_shells(
            surgery_records, mr_surgeries
        )
    if not surgery_records:
        return len(mr_surgeries), ""
    trusted_mr_ids = {
        _clean(row.get("surgery_id")) for row in mr_surgery_events
    }
    if any(
        not has_trusted_performed_surgery(source_key="mr_surgery", row=row)
        and not (
            (identity := _clean(row.get("surgery_id")))
            and identity in trusted_mr_ids
        )
        for row in qualified_mr_surgery_rows
    ):
        return None, "association_failed"
    if not mr_surgeries:
        return len(surgery_records), ""
    if _has_strict_cross_source_bijection(surgery_records, mr_surgeries):
        return len(surgery_records), ""

    if _is_single_composite_event(surgery_records, mr_surgeries):
        return 1, ""
    return None, "association_failed"


def build_performed_surgery_events(
    materials: Luxian0609EvidenceMaterialStore,
) -> tuple[tuple[SurgeryEvent, ...] | None, str]:
    """仅以运行期正式手术记录形成术前文书关联事件。

    ``mr_surgery`` 通常在终末病案阶段才形成，运行病历质控不能等待或依赖
    该来源。这里仅使用已实施且去除同时间重复壳的 ``surgery_record``；
    跨来源计数仍由 ``count_associated_performed_surgery_events`` 独立负责。
    """

    try:
        rows = tuple(materials.rows("surgery_record"))
        performed = tuple(
            row
            for row in rows
            if has_trusted_performed_surgery(source_key="surgery_record", row=row)
        )
        deduplicated = _deduplicated_source_events(
            "surgery_record", _remove_duplicate_time_shells(performed)
        )
        if deduplicated is None:
            return None, "association_failed"
    except EvidenceMaterialTruncated:
        return None, "source_truncated"
    except EvidenceMaterialUnavailable:
        return None, "source_unavailable"
    return (
        tuple(
            SurgeryEvent(event_index=index, source_key="surgery_record", row=row)
            for index, row in enumerate(
                _ordered_event_rows("surgery_record", deduplicated), start=1
            )
        ),
        "",
    )


def associate_preop_document_to_surgery_event(
    *,
    events: Sequence[SurgeryEvent],
    procedure_name: Any,
    record_time: datetime | None,
    planned_surgery_time: datetime | None = None,
) -> PreopDocumentAssociation:
    """以术式事实优先、计划手术时间收窄候选的保守关联。

    计划时间仅在已按名称筛选的候选中精确到分钟或自然日收窄，不能覆盖
    明确术式冲突。文书记录时间保留旧有回退语义，永不按“最近手术”猜测。
    """

    if not events:
        return PreopDocumentAssociation(state="not_required")
    if len(events) == 1 and planned_surgery_time is None:
        event = events[0]
        if (
            normalize_surgery_name(procedure_name)
            and not procedure_matches_surgery(procedure_name, event.surgery_name)
        ):
            # 单台已实施手术只能在术前文书没有明确术式，或明确术式一致时
            # 作为回退锚点；不能覆盖已经存在的术式冲突。
            return PreopDocumentAssociation(state="ambiguous")
        return PreopDocumentAssociation(state="matched", event_index=event.event_index)

    named_candidates = [
        event
        for event in events
        if procedure_matches_surgery(procedure_name, event.surgery_name)
    ]
    if named_candidates:
        if planned_surgery_time is not None:
            planned_candidate = _unique_event_for_planned_surgery_time(
                named_candidates, planned_surgery_time
            )
            if planned_candidate is not None:
                return PreopDocumentAssociation(
                    state="matched", event_index=planned_candidate.event_index
                )
            # 有明确术式而计划时间无法落到其任何唯一候选时，不能再使用
            # 文书记录时间把它猜测性地关联到一台已实施手术。
            return PreopDocumentAssociation(state="ambiguous")
        candidates = _exclude_finished_before_document(named_candidates, record_time)
        if len(candidates) == 1:
            return PreopDocumentAssociation(
                state="matched", event_index=candidates[0].event_index
            )
        return PreopDocumentAssociation(state="ambiguous")

    if normalize_surgery_name(procedure_name):
        # 已抽到术式事实但不能匹配，不能让时间把它强行绑到另一台手术。
        return PreopDocumentAssociation(state="ambiguous")

    if planned_surgery_time is not None:
        planned_candidate = _unique_event_for_planned_surgery_time(
            events, planned_surgery_time
        )
        if planned_candidate is not None:
            return PreopDocumentAssociation(
                state="matched", event_index=planned_candidate.event_index
            )
        return PreopDocumentAssociation(state="ambiguous")

    interval_candidate = _next_event_in_completed_interval(events, record_time)
    if interval_candidate is not None:
        return PreopDocumentAssociation(
            state="matched", event_index=interval_candidate.event_index
        )
    return PreopDocumentAssociation(state="ambiguous")


def _unique_event_for_planned_surgery_time(
    events: Sequence[SurgeryEvent], planned_surgery_time: datetime
) -> SurgeryEvent | None:
    """按计划时间作确定性收窄，禁止用最近时间猜测。"""

    has_explicit_clock_time = any(
        (
            planned_surgery_time.hour,
            planned_surgery_time.minute,
            planned_surgery_time.second,
            planned_surgery_time.microsecond,
        )
    )
    if has_explicit_clock_time:
        minute_matches = [
            event
            for event in events
            if (begin := _event_boundary(event, "begin")) is not None
            and begin.replace(second=0, microsecond=0)
            == planned_surgery_time.replace(second=0, microsecond=0)
        ]
        if len(minute_matches) == 1:
            return minute_matches[0]
        return None

    same_day_matches = [
        event
        for event in events
        if (begin := _event_boundary(event, "begin")) is not None
        and begin.date() == planned_surgery_time.date()
    ]
    return same_day_matches[0] if len(same_day_matches) == 1 else None


def _event_boundary(event: SurgeryEvent, boundary: str) -> datetime | None:
    value, conflict = _boundary_time(event.source_key, event.row, boundary)
    return None if conflict else value


def _ordered_event_rows(
    source_key: str, rows: Sequence[Mapping[str, Any]]
) -> tuple[Mapping[str, Any], ...]:
    """事件序号以可靠开始时间为主，缺时保留来源已经确定的稳定顺序。"""

    indexed = tuple(enumerate(rows))
    return tuple(
        row
        for _index, row in sorted(
            indexed,
            key=lambda item: (
                (_boundary_time(source_key, item[1], "begin")[0] is None),
                _boundary_time(source_key, item[1], "begin")[0] or datetime.max,
                item[0],
            ),
        )
    )


def _exclude_finished_before_document(
    events: Sequence[SurgeryEvent], record_time: datetime | None
) -> list[SurgeryEvent]:
    if record_time is None:
        return list(events)
    return [
        event
        for event in events
        if (end := _event_boundary(event, "end")) is None or end >= record_time
    ]


def _next_event_in_completed_interval(
    events: Sequence[SurgeryEvent], record_time: datetime | None
) -> SurgeryEvent | None:
    if record_time is None:
        return None
    completed = [
        event
        for event in events
        if (end := _event_boundary(event, "end")) is not None and end <= record_time
    ]
    future = [
        (event, begin)
        for event in events
        if (begin := _event_boundary(event, "begin")) is not None and begin > record_time
    ]
    if not completed or not future:
        return None
    nearest_time = min(begin for _event, begin in future)
    nearest = [event for event, begin in future if begin == nearest_time]
    return nearest[0] if len(nearest) == 1 else None


def _clean(value: Any) -> str:
    return value.strip() if isinstance(value, str) else ""


def _has_effective_content(
    value: Any, *, placeholders: frozenset[str] = frozenset()
) -> bool:
    if isinstance(value, str):
        cleaned = value.strip()
        return bool(cleaned) and cleaned not in placeholders
    return value is not None and bool(value)


def _is_substantive_surgery_record(row: Mapping[str, Any]) -> bool:
    return _has_effective_content(row.get("surgery_process")) or _has_effective_content(
        row.get("record_content"), placeholders=_RECORD_CONTENT_PLACEHOLDERS
    )


def _same_surgery_identity(
    left: Mapping[str, Any], right: Mapping[str, Any]
) -> bool:
    left_code = _normalized_surgery_code(left)
    right_code = _normalized_surgery_code(right)
    if left_code and right_code and left_code == right_code:
        return True
    left_name = _normalized_surgery_name(left)
    right_name = _normalized_surgery_name(right)
    return bool(left_name and right_name and left_name == right_name)


def _remove_duplicate_time_shells(
    rows: Sequence[Mapping[str, Any]],
) -> tuple[Mapping[str, Any], ...]:
    """仅移除有相同实质手术副本的无正文时间壳记录。"""

    substantive_rows = tuple(row for row in rows if _is_substantive_surgery_record(row))
    if not substantive_rows:
        return tuple(rows)
    return tuple(
        row
        for row in rows
        if _is_substantive_surgery_record(row)
        or not any(
            _same_surgery_identity(row, candidate)
            and _same_reliable_surgery_time_shell(row, candidate)
            for candidate in substantive_rows
        )
    )


def _same_reliable_surgery_time_shell(
    left: Mapping[str, Any], right: Mapping[str, Any]
) -> bool:
    """时间壳必须与实质副本具有同一可靠手术开始时间。"""

    left_begin, left_conflict = _boundary_time("surgery_record", left, "begin")
    right_begin, right_conflict = _boundary_time("surgery_record", right, "begin")
    if (
        left_conflict
        or right_conflict
        or left_begin is None
        or right_begin is None
        or left_begin != right_begin
    ):
        return False
    left_end, left_end_conflict = _boundary_time("surgery_record", left, "end")
    right_end, right_end_conflict = _boundary_time("surgery_record", right, "end")
    return not (
        left_end_conflict
        or right_end_conflict
        or left_end is not None
        and right_end is not None
        and left_end != right_end
    )


def _remove_confirmed_unmatched_sparse_time_shells(
    surgery_records: Sequence[Mapping[str, Any]],
    mr_surgeries: Sequence[Mapping[str, Any]],
) -> tuple[Mapping[str, Any], ...]:
    """受控消除 C01 型稀疏时间壳。

    仅在唯一 mr_surgery 已严格匹配一份实质正式记录时，才移除同名、无正文、
    无 mr 对应且记录时间不早于该实质手术开始的额外行。该分支不适用于
    多台手术，不能以名称或最近时间直接合并。
    """

    if len(mr_surgeries) != 1:
        return tuple(surgery_records)
    mr_row = mr_surgeries[0]
    matched_indexes = [
        index
        for index, row in enumerate(surgery_records)
        if (
            _is_strict_cross_source_match(row, mr_row)
            or (
                _same_surgery_identity(row, mr_row)
                and _natural_day("surgery_record", row)
                == _natural_day("mr_surgery", mr_row)
                is not None
            )
        )
        and _is_substantive_surgery_record(row)
    ]
    if len(matched_indexes) != 1:
        return tuple(surgery_records)
    substantive = surgery_records[matched_indexes[0]]
    substantive_begin, conflict = _boundary_time("surgery_record", substantive, "begin")
    if conflict or substantive_begin is None:
        return tuple(surgery_records)
    retained: list[Mapping[str, Any]] = []
    for row in surgery_records:
        if row is substantive:
            retained.append(row)
            continue
        if (
            not _is_substantive_surgery_record(row)
            and _same_surgery_identity(row, substantive)
            and not _is_strict_cross_source_match(row, mr_row)
            and (row_begin := _boundary_time("surgery_record", row, "begin")[0])
            is not None
            and row_begin < substantive_begin
            and (record_time := _surgery_record_document_time(row)) is not None
            and record_time >= substantive_begin
        ):
            continue
        retained.append(row)
    return tuple(retained)


def _surgery_record_document_time(row: Mapping[str, Any]) -> datetime | None:
    """仅用于 C01 时间壳的受控 record_time 比较，禁止改用提交时间。"""

    value = row.get("record_time")
    if isinstance(value, datetime):
        return value.replace(tzinfo=None) if value.tzinfo is not None else value
    if not isinstance(value, str):
        return None
    strict = parse_strict_performed_time(value)
    if strict is not None:
        return strict
    try:
        return datetime.strptime(value.strip(), "%Y-%m-%d %H:%M:%S")
    except ValueError:
        return None


def _natural_day(source_key: str, row: Mapping[str, Any]) -> date | None:
    days = {
        value.date()
        for value in trusted_performed_surgery_times(source_key=source_key, row=row)
    }
    return next(iter(days)) if len(days) == 1 else None


def _is_single_composite_event(
    surgery_records: Sequence[Mapping[str, Any]],
    mr_surgeries: Sequence[Mapping[str, Any]],
) -> bool:
    """在唯一正式记录下按自然日安全收拢 mr_surgery 组件。"""

    if (
        len(surgery_records) != 1
        or not mr_surgeries
        or not _is_substantive_surgery_record(surgery_records[0])
    ):
        return False
    record = surgery_records[0]
    record_day = _natural_day("surgery_record", record)
    if record_day is None:
        return False
    for component in mr_surgeries:
        if _natural_day("mr_surgery", component) != record_day:
            return False
    return True


def _is_linkable_single_composite_event(
    surgery_records: Sequence[Mapping[str, Any]],
    mr_surgeries: Sequence[Mapping[str, Any]],
) -> bool:
    """术前文书关联只接受术式名称可覆盖全部组件的单一复合事件。

    既有计数规则允许同日组件按一台计数；关联规则更严格，因为同日也可能
    实施两台彼此独立的手术，不能把“同日”本身当作文书归属依据。
    """

    if not _is_single_composite_event(surgery_records, mr_surgeries):
        return False
    record = surgery_records[0]
    record_name = _clean(record.get("surgery_name"))
    if not record_name:
        return False
    names_cover_all_components = all(
        procedure_matches_surgery(record_name, component.get("surgery_name"))
        or _same_surgery_identity(record, component)
        for component in mr_surgeries
    )
    if names_cover_all_components:
        return True

    # 客户 mr_surgery 的组件时间常只有日期（同日零点），而正式记录保留
    # 实际时分。所有组件共享同一精确时间时可视为一个事件的编码拆分；
    # 同日但时间不同仍按可能的独立手术处理。
    component_begins: set[datetime] = set()
    for component in mr_surgeries:
        begin, conflict = _boundary_time("mr_surgery", component, "begin")
        if conflict or begin is None:
            return False
        component_begins.add(begin)
    return len(component_begins) == 1


def _deduplicated_source_events(
    source_key: str,
    rows: Sequence[Mapping[str, Any]],
) -> tuple[Mapping[str, Any], ...] | None:
    if len(rows) <= 1:
        return tuple(rows)
    # 单来源重复同步可由该来源的物理主键去重；缺少主键时不能把重复行猜成
    # 多台手术，也不能反向认定为同一台。
    identity_field = {
        "surgery_record": "document_id",
        "mr_surgery": "surgery_id",
    }[source_key]
    deduplicated: dict[str, Mapping[str, Any]] = {}
    for row in rows:
        identity = _clean(row.get(identity_field))
        if not identity:
            return None
        deduplicated.setdefault(identity, row)
    return tuple(deduplicated.values())


def _has_strict_cross_source_bijection(
    surgery_records: Sequence[Mapping[str, Any]],
    mr_surgeries: Sequence[Mapping[str, Any]],
) -> bool:
    if len(surgery_records) != len(mr_surgeries):
        return False
    matched_mr_indexes: set[int] = set()
    for surgery_record_row in surgery_records:
        matching_indexes = [
            index
            for index, mr_surgery_row in enumerate(mr_surgeries)
            if _is_strict_cross_source_match(surgery_record_row, mr_surgery_row)
        ]
        if len(matching_indexes) != 1 or matching_indexes[0] in matched_mr_indexes:
            return False
        matched_mr_indexes.add(matching_indexes[0])
    return len(matched_mr_indexes) == len(mr_surgeries)


def _normalized_surgery_code(row: Mapping[str, Any]) -> str:
    return re.sub(r"\s+", "", _clean(row.get("surgery_code"))).casefold()


def _normalized_surgery_name(row: Mapping[str, Any]) -> str:
    return re.sub(r"\s+", "", _clean(row.get("surgery_name"))).casefold()


def _boundary_time(
    source_key: str,
    row: Mapping[str, Any],
    boundary: str,
) -> tuple[datetime | None, bool]:
    """返回单边界时间；同一行双字段冲突时拒绝跨源关联。"""

    fields_by_source = {
        "surgery_record": {
            "begin": ("surgery_begin_time", "surgery_begin_datetime"),
            "end": ("surgery_end_time", "surgery_end_datetime"),
        },
        "mr_surgery": {
            "begin": ("surgery_begin_datetime",),
            "end": ("surgery_end_datetime",),
        },
    }
    values: set[datetime] = set()
    for field in fields_by_source[source_key][boundary]:
        value = row.get(field)
        if source_key == "surgery_record":
            parsed = parse_strict_performed_time(value)
        elif isinstance(value, datetime) and value.tzinfo is None:
            parsed = value
        else:
            parsed = None
        if parsed is not None:
            values.add(parsed)
    if len(values) > 1:
        return None, True
    return (next(iter(values)), False) if values else (None, False)


def _is_strict_cross_source_match(
    surgery_record_row: Mapping[str, Any],
    mr_surgery_row: Mapping[str, Any],
) -> bool:
    """只按已投影的业务事实做跨源一对一匹配，禁止互比物理主键。"""

    record_code = _normalized_surgery_code(surgery_record_row)
    mr_code = _normalized_surgery_code(mr_surgery_row)
    record_name = _normalized_surgery_name(surgery_record_row)
    mr_name = _normalized_surgery_name(mr_surgery_row)

    if record_code and mr_code:
        if record_code != mr_code:
            return False
        # 编码相同仍不允许同时存在的完整名称互相矛盾。
        if record_name and mr_name and record_name != mr_name:
            return False
    elif not (record_name and mr_name and record_name == mr_name):
        return False

    has_matching_boundary = False
    for boundary in ("begin", "end"):
        record_time, record_conflict = _boundary_time(
            "surgery_record", surgery_record_row, boundary
        )
        mr_time, mr_conflict = _boundary_time("mr_surgery", mr_surgery_row, boundary)
        if record_conflict or mr_conflict:
            return False
        if record_time is not None and mr_time is not None:
            if record_time != mr_time:
                return False
            has_matching_boundary = True
    return has_matching_boundary
