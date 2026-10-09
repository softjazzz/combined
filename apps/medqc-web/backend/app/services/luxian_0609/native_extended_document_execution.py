"""第一阶段新增的确定性文书规则。

本执行器只消费同一个 Evidence Snapshot/Material Store，不调用旧四川规则，
也不从自由文本结论反推状态。
"""

from __future__ import annotations

import re
from dataclasses import dataclass
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
    bind_diagnosis_change_evidence,
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
from .extended_document.diagnosis_change_extraction import (
    DiagnosisChangeDocumentInput,
    extract_diagnosis_change_documentation,
)
from .extended_document.antimicrobial_action_extraction import (
    ANTIMICROBIAL_CONTEXT_MARKERS as _ANTIMICROBIAL_EFFECT_CONTEXT_MARKERS,
    SPECIAL_ANTIMICROBIALS as _SPECIAL_ANTIMICROBIALS,
    AntimicrobialOrderEvent as _AntimicrobialOrderEvent,
    antimicrobial_names_in as _antimicrobial_names_in,
    antimicrobial_names_in_rows as _antimicrobial_names_in_rows,
    build_antimicrobial_order_events as _antimicrobial_order_events,
    extract_confirmed_antimicrobial_actions,
    linked_order_id as _linked_order_id,
)
from .extended_document.antimicrobial_effect_extraction import extract_antimicrobial_effects
from .extended_document.transfusion_performance_extraction import extract_transfusion_performance
from .extended_document.physician_handoff import evaluate_physician_handoff
from .extended_document.rule_076 import evaluate_rule_076
from .extended_document.shared import _clean, _parse_datetime, _row_time
from .extended_document.discharge_medication_extraction import extract_discharge_medications
from .extended_document.discharge_approval_extraction import (
    DischargeApprovalInput,
    extract_discharge_approval,
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
_DIAGNOSIS_CHANGE_EVENT_PATTERN = re.compile(
    r"(?:修正诊断|补充诊断)\s*(?:为|[:：])\s*"
    r"[^\s，,。；;：:！？!?][^，,。；;\r\n]*"
)
_DIAGNOSIS_CHANGE_NON_EVENT_PREFIX_PATTERN = re.compile(
    r"(?:暂不|无需|不需|不必|不予|未予|未作|若需|如需|是否|应记录|应当记录).{0,8}$"
)
_ADMISSION_DIAGNOSIS_CHANGE_TYPES = frozenset({"修正诊断", "补充诊断"})
# 客户入院记录诊断把签名与记录时间拼在诊断名尾部；解析“变更后诊断名”时
# 必须剥离，否则同条关联判据永远匹配不上病程正文。
_ADMISSION_DIAGNOSIS_LABEL_PATTERN = re.compile(
    r"(?:医师签名|医生签名|签名|记录时间|记录日期|记录者|签名日期|日期|时间)\s*[:：]"
)
_ADMISSION_DIAGNOSIS_TIME_PATTERN = re.compile(
    r"\d{4}[-/年]\d{1,2}(?:[-/月]\d{1,2}日?)?"
    r"(?:[ T]?\d{1,2}[:：]\d{1,2}(?:[:：]\d{1,2})?)?"
)
# 074 的唯一理由/依据标记门禁：新旧两条触发路径共用，禁止把普通病程直接
# 送受控抽取器。
_DIAGNOSIS_CHANGE_REASON_MARKERS = (
    "修正诊断",
    "补充诊断",
    "修改理由",
)
_DIAGNOSIS_CHANGE_BASIS_MARKERS = ("诊断依据", "依据为", "依据：", "依据:")
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
)
_SPECIAL_ANTIMICROBIAL_EXPERT_SUPPORT_MARKERS = (
    "感染专家", "专家会诊", "专家查房", "同意特殊级",
)
_SPECIAL_ANTIMICROBIAL_EXPERT_SUPPORT_NEGATED_PATTERN = re.compile(
    r"(?:拒绝|不同意|未(?:行|完成|进行)|尚未|无).{0,12}"
    r"(?:感染专家|专家会诊|专家查房|会诊意见)|"
    r"(?:感染专家|专家会诊|专家查房|会诊意见).{0,12}"
    r"(?:未(?:行|完成|进行)|尚未|缺失|不存在|无)",
)
_LX0609_HOSPITAL_TIMEZONE = ZoneInfo("Asia/Shanghai")
_INVASIVE_PROCEDURES = (
    "中心静脉置管", "胸腔穿刺", "腹腔穿刺", "腰椎穿刺",
    "气管插管", "支气管镜", "动脉置管",
)
_DISCHARGE_APPROVAL_PATTERN = re.compile(
    r"(?:同意|批准|准许|准予)(?:患者|其)?(?:于|拟于)?"
    r"(?:今日|明日|次日)?(?:安排|办理)?出院"
    r"|(?:可以|可)(?:患者|其)?(?:于|拟于)?"
    r"(?:今日|明日|次日)?(?:安排|办理|予以)?出院"
    r"|(?:建议|予以)(?:患者|其)?(?:于|拟于)?"
    r"(?:今日|明日|次日)?(?:安排|办理)?出院"
    r"|(?<!拟)(?<!计划)(?<!准备)于今日(?:办理)?出院"
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
    r"|(?:拟|计划|准备|考虑).{0,12}于今日(?:办理)?出院"
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
    r"(?:签署|签订|签字|签)[《\"“]?自动出院(?:书|协议|知情同意书)[》\"”]?"
)
_AUTOMATIC_DISCHARGE_UNSIGNED_PATTERN = re.compile(
    r"(?:未|未予|尚未|拒绝|拒不).{0,8}"
    r"(?:签署|签订|签字|签)[《\"“]?自动出院(?:书|协议|知情同意书)"
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

    approval = _confirmed_discharge_approval_match(text)
    if approval is None:
        return None
    local_context = text[max(0, approval.start() - 80): approval.end() + 40]
    author_title = _clean(row.get("author_title"))
    if (
        source_key == "senior_course_record"
        or _SENIOR_PHYSICIAN_REFERENCE_PATTERN.search(local_context)
        or _SENIOR_PHYSICIAN_REFERENCE_PATTERN.search(author_title)
    ):
        return "senior_approval"
    return None


def _confirmed_discharge_approval_match(text: str) -> re.Match[str] | None:
    """返回未被否定或条件短语约束的明确出院处置。"""

    value = str(text or "")
    for approval in _DISCHARGE_APPROVAL_PATTERN.finditer(value):
        local_start = max(0, approval.start() - 80)
        local_context = value[local_start: approval.end() + 40]
        is_bound_to_negation = any(
            local_start + negated.start() < approval.end()
            and local_start + negated.end() > approval.start()
            for negated in _DISCHARGE_APPROVAL_NEGATED_PATTERN.finditer(local_context)
        )
        if not is_bound_to_negation:
            return approval
    return None


def _has_confirmed_discharge_approval(text: str) -> bool:
    """模型的 approved 枚举也必须通过同一明确处置合同。"""

    return _confirmed_discharge_approval_match(text) is not None


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
        bloodtrans_record_rows = materials.document_rows(
            "bloodtrans_record", snapshot=snapshot
        )
        if not include_pretransfusion_materials:
            # 没有已确认实施事件时未核对九项，只引用实际用于抽取的专用资料。
            return tuple(dict.fromkeys(
                reference for reference, row in bloodtrans_record_rows
                if consumed_bloodtrans_rows is None or row in consumed_bloodtrans_rows
            ))
        registration_rows = materials.document_rows(
            "inpat_registration", snapshot=snapshot
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
        if name and name not in declarations:
            declarations.append(name)
    return tuple(declarations)


def _reason_and_basis_candidate_rows(
    rows_by_source: Sequence[tuple[str, Sequence[Mapping[str, Any]]]],
    *,
    changed_diagnosis_names: Sequence[str],
) -> tuple[tuple[datetime | None, str, str, Mapping[str, Any]], ...]:
    """复用 074 旧路径的理由/依据标记门禁，确认病程确实记录了变更事由。"""

    reason_markers = _DIAGNOSIS_CHANGE_REASON_MARKERS
    basis_markers = _DIAGNOSIS_CHANGE_BASIS_MARKERS
    candidates = tuple(
        (_row_time(row), _row_text(row), source_key, row)
        for source_key, source_rows in rows_by_source
        for row in source_rows
        if any(marker in _row_text(row) for marker in reason_markers)
        and any(marker in _row_text(row) for marker in basis_markers)
    )
    return tuple(
        candidate
        for candidate in candidates
        if any(name in candidate[1] for name in changed_diagnosis_names)
    )


def _material_text(row: Mapping[str, Any]) -> str:
    return "\n".join(
        _clean(row.get(key))
        for key in (
            "record_content", "document_title", "order_name", "generic_name",
            "item_code", "item_name", "item_abbreviation", "result",
            "result_flag", "abnormal_flag", "diagnosis_name", "labtest_subject",
            "specimen",
        )
        if _clean(row.get(key))
    )


def _antimicrobial_orders(rows: Sequence[Mapping[str, Any]]) -> tuple[Mapping[str, Any], ...]:
    return tuple(row for row in rows if _antimicrobial_names_in(row))


def _has_performed_antimicrobial_administration(
    text: str, names: Sequence[str],
) -> bool:
    """取消与已实施冲突时保留事件；计划、否定和历史给药不是本次实施。"""

    target = "|".join(re.escape(name) for name in names)
    action = re.compile(
        r"已给予|已使用|已启用|已输注|实际给予|实际使用"
        + (rf"|(?:已予以|予以|已予|给予)(?=\s*(?:{target}))" if target else "")
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
        _has_any_text((row,), _SPECIAL_ANTIMICROBIAL_EXPERT_SUPPORT_MARKERS)
        and not _SPECIAL_ANTIMICROBIAL_EXPERT_SUPPORT_NEGATED_PATTERN.search(text)
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
            if len(candidates) != 1:
                # 病程动作本身不能证明属于本次哪条受控医嘱；不能凭 status 或
                # update_time 补造关联，也不能让其他同名医嘱代为触发。
                association_failed = True
                continue
            events.append(_AntimicrobialReasonAction(
                row=row,
                antimicrobial=antimicrobial,
                action=action,
                order_ids=candidates[0].order_ids,
                orders=candidates[0].orders,
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

    if _054_reason_documented(event.row):
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


def _empiric_antimicrobial_event_contexts(
    *,
    antimicrobial_orders: Sequence[Mapping[str, Any]],
    candidate_rows: Sequence[Mapping[str, Any]],
) -> tuple[tuple[tuple[Mapping[str, Any], _AntimicrobialOrderEvent], ...], bool]:
    """返回可唯一关联的经验用药事件；无法归属具体医嘱时由调用方交付资料缺口。"""

    order_events = _antimicrobial_order_events(antimicrobial_orders)
    contexts: list[tuple[Mapping[str, Any], _AntimicrobialOrderEvent]] = []
    association_ambiguous = False
    for row in candidate_rows:
        if not _is_explicit_empiric_antimicrobial_use(row):
            continue
        linked_order_id = _linked_order_id(row)
        mentioned_names = _antimicrobial_names_in(row)
        if linked_order_id:
            candidates = tuple(
                event
                for event in order_events
                if linked_order_id in event.order_ids
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
        if len(candidates) != 1:
            association_ambiguous = True
            continue
        contexts.append((row, candidates[0]))
    return tuple(contexts), association_ambiguous


def _empiric_reason_documented(
    *,
    event_row: Mapping[str, Any],
    order_event: _AntimicrobialOrderEvent,
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
        if row_order_id and order_ids:
            if row_order_id in order_ids:
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
        "daily_course_record",
        "senior_course_record",
        "consultation_record",
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
    """064/065 的最小事件投影：正式手术记录一行即一台手术。"""

    source_key: str
    row: Mapping[str, Any]
    document_id: str
    surgery_name: str
    surgery_end_time: datetime | None
    surgeon_names: tuple[str, ...]
    surgeon_tokens: frozenset[str]


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
    """病程记录仅从受控的作者或签名字段获取记录医师。"""

    return frozenset(
        token
        for key in (
            "author_name",
            "physician_sign",
            "author_signature",
            "doctor_signature",
        )
        if (token := _normalized_physician_token(row.get(key)))
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
    # 按职称分段提取完整姓名，不能用术者姓名去匹配另一姓名的后缀。
    identities = set()
    for match in re.finditer(
        r"([^，,、；;：:（）()]+?)(?:副主任医师|主任医师|主治医师|住院医师|医师)",
        title_header,
    ):
        identity = match.group(1).strip()
        # 仅剥离有明确边界的联合查房/科室前缀；其余整段保留，不能猜姓名。
        identity = re.sub(
            r"^(?:联合)?(?:神经疾病中心|神经外科|神经内科|心胸外科|"
            r"普通外科|普外科|骨科|眼科|耳鼻喉科|妇产科|儿科|泌尿外科)",
            "",
            identity,
        )
        identities.add(_normalized_physician_token(identity))
    return frozenset(identities.intersection(candidate_tokens))


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
    return tuple(
        _PostoperativeSurgeryEvent(
            source_key=source_key,
            row=row,
            document_id=_clean(row.get("document_id") or row.get("id")) or f"{source_key}:{index}",
            surgery_name=_clean(
                row.get("surgery_name")
                or row.get("operation_name")
                or row.get("procedure_name")
            ),
            surgery_end_time=_actual_surgery_end_time(source_key=source_key, row=row),
            surgeon_names=_surgery_event_surgeon_names(row),
            surgeon_tokens=_surgery_event_surgeon_tokens(row),
        )
        for index, row in enumerate(source_rows, start=1)
    )


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

    if any(event.surgery_end_time is None for event in surgery_events):
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
    discharge_approval_extraction = None
    course_body_extractions: list[CourseBodyExtraction] = []
    diagnosis_change_extraction = None
    antimicrobial_action_extraction = None
    antimicrobial_effect_extraction = None
    diagnosis_scope_extraction = None
    transfusion_performance_extraction = None
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
                scope_rows = tuple(row for row in daily_rows if _row_time(row) is None
                                   or _row_time(row) >= admission_time + timedelta(days=7))
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
                final_state, reason_code = "uncertain", "diagnosis_scope_uncertain"
                scope_resolution = "unknown"
            elif not uncertain_rows:
                final_state, reason_code = "not_applicable", "trigger_absent_complete"
            elif not strong_uncertain_rows:
                final_state, reason_code = "uncertain", "diagnosis_scope_uncertain"
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
            course_rows = (*daily_rows, *senior_rows)
            selected_antimicrobial_evidence_rows: list[Mapping[str, Any]] = list(
                excluded_antimicrobial_evidence
            )
            source_error = drug_order_error or (
                "" if rule_id == "LX0609-05-01-06" else daily_error or senior_error
            )
            if source_error:
                final_state, reason_code = "data_gap", source_error
            elif rule_id == "LX0609-05-01-02":
                antimicrobial_action_extraction = (
                    await extract_confirmed_antimicrobial_actions(
                        course_rows, llm_client
                    )
                )
                confirmed_actions = {
                    (item.row_index, item.antimicrobial): item.action
                    for item in antimicrobial_action_extraction.confirmed_actions
                }
                if antimicrobial_action_extraction.state not in {"ready", "absent"}:
                    final_state = (
                        "technical_error"
                        if antimicrobial_action_extraction.state == "technical_error"
                        else "uncertain"
                    )
                    reason_code = antimicrobial_action_extraction.reason_code
                    display.append((rule_id, {
                        "verification_kind": "antimicrobial_reason_documentation_check",
                        "antimicrobials": list(
                            antimicrobial_action_extraction.semantic_antimicrobials
                        ),
                        "action_count": len(confirmed_actions),
                        "reason_documented": False,
                        "unmatched_antimicrobials": list(
                            antimicrobial_action_extraction.semantic_antimicrobials
                        ),
                        "association_ambiguous": True,
                    }))
                else:
                    (
                        action_events,
                        action_association_failed,
                        mentioned_action_names,
                    ) = _054_action_events(
                        course_rows,
                        antimicrobial_orders,
                        confirmed_actions,
                    )
                    if action_association_failed:
                        final_state, reason_code = "data_gap", "association_failed"
                    elif not action_events:
                        final_state, reason_code = (
                            "not_applicable", "trigger_absent_complete"
                        )
                    else:
                        reason_outcomes = tuple(
                            _054_event_reason_state(
                                event=event,
                                all_events=action_events,
                                course_rows=course_rows,
                            )
                            for event in action_events
                        )
                        event_states = tuple(
                            state for state, _row in reason_outcomes
                        )
                        selected_antimicrobial_evidence_rows.extend(
                            row
                            for event, (_state, reason_row) in zip(
                                action_events, reason_outcomes
                            )
                            for row in (event.row, *event.orders, reason_row)
                            if row is not None
                        )
                        unmatched_names = tuple(dict.fromkeys(
                            event.antimicrobial
                            for event, state in zip(action_events, event_states)
                            if state != "documented"
                        ))
                        association_ambiguous = "ambiguous" in event_states
                        complete = not unmatched_names
                        if association_ambiguous:
                            final_state, reason_code = "data_gap", "association_failed"
                        elif complete:
                            final_state, reason_code = (
                                "compliant", "requirement_satisfied"
                            )
                        else:
                            final_state, reason_code = (
                                "non_compliant", "requirement_violated"
                            )
                        display.append((rule_id, {
                            "verification_kind": "antimicrobial_reason_documentation_check",
                            "antimicrobials": list(dict.fromkeys(
                                event.antimicrobial for event in action_events
                            )),
                            "action_count": len(action_events),
                            "reason_documented": complete,
                            "unmatched_antimicrobials": list(unmatched_names),
                            "association_ambiguous": association_ambiguous,
                        }))
                    if action_association_failed:
                        display.append((rule_id, {
                            "verification_kind": "antimicrobial_reason_documentation_check",
                            "antimicrobials": list(mentioned_action_names),
                            "action_count": len(action_events),
                            "reason_documented": False,
                            "unmatched_antimicrobials": list(mentioned_action_names),
                            "association_ambiguous": True,
                        }))
            elif not rule_antimicrobial_orders:
                final_state, reason_code = "not_applicable", "trigger_absent_complete"
            elif rule_id == "LX0609-05-01-03":
                order_events = tuple(
                    (row, name, _antimicrobial_start_datetime(row))
                    for row in rule_antimicrobial_orders
                    for name in _antimicrobial_names_in(row)
                )
                # 即使评价窗尚未成熟，开始医嘱仍是这项否定结论实际消费的
                # 业务事实；horizon 仅决定窗口状态，绝不成为客户证据。
                selected_antimicrobial_evidence_rows.extend(
                    order
                    for order, _name, start in order_events
                    if start is not None
                )
                event_windows: list[dict[str, Any]] = []
                mature_events: list[tuple[Mapping[str, Any], str, datetime]] = []
                immature_states: list[str] = []
                if any(start is None for _, _, start in order_events):
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
                evaluation_resolution = "ready"
                unassigned_regimen = False
                if not final_state and mature_events:
                    targets = tuple(dict.fromkeys(name for _, name, _ in mature_events))
                    antimicrobial_effect_extraction = await extract_antimicrobial_effects(
                        course_rows, targets, llm_client,
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
                            row = course_rows[assertion.row_index]
                            name = targets[assertion.target_index]
                            if assertion.state == "present":
                                effect_rows_by_name.setdefault(name, []).append(row)
                            elif assertion.state == "regimen":
                                if len(order_events) == 1:
                                    effect_rows_by_name.setdefault(name, []).append(row)
                                else:
                                    unassigned_regimen = True
                            elif assertion.state == "unknown":
                                # 窗外未知不能阻止已成熟事件的窗内评价；缺时仍不可排除。
                                value = _row_time(row)
                                if value is None or any(
                                    event_name == name and 48 <= (value - start).total_seconds() / 3600 <= 72
                                    for _, event_name, start in mature_events
                                ):
                                    final_state, reason_code = "data_gap", "semantic_extraction_unresolved"
                                    evaluation_resolution = "unknown"
                ambiguous_evaluation = unassigned_regimen or any(
                    not _linked_order_id(row)
                    and sum(name == event_name for _, event_name, _ in order_events) > 1
                    for name, rows in effect_rows_by_name.items() for row in rows
                )
                intervals: list[float] = []
                unmatched_names: list[str] = []
                has_untimed_match = False
                if final_state in {"data_gap", "technical_error"}:
                    pass
                elif ambiguous_evaluation:
                    final_state, reason_code = "data_gap", "association_failed"
                else:
                    for order, name, start in mature_events:
                        order_id = _clean(order.get("order_id"))
                        matching_rows = tuple(
                            row for row in effect_rows_by_name.get(name, ())
                            if not _linked_order_id(row)
                            or (bool(order_id) and _linked_order_id(row) == order_id)
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
                        intervals.extend(event_intervals)
                        if not any(48 <= value <= 72 for value in event_intervals):
                            unmatched_names.append(name)
                            has_untimed_match = has_untimed_match or any(
                                _row_time(row) is None for row in matching_rows
                            )
                    if not unmatched_names:
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
                    "evaluation_intervals": [round(value, 2) for value in intervals],
                    "unmatched_antimicrobials": list(dict.fromkeys(unmatched_names)),
                    "association_ambiguous": ambiguous_evaluation,
                    "event_windows": event_windows,
                }
                if final_state == "not_applicable":
                    display_facts["window_state"] = reason_code
                display.append((rule_id, display_facts))
            elif rule_id == "LX0609-05-01-04":
                special_orders = tuple(
                    row for row in antimicrobial_orders
                    if _antimicrobial_names_in(row, _SPECIAL_ANTIMICROBIALS)
                )
                if len(special_orders) < 2:
                    final_state, reason_code = "not_applicable", "trigger_absent_complete"
                elif lab_master_error or lab_item_error:
                    final_state, reason_code = "data_gap", lab_master_error or lab_item_error
                else:
                    special_order_times = tuple(
                        value
                        for row in special_orders
                        if (value := _parse_datetime(row.get("prescribed_datetime")))
                        is not None
                    )
                    first_order = min(special_order_times, default=None)
                    specimen_times = tuple(
                        value
                        for row in lab_master_rows
                        if _has_any_text((row,), ("培养", "药敏", "病原"))
                        and (value := _parse_datetime(row.get("request_datetime") or row.get("sample_datetime")))
                        is not None
                    )
                    if first_order is None:
                        final_state, reason_code = "data_gap", "authoritative_time_missing"
                    else:
                        complete = any(value <= first_order for value in specimen_times)
                        final_state = "compliant" if complete else "non_compliant"
                        reason_code = "requirement_satisfied" if complete else "requirement_violated"
            elif rule_id == "LX0609-05-01-05":
                empiric_contexts, association_ambiguous = (
                    _empiric_antimicrobial_event_contexts(
                        antimicrobial_orders=antimicrobial_orders,
                        candidate_rows=(*antimicrobial_orders, *course_rows),
                    )
                )
                if association_ambiguous:
                    final_state, reason_code = "data_gap", "association_failed"
                elif not empiric_contexts:
                    final_state, reason_code = (
                        "not_applicable", "trigger_absent_complete"
                    )
                else:
                    reason_rows = tuple(
                        _empiric_reason_documented(
                            event_row=event_row,
                            order_event=order_event,
                            course_rows=course_rows,
                        )
                        for event_row, order_event in empiric_contexts
                    )
                    selected_antimicrobial_evidence_rows.extend(
                        row
                        for (event_row, order_event), reason_row in zip(
                            empiric_contexts, reason_rows
                        )
                        for row in (event_row, *order_event.orders, reason_row)
                        if row is not None
                    )
                    complete = all(reason_row is not None for reason_row in reason_rows)
                    final_state = "compliant" if complete else "non_compliant"
                    reason_code = "requirement_satisfied" if complete else "requirement_violated"
                    display.append((rule_id, {
                        "verification_kind": "empiric_antimicrobial_reason_check",
                        "antimicrobials": list(dict.fromkeys(
                            name
                            for _event_row, order_event in empiric_contexts
                            for name in order_event.antimicrobials
                        )),
                        "empiric_use_confirmed": True,
                        "reason_or_no_specimen_documented": complete,
                    }))
            elif rule_id == "LX0609-05-01-06":
                special_events = tuple(
                    (row, name, _parse_lx0609_058_datetime(
                        row.get("planned_start_datetime") or row.get("prescribed_datetime")
                    ))
                    for row in antimicrobial_orders
                    for name in _antimicrobial_names_in(row, _SPECIAL_ANTIMICROBIALS)
                )
                special_names = tuple(dict.fromkeys(
                    name for _, name, _ in special_events
                ))
                selected_antimicrobial_evidence_rows.extend(
                    order for order, _name, _start in special_events
                )
                expert_support_rows = tuple(
                    row
                    for row in (*consultation_rows, *senior_rows)
                    if _is_special_antimicrobial_expert_support(row)
                )
                associated_expert_support_rows: list[Mapping[str, Any]] = []
                first_order_time = min(
                    (start for _, _, start in special_events if start is not None),
                    default=None,
                )
                ambiguous_support = len(special_events) > 1 and any(
                    not _linked_order_id(row)
                    and (
                        not (mentioned := _antimicrobial_names_in(row))
                        or any(
                            sum(name == event_name for _, event_name, _ in special_events) > 1
                            for name in mentioned
                        )
                    )
                    for row in expert_support_rows
                )
                unmatched_names: list[str] = []
                late_support = False
                untimed_support = False
                if not special_events:
                    final_state, reason_code = "not_applicable", "trigger_absent_complete"
                elif any(start is None for _, _, start in special_events):
                    final_state, reason_code = "data_gap", "authoritative_time_missing"
                elif ambiguous_support:
                    final_state, reason_code = "data_gap", "association_failed"
                else:
                    for order, name, start in special_events:
                        order_id = _clean(order.get("order_id"))
                        matching_rows = tuple(
                            row for row in expert_support_rows
                            if (_linked_order_id(row) == order_id and bool(order_id) and (
                                name in _antimicrobial_names_in(row, _SPECIAL_ANTIMICROBIALS)
                                or len(_antimicrobial_names_in(
                                    order, _SPECIAL_ANTIMICROBIALS
                                )) == 1
                            ))
                            or (
                                not _linked_order_id(row)
                                and name in _antimicrobial_names_in(
                                    row, _SPECIAL_ANTIMICROBIALS
                                )
                            )
                            or (
                                not _linked_order_id(row) and len(special_events) == 1
                                and not _antimicrobial_names_in(row)
                            )
                        )
                        matching_times = tuple(
                            value for row in matching_rows
                            if (value := _lx0609_058_row_time(row)) is not None
                        )
                        selected_antimicrobial_evidence_rows.extend(matching_rows)
                        # 事实与精确证据共用实际关联行，不能借其他药支持时间。
                        associated_expert_support_rows.extend(matching_rows)
                        if any(value <= start for value in matching_times):
                            continue
                        unmatched_names.append(name)
                        late_support = late_support or bool(matching_times)
                        untimed_support = untimed_support or any(
                            _lx0609_058_row_time(row) is None for row in matching_rows
                        )
                    if not unmatched_names:
                        final_state, reason_code = "compliant", "requirement_satisfied"
                    elif untimed_support:
                        final_state, reason_code = "data_gap", "authoritative_time_missing"
                    elif consultation_error or senior_error:
                        final_state, reason_code = "data_gap", consultation_error or senior_error
                    else:
                        final_state = "non_compliant"
                        reason_code = (
                            "requirement_violated"
                            if late_support
                            else "required_document_missing"
                        )
                timed_expert_supports = tuple(
                    value for row in associated_expert_support_rows
                    if (value := _lx0609_058_row_time(row)) is not None
                )
                expert_support_time = min(timed_expert_supports, default=None)
                if special_events:
                    display.append((rule_id, {
                        "verification_kind": "special_antimicrobial_expert_support_check",
                        "special_antimicrobials": list(special_names),
                        "expert_support_present": bool(associated_expert_support_rows),
                        "first_antimicrobial_time": (
                            first_order_time.isoformat(sep=" ")
                            if first_order_time is not None
                            else None
                        ),
                        "expert_support_time": (
                            expert_support_time.isoformat(sep=" ")
                            if expert_support_time is not None
                            else None
                        ),
                        "support_before_use": final_state == "compliant",
                        "unmatched_special_antimicrobials": list(dict.fromkeys(unmatched_names)),
                        "association_ambiguous": ambiguous_support,
                    }))
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
            elif discharge_rows and not discharge_error:
                diagnosis_scope, scope_gap = "discharge", None
                consumed.extend(("discharge_record", row) for row in discharge_rows)
            elif alive_registration_rows:
                scope_gap = None
                consumed.extend(("inpat_registration", row) for row in alive_registration_rows)
            else:
                scope_gap = "scope_unknown"

            if authority_error:
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
                    if not content_consistent:
                        final_state, reason_code = "non_compliant", "requirement_violated"
                        display.append((rule_id, {
                            "verification_kind": "discharge_diagnosis_consistency_check",
                            **({"diagnosis_scope": "death"} if diagnosis_scope == "death" else {}),
                            "authoritative_diagnoses": sorted(authority),
                            "written_diagnoses": sorted(written),
                            "diagnoses_consistent": False,
                            "order_comparable": order_comparable,
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
                        complete = authority == written
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
                        ref if _clean(row.get("document_id") or row.get("id")) or source_key == "inpat_registration"
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
                "inpat_registration", "mr_bloodtrans", "bloodtrans_record", "labtest_item_report",
            )
            transfusion_source_error = mr_bloodtrans_error or bloodtrans_record_error
            actual_transfusion_rows = tuple(mr_bloodtrans_rows)
            consumed_bloodtrans_rows: list[Mapping[str, Any]] = []
            unconfirmed_record_count = 0
            extraction_reason = ""
            performed_time_missing = False
            if transfusion_source_error:
                final_state, reason_code = "data_gap", transfusion_source_error
            elif not mr_bloodtrans_rows and not bloodtrans_record_rows:
                final_state, reason_code = "not_applicable", "trigger_absent_complete"
            else:
                transfusion_performance_extraction = await extract_transfusion_performance(
                    bloodtrans_record_rows, llm_client,
                )
                extraction_reason = transfusion_performance_extraction.reason_code
                # 全部专用行均用于事实抽取或范围门控；否定资料不计入实施事件。
                consumed_bloodtrans_rows = list(bloodtrans_record_rows)
                confirmed_records = []
                for row, state in zip(bloodtrans_record_rows, transfusion_performance_extraction.states):
                    if state == "performed" and _parse_datetime(row.get("record_time")) is not None:
                        confirmed_records.append(row)
                    elif state in {"performed", "unknown"}:
                        unconfirmed_record_count += 1
                        performed_time_missing = performed_time_missing or state == "performed"
                actual_transfusion_rows = (*mr_bloodtrans_rows, *confirmed_records)
                if not actual_transfusion_rows:
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
                            "inpat_registration": list(registration_rows),
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
                        "pretransfusion_tests_outside_current_stay": "requirement_violated",
                        "source_query_error": "source_query_error",
                    }.get(detail_reason, "required_field_missing")
                    if final_state == "compliant" and unconfirmed_record_count:
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
            invasive_orders = tuple(
                row for row in nondrug_order_rows
                if any(name in _material_text(row) for name in _INVASIVE_PROCEDURES)
            )
            if nondrug_order_error:
                final_state, reason_code = "data_gap", nondrug_order_error
            elif not invasive_orders:
                final_state, reason_code = "not_applicable", "trigger_absent_complete"
            elif daily_error:
                final_state, reason_code = "data_gap", daily_error
            else:
                ordered_names = tuple(
                    name for name in _INVASIVE_PROCEDURES
                    if any(name in _material_text(row) for row in invasive_orders)
                )
                complete = all(_has_any_text(daily_rows, (name,)) for name in ordered_names)
                final_state = "compliant" if complete else "non_compliant"
                reason_code = "requirement_satisfied" if complete else "required_document_missing"
                display.append((rule_id, {
                    (
                        "verification_kind"
                        if complete
                        else "failure_kind"
                    ): (
                        "invasive_procedure_course_record_complete"
                        if complete
                        else "invasive_procedure_course_record_missing"
                    ),
                    "ordered_procedures": list(ordered_names),
                    "course_documented": complete,
                }))
            decisions.append(_decision(
                rule_id=rule_id, snapshot=evidence_snapshot,
                source_keys=("inpat_nondrug_order", "daily_course_record"),
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
                medication_extraction = await extract_discharge_medications(
                    str(discharge_rows[0]["discharge_order"]), llm_client
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
                required_groups = (
                    ("drug_name", "generic_name", "name"),
                    ("dose", "single_dose"),
                    ("route", "drug_apply_method"),
                    ("duration", "usage_time", "frequency"),
                )
                complete = all(
                    all(
                        any(_clean(item.get(key)) for key in group)
                        for group in required_groups
                    )
                    for item in medications
                )
                final_state = "compliant" if complete else "non_compliant"
                reason_code = (
                    "requirement_satisfied" if complete else "requirement_violated"
                )
                missing_fields = sorted({
                    group[0]
                    for item in medications
                    for group in required_groups
                    if not any(_clean(item.get(key)) for key in group)
                })
                display.append(
                    (
                        rule_id,
                        {
                            "verification_kind": "discharge_medication_completeness_check",
                            "medication_count": len(medications),
                            "required_fields": [
                                "drug_name",
                                "dose",
                                "route",
                                "duration",
                            ],
                            "missing_fields": missing_fields,
                        },
                    )
                )
            decisions.append(
                _decision(
                    rule_id=rule_id,
                    snapshot=evidence_snapshot,
                    source_keys=("discharge_record",),
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
                        event.row for event in surgery_events
                    )
                elif final_state == "non_compliant":
                    # 缺失首次病程时，客户证据只指向缺失的手术事件；已满足
                    # 事件的病程不应被这条缺陷结论顺带投影。
                    selected_postoperative_rows.extend(
                        event.row
                        for event, linked_rows in linked_events
                        if not linked_rows
                    )
                else:
                    selected_postoperative_rows.extend(
                        event.row for event, _linked_rows in linked_events
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
            elif (
                len(surgery_events) > 1
                and all(event.source_key == "mr_surgery" for event in surgery_events)
            ):
                # 没有正式手术记录时，多个操作目录行仍无法安全证明逐台关联。
                # 本轮仅收敛“正式手术记录一行即一事件”的主路径。
                final_state, reason_code = "data_gap", "association_failed"
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
                        selected_postoperative_rows.append(event.row)
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
                    empty_body_events = []
                    unresolved_time_events = []
                    undated_course_rows = tuple(
                        row for row in (*daily_rows, *senior_rows)
                        if _row_time(row) is None and _course_row_has_body(row)
                    )
                    for event in surgery_events:
                        assert event.surgery_end_time is not None
                        selected_postoperative_rows.append(event.row)
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
                        surgeon_round_row = next(
                            (
                                row
                                for row in postop_rows
                                if event.surgeon_tokens
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
                        if surgeon_round_row is not None:
                            selected_postoperative_rows.append(surgeon_round_row)
                        surgeon_round = surgeon_round_row is not None
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
                        })
                        if not event.surgeon_tokens:
                            missing_surgeon_events.append(event.document_id)
                        if unresolved_empty_body_dates:
                            empty_body_events.append(event.document_id)
                        if missing_dates or not surgeon_round:
                            if undated_course_rows:
                                # 候选不能定日时，既不能补齐，也不能确认该手术缺项。
                                unresolved_time_events.append(event.document_id)
                                event_facts[-1]["course_time_unresolved"] = True
                                selected_postoperative_rows.extend(undated_course_rows)
                            else:
                                unmet_events.append({
                                    "document_id": event.document_id,
                                    "missing_postop_dates": missing_dates,
                                    "surgeon_round_present": surgeon_round,
                                })
                    if missing_surgeon_events or empty_body_events or unresolved_time_events:
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
                    final_state = "compliant" if present else "data_gap"
                    reason_code = (
                        "requirement_satisfied"
                        if present
                        else "source_empty"
                    )
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
                        structured_candidate_rows = _reason_and_basis_candidate_rows(
                            (
                                ("daily_course_record", daily_rows),
                                ("senior_course_record", senior_rows),
                            ),
                            changed_diagnosis_names=declared_diagnosis_names,
                        )
                        final_state, reason_code = (
                            "non_compliant",
                            "requirement_violated",
                        )
                        has_reason_and_basis = bool(structured_candidate_rows)
                        display.append((rule_id, {
                            "verification_kind": "diagnosis_change_documentation_check",
                            "diagnosis_change_count": len(declared_diagnosis_names),
                            "reason_recorded": has_reason_and_basis,
                            "basis_recorded": has_reason_and_basis,
                        }))
                        structured_binding = bind_consumed_continuity_document_rows(
                            snapshot=evidence_snapshot,
                            materials=evidence_materials,
                            consumed_rows=tuple(
                                ("admission_record_diagnosis", row)
                                for row in declaration_rows
                            )
                            + tuple(
                                (source_key, row)
                                for _time, _text, source_key, row in structured_candidate_rows
                            ),
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
            matching_course_indexes: tuple[tuple[int, ...], ...] = ()
            uniquely_matched = False
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
                    course_rows = tuple(
                        (_row_time(row), _row_text(row), source_key, row)
                        for source_key, source_rows in (
                            ("daily_course_record", daily_rows),
                            ("senior_course_record", senior_rows),
                        )
                        for row in source_rows
                    )
                    candidate_rows = tuple(
                        (record_time, text, source_key, row)
                        for record_time, text, source_key, row in course_rows
                        if any(
                            marker in text
                            for marker in _DIAGNOSIS_CHANGE_REASON_MARKERS
                        )
                        and any(
                            marker in text
                            for marker in _DIAGNOSIS_CHANGE_BASIS_MARKERS
                        )
                    )
                    if len(change_events) == 1:
                        changed_diagnosis_name = change_events[0][1]
                        # 名称、依据与时间必须属于同一条病程，不能借用其他诊断的时间。
                        candidate_rows = tuple(
                            candidate for candidate in candidate_rows
                            if changed_diagnosis_name in candidate[1]
                        )
                        has_changed_diagnosis_reference = bool(candidate_rows)
                        if not has_changed_diagnosis_reference:
                            # 有带时间的理由/依据候选，但未提及本次变更后的
                            # 诊断名称时，不能把其他诊断的记录当作本次变更
                            # 的证明；按既有规则合同保留为确定问题。
                            final_state, reason_code = (
                                "non_compliant",
                                "requirement_violated",
                            )
                            has_reason_and_basis = False
                        else:
                            matching_timed_candidates = tuple(
                                candidate
                                for candidate in candidate_rows
                                if candidate[0] is not None
                                and candidate[0] >= change_events[0][0]
                            )
                            untimed_candidates = tuple(
                                candidate
                                for candidate in candidate_rows
                                if candidate[0] is None
                            )
                            if matching_timed_candidates:
                                candidate_rows = matching_timed_candidates
                                has_reason_and_basis = True
                            elif untimed_candidates:
                                candidate_rows = untimed_candidates
                                has_reason_and_basis = False
                            else:
                                # 剩余候选均有时间且早于诊断变更，只能形成确定缺陷。
                                has_reason_and_basis = False
                        if has_changed_diagnosis_reference and not has_reason_and_basis and any(
                            record_time is None
                            for record_time, _text, _source_key, _row in candidate_rows
                        ):
                            final_state, reason_code = (
                                "data_gap",
                                "authoritative_time_missing",
                            )
                            display.append((rule_id, {
                                "failure_kind": "diagnosis_change_documentation_time_missing",
                                "diagnosis_change_count": len(change_events),
                                "untimed_document_count": len(candidate_rows),
                                "issue": "candidate_document_time_missing",
                            }))
                        elif has_changed_diagnosis_reference:
                            final_state = (
                                "compliant" if has_reason_and_basis else "non_compliant"
                            )
                            reason_code = (
                                "requirement_satisfied"
                                if has_reason_and_basis
                                else "requirement_violated"
                            )
                    else:
                        matching_course_indexes = tuple(
                            tuple(
                                index
                                for index, (record_time, text, _source_key, _row) in enumerate(candidate_rows)
                                if record_time is not None
                                and record_time >= change_time
                                and diagnosis_name in text
                            )
                            for change_time, diagnosis_name, _change_row in change_events
                        )
                        uniquely_matched = (
                            len(matching_course_indexes) == len(change_events)
                            and all(len(indexes) == 1 for indexes in matching_course_indexes)
                            and len({indexes[0] for indexes in matching_course_indexes})
                            == len(matching_course_indexes)
                        )
                        if uniquely_matched:
                            final_state, reason_code = (
                                "compliant",
                                "requirement_satisfied",
                            )
                        else:
                            final_state, reason_code = (
                                "data_gap",
                                "association_failed",
                            )
                            display.append((rule_id, {
                                "failure_kind": "diagnosis_change_association_failed",
                                "diagnosis_record_count": len(diagnosis_rows),
                                "diagnosis_change_count": len(change_events),
                                "association_issue": "multiple_changes_unresolved",
                            }))
                        has_reason_and_basis = uniquely_matched
                    if reason_code not in {
                        "association_failed",
                        "authoritative_time_missing",
                    }:
                        display.append((rule_id, {
                            "verification_kind": "diagnosis_change_documentation_check",
                            "diagnosis_change_count": len(change_events),
                            "reason_recorded": has_reason_and_basis,
                            "basis_recorded": has_reason_and_basis,
                        }))
            diagnosis_binding = bind_diagnosis_change_evidence(
                snapshot=evidence_snapshot,
                materials=evidence_materials,
                change_events=change_events,
                candidate_rows=candidate_rows,
                matching_course_indexes=matching_course_indexes,
                uniquely_matched=uniquely_matched,
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
                antimicrobial_effect_extraction,
                diagnosis_scope_extraction,
                medication_extraction,
                discharge_approval_extraction,
                diagnosis_change_extraction,
                transfusion_performance_extraction,
                *course_body_extractions,
            )
            if item is not None
        ),
        prompt_tokens=sum(
            item.prompt_tokens
            for item in (
                course_content_extraction,
                antimicrobial_action_extraction,
                antimicrobial_effect_extraction,
                diagnosis_scope_extraction,
                medication_extraction,
                discharge_approval_extraction,
                diagnosis_change_extraction,
                transfusion_performance_extraction,
                *course_body_extractions,
            )
            if item is not None
        ),
        completion_tokens=sum(
            item.completion_tokens
            for item in (
                course_content_extraction,
                antimicrobial_action_extraction,
                antimicrobial_effect_extraction,
                diagnosis_scope_extraction,
                medication_extraction,
                discharge_approval_extraction,
                diagnosis_change_extraction,
                transfusion_performance_extraction,
                *course_body_extractions,
            )
            if item is not None
        ),
        total_tokens=sum(
            item.total_tokens
            for item in (
                course_content_extraction,
                antimicrobial_action_extraction,
                antimicrobial_effect_extraction,
                diagnosis_scope_extraction,
                medication_extraction,
                discharge_approval_extraction,
                diagnosis_change_extraction,
                transfusion_performance_extraction,
                *course_body_extractions,
            )
            if item is not None
        ),
        api_time=sum(
            item.api_time
            for item in (
                course_content_extraction,
                antimicrobial_action_extraction,
                antimicrobial_effect_extraction,
                diagnosis_scope_extraction,
                medication_extraction,
                discharge_approval_extraction,
                diagnosis_change_extraction,
                transfusion_performance_extraction,
                *course_body_extractions,
            )
            if item is not None
        ),
    )
