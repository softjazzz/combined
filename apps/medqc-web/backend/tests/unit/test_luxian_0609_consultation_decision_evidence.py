from __future__ import annotations

from dataclasses import dataclass

import pytest

from app.services.luxian_0609.consultation_decision_evidence import (
    material_refs_for_internal_refs,
    select_consultation_rule_material_refs,
)


@dataclass(frozen=True)
class _Episode:
    episode_ref: str
    application_state: str = "clear"
    opinion_state: str = "clear"
    confidence: str = "high"
    application_refs: tuple[str, ...] = ()
    opinion_refs: tuple[str, ...] = ()


@dataclass(frozen=True)
class _Recommendation:
    recommendation_ref: str


@dataclass(frozen=True)
class _CompletedRecommendation:
    episode_ref: str
    recommendation: _Recommendation


@dataclass(frozen=True)
class _Assessment:
    recommendation_ref: str
    execution_record_state: str
    trace_refs: tuple[str, ...]
    execution_refs: tuple[str, ...] = ()


@dataclass(frozen=True)
class _Candidate:
    ref: str
    material_ref: str


def test_material_binding_rejects_partially_mapped_decisive_references() -> None:
    with pytest.raises(ValueError, match="cannot be uniquely bound"):
        material_refs_for_internal_refs(
            documents=(
                {"ref": "consultation_record-1", "material_ref": "material-1"},
            ),
            candidates=(),
            internal_refs=("consultation_record-1", "missing-reference"),
        )


def test_material_binding_rejects_tampered_missing_material_reference() -> None:
    with pytest.raises(ValueError, match="cannot be uniquely bound"):
        material_refs_for_internal_refs(
            documents=(
                {"ref": "consultation_record-1", "material_ref": ""},
            ),
            candidates=(),
            internal_refs=("consultation_record-1",),
        )


def test_material_binding_rejects_cross_source_reference_collision() -> None:
    with pytest.raises(ValueError, match="cannot be uniquely bound"):
        material_refs_for_internal_refs(
            documents=(
                {"ref": "shared-reference", "material_ref": "consultation-material"},
            ),
            candidates=(
                _Candidate(
                    ref="shared-reference",
                    material_ref="course-material",
                ),
            ),
            internal_refs=("shared-reference",),
        )


def test_023_prioritizes_late_offending_episode_before_eight_item_limit() -> None:
    episodes = tuple(
        _Episode(
            episode_ref=f"consultation_record-{index}",
            application_refs=(f"consultation_record-{index}",),
            opinion_refs=(f"consultation_record-{index}",),
        )
        for index in range(1, 10)
    )
    completed = tuple(
        _CompletedRecommendation(
            episode_ref=item.episode_ref,
            recommendation=_Recommendation(f"{item.episode_ref}#r1"),
        )
        for item in episodes
    )
    assessments = tuple(
        _Assessment(
            recommendation_ref=item.recommendation.recommendation_ref,
            execution_record_state=(
                "generic_trace" if index == 9 else "specific_trace"
            ),
            trace_refs=(f"daily_course_record-{index}",),
        )
        for index, item in enumerate(completed, start=1)
    )
    documents = tuple(
        {
            "ref": f"consultation_record-{index}",
            "material_ref": f"consultation-material-{index}",
        }
        for index in range(1, 10)
    )
    candidates = tuple(
        _Candidate(
            ref=f"daily_course_record-{index}",
            material_ref=f"course-material-{index}",
        )
        for index in range(1, 10)
    )

    refs = select_consultation_rule_material_refs(
        rule_id="LX0609-023",
        status="non_compliant",
        reason_code="requirement_violated",
        documents=documents,
        episodes=episodes,
        completed_recommendations=completed,
        assessments=assessments,
        candidates=candidates,
    )

    assert refs[:2] == ("consultation-material-9", "course-material-9")
    assert len(refs) == 8
