"""第一阶段新增的确定性文书规则。

本执行器只消费同一个 Evidence Snapshot/Material Store，不调用旧四川规则，
也不从自由文本结论反推状态。
"""

from __future__ import annotations

from ..automatic_material_scope import source_scope
from ..llm_token_budget import budget_guarded_executor

import asyncio
from collections import Counter

import logging
import re
import sys
from dataclasses import dataclass, replace
from datetime import date, datetime, timedelta
from typing import Any, Mapping, Sequence
from zoneinfo import ZoneInfo

from app.core.execution_timing import measure_stage, timing_labels
from .evaluation_horizon import after_frozen_horizon, frozen_window_is_mature
from .phase_scope import build_luxian_0609_pending_definition_result

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
from .evidence_snapshot import Luxian0609EvidenceSnapshot, SourceCompleteness
from .extended_document.diagnosis_scope_extraction import extract_diagnosis_scope
from .extended_document.discharge_diagnosis_equivalence import (
    extract_discharge_diagnosis_equivalence,
    map_equivalent_diagnoses as _map_equivalent_diagnoses,
    split_numbered_diagnoses,
)
from .extended_document.invasive_procedure_record import (
    RECORD_WINDOW_DAYS as INVASIVE_RECORD_WINDOW_DAYS,
    candidate_order_rows as _invasive_candidate_order_rows,
    check_invasive_procedure_records,
    map_orders_to_invasive_catalog,
    merge_triggers as _merge_invasive_triggers,
    order_triggers as _invasive_order_triggers,
    trigger_key as _invasive_trigger_key,
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
from .extended_document.diagnosis_change_extraction import (
    DiagnosisChangeDocumentInput,
    extract_diagnosis_change_documentation,
)
from .extended_document.antimicrobial_action_extraction import (
    antimicrobial_names_in as _antimicrobial_names_in,
)
from .extended_document.transfusion_performance_extraction import extract_transfusion_performance
from .transfusion_course_presence import classify_transfusion_course_records, select_transfusion_course_candidates
from .extended_document.physician_handoff import evaluate_physician_handoff
from .extended_document.rule_076 import death_time_from_body, death_times_from_body, evaluate_rule_076
from .extended_document.shared import _clean, _parse_datetime, _row_time, row_time_upper_bound
from app.services.document_assembly.signatures import course_physician_signatures
from .extended_document.discharge_medication_extraction import extract_discharge_medications
from .extended_document.discharge_approval_extraction import (
    DischargeApprovalInput,
    extract_discharge_approval,
)
from .extended_document.transfer_documentation import (
    evaluate_transfer_documentation,
)
from .extended_document_critical_value import CRITICAL_VALUE_RULE_IDS
from .extended_document.antimicrobial_family import (
    ANTIMICROBIAL_RULE_IDS,
    execute_antimicrobial_family,
)
from .extended_document.critical_value_family import (
    execute_critical_value_family,
)
from .extended_document.family_runtime import (
    SourceRowsCache,
    build_extended_decision as _decision,
    discharge_time as _discharge_time,
    discharge_time_with_source as _discharge_time_with_source,
    fact_refs as _fact_refs,
    has_any_text as _has_any_text,
    material_text as _material_text,
    parse_hospital_datetime as _parse_lx0609_058_datetime,
    precise_datetime as _precise_datetime,
    resolve_evaluation_horizon as _critical_value_evaluation_horizon,
    resolve_horizon_rows,
    source_rows as _source_rows,
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

EXECUTOR_KEY = "extended_document"
EXTENDED_DOCUMENT_RULE_IDS = (
    "LX0609-10-04-01",
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
    "LX0609-04-02-09",
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
    "bloodtrans_record",
)

_DEATH_MARKERS = ("死亡", "病故")
_ALIVE_DISCHARGE_MARKERS = ("出院", "转院", "医嘱离院", "非医嘱离院")
_EXPLICIT_ALIVE_DISCHARGE_MARKERS = ("存活", "好转", "治愈", "未愈", "转院", "医嘱离院")
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
_EXPLICIT_NO_DISCHARGE_MEDICATION_PATTERN = re.compile(
    r"(?:出院带药\s*[:：]\s*(?:无|未开|拒绝)|"
    r"(?:患者)?(?:未开|无|不需(?:要)?|拒绝)(?:出院)?带药)"
)
_EMPTY_DISCHARGE_ORDER_TEMPLATE_PATTERN = re.compile(
    r"(?:随访方式|随访周期|随访日期|出院医嘱|出院带药|注意事项)\s*[:：]?"
)
_GHOST_DEATH_RECORD_SUBSTANTIVE_FIELDS = (
    "record_content",
    "treatment_course",
    "death_datetime",
    "death_time",
    "record_time",
    "submit_datetime",
    "document_title",
    "death_reason",
    "death_diagnosis",
    "admission_condition",
    "rescue_process",
)
_DEATH_RECORD_METADATA_FIELDS = (
    "record_time",
    "submit_datetime",
    "last_modified_datetime",
    "update_time",
    "document_status",
    "death_datetime",
    "death_time",
    "treatment_course",
)
_LX0609_HOSPITAL_TIMEZONE = ZoneInfo("Asia/Shanghai")
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
        and _affirmative_discharge_clause(text, _SENIOR_PHYSICIAN_CONSULTED_PATTERN)
        and _affirmative_discharge_clause(text, _AUTOMATIC_DISCHARGE_SIGNED_PATTERN)
        and not _AUTOMATIC_DISCHARGE_UNSIGNED_PATTERN.search(text)
    ):
        return "automatic_discharge"

    # 上级同意出院一律交模型抽取，不再由正则直接认定（用户口径 2026-10-22）。
    return None


def _affirmative_discharge_clause(text: str, pattern: re.Pattern[str]) -> bool:
    """只接受同分句已发生事实，否定、计划及既往叙述不能证明本次已完成。"""
    # 比较局部情态的先后，允许“已”后有方式修饰，后续否定/计划仍覆盖肯定。
    pending_action = re.compile(r"未|无|不|拒绝|拟|计划|准备|待|取消|撤销")
    # “现”只接受动作前的现行表达，不将发现/出现等复合词尾字视为时态。
    completed_action = re.compile(r"已经?|(?<![发出体实呈表再显])现(?:行)?\s*$")
    history = re.compile(r"既往|此前|曾经|曾")
    current_scope = re.compile(r"本次|此次|今日|目前|现在|现")
    for clause in re.split(r"[，,。；;\n]|但是|但|然而|不过", text):
        for match in pattern.finditer(clause):
            prefix = clause[:match.start()]
            pending = tuple(pending_action.finditer(prefix))
            completed = tuple(completed_action.finditer(prefix))
            if pending and (not completed or pending[-1].start() > completed[-1].start()):
                continue
            histories = tuple(history.finditer(prefix))
            currents = tuple(current_scope.finditer(prefix))
            if histories and (not currents or currents[-1].start() < histories[-1].start()):
                continue
            return True
    return False


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


def _latest_written_diagnosis_version(
    written_rows: Sequence[Mapping[str, Any]],
    discharge_rows: Sequence[Mapping[str, Any]],
) -> tuple[tuple[Mapping[str, Any], ...], str | None]:
    """多版本出院记录（初写、补录、修订）只取最后一份权威版本的诊断，不合并比对。

    诊断行以 ``document_id`` 归属出院记录。只有一份出院记录时沿用其诊断行
    （兼容未带文书编号的旧快照），但两边编号都有而不一致时返回冲突。多份出院记录时：
    - 出院记录或诊断行缺文书编号、诊断行归属不到任何出院记录，均无法确认
      诊断属于哪一版，返回 ``version_conflict``，不借旧版判定；
    - 各版在判定字段（序号、名称、主诊断标记、类型）上完全相同时取任一版本；
    - 否则凭出院记录时间唯一确定最后版本，取该版诊断（可为空，由后续给出
      诊断缺失）；无法唯一确定时返回 ``version_conflict``。
    """
    from .basic_timeliness_facts import parse_authoritative_datetime

    rows = tuple(written_rows)
    ids = [_clean(row.get("document_id")) for row in rows]
    parent_ids = [_clean(row.get("document_id")) for row in discharge_rows]
    groups: dict[str, list[Mapping[str, Any]]] = {}
    for doc_id, row in zip(ids, rows):
        groups.setdefault(doc_id, []).append(row)
    distinct_parents = set(parent_ids)
    if len(discharge_rows) <= 1 or (all(parent_ids) and len(distinct_parents) == 1):
        # 单一出院记录：缺编号的旧快照沿用其诊断行；两边都有编号而明确不一致，
        # 或多组诊断行时，无法确认诊断属于该出院记录。
        known_parents = {doc_id for doc_id in distinct_parents if doc_id}
        known_children = {doc_id for doc_id in groups if doc_id}
        if known_parents and known_children and not known_children <= known_parents:
            return (), "version_conflict"
        if len(groups) <= 1:
            return rows, None
        if all(ids) and set(groups) <= distinct_parents:
            return rows, None
        return (), "version_conflict"
    if not all(parent_ids) or not all(ids) or not set(groups) <= distinct_parents:
        return (), "version_conflict"

    def signature(group):
        return tuple(sorted(
            (
                _clean(row.get("diagnosis_no")),
                _clean(row.get("diagnosis_name") or row.get("diagnosis")),
                _clean(row.get("diagnosis_main")),
                _clean(row.get("diagnosis_type")),
            )
            for row in group
        ))

    if set(groups) == distinct_parents and len({signature(group) for group in groups.values()}) == 1:
        return tuple(next(iter(groups.values()))), None
    times: dict[str, Any] = {}
    for row in discharge_rows:
        doc_id = _clean(row.get("document_id"))
        moment = parse_authoritative_datetime(authoritative_document_time_value(row))
        if moment is None or (doc_id in times and times[doc_id] != moment):
            return (), "version_conflict"
        times[doc_id] = moment
    latest = max(times.values())
    latest_ids = [doc_id for doc_id, moment in times.items() if moment == latest]
    if len(latest_ids) != 1:
        return (), "version_conflict"
    return tuple(groups.get(latest_ids[0], ())), None


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

    bloodtrans_record_rows = []
    for key in ("bloodtrans_record", "daily_course_record", "senior_course_record"):
        try:
            rows = materials.document_rows(key, snapshot=snapshot)
        except (EvidenceMaterialUnavailable, EvidenceMaterialTruncated):
            # 未消费的辅助源不可用，不得清空已核验的专用文书引用。
            continue
        bloodtrans_record_rows.extend(
            (reference, row) for reference, row in rows
            if consumed_bloodtrans_rows is None or row in consumed_bloodtrans_rows
        )
    if consumed_bloodtrans_rows is not None and any(
        not any(row == selected for _, row in bloodtrans_record_rows)
        for selected in consumed_bloodtrans_rows
    ):
        return ()
    if not include_pretransfusion_materials:
        return tuple(dict.fromkeys(reference for reference, _ in bloodtrans_record_rows))
    try:
        registration_rows = materials.document_rows("inpat_registration", snapshot=snapshot)
        if not any(resolve_pretransfusion_admission_time(row) is not None for _, row in registration_rows):
            registration_rows = materials.document_rows("admission_record", snapshot=snapshot)
        lab_rows = materials.document_rows("labtest_item_report", snapshot=snapshot)
    except (EvidenceMaterialUnavailable, EvidenceMaterialTruncated):
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
        *(reference for reference, row in bloodtrans_record_rows
          if consumed_bloodtrans_rows is None or row in consumed_bloodtrans_rows),
        *lab_refs,
    )
    return tuple(dict.fromkeys(refs))


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
    from .basic_timeliness_facts import parse_authoritative_date, parse_authoritative_datetime

    raw_death_times = tuple(
        value for row in (*death_rows, *registration_rows)
        if (value := row.get("death_datetime") or row.get("death_time")) is not None
        and str(value).strip()
    )
    explicit_death_times = {
        candidate
        for value in raw_death_times
        if (candidate := parse_authoritative_datetime(value)) is not None
    }
    if len(explicit_death_times) > 1:
        return "conflict", None
    if any(parse_authoritative_datetime(value) is None for value in raw_death_times) and (
        death_rows or explicit_death_times
        or any(parse_authoritative_date(value) is not None for value in raw_death_times)
    ):
        # 有死亡字段只能证明死亡，纯日期不能升级零点参与精确小时判定。
        return "present", None
    if not explicit_death_times:
        # 正文死亡时间也统一到医院时区，与结构化时间及讨论时间保持一致。
        explicit_death_times = {
            candidate
            for row in death_rows
            if (candidate := parse_authoritative_datetime(death_time_from_body(row))) is not None
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


def _affirmative_death_record_refs(
    snapshot: Luxian0609EvidenceSnapshot,
    materials: Luxian0609EvidenceMaterialStore,
    registration_rows: Sequence[Mapping[str, Any]],
) -> tuple[tuple[str, ...], bool]:
    """返回明确死亡证据及日期/时刻是否矛盾。"""
    from .basic_timeliness_facts import parse_authoritative_date, parse_authoritative_datetime

    try:
        records = materials.document_rows("death_record", snapshot=snapshot)
    except (EvidenceMaterialUnavailable, EvidenceMaterialTruncated):
        return (), False
    dates: set[date] = set()
    times: set[datetime] = set()
    proof: list[str] = []
    unparseable = False
    for ref, row in (*records, *(("", row) for row in registration_rows)):
        row_times: list[datetime] = []
        row_dates: list[date] = []
        for field in ("death_datetime", "death_time"):
            value = row.get(field)
            if not _clean(value):
                continue
            if (moment := parse_authoritative_datetime(value)) is not None:
                row_times.append(moment)
            elif (day := parse_authoritative_date(value)) is not None:
                row_dates.append(day)
            else:
                unparseable = True
        if ref:
            row_times.extend(
                moment for value in death_times_from_body(row)
                if (moment := parse_authoritative_datetime(value)) is not None
            )
        times.update(row_times)
        dates.update((*row_dates, *(moment.date() for moment in row_times)))
        if ref and (row_times or row_dates):
            proof.append(ref)
    conflict = len(dates) > 1 or len(times) > 1
    return (() if conflict or unparseable or len(proof) > 128 else tuple(proof)), conflict


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
    *, incomplete_names: frozenset[str] = frozenset(),
) -> tuple[str, str, dict[str, Any] | None, Any]:
    """对 (来源, 病程行, 正文, 变更诊断名) 候选做一次受控抽取并按诊断汇总。

    同一变更诊断的理由与依据可分记于不同病程；任一诊断确定未记录→不合规，
    仅因语义未知而无法确认→不确定。
    """

    from ..llm_token_budget import budget_rule_scope
    budget_errors = []
    with budget_rule_scope(budget_errors.append):
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
    if budget_errors:
        error = budget_errors[0]
        extraction = replace(extraction, state="technical_error", reason_code=error.code,
            llm_call_count=max(0, extraction.llm_call_count - int(not getattr(error, "request_started", False))))
        return "technical_error", error.code, None, extraction
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
    elif any(not unknown[name] and name not in incomplete_names for name in unsatisfied):
        final_state, reason_code = "non_compliant", "requirement_violated"
    elif any(name in incomplete_names for name in unsatisfied):
        return "data_gap", "candidate_scope_incomplete", None, extraction
    else:
        return "uncertain", "semantic_low_confidence", None, extraction
    return final_state, reason_code, {
        "verification_kind": "diagnosis_change_documentation_check",
        "diagnosis_change_count": len(change_names),
        "reason_recorded": all(reason.values()),
        "basis_recorded": all(basis.values()),
    }, extraction


def _is_ghost_death_row(row: Mapping[str, Any]) -> bool:
    """过滤全部业务正文与时间字段均为 NULL/空的死亡记录幽灵行。"""

    return not any(_clean(row.get(field)) for field in _GHOST_DEATH_RECORD_SUBSTANTIVE_FIELDS)


def _is_metadata_bare_untimed_death_duplicate(row: Mapping[str, Any]) -> bool:
    """识别 PDF 补录的无时间/无状态纯正文重复行（visit_type='I' 或无 document_id 且所有元数据时间与状态列均为空）。"""

    if any(_clean(row.get(field)) for field in _DEATH_RECORD_METADATA_FIELDS):
        return False
    visit_type = _clean(row.get("visit_type")).upper()
    doc_id = _clean(row.get("document_id"))
    return visit_type == "I" or not doc_id


def _filter_death_rows_for_timeliness(
    death_rows: Sequence[Mapping[str, Any]],
) -> tuple[Mapping[str, Any], ...]:
    """当已存在权威计时的死亡记录时，过滤无时间无状态的重复 PDF 补录行，但保留时间冲突。"""

    if len(death_rows) <= 1:
        return tuple(death_rows)
    timed_rows = tuple(
        row for row in death_rows
        if not _is_metadata_bare_untimed_death_duplicate(row)
        and _parse_datetime(authoritative_document_time_value(row)) is not None
    )
    if not timed_rows:
        return tuple(death_rows)
    from .basic_timeliness_facts import parse_authoritative_datetime

    timed_death_clocks = {
        parsed
        for row in timed_rows
        for raw in (row.get("death_datetime") or row.get("death_time") or death_time_from_body(row),)
        if raw and (parsed := parse_authoritative_datetime(raw)) is not None
    }
    kept: list[Mapping[str, Any]] = []
    for row in death_rows:
        if _is_metadata_bare_untimed_death_duplicate(row):
            body_death = death_time_from_body(row)
            body_clock = parse_authoritative_datetime(body_death) if body_death else None
            # 仅当无时间补录行的正文死亡时刻与权威行不冲突时才安全去重。
            if body_clock is None or not timed_death_clocks or body_clock in timed_death_clocks:
                continue
        kept.append(row)
    return tuple(kept) or tuple(death_rows)


def _is_empty_template_discharge_order(value: Any) -> bool:
    cleaned = _clean(value)
    if not cleaned:
        return True
    stripped = _EMPTY_DISCHARGE_ORDER_TEMPLATE_PATTERN.sub("", cleaned)
    stripped = re.sub(r"[\s:：。，,;；、\-_/]+", "", stripped)
    return not stripped


def _is_empty_discharge_shell_for_course(row: Mapping[str, Any]) -> bool:
    """判断出院记录是否为无诊疗正文的空壳行（避免 08-01-05 对空壳误判不合规）。"""

    narrative_fields = (
        "record_content",
        "treatment_course",
        "admission_condition",
        "discharge_condition",
        "discharge_sympton_condition",
        "positive_assist_exam",
        "condition_transform",
    )
    if not any(_clean(row.get(field)) for field in narrative_fields):
        return _is_empty_template_discharge_order(row.get("discharge_order"))
    if "record_content" in row and not _clean(row.get("record_content")) and not _clean(row.get("treatment_course")):
        return True
    return False


def _is_empty_body_discharge_row(row: Mapping[str, Any]) -> bool:
    """判断出院记录正文是否缺失（用于 08-01-02 防止对空正文壳行误报漏写带药）。"""

    if row.get("discharge_medications") is not None:
        return False
    if "record_content" in row and not _clean(row.get("record_content")):
        return True
    return not _clean(row.get("record_content")) and _is_empty_template_discharge_order(
        row.get("discharge_order")
    )


def _resolve_death_discussion_horizon_rows(
    *,
    horizon_rows: Sequence[Mapping[str, Any]],
    horizon_error: str,
    death_time: datetime | None,
    snapshot: Luxian0609EvidenceSnapshot,
    registration_rows: Sequence[Mapping[str, Any]],
    death_rows: Sequence[Mapping[str, Any]],
) -> tuple[Mapping[str, Any], ...]:
    """终末场景下 09-02-01 不能把评价时点钉死在死亡时刻（导致恒定尚余168h）。

    仅在终末出院口径（basis='discharge_date'）、非在院运行态且未显式冻结
    task_frozen_date 时，回退至不早于死亡时刻的快照冻结时间或病历归档修改时间；
    在院运行态（evaluation_as_of / running）与显式 task_frozen_date 保持原合同不变。
    """

    if horizon_error or death_time is None or len(horizon_rows) != 1:
        return tuple(horizon_rows)
    row = horizon_rows[0]
    if (
        _clean(row.get("basis")) != "discharge_date"
        or _clean(row.get("record_scene")).lower() == "running"
        or _clean(row.get("task_frozen_date"))
    ):
        return tuple(horizon_rows)
    candidates: list[datetime] = []
    snapshot_dt = _parse_lx0609_058_datetime(snapshot.created_at)
    if snapshot_dt is not None and snapshot_dt >= death_time:
        candidates.append(snapshot_dt)
    for source_row in (*registration_rows, *death_rows):
        for field in ("last_modified_datetime", "update_time"):
            modified_dt = _parse_lx0609_058_datetime(source_row.get(field))
            if modified_dt is not None and modified_dt >= death_time:
                candidates.append(modified_dt)
    if not candidates:
        return tuple(horizon_rows)
    effective_dt = max(candidates)
    current_dt = _parse_datetime(row.get("horizon_datetime"))
    if current_dt is not None and effective_dt <= current_dt:
        return tuple(horizon_rows)
    return (
        {
            **row,
            "horizon_datetime": effective_dt.isoformat(sep=" "),
            "horizon_date": effective_dt.date().isoformat(),
        },
    )


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


def _is_effective_discharge_prescription(row: Mapping[str, Any]) -> bool:
    return (
        _clean(row.get("order_type")) == "出院带药"
        and _clean(row.get("order_status")) in {"新开", "执行", "执行中", "核实", "完成"}
        and _clean(row.get("is_deleted")).lower() not in {"1", "true"}
    )


def _discharge_oral_prescription_names(materials: Luxian0609EvidenceMaterialStore) -> tuple[str, ...]:
    """只读同次就诊正式出院处方，仅用于确定口服剂型，不补剂量或频次。"""
    try:
        prescriptions = materials.rows("inpat_prescription")
        items = materials.rows("inpat_prescription_item")
    except (EvidenceMaterialUnavailable, EvidenceMaterialTruncated):
        return ()
    eligible = {
        _clean(row.get("prescription_id")) for row in prescriptions
        if _clean(row.get("prescription_id")) and _is_effective_discharge_prescription(row)
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
        if _clean(row.get("prescription_id")) and _is_effective_discharge_prescription(row)
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

    # 正文与处方同口径去掉括注（如采购标记“(JC)”、规格），否则正文照抄处方名时
    # 永远对不上（1022 C17）。
    documented = re.sub(r"[（(][^）)]*[）)]", "", _clean(documented_name)).strip()
    prescribed = re.sub(r"[（(][^）)]*[）)]", "", _clean(prescription_name)).strip()
    if not documented or not prescribed:
        return False
    if documented == prescribed:
        return True
    # 正文剂型写法与处方不同（“丁苯酞胶囊”对“丁苯酞软胶囊”）时按去剂型后的药名比对。
    base = re.sub(_SAFE_MEDICATION_IDENTITY_SUFFIX + r"$", "", documented)
    if len(base) < 3:
        return False
    return bool(re.fullmatch(
        re.escape(base) + _SAFE_MEDICATION_IDENTITY_SUFFIX, prescribed,
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


def _qualified_surgery_rows(surgery_record_rows: Sequence[Mapping[str, Any]]) -> tuple[Mapping[str, Any], ...]:
    return tuple(row for row in surgery_record_rows if catalog_surgery_state(row) is not False)


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


_PHYSICIAN_TITLE_ALTERNATION = "副主任医师|主任医师|主治医师|住院医师|医师"


def _body_surgeon_round_tokens(row: Mapping[str, Any], *, candidate_tokens: frozenset[str]) -> frozenset[str]:
    """用户口径（2026-10-22）：正文明确写“术者/主刀医师××查看患者”也算术者查房。

    只认术者/主刀角色与首页术者完整姓名紧邻、且同句写明查看/查房；单纯提及术者
    （如“手术由××完成”）不算。
    """

    text = _clean(row.get("record_content"))
    if not text:
        return frozenset()
    found = set()
    for token in candidate_tokens:
        name = re.escape(token)
        title = rf"(?:{_PHYSICIAN_TITLE_ALTERNATION})?"
        role = r"(?:术者|主刀(?:医师|医生)?)"
        if re.search(
            rf"(?:{role}[：:]?\s*{name}{title}|{name}{title}[（(]?{role}[）)]?)"
            rf"[^。；;\n]{{0,12}}(?:查看|查房|看望|探视)",
            text,
        ):
            found.add(token)
    return frozenset(found)


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
    return None


def _postoperative_surgery_events(
    *, surgery_record_rows: Sequence[Mapping[str, Any]],
) -> tuple[_PostoperativeSurgeryEvent, ...]:
    """按原始手术记录逐文书建事件，首页不提供台次、术者或时间回退。"""
    events = []
    for index, row in enumerate(_qualified_surgery_rows(surgery_record_rows), start=1):
        end_time = _actual_surgery_end_time(source_key="surgery_record", row=row)
        begin_time = _actual_surgery_begin_time(source_key="surgery_record", row=row)
        events.append(_PostoperativeSurgeryEvent(
            source_key="surgery_record", row=row, member_rows=(row,),
            document_id=_clean(row.get("document_id") or row.get("id")) or f"surgery_record:{index}",
            surgery_name=_clean(row.get("surgery_name") or row.get("operation_name") or row.get("procedure_name")),
            surgery_end_time=end_time if end_time is not None else begin_time,
            surgeon_names=_surgery_event_surgeon_names(row),
            surgeon_tokens=_surgery_event_surgeon_tokens(row),
            surgery_begin_time=begin_time,
            surgery_time_estimated=end_time is None and begin_time is not None,
            surgery_time_date_only=False,
        ))
    return tuple(events)


def _postoperative_document_refs(
    *,
    snapshot: Luxian0609EvidenceSnapshot,
    materials: Luxian0609EvidenceMaterialStore,
    selected_rows: Sequence[Mapping[str, Any]],
) -> tuple[str, ...]:
    """把064/065/066实际消费的事件或病程唯一绑定为逐文书证据。"""

    allowed_sources = (
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
    """在逐台核对前确认至少有一台术后三日观察窗口已经成熟。

    评价终点必须来自同一冻结 Evidence Session。只有日期时按保守口径，
    评价日期严格晚于对应手术结束日后的第三个自然日，避免在窗口当天提前
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
        any(horizon_time.date() > deadline for deadline in deadlines)
        if horizon_time is not None
        else any(horizon_date > deadline for deadline in deadlines)
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


@budget_guarded_executor
async def execute_luxian_0609_native_extended_document_rules(
    *,
    rule_ids: Sequence[str],
    evidence_snapshot: Luxian0609EvidenceSnapshot,
    evidence_materials: Luxian0609EvidenceMaterialStore,
    decision_rule_ids: Sequence[str] = (),
    llm_client: Any = None,
    **kwargs: Any,
) -> NativeExtendedDocumentExecutionResult:
    """仅并行两个独立事实组；不拆抗菌药共享缓存，不改变临床内核。"""
    requested = tuple(
        dict.fromkeys(
            str(item or "").strip().upper()
            for item in rule_ids
            if str(item or "").strip()
        )
    )
    selected = tuple(
        rule_id for rule_id in requested if rule_id in EXTENDED_DOCUMENT_RULE_IDS
    )
    if not selected:
        return NativeExtendedDocumentExecutionResult((), (), ())
    if (not isinstance(evidence_snapshot, Luxian0609EvidenceSnapshot)
            or not isinstance(evidence_materials, Luxian0609EvidenceMaterialStore)
            or evidence_materials.snapshot_hash != evidence_snapshot.snapshot_hash):
        raise ValueError("extended document rules require one evidence session")
    if set(decision_rule_ids) != set(selected):
        raise ValueError("extended document rules require typed decisions")

    # 暂停的首页对照规则仅交付政策待定结果，不进入临床决策或模型执行。
    pending_results = tuple(
        build_luxian_0609_pending_definition_result(rule_id)
        for rule_id in selected if rule_id == "LX0609-08-01-03"
    )
    executable = tuple(rule_id for rule_id in selected if rule_id != "LX0609-08-01-03")
    if not executable:
        return NativeExtendedDocumentExecutionResult(pending_results, selected, ())

    # 054/057 共用一次理由抽取，055/056/058 也留在同组；其余文书不消费
    # 这些局部缓存。两组只读同一不可变材料仓，HTTP 仍走既有共享预算。
    antimicrobial = frozenset(ANTIMICROBIAL_RULE_IDS)
    groups = tuple((label, rules) for label, rules in (
        ("antimicrobial", tuple(rule for rule in executable if rule in antimicrobial)),
        ("documents", tuple(rule for rule in executable if rule not in antimicrobial)),
    ) if rules)

    async def run_group(label, rules):
        with timing_labels(unit=label), measure_stage("extended_group"):
            return await _execute_extended_document_group(
                rule_ids=rules, decision_rule_ids=rules,
                evidence_snapshot=evidence_snapshot, evidence_materials=evidence_materials,
                llm_client=llm_client, **kwargs,
            )

    if len(groups) == 1:
        part = await run_group(*groups[0])
        if not pending_results:
            return part
        return replace(
            part, results=tuple(sorted((*part.results, *pending_results),
                                       key=lambda item: selected.index(item["rule_id"]))),
            planned_rule_ids=selected,
        )
    tasks = [asyncio.create_task(run_group(*group)) for group in groups]
    try:
        parts = await asyncio.gather(*tasks)
    except BaseException:
        for task in tasks:
            if not task.done():
                task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        raise

    order = {rule_id: index for index, rule_id in enumerate(selected)}
    return NativeExtendedDocumentExecutionResult(
        results=tuple(sorted((*pending_results, *(item for part in parts for item in part.results)),
                             key=lambda item: order[item["rule_id"]])),
        planned_rule_ids=selected,
        decisions=tuple(sorted((item for part in parts for item in part.decisions),
                               key=lambda item: order[item.rule_id])),
        customer_display_facts=tuple(sorted(
            (item for part in parts for item in part.customer_display_facts),
            key=lambda item: order[item[0]],
        )),
        **{key: sum(getattr(part, key) for part in parts) for key in (
            "llm_call_count", "prompt_tokens", "completion_tokens", "total_tokens", "api_time",
        )},
    )


async def _execute_extended_document_group(
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
    diagnosis_scope_extraction = None
    diagnosis_equivalence_extraction = None
    invasive_extractions: list[Any] = []
    transfusion_performance_extraction = None
    transfusion_course_extraction = None
    postoperative_time_estimated_rules: set[str] = set()
    requested = tuple(
        dict.fromkeys(
            str(item or "").strip().upper()
            for item in rule_ids
            if str(item or "").strip()
        )
    )
    selected = tuple(
        rule_id for rule_id in requested if rule_id in EXTENDED_DOCUMENT_RULE_IDS
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

    group_source_cache: SourceRowsCache = {}
    if set(selected).issubset(ANTIMICROBIAL_RULE_IDS):
        antimicrobial_only = await execute_antimicrobial_family(
            rule_ids=selected,
            evidence_snapshot=evidence_snapshot,
            evidence_materials=evidence_materials,
            llm_client=llm_client,
            source_cache=group_source_cache,
        )
        return NativeExtendedDocumentExecutionResult(
            results=(),
            planned_rule_ids=selected,
            decisions=antimicrobial_only.decisions,
            customer_display_facts=antimicrobial_only.display_facts,
            llm_call_count=antimicrobial_only.llm_call_count,
            prompt_tokens=antimicrobial_only.prompt_tokens,
            completion_tokens=antimicrobial_only.completion_tokens,
            total_tokens=antimicrobial_only.total_tokens,
            api_time=antimicrobial_only.api_time,
        )

    registration_rows, registration_error = _source_rows(
        evidence_materials, "inpat_registration", cache=group_source_cache
    )
    admission_rows, admission_error = _source_rows(
        evidence_materials, "admission_record", cache=group_source_cache
    )
    death_rows, death_error = _source_rows(
        evidence_materials, "death_record", cache=group_source_cache
    )
    death_rows = tuple(row for row in death_rows if not _is_ghost_death_row(row))
    discussion_rows, discussion_error = _source_rows(
        evidence_materials, "death_discussion", cache=group_source_cache
    )
    horizon_rows, horizon_error = (
        resolve_horizon_rows(
            evidence_snapshot, evidence_materials, cache=group_source_cache
        )
        if {
            "LX0609-09-02-01",
            "LX0609-06-04-01",
            "LX0609-05-01-03",
            "LX0609-05-01-02", "LX0609-05-01-05", "LX0609-05-01-06",
            "LX0609-10-01-01", "LX0609-10-03-01",
            "LX0609-08-01-01",
            "LX0609-08-01-03",
            "LX0609-04-05-01",
            "LX0609-04-05-02",
            "LX0609-08-02-01",
            "LX0609-08-02-02",
            "LX0609-10-02-01",
            "LX0609-10-04-01",
        }.intersection(selected)
        else ((), "")
    )
    (
        antimicrobial_horizon_date,
        antimicrobial_horizon_datetime,
        antimicrobial_horizon_error,
    ) = (
        _critical_value_evaluation_horizon(horizon_rows, horizon_error)
        if {"LX0609-10-01-01", "LX0609-10-03-01"}.intersection(selected)
        else (None, None, None)
    )
    antimicrobial_evaluation_horizon = antimicrobial_horizon_datetime or antimicrobial_horizon_date
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
        evidence_materials, "discharge_record", cache=group_source_cache
    )
    daily_rows, daily_error = _source_rows(
        evidence_materials, "daily_course_record", cache=group_source_cache
    )
    daily_scope_complete = evidence_materials.permits_absence("daily_course_record")
    senior_rows, senior_error = _source_rows(
        evidence_materials, "senior_course_record", cache=group_source_cache
    )
    postop_first_rows, postop_first_error = _source_rows(
        evidence_materials, "postsurg_firstcourse_record", cache=group_source_cache
    )
    surgery_record_rows, surgery_record_error = _source_rows(
        evidence_materials, "surgery_record", cache=group_source_cache
    )
    consultation_rows, consultation_error = _source_rows(
        evidence_materials, "consultation_record", cache=group_source_cache
    )
    handoff_rows, handoff_error = _source_rows(
        evidence_materials, "handoff_record", cache=group_source_cache
    )
    handover_rows, handover_error = _source_rows(
        evidence_materials, "handover_record", cache=group_source_cache
    )
    physician_change_rows, physician_change_error = _source_rows(
        evidence_materials, "physician_change_event", cache=group_source_cache
    )
    transfer_in_rows, transfer_in_error = _source_rows(
        evidence_materials, "transfer_in_record", cache=group_source_cache
    )
    transfer_out_rows, transfer_out_error = _source_rows(
        evidence_materials, "transfer_out_record", cache=group_source_cache
    )
    nondrug_order_rows, nondrug_order_error = _source_rows(
        evidence_materials, "inpat_nondrug_order", cache=group_source_cache
    )
    first_course_rows, first_course_error = (
        _source_rows(evidence_materials, "first_course_record", cache=group_source_cache)
        if "LX0609-10-03-01" in selected
        else ((), "")
    )
    diagnosis_rows, diagnosis_error = _source_rows(
        evidence_materials, "diagnosis", cache=group_source_cache
    )
    # 074 的结构化变更声明只作为触发信号：该来源缺少诊断序号与诊断时间，
    # 绝不能挂成 diagnosis_rows。
    (
        admission_diagnosis_rows,
        admission_diagnosis_error,
    ) = (
        _source_rows(evidence_materials, "admission_record_diagnosis", cache=group_source_cache)
        if "LX0609-12-02-01" in selected
        else ((), "")
    )
    diffcase_rows, diffcase_error = _source_rows(
        evidence_materials, "diffcase_discussion_record", cache=group_source_cache
    )
    lab_item_rows, lab_item_error = _source_rows(
        evidence_materials, "labtest_item_report", cache=group_source_cache
    )
    lab_master_rows, lab_master_error = _source_rows(
        evidence_materials, "labtest_master", cache=group_source_cache
    )
    drug_order_rows, drug_order_error = _source_rows(
        evidence_materials, "inpat_drug_order", cache=group_source_cache
    )
    discharge_diagnosis_rows, discharge_diagnosis_error = _source_rows(
        evidence_materials, "discharge_record_diagnosis", cache=group_source_cache
    )
    bloodtrans_record_rows, bloodtrans_record_error = _source_rows(
        evidence_materials, "bloodtrans_record", cache=group_source_cache
    )
    death_state, death_time = _death_context(
        registration_rows=registration_rows,
        death_rows=death_rows,
        discharge_rows=discharge_rows,
    )
    ordinary_discharge_rule_ids = {"LX0609-08-01-01", "LX0609-08-02-01", "LX0609-08-02-02"}
    death_discharge_exclusion_refs = ()
    conflicting_death_time = False
    conflicting_discharge_outcome = False
    conflicting_discharge_condition = False
    if ordinary_discharge_rule_ids.intersection(selected) and death_state == "present":
        death_discharge_exclusion_refs, conflicting_death_time = _affirmative_death_record_refs(
            evidence_snapshot, evidence_materials, registration_rows,
        )
        conflicting_discharge_outcome = bool(death_discharge_exclusion_refs) and any(
            any(marker in _clean(row.get(field)) for marker in _EXPLICIT_ALIVE_DISCHARGE_MARKERS)
            and not any(marker in _clean(row.get(field)) for marker in _DEATH_MARKERS)
            for row in registration_rows
            for field in ("patient_status", "discharge_status", "discharge_type")
        )
        conflicting_discharge_condition = bool(death_discharge_exclusion_refs) and any(
            _clean(row.get("discharge_condition")) in {"治愈", "好转", "未愈", "存活"}
            for row in discharge_rows
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
    pending_results: list[Mapping[str, Any]] = []
    surgery_applicability = (
        resolve_surgery_applicability(
            snapshot=evidence_snapshot,
            materials=evidence_materials,
        )
        if {"LX0609-04-05-01", "LX0609-04-05-02", "LX0609-04-05-03"}.intersection(selected)
        else None
    )
    critical_value_rules = tuple(
        rule_id for rule_id in selected if rule_id in CRITICAL_VALUE_RULE_IDS
    )
    critical_value_family_outcome = (
        execute_critical_value_family(
            rule_ids=critical_value_rules,
            evidence_snapshot=evidence_snapshot,
            evidence_materials=evidence_materials,
            horizon_rows=horizon_rows,
            horizon_error=horizon_error,
            source_cache=group_source_cache,
        )
        if critical_value_rules
        else None
    )
    critical_value_decisions_by_rule = (
        {item.rule_id: item for item in critical_value_family_outcome.decisions}
        if critical_value_family_outcome is not None
        else {}
    )
    critical_value_display_by_rule = (
        dict(critical_value_family_outcome.display_facts)
        if critical_value_family_outcome is not None
        else {}
    )

    antimicrobial_rules = tuple(
        rule_id for rule_id in selected if rule_id in ANTIMICROBIAL_RULE_IDS
    )
    antimicrobial_family_outcome = (
        await execute_antimicrobial_family(
            rule_ids=antimicrobial_rules,
            evidence_snapshot=evidence_snapshot,
            evidence_materials=evidence_materials,
            llm_client=llm_client,
            source_cache=group_source_cache,
        )
        if antimicrobial_rules
        else None
    )
    antimicrobial_decisions_by_rule = (
        {item.rule_id: item for item in antimicrobial_family_outcome.decisions}
        if antimicrobial_family_outcome is not None
        else {}
    )
    antimicrobial_display_by_rule = (
        dict(antimicrobial_family_outcome.display_facts)
        if antimicrobial_family_outcome is not None
        else {}
    )

    for rule_id in selected:
        if rule_id == "LX0609-08-01-05":
            if death_state == "present" and not (death_error or registration_error):
                # 死亡病例（含有效死亡记录）不适用出院记录诊疗经过核对，与 08-01-01/02 口径一致。
                decisions.append(_decision(
                    rule_id=rule_id, snapshot=evidence_snapshot,
                    source_keys=("discharge_record",), final_state="not_applicable",
                    reason_code="eligibility_not_met",
                ))
                display.append((rule_id, {
                    "verification_kind": "discharge_course_pending",
                    "state": "not_applicable",
                }))
                continue
            if (
                not discharge_error
                and discharge_rows
                and all(_is_empty_discharge_shell_for_course(row) for row in discharge_rows)
            ):
                # 空壳出院记录缺少诊疗经过正文，不得判定不合规，应降级 data_gap。
                decisions.append(_decision(
                    rule_id=rule_id, snapshot=evidence_snapshot,
                    source_keys=("discharge_record",), final_state="data_gap",
                    reason_code="source_readiness_unproven",
                ))
                display.append((rule_id, {
                    "verification_kind": "discharge_course_pending",
                    "state": "data_gap",
                }))
                continue
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
            elif not uncertain_rows and not daily_scope_complete:
                final_state, reason_code = "data_gap", "source_unavailable"
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

        if rule_id in CRITICAL_VALUE_RULE_IDS:
            if rule_id in critical_value_display_by_rule:
                display.append((rule_id, critical_value_display_by_rule[rule_id]))
            decisions.append(critical_value_decisions_by_rule[rule_id])
            continue

        if rule_id in ANTIMICROBIAL_RULE_IDS:
            if rule_id in antimicrobial_display_by_rule:
                display.append((rule_id, antimicrobial_display_by_rule[rule_id]))
            decisions.append(antimicrobial_decisions_by_rule[rule_id])
            continue

        if rule_id == "LX0609-08-01-03":
            pending_results.append(build_luxian_0609_pending_definition_result(rule_id))
            continue

        if rule_id == "LX0609-07-01-03":
            source_keys = (
                "inpat_registration", "admission_record", "bloodtrans_record", "labtest_item_report",
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
            transfusion_source_error = bloodtrans_record_error
            # 无专用输血记录时实施事实靠病程兜底：病程读取失败不能当作“没有输血”或“全部已核”。
            course_fallback_error = "" if dedicated_performance_source else (daily_error or senior_error)
            order_source_error = nondrug_order_error or drug_order_error
            actual_transfusion_rows: tuple[Mapping[str, Any], ...] = ()
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
            elif not performance_rows:
                final_state, reason_code = (
                    ("data_gap", course_fallback_error) if course_fallback_error
                    else ("data_gap", "positive_assertion_not_explicit") if pending_order
                    else ("data_gap", order_source_error) if order_source_error
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
                actual_transfusion_rows = tuple(confirmed_records)
                extraction_failed = transfusion_performance_extraction.technical_failure
                if extraction_failed:
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
                            "performed_transfusion_events": list(actual_transfusion_rows),
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
                    if final_state == "compliant" and course_fallback_error:
                        # 读取失败的病程里可能还有未核对的输血事件，不能确认合规。
                        final_state, reason_code, facts = "data_gap", course_fallback_error, None
                    if facts is not None:
                        display.append((rule_id, dict(facts)))
            decisions.append(_decision(
                rule_id=rule_id, snapshot=evidence_snapshot,
                source_keys=source_keys,
                final_state=final_state, reason_code=reason_code,
                exact_document_refs=bool(consumed_bloodtrans_rows) and not transfusion_source_error,
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
            # 以原始医嘱及文书记载核对；不以首页编码触发。
            final_state, reason_code = "", ""
            invasive_document_refs: tuple[str, ...] = ()
            affirmative_invasive_window = False
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
                candidate_records = tuple(
                    (source, row)
                    for source, rows in (
                        ("first_course_record", first_course_rows),
                        ("daily_course_record", daily_rows),
                        ("senior_course_record", senior_rows),
                        ("postsurg_firstcourse_record", postop_first_rows),
                        ("surgery_record", surgery_record_rows),
                    )
                    for row in rows
                )
                documentation = await check_invasive_procedure_records(
                    triggers, tuple(row for _source, row in candidate_records), llm_client,
                )
                invasive_extractions.append(documentation)
                states = dict(documentation.states)
                # 逐次（目录项+操作日）核对；客户事实沿用按目录项去重的名称形状。
                names = list(dict.fromkeys(trigger.procedure.name for trigger in triggers))
                missing_triggers = [
                    trigger for trigger in triggers
                    if states.get(_invasive_trigger_key(trigger)) == "not_documented"
                ]
                missing = [trigger.procedure.name for trigger in missing_triggers]
                mature_missing = list(dict.fromkeys(
                    trigger.procedure.name for trigger in missing_triggers
                    if not antimicrobial_horizon_error and antimicrobial_evaluation_horizon is not None
                    and frozen_window_is_mature(antimicrobial_evaluation_horizon, datetime.combine(
                        trigger.anchor_date + timedelta(days=INVASIVE_RECORD_WINDOW_DAYS), datetime.min.time()))
                ))
                if documentation.state == "technical_error":
                    final_state, reason_code = "technical_error", documentation.reason_code
                elif documentation.state == "unresolved":
                    final_state, reason_code = "data_gap", documentation.reason_code
                elif missing and (antimicrobial_horizon_error or antimicrobial_evaluation_horizon is None):
                    final_state, reason_code = "data_gap", antimicrobial_horizon_error or "authoritative_time_missing"
                elif missing and not mature_missing:
                    if any(state == "uncertain" for state in states.values()):
                        final_state, reason_code = "data_gap", "semantic_extraction_unresolved"
                    elif any(
                        after_frozen_horizon(
                            datetime.combine(trigger.anchor_date, datetime.min.time()),
                            antimicrobial_evaluation_horizon,
                        )
                        for trigger in triggers
                    ):
                        final_state, reason_code = "data_gap", "authoritative_time_conflict"
                    else:
                        final_state, reason_code = "not_applicable", "evaluation_window_not_mature"
                elif missing and not all(evidence_materials.permits_absence(source) for source in (
                    "first_course_record", "daily_course_record", "senior_course_record",
                    "postsurg_firstcourse_record", "surgery_record",
                )):
                    final_state, reason_code = "data_gap", "source_unavailable"
                elif missing:
                    final_state, reason_code = "non_compliant", "required_document_missing"
                    display.append((rule_id, {
                        "failure_kind": "invasive_procedure_record_missing",
                        "procedures": names,
                        "procedure_count": len(names),
                        "missing_procedures": mature_missing,
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
                if final_state == "compliant" or reason_code == "evaluation_window_not_mature":
                    invasive_binding = bind_consumed_continuity_document_rows(
                        snapshot=evidence_snapshot,
                        materials=evidence_materials,
                        consumed_rows=(
                            *(("inpat_nondrug_order", row) for trigger in triggers for row in trigger.orders),
                            *(candidate_records[index] for index in documentation.selected_record_indexes),
                        ),
                    )
                    if invasive_binding.binding_failed or not invasive_binding.document_refs:
                        final_state, reason_code = "technical_error", "snapshot_mismatch"
                    else:
                        invasive_document_refs = invasive_binding.document_refs
                        if reason_code == "evaluation_window_not_mature":
                            horizon_refs = _fact_refs(evidence_snapshot, ("evaluation_context.horizon",))
                            affirmative_invasive_window = bool(horizon_refs)
                            invasive_document_refs += horizon_refs
            decisions.append(_decision(
                rule_id=rule_id, snapshot=evidence_snapshot,
                source_keys=(
                    "inpat_nondrug_order", "first_course_record", "daily_course_record",
                    "senior_course_record", "postsurg_firstcourse_record", "surgery_record",
                    "evaluation_context.horizon",
                ),
                final_state=final_state, reason_code=reason_code,
                document_refs=invasive_document_refs,
                exact_document_refs=bool(invasive_document_refs),
                affirmative_applicability=affirmative_invasive_window,
            ))
            continue

        if rule_id == "LX0609-10-04-01":
            from .extended_document.stage_summary_timeliness import evaluate_stage_summary_timeliness

            source_keys = ("summary_record", "handoff_record", "handover_record", "transfer_in_record", "transfer_out_record")
            all_sources = (*source_keys, "inpat_registration", "admission_record", "evaluation_context.horizon")
            try:
                documents = {source: _source_rows(evidence_materials, source) for source in source_keys}
                source_error = registration_error or admission_error or horizon_error or next(
                    (error for _, error in documents.values() if error), "",
                )
                outcome = evaluate_stage_summary_timeliness(
                    registration_rows=registration_rows, admission_rows=admission_rows,
                    document_rows={source: rows for source, (rows, _) in documents.items()},
                    horizon_rows=horizon_rows, source_error=source_error,
                )
                binding = bind_consumed_continuity_document_rows(
                    snapshot=evidence_snapshot, materials=evidence_materials,
                    consumed_rows=outcome.consumed_rows,
                )
                selected_refs = binding.document_refs
                if binding.binding_failed:
                    raise EvidenceMaterialUnavailable("selected_stage_document_unavailable")
            except Exception:
                decisions.append(_decision(rule_id=rule_id, snapshot=evidence_snapshot, source_keys=all_sources,
                    final_state="technical_error", reason_code="native_stage_summary_failure"))
                continue
            if outcome.display_facts is not None:
                display.append((rule_id, outcome.display_facts))
            decisions.append(_decision(rule_id=rule_id, snapshot=evidence_snapshot, source_keys=all_sources,
                final_state=outcome.final_state, reason_code=outcome.reason_code,
                document_refs=selected_refs, exact_document_refs=bool(selected_refs)))
            continue

        if rule_id == "LX0609-04-02-09":
            from .extended_document.death_record_timeliness import evaluate_death_record_timeliness

            try:
                effective_death_rows = _filter_death_rows_for_timeliness(death_rows)
                source_error = registration_error or death_error or discharge_error
                outcome = evaluate_death_record_timeliness(
                    death_rows=effective_death_rows, discharge_rows=discharge_rows,
                    registration_rows=registration_rows,
                    source_error=source_error,
                    frozen_at=evidence_snapshot.created_at,
                )
                # 活人出院病例（含无 document_title 的可见普通出院记录）与 04-02-06/04-02-08 保持一致判 not_applicable；
                # 若出院记录全为被冻结截断的未来死亡文书（无可见普通出院记录），仍保持 data_gap(source_empty)。
                from .basic_timeliness_facts import parse_authoritative_datetime as _parse_auth_dt

                frozen_cutoff = _parse_auth_dt(evidence_snapshot.created_at) if evidence_snapshot.created_at else None
                has_visible_ordinary_discharge = False
                for _drow in discharge_rows:
                    _dtitle = _clean(_drow.get("document_title"))
                    if "死亡" in _dtitle:
                        continue
                    _dclock_raw = authoritative_document_time_value(_drow) or _drow.get("discharge_time") or _drow.get("discharge_datetime")
                    _dclock = _parse_auth_dt(_dclock_raw) if _dclock_raw else None
                    if frozen_cutoff is not None and _dclock is not None and _dclock > frozen_cutoff:
                        continue
                    has_visible_ordinary_discharge = True
                    break
                if (
                    not source_error
                    and outcome.final_state == "data_gap"
                    and outcome.reason_code == "source_empty"
                    and death_state == "absent"
                    and has_visible_ordinary_discharge
                ):
                    decisions.append(_decision(
                        rule_id=rule_id, snapshot=evidence_snapshot,
                        source_keys=("inpat_registration", "death_record", "discharge_record"),
                        final_state="not_applicable", reason_code="trigger_absent_complete",
                    ))
                    continue
                # 只绑定执行器实际消费的原始行，避免同ID未来版本重新混入证据。
                binding = bind_consumed_continuity_document_rows(
                    snapshot=evidence_snapshot, materials=evidence_materials,
                    consumed_rows=outcome.consumed_rows,
                )
                selected_refs = binding.document_refs
                if binding.binding_failed:
                    raise EvidenceMaterialUnavailable("selected_death_document_unavailable")
            except Exception:
                # 新规则意外故障只影响自身，不重新裁定相邻死亡/出院规则。
                decisions.append(_decision(
                    rule_id=rule_id, snapshot=evidence_snapshot,
                    source_keys=("death_record", "discharge_record", "inpat_registration"),
                    final_state="technical_error", reason_code="native_death_timeliness_failure",
                ))
                continue
            if outcome.display_facts is not None:
                display.append((rule_id, outcome.display_facts))
            decisions.append(_decision(
                rule_id=rule_id, snapshot=evidence_snapshot,
                source_keys=("death_record", "discharge_record", "inpat_registration"),
                final_state=outcome.final_state, reason_code=outcome.reason_code,
                # 空集合也是执行器的明确选择，不能退回整个来源重新带入未来文书。
                document_refs=selected_refs, exact_document_refs=True,
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
                death_document_rows = tuple(
                    (ref, row)
                    for ref, row in evidence_materials.document_rows(
                        "death_record", snapshot=evidence_snapshot
                    )
                    if not _is_ghost_death_row(row)
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
                    exact_document_refs=bool(outcome.document_refs),
                    positive_document_refs=(
                        outcome.document_refs if outcome.status == "non_compliant" else ()
                    ),
                )
            )
            continue

        if rule_id == "LX0609-04-02-06" and death_error:
            decisions.append(_decision(rule_id=rule_id, snapshot=evidence_snapshot, source_keys=("death_record",), final_state="data_gap", reason_code=death_error))
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
            effective_horizon_rows = _resolve_death_discussion_horizon_rows(
                horizon_rows=horizon_rows,
                horizon_error=horizon_error,
                death_time=death_time,
                snapshot=evidence_snapshot,
                registration_rows=registration_rows,
                death_rows=death_rows,
            )
            outcome = evaluate_death_discussion_timeliness(
                death_time=death_time,
                death_rows=death_rows,
                discussion_rows=discussion_rows,
                discussion_error=discussion_error,
                horizon_rows=effective_horizon_rows,
                horizon_error=horizon_error,
            )
            if (
                outcome.final_state == "non_compliant"
                and outcome.reason_code == "required_document_missing"
                and not discussion_rows
                and not evidence_materials.permits_absence("death_discussion")
            ):
                # 死亡讨论表未确认全量同步（empty_unconfirmed）时，窗口届满仍降级为资料不足。
                outcome = replace(
                    outcome,
                    final_state="data_gap",
                    reason_code="source_unavailable",
                    display_facts=None,
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

        if rule_id in ordinary_discharge_rule_ids:
            outcome_conflict = conflicting_discharge_outcome or conflicting_discharge_condition
            if outcome_conflict or conflicting_death_time or death_state == "conflict":
                decisions.append(_decision(
                    rule_id=rule_id, snapshot=evidence_snapshot,
                    source_keys=(
                        "inpat_registration", "death_record",
                        *(("discharge_record",) if conflicting_discharge_condition else ()),
                    ),
                    final_state="data_gap", reason_code=(
                        "association_failed" if outcome_conflict else "authoritative_time_conflict"
                    ),
                ))
                continue
            if (
                death_discharge_exclusion_refs
                and not (death_error or registration_error or discharge_error)
                and (source_scope("inpat_registration") or {}).get("status")
                not in {"table_missing", "columns_missing"}
            ):
                decisions.append(_decision(
                    rule_id=rule_id, snapshot=evidence_snapshot, source_keys=(),
                    final_state="not_applicable", reason_code="trigger_absent_complete",
                    document_refs=death_discharge_exclusion_refs, exact_document_refs=True,
                    affirmative_applicability=True,
                ))
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
                    or ("authoritative_time_missing" if discharge_time_source.endswith(("date_only", "horizon_date_only")) else "")
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
            has_explicit_late_document = (
                outcome.reason_code == "threshold_exceeded"
                and outcome.display_facts is not None
                and any(
                    _clean(row.get("record_content") or row.get("content"))
                    and (completion := _parse_datetime(authoritative_document_time_value(row))) is not None
                    and completion.isoformat(sep=" ") == outcome.display_facts["record_time"]
                    for row in discharge_rows
                )
            )
            if (
                (outcome.final_state == "compliant" or has_explicit_late_document)
                and discharge_document_refs
                and discharge_time_source in {
                    "evaluation_context.horizon", "discharge_record.discharge_datetime",
                    "discharge_record.discharge_time",
                }
                and (source_scope("inpat_registration") or {}).get("status") == "empty_unconfirmed"
                and any(
                    item.source_key == "inpat_registration"
                    and item.query_state.value == "empty"
                    and item.completeness is SourceCompleteness.COMPLETE
                    for item in evidence_snapshot.observations
                )
            ):
                # 备用登记正常零行时，采用实际锚点及已核对的出院记录版本。
                source_keys = ("discharge_record", "evaluation_context.horizon") if (
                    discharge_time_source == "evaluation_context.horizon"
                ) else ("discharge_record",)
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
            prescription_source_keys = ("inpat_prescription", "inpat_prescription_item")
            oral_prescription_names = _discharge_oral_prescription_names(evidence_materials)
            (
                formal_prescription_medications,
                formal_prescription_error,
                affected_prescription_item_count,
            ) = _formal_discharge_prescription_medications(evidence_materials)
            if death_state == "present" and not (death_error or registration_error or discharge_error):
                decisions.append(
                    _decision(
                        rule_id=rule_id,
                        snapshot=evidence_snapshot,
                        source_keys=("inpat_registration", "discharge_record"),
                        final_state="not_applicable",
                        reason_code="trigger_absent_complete",
                    )
                )
                continue
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
            body_only_medication_scope = (
                any(_clean(row.get("discharge_order_source")).startswith("record_content:")
                    for row in discharge_rows)
                and not formal_prescription_medications
                and formal_prescription_error == "source_unavailable"
                and all(
                    observation.query_state.value in {"unavailable", "empty"}
                    for observation in evidence_snapshot.observations
                    if observation.source_key in prescription_source_keys
                )
            )
            normal_empty_prescriptions = all(
                (source_scope(source) or {}).get("status") == "empty_unconfirmed"
                and any(
                    observation.source_key == source
                    and observation.query_state.value == "empty"
                    and observation.completeness is SourceCompleteness.COMPLETE
                    for observation in evidence_snapshot.observations
                )
                for source in prescription_source_keys
            )
            body_only_medication_scope = body_only_medication_scope or normal_empty_prescriptions
            if body_only_medication_scope:
                # 只核对实际出院文书的带药内容，不把未知处方范围报成“处方0项”。
                formal_prescription_error = ""
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
            explicit_no_medications = False
            grounded_no_medications = False
            positive_body_defect = False
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
                            exact_document_refs=bool(selected_discharge_document_refs),
                            positive_document_refs=selected_discharge_document_refs,
                        ))
                        continue
                if medication_extraction.state in {"ready", "absent"}:
                    medications = list(medication_extraction.medications)
                    medication_error = ""
                    # absent=原文明确写明无出院带药（如拒绝带药），不同于出院记录对带药只字未提。
                    explicit_no_medications = medication_extraction.state == "absent" and not medications
                    if explicit_no_medications:
                        medication_clauses = tuple(
                            clause.strip()
                            for clause in re.split(r"[。；;！!\n]", str(discharge_rows[0]["discharge_order"]))
                            if _DISCHARGE_MEDICATION_SIGNAL_PATTERN.search(clause)
                        )
                        grounded_no_medications = bool(medication_clauses) and all(
                            _EXPLICIT_NO_DISCHARGE_MEDICATION_PATTERN.fullmatch(clause)
                            for clause in medication_clauses
                        )
                else:
                    # 定向补核后仍不确定：按资料不足交付（uncertain 不得交付，2026-10-23 C15）。
                    final_state = {
                        "unknown": "data_gap",
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
                        reason_code=(
                            "semantic_extraction_unresolved" if medication_extraction.state == "unknown"
                            else medication_extraction.reason_code
                        ),
                        document_refs=selected_discharge_document_refs,
                    ))
                    continue
            if medication_error:
                final_state, reason_code = "data_gap", medication_error
            elif (
                not medications
                and not explicit_no_medications
                and all(_is_empty_body_discharge_row(row) for row in discharge_rows)
                and (
                    bool(formal_prescription_medications)
                    or all(
                        _is_empty_template_discharge_order(row.get("discharge_order"))
                        for row in discharge_rows
                    )
                )
            ):
                # 出院记录正文为空壳时，不得据正式处方反推“漏写带药”并判不合规，降级为资料不足。
                final_state, reason_code = "data_gap", "required_field_missing"
            elif not medications and (
                explicit_no_medications
                or (not formal_prescription_medications and not formal_prescription_error)
            ):
                # 既有口径：原文明确无带药时，正式处方不能把它改写成漏写（062处方一致性用例）；
                # 只有出院记录未写任何带药、而正式出院处方存在时，才按整组漏写核对（F5）。
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
                positive_body_defect = any(
                    _clean(item.get("drug_name"))
                    and not _discharge_medications_complete((item,))
                    for item in medications
                )
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
                    positive_body_defect = positive_body_defect and not missing_drug_names
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
                                **({"prescription_medication_count": len(formal_prescription_medications),
                                    "missing_drug_names": list(missing_drug_names)}
                                   if not body_only_medication_scope else {}),
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
            affirmative_no_medications = False
            if grounded_no_medications and selected_discharge_document_refs:
                prescription_rows, prescription_read_error = _source_rows(evidence_materials, "inpat_prescription")
                items, item_read_error = _source_rows(evidence_materials, "inpat_prescription_item")
                affirmative_no_medications = (
                    not (prescription_read_error or item_read_error or formal_prescription_error)
                    and not any(_is_effective_discharge_prescription(row) for row in prescription_rows)
                    and (bool(prescription_rows) or not items)
                    and all(
                        (source_scope(source) or {}).get("status") not in {"table_missing", "columns_missing"}
                        for source in prescription_source_keys
                    )
                )
            exact_body_evidence = bool(selected_discharge_document_refs) and (
                affirmative_no_medications
                or (positive_body_defect and final_state == "non_compliant")
                or (body_only_medication_scope and final_state == "compliant")
            )
            decisions.append(
                _decision(
                    rule_id=rule_id,
                    snapshot=evidence_snapshot,
                    source_keys=(
                        ("discharge_record",)
                        if reason_code == "trigger_absent_complete" or body_only_medication_scope
                        else ("discharge_record", *prescription_source_keys)
                    ),
                    final_state=final_state,
                    reason_code=reason_code,
                    document_refs=(
                        ()
                        if reason_code == "trigger_absent_complete" and not affirmative_no_medications
                        else selected_discharge_document_refs
                    ),
                    exact_document_refs=exact_body_evidence,
                    positive_document_refs=(
                        selected_discharge_document_refs
                        if positive_body_defect and final_state == "non_compliant"
                        else ()
                    ),
                    affirmative_applicability=affirmative_no_medications,
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
                    surgery_record_rows=surgery_record_rows,
                )
                if any(event.surgery_time_estimated for event in surgery_events):
                    postoperative_time_estimated_rules.add(rule_id)
                linkage_error = postop_first_error or ("authoritative_time_missing" if not surgery_events else "")
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
                    if unmet_events and not evidence_materials.permits_absence("postsurg_firstcourse_record"):
                        final_state, reason_code = "data_gap", "source_unavailable"
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
            affirmative_non_surgical_operation = False
            if (
                gate_outcome == ("not_applicable", "performed_event_absent")
                and surgery_applicability.procedure_kind == "non_surgical_operation"
            ):
                selected_postoperative_rows.extend(
                    row
                    for row in surgery_record_rows
                    if catalog_surgery_state(row) is False
                )
                affirmative_non_surgical_operation = (
                    bool(selected_postoperative_rows)
                    and len(selected_postoperative_rows) == len(surgery_record_rows)
                    and evidence_materials.permits_absence("surgery_record")
                )
                if not affirmative_non_surgical_operation:
                    final_state, reason_code = "data_gap", "source_readiness_unproven"
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
                    affirmative_applicability=(
                        affirmative_non_surgical_operation and bool(postoperative_document_refs)
                    ),
                )
            )
            continue

        if rule_id in {"LX0609-04-05-01", "LX0609-04-05-02"}:
            assert surgery_applicability is not None
            gate_outcome = _surgery_applicability_outcome(surgery_applicability)
            surgery_events = _postoperative_surgery_events(
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
                    for row in surgery_record_rows
                    if catalog_surgery_state(row) is False
                )
            if gate_outcome is not None:
                final_state, reason_code = gate_outcome
            elif not surgery_events:
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
                and _postoperative_window_gate(
                    surgery_events=(event,), horizon_rows=horizon_rows, horizon_error=horizon_error,
                ) is None
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
                    if unmet_events:
                        # 逐台确定缺失（窗口到期、窗口内无任何查房、也无可能落入窗口的无日期查房）
                        # 不受其他台正文未决或模型失败影响。
                        final_state, reason_code = (
                            "non_compliant",
                            "required_document_missing",
                        )
                    elif body_issue:
                        final_state, reason_code = ("technical_error" if extraction.state == "technical_error" else "data_gap"), body_issue
                    elif unresolved_senior_semantics:
                        final_state, reason_code = "data_gap", "semantic_extraction_unresolved"
                    elif unresolved_senior_time:
                        final_state, reason_code = "data_gap", "authoritative_time_missing"
                    elif unresolved_senior_body:
                        final_state, reason_code = "data_gap", "required_field_missing"
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
                    if unmet_events or (
                        not body_issue and not unresolved_senior_semantics
                        and (not unresolved_senior_body or unresolved_senior_time)
                    ):
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
                    pending_window_events = []
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
                        event_window = _postoperative_window_gate(
                            surgery_events=(event,), horizon_rows=horizon_rows,
                            horizon_error=horizon_error,
                        )
                        if event_window is not None:
                            pending_window_events.append(event.document_id)
                            event_facts.append({
                                **_event_display_base(event),
                                "required_postop_dates": sorted(value.isoformat() for value in required_dates),
                                "covered_postop_dates": [],
                                "surgeon_round_present": None,
                                "preop_surgeon_round_present": None,
                                "window_state": "evaluation_window_not_mature",
                            })
                            continue
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
                                        | _body_surgeon_round_tokens(
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
                    if (definite_missing_events or unmet_events) and rule_id == "LX0609-04-05-01" and not daily_scope_complete:
                        final_state, reason_code = "data_gap", "source_unavailable"
                    elif definite_missing_events:
                        # 已确定某个术后日完全没有病程记录，属确定缺陷，不被术者身份等
                        # 其他资料缺口遮蔽。
                        final_state, reason_code = "non_compliant", "requirement_violated"
                    elif missing_surgeon_events or empty_body_events or unresolved_time_events:
                        final_state, reason_code = (
                            "data_gap",
                            "required_field_missing",
                        )
                    elif not unmet_events and pending_window_events:
                        final_state, reason_code = "not_applicable", "evaluation_window_not_mature"
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
            qualified_body_refs: tuple[str, ...] = ()
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
                        qualified_body_refs = tuple(
                            body_refs[(source, ordinal)]
                            for source, ordinal, row in dated_candidates
                            if body_states[(source, ordinal)] == "present"
                            and not _clean(row.get("document_id") or row.get("id"))
                        )[:8]
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
                daily_scope_complete=daily_scope_complete,
            )
            if body_issue:
                outcome = PredischargeCourseOutcome("technical_error" if extraction.state == "technical_error" else "data_gap", body_issue)
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
                selected_document_refs = (*selected_document_refs, *qualified_body_refs)[:8]
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
                    # 无 ID 时可使用已经核对的原行坐标；重复自然 ID 保持既有保守投影。
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
            passage_facts: dict[str, Any] = {}
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
                        if isinstance(text := row.get("record_content"), str) and text.strip()
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
                                llm_client, numbered_passages=True,
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
                            passage_spans = tuple(
                                (source_key, version, *assertion.source_span)
                                for source_key, row, _, assertion in extracted_candidates
                                if assertion.source_span and (version := _clean(
                                    row.get("source_version_key") or row.get("document_id") or row.get("id")
                                ))
                            )
                            if passage_spans:
                                passage_facts["_approval_passages"] = passage_spans
                            semantic_match = next(
                                (
                                    (source_key, "senior_approval", row)
                                    for source_key, row, row_time, assertion
                                    in extracted_candidates
                                    if row_time is not None
                                    and assertion.role == "senior"
                                    and assertion.opinion == "approved"
                                ),
                                None,
                            )
                            # 同意与否以模型意见为准，不再用正则复核语义（用户口径 2026-10-22）；
                            # 引文未写明上级医师称谓的日常病程意见不是上级同意。
                            semantic_undated = tuple(
                                (source_key, row)
                                for source_key, row, row_time, assertion
                                in extracted_candidates
                                if row_time is None
                                and assertion.role == "senior"
                                and assertion.opinion == "approved"
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
                        **passage_facts,
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
                    elif any(not _row_text(row) for rows in (daily_rows, senior_rows) for row in rows
                             if _row_time(row) is not None and _row_time(row).date() in valid_dates):
                        final_state, reason_code = "data_gap", "required_field_missing"
                    elif window_course_count and llm_client is None:
                        # 上级同意只能由模型抽取确认；无模型时不能据未读到意见判缺。
                        window_course_count = 0
                        final_state, reason_code = "data_gap", "semantic_extraction_unresolved"
                    elif window_course_count and not daily_scope_complete:
                        final_state, reason_code = "data_gap", "source_unavailable"
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
                    render_display = final_state != "data_gap" or reason_code != "source_unavailable"
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
                                **passage_facts,
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
                daily_scope_complete=daily_scope_complete,
                handoff_rows=handoff_rows,
                handoff_error=handoff_error,
                handover_rows=handover_rows,
                handover_error=handover_error,
                evaluation_horizon_datetime=antimicrobial_evaluation_horizon,
                evaluation_horizon_error=antimicrobial_horizon_error or "",
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
            pending_handoff_refs: tuple[str, ...] = ()
            if outcome.pending_change_rows and outcome.pending_binding_facts:
                pending_facts = outcome.pending_binding_facts
                event_facts = pending_facts.get("events")
                needed_record_count = (
                    sum(bool(event.get(field)) for event in event_facts for field in ("handoff_time", "handover_time"))
                    if event_facts is not None
                    else len(pending_facts.get("handoff_times", ())) + len(pending_facts.get("handover_times", ()))
                )
                selections = tuple(
                    (reference["source_type"], reference["source_document_id"])
                    for reference in pending_facts.get("source_document_refs", ())
                )
                selected_handoff_rows = tuple(
                    (source, row)
                    for source, rows in (("handoff_record", handoff_rows), ("handover_record", handover_rows))
                    for row in rows
                    if (source, _clean(row.get("document_id") or row.get("id"))) in selections
                )
                if (
                    len(selected_handoff_rows) == len(selections) == needed_record_count
                    and any(source == "handoff_record" for source, _row in selected_handoff_rows)
                ):
                    pending_binding = bind_consumed_continuity_document_rows(
                        snapshot=evidence_snapshot,
                        materials=evidence_materials,
                        consumed_rows=(
                            *((outcome.change_source_key, row) for row in outcome.pending_change_rows),
                            *selected_handoff_rows,
                        ),
                    )
                    horizon_refs = _fact_refs(evidence_snapshot, ("evaluation_context.horizon",))
                    if pending_binding.document_refs and horizon_refs:
                        pending_handoff_refs = (*pending_binding.document_refs, *horizon_refs)
            decisions.append(
                _decision(
                    rule_id=rule_id,
                    snapshot=evidence_snapshot,
                    source_keys=(
                        (outcome.change_source_key, "evaluation_context.horizon")
                    ),
                    document_refs=pending_handoff_refs or handoff_binding.document_refs,
                    # physician_change_event 尚未纳入客户文书投影白名单。保留它的
                    # snapshot 判定锚点，并只让已匹配的交/接班文书进入公共证据；
                    # 兼容字段待后续结构提交统一删除。
                    exact_document_refs=bool(pending_handoff_refs),
                    affirmative_applicability=bool(pending_handoff_refs),
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
            transfer_visibility_date = None
            transfer_visibility_error = None
            if rule_id == "LX0609-10-02-01" and len(horizon_rows) == 1 and horizon_rows[0].get("basis") == "discharge_date":
                try:
                    transfer_visibility_date = date.fromisoformat(str(horizon_rows[0].get("task_frozen_date") or ""))
                except ValueError:
                    transfer_visibility_error = "authoritative_time_missing"
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
                evaluation_horizon_error=transfer_horizon_error or transfer_visibility_error,
                evaluation_visibility_date=transfer_visibility_date,
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
                consumed_rows=outcome.consumed_rows,
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
                    if not declared_diagnosis_names and not daily_scope_complete:
                        final_state, reason_code = "data_gap", "source_unavailable"
                    elif not declared_diagnosis_names:
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
                            )
                            for name in declared_diagnosis_names
                        }
                        structured_pairs = tuple(
                            (source_key, row, text, name)
                            for name, candidates in declared_candidates.items()
                            for _time, text, source_key, row in candidates[:_DIAGNOSIS_CHANGE_CANDIDATES_PER_CHANGE]
                        )
                        if not all(declared_candidates.values()) and not daily_scope_complete:
                            final_state, reason_code = "data_gap", "source_unavailable"
                            structured_facts = None
                        elif not all(declared_candidates.values()):
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
                                incomplete_names=frozenset(name for name, candidates in declared_candidates.items() if len(candidates) > _DIAGNOSIS_CHANGE_CANDIDATES_PER_CHANGE or not daily_scope_complete),
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
                                freeze_scope=evidence_snapshot.visit_ref if evidence_snapshot is not None else None,
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
                            if "missing" in assertion_states and not daily_scope_complete:
                                final_state, reason_code = "data_gap", "source_unavailable"
                            elif "missing" in assertion_states:
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
                    selected_candidates: list[tuple[datetime | None, str, str, Mapping[str, Any]]] = []
                    table_pairs: list[tuple[str, Mapping[str, Any], str, str]] = []
                    untimed_only = False
                    incomplete_names: set[str] = set()
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
                        if len(timed) > _DIAGNOSIS_CHANGE_CANDIDATES_PER_CHANGE or len(timed) < len(candidates):
                            incomplete_names.add(diagnosis_name)
                        timed = timed[:_DIAGNOSIS_CHANGE_CANDIDATES_PER_CHANGE]
                        if timed:
                            table_pairs.extend(
                                (source_key, row, text, diagnosis_name)
                                for _time, text, source_key, row in timed
                            )
                            selected_candidates.extend(
                                item for item in timed
                                if not any(item[3] is seen[3] for seen in selected_candidates)
                            )
                        elif candidates:
                            untimed_only = True
                            selected_candidates.extend(candidates)
                        else:
                            unmentioned = True
                            # 仅有变更之前的提及：不能证明本次变更的理由，作为不合规证据展示。
                            selected_candidates.extend(mentions)
                    candidate_rows = tuple(selected_candidates)
                    if unmentioned and not daily_scope_complete:
                        final_state, reason_code = "data_gap", "source_unavailable"
                    elif unmentioned:
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
                            table_pairs, change_names, llm_client, incomplete_names=frozenset(incomplete_names if daily_scope_complete else change_names),
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
        results=tuple(pending_results),
        planned_rule_ids=selected,
        decisions=tuple(decisions),
        customer_display_facts=tuple(display),
        llm_call_count=sum(
            item.llm_call_count
            for item in (
                course_content_extraction,
                antimicrobial_family_outcome,
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
                antimicrobial_family_outcome,
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
                antimicrobial_family_outcome,
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
                antimicrobial_family_outcome,
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
                antimicrobial_family_outcome,
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
