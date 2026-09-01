"""LX0609 检查检验族原生执行：多事件投影、一次事实抽取、Python 判定。"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timedelta
import json
import logging
import re
from typing import Any, Mapping, Protocol, Sequence

from .decision_model import RuleDecision
from .evidence_material import (
    EvidenceMaterialTruncated,
    EvidenceMaterialUnavailable,
    Luxian0609EvidenceMaterialStore,
)
from .evidence_snapshot import Luxian0609EvidenceSnapshot, SourceCompleteness
from .exam_lab_fact_extraction import (
    ExamLabFactParseError,
    ExamLabEventFact,
    ExamLabTextProjection,
    _event_identity_mentions_course,
    build_exam_lab_fact_prompt,
    build_exam_lab_text_projection,
    event_for_fact,
    events_for_family,
    parse_exam_lab_fact_response,
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
    async def generate(self, prompt: str) -> dict[str, Any]: ...


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


@dataclass(frozen=True)
class _TypedSource:
    state: str
    rows: tuple[Mapping[str, Any], ...] = ()


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
        return _TypedSource("missing")
    if observation.query_state.value in {"unavailable", "error"}:
        return _TypedSource(observation.query_state.value)
    if observation.completeness is SourceCompleteness.TRUNCATED:
        return _TypedSource("truncated")
    try:
        rows = materials.rows(source_key)
    except EvidenceMaterialTruncated:
        return _TypedSource("truncated")
    except EvidenceMaterialUnavailable:
        return _TypedSource("error")
    selected = tuple(row for row in rows if isinstance(row, Mapping))
    return _TypedSource("present" if selected else "empty", selected)


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
        and pattern.search(_clean(row.get("order_name")))
    )


def _order_exam_structure_outcome(
    rows_by_source: Mapping[str, Sequence[Mapping[str, Any]]],
) -> _ExamLabOutcome | None:
    """只校验010的结构化医嘱、检查与报告合同，语义交给受控LLM。

    ``order_id`` 与 ``exam_id`` 是唯一允许的关联键。结构完整时返回 ``None``，
    让后续事实投影按权威检查时间截取病程；关联不完整时失败关闭，模型不得
    猜测事件归属或权威时间。
    """

    orders = _effective_target_orders(rows_by_source, fact_kind="exam")
    raw_target_orders = tuple(
        row
        for row in rows_by_source.get(_ORDER_SOURCE_KEY, ())
        if isinstance(row, Mapping)
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
    if not orders and not course_rows and not exam_rows:
        return None
    if raw_target_orders and not orders:
        # 已撤销的目标医嘱不产生检查触发；病程中的既往计划不能据此构成
        # “病程有检查、无医嘱”的缺陷。
        return None
    if course_rows and not orders and not exam_rows:
        return _ExamLabOutcome("LX0609-010", "data_gap", "association_failed")
    if not orders:
        # 正式检查行若声明了order_id，则完整医嘱集中找不到该键属于关联冲突；
        # 只有检查来源本身不提供order_id时，才按院方“仅报告”能力继续核对。
        if any(_clean(row.get("order_id")) for row in exam_rows):
            return _ExamLabOutcome("LX0609-010", "data_gap", "association_failed")
        return None

    # 已识别到目标医嘱或检查主表，但其正式业务键缺失时，不能回退到仅按
    # “检查前原因”判定的旧路径。此时无法核实同一次诊疗事件，只能资料待核实。
    if any(not _clean(row.get("order_id")) for _time, row in orders) or (
        exam_rows
        and any(
            not _clean(row.get("order_id")) or not _clean(row.get("exam_id"))
            for row in exam_rows
        )
    ):
        return _ExamLabOutcome("LX0609-010", "data_gap", "association_failed")

    orders_by_id: dict[str, tuple[datetime | None, Mapping[str, Any]]] = {}
    for order_time, order in orders:
        order_id = _clean(order.get("order_id"))
        if not order_id or order_id in orders_by_id:
            return _ExamLabOutcome("LX0609-010", "data_gap", "association_failed")
        if order_time is None:
            return _ExamLabOutcome("LX0609-010", "data_gap", "authoritative_order_time_missing")
        orders_by_id[order_id] = (order_time, order)

    if not exam_rows:
        return _ExamLabOutcome("LX0609-010", "data_gap", "association_failed")

    exams_by_order: dict[str, list[Mapping[str, Any]]] = {}
    for exam in exam_rows:
        order_id = _clean(exam.get("order_id"))
        exam_id = _clean(exam.get("exam_id"))
        if not order_id or not exam_id or order_id not in orders_by_id:
            return _ExamLabOutcome("LX0609-010", "data_gap", "association_failed")
        exams_by_order.setdefault(order_id, []).append(exam)
    # exam_id 是检查主表的报告级唯一键；同一检查被不同医嘱复用时，
    # 不能把一份报告当作多个事件的证据。
    exam_ids = [_clean(exam.get("exam_id")) for exam in exam_rows]
    if len(exam_ids) != len(set(exam_ids)):
        return _ExamLabOutcome("LX0609-010", "data_gap", "association_failed")
    # 关联是双向完整合同：不能只确认“已有主表的医嘱”唯一，还必须确认每条
    # 有效 CT/MRI 医嘱都有且仅有一条检查主表。缺少主表时不能擅自视为未执行。
    if (
        set(exams_by_order) != set(orders_by_id)
        or any(len(exams) != 1 for exams in exams_by_order.values())
    ):
        return _ExamLabOutcome("LX0609-010", "data_gap", "association_failed")

    executed = tuple(exams[0] for exams in exams_by_order.values())

    report_rows = tuple(
        row
        for row in rows_by_source.get("exam_item_report", ())
        if isinstance(row, Mapping)
    )
    for exam in executed:
        exam_id = _clean(exam.get("exam_id"))
        has_report = any(_clean(row.get("exam_id")) == exam_id for row in report_rows)
        has_master_report_time = _parse_current_visit_time(
            exam.get("report_time") or exam.get("report_datetime")
        ) is not None
        if not has_report and not has_master_report_time:
            return _ExamLabOutcome("LX0609-010", "non_compliant", "exam_report_missing")
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
    exam_order_ids = tuple(_clean(row.get("order_id")) for row in exam_rows)
    exam_ids = tuple(_clean(row.get("exam_id")) for row in exam_rows)
    order_id_counts = Counter(order_ids)
    exam_id_counts = Counter(exam_ids)
    exams_by_order: dict[str, list[Mapping[str, Any]]] = {}
    for row, order_id in zip(exam_rows, exam_order_ids):
        if order_id:
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
        or any(not value for value in exam_order_ids)
        or any(not value for value in exam_ids)
    ):
        issues.add("invalid_business_key")
    known_order_ids = {value for value in order_ids if value}
    if any(value and value not in known_order_ids for value in exam_order_ids):
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
        if not order_name or not pattern.search(order_name):
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


def _single_text_fact_outcome(
    *,
    rule_id: str,
    fact: ExamLabEventFact,
    projection: ExamLabTextProjection,
) -> _ExamLabOutcome:
    """由一个事件的语义事实和权威字段时间生成事件级结果。"""

    safe_refs = projection.safe_refs or {}
    refs = tuple(
        safe_refs[item]
        for item in fact.evidence_refs
        if item in safe_refs
    )
    if fact.applicability == "not_applicable":
        return _ExamLabOutcome(rule_id, "not_applicable", "exam_lab_text_fact_absent", refs)
    if fact.applicability != "applicable":
        return _ExamLabOutcome(rule_id, "data_gap", "exam_lab_text_fact_unknown", refs)
    if rule_id in {"LX0609-012", "LX0609-015"}:
        if fact.positive_state in {"negative", "not_relevant"}:
            return _ExamLabOutcome(rule_id, "not_applicable", "exam_lab_text_fact_absent", refs)
        if fact.positive_state != "positive":
            return _ExamLabOutcome(rule_id, "data_gap", "exam_lab_text_fact_unknown", refs)

    event = event_for_fact(projection, fact)
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
            else "data_gap",
            "exam_lab_text_fact"
            if window_state is EvaluationWindowState.MATURE
            else _evaluation_window_gap_reason(window_state),
            refs,
        )
    if fact.semantic_state != "present":
        return _ExamLabOutcome(rule_id, "data_gap", "exam_lab_text_fact_unknown", refs)

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
    for status in ("non_compliant", "data_gap", "compliant", "not_applicable"):
        selected = tuple(item for item in outcomes if item.status == status)
        if selected:
            return _ExamLabOutcome(
                rule_id,
                status,
                selected[0].reason_code,
                tuple(dict.fromkeys(
                    ref for item in selected for ref in item.fact_refs
                )),
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

    rule_facts = tuple(item for item in facts if item.rule_id == rule_id)
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
    rule_facts = tuple(item for item in facts if item.rule_id == rule_id)
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
                emit_typed(rule_id, "not_applicable", f"{fact_kind}_fact_absent")
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
                    order_display_facts = dict(
                        _order_contract_display_facts(
                            order_outcome,
                            rows_by_source=rows_by_source,
                        )
                    )
                    order_display_facts["trigger_orders"] = _trigger_order_summaries(
                        rows_by_source,
                        fact_kind="exam",
                    )
                    emit_typed(
                        order_outcome.rule_id,
                        order_outcome.status,
                        order_outcome.reason_code,
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
                    if not events:
                        if _effective_target_orders(rows_by_source, fact_kind=family):
                            emit_typed(
                                rule_id,
                                "data_gap",
                                "target_report_missing",
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
                llm_call_count += 1
                try:
                    response = await llm_client.generate(
                        build_exam_lab_fact_prompt(
                            selected_rule_ids=eligible_rule_ids,
                            projection=projection,
                        )
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
                    try:
                        text_facts = parse_exam_lab_fact_response(
                            response=response,
                            selected_rule_ids=eligible_rule_ids,
                            projection=projection,
                        )
                    except (ExamLabFactParseError, ValueError) as exc:
                        # 保持严格解析合同；仅对模型偶发的 value/schema 输出重试一次，
                        # 避免单次非法响应让整批检查检验规则永久技术失败。
                        failure_kind = getattr(exc, "failure_kind", "value")
                        parse_failure_kinds.append(failure_kind)
                        logger.warning(
                            "exam_lab_fact_parse_failed parse_failure_kind=%s",
                            failure_kind,
                        )
                        if isinstance(exc, (ExamLabFactParseError, ValueError)):
                            logger.warning(
                                "exam_lab_fact_parse_failed parse_failure_kind=%s; retrying once",
                                failure_kind,
                            )
                            llm_call_count += 1
                            try:
                                retry_response = await llm_client.generate(
                                    build_exam_lab_fact_prompt(
                                        selected_rule_ids=eligible_rule_ids,
                                        projection=projection,
                                    )
                                )
                                retry_prompt, retry_completion, retry_total, retry_elapsed = _usage(retry_response)
                                prompt_tokens += retry_prompt
                                completion_tokens += retry_completion
                                total_tokens += retry_total
                                api_time += retry_elapsed
                                text_facts = parse_exam_lab_fact_response(
                                    response=retry_response,
                                    selected_rule_ids=eligible_rule_ids,
                                    projection=projection,
                                )
                            except Exception as retry_exc:  # noqa: BLE001
                                parse_failure_kinds.append(getattr(retry_exc, "failure_kind", "value"))
                                logger.warning("exam_lab_fact_retry_failed")
                                text_facts = None
                        else:
                            text_facts = None
                    for rule_id in eligible_rule_ids:
                        outcome = (
                            _ExamLabOutcome(rule_id, "technical_error", "exam_lab_llm_invalid_output")
                            if text_facts is None
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
    )
