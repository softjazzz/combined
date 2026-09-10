"""LX0609-020 至 023 的两阶段会诊 episode 原生执行器。

第一阶段只聚合本次住院的真实会诊 episode；第二阶段仅对高置信、
意见明确的 episode 批量判断后续执行关联，禁止行级唯一归属推断。
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import date, datetime
from enum import Enum
import httpx
import json
import logging
from pathlib import Path
import re
import time
import traceback
import unicodedata
from typing import Any, Mapping, Protocol, Sequence

from .consultation_decision_evidence import (
    bind_document_material_rows,
    is_material_binding_error,
    material_refs_for_internal_refs,
    select_consultation_rule_material_refs,
)
from .consultation_customer_projection import (
    is_consultation_customer_rule,
    safe_consultation_customer_display_facts,
)
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


logger = logging.getLogger(__name__)


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
# 真实 29 个独立会诊事件、62 条建议和 67 份病程候选的共享投影为
# 52,485 字符。第二阶段不重复候选正文后使用独立 64k 防御上限，避免
# 把常见完整长住院资料误报为候选范围不完整。
_MAX_EXECUTION_PROMPT_CHARS = 64000
_MAX_EPISODES = 12
_MAX_EPISODE_OPINION_CHARS = 1200
# 单份意见保留防御上限；整份长住院病例可包含多次独立会诊，不能把
# “单文书建议数”和“全病历建议数”混成一个阈值而误报关联缺失。
_MAX_RECOMMENDATIONS_PER_EPISODE = 12
_MAX_TOTAL_RECOMMENDATIONS = 96
_MAX_RECOMMENDATION_CHARS = 240
# 病程是 4.20.4 的主执行证据。完整 Snapshot 中真实病程常超过 12 份，
# 单份上级查房记录也常超过 1000 字；不能因为展示/提示词投影上限把整类
# 权威病程误判为不完整。提示词在第二阶段按引用去重，硬上限仅防御异常巨行。
_MAX_CANDIDATE_CHARS = 5000
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
    "exam_master",
    "exam_item_report",
    "labtest_master",
    "labtest_item_report",
    "surgery_record",
)
_SNAPSHOT_EXECUTION_SOURCE_KEYS = _EXECUTION_SOURCE_KEYS
_COURSE_EXECUTION_SOURCE_KEYS = frozenset((
    "daily_course_record",
    "senior_course_record",
))
_CONTEXT_ONLY_EXECUTION_SOURCE_KEYS = frozenset((
    *_COURSE_EXECUTION_SOURCE_KEYS,
    "consultation_record",
))
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
        "exam_master", "exam_item_report", "labtest_master", "labtest_item_report",
    )),
    "procedure": frozenset((
        "inpat_nondrug_order", "daily_course_record", "senior_course_record", "surgery_record",
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
# consultation_record 的真实正文常用“会诊后指出：”承载完整意见，
# 不一定包含“会诊意见”字段标签。仅在同一段同时出现明确诊疗动作/结论时
# 作为高置信正向事实；泛化“必要时/酌情”仍由下方模糊模式优先拦截。
_EXPLICIT_EMBEDDED_OPINION_CLEAR_PATTERN = re.compile(
    r"(?:会诊后(?:指出|建议|认为)|会诊(?:医师|医生)?(?:指出|建议|认为))"
    r".{0,220}(?:考虑|诊断|建议|继续|予以|给予|调整|停用|改用|加用|"
    r"复查|随访|治疗|监测|用药|检查|检验)"
)
_EXPLICIT_EXECUTION_TRACE_PATTERN = re.compile(
    r"(?:已归纳.{0,12}会诊意见|执行会诊意见|按(?:会诊)?建议|"
    r"根据会诊意见|落实会诊意见|按意见.{0,12}(?:执行|处理|治疗))"
)
_EXPLICIT_COMPLETED_ACTION_PATTERN = re.compile(
    r"(?:已(?:安排|完成|给予|实施|行)|予以|给予|实施|完成|冰敷|石膏固定|观察末梢循环)"
)
_EMBEDDED_DECISION_COMMUNICATION_PATTERN = re.compile(
    r"(?:(?:已|经).{0,8})?(?:与)?(?:患者(?:家属)?|家属).{0,8}(?:沟通|告知|说明)"
)
_EMBEDDED_DECISION_DEFER_PATTERN = re.compile(
    r"(?:患者|家属).{0,16}(?:拒绝|不同意|暂不|暂缓|放弃|决定不|要求不)"
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
_GENERIC_LABELLED_APPLICATION_PURPOSE_PATTERN = re.compile(
    r"^(?:会诊申请单(?:\([^)]*\)|（[^）]*）)?[；;])?"
    r"(?:会诊目的[:：])?请(?:相关)?(?:专科|科室)?"
    r"(?:协助)?(?:评估|诊治|处理)(?:并提出(?:诊疗)?(?:建议|意见))?[。.]?$"
)
_GENERIC_OPINION_PATTERN = re.compile(
    r"^(?:会诊记录单(?:\([^)]*\)|（[^）]*）)?[；;])?"
    r"(?:会诊意见[:：])?建议(?:继续)?(?:监测|观察)病情(?:变化)?"
    r"[，,；;]?(?:结合|根据)(?:相关)?检查结果(?:酌情|视情况)?"
    r"(?:调整|继续)(?:诊疗|治疗)方案[。.]?$"
)
_NO_SPECIAL_TREATMENT_DECISION_PATTERN = re.compile(
    r"(?:目前|当前|现阶段)?(?:我科)?(?:暂无|无需|无须)"
    r"(?:特殊|特别|进一步)?(?:处理|治疗|处置)"
)
_DYNAMIC_ECG_FOLLOW_UP_PATTERN = re.compile(
    r"(?:建议|可|必要时)[^。；]{0,48}"
    r"(?:复查|再次完善|重新完善|进一步完善|完善)"
    r"(?:24小时|二十四小时)?动态心电图"
)
_SAFE_EXCEPTION_ORIGIN_PART = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


class ConsultationEpisodeLLMClient(Protocol):
    async def generate(self, prompt: str) -> dict[str, Any]: ...


def _is_retryable_execution_transport_failure(error: Exception) -> bool:
    """仅识别第二阶段可安全重试一次的瞬时上游失败。"""

    if isinstance(error, (httpx.TransportError, httpx.TimeoutException)):
        return True
    status_match = re.search(r"\bupstream_http_status=(\d{3})\b", str(error))
    if status_match is None:
        return False
    return 500 <= int(status_match.group(1)) <= 599


def _stage_two_failure_kind(error: Exception) -> str:
    """将二阶段模型异常收敛为安全枚举，绝不将原始异常写入日志。"""

    if isinstance(error, httpx.TimeoutException):
        return "timeout"
    status_match = re.search(r"\bupstream_http_status=(\d{3})\b", str(error))
    if status_match is not None:
        status_code = int(status_match.group(1))
        if status_code == 429:
            return "upstream_429"
        if 500 <= status_code <= 599:
            return "upstream_5xx"
    if isinstance(error, httpx.TransportError):
        return "http_transport"
    normalized = str(error).lower()
    if any(marker in normalized for marker in (
        "not configured",
        "configuration",
        "missing api key",
        "missing endpoint",
    )):
        return "configuration"
    return "unclassified"


def _stage_two_exception_module(error: Exception) -> str:
    """日志仅保留受控模块分类，禁止把异常上下文带出。"""

    module = type(error).__module__.partition(".")[0]
    if module in {"httpx", "asyncio", "builtins", "aiohttp"}:
        return module
    return "other"


def _stage_two_exception_origin(error: Exception) -> str:
    """从 traceback 最末帧提取脱敏来源；不记录路径、行号或源码。"""

    if error.__traceback__ is None:
        return "unknown"
    frames = traceback.extract_tb(error.__traceback__)
    if not frames:
        return "unknown"
    frame = frames[-1]
    module_basename = Path(frame.filename).stem
    function_name = frame.name
    if not (
        _SAFE_EXCEPTION_ORIGIN_PART.fullmatch(module_basename)
        and _SAFE_EXCEPTION_ORIGIN_PART.fullmatch(function_name)
    ):
        return "unknown"
    return f"{module_basename}:{function_name}"


@dataclass(frozen=True)
class NativeConsultationEpisodeExecutionResult:
    results: tuple[dict[str, Any], ...]
    planned_rule_ids: tuple[str, ...]
    decisions: tuple[RuleDecision, ...] = ()
    customer_display_facts: tuple[tuple[str, Mapping[str, Any]], ...] = ()
    diagnostic_semantic_snapshot: Mapping[str, Any] | None = None
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


def _merge_rechecked_execution_assessment(
    original: _ExecutionAssessment,
    rechecked: _ExecutionAssessment,
) -> _ExecutionAssessment:
    """复核结果优先；两次独立均确认无执行痕迹时可收敛信心。"""

    if rechecked.confidence == "high":
        return rechecked
    if (
        original.execution_record_state == "no_trace"
        and rechecked.execution_record_state == "no_trace"
        and original.execution_state == "absent"
        and rechecked.execution_state == "absent"
        and not original.trace_refs
        and not rechecked.trace_refs
        and not original.execution_refs
        and not rechecked.execution_refs
    ):
        # 不从关键词推断“未执行”；只在两次受控语义核对对
        # 同一建议给出完全一致的 no_trace/absent 事实时收敛。
        return replace(rechecked, confidence="high")
    return rechecked


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
    document_id: str = ""
    material_ref: str = ""


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


class _SemanticInvalidKind(str, Enum):
    OTHER = "other"
    RESPONSE_SHAPE = "response_shape"
    RECOMMENDATION_IDENTITY = "recommendation_identity"
    REFERENCE_SHAPE = "reference_shape"
    REFERENCE_NOT_CANDIDATE = "reference_not_candidate"
    COVERAGE_INCOMPLETE = "coverage_incomplete"


class _SemanticInvalid(Exception):
    def __init__(
        self,
        kind: _SemanticInvalidKind = _SemanticInvalidKind.OTHER,
    ) -> None:
        super().__init__(kind.value)
        self.kind = kind

    @property
    def retryable_stage_two_once(self) -> bool:
        return self.kind in {
            _SemanticInvalidKind.RESPONSE_SHAPE,
            _SemanticInvalidKind.REFERENCE_NOT_CANDIDATE,
        }


class _ExecutionCoverageIncomplete(_SemanticInvalid):
    """二阶段结构合法，但遗漏了部分既定建议。"""

    def __init__(
        self,
        *,
        parsed: tuple[_ExecutionAssessment, ...],
        missing_refs: frozenset[str],
    ) -> None:
        super().__init__(_SemanticInvalidKind.COVERAGE_INCOMPLETE)
        self.parsed = parsed
        self.missing_refs = missing_refs


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
    if not text or (
        _GENERIC_APPLICATION_PURPOSE_PATTERN.fullmatch(text)
        or _GENERIC_LABELLED_APPLICATION_PURPOSE_PATTERN.fullmatch(text)
    ):
        return False
    return bool(_SPECIFIC_APPLICATION_PURPOSE_PATTERN.search(text))


def _opinion_is_only_generic(
    *,
    opinion_refs: Sequence[str],
    documents_by_ref: Mapping[str, Mapping[str, str]],
) -> bool:
    """锁定只有泛化监测/调整措辞的意见，避免模型把它升级为明确意见。"""

    texts = [
        _clean((documents_by_ref.get(ref) or {}).get("text"))
        for ref in opinion_refs
    ]
    text = _evidence_text("；".join(item for item in texts if item))
    return bool(text and _GENERIC_OPINION_PATTERN.fullmatch(text))


def _stabilize_explicit_opinion_state(
    *,
    opinion_state: str,
    opinion_refs: Sequence[str],
    documents_by_ref: Mapping[str, Mapping[str, str]],
) -> str:
    """同一意见原文已有明确处理决定和具体复查时，稳定 022 模型抖动。"""

    if opinion_state not in {"vague", "missing", "unknown"}:
        return opinion_state
    for ref in opinion_refs:
        text = _evidence_text(_clean((documents_by_ref.get(ref) or {}).get("text")))
        if (
            _NO_SPECIAL_TREATMENT_DECISION_PATTERN.search(text)
            and _DYNAMIC_ECG_FOLLOW_UP_PATTERN.search(text)
        ):
            return "clear"
    return opinion_state


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
            material_rows = evidence_materials.bounded_rows(source_key)
            # `material_ref` 只在本次请求内连接匿名 Prompt 引用与冻结材料。
            # 它绝不进入 Prompt；只有完整且已由 snapshot 证明的来源才能产出。
            if observation.completeness is SourceCompleteness.COMPLETE:
                try:
                    rows = bind_document_material_rows(
                        source_key=source_key,
                        rows=material_rows,
                        materials=evidence_materials,
                        snapshot=evidence_snapshot,
                    )
                except Exception as exc:
                    # 会诊正文和后续病程会被交付为客户证据；材料与 snapshot
                    # 无法证明同源时，绝不能继续用无引用行得出确定结论。
                    if (
                        is_material_binding_error(exc)
                        and (source_key == _SOURCE_KEY or source_key in _COURSE_EXECUTION_SOURCE_KEYS)
                    ):
                        raise _SourceTechnical()
                    if not is_material_binding_error(exc):
                        raise
                    rows = [dict(row) for row in material_rows]
            else:
                rows = [dict(row) for row in material_rows]
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
    projected: list[tuple[dict[str, str], frozenset[str]]] = []
    for index, row in enumerate(rows, start=1):
        body = _clean(row.get("record_content"))
        if _is_pure_signature_template(body):
            continue
        text = _clean("；".join(
            value for value in (_clean(row.get("document_title")), body) if value
        ))
        if len(text) > _MAX_DOCUMENT_CHARS:
            raise _SourceGap()
        business_tokens = frozenset(
            token
            for prefix, value in (
                ("consultation", _clean(row.get("consultation_id"))),
                ("application", _clean(row.get("application_id"))),
            )
            if value
            for token in (f"{prefix}:{value}",)
        )
        document_id = _clean(row.get("document_id"))
        event_identity_mode = "business" if business_tokens else "semantic"
        # document_id 只定位文书，不能证明不同文书属于不同会诊事件。
        # 缺少会诊/申请业务键时沿用语义归并及不确定口径，不能按行数计次。
        projected.append(({
            "ref": f"{_SOURCE_KEY}-{index}",
            "document_id": document_id,
            "material_ref": _clean(row.get("_material_document_ref")),
            "time": _clean(row.get("record_time")),
            "text": text,
            "event_identity_mode": event_identity_mode,
        }, business_tokens))

    # consultation_id/application_id 是同一事件的别名。先在 Python 内做并查集，
    # 再只把本次请求内的序号 event_group_ref 交给模型，避免业务键出境，
    # 同时禁止模型跨业务键合并或拆分文书。
    parents = list(range(len(projected)))

    def _root(index: int) -> int:
        while parents[index] != index:
            parents[index] = parents[parents[index]]
            index = parents[index]
        return index

    def _union(left: int, right: int) -> None:
        left_root, right_root = _root(left), _root(right)
        if left_root != right_root:
            parents[right_root] = left_root

    token_owner: dict[str, int] = {}
    for index, (_, tokens) in enumerate(projected):
        for token in tokens:
            prior = token_owner.setdefault(token, index)
            _union(index, prior)

    component_tokens: dict[int, set[str]] = {}
    for index, (_, tokens) in enumerate(projected):
        component_tokens.setdefault(_root(index), set()).update(tokens)
    component_labels = {
        root: label
        for label, root in enumerate(sorted(component_tokens), start=1)
    }

    documents: list[dict[str, str]] = []
    for index, (document, tokens) in enumerate(projected):
        event_group_ref = ""
        if tokens:
            event_group_ref = f"consultation-event-{component_labels[_root(index)]}"
        documents.append({**document, "event_group_ref": event_group_ref})
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
    elif source_key in _COURSE_EXECUTION_SOURCE_KEYS:
        # 与病程质量规则共用同一权威时间口径：优先正式记录时间，客户CDM
        # 未回传该字段时使用提交时间；不从正文、同步时间或文件顺序猜测。
        time_keys = (
            "record_time",
            "record_datetime",
            "submit_time",
            "submit_datetime",
        )
    elif source_key in {"exam_master", "exam_item_report"}:
        # 检查执行的时序优先取实际检查时间；申请时间不能替代已实施检查，
        # report/record_time 也可能只是报告或同步归档时间。
        time_keys = (
            "exam_time",
            "exam_datetime",
            "report_time",
            "report_datetime",
            "request_time",
            "request_datetime",
        )
    elif source_key in {"labtest_master", "labtest_item_report"}:
        # 检验以报告/申请等明确业务事件为准，禁止把本地同步 record_time
        # 当成会诊后执行时间，避免把既往检验错纳入本次关联。
        time_keys = (
            "report_datetime",
            "report_time",
            "request_datetime",
            "request_time",
        )
    elif source_key == "surgery_record":
        # 手术记录通常在术后补写，020/023 的执行时序必须按实际手术开始，
        # 而不是文书提交/归档时间。
        time_keys = (
            "surgery_begin_time",
            "surgery_begin_datetime",
            "surgery_end_time",
            "surgery_end_datetime",
            "record_time",
            "record_datetime",
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


def _candidate_document_id(*, row: Mapping[str, Any], source_key: str) -> str:
    """只使用来源自身稳定业务键作为定位证据，禁止从正文或行号构造 ID。"""

    identity_fields = {
        "inpat_drug_order": ("order_id", "application_id", "document_id"),
        "inpat_nondrug_order": ("order_id", "application_id", "document_id"),
        "exam_master": ("document_id", "exam_id"),
        "exam_item_report": ("document_id", "exam_id"),
        "labtest_master": ("document_id", "test_id"),
        "labtest_item_report": ("document_id", "test_id"),
        "surgery_record": ("document_id",),
    }
    return next(
        (
            candidate
            for field in identity_fields.get(source_key, ("document_id",))
            if (candidate := _clean(row.get(field)))
        ),
        "",
    )


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
    preloaded_course_rows: dict[str, tuple[str, Sequence[Mapping[str, Any]]]] = {}
    for source_key in source_keys:
        if source_key not in _COURSE_EXECUTION_SOURCE_KEYS:
            continue
        try:
            rows = _read_rows(
                source_key=source_key,
                institute_id=institute_id,
                patient_id=patient_id,
                visit_id=visit_id,
                source_schema=source_schema,
                evidence_materials=evidence_materials,
                evidence_snapshot=evidence_snapshot,
                allow_truncated=False,
            )
        except _SourceGap:
            preloaded_course_rows[source_key] = ("gap", ())
        except _SourceTechnical:
            preloaded_course_rows[source_key] = ("technical", ())
        else:
            preloaded_course_rows[source_key] = ("ok", rows)

    course_document_times: dict[str, _ObservedTime] = {}
    conflicting_course_document_times: set[str] = set()
    for source_key, (state, rows) in preloaded_course_rows.items():
        if state != "ok":
            continue
        for row in rows:
            document_id = _clean(row.get("document_id"))
            observed_time = _row_time(row, source_key=source_key)
            if not document_id or observed_time is None:
                continue
            existing = course_document_times.get(document_id)
            if existing is not None and existing != observed_time:
                conflicting_course_document_times.add(document_id)
                course_document_times.pop(document_id, None)
            elif document_id not in conflicting_course_document_times:
                course_document_times[document_id] = observed_time

    for source_key in source_keys:
        is_order_source = source_key in _ORDER_EXECUTION_SOURCE_KEYS
        if source_key in preloaded_course_rows:
            read_state, rows = preloaded_course_rows[source_key]
            if read_state == "gap":
                source_incomplete_keys.add(source_key)
                continue
            if read_state == "technical":
                source_technical = True
                continue
        else:
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
        source_limit = _MAX_ORDER_CANDIDATES_PER_SOURCE
        if is_order_source and len(rows) > source_limit:
            # 医嘱是 020/023 的辅助执行证据，真实病例中常为高频清单。
            # 这里采用会诊后时间排序的固定上限候选集，避免“医嘱很多”
            # 本身把所有建议都拖成资料不足；行级缺时间/缺内容仍会在
            # 下方标记为来源不完整。
            rows = rows[:source_limit]
        for index, row in enumerate(rows, start=1):
            observed_time = _row_time(row, source_key=source_key)
            text = _candidate_text(row=row, source_key=source_key)
            if observed_time is None and source_key in _COURSE_EXECUTION_SOURCE_KEYS:
                document_id = _clean(row.get("document_id"))
                observed_time = course_document_times.get(document_id)
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
            if not text and source_key in _COURSE_EXECUTION_SOURCE_KEYS:
                # 无标题、无正文的病程占位行不可能承载会诊执行事实；忽略该
                # 空工件，不能仅因它同时缺时间就把完整病程来源降为不完整。
                continue
            if observed_time is None or not text or len(text) > text_limit:
                source_is_complete = False
                continue
            candidates.append(_CandidateDocument(
                ref=f"{source_key}-{index}",
                source_key=source_key,
                observed_time=observed_time,
                text=text,
                document_id=_candidate_document_id(row=row, source_key=source_key),
                material_ref=_clean(row.get("_material_document_ref")),
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


def _explicit_embedded_opinion_documents(
    documents: Sequence[Mapping[str, str]],
) -> tuple[Mapping[str, str], ...]:
    """返回全部正文均可直接证明意见明确的会诊文书。"""

    embedded_opinions = tuple(
        item
        for item in documents
        if _EXPLICIT_EMBEDDED_OPINION_CLEAR_PATTERN.search(
            _evidence_text(_clean(item.get("text")))
        )
        and not _EXPLICIT_OPINION_VAGUE_PATTERN.search(
            _evidence_text(_clean(item.get("text")))
        )
    )
    if embedded_opinions and len(embedded_opinions) == len(documents):
        return embedded_opinions
    return ()


def _strong_explicit_consultation_statuses(
    *,
    selected: Sequence[str],
    documents: Sequence[Mapping[str, str]],
    execution_projection: _CandidateProjection | None,
    decision_document_refs: dict[str, tuple[str, ...]] | None = None,
) -> dict[str, tuple[str, str]]:
    """只处理文书角色和结论均显式的高置信会诊场景。"""

    request_documents = tuple(
        item for item in documents if "会诊申请" in _clean(item.get("text"))
    )
    opinion_documents = tuple(
        item for item in documents if "会诊意见" in _clean(item.get("text"))
    )
    if len(request_documents) != 1 or len(opinion_documents) != 1:
        # consultation_record 的源字段本身就是会诊正文，真实数据常不带
        # “会诊申请/会诊意见”标签。仅对每份正文都明确包含“会诊后指出/建议”
        # 及具体诊疗动作的场景短路，避免让模型把明确意见误降级为 vague。
        if (
            "LX0609-022" in selected
            and _explicit_embedded_opinion_documents(documents)
        ):
            if decision_document_refs is not None:
                decision_document_refs["LX0609-022"] = tuple(
                    _clean(item.get("ref"))
                    for item in documents
                    if _clean(item.get("ref"))
                )
            return {"LX0609-022": ("compliant", "requirement_satisfied")}
        return {}

    statuses: dict[str, tuple[str, str]] = {}
    request_text = _clean(request_documents[0].get("text"))
    opinion_text = _clean(opinion_documents[0].get("text"))
    if "LX0609-021" in selected:
        if _EXPLICIT_REQUEST_VAGUE_PATTERN.fullmatch(request_text):
            statuses["LX0609-021"] = ("non_compliant", "requirement_violated")
        elif _EXPLICIT_REQUEST_CLEAR_PATTERN.search(request_text):
            statuses["LX0609-021"] = ("compliant", "requirement_satisfied")
        if "LX0609-021" in statuses and decision_document_refs is not None:
            decision_document_refs["LX0609-021"] = tuple(
                _clean(item.get("ref")) for item in request_documents
                if _clean(item.get("ref"))
            )
    if "LX0609-022" in selected:
        if _EXPLICIT_OPINION_VAGUE_PATTERN.search(opinion_text):
            statuses["LX0609-022"] = ("non_compliant", "requirement_violated")
        elif _EXPLICIT_OPINION_CLEAR_PATTERN.search(opinion_text):
            statuses["LX0609-022"] = ("compliant", "requirement_satisfied")
        if "LX0609-022" in statuses and decision_document_refs is not None:
            decision_document_refs["LX0609-022"] = tuple(
                _clean(item.get("ref")) for item in opinion_documents
                if _clean(item.get("ref"))
            )
    if "LX0609-020" in selected and execution_projection is not None:
        opinion_time = _parse_observed_time(opinion_documents[0].get("time"))

        def _is_after_opinion(candidate: _CandidateDocument) -> bool:
            if opinion_time is None:
                return False
            if candidate.observed_time.day != opinion_time.day:
                return candidate.observed_time.day > opinion_time.day
            return (
                candidate.observed_time.precise
                and opinion_time.precise
                and candidate.observed_time.value > opinion_time.value
            )

        explicit_execution_candidates = tuple(
            item
            for item in execution_projection.candidates
            if (
                item.source_key in _COURSE_EXECUTION_SOURCE_KEYS
                and _is_after_opinion(item)
                and _EXPLICIT_EXECUTION_TRACE_PATTERN.search(item.text)
            )
        )
        if explicit_execution_candidates:
            statuses["LX0609-020"] = ("compliant", "requirement_satisfied")
            if decision_document_refs is not None:
                decision_document_refs["LX0609-020"] = tuple(
                    dict.fromkeys((
                        *(
                            _clean(item.get("ref"))
                            for item in opinion_documents
                            if _clean(item.get("ref"))
                        ),
                        *(item.ref for item in explicit_execution_candidates),
                    ))
                )
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
            if decision_document_refs is not None:
                # 缺失的是会诊后病程执行痕迹；实际可证明的决定性文书只有
                # 对应会诊意见，不能借空来源或 snapshot ref 伪造执行证据。
                decision_document_refs["LX0609-020"] = tuple(
                    _clean(item.get("ref"))
                    for item in opinion_documents
                    if _clean(item.get("ref"))
                )
    return statuses


def _uses_compact_document_contract(
    documents: Sequence[Mapping[str, str]],
) -> bool:
    event_groups = tuple(
        _clean(document.get("event_group_ref")) for document in documents
    )
    return bool(documents) and all(
        _clean(document.get("event_identity_mode")) == "document"
        for document in documents
    ) and all(event_groups) and len(set(event_groups)) == len(event_groups)


def _compact_document_prompt(
    prompt_documents: Sequence[Mapping[str, str]],
) -> str:
    payload = json.dumps(
        {"consultation_documents": list(prompt_documents)}, ensure_ascii=False
    )
    if len(payload) > _MAX_PROMPT_CHARS:
        raise _SourceGap()
    return (
        "你逐份识别本次住院的普通专科会诊文书，并从明确会诊意见中抽取建议清单；不做质控结论。"
        "每个ref已经由CDM稳定文书身份隔离为独立事件，禁止跨ref合并，也禁止拆分同一ref。"
        "scope只能是ordinary/non_target/unknown：普通专科会诊为ordinary；术前多学科讨论、术前风险评估、"
        "麻醉评估、MDT讨论、普通病程、计划会诊、既往会诊提及和空模板为non_target；材料确实无法辨认才为unknown。"
        "application_state和opinion_state只能是clear/vague/missing/absent/unknown；"
        "clear为有明确目的或具体意见，vague为只有泛化措辞，missing为角色存在但内容空缺，"
        "absent为该角色不存在，unknown为材料无法可靠判断。confidence只能为high/medium/low。"
        "明确写出会诊原因、临床问题、请求专科建议或具体诊疗意见，即使只有一句，也属于clear；"
        "明确的病情判断、处理方向或随访安排也属于opinion_state=clear；"
        "opinion_state与recommendations相互独立，不得因为recommendations为空就把opinion_state降为vague；"
        "只有纯请会诊、协助诊治、遵会诊意见而没有具体内容时才为vague。"
        "recommendations仅用于ordinary且意见clear、confidence=high的可执行建议；不得把诊断、风险描述、"
        "既往史或泛化继续治疗当建议。建议身份由Python按数组顺序生成，禁止输出recommendation_ref；action_type只能是"
        "medication/test/procedure/transfer/monitoring/other；source_quote优先返回该文书的连续支持原句，最长240字；"
        "normalized_action只做医学归一化，不得虚构。non_target/unknown的recommendations必须为空。"
        "每个输入ref必须恰好输出一次，禁止创造、改写、遗漏或重复ref。"
        "严格输出JSON对象：{consultation_event_facts:[{ref,scope,application_state,opinion_state,confidence,"
        "recommendations:[{source_quote,normalized_action,action_type}]}]}。输入："
        + payload
    )


def _prompt(documents: Sequence[Mapping[str, str]]) -> str:
    prompt_documents = [
        {
            "ref": _clean(document.get("ref")),
            "time": _clean(document.get("time")),
            "text": _clean(document.get("text")),
            "event_group_ref": _clean(document.get("event_group_ref")),
        }
        for document in documents
    ]
    if _uses_compact_document_contract(documents):
        return _compact_document_prompt(prompt_documents)
    payload = json.dumps({"consultation_documents": prompt_documents}, ensure_ascii=False)
    if len(payload) > _MAX_PROMPT_CHARS:
        raise _SourceGap()
    first_ref = _clean(prompt_documents[0].get("ref"))
    output_example = json.dumps(
        {
            "episodes": [
                {
                    "episode_ref": first_ref,
                    "member_refs": [first_ref],
                    "application_refs": [first_ref],
                    "opinion_refs": [],
                    "application_state": "clear",
                    "opinion_state": "absent",
                    "confidence": "high",
                    "recommendations": [],
                }
            ],
            "non_target_refs": [],
            "unresolved_refs": [],
        },
        ensure_ascii=False,
        separators=(",", ":"),
    )
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
        "明确的病情判断、处理方向或随访安排同样可支持opinion_state=clear；"
        "opinion_state与recommendations相互独立：意见可以明确但没有满足建议清单抽取标准，"
        "不得因为recommendations为空就把opinion_state降为vague；"
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
        "event_group_ref非空表示Python已用CDM业务键或稳定文书身份确认事件边界：同一event_group_ref的全部文书必须进入同一个归属，"
        "不同event_group_ref的文书绝不能合并为同一个episode。event_group_ref为空时才允许按语义谨慎聚类。"
        "同一输入ref不得被拆入多个episode。"
        "episode_ref必须原样等于member_refs中的第一个引用。禁止创造、改写或遗漏ref；"
        "禁止把下划线改为连字符，也禁止把consultation_record改写为consultation-event。"
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
        "non_target_refs:[],unresolved_refs:[]}。格式示例（只说明引用和字段结构，不代表实际语义）："
        + output_example
        + "。输入："
        + payload
    )


def _parse_compact_document_facts(
    payload: Mapping[str, Any],
    documents: Sequence[Mapping[str, str]],
) -> tuple[_Episode, ...]:
    raw_facts = payload.get("consultation_event_facts")
    if not isinstance(raw_facts, list):
        raise _SemanticInvalid()
    expected_refs = tuple(str(item["ref"]) for item in documents)
    expected = set(expected_refs)
    documents_by_ref = {str(item["ref"]): item for item in documents}
    if len(raw_facts) != len(expected_refs):
        raise _SemanticInvalid()
    seen: set[str] = set()
    episodes: list[_Episode] = []
    for raw in raw_facts:
        if not isinstance(raw, Mapping):
            raise _SemanticInvalid()
        ref = _clean(raw.get("ref"))
        scope = _clean(raw.get("scope")).lower()
        application = _clean(raw.get("application_state")).lower()
        opinion = _clean(raw.get("opinion_state")).lower()
        confidence = _clean(raw.get("confidence")).lower()
        raw_recommendations = raw.get("recommendations")
        if (
            ref not in expected
            or ref in seen
            or scope not in {"ordinary", "non_target", "unknown"}
            or application not in _STATES
            or opinion not in _STATES
            or confidence not in _CONFIDENCE
            or not isinstance(raw_recommendations, list)
            or len(raw_recommendations) > _MAX_RECOMMENDATIONS_PER_EPISODE
            or (scope != "ordinary" and raw_recommendations)
        ):
            raise _SemanticInvalid()
        seen.add(ref)
        if scope == "non_target":
            continue
        recommendations: list[_Recommendation] = []
        document_text = _clean(documents_by_ref[ref].get("text"))
        for number, raw_recommendation in enumerate(raw_recommendations, 1):
            if not isinstance(raw_recommendation, Mapping):
                raise _SemanticInvalid()
            recommendation_ref = f"{ref}#r{number}"
            action_type = _clean(raw_recommendation.get("action_type")).lower()
            source_quote = raw_recommendation.get("source_quote")
            normalized_action = raw_recommendation.get("normalized_action")
            if (
                action_type not in _RECOMMENDATION_TYPES
                or not isinstance(normalized_action, str)
                or not normalized_action.strip()
                or len(normalized_action) > _MAX_RECOMMENDATION_CHARS
            ):
                raise _SemanticInvalid()
            grounded_source_quote = ""
            if (
                isinstance(source_quote, str)
                and source_quote.strip()
                and len(source_quote) <= _MAX_RECOMMENDATION_CHARS
                and _quote_is_grounded(
                    quote=source_quote,
                    source=document_text,
                )
            ):
                grounded_source_quote = source_quote
            recommendations.append(
                _Recommendation(
                    recommendation_ref,
                    action_type,
                    grounded_source_quote,
                    normalized_action,
                    ref,
                )
            )
        if recommendations and (opinion != "clear" or confidence != "high"):
            raise _SemanticInvalid()
        if application in {"vague", "missing", "unknown"} and _has_specific_application_purpose(
            application_refs=(ref,),
            documents_by_ref=documents_by_ref,
        ):
            application = "clear"
        if (
            opinion == "clear"
            and not recommendations
            and _opinion_is_only_generic(
                opinion_refs=(ref,),
                documents_by_ref=documents_by_ref,
            )
        ):
            opinion = "vague"
        if scope == "ordinary":
            opinion = _stabilize_explicit_opinion_state(
                opinion_state=opinion,
                opinion_refs=(ref,),
                documents_by_ref=documents_by_ref,
            )
        episodes.append(
            _Episode(
                ref,
                (ref,),
                () if application == "absent" else (ref,),
                () if opinion == "absent" else (ref,),
                application,
                opinion,
                confidence,
                tuple(recommendations),
            )
        )
    if seen != expected:
        raise _SemanticInvalid()
    return tuple(episodes)


def _merge_authoritative_event_group_splits(
    episodes: Sequence[_Episode],
    *,
    expected_refs: Sequence[str],
    documents_by_ref: Mapping[str, Mapping[str, str]],
) -> tuple[_Episode, ...]:
    """按程序已确认的同一事件合并模型误拆的申请、意见文书。"""

    document_order = {ref: index for index, ref in enumerate(expected_refs)}
    group_episode_indexes: dict[str, list[int]] = {}
    for index, item in enumerate(episodes):
        groups = frozenset(
            event_group_ref
            for ref in item.member_refs
            if (
                event_group_ref := _clean(
                    documents_by_ref[ref].get("event_group_ref")
                )
            )
        )
        if len(groups) > 1:
            raise _SemanticInvalid()
        if groups:
            group_episode_indexes.setdefault(next(iter(groups)), []).append(index)

    split_groups = {
        group_ref: tuple(indexes)
        for group_ref, indexes in group_episode_indexes.items()
        if len(indexes) > 1
    }
    if not split_groups:
        return tuple(episodes)

    def _state(values: Sequence[str]) -> str:
        # 明确事实可以收敛同事件内另一张角色单据的 absent；其余冲突保守
        # 保留 unknown，避免把模型不确定性转成确定问题。
        for candidate in ("clear", "unknown", "vague", "missing", "absent"):
            if candidate in values:
                return candidate
        raise _SemanticInvalid()

    merged_by_first_index: dict[int, _Episode] = {}
    consumed: set[int] = set()
    for group_ref, indexes in split_groups.items():
        grouped = tuple(episodes[index] for index in indexes)
        if any(
            _clean(documents_by_ref[ref].get("event_group_ref")) != group_ref
            for item in grouped
            for ref in item.member_refs
        ):
            raise _SemanticInvalid()
        member_refs = tuple(sorted(
            (ref for item in grouped for ref in item.member_refs),
            key=document_order.__getitem__,
        ))
        application_refs = tuple(sorted(
            (ref for item in grouped for ref in item.application_refs),
            key=document_order.__getitem__,
        ))
        opinion_refs = tuple(sorted(
            (ref for item in grouped for ref in item.opinion_refs),
            key=document_order.__getitem__,
        ))
        application_state = _state(tuple(item.application_state for item in grouped))
        opinion_state = _state(tuple(item.opinion_state for item in grouped))
        confidence = min(
            (item.confidence for item in grouped),
            key={"low": 0, "medium": 1, "high": 2}.__getitem__,
        )
        source_recommendations = tuple(
            recommendation
            for index in sorted(
                indexes,
                key=lambda value: min(
                    document_order[ref] for ref in episodes[value].member_refs
                ),
            )
            for recommendation in episodes[index].recommendations
        )
        if (
            len(source_recommendations) > _MAX_RECOMMENDATIONS_PER_EPISODE
            or source_recommendations
            and (opinion_state != "clear" or confidence != "high")
        ):
            raise _SemanticInvalid()
        episode_ref = member_refs[0]
        recommendations = tuple(
            _Recommendation(
                f"{episode_ref}#r{number}",
                item.action_type,
                item.source_quote,
                item.normalized_action,
                item.opinion_ref,
            )
            for number, item in enumerate(source_recommendations, 1)
        )
        first_index = min(indexes)
        merged_by_first_index[first_index] = _Episode(
            episode_ref,
            member_refs,
            application_refs,
            opinion_refs,
            application_state,
            opinion_state,
            confidence,
            recommendations,
        )
        consumed.update(indexes)

    normalized: list[_Episode] = []
    for index, item in enumerate(episodes):
        if index in merged_by_first_index:
            normalized.append(merged_by_first_index[index])
        elif index not in consumed:
            normalized.append(item)
    return tuple(normalized)


def _parse(payload: Mapping[str, Any], documents: Sequence[Mapping[str, str]]) -> tuple[_Episode, ...]:
    if _uses_compact_document_contract(documents):
        return _parse_compact_document_facts(payload, documents)
    raw_episodes = payload.get("episodes")
    non_target = payload.get("non_target_refs")
    unresolved = payload.get("unresolved_refs")
    if not isinstance(raw_episodes, list) or not isinstance(non_target, list) or not isinstance(unresolved, list):
        raise _SemanticInvalid()
    expected_refs = tuple(str(item["ref"]) for item in documents)
    expected = set(expected_refs)
    documents_by_ref = {str(item["ref"]): item for item in documents}
    assigned: list[str] = []
    assignment_bucket_by_ref: dict[str, str] = {}
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
            or len(raw_recommendations) > _MAX_RECOMMENDATIONS_PER_EPISODE
        ):
            raise _SemanticInvalid()
        recommendations: list[_Recommendation] = []
        for number, raw_recommendation in enumerate(raw_recommendations, 1):
            if not isinstance(raw_recommendation, Mapping):
                raise _SemanticInvalid()
            # recommendation_ref 是 Python 内部身份，不是模型判定事实。合并
            # episode 中模型可能按各意见文书分别从 r1 编号；与 compact 路径
            # 一致，统一按 episode 内数组顺序生成，避免格式差异抹掉合法事实。
            recommendation_ref = f"{episode_ref}#r{number}"
            opinion_ref = _clean(raw_recommendation.get("opinion_ref"))
            action_type = _clean(raw_recommendation.get("action_type")).lower()
            source_quote = raw_recommendation.get("source_quote")
            normalized_action = raw_recommendation.get("normalized_action")
            if (
                opinion_ref not in opinion_refs
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
        if (
            opinion == "clear"
            and not recommendations
            and _opinion_is_only_generic(
                opinion_refs=opinion_refs,
                documents_by_ref=documents_by_ref,
            )
        ):
            opinion = "vague"
        opinion = _stabilize_explicit_opinion_state(
            opinion_state=opinion,
            opinion_refs=opinion_refs,
            documents_by_ref=documents_by_ref,
        )
        assigned.extend(member_refs)
        assignment_bucket_by_ref.update(
            (ref, f"episode:{episode_ref}") for ref in member_refs
        )
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
    for bucket, group in (("non_target", non_target), ("unresolved", unresolved)):
        if not all(isinstance(ref, str) and ref in expected for ref in group):
            raise _SemanticInvalid()
        assigned.extend(group)
        assignment_bucket_by_ref.update((ref, bucket) for ref in group)
    if len(assigned) != len(expected_refs) or len(set(assigned)) != len(expected_refs) or set(assigned) != expected:
        raise _SemanticInvalid()
    episodes = list(_merge_authoritative_event_group_splits(
        episodes,
        expected_refs=expected_refs,
        documents_by_ref=documents_by_ref,
    ))
    assignment_bucket_by_ref = {
        ref: f"episode:{item.episode_ref}"
        for item in episodes
        for ref in item.member_refs
    }
    for bucket, group in (("non_target", non_target), ("unresolved", unresolved)):
        assignment_bucket_by_ref.update((ref, bucket) for ref in group)
    event_group_buckets: dict[str, set[str]] = {}
    for ref, document in documents_by_ref.items():
        event_group_ref = _clean(document.get("event_group_ref"))
        if event_group_ref:
            event_group_buckets.setdefault(event_group_ref, set()).add(
                assignment_bucket_by_ref[ref]
            )
    if any(len(buckets) != 1 for buckets in event_group_buckets.values()):
        raise _SemanticInvalid()
    episode_event_groups: dict[str, set[str]] = {}
    for ref, bucket in assignment_bucket_by_ref.items():
        if not bucket.startswith("episode:"):
            continue
        event_group_ref = _clean(documents_by_ref[ref].get("event_group_ref"))
        if event_group_ref:
            episode_event_groups.setdefault(bucket, set()).add(event_group_ref)
    if any(len(groups) > 1 for groups in episode_event_groups.values()):
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
    episode_results: list[dict[str, Any]] = []
    episode_source_document_ids: list[tuple[str, tuple[str, ...]]] = []
    if rule_id in {"LX0609-021", "LX0609-022"}:
        for episode_index, episode in enumerate(relevant, start=1):
            episode_refs = tuple(getattr(episode, ref_field)) or episode.member_refs
            episode_document_ids = tuple(
                dict.fromkeys(
                    document_id
                    for ref in episode_refs
                    if (
                        document_id := _clean(
                            documents_by_ref.get(ref, {}).get("document_id")
                        )
                    )
                )
            )
            representative = next(
                (
                    documents_by_ref[ref]
                    for ref in episode_refs
                    if ref in documents_by_ref
                ),
                {},
            )
            representative_document_id = _clean(representative.get("document_id"))
            observed_time = _parse_observed_time(representative.get("time"))
            record_time = ""
            if observed_time is not None:
                record_time = observed_time.value.strftime(
                    "%Y-%m-%d %H:%M:%S" if observed_time.precise else "%Y-%m-%d"
                )
            episode_state = getattr(episode, state_field)
            episode_source_document_ids.append(
                (episode_state, episode_document_ids)
            )
            episode_results.append(
                {
                    "episode_index": episode_index,
                    "semantic_state": episode_state,
                    "source_document_id": representative_document_id,
                    "record_time": record_time,
                    "document_title": (
                        "会诊申请单"
                        if rule_id == "LX0609-021"
                        else "会诊记录单"
                    ),
                }
            )
    # 客户展示不携带原始文书 ID；证据投影仍必须优先保留实际缺陷 episode，
    # 否则第 9--12 次会诊出现问题时会被通用 8 条证据上限截掉而无法定位。
    source_document_ids = [
        document_id
        for wanted_state in ("vague", "missing", "unknown", "clear")
        for episode_state, document_ids in episode_source_document_ids
        if episode_state == wanted_state
        for document_id in document_ids
    ]
    facts = {
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
    if rule_id in {"LX0609-021", "LX0609-022"}:
        facts["source_document_ids"] = list(dict.fromkeys(source_document_ids))[
            :100
        ]
        facts["episode_results"] = episode_results
    return facts


def _explicit_embedded_opinion_display_facts(
    documents: Sequence[Mapping[str, str]],
) -> Mapping[str, Any]:
    """按已核实的逐份会诊正文生成 022 客户展示事实。"""

    explicit_episodes = tuple(
        _Episode(
            episode_ref=ref,
            member_refs=(ref,),
            application_refs=(),
            opinion_refs=(ref,),
            application_state="absent",
            opinion_state="clear",
            confidence="high",
            recommendations=(),
        )
        for document in documents
        if (ref := _clean(document.get("ref")))
    )
    return _consultation_semantic_display_facts(
        rule_id="LX0609-022",
        episodes=explicit_episodes,
        documents=documents,
    )


def _build_diagnostic_semantic_snapshot(
    *,
    documents: Sequence[Mapping[str, str]],
    episodes: Sequence[_Episode],
    statuses: Mapping[str, tuple[str, str]],
) -> Mapping[str, Any]:
    """生成仅供诊断追踪使用的语义事实快照，不携带正文、Prompt 或引用摘录。"""

    document_rows = []
    for document in documents:
        document_rows.append(
            {
                "source_ref": _clean(document.get("ref")),
                "source": _clean(document.get("source")),
                "document_id": _clean(document.get("document_id")),
                "record_time": _clean(document.get("time")),
            }
        )
    episode_rows = []
    for episode in episodes:
        episode_rows.append(
            {
                "episode_ref": episode.episode_ref,
                "member_refs": list(episode.member_refs),
                "application_refs": list(episode.application_refs),
                "opinion_refs": list(episode.opinion_refs),
                "application_state": episode.application_state,
                "opinion_state": episode.opinion_state,
                "confidence": episode.confidence,
                "recommendation_count": len(episode.recommendations),
            }
        )
    return {
        "schema_version": "consultation-semantic-snapshot-v1",
        "stage": "semantic",
        "semantic_documents": document_rows,
        "episodes": episode_rows,
        "synthesized_rule_states": {
            rule_id: {"status": status, "reason_code": reason_code}
            for rule_id, (status, reason_code) in statuses.items()
        },
    }


def _consultation_execution_display_facts(
    *,
    rule_id: str,
    status: str,
    episodes: Sequence[_Episode],
    completed_recommendations: Sequence[_CompletedRecommendation],
    assessments: Sequence[_ExecutionAssessment] | None,
    documents: Sequence[Mapping[str, str]],
    candidates: Sequence[_CandidateDocument] = (),
) -> Mapping[str, Any]:
    """解释020的关联结果或023的执行质量结果。"""

    relation_by_status_020 = {
        "compliant": "all_linked",
        "non_compliant": "execution_missing",
        "not_applicable": "not_triggered",
        "data_gap": "source_incomplete",
        "evaluation_unknown": "association_unresolved",
        "technical_error": "source_error",
    }
    relation_by_status_023 = {
        "compliant": "specific_execution",
        "non_compliant": "generic_or_copied_execution",
        "not_applicable": "execution_record_absent",
        "data_gap": "source_incomplete",
        "evaluation_unknown": "association_unresolved",
        "technical_error": "source_error",
    }
    assessment_rows = tuple(assessments or ())
    assessments_by_recommendation = {
        item.recommendation_ref: item for item in assessment_rows
    }
    completed_episode_refs = tuple(
        dict.fromkeys(
            item.episode_ref
            for item in episodes
            if item.opinion_state == "clear" and item.confidence == "high"
        )
    )
    episode_indexes = {
        episode_ref: index
        for index, episode_ref in enumerate(completed_episode_refs, start=1)
    }
    missing_episode_refs: set[str] = set()
    for item in completed_recommendations:
        assessment = assessments_by_recommendation.get(
            item.recommendation.recommendation_ref
        )
        if (
            assessment is not None
            and assessment.execution_record_state == "no_trace"
            and not assessment.execution_refs
        ):
            missing_episode_refs.add(item.episode_ref)
    evidence_episodes = tuple(
        episode
        for episode in episodes
        if not (
            rule_id == "LX0609-020"
            and status == "non_compliant"
            and missing_episode_refs
        )
        or episode.episode_ref in missing_episode_refs
    )
    opinion_refs = tuple(
        dict.fromkeys(
            ref
            for episode in evidence_episodes
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
    candidate_by_ref = {item.ref: item for item in candidates}
    source_document_refs: list[dict[str, str]] = [
        {
            "source_type": "consultation_record",
            "source_document_id": document_id,
        }
        for document_id in source_document_ids
    ]
    if not (rule_id == "LX0609-020" and status == "non_compliant"):
        offending_refs: list[dict[str, str]] = []
        recommendations_by_ref = {
            item.recommendation.recommendation_ref: item.recommendation
            for item in completed_recommendations
        }
        for assessment in assessment_rows:
            is_offending = (
                rule_id == "LX0609-023"
                and status == "non_compliant"
                and assessment.execution_record_state
                in {"generic_trace", "copied_opinion"}
            )
            recommendation = recommendations_by_ref.get(assessment.recommendation_ref)
            if (
                recommendation is not None
                and recommendation.opinion_ref in documents_by_ref
            ):
                opinion_document_id = _clean(
                    documents_by_ref[recommendation.opinion_ref].get("document_id")
                )
                if opinion_document_id:
                    opinion_ref = {
                        "source_type": "consultation_record",
                        "source_document_id": opinion_document_id,
                    }
                    if is_offending:
                        offending_refs.append(opinion_ref)
            for ref in (*assessment.trace_refs, *assessment.execution_refs):
                candidate = candidate_by_ref.get(ref)
                if candidate is None or not candidate.document_id:
                    continue
                candidate_ref = {
                    "source_type": candidate.source_key,
                    "source_document_id": candidate.document_id,
                }
                source_document_refs.append(candidate_ref)
                if is_offending:
                    offending_refs.append(candidate_ref)
        if offending_refs:
            # 非合规证据最多保留 8 条，但实际笼统/照抄的会诊及执行文书
            # 必须优先保留；其余上下文按原顺序填充，避免末次缺陷被截掉。
            deduplicated: list[dict[str, str]] = []
            seen_refs: set[tuple[str, str]] = set()
            for item in source_document_refs:
                key = (item["source_type"], item["source_document_id"])
                if key not in seen_refs:
                    seen_refs.add(key)
                    deduplicated.append(item)
            offending_unique: list[dict[str, str]] = []
            seen_offending: set[tuple[str, str]] = set()
            offending_keys = {
                (item["source_type"], item["source_document_id"])
                for item in offending_refs
            }
            for item in offending_refs:
                key = (item["source_type"], item["source_document_id"])
                if key not in seen_offending:
                    seen_offending.add(key)
                    offending_unique.append(item)
            context_refs = [
                item
                for item in deduplicated
                if (item["source_type"], item["source_document_id"])
                not in offending_keys
            ]
            source_document_refs = (
                context_refs[: max(0, 8 - len(offending_unique))]
                + offending_unique[:8]
            )[:8]
    source_document_refs = list(
        {
            (item["source_type"], item["source_document_id"]): item
            for item in source_document_refs
        }.values()
    )[:8]
    facts: dict[str, Any] = {
        "verification_kind": (
            "consultation_execution_quality_check"
            if rule_id == "LX0609-023"
            else "consultation_execution_relation_check"
        ),
        "completed_opinion_episode_count": len(
            {
                episode.episode_ref
                for episode in episodes
                if episode.opinion_state == "clear" and episode.confidence == "high"
            }
        ),
        "recommendation_count": (
            # 只有通过权威时间和住院窗口校验的建议才进入二阶段执行核对。
            # 当来源不完整时，episodes 仍可能包含语义上提取出的建议，
            # 但 completed_recommendations 为空；此时不能把未进入核对的
            # 数量写入 recommendation_count，否则 recommendation_results
            # 无法逐项投影，聚合器会把本病例错误升级为技术异常。
            len(completed_recommendations)
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
        "relation_state": (
            relation_by_status_023 if rule_id == "LX0609-023" else relation_by_status_020
        ).get(status, "association_unresolved"),
        "source_document_ids": list(dict.fromkeys(source_document_ids))[:8],
        "source_document_refs": source_document_refs,
    }
    if rule_id in {"LX0609-020", "LX0609-023"}:
        recommendation_results: list[dict[str, Any]] = []
        recommendation_evidence: list[dict[str, Any]] = []
        for recommendation_index, item in enumerate(
            completed_recommendations, start=1
        ):
            assessment = assessments_by_recommendation.get(
                item.recommendation.recommendation_ref
            )
            execution_state = "unknown"
            if assessment is not None:
                if assessment.execution_record_state == "specific_trace":
                    execution_state = "specific"
                elif assessment.execution_record_state in {
                    "generic_trace",
                    "copied_opinion",
                }:
                    execution_state = "generic"
                elif (
                    assessment.execution_record_state == "no_trace"
                    and not assessment.execution_refs
                ):
                    execution_state = "missing"
            opinion_evidence: list[dict[str, str]] = []
            opinion_document = documents_by_ref.get(item.recommendation.opinion_ref)
            opinion_document_id = _clean(
                opinion_document.get("document_id") if opinion_document else ""
            )
            if opinion_document_id:
                opinion_evidence.append(
                    {
                        "source_type": "consultation_record",
                        "source_document_id": opinion_document_id,
                    }
                )
            execution_evidence: list[dict[str, str]] = []
            seen_execution_refs: set[tuple[str, str]] = set()
            if assessment is not None:
                for ref in (*assessment.trace_refs, *assessment.execution_refs):
                    candidate = candidate_by_ref.get(ref)
                    candidate_document_id = _clean(
                        candidate.document_id if candidate is not None else ""
                    )
                    if candidate is None or not candidate_document_id:
                        continue
                    key = (candidate.source_key, candidate_document_id)
                    if key in seen_execution_refs:
                        continue
                    seen_execution_refs.add(key)
                    execution_evidence.append(
                        {
                            "source_type": candidate.source_key,
                            "source_document_id": candidate_document_id,
                        }
                    )
            if rule_id == "LX0609-020":
                recommendation_results.append(
                    {
                        "episode_index": episode_indexes[item.episode_ref],
                        "recommendation_index": recommendation_index,
                        "action_type": item.recommendation.action_type,
                        "execution_state": execution_state,
                    }
                )
            recommendation_evidence.append(
                {
                    "episode_index": episode_indexes[item.episode_ref],
                    "recommendation_index": recommendation_index,
                    "execution_state": execution_state,
                    "opinion_refs": opinion_evidence,
                    # 客户事实合同每组最多接收 8 条引用。这里只裁剪展示引用；
                    # assessments 与 RuleDecision.fact_refs 继续保留完整判定事实。
                    # 上方按 trace refs、structured refs 的顺序去重，因此切片
                    # 仍会优先保留病程主证据。
                    "execution_refs": execution_evidence[:8],
                }
            )
        if rule_id == "LX0609-020":
            facts["recommendation_results"] = recommendation_results
        facts["recommendation_evidence"] = recommendation_evidence[:96]
    return facts


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
    if len(completed) > _MAX_TOTAL_RECOMMENDATIONS:
        raise _SourceGap()
    return tuple(completed)


def _execution_prompt(
    *,
    completed: Sequence[_CompletedRecommendation],
    candidates: Sequence[_CandidateDocument],
) -> tuple[str, Mapping[str, frozenset[str]]]:
    entries: list[dict[str, object]] = []
    allowed_refs: dict[str, frozenset[str]] = {}
    documents_by_ref: dict[str, dict[str, object]] = {}
    trace_candidates = tuple(
        candidate
        for candidate in candidates
        if candidate.source_key in _CONTEXT_ONLY_EXECUTION_SOURCE_KEYS
    )
    # 4.20.4 的主核对对象仍是会诊后的病程记录，但正式资料链已明确：医嘱、
    # 检查、检验和手术可作为同次执行的结构化佐证。不能因为存在病程候选就
    # 把这些已选来源从二阶段事实输入中静默丢失。
    prompt_candidates = tuple(candidates)
    for item in completed:
        related_refs: list[str] = []
        eligible_sources = _ACTION_TYPE_SOURCE_KEYS.get(
            item.recommendation.action_type,
            frozenset((*_EXECUTION_SOURCE_KEYS, "inpat_nondrug_order")),
        )
        for candidate in prompt_candidates:
            embedded_same_episode = (
                candidate.source_key == "consultation_record"
                and candidate.ref == item.recommendation.opinion_ref
            )
            if candidate.source_key not in eligible_sources and not embedded_same_episode:
                continue
            if embedded_same_episode:
                include = True
            elif candidate.observed_time.day > item.opinion_time.day:
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
                related_refs.append(candidate.ref)
                documents_by_ref.setdefault(candidate.ref, {
                    "ref": candidate.ref,
                    "source": candidate.source_key,
                    "date": candidate.observed_time.value.isoformat(),
                    "text": candidate.text,
                })
        allowed_refs[item.recommendation.recommendation_ref] = frozenset(
            related_refs
        )
        entries.append({
            "recommendation_ref": item.recommendation.recommendation_ref,
            "action_type": item.recommendation.action_type,
            "normalized_action": item.recommendation.normalized_action,
            "source_quote": item.recommendation.source_quote,
            "opinion_date": item.opinion_time.value.isoformat(),
        })
    payload = json.dumps({
        "recommendations": entries,
        "candidate_documents": list(documents_by_ref.values()),
    }, ensure_ascii=False)
    if len(payload) > _MAX_EXECUTION_PROMPT_CHARS:
        raise _SourceGap()
    if trace_candidates and not any(
        candidate.source_key in _STRUCTURED_EXECUTION_EVIDENCE_SOURCE_KEYS
        for candidate in prompt_candidates
    ):
        return (
            "你只核对每条会诊建议在后续病程、查房或同一会诊文书内明确闭环决策中的执行痕迹，不得补充病历之外的信息。"
            "execution_record_state只能是specific_trace/generic_trace/copied_opinion/no_trace/unknown："
            "specific_trace=明确写出按会诊意见采取的具体措施；generic_trace=仅写遵会诊意见执行或已按建议处理；"
            "copied_opinion=照抄意见但没有归纳执行情况；no_trace=未见该建议的执行记录痕迹；unknown=无法判断。"
            "病程明确记载已经给予、已行、已实施的具体治疗、检查、固定、制动或监测措施，可判specific_trace；"
            "属于specific_trace时必须能由所引病程原文直接核实具体执行动作。"
            "病程明确写出已安排并完成检查、已给予治疗或已实施固定/冰敷等动作，绝不是generic_trace。"
            "同一治疗类别的多个细项建议，若病程明确记载该治疗类别已经实施、但未逐项重复细项，"
            "可以分别判定已有执行痕迹；不得把跨类别措施合并推断。"
            "拟执行、计划执行、申请执行、请会诊、症状改善、无关治疗或同部位一般治疗都不是已经执行。"
            "trace_refs只能引用candidate_documents中的病程ref，且候选时间不得早于该建议的opinion_date；"
            "不得引用会诊申请或会诊意见的ref，也不得引用其他建议的ref。specific_trace/generic_trace/copied_opinion必须返回至少一个trace_refs；"
            "no_trace/unknown必须返回空trace_refs。confidence只能是high/medium/low。"
            "某条建议没有不早于其opinion_date的可验证candidate_documents ref时必须返回unknown。"
            "每个输入recommendation_ref恰好输出一次，禁止重复、遗漏或创造。"
            "严格输出JSON：{executions:[{recommendation_ref,execution_record_state,trace_refs,confidence}]}。输入："
            + payload,
            allowed_refs,
        )
    prompt = (
        "你分两步判断每条会诊建议的后续落实，不得补充病历之外的信息。"
        "第一步先识别会诊后病程/查房中是否记录会诊意见及执行情况："
        "specific_trace=明确写出按会诊意见采取的具体措施；"
        "generic_trace=仅写遵会诊意见执行/已按建议处理等笼统表述；"
        "copied_opinion=照抄会诊意见、没有归纳执行情况；"
        "no_trace=未见请会诊执行记录痕迹；unknown=无法判断。"
        "病程明确写出予以、给予、已行或已实施某项具体治疗、检查、固定、制动或监测措施，"
        "属于specific_trace；不得仅因没有重复会诊原句或没有结构化医嘱而降为generic_trace或unknown。"
        "第二步可辅助判断结构化医嘱/操作候选是否与该建议存在动作对应关系，"
        "但结构化匹配不是020或023的合规硬条件。"
        "同一执行文书可同时落实多条建议，禁止要求唯一归属。"
        "同一会诊文书仅可关联该文书自身意见中的建议；只有文书在建议后又明确记载已沟通、"
        "患者或家属拒绝/暂缓执行及具体原因，才属于specific_trace；建议原文本身绝不是执行。"
        "execution_state只描述结构化动作匹配：linked_specific=结构化候选明确落实同一条建议，"
        "linked_vague=结构化候选仅笼统相关，absent=无结构化动作匹配，unknown=无法判断。"
        "daily_course_record和senior_course_record只允许进入trace_refs，不能进入structured_action_refs；"
        "inpat_drug_order、inpat_nondrug_order、exam_master、exam_item_report、"
        "labtest_master、labtest_item_report和surgery_record只允许进入structured_action_refs。"
        "只有病程写“遵会诊意见执行”“已按建议处理”或具体动作、但无对应医嘱/检查/检验/手术/操作结构化记录时，"
        "execution_record_state按其具体程度填写，但execution_state必须输出absent。"
        "只有结构化医嘱/检查/检验/操作动作、没有病程/查房执行记录痕迹时，execution_record_state必须为no_trace。"
        "同一治疗类别的多个细项建议（例如同属康复训练的关节活动、肌力训练），"
        "若候选明确记载该治疗类别已经实施、但未逐项写明细项，可对每个细项输出linked_vague且confidence=high；"
        "这只适用于同一临床治疗类别，绝不得用一句泛化记录覆盖药物、检查、转运等跨类别建议。"
        "拟执行、计划执行、申请执行、请会诊、症状改善、无关治疗或同部位一般治疗都不是已经执行。"
        "confidence只能为high/medium/low。"
        "trace_refs和structured_action_refs只能引用candidate_documents中的ref，且候选时间必须不早于该建议的opinion_date；绝不得引用会诊申请或会诊意见的ref。"
        "specific_trace/generic_trace/copied_opinion必须至少返回一个trace_refs；linked_specific或linked_vague必须至少返回一个structured_action_refs。"
        "某条建议没有不早于其opinion_date的可验证candidate_documents ref时必须返回unknown。"
        "execution_quotes是可选的辅助摘录；已选择精确trace_refs或structured_action_refs时可以返回空数组。"
        "若返回摘录，每项必须是所引执行候选中的连续原文，不得改写、拼接或引用未选候选。"
        "no_trace/absent组合必须返回空数组trace_refs、structured_action_refs和execution_quotes。"
        "每个输入recommendation_ref恰好输出一项，禁止重复。"
        "严格输出JSON：{executions:[{recommendation_ref,execution_record_state,trace_refs,execution_state,structured_action_refs,execution_quotes,confidence}]}。输入："
        + payload
    )
    return prompt, allowed_refs


def _generic_trace_conflicts_with_completed_action(
    assessment: _ExecutionAssessment,
    candidates: Sequence[_CandidateDocument],
) -> bool:
    if assessment.execution_record_state not in {"generic_trace", "copied_opinion"}:
        return False
    by_ref = {item.ref: item for item in candidates}
    return any(
        ref in by_ref and _EXPLICIT_COMPLETED_ACTION_PATTERN.search(by_ref[ref].text)
        for ref in assessment.trace_refs
    )


def _apply_embedded_decision_traces(
    assessments: Sequence[_ExecutionAssessment],
    *,
    completed: Sequence[_CompletedRecommendation],
    embedded_refs: frozenset[str],
) -> tuple[_ExecutionAssessment, ...]:
    """同次会诊内明确沟通并暂缓/拒绝的决定是可核验闭环事实。"""

    opinion_ref_by_recommendation = {
        item.recommendation.recommendation_ref: item.recommendation.opinion_ref
        for item in completed
    }
    return tuple(
        replace(
            item,
            confidence="high",
            execution_record_state="specific_trace",
            trace_refs=(opinion_ref,),
            context_only_refs=(opinion_ref,),
        )
        if (
            opinion_ref := opinion_ref_by_recommendation.get(item.recommendation_ref)
        ) in embedded_refs
        else item
        for item in assessments
    )


def _unknown_execution_assessment(recommendation_ref: str) -> _ExecutionAssessment:
    return _ExecutionAssessment(
        recommendation_ref,
        "unknown",
        (),
        "low",
        (),
        "unknown",
        (),
        (),
    )


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
    prompt_candidate_refs = {
        ref for refs in allowed_refs.values() for ref in refs
    }
    compact_course_only = bool(prompt_candidate_refs) and all(
        ref in candidate_by_ref
        and candidate_by_ref[ref].source_key in _CONTEXT_ONLY_EXECUTION_SOURCE_KEYS
        for ref in prompt_candidate_refs
    )
    if not isinstance(raw, list):
        raise _SemanticInvalid(_SemanticInvalidKind.RESPONSE_SHAPE)
    if len(raw) > len(expected_refs):
        raise _SemanticInvalid(_SemanticInvalidKind.RECOMMENDATION_IDENTITY)
    parsed: list[_ExecutionAssessment] = []
    seen: set[str] = set()
    for item in raw:
        if not isinstance(item, Mapping):
            raise _SemanticInvalid(_SemanticInvalidKind.RESPONSE_SHAPE)
        recommendation_ref = _clean(item.get("recommendation_ref"))
        if recommendation_ref not in expected_refs or recommendation_ref in seen:
            raise _SemanticInvalid(_SemanticInvalidKind.RECOMMENDATION_IDENTITY)
        seen.add(recommendation_ref)
        state = _clean(item.get("execution_state")).lower()
        original_state = state
        confidence = _clean(item.get("confidence")).lower()
        refs = item.get("execution_refs")
        raw_trace_refs = item.get("trace_refs")
        raw_structured_refs = item.get("structured_action_refs")
        raw_quotes = item.get("execution_quotes")
        execution_record_state = _clean(item.get("execution_record_state")).lower()
        compact_item = (
            compact_course_only
            and item.get("execution_state") is None
            and item.get("execution_refs") is None
            and raw_structured_refs is None
            and raw_quotes is None
        )
        if compact_item:
            state = "absent"
            original_state = state
            raw_structured_refs = []
            raw_quotes = []
        # Prompt 合同明确 execution_quotes 是可选的辅助摘录。模型省略该键与
        # 显式返回空数组语义等价；仍拒绝字符串、对象等错误类型。
        if raw_quotes is None:
            raw_quotes = []
        if (
            (refs is not None and not isinstance(refs, list))
            or (raw_trace_refs is not None and not isinstance(raw_trace_refs, list))
            or (raw_structured_refs is not None and not isinstance(raw_structured_refs, list))
            or (
                isinstance(refs, list)
                and not all(isinstance(ref, str) for ref in refs)
            )
            or (
                isinstance(raw_trace_refs, list)
                and not all(isinstance(ref, str) for ref in raw_trace_refs)
            )
            or (
                isinstance(raw_structured_refs, list)
                and not all(isinstance(ref, str) for ref in raw_structured_refs)
            )
        ):
            raise _SemanticInvalid(_SemanticInvalidKind.REFERENCE_SHAPE)
        if (
            state not in _EXECUTION_STATES
            or confidence not in _CONFIDENCE
            or (compact_item and not execution_record_state)
            or (execution_record_state and execution_record_state not in _EXECUTION_RECORD_STATES)
            or not isinstance(raw_quotes, list)
        ):
            parsed.append(_unknown_execution_assessment(recommendation_ref))
            continue
        refs = refs if isinstance(refs, list) else []
        trace_refs = raw_trace_refs if isinstance(raw_trace_refs, list) else []
        structured_refs = raw_structured_refs if isinstance(raw_structured_refs, list) else []
        if any(ref not in candidate_by_ref for ref in refs):
            raise _SemanticInvalid(_SemanticInvalidKind.REFERENCE_NOT_CANDIDATE)
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
        # 部分模型会把同一病程ref同时放入trace和辅助结构化字段。病程只能
        # 作为020/023主证据；安全丢弃这个冗余辅助副本，不把仅出现在辅助
        # 字段的病程反向提升为执行记录。嵌套、伪造和越界ref仍由下方拒绝。
        duplicated_course_refs = {
            ref
            for ref in structured_refs
            if ref in trace_refs
            and ref in candidate_by_ref
            and candidate_by_ref[ref].source_key in _CONTEXT_ONLY_EXECUTION_SOURCE_KEYS
        }
        if duplicated_course_refs:
            structured_refs = [
                ref for ref in structured_refs if ref not in duplicated_course_refs
            ]
        if trace_refs and not structured_refs and state in {
            "linked_specific",
            "linked_vague",
        }:
            # 结构化动作状态是辅助维度；没有结构化ref时统一收敛为absent，
            # 但保留已经逐字落地的病程trace，不让模型的冗余枚举作废主事实。
            state = "absent"
        all_refs = [*trace_refs, *structured_refs]
        reference_scope_invalid = any(
            ref not in allowed_refs[recommendation_ref]
            for ref in all_refs
        )
        if any(ref not in candidate_by_ref for ref in all_refs):
            raise _SemanticInvalid(_SemanticInvalidKind.REFERENCE_NOT_CANDIDATE)
        if reference_scope_invalid:
            parsed.append(_unknown_execution_assessment(recommendation_ref))
            continue
        if (
            len(trace_refs) != len(set(trace_refs))
            or len(structured_refs) != len(set(structured_refs))
            or len(all_refs) != len(set(all_refs))
            or not all(candidate_by_ref[ref].source_key in _CONTEXT_ONLY_EXECUTION_SOURCE_KEYS for ref in trace_refs)
            or not all(candidate_by_ref[ref].source_key in _STRUCTURED_EXECUTION_EVIDENCE_SOURCE_KEYS for ref in structured_refs)
            or (state in {"linked_specific", "linked_vague"} and not structured_refs)
            or (state in {"absent", "unknown"} and structured_refs)
        ):
            parsed.append(_unknown_execution_assessment(recommendation_ref))
            continue
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
            parsed.append(_unknown_execution_assessment(recommendation_ref))
            continue
        quotes = tuple(_clean(quote) for quote in raw_quotes)
        if any(not quote or len(quote) > _MAX_RECOMMENDATION_CHARS for quote in quotes) or len(quotes) != len(set(quotes)):
            parsed.append(_unknown_execution_assessment(recommendation_ref))
            continue
        selected_documents = tuple(
            candidate_by_ref[ref] for ref in all_refs if ref in candidate_by_ref
        )
        if all_refs and quotes:
            grounded_quotes = tuple(
                quote
                for quote in quotes
                if any(
                    _quote_is_grounded(quote=quote, source=candidate.text)
                    for candidate in selected_documents
                )
            )
            # 模型偶尔在已落地摘录之外追加一段无法落地的冗余文字。只保留
            # 已逐字命中受控候选的摘录。摘录是辅助字段，精确ref已通过
            # 来源、时序与白名单校验后，冗余改写不得作废主事实。
            quotes = grounded_quotes
        elif quotes:
            parsed.append(_unknown_execution_assessment(recommendation_ref))
            continue
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
        raise _ExecutionCoverageIncomplete(
            parsed=tuple(parsed),
            missing_refs=frozenset(expected_refs.difference(seen)),
        )
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
    if source_technical:
        return "technical_error", "source_query_error"
    trace_states = tuple(
        item.execution_record_state for item in assessments or ()
    )
    confirmed_no_course_trace_refs = {
        item.recommendation_ref
        for item in assessments or ()
        if item.execution_record_state == "no_trace"
        and item.confidence == "high"
        and item.execution_state != "unknown"
    }
    confirmed_vague_trace = any(
        item.execution_record_state in {"generic_trace", "copied_opinion"}
        and item.confidence == "high"
        for item in assessments or ()
    )
    course_source_incomplete = bool(
        _COURSE_EXECUTION_SOURCE_KEYS.intersection(source_incomplete_keys)
    )
    # 一条已经严格落地的缺陷足以形成不合规结论；其他建议仍待判断只会
    # 阻止“全部合规”，不能反向抹掉已确认的缺失或笼统记录。
    if rule_id == "LX0609-020" and confirmed_no_course_trace_refs:
        if course_source_incomplete:
            return "data_gap", "candidate_scope_incomplete"
        return "non_compliant", "requirement_violated"
    if rule_id == "LX0609-023" and confirmed_vague_trace:
        return "non_compliant", "requirement_violated"
    if uncertain:
        return "evaluation_unknown", "semantic_low_confidence"
    if not completed or not completed_recommendations:
        return "not_applicable", "trigger_absent_complete"
    if assessments is None or any(
        item.confidence != "high"
        or item.execution_state == "unknown"
        or item.execution_record_state == "unknown"
        for item in assessments
    ):
        if source_technical:
            return "technical_error", "source_query_error"
        return "evaluation_unknown", "semantic_low_confidence"
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
    if len(no_course_trace_refs) == len(assessments):
        if course_source_incomplete:
            return "data_gap", "candidate_scope_incomplete"
        return "not_applicable", "trigger_absent_complete"
    recorded_trace_states = tuple(
        state for state in trace_states if state != "no_trace"
    )
    if any(
        state in {"generic_trace", "copied_opinion"}
        for state in recorded_trace_states
    ):
        return "non_compliant", "requirement_violated"
    if recorded_trace_states and all(
        state == "specific_trace" for state in recorded_trace_states
    ):
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


def _safe_customer_display_facts(
    raw_facts: Sequence[tuple[str, Mapping[str, Any]]],
) -> tuple[tuple[tuple[str, Mapping[str, Any]], ...], frozenset[str]]:
    """客户事实只经声明式投影输出；单规则合同异常就地技术失败。"""

    safe_facts: list[tuple[str, Mapping[str, Any]]] = []
    invalid_rule_ids: set[str] = set()
    for rule_id, raw in raw_facts:
        if not is_consultation_customer_rule(rule_id):
            invalid_rule_ids.add(rule_id)
        elif (safe := safe_consultation_customer_display_facts(rule_id=rule_id, raw=raw)) is None:
            invalid_rule_ids.add(rule_id)
        else:
            safe_facts.append((rule_id, safe))
    return tuple(safe_facts), frozenset(invalid_rule_ids)


def _decision(
    *, rule_id: str, status: str, reason_code: str,
    snapshot: Luxian0609EvidenceSnapshot,
    fact_refs: Sequence[str] = (),
) -> RuleDecision:
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
        fact_refs=tuple(dict.fromkeys(str(reference) for reference in fact_refs if reference)),
        evaluator_version=_EVALUATOR_VERSION,
    )


def _finish(
    *, selected: tuple[str, ...], status: str, reason_code: str,
    calls: int = 0, prompt_tokens: int = 0, completion_tokens: int = 0,
    total_tokens: int = 0, api_time: float = 0.0,
    evidence_snapshot: Luxian0609EvidenceSnapshot | None = None,
    decision_rule_ids: frozenset[str] = frozenset(),
    fact_refs_by_rule: Mapping[str, Sequence[str]] | None = None,
) -> NativeConsultationEpisodeExecutionResult:
    decisions = tuple(
        _decision(
            rule_id=rule_id,
            status=status,
            reason_code=reason_code,
            snapshot=evidence_snapshot,
            fact_refs=(fact_refs_by_rule or {}).get(rule_id, ()),
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


def _finish_statuses(
    *, selected: tuple[str, ...], statuses: Mapping[str, tuple[str, str]],
    calls: int = 0, prompt_tokens: int = 0, completion_tokens: int = 0,
    total_tokens: int = 0, api_time: float = 0.0,
    evidence_snapshot: Luxian0609EvidenceSnapshot | None = None,
    decision_rule_ids: frozenset[str] = frozenset(),
) -> NativeConsultationEpisodeExecutionResult:
    """按规则分别收敛失败状态，同时保留同一证据快照引用。"""

    results = []
    decisions = []
    for rule_id in selected:
        status, reason_code = statuses[rule_id]
        if rule_id in decision_rule_ids and evidence_snapshot is not None:
            decisions.append(
                _decision(
                    rule_id=rule_id,
                    status=status,
                    reason_code=reason_code,
                    snapshot=evidence_snapshot,
                )
            )
        elif rule_id not in decision_rule_ids:
            results.append(
                _result(
                    rule_id=rule_id,
                    status=status,
                    reason_code=reason_code,
                    prompt_tokens=prompt_tokens,
                    completion_tokens=completion_tokens,
                    total_tokens=total_tokens,
                )
            )
    return NativeConsultationEpisodeExecutionResult(
        results=tuple(results),
        planned_rule_ids=selected,
        decisions=tuple(decisions),
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
    explicit_decision_document_refs: Mapping[str, Sequence[str]],
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
    decisions: list[RuleDecision] = []
    material_binding_failure_rule_ids: set[str] = set()
    if evidence_snapshot is not None:
        for rule_id in selected:
            if rule_id not in decision_rule_ids:
                continue
            try:
                fact_refs = material_refs_for_internal_refs(
                    documents=documents,
                    candidates=(
                        execution_projection.candidates
                        if execution_projection is not None
                        else ()
                    ),
                    internal_refs=explicit_decision_document_refs.get(rule_id, ()),
                )
            except Exception as exc:
                if not is_material_binding_error(exc):
                    raise
                material_binding_failure_rule_ids.add(rule_id)
                decisions.append(
                    _decision(
                        rule_id=rule_id,
                        status="technical_error",
                        reason_code="snapshot_mismatch",
                        snapshot=evidence_snapshot,
                    )
                )
                continue
            decisions.append(
                _decision(
                    rule_id=rule_id,
                    status=statuses[rule_id][0],
                    reason_code=statuses[rule_id][1],
                    snapshot=evidence_snapshot,
                    fact_refs=fact_refs,
                )
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
        facts: dict[str, Any]
        if rule_id in {"LX0609-021", "LX0609-022"}:
            facts = {
                "verification_kind": (
                    "consultation_application_quality_check"
                    if rule_id == "LX0609-021"
                    else "consultation_opinion_quality_check"
                ),
                "episode_count": len(documents),
                "document_count": len(documents),
                "semantic_state": "clear" if status == "compliant" else "mixed",
                "checked_requirement": (
                    "说明具体临床问题、会诊理由或明确会诊目的"
                    if rule_id == "LX0609-021"
                    else "给出针对当前病情的明确诊疗意见"
                ),
                "source_document_ids": list(source_document_ids),
                "episode_results": [
                    {
                        "episode_index": index,
                        "semantic_state": "clear" if status == "compliant" else "unknown",
                        "source_document_id": _clean(document.get("document_id")),
                        "record_time": _clean(document.get("time")),
                        "document_title": "会诊申请单" if rule_id == "LX0609-021" else "会诊记录单",
                    }
                    for index, document in enumerate(documents, start=1)
                ],
            }
        else:
            facts = {
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
    safe_display_facts, invalid_fact_rule_ids = _safe_customer_display_facts(
        tuple(
            item
            for item in display_facts
            if item[0] not in material_binding_failure_rule_ids
        )
    )
    if invalid_fact_rule_ids:
        results = [
            (
                _result(
                    rule_id=item["rule_id"],
                    status="technical_error",
                    reason_code="model_invalid_output",
                    prompt_tokens=0,
                    completion_tokens=0,
                    total_tokens=0,
                )
                if item["rule_id"] in invalid_fact_rule_ids
                else item
            )
            for item in results
        ]
        decisions = [
            (
                _decision(
                    rule_id=item.rule_id,
                    status="technical_error",
                    reason_code="model_invalid_output",
                    snapshot=evidence_snapshot,
                )
                if item.rule_id in invalid_fact_rule_ids
                else item
            )
            for item in decisions
        ]
    return NativeConsultationEpisodeExecutionResult(
        results=tuple(results),
        planned_rule_ids=selected,
        decisions=tuple(decisions),
        customer_display_facts=safe_display_facts,
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
        try:
            non_target_refs = material_refs_for_internal_refs(
                documents=documents,
                candidates=(),
                internal_refs=tuple(
                    _clean(document.get("ref"))
                    for document in documents
                    if _clean(document.get("ref"))
                ),
            )
        except Exception as exc:
            if not is_material_binding_error(exc):
                raise
            return NativeConsultationEpisodeExecutionResult(
                results=tuple(
                    _result(
                        rule_id=rule_id,
                        status="not_applicable",
                        reason_code="eligibility_not_met",
                        prompt_tokens=0,
                        completion_tokens=0,
                        total_tokens=0,
                    )
                    for rule_id in selected
                    if rule_id not in typed
                ),
                planned_rule_ids=selected,
                decisions=tuple(
                    _decision(
                        rule_id=rule_id,
                        status="technical_error",
                        reason_code="snapshot_mismatch",
                        snapshot=evidence_snapshot,
                    )
                    for rule_id in selected
                    if rule_id in typed and evidence_snapshot is not None
                ),
            )
        return _finish(
            selected=selected,
            status="not_applicable",
            reason_code="eligibility_not_met",
            evidence_snapshot=evidence_snapshot,
            decision_rule_ids=typed,
            fact_refs_by_rule={rule_id: non_target_refs for rule_id in typed},
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
    explicit_decision_document_refs: dict[str, tuple[str, ...]] = {}
    explicit_statuses = _strong_explicit_consultation_statuses(
        selected=selected,
        documents=documents,
        execution_projection=explicit_execution_projection,
        decision_document_refs=explicit_decision_document_refs,
    )
    if all(rule_id in explicit_statuses for rule_id in selected):
        return _finish_explicit_statuses(
            selected=selected,
            statuses=explicit_statuses,
            documents=documents,
            execution_projection=explicit_execution_projection,
            evidence_snapshot=evidence_snapshot,
            decision_rule_ids=typed,
            explicit_decision_document_refs=explicit_decision_document_refs,
        )
    explicit_022_documents = (
        _explicit_embedded_opinion_documents(documents)
        if "LX0609-022" in selected
        else ()
    )
    if llm_client is None:
        return _finish(selected=selected, status="technical_error", reason_code="model_transport_error", evidence_snapshot=evidence_snapshot, decision_rule_ids=typed)
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
        invalid_statuses = {
            rule_id: ("technical_error", "model_invalid_output")
            for rule_id in selected
        }
        return _finish_statuses(
            selected=selected,
            statuses=invalid_statuses,
            calls=calls,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
            api_time=api_time,
            evidence_snapshot=evidence_snapshot,
            decision_rule_ids=typed,
        )
    except Exception:
        return _finish(selected=selected, status="technical_error", reason_code="model_transport_error", calls=calls, evidence_snapshot=evidence_snapshot, decision_rule_ids=typed)
    statuses: dict[str, tuple[str, str]] = {
        rule_id: _outcome(rule_id, episodes)
        for rule_id in selected
        if rule_id in {"LX0609-021", "LX0609-022"}
    }
    if explicit_022_documents:
        # 022 的高置信逐份正文事实独立于同族 020/021/023。批量执行仍只调用
        # 原有语义链处理其余规则，但模型不得覆盖已经由正文确定的 022 结论。
        statuses["LX0609-022"] = ("compliant", "requirement_satisfied")
    execution_assessments: tuple[_ExecutionAssessment, ...] | None = None
    execution_source_technical = False
    execution_source_incomplete_keys: frozenset[str] = frozenset()
    context_only_candidate_present = False
    execution_candidate_projection: _CandidateProjection | None = None
    completed_recommendations: tuple[_CompletedRecommendation, ...] = ()
    embedded_decision_refs: frozenset[str] = frozenset()
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
                    statuses[rule_id] = ("technical_error", "model_invalid_output")
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
                documents_by_ref = {
                    _clean(item.get("ref")): item for item in documents
                }
                embedded_decision_refs = frozenset({
                    ref
                    for item in episodes
                    for ref in item.opinion_refs
                    if ref in documents_by_ref
                    and _EMBEDDED_DECISION_COMMUNICATION_PATTERN.search(
                        _clean(documents_by_ref[ref].get("text"))
                    )
                    and _EMBEDDED_DECISION_DEFER_PATTERN.search(
                        _clean(documents_by_ref[ref].get("text"))
                    )
                })
                embedded_candidates = tuple(
                    _CandidateDocument(
                        ref,
                        "consultation_record",
                        observed_time,
                        _clean(documents_by_ref[ref].get("text")),
                        _clean(documents_by_ref[ref].get("document_id")),
                    )
                    for ref in embedded_decision_refs
                    if (
                        observed_time := _parse_observed_time(
                            documents_by_ref[ref].get("time")
                        )
                    ) is not None
                )
                if embedded_candidates:
                    projection = replace(
                        projection,
                        candidates=projection.candidates + embedded_candidates,
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
                        exhausted_missing_refs: set[str] = set()
                        calls += 1
                        retry_attempted = False
                        try:
                            started = time.perf_counter()
                            try:
                                response = await llm_client.generate(second_prompt)
                            except Exception as first_error:
                                api_time += time.perf_counter() - started
                                if not _is_retryable_execution_transport_failure(first_error):
                                    raise
                                calls += 1
                                retry_attempted = True
                                retry_started = time.perf_counter()
                                try:
                                    response = await llm_client.generate(second_prompt)
                                except Exception:
                                    api_time += time.perf_counter() - retry_started
                                    raise
                                started = retry_started
                            if not isinstance(response, Mapping):
                                raise _SemanticInvalid()
                            next_prompt, next_completion, next_total, response_time = _usage(response)
                            prompt_tokens += next_prompt
                            completion_tokens += next_completion
                            total_tokens += next_total
                            api_time += response_time or (time.perf_counter() - started)
                            stage_two_payload = _payload(response)
                            try:
                                try:
                                    execution_assessments = _parse_executions(
                                        stage_two_payload,
                                        completed=completed_recommendations,
                                        allowed_refs=allowed_refs,
                                        candidates=projection.candidates,
                                    )
                                except _SemanticInvalid as semantic_error:
                                    if (
                                        not semantic_error.retryable_stage_two_once
                                        or retry_attempted
                                    ):
                                        raise
                                    # 只对 HTTP 已成功后的纯响应形状错误或候选外
                                    # ref 做一次同 Prompt 重试。后者只容忍模型偶发
                                    # 抄错；第二响应仍须完整通过相同安全合同。
                                    # 身份和引用结构错误始终直接失败。
                                    calls += 1
                                    retry_attempted = True
                                    semantic_retry_started = time.perf_counter()
                                    try:
                                        semantic_retry_response = (
                                            await llm_client.generate(second_prompt)
                                        )
                                    except Exception:
                                        api_time += (
                                            time.perf_counter()
                                            - semantic_retry_started
                                        )
                                        raise
                                    if not isinstance(
                                        semantic_retry_response, Mapping
                                    ):
                                        api_time += (
                                            time.perf_counter()
                                            - semantic_retry_started
                                        )
                                        raise _SemanticInvalid()
                                    (
                                        semantic_prompt_tokens,
                                        semantic_completion_tokens,
                                        semantic_total_tokens,
                                        semantic_response_time,
                                    ) = _usage(semantic_retry_response)
                                    prompt_tokens += semantic_prompt_tokens
                                    completion_tokens += semantic_completion_tokens
                                    total_tokens += semantic_total_tokens
                                    api_time += semantic_response_time or (
                                        time.perf_counter()
                                        - semantic_retry_started
                                    )
                                    execution_assessments = _parse_executions(
                                        _payload(semantic_retry_response),
                                        completed=completed_recommendations,
                                        allowed_refs=allowed_refs,
                                        candidates=projection.candidates,
                                    )
                            except _ExecutionCoverageIncomplete as incomplete:
                                # 模型偶发只漏回一部分建议。只把缺失建议连同其
                                # 受控候选重问一次；首轮合法结果不重复发送，也不
                                # 把缺项默认解释为未执行。补问失败或仍不完整时，
                                # 保留两轮已经通过合同的建议，只有未闭合项降为
                                # unknown，避免一个缺项抹掉同批合法事实。
                                missing_completed = tuple(
                                    item
                                    for item in completed_recommendations
                                    if item.recommendation.recommendation_ref
                                    in incomplete.missing_refs
                                )
                                completed_missing_assessments: tuple[
                                    _ExecutionAssessment, ...
                                ] = ()
                                if not retry_attempted:
                                    missing_prompt, missing_allowed_refs = (
                                        _execution_prompt(
                                            completed=missing_completed,
                                            candidates=projection.candidates,
                                        )
                                    )
                                    calls += 1
                                    missing_started = time.perf_counter()
                                    missing_time_recorded = False
                                    try:
                                        missing_response = await llm_client.generate(
                                            missing_prompt
                                        )
                                        missing_elapsed = (
                                            time.perf_counter() - missing_started
                                        )
                                        if not isinstance(missing_response, Mapping):
                                            api_time += missing_elapsed
                                            missing_time_recorded = True
                                            raise _SemanticInvalid()
                                        (
                                            missing_prompt_tokens,
                                            missing_completion_tokens,
                                            missing_total_tokens,
                                            missing_response_time,
                                        ) = _usage(missing_response)
                                        prompt_tokens += missing_prompt_tokens
                                        completion_tokens += missing_completion_tokens
                                        total_tokens += missing_total_tokens
                                        api_time += (
                                            missing_response_time or missing_elapsed
                                        )
                                        missing_time_recorded = True
                                        try:
                                            completed_missing_assessments = (
                                                _parse_executions(
                                                    _payload(missing_response),
                                                    completed=missing_completed,
                                                    allowed_refs=missing_allowed_refs,
                                                    candidates=projection.candidates,
                                                )
                                            )
                                        except _ExecutionCoverageIncomplete as retry_incomplete:
                                            completed_missing_assessments = (
                                                retry_incomplete.parsed
                                            )
                                    except Exception:
                                        if not missing_time_recorded:
                                            api_time += (
                                                time.perf_counter() - missing_started
                                            )
                                assessment_by_ref = {
                                    item.recommendation_ref: item
                                    for item in (
                                        *incomplete.parsed,
                                        *completed_missing_assessments,
                                    )
                                }
                                for missing_item in missing_completed:
                                    missing_ref = (
                                        missing_item.recommendation.recommendation_ref
                                    )
                                    if missing_ref not in assessment_by_ref:
                                        assessment_by_ref[missing_ref] = (
                                            _unknown_execution_assessment(missing_ref)
                                        )
                                        exhausted_missing_refs.add(missing_ref)
                                execution_assessments = tuple(
                                    assessment_by_ref[
                                        item.recommendation.recommendation_ref
                                    ]
                                    for item in completed_recommendations
                                )
                            conflict_refs = {
                                item.recommendation_ref
                                for item in execution_assessments
                                if item.confidence == "high"
                                and _generic_trace_conflicts_with_completed_action(
                                    item, projection.candidates
                                )
                            }
                            if conflict_refs:
                                # 具体执行原文与“笼统记录”标签冲突时只复核该建议；
                                # 复核失败保留中置信事实，由状态机收敛为 uncertain。
                                execution_assessments = tuple(
                                    replace(item, confidence="medium")
                                    if item.recommendation_ref in conflict_refs
                                    else item
                                    for item in execution_assessments
                                )
                            low_confidence_refs = {
                                item.recommendation_ref
                                for item in execution_assessments
                                if item.confidence != "high"
                                and item.recommendation_ref
                                not in exhausted_missing_refs
                            }
                            if low_confidence_refs and not retry_attempted:
                                # 只对首轮明确标为中/低信心的建议做一次
                                # 最小上下文重问；已高信心的其他建议不重复投递。
                                recheck_completed = tuple(
                                    item
                                    for item in completed_recommendations
                                    if item.recommendation.recommendation_ref
                                    in low_confidence_refs
                                )
                                try:
                                    recheck_prompt, recheck_allowed_refs = _execution_prompt(
                                        completed=recheck_completed,
                                        candidates=projection.candidates,
                                    )
                                    calls += 1
                                    recheck_started = time.perf_counter()
                                    recheck_response = await llm_client.generate(recheck_prompt)
                                    if not isinstance(recheck_response, Mapping):
                                        raise _SemanticInvalid()
                                    (
                                        recheck_prompt_tokens,
                                        recheck_completion_tokens,
                                        recheck_total_tokens,
                                        recheck_response_time,
                                    ) = _usage(recheck_response)
                                    prompt_tokens += recheck_prompt_tokens
                                    completion_tokens += recheck_completion_tokens
                                    total_tokens += recheck_total_tokens
                                    api_time += recheck_response_time or (
                                        time.perf_counter() - recheck_started
                                    )
                                    rechecked = _parse_executions(
                                        _payload(recheck_response),
                                        completed=recheck_completed,
                                        allowed_refs=recheck_allowed_refs,
                                        candidates=projection.candidates,
                                    )
                                    rechecked_by_ref = {
                                        item.recommendation_ref: item for item in rechecked
                                    }
                                    execution_assessments = tuple(
                                        _merge_rechecked_execution_assessment(
                                            item,
                                            rechecked_by_ref[item.recommendation_ref],
                                        )
                                        if item.recommendation_ref in rechecked_by_ref
                                        else item
                                        for item in execution_assessments
                                    )
                                except Exception:
                                    # 语义复核只用于提升个别低信心事实；其失败
                                    # 不得覆盖首轮可交付的其他建议。
                                    pass
                        except _SemanticInvalid as semantic_error:
                            logger.warning(
                                "consultation_stage_two_invalid "
                                "stage_two_invalid_kind=%s retry_attempted=%s",
                                semantic_error.kind.value,
                                retry_attempted,
                            )
                            for rule_id in stage_two_rule_ids:
                                statuses[rule_id] = (
                                    "technical_error",
                                    "model_invalid_output",
                                )
                        except Exception as error:
                            logger.warning(
                                "consultation_stage_two_failed "
                                "stage_two_failure_kind=%s retry_attempted=%s "
                                "exception_type=%s exception_module=%s exception_origin=%s",
                                _stage_two_failure_kind(error),
                                retry_attempted,
                                type(error).__name__,
                                _stage_two_exception_module(error),
                                _stage_two_exception_origin(error),
                            )
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
            execution_assessments = _apply_embedded_decision_traces(
                execution_assessments,
                completed=completed_recommendations,
                embedded_refs=embedded_decision_refs,
            )
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
        item = _result(
            rule_id=rule_id,
            status=status,
            reason_code=reason,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
            link_diagnostics=link_diagnostics,
        )
        if rule_id == "LX0609-022" and explicit_022_documents:
            item["metadata"]["executor_type"] = "program"
        results.append(item)
    decisions: list[RuleDecision] = []
    material_binding_failure_rule_ids: set[str] = set()
    if evidence_snapshot is not None:
        for rule_id in selected:
            if rule_id not in typed:
                continue
            try:
                fact_refs = select_consultation_rule_material_refs(
                    rule_id=rule_id,
                    status=statuses[rule_id][0],
                    reason_code=statuses[rule_id][1],
                    documents=documents,
                    episodes=episodes,
                    completed_recommendations=completed_recommendations,
                    assessments=execution_assessments,
                    candidates=(
                        execution_candidate_projection.candidates
                        if execution_candidate_projection is not None
                        else ()
                    ),
                )
            except Exception as exc:
                if not is_material_binding_error(exc):
                    raise
                material_binding_failure_rule_ids.add(rule_id)
                decisions.append(
                    _decision(
                        rule_id=rule_id,
                        status="technical_error",
                        reason_code="snapshot_mismatch",
                        snapshot=evidence_snapshot,
                    )
                )
                continue
            decisions.append(
                _decision(
                    rule_id=rule_id,
                    status=statuses[rule_id][0],
                    reason_code=statuses[rule_id][1],
                    snapshot=evidence_snapshot,
                    fact_refs=fact_refs,
                )
            )
    display_facts: list[tuple[str, Mapping[str, Any]]] = []
    for rule_id in ("LX0609-021", "LX0609-022"):
        if rule_id in selected and rule_id in statuses:
            display_facts.append(
                (
                    rule_id,
                    (
                        _explicit_embedded_opinion_display_facts(
                            explicit_022_documents
                        )
                        if rule_id == "LX0609-022" and explicit_022_documents
                        else _consultation_semantic_display_facts(
                            rule_id=rule_id,
                            episodes=episodes,
                            documents=documents,
                        )
                    ),
                )
            )
    for rule_id in ("LX0609-020", "LX0609-023"):
        if rule_id not in selected or rule_id not in statuses:
            continue
        display_facts.append(
            (
                rule_id,
                _consultation_execution_display_facts(
                    rule_id=rule_id,
                    status=statuses[rule_id][0],
                    episodes=episodes,
                    completed_recommendations=completed_recommendations,
                    assessments=execution_assessments,
                    documents=documents,
                    candidates=(
                        execution_candidate_projection.candidates
                        if execution_candidate_projection is not None
                        else ()
                    ),
                ),
            )
        )
    safe_display_facts, invalid_fact_rule_ids = _safe_customer_display_facts(
        tuple(
            item
            for item in display_facts
            if item[0] not in material_binding_failure_rule_ids
        )
    )
    failed_rule_ids = material_binding_failure_rule_ids | set(invalid_fact_rule_ids)
    if failed_rule_ids:
        results = [
            (
                _result(
                    rule_id=item["rule_id"],
                    status="technical_error",
                    reason_code=(
                        "snapshot_mismatch"
                        if item["rule_id"] in material_binding_failure_rule_ids
                        else "model_invalid_output"
                    ),
                    prompt_tokens=prompt_tokens,
                    completion_tokens=completion_tokens,
                    total_tokens=total_tokens,
                    link_diagnostics=link_diagnostics,
                )
                if item["rule_id"] in failed_rule_ids
                else item
            )
            for item in results
        ]
        decisions = [
            (
                _decision(
                    rule_id=item.rule_id,
                    status="technical_error",
                    reason_code=(
                        "snapshot_mismatch"
                        if item.rule_id in material_binding_failure_rule_ids
                        else "model_invalid_output"
                    ),
                    snapshot=evidence_snapshot,
                )
                if item.rule_id in failed_rule_ids
                else item
            )
            for item in decisions
        ]
    diagnostic_semantic_snapshot = _build_diagnostic_semantic_snapshot(
        documents=documents,
        episodes=episodes,
        statuses=statuses,
    )
    return NativeConsultationEpisodeExecutionResult(
        results=tuple(item for item in results if item["rule_id"] not in typed), planned_rule_ids=selected,
        decisions=tuple(decisions), customer_display_facts=safe_display_facts,
        diagnostic_semantic_snapshot=diagnostic_semantic_snapshot,
        llm_call_count=calls,
        prompt_tokens=prompt_tokens, completion_tokens=completion_tokens,
        total_tokens=total_tokens, api_time=api_time,
    )
