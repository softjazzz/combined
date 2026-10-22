"""LX0609 高风险手术族的裁剪文本事实契约。"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
import json
import re
from typing import Any, Mapping, Sequence

from .source_evidence_reader import AUTHORITATIVE_DOCUMENT_TIME_FIELDS


SCHEMA_VERSION = "lx0609-surgery-text-facts-v2"
LX0609_025_REQUIRED_FIELDS = (
    "implant_name",
    "implant_type",
    "implant_specification",
    "implant_material",
    "implant_quantity",
)
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
    # 仅在服务端用于校验模型返回的植入物名称确实逐字来自所引文书；
    # 不进入 repr、快照或客户接口。
    document_texts: Mapping[str, str] = field(default_factory=dict)

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
    # (植入物原文名称, 使用性质, S文书引用)；仅025使用，名称已由Python逐字校验。
    implant_items: tuple[tuple[str, str, str], ...] = ()


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
    "LX0609-04-02-03": (
        "surgery_occurrence", "malignant_relation",
        "lymph_node_documentation",
    ),
    "LX0609-04-02-04": (
        "surgery_occurrence", "implant_use", *LX0609_025_REQUIRED_FIELDS,
        "implant_items",
    ),
    "LX0609-05-01-01": (
        "surgery_occurrence", "incision_class", "antimicrobial_intent",
        "start_time_ref", "start_time_role", "end_time_ref", "end_time_role",
        "interval_scope", "special_extension_reason",
    ),
    "LX0609-11-01-01": (
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
    "implant_barcode": "present|missing|unknown",
    "implant_items": [{
        "name": "人工硬脑膜",
        "use_kind": "permanent_implant",
        "evidence_ref": "S01-01",
    }],
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
    for field_name in fields:
        value = _clean(row.get(field_name))
        if not value:
            continue
        if field_name in {"surgial_incision_level", "surgical_incision_level"}:
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
    document_texts_by_ref: dict[str, str] = {}
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
            document_texts_by_ref[doc_ref] = text
            source_document_id = _clean(row.get("document_id") or row.get("id"))
            if source_document_id:
                source_ids_by_ref[doc_ref] = source_document_id
            document_clock = next(
                (
                    (row[field], field)
                    for field in AUTHORITATIVE_DOCUMENT_TIME_FIELDS
                    if row.get(field) is not None and str(row[field]).strip()
                ),
                None,
            )
            raw_times: list[tuple[Any, str]] = ([document_clock] if document_clock else []) + [
                (row.get(field), field)
                for field in (
                    "report_time", "report_datetime", "prescribed_datetime",
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
        document_texts_by_ref,
    )


def build_surgery_text_fact_prompt(
    *,
    selected_rule_ids: Sequence[str],
    projection: SurgeryTextProjection,
    max_completion_tokens: int | None = None,
) -> str:
    selected = tuple(str(item).strip().upper() for item in selected_rule_ids)
    allowed = {"LX0609-04-02-03", "LX0609-04-02-04", "LX0609-05-01-01", "LX0609-11-01-01"}
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
    if selected == ("LX0609-05-01-01",):
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
    if "LX0609-11-01-01" in selected:
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
    if "LX0609-04-02-04" in selected:
        required_implant_fields = "、".join(LX0609_025_REQUIRED_FIELDS)
        implant_025_instruction = (
            "材料名称本身不能证明植入，"
            "必须结合同一份手术记录或病程记录中本次实际使用、置入、覆盖或修补等明确动作与语境判断。"
            f"025 只核对手术记录中的 {required_implant_fields} 五项；"
            "implant_barcode 完全不属于本规则，禁止输出或据此判定。"
            "病程记录只能帮助确认本次是否实际使用永久性植入物，不能补足手术记录中的五项字段。"
            "五项字段的 present/missing/unknown 必须只依据本次手术记录正文；"
            "同一手术事件存在多个永久植入物时，每一项字段只有在所有永久植入物均有记录时才可输出present；"
            "任一永久植入物明确缺少该字段即输出missing；没有明确缺失但至少一项无法确认时输出unknown。"
            "implant_items必须逐项输出本次有名称的植入/置入候选、使用性质及其S引用；"
            "name必须是对应S文书中的连续原文，不能归纳、改写或猜测。"
            "use_kind只能是permanent_implant、temporary_device、removed_item或unknown；"
            "仅明确预期永久留在体内的材料可标permanent_implant。"
            "颅内压监测探头、引流管等用于临时监测或引流且后续需移除的器械属于temporary_device，"
            "不能作为永久植入物。"
            "任一五项字段在手术记录中明确缺失时输出missing；没有明确缺失但无法确认时输出unknown。"
        )
    return f"""你是泸县0609手术事实抽取器。只抽取事实，不直接输出质控状态。本次规则：{','.join(selected)}。
每个本次手术事件单独输出。只有已实施的本次手术才是performed，拟行、计划、申请均为planned。024只在本次已实施手术属于胃癌、结直肠癌、食管癌、肺癌的肿瘤切除，宫颈癌根治术、膀胱癌根治性切除，或明确实施淋巴结清扫、淋巴结取样、前哨淋巴结活检时，malignant_relation才可输出qualifying。单纯活检、穿刺、内镜局部切除、置管、造口、引流、姑息减症、无关手术，以及脑肿瘤或血液肿瘤治疗必须输出explicit_nonqualifying。既往恶性史、普通送病理、当前良性手术、术后并发症或救治也不能认定为本次目标肿瘤手术。024的lymph_node_documentation=documented包括三类：记录清扫范围/取样送检，记录前哨淋巴结活检，或明确记录未行淋巴结处理及其原因；只有目标手术记录完全未交代淋巴结处理时才可输出not_documented。{shared_implant_instruction}{implant_025_instruction}治疗性抗菌药不能当预防用药；时间只能选择给定T候选。麻醉、输血、其他治疗同意书及空模板不能当手术知情同意书，且必须关联本次手术。
{consent_033_instruction}
只能引用给定S/T；无法确定必须unknown，禁止猜测。028引用start_time_ref或end_time_ref时，每个T所在文书的S引用都必须加入evidence_refs，不能只引用手术文书。
材料：
{projection.context}
025除字段状态外，还必须输出implant_items；每项只含name、use_kind和evidence_ref，name必须逐字来自该S文书。实际使用的永久植入物、临时器械、取出物均可列为候选，但只有use_kind=permanent_implant的项目属于025核对对象；无法确定使用性质时必须unknown。implant_use=actual_permanent_implant且implant_name=present时必须至少有一项permanent_implant，否则不得有permanent_implant项目。025不判断“整体完整”，也不输出implant_barcode；028起止时间角色只有正文明确表示实际给药/实际停止时才输出actual_administration/actual_stop，否则输出planned_order、document_time或unknown。若预防用药后来转为治疗，只能选择预防阶段的起止并输出interval_scope=prophylactic_segment；选择了整个治疗疗程或无法区分时输出whole_course或unknown。
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
    expected_fields = {"event_ref", "evidence_refs", *selected_fields}
    result: list[SurgeryEventFact] = []
    seen_refs: set[str] = set()
    for raw in payload["events"]:
        if (
            not isinstance(raw, Mapping)
            or set(raw) != expected_fields
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
            "LX0609-11-01-01" in selected
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
        implant_items: list[tuple[str, str, str]] = []
        if "implant_items" in selected_fields:
            raw_implant_items = raw.get("implant_items")
            if not isinstance(raw_implant_items, list) or len(raw_implant_items) > 12:
                raise ValueError("surgery implant items mismatch")
            seen_implant_items: set[tuple[str, str, str]] = set()
            for raw_item in raw_implant_items:
                if not isinstance(raw_item, Mapping) or set(raw_item) != {
                    "name", "use_kind", "evidence_ref",
                }:
                    raise ValueError("surgery implant item schema mismatch")
                name = _clean(raw_item.get("name"))
                use_kind = _clean(raw_item.get("use_kind"))
                evidence_ref = _clean(raw_item.get("evidence_ref"))
                identity = (name, use_kind, evidence_ref)
                if (
                    not name
                    or len(name) > 80
                    or use_kind not in {
                        "permanent_implant",
                        "temporary_device",
                        "removed_item",
                        "unknown",
                    }
                    or evidence_ref not in normalized_evidence
                    or identity in seen_implant_items
                    or name not in projection.document_texts.get(evidence_ref, "")
                ):
                    raise ValueError("surgery implant item evidence mismatch")
                seen_implant_items.add(identity)
                implant_items.append(identity)
            should_identify_implants = (
                values["implant_use"] == "actual_permanent_implant"
                and values["implant_name"] == "present"
            )
            has_permanent_implant = any(
                use_kind == "permanent_implant"
                for _name, use_kind, _evidence_ref in implant_items
            )
            if should_identify_implants != has_permanent_implant:
                raise ValueError("surgery implant item state mismatch")
        time_refs: list[str | None] = []
        for key in ("start_time_ref", "end_time_ref"):
            value = raw.get(key) if key in selected_fields else None
            normalized = None if value is None else str(value).strip()
            if normalized and normalized not in projection.time_candidates:
                if set(selected) == {"LX0609-05-01-01"}:
                    normalized = None
                else:
                    raise ValueError("surgery event time ref mismatch")
            if (
                normalized
                and projection.time_candidates[normalized].document_ref
                not in normalized_evidence
            ):
                if set(selected) == {"LX0609-05-01-01"}:
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
            tuple(implant_items),
        ))
    return tuple(result)
