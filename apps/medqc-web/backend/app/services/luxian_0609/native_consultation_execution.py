"""LX0609 会诊质量族原生执行：按语义/执行拆分裁剪，每病例最多两次调用。"""

from __future__ import annotations

import asyncio
from collections import Counter
from dataclasses import dataclass
from datetime import datetime
import json
import re
from typing import Any, Mapping, Protocol, Sequence

from .decision_model import (
    ApplicabilityState,
    EvidenceState,
    QcDirection,
    RuleDecision,
)
from .consultation_fact_contract import (
    ConsultationInputDocument,
    FactContractError,
    synthesize_consultation_semantic_states,
    synthesize_consultation_rule_states,
    synthesize_consultation_rule_fact_states,
    validate_consultation_semantic_payload,
    validate_consultation_fact_payload,
    validate_consultation_rule_fact_payload,
)
from .evidence_material import (
    EvidenceMaterialTruncated,
    EvidenceMaterialUnavailable,
    Luxian0609EvidenceMaterialStore,
)
from .evidence_snapshot import Luxian0609EvidenceSnapshot
from .native_execution import build_luxian_0609_native_result
from .source_evidence_reader import (
    authoritative_document_time_value,
    SourceEvidenceQueryError,
    SourceEvidenceTruncated,
    SourceEvidenceUnavailable,
    canonical_source_evidence,
    digest_source_evidence,
    read_luxian_0609_native_source_rows,
)


CONSULTATION_RULE_IDS = (
    "LX0609-03-01-01",
    "LX0609-03-01-02",
    "LX0609-03-01-03",
    "LX0609-03-01-04",
)
EXECUTOR_KEY = "consultation_quality"
_TYPED_DECISION_RULE_IDS = frozenset(CONSULTATION_RULE_IDS)
_TYPED_EVALUATOR_VERSION = "consultation-ruledecision-shadow-v2"
_DECISION_SOURCE_KEYS_BY_RULE = {
    "LX0609-03-01-01": (
        "consultation_record",
        "daily_course_record",
        "senior_course_record",
    ),
    "LX0609-03-01-02": ("consultation_record",),
    "LX0609-03-01-03": ("consultation_record",),
    "LX0609-03-01-04": (
        "consultation_record",
        "daily_course_record",
        "senior_course_record",
    ),
}
_SOURCE_KEYS = (
    "consultation_record",
    "daily_course_record",
    "senior_course_record",
    "inpat_drug_order",
    "inpat_nondrug_order",
    "exam_master",
    "exam_item_report",
    "labtest_master",
    "labtest_item_report",
    "surgery_record",
)
_EXECUTION_CANDIDATE_SOURCE_KEYS = (
    "daily_course_record",
    "senior_course_record",
    "inpat_drug_order",
    "inpat_nondrug_order",
    "exam_master",
    "exam_item_report",
    "labtest_master",
    "labtest_item_report",
    "surgery_record",
)
_FACT_MAX_DOCUMENTS = 96
_FACT_MAX_DOCUMENT_CHARS = 4200
_FACT_MAX_CONTEXT_CHARS = 64000
# 仅用于扩大病程候选召回，不据此猜测文书角色或最终状态。
_COURSE_FACT_CANDIDATE_MARKERS = (
    "会诊",
    "会诊意见",
    "遵会诊",
    "按会诊",
    "落实会诊",
    "采纳会诊",
)
_MAX_ROWS_BY_SOURCE = {
    # 本地214个有会诊就诊中，12张可覆盖212个；再高则保守返回data_gap，避免静默丢证据。
    "consultation_record": 12,
    "daily_course_record": 3,
    "senior_course_record": 3,
    "inpat_drug_order": 12,
    "inpat_nondrug_order": 12,
    "exam_master": 8,
    "exam_item_report": 8,
    "labtest_master": 8,
    "labtest_item_report": 8,
    "surgery_record": 4,
}
_MAX_DOCUMENT_CHARS = 900
_MAX_CONTEXT_CHARS = 20000
_COURSE_CONTEXT_KEYWORDS = ("会诊", "遵嘱", "遵会诊", "已遵", "执行")
_CONSULTATION_OPINION_MARKERS = (
    "病史敬悉",
    "病史尽悉",
    "病史已悉",
    "病史已获悉",
)
_CONSULTATION_OPINION_HEADING_RE = re.compile(r"会诊意见\s*[:：]?")
_OPINION_REFERENCE_PREFIX_RE = re.compile(r"(?:遵|按|根据|结合|采纳)\s*$")
_OPINION_AUTHOR_SUFFIX_RE = re.compile(
    r"(?:(?:[一-鿿]{1,12}科)?[一-鿿]{0,8})"
    r"(?:主任医师|副主任医师|主治医师|住院医师|医师|医生|药师)\s*$"
)
_COURSE_LINK_PATTERNS = (
    re.compile(r"(?:遵(?:照|从)?|按|根据|结合|采纳).{0,16}会诊(?:意见)?"),
    re.compile(r"会诊意见.{0,24}(?:执行|落实|调整|加用|停用|改为|给予|予以|复查|完善)"),
)
_EMBEDDED_EXECUTION_HEADING_RE = re.compile(
    r"(?:请会诊执行记录|会诊意见执行情况|执行情况)\s*[:：]"
)
_ROLE_OPINION_MARKER_RE = re.compile(
    r"(?:(?<!申请)(?:医师|医生|药师)会诊|会诊(?:医师|医生|药师))\s*[:：]"
)
_SIGNATURE_RE = re.compile(r"(?:会诊医师|申请医师|医师|医生)?签名\s*[:：]")
_CONSULTATION_SIGNATURE_RE = re.compile(
    r"(?:会诊医师|会诊医生|会诊药师)签名\s*[:：]"
)
_CONSULTATION_OPINION_IDENTITY_RE = re.compile(
    r"(?:^|[\n。；])\s*会诊意见\s*(?:[:：]|\s+)"
)
_COURSE_HISTORY_CONSULTATION_RE = re.compile(
    r"(?:(?:昨日|前日|既往|此前|前次|上次).{0,12}会诊|(?:已经|已|经)会诊(?:后)?)"
)
_EXECUTION_ANCHOR_RE = re.compile(
    r"(?:已)?(?:遵(?:照|从)?|按|根据|结合).{0,12}(?:会诊意见|会诊医嘱|医嘱)"
)
_NON_EXECUTION_PREFIX_RE = re.compile(
    r"^(?:拟|计划|应|待|未|无|尚未|未见|未予|未能|暂无|建议|必要时|需)"
)
_DISQUALIFYING_EXECUTION_RE = re.compile(
    r"(?:尚未|未见|未予|未能|暂无|未(?:执行|落实|遵|按|根据|结合)|拟|计划|"
    r"建议|必要时|应当?|待(?:执行|落实|填写)|需(?:要)?|请填写|未填写)"
)
_NON_ACTIONABLE_OPINION_RE = re.compile(
    r"(?:尚未|未见|未予|未能|暂无|未(?:执行|落实|遵|按|根据|结合)|拟|计划|"
    r"必要时|应当?|待(?:执行|落实|填写)|需(?:要)?|请填写|未填写)"
)
_EXECUTION_GENERIC_WORD_RE = re.compile(
    r"(?:遵照?|遵从|按|根据|结合|会诊意见|会诊医嘱|医嘱|执行|落实|已)"
)
_SPECIFIC_EXECUTION_ACTION_RE = re.compile(
    r"(?:调整|加用|停用|给予|予以|复查|完善|监测|告知|开立|继续|治疗|处理|观察|控制|随访|检查|用药|饮食|护理)"
)
_ACTIONABLE_OPINION_RE = re.compile(
    r"(?:治疗|处理|复查|用药|检查|调整|给予|完善|观察|监测|随访)"
)
_NON_REQUEST_CONSULTATION_RE = re.compile(
    r"(?:(?:拟|计划|建议|必要时|考虑|可)[^。；]{0,24}会诊|"
    r"会诊[^。；]{0,24}(?:拒绝|不同意|取消|未行|未予|暂缓)|"
    r"(?:拒绝|不同意|取消|未行|未予|暂缓)[^。；]{0,24}会诊)"
)
_DEFINITE_CONSULTATION_REQUEST_RE = re.compile(
    r"(?:今日|现已|已经|已|申请|予以|请)[^。；]{0,16}(?:科|医师|医生|药师)?会诊"
)
_RECONSULTATION_MARKER_RE = re.compile(
    r"(?:再次(?:请|申请|予以)?.{0,12}会诊|复会诊|二次会诊|第[二三四五六七八九十0-9]+次会诊)"
)
_PREVIOUS_CONSULTATION_REFERENCE_RE = re.compile(
    r"(?:(?:前次|上次|前述|此前|既往|原)(?:的)?.{0,12}(?:会诊|会诊意见|方案)|"
    r"(?:会诊|会诊意见|方案).{0,8}(?:前次|上次|前述|此前|既往|原)|"
    r"我科会诊(?:曾|已)?.{0,8}(?:给予|予以|使用|应用|开立|制定|调整))"
)
_COMPLETED_EXECUTION_RE = re.compile(
    r"(?:(?:已|已经).{0,32}(?:执行|落实|给予|使用|应用|服用|开立|完成|抗凝|治疗|用药|方案)|"
    r"我科会诊(?:曾|已)?.{0,8}(?:给予|予以|使用|应用|开立))"
)
_OBJECTIVE_RECHECK_RESULT_RE = re.compile(
    r"复查.{0,48}(?:[0-9０-９]|正常|异常|升高|降低|增高|减低|阳性|阴性|达标|未达标|改善|较前)"
)
_RESULT_BASED_ADJUSTMENT_RE = re.compile(
    r"(?:(?:根据|结合|依据).{0,28}(?:复查|结果|指标|INR).{0,40}(?:调整|加量|减量|增量|停用|改用|改为|维持)|"
    r"复查.{0,72}(?:建议|故|遂|现).{0,32}(?:调整|加量|减量|增量|停用|改用|改为|维持))"
)
_DOSE_OR_PLAN_RE = re.compile(
    r"(?:剂量|方案|药物|用药|治疗|[0-9０-９]+(?:\.[0-9０-９]+)?\s*(?:mg|g|ml|片|粒|单位))",
    re.IGNORECASE,
)
_PURPOSE_STRONG_CLINICAL_RE = re.compile(
    r"(?:胸闷|胸痛|腹痛|头痛|发热|咳嗽|咳痰|气促|呼吸困难|恶心|呕吐|"
    r"头晕|乏力|水肿|出血|意识障碍|"
    r"(?:血压|心率|血糖).{0,6}(?:异常|升高|降低|增高|减低|不稳|波动|[0-9０-９])|"
    r"(?:白细胞|血红蛋白|肌酐|转氨酶).{0,6}(?:异常|升高|降低|增高|减低|[0-9０-９])|"
    r"(?:检查|检验|培养|病理).{0,6}(?:阳性|异常)|"
    r"异常|升高|降低|增高|减低|感染|梗死|狭窄|占位|"
    r"结节|肿物|肿瘤|贫血|"
    r"食欲(?:差|下降|不振)|纳差|(?:进食|饮食)(?:差|少|减少|困难|受限)|"
    r"营养(?:不良|风险|不足)|消瘦|体重(?:下降|减轻)|"
    r"心累|心慌|心悸|突发.{0,6}不适|"
    r"术前评估|麻醉评估|用药评估|明确诊断|"
    r"(?:评估|调整|制定).{0,8}(?:手术|麻醉|用药|治疗|风险|方案))"
)
_PURPOSE_GENERIC_ONLY_RE = re.compile(
    r"(?:申请|请|拟请).{0,12}会诊(?:协助诊治|指导诊治|请指导|进一步诊治|评估病情)?"
)
_PURPOSE_NEGATED_CLINICAL_RE = re.compile(
    r"(?:无|未诉|否认)[^，,。；;!?！？]{0,24}"
)
_OPINION_EXECUTION_ONLY_RE = re.compile(
    r"(?:以上)?(?:已)?(?:遵嘱|遵医嘱|遵会诊意见)(?:执行)?"
)
_EXPLICIT_OPINION_ASSESSMENT_RE = re.compile(
    r"(?:综合评估|考虑诊断|结合患者既往病史及检查结果)"
)
_EXPLICIT_OPINION_DISPOSITION_RE = re.compile(
    r"(?:暂无特殊处理|同意手术麻醉|观察随访)"
)

_REASON_STATUS = {
    "LX0609-03-01-01": {
        "execution_specific": "compliant",
        "all_completed_opinions_have_execution": "compliant",
        "execution_missing": "non_compliant",
        "no_completed_opinion": "not_applicable",
        "opinion_unresolved": "data_gap",
        "execution_source_incomplete": "data_gap",
        "semantic_low_confidence": "evaluation_unknown",
    },
    "LX0609-03-01-02": {
        "purpose_clear": "compliant",
        "purpose_vague": "non_compliant",
        "purpose_missing": "non_compliant",
        "no_application": "not_applicable",
        "application_unresolved": "data_gap",
        "semantic_low_confidence": "evaluation_unknown",
    },
    "LX0609-03-01-03": {
        "opinion_clear": "compliant",
        "opinion_vague": "non_compliant",
        "opinion_missing": "non_compliant",
        "no_completed_opinion": "not_applicable",
        "opinion_unresolved": "data_gap",
        "semantic_low_confidence": "evaluation_unknown",
    },
    "LX0609-03-01-04": {
        "execution_specific_summarized": "compliant",
        "execution_vague_or_copied": "non_compliant",
        "execution_record_missing": "not_applicable",
        "execution_time_unresolved": "data_gap",
        "execution_source_incomplete": "data_gap",
        "semantic_low_confidence": "evaluation_unknown",
    },
}

_CONTROLLED_MESSAGES = {
    "compliant": ("会诊相关记录满足该项要求。", ""),
    "non_compliant": ("会诊相关记录未满足该项要求。", "请按会诊记录规范补充具体内容。"),
    "not_applicable": ("当前就诊未发现会诊记录，本规则不适用。", ""),
    "data_gap": ("当前会诊相关资料不足，暂不能形成可靠结论。", "请补齐会诊及后续病程资料后重新质控。"),
    "evaluation_unknown": (
        "当前会诊证据的语义关联置信度不足，暂不能形成确定结论。",
        "请结合会诊申请、意见及后续执行记录复核。",
    ),
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
    decisions: tuple[RuleDecision, ...] = ()
    llm_call_count: int = 0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    api_time: float = 0.0


@dataclass(frozen=True)
class _ConsultationRuleOutcome:
    rule_id: str
    status: str
    reason_code: str
    executor_type: str
    confidence_bucket: str | None = None


_CONFIDENCE_VALUE = {"high": 0.95, "medium": 0.6, "low": 0.3}


@dataclass(frozen=True)
class _ConsultationFactProjection:
    documents: tuple[ConsultationInputDocument, ...]
    context: str
    overflow: bool
    alias_pairs: tuple[tuple[str, str], ...] = ()


def _clean(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def _stable_projected_rows(
    source_key: str,
    rows: Sequence[Mapping[str, Any]],
) -> tuple[tuple[str, Mapping[str, Any]], ...]:
    """按规范化材料排序并为重复材料分配稳定 occurrence。"""

    ordered = sorted(
        ((canonical_source_evidence(dict(row)), row) for row in rows),
        key=lambda item: item[0],
    )
    occurrences: Counter[str] = Counter()
    accepted: list[tuple[str, Mapping[str, Any]]] = []
    for material, row in ordered:
        occurrence = occurrences[material]
        occurrences[material] += 1
        digest = digest_source_evidence(
            {
                "material": material,
                "occurrence": occurrence,
                "source_key": source_key,
            }
        )
        accepted.append((f"{source_key}:{digest}", row))
    return tuple(accepted)


def _is_course_fact_candidate(row: Mapping[str, Any]) -> bool:
    candidate = (
        f"{_clean(row.get('document_title'))} "
        f"{_clean(row.get('record_content'))}"
    )
    return any(marker in candidate for marker in _COURSE_FACT_CANDIDATE_MARKERS)


def _row_time_value(source_key: str, row: Mapping[str, Any]) -> Any:
    fields_by_source = {
        "inpat_drug_order": ("start_time", "order_time", "prescribed_datetime"),
        "inpat_nondrug_order": ("start_time", "order_time", "prescribed_datetime"),
        "exam_master": ("exam_time", "exam_datetime", "report_time", "report_datetime"),
        "exam_item_report": ("report_time",),
        "labtest_master": ("report_datetime", "request_datetime"),
        "labtest_item_report": ("report_time",),
        "surgery_record": ("surgery_begin_time", "surgery_begin_datetime", "record_time"),
    }
    for field in ("record_time", *fields_by_source.get(source_key, ())):
        value = row.get(field)
        if _clean(value):
            return value
    return None


def _structured_execution_text(source_key: str, row: Mapping[str, Any]) -> str:
    if source_key == "inpat_drug_order":
        parts = (
            _clean(row.get("generic_name")) or _clean(row.get("brand_name")),
            _clean(row.get("drug_type")),
            _clean(row.get("drug_apply_method")),
            _clean(row.get("drug_frequency")),
            _clean(row.get("order_status")),
        )
    elif source_key == "inpat_nondrug_order":
        parts = (
            _clean(row.get("order_name")),
            _clean(row.get("order_type")),
            _clean(row.get("order_status")),
        )
    elif source_key in {"exam_master", "exam_item_report"}:
        parts = (
            _clean(row.get("exam_name")),
            _clean(row.get("exam_item_name")) or _clean(row.get("item_name")),
            _clean(row.get("exam_type")),
            _clean(row.get("exam_result")),
            _clean(row.get("exam_impression")) or _clean(row.get("impression")),
            _clean(row.get("exam_conclusion")) or _clean(row.get("conclusion")),
        )
    elif source_key in {"labtest_master", "labtest_item_report"}:
        parts = (
            _clean(row.get("labtest_subject")),
            _clean(row.get("lab_item_name")) or _clean(row.get("item_name")),
            _clean(row.get("specimen")),
            _clean(row.get("result")),
            _clean(row.get("abnormal_indicator")),
            _clean(row.get("labtest_result_status")),
        )
    elif source_key == "surgery_record":
        parts = (
            _clean(row.get("document_title")),
            _clean(row.get("surgery_name")),
            _clean(row.get("surgery_code")),
            _clean(row.get("surgery_process")),
        )
    else:
        parts = ()
    return "；".join(part for part in parts if part)


def _is_execution_fact_candidate(source_key: str, row: Mapping[str, Any]) -> bool:
    if source_key in {"daily_course_record", "senior_course_record"}:
        return _is_course_fact_candidate(row)
    return bool(_structured_execution_text(source_key, row) or _clean(row.get("record_content")))


def _fact_document_text(source_key: str, row: Mapping[str, Any]) -> str:
    """只裁剪角色/关联所需片段，不在此层判断合规状态。"""

    content = _clean(row.get("record_content"))
    if source_key == "consultation_record":
        application, opinion = _split_consultation_content(content)
        embedded = _extract_embedded_execution_text(content)
        parts = (
            f"申请段={application[:1400] or '空'}",
            f"意见段={opinion[:1800] or '空'}",
            f"执行段={embedded[:900] or '空'}",
        )
        projected = "；".join(parts)
    elif source_key in {"daily_course_record", "senior_course_record"}:
        windows: list[str] = []
        for marker in _COURSE_FACT_CANDIDATE_MARKERS:
            start = 0
            while len(windows) < 5:
                position = content.find(marker, start)
                if position < 0:
                    break
                excerpt = content[max(0, position - 260) : position + 520]
                if excerpt not in windows:
                    windows.append(excerpt)
                start = position + len(marker)
        projected = "；".join(windows) or content
    else:
        projected = _structured_execution_text(source_key, row) or content
    if len(projected) <= _FACT_MAX_DOCUMENT_CHARS:
        return projected
    half = _FACT_MAX_DOCUMENT_CHARS // 2
    return f"{projected[:half]}…{projected[-half:]}"


def _build_fact_projection(
    rows_by_source: Mapping[str, Sequence[Mapping[str, Any]]],
) -> _ConsultationFactProjection:
    """会诊表全量进入；后续执行候选按来源裁剪，预算溢出显式失败。"""

    projected: list[tuple[str, str, Mapping[str, Any]]] = []
    for source_key in _SOURCE_KEYS:
        rows = tuple(rows_by_source.get(source_key) or ())
        if source_key != "consultation_record":
            rows = tuple(
                row for row in rows if _is_execution_fact_candidate(source_key, row)
            )
        projected.extend(
            (ref, source_key, row)
            for ref, row in _stable_projected_rows(source_key, rows)
        )
    if len(projected) > _FACT_MAX_DOCUMENTS:
        return _ConsultationFactProjection((), "", True)

    documents: list[ConsultationInputDocument] = []
    lines: list[str] = []
    alias_pairs: list[tuple[str, str]] = []
    source_counts: Counter[str] = Counter()
    alias_prefix = {
        "consultation_record": "C",
        "daily_course_record": "D",
        "senior_course_record": "S",
        "inpat_drug_order": "DO",
        "inpat_nondrug_order": "NO",
        "exam_master": "EM",
        "exam_item_report": "ER",
        "labtest_master": "LM",
        "labtest_item_report": "LR",
        "surgery_record": "SR",
    }
    for ref, source_key, row in projected:
        source_counts[source_key] += 1
        alias = f"{alias_prefix[source_key]}{source_counts[source_key]:02d}"
        alias_pairs.append((alias, ref))
        content = _fact_document_text(source_key, row)
        record_time = _row_time_value(source_key, row)
        documents.append(
            ConsultationInputDocument(
                ref=ref,
                source=source_key,
                record_time=record_time,
            )
        )
        lines.append(
            json.dumps(
                {
                    "ref": alias,
                    "source": source_key,
                    "title": _clean(row.get("document_title")),
                    "record_time": _clean(record_time),
                    "text": content,
                },
                ensure_ascii=False,
                separators=(",", ":"),
            )
        )
    context = "\n".join(lines)
    if len(context) > _FACT_MAX_CONTEXT_CHARS:
        return _ConsultationFactProjection((), "", True)
    return _ConsultationFactProjection(
        tuple(documents), context, False, tuple(alias_pairs)
    )


def _execution_structure_context(
    consultation_rows: Sequence[Mapping[str, Any]],
    projection: _ConsultationFactProjection,
) -> str:
    """仅提供安全计数和引用，帮助模型逐份检查，不在 Python 中下临床结论。"""

    projected = _stable_projected_rows("consultation_record", consultation_rows)
    stable_to_alias = {stable_ref: alias for alias, stable_ref in projection.alias_pairs}
    embedded_refs: list[str] = []
    vague_refs: list[str] = []
    for ref, row in projected:
        alias = stable_to_alias.get(ref)
        execution_text = _extract_embedded_execution_text(
            _clean(row.get("record_content"))
        )
        if not alias or not execution_text:
            continue
        embedded_refs.append(alias)
        if _embedded_execution_quality(execution_text) == "vague":
            vague_refs.append(alias)
    execution_refs = [
        alias
        for alias, stable_ref in projection.alias_pairs
        if any(
            document.ref == stable_ref
            and document.source in _EXECUTION_CANDIDATE_SOURCE_KEYS
            for document in projection.documents
        )
    ]
    return json.dumps(
        {
            "consultation_ref_count": len(projected),
            "same_document_execution_candidate_refs": embedded_refs,
            "same_document_vague_candidate_refs": vague_refs,
            "execution_candidate_refs": execution_refs,
        },
        ensure_ascii=False,
        separators=(",", ":"),
    )


def _restore_projection_refs(
    payload: Mapping[str, Any],
    projection: _ConsultationFactProjection,
) -> dict[str, Any]:
    """模型只复制短别名；进入严格合同前恢复为不可逆稳定引用。"""

    alias_to_ref = dict(projection.alias_pairs)
    restored = dict(payload)
    raw_documents = payload.get("documents")
    if isinstance(raw_documents, list):
        documents: list[Any] = []
        for raw in raw_documents:
            if isinstance(raw, list) and raw:
                item = list(raw)
                item[0] = alias_to_ref.get(str(item[0]), str(item[0]))
                documents.append(item)
            else:
                documents.append(raw)
        restored["documents"] = documents
    raw_facts = payload.get("facts")
    if isinstance(raw_facts, Mapping):
        facts: dict[str, Any] = {}
        for rule_id, raw in raw_facts.items():
            if isinstance(raw, Mapping):
                item = dict(raw)
                refs = item.get("evidence_refs")
                if isinstance(refs, list):
                    item["evidence_refs"] = [
                        alias_to_ref.get(str(ref), str(ref)) for ref in refs
                    ]
                facts[str(rule_id)] = item
            else:
                facts[str(rule_id)] = raw
        restored["facts"] = facts
    return restored


def _role_opinion_matches(content: str) -> tuple[re.Match[str], ...]:
    accepted: list[re.Match[str]] = []
    for match in _ROLE_OPINION_MARKER_RE.finditer(content):
        clause_start = max(
            (content.rfind(token, 0, match.start()) for token in "。；;!?！？"),
            default=-1,
        )
        prefix = content[clause_start + 1 : match.start()]
        if "申请" in prefix:
            continue
        if re.search(r"请.{0,12}科", prefix) and not _extract_tail_execution(
            content, match.end()
        ):
            continue
        accepted.append(match)
    return tuple(accepted)


def _opinion_heading_matches(content: str) -> tuple[re.Match[str], ...]:
    accepted: list[re.Match[str]] = []
    for match in _CONSULTATION_OPINION_HEADING_RE.finditer(content):
        prefix = content[max(0, match.start() - 8) : match.start()]
        if _OPINION_REFERENCE_PREFIX_RE.search(prefix):
            continue
        accepted.append(match)
    return tuple(accepted)


def _opinion_heading_start(content: str, match: re.Match[str]) -> int:
    """将紧邻无冒号“会诊意见”前的科室/医师署名归入意见段。"""

    clause_start = max(
        (content.rfind(token, 0, match.start()) for token in "。；;!?！？"),
        default=-1,
    )
    prefix = content[clause_start + 1 : match.start()].strip()
    if (
        prefix
        and not re.search(r"(?:申请|拟请|请)", prefix)
        and _OPINION_AUTHOR_SUFFIX_RE.fullmatch(prefix)
    ):
        return clause_start + 1
    return match.start()


def _split_consultation_content(content: str) -> tuple[str, str]:
    positions = [content.find(marker) for marker in _CONSULTATION_OPINION_MARKERS]
    positions = [position for position in positions if position >= 0]
    positions.extend(
        _opinion_heading_start(content, match)
        for match in _opinion_heading_matches(content)
    )
    positions.extend(match.start() for match in _role_opinion_matches(content))
    if not positions:
        return content, ""
    split_at = min(positions)
    return content[:split_at].strip(" ,，;；"), content[split_at:].strip()


def _trim_before_signature(content: str) -> str:
    match = _SIGNATURE_RE.search(content)
    return content[: match.start()] if match else content


def _is_positive_execution_segment(content: str, *, require_controlled_start: bool) -> bool:
    candidate = _clean(_trim_before_signature(content)).strip(" ,，;；。")
    if not candidate or candidate in {"/", "-", "--", "无", "空", "未填写"}:
        return False
    if _NON_EXECUTION_PREFIX_RE.search(candidate):
        return False
    if _DISQUALIFYING_EXECUTION_RE.search(candidate):
        return False
    if require_controlled_start:
        return bool(_EXECUTION_ANCHOR_RE.match(candidate))
    # 显式“执行情况”标题已经提供强结构边界；这里只排除空模板、计划和否定。
    return True


def _extract_positive_execution_sentences(
    content: str, *, require_controlled_start: bool
) -> str:
    accepted: list[str] = []
    for raw_sentence in re.split(r"[。；;!?！？]+", _trim_before_signature(content)):
        sentence = _clean(raw_sentence).strip(" ,，;；。")
        if not sentence:
            continue
        disqualifying = _DISQUALIFYING_EXECUTION_RE.search(sentence)
        if disqualifying:
            completed_prefix = sentence[: disqualifying.start()].strip(" ,，;；。")
            if not completed_prefix or not re.search(
                r"(?:已|完成|落实|执行|调整|加用|停用|给予|予以|复查|完善|监测|告知|开立|继续|治疗|处理|观察|控制|随访|检查|用药|饮食|护理)",
                completed_prefix,
            ):
                continue
            sentence = completed_prefix
        if _is_positive_execution_segment(
            sentence, require_controlled_start=require_controlled_start
        ):
            accepted.append(sentence)
    return "。".join(accepted)


def _extract_tail_execution(content: str, boundary_end: int) -> str:
    opinion_tail = _trim_before_signature(content[boundary_end:])
    for match in reversed(list(_EXECUTION_ANCHOR_RE.finditer(opinion_tail))):
        if len(opinion_tail) - match.start() > 120:
            continue
        prefix = opinion_tail[max(0, match.start() - 6) : match.start()]
        if re.search(r"(?:拟|计划|应|待|未|无|尚未|未予|未能|建议)\s*$", prefix):
            continue
        opinion_prefix = opinion_tail[: match.start()]
        if not opinion_prefix.strip(" ,，;；。"):
            continue
        has_sentence_end = bool(re.search(r"[。；;!?！？]", opinion_prefix))
        long_enumerated_opinion = (
            len(opinion_prefix) >= 80
            and sum(opinion_prefix.count(token) for token in ("，", ",")) >= 4
            and bool(
                re.search(
                    r"(?:意见|建议|诊断|考虑|治疗|处理|检查|复查|用药|调整|给予|完善|观察|监测)",
                    opinion_prefix,
                )
            )
        )
        if not (has_sentence_end or long_enumerated_opinion):
            continue
        candidate = opinion_tail[match.start() :]
        positive = _extract_positive_execution_sentences(
            candidate, require_controlled_start=True
        )
        if positive:
            return positive
    return ""


def _extract_embedded_execution_text(content: str) -> str:
    """仅提取同张会诊单中有明确结构边界的既往执行事实。"""
    normalized = _clean(content)
    heading = _EMBEDDED_EXECUTION_HEADING_RE.search(normalized)
    if heading:
        candidate = normalized[heading.end() :]
        return _extract_positive_execution_sentences(
            candidate, require_controlled_start=False
        )

    opinion_boundaries = [
        (position, position + len(marker))
        for marker in _CONSULTATION_OPINION_MARKERS
        if (position := normalized.find(marker)) >= 0
    ]
    opinion_boundaries.extend(
        (match.start(), match.end())
        for match in _role_opinion_matches(normalized)
    )
    opinion_boundaries.extend(
        (match.start(), match.end())
        for match in _opinion_heading_matches(normalized)
    )
    if not opinion_boundaries:
        return ""
    _boundary_start, boundary_end = min(opinion_boundaries)
    return _extract_tail_execution(normalized, boundary_end)


def _embedded_execution_quality(content: str) -> str | None:
    """只裁决段级强边界；灰区继续交给单次语义调用。"""
    if _DISQUALIFYING_EXECUTION_RE.search(_clean(content)):
        return None
    residual = _EXECUTION_GENERIC_WORD_RE.sub("", _clean(content))
    residual = re.sub(r"[\s,，;；。:：!?！？、()（）\[\]【】]+", "", residual)
    action_count = len(_SPECIFIC_EXECUTION_ACTION_RE.findall(residual))
    has_number = bool(re.search(r"[0-9０-９]", residual))
    if len(residual) <= 5 and action_count == 0 and not has_number:
        return "vague"
    if len(residual) >= 8 and (action_count >= 1 or has_number):
        return "specific"
    return None


def _embedded_execution_by_ref(
    rows_by_source: Mapping[str, Sequence[Mapping[str, Any]]]
) -> dict[str, tuple[str, str]]:
    evidence: dict[str, tuple[str, str]] = {}
    rows = _rows_for_context("consultation_record", rows_by_source)
    for index, row in enumerate(rows, start=1):
        content = _extract_embedded_execution_text(
            _clean(row.get("record_content"))
        )
        if content:
            consultation_ref = f"consultation_record-{index}"
            evidence[f"{consultation_ref}-embedded-execution"] = (
                consultation_ref,
                content,
            )
    return evidence

def _embedded_execution_020_coverage_refs(
    rows_by_source: Mapping[str, Sequence[Mapping[str, Any]]]
) -> set[str]:
    covered: set[str] = set()
    for index, row in enumerate(
        _rows_for_context("consultation_record", rows_by_source), start=1
    ):
        source_content = _clean(row.get("record_content"))
        execution_content = _extract_embedded_execution_text(source_content)
        if not execution_content:
            continue
        has_heading = _EMBEDDED_EXECUTION_HEADING_RE.search(source_content) is not None
        if has_heading:
            covered.add(f"consultation_record-{index}")
    return covered


def _is_actionable_consultation_row(content: str) -> bool:
    """判断该会诊意见是否需要后续执行覆盖；申请、模板、否定和空泛意见不计入020。"""
    if _extract_embedded_execution_text(content):
        return True
    _application, opinion = _split_consultation_content(content)
    normalized_opinion = _clean(_trim_before_signature(opinion))
    if not normalized_opinion:
        return False
    if _NON_ACTIONABLE_OPINION_RE.search(normalized_opinion):
        return False
    if _SPECIFIC_EXECUTION_ACTION_RE.search(normalized_opinion):
        return True
    residual = re.sub(r"[\s,，;；。:：!?！？、()（）\[\]【】]+", "", normalized_opinion)
    return len(residual) >= 8 and bool(_ACTIONABLE_OPINION_RE.search(residual))


def _is_actual_consultation_record(row: Mapping[str, Any]) -> bool:
    """筛除混入会诊表的普通病程噪声，但保留短会诊模板供021/022裁决。"""
    title = _clean(row.get("document_title"))
    content = _clean(row.get("record_content"))
    explicit_title = title == "会诊" or any(
        title.endswith(suffix)
        for suffix in (
            "会诊记录",
            "会诊意见",
            "会诊申请",
            "会诊申请单",
            "会诊单",
            "会诊回复",
        )
    )
    if explicit_title or _CONSULTATION_SIGNATURE_RE.search(content):
        return True
    if not content:
        return False
    complete_reconsultation = _is_complete_reconsultation_execution(row)
    has_opinion = (
        any(marker in content for marker in _CONSULTATION_OPINION_MARKERS)
        or bool(_CONSULTATION_OPINION_IDENTITY_RE.search(content))
        or bool(_role_opinion_matches(content))
    )
    if complete_reconsultation:
        return True
    has_request = bool(_DEFINITE_CONSULTATION_REQUEST_RE.search(content))
    request_is_valid = has_request and not _NON_REQUEST_CONSULTATION_RE.search(content)
    if _PREVIOUS_CONSULTATION_REFERENCE_RE.search(
        content
    ) or _COURSE_HISTORY_CONSULTATION_RE.search(content):
        if request_is_valid and has_opinion:
            return True
        return False
    return bool(
        has_opinion
        or request_is_valid
    )


def _consultation_refs_for_execution(
    rows_by_source: Mapping[str, Sequence[Mapping[str, Any]]]
) -> frozenset[str]:
    refs: set[str] = set()
    for index, row in enumerate(
        _rows_for_context("consultation_record", rows_by_source), start=1
    ):
        content = _clean(row.get("record_content"))
        has_embedded_execution = bool(_extract_embedded_execution_text(content))
        has_standard_opinion = any(
            marker in content for marker in _CONSULTATION_OPINION_MARKERS
        ) or bool(_opinion_heading_matches(content))
        if (
            has_embedded_execution
            or (has_standard_opinion or _role_opinion_matches(content))
            and _is_actionable_consultation_row(content)
        ):
            refs.add(f"consultation_record-{index}")
    return frozenset(refs)


def _is_complete_reconsultation_execution(row: Mapping[str, Any]) -> bool:
    """仅接受“前次方案已执行 + 客观复查结果 + 据此调整”的复会诊闭环。"""

    title = _clean(row.get("document_title"))
    content = _clean(row.get("record_content"))
    combined = f"{title} {content}".strip()
    if not combined or not _RECONSULTATION_MARKER_RE.search(combined):
        return False
    if not _PREVIOUS_CONSULTATION_REFERENCE_RE.search(content):
        return False
    if not _COMPLETED_EXECUTION_RE.search(content):
        return False
    if not _OBJECTIVE_RECHECK_RESULT_RE.search(content):
        return False
    if not _RESULT_BASED_ADJUSTMENT_RE.search(content):
        return False
    return bool(_DOSE_OR_PLAN_RE.search(content))


def _reconsultation_execution_by_ref(
    rows_by_source: Mapping[str, Sequence[Mapping[str, Any]]]
) -> dict[str, tuple[str, str]]:
    """仅在唯一既往可执行会诊时绑定完整复会诊闭环。"""

    rows = _rows_for_context("consultation_record", rows_by_source)
    indexed_rows = [
        (index, row, _record_datetime(row))
        for index, row in enumerate(rows, start=1)
    ]
    evidence: dict[str, tuple[str, str]] = {}
    claimed_targets: set[str] = set()
    for evidence_index, evidence_row, evidence_time in indexed_rows:
        if evidence_time is None or not _is_complete_reconsultation_execution(
            evidence_row
        ):
            continue
        earlier = [
            (target_time, target_index)
            for target_index, target_row, target_time in indexed_rows
            if target_time is not None
            and target_time < evidence_time
            and target_index != evidence_index
            and _is_actionable_consultation_row(
                _clean(target_row.get("record_content"))
            )
        ]
        # 没有受控科室/会诊单关联键时，多个既往会诊不能靠“最近一张”猜绑定。
        # 仅在唯一既往可执行会诊时接受“前次会诊”这一明确指代。
        if len(earlier) != 1:
            continue
        _target_time, target_index = earlier[0]
        target_ref = f"consultation_record-{target_index}"
        if target_ref in claimed_targets:
            continue
        claimed_targets.add(target_ref)
        evidence_ref = f"consultation_record-{evidence_index}-reconsult-execution"
        evidence[evidence_ref] = (
            target_ref,
            f"consultation_record-{evidence_index}",
        )
    return evidence


def _course_row_can_link(row: Mapping[str, Any]) -> bool:
    content = _clean(row.get("record_content"))
    return any(pattern.search(content) for pattern in _COURSE_LINK_PATTERNS)


def _course_row_has_consultation_clue(row: Mapping[str, Any]) -> bool:
    """仅用于识别会诊来源可能缺失，不把该线索提升为执行事实。"""
    content = _clean(row.get("record_content"))
    for sentence in re.split(r"[。；;!?！？]", content):
        if "会诊" not in sentence or _NON_REQUEST_CONSULTATION_RE.search(sentence):
            continue
        if _DEFINITE_CONSULTATION_REQUEST_RE.search(sentence):
            return True
    return False


def _purpose_state_from_application(content: str) -> str | None:
    """只用申请段识别强目的或纯套话；灰区继续交给语义模型。"""

    application, _opinion = _split_consultation_content(content)
    application = _clean(application)
    if not application:
        return "purpose_missing"
    positive_application = _PURPOSE_NEGATED_CLINICAL_RE.sub("", application)
    if _PURPOSE_STRONG_CLINICAL_RE.search(positive_application):
        return "purpose_clear"
    compact = re.sub(r"[\s,，;；。:：!?！？、()（）\[\]【】]+", "", application)
    if compact in {"申请会诊", "请会诊", "拟请会诊", "会诊"}:
        return "purpose_missing"
    if _PURPOSE_GENERIC_ONLY_RE.fullmatch(compact):
        return "purpose_vague"
    return None


def _programmatic_purpose_reason(
    consultation_rows: Sequence[Mapping[str, Any]],
) -> str | None:
    states = [
        _purpose_state_from_application(_clean(row.get("record_content")))
        for row in consultation_rows
    ]
    if not states or any(state is None for state in states):
        return None
    if "purpose_missing" in states:
        return "purpose_missing"
    if "purpose_vague" in states:
        return "purpose_vague"
    return "purpose_clear"


def _opinion_state_from_record(content: str) -> str | None:
    """只裁决没有实际意见的强负例；其余内容继续交给语义模型。"""

    _application, opinion = _split_consultation_content(content)
    normalized = _clean(_trim_before_signature(opinion))
    if not normalized:
        whole_before_signature = _clean(_trim_before_signature(content))
        whole_residual = re.sub(
            r"[\s,，;；。:：!?！？、()（）\[\]【】]+", "", whole_before_signature
        )
        if _SIGNATURE_RE.search(content) and not whole_residual:
            return "opinion_missing"
        return None
    compact = normalized
    for marker in _CONSULTATION_OPINION_MARKERS:
        compact = compact.replace(marker, "")
    compact = _CONSULTATION_OPINION_HEADING_RE.sub("", compact)
    compact = _ROLE_OPINION_MARKER_RE.sub("", compact)
    compact = re.sub(r"[\s,，;；。:：!?！？、()（）\[\]【】]+", "", compact)
    if not compact or _OPINION_EXECUTION_ONLY_RE.fullmatch(compact):
        return "opinion_missing"
    # 明确记录患者/家属已沟通后的拒绝、暂缓或暂不处理决定，属于可核对的
    # 会诊处置意见；仅有“建议/拟/计划”时仍交给模型，不得提前判清晰。
    decision_clauses = re.split(r"[。；;\n]+", normalized)
    def _is_explicit_decision(clause: str) -> bool:
        decision = re.search(r"(?:暂不处理|拒绝|不同意|暂缓)", clause)
        if decision is None:
            return False
        prefix = clause[max(0, decision.start() - 8) : decision.start()]
        suffix = clause[decision.end() : decision.end() + 8]
        if re.search(r"(?:未|并未|尚未|不曾).{0,4}$", prefix) or re.search(
            r"(?:尚未确定|尚未明确|未确定|不确定)", suffix
        ):
            return False
        return bool(
            re.search(
                r"(?:已|已经|经).{0,8}(?:与患者|与家属).{0,8}沟通",
                clause,
            )
            or re.search(
                r"(?:患者|家属).{0,8}(?:拒绝|不同意|暂不处理|暂缓)"
                r".{0,20}(?:处理|治疗|检查|手术|会诊|干预)",
                clause,
            )
        )

    has_explicit_decision = any(
        _is_explicit_decision(clause) for clause in decision_clauses
    )
    if has_explicit_decision:
        return "opinion_clear"
    assessment_count = len(_EXPLICIT_OPINION_ASSESSMENT_RE.findall(normalized))
    dispositions = set(_EXPLICIT_OPINION_DISPOSITION_RE.findall(normalized))
    if assessment_count >= 2 and len(dispositions) >= 2 and "必要时" not in normalized:
        return "opinion_clear"
    return None


def _programmatic_opinion_reason(
    consultation_rows: Sequence[Mapping[str, Any]],
) -> str | None:
    states = [
        _opinion_state_from_record(_clean(row.get("record_content")))
        for row in consultation_rows
    ]
    if "opinion_missing" in states:
        return "opinion_missing"
    if states and all(state == "opinion_clear" for state in states):
        return "opinion_clear"
    return None


def _opinion_segment_for_review(row: Mapping[str, Any]) -> str:
    """只向022语义判定投影意见正文，不混入申请、执行、标题或签名。"""

    content = _clean(row.get("record_content"))
    _application, opinion = _split_consultation_content(content)
    embedded = _extract_embedded_execution_text(content)
    if embedded and embedded in opinion:
        opinion = opinion[: opinion.rfind(embedded)]
    opinion = _trim_before_signature(opinion)
    for marker in _CONSULTATION_OPINION_MARKERS:
        opinion = opinion.replace(marker, "")
    opinion = _CONSULTATION_OPINION_HEADING_RE.sub("", opinion)
    opinion = _ROLE_OPINION_MARKER_RE.sub("", opinion)
    return _clean(opinion).strip(" ,，;；。:：")


def _opinion_review_context(consultation_rows: Sequence[Mapping[str, Any]]) -> str:
    return "\n".join(
        f"022意见[consultation_record-{index}]={_opinion_segment_for_review(row) or '空'}"
        for index, row in enumerate(consultation_rows, start=1)
    )


def _derive_semantic_opinion_reason(
    payload: Mapping[str, Any],
    consultation_rows: Sequence[Mapping[str, Any]],
) -> str:
    expected_refs = {
        f"consultation_record-{index}"
        for index in range(1, len(consultation_rows) + 1)
    }
    raw_reviews = payload.get("opinion_reviews")
    if not isinstance(raw_reviews, list) or len(raw_reviews) != len(expected_refs):
        return "semantic_low_confidence"
    states_by_ref: dict[str, str] = {}
    for raw in raw_reviews:
        if not isinstance(raw, Mapping):
            return "semantic_low_confidence"
        ref = str(raw.get("consultation_ref") or "").strip()
        state = str(raw.get("opinion_state") or "").strip().lower()
        if (
            ref not in expected_refs
            or ref in states_by_ref
            or state not in {"clear", "vague", "missing"}
            or _confidence_bucket(raw) != "high"
        ):
            return "semantic_low_confidence"
        states_by_ref[ref] = state
    if set(states_by_ref) != expected_refs:
        return "semantic_low_confidence"
    states = set(states_by_ref.values())
    if "missing" in states:
        return "opinion_missing"
    if "vague" in states:
        return "opinion_vague"
    return "opinion_clear"


def _project_row(source_key: str, row: Mapping[str, Any], index: int) -> str:
    title = _clean(row.get("document_title")) or source_key
    record_time = _clean(authoritative_document_time_value(row))
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
        embedded = _extract_embedded_execution_text(content)
        if embedded and embedded in opinion:
            opinion = opinion[: opinion.rfind(embedded)]
            opinion = _EMBEDDED_EXECUTION_HEADING_RE.sub("", opinion).strip(
                " ,，;；。"
            )
        embedded_projection = (
            f"内嵌执行[{source_key}-{index}-embedded-execution]={embedded[:300]}；"
            if embedded
            else ""
        )
        content = (
            f"{embedded_projection}申请段={application or '空'}；"
            f"会诊意见段={opinion or '无法分段'}"
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
        for source_key in _EXECUTION_CANDIDATE_SOURCE_KEYS
        for index, row in enumerate(
            _rows_for_context(source_key, rows_by_source),
            start=1,
        )
        if _is_execution_fact_candidate(source_key, row)
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
    source_key = _clean(row.get("_source_key"))
    value = _row_time_value(source_key, row) if source_key else None
    if not _clean(value):
        for fallback_source in ("", *_EXECUTION_CANDIDATE_SOURCE_KEYS):
            value = _row_time_value(fallback_source, row)
            if _clean(value):
                break
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


def _prompt(
    *,
    selected: Sequence[str],
    context: str,
    opinion_review_context: str,
    course_source_complete: bool,
) -> str:
    requested = "、".join(selected)
    course_state = "完整" if course_source_complete else "不完整"
    return f"""你是泸县0609会诊质量事实判定器。一次只分析本次就诊的会诊文书及后续病程，不得使用常识补写缺失事实。
本次规则：{requested}
后续病程来源状态：{course_state}

严格口径：
- 020：逐张核对会诊是否存在执行记录；明确投影出的“内嵌执行[...]”或后续病程执行均可作为执行记录。即使只笼统写“遵会诊意见”，也算存在执行记录，记录质量由023判断；不得用一条执行记录猜测覆盖多张会诊。
- 021：会诊申请目的是否明确具体诊疗问题；单独只写“请会诊/协助诊治/请指导”属于不明确，但前面已写明具体症状、异常检查、诊断问题或明确术前评估事项时，即使结尾是“协助诊治”也属于目的明确。
- 022：逐张只看“会诊意见段=”。不得借申请段、标题、时间、签名、内嵌执行或其他文书补足意见。任一具体诊断、具体检查项目、药名加剂量/频次/途径或明确调整、明确对象的处置，或明确评估下的暂无特殊处理/同意手术/观察随访，即为 opinion_clear 且 confidence_bucket=high。
- 022 多张合成按最差项：空、只有标题/签名或 missing 优先为 opinion_missing；其次为 opinion_vague；只有全部意见段 clear 才返回 opinion_clear。不得用一张明确意见覆盖另一张空缺或笼统意见。
- 022 对“必要时检查/调整用药/继续治疗/建议处理”等没有具体项目、药物或处置对象的表述判 opinion_vague。
- 023：逐张检查已有后续执行记录是否归纳并写明具体措施；任何只写“遵会诊意见执行”、照抄意见或无具体措施的链接标为 vague；完全没有执行记录返回 execution_record_missing。
- 020/023 只能使用裁剪文书中明确投影的 *-embedded-execution、daily_course_record-* 或 senior_course_record-* 作为执行证据。内嵌执行只能绑定同编号 consultation_ref；后续病程由系统按时间唯一归属，不得让同一个病程重复覆盖多张会诊。病程只写“请某科会诊”仍是申请，不是执行。没有匹配证据的会诊不得编造链接。
- 021 只判断申请段，即 consultation_record 中“病史敬悉/会诊意见/会诊医师意见”之前的内容；申请段已有具体症状、检查、诊断或评估事项即为明确，合并格式不得误判；不得借用会诊医师后写的诊断和建议反推申请目的明确。
- 忽略空模板。每个 results 项和 execution_link 都必须返回 confidence_bucket=high|medium|low；只有 high 可形成确定结论，medium/low 必须保守为不确定。
- 不得把签名、会诊时间缺项串到 021/022/023；只有后续病程来源查询不完整才允许 source_incomplete，临床内容未记录不等于资料来源不完整。

每条规则只能返回下列 reason_code：
020=execution_specific|execution_missing|execution_source_incomplete
021=purpose_clear|purpose_vague|purpose_missing|application_unresolved
022=opinion_clear|opinion_vague|opinion_missing|opinion_unresolved
023=execution_specific_summarized|execution_vague_or_copied|execution_record_missing|execution_time_unresolved|execution_source_incomplete
execution_link.quality=specific|vague

只输出 JSON，不要输出原文、解释或新增字段：
{{"results":{{"LX0609-03-01-01":{{"reason_code":"...","confidence_bucket":"high|medium|low"}},"LX0609-03-01-02":{{"reason_code":"...","confidence_bucket":"high|medium|low"}},"LX0609-03-01-03":{{"reason_code":"...","confidence_bucket":"high|medium|low"}},"LX0609-03-01-04":{{"reason_code":"...","confidence_bucket":"high|medium|low"}}}},"opinion_reviews":[{{"consultation_ref":"consultation_record-1","opinion_state":"clear|vague|missing","confidence_bucket":"high|medium|low"}}],"execution_links":[{{"consultation_ref":"consultation_record-1","execution_ref":"consultation_record-1-embedded-execution或daily_course_record-1或senior_course_record-1","quality":"specific或vague","confidence_bucket":"high|medium|low"}}]}}

022逐文书意见：
{opinion_review_context}

裁剪文书：
{context} """


def _consultation_fact_prompt(*, context: str) -> str:
    """只让模型抽取会诊事实；最终规则状态必须由 Python 合成。"""

    return f"""你是会诊文书事实抽取器。你只识别文书事实和关系，禁止判断或输出LX0609-03-01-01至023的status、reason_code、合规/不合规结论。

输入是一行一个JSON文书对象。必须逐输入ref原样返回且恰好一次，不得遗漏、重复或创造ref，不得输出原文、摘要、解释或合同外字段。

document_facts每项必须是6元素数组：
[ref, roles, episode_ref, application_state, opinion_state, confidence]
- ref原样复制；不要重复source，系统由ref校验source。
- roles是非空数组，枚举只能是 application/opinion/embedded_execution/course_execution/history/planned/template/other/unknown；同一文书同时含申请、正式意见、内嵌执行时必须返回多个roles，不能只选一个。
- episode_ref是同一次会诊episode的稳定锚点，必须选该episode内某个输入consultation_record ref；分行申请与意见共享episode_ref，锚点文书自身也必须属于该episode。history/planned/template/other/unknown以及独立病程执行填null。
- application_state为clear/vague/missing/unknown。只有roles含application时才可非unknown。只评价明确的“会诊目的/请求解决问题/申请事项”字段；病情摘要中的症状、检查异常或诊断不能替代会诊目的。仅有病情摘要加“协助诊治/请指导/请会诊”仍为vague。
- opinion_state为clear/vague/missing/unknown。只有roles含opinion时才可非unknown。单独诊断名不自动clear；必须有明确评估结论，或具体可执行的检查、治疗、药物、复查、处置意见才是clear。无具体对象的“调整用药/继续治疗/必要时检查/建议处理”为vague；正式意见文书意见段空为missing。
- confidence为high/medium/low；角色、episode或状态不能可靠确定时不得high。

角色边界：
- application：已经提出的正式会诊申请；“拟请/计划/必要时请”是planned。
- opinion：已经完成的正式会诊意见；既往提及是history。
- embedded_execution：consultation_record自身明确记载已执行会诊意见。无标题但明确“遵会诊意见执行”仍是执行事实。
- course_execution：daily/senior病程明确记载已执行会诊意见。病程只写申请、计划、建议或既往史不是执行。
- 空白/签名模板为template；无法判定为unknown。不得用关键词正好出现就提升角色。

逐文书强制检查：
- 每份consultation_record都必须分别检查申请段、会诊意见段、执行情况段。一份文书同时存在三段时，roles必须同时包含application、opinion、embedded_execution。
- consultation_record出现“执行情况/会诊意见执行情况/遵会诊意见执行/按会诊意见执行/已落实会诊意见”等已执行表述时，必须返回embedded_execution，并为该episode输出指向自身ref的execution_link；不能因为执行表述简短而省略链接。
- “遵会诊意见执行”本身证明执行记录存在，但quality必须为vague；只有写出实际采取的具体措施、药物、检查、处置或结果时才可specific。

execution_links每项必须是4元素数组：[episode_ref, execution_ref, quality, confidence]。
- episode_ref必须是已含opinion角色的episode锚点；execution_ref必须是roles含embedded_execution或course_execution的输入ref。
- quality只能specific/vague/unknown；具体归纳执行措施为specific，只写“遵会诊意见执行”或照抄意见为vague，无法判断为unknown。
- 同一execution_ref只有在正文分别明确覆盖多个会诊episode时才可高置信关联多个episode；归属含糊必须medium/low，不能猜最近一张会诊。
- 执行不得早于该episode最晚一份意见；时间缺失且非同文书结构化内嵌执行时不得high。

只输出以下紧凑JSON，不得输出对象字段、results/status/reason_code/completeness或任何原文：
{{"document_facts":[["原ref",["application"],"episode_ref或null","clear|vague|missing|unknown","clear|vague|missing|unknown","high|medium|low"]],"execution_links":[["episode_ref","execution_ref","specific|vague|unknown","high|medium|low"]]}}

输入文书：
{context}"""


def _consultation_episode_prompt(*, context: str) -> str:
    """紧凑episode事实合同，避免模型逐文书重复输出大量字段。"""

    return f"""你是会诊文书事实抽取器。只识别文书角色、会诊episode和执行关联；禁止输出LX0609规则状态、reason_code、合规/不合规结论、原文或解释。

输入是一行一个JSON文书对象。ref必须原样复制，不能创造ref。consultation_record才能作为application/opinion并建立episode；daily_course_record和senior_course_record只能是执行、计划、历史提及或非目标。

每个episode输出7元素数组：
[episode_ref, application_refs, opinion_refs, application_state, opinion_state, confidence, execution_links]
- episode_ref必须从本episode的application_refs或opinion_refs中选一个consultation_record ref。
- application_refs只收已经提出的正式会诊申请；“拟请/计划/必要时请”不是申请。病情摘要的症状、检查异常、诊断不能替代明确会诊目的；只有“协助诊治/请指导/请会诊”为vague，目的字段空为missing，目的明确具体才clear。
- opinion_refs只收已经完成的正式会诊意见；既往提及不是意见。单独诊断名不自动clear；有明确评估结论或具体可执行检查、治疗、药物、复查、处置才clear。无具体对象的“调整用药/继续治疗/必要时检查/建议处理”为vague，正式意见段空为missing。
- 分行申请和意见属于同一次会诊时放进同一episode。一份consultation_record同时含申请和意见时可同时出现在两个refs数组。
- application_state/opinion_state只能clear/vague/missing/unknown；confidence只能high/medium/low。episode关系不可靠不得high。
- execution_links每项为[execution_ref, quality, confidence]。明确已执行/落实会诊意见才是执行；拟执行、建议、历史回顾不是执行。只写“遵会诊意见执行”证明执行记录存在但quality=vague；写出实际采取的药物、检查、治疗或处置才specific；无法判断为unknown。
- 同一consultation_record含“执行情况/会诊意见执行情况/遵会诊意见执行/按会诊意见执行/已落实会诊意见”时，必须把自身ref加入对应episode的execution_links，不能因内容简短而省略。
- 同一病程明确分别落实多个episode时可以关联多个；归属含糊必须medium/low，不能猜最近一次。执行时间不得早于对应意见。

没有进入episode或execution_links的ref，必须恰好放入以下之一：
- non_target_refs：明确是history/planned/template/other；
- unresolved_refs：角色或关联无法可靠判断。
不要因为输出很长而省略ref；数组中只写ref和受控代码。

只输出紧凑JSON：
{{"episodes":[["episode_ref",["application_ref"],["opinion_ref"],"clear|vague|missing|unknown","clear|vague|missing|unknown","high|medium|low",[["execution_ref","specific|vague|unknown","high|medium|low"]]]],"non_target_refs":["ref"],"unresolved_refs":["ref"]}}

输入文书：
{context}"""


def _consultation_rule_fact_prompt(
    *,
    selected: Sequence[str],
    context: str,
) -> str:
    requested = ",".join(selected)
    fact_templates = {
        "LX0609-03-01-01": "execution_all_present|execution_missing|no_completed_opinion|unknown",
        "LX0609-03-01-02": "purpose_clear|purpose_vague|purpose_missing|no_application|unknown",
        "LX0609-03-01-03": "opinion_clear|opinion_vague|opinion_missing|no_completed_opinion|unknown",
        "LX0609-03-01-04": "execution_specific|execution_vague|execution_absent|unknown",
    }
    schema = ",".join(
        f'"{rule_id}":{{"fact":"{fact_templates[rule_id]}","evidence_refs":["输入ref"],"confidence":"high|medium|low"}}'
        for rule_id in selected
    )
    return f"""你是会诊病历事实核对器。本次只核对：{requested}。不要输出合规/不合规、status、reason_code、患者原文或解释；Python会依据事实代码生成最终质控结果。

输入是一行一个本次就诊文书JSON。先在内部逐行识别row_role：blank_template/application_only/application_opinion/history_or_plan/course_execution_candidate；不要输出row_role。空模板不参与021，application_only只参与021，不得因此让020/022/023形成缺陷。不得按表中一行等于一次会诊。

事实口径：
- 020：只核对application_opinion，即已经形成正式意见的会诊。每次都有后续或同文书执行记录=execution_all_present；任一次明确没有执行=execution_missing；没有已完成意见=no_completed_opinion；存在可能相关的后续动作但多会诊无法唯一归属=unknown。“遵会诊意见执行”虽然空泛，但证明020执行存在。
- 021：评价application_only和application_opinion，不要求固定“会诊目的”标题。申请段明确提出当前具体临床问题并请求受邀专科判断或处理可判purpose_clear；纯病情罗列而没有请求不能clear；只有“协助诊治/请指导/请会诊”等泛化请求=purpose_vague；申请内容缺失=purpose_missing；没有正式申请=no_application；角色无法确定=unknown。
- 022：只看application_opinion。所有完成意见都有明确评估结论或具体可执行检查、治疗、药物、复查、处置=opinion_clear；任一无具体对象的泛化意见或只有诊断名=opinion_vague；任一完成意见段为空=opinion_missing；没有已完成意见=no_completed_opinion；角色无法确定=unknown。
- 023：只评价已经存在的执行记录。任一仅写“遵会诊意见执行”、照抄意见或未写具体措施=execution_vague；后续病程明确记录具体剂量调整、复查结果及据此处置闭环可判execution_specific，不能只看同一会诊文书中的泛句；确实没有执行记录=execution_absent；执行角色或质量无法确定=unknown。

边界示例：
- 4份完成意见只有3份能找到执行，必须是execution_missing，不能因为多数已执行而输出execution_all_present。
- 同一意见中同时存在泛化措辞和具体可执行建议，应按完整意见整体判断为明确；只有整段都缺少具体对象或措施时才是opinion_vague。

历史提及、拟请/计划会诊、拒绝或未行会诊、空模板不进入上述真实会诊集合。多条申请和意见可以属于同一次会诊；一条病程也可以明确覆盖多次会诊。020的关联不确定不能掩盖023已经明确的空泛执行缺陷。

每条fact必须使用该规则允许的代码。confidence只有证据和角色都可靠时才high。evidence_refs只能原样引用输入ref：021/022只能引用consultation_record；020/023可引用consultation、病程、医嘱、检查、检验或手术候选ref。确定事实必须非空，并列出所有决定该全称事实的目标consultation refs；020/023还要列出决定性的执行refs。no_application/no_completed_opinion必须列出已审阅并据以排除目标的全部consultation refs。unknown可给相关ref或空数组。不要返回未请求规则或额外字段。

只输出JSON：
{{"facts":{{{schema}}}}}

输入文书：
{context}"""


def _consultation_semantic_prompt(*, context: str) -> str:
    return f"""你是会诊申请与意见事实核对器。输入只包含本次就诊的consultation_record；一行不等于一次会诊。先区分正式申请、已完成意见、既往回顾、拟请会诊和空模板。

对每个输入ref必须恰好返回一行，顺序不限，不得遗漏。每行五项：
[ref, roles, application_state, opinion_state, confidence]
- roles为application/opinion/history/planned/template/other/unknown，可同时有application和opinion；空模板只标template；只有正式申请尚无意见只标application。
- application_state只在application角色上评价。无需固定“会诊目的”标题：正式申请中已经写明与受邀专科相关的具体当前临床问题、症状、检查异常或待处理风险，即使没有再次出现“请判断/请处理”字样也必须=clear；不要因为结尾只有“请会诊/协助诊治”就把前面的具体问题降为vague。只有去掉“请会诊/协助诊治”等请求词后完全没有具体当前问题，才=vague；申请内容空=missing。
- opinion_state只在opinion角色上评价。有明确评估结论或具体检查、药物、剂量、治疗、复查、处置=clear；同一意见中同时存在泛化措辞和具体可执行建议，按完整意见整体判clear；整段只有诊断名、同意/余同贵科、必要时处理等=vague；意见段空=missing。
- 非对应角色的state填unknown。confidence仅high/medium/low，表示分类是否可靠而不是文书质量好坏；明确的vague或missing也必须是high，不能因为结论是缺陷就降低confidence。只有角色或边界确实无法可靠判断才用unknown/medium或low。

只输出紧凑JSON，不得输出状态、解释或原文：
{{"documents":[["输入ref",["application|opinion|history|planned|template|other|unknown"],"clear|vague|missing|unknown","clear|vague|missing|unknown","high|medium|low"]]}}

输入文书：
{context}"""


def _consultation_execution_fact_prompt(*, context: str, structure: str) -> str:
    return f"""你是会诊意见执行事实核对器。本次只核对LX0609-03-01-01和LX0609-03-01-04。输入包含本次就诊会诊文书及后续候选执行事件，包括病程、医嘱、检查、检验和手术记录。不要输出客户状态、解释或原文。

先内部识别已完成正式意见和实际执行记录，但不要输出episode图：
- 020：所有已完成意见都有可唯一关联的同文书或后续执行=execution_all_present；任一完成意见没有任何执行候选=execution_missing；没有已完成意见=no_completed_opinion；存在可能相关动作但多次会诊下无法唯一归属=unknown。4份完成意见只有3份能找到执行，必须execution_missing。“遵会诊意见执行”虽空泛但证明执行存在。
- 023：所有已有执行记录都具体写明实际药物/剂量、检查、治疗、复查、处置、手术或拒绝决定=execution_specific；任一明确仅写“遵会诊意见执行”、照抄意见、泛称治疗/考虑中=execution_vague，且这种明确的空泛缺陷confidence应为high；确实没有执行记录=execution_absent；角色或质量不可靠=unknown。后续病程、医嘱、检查、检验或手术中的具体执行事实可以补足同文书泛句。

evidence_refs只能原样引用输入ref。确定事实必须列出所有决定性会诊ref及执行ref；unknown可为空。confidence仅high/medium/low。
Python已提供安全结构摘要，只表示行数和同文书执行候选，不代表这些行一定是正式意见。必须逐份核对，不能用多数票：
{structure}
- same_document_vague_candidate_refs中的每一项都必须检查是否被后续病程、医嘱、检查、检验或手术中的具体执行补足；只要有一项未被明确补足，023必须execution_vague，不能因其他执行具体而输出execution_specific。
- 某完成意见缺少同文书执行时，若execution_candidate_refs中存在可能相关动作但多次会诊下不能唯一归属，020必须unknown；只有确认没有任何候选执行才是execution_missing。
只输出：
{{"facts":{{"LX0609-03-01-01":{{"fact":"execution_all_present|execution_missing|no_completed_opinion|unknown","evidence_refs":["输入ref"],"confidence":"high|medium|low"}},"LX0609-03-01-04":{{"fact":"execution_specific|execution_vague|execution_absent|unknown","evidence_refs":["输入ref"],"confidence":"high|medium|low"}}}}}}

输入文书：
{context}"""


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


def _parse_consultation_fact_payload(
    response: Mapping[str, Any],
) -> Mapping[str, Any]:
    payload = _parse_payload(response)
    if not isinstance(payload, Mapping):
        raise FactContractError("consultation fact payload is not valid JSON")
    return payload


def _usage(response: Mapping[str, Any]) -> tuple[int, int, int, float]:
    usage = response.get("usage")
    usage = usage if isinstance(usage, Mapping) else {}
    prompt = int(usage.get("prompt_tokens") or 0)
    completion = int(usage.get("completion_tokens") or 0)
    total = int(usage.get("total_tokens") or prompt + completion)
    return prompt, completion, total, float(response.get("_api_time") or 0.0)


def _confidence_bucket(raw: Mapping[str, Any] | None) -> str:
    value = str((raw or {}).get("confidence_bucket") or "").strip().lower()
    return value if value in _CONFIDENCE_VALUE else "low"


def _result_confidence(payload: Mapping[str, Any] | None, rule_id: str) -> str:
    results = payload.get("results") if isinstance(payload, Mapping) else None
    raw = results.get(rule_id) if isinstance(results, Mapping) else None
    return _confidence_bucket(raw if isinstance(raw, Mapping) else None)


_SEMANTIC_EXECUTION_REASONS = {
    "LX0609-03-01-01": frozenset(
        {"execution_specific", "execution_missing", "execution_source_incomplete"}
    ),
    "LX0609-03-01-04": frozenset(
        {"execution_specific_summarized", "execution_vague_or_copied", "execution_record_missing", "execution_time_unresolved", "execution_source_incomplete"}
    ),
}


def _has_valid_high_semantic_result(payload: Mapping[str, Any] | None, rule_id: str) -> bool:
    results = payload.get("results") if isinstance(payload, Mapping) else None
    raw = results.get(rule_id) if isinstance(results, Mapping) else None
    return bool(
        isinstance(raw, Mapping)
        and str(raw.get("reason_code") or "").strip() in _SEMANTIC_EXECUTION_REASONS[rule_id]
        and _confidence_bucket(raw) == "high"
    )


def _derive_execution_reasons(
    *,
    payload: Mapping[str, Any] | None,
    rows_by_source: Mapping[str, Sequence[Mapping[str, Any]]],
    course_source_complete: bool,
) -> tuple[str, str, str, str]:
    rows_by_ref = _rows_by_ref(rows_by_source)
    reconsultation_by_ref = _reconsultation_execution_by_ref(rows_by_source)
    reconsultation_evidence_rows = {
        evidence_row_ref
        for _target_ref, evidence_row_ref in reconsultation_by_ref.values()
    }
    consultation_refs = _consultation_refs_for_execution(
        rows_by_source
    ) - reconsultation_evidence_rows
    course_refs = _course_refs(rows_by_source)
    embedded_by_ref = _embedded_execution_by_ref(rows_by_source)
    embedded_consultation_refs = {
        consultation_ref
        for consultation_ref, _content in embedded_by_ref.values()
        if consultation_ref not in reconsultation_evidence_rows
    }
    embedded_020_coverage_refs = (
        _embedded_execution_020_coverage_refs(rows_by_source)
        - reconsultation_evidence_rows
    )
    deterministic_embedded_quality = {
        execution_ref: quality
        for execution_ref, (consultation_ref, content) in embedded_by_ref.items()
        if consultation_ref not in reconsultation_evidence_rows
        if (quality := _embedded_execution_quality(content)) is not None
    }

    confidence_020 = _result_confidence(payload, "LX0609-03-01-01")
    confidence_023 = _result_confidence(payload, "LX0609-03-01-04")
    semantic_result_020_valid = _has_valid_high_semantic_result(payload, "LX0609-03-01-01")
    semantic_result_023_valid = _has_valid_high_semantic_result(payload, "LX0609-03-01-04")
    deterministic_consultation_refs = {
        embedded_by_ref[execution_ref][0]
        for execution_ref in deterministic_embedded_quality
    } | {
        consultation_ref
        for consultation_ref, _evidence_row_ref in reconsultation_by_ref.values()
    }
    complete_deterministic_quality = bool(consultation_refs) and (
        consultation_refs <= deterministic_consultation_refs
    )
    deterministic_020_refs = embedded_020_coverage_refs | {
        consultation_ref
        for consultation_ref, _evidence_row_ref in reconsultation_by_ref.values()
    }
    complete_deterministic_020 = bool(consultation_refs) and (
        consultation_refs <= deterministic_020_refs
    )
    links = payload.get("execution_links") if isinstance(payload, Mapping) else None
    if not isinstance(links, list):
        if complete_deterministic_quality:
            reason_023 = (
                "execution_vague_or_copied"
                if "vague" in deterministic_embedded_quality.values()
                else "execution_specific_summarized"
            )
            reason_020 = (
                "execution_specific"
                if complete_deterministic_020
                else "execution_missing" if course_source_complete else "execution_source_incomplete"
            )
            return reason_020, reason_023, "high", "high"
        reason_020 = (
            "execution_specific"
            if consultation_refs
            and consultation_refs <= embedded_020_coverage_refs
            else "execution_source_incomplete"
        )
        return reason_020, "execution_time_unresolved", confidence_020, confidence_023
    valid_qualities_by_consultation: dict[str, list[str]] = {}
    for execution_ref, quality in deterministic_embedded_quality.items():
        consultation_ref, _content = embedded_by_ref[execution_ref]
        valid_qualities_by_consultation.setdefault(consultation_ref, []).append(
            quality
        )
    for consultation_ref, _evidence_row_ref in reconsultation_by_ref.values():
        valid_qualities_by_consultation.setdefault(consultation_ref, []).append(
            "specific"
        )
    course_qualities_by_ref: dict[str, list[str]] = {}
    course_claims_by_ref: dict[str, set[str]] = {}
    unresolved = False
    for raw_link in links:
        if not isinstance(raw_link, Mapping):
            unresolved = True
            continue
        consultation_ref = str(raw_link.get("consultation_ref") or "").strip()
        execution_ref = str(
            raw_link.get("execution_ref") or raw_link.get("course_ref") or ""
        ).strip()
        quality = str(raw_link.get("quality") or "").strip()
        if quality not in {"specific", "vague"}:
            unresolved = True
            continue
        link_is_high_confidence = _confidence_bucket(raw_link) == "high"
        if execution_ref in embedded_by_ref:
            bound_consultation_ref, _content = embedded_by_ref[execution_ref]
            if bound_consultation_ref in reconsultation_evidence_rows:
                # 完整复会诊是前次会诊的执行证据，不再把其自身作为待覆盖会诊。
                continue
            if consultation_ref != bound_consultation_ref:
                unresolved = True
                continue
            if execution_ref in deterministic_embedded_quality:
                # 确定性段级边界优先，避免模型把具体执行误标为空泛，或反向放宽。
                continue
            if not link_is_high_confidence:
                unresolved = True
                continue
            valid_qualities_by_consultation.setdefault(
                bound_consultation_ref, []
            ).append(quality)
            continue
        if execution_ref not in course_refs:
            # 未知引用不能静默折叠为临床缺失。
            unresolved = True
            continue
        if consultation_ref not in consultation_refs:
            unresolved = True
            continue
        course_time = _record_datetime(rows_by_ref.get(execution_ref))
        consultation_time = _record_datetime(rows_by_ref.get(consultation_ref))
        if (
            course_time is None
            or consultation_time is None
            or course_time <= consultation_time
        ):
            unresolved = True
            continue
        if not link_is_high_confidence:
            unresolved = True
            continue
        course_qualities_by_ref.setdefault(execution_ref, []).append(quality)
        course_claims_by_ref.setdefault(execution_ref, set()).add(consultation_ref)

    # 一个病程执行记录只能被一张会诊声明；保留模型明确关联，但严格校验引用和时序。
    for course_ref, qualities in course_qualities_by_ref.items():
        claims = course_claims_by_ref.get(course_ref, set())
        if len(claims) != 1:
            unresolved = True
            continue
        course_time = _record_datetime(rows_by_ref.get(course_ref))
        consultation_ref = next(iter(claims))
        consultation_time = _record_datetime(rows_by_ref.get(consultation_ref))
        if (
            course_time is None
            or consultation_time is None
            or course_time <= consultation_time
        ):
            unresolved = True
            continue
        quality = "vague" if "vague" in qualities else "specific"
        valid_qualities_by_consultation.setdefault(consultation_ref, []).append(
            quality
        )

    # 后续复会诊形成了完整、客观且据结果调整的闭环时，覆盖此前仅有的空泛执行记载。
    # 该覆盖只针对已由严格确定性边界唯一绑定的前次会诊，不接受模型扩张。
    for consultation_ref, _evidence_row_ref in reconsultation_by_ref.values():
        valid_qualities_by_consultation[consultation_ref] = ["specific"]

    covered_consultation_refs = (
        embedded_020_coverage_refs
        | (set(valid_qualities_by_consultation) - embedded_consultation_refs)
    )
    all_consultations_covered = bool(consultation_refs) and (
        consultation_refs <= covered_consultation_refs
    )
    if complete_deterministic_020 or all_consultations_covered:
        reason_020 = "execution_specific"
    elif not course_source_complete:
        reason_020 = "execution_source_incomplete"
    elif unresolved:
        reason_020 = "semantic_low_confidence"
    else:
        reason_020 = "execution_missing"

    has_vague = any(
        quality == "vague"
        for qualities in valid_qualities_by_consultation.values()
        for quality in qualities
    )
    all_consultations_specific = bool(consultation_refs) and (
        consultation_refs <= set(valid_qualities_by_consultation)
        and all(
            set(valid_qualities_by_consultation.get(consultation_ref) or ())
            == {"specific"}
            for consultation_ref in consultation_refs
        )
    )
    embedded_without_quality = embedded_consultation_refs - set(
        valid_qualities_by_consultation
    )
    deterministic_has_vague = "vague" in deterministic_embedded_quality.values()
    if complete_deterministic_quality:
        reason_023 = (
            "execution_vague_or_copied"
            if deterministic_has_vague
            else "execution_specific_summarized"
        )
    elif has_vague:
        reason_023 = "execution_vague_or_copied"
    elif all_consultations_specific:
        reason_023 = "execution_specific_summarized"
    elif not course_source_complete and not (
        consultation_refs <= embedded_consultation_refs
    ):
        reason_023 = "execution_source_incomplete"
    elif unresolved:
        reason_023 = "semantic_low_confidence"
    elif embedded_without_quality:
        reason_023 = "execution_time_unresolved"
    elif not covered_consultation_refs:
        reason_023 = "execution_record_missing"
    else:
        reason_023 = "execution_specific_summarized"

    if (
        reason_020 != "execution_source_incomplete"
        and not complete_deterministic_020
        and not semantic_result_020_valid
    ):
        reason_020 = "semantic_low_confidence"
    if (
        reason_023 != "execution_source_incomplete"
        and not complete_deterministic_quality
        and not semantic_result_023_valid
    ):
        reason_023 = "semantic_low_confidence"

    if reason_020 in {"execution_specific", "execution_missing"}:
        confidence_020 = "high"
    elif reason_020 == "semantic_low_confidence":
        confidence_020 = "low"
    if reason_023 in {
        "execution_specific_summarized",
        "execution_vague_or_copied",
        "execution_record_missing",
    }:
        confidence_023 = "high"
    elif reason_023 == "semantic_low_confidence":
        confidence_023 = "low"
    return reason_020, reason_023, confidence_020, confidence_023


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


def _typed_decision_from_outcome(
    *,
    outcome: _ConsultationRuleOutcome,
    snapshot: Luxian0609EvidenceSnapshot,
) -> RuleDecision:
    """由会诊内核 outcome 直接生成决策，不经过客户结果 DTO。"""

    source_keys = frozenset(_DECISION_SOURCE_KEYS_BY_RULE[outcome.rule_id])
    refs = tuple(
        observation.snapshot_ref.removeprefix("sha256:")
        for observation in snapshot.observations
        if observation.source_key in source_keys
    )
    status = outcome.status
    if status in {"compliant", "non_compliant", "not_applicable"} and not refs:
        raise ValueError("typed consultation decision requires evidence refs")
    if status == "compliant":
        dimensions = (
            ApplicabilityState.APPLICABLE,
            EvidenceState.SUFFICIENT,
            QcDirection.SATISFIED,
            "requirement_satisfied",
        )
    elif status == "non_compliant":
        dimensions = (
            ApplicabilityState.APPLICABLE,
            EvidenceState.SUFFICIENT,
            QcDirection.DEFECT,
            "requirement_violated",
        )
    elif status == "not_applicable":
        dimensions = (
            ApplicabilityState.NOT_APPLICABLE,
            EvidenceState.SUFFICIENT,
            QcDirection.UNKNOWN,
            "trigger_absent_complete",
        )
    elif status == "data_gap":
        reason_code = (
            "source_truncated"
            if "truncated" in outcome.reason_code
            else (
                "source_unavailable"
                if "source_unavailable" in outcome.reason_code
                else "required_field_missing"
            )
        )
        dimensions = (
            ApplicabilityState.UNKNOWN,
            EvidenceState.DATA_GAP,
            QcDirection.UNKNOWN,
            reason_code,
        )
    elif status == "evaluation_unknown":
        dimensions = (
            ApplicabilityState.APPLICABLE,
            EvidenceState.CONFLICT,
            QcDirection.UNKNOWN,
            "semantic_low_confidence",
        )
    elif status == "technical_error":
        reason_code = (
            outcome.reason_code
            if outcome.reason_code in {"source_query_error", "snapshot_mismatch"}
            else "executor_exception"
        )
        dimensions = (
            ApplicabilityState.ERROR,
            EvidenceState.TECHNICAL_ERROR,
            QcDirection.UNKNOWN,
            reason_code,
        )
    else:
        raise ValueError("unsupported consultation final state")
    applicability, evidence_state, qc_direction, reason_code = dimensions
    return RuleDecision(
        rule_id=outcome.rule_id,
        snapshot_hash=snapshot.snapshot_hash,
        applicability=applicability,
        evidence_state=evidence_state,
        qc_direction=qc_direction,
        reason_code=reason_code,
        fact_refs=refs,
        evaluator_version=_TYPED_EVALUATOR_VERSION,
        confidence=_CONFIDENCE_VALUE.get(outcome.confidence_bucket),
    )


def _terminal_outcomes(
    selected: Sequence[str], status: str, reason_code: str
) -> tuple[_ConsultationRuleOutcome, ...]:
    return tuple(
        _ConsultationRuleOutcome(rule_id, status, reason_code, "program")
        for rule_id in selected
    )


def _finalize_outcomes(
    *,
    outcomes: Sequence[_ConsultationRuleOutcome],
    selected: tuple[str, ...],
    typed_requested: frozenset[str],
    snapshot: Luxian0609EvidenceSnapshot | None,
    typed_terminal_blockers: Mapping[str, _ConsultationRuleOutcome] | None = None,
    typed_conditional_blockers: Mapping[str, _ConsultationRuleOutcome] | None = None,
    llm_call_count: int = 0,
    prompt_tokens: int = 0,
    completion_tokens: int = 0,
    total_tokens: int = 0,
    api_time: float = 0.0,
) -> NativeConsultationExecutionResult:
    terminal_blockers = typed_terminal_blockers or {}
    conditional_blockers = typed_conditional_blockers or {}
    results: list[dict[str, Any]] = []
    decisions: list[RuleDecision] = []
    for raw_outcome in outcomes:
        outcome = terminal_blockers.get(raw_outcome.rule_id, raw_outcome)
        if (
            outcome is raw_outcome
            and raw_outcome.status == "data_gap"
            and raw_outcome.rule_id in conditional_blockers
        ):
            outcome = conditional_blockers[raw_outcome.rule_id]
        if outcome.rule_id in typed_requested:
            assert snapshot is not None
            decisions.append(
                _typed_decision_from_outcome(outcome=outcome, snapshot=snapshot)
            )
        else:
            results.append(
                _result(
                    outcome.rule_id,
                    outcome.status,
                    outcome.reason_code,
                    executor_type=outcome.executor_type,
                )
            )
    return NativeConsultationExecutionResult(
        results=tuple(results),
        planned_rule_ids=selected,
        decisions=tuple(decisions),
        llm_call_count=llm_call_count,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        total_tokens=total_tokens,
        api_time=api_time,
    )


def _typed_source_blockers(
    *,
    selected: tuple[str, ...],
    typed_requested: frozenset[str],
    snapshot: Luxian0609EvidenceSnapshot,
) -> tuple[
    dict[str, _ConsultationRuleOutcome],
    dict[str, _ConsultationRuleOutcome],
]:
    observations = {item.source_key: item for item in snapshot.observations}
    terminal: dict[str, _ConsultationRuleOutcome] = {}
    conditional: dict[str, _ConsultationRuleOutcome] = {}
    for rule_id in selected:
        if rule_id not in typed_requested:
            continue
        for source_key in _DECISION_SOURCE_KEYS_BY_RULE[rule_id]:
            observation = observations.get(source_key)
            if observation is None:
                blocker = _ConsultationRuleOutcome(
                    rule_id, "technical_error", "snapshot_mismatch", "program"
                )
            elif observation.query_state.value == "error":
                blocker = _ConsultationRuleOutcome(
                    rule_id, "technical_error", "source_query_error", "program"
                )
            elif observation.query_state.value == "unavailable":
                blocker = _ConsultationRuleOutcome(
                    rule_id, "data_gap", "consultation_source_unavailable", "program"
                )
            elif observation.completeness.value == "truncated":
                blocker = _ConsultationRuleOutcome(
                    rule_id, "data_gap", "consultation_source_truncated", "program"
                )
            else:
                continue
            # consultation_record 是四条规则的必要来源；两个病程来源仅在
            # 020/023 无法由会诊文书内嵌执行闭环直接判定时才是终局阻塞。
            if source_key == "consultation_record":
                terminal[rule_id] = blocker
                break
            conditional.setdefault(rule_id, blocker)
    return terminal, conditional


async def execute_luxian_0609_native_consultation_rules(
    *,
    rule_ids: Sequence[str],
    institute_id: str,
    patient_id: str,
    visit_id: str,
    source_schema: str | None,
    llm_client: ConsultationLLMClient | None,
    evidence_materials: Luxian0609EvidenceMaterialStore | None = None,
    evidence_snapshot: Luxian0609EvidenceSnapshot | None = None,
    decision_rule_ids: Sequence[str] = (),
) -> NativeConsultationExecutionResult:
    requested = {str(rule_id or "").strip().upper() for rule_id in rule_ids}
    selected = tuple(rule_id for rule_id in CONSULTATION_RULE_IDS if rule_id in requested)
    typed_requested = frozenset(
        str(rule_id or "").strip().upper() for rule_id in decision_rule_ids
    )
    if (
        not typed_requested.issubset(_TYPED_DECISION_RULE_IDS)
        or not typed_requested.issubset(set(selected))
    ):
        raise ValueError("unsupported typed consultation rule scope")
    if typed_requested and (
        type(evidence_snapshot) is not Luxian0609EvidenceSnapshot
        or type(evidence_materials) is not Luxian0609EvidenceMaterialStore
        or evidence_materials.snapshot_hash != evidence_snapshot.snapshot_hash
    ):
        raise ValueError("typed consultation rules require one evidence session")
    if not selected:
        return NativeConsultationExecutionResult((), ())
    typed_terminal_blockers, typed_conditional_blockers = (
        _typed_source_blockers(
            selected=selected,
            typed_requested=typed_requested,
            snapshot=evidence_snapshot,
        )
        if typed_requested and evidence_snapshot is not None
        else ({}, {})
    )

    def finalize(
        outcomes: Sequence[_ConsultationRuleOutcome],
        *,
        llm_call_count: int = 0,
        prompt_tokens: int = 0,
        completion_tokens: int = 0,
        total_tokens: int = 0,
        api_time: float = 0.0,
    ) -> NativeConsultationExecutionResult:
        return _finalize_outcomes(
            outcomes=outcomes,
            selected=selected,
            typed_requested=typed_requested,
            snapshot=evidence_snapshot,
            typed_terminal_blockers=typed_terminal_blockers,
            typed_conditional_blockers=typed_conditional_blockers,
            llm_call_count=llm_call_count,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
            api_time=api_time,
        )

    if not all(isinstance(value, str) and value.strip() for value in (institute_id, patient_id, visit_id)):
        return finalize(
            _terminal_outcomes(
                selected, "technical_error", "native_coordinates_unavailable"
            )
        )

    rows_by_source: dict[str, list[dict[str, Any]]] = {}
    source_complete = {source_key: False for source_key in _SOURCE_KEYS}
    source_issues: dict[str, tuple[str, str]] = {}
    for source_key in _SOURCE_KEYS:
        try:
            if evidence_materials is not None:
                rows_by_source[source_key] = [
                    dict(row) for row in evidence_materials.rows(source_key)
                ]
                source_complete[source_key] = evidence_materials.permits_absence(source_key)
            else:
                rows_by_source[source_key] = read_luxian_0609_native_source_rows(
                    source_key=source_key,
                    institute_id=institute_id,
                    patient_id=patient_id,
                    visit_id=visit_id,
                    source_schema=source_schema,
                )
                # 旧直读接口没有与本次结果绑定的完整性证明，不能据“未发现”判缺陷。
                source_complete[source_key] = False
        except (EvidenceMaterialTruncated, SourceEvidenceTruncated):
            rows_by_source[source_key] = []
            source_issues[source_key] = (
                "data_gap",
                "consultation_source_truncated",
            )
        except (EvidenceMaterialUnavailable, SourceEvidenceUnavailable):
            rows_by_source[source_key] = []
            source_issues[source_key] = (
                "data_gap",
                "consultation_source_unavailable",
            )
        except SourceEvidenceQueryError:
            rows_by_source[source_key] = []
            source_issues[source_key] = (
                "technical_error",
                "source_query_error",
            )
        except Exception:
            rows_by_source[source_key] = []
            source_issues[source_key] = (
                "technical_error",
                "source_query_error",
            )

    consultation_issue = source_issues.get("consultation_record")
    if consultation_issue is not None:
        status, reason_code = consultation_issue
        return finalize(_terminal_outcomes(selected, status, reason_code))

    consultation_rows = rows_by_source["consultation_record"]
    has_course_candidates = any(
        _is_course_fact_candidate(row)
        for source_key in ("daily_course_record", "senior_course_record")
        for row in rows_by_source[source_key]
    )
    if not consultation_rows:
        if source_complete["consultation_record"] and not has_course_candidates:
            return finalize(
                _terminal_outcomes(
                    selected,
                    "not_applicable",
                    "consultation_absent",
                )
            )
        if not source_complete["consultation_record"]:
            return finalize(
                _terminal_outcomes(
                    selected,
                    "data_gap",
                    "consultation_source_incomplete",
                )
            )

    if llm_client is None:
        return finalize(
            _terminal_outcomes(
                selected,
                "data_gap",
                "consultation_llm_unavailable",
            )
        )

    semantic_rule_ids = tuple(
        rule_id for rule_id in selected if rule_id in {"LX0609-03-01-02", "LX0609-03-01-03"}
    )
    execution_rule_ids = tuple(
        rule_id for rule_id in selected if rule_id in {"LX0609-03-01-01", "LX0609-03-01-04"}
    )
    semantic_projection = _build_fact_projection(
        {
            "consultation_record": consultation_rows,
            "daily_course_record": (),
            "senior_course_record": (),
        }
    )
    execution_projection = _build_fact_projection(rows_by_source)

    outcomes_by_rule: dict[str, _ConsultationRuleOutcome] = {}
    call_specs: list[tuple[str, tuple[str, ...], _ConsultationFactProjection, str]] = []
    if semantic_rule_ids:
        if semantic_projection.overflow:
            outcomes_by_rule.update(
                {
                    item.rule_id: item
                    for item in _terminal_outcomes(
                        semantic_rule_ids,
                        "evaluation_unknown",
                        "consultation_context_overflow",
                    )
                }
            )
        else:
            call_specs.append(
                (
                    "semantic",
                    semantic_rule_ids,
                    semantic_projection,
                    _consultation_semantic_prompt(context=semantic_projection.context),
                )
            )
    if execution_rule_ids:
        if execution_projection.overflow:
            outcomes_by_rule.update(
                {
                    item.rule_id: item
                    for item in _terminal_outcomes(
                        execution_rule_ids,
                        "evaluation_unknown",
                        "consultation_context_overflow",
                    )
                }
            )
        else:
            call_specs.append(
                (
                    "execution",
                    execution_rule_ids,
                    execution_projection,
                    _consultation_execution_fact_prompt(
                        context=execution_projection.context,
                        structure=_execution_structure_context(
                            consultation_rows, execution_projection
                        ),
                    ),
                )
            )

    responses = await asyncio.gather(
        *(llm_client.generate(spec[3]) for spec in call_specs),
        return_exceptions=True,
    )
    prompt_tokens = completion_tokens = total_tokens = 0
    api_time = 0.0
    semantic_opinion_refs: frozenset[str] = frozenset()
    execution_all_coverage_unproven = False
    execution_missing_has_unresolved_candidates = False
    llm_call_count = len(call_specs)
    for (kind, rule_ids, fact_projection, prompt_text), response in zip(
        call_specs, responses
    ):
        if isinstance(response, BaseException):
            outcomes_by_rule.update(
                {
                    rule_id: _ConsultationRuleOutcome(
                        rule_id,
                        "technical_error",
                        "consultation_llm_failure",
                        "llm",
                    )
                    for rule_id in rule_ids
                }
            )
            continue
        usage = _usage(response)
        prompt_tokens += usage[0]
        completion_tokens += usage[1]
        total_tokens += usage[2]
        api_time += usage[3]
        parse_succeeded = False
        for attempt in range(2):
            try:
                payload = _restore_projection_refs(
                    _parse_consultation_fact_payload(response),
                    fact_projection,
                )
                if kind == "semantic":
                    semantic_facts = validate_consultation_semantic_payload(
                        payload,
                        fact_projection.documents,
                    )
                    semantic_opinion_refs = frozenset(
                        fact.ref
                        for fact in semantic_facts.facts
                        if "opinion" in fact.roles
                    )
                    states = synthesize_consultation_semantic_states(
                        semantic_facts,
                        consultation_source_complete=source_complete[
                            "consultation_record"
                        ],
                    )
                else:
                    execution_facts = validate_consultation_rule_fact_payload(
                        payload,
                        fact_projection.documents,
                        selected_rule_ids=rule_ids,
                    )
                    execution_020 = execution_facts.get("LX0609-03-01-01")
                    execution_all_coverage_unproven = bool(
                        execution_020 is not None
                        and execution_020.fact == "execution_all_present"
                        and semantic_opinion_refs
                        and not semantic_opinion_refs.issubset(
                            execution_020.evidence_refs
                        )
                    )
                    execution_missing_has_unresolved_candidates = bool(
                        execution_020 is not None
                        and execution_020.fact == "execution_missing"
                        and any(
                            document.source
                            in {"daily_course_record", "senior_course_record"}
                            for document in fact_projection.documents
                        )
                    )
                    states = synthesize_consultation_rule_fact_states(
                        execution_facts,
                        consultation_source_complete=source_complete[
                            "consultation_record"
                        ],
                        course_source_complete=all(
                            source_complete[source_key]
                            for source_key in _EXECUTION_CANDIDATE_SOURCE_KEYS
                        ),
                    )
                parse_succeeded = True
                break
            except (FactContractError, TypeError, ValueError):
                if attempt == 1:
                    break
                llm_call_count += 1
                try:
                    response = await llm_client.generate(prompt_text)
                except BaseException:
                    break
                retry_usage = _usage(response)
                prompt_tokens += retry_usage[0]
                completion_tokens += retry_usage[1]
                total_tokens += retry_usage[2]
                api_time += retry_usage[3]
        if not parse_succeeded:
            # 020/023 的执行事实无法解析时，模型输出本身不是业务技术故障。
            # 收敛为 evaluation_unknown（对外投影为 uncertain），避免把规则
            # 阻断为 technical_error；保留 model_invalid_output 原因码，便于
            # 诊断和证据链追踪。语义阶段（021/022）维持原有错误语义。
            fallback_status = (
                "evaluation_unknown" if kind == "execution" else "technical_error"
            )
            outcomes_by_rule.update(
                {
                    rule_id: _ConsultationRuleOutcome(
                        rule_id,
                        fallback_status,
                        "model_invalid_output",
                        "llm",
                        "low" if fallback_status == "evaluation_unknown" else None,
                    )
                    for rule_id in rule_ids
                }
            )
            continue
        for rule_id in rule_ids:
            state = states[rule_id]
            if rule_id == "LX0609-03-01-01" and (
                execution_all_coverage_unproven
                or execution_missing_has_unresolved_candidates
            ):
                outcomes_by_rule[rule_id] = _ConsultationRuleOutcome(
                    rule_id,
                    "evaluation_unknown",
                    "semantic_low_confidence",
                    "llm",
                    "low",
                )
                continue
            outcomes_by_rule[rule_id] = _ConsultationRuleOutcome(
                rule_id,
                state.status,
                state.reason_code,
                "llm",
                (
                    "high"
                    if state.status in {"compliant", "non_compliant", "not_applicable"}
                    else ("low" if state.status == "evaluation_unknown" else None)
                ),
            )

    course_has_query_error = any(
        source_issues.get(source_key, (None, None))[0] == "technical_error"
        for source_key in ("daily_course_record", "senior_course_record")
    )
    outcomes: list[_ConsultationRuleOutcome] = []
    for rule_id in selected:
        resolved = outcomes_by_rule[rule_id]
        status, reason_code = resolved.status, resolved.reason_code
        if (
            course_has_query_error
            and rule_id in {"LX0609-03-01-01", "LX0609-03-01-04"}
            and status == "data_gap"
        ):
            status, reason_code = "technical_error", "source_query_error"
        confidence_bucket = (
            "high"
            if status in {"compliant", "non_compliant", "not_applicable"}
            else ("low" if status == "evaluation_unknown" else None)
        )
        outcomes.append(
            _ConsultationRuleOutcome(
                rule_id=rule_id,
                status=status,
                reason_code=reason_code,
                executor_type=resolved.executor_type,
                confidence_bucket=(resolved.confidence_bucket or confidence_bucket),
            )
        )
    return finalize(
        outcomes,
        llm_call_count=llm_call_count,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        total_tokens=total_tokens,
        api_time=api_time,
    )

    rows_by_source: dict[str, list[dict[str, Any]]] = {}
    consultation_complete = True
    course_source_complete = True
    for source_key in _SOURCE_KEYS:
        try:
            if evidence_materials is not None:
                rows_by_source[source_key] = [
                    dict(row) for row in evidence_materials.rows(source_key)
                ]
            else:
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

    raw_consultation_rows = rows_by_source["consultation_record"]
    consultation_rows = [
        row
        for row in raw_consultation_rows
        if _is_actual_consultation_record(row)
    ]
    if (
        not consultation_rows
        and len(raw_consultation_rows) == 1
        and _clean(raw_consultation_rows[0].get("record_content"))
    ):
        consultation_rows = [raw_consultation_rows[0]]
    rows_by_source["consultation_record"] = consultation_rows
    consultation_prompt_complete = (
        len(consultation_rows) <= _MAX_ROWS_BY_SOURCE["consultation_record"]
    )
    if not consultation_complete:
        return finalize(
            _terminal_outcomes(
                selected, "data_gap", "consultation_source_unavailable"
            )
        )
    if not consultation_rows:
        return finalize(
            _terminal_outcomes(selected, "not_applicable", "consultation_absent")
        )
    if not consultation_prompt_complete:
        return finalize(
            _terminal_outcomes(
                selected, "evaluation_unknown", "semantic_low_confidence"
            )
        )

    if not any(_clean(row.get("record_content")) for row in consultation_rows):
        return finalize(
            _terminal_outcomes(
                selected, "data_gap", "consultation_content_unavailable"
            )
        )
    execution_prompt_complete = consultation_prompt_complete and _course_context_complete(
        rows_by_source
    )
    programmatic_reasons: dict[str, str] = {}
    if "LX0609-03-01-02" in selected:
        purpose_reason = _programmatic_purpose_reason(consultation_rows)
        if purpose_reason is not None:
            programmatic_reasons["LX0609-03-01-02"] = purpose_reason
    if "LX0609-03-01-03" in selected:
        opinion_reason = _programmatic_opinion_reason(consultation_rows)
        if opinion_reason is not None:
            programmatic_reasons["LX0609-03-01-03"] = opinion_reason
    if (
        "LX0609-03-01-04" in selected
        and _reconsultation_execution_by_ref(rows_by_source)
    ):
        # 完整复会诊闭环已经由严格 Python 条件唯一绑定，无需先把正文送模型。
        programmatic_reasons["LX0609-03-01-04"] = "execution_specific_summarized"
    semantic_selected = tuple(
        rule_id
        for rule_id in selected
        if rule_id not in programmatic_reasons
        and rule_id not in typed_terminal_blockers
    )
    if not semantic_selected:
        return finalize(
            tuple(
                _ConsultationRuleOutcome(
                    rule_id,
                    (
                        _REASON_STATUS[rule_id][programmatic_reasons[rule_id]]
                        if rule_id in programmatic_reasons
                        else "data_gap"
                    ),
                    programmatic_reasons.get(
                        rule_id, "consultation_source_unavailable"
                    ),
                    "program",
                )
                for rule_id in selected
            )
        )
    if llm_client is None:
        return finalize(
            tuple(
                _ConsultationRuleOutcome(
                    rule_id,
                    (
                        _REASON_STATUS[rule_id][programmatic_reasons[rule_id]]
                        if rule_id in programmatic_reasons
                        else "data_gap"
                    ),
                    programmatic_reasons.get(
                        rule_id, "consultation_llm_unavailable"
                    ),
                    "program",
                )
                for rule_id in selected
            )
        )

    try:
        analysis_rule_ids = list(semantic_selected)
        if "LX0609-03-01-01" in semantic_selected and "LX0609-03-01-04" not in analysis_rule_ids:
            analysis_rule_ids.append("LX0609-03-01-04")
        response = await llm_client.generate(
            _prompt(
                selected=analysis_rule_ids,
                context=_context(rows_by_source),
                opinion_review_context=(
                    _opinion_review_context(consultation_rows)
                    if "LX0609-03-01-03" in analysis_rule_ids else "未请求"
                ),
                course_source_complete=course_source_complete,
            )
        )
    except Exception:
        return finalize(
            tuple(
                _ConsultationRuleOutcome(
                    rule_id,
                    (
                        _REASON_STATUS[rule_id][programmatic_reasons[rule_id]]
                        if rule_id in programmatic_reasons
                        else "data_gap"
                    ),
                    programmatic_reasons.get(rule_id, "consultation_llm_failure"),
                    (
                        "program" if rule_id in programmatic_reasons else "llm"
                    ),
                )
                for rule_id in selected
            ),
            llm_call_count=1,
        )
    prompt_tokens, completion_tokens, total_tokens, api_time = _usage(response)
    payload = _parse_payload(response)
    raw_results = payload.get("results") if isinstance(payload, Mapping) else None
    raw_results = raw_results if isinstance(raw_results, Mapping) else {}
    reason_022 = (
        _derive_semantic_opinion_reason(payload, consultation_rows)
        if isinstance(payload, Mapping) else "consultation_llm_invalid_output"
    )
    reason_020, reason_023, confidence_020, confidence_023 = _derive_execution_reasons(
        payload=payload,
        rows_by_source=rows_by_source,
        course_source_complete=course_source_complete,
    )
    if not execution_prompt_complete and course_source_complete:
        (
            deterministic_reason_020,
            deterministic_reason_023,
            deterministic_confidence_020,
            deterministic_confidence_023,
        ) = _derive_execution_reasons(
            payload=None,
            rows_by_source=rows_by_source,
            course_source_complete=True,
        )
        if deterministic_reason_020 == "execution_specific":
            reason_020 = deterministic_reason_020
            confidence_020 = deterministic_confidence_020
        else:
            reason_020 = "semantic_low_confidence"
            confidence_020 = "low"
        if deterministic_reason_023 in {
            "execution_specific_summarized",
            "execution_vague_or_copied",
        }:
            reason_023 = deterministic_reason_023
            confidence_023 = deterministic_confidence_023
        else:
            reason_023 = "semantic_low_confidence"
            confidence_023 = "low"
    outcomes: list[_ConsultationRuleOutcome] = []
    for rule_id in selected:
        confidence_bucket: str | None = None
        if rule_id in programmatic_reasons:
            reason_code = programmatic_reasons[rule_id]
            status = _REASON_STATUS[rule_id][reason_code]
            executor_type = "program"
        elif rule_id == "LX0609-03-01-01":
            reason_code = reason_020
            status = _REASON_STATUS[rule_id].get(reason_code, "data_gap")
            executor_type = "llm"
            confidence_bucket = confidence_020
        elif rule_id == "LX0609-03-01-03":
            reason_code = reason_022
            status = _REASON_STATUS[rule_id].get(reason_code, "data_gap")
            executor_type = "llm"
            confidence_bucket = (
                "high" if reason_code in {"opinion_clear", "opinion_vague", "opinion_missing"}
                else "low"
            )
        else:
            raw = raw_results.get(rule_id)
            raw = raw if isinstance(raw, Mapping) else {}
            reason_code = str(raw.get("reason_code") or "").strip()
            if rule_id == "LX0609-03-01-04":
                reason_code = reason_023
                confidence_bucket = confidence_023
            if reason_code not in _REASON_STATUS[rule_id]:
                reason_code = "consultation_llm_invalid_output"
                status = "data_gap"
            else:
                status = _REASON_STATUS[rule_id][reason_code]
                if rule_id == "LX0609-03-01-02":
                    confidence_bucket = _confidence_bucket(raw)
                    if confidence_bucket != "high":
                        reason_code = "semantic_low_confidence"
                        status = "evaluation_unknown"
            executor_type = "llm"
        if status == "data_gap" and not reason_code:
            reason_code = "consultation_llm_invalid_output"
        outcomes.append(
            _ConsultationRuleOutcome(
                rule_id, status, reason_code, executor_type, confidence_bucket
            )
        )
    return finalize(
        outcomes,
        llm_call_count=1,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        total_tokens=total_tokens,
        api_time=api_time,
    )
