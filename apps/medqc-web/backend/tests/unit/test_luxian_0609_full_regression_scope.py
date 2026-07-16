from __future__ import annotations

from types import SimpleNamespace

import pytest

from scripts.run_luxian_0609_fixed10_readonly import (
    EXPECTED_LUXIAN_0609_RULE_IDS,
    build_safe_rule_states,
    evaluate_full_luxian_0609_case,
    evaluate_snapshot_sidecar_ab_case,
    evaluate_unified_engine_ab_case,
    parse_args,
    resolve_full_luxian_0609_rule_ids,
    validate_full_luxian_0609_results,
)


def test_full_regression_accepts_explicit_assert_49_cli_contract() -> None:
    args = parse_args(["--assert-49", "--snapshot-sidecar-ab"])
    assert args.assert_49 is True
    assert args.snapshot_sidecar_ab is True

    unified_args = parse_args(["--assert-49", "--unified-engine-ab"])
    assert unified_args.assert_49 is True
    assert unified_args.unified_engine_ab is True

    with pytest.raises(SystemExit):
        parse_args(["--snapshot-sidecar-ab", "--unified-engine-ab"])


@pytest.mark.asyncio
async def test_snapshot_sidecar_ab_replays_same_model_response_and_counts_one_snapshot(
    monkeypatch,
) -> None:
    from app.services.luxian_0609 import execution as luxian_execution

    original_calls = 0

    async def generate(_prompt):
        nonlocal original_calls
        original_calls += 1
        return {
            "choices": [{"message": {"content": "stable"}}],
            "usage": {"total_tokens": 11},
        }

    settings = SimpleNamespace(
        LUXIAN_0609_EVIDENCE_SNAPSHOT_SIDECAR_ENABLED=False
    )
    client = SimpleNamespace(generate=generate)

    class Service:
        adjudicator_client = client

        async def evaluate_running_final_bundle_input(self, **_kwargs):
            response = await self.adjudicator_client.generate("same prompt")
            if settings.LUXIAN_0609_EVIDENCE_SNAPSHOT_SIDECAR_ENABLED:
                luxian_execution.build_luxian_0609_evidence_snapshot()
            assert response["choices"][0]["message"]["content"] == "stable"
            return {
                "evaluation_results": [
                    {"rule_id": rule_id, "status": "compliant"}
                    for rule_id in EXPECTED_LUXIAN_0609_RULE_IDS
                ],
                "token_usage": {"total_tokens": 11},
            }

    monkeypatch.setattr(
        luxian_execution,
        "build_luxian_0609_evidence_snapshot",
        lambda **_kwargs: SimpleNamespace(snapshot_hash="b" * 64),
    )

    comparison = await evaluate_snapshot_sidecar_ab_case(
        service=Service(),
        settings=settings,
        bundle={"scene": "running"},
        rule_ids=EXPECTED_LUXIAN_0609_RULE_IDS,
        timeout_seconds=1.0,
    )

    assert comparison == {
        "states_match": True,
        "tokens_match": True,
        "logical_llm_call_count": 1,
        "snapshot_build_count": 1,
        "result_count": 49,
    }
    assert original_calls == 1


@pytest.mark.asyncio
async def test_unified_engine_ab_replays_same_model_response_and_counts_one_snapshot(
    monkeypatch,
) -> None:
    from app.services.luxian_0609 import execution as luxian_execution

    original_calls = 0

    async def generate(_prompt):
        nonlocal original_calls
        original_calls += 1
        return {
            "choices": [{"message": {"content": "stable"}}],
            "usage": {"total_tokens": 11},
        }

    settings = SimpleNamespace(
        LUXIAN_0609_EVIDENCE_SNAPSHOT_SIDECAR_ENABLED=False,
        LUXIAN_0609_UNIFIED_ENGINE_ENABLED=False,
    )
    client = SimpleNamespace(generate=generate)

    class Service:
        adjudicator_client = client

        async def evaluate_running_final_bundle_input(self, **_kwargs):
            response = await self.adjudicator_client.generate("same prompt")
            if settings.LUXIAN_0609_UNIFIED_ENGINE_ENABLED:
                luxian_execution.build_luxian_0609_evidence_snapshot()
                luxian_execution.bind_and_reduce_luxian_0609_rule_decisions()
            assert response["choices"][0]["message"]["content"] == "stable"
            return {
                "evaluation_results": [
                    {"rule_id": rule_id, "status": "compliant"}
                    for rule_id in EXPECTED_LUXIAN_0609_RULE_IDS
                ],
                "token_usage": {"total_tokens": 11},
            }

    monkeypatch.setattr(
        luxian_execution,
        "build_luxian_0609_evidence_snapshot",
        lambda **_kwargs: SimpleNamespace(snapshot_hash="c" * 64),
    )
    monkeypatch.setattr(
        luxian_execution,
        "bind_and_reduce_luxian_0609_rule_decisions",
        lambda **_kwargs: tuple(
            SimpleNamespace(
                rule_id=rule_id,
                final_state=SimpleNamespace(value="compliant"),
                fact_refs=("d" * 64,),
            )
            for rule_id in (
                "LX0609-001",
                "LX0609-002",
                "LX0609-004",
                "LX0609-005",
                "LX0609-006",
                "LX0609-007",
                "LX0609-008",
                "LX0609-009",
            )
        ),
    )

    comparison = await evaluate_unified_engine_ab_case(
        service=Service(),
        settings=settings,
        bundle={"scene": "running"},
        rule_ids=EXPECTED_LUXIAN_0609_RULE_IDS,
        timeout_seconds=1.0,
    )

    assert comparison == {
        "states_match": True,
        "states_accepted": True,
        "tokens_match": True,
        "logical_llm_call_count": 1,
        "snapshot_build_count": 1,
        "result_count": 49,
        "baseline_family_reader_calls": 0,
        "candidate_family_reader_calls": 0,
        "typed_decision_count": 8,
        "typed_decision_min_fact_ref_count": 1,
        "typed_model_call_count": 0,
        "typed_007_decision_count": 1,
        "typed_007_fact_ref_count": 1,
        "typed_007_model_call_count": 0,
    }
    assert original_calls == 1


def test_full_regression_scope_rejects_empty_rule_ids() -> None:
    with pytest.raises(RuntimeError, match="必须显式包含49个客户规则ID"):
        resolve_full_luxian_0609_rule_ids([])


def test_full_regression_scope_requires_exact_customer_rule_order() -> None:
    inventory = [type("Dependency", (), {"rule_id": rule_id})() for rule_id in EXPECTED_LUXIAN_0609_RULE_IDS]
    assert resolve_full_luxian_0609_rule_ids(inventory) == list(EXPECTED_LUXIAN_0609_RULE_IDS)

    with pytest.raises(RuntimeError, match="必须显式包含49个客户规则ID"):
        resolve_full_luxian_0609_rule_ids(list(reversed(inventory)))


def test_full_regression_results_require_exact_customer_rule_order() -> None:
    rows = [{"rule_id": rule_id} for rule_id in EXPECTED_LUXIAN_0609_RULE_IDS]
    validate_full_luxian_0609_results({"evaluation_results": rows})

    with pytest.raises(RuntimeError, match="结果范围异常"):
        validate_full_luxian_0609_results({"evaluation_results": rows[:-1]})


def test_full_regression_safe_rows_only_keep_customer_rule_states() -> None:
    safe_rows = build_safe_rule_states(
        [
            {
                "rule_id": "LX0609-001",
                "status": "compliant",
                "evidence": "不应由回归摘要输出",
            }
        ]
    )
    assert safe_rows == [{"rule_id": "LX0609-001", "status": "compliant"}]


@pytest.mark.asyncio
async def test_full_regression_passes_explicit_customer_ids_to_public_entry() -> None:
    captured = {}

    class Service:
        async def evaluate_running_final_bundle_input(self, **kwargs):
            captured.update(kwargs)
            return {
                "evaluation_results": [
                    {"rule_id": rule_id} for rule_id in EXPECTED_LUXIAN_0609_RULE_IDS
                ]
            }

    result = await evaluate_full_luxian_0609_case(
        service=Service(),
        bundle={"scene": "running"},
        rule_ids=EXPECTED_LUXIAN_0609_RULE_IDS,
        timeout_seconds=1.0,
    )

    assert captured["rule_ids"] == list(EXPECTED_LUXIAN_0609_RULE_IDS)
    assert captured["rule_ids"]
    assert len(result["evaluation_results"]) == 49


@pytest.mark.asyncio
async def test_full_regression_rejects_empty_scope_before_public_entry() -> None:
    called = False

    class Service:
        async def evaluate_running_final_bundle_input(self, **_):
            nonlocal called
            called = True
            return {}

    with pytest.raises(RuntimeError, match="禁止使用空列表"):
        await evaluate_full_luxian_0609_case(
            service=Service(),
            bundle={"scene": "running"},
            rule_ids=[],
            timeout_seconds=1.0,
        )

    assert called is False
