"""LX0609-01-01-02 主诉长度与第一诊断指向的受控判定。"""

from __future__ import annotations

from functools import lru_cache
import re
import unicodedata
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
LX018_CHIEF_SIGNAL_KINDS = frozenset(
    {
        "event_or_etiology",
        "localized_symptom_or_sign",
        "nonspecific_symptom_or_sign",
        "unknown",
    }
)
LX018_ATOMIC_RELATION_FIELDS = (
    "anatomic_relation",
    "laterality_relation",
    "symptom_relation",
    "disease_course_relation",
    "disease_direction_relation",
)
LX018_ATOMIC_RELATION_VALUES = frozenset(
    {"supports", "conflicts", "nonspecific", "not_applicable", "unknown"}
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
_ADMISSION_FIRST_DIAGNOSIS_TYPES = frozenset({"初步诊断", "入院诊断"})
_EXPLICIT_MAIN_DIAGNOSIS_VALUES = frozenset({"是", "true", "1", "yes", "y", "主诊断"})
_DIAGNOSIS_TYPE_SEPARATOR_PATTERN = re.compile(r"[\s/／,，、;；+＋|｜]+")
_LX018_DIAGNOSIS_ORDER_FIELDS = (
    "diagnosis_no",
    "diagnosis_sequence",
    "sequence",
    "sequence_no",
    "order_no",
    "order",
    "sort_order",
)
_LX018_SEQUENCE_VALUE_PATTERN = re.compile(r"^(?:.*\|\|)?([1-9]\d*)$")
_NUMBERED_DIAGNOSIS_ITEM_PATTERN = re.compile(
    r"(?:^|(?=\d+\s*[、.．,，]))\d+\s*[、.．,，]\s*"
    r"(.*?)(?=\d+\s*[、.．,，]|$)"
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
        if item.rule_id == "LX0609-01-01-02"
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
        raise ValueError("LX0609-01-01-02 criteria contract is incomplete")
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
    return items


def _is_admission_first_diagnosis_type(value: Any) -> bool:
    """接受精确类型或明确分隔的入院/初步诊断复合值。"""

    normalized = _clean(value)
    if normalized in _ADMISSION_FIRST_DIAGNOSIS_TYPES:
        return True
    tokens = tuple(
        token for token in _DIAGNOSIS_TYPE_SEPARATOR_PATTERN.split(normalized) if token
    )
    return bool(tokens) and set(tokens).issubset(_ADMISSION_FIRST_DIAGNOSIS_TYPES)


def _lx018_structured_order(row: Mapping[str, Any]) -> int | None:
    """读取诊断的权威排序，缺失或互相冲突时拒绝推断。"""

    values: set[int] = set()
    for field_name in _LX018_DIAGNOSIS_ORDER_FIELDS:
        raw_value = _clean(row.get(field_name))
        if not raw_value:
            continue
        match = _LX018_SEQUENCE_VALUE_PATTERN.fullmatch(raw_value)
        if match is None:
            return None
        values.add(int(match.group(1)))
    return values.pop() if len(values) == 1 else None


def _lx018_has_explicit_main_flag(row: Mapping[str, Any]) -> bool:
    return _clean(row.get("diagnosis_main")).lower() in _EXPLICIT_MAIN_DIAGNOSIS_VALUES


def _lx018_diagnosis_label(row: Mapping[str, Any]) -> str:
    label = _clean(row.get("diagnosis_name") or row.get("diagnosis"))
    if not label:
        label = _clean(row.get("diagnosis_code"))
    numbered_items = _split_numbered_diagnosis_items(label)
    return numbered_items[0] if numbered_items else label


def _lx018_primary_diagnosis_resolution(
    documents: Mapping[str, Any],
) -> tuple[str, str]:
    """只选择有权威排序的第一入院诊断；不能由数据库行序补位。"""

    ordered_candidates: list[tuple[int, str]] = []
    saw_admission_candidate = False
    saw_unordered_candidate = False
    unordered_labels_by_source: dict[str, list[str]] = {}
    for source_key in LX018_DIAGNOSIS_SOURCES:
        for row in _source_rows(documents, source_key, limit=None):
            from ..cache_document_source_adapter import is_homepage_diagnosis
            if is_homepage_diagnosis(row):
                continue
            diagnosis_type = _clean(row.get("diagnosis_type"))
            if not _is_admission_first_diagnosis_type(diagnosis_type):
                continue
            saw_admission_candidate = True
            order = _lx018_structured_order(row)
            if order is None and _lx018_has_explicit_main_flag(row):
                order = 1
            label = _lx018_diagnosis_label(row)
            numbered_items = _split_numbered_diagnosis_items(
                row.get("diagnosis_name") or row.get("diagnosis")
            )
            # 客户 admission_record_diagnosis 的诊断类别没有 diagnosis_no，
            # 但同一字段中的“1、...2、...”仍是明确的行内权威顺序。
            if order is None and numbered_items:
                order = 1
            # 无序号/空内容候选不能覆盖另一来源的有效候选；只有没有任何有效
            # 候选时才以 unknown 结束，避免重复投影把结论锁死为资料不足。
            if order is None or not label:
                saw_unordered_candidate = True
                if label:
                    unordered_labels_by_source.setdefault(source_key, []).append(label)
                continue
            ordered_candidates.append((order, label))

    if not ordered_candidates and unordered_labels_by_source:
        # 单条诊断不存在相对顺序问题：各来源至多一条非空入院/初步诊断且内容一致时，
        # 即为第一诊断（0910 真实样本客户诊断类别常无 diagnosis_no）。
        single_labels = {
            labels[0] for labels in unordered_labels_by_source.values() if len(labels) == 1
        }
        if (
            all(len(labels) == 1 for labels in unordered_labels_by_source.values())
            and len(single_labels) == 1
        ):
            return ("available", next(iter(single_labels)))

    if not ordered_candidates:
        return (
            ("unknown", "")
            if saw_admission_candidate or saw_unordered_candidate
            else ("missing", "")
        )
    first_order = min(order for order, _ in ordered_candidates)
    first_labels = {
        label for order, label in ordered_candidates if order == first_order
    }
    return (
        ("available", next(iter(first_labels)))
        if len(first_labels) == 1
        else ("unknown", "")
    )


def _lx018_primary_diagnosis_available(documents: Mapping[str, Any]) -> bool:
    state, _ = _lx018_primary_diagnosis_resolution(documents)
    return state == "available"


def _lx018_prompt(*, context: str) -> str:
    """模型只抽取主诉与第一诊断之间的原子事实，不输出最终状态。"""

    return (
        "你只从本次入院记录的主诉原文与受控第一诊断中抽取医学关系原子事实。只按主诉原文提供的症状线索判断能否导出第一诊断。现病史仅用于第一诊断未标侧别时核实病灶侧别、识别规范列明的例外（同病反复入院、肿瘤再次放化疗、无症状检查异常）、理解主诉里的缩写或术语。只出现在现病史而未写进主诉的症状、体征或事件不得作为主诉线索，不得据此判supports。下述侧别与症状组合规则只作用于主诉原文中的症状。"
        "不要评价主诉字数，不要输出整条质控规则是否合规，也不要引入出院诊断或后续病程诊断。\n"
        "chief_signal_kind只能取event_or_etiology、localized_symptom_or_sign、"
        "nonspecific_symptom_or_sign、unknown。event_or_etiology只在外伤、暴露、操作等明确事件或病因"
        "与本次第一诊断临床相容并形成病因支持时使用；事件存在但与第一诊断无关时不得使用该枚举。"
        "localized_symptom_or_sign指单个症状、体征或症状组合能为该第一诊断提供有意义的"
        "解剖、器官系统或疾病方向线索；不要求主诉能唯一锁定该疾病。例如单侧肢体无力对脑血管病、"
        "急性上腹痛对胆道疾病、"
        "右腰腹痛对右侧输尿管结石、腰背痛对腰椎病变、咽痛伴发热对扁桃体炎，均可具有定位价值。"
        "仅写身体部位并不自动算有定位价值，必须结合本次第一诊断判断。以下边界必须严格执行："
        "单独心悸对冠心病、单独咳嗽对肺占位，均应将chief_signal_kind判为"
        "nonspecific_symptom_or_sign，关系字段不得判supports。"
        "症状组合应整体判断，不能拆成孤立咳嗽后套用上述边界；不要求特异性确诊。"
        "例如咳嗽合并咯血可提供肺部感染方向，反复咳嗽咳痰合并痰血可提供肺部占位方向，"
        "胸痛可提供冠脉疾病方向；不能因为还可能存在其他病因就否定这些方向线索。"
        "主诉症状指向第一诊断所在的器官系统或急症类别即可判localized_symptom_or_sign："
        "例如急性意识障碍对脑出血、脑卒中等颅内急症，呼吸困难对心力衰竭或肺部疾病，均提供方向线索。"
        "头痛、头晕、头昏、乏力、全身不适等全身性非特异症状单独或组合出现时判nonspecific_symptom_or_sign；"
        "全身性症状不能为以病因命名的诊断提供方向，例如头昏、乏力伴心累、气促对缺铁性贫血，"
        "头痛、头晕对脑梗死，均判nonspecific_symptom_or_sign。"
        "主诉已经直接写出与第一诊断相同"
        "或明确同义的疾病/检查发现时，应判localized_symptom_or_sign且disease_direction_relation=supports。"
        "第一诊断本身是以症状命名的待诊/待查（如抽搐待诊、发热待查）时，主诉写出该症状即属相同表述，"
        "同样判localized_symptom_or_sign且symptom_relation=supports，不因症状非特异而判不支持。\n"
        "anatomic_relation、laterality_relation、symptom_relation、disease_course_relation、"
        "disease_direction_relation分别只能取supports、conflicts、nonspecific、"
        "not_applicable、unknown。supports表示材料明确支持该关系，conflicts表示明确冲突；"
        "没有对应维度用not_applicable，材料不足用unknown。解剖和侧别按临床生理关系判断，"
        "不能机械比较字面同侧：例如右侧大脑半球病变与左侧肢体无力是典型对侧定位，应判supports。"
        "第一诊断未标侧别时，应结合本次入院现病史已确认的致病病灶核实侧别，"
        "不能把未标侧别当作不存在冲突；现病史只作入院病灶关系核实，不替代受控第一诊断。"
        "当核心只是缺少相符定位或疾病方向的非特异症状时，关系字段应使用nonspecific或not_applicable，"
        "不能仅因该症状可能出现在第一诊断中就判supports。不要补造病历没有的事实。\n"
        "反例：主诉“头痛、头晕1天”，现病史另有“伴左手乏力”，第一诊断脑梗死；主诉线索只有头痛、头晕，属nonspecific_symptom_or_sign，不得因现病史判supports。\n"
        "chief_complaint_signals为必填字符串数组，逐字摘自[主诉原文]中实际采信的症状、体征或事件，1–6项，每项不超过20字；chief_signal_kind=unknown时可为空数组。\n"
        "注意：即使主诉极短（如“呼之不应 3天。”“意识不清2小时”“昏迷1天”），chief_complaint_signals也必须原样逐字截取[主诉原文]中的连续子串"
        "（例如主诉为“呼之不应 3天。”时必须写[\"呼之不应\"]，不得改写或替换为同义术语“意识障碍”“昏迷”）；"
        "且当chief_signal_kind=unknown时，五个关系字段均不得为supports或conflicts。\n"
        "medical_analysis只能作展示说明，不能决定状态；用中文说明采用的原子事实，"
        "不得复述姓名、住院号等身份信息，最多80个汉字，不要解释枚举定义。\n"
        "严格输出JSON对象："
        '{"chief_signal_kind":"event_or_etiology|localized_symptom_or_sign|nonspecific_symptom_or_sign|unknown",'
        '"chief_complaint_signals":["主诉原文线索"],'
        '"anatomic_relation":"supports|conflicts|nonspecific|not_applicable|unknown",'
        '"laterality_relation":"supports|conflicts|nonspecific|not_applicable|unknown",'
        '"symptom_relation":"supports|conflicts|nonspecific|not_applicable|unknown",'
        '"disease_course_relation":"supports|conflicts|nonspecific|not_applicable|unknown",'
        '"disease_direction_relation":"supports|conflicts|nonspecific|not_applicable|unknown",'
        '"medical_analysis":"..."}。\n'
        f"受控材料：\n{context}"
    )


def _lx018_retry_reason_hint(
    previous_response: Mapping[str, Any] | None,
    *,
    chief_complaint: str = "",
) -> str:
    """基于失败类型生成固定纠偏提示；绝不回显原始病历正文或模型自由文本。"""

    if not isinstance(previous_response, Mapping):
        return "上次输出不是合法JSON对象"
    payload = _response_json_payload(previous_response)
    if payload is None:
        return "上次输出不是合法JSON对象"
    signal_kind = _clean(payload.get("chief_signal_kind"))
    if signal_kind not in LX018_CHIEF_SIGNAL_KINDS:
        return (
            "上次chief_signal_kind不在允许枚举内"
            "（仅允许event_or_etiology、localized_symptom_or_sign、nonspecific_symptom_or_sign、unknown）"
        )
    signals = payload.get("chief_complaint_signals")

    def normalize(value: str) -> str:
        return "".join(
            char
            for char in value
            if not char.isspace() and not unicodedata.category(char).startswith("P")
        )

    normalized_complaint = normalize(chief_complaint) if chief_complaint else ""
    if (
        not isinstance(signals, list)
        or len(signals) > 6
        or (signal_kind != "unknown" and not signals)
        or any(
            not isinstance(item, str)
            or not 1 <= len(item) <= 20
            or not normalize(item)
            or (normalized_complaint and normalize(item) not in normalized_complaint)
            for item in signals
        )
    ):
        return (
            "上次chief_complaint_signals未逐字命中[主诉原文]（或长度/数量超限）"
        )
    for field_name in LX018_ATOMIC_RELATION_FIELDS:
        if _clean(payload.get(field_name)) not in LX018_ATOMIC_RELATION_VALUES:
            return (
                f"上次{field_name}不在允许枚举内"
                "（仅允许supports、conflicts、nonspecific、not_applicable、unknown）"
            )
    if signal_kind == "unknown" and any(
        _clean(payload.get(field_name)) in {"supports", "conflicts"}
        for field_name in LX018_ATOMIC_RELATION_FIELDS
    ):
        return "上次chief_signal_kind为unknown时同时在关系字段给出了supports或conflicts"
    return "上次输出未通过原子事实结构校验"


def _lx018_retry_prompt(
    *,
    context: str,
    previous_response: Mapping[str, Any] | None = None,
    chief_complaint: str = "",
) -> str:
    """在018原子事实解析失败时构造1次定向纠偏重试提示词。"""

    reason = _lx018_retry_reason_hint(
        previous_response, chief_complaint=chief_complaint
    )
    correction = (
        f"上一次输出未通过校验：{reason}。请严格修正后重新输出完整JSON：\n"
        "1. chief_complaint_signals 必须是从[主诉原文]原样逐字复制的连续子串（1–6项，每项1–20字），"
        "绝不能改写或替换为同义词（例如[主诉原文]为“呼之不应 3天。”时必须写[\"呼之不应\"]，"
        "不得写成“意识障碍”或“昏迷”）；\n"
        "2. chief_signal_kind 只能取 event_or_etiology、localized_symptom_or_sign、"
        "nonspecific_symptom_or_sign、unknown；\n"
        "3. 五个关系字段只能取 supports、conflicts、nonspecific、not_applicable、unknown，"
        "且当 chief_signal_kind=unknown 时五个关系字段均不得取 supports 或 conflicts。\n"
    )
    base = _lx018_prompt(context=context)
    return base.replace(
        f"受控材料：\n{context}",
        f"{correction}受控材料：\n{context}",
        1,
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
    return value[:200] if value and "\x00" not in value else ""


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


def _parse_lx018_atomic_facts(
    response: Mapping[str, Any],
    *,
    chief_complaint: str,
) -> dict[str, str] | None:
    """严格解析 018 的原子事实输出；旧的总状态字段不再作为输入。"""

    payload = _response_json_payload(response)
    if payload is None:
        return None
    signal_kind = _clean(payload.get("chief_signal_kind"))
    if signal_kind not in LX018_CHIEF_SIGNAL_KINDS:
        return None
    signals = payload.get("chief_complaint_signals")

    # 原文锚定仅用于输入合同校验，不能进入客户展示事实。
    def normalize(value: str) -> str:
        return "".join(
            char for char in value
            if not char.isspace() and not unicodedata.category(char).startswith("P")
        )

    normalized_complaint = normalize(chief_complaint)
    if (
        not isinstance(signals, list)
        or len(signals) > 6
        or (signal_kind != "unknown" and not signals)
        or any(
            not isinstance(item, str) or not 1 <= len(item) <= 20
            or not normalize(item) or normalize(item) not in normalized_complaint
            for item in signals
        )
    ):
        return None
    facts: dict[str, str] = {"chief_signal_kind": signal_kind}
    for field_name in LX018_ATOMIC_RELATION_FIELDS:
        value = _clean(payload.get(field_name))
        if value not in LX018_ATOMIC_RELATION_VALUES:
            return None
        facts[field_name] = value
    if "medical_analysis" in payload and not isinstance(
        payload.get("medical_analysis"), str
    ):
        return None
    medical_analysis = _parse_lx018_medical_analysis(response)
    if signal_kind == "unknown" and any(
        facts[field_name] in {"supports", "conflicts"}
        for field_name in LX018_ATOMIC_RELATION_FIELDS
    ):
        # 无法识别主诉类型时，不能同时声称有明确的支持/冲突事实。
        return None
    facts["medical_analysis"] = medical_analysis
    return facts


def _aggregate_lx018_atomic_facts(
    facts: Mapping[str, str],
) -> tuple[str, str, tuple[str, ...]]:
    """以确定性规则把原子事实汇总为内部诊断关系和受控原因码。"""

    signal_kind = facts.get("chief_signal_kind", "")
    relations = {
        field_name: facts.get(field_name, "")
        for field_name in LX018_ATOMIC_RELATION_FIELDS
    }
    dimensions_by_field = {
        "anatomic_relation": "anatomic_site",
        "laterality_relation": "laterality",
        "symptom_relation": "symptom_pattern",
        "disease_course_relation": "disease_course",
        "disease_direction_relation": "disease_direction",
    }
    dimensions = tuple(
        dimensions_by_field[field_name]
        for field_name in LX018_ATOMIC_RELATION_FIELDS
        if relations[field_name] in {"supports", "conflicts"}
    )
    if any(value == "conflicts" for value in relations.values()):
        return "mismatch", "diagnosis_mismatch", dimensions
    if signal_kind == "unknown":
        return "unknown", "insufficient_information", dimensions
    if signal_kind == "nonspecific_symptom_or_sign":
        return "unsupported", "symptom_only", dimensions

    if signal_kind == "event_or_etiology":
        # 枚举本身已声明事件/病因与第一诊断形成支持；关系字段只补充支持维度，
        # 不再让模型把同一事实重复编码时的漏填覆盖该原子事实。
        return "supported", "supported", dimensions
    elif signal_kind == "localized_symptom_or_sign":
        support_fields = {
            "anatomic_relation",
            "laterality_relation",
            "symptom_relation",
        }
    else:
        return "unknown", "insufficient_information", dimensions
    if any(relations[field_name] == "supports" for field_name in support_fields):
        return "supported", "supported", dimensions
    if any(relations[field_name] == "unknown" for field_name in support_fields):
        return "unknown", "insufficient_information", dimensions
    if relations["disease_direction_relation"] == "supports":
        return "supported", "supported", dimensions
    return (
        "unsupported",
        "site_symptom_not_specific"
        if signal_kind == "localized_symptom_or_sign"
        else "symptom_only",
        dimensions,
    )


def _lx018_atomic_semantic_result(
    response: Mapping[str, Any],
    *,
    chief_complaint: str,
) -> tuple[CriterionResult, str] | None:
    """返回原子事实汇总结果；``None`` 表示模型输出不符合原子合同。"""

    facts = _parse_lx018_atomic_facts(response, chief_complaint=chief_complaint)
    if facts is None:
        return None
    relation_state, rationale_code, dimensions = _aggregate_lx018_atomic_facts(facts)
    return (
        _lx018_semantic_criterion_result(
            relation_state=relation_state,
            reason_dimensions=dimensions,
            rationale_code=rationale_code,
            medical_analysis=facts.get("medical_analysis", ""),
        ),
        relation_state,
    )
