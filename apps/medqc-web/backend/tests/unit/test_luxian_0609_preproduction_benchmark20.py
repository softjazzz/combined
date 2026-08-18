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
_WITHHELD_RULE_IDS = frozenset(
    {
        "LX0609-025",
        "LX0609-028",
        "LX0609-049",
        "LX0609-056",
        "LX0609-059",
        "LX0609-075",
    }
)
_CATALOG_RULE_IDS = tuple(
    contract.rule_id for contract in benchmark20.load_luxian_0609_rule_contracts()
)


def test_rule_attestations_use_authoritative_executable_phase_scope():
    rule_ids, executor_types = benchmark20._rule_attestations()

    assert rule_ids == tuple(
        f"LX0609-{index:03d}"
        for index in range(1, 76)
        if f"LX0609-{index:03d}" not in _WITHHELD_RULE_IDS
    )
    assert len(rule_ids) == 69
    assert not set(rule_ids).intersection(_WITHHELD_RULE_IDS)
    assert set(executor_types) == set(rule_ids)
    assert sum(item == "program" for item in executor_types.values()) == 47
    assert sum(item == "llm" for item in executor_types.values()) == 22


@pytest.mark.parametrize("rule_id", sorted(_WITHHELD_RULE_IDS))
def test_selected_scope_rejects_withheld_rule(rule_id):
    with pytest.raises(BenchmarkContractError, match="invalid selected rule scope"):
        benchmark20._select_rule_attestations((rule_id,))


def _usage_attributions(rule_ids: tuple[str, ...]) -> list[dict]:
    program_rule_ids = [
        rule_id for rule_id in rule_ids if rule_id in _DETERMINISTIC_RULE_IDS
    ]
    semantic_rule_ids = [
        rule_id for rule_id in rule_ids if rule_id in _SEMANTIC_RULE_IDS
    ]
    items: list[dict] = []
    if program_rule_ids:
        items.append(
            {
                "executor_key": "programmatic",
                "llm_call_count": 0,
                "prompt_tokens": 0,
                "completion_tokens": 0,
                "total_tokens": 0,
                "covered_customer_rule_ids": program_rule_ids,
                "latency_ms": 0.0,
            }
        )
    if semantic_rule_ids:
        items.append(
            {
                "executor_key": "semantic",
                "llm_call_count": 1,
                "prompt_tokens": 10,
                "completion_tokens": 2,
                "total_tokens": 12,
                "covered_customer_rule_ids": semantic_rule_ids,
                "latency_ms": 5.0,
            }
        )
    return items


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
        "customer_rule_count": len(_CATALOG_RULE_IDS),
        "flags": {},
        "rule_set": {
            "key": "luxian_0609_qc_v1",
            "version": "2026-06-09",
            "rule_count": len(_CATALOG_RULE_IDS),
            "rule_ids": list(_CATALOG_RULE_IDS),
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
            "rule_id": rule_id,
            "status": "compliant",
            "metadata": {
                "reason_code": "verified",
            },
            "evidence_items": [],
            "findings": "PRIVATE-BODY-MARKER",
        }
        for rule_id in _RULE_IDS
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
            "rule_decision_count": len(_RULE_IDS),
            "typed_shadow_adapter_count": 0,
            "legacy_projection_count": 0,
            "usage_complete": True,
            "usage_error_reason": "",
            "unattributed_prompt_tokens": 0,
            "unattributed_completion_tokens": 0,
            "unattributed_total_tokens": 0,
            "api_time_seconds": 0.005,
            "usage_attributions": _usage_attributions(_RULE_IDS),
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
    has_semantic = any(rule_id in _SEMANTIC_RULE_IDS for rule_id in rule_ids)
    response["metrics"].update(
        {
            "llm_call_count": 1 if has_semantic else 0,
            "prompt_tokens": 10 if has_semantic else 0,
            "completion_tokens": 2 if has_semantic else 0,
            "total_tokens": 12 if has_semantic else 0,
            "usage_attributions": _usage_attributions(rule_ids),
            "api_time_seconds": 0.005 if has_semantic else 0.0,
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
                "rule_id": rule_id,
                "evidence_hash": hashlib.sha256(
                    f"{salt}:{rule_id}".encode()
                ).hexdigest(),
                "observed_state": state_overrides.get(rule_id, "compliant"),
                "reason_code": reason_overrides.get(rule_id, "verified"),
            }
            for rule_id in _RULE_IDS
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
    """锁定当前可执行规则的权威契约分类。"""

    rows = candidate["rows"]
    assert len(_DETERMINISTIC_RULE_IDS) == 47
    assert len(_SEMANTIC_RULE_IDS) == 22
    assert len(rows) == 20 * len(_RULE_IDS)
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
        row["decision_kind"] == "semantic"
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
        selected == _RULE_IDS for selected in runner_calls
    )
    assert batch["schema_version"] == "lx0609-golden-api-batch-v1"
    assert [case["case_label"] for case in batch["cases"]] == [
        f"case-{index:02d}" for index in range(1, 21)
    ]
    assert batch["summary"]["case_count"] == 20
    assert batch["summary"]["judgment_count"] == 1380
    assert batch["summary"]["status_counts"] == {"compliant": 1380}
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
        "rule_decision_count": 69,
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
    assert candidate["candidate_count"] == 1380
    _assert_candidate_decision_kind_contract(candidate)
    attestation_hashes = [
        evidence_hash
        for case in batch["cases"]
        for evidence_hash in case["evidence_attestations"].values()
    ]
    assert len(attestation_hashes) == len(set(attestation_hashes)) == 1380
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
        }
        for case in batch["cases"]
        for result in case["response"]["results"]
    )


@pytest.mark.asyncio
async def test_benchmark20_counts_one_family_call_once_while_covering_multiple_rules():
    selected_rule_ids = ("LX0609-010", "LX0609-011")
    call_numbers = count(1)

    async def fake_runner(**kwargs):
        _emit_selected_attestations(
            kwargs,
            salt=f"family-usage-{next(call_numbers)}",
        )
        response = _selected_safe_response(selected_rule_ids)
        response["metrics"].update(
            {
                "usage_complete": True,
                "usage_error_reason": "",
                "unattributed_prompt_tokens": 0,
                "unattributed_completion_tokens": 0,
                "unattributed_total_tokens": 0,
                "usage_attributions": [
                    {
                        "executor_key": "mixed_family",
                        "llm_call_count": 1,
                        "prompt_tokens": 10,
                        "completion_tokens": 2,
                        "total_tokens": 12,
                        "covered_customer_rule_ids": [
                            "LX0609-010",
                            "LX0609-011",
                        ],
                        "latency_ms": 5.0,
                    },
                ],
            }
        )
        return response

    batch = await build_benchmark_batch(
        case_map=_case_map(),
        evaluation_as_of_date="2026-07-24",
        bundle_loader=lambda **kwargs: {"scene": kwargs["scene"]},
        runner=fake_runner,
        llm_client=object(),
        base_settings=SimpleNamespace(),
        selected_rule_ids=selected_rule_ids,
    )

    assert batch["summary"]["total_tokens"] == 20 * 12
    for case in batch["cases"]:
        safe_response = case["response"]
        assert safe_response["metrics"]["usage_attributions"][0][
            "covered_customer_rule_ids"
        ] == ["LX0609-010", "LX0609-011"]
        assert all(
            not {"prompt_tokens", "completion_tokens", "total_tokens"}
            & set(result["metadata"])
            for result in safe_response["results"]
        )
    candidate = build_candidate_ledger(
        batch,
        candidate_version="family-usage-v2",
        generated_at="2026-07-24T00:00:00Z",
    )
    by_rule = {
        row["rule_id"]: row
        for row in candidate["rows"]
        if row["case_label"] == "case-01"
    }
    assert by_rule["LX0609-010"]["total_tokens"] == 12
    assert by_rule["LX0609-011"]["total_tokens"] == 12


@pytest.mark.asyncio
async def test_benchmark20_rejects_incomplete_unattributed_and_latency_accounting():
    call_numbers = count(1)

    async def fake_runner(**kwargs):
        _emit_attestations(
            kwargs,
            salt=f"latency-accounting-{next(call_numbers)}",
        )
        response = _safe_response()
        response["metrics"]["api_time_seconds"] = 99.0
        return response

    with pytest.raises(BenchmarkContractError, match="usage attribution"):
        await build_benchmark_batch(
            case_map=_case_map(),
            evaluation_as_of_date="2026-07-24",
            bundle_loader=lambda **kwargs: {"scene": kwargs["scene"]},
            runner=fake_runner,
            llm_client=object(),
            base_settings=SimpleNamespace(),
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
@pytest.mark.parametrize(
    "failure_kind",
    (
        "missing",
        "arithmetic",
        "usage_incomplete",
        "unattributed",
        "unattributed_prompt",
        "unattributed_completion",
        "duplicate_executor",
        "unknown_coverage",
        "duplicate_coverage",
        "boolean",
        "latency_boolean",
    ),
)
async def test_benchmark20_fails_closed_for_family_usage_attribution(
    failure_kind: str,
):
    async def fake_runner(**kwargs):
        _emit_attestations(kwargs, salt=f"token-{failure_kind}")
        response = _safe_response()
        if failure_kind == "missing":
            response["metrics"].pop("usage_attributions")
        elif failure_kind == "arithmetic":
            response["metrics"]["usage_attributions"][-1]["total_tokens"] = 11
        elif failure_kind == "usage_incomplete":
            response["metrics"]["usage_complete"] = False
            response["metrics"]["usage_error_reason"] = "usage_incomplete"
        elif failure_kind == "unattributed":
            response["metrics"]["unattributed_total_tokens"] = 1
        elif failure_kind == "unattributed_prompt":
            response["metrics"]["unattributed_prompt_tokens"] = 1
        elif failure_kind == "unattributed_completion":
            response["metrics"]["unattributed_completion_tokens"] = 1
        elif failure_kind == "duplicate_executor":
            duplicate = dict(response["metrics"]["usage_attributions"][0])
            duplicate["covered_customer_rule_ids"] = ["LX0609-001"]
            response["metrics"]["usage_attributions"].append(duplicate)
        elif failure_kind == "unknown_coverage":
            response["metrics"]["usage_attributions"][0][
                "covered_customer_rule_ids"
            ][0] = "LX0609-999"
        elif failure_kind == "duplicate_coverage":
            response["metrics"]["usage_attributions"][0][
                "covered_customer_rule_ids"
            ].append(
                response["metrics"]["usage_attributions"][0][
                    "covered_customer_rule_ids"
                ][0]
            )
        elif failure_kind == "boolean":
            response["metrics"]["usage_attributions"][-1]["prompt_tokens"] = False
        else:
            response["metrics"]["api_time_seconds"] = False
        return response

    with pytest.raises(BenchmarkContractError, match="usage attribution"):
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
        *((rule_id,) for rule_id in sorted(_WITHHELD_RULE_IDS)),
        ("LX0609-999",),
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
        "compliant": 1360,
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
                authority if index == 74 else "program_only"
            ),
            phase_status=(
                "pending_definition"
                if f"LX0609-{index:03d}" in _WITHHELD_RULE_IDS
                else "phase_1_target"
            ),
        )
        for index in range(1, 76)
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
            "judgment_count": 1360,
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
