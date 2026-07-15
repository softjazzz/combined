from __future__ import annotations

import pytest

from scripts.run_luxian_0609_fixed10_readonly import (
    EXPECTED_LUXIAN_0609_RULE_IDS,
    build_safe_rule_states,
    evaluate_full_luxian_0609_case,
    resolve_full_luxian_0609_rule_ids,
    validate_full_luxian_0609_results,
)


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
