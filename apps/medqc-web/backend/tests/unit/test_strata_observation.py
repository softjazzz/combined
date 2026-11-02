"""P0 指标只能观测，不改变请求、临床内容或费用语义。"""

from copy import deepcopy
import json

import pytest

from app.services.strata_observation import (
    StrataObservationCollector,
    describe_strata_request,
    parse_strata_metrics,
)


def response():
    return {
        "usage": {"prompt_tokens": 1000, "completion_tokens": 20,
                  "prompt_tokens_details": {"cached_tokens": 800}},
        "timings": {"cache_n": 800, "prompt_n": 200, "prompt_ms": 25.5,
                    "predicted_n": 20, "predicted_ms": 100.0},
        "_gateway_timing": {"queue_seconds": .2, "http_seconds": .5},
    }


def describe(payload, *, case="case-a", route="route-a"):
    return describe_strata_request(
        payload, scope_key=case, route_key=route,
        digest=lambda value: __import__("hashlib").sha256(value.encode()).hexdigest(),
    )


def test_reports_separate_source_metrics_without_mutation_or_adding_durations():
    raw = response()
    before = deepcopy(raw)
    metrics = parse_strata_metrics(raw, wall_ms=900, transport=None, gateway=True)
    assert raw == before
    assert metrics["nominal_input_tokens"] == 1000
    assert metrics["cached_tokens"] == 800
    assert metrics["prefill_tokens"] == 200
    assert metrics["prefill_ms"] == 25.5
    assert metrics["decode_ms"] == 100
    assert metrics["queue_ms"] == 200
    assert metrics["transport_ms"] == 500
    assert metrics["wall_ms"] == 900
    assert metrics["cache_state"] == "reported_hit"
    assert metrics["token_reuse_verified"] is False


def test_missing_is_unknown_not_zero_or_inferred_by_subtraction():
    metrics = parse_strata_metrics({"usage": {"prompt_tokens": 1000}}, wall_ms=1)
    assert metrics["prefill_tokens"] is None
    assert metrics["cached_tokens"] is None
    assert metrics["decode_ms"] is None
    assert metrics["queue_ms"] is None
    assert metrics["cache_state"] == "unknown"


def test_conflicting_cached_sources_are_kept_and_not_chosen_silently():
    raw = response()
    raw["timings"]["cache_n"] = 700
    result = parse_strata_metrics(raw, wall_ms=1)
    assert result["cache_tokens_usage"] == 800
    assert result["cache_tokens_timing"] == 700
    assert result["cached_tokens"] is None
    assert result["cache_state"] == "unknown"
    assert "cached_sources_conflict" in result["issues"]


@pytest.mark.parametrize("bad", [True, -1, "8", float("nan"), float("inf"), {}, []])
def test_malformed_tokens_and_milliseconds_do_not_break_observation(bad):
    raw = {"usage": {"prompt_tokens": bad}, "timings": {"cache_n": bad, "prompt_ms": bad}}
    metrics = parse_strata_metrics(raw, wall_ms=2)
    assert metrics["nominal_input_tokens"] is None
    assert metrics["cache_tokens_timing"] is None
    assert metrics["prefill_ms"] is None
    json.dumps(metrics, allow_nan=False)


def test_token_delta_is_visible_without_manufacturing_a_new_read_count():
    raw = response()
    raw["timings"]["prompt_n"] = 193
    metrics = parse_strata_metrics(raw, wall_ms=1)
    assert metrics["prefill_tokens"] == 193
    assert metrics["token_accounting_delta"] == 7
    assert metrics["token_reuse_verified"] is False


def test_conflicting_output_sources_keep_cost_unknown():
    raw = response()
    raw["timings"]["predicted_n"] = 99
    metrics = parse_strata_metrics(raw, wall_ms=1, gateway=True)
    assert metrics["output_tokens"] is None
    assert metrics["usage_output_tokens"] == 20
    assert metrics["timing_output_tokens"] == 99
    assert metrics["unknown_usage_request_count"] == 1


def test_oversized_numeric_metrics_are_rejected_without_overflow():
    assert parse_strata_metrics({"usage": {"prompt_tokens": 10 ** 400}}, wall_ms=1)["nominal_input_tokens"] is None


def test_gateway_seconds_overflow_remains_unknown_without_losing_other_metrics():
    raw = response()
    raw["_gateway_timing"]["queue_seconds"] = 1e308
    metrics = parse_strata_metrics(raw, wall_ms=1, gateway=True)
    assert metrics["queue_ms"] is None
    assert metrics["prefill_tokens"] == 200
    json.dumps(metrics, allow_nan=False)


def test_zero_cache_is_reported_miss_not_a_request_failure():
    metrics = parse_strata_metrics({"timings": {"cache_n": 0, "prompt_n": 20}}, wall_ms=1)
    assert metrics["cache_state"] == "reported_miss"


def test_gateway_timing_is_not_accepted_as_direct_transport_evidence():
    metrics = parse_strata_metrics(response(), wall_ms=3, gateway=False)
    assert metrics["queue_ms"] is None
    assert metrics["transport_ms"] is None


def test_current_single_message_only_proves_identical_request_groups():
    payload = {"model": "synthetic-model", "messages": [{"role": "user", "content": "synthetic case"}]}
    first, second = describe(payload), describe(deepcopy(payload))
    assert first == second
    assert first["input_group_key"]
    assert first["leading_messages_key"] is None
    assert first["current_prefix_state"] == "single_message_no_shared_message_boundary"
    assert describe(payload, case="case-b")["input_group_key"] != first["input_group_key"]
    assert describe(payload, route="route-b")["input_group_key"] != first["input_group_key"]


def test_message_head_candidates_require_exact_order_and_template():
    payload = {"model": "m", "messages": [{"role": "system", "content": "fixed"},
               {"role": "user", "content": "case"}, {"role": "user", "content": "rule-a"}],
               "chat_template_kwargs": {"enable_thinking": False}}
    another = deepcopy(payload)
    another["messages"][-1]["content"] = "rule-b"
    a, b = describe(payload), describe(another)
    assert a["leading_messages_key"] == b["leading_messages_key"]
    assert a["input_group_key"] != b["input_group_key"]
    another["messages"][:2] = list(reversed(another["messages"][:2]))
    assert describe(another)["leading_messages_key"] != a["leading_messages_key"]
    another = deepcopy(payload)
    another["chat_template_kwargs"]["enable_thinking"] = True
    assert describe(another)["leading_messages_key"] != a["leading_messages_key"]


def test_unknown_case_and_oversize_input_do_not_enter_shared_groups():
    payload = {"messages": [{"role": "user", "content": "x" * 270000}]}
    assert describe(payload)["input_group_key"] is None
    assert describe({"messages": []}, case=None)["input_group_key"] is None


def test_totals_keep_unknown_cost_and_separate_attempts_from_logical_calls():
    collector = StrataObservationCollector(max_events=3)
    for i in range(2):
        collector.add({"logical_call_id": "call-a", "attempt_no": i + 1,
                       "record_key_hash": "case-a", "status": "success",
                       "metrics": parse_strata_metrics(response() if i else {}, wall_ms=5),
                       "groups": {"input_group_key": "same"}})
    report = collector.report()
    assert report["attempt_count"] == 2
    assert report["logical_call_count"] == 1
    assert report["cost"]["nominal_input_tokens"] == {"known_sum": 1000, "unknown_count": 1}
    assert report["currency_cost"] is None
    assert report["cost_complete"] is False
    assert report["prime_requests_started"] == 0
    assert report["groups"]["identical_input"][0]["attempt_count"] == 2
    assert report["groups"]["identical_input"][0]["logical_call_count"] == 1
    for _ in range(3):
        collector.add({"metrics": {}, "groups": {}})
    assert collector.report()["dropped_events"] == 2
    assert collector.report()["complete"] is False


def test_aggregate_numeric_overflow_is_unknown_and_not_serialized_as_infinity():
    collector = StrataObservationCollector()
    for _ in range(2):
        collector.add({"metrics": {"prefill_ms": 1e308}})
    report = collector.report()
    assert report["cost"]["prefill_ms"]["known_sum"] is None
    assert report["cost"]["prefill_ms"]["sum_issue"] == "numeric_overflow"
    assert report["cost_complete"] is False
    json.dumps(report, allow_nan=False)
