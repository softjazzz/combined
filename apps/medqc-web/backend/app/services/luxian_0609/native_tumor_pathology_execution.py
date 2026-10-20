"""LX0609 肿瘤病理族原生执行：受控来源门控后逐规则裁剪判定。"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
import json
import logging
import re
import sys
from typing import Any, Mapping, Protocol, Sequence

from .evidence_material import (
    EvidenceMaterialTruncated,
    EvidenceMaterialUnavailable,
    Luxian0609EvidenceMaterialStore,
)
from .evidence_snapshot import Luxian0609EvidenceSnapshot
from .decision_model import (
    ApplicabilityState,
    EvidenceState,
    QcDirection,
    RuleDecision,
)
from .native_execution import build_luxian_0609_native_result
from .malignancy_fact import (
    MalignancyFactResolver,
    MalignancySource,
    build_stage_malignancy_sources,
    resolve_malignancy_visit_stage,
)
from .chemotherapy_administration_facts import CourseDocument, extract_chemotherapy_administrations
from .pathology_documentation_extraction import (
    PathologyDocument,
    PathologyEvent,
    extract_pathology_documentation_facts,
)
from .source_evidence_reader import (
    authoritative_document_time_value,
    SourceEvidenceUnavailable,
    read_luxian_0609_native_source_rows,
)
from .pathology_report_completeness import (
    PATHOLOGY_COMPLETENESS_SOURCES,
    PATHOLOGY_REPORT_COMPLETENESS_RULE_ID,
    evaluate_pathology_report_completeness,
)



logger = logging.getLogger(__name__)

TUMOR_PATHOLOGY_RULE_IDS = (
    "LX0609-06-02-03",
    "LX0609-06-02-02",
    "LX0609-05-02-01",
    "LX0609-08-01-04",
)
EXECUTABLE_TUMOR_PATHOLOGY_RULE_IDS = (
    *TUMOR_PATHOLOGY_RULE_IDS,
    PATHOLOGY_REPORT_COMPLETENESS_RULE_ID,
)
EXECUTOR_KEY = "tumor_pathology"
_TYPED_DECISION_RULE_IDS = frozenset(EXECUTABLE_TUMOR_PATHOLOGY_RULE_IDS)
_TYPED_RULE_SOURCE_KEYS = {
    PATHOLOGY_REPORT_COMPLETENESS_RULE_ID: PATHOLOGY_COMPLETENESS_SOURCES,
    "LX0609-06-02-03": (
        "pathology_exam_master",
        "pathology_exam_report",
        "surgery_record",
        "daily_course_record",
        "senior_course_record",
    ),
    "LX0609-06-02-02": (
        "pathology_exam_master",
        "pathology_exam_report",
        "surgery_record",
        "daily_course_record",
    ),
    "LX0609-05-02-01": (
        "admission_record_diagnosis",
        "diagnosis",
        "discharge_record_diagnosis",
        "pathology_exam_report",
        "inpat_registration.discharge_horizon",
        "discharge_record",
        "inpat_drug_order",
        "daily_course_record",
    ),
    "LX0609-08-01-04": (
        "diagnosis",
        "discharge_record_diagnosis",
        "pathology_exam_report",
        "inpat_registration.discharge_horizon",
        "discharge_record",
    ),
}
_TYPED_EVALUATOR_VERSION = "tumor-pathology-ruledecision-shadow-v1"

_PATHOLOGY_SOURCES = ("pathology_exam_master", "pathology_exam_report")
_PATHOLOGY_TARGET_SOURCES = ("surgery_record", "daily_course_record")
_PATHOLOGY_RESULT_TARGET_SOURCES = (*_PATHOLOGY_TARGET_SOURCES, "senior_course_record")
# 院方口径（2026-10-10）：病理取材只核对手术记录和日常病程，不看上级医师查房记录。
_LX019_PATHOLOGY_TARGET_SOURCES = _PATHOLOGY_TARGET_SOURCES
_CHEMO_TARGET_SOURCES = ("inpat_drug_order", "daily_course_record")
_DISCHARGE_TARGET_SOURCES = ("diagnosis", "discharge_record")
_MAX_ROWS_PER_SOURCE = 8
_MAX_ROW_CHARS = 1400
_MAX_CONTEXT_CHARS = 18000
# 027「明示可疑」判别器的取文口径（A 案，见
# `docs/plans/2026-09-12-0910-issue-backlog.md` §15.3）：出院记录的**叙事列**。
# 实测（`s027_probe_discharge_columns.py`，只读）：本样本库 `record_content` 30/30 为空，
# 正文实际落在 `treatment_course`（30/30）与 `discharge_order`（30/30）；只扫
# `record_content` 会得到假的「无证据」（M1 调查报告 §4.1）。
#
# 这里只取执行器**实际已加载**的列：`source_evidence_reader._NATIVE_SOURCE_FIELDS
# ["discharge_record"]` 的当前白名单（见下方 `_DISCHARGE_LOADED_COLUMNS`）。
# 该表在 `cdm.discharge_record` 上确实存在、但**不在加载白名单**内的列
# （`admission_condition`/`positive_assist_exam`/`discharge_condition`/
# `condition_transform`）不在此列表：本样本库它们 0/30 非空或未加载，引用它们
# 只会造成「扫描了但读不到」的假安全感。若后续需要扩大取文范围，必须同时改
# `source_evidence_reader` 的加载白名单（该文件不在任务 S 的白名单内）。
_DISCHARGE_LOADED_COLUMNS = (
    "document_title",
    "discharge_order",
    "discharge_medications",
    "treatment_course",
    "record_content",
)
# 口径来源：`docs/plans/2026-09-12-0910-qc-closure-prioritization.md` §八 D3 与
# `docs/plans/2026-09-12-0910-issue-backlog.md` §15.3 主协调裁定 A 案。
# 「考虑:Ca 伴瘤周转移可能」「考虑:转移可能」属**明示未决可疑**，不等于「确无恶性证据」，
# 故不得据此判 `not_applicable`（D3「确无 ≠ 未找到」，M1 报告 §4.3/5.2）。
_EXPLICIT_MALIGNANCY_SUSPICION_PATTERNS = (
    re.compile(r"考虑.{0,6}(?:Ca|癌|恶性|转移)"),
    re.compile(r"转移可能"),
    re.compile(r"恶性可能"),
    re.compile(r"Ca[?？]"),
)
_MAPPING_LINE_PATTERN = re.compile(r"^.*(?:主执行规则|映射执行规则).*$", re.MULTILINE)
_MALIGNANT_CODE_PATTERN = re.compile(r"^C[0-9]{2}(?:[.A-Z0-9-]*)$")
_PRESENT_FACT_STATES = frozenset({"present", "performed", "available", "positive"})
_PATHOLOGY_SAMPLING_ACTION_PATTERNS = (
    re.compile(
        r"(?:切除|取出|切取|留取|获取|取材).{0,48}"
        r"(?:标本|组织|病灶|肿物|阑尾|胆囊)?.{0,24}"
        r"(?:送病理(?:检查)?|送病检|送检)"
    ),
    re.compile(
        r"(?:标本|组织|病灶|肿物|阑尾|胆囊).{0,48}"
        r"(?:已送|送病理(?:检查)?|送病检|送检)"
    ),
    re.compile(
        r"(?:术中|手术中).{0,24}(?:取材|切取|留取)"
        r"(?:了|完成|并|后|，|,|送病理|送病检|送检|$)"
    ),
    re.compile(r"(?:已|已经)(?:送病理(?:检查)?|送病检|送检)"),
)
_PATHOLOGY_SAMPLING_NEGATIVE_PATTERN = re.compile(
    r"(?:"
    r"(?:不|未|无|未见|尚未|未予|未行|未记录|缺少|遗漏|拒绝|取消|放弃|暂缓).{0,18}"
    r"(?:取材|标本|送病理|送病检|送检)"
    r"|(?:拟|计划|建议|待|考虑|准备|预计|应|需|请|嘱).{0,18}"
    r"(?:取材|标本|送病理|送病检|送检)"
    r"|(?:取材|标本|送病理|送病检|送检).{0,18}"
    r"(?:不|未|无|未见|尚未|缺失|未记录|不详|拒绝|取消|放弃|暂缓|单|申请|医嘱|登记|流程|手续|计划)"
    r")"
)
_PATHOLOGY_SAMPLING_EMPTY_TEMPLATE_PATTERN = re.compile(
    r"(?:术中取材|标本送检情况|送检情况)\s*[:：]\s*$"
)
_PATHOLOGY_DIRECT_SEND_PATTERN = re.compile(r"(?:送病理(?:检查)?|送病检|送检)")
_PATHOLOGY_SAMPLING_SUBJECT_PATTERN = re.compile(
    r"(?:标本|组织|病灶|肿物|阑尾|胆囊|取材|切除|取出)"
)
_PATHOLOGY_SAMPLING_ADMIN_PATTERN = re.compile(
    r"(?:送检单|申请|医嘱|登记|流程|手续|计划|打印)"
)
_PATHOLOGY_FINAL_RESULT_PATTERN = re.compile(r"病理(?:诊断|结果)")
_PATHOLOGY_PENDING_RESULT_PATTERN = re.compile(
    r"(?:待补|待出|待定|待完善|待诊断|待报告|待回报|待复核|未出|审核中|尚未|另报|后续正式报告|暂缺|未完成|初步)"
)
_PATHOLOGY_REPORT_DATETIME_PATTERN = re.compile(
    r"^\d{4}-\d{1,2}-\d{1,2}[T ]\d{1,2}:\d{2}(?::\d{2}(?:\.\d{1,6})?)?(?:Z|[+-]\d{2}:?\d{2})?$"
)
_PATHOLOGY_RESULT_REFERENCE_PATTERN = re.compile(r"病理(?:报告|结果|诊断)")
_PATHOLOGY_RESULT_MISSING_PATTERN = re.compile(
    r"(?:未记录.{0,12}病理(?:报告|结果|诊断)|病理(?:报告|结果|诊断).{0,12}未记录)"
)
_PATHOLOGY_SAMPLING_MISSING_PATTERN = re.compile(
    r"(?:未记录.{0,12}(?:病理)?(?:取材|送检)|(?:病理)?(?:取材|送检).{0,12}未记录)"
)
# ATC 皮肤抗感染分类中的“化疗药物”不表示肿瘤化疗；非肿瘤类别
# 不能仅凭包含该词触发。独立化疗分类及明确抗肿瘤分类仍保留。
_CHEMOTHERAPY_CLASS_PATTERN = re.compile(r"抗肿瘤|(?:^|[\s/、,，;；>])化疗(?:药物|药)?(?:$|[\s/、,，;；>])")
_CHEMO_ORDER_VOID_STATUSES = frozenset({"取消", "撤销", "作废"})
_CHEMO_ORDER_PENDING_STATUSES = frozenset({"拟执行"})
_CHEMOTHERAPY_RELATIVE_DATE_PATTERN = re.compile(r"(?:今日|当日)")
_CHEMOTHERAPY_EXPLICIT_DATE_PATTERN = re.compile(
    r"(?P<year>\d{4})[-年/](?P<month>\d{1,2})[-月/](?P<day>\d{1,2})日?"
)
_CLINICAL_CLAUSE_SEPARATOR = re.compile(r"[\r\n。；;！？!?]+")
_DISCHARGE_PLAN_FUTURE_PATTERN = re.compile(r"(?:后续|出院后|继续|定期|计划|建议|门诊)")
_DISCHARGE_PLAN_TREATMENT_PATTERN = re.compile(
    r"(?:肿瘤治疗|化疗|放疗|靶向|免疫治疗|内分泌治疗|抗肿瘤|治疗计划)"
)
# 业务基线 027：后续肿瘤治疗或随访计划任一项即可。随访只认明确的随访/定期复查安排；
# 单项化验复查（如“门诊复查血常规”）和“如有不适随诊”类附条件叮嘱不算随访计划。
_DISCHARGE_PLAN_FOLLOW_UP_PATTERN = re.compile(r"(?:随访|定期复查|定期复诊)")
_DISCHARGE_PLAN_CONDITIONAL_PATTERN = re.compile(r"(?:不适|如有|若有|如出现|若出现|必要时)")
_DISCHARGE_PLAN_NEGATIVE_TREATMENT_PATTERN = re.compile(
    r"(?:暂不|不予|无需|未予|取消|停止|拒绝|不建议|不考虑|不行|不实施).{0,8}"
    r"(?:肿瘤治疗|化疗|放疗|靶向|免疫治疗|内分泌治疗|抗肿瘤)"
)
_DISCHARGE_PLAN_PENDING_TREATMENT_PATTERN = re.compile(
    r"(?:待病理|待病检|待结果|待明确)"
    r"|(?:必要时|酌情|视情况|视病情).{0,8}"
    r"(?:肿瘤治疗|化疗|放疗|靶向|免疫治疗|内分泌治疗|抗肿瘤)"
)

_MALIGNANT_FACT_TYPES = frozenset(
    {
        "current_visit_malignant_neoplasm_diagnosis",
        "current_visit_malignant_tumor",
    }
)
_CHEMO_FACT_TYPES = frozenset(
    {
        "current_visit_chemotherapy_order",
        "current_visit_chemotherapy_treatment",
    }
)

_CONTROLLED_MESSAGES = {
    "compliant": ("肿瘤病理相关记录满足该项要求。", ""),
    "non_compliant": (
        "肿瘤病理相关记录未满足该项要求。",
        "请按该质控点补充或修正相关记录。",
    ),
    "not_applicable": ("当前就诊未发现该项适用的肿瘤病理事实。", ""),
    "data_gap": (
        "当前肿瘤病理资料不足，暂不能形成可靠结论。",
        "请补齐相关资料后重新质控。",
    ),
    "technical_error": (
        "本项自动质控执行异常，未形成临床结论。",
        "请联系系统管理员核查模型执行能力后重新质控。",
    ),
}


class TumorPathologyLLMClient(Protocol):
    async def generate(
        self,
        prompt: str,
        *,
        max_completion_tokens: int | None = None,
        allow_length_retry: bool = True,
    ) -> dict[str, Any]: ...


@dataclass(frozen=True)
class SourceMaterial:
    state: str
    rows: tuple[Mapping[str, Any], ...] = ()


@dataclass(frozen=True)
class NativeTumorPathologyExecutionResult:
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
class _TumorRuleOutcome:
    rule_id: str
    status: str
    reason_code: str
    executor_type: str
    fact_refs: tuple[str, ...] = ()


def _typed_decision_from_outcome(
    *,
    outcome: _TumorRuleOutcome,
    snapshot: Luxian0609EvidenceSnapshot,
) -> RuleDecision:
    # 文书选择是执行器的职责。禁止以规则允许的所有来源 Observation 代替
    # 实际参与判定的文书，否则 Binding 会把适用性内部资料误投影给客户。
    refs = tuple(dict.fromkeys(outcome.fact_refs))
    if not refs and outcome.status == "not_applicable":
        # 完整空来源没有可投影文书；保留来源级审计事实以证明“无触发”不是
        # 执行器遗漏，同时公共投影不会把它伪造为客户文书证据。
        refs = tuple(
            observation.snapshot_ref.removeprefix("sha256:")
            for observation in snapshot.observations
            if observation.source_key in _TYPED_RULE_SOURCE_KEYS[outcome.rule_id]
        )

    if outcome.status == "compliant":
        dimensions = (
            ApplicabilityState.APPLICABLE,
            EvidenceState.SUFFICIENT,
            QcDirection.SATISFIED,
            "requirement_satisfied",
        )
    elif outcome.status == "non_compliant":
        dimensions = (
            ApplicabilityState.APPLICABLE,
            EvidenceState.SUFFICIENT,
            QcDirection.DEFECT,
            "requirement_violated",
        )
    elif outcome.status == "not_applicable":
        dimensions = (
            ApplicabilityState.NOT_APPLICABLE,
            EvidenceState.SUFFICIENT,
            QcDirection.UNKNOWN,
            "trigger_absent_complete",
        )
    elif outcome.status == "data_gap":
        # 字段名中带 unavailable 不等于来源未接入。013 已读取到具体病理报告，
        # 只是同一报告缺最终诊断或有效报告时间，必须保留为字段缺口。
        source_gap = (
            outcome.reason_code
            != "pathology_final_result_or_report_time_unavailable"
            and "unavailable" in outcome.reason_code
        )
        dimensions = (
            ApplicabilityState.UNKNOWN if source_gap else ApplicabilityState.APPLICABLE,
            EvidenceState.DATA_GAP,
            QcDirection.UNKNOWN,
            "target_report_missing"
            if outcome.rule_id == PATHOLOGY_REPORT_COMPLETENESS_RULE_ID
            and outcome.reason_code == "target_report_missing"
            else "association_failed"
            if outcome.rule_id in {"LX0609-06-02-02", "LX0609-06-02-03"}
            and outcome.reason_code == "pathology_event_association_unresolved"
            else "source_unavailable" if source_gap else "required_field_missing",
        )
    elif outcome.status == "technical_error":
        technical_reason = (
            "source_query_error"
            if outcome.reason_code
            in {"source_query_error", "malignancy_source_query_error"}
            else "model_invalid_output"
            if outcome.reason_code in {"tumor_llm_invalid_output", "malignancy_llm_invalid"}
            else "model_transport_error"
            if outcome.reason_code in {"tumor_llm_failure", "malignancy_llm_transport_error"}
            else "executor_exception"
        )
        dimensions = (
            ApplicabilityState.ERROR,
            EvidenceState.TECHNICAL_ERROR,
            QcDirection.UNKNOWN,
            technical_reason,
        )
    else:
        raise ValueError("unsupported typed tumor final state")

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


def _clean(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def _discharge_narrative_text(material: SourceMaterial) -> str:
    """拼接已加载的 discharge_record 叙事列文本（不含坐标与患者身份列）。"""

    parts: list[str] = []
    for row in material.rows:
        if not isinstance(row, Mapping):
            continue
        for key in _DISCHARGE_LOADED_COLUMNS:
            if key in row:
                value = row.get(key)
                if value:
                    parts.append(str(value))
    return "\n".join(parts)


def _has_explicit_malignancy_suspicion(
    *,
    discharge_material: SourceMaterial,
    uncertain_rows: Sequence[tuple[str, Mapping[str, Any]]],
) -> bool:
    """判定输入是否**明示未决恶性可疑**（A 案判别器，纯确定性正则，不调用模型）。

    口径来源：`docs/plans/2026-09-12-0910-qc-closure-prioritization.md` §八 D3「不触发，
    判 not_applicable + trigger_absent_complete」只适用于「**确无**明确恶性证据」；
    `docs/plans/2026-09-12-0910-issue-backlog.md` §15.3 主协调裁定取 A 案：出院记录
    叙事列或不确定诊断名出现「考虑…Ca/癌/恶性/转移」「转移可能」「恶性可能」「Ca?」
    即属**明示未决可疑**（≠ 确无），维持 `data_gap`，不得对客户宣告「本项不适用」。

    输入只取执行器**已加载**的材料：同一 Evidence Session 的 `discharge_record` 行
    （不新增查询、不调用模型）与恶性分类回执中的不确定诊断行。
    """

    texts = [_discharge_narrative_text(discharge_material)]
    texts.extend(
        str(row.get("diagnosis_name") or row.get("diagnosis") or "")
        for _source_key, row in uncertain_rows
        if isinstance(row, Mapping)
    )
    haystack = "\n".join(text for text in texts if text)
    if not haystack:
        return False
    return any(
        pattern.search(haystack)
        for pattern in _EXPLICIT_MALIGNANCY_SUSPICION_PATTERNS
    )


def _documents(evidence_payload: Mapping[str, Any] | None) -> Mapping[str, Any] | None:
    if not isinstance(evidence_payload, Mapping):
        return None
    timeline = evidence_payload.get("programmatic_timeline")
    if not isinstance(timeline, Mapping):
        return None
    documents = timeline.get("documents")
    return documents if isinstance(documents, Mapping) else None


def _timeline_facts(evidence_payload: Mapping[str, Any] | None) -> Sequence[Any]:
    if not isinstance(evidence_payload, Mapping):
        return ()
    facts = evidence_payload.get("timeline_facts")
    return tuple(facts) if isinstance(facts, list) else ()


def _bundle_rows(
    documents: Mapping[str, Any] | None, source_key: str
) -> tuple[Mapping[str, Any], ...]:
    if not isinstance(documents, Mapping):
        return ()
    raw_rows = documents.get(source_key)
    if not isinstance(raw_rows, list):
        return ()
    return tuple(
        row for row in raw_rows[:_MAX_ROWS_PER_SOURCE] if isinstance(row, Mapping)
    )


def _load_source(
    *,
    documents: Mapping[str, Any] | None,
    source_key: str,
    institute_id: str,
    patient_id: str,
    visit_id: str,
    source_schema: str | None,
    evidence_snapshot: Luxian0609EvidenceSnapshot | None = None,
    evidence_materials: Luxian0609EvidenceMaterialStore | None = None,
) -> SourceMaterial:
    bundle_rows = _bundle_rows(documents, source_key)
    if bundle_rows:
        return SourceMaterial("present", bundle_rows)
    if evidence_snapshot is not None:
        observation = next(
            (
                item
                for item in evidence_snapshot.observations
                if item.source_key == source_key
            ),
            None,
        )
        if observation is not None:
            if (
                evidence_materials is None
                or evidence_materials.snapshot_hash != evidence_snapshot.snapshot_hash
            ):
                return SourceMaterial("error")
            if observation.query_state.value in {"unavailable", "error"}:
                return SourceMaterial(observation.query_state.value)
            try:
                rows = evidence_materials.rows(source_key)
            except EvidenceMaterialTruncated:
                return SourceMaterial("truncated")
            except EvidenceMaterialUnavailable:
                return SourceMaterial("error")
            material = tuple(
                row
                for row in rows[:_MAX_ROWS_PER_SOURCE]
                if isinstance(row, Mapping)
            )
            return SourceMaterial("present" if material else "empty", material)
    if not all((institute_id, patient_id, visit_id)):
        return SourceMaterial("unavailable")
    try:
        rows = read_luxian_0609_native_source_rows(
            source_key=source_key,
            institute_id=institute_id,
            patient_id=patient_id,
            visit_id=visit_id,
            source_schema=source_schema,
        )
    except SourceEvidenceUnavailable:
        return SourceMaterial("unavailable")
    except Exception:
        return SourceMaterial("error")
    material = tuple(
        row for row in rows[:_MAX_ROWS_PER_SOURCE] if isinstance(row, Mapping)
    )
    return SourceMaterial("present" if material else "empty", material)


def _load_typed_source(
    *,
    source_key: str,
    evidence_snapshot: Luxian0609EvidenceSnapshot,
    evidence_materials: Luxian0609EvidenceMaterialStore,
) -> SourceMaterial:
    """typed 019 只读同一快照材料，不允许 payload 或族内查询回退。"""

    if evidence_materials.snapshot_hash != evidence_snapshot.snapshot_hash:
        return SourceMaterial("error")
    observation = next(
        (
            item
            for item in evidence_snapshot.observations
            if item.source_key == source_key
        ),
        None,
    )
    if observation is None:
        return SourceMaterial("error")
    if observation.query_state.value in {"unavailable", "error"}:
        return SourceMaterial(observation.query_state.value)
    try:
        rows = evidence_materials.rows(source_key)
    except EvidenceMaterialTruncated:
        return SourceMaterial("truncated")
    except EvidenceMaterialUnavailable:
        return SourceMaterial("error")
    # typed 判定必须消费本次 Evidence Session 的完整 bounded 材料；只在构造
    # 模型上下文时限行，不能让第9行以后的强触发事实被静默丢弃。
    material = tuple(row for row in rows if isinstance(row, Mapping))
    return SourceMaterial("present" if material else "empty", material)


def _row_text(row: Mapping[str, Any]) -> str:
    approved_keys = (
        "content",
        "record_content",
        "assembled_text",
        "diagnosis",
        "eye_findings",
        "microscope_findings",
        "specimen_name",
        "surgery_name",
        "diagnosis_code",
        "drug_code",
        "generic_name",
        "brand_name",
        "drug_type",
        "single_dose",
        "single_dose_unit",
        "drug_apply_method",
        "drug_frequency",
        "prescribed_datetime",
        "order_status",
        "discharge_order",
        "treatment_course",
    )
    return _clean(
        " ".join(_clean(row.get(key)) for key in approved_keys if _clean(row.get(key)))
    )


def _source_text(source_key: str, material: SourceMaterial) -> list[str]:
    return [
        f"[{source_key}-{index}] {text[:_MAX_ROW_CHARS]}"
        for index, row in enumerate(
            material.rows[:_MAX_ROWS_PER_SOURCE], start=1
        )
        if (text := _row_text(row))
    ]


def _has_fact(
    facts: Sequence[Any], fact_types: frozenset[str], source_keys: frozenset[str]
) -> bool:
    for raw_fact in facts:
        if not isinstance(raw_fact, Mapping):
            continue
        if raw_fact.get("current_visit_bound") is not True:
            continue
        fact_type = _clean(raw_fact.get("fact_type")).lower()
        state = _clean(raw_fact.get("state")).lower()
        source_key = _clean(raw_fact.get("source_key")).lower()
        if (
            fact_type in fact_types
            and state in _PRESENT_FACT_STATES
            and source_key in source_keys
        ):
            return True
    return False


def _has_malignant_code(material: SourceMaterial) -> bool:
    return any(
        _MALIGNANT_CODE_PATTERN.fullmatch(
            _clean(row.get("diagnosis_code") or row.get("content")).upper()
        )
        for row in material.rows
    )


def _has_any_diagnosis_code(material: SourceMaterial) -> bool:
    return any(_clean(row.get("diagnosis_code")) for row in material.rows)


def _malignancy_sources(
    source_for_rule: Any, *, visit_stage: str
) -> tuple[MalignancySource, ...]:
    admission = source_for_rule("admission_record_diagnosis")
    diagnosis = source_for_rule("diagnosis")
    discharge_diagnosis = source_for_rule("discharge_record_diagnosis")
    pathology = source_for_rule("pathology_exam_report")
    return build_stage_malignancy_sources(
        visit_stage=visit_stage,
        admission_state=admission.state,
        admission_rows=admission.rows,
        diagnosis_state=diagnosis.state,
        diagnosis_rows=diagnosis.rows,
        discharge_diagnosis_state=discharge_diagnosis.state,
        discharge_diagnosis_rows=discharge_diagnosis.rows,
        pathology_state=pathology.state,
        pathology_rows=pathology.rows,
    )


def _typed_chemotherapy_orders(material: SourceMaterial) -> tuple[Mapping[str, Any], ...]:
    return tuple(
        row
        for row in material.rows
        if _CHEMOTHERAPY_CLASS_PATTERN.search(
            _clean(
                row.get("drug_type")
                or row.get("order_class")
                or row.get("order_category")
            )
        )
    )


def _discharge_stage(
    horizon: SourceMaterial, discharge_record: SourceMaterial
) -> str:
    return resolve_malignancy_visit_stage(
        horizon_state=horizon.state,
        horizon_rows=horizon.rows,
        discharge_record_state=discharge_record.state,
    )


def _has_complete_pathology_result(material: SourceMaterial) -> bool:
    """最终结果和报告时间必须来自同一份报告，肉眼/镜下材料不能代替最终诊断。"""

    return _complete_pathology_result_row(material) is not None


def _complete_pathology_result_row(
    material: SourceMaterial,
) -> Mapping[str, Any] | None:
    """返回实际构成病理最终结果触发的报告行。"""

    for row in material.rows:
        if (
            _pathology_report_time_state(row) == "valid"
            and _pathology_final_diagnosis_state(row) == "confirmed"
        ):
            return row
    return None


def _pathology_report_time_state(row: Mapping[str, Any]) -> str:
    report_time = _clean(
        row.get("report_datetime")
        or row.get("report_time")
        or row.get("record_time")
        or row.get("display_time")
        or row.get("authored_at")
    )
    if not report_time or not _PATHOLOGY_REPORT_DATETIME_PATTERN.fullmatch(report_time):
        return "missing"
    try:
        datetime.fromisoformat(report_time.replace("Z", "+00:00"))
    except ValueError:
        return "missing"
    return "valid"


def _pathology_final_diagnosis_state(row: Mapping[str, Any]) -> str:
    diagnosis = _clean(row.get("diagnosis"))
    body = _clean(row.get("record_content") or row.get("content"))
    result_text = diagnosis or body
    if result_text and _PATHOLOGY_PENDING_RESULT_PATTERN.search(result_text):
        return "pending"
    if diagnosis or (body and _PATHOLOGY_FINAL_RESULT_PATTERN.search(body)):
        return "confirmed"
    return "missing"


def _has_documented_pathology_sampling(*materials: SourceMaterial) -> bool:
    """仅接受已实施的取材/送检事实；计划、否定和空模板继续交由模型判断。"""

    return _documented_pathology_sampling_row(*materials) is not None


def _documented_pathology_sampling_row(
    *materials: SourceMaterial,
) -> Mapping[str, Any] | None:
    """返回实际证明已取材/送检的第一份文书行，判定口径与布尔检查一致。"""

    for material in materials:
        for row in material.rows:
            text = _clean(
                " ".join(
                    part
                    for part in (_row_text(row), _clean(row.get("surgery_process")))
                    if part
                )
            )
            segments = [
                _clean(segment)
                for segment in re.split(r"[。！？；;，,\r\n]+", text)
                if _clean(segment)
            ]
            for index, normalized in enumerate(segments):
                if not normalized:
                    continue
                if _PATHOLOGY_SAMPLING_EMPTY_TEMPLATE_PATTERN.search(normalized):
                    continue
                for pattern in _PATHOLOGY_SAMPLING_ACTION_PATTERNS:
                    for match in pattern.finditer(normalized):
                        local_window = normalized[
                            max(0, match.start() - 20) : min(
                                len(normalized), match.end() + 20
                            )
                        ]
                        if not _PATHOLOGY_SAMPLING_NEGATIVE_PATTERN.search(
                            local_window
                        ):
                            return row
                if not _PATHOLOGY_DIRECT_SEND_PATTERN.search(normalized):
                    continue
                recent_context = " ".join(segments[max(0, index - 2) : index])
                combined_context = f"{recent_context} {normalized}".strip()
                if (
                    _PATHOLOGY_SAMPLING_SUBJECT_PATTERN.search(recent_context)
                    and not _PATHOLOGY_SAMPLING_NEGATIVE_PATTERN.search(
                        combined_context
                    )
                    and not _PATHOLOGY_SAMPLING_ADMIN_PATTERN.search(
                        combined_context
                    )
                ):
                    return row
    return None


def _has_documented_pathology_result(
    pathology_report: SourceMaterial,
    *target_materials: SourceMaterial,
) -> bool:
    """只接受目标文书中明确的病理结果引用，并用最终诊断关键词交叉核对。"""

    return _documented_pathology_result_row(
        pathology_report, *target_materials
    ) is not None


def _pathology_link_time(value: Any) -> datetime | None:
    """仅解析事件/记录时间；提交时间不能补出临床记录的发生时间。"""
    try:
        parsed = datetime.fromisoformat(_clean(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    # CDM 同时存在无时区院内时间与带时区时间，统一为院内东八区时间。
    if parsed.tzinfo is not None:
        from datetime import timedelta, timezone

        parsed = parsed.astimezone(timezone(timedelta(hours=8))).replace(tzinfo=None)
    return parsed


def _documented_pathology_result_row(
    pathology_report: SourceMaterial,
    *target_materials: SourceMaterial,
) -> Mapping[str, Any] | None:
    """返回实际引用最终病理结果的目标文书行，判定口径与布尔检查一致。"""

    diagnosis_terms: list[str] = []
    for row in pathology_report.rows:
        diagnosis = _clean(row.get("diagnosis"))
        diagnosis_terms.extend(
            term
            for term in (
                _clean(item)
                for item in re.split(r"[，,；;。\r\n]+", diagnosis)
            )
            if len(term) >= 2
        )
    for material in target_materials:
        for row in material.rows:
            text = _clean(_row_text(row))
            if not _PATHOLOGY_RESULT_REFERENCE_PATTERN.search(text):
                continue
            if _PATHOLOGY_PENDING_RESULT_PATTERN.search(text):
                continue
            if any(term in text for term in diagnosis_terms):
                return row
            if not diagnosis_terms and _PATHOLOGY_FINAL_RESULT_PATTERN.search(text):
                return row
    return None


def _all_targets_explicitly_missing(
    pattern: re.Pattern[str], *target_materials: SourceMaterial
) -> bool:
    """只有每类现有目标文书都明确声明该事实未记录时才短路为缺陷。"""

    return bool(_explicitly_missing_target_rows(pattern, *target_materials))


def _explicitly_missing_target_rows(
    pattern: re.Pattern[str], *target_materials: SourceMaterial
) -> tuple[Mapping[str, Any], ...]:
    """仅在所有目标文书均明确缺失时，返回各自实际作出该结论的行。"""

    selected: list[Mapping[str, Any]] = []
    for material in target_materials:
        if material.state != "present":
            return ()
        row = next(
            (
                candidate
                for candidate in material.rows
                if pattern.search(_clean(_row_text(candidate)))
            ),
            None,
        )
        if row is None:
            return ()
        selected.append(row)
    return tuple(selected)


def _prompt(wrapper: Mapping[str, Any], *, context: str) -> str:
    custom_prompt = _MAPPING_LINE_PATTERN.sub(
        "", str(wrapper.get("custom_prompt") or "")
    )
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


def _result(
    rule_id: str, status: str, reason_code: str, *, executor_type: str
) -> dict[str, Any]:
    item = build_luxian_0609_native_result(
        rule_id=rule_id,
        final_state=status,
        finding_kind="requirement_satisfied" if status == "compliant" else status,
        reason_code=reason_code,
    )
    findings, suggestion = _CONTROLLED_MESSAGES[status]
    item["findings"] = findings
    item["suggestion"] = suggestion
    metadata = dict(item.get("metadata") or {})
    metadata["executor_type"] = executor_type
    item["metadata"] = metadata
    return item


def _lx019_missing_sampling_display_facts(
    *,
    pathology_master: SourceMaterial,
    pathology_report: SourceMaterial,
    surgery_record: SourceMaterial,
    daily_course_record: SourceMaterial,
) -> Mapping[str, Any] | None:
    """019 只投影已核对的来源状态，不携带病理或病程原文。"""

    pathology_sources = [
        source_key
        for source_key, material in (
            ("pathology_exam_master", pathology_master),
            ("pathology_exam_report", pathology_report),
        )
        if material.state == "present"
    ]
    target_sources = [
        {"source": source_key, "state": material.state}
        for source_key, material in (
            ("surgery_record", surgery_record),
            ("daily_course_record", daily_course_record),
        )
        if material.state in {"present", "empty"}
    ]
    if not pathology_sources or len(target_sources) != 2:
        return None
    return {
        "failure_kind": "pathology_sampling_not_documented",
        "pathology_trigger_sources": pathology_sources,
        "checked_target_sources": target_sources,
    }


def _pathology_checked_sources(
    *,
    pathology_master: SourceMaterial,
    pathology_report: SourceMaterial,
    surgery_record: SourceMaterial,
    daily_course_record: SourceMaterial,
) -> tuple[list[str], list[dict[str, str]]]:
    trigger_sources = [
        source_key
        for source_key, material in (
            ("pathology_exam_master", pathology_master),
            ("pathology_exam_report", pathology_report),
        )
        if material.state == "present"
    ]
    target_materials = [
        ("surgery_record", surgery_record),
        ("daily_course_record", daily_course_record),
    ]
    target_sources = [
        {"source": source_key, "state": material.state}
        for source_key, material in target_materials
        if material.state in {"present", "empty"}
    ]
    return trigger_sources, target_sources


def _pathology_result_display_facts(
    *,
    status: str,
    pathology_master: SourceMaterial,
    pathology_report: SourceMaterial,
    surgery_record: SourceMaterial,
    daily_course_record: SourceMaterial,
    senior_course_record: SourceMaterial | None = None,
) -> Mapping[str, Any] | None:
    trigger_sources, target_sources = _pathology_checked_sources(
        pathology_master=pathology_master,
        pathology_report=pathology_report,
        surgery_record=surgery_record,
        daily_course_record=daily_course_record,
    )
    if not trigger_sources or len(target_sources) != 2:
        return None
    if senior_course_record is not None:
        if senior_course_record.state not in {"present", "empty"}:
            return None
        target_sources.append({"source": "senior_course_record", "state": senior_course_record.state})
    report_times = {
        value
        for row in pathology_report.rows
        if (
            value := _clean(
                row.get("report_datetime")
                or row.get("report_time")
                or row.get("record_time")
            )
        )
        and _PATHOLOGY_REPORT_DATETIME_PATTERN.fullmatch(value)
    }
    facts: dict[str, Any] = {
        "verification_kind": "pathology_result_documentation_check",
        "pathology_trigger_sources": trigger_sources,
        "checked_target_sources": target_sources,
        "requirement_met": status == "compliant",
    }
    if len(report_times) == 1:
        facts["report_time"] = next(iter(report_times))
    return facts


def _pathology_report_gap_display_facts(
    pathology_report: SourceMaterial,
) -> Mapping[str, Any] | None:
    """投影逐报告字段完整性；不携带报告正文，也不跨报告合并字段。"""

    report_gaps = [
        {
            "final_diagnosis_state": _pathology_final_diagnosis_state(row),
            "report_time_state": _pathology_report_time_state(row),
        }
        for row in pathology_report.rows
        if not (
            _pathology_final_diagnosis_state(row) == "confirmed"
            and _pathology_report_time_state(row) == "valid"
        )
    ]
    if not report_gaps:
        return None
    return {
        "verification_kind": "pathology_report_field_gap",
        "report_gaps": report_gaps,
    }


def _pathology_sampling_display_facts(
    *,
    pathology_master: SourceMaterial,
    pathology_report: SourceMaterial,
    surgery_record: SourceMaterial,
    daily_course_record: SourceMaterial,
) -> Mapping[str, Any] | None:
    trigger_sources, target_sources = _pathology_checked_sources(
        pathology_master=pathology_master,
        pathology_report=pathology_report,
        surgery_record=surgery_record,
        daily_course_record=daily_course_record,
    )
    if not trigger_sources or len(target_sources) != 2:
        return None
    documented_sources = [
        source
        for source, material in (
            ("surgery_record", surgery_record),
            ("daily_course_record", daily_course_record),
        )
        if _has_documented_pathology_sampling(material)
    ]
    return {
        "verification_kind": "pathology_sampling_documentation_check",
        "pathology_trigger_sources": trigger_sources,
        "checked_target_sources": target_sources,
        "documented_sources": documented_sources,
        "requirement_met": bool(documented_sources),
    }


def _lx019_typed_display_facts(
    *,
    pathology_master: SourceMaterial,
    pathology_report: SourceMaterial,
    checked: Sequence[tuple[str, SourceMaterial]],
    documented_sources: Sequence[str] | None,
) -> Mapping[str, Any] | None:
    """019 投影实际核对的来源；documented_sources 为 None 表示未记录。"""

    triggers = [
        source for source, material in (
            ("pathology_exam_master", pathology_master),
            ("pathology_exam_report", pathology_report),
        )
        if material.state == "present"
    ]
    targets = [{"source": source, "state": material.state} for source, material in checked]
    if not triggers or any(item["state"] not in {"present", "empty"} for item in targets):
        return None
    if documented_sources is None:
        return {
            "failure_kind": "pathology_sampling_not_documented",
            "pathology_trigger_sources": triggers,
            "checked_target_sources": targets,
        }
    return {
        "verification_kind": "pathology_sampling_documentation_check",
        "pathology_trigger_sources": triggers,
        "checked_target_sources": targets,
        "documented_sources": list(documented_sources),
        "requirement_met": True,
    }


_TARGET_SOURCE_LABELS = {
    "surgery_record": "手术记录",
    "daily_course_record": "日常病程记录",
    "senior_course_record": "上级医师查房记录",
}


@dataclass(frozen=True)
class _PathologyDocumentationOutcome:
    status: str
    reason_code: str
    cited: tuple[tuple[str, Mapping[str, Any]], ...] = ()
    checked: tuple[tuple[str, Mapping[str, Any]], ...] = ()
    llm_call_count: int = 0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    api_time: float = 0.0


def _pathology_events(
    *, sampling: bool, master: SourceMaterial, report: SourceMaterial,
) -> tuple[tuple[PathologyEvent, datetime | None], ...] | None:
    """逐份病理报告构成一次检查；业务键冲突时不能确定事件，返回 None。"""

    key_fields = ("pathology_exam_id", "pathology_id")
    rows = report.rows if sampling else tuple(
        row for row in report.rows
        if _pathology_report_time_state(row) == "valid"
        and _pathology_final_diagnosis_state(row) == "confirmed"
    )
    events: list[tuple[PathologyEvent, datetime | None]] = []
    used_masters: set[int] = set()
    for index, row in enumerate(rows, 1):
        linked = [
            candidate for candidate in master.rows
            if any(_clean(row.get(key)) and _clean(row.get(key)) == _clean(candidate.get(key)) for key in key_fields)
        ]
        if len(linked) > 1:
            return None
        if not linked and len(master.rows) == len(report.rows) == 1 and not any(
            _clean(row.get(key)) and _clean(master.rows[0].get(key)) for key in key_fields
        ):
            linked = [master.rows[0]]
        used_masters.update(id(candidate) for candidate in linked)
        specimens = {_clean(item.get("specimen_name")) for item in (row, *linked) if _clean(item.get("specimen_name"))}
        report_time = _pathology_link_time(row.get("report_datetime") or row.get("report_time"))
        events.append((
            PathologyEvent(
                event_id=f"P{index}", specimen="、".join(sorted(specimens)),
                diagnosis=_clean(row.get("diagnosis") or row.get("record_content") or row.get("content")),
                report_time=report_time.isoformat(sep=" ") if report_time else "",
            ),
            report_time,
        ))
    # 019：未关联到任何报告的病理申请也是一次取材，不能被其他事件的记录覆盖。
    if sampling and any(id(row) not in used_masters for row in master.rows):
        return None
    return tuple(events)


async def _typed_pathology_documentation(
    *, rule_id: str, master: SourceMaterial, report: SourceMaterial,
    targets: Mapping[str, SourceMaterial], llm_client: Any,
) -> _PathologyDocumentationOutcome:
    """模型逐次检查抽取取材/结果记录及原文引用，程序核验时间并判定。"""

    sampling = rule_id == "LX0609-06-02-02"
    events = _pathology_events(sampling=sampling, master=master, report=report)
    if not events:
        return _PathologyDocumentationOutcome("data_gap", "pathology_event_association_unresolved")
    earliest_report = min((moment for _, moment in events if moment is not None), default=None)
    documents: list[PathologyDocument] = []
    checked: list[tuple[str, Mapping[str, Any]]] = []
    times: dict[int, datetime | None] = {}
    untimed = False
    for source, material in targets.items():
        for row in material.rows:
            body = _clean(" ".join(dict.fromkeys(
                part for part in (_row_text(row), _clean(row.get("surgery_process"))) if part
            )))
            if not body:
                continue
            document_time = row.get("record_time") or row.get("record_datetime")
            if not sampling:
                document_time = authoritative_document_time_value(row)
            moment = _pathology_link_time((row.get("surgery_begin_time") if sampling else None) or document_time)
            if not sampling:
                # 013 核对结果是否写入文书；记录时间优先，缺失时正式提交时间可证明文书存在。
                # 不使用修改时间，不借提交时间改写检查或手术事件的发生时间。
                if moment is None:
                    untimed = True
                    continue
                if earliest_report is None or moment < earliest_report:
                    continue
            times[id(row)] = moment
            checked.append((source, row))
            documents.append(PathologyDocument(
                (source, row), _TARGET_SOURCE_LABELS.get(source, source),
                moment.isoformat(sep=" ") if moment else "", body,
            ))
    extraction = await extract_pathology_documentation_facts(
        sampling=sampling, events=[event for event, _ in events], documents=documents, llm_client=llm_client,
    )
    usage = dict(
        llm_call_count=extraction.llm_call_count, prompt_tokens=extraction.prompt_tokens,
        completion_tokens=extraction.completion_tokens, total_tokens=extraction.total_tokens,
        api_time=extraction.api_time,
    )
    if extraction.state != "ready":
        status = "technical_error" if extraction.state == "technical_error" else "data_gap"
        reason = extraction.reason_code if status == "technical_error" else "tumor_target_projection_unavailable"
        return _PathologyDocumentationOutcome(status, reason, checked=tuple(checked), **usage)
    states: list[str] = []
    cited: list[tuple[str, Mapping[str, Any]]] = []
    for event, report_time in events:
        fact = extraction.events[event.event_id]
        state = fact.state
        if state == "documented":
            source, row = fact.document_key
            moment = times.get(id(row))
            if not sampling and (report_time is None or moment is None or moment < report_time):
                # 引用的记录早于本次报告，不能证明记录了本次结果。
                state = "unknown"
            elif all(row is not other for _, other in cited):
                cited.append((source, row))
        states.append(state)
    if "not_documented" in states:
        if untimed:
            return _PathologyDocumentationOutcome(
                "data_gap", "pathology_event_association_unresolved", checked=tuple(checked), **usage,
            )
        return _PathologyDocumentationOutcome(
            "non_compliant",
            "pathology_sampling_not_documented" if sampling else "pathology_result_not_documented",
            checked=tuple(checked), **usage,
        )
    if "unknown" in states:
        return _PathologyDocumentationOutcome(
            "data_gap", "pathology_event_association_unresolved", checked=tuple(checked), **usage,
        )
    return _PathologyDocumentationOutcome(
        "compliant",
        "pathology_sampling_recorded" if sampling else "pathology_result_documented",
        cited=tuple(cited), checked=tuple(checked), **usage,
    )


def _normalized_comparison_text(value: Any) -> str:
    return re.sub(r"[^0-9a-z\u3400-\u9fff]+", "", _clean(value).lower())


def _date_value(value: Any) -> date | None:
    if isinstance(value, datetime):
        return value.date()
    text = _clean(value)
    if not text:
        return None
    try:
        normalized = text.replace("T", " ").replace("Z", "+00:00")
        return datetime.fromisoformat(normalized).date()
    except ValueError:
        return None


def _course_record_date(row: Mapping[str, Any]) -> date | None:
    # “今日/当日”只能绑定临床记录时间；文书提交时间不代表用药发生日期。
    for key in ("record_time", "record_datetime"):
        if value := _date_value(row.get(key)):
            return value
    return None


def _chemotherapy_time_state(
    *,
    prescribed: Any,
    drug_name: str,
    course_rows: Sequence[Mapping[str, Any]],
) -> str:
    """将病程中的今日/当日绑定到文书日期，再与医嘱日期核对。"""

    prescribed_date = _date_value(prescribed)
    if prescribed_date is None:
        return "unknown"
    normalized_drug = _normalized_comparison_text(drug_name)
    candidates = tuple(
        row
        for row in course_rows
        if not normalized_drug
        or normalized_drug in _normalized_comparison_text(_row_text(row))
    )
    if not candidates:
        return "unknown"

    observed_dates: list[date] = []
    for row in candidates:
        row_text = _row_text(row)
        for match in _CHEMOTHERAPY_EXPLICIT_DATE_PATTERN.finditer(row_text):
            try:
                observed_dates.append(
                    datetime(
                        int(match.group("year")),
                        int(match.group("month")),
                        int(match.group("day")),
                    ).date()
                )
            except ValueError:
                continue
        if _CHEMOTHERAPY_RELATIVE_DATE_PATTERN.search(row_text):
            if record_date := _course_record_date(row):
                observed_dates.append(record_date)

    if prescribed_date in observed_dates:
        return "matched"
    if observed_dates:
        return "mismatched"
    return "unknown"


def _course_record_text(row: Mapping[str, Any]) -> str:
    return _clean(
        row.get("record_content") or row.get("content") or row.get("assembled_text")
    )


def _project_course_clause(
    row: Mapping[str, Any], clause: str
) -> Mapping[str, Any]:
    projected = dict(row)
    # _row_text 优先取 content；覆盖后确保比较仅使用当前片段。
    projected["content"] = clause
    projected["record_content"] = clause
    projected["assembled_text"] = clause
    # 仅供同一请求内的 document_rows 回投原始材料行；不得进入 Prompt、事实或客户 DTO。
    projected["_source_material_row"] = row
    return projected


_CHEMO_MASS_UNIT_FACTORS = {
    "mg": Decimal(1), "毫克": Decimal(1), "g": Decimal(1000), "克": Decimal(1000),
    "μg": Decimal("0.001"), "ug": Decimal("0.001"), "mcg": Decimal("0.001"), "微克": Decimal("0.001"),
}


def _chemotherapy_dose_unit_unconfirmed(expected: str, observed: str) -> bool:
    """病程写的是同一质量的另一单位写法（毫克、g 等）：换算口径待确认，不能判不一致。"""

    parsed = re.fullmatch(r"([+-]?(?:\d+(?:\.\d*)?|\.\d+))(.+)?", re.sub(r"\s+", "", expected).lower())
    if parsed is None or (parsed.group(2) or "") not in _CHEMO_MASS_UNIT_FACTORS:
        return False
    expected_mass = Decimal(parsed.group(1)) * _CHEMO_MASS_UNIT_FACTORS[parsed.group(2)]
    units = "|".join(sorted((re.escape(unit) for unit in _CHEMO_MASS_UNIT_FACTORS), key=len, reverse=True))
    for match in re.finditer(
        r"(?<![\d.+-])(\d+(?:\.\d*)?|\.\d+)\s*(" + units + r")(?![a-z0-9])(?!\s*[/／⁄∕²³^·⋅∙])",
        observed, re.IGNORECASE,
    ):
        unit = match.group(2).lower()
        if unit != parsed.group(2) and Decimal(match.group(1)) * _CHEMO_MASS_UNIT_FACTORS[unit] == expected_mass:
            return True
    return False


def _chemotherapy_dose_matches(expected: str, observed: str) -> bool:
    """只比较完整数值和原单位，保留正负号、小数点及单位分母。"""

    compact_expected = re.sub(r"\s+", "", expected).lower()
    parsed = re.fullmatch(r"([+-]?(?:\d+(?:\.\d*)?|\.\d+))(.+)?", compact_expected)
    if parsed is None:
        return False
    try:
        expected_value = Decimal(parsed.group(1))
    except InvalidOperation:
        return False
    unit = parsed.group(2) or ""
    # 保留单位后的空白边界：mg d1/ivgtt 是剂量后的独立频次或途径。
    # 数值内ASCII千分位作为整体；d1后的逗号及中文句读不属于剂量数字。
    # d1,130mg中的日程数字不是千分位；其他字母前缀不阻断完整剂量。
    observed = re.sub(r"(?<![a-z])d\d+\s*[,，]", "；", observed, flags=re.IGNORECASE)
    dose_pattern = re.compile(
        r"(?<![\d.+-])"
        r"((?:[+-]\s*)?(?:\d{1,3}(?:,\d{3})+(?:\.\d*)?|\d+(?:\.\d*)?|\.\d+))\s*"
        + re.escape(unit)
        + r"(?![a-z0-9])"
        + r"(?!\s*[/／⁄∕²³^·⋅∙])",
        re.IGNORECASE,
    )
    return any(
        Decimal(re.sub(r"\s+", "", match.group(1)).replace(",", "").replace("，", "")) == expected_value
        for match in dose_pattern.finditer(observed)
    )


def _compact_dose(value: str) -> str:
    return re.sub(r"\s+", "", value).lower()


def _chemotherapy_fact_date_text(row: Mapping[str, Any], fact: Any) -> str:
    """该次给药的日期依据文本。

    优先用模型绑定的日期原文或片段本身；片段内无日期时退到片段所在的同一句，
    该句只有一个日期表述时才算归属（如“2026-04-26 使用奥沙利铂120mg 静滴。”），
    多个日期仍交由时间比较判为未知，不跨句借用日期。
    """

    if fact.date_quote:
        return fact.date_quote
    if _CHEMOTHERAPY_EXPLICIT_DATE_PATTERN.search(fact.quote) or _CHEMOTHERAPY_RELATIVE_DATE_PATTERN.search(fact.quote):
        return fact.quote
    body = _course_record_text(row)
    start = body.find(fact.quote)
    if start < 0 or body.find(fact.quote, start + 1) >= 0:
        return fact.quote
    end = start + len(fact.quote)
    separators = list(_CLINICAL_CLAUSE_SEPARATOR.finditer(body))
    sentence_start = max((m.end() for m in separators if m.end() <= start), default=0)
    sentence_end = min((m.start() for m in separators if m.start() >= end), default=len(body))
    sentence = body[sentence_start:sentence_end]
    date_mentions = len(_CHEMOTHERAPY_EXPLICIT_DATE_PATTERN.findall(sentence)) + len(
        _CHEMOTHERAPY_RELATIVE_DATE_PATTERN.findall(sentence)
    )
    return sentence if date_mentions == 1 else fact.quote


def _chemotherapy_fact_date(row: Mapping[str, Any], fact: Any) -> date | None:
    """该次给药片段内唯一可确定的临床日期；多个或无法绑定时返回 None。"""

    text = _chemotherapy_fact_date_text(row, fact)
    dates = set()
    for match in _CHEMOTHERAPY_EXPLICIT_DATE_PATTERN.finditer(text):
        try:
            dates.add(datetime(int(match.group("year")), int(match.group("month")), int(match.group("day"))).date())
        except ValueError:
            return None
    if _CHEMOTHERAPY_RELATIVE_DATE_PATTERN.search(text):
        record_date = _course_record_date(row)
        if record_date is None:
            return None
        dates.add(record_date)
    return next(iter(dates)) if len(dates) == 1 else None


def _chemotherapy_fact_time_state(prescribed: Any, row: Mapping[str, Any], fact: Any) -> str:
    """只用该条给药事实片段内的日期（今日/当日绑定临床记录时间）核对医嘱日期。"""

    return _chemotherapy_time_state(
        prescribed=prescribed,
        drug_name="",
        course_rows=(_project_course_clause(row, _chemotherapy_fact_date_text(row, fact)),),
    )


def _chemotherapy_candidate_course_rows(
    rows: Sequence[Mapping[str, Any]],
    *,
    chemotherapy_orders: Sequence[Mapping[str, Any]],
    target_names: Sequence[str],
) -> tuple[Mapping[str, Any], ...]:
    """医嘱日期前后时间窗内的病程，及点名目标药的病程；其余病程不送模型。"""

    prescribed_dates = [
        value for row in chemotherapy_orders
        if (value := _date_value(_clean(row.get("prescribed_datetime") or row.get("order_time"))))
    ]
    normalized_targets = [_normalized_comparison_text(name) for name in target_names]
    selected = []
    for row in rows:
        text = _course_record_text(row)
        if not text:
            continue
        record_date = _course_record_date(row)
        in_window = record_date is not None and any(
            -1 <= (record_date - value).days <= 7 for value in prescribed_dates
        )
        names_target = any(target and target in _normalized_comparison_text(text) for target in normalized_targets)
        if in_window or names_target:
            selected.append(row)
    return tuple(selected)


async def _typed_chemotherapy_comparison(
    *,
    orders: SourceMaterial,
    course_records: SourceMaterial,
    llm_client: Any = None,
    extractions: list[Any] | None = None,
) -> tuple[
    str,
    str,
    Mapping[str, Any] | None,
    tuple[Mapping[str, Any], ...],
    tuple[Mapping[str, Any], ...],
]:
    """以结构化医嘱为权威值，逐项核对病程中的药名、剂量、用法和时间。"""

    chemotherapy_orders = tuple(
        row
        for row in orders.rows
        if _CHEMOTHERAPY_CLASS_PATTERN.search(
            _clean(
                row.get("drug_type")
                or row.get("order_class")
                or row.get("order_category")
            )
        )
    )
    if not chemotherapy_orders:
        return "data_gap", "chemotherapy_fact_unavailable", None, (), ()
    # 冻结口径（院方状态码表待提供）：取消/撤销/作废医嘱不证明用药，排除后无有效
    # 化疗医嘱即不适用；拟执行医嘱尚未证明实施，资料不足。未列出的状态沿用原行为。
    statuses = [_clean(row.get("order_status")) for row in chemotherapy_orders]
    chemotherapy_orders = tuple(
        row for row, status in zip(chemotherapy_orders, statuses)
        if status not in _CHEMO_ORDER_VOID_STATUSES
    )
    if not chemotherapy_orders:
        return "not_applicable", "chemotherapy_orders_cancelled", None, (), ()
    if any(_clean(row.get("order_status")) in _CHEMO_ORDER_PENDING_STATUSES for row in chemotherapy_orders):
        return "data_gap", "chemotherapy_order_not_executed", None, chemotherapy_orders, ()
    if not any(_course_record_text(row) for row in course_records.rows):
        return "data_gap", "chemotherapy_course_record_unavailable", None, (), ()

    field_results = {
        "drug_name": "matched",
        "dose": "matched",
        "route": "matched",
        "time": "matched",
    }
    missing_order_fields: set[str] = set()
    missing_order_event_count = 0
    target_drug_names: list[str] = []
    all_events: list[dict[str, str]] = []
    expected_events: list[dict[str, str]] = []
    for row in chemotherapy_orders:
        event_missing_fields: set[str] = set()
        drug_name = _clean(
            row.get("generic_name") or row.get("drug_name") or row.get("brand_name")
        )
        if drug_name:
            target_drug_names.append(drug_name)
        dose_value = _clean(row.get("single_dose") or row.get("dose"))
        dose_unit = _clean(row.get("single_dose_unit") or row.get("dose_unit"))
        route = _clean(row.get("drug_apply_method") or row.get("administration_route"))
        prescribed = _clean(row.get("prescribed_datetime") or row.get("order_time"))
        # 医嘱缺单位不足以核对剂量，复用既有资料不足合同，不推定不一致。
        if not dose_unit:
            event_missing_fields.add("dose")
        expected_values = {
            "drug_name": drug_name,
            "dose": f"{dose_value}{dose_unit}" if dose_value else "",
            "route": route,
        }
        for field, expected in expected_values.items():
            if not _normalized_comparison_text(expected):
                event_missing_fields.add(field)
        if not _date_value(prescribed):
            event_missing_fields.add("time")
        event = {
            "drug_name": drug_name,
            "dose": expected_values["dose"],
            "route": route,
            "prescribed": prescribed,
        }
        all_events.append(event)
        if event_missing_fields:
            missing_order_fields.update(event_missing_fields)
            missing_order_event_count += 1
            continue
        expected_events.append(event)

    unresolved_event_count = 0
    missing_course_event_count = 0
    unknown_time_event_count = 0
    selected_course_rows: list[Mapping[str, Any]] = []
    if expected_events:
        # 目标药物身份只给模型药名（不给剂量），由模型逐份病程抽取给药原子事实。
        target_names = list({
            _normalized_comparison_text(name): name for name in reversed(target_drug_names)
        }.values())[::-1]
        target_index = {_normalized_comparison_text(name): index for index, name in enumerate(target_names)}
        candidate_rows = _chemotherapy_candidate_course_rows(
            course_records.rows, chemotherapy_orders=chemotherapy_orders, target_names=target_names,
        )
        documents = [
            CourseDocument(f"c{index}", _course_record_text(row)) for index, row in enumerate(candidate_rows)
        ]
        extraction = await extract_chemotherapy_administrations(documents, target_names, llm_client)
        if extractions is not None:
            extractions.append(extraction)
        if extraction.state != "ready":
            # 沿用本执行器的模型错误原因码约定。
            reason = {"model_invalid_output": "tumor_llm_invalid_output",
                      "model_transport_error": "tumor_llm_failure"}.get(extraction.reason_code, extraction.reason_code)
            return extraction.state, reason, None, chemotherapy_orders, ()
        related_by_target: dict[int, list[tuple[Mapping[str, Any], Any]]] = {}
        for row, document in zip(candidate_rows, documents):
            for fact in extraction.facts.get(document.document_ref, ()):
                related_by_target.setdefault(fact.target_index, []).append((row, fact))
        # 有病程未能完整核查目标药提及时，“没抽到”不能证明病程未记录。
        coverage_incomplete = bool(extraction.uncovered_documents)
        incomplete_events = [event for event in all_events if event not in expected_events]
        claimed_facts: set[int] = set()
        for event in expected_events:
            normalized_drug = _normalized_comparison_text(event["drug_name"])
            related = related_by_target.get(target_index[normalized_drug], [])
            # 有病程未能完整核查时，已抽到的事实也可能不全，不能据此确认一致或缺失。
            if coverage_incomplete or any(fact.action == "unknown" for _, fact in related):
                unresolved_event_count += 1
                continue
            administered = [(row, fact) for row, fact in related if fact.action == "administered"]
            planned = [(row, fact) for row, fact in related if fact.action == "planned"]
            withheld = [(row, fact) for row, fact in related if fact.action == "withheld"]
            if not administered:
                if withheld:
                    # 病程明确未给/停用而医嘱为执行：记录与医嘱不一致。
                    field_results["drug_name"] = "mismatched"
                    selected_course_rows.extend(row for row, _ in withheld)
                elif planned:
                    # 仅计划不能证明已实施，也不能断言未记录。
                    unresolved_event_count += 1
                else:
                    missing_course_event_count += 1
                    field_results["drug_name"] = "mismatched"
                continue
            administered_rows = {id(row) for row, _ in administered}
            administered_doses = {_compact_dose(fact.dose_quote) for _, fact in administered}
            if any(
                id(row) in administered_rows and fact.dose_quote
                and _compact_dose(fact.dose_quote) not in administered_doses
                for row, fact in planned
            ):
                # 同篇既有实际给药又有不同剂量的计划改量：医嘱可能对应任一方案，归属不明。
                unresolved_event_count += 1
                continue
            timed = [
                (row, fact) for row, fact in administered
                if _chemotherapy_fact_time_state(event["prescribed"], row, fact) == "matched"
            ]
            if len(timed) == 1:
                row, fact = timed[0]
            elif len(timed) > 1 or len(administered) > 1:
                unresolved_event_count += 1
                continue
            else:
                row, fact = administered[0]
            if id(fact) in claimed_facts:
                unresolved_event_count += 1
                continue
            # 缺字段医嘱若同药或药名不明，只有该次给药的临床日期能将其排除为归属。
            fact_date = _chemotherapy_fact_date(row, fact)
            if any(
                (not _normalized_comparison_text(other["drug_name"])
                 or _normalized_comparison_text(other["drug_name"]) == normalized_drug)
                and not (
                    fact_date is not None
                    and (other_date := _date_value(other["prescribed"])) is not None
                    and fact_date != other_date
                )
                for other in incomplete_events
            ):
                unresolved_event_count += 1
                continue
            claimed_facts.add(id(fact))
            selected_course_rows.append(row)
            # 片段已保证至多一个剂量；在整条片段上沿用既有剂量边界规则（d1、分母、千分位等）。
            if not fact.dose_quote or not _chemotherapy_dose_matches(event["dose"], fact.quote):
                field_results["dose"] = (
                    "unknown" if fact.dose_quote
                    and _chemotherapy_dose_unit_unconfirmed(event["dose"], fact.quote)
                    and field_results["dose"] != "mismatched" else "mismatched"
                )
            route_text = _normalized_comparison_text(fact.route_quote or fact.quote)
            if _normalized_comparison_text(event["route"]) not in route_text:
                field_results["route"] = "mismatched"
            time_state = _chemotherapy_fact_time_state(event["prescribed"], row, fact)
            if time_state == "unknown":
                unknown_time_event_count += 1
            if time_state == "mismatched" or (
                time_state == "unknown" and field_results["time"] != "mismatched"
            ):
                field_results["time"] = time_state

    if missing_order_event_count or unresolved_event_count or missing_course_event_count:
        # 汇总未能核对的事件：未知不能冒充匹配，也不能覆盖已确认的不一致。
        field_results = {
            key: "unknown" if value == "matched" else value
            for key, value in field_results.items()
        }

    facts = {
        "verification_kind": "chemotherapy_order_course_comparison",
        "order_count": len(chemotherapy_orders),
        "field_results": field_results,
        "missing_order_fields": sorted(missing_order_fields),
        "missing_order_event_count": missing_order_event_count,
        "unresolved_event_count": unresolved_event_count,
        "missing_course_event_count": missing_course_event_count,
        "unknown_time_event_count": unknown_time_event_count,
    }
    if missing_order_fields:
        # 完整独立事件已确认的不一致不能被另一事件的字段缺口掩盖。
        independent_mismatch = "mismatched" in field_results.values()
        return (
            "non_compliant" if independent_mismatch else "data_gap",
            "chemotherapy_record_mismatch" if independent_mismatch else "chemotherapy_order_fields_missing",
            facts,
            chemotherapy_orders,
            tuple(selected_course_rows),
        )
    if unresolved_event_count:
        return (
            "data_gap",
            "chemotherapy_event_association_ambiguous",
            facts,
            chemotherapy_orders,
            tuple(selected_course_rows),
        )
    if field_results["dose"] == "unknown" and "mismatched" not in field_results.values():
        return (
            "data_gap",
            "chemotherapy_dose_unit_unconfirmed",
            facts,
            chemotherapy_orders,
            tuple(selected_course_rows),
        )
    if unknown_time_event_count or (
        not missing_course_event_count
        and any(value == "unknown" for value in field_results.values())
    ):
        return (
            "data_gap",
            "chemotherapy_time_unavailable",
            facts,
            chemotherapy_orders,
            tuple(selected_course_rows),
        )
    if any(value == "mismatched" for value in field_results.values()):
        return (
            "non_compliant",
            "chemotherapy_record_mismatch",
            facts,
            chemotherapy_orders,
            tuple(selected_course_rows),
        )
    return (
        "compliant",
        "chemotherapy_record_matches_order",
        facts,
        chemotherapy_orders,
        tuple(selected_course_rows),
    )


def _is_future_discharge_treatment_clause(clause: str) -> bool:
    """历史语境中的继续/建议不证明未来计划，明确出院后语境可重新起算。"""

    if not _DISCHARGE_PLAN_FUTURE_PATTERN.search(clause):
        return False
    history_pattern = re.compile(
        r"既往|此前|曾经|曾予|曾行|入院后|住院期间|住院中|住院后|本次住院|已完成|已结束"
    )
    future_scope_pattern = re.compile(r"出院后|离院后|后续|下次")
    for treatment in _DISCHARGE_PLAN_TREATMENT_PATTERN.finditer(clause):
        prefix = clause[: treatment.start()]
        history_positions = [item.start() for item in history_pattern.finditer(prefix)]
        future_positions = [item.start() for item in future_scope_pattern.finditer(prefix)]
        if not history_positions or (
            future_positions and future_positions[-1] > history_positions[-1]
        ):
            return True
    return False


def _typed_discharge_plan_outcome(
    material: SourceMaterial,
) -> tuple[str, str, Mapping[str, Any]]:
    clauses = tuple(
        normalized_clause
        for row in material.rows
        for clause in _CLINICAL_CLAUSE_SEPARATOR.split(_row_text(row))
        if (normalized_clause := _clean(clause))
    )
    future_plan = any(_DISCHARGE_PLAN_FUTURE_PATTERN.search(item) for item in clauses)
    treatment_plan_clauses = tuple(
        item
        for item in clauses
        if _is_future_discharge_treatment_clause(item)
        and not _DISCHARGE_PLAN_NEGATIVE_TREATMENT_PATTERN.search(item)
        and not _DISCHARGE_PLAN_PENDING_TREATMENT_PATTERN.search(item)
    )
    treatment_plan = bool(treatment_plan_clauses)
    follow_up_plan = any(
        _DISCHARGE_PLAN_FOLLOW_UP_PATTERN.search(item)
        and not _DISCHARGE_PLAN_CONDITIONAL_PATTERN.search(item)
        for item in clauses
    )
    compliant = treatment_plan or follow_up_plan
    return (
        "compliant" if compliant else "non_compliant",
        "malignant_discharge_plan_recorded"
        if compliant
        else "malignant_discharge_plan_missing",
        {
            "verification_kind": "malignant_discharge_plan_check",
            "malignant_diagnosis_present": True,
            "plan_items": {
                "future_plan": future_plan,
                "tumor_treatment": treatment_plan,
                "follow_up": follow_up_plan,
            },
            "requirement_met": compliant,
        },
    )


async def execute_luxian_0609_native_tumor_pathology_rules(
    *,
    rule_ids: Sequence[str],
    wrapper_rules: Sequence[Mapping[str, Any]],
    evidence_payload: Mapping[str, Any] | None,
    institute_id: str,
    patient_id: str,
    visit_id: str,
    source_schema: str | None,
    llm_client: TumorPathologyLLMClient | None,
    evidence_snapshot: Luxian0609EvidenceSnapshot | None = None,
    evidence_materials: Luxian0609EvidenceMaterialStore | None = None,
    decision_rule_ids: Sequence[str] = (),
    malignancy_resolver: MalignancyFactResolver | None = None,
) -> NativeTumorPathologyExecutionResult:
    """按客户目录顺序执行；无受控适用事实时不调用模型。"""

    requested = tuple(dict.fromkeys(
        str(rule_id or "").strip().upper()
        for rule_id in rule_ids
        if str(rule_id or "").strip()
    ))
    selected = tuple(
        rule_id for rule_id in requested
        if rule_id in EXECUTABLE_TUMOR_PATHOLOGY_RULE_IDS
    )
    typed_requested = {
        str(rule_id or "").strip().upper() for rule_id in decision_rule_ids
    }
    if (
        not typed_requested.issubset(_TYPED_DECISION_RULE_IDS)
        or not typed_requested.issubset(set(selected))
    ):
        raise ValueError("unsupported typed tumor pathology rule scope")
    if typed_requested and (
        type(evidence_snapshot) is not Luxian0609EvidenceSnapshot
        or type(evidence_materials) is not Luxian0609EvidenceMaterialStore
        or evidence_materials.snapshot_hash != evidence_snapshot.snapshot_hash
    ):
        raise ValueError("typed tumor pathology rules require one evidence session")
    if not selected:
        return NativeTumorPathologyExecutionResult((), ())

    shared_malignancy = malignancy_resolver or MalignancyFactResolver(llm_client)

    documents = _documents(evidence_payload)
    facts = _timeline_facts(evidence_payload)
    cache: dict[str, SourceMaterial] = {}
    typed_cache: dict[str, SourceMaterial] = {}

    def source(source_key: str) -> SourceMaterial:
        if source_key not in cache:
            cache[source_key] = _load_source(
                documents=documents,
                source_key=source_key,
                institute_id=institute_id,
                patient_id=patient_id,
                visit_id=visit_id,
                source_schema=source_schema,
                evidence_snapshot=evidence_snapshot,
                evidence_materials=evidence_materials,
            )
        return cache[source_key]

    def typed_source(source_key: str) -> SourceMaterial:
        if source_key not in typed_cache:
            assert evidence_snapshot is not None
            assert evidence_materials is not None
            typed_cache[source_key] = _load_typed_source(
                source_key=source_key,
                evidence_snapshot=evidence_snapshot,
                evidence_materials=evidence_materials,
            )
        return typed_cache[source_key]

    def typed_document_refs(
        *selected: tuple[str, Sequence[Mapping[str, Any]]],
    ) -> tuple[str, ...]:
        """将执行器实际采用的材料行转换为同一会话已验证的文书引用。"""

        if evidence_snapshot is None or evidence_materials is None:
            return ()
        refs: list[str] = []
        for source_key, selected_rows in selected:
            target_rows = {
                id(
                    row.get("_source_material_row")
                    if isinstance(row.get("_source_material_row"), Mapping)
                    else row
                )
                for row in selected_rows
            }
            if not target_rows:
                continue
            try:
                document_rows = evidence_materials.document_rows(
                    source_key,
                    snapshot=evidence_snapshot,
                )
            except (EvidenceMaterialTruncated, EvidenceMaterialUnavailable, ValueError):
                continue
            refs.extend(
                document_ref
                for document_ref, row in document_rows
                if id(row) in target_rows
            )
        return tuple(dict.fromkeys(refs))

    def typed_context_document_refs(
        source_keys: Sequence[str],
        materials: Mapping[str, SourceMaterial],
    ) -> tuple[str, ...]:
        """语义执行失败时保留真实送模上下文，不以来源级快照引用替代。"""

        return typed_document_refs(
            *( (source_key, materials[source_key].rows) for source_key in source_keys )
        )

    wrappers_by_id = {
        str(wrapper.get("rule_id") or wrapper.get("rule_code") or "")
        .strip()
        .upper(): wrapper
        for wrapper in wrapper_rules
        if isinstance(wrapper, Mapping)
    }
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
        fact_refs: Sequence[str] = (),
    ) -> None:
        if status == "technical_error":
            # 诊断日志：只记规则、原因码、是否类型化与出错代码行，不含病历或模型内容。
            logger.warning(
                "LX0609 肿瘤病理族技术错误: rule_id=%s reason_code=%s typed=%s call_line=%s",
                rule_id, reason_code, rule_id in typed_requested, sys._getframe(1).f_lineno,
            )
        outcome = _TumorRuleOutcome(
            rule_id=rule_id,
            status=status,
            reason_code=reason_code,
            executor_type=executor_type,
            fact_refs=tuple(dict.fromkeys(fact_refs)),
        )
        if rule_id in typed_requested:
            assert evidence_snapshot is not None
            decisions.append(
                _typed_decision_from_outcome(
                    outcome=outcome,
                    snapshot=evidence_snapshot,
                )
            )
            if display_facts is not None:
                customer_display_facts.append((rule_id, display_facts))
        else:
            results.append(
                _result(
                    outcome.rule_id,
                    outcome.status,
                    outcome.reason_code,
                    executor_type=outcome.executor_type,
                )
            )
    llm_call_count = prompt_tokens = completion_tokens = total_tokens = 0
    api_time = 0.0

    for rule_id in selected:
        typed_rule = rule_id in typed_requested
        source_for_rule = typed_source if typed_rule else source
        facts_for_rule = () if typed_rule else facts
        context_sources: tuple[str, ...]
        if rule_id == PATHOLOGY_REPORT_COMPLETENESS_RULE_ID:
            # 新完整性规则只使用同一会话材料；不依赖恶性诊断、旧 payload
            # 或限8行的旧入口，也不能把申请记录视为已执行检查。
            session_available = (
                evidence_snapshot is not None
                and evidence_materials is not None
                and evidence_materials.snapshot_hash == evidence_snapshot.snapshot_hash
            )
            materials = {
                key: typed_source(key) if session_available else SourceMaterial("unavailable")
                for key in PATHOLOGY_COMPLETENESS_SOURCES
            }
            completeness = {
                item.source_key: item.completeness.value
                for item in evidence_snapshot.observations
                if item.source_key in PATHOLOGY_COMPLETENESS_SOURCES
            } if session_available else {}
            outcome = evaluate_pathology_report_completeness(
                master_rows=materials["pathology_exam_master"].rows,
                report_rows=materials["pathology_exam_report"].rows,
                source_states={key: material.state for key, material in materials.items()},
                source_completeness=completeness,
                document_refs=lambda key, rows: typed_document_refs((key, rows)),
            )
            emit_outcome(
                rule_id,
                outcome.status,
                outcome.reason_code,
                executor_type="program",
                display_facts=outcome.display_facts,
                fact_refs=outcome.fact_refs,
            )
            continue
        if rule_id in {"LX0609-06-02-03", "LX0609-06-02-02"}:
            master = source_for_rule("pathology_exam_master")
            report = source_for_rule("pathology_exam_report")
            if rule_id in typed_requested and any(
                material.state == "error" for material in (master, report)
            ):
                emit_outcome(
                    rule_id,
                    "technical_error",
                    "source_query_error",
                    executor_type="program",
                )
                continue
            if rule_id in typed_requested and any(
                material.state in {"unavailable", "truncated"}
                for material in (master, report)
            ):
                emit_outcome(
                    rule_id,
                    "data_gap",
                    "pathology_source_unavailable",
                    executor_type="program",
                )
                continue
            pathology_present = master.state == "present" or report.state == "present"
            if not pathology_present:
                source_failed = any(
                    material.state in {"unavailable", "error", "truncated"}
                    for material in (master, report)
                )
                emit_outcome(
                    rule_id,
                    "data_gap" if source_failed else "not_applicable",
                    "pathology_source_unavailable"
                    if source_failed
                    else "pathology_fact_absent",
                    executor_type="program",
                )
                continue
            requires_complete_pathology_result = rule_id == "LX0609-06-02-03" or (
                rule_id == "LX0609-06-02-02" and typed_rule
            )
            complete_pathology_report_row = (
                _complete_pathology_result_row(report)
                if requires_complete_pathology_result
                else None
            )
            if (
                requires_complete_pathology_result
                and complete_pathology_report_row is None
            ):
                emit_outcome(
                    rule_id,
                    "data_gap",
                    "pathology_final_result_or_report_time_unavailable",
                    executor_type="program",
                    display_facts=_pathology_report_gap_display_facts(report),
                    fact_refs=(
                        typed_document_refs(("pathology_exam_report", report.rows))
                        if typed_rule
                        else ()
                    ),
                )
                continue
            target_context_sources = (
                _PATHOLOGY_RESULT_TARGET_SOURCES
                if typed_rule and rule_id == "LX0609-06-02-03"
                else _LX019_PATHOLOGY_TARGET_SOURCES
                if rule_id == "LX0609-06-02-02"
                else _PATHOLOGY_TARGET_SOURCES
            )
            context_sources = (*_PATHOLOGY_SOURCES, *target_context_sources)
        else:
            diagnosis = source_for_rule("diagnosis")
            if typed_rule and rule_id == "LX0609-05-02-01":
                chemotherapy_orders = source_for_rule("inpat_drug_order")
                course_records = source_for_rule("daily_course_record")
                if chemotherapy_orders.state == "error":
                    emit_outcome(
                        rule_id,
                        "technical_error",
                        "source_query_error",
                        executor_type="program",
                    )
                    continue
                if chemotherapy_orders.state == "empty" or (
                    chemotherapy_orders.state == "present"
                    and not _typed_chemotherapy_orders(chemotherapy_orders)
                ):
                    emit_outcome(
                        rule_id,
                        "not_applicable",
                        "chemotherapy_event_absent",
                        executor_type="program",
                    )
                    continue
                stage = _discharge_stage(
                    source_for_rule("inpat_registration.discharge_horizon"),
                    source_for_rule("discharge_record"),
                )
                if stage == "technical_error":
                    emit_outcome(
                        rule_id,
                        "technical_error",
                        "source_query_error",
                        executor_type="program",
                    )
                    continue
                if stage == "unknown":
                    emit_outcome(
                        rule_id,
                        "data_gap",
                        "discharge_stage_unavailable",
                        executor_type="program",
                    )
                    continue
                malignancy = await shared_malignancy.resolve(
                    _malignancy_sources(source_for_rule, visit_stage=stage)
                )
                usage = shared_malignancy.claim_usage(malignancy)
                llm_call_count += usage.llm_call_count
                prompt_tokens += usage.prompt_tokens
                completion_tokens += usage.completion_tokens
                total_tokens += usage.total_tokens
                api_time += usage.api_time
                if chemotherapy_orders.state in {"unavailable", "truncated"}:
                    status = (
                        "not_applicable"
                        if malignancy.state == "absent"
                        else "data_gap"
                    )
                    emit_outcome(
                        rule_id,
                        status,
                        "chemotherapy_event_absent"
                        if status == "not_applicable"
                        else "chemotherapy_source_unavailable",
                        executor_type="program",
                    )
                    continue
                if malignancy.state == "technical_error":
                    emit_outcome(
                        rule_id,
                        "technical_error",
                        malignancy.reason_code,
                        executor_type="program",
                    )
                    continue
                if malignancy.state != "confirmed":
                    emit_outcome(
                        rule_id,
                        "data_gap",
                        "malignancy_evidence_conflict"
                        if malignancy.state == "absent"
                        else malignancy.reason_code,
                        executor_type="program",
                    )
                    continue
                if course_records.state == "error":
                    emit_outcome(
                        rule_id,
                        "technical_error",
                        "source_query_error",
                        executor_type="program",
                    )
                    continue
                if course_records.state in {"unavailable", "truncated"}:
                    emit_outcome(
                        rule_id,
                        "data_gap",
                        "tumor_target_projection_unavailable",
                        executor_type="program",
                    )
                    continue
                (
                    status,
                    reason_code,
                    display_facts,
                    selected_order_rows,
                    selected_course_rows,
                ) = await _typed_chemotherapy_comparison(
                    orders=chemotherapy_orders,
                    course_records=course_records,
                    llm_client=llm_client,
                    extractions=(chemo_extractions := []),
                )
                for extraction in chemo_extractions:
                    llm_call_count += extraction.llm_call_count
                    prompt_tokens += extraction.prompt_tokens
                    completion_tokens += extraction.completion_tokens
                    total_tokens += extraction.total_tokens
                    api_time += extraction.api_time
                emit_outcome(
                    rule_id,
                    status,
                    reason_code,
                    executor_type="llm" if chemo_extractions else "program",
                    display_facts=display_facts,
                    fact_refs=typed_document_refs(
                        ("inpat_drug_order", selected_order_rows),
                        ("daily_course_record", selected_course_rows),
                    ),
                )
                continue
            if typed_rule and rule_id == "LX0609-08-01-04":
                stage = _discharge_stage(
                    source_for_rule("inpat_registration.discharge_horizon"),
                    source_for_rule("discharge_record"),
                )
                if stage == "technical_error":
                    emit_outcome(
                        rule_id,
                        "technical_error",
                        "source_query_error",
                        executor_type="program",
                    )
                    continue
                if stage == "inpatient":
                    emit_outcome(
                        rule_id,
                        "not_applicable",
                        "visit_not_discharged",
                        executor_type="program",
                    )
                    continue
                if stage == "unknown":
                    emit_outcome(
                        rule_id,
                        "data_gap",
                        "discharge_stage_unavailable",
                        executor_type="program",
                    )
                    continue
                malignancy = await shared_malignancy.resolve(
                    _malignancy_sources(source_for_rule, visit_stage=stage)
                )
                usage = shared_malignancy.claim_usage(malignancy)
                llm_call_count += usage.llm_call_count
                prompt_tokens += usage.prompt_tokens
                completion_tokens += usage.completion_tokens
                total_tokens += usage.total_tokens
                api_time += usage.api_time
                if malignancy.state == "technical_error":
                    emit_outcome(
                        rule_id,
                        "technical_error",
                        malignancy.reason_code,
                        executor_type="program",
                    )
                    continue
                if malignancy.state == "absent":
                    emit_outcome(
                        rule_id,
                        "not_applicable",
                        "malignant_diagnosis_absent",
                        executor_type="program",
                    )
                    continue
                if malignancy.state != "confirmed":
                    # 027 的非 confirmed 出口分两条（`docs/plans/2026-09-12-0910-issue-backlog.md`
                    # §15.4 主协调裁定）：
                    # ① 语义不确定（`malignancy_semantics_uncertain`）且输入**确无**明示恶性可疑
                    #    ⇒ 属「完整输入上的确定性否定」，判 `not_applicable` + `trigger_absent_complete`，
                    #    不携带适用性不确定事实与逐条文书引用（既有 21 条 not_applicable 走同一路径）。
                    # ② 来源缺失/内容不可读，以及**明示未决可疑**（C17 类）⇒ 维持现状
                    #    `data_gap` + 原原因码 + 逐条文书引用（事实合同受限，见下）。
                    if malignancy.reason_code == "malignancy_semantics_uncertain" and not _has_explicit_malignancy_suspicion(
                        discharge_material=source_for_rule("discharge_record"),
                        uncertain_rows=malignancy.uncertain_rows,
                    ):
                        emit_outcome(
                            rule_id,
                            "not_applicable",
                            "trigger_absent_complete",
                            executor_type="program",
                        )
                        continue
                    emit_outcome(
                        rule_id,
                        "data_gap",
                        malignancy.reason_code,
                        executor_type="program",
                        # M17：本分支**恢复携带** `malignant_diagnosis_applicability_uncertain`
                        # 事实。此前为规避 finalizer 降级而丢弃它，代价是客户看不到
                        # 「影像提示恶性可能、缺病理」这条未决线索（C17 只显示"资料不足"）。
                        # 现在事实合同已同步接受 `data_gap` 终态
                        # （`tumor_pathology_result_mapping.py:247`），故可以带。
                        # 该事实仍是**纯展示事实**：不改变状态与原因码，只让客户文案
                        # 说出"恶性性质尚不明确、暂不能确定是否适用"。
                        # 只有确有可疑诊断行时才携带“恶性性质未决”事实；来源不可用或诊断内容
                        # 缺失时没有可展示的未决诊断，按普通资料不足交付，避免事实合同失败。
                        display_facts=(
                            {
                                "verification_kind": "malignant_diagnosis_applicability_uncertain",
                                "malignancy_state": "unknown",
                                "uncertain_diagnosis_count": len(malignancy.uncertain_rows),
                            }
                            if malignancy.uncertain_rows
                            else None
                        ),
                        fact_refs=typed_document_refs(*(
                            (source_key, (row,)) for source_key, row in malignancy.uncertain_rows
                        )),
                    )
                    continue
                context_sources = _DISCHARGE_TARGET_SOURCES
            elif typed_rule:
                raise ValueError("unsupported typed tumor rule")

            malignant_present = typed_rule or _has_fact(
                facts_for_rule,
                _MALIGNANT_FACT_TYPES,
                frozenset({"diagnosis", "pathology_exam_report"}),
            ) or _has_malignant_code(diagnosis)
            if not malignant_present:
                if typed_rule and diagnosis.state == "empty":
                    status = "not_applicable"
                else:
                    status = "not_applicable"
                    if diagnosis.state in {
                        "empty",
                        "unavailable",
                        "error",
                    } or not _has_any_diagnosis_code(diagnosis):
                        status = "data_gap"
                emit_outcome(
                    rule_id,
                    status,
                    "malignant_diagnosis_unavailable"
                    if status == "data_gap"
                    else "malignant_diagnosis_absent",
                    executor_type="program",
                )
                continue
            if rule_id == "LX0609-05-02-01":
                chemo_present = _has_fact(
                    facts_for_rule,
                    _CHEMO_FACT_TYPES,
                    frozenset({"inpat_drug_order"}),
                )
                if not chemo_present:
                    emit_outcome(
                        rule_id,
                        "data_gap",
                        "chemotherapy_fact_unavailable",
                        executor_type="program",
                    )
                    continue
                context_sources = _CHEMO_TARGET_SOURCES
            else:
                context_sources = _DISCHARGE_TARGET_SOURCES

        materials = {
            source_key: source_for_rule(source_key)
            for source_key in context_sources
        }
        required_sources = (
            _PATHOLOGY_RESULT_TARGET_SOURCES
            if typed_rule and rule_id == "LX0609-06-02-03"
            else _LX019_PATHOLOGY_TARGET_SOURCES
            if rule_id == "LX0609-06-02-02" and typed_rule
            else _PATHOLOGY_TARGET_SOURCES
            if rule_id in {"LX0609-06-02-03", "LX0609-06-02-02"}
            else ("inpat_drug_order", "daily_course_record")
            if rule_id == "LX0609-05-02-01"
            else ("discharge_record",)
        )
        if rule_id in typed_requested and any(
            materials[source_key].state == "error"
            for source_key in required_sources
        ):
            emit_outcome(
                rule_id,
                "technical_error",
                "source_query_error",
                executor_type="program",
            )
            continue
        if rule_id in typed_requested and any(
            materials[source_key].state in {"unavailable", "truncated"}
            for source_key in required_sources
        ):
            emit_outcome(
                rule_id,
                "data_gap",
                "tumor_target_projection_unavailable",
                executor_type="program",
            )
            continue
        target_states = tuple(
            materials[source_key].state for source_key in required_sources
        )
        if rule_id == "LX0609-06-02-03" and all(
            state == "empty" for state in target_states
        ):
            emit_outcome(
                rule_id,
                "non_compliant",
                "pathology_result_not_documented",
                executor_type="program",
                display_facts=_pathology_result_display_facts(
                    status="non_compliant",
                    pathology_master=master,
                    pathology_report=report,
                    surgery_record=materials["surgery_record"],
                    daily_course_record=materials["daily_course_record"],
                    senior_course_record=materials.get("senior_course_record"),
                ),
                fact_refs=(
                        typed_document_refs(
                            (
                                "pathology_exam_report",
                                (complete_pathology_report_row,),
                            )
                        )
                    if typed_rule
                    else ()
                ),
            )
            continue
        if rule_id == "LX0609-06-02-02" and all(
            state == "empty" for state in target_states
        ):
            missing_sampling_facts = _lx019_missing_sampling_display_facts(
                pathology_master=master,
                pathology_report=report,
                surgery_record=materials["surgery_record"],
                daily_course_record=materials["daily_course_record"],
            )
            emit_outcome(
                rule_id,
                "non_compliant" if missing_sampling_facts else "data_gap",
                "pathology_sampling_not_documented"
                if missing_sampling_facts
                else "tumor_target_projection_unavailable",
                executor_type="program",
                display_facts=missing_sampling_facts,
                fact_refs=(
                    typed_document_refs(
                        ("pathology_exam_master", master.rows),
                        ("pathology_exam_report", report.rows),
                    )
                    if typed_rule
                    else ()
                ),
            )
            continue
        if rule_id in {"LX0609-06-02-03", "LX0609-06-02-02"}:
            target_material_available = (
                all(state in {"present", "empty"} for state in target_states)
                and "present" in target_states
            )
        else:
            target_material_available = all(
                state == "present" for state in target_states
            )
        if not target_material_available:
            emit_outcome(
                rule_id,
                "data_gap",
                "tumor_target_projection_unavailable",
                executor_type="program",
            )
            continue
        if typed_rule and rule_id in {"LX0609-06-02-02", "LX0609-06-02-03"}:
            target_materials = {key: materials[key] for key in required_sources}
            sampling_rule = rule_id == "LX0609-06-02-02"
            # 院方口径（2026-10-10）：019 有手术记录时只认手术记录中的取材记录；
            # 本次没有手术记录（内镜、穿刺等活检）时，核对日常病程记录。
            sampling_checked = (
                (("surgery_record", target_materials["surgery_record"]),)
                if target_materials["surgery_record"].state == "present"
                else (
                    ("surgery_record", target_materials["surgery_record"]),
                    ("daily_course_record", target_materials["daily_course_record"]),
                )
            ) if sampling_rule else ()
            documentation = await _typed_pathology_documentation(
                rule_id=rule_id, master=master, report=report,
                targets=(
                    {source: material for source, material in sampling_checked if material.state == "present"}
                    if sampling_rule else target_materials
                ),
                llm_client=llm_client,
            )
            llm_call_count += documentation.llm_call_count
            prompt_tokens += documentation.prompt_tokens
            completion_tokens += documentation.completion_tokens
            total_tokens += documentation.total_tokens
            api_time += documentation.api_time
            trigger_rows = (
                *((("pathology_exam_master", master.rows),) if sampling_rule else ()),
                ("pathology_exam_report", report.rows),
            )
            executor_type = "llm" if documentation.llm_call_count else "program"
            if documentation.status in {"technical_error", "data_gap"}:
                emit_outcome(
                    rule_id, documentation.status, documentation.reason_code,
                    executor_type=executor_type,
                    fact_refs=typed_context_document_refs(context_sources, materials),
                )
                continue
            if documentation.status == "compliant":
                display_facts = (
                    _lx019_typed_display_facts(
                        pathology_master=master, pathology_report=report, checked=sampling_checked,
                        documented_sources=list(dict.fromkeys(source for source, _ in documentation.cited)),
                    )
                    if sampling_rule
                    else _pathology_result_display_facts(
                        status="compliant", pathology_master=master, pathology_report=report,
                        surgery_record=target_materials["surgery_record"],
                        daily_course_record=target_materials["daily_course_record"],
                        senior_course_record=target_materials["senior_course_record"],
                    )
                )
                selected_rows = documentation.cited
            else:
                display_facts = (
                    _lx019_typed_display_facts(
                        pathology_master=master, pathology_report=report, checked=sampling_checked,
                        documented_sources=None,
                    )
                    if sampling_rule
                    else _pathology_result_display_facts(
                        status="non_compliant", pathology_master=master, pathology_report=report,
                        surgery_record=target_materials["surgery_record"],
                        daily_course_record=target_materials["daily_course_record"],
                        senior_course_record=target_materials["senior_course_record"],
                    )
                )
                selected_rows = documentation.checked
            emit_outcome(
                rule_id, documentation.status, documentation.reason_code,
                executor_type=executor_type, display_facts=display_facts,
                fact_refs=typed_document_refs(
                    *trigger_rows, *((source, (row,)) for source, row in selected_rows),
                ),
            )
            continue
        if rule_id == "LX0609-08-01-04" and typed_rule:
            status, reason_code, display_facts = _typed_discharge_plan_outcome(
                materials["discharge_record"]
            )
            emit_outcome(
                rule_id,
                status,
                reason_code,
                executor_type="program",
                display_facts=display_facts,
                fact_refs=(
                    typed_document_refs(
                        ("discharge_record", materials["discharge_record"].rows)
                    )
                    if typed_rule
                    else ()
                ),
            )
            continue
        sampling_surgery = materials.get("surgery_record")
        if (
            rule_id == "LX0609-06-02-02"
            and rule_id not in typed_requested
            and sampling_surgery is not None
            and not any("surgery_process" in row for row in sampling_surgery.rows)
        ):
            live_surgery = _load_source(
                documents=None,
                source_key="surgery_record",
                institute_id=institute_id,
                patient_id=patient_id,
                visit_id=visit_id,
                source_schema=source_schema,
                evidence_snapshot=evidence_snapshot,
                evidence_materials=evidence_materials,
            )
            if live_surgery.state == "present":
                sampling_surgery = live_surgery
        sampling_materials = (
            (
                sampling_surgery or materials["surgery_record"],
                materials["daily_course_record"],
            )
            if rule_id == "LX0609-06-02-02"
            else ()
        )
        sampling_row = (
            _documented_pathology_sampling_row(*sampling_materials)
            if sampling_materials
            else None
        )
        if rule_id == "LX0609-06-02-02" and sampling_row is not None:
            sampling_source = next(
                source_key
                for source_key, material in zip(
                    _LX019_PATHOLOGY_TARGET_SOURCES, sampling_materials
                )
                if any(sampling_row is row for row in material.rows)
            )
            emit_outcome(
                rule_id,
                "compliant",
                "pathology_sampling_recorded",
                executor_type="program",
                display_facts=_pathology_sampling_display_facts(
                    pathology_master=master,
                    pathology_report=report,
                    surgery_record=sampling_surgery or materials["surgery_record"],
                    daily_course_record=materials["daily_course_record"],
                ),
                fact_refs=(
                    typed_document_refs(
                        ("pathology_exam_master", master.rows),
                        ("pathology_exam_report", report.rows),
                        (sampling_source, (sampling_row,)),
                    )
                    if typed_rule
                    else ()
                ),
            )
            continue
        if rule_id == "LX0609-06-02-03":
            documented_row = _documented_pathology_result_row(
                report,
                materials["surgery_record"],
                materials["daily_course_record"],
            )
            documented = documented_row is not None
            explicitly_missing_rows = _explicitly_missing_target_rows(
                _PATHOLOGY_RESULT_MISSING_PATTERN,
                materials["surgery_record"],
                materials["daily_course_record"],
            )
            explicitly_missing = bool(explicitly_missing_rows)
            if documented or explicitly_missing:
                status = "compliant" if documented else "non_compliant"
                if documented_row is not None:
                    target_source_rows = (
                        (
                            "surgery_record"
                            if any(
                                documented_row is row
                                for row in materials["surgery_record"].rows
                            )
                            else "daily_course_record",
                            (documented_row,),
                        ),
                    )
                else:
                    target_source_rows = tuple(
                        (
                            source_key,
                            tuple(
                                row
                                for row in explicitly_missing_rows
                                if any(
                                    row is candidate for candidate in material.rows
                                )
                            ),
                        )
                        for source_key, material in (
                            ("surgery_record", materials["surgery_record"]),
                            ("daily_course_record", materials["daily_course_record"]),
                        )
                    )
                emit_outcome(
                    rule_id,
                    status,
                    "pathology_result_documented"
                    if documented
                    else "pathology_result_not_documented",
                    executor_type="program",
                    display_facts=_pathology_result_display_facts(
                        status=status,
                        pathology_master=master,
                        pathology_report=report,
                        surgery_record=materials["surgery_record"],
                        daily_course_record=materials["daily_course_record"],
                    ),
                    fact_refs=(
                        typed_document_refs(
                            (
                                "pathology_exam_report",
                                (complete_pathology_report_row,),
                            ),
                            *target_source_rows,
                        )
                        if typed_rule
                        else ()
                    ),
                )
                continue
        missing_sampling_rows = (
            _explicitly_missing_target_rows(
                _PATHOLOGY_SAMPLING_MISSING_PATTERN,
                materials["surgery_record"],
                materials["daily_course_record"],
            )
            if rule_id == "LX0609-06-02-02"
            else ()
        )
        if rule_id == "LX0609-06-02-02" and missing_sampling_rows:
            missing_sampling_facts = _lx019_missing_sampling_display_facts(
                pathology_master=master,
                pathology_report=report,
                surgery_record=materials["surgery_record"],
                daily_course_record=materials["daily_course_record"],
            )
            emit_outcome(
                rule_id,
                "non_compliant" if missing_sampling_facts else "data_gap",
                "pathology_sampling_not_documented"
                if missing_sampling_facts
                else "tumor_target_projection_unavailable",
                executor_type="program",
                display_facts=missing_sampling_facts,
                fact_refs=(
                    typed_document_refs(
                        ("pathology_exam_master", master.rows),
                        ("pathology_exam_report", report.rows),
                        *(
                            (source_key, (row,))
                            for source_key, row in zip(
                                _LX019_PATHOLOGY_TARGET_SOURCES,
                                missing_sampling_rows,
                            )
                        ),
                    )
                    if typed_rule
                    else ()
                ),
            )
            continue
        context = "\n".join(
            line
            for source_key in context_sources
            for line in _source_text(source_key, materials[source_key])
        )[:_MAX_CONTEXT_CHARS]
        wrapper = wrappers_by_id.get(rule_id)
        if wrapper is None or not _clean(wrapper.get("custom_prompt")) or not context:
            emit_outcome(
                rule_id,
                "data_gap",
                "tumor_prompt_input_unavailable",
                executor_type="program",
            )
            continue
        if llm_client is None:
            emit_outcome(
                rule_id,
                "technical_error",
                "tumor_llm_failure",
                # 未发起请求不等于程序规则完成判定：此处失败的是受控语义执行器
                # 的可用性，审计类型必须与传输/输出失败保持一致。
                executor_type="llm",
                fact_refs=(
                    typed_context_document_refs(context_sources, materials)
                    if typed_rule
                    else ()
                ),
            )
            continue
        llm_call_count += 1
        try:
            response = await llm_client.generate(_prompt(wrapper, context=context))
        except Exception:
            emit_outcome(
                rule_id,
                "technical_error",
                "tumor_llm_failure",
                executor_type="llm",
                fact_refs=(
                    typed_context_document_refs(context_sources, materials)
                    if typed_rule
                    else ()
                ),
            )
            continue
        if not isinstance(response, Mapping):
            emit_outcome(
                rule_id,
                "technical_error",
                "tumor_llm_invalid_output",
                executor_type="llm",
                fact_refs=(
                    typed_context_document_refs(context_sources, materials)
                    if typed_rule
                    else ()
                ),
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
                "tumor_llm_invalid_output",
                executor_type="llm",
                fact_refs=(
                    typed_context_document_refs(context_sources, materials)
                    if typed_rule
                    else ()
                ),
            )
            continue
        status = "compliant" if is_compliant else "non_compliant"
        display_facts = None
        if rule_id == "LX0609-06-02-03":
            display_facts = _pathology_result_display_facts(
                status=status,
                pathology_master=master,
                pathology_report=report,
                surgery_record=materials["surgery_record"],
                daily_course_record=materials["daily_course_record"],
            )
        elif rule_id == "LX0609-06-02-02" and status == "non_compliant":
            display_facts = _lx019_missing_sampling_display_facts(
                pathology_master=master,
                pathology_report=report,
                surgery_record=materials["surgery_record"],
                daily_course_record=materials["daily_course_record"],
            )
        emit_outcome(
            rule_id,
            status,
            "tumor_customer_prompt",
            executor_type="llm",
            display_facts=display_facts,
            fact_refs=(
                typed_context_document_refs(context_sources, materials)
                if typed_rule
                else ()
            ),
        )

    return NativeTumorPathologyExecutionResult(
        results=tuple(results),
        planned_rule_ids=selected,
        decisions=tuple(decisions),
        customer_display_facts=tuple(customer_display_facts),
        llm_call_count=llm_call_count,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        total_tokens=total_tokens,
        api_time=api_time,
    )
