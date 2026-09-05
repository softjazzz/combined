from __future__ import annotations

import pytest

from app.services.luxian_0609.evidence_material import Luxian0609EvidenceMaterialStore
from test_luxian_0609_basic_timeliness_evidence_freeze import (
    _execute_and_aggregate,
    _multi_document_session,
)


@pytest.mark.parametrize(
    ("rule_id", "source_key"),
    (
        ("LX0609-001", "admission_record"),
        ("LX0609-002", "first_course_record"),
        ("LX0609-005", "daily_course_record"),
        ("LX0609-006", "senior_course_record"),
    ),
)
def test_selected_row_reference_failure_is_technical_and_not_customer_fact(
    monkeypatch, rule_id, source_key
):
    session = _multi_document_session((rule_id,))
    original_document_rows = Luxian0609EvidenceMaterialStore.document_rows

    def fail_selected_row(self, actual_source_key, *, snapshot):
        if actual_source_key == source_key:
            raise ValueError("forced selected-row binding failure")
        return original_document_rows(self, actual_source_key, snapshot=snapshot)

    monkeypatch.setattr(
        Luxian0609EvidenceMaterialStore,
        "document_rows",
        fail_selected_row,
    )

    execution, reduced, results = _execute_and_aggregate(session, (rule_id,))

    assert execution.decisions[0].reason_code == "snapshot_mismatch"
    assert execution.customer_display_facts == ()
    assert reduced[0].reason_code == "snapshot_mismatch"
    assert results[0]["status"] == "technical_error"
    assert "已确认" not in results[0]["findings"]
