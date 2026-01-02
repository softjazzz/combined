"""
应用配置管理
使用 pydantic-settings 管理环境变量
"""

from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    """应用配置"""

    # 应用基本信息
    APP_NAME: str = "DRG Backend API"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False

    # API 配置
    API_V1_PREFIX: str = "/api/v1"
    CORS_ORIGINS: list = ["http://localhost:5173", "http://localhost:3000"]

    # Supabase 配置
    SUPABASE_URL: Optional[str] = None
    SUPABASE_KEY: Optional[str] = None  # service_role key for backend

    # LLM 配置（DeepSeek）
    DEEPSEEK_API_KEY: Optional[str] = None
    DEEPSEEK_API_URL: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    DEEPSEEK_MODEL: str = "deepseek-v3"

    # OpenDRG 配置
    OPENDRG_DEFAULT_REGION: str = "sichuan"
    OPENDRG_BASE_PAYMENT: float = 14655.0  # 四川省 2024 年基准支付标准（元）

    # 外部 API 集成
    DRG_API_URL: str = "https://medchat.fun/api/drg-grouping"
    CODE_INFO_API_URL: str = "https://medchat.fun/api/find-info-by-code"
    DIP_API_URL: str = "https://medchat.fun/api/dip-grouping"
    DRG_API_MODE: str = "mock"  # mock, remote

    # 日志配置
    LOG_LEVEL: str = "INFO"

    # Demo 配置
    DEMO_MODE: bool = False
    DEMO_SEED: int = 20250101
    DEMO_SIZE: int = 200

    class Config:
        env_file = ".env"
        case_sensitive = True


# 全局配置实例
settings = Settings()
