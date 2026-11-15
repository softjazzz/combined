"""LX0609 输血族原生执行：专用来源事实门控后逐规则裁剪判定。"""

from __future__ import annotations

from .llm_prompt_privacy import luxian_0609_llm_call_failure_reason
from ..llm_token_budget import budget_guarded_executor, budget_rule_scope
from ..llm_context_contract import CONTEXT_FAILURE_REASON_CODES

import asyncio
from dataclasses import dataclass
from datetime import date, datetime, timedelta
import json
import logging
import re
import sys
import unicodedata
from typing import Any, Awaitable, Callable, Mapping, Protocol, Sequence

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
from .pretransfusion_assessment import (
    PretransfusionReasonCandidate,
    build_pretransfusion_reason_candidate,
    evaluate_structured_pretransfusion_application,
    has_structured_pretransfusion_application,
)
from .transfusion_order_trigger import (
    TransfusionOrderTriggerResult, classify_transfusion_orders,
    _RecheckIssue, _RecheckViolation, _recheck_prompt,
)
from .transfusion_course_presence import (
    TransfusionCoursePresenceResult, classify_transfusion_course_records,
    select_transfusion_course_candidates,
)
from .posttransfusion_effect_extraction import (
    PosttransfusionEffectCandidate,
    confirm_posttransfusion_effects,
)
from .transfusion_association import (
    authoritative_posttransfusion_time_value,
    build_transfusion_associations,
    document_ref as association_document_ref,
    is_pre_assessment_document,
    is_post_evaluation_document,
    parse_precise_transfusion_datetime,
    parse_transfusion_document_date,
    source_start_times,
)
from .intraoperative_transfusion_facts import (
    SOURCES as INTRAOPERATIVE_SOURCES,
    IntraoperativeDocument,
    evaluate_intraoperative_consistency,
    extract_intraoperative_transfusion_items,
)
from .source_evidence_reader import (
    authoritative_document_time_value,
    read_luxian_0609_native_source_rows,
)
from .source_registry import (
    resolve_luxian_0609_controlled_fact_source_keys,
    resolve_luxian_0609_decision_support_source_keys,
    resolve_luxian_0609_rule_sources,
)

logger = logging.getLogger(__name__)

TRANSFUSION_RULE_IDS = (
    "LX0609-11-03-01",
    "LX0609-11-03-02",
    "LX0609-07-01-01",
    "LX0609-07-01-02",
    "LX0609-07-02-01",
    "LX0609-07-02-02",
    "LX0609-07-03-01",
    "LX0609-07-04-01",
    "LX0609-07-04-02",
)
EXECUTOR_KEY = "transfusion"
_TYPED_DECISION_RULE_IDS = frozenset(TRANSFUSION_RULE_IDS)
_TYPED_EVALUATOR_VERSION = "transfusion-ruledecision-post-semantic-scope-v10"
_PRE_ASSESSMENT_EVALUATOR_VERSION = "transfusion-pre-assessment-associated-v8"
_COURSE_COMPLETENESS_EVALUATOR_VERSION = "transfusion-course-component-state-v1"

# 049 仍缺少可受控关联的收费数量，因此旧的直接执行入口继续保守返回 DATA_GAP；
# 新建客户任务会在任务入口明确暂停该规则，不会把此系统缺口交付为客户质控结论。
_CONSERVATIVE_DATA_GAP_RULE_IDS = frozenset({"LX0609-07-04-02"})
_CONSERVATIVE_DATA_GAP_REASONS = {
    "LX0609-07-04-02": "billing_linkage_source_unavailable",
}

_TRIGGER_SOURCES = ("bloodtrans_record",)
_ORDER_TRIGGER_RULES = frozenset({"LX0609-07-01-02", "LX0609-07-02-01", "LX0609-07-02-02"})
_ORDER_TRIGGER_SOURCES = ("inpat_nondrug_order", "inpat_drug_order")


def _trigger_sources(rule_id: str) -> tuple[str, ...]:
    return _ORDER_TRIGGER_SOURCES if rule_id in _ORDER_TRIGGER_RULES else _TRIGGER_SOURCES

_EVALUATION_HORIZON_SOURCE_KEY = "evaluation_context.horizon"
_MAX_ROWS_PER_SOURCE = 8
_MAX_ROW_CHARS = 1400
_MAX_CONTEXT_CHARS = 18000
_MAPPING_LINE_PATTERN = re.compile(r"^.*(?:主执行规则|映射执行规则).*$", re.MULTILINE)
_DOCUMENT_IDENTITY_FIELDS = (
    "document_id",
    "exam_id",
    "test_id",
    "labtest_id",
    "report_id",
    "pathology_exam_id",
    "pathology_id",
    "order_id",
    "application_id",
    "event_id",
    "diagnosis_id",
    "surgery_id",
    "id",
)


def _declared_document_identity(value: Any, *, field_name: str) -> str:
    """保留既有边缘空格容忍，但拒绝声明坐标中的控制字符。"""

    raw = str(value or "")
    if any(unicodedata.category(character) == "Cc" for character in raw):
        raise ValueError(f"invalid {field_name} control character")
    normalized = raw.strip()
    if not normalized:
        raise ValueError(f"missing {field_name}")
    return normalized

_PRETRANSFUSION_ASSESSMENT_PATTERN = re.compile(r"输血前(?:评估|评价)")
_PRETRANSFUSION_PURPOSE_PATTERN = re.compile(
    r"输血目的|输血指征|拟输血原因"
    r"|因.{0,12}(?:予|给予|行).{0,12}(?:输血|输注|输入|红细胞|血浆|血小板|冷沉淀|全血)"
)
_PRETRANSFUSION_ASSESSMENT_MISSING_PATTERN = re.compile(
    r"(?:未见|未记录|未形成|无|缺少).{0,12}输血前(?:评估|评价)"
    r"|输血前(?:评估|评价).{0,12}(?:缺失|不完整|未记录)"
)
_PRETRANSFUSION_CORE_PATTERNS = (
    re.compile(r"输血指征|适应证|必要性|拟输血原因"),
    re.compile(r"贫血|血红蛋白|\bHb\b|血小板|凝血|失血|出血"),
    re.compile(r"输血风险|既往输血|不良反应|过敏|生命体征|发热"),
)

_PRETRANSFUSION_REQUIRED_ITEMS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("hbsag", ("乙肝表面抗原", "乙型肝炎病毒表面抗原", "hbsag")),
    ("hbsab", ("乙肝表面抗体", "乙型肝炎病毒表面抗体", "抗-hbs", "anti-hbs", "hbsab")),
    ("hbeag", ("乙肝e抗原", "乙型肝炎e抗原", "乙型肝炎病毒e抗原", "hbeag")),
    ("hbeab", ("乙肝e抗体", "乙型肝炎e抗体", "乙型肝炎病毒e抗体", "抗-hbe", "anti-hbe", "hbeab")),
    ("hbcab", ("乙肝核心抗体", "乙型肝炎核心抗体", "乙型肝炎病毒核心抗体", "抗-hbc", "anti-hbc", "hbcab")),
    ("hcv", ("丙肝", "丙型肝炎", "抗-hcv", "hcv", "hcvab")),
    ("hiv", ("艾滋", "人免疫缺陷病毒", "人类免疫缺陷病毒", "hiv", "hivab", "hivagab")),
    # 缩写 TP 同时是总蛋白（如“*总蛋白测定”），不能作为梅毒别名。
    ("syphilis", ("梅毒", "trust", "rpr")),
    ("alt", ("谷丙转氨酶", "丙氨酸氨基转移酶", "alt")),
)

# 043 常规项目按业务基线：血型及抗体筛查，加八项感染筛查，不含 ALT。
_PRETRANSFUSION_REGULAR_ITEMS = (
    ("abo", ("abo血型", "abo血型鉴定")),
    ("rh", ("rh血型", "rh(d)", "rhd")),
    # 不用裸“抗体筛查”：会同时命中 HIV 等感染项目的抗体筛查。
    ("antibody_screen", ("不规则抗体筛查", "意外抗体筛查", "红细胞抗体筛查")),
    *tuple(item for item in _PRETRANSFUSION_REQUIRED_ITEMS if item[0] != "alt"),
)

_TRANSFUSION_COURSE_SHELL_PATTERN = re.compile(
    r"空模板|模板(?:内容)?|待补(?:充)?|未填写|暂无内容|无正文|记录正文"
)
_TRANSFUSION_COMPONENT_PATTERN = re.compile(
    r"红细胞|血浆|血小板|冷沉淀|全血|白蛋白|粒细胞"
)
_BLOOD_TYPE_OR_RH_PATTERN = re.compile(
    r"(?:AB|A|B|O)型|Rh\s*\(?D\)?\s*(?:阳性|阴性|[+-])?",
    flags=re.IGNORECASE,
)
_TRANSFUSION_PRODUCT_IDENTIFIER_PATTERN = re.compile(
    r"(?:血袋|产品|条码|编号|批号)|\d{8,}",
    flags=re.IGNORECASE,
)
_TRANSFUSION_DOSE_PATTERN = re.compile(
    r"\d+(?:\.\d+)?\s*(?:U|单位|m[lL]|毫升|袋|(?:个)?治疗量)",
    flags=re.IGNORECASE,
)
_TRANSFUSION_START_PATTERN = re.compile(
    r"(?:输血|输注).{0,12}(?:开始|起始)|(?:开始|起始)(?:时间|输血|输注)"
    r"|(?:开始|起始)(?:输入|输注)"
    r"|\d{1,2}:\d{2}.{0,4}(?:开始|起始)"
    r"|(?:开始|起始).{0,4}\d{1,2}:\d{2}"
    r"|\d{1,2}(?:时|点)(?:\d{1,2}分)?.{0,4}(?:开始|起始)"
)
_TRANSFUSION_COURSE_END_PATTERN = re.compile(
    r"(?:输血|输注).{0,12}(?:结束|完毕|完成)"
    r"|结束(?:时间)?|输毕"
)
_TRANSFUSION_OBSERVATION_PATTERN = re.compile(
    r"输血过程中|输注过程中|严密观察|生命体征|过程(?:平稳|顺利)"
)
_TRANSFUSION_REACTION_PATTERN = re.compile(
    r"(?:无|未见).{0,16}(?:不良反应|输血反应|寒战|发热|皮疹|胸闷)"
    r"|耐受良好|有输血反应|发生.{0,8}反应"
)
_TRANSFUSION_COURSE_MISSING_PATTERN = re.compile(
    r"(?:未记录|缺少|未书写).{0,12}(?:输血|输注)(?:病程|记录)"
    r"|(?:输血|输注)(?:病程|记录).{0,12}(?:缺失|未记录|未书写)"
)
_TRANSFUSION_COURSE_INCOMPLETE_PATTERN = re.compile(
    r"(?:输血|输注).{0,12}(?:病程|过程|记录).{0,12}(?:不完整|不规范|缺项)"
    r"|(?:病程|过程|记录).{0,12}(?:不完整|不规范|缺项)"
)

_TRANSFUSION_END_PATTERN = re.compile(
    r"(?:输血|输注)(?:结束|完毕|完成)|输毕|结束(?:输血|输注)"
)
_ANOTHER_UNTIMED_END_PATTERN = re.compile(
    r"(?:另|又|再)\s*(?:一|1)\s*次[^。；;\n]{0,12}"
    r"(?:输血|输注)(?:结束|完毕|完成)"
)
_TRANSFUSION_CONTEXT_PATTERN = re.compile(r"输血|输注|输毕")
_PLANNED_TIME_PREFIX_PATTERN = re.compile(r"预计|计划|拟于|拟在|预定|约于")
_POSTTRANSFUSION_MISSING_PATTERN = re.compile(
    r"(?:未记录|缺少|未书写).{0,12}"
    r"(?:输血|输注)(?:结束)?后(?:评价|评估|疗效|复查)"
    r"|(?:输血|输注)(?:结束)?后.{0,12}(?:评价|评估).{0,12}"
    r"(?:缺失|未记录|未书写)"
)
_POSTTRANSFUSION_CLINICAL_PATTERNS = (
    re.compile(
        r"(?:未见|无)(?:输血|输注)(?:结束)?后(?:评价|评估)异常"
        r"|(?:输血|输注)(?:结束)?后(?:评价|评估).{0,8}"
        r"(?:未见|无)(?:明显)?异常"
        r"|(?:输血|输注)(?:结束)?后(?:评价|评估)正常"
        r"|^后(?:评价|评估).{0,8}(?:未见|无)(?:明显)?异常"
    ),
    re.compile(r"疗效|效果|改善|好转|缓解|复查|复测"),
)
_ISO_DATETIME_PATTERN = re.compile(
    r"(?<!\d)(?P<year>\d{4})[-/](?P<month>\d{1,2})[-/]"
    r"(?P<day>\d{1,2})[ T](?P<hour>\d{1,2}):(?P<minute>\d{2})"
    r"(?::(?P<second>\d{2}))?(?P<timezone>\+08(?::?00)?)?"
)
_CN_DATETIME_PATTERN = re.compile(
    r"(?<!\d)(?P<year>\d{4})年(?P<month>\d{1,2})月(?P<day>\d{1,2})日\s*"
    r"(?P<hour>\d{1,2})(?::(?P<minute_colon>\d{2})"
    r"(?::(?P<second_colon>\d{2}))?"
    r"|时(?P<minute_cn>\d{1,2})分?(?:(?P<second_cn>\d{1,2})秒?)?)"
)

_RULE_CONTEXT_SOURCES = {
    "LX0609-11-03-01": ("bloodtrans_record", "consent_form"),
    "LX0609-11-03-02": ("bloodtrans_record", "consent_form"),
    "LX0609-07-01-01": (
        "bloodtrans_record",
        "blood_application",
        "labtest_master",
        "labtest_item_report",
        "exam_master",
        "exam_item_report",
        "daily_course_record",
        "senior_course_record",
        "inpat_nondrug_order",
        "inpat_drug_order",
    ),
    "LX0609-07-01-02": ("bloodtrans_record", "blood_application", "daily_course_record",
        "senior_course_record",
    ),
    "LX0609-07-02-01": ("bloodtrans_record", "daily_course_record",
        "senior_course_record",
    ),
    "LX0609-07-02-02": ("bloodtrans_record", "daily_course_record",
        "senior_course_record",
    ),
    "LX0609-07-03-01": ("bloodtrans_record", "daily_course_record",
        "senior_course_record",
        "inpat_nondrug_order",
        "inpat_drug_order",
    ),
    "LX0609-07-04-01": (
        "bloodtrans_record",
        "surgery_record",
        "anesthesia_record",
        "postsurg_firstcourse_record",
    ),
    "LX0609-07-04-02": (
        "bloodtrans_record",
        "inpat_nondrug_order",
        "inpat_bill_item",
        "blood_application",
    ),
}

# 每组至少一个来源有实质内容才允许模型判断；缺少来源能力不能伪装成临床缺项。
_RULE_REQUIRED_SOURCE_GROUPS = {
    "LX0609-11-03-01": (("bloodtrans_record",), ("consent_form",)),
    "LX0609-11-03-02": (("bloodtrans_record",), ("consent_form",)),
    "LX0609-07-01-01": (
        ("bloodtrans_record",),
        ("labtest_master", "labtest_item_report", "exam_master", "exam_item_report"),
    ),
    "LX0609-07-01-02": (("bloodtrans_record",), ("blood_application", "daily_course_record")),
    "LX0609-07-02-01": (("bloodtrans_record",), ("daily_course_record",)),
    "LX0609-07-02-02": (("bloodtrans_record",), ("daily_course_record",)),
    "LX0609-07-03-01": (("bloodtrans_record",), ("daily_course_record",)),
    "LX0609-07-04-01": (
        ("bloodtrans_record",),
        ("surgery_record",),
        ("anesthesia_record",),
        ("postsurg_firstcourse_record",),
    ),
    "LX0609-07-04-02": (
        ("bloodtrans_record",),
        ("inpat_nondrug_order",),
        ("inpat_bill_item",),
    ),
}

# typed 路径只消费同一 Evidence Session 的物理材料。别名仅用于把已经进入
# snapshot/material store 的白名单来源投影成旧临床内核所需的逻辑文书名；
# 它不会查询数据库，也不会回读 legacy evidence_payload。
_TYPED_SOURCE_ALIASES = {
    "bloodtrans_record": ("bloodtrans_record",),
    "consent_form": ("consent_form",),
    "labtest_master": ("labtest_master",),
    "labtest_item_report": ("labtest_item_report",),
    "exam_master": ("exam_master",),
    "exam_item_report": ("exam_item_report",),
    "blood_application": ("blood_application",),
    "daily_course_record": ("daily_course_record",),
    "senior_course_record": ("senior_course_record",),
    "surgery_record": ("surgery_record",),
    "anesthesia_record": ("anesthesia_record",),
    "postsurg_firstcourse_record": ("postsurg_firstcourse_record",),
    # medical_order 仅用于识别来源 ERROR；保守规则不会读取其内容推断输血医嘱。
    "inpat_nondrug_order": ("inpat_nondrug_order", "medical_order"),
    "inpat_bill_item": ("inpat_bill_item",),
}


def _typed_rule_source_keys(rule_id: str) -> frozenset[str]:
    logical_sources = set(_trigger_sources(rule_id))
    logical_sources.update(_RULE_CONTEXT_SOURCES[rule_id])
    physical_sources = set(_trigger_sources(rule_id)) | set(_TRIGGER_SOURCES)
    for logical_source in logical_sources:
        physical_sources.update(
            _TYPED_SOURCE_ALIASES.get(logical_source, (logical_source,))
        )
    if rule_id == "LX0609-07-03-01":
        physical_sources.update(
            resolve_luxian_0609_decision_support_source_keys((rule_id,))
        )
    return frozenset(physical_sources)

_CONTROLLED_MESSAGES = {
    "compliant": ("输血相关记录满足该项要求。", ""),
    "non_compliant": ("输血相关记录未满足该项要求。", "请按该质控点补充或修正输血相关记录。"),
    "not_applicable": ("当前就诊未发现已实施输血事实，本规则不适用。", ""),
    "data_gap": ("当前输血相关资料不足，暂不能形成可靠结论。", "请补齐输血相关资料后重新质控。"),
    "evaluation_unknown": ("当前输血相关资料无法形成可靠判断。", "请由临床人员结合原始记录进一步核对。"),
    "technical_error": ("本次规则执行出现技术异常，暂未形成质控结论。", "请稍后重试；如持续发生，请联系技术支持。"),
}
_SYSTEM_DATA_GAP_MESSAGES = {
    "consent_source_unavailable": (
        "本次质控未读取到输血知情同意书，暂无法核对是否已签署。",
        "请确认输血知情同意书已纳入本次质控资料后重新评估。",
    ),
    "consent_signature_contract_unavailable": (
        "本次质控未读取到输血知情同意书的签名及签署时间，暂无法核对填写是否完整。",
        "请确认同意书签名及签署时间已纳入本次质控资料后重新评估。",
    ),
    "pretransfusion_item_contract_unavailable": (
        "本次质控未读取到完整的输血前检查项目及结果时间，暂无法核对检查是否齐全。",
        "请确认输血前检查明细已纳入本次质控资料后重新评估。",
    ),
    "billing_linkage_source_unavailable": (
        "本次质控未读取到可相互核对的输血医嘱、实际输注记录和收费明细。",
        "请确认输血医嘱及收费明细已纳入本次质控资料后重新评估。",
    ),
    "pretransfusion_assessment_source_unavailable": (
        "本次质控未读取到完整的输血前评估相关记录，暂无法判断是否已完成评估。",
        "请确认输血申请及相关病程已纳入本次质控资料后重新评估。",
    ),
    "transfusion_course_source_unavailable": (
        "本次质控未读取到完整的输血病程记录，暂无法核对记录是否存在或完整。",
        "请确认输血记录及相关病程已完整同步后重新评估。",
    ),
    "transfusion_course_record_content_unavailable": (
        "已读取到输血记录条目，但正文为空或仍是模板，暂无法核对记录内容。",
        "请确认输血记录正文已完整同步后重新评估。",
    ),
    "transfusion_comparison_fields_unavailable": (
        "已确认存在术中输血，但暂无法完成三份文书的一致性核对。",
        "请确认手术记录、麻醉记录和术后首次病程中的输血成分、剂量及时间均已完整同步后重新评估。",
    ),
}


class TransfusionLLMClient(Protocol):
    async def generate(self, prompt: str) -> dict[str, Any]: ...


@dataclass(frozen=True)
class NativeTransfusionExecutionResult:
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
class _TransfusionRuleOutcome:
    rule_id: str
    status: str
    reason_code: str
    executor_type: str


def _row_has_document_identity(row: Mapping[str, Any], document_id: str) -> bool:
    """按任一既有业务身份字段精确匹配，禁止空白归一化后的模糊命中。"""

    return any(
        str(row.get(field) if row.get(field) is not None else "").strip() == document_id
        for field in _DOCUMENT_IDENTITY_FIELDS
    )


def _selected_document_identities(
    *,
    rule_id: str,
    display_facts: Mapping[str, Any],
) -> tuple[tuple[str, str], ...]:
    """从执行器已选的内部文书坐标读取证据，不从来源级快照反推。"""

    selected: list[tuple[str, str]] = []
    raw_refs = display_facts.get("source_document_refs")
    if raw_refs is not None:
        if not isinstance(raw_refs, list):
            raise ValueError("invalid selected transfusion document refs")
        for raw_ref in raw_refs:
            if not isinstance(raw_ref, Mapping):
                raise ValueError("invalid selected transfusion document ref")
            source_key = _declared_document_identity(
                raw_ref.get("source_type"), field_name="selected transfusion source"
            )
            document_id = _declared_document_identity(
                raw_ref.get("source_document_id"),
                field_name="selected transfusion document id",
            )
            selected.append((source_key, document_id))

    raw_ids = display_facts.get("source_document_ids")
    if raw_ids is not None:
        if rule_id not in {"LX0609-07-02-01", "LX0609-07-02-02"} or not isinstance(raw_ids, list):
            raise ValueError("invalid selected transfusion document ids")
        for raw_id in raw_ids:
            document_id = _declared_document_identity(
                raw_id, field_name="selected transfusion document id"
            )
            selected.append(("bloodtrans_record", document_id))
    return tuple(dict.fromkeys(selected))


def _material_document_refs_for_selected_identities(
    *,
    selected_identities: Sequence[tuple[str, str]],
    snapshot: Luxian0609EvidenceSnapshot,
    materials: Luxian0609EvidenceMaterialStore,
) -> tuple[str, ...]:
    """将执行器选择的 source+ID 映射为同一快照既有逐行引用。

    同一业务 ID 可能对应多条合法材料行；公共投影要求这些行必须一起被选择，
    因而这里保留全部匹配的 ``document_ref``，不把重复 ID 误作歧义。
    """

    resolved: list[str] = []
    for source_key, document_id in selected_identities:
        try:
            rows = materials.document_rows(source_key, snapshot=snapshot)
        except (EvidenceMaterialUnavailable, EvidenceMaterialTruncated, TypeError, ValueError) as exc:
            raise ValueError("selected transfusion source is not bound to snapshot") from exc
        matches = [
            reference
            for reference, row in rows
            if _row_has_document_identity(row, document_id)
        ]
        if not matches:
            raise ValueError("selected transfusion document is not bound to snapshot")
        resolved.extend(matches)
    return tuple(dict.fromkeys(resolved))


def _typed_decision_from_outcome(
    *,
    outcome: _TransfusionRuleOutcome,
    snapshot: Luxian0609EvidenceSnapshot,
    selected_document_refs: Sequence[str] = (),
) -> RuleDecision:
    """从受控内核 outcome 生成 typed decision，不经过客户结果 DTO。"""

    status = outcome.status
    entries = resolve_luxian_0609_rule_sources((outcome.rule_id,))[outcome.rule_id]
    binding_source_keys = frozenset(
        {
            *(entry.document_type for entry in entries),
            *(source_key for entry in entries for source_key in entry.source_keys),
            *resolve_luxian_0609_controlled_fact_source_keys((outcome.rule_id,)),
            *resolve_luxian_0609_decision_support_source_keys((outcome.rule_id,)),
        }
    )
    allowed_source_keys = _typed_rule_source_keys(outcome.rule_id).intersection(
        binding_source_keys
    )
    if status == "not_applicable" and outcome.reason_code in {"transfusion_order_absent", "transfusion_fact_absent"}:
        # 无事件短路只依赖已核验的触发来源，不消费尚不需要的出院时间或评价正文。
        checked_sources = set(_trigger_sources(outcome.rule_id))
        if outcome.reason_code == "transfusion_fact_absent" and outcome.rule_id in {"LX0609-07-01-01", "LX0609-07-03-01"}:
            checked_sources.update(("daily_course_record", "senior_course_record", *_ORDER_TRIGGER_SOURCES))
        allowed_source_keys = allowed_source_keys.intersection(checked_sources)
    source_refs = tuple(
        observation.snapshot_ref.removeprefix("sha256:")
        for observation in snapshot.observations
        if observation.source_key in allowed_source_keys
    )
    # 来源级观察引用继续保留给审计合同；公共逐行投影只消费 document_ref，
    # 因而不会由这些观察引用重新猜测无关文书。
    refs = tuple(dict.fromkeys((*source_refs, *selected_document_refs)))
    if status in {"compliant", "non_compliant", "not_applicable"} and not refs:
        raise ValueError("typed transfusion decision requires evidence refs")

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
        reason_code = (
            "eligibility_not_met"
            if outcome.rule_id == "LX0609-11-03-02"
            and outcome.reason_code == "transfusion_consent_absent"
            else "evaluation_window_not_mature"
            if outcome.rule_id == "LX0609-07-03-01"
            and outcome.reason_code == "evaluation_window_not_mature"
            else "trigger_absent_complete"
        )
        dimensions = (
            ApplicabilityState.NOT_APPLICABLE,
            EvidenceState.SUFFICIENT,
            QcDirection.UNKNOWN,
            reason_code,
        )
    elif status == "data_gap":
        source_gap = (
            "source_unavailable" in outcome.reason_code
            or outcome.reason_code == "pretransfusion_lab_results_absent"
        )
        # 来源被截断与来源未接入不同：客户应看到“资料不完整”，而不是“数据源未接入”。
        source_truncated = outcome.reason_code == "transfusion_source_truncated"
        authoritative_time_gap = (
            outcome.rule_id == "LX0609-07-03-01"
            and outcome.reason_code == "posttransfusion_evaluation_time_unavailable"
        )
        authoritative_time_conflict = (
            outcome.rule_id == "LX0609-07-03-01"
            and outcome.reason_code == "posttransfusion_evaluation_horizon_conflict"
        )
        association_gap = (
            outcome.rule_id in {"LX0609-07-01-02", "LX0609-07-03-01"}
            and outcome.reason_code == "association_failed"
        )
        # 受控语义核验未决的资料不足保留原因码，供客户文案区分。
        effect_extraction_gap = (
            outcome.rule_id in {"LX0609-07-01-02", "LX0609-07-02-02", "LX0609-07-03-01"}
            and outcome.reason_code in {"semantic_extraction_unresolved", "candidate_scope_incomplete"}
        )
        dimensions = (
            (
                ApplicabilityState.UNKNOWN
                if source_gap or source_truncated
                else ApplicabilityState.APPLICABLE
            ),
            EvidenceState.DATA_GAP,
            QcDirection.UNKNOWN,
            (
                "source_truncated"
                if source_truncated
                else "source_unavailable"
                if source_gap
                else "authoritative_time_missing"
                if authoritative_time_gap
                else "authoritative_time_conflict"
                if authoritative_time_conflict
                else "association_failed"
                if association_gap
                else outcome.reason_code
                if effect_extraction_gap
                else "required_field_missing"
            ),
        )
    elif status == "evaluation_unknown":
        dimensions = (
            ApplicabilityState.APPLICABLE,
            EvidenceState.CONFLICT,
            QcDirection.UNKNOWN,
            "semantic_output_unknown",
        )
    elif status == "technical_error":
        technical_reason = (
            outcome.reason_code
            if outcome.reason_code
            in {
                *CONTEXT_FAILURE_REASON_CODES,
                "source_query_error",
                "snapshot_mismatch",
                "model_transport_error",
                "model_invalid_output",
                # 细分原因码原样保留：隐私拦截与程序异常是确定性失败，改写成执行器异常会被误补跑。
                "model_timeout",
                "privacy_guard_blocked",
                "execution_program_error",
            }
            else "executor_exception"
        )
        dimensions = (
            ApplicabilityState.ERROR,
            EvidenceState.TECHNICAL_ERROR,
            QcDirection.UNKNOWN,
            technical_reason,
        )
    else:
        raise ValueError("unsupported transfusion final state")

    applicability, evidence_state, qc_direction, reason_code = dimensions
    return RuleDecision(
        rule_id=outcome.rule_id,
        snapshot_hash=snapshot.snapshot_hash,
        applicability=applicability,
        evidence_state=evidence_state,
        qc_direction=qc_direction,
        reason_code=reason_code,
        fact_refs=refs,
        evaluator_version=(
            _PRE_ASSESSMENT_EVALUATOR_VERSION
            if outcome.rule_id == "LX0609-07-01-02"
            else _COURSE_COMPLETENESS_EVALUATOR_VERSION
            if outcome.rule_id == "LX0609-07-02-02" else _TYPED_EVALUATOR_VERSION
        ),
        confidence=None,
    )


def _finalize_execution_result(
    *,
    results: Sequence[dict[str, Any]],
    decisions: Sequence[RuleDecision],
    customer_display_facts: Sequence[tuple[str, Mapping[str, Any]]] = (),
    planned_rule_ids: tuple[str, ...],
    llm_call_count: int = 0,
    prompt_tokens: int = 0,
    completion_tokens: int = 0,
    total_tokens: int = 0,
    api_time: float = 0.0,
) -> NativeTransfusionExecutionResult:
    return NativeTransfusionExecutionResult(
        results=tuple(results),
        planned_rule_ids=planned_rule_ids,
        decisions=tuple(decisions),
        customer_display_facts=tuple(customer_display_facts),
        llm_call_count=llm_call_count,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        total_tokens=total_tokens,
        api_time=api_time,
    )


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


def _typed_documents_from_evidence_session(
    *,
    snapshot: Luxian0609EvidenceSnapshot,
    materials: Luxian0609EvidenceMaterialStore,
    rule_id: str,
) -> tuple[Mapping[str, Any] | None, str, str]:
    """只从同一快照材料构造单规则 typed 投影，禁止回读旧 payload。"""

    observation_by_source = {
        observation.source_key: observation
        for observation in snapshot.observations
    }

    # 按规则选择已批准的触发来源。缺少观察是快照接线错误；
    # 查询错误、来源不可用和截断不能当作未开医嘱或无输血事实。
    for source_key in _trigger_sources(rule_id):
        observation = observation_by_source.get(source_key)
        if observation is None:
            return None, "technical_error", "snapshot_mismatch"
        if observation.query_state.value == "error":
            return None, "technical_error", "source_query_error"
        if observation.query_state.value == "unavailable":
            return None, "data_gap", "transfusion_source_unavailable"
        if observation.completeness.value == "truncated":
            return None, "data_gap", "transfusion_source_truncated"

    documents: dict[str, Any] = {}
    try:
        # 触发判断只读取同一材料仓；这里先证明来源完整且可读。
        for source_key in _trigger_sources(rule_id):
            materials.rows(source_key)
    except Exception:
        return None, "technical_error", "snapshot_mismatch"

    # 结构化输注事件只作为同次就诊内的关联锚点，不进入模型上下文。
    # 时间字段仅供后续时序检查，不能代替医嘱触发。
    for source_key in _trigger_sources(rule_id):
        if source_key in _ORDER_TRIGGER_SOURCES:
            documents[source_key] = [dict(row) for row in materials.rows(source_key)]
    logical_states: dict[str, str] = {}
    projected_physical_sources: set[str] = set()
    for logical_source in _RULE_CONTEXT_SOURCES[rule_id]:
        rows: list[dict[str, Any]] = []
        states: list[str] = []
        for source_key in _TYPED_SOURCE_ALIASES.get(
            logical_source, (logical_source,)
        ):
            if source_key in projected_physical_sources:
                continue
            observation = observation_by_source.get(source_key)
            if observation is None:
                continue
            if observation.query_state.value == "error":
                states.append("error")
                continue
            if (
                observation.query_state.value == "unavailable"
                or observation.completeness.value == "truncated"
            ):
                states.append("unavailable")
                continue
            try:
                rows.extend(dict(row) for row in materials.rows(source_key))
            except Exception:
                return None, "technical_error", "snapshot_mismatch"
            states.append("complete")
            projected_physical_sources.add(source_key)
        documents[logical_source] = rows
        if rows:
            logical_states[logical_source] = "available"
        elif "error" in states:
            logical_states[logical_source] = "error"
        elif "unavailable" in states:
            logical_states[logical_source] = "unavailable"
        elif "complete" in states:
            logical_states[logical_source] = "empty"
        else:
            logical_states[logical_source] = "missing"

    if rule_id == "LX0609-07-03-01":
        horizon_observation = observation_by_source.get(
            _EVALUATION_HORIZON_SOURCE_KEY
        )
        if horizon_observation is None:
            return None, "technical_error", "snapshot_mismatch"
        if horizon_observation.query_state.value == "error":
            return None, "technical_error", "source_query_error"
        if (
            horizon_observation.query_state.value == "unavailable"
            or horizon_observation.completeness.value == "truncated"
        ):
            documents["__evaluation_horizon_rows__"] = []
        else:
            try:
                documents["__evaluation_horizon_rows__"] = [
                    dict(row)
                    for row in materials.rows(_EVALUATION_HORIZON_SOURCE_KEY)
                ]
            except Exception:
                return None, "technical_error", "snapshot_mismatch"
        documents["__evaluation_horizon_reason__"] = str(
            horizon_observation.reason_code or ""
        ).strip()

    # 这里只构造同一快照内的材料和四态，不在辅助来源为空时提前终止。
    # 专用输血记录可能已足以给出确定结论；辅助来源四态只能在程序化判断
    # 无法定论后参与 fail-closed，不能覆盖专用记录的强事实。
    documents["__material_scope__"] = {key: materials.scope(key) for key in logical_states if materials.scope(key) is not None}
    documents["__logical_source_states__"] = logical_states
    return documents, "", ""


def _typed_conservative_material_status(
    *,
    snapshot: Luxian0609EvidenceSnapshot,
    materials: Luxian0609EvidenceMaterialStore,
    rule_id: str,
) -> tuple[Mapping[str, Any], str, str]:
    """校验保守迁移规则的安全来源四态，不消费代理材料作临床判断。"""

    observation_by_source = {
        observation.source_key: observation
        for observation in snapshot.observations
    }
    # 先只校验输血触发锚点。规则详细材料是否可用必须在确认
    # 实际输血之后再判断，否则会把“明确无输血”错误降级为 DATA_GAP。
    for source_key in _TRIGGER_SOURCES:
        observation = observation_by_source.get(source_key)
        if observation is None:
            continue
        if observation.query_state.value == "error":
            return {}, "technical_error", "source_query_error"
        if (
            observation.query_state.value == "unavailable"
            or observation.completeness.value == "truncated"
        ):
            return {}, "data_gap", "transfusion_source_unavailable"

    # 只对当前 session 真正包含的专用输血锚点做材料身份校验。单规则尚未把
    # 两个锚点都接入 snapshot 时不能伪装为“确认无输血”，后续 source_state
    # 会保持 DATA_GAP；任一锚点有确定阳性仍可证明规则适用。
    for source_key in _TRIGGER_SOURCES:
        observation = observation_by_source.get(source_key)
        if observation is None:
            continue
        try:
            materials.rows(source_key)
        except Exception:
            return {}, "technical_error", "snapshot_mismatch"
    return {}, "", ""


def _typed_conservative_contract_outcome(
    *, snapshot: Luxian0609EvidenceSnapshot, rule_id: str
) -> tuple[str, str]:
    """确认实际输血后，再按规则详细来源四态 fail closed。"""

    observation_by_source = {
        observation.source_key: observation
        for observation in snapshot.observations
    }
    context_source_keys = _typed_rule_source_keys(rule_id).difference(
        _TRIGGER_SOURCES
    )
    for source_key in sorted(context_source_keys):
        observation = observation_by_source.get(source_key)
        if observation is None:
            continue
        if observation.query_state.value == "error":
            return "technical_error", "source_query_error"
        if (
            observation.query_state.value == "unavailable"
            or observation.completeness.value == "truncated"
        ):
            return "data_gap", _CONSERVATIVE_DATA_GAP_REASONS.get(
                rule_id, "transfusion_rule_contract_unavailable"
            )
    return "data_gap", _CONSERVATIVE_DATA_GAP_REASONS.get(
        rule_id, "transfusion_rule_contract_unavailable"
    )


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


def _source_entries(
    documents: Mapping[str, Any],
    source_key: str,
    *,
    limit: int | None = _MAX_ROWS_PER_SOURCE,
) -> list[str]:
    """为单文书判定保留标题与正文边界，避免跨文书拼接临床事实。"""

    raw_rows = documents.get(source_key)
    if not isinstance(raw_rows, list):
        return []
    entries: list[str] = []
    bounded_rows = raw_rows if limit is None else raw_rows[:limit]
    for raw_row in bounded_rows:
        if not isinstance(raw_row, Mapping):
            continue
        title = _clean(raw_row.get("document_title") or raw_row.get("title"))
        content = _row_text(raw_row)
        entry = " ".join(value for value in (title, content) if value).strip()
        if entry:
            entries.append(entry[:_MAX_ROW_CHARS])
    return entries


def _source_document_rows(
    documents: Mapping[str, Any], source_key: str
) -> list[Mapping[str, Any]]:
    raw_rows = documents.get(source_key)
    if not isinstance(raw_rows, list):
        return []
    return [raw_row for raw_row in raw_rows if isinstance(raw_row, Mapping)]


def _required_projection_failure(
    rule_id: str, documents: Mapping[str, Any]
) -> tuple[str, str] | None:
    """仅在专用程序化事实无法定论后解释辅助投影四态。"""

    raw_states = documents.get("__logical_source_states__")
    logical_states = raw_states if isinstance(raw_states, Mapping) else None
    for group in _RULE_REQUIRED_SOURCE_GROUPS[rule_id]:
        if any(_source_rows(documents, source_key) for source_key in group):
            continue
        if logical_states is None:
            return "data_gap", "transfusion_rule_projection_incomplete"
        group_states = tuple(
            str(logical_states.get(source_key) or "missing") for source_key in group
        )
        if "error" in group_states:
            return "technical_error", "source_query_error"
        if all(state == "missing" for state in group_states):
            return "technical_error", "snapshot_mismatch"
        if "unavailable" in group_states:
            return "data_gap", "transfusion_source_unavailable"
        return "data_gap", "transfusion_rule_projection_incomplete"
    return None


def _logical_source_state(documents: Mapping[str, Any], source_key: str) -> str:
    raw = documents.get("__logical_source_states__")
    return str(raw.get(source_key) or "missing") if isinstance(raw, Mapping) else "missing"


def _structured_or_labeled_value(
    row: Mapping[str, Any], *, fields: Sequence[str], labels: Sequence[str]
) -> bool:
    if any(_clean(row.get(field)) for field in fields):
        return True
    text = _row_text(row)
    return any(
        re.search(rf"{re.escape(label)}\s*[：:]\s*(?!无\b|未\b|缺失\b)\S+", text, re.IGNORECASE)
        for label in labels
    )


def _consent_signature_present(
    row: Mapping[str, Any], *, fields: Sequence[str], labels: Sequence[str]
) -> bool:
    """Explicitly unsigned values and placeholders cannot prove a signature."""

    def usable(value: Any) -> bool:
        text = _clean(value).strip("。.;；")
        return bool(text) and not re.fullmatch(
            r"(?:[-—_/\\\s]+|无|暂无|空|空白|不详|未知|缺失|"
            r"null|none|n/?a|\[\]|\{\}|"
            r"待(?:填|填写|补充|完善|签名|签字)?|"
            r"未(?:填|填写|完成|签名|签字)?|"
            r"尚未(?:完成|签名|签字|填写)?)",
            text,
            re.IGNORECASE,
        ) and not re.match(r"^(?:未签|尚未签|未见签|拒绝签|拒签|无签)", text)

    structured = [row.get(field) for field in fields if _clean(row.get(field))]
    if structured:
        return any(usable(value) for value in structured)
    text = _row_text(row)
    return any(
        usable(match.group(1))
        for label in labels
        for match in re.finditer(
            rf"{re.escape(label)}\s*[：:]\s*([^。；;，,\n]+)", text
        )
    )


def _has_minute_precise_signed_time(row: Mapping[str, Any]) -> bool:
    fields = (
        "sign_datetime",
        "signed_at",
        "sign_time",
        "patient_sign_datetime",
        "physician_sign_datetime",
    )
    for field in fields:
        value = row.get(field)
        if isinstance(value, datetime):
            return True
        if isinstance(value, str) and re.search(
            r"\d{4}[-年/]\d{1,2}[-月/]\d{1,2}(?:日)?\s+\d{1,2}[:时]\d{2}",
            value,
        ):
            return True
    return bool(
        re.search(
            r"(?:签署时间|签名时间)\s*[：:]\s*"
            r"\d{4}[-年/]\d{1,2}[-月/]\d{1,2}(?:日)?\s+\d{1,2}[:时]\d{2}",
            _row_text(row),
        )
    )


def _transfusion_event_rows(documents: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    raw_rows = documents.get("performed_transfusion_events")
    rows = (
        [row for row in raw_rows if isinstance(row, Mapping)]
        if isinstance(raw_rows, list)
        else []
    )
    return [row for row in rows if _transfusion_event_time(row) is not None]


def _transfusion_event_time(row: Mapping[str, Any]) -> datetime | None:
    for key in (
        "transfution_datetime",
        "transfusion_datetime",
        "start_time",
        "transfusion_start_time",
        "record_time",
    ):
        parsed = _parse_document_datetime(row.get(key))
        if parsed is not None:
            return parsed
    return None


def _transfusion_consent_rows(
    documents: Mapping[str, Any],
) -> list[Mapping[str, Any]]:
    """仅接受明确标型或标题明确的输血同意书，隔离手术/麻醉同意书。"""

    rows: list[Mapping[str, Any]] = []
    for row in _source_document_rows(documents, "consent_form"):
        consent_type = _clean(row.get("consent_type")).lower().replace("-", "_")
        title = _clean(row.get("document_title"))
        if consent_type in {"blood_transfusion", "transfusion", "blood"} or (
            "输血" in title and "同意" in title
        ):
            rows.append(row)
    return rows


def _source_document_refs(
    rows: Sequence[Mapping[str, Any]],
    *,
    source_type: str,
    identity_fields: Sequence[str] = ("document_id",),
    limit: int | None = 8,
) -> list[dict[str, str]]:
    refs: list[dict[str, str]] = []
    seen: set[str] = set()
    for row in rows:
        document_id = ""
        for field in identity_fields:
            document_id = str(row.get(field) or "").strip()
            if document_id:
                break
        if not document_id or document_id in seen:
            continue
        seen.add(document_id)
        refs.append({"source_type": source_type, "source_document_id": document_id})
        if limit is not None and len(refs) == limit:
            break
    return refs


def _programmatic_041_status(
    documents: Mapping[str, Any],
) -> tuple[str, str, Mapping[str, Any] | None]:
    consent_rows = _transfusion_consent_rows(documents)
    state = _logical_source_state(documents, "consent_form")
    if state in {"unavailable", "missing"}:
        return "data_gap", "consent_source_unavailable", None
    if state == "error":
        return "technical_error", "source_query_error", None
    if not consent_rows:
        trigger_refs = _source_document_refs(
            _source_document_rows(documents, "bloodtrans_record"),
            source_type="bloodtrans_record",
            limit=None,
        )
        return (
            "non_compliant",
            "transfusion_consent_missing",
            {
                "failure_kind": "transfusion_consent_missing",
                "performed_transfusion_confirmed": True,
                "checked_source": "blood_transfusion_consent",
                **({"source_document_refs": trigger_refs} if trigger_refs else {}),
            },
        )
    return (
        "compliant",
        "transfusion_consent_present",
        {
            "verification_kind": "transfusion_consent_present",
            "performed_transfusion_confirmed": True,
            "consent_count": len(consent_rows),
            "source_document_refs": _source_document_refs(
                consent_rows,
                source_type="consent_form",
                limit=None,
            ),
        },
    )


def _programmatic_042_status(
    documents: Mapping[str, Any],
) -> tuple[str, str, Mapping[str, Any] | None]:
    consent_rows = _transfusion_consent_rows(documents)
    state = _logical_source_state(documents, "consent_form")
    if state in {"unavailable", "missing"}:
        return "data_gap", "consent_signature_contract_unavailable", None
    if state == "error":
        return "technical_error", "source_query_error", None
    if not consent_rows:
        return "not_applicable", "transfusion_consent_absent", None
    checks = (
        ("patient_information", ("patient_name", "name", "patient_id"), ("患者姓名", "患者")),
        ("diagnosis", ("diagnosis",), ("诊断",)),
        ("indication", ("transfusion_reason", "indication"), ("输血指征", "输血目的")),
        ("component", ("blood_component", "transfuse_variety"), ("输血成分", "输血品种")),
        ("risks", ("risk_description",), ("风险", "不良反应")),
        ("alternatives", ("alternative_plan",), ("替代方案", "其他治疗")),
        ("patient_or_agent_signature", ("patient_sign", "agent_sign", "patient_signature"), ("患者签名", "代理人签名")),
        ("physician_signature", ("physician_sign", "doctor_sign", "physician_signature"), ("医师签名", "医生签名")),
    )
    missing = [
        item
        for item, fields, labels in checks
        if not all(
            (
                _consent_signature_present(row, fields=fields, labels=labels)
                if item in {"patient_or_agent_signature", "physician_signature"}
                else _structured_or_labeled_value(row, fields=fields, labels=labels)
            )
            for row in consent_rows
        )
    ]
    if not all(_has_minute_precise_signed_time(row) for row in consent_rows):
        missing.append("signed_time")
    missing.sort()
    if missing:
        return (
            "non_compliant",
            "transfusion_consent_incomplete",
            {
                "failure_kind": "transfusion_consent_incomplete",
                "performed_transfusion_confirmed": True,
                "missing_fields": missing,
            },
        )
    return (
        "compliant",
        "transfusion_consent_complete",
        {
            "verification_kind": "transfusion_consent_complete",
            "performed_transfusion_confirmed": True,
            "checked_fields": [item for item, _, _ in checks] + ["signed_time"],
        },
    )


def _lab_item_key(row: Mapping[str, Any]) -> str:
    # 来源合同同时认可 item_name 与 lab_item_name 两种项目名字段。
    return " ".join(_clean(row.get(key)) for key in (
        "item_name", "lab_item_name", "item_code", "item_abbreviation", "content",
    )).lower()


def _lab_item_alias_matches(key: str, alias: str) -> bool:
    normalized = alias.lower()
    if normalized.isascii() and normalized.isalnum():
        return re.search(
            rf"(?<![a-z0-9]){re.escape(normalized)}(?![a-z0-9])",
            key,
        ) is not None
    return normalized in key


def resolve_pretransfusion_required_item(
    row: Mapping[str, Any],
    *,
    required_items: tuple[tuple[str, tuple[str, ...]], ...] = _PRETRANSFUSION_REQUIRED_ITEMS,
) -> str | None:
    """返回指定输血前项目集合中该检验行命中的唯一受控项目。"""

    key = _lab_item_key(row)
    matched = {item for item, aliases in required_items
               if any(_lab_item_alias_matches(key, alias) for alias in aliases)}
    return next(iter(matched)) if len(matched) == 1 else None


def resolve_pretransfusion_admission_time(row: Mapping[str, Any]) -> datetime | None:
    """读取输血前九项当前住院判定认可的唯一住院时间字段。"""

    return _parse_document_datetime(
        row.get("admission_datetime")
        or row.get("admission_time")
        or row.get("inpat_datetime")
    )


def _lab_report_time(row: Mapping[str, Any]) -> datetime | None:
    for key in ("report_datetime", "report_time", "record_time"):
        parsed = _parse_document_datetime(row.get(key))
        if parsed is not None:
            return parsed
    return None


def evaluate_pretransfusion_nine_items(
    documents: Mapping[str, Any],
    *,
    require_current_stay: bool = False,
    required_items: tuple[tuple[str, tuple[str, ...]], ...] = _PRETRANSFUSION_REQUIRED_ITEMS,
) -> tuple[str, str, Mapping[str, Any] | None]:
    # 九项检查本身就可能超过模型上下文使用的 8 行上限；确定性核对必须消费
    # 已进入同一 Evidence Session 的完整有界材料，不能把第九项误判为缺失。
    raw_rows = documents.get("labtest_item_report")
    rows = (
        [row for row in raw_rows if isinstance(row, Mapping)]
        if isinstance(raw_rows, list)
        else []
    )
    state = _logical_source_state(documents, "labtest_item_report")
    if state in {"unavailable", "missing"}:
        return "data_gap", "pretransfusion_item_contract_unavailable", None
    if state == "error":
        return "technical_error", "source_query_error", None
    raw_event_rows = _source_document_rows(documents, "performed_transfusion_events")
    event_times = sorted(
        {
            value
            for row in raw_event_rows
            if (value := _transfusion_event_time(row)) is not None
        }
    )
    if not event_times:
        return "data_gap", "transfusion_time_unavailable", None

    if len(raw_event_rows) != sum(
        1 for row in raw_event_rows if _transfusion_event_time(row) is not None
    ):
        return "data_gap", "transfusion_time_unavailable", None

    if state == "empty" or not rows:
        return "data_gap", "pretransfusion_lab_results_absent", None

    admission_time: datetime | None = None
    if require_current_stay:
        admission_times = {
            parsed
            for row in _source_document_rows(documents, "inpat_registration")
            if (parsed := resolve_pretransfusion_admission_time(row)) is not None
        }
        if len(admission_times) != 1:
            return "data_gap", "admission_time_unavailable", None
        admission_time = next(iter(admission_times))

    matched: dict[str, list[Mapping[str, Any]]] = {
        item: [] for item, _ in required_items
    }
    for row in rows:
        if (item := resolve_pretransfusion_required_item(row, required_items=required_items)) is not None:
            matched[item].append(row)
    event_checks: list[dict[str, Any]] = []
    for transfusion_time in event_times:
        missing_items: list[str] = []
        missing_time_items: list[str] = []
        late_items: list[str] = []
        outside_current_stay_items: list[str] = []
        valid_item_times: list[datetime] = []
        for item, item_rows in matched.items():
            if not item_rows:
                missing_items.append(item)
                continue
            report_times = [
                value
                for row in item_rows
                if (value := _lab_report_time(row)) is not None
            ]
            if not report_times:
                missing_time_items.append(item)
                continue
            valid_times = [
                value
                for value in report_times
                if value < transfusion_time
                and (admission_time is None or value >= admission_time)
            ]
            if valid_times:
                valid_item_times.append(max(valid_times))
                continue
            if admission_time is not None and any(
                value < admission_time for value in report_times
            ):
                outside_current_stay_items.append(item)
            else:
                late_items.append(item)
        event_checks.append(
            {
                "transfusion_time": transfusion_time.isoformat(sep=" "),
                "missing_items": sorted(missing_items),
                "missing_time_items": sorted(missing_time_items),
                "late_items": sorted(late_items),
                "outside_current_stay_items": sorted(outside_current_stay_items),
                "latest_valid_test_time": (
                    max(valid_item_times).isoformat(sep=" ")
                    if valid_item_times
                    else None
                ),
            }
        )

    base_facts: dict[str, Any] = {
        "performed_transfusion_confirmed": True,
        "required_items": [item for item, _ in required_items],
        "transfusion_event_count": len(event_times),
        "checked_transfusion_times": [
            value.isoformat(sep=" ") for value in event_times
        ],
        "event_checks": event_checks,
    }
    if admission_time is not None:
        base_facts["admission_time"] = admission_time.isoformat(sep=" ")

    failed_checks = [
        item
        for item in event_checks
        if any(
            item[key]
            for key in (
                "missing_items",
                "missing_time_items",
                "late_items",
                "outside_current_stay_items",
            )
        )
    ]
    if failed_checks:
        base_facts["failed_transfusion_times"] = [
            str(item["transfusion_time"]) for item in failed_checks
        ]
    missing_checks = [item for item in failed_checks if item["missing_items"]]
    if missing_checks:
        base_facts.update(
            {
                "failure_kind": "pretransfusion_items_incomplete",
                "missing_items": sorted(
                    {
                        name
                        for item in missing_checks
                        for name in item["missing_items"]
                    }
                ),
            }
        )
        return "non_compliant", "pretransfusion_items_incomplete", base_facts
    outside_checks = [
        item for item in failed_checks if item["outside_current_stay_items"]
    ]
    if outside_checks:
        base_facts.update(
            {
                "failure_kind": "pretransfusion_tests_outside_current_stay",
                "outside_current_stay_items": sorted(
                    {
                        name
                        for item in outside_checks
                        for name in item["outside_current_stay_items"]
                    }
                ),
            }
        )
        return "non_compliant", "pretransfusion_tests_outside_current_stay", base_facts
    late_checks = [item for item in failed_checks if item["late_items"]]
    if late_checks:
        base_facts.update(
            {
                "failure_kind": "pretransfusion_tests_after_transfusion",
                "late_items": sorted(
                    {
                        name
                        for item in late_checks
                        for name in item["late_items"]
                    }
                ),
            }
        )
        return "non_compliant", "pretransfusion_tests_after_transfusion", base_facts
    # 缺时间只说明该项无法核对，不能掩盖其他项目已确认的缺失、院外或晚于输血。
    time_gap_checks = [item for item in failed_checks if item["missing_time_items"]]
    if time_gap_checks:
        base_facts.update(
            {
                "failure_kind": "pretransfusion_test_time_missing",
                "missing_time_items": sorted(
                    {
                        name
                        for item in time_gap_checks
                        for name in item["missing_time_items"]
                    }
                ),
            }
        )
        return "data_gap", "authoritative_time_missing", base_facts

    latest = max(
        datetime.fromisoformat(str(item["latest_valid_test_time"]))
        for item in event_checks
        if item["latest_valid_test_time"] is not None
    )
    application_rows = _source_document_rows(documents, "blood_application")
    abo_present = any(_clean(row.get("patient_bloodtype_abo") or row.get("blood_type")) for row in application_rows)
    rh_present = any(_clean(row.get("patient_bloodtype_rhd")) for row in application_rows)
    antibody_present = any("抗体筛查" in _lab_item_key(row) or "不规则抗体" in _lab_item_key(row) for row in rows)
    base_facts.update(
        {
            "verification_kind": "pretransfusion_items_complete",
            "checked_items": [item for item, _ in required_items],
            "latest_test_time": latest.isoformat(sep=" "),
            "transfusion_time": event_times[-1].isoformat(sep=" "),
            "abo_present": bool(matched.get("abo")) if "abo" in matched else abo_present,
            "rh_present": bool(matched.get("rh")) if "rh" in matched else rh_present,
            "antibody_screen_present": antibody_present,
        }
    )
    return "compliant", "pretransfusion_items_complete", base_facts


def _pre_assessment_documents(documents: Mapping[str, Any]) -> dict[str, Any]:
    """前评估候选只保留专门文书；申请单仍走原有结构化合同。"""
    return {**documents, **{source: [row for row in _source_document_rows(documents, source)
                                   if is_pre_assessment_document(row)]
                           for source in ("daily_course_record", "senior_course_record")}}


def _context(rule_id: str, documents: Mapping[str, Any]) -> str:
    if rule_id == "LX0609-07-01-02":
        documents = _pre_assessment_documents(documents)
    parts: list[str] = []
    for source_key in _RULE_CONTEXT_SOURCES[rule_id]:
        for index, content in enumerate(_source_rows(documents, source_key), start=1):
            parts.append(f"[{source_key}-{index}] {content}")
    return "\n".join(parts)[:_MAX_CONTEXT_CHARS]


def _programmatic_044_status(
    documents: Mapping[str, Any],
) -> tuple[str, str] | tuple[str, str, Mapping[str, Any]] | None:
    """按次只核对最近一份专门评估；同一份评估不重复满足后续输血。"""
    legacy_pre_sources_complete = not isinstance(documents.get("__logical_source_states__"), Mapping) and all(
        isinstance(documents.get(source), list) for source in ("blood_application", "daily_course_record", "senior_course_record"))
    documents = _pre_assessment_documents(documents)
    records = _source_document_rows(documents, "bloodtrans_record")
    source_times = {value for row in _transfusion_event_rows(documents) for value in source_start_times(row)}
    pre_count = sum(len(_source_document_rows(documents, source)) for source in (
        "blood_application", "daily_course_record", "senior_course_record"))
    if (len(records) <= 1 and len(source_times) <= 1 and pre_count == 1
            and has_structured_pretransfusion_application(documents)):
        # 唯一结构化申请单由原时序合同核对，保留晚于/同刻申请及缺时间的诊断事实。
        # 该所有者不读取输血记录中的评估描述，不能恢复旧正文短路；有竞争候选仍逐次关联。
        return evaluate_structured_pretransfusion_application(documents)
    # 有输血记录时，单次与多次都先关联专门前评估/申请单，再核对内容。
    # 不能因只有一条记录就跳过关联，让记录内的评估描述或晚写评估直接判合规。
    # 尚无输血记录的旧入口继续保留原申请单/缺失材料合同。
    if not records and len(source_times) <= 1 and pre_count <= 1:
        return _programmatic_044_single_status(documents)
    try:
        associations = build_transfusion_associations(documents, end_evidence=_transfusion_end_evidence)
        if len(records) == 1 and len(source_times) == 1 and associations.events[0].start is None:
            # 唯一结构化实际输血事件仍可为单份记录提供锚点；不使用记录/提交时间猜测。
            associations = build_transfusion_associations(
                {**documents, "bloodtrans_record": [
                    {**records[0], "transfusion_start_time": next(iter(source_times))}]},
                end_evidence=_transfusion_end_evidence,
            )
    except ValueError:
        return "technical_error", "snapshot_mismatch"
    represented_times = {value for event in associations.events for value in event.start_times}
    if not records or source_times - represented_times:
        return "data_gap", "association_failed"
    outcomes = []
    pending = False
    semantic_pending = False
    unavailable = []
    pre_links = [item for item in associations.documents if item.stage == "pre"]
    for event, record in zip(associations.events, records):
        selected = {item.document_ref for item in associations.documents
                    if item.stage == "pre" and item.state == "linked" and item.event_refs == (event.record_ref,)}
        if (event.start is None or event.time_unresolved) and pre_links:
            pending = True
            continue
        if not selected:
            # 不能把时间未知、候选冲突或读取失败解释成医院漏写；但完整来源中
            # 明确缺少这次评估时，应与单次输血一样判文书缺失，而非关联资料不足。
            if any(item.document_time is None for item in pre_links):
                unavailable.append(("data_gap", "authoritative_time_missing"))
                continue
            if any(event.record_ref in item.event_refs and item.state not in {"linked", "ignored"}
                   for item in pre_links):
                pending = True
                continue
            sources = ("blood_application", "daily_course_record", "senior_course_record")
            states = {_logical_source_state(documents, source) for source in sources}
            if "error" in states:
                unavailable.append(("technical_error", "source_query_error"))
                continue
            if not legacy_pre_sources_complete and not states.issubset({"available", "empty"}):
                unavailable.append(("data_gap", "pretransfusion_assessment_source_unavailable"))
                continue
            facts = dict(_customer_display_facts_for_outcome(rule_id="LX0609-07-01-02",
                status="non_compliant", reason_code="pretransfusion_assessment_missing") or {})
            facts["source_document_refs"] = _source_document_refs([record], source_type="bloodtrans_record", limit=None)
            outcomes.append(("non_compliant", "pretransfusion_assessment_missing", facts))
            continue
        scoped = dict(documents)
        scoped["bloodtrans_record"] = [record]
        # 使用同一证据会话已确认的实际开始时刻，不使用记录或提交时间猜测。
        scoped["performed_transfusion_events"] = [{"transfution_datetime": event.start.isoformat(sep=" ")}]
        for source in ("blood_application", "daily_course_record", "senior_course_record"):
            scoped[source] = [row for index, row in enumerate(_source_document_rows(documents, source))
                              if association_document_ref(source, row, index) in selected]
        outcome = _programmatic_044_single_status(scoped)
        if outcome is None:
            if len(records) == 1 and len(source_times) <= 1 and pre_count <= 1:
                # 单次申请单的受控理由补核继续由原执行入口处理。
                return None
            semantic_pending = True
        elif outcome[0] not in {"compliant", "non_compliant"}:
            unavailable.append(outcome)
        else:
            outcomes.append(outcome)
    # 确定的问题仍保留；剩余关系不清不能抹掉已确认的问题，也不能判整例合规。
    failed = next((outcome for outcome in outcomes if outcome[0] == "non_compliant"), None)
    if failed:
        return failed
    if unavailable:
        return unavailable[0]
    if pending:
        return "data_gap", "association_failed"
    if semantic_pending:
        return "data_gap", "semantic_extraction_unresolved"
    facts = dict(outcomes[0][2]) if len(outcomes[0]) == 3 else {}
    refs = [ref for outcome in outcomes if len(outcome) == 3 for ref in outcome[2].get("source_document_refs", ())]
    facts["source_document_refs"] = [dict(pair) for pair in dict.fromkeys(tuple(sorted(ref.items())) for ref in refs)]
    return "compliant", "pretransfusion_assessment_complete", facts


def _programmatic_044_single_status(
    documents: Mapping[str, Any],
) -> tuple[str, str] | tuple[str, str, Mapping[str, Any]] | None:
    """输血申请单的理由、客观指标及时序直接构成输血前评估。"""

    structured = evaluate_structured_pretransfusion_application(documents)
    if structured is not None:
        return structured

    sourced_entries: list[tuple[str, Mapping[str, Any], str]] = []
    for source_key in _RULE_CONTEXT_SOURCES["LX0609-07-01-02"]:
        for row in _source_document_rows(documents, source_key):
            title = _clean(row.get("document_title") or row.get("title"))
            content = _row_text(row)
            entry = " ".join(value for value in (title, content) if value).strip()
            if entry:
                sourced_entries.append((source_key, row, entry))
    entries = tuple(entry for _, _, entry in sourced_entries)

    def selected_refs(
        predicate: Any,
    ) -> list[dict[str, str]]:
        refs: list[dict[str, str]] = []
        for source_key, row, entry in sourced_entries:
            if predicate(entry):
                refs.extend(
                    _source_document_refs(
                        [row], source_type=source_key, limit=None
                    )
                )
        return refs

    def display_facts(
        status: str,
        reason_code: str,
        *,
        refs: Sequence[Mapping[str, str]] = (),
    ) -> Mapping[str, Any] | None:
        if status == "non_compliant" and reason_code == "pretransfusion_assessment_missing":
            # 评估记录不存在是文书缺失，不能借过程信号生成评估字段缺项。
            facts = _customer_display_facts_for_outcome(
                rule_id="LX0609-07-01-02", status=status, reason_code=reason_code,
            )
        else:
            facts = _programmatic_transfusion_display_facts(
                rule_id="LX0609-07-01-02",
                status=status,
                reason_code=reason_code,
                documents=documents,
            )
        if facts is None:
            return None
        result = dict(facts)
        if refs:
            result["source_document_refs"] = [dict(item) for item in refs]
        else:
            result.pop("source_document_refs", None)
        return result

    def with_bloodtrans_anchors(
        refs: Sequence[Mapping[str, str]],
    ) -> list[dict[str, str]]:
        return [
            *(dict(item) for item in refs),
            *_source_document_refs(
                _source_document_rows(documents, "bloodtrans_record"),
                source_type="bloodtrans_record",
                limit=None,
            ),
        ]

    has_explicit_missing = any(
        _PRETRANSFUSION_ASSESSMENT_MISSING_PATTERN.search(entry) is not None
        for entry in entries
    )
    missing_refs = selected_refs(
        lambda entry: _PRETRANSFUSION_ASSESSMENT_MISSING_PATTERN.search(entry)
        is not None
    )
    if has_explicit_missing:
        return (
            "non_compliant",
            "pretransfusion_assessment_missing",
            display_facts(
                "non_compliant",
                "pretransfusion_assessment_missing",
                refs=with_bloodtrans_anchors(missing_refs),
            )
            or {},
        )

    bloodtrans_entries = tuple(
        _source_entries(documents, "bloodtrans_record", limit=None)
    )
    has_application = bool(
        _source_entries(documents, "blood_application", limit=None)
    )

    has_complete_assessment = any(
        _PRETRANSFUSION_ASSESSMENT_PATTERN.search(entry) is not None
        and all(pattern.search(entry) for pattern in _PRETRANSFUSION_CORE_PATTERNS)
        for entry in entries
    )
    complete_refs = selected_refs(
        lambda entry: _PRETRANSFUSION_ASSESSMENT_PATTERN.search(entry) is not None
        and all(pattern.search(entry) for pattern in _PRETRANSFUSION_CORE_PATTERNS)
    )
    if has_complete_assessment:
        return (
            "compliant",
            "pretransfusion_assessment_complete",
            display_facts(
                "compliant",
                "pretransfusion_assessment_complete",
                refs=with_bloodtrans_anchors(complete_refs),
            )
            or {},
        )

    has_marker = any(_PRETRANSFUSION_ASSESSMENT_PATTERN.search(entry) for entry in entries)
    has_indication = any(
        _PRETRANSFUSION_CORE_PATTERNS[0].search(entry) for entry in entries
    )
    raw_states = documents.get("__logical_source_states__")
    logical_states = raw_states if isinstance(raw_states, Mapping) else {}
    supporting_states = {
        str(logical_states.get(source_key) or "")
        for source_key in ("blood_application", "daily_course_record", "senior_course_record")
    }
    if "error" in supporting_states:
        return "technical_error", "source_query_error"
    if "unavailable" in supporting_states:
        return "data_gap", "pretransfusion_assessment_source_unavailable"
    # 输血目的、输注过程中的生命体征或不良反应均不能反向充当
    # “输血前评估”。专用输血记录存在但没有评估标识，且也没有独立
    # 申请/评估文书时，可确定为缺失；有独立申请文书的灰区仍交给模型。
    if (
        not has_marker
        and bloodtrans_entries
        and not has_application
    ):
        return (
            "non_compliant",
            "pretransfusion_assessment_missing",
            display_facts(
                "non_compliant",
                "pretransfusion_assessment_missing",
                refs=_source_document_refs(
                    _source_document_rows(documents, "bloodtrans_record"),
                    source_type="bloodtrans_record",
                    limit=None,
                ),
            )
            or {},
        )
    if not has_marker and not has_indication and not has_application:
        # 没有评估文书时沿用前面同类分支的“文书未记录”合同。
        # 不能让后续回退扫描普通病程的零散目的/指标，再生成空缺项或字段缺失结论。
        return (
            "non_compliant",
            "pretransfusion_assessment_missing",
            display_facts("non_compliant", "pretransfusion_assessment_missing") or {},
        )
    if bloodtrans_entries and has_application and not has_marker:
        return "non_compliant", "pretransfusion_assessment_incomplete"
    return None


def _is_substantive_transfusion_course_entry(entry: str) -> bool:
    """只识别专用输血记录中的实质临床内容；标题或模板不进入确定性短路。"""

    if (
        len(entry) < 24
        or not _TRANSFUSION_CONTEXT_PATTERN.search(entry)
        or _TRANSFUSION_COURSE_SHELL_PATTERN.search(entry)
    ):
        return False
    clinical_signals = tuple(
        bool(pattern.search(entry))
        for pattern in (
            _PRETRANSFUSION_PURPOSE_PATTERN,
            _PRETRANSFUSION_CORE_PATTERNS[0],
            _TRANSFUSION_COMPONENT_PATTERN,
            _TRANSFUSION_DOSE_PATTERN,
            _TRANSFUSION_START_PATTERN,
            _TRANSFUSION_END_PATTERN,
            _TRANSFUSION_OBSERVATION_PATTERN,
            _TRANSFUSION_REACTION_PATTERN,
        )
    )
    # 前两项仅描述目的/指征；至少还要有一个真实输注过程信号。
    return sum(clinical_signals) >= 2 and any(clinical_signals[2:])


def _programmatic_045_status(
    documents: Mapping[str, Any],
) -> tuple[str, str] | None:
    entries = tuple(_source_entries(documents, "bloodtrans_record", limit=None))
    if any(_TRANSFUSION_COURSE_MISSING_PATTERN.search(entry) for entry in entries):
        return "non_compliant", "transfusion_course_record_missing"
    if any(_is_substantive_transfusion_course_entry(entry) for entry in entries):
        return "compliant", "transfusion_course_record_present"
    if not entries and _logical_source_state(documents, "bloodtrans_record") == "empty":
        return "non_compliant", "transfusion_course_record_missing"
    return None


def _is_complete_transfusion_course_entry(entry: str) -> bool:
    """逐份核对完整性，禁止从多份文书拼接成一份合规记录。"""

    if not _is_substantive_transfusion_course_entry(entry):
        return False
    has_purpose_or_indication = bool(
        _PRETRANSFUSION_PURPOSE_PATTERN.search(entry)
        or _PRETRANSFUSION_CORE_PATTERNS[0].search(entry)
    )
    return all(
        (
            has_purpose_or_indication,
            bool(_TRANSFUSION_COMPONENT_PATTERN.search(entry)),
            bool(_TRANSFUSION_DOSE_PATTERN.search(entry)),
            bool(_TRANSFUSION_START_PATTERN.search(entry)),
            bool(_TRANSFUSION_COURSE_END_PATTERN.search(entry)),
            bool(_TRANSFUSION_OBSERVATION_PATTERN.search(entry)),
            bool(_TRANSFUSION_REACTION_PATTERN.search(entry)),
        )
    )


def _transfusion_046_field_checks(
    entry: str,
    *,
    component_confirmed: bool = False,
    component_unresolved: bool = False,
) -> dict[str, bool | None]:
    """逐份输血记录核验046必填项；受控LLM只能补齐component。"""

    return {
        "reason_or_indication": bool(
            _PRETRANSFUSION_PURPOSE_PATTERN.search(entry)
            or _PRETRANSFUSION_CORE_PATTERNS[0].search(entry)
        ),
        "start_and_end_time": bool(
            _TRANSFUSION_START_PATTERN.search(entry)
            and _TRANSFUSION_COURSE_END_PATTERN.search(entry)
        ),
        "component": (
            True if _TRANSFUSION_COMPONENT_PATTERN.search(entry) or component_confirmed
            else None if component_unresolved else False
        ),
        "dose": bool(_TRANSFUSION_DOSE_PATTERN.search(entry)),
        "process_observation": bool(_TRANSFUSION_OBSERVATION_PATTERN.search(entry)),
        "reaction_and_handling": bool(_TRANSFUSION_REACTION_PATTERN.search(entry)),
        "clinical_effect": _transfusion_record_has_effect(entry),
    }


def _transfusion_record_ref(record: Mapping[str, Any], index: int) -> str:
    """只标识本次输血记录，不把文书正文或其他来源传给模型。"""

    return _clean(record.get("document_id")) or f"bloodtrans_record-{index}"


def _046_component_llm_candidates(
    documents: Mapping[str, Any],
) -> tuple[tuple[str, str], ...]:
    """成分词典未命中只表示待核；不能跳过同份或其他记录的确定缺项。"""

    rows = _source_document_rows(documents, "bloodtrans_record")
    candidates: list[tuple[str, str]] = []
    for index, record in enumerate(rows, start=1):
        entry = _row_text(record)
        if not documents.get("__course_presence_verified__") and not _is_substantive_transfusion_course_entry(entry):
            return ()
        checks = _transfusion_046_field_checks(entry)
        if checks["component"]:
            continue
        candidates.append((_transfusion_record_ref(record, index), entry))
    return tuple(candidates)


def _programmatic_046_status(
    documents: Mapping[str, Any],
    *, component_assertions: Mapping[str, str] | None = None,
) -> tuple[str, str] | None:
    verified = documents.get("__course_presence_verified__") is True
    entries = tuple(_row_text(row) for row in _source_document_rows(documents, "bloodtrans_record"))
    if not entries:
        return "data_gap", "transfusion_course_source_unavailable"
    if not verified and not any(_is_substantive_transfusion_course_entry(entry) for entry in entries):
        return "data_gap", "transfusion_course_record_content_unavailable"
    if entries and any(
        _TRANSFUSION_COURSE_INCOMPLETE_PATTERN.search(entry) for entry in entries
    ):
        return "non_compliant", "transfusion_course_record_incomplete"
    candidates = _046_component_llm_candidates(documents)
    if candidates and component_assertions is None:
        return None
    assertions = component_assertions or {}
    checks = [
        _transfusion_046_field_checks(
            _row_text(row),
            component_confirmed=assertions.get(_transfusion_record_ref(row, index)) == "explicit",
            component_unresolved=assertions.get(_transfusion_record_ref(row, index)) not in {"explicit", "not_explicit"},
        )
        for index, row in enumerate(_source_document_rows(documents, "bloodtrans_record"), start=1)
    ]
    if entries and all(
        (verified or _is_substantive_transfusion_course_entry(entry))
        and not (
            _PRETRANSFUSION_PURPOSE_PATTERN.search(entry)
            or _PRETRANSFUSION_CORE_PATTERNS[0].search(entry)
        )
        for entry in entries
    ):
        return "non_compliant", "transfusion_purpose_or_indication_missing"
    if any(any(value is False for value in item.values()) for item in checks):
        return "non_compliant", "transfusion_course_record_incomplete"
    if any(item["component"] is None for item in checks):
        return None
    return "compliant", "transfusion_course_record_complete"


def _046_component_prompt(*, document_ref: str, record_text: str) -> str:
    """046专用受控事实提取：禁止从血型、剂量或编号推断输血成分。"""

    return (
        "你只核对下面这一份输血记录单是否明确写出实际输注血液成分。\n"
        "不得根据血型、Rh、产品/血袋编号、剂量或医学常识推断成分。\n"
        "仅输出严格JSON，不要解释："
        '{"assertion":"explicit|not_explicit|unclear","component_text":"",'
        '"quote":"","document_ref":""}\n'
        f"document_ref: {document_ref}\n"
        "输血记录单正文：\n"
        f"{record_text}"
    )


def _044_reason_prompt(candidate: PretransfusionReasonCandidate) -> str:
    """044专用语义提取：只确认这一张申请单是否写明申请输血的临床理由。"""

    if candidate.reason_source == "course":
        # 申请单未提供理由与正文时，理由改从实际输血前的病程核对（用户口径 2026-10-18）。
        return (
            "输血申请单没有申请理由与正文。你只核对下面实际输血前的病程记录，"
            "是否明确写出本次决定输血的临床理由（如结合检验结果说明贫血、出血风险、"
            "凝血功能异常等而决定输注某种血液成分）。\n"
            "仅写“必要时输血”“必要时可输血”等条件性计划、未决定本次输血的，不算理由；"
            "仅记录输血后的情况也不算。\n"
            "不得根据检验数值、拟输血成分、剂量或医学常识自行推断理由。\n"
            "reason_state=present时，evidence_quote必须逐字摘自病程原文的单个连续片段并直接表达输血理由；"
            "无法确定时返回uncertain。\n"
            "仅输出严格JSON，不要解释："
            '{"reason_state":"present|absent|uncertain","evidence_quote":"",'
            '"application_ref":""}\n'
            f"application_ref: {candidate.application_ref}\n"
            f"实际输血时间：{candidate.transfusion_time.isoformat(sep=' ')}\n"
            "输血前病程：\n"
            f"{candidate.application_text}"
        )
    return (
        "你只核对下面这一张输血申请单是否明确写出申请输血的临床理由。\n"
        "不得根据检验数值、拟输血成分、剂量或医学常识自行推断理由。\n"
        "reason_state=present时，evidence_quote必须逐字摘自原文并直接表达申请理由；"
        "无法确定时返回uncertain。\n"
        "仅输出严格JSON，不要解释："
        '{"reason_state":"present|absent|uncertain","evidence_quote":"",'
        '"application_ref":""}\n'
        f"application_ref: {candidate.application_ref}\n"
        "输血申请单正文：\n"
        f"{candidate.application_text}"
    )


def _parse_044_reason_response(
    response: Mapping[str, Any],
) -> Mapping[str, str] | None:
    cleaned = re.sub(
        r"<think>[\s\S]*?</think>", "", _response_text(response), flags=re.IGNORECASE
    ).strip()
    try:
        payload = json.loads(cleaned)
    except (TypeError, ValueError):
        return None
    if not isinstance(payload, Mapping) or set(payload) != {
        "reason_state",
        "evidence_quote",
        "application_ref",
    }:
        return None
    if any(not isinstance(value, str) for value in payload.values()):
        return None
    normalized = {key: payload[key].strip() for key in payload}
    if normalized["reason_state"] not in {"present", "absent", "uncertain"}:
        return None
    return normalized


def _validated_044_reason_state(
    payload: Mapping[str, str],
    *,
    candidate: PretransfusionReasonCandidate,
) -> str | None:
    issues: list[_RecheckIssue] = []
    location = f"application_ref={candidate.application_ref}"
    if payload.get("application_ref") != candidate.application_ref:
        issues.append(_RecheckIssue("invalid application binding", location, "application_ref", payload.get("application_ref"),
            correction="application_ref须原样使用输入申请单标识，不能引用其他申请单"))
    state = payload.get("reason_state") or ""
    quote = payload.get("evidence_quote") or ""
    if state == "present":
        invalid_quote = not quote or quote not in candidate.application_text
    elif state in {"absent", "uncertain"}:
        invalid_quote = bool(quote) and quote not in candidate.application_text
    else:
        return None
    if invalid_quote:
        source = "输血前病程" if candidate.reason_source == "course" else "申请单正文"
        issues.append(_RecheckIssue("invalid reason quote", location, "evidence_quote", quote,
            correction=f"须逐字复制输入{source}中直接表达本次输血理由的单个连续片段，不得拼接、改写或借用其他文书"))
    if issues:
        raise _RecheckViolation(issues)
    return state


def _parse_046_component_response(
    response: Mapping[str, Any],
) -> Mapping[str, str] | None:
    cleaned = re.sub(
        r"<think>[\s\S]*?</think>", "", _response_text(response), flags=re.IGNORECASE
    ).strip()
    try:
        payload = json.loads(cleaned)
    except (TypeError, ValueError):
        return None
    if not isinstance(payload, Mapping) or set(payload) != {
        "assertion", "component_text", "quote", "document_ref"
    }:
        return None
    if any(not isinstance(value, str) for value in payload.values()):
        return None
    assertion = payload["assertion"].strip()
    if assertion not in {"explicit", "not_explicit", "unclear"}:
        return None
    return {key: payload[key].strip() for key in payload}


def _validated_046_component_assertion(
    payload: Mapping[str, str],
    *,
    document_ref: str,
    record_text: str,
) -> str | None:
    """验证模型引用仍落在同一原文，且成分不能只是血型、编号或剂量。"""

    issues: list[_RecheckIssue] = []
    location = f"document_ref={document_ref}"
    if payload.get("document_ref") != document_ref:
        issues.append(_RecheckIssue("invalid component document binding", location, "document_ref", payload.get("document_ref"),
            correction="document_ref须原样使用输入文书标识，不得借用其他文书"))
    quote = payload.get("quote") or ""
    component_text = payload.get("component_text") or ""
    assertion = payload.get("assertion") or ""
    if not quote or quote not in record_text:
        issues.append(_RecheckIssue("invalid component quote", location, "quote", quote))
    if assertion == "explicit":
        component_remainder = _BLOOD_TYPE_OR_RH_PATTERN.sub("", component_text)
        component_remainder = _TRANSFUSION_PRODUCT_IDENTIFIER_PATTERN.sub(
            "", component_remainder
        )
        component_remainder = _TRANSFUSION_DOSE_PATTERN.sub("", component_remainder)
        component_remainder = re.sub(r"[\s,，;；:：()（）\[\]【】\-]+", "", component_remainder)
        if (
            not component_text
            or component_text not in quote
            # 仅血型/Rh、产品编号或剂量不能被升级为血液成分；但“AB型血浆”
            # 一类表述去掉血型后仍保留制品名称，应允许通过同原文校验。
            or not component_remainder
        ):
            issues.append(_RecheckIssue("invalid component binding", location, "component_text", component_text,
                correction="component_text须逐字取自同条quote中明确的实际输注成分；不能把血型、Rh、编号或剂量推断为成分"))
    elif component_text:
        issues.append(_RecheckIssue("unproven component assertion", location, "component_text", component_text,
            correction="非explicit时component_text须为空，不能断言成分"))
    if issues:
        raise _RecheckViolation(issues)
    return assertion


@dataclass(frozen=True)
class _SemanticRecheck:
    state: str | None
    reason_code: str
    calls: int
    usage: tuple[int, int, int, float]


async def _recheck_transfusion_semantics(
    prompt: str, llm_client: Any,
    parse: Callable[[Mapping[str, Any]], Mapping[str, str] | None],
    validate: Callable[[Mapping[str, str]], str | None],
) -> _SemanticRecheck:
    """单条语义仅对已识别的引文或绑定错误补核一次，结构错误立即结束。"""
    attempt_prompt = prompt
    prompt_tokens = completion_tokens = total_tokens = 0
    api_time = 0.0
    for attempt in range(2):
        try:
            response = await llm_client.generate(attempt_prompt)
        except Exception as error:
            return _SemanticRecheck(None, luxian_0609_llm_call_failure_reason(error), attempt + 1,
                (prompt_tokens, completion_tokens, total_tokens, api_time))
        usage = _usage(response)
        prompt_tokens += usage[0]
        completion_tokens += usage[1]
        total_tokens += usage[2]
        api_time += usage[3]
        payload = parse(response)
        state = None
        if payload is not None:
            try:
                state = validate(payload)
            except _RecheckViolation as error:
                logger.warning("LX0609 transfusion_recheck_invalid checks=%s",
                               sorted({(issue.field, issue.reason) for issue in error.issues}))
                if attempt == 0:
                    attempt_prompt = _recheck_prompt(prompt, error, response)
                    continue
        else:
            logger.warning("LX0609 transfusion_recheck_invalid phase=response_shape")
        return _SemanticRecheck(state, "" if state is not None else "model_invalid_output", attempt + 1,
            (prompt_tokens, completion_tokens, total_tokens, api_time))
    raise AssertionError("输血语义补核未结束")


def _datetime_from_match(match: re.Match[str]) -> datetime | None:
    values = match.groupdict()
    minute = values.get("minute") or values.get("minute_colon") or values.get("minute_cn")
    second = values.get("second") or values.get("second_colon") or values.get("second_cn") or "0"
    try:
        return datetime(
            int(values["year"]),
            int(values["month"]),
            int(values["day"]),
            int(values["hour"]),
            int(minute or 0),
            int(second),
        )
    except (TypeError, ValueError):
        return None


def _parse_document_calendar_datetime(value: Any) -> datetime | None:
    """保留原始时区坐标下的日历时刻（仅用于与同一行原始日期做一致性校验）。"""
    if isinstance(value, datetime):
        return value.replace(tzinfo=None) if value.tzinfo is not None else value
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except ValueError:
        return _parse_document_datetime(value)
    return parsed.replace(tzinfo=None) if parsed.tzinfo is not None else parsed


def _parse_document_datetime(value: Any) -> datetime | None:
    # 带时区的时间先换算为医院本地时间再去掉时区，不能直接丢弃时区（如 08:00Z 应为本地 16:00）。
    from ..discharge_time import hospital_business_time

    if isinstance(value, datetime):
        return hospital_business_time(value).replace(tzinfo=None) if value.tzinfo is not None else value
    if not isinstance(value, str):
        return None
    candidate = value.strip()
    if not candidate:
        return None
    for pattern in (_ISO_DATETIME_PATTERN, _CN_DATETIME_PATTERN):
        match = pattern.fullmatch(candidate)
        if match:
            return _datetime_from_match(match)
    try:
        parsed = datetime.fromisoformat(candidate.replace("Z", "+00:00"))
    except ValueError:
        return None
    return hospital_business_time(parsed).replace(tzinfo=None) if parsed.tzinfo is not None else parsed


def _transfusion_end_evidence(
    text: str,
) -> tuple[tuple[tuple[datetime, int, int], ...], bool]:
    """只接受紧邻“结束/完毕”标识的完整日期时间，避免用文书时间猜输血结束。"""

    datetime_matches = [
        match
        for pattern in (_ISO_DATETIME_PATTERN, _CN_DATETIME_PATTERN)
        for match in pattern.finditer(text)
    ]
    events: list[tuple[datetime, int, int]] = []
    unresolved = False
    for end_match in _TRANSFUSION_END_PATTERN.finditer(text):
        time_match = max(
            (
                match
                for match in datetime_matches
                if match.end() <= end_match.start()
                and end_match.start() - match.end() <= 4
            ),
            key=lambda match: match.end(),
            default=None,
        )
        if time_match is None:
            # “输血结束后复查”可以是对前述已记录结束事件的引用，不能重复要求时间；
            # 其余独立结束标志缺少完整时间时必须 fail-closed。
            if not text[end_match.end() :].startswith("后"):
                unresolved = True
            continue
        separator = text[time_match.end() : end_match.start()]
        if separator.strip(" \t\r\n，,。；;：:"):
            unresolved = True
            continue
        prefix = text[max(0, time_match.start() - 12) : time_match.start()]
        if _PLANNED_TIME_PREFIX_PATTERN.search(prefix):
            unresolved = True
            continue
        parsed = _datetime_from_match(time_match)
        if parsed is not None:
            events.append((parsed, end_match.start(), end_match.end()))
        else:
            unresolved = True
    return tuple(events), unresolved


def _has_clinical_posttransfusion_evaluation(text: str) -> bool:
    if _POSTTRANSFUSION_MISSING_PATTERN.search(text):
        return False
    return any(pattern.search(text) for pattern in _POSTTRANSFUSION_CLINICAL_PATTERNS)


def _transfusion_record_has_effect(text: str) -> bool:
    """输血目的中的“改善”不构成实际效果；核验过程结束后的评价内容。"""
    ends = tuple(_TRANSFUSION_COURSE_END_PATTERN.finditer(text))
    return bool(ends) and _has_clinical_posttransfusion_evaluation(text[ends[-1].end():])


_STRICT_LAB_EFFECT_PATTERN = re.compile(
    r"(?:血红蛋白|(?<![A-Za-z])(?:HGB|Hb)(?![A-Za-z])|血小板|凝血功能)[^。；;\n]{0,50}"
    r"较前[^。；;\n]{0,8}(?:上升|升高|提升|下降|降低|改善|无明显变化)"
    # 同一分句写明输血后的指标及变化方向，同属带方向的实验室效果评价。
    r"|(?:输血|输注)(?:(?:结束|完毕|完成)后?|后)[^。；;\n]{0,20}"
    r"(?:血红蛋白|(?<![A-Za-z])(?:HGB|Hb|HCT)(?![A-Za-z])|红细胞压积|血小板|凝血功能)"
    r"[^。；;\n]{0,20}(?:上升|升高|提升|恢复|改善|纠正)",
    re.I,
)


def _course_has_strict_lab_effect(text: str) -> bool:
    """唯一保留的程序直认：血液指标带方向的前后比较本身即实验室效果评价。"""
    return _STRICT_LAB_EFFECT_PATTERN.search(text) is not None


def _course_has_transfusion_effect(text: str) -> bool:
    """跨病程评价须明确关联输血，不能借用另一疾病的症状好转。"""
    # 24小时关联由调用方核验。明确的血液指标比较本身也是实验室效果评价，
    # 不额外要求把“输血后”三个字写进同一句；普通症状好转仍不据此采信。
    if _course_has_strict_lab_effect(text):
        return True
    # 写明输血结束后紧接的评价（如“输血结束，复查血红蛋白改善”）与专用记录同口径。
    if _transfusion_record_has_effect(text):
        return True
    return bool(re.search(
        r"(?:输血|输注|输毕)(?:结束)?后|(?:输血|输注)(?:治疗)?(?:效果|疗效|评价|评估)", text,
    )) and _has_clinical_posttransfusion_evaluation(text)


_047_MODEL_CONFIRMED_EFFECTS_KEY = "__posttransfusion_effect_confirmed__"


def _course_effect_confirmed(
    documents: Mapping[str, Any], source_key: str, row: Mapping[str, Any], text: str,
) -> bool:
    """院方口径（047 基线）：评价须含临床或实验室效果。程序只直认带方向的指标比较；
    其余写法（如“输血后复查”“效果好”）是否构成效果评价由受控模型逐字引文确认。"""
    if _course_has_strict_lab_effect(text):
        return True
    document_id = str(row.get("document_id") or row.get("id") or "").strip()
    return bool(document_id) and (source_key, document_id) in (
        documents.get(_047_MODEL_CONFIRMED_EFFECTS_KEY) or frozenset()
    )


def _post_evaluation_documents(documents: Mapping[str, Any]) -> dict[str, Any]:
    """后评价只核对专门单据；不变更源完整性状态，也不造空来源。"""
    selected = dict(documents)
    for source in ("daily_course_record", "senior_course_record"):
        if isinstance(documents.get(source), list):
            selected[source] = [row for row in _source_document_rows(documents, source)
                                if is_post_evaluation_document(row)]
    return selected


def _047_effect_candidates(documents: Mapping[str, Any]) -> tuple[PosttransfusionEffectCandidate, ...]:
    """结束后24小时内、正则未认出效果的专门后评价；时间与关联仍由Python判定。"""
    documents = _post_evaluation_documents(documents)
    end_times = [
        max(event[0] for event in events)
        for row in _source_document_rows(documents, "bloodtrans_record")
        for events in (_transfusion_end_evidence(_row_text(row))[0],)
        if events
    ]
    candidates: list[PosttransfusionEffectCandidate] = []
    for source_key in ("daily_course_record", "senior_course_record"):
        for row in _source_document_rows(documents, source_key):
            text = _row_text(row)
            record_time = _authoritative_047_record_time(row)
            record_date = _authoritative_047_record_date(row)
            document_id = str(row.get("document_id") or row.get("id") or "").strip()
            if (
                not text.strip() or not document_id
                or _course_has_strict_lab_effect(text)
                or not any(
                    0 <= (record_time - end).total_seconds() <= 24 * 3600
                    if record_time is not None
                    else record_date is not None
                    and _047_date_may_fall_in_window(record_date, end)
                    for end in end_times
                )
            ):
                continue
            candidates.append(PosttransfusionEffectCandidate(source_key, document_id, text))
    return tuple(candidates)


@dataclass(frozen=True)
class _PosttransfusionEvaluationAssessment:
    """047 的唯一时间资格判定，供状态与客户事实投影共同使用。"""

    status: str
    reason_code: str
    latest_end_time: datetime | None = None
    evaluation_time: datetime | None = None
    selected_source_document_refs: tuple[tuple[str, str], ...] = ()


def _047_evaluation_horizon(
    documents: Mapping[str, Any],
) -> tuple[datetime | None, date | None, str]:
    """读取冻结快照内的评价终点，不以当前时间或当天末尾补足精度。"""

    rows = documents.get("__evaluation_horizon_rows__")
    if not isinstance(rows, list) or len(rows) != 1 or not isinstance(rows[0], Mapping):
        return None, None, str(
            documents.get("__evaluation_horizon_reason__") or "authoritative_time_missing"
        )
    row = rows[0]
    raw_datetime = row.get("horizon_datetime")
    raw_calendar_datetime = _parse_document_calendar_datetime(raw_datetime)
    horizon_datetime = parse_precise_transfusion_datetime(raw_datetime)
    raw_date = _clean(row.get("horizon_date"))
    horizon_date: date | None = None
    if raw_date:
        try:
            horizon_date = date.fromisoformat(raw_date)
        except ValueError:
            return None, None, "authoritative_time_missing"
    if (
        horizon_date is not None
        and raw_calendar_datetime is not None
        and horizon_date != raw_calendar_datetime.date()
    ):
        # provider 保留原始 aware 时间的日期；先在原始坐标中校验，
        # 再与精确时刻一同换算为医院时区，避免 UTC 跨日伪冲突。
        return None, None, "authoritative_time_conflict"
    if horizon_datetime is not None:
        horizon_date = horizon_datetime.date()
    elif raw_datetime:
        # 上界只有日期时保留日精度；禁止补成 00:00 改变 24h 成熟判定。
        if raw_calendar_datetime is None:
            return None, None, "authoritative_time_missing"
        horizon_date = raw_calendar_datetime.date()
    if horizon_date is None:
        return None, None, str(
            documents.get("__evaluation_horizon_reason__") or "authoritative_time_missing"
        )
    return horizon_datetime, horizon_date, ""


def _047_evaluation_time_is_after_horizon(
    evaluation_time: datetime,
    *,
    horizon_datetime: datetime | None,
    horizon_date: date,
) -> bool:
    return (
        evaluation_time > horizon_datetime
        if horizon_datetime is not None
        else evaluation_time.date() > horizon_date
    )


def _047_window_is_mature(
    end_time: datetime,
    *,
    horizon_datetime: datetime | None,
    horizon_date: date,
) -> tuple[bool, bool]:
    """返回(已成熟, 终点是否早于输血结束)。日期精度必须保守处理。"""

    if horizon_datetime is not None:
        if horizon_datetime < end_time:
            return False, True
        return horizon_datetime > end_time + timedelta(hours=24), False
    if horizon_date < end_time.date():
        return False, True
    return horizon_date > (end_time + timedelta(hours=24)).date(), False


def _programmatic_047_assessment(
    documents: Mapping[str, Any],
    *,
    unclear_effect_refs: frozenset[tuple[str, str]] = frozenset(),
) -> _PosttransfusionEvaluationAssessment:
    """按输血结束后24小时窗口判定，评价正文必须有可用的完成时间。"""

    documents = _post_evaluation_documents(documents)
    post_refs = frozenset(association_document_ref(key, row, index)
        for key in ("daily_course_record", "senior_course_record")
        for index, row in enumerate(_source_document_rows(documents, key))
        if _course_effect_confirmed(documents, key, row, _row_text(row)))
    try:
        associations = build_transfusion_associations(documents, end_evidence=_transfusion_end_evidence,
                                                      post_document_refs=post_refs)
    except ValueError:
        return _PosttransfusionEvaluationAssessment("technical_error", "snapshot_mismatch")
    post_links = {(source, id(row)): associations.find(association_document_ref(source, row, index), "post")
                  for source in ("daily_course_record", "senior_course_record")
                  for index, row in enumerate(_source_document_rows(documents, source))}

    # 关联器保留每份已确认实际输血记录，即使记录没有可解析的结束时刻。047 以
    # record_ref 作为事件主键，禁止把过滤后的结束时刻数组再与完整事件数组按位置对齐。
    event_refs = tuple(event.record_ref for event in associations.events)
    if not event_refs:
        return _PosttransfusionEvaluationAssessment(
            "data_gap", "transfusion_end_time_unavailable"
        )
    if len(set(event_refs)) != len(event_refs):
        return _PosttransfusionEvaluationAssessment("technical_error", "snapshot_mismatch")
    events_by_ref = {event.record_ref: event for event in associations.events}
    known_end_by_ref = {
        ref: event.end
        for ref, event in events_by_ref.items()
        if event.end is not None and not event.time_unresolved
    }
    unknown_end_refs = set(event_refs).difference(known_end_by_ref)

    def selected_event_refs(refs: set[tuple[str, str]]) -> tuple[tuple[str, str], ...]:
        # @row 只用于同一快照内稳定关联，不可冒充对外可定位的文书编号。
        return tuple(
            ref for ref in event_refs
            if ref in refs and ref[1] and not ref[1].startswith("@row:")
        )

    def unresolved_another_refs(
        text: str,
        *,
        anchored_refs: set[tuple[str, str]],
        record_date: date | None,
        record_time: datetime | None,
    ) -> set[tuple[str, str]]:
        """按显式锚点日期及评价前24小时的可能范围限定“另一次”，不按数组位置猜测。"""

        if not anchored_refs or _ANOTHER_UNTIMED_END_PATTERN.search(text) is None:
            return set()
        clue_dates = {
            known_end_by_ref[ref].date()
            for ref in anchored_refs.intersection(known_end_by_ref)
        }
        if record_date is not None:
            # 日精度只能给可能范围；不能把前一天输血的次日评价误当作缺评价。
            clue_dates.update((record_date, record_date - timedelta(days=1)))
        candidates = {
            ref
            for ref, end_time in known_end_by_ref.items()
            if ref not in anchored_refs
            and (end_time.date() in clue_dates if record_time is None else (
                # 同锚点日期但晚于评价的冲突仍属关联待核，不能变成确定缺评价。
                end_time.date() in {
                    known_end_by_ref[anchor].date()
                    for anchor in anchored_refs.intersection(known_end_by_ref)
                }
                or timedelta(0) <= record_time - end_time <= timedelta(hours=24)
            ))
        }
        return candidates

    if not known_end_by_ref:
        return _PosttransfusionEvaluationAssessment(
            "data_gap",
            "transfusion_end_time_unavailable",
            selected_source_document_refs=selected_event_refs(set(event_refs)),
        )

    end_document_refs = selected_event_refs(set(event_refs))
    latest_end = max(known_end_by_ref.values())
    horizon_datetime, horizon_date, horizon_error = _047_evaluation_horizon(documents)
    if horizon_error == "authoritative_time_conflict":
        return _PosttransfusionEvaluationAssessment(
            "data_gap", "posttransfusion_evaluation_horizon_conflict"
        )
    if horizon_date is not None and any(
        _047_window_is_mature(
            end_time,
            horizon_datetime=horizon_datetime,
            horizon_date=horizon_date,
        )[1]
        for end_time in known_end_by_ref.values()
    ):
        return _PosttransfusionEvaluationAssessment(
            "data_gap", "posttransfusion_evaluation_horizon_conflict"
        )
    unusable_evaluation_time = False
    late_evaluation_found = False

    daily_scope = documents.get("__material_scope__", {}).get("daily_course_record")
    daily_absence_proven = daily_scope is None or daily_scope.get("can_judge_clinical_absence") is True

    # 多份独立输血记录按结束事件关联专门后评价；任何笼统评价都不得扇出。
    if len(event_refs) > 1:
        pending = set(event_refs)
        daily_state = _logical_source_state(documents, "daily_course_record")
        if pending and daily_state == "error":
            return _PosttransfusionEvaluationAssessment(
                "technical_error", "source_query_error"
            )
        if pending and daily_state == "unavailable":
            return _PosttransfusionEvaluationAssessment(
                "data_gap", "transfusion_source_unavailable"
            )
        associated_daily: dict[tuple[str, str], tuple[datetime, tuple[str, str] | None]] = {}
        ambiguous_pending_refs: set[tuple[str, str]] = set()
        ambiguous_daily_refs: list[tuple[str, str]] = []
        unusable_daily_event_refs: set[tuple[str, str]] = set()
        unusable_daily_refs: list[tuple[str, str]] = []
        late_evaluation_refs: set[tuple[str, str]] = set()
        late_daily_refs: dict[tuple[str, str], list[tuple[str, str]]] = {}
        unclear_event_refs: set[tuple[str, str]] = set()
        unclear_daily_refs: list[tuple[str, str]] = []
        for source_key, row in ((key, row) for key in ("daily_course_record", "senior_course_record")
                                for row in _source_document_rows(documents, key)):
            text = _row_text(row)
            record_time = _authoritative_047_record_time(row)
            record_date = _authoritative_047_record_date(row)
            daily_ref = (
                (source_key, document_id)
                if (document_id := str(row.get("document_id") or row.get("id") or "").strip())
                else None
            )
            unclear = daily_ref in unclear_effect_refs
            if not unclear and not _course_effect_confirmed(documents, source_key, row, text):
                continue
            if horizon_date is not None and record_time is not None and _047_evaluation_time_is_after_horizon(
                record_time,
                horizon_datetime=horizon_datetime,
                horizon_date=horizon_date,
            ):
                continue
            association = post_links.get((source_key, id(row)))
            anchored_refs = set(association.event_refs).intersection(pending) if association else set()
            possible_refs = (
                set(association.possible_event_refs).intersection(pending)
                if association else set()
            )
            affected_scope_refs = anchored_refs or possible_refs
            anchors = association is not None and (association.explicit or "blood_component" in association.basis)
            if unclear:
                # 语义无法确认仅阻断这份评价真实候选事件的缺失判断；不覆盖其他事件。
                affected_refs = set(affected_scope_refs)
                affected_refs.update(unresolved_another_refs(
                    text, anchored_refs=anchored_refs,
                    record_date=record_date, record_time=record_time,
                ))
                if not affected_refs and not anchors and record_date is None:
                    affected_refs = set(pending)
                unclear_event_refs.update(affected_refs)
                if affected_refs and daily_ref is not None:
                    unclear_daily_refs.append(daily_ref)
                continue
            _, unresolved_end_marker = _transfusion_end_evidence(text)
            association_ambiguous = bool(
                association and association.state == "ambiguous"
            )
            if unresolved_end_marker or association_ambiguous:
                # 歧义只覆盖该文书真实候选事件；例如 B/C 间待定不能抹掉 A 的确定缺失。
                affected_refs = set(affected_scope_refs)
                affected_refs.update(
                    unresolved_another_refs(
                        text,
                        anchored_refs=anchored_refs,
                        record_date=record_date,
                        record_time=record_time,
                    )
                )
                if not affected_refs and not anchors and record_date is None:
                    affected_refs = set(pending)
                if affected_refs:
                    ambiguous_pending_refs.update(affected_refs)
                    if daily_ref is not None:
                        ambiguous_daily_refs.append(daily_ref)
                continue
            if anchors and not anchored_refs:
                if possible_refs:
                    # 强锚点无法完成精确关联时，保留同一候选事件的不确定性；不得把该
                    # 评价当作合格，也不得因此武断发布候选事件“缺评价”。
                    unusable_daily_event_refs.update(possible_refs)
                    if daily_ref is not None:
                        unusable_daily_refs.append(daily_ref)
                continue
            if record_time is None:
                affected_refs = set(affected_scope_refs)
                if not anchors and record_date is None:
                    # 完全无时间也无事件锚点时无法缩小真实候选；若已有日
                    # 精度，possible_event_refs 的空集表示已排除全部事件，禁止再扩散。
                    affected_refs = affected_refs or set(pending)
                if affected_refs:
                    unusable_daily_event_refs.update(affected_refs)
                    if daily_ref is not None:
                        unusable_daily_refs.append(daily_ref)
                continue
            if anchors and anchored_refs.intersection(unknown_end_refs):
                unusable_daily_event_refs.update(anchored_refs.intersection(unknown_end_refs))
                if daily_ref is not None:
                    unusable_daily_refs.append(daily_ref)
            candidate_refs = {
                ref
                for ref, end_time in known_end_by_ref.items()
                if (not anchors or ref in anchored_refs)
                and 0 <= (record_time - end_time).total_seconds() <= 24 * 3600
            }
            if not candidate_refs:
                if anchored_refs:
                    anchored_known = anchored_refs.intersection(known_end_by_ref)
                    if any(
                        record_time < known_end_by_ref[ref]
                        for ref in anchored_known
                    ):
                        unusable_daily_event_refs.update(anchored_known)
                        if daily_ref is not None:
                            unusable_daily_refs.append(daily_ref)
                    else:
                        late_evaluation_refs.update(anchored_known)
                        if daily_ref is not None:
                            for ref in anchored_known:
                                late_daily_refs.setdefault(ref, []).append(daily_ref)
                continue
            if len(candidate_refs) > 1 and candidate_refs.intersection(pending):
                ambiguous_pending_refs.update(candidate_refs.intersection(pending))
                if daily_ref is not None:
                    ambiguous_daily_refs.append(daily_ref)
                continue
            candidate_ref = next(iter(candidate_refs))
            if candidate_ref in pending:
                previous = associated_daily.get(candidate_ref)
                if previous is None or (record_time, daily_ref or ("", "")) < (
                    previous[0],
                    previous[1] or ("", ""),
                ):
                    associated_daily[candidate_ref] = (record_time, daily_ref)
        pending.difference_update(associated_daily)
        # 只从没有本次关联/时间歧义的事件形成确定问题；另一事件未知不抹掉它。
        confirmed = pending - ambiguous_pending_refs - unusable_daily_event_refs - unknown_end_refs - unclear_event_refs
        late = confirmed.intersection(late_evaluation_refs)
        mature_missing = {
            ref for ref in confirmed - late_evaluation_refs
            if not horizon_error and horizon_date is not None
            and _047_window_is_mature(known_end_by_ref[ref], horizon_datetime=horizon_datetime,
                                     horizon_date=horizon_date)[0]
        }
        if not daily_absence_proven:
            mature_missing = set()
        if late or mature_missing:
            selected = late or mature_missing
            refs = tuple(dict.fromkeys(
                evidence_ref for event_ref in event_refs if event_ref in selected
                for evidence_ref in (*selected_event_refs({event_ref}),
                                     *late_daily_refs.get(event_ref, ()))
            ))
            return _PosttransfusionEvaluationAssessment(
                "non_compliant",
                "posttransfusion_evaluation_late" if late else "posttransfusion_evaluation_missing",
                latest_end_time=max(known_end_by_ref[ref] for ref in selected),
                selected_source_document_refs=refs,
            )
        if pending.intersection(unclear_event_refs):
            return _PosttransfusionEvaluationAssessment(
                "data_gap", "semantic_extraction_unresolved",
                selected_source_document_refs=tuple(dict.fromkeys((
                    *selected_event_refs(pending.intersection(unclear_event_refs)),
                    *unclear_daily_refs,
                ))),
            )
        if pending.intersection(ambiguous_pending_refs):
            affected = pending.intersection(ambiguous_pending_refs)
            return _PosttransfusionEvaluationAssessment(
                "data_gap",
                "association_failed",
                selected_source_document_refs=tuple(
                    dict.fromkeys((*selected_event_refs(affected), *ambiguous_daily_refs))
                ),
            )
        if pending.intersection(unknown_end_refs):
            return _PosttransfusionEvaluationAssessment(
                "data_gap",
                "transfusion_end_time_unavailable",
                selected_source_document_refs=selected_event_refs(
                    pending.intersection(unknown_end_refs)
                ),
            )
        if pending.intersection(unusable_daily_event_refs):
            affected = pending.intersection(unusable_daily_event_refs)
            return _PosttransfusionEvaluationAssessment(
                "data_gap",
                "posttransfusion_evaluation_time_unavailable",
                selected_source_document_refs=tuple(
                    dict.fromkeys((*selected_event_refs(affected), *unusable_daily_refs))
                ),
            )
        if pending.intersection(late_evaluation_refs):
            return _PosttransfusionEvaluationAssessment(
                "non_compliant",
                "posttransfusion_evaluation_late",
                latest_end_time=latest_end,
                selected_source_document_refs=end_document_refs,
            )
        if not pending:
            evaluations = associated_daily
            selected_refs = tuple(
                dict.fromkeys(
                    (*end_document_refs, *(ref for _, ref in associated_daily.values() if ref))
                )
            )
            return _PosttransfusionEvaluationAssessment(
                "compliant",
                "posttransfusion_evaluation_complete",
                latest_end_time=latest_end,
                evaluation_time=min(
                    evaluation_time
                    for ref, (evaluation_time, _) in evaluations.items()
                    if known_end_by_ref[ref] == latest_end
                ),
                selected_source_document_refs=selected_refs,
            )
        if not daily_absence_proven:
            return _PosttransfusionEvaluationAssessment("data_gap", "transfusion_source_unavailable")
        if horizon_error:
            return _PosttransfusionEvaluationAssessment(
                "data_gap", "posttransfusion_evaluation_time_unavailable"
            )
        assert horizon_date is not None
        if any(
            _047_window_is_mature(
                known_end_by_ref[ref],
                horizon_datetime=horizon_datetime,
                horizon_date=horizon_date,
            )[0]
            for ref in pending
        ):
            return _PosttransfusionEvaluationAssessment(
                "non_compliant",
                "posttransfusion_evaluation_missing",
                latest_end_time=max(known_end_by_ref[ref] for ref in pending),
                selected_source_document_refs=selected_event_refs(pending),
            )
        return _PosttransfusionEvaluationAssessment(
            "not_applicable",
            "evaluation_window_not_mature",
            latest_end_time=latest_end,
            selected_source_document_refs=end_document_refs,
        )

    single_event_ref = event_refs[0]
    qualified_daily_evaluations: list[tuple[datetime, tuple[str, str] | None]] = []
    unclear_evaluation = False
    for source_key, row in ((key, row) for key in ("daily_course_record", "senior_course_record")
                                for row in _source_document_rows(documents, key)):
        record_time = _authoritative_047_record_time(row)
        record_date = _authoritative_047_record_date(row)
        text = _row_text(row)
        document_id = str(row.get("document_id") or row.get("id") or "").strip()
        unclear = (source_key, document_id) in unclear_effect_refs
        if not unclear and not _course_effect_confirmed(documents, source_key, row, text):
            continue
        association = post_links.get((source_key, id(row)))
        if association is not None and (association.explicit or "blood_component" in association.basis):
            if single_event_ref not in association.event_refs:
                if single_event_ref in association.possible_event_refs:
                    unusable_evaluation_time = True
                # 正文明确评价另一时次输血时，即使落在24小时内也不能借用；仍可能
                # 属于本次时只保留资料不确定性，不能直接发布“缺评价”。
                continue
            if association.state == "ambiguous":
                unusable_evaluation_time = True
                continue
        if (
            record_time is not None
            and horizon_date is not None
            and _047_evaluation_time_is_after_horizon(
                record_time,
                horizon_datetime=horizon_datetime,
                horizon_date=horizon_date,
            )
        ):
            continue
        if record_time is None:
            if (
                record_date is not None
                and association is not None
                and single_event_ref not in association.possible_event_refs
            ):
                # 日精度已能排除本次输血时，该文书与本次无关，不能制造时间缺口。
                continue
            unusable_evaluation_time = True
            continue
        if record_time < latest_end:
            unusable_evaluation_time = True
            continue
        if (record_time - latest_end).total_seconds() <= 24 * 3600:
            if unclear:
                unclear_evaluation = True
                continue
            qualified_daily_evaluations.append(
                (
                    record_time,
                    (source_key, document_id) if document_id else None,
                )
            )
            continue
        late_evaluation_found = True

    if qualified_daily_evaluations:
        selected_daily_time, selected_daily_ref = min(
            qualified_daily_evaluations, key=lambda item: item[0]
        )
        selected_refs = tuple(
            dict.fromkeys(
                (
                    *end_document_refs,
                    *((selected_daily_ref,) if selected_daily_ref is not None else ()),
                )
            )
        )
        return _PosttransfusionEvaluationAssessment(
            "compliant",
            "posttransfusion_evaluation_complete",
            latest_end_time=latest_end,
            evaluation_time=selected_daily_time,
            selected_source_document_refs=selected_refs,
        )
    if unclear_evaluation:
        return _PosttransfusionEvaluationAssessment(
            "data_gap", "semantic_extraction_unresolved",
            selected_source_document_refs=end_document_refs,
        )
    if unusable_evaluation_time:
        return _PosttransfusionEvaluationAssessment(
            "data_gap", "posttransfusion_evaluation_time_unavailable"
        )
    if late_evaluation_found:
        return _PosttransfusionEvaluationAssessment(
            "non_compliant",
            "posttransfusion_evaluation_late",
            latest_end_time=latest_end,
            selected_source_document_refs=end_document_refs,
        )
    if horizon_error:
        return _PosttransfusionEvaluationAssessment(
            "data_gap", "posttransfusion_evaluation_time_unavailable"
        )
    if not daily_absence_proven:
        return _PosttransfusionEvaluationAssessment("data_gap", "transfusion_source_unavailable")
    assert horizon_date is not None
    mature, _ = _047_window_is_mature(
        latest_end,
        horizon_datetime=horizon_datetime,
        horizon_date=horizon_date,
    )
    return _PosttransfusionEvaluationAssessment(
        "non_compliant" if mature else "not_applicable",
        "posttransfusion_evaluation_missing"
        if mature
        else "evaluation_window_not_mature",
        latest_end_time=latest_end,
        selected_source_document_refs=end_document_refs,
    )


def _programmatic_047_status(documents: Mapping[str, Any]) -> tuple[str, str]:
    assessment = _programmatic_047_assessment(documents)
    return assessment.status, assessment.reason_code


@dataclass(frozen=True)
class _Intraoperative048Assessment:
    status: str
    reason_code: str
    display_facts: Mapping[str, Any] | None = None
    selected_refs: tuple[tuple[str, str], ...] = ()
    llm_call_count: int = 0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    api_time: float = 0.0


_048_TEXT_FIELDS = {
    "surgery_record": ("surgery_name", "surgery_process", "content", "record_content", "assembled_text"),
    "anesthesia_record": ("anesthesia_method", "anesthesia_process", "content", "record_content",
                          "assembled_text"),
    "postsurg_firstcourse_record": ("content", "record_content", "assembled_text"),
}
# 仅采用来源已携带的可信手术身份；模型不生成关联键。
_048_OPERATION_KEY_FIELDS = ("surgery_id", "operation_id")


def _048_document_text(source: str, row: Mapping[str, Any]) -> str:
    return _clean(" ".join(
        _clean(row.get(key)) for key in _048_TEXT_FIELDS[source] if _clean(row.get(key))
    ))


async def _intraoperative_048_assessment(
    documents: Mapping[str, Any],
    llm_client: TransfusionLLMClient | None,
) -> _Intraoperative048Assessment:
    """三份术中文书各取实际输注原子事实，再由程序比较成分与剂量。"""

    has_states = isinstance(documents.get("__logical_source_states__"), Mapping)
    states = {
        source: _logical_source_state(documents, source) if has_states else "available"
        for source in INTRAOPERATIVE_SOURCES
    }
    if "error" in states.values():
        return _Intraoperative048Assessment("technical_error", "source_query_error")
    # 只有标题/空正文的文书没有可阅读的临床内容，视同缺失而不是“已核对无输血”。
    rows_by_source = {
        source: [row for row in _source_document_rows(documents, source)
                 if _048_document_text(source, row)]
        for source in INTRAOPERATIVE_SOURCES
    }
    unavailable = sorted(
        source for source, state in states.items() if state in {"unavailable", "missing"}
    )
    if any(len(rows) > 1 for rows in rows_by_source.values()):
        # 多台手术/多份文书尚无可信逐台配对，不静默挑选一份比较。
        return _Intraoperative048Assessment("data_gap", "association_failed")
    operation_keys = {
        key
        for rows in rows_by_source.values()
        for row in rows
        if (key := next((_clean(row.get(field)) for field in _048_OPERATION_KEY_FIELDS
                         if _clean(row.get(field))), ""))
    }
    if len(operation_keys) > 1:
        return _Intraoperative048Assessment("data_gap", "association_failed")
    present_sources = [source for source, rows in rows_by_source.items() if rows]
    if not present_sources:
        # 手术记录与麻醉记录均确实为空才能确认本次无手术中输血；
        # 其中任一来源不可用时不能证明不存在。
        surgical_unavailable = [
            source for source in unavailable
            if source in {"surgery_record", "anesthesia_record"}
        ]
        if surgical_unavailable:
            return _Intraoperative048Assessment(
                "data_gap", "transfusion_comparison_fields_unavailable",
                {"failure_kind": "transfusion_comparison_material_missing",
                 "missing_sources": surgical_unavailable},
            )
        return _Intraoperative048Assessment(
            "not_applicable", "intraoperative_transfusion_fact_absent",
            {"verification_kind": "intraoperative_transfusion_absent",
             "checked_sources": ["surgery_record", "anesthesia_record"]},
        )
    refs = tuple(
        (source, str(rows_by_source[source][0].get("document_id")
                     or rows_by_source[source][0].get("id") or ""))
        for source in present_sources
    )
    docs = [
        IntraoperativeDocument(f"{source}:{ref}", source,
                               _048_document_text(source, rows_by_source[source][0]))
        for source, ref in refs
    ]
    extraction = await extract_intraoperative_transfusion_items(
        docs, llm_client, parse_time=_parse_document_datetime,
    )
    usage = dict(
        llm_call_count=extraction.llm_call_count, prompt_tokens=extraction.prompt_tokens,
        completion_tokens=extraction.completion_tokens, total_tokens=extraction.total_tokens,
        api_time=extraction.api_time,
    )
    if extraction.state != "ready":
        return _Intraoperative048Assessment(extraction.state, extraction.reason_code, **usage)
    facts_by_source = {
        doc.source_type: extraction.facts[doc.document_ref] for doc in docs
    }
    missing_sources = sorted(
        {*unavailable, *(source for source, rows in rows_by_source.items() if not rows)}
    )
    if missing_sources:
        if any(facts.state == "unknown" for facts in facts_by_source.values()):
            return _Intraoperative048Assessment("data_gap", "semantic_extraction_unresolved", **usage)
        if all(facts.state == "absent" for facts in facts_by_source.values()) and not unavailable:
            # 已有文书均确认未术中输血，缺少的只是空来源，仍可确认不适用。
            status, reason, display = evaluate_intraoperative_consistency(facts_by_source)
            return _Intraoperative048Assessment(status, reason, display, **usage)
        # 未接入或缺失的文书不能证明未输血，也无法完成三方一致性比较。
        return _Intraoperative048Assessment(
            "data_gap", "transfusion_comparison_fields_unavailable",
            {"failure_kind": "transfusion_comparison_material_missing",
             "missing_sources": missing_sources},
            **usage,
        )
    status, reason, display = evaluate_intraoperative_consistency(facts_by_source)
    selected = refs if status in {"compliant", "non_compliant"} else ()
    return _Intraoperative048Assessment(status, reason, display, selected, **usage)


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
    findings, suggestion = _SYSTEM_DATA_GAP_MESSAGES.get(
        reason_code, _CONTROLLED_MESSAGES[status]
    )
    if reason_code == "transfusion_order_absent":
        findings = "当前就诊未发现未取消的输血医嘱，本规则不适用。"
        suggestion = ""
    if reason_code == "intraoperative_transfusion_fact_absent":
        findings = "未发现可信的术中输血事实，本规则不适用。"
        suggestion = ""
    item["findings"] = findings
    item["suggestion"] = suggestion
    metadata = dict(item.get("metadata") or {})
    metadata["executor_type"] = executor_type
    if reason_code in _SYSTEM_DATA_GAP_MESSAGES:
        metadata["data_gap_kind"] = "system_data_contract_gap"
        metadata["gap_owner"] = "system_integration"
    item["metadata"] = metadata
    return item


def _customer_display_facts_for_outcome(
    *, rule_id: str, status: str, reason_code: str
) -> Mapping[str, Any] | None:
    """仅投影程序可确定的输血缺口，不回显正文、提示词或模型回答。"""

    if status == "data_gap" and reason_code in _SYSTEM_DATA_GAP_MESSAGES:
        findings, suggestion = _SYSTEM_DATA_GAP_MESSAGES[reason_code]
        return {
            "failure_kind": "system_data_contract_gap",
            "system_gap_reason": reason_code,
            "gap_owner": "system_integration",
            "conclusion": findings,
            "handling_suggestion": suggestion,
        }
    if status != "non_compliant":
        return None
    cases = {
        ("LX0609-07-01-02", "pretransfusion_assessment_missing"): (
            "pretransfusion_assessment",
            ["bloodtrans_record", "blood_application", "course_record"],
        ),
        ("LX0609-07-02-02", "transfusion_purpose_or_indication_missing"): (
            "purpose_or_indication",
            ["bloodtrans_record"],
        ),
        ("LX0609-07-03-01", "posttransfusion_evaluation_missing"): (
            "posttransfusion_evaluation",
            ["bloodtrans_record", "course_record"],
        ),
    }
    detail = cases.get((rule_id, reason_code))
    if detail is None:
        return None
    requirement, checked_sources = detail
    return {
        "failure_kind": "transfusion_requirement_not_documented",
        "requirement": requirement,
        "checked_sources": checked_sources,
    }


def _programmatic_transfusion_display_facts(
    *,
    rule_id: str,
    status: str,
    reason_code: str,
    documents: Mapping[str, Any],
    component_evidence_document_refs: Sequence[str] = (),
    unresolved_component_document_refs: Sequence[str] = (),
    posttransfusion_assessment: _PosttransfusionEvaluationAssessment | None = None,
) -> Mapping[str, Any] | None:
    """从已参与裁决的同一份资料中生成受控事实，不回显正文。"""

    if status not in {"compliant", "non_compliant"}:
        return _customer_display_facts_for_outcome(rule_id=rule_id, status=status, reason_code=reason_code)
    records = _source_document_rows(documents, "bloodtrans_record")
    if rule_id == "LX0609-07-01-02":
        documents = _pre_assessment_documents(documents)
        entries = [
            _row_text(row)
            for source_key in ("bloodtrans_record", "blood_application", "daily_course_record", "senior_course_record")
            for row in _source_document_rows(documents, source_key)
        ]
        joined = " ".join(entries)
        checked = {
            "application_reason": bool(
                _PRETRANSFUSION_PURPOSE_PATTERN.search(joined)
                or _PRETRANSFUSION_CORE_PATTERNS[0].search(joined)
            ),
            "laboratory_indicator": bool(
                _PRETRANSFUSION_CORE_PATTERNS[1].search(joined)
            ),
        }
        missing = sorted(key for key, present in checked.items() if not present)
        payload: dict[str, Any] = {
            "performed_transfusion_confirmed": True,
            "checked_fields": sorted(checked),
            "missing_fields": missing,
        }
        source_refs = [
            *_source_document_refs(
                _source_document_rows(documents, "blood_application"),
                source_type="blood_application",
                identity_fields=("application_id", "document_id", "id"),
            )[:1],
            *_source_document_refs(
                records, source_type="bloodtrans_record"
            )[:1],
        ]
        if source_refs:
            payload["source_document_refs"] = source_refs
        if status == "compliant":
            payload["verification_kind"] = "pretransfusion_assessment_complete"
        else:
            payload["failure_kind"] = (
                "pretransfusion_assessment_missing"
                if reason_code == "pretransfusion_assessment_missing"
                else "pretransfusion_assessment_incomplete"
            )
        return payload
    if rule_id == "LX0609-07-02-01":
        payload: dict[str, Any] = {
            "verification_kind" if status == "compliant" else "failure_kind": (
                "transfusion_course_record_present"
                if status == "compliant"
                else "transfusion_course_record_missing"
            ),
            "performed_transfusion_confirmed": True,
            "checked_sources": ["bloodtrans_record", "daily_course_record"],
        }
        if status == "compliant":
            payload["record_count"] = len(records)
        # 045 的状态逐条读取专用输血记录；无论合规或缺项，都把这批实际
        # 核对的文书交给同一 snapshot 的逐行引用绑定，日常病程不参与选择。
        source_document_ids = [
            document_id
            for record in records
            if (document_id := str(record.get("document_id", record.get("id", ""))).strip())
        ]
        if source_document_ids:
            if documents.get("__course_source_refs__"):
                payload["source_document_refs"] = documents["__course_source_refs__"]
            else:
                payload["source_document_ids"] = list(dict.fromkeys(source_document_ids))
        return payload
    if rule_id == "LX0609-07-02-02":
        llm_component_refs = set(component_evidence_document_refs)
        unresolved_component_refs = set(unresolved_component_document_refs)
        checks_by_record = []
        for index, record in enumerate(records, start=1):
            text = _row_text(record)
            checks_by_record.append(
                _transfusion_046_field_checks(
                    text,
                    component_confirmed=(
                        _transfusion_record_ref(record, index) in llm_component_refs
                    ),
                    component_unresolved=_transfusion_record_ref(record, index) in unresolved_component_refs,
                )
            )
        field_names = (
            "reason_or_indication", "start_and_end_time", "component", "dose",
            "process_observation", "reaction_and_handling", "clinical_effect",
        )
        checked = [field for field in field_names if any(item[field] is not None for item in checks_by_record)]
        missing = sorted(field for field in field_names if any(item[field] is False for item in checks_by_record))
        missing_field_record_counts = {
            field: sum(1 for item in checks_by_record if item[field] is False)
            for field in missing
        }
        incomplete_record_count = sum(
            1 for item in checks_by_record if any(value is False for value in item.values())
        )
        payload = {
            "performed_transfusion_confirmed": True,
            "record_count": len(records),
            "incomplete_record_count": incomplete_record_count,
            "checked_fields": sorted(checked),
            "missing_fields": missing,
            "missing_field_record_counts": missing_field_record_counts,
        }
        unresolved_count = sum(1 for item in checks_by_record if item["component"] is None)
        if unresolved_count:
            payload["unresolved_component_record_count"] = unresolved_count
        source_document_ids = [
            document_id
            for record, record_checks in zip(records, checks_by_record, strict=True)
            if status == "compliant" or any(value is False for value in record_checks.values())
            if (document_id := str(record.get("document_id", record.get("id", ""))).strip())
        ]
        if source_document_ids:
            if documents.get("__course_source_refs__"):
                payload["source_document_refs"] = [ref for ref in documents["__course_source_refs__"]
                                                   if ref["source_document_id"] in source_document_ids]
            else:
                payload["source_document_ids"] = list(dict.fromkeys(source_document_ids))
        payload["verification_kind" if status == "compliant" else "failure_kind"] = (
            "transfusion_course_record_complete"
            if status == "compliant"
            else "transfusion_course_record_incomplete"
        )
        return payload
    if rule_id == "LX0609-07-03-01":
        assessment = posttransfusion_assessment or _programmatic_047_assessment(
            documents
        )
        if status not in {"compliant", "non_compliant"}:
            # 权威评价时间缺失属于资料缺口，不能继续投影为“未找到评价”的
            # 临床缺项事实；技术失败也同样不得投影临床缺项。
            return None
        facts: dict[str, Any] = {
            "performed_transfusion_confirmed": True,
            "threshold_hours": 24,
            "checked_sources": ["bloodtrans_record", "daily_course_record"],
        }
        source_refs = [
            {"source_type": source_type, "source_document_id": document_id}
            for source_type, document_id in assessment.selected_source_document_refs
        ]
        if source_refs:
            facts["source_document_refs"] = source_refs
        if assessment.latest_end_time is not None:
            facts["transfusion_end_time"] = assessment.latest_end_time.isoformat(sep=" ")
        if status == "compliant":
            if (
                assessment.status != "compliant"
                or assessment.latest_end_time is None
                or assessment.evaluation_time is None
            ):
                raise ValueError("047 compliant outcome requires qualified evaluation time")
            facts["evaluation_time"] = assessment.evaluation_time.isoformat(sep=" ")
            facts["elapsed_hours"] = round(
                (
                    assessment.evaluation_time - assessment.latest_end_time
                ).total_seconds()
                / 3600,
                2,
            )
        facts["verification_kind" if status == "compliant" else "failure_kind"] = (
            "posttransfusion_evaluation_complete"
            if status == "compliant"
            else "posttransfusion_evaluation_missing"
        )
        return facts
    return None


def _authoritative_record_time(row: Mapping[str, Any]) -> datetime | None:
    """读取可用于时限判定的文书完成时间，不接受适配层的非权威回退。"""

    explicit_time = authoritative_document_time_value(row)
    if explicit_time:
        return _parse_document_datetime(explicit_time)
    if str(row.get("time_basis") or "").strip() == "record_time":
        return _parse_document_datetime(row.get("authored_at"))
    return None


def _authoritative_047_record_time(row: Mapping[str, Any]) -> datetime | None:
    """047 小时级判定仅接受有时刻精度的权威记录/提交时间。"""

    explicit_time = authoritative_posttransfusion_time_value(row)
    if explicit_time:
        return parse_precise_transfusion_datetime(explicit_time)
    return None


def _authoritative_047_record_date(row: Mapping[str, Any]) -> date | None:
    """保留 047 权威文书时间的日精度，不构造小时级时刻。"""

    return parse_transfusion_document_date(
        authoritative_posttransfusion_time_value(row)
    )


def _047_date_may_fall_in_window(record_date: date, end_time: datetime) -> bool:
    day_start = datetime.combine(record_date, datetime.min.time())
    day_end = day_start + timedelta(days=1)
    return day_end > end_time and day_start <= end_time + timedelta(hours=24)


CoursePresenceClassifier = Callable[
    [Sequence[Mapping[str, Any]]], Awaitable[TransfusionCoursePresenceResult]
]


def _structured_transfusion_performed(row: Mapping[str, Any]) -> bool:
    """输血结构化记录中的实际输注时间是实施事实的权威来源。"""

    return _parse_document_datetime(row.get("transfution_datetime")) is not None


async def _performed_source_state(
    *,
    documents: Mapping[str, Any] | None,
    institute_id: str,
    patient_id: str,
    visit_id: str,
    source_schema: str | None,
    classify_course_records: CoursePresenceClassifier,
    evidence_materials: Luxian0609EvidenceMaterialStore | None = None,
    include_course_sources: bool = False,
) -> tuple[str, str]:
    """确认本次就诊是否实际输血，返回 (状态, 原因)。

    原因只在技术错误或来源截断导致的资料不足时填写，其余为空串。

    结构化实际输注时间可直接证明实施；否则专用输血记录是否记载实际输注
    与 045/046 共用同一语义分类结果，不按正文长度或关键词推断。计划、拒绝、
    延期、取消等记录存在但不能证明实施时保持资料不足，不降为“无输血”。
    """

    rows_by_source: dict[str, list[Mapping[str, Any]]] = {}
    failed = False
    truncated = False

    def available_without_query(source_key: str) -> bool:
        return evidence_materials is not None or (
            isinstance(documents, Mapping) and isinstance(documents.get(source_key), list)
        )

    def load(source_key: str) -> list[Mapping[str, Any]]:
        nonlocal failed, truncated
        if source_key in rows_by_source:
            return rows_by_source[source_key]
        rows: list[Mapping[str, Any]] = []
        # 同一证据会话的快照材料是权威来源；仅旧入口没有快照时，才采用
        # bundle 已携带的同次就诊来源，缺少时再按需查库。
        if evidence_materials is not None:
            try:
                rows = [dict(row) for row in evidence_materials.rows(source_key)]
            except EvidenceMaterialTruncated:
                failed = truncated = True
            except Exception:
                failed = True
        elif isinstance(documents, Mapping) and isinstance(documents.get(source_key), list):
            rows = list(_source_document_rows(documents, source_key))
        elif not all((institute_id, patient_id, visit_id)):
            failed = True
        else:
            try:
                rows = read_luxian_0609_native_source_rows(
                    source_key=source_key,
                    institute_id=institute_id,
                    patient_id=patient_id,
                    visit_id=visit_id,
                    source_schema=source_schema,
                )
            except Exception:
                failed = True
        rows_by_source[source_key] = rows
        return rows

    def structured_performed() -> bool:
        return any(_structured_transfusion_performed(row) for row in load("bloodtrans_record"))

    if available_without_query("bloodtrans_record") and structured_performed():
        return "present", ""
    record_rows = load("bloodtrans_record")
    if record_rows:
        presence = await classify_course_records(record_rows)
        if presence.state == "present":
            return "present", ""
        if structured_performed():
            return "present", ""
        if presence.state == "technical_error":
            return "technical_error", presence.reason_code or "model_invalid_output"
        return "data_gap", ""
    if structured_performed():
        return "present", ""
    # 专用记录为空不等于未实施；普通/上级病程同样可以记载真实输注。
    # 关键词仅筛选语义候选，实施与否仍由受控抽取决定。
    course_rows = [
        row for key in ("daily_course_record", "senior_course_record")
        if include_course_sources and isinstance(documents, Mapping) and isinstance(documents.get(key), list)
        for row in select_transfusion_course_candidates(load(key))
    ]
    if course_rows:
        presence = await classify_course_records(course_rows)
        if presence.state == "present":
            return "present", ""
        if presence.state == "technical_error":
            return "technical_error", presence.reason_code or "model_invalid_output"
        if presence.state == "data_gap":
            return "data_gap", ""
    if include_course_sources and any(
        re.search(r"输血|输(?:注|入)?(?:红细胞|悬浮红|去白|血浆|血小板|冷沉淀|全血)", _clean(row.get("order_name")))
        for key in _ORDER_TRIGGER_SOURCES if isinstance(documents, Mapping) and isinstance(documents.get(key), list)
        for row in load(key)
        if not any(word in _clean(row.get("order_status")) for word in ("取消", "作废", "撤销", "未执行"))
    ):
        return "data_gap", ""
    if failed or any(rows_by_source.get(key) for key in _TRIGGER_SOURCES):
        return "data_gap", "transfusion_source_truncated" if truncated else ""
    return "absent", ""


@budget_guarded_executor
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
    evidence_materials: Luxian0609EvidenceMaterialStore | None = None,
    evidence_snapshot: Luxian0609EvidenceSnapshot | None = None,
    decision_rule_ids: Sequence[str] = (),
) -> NativeTransfusionExecutionResult:
    """先证明本次存在专用输血来源，再按客户规则逐条裁剪执行。"""

    requested = {str(rule_id or "").strip().upper() for rule_id in rule_ids}
    selected = tuple(rule_id for rule_id in TRANSFUSION_RULE_IDS if rule_id in requested)
    typed_requested = {
        str(rule_id or "").strip().upper() for rule_id in decision_rule_ids
    }
    if (
        not typed_requested.issubset(_TYPED_DECISION_RULE_IDS)
        or not typed_requested.issubset(set(selected))
    ):
        raise ValueError("unsupported typed transfusion rule scope")
    typed_selected = tuple(
        rule_id for rule_id in selected if rule_id in typed_requested
    )
    if typed_selected and (
        type(evidence_snapshot) is not Luxian0609EvidenceSnapshot
        or type(evidence_materials) is not Luxian0609EvidenceMaterialStore
        or evidence_materials.snapshot_hash != evidence_snapshot.snapshot_hash
    ):
        raise ValueError("typed transfusion rules require one evidence session")
    if not selected:
        return NativeTransfusionExecutionResult((), ())
    results: list[dict[str, Any]] = []
    decisions: list[RuleDecision] = []
    customer_display_facts: list[tuple[str, Mapping[str, Any]]] = []

    def emit_outcome(
        rule_id: str,
        status: str,
        reason_code: str,
        *,
        executor_type: str,
        display_facts: Mapping[str, Any] | None = None,
        selected_source_document_refs: Sequence[tuple[str, str]] = (),
    ) -> None:
        if status == "technical_error":
            # 诊断日志：只记规则、原因码与出错代码行，不含病历或模型内容。
            logger.warning(
                "LX0609 输血族技术错误: rule_id=%s reason_code=%s call_line=%s",
                rule_id, reason_code, sys._getframe(1).f_lineno,
            )
        outcome = _TransfusionRuleOutcome(
            rule_id=rule_id,
            status=status,
            reason_code=reason_code,
            executor_type=executor_type,
        )
        controlled_facts = display_facts or _customer_display_facts_for_outcome(
            rule_id=rule_id, status=status, reason_code=reason_code
        )
        if rule_id in _ORDER_TRIGGER_RULES and controlled_facts is not None:
            controlled_facts = dict(controlled_facts)
            controlled_facts.pop("performed_transfusion_confirmed", None)
            if order_identities:
                controlled_facts["transfusion_order_present"] = True
        selected_document_refs: tuple[str, ...] = ()
        fact_identities = (
            _selected_document_identities(
                rule_id=rule_id,
                display_facts=controlled_facts,
            )
            if rule_id in typed_requested and controlled_facts is not None
            else ()
        )
        selected_identities = tuple(
            dict.fromkeys(
                (*fact_identities, *selected_source_document_refs, *order_identities)
            )
        )
        if rule_id in typed_requested and selected_identities:
            assert evidence_snapshot is not None
            assert evidence_materials is not None
            try:
                selected_document_refs = _material_document_refs_for_selected_identities(
                    selected_identities=selected_identities,
                    snapshot=evidence_snapshot,
                    materials=evidence_materials,
                )
            except ValueError:
                # 执行器声称已选中的文书无法绑定到同一请求快照，属于合同/实现
                # 错误，不得投影成临床资料缺口；同时丢弃原客户事实。
                outcome = _TransfusionRuleOutcome(
                    rule_id=rule_id,
                    status="technical_error",
                    reason_code="snapshot_mismatch",
                    executor_type=executor_type,
                )
                controlled_facts = None
        if rule_id in typed_requested:
            assert evidence_snapshot is not None
            try:
                decision = (
                    _typed_decision_from_outcome(
                        outcome=outcome,
                        snapshot=evidence_snapshot,
                        selected_document_refs=selected_document_refs,
                    )
                )
            except ValueError:
                # RuleDecision 的 fact_refs 是有上限的受控合同。逐笔文书过多时
                # 不能静默丢弃已选证据，也不能让单条规则异常中断同一规则族；
                # 降为本规则技术错误并清理不可投影的客户事实。
                outcome = _TransfusionRuleOutcome(
                    rule_id=rule_id,
                    status="technical_error",
                    reason_code="executor_exception",
                    executor_type=executor_type,
                )
                controlled_facts = None
                decision = _typed_decision_from_outcome(
                    outcome=outcome,
                    snapshot=evidence_snapshot,
                )
            decisions.append(decision)
        if controlled_facts is not None:
            customer_display_facts.append((rule_id, controlled_facts))
        if rule_id not in typed_requested:
            results.append(
                _result(
                    outcome.rule_id,
                    outcome.status,
                    outcome.reason_code,
                    executor_type=outcome.executor_type,
                )
            )

    legacy_documents = _documents(evidence_payload)
    typed_material_by_rule: dict[
        str, tuple[Mapping[str, Any] | None, str, str]
    ] = {}
    if typed_selected:
        assert evidence_snapshot is not None
        assert evidence_materials is not None
        for typed_rule_id in typed_selected:
            if typed_rule_id in _CONSERVATIVE_DATA_GAP_RULE_IDS:
                typed_material_by_rule[typed_rule_id] = (
                    _typed_conservative_material_status(
                        snapshot=evidence_snapshot,
                        materials=evidence_materials,
                        rule_id=typed_rule_id,
                    )
                )
            else:
                typed_material_by_rule[typed_rule_id] = (
                    _typed_documents_from_evidence_session(
                        snapshot=evidence_snapshot,
                        materials=evidence_materials,
                        rule_id=typed_rule_id,
                    )
                )
    wrappers_by_id = {
        str(wrapper.get("rule_id") or wrapper.get("rule_code") or "").strip().upper(): wrapper
        for wrapper in wrapper_rules
        if isinstance(wrapper, Mapping)
    }
    llm_call_count = prompt_tokens = completion_tokens = total_tokens = 0
    api_time = 0.0
    order_trigger_cache: dict[bool, TransfusionOrderTriggerResult] = {}
    course_cache: dict[
        tuple[tuple[str, str], ...], TransfusionCoursePresenceResult
    ] = {}
    course_tasks: dict[
        tuple[tuple[str, str], ...], asyncio.Task[TransfusionCoursePresenceResult]
    ] = {}
    performed_cache: dict[bool, tuple[str, str]] = {}
    performed_tasks: dict[object, asyncio.Task[tuple[str, str]]] = {}
    order_trigger_tasks: dict[
        bool, asyncio.Task[TransfusionOrderTriggerResult]
    ] = {}
    intraoperative_task: asyncio.Task[_Intraoperative048Assessment] | None = None
    order_identities: tuple[tuple[str, str], ...] = ()
    performance_event_cache: dict[tuple[tuple[str, str], ...], tuple[str, Any]] = {}
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        parallel_prefetch_enabled = False
    else:
        parallel_prefetch_enabled = True

    async def classify_course_records(
        rows: Sequence[Mapping[str, Any]],
    ) -> TransfusionCoursePresenceResult:
        # 同一批专用记录在门控、045/046 与 047 之间只做一次语义核验。
        nonlocal llm_call_count, prompt_tokens, completion_tokens, total_tokens, api_time
        key = tuple(
            (str(row.get("document_id", row.get("id"))), _row_text(row)) for row in rows
        )
        if not parallel_prefetch_enabled:
            if key not in course_cache:
                presence = await classify_transfusion_course_records(rows, llm_client)
                course_cache[key] = presence
                llm_call_count += presence.llm_call_count
                prompt_tokens += presence.prompt_tokens
                completion_tokens += presence.completion_tokens
                total_tokens += presence.total_tokens
                api_time += presence.api_time
            return course_cache[key]
        if key not in course_tasks:
            async def load_course_presence() -> TransfusionCoursePresenceResult:
                nonlocal llm_call_count, prompt_tokens, completion_tokens, total_tokens, api_time
                presence = await classify_transfusion_course_records(rows, llm_client)
                course_cache[key] = presence
                llm_call_count += presence.llm_call_count
                prompt_tokens += presence.prompt_tokens
                completion_tokens += presence.completion_tokens
                total_tokens += presence.total_tokens
                api_time += presence.api_time
                return presence

            course_tasks[key] = asyncio.create_task(load_course_presence())
        return await course_tasks[key]

    def material_for_rule(
        rule_id: str,
    ) -> tuple[bool, Mapping[str, Any] | None, str, str]:
        typed_rule = rule_id in typed_requested
        if typed_rule:
            documents, material_status, material_reason = typed_material_by_rule[rule_id]
            return typed_rule, documents, material_status, material_reason
        documents = legacy_documents
        return typed_rule, documents, "", ""

    def performed_task_key(*, rule_id: str, typed_rule: bool) -> object:
        # 仅043/047扩展实施来源，不改变知情同意等其他质控点的门禁。
        return rule_id if typed_rule else ("legacy", rule_id in {"LX0609-07-01-01", "LX0609-07-03-01"})

    def get_performed_task(
        *,
        rule_id: str,
        typed_rule: bool,
        documents: Mapping[str, Any] | None,
    ) -> asyncio.Task[tuple[str, str]]:
        key = performed_task_key(rule_id=rule_id, typed_rule=typed_rule)
        if key not in performed_tasks:
            performed_tasks[key] = asyncio.create_task(
                _performed_source_state(
                    documents=documents,
                    institute_id=str(institute_id or ""),
                    patient_id=str(patient_id or ""),
                    visit_id=str(visit_id or ""),
                    source_schema=source_schema,
                    classify_course_records=classify_course_records,
                    evidence_materials=evidence_materials,
                    include_course_sources=rule_id in {"LX0609-07-01-01", "LX0609-07-03-01"},
                )
            )
        return performed_tasks[key]

    async def resolve_performance_events(
        record_rows: Sequence[Mapping[str, Any]], *, dedicated_performance_source: bool,
    ) -> tuple[str, Any]:
        """从输血记录正文抽取实施事件及开始时间；同批记录在本次执行内只抽取一次。

        返回 ("ok", 事件行) / ("technical_error", 原因码) / ("unresolved", None)。
        07-01-01 与 07-01-02 共用（首页输血表缺失时的后备）。
        """

        nonlocal llm_call_count, prompt_tokens, completion_tokens, total_tokens, api_time
        key = tuple(
            (str(row.get("document_id") or row.get("id") or ""), str(authoritative_document_time_value(row) or ""))
            for row in record_rows
        ) + (("dedicated", str(dedicated_performance_source)),)
        if key in performance_event_cache:
            return performance_event_cache[key]
        from .extended_document.transfusion_performance_extraction import extract_transfusion_performance

        performance = await extract_transfusion_performance(
            [{**row, "record_content": _row_text(row), "record_time": _authoritative_record_time(row)} for row in record_rows], llm_client,
        )
        llm_call_count += performance.llm_call_count
        prompt_tokens += performance.prompt_tokens
        completion_tokens += performance.completion_tokens
        total_tokens += performance.total_tokens
        api_time += performance.api_time
        if performance.technical_failure:
            # 实施抽取的模型调用失败不能交付为资料不足。
            outcome: tuple[str, Any] = ("technical_error", performance.reason_code)
        else:
            events = []
            unresolved = False
            for row, state, event_time in zip(record_rows, performance.states, performance.event_times):
                if state == "performed":
                    # 普通/上级病程的完成时间不能替代实际开始输血时间。
                    value = event_time or (_authoritative_record_time(row) if dedicated_performance_source else None)
                    if value is not None:
                        events.append({**row, "transfution_datetime": value.isoformat(sep=" ")})
                    else:
                        unresolved = True
                elif state == "unknown":
                    unresolved = True
            outcome = ("unresolved", None) if unresolved or not events else ("ok", events)
        performance_event_cache[key] = outcome
        return outcome

    def get_order_trigger_task(
        *,
        typed_rule: bool,
        documents: Mapping[str, Any],
    ) -> asyncio.Task[TransfusionOrderTriggerResult]:
        if typed_rule not in order_trigger_tasks:
            async def load_order_trigger() -> TransfusionOrderTriggerResult:
                nonlocal llm_call_count, prompt_tokens, completion_tokens, total_tokens, api_time
                result = await classify_transfusion_orders(
                    [
                        (source_key, row)
                        for source_key in _ORDER_TRIGGER_SOURCES
                        for row in _source_document_rows(documents, source_key)
                    ],
                    llm_client,
                )
                order_trigger_cache[typed_rule] = result
                llm_call_count += result.llm_call_count
                prompt_tokens += result.prompt_tokens
                completion_tokens += result.completion_tokens
                total_tokens += result.total_tokens
                api_time += result.api_time
                return result

            order_trigger_tasks[typed_rule] = asyncio.create_task(
                load_order_trigger()
            )
        return order_trigger_tasks[typed_rule]

    def get_intraoperative_task(
        documents: Mapping[str, Any],
    ) -> asyncio.Task[_Intraoperative048Assessment]:
        nonlocal intraoperative_task
        if intraoperative_task is None:
            async def load_intraoperative() -> _Intraoperative048Assessment:
                nonlocal llm_call_count, prompt_tokens, completion_tokens, total_tokens, api_time
                assessment = await _intraoperative_048_assessment(
                    documents,
                    llm_client,
                )
                llm_call_count += assessment.llm_call_count
                prompt_tokens += assessment.prompt_tokens
                completion_tokens += assessment.completion_tokens
                total_tokens += assessment.total_tokens
                api_time += assessment.api_time
                return assessment

            intraoperative_task = asyncio.create_task(load_intraoperative())
        return intraoperative_task

    # 三类门控读取相互独立。先启动并共同等待，避免病程、医嘱和术中文书的
    # 模型耗时在单病历内串成关键路径；底层 HTTP 仍受全局并发门控约束。
    prefetch_tasks: set[asyncio.Task[Any]] = set()
    if parallel_prefetch_enabled:
        for prefetch_rule_id in selected:
            typed_rule, documents, material_status, _ = material_for_rule(
                prefetch_rule_id
            )
            if material_status:
                continue
            if prefetch_rule_id == "LX0609-07-04-01":
                if isinstance(documents, Mapping):
                    prefetch_tasks.add(get_intraoperative_task(documents))
                continue
            if prefetch_rule_id in _ORDER_TRIGGER_RULES:
                if isinstance(documents, Mapping) and all(
                    isinstance(documents.get(key), list)
                    for key in _ORDER_TRIGGER_SOURCES
                ):
                    prefetch_tasks.add(
                        get_order_trigger_task(
                            typed_rule=typed_rule,
                            documents=documents,
                        )
                    )
                continue
            prefetch_tasks.add(
                get_performed_task(
                    rule_id=prefetch_rule_id,
                    typed_rule=typed_rule,
                    documents=documents,
                )
            )

    if prefetch_tasks:
        try:
            await asyncio.gather(*prefetch_tasks)
        except BaseException:
            for task in prefetch_tasks:
                if not task.done():
                    task.cancel()
            await asyncio.gather(*prefetch_tasks, return_exceptions=True)
            raise

    for rule_id in selected:
        order_identities = ()
        typed_rule, documents, typed_material_status, typed_material_reason = (
            material_for_rule(rule_id)
        )
        if typed_material_status:
            emit_outcome(
                rule_id,
                typed_material_status,
                typed_material_reason,
                executor_type="program",
            )
            continue
        if rule_id == "LX0609-07-04-01":
            # 术中输血只看本次手术的三份文书；病房输血记录不能证明或否定术中实施。
            if not isinstance(documents, Mapping):
                emit_outcome(rule_id, "data_gap", "transfusion_projection_unavailable",
                             executor_type="program")
                continue
            if parallel_prefetch_enabled:
                assessment_048 = await get_intraoperative_task(documents)
            else:
                assessment_048 = await _intraoperative_048_assessment(
                    documents,
                    llm_client,
                )
                llm_call_count += assessment_048.llm_call_count
                prompt_tokens += assessment_048.prompt_tokens
                completion_tokens += assessment_048.completion_tokens
                total_tokens += assessment_048.total_tokens
                api_time += assessment_048.api_time
            emit_outcome(
                rule_id,
                assessment_048.status,
                assessment_048.reason_code,
                executor_type="llm" if assessment_048.llm_call_count else "program",
                display_facts=assessment_048.display_facts,
                selected_source_document_refs=assessment_048.selected_refs,
            )
            continue
        if rule_id in _ORDER_TRIGGER_RULES:
            if not isinstance(documents, Mapping):
                emit_outcome(rule_id, "data_gap", "transfusion_source_unavailable", executor_type="program")
                continue
            # 旧入口也必须明确提供医嘱来源，不能将漏传解释成无医嘱。
            if any(not isinstance(documents.get(key), list) for key in _ORDER_TRIGGER_SOURCES):
                emit_outcome(rule_id, "data_gap", "transfusion_source_unavailable", executor_type="program")
                continue
            if parallel_prefetch_enabled:
                order_result = await get_order_trigger_task(
                    typed_rule=typed_rule,
                    documents=documents,
                )
            else:
                if typed_rule not in order_trigger_cache:
                    order_result = await classify_transfusion_orders(
                        [
                            (source_key, row)
                            for source_key in _ORDER_TRIGGER_SOURCES
                            for row in _source_document_rows(documents, source_key)
                        ],
                        llm_client,
                    )
                    order_trigger_cache[typed_rule] = order_result
                    llm_call_count += order_result.llm_call_count
                    prompt_tokens += order_result.prompt_tokens
                    completion_tokens += order_result.completion_tokens
                    total_tokens += order_result.total_tokens
                    api_time += order_result.api_time
                order_result = order_trigger_cache[typed_rule]
            source_state = order_result.state
            performed_error = ""
            order_identities = order_result.selected_identities
            if source_state == "technical_error":
                emit_outcome(rule_id, "technical_error", order_result.reason_code or "model_invalid_output", executor_type="llm")
                continue

        else:
            if parallel_prefetch_enabled:
                performed_state = await get_performed_task(
                    rule_id=rule_id,
                    typed_rule=typed_rule,
                    documents=documents,
                )
            elif typed_rule:
                performed_state = await _performed_source_state(
                    documents=documents,
                    institute_id=str(institute_id or ""),
                    patient_id=str(patient_id or ""),
                    visit_id=str(visit_id or ""),
                    source_schema=source_schema,
                    classify_course_records=classify_course_records,
                    evidence_materials=evidence_materials,
                    include_course_sources=rule_id in {"LX0609-07-01-01", "LX0609-07-03-01"},
                )
            else:
                include_courses = rule_id in {"LX0609-07-01-01", "LX0609-07-03-01"}
                if include_courses not in performed_cache:
                    performed_cache[include_courses] = await _performed_source_state(
                        documents=legacy_documents,
                        institute_id=str(institute_id or ""),
                        patient_id=str(patient_id or ""),
                        visit_id=str(visit_id or ""),
                        source_schema=source_schema,
                        classify_course_records=classify_course_records,
                        evidence_materials=evidence_materials,
                        include_course_sources=include_courses,
                    )
                performed_state = performed_cache[include_courses]
            source_state, performed_error = performed_state
            if source_state == "technical_error":
                emit_outcome(rule_id, "technical_error", performed_error, executor_type="llm")
                continue
        if source_state != "present":
            emit_outcome(
                rule_id,
                "not_applicable" if source_state == "absent" else "data_gap",
                (
                    ("transfusion_order_absent" if rule_id in _ORDER_TRIGGER_RULES else "transfusion_fact_absent")
                    if source_state == "absent"
                    else performed_error or "transfusion_source_unavailable"
                ),
                executor_type="program",
            )
            continue
        if typed_rule and rule_id in _CONSERVATIVE_DATA_GAP_RULE_IDS:
            assert evidence_snapshot is not None
            conservative_status, conservative_reason = (
                _typed_conservative_contract_outcome(
                    snapshot=evidence_snapshot,
                    rule_id=rule_id,
                )
            )
            emit_outcome(
                rule_id,
                conservative_status,
                conservative_reason,
                executor_type="program",
            )
            continue
        if documents is None:
            emit_outcome(
                rule_id,
                "data_gap",
                "transfusion_projection_unavailable",
                executor_type="program",
            )
            continue
        if rule_id in {"LX0609-11-03-01", "LX0609-11-03-02", "LX0609-07-01-01"}:
            if (rule_id == "LX0609-07-01-01" and not _transfusion_event_rows(documents)
                    and _logical_source_state(documents, "labtest_item_report") not in {"missing", "unavailable", "error"}):
                record_rows = _source_document_rows(documents, "bloodtrans_record")
                dedicated_performance_source = bool(record_rows)
                if not record_rows:
                    record_rows = [row for key in ("daily_course_record", "senior_course_record")
                                   for row in select_transfusion_course_candidates(_source_document_rows(documents, key))]
                performance_state, performance_value = await resolve_performance_events(
                    record_rows, dedicated_performance_source=dedicated_performance_source,
                )
                if performance_state == "technical_error":
                    emit_outcome(rule_id, "technical_error", performance_value, executor_type="llm")
                    continue
                if performance_state != "ok":
                    emit_outcome(rule_id, "data_gap", "transfusion_time_unavailable", executor_type="llm")
                    continue
                documents = {**documents, "performed_transfusion_events": performance_value}
            programmatic = {
                "LX0609-11-03-01": _programmatic_041_status,
                "LX0609-11-03-02": _programmatic_042_status,
                "LX0609-07-01-01": lambda docs: evaluate_pretransfusion_nine_items(
                    docs, required_items=_PRETRANSFUSION_REGULAR_ITEMS,
                ),
            }[rule_id](documents)
            status, reason_code, display_facts = programmatic
            if reason_code == "pretransfusion_lab_results_absent":
                display_facts = _customer_display_facts_for_outcome(
                    rule_id=rule_id, status=status, reason_code="pretransfusion_item_contract_unavailable",
                )
            emit_outcome(
                rule_id,
                status,
                reason_code,
                executor_type="program",
                display_facts=display_facts,
            )
            continue
        if not typed_rule and rule_id in _CONSERVATIVE_DATA_GAP_RULE_IDS:
            projection_failure = _required_projection_failure(rule_id, documents)
            if projection_failure is not None and projection_failure[0] == "technical_error":
                conservative_status, conservative_reason = projection_failure
            else:
                conservative_status = "data_gap"
                conservative_reason = _CONSERVATIVE_DATA_GAP_REASONS[rule_id]
            emit_outcome(
                rule_id,
                conservative_status,
                conservative_reason,
                executor_type="program",
            )
            continue
        # 各规则先尝试确定性判定；047只认专门后评价，输血记录仅作事件锚点，
        # 只有不能定论时才检查日常病程等辅助投影并进入裁剪模型。
        if rule_id == "LX0609-07-01-02":
            # 按 07-01-01 同一实施抽取从专用输血记录正文取开始输注时间
            # （第六轮 C03、复验 C04/C08：输血记录写明开始时间仍判“缺实际输血时间”）。
            # 只用专用输血记录；同批记录与 07-01-01 共用一次抽取。抽不到时间时交由原评估判资料不足。
            # 申请单和输血前病程都需要同一次实际输注的时间，统一核验原始文书。
            bloodtrans_rows = _source_document_rows(documents, "bloodtrans_record")
            if (
                not _transfusion_event_rows(documents)
                and bloodtrans_rows
            ):
                performance_state, performance_value = await resolve_performance_events(
                    bloodtrans_rows, dedicated_performance_source=True,
                )
                if performance_state == "technical_error":
                    emit_outcome(rule_id, "technical_error", performance_value, executor_type="llm")
                    continue
                if performance_state == "ok":
                    documents = {**documents, "performed_transfusion_events": performance_value}
            programmatic_status = _programmatic_044_status(documents)
            reason_candidate = build_pretransfusion_reason_candidate(documents)
            needs_reason_semantics = (
                programmatic_status is not None
                and len(programmatic_status) == 3
                and programmatic_status[0:2]
                == (
                    "non_compliant",
                    "pretransfusion_assessment_incomplete",
                )
                and list(programmatic_status[2].get("missing_fields") or [])
                == ["application_reason"]
                and reason_candidate is not None
            )
            if needs_reason_semantics:
                if llm_client is None:
                    emit_outcome(
                        rule_id,
                        "technical_error",
                        "model_transport_error",
                        executor_type="program",
                    )
                    continue
                checked = await _recheck_transfusion_semantics(
                    _044_reason_prompt(reason_candidate), llm_client,
                    _parse_044_reason_response,
                    lambda payload: _validated_044_reason_state(payload, candidate=reason_candidate),
                )
                llm_call_count += checked.calls
                prompt_tokens += checked.usage[0]
                completion_tokens += checked.usage[1]
                total_tokens += checked.usage[2]
                api_time += checked.usage[3]
                reason_state = checked.state
                if reason_state is None:
                    emit_outcome(
                        rule_id,
                        "technical_error",
                        checked.reason_code,
                        executor_type="llm",
                    )
                    continue
                if reason_state == "uncertain":
                    emit_outcome(
                        rule_id,
                        "evaluation_unknown",
                        "semantic_output_unknown",
                        executor_type="llm",
                    )
                    continue
                reason_present = reason_state == "present"
                emit_outcome(
                    rule_id,
                    "compliant" if reason_present else "non_compliant",
                    (
                        "pretransfusion_assessment_complete"
                        if reason_present
                        else "pretransfusion_assessment_incomplete"
                    ),
                    executor_type="llm",
                    display_facts=reason_candidate.display_facts(
                        reason_present=reason_present
                    ),
                )
                continue
            if programmatic_status is not None:
                status, reason_code = programmatic_status[:2]
                if (
                    status == "data_gap"
                    and reason_code == "pretransfusion_assessment_source_unavailable"
                ):
                    # 来源不可用属于系统资料缺口，不能生成临床不完整事实。
                    display_facts = _customer_display_facts_for_outcome(
                        rule_id=rule_id, status=status, reason_code=reason_code,
                    )
                else:
                    display_facts = (
                        programmatic_status[2]
                        if len(programmatic_status) == 3
                        else _programmatic_transfusion_display_facts(
                            rule_id=rule_id,
                            status=status,
                            reason_code=reason_code,
                            documents=documents,
                        )
                    )
                emit_outcome(
                    rule_id,
                    status,
                    reason_code,
                    executor_type="program",
                    display_facts=display_facts,
                )
                continue
        if rule_id in {"LX0609-07-02-01", "LX0609-07-02-02"}:
            course_state = _logical_source_state(documents, "bloodtrans_record")
            if course_state == "error":
                emit_outcome(rule_id, "technical_error", "source_query_error", executor_type="program")
                continue
            if course_state not in {"available", "empty"}:
                emit_outcome(rule_id, "data_gap", "transfusion_course_source_unavailable", executor_type="program")
                continue
            if not _source_document_rows(documents, "bloodtrans_record"):
                selected_courses = []
                selected_refs = []
                course_failure = None
                course_source_unavailable = False
                for source_key in ("daily_course_record", "senior_course_record"):
                    source_rows = _source_document_rows(documents, source_key)
                    # 07-02-01 与 07-02-02 同样不能把截断/读取失败的病程来源当作“没有输血病程”。
                    source_state = _logical_source_state(documents, source_key)
                    if source_state == "missing" and (
                        isinstance(documents.get(source_key), list)
                        or not isinstance(
                            documents.get("__logical_source_states__"), Mapping
                        )
                    ):
                        # Legacy payloads predate logical source-state metadata.
                        source_state = "available" if source_rows else "empty"
                    if source_state == "error":
                        course_failure = TransfusionCoursePresenceResult(
                            "technical_error", reason_code="source_query_error"
                        )
                        break
                    if source_state not in {"available", "empty"}:
                        course_source_unavailable = True
                        continue
                    candidates = list(select_transfusion_course_candidates(source_rows))
                    if not candidates:
                        continue
                    course_presence = await classify_course_records(candidates)
                    if course_presence.state in {"data_gap", "technical_error"}:
                        course_failure = course_presence
                        break
                    for row in candidates:
                        if str(row.get("document_id", row.get("id"))) in course_presence.valid_document_ids:
                            selected_courses.append({**row, "__source_key__": source_key})
                            selected_refs.extend(_source_document_refs([row], source_type=source_key, limit=None))
                if course_failure is not None:
                    emit_outcome(rule_id, course_failure.state,
                                 course_failure.reason_code or "transfusion_course_record_content_unavailable",
                                 executor_type="llm")
                    continue
                if not selected_courses and course_source_unavailable:
                    emit_outcome(
                        rule_id,
                        "data_gap",
                        "transfusion_course_source_unavailable",
                        executor_type="program",
                    )
                    continue
                if selected_courses:
                    # 临床内核复用逐份核查；证据始终绑定原始物理来源。
                    documents = {**documents, "bloodtrans_record": selected_courses,
                                 "__course_source_refs__": selected_refs}
            presence = await classify_course_records(
                _source_document_rows(documents, "bloodtrans_record")
            )
            if presence.state in {"data_gap", "technical_error"}:
                emit_outcome(rule_id, presence.state,
                             (presence.reason_code or "model_invalid_output") if presence.state == "technical_error"
                             else "transfusion_course_record_content_unavailable", executor_type="llm")
                continue
            if presence.state == "absent":
                missing = rule_id == "LX0609-07-02-01"
                status = "non_compliant" if missing else "data_gap"
                reason = "transfusion_course_record_missing" if missing else "transfusion_course_record_content_unavailable"
                emit_outcome(rule_id, status, reason, executor_type="program",
                             display_facts=_programmatic_transfusion_display_facts(
                                 rule_id=rule_id, status=status, reason_code=reason, documents=documents))
                continue
            valid_ids = set(presence.valid_document_ids)
            documents = dict(documents)
            documents["bloodtrans_record"] = [row for row in _source_document_rows(documents, "bloodtrans_record")
                                              if str(row.get("document_id", row.get("id"))) in valid_ids]
            if not documents["bloodtrans_record"]:
                emit_outcome(rule_id, "technical_error", "snapshot_mismatch", executor_type="program")
                continue
            documents["__course_presence_verified__"] = True
        if rule_id == "LX0609-07-02-01":
            programmatic_status = ("compliant", "transfusion_course_record_present")
            if programmatic_status is not None:
                status, reason_code = programmatic_status
                emit_outcome(
                    rule_id,
                    status,
                    reason_code,
                    executor_type="program",
                    display_facts=_programmatic_transfusion_display_facts(
                        rule_id=rule_id,
                        status=status,
                        reason_code=reason_code,
                        documents=documents,
                    ),
                )
                continue
        if rule_id == "LX0609-07-02-02":
            programmatic_status = _programmatic_046_status(documents)
            if programmatic_status is not None:
                status, reason_code = programmatic_status
                emit_outcome(
                    rule_id,
                    status,
                    reason_code,
                    executor_type="program",
                    display_facts=_programmatic_transfusion_display_facts(
                        rule_id=rule_id,
                        status=status,
                        reason_code=reason_code,
                        documents=documents,
                        unresolved_component_document_refs=tuple(
                            ref for ref, _ in _046_component_llm_candidates(documents)
                        ),
                    ),
                )
                continue
            candidates = _046_component_llm_candidates(documents)
            if candidates:
                # 保留既有单文书补核限额（最多一次原始调用及一次绑定纠正）。
                # 超过覆盖能力是程序未完成，不是医学缺项或P5 token预算拒绝。
                assertions: dict[str, str] = {}
                failure_reason = "execution_program_error"
                checked = _SemanticRecheck(None, failure_reason, 0, (0, 0, 0, 0.0))
                if len(candidates) == 1:
                    document_ref, record_text = candidates[0]
                    if llm_client is None:
                        checked = _SemanticRecheck(None, "model_transport_error", 0, (0, 0, 0, 0.0))
                    else:
                        budget_failures: list[Any] = []
                        with budget_rule_scope(budget_failures.append):
                            checked = await _recheck_transfusion_semantics(
                                _046_component_prompt(document_ref=document_ref, record_text=record_text), llm_client,
                                _parse_046_component_response,
                                lambda payload: _validated_046_component_assertion(
                                    payload, document_ref=document_ref, record_text=record_text),
                            )
                        if budget_failures:
                            # P5准入失败仍由规则承接；保留独立确定缺陷，不改成临床DG。
                            checked = _SemanticRecheck(None, budget_failures[0].code, checked.calls, checked.usage)
                    if checked.state is not None:
                        assertions[document_ref] = checked.state
                llm_call_count += checked.calls
                prompt_tokens += checked.usage[0]
                completion_tokens += checked.usage[1]
                total_tokens += checked.usage[2]
                api_time += checked.usage[3]
                unresolved_refs = tuple(ref for ref, _ in candidates
                                        if assertions.get(ref) not in {"explicit", "not_explicit"})
                # 成分肯定只更新对应文书；重新汇总每份记录的确定缺项。
                outcome = _programmatic_046_status(documents, component_assertions=assertions)
                if outcome is None:
                    outcome = ("data_gap", "semantic_extraction_unresolved") if checked.state == "unclear" else (
                        "technical_error", checked.reason_code)
                status, reason_code = outcome
                display_facts = (
                    {"failure_kind": "transfusion_component_unresolved",
                     "record_count": len(_source_document_rows(documents, "bloodtrans_record")),
                     "unresolved_component_record_count": len(unresolved_refs)}
                    if status == "data_gap" else _programmatic_transfusion_display_facts(
                        rule_id=rule_id, status=status, reason_code=reason_code, documents=documents,
                        component_evidence_document_refs=tuple(ref for ref, state in assertions.items() if state == "explicit"),
                        unresolved_component_document_refs=unresolved_refs,
                    )
                )
                emit_outcome(
                    rule_id, status, reason_code, executor_type="llm" if checked.calls else "program",
                    display_facts=display_facts,
                )
                continue
        if rule_id == "LX0609-07-03-01":
            # 只有被确认为实际输注过程的专用记录才能提供结束时间和评价；
            # 计划、取消等记录既不产生评价义务，也不能抹掉已知的实际输血事件。
            record_rows = _source_document_rows(documents, "bloodtrans_record")
            if record_rows:
                presence = await classify_course_records(record_rows)
                if presence.state == "technical_error":
                    emit_outcome(rule_id, "technical_error",
                                 presence.reason_code or "model_invalid_output", executor_type="llm")
                    continue
                if presence.state == "data_gap":
                    # 有记录不能确定是否为实际输注，可能缺少一次输血的结束与评价。
                    emit_outcome(rule_id, "data_gap",
                                 "transfusion_performance_unresolved", executor_type="llm")
                    continue
                valid_ids = set(presence.valid_document_ids)
                documents = dict(documents)
                documents["bloodtrans_record"] = [
                    row for row in record_rows
                    if str(row.get("document_id", row.get("id"))) in valid_ids
                ]
            assessment = _programmatic_047_assessment(documents)
            executor_type = "program"
            if (
                assessment.status == "non_compliant"
                and assessment.reason_code in {"posttransfusion_evaluation_missing", "posttransfusion_evaluation_late"}
                and (effect_candidates := _047_effect_candidates(documents))
            ):
                # 是否评价了输血效果是语义判断：病程只直认带方向的指标比较，其余窗口内病程交受控模型确认，
                # 既不由词表闭世界判缺，也不凭“输血后复查/效果好”等宽词判合规（2026-10-22）。
                effects = await confirm_posttransfusion_effects(effect_candidates, llm_client)
                llm_call_count += effects.llm_call_count
                prompt_tokens += effects.prompt_tokens
                completion_tokens += effects.completion_tokens
                total_tokens += effects.total_tokens
                api_time += effects.api_time
                if effects.state != "ready":
                    emit_outcome(rule_id, effects.state, effects.reason_code, executor_type="llm")
                    continue
                executor_type = "llm"
                documents = {**documents, _047_MODEL_CONFIRMED_EFFECTS_KEY: effects.confirmed}
                assessment = _programmatic_047_assessment(
                    documents, unclear_effect_refs=effects.unclear,
                )
            status, reason_code = assessment.status, assessment.reason_code
            emit_outcome(
                rule_id,
                status,
                reason_code,
                executor_type=executor_type,
                selected_source_document_refs=assessment.selected_source_document_refs,
                display_facts=_programmatic_transfusion_display_facts(
                    rule_id=rule_id,
                    status=status,
                    reason_code=reason_code,
                    documents=documents,
                    posttransfusion_assessment=assessment,
                ),
            )
            continue
        projection_failure = _required_projection_failure(rule_id, documents)
        if projection_failure is not None:
            status, reason_code = projection_failure
            emit_outcome(
                rule_id,
                status,
                reason_code,
                executor_type="program",
            )
            continue
        wrapper = wrappers_by_id.get(rule_id)
        context = _context(rule_id, documents)
        if wrapper is None or not str(wrapper.get("custom_prompt") or "").strip() or not context:
            emit_outcome(
                rule_id,
                "data_gap",
                "transfusion_prompt_input_unavailable",
                executor_type="program",
            )
            continue
        if llm_client is None:
            emit_outcome(
                rule_id,
                "technical_error",
                "model_transport_error",
                executor_type="program",
            )
            continue
        llm_call_count += 1
        try:
            response = await llm_client.generate(_prompt(wrapper, context=context))
        except Exception as error:
            emit_outcome(
                rule_id,
                "technical_error",
                luxian_0609_llm_call_failure_reason(error),
                executor_type="llm",
            )
            continue
        prompt, completion, total, elapsed = _usage(response)
        prompt_tokens += prompt
        completion_tokens += completion
        total_tokens += total
        api_time += elapsed
        is_compliant = _parse_is_compliant(response)
        if is_compliant is None:
            emit_outcome(
                rule_id,
                "technical_error",
                "model_invalid_output",
                executor_type="llm",
            )
            continue
        status = "compliant" if is_compliant else "non_compliant"
        emit_outcome(
            rule_id,
            status,
            "transfusion_customer_prompt",
            executor_type="llm",
        )

    return _finalize_execution_result(
        results=tuple(results),
        decisions=tuple(decisions),
        customer_display_facts=tuple(customer_display_facts),
        planned_rule_ids=selected,
        llm_call_count=llm_call_count,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        total_tokens=total_tokens,
        api_time=api_time,
    )
