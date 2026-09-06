from __future__ import annotations

from datetime import datetime
from typing import Any

import pytest

from app.services.luxian_0609.decision_binding import (
    bind_and_reduce_luxian_0609_rule_decisions,
)
from app.services.luxian_0609.evidence_snapshot_provider import (
    SnapshotSourceRows,
    SourceEvidenceQueryError,
    SourceEvidenceUnavailable,
    build_luxian_0609_evidence_read_session,
)
from app.services.luxian_0609.native_transfusion_execution import (
    execute_luxian_0609_native_transfusion_rules,
)


def _session(
    *,
    bloodtrans_rows: list[dict[str, Any]],
    daily_rows: list[dict[str, Any]],
    horizon_date: str,
    daily_source_error: bool = False,
    daily_source_unavailable: bool = False,
):
    def reader(**kwargs: Any) -> SnapshotSourceRows:
        source_key = str(kwargs["source_key"])
        if source_key == "daily_course_record" and daily_source_unavailable:
            raise SourceEvidenceUnavailable("episode daily source unavailable")
        if source_key == "daily_course_record" and daily_source_error:
            raise SourceEvidenceQueryError("episode daily query failure")
        rows = {
            "mr_bloodtrans": [
                {"transfution_datetime": datetime(2026, 1, 1, 10, 0)}
            ],
            "bloodtrans_record": bloodtrans_rows,
            "daily_course_record": daily_rows,
        }
        return SnapshotSourceRows.create(
            source_key=source_key,
            rows=rows.get(source_key, []),
            truncated=False,
            limit_rows=50,
        )

    return build_luxian_0609_evidence_read_session(
        selected_rule_ids=("LX0609-047",),
        institute_id="I",
        patient_id="P",
        visit_id="V",
        source_schema=None,
        created_at="2026-01-05T08:00:00+08:00",
        evaluation_as_of_date=horizon_date,
        evaluation_horizon_policy="frozen_task_date",
        row_reader=reader,
    )


async def _evaluate(*, session: Any):
    execution = await execute_luxian_0609_native_transfusion_rules(
        rule_ids=("LX0609-047",),
        wrapper_rules=[],
        evidence_payload=None,
        institute_id="I",
        patient_id="P",
        visit_id="V",
        source_schema=None,
        llm_client=None,
        evidence_snapshot=session.snapshot,
        evidence_materials=session.materials,
        decision_rule_ids=("LX0609-047",),
    )
    canonical = bind_and_reduce_luxian_0609_rule_decisions(
        decisions=execution.decisions,
        expected_rule_ids=("LX0609-047",),
        snapshot=session.snapshot,
        evidence_materials=session.materials,
    )[0]
    return execution, canonical


def _selected_document_refs(session: Any, source_key: str, document_ids: set[str]) -> set[str]:
    return {
        reference
        for reference, row in session.materials.document_rows(
            source_key, snapshot=session.snapshot
        )
        if str(row.get("document_id") or row.get("id") or "") in document_ids
    }


@pytest.mark.asyncio
async def test_047_two_nonoverlapping_episodes_bind_their_own_daily_evaluations():
    session = _session(
        bloodtrans_rows=[
            {"document_id": "BT-1", "record_content": "2026-01-01 10:00:00输血结束。"},
            {"document_id": "BT-2", "record_content": "2026-01-02 16:00:00输血结束。"},
        ],
        daily_rows=[
            {"document_id": "DC-1", "record_time": "2026-01-01 11:00:00", "record_content": "2026-01-01 10:00:00输血结束后复查血红蛋白改善。"},
            {"document_id": "DC-2", "record_time": "2026-01-02 17:00:00", "record_content": "2026-01-02 16:00:00输血结束后复查血红蛋白改善。"},
        ],
        horizon_date="2026-01-04",
    )

    execution, canonical = await _evaluate(session=session)

    assert (canonical.final_state.value, canonical.reason_code) == (
        "compliant",
        "requirement_satisfied",
    )
    assert execution.llm_call_count == 0
    refs = dict(execution.customer_display_facts)["LX0609-047"]["source_document_refs"]
    assert {item["source_document_id"] for item in refs} == {
        "BT-1", "BT-2", "DC-1", "DC-2",
    }


@pytest.mark.asyncio
async def test_047_multi_episode_material_order_does_not_change_selected_coordinates():
    bloodtrans_rows = [
        {"document_id": "BT-1", "record_content": "2026-01-01 10:00:00输血结束。"},
        {"document_id": "BT-2", "record_content": "2026-01-02 16:00:00输血结束。"},
    ]
    daily_rows = [
        {"document_id": "DC-1", "record_time": "2026-01-01 11:00:00", "record_content": "2026-01-01 10:00:00输血结束后复查血红蛋白改善。"},
        {"document_id": "DC-2", "record_time": "2026-01-02 17:00:00", "record_content": "2026-01-02 16:00:00输血结束后复查血红蛋白改善。"},
    ]
    original = _session(
        bloodtrans_rows=bloodtrans_rows,
        daily_rows=daily_rows,
        horizon_date="2026-01-04",
    )
    permuted = _session(
        bloodtrans_rows=list(reversed(bloodtrans_rows)),
        daily_rows=list(reversed(daily_rows)),
        horizon_date="2026-01-04",
    )

    original_execution, original_canonical = await _evaluate(session=original)
    permuted_execution, permuted_canonical = await _evaluate(session=permuted)

    assert (
        original_canonical.final_state.value,
        original_canonical.reason_code,
    ) == (
        permuted_canonical.final_state.value,
        permuted_canonical.reason_code,
    ) == ("compliant", "requirement_satisfied")
    original_facts = dict(original_execution.customer_display_facts)["LX0609-047"]
    permuted_facts = dict(permuted_execution.customer_display_facts)["LX0609-047"]
    assert {
        key: original_facts[key]
        for key in ("transfusion_end_time", "evaluation_time", "elapsed_hours")
    } == {
        key: permuted_facts[key]
        for key in ("transfusion_end_time", "evaluation_time", "elapsed_hours")
    } == {
        "transfusion_end_time": "2026-01-02 16:00:00",
        "evaluation_time": "2026-01-02 17:00:00",
        "elapsed_hours": 1.0,
    }
    expected_original_refs = _selected_document_refs(
        original, "bloodtrans_record", {"BT-1", "BT-2"}
    ).union(_selected_document_refs(original, "daily_course_record", {"DC-1", "DC-2"}))
    expected_permuted_refs = _selected_document_refs(
        permuted, "bloodtrans_record", {"BT-1", "BT-2"}
    ).union(_selected_document_refs(permuted, "daily_course_record", {"DC-1", "DC-2"}))
    assert expected_original_refs.issubset(set(original_execution.decisions[0].fact_refs))
    assert expected_permuted_refs.issubset(set(permuted_execution.decisions[0].fact_refs))


@pytest.mark.asyncio
async def test_047_same_time_daily_tie_breaks_by_document_identity_not_input_order():
    bloodtrans_rows = [
        {"document_id": "BT-1", "record_content": "2026-01-01 10:00:00输血结束。"},
        {"document_id": "BT-2", "record_content": "2026-01-02 16:00:00输血结束。"},
    ]
    daily_rows = [
        {"document_id": "DC-1", "record_time": "2026-01-01 11:00:00", "record_content": "2026-01-01 10:00:00输血结束后复查血红蛋白改善。"},
        {"document_id": "DC-Z", "record_time": "2026-01-02 17:00:00", "record_content": "2026-01-02 16:00:00输血结束后复查血红蛋白改善。"},
        {"document_id": "DC-A", "record_time": "2026-01-02 17:00:00", "record_content": "2026-01-02 16:00:00输血结束后复查血红蛋白改善。"},
    ]
    original = _session(
        bloodtrans_rows=bloodtrans_rows,
        daily_rows=daily_rows,
        horizon_date="2026-01-04",
    )
    permuted = _session(
        bloodtrans_rows=list(reversed(bloodtrans_rows)),
        daily_rows=list(reversed(daily_rows)),
        horizon_date="2026-01-04",
    )

    original_execution, original_canonical = await _evaluate(session=original)
    permuted_execution, permuted_canonical = await _evaluate(session=permuted)

    assert (
        original_canonical.final_state.value,
        original_canonical.reason_code,
    ) == (
        permuted_canonical.final_state.value,
        permuted_canonical.reason_code,
    ) == ("compliant", "requirement_satisfied")
    for execution in (original_execution, permuted_execution):
        refs = dict(execution.customer_display_facts)["LX0609-047"][
            "source_document_refs"
        ]
        assert {item["source_document_id"] for item in refs} == {
            "BT-1",
            "BT-2",
            "DC-1",
            "DC-A",
        }
    assert set(original_execution.decisions[0].fact_refs) == set(
        permuted_execution.decisions[0].fact_refs
    )


@pytest.mark.asyncio
async def test_047_multi_episode_daily_source_error_is_technical_without_clinical_facts():
    session = _session(
        bloodtrans_rows=[
            {"document_id": "BT-1", "record_content": "2026-01-01 10:00:00输血结束。"},
            {"document_id": "BT-2", "record_content": "2026-01-02 16:00:00输血结束。"},
        ],
        daily_rows=[],
        horizon_date="2026-01-04",
        daily_source_error=True,
    )

    execution, canonical = await _evaluate(session=session)

    assert (canonical.final_state.value, canonical.reason_code) == (
        "technical_error",
        "source_query_error",
    )
    assert execution.customer_display_facts == ()
    assert execution.llm_call_count == 0


@pytest.mark.asyncio
async def test_047_multi_episode_daily_source_unavailable_is_a_data_gap():
    session = _session(
        bloodtrans_rows=[
            {"document_id": "BT-1", "record_content": "2026-01-01 10:00:00输血结束。"},
            {"document_id": "BT-2", "record_content": "2026-01-02 16:00:00输血结束。"},
        ],
        daily_rows=[],
        horizon_date="2026-01-04",
        daily_source_unavailable=True,
    )

    execution, canonical = await _evaluate(session=session)

    assert (canonical.final_state.value, canonical.reason_code) == (
        "data_gap",
        "source_unavailable",
    )
    assert execution.customer_display_facts == ()
    assert execution.llm_call_count == 0


@pytest.mark.asyncio
async def test_047_pre_end_daily_anchor_is_a_time_gap_not_a_late_evaluation():
    session = _session(
        bloodtrans_rows=[
            {"document_id": "BT-1", "record_content": "2026-01-01 10:00:00输血结束。"},
            {"document_id": "BT-2", "record_content": "2026-01-02 16:00:00输血结束。"},
        ],
        daily_rows=[
            {"document_id": "DC-EARLY", "record_time": "2026-01-01 09:00:00", "record_content": "2026-01-01 10:00:00输血结束后复查血红蛋白改善。"},
        ],
        horizon_date="2026-01-04",
    )

    execution, canonical = await _evaluate(session=session)

    assert (canonical.final_state.value, canonical.reason_code) == (
        "data_gap",
        "authoritative_time_missing",
    )
    assert execution.llm_call_count == 0


@pytest.mark.asyncio
async def test_047_unresolved_end_marker_makes_an_explicit_anchor_unreliable():
    session = _session(
        bloodtrans_rows=[
            {"document_id": "BT-1", "record_content": "2026-01-01 10:00:00输血结束。"},
            {"document_id": "BT-2", "record_content": "2026-01-01 16:00:00输血结束。"},
        ],
        daily_rows=[
            {"document_id": "DC-MIXED", "record_time": "2026-01-01 11:00:00", "record_content": "2026-01-01 10:00:00输血结束；另一次输血结束，复查血红蛋白改善。"},
        ],
        horizon_date="2026-01-03",
    )

    _execution, canonical = await _evaluate(session=session)

    assert (canonical.final_state.value, canonical.reason_code) == (
        "data_gap",
        "association_failed",
    )


@pytest.mark.asyncio
async def test_047_unresolved_end_marker_can_still_refer_to_an_unmet_episode():
    session = _session(
        bloodtrans_rows=[
            {
                "document_id": "BT-1",
                "record_time": "2026-01-01 11:00:00",
                "record_content": "2026-01-01 10:00:00输血结束；输血后复查血红蛋白改善。",
            },
            {"document_id": "BT-2", "record_content": "2026-01-01 16:00:00输血结束。"},
        ],
        daily_rows=[
            {"document_id": "DC-MIXED", "record_time": "2026-01-01 11:00:00", "record_content": "2026-01-01 10:00:00输血结束；另一次输血结束，复查血红蛋白改善。"},
        ],
        horizon_date="2026-01-03",
    )

    _execution, canonical = await _evaluate(session=session)

    assert (canonical.final_state.value, canonical.reason_code) == (
        "data_gap",
        "association_failed",
    )


@pytest.mark.asyncio
async def test_047_multiple_explicit_end_anchors_cannot_be_time_window_filtered_to_one_episode():
    session = _session(
        bloodtrans_rows=[
            {"document_id": "BT-1", "record_content": "2026-01-01 10:00:00输血结束。"},
            {"document_id": "BT-2", "record_content": "2026-01-01 16:00:00输血结束。"},
        ],
        daily_rows=[
            {"document_id": "DC-MULTI", "record_time": "2026-01-01 17:00:00", "record_content": "2026-01-01 10:00:00输血结束；2026-01-01 16:00:00输血结束后复查血红蛋白改善。"},
        ],
        horizon_date="2026-01-03",
    )

    _execution, canonical = await _evaluate(session=session)

    assert (canonical.final_state.value, canonical.reason_code) == (
        "data_gap",
        "association_failed",
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "future_content",
    (
        "2026-01-01 10:00:00输血结束；另一次输血结束，复查血红蛋白改善。",
        "2026-01-01 10:00:00输血结束；2026-01-01 16:00:00输血结束后复查血红蛋白改善。",
    ),
)
async def test_047_future_daily_anchor_ambiguity_does_not_override_frozen_deadline(
    future_content: str,
):
    session = _session(
        bloodtrans_rows=[
            {"document_id": "BT-1", "record_content": "2026-01-01 10:00:00输血结束。"},
            {"document_id": "BT-2", "record_content": "2026-01-01 16:00:00输血结束。"},
        ],
        daily_rows=[
            {
                "document_id": "DC-FUTURE",
                "record_time": "2026-01-04 09:00:00",
                "record_content": future_content,
            },
        ],
        horizon_date="2026-01-03",
    )

    execution, canonical = await _evaluate(session=session)

    assert (canonical.final_state.value, canonical.reason_code) == (
        "non_compliant",
        "requirement_violated",
    )
    assert execution.llm_call_count == 0


@pytest.mark.asyncio
async def test_047_unusable_daily_does_not_preempt_later_unique_episodes():
    session = _session(
        bloodtrans_rows=[
            {"document_id": "BT-1", "record_content": "2026-01-01 10:00:00输血结束。"},
            {"document_id": "BT-2", "record_content": "2026-01-02 16:00:00输血结束。"},
        ],
        daily_rows=[
            {"document_id": "DC-UNUSABLE", "record_content": "输血后复查血红蛋白改善。"},
            {"document_id": "DC-1", "record_time": "2026-01-01 11:00:00", "record_content": "2026-01-01 10:00:00输血结束后复查血红蛋白改善。"},
            {"document_id": "DC-2", "record_time": "2026-01-02 17:00:00", "record_content": "2026-01-02 16:00:00输血结束后复查血红蛋白改善。"},
        ],
        horizon_date="2026-01-04",
    )

    execution, canonical = await _evaluate(session=session)

    assert (canonical.final_state.value, canonical.reason_code) == (
        "compliant",
        "requirement_satisfied",
    )
    assert execution.llm_call_count == 0


@pytest.mark.asyncio
async def test_047_timely_daily_can_supersede_late_same_record_evaluation():
    session = _session(
        bloodtrans_rows=[
            {"document_id": "BT-1", "record_content": "2026-01-01 10:00:00输血结束。"},
            {"document_id": "BT-2", "record_time": "2026-01-02 18:00:00", "record_content": "2026-01-01 16:00:00输血结束；输血后复查血红蛋白改善。"},
        ],
        daily_rows=[
            {"document_id": "DC-1", "record_time": "2026-01-01 11:00:00", "record_content": "2026-01-01 10:00:00输血结束后复查血红蛋白改善。"},
            {"document_id": "DC-2", "record_time": "2026-01-01 17:00:00", "record_content": "2026-01-01 16:00:00输血结束后复查血红蛋白改善。"},
        ],
        horizon_date="2026-01-03",
    )

    execution, canonical = await _evaluate(session=session)

    assert (canonical.final_state.value, canonical.reason_code) == (
        "compliant",
        "requirement_satisfied",
    )
    assert execution.llm_call_count == 0


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "bloodtrans_rows",
    (
        [
            {"document_id": "BT-1", "record_content": "2026-01-01 10:00:00输血结束。"},
            {"document_id": "BT-2", "record_content": "2026-01-01 16:00:00输血结束。"},
        ],
        [
            {"document_id": "BT-1", "record_content": "2026-01-01 10:00:00输血结束。"},
            {"document_id": "BT-2", "record_content": "2026-01-01 10:00:00输血结束。"},
        ],
    ),
)
async def test_047_ambiguous_daily_evaluation_never_fans_out_to_multiple_episodes(
    bloodtrans_rows: list[dict[str, Any]],
):
    session = _session(
        bloodtrans_rows=bloodtrans_rows,
        daily_rows=[
            {"document_id": "DC-AMB", "record_time": "2026-01-01 17:00:00", "record_content": "输血后复查血红蛋白改善。"}
        ],
        horizon_date="2026-01-03",
    )

    execution, canonical = await _evaluate(session=session)

    assert (canonical.final_state.value, canonical.reason_code) == (
        "data_gap",
        "association_failed",
    )
    expected_refs = _selected_document_refs(
        session, "bloodtrans_record", {"BT-1", "BT-2"}
    ).union(_selected_document_refs(session, "daily_course_record", {"DC-AMB"}))
    assert expected_refs.issubset(set(execution.decisions[0].fact_refs))
    assert execution.llm_call_count == 0


@pytest.mark.asyncio
async def test_047_satisfied_episode_still_blocks_ambiguous_daily_for_remaining_episode():
    session = _session(
        bloodtrans_rows=[
            {
                "document_id": "BT-1",
                "record_content": "2026-01-01 10:00:00输血结束；输血后复查血红蛋白改善。",
                "record_time": "2026-01-01 11:00:00",
            },
            {"document_id": "BT-2", "record_content": "2026-01-01 16:00:00输血结束。"},
        ],
        daily_rows=[
            {"document_id": "DC-AMB", "record_time": "2026-01-01 17:00:00", "record_content": "输血后复查血红蛋白改善。"}
        ],
        horizon_date="2026-01-03",
    )

    _execution, canonical = await _evaluate(session=session)

    assert (canonical.final_state.value, canonical.reason_code) == (
        "data_gap",
        "association_failed",
    )


@pytest.mark.asyncio
async def test_047_two_explicit_end_anchors_bind_to_their_matching_episodes():
    session = _session(
        bloodtrans_rows=[
            {"document_id": "BT-1", "record_content": "2026-01-01 10:00:00输血结束。"},
            {"document_id": "BT-2", "record_content": "2026-01-01 16:00:00输血结束。"},
        ],
        daily_rows=[
            {"document_id": "DC-1", "record_time": "2026-01-01 17:00:00", "record_content": "2026-01-01 10:00:00输血结束后复查血红蛋白改善。"},
            {"document_id": "DC-2", "record_time": "2026-01-01 18:00:00", "record_content": "2026-01-01 16:00:00输血结束后复查血红蛋白改善。"},
        ],
        horizon_date="2026-01-03",
    )

    _execution, canonical = await _evaluate(session=session)

    assert (canonical.final_state.value, canonical.reason_code) == (
        "compliant",
        "requirement_satisfied",
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("horizon_date", "expected"),
    (
        ("2026-01-04", ("non_compliant", "requirement_violated")),
        ("2026-01-03", ("not_applicable", "evaluation_window_not_mature")),
    ),
)
async def test_047_missing_episode_keeps_existing_maturity_priority(
    horizon_date: str, expected: tuple[str, str]
):
    session = _session(
        bloodtrans_rows=[
            {
                "document_id": "BT-1",
                "record_content": "2026-01-01 10:00:00输血结束；输血后复查血红蛋白改善。",
                "record_time": "2026-01-01 11:00:00",
            },
            {"document_id": "BT-2", "record_content": "2026-01-02 16:00:00输血结束。"},
        ],
        daily_rows=[],
        horizon_date=horizon_date,
    )

    execution, canonical = await _evaluate(session=session)

    assert (canonical.final_state.value, canonical.reason_code) == expected
    assert execution.llm_call_count == 0
