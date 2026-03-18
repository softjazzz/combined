"""
LLM 閰嶇疆鍔犺浇鏈嶅姟
浠?Supabase 鏁版嵁搴撳姞杞?LLM 閰嶇疆锛屾敮鎸佸洖閫€鍒?.env 鏂囦欢
"""
from typing import Dict, Any, Optional
import logging
import base64

from ..core.supabase_client import get_supabase
from ..core.settings import get_settings

logger = logging.getLogger(__name__)


class LLMConfigLoader:
    """LLM 閰嶇疆鍔犺浇鍣紝鏀寔浠庢暟鎹簱鎴?.env 鏂囦欢鍔犺浇閰嶇疆"""
    
    @staticmethod
    async def load_config(config_name: str = "default", user_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """
        鍔犺浇 LLM 閰嶇疆
        
        浼樺厛绾э細
        1. 鏁版嵁搴撲腑鐨勭敤鎴烽厤缃紙濡傛灉鎸囧畾浜?user_id锛?
        2. 鏁版嵁搴撲腑鐨勫叏灞€閰嶇疆锛坲ser_id = NULL锛?
        3. .env 鏂囦欢閰嶇疆锛堝洖閫€鏂规锛?
        
        Args:
            config_name: 閰嶇疆鍚嶇О锛岄粯璁や负 "default"
            user_id: 鐢ㄦ埛 ID锛屽鏋滀负 None 鍒欏姞杞藉叏灞€閰嶇疆
            
        Returns:
            閰嶇疆瀛楀吀锛屽寘鍚互涓嬪瓧娈碉細
            - api_endpoint: API 绔偣
            - api_key: API 瀵嗛挜锛堝凡瑙ｅ瘑锛?
            - model: 妯″瀷浠ｇ爜
            - provider_code: 鎻愪緵鍟嗕唬鐮?
            - model_code: 妯″瀷浠ｇ爜
            - timeout_seconds: 瓒呮椂鏃堕棿
            濡傛灉鍔犺浇澶辫触鍒欒繑鍥?None
        """
        supabase = get_supabase()
        
        # 灏濊瘯浠庢暟鎹簱鍔犺浇
        if supabase is not None:
            try:
                config = await LLMConfigLoader._load_from_database(
                    supabase, config_name, user_id
                )
                if config:
                    logger.info(f"鉁?浠庢暟鎹簱鍔犺浇 LLM 閰嶇疆鎴愬姛: config_name={config_name}, user_id={user_id}, model={config.get('model')}")
                    return config
            except Exception as exc:
                logger.warning(f"浠庢暟鎹簱鍔犺浇 LLM 閰嶇疆澶辫触: {exc}锛屽皢鍥為€€鍒?.env 閰嶇疆")
        
        # 鍥為€€鍒?.env 鏂囦欢
        config = LLMConfigLoader._load_from_env()
        logger.info(f"鉁?浠?.env 鏂囦欢鍔犺浇 LLM 閰嶇疆: model={config.get('model')}")
        return config
    
    @staticmethod
    async def _load_from_database(
        supabase,
        config_name: str,
        user_id: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """浠庢暟鎹簱鍔犺浇閰嶇疆"""
        try:
            # 鏋勫缓鏌ヨ锛堜笉浣跨敤鍏宠仈鏌ヨ锛屽垎姝ユ煡璇級
            q = supabase.table("user_llm_configs").select("*").eq("config_name", config_name).eq("is_active", True)

            if user_id:
                q = q.eq("user_id", user_id)
            else:
                q = q.is_("user_id", None)  # type: ignore[attr-defined]

            # 鎵ц鏌ヨ
            resp = q.order("updated_at", desc=True).limit(1).execute()

            if not resp.data:
                logger.debug(f"鏁版嵁搴撲腑鏈壘鍒伴厤缃? config_name={config_name}, user_id={user_id}")
                return None

            db_config = resp.data[0]

            # 鍒嗗埆鏌ヨ provider 鍜?model
            provider = {}
            model = {}

            if db_config.get("provider_id"):
                try:
                    provider_resp = supabase.table("llm_api_providers").select("*").eq("id", db_config["provider_id"]).limit(1).execute()
                    if provider_resp.data:
                        provider = provider_resp.data[0]
                except Exception as e:
                    logger.warning(f"鏌ヨ provider 澶辫触: {e}")

            if db_config.get("model_id"):
                try:
                    model_resp = supabase.table("llm_models").select("*").eq("id", db_config["model_id"]).limit(1).execute()
                    if model_resp.data:
                        model = model_resp.data[0]
                except Exception as e:
                    logger.warning(f"鏌ヨ model 澶辫触: {e}")

            # 瑙ｅ瘑 API 瀵嗛挜
            api_key = None
            if db_config.get("api_key_encrypted"):
                try:
                    api_key = base64.b64decode(db_config["api_key_encrypted"]).decode("utf-8")
                except Exception as e:
                    logger.warning(f"瑙ｅ瘑 API 瀵嗛挜澶辫触: {e}")
                    api_key = None

            # 鏋勫缓閰嶇疆瀛楀吀
            config = {
                "api_endpoint": db_config.get("custom_endpoint") or provider.get("base_endpoint"),
                "api_key": api_key,
                "model": model.get("model_code"),
                "provider_code": provider.get("provider_code"),
                "model_code": model.get("model_code"),
                "timeout_seconds": 120,  # 榛樿瓒呮椂鏃堕棿
                "source": "database",
                "config_id": db_config.get("id"),
                "config_name": config_name,
                "custom_parameters": db_config.get("custom_parameters", {}),  # 鍖呭惈楂樼骇鍙傛暟
            }

            return config

        except Exception as exc:
            logger.error(f"浠庢暟鎹簱鍔犺浇閰嶇疆鏃跺嚭閿? {exc}")
            raise
    
    @staticmethod
    def _load_from_env() -> Dict[str, Any]:
        """浠?.env 鏂囦欢鍔犺浇閰嶇疆"""
        settings = get_settings()
        
        config = {
            "api_endpoint": str(settings.LLM_API_ENDPOINT) if settings.LLM_API_ENDPOINT else None,
            "api_key": settings.LLM_API_KEY,
            "model": settings.LLM_MODEL,
            "provider_code": "alibaba",  # 榛樿鎻愪緵鍟?
            "model_code": settings.LLM_MODEL,
            "timeout_seconds": settings.LLM_TIMEOUT_SECONDS,
            "source": "env",
            "config_name": "env_default",
        }
        
        return config
    
    @staticmethod
    async def reload_config_for_service(service, config_name: str = "default", user_id: Optional[str] = None) -> bool:
        """
        涓烘湇鍔￠噸鏂板姞杞介厤缃?
        
        Args:
            service: SichuanQCService 瀹炰緥
            config_name: 閰嶇疆鍚嶇О
            user_id: 鐢ㄦ埛 ID
            
        Returns:
            鏄惁鎴愬姛閲嶆柊鍔犺浇閰嶇疆
        """
        try:
            config = await LLMConfigLoader.load_config(config_name, user_id)
            if not config:
                logger.warning(f"鏃犳硶鍔犺浇閰嶇疆: config_name={config_name}, user_id={user_id}")
                return False
            
            # 鏇存柊鏈嶅姟鐨?LLM 瀹㈡埛绔厤缃?
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

                # 鏇存柊楂樼骇鍙傛暟
                custom_params = config.get("custom_parameters", {})
                if hasattr(client, 'temperature'):
                    client.temperature = custom_params.get("temperature", 0.2)
                if hasattr(client, 'top_p'):
                    client.top_p = custom_params.get("top_p", 0.9)
                if hasattr(client, 'max_tokens'):
                    client.max_tokens = custom_params.get("max_tokens", 16384)

                logger.info(f"鉁?鎴愬姛涓烘湇鍔￠噸鏂板姞杞介厤缃? model={client.model}, source={config.get('source')}, temperature={getattr(client, 'temperature', 'N/A')}, top_p={getattr(client, 'top_p', 'N/A')}")
                return True
            
            return False
            
        except Exception as exc:
            logger.error(f"閲嶆柊鍔犺浇閰嶇疆澶辫触: {exc}")
            return False


