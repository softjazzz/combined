"""LX0609 基础时限族的原生确定性执行器。"""

from __future__ import annotations

from datetime import date, datetime, timedelta
import re
from typing import Any, Mapping, Sequence

from .decision_model import (
    ApplicabilityState,
    EvidenceState,
    QcDirection,
    RuleDecision,
)
from .evidence_material import (
    EvidenceMaterialTruncated,
    Luxian0609EvidenceMaterialStore,
)
from .evidence_snapshot import Luxian0609EvidenceSnapshot
from .native_execution import NativeExecutionResult, build_luxian_0609_native_result
from .source_evidence_reader import (
    authoritative_document_time_value,
    build_luxian_0609_course_round_timeline_from_rows,
    parse_luxian_0609_rescue_end_time,
    read_luxian_0609_course_round_timeline,
)
from ..luxian_0609_rule_catalog import load_luxian_0609_rules
from ..luxian_0609_programmatic_rules import evaluate_luxian_0609_programmatic_rules


BASIC_TIMELINESS_RULE_IDS = (
    "LX0609-001",
    "LX0609-002",
    "LX0609-004",
    "LX0609-005",
    "LX0609-006",
)
EXECUTOR_KEY = "basic_timeliness"
_FIRST_COURSE_RULE_ID = "LX0609-002"
_ADMISSION_ANCHOR_RULE_IDS = frozenset(
    {"LX0609-001", "LX0609-005", "LX0609-006"}
)
_COURSE_SOURCE_RULE_IDS = frozenset({"LX0609-005", "LX0609-006"})
_TRUSTED_ADMISSION_TIME_BASES = frozenset(
    {
        "cdm_inpat_registration_admission_datetime",
        "timeline_primary_admission_datetime",
    }
)
_CUSTOMER_APPROVED_ADMISSION_TIME_BASES = frozenset(
    {
        # 0426 存量数据无住院登记时间；入院记录源的 record_time
        # 是当前客户批准的入院时限锨点，仅限该固定来源基础。
        "admission_record_record_time_fallback",
    }
)
_FIRST_COURSE_BODY_FIELDS = (
    "case_characteristic",
    "record_content",
    "content",
    "assembled_text",
    "raw_text",
)
_MIN_FIRST_COURSE_BODY_CHARS = 6
_TYPED_RULE_IDS = (
    "LX0609-001",
    "LX0609-002",
    "LX0609-004",
    "LX0609-005",
    "LX0609-006",
)
_TYPED_SOURCE_KEYS_BY_RULE = {
    "LX0609-001": (
        "admission_record",
        "discharge_record",
        "inpat_registration",
    ),
    "LX0609-002": (
        "admission_record",
        "first_course_record",
        "inpat_registration",
    ),
    "LX0609-004": ("rescue_record",),
    "LX0609-005": (
        "admission_record",
        "daily_course_record",
        "discharge_record",
        "inpat_registration",
        "senior_course_record",
    ),
    "LX0609-006": (
        "admission_record",
        "daily_course_record",
        "discharge_record",
        "inpat_registration",
        "senior_course_record",
    ),
}
_ATTENDING_MARKERS = ("主治医师", "主治查房", "代主治医师", "代主治查房")
_SENIOR_MARKERS = ("副主任医师", "主任医师", "副主任查房", "主任查房", "高级职称")
_AUTHORITATIVE_DATETIME_PATTERN = re.compile(
    r"^\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}(?::\d{2}(?:\.\d{1,6})?)?$"
)
_INLINE_RESCUE_END_TIME_PATTERN = re.compile(
    r"(?<![\w\u4e00-\u9fff])抢救结束时间\s*[:：]\s*(?P<value>"
    r"\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}(?::\d{2})?"
    r"|\d{4}年\d{1,2}月\d{1,2}日\s+\d{1,2}:\d{2}(?::\d{2})?"
    r")"
)


def _is_substantive_first_course_text(value: Any) -> bool:
    if not isinstance(value, str):
        return False
    normalized = re.sub(r"[\W_]+", "", value, flags=re.UNICODE)
    shell_remainder = re.sub(
        r"(?:首次病程记录|首次病程|记录时间|提交时间|文书类型|文书编号|正文|"
        r"sourcetable|firstcourserecord|assemblystatus|partial|"
        r"年|月|日|时|分|秒|\d+)",
        "",
        normalized,
        flags=re.IGNORECASE,
    )
    return len(shell_remainder) >= _MIN_FIRST_COURSE_BODY_CHARS


def _technical_result(rule_id: str, reason_code: str) -> dict[str, Any]:
    return build_luxian_0609_native_result(
        rule_id=rule_id,
        final_state="technical_error",
        finding_kind="technical_failure",
        reason_code=reason_code,
    )


def _has_substantive_first_course_body(
    evidence_payload: dict[str, Any] | None,
) -> bool:
    if not isinstance(evidence_payload, dict):
        return False
    timeline = evidence_payload.get("programmatic_timeline")
    if not isinstance(timeline, dict):
        return False
    documents = timeline.get("documents")
    if not isinstance(documents, dict):
        return False
    rows = documents.get("first_course_record")
    if not isinstance(rows, (list, tuple)):
        return False
    for row in rows:
        if not isinstance(row, dict):
            continue
        for field in _FIRST_COURSE_BODY_FIELDS:
            value = row.get(field)
            if _is_substantive_first_course_text(value):
                return True
    return False


def _first_course_data_gap_result() -> dict[str, Any]:
    return build_luxian_0609_native_result(
        rule_id=_FIRST_COURSE_RULE_ID,
        final_state="data_gap",
        finding_kind="source_data_gap",
        reason_code="first_course_substantive_content_unavailable",
    )


def _approved_admission_anchor_available(
    evidence_payload: dict[str, Any] | None,
) -> bool:
    if not isinstance(evidence_payload, dict):
        return False
    timeline = evidence_payload.get("programmatic_timeline")
    if not isinstance(timeline, dict):
        return False
    basis = timeline.get("admission_time_basis")
    admission_time = str(timeline.get("admission_time") or "").strip()
    documents = timeline.get("documents")
    admission_rows = (
        documents.get("admission_record") if isinstance(documents, dict) else None
    )
    approved_record_time_bound = (
        basis in _CUSTOMER_APPROVED_ADMISSION_TIME_BASES
        and isinstance(admission_rows, (list, tuple))
        and any(
            isinstance(row, dict)
            and str(row.get("source_table") or "").strip().lower()
            == "admission_record"
            and str(row.get("authored_at") or "").strip() == admission_time
            for row in admission_rows
        )
    )
    return bool(admission_time) and (
        (
            timeline.get("admission_time_trusted") is True
            and basis in _TRUSTED_ADMISSION_TIME_BASES
        )
        or approved_record_time_bound
    )


def _admission_anchor_data_gap_result(rule_id: str) -> dict[str, Any]:
    return build_luxian_0609_native_result(
        rule_id=rule_id,
        final_state="data_gap",
        finding_kind="source_data_gap",
        reason_code="trusted_admission_anchor_unavailable",
    )


def _course_source_data_gap_result(rule_id: str) -> dict[str, Any]:
    return build_luxian_0609_native_result(
        rule_id=rule_id,
        final_state="data_gap",
        finding_kind="source_data_gap",
        reason_code="course_source_read_unavailable",
    )


def _authoritative_time(value: Any) -> datetime | None:
    """仅接受权威字段整值，不从标题或正文提取时间。"""

    if isinstance(value, datetime):
        return value if value.tzinfo is None else None
    if not isinstance(value, str):
        return None
    normalized = value.strip()
    if not _AUTHORITATIVE_DATETIME_PATTERN.fullmatch(normalized):
        return None
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        return None
    return parsed if parsed.tzinfo is None else None


def _rescue_end_time(value: Any) -> datetime | None:
    """兼容开始、结束时间写在同一行，同时拒绝“拟抢救结束时间”。"""

    parsed = parse_luxian_0609_rescue_end_time(value)
    if parsed is not None or not isinstance(value, str):
        return parsed
    match = _INLINE_RESCUE_END_TIME_PATTERN.search(value)
    if match is None:
        return None
    normalized = match.group("value").strip()
    for date_format in (
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d %H:%M",
        "%Y年%m月%d日 %H:%M:%S",
        "%Y年%m月%d日 %H:%M",
    ):
        try:
            return datetime.strptime(normalized, date_format)
        except ValueError:
            continue
    return None


def _authoritative_date(value: Any) -> date | None:
    """仅接受权威日期字段整值；日期不能伪装成精确入院时刻。"""

    if isinstance(value, datetime):
        return None
    if isinstance(value, date):
        return value
    if not isinstance(value, str):
        return None
    normalized = value.strip()
    try:
        parsed = date.fromisoformat(normalized)
    except ValueError:
        return None
    return parsed if parsed.isoformat() == normalized else None


def _elapsed_state_from_date_range(
    *,
    event_time: datetime,
    admission_date: date,
    threshold: timedelta,
) -> str:
    """在整日入院区间上只返回可证明的结论，中间边界保持未知。"""

    range_start = datetime.combine(admission_date, datetime.min.time())
    range_end = range_start + timedelta(days=1)
    if event_time < range_start:
        return "before"
    if event_time - range_start <= threshold:
        return "within"
    if event_time - range_end >= threshold:
        return "over"
    return "ambiguous"


def _typed_basic_decisions(
    *,
    rule_ids: tuple[str, ...],
    snapshot: Luxian0609EvidenceSnapshot,
    materials: Luxian0609EvidenceMaterialStore,
    customer_display_facts: list[tuple[str, Mapping[str, Any]]] | None = None,
) -> tuple[RuleDecision, ...]:
    """001/005/006 共用一次入院锚点，只做权威字段时间计算。"""

    if (
        type(snapshot) is not Luxian0609EvidenceSnapshot
        or type(materials) is not Luxian0609EvidenceMaterialStore
        or materials.snapshot_hash != snapshot.snapshot_hash
    ):
        raise ValueError("typed basic evidence session mismatch")
    observation_by_source = {
        item.source_key: item for item in snapshot.observations
    }
    evaluator_version = "basic-timeliness-authoritative-v1"

    allowed_sources = {
        "LX0609-001": (
            "admission_record",
            "discharge_record",
            "inpat_registration",
        ),
        "LX0609-002": (
            "admission_record",
            "first_course_record",
            "inpat_registration",
        ),
        "LX0609-004": ("rescue_record",),
        "LX0609-005": (
            "admission_record",
            "daily_course_record",
            "discharge_record",
            "inpat_registration",
            "senior_course_record",
        ),
        "LX0609-006": (
            "admission_record",
            "daily_course_record",
            "discharge_record",
            "inpat_registration",
            "senior_course_record",
        ),
    }

    def make(
        rule_id: str,
        *,
        evidence_state: EvidenceState,
        qc_direction: QcDirection,
        reason_code: str,
        confidence: float | None,
        sources: tuple[str, ...] | None = None,
        applicability: ApplicabilityState | None = None,
    ) -> RuleDecision:
        refs = tuple(
            observation_by_source[source_key].snapshot_ref.removeprefix("sha256:")
            for source_key in (sources or allowed_sources[rule_id])
            if source_key in observation_by_source
        )
        return RuleDecision(
            rule_id=rule_id,
            snapshot_hash=snapshot.snapshot_hash,
            applicability=(
                applicability
                if applicability is not None
                else (
                    ApplicabilityState.ERROR
                    if evidence_state is EvidenceState.TECHNICAL_ERROR
                    else ApplicabilityState.APPLICABLE
                )
            ),
            evidence_state=evidence_state,
            qc_direction=qc_direction,
            reason_code=reason_code,
            fact_refs=refs,
            evaluator_version=evaluator_version,
            confidence=confidence,
        )

    def gap(
        rule_id: str,
        reason_code: str,
        *,
        technical: bool = False,
    ) -> RuleDecision:
        return make(
            rule_id,
            evidence_state=(
                EvidenceState.TECHNICAL_ERROR
                if technical
                else EvidenceState.DATA_GAP
            ),
            qc_direction=QcDirection.UNKNOWN,
            reason_code=reason_code,
            confidence=None,
        )

    required_source_keys = {
        source_key
        for rule_id in rule_ids
        for source_key in _TYPED_SOURCE_KEYS_BY_RULE[rule_id]
    }
    if any(source_key not in observation_by_source for source_key in required_source_keys):
        return tuple(gap(rule_id, "snapshot_mismatch", technical=True) for rule_id in rule_ids)

    def source_issue(
        source_keys: tuple[str, ...],
        *,
        allow_unavailable: frozenset[str] = frozenset(),
    ) -> tuple[str, bool] | None:
        for source_key in source_keys:
            observation = observation_by_source[source_key]
            if observation.query_state.value == "error":
                return "source_query_error", True
            if (
                observation.query_state.value == "unavailable"
                and source_key not in allow_unavailable
            ):
                return "source_unavailable", False
            if observation.completeness.value == "truncated":
                return "source_truncated", False
        return None

    def rows(source_key: str) -> tuple[Mapping[str, Any], ...]:
        try:
            return tuple(materials.rows(source_key))
        except EvidenceMaterialTruncated:
            raise
        except Exception as exc:
            raise ValueError("snapshot material mismatch") from exc

    admission_needed = any(
        rule_id in {"LX0609-001", "LX0609-002", "LX0609-005", "LX0609-006"}
        for rule_id in rule_ids
    )
    admission_issue: tuple[str, bool] | None = None
    registration_issue: tuple[str, bool] | None = None
    discharge_issue: tuple[str, bool] | None = None
    admission_rows: tuple[Mapping[str, Any], ...] = ()
    registration_rows: tuple[Mapping[str, Any], ...] = ()
    discharge_rows: tuple[Mapping[str, Any], ...] = ()
    if admission_needed:
        admission_issue = source_issue(("admission_record",))
        registration_issue = source_issue(
            ("inpat_registration",),
            allow_unavailable=frozenset({"inpat_registration"}),
        )
        try:
            admission_rows = (
                rows("admission_record")
                if observation_by_source["admission_record"].query_state.value
                in {"available", "empty"}
                else ()
            )
            registration_rows = (
                rows("inpat_registration")
                if observation_by_source["inpat_registration"].query_state.value
                in {"available", "empty"}
                else ()
            )
        except EvidenceMaterialTruncated:
            admission_issue = ("source_truncated", False)
            admission_rows = registration_rows = ()
        except ValueError:
            admission_issue = ("snapshot_mismatch", True)
            admission_rows = registration_rows = ()
    if any(rule_id in _ADMISSION_ANCHOR_RULE_IDS for rule_id in rule_ids):
        discharge_issue = source_issue(("discharge_record",))
        try:
            discharge_rows = (
                rows("discharge_record")
                if observation_by_source["discharge_record"].query_state.value
                in {"available", "empty"}
                else ()
            )
        except EvidenceMaterialTruncated:
            discharge_issue = ("source_truncated", False)
            discharge_rows = ()
        except ValueError:
            discharge_issue = ("snapshot_mismatch", True)
            discharge_rows = ()

    # 001 的合规解释必须能回到实际被选中的入院记录。时间计算仍只使用
    # 权威 record time；这里额外保留同一行的内部文书 ID，供安全聚合层生成
    # 不可逆引用。没有可靠 ID 时只展示时间事实，不猜测文书。
    admission_record_events = tuple(
        sorted(
            (
                (
                    parsed,
                    str(row.get("document_id") or "").strip() or None,
                )
                for row in admission_rows
                if (
                    parsed := _authoritative_time(
                        authoritative_document_time_value(row)
                    )
                )
                is not None
            ),
            key=lambda item: (item[0], item[1] or ""),
        )
    )
    admission_record_times = tuple(event[0] for event in admission_record_events)
    admission_record_admission_times = tuple(
        sorted(
            parsed
            for row in admission_rows
            if (
                parsed := _authoritative_time(row.get("admission_datetime"))
            )
            is not None
        )
    )
    registration_times = tuple(
        sorted(
            parsed
            for row in registration_rows
            if (
                parsed := _authoritative_time(
                    row.get("admission_datetime") or row.get("admission_time")
                )
            )
            is not None
        )
    )
    discharge_admission_dates = tuple(
        sorted(
            {
                parsed
                for row in discharge_rows
                if (
                    parsed := _authoritative_date(row.get("admission_date"))
                )
                is not None
            }
        )
    )

    def admission_anchor(
        rule_id: str,
    ) -> tuple[datetime | None, date | None, RuleDecision | None]:
        if admission_issue is not None:
            reason, technical = admission_issue
            return None, None, gap(rule_id, reason, technical=technical)
        if registration_issue is not None:
            reason, technical = registration_issue
            return None, None, gap(rule_id, reason, technical=technical)
        registration_state = observation_by_source[
            "inpat_registration"
        ].query_state.value
        if registration_state == "available" and registration_times:
            return registration_times[0], None, None
        if admission_record_admission_times:
            return admission_record_admission_times[0], None, None
        if rule_id not in _ADMISSION_ANCHOR_RULE_IDS:
            return None, None, gap(rule_id, "authoritative_time_missing")
        if discharge_issue is not None:
            reason, technical = discharge_issue
            return None, None, gap(rule_id, reason, technical=technical)
        if len(discharge_admission_dates) != 1:
            return None, None, gap(rule_id, "authoritative_time_missing")
        return None, discharge_admission_dates[0], None

    def conclusive(
        rule_id: str,
        direction: QcDirection,
        reason_code: str,
    ) -> RuleDecision:
        return make(
            rule_id,
            evidence_state=EvidenceState.SUFFICIENT,
            qc_direction=direction,
            reason_code=reason_code,
            confidence=1.0,
        )

    def not_applicable(rule_id: str, reason_code: str) -> RuleDecision:
        return make(
            rule_id,
            evidence_state=EvidenceState.SUFFICIENT,
            qc_direction=QcDirection.UNKNOWN,
            reason_code=reason_code,
            confidence=1.0,
            applicability=ApplicabilityState.NOT_APPLICABLE,
        )

    def add_customer_fact(rule_id: str, facts: Mapping[str, Any]) -> None:
        """仅保留时限解释需要的标量事实；原始文书仍留在证据材料仓。"""

        if customer_display_facts is not None:
            customer_display_facts.append((rule_id, dict(facts)))

    def format_time(value: datetime | None) -> str:
        return value.strftime("%Y-%m-%d %H:%M:%S") if value is not None else ""

    def timeliness_fact(
        *,
        rule_id: str,
        target_document: str,
        source_label: str,
        state: str,
        threshold_hours: int,
        anchor: datetime | None,
        anchor_date: date | None = None,
        observed: datetime | None = None,
        source_document_id: str | None = None,
        failure_kind: str = "timeliness_requirement_not_met",
    ) -> dict[str, Any]:
        facts: dict[str, Any] = {
            "failure_kind": failure_kind,
            "target_document": target_document,
            "source_label": source_label,
            "timeliness_state": state,
            "threshold_hours": threshold_hours,
        }
        if anchor is not None:
            facts["anchor_time"] = format_time(anchor)
        elif anchor_date is not None:
            facts["anchor_date"] = anchor_date.isoformat()
        if observed is not None:
            facts["observed_time"] = format_time(observed)
        if anchor is not None and observed is not None:
            elapsed_hours = (observed - anchor).total_seconds() / 3600
            facts["elapsed_hours"] = round(elapsed_hours, 2)
            if (
                rule_id == "LX0609-002"
                and state == "late"
                and elapsed_hours > threshold_hours
            ):
                facts["overdue_hours"] = round(
                    elapsed_hours - threshold_hours,
                    2,
                )
        if source_document_id:
            # 仅供聚合层生成不可逆文书引用；安全投影不得回传该内部 ID。
            facts["source_document_id"] = source_document_id
        return facts

    decisions: list[RuleDecision] = []
    for rule_id in rule_ids:
        if rule_id == "LX0609-002":
            anchor, _anchor_date, anchor_gap = admission_anchor(rule_id)
            if anchor_gap is not None or anchor is None:
                decisions.append(
                    anchor_gap or gap(rule_id, "authoritative_time_missing")
                )
                continue
            first_course_issue = source_issue(("first_course_record",))
            try:
                first_course_rows = (
                    rows("first_course_record")
                    if observation_by_source["first_course_record"].query_state.value
                    in {"available", "empty"}
                    else ()
                )
            except EvidenceMaterialTruncated:
                first_course_issue = ("source_truncated", False)
                first_course_rows = ()
            except ValueError:
                first_course_issue = ("snapshot_mismatch", True)
                first_course_rows = ()
            if first_course_issue is not None:
                reason, technical = first_course_issue
                decisions.append(gap(rule_id, reason, technical=technical))
                continue
            if not first_course_rows:
                decisions.append(gap(rule_id, "source_readiness_unproven"))
                continue
            complete_events: list[tuple[datetime, str | None]] = []
            incomplete = False
            for row in first_course_rows:
                record_time = _authoritative_time(
                    authoritative_document_time_value(row)
                )
                substantive = any(
                    _is_substantive_first_course_text(row.get(field))
                    for field in _FIRST_COURSE_BODY_FIELDS
                )
                if record_time is None or not substantive:
                    incomplete = True
                else:
                    complete_events.append(
                        (
                            record_time,
                            str(row.get("document_id") or "").strip() or None,
                        )
                    )
            complete_times = [value for value, _document_id in complete_events]
            deltas = sorted(value - anchor for value in complete_times)
            if any(timedelta(0) <= delta <= timedelta(hours=8) for delta in deltas):
                decisions.append(
                    conclusive(
                        rule_id,
                        QcDirection.SATISFIED,
                        "requirement_within_threshold",
                    )
                )
                observed, source_document_id = min(
                    (
                        item
                        for item in complete_events
                        if timedelta(0) <= item[0] - anchor <= timedelta(hours=8)
                    ),
                    key=lambda item: item[0],
                )
                add_customer_fact(
                    rule_id,
                    timeliness_fact(
                        rule_id=rule_id,
                        target_document="first_course_record",
                        source_label="首次病程记录",
                        state="within",
                        threshold_hours=8,
                        anchor=anchor,
                        observed=observed,
                        source_document_id=source_document_id,
                        failure_kind="timeliness_requirement_satisfied",
                    ),
                )
            elif incomplete:
                decisions.append(gap(rule_id, "required_field_missing"))
            elif any(delta < timedelta(0) for delta in deltas):
                decisions.append(
                    make(
                        rule_id,
                        evidence_state=EvidenceState.CONFLICT,
                        qc_direction=QcDirection.UNKNOWN,
                        reason_code="evidence_conflict",
                        confidence=None,
                    )
                )
            elif deltas:
                decision = conclusive(
                    rule_id, QcDirection.DEFECT, "threshold_exceeded"
                )
                decisions.append(decision)
                add_customer_fact(
                    rule_id,
                    timeliness_fact(
                        rule_id=rule_id,
                        target_document="first_course_record",
                        source_label="首次病程记录",
                        state="late",
                        threshold_hours=8,
                        anchor=anchor,
                        observed=min(complete_times),
                    ),
                )
            else:
                decisions.append(gap(rule_id, "required_field_missing"))
            continue

        if rule_id == "LX0609-004":
            rescue_issue = source_issue(("rescue_record",))
            try:
                rescue_rows = (
                    rows("rescue_record")
                    if observation_by_source["rescue_record"].query_state.value
                    in {"available", "empty"}
                    else ()
                )
            except EvidenceMaterialTruncated:
                rescue_issue = ("source_truncated", False)
                rescue_rows = ()
            except ValueError:
                rescue_issue = ("snapshot_mismatch", True)
                rescue_rows = ()
            if rescue_issue is not None:
                reason, technical = rescue_issue
                decisions.append(gap(rule_id, reason, technical=technical))
                continue
            if not rescue_rows:
                decisions.append(not_applicable(rule_id, "trigger_absent_complete"))
                continue
            rescue_timeline: list[tuple[timedelta, datetime, datetime, str]] = []
            incomplete = False
            for row in rescue_rows:
                record_time = _authoritative_time(row.get("record_time"))
                rescue_end = _rescue_end_time(row.get("record_content"))
                if record_time is None or rescue_end is None:
                    incomplete = True
                    continue
                delta = record_time - rescue_end
                if delta < timedelta(0):
                    incomplete = True
                else:
                    rescue_timeline.append(
                        (
                            delta,
                            rescue_end,
                            record_time,
                            str(row.get("document_id") or "").strip(),
                        )
                    )
            overdue = next(
                (
                    item
                    for item in sorted(rescue_timeline, key=lambda item: item[0])
                    if item[0] > timedelta(hours=6)
                ),
                None,
            )
            if overdue is not None:
                _delta, rescue_end, record_time, document_id = overdue
                decisions.append(
                    conclusive(rule_id, QcDirection.DEFECT, "threshold_exceeded")
                )
                add_customer_fact(
                    rule_id,
                    timeliness_fact(
                        rule_id=rule_id,
                        target_document="rescue_record",
                        source_label="抢救记录",
                        state="late",
                        threshold_hours=6,
                        anchor=rescue_end,
                        observed=record_time,
                        source_document_id=document_id or None,
                    ),
                )
            elif incomplete:
                decisions.append(gap(rule_id, "required_field_missing"))
            elif rescue_timeline:
                decisions.append(
                    conclusive(
                        rule_id,
                        QcDirection.SATISFIED,
                        "requirement_within_threshold",
                    )
                )
                _delta, rescue_end, record_time, document_id = max(
                    rescue_timeline,
                    key=lambda item: item[0],
                )
                add_customer_fact(
                    rule_id,
                    timeliness_fact(
                        rule_id=rule_id,
                        target_document="rescue_record",
                        source_label="抢救记录",
                        state="within",
                        threshold_hours=6,
                        anchor=rescue_end,
                        observed=record_time,
                        source_document_id=document_id or None,
                        failure_kind="timeliness_requirement_satisfied",
                    ),
                )
            else:
                decisions.append(gap(rule_id, "required_field_missing"))
            continue

        if rule_id == "LX0609-001":
            if admission_issue is not None:
                reason, technical = admission_issue
                decisions.append(gap(rule_id, reason, technical=technical))
                continue
            if not admission_rows:
                decision = conclusive(
                    rule_id,
                    QcDirection.DEFECT,
                    "required_document_missing",
                )
                decisions.append(decision)
                add_customer_fact(
                    rule_id,
                    timeliness_fact(
                        rule_id=rule_id,
                        target_document="admission_record",
                        source_label="入院记录",
                        state="missing",
                        threshold_hours=24,
                        anchor=None,
                    ),
                )
                continue
            if not admission_record_times:
                decisions.append(gap(rule_id, "authoritative_time_missing"))
                continue
            anchor, anchor_date, anchor_gap = admission_anchor(rule_id)
            if anchor_gap is not None or (
                anchor is None and anchor_date is None
            ):
                decisions.append(anchor_gap or gap(rule_id, "authoritative_time_missing"))
                continue
            if anchor is not None:
                delta_state = (
                    "before"
                    if admission_record_times[0] < anchor
                    else (
                        "within"
                        if admission_record_times[0] - anchor
                        <= timedelta(hours=24)
                        else "over"
                    )
                )
            else:
                assert anchor_date is not None
                delta_state = _elapsed_state_from_date_range(
                    event_time=admission_record_times[0],
                    admission_date=anchor_date,
                    threshold=timedelta(hours=24),
                )
            if delta_state == "before":
                decisions.append(
                    make(
                        rule_id,
                        evidence_state=EvidenceState.CONFLICT,
                        qc_direction=QcDirection.UNKNOWN,
                        reason_code="evidence_conflict",
                        confidence=None,
                    )
                )
            elif delta_state == "within":
                decisions.append(
                    conclusive(rule_id, QcDirection.SATISFIED, "requirement_within_threshold")
                )
                observed, source_document_id = admission_record_events[0]
                add_customer_fact(
                    rule_id,
                    timeliness_fact(
                        rule_id=rule_id,
                        target_document="admission_record",
                        source_label="入院记录",
                        state="within",
                        threshold_hours=24,
                        anchor=anchor,
                        anchor_date=anchor_date,
                        observed=observed,
                        source_document_id=source_document_id,
                        failure_kind="timeliness_requirement_satisfied",
                    ),
                )
            elif len(admission_record_times) < len(admission_rows):
                decisions.append(gap(rule_id, "authoritative_time_missing"))
            elif delta_state == "ambiguous":
                decisions.append(gap(rule_id, "authoritative_time_missing"))
            else:
                decision = conclusive(
                    rule_id, QcDirection.DEFECT, "threshold_exceeded"
                )
                decisions.append(decision)
                add_customer_fact(
                    rule_id,
                    timeliness_fact(
                        rule_id=rule_id,
                        target_document="admission_record",
                        source_label="入院记录",
                        state="late",
                        threshold_hours=24,
                        anchor=anchor,
                        anchor_date=anchor_date,
                        observed=admission_record_events[0][0],
                        source_document_id=admission_record_events[0][1],
                    ),
                )
            continue

        anchor, anchor_date, anchor_gap = admission_anchor(rule_id)
        if anchor_gap is not None or (
            anchor is None and anchor_date is None
        ):
            decisions.append(anchor_gap or gap(rule_id, "authoritative_time_missing"))
            continue
        source_keys = ("daily_course_record", "senior_course_record")
        course_issue = source_issue(source_keys)
        try:
            course_rows = tuple(
                row
                for source_key in source_keys
                if observation_by_source[source_key].query_state.value
                in {"available", "empty"}
                for row in rows(source_key)
            )
        except EvidenceMaterialTruncated:
            course_issue = ("source_truncated", False)
            course_rows = ()
        except ValueError:
            course_issue = ("snapshot_mismatch", True)
            course_rows = ()

        def qualifies(title: str) -> bool:
            if rule_id == "LX0609-005":
                return any(
                    marker in title
                    for marker in (*_ATTENDING_MARKERS, *_SENIOR_MARKERS)
                )
            return any(marker in title for marker in _SENIOR_MARKERS)

        qualifying_events: list[tuple[datetime, str | None]] = []
        qualifying_missing_time = False
        ambiguous_round = False
        for row in course_rows:
            title = str(row.get("document_title") or row.get("title") or "").strip()
            if qualifies(title):
                parsed = _authoritative_time(
                    authoritative_document_time_value(row)
                )
                if parsed is None:
                    qualifying_missing_time = True
                else:
                    document_id = str(row.get("document_id") or "").strip() or None
                    qualifying_events.append((parsed, document_id))
            elif not title or (
                "查房" in title
                and not any(
                    marker in title
                    for marker in (*_ATTENDING_MARKERS, *_SENIOR_MARKERS)
                )
            ):
                ambiguous_round = True

        threshold = timedelta(hours=48 if rule_id == "LX0609-005" else 72)
        qualifying_times = tuple(value for value, _document_id in qualifying_events)
        if anchor is not None:
            elapsed_states = tuple(
                "before"
                if value < anchor
                else "within" if value - anchor <= threshold else "over"
                for value in qualifying_times
            )
        else:
            assert anchor_date is not None
            elapsed_states = tuple(
                _elapsed_state_from_date_range(
                    event_time=value,
                    admission_date=anchor_date,
                    threshold=threshold,
                )
                for value in qualifying_times
            )
        if "within" in elapsed_states:
            decisions.append(
                conclusive(
                    rule_id,
                    QcDirection.SATISFIED,
                    "requirement_within_threshold",
                )
            )
            observed, source_document_id = min(
                (
                    event
                    for event, state in zip(qualifying_events, elapsed_states)
                    if state == "within"
                ),
                key=lambda item: item[0],
            )
            add_customer_fact(
                rule_id,
                timeliness_fact(
                    rule_id=rule_id,
                    target_document=(
                        "attending_course_record"
                        if rule_id == "LX0609-005"
                        else "senior_course_record"
                    ),
                    source_label=(
                        "主治医师及以上首次查房记录"
                        if rule_id == "LX0609-005"
                        else "副主任医师或主任医师首次查房记录"
                    ),
                    state="within",
                    threshold_hours=48 if rule_id == "LX0609-005" else 72,
                    anchor=anchor,
                    anchor_date=anchor_date,
                    observed=observed,
                    source_document_id=source_document_id,
                    failure_kind="timeliness_requirement_satisfied",
                ),
            )
        elif qualifying_missing_time:
            decisions.append(gap(rule_id, "authoritative_time_missing"))
        elif course_issue is not None:
            reason, technical = course_issue
            decisions.append(gap(rule_id, reason, technical=technical))
        elif "before" in elapsed_states:
            decisions.append(
                make(
                    rule_id,
                    evidence_state=EvidenceState.CONFLICT,
                    qc_direction=QcDirection.UNKNOWN,
                    reason_code="evidence_conflict",
                    confidence=None,
                )
            )
        elif "ambiguous" in elapsed_states:
            decisions.append(gap(rule_id, "authoritative_time_missing"))
        elif elapsed_states:
            observed = min(
                value
                for value, state in zip(qualifying_times, elapsed_states)
                if state == "over"
            )
            decision = conclusive(
                rule_id, QcDirection.DEFECT, "threshold_exceeded"
            )
            decisions.append(decision)
            add_customer_fact(
                rule_id,
                timeliness_fact(
                    rule_id=rule_id,
                    target_document=(
                        "attending_course_record"
                        if rule_id == "LX0609-005"
                        else "senior_course_record"
                    ),
                    source_label=(
                        "主治医师及以上首次查房记录"
                        if rule_id == "LX0609-005"
                        else "副主任医师或主任医师首次查房记录"
                    ),
                    state="late",
                    threshold_hours=48 if rule_id == "LX0609-005" else 72,
                    anchor=anchor,
                    anchor_date=anchor_date,
                    observed=observed,
                ),
            )
        elif ambiguous_round:
            decisions.append(gap(rule_id, "required_field_missing"))
        else:
            decision = conclusive(
                rule_id,
                QcDirection.DEFECT,
                "required_document_missing",
            )
            decisions.append(decision)
            add_customer_fact(
                rule_id,
                timeliness_fact(
                    rule_id=rule_id,
                    target_document=(
                        "attending_course_record"
                        if rule_id == "LX0609-005"
                        else "senior_course_record"
                    ),
                    source_label=(
                        "主治医师及以上首次查房记录"
                        if rule_id == "LX0609-005"
                        else "副主任医师或主任医师首次查房记录"
                    ),
                    state="missing",
                    threshold_hours=48 if rule_id == "LX0609-005" else 72,
                    anchor=anchor,
                    anchor_date=anchor_date,
                ),
            )
    return tuple(decisions)


def execute_luxian_0609_native_basic_timeliness(
    *,
    rule_ids: Sequence[str],
    evidence_payload: dict[str, Any] | None,
    institute_id: str = "",
    patient_id: str = "",
    visit_id: str = "",
    source_schema: str | None = None,
    evidence_snapshot: Luxian0609EvidenceSnapshot | None = None,
    evidence_materials: Luxian0609EvidenceMaterialStore | None = None,
    decision_rule_ids: Sequence[str] = (),
) -> NativeExecutionResult:
    """一次执行所选基础时限点；不调用模型、不展开旧映射 ID。"""

    requested = {
        str(rule_id or "").strip().upper()
        for rule_id in rule_ids
        if str(rule_id or "").strip()
    }
    selected = tuple(
        rule_id for rule_id in BASIC_TIMELINESS_RULE_IDS if rule_id in requested
    )
    if not selected:
        return NativeExecutionResult((), ())

    typed_requested = {
        str(rule_id or "").strip().upper() for rule_id in decision_rule_ids
    }
    if (
        any(rule_id not in _TYPED_RULE_IDS for rule_id in typed_requested)
        or not typed_requested.issubset(set(selected))
    ):
        raise ValueError("unsupported typed basic rule scope")
    typed_selected = tuple(
        rule_id for rule_id in selected if rule_id in typed_requested
    )
    if typed_selected and (
        evidence_snapshot is None or evidence_materials is None
    ):
        raise ValueError("typed basic rules require one evidence session")

    try:
        selected_set = set(selected)
        typed_set = set(typed_selected)
        typed_customer_display_facts: list[tuple[str, Mapping[str, Any]]] = []
        decisions = (
            _typed_basic_decisions(
                rule_ids=typed_selected,
                snapshot=evidence_snapshot,
                materials=evidence_materials,
                customer_display_facts=typed_customer_display_facts,
            )
            if typed_selected
            and evidence_snapshot is not None
            and evidence_materials is not None
            else ()
        )
        course_rule_ids = _COURSE_SOURCE_RULE_IDS.intersection(
            selected_set - typed_set
        )
        course_source_data_gap_ids: set[str] = set()
        course_evidence_payload: dict[str, Any] | None = None
        if course_rule_ids:
            try:
                if evidence_materials is not None:
                    course_documents = (
                        build_luxian_0609_course_round_timeline_from_rows(
                            {
                                source_key: evidence_materials.rows(source_key)
                                for source_key in (
                                    "daily_course_record",
                                    "senior_course_record",
                                )
                            }
                        )
                    )
                else:
                    course_documents = read_luxian_0609_course_round_timeline(
                        institute_id=institute_id,
                        patient_id=patient_id,
                        visit_id=visit_id,
                        source_schema=source_schema,
                    )
            except Exception:
                course_source_data_gap_ids = set(course_rule_ids)
            else:
                original_payload = (
                    dict(evidence_payload) if isinstance(evidence_payload, dict) else {}
                )
                original_timeline = original_payload.get("programmatic_timeline")
                private_timeline = (
                    dict(original_timeline) if isinstance(original_timeline, dict) else {}
                )
                private_documents = dict(course_documents)
                private_documents["first_course_record"] = []
                private_timeline["documents"] = private_documents
                original_payload["programmatic_timeline"] = private_timeline
                course_evidence_payload = original_payload
        first_course_data_gap = (
            _FIRST_COURSE_RULE_ID in selected
            and not _has_substantive_first_course_body(evidence_payload)
        )
        admission_anchor_data_gap_ids = _ADMISSION_ANCHOR_RULE_IDS.intersection(
            selected_set - typed_set
        ) if not _approved_admission_anchor_available(evidence_payload) else set()
        evaluated_rule_ids = selected_set - typed_set - (
            {_FIRST_COURSE_RULE_ID} if first_course_data_gap else set()
        ) - admission_anchor_data_gap_ids - course_source_data_gap_ids
        wrappers = [
            rule
            for rule in load_luxian_0609_rules()
            if str(rule.get("rule_id") or "").strip().upper() in evaluated_rule_ids
        ]
        non_course_wrappers = [
            rule
            for rule in wrappers
            if str(rule.get("rule_id") or "").strip().upper()
            not in _COURSE_SOURCE_RULE_IDS
        ]
        course_wrappers = [
            rule
            for rule in wrappers
            if str(rule.get("rule_id") or "").strip().upper()
            in _COURSE_SOURCE_RULE_IDS
        ]
        evaluated = evaluate_luxian_0609_programmatic_rules(
            wrapper_rules=non_course_wrappers,
            evidence_payload=evidence_payload,
        )
        if course_wrappers and course_evidence_payload is not None:
            evaluated.extend(
                evaluate_luxian_0609_programmatic_rules(
                    wrapper_rules=course_wrappers,
                    evidence_payload=course_evidence_payload,
                )
            )
        by_rule_id = {
            str(item.get("rule_id") or "").strip().upper(): item
            for item in evaluated
            if isinstance(item, dict)
        }
    except Exception:
        return NativeExecutionResult(
            results=tuple(
                _technical_result(rule_id, "native_basic_execution_failure")
                for rule_id in selected
            ),
            planned_rule_ids=selected,
            terminal_reason_code="native_basic_execution_failure",
        )

    results: list[dict[str, Any]] = []
    for rule_id in selected:
        if rule_id in typed_set:
            continue
        if rule_id in admission_anchor_data_gap_ids:
            results.append(_admission_anchor_data_gap_result(rule_id))
            continue
        if rule_id in course_source_data_gap_ids:
            results.append(_course_source_data_gap_result(rule_id))
            continue
        if rule_id == _FIRST_COURSE_RULE_ID and first_course_data_gap:
            results.append(_first_course_data_gap_result())
            continue
        raw = by_rule_id.get(rule_id)
        if raw is None:
            results.append(_technical_result(rule_id, "native_basic_result_incomplete"))
            continue
        item = dict(raw)
        metadata = dict(item.get("metadata") or {})
        metadata.update(
            {
                "execution_source": "lx0609_native",
                "executor_type": "program",
                "prompt_tokens": 0,
                "completion_tokens": 0,
                "total_tokens": 0,
            }
        )
        item["metadata"] = metadata
        results.append(item)

    return NativeExecutionResult(
        results=tuple(results),
        planned_rule_ids=selected,
        decisions=decisions,
        customer_display_facts=tuple(typed_customer_display_facts),
    )
