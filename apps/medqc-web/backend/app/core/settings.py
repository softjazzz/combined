from pydantic_settings import BaseSettings
from pydantic import AnyHttpUrl, AliasChoices, Field, field_validator, model_validator
from typing import List, Optional
import os
import logging


logger = logging.getLogger(__name__)
_legacy_llm_env_warned = False


class Settings(BaseSettings):
    # Security
    JWT_SECRET: str
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440

    # CORS
    CORS_ORIGINS: List[str] = []
    CORS_ALLOW_CREDENTIALS: bool = True
    CORS_ALLOW_METHODS: List[str] = ["*"]
    CORS_ALLOW_HEADERS: List[str] = ["*"]

    # Supabase (optional)
    SUPABASE_URL: Optional[AnyHttpUrl] = None
    SUPABASE_ANON_KEY: Optional[str] = None
    SUPABASE_SERVICE_ROLE_KEY: Optional[str] = None

    # Table names (configurable)
    RECORDS_TABLE: str = os.getenv("RECORDS_TABLE", "medical_records")
    DOCUMENTS_TABLE: str = os.getenv("DOCUMENTS_TABLE", "medical_documents")

    # Environment
    ENV: str = os.getenv("ENV", "development")

    # ICD semantic retrieval fallback (exact match still first)
    ICD_SEMANTIC_ENABLED: bool = False
    ICD_SEMANTIC_TOP_K: int = 5
    ICD_SEMANTIC_T_HIGH: float = 0.90
    ICD_SEMANTIC_T_LOW: float = 0.60
    ICD_SEMANTIC_BACKEND: str = "tfidf"  # tfidf | hnsw | faiss | auto
    ICD_SEMANTIC_INDEX_DIR: str = "backend/data/vector"
    ICD_SEMANTIC_EMBED_MODEL: str = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
    ICD_SEMANTIC_API_ENDPOINT: str = "https://api.siliconflow.cn/v1/embeddings"
    ICD_SEMANTIC_API_KEY: Optional[str] = None
    ICD_SEMANTIC_TIMEOUT_SECONDS: int = 30

    # Outbound HTTP safety
    OUTBOUND_ALLOWLIST: List[str] = [
        "dashscope.aliyuncs.com",
    ]

    # LLM API Configuration (unified naming; compatible with legacy SICHUAN_* env vars)
    LLM_API_ENDPOINT: Optional[AnyHttpUrl] = Field(
        default=None,
        validation_alias=AliasChoices("LLM_API_ENDPOINT", "SICHUAN_API_ENDPOINT"),
    )
    LLM_API_KEY: Optional[str] = Field(
        default=None,
        validation_alias=AliasChoices("LLM_API_KEY", "SICHUAN_API_KEY"),
    )
    LLM_MODEL: str = Field(
        default="qwen3.5-35b-a3b",
        validation_alias=AliasChoices("LLM_MODEL", "SICHUAN_MODEL"),
    )
    LLM_TIMEOUT_SECONDS: int = Field(
        default=120,
        validation_alias=AliasChoices("LLM_TIMEOUT_SECONDS", "SICHUAN_TIMEOUT_SECONDS"),
    )
    LLM_ENABLE_TRUNCATE: bool = Field(
        default=False,
        validation_alias=AliasChoices("LLM_ENABLE_TRUNCATE", "SICHUAN_ENABLE_TRUNCATE"),
    )
    LLM_MAX_CONTENT_LENGTH: int = Field(
        default=100000,
        validation_alias=AliasChoices("LLM_MAX_CONTENT_LENGTH", "SICHUAN_MAX_CONTENT_LENGTH"),
    )
    LLM_ALLOW_MOCK_WHEN_UNCONFIGURED: bool = Field(
        default=False,
        validation_alias=AliasChoices(
            "LLM_ALLOW_MOCK_WHEN_UNCONFIGURED",
            "SICHUAN_ALLOW_MOCK_WHEN_UNCONFIGURED",
        ),
    )

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

    @model_validator(mode="after")
    def validate_llm_env_conflicts(self):
        pairs = [
            ("LLM_API_ENDPOINT", "SICHUAN_API_ENDPOINT"),
            ("LLM_API_KEY", "SICHUAN_API_KEY"),
            ("LLM_MODEL", "SICHUAN_MODEL"),
            ("LLM_TIMEOUT_SECONDS", "SICHUAN_TIMEOUT_SECONDS"),
            ("LLM_ENABLE_TRUNCATE", "SICHUAN_ENABLE_TRUNCATE"),
            ("LLM_MAX_CONTENT_LENGTH", "SICHUAN_MAX_CONTENT_LENGTH"),
            ("LLM_ALLOW_MOCK_WHEN_UNCONFIGURED", "SICHUAN_ALLOW_MOCK_WHEN_UNCONFIGURED"),
        ]
        conflicts = []
        for std_key, legacy_key in pairs:
            std_v = os.getenv(std_key)
            legacy_v = os.getenv(legacy_key)
            if std_v and legacy_v and std_v.strip() != legacy_v.strip():
                conflicts.append(f"{std_key} != {legacy_key}")
        if conflicts:
            raise ValueError(
                "Conflicting LLM env vars detected: "
                + ", ".join(conflicts)
                + ". Keep only LLM_* or make sure values are identical."
            )
        return self

    def llm_env_source(self) -> str:
        has_std = any(os.getenv(k) for k in ["LLM_API_ENDPOINT", "LLM_API_KEY", "LLM_MODEL"])
        has_legacy = any(os.getenv(k) for k in ["SICHUAN_API_ENDPOINT", "SICHUAN_API_KEY", "SICHUAN_MODEL"])
        if has_std and has_legacy:
            return "mixed"
        if has_std:
            return "LLM_*"
        if has_legacy:
            return "SICHUAN_*"
        return "none"

    def llm_diagnostics(self) -> dict:
        return {
            "source": self.llm_env_source(),
            "endpoint_set": bool(self.LLM_API_ENDPOINT),
            "api_key_set": bool(self.LLM_API_KEY),
            "model": self.LLM_MODEL,
            "timeout_seconds": self.LLM_TIMEOUT_SECONDS,
            "allow_mock_when_unconfigured": self.LLM_ALLOW_MOCK_WHEN_UNCONFIGURED,
        }

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def split_origins(cls, v):
        if isinstance(v, str):
            txt = v.strip()
            if txt.startswith("[") and txt.endswith("]"):
                try:
                    import json
                    arr = json.loads(txt)
                    if isinstance(arr, list):
                        return [str(o).strip() for o in arr if str(o).strip()]
                except Exception:
                    pass
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

    global _legacy_llm_env_warned
    if (not _legacy_llm_env_warned) and settings.llm_env_source() in {"SICHUAN_*", "mixed"}:
        logger.warning(
            "Detected legacy SICHUAN_* env vars. Standard keys are LLM_*. "
            "Compatibility is enabled but migration is recommended."
        )
        _legacy_llm_env_warned = True

    if not settings.JWT_SECRET:
        raise RuntimeError("JWT_SECRET is required and must not be empty")
    return settings
