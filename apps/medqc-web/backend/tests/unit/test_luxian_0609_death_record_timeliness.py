"""死亡记录24小时：标题分流、精确时差与不完整证据反例。"""
from datetime import datetime, timedelta
from itertools import permutations

import pytest

from app.services.luxian_0609.extended_document.death_record_timeliness import (
    evaluate_death_record_timeliness,
)

DEATH = datetime(2026, 1, 1, 8)


def row(seconds=3600, **changes):
    return {"document_id": "D1", "document_title": "死亡记录",
            "record_content": "本次住院死亡记录正文。", "record_time": DEATH + timedelta(seconds=seconds),
            **changes}


def evaluate(rows=None, **changes):
    death_time = changes.pop("death_time", DEATH)
    return evaluate_death_record_timeliness(
        death_rows=[row()] if rows is None else rows,
        discharge_rows=changes.pop("discharge_rows", ()),
        registration_rows=changes.pop("registration_rows", [{"death_datetime": death_time}]),
        source_error=changes.pop("source_error", ""), **changes,
    )


@pytest.mark.parametrize("seconds,status", [(86399,"compliant"),(86400,"compliant"),(86401,"non_compliant")])
def test_second_precision_threshold(seconds, status):
    outcome = evaluate([row(seconds)])
    assert outcome.final_state == status
    assert outcome.display_facts["elapsed_seconds"] == seconds


@pytest.mark.parametrize("value", ["2026-01-01T09:00:00+08:00", "2026-01-01T01:00:00Z", "2026-01-01 09:00:00"])
def test_clock_representations_use_hospital_timezone(value):
    outcome = evaluate([row(record_time=value)])
    assert outcome.final_state == "compliant"
    assert outcome.display_facts["elapsed_seconds"] == 3600


def test_latest_authoritative_document_and_evidence_are_stable_under_reordering():
    records = [row(3600), row(90000, document_id="D2")]
    outcomes = [evaluate(list(order)) for order in permutations(records)]
    assert outcomes[0] == outcomes[1]
    assert outcomes[0].final_state == "non_compliant"
    assert outcomes[0].document_refs[0]["source_document_id"] == "D2"


@pytest.mark.parametrize("value", [None, "", "2026-01-02", "not-a-time"])
def test_missing_or_date_only_completion_is_not_a_pass(value):
    outcome = evaluate([row(record_time=value)])
    assert (outcome.final_state, outcome.reason_code) == ("data_gap", "authoritative_time_missing")


def test_unknown_version_is_not_silently_discarded():
    outcome = evaluate([row(90000), row(document_id="D2", record_time=None)])
    assert outcome.final_state == "data_gap"


def test_official_submission_is_used_only_when_record_clock_absent():
    outcome = evaluate([row(record_time="", submit_datetime=DEATH+timedelta(hours=2))])
    assert outcome.display_facts["elapsed_seconds"] == 7200
    assert evaluate([row(90000, submit_datetime=DEATH+timedelta(hours=2))]).final_state == "non_compliant"


def test_completion_before_death_is_a_conflict():
    assert evaluate([row(-1)]).reason_code == "authoritative_time_conflict"


def test_empty_death_source_does_not_duplicate_presence_defect():
    outcome = evaluate([])
    assert (outcome.final_state, outcome.reason_code) == ("data_gap", "source_empty")


@pytest.mark.parametrize("error", ["source_unavailable", "source_truncated", "source_query_failed"])
def test_incomplete_source_never_produces_clinical_result(error):
    outcome = evaluate(source_error=error)
    assert (outcome.final_state, outcome.reason_code) == ("data_gap", error)


def test_discharge_title_is_not_death_and_shell_is_not_a_conflict():
    discharge = {"document_id":"O1", "document_title":"出院记录", "record_content":"出院正文"}
    outcome = evaluate([], death_time=None, discharge_rows=[discharge])
    assert outcome.final_state == "not_applicable"
    assert evaluate(discharge_rows=[{"document_title":"", "record_content":""}]).final_state == "compliant"


@pytest.mark.parametrize("title", ["死亡病例讨论记录", "出院前查房", "死亡记录（PDF待核对）"])
def test_related_or_unapproved_title_is_not_used(title):
    assert evaluate([row(document_title=title)]).final_state == "data_gap"


def test_actual_two_terminal_types_are_a_source_conflict():
    outcome = evaluate(discharge_rows=[{"document_id":"O1", "document_title":"出院记录", "record_content":"出院正文"}])
    assert outcome.reason_code == "authoritative_time_conflict"


def test_absent_death_clock_is_not_replaced_by_completion():
    assert evaluate(death_time=None).reason_code == "authoritative_time_missing"


def test_date_only_death_field_cannot_be_promoted_to_midnight():
    assert evaluate([row(death_datetime="2026-01-01")]).reason_code == "authoritative_time_missing"


async def final_result(rows, *, rule="LX0609-04-02-09", discharge_rows=(), registration_rows=(),
                       registration_error=False, identity=("I", "P", "V"),
                       created_at="2026-01-04T12:00:00+08:00"):
    from app.services.luxian_0609.canonical_result_finalizer import finalize_luxian_0609_reduced_customer_result
    from app.services.luxian_0609.decision_binding import bind_and_reduce_luxian_0609_rule_decisions
    from app.services.luxian_0609.evidence_snapshot_provider import SnapshotSourceRows, build_luxian_0609_evidence_read_session
    from app.services.luxian_0609.native_extended_document_execution import execute_luxian_0609_native_extended_document_rules

    source_rows = {"death_record": rows, "discharge_record": discharge_rows, "inpat_registration": registration_rows}
    def reader(**kwargs):
        source = kwargs["source_key"]
        if source == "inpat_registration" and registration_error:
            from app.services.luxian_0609.source_evidence_reader import SourceEvidenceUnavailable
            raise SourceEvidenceUnavailable("synthetic_registration_unavailable")
        return SnapshotSourceRows.create(source_key=source, rows=source_rows.get(source, ()), truncated=False, limit_rows=100)
    session = build_luxian_0609_evidence_read_session(
        selected_rule_ids=(rule,), institute_id=identity[0], patient_id=identity[1], visit_id=identity[2], source_schema=None,
        created_at=created_at, evaluation_as_of_date=created_at[:10], row_reader=reader,
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
    result = finalize_luxian_0609_reduced_customer_result(
        decision=reduced, raw_customer_display_facts=dict(execution.customer_display_facts).get(rule),
        evidence_snapshot=session.snapshot, evidence_materials=session.materials,
    )
    return result


def saved_roundtrip(result, identity=("I", "P", "V")):
    import json
    from sqlalchemy import MetaData, create_engine
    from sqlalchemy.orm import Session
    import app.services.custom_qc_workspace_service as workspace
    from app.services.qc_workspace.canonical_result_store import CanonicalResultStore, envelope_item_from_rule_result

    table = workspace._record_result_envelopes_table().to_metadata(MetaData(), schema=None)
    engine = create_engine("sqlite://")
    table.metadata.create_all(engine)
    item = {**result, "institute_id":identity[0], "patient_id":identity[1], "visit_id":identity[2], "record_id":identity[2]}
    selected = {"root_job_id":"J", "institute_id":identity[0], "patient_id":identity[1], "visit_id":identity[2],
                "rule_set_key":"luxian_0609_qc_v1", "rule_set_version":"2026-06-09"}
    try:
        with Session(engine) as db:
            store = CanonicalResultStore(table)
            store.replace_for_job(db, job_row={"id":"J", "created_by":"synthetic-reviewer", "filters_json":json.dumps({
                "rule_set_key":"luxian_0609_qc_v1", "rule_set_version":"2026-06-09"})},
                items=[item], now=datetime(2026,1,4),
                projector=lambda raw: envelope_item_from_rule_result(raw,hmac_key="synthetic-death-test-key"),
                projection_key="synthetic-death-test-key")
            db.commit()
            return store.load_selected(db, **selected)["items"][0]
    finally:
        engine.dispose()


@pytest.mark.asyncio
@pytest.mark.parametrize("seconds,status", [(86400,"compliant"),(86401,"non_compliant")])
async def test_real_execution_binding_and_public_facts(seconds, status):
    result = await final_result([row(seconds, death_datetime=DEATH)])
    assert result["status"] == status
    assert result["customer_display_facts"]["elapsed_seconds"] == seconds
    loaded = saved_roundtrip(result)
    assert loaded["customer_display_facts"] == result["customer_display_facts"]
    assert loaded["status"] == status


@pytest.mark.asyncio
async def test_real_execution_does_not_require_discharge_document():
    assert (await final_result([row(death_datetime=DEATH)]))["status"] == "compliant"


@pytest.mark.asyncio
async def test_actual_gap_remains_data_gap_after_finalizer():
    result = await final_result([row(record_time=None, death_datetime=DEATH)])
    assert (result["status"], result["reason_code"]) == ("data_gap", "authoritative_time_missing")


@pytest.mark.asyncio
async def test_actual_ordinary_discharge_remains_not_applicable():
    result = await final_result([], discharge_rows=[{"document_id":"O1", "document_title":"出院记录", "record_content":"出院记录正文。"}])
    assert result["status"] == "not_applicable"


def test_acceptance_rule_keeps_existing_default_selection_unchanged():
    from app.services.luxian_0609.phase_scope import get_luxian_0609_acceptance_only_rule_ids
    assert "LX0609-04-02-09" in get_luxian_0609_acceptance_only_rule_ids()


@pytest.mark.asyncio
async def test_unavailable_registration_blocks_clinical_result():
    result = await final_result([row(death_datetime=DEATH)], registration_error=True)
    assert result["status"] == "data_gap"


@pytest.mark.asyncio
async def test_registration_date_only_is_not_promoted_to_midnight():
    result = await final_result([row()], registration_rows=[{"death_datetime": "2026-01-01"}])
    assert (result["status"], result["reason_code"]) == ("data_gap", "authoritative_time_missing")


@pytest.mark.asyncio
async def test_cross_source_same_id_keeps_selected_death_evidence():
    result = await final_result(
        [row(document_title="死亡病例讨论记录", record_content="未选中文书")],
        discharge_rows=[row(death_datetime=DEATH, record_content="实际死亡记录正文")],
    )
    assert result["status"] == "compliant"
    assert result["customer_display_facts"]["elapsed_seconds"] == 3600
    evidence = str(result["customer_evidence"])
    assert "实际死亡记录正文" in evidence
    assert "未选中文书" not in evidence


@pytest.mark.asyncio
async def test_conflicting_registration_clock_blocks_result():
    result = await final_result([row(death_datetime=DEATH)],
                                registration_rows=[{"death_datetime": DEATH + timedelta(hours=1)}])
    assert (result["status"], result["reason_code"]) == ("data_gap", "authoritative_time_conflict")


@pytest.mark.asyncio
async def test_same_source_same_id_different_versions_are_not_guess_located():
    result = await final_result([
        row(death_datetime=DEATH, record_content="较早版本正文"),
        row(90000, death_datetime=DEATH, record_content="最终选中版本正文"),
    ])
    assert (result["status"], result["reason_code"]) == ("data_gap", "authoritative_time_conflict")


@pytest.mark.asyncio
async def test_explicit_body_death_clock_is_used_without_structured_clock():
    result = await final_result([row(record_content="死亡时间：2026-01-01 08:00:00。")])
    assert result["status"] == "compliant"
    assert result["customer_display_facts"]["elapsed_seconds"] == 3600


@pytest.mark.parametrize("state", ["held", "version_review"])
def test_unapproved_pdf_versions_are_not_active_death_documents(state):
    assert evaluate([row(validation_material_state=state)]).final_state == "data_gap"
