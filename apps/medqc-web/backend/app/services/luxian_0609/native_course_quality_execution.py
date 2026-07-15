"""LX0609 查房病程族原生执行：强事实门控、裁剪文书与确定性复制检测。"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from difflib import SequenceMatcher
import json
import re
from typing import Any, Mapping, Protocol, Sequence

from .native_execution import build_luxian_0609_native_result
from .source_evidence_reader import (
    has_luxian_0609_current_visit_unstable_order,
    luxian_0609_native_source_row_limit,
    read_luxian_0609_native_source_rows,
)


COURSE_QUALITY_RULE_IDS = (
    "LX0609-007",
    "LX0609-008",
    "LX0609-009",
    "LX0609-016",
    "LX0609-017",
    "LX0609-018",
)
EXECUTOR_KEY = "course_quality"

_COURSE_SOURCES = (
    "first_course_record",
    "daily_course_record",
    "senior_course_record",
    "rescue_record",
)
_RULE_007_RECORD_SOURCES = (
    "daily_course_record",
    "senior_course_record",
)
_ROUND_SOURCES = (
    "daily_course_record",
    "senior_course_record",
    "rescue_record",
    "first_course_record",
)
_TIMELINE_SOURCES = (
    *_COURSE_SOURCES,
    "exam_attention_report",
    "lab_attention_report",
)
_FACT_SOURCE_KEYS = frozenset({"inpat_nondrug_order"})
_SERIOUS_FACT_TYPES = frozenset(
    {
        "current_visit_serious_order",
        "current_visit_serious_condition",
        "current_visit_severe_order",
    }
)
_CRITICAL_FACT_TYPES = frozenset(
    {
        "current_visit_critical_order",
        "current_visit_critical_condition",
    }
)
_COMPLAINT_FACT_TYPES = frozenset({"current_visit_chief_complaint"})
_PRIMARY_DIAGNOSIS_FACT_TYPES = frozenset(
    {"current_visit_primary_diagnosis", "current_visit_first_diagnosis"}
)
_PRESENT_FACT_STATES = frozenset(
    {"present", "active", "ordered", "available", "affirmed"}
)
_ABSENT_FACT_STATES = frozenset(
    {"absent", "not_present", "negative", "inactive", "not_ordered"}
)
_MAX_ROWS_PER_SOURCE = 8
_MAX_ROW_CHARS = 1400
_MAX_CONTEXT_CHARS = 18000
_MIN_COMPARABLE_CHARS = 24
_MIN_FIRST_COURSE_BODY_CHARS = 6
_COPY_SIMILARITY_THRESHOLD = 0.70
_COPY_STRONG_EXACT_THRESHOLD = 0.95
_COPY_STRONG_LONGEST_BLOCK_CHARS = 120
_COPY_STRONG_MATCH_COVERAGE = 0.45
_MAPPING_LINE_PATTERN = re.compile(r"^.*(?:主执行规则|映射执行规则).*$", re.MULTILINE)
_DATE_PATTERN = re.compile(r"\d{4}[-/.年]\d{1,2}[-/.月]\d{1,2}日?")
_TIME_PATTERN = re.compile(r"\d{1,2}:\d{2}(?::\d{2})?")
_COMPLAINT_PATTERN = re.compile(r"主诉\s*[:：]\s*[^；;。]{2,}")
_DIAGNOSIS_PATTERN = re.compile(r"(?:第一诊断|主要诊断|入院诊断|首页第一诊断)\s*[:：]\s*[^；;。]{2,}")

_RULE_CONTEXT_SOURCES = {
    "LX0609-007": _RULE_007_RECORD_SOURCES,
    "LX0609-008": _TIMELINE_SOURCES,
    "LX0609-009": _TIMELINE_SOURCES,
    "LX0609-016": ("admission_record", "first_course_record"),
    "LX0609-018": ("admission_record",),
}

_RULE_007_MAX_INTERVAL = timedelta(hours=72)

_CONTROLLED_MESSAGES = {
    "compliant": ("查房病程相关记录满足该项要求。", ""),
    "non_compliant": (
        "查房病程相关记录未满足该项要求。",
        "请按该质控点补充或修正相关记录。",
    ),
    "not_applicable": ("当前就诊不满足该项查房病程规则的适用条件。", ""),
    "data_gap": (
        "当前查房病程资料不足，暂不能形成可靠结论。",
        "请补齐相关资料后重新质控。",
    ),
}


class CourseQualityLLMClient(Protocol):
    async def generate(self, prompt: str) -> dict[str, Any]:
        ...


@dataclass(frozen=True)
class NativeCourseQualityExecutionResult:
    results: tuple[dict[str, Any], ...]
    planned_rule_ids: tuple[str, ...]
    llm_call_count: int = 0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    api_time: float = 0.0


def _clean(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def _documents(
    evidence_payload: Mapping[str, Any] | None,
) -> Mapping[str, Any] | None:
    if not isinstance(evidence_payload, Mapping):
        return None
    timeline = evidence_payload.get("programmatic_timeline")
    if not isinstance(timeline, Mapping):
        return None
    documents = timeline.get("documents")
    return documents if isinstance(documents, Mapping) else None


def _timeline_facts(
    evidence_payload: Mapping[str, Any] | None,
) -> tuple[Any, ...]:
    if not isinstance(evidence_payload, Mapping):
        return ()
    raw_facts = evidence_payload.get("timeline_facts")
    if not isinstance(raw_facts, list):
        timeline = evidence_payload.get("programmatic_timeline")
        raw_facts = (
            timeline.get("timeline_facts") if isinstance(timeline, Mapping) else None
        )
    return tuple(raw_facts) if isinstance(raw_facts, list) else ()


def _row_text(row: Mapping[str, Any]) -> str:
    return _clean(
        row.get("record_content")
        or row.get("content")
        or row.get("assembled_text")
        or row.get("raw_text")
        or row.get("content_preview")
        or row.get("text_preview")
    )


def _first_course_body_text(row: Mapping[str, Any]) -> str:
    """只返回首次病程实质正文，不把界面预览当作正文。"""

    content = _clean(
        row.get("record_content")
        or row.get("content")
        or row.get("assembled_text")
        or row.get("raw_text")
    )
    if not content:
        return ""
    normalized = re.sub(r"[\W_]+", "", content, flags=re.UNICODE)
    shell_remainder = re.sub(
        r"(?:首次病程记录|首次病程|记录时间|提交时间|文书类型|文书编号|正文|"
        r"sourcetable|firstcourserecord|assemblystatus|partial|"
        r"年|月|日|时|分|秒|\d+)",
        "",
        normalized,
        flags=re.IGNORECASE,
    )
    return content if len(shell_remainder) >= _MIN_FIRST_COURSE_BODY_CHARS else ""


def _admission_body_text(row: Mapping[str, Any]) -> str:
    """只接受入院记录正文承载字段，拒绝标题、时间和预览壳。"""

    content = _clean(
        row.get("record_content")
        or row.get("content")
        or row.get("assembled_text")
        or row.get("raw_text")
    )
    if not content:
        return ""
    normalized = re.sub(r"[\W_]+", "", content, flags=re.UNICODE)
    shell_remainder = re.sub(
        r"(?:入院记录|记录时间|提交时间|文书类型|文书编号|正文|"
        r"sourcetable|admissionrecord|assemblystatus|partial|"
        r"年|月|日|时|分|秒|\d+)",
        "",
        normalized,
        flags=re.IGNORECASE,
    )
    return content if len(shell_remainder) >= _MIN_FIRST_COURSE_BODY_CHARS else ""


def _source_rows(
    documents: Mapping[str, Any],
    source_key: str,
    *,
    limit: int | None = _MAX_ROWS_PER_SOURCE,
) -> tuple[Mapping[str, Any], ...]:
    raw_rows = documents.get(source_key)
    if not isinstance(raw_rows, list):
        return ()
    selected_rows = raw_rows if limit is None else raw_rows[:limit]
    return tuple(
        row for row in selected_rows if isinstance(row, Mapping)
    )


def _substantive_rows(
    documents: Mapping[str, Any],
    source_keys: Sequence[str],
    *,
    limit_per_source: int | None = _MAX_ROWS_PER_SOURCE,
) -> tuple[tuple[str, Mapping[str, Any], str], ...]:
    rows: list[tuple[str, Mapping[str, Any], str]] = []
    for source_key in source_keys:
        for row in _source_rows(documents, source_key, limit=limit_per_source):
            content = _row_text(row)
            if content:
                rows.append((source_key, row, content))
    return tuple(rows)


def _substantive_first_course_rows(
    documents: Mapping[str, Any],
) -> tuple[tuple[str, Mapping[str, Any], str], ...]:
    return tuple(
        ("first_course_record", row, content)
        for row in _source_rows(documents, "first_course_record")
        if (content := _first_course_body_text(row))
    )


def _substantive_admission_rows(
    documents: Mapping[str, Any],
) -> tuple[tuple[str, Mapping[str, Any], str], ...]:
    return tuple(
        ("admission_record", row, content)
        for row in _source_rows(documents, "admission_record")
        if (content := _admission_body_text(row))
    )


def _fact_state(
    facts: Sequence[Any], fact_types: frozenset[str], source_keys: frozenset[str]
) -> str:
    observed_absent = False
    for raw_fact in facts:
        if not isinstance(raw_fact, Mapping):
            continue
        fact_type = _clean(raw_fact.get("fact_type")).lower()
        state = _clean(raw_fact.get("state")).lower()
        source_key = _clean(raw_fact.get("source_key")).lower()
        if (
            fact_type not in fact_types
            or source_key not in source_keys
            or raw_fact.get("current_visit_bound") is not True
        ):
            continue
        if state in _PRESENT_FACT_STATES:
            return "present"
        if state in _ABSENT_FACT_STATES:
            observed_absent = True
    return "absent" if observed_absent else "unknown"


def _timeline_ready(documents: Mapping[str, Any]) -> bool:
    time_markers: set[str] = set()
    for _, row, content in _substantive_rows(documents, _TIMELINE_SOURCES):
        record_time = _clean(row.get("record_time"))
        if record_time:
            time_markers.add(record_time)
        time_markers.update(_DATE_PATTERN.findall(content))
    return len(time_markers) >= 2


def _authoritative_course_time(value: Any) -> datetime | None:
    """007 只接受两类病程表的 record_time，不使用正文或更新时间。"""

    if isinstance(value, datetime):
        return value if value.tzinfo is None else None
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        parsed = datetime.fromisoformat(value.strip())
    except ValueError:
        return None
    return parsed if parsed.tzinfo is None else None


def _rule_007_result(
    *,
    serious_state: str,
    critical_state: str,
    institute_id: str,
    patient_id: str,
    visit_id: str,
    source_schema: str | None,
) -> dict[str, Any]:
    if serious_state == "present" or critical_state == "present":
        return _result(
            "LX0609-007",
            "not_applicable",
            "unstable_patient_fact_present",
            executor_type="program",
        )

    coordinates = (institute_id, patient_id, visit_id)
    if not all(str(value or "").strip() for value in coordinates):
        return _result(
            "LX0609-007",
            "data_gap",
            "course_time_source_unavailable",
            executor_type="program",
        )

    try:
        if has_luxian_0609_current_visit_unstable_order(
            institute_id=institute_id,
            patient_id=patient_id,
            visit_id=visit_id,
            source_schema=source_schema,
        ):
            return _result(
                "LX0609-007",
                "not_applicable",
                "unstable_patient_order_present",
                executor_type="program",
            )

        record_times: set[datetime] = set()
        for source_key in _RULE_007_RECORD_SOURCES:
            rows = read_luxian_0609_native_source_rows(
                source_key=source_key,
                institute_id=institute_id,
                patient_id=patient_id,
                visit_id=visit_id,
                source_schema=source_schema,
            )
            if len(rows) >= luxian_0609_native_source_row_limit(source_key):
                return _result(
                    "LX0609-007",
                    "data_gap",
                    "course_time_source_truncated",
                    executor_type="program",
                )
            record_times.update(
                parsed
                for row in rows
                if (parsed := _authoritative_course_time(row.get("record_time")))
                is not None
            )
    except Exception:
        return _result(
            "LX0609-007",
            "data_gap",
            "course_time_source_unavailable",
            executor_type="program",
        )

    ordered_times = sorted(record_times)
    if len(ordered_times) < 2:
        return _result(
            "LX0609-007",
            "data_gap",
            "authoritative_course_time_unavailable",
            executor_type="program",
        )
    if any(
        current - previous > _RULE_007_MAX_INTERVAL
        for previous, current in zip(ordered_times, ordered_times[1:])
    ):
        return _result(
            "LX0609-007",
            "non_compliant",
            "course_record_interval_over_72h",
            executor_type="program",
        )
    return _result(
        "LX0609-007",
        "compliant",
        "course_record_interval_within_72h",
        executor_type="program",
    )


def _context(
    rule_id: str,
    documents: Mapping[str, Any],
    *,
    controlled_fact: str = "",
) -> str:
    parts = [f"[受控事实] {controlled_fact}"] if controlled_fact else []
    for source_key, row, content in _substantive_rows(
        documents, _RULE_CONTEXT_SOURCES[rule_id]
    ):
        record_time = _clean(row.get("record_time")) or "未提供"
        parts.append(f"[{source_key}] 记录时间={record_time}；内容={content[:_MAX_ROW_CHARS]}")
    return "\n".join(parts)[:_MAX_CONTEXT_CHARS]


def _prompt(wrapper: Mapping[str, Any], *, context: str) -> str:
    custom_prompt = _MAPPING_LINE_PATTERN.sub(
        "", str(wrapper.get("custom_prompt") or "")
    )
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
        r"<think>[\s\S]*?</think>",
        "",
        _response_text(response),
        flags=re.IGNORECASE,
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
    extra_metadata: Mapping[str, Any] | None = None,
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
    metadata.update(dict(extra_metadata or {}))
    item["metadata"] = metadata
    return item


def _normalized_for_similarity(content: str) -> str:
    value = _DATE_PATTERN.sub("", content)
    value = _TIME_PATTERN.sub("", value)
    return re.sub(r"[^0-9A-Za-z\u4e00-\u9fff]", "", value).lower()


@dataclass(frozen=True)
class _CopyAssessment:
    terminal_result: dict[str, Any] | None
    gray_context: str
    safe_metadata: Mapping[str, Any]


def _copy_gray_context(
    *, left_source: str, left_content: str, right_source: str, right_content: str,
    maximum_similarity: float,
) -> str:
    return (
        f"[Python候选] 全文相似度={maximum_similarity * 100:.2f}%，"
        "但未达到强复制证据标准。只比较以下两份当前就诊病程，不得引用其他病历。\n"
        f"[文书A:{left_source}]\n{left_content[:_MAX_ROW_CHARS]}\n"
        f"[文书B:{right_source}]\n{right_content[:_MAX_ROW_CHARS]}"
    )[:_MAX_CONTEXT_CHARS]


def _copy_gray_prompt(*, context: str) -> str:
    return f"""你是病历复制质控裁决器，只判断 LX0609-017：两份病程是否属于不合理复制。

判定约束：
1. Python 已发现全文相似度略高于70%，但这本身不能直接判缺陷。
2. 常规查体模板、共同诊断背景和固定格式重复，不等于不合理复制。
3. 如果症状变化、客观检查数值、病情评估或治疗计划存在明确实质更新，应判合规。
4. 只有核心临床内容大段复用，且缺少针对当日病情的实质变化和处置更新，才判不合规。
5. 不得推测未提供的病历内容。

{context}

只输出JSON：{{"is_compliant": true/false}}"""


def _assess_copy(
    documents: Mapping[str, Any], *, source_complete: bool = False
) -> _CopyAssessment:
    rows = _substantive_rows(
        documents,
        _ROUND_SOURCES,
        limit_per_source=None if source_complete else _MAX_ROWS_PER_SOURCE,
    )
    comparable: list[tuple[str, str, str]] = []
    seen_documents: set[tuple[str, str, str]] = set()
    for source_key, row, content in rows:
        normalized = _normalized_for_similarity(content)
        if len(normalized) < _MIN_COMPARABLE_CHARS:
            continue
        document_id = _clean(row.get("document_id"))
        identity = (
            source_key,
            "document_id" if document_id else _clean(row.get("record_time")),
            document_id or normalized,
        )
        if identity in seen_documents:
            continue
        seen_documents.add(identity)
        comparable.append((source_key, normalized, content))
    safe_metadata: dict[str, Any] = {
        "comparable_document_count": len(comparable),
        "maximum_similarity": 0.0,
        "similarity_threshold": _COPY_SIMILARITY_THRESHOLD,
        "best_match_source_types": [],
    }
    if not rows:
        return _CopyAssessment(
            terminal_result=_result(
                "LX0609-017",
                "not_applicable" if source_complete else "data_gap",
                (
                    "insufficient_comparable_course_records"
                    if source_complete
                    else "course_comparison_material_unavailable"
                ),
                executor_type="program",
                extra_metadata=safe_metadata,
            ),
            gray_context="",
            safe_metadata=safe_metadata,
        )
    if len(comparable) < 2:
        return _CopyAssessment(
            terminal_result=_result(
                "LX0609-017",
                "not_applicable",
                "insufficient_comparable_course_records",
                executor_type="program",
                extra_metadata=safe_metadata,
            ),
            gray_context="",
            safe_metadata=safe_metadata,
        )
    maximum = -1.0
    best_source_types: list[str] = []
    best_pair: tuple[str, str, str, str] | None = None
    longest_block = 0
    substantial_coverage = 0.0
    for index, (left_source, left, left_content) in enumerate(comparable):
        for right_source, right, right_content in comparable[index + 1 :]:
            matcher = SequenceMatcher(None, left, right, autojunk=False)
            similarity = matcher.ratio()
            if similarity > maximum:
                maximum = similarity
                best_source_types = [left_source, right_source]
                best_pair = (left_source, left_content, right_source, right_content)
                blocks = [block.size for block in matcher.get_matching_blocks() if block.size]
                longest_block = max(blocks, default=0)
                substantial_chars = sum(size for size in blocks if size >= 40)
                substantial_coverage = substantial_chars / max(1, min(len(left), len(right)))
    maximum = max(maximum, 0.0)
    safe_metadata.update(
        {
            "maximum_similarity": round(maximum, 4),
            "best_match_source_types": best_source_types,
            "longest_matching_block_chars": longest_block,
            "substantial_matching_coverage": round(substantial_coverage, 4),
        }
    )
    evidence = (
        f"已比较 {len(comparable)} 份病程/查房记录，最高全文相似度 "
            f"{maximum * 100:.4f}%，判定阈值 {_COPY_SIMILARITY_THRESHOLD * 100:.0f}%。"
    )
    strong_copy = maximum >= _COPY_STRONG_EXACT_THRESHOLD or (
        longest_block >= _COPY_STRONG_LONGEST_BLOCK_CHARS
        and substantial_coverage >= _COPY_STRONG_MATCH_COVERAGE
    )
    if maximum > _COPY_SIMILARITY_THRESHOLD and strong_copy:
        item = _result(
            "LX0609-017",
            "non_compliant",
            "strong_copy_evidence",
            executor_type="program",
            extra_metadata=safe_metadata,
        )
        item["findings"] = "发现两份病程/查房记录全文相似度超过70%，存在高度重复。"
        item["evidence"] = evidence
        item["suggestion"] = "请核对重复记录，补充本次病情变化、诊疗调整和查房意见。"
        return _CopyAssessment(item, "", safe_metadata)
    if maximum > _COPY_SIMILARITY_THRESHOLD and best_pair is not None:
        left_source, left_content, right_source, right_content = best_pair
        return _CopyAssessment(
            terminal_result=None,
            gray_context=_copy_gray_context(
                left_source=left_source,
                left_content=left_content,
                right_source=right_source,
                right_content=right_content,
                maximum_similarity=maximum,
            ),
            safe_metadata=safe_metadata,
        )
    item = _result(
        "LX0609-017",
        "compliant",
        "course_similarity_within_threshold",
        executor_type="program",
        extra_metadata=safe_metadata,
    )
    item["evidence"] = evidence
    return _CopyAssessment(item, "", safe_metadata)


def _copy_result(
    documents: Mapping[str, Any], *, source_complete: bool = False
) -> dict[str, Any]:
    """兼容纯函数测试；灰区必须由正式执行入口调用裁剪模型。"""

    assessment = _assess_copy(documents, source_complete=source_complete)
    if assessment.terminal_result is not None:
        return assessment.terminal_result
    return _result(
        "LX0609-017",
        "data_gap",
        "copy_semantic_review_required",
        executor_type="program",
        extra_metadata=assessment.safe_metadata,
    )


def _admission_material_ready(
    documents: Mapping[str, Any], facts: Sequence[Any]
) -> bool:
    complaint_fact = (
        _fact_state(facts, _COMPLAINT_FACT_TYPES, frozenset({"admission_record"}))
        == "present"
    )
    diagnosis_fact = (
        _fact_state(
            facts,
            _PRIMARY_DIAGNOSIS_FACT_TYPES,
            frozenset({"admission_record", "diagnosis"}),
        )
        == "present"
    )
    complaint_text = diagnosis_text = False
    for row in _source_rows(documents, "admission_record"):
        complaint_text = complaint_text or bool(
            _clean(row.get("chief_complaint") or row.get("complaint"))
            or _COMPLAINT_PATTERN.search(_row_text(row))
        )
        diagnosis_text = diagnosis_text or bool(
            _clean(
                row.get("first_diagnosis")
                or row.get("primary_diagnosis")
                or row.get("diagnosis")
            )
            or _DIAGNOSIS_PATTERN.search(_row_text(row))
        )
    return (complaint_fact or complaint_text) and (diagnosis_fact or diagnosis_text)


async def execute_luxian_0609_native_course_quality_rules(
    *,
    rule_ids: Sequence[str],
    wrapper_rules: Sequence[Mapping[str, Any]],
    evidence_payload: Mapping[str, Any] | None,
    institute_id: str = "",
    patient_id: str = "",
    visit_id: str = "",
    source_schema: str | None = None,
    llm_client: CourseQualityLLMClient | None,
) -> NativeCourseQualityExecutionResult:
    """按客户目录顺序执行；每条适用语义规则最多调用模型一次。"""

    requested = {str(rule_id or "").strip().upper() for rule_id in rule_ids}
    selected = tuple(
        rule_id for rule_id in COURSE_QUALITY_RULE_IDS if rule_id in requested
    )
    if not selected:
        return NativeCourseQualityExecutionResult((), ())

    documents = _documents(evidence_payload)
    if documents is None:
        return NativeCourseQualityExecutionResult(
            results=tuple(
                _result(
                    rule_id,
                    "data_gap",
                    "course_projection_unavailable",
                    executor_type="program",
                )
                for rule_id in selected
            ),
            planned_rule_ids=selected,
        )
    facts = _timeline_facts(evidence_payload)
    serious_state = _fact_state(facts, _SERIOUS_FACT_TYPES, _FACT_SOURCE_KEYS)
    critical_state = _fact_state(facts, _CRITICAL_FACT_TYPES, _FACT_SOURCE_KEYS)
    wrappers_by_id = {
        str(wrapper.get("rule_id") or wrapper.get("rule_code") or "")
        .strip()
        .upper(): wrapper
        for wrapper in wrapper_rules
        if isinstance(wrapper, Mapping)
    }

    copy_documents = documents
    copy_source_failure = ""
    coordinates = (institute_id, patient_id, visit_id)
    if "LX0609-017" in selected:
        if not all(str(value or "").strip() for value in coordinates):
            copy_source_failure = "course_comparison_source_unavailable"
        else:
            try:
                complete_documents: dict[str, list[dict[str, Any]]] = {}
                for source_key in (
                    "daily_course_record",
                    "senior_course_record",
                ):
                    source_rows = read_luxian_0609_native_source_rows(
                        source_key=source_key,
                        institute_id=institute_id,
                        patient_id=patient_id,
                        visit_id=visit_id,
                        source_schema=source_schema,
                    )
                    if len(source_rows) >= luxian_0609_native_source_row_limit(
                        source_key
                    ):
                        copy_source_failure = "course_comparison_source_truncated"
                        break
                    complete_documents[source_key] = source_rows
                if not copy_source_failure:
                    copy_documents = complete_documents
            except Exception:
                copy_source_failure = "course_comparison_source_unavailable"

    results: list[dict[str, Any]] = []
    llm_call_count = prompt_tokens = completion_tokens = total_tokens = 0
    api_time = 0.0
    for rule_id in selected:
        if rule_id == "LX0609-017":
            if copy_source_failure:
                results.append(
                    _result(
                        rule_id,
                        "data_gap",
                        copy_source_failure,
                        executor_type="program",
                    )
                )
                continue
            assessment = _assess_copy(
                copy_documents,
                source_complete=copy_documents is not documents,
            )
            if assessment.terminal_result is not None:
                results.append(assessment.terminal_result)
                continue
            wrapper = wrappers_by_id.get(rule_id)
            if (
                wrapper is None
                or not _clean(wrapper.get("custom_prompt"))
                or not assessment.gray_context
            ):
                results.append(
                    _result(
                        rule_id,
                        "data_gap",
                        "copy_prompt_input_unavailable",
                        executor_type="program",
                        extra_metadata=assessment.safe_metadata,
                    )
                )
                continue
            if llm_client is None:
                results.append(
                    _result(
                        rule_id,
                        "data_gap",
                        "copy_llm_unavailable",
                        executor_type="program",
                        extra_metadata=assessment.safe_metadata,
                    )
                )
                continue
            llm_call_count += 1
            try:
                response = await llm_client.generate(
                    _copy_gray_prompt(context=assessment.gray_context)
                )
            except Exception:
                results.append(
                    _result(
                        rule_id,
                        "data_gap",
                        "copy_llm_failure",
                        executor_type="llm",
                        extra_metadata=assessment.safe_metadata,
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
                        "copy_llm_invalid_output",
                        executor_type="llm",
                        prompt_tokens=prompt,
                        completion_tokens=completion,
                        total_tokens=total,
                        api_time=elapsed,
                        extra_metadata=assessment.safe_metadata,
                    )
                )
                continue
            results.append(
                _result(
                    rule_id,
                    "compliant" if is_compliant else "non_compliant",
                    "copy_gray_llm",
                    executor_type="llm",
                    prompt_tokens=prompt,
                    completion_tokens=completion,
                    total_tokens=total,
                    api_time=elapsed,
                    extra_metadata=assessment.safe_metadata,
                )
            )
            continue

        controlled_fact = ""
        if rule_id == "LX0609-007":
            results.append(
                _rule_007_result(
                    serious_state=serious_state,
                    critical_state=critical_state,
                    institute_id=institute_id,
                    patient_id=patient_id,
                    visit_id=visit_id,
                    source_schema=source_schema,
                )
            )
            continue
        elif rule_id == "LX0609-008":
            if serious_state == "absent":
                results.append(
                    _result(
                        rule_id,
                        "not_applicable",
                        "serious_order_fact_absent",
                        executor_type="program",
                    )
                )
                continue
            if serious_state != "present":
                results.append(
                    _result(
                        rule_id,
                        "data_gap",
                        "serious_order_fact_unavailable",
                        executor_type="program",
                    )
                )
                continue
            if not _timeline_ready(documents):
                results.append(
                    _result(
                        rule_id,
                        "data_gap",
                        "course_timeline_unavailable",
                        executor_type="program",
                    )
                )
                continue
            controlled_fact = "当前就诊存在病重医嘱"
        elif rule_id == "LX0609-009":
            if critical_state == "absent":
                results.append(
                    _result(
                        rule_id,
                        "not_applicable",
                        "critical_order_fact_absent",
                        executor_type="program",
                    )
                )
                continue
            if critical_state != "present":
                results.append(
                    _result(
                        rule_id,
                        "data_gap",
                        "critical_order_fact_unavailable",
                        executor_type="program",
                    )
                )
                continue
            if not _timeline_ready(documents):
                results.append(
                    _result(
                        rule_id,
                        "data_gap",
                        "course_timeline_unavailable",
                        executor_type="program",
                    )
                )
                continue
            controlled_fact = "当前就诊存在病危医嘱"
        elif rule_id == "LX0609-016":
            if not _substantive_admission_rows(
                documents
            ) or not _substantive_first_course_rows(documents):
                results.append(
                    _result(
                        rule_id,
                        "data_gap",
                        "admission_or_first_course_unavailable",
                        executor_type="program",
                    )
                )
                continue
        elif rule_id == "LX0609-018":
            if not _substantive_rows(
                documents, ("admission_record",)
            ) or not _admission_material_ready(documents, facts):
                results.append(
                    _result(
                        rule_id,
                        "data_gap",
                        "complaint_or_primary_diagnosis_unavailable",
                        executor_type="program",
                    )
                )
                continue

        context = _context(rule_id, documents, controlled_fact=controlled_fact)
        wrapper = wrappers_by_id.get(rule_id)
        if wrapper is None or not _clean(wrapper.get("custom_prompt")) or not context:
            results.append(
                _result(
                    rule_id,
                    "data_gap",
                    "course_prompt_input_unavailable",
                    executor_type="program",
                )
            )
            continue
        if llm_client is None:
            results.append(
                _result(
                    rule_id,
                    "data_gap",
                    "course_llm_unavailable",
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
                    "course_llm_failure",
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
                    "course_llm_invalid_output",
                    executor_type="llm",
                    prompt_tokens=prompt,
                    completion_tokens=completion,
                    total_tokens=total,
                    api_time=elapsed,
                )
            )
            continue
        status = "compliant" if is_compliant else "non_compliant"
        results.append(
            _result(
                rule_id,
                status,
                "course_customer_prompt",
                executor_type="llm",
                prompt_tokens=prompt,
                completion_tokens=completion,
                total_tokens=total,
                api_time=elapsed,
            )
        )

    return NativeCourseQualityExecutionResult(
        results=tuple(results),
        planned_rule_ids=selected,
        llm_call_count=llm_call_count,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        total_tokens=total_tokens,
        api_time=api_time,
    )
