"""
QC LLM client.

Wraps network calls to LLM API and keeps stats for QC workflows.
"""

from collections.abc import Mapping
from copy import deepcopy
import hashlib
import logging
import re
import time
from typing import Any, Dict, Optional
from urllib.parse import urlparse
from uuid import uuid4

from ..core.http import safe_post_json
from ..core.http_attempt_observation import http_attempt_observation_scope
from ..core.settings import get_settings
from .llm_observability import (
    LLMObservabilityRecorder,
    get_llm_observability_recorder,
    observed_usage,
    safe_status_for_exception,
    safe_status_for_http_result,
)
from .llm_execution_concurrency import concurrency_from_custom_parameters
from .llm_dispatch.client import GatewayDispatchClient
from .llm_dispatch.provider_profiles import (
    ProviderConfigurationError,
    configured_gateway_profile,
    normalize_dispatch_mode,
    strata_is_explicitly_configured,
    validate_gateway_profile,
    validate_provider_code,
)
from .qc_diagnostics.capture import (
    begin_attempt as begin_diagnostic_attempt,
    finish_attempt as finish_diagnostic_attempt,
)

logger = logging.getLogger(__name__)


class SichuanQCLLMClient:
    DEFAULT_MAX_TOKENS = 16384
    THINKING_MIN_MAX_TOKENS = 16384
    THINKING_LARGE_RULES_MAX_TOKENS = 24576
    MAX_TOKENS_HARD_CAP = 32768
    DEEPSEEK_BASE_URL_PREFIX = "https://api.deepseek.com"

    def __init__(
        self,
        config: Optional[Dict[str, Any]] = None,
        *,
        observability_recorder: Optional[LLMObservabilityRecorder] = None,
        gateway_dispatch_client: Optional[GatewayDispatchClient] = None,
    ) -> None:
        if config:
            self.api_endpoint: Optional[str] = config.get("api_endpoint")
            self.api_key: Optional[str] = config.get("api_key")
            self.model: str = config.get("model", "qwen2.5-14b-instruct")
            self.timeout_seconds: int = config.get("timeout_seconds", 120)
            self.allow_mock_when_unconfigured: bool = bool(
                config.get("allow_mock_when_unconfigured", False)
            )
            self.config_source = config.get("source", "unknown")
            self.provider_code: str = (
                str(config.get("provider_code") or "").strip().lower()
            )
            if self.provider_code:
                validate_provider_code(self.provider_code)
            self.dispatch_mode = normalize_dispatch_mode(
                config.get("dispatch_mode", "direct")
            )
            self.gateway_profile: str | None = None
            if self.dispatch_mode == "gateway":
                self.gateway_profile = validate_gateway_profile(
                    profile=config.get("gateway_profile"),
                    provider_code=self.provider_code,
                )
            if self.provider_code == "strata" and (
                not self.api_endpoint or not self.model
            ):
                raise ProviderConfigurationError(
                    "Strata provider is not fully configured"
                )
            self.model_role: str = (
                str(config.get("model_role") or "first_pass").strip() or "first_pass"
            )
            self.adjudicator_model_source: str = str(
                config.get("adjudicator_model_source") or ""
            ).strip()

            custom_params = config.get("custom_parameters", {})
            execution_concurrency = concurrency_from_custom_parameters(custom_params)
            self.max_parallel_records = execution_concurrency.max_parallel_records
            self.family_max_concurrency = execution_concurrency.family_max_concurrency
            self.http_max_concurrency = execution_concurrency.http_max_concurrency
            self.temperature: float = custom_params.get("temperature", 0.2)
            self.top_p: float = custom_params.get("top_p", 0.9)
            self.max_tokens: int = custom_params.get(
                "max_tokens", self.DEFAULT_MAX_TOKENS
            )
            self.enable_thinking: bool = bool(
                custom_params.get("enable_thinking", False)
            )
            self.thinking_budget = custom_params.get("thinking_budget")
            self.reasoning_effort: str = (
                str(custom_params.get("reasoning_effort") or "").strip().lower()
            )

            logger.info(
                "SichuanQCLLMClient custom init: model=%s source=%s temperature=%s top_p=%s max_tokens=%s enable_thinking=%s thinking_budget=%s",
                self.model,
                self.config_source,
                self.temperature,
                self.top_p,
                self.max_tokens,
                self.enable_thinking,
                self.thinking_budget,
            )
        else:
            s = get_settings()
            provider_code = validate_provider_code(s.LLM_DEFAULT_PROVIDER or "alibaba")
            if provider_code == "alibaba":
                self.api_endpoint = (
                    str(s.DASHSCOPE_BASE_URL or s.LLM_API_ENDPOINT or "").strip()
                    or None
                )
                self.api_key = s.DASHSCOPE_API_KEY or s.LLM_API_KEY
            elif provider_code == "deepseek":
                self.api_endpoint = (
                    str(s.DEEPSEEK_API_ENDPOINT or s.LLM_API_ENDPOINT or "").strip()
                    or None
                )
                self.api_key = s.DEEPSEEK_API_KEY or s.LLM_API_KEY
            elif provider_code == "siliconflow":
                self.api_endpoint = (
                    str(s.SILICONFLOW_API_ENDPOINT or s.LLM_API_ENDPOINT or "").strip()
                    or None
                )
                self.api_key = s.SILICONFLOW_API_KEY or s.LLM_API_KEY
            elif provider_code == "ollama":
                self.api_endpoint = (
                    str(s.OLLAMA_API_ENDPOINT or s.LLM_API_ENDPOINT or "").strip()
                    or None
                )
                self.api_key = s.OLLAMA_API_KEY or s.LLM_API_KEY
            elif provider_code == "strata":
                if not strata_is_explicitly_configured(s):
                    raise ProviderConfigurationError(
                        "Strata provider is not fully configured"
                    )
                self.api_endpoint = str(s.STRATA_API_ENDPOINT).strip()
                self.api_key = s.STRATA_API_KEY
            else:
                self.api_endpoint = (
                    str(s.LLM_API_ENDPOINT) if s.LLM_API_ENDPOINT else None
                )
                self.api_key = s.LLM_API_KEY
            self.model = (
                str(s.STRATA_MODEL)
                if provider_code == "strata"
                else s.LLM_MODEL
            )
            self.timeout_seconds = s.LLM_TIMEOUT_SECONDS
            self.allow_mock_when_unconfigured = s.LLM_ALLOW_MOCK_WHEN_UNCONFIGURED
            self.config_source = "env"
            self.provider_code = provider_code
            self.dispatch_mode = normalize_dispatch_mode(
                getattr(s, "LLM_DISPATCH_MODE", "direct")
            )
            self.gateway_profile = None
            if self.dispatch_mode == "gateway":
                self.gateway_profile = validate_gateway_profile(
                    profile=configured_gateway_profile(s, self.provider_code, self.model),
                    provider_code=self.provider_code,
                )
            self.max_parallel_records = int(
                getattr(s, "QC_BATCH_RECORD_MAX_CONCURRENCY", 16)
            )
            self.family_max_concurrency = int(
                getattr(s, "LUXIAN_0609_FAMILY_MAX_CONCURRENCY", 4)
            )
            self.http_max_concurrency = int(
                getattr(s, "LLM_HTTP_MAX_CONCURRENCY", 40)
            )
            self.model_role = "first_pass"
            self.adjudicator_model_source = ""

            self.temperature = 0.2
            self.top_p = 0.9
            self.max_tokens = self.DEFAULT_MAX_TOKENS
            self.enable_thinking = s.LLM_ENABLE_THINKING
            self.thinking_budget = s.LLM_THINKING_BUDGET
            self.reasoning_effort = ""

            logger.info(
                "SichuanQCLLMClient env init: source=%s endpoint_set=%s api_key_set=%s model=%s enable_thinking=%s thinking_budget=%s allow_mock=%s",
                s.llm_env_source() if hasattr(s, "llm_env_source") else "unknown",
                bool(self.api_endpoint),
                bool(self.api_key),
                self.model,
                self.enable_thinking,
                self.thinking_budget,
                self.allow_mock_when_unconfigured,
            )

        from .llm_token_budget import LOCAL, strict_enabled
        self.request_observation_enabled = (
            getattr(get_settings(), "LLM_REQUEST_OBSERVATION_ENABLED", False) is True
            or self.provider_code in LOCAL and strict_enabled()
        )
        self.strata_observation_mode = (
            getattr(get_settings(), "STRATA_CASE_CACHE_MODE", "off")
            if self.provider_code == "strata" else "off"
        )
        if self.strata_observation_mode == "prefix" and self.dispatch_mode != "gateway":
            raise ProviderConfigurationError("Strata prefix mode requires the controlled Gateway")
        self.call_count = 0
        self.total_tokens = 0
        self.total_api_time = 0.0
        self.success_count = 0
        self.error_count = 0
        self._stats_parent: SichuanQCLLMClient | None = None
        self._observability_recorder = (
            observability_recorder or get_llm_observability_recorder()
        )
        self._gateway_dispatch_client = (
            gateway_dispatch_client or GatewayDispatchClient()
        )
        if self.provider_code == "local_openai" and self.dispatch_mode != "gateway":
            raise ProviderConfigurationError("local_openai requires the controlled Gateway")
        self.refresh_dispatch_identity()

    def refresh_dispatch_identity(self) -> None:
        """从当前受控 Settings 刷新非敏感 Gateway 地址身份。"""

        self.gateway_endpoint_sha256: str | None = None
        if self.dispatch_mode == "gateway":
            settings = get_settings()
            self.gateway_profile = validate_gateway_profile(
                profile=self.gateway_profile,
                provider_code=self.provider_code,
            )
            if normalize_dispatch_mode(
                getattr(settings, "LLM_DISPATCH_MODE", "direct")
            ) != "gateway":
                raise ProviderConfigurationError(
                    "LLM gateway dispatch is no longer enabled"
                )
            current_profile = str(
                configured_gateway_profile(settings, self.provider_code, self.model) or ""
            ).strip()
            if current_profile != self.gateway_profile:
                raise ProviderConfigurationError(
                    "LLM gateway profile changed after runtime selection"
                )
            gateway_url = str(
                getattr(settings, "LLM_GATEWAY_URL", "") or ""
            ).strip().rstrip("/")
            if not gateway_url:
                raise ProviderConfigurationError("LLM gateway URL is unavailable")
            self.gateway_endpoint_sha256 = hashlib.sha256(
                gateway_url.encode("utf-8")
            ).hexdigest()

    def _record_stats_delta(
        self, *, calls: int = 0, successes: int = 0, errors: int = 0,
        tokens: int = 0, api_time: float = 0.0,
    ) -> None:
        """保留任务本地用量，并同步到原服务的进程统计。"""

        self.call_count += calls
        self.success_count += successes
        self.error_count += errors
        self.total_tokens += tokens
        self.total_api_time += api_time
        parent = self._stats_parent
        if parent is not None and parent is not self:
            parent._record_stats_delta(
                calls=calls, successes=successes, errors=errors,
                tokens=tokens, api_time=api_time,
            )

    def _build_request_payload(self, prompt, *, max_completion_tokens=None, response_format_payload=None,
                               enable_thinking=None, thinking_budget=None, temperature=None):
        max_tokens = self._resolve_max_tokens(prompt)
        if max_completion_tokens is not None:
            max_tokens = min(max_tokens, max_completion_tokens)
        resolved_enable_thinking = (
            self.enable_thinking if enable_thinking is None else enable_thinking
        )
        resolved_thinking_budget = (
            self.thinking_budget if thinking_budget is None else thinking_budget
        )
        payload = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
            # 调用方可按场景覆盖（如 0609 抽取固定为 0）；未指定时沿用客户端配置。
            "temperature": self.temperature if temperature is None else float(temperature),
            "top_p": self.top_p,
            "max_tokens": max_tokens,
            "stream": False,
        }
        payload.update(
            self._build_provider_specific_payload(
                enable_thinking=resolved_enable_thinking,
                thinking_budget=resolved_thinking_budget,
            )
        )
        if response_format_payload is not None:
            payload["response_format"] = deepcopy(response_format_payload)

        return payload

    def probe_context_budget(self, prompt, *, max_completion_tokens=None, response_format=None,
                             enable_thinking=None, thinking_budget=None, temperature=None, **_):
        from .llm_token_budget import assess_payload, deployed_capability, strict_enabled
        from .luxian_0609.privacy_request_scope import protect_current_payload
        payload = protect_current_payload(self._build_request_payload(prompt,
            max_completion_tokens=max_completion_tokens, response_format_payload=self._copy_response_format(response_format),
            enable_thinking=enable_thinking, thinking_budget=thinking_budget, temperature=temperature))
        profile, capability = deployed_capability(self.provider_code, self.model,
            self.gateway_profile, self.api_endpoint, dispatch_mode=self.dispatch_mode)
        return assess_payload(self.provider_code, profile, payload, capability, enabled=strict_enabled())

    async def generate(
        self,
        prompt: str,
        *,
        max_completion_tokens: int | None = None,
        allow_length_retry: bool = True,
        response_format: Mapping[str, Any] | None = None,
        enable_thinking: bool | None = None,
        thinking_budget: int | None = None,
        temperature: float | None = None,
    ) -> Dict[str, Any]:
        if temperature is not None and (
            isinstance(temperature, bool)
            or not isinstance(temperature, (int, float))
            or not 0 <= temperature <= 2
        ):
            raise ValueError("temperature must be a number between 0 and 2")
        if max_completion_tokens is not None and (
            isinstance(max_completion_tokens, bool)
            or not isinstance(max_completion_tokens, int)
            or max_completion_tokens <= 0
            or max_completion_tokens > self.MAX_TOKENS_HARD_CAP
        ):
            raise ValueError(
                "max_completion_tokens must be a positive integer no greater than "
                f"{self.MAX_TOKENS_HARD_CAP}"
            )
        response_format_payload = self._copy_response_format(response_format)

        self._record_stats_delta(calls=1)
        api_start = time.time()
        logical_call_id = str(uuid4())
        attempt_no = 0
        attempt_usages: list[dict[str, int]] = []

        if self.dispatch_mode == "direct" and not self.api_endpoint:
            if self.allow_mock_when_unconfigured:
                api_time = time.time() - api_start
                self._record_stats_delta(successes=1)
                return {
                    "choices": [
                        {
                            "message": {
                                "content": f"[MOCK RESULT] 分析完成: {prompt[:60]}..."
                            }
                        }
                    ],
                    "usage": {"total_tokens": 0},
                    "_mock": True,
                    "_api_time": api_time,
                }

            self._record_stats_delta(errors=1)
            raise RuntimeError(
                "LLM is not configured. Set endpoint/model in env or database config."
            )

        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        payload = self._build_request_payload(prompt, max_completion_tokens=max_completion_tokens,
            response_format_payload=response_format_payload, enable_thinking=enable_thinking,
            thinking_budget=thinking_budget, temperature=temperature)
        max_tokens = payload["max_tokens"]

        try:
            attempt_no += 1
            result, attempt_usage = await self._perform_observed_attempt(
                logical_call_id=logical_call_id,
                attempt_no=attempt_no,
                headers=headers,
                payload=payload,
            )
            if attempt_usage is not None:
                attempt_usages.append(attempt_usage)
            self._raise_for_upstream_error(result)
            cot_observation = self._detect_cot_observation(result, payload=payload)
            self._strip_think_content_inplace(result)

            finish_reason = result.get("choices", [{}])[0].get("finish_reason", "")
            if finish_reason == "length":
                logger.warning(
                    "LLM output hit max_tokens cap: model=%s max_tokens=%s prompt_len=%s",
                    self.model,
                    max_tokens,
                    len(prompt),
                )
                retry_cap = (
                    self.MAX_TOKENS_HARD_CAP
                    if max_completion_tokens is None
                    else max_completion_tokens
                )
                retry_tokens = min(
                    max(max_tokens * 2, self.THINKING_MIN_MAX_TOKENS),
                    self.MAX_TOKENS_HARD_CAP,
                    retry_cap,
                )
                if (
                    allow_length_retry
                    and self._is_thinking_model()
                    and retry_tokens > max_tokens
                ):
                    retry_payload = dict(payload)
                    retry_payload["max_tokens"] = retry_tokens
                    if response_format_payload is not None:
                        retry_payload["response_format"] = deepcopy(
                            response_format_payload
                        )
                    logger.warning(
                        "Retrying once after length cutoff: model=%s max_tokens=%s -> %s",
                        self.model,
                        max_tokens,
                        retry_tokens,
                    )
                    attempt_no += 1
                    result, attempt_usage = await self._perform_observed_attempt(
                        logical_call_id=logical_call_id,
                        attempt_no=attempt_no,
                        headers=headers,
                        payload=retry_payload,
                    )
                    if attempt_usage is not None:
                        attempt_usages.append(attempt_usage)
                    self._raise_for_upstream_error(result)
                    cot_observation = self._detect_cot_observation(
                        result, payload=retry_payload
                    )
                    self._strip_think_content_inplace(result)

            usage_breakdown = self._aggregate_attempt_usages(attempt_usages)
            api_time = time.time() - api_start
            self._record_stats_delta(
                api_time=api_time, successes=1,
                tokens=int(usage_breakdown.get("total_tokens") or 0),
            )
            result["_api_time"] = api_time
            result["_first_result_latency"] = api_time
            result["_usage_breakdown"] = usage_breakdown
            result["_cot_observation"] = cot_observation
            return result
        except Exception:
            api_time = time.time() - api_start
            self._record_stats_delta(api_time=api_time, errors=1)
            raise

    owns_context_attempt_budget = True

    async def _perform_observed_attempt(
        self,
        *,
        logical_call_id: str,
        attempt_no: int,
        headers: Dict[str, str],
        payload: Dict[str, Any],
    ) -> tuple[Dict[str, Any], Optional[dict[str, int]]]:
        from .luxian_0609.privacy_request_scope import protect_current_payload

        payload = protect_current_payload(payload)
        from .llm_token_budget import deployed_capability, guard_payload, strict_enabled
        profile, capability = deployed_capability(self.provider_code, self.model,
            self.gateway_profile, self.api_endpoint, dispatch_mode=self.dispatch_mode)
        from .llm_observability import current_llm_observation_context
        guard_payload(self.provider_code, profile, payload, capability, enabled=strict_enabled(),
                      phase="client_final_request", attribution={"logical_call_id": logical_call_id,
                          "attempt_no": attempt_no, "role": self.model_role,
                          "executor": current_llm_observation_context().executor_key,
                          "root_job_id": current_llm_observation_context().root_job_id})
        from .luxian_0609.exam_token_budget import take_http_attempt
        take_http_attempt(self)
        case_prefix = None
        event_id, started_timestamp = await self._observability_recorder.start_attempt(
            logical_call_id=logical_call_id,
            attempt_no=attempt_no,
            provider_code=self.provider_code,
            model=self.model,
            model_role=self.model_role,
        )
        diagnostic_attempt = begin_diagnostic_attempt(
            logical_call_id=logical_call_id, attempt_no=attempt_no, payload=payload,
        )
        transport_observation = None
        try:
            from .luxian_0609.execution_time_budget import request_timeout

            timeout_seconds = request_timeout(self.timeout_seconds)
            with http_attempt_observation_scope(
                enabled=(getattr(self, "strata_observation_mode", "off") in {"observe", "prefix"}
                         or getattr(self, "request_observation_enabled", False)),
            ) as transport_observation:
                if self.dispatch_mode == "gateway":
                    if not self.gateway_profile:
                        raise ProviderConfigurationError(
                            "LLM gateway profile is unavailable"
                        )
                    if self.provider_code == "strata" and getattr(self, "strata_observation_mode", "off") == "prefix":
                        from .strata_case_context import (
                            consume_exam_result_prefix_request, current_exam_result_prefix,
                        )

                        case_prefix = current_exam_result_prefix(payload, model_role=self.model_role)
                        if case_prefix is not None:
                            # 先校验完整元数据，再扣调用预算；两者间无await。
                            protect_current_payload({"case_prefix": case_prefix.model_dump(mode="json")})
                            consume_exam_result_prefix_request()
                    prefix_kwargs = {"case_prefix": case_prefix} if case_prefix is not None else {}
                    from .llm_token_budget import LOCAL
                    if strict_enabled() and self.provider_code in LOCAL:
                        # 远程Gateway即使默认关闭，也必须执行最终组装后的准入；旧Gateway拒绝未知字段而非静默绕过。
                        prefix_kwargs["context_budget_required"] = True
                    if getattr(self, "request_observation_enabled", False):
                        prefix_kwargs["observe_request"] = True
                    if self.provider_code == "strata":
                        from .llm_observability import current_llm_observation_context

                        case_key = current_llm_observation_context().record_key_hash
                        if case_key is not None:
                            protect_current_payload({"case_key": case_key})
                            prefix_kwargs["case_key"] = case_key
                            from .strata_scheduling import current_strata_package_key

                            package_key = current_strata_package_key()
                            if package_key is not None:
                                protect_current_payload({"package_key": package_key})
                                prefix_kwargs["package_key"] = package_key
                    result = await self._gateway_dispatch_client.complete(
                        provider_code=self.provider_code,
                        profile=self.gateway_profile,
                        expected_endpoint_sha256=str(
                            self.gateway_endpoint_sha256 or ""
                        ),
                        payload=payload,
                        timeout_seconds=timeout_seconds,
                        **prefix_kwargs,
                    )
                else:
                    result = await safe_post_json(
                        url=f"{self.api_endpoint}/chat/completions",
                        headers=headers,
                        payload=payload,
                        timeout_seconds=timeout_seconds,
                    )
            finish_diagnostic_attempt(diagnostic_attempt, result=result)
            usage = observed_usage(result)
            status, safe_error_kind = safe_status_for_http_result(result)
            self._observe_strata_attempt(
                event_id=event_id, logical_call_id=logical_call_id, attempt_no=attempt_no,
                payload=payload, result=result, status=status,
                started_timestamp=started_timestamp, transport_observation=transport_observation,
            )
            await self._observability_recorder.finish_attempt(
                event_id=event_id,
                started_timestamp=started_timestamp,
                status=status,
                safe_error_kind=safe_error_kind,
                usage=usage,
            )
            return result, usage
        except BaseException as error:
            from .llm_token_budget import note_budget_failure
            note_budget_failure(error)
            status, safe_error_kind = safe_status_for_exception(error)
            failed_cache_observation = None
            if case_prefix is not None:
                failed_cache_observation = {"_strata_cache_expected": True}
                if getattr(error, "cache_trace", None) is not None:
                    failed_cache_observation["_strata_cache"] = error.cache_trace
                if getattr(error, "cache_trace_invalid", False):
                    failed_cache_observation["_strata_cache_invalid"] = True
            if getattr(error, "request_observation", None) is not None:
                failed_cache_observation = dict(failed_cache_observation or {})
                failed_cache_observation["_gateway_request_observation"] = error.request_observation
            if getattr(error, "request_observation_invalid", False):
                failed_cache_observation = dict(failed_cache_observation or {})
                failed_cache_observation["_gateway_request_observation_invalid"] = True
            self._observe_strata_attempt(
                event_id=event_id, logical_call_id=logical_call_id, attempt_no=attempt_no,
                payload=payload, result=failed_cache_observation, status=status,
                started_timestamp=started_timestamp, transport_observation=transport_observation,
            )
            finish_diagnostic_attempt(diagnostic_attempt, error_kind=safe_error_kind or "unknown_error")
            await self._observability_recorder.finish_attempt(
                event_id=event_id,
                started_timestamp=started_timestamp,
                status=status,
                safe_error_kind=safe_error_kind,
                usage=None,
            )
            raise

    def _observe_strata_attempt(self, *, transport_observation, **kwargs) -> None:
        if (getattr(self, "strata_observation_mode", "off") not in {"observe", "prefix"}
                and not getattr(self, "request_observation_enabled", False)):
            return
        try:
            self._observability_recorder.record_strata_attempt(
                **kwargs, model=self.model, model_role=self.model_role, provider_code=self.provider_code,
                gateway=self.dispatch_mode == "gateway",
                route_key=[self.dispatch_mode, self.gateway_profile, self.api_endpoint, self.model_role],
                transport=transport_observation.snapshot() if transport_observation else None,
            )
        except Exception:
            # 包含自定义 recorder；旁路失败不能触发医学请求重试或回退。
            logger.warning("strata_p0_observation_failed")

    @staticmethod
    def _aggregate_attempt_usages(
        attempt_usages: list[dict[str, int]],
    ) -> Dict[str, int]:
        input_tokens = sum(item["input_tokens"] for item in attempt_usages)
        cached_input_tokens = sum(
            int(item.get("cached_input_tokens") or 0) for item in attempt_usages
        )
        output_tokens = sum(item["output_tokens"] for item in attempt_usages)
        total_tokens = sum(item["total_tokens"] for item in attempt_usages)
        return {
            "prompt_tokens": input_tokens,
            "completion_tokens": output_tokens,
            "input_tokens": input_tokens,
            "cached_input_tokens": cached_input_tokens,
            "output_tokens": output_tokens,
            "total_tokens": total_tokens,
        }

    def _endpoint_host(self) -> str:
        try:
            return urlparse(str(self.api_endpoint or "")).hostname or ""
        except Exception:
            return ""

    @staticmethod
    def _summarize_upstream_body(body: Any, *, max_length: int = 600) -> str:
        text = ""
        if isinstance(body, dict):
            parts: list[str] = []
            for key in ("code", "message", "error", "request_id", "text"):
                value = body.get(key)
                if value:
                    parts.append(f"{key}={value}")
            nested_error = body.get("error")
            if isinstance(nested_error, dict):
                for key in ("code", "message", "type"):
                    value = nested_error.get(key)
                    if value:
                        parts.append(f"error.{key}={value}")
            text = "; ".join(parts) if parts else str(body)
        else:
            text = str(body)
        text = re.sub(r"sk-[A-Za-z0-9_\-]{8,}", "sk-***", text)
        return text[:max_length]

    def _raise_for_upstream_error(self, result: Dict[str, Any]) -> None:
        if not isinstance(result, dict) or result.get("__error__") is not True:
            return
        from .luxian_0609.privacy_request_scope import is_luxian_0609_privacy_scope_active

        status = result.get("__status__")
        body = result.get("body")
        if is_luxian_0609_privacy_scope_active():
            # 响应正文不可信；只发布安全枚举，禁止把任意 code/message 当摘要。
            safe_codes = {
                "InvalidParameter": "invalid_parameter",
                "invalid_request_error": "invalid_request",
                "rate_limit_exceeded": "rate_limit",
                "insufficient_quota": "quota_exceeded",
                "model_not_found": "model_unavailable",
                "authentication_error": "authentication_error",
            }
            code = body.get("code") if isinstance(body, dict) else None
            if isinstance(body, dict) and isinstance(body.get("error"), dict):
                code = body["error"].get("code") or body["error"].get("type")
            summary = safe_codes.get(code, "upstream_response_error") if isinstance(code, str) else "upstream_response_error"
            safe_status = status if type(status) is int and 100 <= status <= 599 else "unknown"
            raise RuntimeError(
                "upstream_http_error "
                f"upstream_http_status={safe_status} "
                f"upstream_error_summary={summary}"
            ) from None
        summary = self._summarize_upstream_body(body)
        raise RuntimeError(
            "upstream_http_error "
            f"upstream_http_status={status} "
            f"provider_code={self.provider_code or 'unknown'} "
            f"model={self.model} "
            f"endpoint_host={self._endpoint_host()} "
            f"upstream_error_summary={summary}"
        )

    def _is_thinking_model(self) -> bool:
        model = (self.model or "").lower()
        return (
            ("qwen3.5" in model)
            or ("thinking" in model)
            or (model == "deepseek-reasoner")
        )

    def _is_deepseek_provider(self) -> bool:
        if self.provider_code == "deepseek":
            return True
        endpoint = str(self.api_endpoint or "").strip().lower().rstrip("/")
        return endpoint.startswith(self.DEEPSEEK_BASE_URL_PREFIX)

    def _build_provider_specific_payload(
        self,
        *,
        enable_thinking: bool | None = None,
        thinking_budget: int | None = None,
    ) -> Dict[str, Any]:
        resolved_enable_thinking = (
            self.enable_thinking if enable_thinking is None else enable_thinking
        )
        resolved_thinking_budget = (
            self.thinking_budget if thinking_budget is None else thinking_budget
        )
        if self.provider_code == "local_openai":
            # 通用本地服务只使用已确认的OpenAI字段，Thinking能力保持未知。
            return {}
        if self._is_deepseek_provider():
            if self.model == "deepseek-reasoner" or resolved_enable_thinking:
                extra: Dict[str, Any] = {"thinking": {"type": "enabled"}}
                if self.reasoning_effort in {"high", "max"}:
                    extra["reasoning_effort"] = self.reasoning_effort
                return extra
            return {"thinking": {"type": "disabled"}}
        if self.provider_code == "strata":
            chat_template_kwargs: Dict[str, Any] = {
                "enable_thinking": bool(resolved_enable_thinking)
            }
            if resolved_enable_thinking and resolved_thinking_budget is not None:
                if (
                    isinstance(resolved_thinking_budget, bool)
                    or not isinstance(resolved_thinking_budget, int)
                    or resolved_thinking_budget <= 0
                ):
                    raise ValueError("thinking_budget must be a positive integer")
                chat_template_kwargs["thinking_budget"] = resolved_thinking_budget
            return {"chat_template_kwargs": chat_template_kwargs}
        if (
            (self.model or "").lower().startswith("qwen3")
            and (
                self.provider_code == "alibaba"
                or self._endpoint_host()
                in {"dashscope.aliyuncs.com", "dashscope-intl.aliyuncs.com"}
            )
        ):
            extra: Dict[str, Any] = {"enable_thinking": resolved_enable_thinking}
            if resolved_enable_thinking and resolved_thinking_budget is not None:
                if (
                    isinstance(resolved_thinking_budget, bool)
                    or not isinstance(resolved_thinking_budget, int)
                    or resolved_thinking_budget <= 0
                ):
                    raise ValueError("thinking_budget must be a positive integer")
                extra["thinking_budget"] = resolved_thinking_budget
            return extra
        return {"enable_thinking": False}

    @staticmethod
    def _copy_response_format(
        response_format: Mapping[str, Any] | None,
    ) -> Dict[str, Any] | None:
        if response_format is None:
            return None
        if not isinstance(response_format, Mapping):
            raise ValueError("response_format must be a mapping")
        response_type = response_format.get("type")
        if response_type not in {"json_object", "json_schema"}:
            raise ValueError(
                "response_format type must be one of: json_object, json_schema"
            )
        return deepcopy(dict(response_format))

    def supports_strict_json_schema(self) -> bool:
        provider_code = str(self.provider_code or "").strip().lower()
        dashscope_hosts = {
            "dashscope.aliyuncs.com",
            "dashscope-intl.aliyuncs.com",
        }
        if (
            provider_code not in {"", "alibaba"}
            or self._endpoint_host() not in dashscope_hosts
        ):
            return False
        model = str(self.model or "").strip().lower()
        return model.startswith(
            (
                "qwen3.7-flash",
                "qwen3.7-plus",
                "qwen3.7-max",
                "qwen3.8-flash",
                "qwen3.8-max",
            )
        )

    @staticmethod
    def _extract_usage_breakdown(result: Dict[str, Any]) -> Dict[str, int]:
        usage = dict(result.get("usage") or {})
        prompt_tokens = int(
            usage.get("prompt_tokens") or usage.get("input_tokens") or 0
        )
        completion_tokens = int(
            usage.get("completion_tokens") or usage.get("output_tokens") or 0
        )
        total_tokens = int(
            usage.get("total_tokens")
            or usage.get("total")
            or (prompt_tokens + completion_tokens)
            or 0
        )
        prompt_details = usage.get("prompt_tokens_details") or {}
        cached_input_tokens = int(
            prompt_details.get("cached_tokens") or usage.get("cached_tokens") or 0
        )
        return {
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "input_tokens": prompt_tokens,
            "cached_input_tokens": cached_input_tokens,
            "output_tokens": completion_tokens,
            "total_tokens": total_tokens,
        }

    def _detect_cot_observation(
        self, result: Dict[str, Any], *, payload: Dict[str, Any]
    ) -> Dict[str, Any]:
        message = dict(result.get("choices", [{}])[0].get("message") or {})
        content = str(message.get("content") or "")
        reasoning_content = message.get("reasoning_content")
        has_think_tags = bool(
            re.search(r"<think>[\s\S]*?</think>", content, flags=re.IGNORECASE)
        )
        has_reasoning_content = bool(reasoning_content)
        thinking = payload.get("thinking")
        chat_template_kwargs = payload.get("chat_template_kwargs")
        requested_enable_thinking = bool(
            payload.get("enable_thinking") is True
            or (isinstance(thinking, dict) and thinking.get("type") == "enabled")
            or (
                isinstance(chat_template_kwargs, dict)
                and chat_template_kwargs.get("enable_thinking") is True
            )
        )
        requested_disable_thinking = bool(
            (isinstance(thinking, dict) and thinking.get("type") == "disabled")
            or (
                isinstance(chat_template_kwargs, dict)
                and chat_template_kwargs.get("enable_thinking") is False
            )
        )
        cot_mode = "disabled"
        if requested_enable_thinking:
            cot_mode = "explicit"
        elif has_think_tags or has_reasoning_content:
            cot_mode = "implicit"
        return {
            "cot_mode": cot_mode,
            "requested_enable_thinking": requested_enable_thinking,
            "requested_disable_thinking": requested_disable_thinking,
            "thinking_heuristic_applied": bool(self._is_thinking_model()),
            "response_has_think_tags": has_think_tags,
            "response_has_reasoning_content": has_reasoning_content,
        }

    def _estimate_rule_count(self, prompt: str) -> int:
        match = re.search(r"适用规则数\s*[:：]?\s*(\d+)", prompt)
        if match:
            try:
                return int(match.group(1))
            except Exception:
                return 0
        return 0

    def _resolve_max_tokens(self, prompt: str) -> int:
        max_tokens = int(self.max_tokens or self.DEFAULT_MAX_TOKENS)
        if max_tokens <= 0:
            raise ValueError("max_tokens must be a positive integer")
        max_tokens = min(max_tokens, self.MAX_TOKENS_HARD_CAP)
        if not self._is_thinking_model():
            return max_tokens

        max_tokens = max(max_tokens, self.THINKING_MIN_MAX_TOKENS)
        rule_count = self._estimate_rule_count(prompt)
        if rule_count >= 40:
            max_tokens = max(max_tokens, self.THINKING_LARGE_RULES_MAX_TOKENS)
        return min(max_tokens, self.MAX_TOKENS_HARD_CAP)

    @staticmethod
    def _strip_think_tags(text: str) -> str:
        if not text:
            return text
        return re.sub(r"<think>[\s\S]*?</think>", "", text, flags=re.IGNORECASE).strip()

    def _strip_think_content_inplace(self, result: Dict[str, Any]) -> None:
        try:
            message = result.get("choices", [{}])[0].get("message", {})
            content = message.get("content", "")
            cleaned = self._strip_think_tags(content)
            if cleaned != content:
                message["content"] = cleaned
                result["choices"][0]["message"] = message
        except Exception:
            return

    def stats(self) -> Dict[str, Any]:
        return {
            "total_calls": self.call_count,
            "success_calls": self.success_count,
            "error_calls": self.error_count,
            "success_rate": (self.success_count / self.call_count * 100)
            if self.call_count
            else 0.0,
            "total_tokens": self.total_tokens,
            "total_api_time": self.total_api_time,
            "avg_api_time": (self.total_api_time / self.call_count)
            if self.call_count
            else 0.0,
        }
