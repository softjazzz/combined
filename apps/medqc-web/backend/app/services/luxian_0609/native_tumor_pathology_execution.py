"""LX0609 肿瘤病理族原生执行：受控来源门控后逐规则裁剪判定。"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import json
import re
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
from .source_evidence_reader import (
    SourceEvidenceUnavailable,
    read_luxian_0609_native_source_rows,
)


TUMOR_PATHOLOGY_RULE_IDS = (
    "LX0609-013",
    "LX0609-019",
    "LX0609-026",
    "LX0609-027",
)
EXECUTOR_KEY = "tumor_pathology"
_TYPED_DECISION_RULE_IDS = frozenset(TUMOR_PATHOLOGY_RULE_IDS)
_TYPED_RULE_SOURCE_KEYS = {
    "LX0609-013": (
        "pathology_exam_master",
        "pathology_exam_report",
        "surgery_record",
        "daily_course_record",
    ),
    "LX0609-019": (
        "pathology_exam_master",
        "pathology_exam_report",
        "surgery_record",
        "daily_course_record",
    ),
    # 026 仍缺受控化疗事实，只绑定真正读取的恶性诊断来源并保守 DG。
    "LX0609-026": ("diagnosis",),
    "LX0609-027": ("diagnosis", "discharge_record"),
}
_TYPED_EVALUATOR_VERSION = "tumor-pathology-ruledecision-shadow-v1"

_PATHOLOGY_SOURCES = ("pathology_exam_master", "pathology_exam_report")
_PATHOLOGY_TARGET_SOURCES = ("surgery_record", "daily_course_record")
_CHEMO_TARGET_SOURCES = ("inpat_drug_order", "daily_course_record")
_DISCHARGE_TARGET_SOURCES = ("diagnosis", "discharge_record")
_MAX_ROWS_PER_SOURCE = 8
_MAX_ROW_CHARS = 1400
_MAX_CONTEXT_CHARS = 18000
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
    r"(?:待补|待出|待定|待完善|待诊断|待报告|待复核|未出|审核中|尚未|另报|后续正式报告|暂缺|未完成|初步)"
)
_PATHOLOGY_REPORT_DATETIME_PATTERN = re.compile(
    r"^\d{4}-\d{1,2}-\d{1,2}[T ]\d{1,2}:\d{2}(?::\d{2}(?:\.\d{1,6})?)?(?:Z|[+-]\d{2}:?\d{2})?$"
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
}


class TumorPathologyLLMClient(Protocol):
    async def generate(self, prompt: str) -> dict[str, Any]:
        ...


@dataclass(frozen=True)
class SourceMaterial:
    state: str
    rows: tuple[Mapping[str, Any], ...] = ()


@dataclass(frozen=True)
class NativeTumorPathologyExecutionResult:
    results: tuple[dict[str, Any], ...]
    planned_rule_ids: tuple[str, ...]
    decisions: tuple[RuleDecision, ...] = ()
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


def _typed_decision_from_outcome(
    *,
    outcome: _TumorRuleOutcome,
    snapshot: Luxian0609EvidenceSnapshot,
) -> RuleDecision:
    refs = tuple(
        observation.snapshot_ref.removeprefix("sha256:")
        for observation in snapshot.observations
        if observation.source_key in _TYPED_RULE_SOURCE_KEYS[outcome.rule_id]
    )
    if outcome.status in {"compliant", "non_compliant", "not_applicable"} and not refs:
        raise ValueError("typed tumor decision requires evidence refs")

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
        source_gap = "unavailable" in outcome.reason_code
        dimensions = (
            ApplicabilityState.UNKNOWN if source_gap else ApplicabilityState.APPLICABLE,
            EvidenceState.DATA_GAP,
            QcDirection.UNKNOWN,
            "source_unavailable" if source_gap else "required_field_missing",
        )
    elif outcome.status == "technical_error":
        dimensions = (
            ApplicabilityState.ERROR,
            EvidenceState.TECHNICAL_ERROR,
            QcDirection.UNKNOWN,
            "source_query_error"
            if outcome.reason_code == "source_query_error"
            else "executor_exception",
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


def _has_complete_pathology_result(material: SourceMaterial) -> bool:
    """最终结果和报告时间必须来自同一份报告，肉眼/镜下材料不能代替最终诊断。"""

    for row in material.rows:
        report_time = _clean(
            row.get("report_datetime")
            or row.get("report_time")
            or row.get("record_time")
            or row.get("display_time")
            or row.get("authored_at")
        )
        if not report_time:
            continue
        if not _PATHOLOGY_REPORT_DATETIME_PATTERN.fullmatch(report_time):
            continue
        try:
            datetime.fromisoformat(report_time.replace("Z", "+00:00"))
        except ValueError:
            continue
        diagnosis = _clean(row.get("diagnosis"))
        body = _clean(row.get("record_content") or row.get("content"))
        result_text = diagnosis or body
        if not result_text or _PATHOLOGY_PENDING_RESULT_PATTERN.search(result_text):
            continue
        if diagnosis or _PATHOLOGY_FINAL_RESULT_PATTERN.search(body):
            return True
    return False


def _has_documented_pathology_sampling(*materials: SourceMaterial) -> bool:
    """仅接受已实施的取材/送检事实；计划、否定和空模板继续交由模型判断。"""

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
                            return True
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
                    return True
    return False


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
) -> NativeTumorPathologyExecutionResult:
    """按客户目录顺序执行；无受控适用事实时不调用模型。"""

    requested = {str(rule_id or "").strip().upper() for rule_id in rule_ids}
    selected = tuple(
        rule_id for rule_id in TUMOR_PATHOLOGY_RULE_IDS if rule_id in requested
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

    wrappers_by_id = {
        str(wrapper.get("rule_id") or wrapper.get("rule_code") or "")
        .strip()
        .upper(): wrapper
        for wrapper in wrapper_rules
        if isinstance(wrapper, Mapping)
    }
    results: list[dict[str, Any]] = []
    decisions: list[RuleDecision] = []

    def emit_outcome(
        rule_id: str,
        status: str,
        reason_code: str,
        *,
        executor_type: str,
    ) -> None:
        outcome = _TumorRuleOutcome(
            rule_id=rule_id,
            status=status,
            reason_code=reason_code,
            executor_type=executor_type,
        )
        if rule_id in typed_requested:
            assert evidence_snapshot is not None
            decisions.append(
                _typed_decision_from_outcome(
                    outcome=outcome,
                    snapshot=evidence_snapshot,
                )
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
    llm_call_count = prompt_tokens = completion_tokens = total_tokens = 0
    api_time = 0.0

    for rule_id in selected:
        typed_rule = rule_id in typed_requested
        source_for_rule = typed_source if typed_rule else source
        facts_for_rule = () if typed_rule else facts
        context_sources: tuple[str, ...]
        if rule_id in {"LX0609-013", "LX0609-019"}:
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
            if rule_id == "LX0609-013" and not _has_complete_pathology_result(report):
                emit_outcome(
                    rule_id,
                    "data_gap",
                    "pathology_final_result_or_report_time_unavailable",
                    executor_type="program",
                )
                continue
            context_sources = (*_PATHOLOGY_SOURCES, *_PATHOLOGY_TARGET_SOURCES)
        else:
            diagnosis = source_for_rule("diagnosis")
            if typed_rule and diagnosis.state == "error":
                emit_outcome(
                    rule_id,
                    "technical_error",
                    "source_query_error",
                    executor_type="program",
                )
                continue
            if typed_rule and diagnosis.state in {"unavailable", "truncated"}:
                emit_outcome(
                    rule_id,
                    "data_gap",
                    "malignant_diagnosis_unavailable",
                    executor_type="program",
                )
                continue
            malignant_present = _has_fact(
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
            if rule_id == "LX0609-026":
                if typed_rule:
                    # 当前快照没有受控 chemotherapy FactV2，普通药品医嘱不能
                    # 被提升为化疗事实。保守闭合，不回读 legacy timeline_facts。
                    emit_outcome(
                        rule_id,
                        "data_gap",
                        "chemotherapy_fact_unavailable",
                        executor_type="program",
                    )
                    continue
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
            ("surgery_record", "daily_course_record")
            if rule_id in {"LX0609-013", "LX0609-019"}
            else ("inpat_drug_order", "daily_course_record")
            if rule_id == "LX0609-026"
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
        if rule_id == "LX0609-019" and all(
            state == "empty" for state in target_states
        ):
            emit_outcome(
                rule_id,
                "non_compliant",
                "pathology_sampling_not_documented",
                executor_type="program",
            )
            continue
        if rule_id == "LX0609-019":
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
        sampling_surgery = materials.get("surgery_record")
        if (
            rule_id == "LX0609-019"
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
        if rule_id == "LX0609-019" and _has_documented_pathology_sampling(
            sampling_surgery or materials["surgery_record"],
            materials["daily_course_record"],
        ):
            emit_outcome(
                rule_id,
                "compliant",
                "pathology_sampling_recorded",
                executor_type="program",
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
                "data_gap",
                "tumor_llm_unavailable",
                executor_type="program",
            )
            continue
        llm_call_count += 1
        try:
            response = await llm_client.generate(_prompt(wrapper, context=context))
        except Exception:
            emit_outcome(
                rule_id,
                "data_gap",
                "tumor_llm_failure",
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
                "data_gap",
                "tumor_llm_invalid_output",
                executor_type="llm",
            )
            continue
        status = "compliant" if is_compliant else "non_compliant"
        emit_outcome(
            rule_id,
            status,
            "tumor_customer_prompt",
            executor_type="llm",
        )

    return NativeTumorPathologyExecutionResult(
        results=tuple(results),
        planned_rule_ids=selected,
        decisions=tuple(decisions),
        llm_call_count=llm_call_count,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        total_tokens=total_tokens,
        api_time=api_time,
    )
