"""RR-D02冻结合成预期：未知完成时间不得被晚讨论静默覆盖。"""

from datetime import datetime

import pytest

from app.services.luxian_0609.extended_document.death_discussion import evaluate_death_discussion_timeliness
from tests.unit.test_luxian_0609_native_extended_document_execution import (
    _canonical_extended_result,
    _evaluate_selected,
)


RULE = "LX0609-09-02-01"
DEATH = {"document_id": "SYNTH-DEATH-D02", "death_datetime": "2026-09-01 08:00:00"}
BODY = "死亡病例讨论已进行，讨论死亡原因和诊疗过程。"
LATE = {"document_id": "SYNTH-LATE-D02", "record_time": "2026-09-10 08:00:00", "record_content": BODY}
TIMELY = {"document_id": "SYNTH-TIMELY-D02", "record_time": "2026-09-02 08:00:00", "record_content": BODY}
HORIZON = {"horizon_datetime": "2026-09-20 08:00:00", "horizon_date": "2026-09-20", "basis": "evaluation_as_of"}


def _outcome(rows, *, horizon=HORIZON):
    return evaluate_death_discussion_timeliness(
        death_time=datetime(2026, 9, 1, 8), death_rows=(DEATH,),
        discussion_rows=rows, discussion_error="", horizon_rows=(horizon,), horizon_error="",
    )


@pytest.mark.parametrize("unknown_time", [None, "", "invalid-time"])
@pytest.mark.parametrize("reverse", [False, True])
def test_real_untimed_discussion_blocks_earliest_overdue_assertion(unknown_time, reverse):
    unknown = {"document_id": "SYNTH-UNTIMED-D02", "record_time": unknown_time, "record_content": BODY}
    rows = (LATE, unknown) if reverse else (unknown, LATE)
    outcome = _outcome(rows)
    assert (outcome.final_state, outcome.reason_code) == ("data_gap", "authoritative_time_missing")
    assert outcome.display_facts is None


@pytest.mark.parametrize("unknown_body", [None, "", " \n\t", 123, True, {}, []])
def test_explicit_empty_untimed_body_does_not_block_known_late_discussion(unknown_body):
    unknown = {"document_id": "SYNTH-EMPTY-D02", "record_content": unknown_body}
    outcome = _outcome((unknown, LATE))
    assert (outcome.final_state, outcome.reason_code) == ("non_compliant", "threshold_exceeded")
    assert outcome.display_facts["discussion_time"] == LATE["record_time"]


def test_absent_untimed_body_does_not_claim_a_real_discussion():
    # 原冻结D02只有ID；本修复的真实正文反例另行冻结，不补造原材料。
    outcome = _outcome(({"document_id": "SYNTH-BODY-UNAVAILABLE-D02"}, LATE))
    assert (outcome.final_state, outcome.reason_code) == ("non_compliant", "threshold_exceeded")


@pytest.mark.parametrize("rows", [
    ({"document_id": "SYNTH-UNTIMED-D02", "record_content": BODY}, LATE, TIMELY),
    (TIMELY, {"document_id": "SYNTH-UNTIMED-D02", "record_content": BODY}, LATE),
])
def test_real_timely_discussion_keeps_compliant_with_unknown_and_late_candidates(rows):
    outcome = _outcome(rows)
    assert (outcome.final_state, outcome.reason_code) == ("compliant", "requirement_within_threshold")
    assert outcome.display_facts["discussion_time"] == TIMELY["record_time"]
    assert outcome.display_facts["source_document_refs"] == [
        {"source_type": "death_record", "source_document_id": DEATH["document_id"]},
        {"source_type": "death_discussion", "source_document_id": TIMELY["document_id"]},
    ]


def test_future_frozen_evaluation_endpoint_is_not_compared_to_machine_now():
    unknown = {"document_id": "SYNTH-UNTIMED-D02", "record_content": BODY}
    outcome = _outcome((unknown, TIMELY), horizon={"horizon_date": "2099-01-01", "basis": "evaluation_as_of"})
    assert outcome.final_state == "compliant"


@pytest.mark.parametrize("record_time,state", [
    ("2026-09-08 08:00:00", "compliant"),
    ("2026-09-08 08:00:01", "non_compliant"),
])
def test_minimal_timed_fixture_without_body_keeps_second_boundary(record_time, state):
    assert _outcome(({"record_time": record_time},)).final_state == state


@pytest.mark.parametrize("horizon,state,reason", [
    ({"horizon_datetime": "2026-09-03 08:00:00"}, "data_gap", "evaluation_window_not_mature"),
    (HORIZON, "non_compliant", "required_document_missing"),
])
def test_complete_empty_discussion_source_keeps_existing_maturity_contract(horizon, state, reason):
    outcome = _outcome((), horizon=horizon)
    assert (outcome.final_state, outcome.reason_code) == (state, reason)


@pytest.mark.asyncio
@pytest.mark.parametrize("timely", [False, True])
async def test_rr_d02_formal_execution_reduction_and_finalizer_preserve_expected_state(timely):
    discussions = ({"document_id": "SYNTH-UNTIMED-D02", "record_content": BODY}, LATE)
    if timely:
        discussions += (TIMELY,)
    snapshot, materials, execution, reduced = await _evaluate_selected((RULE,), {
        "death_record": (DEATH,), "death_discussion": discussions,
        "evaluation_context.horizon": (HORIZON,),
    })
    expected = "compliant" if timely else "data_gap"
    assert reduced[0].final_state.value == expected
    assert reduced[0].reason_code == ("requirement_within_threshold" if timely else "authoritative_time_missing")
    canonical = _canonical_extended_result(rule_id=RULE, snapshot=snapshot, materials=materials, result=execution, reduced=reduced)
    assert canonical["status"] == expected
    if timely:
        assert canonical["customer_display_facts"]["discussion_time"] == TIMELY["record_time"]
    else:
        assert "超时48" not in canonical["findings"]
    assert execution.llm_call_count == execution.total_tokens == 0
