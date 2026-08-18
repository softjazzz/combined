"""LX0609 规则决策的结构化中间契约。

执行器只能提交适用性、证据状态和质控方向；客户最终状态由统一 reducer
生成，禁止根据结论文案、建议或证据正文反推状态。
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import hashlib
import json
import math
import re
from types import MappingProxyType
from typing import Any


_RULE_ID_PATTERN = re.compile(r"^LX0609-(?:00[1-9]|0[1-6][0-9]|07[0-5])$")
_SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")
_REASON_CODE_PATTERN = re.compile(r"^[a-z][a-z0-9_]{0,63}$")
_VERSION_PATTERN = re.compile(r"^[a-z0-9][a-z0-9._-]{0,63}$")
_MAX_FACT_REFS = 128
_FORBIDDEN_COMPACT_VERSION_MARKERS = (
    "rawtext",
    "medicaltext",
    "recordcontent",
    "patientname",
    "visitid",
    "sourcedocumentid",
    "prompt",
    "response",
    "sql",
    "credential",
    "bearer",
    "apikey",
    "phone",
    "mobile",
    "address",
    "password",
    "email",
    "name",
    "idcard",
    "idnumber",
    "authorization",
    "privatekey",
    "secret",
    "token",
    "certificate",
)


class ApplicabilityState(str, Enum):
    """规则对当前就诊是否适用。"""

    APPLICABLE = "applicable"
    NOT_APPLICABLE = "not_applicable"
    UNKNOWN = "unknown"
    ERROR = "error"


class EvidenceState(str, Enum):
    """作出质控方向所需证据的完备状态。"""

    SUFFICIENT = "sufficient"
    DATA_GAP = "data_gap"
    CONFLICT = "conflict"
    TECHNICAL_ERROR = "technical_error"


class QcDirection(str, Enum):
    """证据充分时的质控方向，不是客户最终状态。"""

    SATISFIED = "satisfied"
    DEFECT = "defect"
    UNKNOWN = "unknown"


ALLOWED_REASON_CODES_BY_FINAL_STATE = MappingProxyType({
    "compliant": frozenset(
        {
            "requirement_satisfied",
            "requirement_within_threshold",
        }
    ),
    "non_compliant": frozenset(
        {
            "requirement_violated",
            "required_document_missing",
            "threshold_exceeded",
            "defect_proven",
        }
    ),
    "not_applicable": frozenset(
        {
            "trigger_absent_complete",
            "eligibility_not_met",
            "performed_event_absent",
        }
    ),
    "data_gap": frozenset(
        {
            "source_unavailable",
            "source_empty",
            "source_truncated",
            "source_readiness_unproven",
            "required_field_missing",
            "target_report_missing",
            "authoritative_time_missing",
            "authoritative_report_time_missing",
            "authoritative_time_conflict",
            "evaluation_window_not_mature",
            "positive_assertion_not_explicit",
            "association_failed",
            "linkage_unresolved",
            "applicability_source_gap",
            "candidate_scope_incomplete",
        }
    ),
    "evaluation_unknown": frozenset(
        {
            "evidence_conflict",
            "semantic_low_confidence",
            "semantic_output_unknown",
            "candidate_scope_incomplete",
            "applicability_conflict",
        }
    ),
    "technical_error": frozenset(
        {
            "source_query_error",
            "model_transport_error",
            "model_timeout",
            "model_parse_error",
            "model_invalid_output",
            "executor_timeout",
            "executor_exception",
            "snapshot_mismatch",
            "decision_contract_violation",
            "applicability_evaluator_error",
            "family_result_invalid",
            "family_result_missing",
            "family_result_duplicate",
            "family_result_extra",
            "family_result_order_mismatch",
            "family_result_scope_mismatch",
        }
    ),
})
_ALL_ALLOWED_REASON_CODES = frozenset().union(
    *ALLOWED_REASON_CODES_BY_FINAL_STATE.values()
)


def _require_enum(value: Any, enum_type: type[Enum], field_name: str) -> None:
    if not isinstance(value, enum_type):
        raise TypeError(f"{field_name} must use its enum type")


def _has_forbidden_version_marker(value: str) -> bool:
    compact = re.sub(r"[^a-z0-9]", "", value)
    return any(marker in compact for marker in _FORBIDDEN_COMPACT_VERSION_MARKERS)


class CriterionStatus(str, Enum):
    PASSED = "passed"
    FAILED = "failed"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class CriterionResult:
    """单个规则子项的受控结果；不参与 reducer 的六态推导。"""

    criterion_id: str
    status: CriterionStatus
    reason_code: str
    fact_refs: tuple[str, ...] = ()
    actual_value: int | str | bool | None = None
    expected_value: int | str | bool | None = None
    operator: str = ""
    unit: str = ""
    rationale_code: str = ""
    dimensions: tuple[str, ...] = ()
    medical_analysis: str = ""

    def __post_init__(self) -> None:
        if not re.fullmatch(r"^[a-z][a-z0-9_]{1,63}$", self.criterion_id):
            raise ValueError("invalid criterion_id")
        _require_enum(self.status, CriterionStatus, "criterion status")
        if not isinstance(self.reason_code, str) or not _REASON_CODE_PATTERN.fullmatch(
            self.reason_code
        ):
            raise ValueError("invalid criterion reason_code")
        if (
            not isinstance(self.fact_refs, tuple)
            or len(self.fact_refs) > _MAX_FACT_REFS
            or len(self.fact_refs) != len(set(self.fact_refs))
            or any(
                not isinstance(ref, str) or not _SHA256_PATTERN.fullmatch(ref)
                for ref in self.fact_refs
            )
        ):
            raise ValueError("invalid criterion fact_refs")
        object.__setattr__(self, "fact_refs", tuple(sorted(self.fact_refs)))
        for value in (self.actual_value, self.expected_value):
            if value is not None and (
                not isinstance(value, (int, str, bool))
                or isinstance(value, str) and len(value) > 120
            ):
                raise ValueError("invalid criterion scalar value")
        for value, field_name in (
            (self.operator, "operator"),
            (self.unit, "unit"),
            (self.rationale_code, "rationale_code"),
        ):
            if value and not re.fullmatch(r"^[a-z][a-z0-9_]{0,63}$", value):
                raise ValueError(f"invalid criterion {field_name}")
        if (
            not isinstance(self.dimensions, tuple)
            or len(self.dimensions) != len(set(self.dimensions))
            or any(
                not isinstance(value, str)
                or not re.fullmatch(r"^[a-z][a-z0-9_]{0,63}$", value)
                for value in self.dimensions
            )
        ):
            raise ValueError("invalid criterion dimensions")
        if (
            not isinstance(self.medical_analysis, str)
            or len(self.medical_analysis) > 2000
            or "\x00" in self.medical_analysis
        ):
            raise ValueError("invalid criterion medical_analysis")

    def to_safe_dict(self) -> dict[str, Any]:
        return {
            "criterion_id": self.criterion_id,
            "status": self.status.value,
            "reason_code": self.reason_code,
            "fact_refs": list(self.fact_refs),
            "actual_value": self.actual_value,
            "expected_value": self.expected_value,
            "operator": self.operator,
            "unit": self.unit,
            "rationale_code": self.rationale_code,
            "dimensions": list(self.dimensions),
            "medical_analysis": self.medical_analysis,
        }


@dataclass(frozen=True)
class RuleDecision:
    """一个规则执行器提交给统一 reducer 的安全决策。"""

    rule_id: str
    snapshot_hash: str
    applicability: ApplicabilityState
    evidence_state: EvidenceState
    qc_direction: QcDirection
    reason_code: str
    fact_refs: tuple[str, ...]
    evaluator_version: str
    confidence: float | None = None
    criterion_results: tuple[CriterionResult, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.rule_id, str) or not _RULE_ID_PATTERN.fullmatch(
            self.rule_id
        ):
            raise ValueError("invalid rule_id")
        if not isinstance(self.snapshot_hash, str) or not _SHA256_PATTERN.fullmatch(
            self.snapshot_hash
        ):
            raise ValueError("invalid snapshot_hash")
        _require_enum(self.applicability, ApplicabilityState, "applicability")
        _require_enum(self.evidence_state, EvidenceState, "evidence_state")
        _require_enum(self.qc_direction, QcDirection, "qc_direction")
        self._validate_dimensions()
        if not isinstance(self.reason_code, str) or not _REASON_CODE_PATTERN.fullmatch(
            self.reason_code
        ):
            raise ValueError("invalid reason_code")
        if (
            not isinstance(self.fact_refs, tuple)
            or len(self.fact_refs) > _MAX_FACT_REFS
            or len(self.fact_refs) != len(set(self.fact_refs))
            or any(
                not isinstance(ref, str) or not _SHA256_PATTERN.fullmatch(ref)
                for ref in self.fact_refs
            )
        ):
            raise ValueError("invalid fact_refs")
        object.__setattr__(self, "fact_refs", tuple(sorted(self.fact_refs)))
        if not isinstance(
            self.evaluator_version, str
        ) or not _VERSION_PATTERN.fullmatch(
            self.evaluator_version
        ) or _has_forbidden_version_marker(self.evaluator_version):
            raise ValueError("invalid evaluator_version")
        if self.confidence is not None:
            if (
                isinstance(self.confidence, bool)
                or not isinstance(self.confidence, (int, float))
                or not math.isfinite(self.confidence)
                or not 0 <= self.confidence <= 1
            ):
                raise ValueError("invalid confidence")
            object.__setattr__(self, "confidence", float(self.confidence))
        if self.reason_code not in _ALL_ALLOWED_REASON_CODES:
            raise ValueError("invalid reason_code")
        if (
            not isinstance(self.criterion_results, tuple)
            or len({item.criterion_id for item in self.criterion_results})
            != len(self.criterion_results)
            or any(
                not isinstance(item, CriterionResult)
                or not set(item.fact_refs).issubset(self.fact_refs)
                for item in self.criterion_results
            )
        ):
            raise ValueError("invalid criterion_results")

    def _validate_dimensions(self) -> None:
        applicability = self.applicability
        evidence = self.evidence_state
        direction = self.qc_direction

        if applicability is ApplicabilityState.NOT_APPLICABLE:
            valid = (
                evidence is EvidenceState.SUFFICIENT
                and direction is QcDirection.UNKNOWN
            )
        elif applicability is ApplicabilityState.ERROR:
            valid = (
                evidence is EvidenceState.TECHNICAL_ERROR
                and direction is QcDirection.UNKNOWN
            )
        elif applicability is ApplicabilityState.UNKNOWN:
            valid = (
                evidence
                in {
                    EvidenceState.DATA_GAP,
                    EvidenceState.CONFLICT,
                    EvidenceState.TECHNICAL_ERROR,
                }
                and direction is QcDirection.UNKNOWN
            )
        elif evidence is EvidenceState.SUFFICIENT:
            valid = direction in {
                QcDirection.SATISFIED,
                QcDirection.DEFECT,
                QcDirection.UNKNOWN,
            }
        else:
            valid = direction is QcDirection.UNKNOWN

        if not valid:
            raise ValueError("invalid decision dimensions")

    def to_safe_dict(self) -> dict[str, Any]:
        return {
            "rule_id": self.rule_id,
            "snapshot_hash": self.snapshot_hash,
            "applicability": self.applicability.value,
            "evidence_state": self.evidence_state.value,
            "qc_direction": self.qc_direction.value,
            "reason_code": self.reason_code,
            "fact_refs": list(self.fact_refs),
            "evaluator_version": self.evaluator_version,
            "confidence": self.confidence,
            "criterion_results": [
                item.to_safe_dict() for item in self.criterion_results
            ],
        }

    def canonical_json(self) -> str:
        return json.dumps(
            self.to_safe_dict(),
            ensure_ascii=True,
            sort_keys=True,
            separators=(",", ":"),
        )

    def fingerprint(self) -> str:
        return hashlib.sha256(self.canonical_json().encode("utf-8")).hexdigest()
