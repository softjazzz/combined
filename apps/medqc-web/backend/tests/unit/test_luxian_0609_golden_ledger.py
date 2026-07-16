from __future__ import annotations

import importlib.util
import csv
import json
from pathlib import Path

import pytest


SCRIPT_PATH = (
    Path(__file__).resolve().parents[2]
    / "scripts"
    / "build_luxian_0609_golden_ledger.py"
)
spec = importlib.util.spec_from_file_location(
    "build_luxian_0609_golden_ledger",
    SCRIPT_PATH,
)
assert spec is not None
ledger_builder = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(ledger_builder)


def _safe_api_batch(*, status: str = "non_compliant") -> dict[str, object]:
    return {
        "schema_version": "lx0609-golden-api-batch-v1",
        "selector_version": "fixed20-v1",
        "selector_digest": "a" * 64,
        "rule_set_digest": "b" * 64,
        "cases": [
            {
                "case_label": "case-01",
                "response": {
                    "schema_version": "lx0609-preproduction-runner-v1",
                    "results": [
                        {
                            "rule_id": "LX0609-001",
                            "status": status,
                            "metadata": {"reason_code": "deadline_exceeded"},
                            "evidence_items": [
                                {
                                    "source_table": "admission_record",
                                    "field_path": "record_time",
                                    "evidence_role": "deadline_evidence",
                                }
                            ],
                        }
                    ],
                    "metrics": {
                        "llm_call_count": 0,
                        "total_tokens": 0,
                    },
                },
            }
        ],
    }


def test_safe_api_dto_builds_candidate_without_promoting_observed_state() -> None:
    candidate = ledger_builder.build_candidate_ledger(
        _safe_api_batch(),
        candidate_version="candidate20-v1",
        generated_at="2026-07-17T10:00:00Z",
    )

    assert candidate["schema_version"] == "lx0609-golden-candidate-v1"
    assert candidate["candidate_count"] == 1
    assert candidate["candidate_digest"] == ledger_builder.canonical_digest(
        {key: value for key, value in candidate.items() if key != "candidate_digest"}
    )
    assert candidate["rows"] == [
        {
            "case_label": "case-01",
            "selector_digest": "a" * 64,
            "rule_id": "LX0609-001",
            "observed_state": "non_compliant",
            "observed_reason_code": "deadline_exceeded",
            "evidence_ref_hashes": candidate["rows"][0]["evidence_ref_hashes"],
            "review_status": "candidate",
        }
    ]
    assert len(candidate["rows"][0]["evidence_ref_hashes"]) == 1
    assert len(candidate["rows"][0]["evidence_ref_hashes"][0]) == 64
    assert "expected_state" not in candidate["rows"][0]


@pytest.mark.parametrize(
    ("forbidden_key", "forbidden_value"),
    [
        ("visit_id", "PRIVATE-VISIT-MARKER"),
        ("patient_name", "PRIVATE-NAME-MARKER"),
        ("medical_text", "PRIVATE-BODY-MARKER"),
        ("prompt", "PRIVATE-PROMPT-MARKER"),
        ("raw_response", "PRIVATE-RAW-MARKER"),
    ],
)
def test_candidate_builder_rejects_phi_or_internal_api_fields_without_echo(
    forbidden_key: str,
    forbidden_value: str,
) -> None:
    payload = _safe_api_batch()
    payload["cases"][0]["response"][forbidden_key] = forbidden_value

    with pytest.raises(ValueError) as raised:
        ledger_builder.build_candidate_ledger(
            payload,
            candidate_version="candidate20-v1",
            generated_at="2026-07-17T10:00:00Z",
        )

    assert str(raised.value) == "unsafe API DTO"
    assert forbidden_value not in repr(raised.value)


def _accepted_review(candidate: dict[str, object]) -> dict[str, str]:
    row = candidate["rows"][0]
    return {
        "candidate_digest": str(candidate["candidate_digest"]),
        "case_label": str(row["case_label"]),
        "selector_digest": str(row["selector_digest"]),
        "rule_id": str(row["rule_id"]),
        "decision_kind": "deterministic",
        "expected_state": "compliant",
        "expected_reason_code": "deadline_met",
        "evidence_ref_hashes": ";".join(row["evidence_ref_hashes"]),
        "reviewer_code": "REVIEWER-01",
        "accepted_at": "2026-07-17T10:30:00Z",
        "review_revision": "1",
        "review_status": "accepted",
    }


def test_promotion_requires_explicit_complete_human_review() -> None:
    candidate = ledger_builder.build_candidate_ledger(
        _safe_api_batch(),
        candidate_version="candidate20-v1",
        generated_at="2026-07-17T10:00:00Z",
    )
    review = _accepted_review(candidate)
    review["expected_state"] = ""

    with pytest.raises(ValueError, match="incomplete accepted review"):
        ledger_builder.promote_candidate_ledger(
            candidate,
            [review],
            ledger_version="accepted20-v1",
            generated_at="2026-07-17T10:31:00Z",
        )


def test_promotion_uses_human_expected_state_not_model_observed_state() -> None:
    candidate = ledger_builder.build_candidate_ledger(
        _safe_api_batch(status="non_compliant"),
        candidate_version="candidate20-v1",
        generated_at="2026-07-17T10:00:00Z",
    )
    ledger = ledger_builder.promote_candidate_ledger(
        candidate,
        [_accepted_review(candidate)],
        ledger_version="accepted20-v1",
        generated_at="2026-07-17T10:31:00Z",
    )

    assert ledger["schema_version"] == "lx0609-golden-ledger-v1"
    assert ledger["accepted_count"] == 1
    assert ledger["accepted_from_candidate_digest"] == candidate["candidate_digest"]
    assert ledger["entries"][0]["expected_state"] == "compliant"
    assert ledger["entries"][0]["expected_reason_code"] == "deadline_met"
    assert "observed_state" not in ledger["entries"][0]
    assert ledger["ledger_digest"] == ledger_builder.canonical_digest(
        {key: value for key, value in ledger.items() if key != "ledger_digest"}
    )


def test_schema_and_empty_review_template_are_safe_and_do_not_fake_acceptance() -> None:
    root = Path(__file__).resolve().parents[3]
    schema_path = (
        root
        / "docs"
        / "acceptance"
        / "lx0609-golden"
        / "lx0609-golden-ledger-v1.schema.json"
    )
    review_path = schema_path.with_name("review20-v1.csv")

    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    assert schema["properties"]["schema_version"]["const"] == (
        "lx0609-golden-ledger-v1"
    )
    assert schema["$defs"]["acceptedEntry"]["properties"][
        "expected_state"
    ]["enum"] == [
        "compliant",
        "non_compliant",
        "not_applicable",
        "data_gap",
        "evaluation_unknown",
    ]
    rendered = schema_path.read_text(encoding="utf-8").lower()
    for forbidden in ("visit_id", "patient_name", "medical_text", "record_content"):
        assert forbidden not in rendered

    with review_path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        assert list(reader) == []
        assert reader.fieldnames == [
            "candidate_digest",
            "case_label",
            "selector_digest",
            "rule_id",
            "decision_kind",
            "expected_state",
            "expected_reason_code",
            "evidence_ref_hashes",
            "reviewer_code",
            "accepted_at",
            "review_revision",
            "review_status",
        ]
