from __future__ import annotations

import pytest

from app.services.luxian_0609 import native_surgery_document_execution as surgery_document
from app.services.luxian_0609.decision_binding import (
    bind_and_reduce_luxian_0609_rule_decisions,
)
from app.services.luxian_0609.evidence_snapshot_provider import (
    SnapshotSourceRows,
    build_luxian_0609_evidence_read_session,
)


def _reader_with_nonlocal_anesthesia(calls: list[str]):
    rows_by_source = {
        "anesthesia_record": (
            {
                "document_id": "anesthesia-038",
                "anesthesia_method": "全身麻醉",
                "record_time": "2026-09-01 08:00:00+08:00",
                "record_content": "全身麻醉记录单已完成。",
            },
        ),
        "consent_form": (
            {
                "document_id": "consent-038",
                "record_time": "2026-09-01 07:30:00+08:00",
                "record_content": "麻醉知情同意书。",
            },
        ),
    }

    def reader(**kwargs):
        source_key = kwargs["source_key"]
        calls.append(source_key)
        return SnapshotSourceRows.create(
            source_key=source_key,
            rows=rows_by_source.get(source_key, ()),
            truncated=False,
            limit_rows=50,
        )

    return reader


async def _run_038(*, selected_rule_ids: tuple[str, ...]):
    calls: list[str] = []
    session = build_luxian_0609_evidence_read_session(
        selected_rule_ids=selected_rule_ids,
        institute_id="safe-institute",
        patient_id="safe-patient",
        visit_id="safe-visit",
        source_schema=None,
        created_at="2026-09-01T12:00:00+08:00",
        row_reader=_reader_with_nonlocal_anesthesia(calls),
    )
    execution = await surgery_document.execute_luxian_0609_native_surgery_document_rules(
        rule_ids=selected_rule_ids,
        wrapper_rules=[],
        evidence_payload=None,
        llm_client=None,
        evidence_snapshot=session.snapshot,
        evidence_materials=session.materials,
        decision_rule_ids=selected_rule_ids,
    )
    decision = next(
        item for item in execution.decisions if item.rule_id == "LX0609-04-04-03"
    )
    reduced = bind_and_reduce_luxian_0609_rule_decisions(
        decisions=(decision,),
        expected_rule_ids=("LX0609-04-04-03",),
        snapshot=session.snapshot,
        evidence_materials=session.materials,
    )[0]
    return calls, reduced, dict(execution.customer_display_facts).get("LX0609-04-04-03")


@pytest.mark.asyncio
async def test_038_single_rule_reads_anesthesia_record_and_matches_batch_canonical_result():
    single_calls, single_reduced, single_facts = await _run_038(
        selected_rule_ids=("LX0609-04-04-03",)
    )
    batch_calls, batch_reduced, batch_facts = await _run_038(
        selected_rule_ids=("LX0609-11-02-01", "LX0609-04-04-03")
    )

    assert "anesthesia_record" in single_calls
    assert "anesthesia_record" in batch_calls
    assert single_reduced.final_state.value == batch_reduced.final_state.value == "compliant"
    assert single_reduced.reason_code == batch_reduced.reason_code == "requirement_satisfied"
    assert single_facts == batch_facts == {
        "verification_kind": "anesthesia_record_present",
        "performed_anesthesia_confirmed": True,
        "checked_sources": ["anesthesia_record"],
    }
