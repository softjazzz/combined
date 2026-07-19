"""LX0609-021/022/023 会诊质量原生执行器。

第一阶段只抽取会诊申请与意见事实；仅在 023 需要且存在会诊后病程候选时，
第二阶段才核对执行记录。模型只产生受控事实，最终状态始终由 Python 映射。
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import json
import time
from typing import Any, Mapping, Protocol, Sequence

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
from .evidence_snapshot import Luxian0609EvidenceSnapshot, SourceCompleteness
from .native_execution import build_luxian_0609_native_result
from .source_evidence_reader import (
    SourceEvidenceQueryError,
    SourceEvidenceTruncated,
    SourceEvidenceUnavailable,
    read_luxian_0609_native_source_rows,
)


CONSULTATION_RULE_IDS = ("LX0609-021", "LX0609-022", "LX0609-023")
EXECUTOR_KEY = "consultation_quality"
_STAGE1_SOURCE = "consultation_record"
_COURSE_SOURCES = ("daily_course_record", "senior_course_record")
_SUPPORT_SOURCES = (
    "inpat_drug_order",
    "exam_item_report",
    "labtest_item_report",
    "surgery_record",
)
_STAGE2_SOURCES = (*_COURSE_SOURCES, *_SUPPORT_SOURCES)
_SOURCE_LIMITS = {
    "consultation_record": 48,
    "daily_course_record": 48,
    "senior_course_record": 48,
    "inpat_drug_order": 64,
    "exam_item_report": 32,
    "labtest_item_report": 32,
    "surgery_record": 24,
}
_MAX_CONTENT_CHARS = 1600
_MAX_STAGE1_CHARS = 48000
_MAX_STAGE2_CHARS = 56000
_APPLICATION_STATES = frozenset({"clear", "vague", "missing", "absent", "unknown"})
_OPINION_STATES = frozenset({"clear", "vague", "missing", "absent", "unknown"})
_RECOMMENDATION_TYPES = frozenset(
    {
        "medication",
        "examination",
        "laboratory",
        "surgery",
        "treatment",
        "monitoring",
        "follow_up",
        "other",
    }
)
_EXECUTION_QUALITIES = frozenset(
    {"specific", "vague_or_copied", "absent", "unknown"}
)
_IMPLEMENTATION_MATCHES = frozenset({"supported", "contradicted", "unknown"})
_ASSOCIATION_STATES = frozenset(
    {"explicit", "contextual", "ambiguous", "none", "unknown"}
)
_LINKED_ASSOCIATION_STATES = frozenset({"explicit", "contextual"})
_EVALUATOR_VERSION = "consultation-021-023-v2"


class ConsultationLLMClient(Protocol):
    async def generate(self, prompt: str) -> dict[str, Any]: ...


@dataclass(frozen=True)
class NativeConsultationExecutionResult:
    results: tuple[dict[str, Any], ...]
    planned_rule_ids: tuple[str, ...]
    decisions: tuple[RuleDecision, ...] = ()
    llm_call_count: int = 0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    api_time: float = 0.0


@dataclass(frozen=True)
class _Episode:
    episode_ref: str
    application_state: str
    opinion_state: str
    recommendations: tuple[tuple[str, str, str], ...]
    confidence: float


@dataclass(frozen=True)
class _Outcome:
    rule_id: str
    status: str
    reason_code: str


class _SemanticInvalid(Exception):
    pass


class _SourceGap(Exception):
    pass


class _SourceTechnical(Exception):
    pass


def _clean(value: Any) -> str:
    return " ".join(str(value or "").split())


def _parse_time(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    text = value.strip().replace("T", " ")
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        return datetime.fromisoformat(text)
    except ValueError:
        return None


def _row_time(row: Mapping[str, Any]) -> datetime | None:
    for key in (
        "record_time",
        "prescribed_datetime",
        "report_time",
        "report_datetime",
        "surgery_begin_time",
        "surgery_begin_datetime",
    ):
        parsed = _parse_time(row.get(key))
        if parsed is not None:
            return parsed
    return None


def _has_mixed_timezone(values: Sequence[datetime]) -> bool:
    """禁止把无时区本地时间与带时区时间直接混算。"""

    return len({value.utcoffset() is not None for value in values}) > 1


def _row_text(source_key: str, row: Mapping[str, Any]) -> str:
    fields = {
        "consultation_record": ("document_title", "record_content"),
        "daily_course_record": ("document_title", "record_content"),
        "senior_course_record": ("document_title", "record_content"),
        "inpat_drug_order": (
            "generic_name",
            "brand_name",
            "drug_type",
            "drug_apply_method",
            "drug_frequency",
            "order_status",
        ),
        "exam_item_report": (
            "item_name",
            "exam_name",
            "exam_result",
            "exam_impression",
            "exam_conclusion",
        ),
        "labtest_item_report": (
            "item_name",
            "lab_item_name",
            "result",
            "abnormal_indicator",
        ),
        "surgery_record": ("surgery_name", "surgery_process"),
    }[source_key]
    return _clean("；".join(_clean(row.get(field)) for field in fields if _clean(row.get(field))))


def _usage(response: Mapping[str, Any]) -> tuple[int, int, int, float]:
    usage = response.get("usage")
    usage = usage if isinstance(usage, Mapping) else {}
    prompt = int(usage.get("prompt_tokens") or usage.get("input_tokens") or 0)
    completion = int(usage.get("completion_tokens") or usage.get("output_tokens") or 0)
    total = int(usage.get("total_tokens") or prompt + completion)
    api_time = float(
        response.get("_api_time")
        or response.get("api_time")
        or response.get("latency")
        or 0.0
    )
    return prompt, completion, total, api_time


def _payload(response: Mapping[str, Any]) -> Mapping[str, Any]:
    raw: Any = response.get("content")
    if raw is None:
        raw = response.get("text")
    if raw is None:
        choices = response.get("choices")
        if isinstance(choices, list) and choices and isinstance(choices[0], Mapping):
            message = choices[0].get("message")
            if isinstance(message, Mapping):
                raw = message.get("content")
    if isinstance(raw, Mapping):
        return raw
    if not isinstance(raw, str):
        raise _SemanticInvalid()
    text = raw.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        text = "\n".join(lines[1:-1]).strip()
        if text.startswith("json"):
            text = text[4:].lstrip()
    try:
        parsed = json.loads(text)
    except (TypeError, ValueError) as exc:
        raise _SemanticInvalid() from exc
    if not isinstance(parsed, Mapping):
        raise _SemanticInvalid()
    return parsed


def _confidence(value: Any) -> float:
    if isinstance(value, str):
        mapping = {"high": 0.9, "medium": 0.6, "low": 0.3}
        value = mapping.get(value.strip().lower())
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise _SemanticInvalid()
    confidence = float(value)
    if not 0 <= confidence <= 1:
        raise _SemanticInvalid()
    return confidence


def _read_source(
    *,
    source_key: str,
    institute_id: str,
    patient_id: str,
    visit_id: str,
    source_schema: str | None,
    evidence_materials: Luxian0609EvidenceMaterialStore | None,
    evidence_snapshot: Luxian0609EvidenceSnapshot | None,
) -> list[dict[str, Any]]:
    try:
        if evidence_materials is not None:
            if (
                type(evidence_snapshot) is not Luxian0609EvidenceSnapshot
                or evidence_materials.snapshot_hash != evidence_snapshot.snapshot_hash
            ):
                raise _SourceTechnical()
            observation = next(
                (
                    item
                    for item in evidence_snapshot.observations
                    if item.source_key == source_key
                ),
                None,
            )
            if observation is None:
                raise _SourceGap()
            if observation.query_state.value == "error":
                raise _SourceTechnical()
            if observation.query_state.value == "unavailable":
                raise _SourceGap()
            if observation.completeness is SourceCompleteness.TRUNCATED:
                raise _SourceGap()
            material_rows = [
                dict(row) for row in evidence_materials.bounded_rows(source_key)
            ]
            if len(material_rows) >= _SOURCE_LIMITS[source_key]:
                raise _SourceGap()
            return material_rows
        rows = read_luxian_0609_native_source_rows(
            source_key=source_key,
            institute_id=institute_id,
            patient_id=patient_id,
            visit_id=visit_id,
            source_schema=source_schema,
        )
    except (EvidenceMaterialTruncated, EvidenceMaterialUnavailable):
        raise _SourceGap()
    except (SourceEvidenceUnavailable, SourceEvidenceTruncated):
        raise _SourceGap()
    except SourceEvidenceQueryError:
        raise _SourceTechnical()
    except (_SourceGap, _SourceTechnical):
        raise
    except Exception:
        raise _SourceTechnical()
    if len(rows) >= _SOURCE_LIMITS[source_key]:
        raise _SourceGap()
    return [dict(row) for row in rows]


def _documents(source_key: str, rows: Sequence[Mapping[str, Any]]) -> tuple[dict[str, Any], ...]:
    documents: list[dict[str, Any]] = []
    for index, row in enumerate(rows, start=1):
        text = _row_text(source_key, row)
        if len(text) > _MAX_CONTENT_CHARS:
            raise _SourceGap()
        documents.append(
            {
                "ref": f"{source_key}-{index}",
                "time": _clean(
                    row.get("record_time")
                    or row.get("prescribed_datetime")
                    or row.get("report_time")
                    or row.get("report_datetime")
                    or row.get("surgery_begin_time")
                    or row.get("surgery_begin_datetime")
                ),
                "text": text,
            }
        )
    return tuple(documents)


def _stage1_prompt(documents: Sequence[Mapping[str, Any]]) -> str:
    payload = json.dumps({"consultations": list(documents)}, ensure_ascii=False)
    if len(payload) > _MAX_STAGE1_CHARS:
        raise _SourceGap()
    return (
        "你只做本次住院会诊事实抽取，不做质控结论。每个输入ref必须且只能输出一次。"
        "application_state和opinion_state只能为clear/vague/missing/absent/unknown。"
        "absent表示对应角色在该文书中不存在；missing表示角色存在但内容空缺；"
        "vague表示只有泛化措辞；clear表示有明确临床目的或具体意见。"
        "application_state中，具体症状、检查、诊断或评估判为clear；"
        "只有申请会诊、协助诊治等泛化目的判为vague。"
        "opinion_state中，具体诊断、检查、治疗、用药、复查或处置判为clear；"
        "泛化原则判为vague。"
        "application_state只评申请段，不得用意见段、标题或签名补足；"
        "opinion_state只评意见段，不得用申请段、标题或签名补足。"
        "normalized_recommendations仅从会诊意见提取，元素字段只能为"
        "type(medication/examination/laboratory/surgery/treatment/monitoring/follow_up/other)、"
        "item（不超过80字的归一化事项）。每个可执行动作必须逐项列入"
        "normalized_recommendations，不得由Python猜测或补全动作。不得引用输入外信息。"
        "严格输出JSON对象{episodes:[{episode_ref,application_state,opinion_state,"
        "normalized_recommendations,confidence,input_refs}]}。输入：" + payload
    )


def _invalid_episode(episode_ref: str) -> _Episode:
    return _Episode(episode_ref, "unknown", "unknown", (), 0.0)


def _parse_stage1(
    payload: Mapping[str, Any], expected_refs: tuple[str, ...]
) -> tuple[_Episode, ...]:
    raw_episodes = payload.get("episodes")
    if not isinstance(raw_episodes, list) or len(raw_episodes) != len(expected_refs):
        raise _SemanticInvalid()
    # episode_ref 承担顶层覆盖身份：缺失、越界或重复均使整包无效。
    seen: set[str] = set()
    identified: list[tuple[str, Mapping[str, Any]]] = []
    for raw in raw_episodes:
        if not isinstance(raw, Mapping):
            raise _SemanticInvalid()
        episode_ref = _clean(raw.get("episode_ref"))
        if episode_ref not in expected_refs or episode_ref in seen:
            raise _SemanticInvalid()
        seen.add(episode_ref)
        identified.append((episode_ref, raw))
    if seen != set(expected_refs):
        raise _SemanticInvalid()

    episodes: list[_Episode] = []
    for episode_ref, raw in identified:
        try:
            input_refs = raw.get("input_refs")
            if not isinstance(input_refs, list) or input_refs != [episode_ref]:
                raise _SemanticInvalid()
            application = _clean(raw.get("application_state")).lower()
            opinion = _clean(raw.get("opinion_state")).lower()
            if (
                application not in _APPLICATION_STATES
                or opinion not in _OPINION_STATES
            ):
                raise _SemanticInvalid()
            confidence = _confidence(raw.get("confidence"))
            recommendations_raw = raw.get("normalized_recommendations")
            if not isinstance(recommendations_raw, list):
                raise _SemanticInvalid()
            recommendations: list[tuple[str, str, str]] = []
            local_facts: set[tuple[str, str]] = set()
            for item in recommendations_raw:
                if not isinstance(item, Mapping):
                    raise _SemanticInvalid()
                kind = _clean(item.get("type")).lower()
                normalized = _clean(item.get("item"))
                if (
                    kind not in _RECOMMENDATION_TYPES
                    or not normalized
                    or len(normalized) > 80
                ):
                    raise _SemanticInvalid()
                fact_key = (kind, normalized)
                if fact_key in local_facts:
                    continue
                local_facts.add(fact_key)
                ref = f"{episode_ref}-recommendation-{len(recommendations) + 1}"
                recommendations.append((ref, kind, normalized))
            if opinion in {"missing", "absent", "unknown"} and recommendations:
                raise _SemanticInvalid()
        except _SemanticInvalid:
            episodes.append(_invalid_episode(episode_ref))
            continue
        episodes.append(
            _Episode(
                episode_ref,
                application,
                opinion,
                tuple(recommendations),
                confidence,
            )
        )
    return tuple(sorted(episodes, key=lambda item: expected_refs.index(item.episode_ref)))


def _state_outcome(rule_id: str, episodes: Sequence[_Episode]) -> _Outcome:
    key = "application_state" if rule_id == "LX0609-021" else "opinion_state"
    states = tuple(getattr(item, key) for item in episodes)
    applicable_states = tuple(state for state in states if state != "absent")
    if any(state in {"missing", "vague"} for state in applicable_states):
        return _Outcome(rule_id, "non_compliant", "requirement_violated")
    if any(item.confidence < 0.8 for item in episodes) or "unknown" in states:
        return _Outcome(rule_id, "evaluation_unknown", "semantic_low_confidence")
    if not applicable_states:
        return _Outcome(rule_id, "not_applicable", "trigger_absent_complete")
    if all(state == "clear" for state in applicable_states):
        return _Outcome(rule_id, "compliant", "requirement_satisfied")
    return _Outcome(rule_id, "evaluation_unknown", "semantic_output_unknown")


def _stage2_prompt(
    episodes: Sequence[_Episode],
    documents: Sequence[Mapping[str, Any]],
    consultation_time_by_ref: Mapping[str, datetime],
    allowed_refs_by_episode: Mapping[str, frozenset[str]],
) -> str:
    facts = [
        {
            "episode_ref": episode.episode_ref,
            "consultation_time": consultation_time_by_ref[episode.episode_ref].isoformat(
                sep=" "
            ),
            "allowed_evidence_refs": sorted(
                allowed_refs_by_episode[episode.episode_ref]
            ),
            "recommendations": [
                {"recommendation_ref": ref, "type": kind, "item": item}
                for ref, kind, item in episode.recommendations
            ],
        }
        for episode in episodes
        if episode.recommendations
    ]
    payload = json.dumps(
        {"consultation_facts": facts, "post_consultation_evidence": list(documents)},
        ensure_ascii=False,
    )
    if len(payload) > _MAX_STAGE2_CHARS:
        raise _SourceGap()
    return (
        "你只核对会诊后病程是否具体记录了会诊意见执行情况。必须逐recommendation输出一次。"
        "execution_record_quality只能为specific/vague_or_copied/absent/unknown；"
        "implementation_match只能为supported/contradicted/unknown。"
        "association_state只能为explicit/contextual/ambiguous/none/unknown："
        "explicit表示执行记录明确指向该会诊或该条意见；contextual表示虽未点名会诊，"
        "但具体临床动作和上下文只能对应这一episode及recommendation；"
        "ambiguous表示可能对应多个会诊或多条意见；none表示没有关联执行证据。"
        "只有daily_course_record或senior_course_record可作为执行记录证明；医嘱、检查、检验、"
        "手术仅可佐证关联，不能单独把absent提升为specific。每条execution的evidence_refs"
        "必须是同一episode的allowed_evidence_refs子集，禁止跨episode或引用会诊前材料；"
        "时间先后只用于排除不可能证据，绝不能仅因发生在会诊后就判定有关联。"
        "多次会诊重叠时必须分别核对，无法唯一归属就输出association_state=ambiguous。"
        "没有合法执行证据时必须输出execution_record_quality=absent、"
        "implementation_match=unknown、association_state=none、evidence_refs=[]。"
        "严格输出JSON对象"
        "{executions:[{episode_ref,recommendation_ref,execution_record_quality,"
        "implementation_match,association_state,evidence_refs,confidence}]}。输入：" + payload
    )


def _parse_stage2(
    payload: Mapping[str, Any],
    episodes: Sequence[_Episode],
    allowed_refs: frozenset[str],
    course_refs: frozenset[str],
    allowed_refs_by_episode: Mapping[str, frozenset[str]],
) -> tuple[tuple[str, str], ...]:
    expected = {
        (episode.episode_ref, recommendation[0])
        for episode in episodes
        for recommendation in episode.recommendations
    }
    raw_items = payload.get("executions")
    if not isinstance(raw_items, list) or len(raw_items) != len(expected):
        raise _SemanticInvalid()
    reused_refs: dict[str, set[str]] = {}
    for raw in raw_items:
        if not isinstance(raw, Mapping):
            continue
        episode_ref = _clean(raw.get("episode_ref"))
        refs = raw.get("evidence_refs")
        if episode_ref and isinstance(refs, list):
            for ref in refs:
                if (
                    isinstance(ref, str)
                    and ref in allowed_refs_by_episode.get(episode_ref, frozenset())
                ):
                    reused_refs.setdefault(ref, set()).add(episode_ref)
    seen: set[tuple[str, str]] = set()
    states: list[tuple[str, str]] = []
    for raw in raw_items:
        if not isinstance(raw, Mapping):
            raise _SemanticInvalid()
        key = (_clean(raw.get("episode_ref")), _clean(raw.get("recommendation_ref")))
        quality = _clean(raw.get("execution_record_quality")).lower()
        match = _clean(raw.get("implementation_match")).lower()
        association = _clean(raw.get("association_state")).lower()
        refs = raw.get("evidence_refs")
        if (
            key not in expected
            or key in seen
        ):
            raise _SemanticInvalid()
        refs_are_valid = (
            isinstance(refs, list)
            and all(isinstance(ref, str) for ref in refs)
            and len(refs) == len(set(refs))
        )
        safe_refs = refs if refs_are_valid else []
        try:
            confidence = _confidence(raw.get("confidence"))
        except _SemanticInvalid:
            confidence = None
        item_invalid = (
            quality not in _EXECUTION_QUALITIES
            or match not in _IMPLEMENTATION_MATCHES
            or association not in _ASSOCIATION_STATES
            or confidence is None
            or not refs_are_valid
            or any(ref not in allowed_refs for ref in safe_refs)
            or any(
                ref not in allowed_refs_by_episode.get(key[0], frozenset())
                for ref in safe_refs
            )
        )
        association_is_ambiguous = association in {"ambiguous", "unknown"}
        linked_quality_without_link = (
            quality in {"specific", "vague_or_copied"}
            and association not in _LINKED_ASSOCIATION_STATES
        )
        linked_without_refs = (
            association in _LINKED_ASSOCIATION_STATES and not safe_refs
        )
        ref_reused_across_episodes = any(
            len(reused_refs.get(ref, set())) > 1 for ref in safe_refs
        )
        invalid_absent_shape = quality == "absent" and not (
            match == "unknown" and association == "none" and not safe_refs
        )
        if item_invalid:
            states.append(("unknown", "semantic_low_confidence"))
        elif (
            association_is_ambiguous
            or linked_quality_without_link
            or linked_without_refs
            or ref_reused_across_episodes
            or invalid_absent_shape
        ):
            states.append(("unknown", "semantic_low_confidence"))
        elif quality == "absent":
            states.append(("absent", "unknown"))
        elif (
            confidence < 0.8
            or quality == "unknown"
            or (match == "unknown" and quality != "vague_or_copied")
        ):
            states.append(("unknown", "semantic_low_confidence"))
        elif quality in {"specific", "vague_or_copied"} and not (
            set(safe_refs) & course_refs
        ):
            states.append(("unknown", "semantic_low_confidence"))
        elif quality == "absent":
            states.append(("unknown", "semantic_low_confidence"))
        else:
            states.append((quality, match))
        seen.add(key)
    if seen != expected:
        raise _SemanticInvalid()
    return tuple(states)


def _result(outcome: _Outcome) -> dict[str, Any]:
    item = build_luxian_0609_native_result(
        rule_id=outcome.rule_id,
        final_state=outcome.status,
        finding_kind=(
            "requirement_satisfied"
            if outcome.status == "compliant"
            else outcome.status
        ),
        reason_code=outcome.reason_code,
    )
    messages = {
        "compliant": ("会诊记录满足该项要求。", ""),
        "non_compliant": ("会诊记录未满足该项要求。", "请补充明确、具体的会诊记录。"),
        "not_applicable": ("当前就诊无可评价的会诊事项，本项不适用。", ""),
        "data_gap": ("会诊相关资料不足，暂不能可靠判断。", "请补齐相关资料后重新质控。"),
        "evaluation_unknown": ("会诊语义证据无法稳定判定。", "建议复核相关会诊记录。"),
        "technical_error": ("会诊质量自动判定暂不可用。", "请稍后重试。"),
    }
    item["findings"], item["suggestion"] = messages[outcome.status]
    metadata = dict(item.get("metadata") or {})
    metadata.update(
        {
            "execution_source": "lx0609_native",
            "executor_type": "llm_fact_then_program",
        }
    )
    item["metadata"] = metadata
    return item


def _decision(
    outcome: _Outcome, snapshot: Luxian0609EvidenceSnapshot
) -> RuleDecision:
    source_keys = (
        {_STAGE1_SOURCE}
        if outcome.rule_id in {"LX0609-021", "LX0609-022"}
        else {_STAGE1_SOURCE, *_STAGE2_SOURCES}
    )
    refs = tuple(
        observation.snapshot_ref.removeprefix("sha256:")
        for observation in snapshot.observations
        if observation.source_key in source_keys
    )
    if not refs:
        raise ValueError("typed consultation decision requires fact refs")
    dimensions = {
        "compliant": (
            ApplicabilityState.APPLICABLE,
            EvidenceState.SUFFICIENT,
            QcDirection.SATISFIED,
            "requirement_satisfied",
        ),
        "non_compliant": (
            ApplicabilityState.APPLICABLE,
            EvidenceState.SUFFICIENT,
            QcDirection.DEFECT,
            "requirement_violated",
        ),
        "not_applicable": (
            ApplicabilityState.NOT_APPLICABLE,
            EvidenceState.SUFFICIENT,
            QcDirection.UNKNOWN,
            "trigger_absent_complete",
        ),
        "data_gap": (
            ApplicabilityState.UNKNOWN,
            EvidenceState.DATA_GAP,
            QcDirection.UNKNOWN,
            "source_unavailable",
        ),
        "evaluation_unknown": (
            ApplicabilityState.UNKNOWN,
            EvidenceState.CONFLICT,
            QcDirection.UNKNOWN,
            "semantic_output_unknown",
        ),
        "technical_error": (
            ApplicabilityState.ERROR,
            EvidenceState.TECHNICAL_ERROR,
            QcDirection.UNKNOWN,
            "model_transport_error",
        ),
    }[outcome.status]
    applicability, evidence_state, direction, _reason = dimensions
    return RuleDecision(
        rule_id=outcome.rule_id,
        snapshot_hash=snapshot.snapshot_hash,
        applicability=applicability,
        evidence_state=evidence_state,
        qc_direction=direction,
        reason_code=outcome.reason_code,
        fact_refs=refs,
        evaluator_version=_EVALUATOR_VERSION,
        confidence=None,
    )


def _finish(
    *,
    selected: tuple[str, ...],
    outcomes: Sequence[_Outcome],
    decision_rule_ids: frozenset[str],
    snapshot: Luxian0609EvidenceSnapshot | None,
    calls: int = 0,
    prompt_tokens: int = 0,
    completion_tokens: int = 0,
    total_tokens: int = 0,
    api_time: float = 0.0,
) -> NativeConsultationExecutionResult:
    by_id = {item.rule_id: item for item in outcomes}
    ordered = tuple(by_id[rule_id] for rule_id in selected)
    decisions = tuple(
        _decision(item, snapshot)
        for item in ordered
        if item.rule_id in decision_rule_ids and snapshot is not None
    )
    results = tuple(_result(item) for item in ordered if item.rule_id not in decision_rule_ids)
    return NativeConsultationExecutionResult(
        results=results,
        planned_rule_ids=selected,
        decisions=decisions,
        llm_call_count=calls,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        total_tokens=total_tokens,
        api_time=api_time,
    )


async def execute_luxian_0609_native_consultation_021_023_rules(
    *,
    rule_ids: Sequence[str],
    institute_id: str,
    patient_id: str,
    visit_id: str,
    source_schema: str | None,
    llm_client: ConsultationLLMClient | None,
    evidence_materials: Luxian0609EvidenceMaterialStore | None = None,
    evidence_snapshot: Luxian0609EvidenceSnapshot | None = None,
    decision_rule_ids: Sequence[str] = (),
) -> NativeConsultationExecutionResult:
    requested = {str(item or "").strip().upper() for item in rule_ids}
    selected = tuple(item for item in CONSULTATION_RULE_IDS if item in requested)
    typed = frozenset(str(item or "").strip().upper() for item in decision_rule_ids)
    if not typed.issubset(set(selected)):
        raise ValueError("unsupported typed consultation rule scope")
    if not selected:
        return NativeConsultationExecutionResult((), ())
    if not all(isinstance(value, str) and value.strip() for value in (institute_id, patient_id, visit_id)):
        outcomes = tuple(_Outcome(item, "technical_error", "source_query_error") for item in selected)
        return _finish(selected=selected, outcomes=outcomes, decision_rule_ids=typed, snapshot=evidence_snapshot)
    if evidence_materials is not None and (
        type(evidence_snapshot) is not Luxian0609EvidenceSnapshot
        or evidence_materials.snapshot_hash != evidence_snapshot.snapshot_hash
    ):
        outcomes = tuple(_Outcome(item, "technical_error", "snapshot_mismatch") for item in selected)
        return _finish(selected=selected, outcomes=outcomes, decision_rule_ids=typed, snapshot=evidence_snapshot)
    try:
        consultation_rows = _read_source(
            source_key=_STAGE1_SOURCE,
            institute_id=institute_id,
            patient_id=patient_id,
            visit_id=visit_id,
            source_schema=source_schema,
            evidence_materials=evidence_materials,
            evidence_snapshot=evidence_snapshot,
        )
        consultation_docs = _documents(_STAGE1_SOURCE, consultation_rows)
    except _SourceGap:
        outcomes = tuple(_Outcome(item, "data_gap", "source_unavailable") for item in selected)
        return _finish(selected=selected, outcomes=outcomes, decision_rule_ids=typed, snapshot=evidence_snapshot)
    except _SourceTechnical:
        outcomes = tuple(_Outcome(item, "technical_error", "source_query_error") for item in selected)
        return _finish(selected=selected, outcomes=outcomes, decision_rule_ids=typed, snapshot=evidence_snapshot)
    if not consultation_docs:
        outcomes = tuple(_Outcome(item, "not_applicable", "trigger_absent_complete") for item in selected)
        return _finish(selected=selected, outcomes=outcomes, decision_rule_ids=typed, snapshot=evidence_snapshot)
    if llm_client is None:
        outcomes = tuple(_Outcome(item, "evaluation_unknown", "semantic_output_unknown") for item in selected)
        return _finish(selected=selected, outcomes=outcomes, decision_rule_ids=typed, snapshot=evidence_snapshot)

    calls = prompt_tokens = completion_tokens = total_tokens = 0
    api_time = 0.0
    try:
        prompt = _stage1_prompt(consultation_docs)
        started = time.perf_counter()
        calls = 1
        response1 = await llm_client.generate(prompt)
        if not isinstance(response1, Mapping):
            raise _SemanticInvalid()
        elapsed = time.perf_counter() - started
        p, c, t, response_time = _usage(response1)
        prompt_tokens += p
        completion_tokens += c
        total_tokens += t
        api_time += response_time or elapsed
        episodes = _parse_stage1(
            _payload(response1),
            tuple(item["ref"] for item in consultation_docs),
        )
    except _SourceGap:
        outcomes = tuple(_Outcome(item, "data_gap", "source_truncated") for item in selected)
        return _finish(selected=selected, outcomes=outcomes, decision_rule_ids=typed, snapshot=evidence_snapshot)
    except _SemanticInvalid:
        outcomes = tuple(_Outcome(item, "evaluation_unknown", "semantic_output_unknown") for item in selected)
        return _finish(selected=selected, outcomes=outcomes, decision_rule_ids=typed, snapshot=evidence_snapshot, calls=1, prompt_tokens=prompt_tokens, completion_tokens=completion_tokens, total_tokens=total_tokens, api_time=api_time)
    except Exception:
        outcomes = tuple(_Outcome(item, "technical_error", "model_transport_error") for item in selected)
        return _finish(selected=selected, outcomes=outcomes, decision_rule_ids=typed, snapshot=evidence_snapshot, calls=1)

    outcomes: dict[str, _Outcome] = {}
    for rule_id in selected:
        if rule_id in {"LX0609-021", "LX0609-022"}:
            outcomes[rule_id] = _state_outcome(rule_id, episodes)
    if "LX0609-023" not in selected:
        return _finish(selected=selected, outcomes=tuple(outcomes.values()), decision_rule_ids=typed, snapshot=evidence_snapshot, calls=calls, prompt_tokens=prompt_tokens, completion_tokens=completion_tokens, total_tokens=total_tokens, api_time=api_time)

    stage1_unknown_for_023 = any(
        item.opinion_state == "unknown"
        or item.confidence < 0.8
        or (item.opinion_state == "clear" and not item.recommendations)
        for item in episodes
    )
    actionable = tuple(item for item in episodes if item.recommendations)
    if not actionable:
        outcomes["LX0609-023"] = _Outcome(
            "LX0609-023",
            "evaluation_unknown" if stage1_unknown_for_023 else "not_applicable",
            "semantic_output_unknown"
            if stage1_unknown_for_023
            else "trigger_absent_complete",
        )
        return _finish(selected=selected, outcomes=tuple(outcomes.values()), decision_rule_ids=typed, snapshot=evidence_snapshot, calls=calls, prompt_tokens=prompt_tokens, completion_tokens=completion_tokens, total_tokens=total_tokens, api_time=api_time)
    consultation_time_by_ref = {
        document["ref"]: _parse_time(document.get("time")) for document in consultation_docs
    }
    if any(consultation_time_by_ref[item.episode_ref] is None for item in actionable):
        outcomes["LX0609-023"] = _Outcome("LX0609-023", "data_gap", "required_field_missing")
        return _finish(selected=selected, outcomes=tuple(outcomes.values()), decision_rule_ids=typed, snapshot=evidence_snapshot, calls=calls, prompt_tokens=prompt_tokens, completion_tokens=completion_tokens, total_tokens=total_tokens, api_time=api_time)
    actionable_times = tuple(
        consultation_time_by_ref[item.episode_ref] for item in actionable
    )
    if _has_mixed_timezone(actionable_times):
        outcomes["LX0609-023"] = _Outcome("LX0609-023", "data_gap", "required_field_missing")
        return _finish(selected=selected, outcomes=tuple(outcomes.values()), decision_rule_ids=typed, snapshot=evidence_snapshot, calls=calls, prompt_tokens=prompt_tokens, completion_tokens=completion_tokens, total_tokens=total_tokens, api_time=api_time)
    stage2_rows: dict[str, list[dict[str, Any]]] = {}
    course_source_gap = False
    course_source_technical = False
    for source in _STAGE2_SOURCES:
        try:
            stage2_rows[source] = _read_source(
                source_key=source,
                institute_id=institute_id,
                patient_id=patient_id,
                visit_id=visit_id,
                source_schema=source_schema,
                evidence_materials=evidence_materials,
                evidence_snapshot=evidence_snapshot,
            )
        except _SourceGap:
            stage2_rows[source] = []
            if source in _COURSE_SOURCES:
                course_source_gap = True
        except _SourceTechnical:
            stage2_rows[source] = []
            if source in _COURSE_SOURCES:
                course_source_technical = True
    if course_source_technical:
        outcomes["LX0609-023"] = _Outcome("LX0609-023", "technical_error", "source_query_error")
        return _finish(selected=selected, outcomes=tuple(outcomes.values()), decision_rule_ids=typed, snapshot=evidence_snapshot, calls=calls, prompt_tokens=prompt_tokens, completion_tokens=completion_tokens, total_tokens=total_tokens, api_time=api_time)
    stage2_docs = tuple(
        document
        for source in _STAGE2_SOURCES
        for document in _documents(source, stage2_rows[source])
    )
    consultation_uses_timezone = actionable_times[0].utcoffset() is not None
    comparable_stage2_docs: list[dict[str, Any]] = []
    for document in stage2_docs:
        parsed = _parse_time(document.get("time"))
        source_key = document["ref"].split("-", 1)[0]
        if (
            parsed is not None
            and (parsed.utcoffset() is not None) != consultation_uses_timezone
        ):
            if source_key in _COURSE_SOURCES:
                outcomes["LX0609-023"] = _Outcome(
                    "LX0609-023", "data_gap", "required_field_missing"
                )
                return _finish(selected=selected, outcomes=tuple(outcomes.values()), decision_rule_ids=typed, snapshot=evidence_snapshot, calls=calls, prompt_tokens=prompt_tokens, completion_tokens=completion_tokens, total_tokens=total_tokens, api_time=api_time)
            continue
        comparable_stage2_docs.append(document)
    stage2_docs = tuple(comparable_stage2_docs)
    earliest = min(consultation_time_by_ref[item.episode_ref] for item in actionable)
    course_docs = tuple(
        document
        for document in stage2_docs
        if document["ref"].split("-", 1)[0] in _COURSE_SOURCES
    )
    post_docs = tuple(
        document
        for document in stage2_docs
        if _parse_time(document.get("time")) is not None
        and _parse_time(document.get("time")) >= earliest
    )
    course_refs = frozenset(
        document["ref"]
        for document in post_docs
        if document["ref"].split("-", 1)[0] in _COURSE_SOURCES
    )
    if not course_refs and (course_docs or course_source_gap):
        outcomes["LX0609-023"] = _Outcome("LX0609-023", "data_gap", "linkage_unresolved")
        return _finish(selected=selected, outcomes=tuple(outcomes.values()), decision_rule_ids=typed, snapshot=evidence_snapshot, calls=calls, prompt_tokens=prompt_tokens, completion_tokens=completion_tokens, total_tokens=total_tokens, api_time=api_time)
    if not course_refs:
        outcomes["LX0609-023"] = _Outcome("LX0609-023", "not_applicable", "trigger_absent_complete")
        return _finish(selected=selected, outcomes=tuple(outcomes.values()), decision_rule_ids=typed, snapshot=evidence_snapshot, calls=calls, prompt_tokens=prompt_tokens, completion_tokens=completion_tokens, total_tokens=total_tokens, api_time=api_time)
    try:
        allowed_refs_by_episode = {
            episode.episode_ref: frozenset(
                document["ref"]
                for document in post_docs
                if _parse_time(document.get("time")) is not None
                and _parse_time(document.get("time"))
                >= consultation_time_by_ref[episode.episode_ref]
            )
            for episode in actionable
        }
        prompt2 = _stage2_prompt(
            actionable,
            post_docs,
            consultation_time_by_ref,
            allowed_refs_by_episode,
        )
        started = time.perf_counter()
        calls += 1
        response2 = await llm_client.generate(prompt2)
        if not isinstance(response2, Mapping):
            raise _SemanticInvalid()
        elapsed = time.perf_counter() - started
        p, c, t, response_time = _usage(response2)
        prompt_tokens += p
        completion_tokens += c
        total_tokens += t
        api_time += response_time or elapsed
        execution_states = _parse_stage2(
            _payload(response2),
            actionable,
            frozenset(document["ref"] for document in post_docs),
            course_refs,
            allowed_refs_by_episode,
        )
    except _SourceGap:
        outcomes["LX0609-023"] = _Outcome("LX0609-023", "data_gap", "source_truncated")
    except _SemanticInvalid:
        outcomes["LX0609-023"] = _Outcome("LX0609-023", "evaluation_unknown", "semantic_output_unknown")
    except Exception:
        outcomes["LX0609-023"] = _Outcome("LX0609-023", "technical_error", "model_transport_error")
    else:
        qualities = tuple(item[0] for item in execution_states)
        matches = tuple(item[1] for item in execution_states)
        if "vague_or_copied" in qualities or "contradicted" in matches:
            outcomes["LX0609-023"] = _Outcome("LX0609-023", "non_compliant", "requirement_violated")
        elif "specific" in qualities and "absent" in qualities:
            outcomes["LX0609-023"] = _Outcome(
                "LX0609-023", "non_compliant", "requirement_violated"
            )
        elif stage1_unknown_for_023 or "unknown" in qualities:
            outcomes["LX0609-023"] = _Outcome("LX0609-023", "evaluation_unknown", "semantic_low_confidence")
        elif all(item == "absent" for item in qualities):
            outcomes["LX0609-023"] = _Outcome(
                "LX0609-023",
                "data_gap" if course_source_gap else "not_applicable",
                "source_truncated" if course_source_gap else "trigger_absent_complete",
            )
        elif "absent" in qualities:
            outcomes["LX0609-023"] = _Outcome(
                "LX0609-023", "non_compliant", "requirement_violated"
            )
        elif all(item == "specific" for item in qualities) and all(
            item == "supported" for item in matches
        ):
            outcomes["LX0609-023"] = _Outcome("LX0609-023", "compliant", "requirement_satisfied")
        else:
            outcomes["LX0609-023"] = _Outcome("LX0609-023", "evaluation_unknown", "semantic_output_unknown")
    return _finish(selected=selected, outcomes=tuple(outcomes.values()), decision_rule_ids=typed, snapshot=evidence_snapshot, calls=calls, prompt_tokens=prompt_tokens, completion_tokens=completion_tokens, total_tokens=total_tokens, api_time=api_time)
