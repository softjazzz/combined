from fastapi import APIRouter, Query
from ..core.supabase_client import get_supabase

router = APIRouter(prefix="/api/llm", tags=["llm-info"])


@router.get("/providers")
async def providers():
    supabase = get_supabase()
    if supabase is not None:
        try:
            resp = supabase.table("llm_api_providers").select("*").eq("is_active", True).execute()
            return {"data": resp.data or []}
        except Exception:
            pass
    # 静态回退
    return {
        "providers": [
            {"id": "openai", "name": "OpenAI"},
            {"id": "alibaba", "name": "Aliyun DashScope", "provider_code": "alibaba"},
            {"id": "deepseek", "name": "DeepSeek"},
        ]
    }


@router.get("/models")
async def models(provider_id: str | None = Query(default=None)):
    supabase = get_supabase()
    if supabase is not None:
        try:
            q = supabase.table("llm_models").select("*").eq("is_active", True)
            if provider_id:
                q = q.eq("provider_id", provider_id)
            resp = q.execute()
            return {"data": resp.data or []}
        except Exception:
            pass
    # 静态回退
    return {
        "models": [
            {"provider": "alibaba", "id": "qwen2.5-14b-instruct", "model_code": "qwen2.5-14b-instruct", "model_name": "Qwen2.5-14B-Instruct"},
            {"provider": "openai", "id": "gpt-4o-mini", "model_code": "gpt-4o-mini", "model_name": "GPT-4o-mini"},
            {"provider": "deepseek", "id": "deepseek-chat", "model_code": "deepseek-chat", "model_name": "DeepSeek-Chat"},
        ]
    }

