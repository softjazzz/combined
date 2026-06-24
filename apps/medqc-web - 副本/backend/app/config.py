"""
配置管理模块
"""
import os
from functools import lru_cache
from typing import Optional

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """应用配置"""

    # 基础配置
    app_name: str = "MedQC Medical Quality Control System"
    app_version: str = "1.0.0"
    debug: bool = False

    # 数据库配置
    supabase_url: str
    supabase_key: Optional[str] = None  # 从 supabase_anon_key 映射
    supabase_anon_key: Optional[str] = None  # 兼容现有配置
    supabase_service_role_key: Optional[str] = None

    # API配置
    api_host: str = "0.0.0.0"
    api_port: int = 8000  # 修正：根据 DEVELOPMENT_PORTS.md，medqc-api 标准端口为 8000

    # 安全配置
    secret_key: Optional[str] = None  # 从 jwt_secret 映射
    jwt_secret: Optional[str] = None  # 兼容现有配置
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 30

    # CORS配置
    cors_origins: list = ["http://localhost:3000", "http://127.0.0.1:3000"]

    # LLM配置
    openai_api_key: Optional[str] = None
    deepseek_api_key: Optional[str] = None
    qwen_api_key: Optional[str] = None

    # 文件上传配置
    max_file_size: int = 50 * 1024 * 1024  # 50MB
    upload_dir: str = "uploads"

    def model_post_init(self, __context):
        # 映射兼容字段
        if self.supabase_anon_key and not self.supabase_key:
            self.supabase_key = self.supabase_anon_key
        if self.jwt_secret and not self.secret_key:
            self.secret_key = self.jwt_secret

    model_config = {
        "env_file": ".env",
        "case_sensitive": False,
        "extra": "ignore"  # 忽略额外字段
    }


@lru_cache()
def get_settings() -> Settings:
    """获取配置实例（单例模式）"""
    return Settings()
