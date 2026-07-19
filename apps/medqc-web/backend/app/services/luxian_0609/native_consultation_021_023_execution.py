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
_EXECUTION_STATES = frozenset({"clear", "vague", "missing", "absent", "unknown"})
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
_RECOVERY_ACTIONABILITY = frozenset({"present", "absent", "unknown"})
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
    application_ref: str | None
    opinion_state: str
    opinion_ref: str | None
    execution_state: str
    execution_ref: str | None
    recommendations: tuple[tuple[str, str, str], ...]
    confidence: float
    recommendation_contract_invalid: bool = False


@dataclass(frozen=True)
class _Outcome:
    rule_id: str
    status: str
    reason_code: str


@dataclass(frozen=True)
class _RecoveryAssessment:
    actionability: str
    confidence: float
    execution_states: tuple[tuple[str, str], ...]


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
        "application_state、opinion_state和execution_state只能为clear/vague/missing/absent/unknown。"
        "absent表示对应角色在该文书中不存在；missing表示角色存在但内容空缺；"
        "vague表示只有泛化措辞；clear表示有明确临床目的或具体意见。"
        "每个角色同时输出对应的application_ref、opinion_ref或execution_ref："
            "clear/vague/missing必须填写当前episode_ref；absent/unknown必须为null。"
        "角色识别必须先分段再判状态：申请角色只能依据独立的申请、请求或会诊目的段；"
        "意见角色只能依据受邀专科的意见、评估或处置段；不得把一个角色段的事实补到另一个角色。"
        "没有独立申请、请求或会诊目的段时，application_state=absent；即使意见段有丰富病情、"
        "诊断或治疗内容也不得反推申请。申请段存在但内容空缺为missing；申请段任意位置有本次住院的"
        "具体症状、诊断、检查异常、风险、治疗问题、待解决会诊问题或具体处置请求时为clear；"
        "段尾“协助诊治”“协助治疗”“请会诊”等泛化词不得把前述具体问题降为vague。"
        "拟、计划、考虑或需要进行某项具体治疗、检查、手术或处置，因而请求对应专科会诊时必须为clear。"
        "只有申请段存在且全文仅有泛化请求、没有任何具体当前问题时才为vague。"
        "意见判定不依赖“会诊意见”标题。具名专科医师的病史判断、专科评估、诊断、手术指征、"
        "治疗建议、用药、检查、处置计划、治法或方选均为opinion_state=clear。"
        "意见角色不存在为absent，存在但内容空缺为missing，仅有泛化原则且无具体意见为vague；"
        "不得用申请段、标题或签名补足意见。"
        "execution_state只依据明确的执行回填；不得由申请或意见本身推定执行。"
        "normalized_recommendations仅从会诊意见提取，元素字段只能为"
        "type(medication/examination/laboratory/surgery/treatment/monitoring/follow_up/other)、"
            "item（不超过80字的归一化事项）。normalized_recommendations只能从clear意见中提取明确可执行安排；"
        "每个独立行动必须逐项输出，一条长句含多个行动时按原文语义拆为多个保真原子事项。"
        "每个item不超过80字，保留原文支持的行动，不得因单项较长遗漏其他已明确事项，也不得添加原文没有的行动。"
        "会诊意见中的明确可执行行动不得因同文书出现“已执行”“已处理”“已遵嘱”或其他执行语义而删除、"
        "降为absent；必须先抽取行动，执行语义只交后续关联核对。"
        "没有明确可执行事项时输出空列表；opinion_state为missing、absent或unknown时不得输出建议。"
        "不得由Python猜测或补全动作，也不得引用输入外信息。"
        "单输入时系统会绑定内部引用，不能因ID形态影响角色语义；多输入时episode_ref与input_refs必须逐字复用输入提供的内部引用，不得自造、改写或省略。"
        "严格输出JSON对象{episodes:[{episode_ref,application_state,application_ref,opinion_state,"
        "opinion_ref,execution_state,execution_ref,normalized_recommendations,confidence,input_refs}]}。输入：" + payload
    )


def _invalid_episode(episode_ref: str) -> _Episode:
    return _Episode(
        episode_ref,
        "unknown",
        None,
        "unknown",
        None,
        "unknown",
        None,
        (),
        0.0,
    )


def _validate_role_ref(*, state: str, ref: Any, episode_ref: str) -> str | None:
    if state in {"clear", "vague"}:
        if ref != episode_ref:
            raise _SemanticInvalid()
        return episode_ref
    if state == "missing":
        if ref is None or ref == episode_ref:
            return episode_ref
        raise _SemanticInvalid()
    if state in {"absent", "unknown"} and ref is None:
        return None
    raise _SemanticInvalid()


def _bind_single_episode_refs(
    *, raw: Mapping[str, Any], expected_refs: tuple[str, ...]
) -> Mapping[str, Any]:
    """唯一输入文书时由受信任边界绑定内部引用，LLM只负责语义状态。"""
    if len(expected_refs) != 1:
        return raw
    canonical = expected_refs[0]
    normalized = dict(raw)
    normalized["episode_ref"] = canonical
    normalized["input_refs"] = [canonical]
    for state_key, ref_key in (
        ("application_state", "application_ref"),
        ("opinion_state", "opinion_ref"),
        ("execution_state", "execution_ref"),
    ):
        state = _clean(normalized.get(state_key)).lower()
        normalized[ref_key] = (
            canonical if state in {"clear", "vague", "missing"} else None
        )
    return normalized


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
        if len(raw_episodes) == 1:
            raw = _bind_single_episode_refs(
                raw=raw,
                expected_refs=expected_refs,
            )
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
            if not {
                "application_ref",
                "opinion_ref",
                "execution_state",
                "execution_ref",
            }.issubset(raw):
                raise _SemanticInvalid()
            application = _clean(raw.get("application_state")).lower()
            opinion = _clean(raw.get("opinion_state")).lower()
            execution = _clean(raw.get("execution_state")).lower()
            if (
                application not in _APPLICATION_STATES
                or opinion not in _OPINION_STATES
                or execution not in _EXECUTION_STATES
            ):
                raise _SemanticInvalid()
            application_ref = _validate_role_ref(
                state=application,
                ref=raw.get("application_ref"),
                episode_ref=episode_ref,
            )
            opinion_ref = _validate_role_ref(
                state=opinion,
                ref=raw.get("opinion_ref"),
                episode_ref=episode_ref,
            )
            execution_ref = _validate_role_ref(
                state=execution,
                ref=raw.get("execution_ref"),
                episode_ref=episode_ref,
            )
            confidence = _confidence(raw.get("confidence"))
            recommendations_raw = raw.get("normalized_recommendations")
            recommendation_contract_invalid = not isinstance(recommendations_raw, list)
            if recommendation_contract_invalid:
                recommendations_raw = []
            recommendations: list[tuple[str, str, str]] = []
            local_facts: set[tuple[str, str]] = set()
            for item in recommendations_raw:
                if not isinstance(item, Mapping):
                    recommendation_contract_invalid = True
                    continue
                kind = _clean(item.get("type")).lower()
                normalized = _clean(item.get("item"))
                if (
                    kind not in _RECOMMENDATION_TYPES
                    or not normalized
                    or len(normalized) > 80
                ):
                    recommendation_contract_invalid = True
                    continue
                fact_key = (kind, normalized)
                if fact_key in local_facts:
                    continue
                local_facts.add(fact_key)
                ref = f"{episode_ref}-recommendation-{len(recommendations) + 1}"
                recommendations.append((ref, kind, normalized))
            if opinion != "clear" and recommendations:
                recommendation_contract_invalid = True
                recommendations = []
        except _SemanticInvalid:
            episodes.append(_invalid_episode(episode_ref))
            continue
        episodes.append(
            _Episode(
                episode_ref,
                application,
                application_ref,
                opinion,
                opinion_ref,
                execution,
                execution_ref,
                tuple(recommendations),
                confidence,
                recommendation_contract_invalid,
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
        "当已存在明确会诊建议，后续材料仅有“经治疗”“治疗后好转”“继续原治疗”“巩固治疗”“遵意见”等泛化续治表述，"
        "未点名且不能依上下文唯一关联到某条具体建议时，必须输出execution_record_quality=vague_or_copied、"
        "implementation_match=unknown、association_state=none或ambiguous；不得笼统输出unknown。"
        "unknown仅用于确实文本不可判定、材料截断或输入冲突。"
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
        generic_unlinked_continuation = (
            quality == "vague_or_copied"
            and match == "unknown"
            and association in {"none", "ambiguous"}
            and not safe_refs
            and confidence is not None
            and confidence >= 0.8
        )
        if item_invalid:
            states.append(("unknown", "semantic_output_unknown"))
        elif (
            (association_is_ambiguous and not generic_unlinked_continuation)
            or (linked_quality_without_link and not generic_unlinked_continuation)
            or linked_without_refs
            or ref_reused_across_episodes
            or invalid_absent_shape
        ):
            states.append(("unknown", "semantic_low_confidence"))
        elif generic_unlinked_continuation:
            states.append(("vague_or_copied", "unknown"))
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


def _stage2_recovery_prompt(
    episodes: Sequence[_Episode],
    recovery_episode_refs: frozenset[str],
    consultation_documents_by_ref: Mapping[str, Mapping[str, Any]],
    course_documents: Sequence[Mapping[str, Any]],
    consultation_time_by_ref: Mapping[str, datetime],
    allowed_refs_by_episode: Mapping[str, frozenset[str]],
) -> str:
    """第二阶段兼顾既有建议执行核对与第一阶段漏提建议的受控恢复。

    这一分支只投放会诊原文及会诊后的两类病程文书，禁止把医嘱、检查或手术
    当作执行事实或建议来源。
    """

    facts = []
    for episode in episodes:
        document = consultation_documents_by_ref[episode.episode_ref]
        facts.append(
            {
                "episode_ref": episode.episode_ref,
                "consultation_time": consultation_time_by_ref[
                    episode.episode_ref
                ].isoformat(sep=" "),
                "consultation_document": document,
                "recovery_required": episode.episode_ref in recovery_episode_refs,
                "known_recommendations": [
                    {"type": kind, "item": item}
                    for _ref, kind, item in episode.recommendations
                ],
                "allowed_evidence_refs": sorted(
                    allowed_refs_by_episode[episode.episode_ref]
                ),
            }
        )
    payload = json.dumps(
        {
            "consultation_facts": facts,
            "post_consultation_course_evidence": list(course_documents),
        },
        ensure_ascii=False,
    )
    if len(payload) > _MAX_STAGE2_CHARS:
        raise _SourceGap()
    return (
        "你只做会诊建议与会诊后病程执行事实抽取，不做质控结论。每个episode必须输出一次。"
        "recovery_required=true时，上游已确认该会诊存在明确专科意见；先只审会诊文书，"
        "逐项保留明确可执行行动，不得遗漏、杜撰或由Python补全。治疗、检查、手术或处置安排"
        "即使同文书有“已执行”“已处理”“已遵嘱”或其他执行语义，也不得判absent或删除。"
        "会诊文书自身的“已执行”“已处理”“已遵嘱”措辞绝不可作为后续执行证据。"
        "recovery_required=false时，known_recommendations是已确认建议，必须逐字逐项复用，"
        "不得增加、删除或改写。每个建议都要给出执行核对。"
        "recommendations元素字段只能为type(medication/examination/laboratory/surgery/treatment/monitoring/follow_up/other)、"
        "item（不超过80字）、execution_record_quality(specific/vague_or_copied/absent/unknown)、"
        "implementation_match(supported/contradicted/unknown)、"
        "association_state(explicit/contextual/ambiguous/none/unknown)、evidence_refs、confidence。"
        "再只用会诊后的daily_course_record或senior_course_record核对执行；必须只引用当前episode的"
        "allowed_evidence_refs中会诊后病程。没有合法执行证据时必须输出"
        "execution_record_quality=absent、implementation_match=unknown、association_state=none、evidence_refs=[]。"
        "actionability只能为present/absent/unknown：present表示会诊意见有明确可执行安排，"
        "actionability=absent只在意见确无明确行动时，unknown表示无法稳定判断；"
        "actionability=absent或unknown时recommendations必须为空列表。"
        "时间先后只能排除不可能证据，不能仅因会诊后出现就推定执行；无法唯一归属必须unknown或ambiguous。"
        "当已存在明确会诊建议，后续材料仅有“经治疗”“治疗后好转”“继续原治疗”“巩固治疗”“遵意见”等泛化续治表述，"
        "未点名且不能依上下文唯一关联到某条具体建议时，必须输出execution_record_quality=vague_or_copied、"
        "implementation_match=unknown、association_state=none或ambiguous；不得笼统输出unknown。"
        "unknown仅用于确实文本不可判定、材料截断或输入冲突。"
        "严格输出JSON对象{episodes:[{episode_ref,actionability,recommendations,confidence}]}。输入："
        + payload
    )


def _recovery_execution_state(
    *,
    raw: Mapping[str, Any],
    allowed_refs: frozenset[str],
) -> tuple[str, str]:
    quality = _clean(raw.get("execution_record_quality")).lower()
    match = _clean(raw.get("implementation_match")).lower()
    association = _clean(raw.get("association_state")).lower()
    refs = raw.get("evidence_refs")
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
    if (
        quality not in _EXECUTION_QUALITIES
        or match not in _IMPLEMENTATION_MATCHES
        or association not in _ASSOCIATION_STATES
        or confidence is None
        or not refs_are_valid
        or any(ref not in allowed_refs for ref in safe_refs)
    ):
        return "unknown", "semantic_output_unknown"
    if quality == "absent":
        if match == "unknown" and association == "none" and not safe_refs:
            return "absent", "unknown"
        return "unknown", "semantic_low_confidence"
    if (
        quality == "vague_or_copied"
        and match == "unknown"
        and association in {"none", "ambiguous"}
        and not safe_refs
        and confidence >= 0.8
    ):
        return "vague_or_copied", "unknown"
    if (
        confidence < 0.8
        or quality == "unknown"
        or association not in _LINKED_ASSOCIATION_STATES
        or not safe_refs
        or (match == "unknown" and quality != "vague_or_copied")
    ):
        return "unknown", "semantic_low_confidence"
    return quality, match


def _parse_stage2_recovery(
    payload: Mapping[str, Any],
    episodes: Sequence[_Episode],
    recovery_episode_refs: frozenset[str],
    allowed_refs_by_episode: Mapping[str, frozenset[str]],
) -> tuple[_RecoveryAssessment, ...]:
    """严格解析恢复输出；任何模型结构越界只产生未知，不生成临床建议。"""

    by_ref = {episode.episode_ref: episode for episode in episodes}
    raw_episodes = payload.get("episodes")
    if not isinstance(raw_episodes, list) or len(raw_episodes) != len(by_ref):
        raise _SemanticInvalid()
    seen: set[str] = set()
    assessments: list[_RecoveryAssessment] = []
    for raw in raw_episodes:
        if not isinstance(raw, Mapping):
            raise _SemanticInvalid()
        episode_ref = _clean(raw.get("episode_ref"))
        episode = by_ref.get(episode_ref)
        if episode is None or episode_ref in seen:
            raise _SemanticInvalid()
        seen.add(episode_ref)
        actionability = _clean(raw.get("actionability")).lower()
        recommendations = raw.get("recommendations")
        try:
            confidence = _confidence(raw.get("confidence"))
        except _SemanticInvalid:
            raise _SemanticInvalid()
        if actionability not in _RECOVERY_ACTIONABILITY or not isinstance(
            recommendations, list
        ):
            raise _SemanticInvalid()
        if episode_ref not in recovery_episode_refs and actionability != "present":
            # 已由第一阶段确认的建议不能被第二阶段改写为“无行动”或未知。
            raise _SemanticInvalid()
        if actionability in {"absent", "unknown"}:
            if recommendations:
                raise _SemanticInvalid()
            assessments.append(_RecoveryAssessment(actionability, confidence, ()))
            continue
        if not recommendations:
            raise _SemanticInvalid()
        expected_known = {
            (kind, item) for _ref, kind, item in episode.recommendations
        }
        parsed_items: set[tuple[str, str]] = set()
        states: list[tuple[str, str]] = []
        invalid = False
        for item in recommendations:
            if not isinstance(item, Mapping):
                raise _SemanticInvalid()
            kind = _clean(item.get("type")).lower()
            normalized = _clean(item.get("item"))
            key = (kind, normalized)
            if (
                kind not in _RECOMMENDATION_TYPES
                or not normalized
                or len(normalized) > 80
                or key in parsed_items
            ):
                raise _SemanticInvalid()
            parsed_items.add(key)
            states.append(
                _recovery_execution_state(
                    raw=item,
                    allowed_refs=allowed_refs_by_episode[episode_ref],
                )
            )
        if invalid or not parsed_items or (
            episode_ref not in recovery_episode_refs
            and parsed_items != expected_known
        ):
            raise _SemanticInvalid()
        assessments.append(
            _RecoveryAssessment("present", confidence, tuple(states))
        )
    if seen != set(by_ref):
        raise _SemanticInvalid()
    return tuple(assessments)


def _recovery_outcome(
    assessments: Sequence[_RecoveryAssessment],
) -> _Outcome:
    if any(item.actionability == "unknown" or item.confidence < 0.8 for item in assessments):
        return _Outcome("LX0609-023", "data_gap", "semantic_low_confidence")
    present = tuple(item for item in assessments if item.actionability == "present")
    if not present:
        return _Outcome("LX0609-023", "not_applicable", "trigger_absent_complete")
    states = tuple(state for item in present for state in item.execution_states)
    qualities = tuple(item[0] for item in states)
    matches = tuple(item[1] for item in states)
    if "semantic_output_unknown" in matches:
        return _Outcome("LX0609-023", "evaluation_unknown", "semantic_output_unknown")
    if "vague_or_copied" in qualities or "contradicted" in matches or "absent" in qualities:
        return _Outcome("LX0609-023", "non_compliant", "requirement_violated")
    if "unknown" in qualities or "semantic_low_confidence" in matches:
        return _Outcome("LX0609-023", "data_gap", "semantic_low_confidence")
    if all(quality == "specific" for quality in qualities) and all(
        match == "supported" for match in matches
    ):
        return _Outcome("LX0609-023", "compliant", "requirement_satisfied")
    return _Outcome("LX0609-023", "evaluation_unknown", "semantic_output_unknown")


async def _recover_023_recommendations(
    *,
    episodes: Sequence[_Episode],
    recovery_episode_refs: frozenset[str],
    consultation_documents: Sequence[Mapping[str, Any]],
    institute_id: str,
    patient_id: str,
    visit_id: str,
    source_schema: str | None,
    llm_client: ConsultationLLMClient,
    evidence_materials: Luxian0609EvidenceMaterialStore | None,
    evidence_snapshot: Luxian0609EvidenceSnapshot | None,
) -> tuple[_Outcome, int, int, int, int, float]:
    """用一次受控 LLM 补抽建议并核对执行；不读取非病程来源。"""

    consultation_documents_by_ref = {
        _clean(document.get("ref")): document for document in consultation_documents
    }
    consultation_time_by_ref = {
        episode.episode_ref: _parse_time(
            consultation_documents_by_ref[episode.episode_ref].get("time")
        )
        for episode in episodes
    }
    if (
        any(value is None for value in consultation_time_by_ref.values())
        or _has_mixed_timezone(
            tuple(value for value in consultation_time_by_ref.values() if value is not None)
        )
    ):
        return _Outcome("LX0609-023", "data_gap", "required_field_missing"), 0, 0, 0, 0, 0.0
    course_rows: dict[str, list[dict[str, Any]]] = {}
    try:
        for source_key in _COURSE_SOURCES:
            course_rows[source_key] = _read_source(
                source_key=source_key,
                institute_id=institute_id,
                patient_id=patient_id,
                visit_id=visit_id,
                source_schema=source_schema,
                evidence_materials=evidence_materials,
                evidence_snapshot=evidence_snapshot,
            )
        course_documents = tuple(
            document
            for source_key in _COURSE_SOURCES
            for document in _documents(source_key, course_rows[source_key])
        )
    except _SourceGap:
        return _Outcome("LX0609-023", "data_gap", "source_truncated"), 0, 0, 0, 0, 0.0
    except _SourceTechnical:
        return _Outcome("LX0609-023", "technical_error", "source_query_error"), 0, 0, 0, 0, 0.0
    course_times = tuple(_parse_time(document.get("time")) for document in course_documents)
    if any(value is None for value in course_times):
        return _Outcome("LX0609-023", "data_gap", "required_field_missing"), 0, 0, 0, 0, 0.0
    consultation_uses_timezone = next(iter(consultation_time_by_ref.values())).utcoffset() is not None
    if any(
        (value.utcoffset() is not None) != consultation_uses_timezone
        for value in course_times
        if value is not None
    ):
        return _Outcome("LX0609-023", "data_gap", "required_field_missing"), 0, 0, 0, 0, 0.0
    earliest = min(value for value in consultation_time_by_ref.values() if value is not None)
    post_course_documents = tuple(
        document
        for document in course_documents
        if _parse_time(document.get("time")) >= earliest
    )
    allowed_refs_by_episode = {
        episode.episode_ref: frozenset(
            document["ref"]
            for document in post_course_documents
            if _parse_time(document.get("time"))
            >= consultation_time_by_ref[episode.episode_ref]
        )
        for episode in episodes
    }
    prompt_tokens = completion_tokens = total_tokens = 0
    api_time = 0.0
    try:
        prompt = _stage2_recovery_prompt(
            episodes,
            recovery_episode_refs,
            consultation_documents_by_ref,
            post_course_documents,
            {
                key: value
                for key, value in consultation_time_by_ref.items()
                if value is not None
            },
            allowed_refs_by_episode,
        )
        started = time.perf_counter()
        response = await llm_client.generate(prompt)
        if not isinstance(response, Mapping):
            raise _SemanticInvalid()
        elapsed = time.perf_counter() - started
        prompt_tokens, completion_tokens, total_tokens, response_time = _usage(response)
        api_time = response_time or elapsed
        assessments = _parse_stage2_recovery(
            _payload(response),
            episodes,
            recovery_episode_refs,
            allowed_refs_by_episode,
        )
    except _SourceGap:
        return _Outcome("LX0609-023", "data_gap", "source_truncated"), 0, 0, 0, 0, 0.0
    except _SemanticInvalid:
        return (
            _Outcome("LX0609-023", "evaluation_unknown", "semantic_output_unknown"),
            1,
            prompt_tokens,
            completion_tokens,
            total_tokens,
            api_time,
        )
    except Exception:
        return _Outcome("LX0609-023", "technical_error", "model_transport_error"), 1, 0, 0, 0, 0.0
    return (
        _recovery_outcome(assessments),
        1,
        prompt_tokens,
        completion_tokens,
        total_tokens,
        api_time,
    )


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

    recommendation_contract_invalid = any(
        item.recommendation_contract_invalid for item in episodes
    )
    recoverable_episode_refs = frozenset(
        item.episode_ref
        for item in episodes
        if (
            item.opinion_state == "clear"
            and not item.recommendations
            and not item.recommendation_contract_invalid
        )
    )
    stage1_unknown_for_023 = any(
        item.opinion_state == "unknown"
        or item.confidence < 0.8
        or (
            item.opinion_state == "clear"
            and not item.recommendations
            and item.episode_ref not in recoverable_episode_refs
        )
        for item in episodes
    )
    actionable = tuple(item for item in episodes if item.recommendations)
    if recommendation_contract_invalid and not actionable:
        outcomes["LX0609-023"] = _Outcome(
            "LX0609-023",
            "data_gap",
            "recommendation_contract_invalid",
        )
        return _finish(
            selected=selected,
            outcomes=tuple(outcomes.values()),
            decision_rule_ids=typed,
            snapshot=evidence_snapshot,
            calls=calls,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
            api_time=api_time,
        )
    if recoverable_episode_refs and not recommendation_contract_invalid:
        recovery_scope = tuple(
            item
            for item in episodes
            if item.recommendations or item.episode_ref in recoverable_episode_refs
        )
        (
            recovery_outcome,
            recovery_calls,
            recovery_prompt_tokens,
            recovery_completion_tokens,
            recovery_total_tokens,
            recovery_api_time,
        ) = await _recover_023_recommendations(
            episodes=recovery_scope,
            recovery_episode_refs=recoverable_episode_refs,
            consultation_documents=consultation_docs,
            institute_id=institute_id,
            patient_id=patient_id,
            visit_id=visit_id,
            source_schema=source_schema,
            llm_client=llm_client,
            evidence_materials=evidence_materials,
            evidence_snapshot=evidence_snapshot,
        )
        outcomes["LX0609-023"] = recovery_outcome
        return _finish(
            selected=selected,
            outcomes=tuple(outcomes.values()),
            decision_rule_ids=typed,
            snapshot=evidence_snapshot,
            calls=calls + recovery_calls,
            prompt_tokens=prompt_tokens + recovery_prompt_tokens,
            completion_tokens=completion_tokens + recovery_completion_tokens,
            total_tokens=total_tokens + recovery_total_tokens,
            api_time=api_time + recovery_api_time,
        )
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
    try:
        stage2_docs = tuple(
            document
            for source in _STAGE2_SOURCES
            for document in _documents(source, stage2_rows[source])
        )
    except _SourceGap:
        # 第一阶段的021/022已经得到受控结论；仅023依赖这批后续材料。
        outcomes["LX0609-023"] = _Outcome(
            "LX0609-023", "data_gap", "source_truncated"
        )
        return _finish(
            selected=selected,
            outcomes=tuple(outcomes.values()),
            decision_rule_ids=typed,
            snapshot=evidence_snapshot,
            calls=calls,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
            api_time=api_time,
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
    if not course_refs:
        outcomes["LX0609-023"] = _Outcome(
            "LX0609-023",
            "data_gap" if course_source_gap else "non_compliant",
            "source_truncated" if course_source_gap else "requirement_violated",
        )
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
        elif recommendation_contract_invalid:
            outcomes["LX0609-023"] = _Outcome(
                "LX0609-023",
                "data_gap",
                "recommendation_contract_invalid",
            )
        elif "semantic_output_unknown" in matches:
            outcomes["LX0609-023"] = _Outcome(
                "LX0609-023",
                "evaluation_unknown",
                "semantic_output_unknown",
            )
        elif stage1_unknown_for_023 or "unknown" in qualities:
            outcomes["LX0609-023"] = _Outcome(
                "LX0609-023",
                "data_gap",
                "semantic_low_confidence",
            )
        elif all(item == "absent" for item in qualities):
            outcomes["LX0609-023"] = _Outcome(
                "LX0609-023",
                "data_gap" if course_source_gap else "non_compliant",
                "source_truncated" if course_source_gap else "requirement_violated",
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
