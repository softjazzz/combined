from pydantic_settings import BaseSettings
from pydantic import AnyHttpUrl, AliasChoices, Field, field_validator, model_validator
from pydantic_settings.sources import DotEnvSettingsSource, EnvSettingsSource
from typing import List, Optional
import os
import logging


logger = logging.getLogger(__name__)
_legacy_llm_env_warned = False


LIST_LIKE_ENV_FIELDS = {
    "CORS_ORIGINS",
    "CORS_ALLOW_METHODS",
    "CORS_ALLOW_HEADERS",
    "LLM_VISIBLE_PROVIDERS",
    "OUTBOUND_ALLOWLIST",
}


def _parse_list_like_env_value(value):
    if isinstance(value, str):
        txt = value.strip()
        if not txt:
            return []
        if txt.startswith("[") and txt.endswith("]"):
            try:
                import json

                arr = json.loads(txt)
                if isinstance(arr, list):
                    return [str(item).strip() for item in arr if str(item).strip()]
            except Exception:
                pass
        return [item.strip() for item in txt.split(",") if item.strip()]
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    return value


class CsvFriendlyEnvSettingsSource(EnvSettingsSource):
    def prepare_field_value(self, field_name, field, value, value_is_complex):
        if field_name in LIST_LIKE_ENV_FIELDS and value is not None:
            return _parse_list_like_env_value(value)
        return super().prepare_field_value(field_name, field, value, value_is_complex)


class CsvFriendlyDotEnvSettingsSource(DotEnvSettingsSource):
    def prepare_field_value(self, field_name, field, value, value_is_complex):
        if field_name in LIST_LIKE_ENV_FIELDS and value is not None:
            return _parse_list_like_env_value(value)
        return super().prepare_field_value(field_name, field, value, value_is_complex)


class Settings(BaseSettings):
    # Security
    JWT_SECRET: str
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440

    # 产品离线激活：默认关闭，客户正式包通过环境变量显式开启。
    PRODUCT_ACTIVATION_REQUIRED: bool = False
    PRODUCT_ACTIVATION_STATE_PATH: Optional[str] = None

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

    # 客户样本病历同步：保持病例级串行，仅允许明细表级有限并发。
    SAMPLE_SYNC_INCREMENTAL_ENABLED: bool = False
    SAMPLE_SYNC_DETAIL_TABLE_WORKERS: int = Field(default=3, ge=1, le=6)
    SAMPLE_SYNC_DETAIL_TABLE_WORKERS_MAX: int = Field(default=6, ge=1, le=6)
    SAMPLE_SYNC_UPSERT_BATCH_SIZE: int = Field(default=500, ge=50, le=5000)
    SAMPLE_SYNC_WATERMARK_OVERLAP_MINUTES: int = Field(default=10, ge=0, le=1440)

    # SC 规则来源治理（生产硬约束）
    # - strict: true 时要求 SC 规则必须来自 pg_governance，否则阻断执行
    # - block_batch_on_fallback: 即便非 strict，也可在 source 回退时阻断批量任务
    # - monitor_enabled: 启用后端内置周期巡检（等价持续监控 /rules/source）
    QC_SC_RULE_SOURCE_STRICT: bool = False
    QC_SC_RULE_SOURCE_BLOCK_BATCH_ON_FALLBACK: bool = False
    QC_SC_RULE_SOURCE_MONITOR_ENABLED: bool = False
    QC_SC_RULE_SOURCE_MONITOR_INTERVAL_SECONDS: int = 60
    QC_SC_RULE_SOURCE_ALERT_DEDUP_SECONDS: int = 300

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
        "api.deepseek.com",
    ]

    # SQLBot 问数嵌入配置（默认关闭，保持独立部署和只读数据源边界）
    SQLBOT_ENABLED: bool = False
    SQLBOT_BASE_URL: Optional[str] = None
    SQLBOT_EMBED_URL: Optional[str] = None
    SQLBOT_APP_ID: Optional[str] = None
    SQLBOT_TIMEOUT_SECONDS: int = 30

    # QC Agent LLM intent router
    # 仅用于把自然语言解析为受限工具意图，不允许直接执行工具或返回原始模型内容。
    QC_AGENT_LLM_INTENT_ENABLED: bool = True
    QC_AGENT_LLM_INTENT_TIMEOUT_SECONDS: int = 8
    QC_AGENT_LLM_INTENT_MIN_CONFIDENCE: float = 0.55

    # 泸县0609客户专项质控集主干化开关
    # 仅在 rule_set_key=luxian_0609_qc_v1 时生效，关闭后回到原底层 SC/LX/CL 执行链路。
    LUXIAN_0609_TRIGGER_GATE_ENABLED: bool = True
    LUXIAN_0609_LLM_TRIGGER_GATE_ENABLED: bool = True
    LUXIAN_0609_CUSTOMER_AGGREGATION_ENABLED: bool = True
    LUXIAN_0609_EVIDENCE_FORMATTER_ENABLED: bool = True
    # 029/030/032 使用原生确定性执行；正式 LX0609 任务关闭时失败关闭，
    # 不会回退旧映射链。旧入口兼容行为仅供隔离测试和非正式历史入口使用。
    LUXIAN_0609_NATIVE_EXECUTION_ENABLED: bool = True
    # 001/002/004/005/006 使用基础时限族原生确定性执行；正式任务关闭时失败关闭。
    LUXIAN_0609_NATIVE_BASIC_TIMELINESS_ENABLED: bool = True
    # 会诊原生入口总开关：默认启用第一阶段021/022；正式任务关闭时失败关闭。
    # 多专科会诊意见可能被同步在同一文书中；episode 分段完成真实验收前保持
    # compatibility 路径，避免把多个实际会诊压缩为单一对象。
    LUXIAN_0609_NATIVE_CONSULTATION_ENABLED: bool = True
    # 第二阶段“会诊意见—后续执行”关联开关；关闭时仅 021/022 使用原生 episode。
    LUXIAN_0609_CONSULTATION_EXECUTION_LINK_ENABLED: bool = True
    # 检查检验族原生入口；正式任务关闭时失败关闭。
    LUXIAN_0609_NATIVE_EXAM_LAB_ENABLED: bool = True
    # 输血族041-049独立包开关；正式任务关闭时失败关闭。
    LUXIAN_0609_NATIVE_TRANSFUSION_ENABLED: bool = True
    # 肿瘤病理族013/019/026/027独立包开关；正式任务关闭时失败关闭。
    LUXIAN_0609_NATIVE_TUMOR_PATHOLOGY_ENABLED: bool = True
    # 病程质量族007/008/009/016/017/018独立包开关；正式任务关闭时失败关闭。
    LUXIAN_0609_NATIVE_COURSE_QUALITY_ENABLED: bool = True
    # 手术高风险门控003/024/025/028/031/033独立包开关；正式任务关闭时失败关闭。
    LUXIAN_0609_NATIVE_SURGERY_GATE_ENABLED: bool = True
    # 麻醉及手术文书034-039独立包开关；正式任务关闭时失败关闭。
    LUXIAN_0609_NATIVE_SURGERY_DOCUMENT_ENABLED: bool = True
    # 040 使用“结构化四级手术 + 裁剪 MDT LLM”原生执行；正式任务关闭时失败关闭。
    LUXIAN_0609_NATIVE_MDT_040_ENABLED: bool = True
    # 扩展文书族050-075独立原生执行开关；正式任务关闭时失败关闭。
    LUXIAN_0609_NATIVE_EXTENDED_DOCUMENT_ENABLED: bool = True
    # 正式客户主链默认直接使用统一证据快照，不依赖运行时覆盖层。
    LUXIAN_0609_EVIDENCE_SNAPSHOT_SIDECAR_ENABLED: bool = True
    # 正式客户主链默认使用统一执行信封；关闭总开关时正式任务失败关闭。
    LUXIAN_0609_UNIFIED_ENGINE_ENABLED: bool = True
    # 同一病历内互不依赖的规则族有限并发；模型 HTTP 请求仍受全进程
    # LLM_HTTP_MAX_CONCURRENCY 统一约束，避免与病历级并发相乘后失控。
    LUXIAN_0609_FAMILY_MAX_CONCURRENCY: int = Field(default=4, ge=1, le=4)
    # LX0609 RuleDecision 主链总开关；关闭后正式任务失败关闭。
    LUXIAN_0609_MAINLINE_RULE_DECISION_ENABLED: bool = True
    # 以下规则族默认进入正式 Typed Decision 主链；每个开关仍可独立回滚。
    LUXIAN_0609_RULE_DECISION_007_ENABLED: bool = True
    LUXIAN_0609_RULE_DECISION_COURSE_SEVERITY_ENABLED: bool = True
    LUXIAN_0609_RULE_DECISION_BASIC_TIMELINESS_ENABLED: bool = True
    LUXIAN_0609_RULE_DECISION_TRANSFUSION_ENABLED: bool = True
    LUXIAN_0609_RULE_DECISION_CONSULTATION_ENABLED: bool = True
    LUXIAN_0609_RULE_DECISION_COURSE_COPY_ENABLED: bool = True
    LUXIAN_0609_RULE_DECISION_COURSE_ADMISSION_ENABLED: bool = True
    LUXIAN_0609_RULE_DECISION_TUMOR_PATHOLOGY_ENABLED: bool = True
    LUXIAN_0609_RULE_DECISION_MDT_040_ENABLED: bool = True
    LUXIAN_0609_RULE_DECISION_SURGERY_TIMELINESS_ENABLED: bool = True
    LUXIAN_0609_RULE_DECISION_SURGERY_GATE_REMAINING_ENABLED: bool = True
    LUXIAN_0609_RULE_DECISION_EXAM_LAB_ENABLED: bool = True
    LUXIAN_0609_RULE_DECISION_SURGERY_DOCUMENT_ENABLED: bool = True
    # 仅输出影子元数据，永不具备发布资格。
    LUXIAN_0609_RUNTIME_SHADOW_ENABLED: bool = False
    # 059事件—医嘱—病程专项影子验证；不进入正式结果与计费汇总。
    LUXIAN_0609_059_SHADOW_ENABLED: bool = False
    # 025植入物五字段专项影子验证；不进入正式结果与计费汇总。
    LUXIAN_0609_025_SHADOW_ENABLED: bool = False
    # LX0609 独立准生产 API；默认关闭，人工验收后才允许显式开启。
    LUXIAN_0609_PREPRODUCTION_API_ENABLED: bool = False

    # LLM API Configuration (unified naming; compatible with legacy SICHUAN_* env vars)
    LLM_API_ENDPOINT: Optional[AnyHttpUrl] = Field(
        default="https://dashscope.aliyuncs.com/compatible-mode/v1",
        validation_alias=AliasChoices("LLM_API_ENDPOINT", "SICHUAN_API_ENDPOINT"),
    )
    LLM_API_KEY: Optional[str] = Field(
        default=None,
        validation_alias=AliasChoices("LLM_API_KEY", "SICHUAN_API_KEY"),
    )
    LLM_MODEL: str = Field(
        default="qwen3.8-flash",
        validation_alias=AliasChoices("LLM_MODEL", "SICHUAN_MODEL"),
    )
    LLM_ADJUDICATOR_MODEL: Optional[str] = Field(
        default="qwen3.8-flash",
        validation_alias=AliasChoices("LLM_ADJUDICATOR_MODEL", "SICHUAN_ADJUDICATOR_MODEL"),
    )
    LLM_ENABLE_THINKING: bool = False
    LLM_THINKING_BUDGET: Optional[int] = Field(default=None, ge=1)
    LLM_TIMEOUT_SECONDS: int = Field(
        default=120,
        validation_alias=AliasChoices("LLM_TIMEOUT_SECONDS", "SICHUAN_TIMEOUT_SECONDS"),
    )
    # 批量质控任务同时处理的病历上限；单次任务可选择更低值。
    QC_BATCH_RECORD_MAX_CONCURRENCY: int = Field(default=16, ge=1, le=32)
    # 全进程共享的 LLM HTTP 出口预算；所有事件循环与后台线程共同受此上限约束。
    LLM_HTTP_MAX_CONCURRENCY: int = Field(default=40, ge=1, le=64)
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
    LLM_DEFAULT_PROVIDER: Optional[str] = "alibaba"
    LLM_VISIBLE_PROVIDERS: List[str] = Field(default_factory=list)
    DEEPSEEK_API_ENDPOINT: str = "https://api.deepseek.com"
    DEEPSEEK_API_KEY: Optional[str] = None
    DASHSCOPE_BASE_URL: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    DASHSCOPE_API_KEY: Optional[str] = None
    SILICONFLOW_API_ENDPOINT: str = "https://api.siliconflow.cn/v1"
    SILICONFLOW_API_KEY: Optional[str] = None
    OLLAMA_API_ENDPOINT: str = "http://127.0.0.1:11434/v1"
    OLLAMA_API_KEY: Optional[str] = None
    OLLAMA_MODEL: str = "qwen2.5:7b-instruct"

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
            "enable_thinking": self.LLM_ENABLE_THINKING,
            "thinking_budget": self.LLM_THINKING_BUDGET,
            "timeout_seconds": self.LLM_TIMEOUT_SECONDS,
            "allow_mock_when_unconfigured": self.LLM_ALLOW_MOCK_WHEN_UNCONFIGURED,
        }

    @classmethod
    def _parse_list_like_env(cls, v):
        return _parse_list_like_env_value(v)

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def split_origins(cls, v):
        return cls._parse_list_like_env(v)

    @field_validator("LLM_VISIBLE_PROVIDERS", mode="before")
    @classmethod
    def split_visible_providers(cls, v):
        parsed = cls._parse_list_like_env(v)
        if isinstance(parsed, list):
            return [item.lower() for item in parsed]
        return parsed

    @field_validator("OUTBOUND_ALLOWLIST", mode="before")
    @classmethod
    def split_outbound_allowlist(cls, v):
        return cls._parse_list_like_env(v)

    class Config:
        # Only load backend-local .env to avoid picking up frontend Vite envs
        env_file = (".env",)
        env_file_encoding = "utf-8"
        extra = "ignore"

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls,
        init_settings,
        env_settings,
        dotenv_settings,
        file_secret_settings,
    ):
        return (
            init_settings,
            CsvFriendlyEnvSettingsSource(settings_cls),
            CsvFriendlyDotEnvSettingsSource(
                settings_cls,
                env_file=dotenv_settings.env_file,
                env_file_encoding=dotenv_settings.env_file_encoding,
                case_sensitive=dotenv_settings.case_sensitive,
                env_prefix=dotenv_settings.env_prefix,
                env_nested_delimiter=dotenv_settings.env_nested_delimiter,
            ),
            file_secret_settings,
        )


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
