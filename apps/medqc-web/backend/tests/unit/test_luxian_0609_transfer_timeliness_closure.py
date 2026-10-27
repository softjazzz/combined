"""00692/00693：多次转科、精确时间及实际消费文书的正式保存链。"""
from datetime import datetime, timedelta

import pytest

from app.services.luxian_0609.canonical_result_finalizer import finalize_luxian_0609_reduced_customer_result
from app.services.luxian_0609.decision_binding import bind_and_reduce_luxian_0609_rule_decisions
from app.services.luxian_0609.evidence_snapshot_provider import SnapshotSourceRows, build_luxian_0609_evidence_read_session
from app.services.luxian_0609.native_extended_document_execution import execute_luxian_0609_native_extended_document_rules
from app.services.luxian_0609.source_evidence_reader import CURRENT_VISIT_DISCHARGE_HORIZON_SOURCE_KEY
from test_luxian_0609_death_record_timeliness import saved_roundtrip

RULE = "LX0609-10-02-01"
PRESENCE = "LX0609-10-02-02"


def order(when="2026-06-01 08:00:00", target="外科", identifier="O1", **extra):
    return {"order_id": identifier, "order_name": f"转入{target}",
            "prescribed_datetime": when, "order_status": "执行中", **extra}


def record(when="2026-06-01 09:00:00", target="外科", identifier="R1", **extra):
    return {"document_id": identifier, "record_time": when,
            "transferin_department": target, "record_content": "合成转科记录。", **extra}


async def run(orders, incoming, outgoing, *, rule=RULE,
              horizon="2026-06-10 12:00:00", unavailable=(), truncated=(), frozen_day="2026-06-11"):
    from app.services.luxian_0609.source_evidence_reader import SourceEvidenceUnavailable
    rows = {"inpat_registration": [{"admission_datetime": "2026-06-01 00:00:00"}],
            CURRENT_VISIT_DISCHARGE_HORIZON_SOURCE_KEY: [{"discharge_datetime": horizon}],
            "inpat_nondrug_order": orders, "transfer_in_record": incoming,
            "transfer_out_record": outgoing}

    def reader(**kwargs):
        source = kwargs["source_key"]
        if source in unavailable:
            raise SourceEvidenceUnavailable()
        return SnapshotSourceRows.create(source_key=source, rows=rows.get(source, ()),
                                         truncated=source in truncated, limit_rows=50)

    session = build_luxian_0609_evidence_read_session(
        selected_rule_ids=(rule,), institute_id="I", patient_id="P", visit_id="V",
        source_schema=None, created_at="2026-06-11T12:00:00+08:00",
        evaluation_as_of_date="2026-06-11", row_reader=reader,
        evaluation_horizon_policy=("disabled" if CURRENT_VISIT_DISCHARGE_HORIZON_SOURCE_KEY in unavailable
                                   else "authoritative_discharge"),
        horizon_unavailable_reason=("authoritative_time_missing" if CURRENT_VISIT_DISCHARGE_HORIZON_SOURCE_KEY in unavailable else None),
        evaluation_horizon_snapshot=(None if CURRENT_VISIT_DISCHARGE_HORIZON_SOURCE_KEY in unavailable else {
            "record_id": "V", "institute_id": "I", "patient_id": "P", "visit_id": "V",
            "record_scene": "final", "resolution_status": "resolved", "evaluation_basis": "discharge_datetime",
            "evaluation_horizon": str(horizon)[:10], "admission_datetime": "2026-06-01 00:00:00",
            "discharge_datetime": str(horizon),
            "task_frozen_date": frozen_day,
        }),
    )
    execution = await execute_luxian_0609_native_extended_document_rules(
        rule_ids=(rule,), decision_rule_ids=(rule,), evidence_snapshot=session.snapshot,
        evidence_materials=session.materials, llm_client=None,
    )
    assert execution.llm_call_count == 0
    reduced = bind_and_reduce_luxian_0609_rule_decisions(
        decisions=execution.decisions, expected_rule_ids=(rule,), snapshot=session.snapshot,
        evidence_materials=session.materials,
    )[0]
    final = finalize_luxian_0609_reduced_customer_result(
        decision=reduced, raw_customer_display_facts=dict(execution.customer_display_facts).get(rule),
        evidence_snapshot=session.snapshot, evidence_materials=session.materials,
    )
    loaded = saved_roundtrip(final)
    assert (loaded["status"], loaded["reason_code"]) == (final["status"], final["reason_code"])
    assert loaded.get("customer_display_facts") == final.get("customer_display_facts")
    return final, session, execution


@pytest.mark.asyncio
@pytest.mark.parametrize("rule", [RULE, PRESENCE])
@pytest.mark.parametrize("same_clock", [False, True])
async def test_overlapping_transfers_keep_unique_department_ownership(rule, same_clock):
    result, _, _ = await run(
        [order(), order("2026-06-01 10:00:00", "内科", "O2")],
        [record("2026-06-01 11:00:00", identifier="I1"),
         record("2026-06-01 11:00:00" if same_clock else "2026-06-01 12:00:00", "内科", "I2")],
        [record("2026-06-01 11:00:00", identifier="U1"),
         record("2026-06-01 11:00:00" if same_clock else "2026-06-01 12:00:00", "内科", "U2")],
        rule=rule,
    )
    assert result["status"] == "compliant"
    events = result["customer_display_facts"]["event_checks"]
    assert len(events) == 2
    assert all(event["status"] == "compliant" for event in events)


@pytest.mark.asyncio
@pytest.mark.parametrize("clock", ["2026-06-02T01:00:00Z", datetime.fromisoformat("2026-06-02T01:00:00+00:00")])
async def test_equivalent_utc_clocks_remain_25_hours_and_bound(clock):
    result, session, execution = await run([order()], [record(clock, identifier="I")], [record(identifier="U")])
    assert result["status"] == "non_compliant"
    assert result["customer_display_facts"]["transfer_in_time"] == "2026-06-02 09:00:00"
    incoming_ref = next(iter(session.materials.document_rows("transfer_in_record", snapshot=session.snapshot)))[0]
    assert incoming_ref in execution.decisions[0].fact_refs


@pytest.mark.asyncio
@pytest.mark.parametrize("alias", ["2026-06-01", "INVALID"])
async def test_invalid_order_alias_cannot_hide_behind_another_valid_clock(alias):
    result, _, _ = await run([order(start_time=alias)], [record(identifier="I")], [record(identifier="U")])
    assert (result["status"], result["reason_code"]) == ("data_gap", "authoritative_time_missing")


@pytest.mark.asyncio
@pytest.mark.parametrize("bad_time", ["2026-06-01", "INVALID"])
async def test_invalid_primary_record_time_cannot_use_event_time_as_completion(bad_time):
    result, _, _ = await run([order()],
                             [record(bad_time, identifier="I", transfer_date="2026-06-01 09:00:00")],
                             [record(identifier="U")])
    assert (result["status"], result["reason_code"]) == ("data_gap", "authoritative_time_missing")


@pytest.mark.asyncio
@pytest.mark.parametrize("rule", [RULE, PRESENCE])
async def test_same_clock_historical_row_is_not_reintroduced_by_binding(rule):
    result, session, execution = await run([order()],
        [record(identifier="CURRENT"), record(identifier="HISTORY", transfer_date="2026-05-01", target="内科")],
        [record(identifier="U")], rule=rule)
    assert result["status"] == "compliant"
    refs = {row["document_id"]: ref for ref, row in session.materials.document_rows("transfer_in_record", snapshot=session.snapshot)}
    assert refs["CURRENT"] in execution.decisions[0].fact_refs
    assert refs["HISTORY"] not in execution.decisions[0].fact_refs


@pytest.mark.asyncio
@pytest.mark.parametrize("delta,status", [(-1, "compliant"), (0, "compliant"), (1, "non_compliant")])
@pytest.mark.parametrize("source", ["in", "out"])
async def test_24_hour_microsecond_boundary_survives_save(delta, status, source):
    end = datetime(2026, 6, 2, 8) + timedelta(microseconds=delta)
    incoming = record(end if source == "in" else "2026-06-01 09:00:00", identifier="I")
    outgoing = record(end if source == "out" else "2026-06-01 09:00:00", identifier="U")
    result, _, _ = await run([order()], [incoming], [outgoing])
    assert result["status"] == status
    assert result["customer_display_facts"][f"transfer_{source}_time"] == end.isoformat(sep=" ")
    if delta == 1:
        from app.services.luxian_0609.customer_renderer import customer_finding_from_controlled_facts
        assert "超时0.000001秒" in customer_finding_from_controlled_facts(rule_id=RULE, facts=result["customer_display_facts"])


@pytest.mark.asyncio
async def test_future_records_do_not_complete_a_frozen_transfer_window():
    result, _, _ = await run([order()], [record("2026-06-02 08:00:00", identifier="I")],
                             [record(identifier="U")], horizon="2026-06-01 12:00:00", frozen_day="2026-06-01")
    assert (result["status"], result["reason_code"]) == ("not_applicable", "evaluation_window_not_mature")


@pytest.mark.asyncio
async def test_missing_horizon_cannot_turn_existing_transfer_records_into_compliance():
    result, _, _ = await run([order()], [record(identifier="I")], [record(identifier="U")],
                             unavailable=(CURRENT_VISIT_DISCHARGE_HORIZON_SOURCE_KEY,))
    assert result["status"] == "data_gap"


@pytest.mark.asyncio
@pytest.mark.parametrize("when,status", [("2026-06-02 07:00:00", "compliant"),
                                         ("2026-06-02 09:00:00", "non_compliant")])
async def test_postdischarge_supplement_keeps_original_24_hour_contract(when, status):
    result, _, _ = await run([order()], [record(when, identifier="I")], [record(identifier="U")],
                             horizon="2026-06-01 12:00:00", frozen_day="2026-06-03")
    assert result["status"] == status


@pytest.mark.asyncio
@pytest.mark.parametrize("frozen_day", [None, "INVALID"])
async def test_missing_final_visibility_date_cannot_fall_back_to_discharge(frozen_day):
    result, _, _ = await run([order()], [record("2026-06-01 14:00:00", identifier="I")],
                             [record("2026-06-01 15:00:00", identifier="U")],
                             horizon="2026-06-01 12:00:00", frozen_day=frozen_day)
    assert (result["status"], result["reason_code"]) == ("data_gap", "authoritative_time_missing")


@pytest.mark.asyncio
@pytest.mark.parametrize("rule", [RULE, PRESENCE])
async def test_historical_event_cannot_use_early_out_exception(rule):
    result, session, execution = await run([order()], [record(identifier="I")],
        [record("2026-06-01 07:00:00", identifier="OLD_OUT", transfer_date="2026-05-01")], rule=rule)
    assert (result["status"], result["reason_code"]) == ("non_compliant", "required_document_missing")
    old_ref = next(iter(session.materials.document_rows("transfer_out_record", snapshot=session.snapshot)))[0]
    assert old_ref not in execution.decisions[0].fact_refs


@pytest.mark.parametrize("bad_event", [
    {"medical_text": "不得发布的合成正文"},
    {"event_checks": []},
    {"verification_kind": ["invalid"]},
    {"status": {"bad": True}},
    {"reason_code": "arbitrary_private_reason"},
    {"transfer_order_time": "2026-99-01 08:00:00"},
])
def test_multi_event_public_contract_rejects_extra_or_malformed_data(bad_event):
    from app.services.luxian_0609.continuity_result_mapping import (
        safe_continuity_customer_display_facts, validate_published_continuity_facts,
    )
    base = {"verification_kind": "transfer_record_timeliness_check",
            "transfer_order_time": "2026-06-01 08:00:00", "transfer_in_time": "2026-06-01 09:00:00",
            "transfer_out_time": "2026-06-01 09:00:00", "threshold_hours": 24,
            "transfer_in_interval_hours": 1.0, "transfer_out_interval_hours": 1.0}
    raw = {**base, "transfer_order_count": 2,
           "event_checks": [{**base, "status": "compliant", "reason_code": "requirement_within_threshold", **bad_event}]}
    assert safe_continuity_customer_display_facts(rule_id=RULE, raw=raw) is None
    assert validate_published_continuity_facts(rule_id=RULE, raw=raw, status="compliant") == (False, None)
