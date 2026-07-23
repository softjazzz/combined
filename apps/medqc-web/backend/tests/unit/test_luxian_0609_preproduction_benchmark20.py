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


_RULE_IDS, _EXECUTOR_TYPES = benchmark20._rule_attestations()
_SEMANTIC_RULE_IDS = frozenset(
    rule_id for rule_id in _RULE_IDS if _EXECUTOR_TYPES[rule_id] == "llm"
)
_DETERMINISTIC_RULE_IDS = frozenset(
    rule_id for rule_id in _RULE_IDS if _EXECUTOR_TYPES[rule_id] == "program"
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


def _runtime_manifest(*, git_head: str = "a" * 40) -> dict:
    return {
        "schema_version": "lx0609-runtime-manifest-v1",
        "generated_at": "2026-07-24T00:00:00Z",
        "git_head": git_head,
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


_build_benchmark_batch_impl = build_benchmark_batch


async def build_benchmark_batch(**kwargs):
    kwargs.setdefault("runtime_manifest", _runtime_manifest())
    kwargs.setdefault("observed_git_head", "a" * 40)
    return await _build_benchmark_batch_impl(**kwargs)


def _safe_response(*, wall_time_ms: float = 10.0) -> dict:
    results = [
        {
            "rule_id": f"LX0609-{index:03d}",
            "status": "compliant",
            "metadata": {
                "reason_code": "verified",
                "prompt_tokens": 10 if index == 9 else 0,
                "completion_tokens": 2 if index == 9 else 0,
                "total_tokens": 12 if index == 9 else 0,
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


def _selected_safe_response(
    rule_ids: tuple[str, ...], *, wall_time_ms: float = 10.0
) -> dict:
    response = _safe_response(wall_time_ms=wall_time_ms)
    response["results"] = [
        item for item in response["results"] if item["rule_id"] in rule_ids
    ]
    response["metrics"]["rule_decision_count"] = len(rule_ids)
    if "LX0609-009" not in rule_ids:
        response["metrics"].update(
            {
                "llm_call_count": 0,
                "prompt_tokens": 0,
                "completion_tokens": 0,
                "total_tokens": 0,
            }
        )
    return response


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


def _emit_selected_attestations(
    kwargs: dict,
    *,
    salt: str,
) -> None:
    sink = kwargs["evidence_attestation_sink"]
    rule_ids = tuple(kwargs["selected_customer_rule_ids"])
    sink(
        [
            {
                "rule_id": rule_id,
                "evidence_hash": hashlib.sha256(
                    f"{salt}:{rule_id}".encode()
                ).hexdigest(),
                "observed_state": "compliant",
                "reason_code": "verified",
            }
            for rule_id in rule_ids
        ]
    )


def _assert_candidate_decision_kind_contract(candidate: dict) -> None:
    """锁定49点契约分类，避免017灰区被误记为Python决定。"""

    rows = candidate["rows"]
    assert len(_DETERMINISTIC_RULE_IDS) == 26
    assert len(_SEMANTIC_RULE_IDS) == 23
    assert len(rows) == 20 * 49
    decision_kinds = [row["decision_kind"] for row in rows]
    assert decision_kinds.count("deterministic") == (
        len(_DETERMINISTIC_RULE_IDS) * 20
    )
    assert decision_kinds.count("semantic") == len(_SEMANTIC_RULE_IDS) * 20
    assert (
        decision_kinds.count("deterministic") + decision_kinds.count("semantic")
        == len(rows)
    )

    for case_index in range(1, 21):
        case_label = f"case-{case_index:02d}"
        semantic_rule_ids = {
            row["rule_id"]
            for row in rows
            if row["case_label"] == case_label
            and row["decision_kind"] == "semantic"
        }
        deterministic_rule_ids = {
            row["rule_id"]
            for row in rows
            if row["case_label"] == case_label
            and row["decision_kind"] == "deterministic"
        }
        assert semantic_rule_ids == _SEMANTIC_RULE_IDS
        assert deterministic_rule_ids == _DETERMINISTIC_RULE_IDS

    assert all(
        row["decision_kind"] == "deterministic"
        for row in rows
        if row["rule_id"] == "LX0609-017"
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
    assert batch["summary"]["input_tokens"] == 200
    assert batch["summary"]["completion_tokens"] == 40
    assert batch["summary"]["total_tokens"] == 240
    assert (
        batch["summary"]["input_tokens"]
        + batch["summary"]["completion_tokens"]
        == batch["summary"]["total_tokens"]
    )
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
    _assert_candidate_decision_kind_contract(candidate)
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
    ):
        if private_marker in rendered:
            raise AssertionError(f"unsafe benchmark marker: {private_marker}")
    assert all(
        set(result["metadata"])
        == {
            "reason_code",
            "executor_type",
            "prompt_tokens",
            "completion_tokens",
            "total_tokens",
        }
        for case in batch["cases"]
        for result in case["response"]["results"]
    )


@pytest.mark.asyncio
async def test_benchmark20_binds_current_runtime_manifest_and_rejects_stale_head():
    call_numbers = count(1)

    async def fake_runner(**kwargs):
        _emit_attestations(kwargs, salt=f"runtime-{next(call_numbers)}")
        return _safe_response()

    manifest = _runtime_manifest()
    batch = await build_benchmark_batch(
        case_map=_case_map(),
        evaluation_as_of_date="2026-07-24",
        bundle_loader=lambda **kwargs: {"scene": kwargs["scene"]},
        runner=fake_runner,
        llm_client=object(),
        base_settings=SimpleNamespace(),
        runtime_manifest=manifest,
        observed_git_head="a" * 40,
    )

    assert batch["git_head"] == "a" * 40
    assert batch["policy_version"] == "2026-06-09"
    assert len(batch["runtime_manifest_hash"]) == 64
    assert batch["sample_type"] == "real"
    candidate = build_candidate_ledger(
        batch,
        candidate_version="runtime-bound-v2",
        generated_at="2026-07-24T00:00:00Z",
    )
    assert candidate["schema_version"] == "lx0609-golden-candidate-v2"
    assert {row["sample_type"] for row in candidate["rows"]} == {"real"}

    with pytest.raises(BenchmarkContractError, match="runtime manifest"):
        await build_benchmark_batch(
            case_map=_case_map(),
            evaluation_as_of_date="2026-07-24",
            bundle_loader=lambda **kwargs: {"scene": kwargs["scene"]},
            runner=fake_runner,
            llm_client=object(),
            base_settings=SimpleNamespace(),
            runtime_manifest=manifest,
            observed_git_head="b" * 40,
        )


@pytest.mark.asyncio
@pytest.mark.parametrize("failure_kind", ("missing", "incomplete"))
async def test_benchmark20_fails_closed_for_rule_token_attribution(
    failure_kind: str,
):
    async def fake_runner(**kwargs):
        _emit_attestations(kwargs, salt=f"token-{failure_kind}")
        response = _safe_response()
        semantic_metadata = response["results"][8]["metadata"]
        if failure_kind == "missing":
            semantic_metadata.pop("completion_tokens")
        else:
            semantic_metadata.update(
                {
                    "prompt_tokens": 9,
                    "completion_tokens": 2,
                    "total_tokens": 11,
                }
            )
        return response

    with pytest.raises(BenchmarkContractError, match="rule token attribution"):
        await build_benchmark_batch(
            case_map=_case_map(),
            evaluation_as_of_date="2026-07-24",
            bundle_loader=lambda **kwargs: {"scene": kwargs["scene"]},
            runner=fake_runner,
            llm_client=object(),
            base_settings=SimpleNamespace(),
        )


@pytest.mark.asyncio
async def test_benchmark20_selected_rules_run_only_canonical_subset_and_build_safe_40_row_candidate():
    runner_calls: list[tuple[str, ...]] = []

    async def fake_runner(**kwargs):
        selected_rule_ids = tuple(kwargs["selected_customer_rule_ids"])
        runner_calls.append(selected_rule_ids)
        _emit_selected_attestations(kwargs, salt=str(len(runner_calls)))
        return _selected_safe_response(
            selected_rule_ids,
            wall_time_ms=float(len(runner_calls)),
        )

    batch = await build_benchmark_batch(
        case_map=_case_map(),
        evaluation_as_of_date="2026-07-17",
        bundle_loader=lambda **kwargs: {"scene": kwargs["scene"]},
        runner=fake_runner,
        llm_client=object(),
        base_settings=SimpleNamespace(),
        selected_rule_ids=("LX0609-030", "LX0609-029"),
    )

    assert runner_calls == [("LX0609-029", "LX0609-030")] * 20
    assert batch["rule_scope"] == {
        "mode": "selected_subset",
        "selected_rule_ids": ["LX0609-029", "LX0609-030"],
    }
    assert batch["summary"]["judgment_count"] == 40
    assert batch["summary"]["selected_rule_count"] == 2
    assert all(
        tuple(case["evidence_attestations"])
        == ("LX0609-029", "LX0609-030")
        and [item["rule_id"] for item in case["response"]["results"]]
        == ["LX0609-029", "LX0609-030"]
        for case in batch["cases"]
    )
    candidate = build_candidate_ledger(
        batch,
        candidate_version="benchmark-subset-test-v1",
        generated_at="2026-07-17T00:00:00Z",
    )
    assert candidate["candidate_count"] == 40
    assert {row["rule_id"] for row in candidate["rows"]} == {
        "LX0609-029",
        "LX0609-030",
    }
    assert all("private" not in repr(row).lower() for row in candidate["rows"])


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "selected_rule_ids",
    [
        (),
        ("LX0609-029", "LX0609-029"),
        ("LX0609-000",),
        ("LX0609-050",),
        ("lx0609-029",),
        ("LX0609-029 ",),
    ],
)
async def test_benchmark20_rejects_invalid_selected_rule_scope_before_reading(
    selected_rule_ids,
):
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
            selected_rule_ids=selected_rule_ids,
        )

    assert reads == 0
    assert "LX0609" not in str(captured.value)


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
    _assert_candidate_decision_kind_contract(candidate)


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
    runtime_manifest_path = tmp_path / "runtime-manifest.json"
    output_path = tmp_path / "benchmark.json"
    case_map_path.write_text(json.dumps(_case_map()), encoding="utf-8")
    runtime_manifest_path.write_text(
        json.dumps(_runtime_manifest()), encoding="utf-8"
    )
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
            "--runtime-manifest",
            str(runtime_manifest_path),
        ]
    )

    assert exit_code == 0
    assert captured_args["evaluation_as_of_date"] == "2026-07-17"
    assert captured_args["fail_on_technical_error"] is True
    assert captured_args["selected_rule_ids"] is None
    assert json.loads(output_path.read_text(encoding="utf-8")) == safe_batch
    stdout = capsys.readouterr().out
    assert "private-institute" not in stdout


def test_benchmark20_cli_passes_explicit_rule_subset_and_marks_output_scope(
    monkeypatch, tmp_path, capsys
):
    case_map_path = tmp_path / "case-map.json"
    runtime_manifest_path = tmp_path / "runtime-manifest.json"
    output_path = tmp_path / "benchmark.json"
    case_map_path.write_text(json.dumps(_case_map()), encoding="utf-8")
    runtime_manifest_path.write_text(
        json.dumps(_runtime_manifest()), encoding="utf-8"
    )
    safe_batch = {
        "schema_version": "lx0609-golden-api-batch-v1",
        "selector_digest": "a" * 64,
        "rule_set_digest": "b" * 64,
        "rule_scope": {
            "mode": "selected_subset",
            "selected_rule_ids": ["LX0609-029", "LX0609-030"],
        },
        "summary": {
            "case_count": 20,
            "judgment_count": 40,
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
            "--runtime-manifest",
            str(runtime_manifest_path),
            "--rule-id",
            "LX0609-030",
            "--rule-id",
            "LX0609-029",
        ]
    )

    assert exit_code == 0
    assert captured_args["selected_rule_ids"] == ("LX0609-030", "LX0609-029")
    stdout = json.loads(capsys.readouterr().out)
    assert stdout["rule_scope"] == safe_batch["rule_scope"]
    assert stdout["judgment_count"] == 40


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
