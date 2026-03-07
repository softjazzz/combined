from pydantic_settings import BaseSettings
from pydantic import AnyHttpUrl, field_validator
from typing import List, Optional
import os


class Settings(BaseSettings):
    # Security
    JWT_SECRET: str
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30

    # CORS
    # 支持逗号分隔或 JSON 数组两种格式；为避免严格 URL 校验导致环境解析失败，这里使用 List[str]
    CORS_ORIGINS: List[str] = []
    CORS_ALLOW_CREDENTIALS: bool = True
    CORS_ALLOW_METHODS: List[str] = ["*"]
    CORS_ALLOW_HEADERS: List[str] = ["*"]

    # Supabase (optional)
    SUPABASE_URL: Optional[AnyHttpUrl] = None
    SUPABASE_ANON_KEY: Optional[str] = None
    SUPABASE_SERVICE_ROLE_KEY: Optional[str] = None
    # Table names (configurable)
    RECORDS_TABLE: str = os.getenv("RECORDS_TABLE", "medical_records_test")
    DOCUMENTS_TABLE: str = os.getenv("DOCUMENTS_TABLE", "medical_documents_test")

    # Environment
    ENV: str = os.getenv("ENV", "development")

    # Outbound HTTP safety
    OUTBOUND_ALLOWLIST: List[str] = [
        "dashscope.aliyuncs.com",
    ]

    # LLM API Configuration (unified naming)
    LLM_API_ENDPOINT: Optional[AnyHttpUrl] = None  # e.g. https://dashscope.aliyuncs.com/compatible-mode/v1
    LLM_API_KEY: Optional[str] = None
    LLM_MODEL: str = "qwen3.5-35b-a3b"
    LLM_TIMEOUT_SECONDS: int = 120
    # Content truncation settings
    LLM_ENABLE_TRUNCATE: bool = False  # 禁用截断（模型支持128K上下文）
    LLM_MAX_CONTENT_LENGTH: int = 100000  # 最大内容长度（字符数）

    # Backward compatibility aliases (deprecated, use LLM_* instead)
    @property
    def SICHUAN_API_ENDPOINT(self) -> Optional[AnyHttpUrl]:
        return self.LLM_API_ENDPOINT

    @property
    def SICHUAN_API_KEY(self) -> Optional[str]:
        return self.LLM_API_KEY

    @property
    def SICHUAN_MODEL(self) -> str:
        return self.LLM_MODEL

    @property
    def SICHUAN_TIMEOUT_SECONDS(self) -> int:
        return self.LLM_TIMEOUT_SECONDS

    @property
    def SICHUAN_ENABLE_TRUNCATE(self) -> bool:
        return self.LLM_ENABLE_TRUNCATE

    @property
    def SICHUAN_MAX_CONTENT_LENGTH(self) -> int:
        return self.LLM_MAX_CONTENT_LENGTH


    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def split_origins(cls, v):
        if isinstance(v, str):
            txt = v.strip()
            # 如果是 JSON 数组，尝试解析
            if txt.startswith("[") and txt.endswith("]"):
                try:
                    import json
                    arr = json.loads(txt)
                    if isinstance(arr, list):
                        return [str(o).strip() for o in arr if str(o).strip()]
                except Exception:
                    pass
            # 否则按逗号分隔
            return [o.strip() for o in txt.split(",") if o.strip()]
        return v

    class Config:
        # Only load backend-local .env to avoid picking up frontend Vite envs
        env_file = (".env",)
        env_file_encoding = "utf-8"
        extra = "ignore"


def get_settings() -> Settings:
    # Allow fallback to VITE_* env for Supabase compatibility with legacy configs
    if not os.getenv("SUPABASE_URL") and os.getenv("VITE_SUPABASE_URL"):
        os.environ["SUPABASE_URL"] = os.getenv("VITE_SUPABASE_URL", "")
    if not os.getenv("SUPABASE_ANON_KEY") and os.getenv("VITE_SUPABASE_ANON_KEY"):
        os.environ["SUPABASE_ANON_KEY"] = os.getenv("VITE_SUPABASE_ANON_KEY", "")

    settings = Settings()  # type: ignore[call-arg]
    if not settings.JWT_SECRET:
        raise RuntimeError("JWT_SECRET is required and must not be empty")
    return settings
