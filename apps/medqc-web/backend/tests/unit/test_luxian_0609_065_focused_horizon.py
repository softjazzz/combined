"""LX0609-065 单选入口必须在同一 Evidence Session 消费冻结终点。"""

from datetime import datetime

import pytest

from app.services.case_identity import CaseRef
from app.services.luxian_0609.decision_binding import (
    bind_and_reduce_luxian_0609_rule_decisions,
)
from app.services.luxian_0609.decision_reducer import CustomerFinalState
from app.services.luxian_0609.evidence_snapshot_provider import (
    build_luxian_0609_evidence_read_session,
)
from app.services.luxian_0609.native_extended_document_execution import (
    execute_luxian_0609_native_extended_document_rules,
)
from app.services.luxian_0609.source_evidence_reader import (
    CURRENT_VISIT_DISCHARGE_HORIZON_SOURCE_KEY,
    EVALUATION_HORIZON_SOURCE_KEY,
    SnapshotSourceRows,
)


@pytest.mark.asyncio
async def test_065_single_rule_entry_executes_with_known_surgery_end_and_frozen_horizon():
    coordinate = CaseRef("I-065", "P-065", "V-065")
    frozen = {
        "record_id": "V-065",
        "record_scene": "final",
        "resolution_status": "resolved",
        "evaluation_basis": "discharge_datetime",
        "admission_datetime": "2026-07-01 07:00:00",
        "discharge_datetime": "2026-07-05 12:00:00",
        "evaluation_horizon": "2026-07-05",
        **coordinate.as_dict(),
        "record_key": coordinate.as_key(),
    }

    def reader(**kwargs):
        source_key = kwargs["source_key"]
        rows_by_source = {
            "inpat_registration": (
                {"admission_datetime": "2026-07-01 07:00:00"},
            ),
            CURRENT_VISIT_DISCHARGE_HORIZON_SOURCE_KEY: (
                {"discharge_datetime": "2026-08-01 12:00:00"},
            ),
            "mr_surgery": (
                {
                    "surgery_code": "01.2400X013",
                    "surgery_name": "硬脑膜外血肿清除术",
                    "surgery_begin_datetime": datetime(2026, 7, 1, 8, 0),
                    "surgery_end_datetime": datetime(2026, 7, 1, 10, 0),
                    "surgeon": "张医生",
                },
            ),
            "senior_course_record": (
                {
                    "record_time": "2026-07-02 08:00:00",
                    "author_name": "李主任",
                },
            ),
            "daily_course_record": (
                {
                    "record_time": "2026-07-02 09:00:00",
                    "author_name": "王医生",
                },
            ),
        }
        return SnapshotSourceRows.create(
            source_key=source_key,
            rows=rows_by_source.get(source_key, ()),
            truncated=False,
            limit_rows=50,
        )

    session = build_luxian_0609_evidence_read_session(
        selected_rule_ids=("LX0609-065",),
        institute_id=coordinate.institute_id,
        patient_id=coordinate.patient_id,
        visit_id=coordinate.visit_id,
        source_schema=None,
        created_at="2026-09-10T12:00:00+08:00",
        evaluation_as_of_date="2026-09-10",
        evaluation_horizon_policy="authoritative_discharge",
        evaluation_horizon_snapshot=frozen,
        row_reader=reader,
    )
    horizon = session.materials.rows(EVALUATION_HORIZON_SOURCE_KEY)
    assert horizon[0]["horizon_datetime"] == "2026-07-05T12:00:00"

    execution = await execute_luxian_0609_native_extended_document_rules(
        rule_ids=("LX0609-065",),
        decision_rule_ids=("LX0609-065",),
        evidence_snapshot=session.snapshot,
        evidence_materials=session.materials,
    )
    reduced = bind_and_reduce_luxian_0609_rule_decisions(
        decisions=execution.decisions,
        expected_rule_ids=("LX0609-065",),
        snapshot=session.snapshot,
        evidence_materials=session.materials,
    )[0]

    assert reduced.final_state is CustomerFinalState.COMPLIANT
    assert reduced.reason_code == "requirement_satisfied"
    assert execution.llm_call_count == execution.total_tokens == 0
