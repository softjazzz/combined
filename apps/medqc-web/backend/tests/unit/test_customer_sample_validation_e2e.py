from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts import run_customer_sample_validation_e2e as e2e


class FakeApiClient:
    def __init__(self, responses: dict[tuple[str, str], list[dict] | dict]):
        self.responses = {
            key: list(value) if isinstance(value, list) else [value]
            for key, value in responses.items()
        }
        self.calls: list[dict] = []

    def request(
        self,
        method: str,
        path: str,
        *,
        params: dict | None = None,
        json_data: dict | None = None,
        binary: bool = False,
    ) -> dict:
        normalized_method = method.upper()
        self.calls.append(
            {
                "method": normalized_method,
                "path": path,
                "params": params,
                "json_data": json_data,
                "binary": binary,
            }
        )
        queue = self.responses.get((normalized_method, path))
        if not queue:
            raise AssertionError(f"unexpected api call: {normalized_method} {path}")
        result = queue.pop(0)
        if isinstance(result, Exception):
            raise result
        return result


def _response(data: object, *, elapsed_ms: float = 2.0) -> dict:
    return {
        "data": data,
        "status_code": 200,
        "elapsed_ms": elapsed_ms,
        "content_type": "application/json",
        "byte_count": 0,
    }


def _preflight_responses(*, ready: bool = True) -> dict:
    record = {
        "id": "private-record-row",
        "matched_institute_id": "private-institute",
        "matched_patient_id": "private-patient",
        "matched_visit_id": "LX0609_SYN_001",
        "patient_name": "PRIVATE-PATIENT-NAME",
        "mr_no": "PRIVATE-MR-NO",
        "match_status": "matched" if ready else "unmatched",
        "sync_status": "synced" if ready else "pending",
        "bundle_status": "ready" if ready else "pending",
        "sample_item_ids": ["private-item"],
    }
    return {
        ("GET", "/api/v1/health"): _response({"status": "healthy"}),
        ("GET", "/api/v1/qc/sample-pools/rule-sets"): _response(
            {
                "items": [
                    {
                        "rule_set_key": "luxian_0609_qc_v1",
                        "rule_ids": ["LX0609-01-01-01", "LX0609-12-01-02", "LX0609-04-01-01"],
                        "artifact_freshness": {"status": "fresh"},
                        "release_gate_summary": {"release_ready": False},
                    }
                ]
            }
        ),
        ("GET", "/api/v1/qc/sichuan/rules"): _response(
            {
                "rules": [
                    {"rule_id": "LX0609-01-01-01"},
                    {"rule_id": "LX0609-12-01-02"},
                    {"rule_id": "LX0609-04-01-01"},
                ]
            }
        ),
        ("GET", "/api/v1/qc/sample-pools"): _response(
            {
                "items": [
                    {
                        "id": "luxian-0609-synthetic-v1",
                        "name": "泸县0609合成质控样本 v1",
                        "source_file": "synthetic://luxian_0609_synthetic_cases_v1",
                        "total_items": 1,
                    }
                ],
                "total": 1,
            }
        ),
        (
            "GET",
            "/api/v1/qc/sample-pools/luxian-0609-synthetic-v1/records",
        ): _response({"items": [record], "total": 1}),
    }


def _minimal_write_responses() -> dict:
    responses = _preflight_responses()
    responses.update(
        {
            (
                "POST",
                "/api/v1/qc/sample-pools/luxian-0609-synthetic-v1/run",
            ): _response(
                {
                    "job_id": "private-job-id",
                    "operation_ref": f"sample-op-{'b' * 24}",
                    "execution_scope_hash": "a" * 64,
                }
            ),
            (
                "GET",
                "/api/v1/qc/sichuan/workspace/batch-jobs/private-job-id",
            ): _response(
                {
                    "status": "completed",
                    "summary": {},
                    "items": [{"rule_id": "LX0609-01-01-01", "status": "compliant"}],
                }
            ),
            (
                "POST",
                "/api/v1/qc/sichuan/workspace/batch-jobs/private-job-id/review",
            ): _response(
                {
                    "review_report": {
                        "summary": {
                            "total_findings": 0,
                            "p0": 0,
                            "p1": 0,
                            "p2": 0,
                        }
                    }
                }
            ),
            (
                "GET",
                "/api/v1/qc/sichuan/workspace/batch-jobs/private-job-id/export",
            ): [
                {
                    "data": None,
                    "status_code": 200,
                    "elapsed_ms": 1.0,
                    "content_type": "text/html; charset=utf-8",
                    "byte_count": 10,
                },
                {
                    "data": None,
                    "status_code": 200,
                    "elapsed_ms": 1.0,
                    "content_type": "text/csv; charset=utf-8",
                    "byte_count": 10,
                },
                {
                    "data": None,
                    "status_code": 200,
                    "elapsed_ms": 1.0,
                    "content_type": (
                        "application/vnd.openxmlformats-officedocument."
                        "spreadsheetml.sheet"
                    ),
                    "byte_count": 10,
                },
            ],
        }
    )
    return responses


def test_dry_run_is_get_only_and_emits_safe_ledger(tmp_path: Path):
    marker = "lx0609-e2e-v1"
    client = FakeApiClient(_preflight_responses())
    output_path = tmp_path / "safe-ledger.json"

    ledger = e2e.run_e2e(
        api=client,
        fixture_pool=marker,
        selected_rule_ids=("LX0609-01-01-01", "LX0609-12-01-02", "LX0609-04-01-01"),
        dry_run=True,
        allow_local_writes=False,
        output_path=output_path,
    )

    assert {call["method"] for call in client.calls} == {"GET"}
    assert [stage["name"] for stage in ledger["stages"]] == list(e2e.STAGE_NAMES)
    assert [stage["status"] for stage in ledger["stages"]] == [
        "passed",
        "passed",
        "passed",
        "skipped",
        "skipped",
    ]
    assert ledger["summary"]["record_count"] == 1
    assert ledger["summary"]["ready_record_count"] == 1
    assert marker not in repr(ledger)
    assert "luxian-0609-synthetic-v1" not in repr(ledger)
    assert "LX0609_SYN_001" not in repr(ledger)
    assert "PRIVATE-PATIENT-NAME" not in repr(ledger)
    saved = json.loads(output_path.read_text(encoding="utf-8"))
    assert saved == ledger


def test_write_mode_requires_explicit_allow_before_any_request():
    client = FakeApiClient({})

    with pytest.raises(e2e.E2EContractError, match="allow-local-writes"):
        e2e.run_e2e(
            api=client,
            fixture_pool="lx0609-e2e-v1",
            selected_rule_ids=("LX0609-01-01-01",),
            dry_run=False,
            allow_local_writes=False,
        )

    assert client.calls == []


def test_unready_fixture_stops_before_task_creation():
    responses = _preflight_responses(ready=False)
    client = FakeApiClient(responses)

    ledger = e2e.run_e2e(
        api=client,
        fixture_pool="lx0609-e2e-v1",
        selected_rule_ids=("LX0609-01-01-01",),
        dry_run=True,
        allow_local_writes=False,
    )

    statuses = {stage["name"]: stage["status"] for stage in ledger["stages"]}
    assert statuses["match_sync"] == "failed"
    assert statuses["run_poll"] == "skipped"
    assert statuses["review_export_privacy"] == "skipped"
    assert all(call["method"] == "GET" for call in client.calls)
    assert ledger["overall_status"] == "failed"


def test_write_flow_runs_exact_scope_polls_reviews_and_checks_exports():
    responses = _preflight_responses()
    responses.update(
        {
            (
                "POST",
                "/api/v1/qc/sample-pools/luxian-0609-synthetic-v1/run",
            ): _response(
                {
                    "job_id": "private-job-id",
                    "operation_ref": f"sample-op-{'b' * 24}",
                    "execution_scope_hash": "a" * 64,
                    "deduplicated": False,
                }
            ),
            (
                "GET",
                "/api/v1/qc/sichuan/workspace/batch-jobs/private-job-id",
            ): [
                _response({"status": "running"}),
                _response(
                    {
                        "status": "completed",
                        "summary": {
                            "processed_records": 1,
                            "total_records": 1,
                            "llm_call_count": 2,
                            "performance_profile": {
                                "prompt_tokens": 100,
                                "completion_tokens": 20,
                                "total_tokens": 120,
                            },
                        },
                        "items": [
                            {"rule_id": "LX0609-01-01-01", "status": "compliant"},
                            {"rule_id": "LX0609-12-01-02", "status": "non_compliant"},
                            {"rule_id": "LX0609-04-01-01", "status": "data_gap"},
                        ],
                    }
                ),
            ],
            (
                "POST",
                "/api/v1/qc/sichuan/workspace/batch-jobs/private-job-id/review",
            ): _response(
                {
                    "review_report": {
                        "summary": {
                            "total_findings": 3,
                            "p0": 0,
                            "p1": 0,
                            "p2": 3,
                        }
                    }
                }
            ),
            (
                "GET",
                "/api/v1/qc/sichuan/workspace/batch-jobs/private-job-id/export",
            ): [
                {
                    "data": None,
                    "status_code": 200,
                    "elapsed_ms": 3.0,
                    "content_type": "text/html",
                    "byte_count": 120,
                },
                {
                    "data": None,
                    "status_code": 200,
                    "elapsed_ms": 3.0,
                    "content_type": "text/csv",
                    "byte_count": 80,
                },
                {
                    "data": None,
                    "status_code": 200,
                    "elapsed_ms": 3.0,
                    "content_type": (
                        "application/vnd.openxmlformats-officedocument."
                        "spreadsheetml.sheet"
                    ),
                    "byte_count": 500,
                },
            ],
        }
    )
    client = FakeApiClient(responses)

    ledger = e2e.run_e2e(
        api=client,
        fixture_pool="lx0609-e2e-v1",
        selected_rule_ids=("LX0609-01-01-01", "LX0609-12-01-02", "LX0609-04-01-01"),
        dry_run=False,
        allow_local_writes=True,
        poll_interval_seconds=0,
    )

    run_call = next(
        call
        for call in client.calls
        if call["method"] == "POST" and call["path"].endswith("/run")
    )
    assert run_call["json_data"]["selected_rule_ids"] == [
        "LX0609-01-01-01",
        "LX0609-12-01-02",
        "LX0609-04-01-01",
    ]
    assert run_call["json_data"]["record_ids"] == ["LX0609_SYN_001"]
    assert run_call["json_data"]["group_by_luxian_family"] is True
    assert not any(call["path"].endswith("/match") for call in client.calls)
    assert not any(call["path"].endswith("/sync-records") for call in client.calls)
    assert ledger["overall_status"] == "passed"
    assert ledger["summary"]["result_status_counts"] == {
        "compliant": 1,
        "data_gap": 1,
        "non_compliant": 1,
    }
    assert ledger["summary"]["llm_call_count"] == 2
    assert ledger["summary"]["prompt_tokens"] == 100
    assert ledger["summary"]["completion_tokens"] == 20
    assert ledger["summary"]["total_tokens"] == 120
    assert ledger["summary"]["export_format_count"] == 3
    assert ledger["summary"]["review_finding_count"] == 3
    assert "private-job-id" not in repr(ledger)
    assert "LX0609_SYN_001" not in repr(ledger)


def test_safe_ledger_rejects_forbidden_fields_and_raw_private_values():
    with pytest.raises(e2e.E2EPrivacyError, match="forbidden"):
        e2e.assert_safe_ledger({"prompt": "do not leak"})

    with pytest.raises(e2e.E2EPrivacyError, match="private"):
        e2e.assert_safe_ledger(
            {"summary": {"reason_code": "PRIVATE-MARKER"}},
            private_values=("PRIVATE-MARKER",),
        )


def test_preflight_failure_stops_before_fixture_lookup():
    responses = _preflight_responses()
    responses[("GET", "/api/v1/qc/sichuan/rules")] = _response({"rules": []})
    client = FakeApiClient(responses)

    ledger = e2e.run_e2e(
        api=client,
        fixture_pool="lx0609-e2e-v1",
        selected_rule_ids=("LX0609-01-01-01",),
        dry_run=True,
        allow_local_writes=False,
    )

    assert ledger["stages"][0]["status"] == "failed"
    assert ledger["stages"][0]["reason_code"] == "selected_rule_missing"
    assert not any(call["path"] == "/api/v1/qc/sample-pools" for call in client.calls)
    assert all(call["method"] == "GET" for call in client.calls)


def test_stale_release_artifact_stops_before_fixture_lookup():
    responses = _preflight_responses()
    rule_sets = responses[
        ("GET", "/api/v1/qc/sample-pools/rule-sets")
    ]["data"]["items"]
    rule_sets[0]["artifact_freshness"]["status"] = "stale"
    client = FakeApiClient(responses)

    ledger = e2e.run_e2e(
        api=client,
        fixture_pool="lx0609-e2e-v1",
        selected_rule_ids=("LX0609-01-01-01",),
        dry_run=True,
        allow_local_writes=False,
    )

    assert ledger["stages"][0]["status"] == "failed"
    assert ledger["stages"][0]["reason_code"] == "release_artifact_not_fresh"
    assert ledger["summary"]["release_artifact_status"] == "stale"
    assert not any(call["path"] == "/api/v1/qc/sample-pools" for call in client.calls)


def test_fixture_identity_mismatch_stops_before_records_and_run():
    responses = _preflight_responses()
    pool_data = responses[("GET", "/api/v1/qc/sample-pools")]["data"]
    pool_data["items"][0]["source_file"] = "synthetic://wrong-source"
    client = FakeApiClient(responses)

    ledger = e2e.run_e2e(
        api=client,
        fixture_pool="lx0609-e2e-v1",
        selected_rule_ids=("LX0609-01-01-01",),
        dry_run=True,
        allow_local_writes=False,
    )

    fixture_stage = ledger["stages"][1]
    assert fixture_stage["status"] == "failed"
    assert fixture_stage["reason_code"] == "fixture_pool_identity_mismatch"
    assert not any(call["path"].endswith("/records") for call in client.calls)
    assert not any(call["method"] == "POST" for call in client.calls)


def test_failed_job_stops_before_review_and_export():
    responses = _minimal_write_responses()
    responses[
        ("GET", "/api/v1/qc/sichuan/workspace/batch-jobs/private-job-id")
    ] = _response({"status": "failed"})
    client = FakeApiClient(responses)

    ledger = e2e.run_e2e(
        api=client,
        fixture_pool="lx0609-e2e-v1",
        selected_rule_ids=("LX0609-01-01-01",),
        dry_run=False,
        allow_local_writes=True,
        poll_interval_seconds=0,
    )

    assert ledger["stages"][3]["status"] == "failed"
    assert ledger["stages"][3]["reason_code"] == "job_not_completed"
    assert ledger["stages"][4]["status"] == "skipped"
    assert not any(call["path"].endswith("/review") for call in client.calls)
    assert not any(call["path"].endswith("/export") for call in client.calls)


def test_review_failure_stops_before_export():
    responses = _minimal_write_responses()
    responses[
        ("POST", "/api/v1/qc/sichuan/workspace/batch-jobs/private-job-id/review")
    ] = e2e.E2EApiError("api_http_500")
    client = FakeApiClient(responses)

    ledger = e2e.run_e2e(
        api=client,
        fixture_pool="lx0609-e2e-v1",
        selected_rule_ids=("LX0609-01-01-01",),
        dry_run=False,
        allow_local_writes=True,
        poll_interval_seconds=0,
    )

    assert ledger["stages"][4]["status"] == "failed"
    assert ledger["stages"][4]["reason_code"] == "api_http_500"
    assert not any(call["path"].endswith("/export") for call in client.calls)


@pytest.mark.parametrize("invalid_total", [None, "0", -1, True])
def test_invalid_review_report_fails_closed_before_export(invalid_total: object):
    responses = _minimal_write_responses()
    review_key = (
        "POST",
        "/api/v1/qc/sichuan/workspace/batch-jobs/private-job-id/review",
    )
    summary = responses[review_key]["data"]["review_report"]["summary"]
    if invalid_total is None:
        summary.pop("total_findings")
    else:
        summary["total_findings"] = invalid_total
    client = FakeApiClient(responses)

    ledger = e2e.run_e2e(
        api=client,
        fixture_pool="lx0609-e2e-v1",
        selected_rule_ids=("LX0609-01-01-01",),
        dry_run=False,
        allow_local_writes=True,
        poll_interval_seconds=0,
    )

    assert ledger["stages"][4]["status"] == "failed"
    assert ledger["stages"][4]["reason_code"] == "review_report_invalid"
    assert not any(call["path"].endswith("/export") for call in client.calls)


def test_wrong_export_mime_fails_privacy_export_stage():
    responses = _minimal_write_responses()
    export_key = (
        "GET",
        "/api/v1/qc/sichuan/workspace/batch-jobs/private-job-id/export",
    )
    responses[export_key][1]["content_type"] = "text/html"
    client = FakeApiClient(responses)

    ledger = e2e.run_e2e(
        api=client,
        fixture_pool="lx0609-e2e-v1",
        selected_rule_ids=("LX0609-01-01-01",),
        dry_run=False,
        allow_local_writes=True,
        poll_interval_seconds=0,
    )

    assert ledger["stages"][4]["status"] == "failed"
    assert ledger["stages"][4]["reason_code"] == "export_format_incomplete"
    assert ledger["summary"]["export_format_count"] == 2


@pytest.mark.parametrize(
    ("field", "value", "reason_code"),
    [
        ("operation_ref", "unsafe-value", "operation_ref_invalid"),
        ("execution_scope_hash", "ABC", "execution_scope_hash_invalid"),
    ],
)
def test_run_identity_must_match_safe_format(field: str, value: str, reason_code: str):
    responses = _minimal_write_responses()
    run_key = (
        "POST",
        "/api/v1/qc/sample-pools/luxian-0609-synthetic-v1/run",
    )
    responses[run_key]["data"][field] = value
    client = FakeApiClient(responses)

    ledger = e2e.run_e2e(
        api=client,
        fixture_pool="lx0609-e2e-v1",
        selected_rule_ids=("LX0609-01-01-01",),
        dry_run=False,
        allow_local_writes=True,
        poll_interval_seconds=0,
    )

    assert ledger["stages"][3]["status"] == "failed"
    assert ledger["stages"][3]["reason_code"] == reason_code
    assert value not in repr(ledger)


def test_unknown_job_result_status_fails_closed():
    responses = _minimal_write_responses()
    job_key = (
        "GET",
        "/api/v1/qc/sichuan/workspace/batch-jobs/private-job-id",
    )
    responses[job_key]["data"]["items"][0]["status"] = "PRIVATE-STATUS-MARKER"
    client = FakeApiClient(responses)

    ledger = e2e.run_e2e(
        api=client,
        fixture_pool="lx0609-e2e-v1",
        selected_rule_ids=("LX0609-01-01-01",),
        dry_run=False,
        allow_local_writes=True,
        poll_interval_seconds=0,
    )

    assert ledger["stages"][3]["status"] == "failed"
    assert ledger["stages"][3]["reason_code"] == "job_result_status_invalid"
    assert "PRIVATE-STATUS-MARKER" not in repr(ledger)
