"""LX0609 会诊质量族原生执行：三类裁剪文书、每病例最多一次语义调用。"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import json
import re
from typing import Any, Mapping, Protocol, Sequence

from .native_execution import build_luxian_0609_native_result
from .source_evidence_reader import read_luxian_0609_native_source_rows


CONSULTATION_RULE_IDS = (
    "LX0609-020",
    "LX0609-021",
    "LX0609-022",
    "LX0609-023",
)
EXECUTOR_KEY = "consultation_quality"
_SOURCE_KEYS = (
    "consultation_record",
    "daily_course_record",
    "senior_course_record",
)
_MAX_ROWS_BY_SOURCE = {
    # 本地214个有会诊就诊中，12张可覆盖212个；再高则保守返回data_gap，避免静默丢证据。
    "consultation_record": 12,
    "daily_course_record": 3,
    "senior_course_record": 3,
}
_MAX_DOCUMENT_CHARS = 900
_MAX_CONTEXT_CHARS = 20000
_COURSE_CONTEXT_KEYWORDS = ("会诊", "遵嘱", "遵会诊", "已遵", "执行")
_CONSULTATION_OPINION_MARKERS = (
    "会诊意见:",
    "会诊意见：",
    "病史敬悉",
    "病史尽悉",
    "病史已悉",
    "病史已获悉",
)
_COURSE_LINK_PATTERNS = (
    re.compile(r"(?:遵(?:照|从)?|按|根据|结合|采纳).{0,16}会诊(?:意见)?"),
    re.compile(r"会诊意见.{0,24}(?:执行|落实|调整|加用|停用|改为|给予|予以|复查|完善)"),
)

_REASON_STATUS = {
    "LX0609-020": {
        "execution_specific": "compliant",
        "execution_missing": "non_compliant",
        "execution_source_incomplete": "data_gap",
    },
    "LX0609-021": {
        "purpose_clear": "compliant",
        "purpose_vague": "non_compliant",
        "purpose_missing": "non_compliant",
        "application_unresolved": "data_gap",
    },
    "LX0609-022": {
        "opinion_clear": "compliant",
        "opinion_vague": "non_compliant",
        "opinion_missing": "non_compliant",
        "opinion_unresolved": "data_gap",
    },
    "LX0609-023": {
        "execution_specific_summarized": "compliant",
        "execution_vague_or_copied": "non_compliant",
        "execution_record_missing": "not_applicable",
        "execution_time_unresolved": "data_gap",
        "execution_source_incomplete": "data_gap",
    },
}

_CONTROLLED_MESSAGES = {
    "compliant": ("会诊相关记录满足该项要求。", ""),
    "non_compliant": ("会诊相关记录未满足该项要求。", "请按会诊记录规范补充具体内容。"),
    "not_applicable": ("当前就诊未发现会诊记录，本规则不适用。", ""),
    "data_gap": ("当前会诊相关资料不足，暂不能形成可靠结论。", "请补齐会诊及后续病程资料后重新质控。"),
    "technical_error": ("会诊质量自动判定暂不可用。", "请稍后重试。"),
}
_REASON_MESSAGES = {
    "execution_record_missing": (
        "未发现可供评价的后续会诊意见执行记录，本项不适用。",
        "",
    ),
}


class ConsultationLLMClient(Protocol):
    async def generate(self, prompt: str) -> dict[str, Any]: ...


@dataclass(frozen=True)
class NativeConsultationExecutionResult:
    results: tuple[dict[str, Any], ...]
    planned_rule_ids: tuple[str, ...]
    llm_call_count: int = 0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    api_time: float = 0.0


def _clean(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def _split_consultation_content(content: str) -> tuple[str, str]:
    positions = [content.find(marker) for marker in _CONSULTATION_OPINION_MARKERS]
    positions = [position for position in positions if position >= 0]
    if not positions:
        return content, ""
    split_at = min(positions)
    return content[:split_at].strip(" ,，;；"), content[split_at:].strip()


def _course_row_can_link(row: Mapping[str, Any]) -> bool:
    content = _clean(row.get("record_content"))
    return any(pattern.search(content) for pattern in _COURSE_LINK_PATTERNS)


def _project_row(source_key: str, row: Mapping[str, Any], index: int) -> str:
    title = _clean(row.get("document_title")) or source_key
    record_time = _clean(row.get("record_time"))
    content = _clean(row.get("record_content"))
    if source_key in {"daily_course_record", "senior_course_record"}:
        positions = [content.find(keyword) for keyword in _COURSE_CONTEXT_KEYWORDS]
        positions = [position for position in positions if position >= 0]
        if positions:
            start = max(0, min(positions) - 240)
            content = content[start : start + _MAX_DOCUMENT_CHARS]
        else:
            content = content[:_MAX_DOCUMENT_CHARS]
    else:
        application, opinion = _split_consultation_content(content)
        content = (
            f"申请段={application or '空'}；会诊意见段={opinion or '无法分段'}"
        )[:_MAX_DOCUMENT_CHARS]
    return f"[{source_key}-{index}] 标题={title}；记录时间={record_time or '未提供'}；正文={content or '空'}"


def _rows_for_context(
    source_key: str, rows_by_source: Mapping[str, Sequence[Mapping[str, Any]]]
) -> list[Mapping[str, Any]]:
    rows = list(rows_by_source.get(source_key) or [])
    limit = _MAX_ROWS_BY_SOURCE[source_key]
    if source_key == "consultation_record":
        return rows[:limit]
    relevant = [
        row
        for row in rows
        if any(
            keyword in _clean(row.get("record_content"))
            for keyword in _COURSE_CONTEXT_KEYWORDS
        )
    ]
    relevant_ids = {id(row) for row in relevant}
    remaining = [row for row in rows if id(row) not in relevant_ids]
    return (relevant + remaining)[:limit]


def _course_context_complete(
    rows_by_source: Mapping[str, Sequence[Mapping[str, Any]]]
) -> bool:
    """裁剪只能省略无会诊关联的病程；相关病程超过预算时必须保守失败。"""
    for source_key in ("daily_course_record", "senior_course_record"):
        relevant_count = sum(
            1
            for row in rows_by_source.get(source_key) or ()
            if any(
                keyword in _clean(row.get("record_content"))
                for keyword in _COURSE_CONTEXT_KEYWORDS
            )
        )
        if relevant_count > _MAX_ROWS_BY_SOURCE[source_key]:
            return False
    return True


def _context(rows_by_source: Mapping[str, Sequence[Mapping[str, Any]]]) -> str:
    parts: list[str] = []
    for source_key in _SOURCE_KEYS:
        rows = _rows_for_context(source_key, rows_by_source)
        parts.extend(
            _project_row(source_key, row, index)
            for index, row in enumerate(rows, start=1)
        )
    return "\n".join(parts)[:_MAX_CONTEXT_CHARS]


def _course_refs(rows_by_source: Mapping[str, Sequence[Mapping[str, Any]]]) -> frozenset[str]:
    return frozenset(
        f"{source_key}-{index}"
        for source_key in ("daily_course_record", "senior_course_record")
        for index, row in enumerate(
            _rows_for_context(source_key, rows_by_source),
            start=1,
        )
        if _course_row_can_link(row)
    )


def _rows_by_ref(
    rows_by_source: Mapping[str, Sequence[Mapping[str, Any]]]
) -> dict[str, Mapping[str, Any]]:
    return {
        f"{source_key}-{index}": row
        for source_key in _SOURCE_KEYS
        for index, row in enumerate(
            _rows_for_context(source_key, rows_by_source), start=1
        )
    }


def _record_datetime(row: Mapping[str, Any] | None) -> datetime | None:
    if not row:
        return None
    value = row.get("record_time")
    if isinstance(value, datetime):
        return value.replace(tzinfo=None)
    candidate = _clean(value)
    if not candidate:
        return None
    try:
        parsed = datetime.fromisoformat(candidate.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed.replace(tzinfo=None)


def _prompt(*, selected: Sequence[str], context: str, course_source_complete: bool) -> str:
    requested = "、".join(selected)
    course_state = "完整" if course_source_complete else "不完整"
    return f"""你是泸县0609会诊质量事实判定器。一次只分析本次就诊的会诊文书及后续病程，不得使用常识补写缺失事实。
本次规则：{requested}
后续病程来源状态：{course_state}

严格口径：
- 020：有会诊后，后续病程是否存在会诊意见执行记录；即使只笼统写“遵会诊意见”，也算存在执行记录，记录质量由023判断；仅会诊单内出现意见不等于后续病程有执行记录。
- 021：会诊申请目的是否明确具体诊疗问题；单独只写“请会诊/协助诊治/请指导”属于不明确，但前面已写明具体症状、异常检查、诊断问题或明确术前评估事项时，即使结尾是“协助诊治”也属于目的明确。
- 022：会诊意见是否有明确诊断判断或可执行检查、治疗、用药、复查建议；只有“必要时检查/调整用药/继续治疗”且没有具体项目属于笼统；结合明确评估结论写“暂无特殊处理/同意手术/观察随访”属于明确意见。
- 023：逐张检查已有后续执行记录是否归纳并写明具体措施；只写“遵会诊意见执行”、照抄意见或无具体措施的链接标为 vague。
- 020/023 只能使用 daily_course_record-* 或 senior_course_record-* 作为后续执行证据。consultation_record 内的“已遵嘱/执行情况”不能代替后续病程。每个 execution_link 必须同时指向被落实的 consultation_ref 和时间晚于它的 course_ref；病程只写“请某科会诊”仍是申请，不是执行。没有匹配后续病程的会诊不得编造链接。
- 021 只判断申请段，即 consultation_record 中“病史敬悉/会诊意见/会诊医师意见”之前的内容；不得借用会诊医师后写的诊断和建议反推申请目的明确。
- 不得把签名、会诊时间缺项串到 021/022/023；只有后续病程来源查询不完整才允许 source_incomplete，临床内容未记录不等于资料来源不完整。

每条规则只能返回下列 reason_code：
021=purpose_clear|purpose_vague|purpose_missing|application_unresolved
022=opinion_clear|opinion_vague|opinion_missing|opinion_unresolved
execution_link.quality=specific|vague

只输出 JSON，不要输出原文、解释或新增字段：
{{"results":{{"LX0609-021":{{"reason_code":"..."}},"LX0609-022":{{"reason_code":"..."}}}},"execution_links":[{{"consultation_ref":"consultation_record-1","course_ref":"daily_course_record-1或senior_course_record-1","quality":"specific或vague"}}]}}

裁剪文书：
{context} """


def _response_text(response: Mapping[str, Any]) -> str:
    choices = response.get("choices")
    if isinstance(choices, list) and choices and isinstance(choices[0], Mapping):
        message = choices[0].get("message")
        if isinstance(message, Mapping):
            return str(message.get("content") or "")
    return str(response.get("content") or response.get("text") or "")


def _parse_payload(response: Mapping[str, Any]) -> dict[str, Any] | None:
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
    return dict(payload) if isinstance(payload, Mapping) else None


def _usage(response: Mapping[str, Any]) -> tuple[int, int, int, float]:
    usage = response.get("usage")
    usage = usage if isinstance(usage, Mapping) else {}
    prompt = int(usage.get("prompt_tokens") or 0)
    completion = int(usage.get("completion_tokens") or 0)
    total = int(usage.get("total_tokens") or prompt + completion)
    return prompt, completion, total, float(response.get("_api_time") or 0.0)


def _derive_execution_reasons(
    *,
    payload: Mapping[str, Any] | None,
    rows_by_source: Mapping[str, Sequence[Mapping[str, Any]]],
    course_source_complete: bool,
) -> tuple[str, str]:
    if not course_source_complete:
        return "execution_source_incomplete", "execution_source_incomplete"
    links = payload.get("execution_links") if isinstance(payload, Mapping) else None
    if not isinstance(links, list):
        return "execution_source_incomplete", "execution_time_unresolved"

    rows_by_ref = _rows_by_ref(rows_by_source)
    consultation_refs = frozenset(
        ref for ref in rows_by_ref if ref.startswith("consultation_record-")
    )
    course_refs = _course_refs(rows_by_source)
    valid_qualities_by_consultation: dict[str, list[str]] = {}
    for raw_link in links:
        if not isinstance(raw_link, Mapping):
            return "execution_source_incomplete", "execution_time_unresolved"
        consultation_ref = str(raw_link.get("consultation_ref") or "").strip()
        course_ref = str(raw_link.get("course_ref") or "").strip()
        quality = str(raw_link.get("quality") or "").strip()
        if course_ref not in course_refs:
            # 模型引用了申请/普通病程，不构成执行证据；按未建立链接处理。
            continue
        consultation_time = _record_datetime(rows_by_ref.get(consultation_ref))
        course_time = _record_datetime(rows_by_ref.get(course_ref))
        if (
            consultation_ref not in consultation_refs
            or quality not in {"specific", "vague"}
            or consultation_time is None
            or course_time is None
            or course_time <= consultation_time
        ):
            return "execution_source_incomplete", "execution_time_unresolved"
        # 同一引用对重复且质量冲突时保留全部判断；023按任一vague保守聚合，不依赖输出顺序。
        valid_qualities_by_consultation.setdefault(consultation_ref, []).append(quality)

    if not valid_qualities_by_consultation:
        return "execution_missing", "execution_record_missing"
    reason_020 = (
        "execution_specific"
        if consultation_refs == frozenset(valid_qualities_by_consultation)
        else "execution_missing"
    )
    reason_023 = (
        "execution_vague_or_copied"
        if any(
            quality == "vague"
            for qualities in valid_qualities_by_consultation.values()
            for quality in qualities
        )
        else "execution_specific_summarized"
    )
    return reason_020, reason_023


def _result(rule_id: str, status: str, reason_code: str, *, executor_type: str) -> dict[str, Any]:
    item = build_luxian_0609_native_result(
        rule_id=rule_id,
        final_state=status,
        finding_kind="requirement_satisfied" if status == "compliant" else status,
        reason_code=reason_code,
    )
    findings, suggestion = _REASON_MESSAGES.get(
        reason_code, _CONTROLLED_MESSAGES[status]
    )
    item["findings"] = findings
    item["suggestion"] = suggestion
    metadata = dict(item.get("metadata") or {})
    metadata["executor_type"] = executor_type
    item["metadata"] = metadata
    return item


def _terminal_results(
    selected: Sequence[str], status: str, reason_code: str
) -> tuple[dict[str, Any], ...]:
    return tuple(_result(rule_id, status, reason_code, executor_type="program") for rule_id in selected)


async def execute_luxian_0609_native_consultation_rules(
    *,
    rule_ids: Sequence[str],
    institute_id: str,
    patient_id: str,
    visit_id: str,
    source_schema: str | None,
    llm_client: ConsultationLLMClient | None,
) -> NativeConsultationExecutionResult:
    requested = {str(rule_id or "").strip().upper() for rule_id in rule_ids}
    selected = tuple(rule_id for rule_id in CONSULTATION_RULE_IDS if rule_id in requested)
    if not selected:
        return NativeConsultationExecutionResult((), ())
    if not all(isinstance(value, str) and value.strip() for value in (institute_id, patient_id, visit_id)):
        return NativeConsultationExecutionResult(
            _terminal_results(selected, "technical_error", "native_coordinates_unavailable"),
            selected,
        )

    rows_by_source: dict[str, list[dict[str, Any]]] = {}
    consultation_complete = True
    course_source_complete = True
    for source_key in _SOURCE_KEYS:
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
            if source_key == "consultation_record":
                consultation_complete = False
            else:
                course_source_complete = False

    consultation_rows = rows_by_source["consultation_record"]
    if not consultation_complete:
        return NativeConsultationExecutionResult(
            _terminal_results(selected, "data_gap", "consultation_source_unavailable"),
            selected,
        )
    if not consultation_rows:
        return NativeConsultationExecutionResult(
            _terminal_results(selected, "not_applicable", "consultation_absent"),
            selected,
        )
    if len(consultation_rows) > _MAX_ROWS_BY_SOURCE["consultation_record"]:
        return NativeConsultationExecutionResult(
            _terminal_results(selected, "data_gap", "consultation_context_overflow"),
            selected,
        )
    if not any(_clean(row.get("record_content")) for row in consultation_rows):
        return NativeConsultationExecutionResult(
            _terminal_results(selected, "data_gap", "consultation_content_unavailable"),
            selected,
        )
    course_source_complete = course_source_complete and _course_context_complete(
        rows_by_source
    )
    if llm_client is None:
        return NativeConsultationExecutionResult(
            _terminal_results(selected, "data_gap", "consultation_llm_unavailable"),
            selected,
        )

    try:
        analysis_rule_ids = list(selected)
        if "LX0609-020" in selected and "LX0609-023" not in analysis_rule_ids:
            analysis_rule_ids.append("LX0609-023")
        response = await llm_client.generate(
            _prompt(
                selected=analysis_rule_ids,
                context=_context(rows_by_source),
                course_source_complete=course_source_complete,
            )
        )
    except Exception:
        return NativeConsultationExecutionResult(
            _terminal_results(selected, "data_gap", "consultation_llm_failure"),
            selected,
            llm_call_count=1,
        )
    prompt_tokens, completion_tokens, total_tokens, api_time = _usage(response)
    payload = _parse_payload(response)
    raw_results = payload.get("results") if isinstance(payload, Mapping) else None
    raw_results = raw_results if isinstance(raw_results, Mapping) else {}
    reason_020, reason_023 = _derive_execution_reasons(
        payload=payload,
        rows_by_source=rows_by_source,
        course_source_complete=course_source_complete,
    )
    results: list[dict[str, Any]] = []
    for rule_id in selected:
        if rule_id == "LX0609-020":
            reason_code = reason_020
            status = _REASON_STATUS[rule_id].get(reason_code, "data_gap")
        else:
            raw = raw_results.get(rule_id)
            raw = raw if isinstance(raw, Mapping) else {}
            reason_code = str(raw.get("reason_code") or "").strip()
            if rule_id == "LX0609-023":
                reason_code = reason_023
            status = _REASON_STATUS[rule_id].get(reason_code, "data_gap")
        if rule_id in {"LX0609-020", "LX0609-023"} and not course_source_complete:
            reason_code = "execution_source_incomplete"
            status = "data_gap"
        if status == "data_gap" and not reason_code:
            reason_code = "consultation_llm_invalid_output"
        results.append(_result(rule_id, status, reason_code, executor_type="llm"))
    return NativeConsultationExecutionResult(
        results=tuple(results),
        planned_rule_ids=selected,
        llm_call_count=1,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        total_tokens=total_tokens,
        api_time=api_time,
    )
