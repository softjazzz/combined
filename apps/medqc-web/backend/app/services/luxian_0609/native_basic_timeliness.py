"""LX0609 基础时限族的原生确定性执行器。"""

from __future__ import annotations

from datetime import datetime, timedelta
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
    "LX0609-001": ("admission_record", "inpat_registration"),
    "LX0609-002": (
        "admission_record",
        "first_course_record",
        "inpat_registration",
    ),
    "LX0609-004": ("rescue_record",),
    "LX0609-005": (
        "admission_record",
        "daily_course_record",
        "inpat_registration",
        "senior_course_record",
    ),
    "LX0609-006": (
        "admission_record",
        "daily_course_record",
        "inpat_registration",
        "senior_course_record",
    ),
}
_ATTENDING_MARKERS = ("主治医师", "主治查房", "代主治医师", "代主治查房")
_SENIOR_MARKERS = ("副主任医师", "主任医师", "副主任查房", "主任查房", "高级职称")
_AUTHORITATIVE_DATETIME_PATTERN = re.compile(
    r"^\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}(?::\d{2}(?:\.\d{1,6})?)?$"
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


def _typed_basic_decisions(
    *,
    rule_ids: tuple[str, ...],
    snapshot: Luxian0609EvidenceSnapshot,
    materials: Luxian0609EvidenceMaterialStore,
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
        "LX0609-001": ("admission_record", "inpat_registration"),
        "LX0609-002": (
            "admission_record",
            "first_course_record",
            "inpat_registration",
        ),
        "LX0609-004": ("rescue_record",),
        "LX0609-005": (
            "admission_record",
            "daily_course_record",
            "inpat_registration",
            "senior_course_record",
        ),
        "LX0609-006": (
            "admission_record",
            "daily_course_record",
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
    admission_rows: tuple[Mapping[str, Any], ...] = ()
    registration_rows: tuple[Mapping[str, Any], ...] = ()
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

    admission_record_times = tuple(
        sorted(
            parsed
            for row in admission_rows
            if (parsed := _authoritative_time(row.get("record_time"))) is not None
        )
    )
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

    def admission_anchor(rule_id: str) -> tuple[datetime | None, RuleDecision | None]:
        if admission_issue is not None:
            reason, technical = admission_issue
            return None, gap(rule_id, reason, technical=technical)
        if registration_issue is not None:
            reason, technical = registration_issue
            return None, gap(rule_id, reason, technical=technical)
        registration_state = observation_by_source[
            "inpat_registration"
        ].query_state.value
        if registration_state == "available":
            if not registration_times:
                return None, gap(rule_id, "authoritative_time_missing")
            return registration_times[0], None
        if not admission_record_admission_times:
            return None, gap(rule_id, "authoritative_time_missing")
        return admission_record_admission_times[0], None

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

    decisions: list[RuleDecision] = []
    for rule_id in rule_ids:
        if rule_id == "LX0609-002":
            anchor, anchor_gap = admission_anchor(rule_id)
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
            complete_times: list[datetime] = []
            incomplete = False
            for row in first_course_rows:
                record_time = _authoritative_time(row.get("record_time"))
                substantive = _is_substantive_first_course_text(
                    row.get("record_content")
                )
                if record_time is None or not substantive:
                    incomplete = True
                else:
                    complete_times.append(record_time)
            deltas = sorted(value - anchor for value in complete_times)
            if any(timedelta(0) <= delta <= timedelta(hours=8) for delta in deltas):
                decisions.append(
                    conclusive(
                        rule_id,
                        QcDirection.SATISFIED,
                        "requirement_within_threshold",
                    )
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
                decisions.append(
                    conclusive(rule_id, QcDirection.DEFECT, "threshold_exceeded")
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
            rescue_deltas: list[timedelta] = []
            incomplete = False
            for row in rescue_rows:
                record_time = _authoritative_time(row.get("record_time"))
                rescue_end = parse_luxian_0609_rescue_end_time(
                    row.get("record_content")
                )
                if record_time is None or rescue_end is None:
                    incomplete = True
                    continue
                delta = record_time - rescue_end
                if delta < timedelta(0):
                    incomplete = True
                else:
                    rescue_deltas.append(delta)
            if any(delta > timedelta(hours=6) for delta in rescue_deltas):
                decisions.append(
                    conclusive(rule_id, QcDirection.DEFECT, "threshold_exceeded")
                )
            elif incomplete:
                decisions.append(gap(rule_id, "required_field_missing"))
            elif rescue_deltas:
                decisions.append(
                    conclusive(
                        rule_id,
                        QcDirection.SATISFIED,
                        "requirement_within_threshold",
                    )
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
                decisions.append(
                    conclusive(
                        rule_id,
                        QcDirection.DEFECT,
                        "required_document_missing",
                    )
                )
                continue
            if not admission_record_times:
                decisions.append(gap(rule_id, "authoritative_time_missing"))
                continue
            anchor, anchor_gap = admission_anchor(rule_id)
            if anchor_gap is not None or anchor is None:
                decisions.append(anchor_gap or gap(rule_id, "authoritative_time_missing"))
                continue
            delta = admission_record_times[0] - anchor
            if delta < timedelta(0):
                decisions.append(
                    make(
                        rule_id,
                        evidence_state=EvidenceState.CONFLICT,
                        qc_direction=QcDirection.UNKNOWN,
                        reason_code="evidence_conflict",
                        confidence=None,
                    )
                )
            elif delta <= timedelta(hours=24):
                decisions.append(
                    conclusive(
                        rule_id,
                        QcDirection.SATISFIED,
                        "requirement_within_threshold",
                    )
                )
            elif len(admission_record_times) < len(admission_rows):
                decisions.append(gap(rule_id, "authoritative_time_missing"))
            else:
                decisions.append(
                    conclusive(rule_id, QcDirection.DEFECT, "threshold_exceeded")
                )
            continue

        anchor, anchor_gap = admission_anchor(rule_id)
        if anchor_gap is not None or anchor is None:
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
                return not any(marker in title for marker in _SENIOR_MARKERS) and any(
                    marker in title for marker in _ATTENDING_MARKERS
                )
            return any(marker in title for marker in _SENIOR_MARKERS)

        qualifying_times: list[datetime] = []
        qualifying_missing_time = False
        ambiguous_round = False
        for row in course_rows:
            title = str(row.get("document_title") or row.get("title") or "").strip()
            if qualifies(title):
                parsed = _authoritative_time(row.get("record_time"))
                if parsed is None:
                    qualifying_missing_time = True
                else:
                    qualifying_times.append(parsed)
            elif not title or (
                "查房" in title
                and not any(
                    marker in title
                    for marker in (*_ATTENDING_MARKERS, *_SENIOR_MARKERS)
                )
            ):
                ambiguous_round = True

        threshold = timedelta(hours=48 if rule_id == "LX0609-005" else 72)
        deltas = sorted(value - anchor for value in qualifying_times)
        if any(timedelta(0) <= delta <= threshold for delta in deltas):
            decisions.append(
                conclusive(
                    rule_id,
                    QcDirection.SATISFIED,
                    "requirement_within_threshold",
                )
            )
        elif qualifying_missing_time:
            decisions.append(gap(rule_id, "authoritative_time_missing"))
        elif course_issue is not None:
            reason, technical = course_issue
            decisions.append(gap(rule_id, reason, technical=technical))
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
            decisions.append(
                conclusive(rule_id, QcDirection.DEFECT, "threshold_exceeded")
            )
        elif ambiguous_round:
            decisions.append(gap(rule_id, "required_field_missing"))
        else:
            decisions.append(
                conclusive(
                    rule_id,
                    QcDirection.DEFECT,
                    "required_document_missing",
                )
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
        decisions = (
            _typed_basic_decisions(
                rule_ids=typed_selected,
                snapshot=evidence_snapshot,
                materials=evidence_materials,
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
    )
