from __future__ import annotations

from dataclasses import dataclass, field
import json
import re
from typing import Any, Iterable, Protocol

from .luxian_0609.source_evidence_reader import authoritative_document_time_value
from .luxian_0609_trigger_gate import Luxian0609GateDecision, evaluate_luxian_0609_trigger_gates


SUPPORTED_FACT_FAMILIES = {"surgery_anesthesia", "tumor_pathology"}

FAMILY_DISPLAY_NAMES: dict[str, str] = {
    "surgery_anesthesia": "手术麻醉",
    "tumor_pathology": "肿瘤病理",
}

FAMILY_CANDIDATE_MARKERS: dict[str, tuple[str, ...]] = {
    "surgery_anesthesia": ("手术记录", "术前", "术后", "麻醉", "切口", "知情同意", "植入", "抗菌药物", "抗生素"),
    "tumor_pathology": ("病理", "活检", "取材", "送检", "送病检", "送病理", "化疗", "恶性", "肿瘤", "癌"),
}


@dataclass(frozen=True)
class Luxian0609Fact:
    fact_type: str
    family: str
    source_document_type: str
    source_document_id: str = ""
    record_time: str = ""
    quote: str = ""
    confidence: float = 0.0
    extractor: str = "deterministic"
    trace: dict[str, Any] = field(default_factory=dict)

    def to_gate_text(self) -> str:
        return (
            f"事实类型：{self.fact_type}\n"
            f"来源文书：{self.source_document_type or '-'}\n"
            f"记录时间：{self.record_time or '-'}\n"
            f"原文片段：{self.quote}"
        )


@dataclass(frozen=True)
class Luxian0609FactGateEvaluation:
    facts: tuple[Luxian0609Fact, ...]
    fact_context: str
    decisions: dict[str, Luxian0609GateDecision]


@dataclass(frozen=True)
class Luxian0609UnifiedFactTable:
    """POC output for a staged LX0609 fact extraction pipeline.

    The table keeps each stage visible so we can compare recall, latency and
    noise before wiring the route into the live QC path.
    """

    facts: tuple[Luxian0609Fact, ...]
    structured_facts: tuple[Luxian0609Fact, ...]
    regex_facts: tuple[Luxian0609Fact, ...]
    llm_facts: tuple[Luxian0609Fact, ...]
    stats: dict[str, Any]


class Luxian0609FactLLMClient(Protocol):
    async def generate(self, prompt: str) -> dict[str, Any]:
        ...


def _clean_text(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def _document_text(document: dict[str, Any]) -> str:
    fields = (
        "document_type",
        "source_table",
        "doc_type",
        "label",
        "title",
        "document_title",
        "content",
        "text",
        "render_text",
    )
    return "\n".join(_clean_text(document.get(field)) for field in fields if document.get(field))


def _document_type(document: dict[str, Any]) -> str:
    return _clean_text(
        document.get("document_type")
        or document.get("source_table")
        or document.get("doc_type")
        or document.get("label")
        or document.get("title")
        or "unknown"
    )


def _document_time(document: dict[str, Any]) -> str:
    return _clean_text(
        authoritative_document_time_value(document)
        or document.get("display_time")
        or document.get("sort_time")
        or document.get("submit_time")
        or document.get("update_time")
    )


def _document_id(document: dict[str, Any]) -> str:
    return _clean_text(document.get("document_id") or document.get("id") or document.get("doc_id"))


def _iter_structured_fields(document: dict[str, Any]) -> Iterable[tuple[str, Any]]:
    """Yield structured fields without treating the full text as structured data."""

    direct_skip = {
        "content",
        "text",
        "render_text",
        "medical_text",
        "record_content",
        "documents",
        "bundle",
    }
    for key, value in document.items():
        if key in direct_skip or isinstance(value, (dict, list, tuple)):
            continue
        yield str(key), value
    for container_key in ("source_fields", "structured_fields", "fields", "raw_fields"):
        container = document.get(container_key)
        if isinstance(container, dict):
            for key, value in container.items():
                if isinstance(value, (dict, list, tuple)):
                    continue
                yield str(key), value
        elif isinstance(container, list):
            for item in container:
                if not isinstance(item, dict):
                    continue
                key = item.get("source_field") or item.get("field") or item.get("name") or item.get("key")
                value = (
                    item.get("raw_value")
                    or item.get("value")
                    or item.get("raw_value_preview")
                    or item.get("display_value")
                )
                if key and not isinstance(value, (dict, list, tuple)):
                    yield str(key), value


def _structured_field_map(document: dict[str, Any]) -> dict[str, str]:
    fields: dict[str, str] = {}
    for key, value in _iter_structured_fields(document):
        cleaned = _clean_text(value)
        if cleaned:
            fields[key] = cleaned
    return fields


def _structured_source_text(document: dict[str, Any], fields: dict[str, str]) -> str:
    marker_fields = (
        "source_table",
        "document_type",
        "doc_type",
        "label",
        "title",
        "document_title",
        "order_type",
        "order_class",
        "order_name",
        "item_name",
        "surgery_name",
        "operation_name",
        "procedure_name",
        "pathology_diagnosis",
        "diagnosis",
    )
    parts = [_clean_text(document.get(key)) for key in marker_fields if document.get(key)]
    parts.extend(fields.get(key, "") for key in marker_fields if fields.get(key))
    return " ".join(part for part in parts if part)


def _structured_quote(fields: dict[str, str], preferred_keys: Iterable[str], *, fallback_text: str = "") -> str:
    selected: list[str] = []
    lowered = {key.lower(): (key, value) for key, value in fields.items()}
    for preferred_key in preferred_keys:
        item = lowered.get(preferred_key.lower())
        if item:
            selected.append(f"{item[0]}：{item[1]}")
    if not selected:
        for key, value in fields.items():
            if len(selected) >= 5:
                break
            if value and key not in {"content", "text", "record_content"}:
                selected.append(f"{key}：{value}")
    quote = "；".join(selected) or fallback_text
    return _clean_text(quote)[:260]


def _extract_llm_text(response: dict[str, Any]) -> str:
    choices = response.get("choices")
    if isinstance(choices, list) and choices:
        message = choices[0].get("message") if isinstance(choices[0], dict) else None
        if isinstance(message, dict):
            return str(message.get("content") or "")
    return str(response.get("content") or response.get("text") or "")


def _parse_llm_json(text: str) -> dict[str, Any] | None:
    cleaned = re.sub(r"<think>[\s\S]*?</think>", "", str(text or ""), flags=re.IGNORECASE).strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?", "", cleaned, flags=re.IGNORECASE).strip()
        cleaned = re.sub(r"```$", "", cleaned).strip()
    match = re.search(r"\{[\s\S]*\}", cleaned)
    if not match:
        return None
    try:
        parsed = json.loads(match.group(0))
    except Exception:
        return None
    return parsed if isinstance(parsed, dict) else None


def _as_confidence(value: Any) -> float:
    try:
        confidence = float(value)
    except Exception:
        return 0.0
    return max(0.0, min(1.0, confidence))


def _quote_around(text: str, start: int, end: int, *, radius: int = 70, limit: int = 260) -> str:
    return _clean_text(text[max(0, start - radius): min(len(text), end + radius)])[:limit]


def _candidate_documents_for_family(
    documents: Iterable[dict[str, Any]],
    family: str,
    *,
    max_chars: int = 14000,
) -> list[dict[str, Any]]:
    markers = FAMILY_CANDIDATE_MARKERS.get(family, ())
    selected: list[dict[str, Any]] = []
    used_chars = 0
    for document in documents:
        doc_text = _document_text(document)
        if not doc_text:
            continue
        if markers and not any(marker.lower() in doc_text.lower() for marker in markers):
            continue
        selected.append(document)
        used_chars += len(doc_text)
        if used_chars >= max_chars:
            break
    return selected


def _render_documents_for_llm(documents: Iterable[dict[str, Any]], *, max_chars: int = 14000) -> str:
    chunks: list[str] = []
    used_chars = 0
    for index, document in enumerate(documents, start=1):
        doc_text = _document_text(document)
        if not doc_text:
            continue
        chunk = (
            f"【文书{index}】\n"
            f"类型：{_document_type(document)}\n"
            f"文书ID：{_document_id(document)}\n"
            f"记录时间：{_document_time(document) or '-'}\n"
            f"正文：{doc_text[:4200]}"
        )
        if used_chars + len(chunk) > max_chars:
            remaining = max_chars - used_chars
            if remaining > 800:
                chunks.append(chunk[:remaining])
            break
        chunks.append(chunk)
        used_chars += len(chunk)
    return "\n\n".join(chunks)


FACT_PATTERNS: tuple[tuple[str, str, tuple[str, ...], tuple[re.Pattern[str], ...]], ...] = (
    (
        "surgery_anesthesia",
        "surgery_fact",
        ("手术记录", "手术名称", "术中所见", "手术经过"),
        (
            re.compile(r"(手术记录|手术名称|术中所见|手术经过|术前诊断|术后诊断).{0,120}"),
            re.compile(r"(行|拟行|完成|实施).{0,40}(手术|切除|修补|固定|清创|探查)"),
        ),
    ),
    (
        "surgery_anesthesia",
        "antibiotic_order",
        ("抗菌药物", "抗生素", "头孢", "预防用药"),
        (
            re.compile(
                r"(抗菌药物|抗生素|头孢|青霉素|左氧氟沙星|甲硝唑|阿莫西林|克林霉素|哌拉西林|亚胺培南|美罗培南)"
                r".{0,80}(医嘱|静滴|静脉|口服|预防|术前|术后|开始|停止)"
            ),
            re.compile(
                r"(医嘱|静滴|静脉|口服|预防|术前|术后|开始|停止).{0,80}"
                r"(抗菌药物|抗生素|头孢|青霉素|左氧氟沙星|甲硝唑|阿莫西林|克林霉素|哌拉西林|亚胺培南|美罗培南)"
            ),
        ),
    ),
    (
        "surgery_anesthesia",
        "implant_fact",
        ("植入", "补片", "假体", "双J管", "内固定"),
        (
            re.compile(r"(植入物|补片|假体|双J管|内固定|钢板|螺钉|螺丝钉|支架).{0,80}(条码|批号|型号|植入|置入|使用)"),
            re.compile(r"(条码|批号|型号|植入|置入|使用).{0,80}(植入物|补片|假体|双J管|内固定|钢板|螺钉|螺丝钉|支架)"),
        ),
    ),
    (
        "surgery_anesthesia",
        "surgical_discussion",
        ("术前讨论", "MDT", "四级手术"),
        (re.compile(r"(术前讨论|术前小结|MDT|多学科讨论|四级手术|重大手术|疑难复杂手术).{0,120}"),),
    ),
    (
        "tumor_pathology",
        "pathology_report",
        ("病理报告", "病理检查", "病理诊断", "病理结果", "活检报告"),
        (
            re.compile(r"(病理报告|病理检查报告|病理诊断|病理结果|活检报告).{0,120}(报告时间|记录时间|诊断|结果|提示|出具|标本|取材)"),
            re.compile(r"(报告时间|记录时间|诊断|结果|提示|出具|标本|取材).{0,120}(病理报告|病理检查报告|病理诊断|病理结果|活检报告)"),
        ),
    ),
    (
        "tumor_pathology",
        "pathology_specimen_sent",
        ("取材", "送检", "送病检", "送病理", "标本", "活检", "冰冻"),
        (
            re.compile(r"(活检|穿刺活检|取材|送检|送病理|送病检|标本|冰冻病理|术中冰冻).{0,120}"),
            re.compile(r"(手术记录|术中|手术).{0,80}(取材|标本|送检|送病理|送病检|病理)"),
            re.compile(r"(取材|标本|送检|送病理|送病检|病理).{0,80}(手术记录|术中|手术)"),
        ),
    ),
    (
        "tumor_pathology",
        "malignant_tumor_surgery",
        ("恶性肿瘤", "腺癌", "鳞癌", "癌", "淋巴结清扫", "根治术"),
        (
            re.compile(r"(恶性肿瘤|腺癌|鳞癌|癌|淋巴瘤|肉瘤|胃癌|肺癌|乳腺癌|结直肠癌|结肠癌|直肠癌).{0,80}(手术|根治术|切除术|清扫术|淋巴结清扫|标本|送检)"),
            re.compile(r"(手术|根治术|切除术|清扫术|淋巴结清扫|标本|送检).{0,80}(恶性肿瘤|腺癌|鳞癌|癌|淋巴瘤|肉瘤|胃癌|肺癌|乳腺癌|结直肠癌|结肠癌|直肠癌)"),
        ),
    ),
    (
        "tumor_pathology",
        "chemo_fact",
        ("化疗", "奥沙利铂", "卡培他滨", "紫杉醇", "顺铂", "替吉奥"),
        (
            re.compile(r"(化疗医嘱|化疗记录|化学治疗记录|辅助化疗|新辅助化疗|化疗方案).{0,120}"),
            re.compile(r"(奥沙利铂|卡培他滨|顺铂|紫杉醇|多西他赛|吉西他滨|替吉奥|氟尿嘧啶|伊立替康|依托泊苷).{0,80}"),
            re.compile(r"\b(XELOX|FOLFOX|FOLFIRI|TP|GP|TC)\b.{0,80}", re.IGNORECASE),
        ),
    ),
)


_CANCER_RE = re.compile(r"(恶性肿瘤|腺癌|鳞癌|癌|淋巴瘤|肉瘤|胃癌|肺癌|乳腺癌|结直肠癌|结肠癌|直肠癌)")
_SURGERY_RE = re.compile(r"(手术|根治术|切除术|清扫术|修补术|固定术|探查术|清创术)")
_ANTIBIOTIC_RE = re.compile(r"(抗菌药物|抗生素|头孢|青霉素|左氧氟沙星|甲硝唑|阿莫西林|克林霉素|哌拉西林|亚胺培南|美罗培南)")
_IMPLANT_RE = re.compile(r"(植入物|补片|假体|双J管|内固定|钢板|螺钉|螺丝钉|支架)")
_PATHOLOGY_RE = re.compile(r"(病理报告|病理检查|病理诊断|病理结果|活检报告|病理)")
_SPECIMEN_RE = re.compile(r"(活检|穿刺活检|取材|送检|送病理|送病检|标本|冰冻病理|术中冰冻)")
_CHEMO_RE = re.compile(r"(化疗|奥沙利铂|卡培他滨|顺铂|紫杉醇|多西他赛|吉西他滨|替吉奥|氟尿嘧啶|伊立替康|依托泊苷|XELOX|FOLFOX|FOLFIRI)")


def _has_structured_key(fields: dict[str, str], pattern: str) -> bool:
    compiled = re.compile(pattern, re.IGNORECASE)
    return any(compiled.search(key) and value for key, value in fields.items())


def _has_strong_current_surgery_fact(source_text: str, fields: dict[str, str], combined_text: str) -> bool:
    """Avoid treating history phrases such as '否认手术史' as current surgery."""

    source_hit = re.search(r"(surgery_record|operation_record|anesthesia|手术记录|麻醉记录|术前小结|术前讨论)", source_text, re.IGNORECASE)
    key_hit = _has_structured_key(fields, r"(surgery|operation|procedure|手术名称|手术项目|术式)")
    phrase_hit = re.search(r"(行|拟行|实施|完成|接受).{0,30}(手术|切除术|修补术|固定术|探查术|清创术|根治术)", combined_text)
    negated_history = re.search(r"(否认|无).{0,12}(手术史|手术外伤史|外伤手术史)", combined_text)
    return bool(source_hit or key_hit or (phrase_hit and not negated_history))


def _append_structured_fact(
    facts: list[Luxian0609Fact],
    seen: set[tuple[str, str, str, str]],
    *,
    family: str,
    fact_type: str,
    document: dict[str, Any],
    quote: str,
    confidence: float,
    matched_by: str,
) -> None:
    doc_type = _document_type(document)
    doc_id = _document_id(document)
    record_time = _document_time(document)
    cleaned_quote = _clean_text(quote)
    if not cleaned_quote:
        return
    key = (family, fact_type, doc_id or doc_type, cleaned_quote[:120])
    if key in seen:
        return
    seen.add(key)
    facts.append(
        Luxian0609Fact(
            fact_type=fact_type,
            family=family,
            source_document_type=doc_type,
            source_document_id=doc_id,
            record_time=record_time,
            quote=cleaned_quote[:260],
            confidence=confidence,
            extractor="structured",
            trace={"matched_by": matched_by},
        )
    )


def extract_luxian_0609_structured_facts(
    documents: Iterable[dict[str, Any]],
    *,
    families: Iterable[str] | None = None,
) -> list[Luxian0609Fact]:
    """Extract high-confidence facts from structured document fields first."""

    allowed_families = set(families or SUPPORTED_FACT_FAMILIES)
    facts: list[Luxian0609Fact] = []
    seen: set[tuple[str, str, str, str]] = set()
    for document in documents:
        fields = _structured_field_map(document)
        if not fields:
            continue
        source_text = _structured_source_text(document, fields)
        field_text = " ".join(fields.values())
        combined_text = f"{source_text} {field_text}"

        if "surgery_anesthesia" in allowed_families:
            if _has_strong_current_surgery_fact(source_text, fields, combined_text):
                _append_structured_fact(
                    facts,
                    seen,
                    family="surgery_anesthesia",
                    fact_type="surgery_fact",
                    document=document,
                    quote=_structured_quote(
                        fields,
                        (
                            "surgery_name",
                            "operation_name",
                            "procedure_name",
                            "incision_type",
                            "operation_level",
                            "record_time",
                        ),
                        fallback_text=source_text,
                    ),
                    confidence=0.94,
                    matched_by="structured_surgery_fields",
                )
            if _ANTIBIOTIC_RE.search(combined_text):
                _append_structured_fact(
                    facts,
                    seen,
                    family="surgery_anesthesia",
                    fact_type="antibiotic_order",
                    document=document,
                    quote=_structured_quote(
                        fields,
                        ("order_name", "item_name", "drug_name", "start_time", "stop_time", "order_status"),
                        fallback_text=source_text,
                    ),
                    confidence=0.92,
                    matched_by="structured_antibiotic_fields",
                )
            if _IMPLANT_RE.search(combined_text):
                _append_structured_fact(
                    facts,
                    seen,
                    family="surgery_anesthesia",
                    fact_type="implant_fact",
                    document=document,
                    quote=_structured_quote(
                        fields,
                        ("material_name", "item_name", "implant_name", "barcode", "batch_no", "model"),
                        fallback_text=source_text,
                    ),
                    confidence=0.91,
                    matched_by="structured_implant_fields",
                )
            if re.search(r"(术前讨论|术前小结|MDT|多学科讨论|四级手术)", combined_text):
                _append_structured_fact(
                    facts,
                    seen,
                    family="surgery_anesthesia",
                    fact_type="surgical_discussion",
                    document=document,
                    quote=_structured_quote(
                        fields,
                        ("document_title", "title", "record_time", "discussion_time", "physician_sign"),
                        fallback_text=source_text,
                    ),
                    confidence=0.9,
                    matched_by="structured_discussion_fields",
                )

        if "tumor_pathology" in allowed_families:
            if _PATHOLOGY_RE.search(combined_text) or "pathology" in source_text.lower():
                _append_structured_fact(
                    facts,
                    seen,
                    family="tumor_pathology",
                    fact_type="pathology_report",
                    document=document,
                    quote=_structured_quote(
                        fields,
                        (
                            "pathology_diagnosis",
                            "diagnosis",
                            "report_time",
                            "record_time",
                            "specimen",
                            "sample_name",
                        ),
                        fallback_text=source_text,
                    ),
                    confidence=0.94,
                    matched_by="structured_pathology_fields",
                )
            if _SPECIMEN_RE.search(combined_text):
                _append_structured_fact(
                    facts,
                    seen,
                    family="tumor_pathology",
                    fact_type="pathology_specimen_sent",
                    document=document,
                    quote=_structured_quote(
                        fields,
                        ("specimen", "sample_name", "specimen_name", "operation_name", "record_time"),
                        fallback_text=source_text,
                    ),
                    confidence=0.9,
                    matched_by="structured_specimen_fields",
                )
            if _CANCER_RE.search(combined_text) and _has_strong_current_surgery_fact(source_text, fields, combined_text):
                _append_structured_fact(
                    facts,
                    seen,
                    family="tumor_pathology",
                    fact_type="malignant_tumor_surgery",
                    document=document,
                    quote=_structured_quote(
                        fields,
                        ("surgery_name", "operation_name", "procedure_name", "diagnosis", "pathology_diagnosis"),
                        fallback_text=source_text,
                    ),
                    confidence=0.86,
                    matched_by="structured_malignant_surgery_fields",
                )
            if _CHEMO_RE.search(combined_text):
                _append_structured_fact(
                    facts,
                    seen,
                    family="tumor_pathology",
                    fact_type="chemo_fact",
                    document=document,
                    quote=_structured_quote(
                        fields,
                        ("order_name", "item_name", "drug_name", "plan_name", "record_time"),
                        fallback_text=source_text,
                    ),
                    confidence=0.9,
                    matched_by="structured_chemo_fields",
                )
    return facts


def extract_luxian_0609_facts(
    documents: Iterable[dict[str, Any]],
    *,
    families: Iterable[str] | None = None,
    extractor: str = "deterministic",
) -> list[Luxian0609Fact]:
    """Extract source-grounded facts for LX0609 gate/QC decisions.

    This deterministic extractor is intentionally conservative. It is not the
    final compliance judge; it only emits facts that later gates can consume.
    """

    allowed_families = set(families or SUPPORTED_FACT_FAMILIES)
    facts: list[Luxian0609Fact] = []
    seen: set[tuple[str, str, str]] = set()
    for document in documents:
        content = _document_text(document)
        if not content:
            continue
        doc_type = _document_type(document)
        doc_id = _document_id(document)
        record_time = _document_time(document)
        for family, fact_type, prefilters, patterns in FACT_PATTERNS:
            if family not in allowed_families:
                continue
            if prefilters and not any(marker.lower() in content.lower() for marker in prefilters):
                continue
            for pattern in patterns:
                for match in pattern.finditer(content):
                    quote = _quote_around(content, match.start(), match.end())
                    key = (fact_type, doc_id or doc_type, quote)
                    if key in seen:
                        continue
                    seen.add(key)
                    facts.append(
                        Luxian0609Fact(
                            fact_type=fact_type,
                            family=family,
                            source_document_type=doc_type,
                            source_document_id=doc_id,
                            record_time=record_time,
                            quote=quote,
                            confidence=0.86,
                            extractor=extractor,
                            trace={
                                "pattern": pattern.pattern,
                                "span": [match.start(), match.end()],
                            },
                        )
                    )
                    break
    return facts


def _llm_fact_from_payload(
    *,
    family: str,
    item: dict[str, Any],
    extractor: str,
) -> Luxian0609Fact | None:
    fact_type = _clean_text(item.get("fact_type"))
    quote = _clean_text(item.get("quote"))
    if not fact_type or not quote:
        return None
    confidence = _as_confidence(item.get("confidence"))
    if confidence < 0.35:
        return None
    return Luxian0609Fact(
        fact_type=fact_type,
        family=family,
        source_document_type=_clean_text(item.get("source_document_type")),
        source_document_id=_clean_text(item.get("source_document_id")),
        record_time=_clean_text(item.get("record_time")),
        quote=quote[:260],
        confidence=confidence,
        extractor=extractor,
        trace={"llm_payload": {key: item.get(key) for key in sorted(item.keys()) if key != "quote"}},
    )


async def extract_luxian_0609_facts_with_llm(
    documents: Iterable[dict[str, Any]],
    *,
    families: Iterable[str],
    client: Luxian0609FactLLMClient,
    extractor: str = "llm",
    max_chars_per_family: int = 14000,
) -> list[Luxian0609Fact]:
    """Extract facts through an injected LLM client.

    The LLM is only allowed to emit source-grounded facts. It does not decide
    compliance, and it does not replace downstream gate/programmatic rules.
    """

    document_list = list(documents)
    facts: list[Luxian0609Fact] = []
    seen: set[tuple[str, str, str]] = set()
    for family in families:
        if family not in SUPPORTED_FACT_FAMILIES:
            continue
        candidates = _candidate_documents_for_family(document_list, family, max_chars=max_chars_per_family)
        if not candidates:
            continue
        documents_text = _render_documents_for_llm(candidates, max_chars=max_chars_per_family)
        if not documents_text.strip():
            continue
        response = await client.generate(build_luxian_0609_fact_prompt(family=family, documents_text=documents_text))
        parsed = _parse_llm_json(_extract_llm_text(response))
        raw_facts = parsed.get("facts") if isinstance(parsed, dict) else None
        if not isinstance(raw_facts, list):
            continue
        for item in raw_facts:
            if not isinstance(item, dict):
                continue
            fact = _llm_fact_from_payload(family=family, item=item, extractor=extractor)
            if fact is None:
                continue
            key = (fact.fact_type, fact.source_document_id or fact.source_document_type, fact.quote)
            if key in seen:
                continue
            seen.add(key)
            facts.append(fact)
    return facts


_EXTRACTOR_PRIORITY = {
    "structured": 3,
    "deterministic": 2,
    "regex": 2,
    "llm": 1,
}


def _fact_merge_key(fact: Luxian0609Fact) -> tuple[str, str, str, str]:
    normalized_quote = re.sub(r"\s+", "", fact.quote or "")[:120].lower()
    return (
        fact.family,
        fact.fact_type,
        fact.source_document_id or fact.source_document_type,
        normalized_quote,
    )


def merge_luxian_0609_facts(fact_groups: Iterable[Iterable[Luxian0609Fact]]) -> list[Luxian0609Fact]:
    """Merge staged facts with source-grounded precedence.

    Structured fields are preferred over regex and LLM for the same quote because
    they come from typed upstream columns. Different quotes are kept as separate
    evidence pieces.
    """

    merged: dict[tuple[str, str, str, str], Luxian0609Fact] = {}
    for group in fact_groups:
        for fact in group:
            key = _fact_merge_key(fact)
            existing = merged.get(key)
            if existing is None:
                merged[key] = fact
                continue
            existing_rank = (_EXTRACTOR_PRIORITY.get(existing.extractor, 0), existing.confidence)
            incoming_rank = (_EXTRACTOR_PRIORITY.get(fact.extractor, 0), fact.confidence)
            if incoming_rank > existing_rank:
                merged[key] = fact
    return sorted(
        merged.values(),
        key=lambda fact: (
            FAMILY_DISPLAY_NAMES.get(fact.family, fact.family),
            fact.fact_type,
            fact.source_document_type,
            fact.record_time,
            fact.quote,
        ),
    )


def _fact_stats(facts: Iterable[Luxian0609Fact]) -> dict[str, Any]:
    by_family: dict[str, int] = {}
    by_type: dict[str, int] = {}
    by_extractor: dict[str, int] = {}
    for fact in facts:
        by_family[fact.family] = by_family.get(fact.family, 0) + 1
        by_type[fact.fact_type] = by_type.get(fact.fact_type, 0) + 1
        by_extractor[fact.extractor] = by_extractor.get(fact.extractor, 0) + 1
    return {
        "by_family": by_family,
        "by_type": by_type,
        "by_extractor": by_extractor,
    }


async def extract_luxian_0609_unified_fact_table(
    documents: Iterable[dict[str, Any]],
    *,
    families: Iterable[str] | None = None,
    llm_client: Luxian0609FactLLMClient | None = None,
    llm_model: str = "qwen3-next-80b-a3b-instruct",
    include_llm: bool = True,
    max_chars_per_family: int = 14000,
) -> Luxian0609UnifiedFactTable:
    """POC pipeline: structured fields -> regex strong facts -> LLM text facts."""

    document_list = list(documents)
    family_list = sorted(set(families or SUPPORTED_FACT_FAMILIES))
    structured_facts = extract_luxian_0609_structured_facts(document_list, families=family_list)
    regex_facts = extract_luxian_0609_facts(document_list, families=family_list, extractor="regex")
    llm_facts: list[Luxian0609Fact] = []
    if include_llm and llm_client is not None:
        llm_facts = await extract_luxian_0609_facts_with_llm(
            document_list,
            families=family_list,
            client=llm_client,
            extractor="llm",
            max_chars_per_family=max_chars_per_family,
        )
    merged_facts = merge_luxian_0609_facts((structured_facts, regex_facts, llm_facts))
    return Luxian0609UnifiedFactTable(
        facts=tuple(merged_facts),
        structured_facts=tuple(structured_facts),
        regex_facts=tuple(regex_facts),
        llm_facts=tuple(llm_facts),
        stats={
            "families": family_list,
            "llm_model": llm_model if include_llm and llm_client is not None else "",
            "stage_counts": {
                "structured": len(structured_facts),
                "regex": len(regex_facts),
                "llm": len(llm_facts),
                "merged": len(merged_facts),
            },
            "merged": _fact_stats(merged_facts),
        },
    )


def render_luxian_0609_fact_context(
    facts: Iterable[Luxian0609Fact],
    *,
    families: Iterable[str] | None = None,
) -> str:
    allowed_families = set(families or SUPPORTED_FACT_FAMILIES)
    lines: list[str] = ["LX0609 结构化事实摘要："]
    grouped: dict[str, list[Luxian0609Fact]] = {}
    for fact in facts:
        if fact.family in allowed_families:
            grouped.setdefault(fact.family, []).append(fact)
    for family in sorted(grouped, key=lambda item: FAMILY_DISPLAY_NAMES.get(item, item)):
        lines.append(f"\n## {FAMILY_DISPLAY_NAMES.get(family, family)}")
        for index, fact in enumerate(grouped[family], start=1):
            lines.append(f"【事实{index}】")
            lines.append(fact.to_gate_text())
    return "\n".join(lines).strip()


def evaluate_luxian_0609_gates_from_facts(
    *,
    rules: list[dict[str, Any]],
    facts: Iterable[Luxian0609Fact],
    visit_id: str = "",
    evidence_payload: dict[str, Any] | None = None,
    families: Iterable[str] | None = None,
) -> Luxian0609FactGateEvaluation:
    fact_tuple = tuple(facts)
    fact_context = render_luxian_0609_fact_context(fact_tuple, families=families)
    decisions = evaluate_luxian_0609_trigger_gates(
        rules=rules,
        visit_id=visit_id,
        medical_text=fact_context,
        evidence_payload=evidence_payload or {},
    )
    return Luxian0609FactGateEvaluation(
        facts=fact_tuple,
        fact_context=fact_context,
        decisions=decisions,
    )


def build_luxian_0609_fact_prompt(*, family: str, documents_text: str) -> str:
    family_name = FAMILY_DISPLAY_NAMES.get(family, family)
    return f"""你是医疗质控系统的结构化事实抽取器。你的任务不是判定合规/不合规，只从文书中抽取与“{family_name}”相关的事实。

必须输出 JSON，格式如下：
{{
  "facts": [
    {{
      "fact_type": "surgery_fact|antibiotic_order|implant_fact|surgical_discussion|pathology_report|pathology_specimen_sent|malignant_tumor_surgery|chemo_fact|other_relevant_fact",
      "source_document_type": "文书类型",
      "source_document_id": "文书ID，可为空",
      "record_time": "记录时间，可为空",
      "quote": "原文短片段，不超过160字",
      "confidence": 0.0
    }}
  ]
}}

抽取原则：
1. 只抽取原文能支持的事实，不要补写、推测或下结论。
2. 如果只是在既往史、否认史中提到，置信度应低于 0.5。
3. 如果没有相关事实，返回 {{"facts": []}}。
4. 不要输出 prompt、病历全文或解释性散文。

文书片段：
{documents_text}
"""
