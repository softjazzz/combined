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
    CORS_ORIGINS: List[AnyHttpUrl] = []
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

    # Sichuan QC API (configurable)
    SICHUAN_API_ENDPOINT: Optional[AnyHttpUrl] = None  # e.g. https://dashscope.aliyuncs.com/compatible-mode/v1
    SICHUAN_API_KEY: Optional[str] = None
    SICHUAN_MODEL: str = "qwen2.5-14b-instruct"
    SICHUAN_TIMEOUT_SECONDS: int = 120

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def split_origins(cls, v):
        if isinstance(v, str):
            return [o.strip() for o in v.split(",") if o.strip()]
        return v

    class Config:
        # Only load backend-local .env to avoid picking up frontend Vite envs
        env_file = (".env",)
        env_file_encoding = "utf-8"


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
