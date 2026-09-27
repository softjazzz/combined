from __future__ import annotations

from app.services.luxian_0609.canonical_result_finalizer import (
    finalize_luxian_0609_executor_customer_display_facts,
)
from app.services.luxian_0609.death_document_result_mapping import (
    safe_death_document_customer_display_facts,
)


_TIMELY_051_FACTS = {
    "verification_kind": "death_discussion_timeliness_check",
    "death_time": "2026-08-01 08:00:00",
    "discussion_time": "2026-08-02 08:00:00",
    "threshold_hours": 168,
    "actual_interval_hours": 24.0,
}


def test_051_mapping_strips_private_document_selection_payload() -> None:
    raw = {
        **_TIMELY_051_FACTS,
        "source_document_refs": [
            {
                "source_type": "death_record",
                "source_document_id": "PRIVATE-DEATH-051",
            }
        ],
        "record_content": "PRIVATE_MEDICAL_BODY",
    }

    assert safe_death_document_customer_display_facts(
        rule_id="LX0609-09-02-01", raw=raw
    ) == _TIMELY_051_FACTS


def test_051_finalizer_preserves_boundary_overdue_state_after_display_rounding() -> None:
    facts = {
        **_TIMELY_051_FACTS,
        "actual_interval_hours": 168.0,
        "source_document_refs": [],
    }
    finalized, handled = finalize_luxian_0609_executor_customer_display_facts(
        result={
            "rule_id": "LX0609-09-02-01",
            "status": "non_compliant",
            "reason_code": "threshold_exceeded",
        },
        raw_facts=facts,
    )

    assert handled is True
    assert finalized["status"] == "non_compliant"
    assert finalized["customer_display_facts"] == {
        **_TIMELY_051_FACTS,
        "actual_interval_hours": 168.0,
    }


def test_060_finalizer_rejects_presence_status_conflict() -> None:
    facts = {
        "verification_kind": "death_record_presence_check",
        "death_confirmed": True,
        "death_time": "2026-08-01 08:00:00",
        "death_record_count": 1,
    }
    finalized, handled = finalize_luxian_0609_executor_customer_display_facts(
        result={
            "rule_id": "LX0609-04-02-06",
            "status": "non_compliant",
            "reason_code": "required_document_missing",
            "findings": "不应保留",
        },
        raw_facts=facts,
    )

    assert handled is True
    assert finalized["status"] == "technical_error"
    assert finalized["reason_code"] == "model_invalid_output"
    assert "findings" not in finalized
