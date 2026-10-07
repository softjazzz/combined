"""LX0609 手术高风险门控族原生执行。

只消费当前就诊的受控强事实和裁剪文书；事实沉默不等于明确否定。
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import json
import re
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
from .evidence_snapshot import Luxian0609EvidenceSnapshot
from .native_execution import build_luxian_0609_native_result
from .malignancy_fact import (
    MalignancyFactResolver,
    build_stage_malignancy_sources,
    resolve_malignancy_visit_stage,
)
from .source_evidence_reader import (
    has_qualified_traditional_surgery_row,
    has_strict_performed_time,
    parse_strict_performed_time,
    read_luxian_0609_native_source_rows,
    read_luxian_0609_runtime_source_rows,
)
from .surgery_applicability import resolve_surgery_applicability
from .surgery_text_fact_contract import (
    LX0609_025_REQUIRED_FIELDS,
    SurgeryEventFact,
    SurgeryTextProjection,
    build_surgery_text_fact_prompt,
    build_surgery_text_projection,
    parse_surgery_text_fact_response,
)


SURGERY_GATE_RULE_IDS = (
    "LX0609-04-02-01",
    "LX0609-04-02-03",
    "LX0609-04-02-04",
    "LX0609-05-01-01",
    "LX0609-04-02-05",
    "LX0609-11-01-01",
)
EXECUTOR_KEY = "surgery_gate"

_PRESENT_STATES = frozenset({"present", "performed", "positive", "complete"})
_NEGATIVE_STATES = frozenset({"explicit_negative", "absent", "not_present"})
_MAPPING_LINE_PATTERN = re.compile(r"^.*(?:主执行规则|映射执行规则).*$", re.MULTILINE)
_MAX_ROWS_PER_SOURCE = 6
_MAX_ROW_CHARS = 1000
_MAX_CONTEXT_CHARS = 12000
_TYPED_003_EVALUATOR_VERSION = "surgery-timeliness-003-ruledecision-v1"
_TYPED_SURGERY_GATE_EVALUATOR_VERSION = "surgery-gate-ruledecision-shadow-v2"
_TYPED_DECISION_RULE_IDS = frozenset(SURGERY_GATE_RULE_IDS)
_TEXT_FACT_RULE_IDS = frozenset(
    {"LX0609-04-02-03", "LX0609-04-02-04", "LX0609-05-01-01", "LX0609-11-01-01"}
)
_TYPED_TEXT_SOURCES = {
    "LX0609-04-02-03": (
        "surgery_record", "mr_surgery", "pathology_exam_master",
        "pathology_exam_report", "admission_record_diagnosis", "diagnosis",
        "discharge_record_diagnosis", "inpat_registration.discharge_horizon",
        "discharge_record",
    ),
    # 025 的永久性植入事实可由正式手术记录或病程记录确认；mr_surgery 仅是
    # 操作清单，既不能补充字段事实，也不能因行数多而截断本规则的一次受控抽取。
    "LX0609-04-02-04": ("surgery_record", "daily_course_record"),
    "LX0609-05-01-01": (
        "surgery_record", "mr_surgery", "inpat_drug_order", "daily_course_record",
    ),
    # 033 只需要“已实施手术锚点 + 本次手术同意书”；mr_surgery 既不提供
    # 同意书角色也不提供签署事实，纳入只会挤占 2 份文书的安全上下文预算。
    "LX0609-11-01-01": ("surgery_record", "surgery_inform_consent"),
}
# 033 的已实施手术锚点由同一 snapshot 的严格事实确认，不必把手术记录
# 正文再次送给模型。模型只读取本次就诊的少量手术知情同意书正文。
_TYPED_TEXT_PROJECTION_SOURCES = {
    **_TYPED_TEXT_SOURCES,
    "LX0609-11-01-01": ("surgery_inform_consent",),
}
_TYPED_SOURCE_CUSTOMER_LABELS = {
    "surgery_record": "手术记录",
    "surgery_inform_consent": "手术知情同意书",
}
# typed RuleDecision 旁路将同一就诊仍需语义判断的高风险手术规则合并为
# 一次事实抽取。任何上限触发都 fail-closed 为 data_gap，禁止静默截断后
# 继续调用模型。
_JOINT_TEXT_FACT_MAX_ROWS_PER_SOURCE = 6
_JOINT_TEXT_FACT_MAX_TOTAL_ROWS = 24
_JOINT_TEXT_FACT_MAX_DOCUMENTS = 24
_JOINT_TEXT_FACT_MAX_CONTEXT_CHARS = 12000
_JOINT_TEXT_FACT_MAX_COMPLETION_TOKENS = 512
_AUTHORITATIVE_RECORD_TIME_PATTERN = re.compile(
    r"^\d{4}-\d{1,2}-\d{1,2}[T ]\d{1,2}:\d{2}"
    r"(?::\d{2}(?:\.\d{1,6})?)?(?:Z|[+-]\d{2}:?\d{2})?$"
)
_LABELED_SURGERY_TIME_PATTERN_TEMPLATE = (
    r"(?<!\w){label}\s*[:：]\s*"
    r"(?P<value>\d{{4}}-\d{{1,2}}-\d{{1,2}}[T ]\d{{1,2}}:\d{{2}}"
    r"(?::\d{{2}}(?:\.\d{{1,6}})?)?(?:Z|[+-]\d{{2}}:?\d{{2}}))"
)
_HOSPITAL_TIMEZONE = timezone(timedelta(hours=8))
_TRAUMA_DIAGNOSIS_PATTERN = re.compile(
    r"外伤|创伤|颅内血肿|硬膜外血肿|硬膜下血肿"
)
_RESCUE_SURGERY_PATTERN = re.compile(r"血肿清除|去骨瓣减压|脑疝")
_MALIGNANT_SURGERY_PATTERN = re.compile(r"恶性|癌|肿瘤|淋巴结清扫|根治术")

_RULE_SOURCES = {
    "LX0609-04-02-01": ("surgery_record", "anesthesia_record"),
    "LX0609-04-02-03": ("surgery_record", "pathology_exam_report"),
    "LX0609-04-02-04": ("surgery_record", "daily_course_record", "implant_usage"),
    "LX0609-05-01-01": ("surgery_record", "inpat_drug_order", "daily_course_record"),
    "LX0609-04-02-05": ("surgery_record", "presurg_summary", "presurg_discussion"),
    "LX0609-11-01-01": ("surgery_record", "surgery_inform_consent", "consent_form"),
}

_CONTROLLED_MESSAGES = {
    "compliant": ("手术相关记录满足该项要求。", ""),
    "non_compliant": ("手术相关记录未满足该项要求。", "请按该质控点补充或修正相关记录。"),
    "not_applicable": ("当前就诊不符合该项手术规则的适用条件。", ""),
    "data_gap": ("当前手术资料不足，暂不能形成可靠结论。", "请补齐相关资料后重新质控。"),
}


class SurgeryGateLLMClient(Protocol):
    async def generate(
        self,
        prompt: str,
        *,
        max_completion_tokens: int | None = None,
        allow_length_retry: bool = True,
    ) -> dict[str, Any]:
        ...


@dataclass(frozen=True)
class NativeSurgeryGateExecutionResult:
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
class _SurgeryTextOutcome:
    rule_id: str
    status: str
    reason_code: str
    customer_display_facts: Mapping[str, Any] | None = None
    selected_document_refs: tuple[str, ...] = ()


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


def _facts(evidence_payload: Mapping[str, Any] | None) -> tuple[Mapping[str, Any], ...]:
    if not isinstance(evidence_payload, Mapping):
        return ()
    raw = evidence_payload.get("timeline_facts")
    if not isinstance(raw, list):
        return ()
    return tuple(item for item in raw if isinstance(item, Mapping))


def _matching_facts(
    facts: Sequence[Mapping[str, Any]], fact_type: str
) -> tuple[Mapping[str, Any], ...]:
    return tuple(
        item
        for item in facts
        if item.get("current_visit_bound") is True
        and _clean(item.get("fact_type")).lower() == fact_type
    )


def _fact_state(facts: Sequence[Mapping[str, Any]], fact_type: str) -> str:
    matched = _matching_facts(facts, fact_type)
    states = {_clean(item.get("state")).lower() for item in matched}
    if states.intersection(_PRESENT_STATES):
        return "present"
    if states.intersection(_NEGATIVE_STATES):
        return "negative"
    return "unknown"


def _fact_value(facts: Sequence[Mapping[str, Any]], fact_type: str) -> str:
    for item in _matching_facts(facts, fact_type):
        value = item.get("value")
        if isinstance(value, Mapping):
            value = value.get("value") or value.get("class")
        if _clean(value):
            return _clean(value).upper()
    return ""


def _source_rows(
    documents: Mapping[str, Any], source_key: str
) -> tuple[Mapping[str, Any], ...]:
    rows = documents.get(source_key)
    if not isinstance(rows, list):
        return ()
    return tuple(
        item for item in rows[:_MAX_ROWS_PER_SOURCE] if isinstance(item, Mapping)
    )


def _first_source_document_id(
    documents: Mapping[str, Any], source_key: str
) -> str:
    """只使用当前受控来源行明确提供的文书 ID，禁止按正文或标题猜测。"""

    for row in _source_rows(documents, source_key):
        candidate = _clean(row.get("document_id") or row.get("id"))
        if candidate:
            return candidate
    return ""


def _source_document_refs(
    rows: Sequence[Mapping[str, Any]], *, source_type: str
) -> list[dict[str, str]]:
    refs: list[dict[str, str]] = []
    seen: set[str] = set()
    for row in rows:
        document_id = _clean(row.get("document_id") or row.get("id"))
        if not document_id or document_id in seen:
            continue
        seen.add(document_id)
        refs.append({"source_type": source_type, "source_document_id": document_id})
        if len(refs) == 8:
            break
    return refs


def _material_document_ref_for_row(
    *,
    materials: Luxian0609EvidenceMaterialStore,
    snapshot: Luxian0609EvidenceSnapshot,
    source_key: str,
    selected_row: Mapping[str, Any],
) -> str:
    """将已被判定器选中的那一行映射为同一材料仓文书引用。"""

    try:
        rows = materials.document_rows(source_key, snapshot=snapshot)
    except (EvidenceMaterialUnavailable, EvidenceMaterialTruncated, TypeError, ValueError):
        return ""
    for reference, row in rows:
        if row == selected_row:
            return reference
    return ""


def _projection_material_document_refs(
    *,
    projection: SurgeryTextProjection,
    projection_refs: Sequence[str],
    materials: Luxian0609EvidenceMaterialStore,
    snapshot: Luxian0609EvidenceSnapshot,
) -> tuple[str, ...]:
    """把受控 prompt 的 ``Sxx-yy`` 引用还原为同一材料仓逐行引用。"""

    selected: list[str] = []
    for projection_ref in projection_refs:
        source_key = projection.document_source_keys.get(projection_ref)
        document_id = _clean(projection.document_source_ids.get(projection_ref))
        if not source_key or not document_id:
            continue
        try:
            rows = materials.document_rows(source_key, snapshot=snapshot)
        except (EvidenceMaterialUnavailable, EvidenceMaterialTruncated, TypeError, ValueError):
            continue
        selected.extend(
            material_ref
            for material_ref, row in rows
            if _clean(row.get("document_id") or row.get("id")) == document_id
        )
    return tuple(dict.fromkeys(selected))


def _row_text(row: Mapping[str, Any]) -> str:
    approved_keys = (
        "content",
        "record_content",
        "assembled_text",
        "record_time",
        "surgery_name",
        "surgery_process",
        "surgeon",
        "recorder",
        "signer",
        "report_status",
        "device_code",
        "usage_status",
        "drug_code",
        "order_status",
    )
    return _clean(
        " ".join(_clean(row.get(key)) for key in approved_keys if _clean(row.get(key)))
    )


def _deterministic_024_outcome(
    *,
    surgery_rows: Sequence[Mapping[str, Any]],
    materials: Luxian0609EvidenceMaterialStore,
    snapshot: Luxian0609EvidenceSnapshot,
) -> _SurgeryTextOutcome | None:
    """收口手术记录中已实施且高特异性的 024 事实。"""

    row_texts = tuple((row, _row_text(row)) for row in surgery_rows)
    text = _clean(" ".join(row_text for _, row_text in row_texts if row_text))

    # 024 的合规短路只接受完整正式手术记录中的肯定淋巴结处理事实。
    # 不能把计划、建议或未实施描述当成已完成手术事实，也不能在材料仓
    # 无法返回实际命中文书引用时生成客户可见的合规结论。
    surgery_observation = next(
        (
            item
            for item in snapshot.observations
            if item.source_key == "surgery_record"
        ),
        None,
    )
    if (
        surgery_observation is not None
        and surgery_observation.query_state.value == "available"
        and surgery_observation.completeness.value == "complete"
        # 先保留原有非恶性创伤/急救手术的 N/A 优先级，避免新短路
        # 改变该既有例外的语义。
        and not (
            _TRAUMA_DIAGNOSIS_PATTERN.search(text)
            and _RESCUE_SURGERY_PATTERN.search(text)
            and _MALIGNANT_SURGERY_PATTERN.search(text)
        )
    ):
        lymph_node_action_pattern = re.compile(
            r"(?:清扫|切除|采样|取样|活检|送检|摘除|清除)\s*"
            r"(?:[0-9０-９一二三四五六七八九十百千万]+(?:组|站|枚)?"
            r"[\s、,，至\-－~～]*)*淋巴结"
            r"|淋巴结\s*(?:清扫|切除|采样|取样|活检|送检|摘除|清除)"
        )
        negative_or_planned_pattern = re.compile(
            r"(?:拟|计划|建议|准备|将|待|考虑|未|未予|未行|未做|未进行|未清扫|"
            r"没有|无|不|否认|取消|拒绝)"
            r"[^。；;！？!?，,]{0,8}"
            r"(?:清扫|切除|采样|取样|活检|送检|淋巴结)"
            r"|(?:清扫|切除|采样|取样|活检|送检|淋巴结)"
            r"[^。；;！？!?，,]{0,8}"
            r"(?:未予|未行|未做|未进行|未清扫|取消|拒绝|计划|建议)"
        )
        matching_document_refs: list[str] = []
        for row, row_text in row_texts:
            if (
                not has_strict_performed_time(row)
                or not _clean(row.get("document_id") or row.get("id"))
                or not _clean(row.get("surgery_name"))
                or not _clean(row.get("surgery_process"))
            ):
                continue
            matched = tuple(lymph_node_action_pattern.finditer(row_text))
            if not matched or any(
                negative_or_planned_pattern.search(
                    row_text[
                        max(
                            (
                                row_text.rfind(mark, 0, item.start())
                                for mark in "。；;！？!?，,\\n"
                            ),
                            default=-1,
                        )
                        + 1 : min(
                            (
                                next_position
                                for mark in "。；;！？!?，,\\n"
                                if (next_position := row_text.find(mark, item.end())) >= 0
                            ),
                            default=len(row_text),
                        )
                    ]
                )
                for item in matched
            ):
                continue
            ref = _material_document_ref_for_row(
                materials=materials,
                snapshot=snapshot,
                source_key="surgery_record",
                selected_row=row,
            )
            if ref:
                matching_document_refs.append(ref)
        if matching_document_refs:
            return _SurgeryTextOutcome(
                "LX0609-04-02-03",
                "compliant",
                "lymph_node_documentation_confirmed",
                selected_document_refs=tuple(dict.fromkeys(matching_document_refs)),
            )

    if (
        not text
        or not _TRAUMA_DIAGNOSIS_PATTERN.search(text)
        or not _RESCUE_SURGERY_PATTERN.search(text)
        or _MALIGNANT_SURGERY_PATTERN.search(text)
    ):
        return None
    # 保持迁移前的整组手术文本判定，仅选择实际贡献“创伤/急救手术”
    # 事实的行作为客户坐标，避免把同住院其他手术文书一并投影。
    matching_rows = tuple(
        row
        for row, row_text in row_texts
        if _TRAUMA_DIAGNOSIS_PATTERN.search(row_text)
        or _RESCUE_SURGERY_PATTERN.search(row_text)
    )
    selected_document_refs = tuple(
        ref
        for row in matching_rows
        if (
            ref := _material_document_ref_for_row(
                materials=materials,
                snapshot=snapshot,
                source_key="surgery_record",
                selected_row=row,
            )
        )
    )
    return _SurgeryTextOutcome(
        "LX0609-04-02-03",
        "not_applicable",
        "surgery_text_fact_absent",
        selected_document_refs=selected_document_refs,
    )


def _structured_nonmalignant_diagnoses(
    diagnosis_rows: Sequence[Mapping[str, Any]],
) -> bool:
    """诊断编码完整且均不在ICD恶性肿瘤C段时，明确排除024适用性。"""

    codes = tuple(
        _clean(row.get("diagnosis_code")).upper().replace(".", "")
        for row in diagnosis_rows
    )
    return bool(codes) and all(codes) and not any(
        re.fullmatch(r"C(?:[0-8]\d|9[0-7]).*", code) for code in codes
    )


def _structured_028_not_applicable(
    *,
    surgery_rows: Sequence[Mapping[str, Any]],
    mr_surgery_rows: Sequence[Mapping[str, Any]],
) -> bool:
    """没有手术记录且结构化手术行无I/II切口积极事实时，不触发028。"""

    if surgery_rows or not mr_surgery_rows:
        return False
    target_classes = {"I", "II", "Ⅰ", "Ⅱ"}
    incision_classes = {
        _clean(
            row.get("surgical_incision_level") or row.get("surgial_incision_level")
        ).upper()
        for row in mr_surgery_rows
    }
    return not bool(incision_classes.intersection(target_classes))


def _qualified_traditional_surgery_present(
    rows: Sequence[Mapping[str, Any]],
) -> bool:
    """复用院内目录口径，目录未命中时才回退结构化等级。"""

    return any(has_qualified_traditional_surgery_row(row) for row in rows)


def _context(rule_id: str, documents: Mapping[str, Any]) -> str:
    parts: list[str] = []
    for source_key in _RULE_SOURCES[rule_id]:
        for index, row in enumerate(_source_rows(documents, source_key), start=1):
            if text := _row_text(row):
                parts.append(f"[{source_key}-{index}] {text[:_MAX_ROW_CHARS]}")
    return "\n".join(parts)[:_MAX_CONTEXT_CHARS]


def _prompt(wrapper: Mapping[str, Any], context: str) -> str:
    custom = _MAPPING_LINE_PATTERN.sub("", str(wrapper.get("custom_prompt") or ""))
    prompt = (
        custom.replace("{defect_level}", str(wrapper.get("defect_level") or ""))
        .replace("{medical_text}", context)
        .strip()
    )
    rule_id = str(wrapper.get("rule_id") or wrapper.get("rule_code") or "").strip().upper()
    if rule_id == "LX0609-04-02-04":
        allowed_fields = "、".join(LX0609_025_REQUIRED_FIELDS)
        prompt += (
            "\n补充输出要求：若判定不合规，必须同时返回 missing_fields 数组；仅可使用"
            f"{allowed_fields}。数组只列本次手术记录中明确缺失的必填项；"
            "implant_barcode 不属于本规则，禁止返回；病程记录不能补足手术记录字段；"
            "无法确定时返回空数组。"
        )
    return prompt


def _response_text(response: Mapping[str, Any]) -> str:
    choices = response.get("choices")
    if isinstance(choices, list) and choices and isinstance(choices[0], Mapping):
        message = choices[0].get("message")
        if isinstance(message, Mapping):
            return str(message.get("content") or "")
    return str(response.get("content") or response.get("text") or "")


def _parse_response_payload(response: Mapping[str, Any]) -> Mapping[str, Any] | None:
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
    return payload if isinstance(payload, Mapping) else None


def _parse_is_compliant(response: Mapping[str, Any]) -> bool | None:
    payload = _parse_response_payload(response)
    if payload is None:
        return None
    value = payload.get("is_compliant") if isinstance(payload, Mapping) else None
    return value if isinstance(value, bool) else None


def _parse_implant_missing_fields(response: Mapping[str, Any]) -> tuple[str, ...]:
    payload = _parse_response_payload(response)
    values = payload.get("missing_fields") if payload is not None else None
    if not isinstance(values, list):
        return ()
    allowed = set(LX0609_025_REQUIRED_FIELDS)
    return tuple(value for value in values if value in allowed)


def _usage(response: Mapping[str, Any]) -> tuple[int, int, int, float]:
    usage = response.get("usage")
    usage = usage if isinstance(usage, Mapping) else {}
    prompt = int(usage.get("prompt_tokens") or 0)
    completion = int(usage.get("completion_tokens") or 0)
    total = int(usage.get("total_tokens") or prompt + completion)
    return prompt, completion, total, float(response.get("_api_time") or 0.0)


def _result(
    rule_id: str,
    status: str,
    reason_code: str,
    *,
    executor_type: str,
    prompt_tokens: int = 0,
    completion_tokens: int = 0,
    total_tokens: int = 0,
    api_time: float = 0.0,
    customer_display_facts: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
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
    metadata.update(
        {
            "executor_type": executor_type,
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": total_tokens,
            "api_time": api_time,
        }
    )
    if customer_display_facts is not None:
        metadata["customer_display_facts"] = dict(customer_display_facts)
    item["metadata"] = metadata
    return item


def _has_exact_time(rows: Sequence[Mapping[str, Any]]) -> bool:
    return any(has_strict_performed_time(row) for row in rows)


def _has_signature(rows: Sequence[Mapping[str, Any]]) -> bool:
    for row in rows:
        surgeon = _clean(row.get("surgeon"))
        signer = _clean(
            row.get("surgeon_sign")
            or row.get("physician_sign")
            or row.get("signer")
        )
        if surgeon and signer and surgeon == signer:
            return True
    return False


def _surgery_signature_outcome(
    rows: Sequence[Mapping[str, Any]],
) -> tuple[str, str, Mapping[str, Any] | None]:
    """031：按同一手术事件核对术者与权威签名；有书写者时再核对代写资格。"""

    if not rows:
        return "data_gap", "required_field_missing", None
    states: list[str] = []
    used_first_assistant_exception = False
    # 仅在多台手术时投影逐台事实，保持单台旧结果 DTO 稳定。
    event_facts: list[dict[str, Any]] = []

    def identity(value: Any) -> str:
        normalized = re.sub(r"[\s,，、;；:：]+", "", _clean(value))
        if normalized in {"签名", "已签名", "已签", "电子签名"}:
            return ""
        return re.sub(r"(?:主任医师|副主任医师|主治医师|住院医师|医师|医生)$", "", normalized)

    for row in rows:
        surgeon = identity(row.get("surgeon"))
        recorder = identity(
            row.get("recorder") or row.get("recorder_sign") or row.get("submitter")
        )
        signer = identity(
            row.get("surgeon_sign")
            or row.get("main_surgery_sign")
            or row.get("signer")
        )
        first_assistant = identity(row.get("first_assistant"))
        missing_fields = []
        if not surgeon:
            missing_fields.append("surgeon")
        if not signer:
            missing_fields.append("surgeon_sign")
        if len(rows) > 1:
            event_facts.append(
                {
                    "document_id": _clean(row.get("document_id") or row.get("sys_index_id")),
                    "surgery_name": _clean(row.get("surgery_name") or row.get("surgery_project")),
                    "surgeon": surgeon,
                    "signer": signer,
                    "missing_fields": missing_fields,
                }
            )
        if not surgeon or not signer:
            states.append("unknown")
            continue
        if signer != surgeon:
            states.append("defect")
            continue
        if not recorder:
            states.append("satisfied")
            continue
        if recorder == surgeon:
            states.append("satisfied")
            continue
        if first_assistant and recorder == first_assistant:
            used_first_assistant_exception = True
            states.append("satisfied")
            continue
        states.append("defect")
    if "defect" in states:
        return (
            "non_compliant",
            "surgery_signer_not_qualified",
            {
                "failure_kind": "surgery_signer_not_qualified",
                "performed_surgery_confirmed": True,
                "surgeon_signature_matches": False,
                **({"surgery_events": event_facts} if event_facts else {}),
            },
        )
    if not states or "unknown" in states:
        return (
            "data_gap",
            "required_field_missing",
            (
                {
                    "failure_kind": "surgery_signature_fields_missing",
                    "performed_surgery_confirmed": True,
                    "surgery_events": event_facts,
                }
                if event_facts
                else None
            ),
        )
    return (
        "compliant",
        "surgery_signature_confirmed",
        {
            "verification_kind": "surgery_signature_confirmed",
            "performed_surgery_confirmed": True,
            "surgeon_signature_matches": True,
            "first_assistant_exception_used": used_first_assistant_exception,
            **({"surgery_events": event_facts} if event_facts else {}),
        },
    )


def _resolve_surgery_signature_outcome(
    *,
    surgery_master_rows: Sequence[Mapping[str, Any]],
    surgery_record_rows: Sequence[Mapping[str, Any]],
) -> tuple[str, str, Mapping[str, Any] | None]:
    """优先采用手术主表签名；仅对唯一且术者一致的事件使用文书表回退。"""

    outcome, _source_key, _selected_rows = _resolve_surgery_signature_selection(
        surgery_master_rows=surgery_master_rows,
        surgery_record_rows=surgery_record_rows,
    )
    return outcome


def _resolve_surgery_signature_selection(
    *,
    surgery_master_rows: Sequence[Mapping[str, Any]],
    surgery_record_rows: Sequence[Mapping[str, Any]],
) -> tuple[
    tuple[str, str, Mapping[str, Any] | None],
    str,
    tuple[Mapping[str, Any], ...],
]:
    """返回签名判定及其实际采用的唯一来源行。"""

    if not surgery_master_rows:
        return (
            _surgery_signature_outcome(surgery_record_rows),
            "surgery_record",
            tuple(surgery_record_rows),
        )
    master_outcome = _surgery_signature_outcome(surgery_master_rows)
    if master_outcome[0] == "non_compliant":
        return master_outcome, "mr_surgery", tuple(surgery_master_rows)
    if not surgery_record_rows:
        return ("data_gap", "required_field_missing", None), "", ()
    if len(surgery_master_rows) != len(surgery_record_rows) or (
        len(surgery_master_rows) > 1 and master_outcome[0] == "data_gap"
    ):
        # 术式拆行可以共用同台记录，但须以受控时间证明事件覆盖。
        # 主表已有部分签名时仍保留逐行缺口，不能被文书回退覆盖。
        master_signature_fields = (
            "main_surgery_sign",
            "surgeon_sign",
            "physician_sign",
            "signer",
        )
        master_has_signature_fact = any(
            _clean(row.get(field))
            for row in surgery_master_rows
            for field in master_signature_fields
        )
        if not master_has_signature_fact:
            record_outcome = _surgery_signature_outcome(surgery_record_rows)
            if record_outcome[0] != "data_gap" and not _surgery_records_cover_master_rows(
                surgery_master_rows, surgery_record_rows
            ):
                return ("data_gap", "association_failed", None), "", ()
            return record_outcome, "surgery_record", tuple(surgery_record_rows)
        if master_outcome[0] in {"compliant", "non_compliant"}:
            return master_outcome, "mr_surgery", tuple(surgery_master_rows)
        return ("data_gap", "required_field_missing", None), "", ()
    if len(surgery_master_rows) != 1:
        return master_outcome, "mr_surgery", tuple(surgery_master_rows)
    if master_outcome[0] != "data_gap":
        return master_outcome, "mr_surgery", tuple(surgery_master_rows)

    master_surgeon = re.sub(
        r"[\s,，、;；:：]+", "", _clean(surgery_master_rows[0].get("surgeon"))
    )
    record_surgeon = re.sub(
        r"[\s,，、;；:：]+", "", _clean(surgery_record_rows[0].get("surgeon"))
    )
    if (
        master_surgeon and record_surgeon and master_surgeon != record_surgeon
    ) or not _surgery_records_cover_master_rows(surgery_master_rows, surgery_record_rows):
        return ("data_gap", "association_failed", None), "", ()
    return (
        _surgery_signature_outcome(surgery_record_rows),
        "surgery_record",
        tuple(surgery_record_rows),
    )


def _authoritative_record_time(value: Any) -> datetime | None:
    """只接受 record_time 整值；不从正文、标题或局部文本提取时间。"""

    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, str):
        candidate = value.strip()
        if not _AUTHORITATIVE_RECORD_TIME_PATTERN.fullmatch(candidate):
            return None
        try:
            parsed = datetime.fromisoformat(candidate.replace("Z", "+00:00"))
        except ValueError:
            return None
    else:
        return None
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        return parsed
    return parsed.astimezone(_HOSPITAL_TIMEZONE).replace(tzinfo=None)


def _authoritative_surgery_time(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        if value.tzinfo is None or value.utcoffset() is None:
            return value
        return value.astimezone(_HOSPITAL_TIMEZONE).replace(tzinfo=None)
    return parse_strict_performed_time(value)


def _authoritative_surgery_end_time(
    *, source_key: str, row: Mapping[str, Any]
) -> datetime | None:
    """003 只以受控手术结束时间为锚，不用开始时间替代。"""

    if source_key == "surgery_record":
        parsed = tuple(
            value
            for field in ("surgery_end_time", "surgery_end_datetime")
            if (value := _authoritative_surgery_time(row.get(field))) is not None
        )
        return max(parsed) if parsed else None
    if source_key == "mr_surgery":
        value = row.get("surgery_end_datetime")
        return value if isinstance(value, datetime) and value.tzinfo is None else None
    return None


def _authoritative_surgery_begin_time(row: Mapping[str, Any]) -> datetime | None:
    """读取手术记录的结构化开始时间，用于关联同台麻醉记录。"""

    values = tuple(
        value
        for field in ("surgery_begin_time", "surgery_begin_datetime")
        if (value := _authoritative_surgery_time(row.get(field))) is not None
    )
    return max(values) if values else None


def _surgery_records_cover_master_rows(
    master_rows: Sequence[Mapping[str, Any]],
    record_rows: Sequence[Mapping[str, Any]],
) -> bool:
    """证明逐台覆盖；同台术式拆行可共用记录，关联不明不等于缺文书。"""

    def identity(row: Mapping[str, Any]) -> tuple[datetime | None, datetime | None, str]:
        return (
            _authoritative_surgery_begin_time(row),
            _authoritative_surgery_time(
                row.get("surgery_end_datetime") or row.get("surgery_end_time")
            ),
            re.sub(r"[\s,，、;；:：]+", "", _clean(row.get("surgeon"))),
        )

    masters = tuple(identity(row) for row in master_rows)
    records = tuple(identity(row) for row in record_rows)
    for master in masters:
        matches = []
        for record in records:
            shared_times = [(a, b) for a, b in zip(master[:2], record[:2]) if a and b]
            if any(a != b for a, b in shared_times):
                continue
            if master[2] and record[2] and master[2] != record[2]:
                continue
            # 保留唯一主表/文书的既有回退；多行必须有完全相同的时间锚点。
            if shared_times or len(masters) == len(records) == 1:
                matches.append(record)
        if not matches:
            return False
        # 一份记录只能覆盖身份相同的拆行，不能因共有结束时间串用另一台。
        for matched in matches:
            candidates = [
                other for other in masters
                if any(a and b and a == b for a, b in zip(other[:2], matched[:2]))
                and not any(a and b and a != b for a, b in zip(other, matched))
            ]
            if len(candidates) > 1 and len(set(candidates)) > 1:
                return False
    return True


def _labeled_anesthesia_surgery_time(
    row: Mapping[str, Any], *, label: str
) -> datetime | None:
    """只读取麻醉记录正文中唯一、带时区且明确标注的手术时间。"""

    text = str(row.get("record_content") or "")
    pattern = re.compile(
        _LABELED_SURGERY_TIME_PATTERN_TEMPLATE.format(label=re.escape(label))
    )
    parsed = tuple(
        value
        for match in pattern.finditer(text)
        if (value := parse_strict_performed_time(match.group("value"))) is not None
    )
    unique = tuple(dict.fromkeys(parsed))
    return unique[0] if len(unique) == 1 else None


def _typed_003_decision(
    *,
    snapshot: Luxian0609EvidenceSnapshot,
    materials: Luxian0609EvidenceMaterialStore,
    customer_display_facts: list[tuple[str, Mapping[str, Any]]] | None = None,
) -> RuleDecision:
    """用同一 Evidence Session 的权威时间完成 003 判定。"""

    if (
        type(snapshot) is not Luxian0609EvidenceSnapshot
        or type(materials) is not Luxian0609EvidenceMaterialStore
        or materials.snapshot_hash != snapshot.snapshot_hash
    ):
        raise ValueError("typed 003 requires one evidence session")
    source_keys = (
        "surgery_record",
        "anesthesia_record",
        "mr_surgery",
        "surgery_application",
        "inpat_nondrug_order",
        "evaluation_context.horizon",
    )
    observations = {
        item.source_key: item
        for item in snapshot.observations
        if item.source_key in source_keys
    }
    refs = tuple(
        observations[key].snapshot_ref.removeprefix("sha256:")
        for key in source_keys
        if key in observations
    )
    def decision(
        final_state: str,
        reason_code: str,
        display_facts: Mapping[str, Any] | None = None,
        selected_document_refs: tuple[str, ...] = (),
    ) -> RuleDecision:
        if display_facts is not None and customer_display_facts is not None:
            customer_display_facts.append(("LX0609-04-02-01", display_facts))
        applicability, evidence_state, qc_direction = {
            "compliant": (
                ApplicabilityState.APPLICABLE,
                EvidenceState.SUFFICIENT,
                QcDirection.SATISFIED,
            ),
            "non_compliant": (
                ApplicabilityState.APPLICABLE,
                EvidenceState.SUFFICIENT,
                QcDirection.DEFECT,
            ),
            "not_applicable": (
                ApplicabilityState.NOT_APPLICABLE,
                EvidenceState.SUFFICIENT,
                QcDirection.UNKNOWN,
            ),
            "data_gap": (
                ApplicabilityState.UNKNOWN,
                EvidenceState.DATA_GAP,
                QcDirection.UNKNOWN,
            ),
            "technical_error": (
                ApplicabilityState.ERROR,
                EvidenceState.TECHNICAL_ERROR,
                QcDirection.UNKNOWN,
            ),
        }[final_state]
        return RuleDecision(
            rule_id="LX0609-04-02-01",
            snapshot_hash=snapshot.snapshot_hash,
            applicability=applicability,
            evidence_state=evidence_state,
            qc_direction=qc_direction,
            reason_code=reason_code,
            fact_refs=tuple(dict.fromkeys((*selected_document_refs, *refs))),
            evaluator_version=_TYPED_003_EVALUATOR_VERSION,
            confidence=None,
        )

    if set(observations) != set(source_keys):
        return decision("technical_error", "snapshot_mismatch")
    ordered = tuple(observations[key] for key in source_keys)
    if any(item.query_state.value == "error" for item in ordered):
        return decision("technical_error", "source_query_error")
    surgery_observation = observations["surgery_record"]
    if surgery_observation.query_state.value == "unavailable":
        return decision("data_gap", "source_unavailable")
    if surgery_observation.completeness.value == "truncated":
        return decision("data_gap", "source_truncated")
    try:
        surgery_rows = tuple(materials.rows("surgery_record"))
    except EvidenceMaterialTruncated:
        return decision("data_gap", "source_truncated")
    except EvidenceMaterialUnavailable:
        return decision("technical_error", "snapshot_mismatch")

    support_rows: dict[str, tuple[Mapping[str, Any], ...]] = {}
    for source_key in source_keys[1:]:
        observation = observations[source_key]
        if observation.query_state.value == "unavailable":
            support_rows[source_key] = ()
            continue
        if observation.completeness.value == "truncated":
            support_rows[source_key] = ()
            continue
        try:
            support_rows[source_key] = tuple(materials.rows(source_key))
        except EvidenceMaterialTruncated:
            support_rows[source_key] = ()
        except EvidenceMaterialUnavailable:
            return decision("technical_error", "snapshot_mismatch")

    mr_rows = support_rows["mr_surgery"]
    if not surgery_rows:
        qualified_mr_rows = tuple(
            row for row in mr_rows if _qualified_traditional_surgery_present((row,))
        )
        if qualified_mr_rows:
            # 003 缺正式手术记录时，只能由唯一一台主表手术形成“应有记录”的
            # 结论。同一结束时间不能把多行不同手术事件压成一个时间点。
            if len(qualified_mr_rows) != 1:
                return decision("data_gap", "association_failed")
            selected_mr_ref = _material_document_ref_for_row(
                materials=materials,
                snapshot=snapshot,
                source_key="mr_surgery",
                selected_row=qualified_mr_rows[0],
            )
            surgery_end_time = _authoritative_surgery_end_time(
                source_key="mr_surgery", row=qualified_mr_rows[0]
            )
            if surgery_end_time is None:
                return decision("data_gap", "authoritative_time_missing")
            horizon_observation = observations["evaluation_context.horizon"]
            if horizon_observation.query_state.value == "empty":
                return decision(
                    "data_gap",
                    horizon_observation.reason_code or "authoritative_time_missing",
                )
            if horizon_observation.query_state.value != "available":
                return decision("technical_error", "snapshot_mismatch")
            try:
                horizon_rows = tuple(materials.rows("evaluation_context.horizon"))
            except EvidenceMaterialTruncated:
                return decision("technical_error", "snapshot_mismatch")
            except EvidenceMaterialUnavailable:
                return decision("technical_error", "snapshot_mismatch")
            if len(horizon_rows) != 1:
                return decision("technical_error", "snapshot_mismatch")
            horizon_row = horizon_rows[0]
            try:
                horizon_date = datetime.fromisoformat(
                    str(horizon_row["horizon_date"])
                ).date()
            except (KeyError, TypeError, ValueError):
                return decision("technical_error", "snapshot_mismatch")
            raw_horizon_datetime = horizon_row.get("horizon_datetime")
            try:
                horizon_datetime = (
                    datetime.fromisoformat(str(raw_horizon_datetime))
                    if raw_horizon_datetime is not None
                    else None
                )
            except ValueError:
                return decision("technical_error", "snapshot_mismatch")
            if horizon_datetime is not None:
                if horizon_datetime.tzinfo is not None:
                    return decision("technical_error", "snapshot_mismatch")
                if horizon_datetime.date() != horizon_date:
                    return decision("data_gap", "authoritative_time_conflict")
                if horizon_datetime < surgery_end_time:
                    return decision("data_gap", "authoritative_time_conflict")
                mature = horizon_datetime - surgery_end_time >= timedelta(hours=24)
            else:
                if horizon_date < surgery_end_time.date():
                    return decision("data_gap", "authoritative_time_conflict")
                mature = horizon_date > (surgery_end_time + timedelta(hours=24)).date()
            return decision(
                "non_compliant" if mature else "data_gap",
                "required_document_missing"
                if mature
                else "evaluation_window_not_mature",
                selected_document_refs=(
                    (selected_mr_ref,) if mature and selected_mr_ref else ()
                ),
            )
        if (
            observations["mr_surgery"].query_state.value == "available"
            and observations["mr_surgery"].completeness.value == "complete"
            and mr_rows
            and not _qualified_traditional_surgery_present(mr_rows)
        ):
            return decision(
                "not_applicable",
                "performed_event_absent",
                {
                    "failure_kind": "qualified_surgery_absent",
                    "performed_surgery_confirmed": False,
                },
            )
        application_observation = observations["surgery_application"]
        order_observation = observations["inpat_nondrug_order"]
        if any(
            item.completeness.value == "truncated"
            for item in (observations["mr_surgery"], application_observation, order_observation)
        ):
            return decision("data_gap", "source_truncated")
        if any(
            item.query_state.value == "unavailable"
            for item in (application_observation, order_observation)
        ):
            return decision("data_gap", "source_unavailable")
        order_types = tuple(
            _clean(row.get("order_type"))
            for row in support_rows["inpat_nondrug_order"]
        )
        known_non_surgery_order_types = {
            "检查",
            "检验",
            "治疗",
            "护理",
            "嘱托",
            "转科",
            "其他",
        }
        if any(
            not order_type
            or order_type not in {*known_non_surgery_order_types, "手术"}
            for order_type in order_types
        ):
            return decision("data_gap", "authoritative_time_missing")
        has_surgery_order = "手术" in order_types
        if (
            not mr_rows
            and not support_rows["surgery_application"]
            and not has_surgery_order
        ):
            return decision(
                "not_applicable",
                "performed_event_absent",
                {
                    "failure_kind": "surgery_not_performed",
                    "performed_surgery_confirmed": False,
                },
            )
        return decision("data_gap", "authoritative_time_missing")

    intervals: list[
        tuple[timedelta, datetime, datetime, str | None, tuple[str, ...]]
    ] = []
    incomplete_performed_row = False
    missing_time_fields: set[str] = set()
    time_conflict = False
    fallback_resolved = False
    for row in surgery_rows:
        surgery_end_time = _authoritative_surgery_end_time(
            source_key="surgery_record", row=row
        )
        record_time = _authoritative_record_time(row.get("record_time"))
        if surgery_end_time is None or record_time is None:
            if surgery_end_time is None:
                missing_time_fields.add("surgery_end_time")
            if record_time is None:
                missing_time_fields.add("record_time")
            incomplete_performed_row = True
            continue
        interval = record_time - surgery_end_time
        if interval.total_seconds() < 0:
            time_conflict = True
            incomplete_performed_row = True
            continue
        document_id = str(row.get("document_id") or "").strip() or None
        document_ref = _material_document_ref_for_row(
            materials=materials,
            snapshot=snapshot,
            source_key="surgery_record",
            selected_row=row,
        )
        intervals.append(
            (
                interval,
                surgery_end_time,
                record_time,
                document_id,
                (document_ref,) if document_ref else (),
            )
        )

    # 当 surgery_record 自身没有批准手术时间时，仅允许唯一 mr_surgery 时间
    # 与唯一手术记录时间配对；多记录无关联键时必须保守为数据不足。
    if not intervals:
        mr_end_times = tuple(
            sorted({
                time
                for row in mr_rows
                if (time := _authoritative_surgery_end_time(
                    source_key="mr_surgery", row=row
                )) is not None
            })
        )
        record_times = tuple(
            sorted({
                parsed
                for row in surgery_rows
                if (parsed := _authoritative_record_time(row.get("record_time")))
                is not None
            })
        )
        if (
            len(mr_rows) == 1
            and len(surgery_rows) == 1
            and len(mr_end_times) == 1
            and len(record_times) == 1
        ):
            interval = record_times[0] - mr_end_times[0]
            if interval.total_seconds() >= 0:
                document_id = (
                    str(surgery_rows[0].get("document_id") or "").strip() or None
                )
                document_ref = _material_document_ref_for_row(
                    materials=materials,
                    snapshot=snapshot,
                    source_key="surgery_record",
                    selected_row=surgery_rows[0],
                )
                intervals.append(
                    (
                        interval,
                        mr_end_times[0],
                        record_times[0],
                        document_id,
                        (document_ref,) if document_ref else (),
                    )
                )
                fallback_resolved = True

    # 源合同已将 anesthesia_record 列为 003 的判定资料。只有唯一手术记录
    # 与唯一麻醉记录的结构化/明确标注开始时间完全相同时，才允许用麻醉记录
    # 中明确标注的手术结束时间补齐锚点，避免跨手术串用。
    anesthesia_rows = support_rows["anesthesia_record"]
    anesthesia_association_failed = False
    if not intervals and len(surgery_rows) == len(anesthesia_rows) == 1:
        surgery_begin_time = _authoritative_surgery_begin_time(surgery_rows[0])
        anesthesia_begin_time = _labeled_anesthesia_surgery_time(
            anesthesia_rows[0], label="手术开始时间"
        )
        anesthesia_end_time = _labeled_anesthesia_surgery_time(
            anesthesia_rows[0], label="手术结束时间"
        )
        record_time = _authoritative_record_time(surgery_rows[0].get("record_time"))
        if (
            surgery_begin_time is not None
            and anesthesia_begin_time == surgery_begin_time
            and anesthesia_end_time is not None
            and record_time is not None
        ):
            interval = record_time - anesthesia_end_time
            if interval.total_seconds() >= 0:
                surgery_ref = _material_document_ref_for_row(
                    materials=materials,
                    snapshot=snapshot,
                    source_key="surgery_record",
                    selected_row=surgery_rows[0],
                )
                anesthesia_ref = _material_document_ref_for_row(
                    materials=materials,
                    snapshot=snapshot,
                    source_key="anesthesia_record",
                    selected_row=anesthesia_rows[0],
                )
                document_id = (
                    str(surgery_rows[0].get("document_id") or "").strip() or None
                )
                intervals.append(
                    (
                        interval,
                        anesthesia_end_time,
                        record_time,
                        document_id,
                        tuple(ref for ref in (surgery_ref, anesthesia_ref) if ref),
                    )
                )
                fallback_resolved = True
            else:
                time_conflict = True
        elif anesthesia_begin_time is not None and anesthesia_end_time is not None:
            anesthesia_association_failed = True

    late_interval = next(
        (
            item
            for item in intervals
            if item[0] > timedelta(hours=24)
        ),
        None,
    )
    if late_interval is not None:
        (
            interval,
            surgery_end_time,
            record_time,
            source_document_id,
            document_refs,
        ) = late_interval
        display_facts: dict[str, Any] = {
            "failure_kind": "surgery_record_late",
            "performed_surgery_confirmed": True,
            "surgery_end_time": surgery_end_time.strftime("%Y-%m-%d %H:%M:%S"),
            "record_time": record_time.strftime("%Y-%m-%d %H:%M:%S"),
            "elapsed_hours": round(interval.total_seconds() / 3600, 2),
            "threshold_hours": 24,
            "source_label": "手术记录",
        }
        if source_document_id:
            display_facts["source_document_id"] = source_document_id
        return decision(
            "non_compliant",
            "threshold_exceeded",
            display_facts,
            document_refs,
        )
    if intervals and (not incomplete_performed_row or fallback_resolved):
        qualified_mr_rows = tuple(
            row for row in mr_rows if _qualified_traditional_surgery_present((row,))
        )
        if not _surgery_records_cover_master_rows(qualified_mr_rows, surgery_rows):
            return decision("data_gap", "association_failed", {
                "failure_kind": "surgery_timeliness_data_gap",
                "gap_reason": "association_failed",
                "missing_fields": ["surgery_record_association"],
            })
        (
            interval,
            surgery_end_time,
            record_time,
            source_document_id,
            document_refs,
        ) = min(intervals, key=lambda item: item[2])
        display_facts = {
            "failure_kind": "surgery_record_within_threshold",
            "performed_surgery_confirmed": True,
            "surgery_end_time": surgery_end_time.strftime("%Y-%m-%d %H:%M:%S"),
            "record_time": record_time.strftime("%Y-%m-%d %H:%M:%S"),
            "elapsed_hours": round(interval.total_seconds() / 3600, 2),
            "threshold_hours": 24,
            "source_label": "手术记录",
        }
        if source_document_id:
            display_facts["source_document_id"] = source_document_id
        return decision(
            "compliant",
            "requirement_within_threshold",
            display_facts,
            document_refs,
        )
    mr_observation = observations["mr_surgery"]
    if mr_observation.query_state.value == "unavailable":
        return decision("data_gap", "source_unavailable")
    if mr_observation.completeness.value == "truncated":
        return decision("data_gap", "source_truncated")
    # 只报告本次实际未能完成核对的字段，不把所有可能原因混成一句话。
    reason = "authoritative_time_missing"
    if time_conflict and not missing_time_fields:
        reason = "authoritative_time_conflict"
    elif not intervals and anesthesia_association_failed:
        reason = "association_failed"
        missing_time_fields.discard("surgery_end_time")
        missing_time_fields.add("surgery_record_association")
    elif not intervals and mr_end_times and (len(mr_rows) != 1 or len(surgery_rows) != 1):
        reason = "association_failed"
        missing_time_fields.discard("surgery_end_time")
        missing_time_fields.add("surgery_record_association")
    elif not intervals and len(mr_rows) == len(surgery_rows) == 1 and mr_end_times:
        missing_time_fields.discard("surgery_end_time")
        if record_times and record_times[0] < mr_end_times[0]:
            reason = "authoritative_time_conflict"
    return decision("data_gap", reason, {
        "failure_kind": "surgery_timeliness_data_gap",
        "gap_reason": reason,
        "missing_fields": sorted(missing_time_fields),
    })


def _typed_conservative_surgery_gate_decision(
    *,
    rule_id: str,
    snapshot: Luxian0609EvidenceSnapshot,
    materials: Luxian0609EvidenceMaterialStore,
    customer_display_facts: list[tuple[str, Mapping[str, Any]]] | None = None,
) -> RuleDecision:
    """迁移高风险手术门控，但不把旧关键词/文书存在提升为临床事实。"""

    if rule_id not in _TYPED_DECISION_RULE_IDS - {"LX0609-04-02-01"}:
        raise ValueError("unsupported typed surgery gate rule")
    if materials.snapshot_hash != snapshot.snapshot_hash:
        raise ValueError("typed surgery gate requires one evidence session")
    source_keys = ("surgery_record", "mr_surgery")
    observation_by_source = {
        item.source_key: item
        for item in snapshot.observations
        if item.source_key in source_keys
    }
    observations = tuple(
        observation_by_source[key]
        for key in source_keys
        if key in observation_by_source
    )
    refs = tuple(
        item.snapshot_ref.removeprefix("sha256:") for item in observations
    )
    def decision(
        *,
        applicability: ApplicabilityState,
        evidence_state: EvidenceState,
        qc_direction: QcDirection,
        reason_code: str,
        selected_document_refs: tuple[str, ...] = (),
    ) -> RuleDecision:
        return RuleDecision(
            rule_id=rule_id,
            snapshot_hash=snapshot.snapshot_hash,
            applicability=applicability,
            evidence_state=evidence_state,
            qc_direction=qc_direction,
            reason_code=reason_code,
            fact_refs=tuple(dict.fromkeys((*selected_document_refs, *refs))),
            evaluator_version=_TYPED_SURGERY_GATE_EVALUATOR_VERSION,
            confidence=None,
        )

    if set(observation_by_source) != set(source_keys):
        return decision(
            applicability=ApplicabilityState.ERROR,
            evidence_state=EvidenceState.TECHNICAL_ERROR,
            qc_direction=QcDirection.UNKNOWN,
            reason_code="snapshot_mismatch",
        )
    surgery_observation = observation_by_source["surgery_record"]

    # 033只检查“已有手术记录时是否缺手术知情同意书”。手术记录来源已完整
    # 查询且为空时，缺手术记录由030负责，不能把033继续推入同意书缺口。
    if (
        rule_id == "LX0609-11-01-01"
        and surgery_observation.query_state.value == "empty"
        and surgery_observation.completeness.value == "complete"
    ):
        return decision(
            applicability=ApplicabilityState.NOT_APPLICABLE,
            evidence_state=EvidenceState.SUFFICIENT,
            qc_direction=QcDirection.UNKNOWN,
            reason_code="performed_event_absent",
        )

    surgery_applicability = resolve_surgery_applicability(
        snapshot=snapshot,
        materials=materials,
    )
    if surgery_applicability.state == "technical_error":
        return decision(
            applicability=ApplicabilityState.ERROR,
            evidence_state=EvidenceState.TECHNICAL_ERROR,
            qc_direction=QcDirection.UNKNOWN,
            reason_code=surgery_applicability.reason_code,
        )
    if surgery_applicability.state == "not_applicable":
        return decision(
            applicability=ApplicabilityState.NOT_APPLICABLE,
            evidence_state=EvidenceState.SUFFICIENT,
            qc_direction=QcDirection.UNKNOWN,
            reason_code="performed_event_absent",
        )
    if surgery_applicability.state != "applicable":
        return decision(
            applicability=ApplicabilityState.UNKNOWN,
            evidence_state=EvidenceState.DATA_GAP,
            qc_direction=QcDirection.UNKNOWN,
            reason_code=surgery_applicability.reason_code,
        )

    if rule_id == "LX0609-04-02-05":
        selected_signature_source = ""
        selected_signature_rows: tuple[Mapping[str, Any], ...] = ()
        try:
            surgery_record_rows = tuple(materials.rows("surgery_record"))
            surgery_master_rows = tuple(materials.rows("mr_surgery"))
        except EvidenceMaterialTruncated:
            final_state, reason_code, display_facts = (
                "data_gap",
                "source_truncated",
                None,
            )
        except EvidenceMaterialUnavailable:
            final_state, reason_code, display_facts = (
                "data_gap",
                "source_unavailable",
                None,
            )
        else:
            (
                (final_state, reason_code, display_facts),
                selected_signature_source,
                selected_signature_rows,
            ) = _resolve_surgery_signature_selection(
                surgery_master_rows=surgery_master_rows,
                surgery_record_rows=surgery_record_rows,
            )
        selected_signature_refs = tuple(
            ref
            for row in selected_signature_rows
            if (
                ref := _material_document_ref_for_row(
                    materials=materials,
                    snapshot=snapshot,
                    source_key=selected_signature_source,
                    selected_row=row,
                )
            )
        ) if display_facts is not None else ()
        if display_facts is not None and customer_display_facts is not None:
            customer_display_facts.append((rule_id, display_facts))
        applicability, evidence_state, qc_direction = {
            "compliant": (
                ApplicabilityState.APPLICABLE,
                EvidenceState.SUFFICIENT,
                QcDirection.SATISFIED,
            ),
            "non_compliant": (
                ApplicabilityState.APPLICABLE,
                EvidenceState.SUFFICIENT,
                QcDirection.DEFECT,
            ),
            "data_gap": (
                ApplicabilityState.APPLICABLE,
                EvidenceState.DATA_GAP,
                QcDirection.UNKNOWN,
            ),
        }[final_state]
        return decision(
            applicability=applicability,
            evidence_state=evidence_state,
            qc_direction=qc_direction,
            reason_code=(
                "requirement_satisfied"
                if final_state == "compliant"
                else "requirement_violated"
                if final_state == "non_compliant"
                else reason_code
            ),
            selected_document_refs=selected_signature_refs,
        )

    # 其余规则仍缺少可审计的恶性手术关联、植入物实际使用、预防用药
    # 实际区间或同意书同步完整性事实。迁移只改变执行契约，不制造结论。
    return decision(
        applicability=(
            ApplicabilityState.UNKNOWN
            if rule_id in {"LX0609-04-02-03", "LX0609-04-02-04", "LX0609-05-01-01"}
            else ApplicabilityState.APPLICABLE
        ),
        evidence_state=EvidenceState.DATA_GAP,
        qc_direction=QcDirection.UNKNOWN,
        reason_code=(
            "source_readiness_unproven"
            if rule_id == "LX0609-11-01-01"
            else "applicability_source_gap"
            if rule_id in {"LX0609-04-02-03", "LX0609-04-02-04", "LX0609-05-01-01"}
            else "required_field_missing"
        ),
    )


def _typed_source_rows(
    *,
    source_key: str,
    snapshot: Luxian0609EvidenceSnapshot,
    materials: Luxian0609EvidenceMaterialStore,
) -> tuple[str, tuple[Mapping[str, Any], ...]]:
    observations = tuple(
        item for item in snapshot.observations if item.source_key == source_key
    )
    if len(observations) != 1:
        return "missing", ()
    observation = observations[0]
    if observation.query_state.value == "error":
        return "error", ()
    if observation.query_state.value == "unavailable":
        return "unavailable", ()
    if observation.completeness.value == "truncated":
        return "truncated", ()
    try:
        rows = tuple(materials.rows(source_key))
    except EvidenceMaterialTruncated:
        return "truncated", ()
    except EvidenceMaterialUnavailable:
        return "missing", ()
    return ("empty" if not rows else "available"), rows


def _surgery_text_outcome(
    *,
    rule_id: str,
    facts: Sequence[SurgeryEventFact],
    projection: SurgeryTextProjection,
    materials: Luxian0609EvidenceMaterialStore | None = None,
    snapshot: Luxian0609EvidenceSnapshot | None = None,
) -> _SurgeryTextOutcome:
    """LLM 只抽取事实；规则状态、边界和多事件优先级由 Python 合成。"""

    event_states: list[str] = []
    missing_implant_fields: set[str] = set()
    identified_implants: list[str] = []
    implant_source_document_id = ""
    implant_failure_source_document_id = ""
    implant_event_details: list[dict[str, Any]] = []
    missing_consent_signatures: set[str] = set()
    lymph_node_checked_sources: tuple[str, ...] = ()
    prophylaxis_display_facts: Mapping[str, Any] | None = None
    selected_projection_refs = tuple(
        dict.fromkeys(
            evidence_ref
            for fact in facts
            for evidence_ref in fact.evidence_refs
            if projection.document_source_keys.get(evidence_ref)
            in (
                _TYPED_TEXT_SOURCES[rule_id]
                if rule_id == "LX0609-11-01-01"
                else _TYPED_TEXT_PROJECTION_SOURCES[rule_id]
            )
        )
    )
    selected_document_refs = (
        _projection_material_document_refs(
            projection=projection,
            projection_refs=selected_projection_refs,
            materials=materials,
            snapshot=snapshot,
        )
        if materials is not None and snapshot is not None
        else selected_projection_refs
    )
    for fact in facts:
        if rule_id == "LX0609-04-02-03":
            if fact.surgery_occurrence == "planned":
                event_states.append("not_applicable")
            elif fact.surgery_occurrence != "performed":
                event_states.append("data_gap")
            elif fact.malignant_relation == "explicit_nonqualifying":
                event_states.append("not_applicable")
            elif fact.malignant_relation == "unknown":
                event_states.append("data_gap")
            elif fact.lymph_node_documentation == "documented":
                event_states.append("compliant")
            elif fact.lymph_node_documentation == "not_documented":
                event_states.append("non_compliant")
                lymph_node_checked_sources = tuple(
                    dict.fromkeys(
                        source_key
                        for evidence_ref in fact.evidence_refs
                        if (
                            source_key := projection.document_source_keys.get(evidence_ref)
                        )
                        in {
                            "surgery_record",
                            "pathology_exam_master",
                            "pathology_exam_report",
                        }
                    )
                )
            else:
                event_states.append("data_gap")
        elif rule_id == "LX0609-04-02-04":
            # 只有文书明确“本次未植入”才可判不适用。泛耗材、拟植入、
            # 取出旧物与沉默均不能被偷换成“未植入”。
            # 025 的事实结论只能针对模型同时确认的“已实施本次手术”。手术
            # 发生事实不清时，不能把一段文书的沉默写成“未使用植入物”。
            surgery_evidence_refs = tuple(
                evidence_ref
                for evidence_ref in fact.evidence_refs
                if projection.document_source_keys.get(evidence_ref) == "surgery_record"
            )
            # 没有引用本次投影中的正式手术记录时，模型即使返回present或
            # missing也不能形成C/NC/NA；病程只能辅助确认使用事实。
            if len(surgery_evidence_refs) != 1:
                event_states.append("data_gap")
            elif fact.surgery_occurrence != "performed":
                event_states.append("data_gap")
            elif fact.implant_use == "explicit_no_implant":
                event_states.append("not_applicable")
            elif fact.implant_use != "actual_permanent_implant":
                event_states.append("data_gap")
            else:
                event_implant_names: list[str] = []
                for implant_name, use_kind, evidence_ref in fact.implant_items:
                    if use_kind != "permanent_implant":
                        continue
                    if implant_name not in event_implant_names:
                        event_implant_names.append(implant_name)
                    if implant_name not in identified_implants:
                        identified_implants.append(implant_name)
                required_field_states = tuple(
                    (field_name, getattr(fact, field_name))
                    for field_name in LX0609_025_REQUIRED_FIELDS
                )
                event_missing_fields = tuple(
                    field_name
                    for field_name, field_state in required_field_states
                    if field_state == "missing"
                )
                missing_implant_fields.update(event_missing_fields)
                current_surgery_document_id = ""
                for evidence_ref in surgery_evidence_refs:
                    candidate = _clean(projection.document_source_ids.get(evidence_ref))
                    if candidate:
                        current_surgery_document_id = candidate
                        break
                if not implant_source_document_id and current_surgery_document_id:
                    implant_source_document_id = current_surgery_document_id
                event_has_missing_field = bool(event_missing_fields)
                if (
                    event_has_missing_field
                    and not implant_failure_source_document_id
                    and current_surgery_document_id
                ):
                    implant_failure_source_document_id = current_surgery_document_id
                if event_has_missing_field:
                    implant_event_detail: dict[str, Any] = {
                        "event_ref": fact.event_ref,
                        "missing_fields": list(event_missing_fields),
                        "implant_names": event_implant_names,
                    }
                    if current_surgery_document_id:
                        implant_event_detail["source_document_id"] = (
                            current_surgery_document_id
                        )
                    implant_event_details.append(implant_event_detail)
                    event_states.append("non_compliant")
                elif any(field_state == "unknown" for _, field_state in required_field_states):
                    event_states.append("data_gap")
                else:
                    event_states.append("compliant")
        elif rule_id == "LX0609-05-01-01":
            if fact.surgery_occurrence == "planned":
                event_states.append("not_applicable")
            elif fact.surgery_occurrence != "performed":
                event_states.append("data_gap")
            elif fact.incision_class == "other":
                event_states.append("not_applicable")
            elif fact.incision_class == "unknown":
                event_states.append("data_gap")
            elif fact.antimicrobial_intent in {"therapeutic", "explicit_none"}:
                event_states.append("not_applicable")
            elif fact.antimicrobial_intent not in {"prophylactic", "both"}:
                event_states.append("data_gap")
            elif (
                fact.start_time_role != "actual_administration"
                or fact.end_time_role != "actual_stop"
                or not fact.start_time_ref
                or not fact.end_time_ref
            ):
                event_states.append("data_gap")
            else:
                start = projection.time_candidates.get(fact.start_time_ref)
                end = projection.time_candidates.get(fact.end_time_ref)
                actual_text_sources = {
                    "surgery_record", "inpat_drug_order", "daily_course_record"
                }
                candidates_are_attested = (
                    start is not None
                    and end is not None
                    and fact.start_time_ref != fact.end_time_ref
                    and start.document_ref in fact.evidence_refs
                    and end.document_ref in fact.evidence_refs
                    and start.source_key in actual_text_sources
                    and end.source_key in actual_text_sources
                    and start.field_role == "text_datetime_candidate"
                    and end.field_role == "text_datetime_candidate"
                    and start.precision in {"minute", "second"}
                    and end.precision in {"minute", "second"}
                    and fact.interval_scope == "prophylactic_segment"
                )
                if (
                    not candidates_are_attested
                    or start is None
                    or end is None
                    or end.value < start.value
                ):
                    event_states.append("data_gap")
                else:
                    duration = end.value - start.value
                    if duration <= timedelta(hours=24):
                        event_states.append("compliant")
                    elif duration <= timedelta(hours=48):
                        if fact.special_extension_reason == "documented":
                            event_states.append("compliant")
                        elif fact.special_extension_reason == "unknown":
                            event_states.append("data_gap")
                        else:
                            event_states.append("non_compliant_extension_missing")
                            prophylaxis_display_facts = {
                                "failure_kind": "prophylaxis_extension_reason_missing",
                                "incision_class": fact.incision_class,
                                "start_time": start.value.strftime("%Y-%m-%d %H:%M:%S"),
                                "end_time": end.value.strftime("%Y-%m-%d %H:%M:%S"),
                                "duration_hours": round(
                                    duration.total_seconds() / 3600, 2
                                ),
                                "threshold_hours": 24,
                            }
                    else:
                        event_states.append("non_compliant_over_48h")
                        prophylaxis_display_facts = {
                            "failure_kind": "prophylaxis_duration_over_48h",
                            "incision_class": fact.incision_class,
                            "start_time": start.value.strftime("%Y-%m-%d %H:%M:%S"),
                            "end_time": end.value.strftime("%Y-%m-%d %H:%M:%S"),
                            "duration_hours": round(
                                duration.total_seconds() / 3600, 2
                            ),
                            "threshold_hours": 48,
                        }
        elif rule_id == "LX0609-11-01-01":
            if (
                fact.consent_role != "surgery_informed_consent"
                or fact.consent_linkage != "current_surgery"
            ):
                event_states.append("data_gap")
            elif "missing" in {fact.patient_signature, fact.surgeon_signature}:
                if fact.patient_signature == "missing":
                    missing_consent_signatures.add("patient")
                if fact.surgeon_signature == "missing":
                    missing_consent_signatures.add("surgeon")
                event_states.append("non_compliant")
            elif "unknown" in {fact.patient_signature, fact.surgeon_signature}:
                event_states.append("data_gap")
            else:
                event_states.append("compliant")
        else:
            raise ValueError("unsupported surgery text outcome rule")

    if not event_states:
        return _SurgeryTextOutcome(rule_id, "data_gap", "surgery_fact_scope_missing")
    if rule_id == "LX0609-04-02-03" and "non_compliant" in event_states:
        return _SurgeryTextOutcome(
            rule_id,
            "non_compliant",
            "lymph_node_dissection_not_documented",
            {
                "failure_kind": "lymph_node_dissection_not_documented",
                "performed_surgery_confirmed": True,
                "malignant_surgery_confirmed": True,
                "checked_sources": list(lymph_node_checked_sources),
            },
            selected_document_refs,
        )
    if "non_compliant_over_48h" in event_states:
        return _SurgeryTextOutcome(
            rule_id,
            "non_compliant",
            "prophylaxis_over_48h",
            prophylaxis_display_facts,
            selected_document_refs,
        )
    if "non_compliant_extension_missing" in event_states:
        return _SurgeryTextOutcome(
            rule_id,
            "non_compliant",
            "extension_reason_missing",
            prophylaxis_display_facts,
            selected_document_refs,
        )
    # 025 尚未完成真实病例金标验收，必须保守失败关闭。多手术中只要
    # 任一事件无法唯一绑定一份正式手术记录或字段事实仍未知，整体即DG；
    # 不能用另一已确认事件的缺项覆盖未知事件并交付确定问题。
    if rule_id == "LX0609-04-02-04" and "data_gap" in event_states:
        return _SurgeryTextOutcome(
            rule_id,
            "data_gap",
            "surgery_text_fact_unknown",
            selected_document_refs=selected_document_refs,
        )
    for state, reason in (
        ("non_compliant", "surgery_text_fact_defect"),
        ("data_gap", "surgery_text_fact_unknown"),
        ("compliant", "surgery_text_fact_satisfied"),
        ("not_applicable", "surgery_text_fact_absent"),
    ):
        if state in event_states:
            display_facts = (
                {
                    "failure_kind": "implant_information_incomplete",
                    "performed_surgery_confirmed": True,
                    "missing_fields": [
                        field_name
                        for field_name in LX0609_025_REQUIRED_FIELDS
                        if field_name in missing_implant_fields
                    ],
                    "implant_event_details": list(implant_event_details),
                    **(
                        {"identified_implants": list(identified_implants)}
                        if identified_implants
                        else {}
                    ),
                    "source_label": "手术记录",
                    "source_document_type": "surgery_record",
                    **(
                        {
                            "source_document_id": (
                                implant_failure_source_document_id
                                or implant_source_document_id
                            )
                        }
                        if implant_failure_source_document_id or implant_source_document_id
                        else {}
                    ),
                }
                if rule_id == "LX0609-04-02-04"
                and state == "non_compliant"
                and missing_implant_fields
                else None
            )
            if rule_id == "LX0609-04-02-04" and state == "compliant":
                display_facts = {
                    "verification_kind": "implant_information_complete",
                    "performed_surgery_confirmed": True,
                    "checked_fields": list(LX0609_025_REQUIRED_FIELDS),
                    **(
                        {"identified_implants": list(identified_implants)}
                        if identified_implants
                        else {}
                    ),
                    "source_label": "手术记录",
                    "source_document_type": "surgery_record",
                    **(
                        {"source_document_id": implant_source_document_id}
                        if implant_source_document_id
                        else {}
                    ),
                }
            if rule_id == "LX0609-04-02-04" and state == "not_applicable":
                display_facts = {
                    "verification_kind": "implant_not_used",
                    "performed_surgery_confirmed": True,
                    "source_label": "手术记录",
                }
            if rule_id == "LX0609-11-01-01" and state == "non_compliant":
                display_facts = {
                    "failure_kind": "surgery_consent_signature_missing",
                    "consent_state": "signature_missing",
                    "performed_surgery_confirmed": True,
                    "missing_signature_roles": sorted(missing_consent_signatures),
                }
            if rule_id == "LX0609-11-01-01" and state == "compliant":
                display_facts = {
                    "verification_kind": "surgery_consent_complete",
                    "performed_surgery_confirmed": True,
                    "checked_signature_roles": ["patient", "surgeon"],
                }
            return _SurgeryTextOutcome(
                rule_id,
                state,
                reason,
                customer_display_facts=display_facts,
                selected_document_refs=selected_document_refs,
            )
    raise ValueError("unsupported surgery text outcome")


def _decision_from_surgery_outcome(
    *,
    outcome: _SurgeryTextOutcome,
    snapshot: Luxian0609EvidenceSnapshot,
) -> RuleDecision:
    technical_reason_code = {
        "source_query_error": "source_query_error",
        "surgery_llm_invalid_output": "model_invalid_output",
        "surgery_llm_failure": "model_transport_error",
    }.get(outcome.reason_code, "model_transport_error")
    mapping = {
        "compliant": (
            ApplicabilityState.APPLICABLE, EvidenceState.SUFFICIENT,
            QcDirection.SATISFIED, "requirement_satisfied",
        ),
        "non_compliant": (
            ApplicabilityState.APPLICABLE, EvidenceState.SUFFICIENT,
            QcDirection.DEFECT, "requirement_violated",
        ),
        "not_applicable": (
            ApplicabilityState.NOT_APPLICABLE, EvidenceState.SUFFICIENT,
            QcDirection.UNKNOWN, "trigger_absent_complete",
        ),
        "data_gap": (
            ApplicabilityState.UNKNOWN, EvidenceState.DATA_GAP,
            QcDirection.UNKNOWN, "required_field_missing",
        ),
        "technical_error": (
            ApplicabilityState.ERROR, EvidenceState.TECHNICAL_ERROR,
            QcDirection.UNKNOWN, technical_reason_code,
        ),
    }
    applicability, evidence_state, qc_direction, reason_code = mapping[outcome.status]
    source_keys = _TYPED_TEXT_SOURCES[outcome.rule_id]
    # 逐行文书引用是客户坐标的唯一输入；来源 snapshot ref 仅保留给 Binding
    # 验证无正文/空来源的合法结论，公共 projector 不会把它投影成文书。
    selected_document_refs = outcome.selected_document_refs
    refs = tuple(dict.fromkeys((
        *selected_document_refs,
        *(
            item.snapshot_ref.removeprefix("sha256:")
            for item in snapshot.observations
            if item.source_key in source_keys
        ),
    )))
    return RuleDecision(
        rule_id=outcome.rule_id,
        snapshot_hash=snapshot.snapshot_hash,
        applicability=applicability,
        evidence_state=evidence_state,
        qc_direction=qc_direction,
        reason_code=reason_code,
        fact_refs=refs,
        evaluator_version="surgery-text-fact-ruledecision-v1",
        confidence=None,
    )


def _resolve_performed_state(
    *,
    facts: Sequence[Mapping[str, Any]],
    institute_id: str,
    patient_id: str,
    visit_id: str,
    source_schema: str | None,
    evidence_snapshot: Luxian0609EvidenceSnapshot | None = None,
) -> str:
    state = _fact_state(facts, "current_visit_surgery_confirmed")
    if state != "unknown":
        return state
    if evidence_snapshot is not None:
        return _snapshot_performed_surgery_state(evidence_snapshot)
    if not all((institute_id, patient_id, visit_id)):
        return state
    try:
        rows = read_luxian_0609_runtime_source_rows(
            source_key="surgery_record",
            institute_id=institute_id,
            patient_id=patient_id,
            visit_id=visit_id,
            source_schema=source_schema,
        )
    except Exception:
        return "unknown"
    if any(has_strict_performed_time(row) for row in rows):
        return "present"
    return "negative" if not rows else "unknown"


def _snapshot_performed_surgery_state(
    snapshot: Luxian0609EvidenceSnapshot,
) -> str:
    applicability = resolve_surgery_applicability(snapshot=snapshot)
    if applicability.state == "applicable":
        return "present"
    if applicability.state == "not_applicable":
        return "negative"
    return "unknown"


def _snapshot_surgery_consent_readiness(
    snapshot: Luxian0609EvidenceSnapshot,
) -> str:
    """只接受同一快照显式证明的033来源完整性，缺失证明一律保守。"""

    facts = tuple(
        item
        for item in snapshot.facts
        if item.source_key == "surgery_inform_consent"
        and item.fact_type == "current_visit_surgery_consent_source_readiness"
    )
    if len(facts) != 1:
        return "unproven"
    fact = facts[0]
    value = fact.normalized_value
    if (
        isinstance(value, Mapping)
        and value.get("complete") is True
        and fact.assertion.value == "affirmed"
    ):
        return "complete"
    return "unproven"


def _snapshot_source_failed(
    snapshot: Luxian0609EvidenceSnapshot,
    source_key: str,
) -> bool:
    observation = next(
        (item for item in snapshot.observations if item.source_key == source_key),
        None,
    )
    return bool(
        observation is None
        or observation.query_state.value in {"unavailable", "error"}
    )


def _terminal_status(
    rule_id: str,
    *,
    facts: Sequence[Mapping[str, Any]],
    performed_state: str,
    documents: Mapping[str, Any],
    institute_id: str,
    patient_id: str,
    visit_id: str,
    source_schema: str | None,
    evidence_snapshot: Luxian0609EvidenceSnapshot | None = None,
) -> tuple[str, str] | None:
    if performed_state == "negative":
        return "not_applicable", "performed_surgery_explicitly_absent"
    if performed_state != "present":
        return "data_gap", "performed_surgery_fact_unavailable"

    if rule_id == "LX0609-04-02-03":
        state = _fact_state(facts, "current_visit_malignant_surgery_confirmed")
        if state == "negative":
            return "not_applicable", "malignant_surgery_explicitly_absent"
        if state != "present":
            return "data_gap", "malignant_surgery_fact_unavailable"
    elif rule_id == "LX0609-04-02-04":
        state = _fact_state(facts, "current_visit_surgical_implant_used")
        if state == "negative":
            return "not_applicable", "implant_explicitly_absent"
        if state != "present":
            return "data_gap", "implant_use_fact_unavailable"
    elif rule_id == "LX0609-05-01-01":
        incision = _fact_value(facts, "current_visit_surgical_incision_class")
        if incision and incision not in {"I", "II", "Ⅰ", "Ⅱ"}:
            return "not_applicable", "incision_class_outside_scope"
        if incision not in {"I", "II", "Ⅰ", "Ⅱ"}:
            return "data_gap", "incision_class_unavailable"
        if _fact_state(facts, "current_visit_prophylactic_antimicrobial") != "present":
            return "data_gap", "prophylaxis_fact_unavailable"
        if (
            _fact_state(facts, "current_visit_prophylactic_antimicrobial_interval")
            != "present"
        ):
            return "data_gap", "actual_interval_unavailable"
    elif rule_id == "LX0609-04-02-01":
        rows = _source_rows(documents, "surgery_record") + _source_rows(
            documents, "anesthesia_record"
        )
        if (
            not _has_exact_time(rows)
            and evidence_snapshot is None
            and institute_id
            and patient_id
            and visit_id
        ):
            try:
                rows = tuple(
                    read_luxian_0609_native_source_rows(
                        source_key="mr_surgery",
                        institute_id=institute_id,
                        patient_id=patient_id,
                        visit_id=visit_id,
                        source_schema=source_schema,
                    )
                )
            except Exception:
                return "data_gap", "surgery_time_source_error"
        if not _has_exact_time(rows):
            if evidence_snapshot is not None and _snapshot_source_failed(
                evidence_snapshot, "mr_surgery"
            ):
                return "data_gap", "surgery_time_source_error"
            return "data_gap", "surgery_time_unavailable"
    elif rule_id == "LX0609-04-02-05":
        if not _has_signature(_source_rows(documents, "surgery_record")):
            return "data_gap", "surgery_signature_source_unavailable"
    elif rule_id == "LX0609-11-01-01":
        readiness = _fact_state(facts, "current_visit_surgery_consent_source_readiness")
        if readiness != "present":
            return "data_gap", "surgery_consent_source_unproven"
        if not (
            _source_rows(documents, "surgery_inform_consent")
            or _source_rows(documents, "consent_form")
        ):
            return "data_gap", "surgery_consent_document_unavailable"
    return None


async def execute_luxian_0609_native_surgery_gate_rules(
    *,
    rule_ids: Sequence[str],
    wrapper_rules: Sequence[Mapping[str, Any]],
    evidence_payload: Mapping[str, Any] | None,
    institute_id: str,
    patient_id: str,
    visit_id: str,
    source_schema: str | None,
    llm_client: SurgeryGateLLMClient | None,
    evidence_snapshot: Luxian0609EvidenceSnapshot | None = None,
    evidence_materials: Luxian0609EvidenceMaterialStore | None = None,
    decision_rule_ids: Sequence[str] = (),
    malignancy_resolver: MalignancyFactResolver | None = None,
) -> NativeSurgeryGateExecutionResult:
    requested = {str(rule_id or "").strip().upper() for rule_id in rule_ids}
    selected = tuple(
        rule_id for rule_id in SURGERY_GATE_RULE_IDS if rule_id in requested
    )
    if not selected:
        return NativeSurgeryGateExecutionResult((), ())

    typed_requested = {
        str(rule_id or "").strip().upper() for rule_id in decision_rule_ids
    }
    if not typed_requested.issubset(_TYPED_DECISION_RULE_IDS) or not typed_requested.issubset(
        set(selected)
    ):
        raise ValueError("unsupported typed surgery gate rule scope")
    if typed_requested and (
        type(evidence_snapshot) is not Luxian0609EvidenceSnapshot
        or type(evidence_materials) is not Luxian0609EvidenceMaterialStore
        or evidence_materials.snapshot_hash != evidence_snapshot.snapshot_hash
    ):
        raise ValueError("typed surgery gate requires one evidence session")
    decisions: list[RuleDecision] = []
    customer_display_facts: list[tuple[str, Mapping[str, Any]]] = []
    llm_call_count = prompt_tokens = completion_tokens = total_tokens = 0
    api_time = 0.0
    typed_text_rule_ids: list[str] = []
    for rule_id in selected:
        if rule_id not in typed_requested:
            continue
        if rule_id == "LX0609-04-02-01":
            decisions.append(
                _typed_003_decision(
                    snapshot=evidence_snapshot,
                    materials=evidence_materials,
                    customer_display_facts=customer_display_facts,
                )
            )
            continue
        provisional = _typed_conservative_surgery_gate_decision(
            rule_id=rule_id,
            snapshot=evidence_snapshot,
            materials=evidence_materials,
            customer_display_facts=customer_display_facts,
        )
        performed_state = _snapshot_performed_surgery_state(evidence_snapshot)
        surgery_record_available = any(
            item.source_key == "surgery_record"
            and item.query_state.value == "available"
            and item.completeness.value != "truncated"
            for item in evidence_snapshot.observations
        )
        if (
            rule_id in _TEXT_FACT_RULE_IDS
            and (
                performed_state == "present"
                # 024 需要判断“本次实施手术”与恶性原发治疗的语义关联，不能
                # 误用 029/030 的严格 +08 文本时间合同。受控 surgery_record
                # 可用且未截断时，允许一次裁剪事实抽取；无材料仍保守收口。
                or (rule_id == "LX0609-04-02-03" and surgery_record_available)
                # 025 的实际手术事实可由同一份受控手术记录正文抽取；若快照
                # 因严格时间/字段缺失未形成 performed 事实，也不能提前跳过
                # “明确未植入 / 已植入且字段缺失”的既有三分支。
                or (rule_id == "LX0609-04-02-04" and surgery_record_available)
                or (
                    rule_id == "LX0609-05-01-01"
                    and performed_state == "unknown"
                    and surgery_record_available
                )
            )
        ):
            typed_text_rule_ids.append(rule_id)
        else:
            decisions.append(provisional)

    if typed_text_rule_ids:
        source_keys = tuple(dict.fromkeys(
            source_key
            for rule_id in typed_text_rule_ids
            for source_key in _TYPED_TEXT_SOURCES[rule_id]
        ))
        rows_by_source: dict[str, tuple[Mapping[str, Any], ...]] = {}
        source_states: dict[str, str] = {}
        for source_key in source_keys:
            state, rows = _typed_source_rows(
                source_key=source_key,
                snapshot=evidence_snapshot,
                materials=evidence_materials,
            )
            source_states[source_key] = state
            rows_by_source[source_key] = rows

        active_rule_ids: list[str] = []
        partial_source_rule_ids: set[str] = set()
        pending_outcomes: dict[str, _SurgeryTextOutcome] = {}
        for rule_id in typed_text_rule_ids:
            states_by_source = {
                key: source_states[key] for key in _TYPED_TEXT_SOURCES[rule_id]
            }
            states = set(states_by_source.values())
            if rule_id == "LX0609-04-02-03" and malignancy_resolver is not None:
                visit_stage = resolve_malignancy_visit_stage(
                    horizon_state=states_by_source[
                        "inpat_registration.discharge_horizon"
                    ],
                    horizon_rows=rows_by_source[
                        "inpat_registration.discharge_horizon"
                    ],
                    discharge_record_state=states_by_source["discharge_record"],
                )
                if visit_stage == "technical_error":
                    decisions.append(
                        _decision_from_surgery_outcome(
                            outcome=_SurgeryTextOutcome(
                                rule_id, "technical_error", "source_query_error"
                            ),
                            snapshot=evidence_snapshot,
                        )
                    )
                    continue
                if visit_stage == "unknown":
                    decisions.append(
                        _decision_from_surgery_outcome(
                            outcome=_SurgeryTextOutcome(
                                rule_id, "data_gap", "discharge_stage_unavailable"
                            ),
                            snapshot=evidence_snapshot,
                        )
                    )
                    continue
                malignancy = await malignancy_resolver.resolve(
                    build_stage_malignancy_sources(
                        visit_stage=visit_stage,
                        admission_state=states_by_source[
                            "admission_record_diagnosis"
                        ],
                        admission_rows=rows_by_source[
                            "admission_record_diagnosis"
                        ],
                        diagnosis_state=states_by_source["diagnosis"],
                        diagnosis_rows=rows_by_source["diagnosis"],
                        discharge_diagnosis_state=states_by_source[
                            "discharge_record_diagnosis"
                        ],
                        discharge_diagnosis_rows=rows_by_source[
                            "discharge_record_diagnosis"
                        ],
                        pathology_state=states_by_source["pathology_exam_report"],
                        pathology_rows=rows_by_source["pathology_exam_report"],
                    )
                )
                malignancy_usage = malignancy_resolver.claim_usage(malignancy)
                llm_call_count += malignancy_usage.llm_call_count
                prompt_tokens += malignancy_usage.prompt_tokens
                completion_tokens += malignancy_usage.completion_tokens
                total_tokens += malignancy_usage.total_tokens
                api_time += malignancy_usage.api_time
                if malignancy.state != "confirmed":
                    pending_outcomes[rule_id] = _SurgeryTextOutcome(
                        rule_id,
                        "technical_error"
                        if malignancy.state == "technical_error"
                        else "not_applicable"
                        if malignancy.state == "absent"
                        else "data_gap",
                        malignancy.reason_code,
                    )
                    continue
                # 阶段诊断替代源已由共享Resolver严格判定；后续手术资料门不能
                # 再因未采用的另一阶段诊断为空或不可用而把确定事实降级。
                states = {
                    states_by_source[source_key]
                    for source_key in (
                        "surgery_record",
                        "mr_surgery",
                        "pathology_exam_master",
                        "pathology_exam_report",
                    )
                }
            deterministic_outcome = (
                _deterministic_024_outcome(
                    surgery_rows=rows_by_source["surgery_record"],
                    materials=evidence_materials,
                    snapshot=evidence_snapshot,
                )
                if rule_id == "LX0609-04-02-03"
                and states_by_source.get("surgery_record") == "available"
                else None
            )
            structured_not_applicable = (
                (
                    rule_id == "LX0609-04-02-03"
                    and states_by_source.get("diagnosis") == "available"
                    and _structured_nonmalignant_diagnoses(
                        rows_by_source["diagnosis"]
                    )
                )
                or (
                    rule_id == "LX0609-05-01-01"
                    and states_by_source.get("surgery_record") == "empty"
                    and states_by_source.get("mr_surgery") == "available"
                    and _structured_028_not_applicable(
                        surgery_rows=rows_by_source["surgery_record"],
                        mr_surgery_rows=rows_by_source["mr_surgery"],
                    )
                )
            )
            if rule_id == "LX0609-04-02-04":
                # 025 的五项必填字段只能由正式手术记录核对。病程可辅助证明
                # 实际使用永久植入物，但手术记录不可读时不能替代其字段。
                surgery_state = states_by_source.get("surgery_record")
                if surgery_state == "error":
                    pending_outcomes[rule_id] = _SurgeryTextOutcome(
                        rule_id, "technical_error", "source_query_error"
                    )
                elif surgery_state != "available":
                    pending_outcomes[rule_id] = _SurgeryTextOutcome(
                        rule_id, "data_gap", "surgery_projection_unavailable"
                    )
                else:
                    active_rule_ids.append(rule_id)
                continue
            if "error" in states:
                source_labels = [
                    _TYPED_SOURCE_CUSTOMER_LABELS[source_key]
                    for source_key, state in states_by_source.items()
                    if state == "error"
                    and source_key in _TYPED_SOURCE_CUSTOMER_LABELS
                ]
                pending_outcomes[rule_id] = _SurgeryTextOutcome(
                    rule_id,
                    "technical_error",
                    "source_query_error",
                    {
                        "failure_kind": "source_query_error",
                        "source_labels": source_labels,
                        "performed_surgery_confirmed": True,
                    }
                    if rule_id == "LX0609-11-01-01"
                    else None,
                )
            elif structured_not_applicable:
                pending_outcomes[rule_id] = _SurgeryTextOutcome(
                    rule_id, "not_applicable", "surgery_text_fact_absent"
                )
            elif deterministic_outcome is not None:
                pending_outcomes[rule_id] = deterministic_outcome
            elif rule_id == "LX0609-11-01-01":
                consent_state = states_by_source.get("surgery_inform_consent")
                consent_rows = rows_by_source["surgery_inform_consent"]
                surgery_trigger_document_refs = tuple(
                    ref
                    for row in rows_by_source["surgery_record"]
                    if (
                        ref := _material_document_ref_for_row(
                            materials=evidence_materials,
                            snapshot=evidence_snapshot,
                            source_key="surgery_record",
                            selected_row=row,
                        )
                    )
                )
                consent_document_refs = tuple(
                    ref
                    for row in consent_rows
                    if (
                        ref := _material_document_ref_for_row(
                            materials=evidence_materials,
                            snapshot=evidence_snapshot,
                            source_key="surgery_inform_consent",
                            selected_row=row,
                        )
                    )
                )
                consent_observation = next(
                    (
                        item
                        for item in evidence_snapshot.observations
                        if item.source_key == "surgery_inform_consent"
                    ),
                    None,
                )
                # 033 的来源查询已经由同一 Evidence Session 的 limit+1 快照绑定。
                # 有正文时，不能因为另一份同步完整性说明缺失而跳过该文书；
                # 空结果才在该受控、完整查询下表示“无同意书”。
                if (
                    consent_state == "empty"
                    and consent_observation is not None
                    and consent_observation.completeness.value == "complete"
                ):
                    if _snapshot_surgery_consent_readiness(evidence_snapshot) != "complete":
                        pending_outcomes[rule_id] = _SurgeryTextOutcome(
                            rule_id,
                            "data_gap",
                            "surgery_consent_source_unproven",
                            {
                                "failure_kind": "surgery_consent_source_unproven",
                                "consent_state": "source_unproven",
                                "performed_surgery_confirmed": True,
                            },
                        )
                    else:
                        trigger_refs = _source_document_refs(
                            rows_by_source["surgery_record"],
                            source_type="surgery_record",
                        )
                        pending_outcomes[rule_id] = _SurgeryTextOutcome(
                            rule_id,
                            "non_compliant",
                            "surgery_consent_document_missing",
                            {
                                "failure_kind": "surgery_consent_document_missing",
                                "consent_state": "missing",
                                "performed_surgery_confirmed": True,
                                **(
                                    {"source_document_refs": trigger_refs}
                                    if trigger_refs
                                    else {}
                                ),
                            },
                            selected_document_refs=surgery_trigger_document_refs,
                        )
                elif consent_state != "available":
                    pending_outcomes[rule_id] = _SurgeryTextOutcome(
                        rule_id,
                        "data_gap",
                        "surgery_consent_source_unproven",
                        {
                            "failure_kind": "surgery_consent_source_unproven",
                            "consent_state": "source_unproven",
                            "performed_surgery_confirmed": True,
                        },
                    )
                elif not any(
                    _clean(row.get("record_content") or row.get("content"))
                    for row in consent_rows
                ):
                    # 空壳行不是可供模型判断的同意书正文；完整来源中只有空壳时，
                    # 直接按缺少有效同意书处理，既不扩大上下文也不浪费一次模型调用。
                    pending_outcomes[rule_id] = _SurgeryTextOutcome(
                        rule_id,
                        "non_compliant",
                        "surgery_consent_body_missing",
                        {
                            "failure_kind": "surgery_consent_body_missing",
                            "consent_state": "blank",
                            "performed_surgery_confirmed": True,
                        },
                        selected_document_refs=consent_document_refs,
                    )
                else:
                    # 同一住院可存在多次手术及多份同意书。当前结构化来源
                    # 没有稳定的手术事件键，不能仅凭任意一行双签直接判定。
                    # 保留单次受控语义关联，由 Python 校验 current_surgery 引用。
                    active_rule_ids.append(rule_id)
            elif (
                rule_id == "LX0609-05-01-01"
                and states_by_source.get("inpat_drug_order")
                in {"unavailable", "truncated", "missing"}
                and not any(
                    state in {"unavailable", "truncated", "missing"}
                    for source_key, state in states_by_source.items()
                    if source_key != "inpat_drug_order"
                )
            ):
                partial_source_rule_ids.add(rule_id)
                active_rule_ids.append(rule_id)
            elif states.intersection({"unavailable", "truncated", "missing"}):
                pending_outcomes[rule_id] = _SurgeryTextOutcome(
                    rule_id, "data_gap", "surgery_projection_unavailable"
                )
            else:
                active_rule_ids.append(rule_id)

        if active_rule_ids:
            def projection_sources_for(rule_id: str) -> tuple[str, ...]:
                if rule_id == "LX0609-04-02-04":
                    # 手术记录是五字段唯一事实源；病程若可用，只作为实际使用
                    # 永久植入物的辅助语义证据，与手术记录一并送入一次抽取。
                    # 病程是可选辅助源，数量超出受控上限时不让它挤掉唯一必查
                    # 的手术记录；此时模型只能按手术记录作保守三态判断。
                    sources = ["surgery_record"]
                    if (
                        source_states.get("daily_course_record") == "available"
                        and len(rows_by_source["daily_course_record"])
                        <= _JOINT_TEXT_FACT_MAX_ROWS_PER_SOURCE
                    ):
                        sources.append("daily_course_record")
                    return tuple(sources)
                return _TYPED_TEXT_PROJECTION_SOURCES[rule_id]

            # 先按规则各自来源检查行上限；相关来源过多只能让该规则资料不足，
            # 不能为了合批静默裁剪。
            model_rule_ids: list[str] = []
            for rule_id in active_rule_ids:
                source_keys = projection_sources_for(rule_id)
                if any(
                    len(rows_by_source[source_key])
                    > _JOINT_TEXT_FACT_MAX_ROWS_PER_SOURCE
                    for source_key in source_keys
                ):
                    pending_outcomes[rule_id] = _SurgeryTextOutcome(
                        rule_id, "data_gap", "surgery_projection_truncated"
                    )
                else:
                    model_rule_ids.append(rule_id)

            if model_rule_ids:
                active_sources = tuple(dict.fromkeys(
                    source_key
                    for rule_id in model_rule_ids
                    for source_key in projection_sources_for(rule_id)
                ))
                total_rows = sum(len(rows_by_source[source_key]) for source_key in active_sources)
                if total_rows > _JOINT_TEXT_FACT_MAX_TOTAL_ROWS:
                    for rule_id in model_rule_ids:
                        pending_outcomes[rule_id] = _SurgeryTextOutcome(
                            rule_id, "data_gap", "surgery_projection_truncated"
                        )
                else:
                    try:
                        projection = build_surgery_text_projection(
                            rows_by_source={key: rows_by_source[key] for key in active_sources},
                            max_rows_per_source=_JOINT_TEXT_FACT_MAX_ROWS_PER_SOURCE,
                            max_context_chars=_JOINT_TEXT_FACT_MAX_CONTEXT_CHARS,
                            max_documents=_JOINT_TEXT_FACT_MAX_DOCUMENTS,
                        )
                    except ValueError:
                        projection = None
                    if projection is None or not projection.context:
                        for rule_id in model_rule_ids:
                            pending_outcomes[rule_id] = _SurgeryTextOutcome(
                                rule_id, "data_gap", "surgery_projection_unavailable"
                            )
                    elif llm_client is None:
                        for rule_id in model_rule_ids:
                            pending_outcomes[rule_id] = _SurgeryTextOutcome(
                                rule_id, "technical_error", "surgery_llm_failure"
                            )
                    else:
                        llm_call_count += 1
                        try:
                            response = await llm_client.generate(
                                build_surgery_text_fact_prompt(
                                    selected_rule_ids=tuple(model_rule_ids),
                                    projection=projection,
                                    max_completion_tokens=_JOINT_TEXT_FACT_MAX_COMPLETION_TOKENS,
                                ),
                                max_completion_tokens=_JOINT_TEXT_FACT_MAX_COMPLETION_TOKENS,
                                allow_length_retry=False,
                            )
                        except Exception:
                            response = None
                        if response is None:
                            for rule_id in model_rule_ids:
                                pending_outcomes[rule_id] = _SurgeryTextOutcome(
                                    rule_id, "technical_error", "surgery_llm_failure"
                                )
                        else:
                            prompt, completion, total, elapsed = _usage(response)
                            prompt_tokens += prompt
                            completion_tokens += completion
                            total_tokens += total
                            api_time += elapsed
                            try:
                                text_facts = (
                                    None
                                    if completion > _JOINT_TEXT_FACT_MAX_COMPLETION_TOKENS
                                    else parse_surgery_text_fact_response(
                                        response=response,
                                        projection=projection,
                                        selected_rule_ids=tuple(model_rule_ids),
                                    )
                                )
                            except ValueError:
                                text_facts = None
                            for rule_id in model_rule_ids:
                                outcome = (
                                    _SurgeryTextOutcome(
                                        rule_id, "technical_error", "surgery_llm_invalid_output"
                                    )
                                    if text_facts is None
                                    else _surgery_text_outcome(
                                        rule_id=rule_id,
                                        facts=text_facts,
                                        projection=projection,
                                        materials=evidence_materials,
                                        snapshot=evidence_snapshot,
                                    )
                                )
                                if (
                                    rule_id in partial_source_rule_ids
                                    and (
                                        outcome.status in {"compliant", "not_applicable"}
                                        or (
                                            outcome.status == "non_compliant"
                                            and outcome.reason_code != "prophylaxis_over_48h"
                                        )
                                    )
                                ):
                                    outcome = _SurgeryTextOutcome(
                                        rule_id, "data_gap", "surgery_projection_partial"
                                    )
                                pending_outcomes[rule_id] = outcome
        customer_display_facts.extend(
            (rule_id, outcome.customer_display_facts)
            for rule_id, outcome in pending_outcomes.items()
            if outcome.customer_display_facts is not None
        )
        decisions.extend(
            _decision_from_surgery_outcome(
                outcome=pending_outcomes[rule_id],
                snapshot=evidence_snapshot,
            )
            for rule_id in typed_text_rule_ids
        )
    legacy_selected = tuple(
        rule_id for rule_id in selected if rule_id not in typed_requested
    )
    if not legacy_selected:
        return NativeSurgeryGateExecutionResult(
            results=(),
            planned_rule_ids=selected,
            decisions=tuple(sorted(decisions, key=lambda item: selected.index(item.rule_id))),
            customer_display_facts=tuple(customer_display_facts),
            llm_call_count=llm_call_count,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
            api_time=api_time,
        )

    documents = _documents(evidence_payload)
    if documents is None:
        return NativeSurgeryGateExecutionResult(
            tuple(
                _result(
                    rule_id,
                    "data_gap",
                    "surgery_projection_unavailable",
                    executor_type="program",
                )
                for rule_id in legacy_selected
            ),
            selected,
            decisions,
        )
    facts = _facts(evidence_payload)
    performed_state = _resolve_performed_state(
        facts=facts,
        institute_id=institute_id,
        patient_id=patient_id,
        visit_id=visit_id,
        source_schema=source_schema,
        evidence_snapshot=evidence_snapshot,
    )
    wrappers = {
        str(item.get("rule_id") or item.get("rule_code") or "").strip().upper(): item
        for item in wrapper_rules
        if isinstance(item, Mapping)
    }
    results: list[dict[str, Any]] = []
    for rule_id in legacy_selected:
        terminal = _terminal_status(
            rule_id,
            facts=facts,
            performed_state=performed_state,
            documents=documents,
            institute_id=institute_id,
            patient_id=patient_id,
            visit_id=visit_id,
            source_schema=source_schema,
            evidence_snapshot=evidence_snapshot,
        )
        if terminal:
            status, reason = terminal
            results.append(_result(rule_id, status, reason, executor_type="program"))
            continue
        wrapper = wrappers.get(rule_id)
        context = _context(rule_id, documents)
        if wrapper is None or not context or llm_client is None:
            results.append(
                _result(
                    rule_id,
                    "data_gap",
                    "surgery_prompt_input_unavailable",
                    executor_type="program",
                )
            )
            continue
        llm_call_count += 1
        try:
            response = await llm_client.generate(_prompt(wrapper, context))
        except Exception:
            results.append(
                _result(rule_id, "data_gap", "surgery_llm_failure", executor_type="llm")
            )
            continue
        prompt_count, completion_count, total_count, elapsed = _usage(response)
        prompt_tokens += prompt_count
        completion_tokens += completion_count
        total_tokens += total_count
        api_time += elapsed
        is_compliant = _parse_is_compliant(response)
        if is_compliant is None:
            results.append(
                _result(
                    rule_id,
                    "data_gap",
                    "surgery_llm_invalid_output",
                    executor_type="llm",
                    prompt_tokens=prompt_count,
                    completion_tokens=completion_count,
                    total_tokens=total_count,
                    api_time=elapsed,
                )
            )
            continue
        if rule_id == "LX0609-04-02-04" and not is_compliant:
            missing_fields = _parse_implant_missing_fields(response)
            if not missing_fields:
                # 未明确指出缺项时，不能把通用模型结论包装成确定的植入物缺陷。
                results.append(
                    _result(
                        rule_id,
                        "data_gap",
                        "implant_missing_fields_unavailable",
                        executor_type="llm",
                        prompt_tokens=prompt_count,
                        completion_tokens=completion_count,
                        total_tokens=total_count,
                        api_time=elapsed,
                    )
                )
                continue
            source_document_id = _first_source_document_id(
                documents, "surgery_record"
            )
            results.append(
                _result(
                    rule_id,
                    "non_compliant",
                    "surgery_customer_prompt",
                    executor_type="llm",
                    prompt_tokens=prompt_count,
                    completion_tokens=completion_count,
                    total_tokens=total_count,
                    api_time=elapsed,
                    customer_display_facts={
                        "failure_kind": "implant_information_incomplete",
                        "missing_fields": list(missing_fields),
                        "source_label": "手术记录",
                        **(
                            {"source_document_id": source_document_id}
                            if source_document_id
                            else {}
                        ),
                    },
                )
            )
            continue
        results.append(
            _result(
                rule_id,
                "compliant" if is_compliant else "non_compliant",
                "surgery_customer_prompt",
                executor_type="llm",
                prompt_tokens=prompt_count,
                completion_tokens=completion_count,
                total_tokens=total_count,
                api_time=elapsed,
            )
        )

    return NativeSurgeryGateExecutionResult(
        results=tuple(results),
        planned_rule_ids=selected,
        decisions=tuple(sorted(decisions, key=lambda item: selected.index(item.rule_id))),
        customer_display_facts=tuple(customer_display_facts),
        llm_call_count=llm_call_count,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        total_tokens=total_tokens,
        api_time=api_time,
    )
