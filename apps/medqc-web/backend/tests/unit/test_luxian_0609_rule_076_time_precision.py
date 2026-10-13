"""076 死亡时刻精度保护：日期不能自动补为午夜。"""
import asyncio
from datetime import date, datetime
import json

import pytest
import sqlalchemy as sa
from sqlalchemy.orm import Session

from app.services.luxian_0609.extended_document.rule_076 import evaluate_rule_076
from app.services.luxian_0609.evidence_snapshot_provider import (
    SnapshotSourceRows, build_luxian_0609_evidence_read_session,
)
from app.services.luxian_0609.native_extended_document_execution import (
    execute_luxian_0609_native_extended_document_rules,
)
from app.services.luxian_0609.decision_binding import bind_and_reduce_luxian_0609_rule_decisions
from app.services.luxian_0609_result_aggregator import aggregate_luxian_0609_results
from app.services.luxian_0609_rule_catalog import get_luxian_0609_rule
from app.services.qc_workspace.canonical_result_store import (
    CanonicalResultStore, envelope_item_from_rule_result,
)

RULE_ID = "LX0609-04-02-08"


def test_date_only_death_time_is_missing_the_concrete_clock():
    outcome = evaluate_rule_076(
        death_state="present",
        death_rows=(("d" * 64, {"death_time": "2026-07-01", "record_content": "死亡时间仅填写日期。"}),),
    )
    assert outcome.status == "non_compliant"
    assert outcome.reason_code == "defect_proven"
    assert outcome.criterion_results[0].actual_value is False


@pytest.mark.parametrize("field", ["death_time", "death_datetime"])
@pytest.mark.parametrize("value", [
    "2026-07-01", "2026/07/01", "2026年07月01日", date(2026, 7, 1),
    "2026-07-01T00", "2026-07-01 25:00", "2026-02-30 03:45:00",
])
def test_date_hour_only_or_invalid_death_fields_do_not_prove_a_concrete_time(field, value):
    outcome = evaluate_rule_076(
        death_state="present",
        death_rows=(("d" * 64, {field: value, "record_content": "经抢救无效死亡。"}),),
    )
    assert outcome.status == "non_compliant"
    assert outcome.criterion_results[0].actual_value is False


@pytest.mark.parametrize("field", ["death_time", "death_datetime"])
@pytest.mark.parametrize("value", [
    "2026-07-01 00:00", "2026-07-01 00:00:00", datetime(2026, 7, 1, 0, 0),
    "2026-07-01T03:45:00", "2026-07-01t03:45:00", "2026-07-01 03:45:00+08:00",
    "2026/07/01 03:45:00", "2026.07.01 03:45:00", "2026年07月01日 03时45分",
])
def test_explicit_midnight_and_existing_concrete_time_formats_remain_complete(field, value):
    outcome = evaluate_rule_076(
        death_state="present", death_rows=(("d" * 64, {field: value}),),
    )
    assert outcome.status == "compliant"
    assert outcome.criterion_results[0].actual_value is True


@pytest.mark.parametrize("body", [
    "死亡时间：2026-07-01 00:00。",
    "患者于2026年07月01日 03时45分宣告临床死亡。",
])
def test_date_only_field_can_use_an_existing_concrete_death_time_in_same_record(body):
    outcome = evaluate_rule_076(
        death_state="present",
        death_rows=(("d" * 64, {"death_time": "2026-07-01", "record_content": body}),),
    )
    assert outcome.status == "compliant"


def test_date_only_field_without_readable_body_stays_a_source_gap():
    outcome = evaluate_rule_076(
        death_state="present", death_rows=(("d" * 64, {"death_time": "2026-07-01"}),),
    )
    assert (outcome.status, outcome.reason_code) == ("data_gap", "source_empty")


class _NoModel:
    async def generate(self, *args, **kwargs):
        raise AssertionError("076 must not call a model")


async def _canonical_death_result(death_row, registration_rows):
    rows = {"death_record": [death_row], "inpat_registration": registration_rows}

    def reader(**kwargs):
        key = kwargs["source_key"]
        return SnapshotSourceRows.create(
            source_key=key, rows=rows.get(key, []), truncated=False, limit_rows=50,
        )

    session = build_luxian_0609_evidence_read_session(
        selected_rule_ids=(RULE_ID,), institute_id="076-I", patient_id="076-P",
        visit_id="076-V", source_schema=None, created_at="2026-10-07T00:00:00",
        row_reader=reader,
    )
    execution = await execute_luxian_0609_native_extended_document_rules(
        rule_ids=(RULE_ID,), decision_rule_ids=(RULE_ID,),
        evidence_snapshot=session.snapshot, evidence_materials=session.materials,
        llm_client=_NoModel(),
    )
    decisions = bind_and_reduce_luxian_0609_rule_decisions(
        decisions=execution.decisions, expected_rule_ids=(RULE_ID,),
        snapshot=session.snapshot, evidence_materials=session.materials,
    )
    canonical = aggregate_luxian_0609_results(
        wrapper_rules=[get_luxian_0609_rule(RULE_ID)], execution_results=[],
        reduced_decisions=decisions, customer_display_facts=execution.customer_display_facts,
        audit_context={"evidence_snapshot": session.snapshot, "evidence_materials": session.materials},
    )[0]
    assert execution.llm_call_count == execution.total_tokens == 0
    assert canonical["status"] == decisions[0].final_state.value
    assert canonical["reason_code"] == decisions[0].reason_code
    return canonical


def _sqlite_new_session_roundtrip(canonical, path):
    # 独立SQLite表仅为CanonicalResultStore公共接口提供测试存储。
    table = sa.Table(
        "luxian_0609_record_result_envelopes", sa.MetaData(),
        sa.Column("id", sa.String(36), primary_key=True),
        *[sa.Column(key, sa.String(128), nullable=False) for key in (
            "job_id", "root_job_id", "created_by", "record_id", "institute_id",
            "patient_id", "visit_id", "rule_set_key", "rule_set_version",
        )],
        sa.Column("envelope_json", sa.Text, nullable=False),
        sa.Column("result_count", sa.Integer, nullable=False),
        sa.Column("created_at", sa.DateTime, nullable=False),
        sa.Column("updated_at", sa.DateTime, nullable=False),
    )
    store = CanonicalResultStore(table)
    item = {**canonical, "record_id": "076-V", "visit_id": "076-V",
            "institute_id": "076-I", "patient_id": "076-P"}
    key = "076-time-precision-test-key"
    projected = envelope_item_from_rule_result(item, hmac_key=key)
    engine = sa.create_engine("sqlite:///" + str(path))
    try:
        table.metadata.create_all(engine)
        with Session(engine) as write_session:
            store.replace_for_job(
                write_session,
                job_row={"id": "076-J", "created_by": "076-tester",
                         "filters_json": json.dumps({"rule_set_key": "luxian_0609_qc_v1",
                                                     "rule_set_version": "2026-06-09",
                                                     "rule_ids": [RULE_ID]})},
                items=[item], now=datetime(2026, 10, 7), projection_key=key,
                projector=lambda value: envelope_item_from_rule_result(value, hmac_key=key),
            )
            write_session.commit()
    finally:
        engine.dispose()
    # 写Session关闭、写引擎dispose后另建引擎与Session，不能用写连接内存确认。
    read_engine = sa.create_engine("sqlite:///" + str(path))
    try:
        with Session(read_engine) as read_session:
            envelope = store.load_selected(
                read_session, root_job_id="076-J", institute_id="076-I",
                patient_id="076-P", visit_id="076-V", rule_set_key="luxian_0609_qc_v1",
                rule_set_version="2026-06-09",
            )
    finally:
        read_engine.dispose()
    assert len(envelope["items"]) == 1
    loaded = envelope["items"][0]
    for field in (
        "status", "reason_code", "is_compliant", "criterion_results",
        "customer_evidence", "findings", "suggestion", "customer_display_facts",
    ):
        assert loaded.get(field) == projected.get(field)
    return loaded


@pytest.mark.parametrize("death_row,registration_rows,expected,criterion_state", [
    ({"death_time": "2026-07-01", "record_content": "死亡时间：2026-07-01。"},
     [{"patient_status": "死亡"}], "non_compliant", "failed"),
    ({"death_time": "2026-07-01 00:00:00"},
     [{"patient_status": "死亡"}], "compliant", "passed"),
    ({"death_time": "2026-07-01 25:00", "record_content": "经抢救无效死亡。"},
     [{"patient_status": "死亡"}], "non_compliant", "failed"),
    ({"death_time": "2026-07-01"}, [{"patient_status": "死亡"}], "data_gap", None),
    ({"death_time": "2026-07-01 03:45:00"},
     [{"death_datetime": "2026-07-01 04:45:00"}], "data_gap", None),
    ({"death_time": "2026-07-01", "record_content": "死亡时间：2026-07-01。"},
     [{"death_datetime": "2026-07-01 03:45:00"}], "data_gap", None),
])
def test_time_precision_results_survive_formal_finalizer_and_sqlite_new_session(
    tmp_path, death_row, registration_rows, expected, criterion_state,
):
    canonical = asyncio.run(_canonical_death_result(
        {**death_row, "document_id": "death-076", "record_time": "2026-07-01 10:00:00"},
        registration_rows,
    ))
    assert canonical["status"] == expected
    if criterion_state is not None:
        assert canonical["criterion_results"][0]["status"] == criterion_state
        assert canonical["criterion_results"][0]["source_fact"] == "death_record.death_time"
    else:
        assert not canonical.get("criterion_results")
    loaded = _sqlite_new_session_roundtrip(canonical, tmp_path / "076-result.sqlite")
    assert loaded["status"] == expected
