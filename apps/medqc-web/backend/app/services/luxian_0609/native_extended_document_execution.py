"""第一阶段新增的确定性文书规则。

本执行器只消费同一个 Evidence Snapshot/Material Store，不调用旧四川规则，
也不从自由文本结论反推状态。
"""

from __future__ import annotations

from collections import Counter

import logging
import re
import sys
from dataclasses import dataclass, replace
from datetime import date, datetime, timedelta
from typing import Any, Mapping, Sequence
from zoneinfo import ZoneInfo

from .decision_model import (
    ApplicabilityState,
    EvidenceState,
    QcDirection,
    RuleDecision,
)
from .continuity_evidence_selection import (
    bind_consumed_continuity_document_rows,
    bind_consultation_evidence,
    bind_handoff_evidence,
    bind_transfer_evidence,
)
from .evidence_material import (
    EvidenceMaterialTruncated,
    EvidenceMaterialUnavailable,
    Luxian0609EvidenceMaterialStore,
)
from .evidence_snapshot import Luxian0609EvidenceSnapshot
from .extended_document.diagnosis_scope_extraction import extract_diagnosis_scope
from .extended_document.discharge_diagnosis_equivalence import (
    extract_discharge_diagnosis_equivalence,
    map_equivalent_diagnoses as _map_equivalent_diagnoses,
    split_numbered_diagnoses,
)
from .extended_document.invasive_procedure_record import (
    candidate_order_rows as _invasive_candidate_order_rows,
    check_invasive_procedure_records,
    front_page_triggers as _invasive_front_page_triggers,
    map_orders_to_invasive_catalog,
    merge_triggers as _merge_invasive_triggers,
    order_triggers as _invasive_order_triggers,
)
from .extended_document.death_discussion import (
    evaluate_death_discussion_timeliness,
)
from .extended_document.consultation_timeliness import (
    evaluate_consultation_timeliness,
)
from .extended_document.discharge_documentation import (
    evaluate_discharge_documentation_timeliness,
)
from .extended_document.discharge_course_content import evaluate_discharge_course_content
from .extended_document.discharge_course import (
    PredischargeCourseOutcome,
    evaluate_predischarge_course_presence,
)
from .course_body_fact_extraction import (
    CourseBodyDocument,
    CourseBodyExtraction,
    extract_course_body_facts,
)
from .key_antimicrobial_catalog import key_antimicrobials_in_order
from .extended_document.diagnosis_change_extraction import (
    DiagnosisChangeDocumentInput,
    extract_diagnosis_change_documentation,
)
from .extended_document.antimicrobial_order_reason import (
    WindowDocument,
    derive_antimicrobial_use_events,
    extract_antimicrobial_reasons,
    extract_special_antimicrobial_approvals,
    is_excluded_antimicrobial_order,
    order_start_time,
    is_planned_stop,
    planned_duration,
    window_documents,
)
from .extended_document.antimicrobial_action_extraction import (
    ANTIMICROBIAL_CONTEXT_MARKERS as _ANTIMICROBIAL_EFFECT_CONTEXT_MARKERS,
    SPECIAL_ANTIMICROBIALS as _SPECIAL_ANTIMICROBIALS,
    AntimicrobialOrderEvent as _AntimicrobialOrderEvent,
    antimicrobial_names_in as _antimicrobial_names_in,
    antimicrobial_names_in_rows as _antimicrobial_names_in_rows,
    build_antimicrobial_order_events as _antimicrobial_order_events,
    linked_order_id as _linked_order_id,
)
from .extended_document.antimicrobial_effect_extraction import (
    extract_antimicrobial_effects,
    extract_antimicrobial_effect_pairs,
)
from .extended_document.transfusion_performance_extraction import extract_transfusion_performance
from .prophylactic_antimicrobial_duration import is_local_route_drug_order
from .transfusion_course_presence import classify_transfusion_course_records, select_transfusion_course_candidates
from .extended_document.physician_handoff import evaluate_physician_handoff
from .extended_document.rule_076 import death_time_from_body, evaluate_rule_076
from .extended_document.shared import _clean, _parse_datetime, _row_time, row_time_upper_bound
from app.services.document_assembly.signatures import course_physician_signatures
from .extended_document.discharge_medication_extraction import extract_discharge_medications
from .extended_document.discharge_approval_extraction import (
    DischargeApprovalInput,
    extract_discharge_approval,
    has_confirmed_senior_discharge_approval_quote,
)
from .extended_document.transfer_documentation import (
    evaluate_transfer_documentation,
)
from .extended_document_critical_value import (
    CRITICAL_VALUE_RULE_IDS,
    CriticalValueDisposition,
    CriticalValueInput,
    CriticalValueItem,
    CriticalValueOutcome,
    evaluate_critical_value_rules,
    select_critical_value_fact_refs,
)
from .source_evidence_reader import (
    authoritative_document_time_value,
    parse_strict_performed_time,
    trusted_performed_surgery_times,
)
from .native_transfusion_execution import (
    evaluate_pretransfusion_nine_items,
    resolve_pretransfusion_admission_time,
    resolve_pretransfusion_required_item,
)
from .surgery_applicability import (
    SurgeryApplicability,
    resolve_surgery_applicability,
)
from .surgery_procedure_catalog import catalog_surgery_state

logger = logging.getLogger(__name__)

# 058（05-01-06）业务基线：紧急越级使用特殊级抗菌药须在 24 小时内补办专家会诊/查房。
# 用户口径（2026-10-17）：启用前或启用后 24 小时内有可关联的专家支持即合规，指征不单独核对。
_LX0609_058_SUPPORT_WINDOW = timedelta(hours=24)

EXECUTOR_KEY = "extended_document"
EXTENDED_DOCUMENT_RULE_IDS = (
    "LX0609-03-02-01",
    "LX0609-09-02-01",
    "LX0609-06-04-01",
    "LX0609-06-04-02",
    "LX0609-05-01-02",
    "LX0609-05-01-03",
    "LX0609-05-01-04",
    "LX0609-05-01-05",
    "LX0609-05-01-06",
    "LX0609-05-03-01",
    "LX0609-04-02-06",
    "LX0609-08-01-01",
    "LX0609-08-01-02",
    "LX0609-08-01-03",
    "LX0609-04-05-01",
    "LX0609-04-05-02",
    "LX0609-04-05-03",
    "LX0609-08-02-01",
    "LX0609-08-02-02",
    "LX0609-04-02-07",
    "LX0609-07-01-03",
    "LX0609-10-01-01",
    "LX0609-10-02-01",
    "LX0609-10-02-02",
    "LX0609-12-02-01",
    "LX0609-10-03-01",
    "LX0609-04-02-08",
    "LX0609-08-01-05",
)

EXTENDED_DOCUMENT_SOURCE_KEYS = (
    "inpat_registration",
    "admission_record",
    "death_record",
    "death_discussion",
    "discharge_record",
    "daily_course_record",
    "senior_course_record",
    "postsurg_firstcourse_record",
    "mr_surgery",
    "surgery_record",
    "anesthesia_record",
    "consultation_record",
    "handoff_record",
    "handover_record",
    "physician_change_event",
    "transfer_in_record",
    "transfer_out_record",
    "inpat_nondrug_order",
    "diagnosis",
    "diffcase_discussion_record",
    "crisis_value_record",
    "labtest_item_report",
    "labtest_master",
    "inpat_drug_order",
    "discharge_record_diagnosis",
    "mr_bloodtrans",
    "bloodtrans_record",
)

_DEATH_MARKERS = ("死亡", "病故")
_ALIVE_DISCHARGE_MARKERS = ("出院", "转院", "医嘱离院", "非医嘱离院")
_DISCHARGE_DIAGNOSIS_TYPES = frozenset(("出院诊断", "死亡诊断"))
_UNCERTAIN_DIAGNOSIS_MARKERS = ("诊断仍不明确", "诊断不明确")
_LOCAL_DIAGNOSIS_UNCERTAINTY_MARKERS = ("原因待查", "性质待定")
# “修正诊断为：X”与“修正诊断为X”“修正诊断：X”同为已落地的变更表述。
_DIAGNOSIS_CHANGE_EVENT_PATTERN = re.compile(
    r"(?:修正诊断|补充诊断)\s*(?:为\s*[:：]?|[:：])\s*"
    r"[^\s，,。；;：:！？!?][^，,。；;\r\n]*"
)
_DIAGNOSIS_CHANGE_NON_EVENT_PREFIX_PATTERN = re.compile(
    r"(?:暂不|无需|不需|不必|不予|未予|未作|若需|如需|是否|应记录|应当记录).{0,8}$"
)
_ADMISSION_DIAGNOSIS_CHANGE_TYPES = frozenset({"修正诊断", "补充诊断"})
# 诊断栏列表分隔：分号或“1.”“2、”等序号（不拆“1.5cm”“2型”）。
_ADMISSION_DIAGNOSIS_LIST_SEPARATOR = re.compile(r"[；;\n]|(?<![\d.])\d{1,2}[.、．](?!\d)")
# 客户入院记录诊断把签名与记录时间拼在诊断名尾部；解析“变更后诊断名”时
# 必须剥离，否则同条关联判据永远匹配不上病程正文。
_ADMISSION_DIAGNOSIS_LABEL_PATTERN = re.compile(
    r"(?:医师签名|医生签名|签名|记录时间|记录日期|记录者|签名日期|日期|时间)\s*[:：]"
)
_ADMISSION_DIAGNOSIS_TIME_PATTERN = re.compile(
    r"\d{4}[-/年]\d{1,2}(?:[-/月]\d{1,2}日?)?"
    r"(?:[ T]?\d{1,2}[:：]\d{1,2}(?:[:：]\d{1,2})?)?"
)
# 074 每次诊断变更最多送检的候选病程数：理由与依据通常记在变更后最先的几份病程里，
# 限定数量使长住院中反复提及同名诊断的病程不会无界送模。
_DIAGNOSIS_CHANGE_CANDIDATES_PER_CHANGE = 3
_DISCHARGE_MEDICATION_SIGNAL_PATTERN = re.compile(
    r"(?:药品|药物|用药|服药|服用|口服|停药|带药|注射|静滴|静脉滴注|"
    r"外用|外涂|涂抹|吸入|滴眼|滴耳|滴鼻|含服|舌下|肛塞|"
    r"(?<![a-z])(?:po|sc|ih|im|iv|ivgtt)(?![a-z])|"
    r"\d+(?:\.\d+)?\s*(?:mg|μg|ug|ml|g|单位|片|粒|袋|支)(?![a-z]))",
    re.IGNORECASE,
)
_ANTIMICROBIAL_REASON_MARKERS = (
    "因为", "由于", "考虑", "依据", "理由", "重症感染", "覆盖",
    "培养", "药敏", "感染证据", "感染可能", "疑似感染", "因感染",
    "感染指标升高", "无样可采", "耐药", "过敏", "不良反应", "输注反应",
    "瘙痒", "皮疹", "肝功能", "肾功能",
)
_EMPIRIC_ANTIMICROBIAL_TRIGGER_PATTERN = re.compile(
    r"(?:经验性用药|经验用药|经验性抗感染(?:治疗)?|经验性抗菌治疗|经验性)"
)
_EMPIRIC_ANTIMICROBIAL_NEGATED_PATTERN = re.compile(
    r"(?:非|不是|并非|停止|终止).{0,8}(?:经验性用药|经验用药|经验性抗感染(?:治疗)?|经验性抗菌治疗)"
)
_TARGETED_ANTIMICROBIAL_MARKERS = (
    "根据药敏", "依据药敏", "药敏结果调整", "培养结果后调整",
    "培养结果调整", "目标治疗",
)
_EMPIRIC_REASON_MARKERS = (
    "重症感染", "覆盖耐药菌", "感染证据", "感染可能", "疑似感染",
    "考虑感染", "因感染", "感染指标升高", "无样可采",
    "有抗生素使用指征", "有抗菌药物使用指征",
    "肺部感染", "社区获得性肺炎",
)
_SPECIAL_ANTIMICROBIAL_EXPERT_SUPPORT_MARKERS = (
    "感染专家", "专家会诊", "专家查房", "同意特殊级",
)
# 感染科副主任医师及以上的会诊署名（用户口径 2026-10-17：主治医师、临床药师不算授权专家）。
# 兼容“感染性疾病科”、署名括号、署名后直接接“会诊/意见/指出/建议/查房/冒号/逗号”等写法；
# 科室与职称之间不得出现其他科室，避免把他科医师意见算作感染科。
_SPECIAL_ANTIMICROBIAL_INFECTION_EXPERT_PATTERN = re.compile(
    r"感染(?:性疾病)?科[^。；;\n科]{0,24}?(?:副主任医师|主任医师)"
    r"[\]】）)]?\s*(?:会诊|意见|指出|建议|查房|[:：,，])"
)
_SPECIAL_ANTIMICROBIAL_EXPERT_SUPPORT_NEGATED_PATTERN = re.compile(
    r"(?:拒绝|不同意|未(?:行|完成|进行)|尚未|无).{0,12}"
    r"(?:感染专家|专家会诊|专家查房|会诊意见)|"
    r"(?:感染专家|专家会诊|专家查房|会诊意见).{0,12}"
    r"(?:未(?:行|完成|进行)|尚未|缺失|不存在|无)",
)
_LX0609_HOSPITAL_TIMEZONE = ZoneInfo("Asia/Shanghai")
_DISCHARGE_APPROVAL_PATTERN = re.compile(
    r"(?:同意|批准|准许|准予)(?:患者|其)?(?:于|拟于)?"
    r"(?:今日|明日|次日)?(?:安排|办理)?出院"
    r"|(?:可以|可)(?:患者|其)?(?:于|拟于)?"
    r"(?:今日|明日|次日)?(?:安排|办理|予以)?出院"
    r"|(?:建议|予以)(?:患者|其)?(?:于|拟于)?"
    r"(?:今日|明日|次日)?(?:安排|办理)?出院"
    r"|(?<!拟)(?<!计划)(?<!准备)于今日(?:办理)?出院"
    # 院方口径（2026-10-17）：上级医师写明日期的出院安排（如拟明日带药出院）视为同意出院；
    # 未写日期的“拟办理出院”及“考虑出院”仍不构成明确同意。
    r"|(?P<dated_plan>(?:拟|计划|准备)(?:于)?(?:今日|明日|次日)(?:带药)?(?:办理)?出院)"
)
_DISCHARGE_APPROVAL_NEGATED_PATTERN = re.compile(
    r"(?:不|未|未获|未取得|未得到|尚未|尚不|暂不).{0,12}"
    r"(?:同意|批准|准许|准予|可以|可|建议|予以).{0,8}出院"
    r"|(?:待|若|如|如果).{0,24}"
    r"(?:同意|批准|准许|准予|可以|可|建议|予以).{0,8}出院"
    r"|(?:复查|检查|治疗).{0,16}后(?:再)?.{0,8}"
    r"(?:同意|批准|准许|准予|可以|可|建议|予以).{0,8}出院"
    r"|(?:病情|情况).{0,16}后再.{0,8}"
    r"(?:同意|批准|准许|准予|可以|可|建议|予以).{0,8}出院"
    r"|考虑.{0,12}于今日(?:办理)?出院"
)
_SEMANTIC_DISCHARGE_DISPOSITION_PATTERN = re.compile(
    r"(?:(?:今日|今天|明日|次日)(?:带药)?|办理|安排|予)出院(?!医嘱)"
)
_SENIOR_PHYSICIAN_REFERENCE_PATTERN = re.compile(
    r"(?:上级医师|上级医生|主治医师|副主任医师|主任医师|[\u4e00-\u9fff]{1,4}(?:主任|主治))"
)
_AUTOMATIC_DISCHARGE_PATTERN = re.compile(r"自动出院")
_SENIOR_PHYSICIAN_CONSULTED_PATTERN = re.compile(
    r"(?:请示|报请|报告).{0,12}"
    r"(?:上级医师|上级医生|主治医师|副主任医师|主任医师|[\u4e00-\u9fff]{1,4}(?:主任|主治))"
)
_AUTOMATIC_DISCHARGE_SIGNED_PATTERN = re.compile(
    r"(?:签署|签订|签字|签)[《\"“]?自动出院(?:书|协议|知情同意书|告知书)[》\"”]?"
)
_AUTOMATIC_DISCHARGE_UNSIGNED_PATTERN = re.compile(
    r"(?:未|未予|尚未|拒绝|拒不).{0,8}"
    r"(?:签署|签订|签字|签)[《\"“]?自动出院(?:书|协议|知情同意书|告知书)"
)
_BLOCKING_DISCHARGE_HORIZON_ERRORS = frozenset(
    {"authoritative_time_missing", "authoritative_time_conflict"}
)


def _critical_value_event_key(
    source_key: str,
    row: Mapping[str, Any],
) -> str | None:
    """按来源选择可跨表证明的危急值事件键，不把处置文书自身 ID 当关联键。"""

    fields = (
        ("report_id", "test_id", "document_id")
        if source_key == "labtest_item_report"
        else ("report_id", "test_id")
        if source_key == "crisis_value_record"
        else ()
    )
    for field in fields:
        value = _clean(row.get(field))
        if value:
            return f"{field}:{value}"
    return None


def _discharge_approval_path(
    row: Mapping[str, Any],
    *,
    source_key: str,
) -> str | None:
    text = _row_text(row)
    if not text:
        return None

    if (
        _AUTOMATIC_DISCHARGE_PATTERN.search(text)
        and _SENIOR_PHYSICIAN_CONSULTED_PATTERN.search(text)
        and _AUTOMATIC_DISCHARGE_SIGNED_PATTERN.search(text)
        and not _AUTOMATIC_DISCHARGE_UNSIGNED_PATTERN.search(text)
    ):
        return "automatic_discharge"

    author_title = _clean(row.get("author_title"))
    known_senior = source_key == "senior_course_record" or bool(
        _SENIOR_PHYSICIAN_REFERENCE_PATTERN.search(author_title)
    )
    # 与语义入口共用同分句完成条件，既不把待请示当批准，也不漏掉已获同意后的安排。
    for clause in re.split(r"[。！？!?；;\r\n]+", text):
        if has_confirmed_senior_discharge_approval_quote(
            clause,
            source_type="senior_course_record" if known_senior else "daily_course_record",
        ):
            return "senior_approval"
    return None


def _unnegated_discharge_approvals(text: str) -> list[re.Match[str]]:
    """未被否定或条件短语约束的全部出院处置匹配。"""

    value = str(text or "")
    approvals = []
    for approval in _DISCHARGE_APPROVAL_PATTERN.finditer(value):
        local_start = max(0, approval.start() - 80)
        local_context = value[local_start: approval.end() + 40]
        is_bound_to_negation = any(
            local_start + negated.start() < approval.end()
            and local_start + negated.end() > approval.start()
            for negated in _DISCHARGE_APPROVAL_NEGATED_PATTERN.finditer(local_context)
        )
        if not is_bound_to_negation:
            approvals.append(approval)
    return approvals


def _confirmed_discharge_approval_match(text: str) -> re.Match[str] | None:
    """返回未被否定或条件短语约束的明确出院处置。"""

    approvals = _unnegated_discharge_approvals(text)
    return approvals[0] if approvals else None


def _is_dated_discharge_plan_only(text: str) -> bool:
    """引文只有“拟/计划某日出院”的安排、没有同意或批准等明确表态。

    写明日期的出院安排只在确认为上级医师所写时才视为同意；身份不明的此类安排
    （如住院医师日常病程“拟明日出院”）不构成上级同意，不能当作未能确认的同意。
    """

    approvals = _unnegated_discharge_approvals(text)
    return bool(approvals) and all(approval.group("dated_plan") for approval in approvals)


def _has_confirmed_discharge_approval(text: str) -> bool:
    """模型的 approved 枚举也必须通过同一明确处置合同。"""
    # 此入口只消费已独立确认的 senior 角色；引文自身仍须证明条件已完成。
    return has_confirmed_senior_discharge_approval_quote(
        text, source_type="senior_course_record",
    )


def _source_rows(
    materials: Luxian0609EvidenceMaterialStore,
    source_key: str,
) -> tuple[tuple[Mapping[str, Any], ...], str]:
    try:
        rows = materials.rows(source_key)
    except EvidenceMaterialTruncated:
        return (), "source_truncated"
    except EvidenceMaterialUnavailable:
        return (), "source_unavailable"
    return tuple(dict(row) for row in rows), ""



def _course_body_candidate_inputs(
    *,
    snapshot: Luxian0609EvidenceSnapshot,
    materials: Luxian0609EvidenceMaterialStore,
    candidates: Sequence[tuple[str, int, Mapping[str, Any]]],
) -> tuple[tuple[CourseBodyDocument, ...], Mapping[tuple[str, int], str]]:
    """按原行occurrence绑定，不能把摘要排序与原行索引zip或按docID合并。"""
    available: dict[str, list[tuple[str, Mapping[str, Any]]]] = {}
    documents: list[CourseBodyDocument] = []
    refs: dict[tuple[str, int], str] = {}
    for source, ordinal, row in candidates:
        if source not in available:
            available[source] = list(materials.document_rows(source, snapshot=snapshot))
        matches = available[source]
        position = next((index for index, (_ref, original) in enumerate(matches) if original == row), None)
        if position is None:
            raise ValueError("course body material occurrence mismatch")
        ref, _original = matches.pop(position)
        refs[(source, ordinal)] = ref
        documents.append(CourseBodyDocument(ref, source, row.get("record_content")))
    return tuple(documents), refs


def _has_source_observation(
    snapshot: Luxian0609EvidenceSnapshot,
    source_key: str,
) -> bool:
    normalized = str(source_key or "").strip().lower()
    return any(observation.source_key == normalized for observation in snapshot.observations)


def _discharge_or_death_diagnosis_rows(
    rows: Sequence[Mapping[str, Any]],
    *,
    allow_untyped_legacy_rows: bool = False,
    diagnosis_scope: str | None = None,
) -> tuple[Mapping[str, Any], ...]:
    """只保留首页/出院记录中的出院或死亡诊断。

    旧 ``diagnosis`` 兼容快照可能没有诊断类型字段；仅当整组行都未提供
    类型时允许沿用该来源的既有语义。只要出现类型，就严格按出院/死亡类型
    过滤，避免把入院、门诊或病理诊断混入比较。
    """

    accepted_types = (
        frozenset(("死亡诊断",)) if diagnosis_scope == "death"
        else frozenset(("出院诊断",)) if diagnosis_scope == "discharge"
        else _DISCHARGE_DIAGNOSIS_TYPES
    )
    selected = tuple(
        row
        for row in rows
        if _clean(row.get("diagnosis_type")) in accepted_types
    )
    if not selected and diagnosis_scope == "death":
        # 用户决定（2026-10-20）：死亡病例病案首页与出院记录常把诊断标为“出院诊断”，
        # 没有“死亡诊断”类型时以“出院诊断”作为该病例的出院/死亡诊断比对。
        selected = tuple(row for row in rows if _clean(row.get("diagnosis_type")) == "出院诊断")
    if selected or not allow_untyped_legacy_rows:
        return selected
    if rows and all(not _clean(row.get("diagnosis_type")) for row in rows):
        return tuple(rows)
    return ()


def _critical_value_evaluation_horizon(
    horizon_rows: Sequence[Mapping[str, Any]],
    horizon_error: str,
) -> tuple[date | None, datetime | None, str | None]:
    """读取 052 的单一冻结评价终点，拒绝缺失、重复及日期时间冲突。"""

    if horizon_error:
        return None, None, horizon_error
    if not horizon_rows:
        return None, None, "authoritative_time_missing"
    if len(horizon_rows) != 1:
        return None, None, "authoritative_time_conflict"
    row = horizon_rows[0]
    horizon_time = _parse_datetime(row.get("horizon_datetime"))
    raw_date = _clean(row.get("horizon_date"))
    try:
        horizon_date = date.fromisoformat(raw_date) if raw_date else None
    except ValueError:
        horizon_date = None
    if horizon_time is not None and horizon_date is not None:
        if horizon_time.date() != horizon_date:
            return None, None, "authoritative_time_conflict"
    if horizon_time is None and horizon_date is None:
        return None, None, "authoritative_time_missing"
    return horizon_date, horizon_time, None


def _antimicrobial_effect_window_state(
    *,
    start_time: datetime,
    horizon_date: date | None,
    horizon_time: datetime | None,
) -> tuple[str, float | None, Mapping[str, Any]]:
    """按单次抗菌药启用事件判断 055 的 48～72 小时观察窗口。

    日期粒度的冻结终点不能断言当天已经跨过具体时刻，故仅在截止日后
    才进入成熟状态；这与现有检查检验时间窗的保守口径一致。
    """

    window_start = start_time + timedelta(hours=48)
    window_end = start_time + timedelta(hours=72)
    facts: dict[str, Any] = {
        "start_time": start_time.isoformat(sep=" "),
        "window_start_time": window_start.isoformat(sep=" "),
        "window_end_time": window_end.isoformat(sep=" "),
    }
    if horizon_time is not None:
        facts["evaluation_time"] = horizon_time.isoformat(sep=" ")
        elapsed_hours = (horizon_time - start_time).total_seconds() / 3600
        facts["elapsed_hours"] = round(elapsed_hours, 2)
        if elapsed_hours < 0:
            return "conflict", elapsed_hours, facts
        if elapsed_hours < 48:
            return "not_started", elapsed_hours, facts
        if elapsed_hours < 72:
            return "not_mature", elapsed_hours, facts
        return "mature", elapsed_hours, facts
    if horizon_date is None:
        return "missing", None, facts
    facts["evaluation_date"] = horizon_date.isoformat()
    if horizon_date < start_time.date():
        return "conflict", None, facts
    if horizon_date < window_start.date():
        return "not_started", None, facts
    if horizon_date > window_end.date():
        return "mature", None, facts
    return "not_mature", None, facts


def _fact_refs(
    snapshot: Luxian0609EvidenceSnapshot,
    source_keys: Sequence[str],
) -> tuple[str, ...]:
    wanted = set(source_keys)
    return tuple(
        sorted(
            observation.snapshot_ref.removeprefix("sha256:")
            for observation in snapshot.observations
            if observation.source_key in wanted
        )
    )


def _selected_course_document_refs(
    *,
    snapshot: Luxian0609EvidenceSnapshot,
    materials: Luxian0609EvidenceMaterialStore,
    selected_document_ids: Sequence[tuple[str, str]],
) -> tuple[str, ...]:
    """把已参与 067/068 判定的病程行绑定为同快照逐行引用。

    该函数只把执行器已经选择的 ``(source_key, document_id)`` 映射到材料仓的真实
    document ref；不按日期、标题或正文重新选择文书。无法定位时宁可不投影，
    不能回退成整个来源 observation 或把内部 document_id 写进展示事实。
    """

    refs: list[str] = []
    try:
        for source_key, document_id in selected_document_ids:
            if source_key not in {"daily_course_record", "senior_course_record"}:
                return ()
            document_id = _clean(document_id)
            if not document_id:
                return ()
            matched = tuple(
                reference
                for reference, row in materials.document_rows(
                    source_key,
                    snapshot=snapshot,
                )
                if _clean(row.get("document_id") or row.get("id")) == document_id
            )
            # document_id 在同一来源中必须唯一。多个同名 ID 无法证明哪一行是
            # 执行器实际选中的病程，不能把它们全部当作客户证据。
            if len(matched) != 1:
                return ()
            refs.append(matched[0])
    except (EvidenceMaterialUnavailable, EvidenceMaterialTruncated):
        return ()
    return tuple(dict.fromkeys(refs))


def _selected_course_or_consumed_source_refs(
    *,
    snapshot: Luxian0609EvidenceSnapshot,
    selected_document_refs: Sequence[str],
    consumed_source_keys: Sequence[str],
) -> tuple[str, ...]:
    """优先精确文书引用；不可定位时只保留已消费的来源快照引用。

    来源快照引用用于 Binding 证明本次判定消费过相应来源，不能被公共文书
    projector 转换成客户证据。它只用于“文书身份缺失/歧义但业务事实已成立”的
    受控降级，绝不以来源级引用代替可定位的文书坐标。
    """

    if selected_document_refs:
        return tuple(dict.fromkeys(selected_document_refs))
    return _fact_refs(snapshot, consumed_source_keys)


def _070_document_refs(
    *,
    snapshot: Luxian0609EvidenceSnapshot,
    materials: Luxian0609EvidenceMaterialStore,
    consumed_bloodtrans_rows: Sequence[Mapping[str, Any]] | None = None,
    include_pretransfusion_materials: bool = True,
) -> tuple[str, ...]:
    """只返回 070 判定实际消费的、同一快照验证过的逐行引用。"""

    try:
        bloodtrans_record_rows = tuple(
            item for key in ("bloodtrans_record", "daily_course_record", "senior_course_record")
            for item in materials.document_rows(key, snapshot=snapshot)
            if key == "bloodtrans_record" or (
                consumed_bloodtrans_rows is not None and item[1] in consumed_bloodtrans_rows
            )
        )
        if not include_pretransfusion_materials:
            # 没有已确认实施事件时未核对九项，只引用实际用于抽取的专用资料。
            return tuple(dict.fromkeys(
                reference for reference, row in bloodtrans_record_rows
                if consumed_bloodtrans_rows is None or row in consumed_bloodtrans_rows
            ))
        registration_rows = (
            *materials.document_rows("inpat_registration", snapshot=snapshot),
            *materials.document_rows("admission_record", snapshot=snapshot),
        )
        transfusion_rows = materials.document_rows(
            "mr_bloodtrans", snapshot=snapshot
        )
        lab_rows = materials.document_rows("labtest_item_report", snapshot=snapshot)
    except (EvidenceMaterialUnavailable, EvidenceMaterialTruncated):
        # 既有规则已将受控来源不可用/截断映射为 data_gap；此时不能据部分材料
        # 伪造逐行坐标。材料身份异常则保持 fail-fast，不吞掉技术错误。
        return ()

    registration_refs = (
        reference
        for reference, row in registration_rows
        if resolve_pretransfusion_admission_time(row) is not None
    )
    lab_refs = (
        reference
        for reference, row in lab_rows
        if resolve_pretransfusion_required_item(row) is not None
    )
    refs = (
        *registration_refs,
        *(reference for reference, _row in transfusion_rows),
        *(reference for reference, row in bloodtrans_record_rows
          if consumed_bloodtrans_rows is None or row in consumed_bloodtrans_rows),
        *lab_refs,
    )
    return tuple(dict.fromkeys(refs))


def _critical_value_item_from_row(row: Mapping[str, Any]) -> CriticalValueItem:
    # 报告字段共同证明同一时刻；记录时间不属于危急值报告的权威来源。
    report_times = tuple(
        _parse_datetime(row.get(key))
        for key in ("report_time", "report_datetime")
        if _clean(row.get(key))
    )
    report_time_error = (
        "authoritative_time_missing"
        if not report_times or any(value is None for value in report_times)
        else "authoritative_time_conflict"
        if len(set(report_times)) > 1
        else None
    )
    return CriticalValueItem(
        item_name=_clean(row.get("item_name") or row.get("item_code")),
        flag_values=tuple(
            _clean(row.get(key))
            for key in (
                "result_flag",
                "abnormal_flag",
                "abnormal_indicator",
                "result_status",
                "result_hint",
            )
        ),
        marker_text=_material_text(row),
        display_flag=_clean(
            row.get("result_flag")
            or row.get("abnormal_flag")
            or row.get("abnormal_indicator")
        ),
        report_time=report_times[0] if report_time_error is None else None,
        event_key=_critical_value_event_key("labtest_item_report", row),
        report_time_error=report_time_error,
    )


def _critical_value_disposition_from_row(
    row: Mapping[str, Any],
) -> CriticalValueDisposition | None:
    disposition_time = _row_time(row)
    return CriticalValueDisposition(
        disposition_time=disposition_time,
        event_key=_critical_value_event_key("crisis_value_record", row),
    )


def _critical_value_document_refs(
    *,
    snapshot: Luxian0609EvidenceSnapshot,
    materials: Luxian0609EvidenceMaterialStore,
    outcome: CriticalValueOutcome,
) -> tuple[str, ...]:
    """返回危急值判定实际消费的逐行证据；评价终点不属于客户文书证据。"""

    def rows(source_key: str) -> tuple[tuple[str, Mapping[str, Any]], ...]:
        try:
            return tuple(
                (reference, dict(row))
                for reference, row in materials.document_rows(
                    source_key, snapshot=snapshot
                )
            )
        except (EvidenceMaterialUnavailable, EvidenceMaterialTruncated):
            return ()

    item_rows = rows("labtest_item_report")
    disposition_rows = rows("crisis_value_record")
    master_rows = rows("labtest_master")
    selected_refs = select_critical_value_fact_refs(
        outcome=outcome,
        item_refs=tuple(
            (reference, _critical_value_item_from_row(row))
            for reference, row in item_rows
        ),
        disposition_refs=tuple(
            (reference, disposition)
            for reference, row in disposition_rows
            for disposition in (_critical_value_disposition_from_row(row),)
            if disposition is not None
        ),
        master_refs=tuple(reference for reference, _row in master_rows),
    )
    # RuleDecision 的逐条引用上限为 128。大量检验的完整否定证据不能
    # 截断为前 128 行；改用已有来源快照绑定完整材料，不改变任何判定。
    if len(selected_refs) > 128:
        selected = frozenset(selected_refs)
        return _fact_refs(snapshot, tuple(
            source_key
            for source_key, source_rows in (
                ("labtest_item_report", item_rows),
                ("crisis_value_record", disposition_rows),
                ("labtest_master", master_rows),
            )
            if any(reference in selected for reference, _row in source_rows)
        ))
    return selected_refs


def _death_document_refs(
    *,
    snapshot: Luxian0609EvidenceSnapshot,
    materials: Luxian0609EvidenceMaterialStore,
    selected_document_refs: Sequence[Mapping[str, Any]],
) -> tuple[str, ...]:
    """将 051 已选文书和 060 死亡记录映射为同一快照内的逐行事实引用。

    ``selected_document_refs`` 仅在执行器内部用于选择事实，绝不进入客户展示
    facts。后续客户证据由 Binding 的 ``fact_refs`` 经公共投影统一生成。
    """

    selected_ids_by_source: dict[str, set[str]] = {}
    for item in selected_document_refs:
        source_key = _clean(item.get("source_type"))
        document_id = _clean(item.get("source_document_id"))
        if source_key in {"death_record", "death_discussion"} and document_id:
            selected_ids_by_source.setdefault(source_key, set()).add(document_id)
    if not selected_ids_by_source:
        return ()
    refs: list[str] = []
    try:
        for source_key, selected_ids in selected_ids_by_source.items():
            for reference, row in materials.document_rows(source_key, snapshot=snapshot):
                document_id = _clean(row.get("document_id") or row.get("id"))
                if document_id in selected_ids:
                    refs.append(reference)
    except (EvidenceMaterialUnavailable, EvidenceMaterialTruncated):
        return ()
    return tuple(dict.fromkeys(refs))


def _decision(
    *,
    rule_id: str,
    snapshot: Luxian0609EvidenceSnapshot,
    source_keys: Sequence[str],
    final_state: str,
    reason_code: str,
    document_refs: Sequence[str] = (),
    exact_document_refs: bool = False,
    criterion_results: Sequence[Any] = (),
) -> RuleDecision:
    if final_state == "technical_error":
        # 诊断日志：只记规则、原因码与出错代码行，不含病历或模型内容。
        logger.warning(
            "LX0609 扩展文书族技术错误: rule_id=%s reason_code=%s call_line=%s",
            rule_id, reason_code, sys._getframe(1).f_lineno,
        )
    dimensions = {
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
        "uncertain": (
            ApplicabilityState.UNKNOWN,
            EvidenceState.CONFLICT,
            QcDirection.UNKNOWN,
        ),
        "technical_error": (
            ApplicabilityState.ERROR,
            EvidenceState.TECHNICAL_ERROR,
            QcDirection.UNKNOWN,
        ),
    }
    applicability, evidence_state, direction = dimensions[final_state]
    return RuleDecision(
        rule_id=rule_id,
        snapshot_hash=snapshot.snapshot_hash,
        applicability=applicability,
        evidence_state=evidence_state,
        qc_direction=direction,
        reason_code=reason_code,
        fact_refs=(
            tuple(dict.fromkeys(document_refs))
            if exact_document_refs
            else tuple(dict.fromkeys((*_fact_refs(snapshot, source_keys), *document_refs)))
        ),
        evaluator_version="extended-document-v2",
        confidence=None,
        criterion_results=tuple(criterion_results),
    )


def _registration_status(rows: Sequence[Mapping[str, Any]]) -> str:
    return " ".join(
        _clean(
            row.get("patient_status")
            or row.get("discharge_status")
            or row.get("discharge_type")
        )
        for row in rows
    )


def _death_context(
    *,
    registration_rows: Sequence[Mapping[str, Any]],
    death_rows: Sequence[Mapping[str, Any]],
    discharge_rows: Sequence[Mapping[str, Any]],
) -> tuple[str, datetime | None]:
    explicit_death_times = {
        candidate
        for row in (*death_rows, *registration_rows)
        if (
            candidate := _parse_datetime(
                row.get("death_datetime") or row.get("death_time")
            )
        )
        is not None
    }
    if not explicit_death_times:
        # 正文死亡时间也统一到医院时区，与结构化时间及讨论时间保持一致。
        explicit_death_times = {
            candidate
            for row in death_rows
            if (candidate := _parse_datetime(death_time_from_body(row))) is not None
        }
    if len(explicit_death_times) > 1:
        return "conflict", None

    if death_rows:
        # 文书 record_time/submit_time 只表示记录完成时间，不能替代实际死亡时间。
        # 死亡记录存在仍足以确认死亡状态；时限规则会因缺少死亡时刻而数据缺口关闭。
        return "present", next(iter(explicit_death_times), None)

    status = _registration_status(registration_rows)
    death_time = next(iter(explicit_death_times), None)
    if death_time is not None or any(marker in status for marker in _DEATH_MARKERS):
        return "present", death_time
    if (
        status and any(marker in status for marker in _ALIVE_DISCHARGE_MARKERS)
    ) or discharge_rows:
        return "absent", None
    return "unknown", None


def _discharge_time(
    registration_rows: Sequence[Mapping[str, Any]],
    discharge_rows: Sequence[Mapping[str, Any]],
    horizon_rows: Sequence[Mapping[str, Any]] = (),
    horizon_error: str = "",
) -> datetime | None:
    return _discharge_time_with_source(
        registration_rows,
        discharge_rows,
        horizon_rows,
        horizon_error,
    )[0]


def _discharge_time_with_source(
    registration_rows: Sequence[Mapping[str, Any]],
    discharge_rows: Sequence[Mapping[str, Any]],
    horizon_rows: Sequence[Mapping[str, Any]] = (),
    horizon_error: str = "",
) -> tuple[datetime | None, str]:
    if horizon_error in _BLOCKING_DISCHARGE_HORIZON_ERRORS:
        return None, ""
    if len(horizon_rows) == 1:
        horizon_row = horizon_rows[0]
        if _clean(horizon_row.get("basis")) == "discharge_date":
            horizon_time = _parse_datetime(horizon_row.get("horizon_datetime"))
            horizon_date = _parse_datetime(horizon_row.get("horizon_date"))
            if (
                horizon_time is not None
                and horizon_date is not None
                and horizon_time.date() != horizon_date.date()
            ):
                return None, ""
            if horizon_time is not None or horizon_date is not None:
                return (
                    horizon_time or horizon_date,
                    "evaluation_context.horizon",
                )

    for row in registration_rows:
        for field_name in ("discharge_datetime", "discharge_time"):
            parsed = _parse_datetime(row.get(field_name))
            if parsed is not None:
                return parsed, f"inpat_registration.{field_name}"

    for row in discharge_rows:
        discharge_date = _parse_datetime(row.get("discharge_date"))
        precise_time: tuple[datetime, str] | None = None
        for field_name in ("discharge_datetime", "discharge_time"):
            parsed = _parse_datetime(row.get(field_name))
            if parsed is not None:
                precise_time = (parsed, field_name)
                break
        # CDM 标准 discharge_date 决定业务日；同日的兼容时间补足精度，
        # 跨日矛盾时不能让兼容字段覆盖标准日期。
        if discharge_date is not None:
            if precise_time is not None and precise_time[0].date() == discharge_date.date():
                return precise_time[0], f"discharge_record.{precise_time[1]}"
            return discharge_date, "discharge_record.discharge_date"
        if precise_time is not None:
            return precise_time[0], f"discharge_record.{precise_time[1]}"
    return None, ""


def _registration_discharge_times(
    registration_rows: Sequence[Mapping[str, Any]],
) -> tuple[datetime, ...]:
    """收集登记来源中的唯一权威出院时间，供061冲突关闭使用。"""

    return tuple(
        sorted(
            {
                parsed
                for row in registration_rows
                if (
                    parsed := _parse_datetime(
                        row.get("discharge_datetime") or row.get("discharge_time")
                    )
                )
                is not None
            }
        )
    )


def _row_text(row: Mapping[str, Any]) -> str:
    return "\n".join(
        _clean(row.get(key))
        for key in ("record_content", "discharge_order", "document_title")
        if _clean(row.get(key))
    )


def _has_explicit_diagnosis_change_event(text: str) -> bool:
    """只接受已落地的诊断修正/补充表达，排除否定、条件和泛指。"""

    for match in _DIAGNOSIS_CHANGE_EVENT_PATTERN.finditer(text):
        clause_start = max(
            text.rfind(separator, 0, match.start())
            for separator in ("。", "！", "!", "？", "?", "；", ";", "\n", "\r")
        )
        prefix = text[clause_start + 1:match.start()].strip()
        if _DIAGNOSIS_CHANGE_NON_EVENT_PREFIX_PATTERN.search(prefix) is None:
            return True
    return False


def _normalized_admission_diagnosis_name(raw_name: Any) -> str:
    """剥离入院记录诊断名尾部的签名/记录时间，只保留变更后诊断名。"""

    text = _clean(raw_name)
    if not text:
        return ""
    cleaned_parts: list[str] = []
    for line in text.splitlines():
        head = _ADMISSION_DIAGNOSIS_LABEL_PATTERN.split(line, maxsplit=1)[0]
        cleaned_parts.append(_ADMISSION_DIAGNOSIS_TIME_PATTERN.sub(" ", head))
    normalized = " ".join(" ".join(cleaned_parts).split())
    return normalized.strip(" \t\r\n;；,，。.")


def _diagnosis_change_declarations(
    rows: Sequence[Mapping[str, Any]],
) -> tuple[str, ...]:
    """客户入院记录诊断中显式声明的“修正/补充诊断”名称（去重保序）。

    该来源所有类型行都没有诊断序号与诊断时间，只能作为“变更已经发生”的
    触发信号：不能挂成 diagnosis_rows，也不能据此做时间序校验。
    """

    declarations: list[str] = []
    for row in rows:
        if _clean(row.get("diagnosis_type")) not in _ADMISSION_DIAGNOSIS_CHANGE_TYPES:
            continue
        name = _normalized_admission_diagnosis_name(row.get("diagnosis_name"))
        # 一栏常以“1.甲；2.乙”列出多个变更诊断，逐个作为独立变更与病程关联。
        for part in _ADMISSION_DIAGNOSIS_LIST_SEPARATOR.split(name):
            part = part.strip(" \t\r\n;；,，。.")
            if part and part not in declarations:
                declarations.append(part)
    return tuple(declarations)


def _diagnosis_change_candidates(
    rows_by_source: Sequence[tuple[str, Sequence[Mapping[str, Any]]]],
    *,
    diagnosis_name: str,
    not_before: datetime | None = None,
) -> tuple[tuple[datetime | None, str, str, Mapping[str, Any]], ...]:
    """提及变更后诊断名的病程候选（按记录时间排序，未计时排后）。

    是否记录了理由与依据由受控语义抽取判断，这里只做名称与时序上的候选收集。
    """

    candidates = [
        (_row_time(row), _row_text(row), source_key, row)
        for source_key, source_rows in rows_by_source
        for row in source_rows
        if diagnosis_name and diagnosis_name in _row_text(row)
    ]
    if not_before is not None:
        candidates = [
            item for item in candidates if item[0] is None or item[0] >= not_before
        ]
    return tuple(sorted(candidates, key=lambda item: (item[0] is None, item[0] or datetime.min)))


async def _assess_diagnosis_change_documentation(
    pairs: Sequence[tuple[str, Mapping[str, Any], str, str]],
    change_names: Sequence[str],
    llm_client: Any,
) -> tuple[str, str, dict[str, Any] | None, Any]:
    """对 (来源, 病程行, 正文, 变更诊断名) 候选做一次受控抽取并按诊断汇总。

    同一变更诊断的理由与依据可分记于不同病程；任一诊断确定未记录→不合规，
    仅因语义未知而无法确认→不确定。
    """

    extraction = await extract_diagnosis_change_documentation(
        tuple(
            DiagnosisChangeDocumentInput(
                local_doc_id=f"doc_{index:02d}",
                source_type=source_key,
                text=text,
                changed_diagnosis=name,
            )
            for index, (source_key, _row, text, name) in enumerate(pairs, 1)
        ),
        llm_client,
    )
    if extraction.state != "ready":
        return extraction.state, extraction.reason_code, None, extraction
    reason = {name: False for name in change_names}
    basis = {name: False for name in change_names}
    unknown = {name: False for name in change_names}
    for (_source_key, _row, _text, name), assertion in zip(pairs, extraction.assertions):
        reason[name] = reason[name] or assertion.reason_state == "present"
        basis[name] = basis[name] or assertion.basis_state == "present"
        unknown[name] = unknown[name] or "unknown" in (assertion.reason_state, assertion.basis_state)
    unsatisfied = [name for name in change_names if not (reason[name] and basis[name])]
    if not unsatisfied:
        final_state, reason_code = "compliant", "requirement_satisfied"
    elif any(not unknown[name] for name in unsatisfied):
        final_state, reason_code = "non_compliant", "requirement_violated"
    else:
        return "uncertain", "semantic_low_confidence", None, extraction
    return final_state, reason_code, {
        "verification_kind": "diagnosis_change_documentation_check",
        "diagnosis_change_count": len(change_names),
        "reason_recorded": all(reason.values()),
        "basis_recorded": all(basis.values()),
    }, extraction


def _material_text(row: Mapping[str, Any]) -> str:
    return "\n".join(
        _clean(row.get(key))
        for key in (
            "record_content", "document_title", "order_name", "generic_name",
            "case_characteristic", "diagnose_based_on", "differential_diagnosis", "treatment_plan",
            # 转入记录的诊疗计划章节（通用正文为空时药物与处置只写在这里，1019 C10）。
            "transfer_treatment_plan",
            # 手术记录正文在手术经过（054/057 围术期预防用药引文）。
            "surgery_process",
            "item_code", "item_name", "item_abbreviation", "result",
            "result_flag", "abnormal_flag", "diagnosis_name", "labtest_subject",
            "specimen",
        )
        if _clean(row.get(key))
    )


def _antimicrobial_orders(rows: Sequence[Mapping[str, Any]]) -> tuple[Mapping[str, Any], ...]:
    # 用户口径（2026-10-22）：滴眼、外用、冲洗等局部用药不算抗菌药使用。
    return tuple(row for row in rows if _antimicrobial_names_in(row) and not is_local_route_drug_order(row))


def _has_performed_antimicrobial_administration(
    text: str, names: Sequence[str],
) -> bool:
    """取消与已实施冲突时保留事件；计划、否定和历史给药不是本次实施。"""

    target = "|".join(re.escape(name) for name in names)
    action = re.compile(
        r"已给予|已使用|已启用|已输注|实际给予|实际使用"
        + (rf"|(?:已予以|予以|已予|给予|(?<![给不未])予)(?=\s*(?:{target}))" if target else "")
    )
    for clause in re.split(r"[，,。；;！!？?\n]", text):
        for match in action.finditer(clause):
            prefix = clause[:match.start()]
            if re.search(
                r"(?:未|未曾|未能|不|并非|否认)\s*$"
                r"|(?:考虑|需|应|将|待)\s*$"
                r"|拟|计划|建议|准备|尚待|等待|需待|是否|若|如果"
                r"|既往|曾经|曾用|院外|外院|入院前|用药史",
                prefix,
            ):
                continue
            following = clause[match.end():]
            following_names = _antimicrobial_names_in({"record_content": following})
            if following_names:
                nearest = min(following_names, key=following.index)
                if nearest not in names:
                    continue
            else:
                preceding_names = _antimicrobial_names_in({"record_content": prefix})
                if preceding_names and max(preceding_names, key=prefix.rindex) not in names:
                    continue
            return True
    return False


def _exclude_unperformed_antimicrobial_orders(
    orders: Sequence[Mapping[str, Any]],
    course_rows: Sequence[Mapping[str, Any]],
) -> tuple[tuple[Mapping[str, Any], ...], tuple[Mapping[str, Any], ...]]:
    """仅排除明确未实施事件；停用不等于从未给药，同名多医嘱不猜归属。"""

    kept: list[Mapping[str, Any]] = []
    excluded_evidence: list[Mapping[str, Any]] = []
    for order in orders:
        names = _antimicrobial_names_in(order)
        order_id = _linked_order_id(order)
        linked_rows = []
        for row in course_rows:
            row_id = _linked_order_id(row)
            row_names = _antimicrobial_names_in(row)
            if row_id:
                matches = bool(order_id and row_id == order_id)
            else:
                matches = bool(
                    len(names) == 1 and row_names == names
                    and sum(names[0] in _antimicrobial_names_in(item) for item in orders) == 1
                )
            if matches:
                linked_rows.append(row)
        texts = tuple(_material_text(row) for row in (order, *linked_rows))
        # 明确已实施与取消信息冲突时，不把已用药事件静默删去。
        performed = any(
            _has_performed_antimicrobial_administration(text, names)
            for text in texts
        )
        unperformed_rows = tuple(
            row for row in (order, *linked_rows)
            if re.search(r"(?:未实际给药|未实际使用|从未给药|未曾给药)", _material_text(row))
        )
        cancelled = _clean(order.get("order_status")) in {
            "取消", "已取消", "作废", "已作废", "撤销", "未执行",
        }
        if not performed and (cancelled or unperformed_rows):
            excluded_evidence.extend((order, *unperformed_rows))
        else:
            kept.append(order)
    return tuple(kept), tuple(excluded_evidence)


def _antimicrobial_reason_clauses(row: Mapping[str, Any]) -> tuple[str, ...]:
    """理由缺失声明不能以其中的“理由/依据”字面值充当正向事实。"""

    return tuple(
        clause for clause in re.split(r"[，,。；;\n]", _material_text(row))
        if not re.search(
            r"(?:理由|依据|感染证据).{0,4}(?:未记录|未说明|缺失|不详|未提供)"
            r"|(?:无|缺少|未记录|未说明).{0,4}(?:理由|依据|感染证据)",
            clause,
        )
    )


def _055_treatment_orders(
    rows: Sequence[Mapping[str, Any]],
) -> tuple[Mapping[str, Any], ...]:
    """055 只为实际抗菌治疗建窗；皮试医嘱不是治疗起点。"""

    return tuple(
        row for row in rows
        if _clean(row.get("drug_apply_method")) != "皮试"
    )


def _parse_lx0609_058_datetime(value: Any) -> datetime | None:
    """Parse LX058 timestamps while preserving offsets in hospital local time.

    Untagged source values are already hospital-local and retain the historical
    naive comparison behavior.  Offset-bearing values are converted to the
    hospital timezone before dropping tzinfo so mixed representations compare
    by the same instant.
    """

    text = _clean(value)
    if not text:
        return None
    normalized = text.replace("T", " ").replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        return None
    if parsed.tzinfo is not None:
        parsed = parsed.astimezone(_LX0609_HOSPITAL_TIMEZONE).replace(tzinfo=None)
    return parsed


def _antimicrobial_start_datetime(row: Mapping[str, Any]) -> datetime | None:
    """按院方口径读取抗菌药启用时间；计划时间缺失时回退医嘱下达时间。"""

    return _parse_datetime(
        row.get("planned_start_datetime") or row.get("prescribed_datetime")
    )


def _lx0609_058_first_use_events(
    events: Sequence[tuple[Mapping[str, Any], str, datetime | None]],
) -> tuple[tuple[Mapping[str, Any], str, datetime | None], ...]:
    """每种特殊级药物只保留首次启用事件。

    用户口径（2026-10-17）：同一药物后续续开或调整剂量的医嘱沿用首次启用时的专家支持。
    同药任一医嘱缺启用时间时无法确定首次启用，保留缺时间事件交由时间缺口出口处理。
    """

    first: dict[str, tuple[Mapping[str, Any], str, datetime | None]] = {}
    for event in events:
        _order, name, start = event
        current = first.get(name)
        if current is None:
            first[name] = event
        elif current[2] is None:
            continue
        elif start is None or start < current[2]:
            first[name] = event
    return tuple(first.values())


def _lx0609_058_row_time(row: Mapping[str, Any]) -> datetime | None:
    value = authoritative_document_time_value(row)
    return _parse_lx0609_058_datetime(
        value
        or row.get("death_datetime")
        or row.get("death_time")
        or row.get("discharge_datetime")
        or row.get("discharge_time")
    )


def _is_special_antimicrobial_expert_support(row: Mapping[str, Any]) -> bool:
    """排除明确拒绝/未完成的会诊文字，避免否定句充当支持证据。"""

    text = _material_text(row)
    return (
        (
            _has_any_text((row,), _SPECIAL_ANTIMICROBIAL_EXPERT_SUPPORT_MARKERS)
            or (
                _SPECIAL_ANTIMICROBIAL_INFECTION_EXPERT_PATTERN.search(text)
                and _antimicrobial_names_in(row, _SPECIAL_ANTIMICROBIALS)
                and re.search(r"(?:建议|同意|予以|给予).{0,24}(?:抗感染|美罗培南|亚胺培南|利奈唑胺|万古霉素)", text)
                and not re.search(r"(?:不同意|不建议|暂不|拒绝).{0,24}(?:抗感染|美罗培南|亚胺培南|利奈唑胺|万古霉素)", text)
            )
        )
        and not _SPECIAL_ANTIMICROBIAL_EXPERT_SUPPORT_NEGATED_PATTERN.search(text)
    )


def _special_approval_by_authorized_expert(text: str, quote: str) -> bool:
    """同意引文本身或其紧邻前文须出现授权专家身份，不能借同文书其他段落的专家署名。"""

    position = text.find(quote)
    if position < 0:
        return False
    # 身份只看引文及其前80字：感染科副主任医师意见中“请临床药学会诊后同意加用”仍出自授权专家（C04）；
    # 无授权专家署名的药学会诊或用药申请单文字不能借同文书其他段落的署名（C05）。
    context = text[max(0, position - 80): position + len(quote)]
    return bool(
        _SPECIAL_ANTIMICROBIAL_INFECTION_EXPERT_PATTERN.search(context)
        or any(marker in context for marker in _SPECIAL_ANTIMICROBIAL_EXPERT_SUPPORT_MARKERS)
    )


def _has_any_text(rows: Sequence[Mapping[str, Any]], markers: Sequence[str]) -> bool:
    return any(any(marker in _material_text(row) for marker in markers) for row in rows)


@dataclass(frozen=True)
class _AntimicrobialReasonAction:
    """054 的一个可证明、已命名的抗菌药处置动作。"""

    row: Mapping[str, Any]
    antimicrobial: str
    action: str
    order_ids: tuple[str, ...]
    orders: tuple[Mapping[str, Any], ...]


# 054 用户口径（2026-10-18）：延续原方案不是需要记录理由的用药动作，
# 只查使用/加用、停用、更换、新增联合、超说明书。
_054_CHANGE_ACTION_PATTERN = re.compile(
    r"加用|停用|停药|停止使用|更换|换用|改为|改用|调整为|降阶梯|升阶梯|启用|开始使用|首次使用|新加|超说明书"
)
_054_ADMINISTER_VERB_PATTERN = re.compile(r"予以|给予|使用|应用|静滴|口服|联用")
_054_CONTINUATION_CLAUSE_PATTERN = re.compile(r"继续|维持|续用|仍予|仍用")
_054_UNCHANGED_SENTENCE_PATTERN = re.compile(
    r"暂无调整|暂不调整|未作调整|无调整|治疗同前|方案同前|维持原方案|方案不变|继续(?:目前|当前|原)"
)


# 054 用户口径（2026-10-18，C05）：“给予X抗感染后仍有反复发热”是用药后病情回顾，不是新动作。
_054_RETROSPECTIVE_OUTCOME_PATTERN = re.compile(
    r"后(?:仍|仍有|无|未见|未|好转|改善|缓解|效果|体温|症状|病情|出现|反复)"
)


def _054_governs_drug(gap: str) -> bool:
    """延续标记与药名之间没有新的给药动词（紧跟标记的“继续予以”等复合写法除外）。"""

    gap = re.sub(r"^\s*(?:予以|给予|使用|应用|联用)", "", gap)
    return not _054_ADMINISTER_VERB_PATTERN.search(gap)


def _054_is_continuation_only(row: Mapping[str, Any], antimicrobial: str) -> bool:
    """该病程对目标药的所有提及都只是延续原方案时返回 True。

    以目标药所在分句为准：分句有加用/停用/更换等变更词即为触发；分句自身写
    “继续/维持”，或分句无给药动词而上一分句写“继续”（共用动词），视为延续；
    句中药名之前有“暂无调整/治疗同前”等且其间没有新的给药动词，也视为延续。
    分句在药名之后写“后仍有/后好转”等用药后病情，是既往用药回顾，同样不是新动作。
    """

    text = _material_text(row)
    continuation = False
    for sentence in re.split(r"[。；;！!？?\n]", text):
        if antimicrobial not in sentence:
            continue
        clauses = re.split(r"[，,]", sentence)
        offset = 0
        for index, clause in enumerate(clauses):
            clause_start = offset
            offset += len(clause) + 1
            if antimicrobial not in clause:
                continue
            if any(
                not re.search(r"(?:不|未|无需|无须|勿)(?:建议|考虑|需要|需|予|再)?$", clause[:change.start()])
                for change in _054_CHANGE_ACTION_PATTERN.finditer(clause)
            ):
                return False
            clause_drug_at = clause.find(antimicrobial)
            if _054_RETROSPECTIVE_OUTCOME_PATTERN.search(clause[clause_drug_at + len(antimicrobial):]):
                continuation = True
                continue
            drug_at = clause_start + clause_drug_at
            unchanged = any(
                _054_governs_drug(sentence[marker.end():drug_at])
                for marker in _054_UNCHANGED_SENTENCE_PATTERN.finditer(sentence[:drug_at])
            )
            if (
                any(
                    _054_governs_drug(clause[marker.end():clause_drug_at])
                    for marker in _054_CONTINUATION_CLAUSE_PATTERN.finditer(clause[:clause_drug_at])
                )
                or (
                    index > 0
                    and not _054_ADMINISTER_VERB_PATTERN.search(clause)
                    and _054_CONTINUATION_CLAUSE_PATTERN.search(clauses[index - 1])
                )
                or unchanged
            ):
                continuation = True
                continue
            return False
    return continuation


# 同一病程内与目标药同句的病情依据（用户口径 2026-10-18，程序判定）：
# “鉴于…故/因此…”因果结构，或炎性指标、体温、症状等变化。
_054_CAUSAL_CONNECTOR_PATTERN = re.compile(r"鉴于|故|因此|所以|遂|据此|结合")
_054_CLINICAL_BASIS_PATTERN = re.compile(
    r"(?:炎性|炎症|感染)指标[^，,。；;]{0,8}(?:下降|降低|好转|恢复正常|正常|升高|增高)"
    r"|(?:体温|血象|白细胞|降钙素原|PCT|CRP|C反应蛋白)[^，,。；;]{0,8}(?:正常|下降|降低|好转|升高|增高)"
    r"|(?:症状|病情|感染|腹泻|咳嗽|咳痰|发热)[^，,。；;]{0,6}(?:好转|缓解|控制|加重|无改善|未见好转)"
)


def _054_reason_in_action_sentence(row: Mapping[str, Any], antimicrobial: str) -> bool:
    """理由须与目标药同句且位于药名之前：因果连接词前有内容，或写有病情依据。"""

    sentences = re.split(r"[。；;！!？?\n]", _material_text(row))
    for index, sentence in enumerate(sentences):
        position = sentence.find(antimicrobial)
        if position < 0:
            continue
        prefix = sentence[:position]
        if _054_CLINICAL_BASIS_PATTERN.search(prefix):
            return True
        # “……。故更换X”：以“故/因此/遂”起句即声明理由在上一句。
        if (
            index > 0
            and re.match(r"\s*(?:故|因此|所以|遂|据此)", prefix)
            and re.search(r"[一-鿿]{4,}", sentences[index - 1])
        ):
            return True
        connector = None
        for connector in _054_CAUSAL_CONNECTOR_PATTERN.finditer(prefix):
            pass
        if connector is not None and re.search(r"[一-鿿]{4,}", prefix[:connector.start()]):
            return True
    return False


def _054_action_events(
    rows: Sequence[Mapping[str, Any]],
    antimicrobial_orders: Sequence[Mapping[str, Any]],
    confirmed_actions: Mapping[tuple[int, str], str],
) -> tuple[tuple[_AntimicrobialReasonAction, ...], bool, tuple[str, ...]]:
    """仅从病程里的“具体药物 + 明确动作”建立054触发事件。

    医嘱的普通存在、order_status、update_time 都不表示这里要求的使用或调整
    事实；不得据此推断停用或更换。
    """

    events: list[_AntimicrobialReasonAction] = []
    order_events = _antimicrobial_order_events(antimicrobial_orders)
    mentioned_antimicrobials: list[str] = []
    association_failed = False
    for row_index, row in enumerate(rows):
        for antimicrobial in _antimicrobial_names_in(row):
            if (
                action := confirmed_actions.get((row_index, antimicrobial))
            ) is None:
                continue
            if _054_is_continuation_only(row, antimicrobial):
                continue
            mentioned_antimicrobials.append(antimicrobial)
            row_order_id = _linked_order_id(row)
            if row_order_id:
                candidates = tuple(
                    order_event
                    for order_event in order_events
                    if row_order_id in order_event.order_ids
                    and antimicrobial in order_event.antimicrobials
                )
            else:
                candidates = tuple(
                    order_event
                    for order_event in order_events
                    if antimicrobial in order_event.antimicrobials
                )
            if row_order_id and len(candidates) != 1:
                # 病程带医嘱号时必须唯一对上该医嘱，不能让其他同名医嘱代为触发。
                association_failed = True
                continue
            if not candidates:
                # 本次就诊没有同药受控医嘱，病程动作无法证明属于本次用药。
                association_failed = True
                continue
            # 同药多次开立且源库无停止时间时无法定位具体哪条（用户口径 2026-10-18：
            # 存在同药医嘱即关联成立）；不绑定医嘱号，理由归属按药名规则处理。
            single = candidates[0] if len(candidates) == 1 else None
            events.append(_AntimicrobialReasonAction(
                row=row,
                antimicrobial=antimicrobial,
                action=action,
                order_ids=single.order_ids if single is not None else (),
                orders=(
                    single.orders if single is not None
                    else tuple(order for candidate in candidates for order in candidate.orders)
                ),
            ))
    return (
        tuple(events),
        association_failed,
        tuple(dict.fromkeys(mentioned_antimicrobials)),
    )


def _054_reason_documented(row: Mapping[str, Any]) -> bool:
    return any(
        marker in clause
        for clause in _antimicrobial_reason_clauses(row)
        for marker in _ANTIMICROBIAL_REASON_MARKERS
    )


def _054_event_reason_state(
    *,
    event: _AntimicrobialReasonAction,
    all_events: Sequence[_AntimicrobialReasonAction],
    course_rows: Sequence[Mapping[str, Any]],
) -> tuple[str, Mapping[str, Any] | None]:
    """返回单个054动作的理由状态：documented/missing/ambiguous。

    同一条动作病程内的理由天然同源，优先认可。分开的理由必须有共同医嘱
    标识，或在同名动作仅出现一次时以药名唯一归属；不能让同一条泛化理由
    共享给多次同名动作。
    """

    if _054_reason_documented(event.row) or _054_reason_in_action_sentence(
        event.row, event.antimicrobial
    ):
        return "documented", event.row

    same_name_events = tuple(
        candidate
        for candidate in all_events
        if candidate.antimicrobial == event.antimicrobial
    )
    has_unresolvable_candidate = False
    for row in course_rows:
        if row is event.row or not _054_reason_documented(row):
            continue
        row_order_id = _linked_order_id(row)
        row_names = _antimicrobial_names_in(row)
        if event.order_ids and row_order_id:
            if row_order_id in event.order_ids:
                return "documented", row
            continue
        if row_order_id or event.order_ids:
            # 只有一端带医嘱标识时，不能用同名猜测它们属于同一动作。
            if event.antimicrobial in row_names:
                has_unresolvable_candidate = True
            continue
        if event.antimicrobial in row_names:
            if len(same_name_events) == 1:
                return "documented", row
            has_unresolvable_candidate = True
            continue
        if len(all_events) == 1 and not row_names:
            return "documented", row
        if not row_names:
            has_unresolvable_candidate = True
    return ("ambiguous" if has_unresolvable_candidate else "missing"), None


def _is_explicit_empiric_antimicrobial_use(row: Mapping[str, Any]) -> bool:
    """只以明确的经验用药表述触发057，排除药敏/培养后的目标治疗。"""

    text = _material_text(row)
    if not _EMPIRIC_ANTIMICROBIAL_TRIGGER_PATTERN.search(text):
        return False
    if _EMPIRIC_ANTIMICROBIAL_NEGATED_PATTERN.search(text):
        return False
    if any(marker in text for marker in _TARGETED_ANTIMICROBIAL_MARKERS):
        return False
    # 单独的“经验性”必须同时有实际抗菌用药动作，不能把泛泛的病情描述
    # 误作经验用药事件；其余完整术语本身已足以表示触发事实。
    if "经验性" in text and not any(
        marker in text
        for marker in (
            "经验性用药", "经验性抗感染", "经验性抗菌治疗",
        )
    ):
        return (
            any(action in text for action in ("启用", "使用", "给予", "用药", "治疗"))
            and (
                bool(_antimicrobial_names_in(row))
                or any(marker in text for marker in _ANTIMICROBIAL_EFFECT_CONTEXT_MARKERS)
            )
        )
    return True


def _is_pathogen_lab(row: Mapping[str, Any]) -> bool:
    """病原学项目身份只取检验名称，不把任意核酸检测等同于病原学。"""
    text = " ".join(_clean(row.get(field)) for field in (
        "labtest_subject", "lab_item_name", "item_name", "record_content",
    ))
    return bool(
        re.search(r"培养|药敏|病原", text)
        or re.search(r"(?:病毒|细菌|真菌|支原体|衣原体|结核|HBV|HCV|HIV).{0,20}(?:核酸|DNA|RNA)", text, re.I)
    )


@dataclass(frozen=True)
class _EmpiricAntimicrobialEvent:
    """057 已关联的同药医嘱集合；未绑定具体医嘱时号集合为空。"""
    orders: tuple[Mapping[str, Any], ...]
    antimicrobials: tuple[str, ...]
    order_ids: tuple[str, ...]


def _is_prophylactic_antimicrobial_clause(clause: str) -> bool:
    """预防用药只按抗菌药所在的并列项判断。

    “予以头孢曲松抗感染、奥美拉唑抑酸护胃（预防应激性溃疡）”中的“预防”属于
    抑酸药，不能把同句的抗感染治疗排除（1019 C11）；“预防感染”仍视为预防用药。
    """

    for segment in re.split(r"、", clause):
        if not re.search(r"预防|围术期", segment):
            continue
        if (re.search(r"抗感染|抗菌", segment)
                or _antimicrobial_names_in({"record_content": segment})
                or re.search(r"预防[^、]{0,8}感染", segment)):
            return True
    return False


def _empiric_antimicrobial_event_contexts(
    *,
    antimicrobial_orders: Sequence[Mapping[str, Any]],
    candidate_rows: Sequence[Mapping[str, Any]],
    lab_master_rows: Sequence[Mapping[str, Any]] = (),
    lab_item_rows: Sequence[Mapping[str, Any]] = (),
    pathogen_sources_complete: bool = False,
) -> tuple[tuple[tuple[Mapping[str, Any], _EmpiricAntimicrobialEvent], ...], bool]:
    """返回按药名或唯一医嘱号关联的经验用药事件。"""

    order_events = _antimicrobial_order_events(antimicrobial_orders)
    contexts: list[tuple[Mapping[str, Any], _EmpiricAntimicrobialEvent]] = []
    association_ambiguous = False
    for row in candidate_rows:
        explicit = _is_explicit_empiric_antimicrobial_use(row)
        text = _material_text(row)
        names = _antimicrobial_names_in(row)
        treatment_clauses = tuple(
            clause for clause in re.split(r"[，,。；;\n]", text)
            if re.search(r"抗感染|抗菌治疗", clause)
            and not _is_prophylactic_antimicrobial_clause(clause)
            and _has_performed_antimicrobial_administration(clause, names)
        )
        treatment_names = tuple(dict.fromkeys(
            name for clause in treatment_clauses
            for name in _antimicrobial_names_in({"record_content": clause})
        ))
        # 无“经验性”字样时，只接受有时间的本次已实施、明确治疗感染的
        # 具体用药叙述；计划医嘱和预防用药不进入新增路径。
        inferred_candidate = (
            bool(treatment_names) and _row_time(row) is not None
            and not re.search(r"根据.{0,12}(?:培养|药敏)|依据.{0,12}(?:培养|药敏)", text)
            and not any(marker in text for marker in _TARGETED_ANTIMICROBIAL_MARKERS)
        )
        if not explicit and not inferred_candidate:
            continue
        linked_order_id = _linked_order_id(row)
        mentioned_names = _antimicrobial_names_in(row) if explicit else treatment_names
        if linked_order_id:
            candidates = tuple(
                event
                for event in order_events
                if linked_order_id in event.order_ids
                and (not mentioned_names or all(name in event.antimicrobials for name in mentioned_names))
            )
        elif mentioned_names:
            candidates = tuple(
                event
                for event in order_events
                if any(name in event.antimicrobials for name in mentioned_names)
            )
        elif len(order_events) == 1:
            candidates = order_events
        else:
            candidates = ()
        if not explicit and not linked_order_id and len(candidates) > 1:
            # 沿用经验用药推断的时序门槛；尚未启用的未来医嘱不能证明本次已实施。
            document_time = _row_time(row)
            candidates = tuple(
                event for event in candidates
                if document_time is not None
                and any(
                    (start := _antimicrobial_start_datetime(order)) is None
                    or start <= document_time
                    for order in event.orders
                )
            )
        if not candidates or (linked_order_id and len(candidates) != 1):
            association_ambiguous = association_ambiguous or explicit
            continue
        if len(candidates) > 1 and len({
            name for event in candidates for name in mentioned_names
            if name in event.antimicrobials
        }) > 1:
            # 本轮只合并同药多医嘱；多种药物的原有事件归属边界不变。
            association_ambiguous = association_ambiguous or explicit
            continue
        # 主控代定口径（2026-10-18，待客户复核），基线057：
        # 同药存在即关联；多医嘱不绑定具体号，理由继续按药名归属。
        if not linked_order_id and mentioned_names:
            candidates = tuple(_EmpiricAntimicrobialEvent(
                orders=tuple(order for event in candidates if name in event.antimicrobials
                             for order in event.orders),
                antimicrobials=(name,),
                order_ids=(),
            ) for name in mentioned_names if any(name in event.antimicrobials for event in candidates))
            if len(candidates) != len(mentioned_names):
                if explicit:
                    association_ambiguous = True
                    continue
        if not explicit:
            start = min((value for order in candidates[0].orders
                         if (value := _antimicrobial_start_datetime(order)) is not None), default=None)
            if not pathogen_sources_complete or start is None:
                association_ambiguous = True
                continue
            # 只在完整检验来源中核对启用时已可获得的病原学结果；未知报告
            # 时间不能当作“尚无结果”，已有结果时不推断为经验治疗。
            pathogen_ids = {
                _clean(item.get("test_id")) for item in (*lab_master_rows, *lab_item_rows)
                if _clean(item.get("test_id")) and _is_pathogen_lab(item)
            }
            reports = tuple(item for item in (*lab_master_rows, *lab_item_rows)
                            if _clean(item.get("test_id")) in pathogen_ids)
            prior_basis = False
            unknown_basis_time = False
            for report in reports:
                moment = _parse_datetime(report.get("report_datetime") or report.get("report_time"))
                has_result = bool(_clean(report.get("result")))
                prior_basis = prior_basis or (moment is not None and moment <= start)
                unknown_basis_time = unknown_basis_time or (has_result and moment is None)
            if prior_basis:
                continue
            if unknown_basis_time:
                association_ambiguous = True
                continue
        contexts.extend((row, _EmpiricAntimicrobialEvent(
            event.orders, event.antimicrobials, event.order_ids,
        )) for event in candidates)
    return tuple(contexts), association_ambiguous


def _pathogen_basis_state(
    start: datetime,
    lab_master_rows: Sequence[Mapping[str, Any]],
    lab_item_rows: Sequence[Mapping[str, Any]],
) -> str:
    """开药时是否已有病原学结果：prior 已有、unknown 结果时间不明、none 尚无。"""

    pathogen_ids = {
        _clean(item.get("test_id")) for item in (*lab_master_rows, *lab_item_rows)
        if _clean(item.get("test_id")) and _is_pathogen_lab(item)
    }
    unknown = False
    for report in (*lab_master_rows, *lab_item_rows):
        if _clean(report.get("test_id")) not in pathogen_ids:
            continue
        moment = _parse_datetime(report.get("report_datetime") or report.get("report_time"))
        if moment is not None and moment <= start:
            return "prior"
        unknown = unknown or (bool(_clean(report.get("result"))) and moment is None)
    return "unknown" if unknown else "none"


def _order_reason_rule_outcome(
    *,
    rule_id: str,
    events: Sequence[Any],
    time_missing_names: Sequence[str],
    documents: Mapping[str, Any],
    per_event: Mapping[str, Sequence[str]],
    untimed: frozenset[str],
    extraction: Any,
    lab_master_rows: Sequence[Mapping[str, Any]],
    lab_item_rows: Sequence[Mapping[str, Any]],
    pathogen_sources_complete: bool,
) -> tuple[str, str, Mapping[str, Any] | None, tuple[Mapping[str, Any], ...]]:
    """按医嘱事件映射054/057状态；模型只提供带引文的事实。

    054：每个开始/联合/更换事件须在开医嘱当日病程写明感染判断、选药理由或预防用途。
    057：仅开药时尚无病原学结果的治疗性事件；用户口径（2026-10-22）感染判断与选药理由
    都须记录，选药理由一句话即可（如“经验性覆盖革兰阴性菌”“按指南首选”）；写明“经验性用药/
    经验性抗感染”也算选药理由。
    """

    is_057 = rule_id == "LX0609-05-01-05"
    if time_missing_names:
        return "data_gap", "authoritative_time_missing", None, ()
    if not events:
        return "not_applicable", "trigger_absent_complete", None, ()
    if extraction is None or extraction.state == "technical_error":
        return "technical_error", getattr(extraction, "reason_code", "model_transport_error"), None, ()
    if extraction.state != "ready":
        return "data_gap", extraction.reason_code, None, ()
    facts_by_event = {item.event_id: item for item in extraction.facts}
    evaluated: list[tuple[Any, str]] = []
    for event in events:
        facts = facts_by_event.get(event.event_id)
        if event.kind == "stop":
            if is_057:
                continue
            start_facts = facts_by_event.get(event.start_event_id)
            if start_facts is not None and start_facts.has("planned_duration") and is_planned_stop(
                event, planned_duration(start_facts.quotes["planned_duration"][1]),
            ):
                continue
            if facts is not None and facts.has("stop_reason"):
                evaluated.append((event, "documented"))
            elif event.event_id in untimed or (facts is not None and facts.documented_use == "unknown"):
                evaluated.append((event, "unresolved"))
            else:
                evaluated.append((event, "missing"))
            continue
        if is_057:
            if facts is not None and facts.has("prophylaxis"):
                continue
            basis = _pathogen_basis_state(event.time, lab_master_rows, lab_item_rows)
            if not pathogen_sources_complete or basis == "unknown":
                evaluated.append((event, "unresolved"))
                continue
            if basis == "prior":
                continue
        documented = facts is not None and (
            (facts.has("infection_judgment") and facts.has("selection_reason")) if is_057
            else (facts.has("infection_judgment") or facts.has("selection_reason") or facts.has("prophylaxis"))
        )
        if documented:
            evaluated.append((event, "documented"))
        elif event.event_id in untimed or (facts is not None and facts.documented_use == "unknown"):
            evaluated.append((event, "unresolved"))
        else:
            evaluated.append((event, "missing"))
    if not evaluated:
        return "not_applicable", "trigger_absent_complete", None, ()
    names = list(dict.fromkeys(event.antimicrobial for event, _ in evaluated))
    unmatched = list(dict.fromkeys(event.antimicrobial for event, state in evaluated if state != "documented"))
    evidence: list[Mapping[str, Any]] = []
    for event, state in evaluated:
        evidence.extend(event.orders)
        facts = facts_by_event.get(event.event_id)
        refs = (
            [ref for ref, _quote in facts.quotes.values()] if state == "documented" and facts is not None
            else list(per_event.get(event.event_id, ()))
        )
        evidence.extend(documents[ref].row for ref in dict.fromkeys(refs) if ref in documents)
    evidence = list({id(row): row for row in evidence}.values())
    states = {state for _event, state in evaluated}
    if "missing" in states:
        final_state, reason_code = "non_compliant", "requirement_violated"
    elif "unresolved" in states:
        final_state, reason_code = "data_gap", "association_failed"
    else:
        final_state, reason_code = "compliant", "requirement_satisfied"
    if is_057:
        if final_state == "data_gap":
            return final_state, reason_code, None, tuple(evidence)
        return final_state, reason_code, {
            "verification_kind": "empiric_antimicrobial_reason_check",
            "antimicrobials": names,
            "empiric_use_confirmed": True,
            "reason_or_no_specimen_documented": final_state == "compliant",
        }, tuple(evidence)
    return final_state, reason_code, {
        "verification_kind": "antimicrobial_reason_documentation_check",
        "antimicrobials": names,
        "action_count": len(evaluated),
        "reason_documented": final_state == "compliant",
        "unmatched_antimicrobials": [] if final_state == "compliant" else unmatched,
        "association_ambiguous": final_state == "data_gap",
    }, tuple(evidence)


def _empiric_reason_documented(
    *,
    event_row: Mapping[str, Any],
    order_event: _EmpiricAntimicrobialEvent,
    course_rows: Sequence[Mapping[str, Any]],
) -> Mapping[str, Any] | None:
    """理由只能来自可归属该经验用药事件的病程，不以培养/药敏调整代替。"""

    order_ids = order_event.order_ids
    order_names = order_event.antimicrobials
    for row in course_rows:
        clauses = _antimicrobial_reason_clauses(row)
        if not any(
            any(marker in clause for marker in _EMPIRIC_REASON_MARKERS)
            # 新增同义依据只接受分句起始的明确肯定形式，不在任意前缀后
            # 搜索“证实”。复杂修饰不由短距离否定词排除表推断为肯定。
            or (
                re.match(r"^\s*(?:(?:胸部)?影像)?(?:已)?(?:证实|确诊)"
                         r"(?:为)?(?:细菌|感染)", clause)
                and not re.search(r"尚|未|不|无|非|否|待|拟|可能|可疑|是否|排除", clause)
            )
            for clause in clauses
        ):
            continue
        row_order_id = _linked_order_id(row)
        if row_order_id:
            matches = tuple(event for event in _antimicrobial_order_events(order_event.orders)
                            if row_order_id in event.order_ids)
            if len(matches) == 1 and (not order_ids or row_order_id in order_ids):
                return row
            continue
        row_names = _antimicrobial_names_in(row)
        if row_names and any(name in order_names for name in row_names):
            return row
        if row is event_row and len(order_names) == 1:
            return row
    return None


def _antimicrobial_document_refs(
    *,
    snapshot: Luxian0609EvidenceSnapshot,
    materials: Luxian0609EvidenceMaterialStore,
    selected_rows: Sequence[Mapping[str, Any]],
) -> tuple[str, ...]:
    """仅把执行器实际消费的抗菌药行映射为同快照、逐文书引用。

    选择结果必须在允许来源中唯一命中；重复或无法定位时返回空集。调用方会把
    “已消费却不能精确坐标化”交给 Binding 判为技术错误，绝不回退为整类文书或
    投影内部 ``source_document_refs``。未消费任何文书的否定结论则另行使用受控
    的源级判定锚点，不能与前一种技术失败混淆。
    """

    allowed_sources = (
        "inpat_drug_order",
        "first_course_record",
        "transfer_in_record",
        "daily_course_record",
        "senior_course_record",
        "consultation_record",
        "surgery_record",
        "anesthesia_record",
    )
    refs: list[str] = []
    for selected_row in selected_rows:
        matches: list[str] = []
        for source_key in allowed_sources:
            try:
                document_rows = materials.document_rows(source_key, snapshot=snapshot)
            except (EvidenceMaterialUnavailable, EvidenceMaterialTruncated):
                # 未消费该来源时，它的不可用不应抹掉另一来源已精确定位的文书。
                continue
            matches.extend(
                reference
                for reference, material_row in document_rows
                if material_row == selected_row
            )
        if len(matches) != 1:
            return ()
        refs.append(matches[0])
    return tuple(dict.fromkeys(refs))


_MAIN_DIAGNOSIS_FLAGS = frozenset({"是", "1", "Y", "y", "true", "True"})


def _written_main_diagnosis(rows: Sequence[Mapping[str, Any]]) -> str | None:
    """唯一标记为主诊断且未罗列多条诊断的书写诊断名称；否则无法核对返回 None。"""

    flagged = [
        _clean(row.get("diagnosis_name") or row.get("diagnosis"))
        for row in rows
        if _clean(row.get("diagnosis_main")) in _MAIN_DIAGNOSIS_FLAGS
    ]
    if len(flagged) != 1 or not flagged[0]:
        return None
    if len(split_numbered_diagnoses(flagged)) != 1:
        return None
    return flagged[0]


def _diagnosis_sequence(rows: Sequence[Mapping[str, Any]]) -> tuple[tuple[str, ...], str | None]:
    """名称完整后才比较内容；多行仅以唯一合法序号建立顺序。"""
    if not rows:
        return (), "diagnoses_missing"
    names = tuple(_clean(row.get("diagnosis_name") or row.get("diagnosis")) for row in rows)
    if not all(names):
        return names, "name_missing"
    # 单条诊断不存在相对顺序问题；不能因为源表未填写冗余序号而丢掉
    # 已经可以确定的名称一致性结论。
    if len(rows) == 1:
        return names, None
    positions: list[int] = []
    missing = False
    invalid = False
    for row in rows:
        value = row.get("diagnosis_no")
        if value is None or (isinstance(value, str) and not value.strip()):
            missing = True
            continue
        if type(value) is int:
            position = value
        elif isinstance(value, str):
            normalized = value.strip()
            if re.fullmatch(r"[0-9]{1,9}", normalized):
                position = int(normalized)
            else:
                composite = re.fullmatch(
                    r"[^|\r\n]+\|\|([0-9]{1,9})", normalized
                )
                if composite is None or not normalized.rsplit("||", 1)[0].strip():
                    invalid = True
                    continue
                position = int(composite.group(1))
        else:
            invalid = True
            continue
        if position <= 0:
            invalid = True
        positions.append(position)
    if invalid or len(positions) != len(set(positions)):
        return names, "order_invalid"
    if missing:
        return names, "order_missing"
    return tuple(name for _, name in sorted(zip(positions, names))), None


_DISCHARGE_MEDICATION_REQUIRED_GROUPS = (
    ("drug_name", "generic_name", "name"),
    ("dose", "single_dose"),
    ("route", "drug_apply_method"),
    ("duration", "usage_time", "frequency"),
)


# 院方口径（2026-10-10）：片剂、胶囊、糖浆（及名称已写明口服的制剂）未写给药途径时按剂型
# 默认口服；2026-10-20 用户确认口服颗粒剂沿用该口径，外用、冲洗等用途不推定。
_ORAL_DOSAGE_FORM_PATTERN = re.compile(r"(?:片|胶囊|糖浆|口服液|口服溶液|颗粒)")
_NON_ORAL_TABLET_PATTERN = re.compile(r"(?:舌下片|含片|阴道片|泡腾片|贴片)")
_NON_ORAL_GRANULE_PATTERN = re.compile(r"(?:外用|外洗|冲洗|含漱|漱口|灌肠|阴道|直肠|外敷|湿敷)")
_SAFE_MEDICATION_IDENTITY_SUFFIX = r"(?:钙|钠|镁)?(?:肠溶|缓释|控释|软)?(?:片|胶囊|颗粒|糖浆|口服液)"


@dataclass(frozen=True)
class _FormalDischargeMedication:
    display_name: str
    identity_names: tuple[str, ...]


def _with_dosage_form_oral_route(
    medications: Sequence[Mapping[str, Any]],
    *, oral_prescription_names: Sequence[str] = (), source_text: str = "",
) -> list[Mapping[str, Any]]:
    result: list[Mapping[str, Any]] = []
    for item in medications:
        if (
            not any(_clean(item.get(key)) for key in ("route", "drug_apply_method"))
            and _medication_has_oral_form(item, oral_prescription_names, source_text)
        ):
            result.append({**item, "route": "口服（按剂型推定）"})
        else:
            result.append(item)
    return result


def _medication_has_oral_form(item: Mapping[str, Any], prescription_names: Sequence[str], source_text: str = "") -> bool:
    name = _clean(" ".join(_clean(item.get(key)) for key in ("drug_name", "generic_name", "name")))
    if _NON_ORAL_GRANULE_PATTERN.search(name) or re.search(r"注射|滴眼|滴耳|舌下|含片|贴片|泡腾", name):
        return False
    if _oral_dosage_form(name):
        return True
    # 最短药名引文可能不带紧随其后的“(5mg/片)”规格，仍以同一药名的唯一原文为准。
    if name and source_text.count(name) == 1 and re.search(
        re.escape(name) + r"\s*[（(][^）)；;。\n]{0,35}/片\s*[）)]", source_text,
    ):
        return True
    # 原文计量单位明确为片剂时也可应用默认口服；不覆盖外用或特殊给药剂型。
    if re.search(r"\d\s*片", _clean(item.get("dose"))) and not re.search(
        r"外用|外敷|阴道|舌下|含服|含片|贴片|泡腾", name
    ):
        return True
    if len(name) < 3 or re.search(r"注射|外用|滴眼|滴耳|舌下|含片|复方", name):
        return False
    # 仅补剂型缩写：品牌/规格括号去掉后，药物名称及已知剂型后缀须完整对应。
    for prescribed_name in prescription_names:
        normalized = re.sub(r"[（(][^）)]*[）)]", "", prescribed_name).strip()
        if re.fullmatch(re.escape(name) + _SAFE_MEDICATION_IDENTITY_SUFFIX, normalized):
            return True
    return False


def _discharge_oral_prescription_names(materials: Luxian0609EvidenceMaterialStore) -> tuple[str, ...]:
    """只读同次就诊正式出院处方，仅用于确定口服剂型，不补剂量或频次。"""
    try:
        prescriptions = materials.rows("inpat_prescription")
        items = materials.rows("inpat_prescription_item")
    except (EvidenceMaterialUnavailable, EvidenceMaterialTruncated):
        return ()
    eligible = {
        _clean(row.get("prescription_id")) for row in prescriptions
        if _clean(row.get("prescription_id")) and _clean(row.get("order_type")) == "出院带药"
        and _clean(row.get("order_status")) in {"新开", "执行", "执行中", "核实", "完成"}
        and _clean(row.get("is_deleted")).lower() not in {"1", "true"}
    }
    grouped: dict[str, list[Mapping[str, Any]]] = {}
    for item in items:
        if _clean(item.get("prescription_id")) not in eligible or _clean(item.get("is_deleted")).lower() in {"1", "true"}:
            continue
        name = _clean(item.get("generic_name") or item.get("brand_name"))
        grouped.setdefault(name, []).append(item)
    return tuple(name for name, rows in grouped.items() if name and _oral_dosage_form(name)
                 and all(_clean(row.get("drug_apply_method")).lower() in {"口服", "po"} for row in rows))


def _formal_discharge_prescription_medications(
    materials: Luxian0609EvidenceMaterialStore,
) -> tuple[tuple[_FormalDischargeMedication, ...], str, int]:
    """读取同次就诊正式有效出院处方；名称缺失时保守返回资料缺口。"""

    try:
        prescriptions = materials.rows("inpat_prescription")
    except (EvidenceMaterialUnavailable, EvidenceMaterialTruncated):
        return (), "source_unavailable", 0
    eligible = {
        _clean(row.get("prescription_id")) for row in prescriptions
        if _clean(row.get("prescription_id"))
        and _clean(row.get("order_type")) == "出院带药"
        and _clean(row.get("order_status")) in {"新开", "执行", "执行中", "核实", "完成"}
        and _clean(row.get("is_deleted")).lower() not in {"1", "true"}
    }
    if not eligible:
        return (), "", 0
    try:
        items = materials.rows("inpat_prescription_item")
    except (EvidenceMaterialUnavailable, EvidenceMaterialTruncated):
        return (), "source_unavailable", 0
    result: list[_FormalDischargeMedication] = []
    seen_item_ids: set[str] = set()
    unnamed = 0
    for item in items:
        if (
            _clean(item.get("prescription_id")) not in eligible
            or _clean(item.get("is_deleted")).lower() in {"1", "true"}
        ):
            continue
        item_id = _clean(item.get("prescription_item_id"))
        if item_id and item_id in seen_item_ids:
            continue
        if item_id:
            seen_item_ids.add(item_id)
        names = tuple(dict.fromkeys(
            name for name in (
                _clean(item.get("generic_name")), _clean(item.get("brand_name")),
            ) if name and len(name) <= 160 and "\n" not in name and "\r" not in name
        ))
        if not names:
            unnamed += 1
            continue
        existing_index = next((
            index for index, existing in enumerate(result)
            if set(existing.identity_names) & set(names)
        ), None)
        if existing_index is None:
            result.append(_FormalDischargeMedication(names[0], names))
        else:
            existing = result[existing_index]
            result[existing_index] = _FormalDischargeMedication(
                existing.display_name, tuple(dict.fromkeys((*existing.identity_names, *names))),
            )
    if unnamed:
        return tuple(result), "identity_missing", unnamed
    if len(result) > 20:
        return (), "too_many_items", len(result)
    return tuple(result), "", 0


def _medication_identity_matches(documented_name: Any, prescription_name: Any) -> bool:
    """只接受精确药名或现有有限盐型/剂型后缀，不做泛品牌、片段或相似匹配。"""

    documented = _clean(documented_name)
    prescribed = re.sub(r"[（(][^）)]*[）)]", "", _clean(prescription_name)).strip()
    if not documented or not prescribed:
        return False
    if documented == prescribed:
        return True
    if len(documented) < 3:
        return False
    return bool(re.fullmatch(
        re.escape(documented) + _SAFE_MEDICATION_IDENTITY_SUFFIX, prescribed,
    ))


def _unmatched_formal_discharge_medication_names(
    medications: Sequence[Mapping[str, Any]],
    prescriptions: Sequence[_FormalDischargeMedication],
) -> tuple[str, ...]:
    """一对一绑定正文药物与正式处方，返回处方中未写入正文的受控单药名。"""

    available_documented = set(range(len(medications)))
    missing: list[str] = []
    for prescription in prescriptions:
        matched_index = next((
            index for index in available_documented
            if any(
                _medication_identity_matches(
                    next((_clean(medications[index].get(key)) for key in ("drug_name", "generic_name", "name")
                          if _clean(medications[index].get(key))), ""),
                    identity_name,
                )
                for identity_name in prescription.identity_names
            )
        ), None)
        if matched_index is None:
            if prescription.display_name not in missing:
                missing.append(prescription.display_name)
        else:
            available_documented.remove(matched_index)
    return tuple(missing)


def _oral_dosage_form(name: Any) -> bool:
    text = _clean(name)
    return (
        bool(_ORAL_DOSAGE_FORM_PATTERN.search(text))
        and not _NON_ORAL_TABLET_PATTERN.search(text)
        and not ("颗粒" in text and _NON_ORAL_GRANULE_PATTERN.search(text))
    )


def _with_oral_route_uncertainty_resolved(extraction: Any, *, oral_prescription_names: Sequence[str] = (), source_text: str = "") -> Any:
    """口服剂型未写途径按院方口径推定口服，模型对途径的“不确定”不再阻断判定。

    仅当全部不确定字段都是口服剂型药物的给药途径时升级为 ready；药名、剂量、
    用药时间不确定或非口服剂型的途径不确定，仍保持 unknown。
    同时纠正明确口服剂型的 route=missing，避免其他字段不确定时提前报错缺给药途径。
    """

    if extraction.state not in {"unknown", "ready"} or not extraction.field_assertions:
        return extraction
    medications = _with_dosage_form_oral_route(extraction.medications, oral_prescription_names=oral_prescription_names, source_text=source_text)
    assertions = tuple(
        {**fields, "route": "present"} if _clean(medication.get("route")) else fields
        for medication, fields in zip(medications, extraction.field_assertions)
    )
    unresolved = any(value == "uncertain" for fields in assertions for value in fields.values())
    return replace(extraction, medications=tuple(medications), field_assertions=assertions,
                   state="unknown" if unresolved else "ready",
                   reason_code=extraction.reason_code if unresolved else "discharge_medications_extracted")


def _discharge_medications_complete(medications: Sequence[Mapping[str, Any]]) -> bool:
    return bool(medications) and all(
        all(any(_clean(item.get(key)) for key in group) for group in _DISCHARGE_MEDICATION_REQUIRED_GROUPS)
        for item in medications
    )


def _structured_discharge_medications(
    rows: Sequence[Mapping[str, Any]],
) -> tuple[list[Mapping[str, Any]] | None, str, tuple[int, ...]]:
    labels = {
        "药品名称": "drug_name",
        "用药剂量": "dose",
        "给药途径": "route",
        "用药时间": "duration",
    }
    label_pattern = re.compile(r"(药品名称|用药剂量|给药途径|用药时间)\s*[:：]")
    medications: list[Mapping[str, Any]] = []
    selected_indexes: list[int] = []
    has_discharge_instruction = False
    has_unresolved_medications = False
    for index, row in enumerate(rows):
        structured = row.get("discharge_medications")
        if structured is not None:
            selected_indexes.append(index)
            has_discharge_instruction = True
            if isinstance(structured, list) and all(
                isinstance(item, Mapping) for item in structured
            ):
                medications.extend(structured)
            else:
                has_unresolved_medications = True
            continue
        value = _clean(row.get("discharge_order"))
        if not value:
            continue
        has_discharge_instruction = True
        if not _DISCHARGE_MEDICATION_SIGNAL_PATTERN.search(value):
            continue
        selected_indexes.append(index)
        matches = list(label_pattern.finditer(value))
        if not matches:
            has_unresolved_medications = True
            continue
        # 多药固定标签只接受以药名开头的逐药分组；前置字段归属不明时交给受控抽取。
        multiple_names = sum(match.group(1) == "药品名称" for match in matches) > 1
        if multiple_names and matches[0].group(1) != "药品名称":
            has_unresolved_medications = True
            continue
        parsed: dict[str, str] = {}
        row_medications: list[Mapping[str, Any]] = []
        for position, match in enumerate(matches):
            key = labels[match.group(1)]
            if key == "drug_name" and key in parsed:
                row_medications.append(parsed)
                parsed = {}
            if key in parsed:
                has_unresolved_medications = True
                break
            end = matches[position + 1].start() if position + 1 < len(matches) else len(value)
            parsed[key] = re.split(r"[；;\n]", value[match.end():end].lstrip(), maxsplit=1)[0].strip()
        else:
            row_medications.append(parsed)
            medications.extend(row_medications)
    if has_unresolved_medications or not has_discharge_instruction:
        return None, "required_field_missing", tuple(selected_indexes) or tuple(range(len(rows)))
    return medications, "", tuple(selected_indexes)


async def _resolve_multi_record_discharge_medications(
    rows: Sequence[Mapping[str, Any]],
    llm_client: Any,
    extractions: list[Any],
) -> tuple[str, str, list[Mapping[str, Any]], tuple[int, ...]] | None:
    """多份出院记录：以带药明细完整的记录为准，笼统用药叮嘱不再阻断核对。

    业务确认：同次住院一份写有完整带药明细时，其他只写“继续服药”等未指明
    具体药物的记录不使整体资料不足；但任何记录中出现的具体药物仍须并入核对，
    不能被完整那份掩盖。返回 None 表示不适用本路径，沿用原资料缺口。
    返回 (终态, 原因, 药物, 选中行)：终态非空时直接以该状态交付。
    """

    parsed = [_structured_discharge_medications((row,)) for row in rows]
    if not any(
        not error and medications and _discharge_medications_complete(medications)
        for medications, error, _ in parsed
    ):
        return None
    medications: list[Mapping[str, Any]] = []
    indexes: list[int] = []
    for index, (row, (row_medications, error, _)) in enumerate(zip(rows, parsed)):
        if not error:
            if row_medications:
                medications.extend(row_medications)
                indexes.append(index)
            continue
        # 结构化字段格式非法不属于笼统叮嘱，保持原资料缺口。
        if row.get("discharge_medications") is not None:
            return None
        extraction = _with_oral_route_uncertainty_resolved(
            await extract_discharge_medications(str(row.get("discharge_order") or ""), llm_client)
        )
        extractions.append(extraction)
        if extraction.state in {"technical_error", "data_gap"}:
            return extraction.state, extraction.reason_code, [], ()
        if extraction.state == "absent" or not extraction.medications:
            # 明确无带药或未指明任何具体药物：笼统叮嘱，由完整记录覆盖。
            continue
        if extraction.state == "unknown":
            return "uncertain", extraction.reason_code, [], ()
        medications.extend(extraction.medications)
        indexes.append(index)
    return "", "", medications, tuple(indexes)


def _course_dates(
    rows: Sequence[Mapping[str, Any]],
) -> set:
    return {
        parsed.date()
        for row in rows
        if (parsed := _row_time(row)) is not None
    }


def _course_row_has_body(row: Mapping[str, Any]) -> bool:
    """正文列明确为空时，不把日期本身当作有效病程记录。"""

    # Evidence Snapshot 的病程投影固定保留 record_content。对旧的最小测试
    # 夹具保留“未提供该列”的兼容语义，但一旦来源明确给出空列，必须按资料
    # 不完整处理，不能仅凭 record_time/标题或作者计入覆盖日期。
    if "record_content" not in row:
        return True
    return bool(_clean(row.get("record_content")))


def _qualified_surgery_rows(
    mr_surgery_rows: Sequence[Mapping[str, Any]],
    surgery_record_rows: Sequence[Mapping[str, Any]],
) -> tuple[tuple[Mapping[str, Any], ...], tuple[Mapping[str, Any], ...]]:
    return (
        tuple(
            row
            for row in mr_surgery_rows
            if catalog_surgery_state(row) is not False
        ),
        tuple(
            row
            for row in surgery_record_rows
            if catalog_surgery_state(row) is not False
        ),
    )


def _surgery_applicability_outcome(
    applicability: SurgeryApplicability,
) -> tuple[str, str] | None:
    """将规则族共用门控投影为扩展文书执行器的受控状态。"""

    if applicability.state == "applicable":
        return None
    if applicability.state == "not_applicable":
        return "not_applicable", "performed_event_absent"
    if applicability.state == "technical_error":
        return "technical_error", applicability.reason_code
    return "data_gap", applicability.reason_code


def _performed_surgery_times(
    mr_surgery_rows: Sequence[Mapping[str, Any]],
    surgery_record_rows: Sequence[Mapping[str, Any]],
) -> tuple[datetime, ...]:
    values: list[datetime] = []
    qualified_mr_rows, qualified_record_rows = _qualified_surgery_rows(
        mr_surgery_rows, surgery_record_rows
    )
    for source_key, rows in (
        ("mr_surgery", qualified_mr_rows),
        ("surgery_record", qualified_record_rows),
    ):
        for row in rows:
            values.extend(
                parsed
                for value in trusted_performed_surgery_times(
                    source_key=source_key, row=row
                )
                if (parsed := _parse_datetime(value)) is not None
            )
    return tuple(sorted(set(values)))


def _performed_surgery_event_count(
    mr_surgery_rows: Sequence[Mapping[str, Any]],
    surgery_record_rows: Sequence[Mapping[str, Any]],
) -> int:
    """按权威手术主表优先计数，避免把同台手术的开始/结束时间算成两台。"""

    qualified_mr_rows, qualified_record_rows = _qualified_surgery_rows(
        mr_surgery_rows, surgery_record_rows
    )
    # 正式手术记录是一台手术事件的主依据；mr_surgery 是操作目录补充，
    # 同一台手术可包含多行操作，不能在正式记录存在时用它虚增台次。
    authoritative_rows = qualified_record_rows or qualified_mr_rows
    source_key = "surgery_record" if qualified_record_rows else "mr_surgery"
    return sum(
        1
        for row in authoritative_rows
        if trusted_performed_surgery_times(source_key=source_key, row=row)
    )


@dataclass(frozen=True)
class _PostoperativeSurgeryEvent:
    """064–066 的手术台次投影，保留组成台次的原始行以绑定证据。"""

    source_key: str
    row: Mapping[str, Any]
    document_id: str
    surgery_name: str
    surgery_end_time: datetime | None
    surgeon_names: tuple[str, ...]
    surgeon_tokens: frozenset[str]
    surgery_begin_time: datetime | None = None
    # 院方口径（2026-10-10）：源库缺实际结束时间时以开始时间推算术后起点。
    surgery_time_estimated: bool = False
    member_rows: tuple[Mapping[str, Any], ...] = ()
    # 缺手术记录、仅首页手术日期（0点）时，手术时刻未知（C23、C25 源库缺手术记录单据）。
    surgery_time_date_only: bool = False


# 064 院方口径：术者须亲自在术前24小时内、术后24小时内查房。
_SURGEON_ROUND_WINDOW_HOURS = 24
_PHYSICIAN_TITLE_SUFFIXES = (
    "副主任医师",
    "主任医师",
    "主治医师",
    "住院医师",
    "医师",
)
_TITLE_ROUND_MARKER_PATTERN = re.compile(r"(?:查房|巡诊)")
_TITLE_ROUND_ROLE_DESCRIPTION_PATTERN = re.compile(
    r"(?:术者\s*[:：]|手术由[^，,；;。]*完成)"
)
_MASKED_PHYSICIAN_IDENTITY_PATTERN = re.compile(r"(?:某|匿名|脱敏|[*＊×])")


def _normalized_physician_token(value: Any) -> str:
    token = re.sub(r"\s+", "", _clean(value)).lower()
    for suffix in _PHYSICIAN_TITLE_SUFFIXES:
        if token.endswith(suffix):
            token = token[: -len(suffix)]
            break
    return token


def _physician_identity_is_masked(value: Any) -> bool:
    """脱敏姓名不能用于证明或否定术者与查房医师是同一人。"""

    return bool(_MASKED_PHYSICIAN_IDENTITY_PATTERN.search(_clean(value)))


def _surgery_event_surgeon_tokens(row: Mapping[str, Any]) -> frozenset[str]:
    """正式手术事件只接受术者专属字段，不能把文书作者当作术者。"""

    return frozenset(
        token
        for key in (
            "surgeon",
            "surgeon_sign",
            "main_surgery_sign",
        )
        if (token := _normalized_physician_token(row.get(key)))
    )


def _surgery_event_surgeon_names(row: Mapping[str, Any]) -> tuple[str, ...]:
    """保留术者专属字段中的客户可读姓名，不展示标准化匹配 token。"""

    names: list[str] = []
    for key in ("surgeon", "surgeon_sign", "main_surgery_sign"):
        name = _clean(row.get(key))
        if name and name not in names:
            names.append(name)
    return tuple(names)


def _course_record_physician_tokens(row: Mapping[str, Any]) -> frozenset[str]:
    """从受控作者字段或明确正文签名读取医师；提交人不替代签名。"""

    return frozenset(
        token
        for value in (
            row.get("author_name"),
            row.get("author_signature"),
            row.get("doctor_signature"),
            *course_physician_signatures(row),
        )
        if (token := _normalized_physician_token(value))
    )


def _title_round_physician_tokens(
    row: Mapping[str, Any],
    *,
    candidate_tokens: frozenset[str],
) -> frozenset[str]:
    """仅确认查房标题中、查房标记前明确列出的当前术者。"""

    title = _clean(row.get("document_title"))
    marker = _TITLE_ROUND_MARKER_PATTERN.search(title)
    if marker is None:
        return frozenset()
    title_header = title[: marker.start()]
    # 标题中的角色说明（如“手术由…完成”）不构成查房医师名单；
    # 不从正文、科室或查房标记后的附注反向推断术者。
    if _TITLE_ROUND_ROLE_DESCRIPTION_PATTERN.search(title_header):
        return frozenset()
    # 0910 源库的上级医师病程标题会将当前术者写成“姓名+主刀医师”，
    # “主刀”是角色而非姓名的一部分。只在标题开头、联合查房或明确标点边界后
    # 接受完整候选姓名，避免把较长姓名的尾部误认作当前术者。
    explicit_primary_surgeons = {
        candidate
        for candidate in candidate_tokens
        if re.search(
            rf"(?:^|联合|[，,、；;（）()]){re.escape(candidate)}主刀医师",
            title_header,
            flags=re.IGNORECASE,
        )
    }
    # 按职称分段提取完整姓名，不能用术者姓名去匹配另一姓名的后缀。
    identities = set()
    for match in re.finditer(
        r"([^，,、；;：:（）()]+?)(?:副主任医师|主任医师|主治医师|住院医师|医师)",
        title_header,
    ):
        identity = match.group(1).strip()
        # 仅剥离有明确边界的联合查房/科室前缀；其余整段保留，不能猜姓名。
        # “联合”后紧跟的“××科/××中心”是会诊科室（C25“联合胸外科某某副主任医师”），
        # 不在固定名单内也剥离；无“联合”边界时不拆（“王科李明”不能拆出“李明”）。
        identity = re.sub(r"^联合[\u4e00-\u9fff]{1,8}?(?:科|中心)(?=[\u4e00-\u9fff]{2,4}$)", "", identity)
        identity = re.sub(r"^联合", "", identity)
        identity = re.sub(
            r"^(?:联合)?(?:神经疾病中心|神经外科|神经内科|心胸外科|"
            r"普通外科|普外科|骨科|眼科|耳鼻喉科|妇产科|儿科|泌尿外科)",
            "",
            identity,
        )
        identities.add(_normalized_physician_token(identity))
    return frozenset(
        identities.intersection(candidate_tokens) | explicit_primary_surgeons
    )


def _actual_surgery_begin_time(
    *, source_key: str, row: Mapping[str, Any]
) -> datetime | None:
    """术前查房时限只读取实际开始字段；不得回退到申请或文书时间。"""

    for field in ("surgery_begin_time", "surgery_begin_datetime"):
        value = row.get(field)
        if source_key == "surgery_record":
            if (parsed := parse_strict_performed_time(value)) is not None:
                return parsed
        elif source_key == "mr_surgery" and isinstance(value, datetime) and value.tzinfo is None:
            return value
    return None


def _actual_surgery_end_time(
    *, source_key: str, row: Mapping[str, Any]
) -> datetime | None:
    """术后规则只能读取实际结束字段；不得回退到申请或文书时间。"""

    for field in ("surgery_end_time", "surgery_end_datetime"):
        value = row.get(field)
        if source_key == "surgery_record":
            if (parsed := parse_strict_performed_time(value)) is not None:
                return parsed
        elif source_key == "mr_surgery" and isinstance(value, datetime) and value.tzinfo is None:
            return value
    return None


def _postoperative_surgery_events(
    *,
    mr_surgery_rows: Sequence[Mapping[str, Any]],
    surgery_record_rows: Sequence[Mapping[str, Any]],
) -> tuple[_PostoperativeSurgeryEvent, ...]:
    """正式手术记录优先；仅在正式记录缺失时兼容既有 mr_surgery 触发。"""

    _qualified_mr_rows, qualified_record_rows = _qualified_surgery_rows(
        mr_surgery_rows, surgery_record_rows
    )
    source_key = "surgery_record" if qualified_record_rows else "mr_surgery"
    source_rows = qualified_record_rows if qualified_record_rows else _qualified_mr_rows
    events = []
    for index, row in enumerate(source_rows, start=1):
        end_time = _actual_surgery_end_time(source_key=source_key, row=row)
        begin_time = _actual_surgery_begin_time(source_key=source_key, row=row)
        surgeon_row = row
        if source_key == "surgery_record" and not _surgery_event_surgeon_names(row) and begin_time is not None:
            # 运行文书优先、病案首页回退：手术记录无术者时取首页同一手术日的术者。
            # 0910 真实源库首页手术时间只精确到日，且一台手术常拆为多行术式；仅当
            # 同日首页各行术者完全一致时采用，术者不一致或无同日记录保持缺失。
            same_day = [
                candidate
                for candidate in _qualified_mr_rows
                if (candidate_time := _actual_surgery_begin_time(source_key="mr_surgery", row=candidate)) is not None
                and candidate_time.date() == begin_time.date()
            ]
            surgeon_sets = {_surgery_event_surgeon_names(candidate) for candidate in same_day}
            if len(surgeon_sets) == 1 and next(iter(surgeon_sets)):
                surgeon_row = same_day[0]
        # 院方口径（2026-10-10）：0910 真实源库手术记录与病案首页均无结束时间，
        # 缺结束时间时以同一行实际开始时间推算术后起点，并在客户结论中注明。
        events.append(_PostoperativeSurgeryEvent(
            source_key=source_key,
            row=row,
            document_id=_clean(row.get("document_id") or row.get("id")) or f"{source_key}:{index}",
            surgery_name=_clean(
                row.get("surgery_name")
                or row.get("operation_name")
                or row.get("procedure_name")
            ),
            surgery_end_time=end_time if end_time is not None else begin_time,
            surgeon_names=_surgery_event_surgeon_names(surgeon_row),
            surgeon_tokens=_surgery_event_surgeon_tokens(surgeon_row),
            surgery_begin_time=begin_time,
            surgery_time_estimated=end_time is None and begin_time is not None,
            surgery_time_date_only=(
                source_key == "mr_surgery" and end_time is None and begin_time is not None
                and begin_time.time() == datetime.min.time()
            ),
        ))
    # 主控代定口径（2026-10-18，待客户复核），基线064/065/066：
    # 仅首页同日同开始时间术式行合台；无开始时间的行独立保留，不猜测关联。
    grouped: list[_PostoperativeSurgeryEvent] = []
    for event in events:
        matching_index = next((
            index for index, existing in enumerate(grouped)
            if event.source_key == existing.source_key == "mr_surgery"
            and event.surgery_begin_time is not None
            and existing.surgery_begin_time == event.surgery_begin_time
        ), None)
        if matching_index is None:
            grouped.append(replace(event, member_rows=(event.row,)))
            continue
        existing = grouped[matching_index]
        grouped[matching_index] = replace(
            existing,
            member_rows=(*existing.member_rows, event.row),
            surgeon_names=tuple(dict.fromkeys((*existing.surgeon_names, *event.surgeon_names))),
            surgeon_tokens=existing.surgeon_tokens | event.surgeon_tokens,
            # 同台结束字段冲突时不擅自择一；后续按权威时间不足关闭。
            surgery_end_time=(existing.surgery_end_time
                              if existing.surgery_end_time == event.surgery_end_time else None),
            surgery_time_estimated=existing.surgery_time_estimated or event.surgery_time_estimated,
        )
    return tuple(grouped)


def _postoperative_document_refs(
    *,
    snapshot: Luxian0609EvidenceSnapshot,
    materials: Luxian0609EvidenceMaterialStore,
    selected_rows: Sequence[Mapping[str, Any]],
) -> tuple[str, ...]:
    """把064/065/066实际消费的事件或病程唯一绑定为逐文书证据。"""

    allowed_sources = (
        "mr_surgery",
        "surgery_record",
        "daily_course_record",
        "senior_course_record",
        "postsurg_firstcourse_record",
    )
    refs: list[str] = []
    for selected_row in selected_rows:
        matches: list[str] = []
        for source_key in allowed_sources:
            try:
                document_rows = materials.document_rows(source_key, snapshot=snapshot)
            except (
                EvidenceMaterialUnavailable,
                EvidenceMaterialTruncated,
                TypeError,
                ValueError,
            ):
                continue
            matches.extend(
                reference
                for reference, material_row in document_rows
                if material_row == selected_row
            )
        if len(matches) != 1:
            return ()
        refs.append(matches[0])
    return tuple(dict.fromkeys(refs))


def _link_postoperative_first_course_records(
    *,
    surgery_events: Sequence[_PostoperativeSurgeryEvent],
    postoperative_rows: Sequence[Mapping[str, Any]],
) -> tuple[tuple[tuple[_PostoperativeSurgeryEvent, tuple[Mapping[str, Any], ...]], ...], str]:
    """按最近一台已结束的正式手术，将术后首次病程唯一归属到单个事件。

    仅使用实际手术结束时间和文书权威记录时间；结束时间相同或任一待核对文书
    缺时间时无法做安全归属，保持数据不足而不猜测。
    """

    if any(event.surgery_end_time is None for event in surgery_events) or (
        len(surgery_events) > 1
        and any(event.source_key == "mr_surgery" and event.surgery_begin_time is None
                for event in surgery_events)
    ):
        # 主控代定口径（2026-10-18，待客户复核），基线066：缺开始时间的首页行不能证明台次关联。
        return (), "authoritative_time_missing"
    ordered_events = tuple(sorted(surgery_events, key=lambda item: item.surgery_end_time))
    if len({item.surgery_end_time for item in ordered_events}) != len(ordered_events):
        return (), "association_failed"

    # 事件身份按本次有序事件序号保存，不能用展示用 document_id 作字典键：
    # 上游允许不同正式记录行复用同一个 document_id。
    linked_rows: list[list[Mapping[str, Any]]] = [[] for _event in ordered_events]
    for row in postoperative_rows:
        record_time = _row_time(row)
        if record_time is None:
            return (), "authoritative_time_missing"
        eligible_event_indexes = tuple(
            index
            for index, event in enumerate(ordered_events)
            if event.surgery_end_time is not None and event.surgery_end_time <= record_time
        )
        if not eligible_event_indexes:
            continue
        # 归属最近一台已经结束的手术，一份术后首次病程不会复用到更早手术。
        linked_rows[eligible_event_indexes[-1]].append(row)

    return (
        tuple(
            (event, tuple(rows))
            for event, rows in zip(ordered_events, linked_rows)
        ),
        "",
    )


def _event_display_base(event: _PostoperativeSurgeryEvent) -> dict[str, Any]:
    return {
        "document_id": event.document_id,
        "surgery_name": event.surgery_name,
        "surgeon_names": list(event.surgeon_names),
        "surgery_end_time": (
            event.surgery_end_time.isoformat(sep=" ")
            if event.surgery_end_time is not None
            else None
        ),
    }


def _postoperative_window_gate(
    *,
    surgery_events: Sequence[_PostoperativeSurgeryEvent],
    horizon_rows: Sequence[Mapping[str, Any]],
    horizon_error: str,
) -> tuple[str, str, Mapping[str, Any]] | None:
    """在逐台核对前确认术后三日观察窗口已经成熟。

    评价终点必须来自同一冻结 Evidence Session。只有日期时按保守口径，
    评价日期严格晚于每台手术结束日后的第三个自然日，避免在窗口当天提前
    把尚未发生的病程判为缺失。
    """

    def unavailable(issue: str) -> tuple[str, str, Mapping[str, Any]]:
        return (
            "data_gap",
            issue,
            {
                "verification_kind": "postoperative_three_day_window_unavailable",
                "issue": issue,
            },
        )

    if horizon_error:
        return unavailable(horizon_error)
    if len(horizon_rows) != 1:
        return unavailable("authoritative_time_missing")

    row = horizon_rows[0]
    horizon_time = _parse_datetime(row.get("horizon_datetime"))
    raw_date = _clean(row.get("horizon_date"))
    horizon_date: date | None = None
    if raw_date:
        try:
            horizon_date = date.fromisoformat(raw_date)
        except ValueError:
            return unavailable("authoritative_time_missing")
    if horizon_time is None and horizon_date is None:
        return unavailable("authoritative_time_missing")
    if horizon_time is not None and horizon_date is not None and horizon_time.date() != horizon_date:
        return unavailable("authoritative_time_conflict")

    deadlines = tuple(
        event.surgery_end_time.date() + timedelta(days=3)
        for event in surgery_events
        if event.surgery_end_time is not None
    )
    if len(deadlines) != len(surgery_events):
        return unavailable("authoritative_time_missing")
    if any(
        (horizon_time is not None and horizon_time < event.surgery_end_time)
        or (horizon_time is None and horizon_date < event.surgery_end_time.date())
        for event in surgery_events
        if event.surgery_end_time is not None
    ):
        return unavailable("authoritative_time_conflict")

    mature = (
        all(horizon_time.date() > deadline for deadline in deadlines)
        if horizon_time is not None
        else all(horizon_date > deadline for deadline in deadlines)
    )
    if mature:
        return None

    facts: dict[str, Any] = {
        "verification_kind": "postoperative_three_day_window_not_mature",
        "surgery_times": [
            event.surgery_end_time.isoformat(sep=" ")
            for event in surgery_events
            if event.surgery_end_time is not None
        ],
        "deadline_dates": [deadline.isoformat() for deadline in deadlines],
    }
    if horizon_time is not None:
        facts["evaluation_time"] = horizon_time.isoformat(sep=" ")
    else:
        facts["evaluation_date"] = horizon_date.isoformat()
    return "not_applicable", "evaluation_window_not_mature", facts


def _postoperative_senior_round_evaluation_horizon(
    *,
    surgery_events: Sequence[_PostoperativeSurgeryEvent],
    horizon_rows: Sequence[Mapping[str, Any]],
    horizon_error: str,
) -> tuple[datetime | None, date | None, str]:
    """返回065逐台72小时核对可用的冻结评价终点。"""

    if horizon_error:
        return None, None, horizon_error
    if len(horizon_rows) != 1:
        return None, None, "authoritative_time_missing"

    row = horizon_rows[0]
    horizon_time = _parse_datetime(row.get("horizon_datetime"))
    raw_date = _clean(row.get("horizon_date"))
    horizon_date: date | None = None
    if raw_date:
        try:
            horizon_date = date.fromisoformat(raw_date)
        except ValueError:
            return None, None, "authoritative_time_missing"
    if horizon_time is None and horizon_date is None:
        return None, None, "authoritative_time_missing"
    if horizon_time is not None and horizon_date is not None and horizon_time.date() != horizon_date:
        return None, None, "authoritative_time_conflict"

    for event in surgery_events:
        assert event.surgery_end_time is not None
        try:
            before_surgery = (
                horizon_time < event.surgery_end_time
                if horizon_time is not None
                else horizon_date < event.surgery_end_time.date()
            )
        except TypeError:
            return None, None, "authoritative_time_conflict"
        if before_surgery:
            return None, None, "authoritative_time_conflict"
    return horizon_time, horizon_date, ""


def _person_tokens(row: Mapping[str, Any]) -> set[str]:
    return {
        _clean(row.get(key)).lower()
        for key in (
            "surgeon",
            "surgeon_physician_code",
            "main_surgery_sign",
            "author_id",
            "author_name",
            "physician_sign",
            "submitter",
            "submitter_id",
        )
        if _clean(row.get(key))
    }


@dataclass(frozen=True)
class NativeExtendedDocumentExecutionResult:
    results: tuple[dict[str, Any], ...]
    planned_rule_ids: tuple[str, ...]
    decisions: tuple[RuleDecision, ...]
    customer_display_facts: tuple[tuple[str, Mapping[str, Any]], ...] = ()
    llm_call_count: int = 0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    api_time: float = 0.0


async def execute_luxian_0609_native_extended_document_rules(
    *,
    rule_ids: Sequence[str],
    evidence_snapshot: Luxian0609EvidenceSnapshot,
    evidence_materials: Luxian0609EvidenceMaterialStore,
    decision_rule_ids: Sequence[str] = (),
    llm_client: Any = None,
    **_: Any,
) -> NativeExtendedDocumentExecutionResult:
    course_content_extraction = None
    medication_extraction = None
    # 多份出院记录时对无法解析的自由文本逐份抽取，用量一并计入。
    other_medication_extractions: list[Any] = []
    discharge_approval_extraction = None
    course_body_extractions: list[CourseBodyExtraction] = []
    diagnosis_change_extraction = None
    antimicrobial_action_extraction = None
    antimicrobial_order_reason_extraction = None
    special_approval_extraction = None
    antimicrobial_effect_extraction = None
    diagnosis_scope_extraction = None
    diagnosis_equivalence_extraction = None
    invasive_extractions: list[Any] = []
    transfusion_performance_extraction = None
    transfusion_course_extraction = None
    postoperative_time_estimated_rules: set[str] = set()
    selected = tuple(
        rule_id
        for rule_id in EXTENDED_DOCUMENT_RULE_IDS
        if rule_id in {str(item or "").strip().upper() for item in rule_ids}
    )
    if not selected:
        return NativeExtendedDocumentExecutionResult((), (), ())
    if (
        not isinstance(evidence_snapshot, Luxian0609EvidenceSnapshot)
        or not isinstance(evidence_materials, Luxian0609EvidenceMaterialStore)
        or evidence_materials.snapshot_hash != evidence_snapshot.snapshot_hash
    ):
        raise ValueError("extended document rules require one evidence session")
    if set(decision_rule_ids) != set(selected):
        raise ValueError("extended document rules require typed decisions")

    registration_rows, registration_error = _source_rows(
        evidence_materials, "inpat_registration"
    )
    admission_rows, admission_error = _source_rows(
        evidence_materials, "admission_record"
    )
    death_rows, death_error = _source_rows(evidence_materials, "death_record")
    discussion_rows, discussion_error = _source_rows(
        evidence_materials, "death_discussion"
    )
    horizon_rows, horizon_error = (
        _source_rows(evidence_materials, "evaluation_context.horizon")
        if {
            "LX0609-09-02-01",
            "LX0609-06-04-01",
            "LX0609-05-01-03",
            "LX0609-08-01-01",
            "LX0609-08-01-03",
            "LX0609-04-05-01",
            "LX0609-04-05-02",
            "LX0609-08-02-01",
            "LX0609-08-02-02",
            "LX0609-10-02-01",
        }.intersection(selected)
        else ((), "")
    )
    if not horizon_rows and not horizon_error:
        horizon_observation = next(
            (
                observation
                for observation in evidence_snapshot.observations
                if observation.source_key == "evaluation_context.horizon"
            ),
            None,
        )
        if (
            horizon_observation is not None
            and horizon_observation.query_state.value == "empty"
        ):
            horizon_error = _clean(horizon_observation.reason_code)
    (
        critical_horizon_date,
        critical_horizon_datetime,
        critical_horizon_error,
    ) = (
        _critical_value_evaluation_horizon(horizon_rows, horizon_error)
        if "LX0609-06-04-01" in selected
        else (None, None, None)
    )
    (
        antimicrobial_horizon_date,
        antimicrobial_horizon_datetime,
        antimicrobial_horizon_error,
    ) = (
        _critical_value_evaluation_horizon(horizon_rows, horizon_error)
        if "LX0609-05-01-03" in selected
        else (None, None, None)
    )
    order_reason_horizon_datetime = (
        _critical_value_evaluation_horizon(horizon_rows, horizon_error)[1]
        if {"LX0609-05-01-02", "LX0609-05-01-05"}.intersection(selected)
        else None
    )
    (
        transfer_horizon_date,
        transfer_horizon_datetime,
        transfer_horizon_error,
    ) = (
        _critical_value_evaluation_horizon(horizon_rows, horizon_error)
        if "LX0609-10-02-01" in selected
        else (None, None, None)
    )
    discharge_rows, discharge_error = _source_rows(
        evidence_materials, "discharge_record"
    )
    daily_rows, daily_error = _source_rows(evidence_materials, "daily_course_record")
    senior_rows, senior_error = _source_rows(
        evidence_materials, "senior_course_record"
    )
    postop_first_rows, postop_first_error = _source_rows(
        evidence_materials, "postsurg_firstcourse_record"
    )
    mr_surgery_rows, mr_surgery_error = _source_rows(
        evidence_materials, "mr_surgery"
    )
    surgery_record_rows, surgery_record_error = _source_rows(
        evidence_materials, "surgery_record"
    )
    consultation_rows, consultation_error = _source_rows(
        evidence_materials, "consultation_record"
    )
    anesthesia_record_rows, _anesthesia_record_error = (
        _source_rows(evidence_materials, "anesthesia_record")
        if {"LX0609-05-01-02", "LX0609-05-01-05"}.intersection(selected)
        else ((), "")
    )
    handoff_rows, handoff_error = _source_rows(evidence_materials, "handoff_record")
    handover_rows, handover_error = _source_rows(evidence_materials, "handover_record")
    physician_change_rows, physician_change_error = _source_rows(
        evidence_materials, "physician_change_event"
    )
    transfer_in_rows, transfer_in_error = _source_rows(
        evidence_materials, "transfer_in_record"
    )
    transfer_out_rows, transfer_out_error = _source_rows(
        evidence_materials, "transfer_out_record"
    )
    nondrug_order_rows, nondrug_order_error = _source_rows(
        evidence_materials, "inpat_nondrug_order"
    )
    first_course_rows, first_course_error = (
        _source_rows(evidence_materials, "first_course_record")
        if set(selected).intersection({"LX0609-10-03-01", "LX0609-05-01-02", "LX0609-05-01-05"})
        else ((), "")
    )
    diagnosis_rows, diagnosis_error = _source_rows(evidence_materials, "diagnosis")
    mr_diagnosis_rows, mr_diagnosis_error = (
        _source_rows(evidence_materials, "mr_diagnosis")
        if "LX0609-08-01-03" in selected
        else ((), "")
    )
    mr_diagnosis_observed = _has_source_observation(
        evidence_snapshot,
        "mr_diagnosis",
    )
    # 074 的结构化变更声明只作为触发信号：该来源缺少诊断序号与诊断时间，
    # 绝不能挂成 diagnosis_rows。
    (
        admission_diagnosis_rows,
        admission_diagnosis_error,
    ) = (
        _source_rows(evidence_materials, "admission_record_diagnosis")
        if "LX0609-12-02-01" in selected
        else ((), "")
    )
    diffcase_rows, diffcase_error = _source_rows(
        evidence_materials, "diffcase_discussion_record"
    )
    crisis_rows, crisis_error = _source_rows(
        evidence_materials, "crisis_value_record"
    )
    lab_item_rows, lab_item_error = _source_rows(
        evidence_materials, "labtest_item_report"
    )
    lab_master_rows, lab_master_error = _source_rows(
        evidence_materials, "labtest_master"
    )
    drug_order_rows, drug_order_error = _source_rows(
        evidence_materials, "inpat_drug_order"
    )
    discharge_diagnosis_rows, discharge_diagnosis_error = _source_rows(
        evidence_materials, "discharge_record_diagnosis"
    )
    mr_bloodtrans_rows, mr_bloodtrans_error = _source_rows(
        evidence_materials, "mr_bloodtrans"
    )
    bloodtrans_record_rows, bloodtrans_record_error = _source_rows(
        evidence_materials, "bloodtrans_record"
    )
    death_state, death_time = _death_context(
        registration_rows=registration_rows,
        death_rows=death_rows,
        discharge_rows=discharge_rows,
    )
    if (
        death_state == "unknown"
        and registration_rows
        and not (registration_error or death_error or discharge_error)
    ):
        # 本次住院存在，死亡/出院三类权威来源均已完整读取且无死亡事实。
        death_state = "absent"
    decisions: list[RuleDecision] = []
    display: list[tuple[str, Mapping[str, Any]]] = []
    surgery_applicability = (
        resolve_surgery_applicability(
            snapshot=evidence_snapshot,
            materials=evidence_materials,
        )
        if {"LX0609-04-05-01", "LX0609-04-05-02", "LX0609-04-05-03"}.intersection(selected)
        else None
    )
    critical_value_outcomes = {
        item.rule_id: item
        for item in evaluate_critical_value_rules(
            rule_ids=tuple(rule_id for rule_id in CRITICAL_VALUE_RULE_IDS if rule_id in selected),
            inputs=CriticalValueInput(
                lab_item_error=lab_item_error or None,
                crisis_error=crisis_error or None,
                lab_report_count=len(lab_master_rows),
                lab_detail_count=len(lab_item_rows),
                items=tuple(
                    _critical_value_item_from_row(row) for row in lab_item_rows
                ),
                dispositions=tuple(
                    disposition
                    for row in crisis_rows
                    for disposition in (_critical_value_disposition_from_row(row),)
                    if disposition is not None
                ),
                evaluation_horizon_date=critical_horizon_date,
                evaluation_horizon_datetime=critical_horizon_datetime,
                evaluation_horizon_error=critical_horizon_error,
            ),
        )
    } if set(selected).intersection(CRITICAL_VALUE_RULE_IDS) else {}

    order_reason_cache: dict[str, Any] = {}

    async def special_approval_outcome(
    ) -> tuple[str, str, Mapping[str, Any] | None, tuple[Mapping[str, Any], ...]]:
        """058 医嘱驱动：特殊级药物首次使用 → 专家身份候选会诊/查房 → 模型确认同意使用。"""

        nonlocal special_approval_extraction
        resolution = derive_antimicrobial_use_events(
            _antimicrobial_orders(drug_order_rows),
            lambda row: _antimicrobial_names_in(row, _SPECIAL_ANTIMICROBIALS),
        )
        if resolution.time_missing_names:
            return "data_gap", "authoritative_time_missing", None, ()
        first_events: dict[str, Any] = {}
        for event in resolution.events:
            # 用户口径（2026-10-17）：同药后续续开或调整沿用首次使用时的专家支持。
            if event.kind != "stop" and (
                event.antimicrobial not in first_events or event.time < first_events[event.antimicrobial].time
            ):
                first_events[event.antimicrobial] = event
        events = tuple(first_events.values())
        if not events:
            return "not_applicable", "trigger_absent_complete", None, ()
        documents: list[WindowDocument] = []
        for source_key, rows in (("consultation_record", consultation_rows), ("senior_course_record", senior_rows)):
            for row in rows:
                text = _material_text(row)
                # 专家身份是结构事实：感染科副主任医师及以上署名或专家会诊/查房标记；
                # 是否“同意使用该药”交给模型判定，不再用肯定/否定正则。
                if text and (
                    _SPECIAL_ANTIMICROBIAL_INFECTION_EXPERT_PATTERN.search(text)
                    or any(marker in text for marker in _SPECIAL_ANTIMICROBIAL_EXPERT_SUPPORT_MARKERS)
                ):
                    documents.append(WindowDocument(
                        f"D{len(documents) + 1}", source_key, row, _lx0609_058_row_time(row), text,
                    ))
        # 文书带关联医嘱号时只能支持该医嘱所属药物，不能借给其他事件。
        per_event = {
            event.event_id: tuple(
                doc.doc_ref for doc in documents
                if not (linked := _linked_order_id(doc.row))
                or linked in {_clean(order.get("order_id")) for order in event.orders}
            )
            for event in events
        }
        special_approval_extraction = await extract_special_antimicrobial_approvals(
            events, documents, per_event, llm_client,
        )
        extraction = special_approval_extraction
        if extraction.state == "technical_error":
            return "technical_error", extraction.reason_code, None, ()
        if extraction.state != "ready":
            return "data_gap", extraction.reason_code, None, ()
        by_ref = {doc.doc_ref: doc for doc in documents}
        facts_by_event = {item.event_id: item for item in extraction.facts}
        unmatched: list[str] = []
        late = untimed = ambiguous = False
        support_times: list[datetime] = []
        evidence: list[Mapping[str, Any]] = []
        for event in events:
            evidence.extend(event.orders)
            facts = facts_by_event.get(event.event_id)
            approval = facts.quotes.get("approval") if facts is not None else None
            # 笼统同意“特殊级方案”无法归属到多个特殊级药物中的某一种：关联不明，不判缺失。
            ambiguous = ambiguous or (approval is None and facts is not None and facts.documented_use == "unknown")
            doc = by_ref.get(approval[0]) if approval else None
            if doc is not None and not _special_approval_by_authorized_expert(doc.text, approval[1]):
                # 用户口径（2026-10-17）：同意须出自感染科副主任医师及以上或感染专家会诊/查房；
                # 临床药师、主治医师意见及用药申请单文字不算（1019 C05）。
                doc = None
            if doc is not None:
                evidence.append(doc.row)
                if doc.time is None:
                    untimed = True
                    unmatched.append(event.antimicrobial)
                    continue
                support_times.append(doc.time)
                if doc.time <= event.time + _LX0609_058_SUPPORT_WINDOW:
                    continue
                late = True
            unmatched.append(event.antimicrobial)
        if not unmatched:
            final_state, reason_code = "compliant", "requirement_satisfied"
        elif ambiguous:
            final_state, reason_code = "data_gap", "association_failed"
        elif untimed:
            final_state, reason_code = "data_gap", "authoritative_time_missing"
        elif consultation_error or senior_error:
            final_state, reason_code = "data_gap", consultation_error or senior_error
        else:
            final_state = "non_compliant"
            reason_code = "requirement_violated" if late else "required_document_missing"
        first_time = min(event.time for event in events)
        return final_state, reason_code, {
            "verification_kind": "special_antimicrobial_expert_support_check",
            "special_antimicrobials": [event.antimicrobial for event in events],
            "expert_support_present": bool(support_times) or untimed,
            "first_antimicrobial_time": first_time.isoformat(sep=" "),
            "expert_support_time": min(support_times).isoformat(sep=" ") if support_times else None,
            "support_before_use": final_state == "compliant",
            "unmatched_special_antimicrobials": (
                [] if reason_code == "association_failed" else list(dict.fromkeys(unmatched))
            ),
            "association_ambiguous": final_state == "data_gap" and reason_code == "association_failed",
        }, tuple({id(row): row for row in evidence}.values())

    async def order_reason_outcome(
        rule_id: str,
    ) -> tuple[str, str, Mapping[str, Any] | None, tuple[Mapping[str, Any], ...]]:
        nonlocal antimicrobial_order_reason_extraction
        if "events" not in order_reason_cache:
            resolution = derive_antimicrobial_use_events(
                _antimicrobial_orders(drug_order_rows), _antimicrobial_names_in,
                discharge_time=_discharge_time(registration_rows, (), horizon_rows, horizon_error),
            )
            horizon = order_reason_horizon_datetime
            events = tuple(
                event for event in resolution.events
                if horizon is None or event.window_end <= horizon
            )
            documents, per_event, untimed = window_documents(
                events,
                (
                    ("first_course_record", first_course_rows),
                    ("transfer_in_record", transfer_in_rows),
                    ("daily_course_record", daily_rows),
                    ("senior_course_record", senior_rows),
                    ("consultation_record", consultation_rows),
                    # 只认预防用药引文；缺记录时间的不进窗口，以免把事件拖成无法定位。
                    ("surgery_record", tuple(row for row in surgery_record_rows if _row_time(row) is not None)),
                    ("anesthesia_record", tuple(row for row in anesthesia_record_rows if _row_time(row) is not None)),
                ),
                _material_text,
            )
            antimicrobial_order_reason_extraction = await extract_antimicrobial_reasons(
                events, documents, per_event, llm_client,
            )
            order_reason_cache.update(
                events=events, missing=resolution.time_missing_names,
                documents={doc.doc_ref: doc for doc in documents},
                per_event=per_event, untimed=untimed,
            )
        return _order_reason_rule_outcome(
            rule_id=rule_id,
            events=order_reason_cache["events"],
            time_missing_names=order_reason_cache["missing"],
            documents=order_reason_cache["documents"],
            per_event=order_reason_cache["per_event"],
            untimed=order_reason_cache["untimed"],
            extraction=antimicrobial_order_reason_extraction,
            lab_master_rows=lab_master_rows,
            lab_item_rows=lab_item_rows,
            pathogen_sources_complete=not (lab_master_error or lab_item_error),
        )

    for rule_id in selected:
        if rule_id == "LX0609-08-01-05":
            course_content_extraction = await evaluate_discharge_course_content(
                snapshot=evidence_snapshot, materials=evidence_materials, llm_client=llm_client,
            )
            outcome = course_content_extraction
            decisions.append(_decision(
                rule_id=rule_id, snapshot=evidence_snapshot,
                source_keys=("discharge_record",), final_state=outcome.state,
                reason_code=outcome.reason, document_refs=outcome.refs,
                exact_document_refs=bool(outcome.refs),
            ))
            display.append((rule_id, outcome.facts))
            continue
        if rule_id == "LX0609-05-03-01":
            # 059 仍处于 pending_definition。正式编排不会派发它；若低层
            # 兼容入口收到该规则，只能报告执行合同错误，不能交付临床缺陷。
            decisions.append(
                _decision(
                    rule_id=rule_id,
                    snapshot=evidence_snapshot,
                    source_keys=(),
                    final_state="technical_error",
                    reason_code="decision_contract_violation",
                )
            )
            continue

        if rule_id == "LX0609-03-02-01":
            source_error = (
                (registration_error and admission_error)
                or daily_error
                or diffcase_error
            )
            admission_time = next(
                (
                    _parse_datetime(row.get("admission_datetime") or row.get("admission_time"))
                    for row in (*registration_rows, *admission_rows)
                    if _parse_datetime(row.get("admission_datetime") or row.get("admission_time"))
                    is not None
                ),
                None,
            )
            strong_candidates = []
            local_candidates = []
            unknown_candidates = []
            scope_resolution = "ready"
            extraction_error = None
            if not source_error and admission_time is not None:
                # 权威时间已排除的早期病程不进入语义调用；缺时保留，不能静默排除。
                # 无权威时间的病程以最后修改时间为上限：上限早于第7天的必然是早期病程（用户口径 2026-10-20）。
                scope_rows = tuple(
                    row for row in daily_rows
                    if ((value := _row_time(row)) is not None and value >= admission_time + timedelta(days=7))
                    or (value is None and not (
                        (bound := row_time_upper_bound(row)) is not None
                        and bound < admission_time + timedelta(days=7)))
                )
                diagnosis_scope_extraction = await extract_diagnosis_scope(
                    scope_rows, llm_client, max_prompt_bytes=65536, max_completion_tokens=16384,
                )
                if diagnosis_scope_extraction.state != "ready":
                    extraction_error = (diagnosis_scope_extraction.state, diagnosis_scope_extraction.reason_code)
                    scope_resolution = (
                        "capacity_exceeded" if diagnosis_scope_extraction.reason_code == "candidate_scope_incomplete"
                        else "unavailable" if diagnosis_scope_extraction.state == "data_gap" else "invalid"
                    )
                else:
                    for document in diagnosis_scope_extraction.documents:
                        row = scope_rows[document.row_index]
                        # 2026-10-20按用户要求核对国家核心制度：某一诊断明确不能
                        # 抵消另一当前诊疗疑难。局部问题范围不明仍按既有合同交付
                        # 资料不足，不据主诊断明确豁免，也不强行认定已触发。
                        if document.coverage == "unknown":
                            unknown_candidates.append(row)
                        for assertion in document.assertions:
                            if assertion.temporal_scope in {"historical", "future_conditional"}:
                                continue
                            if "unknown" in (assertion.polarity, assertion.temporal_scope,
                                             assertion.diagnosis_state, assertion.scope):
                                unknown_candidates.append(row)
                                continue
                            # 否定“明确”与肯定“未明确”均表示当前未解决；未知不能当成不存在。
                            is_unresolved = (
                                assertion.polarity == "affirmed"
                                and assertion.diagnosis_state in {"unresolved", "undetermined"}
                            ) or (assertion.polarity == "negated" and assertion.diagnosis_state == "explicit")
                            if is_unresolved and assertion.temporal_scope == "current":
                                if assertion.scope in {"diagnosis", "treatment_plan"}:
                                    if row not in strong_candidates:
                                        strong_candidates.append(row)
                                elif assertion.scope == "local_problem":
                                    if row not in local_candidates:
                                        local_candidates.append(row)
                                else:
                                    unknown_candidates.append(row)
            strong_candidate_rows = tuple(strong_candidates)
            local_candidate_rows = tuple(local_candidates)
            unknown_scope_rows = tuple(row for row in unknown_candidates
                if _row_time(row) is None or (admission_time is not None and _row_time(row) >= admission_time + timedelta(days=7)))
            candidate_time_gap_rows = tuple(
                row for row in daily_rows
                if (row in strong_candidate_rows or row in local_candidate_rows)
                and _row_time(row) is None
            )
            strong_uncertain_rows = tuple(
                row for row in strong_candidate_rows
                if admission_time is not None
                and (row_time := _row_time(row)) is not None
                and row_time >= admission_time + timedelta(days=7)
            )
            local_uncertain_rows = tuple(
                row for row in local_candidate_rows
                if admission_time is not None and (row_time := _row_time(row)) is not None
                and row_time >= admission_time + timedelta(days=7)
            )
            uncertain_rows = strong_uncertain_rows or local_uncertain_rows
            if source_error:
                final_state, reason_code = "data_gap", source_error
            elif extraction_error is not None:
                final_state, reason_code = extraction_error
            elif admission_time is None:
                final_state, reason_code = "data_gap", "authoritative_time_missing"
            elif not strong_uncertain_rows and candidate_time_gap_rows:
                # 缺时只表示候选无法定位；不能据此确认七天触发或完整未触发。
                final_state, reason_code = "data_gap", "authoritative_time_missing"
            elif not strong_uncertain_rows and unknown_scope_rows:
                # 院方口径（2026-10-10）：诊断范围无法确认按资料不足交付，不交付 uncertain。
                final_state, reason_code = "data_gap", "diagnosis_scope_uncertain"
                scope_resolution = "unknown"
            elif not uncertain_rows:
                final_state, reason_code = "not_applicable", "trigger_absent_complete"
            elif not strong_uncertain_rows:
                final_state, reason_code = "data_gap", "diagnosis_scope_uncertain"
            elif diffcase_rows and not any(
                isinstance(row.get("record_content"), str) and row["record_content"].strip()
                for row in diffcase_rows
            ):
                # 已定位资料行不能代替可读取正文；不借标题或非字符串补造正文。
                final_state, reason_code = "data_gap", "required_field_missing"
            elif diffcase_rows:
                final_state, reason_code = "compliant", "requirement_satisfied"
            else:
                final_state, reason_code = "non_compliant", "required_document_missing"
            scope_uncertain = reason_code == "diagnosis_scope_uncertain"
            body_gap_only = reason_code == "required_field_missing" and final_state == "data_gap" and extraction_error is None
            time_gap_only = bool(candidate_time_gap_rows) and reason_code == "authoritative_time_missing"
            selected_time_gap_refs: list[str] = []
            if admission_time is not None and not source_error:
                facts = {
                    "verification_kind": (
                        "uncertain_diagnosis_discussion_body_gap" if body_gap_only
                        else "uncertain_diagnosis_course_time_gap" if time_gap_only
                        else "uncertain_diagnosis_scope_unverified" if scope_uncertain
                        else "uncertain_diagnosis_discussion_check"
                    ),
                    "admission_time": admission_time.isoformat(sep=" "),
                    "uncertain_record_times": [
                        value.isoformat(sep=" ")
                        for row in (local_uncertain_rows if scope_uncertain else strong_uncertain_rows)
                        if (value := _row_time(row)) is not None
                    ],
                    "discussion_count": len(diffcase_rows),
                }
                if scope_resolution != "ready":
                    facts["diagnosis_scope_resolution"] = scope_resolution
                if body_gap_only:
                    facts["discussion_body_gap_count"] = len(diffcase_rows)
                if candidate_time_gap_rows:
                    facts["candidate_course_time_gap_count"] = len(candidate_time_gap_rows)
                if candidate_time_gap_rows or body_gap_only:
                    # 只给本次实际使用的病程和讨论附加精确文书引用。
                    # 无ID或重复ID仍保留既有来源快照锚，不能制造定位坐标。
                    consumed_courses = (*strong_uncertain_rows, *candidate_time_gap_rows)
                    for source_key, consumed_rows in (
                        ("daily_course_record", consumed_courses),
                        ("diffcase_discussion_record", diffcase_rows),
                    ):
                        document_rows = evidence_materials.document_rows(source_key, snapshot=evidence_snapshot)
                        for reference, row in document_rows:
                            document_id = _clean(row.get("document_id") or row.get("id"))
                            if (document_id and row in consumed_rows and sum(
                                _clean(other.get("document_id") or other.get("id")) == document_id
                                for _, other in document_rows
                            ) == 1):
                                selected_time_gap_refs.append(reference)
                display.append((rule_id, facts))
            decisions.append(_decision(
                rule_id=rule_id, snapshot=evidence_snapshot,
                source_keys=(
                    "inpat_registration",
                    "admission_record",
                    "daily_course_record",
                    "diffcase_discussion_record",
                ),
                final_state=final_state, reason_code=reason_code,
                document_refs=selected_time_gap_refs,
            ))
            continue

        if rule_id in {"LX0609-06-04-01", "LX0609-06-04-02"}:
            outcome = critical_value_outcomes[rule_id]
            if outcome.display_facts is not None:
                display.append((rule_id, outcome.display_facts))
            document_refs = _critical_value_document_refs(
                snapshot=evidence_snapshot,
                materials=evidence_materials,
                outcome=outcome,
            )
            decisions.append(_decision(
                rule_id=rule_id, snapshot=evidence_snapshot,
                # 完整资料已读取但确无任何检验明细时，不适用结论仍需一个
                # snapshot 级负向证据；它不会被投影为客户文书。
                source_keys=(
                    ("labtest_item_report",)
                    if not document_refs
                    and outcome.final_state == "not_applicable"
                    else ()
                ),
                document_refs=document_refs,
                final_state=outcome.final_state, reason_code=outcome.reason_code,
            ))
            continue

        if rule_id in {
            "LX0609-05-01-02", "LX0609-05-01-03", "LX0609-05-01-04",
            "LX0609-05-01-05", "LX0609-05-01-06", "LX0609-05-03-01",
        }:
            antimicrobial_orders = _antimicrobial_orders(drug_order_rows)
            excluded_antimicrobial_evidence: tuple[Mapping[str, Any], ...] = ()
            if rule_id in {"LX0609-05-01-03", "LX0609-05-01-05", "LX0609-05-01-06"}:
                antimicrobial_orders, excluded_antimicrobial_evidence = (
                    _exclude_unperformed_antimicrobial_orders(
                        antimicrobial_orders,
                        (*senior_rows, *consultation_rows)
                        if rule_id == "LX0609-05-01-06"
                        else (*daily_rows, *senior_rows, *consultation_rows),
                    )
                )
            rule_antimicrobial_orders = (
                _055_treatment_orders(antimicrobial_orders)
                if rule_id == "LX0609-05-01-03"
                else antimicrobial_orders
            )
            course_rows = (
                # 转入记录是转科后首份病程性文书，其诊疗计划记载抗菌药使用及理由（1019 C10）。
                (*first_course_rows, *transfer_in_rows, *daily_rows, *senior_rows)
                if rule_id in {"LX0609-05-01-02", "LX0609-05-01-05"}
                else (*daily_rows, *senior_rows)
            )
            selected_antimicrobial_evidence_rows: list[Mapping[str, Any]] = list(
                excluded_antimicrobial_evidence
            )
            source_error = drug_order_error or (
                "" if rule_id == "LX0609-05-01-06" else daily_error or senior_error
            )
            if rule_id in {"LX0609-05-01-02", "LX0609-05-01-05"}:
                source_error = source_error or first_course_error or transfer_in_error
            if source_error:
                final_state, reason_code = "data_gap", source_error
            elif rule_id == "LX0609-05-01-02":
                outcome = await order_reason_outcome(rule_id)
                final_state, reason_code = outcome[0], outcome[1]
                if outcome[2] is not None:
                    display.append((rule_id, outcome[2]))
                selected_antimicrobial_evidence_rows.extend(outcome[3])
            elif not rule_antimicrobial_orders:
                final_state, reason_code = "not_applicable", "trigger_absent_complete"
            elif rule_id == "LX0609-05-01-03":
                # 客户确认口径（2026-10-20），基线055：按客户允许的计划开始/开医嘱时间起算，
                # 续开不另建48–72小时窗。用户口径（2026-10-21）改为医嘱驱动：疗程与054/057
                # 共用同一推导——撤销、皮试医嘱不算；同药停用超过24小时后再开为新疗程，另建窗口；
                # 疗程不满48小时即停用的不要求48–72小时评价。
                course_resolution = derive_antimicrobial_use_events(
                    rule_antimicrobial_orders, _antimicrobial_names_in,
                )
                order_events = tuple(
                    (_AntimicrobialOrderEvent(event.orders, (event.antimicrobial,)), event.antimicrobial, event.time)
                    for event in course_resolution.events
                    if event.kind != "stop"
                    and (event.course_end is None or event.course_end >= event.time + timedelta(hours=48))
                ) + tuple(
                    (_AntimicrobialOrderEvent(
                        tuple(order for order in rule_antimicrobial_orders if name in _antimicrobial_names_in(order)),
                        (name,),
                    ), name, None)
                    for name in course_resolution.time_missing_names
                )
                # 即使评价窗尚未成熟，开始医嘱仍是这项否定结论实际消费的
                # 业务事实；horizon 仅决定窗口状态，绝不成为客户证据。
                selected_antimicrobial_evidence_rows.extend(
                    row
                    for event, _name, start in order_events
                    if start is not None
                    for row in event.orders
                )
                event_windows: list[dict[str, Any]] = []
                mature_events: list[tuple[_AntimicrobialOrderEvent, str, datetime]] = []
                immature_states: list[str] = []
                if not order_events:
                    final_state, reason_code = "not_applicable", "trigger_absent_complete"
                elif any(start is None for _, _, start in order_events):
                    final_state, reason_code = "data_gap", "authoritative_time_missing"
                elif antimicrobial_horizon_error:
                    final_state, reason_code = "data_gap", antimicrobial_horizon_error
                else:
                    for order, name, start in order_events:
                        assert start is not None
                        state, _, window_facts = _antimicrobial_effect_window_state(
                            start_time=start,
                            horizon_date=antimicrobial_horizon_date,
                            horizon_time=antimicrobial_horizon_datetime,
                        )
                        event_windows.append({
                            "antimicrobial": name,
                            "event_state": state,
                            **window_facts,
                        })
                        if state == "conflict":
                            final_state, reason_code = (
                                "data_gap", "authoritative_time_conflict"
                            )
                            break
                        if state == "missing":
                            final_state, reason_code = (
                                "data_gap", "authoritative_time_missing"
                            )
                            break
                        if state == "mature":
                            mature_events.append((order, name, start))
                        else:
                            immature_states.append(state)
                    else:
                        final_state = reason_code = ""
                # 先由程序确定窗口，再完整抽取各目标药的评价；不以结果词筛正文。
                effect_rows_by_name: dict[str, list[Mapping[str, Any]]] = {}
                safety_rows_by_name: dict[str, list[Mapping[str, Any]]] = {}
                unknown_effect_rows_by_name: dict[str, list[Mapping[str, Any]]] = {}
                unknown_safety_rows_by_name: dict[str, list[Mapping[str, Any]]] = {}
                unassigned_effect_rows: list[Mapping[str, Any]] = []
                unassigned_safety_rows: list[Mapping[str, Any]] = []
                evaluation_resolution = "ready"
                if not final_state and mature_events:
                    targets = tuple(dict.fromkeys(name for _, name, _ in mature_events))
                    # 用户口径（2026-10-20）：空白病程的时间（无权威时间时取最后修改时间作上限）
                    # 早于全部评价窗或已在窗外时，不可能是窗内评价，不再使整例资料不足。
                    earliest_window = min(start + timedelta(hours=48) for _, _, start in mature_events)
                    # 医嘱驱动：只把落在某个48–72小时评价窗内的病程交给模型；无权威时间的病程
                    # 以最后修改时间为上限，上限早于最早评价窗的必然不在窗内。
                    effect_course_rows = tuple(
                        row for row in course_rows
                        if (
                            (value := _row_time(row)) is not None
                            and any(48 <= (value - start).total_seconds() / 3600 <= 72
                                    for _, _, start in mature_events)
                        )
                        or (
                            value is None
                            and not ((bound := row_time_upper_bound(row)) is not None and bound < earliest_window)
                        )
                    )
                    antimicrobial_effect_extraction = await extract_antimicrobial_effects(
                        effect_course_rows, targets, llm_client,
                        max_prompt_bytes=65536, max_completion_tokens=16384,
                    )
                    if antimicrobial_effect_extraction.reason_code == "source_capacity_exceeded":
                        # 全住院笛卡尔配对超限时，按权威时间排除不可能满足窗口的配对。
                        # 保留所有无时间病程及窗口内全文，不按药名或评价词筛选、截断正文。
                        candidate_pairs = tuple(
                            (row_index, target_index)
                            for row_index, row in enumerate(effect_course_rows)
                            for target_index, target in enumerate(targets)
                            if (value := _row_time(row)) is None
                            or any(
                                name == target and 48 <= (value - start).total_seconds() / 3600 <= 72
                                for _order, name, start in mature_events
                            )
                        )
                        antimicrobial_effect_extraction = await extract_antimicrobial_effect_pairs(
                            effect_course_rows, targets, candidate_pairs, llm_client,
                            max_prompt_bytes=65536, max_completion_tokens=16384,
                        )
                    extraction = antimicrobial_effect_extraction
                    if extraction.state != "ready":
                        final_state = extraction.state
                        reason_code = (
                            "candidate_scope_incomplete"
                            if extraction.reason_code == "source_capacity_exceeded"
                            else extraction.reason_code
                        )
                        evaluation_resolution = (
                            "capacity_exceeded" if reason_code == "candidate_scope_incomplete"
                            else "unavailable" if final_state == "data_gap" else "invalid"
                        )
                    else:
                        for assertion in extraction.assertions:
                            row = effect_course_rows[assertion.row_index]
                            name = targets[assertion.target_index]
                            for state, rows_by_name, unknown_rows_by_name, unassigned_rows in (
                                (
                                    assertion.effect_state,
                                    effect_rows_by_name,
                                    unknown_effect_rows_by_name,
                                    unassigned_effect_rows,
                                ),
                                (
                                    assertion.safety_state,
                                    safety_rows_by_name,
                                    unknown_safety_rows_by_name,
                                    unassigned_safety_rows,
                                ),
                            ):
                                if state == "present":
                                    rows_by_name.setdefault(name, []).append(row)
                                elif state == "regimen":
                                    # 未点药名的整体方案评价：只用一种药（可有多个疗程）时按评价窗归属；
                                    # 多药同用时仍无法确定评价的是哪种药。
                                    row_time = _row_time(row)
                                    window_names = {
                                        event_name for _, event_name, start in mature_events
                                        if row_time is not None
                                        and 48 <= (row_time - start).total_seconds() / 3600 <= 72
                                    }
                                    single_drug = {event_name for _, event_name, _ in order_events} == {name}
                                    if len(order_events) == 1 or (single_drug and window_names == {name}):
                                        rows_by_name.setdefault(name, []).append(row)
                                    elif row not in unassigned_rows:
                                        unassigned_rows.append(row)
                                elif state == "unknown":
                                    unknown_rows_by_name.setdefault(name, []).append(row)
                # 同药多个疗程时按评价窗归属：只有同一份病程同时落入两个同药疗程的
                # 评价窗（或缺时无法定位）才无法归属。
                ambiguous_evaluation = any(
                    not _linked_order_id(row)
                    and sum(
                        name == event_name and (
                            (value := _row_time(row)) is None
                            or 48 <= (value - start).total_seconds() / 3600 <= 72
                        )
                        for _, event_name, start in mature_events
                    ) > 1
                    for rows_by_name in (effect_rows_by_name, safety_rows_by_name)
                    for name, rows in rows_by_name.items() for row in rows
                )
                effect_intervals: list[float] = []
                safety_intervals: list[float] = []
                unmatched_effect_names: list[str] = []
                unmatched_safety_names: list[str] = []
                unmatched_names: list[str] = []
                has_untimed_match = False
                has_unresolved_unknown = False
                has_unassigned_regimen = False
                if final_state in {"data_gap", "technical_error", "not_applicable"}:
                    pass
                elif ambiguous_evaluation:
                    final_state, reason_code = "data_gap", "association_failed"
                else:
                    for order, name, start in mature_events:
                        order_ids = order.order_ids
                        for (
                            rows_by_name,
                            unknown_rows_by_name,
                            unassigned_rows,
                            dimension_intervals,
                            unmatched_names,
                        ) in (
                            (
                                effect_rows_by_name,
                                unknown_effect_rows_by_name,
                                unassigned_effect_rows,
                                effect_intervals,
                                unmatched_effect_names,
                            ),
                            (
                                safety_rows_by_name,
                                unknown_safety_rows_by_name,
                                unassigned_safety_rows,
                                safety_intervals,
                                unmatched_safety_names,
                            ),
                        ):
                            matching_rows = tuple(
                                row for row in rows_by_name.get(name, ())
                                if not _linked_order_id(row)
                                or _linked_order_id(row) in order_ids
                            )
                            event_intervals = [
                                (value - start).total_seconds() / 3600
                                for row in matching_rows
                                if (value := _row_time(row)) is not None and value >= start
                            ]
                            selected_antimicrobial_evidence_rows.extend(
                                row
                                for row in matching_rows
                                if (value := _row_time(row)) is not None
                                and 48 <= (value - start).total_seconds() / 3600 <= 72
                            )
                            dimension_intervals.extend(event_intervals)
                            if not any(48 <= value <= 72 for value in event_intervals):
                                matching_unknown_rows = tuple(
                                    row for row in unknown_rows_by_name.get(name, ())
                                    if not _linked_order_id(row)
                                    or _linked_order_id(row) in order_ids
                                )
                                unknown_is_relevant = any(
                                    (value := _row_time(row)) is None
                                    or 48 <= (value - start).total_seconds() / 3600 <= 72
                                    for row in matching_unknown_rows
                                )
                                unassigned_is_relevant = any(
                                    (value := _row_time(row)) is None
                                    or 48 <= (value - start).total_seconds() / 3600 <= 72
                                    for row in unassigned_rows
                                )
                                if unknown_is_relevant:
                                    has_unresolved_unknown = True
                                elif unassigned_is_relevant:
                                    has_unassigned_regimen = True
                                else:
                                    unmatched_names.append(name)
                                    has_untimed_match = has_untimed_match or any(
                                        _row_time(row) is None for row in matching_rows
                                    )
                    unmatched_names = list(dict.fromkeys(
                        (*unmatched_effect_names, *unmatched_safety_names)
                    ))
                    if has_unresolved_unknown:
                        final_state, reason_code = (
                            "data_gap", "semantic_extraction_unresolved"
                        )
                        evaluation_resolution = "unknown"
                    elif has_unassigned_regimen:
                        final_state, reason_code = "data_gap", "association_failed"
                        ambiguous_evaluation = True
                    elif not unmatched_names:
                        if immature_states:
                            final_state = "not_applicable"
                            reason_code = (
                                "evaluation_window_not_mature"
                                if "not_mature" in immature_states
                                else "evaluation_window_not_started"
                            )
                        else:
                            final_state, reason_code = (
                                "compliant", "requirement_within_threshold"
                            )
                    elif has_untimed_match:
                        final_state, reason_code = "data_gap", "authoritative_time_missing"
                    else:
                        final_state, reason_code = "non_compliant", "threshold_exceeded"
                if final_state == "data_gap" and reason_code in {
                    "authoritative_time_missing", "authoritative_time_conflict"
                }:
                    evaluation_resolution = "time_unresolved"
                display_facts: dict[str, Any] = {
                    "verification_kind": "antimicrobial_effect_evaluation_check",
                    "evaluation_resolution": evaluation_resolution,
                    "antimicrobials": list(dict.fromkeys(
                        name for _, name, _ in order_events
                    )),
                    "window_hours": [48, 72],
                    "evaluation_intervals": [round(value, 2) for value in effect_intervals],
                    "effect_evaluation_intervals": [round(value, 2) for value in effect_intervals],
                    "safety_evaluation_intervals": [round(value, 2) for value in safety_intervals],
                    "unmatched_antimicrobials": unmatched_names,
                    "unmatched_effect_antimicrobials": list(dict.fromkeys(unmatched_effect_names)),
                    "unmatched_safety_antimicrobials": list(dict.fromkeys(unmatched_safety_names)),
                    "association_ambiguous": ambiguous_evaluation,
                    "event_windows": event_windows,
                }
                if final_state == "not_applicable" and reason_code == "trigger_absent_complete":
                    pass
                else:
                    if final_state == "not_applicable":
                        display_facts["window_state"] = reason_code
                    display.append((rule_id, display_facts))
            elif rule_id == "LX0609-05-01-04":
                # 院方口径（2026-10-11）：重点抗菌药物按院方七类清单识别；“两种及以上”
                # 按药品种数计，同一药多条医嘱只算一种。
                # 用户口径（2026-10-21）医嘱驱动：皮试、撤销医嘱不算使用；使用起点取计划开始时间，
                # 缺失才回退开医嘱时间，与054/055/057/058一致。
                special_orders = tuple(
                    row for row in drug_order_rows
                    if key_antimicrobials_in_order(row) and not is_excluded_antimicrobial_order(row)
                    and not is_local_route_drug_order(row)
                )
                key_drugs = {
                    name for row in special_orders for name in key_antimicrobials_in_order(row)
                }
                if len(key_drugs) < 2:
                    final_state, reason_code = "not_applicable", "trigger_absent_complete"
                elif lab_master_error or lab_item_error:
                    final_state, reason_code = "data_gap", lab_master_error or lab_item_error
                else:
                    special_order_times = tuple(order_start_time(row) for row in special_orders)
                    first_order = (
                        None if any(value is None for value in special_order_times)
                        else min(special_order_times, default=None)
                    )
                    # 项目身份常在明细、申请/采样时间在主表；只用同一 test_id
                    # 关联，不能把其他检验的时间借给病原学项目。
                    pathogen_test_ids = {
                        _clean(row.get("test_id"))
                        for row in lab_item_rows
                        if _clean(row.get("test_id"))
                        and _is_pathogen_lab(row)
                    }
                    specimen_times = tuple(
                        value
                        for row in lab_master_rows
                        if (
                            _is_pathogen_lab(row)
                            or _clean(row.get("test_id")) in pathogen_test_ids
                        )
                        and (value := _parse_datetime(row.get("request_datetime") or row.get("sample_datetime")))
                        is not None
                    )
                    if first_order is None:
                        final_state, reason_code = "data_gap", "authoritative_time_missing"
                    else:
                        complete = any(value <= first_order for value in specimen_times)
                        final_state = "compliant" if complete else "non_compliant"
                        reason_code = "requirement_satisfied" if complete else "requirement_violated"
                        display.append((rule_id, {
                            "verification_kind": "key_antimicrobial_specimen_check",
                            "key_drug_count": len(key_drugs),
                            "specimen_before_first_order": complete,
                        }))
            elif rule_id == "LX0609-05-01-05":
                outcome = await order_reason_outcome(rule_id)
                final_state, reason_code = outcome[0], outcome[1]
                if outcome[2] is not None:
                    display.append((rule_id, outcome[2]))
                selected_antimicrobial_evidence_rows.extend(outcome[3])
            elif rule_id == "LX0609-05-01-06":
                outcome = await special_approval_outcome()
                final_state, reason_code = outcome[0], outcome[1]
                if outcome[2] is not None:
                    display.append((rule_id, outcome[2]))
                selected_antimicrobial_evidence_rows.extend(outcome[3])
            else:
                used_names = _antimicrobial_names_in_rows(antimicrobial_orders)
                complete = bool(used_names) and all(
                    _has_any_text(course_rows, (name,)) for name in used_names
                )
                final_state = "compliant" if complete else "non_compliant"
                reason_code = "requirement_satisfied" if complete else "requirement_violated"
                display.append((rule_id, {
                    (
                        "verification_kind"
                        if complete
                        else "failure_kind"
                    ): (
                        "antimicrobial_course_documentation_complete"
                        if complete
                        else "antimicrobial_course_documentation_missing"
                    ),
                    "antimicrobials": list(used_names),
                    "course_documented": complete,
                }))
            antimicrobial_document_refs = _antimicrobial_document_refs(
                snapshot=evidence_snapshot,
                materials=evidence_materials,
                selected_rows=selected_antimicrobial_evidence_rows,
            )
            has_selected_antimicrobial_evidence = bool(
                selected_antimicrobial_evidence_rows
            )
            decisions.append(_decision(
                rule_id=rule_id,
                snapshot=evidence_snapshot,
                # 没有实际消费文书的“触发未发生”结论只保留单一源级锚点；
                # 一旦消费了行，则必须使用精确文书坐标，空/非法坐标由 Binding
                # 明确作为技术失败处理，不能伪装为原业务状态。
                source_keys=(
                    () if has_selected_antimicrobial_evidence
                    else ("inpat_drug_order",)
                ),
                document_refs=antimicrobial_document_refs,
                exact_document_refs=has_selected_antimicrobial_evidence,
                final_state=final_state,
                reason_code=reason_code,
            ))
            continue

        if rule_id == "LX0609-08-01-03":
            # mr观察存在时仍是唯一权威；旧快照才兼容diagnosis，不合并两源。
            authority_source_key = "mr_diagnosis" if mr_diagnosis_observed else "diagnosis"
            authority_error = mr_diagnosis_error if mr_diagnosis_observed else diagnosis_error
            raw_authority_rows = mr_diagnosis_rows if mr_diagnosis_observed else diagnosis_rows
            authority_types = {
                _clean(row.get("diagnosis_type")) for row in raw_authority_rows
                if _clean(row.get("diagnosis_type")) in _DISCHARGE_DIAGNOSIS_TYPES
            }
            death_registration_rows = tuple(
                row for row in registration_rows if not registration_error and (
                    any(marker in _registration_status((row,)) for marker in _DEATH_MARKERS)
                    or _parse_datetime(row.get("death_datetime") or row.get("death_time")) is not None
                )
            )
            alive_registration_rows = tuple(
                row for row in registration_rows if not registration_error and (
                    _registration_status((row,)) in {"在院", "住院", "存活"}
                    or (not any(marker in _registration_status((row,)) for marker in _DEATH_MARKERS)
                        and any(marker in _registration_status((row,)) for marker in _ALIVE_DISCHARGE_MARKERS))
                )
            )
            explicit_death = bool(death_rows or death_registration_rows)
            frozen_running = (
                not horizon_error and len(horizon_rows) == 1
                and horizon_rows[0].get("record_scene") == "running"
            )
            # 可信mr精确死亡类型本身证明范围；记录完成时间占位不反证死亡。
            typed_death = mr_diagnosis_observed and authority_types == {"死亡诊断"}
            scope_conflict = bool(alive_registration_rows) and (
                explicit_death or "死亡诊断" in authority_types
            )
            diagnosis_scope = None
            consumed = []
            scope_sources = ("inpat_registration", "death_record", authority_source_key)
            if scope_conflict:
                scope_gap = "scope_conflict"
                consumed.extend(("inpat_registration", row) for row in alive_registration_rows)
                consumed.extend((authority_source_key, row) for row in raw_authority_rows)
            elif explicit_death or typed_death:
                diagnosis_scope, scope_gap = "death", None
                consumed.extend(("death_record", row) for row in death_rows)
                consumed.extend(("inpat_registration", row) for row in death_registration_rows)
            elif len(authority_types) > 1:
                scope_gap = "scope_conflict"
                consumed.extend((authority_source_key, row) for row in raw_authority_rows)
            elif frozen_running and (discharge_rows or "出院诊断" in authority_types):
                scope_gap = "scope_conflict"
                consumed.extend(("evaluation_context.horizon", row) for row in horizon_rows)
                consumed.extend(("discharge_record", row) for row in discharge_rows)
                consumed.extend((authority_source_key, row) for row in raw_authority_rows)
            elif frozen_running:
                scope_gap = None
                consumed.extend(("evaluation_context.horizon", row) for row in horizon_rows)
            elif discharge_rows and not discharge_error:
                diagnosis_scope, scope_gap = "discharge", None
                consumed.extend(("discharge_record", row) for row in discharge_rows)
            elif alive_registration_rows:
                scope_gap = None
                consumed.extend(("inpat_registration", row) for row in alive_registration_rows)
            else:
                scope_gap = "scope_unknown"

            if frozen_running and diagnosis_scope is None and scope_gap is None:
                final_state, reason_code = "not_applicable", "trigger_absent_complete"
            elif authority_error:
                final_state, reason_code = "data_gap", authority_error
            elif scope_conflict or scope_gap == "scope_conflict":
                final_state, reason_code = "data_gap", "required_field_missing"
                display.append((rule_id, {
                    "verification_kind": "discharge_diagnosis_data_gap",
                    "authoritative_gap": "scope_conflict", "written_gap": None,
                }))
            elif diagnosis_scope is None:
                source_error = registration_error or death_error or discharge_error
                if source_error:
                    final_state, reason_code = "data_gap", source_error
                elif scope_gap:
                    final_state, reason_code = "data_gap", "required_field_missing"
                    display.append((rule_id, {
                        "verification_kind": "discharge_diagnosis_data_gap",
                        "authoritative_gap": scope_gap, "written_gap": None,
                    }))
                else:
                    final_state, reason_code = "not_applicable", "trigger_absent_complete"
            elif discharge_diagnosis_error:
                final_state, reason_code = "data_gap", discharge_diagnosis_error
            else:
                authority_rows = _discharge_or_death_diagnosis_rows(
                    raw_authority_rows, diagnosis_scope=diagnosis_scope,
                    allow_untyped_legacy_rows=not mr_diagnosis_observed and diagnosis_scope == "discharge",
                )
                written_rows = _discharge_or_death_diagnosis_rows(
                    discharge_diagnosis_rows, diagnosis_scope=diagnosis_scope,
                    allow_untyped_legacy_rows=not mr_diagnosis_observed and diagnosis_scope == "discharge",
                )
                consumed.extend((authority_source_key, row) for row in authority_rows)
                consumed.extend(("discharge_record_diagnosis", row) for row in written_rows)
                authority, authority_gap = _diagnosis_sequence(authority_rows)
                written, written_gap = _diagnosis_sequence(written_rows)
                authority = split_numbered_diagnoses(authority)
                written = split_numbered_diagnoses(written)
                names_complete = (
                    authority_gap not in {"diagnoses_missing", "name_missing"}
                    and written_gap not in {"diagnoses_missing", "name_missing"}
                )
                order_gap = {"order_missing", "order_invalid"}
                order_comparable = authority_gap is None and written_gap is None
                # 名称多重集保留重复数量；顺序不可靠时不以名称排序建立临床顺序。
                if not names_complete:
                    final_state, reason_code = "data_gap", "required_field_missing"
                    display.append((rule_id, {
                        "verification_kind": "discharge_diagnosis_data_gap",
                            **({"diagnosis_scope": "death"} if diagnosis_scope == "death" else {}),
                        "authoritative_gap": authority_gap, "written_gap": written_gap,
                    }))
                else:
                    # 顺序字段缺失不妨碍识别确定的错填或漏填：先比较名称
                    # 多重集（保留重复数量），只有内容一致时才需要可靠顺序。
                    content_consistent = sorted(authority) == sorted(written)
                    equivalent_pairs: tuple[tuple[str, str], ...] = ()
                    equivalence_state = "ready"
                    authority_rest = list((Counter(authority) - Counter(written)).elements())
                    written_rest = list((Counter(written) - Counter(authority)).elements())
                    if not content_consistent and len(authority_rest) != len(written_rest):
                        # 同义判定只做一对一配对：剩余条数不同时内容必不一致，不再调用模型
                        # （第六轮 C07：21 对 23 条，模型偶发“无法判定”致缺陷被降为资料不足）。
                        pass
                    elif not content_consistent:
                        # 院方口径（2026-10-10）：逐字未匹配的剩余名称交模型判同义，程序裁定。
                        diagnosis_equivalence_extraction = await extract_discharge_diagnosis_equivalence(
                            authority_rest, written_rest, llm_client,
                        )
                        equivalence_state = diagnosis_equivalence_extraction.state
                        equivalent_pairs = diagnosis_equivalence_extraction.pairs
                        content_consistent = (
                            equivalence_state == "ready"
                            and len(equivalent_pairs) == len(authority_rest) == len(written_rest)
                        )
                    mapped_written = _map_equivalent_diagnoses(written, equivalent_pairs)
                    pair_facts = (
                        {"equivalent_pairs": [list(pair) for pair in equivalent_pairs]}
                        if equivalent_pairs
                        else {}
                    )
                    if equivalence_state == "technical_error":
                        final_state = "technical_error"
                        reason_code = diagnosis_equivalence_extraction.reason_code or "model_invalid_output"
                    elif equivalence_state == "unresolved":
                        final_state, reason_code = "data_gap", "semantic_extraction_unresolved"
                        display.append((rule_id, {
                            "verification_kind": "discharge_diagnosis_data_gap",
                            **({"diagnosis_scope": "death"} if diagnosis_scope == "death" else {}),
                            "authoritative_gap": None,
                            "written_gap": "equivalence_unresolved",
                        }))
                    elif not content_consistent:
                        final_state, reason_code = "non_compliant", "requirement_violated"
                        display.append((rule_id, {
                            "verification_kind": "discharge_diagnosis_consistency_check",
                            **({"diagnosis_scope": "death"} if diagnosis_scope == "death" else {}),
                            "authoritative_diagnoses": sorted(authority),
                            "written_diagnoses": sorted(written),
                            "diagnoses_consistent": False,
                            "order_comparable": order_comparable,
                            **pair_facts,
                        }))
                    elif (
                        authority_gap is None
                        and written_gap == "order_missing"
                        and (written_main := _written_main_diagnosis(written_rows)) is not None
                    ):
                        # 院方口径（2026-10-10）：出院记录诊断无排列序号、仅有主诊断标记时，
                        # 内容一致后只核对主诊断选择（病案首页第 1 诊断）。
                        authority_main = authority[0]
                        main_consistent = written_main == authority_main or (
                            (authority_main, written_main) in equivalent_pairs
                        )
                        final_state = "compliant" if main_consistent else "non_compliant"
                        reason_code = "requirement_satisfied" if main_consistent else "requirement_violated"
                        display.append((rule_id, {
                            "verification_kind": "discharge_main_diagnosis_check",
                            **({"diagnosis_scope": "death"} if diagnosis_scope == "death" else {}),
                            "authoritative_main": authority_main,
                            "written_main": written_main,
                            "main_consistent": main_consistent,
                        }))
                    elif authority_gap in order_gap or written_gap in order_gap:
                        final_state, reason_code = "data_gap", "required_field_missing"
                        display.append((rule_id, {
                            "verification_kind": "discharge_diagnosis_data_gap",
                            **({"diagnosis_scope": "death"} if diagnosis_scope == "death" else {}),
                            "authoritative_gap": authority_gap,
                            "written_gap": written_gap,
                        }))
                    else:
                        complete = list(authority) == mapped_written
                        final_state = "compliant" if complete else "non_compliant"
                        reason_code = (
                            "requirement_satisfied"
                            if complete
                            else "requirement_violated"
                        )
                        display.append((rule_id, {
                            "verification_kind": "discharge_diagnosis_consistency_check",
                            **({"diagnosis_scope": "death"} if diagnosis_scope == "death" else {}),
                            "authoritative_diagnoses": list(authority),
                            "written_diagnoses": list(written),
                            "diagnoses_consistent": complete,
                            "order_comparable": True,
                            **pair_facts,
                        }))

            # 只绑定实际消费的作用域与诊断行，另一终末场景不进入事实引用。
            document_refs = []
            binding_failed = False
            for source_key in dict.fromkeys(source for source, _row in consumed):
                selected_rows = tuple(row for source, row in consumed if source == source_key)
                try:
                    matched_rows = tuple(
                        (ref, row) for ref, row in evidence_materials.document_rows(source_key, snapshot=evidence_snapshot)
                        if row in selected_rows
                    )
                    # 内部诊断无文书ID只保留合法来源锚点；不伪造逐行文书坐标。
                    matched_refs = tuple(
                        ref if _clean(row.get("document_id") or row.get("id")) or source_key in {"inpat_registration", "evaluation_context.horizon"}
                        else _fact_refs(evidence_snapshot, (source_key,))[0]
                        for ref, row in matched_rows
                    )
                except (EvidenceMaterialUnavailable, EvidenceMaterialTruncated):
                    binding_failed = True
                    break
                if len(matched_refs) != len(selected_rows):
                    binding_failed = True
                    break
                document_refs.extend(matched_refs)
            decisions.append(_decision(
                rule_id=rule_id, snapshot=evidence_snapshot,
                source_keys=() if consumed else (*scope_sources, "discharge_record", "discharge_record_diagnosis"),
                document_refs=document_refs, exact_document_refs=bool(consumed),
                final_state="technical_error" if binding_failed else final_state,
                reason_code="snapshot_mismatch" if binding_failed else reason_code,
            ))
            continue

        if rule_id == "LX0609-07-01-03":
            source_keys = (
                "inpat_registration", "admission_record", "mr_bloodtrans", "bloodtrans_record", "labtest_item_report",
                "daily_course_record", "senior_course_record", "inpat_nondrug_order", "inpat_drug_order",
            )
            performance_rows = tuple(bloodtrans_record_rows)
            dedicated_performance_source = bool(performance_rows)
            if not performance_rows:
                performance_rows = select_transfusion_course_candidates((*daily_rows, *senior_rows))
                if performance_rows:
                    transfusion_course_extraction = await classify_transfusion_course_records(performance_rows, llm_client)
                    if transfusion_course_extraction.state in {"absent", "present"}:
                        valid_ids = set(transfusion_course_extraction.valid_document_ids)
                        performance_rows = tuple(row for row in performance_rows
                                                 if str(row.get("document_id", row.get("id"))) in valid_ids)
            pending_order = any(
                re.search(r"输血|输(?:注|入)?(?:红细胞|悬浮红|去白|血浆|血小板|冷沉淀|全血)",
                          _clean(row.get("order_name") or row.get("generic_name")))
                for row in (*nondrug_order_rows, *drug_order_rows)
                if not any(word in _clean(row.get("order_status")) for word in ("取消", "作废", "撤销", "未执行"))
            )
            transfusion_source_error = mr_bloodtrans_error or bloodtrans_record_error
            actual_transfusion_rows = tuple(mr_bloodtrans_rows)
            consumed_bloodtrans_rows: list[Mapping[str, Any]] = []
            unconfirmed_record_count = 0
            extraction_reason = ""
            performed_time_missing = False
            if transfusion_source_error:
                final_state, reason_code = "data_gap", transfusion_source_error
            elif transfusion_course_extraction is not None and transfusion_course_extraction.state == "technical_error":
                final_state, reason_code = "technical_error", transfusion_course_extraction.reason_code or "model_invalid_output"
            elif transfusion_course_extraction is not None and transfusion_course_extraction.state == "data_gap":
                final_state, reason_code = "data_gap", "semantic_extraction_unresolved"
            elif not mr_bloodtrans_rows and not performance_rows:
                final_state, reason_code = (
                    ("data_gap", "positive_assertion_not_explicit") if pending_order
                    else ("not_applicable", "trigger_absent_complete")
                )
            else:
                transfusion_performance_extraction = await extract_transfusion_performance(
                    [{**row, "record_time": _row_time(row)} for row in performance_rows], llm_client,
                )
                extraction_reason = transfusion_performance_extraction.reason_code
                # 全部专用行均用于事实抽取或范围门控；否定资料不计入实施事件。
                consumed_bloodtrans_rows = list(performance_rows)
                confirmed_records = []
                for row, state, event_time in zip(
                    performance_rows,
                    transfusion_performance_extraction.states,
                    transfusion_performance_extraction.event_times,
                ):
                    if state == "performed" and (
                        event_time is not None or (dedicated_performance_source and _row_time(row) is not None)
                    ):
                        # 正文写明实际开始时刻时按开始时刻核对“输血前”；否则沿用记录时间合同。
                        confirmed_records.append(
                            {**row, "transfution_datetime": event_time.isoformat(sep=" ")}
                            if event_time is not None else {**row, "record_time": _row_time(row)}
                        )
                    elif state in {"performed", "unknown"}:
                        unconfirmed_record_count += 1
                        performed_time_missing = performed_time_missing or state == "performed"
                actual_transfusion_rows = (*mr_bloodtrans_rows, *confirmed_records)
                extraction_failed = transfusion_performance_extraction.technical_failure
                if extraction_failed and not mr_bloodtrans_rows:
                    # 实施抽取的模型调用失败不代表病历资料缺失，不能要求医院补写实施事实。
                    final_state, reason_code = "technical_error", extraction_reason
                elif not actual_transfusion_rows:
                    final_state = "data_gap"
                    reason_code = (
                        "authoritative_time_missing" if performed_time_missing
                        else extraction_reason or "positive_assertion_not_explicit"
                    )
                elif registration_error:
                    final_state, reason_code = "data_gap", registration_error
                elif lab_item_error:
                    final_state, reason_code = "data_gap", lab_item_error
                else:
                    final_state, detail_reason, facts = evaluate_pretransfusion_nine_items(
                        {
                            "inpat_registration": list(registration_rows) if any(
                                resolve_pretransfusion_admission_time(row) is not None for row in registration_rows
                            ) else list(admission_rows),
                            "mr_bloodtrans": list(actual_transfusion_rows),
                            "labtest_item_report": list(lab_item_rows),
                            "blood_application": [],
                            "__logical_source_states__": {
                                "labtest_item_report": "available" if lab_item_rows else "empty",
                            },
                        },
                        require_current_stay=True,
                    )
                    reason_code = {
                        "pretransfusion_items_complete": "requirement_satisfied",
                        "pretransfusion_items_incomplete": "requirement_violated",
                        "pretransfusion_tests_after_transfusion": "requirement_violated",
                        "pretransfusion_test_time_missing": "authoritative_time_missing",
                        "authoritative_time_missing": "authoritative_time_missing",
                        "transfusion_time_unavailable": "authoritative_time_missing",
                        "admission_time_unavailable": "authoritative_time_missing",
                        "pretransfusion_item_contract_unavailable": "source_unavailable",
                        "pretransfusion_lab_results_absent": "source_unavailable",
                        "pretransfusion_tests_outside_current_stay": "requirement_violated",
                        "source_query_error": "source_query_error",
                    }.get(detail_reason, "required_field_missing")
                    if final_state == "compliant" and unconfirmed_record_count and extraction_failed:
                        # 结构化输注已可核对，但其余记录因模型失败未核实实施，不能确认合规；
                        # 不合规结论只依赖已确认事件，照常保留。
                        final_state, reason_code, facts = "technical_error", extraction_reason, None
                    elif final_state == "compliant" and unconfirmed_record_count:
                        final_state = "data_gap"
                        reason_code = "authoritative_time_missing" if performed_time_missing else extraction_reason or "positive_assertion_not_explicit"
                        facts = None
                    elif final_state == "non_compliant" and unconfirmed_record_count and facts is not None:
                        facts = {**facts, "unconfirmed_record_count": unconfirmed_record_count}
                    if facts is not None:
                        display.append((rule_id, dict(facts)))
            decisions.append(_decision(
                rule_id=rule_id, snapshot=evidence_snapshot,
                source_keys=source_keys,
                final_state=final_state, reason_code=reason_code,
                exact_document_refs=not actual_transfusion_rows and bool(consumed_bloodtrans_rows) and not transfusion_source_error,
                document_refs=(
                    _070_document_refs(snapshot=evidence_snapshot, materials=evidence_materials,
                        consumed_bloodtrans_rows=consumed_bloodtrans_rows,
                        include_pretransfusion_materials=bool(actual_transfusion_rows))
                    if (actual_transfusion_rows or consumed_bloodtrans_rows) and not transfusion_source_error
                    else ()
                ),
            ))
            continue

        if rule_id == "LX0609-10-03-01":
            # 院方口径（2026-10-11）：有创操作目录为院方目录中的治疗性操作与介入治疗
            # 共 92 项。运行病历只看医嘱（模型把不规范的医嘱名称归入目录）；终末质控
            # 有病案首页时同时按首页手术操作编码精确匹配。
            final_state, reason_code = "", ""
            triggers: tuple[Any, ...] = ()
            order_rows = _invasive_candidate_order_rows(nondrug_order_rows)
            if nondrug_order_error:
                final_state, reason_code = "data_gap", nondrug_order_error
            else:
                mapping = await map_orders_to_invasive_catalog(
                    [row.get("order_name") for row in order_rows], llm_client,
                )
                invasive_extractions.append(mapping)
                if mapping.state == "technical_error":
                    final_state, reason_code = "technical_error", mapping.reason_code
                elif mapping.state == "unresolved":
                    final_state, reason_code = "data_gap", mapping.reason_code
                else:
                    triggers = _merge_invasive_triggers((
                        *_invasive_order_triggers(order_rows, mapping.mapped),
                        *(() if mr_surgery_error else _invasive_front_page_triggers(mr_surgery_rows)),
                    ))
                    if not triggers:
                        final_state, reason_code = "not_applicable", "trigger_absent_complete"
                    elif any(trigger.anchor_date is None for trigger in triggers):
                        final_state, reason_code = "data_gap", "authoritative_time_missing"
                    elif (
                        first_course_error or daily_error or senior_error
                        or postop_first_error or surgery_record_error
                    ):
                        final_state, reason_code = "data_gap", (
                            first_course_error or daily_error or senior_error
                            or postop_first_error or surgery_record_error
                        )
            if not final_state:
                # 0910 源库日常病程为空、病程多记于查房记录，操作记录须同时核对
                # 首次病程、日常病程、查房记录、术后首次病程与手术记录。
                documentation = await check_invasive_procedure_records(
                    triggers,
                    (
                        *first_course_rows, *daily_rows, *senior_rows,
                        *postop_first_rows, *surgery_record_rows,
                    ),
                    llm_client,
                )
                invasive_extractions.append(documentation)
                states = dict(documentation.states)
                names = [trigger.procedure.name for trigger in triggers]
                missing = [
                    trigger.procedure.name for trigger in triggers
                    if states.get(trigger.procedure.code) == "not_documented"
                ]
                if documentation.state == "technical_error":
                    final_state, reason_code = "technical_error", documentation.reason_code
                elif documentation.state == "unresolved":
                    final_state, reason_code = "data_gap", documentation.reason_code
                elif missing:
                    final_state, reason_code = "non_compliant", "required_document_missing"
                    display.append((rule_id, {
                        "failure_kind": "invasive_procedure_record_missing",
                        "procedures": names,
                        "procedure_count": len(names),
                        "missing_procedures": missing,
                    }))
                elif any(state == "uncertain" for state in states.values()):
                    final_state, reason_code = "data_gap", "semantic_extraction_unresolved"
                else:
                    final_state, reason_code = "compliant", "requirement_satisfied"
                    display.append((rule_id, {
                        "verification_kind": "invasive_procedure_record_complete",
                        "procedures": names,
                        "procedure_count": len(names),
                    }))
            decisions.append(_decision(
                rule_id=rule_id, snapshot=evidence_snapshot,
                source_keys=(
                    "inpat_nondrug_order", "first_course_record", "daily_course_record",
                    "senior_course_record", "postsurg_firstcourse_record", "surgery_record",
                    "mr_surgery",
                ),
                final_state=final_state, reason_code=reason_code,
            ))
            continue

        if rule_id in {"LX0609-09-02-01", "LX0609-04-02-06", "LX0609-04-02-08"}:
            source_error = registration_error or death_error or discharge_error
            if source_error and death_state == "unknown":
                decisions.append(
                    _decision(
                        rule_id=rule_id,
                        snapshot=evidence_snapshot,
                        source_keys=(
                            "inpat_registration",
                            "death_record",
                            "discharge_record",
                        ),
                        final_state="data_gap",
                        reason_code=source_error,
                    )
                )
                continue
            if death_state == "absent":
                decisions.append(
                    _decision(
                        rule_id=rule_id,
                        snapshot=evidence_snapshot,
                        source_keys=(
                            "inpat_registration",
                            "death_record",
                            "discharge_record",
                        ),
                        final_state="not_applicable",
                        reason_code="trigger_absent_complete",
                    )
                )
                continue
            if death_state != "present":
                decisions.append(
                    _decision(
                        rule_id=rule_id,
                        snapshot=evidence_snapshot,
                        source_keys=(
                            "inpat_registration",
                            "death_record",
                            "discharge_record",
                        ),
                        final_state="data_gap",
                        reason_code=(
                            "authoritative_time_conflict"
                            if death_state == "conflict"
                            else "applicability_source_gap"
                        ),
                    )
                )
                continue

        if rule_id == "LX0609-04-02-08":
            try:
                death_document_rows = evidence_materials.document_rows(
                    "death_record", snapshot=evidence_snapshot
                )
            except EvidenceMaterialTruncated:
                death_document_rows = ()
                death_rule_error = "source_truncated"
            except EvidenceMaterialUnavailable:
                death_document_rows = ()
                death_rule_error = "source_unavailable"
            else:
                death_rule_error = death_error
            outcome = evaluate_rule_076(
                death_state=death_state,
                death_rows=death_document_rows,
                source_error=death_rule_error,
            )
            decisions.append(
                _decision(
                    rule_id=rule_id,
                    snapshot=evidence_snapshot,
                    source_keys=(
                        "inpat_registration",
                        "death_record",
                        "discharge_record",
                    ),
                    final_state=outcome.status,
                    reason_code=outcome.reason_code,
                    document_refs=outcome.document_refs,
                    criterion_results=outcome.criterion_results,
                )
            )
            continue

        if rule_id == "LX0609-04-02-06":
            final_state = "compliant" if death_rows else "non_compliant"
            death_document_refs = _death_document_refs(
                snapshot=evidence_snapshot,
                materials=evidence_materials,
                selected_document_refs=tuple(
                    {
                        "source_type": "death_record",
                        "source_document_id": _clean(
                            row.get("document_id") or row.get("id")
                        ),
                    }
                    for row in death_rows
                    if _clean(row.get("document_id") or row.get("id"))
                ),
            )
            display.append((rule_id, {
                "verification_kind": "death_record_presence_check",
                "death_confirmed": True,
                "death_time": death_time.isoformat(sep=" ") if death_time else None,
                "death_record_count": len(death_rows),
            }))
            decisions.append(
                _decision(
                    rule_id=rule_id,
                    snapshot=evidence_snapshot,
                    source_keys=("inpat_registration", "death_record"),
                    final_state=final_state,
                    reason_code=(
                        "requirement_satisfied"
                        if death_rows
                        else "required_document_missing"
                    ),
                    document_refs=death_document_refs,
                    # 无可定位文书 ID 时仍保留原来源级事实引用，让 Binding
                    # 维持既有临床结论；公共投影会因没有真实 ID 而不展示证据。
                    exact_document_refs=bool(death_document_refs),
                )
            )
            continue

        if rule_id == "LX0609-09-02-01":
            outcome = evaluate_death_discussion_timeliness(
                death_time=death_time,
                death_rows=death_rows,
                discussion_rows=discussion_rows,
                discussion_error=discussion_error,
                horizon_rows=horizon_rows,
                horizon_error=horizon_error,
            )
            if outcome.display_facts is not None:
                display.append((rule_id, outcome.display_facts))
            raw_selected_document_refs = (
                outcome.display_facts.get("source_document_refs")
                if isinstance(outcome.display_facts, Mapping)
                else ()
            )
            selected_document_refs = (
                tuple(item for item in raw_selected_document_refs if isinstance(item, Mapping))
                if isinstance(raw_selected_document_refs, (list, tuple))
                else ()
            )
            death_document_refs = _death_document_refs(
                snapshot=evidence_snapshot,
                materials=evidence_materials,
                selected_document_refs=selected_document_refs,
            )
            decisions.append(
                _decision(
                    rule_id=rule_id,
                    snapshot=evidence_snapshot,
                    source_keys=(
                        "death_record",
                        "death_discussion",
                        "evaluation_context.horizon",
                    ),
                    final_state=outcome.final_state,
                    reason_code=outcome.reason_code,
                    document_refs=death_document_refs,
                    # 没有真实文书 ID 时不能把正常资料缺失升级成技术错误；仅在
                    # 已选择到同快照文书时收紧为逐行引用。
                    exact_document_refs=bool(death_document_refs),
                )
            )
            continue

        if rule_id == "LX0609-08-01-01":
            discharge_horizon_error = (
                horizon_error
                if horizon_error in _BLOCKING_DISCHARGE_HORIZON_ERRORS
                else ""
            )
            registration_discharge_times = _registration_discharge_times(
                registration_rows
            )
            registration_time_conflicts = (
                registration_discharge_times
                if len(registration_discharge_times) > 1
                else ()
            )
            discharge_time, discharge_time_source = _discharge_time_with_source(
                registration_rows,
                discharge_rows,
                horizon_rows,
                discharge_horizon_error,
            )
            if discharge_time_source == "evaluation_context.horizon":
                registration_time_conflicts = ()
            outcome = evaluate_discharge_documentation_timeliness(
                death_state=death_state,
                death_error=death_error,
                registration_error=(
                    registration_error or discharge_horizon_error
                ),
                discharge_error=discharge_error,
                discharge_time=(
                    None
                    if registration_time_conflicts
                    else discharge_time
                ),
                discharge_time_source=(
                    "" if registration_time_conflicts else discharge_time_source
                ),
                discharge_rows=discharge_rows,
                registration_time_conflicts=registration_time_conflicts,
            )
            if outcome.display_facts is not None:
                display.append((rule_id, outcome.display_facts))
            source_keys = (
                ("inpat_registration", "death_record")
                if death_state == "present" or (death_state == "unknown" and death_error)
                else ("inpat_registration", "discharge_record")
            )
            discharge_document_refs: tuple[str, ...] = ()
            discharge_rows_were_consumed = (
                death_state != "present"
                and not (death_state == "unknown" and death_error)
                and not registration_error
                and not discharge_error
                and not registration_time_conflicts
                and discharge_time is not None
            )
            if discharge_rows_were_consumed:
                try:
                    discharge_document_refs = tuple(
                        reference
                        for reference, _row in evidence_materials.document_rows(
                            "discharge_record", snapshot=evidence_snapshot
                        )
                    )
                except (EvidenceMaterialUnavailable, EvidenceMaterialTruncated):
                    discharge_document_refs = ()
            decisions.append(
                _decision(
                    rule_id=rule_id,
                    snapshot=evidence_snapshot,
                    source_keys=source_keys,
                    final_state=outcome.final_state,
                    reason_code=outcome.reason_code,
                    document_refs=discharge_document_refs,
                )
            )
            continue

        if rule_id == "LX0609-08-01-02":
            oral_prescription_names = _discharge_oral_prescription_names(evidence_materials)
            (
                formal_prescription_medications,
                formal_prescription_error,
                affected_prescription_item_count,
            ) = _formal_discharge_prescription_medications(evidence_materials)
            if discharge_error:
                decisions.append(
                    _decision(
                        rule_id=rule_id,
                        snapshot=evidence_snapshot,
                        source_keys=("discharge_record",),
                        final_state="data_gap",
                        reason_code=discharge_error,
                    )
                )
                continue
            if not discharge_rows:
                decisions.append(
                    _decision(
                        rule_id=rule_id,
                        snapshot=evidence_snapshot,
                        source_keys=("discharge_record",),
                        final_state="not_applicable",
                        reason_code="trigger_absent_complete",
                    )
                )
                continue
            (
                medications,
                medication_error,
                selected_discharge_row_indexes,
            ) = _structured_discharge_medications(
                discharge_rows
            )
            if medication_error and len(discharge_rows) > 1:
                resolved = await _resolve_multi_record_discharge_medications(
                    discharge_rows, llm_client, other_medication_extractions,
                )
                if resolved is not None:
                    resolved_state, resolved_reason, resolved_medications, resolved_indexes = resolved
                    if resolved_state:
                        decisions.append(_decision(
                            rule_id=rule_id, snapshot=evidence_snapshot,
                            source_keys=("discharge_record",), final_state=resolved_state,
                            reason_code=resolved_reason,
                        ))
                        continue
                    medications, medication_error = resolved_medications, ""
                    selected_discharge_row_indexes = resolved_indexes
            use_unstructured_extraction = (
                medication_error
                and len(discharge_rows) == 1
                and discharge_rows[0].get("discharge_medications") is None
                and bool(_clean(discharge_rows[0].get("discharge_order")))
            )
            if use_unstructured_extraction:
                # 模型输入明确只有这一行；来源选择不依赖模型输出。
                selected_discharge_row_indexes = (0,)
            selected_discharge_document_refs: tuple[str, ...] = ()
            original_discharge_rows = evidence_materials.rows("discharge_record")
            try:
                discharge_document_rows = evidence_materials.document_rows(
                    "discharge_record", snapshot=evidence_snapshot
                )
            except (EvidenceMaterialUnavailable, EvidenceMaterialTruncated):
                discharge_document_rows = ()
            selected_refs: list[str] = []
            if (
                len(original_discharge_rows)
                == len(discharge_rows)
                == len(discharge_document_rows)
            ):
                for selected_index in selected_discharge_row_indexes:
                    if not 0 <= selected_index < len(original_discharge_rows):
                        selected_refs = []
                        break
                    selected_material_row = original_discharge_rows[selected_index]
                    matching_refs = tuple(
                        reference
                        for reference, material_row in discharge_document_rows
                        if material_row is selected_material_row
                    )
                    if len(matching_refs) != 1:
                        selected_refs = []
                        break
                    selected_refs.append(matching_refs[0])
            selected_discharge_document_refs = tuple(selected_refs)
            # 仅在结构化资料缺失且固定标签无法解析时裁剪出院医嘱。
            # 多份记录不能猜选一份；不覆盖已提供但格式非法的结构化字段。
            if use_unstructured_extraction:
                medication_extraction = _with_oral_route_uncertainty_resolved(
                    await extract_discharge_medications(
                        str(discharge_rows[0]["discharge_order"]), llm_client
                    ), oral_prescription_names=oral_prescription_names,
                    source_text=str(discharge_rows[0]["discharge_order"]),
                )
                # 已确认药物的明确缺项足以证明不完整；未知字段不可冒充缺项。
                if medication_extraction.state == "unknown":
                    confirmed_missing_fields = sorted({
                        name
                        for assertions in medication_extraction.field_assertions
                        if assertions.get("drug_name") == "present"
                        for name, assertion in assertions.items()
                        if assertion == "missing"
                    })
                    if confirmed_missing_fields:
                        display.append((rule_id, {
                            "verification_kind": "discharge_medication_completeness_check",
                            "medication_count": sum(
                                assertions.get("drug_name") == "present"
                                for assertions in medication_extraction.field_assertions
                            ),
                            "required_fields": ["drug_name", "dose", "route", "duration"],
                            "missing_fields": confirmed_missing_fields,
                        }))
                        decisions.append(_decision(
                            rule_id=rule_id, snapshot=evidence_snapshot,
                            source_keys=("discharge_record",),
                            final_state="non_compliant",
                            reason_code="requirement_violated",
                            document_refs=selected_discharge_document_refs,
                        ))
                        continue
                if medication_extraction.state in {"ready", "absent"}:
                    medications = list(medication_extraction.medications)
                    medication_error = ""
                else:
                    final_state = {
                        "unknown": "uncertain",
                        "data_gap": "data_gap",
                        "technical_error": "technical_error",
                    }[medication_extraction.state]
                    display.append((rule_id, {
                        "verification_kind": "discharge_medication_extraction_pending",
                        "extraction_state": medication_extraction.state,
                    }))
                    decisions.append(_decision(
                        rule_id=rule_id, snapshot=evidence_snapshot,
                        source_keys=("discharge_record",),
                        final_state=final_state,
                        reason_code=medication_extraction.reason_code,
                        document_refs=selected_discharge_document_refs,
                    ))
                    continue
            if medication_error:
                final_state, reason_code = "data_gap", medication_error
            elif not medications:
                final_state, reason_code = "not_applicable", "trigger_absent_complete"
            else:
                required_groups = _DISCHARGE_MEDICATION_REQUIRED_GROUPS
                medications = _with_dosage_form_oral_route(medications, oral_prescription_names=oral_prescription_names)
                missing_fields = sorted({
                    group[0]
                    for item in medications
                    for group in required_groups
                    if not any(_clean(item.get(key)) for key in group)
                })
                if not missing_fields and formal_prescription_error:
                    final_state, reason_code = "data_gap", "required_field_missing"
                    display.append((rule_id, {
                        "verification_kind": "discharge_medication_prescription_identity_gap",
                        "gap_reason": formal_prescription_error,
                        "affected_prescription_item_count": affected_prescription_item_count,
                    }))
                elif formal_prescription_error:
                    # 正文已有确定缺项即可判不合规；处方范围未知时不发布“处方0项”等伪完整事实。
                    final_state, reason_code = "non_compliant", "requirement_violated"
                    display.append((rule_id, {
                        "verification_kind": "discharge_medication_completeness_check",
                        "medication_count": len(medications),
                        "required_fields": ["drug_name", "dose", "route", "duration"],
                        "missing_fields": missing_fields,
                    }))
                else:
                    missing_drug_names = _unmatched_formal_discharge_medication_names(
                        medications, formal_prescription_medications,
                    )
                    if missing_drug_names and "drug_name" not in missing_fields:
                        missing_fields.append("drug_name")
                        missing_fields.sort()
                    complete = not missing_fields
                    final_state = "compliant" if complete else "non_compliant"
                    reason_code = (
                        "requirement_satisfied" if complete else "requirement_violated"
                    )
                    display.append(
                        (
                            rule_id,
                            {
                                "verification_kind": "discharge_medication_completeness_check",
                                "medication_count": len(medications),
                                "prescription_medication_count": len(formal_prescription_medications),
                                "required_fields": [
                                    "drug_name",
                                    "dose",
                                    "route",
                                    "duration",
                                ],
                                "missing_fields": missing_fields,
                                "missing_drug_names": list(missing_drug_names),
                            },
                        )
                    )
            decisions.append(
                _decision(
                    rule_id=rule_id,
                    snapshot=evidence_snapshot,
                    source_keys=(
                        ("discharge_record",)
                        if reason_code == "trigger_absent_complete"
                        else ("discharge_record", "inpat_prescription", "inpat_prescription_item")
                    ),
                    final_state=final_state,
                    reason_code=reason_code,
                    document_refs=(
                        ()
                        if reason_code == "trigger_absent_complete"
                        else selected_discharge_document_refs
                    ),
                )
            )
            continue

        if rule_id == "LX0609-04-05-03":
            assert surgery_applicability is not None
            gate_outcome = _surgery_applicability_outcome(surgery_applicability)
            surgery_events: tuple[_PostoperativeSurgeryEvent, ...] = ()
            linked_events: tuple[
                tuple[_PostoperativeSurgeryEvent, tuple[Mapping[str, Any], ...]], ...
            ] = ()
            linkage_error = ""
            if gate_outcome is not None:
                final_state, reason_code = gate_outcome
            else:
                surgery_events = _postoperative_surgery_events(
                    mr_surgery_rows=mr_surgery_rows,
                    surgery_record_rows=surgery_record_rows,
                )
                if any(event.surgery_time_estimated for event in surgery_events):
                    postoperative_time_estimated_rules.add(rule_id)
                linkage_error = postop_first_error
                if not linkage_error:
                    linked_events, linkage_error = _link_postoperative_first_course_records(
                        surgery_events=surgery_events,
                        postoperative_rows=postop_first_rows,
                    )
                if linkage_error:
                    final_state, reason_code = "data_gap", linkage_error
                else:
                    unmet_events = [
                        event.document_id
                        for event, linked_rows in linked_events
                        if not linked_rows
                    ]
                    final_state = "compliant" if not unmet_events else "non_compliant"
                    reason_code = (
                        "requirement_satisfied"
                        if not unmet_events
                        else "required_document_missing"
                    )
            if gate_outcome is None:
                display.append((rule_id, {
                    "verification_kind": "postoperative_first_course_presence_check",
                    "performed_surgery_count": len(surgery_events),
                    "postoperative_first_course_count": len(postop_first_rows),
                    "surgery_events": [
                        {
                            **_event_display_base(event),
                            "postoperative_first_course_document_ids": [
                                _clean(row.get("document_id") or row.get("id"))
                                for row in linked_rows
                            ],
                        }
                        for event, linked_rows in linked_events
                    ],
                    "unmet_surgery_events": (
                        [
                            event.document_id
                            for event, linked_rows in linked_events
                            if not linked_rows
                        ]
                        if not linkage_error
                        else []
                    ),
                }))
            selected_postoperative_rows: list[Mapping[str, Any]] = []
            if (
                gate_outcome == ("not_applicable", "performed_event_absent")
                and surgery_applicability.procedure_kind == "non_surgical_operation"
            ):
                selected_postoperative_rows.extend(
                    row
                    for row in mr_surgery_rows
                    if catalog_surgery_state(row) is False
                )
            if surgery_events:
                if linkage_error:
                    selected_postoperative_rows.extend(
                        row for event in surgery_events for row in event.member_rows
                    )
                elif final_state == "non_compliant":
                    # 缺失首次病程时，客户证据只指向缺失的手术事件；已满足
                    # 事件的病程不应被这条缺陷结论顺带投影。
                    selected_postoperative_rows.extend(
                        row
                        for event, linked_rows in linked_events
                        if not linked_rows
                        for row in event.member_rows
                    )
                else:
                    selected_postoperative_rows.extend(
                        row for event, _linked_rows in linked_events for row in event.member_rows
                    )
                    selected_postoperative_rows.extend(
                        row
                        for _event, linked_rows in linked_events
                        for row in linked_rows
                    )
            postoperative_document_refs = _postoperative_document_refs(
                snapshot=evidence_snapshot,
                materials=evidence_materials,
                selected_rows=selected_postoperative_rows,
            )
            decisions.append(
                _decision(
                    rule_id=rule_id,
                    snapshot=evidence_snapshot,
                    source_keys=(
                        () if selected_postoperative_rows else ("surgery_record",)
                    ),
                    document_refs=postoperative_document_refs,
                    exact_document_refs=bool(selected_postoperative_rows),
                    final_state=final_state,
                    reason_code=reason_code,
                )
            )
            continue

        if rule_id in {"LX0609-04-05-01", "LX0609-04-05-02"}:
            assert surgery_applicability is not None
            gate_outcome = _surgery_applicability_outcome(surgery_applicability)
            surgery_events = _postoperative_surgery_events(
                mr_surgery_rows=mr_surgery_rows,
                surgery_record_rows=surgery_record_rows,
            )
            if any(event.surgery_time_estimated for event in surgery_events):
                postoperative_time_estimated_rules.add(rule_id)
            selected_postoperative_rows: list[Mapping[str, Any]] = []
            if (
                gate_outcome == ("not_applicable", "performed_event_absent")
                and surgery_applicability.procedure_kind == "non_surgical_operation"
            ):
                selected_postoperative_rows.extend(
                    row
                    for row in mr_surgery_rows
                    if catalog_surgery_state(row) is False
                )
            if gate_outcome is not None:
                final_state, reason_code = gate_outcome
            elif not surgery_events:
                final_state, reason_code = "data_gap", "authoritative_time_missing"
            elif len(surgery_events) > 1 and any(
                event.source_key == "mr_surgery" and event.surgery_begin_time is None
                for event in surgery_events
            ):
                # 主控代定口径（2026-10-18，待客户复核），基线064/065：多首页行缺开始时间仍资料不足。
                final_state, reason_code = "data_gap", "authoritative_time_missing"
            elif any(event.surgery_end_time is None for event in surgery_events):
                final_state, reason_code = "data_gap", "authoritative_time_missing"
                display.append((rule_id, {
                    "verification_kind": "postoperative_surgery_event_time_check",
                    "performed_surgery_count": len(surgery_events),
                    "surgery_events": [_event_display_base(event) for event in surgery_events],
                    "missing_surgery_end_events": [
                        event.document_id
                        for event in surgery_events
                        if event.surgery_end_time is None
                    ],
                }))
            elif rule_id == "LX0609-04-05-01" and (
                window_gate := _postoperative_window_gate(
                    surgery_events=surgery_events,
                    horizon_rows=horizon_rows,
                    horizon_error=horizon_error,
                )
            ) is not None:
                final_state, reason_code, window_facts = window_gate
                display.append((rule_id, window_facts))
            elif rule_id == "LX0609-04-05-02" and (
                senior_round_horizon := _postoperative_senior_round_evaluation_horizon(
                    surgery_events=surgery_events,
                    horizon_rows=horizon_rows,
                    horizon_error=horizon_error,
                )
            )[2]:
                final_state, reason_code = "data_gap", senior_round_horizon[2]
                display.append((rule_id, {
                    "verification_kind": "postoperative_senior_round_window_unavailable",
                    "issue": reason_code,
                }))
            elif (
                (daily_error or senior_error)
                if rule_id == "LX0609-04-05-01"
                else senior_error
            ):
                final_state, reason_code = "data_gap", (
                    daily_error or senior_error
                    if rule_id == "LX0609-04-05-01"
                    else senior_error
                )
            elif rule_id == "LX0609-04-05-01" and any(
                event.surgeon_names
                and all(
                    _physician_identity_is_masked(name)
                    for name in event.surgeon_names
                )
                for event in surgery_events
            ):
                final_state, reason_code = "data_gap", "association_failed"
            else:
                if rule_id == "LX0609-04-05-02":
                    evaluation_time, evaluation_date, _ = (
                        _postoperative_senior_round_evaluation_horizon(
                            surgery_events=surgery_events,
                            horizon_rows=horizon_rows,
                            horizon_error=horizon_error,
                        )
                    )
                    event_facts: list[dict[str, Any]] = []
                    unmet_events: list[dict[str, Any]] = []
                    not_mature_events: list[dict[str, Any]] = []
                    mature_events = tuple(
                        event for event in surgery_events
                        if event.surgery_end_time is not None
                        and (
                            evaluation_time >= event.surgery_end_time + timedelta(hours=72)
                            if evaluation_time is not None
                            else evaluation_date > (event.surgery_end_time + timedelta(hours=72)).date()
                        )
                    )
                    dated_candidates = tuple(
                        ("senior_course_record", ordinal, row)
                        for ordinal, row in enumerate(senior_rows)
                        if (value := _row_time(row)) is not None
                        and any(event.surgery_end_time <= value <= event.surgery_end_time + timedelta(hours=72) for event in mature_events)
                    )
                    undated_senior_rows = tuple(
                        row for row in senior_rows
                        if _row_time(row) is None
                        and isinstance(row.get("record_content"), str)
                        and row["record_content"].strip()
                    )
                    body_states: dict[tuple[str, int], str] = {}
                    body_issue = ""
                    if dated_candidates:
                        candidates = (*dated_candidates, *(
                            ("senior_course_record", ordinal, row)
                            for ordinal, row in enumerate(senior_rows)
                            if _row_time(row) is None
                        ))
                        try:
                            body_documents, body_refs = _course_body_candidate_inputs(
                                snapshot=evidence_snapshot, materials=evidence_materials, candidates=candidates,
                            )
                        except (ValueError, EvidenceMaterialUnavailable):
                            extraction = CourseBodyExtraction("data_gap", "source_readiness_unproven")
                        else:
                            extraction = await extract_course_body_facts(body_documents, llm_client)
                            body_states = {key: extraction.states.get(ref, "unknown") for key, ref in body_refs.items()}
                        course_body_extractions.append(extraction)
                        body_issue = extraction.reason_code if extraction.state != "ready" else ""
                    unresolved_senior_semantics = False
                    unresolved_senior_time = False
                    unresolved_senior_body = False
                    for event in surgery_events:
                        assert event.surgery_end_time is not None
                        selected_postoperative_rows.extend(event.member_rows)
                        deadline = event.surgery_end_time + timedelta(hours=72)
                        window_mature = (
                            evaluation_time >= deadline
                            if evaluation_time is not None
                            else evaluation_date > deadline.date()
                        )
                        dated_senior_rows = tuple(
                            row
                            for row in senior_rows
                            if (value := _row_time(row)) is not None
                            and event.surgery_end_time <= value <= deadline
                        )
                        # 只核正文存在，不评价临床充分性；日期和纯签名不能代替查房正文。
                        matched_senior_rows = tuple(
                            row for ordinal, row in enumerate(senior_rows)
                            if any(row is candidate for candidate in dated_senior_rows)
                            and body_states.get(("senior_course_record", ordinal)) == "present"
                        )
                        selected_postoperative_rows.extend(
                            matched_senior_rows or dated_senior_rows
                        )
                        senior_round_times = [
                            value.isoformat(sep=" ")
                            for row in matched_senior_rows
                            if (value := _row_time(row)) is not None
                        ]
                        event_fact = {
                            **_event_display_base(event),
                            "deadline": deadline.isoformat(sep=" "),
                            "senior_round_times": senior_round_times,
                            "window_state": (
                                "mature"
                                if window_mature
                                else "evaluation_window_not_mature"
                            ),
                        }
                        event_facts.append(event_fact)
                        if not window_mature:
                            not_mature_events.append({
                                "document_id": event.document_id,
                                "deadline": deadline.isoformat(sep=" "),
                            })
                        elif not senior_round_times and undated_senior_rows:
                            # 已有查房但无法定位日期，不能据此宣称72小时内缺少查房。
                            unresolved_senior_time = True
                            selected_postoperative_rows.extend(undated_senior_rows)
                        elif not senior_round_times and dated_senior_rows:
                            if any(
                                body_states.get(("senior_course_record", ordinal)) == "unknown"
                                for ordinal, row in enumerate(senior_rows)
                                if any(row is candidate for candidate in dated_senior_rows)
                            ):
                                unresolved_senior_semantics = True
                            else:
                                unresolved_senior_body = True
                        elif not senior_round_times:
                            unmet_events.append({
                                "document_id": event.document_id,
                                "senior_round_times": [],
                            })
                    if body_issue:
                        final_state, reason_code = "data_gap", body_issue
                    elif unresolved_senior_semantics:
                        final_state, reason_code = "data_gap", "semantic_extraction_unresolved"
                    elif unresolved_senior_time:
                        final_state, reason_code = "data_gap", "authoritative_time_missing"
                    elif unresolved_senior_body:
                        final_state, reason_code = "data_gap", "required_field_missing"
                    elif unmet_events:
                        final_state, reason_code = (
                            "non_compliant",
                            "required_document_missing",
                        )
                    elif not_mature_events:
                        final_state, reason_code = (
                            "not_applicable",
                            "evaluation_window_not_mature",
                        )
                    else:
                        final_state, reason_code = "compliant", "requirement_satisfied"
                    senior_round_delivery_values = sorted({
                        value
                        for item in event_facts
                        for value in item["senior_round_times"]
                    })
                    if unmet_events:
                        senior_round_delivery_values = [
                            f"共{len(event_facts)}台手术中，{len(unmet_events)}台手术结束后72小时内"
                            "未查到上级医师查房",
                            *senior_round_delivery_values,
                        ]
                    legacy_summary_facts = {
                        "surgery_time": "；".join(
                            str(item["surgery_end_time"])
                            for item in event_facts
                            if item.get("surgery_end_time")
                        ),
                        "senior_round_times": senior_round_delivery_values,
                    }
                    if not body_issue and not unresolved_senior_semantics and (not unresolved_senior_body or unresolved_senior_time):
                        display.append((rule_id, {
                            "verification_kind": "postoperative_senior_round_window_unavailable",
                            "issue": "authoritative_time_missing",
                        } if unresolved_senior_time else {
                            "verification_kind": "postoperative_senior_round_check",
                            "threshold_hours": 72,
                            "performed_surgery_count": len(surgery_events),
                            "surgery_events": event_facts,
                            "unmet_surgery_events": unmet_events,
                            "not_mature_surgery_events": not_mature_events,
                            **(
                                {"evaluation_time": evaluation_time.isoformat(sep=" ")}
                                if evaluation_time is not None
                                else {"evaluation_date": evaluation_date.isoformat()}
                            ),
                            **legacy_summary_facts,
                        }))
                else:
                    event_facts = []
                    unmet_events = []
                    missing_surgeon_events = []
                    definite_missing_events: list[str] = []
                    empty_body_events = []
                    unresolved_time_events = []
                    undated_course_rows = tuple(
                        row for row in (*daily_rows, *senior_rows)
                        if _row_time(row) is None and _course_row_has_body(row)
                    )
                    for event in surgery_events:
                        assert event.surgery_end_time is not None
                        selected_postoperative_rows.extend(event.member_rows)
                        required_dates = {
                            (event.surgery_end_time + timedelta(days=offset)).date()
                            for offset in (1, 2, 3)
                        }
                        dated_postop_rows = tuple(
                            row
                            for row in (*daily_rows, *senior_rows)
                            if (record_time := _row_time(row)) is not None
                            and record_time.date() in required_dates
                        )
                        empty_body_dates = {
                            record_time.date()
                            for row in dated_postop_rows
                            if not _course_row_has_body(row)
                            for record_time in (_row_time(row),)
                            if record_time is not None
                        }
                        postop_rows = tuple(
                            row
                            for row in dated_postop_rows
                            if _course_row_has_body(row)
                        )
                        covered_dates = _course_dates(postop_rows)
                        for required_date in required_dates.intersection(covered_dates):
                            # 每日覆盖只需一份实际有效病程；选择权威时间最早的一份
                            # 作为该日期的客户证据，不投影同日的全部候选病程。
                            selected_postoperative_rows.append(
                                min(
                                    (
                                        row
                                        for row in postop_rows
                                        if _row_time(row) is not None
                                        and _row_time(row).date() == required_date
                                    ),
                                    key=lambda row: _row_time(row) or datetime.max,
                                )
                            )
                        unresolved_empty_body_dates = empty_body_dates.difference(
                            covered_dates
                        )
                        for empty_date in unresolved_empty_body_dates:
                            selected_postoperative_rows.append(
                                min(
                                    (
                                        row
                                        for row in dated_postop_rows
                                        if _row_time(row) is not None
                                        and _row_time(row).date() == empty_date
                                        and not _course_row_has_body(row)
                                    ),
                                    key=lambda row: _row_time(row) or datetime.max,
                                )
                            )
                        def surgeon_round_in(
                            window_start: datetime,
                            window_end: datetime,
                            candidate_rows: Sequence[Mapping[str, Any]],
                        ) -> Mapping[str, Any] | None:
                            # 院方口径：术者须亲自在术前24小时内、术后24小时内查房。
                            return next(
                                (
                                    row
                                    for row in sorted(
                                        candidate_rows,
                                        key=lambda item: _row_time(item) or datetime.max,
                                    )
                                    if (record_time := _row_time(row)) is not None
                                    and window_start <= record_time <= window_end
                                    and _course_row_has_body(row)
                                    and event.surgeon_tokens
                                    and event.surgeon_tokens.intersection(
                                        _course_record_physician_tokens(row)
                                        | _title_round_physician_tokens(
                                            row,
                                            candidate_tokens=event.surgeon_tokens,
                                        )
                                    )
                                ),
                                None,
                            )

                        # 用户口径（2026-10-22）：只有手术日期、无具体时刻时按自然日核对——
                        # 术前认手术前一日及当日，术后24小时认手术当日及次日。
                        date_only = event.surgery_time_date_only
                        surgeon_round_row = surgeon_round_in(
                            event.surgery_end_time,
                            event.surgery_end_time + (
                                timedelta(days=2) - timedelta(microseconds=1) if date_only
                                else timedelta(hours=_SURGEON_ROUND_WINDOW_HOURS)
                            ),
                            # 术者本人签署的术后首次病程也是术后查房记录；
                            # 仅参与身份/24小时时窗核对，不替代术后三日病程覆盖。
                            (*daily_rows, *senior_rows, *postop_first_rows),
                        )
                        preop_round_row = (
                            surgeon_round_in(
                                event.surgery_begin_time - timedelta(hours=_SURGEON_ROUND_WINDOW_HOURS),
                                event.surgery_begin_time + (
                                    timedelta(days=1) - timedelta(microseconds=1) if date_only else timedelta()
                                ),
                                (*daily_rows, *senior_rows),
                            )
                            if event.surgery_begin_time is not None
                            else None
                        )
                        for round_row in (preop_round_row, surgeon_round_row):
                            if round_row is not None:
                                selected_postoperative_rows.append(round_row)
                        surgeon_round = surgeon_round_row is not None
                        preop_surgeon_round = preop_round_row is not None
                        missing_dates = sorted(
                            item.isoformat()
                            for item in required_dates.difference(covered_dates)
                        )
                        event_facts.append({
                            **_event_display_base(event),
                            "required_postop_dates": sorted(
                                item.isoformat() for item in required_dates
                            ),
                            "covered_postop_dates": sorted(
                                item.isoformat() for item in covered_dates
                            ),
                            "surgeon_round_present": surgeon_round,
                            "preop_surgeon_round_present": preop_surgeon_round,
                        })
                        if not event.surgeon_tokens:
                            missing_surgeon_events.append(event.document_id)
                        if unresolved_empty_body_dates:
                            empty_body_events.append(event.document_id)
                        if event.surgery_begin_time is None and not preop_surgeon_round:
                            # 无手术开始时间时无法核对术前24小时术者查房，不能判缺失。
                            unresolved_time_events.append(event.document_id)
                            event_facts[-1]["course_time_unresolved"] = True
                        elif missing_dates or not surgeon_round or not preop_surgeon_round:
                            if undated_course_rows:
                                # 候选不能定日时，既不能补齐，也不能确认该手术缺项。
                                unresolved_time_events.append(event.document_id)
                                event_facts[-1]["course_time_unresolved"] = True
                                selected_postoperative_rows.extend(undated_course_rows)
                            else:
                                # 空正文日仅为未决，不算确定缺失日。
                                if set(missing_dates).difference(
                                    item.isoformat() for item in unresolved_empty_body_dates
                                ):
                                    definite_missing_events.append(event.document_id)
                                unmet_events.append({
                                    "document_id": event.document_id,
                                    "missing_postop_dates": missing_dates,
                                    "surgeon_round_present": surgeon_round,
                                    "preop_surgeon_round_present": preop_surgeon_round,
                                })
                    if definite_missing_events:
                        # 已确定某个术后日完全没有病程记录，属确定缺陷，不被术者身份等
                        # 其他资料缺口遮蔽。
                        final_state, reason_code = "non_compliant", "requirement_violated"
                    elif missing_surgeon_events or empty_body_events or unresolved_time_events:
                        final_state, reason_code = (
                            "data_gap",
                            "required_field_missing",
                        )
                    else:
                        final_state = "compliant" if not unmet_events else "non_compliant"
                        reason_code = (
                            "requirement_satisfied"
                            if not unmet_events
                            else "requirement_violated"
                        )
                    legacy_summary_facts = {
                        "surgery_time": "；".join(
                            str(item["surgery_end_time"])
                            for item in event_facts
                            if item.get("surgery_end_time")
                        ),
                        "required_postop_dates": sorted({
                            value
                            for item in event_facts
                            for value in item["required_postop_dates"]
                        }),
                        "covered_postop_dates": sorted({
                            value
                            for item in event_facts
                            for value in item["covered_postop_dates"]
                        }),
                        "surgeon_round_present": all(
                            item["surgeon_round_present"] is True
                            for item in event_facts
                        ),
                        "preop_surgeon_round_present": all(
                            item["preop_surgeon_round_present"] is True
                            for item in event_facts
                        ),
                    }
                    display.append(
                        (
                            rule_id,
                            {
                                "verification_kind": "postoperative_three_day_coverage_check",
                                "performed_surgery_count": len(surgery_events),
                                "surgery_events": event_facts,
                                "unmet_surgery_events": unmet_events,
                                "missing_surgeon_events": missing_surgeon_events,
                                "unresolved_course_time_events": unresolved_time_events,
                                **legacy_summary_facts,
                            },
                        )
                    )
            postoperative_document_refs = _postoperative_document_refs(
                snapshot=evidence_snapshot,
                materials=evidence_materials,
                selected_rows=selected_postoperative_rows,
            )
            decisions.append(
                _decision(
                    rule_id=rule_id,
                    snapshot=evidence_snapshot,
                    source_keys=(
                        () if selected_postoperative_rows else ("surgery_record",)
                    ),
                    document_refs=postoperative_document_refs,
                    exact_document_refs=bool(selected_postoperative_rows),
                    final_state=final_state,
                    reason_code=reason_code,
                )
            )
            continue

        if rule_id == "LX0609-08-02-01":
            discharge_horizon_error = (
                horizon_error
                if horizon_error in _BLOCKING_DISCHARGE_HORIZON_ERRORS
                else ""
            )
            course_discharge_time = _discharge_time(
                registration_rows, discharge_rows, horizon_rows, discharge_horizon_error,
            )
            body_states = {}
            body_issue = ""
            if (death_state != "present" and not (death_state == "unknown" and death_error)
                    and not (registration_error or discharge_horizon_error or discharge_error or daily_error or senior_error)
                    and course_discharge_time is not None):
                valid_dates = {course_discharge_time.date(), (course_discharge_time - timedelta(days=1)).date()}
                dated_candidates = tuple(
                    (source, ordinal, row)
                    for source, rows in (("daily_course_record", daily_rows), ("senior_course_record", senior_rows))
                    for ordinal, row in enumerate(rows)
                    if (value := _row_time(row)) is not None and value.date() in valid_dates
                )
                if dated_candidates:
                    candidates = (*dated_candidates, *(
                        (source, ordinal, row)
                        for source, rows in (("daily_course_record", daily_rows), ("senior_course_record", senior_rows))
                        for ordinal, row in enumerate(rows) if _row_time(row) is None
                    ))
                    try:
                        body_documents, body_refs = _course_body_candidate_inputs(
                            snapshot=evidence_snapshot, materials=evidence_materials, candidates=candidates,
                        )
                    except (ValueError, EvidenceMaterialUnavailable):
                        extraction = CourseBodyExtraction("data_gap", "source_readiness_unproven")
                    else:
                        extraction = await extract_course_body_facts(body_documents, llm_client)
                        body_states = {key: extraction.states.get(ref, "unknown") for key, ref in body_refs.items()}
                    course_body_extractions.append(extraction)
                    body_issue = extraction.reason_code if extraction.state != "ready" else ""
            outcome = evaluate_predischarge_course_presence(
                death_state=death_state,
                death_error=death_error,
                registration_error=(
                    registration_error or discharge_horizon_error
                ),
                discharge_error=discharge_error,
                discharge_time=_discharge_time(
                    registration_rows,
                    discharge_rows,
                    horizon_rows,
                    discharge_horizon_error,
                ),
                daily_error=daily_error,
                senior_error=senior_error,
                daily_rows=daily_rows,
                senior_rows=senior_rows,
                clinical_body_states=body_states,
            )
            if body_issue:
                outcome = PredischargeCourseOutcome("data_gap", body_issue)
            selected_course_document_ids: tuple[tuple[str, str], ...] = ()
            if outcome.display_facts is not None:
                display_facts = dict(outcome.display_facts)
                raw_selected_refs = display_facts.pop("source_document_refs", ())
                if isinstance(raw_selected_refs, (list, tuple)):
                    selected_course_document_ids = tuple(
                        (
                            _clean(item.get("source_type")),
                            _clean(item.get("source_document_id")),
                        )
                        for item in raw_selected_refs
                        if isinstance(item, Mapping)
                    )
                display.append((rule_id, display_facts))
            selected_document_refs = _selected_course_document_refs(
                snapshot=evidence_snapshot,
                materials=evidence_materials,
                selected_document_ids=selected_course_document_ids,
            )
            if outcome.final_state == "compliant":
                consumed_source_keys = (
                    "daily_course_record",
                    "senior_course_record",
                )
            elif outcome.final_state == "not_applicable" and death_state == "present":
                # 067 的已登记可绑定来源是住院登记；死亡记录只用于门控，
                # 不能作为本规则的客户文书或越过规则资料白名单。
                consumed_source_keys = ("inpat_registration",)
            elif outcome.final_state == "not_applicable":
                consumed_source_keys = ("inpat_registration", "discharge_record")
            elif outcome.final_state == "non_compliant":
                consumed_source_keys = ("inpat_registration", "discharge_record", "daily_course_record", "senior_course_record")
            else:
                consumed_source_keys = ()
            decisions.append(
                _decision(
                    rule_id=rule_id,
                    snapshot=evidence_snapshot,
                    source_keys=(
                        "inpat_registration",
                        "discharge_record",
                        "daily_course_record",
                        "senior_course_record",
                    ),
                    final_state=outcome.final_state,
                    reason_code=outcome.reason_code,
                    document_refs=_selected_course_or_consumed_source_refs(
                        snapshot=evidence_snapshot,
                        selected_document_refs=selected_document_refs,
                        consumed_source_keys=consumed_source_keys,
                    ),
                    # 无 ID 或重复 ID 时维持空的逐文书坐标。不能回退为整类来源
                    # observation，否则公共投影会把未参与判定的病程展示为证据。
                    exact_document_refs=True,
                )
            )
            continue

        if rule_id == "LX0609-08-02-02":
            if death_state == "present":
                decisions.append(
                    _decision(
                        rule_id=rule_id,
                        snapshot=evidence_snapshot,
                        source_keys=("inpat_registration", "death_record"),
                        final_state="not_applicable",
                        reason_code="trigger_absent_complete",
                        document_refs=_fact_refs(
                            evidence_snapshot,
                            ("inpat_registration",),
                        ),
                        exact_document_refs=True,
                    )
                )
                continue
            if (
                death_state == "unknown" and death_error
            ):
                decisions.append(
                    _decision(
                        rule_id=rule_id,
                        snapshot=evidence_snapshot,
                        source_keys=("inpat_registration", "death_record"),
                        final_state="data_gap",
                        reason_code=death_error,
                        exact_document_refs=True,
                    )
                )
                continue
            discharge_horizon_error = (
                horizon_error
                if horizon_error in _BLOCKING_DISCHARGE_HORIZON_ERRORS
                else ""
            )
            source_error = (
                discharge_horizon_error or registration_error or discharge_error
            )
            discharge_time = _discharge_time(
                registration_rows,
                discharge_rows,
                horizon_rows,
                discharge_horizon_error,
            )
            approval_match: tuple[str, str, Mapping[str, Any]] | None = None
            selected_course_document_ids: tuple[tuple[str, str], ...] = ()
            render_display = False
            if source_error:
                final_state, reason_code = "data_gap", source_error
            elif discharge_time is None:
                final_state, reason_code = "not_applicable", "trigger_absent_complete"
            else:
                valid_dates = {
                    discharge_time.date(),
                    (discharge_time - timedelta(days=1)).date(),
                }
                approval_match = next(
                    (
                        (source_key, approval_path, row)
                        for source_key, rows in (
                            ("daily_course_record", daily_rows),
                            ("senior_course_record", senior_rows),
                        )
                        for row in rows
                        if _row_time(row) is not None
                        and _row_time(row).date() in valid_dates
                        if (
                            approval_path := _discharge_approval_path(
                                row,
                                source_key=source_key,
                            )
                        )
                    ),
                    None,
                )
                present = approval_match is not None
                # 已识别的同意出院意见若缺时间，只能说明无法确认窗口，不能说未读到意见。
                undated_approvals = tuple(
                    (source_key, row)
                    for source_key, rows in (
                        ("daily_course_record", daily_rows),
                        ("senior_course_record", senior_rows),
                    )
                    for row in rows
                    if _row_time(row) is None
                    and _discharge_approval_path(row, source_key=source_key)
                ) if not present else ()
                approval_resolution_blocked = False
                approval_unresolved = False
                if approval_match is None and (daily_error or senior_error):
                    final_state, reason_code = (
                        "data_gap",
                        daily_error or senior_error,
                    )
                    approval_resolution_blocked = True
                elif not present and not undated_approvals and llm_client is not None:
                    semantic_candidates = tuple(
                        (source_key, row, _row_time(row), text)
                        for source_key, rows in (
                            ("daily_course_record", daily_rows),
                            ("senior_course_record", senior_rows),
                        )
                        for row in rows
                        if (
                            _row_time(row) is None
                            or _row_time(row).date() in valid_dates
                        )
                        if (text := _clean(row.get("record_content")))
                    )
                    if semantic_candidates:
                        discharge_approval_extraction = (
                            await extract_discharge_approval(
                                tuple(
                                    DischargeApprovalInput(
                                        f"doc_{index:02d}", source_key, text
                                    )
                                    for index, (source_key, _row, _time, text)
                                    in enumerate(semantic_candidates, start=1)
                                ),
                                llm_client,
                            )
                        )
                        if discharge_approval_extraction.state == "ready":
                            extracted_candidates = tuple(
                                (source_key, row, row_time, assertion)
                                for (source_key, row, row_time, _text), assertion
                                in zip(
                                    semantic_candidates,
                                    discharge_approval_extraction.assertions,
                                )
                            )
                            semantic_match = next(
                                (
                                    (source_key, "senior_approval", row)
                                    for source_key, row, row_time, assertion
                                    in extracted_candidates
                                    if row_time is not None
                                    and assertion.role == "senior"
                                    and assertion.opinion == "approved"
                                    and _has_confirmed_discharge_approval(
                                        assertion.quote
                                    )
                                ),
                                None,
                            )
                            # 模型称已同意但身份或引文未能确认时，不能确认“缺意见”；
                            # 其余（未知、附条件、拒绝、患者要求）均不构成明确上级同意。
                            approval_unresolved = any(
                                row_time is not None
                                and assertion.opinion == "approved"
                                and (
                                    (
                                        assertion.role == "unknown"
                                        and not _is_dated_discharge_plan_only(assertion.quote)
                                    )
                                    or (
                                        assertion.role == "senior"
                                        and not _has_confirmed_discharge_approval(assertion.quote)
                                    )
                                )
                                for _source_key, _row, row_time, assertion in extracted_candidates
                            )
                            semantic_undated = tuple(
                                (source_key, row)
                                for source_key, row, row_time, assertion
                                in extracted_candidates
                                if row_time is None
                                and assertion.role == "senior"
                                and assertion.opinion == "approved"
                                and _has_confirmed_discharge_approval(
                                    assertion.quote
                                )
                            )
                            if semantic_match is not None:
                                approval_match = semantic_match
                                present = True
                            elif semantic_undated:
                                undated_approvals = (
                                    *undated_approvals,
                                    *(
                                        candidate
                                        for candidate in semantic_undated
                                        if all(
                                            candidate[1] is not existing[1]
                                            for existing in undated_approvals
                                        )
                                    ),
                                )
                        elif discharge_approval_extraction.state == "technical_error":
                            final_state = "technical_error"
                            reason_code = discharge_approval_extraction.reason_code
                            approval_resolution_blocked = True
                        else:
                            final_state = "data_gap"
                            reason_code = discharge_approval_extraction.reason_code
                            approval_resolution_blocked = True
                if approval_resolution_blocked:
                    pass
                elif approval_match is None and undated_approvals:
                    final_state, reason_code = "data_gap", "authoritative_time_missing"
                    selected_course_document_ids = tuple(
                        (source_key, document_id)
                        for source_key, row in undated_approvals
                        if (document_id := _clean(row.get("document_id") or row.get("id")))
                    )
                    display.append((rule_id, {
                        "failure_kind": "senior_discharge_approval_time_missing",
                        "discharge_date": discharge_time.date().isoformat(),
                        "checked_dates": tuple(sorted(item.isoformat() for item in valid_dates)),
                        "missing_time_count": len(undated_approvals),
                    }))
                else:
                    # 院方口径（2026-10-10）：出院当天或前一天已有病程记录却无上级医师
                    # 同意出院意见判不合规；窗口内无病程时仍资料不足（缺病程由 067 报告）。
                    window_course_count = sum(
                        1
                        for rows in (daily_rows, senior_rows)
                        for row in rows
                        if _row_time(row) is not None and _row_time(row).date() in valid_dates
                    )
                    if present:
                        final_state, reason_code = "compliant", "requirement_satisfied"
                    elif window_course_count and approval_unresolved:
                        window_course_count = 0
                        final_state, reason_code = "data_gap", "semantic_extraction_unresolved"
                    elif window_course_count:
                        final_state, reason_code = "non_compliant", "requirement_violated"
                        # 证据为窗口内实际核对过的病程文书。
                        selected_course_document_ids = tuple(
                            (source_key, document_id)
                            for source_key, rows in (
                                ("daily_course_record", daily_rows),
                                ("senior_course_record", senior_rows),
                            )
                            for row in rows
                            if _row_time(row) is not None
                            and _row_time(row).date() in valid_dates
                            and (document_id := _clean(row.get("document_id") or row.get("id")))
                        )
                    else:
                        final_state, reason_code = "data_gap", "source_empty"
                    render_display = True
                if render_display:
                    approval_facts: dict[str, Any] = {}
                    if approval_match is not None:
                        approval_facts["approval_path"] = approval_match[1]
                        document_id = _clean(
                            approval_match[2].get("document_id")
                            or approval_match[2].get("id")
                        )
                        if document_id:
                            selected_course_document_ids = (
                                (approval_match[0], document_id),
                            )
                    display.append(
                        (
                            rule_id,
                            {
                                (
                                    "verification_kind"
                                    if present
                                    else "failure_kind"
                                ): (
                                    "senior_discharge_approval_present"
                                    if present
                                    else "senior_discharge_approval_missing"
                                ),
                                "discharge_date": discharge_time.date().isoformat(),
                                "checked_dates": tuple(
                                    sorted(item.isoformat() for item in valid_dates)
                                ),
                                "checked_source": (
                                    approval_match[0]
                                    if approval_match is not None
                                    else "daily_course_record,senior_course_record"
                                ),
                                "approval_present": present,
                                **approval_facts,
                                **(
                                    {"window_course_count": window_course_count}
                                    if not present and window_course_count
                                    else {}
                                ),
                            },
                        )
                    )
            selected_document_refs = _selected_course_document_refs(
                snapshot=evidence_snapshot,
                materials=evidence_materials,
                selected_document_ids=selected_course_document_ids,
            )
            if final_state == "compliant" and approval_match is not None:
                consumed_source_keys = (approval_match[0],)
            elif final_state == "not_applicable":
                consumed_source_keys = ("inpat_registration", "discharge_record")
            elif final_state == "non_compliant":
                consumed_source_keys = ("daily_course_record", "senior_course_record")
            else:
                consumed_source_keys = ()
            decisions.append(
                _decision(
                    rule_id=rule_id,
                    snapshot=evidence_snapshot,
                    source_keys=(
                        "inpat_registration",
                        "discharge_record",
                        "daily_course_record",
                        "senior_course_record",
                    ),
                    final_state=final_state,
                    reason_code=reason_code,
                    document_refs=_selected_course_or_consumed_source_refs(
                        snapshot=evidence_snapshot,
                        selected_document_refs=selected_document_refs,
                        consumed_source_keys=consumed_source_keys,
                    ),
                    exact_document_refs=True,
                )
            )
            continue

        if rule_id == "LX0609-04-02-07":
            outcome = evaluate_consultation_timeliness(
                consultation_rows=consultation_rows,
                consultation_error=consultation_error,
            )
            if outcome.display_facts is not None:
                display.append((rule_id, outcome.display_facts))
            consultation_binding = bind_consultation_evidence(
                snapshot=evidence_snapshot,
                materials=evidence_materials,
                consultation_rows=consultation_rows,
                display_facts=outcome.display_facts,
                consumed_document_rows=outcome.consumed_document_rows,
            )
            decisions.append(
                _decision(
                    rule_id=rule_id,
                    snapshot=evidence_snapshot,
                    source_keys=(
                        ()
                        if consultation_binding.document_refs
                        else ("consultation_record",)
                    ),
                    document_refs=consultation_binding.document_refs,
                    exact_document_refs=bool(consultation_binding.document_refs),
                    final_state=(
                        "technical_error"
                        if consultation_binding.binding_failed
                        else outcome.final_state
                    ),
                    reason_code=(
                        "snapshot_mismatch"
                        if consultation_binding.binding_failed
                        else outcome.reason_code
                    ),
                )
            )
            continue

        if rule_id == "LX0609-10-01-01":
            outcome = evaluate_physician_handoff(
                physician_change_rows=physician_change_rows,
                physician_change_error=physician_change_error,
                nondrug_order_rows=nondrug_order_rows,
                nondrug_order_error=nondrug_order_error,
                daily_course_rows=daily_rows,
                daily_course_error=daily_error,
                handoff_rows=handoff_rows,
                handoff_error=handoff_error,
                handover_rows=handover_rows,
                handover_error=handover_error,
            )
            if outcome.display_facts is not None:
                display.append((rule_id, outcome.display_facts))
            handoff_binding = bind_handoff_evidence(
                snapshot=evidence_snapshot,
                materials=evidence_materials,
                handoff_rows=handoff_rows,
                handover_rows=handover_rows,
                display_facts=outcome.display_facts,
                daily_course_rows=daily_rows,
            )
            decisions.append(
                _decision(
                    rule_id=rule_id,
                    snapshot=evidence_snapshot,
                    source_keys=(
                        (outcome.change_source_key,)
                    ),
                    document_refs=handoff_binding.document_refs,
                    # physician_change_event 尚未纳入客户文书投影白名单。保留它的
                    # snapshot 判定锚点，并只让已匹配的交/接班文书进入公共证据；
                    # 兼容字段待后续结构提交统一删除。
                    exact_document_refs=False,
                    final_state=(
                        "technical_error"
                        if handoff_binding.binding_failed
                        else outcome.final_state
                    ),
                    reason_code=(
                        "snapshot_mismatch"
                        if handoff_binding.binding_failed
                        else outcome.reason_code
                    ),
                )
            )
            continue

        if rule_id in {"LX0609-10-02-01", "LX0609-10-02-02"}:
            outcome = evaluate_transfer_documentation(
                rule_id=rule_id,
                nondrug_order_error=nondrug_order_error,
                transfer_in_error=transfer_in_error,
                transfer_out_error=transfer_out_error,
                nondrug_order_rows=nondrug_order_rows,
                transfer_in_rows=transfer_in_rows,
                transfer_out_rows=transfer_out_rows,
                evaluation_horizon_date=transfer_horizon_date,
                evaluation_horizon_datetime=transfer_horizon_datetime,
                evaluation_horizon_error=transfer_horizon_error,
            )
            final_state, reason_code = outcome.final_state, outcome.reason_code
            if outcome.display_facts is not None:
                display.append((rule_id, outcome.display_facts))
            transfer_binding = bind_transfer_evidence(
                snapshot=evidence_snapshot,
                materials=evidence_materials,
                nondrug_order_rows=nondrug_order_rows,
                transfer_in_rows=transfer_in_rows,
                transfer_out_rows=transfer_out_rows,
                display_facts=outcome.display_facts,
            )
            decisions.append(
                _decision(
                    rule_id=rule_id,
                    snapshot=evidence_snapshot,
                    source_keys=(
                        () if transfer_binding.document_refs else ("inpat_nondrug_order",)
                    ),
                    document_refs=transfer_binding.document_refs,
                    exact_document_refs=bool(transfer_binding.document_refs),
                    final_state=(
                        "technical_error"
                        if transfer_binding.binding_failed
                        else final_state
                    ),
                    reason_code=(
                        "snapshot_mismatch"
                        if transfer_binding.binding_failed
                        else reason_code
                    ),
                )
            )
            continue

        if rule_id == "LX0609-12-02-01":
            if not diagnosis_rows:
                course_event_rows = tuple(
                    (_row_text(row), source_key, row)
                    for source_key, source_rows in (
                        ("daily_course_record", daily_rows),
                        ("senior_course_record", senior_rows),
                    )
                    for row in source_rows
                    if _has_explicit_diagnosis_change_event(_row_text(row))
                )
                # 触发条件不成立时，判定引用的来源快照就是两条完整可读的
                # 声明通道；病程事件驱动的分支自行绑定逐行文书引用，其余
                # 资料缺口分支维持空的来源引用集合。
                decision_source_keys: tuple[str, ...] = ()
                if diagnosis_error:
                    final_state, reason_code = "data_gap", diagnosis_error
                elif daily_error or senior_error:
                    final_state, reason_code = (
                        "data_gap",
                        daily_error or senior_error,
                    )
                elif admission_diagnosis_error:
                    # 结构化变更声明的来源不可读或截断时不能断言“未发生变更”。
                    final_state, reason_code = (
                        "data_gap",
                        admission_diagnosis_error,
                    )
                elif not course_event_rows:
                    # 入院记录诊断显式声明了修正/补充诊断时，变更已经发生；
                    # 后续只按同一理由/依据门禁判断是否记录了事由。
                    declared_diagnosis_names = _diagnosis_change_declarations(
                        admission_diagnosis_rows
                    )
                    if not declared_diagnosis_names:
                        # 074 的触发条件只能由“观察到”修正/补充诊断的显式声明
                        # 成立，它有两条并列且都完整可读的声明通道：病程正文
                        # 变更表述（上面的 course_event_rows）与入院记录诊断的
                        # 结构化变更声明栏。两条通道都无声明即为完整输入上的
                        # 确定性否定，触发条件不成立，而不是资料缺口；来源
                        # 不可读/截断已在上方 admission_diagnosis_error 分支
                        # fail-closed 保持 data_gap。
                        final_state, reason_code = (
                            "not_applicable",
                            "trigger_absent_complete",
                        )
                        # 两条通道的读取证据：diagnosis 表与入院记录诊断声明栏
                        # 均已完整读取且无声明。绑定为最终判定的 fact_refs 是
                        # 公共绑定层对 not_applicable 的既有合同要求（见
                        # decision_binding._requires_evidence_ref）；它们不是
                        # 文书坐标，客户证据投影对 trigger_absent_complete 保持
                        # 空定位。
                        decision_source_keys = (
                            "diagnosis",
                            "admission_record_diagnosis",
                        )
                    else:
                        declaration_rows = tuple(
                            row
                            for row in admission_diagnosis_rows
                            if _clean(row.get("diagnosis_type"))
                            in _ADMISSION_DIAGNOSIS_CHANGE_TYPES
                            and _normalized_admission_diagnosis_name(
                                row.get("diagnosis_name")
                            )
                            and _clean(row.get("document_id") or row.get("id"))
                        )
                        course_sources = (
                            ("daily_course_record", daily_rows),
                            ("senior_course_record", senior_rows),
                        )
                        declared_candidates = {
                            name: _diagnosis_change_candidates(
                                course_sources, diagnosis_name=name,
                            )[:_DIAGNOSIS_CHANGE_CANDIDATES_PER_CHANGE]
                            for name in declared_diagnosis_names
                        }
                        structured_pairs = tuple(
                            (source_key, row, text, name)
                            for name, candidates in declared_candidates.items()
                            for _time, text, source_key, row in candidates
                        )
                        if not all(declared_candidates.values()):
                            # 有声明的变更诊断在病程中从未提及：确定未记录理由与依据。
                            final_state, reason_code = (
                                "non_compliant",
                                "requirement_violated",
                            )
                            structured_facts = {
                                "verification_kind": "diagnosis_change_documentation_check",
                                "diagnosis_change_count": len(declared_diagnosis_names),
                                "reason_recorded": False,
                                "basis_recorded": False,
                            }
                        else:
                            (
                                final_state,
                                reason_code,
                                structured_facts,
                                diagnosis_change_extraction,
                            ) = await _assess_diagnosis_change_documentation(
                                structured_pairs, declared_diagnosis_names, llm_client,
                            )
                        if structured_facts is not None:
                            display.append((rule_id, structured_facts))
                        consumed_course_rows: list[tuple[str, Mapping[str, Any]]] = []
                        for source_key, row, _text, _name in structured_pairs:
                            if not any(row is seen for _key, seen in consumed_course_rows):
                                consumed_course_rows.append((source_key, row))
                        structured_binding = bind_consumed_continuity_document_rows(
                            snapshot=evidence_snapshot,
                            materials=evidence_materials,
                            consumed_rows=tuple(
                                ("admission_record_diagnosis", row)
                                for row in declaration_rows
                            )
                            + tuple(consumed_course_rows),
                        )
                        decisions.append(
                            _decision(
                                rule_id=rule_id,
                                snapshot=evidence_snapshot,
                                source_keys=(
                                    ()
                                    if structured_binding.document_refs
                                    else ("admission_record_diagnosis",)
                                ),
                                document_refs=structured_binding.document_refs,
                                exact_document_refs=bool(
                                    structured_binding.document_refs
                                ),
                                final_state=(
                                    "technical_error"
                                    if structured_binding.binding_failed
                                    else final_state
                                ),
                                reason_code=(
                                    "snapshot_mismatch"
                                    if structured_binding.binding_failed
                                    else reason_code
                                ),
                            )
                        )
                        continue
                else:
                    event_times = tuple(
                        _parse_datetime(authoritative_document_time_value(row))
                        for _text, _source_key, row in course_event_rows
                    )
                    if any(value is None for value in event_times):
                        final_state, reason_code = (
                            "data_gap",
                            "authoritative_time_missing",
                        )
                        display.append((rule_id, {
                            "failure_kind": "diagnosis_change_documentation_time_missing",
                            "diagnosis_change_count": len(course_event_rows),
                            "untimed_document_count": sum(
                                value is None for value in event_times
                            ),
                            "issue": "candidate_document_time_missing",
                        }))
                    else:
                        diagnosis_change_extraction = (
                            await extract_diagnosis_change_documentation(
                                tuple(
                                    DiagnosisChangeDocumentInput(
                                        local_doc_id=f"doc_{index:02d}",
                                        source_type=source_key,
                                        text=text,
                                    )
                                    for index, (text, source_key, _row) in enumerate(
                                        course_event_rows, 1
                                    )
                                ),
                                llm_client,
                            )
                        )
                        if diagnosis_change_extraction.state != "ready":
                            final_state = diagnosis_change_extraction.state
                            reason_code = diagnosis_change_extraction.reason_code
                        else:
                            assertion_states = tuple(
                                state
                                for assertion in diagnosis_change_extraction.assertions
                                for state in (
                                    assertion.reason_state,
                                    assertion.basis_state,
                                )
                            )
                            if "missing" in assertion_states:
                                final_state, reason_code = (
                                    "non_compliant",
                                    "requirement_violated",
                                )
                            elif "unknown" in assertion_states:
                                final_state, reason_code = (
                                    "uncertain",
                                    "semantic_low_confidence",
                                )
                            else:
                                final_state, reason_code = (
                                    "compliant",
                                    "requirement_satisfied",
                                )
                            if final_state in {"compliant", "non_compliant"}:
                                display.append((rule_id, {
                                    "verification_kind": "diagnosis_change_documentation_check",
                                    "diagnosis_change_count": len(course_event_rows),
                                    "reason_recorded": all(
                                        item.reason_state == "present"
                                        for item in diagnosis_change_extraction.assertions
                                    ),
                                    "basis_recorded": all(
                                        item.basis_state == "present"
                                        for item in diagnosis_change_extraction.assertions
                                    ),
                                }))
                course_binding = bind_consumed_continuity_document_rows(
                    snapshot=evidence_snapshot,
                    materials=evidence_materials,
                    consumed_rows=tuple(
                        (source_key, row)
                        for _text, source_key, row in course_event_rows
                    ),
                )
                decisions.append(
                    _decision(
                        rule_id=rule_id,
                        snapshot=evidence_snapshot,
                        source_keys=(
                            decision_source_keys
                            if final_state == "not_applicable"
                            else ()
                        ),
                        document_refs=course_binding.document_refs,
                        exact_document_refs=bool(course_event_rows),
                        final_state=(
                            "technical_error"
                            if course_binding.binding_failed
                            else final_state
                        ),
                        reason_code=(
                            "snapshot_mismatch"
                            if course_binding.binding_failed
                            else reason_code
                        ),
                    )
                )
                continue
            change_events: list[tuple[datetime, str, Mapping[str, Any]]] = []
            candidate_rows: tuple[
                tuple[datetime | None, str, str, Mapping[str, Any]], ...
            ] = ()
            if diagnosis_error or daily_error or senior_error:
                final_state, reason_code = (
                    "data_gap",
                    diagnosis_error or daily_error or senior_error,
                )
            else:
                diagnoses_by_slot: dict[
                    tuple[str, str], list[tuple[datetime, str, Mapping[str, Any]]]
                ] = {}
                invalid_reason: str | None = None
                association_issue: str | None = None
                for row in diagnosis_rows:
                    diagnosis_time = _parse_datetime(row.get("diagnosis_datetime"))
                    diagnosis_name = _clean(row.get("diagnosis_name"))
                    diagnosis_type = _clean(row.get("diagnosis_type")).casefold()
                    diagnosis_no = _clean(row.get("diagnosis_no")).casefold()
                    if diagnosis_time is None or not diagnosis_name:
                        invalid_reason = "authoritative_time_missing"
                        break
                    if not diagnosis_type or not diagnosis_no:
                        invalid_reason = "association_failed"
                        association_issue = "slot_missing"
                        break
                    diagnoses_by_slot.setdefault(
                        (diagnosis_type, diagnosis_no), []
                    ).append((diagnosis_time, diagnosis_name, row))

                if invalid_reason is None:
                    for slot_diagnoses in diagnoses_by_slot.values():
                        names_by_time: dict[datetime, set[str]] = {}
                        for diagnosis_time, diagnosis_name, _row in slot_diagnoses:
                            names_by_time.setdefault(diagnosis_time, set()).add(diagnosis_name)
                        if any(len(names) > 1 for names in names_by_time.values()):
                            invalid_reason = "association_failed"
                            association_issue = "same_time_conflict"
                            break
                        ordered_diagnoses = sorted(
                            (
                                (
                                    diagnosis_time,
                                    next(iter(names)),
                                    next(
                                        row
                                        for candidate_time, candidate_name, row
                                        in slot_diagnoses
                                        if candidate_time == diagnosis_time
                                        and candidate_name in names
                                    ),
                                )
                                for diagnosis_time, names in names_by_time.items()
                            ),
                            key=lambda item: item[0],
                        )
                        change_events.extend(
                            (current_time, current_name, current_row)
                            for (_, previous_name, _), (current_time, current_name, current_row) in zip(
                                ordered_diagnoses, ordered_diagnoses[1:]
                            )
                            if current_name != previous_name
                        )

                if invalid_reason is not None:
                    final_state, reason_code = "data_gap", invalid_reason
                    if invalid_reason == "association_failed":
                        display.append((rule_id, {
                            "failure_kind": "diagnosis_change_association_failed",
                            "diagnosis_record_count": len(diagnosis_rows),
                            "diagnosis_change_count": len(change_events),
                            "association_issue": association_issue,
                        }))
                elif not change_events:
                    final_state, reason_code = (
                        "not_applicable",
                        "trigger_absent_complete",
                    )
                else:
                    course_sources = (
                        ("daily_course_record", daily_rows),
                        ("senior_course_record", senior_rows),
                    )
                    change_names = tuple(dict.fromkeys(name for _time, name, _row in change_events))
                    selected: list[tuple[datetime | None, str, str, Mapping[str, Any]]] = []
                    table_pairs: list[tuple[str, Mapping[str, Any], str, str]] = []
                    untimed_only = False
                    unmentioned = False
                    for change_time, diagnosis_name, _change_row in change_events:
                        mentions = _diagnosis_change_candidates(
                            course_sources, diagnosis_name=diagnosis_name,
                        )
                        candidates = tuple(
                            item for item in mentions if item[0] is None or item[0] >= change_time
                        )
                        # 名称、理由与依据必须属于变更之后的同一条病程，不借用其他诊断的时间。
                        timed = tuple(item for item in candidates if item[0] is not None)
                        timed = timed[:_DIAGNOSIS_CHANGE_CANDIDATES_PER_CHANGE]
                        if timed:
                            table_pairs.extend(
                                (source_key, row, text, diagnosis_name)
                                for _time, text, source_key, row in timed
                            )
                            selected.extend(
                                item for item in timed
                                if not any(item[3] is seen[3] for seen in selected)
                            )
                        elif candidates:
                            untimed_only = True
                            selected.extend(candidates)
                        else:
                            unmentioned = True
                            # 仅有变更之前的提及：不能证明本次变更的理由，作为不合规证据展示。
                            selected.extend(mentions)
                    candidate_rows = tuple(selected)
                    if unmentioned:
                        # 变更后诊断在变更之后的病程中从未提及：确定未记录理由与依据。
                        final_state, reason_code = (
                            "non_compliant",
                            "requirement_violated",
                        )
                        display.append((rule_id, {
                            "verification_kind": "diagnosis_change_documentation_check",
                            "diagnosis_change_count": len(change_events),
                            "reason_recorded": False,
                            "basis_recorded": False,
                        }))
                    elif untimed_only:
                        final_state, reason_code = (
                            "data_gap",
                            "authoritative_time_missing",
                        )
                        display.append((rule_id, {
                            "failure_kind": "diagnosis_change_documentation_time_missing",
                            "diagnosis_change_count": len(change_events),
                            "untimed_document_count": sum(item[0] is None for item in candidate_rows),
                            "issue": "candidate_document_time_missing",
                        }))
                    else:
                        (
                            final_state,
                            reason_code,
                            table_facts,
                            diagnosis_change_extraction,
                        ) = await _assess_diagnosis_change_documentation(
                            table_pairs, change_names, llm_client,
                        )
                        if table_facts is not None:
                            display.append((rule_id, table_facts))
            diagnosis_binding = bind_consumed_continuity_document_rows(
                snapshot=evidence_snapshot,
                materials=evidence_materials,
                consumed_rows=tuple(
                    ("diagnosis", row) for _time, _name, row in change_events
                )
                + tuple(
                    (source_key, row)
                    for _time, _text, source_key, row in candidate_rows
                ),
            )
            decisions.append(
                _decision(
                    rule_id=rule_id,
                    snapshot=evidence_snapshot,
                    source_keys=(
                        ()
                        if diagnosis_binding.document_refs
                        else ("diagnosis",)
                    ),
                    document_refs=diagnosis_binding.document_refs,
                    exact_document_refs=bool(diagnosis_binding.document_refs),
                    final_state=(
                        "technical_error"
                        if diagnosis_binding.binding_failed
                        else final_state
                    ),
                    reason_code=(
                        "snapshot_mismatch"
                        if diagnosis_binding.binding_failed
                        else reason_code
                    ),
                )
            )
            continue

        decisions.append(
            _decision(
                rule_id=rule_id,
                snapshot=evidence_snapshot,
                source_keys=EXTENDED_DOCUMENT_SOURCE_KEYS,
                final_state="data_gap",
                reason_code="source_readiness_unproven",
            )
        )

    if postoperative_time_estimated_rules:
        display = [
            (rule_id, {**facts, "surgery_time_basis": "begin_time"})
            if rule_id in postoperative_time_estimated_rules and isinstance(facts, Mapping)
            else (rule_id, facts)
            for rule_id, facts in display
        ]
    return NativeExtendedDocumentExecutionResult(
        results=(),
        planned_rule_ids=selected,
        decisions=tuple(decisions),
        customer_display_facts=tuple(display),
        llm_call_count=sum(
            item.llm_call_count
            for item in (
                course_content_extraction,
                antimicrobial_action_extraction,
                antimicrobial_order_reason_extraction,
                special_approval_extraction,
                antimicrobial_effect_extraction,
                diagnosis_scope_extraction,
                diagnosis_equivalence_extraction,
                medication_extraction,
                discharge_approval_extraction,
                diagnosis_change_extraction,
                transfusion_performance_extraction,
                transfusion_course_extraction,
                *course_body_extractions,
                *other_medication_extractions,
                *invasive_extractions,
            )
            if item is not None
        ),
        prompt_tokens=sum(
            item.prompt_tokens
            for item in (
                course_content_extraction,
                antimicrobial_action_extraction,
                antimicrobial_order_reason_extraction,
                special_approval_extraction,
                antimicrobial_effect_extraction,
                diagnosis_scope_extraction,
                diagnosis_equivalence_extraction,
                medication_extraction,
                discharge_approval_extraction,
                diagnosis_change_extraction,
                transfusion_performance_extraction,
                transfusion_course_extraction,
                *course_body_extractions,
                *other_medication_extractions,
                *invasive_extractions,
            )
            if item is not None
        ),
        completion_tokens=sum(
            item.completion_tokens
            for item in (
                course_content_extraction,
                antimicrobial_action_extraction,
                antimicrobial_order_reason_extraction,
                special_approval_extraction,
                antimicrobial_effect_extraction,
                diagnosis_scope_extraction,
                diagnosis_equivalence_extraction,
                medication_extraction,
                discharge_approval_extraction,
                diagnosis_change_extraction,
                transfusion_performance_extraction,
                transfusion_course_extraction,
                *course_body_extractions,
                *other_medication_extractions,
                *invasive_extractions,
            )
            if item is not None
        ),
        total_tokens=sum(
            item.total_tokens
            for item in (
                course_content_extraction,
                antimicrobial_action_extraction,
                antimicrobial_order_reason_extraction,
                special_approval_extraction,
                antimicrobial_effect_extraction,
                diagnosis_scope_extraction,
                diagnosis_equivalence_extraction,
                medication_extraction,
                discharge_approval_extraction,
                diagnosis_change_extraction,
                transfusion_performance_extraction,
                transfusion_course_extraction,
                *course_body_extractions,
                *other_medication_extractions,
                *invasive_extractions,
            )
            if item is not None
        ),
        api_time=sum(
            item.api_time
            for item in (
                course_content_extraction,
                antimicrobial_action_extraction,
                antimicrobial_order_reason_extraction,
                special_approval_extraction,
                antimicrobial_effect_extraction,
                diagnosis_scope_extraction,
                diagnosis_equivalence_extraction,
                medication_extraction,
                discharge_approval_extraction,
                diagnosis_change_extraction,
                transfusion_performance_extraction,
                transfusion_course_extraction,
                *course_body_extractions,
                *other_medication_extractions,
                *invasive_extractions,
            )
            if item is not None
        ),
    )
