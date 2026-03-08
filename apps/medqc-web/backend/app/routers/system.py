from fastapi import APIRouter, Request
from datetime import datetime
import subprocess
import os
import time
from inspect import isawaitable
from ..core.supabase_client import get_supabase
from ..core.settings import get_settings
from ..core.response import success_response, get_trace_id
from ..services.sichuan_qc_service import SichuanQCService

router = APIRouter(prefix="/api/v1", tags=["system"])

_HEALTH_CACHE_TTL_SECONDS = int(os.getenv("HEALTH_CACHE_TTL_SECONDS", "30"))
_git_rev_cache = "unknown"
_llm_health_cache = {
    "expires_at": 0.0,
    "llm_ok": False,
}


def _get_git_rev() -> str:
    global _git_rev_cache
    if _git_rev_cache != "unknown":
        return _git_rev_cache
    try:
        _git_rev_cache = subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=os.path.dirname(os.path.dirname(__file__)),
        ).decode().strip()
    except Exception:
        _git_rev_cache = "unknown"
    return _git_rev_cache


async def _exec_query(query):
    try:
        exec_async = getattr(query, "execute_async", None)
        if callable(exec_async):
            async_result = exec_async()
            if isawaitable(async_result):
                return await async_result
    except Exception:
        pass
    return query.execute()


async def _get_llm_health_cached(supabase) -> bool:
    now = time.time()
    if now < _llm_health_cache["expires_at"]:
        return bool(_llm_health_cache["llm_ok"])

    llm_ok = False
    if supabase is not None:
        try:
            p = await _exec_query(
                supabase.table("llm_api_providers").select("id").eq("is_active", True).limit(1)
            )
            m = await _exec_query(
                supabase.table("llm_models").select("id").eq("is_active", True).limit(1)
            )
            llm_ok = bool((p.data or []) or (m.data or []))
        except Exception:
            llm_ok = False

    _llm_health_cache["llm_ok"] = llm_ok
    _llm_health_cache["expires_at"] = now + _HEALTH_CACHE_TTL_SECONDS
    return llm_ok


@router.get("/health")
async def health(request: Request):
    """健康检查接口"""
    settings = get_settings()
    supabase = get_supabase()
    supabase_ok = supabase is not None
    llm_ok = await _get_llm_health_cached(supabase)

    return success_response(
        data={
            "status": "healthy",
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "version": "1.0.0",
            "git": _get_git_rev(),
            "dependencies": {
                "supabase": supabase_ok,
                "llm": llm_ok,
            },
            "env": settings.ENV,
        },
        trace_id=get_trace_id(request)
    )


@router.get("/metrics")
async def metrics(request: Request):
    """聚合简单运行指标，便于前端看板与运维脚本采集。"""
    sb = get_supabase()
    qc_stats = SichuanQCService().stats()

    return success_response(
        data={
            "system": {
                "env": get_settings().ENV,
            },
            "dependencies": {
                "supabase": sb is not None,
            },
            "qc": {
                "total_calls": qc_stats.get("total_calls", 0),
                "success_rate": qc_stats.get("success_rate", 0.0),
                "avg_api_time": qc_stats.get("avg_api_time", 0.0),
                "total_tokens": qc_stats.get("total_tokens", 0),
            },
            "timestamp": datetime.utcnow().isoformat() + "Z",
        },
        message="系统指标获取成功",
        trace_id=get_trace_id(request)
    )
