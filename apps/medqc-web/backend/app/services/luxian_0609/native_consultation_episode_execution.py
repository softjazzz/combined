"""LX0609-021/022 会诊 episode 第一阶段原生执行器。

本模块只聚合本次住院会诊文书并判断申请目的、会诊意见的清晰度；
020/023 的执行关联属于第二阶段，刻意不在这里推断。
"""

from __future__ import annotations

from dataclasses import dataclass
import json
import time
from typing import Any, Mapping, Protocol, Sequence

from .decision_model import ApplicabilityState, EvidenceState, QcDirection, RuleDecision
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


CONSULTATION_EPISODE_RULE_IDS = ("LX0609-021", "LX0609-022")
EXECUTOR_KEY = "consultation_quality"
_SOURCE_KEY = "consultation_record"
_SOURCE_LIMIT = 48
_MAX_DOCUMENT_CHARS = 1600
_MAX_PROMPT_CHARS = 48000
_STATES = frozenset({"clear", "vague", "missing", "absent", "unknown"})
_CONFIDENCE = frozenset({"high", "medium", "low"})
_EVALUATOR_VERSION = "consultation-episode-v1"


class ConsultationEpisodeLLMClient(Protocol):
    async def generate(self, prompt: str) -> dict[str, Any]: ...


@dataclass(frozen=True)
class NativeConsultationEpisodeExecutionResult:
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
    member_refs: tuple[str, ...]
    application_state: str
    opinion_state: str
    confidence: str


class _SourceGap(Exception):
    pass


class _SourceTechnical(Exception):
    pass


class _SemanticInvalid(Exception):
    pass


def _clean(value: Any) -> str:
    return " ".join(str(value or "").split())


def _usage(response: Mapping[str, Any]) -> tuple[int, int, int, float]:
    usage = response.get("usage")
    usage = usage if isinstance(usage, Mapping) else {}
    prompt = int(usage.get("prompt_tokens") or usage.get("input_tokens") or 0)
    completion = int(usage.get("completion_tokens") or usage.get("output_tokens") or 0)
    total = int(usage.get("total_tokens") or prompt + completion)
    api_time = float(response.get("_api_time") or response.get("api_time") or response.get("latency") or 0.0)
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
    try:
        parsed = json.loads(raw.strip())
    except (TypeError, ValueError) as exc:
        raise _SemanticInvalid() from exc
    if not isinstance(parsed, Mapping):
        raise _SemanticInvalid()
    return parsed


def _read_rows(
    *,
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
                (item for item in evidence_snapshot.observations if item.source_key == _SOURCE_KEY),
                None,
            )
            if observation is None or observation.query_state.value == "unavailable":
                raise _SourceGap()
            if observation.query_state.value == "error":
                raise _SourceTechnical()
            if observation.completeness is SourceCompleteness.TRUNCATED:
                raise _SourceGap()
            rows = [dict(row) for row in evidence_materials.bounded_rows(_SOURCE_KEY)]
        else:
            rows = read_luxian_0609_native_source_rows(
                source_key=_SOURCE_KEY,
                institute_id=institute_id,
                patient_id=patient_id,
                visit_id=visit_id,
                source_schema=source_schema,
            )
    except (EvidenceMaterialTruncated, EvidenceMaterialUnavailable, SourceEvidenceUnavailable, SourceEvidenceTruncated):
        raise _SourceGap()
    except SourceEvidenceQueryError:
        raise _SourceTechnical()
    except (_SourceGap, _SourceTechnical):
        raise
    except Exception:
        raise _SourceTechnical()
    if len(rows) >= _SOURCE_LIMIT:
        raise _SourceGap()
    return [dict(row) for row in rows]


def _documents(rows: Sequence[Mapping[str, Any]]) -> tuple[dict[str, str], ...]:
    documents: list[dict[str, str]] = []
    for index, row in enumerate(rows, start=1):
        text = _clean("；".join(
            value for value in (_clean(row.get("document_title")), _clean(row.get("record_content"))) if value
        ))
        if len(text) > _MAX_DOCUMENT_CHARS:
            raise _SourceGap()
        documents.append({
            "ref": f"{_SOURCE_KEY}-{index}",
            "time": _clean(row.get("record_time")),
            "text": text,
        })
    return tuple(documents)


def _prompt(documents: Sequence[Mapping[str, str]]) -> str:
    payload = json.dumps({"consultation_documents": list(documents)}, ensure_ascii=False)
    if len(payload) > _MAX_PROMPT_CHARS:
        raise _SourceGap()
    return (
        "你只识别本次住院会诊文书中的真实会诊episode，不做任何质控结论。"
        "可把申请、会诊意见、重复同步或分行文书合并为同一episode；非目标文书放入non_target_refs，"
        "无法可靠归属的文书放入unresolved_refs。不得把每一行默认视为一次会诊。"
        "application_state和opinion_state只能是clear/vague/missing/absent/unknown："
        "clear为有明确目的或具体意见，vague为只有泛化措辞，missing为角色存在但内容空缺，"
        "absent为该角色不存在，unknown为材料无法可靠判断。confidence只能为high/medium/low。"
        "所有输入ref必须恰好归属一次：某个episode.member_refs、non_target_refs或unresolved_refs之一。"
        "episode_ref必须是member_refs之一。禁止创造、改写或遗漏ref。"
        "严格输出JSON对象：{episodes:[{episode_ref,member_refs,application_state,opinion_state,confidence}],"
        "non_target_refs:[],unresolved_refs:[]}。输入：" + payload
    )


def _parse(payload: Mapping[str, Any], expected_refs: tuple[str, ...]) -> tuple[_Episode, ...]:
    raw_episodes = payload.get("episodes")
    non_target = payload.get("non_target_refs")
    unresolved = payload.get("unresolved_refs")
    if not isinstance(raw_episodes, list) or not isinstance(non_target, list) or not isinstance(unresolved, list):
        raise _SemanticInvalid()
    expected = set(expected_refs)
    assigned: list[str] = []
    episodes: list[_Episode] = []
    for raw in raw_episodes:
        if not isinstance(raw, Mapping):
            raise _SemanticInvalid()
        episode_ref = _clean(raw.get("episode_ref"))
        member_refs = raw.get("member_refs")
        application = _clean(raw.get("application_state")).lower()
        opinion = _clean(raw.get("opinion_state")).lower()
        confidence = _clean(raw.get("confidence")).lower()
        if (
            not isinstance(member_refs, list)
            or not member_refs
            or not all(isinstance(ref, str) and ref in expected for ref in member_refs)
            or len(member_refs) != len(set(member_refs))
            or episode_ref not in member_refs
            or application not in _STATES
            or opinion not in _STATES
            or confidence not in _CONFIDENCE
        ):
            raise _SemanticInvalid()
        assigned.extend(member_refs)
        episodes.append(_Episode(episode_ref, tuple(member_refs), application, opinion, confidence))
    for group in (non_target, unresolved):
        if not all(isinstance(ref, str) and ref in expected for ref in group):
            raise _SemanticInvalid()
        assigned.extend(group)
    if len(assigned) != len(expected_refs) or len(set(assigned)) != len(expected_refs) or set(assigned) != expected:
        raise _SemanticInvalid()
    if unresolved:
        raise _SourceGap()
    return tuple(episodes)


def _outcome(rule_id: str, episodes: Sequence[_Episode]) -> tuple[str, str]:
    field = "application_state" if rule_id == "LX0609-021" else "opinion_state"
    states = tuple(getattr(episode, field) for episode in episodes)
    if any(state in {"vague", "missing"} for state in states):
        return "non_compliant", "requirement_violated"
    if any(episode.confidence != "high" for episode in episodes) or "unknown" in states:
        return "data_gap", "linkage_unresolved"
    applicable = tuple(state for state in states if state != "absent")
    if not applicable:
        return "not_applicable", "trigger_absent_complete"
    if all(state == "clear" for state in applicable):
        return "compliant", "requirement_satisfied"
    return "data_gap", "linkage_unresolved"


def _result(*, rule_id: str, status: str, reason_code: str, prompt_tokens: int, completion_tokens: int, total_tokens: int) -> dict[str, Any]:
    result = build_luxian_0609_native_result(
        rule_id=rule_id,
        final_state=status,
        finding_kind="consultation_episode",
        reason_code=reason_code,
    )
    result["metadata"].update({
        "executor_type": "llm_fact",
        "evaluator_version": _EVALUATOR_VERSION,
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "total_tokens": total_tokens,
    })
    return result


def _decision(*, rule_id: str, status: str, snapshot: Luxian0609EvidenceSnapshot) -> RuleDecision:
    refs = tuple(
        observation.snapshot_ref.removeprefix("sha256:")
        for observation in snapshot.observations
        if observation.source_key == _SOURCE_KEY
    )
    if status == "compliant":
        dimensions = (ApplicabilityState.APPLICABLE, EvidenceState.SUFFICIENT, QcDirection.SATISFIED, "requirement_satisfied")
    elif status == "non_compliant":
        dimensions = (ApplicabilityState.APPLICABLE, EvidenceState.SUFFICIENT, QcDirection.DEFECT, "requirement_violated")
    elif status == "not_applicable":
        dimensions = (ApplicabilityState.NOT_APPLICABLE, EvidenceState.SUFFICIENT, QcDirection.UNKNOWN, "trigger_absent_complete")
    elif status == "data_gap":
        dimensions = (ApplicabilityState.UNKNOWN, EvidenceState.DATA_GAP, QcDirection.UNKNOWN, "linkage_unresolved")
    else:
        dimensions = (ApplicabilityState.ERROR, EvidenceState.TECHNICAL_ERROR, QcDirection.UNKNOWN, "model_transport_error")
    applicability, evidence_state, direction, reason_code = dimensions
    return RuleDecision(
        rule_id=rule_id,
        snapshot_hash=snapshot.snapshot_hash,
        applicability=applicability,
        evidence_state=evidence_state,
        qc_direction=direction,
        reason_code=reason_code,
        fact_refs=refs,
        evaluator_version=_EVALUATOR_VERSION,
    )


def _finish(
    *, selected: tuple[str, ...], status: str, reason_code: str,
    calls: int = 0, prompt_tokens: int = 0, completion_tokens: int = 0,
    total_tokens: int = 0, api_time: float = 0.0,
    evidence_snapshot: Luxian0609EvidenceSnapshot | None = None,
    decision_rule_ids: frozenset[str] = frozenset(),
) -> NativeConsultationEpisodeExecutionResult:
    decisions = tuple(
        _decision(rule_id=rule_id, status=status, snapshot=evidence_snapshot)
        for rule_id in selected
        if rule_id in decision_rule_ids and evidence_snapshot is not None
    )
    return NativeConsultationEpisodeExecutionResult(
        results=tuple(_result(
            rule_id=rule_id, status=status, reason_code=reason_code,
            prompt_tokens=prompt_tokens, completion_tokens=completion_tokens, total_tokens=total_tokens,
        ) for rule_id in selected if rule_id not in decision_rule_ids),
        planned_rule_ids=selected,
        decisions=decisions,
        llm_call_count=calls,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        total_tokens=total_tokens,
        api_time=api_time,
    )


async def execute_luxian_0609_native_consultation_episode_rules(
    *, rule_ids: Sequence[str], institute_id: str, patient_id: str, visit_id: str,
    source_schema: str | None, llm_client: ConsultationEpisodeLLMClient | None,
    evidence_materials: Luxian0609EvidenceMaterialStore | None = None,
    evidence_snapshot: Luxian0609EvidenceSnapshot | None = None,
    decision_rule_ids: Sequence[str] = (),
) -> NativeConsultationEpisodeExecutionResult:
    requested = {str(item or "").strip().upper() for item in rule_ids}
    selected = tuple(rule_id for rule_id in CONSULTATION_EPISODE_RULE_IDS if rule_id in requested)
    typed = frozenset(str(rule_id or "").strip().upper() for rule_id in decision_rule_ids)
    if not typed.issubset(set(selected)):
        raise ValueError("unsupported typed consultation episode scope")
    if not selected:
        return NativeConsultationEpisodeExecutionResult((), ())
    if not all(isinstance(value, str) and value.strip() for value in (institute_id, patient_id, visit_id)):
        return _finish(selected=selected, status="technical_error", reason_code="source_query_error", evidence_snapshot=evidence_snapshot, decision_rule_ids=typed)
    try:
        documents = _documents(_read_rows(
            institute_id=institute_id, patient_id=patient_id, visit_id=visit_id,
            source_schema=source_schema, evidence_materials=evidence_materials,
            evidence_snapshot=evidence_snapshot,
        ))
    except _SourceGap:
        return _finish(selected=selected, status="data_gap", reason_code="source_unavailable", evidence_snapshot=evidence_snapshot, decision_rule_ids=typed)
    except _SourceTechnical:
        return _finish(selected=selected, status="technical_error", reason_code="source_query_error", evidence_snapshot=evidence_snapshot, decision_rule_ids=typed)
    if not documents:
        return _finish(selected=selected, status="not_applicable", reason_code="trigger_absent_complete", evidence_snapshot=evidence_snapshot, decision_rule_ids=typed)
    if llm_client is None:
        return _finish(selected=selected, status="data_gap", reason_code="linkage_unresolved", evidence_snapshot=evidence_snapshot, decision_rule_ids=typed)
    calls = 1
    prompt_tokens = completion_tokens = total_tokens = 0
    api_time = 0.0
    try:
        started = time.perf_counter()
        response = await llm_client.generate(_prompt(documents))
        if not isinstance(response, Mapping):
            raise _SemanticInvalid()
        prompt_tokens, completion_tokens, total_tokens, response_time = _usage(response)
        api_time = response_time or (time.perf_counter() - started)
        episodes = _parse(_payload(response), tuple(item["ref"] for item in documents))
    except _SourceGap:
        return _finish(selected=selected, status="data_gap", reason_code="linkage_unresolved", calls=calls, prompt_tokens=prompt_tokens, completion_tokens=completion_tokens, total_tokens=total_tokens, api_time=api_time, evidence_snapshot=evidence_snapshot, decision_rule_ids=typed)
    except _SemanticInvalid:
        return _finish(selected=selected, status="data_gap", reason_code="linkage_unresolved", calls=calls, prompt_tokens=prompt_tokens, completion_tokens=completion_tokens, total_tokens=total_tokens, api_time=api_time, evidence_snapshot=evidence_snapshot, decision_rule_ids=typed)
    except Exception:
        return _finish(selected=selected, status="technical_error", reason_code="model_transport_error", calls=calls, evidence_snapshot=evidence_snapshot, decision_rule_ids=typed)
    results = []
    for rule_id in selected:
        status, reason = _outcome(rule_id, episodes)
        results.append(_result(rule_id=rule_id, status=status, reason_code=reason, prompt_tokens=prompt_tokens, completion_tokens=completion_tokens, total_tokens=total_tokens))
    decisions = tuple(
        _decision(rule_id=rule_id, status=_outcome(rule_id, episodes)[0], snapshot=evidence_snapshot)
        for rule_id in selected
        if rule_id in typed and evidence_snapshot is not None
    )
    return NativeConsultationEpisodeExecutionResult(
        results=tuple(item for item in results if item["rule_id"] not in typed), planned_rule_ids=selected,
        decisions=decisions, llm_call_count=calls,
        prompt_tokens=prompt_tokens, completion_tokens=completion_tokens,
        total_tokens=total_tokens, api_time=api_time,
    )
