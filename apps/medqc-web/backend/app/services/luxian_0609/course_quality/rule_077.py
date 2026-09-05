"""LX0609-077：首次病程鉴别诊断与第一诊断关联性。"""

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
from .rule_018 import _lx018_primary_diagnosis_resolution
from .shared import clean_text, response_json_payload


RULE_ID = "LX0609-077"
SOURCE_KEYS = (
    "first_course_record",
    "diagnosis",
    "admission_record_diagnosis",
)
_RELATION_STATES = frozenset({"related", "unrelated", "unknown"})
_DIFFERENTIAL_SECTION = re.compile(
    r"鉴别诊断\s*[:：]\s*(?P<body>.+?)(?=\n\s*(?:诊疗计划|治疗计划|诊治计划|医师签名)\s*[:：]|$)",
    re.DOTALL,
)
_FIRST_DIAGNOSIS_IN_BODY = re.compile(
    r"(?:第一诊断|初步诊断)\s*[:：]\s*(?:\d+[.、]?\s*)?(?P<diagnosis>[^；;，,。\n]{2,100})"
)
_MAX_DIFFERENTIAL_CHARS = 5000


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


def _first_diagnosis(
    rows: tuple[Mapping[str, Any], ...],
    diagnosis_documents: Mapping[str, list[Mapping[str, Any]]],
) -> str:
    for row in rows:
        value = clean_text(
            row.get("first_diagnosis")
            or row.get("primary_diagnosis")
            or row.get("initial_diagnosis")
        )
        if value:
            return value[:200]
        body_match = _FIRST_DIAGNOSIS_IN_BODY.search(_row_text(row))
        if body_match:
            return clean_text(body_match.group("diagnosis"))[:200]
    state, value = _lx018_primary_diagnosis_resolution(diagnosis_documents)
    return value[:200] if state == "available" else ""


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
        "uncertain": (
            ApplicabilityState.APPLICABLE,
            EvidenceState.CONFLICT,
            QcDirection.UNKNOWN,
            None,
        ),
        "technical_error": (
            ApplicabilityState.ERROR,
            EvidenceState.TECHNICAL_ERROR,
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


def _prompt(*, first_diagnosis: str, differential: str) -> str:
    return f"""你是病历质控中的鉴别诊断关联性核对器。

只判断首次病程记录中已经写出的鉴别诊断，是否围绕第一诊断的疾病系统、解剖部位或同一临床问题展开。不要判断诊断是否正确，不要补充病历中不存在的诊断。

第一诊断：{first_diagnosis}
鉴别诊断：{differential}

relation_state 只能是 related、unrelated、unknown：
- related：各项鉴别诊断与第一诊断存在合理临床关联；
- unrelated：至少一项明显无关且正文未解释关联；
- unknown：信息存在但无法可靠判断。

只输出 JSON：{{"relation_state":"related|unrelated|unknown","rationale_code":"same_clinical_problem|obvious_unrelated_item|insufficient_semantic_context"}}。"""


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
    course_refs = tuple(reference for reference, _row in first_course_pairs)
    diagnosis_documents = {
        key: [row for _reference, row in material_rows[key]]
        for key in ("diagnosis", "admission_record_diagnosis")
    }
    diagnosis_refs = tuple(
        reference
        for key in ("diagnosis", "admission_record_diagnosis")
        for reference, _row in material_rows[key]
    )
    refs = tuple(dict.fromkeys((*course_refs, *diagnosis_refs)))

    if not first_course_rows:
        return Rule077Execution(
            _decision(snapshot=snapshot, refs=(), status="data_gap", reason_code="required_field_missing")
        )
    first_diagnosis = _first_diagnosis(first_course_rows, diagnosis_documents)
    differential = next(
        (value for row in first_course_rows if (value := _differential_text(row))),
        "",
    )
    if not first_diagnosis or not differential:
        criterion = _criterion(
            status=CriterionStatus.UNKNOWN,
            reason_code="required_field_missing",
            refs=course_refs,
            actual="missing_required_input",
        )
        return Rule077Execution(
            _decision(
                snapshot=snapshot,
                refs=course_refs,
                status="data_gap",
                reason_code="required_field_missing",
                criterion=criterion,
            )
        )
    if llm_client is None:
        return Rule077Execution(
            _decision(
                snapshot=snapshot,
                refs=refs,
                status="technical_error",
                reason_code="model_transport_error",
            )
        )

    try:
        response = await llm_client.generate(
            _prompt(first_diagnosis=first_diagnosis, differential=differential),
            max_completion_tokens=180,
            allow_length_retry=False,
        )
    except TimeoutError:
        return Rule077Execution(
            _decision(snapshot=snapshot, refs=refs, status="technical_error", reason_code="model_timeout"),
            llm_call_count=1,
        )
    except Exception:
        return Rule077Execution(
            _decision(snapshot=snapshot, refs=refs, status="technical_error", reason_code="model_transport_error"),
            llm_call_count=1,
        )

    prompt_tokens, completion_tokens, total_tokens, api_time = _usage(response)
    payload = response_json_payload(response)
    state = clean_text(payload.get("relation_state")) if payload else ""
    rationale = clean_text(payload.get("rationale_code")) if payload else ""
    if state not in _RELATION_STATES or not re.fullmatch(r"[a-z][a-z0-9_]{1,63}", rationale):
        decision = _decision(
            snapshot=snapshot,
            refs=refs,
            status="technical_error",
            reason_code="model_invalid_output",
        )
    else:
        status = {
            "related": "compliant",
            "unrelated": "non_compliant",
            "unknown": "uncertain",
        }[state]
        reason_code = {
            "related": "requirement_satisfied",
            "unrelated": "requirement_violated",
            "unknown": "semantic_low_confidence",
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
