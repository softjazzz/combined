"""LX0609 高风险手术族的裁剪文本事实契约。"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
import json
import re
from typing import Any, Mapping, Sequence


SCHEMA_VERSION = "lx0609-surgery-text-facts-v1"
_DATETIME_PATTERN = re.compile(
    r"(?<!\d)(\d{4}[-年/]\d{1,2}[-月/]\d{1,2}(?:日)?"
    r"(?:[ T]\d{1,2}:\d{2}(?::\d{2})?)?)(?!\d)"
)


@dataclass(frozen=True, repr=False)
class SurgeryTimeCandidate:
    value: datetime
    source_key: str
    field_role: str
    document_ref: str
    precision: str = "second"

    def __repr__(self) -> str:
        return "SurgeryTimeCandidate(<redacted>)"


@dataclass(frozen=True, repr=False)
class SurgeryTextProjection:
    context: str
    time_candidates: Mapping[str, SurgeryTimeCandidate]
    document_refs: frozenset[str]
    # 联合规则提取时，033 必须能验证其事实至少引用手术知情同意书；
    # 只保存安全文书引用到来源类型的映射，不携带正文或三坐标。
    document_source_keys: Mapping[str, str] = field(default_factory=dict)
    # 仅供服务端把已验证的临时 Sxx 引用绑定回实际文书；绝不进入提示词、
    # 客户展示事实或 repr。客户接口会将它转换为不可逆 source_ref。
    document_source_ids: Mapping[str, str] = field(default_factory=dict)

    def __repr__(self) -> str:
        return (
            "SurgeryTextProjection("
            f"document_count={len(self.document_refs)}, "
            f"time_candidate_count={len(self.time_candidates)})"
        )


@dataclass(frozen=True)
class SurgeryEventFact:
    event_ref: str
    evidence_refs: tuple[str, ...]
    surgery_occurrence: str
    malignant_relation: str
    lymph_node_documentation: str
    implant_use: str
    implant_name: str
    implant_type: str
    implant_specification: str
    implant_material: str
    implant_quantity: str
    # 历史模型响应可能仍携带该字段；025 已不再将其作为客户确认的必填项。
    # 保留解析兼容性，但禁止它参与任何判定或缺项展示。
    implant_barcode: str
    incision_class: str
    antimicrobial_intent: str
    start_time_ref: str | None
    start_time_role: str
    end_time_ref: str | None
    end_time_role: str
    interval_scope: str
    special_extension_reason: str
    consent_role: str
    consent_linkage: str
    patient_signature: str
    surgeon_signature: str


_ENUMS = {
    "surgery_occurrence": {"performed", "planned", "unknown"},
    "malignant_relation": {
        "qualifying", "explicit_nonqualifying", "unknown",
    },
    "lymph_node_documentation": {"documented", "not_documented", "unknown"},
    "implant_use": {
        "actual_permanent_implant", "explicit_no_implant", "generic_material_only",
        "planned_only", "removed_only", "unknown",
    },
    "implant_name": {"present", "missing", "unknown"},
    "implant_type": {"present", "missing", "unknown"},
    "implant_specification": {"present", "missing", "unknown"},
    "implant_material": {"present", "missing", "unknown"},
    "implant_quantity": {"present", "missing", "unknown"},
    "implant_barcode": {"present", "missing", "unknown"},
    "incision_class": {"I", "II", "other", "unknown"},
    "antimicrobial_intent": {"prophylactic", "therapeutic", "both", "explicit_none", "unknown"},
    "start_time_role": {"actual_administration", "planned_order", "document_time", "unknown"},
    "end_time_role": {"actual_stop", "planned_order", "document_time", "unknown"},
    "interval_scope": {"prophylactic_segment", "whole_course", "unknown"},
    "special_extension_reason": {"documented", "not_documented", "unknown"},
    "consent_role": {"surgery_informed_consent", "other_consent", "shell_template", "unknown"},
    "consent_linkage": {"current_surgery", "other_or_unclear", "unknown"},
    "patient_signature": {"present", "missing", "unknown"},
    "surgeon_signature": {"present", "missing", "unknown"},
}

_RULE_FACT_FIELDS = {
    "LX0609-024": (
        "surgery_occurrence", "malignant_relation",
        "lymph_node_documentation",
    ),
    "LX0609-025": (
        "surgery_occurrence", "implant_use", "implant_name", "implant_type",
        "implant_specification", "implant_material", "implant_quantity",
    ),
    "LX0609-028": (
        "surgery_occurrence", "incision_class", "antimicrobial_intent",
        "start_time_ref", "start_time_role", "end_time_ref", "end_time_role",
        "interval_scope", "special_extension_reason",
    ),
    "LX0609-033": (
        "consent_role", "consent_linkage",
        "patient_signature", "surgeon_signature",
    ),
}

_EXAMPLE_VALUES = {
    "surgery_occurrence": "performed|planned|unknown",
    "malignant_relation": "qualifying|explicit_nonqualifying|unknown",
    "lymph_node_documentation": "documented|not_documented|unknown",
    "implant_use": "actual_permanent_implant|explicit_no_implant|generic_material_only|planned_only|removed_only|unknown",
    "implant_name": "present|missing|unknown",
    "implant_type": "present|missing|unknown",
    "implant_specification": "present|missing|unknown",
    "implant_material": "present|missing|unknown",
    "implant_quantity": "present|missing|unknown",
    "incision_class": "I|II|other|unknown",
    "antimicrobial_intent": "prophylactic|therapeutic|both|explicit_none|unknown",
    "start_time_ref": None,
    "start_time_role": "actual_administration|planned_order|document_time|unknown",
    "end_time_ref": None,
    "end_time_role": "actual_stop|planned_order|document_time|unknown",
    "interval_scope": "prophylactic_segment|whole_course|unknown",
    "special_extension_reason": "documented|not_documented|unknown",
    "consent_role": "surgery_informed_consent|other_consent|shell_template|unknown",
    "consent_linkage": "current_surgery|other_or_unclear|unknown",
    "patient_signature": "present|missing|unknown",
    "surgeon_signature": "present|missing|unknown",
}


def _clean(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def _parse_datetime(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, str):
        candidate = value.strip().replace("年", "-").replace("月", "-").replace("日", "")
        candidate = candidate.replace("/", "-").replace("T", " ")
        try:
            parsed = datetime.fromisoformat(candidate)
        except ValueError:
            return None
    else:
        return None
    if parsed.tzinfo is None:
        return parsed
    if parsed.utcoffset() != __import__("datetime").timedelta(hours=8):
        return None
    return parsed.replace(tzinfo=None)


def _time_precision(value: Any) -> str:
    if isinstance(value, datetime):
        return "second"
    candidate = str(value or "").strip()
    if re.search(r"\d{1,2}:\d{2}:\d{2}", candidate):
        return "second"
    if re.search(r"\d{1,2}:\d{2}", candidate):
        return "minute"
    return "date"


def _row_text(row: Mapping[str, Any]) -> str:
    fields = (
        "document_title", "record_content", "content", "surgery_name", "surgery_process",
        "diagnosis", "diagnosis_name", "specimen_name", "eye_findings", "microscope_findings",
        "generic_name", "brand_name", "drug_type", "drug_apply_method", "drug_frequency",
        "order_status", "patient_sign", "surgeon_sign", "planned_operation_name",
        "surgial_incision_level", "surgical_incision_level",
    )
    parts: list[str] = []
    for field in fields:
        value = _clean(row.get(field))
        if not value:
            continue
        if field in {"surgial_incision_level", "surgical_incision_level"}:
            parts.append(f"切口等级:{value}")
        else:
            parts.append(value)
    return _clean(" ".join(parts))


def build_surgery_text_projection(
    *, rows_by_source: Mapping[str, Sequence[Mapping[str, Any]]],
    max_rows_per_source: int = 50, max_row_chars: int = 2400,
    max_context_chars: int = 32000, max_documents: int | None = None,
) -> SurgeryTextProjection:
    if max_documents is not None and max_documents <= 0:
        raise ValueError("invalid surgery document limit")
    source_order = (
        "surgery_record", "mr_surgery", "pathology_exam_master", "pathology_exam_report", "diagnosis",
        "inpat_drug_order", "daily_course_record", "surgery_inform_consent", "consent_form",
    )
    parts: list[str] = []
    refs: set[str] = set()
    source_keys_by_ref: dict[str, str] = {}
    source_ids_by_ref: dict[str, str] = {}
    times: dict[str, SurgeryTimeCandidate] = {}
    time_index = 0
    for source_position, source_key in enumerate(source_order, start=1):
        source_rows = tuple(rows_by_source.get(source_key, ()))
        if len(source_rows) > max_rows_per_source:
            raise ValueError("surgery source projection truncated")
        for row_index, row in enumerate(source_rows, start=1):
            if not isinstance(row, Mapping):
                continue
            text = _row_text(row)
            if not text:
                continue
            if max_documents is not None and len(refs) >= max_documents:
                raise ValueError("surgery document projection truncated")
            if len(text) > max_row_chars:
                raise ValueError("surgery document projection truncated")
            doc_ref = f"S{source_position:02d}-{row_index:02d}"
            refs.add(doc_ref)
            source_keys_by_ref[doc_ref] = source_key
            source_document_id = _clean(row.get("document_id") or row.get("id"))
            if source_document_id:
                source_ids_by_ref[doc_ref] = source_document_id
            raw_times: list[tuple[Any, str]] = [
                (row.get(field), field)
                for field in (
                    "record_time", "report_time", "report_datetime", "prescribed_datetime",
                    "surgery_begin_time", "surgery_end_time", "surgery_begin_datetime",
                    "surgery_end_datetime",
                )
                if row.get(field) not in (None, "")
            ]
            raw_times.extend(
                (match.group(1), "text_datetime_candidate")
                for match in _DATETIME_PATTERN.finditer(text)
            )
            time_labels: list[str] = []
            seen: set[tuple[datetime, str]] = set()
            for raw_time, field_role in raw_times:
                parsed = _parse_datetime(raw_time)
                identity = (parsed, field_role) if parsed is not None else None
                if parsed is None or identity in seen:
                    continue
                seen.add(identity)
                time_index += 1
                time_ref = f"T{time_index:03d}"
                times[time_ref] = SurgeryTimeCandidate(
                    parsed, source_key, field_role, doc_ref,
                    _time_precision(raw_time),
                )
                time_labels.append(
                    f"{time_ref}={parsed.isoformat(sep=' ')}({field_role})"
                )
            parts.append(
                f"[{doc_ref}|{source_key}|{'、'.join(time_labels) or '无权威时间'}] "
                + text
            )
    context = "\n".join(parts)
    if len(context) > max_context_chars:
        raise ValueError("surgery text projection truncated")
    return SurgeryTextProjection(
        context,
        dict(times),
        frozenset(refs),
        source_keys_by_ref,
        source_ids_by_ref,
    )


def build_surgery_text_fact_prompt(
    *,
    selected_rule_ids: Sequence[str],
    projection: SurgeryTextProjection,
    max_completion_tokens: int | None = None,
) -> str:
    selected = tuple(str(item).strip().upper() for item in selected_rule_ids)
    allowed = {"LX0609-024", "LX0609-025", "LX0609-028", "LX0609-033"}
    if not selected or any(item not in allowed for item in selected):
        raise ValueError("unsupported surgery text fact scope")
    if max_completion_tokens is not None and max_completion_tokens <= 0:
        raise ValueError("invalid surgery text completion limit")
    selected_fields = tuple(dict.fromkeys(
        field for rule_id in selected for field in _RULE_FACT_FIELDS[rule_id]
    ))
    event_example: dict[str, Any] = {
        "event_ref": "EV1",
        "evidence_refs": ["S01-01"],
    }
    event_example.update({field: _EXAMPLE_VALUES[field] for field in selected_fields})
    response_example = json.dumps(
        {"schema_version": SCHEMA_VERSION, "events": [event_example]},
        ensure_ascii=False,
        separators=(",", ":"),
    )
    actual_028_example = ""
    if selected == ("LX0609-028",):
        ordered_candidates = sorted(
            projection.time_candidates.items(),
            key=lambda item: (item[1].value, item[0]),
        )
        for start_index, (start_ref, start_candidate) in enumerate(ordered_candidates):
            for end_ref, end_candidate in ordered_candidates[start_index + 1:]:
                if start_candidate.document_ref != end_candidate.document_ref:
                    continue
                actual_028_example = json.dumps(
                    {
                        "schema_version": SCHEMA_VERSION,
                        "events": [{
                            "event_ref": "EV1",
                            "evidence_refs": [start_candidate.document_ref],
                            "surgery_occurrence": "performed",
                            "incision_class": "II",
                            "antimicrobial_intent": "prophylactic",
                            "start_time_ref": start_ref,
                            "start_time_role": "actual_administration",
                            "end_time_ref": end_ref,
                            "end_time_role": "actual_stop",
                            "interval_scope": "prophylactic_segment",
                            # 特殊延长理由与起止时间是两项独立事实；不得由正例
                            # 示例预设“未记录”，否则会把该值锚定为默认输出。
                            "special_extension_reason": "unknown",
                        }],
                    },
                    ensure_ascii=False,
                    separators=(",", ":"),
                )
                break
            if actual_028_example:
                break
    # 028 的同文书实际起止时间正例必须是最终 JSON 示例。否则末尾的通用
    # null 模板会覆盖前面的动态正例，诱导模型忽略已绑定的 T 引用。
    if actual_028_example:
        response_example = actual_028_example
    consent_033_instruction = ""
    if "LX0609-033" in selected:
        consent_033_instruction = (
            "033 只阅读给定的本次手术知情同意书正文；已实施手术锚点已由程序确认，"
            "不得从正文重新推断手术是否发生。只输出 consent_role、consent_linkage、"
            "patient_signature、surgeon_signature 四项三态事实："
            "consent_linkage=current_surgery|other_or_unclear|unknown；"
            "patient_signature/surgeon_signature=present|missing|unknown。"
        )
    shared_implant_instruction = (
        "仅实际永久性植入物才可输出actual_permanent_implant；"
        "缝线、引流、止血材料、器械、导管鞘、导丝、拟植入、取出旧物均不得当作本次实际植入。"
    )
    implant_025_instruction = ""
    if "LX0609-025" in selected:
        implant_025_instruction = (
            "材料名称本身不能证明植入，"
            "必须结合同一条手术记录中本次实际使用、置入、覆盖或修补等明确动作与语境判断。"
        )
    return f"""你是泸县0609手术事实抽取器。只抽取事实，不直接输出质控状态。本次规则：{','.join(selected)}。
每个本次手术事件单独输出。只有已实施的本次手术才是performed，拟行、计划、申请均为planned。024只在本次已实施手术与恶性原发治疗、淋巴结清扫或术中冰冻恶性有直接关联时，malignant_relation才可输出qualifying；既往恶性史、普通送病理、当前良性手术、术后并发症/造口/救治均必须输出explicit_nonqualifying，不能借此认定本次恶性手术。{shared_implant_instruction}{implant_025_instruction}治疗性抗菌药不能当预防用药；时间只能选择给定T候选。麻醉、输血、其他治疗同意书及空模板不能当手术知情同意书，且必须关联本次手术。
{consent_033_instruction}
只能引用给定S/T；无法确定必须unknown，禁止猜测。028引用start_time_ref或end_time_ref时，每个T所在文书的S引用都必须加入evidence_refs，不能只引用手术文书。
材料：
{projection.context}
025只抽取各字段是否明确出现，不判断“整体完整”；028起止时间角色只有正文明确表示实际给药/实际停止时才输出actual_administration/actual_stop，否则输出planned_order、document_time或unknown。若预防用药后来转为治疗，只能选择预防阶段的起止并输出interval_scope=prophylactic_segment；选择了整个治疗疗程或无法区分时输出whole_course或unknown。
028实际用药正例：仅当材料已经明确实际给药/实际停止，且下列S/T正是其对应证据时，必须按此结构输出；材料已经明确实际给药/实际停止时，不得填unknown或null。没有明示时仍必须unknown，不得猜测。{actual_028_example or "本次投影没有可成对的同文书T候选，不提供正例。"}
028的special_extension_reason必须独立从正文抽取：明确特殊延长理由=>documented；明确未记录理由=>not_documented；其余unknown。不得仅根据用药时长、起止时间或正例示例猜测该字段。
只输出示例中的字段，不要增加无关规则字段。start_time_ref/end_time_ref没有依据时必须为JSON null。{("输出不得超过" + str(max_completion_tokens) + "个token。") if max_completion_tokens is not None else ""}：{response_example}"""


def _response_text(response: Mapping[str, Any]) -> str:
    choices = response.get("choices")
    if isinstance(choices, list) and choices and isinstance(choices[0], Mapping):
        message = choices[0].get("message")
        if isinstance(message, Mapping):
            return str(message.get("content") or "")
    return str(response.get("content") or response.get("text") or "")


def parse_surgery_text_fact_response(
    *,
    response: Mapping[str, Any],
    projection: SurgeryTextProjection,
    selected_rule_ids: Sequence[str],
) -> tuple[SurgeryEventFact, ...]:
    cleaned = re.sub(r"<think>[\s\S]*?</think>", "", _response_text(response), flags=re.I).strip()
    match = re.search(r"\{[\s\S]*\}", cleaned)
    if not match:
        raise ValueError("surgery text fact response is not JSON")
    try:
        payload = json.loads(match.group(0))
    except (TypeError, ValueError) as exc:
        raise ValueError("surgery text fact response is not JSON") from exc
    if (
        not isinstance(payload, Mapping) or set(payload) != {"schema_version", "events"}
        or payload.get("schema_version") != SCHEMA_VERSION
        or not isinstance(payload.get("events"), list) or not payload["events"]
    ):
        raise ValueError("surgery text fact response schema mismatch")
    selected = tuple(str(item).strip().upper() for item in selected_rule_ids)
    if not selected or any(item not in _RULE_FACT_FIELDS for item in selected):
        raise ValueError("unsupported surgery text fact scope")
    selected_fields = {
        field for rule_id in selected for field in _RULE_FACT_FIELDS[rule_id]
    }
    required = {"event_ref", "evidence_refs", *selected_fields}
    allowed_fields = {"event_ref", "evidence_refs", *_ENUMS, "start_time_ref", "end_time_ref"}
    result: list[SurgeryEventFact] = []
    seen_refs: set[str] = set()
    for raw in payload["events"]:
        if (
            not isinstance(raw, Mapping)
            or not required.issubset(raw)
            or not set(raw).issubset(allowed_fields)
        ):
            raise ValueError("surgery event schema mismatch")
        event_ref = str(raw.get("event_ref") or "").strip()
        evidence = raw.get("evidence_refs")
        if not event_ref or event_ref in seen_refs or not isinstance(evidence, list) or len(result) >= 24:
            raise ValueError("surgery event value mismatch")
        normalized_evidence = tuple(dict.fromkeys(str(item).strip() for item in evidence))
        if not normalized_evidence or any(item not in projection.document_refs for item in normalized_evidence):
            raise ValueError("surgery event evidence ref mismatch")
        # 联合提示词可能同时携带手术、病理、用药等材料；033 仍必须至少
        # 锚定一份手术知情同意书，不能把其它同意书或治疗文书当作手术同意书。
        if (
            "LX0609-033" in selected
            and projection.document_source_keys
            and not any(
                projection.document_source_keys.get(item)
                == "surgery_inform_consent"
                for item in normalized_evidence
            )
        ):
            raise ValueError("surgery consent evidence ref mismatch")
        values: dict[str, str] = {}
        for key, allowed in _ENUMS.items():
            value = str(raw.get(key) or "unknown").strip()
            if key == "incision_class" and value in {
                "III", "IV", "III类", "IV类", "Ⅲ", "Ⅳ", "Ⅲ类", "Ⅳ类",
            }:
                value = "other"
            if key == "start_time_role" and raw.get("start_time_ref") is None:
                value = "unknown"
            elif key == "end_time_role" and raw.get("end_time_ref") is None:
                value = "unknown"
            elif key in {"interval_scope", "special_extension_reason"} and (
                raw.get("start_time_ref") is None or raw.get("end_time_ref") is None
            ):
                value = "unknown"
            if value not in allowed:
                raise ValueError("surgery event enum mismatch")
            values[key] = value
        time_refs: list[str | None] = []
        for key in ("start_time_ref", "end_time_ref"):
            value = raw.get(key) if key in selected_fields else None
            normalized = None if value is None else str(value).strip()
            if normalized and normalized not in projection.time_candidates:
                if set(selected) == {"LX0609-028"}:
                    normalized = None
                else:
                    raise ValueError("surgery event time ref mismatch")
            if (
                normalized
                and projection.time_candidates[normalized].document_ref
                not in normalized_evidence
            ):
                if set(selected) == {"LX0609-028"}:
                    normalized = None
                else:
                    raise ValueError("surgery event time evidence ref mismatch")
            time_refs.append(normalized)
        if time_refs[0] is None:
            values["start_time_role"] = "unknown"
        if time_refs[1] is None:
            values["end_time_role"] = "unknown"
        if None in time_refs:
            values["interval_scope"] = "unknown"
            values["special_extension_reason"] = "unknown"
        seen_refs.add(event_ref)
        result.append(SurgeryEventFact(
            event_ref, normalized_evidence, values["surgery_occurrence"],
            values["malignant_relation"],
            values["lymph_node_documentation"], values["implant_use"],
            values["implant_name"], values["implant_type"],
            values["implant_specification"], values["implant_material"],
            values["implant_quantity"], values["implant_barcode"],
            values["incision_class"], values["antimicrobial_intent"],
            time_refs[0], values["start_time_role"],
            time_refs[1], values["end_time_role"],
            values["interval_scope"], values["special_extension_reason"],
            values["consent_role"],
            values["consent_linkage"], values["patient_signature"],
            values["surgeon_signature"],
        ))
    return tuple(result)
