from __future__ import annotations

import importlib.util
import copy
from pathlib import Path

import pytest

from scripts.build_luxian_0609_golden_ledger import (
    build_candidate_ledger,
    promote_candidate_ledger,
)


SCRIPT_PATH = (
    Path(__file__).resolve().parents[2]
    / "scripts"
    / "run_luxian_0609_golden_gate.py"
)
spec = importlib.util.spec_from_file_location(
    "run_luxian_0609_golden_gate",
    SCRIPT_PATH,
)
assert spec is not None
golden_gate = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(golden_gate)


def test_missing_accepted_ledger_is_explicitly_blocked() -> None:
    summary, exit_code = golden_gate.run_luxian_0609_golden_gate(
        ledger=None,
        run_batches=[],
    )

    assert exit_code == 3
    assert summary == {
        "schema_version": "lx0609-golden-gate-v1",
        "passed": False,
        "exit_code": 3,
        "status": "blocked",
        "accepted_count": 0,
        "deterministic": {},
        "semantic": {},
        "failures": [
            {
                "gate": "accepted_ledger",
                "failure_kind": "missing_accepted_ledger",
            }
        ],
    }


def _api_batch(*, state: str = "non_compliant") -> dict[str, object]:
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
                            "status": state,
                            "metadata": {"reason_code": "deadline_exceeded"},
                            "evidence_items": [
                                {
                                    "evidence_attestation": "c" * 64,
                                }
                            ],
                        }
                    ],
                    "metrics": {"llm_call_count": 0, "total_tokens": 0},
                },
            }
        ],
    }


def _ledger(*, decision_kind: str = "deterministic") -> dict[str, object]:
    candidate = build_candidate_ledger(
        _api_batch(),
        candidate_version="candidate20-v1",
        generated_at="2026-07-17T10:00:00Z",
    )
    row = candidate["rows"][0]
    review = {
        "candidate_digest": candidate["candidate_digest"],
        "case_label": row["case_label"],
        "selector_digest": row["selector_digest"],
        "rule_id": row["rule_id"],
        "decision_kind": decision_kind,
        "expected_state": row["observed_state"],
        "expected_reason_code": row["observed_reason_code"],
        "evidence_ref_hashes": ";".join(row["evidence_ref_hashes"]),
        "reviewer_code": "REVIEWER-01",
        "accepted_at": "2026-07-17T10:30:00Z",
        "review_revision": "1",
        "review_status": "accepted",
    }
    return promote_candidate_ledger(
        candidate,
        [review],
        ledger_version="accepted20-v1",
        generated_at="2026-07-17T10:31:00Z",
    )


def _promoted_ledger_for_batch(
    batch: dict[str, object],
    *,
    decision_kind: str = "deterministic",
) -> dict[str, object]:
    candidate = build_candidate_ledger(
        batch,
        candidate_version="candidate20-v1",
        generated_at="2026-07-17T10:00:00Z",
    )
    reviews = [
        {
            "candidate_digest": candidate["candidate_digest"],
            "case_label": row["case_label"],
            "selector_digest": row["selector_digest"],
            "rule_id": row["rule_id"],
            "decision_kind": decision_kind,
            "expected_state": row["observed_state"],
            "expected_reason_code": row["observed_reason_code"],
            "evidence_ref_hashes": ";".join(row["evidence_ref_hashes"]),
            "reviewer_code": "REVIEWER-01",
            "accepted_at": "2026-07-17T10:30:00Z",
            "review_revision": "1",
            "review_status": "accepted",
        }
        for row in candidate["rows"]
    ]
    return promote_candidate_ledger(
        candidate,
        reviews,
        ledger_version="accepted20-v1",
        generated_at="2026-07-17T10:31:00Z",
    )


def test_deterministic_gate_requires_exact_state_reason_and_evidence_hash() -> None:
    summary, exit_code = golden_gate.run_luxian_0609_golden_gate(
        ledger=_ledger(),
        run_batches=[_api_batch()],
    )

    assert exit_code == 0
    assert summary["passed"] is True
    assert summary["status"] == "passed"
    assert summary["accepted_count"] == 1
    assert summary["deterministic"] == {
        "accepted_count": 1,
        "exact_count": 1,
        "exact_rate": 1.0,
    }
    assert summary["semantic"] == {"accepted_count": 0, "status": "not_applicable"}


@pytest.mark.parametrize(
    ("field", "value"),
    (
        ("selector_digest", "c" * 64),
        ("rule_set_digest", "d" * 64),
    ),
)
def test_gate_rejects_run_identity_that_differs_from_accepted_ledger(
    field: str,
    value: str,
) -> None:
    run = _api_batch()
    run[field] = value

    summary, exit_code = golden_gate.run_luxian_0609_golden_gate(
        ledger=_ledger(),
        run_batches=[run],
    )

    assert exit_code == 2
    assert summary["status"] == "configuration_error"
    assert summary["failures"] == [
        {
            "gate": "accepted_ledger",
            "failure_kind": "invalid_accepted_ledger_or_run",
        }
    ]


def _semantic_batch() -> dict[str, object]:
    batch = _api_batch(state="non_compliant")
    batch["cases"].append(
        {
            "case_label": "case-02",
            "response": {
                "schema_version": "lx0609-preproduction-runner-v1",
                "results": [
                    {
                        "rule_id": "LX0609-001",
                        "status": "compliant",
                        "metadata": {"reason_code": "deadline_exceeded"},
                        "evidence_items": [
                            {
                                "evidence_attestation": "d" * 64,
                            }
                        ],
                    }
                ],
                "metrics": {"llm_call_count": 1, "total_tokens": 10},
            },
        }
    )
    return batch


def _semantic_ledger() -> dict[str, object]:
    candidate = build_candidate_ledger(
        _semantic_batch(),
        candidate_version="candidate20-v1",
        generated_at="2026-07-17T10:00:00Z",
    )
    reviews = []
    for row in candidate["rows"]:
        reviews.append(
            {
                "candidate_digest": candidate["candidate_digest"],
                "case_label": row["case_label"],
                "selector_digest": row["selector_digest"],
                "rule_id": row["rule_id"],
                "decision_kind": "semantic",
                "expected_state": row["observed_state"],
                "expected_reason_code": row["observed_reason_code"],
                "evidence_ref_hashes": ";".join(row["evidence_ref_hashes"]),
                "reviewer_code": "REVIEWER-01",
                "accepted_at": "2026-07-17T10:30:00Z",
                "review_revision": "1",
                "review_status": "accepted",
            }
        )
    return promote_candidate_ledger(
        candidate,
        reviews,
        ledger_version="accepted20-v1",
        generated_at="2026-07-17T10:31:00Z",
    )


def test_semantic_gate_requires_three_stable_runs_and_meets_ppv_recall() -> None:
    batch = _semantic_batch()
    summary, exit_code = golden_gate.run_luxian_0609_golden_gate(
        ledger=_semantic_ledger(),
        run_batches=[batch, batch, batch],
    )

    assert exit_code == 0
    assert summary["semantic"] == {
        "accepted_count": 2,
        "stable_count": 2,
        "stability_rate": 1.0,
        "evidence_exact_count": 2,
        "true_positive": 1,
        "false_positive": 0,
        "false_negative": 0,
        "truth_positive": 1,
        "truth_negative": 1,
        "ppv": 1.0,
        "recall": 1.0,
        "ppv_min": 0.95,
        "recall_min": 0.9,
        "status": "passed",
    }


def test_semantic_gate_blocks_when_accepted_sample_lacks_negative() -> None:
    summary, exit_code = golden_gate.run_luxian_0609_golden_gate(
        ledger=_ledger(decision_kind="semantic"),
        run_batches=[_api_batch(), _api_batch(), _api_batch()],
    )

    assert exit_code == 3
    assert summary["status"] == "blocked"
    assert summary["semantic"]["status"] == "blocked"
    assert summary["failures"] == [
        {
            "gate": "semantic",
            "failure_kind": "insufficient_sample",
            "rule_id": "LX0609-001",
        }
    ]


def test_semantic_gate_fails_when_same_input_state_is_unstable() -> None:
    stable = _semantic_batch()
    unstable = copy.deepcopy(stable)
    unstable["cases"][0]["response"]["results"][0]["status"] = "compliant"

    summary, exit_code = golden_gate.run_luxian_0609_golden_gate(
        ledger=_semantic_ledger(),
        run_batches=[stable, stable, unstable],
    )

    assert exit_code == 1
    assert summary["semantic"]["stable_count"] == 1
    assert {item["failure_kind"] for item in summary["failures"]} == {
        "unstable_state"
    }


def test_release_gate_blocks_an_incomplete_accepted_matrix() -> None:
    summary, exit_code = golden_gate.run_luxian_0609_golden_gate(
        ledger=_ledger(),
        run_batches=[_api_batch()],
        expected_sample_count=20,
        expected_rule_count=49,
    )

    assert exit_code == 3
    assert summary["status"] == "blocked"
    assert summary["accepted_count"] == 1
    assert summary["failures"] == [
        {"gate": "accepted_ledger", "failure_kind": "incomplete_accepted_matrix"}
    ]


def test_release_gate_requires_exact_canonical_rule_set_not_only_rule_count() -> None:
    batch = _api_batch()
    template = copy.deepcopy(batch["cases"][0]["response"]["results"][0])
    batch["cases"][0]["response"]["results"] = [
        {**copy.deepcopy(template), "rule_id": f"LX0609-{number:03d}"}
        for number in range(2, 51)
    ]
    candidate = build_candidate_ledger(
        batch,
        candidate_version="candidate20-v1",
        generated_at="2026-07-17T10:00:00Z",
    )
    reviews = [
        {
            "candidate_digest": candidate["candidate_digest"],
            "case_label": row["case_label"],
            "selector_digest": row["selector_digest"],
            "rule_id": row["rule_id"],
            "decision_kind": "deterministic",
            "expected_state": row["observed_state"],
            "expected_reason_code": row["observed_reason_code"],
            "evidence_ref_hashes": ";".join(row["evidence_ref_hashes"]),
            "reviewer_code": "REVIEWER-01",
            "accepted_at": "2026-07-17T10:30:00Z",
            "review_revision": "1",
            "review_status": "accepted",
        }
        for row in candidate["rows"]
    ]
    ledger = promote_candidate_ledger(
        candidate,
        reviews,
        ledger_version="accepted20-v1",
        generated_at="2026-07-17T10:31:00Z",
    )

    summary, exit_code = golden_gate.run_luxian_0609_golden_gate(
        ledger=ledger,
        run_batches=[batch],
        expected_sample_count=1,
        expected_rule_count=49,
    )

    assert exit_code == 3
    assert summary["status"] == "blocked"
    assert summary["failures"] == [
        {"gate": "accepted_ledger", "failure_kind": "incomplete_accepted_matrix"}
    ]


def test_each_run_requires_the_same_case_rule_matrix_as_the_ledger() -> None:
    accepted = _api_batch()
    template = copy.deepcopy(accepted["cases"][0]["response"]["results"][0])
    accepted["cases"][0]["response"]["results"] = [
        {**copy.deepcopy(template), "rule_id": f"LX0609-{number:03d}"}
        for number in range(1, 50)
    ]
    mismatched_run = copy.deepcopy(accepted)
    mismatched_run["cases"][0]["response"]["results"][-1]["rule_id"] = (
        "LX0609-050"
    )

    summary, exit_code = golden_gate.run_luxian_0609_golden_gate(
        ledger=_promoted_ledger_for_batch(accepted),
        run_batches=[mismatched_run],
        expected_sample_count=1,
        expected_rule_count=49,
    )

    assert exit_code == 2
    assert summary["status"] == "configuration_error"
    assert summary["failures"] == [
        {
            "gate": "accepted_ledger",
            "failure_kind": "invalid_accepted_ledger_or_run",
        }
    ]


@pytest.mark.parametrize(
    "mutation",
    (
        "extra_top_level",
        "ledger_version",
        "rule_set_digest",
        "selector_version",
        "selector_digest",
        "sample_count",
        "accepted_count",
        "parent_ledger_digest",
        "accepted_from_candidate_digest",
        "generated_at",
        "ledger_digest",
        "ledger_digest_whitespace",
        "extra_entry_field",
        "missing_entry_field",
        "case_label",
        "entry_selector_digest",
        "rule_id",
        "decision_kind",
        "expected_state",
        "expected_reason_code",
        "evidence_ref_hashes",
        "duplicate_evidence_ref_hashes",
        "reviewer_code",
        "accepted_at",
        "review_revision",
    ),
)
def test_gate_revalidates_every_accepted_ledger_field(
    mutation: str,
) -> None:
    ledger = copy.deepcopy(_ledger())
    entry = ledger["entries"][0]
    if mutation == "extra_top_level":
        ledger["unexpected"] = "safe"
    elif mutation == "ledger_version":
        ledger["ledger_version"] = " invalid "
    elif mutation == "rule_set_digest":
        ledger["rule_set_digest"] = "not-a-digest"
    elif mutation == "selector_version":
        ledger["selector_version"] = " invalid "
    elif mutation == "selector_digest":
        ledger["selector_digest"] = "not-a-digest"
    elif mutation == "sample_count":
        ledger["sample_count"] = True
    elif mutation == "accepted_count":
        ledger["accepted_count"] = True
    elif mutation == "parent_ledger_digest":
        ledger["parent_ledger_digest"] = "not-a-digest"
    elif mutation == "accepted_from_candidate_digest":
        ledger["accepted_from_candidate_digest"] = "not-a-digest"
    elif mutation == "generated_at":
        ledger["generated_at"] = "2026-07-17"
    elif mutation == "extra_entry_field":
        entry["unexpected"] = "safe"
    elif mutation == "missing_entry_field":
        entry.pop("reviewer_code")
    elif mutation == "case_label":
        entry["case_label"] = "case-private"
    elif mutation == "entry_selector_digest":
        entry["selector_digest"] = "c" * 64
    elif mutation == "rule_id":
        entry["rule_id"] = "LX0609-private"
    elif mutation == "decision_kind":
        entry["decision_kind"] = "guessed"
    elif mutation == "expected_state":
        entry["expected_state"] = "technical_error"
    elif mutation == "expected_reason_code":
        entry["expected_reason_code"] = " contains whitespace "
    elif mutation == "evidence_ref_hashes":
        entry["evidence_ref_hashes"] = ["not-a-digest"]
    elif mutation == "duplicate_evidence_ref_hashes":
        entry["evidence_ref_hashes"] = entry["evidence_ref_hashes"] * 2
    elif mutation == "reviewer_code":
        entry["reviewer_code"] = "private reviewer"
    elif mutation == "accepted_at":
        entry["accepted_at"] = "2026-07-17T10:30:00+08:00"
    elif mutation == "review_revision":
        entry["review_revision"] = 0
    material = {
        key: value for key, value in ledger.items() if key != "ledger_digest"
    }
    ledger["ledger_digest"] = golden_gate.canonical_digest(material)
    if mutation == "ledger_digest":
        ledger["ledger_digest"] = "not-a-digest"
    elif mutation == "ledger_digest_whitespace":
        ledger["ledger_digest"] = f" {ledger['ledger_digest']} "

    summary, exit_code = golden_gate.run_luxian_0609_golden_gate(
        ledger=ledger,
        run_batches=[_api_batch()],
    )

    assert exit_code == 2
    assert summary["status"] == "configuration_error"
    assert summary["failures"] == [
        {
            "gate": "accepted_ledger",
            "failure_kind": "invalid_accepted_ledger_or_run",
        }
    ]


def test_semantic_sample_threshold_is_enforced_per_rule_not_only_in_aggregate() -> None:
    batch = _semantic_batch()
    batch["cases"][0]["response"]["results"].append(
        {
            "rule_id": "LX0609-002",
            "status": "non_compliant",
            "metadata": {"reason_code": "deadline_exceeded"},
            "evidence_items": [
                {"evidence_attestation": "e" * 64}
            ],
        }
    )
    candidate = build_candidate_ledger(
        batch,
        candidate_version="candidate20-v1",
        generated_at="2026-07-17T10:00:00Z",
    )
    reviews = [
        {
            "candidate_digest": candidate["candidate_digest"],
            "case_label": row["case_label"],
            "selector_digest": row["selector_digest"],
            "rule_id": row["rule_id"],
            "decision_kind": "semantic",
            "expected_state": row["observed_state"],
            "expected_reason_code": row["observed_reason_code"],
            "evidence_ref_hashes": ";".join(row["evidence_ref_hashes"]),
            "reviewer_code": "REVIEWER-01",
            "accepted_at": "2026-07-17T10:30:00Z",
            "review_revision": "1",
            "review_status": "accepted",
        }
        for row in candidate["rows"]
    ]
    ledger = promote_candidate_ledger(
        candidate,
        reviews,
        ledger_version="accepted20-v1",
        generated_at="2026-07-17T10:31:00Z",
    )

    summary, exit_code = golden_gate.run_luxian_0609_golden_gate(
        ledger=ledger,
        run_batches=[batch, batch, batch],
    )

    assert exit_code == 3
    assert summary["failures"] == [
        {
            "gate": "semantic",
            "failure_kind": "insufficient_sample",
            "rule_id": "LX0609-002",
        }
    ]
