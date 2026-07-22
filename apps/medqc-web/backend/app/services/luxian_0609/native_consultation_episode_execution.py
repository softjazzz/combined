"""LX0609-020 至 023 的两阶段会诊 episode 原生执行器。

第一阶段只聚合本次住院的真实会诊 episode；第二阶段仅对高置信、
意见明确的 episode 批量判断后续执行关联，禁止行级唯一归属推断。
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
import json
import re
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


CONSULTATION_EPISODE_RULE_IDS = (
    "LX0609-020",
    "LX0609-021",
    "LX0609-022",
    "LX0609-023",
)
# 020/023 都依赖第二阶段的“会诊意见—后续执行”语义关联，尚未达到包级
# 原生派发验收门槛；第一阶段客户包只允许 021/022 进入原生会诊批次。
PACKAGE_NATIVE_CONSULTATION_RULE_IDS = (
    "LX0609-021",
    "LX0609-022",
)
EXECUTOR_KEY = "consultation_quality"
_SOURCE_KEY = "consultation_record"
_SOURCE_LIMIT = 48
_MAX_DOCUMENT_CHARS = 1600
_MAX_PROMPT_CHARS = 48000
_MAX_EPISODES = 12
_MAX_EPISODE_OPINION_CHARS = 1200
_MAX_RECOMMENDATIONS = 24
_MAX_RECOMMENDATION_CHARS = 240
_MAX_CANDIDATES_PER_SOURCE = 12
_MAX_CANDIDATE_CHARS = 1000
_EXECUTION_SOURCE_KEYS = (
    "daily_course_record",
    "senior_course_record",
    "inpat_drug_order",
    "exam_item_report",
    "labtest_item_report",
    "surgery_record",
)
_STAY_ADMISSION_SOURCE_KEY = "inpat_registration"
_STAY_DISCHARGE_SOURCE_KEY = "inpat_registration.discharge_horizon"
_STAY_HORIZON_SOURCE_KEY = "evaluation_context.horizon"
_STATES = frozenset({"clear", "vague", "missing", "absent", "unknown"})
_CONFIDENCE = frozenset({"high", "medium", "low"})
_EXECUTION_STATES = frozenset({"linked_specific", "linked_vague", "absent", "unknown"})
_RECOMMENDATION_TYPES = frozenset({"medication", "test", "procedure", "transfer", "monitoring", "other"})
_EVALUATOR_VERSION = "consultation-episode-v2"
_SIGNATURE_LABEL = (
    r"(?:(?:患者|家属|会诊(?:医师|医生)?|申请(?:医师|医生)?|"
    r"记录(?:医师|医生)?|上级医师|医师|医生)?(?:电子)?签(?:名|字))"
)
_SIGNATURE_VALUE = r"(?:已(?:签|签名|签字)|[A-Za-z]{1,4}|[\u4e00-\u9fff·]{1,4}|\*{1,4})?"
_PURE_SIGNATURE_TEMPLATE = re.compile(
    rf"^[\s，,;；、|/\\\\()（）\[\]【】]*"
    rf"(?:{_SIGNATURE_LABEL}\s*[:：]?\s*{_SIGNATURE_VALUE}"
    rf"\s*[\s，,;；、|/\\\\()（）\[\]【】]*)+$"
)


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
    application_refs: tuple[str, ...]
    opinion_refs: tuple[str, ...]
    application_state: str
    opinion_state: str
    confidence: str
    recommendations: tuple["_Recommendation", ...]


@dataclass(frozen=True)
class _Recommendation:
    recommendation_ref: str
    action_type: str
    action_text: str


@dataclass(frozen=True)
class _ExecutionAssessment:
    episode_ref: str
    execution_state: str
    execution_refs: tuple[str, ...]
    confidence: str


@dataclass(frozen=True)
class _CandidateDocument:
    ref: str
    source_key: str
    observed_time: "_ObservedTime"
    text: str


@dataclass(frozen=True)
class _CandidateProjection:
    candidates: tuple[_CandidateDocument, ...]
    source_incomplete: bool
    source_technical: bool


@dataclass(frozen=True)
class _StayWindow:
    admission_day: date | None
    horizon_day: date

    def contains(self, observed_time: "_ObservedTime") -> bool:
        return (
            observed_time.day <= self.horizon_day
            and (
                self.admission_day is None
                or self.admission_day <= observed_time.day
            )
        )


@dataclass(frozen=True)
class _ObservedTime:
    value: datetime
    precise: bool

    @property
    def day(self) -> date:
        return self.value.date()


class _SourceGap(Exception):
    pass


class _SourceTechnical(Exception):
    pass


class _SemanticInvalid(Exception):
    pass


class _SemanticUnresolved(Exception):
    pass


def _clean(value: Any) -> str:
    return " ".join(str(value or "").split())


def _is_pure_signature_template(record_content: Any) -> bool:
    """仅排除空正文或纯签名占位，不按标题、科室或普通短文本猜测。"""

    body = _clean(record_content)
    return not body or bool(_PURE_SIGNATURE_TEMPLATE.fullmatch(body))


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

    def _decode_object(value: str) -> Mapping[str, Any]:
        try:
            parsed = json.loads(value.strip())
        except (TypeError, ValueError) as exc:
            raise _SemanticInvalid() from exc
        if not isinstance(parsed, Mapping):
            raise _SemanticInvalid()
        return parsed

    normalized = raw.strip()
    try:
        return _decode_object(normalized)
    except _SemanticInvalid:
        pass

    # 只容忍模型常见的单一 Markdown JSON fence，或前后只有短说明的
    # 唯一 JSON 对象；不扫描或拼接任意正文，以避免把 <think>、多个候选
    # 对象或截断输出误当成可用事实。
    if "<think" in normalized.lower():
        raise _SemanticInvalid()
    fence_count = normalized.count("```")
    if fence_count == 0:
        object_start = normalized.find("{")
        if object_start < 1:
            raise _SemanticInvalid()
        prefix = normalized[:object_start].strip()
        if len(prefix) > 120 or any(token in prefix for token in ("{", "}", "[", "]")):
            raise _SemanticInvalid()
        try:
            parsed, object_end = json.JSONDecoder().raw_decode(normalized[object_start:])
        except (TypeError, ValueError) as exc:
            raise _SemanticInvalid() from exc
        suffix = normalized[object_start + object_end:].strip()
        if (
            not isinstance(parsed, Mapping)
            or len(suffix) > 120
            or any(token in suffix for token in ("{", "}", "[", "]"))
        ):
            raise _SemanticInvalid()
        return parsed
    if fence_count != 2:
        raise _SemanticInvalid()
    first_fence = normalized.find("```")
    second_fence = normalized.rfind("```")
    prefix = normalized[:first_fence].strip()
    fenced = normalized[first_fence + 3:second_fence].strip()
    suffix = normalized[second_fence + 3:].strip()
    if (
        len(prefix) > 120
        or len(suffix) > 120
        or any(token in prefix or token in suffix for token in ("{", "}", "[", "]"))
    ):
        raise _SemanticInvalid()
    if fenced.lower().startswith("json"):
        language, separator, fenced = fenced.partition("\n")
        if language.strip().lower() != "json" or not separator:
            raise _SemanticInvalid()
    return _decode_object(fenced)


def _read_rows(
    *,
    source_key: str = _SOURCE_KEY,
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
                (item for item in evidence_snapshot.observations if item.source_key == source_key),
                None,
            )
            if observation is None or observation.query_state.value == "unavailable":
                raise _SourceGap()
            if observation.query_state.value == "error":
                raise _SourceTechnical()
            if observation.completeness is SourceCompleteness.TRUNCATED:
                raise _SourceGap()
            rows = [dict(row) for row in evidence_materials.bounded_rows(source_key)]
        else:
            rows = read_luxian_0609_native_source_rows(
                source_key=source_key,
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
    if source_key == _SOURCE_KEY and len(rows) >= _SOURCE_LIMIT:
        raise _SourceGap()
    return [dict(row) for row in rows]


def _documents(rows: Sequence[Mapping[str, Any]]) -> tuple[dict[str, str], ...]:
    documents: list[dict[str, str]] = []
    for index, row in enumerate(rows, start=1):
        body = _clean(row.get("record_content"))
        if _is_pure_signature_template(body):
            continue
        text = _clean("；".join(
            value for value in (_clean(row.get("document_title")), body) if value
        ))
        if len(text) > _MAX_DOCUMENT_CHARS:
            raise _SourceGap()
        documents.append({
            "ref": f"{_SOURCE_KEY}-{index}",
            "time": _clean(row.get("record_time")),
            "text": text,
        })
    return tuple(documents)


def _parse_observed_time(value: Any) -> _ObservedTime | None:
    normalized = _clean(value)
    if not normalized:
        return None
    for fmt in (
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d %H:%M",
        "%Y/%m/%d %H:%M:%S",
    ):
        try:
            return _ObservedTime(datetime.strptime(normalized, fmt), True)
        except ValueError:
            continue
    for fmt in ("%Y-%m-%d", "%Y/%m/%d"):
        try:
            return _ObservedTime(datetime.strptime(normalized, fmt), False)
        except ValueError:
            continue
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        return None
    if parsed.tzinfo is not None:
        parsed = parsed.replace(tzinfo=None)
    return _ObservedTime(parsed, "T" in normalized or " " in normalized)


def _row_time(row: Mapping[str, Any]) -> _ObservedTime | None:
    for key in ("record_time", "prescribed_datetime", "report_time", "report_datetime", "exam_time", "exam_datetime"):
        parsed = _parse_observed_time(row.get(key))
        if parsed is not None:
            return parsed
    return None


def _resolve_execution_stay_window(
    *,
    evidence_materials: Luxian0609EvidenceMaterialStore | None,
    evidence_snapshot: Luxian0609EvidenceSnapshot | None,
) -> _StayWindow:
    """只从同一 Snapshot 的权威住院边界读取第二阶段窗口。"""

    if (
        evidence_materials is None
        or type(evidence_snapshot) is not Luxian0609EvidenceSnapshot
        or evidence_materials.snapshot_hash != evidence_snapshot.snapshot_hash
    ):
        raise _SourceGap()

    observations = {
        item.source_key: item for item in evidence_snapshot.observations
    }
    discharge_observation = observations.get(_STAY_DISCHARGE_SOURCE_KEY)
    if (
        discharge_observation is not None
        and discharge_observation.query_state.value == "error"
    ):
        raise _SourceTechnical()

    def _rows(source_key: str) -> tuple[Mapping[str, object], ...]:
        observation = observations.get(source_key)
        if observation is None or observation.query_state.value == "unavailable":
            raise _SourceGap()
        if observation.query_state.value == "error":
            raise _SourceTechnical()
        if observation.completeness is not SourceCompleteness.COMPLETE:
            raise _SourceGap()
        try:
            rows = evidence_materials.bounded_rows(source_key)
        except (EvidenceMaterialTruncated, EvidenceMaterialUnavailable):
            raise _SourceGap() from None
        if len(rows) != 1:
            raise _SourceGap()
        return rows

    horizon_rows = _rows(_STAY_HORIZON_SOURCE_KEY)
    horizon = _parse_observed_time(horizon_rows[0].get("horizon_date"))
    if horizon is None:
        raise _SourceGap()

    # 所有候选已由同一住院三坐标限定，且后续还会逐条校验必须晚于会诊意见。
    # 因此入院登记未同步时不能把整个执行关联降为 data_gap；它只是不再提供
    # 可用的下界。评估终点仍必须来自同一 Snapshot 的权威 horizon。
    admission: _ObservedTime | None = None
    admission_observation = observations.get(_STAY_ADMISSION_SOURCE_KEY)
    if (
        admission_observation is not None
        and admission_observation.query_state.value == "available"
        and admission_observation.completeness is SourceCompleteness.COMPLETE
    ):
        try:
            admission_rows = evidence_materials.bounded_rows(_STAY_ADMISSION_SOURCE_KEY)
        except (EvidenceMaterialTruncated, EvidenceMaterialUnavailable):
            admission_rows = ()
        if len(admission_rows) == 1:
            admission = _parse_observed_time(admission_rows[0].get("admission_datetime"))
    if admission is not None and admission.day > horizon.day:
        raise _SourceGap()
    return _StayWindow(admission.day if admission is not None else None, horizon.day)


def _candidate_text(row: Mapping[str, Any]) -> str:
    fields = (
        "document_title", "record_content", "generic_name", "brand_name", "drug_type",
        "exam_name", "exam_item_name", "item_name", "exam_result", "exam_impression",
        "exam_conclusion", "impression", "conclusion", "lab_item_name", "result",
        "abnormal_indicator", "surgery_name", "surgery_process",
    )
    return _clean("；".join(_clean(row.get(key)) for key in fields if _clean(row.get(key))))


def _candidate_documents(
    *,
    institute_id: str,
    patient_id: str,
    visit_id: str,
    source_schema: str | None,
    evidence_materials: Luxian0609EvidenceMaterialStore | None,
    evidence_snapshot: Luxian0609EvidenceSnapshot | None,
    stay_window: _StayWindow,
) -> _CandidateProjection:
    candidates: list[_CandidateDocument] = []
    source_incomplete = False
    source_technical = False
    for source_key in _EXECUTION_SOURCE_KEYS:
        try:
            rows = _read_rows(
                source_key=source_key,
                institute_id=institute_id,
                patient_id=patient_id,
                visit_id=visit_id,
                source_schema=source_schema,
                evidence_materials=evidence_materials,
                evidence_snapshot=evidence_snapshot,
            )
        except _SourceGap:
            source_incomplete = True
            continue
        except _SourceTechnical:
            source_technical = True
            continue
        if len(rows) > _MAX_CANDIDATES_PER_SOURCE:
            source_incomplete = True
            continue
        for index, row in enumerate(rows, start=1):
            observed_time = _row_time(row)
            text = _candidate_text(row)
            # 住院窗口外的行不属于本次就诊，既不能作为执行证据，也不能
            # 反过来宣称本次候选范围不完整。
            if observed_time is not None and not stay_window.contains(observed_time):
                continue
            # 单行没有自身可核验的时间或语义内容时，不能让它进入时序关联。
            # 但它仍意味着“未观察到执行”不是完整否定；调用模型后若模型仅给
            # absent，020/023 必须保守为 candidate_scope_incomplete。
            if observed_time is None or not text or len(text) > _MAX_CANDIDATE_CHARS:
                source_incomplete = True
                continue
            candidates.append(_CandidateDocument(
                ref=f"{source_key}-{index}",
                source_key=source_key,
                observed_time=observed_time,
                text=text,
            ))
    return _CandidateProjection(
        candidates=tuple(candidates),
        source_incomplete=source_incomplete,
        source_technical=source_technical,
    )


def _prompt(documents: Sequence[Mapping[str, str]]) -> str:
    payload = json.dumps({"consultation_documents": list(documents)}, ensure_ascii=False)
    if len(payload) > _MAX_PROMPT_CHARS:
        raise _SourceGap()
    return (
        "你只识别本次住院的普通专科会诊，并从明确会诊意见中抽取建议清单；不做任何质控结论。"
        "可把申请、会诊意见、重复同步或分行文书合并为同一episode；非目标文书放入non_target_refs，"
        "无法可靠归属的文书放入unresolved_refs。不得把每一行默认视为一次会诊。"
        "术前多学科讨论、术前风险评估、麻醉评估、MDT讨论、普通病程、计划会诊、既往会诊提及和空模板都不是020-023的普通会诊，"
        "必须放入non_target_refs，绝不能拆成多个会诊episode。"
        "application_state和opinion_state只能是clear/vague/missing/absent/unknown："
        "clear为有明确目的或具体意见，vague为只有泛化措辞，missing为角色存在但内容空缺，"
        "absent为该角色不存在，unknown为材料无法可靠判断。confidence只能为high/medium/low。"
        "明确写出会诊原因、临床问题或请求专科建议，即使只有一句，也属于application_state=clear；"
        "明确给出处理或诊疗建议，即使只有一句，也属于opinion_state=clear；"
        "只有纯“请会诊”或“遵会诊意见”且没有具体内容时才为vague。"
        "仅“请会诊/请某科协助诊治/请协助处理”，无病情问题、诊疗疑问、异常或具体任务时，"
        "application_state必须为vague；科室名称本身不构成会诊目的。"
        "“请康复科评估术后活动障碍/制定康复计划”等写明具体临床问题或任务时为clear；"
        "其它已经说明具体临床问题或任务的申请不得因表述简短而判为vague。"
        "文书只含明确会诊意见、没有申请目的或请求时，application_state必须为absent且application_refs为空；"
        "只含明确申请目的、没有会诊意见时，opinion_state必须为absent且opinion_refs为空。"
        "不得把意见文书的ref借作申请ref，也不得把申请文书的ref借作意见ref，只为避免absent状态；"
        "同一ref仅当该同一文书同时包含明确申请目的和明确会诊意见时，才可同时出现在application_refs和opinion_refs，"
        "且两个state都必须为clear；无法区分角色时返回unknown，不得猜测。"
        "missing只用于角色明确存在但内容空或模板，vague只用于角色存在但内容泛化。"
        "所有输入ref必须恰好归属一次：某个episode.member_refs、non_target_refs或unresolved_refs之一。"
        "同一输入ref不得被拆入多个episode。"
        "episode_ref必须是member_refs之一。禁止创造、改写或遗漏ref。"
        "每个episode还必须给出application_refs、opinion_refs和recommendations，三者只能引用本episode.member_refs；"
        "申请或意见为clear时对应refs不得为空。"
        "recommendations仅用于普通会诊中意见明确且高置信的可执行建议；每项必须是意见原文中的具体行动，"
        "不得把诊断、风险描述、既往史、泛化的\"继续治疗\"或\"遵会诊意见\"当作建议。"
        "recommendation_ref固定为episode_ref#r1、episode_ref#r2依次编号；action_type只能是"
        "medication/test/procedure/transfer/monitoring/other；action_text必须是意见原文的短原句，最长240字。"
        "意见不明确、无可执行建议或非普通会诊时recommendations必须为空数组。"
        "严格输出JSON对象：{episodes:[{episode_ref,member_refs,application_refs,opinion_refs,application_state,opinion_state,confidence,recommendations:[{recommendation_ref,action_type,action_text}]}],"
        "non_target_refs:[],unresolved_refs:[]}。输入：" + payload
    )


def _parse(payload: Mapping[str, Any], documents: Sequence[Mapping[str, str]]) -> tuple[_Episode, ...]:
    raw_episodes = payload.get("episodes")
    non_target = payload.get("non_target_refs")
    unresolved = payload.get("unresolved_refs")
    if not isinstance(raw_episodes, list) or not isinstance(non_target, list) or not isinstance(unresolved, list):
        raise _SemanticInvalid()
    expected_refs = tuple(str(item["ref"]) for item in documents)
    expected = set(expected_refs)
    document_text = {str(item["ref"]): _clean(item.get("text")) for item in documents}
    assigned: list[str] = []
    episodes: list[_Episode] = []
    for raw in raw_episodes:
        if not isinstance(raw, Mapping):
            raise _SemanticInvalid()
        episode_ref = _clean(raw.get("episode_ref"))
        member_refs = raw.get("member_refs")
        application_refs = raw.get("application_refs")
        opinion_refs = raw.get("opinion_refs")
        application = _clean(raw.get("application_state")).lower()
        opinion = _clean(raw.get("opinion_state")).lower()
        confidence = _clean(raw.get("confidence")).lower()
        raw_recommendations = raw.get("recommendations")
        if (
            not isinstance(member_refs, list)
            or not member_refs
            or not all(isinstance(ref, str) and ref in expected for ref in member_refs)
            or len(member_refs) != len(set(member_refs))
            or not isinstance(application_refs, list)
            or not isinstance(opinion_refs, list)
            or not all(isinstance(ref, str) and ref in member_refs for ref in application_refs)
            or not all(isinstance(ref, str) and ref in member_refs for ref in opinion_refs)
            or len(application_refs) != len(set(application_refs))
            or len(opinion_refs) != len(set(opinion_refs))
            or (application == "absent" and application_refs)
            or (opinion == "absent" and opinion_refs)
            or (application == "clear" and not application_refs)
            or (opinion == "clear" and not opinion_refs)
            or episode_ref not in member_refs
            or application not in _STATES
            or opinion not in _STATES
            or confidence not in _CONFIDENCE
            or not isinstance(raw_recommendations, list)
            or len(raw_recommendations) > _MAX_RECOMMENDATIONS
        ):
            raise _SemanticInvalid()
        opinion_text = _clean("；".join(document_text.get(ref, "") for ref in opinion_refs))
        recommendations: list[_Recommendation] = []
        for number, raw_recommendation in enumerate(raw_recommendations, 1):
            if not isinstance(raw_recommendation, Mapping):
                raise _SemanticInvalid()
            recommendation_ref = _clean(raw_recommendation.get("recommendation_ref"))
            action_type = _clean(raw_recommendation.get("action_type")).lower()
            action_text = _clean(raw_recommendation.get("action_text"))
            if (
                recommendation_ref != f"{episode_ref}#r{number}"
                or action_type not in _RECOMMENDATION_TYPES
                or not action_text
                or len(action_text) > _MAX_RECOMMENDATION_CHARS
                or action_text not in opinion_text
            ):
                raise _SemanticInvalid()
            recommendations.append(_Recommendation(recommendation_ref, action_type, action_text))
        if raw_recommendations and (opinion != "clear" or confidence != "high"):
            raise _SemanticInvalid()
        assigned.extend(member_refs)
        episodes.append(_Episode(
            episode_ref,
            tuple(member_refs),
            tuple(application_refs),
            tuple(opinion_refs),
            application,
            opinion,
            confidence,
            tuple(recommendations),
        ))
    for group in (non_target, unresolved):
        if not all(isinstance(ref, str) and ref in expected for ref in group):
            raise _SemanticInvalid()
        assigned.extend(group)
    if len(assigned) != len(expected_refs) or len(set(assigned)) != len(expected_refs) or set(assigned) != expected:
        raise _SemanticInvalid()
    if unresolved:
        raise _SemanticUnresolved()
    return tuple(episodes)


def _completed_episodes(
    episodes: Sequence[_Episode],
    documents: Sequence[Mapping[str, str]],
    *,
    stay_window: _StayWindow | None,
) -> tuple[tuple[_Episode, _ObservedTime, str], ...]:
    by_ref = {str(item["ref"]): item for item in documents}
    completed: list[tuple[_Episode, _ObservedTime, str]] = []
    for item in episodes:
        if item.opinion_state != "clear" or item.confidence != "high":
            continue
        members = [by_ref.get(ref) for ref in item.opinion_refs]
        if any(member is None for member in members):
            raise _SemanticInvalid()
        observed_times = [_parse_observed_time(member.get("time")) for member in members if member is not None]
        if not observed_times or any(value is None for value in observed_times):
            raise _SourceGap()
        if stay_window is None or any(
            not stay_window.contains(value)
            for value in observed_times
            if value is not None
        ):
            raise _SourceGap()
        opinion_text = _clean("；".join(str(member.get("text") or "") for member in members if member is not None))
        if not opinion_text or len(opinion_text) > _MAX_EPISODE_OPINION_CHARS:
            raise _SourceGap()
        completed.append((
            item,
            max((value for value in observed_times if value is not None), key=lambda value: value.value),
            opinion_text,
        ))
    if len(completed) > _MAX_EPISODES:
        raise _SourceGap()
    return tuple(completed)


def _execution_prompt(
    *,
    completed: Sequence[tuple[_Episode, _ObservedTime, str]],
    candidates: Sequence[_CandidateDocument],
) -> tuple[str, Mapping[str, frozenset[str]], frozenset[str]]:
    entries: list[dict[str, object]] = []
    allowed_refs: dict[str, frozenset[str]] = {}
    temporal_incomplete: set[str] = set()
    for item, opinion_time, opinion_text in completed:
        related: list[dict[str, object]] = []
        for candidate in candidates:
            if candidate.observed_time.day > opinion_time.day:
                include = True
            elif candidate.observed_time.day < opinion_time.day:
                include = False
            elif candidate.observed_time.precise and opinion_time.precise:
                include = candidate.observed_time.value > opinion_time.value
            else:
                include = False
                temporal_incomplete.add(item.episode_ref)
            if include:
                related.append({
                    "ref": candidate.ref,
                    "source": candidate.source_key,
                    "date": candidate.observed_time.value.isoformat(),
                    "text": candidate.text,
                })
        allowed_refs[item.episode_ref] = frozenset(str(candidate["ref"]) for candidate in related)
        entries.append({
            "episode_ref": item.episode_ref,
            "opinion_date": opinion_time.value.isoformat(),
            "opinion_text": opinion_text,
            "candidate_documents": related,
        })
    payload = json.dumps({"episodes": entries}, ensure_ascii=False)
    if len(payload) > _MAX_PROMPT_CHARS:
        raise _SourceGap()
    prompt = (
        "你只判断每个已完成会诊意见与其后续候选文书是否存在执行关联，不得补充病历之外的信息。"
        "同一执行文书可同时落实多个episode，禁止要求唯一归属。"
        "linked_specific只在候选明确落实同一条意见的具体措施，或直接点名该会诊意见且包含明确措施时使用。"
        "仅直接写“遵/按本次会诊意见”但未写具体措施时为linked_vague。"
        "申请、拟请或请会诊动作本身不是执行。"
        "仅治疗同一症状、部位或一般治疗但措施不同，必须为absent，不能关联。"
        "execution_state只能为linked_specific（有具体落实内容）、linked_vague（仅笼统遵医嘱/遵会诊意见）、"
        "absent（候选中无执行）或unknown。confidence只能为high/medium/low。"
        "execution_refs只能引用该episode输入candidate_documents中的ref，绝不得引用会诊申请或会诊意见的ref。"
        "linked_specific或linked_vague必须至少返回一个execution_refs；没有可验证的candidate_documents ref时必须返回unknown。"
        "absent或unknown必须返回空数组。"
        "每个输入episode_ref恰好输出一项，禁止重复。"
        "严格输出JSON：{executions:[{episode_ref,execution_state,execution_refs,confidence}]}。输入："
        + payload
    )
    return prompt, allowed_refs, frozenset(temporal_incomplete)


def _parse_executions(
    payload: Mapping[str, Any],
    *,
    completed: Sequence[tuple[_Episode, _ObservedTime, str]],
    allowed_refs: Mapping[str, frozenset[str]],
) -> tuple[_ExecutionAssessment, ...]:
    raw = payload.get("executions")
    expected_refs = {item.episode_ref for item, _, _ in completed}
    if not isinstance(raw, list) or len(raw) != len(expected_refs):
        raise _SemanticInvalid()
    parsed: list[_ExecutionAssessment] = []
    seen: set[str] = set()
    for item in raw:
        if not isinstance(item, Mapping):
            raise _SemanticInvalid()
        episode_ref = _clean(item.get("episode_ref"))
        state = _clean(item.get("execution_state")).lower()
        confidence = _clean(item.get("confidence")).lower()
        refs = item.get("execution_refs")
        if (
            episode_ref not in expected_refs
            or episode_ref in seen
            or state not in _EXECUTION_STATES
            or confidence not in _CONFIDENCE
            or not isinstance(refs, list)
            or len(refs) != len(set(refs))
            or not all(isinstance(ref, str) and ref in allowed_refs[episode_ref] for ref in refs)
            or (state in {"linked_specific", "linked_vague"} and not refs)
            or (state in {"absent", "unknown"} and refs)
        ):
            raise _SemanticInvalid()
        seen.add(episode_ref)
        parsed.append(_ExecutionAssessment(episode_ref, state, tuple(refs), confidence))
    if seen != expected_refs:
        raise _SemanticInvalid()
    return tuple(parsed)


def _outcome(rule_id: str, episodes: Sequence[_Episode]) -> tuple[str, str]:
    field = "application_state" if rule_id == "LX0609-021" else "opinion_state"
    states = tuple(getattr(episode, field) for episode in episodes)
    if any(state in {"vague", "missing"} for state in states):
        return "non_compliant", "requirement_violated"
    if any(episode.confidence != "high" for episode in episodes) or "unknown" in states:
        return "evaluation_unknown", "semantic_low_confidence"
    applicable = tuple(state for state in states if state != "absent")
    if not applicable:
        return "not_applicable", "trigger_absent_complete"
    if all(state == "clear" for state in applicable):
        return "compliant", "requirement_satisfied"
    return "evaluation_unknown", "semantic_output_unknown"


def _execution_outcome(
    rule_id: str,
    *,
    episodes: Sequence[_Episode],
    assessments: Sequence[_ExecutionAssessment] | None,
    source_incomplete: bool = False,
    source_technical: bool = False,
    temporal_incomplete_episodes: frozenset[str] = frozenset(),
) -> tuple[str, str]:
    uncertain = any(
        item.confidence != "high" or item.opinion_state == "unknown"
        for item in episodes
    )
    completed = tuple(item for item in episodes if item.opinion_state == "clear" and item.confidence == "high")
    if uncertain:
        return "evaluation_unknown", "semantic_low_confidence"
    if not completed:
        return "not_applicable", "trigger_absent_complete"
    if source_technical:
        return "technical_error", "source_query_error"
    # 同日候选与会诊意见任一侧缺少精确时间时，不能依赖其它候选的
    # 语义关联掩盖先后关系不明；020/023 必须整体 fail-closed。
    if temporal_incomplete_episodes:
        return "evaluation_unknown", "semantic_output_unknown"
    if assessments is None or any(item.confidence != "high" or item.execution_state == "unknown" for item in assessments):
        if source_technical:
            return "technical_error", "source_query_error"
        return "evaluation_unknown", "semantic_low_confidence"
    states = tuple(item.execution_state for item in assessments)
    absent_refs = {
        item.episode_ref for item in assessments if item.execution_state == "absent"
    }
    unresolved_absent = absent_refs.intersection(temporal_incomplete_episodes)
    if rule_id == "LX0609-020":
        if absent_refs:
            if source_technical:
                return "technical_error", "source_query_error"
            if source_incomplete:
                return "evaluation_unknown", "candidate_scope_incomplete"
            if absent_refs.difference(unresolved_absent):
                return "non_compliant", "requirement_violated"
            if unresolved_absent:
                return "data_gap", "linkage_unresolved"
            return "non_compliant", "requirement_violated"
        return "compliant", "requirement_satisfied"
    if absent_refs:
        if source_incomplete:
            return "evaluation_unknown", "candidate_scope_incomplete"
        return "not_applicable", "trigger_absent_complete"
    if "linked_vague" in states:
        return "non_compliant", "requirement_violated"
    if "linked_specific" in states:
        return "compliant", "requirement_satisfied"
    if source_technical:
        return "technical_error", "source_query_error"
    if source_incomplete:
        return "data_gap", "linkage_unresolved"
    if unresolved_absent:
        return "data_gap", "linkage_unresolved"
    return "not_applicable", "trigger_absent_complete"


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


def _decision(
    *, rule_id: str, status: str, reason_code: str,
    snapshot: Luxian0609EvidenceSnapshot,
) -> RuleDecision:
    source_keys = {_SOURCE_KEY}
    if rule_id in {"LX0609-020", "LX0609-023"}:
        source_keys.update({
            _STAY_ADMISSION_SOURCE_KEY,
            _STAY_DISCHARGE_SOURCE_KEY,
            _STAY_HORIZON_SOURCE_KEY,
            *_EXECUTION_SOURCE_KEYS,
        })
    refs = tuple(
        observation.snapshot_ref.removeprefix("sha256:")
        for observation in snapshot.observations
        if observation.source_key in source_keys
    )
    if status == "compliant":
        dimensions = (ApplicabilityState.APPLICABLE, EvidenceState.SUFFICIENT, QcDirection.SATISFIED)
    elif status == "non_compliant":
        dimensions = (ApplicabilityState.APPLICABLE, EvidenceState.SUFFICIENT, QcDirection.DEFECT)
    elif status == "not_applicable":
        dimensions = (ApplicabilityState.NOT_APPLICABLE, EvidenceState.SUFFICIENT, QcDirection.UNKNOWN)
    elif status == "data_gap":
        dimensions = (ApplicabilityState.UNKNOWN, EvidenceState.DATA_GAP, QcDirection.UNKNOWN)
    elif status == "evaluation_unknown":
        dimensions = (ApplicabilityState.UNKNOWN, EvidenceState.CONFLICT, QcDirection.UNKNOWN)
    else:
        dimensions = (ApplicabilityState.ERROR, EvidenceState.TECHNICAL_ERROR, QcDirection.UNKNOWN)
    applicability, evidence_state, direction = dimensions
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
        _decision(
            rule_id=rule_id,
            status=status,
            reason_code=reason_code,
            snapshot=evidence_snapshot,
        )
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
    stage_two_rule_ids = tuple(
        rule_id for rule_id in selected if rule_id in {"LX0609-020", "LX0609-023"}
    )
    execution_stay_window: _StayWindow | None = None
    stage_two_boundary_status: tuple[str, str] | None = None
    if stage_two_rule_ids:
        try:
            execution_stay_window = _resolve_execution_stay_window(
                evidence_materials=evidence_materials,
                evidence_snapshot=evidence_snapshot,
            )
        except _SourceTechnical:
            stage_two_boundary_status = ("technical_error", "source_query_error")
        except _SourceGap:
            stage_two_boundary_status = ("data_gap", "linkage_unresolved")
        if stage_two_boundary_status is not None and len(stage_two_rule_ids) == len(selected):
            return _finish(
                selected=selected,
                status=stage_two_boundary_status[0],
                reason_code=stage_two_boundary_status[1],
                evidence_snapshot=evidence_snapshot,
                decision_rule_ids=typed,
            )
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
        episodes = _parse(_payload(response), documents)
    except _SourceGap:
        return _finish(selected=selected, status="data_gap", reason_code="linkage_unresolved", calls=calls, prompt_tokens=prompt_tokens, completion_tokens=completion_tokens, total_tokens=total_tokens, api_time=api_time, evidence_snapshot=evidence_snapshot, decision_rule_ids=typed)
    except _SemanticUnresolved:
        return _finish(selected=selected, status="evaluation_unknown", reason_code="semantic_output_unknown", calls=calls, prompt_tokens=prompt_tokens, completion_tokens=completion_tokens, total_tokens=total_tokens, api_time=api_time, evidence_snapshot=evidence_snapshot, decision_rule_ids=typed)
    except _SemanticInvalid:
        return _finish(selected=selected, status="evaluation_unknown", reason_code="semantic_output_unknown", calls=calls, prompt_tokens=prompt_tokens, completion_tokens=completion_tokens, total_tokens=total_tokens, api_time=api_time, evidence_snapshot=evidence_snapshot, decision_rule_ids=typed)
    except Exception:
        return _finish(selected=selected, status="technical_error", reason_code="model_transport_error", calls=calls, evidence_snapshot=evidence_snapshot, decision_rule_ids=typed)
    statuses: dict[str, tuple[str, str]] = {
        rule_id: _outcome(rule_id, episodes)
        for rule_id in selected
        if rule_id in {"LX0609-021", "LX0609-022"}
    }
    execution_assessments: tuple[_ExecutionAssessment, ...] | None = None
    execution_source_incomplete = False
    execution_source_technical = False
    execution_temporal_incomplete: frozenset[str] = frozenset()
    if stage_two_rule_ids:
        if stage_two_boundary_status is not None:
            for rule_id in stage_two_rule_ids:
                statuses[rule_id] = stage_two_boundary_status
            completed = ()
        else:
            try:
                completed = _completed_episodes(
                    episodes,
                    documents,
                    stay_window=execution_stay_window,
                )
            except _SourceGap:
                completed = ()
                for rule_id in stage_two_rule_ids:
                    statuses[rule_id] = ("data_gap", "linkage_unresolved")
            except _SemanticInvalid:
                completed = ()
                for rule_id in stage_two_rule_ids:
                    statuses[rule_id] = ("evaluation_unknown", "semantic_output_unknown")
        if not any(rule_id in statuses for rule_id in stage_two_rule_ids):
            preliminary = _execution_outcome("LX0609-020", episodes=episodes, assessments=None)
            if preliminary[0] == "not_applicable":
                for rule_id in stage_two_rule_ids:
                    statuses[rule_id] = ("not_applicable", "trigger_absent_complete")
            elif completed:
                projection = _candidate_documents(
                    institute_id=institute_id,
                    patient_id=patient_id,
                    visit_id=visit_id,
                    source_schema=source_schema,
                    evidence_materials=evidence_materials,
                    evidence_snapshot=evidence_snapshot,
                    stay_window=execution_stay_window,
                )
                execution_source_incomplete = projection.source_incomplete
                execution_source_technical = projection.source_technical
                if execution_source_technical:
                    for rule_id in stage_two_rule_ids:
                        statuses[rule_id] = ("technical_error", "source_query_error")
                elif not projection.candidates:
                    execution_assessments = tuple(
                        _ExecutionAssessment(item.episode_ref, "absent", (), "high")
                        for item, _, _ in completed
                    )
                else:
                    second_prompt, allowed_refs, execution_temporal_incomplete = _execution_prompt(
                        completed=completed,
                        candidates=projection.candidates,
                    )
                    if not any(allowed_refs.values()):
                        execution_assessments = tuple(
                            _ExecutionAssessment(item.episode_ref, "absent", (), "high")
                            for item, _, _ in completed
                        )
                    else:
                        calls += 1
                        try:
                            started = time.perf_counter()
                            response = await llm_client.generate(second_prompt)
                            if not isinstance(response, Mapping):
                                raise _SemanticInvalid()
                            next_prompt, next_completion, next_total, response_time = _usage(response)
                            prompt_tokens += next_prompt
                            completion_tokens += next_completion
                            total_tokens += next_total
                            api_time += response_time or (time.perf_counter() - started)
                            execution_assessments = _parse_executions(
                                _payload(response), completed=completed, allowed_refs=allowed_refs,
                            )
                        except _SemanticInvalid:
                            status = "technical_error" if execution_source_technical else "evaluation_unknown"
                            reason = "source_query_error" if execution_source_technical else "semantic_output_unknown"
                            for rule_id in stage_two_rule_ids:
                                statuses[rule_id] = (status, reason)
                        except Exception:
                            for rule_id in stage_two_rule_ids:
                                statuses[rule_id] = ("technical_error", "model_transport_error")
            else:
                for rule_id in stage_two_rule_ids:
                    statuses[rule_id] = _execution_outcome(rule_id, episodes=episodes, assessments=None)
        if execution_assessments is not None:
            for rule_id in stage_two_rule_ids:
                statuses[rule_id] = _execution_outcome(
                    rule_id,
                    episodes=episodes,
                    assessments=execution_assessments,
                    source_incomplete=execution_source_incomplete,
                    source_technical=execution_source_technical,
                    temporal_incomplete_episodes=execution_temporal_incomplete,
                )
    results = []
    for rule_id in selected:
        status, reason = statuses.get(rule_id, ("data_gap", "linkage_unresolved"))
        results.append(_result(rule_id=rule_id, status=status, reason_code=reason, prompt_tokens=prompt_tokens, completion_tokens=completion_tokens, total_tokens=total_tokens))
    decisions = tuple(
        _decision(
            rule_id=rule_id,
            status=statuses[rule_id][0],
            reason_code=statuses[rule_id][1],
            snapshot=evidence_snapshot,
        )
        for rule_id in selected
        if rule_id in typed and evidence_snapshot is not None
    )
    return NativeConsultationEpisodeExecutionResult(
        results=tuple(item for item in results if item["rule_id"] not in typed), planned_rule_ids=selected,
        decisions=decisions, llm_call_count=calls,
        prompt_tokens=prompt_tokens, completion_tokens=completion_tokens,
        total_tokens=total_tokens, api_time=api_time,
    )
