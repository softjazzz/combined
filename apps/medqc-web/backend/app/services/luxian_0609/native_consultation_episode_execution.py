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
import unicodedata
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
_ORDER_EXECUTION_SOURCE_KEYS = frozenset(
    {"inpat_drug_order", "inpat_nondrug_order"}
)
# 医嘱是高频结构化事件。保留紧凑候选可供模型确认正向落实；来源超过
# 此上限时仍标记不完整，因此模型的 absent 绝不会生成确定性缺陷。
_MAX_ORDER_CANDIDATES_PER_SOURCE = 24
_MAX_ORDER_CANDIDATE_CHARS = 180
_EXECUTION_SOURCE_KEYS = (
    "daily_course_record",
    "senior_course_record",
    "inpat_drug_order",
    "inpat_nondrug_order",
)
_SNAPSHOT_EXECUTION_SOURCE_KEYS = _EXECUTION_SOURCE_KEYS
_CONTEXT_ONLY_EXECUTION_SOURCE_KEYS = frozenset((
    "daily_course_record",
    "senior_course_record",
))
_COURSE_EXECUTION_SOURCE_KEYS = _CONTEXT_ONLY_EXECUTION_SOURCE_KEYS
_STRUCTURED_EXECUTION_EVIDENCE_SOURCE_KEYS = frozenset(
    source_key
    for source_key in _EXECUTION_SOURCE_KEYS
    if source_key not in _CONTEXT_ONLY_EXECUTION_SOURCE_KEYS
)
# 仅供安全台账按建议类型描述候选来源覆盖；不得用于否决 LLM 的 absent
# 语义判断或回退状态。
_ACTION_TYPE_SOURCE_KEYS = {
    "medication": frozenset((
        "inpat_drug_order", "inpat_nondrug_order", "daily_course_record", "senior_course_record",
    )),
    "test": frozenset((
        "inpat_nondrug_order", "daily_course_record", "senior_course_record",
    )),
    "procedure": frozenset((
        "inpat_nondrug_order", "daily_course_record", "senior_course_record",
    )),
    "transfer": frozenset((
        "inpat_nondrug_order", "inpat_drug_order", "daily_course_record", "senior_course_record",
    )),
    "monitoring": frozenset((
        "inpat_nondrug_order", "daily_course_record", "senior_course_record",
    )),
    "other": frozenset(_EXECUTION_SOURCE_KEYS),
}
# 4.20.4 要求申请会诊医师在会诊后的病程记录中记录会诊意见及执行情况。
# 医嘱可辅助语义关联，但不能替代病程记录，也不能成为 020 合规的硬前提。
_STAY_ADMISSION_SOURCE_KEY = "inpat_registration"
_STAY_DISCHARGE_SOURCE_KEY = "inpat_registration.discharge_horizon"
_STAY_HORIZON_SOURCE_KEY = "evaluation_context.horizon"
_STATES = frozenset({"clear", "vague", "missing", "absent", "unknown"})
_CONFIDENCE = frozenset({"high", "medium", "low"})
_EXECUTION_STATES = frozenset({"linked_specific", "linked_vague", "absent", "unknown"})
_EXECUTION_RECORD_STATES = frozenset({
    "specific_trace",
    "generic_trace",
    "copied_opinion",
    "no_trace",
    "unknown",
})
_RECOMMENDATION_TYPES = frozenset({"medication", "test", "procedure", "transfer", "monitoring", "other"})
_EXPLICIT_REQUEST_CLEAR_PATTERN = re.compile(
    r"(?:会诊目的|申请.{0,12}会诊).{0,80}"
    r"(?:评估.{0,24}(?:适应证|病情|方案)|明确.{0,24}(?:诊断|原因|方案)|"
    r"提出.{0,16}(?:明确)?(?:方案|意见)|制定.{0,16}(?:方案|计划))"
)
_EXPLICIT_REQUEST_VAGUE_PATTERN = re.compile(
    r"^(?:会诊申请单；)?(?:请|申请)?相关科室会诊(?:协助)?(?:诊治|处理)[。；]?$"
)
_EXPLICIT_OPINION_VAGUE_PATTERN = re.compile(
    r"(?:必要时|酌情|视情况).{0,24}(?:完善|行|给予).{0,20}(?:检查|药物治疗|对症治疗)"
)
_EXPLICIT_OPINION_CLEAR_PATTERN = re.compile(
    r"(?:会诊意见).{0,160}(?:建议|诊断).{0,100}"
    r"(?:今日|立即|继续|停用|改用|加用|行[A-Za-z0-9\u4e00-\u9fff]{2,24}|"
    r"完善[A-Za-z0-9\u4e00-\u9fff]{2,24}(?:检查|检验)|预约)"
)
_EXPLICIT_EXECUTION_TRACE_PATTERN = re.compile(
    r"(?:已归纳.{0,12}会诊意见|执行会诊意见|按(?:会诊)?建议|"
    r"根据会诊意见|落实会诊意见|按意见.{0,12}(?:执行|处理|治疗))"
)
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
# 020--023 只覆盖普通专科会诊。以下是文书自身明确标注的非目标事件，
# 不能因模型将其误识别为“会诊意见”而进入规则链。不得按“疼痛科”或
# “麻醉科”科室名称泛排除：普通疼痛会诊仍可能是本规则的目标对象。
_EXPLICIT_NON_TARGET_CONSULTATION_PATTERNS = (
    re.compile(r"(?:术前)?(?:麻醉|麻醉科)(?:评估|风险评估)"),
    re.compile(r"术前(?:多学科|MDT|风险)评估"),
    re.compile(r"(?:术前)?(?:多学科讨论|MDT讨论)"),
    re.compile(
        r"(?:拟行|拟做).{0,32}无痛(?:纤支镜|支气管镜|胃镜|肠镜|检查|手术)"
        r".{0,120}(?:疼痛科|麻醉科)(?:会诊|评估)"
    ),
)
_SPECIFIC_APPLICATION_PURPOSE_PATTERN = re.compile(
    r"(?:"
    r"因|由于|出现|伴有|诊断|治疗|处理|评估|制定|调整|完善|明确|控制|监测|"
    r"术后|活动障碍|功能障碍|疼痛|发热|感染|出血|贫血|水肿|胸痛|腹痛|"
    r"呼吸|血压|血糖|心律|肝功|肾功|肺炎|骨折|梗死|休克|风险|异常"
    r")"
)
_GENERIC_APPLICATION_PURPOSE_PATTERN = re.compile(
    r"^(?:申请)?请?[\u4e00-\u9fff]{0,8}科?"
    r"(?:会诊|协诊|协助诊治|协助处理|指导治疗|进一步诊治)$"
)


class ConsultationEpisodeLLMClient(Protocol):
    async def generate(self, prompt: str) -> dict[str, Any]: ...


@dataclass(frozen=True)
class NativeConsultationEpisodeExecutionResult:
    results: tuple[dict[str, Any], ...]
    planned_rule_ids: tuple[str, ...]
    decisions: tuple[RuleDecision, ...] = ()
    customer_display_facts: tuple[tuple[str, Mapping[str, Any]], ...] = ()
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
    source_quote: str
    normalized_action: str
    opinion_ref: str


@dataclass(frozen=True)
class _ExecutionAssessment:
    recommendation_ref: str
    execution_state: str
    execution_refs: tuple[str, ...]
    confidence: str
    execution_quotes: tuple[str, ...]
    execution_record_state: str = "no_trace"
    trace_refs: tuple[str, ...] = ()
    context_only_refs: tuple[str, ...] = ()


@dataclass(frozen=True)
class _CompletedRecommendation:
    episode_ref: str
    recommendation: _Recommendation
    opinion_time: "_ObservedTime"


@dataclass(frozen=True)
class _CandidateDocument:
    ref: str
    source_key: str
    observed_time: "_ObservedTime"
    text: str


@dataclass(frozen=True)
class _CandidateProjection:
    candidates: tuple[_CandidateDocument, ...]
    source_complete_keys: frozenset[str]
    source_incomplete_keys: frozenset[str]
    source_technical: bool

    @property
    def source_incomplete(self) -> bool:
        """兼容只读诊断；业务判定必须改用建议相关来源集合。"""

        return bool(self.source_incomplete_keys)


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


_NEGATION_PREFIX = re.compile(r"(?:不|无|未|否认|禁止|避免)$")
_DOSE_OR_NUMERIC = re.compile(r"\d+(?:\.\d+)?")
_DOSE_VALUE = re.compile(r"\d+(?:\.\d+)?(?:mg|g|ml|μg|ug|片|次|日|h|小时|%)", re.IGNORECASE)


def _evidence_text(value: str) -> str:
    """只做格式归一，不做同义替换或医学解释。"""

    return re.sub(r"\s+", "", unicodedata.normalize("NFKC", value)).strip()


def _quote_is_grounded(*, quote: str, source: str) -> bool:
    """确认摘录可由单一原文支持，拒绝截去否定或紧邻剂量/数值。"""

    normalized_quote = _evidence_text(quote)
    normalized_source = _evidence_text(source)
    if not normalized_quote or not normalized_source:
        return False
    offset = normalized_source.find(normalized_quote)
    while offset >= 0:
        prefix = normalized_source[max(0, offset - 3):offset]
        suffix = normalized_source[offset + len(normalized_quote):offset + len(normalized_quote) + 12]
        quote_has_number = bool(_DOSE_OR_NUMERIC.search(normalized_quote))
        adjacent_dose = bool(_DOSE_VALUE.search(prefix + suffix))
        if not _NEGATION_PREFIX.search(prefix) and (quote_has_number or not adjacent_dose):
            return True
        offset = normalized_source.find(normalized_quote, offset + 1)
    return False


def _clean(value: Any) -> str:
    return " ".join(str(value or "").split())


def _is_pure_signature_template(record_content: Any) -> bool:
    """仅排除空正文或纯签名占位，不按标题、科室或普通短文本猜测。"""

    body = _clean(record_content)
    return not body or bool(_PURE_SIGNATURE_TEMPLATE.fullmatch(body))


def _documents_are_explicit_non_target(documents: Sequence[Mapping[str, str]]) -> bool:
    """只在全部文书均有明确非目标语义时短路，混合文书仍交给第一阶段 LLM。"""

    return bool(documents) and all(
        any(pattern.search(_evidence_text(item.get("text", ""))) for pattern in _EXPLICIT_NON_TARGET_CONSULTATION_PATTERNS)
        for item in documents
    )


def _has_specific_application_purpose(
    *,
    application_refs: Sequence[str],
    documents_by_ref: Mapping[str, Mapping[str, str]],
) -> bool:
    """稳定 021 边界：具体临床问题/任务不能因模型措辞抖动被判 vague。"""

    texts = [
        _clean((documents_by_ref.get(ref) or {}).get("text"))
        for ref in application_refs
    ]
    text = _evidence_text("；".join(item for item in texts if item))
    if not text or _GENERIC_APPLICATION_PURPOSE_PATTERN.fullmatch(text):
        return False
    return bool(_SPECIFIC_APPLICATION_PURPOSE_PATTERN.search(text))


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
    allow_truncated: bool = False,
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
            if (
                observation.completeness is SourceCompleteness.TRUNCATED
                and not allow_truncated
            ):
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
    except KeyError:
        rows = []
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
            "document_id": _clean(row.get("document_id")),
            "time": _clean(row.get("record_time")),
            "text": text,
        })
    return tuple(documents)


def _parse_observed_time(value: Any) -> _ObservedTime | None:
    normalized = _clean(value)
    if not normalized:
        return None
    normalized = re.sub(r"([+-]\d{2})$", r"\1:00", normalized)
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


def _row_time(
    row: Mapping[str, Any], *, source_key: str | None = None
) -> _ObservedTime | None:
    # 医嘱的开始/下达时间是执行关联的业务时序；通用 record_time 可能只是
    # 同步或归档时间，不能覆盖它。其余文书仍按自身记录/报告时间处理。
    if source_key in {"inpat_drug_order", "inpat_nondrug_order"}:
        time_keys = (
            "start_time",
            "order_time",
            "prescribed_datetime",
            "update_time",
            "record_time",
        )
    else:
        time_keys = (
            "record_time",
            "request_time",
            "report_time",
            "report_datetime",
            "exam_time",
            "exam_datetime",
            "request_datetime",
            "request_surgery_datetime",
        )
    for key in time_keys:
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


def _candidate_text(*, row: Mapping[str, Any], source_key: str) -> str:
    if source_key in _ORDER_EXECUTION_SOURCE_KEYS:
        # 医嘱关联只需要可辨识的结构化动作；不把冗长医嘱正文带入模型上下文。
        fields = (
            "generic_name",
            "brand_name",
            "drug_type",
            "drug_apply_method",
            "drug_frequency",
            "order_name",
            "order_type",
        )
    else:
        fields = (
            "document_title", "record_content", "generic_name", "brand_name", "drug_type",
            "order_name", "exam_reason", "labtest_subject",
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
    source_complete_keys: set[str] = set()
    source_incomplete_keys: set[str] = set()
    source_technical = False
    source_keys = (
        _SNAPSHOT_EXECUTION_SOURCE_KEYS
        if evidence_materials is not None and evidence_snapshot is not None
        else _EXECUTION_SOURCE_KEYS
    )
    for source_key in source_keys:
        is_order_source = source_key in _ORDER_EXECUTION_SOURCE_KEYS
        try:
            rows = _read_rows(
                source_key=source_key,
                institute_id=institute_id,
                patient_id=patient_id,
                visit_id=visit_id,
                source_schema=source_schema,
                evidence_materials=evidence_materials,
                evidence_snapshot=evidence_snapshot,
                allow_truncated=is_order_source,
            )
        except _SourceGap:
            source_incomplete_keys.add(source_key)
            continue
        except _SourceTechnical:
            source_technical = True
            continue
        source_is_complete = True
        if evidence_snapshot is not None:
            observation = next(
                (
                    item
                    for item in evidence_snapshot.observations
                    if item.source_key == source_key
                ),
                None,
            )
            if observation is None or observation.completeness is not SourceCompleteness.COMPLETE:
                source_is_complete = False
        source_limit = (
            _MAX_ORDER_CANDIDATES_PER_SOURCE
            if is_order_source
            else _MAX_CANDIDATES_PER_SOURCE
        )
        if len(rows) > source_limit:
            if not is_order_source:
                source_incomplete_keys.add(source_key)
                continue
            # 医嘱是 020/023 的主执行证据，真实病例中常为高频清单。
            # 这里采用会诊后时间排序的固定上限候选集，避免“医嘱很多”
            # 本身把所有建议都拖成资料不足；行级缺时间/缺内容仍会在
            # 下方标记为来源不完整。
            rows = rows[:source_limit]
        for index, row in enumerate(rows, start=1):
            observed_time = _row_time(row, source_key=source_key)
            text = _candidate_text(row=row, source_key=source_key)
            # 住院窗口外的行不属于本次就诊，既不能作为执行证据，也不能
            # 反过来宣称本次候选范围不完整。
            if observed_time is not None and not stay_window.contains(observed_time):
                continue
            # 单行没有自身可核验的时间或语义内容时，不能让它进入时序关联。
            # 但它仍意味着“未观察到执行”不是完整否定；调用模型后若模型仅给
            # absent，020/023 必须保守为 candidate_scope_incomplete。
            text_limit = (
                _MAX_ORDER_CANDIDATE_CHARS
                if is_order_source
                else _MAX_CANDIDATE_CHARS
            )
            if observed_time is None or not text or len(text) > text_limit:
                source_is_complete = False
                continue
            candidates.append(_CandidateDocument(
                ref=f"{source_key}-{index}",
                source_key=source_key,
                observed_time=observed_time,
                text=text,
            ))
        if source_is_complete:
            source_complete_keys.add(source_key)
        else:
            source_incomplete_keys.add(source_key)
    return _CandidateProjection(
        candidates=tuple(candidates),
        source_complete_keys=frozenset(source_complete_keys),
        source_incomplete_keys=frozenset(source_incomplete_keys),
        source_technical=source_technical,
    )


def _strong_explicit_consultation_statuses(
    *,
    selected: Sequence[str],
    documents: Sequence[Mapping[str, str]],
    execution_projection: _CandidateProjection | None,
) -> dict[str, tuple[str, str]]:
    """只处理文书角色和结论均显式的高置信会诊场景。"""

    request_documents = tuple(
        item for item in documents if "会诊申请" in _clean(item.get("text"))
    )
    opinion_documents = tuple(
        item for item in documents if "会诊意见" in _clean(item.get("text"))
    )
    if len(request_documents) != 1 or len(opinion_documents) != 1:
        return {}

    statuses: dict[str, tuple[str, str]] = {}
    request_text = _clean(request_documents[0].get("text"))
    opinion_text = _clean(opinion_documents[0].get("text"))
    if "LX0609-021" in selected:
        if _EXPLICIT_REQUEST_VAGUE_PATTERN.fullmatch(request_text):
            statuses["LX0609-021"] = ("non_compliant", "requirement_violated")
        elif _EXPLICIT_REQUEST_CLEAR_PATTERN.search(request_text):
            statuses["LX0609-021"] = ("compliant", "requirement_satisfied")
    if "LX0609-022" in selected:
        if _EXPLICIT_OPINION_VAGUE_PATTERN.search(opinion_text):
            statuses["LX0609-022"] = ("non_compliant", "requirement_violated")
        elif _EXPLICIT_OPINION_CLEAR_PATTERN.search(opinion_text):
            statuses["LX0609-022"] = ("compliant", "requirement_satisfied")
    if "LX0609-020" in selected and execution_projection is not None:
        if any(
            item.source_key in _COURSE_EXECUTION_SOURCE_KEYS
            and _EXPLICIT_EXECUTION_TRACE_PATTERN.search(item.text)
            for item in execution_projection.candidates
        ):
            statuses["LX0609-020"] = ("compliant", "requirement_satisfied")
        elif (
            not any(
                item.source_key in _COURSE_EXECUTION_SOURCE_KEYS
                for item in execution_projection.candidates
            )
            and set(_COURSE_EXECUTION_SOURCE_KEYS).issubset(
                execution_projection.source_complete_keys
            )
        ):
            statuses["LX0609-020"] = ("non_compliant", "requirement_violated")
    return statuses


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
        "medication/test/procedure/transfer/monitoring/other。每项必须返回opinion_ref、source_quote和normalized_action："
        "opinion_ref只能是本episode的opinion_refs之一；source_quote用于人工溯源，优先摘录该单一意见文书的支持性原句，"
        "不得拼接多个文书、删改否定词、剂量或数值，最长240字；normalized_action仅用于后续语义关联，"
        "允许source_quote和normalized_action作合理医学归一化，但不得虚构原文没有的建议。不要输出字符下标。"
        "意见不明确、无可执行建议或非普通会诊时recommendations必须为空数组。"
        "严格输出JSON对象：{episodes:[{episode_ref,member_refs,application_refs,opinion_refs,application_state,opinion_state,confidence,recommendations:[{recommendation_ref,opinion_ref,source_quote,normalized_action,action_type}]}],"
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
    documents_by_ref = {str(item["ref"]): item for item in documents}
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
        recommendations: list[_Recommendation] = []
        for number, raw_recommendation in enumerate(raw_recommendations, 1):
            if not isinstance(raw_recommendation, Mapping):
                raise _SemanticInvalid()
            recommendation_ref = _clean(raw_recommendation.get("recommendation_ref"))
            opinion_ref = _clean(raw_recommendation.get("opinion_ref"))
            action_type = _clean(raw_recommendation.get("action_type")).lower()
            source_quote = raw_recommendation.get("source_quote")
            normalized_action = raw_recommendation.get("normalized_action")
            if (
                recommendation_ref != f"{episode_ref}#r{number}"
                or opinion_ref not in opinion_refs
                or action_type not in _RECOMMENDATION_TYPES
                or not isinstance(source_quote, str)
                or not isinstance(normalized_action, str)
                or not source_quote.strip()
                or not normalized_action.strip()
                or len(source_quote) > _MAX_RECOMMENDATION_CHARS
                or len(normalized_action) > _MAX_RECOMMENDATION_CHARS
            ):
                raise _SemanticInvalid()
            recommendations.append(_Recommendation(
                recommendation_ref,
                action_type,
                source_quote,
                normalized_action,
                opinion_ref,
            ))
        if raw_recommendations and (opinion != "clear" or confidence != "high"):
            raise _SemanticInvalid()
        if application in {"vague", "missing", "unknown"} and _has_specific_application_purpose(
            application_refs=application_refs,
            documents_by_ref=documents_by_ref,
        ):
            application = "clear"
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


def _consultation_semantic_display_facts(
    *,
    rule_id: str,
    episodes: Sequence[_Episode],
    documents: Sequence[Mapping[str, str]],
) -> Mapping[str, Any]:
    """将021/022已裁决的episode事实投影为受控客户展示事实。"""

    is_application = rule_id == "LX0609-021"
    state_field = "application_state" if is_application else "opinion_state"
    ref_field = "application_refs" if is_application else "opinion_refs"
    relevant = tuple(
        episode
        for episode in episodes
        if getattr(episode, state_field) != "absent"
    )
    refs = tuple(
        dict.fromkeys(
            ref
            for episode in relevant
            for ref in getattr(episode, ref_field)
        )
    )
    documents_by_ref = {str(item.get("ref")): item for item in documents}
    states = {getattr(episode, state_field) for episode in relevant}
    semantic_state = (
        "absent"
        if not relevant
        else next(iter(states))
        if len(states) == 1
        else "mixed"
    )
    source_document_ids = [
        document_id
        for ref in refs
        if (document_id := _clean(documents_by_ref.get(ref, {}).get("document_id")))
    ]
    return {
        "verification_kind": (
            "consultation_application_quality_check"
            if is_application
            else "consultation_opinion_quality_check"
        ),
        "episode_count": len(relevant),
        "document_count": len(refs),
        "semantic_state": semantic_state,
        "checked_requirement": (
            "说明具体临床问题、会诊理由或明确会诊目的"
            if is_application
            else "给出针对当前病情的明确诊疗意见"
        ),
        "source_document_ids": list(dict.fromkeys(source_document_ids))[:8],
    }


def _consultation_execution_display_facts(
    *,
    status: str,
    episodes: Sequence[_Episode],
    completed_recommendations: Sequence[_CompletedRecommendation],
    assessments: Sequence[_ExecutionAssessment] | None,
    documents: Sequence[Mapping[str, str]],
) -> Mapping[str, Any]:
    """解释020为何已关联、缺失、未触发或暂不能关联。"""

    relation_by_status = {
        "compliant": "all_linked",
        "non_compliant": "execution_missing",
        "not_applicable": "not_triggered",
        "data_gap": "source_incomplete",
        "evaluation_unknown": "association_unresolved",
        "technical_error": "source_error",
    }
    opinion_refs = tuple(
        dict.fromkeys(
            ref
            for episode in episodes
            if episode.opinion_state == "clear" and episode.confidence == "high"
            for ref in episode.opinion_refs
        )
    )
    documents_by_ref = {str(item.get("ref")): item for item in documents}
    source_document_ids = [
        document_id
        for ref in opinion_refs
        if (document_id := _clean(documents_by_ref.get(ref, {}).get("document_id")))
    ]
    assessment_rows = tuple(assessments or ())
    return {
        "verification_kind": "consultation_execution_relation_check",
        "completed_opinion_episode_count": len(
            {
                episode.episode_ref
                for episode in episodes
                if episode.opinion_state == "clear" and episode.confidence == "high"
            }
        ),
        "recommendation_count": (
            len(completed_recommendations)
            or sum(len(episode.recommendations) for episode in episodes)
        ),
        "specific_execution_count": sum(
            item.execution_record_state == "specific_trace"
            for item in assessment_rows
        ),
        "generic_execution_count": sum(
            item.execution_record_state in {"generic_trace", "copied_opinion"}
            for item in assessment_rows
        ),
        "missing_execution_count": sum(
            item.execution_record_state == "no_trace" and not item.execution_refs
            for item in assessment_rows
        ),
        "relation_state": relation_by_status.get(status, "association_unresolved"),
        "source_document_ids": list(dict.fromkeys(source_document_ids))[:8],
    }


def _completed_recommendations(
    episodes: Sequence[_Episode],
    documents: Sequence[Mapping[str, str]],
    *,
    stay_window: _StayWindow | None,
) -> tuple[_CompletedRecommendation, ...]:
    by_ref = {str(item["ref"]): item for item in documents}
    completed: list[_CompletedRecommendation] = []
    for item in episodes:
        if (
            item.opinion_state != "clear"
            or item.confidence != "high"
            or not item.recommendations
        ):
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
        opinion_time = max(
            (value for value in observed_times if value is not None),
            key=lambda value: value.value,
        )
        completed.extend(
            _CompletedRecommendation(item.episode_ref, recommendation, opinion_time)
            for recommendation in item.recommendations
        )
    if len(completed) > _MAX_RECOMMENDATIONS:
        raise _SourceGap()
    return tuple(completed)


def _execution_prompt(
    *,
    completed: Sequence[_CompletedRecommendation],
    candidates: Sequence[_CandidateDocument],
) -> tuple[str, Mapping[str, frozenset[str]]]:
    entries: list[dict[str, object]] = []
    allowed_refs: dict[str, frozenset[str]] = {}
    for item in completed:
        related: list[dict[str, object]] = []
        eligible_sources = _ACTION_TYPE_SOURCE_KEYS.get(
            item.recommendation.action_type,
            frozenset((*_EXECUTION_SOURCE_KEYS, "inpat_nondrug_order")),
        )
        for candidate in candidates:
            if candidate.source_key not in eligible_sources:
                continue
            if candidate.observed_time.day > item.opinion_time.day:
                include = True
            elif candidate.observed_time.day < item.opinion_time.day:
                include = False
            elif candidate.observed_time.precise and item.opinion_time.precise:
                include = candidate.observed_time.value > item.opinion_time.value
            else:
                # 当前会诊规则按文书/医嘱/检查的自然日关联，不要求行级时分秒。
                # 同日但任一侧仅有日期时，不能由 Python 臆断先后；保留给 LLM
                # 仅做语义关联。唯有两侧均有精确时间且候选更早时才排除。
                include = True
            if include:
                related.append({
                    "ref": candidate.ref,
                    "source": candidate.source_key,
                    "date": candidate.observed_time.value.isoformat(),
                    "text": candidate.text,
                })
        allowed_refs[item.recommendation.recommendation_ref] = frozenset(
            str(candidate["ref"]) for candidate in related
        )
        entries.append({
            "recommendation_ref": item.recommendation.recommendation_ref,
            "action_type": item.recommendation.action_type,
            "source_quote": item.recommendation.source_quote,
            "normalized_action": item.recommendation.normalized_action,
            "opinion_date": item.opinion_time.value.isoformat(),
            "candidate_documents": related,
        })
    payload = json.dumps({"recommendations": entries}, ensure_ascii=False)
    if len(payload) > _MAX_PROMPT_CHARS:
        raise _SourceGap()
    prompt = (
        "你分两步判断每条会诊建议的后续落实，不得补充病历之外的信息。"
        "第一步先识别会诊后病程/查房中是否记录会诊意见及执行情况："
        "specific_trace=明确写出按会诊意见采取的具体措施；"
        "generic_trace=仅写遵会诊意见执行/已按建议处理等笼统表述；"
        "copied_opinion=照抄会诊意见、没有归纳执行情况；"
        "no_trace=未见请会诊执行记录痕迹；unknown=无法判断。"
        "第二步可辅助判断结构化医嘱/操作候选是否与该建议存在动作对应关系，"
        "但结构化匹配不是020或023的合规硬条件。"
        "同一执行文书可同时落实多条建议，禁止要求唯一归属。"
        "execution_state只描述结构化动作匹配：linked_specific=结构化候选明确落实同一条建议，"
        "linked_vague=结构化候选仅笼统相关，absent=无结构化动作匹配，unknown=无法判断。"
        "daily_course_record和senior_course_record只允许进入trace_refs，不能进入structured_action_refs；"
        "inpat_drug_order和inpat_nondrug_order只允许进入structured_action_refs。"
        "只有病程写“遵会诊意见执行”“已按建议处理”或具体动作、但无对应医嘱/检查/检验/手术/操作结构化记录时，"
        "execution_record_state按其具体程度填写，但execution_state必须输出absent。"
        "只有结构化医嘱/检查/检验/操作动作、没有病程/查房执行记录痕迹时，execution_record_state必须为no_trace。"
        "同一治疗类别的多个细项建议（例如同属康复训练的关节活动、肌力训练），"
        "若候选明确记载该治疗类别已经实施、但未逐项写明细项，可对每个细项输出linked_vague且confidence=high；"
        "这只适用于同一临床治疗类别，绝不得用一句泛化记录覆盖药物、检查、转运等跨类别建议。"
        "拟执行、计划执行、申请执行、请会诊、症状改善、无关治疗或同部位一般治疗都不是已经执行。"
        "confidence只能为high/medium/low。"
        "trace_refs和structured_action_refs只能引用该建议输入candidate_documents中的ref，绝不得引用会诊申请或会诊意见的ref。"
        "specific_trace/generic_trace/copied_opinion必须至少返回一个trace_refs；linked_specific或linked_vague必须至少返回一个structured_action_refs。"
        "没有可验证的candidate_documents ref时必须返回unknown。"
        "每个非空trace_refs或structured_action_refs都必须返回execution_quotes：每项是所引执行候选中的连续原文摘录，"
        "用于证明该候选真的支持你的关联；不得改写、拼接或引用未选候选。"
        "no_trace/absent组合必须返回空数组trace_refs、structured_action_refs和execution_quotes。"
        "每个输入recommendation_ref恰好输出一项，禁止重复。"
        "严格输出JSON：{executions:[{recommendation_ref,execution_record_state,trace_refs,execution_state,structured_action_refs,execution_quotes,confidence}]}。输入："
        + payload
    )
    return prompt, allowed_refs


def _parse_executions(
    payload: Mapping[str, Any],
    *,
    completed: Sequence[_CompletedRecommendation],
    allowed_refs: Mapping[str, frozenset[str]],
    candidates: Sequence[_CandidateDocument],
) -> tuple[_ExecutionAssessment, ...]:
    raw = payload.get("executions")
    expected_refs = {item.recommendation.recommendation_ref for item in completed}
    candidate_by_ref = {item.ref: item for item in candidates}
    if not isinstance(raw, list) or len(raw) != len(expected_refs):
        raise _SemanticInvalid()
    parsed: list[_ExecutionAssessment] = []
    seen: set[str] = set()
    for item in raw:
        if not isinstance(item, Mapping):
            raise _SemanticInvalid()
        recommendation_ref = _clean(item.get("recommendation_ref"))
        state = _clean(item.get("execution_state")).lower()
        original_state = state
        confidence = _clean(item.get("confidence")).lower()
        refs = item.get("execution_refs")
        raw_trace_refs = item.get("trace_refs")
        raw_structured_refs = item.get("structured_action_refs")
        raw_quotes = item.get("execution_quotes")
        execution_record_state = _clean(item.get("execution_record_state")).lower()
        if (
            recommendation_ref not in expected_refs
            or recommendation_ref in seen
            or state not in _EXECUTION_STATES
            or confidence not in _CONFIDENCE
            or (execution_record_state and execution_record_state not in _EXECUTION_RECORD_STATES)
            or (refs is not None and not isinstance(refs, list))
            or (raw_trace_refs is not None and not isinstance(raw_trace_refs, list))
            or (raw_structured_refs is not None and not isinstance(raw_structured_refs, list))
            or not isinstance(raw_quotes, list)
        ):
            raise _SemanticInvalid()
        refs = refs if isinstance(refs, list) else []
        trace_refs = raw_trace_refs if isinstance(raw_trace_refs, list) else []
        structured_refs = raw_structured_refs if isinstance(raw_structured_refs, list) else []
        if raw_trace_refs is None and raw_structured_refs is None:
            trace_refs = [
                ref
                for ref in refs
                if isinstance(ref, str)
                and ref in candidate_by_ref
                and candidate_by_ref[ref].source_key in _CONTEXT_ONLY_EXECUTION_SOURCE_KEYS
            ]
            structured_refs = [
                ref
                for ref in refs
                if isinstance(ref, str)
                and ref in candidate_by_ref
                and candidate_by_ref[ref].source_key in _STRUCTURED_EXECUTION_EVIDENCE_SOURCE_KEYS
            ]
            if trace_refs and not structured_refs and state in {"linked_specific", "linked_vague"}:
                state = "absent"
        all_refs = [*trace_refs, *structured_refs]
        if (
            len(trace_refs) != len(set(trace_refs))
            or len(structured_refs) != len(set(structured_refs))
            or len(all_refs) != len(set(all_refs))
            or not all(isinstance(ref, str) and ref in allowed_refs[recommendation_ref] for ref in all_refs)
            or not all(candidate_by_ref[ref].source_key in _CONTEXT_ONLY_EXECUTION_SOURCE_KEYS for ref in trace_refs)
            or not all(candidate_by_ref[ref].source_key in _STRUCTURED_EXECUTION_EVIDENCE_SOURCE_KEYS for ref in structured_refs)
            or (state in {"linked_specific", "linked_vague"} and not structured_refs)
            or (state in {"absent", "unknown"} and structured_refs)
        ):
            raise _SemanticInvalid()
        if not execution_record_state:
            if trace_refs and original_state == "linked_vague":
                execution_record_state = "generic_trace"
            elif trace_refs and original_state == "linked_specific":
                execution_record_state = "specific_trace"
            elif trace_refs:
                execution_record_state = "unknown"
            else:
                execution_record_state = "no_trace"
        if (
            execution_record_state in {"specific_trace", "generic_trace", "copied_opinion"} and not trace_refs
        ) or (
            execution_record_state in {"no_trace", "unknown"} and trace_refs
        ):
            raise _SemanticInvalid()
        quotes = tuple(_clean(quote) for quote in raw_quotes)
        if any(not quote or len(quote) > _MAX_RECOMMENDATION_CHARS for quote in quotes) or len(quotes) != len(set(quotes)):
            raise _SemanticInvalid()
        selected_documents = tuple(
            candidate_by_ref[ref] for ref in all_refs if ref in candidate_by_ref
        )
        if all_refs:
            if not quotes or any(
                not any(_quote_is_grounded(quote=quote, source=candidate.text) for candidate in selected_documents)
                for quote in quotes
            ):
                raise _SemanticInvalid()
        elif quotes:
            raise _SemanticInvalid()
        seen.add(recommendation_ref)
        parsed.append(_ExecutionAssessment(
            recommendation_ref,
            state,
            tuple(structured_refs),
            confidence,
            quotes,
            execution_record_state,
            tuple(trace_refs),
            tuple(trace_refs),
        ))
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
    completed_recommendations: Sequence[_CompletedRecommendation],
    assessments: Sequence[_ExecutionAssessment] | None,
    source_technical: bool = False,
    source_incomplete_keys: frozenset[str] = frozenset(),
    context_only_candidate_present: bool = False,
) -> tuple[str, str]:
    uncertain = any(
        item.confidence != "high" or item.opinion_state == "unknown"
        for item in episodes
    )
    completed = tuple(
        item for item in episodes
        if item.opinion_state == "clear" and item.confidence == "high"
    )
    if uncertain:
        return "evaluation_unknown", "semantic_low_confidence"
    if not completed or not completed_recommendations:
        return "not_applicable", "trigger_absent_complete"
    if source_technical:
        return "technical_error", "source_query_error"
    if assessments is None or any(
        item.confidence != "high"
        or item.execution_state == "unknown"
        or item.execution_record_state == "unknown"
        for item in assessments
    ):
        if source_technical:
            return "technical_error", "source_query_error"
        return "evaluation_unknown", "semantic_low_confidence"
    trace_states = tuple(item.execution_record_state for item in assessments)
    course_source_incomplete = bool(
        _COURSE_EXECUTION_SOURCE_KEYS.intersection(source_incomplete_keys)
    )
    complete_course_traces = all(
        item.execution_record_state in {"specific_trace", "generic_trace", "copied_opinion"}
        and bool(item.trace_refs)
        for item in assessments
    )
    no_course_trace_refs = {
        item.recommendation_ref
        for item in assessments
        if item.execution_record_state == "no_trace"
    }
    if rule_id == "LX0609-020":
        if no_course_trace_refs:
            if course_source_incomplete:
                return "data_gap", "candidate_scope_incomplete"
            if source_technical:
                return "technical_error", "source_query_error"
            return "non_compliant", "requirement_violated"
        if complete_course_traces:
            return "compliant", "requirement_satisfied"
        return "evaluation_unknown", "semantic_output_unknown"
    # 020 没有找到执行记录时，023 不重复判“无记录”；023 只评价已找到的
    # 执行病程是否笼统、照抄或已明确说明具体落实情况。
    if no_course_trace_refs:
        if course_source_incomplete:
            return "data_gap", "candidate_scope_incomplete"
        return "not_applicable", "trigger_absent_complete"
    if any(state in {"generic_trace", "copied_opinion"} for state in trace_states):
        return "non_compliant", "requirement_violated"
    if all(state == "specific_trace" for state in trace_states):
        return "compliant", "requirement_satisfied"
    if source_technical:
        return "technical_error", "source_query_error"
    return "evaluation_unknown", "semantic_output_unknown"


def _diagnostic_unknown_reason(
    *,
    assessment: _ExecutionAssessment | None,
    relevant_candidate_count: int,
    relevant_incomplete_keys: frozenset[str],
    source_technical: bool,
) -> str:
    if source_technical:
        return "source_query_error"
    if relevant_incomplete_keys:
        return "source_truncated"
    if assessment is None:
        return "candidate_missing" if relevant_candidate_count == 0 else "candidate_available_but_unlinked"
    if (
        assessment.confidence != "high"
        or assessment.execution_state == "unknown"
        or assessment.execution_record_state == "unknown"
    ):
        return "model_low_confidence"
    if assessment.execution_record_state == "no_trace" and not assessment.execution_refs:
        return "candidate_missing" if relevant_candidate_count == 0 else "candidate_available_but_unlinked"
    if assessment.execution_record_state == "no_trace" and assessment.execution_refs:
        return "structured_action_without_execution_trace"
    if assessment.execution_record_state in {"generic_trace", "copied_opinion"}:
        return "generic_execution_only"
    if assessment.execution_state == "linked_vague":
        return "generic_structured_action"
    return "linked"


def _diagnostic_link_state(
    *,
    assessment: _ExecutionAssessment | None,
    relevant_candidate_count: int,
    source_technical: bool,
) -> str:
    if source_technical:
        return "source_error"
    if assessment is None:
        return "no_candidate" if relevant_candidate_count == 0 else "ambiguous"
    if assessment.execution_record_state == "specific_trace":
        return "linked_specific"
    if assessment.execution_record_state in {"generic_trace", "copied_opinion"}:
        return "linked_vague"
    if assessment.execution_record_state == "no_trace" and assessment.execution_refs:
        return "structured_action_only"
    if assessment.execution_record_state == "no_trace":
        return "no_candidate" if relevant_candidate_count == 0 else "candidate_exists_unlinked"
    return "ambiguous"


def _link_diagnostics(
    *,
    completed_recommendations: Sequence[_CompletedRecommendation],
    projection: _CandidateProjection | None,
    assessments: Sequence[_ExecutionAssessment] | None,
    source_technical: bool,
) -> tuple[dict[str, Any], ...]:
    """输出安全诊断链，只解释 020/023 unknown 根因，不改变客户结论。"""

    candidates = tuple(projection.candidates) if projection is not None else ()
    incomplete_keys = projection.source_incomplete_keys if projection is not None else frozenset()
    assessments_by_ref = {
        item.recommendation_ref: item for item in assessments or ()
    }
    diagnostics: list[dict[str, Any]] = []
    for item in completed_recommendations:
        recommendation = item.recommendation
        # 020/023 的主核对对象固定为会诊后的病程/查房；医嘱等不能作为
        # “已记录执行情况”的替代来源，也不能主导资料缺口解释。
        relevant_source_keys = _COURSE_EXECUTION_SOURCE_KEYS
        required_source_keys = _COURSE_EXECUTION_SOURCE_KEYS
        relevant_candidates = tuple(
            candidate
            for candidate in candidates
            if candidate.source_key in relevant_source_keys
        )
        candidate_source_types = tuple(sorted({
            candidate.source_key for candidate in relevant_candidates
        }))
        relevant_incomplete_keys = frozenset(required_source_keys.intersection(incomplete_keys))
        assessment = assessments_by_ref.get(recommendation.recommendation_ref)
        link_state = _diagnostic_link_state(
            assessment=assessment,
            relevant_candidate_count=len(relevant_candidates),
            source_technical=source_technical,
        )
        unknown_reason = _diagnostic_unknown_reason(
            assessment=assessment,
            relevant_candidate_count=len(relevant_candidates),
            relevant_incomplete_keys=relevant_incomplete_keys,
            source_technical=source_technical,
        )
        diagnostics.append({
            "recommendation_ref": recommendation.recommendation_ref,
            "action_type": recommendation.action_type,
            "candidate_count": len(relevant_candidates),
            "candidate_source_types": candidate_source_types,
            "link_state": link_state,
            "unknown_reason": unknown_reason,
            "execution_record_state": (
                assessment.execution_record_state if assessment is not None else "unknown"
            ),
            "structured_action_count": (
                len(assessment.execution_refs) if assessment is not None else 0
            ),
            "source_incomplete_types": tuple(sorted(relevant_incomplete_keys)),
        })
    return tuple(diagnostics)


def _result(
    *,
    rule_id: str,
    status: str,
    reason_code: str,
    prompt_tokens: int,
    completion_tokens: int,
    total_tokens: int,
    link_diagnostics: Sequence[Mapping[str, Any]] = (),
) -> dict[str, Any]:
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
    if rule_id in {"LX0609-020", "LX0609-023"} and link_diagnostics:
        result["metadata"]["consultation_link_diagnostics"] = tuple(link_diagnostics)
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
            *_SNAPSHOT_EXECUTION_SOURCE_KEYS,
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


def _finish_explicit_statuses(
    *,
    selected: tuple[str, ...],
    statuses: Mapping[str, tuple[str, str]],
    documents: Sequence[Mapping[str, str]],
    execution_projection: _CandidateProjection | None,
    evidence_snapshot: Luxian0609EvidenceSnapshot | None,
    decision_rule_ids: frozenset[str],
) -> NativeConsultationEpisodeExecutionResult:
    results = []
    for rule_id in selected:
        status, reason_code = statuses[rule_id]
        item = _result(
            rule_id=rule_id,
            status=status,
            reason_code=reason_code,
            prompt_tokens=0,
            completion_tokens=0,
            total_tokens=0,
        )
        item["metadata"]["executor_type"] = "program"
        if rule_id not in decision_rule_ids:
            results.append(item)
    decisions = tuple(
        _decision(
            rule_id=rule_id,
            status=statuses[rule_id][0],
            reason_code=statuses[rule_id][1],
            snapshot=evidence_snapshot,
        )
        for rule_id in selected
        if rule_id in decision_rule_ids and evidence_snapshot is not None
    )
    source_document_ids = tuple(
        dict.fromkeys(
            document_id
            for item in documents
            if (document_id := _clean(item.get("document_id")))
        )
    )
    display_facts: list[tuple[str, Mapping[str, Any]]] = []
    for rule_id in selected:
        status = statuses[rule_id][0]
        facts: dict[str, Any] = {
            "source_document_ids": list(source_document_ids),
            "consultation_assessment": "明确" if status == "compliant" else "不符合要求",
        }
        if rule_id == "LX0609-020":
            facts["execution_record_state"] = (
                "已发现明确执行记录" if status == "compliant" else "未发现执行记录"
            )
            facts["execution_candidate_count"] = (
                len(execution_projection.candidates)
                if execution_projection is not None
                else 0
            )
        display_facts.append((rule_id, facts))
    return NativeConsultationEpisodeExecutionResult(
        results=tuple(results),
        planned_rule_ids=selected,
        decisions=decisions,
        customer_display_facts=tuple(display_facts),
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
    if _documents_are_explicit_non_target(documents):
        return _finish(
            selected=selected,
            status="not_applicable",
            reason_code="eligibility_not_met",
            evidence_snapshot=evidence_snapshot,
            decision_rule_ids=typed,
        )
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
        # 住院窗口仅是020/023的关联前提。即使窗口缺失或读取异常，021/022
        # 仍须继续基于会诊申请、会诊意见本身完成独立文书内容判定。
        if stage_two_boundary_status is not None and not any(
            rule_id in {"LX0609-021", "LX0609-022"}
            for rule_id in selected
        ):
            return _finish(
                selected=selected,
                status=stage_two_boundary_status[0],
                reason_code=stage_two_boundary_status[1],
                evidence_snapshot=evidence_snapshot,
                decision_rule_ids=typed,
            )
    explicit_execution_projection: _CandidateProjection | None = None
    if "LX0609-020" in stage_two_rule_ids and execution_stay_window is not None:
        explicit_execution_projection = _candidate_documents(
            institute_id=institute_id,
            patient_id=patient_id,
            visit_id=visit_id,
            source_schema=source_schema,
            evidence_materials=evidence_materials,
            evidence_snapshot=evidence_snapshot,
            stay_window=execution_stay_window,
        )
    explicit_statuses = _strong_explicit_consultation_statuses(
        selected=selected,
        documents=documents,
        execution_projection=explicit_execution_projection,
    )
    if all(rule_id in explicit_statuses for rule_id in selected):
        return _finish_explicit_statuses(
            selected=selected,
            statuses=explicit_statuses,
            documents=documents,
            execution_projection=explicit_execution_projection,
            evidence_snapshot=evidence_snapshot,
            decision_rule_ids=typed,
        )
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
    execution_source_technical = False
    execution_source_incomplete_keys: frozenset[str] = frozenset()
    context_only_candidate_present = False
    execution_candidate_projection: _CandidateProjection | None = None
    completed_recommendations: tuple[_CompletedRecommendation, ...] = ()
    if stage_two_rule_ids:
        if stage_two_boundary_status is not None:
            for rule_id in stage_two_rule_ids:
                statuses[rule_id] = stage_two_boundary_status
            completed_recommendations = ()
        else:
            try:
                completed_recommendations = _completed_recommendations(
                    episodes,
                    documents,
                    stay_window=execution_stay_window,
                )
            except _SourceGap:
                completed_recommendations = ()
                for rule_id in stage_two_rule_ids:
                    statuses[rule_id] = ("data_gap", "linkage_unresolved")
            except _SemanticInvalid:
                completed_recommendations = ()
                for rule_id in stage_two_rule_ids:
                    statuses[rule_id] = ("evaluation_unknown", "semantic_output_unknown")
        if not any(rule_id in statuses for rule_id in stage_two_rule_ids):
            preliminary = _execution_outcome(
                "LX0609-020",
                episodes=episodes,
                completed_recommendations=completed_recommendations,
                assessments=None,
            )
            if preliminary[0] == "not_applicable":
                for rule_id in stage_two_rule_ids:
                    statuses[rule_id] = ("not_applicable", "trigger_absent_complete")
            elif completed_recommendations:
                projection = _candidate_documents(
                    institute_id=institute_id,
                    patient_id=patient_id,
                    visit_id=visit_id,
                    source_schema=source_schema,
                    evidence_materials=evidence_materials,
                    evidence_snapshot=evidence_snapshot,
                    stay_window=execution_stay_window,
                )
                execution_candidate_projection = projection
                execution_source_technical = projection.source_technical
                execution_source_incomplete_keys = projection.source_incomplete_keys
                context_only_candidate_present = any(
                    item.source_key in _CONTEXT_ONLY_EXECUTION_SOURCE_KEYS
                    for item in projection.candidates
                )
                if execution_source_technical:
                    for rule_id in stage_two_rule_ids:
                        statuses[rule_id] = ("technical_error", "source_query_error")
                elif (
                    _COURSE_EXECUTION_SOURCE_KEYS.intersection(
                        projection.source_incomplete_keys
                    )
                    and not any(
                        item.source_key in _COURSE_EXECUTION_SOURCE_KEYS
                        for item in projection.candidates
                    )
                ):
                    # 没有任何可核对的后续病程时，病程来源的截断、不可用或
                    # 行级时间/正文缺失不能由医嘱补足。已有可定位病程痕迹时，
                    # 则交由受控事实判断其是否已充分支持正向结论。
                    for rule_id in stage_two_rule_ids:
                        statuses[rule_id] = (
                            "data_gap",
                            "candidate_scope_incomplete",
                        )
                elif not projection.candidates:
                    # 候选因截断、超限、无权威时间或正文预算而无法投给模型时，
                    # 不是模型的 absent 结论，必须单列为资料不足。反之，已成功
                    # 查询且本次住院窗口内确无后续候选时，才可作为未观察到执行。
                    execution_assessments = tuple(
                        _ExecutionAssessment(
                            item.recommendation.recommendation_ref,
                            "absent",
                            (),
                            "high",
                            (),
                            "no_trace",
                            (),
                            (),
                        )
                        for item in completed_recommendations
                    )
                else:
                    try:
                        second_prompt, allowed_refs = _execution_prompt(
                            completed=completed_recommendations,
                            candidates=projection.candidates,
                        )
                    except _SourceGap:
                        for rule_id in stage_two_rule_ids:
                            statuses[rule_id] = (
                                "evaluation_unknown",
                                "candidate_scope_incomplete",
                            )
                        second_prompt = ""
                        allowed_refs = {}
                    if not any(allowed_refs.values()):
                        if not any(rule_id in statuses for rule_id in stage_two_rule_ids):
                            execution_assessments = tuple(
                                _ExecutionAssessment(
                                    item.recommendation.recommendation_ref,
                                    "absent",
                                    (),
                                    "high",
                                    (),
                                    "no_trace",
                                    (),
                                    (),
                                )
                                for item in completed_recommendations
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
                                _payload(response),
                                completed=completed_recommendations,
                                allowed_refs=allowed_refs,
                                candidates=projection.candidates,
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
                    statuses[rule_id] = _execution_outcome(
                        rule_id,
                        episodes=episodes,
                        completed_recommendations=completed_recommendations,
                        assessments=None,
                    )
        if execution_assessments is not None:
            for rule_id in stage_two_rule_ids:
                statuses[rule_id] = _execution_outcome(
                    rule_id,
                    episodes=episodes,
                    completed_recommendations=completed_recommendations,
                    assessments=execution_assessments,
                    source_technical=execution_source_technical,
                    source_incomplete_keys=execution_source_incomplete_keys,
                    context_only_candidate_present=context_only_candidate_present,
                )
    link_diagnostics = _link_diagnostics(
        completed_recommendations=completed_recommendations,
        projection=execution_candidate_projection,
        assessments=execution_assessments,
        source_technical=execution_source_technical,
    )
    results = []
    for rule_id in selected:
        status, reason = statuses.get(rule_id, ("data_gap", "linkage_unresolved"))
        results.append(_result(
            rule_id=rule_id,
            status=status,
            reason_code=reason,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
            link_diagnostics=link_diagnostics,
        ))
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
    display_facts: list[tuple[str, Mapping[str, Any]]] = []
    for rule_id in ("LX0609-021", "LX0609-022"):
        if rule_id in selected and rule_id in statuses:
            display_facts.append(
                (
                    rule_id,
                    _consultation_semantic_display_facts(
                        rule_id=rule_id,
                        episodes=episodes,
                        documents=documents,
                    ),
                )
            )
    if "LX0609-020" in selected and "LX0609-020" in statuses:
        display_facts.append(
            (
                "LX0609-020",
                _consultation_execution_display_facts(
                    status=statuses["LX0609-020"][0],
                    episodes=episodes,
                    completed_recommendations=completed_recommendations,
                    assessments=execution_assessments,
                    documents=documents,
                ),
            )
        )
    return NativeConsultationEpisodeExecutionResult(
        results=tuple(item for item in results if item["rule_id"] not in typed), planned_rule_ids=selected,
        decisions=decisions, customer_display_facts=tuple(display_facts),
        llm_call_count=calls,
        prompt_tokens=prompt_tokens, completion_tokens=completion_tokens,
        total_tokens=total_tokens, api_time=api_time,
    )
