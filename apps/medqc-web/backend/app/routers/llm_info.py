from fastapi import APIRouter, Query, Request
from ..core.supabase_client import get_supabase, async_execute
from ..core.response import success_response, get_trace_id
from ..services.llm_config_loader import SUPPORTED_PROVIDER_CODES, get_enabled_provider_codes

router = APIRouter(prefix="/api/v1/llm", tags=["llm-info"])


@router.get("/providers")
async def providers(request: Request):
    """获取 LLM 提供商列表"""
    enabled_provider_codes = set(get_enabled_provider_codes())
    supabase = get_supabase()
    if supabase is not None:
        try:
            resp = await async_execute(supabase.table("llm_api_providers").select("*").eq("is_active", True))
            rows = [
                item for item in (resp.data or [])
                if str(item.get("provider_code") or "").strip().lower() in SUPPORTED_PROVIDER_CODES
                and str(item.get("provider_code") or "").strip().lower() in enabled_provider_codes
            ]
            return success_response(
                data=rows,
                message="获取提供商列表成功",
                trace_id=get_trace_id(request)
            )
        except Exception:
            pass

    # 静态回退
    fallback_providers = [
        {"id": "alibaba", "provider_name": "阿里云百炼", "provider_code": "alibaba"},
        {"id": "siliconflow", "provider_name": "SiliconFlow", "provider_code": "siliconflow"},
        {"id": "ollama", "provider_name": "内部 Ollama", "provider_code": "ollama"},
    ]
    fallback_providers = [
        item for item in fallback_providers
        if str(item.get("provider_code") or "").strip().lower() in enabled_provider_codes
    ]
    return success_response(
        data=fallback_providers,
        message="获取提供商列表成功（静态数据）",
        trace_id=get_trace_id(request)
    )


@router.get("/models")
async def models(request: Request, provider_id: str | None = Query(default=None)):
    """获取 LLM 模型列表"""
    enabled_provider_codes = set(get_enabled_provider_codes())
    supabase = get_supabase()
    if supabase is not None:
        try:
            q = supabase.table("llm_models").select("*").eq("is_active", True)
            if provider_id:
                q = q.eq("provider_id", provider_id)
            resp = await async_execute(q)
            rows = resp.data or []
            return success_response(
                data=rows,
                message="获取模型列表成功",
                trace_id=get_trace_id(request)
            )
        except Exception:
            pass

    # 静态回退
    fallback_models = [
        {"provider": "alibaba", "id": "qwen-plus", "model_code": "qwen-plus", "model_name": "Qwen-Plus"},
        {"provider": "alibaba", "id": "qwen3.5-35b-a3b", "model_code": "qwen3.5-35b-a3b", "model_name": "Qwen3.5-35B-A3B"},
        {
            "provider": "siliconflow",
            "id": "Qwen/Qwen3.5-27B",
            "model_code": "Qwen/Qwen3.5-27B",
            "model_name": "Qwen/Qwen3.5-27B"
        },
        {
            "provider": "siliconflow",
            "id": "Qwen/Qwen3.5-9B",
            "model_code": "Qwen/Qwen3.5-9B",
            "model_name": "Qwen/Qwen3.5-9B"
        },
        {
            "provider": "siliconflow",
            "id": "Qwen/Qwen3.5-4B",
            "model_code": "Qwen/Qwen3.5-4B",
            "model_name": "Qwen/Qwen3.5-4B"
        },
        {
            "provider": "ollama",
            "id": "qwen2.5:7b-instruct",
            "model_code": "qwen2.5:7b-instruct",
            "model_name": "qwen2.5:7b-instruct"
        },
    ]
    fallback_models = [
        item for item in fallback_models
        if str(item.get("provider") or "").strip().lower() in enabled_provider_codes
    ]
    return success_response(
        data=fallback_models,
        message="获取模型列表成功（静态数据）",
        trace_id=get_trace_id(request)
    )
