from __future__ import annotations

from types import SimpleNamespace
import hashlib
from itertools import count
import json
from pathlib import Path

import pytest

from scripts import run_luxian_0609_preproduction_benchmark20 as benchmark20
from scripts.build_luxian_0609_golden_ledger import build_candidate_ledger
from scripts.run_luxian_0609_preproduction_benchmark20 import (
    BenchmarkContractError,
    build_benchmark_batch,
)


def _case_map() -> dict:
    return {
        "selector_version": "fixed20-v1",
        "cases": [
            {
                "case_label": f"case-{index:02d}",
                "scene": "running",
                "institute_id": f"private-institute-{index}",
                "patient_id": f"private-patient-{index}",
                "visit_id": f"private-visit-{index}",
            }
            for index in range(1, 21)
        ],
    }


def _safe_response(*, wall_time_ms: float = 10.0) -> dict:
    results = [
        {
            "rule_id": f"LX0609-{index:03d}",
            "status": "compliant",
            "metadata": {
                "reason_code": "verified",
                "prompt_tokens": 99,
            },
            "evidence_items": [],
            "findings": "PRIVATE-BODY-MARKER",
        }
        for index in range(1, 50)
    ]
    return {
        "schema_version": "lx0609-preproduction-runner-v1",
        "results": results,
        "metrics": {
            "wall_time_ms": wall_time_ms,
            "llm_call_count": 1,
            "prompt_tokens": 10,
            "completion_tokens": 2,
            "total_tokens": 12,
            "technical_error_count": 0,
            "rule_decision_count": 49,
            "typed_shadow_adapter_count": 0,
            "legacy_projection_count": 0,
        },
    }


def _emit_attestations(
    kwargs: dict,
    *,
    salt: str,
    state_overrides: dict[str, str] | None = None,
    reason_overrides: dict[str, str] | None = None,
) -> None:
    state_overrides = state_overrides or {}
    reason_overrides = reason_overrides or {}
    sink = kwargs["evidence_attestation_sink"]
    sink(
        [
            {
                "rule_id": f"LX0609-{index:03d}",
                "evidence_hash": hashlib.sha256(
                    f"{salt}:LX0609-{index:03d}".encode()
                ).hexdigest(),
                "observed_state": state_overrides.get(
                    f"LX0609-{index:03d}", "compliant"
                ),
                "reason_code": reason_overrides.get(
                    f"LX0609-{index:03d}", "verified"
                ),
            }
            for index in range(1, 50)
        ]
    )


@pytest.mark.asyncio
async def test_benchmark20_runs_exact_cases_in_order_and_returns_safe_golden_batch():
    loader_calls: list[tuple[str, str, str, str]] = []
    runner_calls: list[tuple[str, ...]] = []

    def fake_loader(*, scene, institute_id, patient_id, visit_id, schema="public"):
        assert schema == "public"
        loader_calls.append((scene, institute_id, patient_id, visit_id))
        return {
            "scene": scene,
            "institute_id": institute_id,
            "patient_id": patient_id,
            "visit_id": visit_id,
        }

    async def fake_runner(**kwargs):
        runner_calls.append(tuple(kwargs["selected_customer_rule_ids"]))
        _emit_attestations(kwargs, salt=str(len(runner_calls)))
        response = _safe_response(wall_time_ms=float(len(runner_calls)))
        for result in response["results"]:
            result["metadata"].pop("reason_code")
        return response

    batch = await build_benchmark_batch(
        case_map=_case_map(),
        evaluation_as_of_date="2026-07-17",
        bundle_loader=fake_loader,
        runner=fake_runner,
        llm_client=object(),
        base_settings=SimpleNamespace(),
    )

    assert len(loader_calls) == 20
    assert [call[1] for call in loader_calls] == [
        f"private-institute-{index}" for index in range(1, 21)
    ]
    assert len(runner_calls) == 20
    assert all(
        selected == tuple(f"LX0609-{index:03d}" for index in range(1, 50))
        for selected in runner_calls
    )
    assert batch["schema_version"] == "lx0609-golden-api-batch-v1"
    assert [case["case_label"] for case in batch["cases"]] == [
        f"case-{index:02d}" for index in range(1, 21)
    ]
    assert batch["summary"]["case_count"] == 20
    assert batch["summary"]["judgment_count"] == 980
    assert batch["summary"]["status_counts"] == {"compliant": 980}
    assert batch["summary"]["llm_call_count"] == 20
    assert batch["summary"]["total_tokens"] == 240
    assert batch["summary"]["technical_error_count"] == 0
    assert batch["summary"]["latency_ms"]["p50"] == 10.5
    assert batch["summary"]["latency_ms"]["p95"] == 19.05
    assert batch["summary"]["rule_maturity"] == {
        "rule_decision_count": 49,
        "typed_shadow_adapter_count": 0,
        "legacy_projection_count": 0,
    }
    assert len(batch["selector_digest"]) == 64
    assert len(batch["rule_set_digest"]) == 64
    assert all(len(case["coordinate_hash"]) == 64 for case in batch["cases"])
    candidate = build_candidate_ledger(
        batch,
        candidate_version="benchmark-test-v1",
        generated_at="2026-07-17T00:00:00Z",
    )
    assert candidate["candidate_count"] == 980
    decision_kinds = [row["decision_kind"] for row in candidate["rows"]]
    assert decision_kinds.count("deterministic") == 580
    assert decision_kinds.count("semantic") == 400
    attestation_hashes = [
        evidence_hash
        for case in batch["cases"]
        for evidence_hash in case["evidence_attestations"].values()
    ]
    assert len(attestation_hashes) == len(set(attestation_hashes)) == 980
    assert [row["evidence_ref_hashes"][0] for row in candidate["rows"]] == (
        attestation_hashes
    )
    assert {row["observed_reason_code"] for row in candidate["rows"]} == {
        "verified"
    }

    rendered = repr(batch)
    for private_marker in (
        "private-institute",
        "private-patient",
        "private-visit",
        "institute_id",
        "patient_id",
        "visit_id",
        "PRIVATE-BODY-MARKER",
        "prompt_tokens",
    ):
        assert private_marker not in rendered


@pytest.mark.asyncio
async def test_benchmark20_fails_fast_on_technical_error_without_echo():
    runner_calls = 0

    def fake_loader(**kwargs):
        return {"scene": kwargs["scene"]}

    async def fake_runner(**kwargs):
        nonlocal runner_calls
        runner_calls += 1
        response = _safe_response()
        response["results"][0]["status"] = "technical_error"
        response["results"][0]["metadata"]["reason_code"] = (
            "PRIVATE-ERROR-MARKER"
        )
        _emit_attestations(
            kwargs,
            salt=str(runner_calls),
            state_overrides={"LX0609-001": "technical_error"},
            reason_overrides={"LX0609-001": "runner_failed"},
        )
        response["metrics"]["technical_error_count"] = 1
        return response

    with pytest.raises(Exception) as captured:
        await build_benchmark_batch(
            case_map=_case_map(),
            evaluation_as_of_date="2026-07-17",
            bundle_loader=fake_loader,
            runner=fake_runner,
            llm_client=object(),
            base_settings=SimpleNamespace(),
        )

    assert runner_calls == 1
    assert "PRIVATE-ERROR-MARKER" not in str(captured.value)


@pytest.mark.asyncio
async def test_benchmark20_can_emit_diagnostic_batch_when_technical_error_is_allowed():
    call_numbers = count(1)

    async def fake_runner(**kwargs):
        response = _safe_response()
        response["results"][0]["status"] = "technical_error"
        _emit_attestations(
            kwargs,
            salt=str(next(call_numbers)),
            state_overrides={"LX0609-001": "technical_error"},
            reason_overrides={"LX0609-001": "runner_failed"},
        )
        response["metrics"]["technical_error_count"] = 1
        return response

    batch = await build_benchmark_batch(
        case_map=_case_map(),
        evaluation_as_of_date="2026-07-17",
        bundle_loader=lambda **kwargs: {"scene": kwargs["scene"]},
        runner=fake_runner,
        llm_client=object(),
        base_settings=SimpleNamespace(),
        fail_on_technical_error=False,
    )

    assert batch["summary"]["technical_error_count"] == 20
    assert batch["summary"]["status_counts"] == {
        "compliant": 960,
        "technical_error": 20,
    }


@pytest.mark.asyncio
@pytest.mark.parametrize("invalid_kind", ["nineteen", "duplicate", "reordered", "extra"])
async def test_benchmark20_rejects_noncanonical_case_maps_before_reading(invalid_kind):
    value = _case_map()
    if invalid_kind == "nineteen":
        value["cases"].pop()
    elif invalid_kind == "duplicate":
        value["cases"][1].update(value["cases"][0])
        value["cases"][1]["case_label"] = "case-02"
    elif invalid_kind == "reordered":
        value["cases"][0], value["cases"][1] = value["cases"][1], value["cases"][0]
    else:
        value["cases"][0]["unexpected"] = "PRIVATE-MARKER"
    reads = 0

    def fake_loader(**_):
        nonlocal reads
        reads += 1
        return {}

    with pytest.raises(BenchmarkContractError):
        await build_benchmark_batch(
            case_map=value,
            evaluation_as_of_date="2026-07-17",
            bundle_loader=fake_loader,
            runner=lambda **_: None,
            llm_client=object(),
            base_settings=SimpleNamespace(),
        )
    assert reads == 0


@pytest.mark.asyncio
async def test_benchmark20_rejects_incomplete_response_without_echo():
    async def fake_runner(**kwargs):
        _emit_attestations(kwargs, salt="incomplete")
        response = _safe_response()
        response["results"].pop()
        response["private_error"] = "PRIVATE-RESPONSE-MARKER"
        return response

    with pytest.raises(BenchmarkContractError) as captured:
        await build_benchmark_batch(
            case_map=_case_map(),
            evaluation_as_of_date="2026-07-17",
            bundle_loader=lambda **kwargs: {"scene": kwargs["scene"]},
            runner=fake_runner,
            llm_client=object(),
            base_settings=SimpleNamespace(),
        )
    assert "PRIVATE-RESPONSE-MARKER" not in str(captured.value)


@pytest.mark.asyncio
@pytest.mark.parametrize("authority", ["", "unknown_authority"])
async def test_benchmark20_fails_before_read_when_rule_authority_is_missing_or_unknown(
    monkeypatch, authority
):
    contracts = [
        SimpleNamespace(
            rule_id=f"LX0609-{index:03d}",
            decision_authority=(
                authority if index == 49 else "program_only"
            ),
        )
        for index in range(1, 50)
    ]
    monkeypatch.setattr(
        benchmark20,
        "load_luxian_0609_rule_contracts",
        lambda: contracts,
    )
    reads = 0

    def fake_loader(**_):
        nonlocal reads
        reads += 1
        return {}

    with pytest.raises(BenchmarkContractError) as captured:
        await build_benchmark_batch(
            case_map=_case_map(),
            evaluation_as_of_date="2026-07-17",
            bundle_loader=fake_loader,
            runner=lambda **_: None,
            llm_client=object(),
            base_settings=SimpleNamespace(),
        )

    assert reads == 0
    assert str(captured.value) == "invalid LX0609 decision authority"


@pytest.mark.asyncio
async def test_benchmark20_ignores_untrusted_customer_executor_type():
    call_numbers = count(1)

    async def fake_runner(**kwargs):
        _emit_attestations(kwargs, salt=str(next(call_numbers)))
        response = _safe_response()
        for result in response["results"]:
            result["metadata"]["executor_type"] = "llm"
        return response

    batch = await build_benchmark_batch(
        case_map=_case_map(),
        evaluation_as_of_date="2026-07-17",
        bundle_loader=lambda **kwargs: {"scene": kwargs["scene"]},
        runner=fake_runner,
        llm_client=object(),
        base_settings=SimpleNamespace(),
    )
    candidate = build_candidate_ledger(
        batch,
        candidate_version="benchmark-authority-test-v1",
        generated_at="2026-07-17T00:00:00Z",
    )
    decision_kinds = [row["decision_kind"] for row in candidate["rows"]]
    assert decision_kinds.count("deterministic") == 580
    assert decision_kinds.count("semantic") == 400


@pytest.mark.asyncio
async def test_benchmark20_rejects_attested_state_mismatch_without_echo():
    call_numbers = count(1)

    async def fake_runner(**kwargs):
        _emit_attestations(
            kwargs,
            salt=str(next(call_numbers)),
            state_overrides={"LX0609-001": "non_compliant"},
            reason_overrides={"LX0609-001": "mismatch_reason"},
        )
        return _safe_response()

    with pytest.raises(BenchmarkContractError) as raised:
        await build_benchmark_batch(
            case_map=_case_map(),
            evaluation_as_of_date="2026-07-17",
            bundle_loader=lambda **kwargs: {"scene": kwargs["scene"]},
            runner=fake_runner,
            llm_client=object(),
            base_settings=SimpleNamespace(),
        )

    assert str(raised.value) == "attested result state mismatch"


def test_benchmark20_cli_requires_explicit_inputs_and_writes_only_safe_batch(
    monkeypatch, tmp_path, capsys
):
    case_map_path = tmp_path / "case-map.json"
    output_path = tmp_path / "benchmark.json"
    case_map_path.write_text(json.dumps(_case_map()), encoding="utf-8")
    safe_batch = {
        "schema_version": "lx0609-golden-api-batch-v1",
        "selector_digest": "a" * 64,
        "rule_set_digest": "b" * 64,
        "summary": {
            "case_count": 20,
            "judgment_count": 980,
            "technical_error_count": 0,
        },
    }
    captured_args = {}

    async def fake_build(**kwargs):
        captured_args.update(kwargs)
        return safe_batch

    monkeypatch.setattr(benchmark20, "build_benchmark_batch", fake_build)
    monkeypatch.setattr(benchmark20, "_build_llm_client", lambda: object())
    monkeypatch.setattr(benchmark20, "get_settings", lambda: SimpleNamespace())

    exit_code = benchmark20.main(
        [
            "--case-map",
            str(case_map_path),
            "--evaluation-as-of-date",
            "2026-07-17",
            "--output",
            str(output_path),
        ]
    )

    assert exit_code == 0
    assert captured_args["evaluation_as_of_date"] == "2026-07-17"
    assert captured_args["fail_on_technical_error"] is True
    assert json.loads(output_path.read_text(encoding="utf-8")) == safe_batch
    stdout = capsys.readouterr().out
    assert "private-institute" not in stdout


def test_benchmark20_source_has_no_task_workspace_or_database_write_path():
    source = Path(benchmark20.__file__).read_text(encoding="utf-8").lower()
    for forbidden in (
        "load_or_assemble",
        "workspace",
        "create_job",
        "persist_",
        "insert into",
        "update ",
        "delete from",
    ):
        assert forbidden not in source
