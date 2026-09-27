"""LX0609 输血族原生执行：专用来源事实门控后逐规则裁剪判定。"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta
import json
import re
import unicodedata
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
from .pretransfusion_assessment import (
    PretransfusionReasonCandidate,
    build_pretransfusion_reason_candidate,
    evaluate_structured_pretransfusion_application,
)
from .source_evidence_reader import read_luxian_0609_native_source_rows
from .source_registry import (
    resolve_luxian_0609_controlled_fact_source_keys,
    resolve_luxian_0609_decision_support_source_keys,
    resolve_luxian_0609_rule_sources,
)


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
_TYPED_EVALUATOR_VERSION = "transfusion-ruledecision-shadow-v1"

# 049 仍缺少可受控关联的收费数量，因此旧的直接执行入口继续保守返回 DATA_GAP；
# 新建客户任务会在任务入口明确暂停该规则，不会把此系统缺口交付为客户质控结论。
_CONSERVATIVE_DATA_GAP_RULE_IDS = frozenset({"LX0609-07-04-02"})
_CONSERVATIVE_DATA_GAP_REASONS = {
    "LX0609-07-04-02": "billing_linkage_source_unavailable",
}

_TRIGGER_SOURCES = ("mr_bloodtrans", "bloodtrans_record")
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
    ("hbsag", ("乙肝表面抗原", "hbsag")),
    ("hbsab", ("乙肝表面抗体", "抗-hbs", "hbsab")),
    ("hbeag", ("乙肝e抗原", "hbeag")),
    ("hbeab", ("乙肝e抗体", "抗-hbe", "hbeab")),
    ("hbcab", ("乙肝核心抗体", "抗-hbc", "hbcab")),
    ("hcv", ("丙肝", "抗-hcv", "hcv")),
    ("hiv", ("艾滋", "hiv")),
    ("syphilis", ("梅毒", "tp", "trust", "rpr")),
    ("alt", ("谷丙转氨酶", "丙氨酸氨基转移酶", "alt")),
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
_SURGERY_TRANSFUSION_PATTERN = re.compile(
    r"(?:术中|手术中).{0,80}(?:输血|输注.{0,12}(?:红细胞|血浆|血小板|全血))"
)
_POSTOP_TRANSFUSION_PATTERN = re.compile(
    r"输血|输注|红细胞|血浆|血小板|全血"
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
    ),
    "LX0609-07-01-02": ("bloodtrans_record", "blood_application", "daily_course_record"),
    "LX0609-07-02-01": ("bloodtrans_record", "daily_course_record"),
    "LX0609-07-02-02": ("bloodtrans_record", "daily_course_record"),
    "LX0609-07-03-01": ("bloodtrans_record", "daily_course_record"),
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
    "surgery_record": ("surgery_record",),
    "anesthesia_record": ("anesthesia_record",),
    "postsurg_firstcourse_record": ("postsurg_firstcourse_record",),
    # medical_order 仅用于识别来源 ERROR；保守规则不会读取其内容推断输血医嘱。
    "inpat_nondrug_order": ("inpat_nondrug_order", "medical_order"),
    "inpat_bill_item": ("inpat_bill_item",),
}


def _typed_rule_source_keys(rule_id: str) -> frozenset[str]:
    logical_sources = set(_TRIGGER_SOURCES)
    logical_sources.update(_RULE_CONTEXT_SOURCES[rule_id])
    physical_sources = set(_TRIGGER_SOURCES)
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
        str(row.get(field) or "").strip() == document_id
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
        source_gap = "source_unavailable" in outcome.reason_code
        authoritative_time_gap = (
            outcome.rule_id == "LX0609-07-03-01"
            and outcome.reason_code == "posttransfusion_evaluation_time_unavailable"
        )
        authoritative_time_conflict = (
            outcome.rule_id == "LX0609-07-03-01"
            and outcome.reason_code == "posttransfusion_evaluation_horizon_conflict"
        )
        association_gap = (
            outcome.rule_id == "LX0609-07-03-01"
            and outcome.reason_code == "association_failed"
        )
        dimensions = (
            (
                ApplicabilityState.UNKNOWN
                if source_gap
                else ApplicabilityState.APPLICABLE
            ),
            EvidenceState.DATA_GAP,
            QcDirection.UNKNOWN,
            (
                "source_unavailable"
                if source_gap
                else "authoritative_time_missing"
                if authoritative_time_gap
                else "authoritative_time_conflict"
                if authoritative_time_conflict
                else "association_failed"
                if association_gap
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
                "source_query_error",
                "snapshot_mismatch",
                "model_transport_error",
                "model_invalid_output",
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
        evaluator_version=_TYPED_EVALUATOR_VERSION,
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

    # 输血事实锚点的两个来源属于同一个已批准 trigger contract。缺少观察是
    # snapshot 接线错误；查询错误/不可用则保持既有四态失败语义。
    for source_key in _TRIGGER_SOURCES:
        observation = observation_by_source.get(source_key)
        if observation is None:
            return None, "technical_error", "snapshot_mismatch"
        if observation.query_state.value == "error":
            return None, "technical_error", "source_query_error"
        if (
            observation.query_state.value == "unavailable"
            or observation.completeness.value == "truncated"
        ):
            return None, "data_gap", "transfusion_source_unavailable"

    documents: dict[str, Any] = {}
    try:
        # performed-state 会从同一个材料仓读取该结构化来源；这里先证明可读。
        for source_key in _TRIGGER_SOURCES:
            materials.rows(source_key)
    except Exception:
        return None, "technical_error", "snapshot_mismatch"

    # 结构化输注事件只作为同次就诊内的关联锚点，不进入模型上下文。
    documents["mr_bloodtrans"] = [
        dict(row) for row in materials.rows("mr_bloodtrans")
    ]
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
    raw_rows = documents.get("mr_bloodtrans")
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
            _structured_or_labeled_value(row, fields=fields, labels=labels)
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
    return _clean(
        row.get("item_name")
        or row.get("item_code")
        or row.get("item_abbreviation")
        or row.get("content")
    ).lower()


def _lab_item_alias_matches(key: str, alias: str) -> bool:
    normalized = alias.lower()
    if normalized.isascii() and normalized.isalnum():
        return re.search(
            rf"(?<![a-z0-9]){re.escape(normalized)}(?![a-z0-9])",
            key,
        ) is not None
    return normalized in key


def resolve_pretransfusion_required_item(row: Mapping[str, Any]) -> str | None:
    """返回输血前九项中该检验行命中的受控项目；其余行不参与九项判定。"""

    key = _lab_item_key(row)
    for item, aliases in _PRETRANSFUSION_REQUIRED_ITEMS:
        if any(_lab_item_alias_matches(key, alias) for alias in aliases):
            return item
    return None


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
    raw_event_rows = _source_document_rows(documents, "mr_bloodtrans")
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
        item: [] for item, _ in _PRETRANSFUSION_REQUIRED_ITEMS
    }
    for row in rows:
        if (item := resolve_pretransfusion_required_item(row)) is not None:
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
        "required_items": [item for item, _ in _PRETRANSFUSION_REQUIRED_ITEMS],
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
            "checked_items": [item for item, _ in _PRETRANSFUSION_REQUIRED_ITEMS],
            "latest_test_time": latest.isoformat(sep=" "),
            "transfusion_time": event_times[-1].isoformat(sep=" "),
            "abo_present": abo_present,
            "rh_present": rh_present,
            "antibody_screen_present": antibody_present,
        }
    )
    return "compliant", "pretransfusion_items_complete", base_facts


def _context(rule_id: str, documents: Mapping[str, Any]) -> str:
    parts: list[str] = []
    for source_key in _RULE_CONTEXT_SOURCES[rule_id]:
        for index, content in enumerate(_source_rows(documents, source_key), start=1):
            parts.append(f"[{source_key}-{index}] {content}")
    return "\n".join(parts)[:_MAX_CONTEXT_CHARS]


def _programmatic_044_status(
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
                sourced_entries.append((source_key, row, entry[:_MAX_ROW_CHARS]))
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
        for source_key in ("blood_application", "daily_course_record")
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
        return "non_compliant", "pretransfusion_assessment_missing"
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
) -> dict[str, bool]:
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
        "component": bool(
            _TRANSFUSION_COMPONENT_PATTERN.search(entry) or component_confirmed
        ),
        "dose": bool(_TRANSFUSION_DOSE_PATTERN.search(entry)),
        "process_observation": bool(_TRANSFUSION_OBSERVATION_PATTERN.search(entry)),
        "reaction_and_handling": bool(_TRANSFUSION_REACTION_PATTERN.search(entry)),
    }


def _transfusion_record_ref(record: Mapping[str, Any], index: int) -> str:
    """只标识本次输血记录，不把文书正文或其他来源传给模型。"""

    return _clean(record.get("document_id")) or f"bloodtrans_record-{index}"


def _046_component_llm_candidate(
    documents: Mapping[str, Any],
) -> tuple[str, str] | None:
    """仅在全部其他字段齐备、唯一成分字段未确定时允许一次模型调用。"""

    rows = _source_document_rows(documents, "bloodtrans_record")
    candidates: list[tuple[str, str]] = []
    for index, record in enumerate(rows, start=1):
        entry = _row_text(record)
        if not _is_substantive_transfusion_course_entry(entry):
            return None
        checks = _transfusion_046_field_checks(entry)
        if checks["component"]:
            continue
        if not all(present for name, present in checks.items() if name != "component"):
            return None
        candidates.append((_transfusion_record_ref(record, index), entry))
    # 一次事实提取不能安全覆盖多份待判文书；多候选保持现有确定性不合规。
    return candidates[0] if len(candidates) == 1 else None


def _programmatic_046_status(
    documents: Mapping[str, Any],
) -> tuple[str, str] | None:
    entries = tuple(_source_entries(documents, "bloodtrans_record", limit=None))
    if entries and any(
        _TRANSFUSION_COURSE_INCOMPLETE_PATTERN.search(entry) for entry in entries
    ):
        return "non_compliant", "transfusion_course_record_incomplete"
    if _046_component_llm_candidate(documents) is not None:
        return None
    if entries and all(_is_complete_transfusion_course_entry(entry) for entry in entries):
        return "compliant", "transfusion_course_record_complete"
    if entries and all(
        _is_substantive_transfusion_course_entry(entry)
        and not (
            _PRETRANSFUSION_PURPOSE_PATTERN.search(entry)
            or _PRETRANSFUSION_CORE_PATTERNS[0].search(entry)
        )
        for entry in entries
    ):
        return "non_compliant", "transfusion_purpose_or_indication_missing"
    if entries:
        # 来源完整且已有输血病程正文时，字段核对的缺项本身就是本规则要判定
        # 的“不完整”，不能再交给只返回布尔值、无法给出字段事实的通用模型。
        return "non_compliant", "transfusion_course_record_incomplete"
    return None


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
    if payload.get("application_ref") != candidate.application_ref:
        return None
    state = payload.get("reason_state") or ""
    quote = payload.get("evidence_quote") or ""
    if state == "present":
        return state if quote and quote in candidate.application_text else None
    if state in {"absent", "uncertain"}:
        return state if not quote or quote in candidate.application_text else None
    return None


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

    if payload.get("document_ref") != document_ref:
        return None
    quote = payload.get("quote") or ""
    component_text = payload.get("component_text") or ""
    assertion = payload.get("assertion") or ""
    if not quote or quote not in record_text:
        return None
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
            return None
    elif component_text:
        return None
    return assertion


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


def _parse_document_datetime(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        return value.replace(tzinfo=None) if value.tzinfo is not None else value
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
        parsed = datetime.fromisoformat(candidate)
    except ValueError:
        return None
    return parsed.replace(tzinfo=None) if parsed.tzinfo is not None else parsed


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
    horizon_datetime = _parse_document_datetime(row.get("horizon_datetime"))
    raw_date = _clean(row.get("horizon_date"))
    horizon_date: date | None = None
    if raw_date:
        try:
            horizon_date = date.fromisoformat(raw_date)
        except ValueError:
            return None, None, "authoritative_time_missing"
    if horizon_datetime is not None and horizon_date is not None:
        if horizon_datetime.date() != horizon_date:
            return None, None, "authoritative_time_conflict"
    elif horizon_datetime is not None:
        horizon_date = horizon_datetime.date()
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
) -> _PosttransfusionEvaluationAssessment:
    """按输血结束后24小时窗口判定，评价正文必须有可用的完成时间。"""

    end_rows: list[tuple[datetime, bool, datetime | None, tuple[str, str] | None]] = []
    unresolved_end_marker = False
    for row in _source_document_rows(documents, "bloodtrans_record"):
        text = _row_text(row)
        events, row_unresolved = _transfusion_end_evidence(text)
        unresolved_end_marker = unresolved_end_marker or row_unresolved
        if not events:
            continue
        row_explicit_missing_evaluation = False
        ordered_events = sorted(events, key=lambda event: event[1])
        for index, (_, _, marker_end) in enumerate(ordered_events[:-1]):
            next_marker_start = ordered_events[index + 1][1]
            row_explicit_missing_evaluation = (
                row_explicit_missing_evaluation
                or _POSTTRANSFUSION_MISSING_PATTERN.search(
                    text[marker_end:next_marker_start]
                )
                is not None
            )
        last_end, _, last_marker_end = max(events, key=lambda event: event[0])
        last_tail = text[last_marker_end : last_marker_end + 360]
        row_explicit_missing_evaluation = (
            row_explicit_missing_evaluation
            or _POSTTRANSFUSION_MISSING_PATTERN.search(last_tail) is not None
        )
        evaluation_time = _authoritative_record_time(row)
        end_rows.append(
            (
                last_end,
                (
                    not row_explicit_missing_evaluation
                    and _has_clinical_posttransfusion_evaluation(last_tail)
                ),
                evaluation_time,
                (
                    ("bloodtrans_record", document_id)
                    if (document_id := str(row.get("document_id") or row.get("id") or "").strip())
                    else None
                ),
            )
        )

    if unresolved_end_marker or not end_rows:
        return _PosttransfusionEvaluationAssessment(
            "data_gap", "transfusion_end_time_unavailable"
        )
    end_document_refs = tuple(
        dict.fromkeys(ref for _, _, _, ref in end_rows if ref is not None)
    )
    latest_end = max(end_time for end_time, _, _, _ in end_rows)
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
        for end_time, _, _, _ in end_rows
    ):
        return _PosttransfusionEvaluationAssessment(
            "data_gap", "posttransfusion_evaluation_horizon_conflict"
        )
    qualified_evaluations: list[tuple[datetime, datetime, tuple[str, str] | None]] = []
    qualified_by_index: dict[int, tuple[datetime, tuple[str, str] | None]] = {}
    pending_indices: list[int] = []
    unusable_indices: set[int] = set()
    unusable_evaluation_time = False
    late_evaluation_found = False
    late_evaluation_indices: set[int] = set()
    for index, (end_time, has_evaluation, evaluation_time, document_ref) in enumerate(end_rows):
        if not has_evaluation:
            pending_indices.append(index)
            continue
        if evaluation_time is None or evaluation_time < end_time:
            pending_indices.append(index)
            unusable_indices.add(index)
            unusable_evaluation_time = True
            continue
        if horizon_date is not None and _047_evaluation_time_is_after_horizon(
            evaluation_time,
            horizon_datetime=horizon_datetime,
            horizon_date=horizon_date,
        ):
            pending_indices.append(index)
            continue
        if (evaluation_time - end_time).total_seconds() <= 24 * 3600:
            qualified_evaluations.append((end_time, evaluation_time, document_ref))
            qualified_by_index[index] = (evaluation_time, document_ref)
        else:
            late_evaluation_found = True
            late_evaluation_indices.add(index)
            pending_indices.append(index)

    if len(qualified_evaluations) == len(end_rows):
        latest_evaluation_time = min(
            evaluation_time
            for end_time, evaluation_time, _ in qualified_evaluations
            if end_time == latest_end
        )
        return _PosttransfusionEvaluationAssessment(
            "compliant",
            "posttransfusion_evaluation_complete",
            latest_end_time=latest_end,
            evaluation_time=latest_evaluation_time,
            selected_source_document_refs=end_document_refs,
        )

    # 多份独立输血记录按结束事件关联日常病程；任何笼统评价都不得扇出。
    if len(end_rows) > 1:
        pending = set(pending_indices)
        daily_state = _logical_source_state(documents, "daily_course_record")
        if pending and daily_state == "error":
            return _PosttransfusionEvaluationAssessment(
                "technical_error", "source_query_error"
            )
        if pending and daily_state == "unavailable":
            return _PosttransfusionEvaluationAssessment(
                "data_gap", "transfusion_source_unavailable"
            )
        associated_daily: dict[int, tuple[datetime, tuple[str, str] | None]] = {}
        ambiguous_pending_indices: set[int] = set()
        ambiguous_daily_refs: list[tuple[str, str]] = []
        unusable_daily_indices: set[int] = set()
        unusable_daily_refs: list[tuple[str, str]] = []
        for row in _source_document_rows(documents, "daily_course_record"):
            text = _row_text(row)
            if not (
                _TRANSFUSION_CONTEXT_PATTERN.search(text)
                and _has_clinical_posttransfusion_evaluation(text)
            ):
                continue
            record_time = _authoritative_record_time(row)
            daily_ref = (
                ("daily_course_record", document_id)
                if (document_id := str(row.get("document_id") or row.get("id") or "").strip())
                else None
            )
            if horizon_date is not None and record_time is not None and _047_evaluation_time_is_after_horizon(
                record_time,
                horizon_datetime=horizon_datetime,
                horizon_date=horizon_date,
            ):
                continue
            anchors, unresolved_anchor = _transfusion_end_evidence(text)
            anchored_indices = {
                index
                for anchor_time, _, _ in anchors
                for index, (end_time, _, _, _) in enumerate(end_rows)
                if anchor_time == end_time
            }
            if unresolved_anchor:
                affected_indices = set(pending)
                if affected_indices:
                    ambiguous_pending_indices.update(affected_indices)
                    if daily_ref is not None:
                        ambiguous_daily_refs.append(daily_ref)
                continue
            if len({anchor_time for anchor_time, _, _ in anchors}) > 1:
                affected_indices = anchored_indices.intersection(pending)
                if affected_indices:
                    ambiguous_pending_indices.update(affected_indices)
                    if daily_ref is not None:
                        ambiguous_daily_refs.append(daily_ref)
                continue
            if anchors and not anchored_indices:
                continue
            if record_time is None:
                affected_indices = anchored_indices.intersection(pending)
                if not anchors:
                    affected_indices = set(pending)
                if affected_indices:
                    unusable_daily_indices.update(affected_indices)
                    if daily_ref is not None:
                        unusable_daily_refs.append(daily_ref)
                continue
            candidate_indices = {
                index
                for index, (end_time, _, _, _) in enumerate(end_rows)
                if (not anchors or index in anchored_indices)
                and 0 <= (record_time - end_time).total_seconds() <= 24 * 3600
            }
            if not candidate_indices:
                if anchored_indices.intersection(pending):
                    anchored_pending = anchored_indices.intersection(pending)
                    if any(
                        record_time < end_rows[index][0]
                        for index in anchored_pending
                    ):
                        unusable_daily_indices.update(anchored_pending)
                        if daily_ref is not None:
                            unusable_daily_refs.append(daily_ref)
                    else:
                        late_evaluation_indices.update(anchored_pending)
                continue
            if len(candidate_indices) > 1 and candidate_indices.intersection(pending):
                ambiguous_pending_indices.update(candidate_indices.intersection(pending))
                if daily_ref is not None:
                    ambiguous_daily_refs.append(daily_ref)
                continue
            candidate_index = next(iter(candidate_indices))
            if candidate_index in pending:
                previous = associated_daily.get(candidate_index)
                if previous is None or (record_time, daily_ref or ("", "")) < (
                    previous[0],
                    previous[1] or ("", ""),
                ):
                    associated_daily[candidate_index] = (record_time, daily_ref)
        pending.difference_update(associated_daily)
        if pending.intersection(ambiguous_pending_indices):
            return _PosttransfusionEvaluationAssessment(
                "data_gap",
                "association_failed",
                selected_source_document_refs=tuple(
                    dict.fromkeys((*end_document_refs, *ambiguous_daily_refs))
                ),
            )
        if pending.intersection(unusable_indices | unusable_daily_indices):
            return _PosttransfusionEvaluationAssessment(
                "data_gap",
                "posttransfusion_evaluation_time_unavailable",
                selected_source_document_refs=tuple(
                    dict.fromkeys((*end_document_refs, *unusable_daily_refs))
                ),
            )
        if pending.intersection(late_evaluation_indices):
            return _PosttransfusionEvaluationAssessment(
                "non_compliant",
                "posttransfusion_evaluation_late",
                latest_end_time=latest_end,
                selected_source_document_refs=end_document_refs,
            )
        if not pending:
            evaluations = dict(qualified_by_index)
            evaluations.update(
                {
                    index: (evaluation_time, daily_ref)
                    for index, (evaluation_time, daily_ref) in associated_daily.items()
                }
            )
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
                    for index, (evaluation_time, _) in evaluations.items()
                    if end_rows[index][0] == latest_end
                ),
                selected_source_document_refs=selected_refs,
            )
        if horizon_error:
            return _PosttransfusionEvaluationAssessment(
                "data_gap", "posttransfusion_evaluation_time_unavailable"
            )
        assert horizon_date is not None
        if any(
            _047_window_is_mature(
                end_time,
                horizon_datetime=horizon_datetime,
                horizon_date=horizon_date,
            )[0]
            for index in pending
            for end_time in (end_rows[index][0],)
        ):
            return _PosttransfusionEvaluationAssessment(
                "non_compliant",
                "posttransfusion_evaluation_missing",
                latest_end_time=latest_end,
                selected_source_document_refs=end_document_refs,
            )
        return _PosttransfusionEvaluationAssessment(
            "not_applicable",
            "evaluation_window_not_mature",
            latest_end_time=latest_end,
            selected_source_document_refs=end_document_refs,
        )

    qualified_daily_evaluations: list[tuple[datetime, tuple[str, str] | None]] = []
    for row in _source_document_rows(documents, "daily_course_record"):
        record_time = _authoritative_record_time(row)
        text = _row_text(row)
        if not (
            _TRANSFUSION_CONTEXT_PATTERN.search(text)
            and _has_clinical_posttransfusion_evaluation(text)
        ):
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
        if record_time is None or record_time < latest_end:
            unusable_evaluation_time = True
            continue
        if (record_time - latest_end).total_seconds() <= 24 * 3600:
            document_id = str(row.get("document_id") or row.get("id") or "").strip()
            qualified_daily_evaluations.append(
                (
                    record_time,
                    ("daily_course_record", document_id) if document_id else None,
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


def _programmatic_048_status(
    documents: Mapping[str, Any],
) -> tuple[str, str, Mapping[str, Any] | None]:
    """确认术中输血后，按三份文书的成分和剂量做受控比较。"""

    surgery_texts = tuple(
        _clean(
            " ".join(
                _clean(row.get(key))
                for key in (
                    "surgery_name",
                    "surgery_process",
                    "content",
                    "record_content",
                    "assembled_text",
                )
                if _clean(row.get(key))
            )
        )
        for row in _source_document_rows(documents, "surgery_record")
    )
    anesthesia_texts = tuple(
        _clean(
            " ".join(
                _clean(row.get(key))
                for key in (
                    "anesthesia_method",
                    "anesthesia_process",
                    "content",
                    "record_content",
                    "assembled_text",
                )
                if _clean(row.get(key))
            )
        )
        for row in _source_document_rows(documents, "anesthesia_record")
    )
    intraoperative_transfusion_is_credible = any(
        _SURGERY_TRANSFUSION_PATTERN.search(text)
        and _TRANSFUSION_COMPONENT_PATTERN.search(text)
        and _TRANSFUSION_DOSE_PATTERN.search(text)
        for text in (*surgery_texts, *anesthesia_texts)
    )
    if not intraoperative_transfusion_is_credible:
        return (
            "not_applicable",
            "intraoperative_transfusion_fact_absent",
            {
                "verification_kind": "intraoperative_transfusion_absent",
                "checked_sources": ["surgery_record", "anesthesia_record"],
            },
        )

    source_keys = (
        "surgery_record",
        "anesthesia_record",
        "postsurg_firstcourse_record",
    )
    rows_by_source = {
        source_key: _source_document_rows(documents, source_key)
        for source_key in source_keys
    }
    if any(len(rows) != 1 for rows in rows_by_source.values()):
        if any(len(rows) > 1 for rows in rows_by_source.values()):
            return "data_gap", "association_failed", None
        return (
            "data_gap",
            "transfusion_comparison_fields_unavailable",
            {
                "failure_kind": "transfusion_comparison_material_missing",
                "missing_sources": sorted(
                    source for source, rows in rows_by_source.items() if not rows
                ),
            },
        )

    def normalized_values(row: Mapping[str, Any]) -> dict[str, list[str]]:
        text = _clean(
            " ".join(
                _clean(row.get(key))
                for key in (
                    "surgery_process",
                    "anesthesia_process",
                    "content",
                    "record_content",
                    "assembled_text",
                )
                if _clean(row.get(key))
            )
        )
        components = sorted(set(_TRANSFUSION_COMPONENT_PATTERN.findall(text)))
        doses = sorted(
            {
                re.sub(r"\s+", "", value).lower()
                for value in _TRANSFUSION_DOSE_PATTERN.findall(text)
            }
        )
        return {"components": components, "doses": doses}

    matrix = {
        source: normalized_values(rows[0]) for source, rows in rows_by_source.items()
    }
    missing_fields = {
        source: sorted(field for field, values in fields.items() if not values)
        for source, fields in matrix.items()
    }
    missing_fields = {
        source: fields for source, fields in missing_fields.items() if fields
    }
    if missing_fields:
        return (
            "data_gap",
            "transfusion_comparison_fields_unavailable",
            {
                "failure_kind": "transfusion_comparison_fields_missing",
                "missing_fields_by_source": missing_fields,
            },
        )
    differing_fields = sorted(
        field
        for field in ("components", "doses")
        if len({tuple(values[field]) for values in matrix.values()}) > 1
    )
    if differing_fields:
        return (
            "non_compliant",
            "transfusion_records_inconsistent",
            {
                "failure_kind": "transfusion_records_inconsistent",
                "performed_intraoperative_transfusion_confirmed": True,
                "differing_fields": differing_fields,
                "comparison_matrix": matrix,
            },
        )
    return (
        "compliant",
        "transfusion_records_consistent",
        {
            "verification_kind": "transfusion_records_consistent",
            "performed_intraoperative_transfusion_confirmed": True,
            "checked_fields": ["components", "doses"],
            "comparison_matrix": matrix,
        },
    )


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
    posttransfusion_assessment: _PosttransfusionEvaluationAssessment | None = None,
) -> Mapping[str, Any] | None:
    """从已参与裁决的同一份资料中生成受控事实，不回显正文。"""

    records = _source_document_rows(documents, "bloodtrans_record")
    if rule_id == "LX0609-07-01-02":
        entries = [
            *_source_entries(documents, "blood_application", limit=None),
            *_source_entries(documents, "bloodtrans_record", limit=None),
            *_source_entries(documents, "daily_course_record", limit=None),
        ]
        joined = " ".join(entries)
        checked = {
            "indication": bool(_PRETRANSFUSION_CORE_PATTERNS[0].search(joined)),
            "laboratory_indicator": bool(
                _PRETRANSFUSION_CORE_PATTERNS[1].search(joined)
            ),
            "risk_history_or_status": bool(
                _PRETRANSFUSION_CORE_PATTERNS[2].search(joined)
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
            if (document_id := str(record.get("document_id") or record.get("id") or "").strip())
        ]
        if source_document_ids:
            payload["source_document_ids"] = list(dict.fromkeys(source_document_ids))
        return payload
    if rule_id == "LX0609-07-02-02":
        llm_component_refs = set(component_evidence_document_refs)
        checks_by_record = []
        for index, record in enumerate(records, start=1):
            text = _row_text(record)
            checks_by_record.append(
                _transfusion_046_field_checks(
                    text,
                    component_confirmed=(
                        _transfusion_record_ref(record, index) in llm_component_refs
                    ),
                )
            )
        field_names = (
            "reason_or_indication", "start_and_end_time", "component", "dose",
            "process_observation", "reaction_and_handling",
        )
        checked = {
            field: bool(checks_by_record) and all(item[field] for item in checks_by_record)
            for field in field_names
        }
        missing = sorted(key for key, present in checked.items() if not present)
        missing_field_record_counts = {
            field: sum(1 for item in checks_by_record if not item[field])
            for field in missing
        }
        incomplete_record_count = sum(
            1 for item in checks_by_record if not all(item.values())
        )
        payload = {
            "performed_transfusion_confirmed": True,
            "record_count": len(records),
            "incomplete_record_count": incomplete_record_count,
            "checked_fields": sorted(checked),
            "missing_fields": missing,
            "missing_field_record_counts": missing_field_record_counts,
        }
        source_document_ids = [
            document_id
            for record, record_checks in zip(records, checks_by_record, strict=True)
            if status == "compliant" or not all(record_checks.values())
            if (document_id := _clean(record.get("document_id")))
        ]
        if source_document_ids:
            payload["source_document_ids"] = list(
                dict.fromkeys(source_document_ids)
            )
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

    explicit_time = row.get("record_time") or row.get("display_time")
    if explicit_time:
        return _parse_document_datetime(explicit_time)
    if str(row.get("time_basis") or "").strip() == "record_time":
        return _parse_document_datetime(row.get("authored_at"))
    return None


def _performed_source_state(
    *,
    documents: Mapping[str, Any] | None,
    institute_id: str,
    patient_id: str,
    visit_id: str,
    source_schema: str | None,
    evidence_materials: Luxian0609EvidenceMaterialStore | None = None,
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
        outcome = _TransfusionRuleOutcome(
            rule_id=rule_id,
            status=status,
            reason_code=reason_code,
            executor_type=executor_type,
        )
        controlled_facts = display_facts or _customer_display_facts_for_outcome(
            rule_id=rule_id, status=status, reason_code=reason_code
        )
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
                (*fact_identities, *selected_source_document_refs)
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
    legacy_source_state = _performed_source_state(
        documents=legacy_documents,
        institute_id=str(institute_id or ""),
        patient_id=str(patient_id or ""),
        visit_id=str(visit_id or ""),
        source_schema=source_schema,
        evidence_materials=evidence_materials,
    )
    wrappers_by_id = {
        str(wrapper.get("rule_id") or wrapper.get("rule_code") or "").strip().upper(): wrapper
        for wrapper in wrapper_rules
        if isinstance(wrapper, Mapping)
    }
    llm_call_count = prompt_tokens = completion_tokens = total_tokens = 0
    api_time = 0.0
    for rule_id in selected:
        typed_rule = rule_id in typed_requested
        if typed_rule:
            documents, typed_material_status, typed_material_reason = (
                typed_material_by_rule[rule_id]
            )
        else:
            documents = legacy_documents
            typed_material_status = ""
            typed_material_reason = ""
        if typed_material_status:
            emit_outcome(
                rule_id,
                typed_material_status,
                typed_material_reason,
                executor_type="program",
            )
            continue
        source_state = (
            _performed_source_state(
                documents=documents,
                institute_id=str(institute_id or ""),
                patient_id=str(patient_id or ""),
                visit_id=str(visit_id or ""),
                source_schema=source_schema,
                evidence_materials=evidence_materials,
            )
            if typed_rule
            else legacy_source_state
        )
        if source_state != "present":
            emit_outcome(
                rule_id,
                "not_applicable" if source_state == "absent" else "data_gap",
                (
                    "transfusion_fact_absent"
                    if source_state == "absent"
                    else "transfusion_source_unavailable"
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
            programmatic = {
                "LX0609-11-03-01": _programmatic_041_status,
                "LX0609-11-03-02": _programmatic_042_status,
                "LX0609-07-01-01": evaluate_pretransfusion_nine_items,
            }[rule_id](documents)
            status, reason_code, display_facts = programmatic
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
        if rule_id == "LX0609-07-04-01":
            status, reason_code, display_facts = _programmatic_048_status(documents)
            emit_outcome(
                rule_id,
                status,
                reason_code,
                executor_type="program",
                display_facts=display_facts,
            )
            continue
        # 044–047 的专用输血记录具有更高证据优先级。先尝试确定性判定，
        # 只有不能定论时才检查日常病程等辅助投影并进入裁剪模型。
        if rule_id == "LX0609-07-01-02":
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
                llm_call_count += 1
                try:
                    response = await llm_client.generate(
                        _044_reason_prompt(reason_candidate)
                    )
                except Exception:
                    emit_outcome(
                        rule_id,
                        "technical_error",
                        "model_transport_error",
                        executor_type="llm",
                    )
                    continue
                prompt, completion, total, elapsed = _usage(response)
                prompt_tokens += prompt
                completion_tokens += completion
                total_tokens += total
                api_time += elapsed
                reason_payload = _parse_044_reason_response(response)
                reason_state = (
                    _validated_044_reason_state(
                        reason_payload,
                        candidate=reason_candidate,
                    )
                    if reason_payload is not None
                    else None
                )
                if reason_state is None:
                    emit_outcome(
                        rule_id,
                        "technical_error",
                        "model_invalid_output",
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
        if rule_id == "LX0609-07-02-01":
            programmatic_status = _programmatic_045_status(documents)
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
                    ),
                )
                continue
            candidate = _046_component_llm_candidate(documents)
            if candidate is not None:
                document_ref, record_text = candidate
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
                    response = await llm_client.generate(
                        _046_component_prompt(
                            document_ref=document_ref,
                            record_text=record_text,
                        )
                    )
                except Exception:
                    emit_outcome(
                        rule_id,
                        "technical_error",
                        "model_transport_error",
                        executor_type="llm",
                    )
                    continue
                prompt, completion, total, elapsed = _usage(response)
                prompt_tokens += prompt
                completion_tokens += completion
                total_tokens += total
                api_time += elapsed
                component_payload = _parse_046_component_response(response)
                assertion = (
                    _validated_046_component_assertion(
                        component_payload,
                        document_ref=document_ref,
                        record_text=record_text,
                    )
                    if component_payload is not None
                    else None
                )
                if assertion is None:
                    emit_outcome(
                        rule_id,
                        "technical_error",
                        "model_invalid_output",
                        executor_type="llm",
                    )
                    continue
                if assertion == "unclear":
                    emit_outcome(
                        rule_id,
                        "evaluation_unknown",
                        "semantic_output_unknown",
                        executor_type="llm",
                    )
                    continue
                status = (
                    "compliant" if assertion == "explicit" else "non_compliant"
                )
                emit_outcome(
                    rule_id,
                    status,
                    "transfusion_course_record_complete"
                    if status == "compliant"
                    else "transfusion_course_record_incomplete",
                    executor_type="llm",
                    display_facts=_programmatic_transfusion_display_facts(
                        rule_id=rule_id,
                        status=status,
                        reason_code=(
                            "transfusion_course_record_complete"
                            if status == "compliant"
                            else "transfusion_course_record_incomplete"
                        ),
                        documents=documents,
                        component_evidence_document_refs=(
                            (document_ref,) if assertion == "explicit" else ()
                        ),
                    ),
                )
                continue
        if rule_id == "LX0609-07-03-01":
            assessment = _programmatic_047_assessment(documents)
            status, reason_code = assessment.status, assessment.reason_code
            emit_outcome(
                rule_id,
                status,
                reason_code,
                executor_type="program",
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
        except Exception:
            emit_outcome(
                rule_id,
                "technical_error",
                "model_transport_error",
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
