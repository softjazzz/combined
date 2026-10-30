"""Strata P0 只读观测：未知不补零，分组不充当 Token checkpoint。"""

from collections import defaultdict
from contextlib import contextmanager
from contextvars import ContextVar
from copy import deepcopy
import json
import math
import time
from typing import Mapping


_COLLECTOR = ContextVar("strata_observation_collector", default=None)
_COST_FIELDS = (
    "nominal_input_tokens", "cached_tokens", "prefill_tokens", "output_tokens",
    "prefill_ms", "decode_ms", "queue_ms", "transport_ms", "wall_ms",
    "model_requests_started", "unknown_usage_request_count",
)


def _mapping(value):
    return value if isinstance(value, Mapping) else {}


def _number(value, *, integer=False):
    if type(value) not in ((int,) if integer else (int, float)):
        return None
    try:
        valid = value >= 0 and math.isfinite(value)
    except OverflowError:
        valid = False
    if not valid:
        return None
    return value


def _milliseconds(value):
    seconds = _number(value)
    return _number(seconds * 1000) if seconds is not None else None


def parse_strata_metrics(result, *, wall_ms, transport=None, gateway=False):
    """保留不同 API 来源；不以 input-cached 推算实际 Prefill。"""
    raw = _mapping(result)
    usage, timings = _mapping(raw.get("usage")), _mapping(raw.get("timings"))
    details = _mapping(usage.get("prompt_tokens_details"))
    nominal = _number(usage.get("prompt_tokens"), integer=True)
    cached_usage = _number(details.get("cached_tokens"), integer=True)
    cached_timing = _number(timings.get("cache_n"), integer=True)
    read = _number(timings.get("prompt_n"), integer=True)
    output = _number(usage.get("completion_tokens"), integer=True)
    predicted = _number(timings.get("predicted_n"), integer=True)
    issues = []
    cached = cached_timing if cached_timing is not None else cached_usage
    if cached_usage is not None and cached_timing is not None and cached_usage != cached_timing:
        cached = None
        issues.append("cached_sources_conflict")
    if cached is not None and nominal is not None and cached > nominal:
        cached = None
        issues.append("cached_exceeds_nominal")
    output_conflict = output is not None and predicted is not None and output != predicted
    if output_conflict:
        issues.append("output_sources_conflict")
    observed_output = None if output_conflict else output if output is not None else predicted
    delta = nominal - cached - read if all(x is not None for x in (nominal, cached, read)) else None
    if delta not in (None, 0):
        issues.append("token_accounting_delta")
    queue, http, requests, unknown_usage = None, None, None, None
    transport_complete = None
    if gateway:
        stage = _mapping(raw.get("_gateway_timing"))
        queue_seconds = _number(stage.get("queue_seconds"))
        http_seconds = _number(stage.get("http_seconds"))
        queue = _milliseconds(queue_seconds)
        http = _milliseconds(http_seconds)
        # Gateway 当前无内部 HTTP 重试；有效 timing 表示一次 sender 已完成。
        if queue is not None and http is not None:
            requests, transport_complete = 1, True
    elif _mapping(transport).get("observed") is True:
        queue = _number(transport.get("queue_ms"))
        http = _number(transport.get("transport_ms"))
        requests = _number(transport.get("requests_started"), integer=True)
        transport_complete = transport.get("complete") is True
    if requests is not None:
        # direct 内部断连重发的早先请求没有 usage，不得只用最终响应冒充全部成本。
        known_response = int(nominal is not None and observed_output is not None)
        unknown_usage = max(0, requests - known_response)
    return {
        "nominal_input_tokens": nominal, "cache_tokens_usage": cached_usage,
        "cache_tokens_timing": cached_timing, "cached_tokens": cached,
        "prefill_tokens": read, "output_tokens": observed_output,
        "usage_output_tokens": output, "timing_output_tokens": predicted,
        "prefill_ms": _number(timings.get("prompt_ms")),
        "decode_ms": _number(timings.get("predicted_ms")),
        "queue_ms": queue, "transport_ms": http, "wall_ms": _number(wall_ms),
        "model_requests_started": requests, "unknown_usage_request_count": unknown_usage,
        "transport_complete": transport_complete, "token_accounting_delta": delta,
        "cache_state": "unknown" if cached is None else "reported_hit" if cached else "reported_miss",
        "cache_invalidation": "unknown", "token_reuse_verified": False, "issues": issues,
    }


def describe_strata_request(payload, *, scope_key, route_key, digest):
    """只对最终发送消息的精确内容分组，不改变/存储正文，不把字符当 Token。"""
    result = {"input_group_key": None, "leading_messages_key": None,
              "evidence_projection_key": None, "producer_kind": "unclassified",
              "current_prefix_state": "scope_or_shape_unavailable"}
    messages = payload.get("messages")
    if not scope_key or not isinstance(messages, list) or not messages:
        return result
    if len(messages) > 32 or any(not isinstance(item, dict) or not isinstance(item.get("content"), str)
                                 for item in messages):
        return result
    if sum(len(item["content"]) for item in messages) > 262144:
        result["current_prefix_state"] = "not_analyzed_oversize"
        return result
    template = {key: payload[key] for key in (
        "model", "chat_template_kwargs", "enable_thinking", "thinking", "thinking_budget",
        "response_format", "reasoning_effort",
    ) if key in payload}

    def key(kind, value):
        return digest(json.dumps([scope_key, route_key, template, kind, value],
                                 sort_keys=True, ensure_ascii=False, allow_nan=False))

    result["input_group_key"] = key("input", messages)
    result["current_prefix_state"] = "single_message_no_shared_message_boundary"
    if len(messages) > 1:
        result["leading_messages_key"] = key("head", messages[:-1])
        result["current_prefix_state"] = "message_head_candidate_unverified"
    # 仅盘点已审查的生产者格式；此处不拆消息、不生成 PrefixPlan、不建立 checkpoint。
    known = (
        ("你核对报告出具后的病程是否记录了本次CT/MRI报告的结果", "exam_result_record"),
        ("你核对病程是否针对本次CT/MRI报告的异常作出实质分析", "exam_finding_analysis"),
        ("你核对CT/MRI检查开立前的病程", "exam_reason"),
    )
    for message in messages:
        text = message["content"]
        for start, name in known:
            if not text.startswith(start):
                continue
            result["producer_kind"] = name
            _, sep, evidence = text.rpartition("\nEVENTS_JSON=")
            if sep:
                try:
                    parsed = json.loads(evidence)
                except (ValueError, TypeError):
                    continue
                if isinstance(parsed, dict) and isinstance(parsed.get("events"), list):
                    result["evidence_projection_key"] = key("evidence_projection", evidence)
    return result


class StrataObservationCollector:
    """显式诊断作用域内的有界、安全事件集合；生产默认仅输出结构化日志。"""
    def __init__(self, *, max_events=1000):
        if type(max_events) is not int or not 1 <= max_events <= 10000:
            raise ValueError("invalid observation limit")
        self.max_events = max_events
        self.started_at = time.perf_counter()
        self.events = []
        self.dropped_events = 0

    def add(self, event):
        if len(self.events) >= self.max_events:
            self.dropped_events += 1
        else:
            self.events.append(deepcopy(event))

    def report(self):
        cost = {}
        for field in _COST_FIELDS:
            values = [event.get("metrics", {}).get(field) for event in self.events]
            total = sum(value for value in values if value is not None)
            cost[field] = {"known_sum": _number(total),
                           "unknown_count": sum(value is None for value in values)}
            if _number(total) is None:
                cost[field]["sum_issue"] = "numeric_overflow"
        groups = {}
        for field, label in (("input_group_key", "identical_input"),
                             ("leading_messages_key", "leading_messages_candidates"),
                             ("evidence_projection_key", "evidence_projection_candidates")):
            buckets = defaultdict(list)
            for event in self.events:
                key = event.get("groups", {}).get(field)
                if key:
                    buckets[key].append(event)
            groups[label] = [
                {"group_key": key, "attempt_count": len(items),
                 "logical_call_count": len({x.get("logical_call_id") for x in items}),
                 "executors": sorted({x.get("executor_key", "unknown") for x in items})}
                for key, items in sorted(buckets.items()) if len(items) > 1
            ]
        return {"schema_version": "strata_p0_report_v1", "complete": not self.dropped_events,
                "scope": "observed_attempts_only",
                "collection_wall_ms": max(0, (time.perf_counter() - self.started_at) * 1000),
                "cost_duration_semantics": "summed_attempt_wall_is_not_batch_wall",
                "attempt_count": len(self.events),
                "logical_call_count": len({x.get("logical_call_id") for x in self.events}),
                "failed_attempts": sum(x.get("status") != "success" for x in self.events),
                "cost_complete": bool(self.events) and not self.dropped_events and all(
                    item["known_sum"] is not None and item["unknown_count"] == 0
                    for item in cost.values()
                ) and all(x.get("metrics", {}).get("transport_complete") is True for x in self.events),
                "pending_transport_attempts": sum(
                    x.get("metrics", {}).get("transport_complete") is False for x in self.events
                ),
                "prime_requests_started": 0, "currency_cost": None,
                "currency_cost_reason": "local_compute_price_not_configured",
                "cost": cost, "groups": groups, "token_reuse_verified": False,
                "dropped_events": self.dropped_events}


@contextmanager
def capture_strata_observations(*, max_events=1000):
    collector = StrataObservationCollector(max_events=max_events)
    token = _COLLECTOR.set(collector)
    try:
        yield collector
    finally:
        _COLLECTOR.reset(token)


def collect_strata_observation(event):
    collector = _COLLECTOR.get()
    if collector is not None:
        collector.add(event)
