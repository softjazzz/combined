"""
LLM 配置加载服务
从 Supabase 数据库加载 LLM 配置，支持回退到 .env 文件
"""
from typing import Dict, Any, Optional
import logging
import base64

from ..core.supabase_client import get_supabase
from ..core.settings import get_settings

logger = logging.getLogger(__name__)


class LLMConfigLoader:
    """LLM 配置加载器，支持从数据库或 .env 文件加载配置"""
    
    @staticmethod
    async def load_config(config_name: str = "default", user_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """
        加载 LLM 配置
        
        优先级：
        1. 数据库中的用户配置（如果指定了 user_id）
        2. 数据库中的全局配置（user_id = NULL）
        3. .env 文件配置（回退方案）
        
        Args:
            config_name: 配置名称，默认为 "default"
            user_id: 用户 ID，如果为 None 则加载全局配置
            
        Returns:
            配置字典，包含以下字段：
            - api_endpoint: API 端点
            - api_key: API 密钥（已解密）
            - model: 模型代码
            - provider_code: 提供商代码
            - model_code: 模型代码
            - timeout_seconds: 超时时间
            如果加载失败则返回 None
        """
        supabase = get_supabase()
        
        # 尝试从数据库加载
        if supabase is not None:
            try:
                config = await LLMConfigLoader._load_from_database(
                    supabase, config_name, user_id
                )
                if config:
                    logger.info(f"✅ 从数据库加载 LLM 配置成功: config_name={config_name}, user_id={user_id}, model={config.get('model')}")
                    return config
            except Exception as exc:
                logger.warning(f"从数据库加载 LLM 配置失败: {exc}，将回退到 .env 配置")
        
        # 回退到 .env 文件
        config = LLMConfigLoader._load_from_env()
        logger.info(f"✅ 从 .env 文件加载 LLM 配置: model={config.get('model')}")
        return config
    
    @staticmethod
    async def _load_from_database(
        supabase,
        config_name: str,
        user_id: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """从数据库加载配置"""
        try:
            # 构建查询（不使用关联查询，分步查询）
            q = supabase.table("user_llm_configs").select("*").eq("config_name", config_name).eq("is_active", True)

            if user_id:
                q = q.eq("user_id", user_id)
            else:
                q = q.is_("user_id", None)  # type: ignore[attr-defined]

            # 执行查询
            resp = q.order("updated_at", desc=True).limit(1).execute()

            if not resp.data:
                logger.debug(f"数据库中未找到配置: config_name={config_name}, user_id={user_id}")
                return None

            db_config = resp.data[0]

            # 分别查询 provider 和 model
            provider = {}
            model = {}

            if db_config.get("provider_id"):
                try:
                    provider_resp = supabase.table("llm_api_providers").select("*").eq("id", db_config["provider_id"]).limit(1).execute()
                    if provider_resp.data:
                        provider = provider_resp.data[0]
                except Exception as e:
                    logger.warning(f"查询 provider 失败: {e}")

            if db_config.get("model_id"):
                try:
                    model_resp = supabase.table("llm_models").select("*").eq("id", db_config["model_id"]).limit(1).execute()
                    if model_resp.data:
                        model = model_resp.data[0]
                except Exception as e:
                    logger.warning(f"查询 model 失败: {e}")

            # 解密 API 密钥
            api_key = None
            if db_config.get("api_key_encrypted"):
                try:
                    api_key = base64.b64decode(db_config["api_key_encrypted"]).decode("utf-8")
                except Exception as e:
                    logger.warning(f"解密 API 密钥失败: {e}")
                    api_key = None

            # 构建配置字典
            config = {
                "api_endpoint": db_config.get("custom_endpoint") or provider.get("base_endpoint"),
                "api_key": api_key,
                "model": model.get("model_code"),
                "provider_code": provider.get("provider_code"),
                "model_code": model.get("model_code"),
                "timeout_seconds": 120,  # 默认超时时间
                "source": "database",
                "config_id": db_config.get("id"),
                "config_name": config_name,
                "custom_parameters": db_config.get("custom_parameters", {}),  # 包含高级参数
            }

            return config

        except Exception as exc:
            logger.error(f"从数据库加载配置时出错: {exc}")
            raise
    
    @staticmethod
    def _load_from_env() -> Dict[str, Any]:
        """从 .env 文件加载配置"""
        settings = get_settings()
        
        config = {
            "api_endpoint": str(settings.LLM_API_ENDPOINT) if settings.LLM_API_ENDPOINT else None,
            "api_key": settings.LLM_API_KEY,
            "model": settings.LLM_MODEL,
            "provider_code": "alibaba",  # 默认提供商
            "model_code": settings.LLM_MODEL,
            "timeout_seconds": settings.LLM_TIMEOUT_SECONDS,
            "source": "env",
            "config_name": "env_default",
        }
        
        return config
    
    @staticmethod
    async def reload_config_for_service(service, config_name: str = "default", user_id: Optional[str] = None) -> bool:
        """
        为服务重新加载配置
        
        Args:
            service: SichuanQCService 实例
            config_name: 配置名称
            user_id: 用户 ID
            
        Returns:
            是否成功重新加载配置
        """
        try:
            config = await LLMConfigLoader.load_config(config_name, user_id)
            if not config:
                logger.warning(f"无法加载配置: config_name={config_name}, user_id={user_id}")
                return False
            
            # 更新服务的 LLM 客户端配置
            if hasattr(service, 'client'):
                client = service.client
                if config.get("api_endpoint"):
                    client.api_endpoint = config["api_endpoint"]
                if config.get("api_key"):
                    client.api_key = config["api_key"]
                if config.get("model"):
                    client.model = config["model"]
                if config.get("timeout_seconds"):
                    client.timeout_seconds = config["timeout_seconds"]

                # 更新高级参数
                custom_params = config.get("custom_parameters", {})
                if hasattr(client, 'temperature'):
                    client.temperature = custom_params.get("temperature", 0.2)
                if hasattr(client, 'top_p'):
                    client.top_p = custom_params.get("top_p", 0.9)
                if hasattr(client, 'max_tokens'):
                    client.max_tokens = custom_params.get("max_tokens", 16384)

                logger.info(f"✅ 成功为服务重新加载配置: model={client.model}, source={config.get('source')}, temperature={getattr(client, 'temperature', 'N/A')}, top_p={getattr(client, 'top_p', 'N/A')}")
                return True
            
            return False
            
        except Exception as exc:
            logger.error(f"重新加载配置失败: {exc}")
            return False


