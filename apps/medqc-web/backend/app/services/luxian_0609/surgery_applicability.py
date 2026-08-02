"""LX0609 手术规则族共用的已实施手术适用性解析器。"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Mapping, Sequence

from .evidence_material import (
    EvidenceMaterialTruncated,
    EvidenceMaterialUnavailable,
    Luxian0609EvidenceMaterialStore,
)
from .evidence_snapshot import Luxian0609EvidenceSnapshot, SourceCompleteness
from .fact_schema import Assertion, EventStatus
from .source_evidence_reader import (
    has_qualified_traditional_surgery_row,
    has_trusted_performed_surgery,
)
from .source_manifest import QueryStatus
from .surgery_procedure_catalog import (
    SurgeryProcedureClassification,
    classify_surgery_row,
    effective_surgery_level,
)


@dataclass(frozen=True)
class SurgeryApplicability:
    state: str
    reason_code: str
    procedure_kind: str
    effective_level: str = ""
    level_source: str = ""
    evidence_refs: tuple[str, ...] = ()

    @property
    def is_performed_surgery(self) -> bool:
        return self.state == "applicable" and self.procedure_kind == "surgery"


def _rows(
    materials: Luxian0609EvidenceMaterialStore | None,
    source_key: str,
) -> tuple[Mapping[str, object], ...] | None:
    if materials is None:
        return None
    try:
        return tuple(materials.rows(source_key))
    except (EvidenceMaterialUnavailable, EvidenceMaterialTruncated):
        return None


def _best_classification(
    rows: Sequence[Mapping[str, object]],
) -> SurgeryProcedureClassification | None:
    matched = [item for row in rows if (item := classify_surgery_row(row)) is not None]
    if not matched:
        return None
    levels = {"一级": 1, "二级": 2, "三级": 3, "四级": 4}
    return max(
        matched,
        key=lambda item: (
            item.is_surgery,
            levels.get(item.effective_level, 0),
            item.source == "hospital_performance",
        ),
    )


def _performed_rows(
    *, source_key: str, rows: Sequence[Mapping[str, object]]
) -> tuple[Mapping[str, object], ...]:
    result: list[Mapping[str, object]] = []
    for row in rows:
        performed = has_trusted_performed_surgery(source_key=source_key, row=row)
        if source_key == "mr_surgery" and not performed:
            performed = any(
                isinstance(value, str)
                and bool(value.strip())
                and _is_iso_datetime(value)
                for value in (
                    row.get("surgery_begin_datetime"),
                    row.get("surgery_end_datetime"),
                )
            )
        if not performed:
            continue
        if source_key == "mr_surgery" and not has_qualified_traditional_surgery_row(row):
            continue
        if source_key == "surgery_record":
            classification = classify_surgery_row(row)
            if classification is not None and not classification.is_surgery:
                continue
        result.append(row)
    return tuple(result)


def _is_iso_datetime(value: str) -> bool:
    try:
        datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except ValueError:
        return False
    return True


def resolve_surgery_applicability(
    *,
    snapshot: Luxian0609EvidenceSnapshot,
    materials: Luxian0609EvidenceMaterialStore | None = None,
    source_keys: tuple[str, ...] = ("surgery_record", "mr_surgery"),
) -> SurgeryApplicability:
    """统一判断当前就诊是否存在已实施手术。

    肯定事实可以由一个可信来源独立证明；否定结论必须建立在来源完整且
    没有已实施手术的基础上。非手术操作即使有四级原始等级也不会触发。
    """

    if not isinstance(snapshot, Luxian0609EvidenceSnapshot):
        raise TypeError("snapshot must be Luxian0609EvidenceSnapshot")
    if materials is not None and materials.snapshot_hash != snapshot.snapshot_hash:
        raise ValueError("surgery applicability requires one evidence session")

    if (
        not source_keys
        or len(source_keys) != len(set(source_keys))
        or not set(source_keys).issubset({"surgery_record", "mr_surgery"})
    ):
        raise ValueError("unsupported surgery applicability source scope")
    observations = {
        item.source_key: item
        for item in snapshot.observations
        if item.source_key in source_keys
    }
    refs = tuple(
        sorted(item.snapshot_ref.removeprefix("sha256:") for item in observations.values())
    )
    rows_by_source = {key: _rows(materials, key) for key in source_keys}

    performed_rows: list[Mapping[str, object]] = []
    for source_key, rows in rows_by_source.items():
        if rows is not None:
            performed_rows.extend(_performed_rows(source_key=source_key, rows=rows))

    performed_facts = tuple(
        fact
        for fact in snapshot.facts
        if fact.fact_type == "current_visit_surgery_confirmed"
        and fact.assertion is Assertion.AFFIRMED
        and fact.event_status is EventStatus.PERFORMED
        and fact.source_key in source_keys
        and (
            fact.source_key != "mr_surgery"
            or bool(
                _performed_rows(
                    source_key="mr_surgery",
                    rows=rows_by_source.get("mr_surgery") or (),
                )
            )
        )
    )
    if performed_rows or performed_facts:
        classification = _best_classification(performed_rows)
        fallback_level = max(
            (effective_surgery_level(row) for row in performed_rows),
            key=lambda value: {"一级": 1, "二级": 2, "三级": 3, "四级": 4}.get(
                value, 0
            ),
            default="",
        )
        return SurgeryApplicability(
            state="applicable",
            reason_code="performed_surgery_confirmed",
            procedure_kind="surgery",
            effective_level=(
                classification.effective_level if classification else fallback_level
            ),
            level_source=(
                classification.source
                if classification
                else "structured_field"
                if fallback_level
                else ""
            ),
            evidence_refs=tuple(sorted({*refs, *(fact.fact_id for fact in performed_facts)})),
        )

    if any(item.query_state is QueryStatus.ERROR for item in observations.values()):
        return SurgeryApplicability(
            "technical_error", "source_query_error", "unknown", evidence_refs=refs
        )
    if set(observations) != set(source_keys):
        return SurgeryApplicability(
            "data_gap", "applicability_source_gap", "unknown", evidence_refs=refs
        )
    if any(
        item.query_state is QueryStatus.UNAVAILABLE
        or item.completeness is SourceCompleteness.UNPROVEN
        for item in observations.values()
    ):
        return SurgeryApplicability(
            "data_gap", "source_unavailable", "unknown", evidence_refs=refs
        )
    if any(item.completeness is SourceCompleteness.TRUNCATED for item in observations.values()):
        return SurgeryApplicability(
            "data_gap", "source_truncated", "unknown", evidence_refs=refs
        )

    all_rows = tuple(row for rows in rows_by_source.values() for row in (rows or ()))
    surgery_record_rows = rows_by_source.get("surgery_record", ())
    mr_surgery_rows = rows_by_source.get("mr_surgery", ())
    if (
        surgery_record_rows == ()
        and mr_surgery_rows
        and not any(has_qualified_traditional_surgery_row(row) for row in mr_surgery_rows)
    ):
        return SurgeryApplicability(
            "not_applicable",
            "performed_event_absent",
            "non_surgical_operation",
            evidence_refs=refs,
        )
    classifications = tuple(
        item for row in all_rows if (item := classify_surgery_row(row)) is not None
    )
    if classifications and all(not item.is_surgery for item in classifications):
        return SurgeryApplicability(
            "not_applicable",
            "performed_event_absent",
            "non_surgical_operation",
            evidence_refs=refs,
        )
    if all(item.query_state is QueryStatus.EMPTY for item in observations.values()):
        return SurgeryApplicability(
            "not_applicable", "performed_event_absent", "none", evidence_refs=refs
        )
    if all(rows is not None for rows in rows_by_source.values()) and not all_rows:
        return SurgeryApplicability(
            "not_applicable", "performed_event_absent", "none", evidence_refs=refs
        )
    return SurgeryApplicability(
        "data_gap", "authoritative_time_missing", "unknown", evidence_refs=refs
    )


__all__ = ["SurgeryApplicability", "resolve_surgery_applicability"]
