"""LX0609-018 主诉长度与第一诊断指向的受控判定。"""

from __future__ import annotations

from functools import lru_cache
import re
from typing import Any, Mapping, Sequence

from ..decision_model import CriterionResult, CriterionStatus
from ..rule_contracts import RuleCriterionContract, load_luxian_0609_rule_contracts
from .shared import (
    clean_text as _clean,
    response_json_payload as _response_json_payload,
    row_text as _row_text,
    source_rows as _source_rows,
)


LX018_DIAGNOSIS_SOURCES = ("diagnosis", "admission_record_diagnosis")
LX018_DIAGNOSTIC_RELATION_STATES = frozenset(
    {"supported", "unsupported", "mismatch", "unknown"}
)
LX018_DIAGNOSTIC_REASON_DIMENSIONS = frozenset(
    {
        "anatomic_site",
        "laterality",
        "symptom_pattern",
        "disease_course",
        "disease_direction",
    }
)

_COMPLAINT_VALUE_PATTERN = re.compile(r"主诉\s*[:：]\s*([^；;。\r\n]{1,160})")
_PRIMARY_DIAGNOSIS_TYPES = frozenset({"主要诊断", "主诊断", "第一诊断"})
_ADMISSION_FIRST_DIAGNOSIS_TYPES = frozenset({"初步诊断", "入院诊断"})
_NUMBERED_DIAGNOSIS_ITEM_PATTERN = re.compile(
    r"(?:^|[，,；;\s]+)\d+\s*[、.．]\s*([^，,；;\n\r]+)"
)
_DIAGNOSTIC_RATIONALE_CODES = frozenset(
    {
        "symptom_only",
        "site_symptom_not_specific",
        "diagnosis_mismatch",
        "insufficient_information",
        "supported",
    }
)


@lru_cache(maxsize=1)
def _lx018_criteria() -> tuple[RuleCriterionContract, RuleCriterionContract]:
    contract = next(
        item
        for item in load_luxian_0609_rule_contracts()
        if item.rule_id == "LX0609-018"
    )
    criteria = {item.criterion_id: item for item in contract.criteria}
    length = criteria.get("chief_complaint_length")
    relation = criteria.get("diagnostic_direction")
    if (
        length is None
        or length.kind != "text_length"
        or relation is None
        or relation.kind != "semantic_relation"
        or len(criteria) != 2
    ):
        raise ValueError("LX0609-018 criteria contract is incomplete")
    return length, relation


def _lx018_complaint_text(documents: Mapping[str, Any]) -> str:
    for row in _source_rows(documents, "admission_record"):
        complaint = _clean(row.get("chief_complaint") or row.get("complaint"))
        if complaint:
            return complaint
        match = _COMPLAINT_VALUE_PATTERN.search(_row_text(row))
        if match:
            return _clean(match.group(1))
    return ""


def _lx018_length_criterion_result(
    documents: Mapping[str, Any],
) -> CriterionResult:
    criterion, _ = _lx018_criteria()
    complaint = _lx018_complaint_text(documents)
    if not complaint:
        return CriterionResult(
            criterion_id=criterion.criterion_id,
            status=CriterionStatus.UNKNOWN,
            reason_code="required_field_missing",
            operator=criterion.operator,
            unit=criterion.unit,
            expected_value=criterion.expected,
        )
    # 客户已确认“≤20字”为长度合规边界；标点和内部空白均计入。
    actual = len(complaint)
    passed = actual <= int(criterion.expected)
    return CriterionResult(
        criterion_id=criterion.criterion_id,
        status=CriterionStatus.PASSED if passed else CriterionStatus.FAILED,
        reason_code=(
            "requirement_satisfied" if passed else criterion.failure_reason_code
        ),
        actual_value=actual,
        expected_value=criterion.expected,
        operator=criterion.operator,
        unit=criterion.unit,
    )


def _split_numbered_diagnosis_items(value: Any) -> tuple[str, ...]:
    text = _clean(value)
    if not text:
        return ()
    items = tuple(
        item.strip()
        for item in _NUMBERED_DIAGNOSIS_ITEM_PATTERN.findall(text)
        if item.strip()
    )
    return items if len(items) >= 2 else ()


def _lx018_primary_diagnosis_text(row: Mapping[str, Any]) -> str:
    """返回可采信的第一诊断文本；不把其他诊断补成第一诊断。"""

    diagnosis_type = _clean(row.get("diagnosis_type"))
    diagnosis_name = _clean(row.get("diagnosis_name") or row.get("diagnosis"))
    diagnosis_code = _clean(row.get("diagnosis_code"))
    label = diagnosis_name or diagnosis_code
    if not label:
        return ""
    if diagnosis_type in _PRIMARY_DIAGNOSIS_TYPES:
        return label
    if diagnosis_type not in _ADMISSION_FIRST_DIAGNOSIS_TYPES:
        return ""
    numbered_items = _split_numbered_diagnosis_items(label)
    if numbered_items:
        return numbered_items[0]
    # cdm.diagnosis 已按稳定字段升序；拆成多行时第一行即入院第一诊断。
    return label


def _lx018_primary_diagnosis_available(documents: Mapping[str, Any]) -> bool:
    for source_key in LX018_DIAGNOSIS_SOURCES:
        for row in _source_rows(documents, source_key, limit=None):
            if _lx018_primary_diagnosis_text(row):
                return True
    return False


def _lx018_prompt(*, context: str) -> str:
    """模型只判断医学诊断指向，不接触字数阈值或最终质控状态。"""

    return (
        "你只核对本次入院记录主诉与入院第一诊断之间的医学诊断指向关系。"
        "不要评价主诉字数，不要输出整条质控规则是否合规，也不要引入出院诊断或后续病程诊断。\n"
        "diagnostic_relation_state只能取supported、unsupported、mismatch、unknown："
        "supported表示主诉的部位、症状特征或病程足以支持第一诊断方向；"
        "unsupported表示主诉信息存在但特异性不足；mismatch表示部位、侧别或症状方向冲突；"
        "unknown表示材料本身无法形成可靠医学判断。\n"
        "diagnostic_reason_dimensions只能从anatomic_site、laterality、symptom_pattern、"
        "disease_course、disease_direction中选择实际参与判断的维度。"
        "diagnostic_rationale_code只能取symptom_only、site_symptom_not_specific、"
        "diagnosis_mismatch、insufficient_information、supported。"
        "medical_analysis请用中文具体说明：主诉提供了哪些诊断线索、第一诊断需要哪些关键线索、"
        "两者为何支持、不足或冲突；不得复述姓名、住院号等身份信息，最长600字。\n"
        "严格输出JSON对象："
        '{"diagnostic_relation_state":"supported|unsupported|mismatch|unknown",'
        '"diagnostic_reason_dimensions":[],'
        '"diagnostic_rationale_code":"supported|symptom_only|site_symptom_not_specific|diagnosis_mismatch|insufficient_information",'
        '"medical_analysis":"..."}。\n'
        f"受控材料：\n{context}"
    )


def _parse_lx018_diagnostic_relation(
    response: Mapping[str, Any],
    *,
    is_compliant: bool | None = None,
) -> tuple[str, tuple[str, ...]]:
    del is_compliant
    payload = _response_json_payload(response)
    raw_state = _clean(payload.get("diagnostic_relation_state")) if payload else ""
    state = raw_state if raw_state in LX018_DIAGNOSTIC_RELATION_STATES else "unknown"
    raw_dimensions = payload.get("diagnostic_reason_dimensions") if payload else None
    dimensions = (
        tuple(
            item
            for item in raw_dimensions
            if isinstance(item, str) and item in LX018_DIAGNOSTIC_REASON_DIMENSIONS
        )
        if isinstance(raw_dimensions, list)
        else ()
    )
    return state, tuple(dict.fromkeys(dimensions))


def _parse_lx018_diagnostic_rationale_code(
    response: Mapping[str, Any],
    *,
    relation_state: str,
    dimensions: Sequence[str],
) -> str:
    """只接受受控原因码，绝不把模型自由文本带入客户结果。"""

    payload = _response_json_payload(response)
    value = _clean(payload.get("diagnostic_rationale_code")) if payload else ""
    if value in _DIAGNOSTIC_RATIONALE_CODES:
        if relation_state == "supported":
            return "supported"
        if relation_state == "mismatch":
            return "diagnosis_mismatch"
        if relation_state == "unsupported":
            if value == "symptom_only" and dimensions:
                return "site_symptom_not_specific"
            return value if value != "supported" else "site_symptom_not_specific"
        return "insufficient_information"
    if relation_state == "supported":
        return "supported"
    if relation_state == "mismatch":
        return "diagnosis_mismatch"
    if relation_state == "unsupported":
        return "site_symptom_not_specific" if dimensions else "symptom_only"
    return "insufficient_information"


def _parse_lx018_medical_analysis(response: Mapping[str, Any]) -> str:
    payload = _response_json_payload(response)
    if not payload:
        return ""
    value = str(payload.get("medical_analysis") or "").strip()
    return value[:2000] if value and "\x00" not in value else ""


def _lx018_semantic_criterion_result(
    *,
    relation_state: str,
    reason_dimensions: Sequence[str],
    rationale_code: str,
    medical_analysis: str,
) -> CriterionResult:
    _, criterion = _lx018_criteria()
    status = {
        "supported": CriterionStatus.PASSED,
        "unsupported": CriterionStatus.FAILED,
        "mismatch": CriterionStatus.FAILED,
        "unknown": CriterionStatus.UNKNOWN,
    }[relation_state]
    reason_code = (
        "requirement_satisfied"
        if status is CriterionStatus.PASSED
        else criterion.failure_reason_code
        if status is CriterionStatus.FAILED
        else "semantic_low_confidence"
    )
    return CriterionResult(
        criterion_id=criterion.criterion_id,
        status=status,
        reason_code=reason_code,
        actual_value=relation_state,
        rationale_code=rationale_code,
        dimensions=tuple(reason_dimensions),
        medical_analysis=medical_analysis,
    )


def _lx018_unknown_semantic_result(reason_code: str) -> CriterionResult:
    """为未能完成的诊断指向子判定生成受控未知结果。"""

    return _lx018_semantic_criterion_result(
        relation_state="unknown",
        reason_dimensions=(),
        rationale_code=reason_code,
        medical_analysis="",
    )
