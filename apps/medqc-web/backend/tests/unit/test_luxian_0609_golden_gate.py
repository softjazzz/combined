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
        candidate=None,
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


def _runtime_manifest(*, git_head: str | None = None) -> dict[str, object]:
    resolved_git_head = git_head or golden_gate.current_git_head()
    return {
        "schema_version": "lx0609-runtime-manifest-v1",
        "generated_at": "2026-07-24T00:00:00Z",
        "git_head": resolved_git_head,
        "customer_rule_count": 49,
        "flags": {},
        "rule_set": {
            "key": "luxian_0609_qc_v1",
            "version": "2026-06-09",
            "rule_count": 49,
            "rule_ids": [f"LX0609-{index:03d}" for index in range(1, 50)],
        },
        "runtime": {},
        "rules": [],
    }


def _run_v2_gate(**kwargs):
    manifest = _runtime_manifest()
    kwargs.setdefault("runtime_manifest", manifest)
    return golden_gate.run_luxian_0609_golden_gate(**kwargs)


def _candidate(
    batch: dict[str, object] | None = None,
) -> dict[str, object]:
    return build_candidate_ledger(
        batch or _api_batch(),
        candidate_version="candidate20-v1",
        generated_at="2026-07-17T10:00:00Z",
    )


def _ledger(*, decision_kind: str = "deterministic") -> dict[str, object]:
    candidate = _candidate()
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


def _v2_batch(
    *,
    state: str = "non_compliant",
    total_tokens: int = 0,
) -> dict[str, object]:
    batch = _api_batch(state=state)
    batch.update(
        {
            "git_head": golden_gate.current_git_head(),
            "policy_version": "2026-06-09",
            "runtime_manifest_hash": golden_gate.runtime_manifest_hash(
                _runtime_manifest()
            ),
            "sample_type": "real",
        }
    )
    case = batch["cases"][0]
    case["coordinate_hash"] = "f" * 64
    result = case["response"]["results"][0]
    result["metadata"].update(
        {
            "executor_type": "program",
            "prompt_tokens": total_tokens,
            "completion_tokens": 0,
            "total_tokens": total_tokens,
        }
    )
    result["evidence_source_types"] = ["daily_course_record"]
    return batch


def _v2_candidate_and_ledger(
    *,
    total_tokens: int = 0,
) -> tuple[dict[str, object], dict[str, object], dict[str, object]]:
    batch = _v2_batch(total_tokens=total_tokens)
    candidate = build_candidate_ledger(
        batch,
        candidate_version="candidate20-v2",
        generated_at="2026-07-24T00:00:00Z",
    )
    row = candidate["rows"][0]
    review = {
        "candidate_digest": candidate["candidate_digest"],
        "case_label": row["case_label"],
        "selector_digest": row["selector_digest"],
        "rule_id": row["rule_id"],
        "decision_kind": row["decision_kind"],
        "expected_state": row["observed_state"],
        "expected_reason_code": row["observed_reason_code"],
        "evidence_ref_hashes": ";".join(row["evidence_ref_hashes"]),
        "reviewer_code": "REVIEWER-01",
        "accepted_at": "2026-07-24T00:05:00Z",
        "review_revision": "1",
        "review_status": "accepted",
    }
    ledger = promote_candidate_ledger(
        candidate,
        [review],
        ledger_version="accepted20-v2",
        generated_at="2026-07-24T00:06:00Z",
    )
    return batch, candidate, ledger


def test_v2_gate_reports_separate_quality_buckets_and_real_denominator() -> None:
    batch, candidate, ledger = _v2_candidate_and_ledger()
    summary, exit_code = _run_v2_gate(
        ledger=ledger,
        candidate=candidate,
        run_batches=[batch],
    )

    assert exit_code == 0
    assert summary["quality"]["real_accuracy_denominator"] == 1
    assert summary["quality"]["definite_agreement"] == 1.0
    assert summary["quality"]["data_gap_count"] == 0
    assert summary["quality"]["evaluation_unknown_ai_suggestion_count"] == 0
    assert summary["quality"]["technical_error_rate"] == 0.0
    assert summary["quality"]["per_rule_sample_counts"]["LX0609-001"] == {
        "positive": 1,
        "negative": 0,
        "boundary": 0,
        "real": 1,
        "synthetic": 0,
    }


def test_v2_gate_rejects_runtime_identity_drift_and_program_model_usage() -> None:
    batch, candidate, ledger = _v2_candidate_and_ledger()
    stale = copy.deepcopy(batch)
    stale["git_head"] = "a" * 40
    summary, exit_code = _run_v2_gate(
        ledger=ledger,
        candidate=candidate,
        run_batches=[stale],
    )
    assert exit_code == golden_gate.EXIT_CONFIGURATION_ERROR
    assert summary["failures"][0]["failure_kind"] == "runtime_identity_mismatch"

    token_batch, token_candidate, token_ledger = _v2_candidate_and_ledger(
        total_tokens=1
    )
    summary, exit_code = _run_v2_gate(
        ledger=token_ledger,
        candidate=token_candidate,
        run_batches=[token_batch],
    )
    assert exit_code == golden_gate.EXIT_QUALITY_FAILURE
    assert any(
        item["failure_kind"] == "program_rule_used_model"
        for item in summary["failures"]
    )


def test_v2_release_gate_requires_current_runtime_identity() -> None:
    batch, candidate, ledger = _v2_candidate_and_ledger()

    summary, exit_code = golden_gate.run_luxian_0609_golden_gate(
        ledger=ledger,
        candidate=candidate,
        run_batches=[batch],
    )
    assert exit_code == golden_gate.EXIT_BLOCKED
    assert summary["failures"][0]["failure_kind"] == "missing_current_runtime_manifest"

    stale_batch = _v2_batch()
    stale_batch["runtime_manifest_hash"] = "a" * 64
    stale_candidate = build_candidate_ledger(
        stale_batch,
        candidate_version="candidate20-v2",
        generated_at="2026-07-24T00:00:00Z",
    )
    stale_row = stale_candidate["rows"][0]
    stale_ledger = promote_candidate_ledger(
        stale_candidate,
        [
            {
                "candidate_digest": stale_candidate["candidate_digest"],
                "case_label": stale_row["case_label"],
                "selector_digest": stale_row["selector_digest"],
                "rule_id": stale_row["rule_id"],
                "decision_kind": stale_row["decision_kind"],
                "expected_state": stale_row["observed_state"],
                "expected_reason_code": stale_row["observed_reason_code"],
                "evidence_ref_hashes": ";".join(stale_row["evidence_ref_hashes"]),
                "reviewer_code": "REVIEWER-01",
                "accepted_at": "2026-07-24T00:05:00Z",
                "review_revision": "1",
                "review_status": "accepted",
            }
        ],
        ledger_version="accepted20-v2",
        generated_at="2026-07-24T00:06:00Z",
    )
    summary, exit_code = _run_v2_gate(
        ledger=stale_ledger,
        candidate=stale_candidate,
        run_batches=[stale_batch],
    )
    assert exit_code == golden_gate.EXIT_CONFIGURATION_ERROR
    assert summary["failures"][0]["failure_kind"] == "stale_release_artifacts"


def test_v2_accepted_classification_must_match_candidate() -> None:
    batch, candidate, ledger = _v2_candidate_and_ledger()
    tampered = copy.deepcopy(ledger)
    tampered["entries"][0]["sample_type"] = "synthetic"
    tampered["ledger_digest"] = golden_gate.canonical_digest(
        {key: value for key, value in tampered.items() if key != "ledger_digest"}
    )

    summary, exit_code = _run_v2_gate(
        ledger=tampered,
        candidate=candidate,
        run_batches=[batch],
    )
    assert exit_code == golden_gate.EXIT_CONFIGURATION_ERROR
    assert (
        summary["failures"][0]["failure_kind"]
        == "accepted_candidate_classification_mismatch"
    )


def test_v2_gate_excludes_synthetic_rows_from_real_accuracy_denominator() -> None:
    batch = _v2_batch()
    synthetic_case = copy.deepcopy(batch["cases"][0])
    synthetic_case["case_label"] = "case-02"
    synthetic_case["coordinate_hash"] = "9" * 64
    synthetic_case["sample_type"] = "synthetic"
    synthetic_case["response"]["results"][0]["evidence_items"][0][
        "evidence_attestation"
    ] = "8" * 64
    batch["cases"].append(synthetic_case)
    candidate = build_candidate_ledger(
        batch,
        candidate_version="candidate20-v2",
        generated_at="2026-07-24T00:00:00Z",
    )
    reviews = []
    for row in candidate["rows"]:
        reviews.append(
            {
                "candidate_digest": candidate["candidate_digest"],
                "case_label": row["case_label"],
                "selector_digest": row["selector_digest"],
                "rule_id": row["rule_id"],
                "decision_kind": row["decision_kind"],
                "expected_state": row["observed_state"],
                "expected_reason_code": row["observed_reason_code"],
                "evidence_ref_hashes": ";".join(row["evidence_ref_hashes"]),
                "reviewer_code": "REVIEWER-01",
                "accepted_at": "2026-07-24T00:05:00Z",
                "review_revision": "1",
                "review_status": "accepted",
            }
        )
    ledger = promote_candidate_ledger(
        candidate,
        reviews,
        ledger_version="accepted20-v2",
        generated_at="2026-07-24T00:06:00Z",
    )

    summary, exit_code = _run_v2_gate(
        ledger=ledger,
        candidate=candidate,
        run_batches=[batch],
    )

    assert exit_code == 0
    assert summary["quality"]["real_accuracy_denominator"] == 1
    assert summary["quality"]["synthetic_count"] == 1
    assert summary["quality"]["synthetic_exact_count"] == 1


def test_v2_gate_reports_semantic_per_rule_token_budget_excess() -> None:
    batch = _v2_batch(total_tokens=9000)
    result = batch["cases"][0]["response"]["results"][0]
    result["metadata"]["executor_type"] = "llm"
    candidate = build_candidate_ledger(
        batch,
        candidate_version="candidate20-v2",
        generated_at="2026-07-24T00:00:00Z",
    )
    row = candidate["rows"][0]
    review = {
        "candidate_digest": candidate["candidate_digest"],
        "case_label": row["case_label"],
        "selector_digest": row["selector_digest"],
        "rule_id": row["rule_id"],
        "decision_kind": "semantic",
        "expected_state": row["observed_state"],
        "expected_reason_code": row["observed_reason_code"],
        "evidence_ref_hashes": ";".join(row["evidence_ref_hashes"]),
        "reviewer_code": "REVIEWER-01",
        "accepted_at": "2026-07-24T00:05:00Z",
        "review_revision": "1",
        "review_status": "accepted",
    }
    ledger = promote_candidate_ledger(
        candidate,
        [review],
        ledger_version="accepted20-v2",
        generated_at="2026-07-24T00:06:00Z",
    )
    summary, _exit_code = _run_v2_gate(
        ledger=ledger,
        candidate=candidate,
        run_batches=[batch, batch, batch],
    )
    assert any(
        item["failure_kind"] == "semantic_rule_token_budget_exceeded"
        for item in summary["failures"]
    )


def test_deterministic_gate_requires_exact_state_reason_and_evidence_hash() -> None:
    summary, exit_code = golden_gate._run_luxian_0609_golden_gate_diagnostic(
        ledger=_ledger(),
        candidate=_candidate(),
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


def test_v1_legacy_diagnostic_cannot_pass_formal_release_gate() -> None:
    summary, exit_code = golden_gate.run_luxian_0609_golden_gate(
        ledger=_ledger(),
        candidate=_candidate(),
        run_batches=[_api_batch()],
    )
    assert exit_code == golden_gate.EXIT_BLOCKED
    assert summary["passed"] is False
    assert summary["failures"][0]["failure_kind"] == "legacy_v1_not_release_eligible"


def test_accepted_ledger_requires_an_explicit_candidate_ledger() -> None:
    summary, exit_code = golden_gate.run_luxian_0609_golden_gate(
        ledger=_ledger(),
        candidate=None,
        run_batches=[_api_batch()],
    )

    assert exit_code == 3
    assert summary["status"] == "blocked"
    assert summary["failures"] == [
        {
            "gate": "accepted_ledger",
            "failure_kind": "missing_candidate_ledger",
        }
    ]


def test_gate_requires_candidate_digest_and_rows_to_bind_accepted_ledger_and_runs() -> None:
    batch = _api_batch()
    candidate = _candidate(batch)
    ledger = _ledger()

    summary, exit_code = golden_gate._run_luxian_0609_golden_gate_diagnostic(
        ledger=ledger,
        candidate=candidate,
        run_batches=[batch, batch, batch],
    )

    assert exit_code == 0
    assert summary["passed"] is True

    digest_tampered = copy.deepcopy(ledger)
    digest_tampered["accepted_from_candidate_digest"] = "f" * 64
    digest_material = {
        key: value
        for key, value in digest_tampered.items()
        if key != "ledger_digest"
    }
    digest_tampered["ledger_digest"] = golden_gate.canonical_digest(
        digest_material
    )
    summary, exit_code = golden_gate._run_luxian_0609_golden_gate_diagnostic(
        ledger=digest_tampered,
        candidate=candidate,
        run_batches=[batch, batch, batch],
    )
    assert exit_code == 2
    assert summary["status"] == "configuration_error"
    assert summary["failures"] == [
        {
            "gate": "accepted_ledger",
            "failure_kind": "invalid_candidate_ledger_or_run",
        }
    ]

    candidate_tampered = copy.deepcopy(candidate)
    candidate_tampered["rows"][0]["observed_reason_code"] = "other_safe_reason"
    candidate_material = {
        key: value
        for key, value in candidate_tampered.items()
        if key != "candidate_digest"
    }
    candidate_tampered["candidate_digest"] = golden_gate.canonical_digest(
        candidate_material
    )
    summary, exit_code = golden_gate._run_luxian_0609_golden_gate_diagnostic(
        ledger=ledger,
        candidate=candidate_tampered,
        run_batches=[batch, batch, batch],
    )
    assert exit_code == 2
    assert summary["status"] == "configuration_error"
    assert summary["failures"] == [
        {
            "gate": "accepted_ledger",
            "failure_kind": "invalid_candidate_ledger_or_run",
        }
    ]


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

    summary, exit_code = golden_gate._run_luxian_0609_golden_gate_diagnostic(
        ledger=_ledger(),
        candidate=_candidate(),
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
    summary, exit_code = golden_gate._run_luxian_0609_golden_gate_diagnostic(
        ledger=_semantic_ledger(),
        candidate=_candidate(batch),
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
    summary, exit_code = golden_gate._run_luxian_0609_golden_gate_diagnostic(
        ledger=_ledger(decision_kind="semantic"),
        candidate=_candidate(),
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


def test_semantic_gate_fails_when_baseline_matches_candidate_but_third_run_is_unstable() -> None:
    stable = _semantic_batch()
    unstable = copy.deepcopy(stable)
    unstable["cases"][0]["response"]["results"][0]["status"] = "compliant"

    summary, exit_code = golden_gate._run_luxian_0609_golden_gate_diagnostic(
        ledger=_semantic_ledger(),
        candidate=_candidate(stable),
        run_batches=[stable, stable, unstable],
    )

    assert exit_code == 1
    assert summary["status"] == "failed"
    assert summary["semantic"]["stable_count"] == 1
    assert {item["failure_kind"] for item in summary["failures"]} == {
        "unstable_state"
    }


def test_release_gate_blocks_an_incomplete_accepted_matrix() -> None:
    summary, exit_code = golden_gate._run_luxian_0609_golden_gate_diagnostic(
        ledger=_ledger(),
        candidate=_candidate(),
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

    summary, exit_code = golden_gate._run_luxian_0609_golden_gate_diagnostic(
        ledger=ledger,
        candidate=candidate,
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

    summary, exit_code = golden_gate._run_luxian_0609_golden_gate_diagnostic(
        ledger=_promoted_ledger_for_batch(accepted),
        candidate=_candidate(accepted),
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

    summary, exit_code = golden_gate._run_luxian_0609_golden_gate_diagnostic(
        ledger=ledger,
        candidate=_candidate(),
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

    summary, exit_code = golden_gate._run_luxian_0609_golden_gate_diagnostic(
        ledger=ledger,
        candidate=candidate,
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
