"""LX0609 术后规则族执行模块（04-05-01 / 04-05-02 / 04-05-03）。

从 `native_extended_document_execution.py` 拆出，围绕同一已实施手术适用性门控、
逐台次事件投影、逐文书绑定与病程正文语义抽取独立执行，不反向依赖总调度模块。
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Any, Mapping, Sequence

from app.services.document_assembly.signatures import course_physician_signatures

from ..course_body_fact_extraction import (
    CourseBodyExtraction,
    extract_course_body_facts,
)
from ..decision_model import RuleDecision
from ..evidence_material import (
    EvidenceMaterialTruncated,
    EvidenceMaterialUnavailable,
    Luxian0609EvidenceMaterialStore,
)
from ..evidence_snapshot import Luxian0609EvidenceSnapshot
from ..source_evidence_reader import parse_strict_performed_time
from ..surgery_applicability import (
    SurgeryApplicability,
    resolve_surgery_applicability,
)
from ..surgery_procedure_catalog import catalog_surgery_state
from .family_runtime import (
    ExtendedDocumentFamilyOutcome,
    SourceRowsCache,
    build_extended_decision,
    course_body_candidate_inputs,
    resolve_horizon_rows,
    source_rows,
)
from .shared import _clean, _parse_datetime, _row_time

POSTOPERATIVE_RULE_IDS = (
    "LX0609-04-05-01",
    "LX0609-04-05-02",
    "LX0609-04-05-03",
)

# 064 院方口径：术者须亲自在术前24小时内、术后24小时内查房。
_SURGEON_ROUND_WINDOW_HOURS = 24
_PHYSICIAN_TITLE_SUFFIXES = (
    "副主任医师",
    "主任医师",
    "主治医师",
    "住院医师",
    "医师",
)
_TITLE_ROUND_MARKER_PATTERN = re.compile(r"(?:查房|巡诊)")
_TITLE_ROUND_ROLE_DESCRIPTION_PATTERN = re.compile(
    r"(?:术者\s*[:：]|手术由[^，,；;。]*完成)"
)
_MASKED_PHYSICIAN_IDENTITY_PATTERN = re.compile(r"(?:某|匿名|脱敏|[*＊×])")
_PHYSICIAN_TITLE_ALTERNATION = "副主任医师|主任医师|主治医师|住院医师|医师"


def _course_dates(
    rows: Sequence[Mapping[str, Any]],
) -> set:
    return {
        parsed.date()
        for row in rows
        if (parsed := _row_time(row)) is not None
    }


def _course_row_has_body(row: Mapping[str, Any]) -> bool:
    """正文列明确为空时，不把日期本身当作有效病程记录。"""

    # Evidence Snapshot 的病程投影固定保留 record_content。对旧的最小测试
    # 夹具保留“未提供该列”的兼容语义，但一旦来源明确给出空列，必须按资料
    # 不完整处理，不能仅凭 record_time/标题或作者计入覆盖日期。
    if "record_content" not in row:
        return True
    return bool(_clean(row.get("record_content")))


def _qualified_surgery_rows(
    surgery_record_rows: Sequence[Mapping[str, Any]],
) -> tuple[Mapping[str, Any], ...]:
    return tuple(
        row for row in surgery_record_rows if catalog_surgery_state(row) is not False
    )


def _surgery_applicability_outcome(
    applicability: SurgeryApplicability,
) -> tuple[str, str] | None:
    """将规则族共用门控投影为扩展文书执行器的受控状态。"""

    if applicability.state == "applicable":
        return None
    if applicability.state == "not_applicable":
        return "not_applicable", "performed_event_absent"
    if applicability.state == "technical_error":
        return "technical_error", applicability.reason_code
    return "data_gap", applicability.reason_code


@dataclass(frozen=True)
class _PostoperativeSurgeryEvent:
    """064–066 的手术台次投影，保留组成台次的原始行以绑定证据。"""

    source_key: str
    row: Mapping[str, Any]
    document_id: str
    surgery_name: str
    surgery_end_time: datetime | None
    surgeon_names: tuple[str, ...]
    surgeon_tokens: frozenset[str]
    surgery_begin_time: datetime | None = None
    # 院方口径（2026-10-10）：源库缺实际结束时间时以开始时间推算术后起点。
    surgery_time_estimated: bool = False
    member_rows: tuple[Mapping[str, Any], ...] = ()
    # 缺手术记录、仅首页手术日期（0点）时，手术时刻未知（C23、C25 源库缺手术记录单据）。
    surgery_time_date_only: bool = False


def _body_surgeon_round_tokens(
    row: Mapping[str, Any],
    *,
    candidate_tokens: frozenset[str],
) -> frozenset[str]:
    """用户口径（2026-10-22）：正文明确写“术者/主刀医师××查看患者”也算术者查房。

    只认术者/主刀角色与首页术者完整姓名紧邻、且同句写明查看/查房；单纯提及术者
    （如“手术由××完成”）不算。
    """

    text = _clean(row.get("record_content"))
    if not text:
        return frozenset()
    found = set()
    for token in candidate_tokens:
        name = re.escape(token)
        title = rf"(?:{_PHYSICIAN_TITLE_ALTERNATION})?"
        role = r"(?:术者|主刀(?:医师|医生)?)"
        if re.search(
            rf"(?:{role}[：:]?\s*{name}{title}|{name}{title}[（(]?{role}[）)]?)"
            rf"[^。；;\n]{{0,12}}(?:查看|查房|看望|探视)",
            text,
        ):
            found.add(token)
    return frozenset(found)


def _normalized_physician_token(value: Any) -> str:
    token = re.sub(r"\s+", "", _clean(value)).lower()
    for suffix in _PHYSICIAN_TITLE_SUFFIXES:
        if token.endswith(suffix):
            token = token[: -len(suffix)]
            break
    return token


def _physician_identity_is_masked(value: Any) -> bool:
    """脱敏姓名不能用于证明或否定术者与查房医师是同一人。"""

    return bool(_MASKED_PHYSICIAN_IDENTITY_PATTERN.search(_clean(value)))


def _surgery_event_surgeon_tokens(row: Mapping[str, Any]) -> frozenset[str]:
    """正式手术事件只接受术者专属字段，不能把文书作者当作术者。"""

    return frozenset(
        token
        for key in (
            "surgeon",
            "surgeon_sign",
            "main_surgery_sign",
        )
        if (token := _normalized_physician_token(row.get(key)))
    )


def _surgery_event_surgeon_names(row: Mapping[str, Any]) -> tuple[str, ...]:
    """保留术者专属字段中的客户可读姓名，不展示标准化匹配 token。"""

    names: list[str] = []
    for key in ("surgeon", "surgeon_sign", "main_surgery_sign"):
        name = _clean(row.get(key))
        if name and name not in names:
            names.append(name)
    return tuple(names)


def _course_record_physician_tokens(row: Mapping[str, Any]) -> frozenset[str]:
    """从受控作者字段或明确正文签名读取医师；提交人不替代签名。"""

    return frozenset(
        token
        for value in (
            row.get("author_name"),
            row.get("author_signature"),
            row.get("doctor_signature"),
            *course_physician_signatures(row),
        )
        if (token := _normalized_physician_token(value))
    )


def _title_round_physician_tokens(
    row: Mapping[str, Any],
    *,
    candidate_tokens: frozenset[str],
) -> frozenset[str]:
    """仅确认查房标题中、查房标记前明确列出的当前术者。"""

    title = _clean(row.get("document_title"))
    marker = _TITLE_ROUND_MARKER_PATTERN.search(title)
    if marker is None:
        return frozenset()
    title_header = title[: marker.start()]
    # 标题中的角色说明（如“手术由…完成”）不构成查房医师名单；
    # 不从正文、科室或查房标记后的附注反向推断术者。
    if _TITLE_ROUND_ROLE_DESCRIPTION_PATTERN.search(title_header):
        return frozenset()
    # 0910 源库的上级医师病程标题会将当前术者写成“姓名+主刀医师”，
    # “主刀”是角色而非姓名的一部分。只在标题开头、联合查房或明确标点边界后
    # 接受完整候选姓名，避免把较长姓名的尾部误认作当前术者。
    explicit_primary_surgeons = {
        candidate
        for candidate in candidate_tokens
        if re.search(
            rf"(?:^|联合|[，,、；;（）()]){re.escape(candidate)}主刀医师",
            title_header,
            flags=re.IGNORECASE,
        )
    }
    # 按职称分段提取完整姓名，不能用术者姓名去匹配另一姓名的后缀。
    identities = set()
    for match in re.finditer(
        r"([^，,、；;：:（）()]+?)(?:副主任医师|主任医师|主治医师|住院医师|医师)",
        title_header,
    ):
        identity = match.group(1).strip()
        # 仅剥离有明确边界的联合查房/科室前缀；其余整段保留，不能猜姓名。
        # “联合”后紧跟的“××科/××中心”是会诊科室（C25“联合胸外科某某副主任医师”），
        # 不在固定名单内也剥离；无“联合”边界时不拆（“王科李明”不能拆出“李明”）。
        identity = re.sub(
            r"^联合[\u4e00-\u9fff]{1,8}?(?:科|中心)(?=[\u4e00-\u9fff]{2,4}$)",
            "",
            identity,
        )
        identity = re.sub(r"^联合", "", identity)
        identity = re.sub(
            r"^(?:联合)?(?:神经疾病中心|神经外科|神经内科|心胸外科|"
            r"普通外科|普外科|骨科|眼科|耳鼻喉科|妇产科|儿科|泌尿外科)",
            "",
            identity,
        )
        identities.add(_normalized_physician_token(identity))
    return frozenset(
        identities.intersection(candidate_tokens) | explicit_primary_surgeons
    )


def _actual_surgery_begin_time(
    *, source_key: str, row: Mapping[str, Any]
) -> datetime | None:
    """术前查房时限只读取实际开始字段；不得回退到申请或文书时间。"""

    for field in ("surgery_begin_time", "surgery_begin_datetime"):
        value = row.get(field)
        if source_key == "surgery_record":
            if (parsed := parse_strict_performed_time(value)) is not None:
                return parsed
    return None


def _actual_surgery_end_time(
    *, source_key: str, row: Mapping[str, Any]
) -> datetime | None:
    """术后规则只能读取实际结束字段；不得回退到申请或文书时间。"""

    for field in ("surgery_end_time", "surgery_end_datetime"):
        value = row.get(field)
        if source_key == "surgery_record":
            if (parsed := parse_strict_performed_time(value)) is not None:
                return parsed
    return None


def _postoperative_surgery_events(
    *,
    surgery_record_rows: Sequence[Mapping[str, Any]],
) -> tuple[_PostoperativeSurgeryEvent, ...]:
    """按原始手术记录逐文书建事件，首页不提供台次、术者或时间回退。"""

    events = []
    for index, row in enumerate(_qualified_surgery_rows(surgery_record_rows), start=1):
        end_time = _actual_surgery_end_time(source_key="surgery_record", row=row)
        begin_time = _actual_surgery_begin_time(source_key="surgery_record", row=row)
        events.append(
            _PostoperativeSurgeryEvent(
                source_key="surgery_record",
                row=row,
                member_rows=(row,),
                document_id=_clean(row.get("document_id") or row.get("id"))
                or f"surgery_record:{index}",
                surgery_name=_clean(
                    row.get("surgery_name")
                    or row.get("operation_name")
                    or row.get("procedure_name")
                ),
                surgery_end_time=end_time if end_time is not None else begin_time,
                surgeon_names=_surgery_event_surgeon_names(row),
                surgeon_tokens=_surgery_event_surgeon_tokens(row),
                surgery_begin_time=begin_time,
                surgery_time_estimated=end_time is None and begin_time is not None,
                surgery_time_date_only=False,
            )
        )
    return tuple(events)


def _postoperative_document_refs(
    *,
    snapshot: Luxian0609EvidenceSnapshot,
    materials: Luxian0609EvidenceMaterialStore,
    selected_rows: Sequence[Mapping[str, Any]],
) -> tuple[str, ...]:
    """把064/065/066实际消费的事件或病程唯一绑定为逐文书证据。"""

    allowed_sources = (
        "surgery_record",
        "daily_course_record",
        "senior_course_record",
        "postsurg_firstcourse_record",
    )
    refs: list[str] = []
    for selected_row in selected_rows:
        matches: list[str] = []
        for source_key in allowed_sources:
            try:
                document_rows = materials.document_rows(source_key, snapshot=snapshot)
            except (
                EvidenceMaterialUnavailable,
                EvidenceMaterialTruncated,
                TypeError,
                ValueError,
            ):
                continue
            matches.extend(
                reference
                for reference, material_row in document_rows
                if material_row == selected_row
            )
        if len(matches) != 1:
            return ()
        refs.append(matches[0])
    return tuple(dict.fromkeys(refs))


def _link_postoperative_first_course_records(
    *,
    surgery_events: Sequence[_PostoperativeSurgeryEvent],
    postoperative_rows: Sequence[Mapping[str, Any]],
) -> tuple[
    tuple[tuple[_PostoperativeSurgeryEvent, tuple[Mapping[str, Any], ...]], ...], str
]:
    """按最近一台已结束的正式手术，将术后首次病程唯一归属到单个事件。

    仅使用实际手术结束时间和文书权威记录时间；结束时间相同或任一待核对文书
    缺时间时无法做安全归属，保持数据不足而不猜测。
    """

    if any(event.surgery_end_time is None for event in surgery_events):
        return (), "authoritative_time_missing"
    ordered_events = tuple(sorted(surgery_events, key=lambda item: item.surgery_end_time))
    if len({item.surgery_end_time for item in ordered_events}) != len(ordered_events):
        return (), "association_failed"

    # 事件身份按本次有序事件序号保存，不能用展示用 document_id 作字典键：
    # 上游允许不同正式记录行复用同一个 document_id。
    linked_rows: list[list[Mapping[str, Any]]] = [[] for _event in ordered_events]
    for row in postoperative_rows:
        record_time = _row_time(row)
        if record_time is None:
            return (), "authoritative_time_missing"
        eligible_event_indexes = tuple(
            index
            for index, event in enumerate(ordered_events)
            if event.surgery_end_time is not None and event.surgery_end_time <= record_time
        )
        if not eligible_event_indexes:
            continue
        # 归属最近一台已经结束的手术，一份术后首次病程不会复用到更早手术。
        linked_rows[eligible_event_indexes[-1]].append(row)

    return (
        tuple(
            (event, tuple(rows))
            for event, rows in zip(ordered_events, linked_rows)
        ),
        "",
    )


def _event_display_base(event: _PostoperativeSurgeryEvent) -> dict[str, Any]:
    return {
        "document_id": event.document_id,
        "surgery_name": event.surgery_name,
        "surgeon_names": list(event.surgeon_names),
        "surgery_end_time": (
            event.surgery_end_time.isoformat(sep=" ")
            if event.surgery_end_time is not None
            else None
        ),
    }


def _postoperative_window_gate(
    *,
    surgery_events: Sequence[_PostoperativeSurgeryEvent],
    horizon_rows: Sequence[Mapping[str, Any]],
    horizon_error: str,
) -> tuple[str, str, Mapping[str, Any]] | None:
    """在逐台核对前确认至少有一台术后三日观察窗口已经成熟。

    评价终点必须来自同一冻结 Evidence Session。只有日期时按保守口径，
    评价日期严格晚于对应手术结束日后的第三个自然日，避免在窗口当天提前
    把尚未发生的病程判为缺失。
    """

    def unavailable(issue: str) -> tuple[str, str, Mapping[str, Any]]:
        return (
            "data_gap",
            issue,
            {
                "verification_kind": "postoperative_three_day_window_unavailable",
                "issue": issue,
            },
        )

    if horizon_error:
        return unavailable(horizon_error)
    if len(horizon_rows) != 1:
        return unavailable("authoritative_time_missing")

    row = horizon_rows[0]
    horizon_time = _parse_datetime(row.get("horizon_datetime"))
    raw_date = _clean(row.get("horizon_date"))
    horizon_date: date | None = None
    if raw_date:
        try:
            horizon_date = date.fromisoformat(raw_date)
        except ValueError:
            return unavailable("authoritative_time_missing")
    if horizon_time is None and horizon_date is None:
        return unavailable("authoritative_time_missing")
    if (
        horizon_time is not None
        and horizon_date is not None
        and horizon_time.date() != horizon_date
    ):
        return unavailable("authoritative_time_conflict")

    deadlines = tuple(
        event.surgery_end_time.date() + timedelta(days=3)
        for event in surgery_events
        if event.surgery_end_time is not None
    )
    if len(deadlines) != len(surgery_events):
        return unavailable("authoritative_time_missing")
    if any(
        (horizon_time is not None and horizon_time < event.surgery_end_time)
        or (horizon_time is None and horizon_date < event.surgery_end_time.date())
        for event in surgery_events
        if event.surgery_end_time is not None
    ):
        return unavailable("authoritative_time_conflict")

    mature = (
        any(horizon_time.date() > deadline for deadline in deadlines)
        if horizon_time is not None
        else any(horizon_date > deadline for deadline in deadlines)
    )
    if mature:
        return None

    facts: dict[str, Any] = {
        "verification_kind": "postoperative_three_day_window_not_mature",
        "surgery_times": [
            event.surgery_end_time.isoformat(sep=" ")
            for event in surgery_events
            if event.surgery_end_time is not None
        ],
        "deadline_dates": [deadline.isoformat() for deadline in deadlines],
    }
    if horizon_time is not None:
        facts["evaluation_time"] = horizon_time.isoformat(sep=" ")
    else:
        facts["evaluation_date"] = horizon_date.isoformat()
    return "not_applicable", "evaluation_window_not_mature", facts


def _postoperative_senior_round_evaluation_horizon(
    *,
    surgery_events: Sequence[_PostoperativeSurgeryEvent],
    horizon_rows: Sequence[Mapping[str, Any]],
    horizon_error: str,
) -> tuple[datetime | None, date | None, str]:
    """返回065逐台72小时核对可用的冻结评价终点。"""

    if horizon_error:
        return None, None, horizon_error
    if len(horizon_rows) != 1:
        return None, None, "authoritative_time_missing"

    row = horizon_rows[0]
    horizon_time = _parse_datetime(row.get("horizon_datetime"))
    raw_date = _clean(row.get("horizon_date"))
    horizon_date: date | None = None
    if raw_date:
        try:
            horizon_date = date.fromisoformat(raw_date)
        except ValueError:
            return None, None, "authoritative_time_missing"
    if horizon_time is None and horizon_date is None:
        return None, None, "authoritative_time_missing"
    if (
        horizon_time is not None
        and horizon_date is not None
        and horizon_time.date() != horizon_date
    ):
        return None, None, "authoritative_time_conflict"

    for event in surgery_events:
        assert event.surgery_end_time is not None
        try:
            before_surgery = (
                horizon_time < event.surgery_end_time
                if horizon_time is not None
                else horizon_date < event.surgery_end_time.date()
            )
        except TypeError:
            return None, None, "authoritative_time_conflict"
        if before_surgery:
            return None, None, "authoritative_time_conflict"
    return horizon_time, horizon_date, ""


async def execute_postoperative_family(
    *,
    rule_ids: Sequence[str],
    evidence_snapshot: Luxian0609EvidenceSnapshot,
    evidence_materials: Luxian0609EvidenceMaterialStore,
    llm_client: Any = None,
    source_cache: SourceRowsCache | None = None,
) -> ExtendedDocumentFamilyOutcome:
    """执行已选中的术后规则（04-05-01 / 04-05-02 / 04-05-03）。"""

    selected = tuple(
        dict.fromkeys(
            rule_id for rule_id in rule_ids if rule_id in POSTOPERATIVE_RULE_IDS
        )
    )
    if not selected:
        return ExtendedDocumentFamilyOutcome(decisions=())

    cache: SourceRowsCache = source_cache if source_cache is not None else {}
    selected_set = set(selected)

    surgery_record_rows, surgery_record_error = source_rows(
        evidence_materials, "surgery_record", cache=cache
    )
    surgery_applicability = resolve_surgery_applicability(
        snapshot=evidence_snapshot,
        materials=evidence_materials,
        preloaded_rows={
            "surgery_record": None if surgery_record_error else surgery_record_rows
        },
    )

    postop_first_rows, postop_first_error = (
        source_rows(evidence_materials, "postsurg_firstcourse_record", cache=cache)
        if {"LX0609-04-05-01", "LX0609-04-05-03"}.intersection(selected_set)
        else ((), "")
    )
    daily_rows, daily_error = (
        source_rows(evidence_materials, "daily_course_record", cache=cache)
        if "LX0609-04-05-01" in selected_set
        else ((), "")
    )
    daily_scope_complete = (
        evidence_materials.permits_absence("daily_course_record")
        if "LX0609-04-05-01" in selected_set
        else True
    )
    senior_rows, senior_error = (
        source_rows(evidence_materials, "senior_course_record", cache=cache)
        if {"LX0609-04-05-01", "LX0609-04-05-02"}.intersection(selected_set)
        else ((), "")
    )
    horizon_rows, horizon_error = (
        resolve_horizon_rows(evidence_snapshot, evidence_materials, cache=cache)
        if {"LX0609-04-05-01", "LX0609-04-05-02"}.intersection(selected_set)
        else ((), "")
    )

    decisions: list[RuleDecision] = []
    display: list[tuple[str, Mapping[str, Any]]] = []
    course_body_extractions: list[CourseBodyExtraction] = []
    postoperative_time_estimated_rules: set[str] = set()

    for rule_id in selected:
        if rule_id == "LX0609-04-05-03":
            gate_outcome = _surgery_applicability_outcome(surgery_applicability)
            surgery_events: tuple[_PostoperativeSurgeryEvent, ...] = ()
            linked_events: tuple[
                tuple[_PostoperativeSurgeryEvent, tuple[Mapping[str, Any], ...]], ...
            ] = ()
            linkage_error = ""
            if gate_outcome is not None:
                final_state, reason_code = gate_outcome
            else:
                surgery_events = _postoperative_surgery_events(
                    surgery_record_rows=surgery_record_rows,
                )
                if any(event.surgery_time_estimated for event in surgery_events):
                    postoperative_time_estimated_rules.add(rule_id)
                linkage_error = postop_first_error or (
                    "authoritative_time_missing" if not surgery_events else ""
                )
                if not linkage_error:
                    linked_events, linkage_error = _link_postoperative_first_course_records(
                        surgery_events=surgery_events,
                        postoperative_rows=postop_first_rows,
                    )
                if linkage_error:
                    final_state, reason_code = "data_gap", linkage_error
                else:
                    unmet_events = [
                        event.document_id
                        for event, linked_rows in linked_events
                        if not linked_rows
                    ]
                    final_state = "compliant" if not unmet_events else "non_compliant"
                    reason_code = (
                        "requirement_satisfied"
                        if not unmet_events
                        else "required_document_missing"
                    )
                    if unmet_events and not evidence_materials.permits_absence(
                        "postsurg_firstcourse_record"
                    ):
                        final_state, reason_code = "data_gap", "source_unavailable"
            if gate_outcome is None:
                display.append(
                    (
                        rule_id,
                        {
                            "verification_kind": "postoperative_first_course_presence_check",
                            "performed_surgery_count": len(surgery_events),
                            "postoperative_first_course_count": len(postop_first_rows),
                            "surgery_events": [
                                {
                                    **_event_display_base(event),
                                    "postoperative_first_course_document_ids": [
                                        _clean(row.get("document_id") or row.get("id"))
                                        for row in linked_rows
                                    ],
                                }
                                for event, linked_rows in linked_events
                            ],
                            "unmet_surgery_events": (
                                [
                                    event.document_id
                                    for event, linked_rows in linked_events
                                    if not linked_rows
                                ]
                                if not linkage_error
                                else []
                            ),
                        },
                    )
                )
            selected_postoperative_rows: list[Mapping[str, Any]] = []
            affirmative_non_surgical_operation = False
            if (
                gate_outcome == ("not_applicable", "performed_event_absent")
                and surgery_applicability.procedure_kind == "non_surgical_operation"
            ):
                selected_postoperative_rows.extend(
                    row
                    for row in surgery_record_rows
                    if catalog_surgery_state(row) is False
                )
                affirmative_non_surgical_operation = (
                    bool(selected_postoperative_rows)
                    and len(selected_postoperative_rows) == len(surgery_record_rows)
                    and evidence_materials.permits_absence("surgery_record")
                )
                if not affirmative_non_surgical_operation:
                    final_state, reason_code = "data_gap", "source_readiness_unproven"
            if surgery_events:
                if linkage_error:
                    selected_postoperative_rows.extend(
                        row for event in surgery_events for row in event.member_rows
                    )
                elif final_state == "non_compliant":
                    # 缺失首次病程时，客户证据只指向缺失的手术事件；已满足
                    # 事件的病程不应被这条缺陷结论顺带投影。
                    selected_postoperative_rows.extend(
                        row
                        for event, linked_rows in linked_events
                        if not linked_rows
                        for row in event.member_rows
                    )
                else:
                    selected_postoperative_rows.extend(
                        row
                        for event, _linked_rows in linked_events
                        for row in event.member_rows
                    )
                    selected_postoperative_rows.extend(
                        row
                        for _event, linked_rows in linked_events
                        for row in linked_rows
                    )
            postoperative_document_refs = _postoperative_document_refs(
                snapshot=evidence_snapshot,
                materials=evidence_materials,
                selected_rows=selected_postoperative_rows,
            )
            decisions.append(
                build_extended_decision(
                    rule_id=rule_id,
                    snapshot=evidence_snapshot,
                    source_keys=(
                        () if selected_postoperative_rows else ("surgery_record",)
                    ),
                    document_refs=postoperative_document_refs,
                    exact_document_refs=bool(selected_postoperative_rows),
                    final_state=final_state,
                    reason_code=reason_code,
                    affirmative_applicability=(
                        affirmative_non_surgical_operation
                        and bool(postoperative_document_refs)
                    ),
                )
            )
            continue

        if rule_id in {"LX0609-04-05-01", "LX0609-04-05-02"}:
            gate_outcome = _surgery_applicability_outcome(surgery_applicability)
            surgery_events = _postoperative_surgery_events(
                surgery_record_rows=surgery_record_rows,
            )
            if any(event.surgery_time_estimated for event in surgery_events):
                postoperative_time_estimated_rules.add(rule_id)
            selected_postoperative_rows = []
            if (
                gate_outcome == ("not_applicable", "performed_event_absent")
                and surgery_applicability.procedure_kind == "non_surgical_operation"
            ):
                selected_postoperative_rows.extend(
                    row
                    for row in surgery_record_rows
                    if catalog_surgery_state(row) is False
                )
            if gate_outcome is not None:
                final_state, reason_code = gate_outcome
            elif not surgery_events:
                final_state, reason_code = "data_gap", "authoritative_time_missing"
            elif any(event.surgery_end_time is None for event in surgery_events):
                final_state, reason_code = "data_gap", "authoritative_time_missing"
                display.append(
                    (
                        rule_id,
                        {
                            "verification_kind": "postoperative_surgery_event_time_check",
                            "performed_surgery_count": len(surgery_events),
                            "surgery_events": [
                                _event_display_base(event) for event in surgery_events
                            ],
                            "missing_surgery_end_events": [
                                event.document_id
                                for event in surgery_events
                                if event.surgery_end_time is None
                            ],
                        },
                    )
                )
            elif rule_id == "LX0609-04-05-01" and (
                window_gate := _postoperative_window_gate(
                    surgery_events=surgery_events,
                    horizon_rows=horizon_rows,
                    horizon_error=horizon_error,
                )
            ) is not None:
                final_state, reason_code, window_facts = window_gate
                display.append((rule_id, window_facts))
            elif rule_id == "LX0609-04-05-02" and (
                senior_round_horizon := _postoperative_senior_round_evaluation_horizon(
                    surgery_events=surgery_events,
                    horizon_rows=horizon_rows,
                    horizon_error=horizon_error,
                )
            )[2]:
                final_state, reason_code = "data_gap", senior_round_horizon[2]
                display.append(
                    (
                        rule_id,
                        {
                            "verification_kind": "postoperative_senior_round_window_unavailable",
                            "issue": reason_code,
                        },
                    )
                )
            elif (
                (daily_error or senior_error)
                if rule_id == "LX0609-04-05-01"
                else senior_error
            ):
                final_state, reason_code = "data_gap", (
                    daily_error or senior_error
                    if rule_id == "LX0609-04-05-01"
                    else senior_error
                )
            elif rule_id == "LX0609-04-05-01" and any(
                event.surgeon_names
                and all(
                    _physician_identity_is_masked(name)
                    for name in event.surgeon_names
                )
                and _postoperative_window_gate(
                    surgery_events=(event,),
                    horizon_rows=horizon_rows,
                    horizon_error=horizon_error,
                )
                is None
                for event in surgery_events
            ):
                final_state, reason_code = "data_gap", "association_failed"
            else:
                if rule_id == "LX0609-04-05-02":
                    evaluation_time, evaluation_date, _ = (
                        _postoperative_senior_round_evaluation_horizon(
                            surgery_events=surgery_events,
                            horizon_rows=horizon_rows,
                            horizon_error=horizon_error,
                        )
                    )
                    event_facts: list[dict[str, Any]] = []
                    unmet_events: list[dict[str, Any]] = []
                    not_mature_events: list[dict[str, Any]] = []
                    mature_events = tuple(
                        event
                        for event in surgery_events
                        if event.surgery_end_time is not None
                        and (
                            evaluation_time >= event.surgery_end_time + timedelta(hours=72)
                            if evaluation_time is not None
                            else evaluation_date
                            > (event.surgery_end_time + timedelta(hours=72)).date()
                        )
                    )
                    dated_candidates = tuple(
                        ("senior_course_record", ordinal, row)
                        for ordinal, row in enumerate(senior_rows)
                        if (value := _row_time(row)) is not None
                        and any(
                            event.surgery_end_time
                            <= value
                            <= event.surgery_end_time + timedelta(hours=72)
                            for event in mature_events
                        )
                    )
                    undated_senior_rows = tuple(
                        row
                        for row in senior_rows
                        if _row_time(row) is None
                        and isinstance(row.get("record_content"), str)
                        and row["record_content"].strip()
                    )
                    body_states: dict[tuple[str, int], str] = {}
                    body_issue = ""
                    extraction: CourseBodyExtraction | None = None
                    if dated_candidates:
                        candidates = (
                            *dated_candidates,
                            *(
                                ("senior_course_record", ordinal, row)
                                for ordinal, row in enumerate(senior_rows)
                                if _row_time(row) is None
                            ),
                        )
                        try:
                            body_documents, body_refs = course_body_candidate_inputs(
                                snapshot=evidence_snapshot,
                                materials=evidence_materials,
                                candidates=candidates,
                            )
                        except (ValueError, EvidenceMaterialUnavailable):
                            extraction = CourseBodyExtraction(
                                "data_gap", "source_readiness_unproven"
                            )
                        else:
                            extraction = await extract_course_body_facts(
                                body_documents, llm_client
                            )
                            body_states = {
                                key: extraction.states.get(ref, "unknown")
                                for key, ref in body_refs.items()
                            }
                        course_body_extractions.append(extraction)
                        body_issue = (
                            extraction.reason_code if extraction.state != "ready" else ""
                        )
                    unresolved_senior_semantics = False
                    unresolved_senior_time = False
                    unresolved_senior_body = False
                    for event in surgery_events:
                        assert event.surgery_end_time is not None
                        selected_postoperative_rows.extend(event.member_rows)
                        deadline = event.surgery_end_time + timedelta(hours=72)
                        window_mature = (
                            evaluation_time >= deadline
                            if evaluation_time is not None
                            else evaluation_date > deadline.date()
                        )
                        dated_senior_rows = tuple(
                            row
                            for row in senior_rows
                            if (value := _row_time(row)) is not None
                            and event.surgery_end_time <= value <= deadline
                        )
                        # 只核正文存在，不评价临床充分性；日期和纯签名不能代替查房正文。
                        matched_senior_rows = tuple(
                            row
                            for ordinal, row in enumerate(senior_rows)
                            if any(row is candidate for candidate in dated_senior_rows)
                            and body_states.get(("senior_course_record", ordinal))
                            == "present"
                        )
                        selected_postoperative_rows.extend(
                            matched_senior_rows or dated_senior_rows
                        )
                        senior_round_times = [
                            value.isoformat(sep=" ")
                            for row in matched_senior_rows
                            if (value := _row_time(row)) is not None
                        ]
                        event_fact = {
                            **_event_display_base(event),
                            "deadline": deadline.isoformat(sep=" "),
                            "senior_round_times": senior_round_times,
                            "window_state": (
                                "mature"
                                if window_mature
                                else "evaluation_window_not_mature"
                            ),
                        }
                        event_facts.append(event_fact)
                        if not window_mature:
                            not_mature_events.append(
                                {
                                    "document_id": event.document_id,
                                    "deadline": deadline.isoformat(sep=" "),
                                }
                            )
                        elif not senior_round_times and undated_senior_rows:
                            # 已有查房但无法定位日期，不能据此宣称72小时内缺少查房。
                            unresolved_senior_time = True
                            selected_postoperative_rows.extend(undated_senior_rows)
                        elif not senior_round_times and dated_senior_rows:
                            if any(
                                body_states.get(("senior_course_record", ordinal))
                                == "unknown"
                                for ordinal, row in enumerate(senior_rows)
                                if any(row is candidate for candidate in dated_senior_rows)
                            ):
                                unresolved_senior_semantics = True
                            else:
                                unresolved_senior_body = True
                        elif not senior_round_times:
                            unmet_events.append(
                                {
                                    "document_id": event.document_id,
                                    "senior_round_times": [],
                                }
                            )
                    if unmet_events:
                        # 逐台确定缺失（窗口到期、窗口内无任何查房、也无可能落入窗口的无日期查房）
                        # 不受其他台正文未决或模型失败影响。
                        final_state, reason_code = (
                            "non_compliant",
                            "required_document_missing",
                        )
                    elif body_issue:
                        assert extraction is not None
                        final_state, reason_code = (
                            (
                                "technical_error"
                                if extraction.state == "technical_error"
                                else "data_gap"
                            ),
                            body_issue,
                        )
                    elif unresolved_senior_semantics:
                        final_state, reason_code = (
                            "data_gap",
                            "semantic_extraction_unresolved",
                        )
                    elif unresolved_senior_time:
                        final_state, reason_code = (
                            "data_gap",
                            "authoritative_time_missing",
                        )
                    elif unresolved_senior_body:
                        final_state, reason_code = (
                            "data_gap",
                            "required_field_missing",
                        )
                    elif not_mature_events:
                        final_state, reason_code = (
                            "not_applicable",
                            "evaluation_window_not_mature",
                        )
                    else:
                        final_state, reason_code = "compliant", "requirement_satisfied"
                    senior_round_delivery_values = sorted(
                        {
                            value
                            for item in event_facts
                            for value in item["senior_round_times"]
                        }
                    )
                    if unmet_events:
                        senior_round_delivery_values = [
                            f"共{len(event_facts)}台手术中，{len(unmet_events)}台手术结束后72小时内"
                            "未查到上级医师查房",
                            *senior_round_delivery_values,
                        ]
                    legacy_summary_facts = {
                        "surgery_time": "；".join(
                            str(item["surgery_end_time"])
                            for item in event_facts
                            if item.get("surgery_end_time")
                        ),
                        "senior_round_times": senior_round_delivery_values,
                    }
                    if unmet_events or (
                        not body_issue
                        and not unresolved_senior_semantics
                        and (not unresolved_senior_body or unresolved_senior_time)
                    ):
                        display.append(
                            (
                                rule_id,
                                {
                                    "verification_kind": "postoperative_senior_round_window_unavailable",
                                    "issue": "authoritative_time_missing",
                                }
                                if unresolved_senior_time
                                else {
                                    "verification_kind": "postoperative_senior_round_check",
                                    "threshold_hours": 72,
                                    "performed_surgery_count": len(surgery_events),
                                    "surgery_events": event_facts,
                                    "unmet_surgery_events": unmet_events,
                                    "not_mature_surgery_events": not_mature_events,
                                    **(
                                        {
                                            "evaluation_time": evaluation_time.isoformat(
                                                sep=" "
                                            )
                                        }
                                        if evaluation_time is not None
                                        else {
                                            "evaluation_date": evaluation_date.isoformat()
                                        }
                                    ),
                                    **legacy_summary_facts,
                                },
                            )
                        )
                else:
                    event_facts = []
                    unmet_events = []
                    pending_window_events = []
                    missing_surgeon_events = []
                    definite_missing_events: list[str] = []
                    empty_body_events = []
                    unresolved_time_events = []
                    undated_course_rows = tuple(
                        row
                        for row in (*daily_rows, *senior_rows)
                        if _row_time(row) is None and _course_row_has_body(row)
                    )
                    for event in surgery_events:
                        assert event.surgery_end_time is not None
                        selected_postoperative_rows.extend(event.member_rows)
                        required_dates = {
                            (event.surgery_end_time + timedelta(days=offset)).date()
                            for offset in (1, 2, 3)
                        }
                        event_window = _postoperative_window_gate(
                            surgery_events=(event,),
                            horizon_rows=horizon_rows,
                            horizon_error=horizon_error,
                        )
                        if event_window is not None:
                            pending_window_events.append(event.document_id)
                            event_facts.append(
                                {
                                    **_event_display_base(event),
                                    "required_postop_dates": sorted(
                                        value.isoformat() for value in required_dates
                                    ),
                                    "covered_postop_dates": [],
                                    "surgeon_round_present": None,
                                    "preop_surgeon_round_present": None,
                                    "window_state": "evaluation_window_not_mature",
                                }
                            )
                            continue
                        dated_postop_rows = tuple(
                            row
                            for row in (*daily_rows, *senior_rows)
                            if (record_time := _row_time(row)) is not None
                            and record_time.date() in required_dates
                        )
                        empty_body_dates = {
                            record_time.date()
                            for row in dated_postop_rows
                            if not _course_row_has_body(row)
                            for record_time in (_row_time(row),)
                            if record_time is not None
                        }
                        postop_rows = tuple(
                            row
                            for row in dated_postop_rows
                            if _course_row_has_body(row)
                        )
                        covered_dates = _course_dates(postop_rows)
                        for required_date in required_dates.intersection(covered_dates):
                            # 每日覆盖只需一份实际有效病程；选择权威时间最早的一份
                            # 作为该日期的客户证据，不投影同日的全部候选病程。
                            selected_postoperative_rows.append(
                                min(
                                    (
                                        row
                                        for row in postop_rows
                                        if _row_time(row) is not None
                                        and _row_time(row).date() == required_date
                                    ),
                                    key=lambda row: _row_time(row) or datetime.max,
                                )
                            )
                        unresolved_empty_body_dates = empty_body_dates.difference(
                            covered_dates
                        )
                        for empty_date in unresolved_empty_body_dates:
                            selected_postoperative_rows.append(
                                min(
                                    (
                                        row
                                        for row in dated_postop_rows
                                        if _row_time(row) is not None
                                        and _row_time(row).date() == empty_date
                                        and not _course_row_has_body(row)
                                    ),
                                    key=lambda row: _row_time(row) or datetime.max,
                                )
                            )

                        def surgeon_round_in(
                            window_start: datetime,
                            window_end: datetime,
                            candidate_rows: Sequence[Mapping[str, Any]],
                        ) -> Mapping[str, Any] | None:
                            # 院方口径：术者须亲自在术前24小时内、术后24小时内查房。
                            return next(
                                (
                                    row
                                    for row in sorted(
                                        candidate_rows,
                                        key=lambda item: _row_time(item)
                                        or datetime.max,
                                    )
                                    if (record_time := _row_time(row)) is not None
                                    and window_start <= record_time <= window_end
                                    and _course_row_has_body(row)
                                    and event.surgeon_tokens
                                    and event.surgeon_tokens.intersection(
                                        _course_record_physician_tokens(row)
                                        | _title_round_physician_tokens(
                                            row,
                                            candidate_tokens=event.surgeon_tokens,
                                        )
                                        | _body_surgeon_round_tokens(
                                            row,
                                            candidate_tokens=event.surgeon_tokens,
                                        )
                                    )
                                ),
                                None,
                            )

                        # 用户口径（2026-10-22）：只有手术日期、无具体时刻时按自然日核对——
                        # 术前认手术前一日及当日，术后24小时认手术当日及次日。
                        date_only = event.surgery_time_date_only
                        surgeon_round_row = surgeon_round_in(
                            event.surgery_end_time,
                            event.surgery_end_time
                            + (
                                timedelta(days=2) - timedelta(microseconds=1)
                                if date_only
                                else timedelta(hours=_SURGEON_ROUND_WINDOW_HOURS)
                            ),
                            # 术者本人签署的术后首次病程也是术后查房记录；
                            # 仅参与身份/24小时时窗核对，不替代术后三日病程覆盖。
                            (*daily_rows, *senior_rows, *postop_first_rows),
                        )
                        preop_round_row = (
                            surgeon_round_in(
                                event.surgery_begin_time
                                - timedelta(hours=_SURGEON_ROUND_WINDOW_HOURS),
                                event.surgery_begin_time
                                + (
                                    timedelta(days=1) - timedelta(microseconds=1)
                                    if date_only
                                    else timedelta()
                                ),
                                (*daily_rows, *senior_rows),
                            )
                            if event.surgery_begin_time is not None
                            else None
                        )
                        for round_row in (preop_round_row, surgeon_round_row):
                            if round_row is not None:
                                selected_postoperative_rows.append(round_row)
                        surgeon_round = surgeon_round_row is not None
                        preop_surgeon_round = preop_round_row is not None
                        missing_dates = sorted(
                            item.isoformat()
                            for item in required_dates.difference(covered_dates)
                        )
                        event_facts.append(
                            {
                                **_event_display_base(event),
                                "required_postop_dates": sorted(
                                    item.isoformat() for item in required_dates
                                ),
                                "covered_postop_dates": sorted(
                                    item.isoformat() for item in covered_dates
                                ),
                                "surgeon_round_present": surgeon_round,
                                "preop_surgeon_round_present": preop_surgeon_round,
                            }
                        )
                        if not event.surgeon_tokens:
                            missing_surgeon_events.append(event.document_id)
                        if unresolved_empty_body_dates:
                            empty_body_events.append(event.document_id)
                        if event.surgery_begin_time is None and not preop_surgeon_round:
                            # 无手术开始时间时无法核对术前24小时术者查房，不能判缺失。
                            unresolved_time_events.append(event.document_id)
                            event_facts[-1]["course_time_unresolved"] = True
                        elif (
                            missing_dates
                            or not surgeon_round
                            or not preop_surgeon_round
                        ):
                            if undated_course_rows:
                                # 候选不能定日时，既不能补齐，也不能确认该手术缺项。
                                unresolved_time_events.append(event.document_id)
                                event_facts[-1]["course_time_unresolved"] = True
                                selected_postoperative_rows.extend(undated_course_rows)
                            else:
                                # 空正文日仅为未决，不算确定缺失日。
                                if set(missing_dates).difference(
                                    item.isoformat()
                                    for item in unresolved_empty_body_dates
                                ):
                                    definite_missing_events.append(event.document_id)
                                unmet_events.append(
                                    {
                                        "document_id": event.document_id,
                                        "missing_postop_dates": missing_dates,
                                        "surgeon_round_present": surgeon_round,
                                        "preop_surgeon_round_present": preop_surgeon_round,
                                    }
                                )
                    if (
                        (definite_missing_events or unmet_events)
                        and rule_id == "LX0609-04-05-01"
                        and not daily_scope_complete
                    ):
                        final_state, reason_code = "data_gap", "source_unavailable"
                    elif definite_missing_events:
                        # 已确定某个术后日完全没有病程记录，属确定缺陷，不被术者身份等
                        # 其他资料缺口遮蔽。
                        final_state, reason_code = (
                            "non_compliant",
                            "requirement_violated",
                        )
                    elif (
                        missing_surgeon_events
                        or empty_body_events
                        or unresolved_time_events
                    ):
                        final_state, reason_code = (
                            "data_gap",
                            "required_field_missing",
                        )
                    elif not unmet_events and pending_window_events:
                        final_state, reason_code = (
                            "not_applicable",
                            "evaluation_window_not_mature",
                        )
                    else:
                        final_state = (
                            "compliant" if not unmet_events else "non_compliant"
                        )
                        reason_code = (
                            "requirement_satisfied"
                            if not unmet_events
                            else "requirement_violated"
                        )
                    legacy_summary_facts = {
                        "surgery_time": "；".join(
                            str(item["surgery_end_time"])
                            for item in event_facts
                            if item.get("surgery_end_time")
                        ),
                        "required_postop_dates": sorted(
                            {
                                value
                                for item in event_facts
                                for value in item["required_postop_dates"]
                            }
                        ),
                        "covered_postop_dates": sorted(
                            {
                                value
                                for item in event_facts
                                for value in item["covered_postop_dates"]
                            }
                        ),
                        "surgeon_round_present": all(
                            item["surgeon_round_present"] is True
                            for item in event_facts
                        ),
                        "preop_surgeon_round_present": all(
                            item["preop_surgeon_round_present"] is True
                            for item in event_facts
                        ),
                    }
                    display.append(
                        (
                            rule_id,
                            {
                                "verification_kind": "postoperative_three_day_coverage_check",
                                "performed_surgery_count": len(surgery_events),
                                "surgery_events": event_facts,
                                "unmet_surgery_events": unmet_events,
                                "missing_surgeon_events": missing_surgeon_events,
                                "unresolved_course_time_events": unresolved_time_events,
                                **legacy_summary_facts,
                            },
                        )
                    )
            postoperative_document_refs = _postoperative_document_refs(
                snapshot=evidence_snapshot,
                materials=evidence_materials,
                selected_rows=selected_postoperative_rows,
            )
            decisions.append(
                build_extended_decision(
                    rule_id=rule_id,
                    snapshot=evidence_snapshot,
                    source_keys=(
                        () if selected_postoperative_rows else ("surgery_record",)
                    ),
                    document_refs=postoperative_document_refs,
                    exact_document_refs=bool(selected_postoperative_rows),
                    final_state=final_state,
                    reason_code=reason_code,
                )
            )
            continue

    if postoperative_time_estimated_rules:
        display = [
            (rule_id, {**facts, "surgery_time_basis": "begin_time"})
            if rule_id in postoperative_time_estimated_rules
            and isinstance(facts, Mapping)
            else (rule_id, facts)
            for rule_id, facts in display
        ]

    return ExtendedDocumentFamilyOutcome(
        decisions=tuple(decisions),
        display_facts=tuple(display),
        llm_call_count=sum(item.llm_call_count for item in course_body_extractions),
        prompt_tokens=sum(item.prompt_tokens for item in course_body_extractions),
        completion_tokens=sum(
            item.completion_tokens for item in course_body_extractions
        ),
        total_tokens=sum(item.total_tokens for item in course_body_extractions),
        api_time=sum(item.api_time for item in course_body_extractions),
    )


__all__ = [
    "POSTOPERATIVE_RULE_IDS",
    "execute_postoperative_family",
]
