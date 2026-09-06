"""LX0609-040 原生四级手术 MDT 门控：结构化适用性优先，裁剪 LLM 只判灰区。"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import json
import re
from typing import Any, Mapping, Protocol, Sequence

from .decision_model import (
    ApplicabilityState,
    EvidenceState,
    QcDirection,
    RuleDecision,
)
from .evidence_material import Luxian0609EvidenceMaterialStore
from .evidence_snapshot import Luxian0609EvidenceSnapshot
from .native_execution import build_luxian_0609_native_result
from .source_evidence_reader import (
    read_luxian_0609_native_source_rows,
)
from .surgery_applicability import resolve_surgery_applicability
from .surgery_procedure_catalog import catalog_surgery_state, effective_surgery_level


RULE_ID = "LX0609-040"
LEGACY_RULE_IDS = ("SC-083", "CL-108")
_COMPLETED_MDT_PATTERN = re.compile(
    r"多学科会诊记录|经多学科(?:讨论|会诊)[^。；]{0,160}(?:一致认为|讨论后|会诊后)|"
    r"MDT讨论[^。；]{0,160}(?:一致认为|可手术|结论)",
    re.IGNORECASE,
)
_ROSTER_SECTION_PATTERN = re.compile(r"主持人签名[\s\S]{0,700}?病史汇报")
_ANESTHESIA_ROSTER_PATTERN = re.compile(
    r"(?:麻醉科\s*[\u4e00-\u9fff·]{1,8}|[\u4e00-\u9fff·]{1,8}\s*麻醉)"
    r"(?:主任医师|副主任医师|主治医师|住院医师|医师|医生)"
)
_PHYSICIAN_TITLE_PATTERN = re.compile(
    r"主任医师|副主任医师|主治医师|住院医师|医师|医生"
)
_COMPLETED_DISCUSSION_PATTERN = re.compile(
    r"手术指征|讨论意见|讨论结论|讨论后|同意(?:上述)?意见|手术方案"
)
_PLANNED_PARTICIPANT_PATTERN = re.compile(r"拟请|拟邀请|计划请|计划邀请|建议请|待请")
_ROSTER_PLACEHOLDER_PATTERN = re.compile(
    r"待填|未填|待定|暂无|未知|空缺|某某|姓名|^无$"
)
_CLINICAL_NARRATIVE_TERMS = (
    "患者",
    "诊断",
    "检查",
    "入院",
    "病史",
    "查体",
    "治疗",
    "手术",
    "风险",
    "指征",
    "讨论",
    "认为",
    "分析",
    "建议",
    "方案",
)
_PROJECTION_PATTERN = re.compile(
    r"MDT|多学科|多科|联合会诊|联合讨论|术前讨论|参加人员|参与人员|讨论人员|"
    r"会诊医师|主持|讨论意见|讨论结论|一致认为|麻醉科|科室",
    re.IGNORECASE,
)
_MAX_DOCUMENT_CHARS = 3000
_MAX_CONTEXT_CHARS = 6200
_TYPED_EVALUATOR_VERSION = "mdt-ruledecision-shadow-v2"
_DECISION_SOURCE_KEYS = frozenset(
    {"mr_surgery", "presurg_discussion", "consultation_record"}
)
_EMERGENCY_SURGERY_PATTERN = re.compile(
    r"(?:今日|本次|当日)?(?:急诊手术|急诊抢救|紧急手术|紧急抢救)|"
    r"(?:为|因|系)?紧急.{0,12}(?:抢救|挽救生命|救命)|"
    r"手术时间\s*[:：]?\s*今日急诊",
    re.IGNORECASE,
)
_NON_EMERGENCY_SURGERY_PATTERN = re.compile(
    r"(?:非|不是|不属于|排除).{0,8}(?:急诊|紧急|抢救)"
)


class MdtLLMClient(Protocol):
    async def generate(self, prompt: str) -> dict[str, Any]: ...


@dataclass(frozen=True)
class NativeMdtExecutionResult:
    result: dict[str, Any] | None
    decisions: tuple[RuleDecision, ...] = ()
    customer_display_facts: tuple[tuple[str, Mapping[str, Any]], ...] = ()
    llm_call_count: int = 0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    api_time: float = 0.0


@dataclass(frozen=True)
class _MdtRuleOutcome:
    status: str
    finding_kind: str
    reason_code: str
    executor_type: str = "program"


def native_mdt_rule_selected(
    *, wrapper_rules: Sequence[Mapping[str, Any]], prepared_rule_ids: set[str]
) -> bool:
    """仅当正式入口选择了 040 客户 ID 或其两条历史执行 ID 时启用。"""
    for wrapper in wrapper_rules:
        rule_id = _clean(wrapper.get("rule_id") or wrapper.get("rule_code")).upper()
        mapped = {
            _clean(value).upper()
            for value in list(wrapper.get("mapped_rule_ids") or [])
            if _clean(value)
        }
        if rule_id == RULE_ID and (
            RULE_ID in prepared_rule_ids or mapped.intersection(prepared_rule_ids)
        ):
            return True
    return False


def _clean(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def _parse_datetime(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        return value.replace(tzinfo=None)
    text = _clean(value)
    if not text:
        return None
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).replace(tzinfo=None)
    except ValueError:
        return None


def _original_texts(value: Any) -> tuple[str, ...]:
    try:
        payload = json.loads(value) if isinstance(value, str) else value
    except (TypeError, ValueError):
        return ()
    found: list[str] = []

    def walk(item: Any) -> None:
        if isinstance(item, Mapping):
            for key, nested in item.items():
                if (
                    key == "original_text"
                    and isinstance(nested, str)
                    and _clean(nested)
                ):
                    found.append(_clean(nested))
                else:
                    walk(nested)
        elif isinstance(item, list):
            for nested in item:
                walk(nested)

    walk(payload)
    return tuple(dict.fromkeys(found))


def _document_text(row: Mapping[str, Any]) -> str:
    parts = (
        row.get("document_title"),
        row.get("record_content"),
        row.get("host_name"),
        row.get("host_summary"),
        row.get("discuss_staff"),
        *_original_texts(row.get("v2_schema")),
    )
    return "\n".join(dict.fromkeys(text for value in parts if (text := _clean(value))))


def _project_document(text: str) -> str:
    chunks: list[str] = []

    def add(value: str) -> None:
        candidate = value.strip()
        if candidate and candidate not in chunks:
            chunks.append(candidate)

    add(text[:450])
    add(text[-500:])
    for match in list(_PROJECTION_PATTERN.finditer(text))[:12]:
        add(text[max(0, match.start() - 220) : min(len(text), match.end() + 480)])
    return "\n…\n".join(chunks)[:_MAX_DOCUMENT_CHARS]


def _has_completed_multidepartment_roster(text: str) -> bool:
    """识别术前讨论参会名单中的麻醉医师；不把麻醉方式或拟请会诊当参会。"""
    roster_match = _ROSTER_SECTION_PATTERN.search(text)
    if roster_match is None:
        return False
    roster = roster_match.group(0)
    actual_anesthesiologist = False
    for match in _ANESTHESIA_ROSTER_PATTERN.finditer(roster):
        leading = roster[max(0, match.start() - 8) : match.start()]
        if _PLANNED_PARTICIPANT_PATTERN.search(leading + match.group(0)):
            continue
        compact = re.sub(r"\s+", "", match.group(0))
        if compact.startswith("麻醉科"):
            name = compact[len("麻醉科") :]
        else:
            name = compact.split("麻醉", 1)[0]
        name = _PHYSICIAN_TITLE_PATTERN.sub("", name)
        if not name or _ROSTER_PLACEHOLDER_PATTERN.search(name):
            continue
        actual_anesthesiologist = True
        break
    narrative = _clean(text[roster_match.end() :])
    unique_chinese_chars = {char for char in narrative if "\u4e00" <= char <= "\u9fff"}
    clinical_term_count = sum(term in narrative for term in _CLINICAL_NARRATIVE_TERMS)
    return bool(
        actual_anesthesiologist
        and len(_PHYSICIAN_TITLE_PATTERN.findall(roster)) >= 2
        and len(narrative) >= 100
        and len(unique_chinese_chars) >= 80
        and clinical_term_count >= 3
        and (_COMPLETED_DISCUSSION_PATTERN.search(text) or "术前讨论" in text)
    )


def _llm_text(response: Mapping[str, Any]) -> str:
    choices = response.get("choices")
    if isinstance(choices, list) and choices and isinstance(choices[0], Mapping):
        message = choices[0].get("message")
        if isinstance(message, Mapping):
            return str(message.get("content") or "")
    return str(response.get("content") or response.get("text") or "")


def _llm_payload(response: Mapping[str, Any]) -> dict[str, Any] | None:
    cleaned = re.sub(
        r"<think>[\s\S]*?</think>", "", _llm_text(response), flags=re.IGNORECASE
    ).strip()
    match = re.search(r"\{[\s\S]*\}", cleaned)
    if not match:
        return None
    try:
        payload = json.loads(match.group(0))
    except (TypeError, ValueError):
        return None
    return dict(payload) if isinstance(payload, Mapping) else None


def _usage(response: Mapping[str, Any]) -> tuple[int, int, int, float]:
    usage = response.get("usage")
    usage = usage if isinstance(usage, Mapping) else {}
    prompt = int(usage.get("prompt_tokens") or 0)
    completion = int(usage.get("completion_tokens") or 0)
    total = int(usage.get("total_tokens") or prompt + completion)
    api_time = float(response.get("_api_time") or 0.0)
    return prompt, completion, total, api_time


def _result(
    *,
    status: str,
    finding_kind: str,
    reason_code: str,
    executor_type: str = "program",
    prompt_tokens: int = 0,
    completion_tokens: int = 0,
    total_tokens: int = 0,
    api_time: float = 0.0,
) -> dict[str, Any]:
    result = build_luxian_0609_native_result(
        rule_id=RULE_ID,
        final_state=status,
        finding_kind=finding_kind,
        reason_code=reason_code,
    )
    metadata = dict(result.get("metadata") or {})
    metadata.update(
        {
            "executor_type": executor_type,
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": total_tokens,
            "api_time": api_time,
        }
    )
    result["metadata"] = metadata
    return result


def _typed_source_blockers(
    snapshot: Luxian0609EvidenceSnapshot,
) -> tuple[_MdtRuleOutcome | None, _MdtRuleOutcome | None]:
    """区分手术触发源的终局阻塞与MDT文书源的条件阻塞。"""

    observations = {item.source_key: item for item in snapshot.observations}
    trigger = observations.get("mr_surgery")
    if trigger is None:
        return (
            _MdtRuleOutcome(
                "technical_error", "technical_failure", "snapshot_mismatch"
            ),
            None,
        )
    if trigger.query_state.value == "error":
        return (
            _MdtRuleOutcome(
                "technical_error", "technical_failure", "source_query_error"
            ),
            None,
        )
    if trigger.query_state.value == "unavailable":
        return (
            _MdtRuleOutcome("data_gap", "data_gap", "source_unavailable"),
            None,
        )
    if trigger.completeness.value == "truncated":
        return (
            _MdtRuleOutcome("data_gap", "data_gap", "source_truncated"),
            None,
        )

    conditional: _MdtRuleOutcome | None = None
    for source_key in ("presurg_summary", "presurg_discussion", "consultation_record"):
        observation = observations.get(source_key)
        if observation is None:
            return (
                _MdtRuleOutcome(
                    "technical_error", "technical_failure", "snapshot_mismatch"
                ),
                None,
            )
        if observation.query_state.value == "error":
            conditional = _MdtRuleOutcome(
                "technical_error", "technical_failure", "source_query_error"
            )
        elif observation.query_state.value == "unavailable":
            conditional = conditional or _MdtRuleOutcome(
                "data_gap", "data_gap", "source_unavailable"
            )
        elif observation.completeness.value == "truncated":
            conditional = conditional or _MdtRuleOutcome(
                "data_gap", "data_gap", "source_truncated"
            )
    return None, conditional


def _is_emergency_surgery_text(text: str) -> bool:
    """只接受明确的急诊/紧急抢救表述，排除“非急诊”等否定语句。"""

    normalized = _clean(text)
    return bool(
        normalized
        and _EMERGENCY_SURGERY_PATTERN.search(normalized)
        and not _NON_EMERGENCY_SURGERY_PATTERN.search(normalized)
    )


def _has_emergency_surgery_exception(
    *,
    materials: Luxian0609EvidenceMaterialStore,
) -> bool:
    """从同一 Evidence Session 的术前小结/手术主表读取040豁免事实。"""

    for source_key in ("presurg_summary", "mr_surgery"):
        for row in materials.rows(source_key):
            text = _document_text(row)
            if _is_emergency_surgery_text(text):
                return True
    return False


def _typed_decision_from_outcome(
    *,
    outcome: _MdtRuleOutcome,
    snapshot: Luxian0609EvidenceSnapshot,
) -> RuleDecision:
    """直接从040内核结果生成安全决策，不经过客户结果DTO。"""

    refs = tuple(
        observation.snapshot_ref.removeprefix("sha256:")
        for observation in snapshot.observations
        if observation.source_key in _DECISION_SOURCE_KEYS
    )
    if outcome.status in {"compliant", "non_compliant", "not_applicable"} and not refs:
        raise ValueError("typed mdt decision requires evidence refs")
    if outcome.status == "compliant":
        dimensions = (
            ApplicabilityState.APPLICABLE,
            EvidenceState.SUFFICIENT,
            QcDirection.SATISFIED,
            "requirement_satisfied",
        )
    elif outcome.status == "non_compliant":
        dimensions = (
            ApplicabilityState.APPLICABLE,
            EvidenceState.SUFFICIENT,
            QcDirection.DEFECT,
            "requirement_violated",
        )
    elif outcome.status == "not_applicable":
        dimensions = (
            ApplicabilityState.NOT_APPLICABLE,
            EvidenceState.SUFFICIENT,
            QcDirection.UNKNOWN,
            "trigger_absent_complete",
        )
    elif outcome.status == "data_gap":
        canonical_reason = (
            outcome.reason_code
            if outcome.reason_code in {"source_unavailable", "source_truncated"}
            else "required_field_missing"
        )
        dimensions = (
            ApplicabilityState.UNKNOWN,
            EvidenceState.DATA_GAP,
            QcDirection.UNKNOWN,
            canonical_reason,
        )
    elif outcome.status == "evaluation_unknown":
        dimensions = (
            ApplicabilityState.APPLICABLE,
            EvidenceState.SUFFICIENT,
            QcDirection.UNKNOWN,
            "semantic_output_unknown",
        )
    elif outcome.status == "technical_error":
        canonical_reason = (
            outcome.reason_code
            if outcome.reason_code
            in {
                "source_query_error",
                "snapshot_mismatch",
                "model_transport_error",
                "model_invalid_output",
            }
            else "executor_exception"
        )
        dimensions = (
            ApplicabilityState.ERROR,
            EvidenceState.TECHNICAL_ERROR,
            QcDirection.UNKNOWN,
            canonical_reason,
        )
    else:
        raise ValueError("unsupported mdt final state")
    applicability, evidence_state, qc_direction, reason_code = dimensions
    return RuleDecision(
        rule_id=RULE_ID,
        snapshot_hash=snapshot.snapshot_hash,
        applicability=applicability,
        evidence_state=evidence_state,
        qc_direction=qc_direction,
        reason_code=reason_code,
        fact_refs=refs,
        evaluator_version=_TYPED_EVALUATOR_VERSION,
        confidence=None,
    )


def _finalize(
    *,
    outcome: _MdtRuleOutcome,
    typed_requested: bool,
    snapshot: Luxian0609EvidenceSnapshot | None,
    conditional_blocker: _MdtRuleOutcome | None = None,
    llm_call_count: int = 0,
    prompt_tokens: int = 0,
    completion_tokens: int = 0,
    total_tokens: int = 0,
    api_time: float = 0.0,
    customer_display_facts: tuple[tuple[str, Mapping[str, Any]], ...] = (),
) -> NativeMdtExecutionResult:
    if typed_requested and conditional_blocker is not None and outcome.status in {
        "non_compliant",
        "data_gap",
        "evaluation_unknown",
    }:
        outcome = conditional_blocker
    if typed_requested:
        assert snapshot is not None
        return NativeMdtExecutionResult(
            result=None,
            decisions=(
                _typed_decision_from_outcome(outcome=outcome, snapshot=snapshot),
            ),
            customer_display_facts=customer_display_facts,
            llm_call_count=llm_call_count,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
            api_time=api_time,
        )
    return NativeMdtExecutionResult(
        result=_result(
            status=outcome.status,
            finding_kind=outcome.finding_kind,
            reason_code=outcome.reason_code,
            executor_type=outcome.executor_type,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
            api_time=api_time,
        ),
        customer_display_facts=customer_display_facts,
        llm_call_count=llm_call_count,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        total_tokens=total_tokens,
        api_time=api_time,
    )


def _prompt(*, surgery_names: Sequence[str], context: str) -> str:
    names = "、".join(name for name in surgery_names if name) or "已实施四级手术"
    return f"""你是泸县0609病历质控的事实抽取器，只判断 LX0609-040 的“该四级手术术前是否完成多学科讨论”。
严格口径：
- present：手术前同一份记录明确 MDT/多学科讨论/多学科会诊，或同一份术前讨论明确至少两个不同临床科室实际参与且有讨论意见/结论；麻醉科可算独立科室。
- absent：没有上述证据；分别进行的普通单科会诊、仅拟请相关科室、病史顺带多个科名、同一科室别名不算。
- unknown：文书截断或参与关系无法可靠判断，不得折成 absent。
输入已证明本次已实施且结构化标为四级，禁止重新猜手术级别。
只输出 JSON：{{"state":"present|absent|unknown","confidence":0.0,"reason_code":"explicit_mdt|same_discussion_multidept|ordinary_consult_only|no_qualifying_evidence|insufficient_context"}}
手术名称：{names}
术前证据窗口：
{context or "（无术前讨论/会诊文书）"}"""


async def execute_luxian_0609_native_mdt_rule(
    *,
    institute_id: str,
    patient_id: str,
    visit_id: str,
    source_schema: str | None,
    llm_client: MdtLLMClient | None,
    evidence_materials: Luxian0609EvidenceMaterialStore | None = None,
    evidence_snapshot: Luxian0609EvidenceSnapshot | None = None,
    decision_rule_ids: Sequence[str] = (),
) -> NativeMdtExecutionResult:
    """执行 040；来源缺口、模型技术失败和语义未知按合同分别返回。"""
    typed_scope = tuple(
        str(rule_id or "").strip().upper() for rule_id in decision_rule_ids
    )
    if typed_scope not in {(), (RULE_ID,)}:
        raise ValueError("unsupported typed mdt rule scope")
    typed_requested = typed_scope == (RULE_ID,)
    if typed_requested and (
        type(evidence_snapshot) is not Luxian0609EvidenceSnapshot
        or type(evidence_materials) is not Luxian0609EvidenceMaterialStore
        or evidence_materials.snapshot_hash != evidence_snapshot.snapshot_hash
    ):
        raise ValueError("typed mdt rule requires one evidence session")
    terminal_blocker: _MdtRuleOutcome | None = None
    conditional_blocker: _MdtRuleOutcome | None = None
    display_facts: dict[str, Any] = {}
    if typed_requested:
        assert evidence_snapshot is not None
        terminal_blocker, conditional_blocker = _typed_source_blockers(
            evidence_snapshot
        )

    def finish(
        outcome: _MdtRuleOutcome,
        *,
        llm_call_count: int = 0,
        prompt_tokens: int = 0,
        completion_tokens: int = 0,
        total_tokens: int = 0,
        api_time: float = 0.0,
    ) -> NativeMdtExecutionResult:
        facts = dict(display_facts)
        if facts:
            if outcome.status == "compliant":
                facts["mdt_discussion_state"] = "completed"
            elif outcome.status == "non_compliant":
                facts["mdt_discussion_state"] = "missing"
            elif outcome.status == "data_gap":
                facts["mdt_discussion_state"] = "unknown"
            elif outcome.status == "not_applicable" and facts.get("mdt_exception"):
                facts["mdt_discussion_state"] = "exempt"
        return _finalize(
            outcome=outcome,
            typed_requested=typed_requested,
            snapshot=evidence_snapshot,
            conditional_blocker=conditional_blocker,
            llm_call_count=llm_call_count,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
            api_time=api_time,
            customer_display_facts=((RULE_ID, facts),) if facts else (),
        )

    if terminal_blocker is not None:
        return finish(terminal_blocker)
    if typed_requested:
        assert evidence_snapshot is not None
        assert evidence_materials is not None
        surgery_applicability = resolve_surgery_applicability(
            snapshot=evidence_snapshot,
            materials=evidence_materials,
            source_keys=("mr_surgery",),
        )
        display_facts.update(
            {
                "performed_surgery_confirmed": (
                    surgery_applicability.state == "applicable"
                ),
                "procedure_kind": surgery_applicability.procedure_kind,
            }
        )
        if surgery_applicability.effective_level:
            display_facts["effective_surgery_level"] = (
                surgery_applicability.effective_level
            )
        if surgery_applicability.level_source:
            display_facts["surgery_level_source"] = (
                surgery_applicability.level_source
            )
        if surgery_applicability.procedure_code:
            display_facts["procedure_code"] = surgery_applicability.procedure_code
        if surgery_applicability.procedure_name:
            display_facts["procedure_name"] = surgery_applicability.procedure_name
        if surgery_applicability.state == "technical_error":
            return finish(
                _MdtRuleOutcome(
                    "technical_error", "technical_failure", "source_query_error"
                )
            )
        if surgery_applicability.state == "data_gap":
            return finish(
                _MdtRuleOutcome(
                    "data_gap", "data_gap", surgery_applicability.reason_code
                )
            )
        if surgery_applicability.state == "not_applicable":
            return finish(
                _MdtRuleOutcome(
                    "not_applicable", "trigger_absent", "performed_surgery_absent"
                )
            )
        if surgery_applicability.effective_level != "四级":
            return finish(
                _MdtRuleOutcome(
                    "not_applicable", "trigger_absent", "level4_surgery_absent"
                )
            )
        # 规则口径明确豁免“以紧急抢救生命为目的的急诊手术”。
        # 例外必须来自同一快照中的明确文本，不能仅凭急诊科室、麻醉方式
        # 或手术名称推断；命中后直接返回不适用，不再要求术前 MDT。
        if _has_emergency_surgery_exception(materials=evidence_materials):
            display_facts.update(
                {
                    "emergency_surgery_confirmed": True,
                    "mdt_exception": "emergency_lifesaving_surgery",
                }
            )
            return finish(
                _MdtRuleOutcome(
                    "not_applicable",
                    "trigger_absent",
                    "emergency_surgery_mdt_exception",
                )
            )
    if not all(
        isinstance(value, str) and value.strip()
        for value in (institute_id, patient_id, visit_id)
    ):
        return finish(
            _MdtRuleOutcome(
                "technical_error",
                "technical_failure",
                "native_coordinates_unavailable",
            )
        )
    try:
        surgeries = (
            [dict(row) for row in evidence_materials.rows("mr_surgery")]
            if evidence_materials is not None
            else read_luxian_0609_native_source_rows(
                source_key="mr_surgery",
                institute_id=institute_id,
                patient_id=patient_id,
                visit_id=visit_id,
                source_schema=source_schema,
            )
        )
    except Exception:
        return finish(
            _MdtRuleOutcome(
                "data_gap", "data_gap", "surgery_source_unavailable"
            )
        )

    performed = [
        row
        for row in surgeries
        if _parse_datetime(row.get("surgery_begin_datetime")) is not None
        and catalog_surgery_state(row) is not False
    ]
    if not performed:
        return finish(
            _MdtRuleOutcome(
                "not_applicable", "trigger_absent", "performed_surgery_absent"
            )
        )
    level4 = [
        row
        for row in performed
        if effective_surgery_level(row) == "四级"
    ]
    if not level4:
        # 040只由“四级手术”积极事实触发。等级空缺不等于四级手术，
        # 不能要求病历补充MDT材料；手术等级完整性应由其专属规则处理。
        return finish(
            _MdtRuleOutcome(
                "not_applicable", "trigger_absent", "level4_surgery_absent"
            )
        )
    trigger_refs: list[dict[str, str]] = []
    seen_trigger_ids: set[str] = set()
    for row in level4:
        source_document_id = str(
            row.get("surgery_id") or row.get("document_id") or row.get("id") or ""
        ).strip()
        if not source_document_id or source_document_id in seen_trigger_ids:
            continue
        seen_trigger_ids.add(source_document_id)
        trigger_refs.append(
            {"source_type": "mr_surgery", "source_document_id": source_document_id}
        )
        if len(trigger_refs) == 8:
            break
    if trigger_refs:
        display_facts["source_document_refs"] = trigger_refs
    level4_session_times = {
        start
        for row in level4
        if (start := _parse_datetime(row.get("surgery_begin_datetime"))) is not None
    }
    if len(level4_session_times) > 1:
        return finish(
            _MdtRuleOutcome(
                "data_gap", "data_gap", "multiple_level4_sessions_unresolved"
            )
        )

    try:
        documents: list[tuple[int, datetime, str, str]] = []
        for source_key in ("presurg_discussion", "consultation_record"):
            rows = (
                [dict(row) for row in evidence_materials.rows(source_key)]
                if evidence_materials is not None
                else read_luxian_0609_native_source_rows(
                    source_key=source_key,
                    institute_id=institute_id,
                    patient_id=patient_id,
                    visit_id=visit_id,
                    source_schema=source_schema,
                )
            )
            for row in rows:
                record_time = _parse_datetime(row.get("record_time"))
                text = _document_text(row)
                if record_time is None or not text:
                    continue
                score = (4 if _COMPLETED_MDT_PATTERN.search(text) else 0) + (
                    2 if source_key == "presurg_discussion" else 0
                )
                documents.append((score, record_time, source_key, text))
    except Exception:
        return finish(
            _MdtRuleOutcome("data_gap", "data_gap", "mdt_source_unavailable")
        )

    # 只接受在每台四级手术前出现的完成态强证据；计划性“拟请多学科”不会命中。
    strong_evidence_policies = (
        (
            "completed_mdt_strong_fact",
            lambda source, text: bool(_COMPLETED_MDT_PATTERN.search(text)),
        ),
        (
            "completed_multidepartment_roster",
            lambda source, text: (
                source == "presurg_discussion"
                and _has_completed_multidepartment_roster(text)
            ),
        ),
    )
    for reason_code, predicate in strong_evidence_policies:
        if all(
            (start := _parse_datetime(surgery.get("surgery_begin_datetime")))
            and any(
                record_time <= start and predicate(source, text)
                for _, record_time, source, text in documents
            )
            for surgery in level4
        ):
            return finish(
                _MdtRuleOutcome(
                    "compliant", "requirement_satisfied", reason_code
                )
            )

    earliest_level4 = min(
        _parse_datetime(row.get("surgery_begin_datetime")) for row in level4
    )
    eligible = [item for item in documents if item[1] <= earliest_level4]
    if not eligible:
        return finish(
            _MdtRuleOutcome(
                "non_compliant",
                "required_document_missing",
                "preoperative_mdt_absent",
            )
        )
    if llm_client is None:
        return finish(
            _MdtRuleOutcome(
                "technical_error", "technical_failure", "model_transport_error", "llm"
            )
        )

    eligible.sort(key=lambda item: (-item[0], item[1], item[2]))
    context = "\n\n".join(
        f"[{source}] {_project_document(text)}" for _, _, source, text in eligible
    )[:_MAX_CONTEXT_CHARS]
    names = tuple(
        dict.fromkeys(
            _clean(row.get("surgery_name"))
            for row in level4
            if _clean(row.get("surgery_name"))
        )
    )
    try:
        response = await llm_client.generate(
            _prompt(surgery_names=names, context=context)
        )
    except Exception:
        return finish(
            _MdtRuleOutcome(
                "technical_error", "technical_failure", "model_transport_error", "llm"
            ),
            llm_call_count=1,
        )
    if not isinstance(response, Mapping):
        return finish(
            _MdtRuleOutcome(
                "technical_error", "technical_failure", "model_invalid_output", "llm"
            ),
            llm_call_count=1,
        )
    try:
        prompt_tokens, completion_tokens, total_tokens, api_time = _usage(response)
    except (TypeError, ValueError, OverflowError):
        return finish(
            _MdtRuleOutcome(
                "technical_error", "technical_failure", "model_invalid_output", "llm"
            ),
            llm_call_count=1,
        )
    payload = _llm_payload(response)
    if payload is None or not isinstance(payload.get("state"), str):
        return finish(
            _MdtRuleOutcome(
                "technical_error", "technical_failure", "model_invalid_output", "llm"
            ),
            llm_call_count=1,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
            api_time=api_time,
        )
    state = _clean(payload["state"]).lower()
    if state == "present":
        status, kind, reason = "compliant", "requirement_satisfied", "mdt_llm_present"
    elif state == "absent":
        status, kind, reason = (
            "non_compliant",
            "required_document_missing",
            "mdt_llm_absent",
        )
    elif state == "unknown":
        status, kind, reason = (
            "evaluation_unknown",
            "semantic_uncertain",
            "semantic_output_unknown",
        )
    else:
        return finish(
            _MdtRuleOutcome(
                "technical_error", "technical_failure", "model_invalid_output", "llm"
            ),
            llm_call_count=1,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
            api_time=api_time,
        )
    return finish(
        _MdtRuleOutcome(status, kind, reason, "llm"),
        llm_call_count=1,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        total_tokens=total_tokens,
        api_time=api_time,
    )
