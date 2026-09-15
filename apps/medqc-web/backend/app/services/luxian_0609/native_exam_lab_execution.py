"""LX0609 检查检验族原生执行：多事件投影、一次事实抽取、Python 判定。"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field as dataclass_field
from datetime import datetime, timedelta
import json
import logging
import re
from typing import Any, Mapping, Protocol, Sequence, cast

from .decision_model import RuleDecision
from .evidence_material import (
    EvidenceMaterialTruncated,
    EvidenceMaterialUnavailable,
    Luxian0609EvidenceMaterialStore,
)
from .evidence_snapshot import Luxian0609EvidenceSnapshot, SourceCompleteness
from .exam_lab_event_recovery import recover_exam_lab_rule_by_event
from .exam_lab_fact_extraction import (
    ExamLabFactParseError,
    ExamLabEventFact,
    ExamLabTextProjection,
    _event_identity_mentions_course,
    build_exam_lab_fact_prompt,
    build_exam_lab_fact_response_format,
    build_exam_lab_text_projection,
    event_for_fact,
    events_for_family,
    parse_exam_lab_fact_response,
    parse_exam_lab_fact_response_isolated,
)
from .exam_lab_result_mapping import (
    ExamLabOutcome as _ExamLabOutcome,
    build_default_display_facts as _customer_display_facts_for_outcome,
    build_exam_lab_rule_decision,
    build_text_outcome_display_facts as _text_outcome_display_facts,
)
from .exam_lab_window import (
    EvaluationWindowState,
    _evaluation_window_gap_reason,
    resolve_evaluation_window_state,
)
from .exam_order_linkage import resolve_exam_master_order_ids
from .native_execution import build_luxian_0609_native_result
from .source_evidence_reader import (
    CURRENT_VISIT_DISCHARGE_HORIZON_SOURCE_KEY,
    EVALUATION_HORIZON_SOURCE_KEY,
    authoritative_document_time_value,
)


logger = logging.getLogger(__name__)


EXAM_LAB_RULE_IDS = (
    "LX0609-010",
    "LX0609-011",
    "LX0609-012",
    "LX0609-014",
    "LX0609-015",
)
EXAM_RULE_IDS = frozenset({"LX0609-010", "LX0609-011", "LX0609-012"})
CULTURE_RULE_IDS = frozenset({"LX0609-014", "LX0609-015"})
EXECUTOR_KEY = "exam_lab"
_TYPED_DECISION_RULE_IDS = frozenset(EXAM_LAB_RULE_IDS)
_TYPED_EVALUATOR_VERSION = "exam-lab-ruledecision-shadow-v2"

# LX0609-012 的客户契约允许状态（`docs/0602/luxian_0609_formal_rule_catalog.csv`
# 中含 `LX-012` 的目录行 `allowed_result_statuses`：hit; not_hit; data_quality_gap;
# not_applicable; needs_manual_review）不含 `evaluation_unknown`。运行时
# `rule_contracts.py` 的 `ALLOWED_FINAL_STATES` 是全 75 点共享词表、无权判定单
# 规则合法性，运行时也没有单规则允许状态的消费者，因此在本规则执行器内显式声明
# 012 的交付状态集合。目录词表与运行时状态的权威对应见
# `luxian_0609_result_schema.py::_STATUS_MAP`：hit→non_compliant、
# not_hit→compliant、data_quality_gap→data_gap、needs_manual_review→
# ai_suggested_non_compliant、rejected_by_gate→not_applicable。执行器自身只产出
# 前四类确定状态（ai_suggested_* 由后续人工/后处理产生），故此处集合为四项。
_LX0609_012_ALLOWED_FINAL_STATES = frozenset(
    {"compliant", "non_compliant", "not_applicable", "data_gap"}
)


def _contract_allowed_status(rule_id: str, status: str) -> str:
    """把执行结果收敛到该规则客户契约允许的交付状态。

    只有 012 会出现契约外的语义不确定：`evaluation_unknown` 不在其允许集合内，
    按客户口径以等价的资料缺口 `data_gap` 表达（原因码与客户文案全部沿用既有
    值，映射层不重写业务状态）。映射层会把内部原因码
    `exam_lab_text_fact_unknown` 收敛为 `data_gap` 允许的
    `required_field_missing`，状态与原因码同时落在契约内。
    `technical_error` 是执行失败语义、也不在本规则契约集合内，但属另一问题，
    保持原样；其它规则一律不动。
    """

    if rule_id != "LX0609-012":
        return status
    return "data_gap" if status == "evaluation_unknown" else status


_EXAM_SOURCE_KEYS = ("exam_master", "exam_item_report")
_CULTURE_SOURCE_KEYS = ("labtest_master", "labtest_item_report")
_COURSE_SOURCE_KEYS = (
    "first_course_record",
    "daily_course_record",
    "senior_course_record",
    "rescue_record",
)
_ORDER_SOURCE_KEY = "inpat_nondrug_order.exam_lab_order"
_MAX_ROWS_PER_SOURCE = 6
_MAX_ROW_CHARS = 1200
_MAX_CONTEXT_CHARS = 12000
_EXAM_FACT_TYPE = "current_visit_ct_mri_exam"
_CULTURE_FACT_TYPE = "current_visit_culture_or_ast"
_PRESENT_FACT_STATES = frozenset({"present", "performed", "available", "positive"})
_ABSENT_FACT_STATES = frozenset({"explicit_negative", "absent", "not_present"})
_MAPPING_LINE_PATTERN = re.compile(r"^.*(?:主执行规则|映射执行规则).*$", re.MULTILINE)
_STRONG_SEMANTIC_PATTERNS = {
    "LX0609-011": re.compile(
        r"(?:CT|MRI|计算机断层|磁共振|影像(?:报告|提示)?).{0,30}"
        r"(?:未见(?:明显)?异常|未见明确病变|占位|病变|梗死|出血|炎症|结节|肿块|积液|异常|突出|受压)",
        re.IGNORECASE,
    ),
    "LX0609-012": re.compile(
        r"(?:CT|MRI|计算机断层|磁共振|影像(?:报告|提示)?).{0,40}"
        r"(?:分析|考虑|结合|处理|进一步|计划)",
        re.IGNORECASE,
    ),
    "LX0609-014": re.compile(
        r"(?:培养|药敏|微生物(?:报告|结果)?).{0,40}"
        r"(?:阳性|阴性|无生长|检出.{0,16}(?:菌|病原体)|"
        r"分离出.{0,16}(?:菌|病原体)|敏感|耐药)",
    ),
    "LX0609-015": re.compile(
        r"(?:培养|药敏|菌).{0,50}(?:调整|制定|选择|更换|改用|继续|停用|抗感染|用药|处置)",
    ),
}
_CULTURE_ACTION_PATTERN = r"(?:调整|制定|选择|更换|改用|继续|停用|抗感染|用药|处置)"
_NEGATED_CULTURE_ACTION_PATTERN = re.compile(
    rf"(?:不|未|无需|暂不|尚未).{{0,3}}{_CULTURE_ACTION_PATTERN}"
)
_CONDITIONAL_CULTURE_ACTION_PATTERN = re.compile(
    rf"(?:如|若|拟|计划|待|必要时|视情况).{{0,24}}{_CULTURE_ACTION_PATTERN}"
)
_CONDITIONAL_ANALYSIS_PATTERN = re.compile(
    r"(?:如|若|拟|计划|待|必要时|视情况).{0,24}"
    r"(?:分析|考虑|结合|处理|进一步|复查|评估)"
)
_DEFINITE_ANALYSIS_PATTERN = re.compile(
    r"(?:结合.{0,24}(?:考虑|判断|提示)|分析(?:认为|提示|考虑)?|"
    r"与.{0,24}(?:相符|一致)|考虑.{0,24}(?:明确|可能|诊断))"
)
_UNCERTAIN_SEMANTIC_PATTERN = re.compile(
    r"(?:尚?未(?:回报|报告|确认)|待(?:回|报|确认|评估|定|查|进一步)|"
    r"是否|有无|不能|无法|不确定|没有|尚不能|未予)"
)
_CLAUSE_SPLIT_PATTERN = re.compile(r"[。；;\n]+")

_TYPED_TRIGGER_SOURCES = {
    "exam": ("exam_master", "exam_item_report"),
    "culture": ("labtest_master", "labtest_item_report"),
}
_TYPED_RULE_SOURCE_KEYS = {
    # 010 按省手册核对已执行检查的医嘱、病程和报告完整性。
    "LX0609-010": (*_TYPED_TRIGGER_SOURCES["exam"], _ORDER_SOURCE_KEY, *_COURSE_SOURCE_KEYS),
    "LX0609-011": (*_TYPED_TRIGGER_SOURCES["exam"], _ORDER_SOURCE_KEY, *_COURSE_SOURCE_KEYS),
    "LX0609-012": (*_TYPED_TRIGGER_SOURCES["exam"], _ORDER_SOURCE_KEY, *_COURSE_SOURCE_KEYS),
    "LX0609-014": (*_TYPED_TRIGGER_SOURCES["culture"], _ORDER_SOURCE_KEY, *_COURSE_SOURCE_KEYS),
    "LX0609-015": (*_TYPED_TRIGGER_SOURCES["culture"], _ORDER_SOURCE_KEY, *_COURSE_SOURCE_KEYS),
}
_TRIGGER_SOURCES_BY_RULE = {
    # 病程先写了 CT/MRI 而没有医嘱，同样是 010 的明确缺陷。
    "LX0609-010": (*_TYPED_TRIGGER_SOURCES["exam"], _ORDER_SOURCE_KEY, *_COURSE_SOURCE_KEYS),
    "LX0609-011": (*_TYPED_TRIGGER_SOURCES["exam"], _ORDER_SOURCE_KEY),
    "LX0609-012": (*_TYPED_TRIGGER_SOURCES["exam"], _ORDER_SOURCE_KEY),
    "LX0609-014": (*_TYPED_TRIGGER_SOURCES["culture"], _ORDER_SOURCE_KEY),
    "LX0609-015": (*_TYPED_TRIGGER_SOURCES["culture"], _ORDER_SOURCE_KEY),
}
_POST_RULE_IDS = frozenset({"LX0609-011", "LX0609-012", "LX0609-014", "LX0609-015"})
_HORIZON_SOURCE_KEYS = (
    CURRENT_VISIT_DISCHARGE_HORIZON_SOURCE_KEY,
    EVALUATION_HORIZON_SOURCE_KEY,
)
_EXAM_CONTROLLED_FIELDS = (
    "exam_type",
    "modality",
    "exam_name",
    "item_name",
    "exam_item_name",
    "performed_dept",
    "exam_result",
    "exam_impression",
    "exam_conclusion",
    "record_content",
)
_CULTURE_CONTROLLED_FIELDS = (
    "lab_type",
    "test_type",
    "subject",
    "labtest_subject",
    "item_name",
    "lab_item_name",
)
_EXAM_TRIGGER_PATTERN = re.compile(
    r"(?:^|[^A-Z])(?:CT|MRI)(?:$|[^A-Z])|计算机断层|磁共振",
    flags=re.IGNORECASE,
)
_CULTURE_TRIGGER_PATTERN = re.compile(r"(?:细菌|真菌|血|痰|尿|分泌物)?培养|药敏")
_EXAM_ORDER_NAME_PATTERN = re.compile(
    r"(?:^|[^A-Z])CT(?:$|[^A-Z])|(?:^|[^A-Z])MRI(?:$|[^A-Z])|磁共振|核磁",
    flags=re.IGNORECASE,
)
# 仅排除名称本身就是胶片/影像耗材的医嘱。带有“(含胶片)”的真实 CT/MRI
# 检查不会匹配，因为检查主体不符合此处的整串匹配条件。
_EXAM_FILM_SUPPLY_ORDER_PATTERN = re.compile(
    r"^(?:(?:CT|DR)\s*(?:[/／]\s*(?:介入|放射)\s*)?)?"
    r"(?:(?:医用\s*)?干式\s*胶片(?:\s*\d+\s*[*×xX]\s*\d+\s*(?:in|英寸|cm)?)?"
    r"|胶片\s*\d+\s*[*×xX]\s*\d+\s*(?:in|英寸|cm)?)$",
    flags=re.IGNORECASE,
)
_CANCELLED_ORDER_PATTERN = re.compile(r"撤销|作废|取消")
_RESULT_COURSE_PATTERN = re.compile(
    r"提示|显示|结果|结合|诊断意见|未见|发现|阳性|阴性|无生长|检出|分离|"
    r"血肿|出血|梗死|骨折|异常|菌|\d+\+|敏感|耐药"
)


def _is_exam_master_target(row: Mapping[str, Any]) -> bool:
    """按结构化检查字段识别当前影像，正文仅在字段全空时兜底。

    超声等非 CT/MRI 报告正文常会引用既往 MRI 片；将正文与检查名称混合
    扫描会把这类历史比较误当作当前 CT/MRI 事件并破坏医嘱关联。
    """

    identity_fields = (
        "exam_type",
        "modality",
        "exam_name",
        "item_name",
        "exam_item_name",
        "performed_dept",
    )
    if any(_clean(row.get(field)) for field in identity_fields):
        return any(
            _EXAM_TRIGGER_PATTERN.search(_clean(row.get(field)))
            for field in identity_fields
        )
    # 身份字段完全缺失时，才允许结果/结论或正文作为保守兜底信号。
    fallback_fields = tuple(
        field
        for field in _EXAM_CONTROLLED_FIELDS
        if field != "record_content"
    ) + ("record_content",)
    return any(
        _EXAM_TRIGGER_PATTERN.search(_clean(row.get(field)))
        for field in fallback_fields
    )

_CONTROLLED_MESSAGES = {
    "compliant": ("检查检验相关记录满足该项要求。", ""),
    "non_compliant": ("检查检验相关记录未满足该项要求。", "请按该质控点要求补充或修正相关记录。"),
    "not_applicable": ("当前就诊未发现该项适用的检查检验事实。", ""),
    "data_gap": ("当前检查检验资料不足，暂不能形成可靠结论。", "请补齐相关检查检验资料后重新质控。"),
}


class ExamLabLLMClient(Protocol):
    async def generate(
        self,
        prompt: str,
        *,
        enable_thinking: bool | None = None,
    ) -> dict[str, Any]: ...


class _StrictJsonSchemaExamLabClient(Protocol):
    def supports_strict_json_schema(self) -> bool: ...

    async def generate(
        self,
        prompt: str,
        *,
        response_format: Mapping[str, Any],
        enable_thinking: bool | None = None,
    ) -> dict[str, Any]: ...


@dataclass(frozen=True)
class NativeExamLabExecutionResult:
    results: tuple[dict[str, Any], ...]
    planned_rule_ids: tuple[str, ...]
    decisions: tuple[RuleDecision, ...] = ()
    customer_display_facts: tuple[tuple[str, Mapping[str, Any]], ...] = ()
    llm_call_count: int = 0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    api_time: float = 0.0
    # 仅保留受控枚举，不保存 Prompt、模型正文或病历内容。
    parse_failure_kinds: tuple[str, ...] = ()
    model_execution_stats: Mapping[str, int | float | None] = dataclass_field(default_factory=dict)


@dataclass(frozen=True)
class _TypedSource:
    state: str
    rows: tuple[Mapping[str, Any], ...] = ()
    source_key: str = ""


def _clean(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def _documents(evidence_payload: Mapping[str, Any] | None) -> Mapping[str, Any] | None:
    if not isinstance(evidence_payload, Mapping):
        return None
    timeline = evidence_payload.get("programmatic_timeline")
    if not isinstance(timeline, Mapping):
        return None
    documents = timeline.get("documents")
    return documents if isinstance(documents, Mapping) else None


def _timeline_facts(evidence_payload: Mapping[str, Any] | None) -> Sequence[Any] | None:
    if not isinstance(evidence_payload, Mapping):
        return None
    facts = evidence_payload.get("timeline_facts")
    return facts if isinstance(facts, list) else None


def _row_text(row: Mapping[str, Any]) -> str:
    return _clean(
        " ".join(
            _clean(row.get(field))
            for field in (
                "case_characteristic",
                "diagnose_based_on",
                "differential_diagnosis",
                "treatment_plan",
                "content",
                "record_content",
                "raw_text",
                "content_preview",
                "text_preview",
            )
            if _clean(row.get(field))
        )
    )


def _is_pure_exam_film_supply_order(row: Mapping[str, Any]) -> bool:
    """识别名称明确为胶片耗材的医嘱，不过滤真实影像检查。"""

    return bool(_EXAM_FILM_SUPPLY_ORDER_PATTERN.fullmatch(_clean(row.get("order_name"))))


def _source_rows(
    documents: Mapping[str, Any], source_keys: Sequence[str]
) -> list[tuple[str, int, str]]:
    rows: list[tuple[str, int, str]] = []
    for source_key in source_keys:
        raw_rows = documents.get(source_key)
        if not isinstance(raw_rows, list):
            continue
        for index, raw_row in enumerate(raw_rows[:_MAX_ROWS_PER_SOURCE], start=1):
            if not isinstance(raw_row, Mapping):
                continue
            content = _row_text(raw_row)
            if content:
                rows.append((source_key, index, content[:_MAX_ROW_CHARS]))
    return rows


def _fact_state(
    facts: Sequence[Any], fact_type: str, source_keys: Sequence[str]
) -> str:
    approved_sources = frozenset(source_keys)
    observed_present = False
    observed_absent = False
    for raw_fact in facts:
        if not isinstance(raw_fact, Mapping):
            continue
        actual_type = str(raw_fact.get("fact_type") or "").strip().lower()
        state = str(raw_fact.get("state") or "").strip().lower()
        source_key = str(raw_fact.get("source_key") or "").strip().lower()
        if (
            actual_type != fact_type
            or source_key not in approved_sources
            or raw_fact.get("current_visit_bound") is not True
        ):
            continue
        if state in _PRESENT_FACT_STATES:
            observed_present = True
        elif state in _ABSENT_FACT_STATES:
            observed_absent = True
    if observed_present and not observed_absent:
        return "present"
    if observed_present and observed_absent:
        return "unknown"
    return "absent" if observed_absent else "unknown"


def _typed_source(
    *,
    source_key: str,
    snapshot: Luxian0609EvidenceSnapshot,
    materials: Luxian0609EvidenceMaterialStore,
) -> _TypedSource:
    observation = next(
        (item for item in snapshot.observations if item.source_key == source_key),
        None,
    )
    if observation is None:
        return _TypedSource("missing", source_key=source_key)
    if observation.query_state.value in {"unavailable", "error"}:
        return _TypedSource(observation.query_state.value, source_key=source_key)
    if observation.completeness is SourceCompleteness.TRUNCATED:
        return _TypedSource("truncated", source_key=source_key)
    try:
        rows = materials.rows(source_key)
    except EvidenceMaterialTruncated:
        return _TypedSource("truncated", source_key=source_key)
    except EvidenceMaterialUnavailable:
        return _TypedSource("error", source_key=source_key)
    selected = tuple(row for row in rows if isinstance(row, Mapping))
    return _TypedSource("present" if selected else "empty", selected, source_key)


def _snapshot_fact_state(
    snapshot: Luxian0609EvidenceSnapshot,
    *,
    fact_type: str,
    source_keys: Sequence[str],
) -> str:
    approved_sources = frozenset(source_keys)
    states: set[str] = set()
    for fact in snapshot.facts:
        if fact.fact_type != fact_type or fact.source_key not in approved_sources:
            continue
        if fact.current_visit_relevance.value != "relevant":
            continue
        if fact.assertion.value == "affirmed":
            states.add("present")
        elif fact.assertion.value == "negated":
            states.add("absent")
    if states == {"present"}:
        return "present"
    if states == {"absent"}:
        return "absent"
    return "unknown"


def _controlled_trigger_from_rows(
    *,
    fact_kind: str,
    sources: Sequence[_TypedSource],
) -> bool:
    fields = _EXAM_CONTROLLED_FIELDS if fact_kind == "exam" else _CULTURE_CONTROLLED_FIELDS
    pattern = _EXAM_TRIGGER_PATTERN if fact_kind == "exam" else _CULTURE_TRIGGER_PATTERN
    for source in sources:
        for row in source.rows:
            if _CANCELLED_ORDER_PATTERN.search(_clean(row.get("order_status"))):
                continue
            if (
                fact_kind == "exam"
                and source.source_key == _ORDER_SOURCE_KEY
                and _is_pure_exam_film_supply_order(row)
            ):
                continue
            if fact_kind == "exam" and _is_exam_master_target(row):
                return True
            if fact_kind == "exam":
                # 已有结构化检查字段但明确是其它模态时，正文中的既往 CT/MRI
                # 不应重新触发本规则。
                if any(
                    _clean(row.get(field))
                    for field in fields
                    if field != "record_content"
                ):
                    continue
            for field in (*fields, "order_name"):
                value = _clean(row.get(field))
                if value and pattern.search(value):
                    return True
    return False


def _typed_trigger_state(
    *,
    fact_kind: str,
    snapshot: Luxian0609EvidenceSnapshot,
    materials: Luxian0609EvidenceMaterialStore,
    source_keys: Sequence[str] | None = None,
) -> tuple[str, dict[str, _TypedSource]]:
    source_keys = tuple(source_keys or _TYPED_TRIGGER_SOURCES[fact_kind])
    fact_type = _EXAM_FACT_TYPE if fact_kind == "exam" else _CULTURE_FACT_TYPE
    loaded = {
        source_key: _typed_source(
            source_key=source_key,
            snapshot=snapshot,
            materials=materials,
        )
        for source_key in source_keys
    }
    if any(source.state == "error" for source in loaded.values()):
        return "error", loaded
    if any(
        source.state in {"unavailable", "truncated", "missing"}
        for source in loaded.values()
    ):
        source_gap = True
    else:
        source_gap = False

    fact_state = _snapshot_fact_state(
        snapshot,
        fact_type=fact_type,
        source_keys=source_keys,
    )
    row_trigger = _controlled_trigger_from_rows(
        fact_kind=fact_kind,
        sources=tuple(loaded.values()),
    )
    if fact_state == "present":
        return "present", loaded
    if row_trigger:
        return "present", loaded
    if source_gap:
        return "unavailable", loaded
    # 否定事实只有在本次规则所需来源均完整时才可证明“不适用”。来源缺失、
    # 截断或未接入的优先级高于历史/投影中的 negated fact，避免缺资料被折叠
    # 为“未发生 CT/MRI 或培养事件”。
    if fact_state == "absent":
        return "absent", loaded
    if all(source.state == "empty" for source in loaded.values()):
        return "absent", loaded
    # 有通用检查/检验行但没有受控 CT/MRI 或培养/药敏触发，不得把沉默当临床否定。
    return "unknown", loaded


def _parse_current_visit_time(value: Any) -> datetime | None:
    text = _clean(value).replace("T", " ")
    try:
        return datetime.fromisoformat(text).replace(tzinfo=None)
    except ValueError:
        return None


def _culture_absence_gap(
    snapshot: Luxian0609EvidenceSnapshot,
    materials: Luxian0609EvidenceMaterialStore,
) -> tuple[str | None, tuple[str, ...]]:
    """无报告事件时校验叙述来源；培养提及只阻止断言无事件，不生成报告事实。"""

    sources = tuple(
        _typed_source(source_key=key, snapshot=snapshot, materials=materials)
        for key in (*_COURSE_SOURCE_KEYS, "consultation_record")
    )
    if any(source.state == "error" for source in sources):
        return "source_query_error", ()
    if any(source.state in {"missing", "unavailable", "truncated"} for source in sources):
        return "culture_source_unavailable", ()
    mention_refs = tuple(
        ref
        for key in (*_COURSE_SOURCE_KEYS, "consultation_record")
        for ref in _selected_material_document_refs(
            snapshot=snapshot, materials=materials, source_key=key,
            predicate=lambda row: bool(_CULTURE_TRIGGER_PATTERN.search(_row_text(row))),
        )
    )
    if mention_refs:
        # 包括计划、否定或历史提及：仅凭关键词不能可靠建立本次培养报告，
        # 也不能无视叙述直接认定无事件。保留关联缺口，不判阳性或病历缺陷。
        return "association_failed", mention_refs
    return None, ()


def _target_order_pattern(fact_kind: str) -> re.Pattern[str]:
    return _EXAM_ORDER_NAME_PATTERN if fact_kind == "exam" else _CULTURE_TRIGGER_PATTERN


def _effective_target_orders(
    rows_by_source: Mapping[str, Sequence[Mapping[str, Any]]],
    *,
    fact_kind: str,
) -> tuple[tuple[datetime | None, Mapping[str, Any]], ...]:
    pattern = _target_order_pattern(fact_kind)
    return tuple(
        (
            _parse_current_visit_time(
                row.get("prescribed_datetime")
                or row.get("order_time")
                or row.get("start_time")
            ),
            row,
        )
        for row in rows_by_source.get(_ORDER_SOURCE_KEY, ())
        if not _CANCELLED_ORDER_PATTERN.search(_clean(row.get("order_status")))
        and not (
            fact_kind == "exam"
            and _is_pure_exam_film_supply_order(row)
        )
        and pattern.search(_clean(row.get("order_name")))
    )


def _order_exam_structure_outcome(
    rows_by_source: Mapping[str, Sequence[Mapping[str, Any]]],
) -> _ExamLabOutcome | None:
    """只校验010的结构化医嘱、检查与报告合同，语义交给受控LLM。

    ``order_id`` 与 ``exam_id`` 是唯一允许的关联键。客户源表的合并检查由
    ``exam_id`` 显式枚举多个医嘱号；结构完整时返回 ``None``，让后续事实投影
    按权威检查时间截取病程。关联不完整时失败关闭，模型不得猜测事件归属或
    权威时间。
    """

    orders = _effective_target_orders(rows_by_source, fact_kind="exam")
    raw_target_orders = tuple(
        row
        for row in rows_by_source.get(_ORDER_SOURCE_KEY, ())
        if isinstance(row, Mapping)
        and not _is_pure_exam_film_supply_order(row)
        and _EXAM_ORDER_NAME_PATTERN.search(_clean(row.get("order_name")))
    )
    course_rows = tuple(
        row
        for source_key in _COURSE_SOURCE_KEYS
        for row in rows_by_source.get(source_key, ())
        if isinstance(row, Mapping) and _EXAM_ORDER_NAME_PATTERN.search(_row_text(row))
    )
    exam_rows = tuple(
        row
        for row in rows_by_source.get("exam_master", ())
        if isinstance(row, Mapping)
        and _is_exam_master_target(row)
    )
    report_rows = tuple(
        row
        for row in rows_by_source.get("exam_item_report", ())
        if isinstance(row, Mapping)
    )
    if not orders and not course_rows and not exam_rows:
        return None
    if raw_target_orders and not orders:
        # 已撤销的目标医嘱不产生检查触发；病程中的既往计划不能据此构成
        # “病程有检查、无医嘱”的缺陷。
        return None
    if orders and not exam_rows and any(
        isinstance(row, Mapping)
        and not any(_clean(row.get(field)) for field in (
            "exam_type", "modality", "exam_name", "item_name", "exam_item_name",
        ))
        and (
            not _clean(row.get("performed_dept"))
            or re.search(r"放射|影像", _clean(row.get("performed_dept")))
        )
        and _clean(row.get("report_time") or row.get("report_datetime"))
        for row in rows_by_source.get("exam_master", ())
    ):
        # 放射/影像主记录已有报告时间，但类型与关联未明，不能把识别失败
        # 当成检查未实施。这里不推定它就是CT/MRI，也不让模型猜测事件。
        return _ExamLabOutcome("LX0609-010", "data_gap", "required_field_missing")
    if orders and not exam_rows and not report_rows:
        # 医嘱只表示计划。检查主表和正式报告均为空时尚未形成实际检查事件，
        # 不应因“医嘱无主表”提前产生资料缺口。
        return None
    if course_rows and not orders and not exam_rows:
        return _ExamLabOutcome("LX0609-010", "data_gap", "association_failed")
    if not orders:
        # 正式检查行若声明了order_id，则完整医嘱集中找不到该键属于关联冲突；
        # 只有检查来源本身不提供order_id时，才按院方“仅报告”能力继续核对。
        if any(_clean(row.get("order_id")) for row in exam_rows):
            return _ExamLabOutcome("LX0609-010", "data_gap", "association_failed")
        return None

    # 检查主表缺键时无法确认实际事件，仍须在核对报告前失败关闭。
    if any(
        not _clean(row.get("order_id")) or not _clean(row.get("exam_id"))
        for row in exam_rows
    ):
        return _ExamLabOutcome("LX0609-010", "data_gap", "association_failed")

    orders_by_id: dict[str, tuple[datetime | None, Mapping[str, Any]]] = {}
    missing_order_id = False
    for order_time, order in orders:
        order_id = _clean(order.get("order_id"))
        if not order_id:
            missing_order_id = True
            continue
        if order_id in orders_by_id:
            return _ExamLabOutcome("LX0609-010", "data_gap", "association_failed")
        if order_time is None:
            return _ExamLabOutcome("LX0609-010", "data_gap", "authoritative_order_time_missing")
        orders_by_id[order_id] = (order_time, order)

    exams_by_order: dict[str, list[Mapping[str, Any]]] = {}
    for exam in exam_rows:
        exam_id = _clean(exam.get("exam_id"))
        linked_order_ids = resolve_exam_master_order_ids(
            exam,
            known_order_ids=tuple(orders_by_id),
        )
        if not exam_id or not linked_order_ids:
            return _ExamLabOutcome("LX0609-010", "data_gap", "association_failed")
        for order_id in linked_order_ids:
            exams_by_order.setdefault(order_id, []).append(exam)
    # exam_id 是检查主表的报告级唯一键。同一合并检查可显式枚举多个医嘱，
    # 但同一个医嘱仍不能被多条检查主记录重复占用。
    exam_ids = [_clean(exam.get("exam_id")) for exam in exam_rows]
    if len(exam_ids) != len(set(exam_ids)):
        return _ExamLabOutcome("LX0609-010", "data_gap", "association_failed")
    # 只核对已形成检查主表的实际事件；仍处于待执行状态的医嘱不参与本轮。
    if any(len(exams) != 1 for exams in exams_by_order.values()):
        return _ExamLabOutcome("LX0609-010", "data_gap", "association_failed")

    executed = tuple(exam_rows)

    for exam in executed:
        exam_id = _clean(exam.get("exam_id"))
        has_report = any(_clean(row.get("exam_id")) == exam_id for row in report_rows)
        has_master_report_time = _parse_current_visit_time(
            exam.get("report_time") or exam.get("report_datetime")
        ) is not None
        if not has_report and not has_master_report_time:
            return _ExamLabOutcome("LX0609-010", "non_compliant", "exam_report_missing")
    # 未关联医嘱缺键不遮蔽完整实际事件已证明的缺报告；无确定缺陷时仍保留缺口。
    if missing_order_id:
        return _ExamLabOutcome("LX0609-010", "data_gap", "association_failed")
    return None


def _order_exam_association_summary(
    rows_by_source: Mapping[str, Sequence[Mapping[str, Any]]],
) -> Mapping[str, Any]:
    """仅以受控业务键汇总 010 关联失败，不输出任何业务键或正文。"""

    orders = _effective_target_orders(rows_by_source, fact_kind="exam")
    exam_rows = tuple(
        row
        for row in rows_by_source.get("exam_master", ())
        if isinstance(row, Mapping)
        and _is_exam_master_target(row)
    )
    order_ids = tuple(_clean(row.get("order_id")) for _time, row in orders)
    exam_ids = tuple(_clean(row.get("exam_id")) for row in exam_rows)
    order_id_counts = Counter(order_ids)
    exam_id_counts = Counter(exam_ids)
    exams_by_order: dict[str, list[Mapping[str, Any]]] = {}
    invalid_exam_link = False
    known_order_ids = tuple(value for value in order_ids if value)
    for row in exam_rows:
        linked_order_ids = resolve_exam_master_order_ids(
            row,
            known_order_ids=known_order_ids,
        )
        if not linked_order_ids:
            invalid_exam_link = True
        for order_id in linked_order_ids:
            exams_by_order.setdefault(order_id, []).append(row)

    uniquely_linked = 0
    for order_id in order_ids:
        linked = exams_by_order.get(order_id, ())
        if order_id_counts[order_id] != 1 or len(linked) != 1:
            continue
        exam_id = _clean(linked[0].get("exam_id"))
        if exam_id and exam_id_counts[exam_id] == 1:
            uniquely_linked += 1

    order_count = len(orders)
    unmatched_or_ambiguous = max(0, order_count - uniquely_linked)
    issues: set[str] = set()
    if (
        any(not value for value in order_ids)
        or any(not _clean(row.get("order_id")) for row in exam_rows)
        or any(not value for value in exam_ids)
    ):
        issues.add("invalid_business_key")
    if invalid_exam_link:
        issues.add("exam_master_without_order")
    if any(count > 1 for value, count in order_id_counts.items() if value) or any(
        len(values) > 1 for values in exams_by_order.values()
    ) or any(count > 1 for value, count in exam_id_counts.items() if value):
        issues.add("ambiguous_exam_master_linkage")
    if any(
        value
        and order_id_counts[value] == 1
        and not exams_by_order.get(value)
        for value in order_ids
    ):
        issues.add("order_without_exam_master")

    association_issue_kind = (
        next(iter(issues))
        if len(issues) == 1
        else "mixed_association_failure"
        if issues
        else "association_cardinality_mismatch"
    )
    return {
        "order_count": order_count,
        "exam_master_count": len(exam_rows),
        "uniquely_linked_order_count": uniquely_linked,
        "unmatched_or_ambiguous_order_count": unmatched_or_ambiguous,
        "association_issue_kind": association_issue_kind,
    }


def _order_contract_display_facts(
    outcome: _ExamLabOutcome,
    *,
    rows_by_source: Mapping[str, Sequence[Mapping[str, Any]]],
) -> Mapping[str, Any]:
    """010 三个确定性子判定的客户事实；不在后续层重释状态。"""

    failure_kind = {
        "exam_order_reason_recorded": "exam_order_course_report_consistent",
        "exam_order_reason_missing": "exam_order_reason_missing",
        "exam_course_without_order": "exam_course_without_order",
        "exam_order_course_missing": "exam_order_course_missing",
        "exam_report_missing": "exam_report_missing",
        "association_failed": "exam_order_exam_association_failed",
    }.get(outcome.reason_code, "exam_order_contract_data_gap")
    facts: dict[str, Any] = {
        "failure_kind" if outcome.status != "compliant" else "verification_kind": failure_kind,
        "subject": "ct_mri",
        "checked_sources": ["exam_lab_order", "exam_master", "exam_lab_report", "course_record"],
        "requirement": "order_course_report_consistency",
        "requirement_met": outcome.status == "compliant",
    }
    if outcome.reason_code == "association_failed":
        facts.update(_order_exam_association_summary(rows_by_source))
    return facts


def _typed_context(
    *,
    fact_kind: str,
    snapshot: Luxian0609EvidenceSnapshot,
    materials: Luxian0609EvidenceMaterialStore,
) -> tuple[str, str]:
    source_keys = (*_TYPED_TRIGGER_SOURCES[fact_kind], *_COURSE_SOURCE_KEYS)
    parts: list[str] = []
    for source_key in source_keys:
        material = _typed_source(
            source_key=source_key,
            snapshot=snapshot,
            materials=materials,
        )
        if material.state == "error":
            return "", "error"
        if material.state in {"unavailable", "truncated", "missing"}:
            return "", "unavailable"
        for index, row in enumerate(material.rows[:_MAX_ROWS_PER_SOURCE], start=1):
            if source_key in _TYPED_TRIGGER_SOURCES[fact_kind]:
                fields = (
                    _EXAM_CONTROLLED_FIELDS
                    if fact_kind == "exam"
                    else _CULTURE_CONTROLLED_FIELDS
                )
                # 报告结果与时间只在受控键白名单内进入裁剪上下文。
                fields = (*fields, "report_time", "report_datetime", "result", "conclusion", "impression")
                text = _clean(" ".join(_clean(row.get(key)) for key in fields if _clean(row.get(key))))
            else:
                text = _row_text(row)
                record_time = _clean(authoritative_document_time_value(row))
                if record_time:
                    text = f"记录时间={record_time} {text}".strip()
            if text:
                parts.append(f"[{source_key}-{index}] {text[:_MAX_ROW_CHARS]}")
    return "\n".join(parts)[:_MAX_CONTEXT_CHARS], "present"


def _decision_from_outcome(
    *,
    outcome: _ExamLabOutcome,
    snapshot: Luxian0609EvidenceSnapshot,
) -> RuleDecision:
    allowed_source_keys = set(_TYPED_RULE_SOURCE_KEYS[outcome.rule_id])
    if outcome.rule_id in {"LX0609-014", "LX0609-015"}:
        # 会诊仅参与“无培养事件”的反证校验，不作为报告正文的替代来源。
        allowed_source_keys.add("consultation_record")
    if outcome.rule_id == "LX0609-010" and outcome.reason_code == "association_failed":
        # 关联失败只由医嘱、检查主表和报告支持；病程来源不能作为该结论的关键证据。
        allowed_source_keys = {_ORDER_SOURCE_KEY, *_EXAM_SOURCE_KEYS}
    if outcome.rule_id in _POST_RULE_IDS:
        allowed_source_keys.update(_HORIZON_SOURCE_KEYS)
    return build_exam_lab_rule_decision(
        outcome=outcome,
        snapshot=snapshot,
        allowed_source_keys=allowed_source_keys,
        evaluator_version=_TYPED_EVALUATOR_VERSION,
    )


def _target_source_document_ids(
    rows_by_source: Mapping[str, Sequence[Mapping[str, Any]]],
    *,
    fact_kind: str,
    include_order_document: bool = False,
) -> tuple[str, ...]:
    """返回当前单事件目标行中显式给出的文书 ID。

    主表和医嘱表未必提供可供病历对照页解析的 document_id；没有时宁可不定位。
    这里不使用 exam_id、test_id、order_id 或行下标作为替代，防止跨文书错误跳转。
    """

    source_keys = (
        _EXAM_SOURCE_KEYS if fact_kind == "exam" else _CULTURE_SOURCE_KEYS
    )
    if include_order_document:
        source_keys = (*source_keys, _ORDER_SOURCE_KEY)
    pattern = _target_order_pattern(fact_kind)
    document_ids: list[str] = []
    for source_key in source_keys:
        for row in rows_by_source.get(source_key, ()):
            if not isinstance(row, Mapping):
                continue
            if (
                fact_kind == "exam"
                and source_key == _ORDER_SOURCE_KEY
                and _is_pure_exam_film_supply_order(row)
            ):
                continue
            values = (
                _clean(row.get(field))
                for field in (
                    "order_name",
                    *(
                        _EXAM_CONTROLLED_FIELDS
                        if fact_kind == "exam"
                        else _CULTURE_CONTROLLED_FIELDS
                    ),
                )
            )
            if not any(value and pattern.search(value) for value in values):
                continue
            # 只认可 source reader 已投影的显式 document_id，不回退 id。
            document_id = _clean(row.get("document_id"))
            if document_id:
                document_ids.append(document_id)
    return tuple(dict.fromkeys(document_ids))


def _selected_material_document_refs(
    *,
    snapshot: Luxian0609EvidenceSnapshot,
    materials: Luxian0609EvidenceMaterialStore,
    source_key: str,
    predicate: Any,
) -> tuple[str, ...]:
    """从同一 Evidence Session 选择实际参与判定的逐行引用。

    只读取材料仓已经冻结的行；不回查数据库、不按文书标题或时间猜测。调用方
    提供的谓词必须只表达本规则已有的结构化触发/关联条件。
    """

    try:
        rows = materials.document_rows(source_key, snapshot=snapshot)
    except EvidenceMaterialUnavailable:
        return ()
    return tuple(
        dict.fromkeys(
            reference
            for reference, row in rows
            if isinstance(row, Mapping) and predicate(row)
        )
    )


def _target_order_material_refs(
    *,
    snapshot: Luxian0609EvidenceSnapshot,
    materials: Luxian0609EvidenceMaterialStore,
    fact_kind: str,
) -> tuple[str, ...]:
    pattern = _target_order_pattern(fact_kind)
    return _selected_material_document_refs(
        snapshot=snapshot,
        materials=materials,
        source_key=_ORDER_SOURCE_KEY,
        predicate=lambda row: (
            not _CANCELLED_ORDER_PATTERN.search(_clean(row.get("order_status")))
            and not (
                fact_kind == "exam"
                and _is_pure_exam_film_supply_order(row)
            )
            and bool(pattern.search(_clean(row.get("order_name"))))
        ),
    )


def _lx010_association_material_refs(
    *,
    snapshot: Luxian0609EvidenceSnapshot,
    materials: Luxian0609EvidenceMaterialStore,
) -> tuple[str, ...]:
    """010 关联失败仅绑定触发医嘱、目标检查主表及其正式报告。"""

    refs = list(
        _target_order_material_refs(
            snapshot=snapshot,
            materials=materials,
            fact_kind="exam",
        )
    )
    master_refs = _selected_material_document_refs(
        snapshot=snapshot,
        materials=materials,
        source_key="exam_master",
        predicate=_is_exam_master_target,
    )
    refs.extend(master_refs)
    target_exam_ids: set[str] = set()
    try:
        master_rows = materials.document_rows("exam_master", snapshot=snapshot)
    except EvidenceMaterialUnavailable:
        master_rows = ()
    for reference, row in master_rows:
        if reference in master_refs and isinstance(row, Mapping):
            exam_id = _clean(row.get("exam_id"))
            if exam_id:
                target_exam_ids.add(exam_id)
    if target_exam_ids:
        refs.extend(
            _selected_material_document_refs(
                snapshot=snapshot,
                materials=materials,
                source_key="exam_item_report",
                predicate=lambda row: _clean(row.get("exam_id")) in target_exam_ids,
            )
        )
    return tuple(dict.fromkeys(refs))


def _trigger_order_summaries(
    rows_by_source: Mapping[str, Sequence[Mapping[str, Any]]],
    *,
    fact_kind: str,
) -> list[dict[str, str]]:
    """保留触发资料缺口的具体医嘱名称和时间，不把业务键伪装成文书ID。"""

    pattern = _target_order_pattern(fact_kind)
    summaries: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for row in rows_by_source.get(_ORDER_SOURCE_KEY, ()):
        if not isinstance(row, Mapping):
            continue
        order_name = _clean(row.get("order_name"))
        if (
            not order_name
            or (fact_kind == "exam" and _is_pure_exam_film_supply_order(row))
            or not pattern.search(order_name)
        ):
            continue
        order_time = _clean(
            row.get("start_time")
            or row.get("order_time")
            or row.get("prescribed_datetime")
        )
        key = (order_name, order_time)
        if key in seen:
            continue
        seen.add(key)
        summary = {"order_name": order_name}
        if order_time:
            summary["order_time"] = order_time
        summaries.append(summary)
        if len(summaries) >= 8:
            break
    return summaries


def _target_report_missing_display_facts(
    *,
    rule_id: str,
    rows_by_source: Mapping[str, Sequence[Mapping[str, Any]]],
) -> Mapping[str, Any]:
    fact_kind = "exam" if rule_id in EXAM_RULE_IDS else "culture"
    return {
        "failure_kind": "exam_lab_target_report_missing",
        "subject": "ct_mri" if fact_kind == "exam" else "culture_susceptibility",
        "checked_sources": ["exam_lab_order", "exam_lab_report"],
        "trigger_orders": _trigger_order_summaries(
            rows_by_source,
            fact_kind=fact_kind,
        ),
    }


def _context(documents: Mapping[str, Any], *, fact_kind: str) -> str:
    trigger_sources = _EXAM_SOURCE_KEYS if fact_kind == "exam" else _CULTURE_SOURCE_KEYS
    parts: list[str] = []
    for source_key, index, content in _source_rows(documents, trigger_sources):
        parts.append(f"[{source_key}-{index}] {content}")
    for source_key, index, content in _source_rows(documents, _COURSE_SOURCE_KEYS):
        parts.append(f"[{source_key}-{index}] {content}")
    return "\n".join(parts)[:_MAX_CONTEXT_CHARS]


def _prompt(wrapper: Mapping[str, Any], *, context: str) -> str:
    custom_prompt = str(wrapper.get("custom_prompt") or "")
    custom_prompt = _MAPPING_LINE_PATTERN.sub("", custom_prompt)
    custom_prompt = custom_prompt.replace(
        "{defect_level}", str(wrapper.get("defect_level") or "")
    ).replace("{medical_text}", context)
    return custom_prompt.strip()


def _response_text(response: Mapping[str, Any]) -> str:
    choices = response.get("choices")
    if isinstance(choices, list) and choices and isinstance(choices[0], Mapping):
        message = choices[0].get("message")
        if isinstance(message, Mapping):
            return str(message.get("content") or "")
    return str(response.get("content") or response.get("text") or "")


def _parse_is_compliant(response: Mapping[str, Any]) -> bool | None:
    cleaned = re.sub(
        r"<think>[\s\S]*?</think>", "", _response_text(response), flags=re.IGNORECASE
    ).strip()
    match = re.search(r"\{[\s\S]*\}", cleaned)
    if not match:
        return None
    try:
        payload = json.loads(match.group(0))
    except (TypeError, ValueError):
        return None
    value = payload.get("is_compliant") if isinstance(payload, Mapping) else None
    return value if isinstance(value, bool) else None


def _usage(response: Mapping[str, Any]) -> tuple[int, int, int, float]:
    usage = response.get("usage")
    usage = usage if isinstance(usage, Mapping) else {}
    prompt = int(usage.get("prompt_tokens") or 0)
    completion = int(usage.get("completion_tokens") or 0)
    total = int(usage.get("total_tokens") or prompt + completion)
    return prompt, completion, total, float(response.get("_api_time") or 0.0)


def _supports_strict_json_schema(llm_client: ExamLabLLMClient) -> bool:
    capability = getattr(llm_client, "supports_strict_json_schema", None)
    if not callable(capability):
        return False
    return capability() is True


async def _generate_exam_lab_fact_response(
    *,
    llm_client: ExamLabLLMClient,
    selected_rule_ids: Sequence[str],
    projection: ExamLabTextProjection,
    enable_thinking: bool | None = None,
) -> dict[str, Any]:
    """执行一次 typed 事实抽取；Schema 能力必须由客户端显式声明。"""

    prompt = build_exam_lab_fact_prompt(
        selected_rule_ids=selected_rule_ids,
        projection=projection,
    )
    if not _supports_strict_json_schema(llm_client):
        if enable_thinking is not None:
            return await llm_client.generate(
                prompt,
                enable_thinking=enable_thinking,
            )
        return await llm_client.generate(prompt)
    strict_client = cast(_StrictJsonSchemaExamLabClient, llm_client)
    if enable_thinking is not None:
        return await strict_client.generate(
            prompt,
            response_format=build_exam_lab_fact_response_format(
                selected_rule_ids=selected_rule_ids,
                projection=projection,
            ),
            enable_thinking=enable_thinking,
        )
    return await strict_client.generate(
        prompt,
        response_format=build_exam_lab_fact_response_format(
            selected_rule_ids=selected_rule_ids,
            projection=projection,
        ),
    )


def _single_text_fact_outcome(
    *,
    rule_id: str,
    fact: ExamLabEventFact,
    projection: ExamLabTextProjection,
) -> _ExamLabOutcome:
    """由一个事件的语义事实和权威字段时间生成事件级结果。"""

    event = event_for_fact(projection, fact)
    safe_refs = projection.safe_refs or {}
    selected_evidence_refs = fact.evidence_refs
    if rule_id == "LX0609-010" and event is not None:
        # 010 的语义事实用于确认“检查前原因”是否存在，但客户证据沿用既有
        # 检查事件坐标，不把被模型命中的病程再作为第二份关键证据投影。
        selected_evidence_refs = event.document_refs
    elif rule_id in {"LX0609-011", "LX0609-012", "LX0609-014", "LX0609-015"}:
        # 事件可能同时含主记录和结果明细；只要结果明细可定位，就由它代表
        # 本次报告，避免同一事件将两类记录重复投影。病程只限模型实际命中的
        # 同事件文书，015 的跨培养过滤已在事实解析器完成。
        report_source_keys = (
            {"exam_item_report"}
            if rule_id in {"LX0609-011", "LX0609-012"}
            else {"labtest_item_report"}
        )
        source_document_refs = projection.source_document_refs or {}
        report_refs = tuple(
            ref
            for ref in fact.evidence_refs
            if (located := source_document_refs.get(ref)) is not None
            and located[0] in report_source_keys
        )
        event_refs = report_refs or (
            event.document_refs if event is not None else fact.evidence_refs
        )
        selected_evidence_refs = tuple(
            dict.fromkeys((*event_refs, *fact.course_doc_refs))
        )
    refs = tuple(
        safe_refs[item]
        for item in selected_evidence_refs
        if item in safe_refs
    )
    if (
        rule_id in {"LX0609-011", "LX0609-012"}
        and event is not None
        and event.guidance_only
    ):
        return _ExamLabOutcome(rule_id, "not_applicable", "exam_lab_text_fact_absent", refs)
    if fact.applicability == "not_applicable":
        return _ExamLabOutcome(rule_id, "not_applicable", "exam_lab_text_fact_absent", refs)
    if fact.applicability != "applicable":
        return _ExamLabOutcome(
            rule_id,
            _contract_allowed_status(
                rule_id,
                "evaluation_unknown"
                if rule_id in {"LX0609-012", "LX0609-015"}
                and event is not None
                and event.target_confirmed
                and event.result_text_available
                else "data_gap",
            ),
            "exam_lab_text_fact_unknown",
            refs,
        )
    if rule_id in {"LX0609-012", "LX0609-015"}:
        if fact.positive_state in {"negative", "not_relevant"}:
            return _ExamLabOutcome(rule_id, "not_applicable", "exam_lab_text_fact_absent", refs)
        if fact.positive_state != "positive":
            return _ExamLabOutcome(
                rule_id,
                _contract_allowed_status(
                    rule_id,
                    "evaluation_unknown"
                    if event is not None and event.result_text_available
                    else "data_gap",
                ),
                "exam_lab_text_fact_unknown",
                refs,
            )

    role = "exam_time" if rule_id == "LX0609-010" else "report_time"
    if event is None:
        return _ExamLabOutcome(rule_id, "data_gap", "authoritative_event_missing", refs)
    if role in event.conflict_roles:
        return _ExamLabOutcome(
            rule_id, "data_gap", "multiple_event_or_time_conflict", refs
        )
    event_time = event.exam_time if role == "exam_time" else event.report_time
    if event_time is None:
        return _ExamLabOutcome(rule_id, "data_gap", "authoritative_time_missing", refs)

    if fact.semantic_state == "absent":
        if projection.course_time_incomplete or projection.course_projection_truncated:
            return _ExamLabOutcome(
                rule_id,
                "data_gap",
                "course_projection_incomplete",
                refs,
            )
        if rule_id == "LX0609-010":
            return _ExamLabOutcome(rule_id, "non_compliant", "exam_lab_text_fact", refs)
        window_state = resolve_evaluation_window_state(
            projection=projection,
            event_time=event_time,
        )
        return _ExamLabOutcome(
            rule_id,
            "non_compliant"
            if window_state is EvaluationWindowState.MATURE
            else "not_applicable"
            if window_state is EvaluationWindowState.NOT_MATURE
            else "data_gap",
            "exam_lab_text_fact"
            if window_state is EvaluationWindowState.MATURE
            else _evaluation_window_gap_reason(window_state),
            refs,
        )
    if fact.semantic_state != "present":
        return _ExamLabOutcome(
            rule_id,
            _contract_allowed_status(
                rule_id,
                "data_gap"
                if event is None
                or not event.result_text_available
                or projection.course_time_incomplete
                or projection.course_projection_truncated
                else "evaluation_unknown",
            ),
            "exam_lab_text_fact_unknown",
            refs,
        )

    course_times = tuple(
        projection.course_times.get(doc_ref) for doc_ref in fact.course_doc_refs
    )
    if not course_times or any(item is None for item in course_times):
        return _ExamLabOutcome(rule_id, "data_gap", "course_record_time_missing", refs)
    intervals = tuple(item - event_time for item in course_times if item is not None)
    if rule_id == "LX0609-010":
        compliant = any(
            -timedelta(hours=48) <= interval <= timedelta(0)
            for interval in intervals
        )
        if not compliant and projection.course_projection_truncated:
            return _ExamLabOutcome(
                rule_id, "data_gap", "course_projection_incomplete", refs
            )
        return _ExamLabOutcome(
            rule_id,
            "compliant" if compliant else "non_compliant",
            "exam_lab_text_fact",
            refs,
        )

    post_event_intervals = tuple(
        interval for interval in intervals if interval >= timedelta(0)
    )
    if any(interval <= timedelta(hours=24) for interval in post_event_intervals):
        return _ExamLabOutcome(rule_id, "compliant", "exam_lab_text_fact", refs)
    if projection.course_projection_truncated:
        return _ExamLabOutcome(
            rule_id, "data_gap", "course_projection_incomplete", refs
        )
    if any(interval > timedelta(hours=24) for interval in post_event_intervals):
        return _ExamLabOutcome(rule_id, "non_compliant", "exam_lab_text_fact", refs)
    # 只有报告前病程不能证明已记录报告结果。24 小时尚未届满时不能提前报缺陷。
    window_state = resolve_evaluation_window_state(
        projection=projection,
        event_time=event_time,
    )
    return _ExamLabOutcome(
        rule_id,
        "non_compliant"
        if window_state is EvaluationWindowState.MATURE
        else "not_applicable"
        if window_state is EvaluationWindowState.NOT_MATURE
        else "data_gap",
        "exam_lab_text_fact"
        if window_state is EvaluationWindowState.MATURE
        else _evaluation_window_gap_reason(window_state),
        refs,
    )


def _text_fact_outcome(
    *,
    rule_id: str,
    facts: Sequence[ExamLabEventFact],
    projection: ExamLabTextProjection,
) -> _ExamLabOutcome:
    """逐事件判定后汇总；明确违规不得被其他事件的资料缺口遮蔽。"""

    rule_facts = tuple(item for item in facts if item.rule_id == rule_id)
    expected_count = len(events_for_family(
        projection, "exam" if rule_id in EXAM_RULE_IDS else "culture"
    ))
    if not rule_facts or len(rule_facts) != expected_count:
        return _ExamLabOutcome(rule_id, "data_gap", "exam_lab_fact_scope_missing")
    outcomes = tuple(
        _single_text_fact_outcome(
            rule_id=rule_id,
            fact=fact,
            projection=projection,
        )
        for fact in rule_facts
    )
    all_event_refs = tuple(
        dict.fromkeys(ref for item in outcomes for ref in item.fact_refs)
    )
    for status in (
        "non_compliant",
        "technical_error",
        "data_gap",
        "evaluation_unknown",
        "compliant",
        "not_applicable",
    ):
        selected = tuple(item for item in outcomes if item.status == status)
        if selected:
            return _ExamLabOutcome(
                rule_id,
                status,
                selected[0].reason_code,
                all_event_refs,
            )
    return _ExamLabOutcome(rule_id, "data_gap", "exam_lab_text_fact_unknown")


def _fact_for_outcome_display(
    *,
    rule_id: str,
    facts: Sequence[ExamLabEventFact],
    projection: ExamLabTextProjection,
    outcome: _ExamLabOutcome,
) -> ExamLabEventFact:
    """选择实际决定规则状态的事件，避免展示另一事件的时间和证据。"""

    # M15：主事实的候选顺序必须与逐事件列表同序（都按 event_position 升序）。
    # 此前这里按 facts 的原始顺序（即模型输出顺序）遍历，于是"第一个状态与总状态
    # 相符的事件"取决于模型把哪一条排在前，顶层 report_time/证据可能取自列表中间
    # 的事件（实测 C04 的 r3：顶层 report_time 取的是位置 3 的事件，而列表首项是
    # 位置 1）。排序只改变**候选顺序**，不改变判据本身：仍然是取第一个状态与总状态
    # 相符的事件，找不到才退回首项。
    rule_facts = tuple(
        sorted(
            (item for item in facts if item.rule_id == rule_id),
            key=lambda item: item.event_position,
        )
    )
    for fact in rule_facts:
        event_outcome = _single_text_fact_outcome(
            rule_id=rule_id,
            fact=fact,
            projection=projection,
        )
        if event_outcome.status == outcome.status:
            return fact
    return rule_facts[0]


def _display_facts_for_text_outcome(
    *,
    rule_id: str,
    facts: Sequence[ExamLabEventFact],
    projection: ExamLabTextProjection,
    outcome: _ExamLabOutcome,
) -> Mapping[str, Any] | None:
    """保留总状态兼容字段，并附加每个检查/检验事件的受控判定明细。"""

    primary_fact = _fact_for_outcome_display(
        rule_id=rule_id,
        facts=facts,
        projection=projection,
        outcome=outcome,
    )
    # 顺序合同：`exam_lab_result_mapping.safe_exam_lab_customer_display_facts`
    # 的校验要求 event_results 第 N 项的 event_position 恰好等于 N
    # （`exam_lab_result_mapping.py:427-441`），即物理顺序必须是 1..event_count
    # 升序。但受控事实抽取的提示词与输出骨架都只要求“每个规则与事件组合各一条”，
    # 从未要求模型按 event_position 升序输出；解析器也只按集合完整性校验，对顺序
    # 不敏感。模型因此可能返回完整但乱序的事件（实测 [2,3,1,4] / [2,3,4,1]）。
    # 这里统一按 event_position 升序投影，与上述顺序合同口径一致；排序是稳定
    # 排序，只调整顺序，不改变事件内容、数量与任何字段取值。
    # event_position 出现重号或缺号时，这里**不做静默修补**（不重编号、不补项），
    # 按原序保留，交由 `exam_lab_result_mapping` 的既有集合完整性校验拒绝。
    rule_facts = tuple(
        sorted(
            (item for item in facts if item.rule_id == rule_id),
            key=lambda item: item.event_position,
        )
    )
    multi_event = len(rule_facts) > 1
    event_results: list[dict[str, Any]] = []
    source_document_refs: list[Mapping[str, str]] = []
    for fact in rule_facts:
        event_outcome = _single_text_fact_outcome(
            rule_id=rule_id,
            fact=fact,
            projection=projection,
        )
        single = _text_outcome_display_facts(
            rule_id=rule_id,
            status=event_outcome.status,
            fact=fact,
            projection=projection,
            include_data_gap=multi_event,
        )
        if not isinstance(single, Mapping):
            continue
        detail: dict[str, Any] = {
            "event_position": fact.event_position,
            "event_status": event_outcome.status,
        }
        for key in (
            "report_time",
            "positive_state",
            "response_record_count",
            "response_record_time",
            "interval_hours",
            "applicable",
            "requirement_met",
        ):
            if key in single:
                detail[key] = single[key]
        event_results.append(detail)
        raw_refs = single.get("source_document_refs")
        if isinstance(raw_refs, list):
            source_document_refs.extend(
                item for item in raw_refs if isinstance(item, Mapping)
            )
    return _text_outcome_display_facts(
        rule_id=rule_id,
        status=outcome.status,
        fact=primary_fact,
        projection=projection,
        event_results=event_results if len(event_results) > 1 else (),
        event_source_document_refs=source_document_refs,
        include_data_gap=multi_event,
    )


def _strong_semantic_fact(
    *, rule_id: str, projection: ExamLabTextProjection
) -> ExamLabEventFact | None:
    """提取可由明确短语验证的病程语义；灰区返回 None 交给一次 LLM。"""

    if rule_id == "LX0609-010":
        # 检查原因依赖整段病程语义，禁止恢复关键词快速判定。
        return None
    events = events_for_family(
        projection, "exam" if rule_id in EXAM_RULE_IDS else "culture"
    )
    # 多事件必须逐事件绑定病程；全局关键词强匹配无法证明具体归属，交给
    # 同一次受控事实抽取，避免把一份病程复制给所有事件。
    if len(events) != 1:
        return None
    event = events[0]
    if rule_id in {"LX0609-012", "LX0609-015"}:
        if event.positive_hint == "negative":
            return ExamLabEventFact(
                rule_id=rule_id,
                applicability="not_applicable",
                semantic_state="absent",
                positive_state="negative",
                course_doc_refs=(),
                evidence_refs=event.document_refs,
            )
        if event.positive_hint != "positive":
            return None
        positive_state = "positive"
    else:
        positive_state = "not_relevant"
    family = "exam" if rule_id in EXAM_RULE_IDS else "culture"
    allowed_course_refs = (projection.event_course_refs or {}).get(
        (family, 1)
    )
    course_items = tuple(
        (ref, text)
        for ref, text in (projection.course_texts or {}).items()
        if (allowed_course_refs is None or ref in allowed_course_refs)
        and (
            event.report_time is None
            or (
                projection.course_times.get(ref) is not None
                and event.report_time <= projection.course_times[ref]
                <= event.report_time + timedelta(hours=24)
            )
        )
    )
    pattern = _STRONG_SEMANTIC_PATTERNS[rule_id]
    refs = []
    for ref, text in course_items:
        for clause in _CLAUSE_SPLIT_PATTERN.split(text):
            if not pattern.search(clause):
                continue
            if _UNCERTAIN_SEMANTIC_PATTERN.search(clause):
                continue
            if (
                rule_id == "LX0609-015"
                and not _event_identity_mentions_course(event, clause)
            ):
                # 仅有另一种标本（例如导管尖端培养）的抗感染动作，
                # 不能直接归属于当前阳性培养事件。
                continue
            if rule_id == "LX0609-015":
                if (
                    _NEGATED_CULTURE_ACTION_PATTERN.search(clause)
                    or _CONDITIONAL_CULTURE_ACTION_PATTERN.search(clause)
                ):
                    continue
            if (
                rule_id == "LX0609-012"
                and _CONDITIONAL_ANALYSIS_PATTERN.search(clause)
                and not _DEFINITE_ANALYSIS_PATTERN.search(clause)
            ):
                continue
            refs.append(ref)
            break
    refs = tuple(refs)
    if not refs:
        # 阳性报告已明确记入病程，但完整病程投影中没有分析/处置事实时，
        # 可直接形成“已记录结果、未完成分析”的闭世界结论。条件性计划或
        # “待结合病情观察”不是已经完成的分析/处置，不得据此降为资料不足。
        if rule_id in {"LX0609-012", "LX0609-015"}:
            mention_pattern = _STRONG_SEMANTIC_PATTERNS[
                "LX0609-011" if rule_id == "LX0609-012" else "LX0609-014"
            ]
            mention_refs = tuple(
                ref
                for ref, text in course_items
                if any(
                    mention_pattern.search(clause)
                    and (
                        rule_id != "LX0609-015"
                        or _event_identity_mentions_course(event, clause)
                    )
                    and not _UNCERTAIN_SEMANTIC_PATTERN.search(clause)
                    for clause in _CLAUSE_SPLIT_PATTERN.split(text)
                )
            )
            if mention_refs:
                return ExamLabEventFact(
                    rule_id=rule_id,
                    applicability="applicable",
                    semantic_state="absent",
                    positive_state=positive_state,
                    course_doc_refs=mention_refs,
                    evidence_refs=tuple((*event.document_refs, *mention_refs)),
                )
        return None
    return ExamLabEventFact(
        rule_id=rule_id,
        applicability="applicable",
        semantic_state="present",
        positive_state=positive_state,
        course_doc_refs=refs,
        evidence_refs=tuple((*event.document_refs, *refs)),
    )


def _result(rule_id: str, status: str, reason_code: str, *, executor_type: str) -> dict[str, Any]:
    item = build_luxian_0609_native_result(
        rule_id=rule_id,
        final_state=status,
        finding_kind="requirement_satisfied" if status == "compliant" else status,
        reason_code=reason_code,
    )
    findings, suggestion = _CONTROLLED_MESSAGES[status]
    item["findings"] = findings
    item["suggestion"] = suggestion
    metadata = dict(item.get("metadata") or {})
    metadata["executor_type"] = executor_type
    item["metadata"] = metadata
    return item


async def execute_luxian_0609_native_exam_lab_rules(
    *,
    rule_ids: Sequence[str],
    wrapper_rules: Sequence[Mapping[str, Any]],
    evidence_payload: Mapping[str, Any] | None,
    llm_client: ExamLabLLMClient | None,
    evidence_snapshot: Luxian0609EvidenceSnapshot | None = None,
    evidence_materials: Luxian0609EvidenceMaterialStore | None = None,
    decision_rule_ids: Sequence[str] = (),
) -> NativeExamLabExecutionResult:
    """按客户目录顺序执行；未通过事实门控的规则不调用模型。"""

    requested = {str(rule_id or "").strip().upper() for rule_id in rule_ids}
    selected = tuple(rule_id for rule_id in EXAM_LAB_RULE_IDS if rule_id in requested)
    normalized_decision_ids = tuple(
        str(rule_id or "").strip().upper() for rule_id in decision_rule_ids
    )
    if len(normalized_decision_ids) != len(set(normalized_decision_ids)):
        raise ValueError("duplicate typed exam lab rule scope")
    typed_requested = set(normalized_decision_ids)
    if (
        not typed_requested.issubset(_TYPED_DECISION_RULE_IDS)
        or not typed_requested.issubset(set(selected))
    ):
        raise ValueError("unsupported typed exam lab rule scope")
    if typed_requested and (
        type(evidence_snapshot) is not Luxian0609EvidenceSnapshot
        or type(evidence_materials) is not Luxian0609EvidenceMaterialStore
        or evidence_materials.snapshot_hash != evidence_snapshot.snapshot_hash
    ):
        raise ValueError("typed exam lab rules require one evidence session")
    if not selected:
        return NativeExamLabExecutionResult((), ())

    documents = _documents(evidence_payload)
    timeline_facts = _timeline_facts(evidence_payload)
    exam_state = _fact_state(timeline_facts or (), _EXAM_FACT_TYPE, _EXAM_SOURCE_KEYS)
    culture_state = _fact_state(
        timeline_facts or (), _CULTURE_FACT_TYPE, _CULTURE_SOURCE_KEYS
    )
    wrappers_by_id: dict[str, Mapping[str, Any]] = {}
    for wrapper in wrapper_rules:
        if not isinstance(wrapper, Mapping):
            continue
        wrapper_id = str(wrapper.get("rule_id") or wrapper.get("rule_code") or "").strip().upper()
        if wrapper_id in wrappers_by_id and wrapper_id in typed_requested:
            raise ValueError("duplicate typed exam lab wrapper")
        wrappers_by_id[wrapper_id] = wrapper

    results: list[dict[str, Any]] = []
    decisions: list[RuleDecision] = []
    customer_display_facts: list[tuple[str, Mapping[str, Any]]] = []
    llm_call_count = prompt_tokens = completion_tokens = total_tokens = 0
    api_time = 0.0
    parse_failure_kinds: list[str] = []
    model_rule_count = first_success_count = retried_rule_count = recovered_rule_count = 0
    # 仅在当前一次 Evidence Session 已读取的行内查找显式 document_id；不回读 DB。
    display_rows_by_source: Mapping[str, Sequence[Mapping[str, Any]]] = {}

    def emit_typed(
        rule_id: str,
        status: str,
        reason_code: str,
        fact_refs: tuple[str, ...] = (),
        source_document_ids: Sequence[str] = (),
        display_facts: Mapping[str, Any] | None = None,
    ) -> None:
        assert evidence_snapshot is not None
        if status == "non_compliant" and not source_document_ids:
            fact_kind = "exam" if rule_id in EXAM_RULE_IDS else "culture"
            source_document_ids = _target_source_document_ids(
                display_rows_by_source,
                fact_kind=fact_kind,
                include_order_document=rule_id == "LX0609-010",
            )
        if display_facts is None:
            display_facts = _customer_display_facts_for_outcome(
                rule_id=rule_id,
                status=status,
                reason_code=reason_code,
                source_document_ids=source_document_ids,
            )
        elif source_document_ids:
            display_facts = {
                **display_facts,
                "source_document_ids": list(
                    dict.fromkeys(
                        value
                        for raw in source_document_ids
                        if (value := _clean(raw))
                    )
                ),
            }
        if display_facts is not None:
            customer_display_facts.append((rule_id, display_facts))
        decisions.append(
            _decision_from_outcome(
                outcome=_ExamLabOutcome(rule_id, status, reason_code, fact_refs),
                snapshot=evidence_snapshot,
            )
        )

    typed_processed: set[str] = set()
    text_fact_rule_ids: list[str] = []
    if typed_requested:
        assert evidence_snapshot is not None
        assert evidence_materials is not None
        for rule_id in selected:
            if rule_id not in typed_requested:
                continue
            fact_kind = "exam" if rule_id in EXAM_RULE_IDS else "culture"
            typed_state, _ = _typed_trigger_state(
                fact_kind=fact_kind,
                snapshot=evidence_snapshot,
                materials=evidence_materials,
                source_keys=_TRIGGER_SOURCES_BY_RULE[rule_id],
            )
            if typed_state == "error":
                emit_typed(rule_id, "technical_error", "source_query_error")
                typed_processed.add(rule_id)
            elif typed_state == "unavailable":
                emit_typed(rule_id, "data_gap", f"{fact_kind}_source_unavailable")
                typed_processed.add(rule_id)
            elif typed_state == "absent":
                absence_gap, absence_refs = (
                    _culture_absence_gap(evidence_snapshot, evidence_materials)
                    if fact_kind == "culture" else (None, ())
                )
                emit_typed(
                    rule_id,
                    "technical_error" if absence_gap == "source_query_error"
                    else "data_gap" if absence_gap else "not_applicable",
                    absence_gap or f"{fact_kind}_fact_absent",
                    absence_refs,
                )
                typed_processed.add(rule_id)
            else:
                # 结构化触发 present/unknown 都进入裁剪正文事实提取；unknown
                # 不能再在读取正文前被折叠为 data_gap。
                text_fact_rule_ids.append(rule_id)

    if text_fact_rule_ids:
        assert evidence_snapshot is not None
        assert evidence_materials is not None
        source_keys = tuple(dict.fromkeys(
            source_key
            for rule_id in text_fact_rule_ids
            for source_key in _TYPED_RULE_SOURCE_KEYS[rule_id]
        ))
        rows_by_source: dict[str, tuple[Mapping[str, Any], ...]] = {}
        loaded_sources: dict[str, _TypedSource] = {}
        for source_key in source_keys:
            material = loaded_sources[source_key] = _typed_source(
                source_key=source_key,
                snapshot=evidence_snapshot,
                materials=evidence_materials,
            )
        eligible_rule_ids: list[str] = []
        for rule_id in text_fact_rule_ids:
            required = _TYPED_RULE_SOURCE_KEYS[rule_id]
            if any(loaded_sources[key].state == "error" for key in required):
                emit_typed(rule_id, "technical_error", "source_query_error")
                typed_processed.add(rule_id)
            elif any(
                loaded_sources[key].state in {"unavailable", "truncated", "missing"}
                for key in required
            ):
                emit_typed(rule_id, "data_gap", "exam_lab_projection_unavailable")
                typed_processed.add(rule_id)
            else:
                eligible_rule_ids.append(rule_id)
        for rule_id in eligible_rule_ids:
            for source_key in _TYPED_RULE_SOURCE_KEYS[rule_id]:
                rows_by_source[source_key] = loaded_sources[source_key].rows
        display_rows_by_source = rows_by_source
        observed_source_keys = {item.source_key for item in evidence_snapshot.observations}
        for source_key in _HORIZON_SOURCE_KEYS:
            if source_key not in observed_source_keys:
                continue
            material = _typed_source(
                source_key=source_key,
                snapshot=evidence_snapshot,
                materials=evidence_materials,
            )
            if material.state in {"present", "empty"}:
                rows_by_source[source_key] = material.rows
        if eligible_rule_ids:
            if "LX0609-010" in eligible_rule_ids:
                # 医嘱—检查—报告关联先由结构化键完成；只有结构可靠时，
                # 检查前原因才进入后续48小时病程语义抽取。
                order_outcome = _order_exam_structure_outcome(rows_by_source)
                if order_outcome is not None:
                    trigger_orders = _trigger_order_summaries(
                        rows_by_source,
                        fact_kind="exam",
                    )
                    order_display_facts: Mapping[str, Any] | None = None
                    if trigger_orders:
                        order_display_facts = {
                            **_order_contract_display_facts(
                                order_outcome,
                                rows_by_source=rows_by_source,
                            ),
                            "trigger_orders": trigger_orders,
                        }
                    emit_typed(
                        order_outcome.rule_id,
                        order_outcome.status,
                        order_outcome.reason_code,
                        _lx010_association_material_refs(
                            snapshot=evidence_snapshot,
                            materials=evidence_materials,
                        )
                        if trigger_orders
                        else (),
                        display_facts=order_display_facts,
                    )
                    typed_processed.add("LX0609-010")
                    eligible_rule_ids.remove("LX0609-010")
            try:
                horizon_observation = next(
                    (
                        item
                        for item in evidence_snapshot.observations
                        if item.source_key == EVALUATION_HORIZON_SOURCE_KEY
                    ),
                    None,
                )
                projection = build_exam_lab_text_projection(
                    # 事件级窗口选择由事实投影模块统一完成。旧的最早医嘱预筛
                    # 最多只保留4份病程，会系统性丢失后续检查事件。
                    rows_by_source=rows_by_source,
                    horizon_unavailable_reason=(
                        horizon_observation.reason_code
                        if horizon_observation is not None
                        and horizon_observation.reason_code
                        else None
                    ),
                )
            except ValueError:
                projection = None
            if projection is not None:
                semantic_rule_ids: list[str] = []
                for rule_id in eligible_rule_ids:
                    family = "exam" if rule_id in EXAM_RULE_IDS else "culture"
                    events = events_for_family(projection, family)
                    absence_gap, absence_refs = (
                        _culture_absence_gap(evidence_snapshot, evidence_materials)
                        if family == "culture" and (
                            (not events and not _effective_target_orders(rows_by_source, fact_kind=family))
                            or bool(events) and all(event.target_explicitly_absent for event in events)
                        ) else (None, ())
                    )
                    if absence_gap:
                        emit_typed(
                            rule_id,
                            "technical_error" if absence_gap == "source_query_error" else "data_gap",
                            absence_gap,
                            absence_refs,
                        )
                        typed_processed.add(rule_id)
                    elif not events:
                        if family == "exam":
                            emit_typed(
                                rule_id,
                                "not_applicable",
                                "trigger_absent_complete",
                            )
                        elif _effective_target_orders(rows_by_source, fact_kind=family):
                            emit_typed(
                                rule_id,
                                "data_gap",
                                "target_report_missing",
                                _target_order_material_refs(
                                    snapshot=evidence_snapshot,
                                    materials=evidence_materials,
                                    fact_kind=family,
                                ),
                                display_facts=_target_report_missing_display_facts(
                                    rule_id=rule_id,
                                    rows_by_source=rows_by_source,
                                ),
                            )
                        else:
                            emit_typed(
                                rule_id,
                                "not_applicable",
                                "exam_lab_target_event_absent",
                            )
                        typed_processed.add(rule_id)
                    elif rule_id in {"LX0609-011", "LX0609-012"} and all(
                        event.guidance_only for event in events
                    ):
                        emit_typed(
                            rule_id,
                            "not_applicable",
                            "exam_lab_target_event_absent",
                        )
                        typed_processed.add(rule_id)
                    elif all(event.target_explicitly_absent for event in events):
                        emit_typed(
                            rule_id,
                            "not_applicable",
                            "exam_lab_target_event_absent",
                        )
                        typed_processed.add(rule_id)
                    elif any("event_binding" in event.conflict_roles for event in events):
                        emit_typed(
                            rule_id,
                            "data_gap",
                            "multiple_event_or_time_conflict",
                        )
                        typed_processed.add(rule_id)
                    elif any(
                        not event.target_confirmed and not event.readable_text
                        for event in events
                    ):
                        emit_typed(
                            rule_id,
                            "data_gap",
                            "exam_lab_candidate_text_missing",
                        )
                        typed_processed.add(rule_id)
                    elif any(
                        event.target_confirmed
                        and (
                            (
                                rule_id == "LX0609-010"
                                and (
                                    "exam_time" in event.conflict_roles
                                    or event.exam_time is None
                                )
                            )
                            or (
                                rule_id != "LX0609-010"
                                and (
                                    "report_time" in event.conflict_roles
                                    or event.report_time is None
                                )
                            )
                        )
                        for event in events
                    ):
                        # 时间窗只能由受控字段计算；模型不能补造或推断时间。
                        emit_typed(
                            rule_id,
                            "data_gap",
                            "authoritative_time_missing"
                            if rule_id == "LX0609-010"
                            else "authoritative_report_time_missing",
                        )
                        typed_processed.add(rule_id)
                    elif projection.course_projection_truncated:
                        emit_typed(rule_id, "data_gap", "course_projection_incomplete")
                        typed_processed.add(rule_id)
                    else:
                        semantic_rule_ids.append(rule_id)
                eligible_rule_ids = semantic_rule_ids
            if eligible_rule_ids and projection is not None:
                # 对报告及病程中可由明确短语直接验证的事实优先使用 Python。
                # 含混、否定不清或条件性表述仍保留给一次受控 LLM。
                for rule_id in tuple(eligible_rule_ids):
                    if rule_id == "LX0609-010":
                        # 检查原因依赖整段病程语义，不再用关键词提前收口。
                        continue
                    fact = _strong_semantic_fact(
                        rule_id=rule_id,
                        projection=projection,
                    )
                    if fact is None:
                        continue
                    outcome = _text_fact_outcome(
                        rule_id=rule_id,
                        facts=(fact,),
                        projection=projection,
                    )
                    emit_typed(
                        rule_id,
                        outcome.status,
                        outcome.reason_code,
                        outcome.fact_refs,
                        display_facts=_text_outcome_display_facts(
                            rule_id=rule_id,
                            status=outcome.status,
                            fact=fact,
                            projection=projection,
                        ),
                    )
                    typed_processed.add(rule_id)
                    eligible_rule_ids.remove(rule_id)
            if not eligible_rule_ids:
                projection = None
            if (
                eligible_rule_ids
                and projection is not None
                and not projection.course_times
                and not projection.course_time_incomplete
                and not projection.course_projection_truncated
                and all(
                    all(event.target_confirmed for event in events_for_family(
                        projection,
                        "exam" if rule_id in EXAM_RULE_IDS else "culture",
                    ))
                    for rule_id in eligible_rule_ids
                )
            ):
                # 来源完整且确实没有任何相关病程时，010/011/014 的“未记录”
                # 可由 Python 直接确定；012/015 仅接受事件结果中的强阳性/阴性
                # 提示。012 报告尚未完成异常/正常分类时仍需一次受控模型判断；
                # 模型只分类报告，病程为空和最终缺陷仍由 Python 确定。
                for rule_id in tuple(eligible_rule_ids):
                    family = "exam" if rule_id in EXAM_RULE_IDS else "culture"
                    if rule_id == "LX0609-012" and any(
                        event.positive_hint == "unknown"
                        for event in events_for_family(projection, family)
                    ):
                        continue
                    facts = tuple(
                        ExamLabEventFact(
                            rule_id=rule_id,
                            applicability=(
                                "unknown"
                                if rule_id in {"LX0609-012", "LX0609-015"}
                                and event.positive_hint == "unknown"
                                else "not_applicable"
                                if event.positive_hint == "negative"
                                else "applicable"
                            ),
                            semantic_state=(
                                "unknown"
                                if rule_id in {"LX0609-012", "LX0609-015"}
                                and event.positive_hint == "unknown"
                                else "absent"
                            ),
                            positive_state=(
                                event.positive_hint
                                if rule_id in {"LX0609-012", "LX0609-015"}
                                else "not_relevant"
                            ),
                            course_doc_refs=(),
                            evidence_refs=event.document_refs,
                            event_position=event_position,
                        )
                        for event_position, event in enumerate(
                            events_for_family(projection, family), start=1
                        )
                    )
                    outcome = _text_fact_outcome(
                        rule_id=rule_id,
                        facts=facts,
                        projection=projection,
                    )
                    emit_typed(
                        rule_id,
                        outcome.status,
                        outcome.reason_code,
                        outcome.fact_refs,
                        display_facts=_display_facts_for_text_outcome(
                            rule_id=rule_id,
                            facts=facts,
                            projection=projection,
                            outcome=outcome,
                        ),
                    )
                    typed_processed.add(rule_id)
                    eligible_rule_ids.remove(rule_id)
                if not eligible_rule_ids:
                    projection = None
            if eligible_rule_ids and (
                projection is None or not projection.context or llm_client is None
            ):
                status = "technical_error" if llm_client is None else "data_gap"
                reason = "exam_lab_llm_failure" if llm_client is None else "exam_lab_projection_unavailable"
                for rule_id in eligible_rule_ids:
                    emit_typed(rule_id, status, reason)
                    typed_processed.add(rule_id)
            elif eligible_rule_ids:
                model_rule_count += len(eligible_rule_ids)
                llm_call_count += 1
                try:
                    response = await _generate_exam_lab_fact_response(
                        llm_client=llm_client,
                        selected_rule_ids=eligible_rule_ids,
                        projection=projection,
                    )
                except Exception:
                    response = None
                if response is None:
                    for rule_id in eligible_rule_ids:
                        emit_typed(rule_id, "technical_error", "exam_lab_llm_failure")
                        typed_processed.add(rule_id)
                else:
                    prompt, completion, total, elapsed = _usage(response)
                    prompt_tokens += prompt
                    completion_tokens += completion
                    total_tokens += total
                    api_time += elapsed
                    isolated_rule_failures: dict[str, str] = {}
                    try:
                        partition = parse_exam_lab_fact_response_isolated(
                            response=response,
                            selected_rule_ids=eligible_rule_ids,
                            projection=projection,
                            # 保留 native 模块上的严格解析符号，既不改变公开
                            # 解析行为，也让既有测试/诊断替换点继续生效。
                            _strict_parser=parse_exam_lab_fact_response,
                        )
                        text_facts = partition.facts
                        isolated_rule_failures = dict(partition.rule_failures)
                        first_success_count += len(eligible_rule_ids) - len(isolated_rule_failures)
                        if isolated_rule_failures:
                            # 首轮共享提取只记一次受控失败类别；重试仅携带
                            # 失败规则，其余已通过事实继续留在 text_facts。
                            failure_kind = next(iter(isolated_rule_failures.values()))
                            parse_failure_kinds.append(failure_kind)
                            logger.warning(
                                "exam_lab_fact_parse_failed parse_failure_kind=%s",
                                failure_kind,
                            )
                            logger.warning(
                                "exam_lab_fact_parse_failed parse_failure_kind=%s; starting controlled recovery",
                                failure_kind,
                            )
                            retry_rule_ids = tuple(
                                rule_id
                                for rule_id in eligible_rule_ids
                                if rule_id in isolated_rule_failures
                            )
                            retried_rule_count += len(retry_rule_ids)
                            use_event_recovery = all(
                                isolated_rule_failures[rule_id] == "evidence_ref"
                                and len(events_for_family(
                                    projection,
                                    "exam" if rule_id in EXAM_RULE_IDS else "culture",
                                )) > 1
                                for rule_id in retry_rule_ids
                            )
                            if use_event_recovery:
                                for rule_id in retry_rule_ids:
                                    recovery = await recover_exam_lab_rule_by_event(
                                        rule_id=rule_id,
                                        projection=projection,
                                        generate_response=lambda selected, event_projection: (
                                            _generate_exam_lab_fact_response(
                                                llm_client=llm_client,
                                                selected_rule_ids=selected,
                                                projection=event_projection,
                                                enable_thinking=(
                                                    False
                                                    if rule_id in {
                                                        "LX0609-011",
                                                        "LX0609-014",
                                                    }
                                                    else None
                                                ),
                                            )
                                        ),
                                        strict_parser=parse_exam_lab_fact_response,
                                    )
                                    llm_call_count += recovery.call_count
                                    for recovery_response in recovery.responses:
                                        retry_prompt, retry_completion, retry_total, retry_elapsed = _usage(
                                            recovery_response
                                        )
                                        prompt_tokens += retry_prompt
                                        completion_tokens += retry_completion
                                        total_tokens += retry_total
                                        api_time += retry_elapsed
                                    if recovery.failure_kind is None:
                                        text_facts = tuple((*text_facts, *recovery.facts))
                                        isolated_rule_failures.pop(rule_id, None)
                                        recovered_rule_count += 1
                                    else:
                                        isolated_rule_failures[rule_id] = recovery.failure_kind
                                        logger.warning(
                                            "exam_lab_fact_event_recovery_failed rule_id=%s failure_kind=%s",
                                            rule_id,
                                            recovery.failure_kind,
                                        )
                            else:
                                llm_call_count += 1
                                try:
                                    retry_response = await _generate_exam_lab_fact_response(
                                        llm_client=llm_client,
                                        selected_rule_ids=retry_rule_ids,
                                        projection=projection,
                                    )
                                    retry_prompt, retry_completion, retry_total, retry_elapsed = _usage(retry_response)
                                    prompt_tokens += retry_prompt
                                    completion_tokens += retry_completion
                                    total_tokens += retry_total
                                    api_time += retry_elapsed
                                    retry_partition = parse_exam_lab_fact_response_isolated(
                                        response=retry_response,
                                        selected_rule_ids=retry_rule_ids,
                                        projection=projection,
                                        _strict_parser=parse_exam_lab_fact_response,
                                    )
                                    text_facts = tuple(
                                        (*text_facts, *retry_partition.facts)
                                    )
                                    for rule_id in retry_rule_ids:
                                        isolated_rule_failures.pop(rule_id, None)
                                    isolated_rule_failures.update(
                                        retry_partition.rule_failures
                                    )
                                    recovered_rule_count += len(retry_rule_ids) - len(retry_partition.rule_failures)
                                except Exception as retry_exc:  # noqa: BLE001
                                    # 重试响应的顶层/范围错误仍闭合失败规则；首轮
                                    # 已通过的其它规则保留，不把异常扩散回它们。
                                    logger.warning("exam_lab_fact_retry_failed")
                                    for rule_id in retry_rule_ids:
                                        isolated_rule_failures.setdefault(
                                            rule_id,
                                            getattr(retry_exc, "failure_kind", "value"),
                                        )
                    except (ExamLabFactParseError, ValueError) as exc:
                        # 顶层 JSON/schema、规则/事件身份、引用范围错误，以及
                        # 非受控 ValueError，仍按原合同让整批进入一次重试。
                        failure_kind = getattr(exc, "failure_kind", "value")
                        parse_failure_kinds.append(failure_kind)
                        retried_rule_count += len(eligible_rule_ids)
                        logger.warning(
                            "exam_lab_fact_parse_failed parse_failure_kind=%s",
                            failure_kind,
                        )
                        logger.warning(
                            "exam_lab_fact_parse_failed parse_failure_kind=%s; retrying once",
                            failure_kind,
                        )
                        llm_call_count += 1
                        try:
                            retry_response = await _generate_exam_lab_fact_response(
                                llm_client=llm_client,
                                selected_rule_ids=eligible_rule_ids,
                                projection=projection,
                            )
                            retry_prompt, retry_completion, retry_total, retry_elapsed = _usage(retry_response)
                            prompt_tokens += retry_prompt
                            completion_tokens += retry_completion
                            total_tokens += retry_total
                            api_time += retry_elapsed
                            retry_partition = parse_exam_lab_fact_response_isolated(
                                response=retry_response,
                                selected_rule_ids=eligible_rule_ids,
                                projection=projection,
                                _strict_parser=parse_exam_lab_fact_response,
                            )
                            text_facts = retry_partition.facts
                            isolated_rule_failures = dict(retry_partition.rule_failures)
                            parse_failure_kinds.extend(isolated_rule_failures.values())
                            recovered_rule_count += len(eligible_rule_ids) - len(isolated_rule_failures)
                        except Exception:  # noqa: BLE001
                            logger.warning("exam_lab_fact_retry_failed")
                            text_facts = None
                    for rule_id in eligible_rule_ids:
                        outcome = (
                            _ExamLabOutcome(rule_id, "technical_error", "exam_lab_llm_invalid_output")
                            if text_facts is None or rule_id in isolated_rule_failures
                            else _text_fact_outcome(
                                rule_id=rule_id,
                                facts=text_facts,
                                projection=projection,
                            )
                        )
                        emit_typed(
                            rule_id,
                            outcome.status,
                            outcome.reason_code,
                            outcome.fact_refs,
                            display_facts=(
                                _display_facts_for_text_outcome(
                                    rule_id=rule_id,
                                    facts=text_facts,
                                    projection=projection,
                                    outcome=outcome,
                                )
                                if text_facts is not None
                                and rule_id not in isolated_rule_failures
                                else None
                            ),
                        )
                        typed_processed.add(rule_id)

    for rule_id in selected:
        fact_kind = "exam" if rule_id in EXAM_RULE_IDS else "culture"
        if rule_id in typed_requested:
            if rule_id not in typed_processed:
                emit_typed(rule_id, "technical_error", "executor_exception")
            continue

        if documents is None or timeline_facts is None:
            results.append(
                _result(
                    rule_id,
                    "data_gap",
                    "exam_lab_projection_unavailable",
                    executor_type="program",
                )
            )
            continue
        fact_state = exam_state if fact_kind == "exam" else culture_state
        if fact_state == "absent":
            results.append(
                _result(
                    rule_id,
                    "not_applicable",
                    f"{fact_kind}_fact_absent",
                    executor_type="program",
                )
            )
            continue
        if fact_state != "present":
            results.append(
                _result(
                    rule_id,
                    "data_gap",
                    f"{fact_kind}_fact_unknown",
                    executor_type="program",
                )
            )
            continue
        wrapper = wrappers_by_id.get(rule_id)
        context = _context(documents, fact_kind=fact_kind)
        if wrapper is None or not str(wrapper.get("custom_prompt") or "").strip() or not context:
            results.append(
                _result(rule_id, "data_gap", "exam_lab_prompt_input_unavailable", executor_type="program")
            )
            continue
        if llm_client is None:
            results.append(
                _result(rule_id, "data_gap", "exam_lab_llm_unavailable", executor_type="program")
            )
            continue
        llm_call_count += 1
        try:
            response = await llm_client.generate(_prompt(wrapper, context=context))
        except Exception:
            results.append(
                _result(rule_id, "data_gap", "exam_lab_llm_failure", executor_type="llm")
            )
            continue
        prompt, completion, total, elapsed = _usage(response)
        prompt_tokens += prompt
        completion_tokens += completion
        total_tokens += total
        api_time += elapsed
        is_compliant = _parse_is_compliant(response)
        if is_compliant is None:
            results.append(
                _result(rule_id, "data_gap", "exam_lab_llm_invalid_output", executor_type="llm")
            )
            continue
        status = "compliant" if is_compliant else "non_compliant"
        results.append(
            _result(rule_id, status, "exam_lab_customer_prompt", executor_type="llm")
        )

    return NativeExamLabExecutionResult(
        results=tuple(results),
        planned_rule_ids=selected,
        decisions=tuple(
            sorted(
                decisions,
                key=lambda item: normalized_decision_ids.index(item.rule_id),
            )
        ),
        customer_display_facts=tuple(customer_display_facts),
        llm_call_count=llm_call_count,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        total_tokens=total_tokens,
        api_time=api_time,
        parse_failure_kinds=tuple(dict.fromkeys(parse_failure_kinds)),
        model_execution_stats={
            "requested_rule_count": model_rule_count,
            "first_success_rule_count": first_success_count,
            "retried_rule_count": retried_rule_count,
            "recovered_rule_count": recovered_rule_count,
            "failed_rule_count": model_rule_count - first_success_count - recovered_rule_count,
            "first_answer_success_rate": first_success_count / model_rule_count if model_rule_count else None,
            "recovery_success_rate": recovered_rule_count / retried_rule_count if retried_rule_count else None,
            "model_failure_rate": (
                (model_rule_count - first_success_count - recovered_rule_count) / model_rule_count
                if model_rule_count else None
            ),
        },
    )
