"""Prime成本独立于医学逻辑调用，未知或畸形trace不能冒充零成本。"""

from copy import deepcopy
import json
import time

import pytest

from app.services.llm_observability import LLMObservabilityRecorder, NullLLMCallEventStore
from app.services.strata_observation import (
    StrataObservationCollector, capture_strata_observations,
    expand_strata_cache_cost_events, parse_strata_metrics,
)


def trace(**changes):
    result = {
        "strategy": "primed", "prime_requests_started": 1, "rule_requests_started": 1,
        "prime_metrics": {
            "nominal_input_tokens": 900, "cached_tokens": 0, "prefill_tokens": 900,
            "output_tokens": 1, "prefill_ms": 30., "decode_ms": 1.,
            "queue_ms": 5., "transport_ms": 40., "wall_ms": 45.,
        }, "prime_error_code": None,
    }
    result.update(changes)
    return result


def response(**changes):
    result = {
        "choices": [{"message": {"content": '{"clinical":"unchanged"}'}, "finish_reason": "stop"}],
        "usage": {"prompt_tokens": 1000, "completion_tokens": 20,
                  "prompt_tokens_details": {"cached_tokens": 900}},
        "timings": {"cache_n": 900, "prompt_n": 100, "predicted_n": 20,
                    "prompt_ms": 4., "predicted_ms": 20.},
        "_gateway_timing": {"queue_seconds": .002, "http_seconds": .03},
        "_strata_cache": trace(),
    }
    result.update(changes)
    return result


def rule_event(result=None):
    return {"event_id": "rule-event", "logical_call_id": "logical-a", "attempt_no": 1,
            "purpose": "rule", "status": "success", "groups": {"input_group_key": "case-group"},
            "metrics": parse_strata_metrics(result or response(), wall_ms=100., gateway=True)}


def test_prime_and_rule_costs_are_distinct_without_changing_the_response():
    raw = response()
    original = deepcopy(raw)
    events = expand_strata_cache_cost_events(rule_event(raw), raw, gateway=True)
    assert raw == original
    assert [event["purpose"] for event in events] == ["prime", "rule"]
    assert len({event["event_id"] for event in events}) == 2
    assert events[0]["parent_event_id"] == events[1]["event_id"]
    assert events[0]["logical_call_id"] == events[1]["logical_call_id"]
    collector = StrataObservationCollector()
    for event in events:
        collector.add(event)
    report = collector.report()
    assert report["logical_call_count"] == 1
    assert report["attempt_count"] == 2
    assert report["rule_attempt_count"] == 1 and report["prime_attempt_count"] == 1
    assert report["failed_rule_attempts"] == report["failed_prime_attempts"] == 0
    assert report["prime_requests_started"] == 1
    assert report["cost"]["model_requests_started"]["known_sum"] == 2
    assert report["cost"]["nominal_input_tokens"]["known_sum"] == 1900
    assert report["cost"]["output_tokens"]["known_sum"] == 21
    assert report["cost"]["queue_ms"]["known_sum"] == 7.
    assert report["cost"]["transport_ms"]["known_sum"] == 70.
    # 规则client wall已包含Prime，不能再加45ms。
    assert report["cost"]["wall_ms"]["known_sum"] == 100.
    assert report["prime_wall_ms"]["known_sum"] == 45.
    assert report["cost_complete"] is True


@pytest.mark.parametrize("marker", ["_strata_cache_invalid", "_strata_cache_expected"])
def test_missing_or_invalid_trace_makes_prime_and_total_cost_unknown(marker):
    raw = {marker: True}
    events = expand_strata_cache_cost_events(rule_event(), raw, gateway=True)
    collector = StrataObservationCollector()
    for event in events:
        collector.add(event)
    report = collector.report()
    assert report["prime_requests_started"] is None
    assert report["cost_complete"] is False
    assert report["cost"]["model_requests_started"]["unknown_count"] == 2
    assert report["cost"]["nominal_input_tokens"]["unknown_count"] == 1
    assert events[0]["status"] == "unknown"


@pytest.mark.parametrize("bad", [
    None, {"strategy": "primed"},
    trace(prime_requests_started=True), trace(prime_requests_started="1"),
    trace(prime_metrics={"nominal_input_tokens": -1}),
    trace(prime_metrics={"prefill_ms": float("nan")}),
    trace(secret="must-not-log"),
])
def test_bad_trace_is_not_normalized_into_known_zero(bad):
    raw = {"_strata_cache": bad}
    events = expand_strata_cache_cost_events(rule_event(), raw, gateway=True)
    assert events[1]["cache_trace_state"] == "invalid"
    assert events[0]["metrics"]["model_requests_started"] is None
    assert "must-not-log" not in json.dumps(events)


def test_prime_failure_records_attempt_and_unknown_usage_not_zero():
    raw = {"_strata_cache": trace(strategy="prime_failed", prime_metrics=None,
                                    prime_error_code="gateway_provider_rejected")}
    events = expand_strata_cache_cost_events(rule_event(), raw, gateway=True)
    prime = events[0]
    assert prime["status"] == "failed"
    assert prime["metrics"]["model_requests_started"] == 1
    assert prime["metrics"]["unknown_usage_request_count"] == 1
    assert prime["metrics"]["nominal_input_tokens"] is None
    collector = StrataObservationCollector()
    for event in events:
        collector.add(event)
    report = collector.report()
    assert report["failed_prime_attempts"] == 1 and report["failed_rule_attempts"] == 0


def test_reused_checkpoint_adds_no_prime_event_and_old_gateway_keeps_p0_behavior():
    raw = response(_strata_cache=trace(strategy="reused", prime_requests_started=0, prime_metrics=None))
    events = expand_strata_cache_cost_events(rule_event(), raw, gateway=True)
    assert len(events) == 1
    assert events[0]["purpose"] == "rule"
    old = rule_event()
    assert expand_strata_cache_cost_events(old, {}, gateway=True) == [old]
    # direct Provider不能伪造Gateway成本元数据。
    assert expand_strata_cache_cost_events(old, response(), gateway=False) == [old]


def test_recorder_emits_safe_prime_and_rule_events_without_saving_extra_clinical_results(caplog):
    raw = response()
    recorder = LLMObservabilityRecorder(store=NullLLMCallEventStore())
    with capture_strata_observations() as captured, caplog.at_level("INFO"):
        recorder.record_strata_attempt(
            event_id="event-a", logical_call_id="call-a", attempt_no=1,
            model="synthetic", model_role="first_pass",
            payload={"messages": [{"role": "user", "content": "private-synthetic-evidence"}]},
            result=raw, status="success", started_timestamp=time.perf_counter(),
            gateway=True, route_key="private-endpoint", transport=None,
        )
    assert [event["purpose"] for event in captured.events] == ["prime", "rule"]
    assert captured.report()["prime_requests_started"] == 1
    assert "private-synthetic-evidence" not in caplog.text
    assert "private-endpoint" not in caplog.text
    assert "clinical" not in caplog.text
