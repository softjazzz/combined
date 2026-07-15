"""LX0609 输血族原生执行：专用来源事实门控后逐规则裁剪判定。"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import json
import re
from typing import Any, Mapping, Protocol, Sequence

from .native_execution import build_luxian_0609_native_result
from .source_evidence_reader import read_luxian_0609_native_source_rows


TRANSFUSION_RULE_IDS = tuple(f"LX0609-{number:03d}" for number in range(41, 50))
EXECUTOR_KEY = "transfusion"

_TRIGGER_SOURCES = ("mr_bloodtrans", "bloodtrans_record")
_MAX_ROWS_PER_SOURCE = 8
_MAX_ROW_CHARS = 1400
_MAX_CONTEXT_CHARS = 18000
_MAPPING_LINE_PATTERN = re.compile(r"^.*(?:主执行规则|映射执行规则).*$", re.MULTILINE)

_PRETRANSFUSION_ASSESSMENT_PATTERN = re.compile(r"输血前(?:评估|评价)")
_PRETRANSFUSION_ASSESSMENT_MISSING_PATTERN = re.compile(
    r"(?:未见|未记录|未形成|无|缺少).{0,12}输血前(?:评估|评价)"
    r"|输血前(?:评估|评价).{0,12}(?:缺失|不完整|未记录)"
)
_PRETRANSFUSION_CORE_PATTERNS = (
    re.compile(r"输血指征|适应证|必要性|拟输血原因"),
    re.compile(r"贫血|血红蛋白|\bHb\b|血小板|凝血|失血|出血"),
    re.compile(r"输血风险|既往输血|不良反应|过敏|生命体征|发热"),
)

_RULE_CONTEXT_SOURCES = {
    "LX0609-041": ("bloodtrans_record", "consent_form", "blood_transfusion_consent"),
    "LX0609-042": ("bloodtrans_record", "consent_form", "blood_transfusion_consent"),
    "LX0609-043": (
        "bloodtrans_record",
        "labtest_master",
        "labtest_item_report",
        "exam_master",
        "exam_item_report",
    ),
    "LX0609-044": ("bloodtrans_record", "blood_application", "daily_course_record"),
    "LX0609-045": ("bloodtrans_record", "daily_course_record"),
    "LX0609-046": ("bloodtrans_record", "daily_course_record"),
    "LX0609-047": ("bloodtrans_record", "daily_course_record"),
    "LX0609-048": (
        "bloodtrans_record",
        "surgery_record",
        "anesthesia_record",
        "postsurg_firstcourse_record",
    ),
    "LX0609-049": (
        "bloodtrans_record",
        "inpat_nondrug_order",
        "inpat_bill_item",
        "blood_application",
    ),
}

# 每组至少一个来源有实质内容才允许模型判断；缺少来源能力不能伪装成临床缺项。
_RULE_REQUIRED_SOURCE_GROUPS = {
    "LX0609-041": (("bloodtrans_record",), ("consent_form", "blood_transfusion_consent")),
    "LX0609-042": (("bloodtrans_record",), ("consent_form", "blood_transfusion_consent")),
    "LX0609-043": (
        ("bloodtrans_record",),
        ("labtest_master", "labtest_item_report", "exam_master", "exam_item_report"),
    ),
    "LX0609-044": (("bloodtrans_record",), ("blood_application", "daily_course_record")),
    "LX0609-045": (("bloodtrans_record",), ("daily_course_record",)),
    "LX0609-046": (("bloodtrans_record",), ("daily_course_record",)),
    "LX0609-047": (("bloodtrans_record",), ("daily_course_record",)),
    "LX0609-048": (
        ("bloodtrans_record",),
        ("surgery_record",),
        ("anesthesia_record",),
        ("postsurg_firstcourse_record",),
    ),
    "LX0609-049": (
        ("bloodtrans_record",),
        ("inpat_nondrug_order",),
        ("inpat_bill_item",),
    ),
}

_CONTROLLED_MESSAGES = {
    "compliant": ("输血相关记录满足该项要求。", ""),
    "non_compliant": ("输血相关记录未满足该项要求。", "请按该质控点补充或修正输血相关记录。"),
    "not_applicable": ("当前就诊未发现已实施输血事实，本规则不适用。", ""),
    "data_gap": ("当前输血相关资料不足，暂不能形成可靠结论。", "请补齐输血相关资料后重新质控。"),
}


class TransfusionLLMClient(Protocol):
    async def generate(self, prompt: str) -> dict[str, Any]: ...


@dataclass(frozen=True)
class NativeTransfusionExecutionResult:
    results: tuple[dict[str, Any], ...]
    planned_rule_ids: tuple[str, ...]
    llm_call_count: int = 0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    api_time: float = 0.0


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


def _row_text(row: Mapping[str, Any]) -> str:
    return _clean(
        row.get("content")
        or row.get("record_content")
        or row.get("assembled_text")
        or row.get("raw_text")
        or row.get("content_preview")
        or row.get("text_preview")
    )


def _source_rows(documents: Mapping[str, Any], source_key: str) -> list[str]:
    raw_rows = documents.get(source_key)
    if not isinstance(raw_rows, list):
        return []
    rows: list[str] = []
    for raw_row in raw_rows[:_MAX_ROWS_PER_SOURCE]:
        if not isinstance(raw_row, Mapping):
            continue
        content = _row_text(raw_row)
        if content:
            rows.append(content[:_MAX_ROW_CHARS])
    return rows


def _source_entries(documents: Mapping[str, Any], source_key: str) -> list[str]:
    """为单文书判定保留标题与正文边界，避免跨文书拼接临床事实。"""

    raw_rows = documents.get(source_key)
    if not isinstance(raw_rows, list):
        return []
    entries: list[str] = []
    for raw_row in raw_rows[:_MAX_ROWS_PER_SOURCE]:
        if not isinstance(raw_row, Mapping):
            continue
        title = _clean(raw_row.get("document_title") or raw_row.get("title"))
        content = _row_text(raw_row)
        entry = " ".join(value for value in (title, content) if value).strip()
        if entry:
            entries.append(entry[:_MAX_ROW_CHARS])
    return entries


def _has_required_projection(rule_id: str, documents: Mapping[str, Any]) -> bool:
    return all(
        any(_source_rows(documents, source_key) for source_key in group)
        for group in _RULE_REQUIRED_SOURCE_GROUPS[rule_id]
    )


def _context(rule_id: str, documents: Mapping[str, Any]) -> str:
    parts: list[str] = []
    for source_key in _RULE_CONTEXT_SOURCES[rule_id]:
        for index, content in enumerate(_source_rows(documents, source_key), start=1):
            parts.append(f"[{source_key}-{index}] {content}")
    return "\n".join(parts)[:_MAX_CONTEXT_CHARS]


def _programmatic_044_status(documents: Mapping[str, Any]) -> tuple[str, str] | None:
    """仅收口明确的输血前评估事实；灰区仍交给裁剪模型。"""

    entries = tuple(
        entry
        for source_key in _RULE_CONTEXT_SOURCES["LX0609-044"]
        for entry in _source_entries(documents, source_key)
    )
    if any(_PRETRANSFUSION_ASSESSMENT_MISSING_PATTERN.search(entry) for entry in entries):
        return "non_compliant", "pretransfusion_assessment_missing"

    if any(
        _PRETRANSFUSION_ASSESSMENT_PATTERN.search(entry)
        and all(pattern.search(entry) for pattern in _PRETRANSFUSION_CORE_PATTERNS)
        for entry in entries
    ):
        return "compliant", "pretransfusion_assessment_complete"

    has_marker = any(_PRETRANSFUSION_ASSESSMENT_PATTERN.search(entry) for entry in entries)
    has_indication = any(
        _PRETRANSFUSION_CORE_PATTERNS[0].search(entry) for entry in entries
    )
    has_application = bool(_source_entries(documents, "blood_application"))
    # 输血过程中的生命体征、发热或不良反应不能反向充当“输血前评估”。
    # 没有评估标识且连指征/必要性也未记录时，可确定为缺失；其余灰区仍交给模型。
    if not has_marker and not has_indication and not has_application:
        return "non_compliant", "pretransfusion_assessment_missing"
    return None


def _prompt(wrapper: Mapping[str, Any], *, context: str) -> str:
    custom_prompt = str(wrapper.get("custom_prompt") or "")
    custom_prompt = _MAPPING_LINE_PATTERN.sub("", custom_prompt)
    return (
        custom_prompt.replace("{defect_level}", str(wrapper.get("defect_level") or ""))
        .replace("{medical_text}", context)
        .strip()
    )


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


def _performed_source_state(
    *,
    documents: Mapping[str, Any] | None,
    institute_id: str,
    patient_id: str,
    visit_id: str,
    source_schema: str | None,
) -> str:
    # 正式 bundle 已携带同次就诊专用输血记录时直接采用，避免重复查库；
    # 普通病程/手术文本中的“输血”字样不进入该分支。
    if isinstance(documents, Mapping) and any(
        len(content) >= 16 for content in _source_rows(documents, "bloodtrans_record")
    ):
        return "present"
    if not all((institute_id, patient_id, visit_id)):
        return "data_gap"
    rows_by_source: dict[str, list[dict[str, Any]]] = {}
    failed = False
    for source_key in _TRIGGER_SOURCES:
        try:
            rows_by_source[source_key] = read_luxian_0609_native_source_rows(
                source_key=source_key,
                institute_id=institute_id,
                patient_id=patient_id,
                visit_id=visit_id,
                source_schema=source_schema,
            )
        except Exception:
            rows_by_source[source_key] = []
            failed = True

    structured_performed = any(
        isinstance(row.get("transfution_datetime"), datetime)
        for row in rows_by_source.get("mr_bloodtrans", ())
    )
    dedicated_record_present = any(
        len(_clean(row.get("record_content"))) >= 16
        for row in rows_by_source.get("bloodtrans_record", ())
    )
    if structured_performed or dedicated_record_present:
        return "present"
    if failed or any(rows_by_source.values()):
        return "data_gap"
    return "absent"


async def execute_luxian_0609_native_transfusion_rules(
    *,
    rule_ids: Sequence[str],
    wrapper_rules: Sequence[Mapping[str, Any]],
    evidence_payload: Mapping[str, Any] | None,
    institute_id: str,
    patient_id: str,
    visit_id: str,
    source_schema: str | None,
    llm_client: TransfusionLLMClient | None,
) -> NativeTransfusionExecutionResult:
    """先证明本次存在专用输血来源，再按客户规则逐条裁剪执行。"""

    requested = {str(rule_id or "").strip().upper() for rule_id in rule_ids}
    selected = tuple(rule_id for rule_id in TRANSFUSION_RULE_IDS if rule_id in requested)
    if not selected:
        return NativeTransfusionExecutionResult((), ())

    documents = _documents(evidence_payload)
    source_state = _performed_source_state(
        documents=documents,
        institute_id=str(institute_id or ""),
        patient_id=str(patient_id or ""),
        visit_id=str(visit_id or ""),
        source_schema=source_schema,
    )
    if source_state != "present":
        status = "not_applicable" if source_state == "absent" else "data_gap"
        reason_code = (
            "transfusion_fact_absent"
            if source_state == "absent"
            else "transfusion_source_unavailable"
        )
        return NativeTransfusionExecutionResult(
            results=tuple(
                _result(rule_id, status, reason_code, executor_type="program")
                for rule_id in selected
            ),
            planned_rule_ids=selected,
        )

    if documents is None:
        return NativeTransfusionExecutionResult(
            results=tuple(
                _result(
                    rule_id,
                    "data_gap",
                    "transfusion_projection_unavailable",
                    executor_type="program",
                )
                for rule_id in selected
            ),
            planned_rule_ids=selected,
        )

    wrappers_by_id = {
        str(wrapper.get("rule_id") or wrapper.get("rule_code") or "").strip().upper(): wrapper
        for wrapper in wrapper_rules
        if isinstance(wrapper, Mapping)
    }
    results: list[dict[str, Any]] = []
    llm_call_count = prompt_tokens = completion_tokens = total_tokens = 0
    api_time = 0.0
    for rule_id in selected:
        if not _has_required_projection(rule_id, documents):
            results.append(
                _result(
                    rule_id,
                    "data_gap",
                    "transfusion_rule_projection_incomplete",
                    executor_type="program",
                )
            )
            continue
        if rule_id == "LX0609-044":
            programmatic_status = _programmatic_044_status(documents)
            if programmatic_status is not None:
                status, reason_code = programmatic_status
                results.append(
                    _result(rule_id, status, reason_code, executor_type="program")
                )
                continue
        wrapper = wrappers_by_id.get(rule_id)
        context = _context(rule_id, documents)
        if wrapper is None or not str(wrapper.get("custom_prompt") or "").strip() or not context:
            results.append(
                _result(
                    rule_id,
                    "data_gap",
                    "transfusion_prompt_input_unavailable",
                    executor_type="program",
                )
            )
            continue
        if llm_client is None:
            results.append(
                _result(
                    rule_id,
                    "data_gap",
                    "transfusion_llm_unavailable",
                    executor_type="program",
                )
            )
            continue
        llm_call_count += 1
        try:
            response = await llm_client.generate(_prompt(wrapper, context=context))
        except Exception:
            results.append(
                _result(
                    rule_id,
                    "data_gap",
                    "transfusion_llm_failure",
                    executor_type="llm",
                )
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
                _result(
                    rule_id,
                    "data_gap",
                    "transfusion_llm_invalid_output",
                    executor_type="llm",
                )
            )
            continue
        status = "compliant" if is_compliant else "non_compliant"
        results.append(
            _result(rule_id, status, "transfusion_customer_prompt", executor_type="llm")
        )

    return NativeTransfusionExecutionResult(
        results=tuple(results),
        planned_rule_ids=selected,
        llm_call_count=llm_call_count,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        total_tokens=total_tokens,
        api_time=api_time,
    )
