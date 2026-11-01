"""有界的 Strata checkpoint 元数据；不保存医学判断或远端 KV。"""

from __future__ import annotations

import asyncio
from copy import deepcopy
from dataclasses import dataclass
import hashlib
import json
import time

from app.services.llm_dispatch.contracts import GatewayCacheTrace, GatewayPrimeMetrics
from .admission import AdmissionDeadlineError, AdmissionError, QueueFullError
from .providers import InvalidPayloadError, ProviderError, ProviderHTTPError, ProviderTimeoutError, ProviderTransportError, prepare_provider_payload


@dataclass
class _Entry:
    tokens: int
    expires: float


@dataclass
class _Pending:
    task: asyncio.Task
    waiters: int = 0


class CasePrefixCache:
    def __init__(self, settings):
        self.settings = settings
        self.entries = {}
        self.pending = {}
        self.waiting_by_resource = {}
        self.lock = asyncio.Lock()

    async def close(self):
        async with self.lock:
            tasks = [item.task for item in self.pending.values()]
            for task in tasks:
                task.cancel()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

    @staticmethod
    def _split(payload, spec):
        messages = payload.get("messages")
        if (not isinstance(messages, list) or len(messages) != 1
                or set(messages[0]) != {"role", "content"} or messages[0].get("role") != "user"):
            raise InvalidPayloadError()
        text = messages[0]["content"]
        if not isinstance(text, str) or not spec.prefix_start < len(text) <= 262144:
            raise InvalidPayloadError()
        suffix, prefix = text[:spec.prefix_start], text[spec.prefix_start:]
        if not suffix.strip() or not prefix.strip() or hashlib.sha256(prefix.encode()).hexdigest() != spec.evidence_version:
            raise InvalidPayloadError()
        return prefix, suffix

    def _key(self, profile, payload, spec):
        identity = [profile.resource_id, profile.name, profile.provider_code, profile.model,
                    profile.api_endpoint, self.settings.cache_deployment_version,
                    spec.case_key, spec.evidence_version, spec.context_version,
                    {key: payload.get(key) for key in ("chat_template_kwargs", "enable_thinking", "thinking_budget", "thinking", "reasoning_effort", "response_format")}]
        return hashlib.sha256(json.dumps(identity, sort_keys=True, allow_nan=False).encode()).hexdigest()

    @staticmethod
    def _metrics(response, elapsed):
        # API 字段互相独立；不从名义输入相减制造实读或耗时。
        usage = response.get("usage") if isinstance(response.get("usage"), dict) else {}
        timings = response.get("timings") if isinstance(response.get("timings"), dict) else {}
        gateway = response.get("_gateway_timing", {})
        def integer(value):
            return value if type(value) is int and 0 <= value <= 2 ** 63 - 1 else None
        def number(value):
            import math
            return value if type(value) in (int, float) and 0 <= value <= 1e12 and math.isfinite(value) else None
        cached = integer(timings.get("cache_n"))
        details = usage.get("prompt_tokens_details", {})
        other = integer(details.get("cached_tokens")) if isinstance(details, dict) else None
        if cached is None:
            cached = other
        elif other is not None and cached != other:
            cached = None
        return GatewayPrimeMetrics(
            nominal_input_tokens=integer(usage.get("prompt_tokens")), cached_tokens=cached,
            prefill_tokens=integer(timings.get("prompt_n")), output_tokens=integer(usage.get("completion_tokens")),
            prefill_ms=number(timings.get("prompt_ms")), decode_ms=number(timings.get("predicted_ms")),
            queue_ms=number(gateway.get("queue_seconds", -1) * 1000),
            transport_ms=number(gateway.get("http_seconds", -1) * 1000), wall_ms=elapsed * 1000,
        )

    async def run(self, completion, profile, invoke, *, deadline):
        spec, original = completion.case_prefix, completion.payload
        prefix, suffix = self._split(original, spec)
        trace = GatewayCacheTrace(strategy="cold", prime_requests_started=0, rule_requests_started=0)
        if profile.provider_code != "strata":
            raise InvalidPayloadError()
        if not self.settings.cache_enabled:
            trace.strategy = "disabled"
            return await self._rule(original, invoke, trace)
        normalized = prepare_provider_payload(profile, original)
        template = normalized.get("chat_template_kwargs", {})
        thinking = normalized.get("thinking", {})
        if (template.get("enable_thinking") is not False
                or isinstance(thinking, dict) and thinking.get("type") == "enabled"):
            # 首版Prime固定关闭思考；不能将不同模板的位点pin到实际规则。
            return await self._rule(original, invoke, trace)
        key = self._key(profile, normalized, spec)
        loop = asyncio.get_running_loop()
        async with self.lock:
            self.entries = {k: entry for k, entry in self.entries.items() if entry.expires > loop.time()}
            entry = self.entries.get(key)
        if entry is not None:
            trace.strategy = "reused"
        elif spec.expected_requests >= 2 and len(prefix) >= 1024:
            entry = await self._prime(key, prefix, original, invoke, trace, deadline, profile.resource_id)
        if entry is None:
            return await self._rule(original, invoke, trace)
        prepared = deepcopy(original)
        prepared["messages"] = [{"role": "user", "content": prefix}, {"role": "user", "content": suffix}]
        prepared["strata_prefix"] = {"tokens": entry.tokens}
        response = await self._rule(prepared, invoke, trace)
        timings = response.get("timings")
        if isinstance(timings, dict) and type(timings.get("cache_n")) is int and timings["cache_n"] == 0:
            async with self.lock:
                if self.entries.get(key) is entry:
                    self.entries.pop(key, None)
        return response

    async def _prime(self, key, prefix, original, invoke, trace, deadline, resource_id):
        async with self.lock:
            ready = self.entries.get(key)
            if ready is not None and ready.expires > asyncio.get_running_loop().time():
                trace.strategy = "reused"
                return ready
            resource = self.settings.resources[resource_id]
            waiting = self.waiting_by_resource.get(resource_id, 0)
            if waiting >= resource.max_inflight + resource.max_queue:
                error = QueueFullError()
                error.cache_trace = trace
                raise error
            pending = self.pending.get(key)
            creator = pending is None
            if creator:
                if len(self.entries) + len(self.pending) >= self.settings.cache_max_entries:
                    trace.strategy = "capacity_bypass"
                    return None
                prime = {"model": original["model"], "messages": [{"role": "user", "content": prefix}],
                         "max_tokens": 1, "temperature": 0.0, "stream": False,
                         "chat_template_kwargs": {"enable_thinking": False}}
                pending = _Pending(asyncio.create_task(self._build(key, prime, invoke)))
                self.pending[key] = pending
            pending.waiters += 1
            self.waiting_by_resource[resource_id] = waiting + 1
        try:
            response, entry, elapsed = await asyncio.wait_for(
                asyncio.shield(pending.task), timeout=max(0, deadline - asyncio.get_running_loop().time()),
            )
            if creator:
                trace.prime_requests_started = 1
                trace.prime_metrics = self._metrics(response, elapsed)
            trace.strategy = "primed" if creator else "reused"
            if entry is None:
                trace.strategy = "prime_failed"
                trace.prime_error_code = "invalid_prime_checkpoint"
            return entry
        except asyncio.TimeoutError:
            trace.prime_requests_started = None if creator else 0
            trace.strategy = "prime_failed"
            trace.prime_error_code = "gateway_deadline_exceeded"
            error = AdmissionDeadlineError()
            error.cache_trace = trace
            raise error from None
        except asyncio.CancelledError as error:
            trace.prime_requests_started = None if creator else 0
            trace.strategy = "prime_failed"
            trace.prime_error_code = "gateway_client_cancelled"
            error.cache_trace = trace
            raise
        except (AdmissionError, ProviderError) as error:
            trace.prime_requests_started = (0 if isinstance(error, AdmissionError) else 1) if creator else 0
            trace.strategy = "prime_failed"
            trace.prime_error_code = error.code
            if isinstance(error, (ProviderTimeoutError, ProviderTransportError, AdmissionError)):
                error.cache_trace = trace
                raise
            return None
        finally:
            async with self.lock:
                pending.waiters -= 1
                self.waiting_by_resource[resource_id] -= 1
                if not self.waiting_by_resource[resource_id]:
                    self.waiting_by_resource.pop(resource_id, None)
                if pending.waiters == 0:
                    if not pending.task.done():
                        pending.task.cancel()
                        await asyncio.gather(pending.task, return_exceptions=True)
                    if self.pending.get(key) is pending:
                        self.pending.pop(key, None)

    async def _build(self, key, prime, invoke):
        started = time.monotonic()
        response = await invoke(prime)
        usage = response.get("usage", {})
        tokens = usage.get("prompt_tokens") if isinstance(usage, dict) else None
        entry = None
        choices = response.get("choices")
        valid = (isinstance(choices, list) and len(choices) == 1 and isinstance(choices[0], dict)
                 and choices[0].get("finish_reason") in {"stop", "length"}
                 and isinstance(choices[0].get("message"), dict)
                 and isinstance(choices[0]["message"].get("content"), str)
                 and response.get("__error__") is not True and not response.get("error"))
        if type(tokens) is int and 1 <= tokens <= 32768 and valid:
            entry = _Entry(tokens, asyncio.get_running_loop().time() + self.settings.cache_ttl_seconds)
            async with self.lock:
                self.entries[key] = entry
        return response, entry, max(0, time.monotonic() - started)

    @staticmethod
    async def _rule(payload, invoke, trace):
        try:
            response = await invoke(payload)
            trace.rule_requests_started = 1
            response = dict(response)
            response["_strata_cache"] = trace.model_dump(mode="json")
            return response
        except BaseException as error:
            trace.rule_requests_started = 0 if isinstance(error, AdmissionError) else 1 if isinstance(error, ProviderHTTPError) else None
            error.cache_trace = trace
            raise
