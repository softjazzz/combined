from fastapi import APIRouter
from datetime import datetime
import subprocess
import os
from ..core.supabase_client import get_supabase
from ..core.settings import get_settings
from ..services.sichuan_qc_service import SichuanQCService

router = APIRouter(prefix="/api", tags=["system"])


@router.get("/health")
async def health():
    git_rev = ""
    try:
        git_rev = subprocess.check_output(["git", "rev-parse", "--short", "HEAD"], cwd=os.path.dirname(os.path.dirname(__file__))).decode().strip()
    except Exception:
        git_rev = "unknown"

    settings = get_settings()
    supabase_ok = get_supabase() is not None
    llm_ok = False
    try:
        # 简化健康检查：若存在任一启用 provider 或 model 即认为可用
        sb = get_supabase()
        if sb:
            p = sb.table("llm_api_providers").select("id").eq("is_active", True).limit(1).execute()
            m = sb.table("llm_models").select("id").eq("is_active", True).limit(1).execute()
            llm_ok = bool((p.data or []) or (m.data or []))
    except Exception:
        llm_ok = False

    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "version": "1.0.0",
        "git": git_rev,
        "dependencies": {
            "supabase": supabase_ok,
            "llm": llm_ok,
        },
        "env": settings.ENV,
    }


@router.get("/metrics")
async def metrics():
    """聚合简单运行指标，便于前端看板与运维脚本采集。"""
    sb = get_supabase()
    qc_stats = SichuanQCService().stats()

    return {
        "success": True,
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
    }

