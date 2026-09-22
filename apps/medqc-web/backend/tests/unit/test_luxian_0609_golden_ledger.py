from __future__ import annotations

import importlib.util
import csv
import json
from pathlib import Path

import jsonschema
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
                            "rule_id": "LX0609-01-01-01",
                            "status": status,
                            "metadata": {
                                "reason_code": "deadline_exceeded",
                                "executor_type": "program",
                            },
                            "evidence_items": [
                                {
                                    "evidence_attestation": "c" * 64,
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


def _v2_api_batch(
    *,
    status: str = "non_compliant",
    sample_type: str = "real",
) -> dict[str, object]:
    batch = _safe_api_batch(status=status)
    batch.update(
        {
            "git_head": "d" * 40,
            "policy_version": "2026-06-09",
            "runtime_manifest_hash": "e" * 64,
            "sample_type": sample_type,
        }
    )
    case = batch["cases"][0]
    case["coordinate_hash"] = "f" * 64
    result = case["response"]["results"][0]
    result["evidence_source_types"] = ["daily_course_record"]
    case["response"]["metrics"].update(
        {
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "total_tokens": 0,
            "usage_complete": True,
            "usage_error_reason": "",
            "unattributed_prompt_tokens": 0,
            "unattributed_completion_tokens": 0,
            "unattributed_total_tokens": 0,
            "api_time_seconds": 0.0,
            "usage_attributions": [
                {
                    "executor_key": "programmatic",
                    "llm_call_count": 0,
                    "prompt_tokens": 0,
                    "completion_tokens": 0,
                    "total_tokens": 0,
                    "covered_customer_rule_ids": ["LX0609-01-01-01"],
                    "latency_ms": 0.0,
                }
            ],
        }
    )
    return batch


def test_v2_candidate_and_accepted_ledger_bind_safe_runtime_identity() -> None:
    candidate = ledger_builder.build_candidate_ledger(
        _v2_api_batch(),
        candidate_version="candidate20-v2",
        generated_at="2026-07-24T00:00:00Z",
    )
    row = candidate["rows"][0]
    assert candidate["schema_version"] == "lx0609-golden-candidate-v2"
    assert row["safe_case_ref"] == "f" * 64
    assert row["sample_type"] == "real"
    assert row["evidence_source_types"] == ["daily_course_record"]
    assert row["manual_review_status"] == "candidate"
    assert row["policy_version"] == "2026-06-09"
    assert row["git_head"] == "d" * 40
    assert row["runtime_manifest_hash"] == "e" * 64

    review = ledger_builder.build_review_template_rows(candidate)[0]
    review.update(
        {
            "expected_state": "non_compliant",
            "expected_reason_code": "deadline_exceeded",
            "reviewer_code": "REVIEWER-01",
            "accepted_at": "2026-07-24T00:05:00Z",
            "review_revision": "1",
            "review_status": "accepted",
        }
    )
    ledger = ledger_builder.promote_candidate_ledger(
        candidate,
        [review],
        ledger_version="accepted20-v2",
        generated_at="2026-07-24T00:06:00Z",
    )
    accepted = ledger["entries"][0]
    assert ledger["schema_version"] == "lx0609-golden-ledger-v2"
    assert accepted["manual_review_status"] == "accepted"
    assert accepted["sample_type"] == "real"
    assert accepted["safe_case_ref"] == "f" * 64

    schema_path = (
        Path(__file__).resolve().parents[3]
        / "docs"
        / "acceptance"
        / "lx0609-golden"
        / "lx0609-golden-ledger-v2.schema.json"
    )
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    jsonschema.validate(ledger, schema)
    unsafe = json.loads(json.dumps(ledger))
    unsafe["entries"][0]["patient_name"] = "PRIVATE-MARKER"
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(unsafe, schema)


def test_v2_candidate_uses_family_coverage_once_and_ignores_result_token_metadata():
    batch = _v2_api_batch()
    response = batch["cases"][0]["response"]
    response["results"][0]["metadata"].update(
        {
            "prompt_tokens": 999,
            "completion_tokens": 999,
            "total_tokens": 1998,
        }
    )
    response["results"].append(
        {
            "rule_id": "LX0609-02-01-05",
            "status": "compliant",
            "metadata": {
                "reason_code": "daily_record_complete",
                "executor_type": "llm",
            },
            "evidence_items": [{"evidence_attestation": "1" * 64}],
            "evidence_source_types": ["daily_course_record"],
        }
    )
    response["metrics"].update(
        {
            "llm_call_count": 1,
            "prompt_tokens": 100,
            "completion_tokens": 20,
            "total_tokens": 120,
            "api_time_seconds": 0.008,
            "usage_attributions": [
                {
                    "executor_key": "course_quality",
                    "llm_call_count": 1,
                    "prompt_tokens": 100,
                    "completion_tokens": 20,
                    "total_tokens": 120,
                    "covered_customer_rule_ids": [
                        "LX0609-01-01-01",
                        "LX0609-02-01-05",
                    ],
                    "latency_ms": 8.0,
                }
            ],
        }
    )

    candidate = ledger_builder.build_candidate_ledger(
        batch,
        candidate_version="family-coverage-v2",
        generated_at="2026-07-24T00:00:00Z",
    )

    by_rule = {row["rule_id"]: row for row in candidate["rows"]}
    assert by_rule["LX0609-01-01-01"]["total_tokens"] == 0
    assert by_rule["LX0609-02-01-05"]["prompt_tokens"] == 100
    assert by_rule["LX0609-02-01-05"]["completion_tokens"] == 20
    assert by_rule["LX0609-02-01-05"]["total_tokens"] == 120
    assert response["metrics"]["total_tokens"] == 120


@pytest.mark.parametrize(
    "mutation",
    ("patient_name", "record_content", "missing_runtime", "bad_manifest"),
)
def test_v2_candidate_fails_closed_for_phi_or_incomplete_identity(
    mutation: str,
) -> None:
    batch = _v2_api_batch()
    if mutation == "missing_runtime":
        batch.pop("runtime_manifest_hash")
    elif mutation == "bad_manifest":
        batch["runtime_manifest_hash"] = "invalid"
    else:
        batch["cases"][0][mutation] = "PRIVATE-MARKER"
    with pytest.raises(ValueError):
        ledger_builder.build_candidate_ledger(
            batch,
            candidate_version="candidate20-v2",
            generated_at="2026-07-24T00:00:00Z",
        )


@pytest.mark.parametrize(
    "mutation",
    (
        "missing",
        "boolean",
        "negative",
        "arithmetic_mismatch",
        "nan_latency",
        "unattributed_prompt_boolean",
        "unattributed_completion_nonzero",
        "latency_mismatch",
    ),
)
def test_v2_candidate_fails_closed_for_incomplete_rule_token_usage(
    mutation: str,
) -> None:
    batch = _v2_api_batch()
    metrics = batch["cases"][0]["response"]["metrics"]
    attribution = metrics["usage_attributions"][0]
    if mutation == "missing":
        metrics.pop("usage_attributions")
    elif mutation == "boolean":
        attribution["prompt_tokens"] = False
    elif mutation == "negative":
        attribution["completion_tokens"] = -1
    elif mutation == "nan_latency":
        attribution["latency_ms"] = float("nan")
    elif mutation == "unattributed_prompt_boolean":
        metrics["unattributed_prompt_tokens"] = False
    elif mutation == "unattributed_completion_nonzero":
        metrics["unattributed_completion_tokens"] = 1
    elif mutation == "latency_mismatch":
        metrics["api_time_seconds"] = 1.0
    else:
        attribution["total_tokens"] = 1

    with pytest.raises(ValueError, match="usage attribution"):
        ledger_builder.build_candidate_ledger(
            batch,
            candidate_version="candidate20-v2",
            generated_at="2026-07-24T00:00:00Z",
        )


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
            "rule_id": "LX0609-01-01-01",
            "decision_kind": "deterministic",
            "observed_state": "non_compliant",
            "observed_reason_code": "deadline_exceeded",
            "evidence_ref_hashes": candidate["rows"][0]["evidence_ref_hashes"],
            "review_status": "candidate",
        }
    ]
    assert len(candidate["rows"][0]["evidence_ref_hashes"]) == 1
    assert len(candidate["rows"][0]["evidence_ref_hashes"][0]) == 64
    assert candidate["rows"][0]["evidence_ref_hashes"] == ["c" * 64]
    assert "expected_state" not in candidate["rows"][0]


def test_candidate_observation_changes_without_changing_bound_evidence_hash() -> None:
    first_payload = _safe_api_batch(status="compliant")
    first_payload["cases"][0]["response"]["results"][0]["metadata"][
        "reason_code"
    ] = "first_reason"
    second_payload = _safe_api_batch(status="non_compliant")
    second_payload["cases"][0]["response"]["results"][0]["metadata"][
        "reason_code"
    ] = "second_reason"

    first = ledger_builder.build_candidate_ledger(
        first_payload,
        candidate_version="candidate20-v1",
        generated_at="2026-07-17T10:00:00Z",
    )["rows"][0]
    second = ledger_builder.build_candidate_ledger(
        second_payload,
        candidate_version="candidate20-v1",
        generated_at="2026-07-17T10:00:00Z",
    )["rows"][0]

    assert (first["observed_state"], first["observed_reason_code"]) == (
        "compliant",
        "first_reason",
    )
    assert (second["observed_state"], second["observed_reason_code"]) == (
        "non_compliant",
        "second_reason",
    )
    assert first["evidence_ref_hashes"] == second["evidence_ref_hashes"] == [
        "c" * 64
    ]


@pytest.mark.parametrize("invalid_kind", ["missing", "empty", "arbitrary", "malformed"])
def test_candidate_rejects_missing_or_untrusted_evidence_attestation(
    invalid_kind: str,
) -> None:
    payload = _safe_api_batch()
    result = payload["cases"][0]["response"]["results"][0]
    if invalid_kind == "missing":
        result.pop("evidence_items")
    elif invalid_kind == "empty":
        result["evidence_items"] = []
    elif invalid_kind == "arbitrary":
        result["evidence_items"] = [
            {"source_table": "PRIVATE-TABLE-MARKER", "field_path": "record_time"}
        ]
    else:
        result["evidence_items"] = [
            {"evidence_attestation": "PRIVATE-MALFORMED-MARKER"}
        ]

    with pytest.raises(ValueError) as raised:
        ledger_builder.build_candidate_ledger(
            payload,
            candidate_version="candidate20-v1",
            generated_at="2026-07-17T10:00:00Z",
        )

    assert str(raised.value) in {
        "missing evidence attestation",
        "invalid evidence attestation",
        "invalid evidence_attestation",
    }
    assert "PRIVATE-" not in repr(raised.value)


def test_candidate_exports_stable_blank_human_review_template(tmp_path: Path) -> None:
    candidate = ledger_builder.build_candidate_ledger(
        _safe_api_batch(status="non_compliant"),
        candidate_version="candidate20-v1",
        generated_at="2026-07-17T10:00:00Z",
    )
    review_rows = ledger_builder.build_review_template_rows(candidate)

    assert review_rows == [
        {
            "candidate_digest": candidate["candidate_digest"],
            "case_label": "case-01",
            "selector_digest": "a" * 64,
            "rule_id": "LX0609-01-01-01",
            "decision_kind": "deterministic",
            "expected_state": "",
            "expected_reason_code": "",
            "evidence_ref_hashes": ";".join(
                candidate["rows"][0]["evidence_ref_hashes"]
            ),
            "reviewer_code": "",
            "accepted_at": "",
            "review_revision": "",
            "review_status": "",
        }
    ]
    assert "observed_state" not in review_rows[0]
    assert "observed_reason_code" not in review_rows[0]

    output = tmp_path / "review.csv"
    ledger_builder.write_review_template_csv(output, review_rows)
    raw = output.read_bytes()
    assert not raw.startswith(b"\xef\xbb\xbf")
    assert b"\r\n" not in raw
    with output.open("r", encoding="utf-8", newline="") as handle:
        assert list(csv.DictReader(handle)) == review_rows


def test_review_template_uses_explicit_llm_executor_as_semantic() -> None:
    payload = _safe_api_batch()
    payload["cases"][0]["response"]["results"][0]["metadata"][
        "executor_type"
    ] = "llm"
    candidate = ledger_builder.build_candidate_ledger(
        payload,
        candidate_version="candidate20-v1",
        generated_at="2026-07-17T10:00:00Z",
    )

    assert ledger_builder.build_review_template_rows(candidate)[0][
        "decision_kind"
    ] == "semantic"


def test_review_template_never_guesses_missing_decision_kind() -> None:
    payload = _safe_api_batch()
    del payload["cases"][0]["response"]["results"][0]["metadata"][
        "executor_type"
    ]
    candidate = ledger_builder.build_candidate_ledger(
        payload,
        candidate_version="legacy-candidate-v1",
        generated_at="2026-07-17T10:00:00Z",
    )

    with pytest.raises(ValueError, match="invalid candidate ledger"):
        ledger_builder.build_review_template_rows(candidate)


@pytest.mark.parametrize(
    ("forbidden_key", "forbidden_value"),
    [
        ("visit_id", "PRIVATE-VISIT-MARKER"),
        ("patient_name", "PRIVATE-NAME-MARKER"),
        ("medical_text", "PRIVATE-BODY-MARKER"),
        ("prompt", "PRIVATE-PROMPT-MARKER"),
        ("raw_response", "PRIVATE-RAW-MARKER"),
        ("document_body", "PRIVATE-BODY-MARKER"),
        ("raw_output", "PRIVATE-RAW-OUTPUT-MARKER"),
        ("sql", "PRIVATE-SQL-MARKER"),
        ("source_coordinates", "PRIVATE-COORDINATES-MARKER"),
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


def test_candidate_accepts_exact_lowercase_sha256_with_phone_shaped_digits() -> None:
    opaque_digest = "a" * 20 + "13800138000" + "b" * 33
    assert len(opaque_digest) == 64
    payload = _safe_api_batch()
    payload["selector_digest"] = opaque_digest

    candidate = ledger_builder.build_candidate_ledger(
        payload,
        candidate_version="candidate20-v1",
        generated_at="2026-07-17T10:00:00Z",
    )

    assert candidate["selector_digest"] == opaque_digest


@pytest.mark.parametrize(
    "unsafe_value",
    [
        "A" * 20 + "13800138000" + "B" * 33,
        "a" * 19 + "13800138000" + "b" * 33,
        "prefix-" + "a" * 20 + "13800138000" + "b" * 33,
        "a" * 20 + "13800138000" + "b" * 33 + "-suffix",
        "13800138000",
        "11010519491231002X",
        "Bearer PRIVATE-CREDENTIAL",
    ],
)
def test_nonexact_digest_or_raw_sensitive_value_remains_non_echo_rejected(
    unsafe_value: str,
) -> None:
    payload = _safe_api_batch()
    payload["selector_digest"] = unsafe_value

    with pytest.raises(ValueError) as raised:
        ledger_builder.build_candidate_ledger(
            payload,
            candidate_version="candidate20-v1",
            generated_at="2026-07-17T10:00:00Z",
        )

    assert str(raised.value) == "unsafe API DTO"
    assert unsafe_value not in repr(raised.value)


def test_forbidden_key_is_rejected_even_when_value_is_exact_digest() -> None:
    payload = _safe_api_batch()
    payload["visit_id"] = "a" * 64

    with pytest.raises(ValueError, match="unsafe API DTO"):
        ledger_builder.build_candidate_ledger(
            payload,
            candidate_version="candidate20-v1",
            generated_at="2026-07-17T10:00:00Z",
        )


def _accepted_review(candidate: dict[str, object]) -> dict[str, str]:
    row = candidate["rows"][0]
    return {
        "candidate_digest": str(candidate["candidate_digest"]),
        "case_label": str(row["case_label"]),
        "selector_digest": str(row["selector_digest"]),
        "rule_id": str(row["rule_id"]),
        "decision_kind": str(row["decision_kind"]),
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


def test_review_template_cli_sorts_matrix_and_preserves_row_count(
    tmp_path: Path,
) -> None:
    payload = _safe_api_batch()
    second = json.loads(json.dumps(payload["cases"][0]))
    second["case_label"] = "case-02"
    second["response"]["results"][0]["rule_id"] = "LX0609-02-01-05"
    payload["cases"] = [second, payload["cases"][0]]
    candidate = ledger_builder.build_candidate_ledger(
        payload,
        candidate_version="candidate20-v1",
        generated_at="2026-07-17T10:00:00Z",
    )
    candidate_path = tmp_path / "candidate.json"
    output_path = tmp_path / "review.csv"
    candidate_path.write_text(
        json.dumps(candidate, ensure_ascii=False), encoding="utf-8", newline="\n"
    )

    assert ledger_builder.main(
        [
            "review-template",
            "--candidate",
            str(candidate_path),
            "--out",
            str(output_path),
        ]
    ) == 0

    with output_path.open("r", encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    assert len(rows) == candidate["candidate_count"] == 2
    assert [(row["case_label"], row["rule_id"]) for row in rows] == [
        ("case-01", "LX0609-01-01-01"),
        ("case-02", "LX0609-02-01-05"),
    ]
    assert all(row["expected_state"] == "" for row in rows)


def test_review_template_rejects_unsafe_tampered_candidate_without_echo() -> None:
    candidate = ledger_builder.build_candidate_ledger(
        _safe_api_batch(),
        candidate_version="candidate20-v1",
        generated_at="2026-07-17T10:00:00Z",
    )
    candidate["rows"][0]["record_content"] = "PRIVATE-BODY-MARKER"
    candidate["candidate_digest"] = ledger_builder.canonical_digest(
        {key: value for key, value in candidate.items() if key != "candidate_digest"}
    )

    with pytest.raises(ValueError) as raised:
        ledger_builder.build_review_template_rows(candidate)

    assert str(raised.value) == "unsafe API DTO"
    assert "PRIVATE-BODY-MARKER" not in repr(raised.value)


def test_promotion_rejects_changed_immutable_decision_kind() -> None:
    candidate = ledger_builder.build_candidate_ledger(
        _safe_api_batch(),
        candidate_version="candidate20-v1",
        generated_at="2026-07-17T10:00:00Z",
    )
    review = _accepted_review(candidate)
    review["decision_kind"] = "semantic"

    with pytest.raises(ValueError, match="incomplete accepted review"):
        ledger_builder.promote_candidate_ledger(
            candidate,
            [review],
            ledger_version="accepted20-v1",
            generated_at="2026-07-17T10:31:00Z",
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
