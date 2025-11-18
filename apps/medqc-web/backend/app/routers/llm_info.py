from fastapi import APIRouter, Query, Request
from ..core.supabase_client import get_supabase, async_execute
from ..core.response import success_response, get_trace_id

router = APIRouter(prefix="/api/v1/llm", tags=["llm-info"])


@router.get("/providers")
async def providers(request: Request):
    """获取 LLM 提供商列表"""
    supabase = get_supabase()
    if supabase is not None:
        try:
            resp = await async_execute(supabase.table("llm_api_providers").select("*").eq("is_active", True))
            return success_response(
                data=resp.data or [],
                message="获取提供商列表成功",
                trace_id=get_trace_id(request)
            )
        except Exception:
            pass

    # 静态回退
    fallback_providers = [
        {"id": "openai", "name": "OpenAI"},
        {"id": "alibaba", "name": "Aliyun DashScope", "provider_code": "alibaba"},
        {"id": "deepseek", "name": "DeepSeek"},
    ]
    return success_response(
        data=fallback_providers,
        message="获取提供商列表成功（静态数据）",
        trace_id=get_trace_id(request)
    )


@router.get("/models")
async def models(request: Request, provider_id: str | None = Query(default=None)):
    """获取 LLM 模型列表"""
    supabase = get_supabase()
    if supabase is not None:
        try:
            q = supabase.table("llm_models").select("*").eq("is_active", True)
            if provider_id:
                q = q.eq("provider_id", provider_id)
            resp = await async_execute(q)
            return success_response(
                data=resp.data or [],
                message="获取模型列表成功",
                trace_id=get_trace_id(request)
            )
        except Exception:
            pass

    # 静态回退
    fallback_models = [
        {
            "provider": "alibaba",
            "id": "qwen2.5-14b-instruct",
            "model_code": "qwen2.5-14b-instruct",
            "model_name": "Qwen2.5-14B-Instruct"
        },
        {
            "provider": "alibaba",
            "id": "qwen3-30b-a3b-instruct-2507",
            "model_code": "qwen3-30b-a3b-instruct-2507",
            "model_name": "Qwen3-30B-A3B Instruct (2507)"
        },
        {
            "provider": "openai",
            "id": "gpt-4o-mini",
            "model_code": "gpt-4o-mini",
            "model_name": "GPT-4o-mini"
        },
        {
            "provider": "deepseek",
            "id": "deepseek-chat",
            "model_code": "deepseek-chat",
            "model_name": "DeepSeek-Chat"
        },
    ]
    return success_response(
        data=fallback_models,
        message="获取模型列表成功（静态数据）",
        trace_id=get_trace_id(request)
    )
