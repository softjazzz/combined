"""阶段小结：30天循环、替代重置及资料缺口，禁止只看是否有任意一份文书。"""
from datetime import datetime, timedelta
from itertools import permutations

import pytest

from app.services.luxian_0609.extended_document.stage_summary_timeliness import (
    evaluate_stage_summary_timeliness,
)

START = datetime(2026, 1, 1, 8)


def document(day=30, **changes):
    return {"document_id": f"S{day}", "document_title": "阶段小结", "record_content": "阶段诊疗情况总结。",
            "record_time": START + timedelta(days=day), **changes}


def evaluate(days=31, documents=None, **changes):
    horizon = START + timedelta(days=days)
    return evaluate_stage_summary_timeliness(
        registration_rows=changes.pop("registration_rows", [{"admission_datetime": START}]),
        admission_rows=changes.pop("admission_rows", ()),
        document_rows=documents or {},
        horizon_rows=changes.pop("horizon_rows", [{"horizon_datetime": horizon,
            "horizon_date": horizon.date().isoformat(), "basis": "discharge_date"}]),
        source_error=changes.pop("source_error", ""), **changes,
    )


@pytest.mark.parametrize("seconds,status", [(-1,"not_applicable"),(0,"not_applicable"),(1,"non_compliant")])
def test_strict_more_than_30_days_threshold(seconds, status):
    outcome = evaluate(days=30 + seconds / 86400)
    assert outcome.final_state == status


def test_31_day_discharge_has_no_exemption():
    assert evaluate(31).final_state == "non_compliant"


def test_record_at_exact_deadline_satisfies_period():
    assert evaluate(documents={"summary_record": [document()]}).final_state == "compliant"


def test_one_second_late_does_not_erase_old_period():
    outcome = evaluate(documents={"summary_record": [document(record_time=START + timedelta(days=30, seconds=1))]})
    assert outcome.final_state == "non_compliant"
    assert outcome.display_facts["overdue_deadlines"] == ["2026-01-31 08:00:00"]


def test_long_stay_is_checked_per_period():
    outcome = evaluate(91, {"summary_record": [document(30)]})
    assert outcome.final_state == "non_compliant"
    assert outcome.display_facts["overdue_deadlines"] == ["2026-03-02 08:00:00", "2026-04-01 08:00:00"]


@pytest.mark.parametrize("source,title", [("handoff_record","交班记录"),("handover_record","接班记录"),
    ("transfer_in_record","转入记录"),("transfer_out_record","转出记录")])
def test_real_substitute_resets_next_period(source, title):
    outcome = evaluate(40, {source: [document(20, document_title=title)]})
    assert outcome.final_state == "compliant"
    assert len(outcome.display_facts["substitute_times"]) == 1


def test_substitute_is_not_a_permanent_exemption():
    outcome = evaluate(51, {"transfer_in_record": [document(20, document_title="转入记录")]})
    assert outcome.final_state == "non_compliant"
    assert outcome.display_facts["overdue_deadlines"] == ["2026-02-20 08:00:00"]


def test_late_substitute_cannot_erase_missed_period():
    assert evaluate(45, {"handoff_record": [document(40, document_title="交班记录")]}).final_state == "non_compliant"


def test_full_period_coverage_is_stable_under_reordering():
    rows = [document(30), document(60), document(90)]
    outcomes = [evaluate(91, {"summary_record": list(order)}) for order in permutations(rows)]
    assert all(item == outcomes[0] for item in outcomes)
    assert outcomes[0].final_state == "compliant"


@pytest.mark.parametrize("clock", [None,"","2026-01-31","invalid"])
def test_untimed_record_never_becomes_a_pass_or_missing_document_defect(clock):
    outcome = evaluate(documents={"summary_record": [document(record_time=clock)]})
    assert (outcome.final_state, outcome.reason_code) == ("data_gap", "authoritative_time_missing")


def test_blank_body_and_missing_title_are_not_valid_summaries():
    for row in (document(record_content=""), document(document_title="")):
        assert evaluate(documents={"summary_record": [row]}).final_state == "data_gap"


def test_official_submit_time_fallback_does_not_replace_present_record_time():
    assert evaluate(documents={"summary_record": [document(record_time=None,
        submit_datetime=START + timedelta(days=30))]}).final_state == "compliant"
    assert evaluate(documents={"summary_record": [document(31,
        submit_datetime=START + timedelta(days=30))]}).final_state == "non_compliant"


@pytest.mark.parametrize("state", ["held","version_review"])
def test_unapproved_pdf_cannot_satisfy_period(state):
    assert evaluate(documents={"summary_record": [document(validation_material_state=state)]}).final_state == "non_compliant"


def test_future_summary_cannot_satisfy_frozen_period():
    outcome = evaluate(31, {"summary_record": [document(35)]})
    assert outcome.final_state == "non_compliant"
    assert outcome.display_facts["summary_times"] == []


@pytest.mark.parametrize("error", ["source_unavailable","source_truncated","source_query_failed"])
def test_incomplete_sources_never_produce_a_clinical_result(error):
    assert evaluate(source_error=error).final_state == "data_gap"


def test_admission_record_is_approved_fallback_but_writing_time_is_not_admission():
    assert evaluate(registration_rows=[], admission_rows=[{"admission_datetime": START}]).final_state == "non_compliant"
    assert evaluate(registration_rows=[], admission_rows=[{"record_time": START}]).final_state == "data_gap"


def test_conflicting_admission_anchors_are_not_chosen_by_recency():
    assert evaluate(registration_rows=[{"admission_datetime": START},
        {"admission_datetime": START + timedelta(days=1)}]).reason_code == "authoritative_time_conflict"


def test_same_source_same_id_different_versions_are_a_gap():
    assert evaluate(documents={"summary_record": [document(), document(31,document_id="S30")]}).final_state == "data_gap"


def test_unknown_or_conflicting_horizon_is_not_replaced_by_machine_time():
    for rows in ([], [{"horizon_datetime": START - timedelta(days=1),"basis":"discharge_date"}],
                 [{"horizon_datetime": START + timedelta(days=31),"horizon_date":"2026-02-02","basis":"discharge_date"}]):
        assert evaluate(horizon_rows=rows).final_state == "data_gap"


def test_date_only_horizon_keeps_ambiguous_boundary_unknown():
    outcome = evaluate(horizon_rows=[{"horizon_date":"2026-01-31", "basis":"evaluation_as_of"}])
    assert (outcome.final_state, outcome.reason_code) == ("data_gap", "authoritative_time_missing")


def test_date_only_horizon_can_prove_already_missed_period():
    outcome = evaluate(horizon_rows=[{"horizon_date":"2026-02-01", "basis":"evaluation_as_of"}])
    assert outcome.final_state == "non_compliant"
    assert outcome.display_facts["evaluation_time"] is None


@pytest.mark.parametrize("value", ["2026-01-31T08:00:00+08:00","2026-01-31T00:00:00Z"])
def test_hospital_timezone_is_independent_of_developer_timezone(value):
    assert evaluate(documents={"summary_record": [document(record_time=value)]}).final_state == "compliant"


async def final_result(sources=None, *, days=31, unavailable=(), truncated=(),
                       identity=("I","P","V"), created_at="2026-05-01T12:00:00+08:00",
                       horizon_policy="authoritative_discharge", frozen_horizon=None):
    from app.services.luxian_0609.canonical_result_finalizer import finalize_luxian_0609_reduced_customer_result
    from app.services.luxian_0609.decision_binding import bind_and_reduce_luxian_0609_rule_decisions
    from app.services.luxian_0609.evidence_snapshot_provider import SnapshotSourceRows, build_luxian_0609_evidence_read_session
    from app.services.luxian_0609.native_extended_document_execution import execute_luxian_0609_native_extended_document_rules
    from app.services.luxian_0609.source_evidence_reader import SourceEvidenceUnavailable

    rule = "LX0609-10-04-01"
    rows = sources if sources is not None else {
        "inpat_registration": [{"admission_datetime":START}],
        "inpat_registration.discharge_horizon": [{"discharge_datetime":START + timedelta(days=days)}],
        "summary_record": [document()],
    }
    def reader(**kwargs):
        source = kwargs["source_key"]
        if source in unavailable:
            raise SourceEvidenceUnavailable()
        return SnapshotSourceRows.create(source_key=source, rows=rows.get(source, ()),
            truncated=source in truncated, limit_rows=100)
    session = build_luxian_0609_evidence_read_session(
        selected_rule_ids=(rule,), institute_id=identity[0], patient_id=identity[1], visit_id=identity[2],
        source_schema=None, created_at=created_at, evaluation_as_of_date=created_at[:10], row_reader=reader,
        evaluation_horizon_policy=horizon_policy, evaluation_horizon_snapshot=frozen_horizon,
    )
    execution = await execute_luxian_0609_native_extended_document_rules(
        rule_ids=(rule,), decision_rule_ids=(rule,), evidence_snapshot=session.snapshot,
        evidence_materials=session.materials, llm_client=None,
    )
    assert execution.llm_call_count == 0
    reduced = bind_and_reduce_luxian_0609_rule_decisions(decisions=execution.decisions,
        expected_rule_ids=(rule,), snapshot=session.snapshot, evidence_materials=session.materials)[0]
    return finalize_luxian_0609_reduced_customer_result(decision=reduced,
        raw_customer_display_facts=dict(execution.customer_display_facts).get(rule),
        evidence_snapshot=session.snapshot, evidence_materials=session.materials)


@pytest.mark.asyncio
async def test_actual_execution_binding_finalizer_and_store():
    from test_luxian_0609_death_record_timeliness import saved_roundtrip

    result = await final_result()
    assert result["status"] == "compliant"
    assert result["customer_evidence"][0]["source_type"] == "summary_record"
    loaded = saved_roundtrip(result)
    assert loaded["status"] == result["status"]
    assert loaded["customer_display_facts"] == result["customer_display_facts"]
    # Canonical将坐标保存为受保护source_ref，并统一到evidence键，不重选文书。
    assert len(loaded["evidence"]) == len(result["customer_evidence"])
    for stored, original in zip(loaded["evidence"], result["customer_evidence"]):
        assert stored["source_type"] == original["source_type"]
        assert stored["evidence_excerpt"] == original["evidence_excerpt"]
        assert stored["source_ref"].startswith("src_")


@pytest.mark.asyncio
async def test_actual_long_stay_missing_later_periods_is_saved():
    from test_luxian_0609_death_record_timeliness import saved_roundtrip

    result = await final_result(days=91)
    assert result["status"] == "non_compliant"
    assert len(result["customer_display_facts"]["overdue_deadlines"]) == 2
    assert saved_roundtrip(result)["customer_display_facts"] == result["customer_display_facts"]


@pytest.mark.asyncio
@pytest.mark.parametrize("source", ["summary_record","handoff_record","handover_record","transfer_in_record","transfer_out_record",
                                    "inpat_registration","admission_record","inpat_registration.discharge_horizon"])
async def test_actual_unavailable_sources_fail_closed(source):
    result = await final_result(unavailable=(source,))
    assert result["status"] == "data_gap"


@pytest.mark.asyncio
async def test_actual_admission_record_fallback():
    result = await final_result({"admission_record":[{"admission_datetime":START}], "summary_record":[document()],
        "inpat_registration.discharge_horizon":[{"discharge_datetime":START + timedelta(days=31)}]})
    assert result["status"] == "compliant"


@pytest.mark.asyncio
async def test_actual_truncated_summary_is_not_a_pass():
    assert (await final_result(truncated=("summary_record",)))["status"] == "data_gap"


@pytest.mark.asyncio
async def test_public_facts_tampering_and_clinical_missing_facts_are_rejected():
    from app.services.luxian_0609.canonical_result_finalizer import validate_luxian_0609_published_customer_display_facts

    facts = (await final_result())["customer_display_facts"]
    for damaged in (None, {**facts, "source_document_id":"PRIVATE"}, {**facts, "threshold_days":True},
                    {**facts, "overdue_deadlines":["invalid"]}, {**facts, "admission_time": START},
                    {**facts, "evaluation_time":START + timedelta(days=31)}):
        with pytest.raises(ValueError, match="解释合同不完整"):
            validate_luxian_0609_published_customer_display_facts(rule_id="LX0609-10-04-01", raw=damaged, status="compliant")


def test_summary_source_reader_is_bounded_scoped_and_projects_only_approved_fields(monkeypatch):
    from app.services.luxian_0609 import source_evidence_reader as reader
    from test_luxian_0609_source_evidence_reader import _Engine, _SourceRowsConnection

    connection = _SourceRowsConnection([document()])
    monkeypatch.setattr(reader.bundle_assembly, "engine", _Engine(connection))
    monkeypatch.setattr(reader.bundle_assembly, "_default_source_schema", lambda: "cdm")
    monkeypatch.setattr(reader.bundle_assembly, "_get_table_columns", lambda schema, table: [
        "institute_id","patient_id","visit_id","document_id","document_title","record_content",
        "record_time","submit_datetime","private_extra_field",
    ])
    result = reader.read_luxian_0609_snapshot_source_rows(source_key="summary_record",
        institute_id="I",patient_id="P",visit_id="V",source_schema=None)
    assert result.rows[0]["document_title"] == "阶段小结"
    sql, params = connection.calls[0]
    assert '"summary_record"' in sql
    assert "private_extra_field" not in sql
    assert all(f'"{key}" = :{key}' in sql for key in ("institute_id","patient_id","visit_id"))
    assert {key: params[key] for key in ("institute_id","patient_id","visit_id")} == {"institute_id":"I","patient_id":"P","visit_id":"V"}
    assert "LIMIT :limit_rows" in sql and params["limit_rows"] == result.limit_rows + 1
