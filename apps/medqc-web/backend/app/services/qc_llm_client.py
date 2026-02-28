"""
质控 LLM 客户端

封装 LLM API 的网络调用逻辑，与质控业务逻辑解耦。
"""
import time
import logging
from typing import Dict, Any, Optional

from ..core.settings import get_settings
from ..core.http import safe_post_json

logger = logging.getLogger(__name__)


class SichuanQCLLMClient:
    def __init__(self, config: Optional[Dict[str, Any]] = None) -> None:
        """
        初始化 LLM 客户端

        Args:
            config: 配置字典，如果为 None 则从 .env 文件加载
                   配置字典应包含：
                   - api_endpoint: API 端点
                   - api_key: API 密钥
                   - model: 模型代码
                   - timeout_seconds: 超时时间
        """
        if config:
            # 使用传入的配置
            self.api_endpoint: Optional[str] = config.get("api_endpoint")
            self.api_key: Optional[str] = config.get("api_key")
            self.model: str = config.get("model", "qwen2.5-14b-instruct")
            self.timeout_seconds: int = config.get("timeout_seconds", 120)
            self.config_source = config.get("source", "unknown")

            # Load advanced LLM parameters from custom_parameters
            custom_params = config.get("custom_parameters", {})
            self.temperature: float = custom_params.get("temperature", 0.2)
            self.top_p: float = custom_params.get("top_p", 0.9)
            self.max_tokens: int = custom_params.get("max_tokens", 4000)

            logger.info(f"✅ SichuanQCLLMClient 使用传入配置初始化: model={self.model}, source={self.config_source}, temperature={self.temperature}, top_p={self.top_p}, max_tokens={self.max_tokens}")
        else:
            # 回退到 .env 文件配置
            s = get_settings()
            self.api_endpoint: Optional[str] = str(s.SICHUAN_API_ENDPOINT) if s.SICHUAN_API_ENDPOINT else None
            self.api_key: Optional[str] = s.SICHUAN_API_KEY
            self.model: str = s.SICHUAN_MODEL
            self.timeout_seconds: int = s.SICHUAN_TIMEOUT_SECONDS
            self.config_source = "env"

            # Default advanced parameters when using .env
            self.temperature: float = 0.2
            self.top_p: float = 0.9
            self.max_tokens: int = 4000

            logger.info(f"✅ SichuanQCLLMClient 使用 .env 配置初始化: model={self.model}, temperature={self.temperature}")

        # Stats
        self.call_count = 0
        self.total_tokens = 0
        self.total_api_time = 0.0
        self.success_count = 0
        self.error_count = 0

    async def generate(self, prompt: str) -> Dict[str, Any]:
        self.call_count += 1
        api_start = time.time()

        if not (self.api_endpoint and self.api_key):
            # Mock result when not configured
            api_time = time.time() - api_start
            self.success_count += 1
            return {
                "choices": [{"message": {"content": f"[MOCK RESULT] 分析完成: {prompt[:60]}..."}}],
                "usage": {"total_tokens": 0},
                "_mock": True,
                "_api_time": api_time,
            }

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": self.temperature,
            "top_p": self.top_p,
            "max_tokens": self.max_tokens,
            "stream": False,
            "enable_thinking": False,  # Qwen3 系列模型需要此参数
        }

        try:
            result = await safe_post_json(
                url=f"{self.api_endpoint}/chat/completions",
                headers=headers,
                payload=payload,
                timeout_seconds=self.timeout_seconds,
            )
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
