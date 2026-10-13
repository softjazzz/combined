"""LX0609-01-02-02：首次病程鉴别诊断与第一诊断关联性。"""

from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any, Mapping, Protocol

from ..decision_model import (
    ApplicabilityState,
    CriterionResult,
    CriterionStatus,
    EvidenceState,
    QcDirection,
    RuleDecision,
)
from ..evidence_material import (
    EvidenceMaterialTruncated,
    EvidenceMaterialUnavailable,
    Luxian0609EvidenceMaterialStore,
)
from ..evidence_snapshot import Luxian0609EvidenceSnapshot
from .shared import clean_text, response_json_payload


RULE_ID = "LX0609-01-02-02"
SOURCE_KEYS = (
    "first_course_record",
    "first_course_record_diagnosis",
)
ALLOWED_RESULT_STATUSES = frozenset({"compliant", "non_compliant", "data_gap"})
_DELIVERABLE_DATA_GAP_REASONS = frozenset(
    {
        "source_unavailable",
        "source_truncated",
        "source_readiness_unproven",
        "required_field_missing",
        "linkage_unresolved",
    }
)
_RELATION_STATES = frozenset({"related", "unrelated", "unknown"})
_RATIONALE_CODES = frozenset(
    {"same_clinical_problem", "no_related_item", "insufficient_information"}
)
_DIFFERENTIAL_SECTION = re.compile(
    r"鉴别诊断\s*[:：]\s*(?P<body>.+?)(?=\n\s*(?:诊疗计划|治疗计划|诊治计划|医师签名)\s*[:：]|$)",
    re.DOTALL,
)
_FIRST_DIAGNOSIS_IN_BODY = re.compile(
    r"(?:第一诊断|初步诊断)\s*[:：]\s*(?:\d+[.、]?\s*)?(?P<diagnosis>[^；;，,。\n]{2,100})"
)
_MAX_DIFFERENTIAL_CHARS = 5000
_MAX_DIAGNOSIS_CHARS = 1600
_NUMBERED_DIAGNOSIS_ITEM_PATTERN = re.compile(
    r"(?:^|(?=\d+\s*[、.．,，]))\d+\s*[、.．,，]\s*"
    r"(.*?)(?=\d+\s*[、.．,，]|$)"
)


class Rule077LLMClient(Protocol):
    async def generate(self, prompt: str, **kwargs: Any) -> Mapping[str, Any]: ...


@dataclass(frozen=True)
class Rule077Execution:
    decision: RuleDecision
    llm_call_count: int = 0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    api_time: float = 0.0


@dataclass(frozen=True)
class _FirstDiagnosisEvidence:
    state: str
    first: str
    full_text: str
    refs: tuple[str, ...]
    reason_code: str = ""


def _usage(response: Mapping[str, Any]) -> tuple[int, int, int, float]:
    usage = response.get("usage")
    usage = usage if isinstance(usage, Mapping) else {}
    prompt = int(usage.get("prompt_tokens") or 0)
    completion = int(usage.get("completion_tokens") or 0)
    return (
        prompt,
        completion,
        int(usage.get("total_tokens") or prompt + completion),
        float(response.get("_api_time") or response.get("response_time") or 0.0),
    )


def _row_text(row: Mapping[str, Any]) -> str:
    return clean_text(row.get("record_content") or row.get("content"))


def _differential_text(row: Mapping[str, Any]) -> str:
    structured = clean_text(
        row.get("differential_diagnosis")
        or row.get("differential_diagnoses")
        or row.get("differential_diagnosis_content")
    )
    if structured:
        return structured[:_MAX_DIFFERENTIAL_CHARS]
    match = _DIFFERENTIAL_SECTION.search(_row_text(row))
    return clean_text(match.group("body"))[:_MAX_DIFFERENTIAL_CHARS] if match else ""


def _diagnosis_items(value: Any) -> tuple[str, ...]:
    text = clean_text(value)
    if not text:
        return ()
    numbered = tuple(
        clean_text(item)
        for item in _NUMBERED_DIAGNOSIS_ITEM_PATTERN.findall(text)
        if clean_text(item)
    )
    return numbered or (text,)


def _first_course_row_diagnosis(row: Mapping[str, Any]) -> tuple[str, ...]:
    value = clean_text(
        row.get("first_diagnosis")
        or row.get("primary_diagnosis")
        or row.get("initial_diagnosis")
    )
    if value:
        return _diagnosis_items(value)
    body_match = _FIRST_DIAGNOSIS_IN_BODY.search(_row_text(row))
    return _diagnosis_items(body_match.group("diagnosis")) if body_match else ()


def _first_diagnosis_evidence(
    first_course_pairs: tuple[tuple[str, Mapping[str, Any]], ...],
    diagnosis_pairs: tuple[tuple[str, Mapping[str, Any]], ...],
) -> _FirstDiagnosisEvidence:
    """按首次病程文书 ID 绑定诊断行，拒绝用数据库行序猜第一诊断。"""

    course_refs = tuple(reference for reference, _row in first_course_pairs)
    course_document_ids = {
        clean_text(row.get("document_id"))
        for _reference, row in first_course_pairs
        if clean_text(row.get("document_id"))
    }
    if len(course_document_ids) > 1:
        return _FirstDiagnosisEvidence(
            "unknown",
            "",
            "",
            course_refs,
            "diagnosis_binding_conflict",
        )

    structured_refs = tuple(reference for reference, _row in diagnosis_pairs)
    bound_rows: list[tuple[str, Mapping[str, Any]]] = []
    unbound_rows = False
    for reference, row in diagnosis_pairs:
        row_document_id = clean_text(row.get("document_id"))
        if not row_document_id:
            unbound_rows = True
        elif row_document_id in course_document_ids:
            bound_rows.append((reference, row))
        else:
            unbound_rows = True
    if diagnosis_pairs and (unbound_rows or not bound_rows):
        return _FirstDiagnosisEvidence(
            "unknown",
            "",
            "",
            tuple(dict.fromkeys((*course_refs, *structured_refs))),
            "diagnosis_binding_conflict" if bound_rows else "diagnosis_binding_unavailable",
        )

    if bound_rows:
        candidates: list[tuple[str, tuple[str, ...]]] = []
        for _reference, row in bound_rows:
            if clean_text(row.get("diagnosis_type")) != "初步诊断":
                continue
            items = _diagnosis_items(
                row.get("diagnosis_name") or row.get("diagnosis")
            )
            if items:
                candidates.append((items[0], items))
        if not candidates:
            return _FirstDiagnosisEvidence(
                "unknown",
                "",
                "",
                tuple(dict.fromkeys((*course_refs, *structured_refs))),
                "diagnosis_field_missing",
            )
        first_values = {first for first, _items in candidates}
        if len(first_values) != 1:
            return _FirstDiagnosisEvidence(
                "unknown",
                "",
                "",
                tuple(dict.fromkeys((*course_refs, *structured_refs))),
                "diagnosis_binding_conflict",
            )
        full_items = tuple(
            dict.fromkeys(item for _first, items in candidates for item in items)
        )
        return _FirstDiagnosisEvidence(
            "available",
            next(iter(first_values))[:200],
            "；".join(full_items)[:_MAX_DIAGNOSIS_CHARS],
            tuple(dict.fromkeys((*course_refs, *structured_refs))),
        )

    candidates = [
        items
        for _reference, row in first_course_pairs
        if (items := _first_course_row_diagnosis(row))
    ]
    if not candidates:
        return _FirstDiagnosisEvidence(
            "missing", "", "", course_refs, "diagnosis_field_missing"
        )
    first_values = {items[0] for items in candidates}
    if len(first_values) != 1:
        return _FirstDiagnosisEvidence(
            "unknown", "", "", course_refs, "diagnosis_binding_conflict"
        )
    full_items = tuple(dict.fromkeys(item for items in candidates for item in items))
    return _FirstDiagnosisEvidence(
        "available",
        next(iter(first_values))[:200],
        "；".join(full_items)[:_MAX_DIAGNOSIS_CHARS],
        course_refs,
    )


def _criterion(
    *,
    status: CriterionStatus,
    reason_code: str,
    refs: tuple[str, ...],
    actual: str,
) -> CriterionResult:
    return CriterionResult(
        criterion_id="differential_diagnosis_relation",
        status=status,
        reason_code=reason_code,
        fact_refs=refs,
        actual_value=actual,
        rationale_code=reason_code,
    )


def _decision(
    *,
    snapshot: Luxian0609EvidenceSnapshot,
    refs: tuple[str, ...],
    status: str,
    reason_code: str,
    criterion: CriterionResult | None = None,
) -> RuleDecision:
    if status not in ALLOWED_RESULT_STATUSES:
        raise ValueError("LX0609-01-02-02 produced a status outside its rule contract")
    if status == "data_gap" and reason_code not in _DELIVERABLE_DATA_GAP_REASONS:
        reason_code = (
            "linkage_unresolved"
            if "binding" in reason_code
            else "required_field_missing"
        )
    dimensions = {
        "compliant": (
            ApplicabilityState.APPLICABLE,
            EvidenceState.SUFFICIENT,
            QcDirection.SATISFIED,
            1.0,
        ),
        "non_compliant": (
            ApplicabilityState.APPLICABLE,
            EvidenceState.SUFFICIENT,
            QcDirection.DEFECT,
            1.0,
        ),
        "data_gap": (
            ApplicabilityState.UNKNOWN,
            EvidenceState.DATA_GAP,
            QcDirection.UNKNOWN,
            None,
        ),
    }
    applicability, evidence_state, direction, confidence = dimensions[status]
    return RuleDecision(
        rule_id=RULE_ID,
        snapshot_hash=snapshot.snapshot_hash,
        applicability=applicability,
        evidence_state=evidence_state,
        qc_direction=direction,
        reason_code=reason_code,
        fact_refs=refs,
        evaluator_version="course-differential-relation-v1",
        confidence=confidence,
        criterion_results=(criterion,) if criterion is not None else (),
    )


def _prompt(*, first_diagnosis: str, full_diagnosis: str, differential: str) -> str:
    return f"""你是病历质控中的鉴别诊断关联性核对器。

只判断首次病程记录中已经写出的鉴别诊断，是否是用于解释相同主诉、体征、检查发现或同一临床问题的合理备选诊断。不要判断诊断是否正确，不要补充病历中不存在的诊断。疾病系统相同本身不是充分条件，跨系统也不是否决条件。只要有任一项鉴别诊断围绕第一诊断的临床问题展开即判 related，其余项围绕其他诊断或其他问题不影响；只有全部鉴别诊断都明显不能解释第一诊断的临床问题且正文未说明关联时才判 unrelated。

第一诊断：{first_diagnosis}
初步诊断完整列表/文本：{full_diagnosis}
鉴别诊断：{differential}

relation_state 只能是 related、unrelated、unknown：
- related：至少一项鉴别诊断与第一诊断或其同一临床问题存在合理临床关联；
- unrelated：没有任何一项与第一诊断的临床问题相关，且正文未解释关联；
- unknown：信息存在但无法可靠判断。

只输出 JSON：{{"relation_state":"related|unrelated|unknown","rationale_code":"same_clinical_problem|no_related_item|insufficient_information"}}。"""


async def evaluate_rule_077(
    *,
    snapshot: Luxian0609EvidenceSnapshot,
    materials: Luxian0609EvidenceMaterialStore,
    llm_client: Rule077LLMClient | None,
) -> Rule077Execution:
    try:
        material_rows = {
            source_key: materials.document_rows(source_key, snapshot=snapshot)
            for source_key in SOURCE_KEYS
        }
    except EvidenceMaterialTruncated:
        return Rule077Execution(
            _decision(snapshot=snapshot, refs=(), status="data_gap", reason_code="source_truncated")
        )
    except EvidenceMaterialUnavailable:
        return Rule077Execution(
            _decision(snapshot=snapshot, refs=(), status="data_gap", reason_code="source_unavailable")
        )

    first_course_pairs = material_rows["first_course_record"]
    first_course_rows = tuple(row for _reference, row in first_course_pairs)
    first_course_diagnosis_pairs = material_rows["first_course_record_diagnosis"]

    if not first_course_rows:
        return Rule077Execution(
            _decision(snapshot=snapshot, refs=(), status="data_gap", reason_code="required_field_missing")
        )
    diagnosis_evidence = _first_diagnosis_evidence(
        first_course_pairs,
        first_course_diagnosis_pairs,
    )
    refs = diagnosis_evidence.refs
    differential = next(
        (value for row in first_course_rows if (value := _differential_text(row))),
        "",
    )
    if diagnosis_evidence.state != "available" or not differential:
        reason_code = (
            diagnosis_evidence.reason_code
            if diagnosis_evidence.state != "available"
            else "required_field_missing"
        )
        criterion = _criterion(
            status=CriterionStatus.UNKNOWN,
            reason_code=reason_code,
            refs=refs,
            actual="missing_required_input",
        )
        return Rule077Execution(
            _decision(
                snapshot=snapshot,
                refs=refs,
                status="data_gap",
                reason_code=reason_code,
                criterion=criterion,
            )
        )
    if llm_client is None:
        criterion = _criterion(
            status=CriterionStatus.UNKNOWN,
            reason_code="model_transport_error",
            refs=refs,
            actual="model_unavailable",
        )
        return Rule077Execution(
            _decision(
                snapshot=snapshot,
                refs=refs,
                status="data_gap",
                reason_code="source_readiness_unproven",
                criterion=criterion,
            )
        )

    try:
        response = await llm_client.generate(
            _prompt(
                first_diagnosis=diagnosis_evidence.first,
                full_diagnosis=diagnosis_evidence.full_text,
                differential=differential,
            ),
            max_completion_tokens=180,
            allow_length_retry=False,
        )
    except TimeoutError:
        criterion = _criterion(
            status=CriterionStatus.UNKNOWN,
            reason_code="model_timeout",
            refs=refs,
            actual="model_timeout",
        )
        return Rule077Execution(
            _decision(
                snapshot=snapshot,
                refs=refs,
                status="data_gap",
                reason_code="source_readiness_unproven",
                criterion=criterion,
            ),
            llm_call_count=1,
        )
    except Exception:
        criterion = _criterion(
            status=CriterionStatus.UNKNOWN,
            reason_code="model_transport_error",
            refs=refs,
            actual="model_transport_error",
        )
        return Rule077Execution(
            _decision(
                snapshot=snapshot,
                refs=refs,
                status="data_gap",
                reason_code="source_readiness_unproven",
                criterion=criterion,
            ),
            llm_call_count=1,
        )

    prompt_tokens, completion_tokens, total_tokens, api_time = _usage(response)
    payload = response_json_payload(response)
    state = clean_text(payload.get("relation_state")) if payload else ""
    rationale = clean_text(payload.get("rationale_code")) if payload else ""
    rationale_matches_state = {
        "related": "same_clinical_problem",
        "unrelated": "no_related_item",
        "unknown": "insufficient_information",
    }
    if (
        state not in _RELATION_STATES
        or rationale not in _RATIONALE_CODES
        or rationale != rationale_matches_state.get(state)
    ):
        criterion = _criterion(
            status=CriterionStatus.UNKNOWN,
            reason_code="model_invalid_output",
            refs=refs,
            actual="invalid_output",
        )
        decision = _decision(
            snapshot=snapshot,
            refs=refs,
            status="data_gap",
            reason_code="source_readiness_unproven",
            criterion=criterion,
        )
    else:
        status = {
            "related": "compliant",
            "unrelated": "non_compliant",
            "unknown": "data_gap",
        }[state]
        reason_code = {
            "related": "requirement_satisfied",
            "unrelated": "requirement_violated",
            "unknown": "source_readiness_unproven",
        }[state]
        criterion = _criterion(
            status={
                "related": CriterionStatus.PASSED,
                "unrelated": CriterionStatus.FAILED,
                "unknown": CriterionStatus.UNKNOWN,
            }[state],
            reason_code=rationale,
            refs=refs,
            actual=state,
        )
        decision = _decision(
            snapshot=snapshot,
            refs=refs,
            status=status,
            reason_code=reason_code,
            criterion=criterion,
        )
    return Rule077Execution(
        decision,
        llm_call_count=1,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        total_tokens=total_tokens,
        api_time=api_time,
    )
