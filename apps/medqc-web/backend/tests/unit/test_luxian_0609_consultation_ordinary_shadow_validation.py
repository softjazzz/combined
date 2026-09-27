from __future__ import annotations

import json
from types import SimpleNamespace

from scripts import run_luxian_0609_consultation_ordinary_shadow_validation as shadow


def _result(*, rule_id: str, final_state: str, reason_code: str):
    return {
        "rule_id": rule_id,
        "metadata": {
            "source_state": final_state,
            "reason_code": reason_code,
        },
    }


def test_ledger_row_uses_strict_safe_allowlist_and_never_serializes_model_text():
    marker = "CONSULTATION_LEDGER_SECRET_20260722"
    capture = shadow._SafeStageCapture()
    capture.capture_response({
        "content": json.dumps({
            "episodes": [{
                "confidence": "high",
                "recommendations": [{
                    "action_type": "test",
                    "source_quote": marker,
                    "normalized_action": marker,
                }],
            }],
            "non_target_refs": [],
            "unresolved_refs": [],
        }, ensure_ascii=False),
    })
    rows = shadow.build_safe_ledger_rows(
        case_label="case-01",
        selector_fingerprint="a" * 64,
        results=(_result(
            rule_id="LX0609-03-01-01",
            final_state="evaluation_unknown",
            reason_code="semantic_output_unknown",
        ),),
        capture=capture,
        source_complete_keys=frozenset({
            "exam_item_report", "labtest_item_report", "daily_course_record", "senior_course_record",
        }),
        source_incomplete_keys=frozenset({"inpat_drug_order"}),
        llm_call_count=2,
        prompt_tokens=12,
        completion_tokens=4,
        total_tokens=16,
        latency_seconds=0.25,
    )

    assert len(rows) == 1
    assert set(rows[0]) == shadow.SAFE_LEDGER_FIELDS
    assert rows[0]["action_types"] == ["test"]
    assert rows[0]["execution_states"] == []
    assert marker not in json.dumps(rows, ensure_ascii=False)


def test_invalid_model_payload_yields_only_empty_enums_and_safe_reason():
    marker = "CONSULTATION_INVALID_SECRET_20260722"
    capture = shadow._SafeStageCapture()
    capture.capture_response({"content": marker})
    rows = shadow.build_safe_ledger_rows(
        case_label="case-02",
        selector_fingerprint="b" * 64,
        results=(_result(
            rule_id="LX0609-03-01-04",
            final_state="evaluation_unknown",
            reason_code="semantic_output_unknown",
        ),),
        capture=capture,
        source_complete_keys=frozenset(),
        source_incomplete_keys=frozenset(),
        llm_call_count=1,
        prompt_tokens=0,
        completion_tokens=0,
        total_tokens=0,
        latency_seconds=0.0,
    )

    assert rows[0]["action_types"] == []
    assert rows[0]["execution_states"] == []
    assert rows[0]["confidence"] == []
    assert marker not in json.dumps(rows, ensure_ascii=False)


def test_non_target_document_reason_is_preserved_in_safe_ledger():
    rows = shadow.build_safe_ledger_rows(
        case_label="case-03",
        selector_fingerprint="c" * 64,
        results=(_result(
            rule_id="LX0609-03-01-01",
            final_state="not_applicable",
            reason_code="non_target_document",
        ),),
        capture=shadow._SafeStageCapture(),
        source_complete_keys=frozenset(),
        source_incomplete_keys=frozenset(),
        llm_call_count=0,
        prompt_tokens=0,
        completion_tokens=0,
        total_tokens=0,
        latency_seconds=0.0,
    )

    assert rows[0]["reason_code"] == "non_target_document"
