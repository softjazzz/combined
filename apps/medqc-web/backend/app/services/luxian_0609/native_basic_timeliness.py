"""LX0609 基础时限族的原生确定性执行器。"""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import date, datetime, timedelta
from inspect import isawaitable
import re
from typing import Any, Awaitable, Mapping, Protocol, Sequence

from .basic_timeliness_facts import (
    AdmissionAnchorState,
    CourseRoundRole,
    associate_timeliness_event,
    classify_course_round_role,
    extract_admission_anchor,
    extract_document_events,
    extract_rescue_events,
    is_generic_upper_physician_round,
    parse_authoritative_datetime,
)
from .basic_timeliness_customer_projection import (
    safe_basic_timeliness_customer_display_facts,
)
from .decision_model import (
    ApplicabilityState,
    EvidenceState,
    QcDirection,
    RuleDecision,
)
from .evidence_material import (
    EvidenceMaterialTruncated,
    EvidenceMaterialUnavailable,
    Luxian0609EvidenceMaterialStore,
)
from .evidence_snapshot import Luxian0609EvidenceSnapshot
from .native_execution import NativeExecutionResult, build_luxian_0609_native_result
from .rescue_record_completeness import (
    RESCUE_COMPLETENESS_RULE_ID,
    execute_rescue_record_completeness,
)
from .source_evidence_reader import (
    CURRENT_VISIT_RESCUE_ORDER_SOURCE_KEY,
    EVALUATION_HORIZON_SOURCE_KEY,
    build_luxian_0609_course_round_timeline_from_rows,
    read_luxian_0609_course_round_timeline,
)
from ..luxian_0609_rule_catalog import load_luxian_0609_rules
from ..luxian_0609_programmatic_rules import evaluate_luxian_0609_programmatic_rules


BASIC_TIMELINESS_RULE_IDS = (
    "LX0609-01-01-01",
    "LX0609-01-02-01",
    "LX0609-09-01-01",
    "LX0609-02-01-01",
    "LX0609-02-01-02",
)
# 保持原五规则公开调用范围稳定；新增抢救内容规则仅在目录明确选中时执行。
EXECUTABLE_BASIC_TIMELINESS_RULE_IDS = (
    *BASIC_TIMELINESS_RULE_IDS,
    RESCUE_COMPLETENESS_RULE_ID,
)
EXECUTOR_KEY = "basic_timeliness"
_FIRST_COURSE_RULE_ID = "LX0609-01-02-01"
_ADMISSION_ANCHOR_RULE_IDS = frozenset(
    {"LX0609-01-01-01", "LX0609-02-01-01", "LX0609-02-01-02"}
)
_COURSE_SOURCE_RULE_IDS = frozenset({"LX0609-02-01-01", "LX0609-02-01-02"})
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
_ADMISSION_RECORD_BODY_FIELDS = (
    "chief_complaint",
    "history_of_present_illness",
    "record_content",
)
_MIN_ADMISSION_RECORD_BODY_CHARS = 2
_ADMISSION_RECORD_FIELD_LABEL_PATTERN = re.compile(
    r"(?:入院记录|记录时间|完成时间|提交时间|文书类型|文书编号|主诉|现病史|正文|"
    r"chiefcomplaint|historyofpresentillness|recordcontent)",
    flags=re.IGNORECASE,
)
_ADMISSION_RECORD_PLACEHOLDERS = frozenset(
    {
        "",
        "无",
        "否",
        "无否",
        "暂无",
        "无特殊",
        "未填",
        "未填写",
        "不详",
        "未知",
        "null",
        "none",
    }
)
_TYPED_RULE_IDS = (
    "LX0609-01-01-01",
    "LX0609-01-02-01",
    "LX0609-09-01-01",
    "LX0609-02-01-01",
    "LX0609-02-01-02",
)
_TYPED_SOURCE_KEYS_BY_RULE = {
    "LX0609-01-01-01": (
        "admission_record",
        "discharge_record",
        EVALUATION_HORIZON_SOURCE_KEY,
        "inpat_registration",
    ),
    "LX0609-01-02-01": (
        "admission_record",
        EVALUATION_HORIZON_SOURCE_KEY,
        "first_course_record",
        "inpat_registration",
    ),
    "LX0609-09-01-01": (CURRENT_VISIT_RESCUE_ORDER_SOURCE_KEY, "rescue_record"),
    "LX0609-02-01-01": (
        "admission_record",
        "daily_course_record",
        "discharge_record",
        EVALUATION_HORIZON_SOURCE_KEY,
        "inpat_registration",
        "senior_course_record",
    ),
    "LX0609-02-01-02": (
        "admission_record",
        "daily_course_record",
        "discharge_record",
        EVALUATION_HORIZON_SOURCE_KEY,
        "inpat_registration",
        "senior_course_record",
    ),
}


class BasicTimelinessLLMClient(Protocol):
    async def generate(self, prompt: str, **kwargs: Any) -> dict[str, Any]: ...


@dataclass(frozen=True)
class NativeBasicTimelinessExecutionResult(NativeExecutionResult):
    llm_call_count: int = 0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    api_time: float = 0.0
    usage_observation_complete: bool = True


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


def _is_substantive_admission_record(row: Mapping[str, Any]) -> bool:
    """逐字段确认入院记录含有临床内容，拒绝标题、时间和受控占位值。"""

    for field in _ADMISSION_RECORD_BODY_FIELDS:
        value = row.get(field)
        if not isinstance(value, str):
            continue
        normalized = re.sub(r"[\W_]+", "", value, flags=re.UNICODE)
        meaningful = _ADMISSION_RECORD_FIELD_LABEL_PATTERN.sub("", normalized)
        # 日期、时刻和纯数字不能单独证明存在有效临床内容；但“腹痛3天”
        # 去除数字后仍保留足够的临床文字，不会被误伤。
        meaningful = re.sub(r"(?:\d+|年|月|日|时|分|秒)", "", meaningful)
        if (
            meaningful not in _ADMISSION_RECORD_PLACEHOLDERS
            and len(meaningful) >= _MIN_ADMISSION_RECORD_BODY_CHARS
        ):
            return True
    return False


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
        "LX0609-01-01-01": (
            "admission_record",
            "discharge_record",
            EVALUATION_HORIZON_SOURCE_KEY,
            "inpat_registration",
        ),
        "LX0609-01-02-01": (
            "admission_record",
            EVALUATION_HORIZON_SOURCE_KEY,
            "first_course_record",
            "inpat_registration",
        ),
        "LX0609-09-01-01": (CURRENT_VISIT_RESCUE_ORDER_SOURCE_KEY, "rescue_record"),
        "LX0609-02-01-01": (
            "admission_record",
            "daily_course_record",
            "discharge_record",
            EVALUATION_HORIZON_SOURCE_KEY,
            "inpat_registration",
            "senior_course_record",
        ),
        "LX0609-02-01-02": (
            "admission_record",
            "daily_course_record",
            "discharge_record",
            EVALUATION_HORIZON_SOURCE_KEY,
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
        applicability: ApplicabilityState | None = None,
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
            applicability=applicability,
        )

    def conflict(rule_id: str) -> RuleDecision:
        return make(
            rule_id,
            evidence_state=EvidenceState.CONFLICT,
            qc_direction=QcDirection.UNKNOWN,
            reason_code="evidence_conflict",
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

    document_rows_by_source: dict[str, tuple[tuple[str, Mapping[str, object]], ...]] = {}

    def attach_selected_row(
        decision: RuleDecision,
        *,
        source_key: str,
        row: Mapping[str, Any],
    ) -> RuleDecision:
        """将实际参与结论的同一行材料引用附加到既有来源快照引用之后。"""

        try:
            document_rows = document_rows_by_source.get(source_key)
            if document_rows is None:
                document_rows = materials.document_rows(source_key, snapshot=snapshot)
                document_rows_by_source[source_key] = document_rows
        except (
            EvidenceMaterialTruncated,
            EvidenceMaterialUnavailable,
            KeyError,
            TypeError,
            ValueError,
        ):
            return gap(decision.rule_id, "snapshot_mismatch", technical=True)
        document_ref = next(
            (reference for reference, original_row in document_rows if original_row is row),
            None,
        )
        if document_ref is None:
            return gap(decision.rule_id, "snapshot_mismatch", technical=True)
        return replace(decision, fact_refs=(*decision.fact_refs, document_ref))

    def attach_selected_rows(
        decision: RuleDecision,
        *,
        source_key: str,
        selected_rows: Sequence[Mapping[str, Any]],
    ) -> RuleDecision:
        """为同一结论实际检查到的每一行文书绑定材料引用。"""

        bound = decision
        seen_rows: set[int] = set()
        for selected_row in selected_rows:
            if id(selected_row) in seen_rows:
                continue
            seen_rows.add(id(selected_row))
            bound = attach_selected_row(
                bound,
                source_key=source_key,
                row=selected_row,
            )
            if (
                bound.evidence_state is EvidenceState.TECHNICAL_ERROR
                and bound.reason_code == "snapshot_mismatch"
            ):
                return bound
        return bound

    admission_needed = any(
        rule_id in {"LX0609-01-01-01", "LX0609-01-02-01", "LX0609-02-01-01", "LX0609-02-01-02"}
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

    horizon_datetime_for_filter: datetime | None = None
    horizon_date_for_filter: date | None = None
    horizon_filter_issue = "authoritative_time_missing"
    # 抢救等独立规则不需要终点，证据会话可以合法地没有该观测。
    horizon_observation = observation_by_source.get(EVALUATION_HORIZON_SOURCE_KEY)
    horizon_reason = horizon_observation.reason_code if horizon_observation is not None else ""
    if horizon_reason == "authoritative_time_conflict":
        horizon_filter_issue = horizon_reason
    try:
        frozen_rows = tuple(materials.rows(EVALUATION_HORIZON_SOURCE_KEY))
        if len(frozen_rows) == 1:
            frozen_row = frozen_rows[0]
            if frozen_row.get("basis") == "discharge_date":
                # 出院是临床观察终点，不是文书可见性截止：出院后补写但在任务冻结前
                # 完成的记录仍须按原24/8/48/72小时合同判定。
                horizon_date_for_filter = date.fromisoformat(str(frozen_row["task_frozen_date"]))
            else:
                horizon_datetime_for_filter = parse_authoritative_datetime(frozen_row.get("horizon_datetime"))
                if frozen_row.get("horizon_date"):
                    horizon_date_for_filter = date.fromisoformat(str(frozen_row["horizon_date"]))
            if horizon_datetime_for_filter is not None or horizon_date_for_filter is not None:
                horizon_filter_issue = ""
            if frozen_row.get("basis") != "discharge_date" and frozen_row.get("horizon_datetime") and horizon_datetime_for_filter is None:
                horizon_filter_issue = "authoritative_time_missing"
            if (horizon_datetime_for_filter is not None and horizon_date_for_filter is not None
                and horizon_datetime_for_filter.date() != horizon_date_for_filter):
                horizon_filter_issue = "authoritative_time_conflict"
    except EvidenceMaterialTruncated:
        horizon_filter_issue = "source_truncated"
    except EvidenceMaterialUnavailable:
        horizon_filter_issue = "source_unavailable"
    except (ValueError, TypeError, KeyError):
        horizon_filter_issue = "authoritative_time_missing"

    def within_frozen_horizon(value: datetime | None) -> bool:
        if value is None:
            return True  # 未知时刻仍参与资料缺口判断，不能当成未来记录丢弃。
        if horizon_datetime_for_filter is not None:
            return value <= horizon_datetime_for_filter
        return horizon_date_for_filter is None or value.date() <= horizon_date_for_filter

    # 001 的合规解释必须能回到实际被选中的入院记录。时间计算仍只使用
    # 权威 record time；这里额外保留同一行的内部文书 ID，供安全聚合层生成
    # 不可逆引用。没有可靠 ID 时只展示时间事实，不猜测文书。
    substantive_admission_rows = tuple(
        event.row for event in extract_document_events(admission_rows)
        if _is_substantive_admission_record(event.row) and within_frozen_horizon(event.observed_time)
    )
    admission_record_events = tuple(
        sorted(
            (
                (event.observed_time, event.document_id, event.row)
                for event in extract_document_events(substantive_admission_rows)
                if event.observed_time is not None
            ),
            key=lambda item: (item[0], item[1] or ""),
        )
    )
    admission_record_times = tuple(event[0] for event in admission_record_events)
    def admission_anchor(
        rule_id: str,
    ) -> tuple[datetime | None, date | None, RuleDecision | None]:
        if admission_issue is not None:
            reason, technical = admission_issue
            return None, None, gap(rule_id, reason, technical=technical)
        if registration_issue is not None:
            reason, technical = registration_issue
            return None, None, gap(rule_id, reason, technical=technical)
        if discharge_issue is not None:
            reason, technical = discharge_issue
            return None, None, gap(rule_id, reason, technical=technical)
        anchor_fact = extract_admission_anchor(
            registration_rows=registration_rows,
            admission_rows=admission_rows,
            discharge_rows=discharge_rows,
            allow_date_fallback=rule_id in _ADMISSION_ANCHOR_RULE_IDS,
        )
        if anchor_fact.state is AdmissionAnchorState.CONFLICT:
            return None, None, conflict(rule_id)
        if anchor_fact.state is AdmissionAnchorState.EXACT:
            return anchor_fact.anchor_time, None, None
        if anchor_fact.state is AdmissionAnchorState.DATE_ONLY:
            return None, anchor_fact.anchor_date, None
        return None, None, gap(rule_id, "authoritative_time_missing")

    def conclusive(
        rule_id: str,
        direction: QcDirection,
        reason_code: str,
        *,
        sources: tuple[str, ...] | None = None,
    ) -> RuleDecision:
        return make(
            rule_id,
            evidence_state=EvidenceState.SUFFICIENT,
            qc_direction=direction,
            reason_code=reason_code,
            confidence=1.0,
            sources=sources,
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

    def missing_target_decision(
        rule_id: str,
        *,
        anchor: datetime | None,
        threshold: timedelta,
    ) -> RuleDecision | None:
        """仅在评价时点已越过时限时，将完整来源中的目标缺失判为缺陷。"""

        if anchor is None:
            return gap(rule_id, "authoritative_time_missing")
        horizon_observation = observation_by_source[EVALUATION_HORIZON_SOURCE_KEY]
        if horizon_observation.query_state.value == "empty":
            return gap(rule_id, "authoritative_time_missing")
        if horizon_observation.query_state.value != "available":
            return gap(rule_id, "snapshot_mismatch", technical=True)
        try:
            horizon_rows = tuple(materials.rows(EVALUATION_HORIZON_SOURCE_KEY))
        except EvidenceMaterialTruncated:
            return gap(rule_id, "snapshot_mismatch", technical=True)
        except Exception:
            return gap(rule_id, "snapshot_mismatch", technical=True)
        if len(horizon_rows) != 1:
            return gap(rule_id, "snapshot_mismatch", technical=True)
        horizon_row = horizon_rows[0]
        try:
            horizon_date = date.fromisoformat(str(horizon_row["horizon_date"]))
        except (KeyError, TypeError, ValueError):
            return gap(rule_id, "snapshot_mismatch", technical=True)
        raw_horizon_datetime = horizon_row.get("horizon_datetime")
        try:
            horizon_datetime = (
                datetime.fromisoformat(str(raw_horizon_datetime))
                if raw_horizon_datetime is not None
                else None
            )
        except ValueError:
            return gap(rule_id, "snapshot_mismatch", technical=True)
        if horizon_datetime is not None:
            if horizon_datetime.tzinfo is not None:
                return gap(rule_id, "snapshot_mismatch", technical=True)
            if horizon_datetime.date() != horizon_date:
                return conflict(rule_id)
            maturity_state = (
                "conflict"
                if horizon_datetime < anchor
                else "mature"
                if horizon_datetime - anchor >= threshold
                else "not_reached"
            )
        else:
            maturity_state = (
                "conflict"
                if horizon_date < anchor.date()
                else "mature"
                if horizon_date > (anchor + threshold).date()
                else "not_reached"
            )
        if maturity_state == "mature":
            return None
        if (
            maturity_state == "not_reached"
            and horizon_datetime is None
            and horizon_row.get("basis") == "discharge_date"
            and horizon_date == (anchor + threshold).date()
        ):
            # 日期级出院恰在截止日：无法证明出院早于或晚于截止时刻，不能当作“未到期”。
            return gap(rule_id, "authoritative_time_missing")
        if maturity_state == "not_reached":
            return (
                not_applicable(rule_id, "evaluation_window_not_mature")
                if rule_id == "LX0609-02-01-02"
                else gap(rule_id, "evaluation_window_not_mature")
            )
        if maturity_state == "conflict":
            return conflict(rule_id)
        return gap(rule_id, "snapshot_mismatch", technical=True)

    def add_customer_fact(rule_id: str, facts: Mapping[str, Any]) -> None:
        """执行器在选择点输出已脱敏、已校验的客户事实。"""

        if (
            customer_display_facts is not None
            and not (
                decisions
                and decisions[-1].evidence_state is EvidenceState.TECHNICAL_ERROR
                and decisions[-1].reason_code == "snapshot_mismatch"
            )
        ):
            safe_facts = safe_basic_timeliness_customer_display_facts(
                rule_id=rule_id,
                raw=facts,
                formal_publication=True,
            )
            if safe_facts is not None:
                customer_display_facts.append((rule_id, safe_facts))

    def format_time(value: datetime | None, *, precise: bool = False) -> str:
        if value is None:
            return ""
        return value.isoformat(sep=" ") if precise else value.strftime("%Y-%m-%d %H:%M:%S")

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
            facts["anchor_time"] = format_time(anchor, precise=rule_id == "LX0609-09-01-01")
        elif anchor_date is not None:
            facts["anchor_date"] = anchor_date.isoformat()
        if observed is not None:
            facts["observed_time"] = format_time(observed, precise=rule_id == "LX0609-09-01-01")
        if anchor is not None and observed is not None:
            elapsed_hours = (observed - anchor).total_seconds() / 3600
            facts["elapsed_hours"] = round(elapsed_hours, 2)
            if state == "late" and elapsed_hours > threshold_hours:
                facts["overdue_hours"] = round(
                    elapsed_hours - threshold_hours,
                    2,
                )
            elif state == "within" and elapsed_hours >= 0:
                facts["remaining_hours"] = round(
                    max(0.0, threshold_hours - elapsed_hours),
                    2,
                )
        if source_document_id:
            # 仅供聚合层生成不可逆文书引用；安全投影不得回传该内部 ID。
            facts["source_document_id"] = source_document_id
        return facts

    decisions: list[RuleDecision] = []
    for rule_id in rule_ids:
        if rule_id in {"LX0609-01-01-01", "LX0609-01-02-01", "LX0609-02-01-01", "LX0609-02-01-02"} and horizon_filter_issue:
            # 已有目标文书也必须证明属于冻结范围，不能只在目标缺失时检查终点。
            decisions.append(gap(rule_id, horizon_filter_issue))
            continue
        if rule_id == "LX0609-01-02-01":
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
            first_course_rows = tuple(
                event.row for event in extract_document_events(first_course_rows)
                if within_frozen_horizon(event.observed_time)
            )
            if not first_course_rows:
                missing_decision = missing_target_decision(
                    rule_id,
                    anchor=anchor,
                    threshold=timedelta(hours=8),
                )
                decisions.append(
                    missing_decision
                    or conclusive(
                        rule_id,
                        QcDirection.DEFECT,
                        "required_document_missing",
                    )
                )
                if missing_decision is None:
                    add_customer_fact(
                        rule_id,
                        timeliness_fact(
                            rule_id=rule_id,
                            target_document="first_course_record",
                            source_label="首次病程记录",
                            state="missing",
                            threshold_hours=8,
                            anchor=anchor,
                        ),
                    )
                continue
            complete_events: list[tuple[datetime, str | None, Mapping[str, Any]]] = []
            incomplete = False
            for event in extract_document_events(first_course_rows):
                row = event.row
                record_time = event.observed_time
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
                            event.document_id,
                            row,
                        )
                    )
            complete_times = [value for value, *_ in complete_events]
            deltas = sorted(value - anchor for value in complete_times)
            if any(timedelta(0) <= delta <= timedelta(hours=8) for delta in deltas):
                observed, source_document_id, selected_row = min(
                    (
                        item
                        for item in complete_events
                        if timedelta(0) <= item[0] - anchor <= timedelta(hours=8)
                    ),
                    key=lambda item: item[0],
                )
                decision = attach_selected_row(
                    conclusive(
                        rule_id,
                        QcDirection.SATISFIED,
                        "requirement_within_threshold",
                    ),
                    source_key="first_course_record",
                    row=selected_row,
                )
                decisions.append(decision)
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
                observed, source_document_id, selected_row = min(
                    complete_events,
                    key=lambda item: item[0],
                )
                decision = attach_selected_row(
                    conclusive(rule_id, QcDirection.DEFECT, "threshold_exceeded"),
                    source_key="first_course_record",
                    row=selected_row,
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
                        observed=observed,
                        source_document_id=source_document_id,
                    ),
                )
            else:
                decisions.append(gap(rule_id, "required_field_missing"))
            continue

        if rule_id == "LX0609-09-01-01":
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
                order_issue = source_issue((CURRENT_VISIT_RESCUE_ORDER_SOURCE_KEY,))
                try:
                    order_rows = (
                        rows(CURRENT_VISIT_RESCUE_ORDER_SOURCE_KEY)
                        if observation_by_source[
                            CURRENT_VISIT_RESCUE_ORDER_SOURCE_KEY
                        ].query_state.value
                        in {"available", "empty"}
                        else ()
                    )
                except EvidenceMaterialTruncated:
                    order_issue = ("source_truncated", False)
                    order_rows = ()
                except ValueError:
                    order_issue = ("snapshot_mismatch", True)
                    order_rows = ()
                if order_issue is not None:
                    reason, technical = order_issue
                    decisions.append(gap(rule_id, reason, technical=technical))
                    continue
                rescue_orders = tuple(
                    row for row in order_rows if row.get("status_state") == "effective"
                )
                if order_rows and not rescue_orders:
                    decisions.append(gap(rule_id, "required_field_missing"))
                    continue
                if not rescue_orders:
                    decisions.append(not_applicable(rule_id, "trigger_absent_complete"))
                    continue
                decisions.append(
                    attach_selected_rows(
                        gap(rule_id, "rescue_record_missing_after_trigger"),
                        source_key=CURRENT_VISIT_RESCUE_ORDER_SOURCE_KEY,
                        selected_rows=rescue_orders,
                    )
                )
                add_customer_fact(
                    rule_id,
                    {
                        "failure_kind": "rescue_record_missing_after_trigger",
                        "target_document": "rescue_record",
                        "source_label": "抢救记录",
                        "trigger_source": CURRENT_VISIT_RESCUE_ORDER_SOURCE_KEY,
                    },
                )
                continue
            rescue_timeline: list[
                tuple[timedelta, datetime, datetime, str, Mapping[str, Any]]
            ] = []
            incomplete: list[
                tuple[str, datetime | None, datetime | None, str, Mapping[str, Any]]
            ] = []
            rescue_event_facts: list[dict[str, Any]] = []
            rescue_events = extract_rescue_events(rescue_rows)
            for event_index, event in enumerate(rescue_events, start=1):
                record_time = event.document.observed_time
                rescue_end = event.rescue_end_time
                event_fact: dict[str, Any] = {"event_index": event_index}
                if event.document.document_id:
                    event_fact["source_document_id"] = event.document.document_id
                if rescue_end is not None:
                    event_fact["rescue_end_time"] = format_time(rescue_end, precise=True)
                if record_time is not None:
                    event_fact["document_completion_time"] = format_time(record_time, precise=True)
                if rescue_end is None:
                    event_fact["event_state"] = "rescue_end_time_missing"
                    rescue_event_facts.append(event_fact)
                    incomplete.append(
                        (
                            "rescue_end_time_missing",
                            None,
                            record_time,
                            event.document.document_id or "",
                            event.document.row,
                        )
                    )
                    continue
                if record_time is None:
                    event_fact["event_state"] = "document_completion_time_missing"
                    rescue_event_facts.append(event_fact)
                    incomplete.append(
                        (
                            "document_completion_time_missing",
                            rescue_end,
                            None,
                            event.document.document_id or "",
                            event.document.row,
                        )
                    )
                    continue
                association = associate_timeliness_event(
                    anchor_time=rescue_end,
                    observed_event=event.document,
                    threshold_hours=6,
                )
                if association is None or association.state == "before":
                    event_fact["event_state"] = "authoritative_time_conflict"
                    rescue_event_facts.append(event_fact)
                    incomplete.append(
                        (
                            "authoritative_time_conflict",
                            rescue_end,
                            record_time,
                            event.document.document_id or "",
                            event.document.row,
                        )
                    )
                else:
                    elapsed_hours = (record_time - rescue_end).total_seconds() / 3600
                    event_fact["event_state"] = (
                        "late" if elapsed_hours > 6 else "within"
                    )
                    event_fact["elapsed_hours"] = round(elapsed_hours, 2)
                    rescue_event_facts.append(event_fact)
                    rescue_timeline.append(
                        (
                            record_time - rescue_end,
                            rescue_end,
                            record_time,
                            event.document.document_id or "",
                            event.document.row,
                        )
                    )
            overdue = max(
                (
                    item
                    for item in rescue_timeline
                    if item[0] > timedelta(hours=6)
                ),
                key=lambda item: item[0],
                default=None,
            )
            if overdue is not None:
                _delta, rescue_end, record_time, document_id, selected_row = overdue
                decisions.append(
                    attach_selected_rows(
                        conclusive(rule_id, QcDirection.DEFECT, "threshold_exceeded"),
                        source_key="rescue_record",
                        selected_rows=(
                            selected_row,
                            *(event.document.row for event in rescue_events),
                        ),
                    )
                )
                projected = timeliness_fact(
                    rule_id=rule_id,
                    target_document="rescue_record",
                    source_label="抢救记录",
                    state="late",
                    threshold_hours=6,
                    anchor=rescue_end,
                    observed=record_time,
                    source_document_id=document_id or None,
                )
                if len(rescue_event_facts) > 1:
                    projected["rescue_events"] = rescue_event_facts
                add_customer_fact(rule_id, projected)
            elif incomplete:
                reason, rescue_end, record_time, document_id, selected_row = sorted(
                    incomplete,
                    key=lambda item: (
                        {
                            "authoritative_time_conflict": 0,
                            "rescue_end_time_missing": 1,
                            "document_completion_time_missing": 2,
                        }[item[0]],
                        item[3],
                    ),
                )[0]
                decisions.append(
                    attach_selected_rows(
                        gap(rule_id, reason),
                        source_key="rescue_record",
                        selected_rows=(
                            selected_row,
                            *(event.document.row for event in rescue_events),
                        ),
                    )
                )
                projected = timeliness_fact(
                    rule_id=rule_id,
                    target_document="rescue_record",
                    source_label="抢救记录",
                    state=(
                        "conflict"
                        if reason == "authoritative_time_conflict"
                        else "missing_time"
                    ),
                    threshold_hours=6,
                    anchor=rescue_end,
                    observed=record_time,
                    source_document_id=document_id or None,
                    failure_kind=reason,
                )
                if len(rescue_event_facts) > 1:
                    projected["rescue_events"] = rescue_event_facts
                add_customer_fact(rule_id, projected)
            elif rescue_timeline:
                _delta, rescue_end, record_time, document_id, selected_row = max(
                    rescue_timeline,
                    key=lambda item: item[0],
                )
                decisions.append(
                    attach_selected_rows(
                        conclusive(
                            rule_id,
                            QcDirection.SATISFIED,
                            "requirement_within_threshold",
                        ),
                        source_key="rescue_record",
                        selected_rows=(
                            selected_row,
                            *(event.document.row for event in rescue_events),
                        ),
                    )
                )
                projected = timeliness_fact(
                    rule_id=rule_id,
                    target_document="rescue_record",
                    source_label="抢救记录",
                    state="within",
                    threshold_hours=6,
                    anchor=rescue_end,
                    observed=record_time,
                    source_document_id=document_id or None,
                    failure_kind="timeliness_requirement_satisfied",
                )
                if len(rescue_event_facts) > 1:
                    projected["rescue_events"] = rescue_event_facts
                add_customer_fact(rule_id, projected)
            else:
                decisions.append(gap(rule_id, "required_field_missing"))
            continue

        if rule_id == "LX0609-01-01-01":
            if admission_issue is not None:
                reason, technical = admission_issue
                decisions.append(gap(rule_id, reason, technical=technical))
                continue
            if not substantive_admission_rows:
                anchor, _anchor_date, anchor_gap = admission_anchor(rule_id)
                if anchor_gap is not None:
                    decisions.append(anchor_gap)
                    continue
                missing_decision = missing_target_decision(
                    rule_id,
                    anchor=anchor,
                    threshold=timedelta(hours=24),
                )
                if missing_decision is not None:
                    decisions.append(missing_decision)
                    continue
                if admission_rows:
                    # 行已存在但实质正文未供给，不能据此断言临床没有入院记录。
                    decisions.append(gap(rule_id, "required_field_missing"))
                    continue
                decision = conclusive(
                    rule_id,
                    QcDirection.DEFECT,
                    "required_document_missing",
                )
                decisions.append(decision)
                document_content_state = (
                    "blank_or_placeholder" if admission_rows else None
                )
                add_customer_fact(
                    rule_id,
                    {
                        **timeliness_fact(
                            rule_id=rule_id,
                            target_document="admission_record",
                            source_label="入院记录",
                            state="missing",
                            threshold_hours=24,
                            anchor=None,
                        ),
                        **(
                            {"document_content_state": document_content_state}
                            if document_content_state is not None
                            else {}
                        ),
                    },
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
                observed, source_document_id, selected_row = admission_record_events[0]
                decisions.append(
                    attach_selected_row(
                        make(
                            rule_id,
                            evidence_state=EvidenceState.CONFLICT,
                            qc_direction=QcDirection.UNKNOWN,
                            reason_code="evidence_conflict",
                            confidence=None,
                        ),
                        source_key="admission_record",
                        row=selected_row,
                    )
                )
                assert anchor is not None
                add_customer_fact(
                    rule_id,
                    {
                        "failure_kind": "evidence_time_conflict",
                        "target_document": "admission_record",
                        "source_label": "入院记录",
                        "timeliness_state": "before",
                        "threshold_hours": 24,
                        "anchor_time": format_time(anchor),
                        "observed_time": format_time(observed),
                        "time_conflict_seconds": round(
                            (anchor - observed).total_seconds()
                        ),
                        **(
                            {"source_document_id": source_document_id}
                            if source_document_id
                            else {}
                        ),
                    },
                )
            elif delta_state == "within":
                observed, source_document_id, selected_row = admission_record_events[0]
                # 登记零行且锚点精确时，实际采用的是入院记录中的入院时间。
                # 按时结论已有文书证据，空登记不作为来源完整性的前提。
                registration = observation_by_source["inpat_registration"]
                sources = (
                    tuple(key for key in allowed_sources[rule_id] if key != "inpat_registration")
                    if anchor is not None and registration.query_state.value == "empty"
                    else None
                )
                decisions.append(
                    attach_selected_row(
                        conclusive(
                            rule_id,
                            QcDirection.SATISFIED,
                            "requirement_within_threshold",
                            sources=sources,
                        ),
                        source_key="admission_record",
                        row=selected_row,
                    )
                )
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
            elif len(admission_record_times) < len(substantive_admission_rows):
                decisions.append(gap(rule_id, "authoritative_time_missing"))
            elif delta_state == "ambiguous":
                decisions.append(gap(rule_id, "authoritative_time_missing"))
            else:
                observed, source_document_id, selected_row = admission_record_events[0]
                decision = attach_selected_row(
                    conclusive(
                        rule_id, QcDirection.DEFECT, "threshold_exceeded"
                    ),
                    source_key="admission_record",
                    row=selected_row,
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
                        observed=observed,
                        source_document_id=source_document_id,
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
        if course_issue is None and not materials.permits_absence("daily_course_record"):
            course_issue = ("source_unavailable", False)
        try:
            course_events = tuple(
                (source_key, event)
                for source_key in source_keys
                if observation_by_source[source_key].query_state.value
                in {"available", "empty"}
                for event in extract_document_events(rows(source_key))
            )
        except EvidenceMaterialTruncated:
            course_issue = ("source_truncated", False)
            course_events = ()
        except ValueError:
            course_issue = ("snapshot_mismatch", True)
            course_events = ()

        def qualifies(role: CourseRoundRole) -> bool:
            if rule_id == "LX0609-02-01-01":
                return role in {
                    CourseRoundRole.ATTENDING_OR_ABOVE,
                    CourseRoundRole.SENIOR,
                }
            return role is CourseRoundRole.SENIOR

        qualifying_events: list[tuple[datetime, str | None, str, Mapping[str, Any]]] = []
        qualifying_missing_time = False
        ambiguous_round = False
        ambiguous_before_deadline = False
        threshold = timedelta(hours=48 if rule_id == "LX0609-02-01-01" else 72)
        for source_key, event in course_events:
            event_time = event.observed_time
            if not within_frozen_horizon(event_time):
                continue
            role = classify_course_round_role(event.row, source_key=source_key)
            # 客户确认：标准上级医师查房文书已能证明本次查房身份，
            # 006 不再要求正文额外提供姓名和具体职称。
            customer_upper_round = (
                rule_id == "LX0609-02-01-02"
                and is_generic_upper_physician_round(event.row, source_key=source_key)
            )
            if qualifies(role) or customer_upper_round:
                parsed = event_time
                if parsed is None:
                    qualifying_missing_time = True
                else:
                    qualifying_events.append(
                        (parsed, event.document_id, source_key, event.row)
                    )
            elif role is CourseRoundRole.AMBIGUOUS:
                ambiguous_round = True
                ambiguous_before_deadline |= (
                    event_time is None
                    or (anchor is not None and anchor <= event_time <= anchor + threshold)
                    or (anchor is None and anchor_date is not None and
                        _elapsed_state_from_date_range(event_time=event_time, admission_date=anchor_date,
                                                       threshold=threshold) in {"within", "ambiguous"})
                )

        threshold = timedelta(hours=48 if rule_id == "LX0609-02-01-01" else 72)
        qualifying_times = tuple(value for value, *_ in qualifying_events)
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
            observed, source_document_id, selected_source_key, selected_row = min(
                (
                    event
                    for event, state in zip(qualifying_events, elapsed_states)
                    if state == "within"
                ),
                key=lambda item: item[0],
            )
            decisions.append(
                attach_selected_row(
                    conclusive(
                        rule_id,
                        QcDirection.SATISFIED,
                        "requirement_within_threshold",
                    ),
                    source_key=selected_source_key,
                    row=selected_row,
                ),
            )
            add_customer_fact(
                rule_id,
                timeliness_fact(
                    rule_id=rule_id,
                    target_document=(
                        "attending_course_record"
                        if rule_id == "LX0609-02-01-01"
                        else "senior_course_record"
                    ),
                    source_label=(
                        "主治医师及以上首次查房记录"
                        if rule_id == "LX0609-02-01-01"
                        else "上级医师首次查房记录"
                    ),
                    state="within",
                    threshold_hours=48 if rule_id == "LX0609-02-01-01" else 72,
                    anchor=anchor,
                    anchor_date=anchor_date,
                    observed=observed,
                    source_document_id=source_document_id,
                    failure_kind="timeliness_requirement_satisfied",
                ),
            )
        elif course_issue is not None:
            reason, technical = course_issue
            decisions.append(gap(rule_id, reason, technical=technical))
        elif rule_id == "LX0609-02-01-02" and anchor is not None and (
            maturity_decision := missing_target_decision(
                rule_id,
                anchor=anchor,
                threshold=threshold,
            )
        ) is not None:
            decisions.append(maturity_decision)
        elif qualifying_missing_time:
            decisions.append(gap(rule_id, "authoritative_time_missing"))
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
        elif ambiguous_before_deadline:
            decisions.append(gap(rule_id, "required_field_missing"))
        elif elapsed_states:
            observed, source_document_id, selected_source_key, selected_row = min(
                (
                    event
                    for event, state in zip(qualifying_events, elapsed_states)
                    if state == "over"
                ),
                key=lambda item: item[0],
            )
            decision = attach_selected_row(
                conclusive(rule_id, QcDirection.DEFECT, "threshold_exceeded"),
                source_key=selected_source_key,
                row=selected_row,
            )
            decisions.append(decision)
            add_customer_fact(
                rule_id,
                timeliness_fact(
                    rule_id=rule_id,
                    target_document=(
                        "attending_course_record"
                        if rule_id == "LX0609-02-01-01"
                        else "senior_course_record"
                    ),
                    source_label=(
                        "主治医师及以上首次查房记录"
                        if rule_id == "LX0609-02-01-01"
                        else "上级医师首次查房记录"
                    ),
                    state="late",
                    threshold_hours=48 if rule_id == "LX0609-02-01-01" else 72,
                    anchor=anchor,
                    anchor_date=anchor_date,
                    observed=observed,
                    source_document_id=source_document_id,
                ),
            )
        elif ambiguous_round:
            decisions.append(gap(rule_id, "required_field_missing"))
        else:
            missing_decision = missing_target_decision(
                rule_id,
                anchor=anchor,
                threshold=threshold,
            )
            if missing_decision is not None:
                decisions.append(missing_decision)
                continue
            # 完整查询为空且已通过成熟门，表示目标缺失；不要求补充不存在的记录。
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
                        if rule_id == "LX0609-02-01-01"
                        else "senior_course_record"
                    ),
                    source_label=(
                        "主治医师及以上首次查房记录"
                        if rule_id == "LX0609-02-01-01"
                        else "上级医师首次查房记录"
                    ),
                    state="missing",
                    threshold_hours=48 if rule_id == "LX0609-02-01-01" else 72,
                    anchor=anchor,
                    anchor_date=anchor_date,
                ),
            )
    return tuple(decisions)


def _execute_luxian_0609_native_basic_timeliness(
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
    """一次执行所选基础时限点；上级查房身份由标准文书类型直接确认。"""

    requested = tuple(dict.fromkeys(
        str(rule_id or "").strip().upper()
        for rule_id in rule_ids
        if str(rule_id or "").strip()
    ))
    selected = tuple(
        rule_id for rule_id in requested if rule_id in EXECUTABLE_BASIC_TIMELINESS_RULE_IDS
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


def _with_usage(
    result: NativeExecutionResult,
    *,
    llm_call_count: int = 1,
    prompt_tokens: int,
    completion_tokens: int,
    total_tokens: int,
    api_time: float,
    usage_observation_complete: bool = True,
) -> NativeBasicTimelinessExecutionResult:
    return NativeBasicTimelinessExecutionResult(
        results=result.results,
        planned_rule_ids=result.planned_rule_ids,
        decisions=result.decisions,
        customer_display_facts=result.customer_display_facts,
        execution_fingerprint=result.execution_fingerprint,
        terminal_reason_code=result.terminal_reason_code,
        llm_call_count=llm_call_count,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        total_tokens=total_tokens,
        api_time=api_time,
        usage_observation_complete=usage_observation_complete,
    )


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
    llm_client: BasicTimelinessLLMClient | None = None,
) -> NativeExecutionResult | Awaitable[NativeBasicTimelinessExecutionResult]:
    """按同一证据会话装配基础时限与抢救内容检查。"""
    requested = tuple(dict.fromkeys(
        str(value or "").strip().upper()
        for value in rule_ids
        if str(value or "").strip()
    ))
    legacy = _execute_luxian_0609_native_basic_timeliness(
        rule_ids=tuple(value for value in requested if value != RESCUE_COMPLETENESS_RULE_ID),
        evidence_payload=evidence_payload, institute_id=institute_id,
        patient_id=patient_id, visit_id=visit_id, source_schema=source_schema,
        evidence_snapshot=evidence_snapshot, evidence_materials=evidence_materials,
        decision_rule_ids=tuple(value for value in decision_rule_ids if str(value).strip().upper() != RESCUE_COMPLETENESS_RULE_ID),
    )
    if RESCUE_COMPLETENESS_RULE_ID not in requested:
        return legacy
    content = execute_rescue_record_completeness(
        snapshot=evidence_snapshot, materials=evidence_materials, llm_client=llm_client,
    )

    def merge(old: NativeExecutionResult, new: NativeExecutionResult) -> NativeBasicTimelinessExecutionResult:
        selected = tuple(
            rule_id for rule_id in requested
            if rule_id in EXECUTABLE_BASIC_TIMELINESS_RULE_IDS
        )
        order = {rule_id: index for index, rule_id in enumerate(selected)}
        combined = NativeExecutionResult(
            results=tuple(sorted((*old.results, *new.results), key=lambda item: order[item["rule_id"]])),
            planned_rule_ids=selected,
            decisions=tuple(sorted((*old.decisions, *new.decisions), key=lambda item: order[item.rule_id])),
            customer_display_facts=tuple(sorted((*old.customer_display_facts, *new.customer_display_facts), key=lambda item: order[item[0]])),
            execution_fingerprint=old.execution_fingerprint,
            terminal_reason_code=old.terminal_reason_code,
        )
        return _with_usage(
            combined,
            llm_call_count=getattr(old, "llm_call_count", 0) + getattr(new, "llm_call_count", 0),
            prompt_tokens=getattr(old, "prompt_tokens", 0) + getattr(new, "prompt_tokens", 0),
            completion_tokens=getattr(old, "completion_tokens", 0) + getattr(new, "completion_tokens", 0),
            total_tokens=getattr(old, "total_tokens", 0) + getattr(new, "total_tokens", 0),
            api_time=getattr(old, "api_time", 0.0) + getattr(new, "api_time", 0.0),
            usage_observation_complete=(
                getattr(old, "usage_observation_complete", True)
                and getattr(new, "usage_observation_complete", True)
            ),
        )

    if not isawaitable(legacy) and not isawaitable(content):
        return merge(legacy, content)

    async def resolve() -> NativeBasicTimelinessExecutionResult:
        old = await legacy if isawaitable(legacy) else legacy
        new = await content if isawaitable(content) else content
        return merge(old, new)

    return resolve()
