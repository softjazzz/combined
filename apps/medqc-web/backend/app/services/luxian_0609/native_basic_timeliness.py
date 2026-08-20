"""LX0609 基础时限族的原生确定性执行器。"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta
import json
import re
import time
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
from .source_evidence_reader import (
    EVALUATION_HORIZON_SOURCE_KEY,
    build_luxian_0609_course_round_timeline_from_rows,
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
_ROUND_BODY_FIELDS = ("record_content", "content", "assembled_text", "raw_text")
_MAX_SEMANTIC_ROUND_CANDIDATES = 8
_MAX_SEMANTIC_ROUND_BODY_CHARS = 1800
_ROUND_ROLE_SCHEMA_VERSION = "lx0609-006-round-role-v1"
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
        EVALUATION_HORIZON_SOURCE_KEY,
        "inpat_registration",
    ),
    "LX0609-002": (
        "admission_record",
        EVALUATION_HORIZON_SOURCE_KEY,
        "first_course_record",
        "inpat_registration",
    ),
    "LX0609-004": ("rescue_record",),
    "LX0609-005": (
        "admission_record",
        "daily_course_record",
        "discharge_record",
        EVALUATION_HORIZON_SOURCE_KEY,
        "inpat_registration",
        "senior_course_record",
    ),
    "LX0609-006": (
        "admission_record",
        "daily_course_record",
        "discharge_record",
        EVALUATION_HORIZON_SOURCE_KEY,
        "inpat_registration",
        "senior_course_record",
    ),
}


class BasicTimelinessLLMClient(Protocol):
    async def generate(self, prompt: str) -> dict[str, Any]: ...


@dataclass(frozen=True)
class NativeBasicTimelinessExecutionResult(NativeExecutionResult):
    llm_call_count: int = 0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    api_time: float = 0.0


@dataclass(frozen=True)
class _SemanticRoundCandidate:
    row: Mapping[str, Any]
    title: str
    record_time: str
    body: str


def _clean_text(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def _semantic_round_candidates(
    materials: Luxian0609EvidenceMaterialStore,
) -> tuple[_SemanticRoundCandidate, ...]:
    candidates: list[_SemanticRoundCandidate] = []
    for source_key in ("daily_course_record", "senior_course_record"):
        for row in materials.rows(source_key):
            if not isinstance(row, Mapping) or not is_generic_upper_physician_round(
                row,
                source_key=source_key,
            ):
                continue
            if (
                classify_course_round_role(row, source_key=source_key)
                is CourseRoundRole.SENIOR
            ):
                continue
            body = next(
                (
                    text
                    for field in _ROUND_BODY_FIELDS
                    if (text := _clean_text(row.get(field)))
                ),
                "",
            )
            candidates.append(
                _SemanticRoundCandidate(
                    row=row,
                    title=_clean_text(
                        row.get("document_title") or row.get("title")
                    ),
                    record_time=_clean_text(
                        row.get("record_time")
                        or row.get("record_datetime")
                        or row.get("submit_time")
                        or row.get("submit_datetime")
                    ),
                    body=body[:_MAX_SEMANTIC_ROUND_BODY_CHARS],
                )
            )
    return tuple(candidates)


def _semantic_round_prompt(
    candidates: Sequence[_SemanticRoundCandidate],
) -> str:
    documents = [
        {
            "position": position,
            "document_title": candidate.title,
            "record_time": candidate.record_time,
            "body": candidate.body,
        }
        for position, candidate in enumerate(candidates, start=1)
    ]
    return (
        "你只提取上级医师查房文书中实际参与本次查房者的职称事实，不判断质控结果。"
        "不得把会诊、邀请、既往诊疗或计划中的医师职称当成本次查房职称。"
        "只返回严格JSON，不要Markdown。schema_version固定为"
        f"{_ROUND_ROLE_SCHEMA_VERSION}。documents必须逐项返回position、role、"
        "physician_name、physician_title、evidence_quote。role只能是senior、"
        "attending_or_above、unclear；senior仅限副主任医师或主任医师，"
        "attending_or_above仅限主治医师。确认时evidence_quote必须逐字来自同一正文，"
        "并同时包含姓名和职称；无法确认时其余三个字段均为null。输入："
        + json.dumps(documents, ensure_ascii=False, separators=(",", ":"))
    )


def _response_text(response: Mapping[str, Any]) -> str:
    raw = response.get("content") or response.get("text") or ""
    return raw if isinstance(raw, str) else json.dumps(raw, ensure_ascii=False)


def _usage(response: Mapping[str, Any]) -> tuple[int, int, int, float]:
    usage = response.get("usage")
    usage = usage if isinstance(usage, Mapping) else {}
    prompt = int(usage.get("prompt_tokens") or 0)
    completion = int(usage.get("completion_tokens") or 0)
    total = int(usage.get("total_tokens") or prompt + completion)
    elapsed = float(response.get("response_time") or 0.0)
    return prompt, completion, total, elapsed


def _parse_semantic_round_roles(
    response: Mapping[str, Any],
    candidates: Sequence[_SemanticRoundCandidate],
) -> tuple[dict[int, CourseRoundRole], frozenset[int]]:
    payload = json.loads(_response_text(response))
    if not isinstance(payload, dict) or set(payload) != {"schema_version", "documents"}:
        raise ValueError("invalid semantic round payload")
    if payload.get("schema_version") != _ROUND_ROLE_SCHEMA_VERSION:
        raise ValueError("invalid semantic round schema")
    raw_documents = payload.get("documents")
    if not isinstance(raw_documents, list) or len(raw_documents) != len(candidates):
        raise ValueError("invalid semantic round documents")
    roles: dict[int, CourseRoundRole] = {}
    unresolved: set[int] = set()
    seen_positions: set[int] = set()
    expected_keys = {
        "position",
        "role",
        "physician_name",
        "physician_title",
        "evidence_quote",
    }
    for item in raw_documents:
        if not isinstance(item, dict) or set(item) != expected_keys:
            raise ValueError("invalid semantic round item")
        position = item.get("position")
        if (
            isinstance(position, bool)
            or not isinstance(position, int)
            or not 1 <= position <= len(candidates)
            or position in seen_positions
        ):
            raise ValueError("invalid semantic round position")
        seen_positions.add(position)
        candidate = candidates[position - 1]
        row_id = id(candidate.row)
        role = item.get("role")
        if role == "unclear":
            if any(
                item.get(field) not in (None, "")
                for field in ("physician_name", "physician_title", "evidence_quote")
            ):
                raise ValueError("invalid unclear semantic round evidence")
            unresolved.add(row_id)
            continue
        allowed_titles = {
            "senior": {"副主任医师", "主任医师"},
            "attending_or_above": {"主治医师"},
        }
        if role not in allowed_titles:
            raise ValueError("invalid semantic round role")
        physician_name = _clean_text(item.get("physician_name"))
        physician_title = _clean_text(item.get("physician_title"))
        evidence_quote = _clean_text(item.get("evidence_quote"))
        if (
            not physician_name
            or len(physician_name) > 40
            or physician_title not in allowed_titles[role]
            or not evidence_quote
            or len(evidence_quote) > 240
            or evidence_quote not in candidate.body
            or physician_name not in evidence_quote
            or physician_title not in evidence_quote
        ):
            raise ValueError("invalid semantic round evidence")
        roles[row_id] = (
            CourseRoundRole.SENIOR
            if role == "senior"
            else CourseRoundRole.ATTENDING_OR_ABOVE
        )
    if seen_positions != set(range(1, len(candidates) + 1)):
        raise ValueError("incomplete semantic round positions")
    return roles, frozenset(unresolved)
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
    semantic_round_roles: Mapping[int, CourseRoundRole] | None = None,
    semantic_round_unresolved: frozenset[int] = frozenset(),
    semantic_round_body_missing: frozenset[int] = frozenset(),
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
            EVALUATION_HORIZON_SOURCE_KEY,
            "inpat_registration",
        ),
        "LX0609-002": (
            "admission_record",
            EVALUATION_HORIZON_SOURCE_KEY,
            "first_course_record",
            "inpat_registration",
        ),
        "LX0609-004": ("rescue_record",),
        "LX0609-005": (
            "admission_record",
            "daily_course_record",
            "discharge_record",
            EVALUATION_HORIZON_SOURCE_KEY,
            "inpat_registration",
            "senior_course_record",
        ),
        "LX0609-006": (
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
                (event.observed_time, event.document_id)
                for event in extract_document_events(admission_rows)
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
        if maturity_state == "not_reached":
            return gap(rule_id, "evaluation_window_not_mature")
        if maturity_state == "conflict":
            return conflict(rule_id)
        return gap(rule_id, "snapshot_mismatch", technical=True)

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
                continue
            complete_events: list[tuple[datetime, str | None]] = []
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
                observed, source_document_id = min(
                    complete_events,
                    key=lambda item: item[0],
                )
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
            for event in extract_rescue_events(rescue_rows):
                record_time = event.document.observed_time
                rescue_end = event.rescue_end_time
                if record_time is None or rescue_end is None:
                    incomplete = True
                    continue
                association = associate_timeliness_event(
                    anchor_time=rescue_end,
                    observed_event=event.document,
                    threshold_hours=6,
                )
                if association is None or association.state == "before":
                    incomplete = True
                else:
                    rescue_timeline.append(
                        (
                            record_time - rescue_end,
                            rescue_end,
                            record_time,
                            event.document.document_id or "",
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
                observed, source_document_id = admission_record_events[0]
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
            if rule_id == "LX0609-005":
                return role in {
                    CourseRoundRole.ATTENDING_OR_ABOVE,
                    CourseRoundRole.SENIOR,
                }
            return role is CourseRoundRole.SENIOR

        qualifying_events: list[tuple[datetime, str | None]] = []
        qualifying_missing_time = False
        ambiguous_round = False
        semantic_round_unknown = False
        for source_key, event in course_events:
            row_id = id(event.row)
            role = (
                semantic_round_roles.get(
                    row_id,
                    classify_course_round_role(event.row, source_key=source_key),
                )
                if semantic_round_roles is not None
                else classify_course_round_role(event.row, source_key=source_key)
            )
            if rule_id == "LX0609-006":
                if row_id in semantic_round_body_missing:
                    ambiguous_round = True
                    continue
                if row_id in semantic_round_unresolved:
                    semantic_round_unknown = True
                    continue
            if qualifies(role):
                parsed = event.observed_time
                if parsed is None:
                    qualifying_missing_time = True
                else:
                    qualifying_events.append((parsed, event.document_id))
            elif role is CourseRoundRole.AMBIGUOUS:
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
            observed, source_document_id = min(
                (
                    event
                    for event, state in zip(qualifying_events, elapsed_states)
                    if state == "over"
                ),
                key=lambda item: item[0],
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
                    source_document_id=source_document_id,
                ),
            )
        elif semantic_round_unknown:
            decisions.append(
                make(
                    rule_id,
                    evidence_state=EvidenceState.CONFLICT,
                    qc_direction=QcDirection.UNKNOWN,
                    reason_code="semantic_output_unknown",
                    confidence=None,
                )
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
    semantic_round_roles: Mapping[int, CourseRoundRole] | None = None,
    semantic_round_unresolved: frozenset[int] = frozenset(),
    semantic_round_body_missing: frozenset[int] = frozenset(),
) -> NativeExecutionResult:
    """一次执行所选基础时限点；语义事实由调用方预先校验后注入。"""

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
                semantic_round_roles=semantic_round_roles,
                semantic_round_unresolved=semantic_round_unresolved,
                semantic_round_body_missing=semantic_round_body_missing,
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


def _with_semantic_usage(
    result: NativeExecutionResult,
    *,
    prompt_tokens: int,
    completion_tokens: int,
    total_tokens: int,
    api_time: float,
) -> NativeBasicTimelinessExecutionResult:
    return NativeBasicTimelinessExecutionResult(
        results=result.results,
        planned_rule_ids=result.planned_rule_ids,
        decisions=result.decisions,
        customer_display_facts=result.customer_display_facts,
        execution_fingerprint=result.execution_fingerprint,
        terminal_reason_code=result.terminal_reason_code,
        llm_call_count=1,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        total_tokens=total_tokens,
        api_time=api_time,
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
    """执行基础时限规则；仅006的通用上级医师文书允许一次受控语义提取。"""

    typed_requested = {
        str(rule_id or "").strip().upper() for rule_id in decision_rule_ids
    }
    if "LX0609-006" not in typed_requested or evidence_materials is None:
        return _execute_luxian_0609_native_basic_timeliness(
            rule_ids=rule_ids,
            evidence_payload=evidence_payload,
            institute_id=institute_id,
            patient_id=patient_id,
            visit_id=visit_id,
            source_schema=source_schema,
            evidence_snapshot=evidence_snapshot,
            evidence_materials=evidence_materials,
            decision_rule_ids=decision_rule_ids,
        )
    try:
        candidates = _semantic_round_candidates(evidence_materials)
    except (EvidenceMaterialTruncated, EvidenceMaterialUnavailable, ValueError):
        candidates = ()
    if not candidates:
        return _execute_luxian_0609_native_basic_timeliness(
            rule_ids=rule_ids,
            evidence_payload=evidence_payload,
            institute_id=institute_id,
            patient_id=patient_id,
            visit_id=visit_id,
            source_schema=source_schema,
            evidence_snapshot=evidence_snapshot,
            evidence_materials=evidence_materials,
            decision_rule_ids=decision_rule_ids,
        )

    with_body = tuple(candidate for candidate in candidates if candidate.body)
    body_missing = frozenset(id(candidate.row) for candidate in candidates if not candidate.body)
    initially_unresolved = frozenset(id(candidate.row) for candidate in with_body)
    baseline = _execute_luxian_0609_native_basic_timeliness(
        rule_ids=rule_ids,
        evidence_payload=evidence_payload,
        institute_id=institute_id,
        patient_id=patient_id,
        visit_id=visit_id,
        source_schema=source_schema,
        evidence_snapshot=evidence_snapshot,
        evidence_materials=evidence_materials,
        decision_rule_ids=decision_rule_ids,
        semantic_round_unresolved=initially_unresolved,
        semantic_round_body_missing=body_missing,
    )
    senior_decision = next(
        (item for item in baseline.decisions if item.rule_id == "LX0609-006"),
        None,
    )
    if (
        senior_decision is not None
        and senior_decision.qc_direction is QcDirection.SATISFIED
    ):
        return baseline
    if (
        llm_client is None
        or not with_body
        or len(with_body) > _MAX_SEMANTIC_ROUND_CANDIDATES
    ):
        return baseline

    async def resolve_semantic_rounds() -> NativeBasicTimelinessExecutionResult:
        started = time.perf_counter()
        prompt_tokens = completion_tokens = total_tokens = 0
        api_time = 0.0
        try:
            response = await llm_client.generate(_semantic_round_prompt(with_body))
            prompt_tokens, completion_tokens, total_tokens, api_time = _usage(response)
            roles, unresolved = _parse_semantic_round_roles(response, with_body)
        except Exception:
            return _with_semantic_usage(
                baseline,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                total_tokens=total_tokens,
                api_time=api_time or (time.perf_counter() - started),
            )
        resolved = _execute_luxian_0609_native_basic_timeliness(
            rule_ids=rule_ids,
            evidence_payload=evidence_payload,
            institute_id=institute_id,
            patient_id=patient_id,
            visit_id=visit_id,
            source_schema=source_schema,
            evidence_snapshot=evidence_snapshot,
            evidence_materials=evidence_materials,
            decision_rule_ids=decision_rule_ids,
            semantic_round_roles=roles,
            semantic_round_unresolved=unresolved,
            semantic_round_body_missing=body_missing,
        )
        return _with_semantic_usage(
            resolved,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
            api_time=api_time or (time.perf_counter() - started),
        )

    return resolve_semantic_rounds()
