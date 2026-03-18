"""
QC LLM client.

Wraps network calls to LLM API and keeps stats for QC workflows.
"""

import logging
import re
import time
from typing import Any, Dict, Optional

from ..core.http import safe_post_json
from ..core.settings import get_settings

logger = logging.getLogger(__name__)


class SichuanQCLLMClient:
    DEFAULT_MAX_TOKENS = 16384
    THINKING_MIN_MAX_TOKENS = 16384
    THINKING_LARGE_RULES_MAX_TOKENS = 24576
    MAX_TOKENS_HARD_CAP = 32768

    def __init__(self, config: Optional[Dict[str, Any]] = None) -> None:
        if config:
            self.api_endpoint: Optional[str] = config.get("api_endpoint")
            self.api_key: Optional[str] = config.get("api_key")
            self.model: str = config.get("model", "qwen2.5-14b-instruct")
            self.timeout_seconds: int = config.get("timeout_seconds", 120)
            self.allow_mock_when_unconfigured: bool = bool(config.get("allow_mock_when_unconfigured", False))
            self.config_source = config.get("source", "unknown")

            custom_params = config.get("custom_parameters", {})
            self.temperature: float = custom_params.get("temperature", 0.2)
            self.top_p: float = custom_params.get("top_p", 0.9)
            self.max_tokens: int = custom_params.get("max_tokens", self.DEFAULT_MAX_TOKENS)

            logger.info(
                "SichuanQCLLMClient custom init: model=%s source=%s temperature=%s top_p=%s max_tokens=%s",
                self.model,
                self.config_source,
                self.temperature,
                self.top_p,
                self.max_tokens,
            )
        else:
            s = get_settings()
            self.api_endpoint = str(s.LLM_API_ENDPOINT) if s.LLM_API_ENDPOINT else None
            self.api_key = s.LLM_API_KEY
            self.model = s.LLM_MODEL
            self.timeout_seconds = s.LLM_TIMEOUT_SECONDS
            self.allow_mock_when_unconfigured = s.LLM_ALLOW_MOCK_WHEN_UNCONFIGURED
            self.config_source = "env"

            self.temperature = 0.2
            self.top_p = 0.9
            self.max_tokens = self.DEFAULT_MAX_TOKENS

            logger.info(
                "SichuanQCLLMClient env init: source=%s endpoint_set=%s api_key_set=%s model=%s allow_mock=%s",
                s.llm_env_source() if hasattr(s, "llm_env_source") else "unknown",
                bool(self.api_endpoint),
                bool(self.api_key),
                self.model,
                self.allow_mock_when_unconfigured,
            )

        self.call_count = 0
        self.total_tokens = 0
        self.total_api_time = 0.0
        self.success_count = 0
        self.error_count = 0

    async def generate(self, prompt: str) -> Dict[str, Any]:
        self.call_count += 1
        api_start = time.time()

        if not (self.api_endpoint and self.api_key):
            if self.allow_mock_when_unconfigured:
                api_time = time.time() - api_start
                self.success_count += 1
                return {
                    "choices": [{"message": {"content": f"[MOCK RESULT] 分析完成: {prompt[:60]}..."}}],
                    "usage": {"total_tokens": 0},
                    "_mock": True,
                    "_api_time": api_time,
                }

            self.error_count += 1
            raise RuntimeError(
                "LLM is not configured. Set LLM_API_ENDPOINT / LLM_API_KEY / LLM_MODEL. "
                "Legacy SICHUAN_* variables are still supported via alias."
            )

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        max_tokens = self._resolve_max_tokens(prompt)
        payload = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": self.temperature,
            "top_p": self.top_p,
            "max_tokens": max_tokens,
            "stream": False,
            "enable_thinking": False,
        }

        try:
            result = await safe_post_json(
                url=f"{self.api_endpoint}/chat/completions",
                headers=headers,
                payload=payload,
                timeout_seconds=self.timeout_seconds,
            )

            self._strip_think_content_inplace(result)

            finish_reason = result.get("choices", [{}])[0].get("finish_reason", "")
            if finish_reason == "length":
                logger.warning(
                    "LLM output hit max_tokens cap: model=%s max_tokens=%s prompt_len=%s",
                    self.model,
                    max_tokens,
                    len(prompt),
                )
                retry_tokens = min(max(max_tokens * 2, self.THINKING_MIN_MAX_TOKENS), self.MAX_TOKENS_HARD_CAP)
                if self._is_thinking_model() and retry_tokens > max_tokens:
                    retry_payload = dict(payload)
                    retry_payload["max_tokens"] = retry_tokens
                    logger.warning(
                        "Retrying once after length cutoff: model=%s max_tokens=%s -> %s",
                        self.model,
                        max_tokens,
                        retry_tokens,
                    )
                    result = await safe_post_json(
                        url=f"{self.api_endpoint}/chat/completions",
                        headers=headers,
                        payload=retry_payload,
                        timeout_seconds=self.timeout_seconds,
                    )
                    self._strip_think_content_inplace(result)

            api_time = time.time() - api_start
            self.total_api_time += api_time
            self.success_count += 1
            usage = result.get("usage", {})
            self.total_tokens += usage.get("total_tokens", 0)
            result["_api_time"] = api_time
            return result
        except Exception:
            api_time = time.time() - api_start
            self.total_api_time += api_time
            self.error_count += 1
            raise

    def _is_thinking_model(self) -> bool:
        model = (self.model or "").lower()
        return ("qwen3.5" in model) or ("thinking" in model)

    def _estimate_rule_count(self, prompt: str) -> int:
        match = re.search(r"适用规则数\s*(\d+)", prompt)
        if match:
            try:
                return int(match.group(1))
            except Exception:
                return 0
        return 0

    def _resolve_max_tokens(self, prompt: str) -> int:
        max_tokens = int(self.max_tokens or self.DEFAULT_MAX_TOKENS)
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
            "success_rate": (self.success_count / self.call_count * 100) if self.call_count else 0.0,
            "total_tokens": self.total_tokens,
            "total_api_time": self.total_api_time,
            "avg_api_time": (self.total_api_time / self.call_count) if self.call_count else 0.0,
        }
