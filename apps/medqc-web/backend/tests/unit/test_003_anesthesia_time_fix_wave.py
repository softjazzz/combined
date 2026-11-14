"""固定提交复审 F2/F3：原始麻醉实施事实、时序与最终交付。"""

from contextlib import nullcontext

import pytest

from app.services import case_material_snapshot as automatic_material
from app.services.luxian_0609 import native_surgery_gate_execution as surgery
from app.services.luxian_0609.canonical_result_finalizer import finalize_luxian_0609_reduced_customer_result
from app.services.luxian_0609.decision_binding import bind_and_reduce_luxian_0609_rule_decisions
from test_luxian_0609_native_surgery_gate_execution import _typed_003_session
from test_surgery_independent_positive_scope import _auto_state


def _anesthesia(body, *, begin="2026-01-01 08:00:00+08:00", end="2026-01-01 10:00:00+08:00"):
    return {"document_id": "synthetic-anesthesia-003",
            "record_content": f"{body}\n手术开始时间：{begin}\n手术结束时间：{end}"}


def _finalize(session):
    display = []
    decision = surgery._typed_003_decision(
        snapshot=session.snapshot, materials=session.materials, customer_display_facts=display,
    )
    reduced = bind_and_reduce_luxian_0609_rule_decisions(
        decisions=(decision,), expected_rule_ids=(decision.rule_id,),
        snapshot=session.snapshot, evidence_materials=session.materials,
    )[0]
    result = finalize_luxian_0609_reduced_customer_result(
        decision=reduced, raw_customer_display_facts=dict(display).get(decision.rule_id),
        evidence_snapshot=session.snapshot, evidence_materials=session.materials,
    )
    return decision, reduced, result


@pytest.mark.parametrize("automatic", [False, True])
def test_anesthesia_end_before_matching_begin_is_conflict_through_finalizer(automatic):
    state = _auto_state()
    state["automatic_material"]["sources"]["anesthesia_record"]["status"] = "available"
    with automatic_material.activate(state) if automatic else nullcontext():
        session = _typed_003_session(
            surgery_document_id="synthetic-S1", surgery_begin_time="2026-01-01 12:00:00+08:00",
            record_time="2026-01-02 13:00:00",
            original_anesthesia_rows=(_anesthesia("本次手术已完成。", begin="2026-01-01 12:00:00+08:00"),),
        )
        decision, reduced, result = _finalize(session)
        assert decision.reason_code == "authoritative_time_conflict"
        assert decision.positive_document_refs == ()
        assert set(decision.fact_refs) == {
            ref for key in ("surgery_record", "anesthesia_record")
            for ref, _row in session.materials.document_rows(key, snapshot=session.snapshot)
        }
        assert (reduced.final_state.value, reduced.reason_code) == ("data_gap", "authoritative_time_conflict")
        assert (result["status"], result["reason_code"]) == ("data_gap", "authoritative_time_conflict")


@pytest.mark.parametrize("existing_record", [False, True])
@pytest.mark.parametrize("body", [
    "本次手术已取消，尚未实施。以下为术前排班预填时间，非实际手术时间：",
    "拟行手术，尚未实施。以下为计划手术时间：",
    "排班预填，以下时间非实际实施时间。",
    "本次手术已完成。另记：本次手术已取消，尚未实施。",
    "",  # 标签与来源名本身不能证明已实施。
])
def test_planned_cancelled_or_unproven_anesthesia_times_cannot_be_borrowed(existing_record, body):
    session = _typed_003_session(
        source_mode="available" if existing_record else "empty",
        surgery_document_id="synthetic-S1", surgery_begin_time="2026-01-01 08:00:00+08:00",
        record_time="2026-01-02 11:00:00", evaluation_as_of_date="2026-01-03",
        original_anesthesia_rows=(_anesthesia(body),),
    )
    decision, reduced, result = _finalize(session)
    assert decision.evidence_state.value == "data_gap"
    assert decision.positive_document_refs == ()
    assert reduced.final_state.value == result["status"] == "data_gap"
    assert result.get("customer_display_facts", {}).get("performed_surgery_confirmed") is not True


@pytest.mark.parametrize("body", ["本次手术已完成。", "本次手术按计划顺利实施并已完成。", "本次手术未取消，已完成。"])
@pytest.mark.parametrize("hours,expected", [(24, "compliant"), (25, "non_compliant")])
def test_actual_anesthesia_with_ordinary_plan_wording_keeps_24h_boundary(body, hours, expected):
    session = _typed_003_session(
        surgery_document_id="synthetic-S1", surgery_begin_time="2026-01-01 08:00:00+08:00",
        record_time=f"2026-01-02 {10 + hours - 24}:00:00",
        original_anesthesia_rows=(_anesthesia(body),),
    )
    decision, reduced, result = _finalize(session)
    assert reduced.final_state.value == result["status"] == expected
    if hours == 25:
        assert len(decision.positive_document_refs) == 2


@pytest.mark.parametrize("date,expected", [("2026-01-02", "data_gap"), ("2026-01-03", "non_compliant")])
def test_actual_anesthesia_missing_record_retains_maturity_window(date, expected):
    session = _typed_003_session(
        source_mode="empty", evaluation_as_of_date=date,
        original_anesthesia_rows=(_anesthesia("本次手术按计划顺利实施并已完成。"),),
    )
    decision, reduced, result = _finalize(session)
    assert reduced.final_state.value == result["status"] == expected
    assert decision.positive_document_refs == ()
