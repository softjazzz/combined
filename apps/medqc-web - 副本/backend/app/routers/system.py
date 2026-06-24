import asyncio
import logging
from fastapi import APIRouter, Request, Response, status
from datetime import datetime
import subprocess
import os
import time
from ..core.supabase_client import get_supabase, async_execute
from ..core.settings import get_settings
from ..core.response import success_response, get_trace_id
from ..core.runtime_metrics import runtime_request_metrics
from ..services.sichuan_qc_service import SichuanQCService
from ..services.sync_run_history import get_sync_health_stats

router = APIRouter(prefix="/api/v1", tags=["system"])
logger = logging.getLogger(__name__)

_HEALTH_CACHE_TTL_SECONDS = int(os.getenv("HEALTH_CACHE_TTL_SECONDS", "30"))
_HEALTH_REMOTE_TIMEOUT_SECONDS = float(os.getenv("HEALTH_REMOTE_TIMEOUT_SECONDS", "2.0"))
_HEALTH_REMOTE_CHECK_ENABLED = os.getenv("HEALTH_REMOTE_CHECK_ENABLED", "false").lower() == "true"
_git_rev_cache = "unknown"
_llm_health_cache = {
    "expires_at": 0.0,
    "llm_ok": False,
}


def _safe_float(value: object, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _safe_int(value: object, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _render_prometheus_metrics(
    runtime_metrics: dict,
    qc_stats: dict,
    sync_stats: dict,
    supabase_ok: bool,
    env: str,
) -> str:
    status_counts = runtime_metrics.get("status_counts", {}) if isinstance(runtime_metrics, dict) else {}
    total_requests = _safe_int(runtime_metrics.get("total_requests", 0))
    status_5xx = _safe_int(status_counts.get("5xx", 0)) if isinstance(status_counts, dict) else 0
    runtime_5xx_rate = (status_5xx / total_requests) if total_requests > 0 else 0.0
    sync_window_total = _safe_int(sync_stats.get("window_total_runs", 0))
    sync_window_failed = _safe_int(sync_stats.get("window_failed_runs", 0))
    sync_window_success = max(sync_window_total - sync_window_failed, 0)
    # Backlog proxy: use failed runs inside rolling window as retriable pressure estimate.
    sync_backlog_estimate = sync_window_failed
    metrics_lines = [
        "# HELP medqc_runtime_requests_total Total HTTP requests served by MedQC backend.",
        "# TYPE medqc_runtime_requests_total counter",
        f'medqc_runtime_requests_total{{env="{env}"}} {int(runtime_metrics.get("total_requests", 0))}',
        "# HELP medqc_runtime_requests_in_flight Current in-flight HTTP requests.",
        "# TYPE medqc_runtime_requests_in_flight gauge",
        f'medqc_runtime_requests_in_flight{{env="{env}"}} {int(runtime_metrics.get("in_flight_requests", 0))}',
        "# HELP medqc_runtime_request_errors_total Total HTTP requests with status >= 400.",
        "# TYPE medqc_runtime_request_errors_total counter",
        f'medqc_runtime_request_errors_total{{env="{env}"}} {int(runtime_metrics.get("error_requests", 0))}',
        "# HELP medqc_runtime_request_error_rate Error rate across total requests.",
        "# TYPE medqc_runtime_request_error_rate gauge",
        f'medqc_runtime_request_error_rate{{env="{env}"}} {_safe_float(runtime_metrics.get("error_rate"))}',
        "# HELP medqc_runtime_request_latency_avg_ms Average request latency in milliseconds.",
        "# TYPE medqc_runtime_request_latency_avg_ms gauge",
        f'medqc_runtime_request_latency_avg_ms{{env="{env}"}} {_safe_float(runtime_metrics.get("avg_latency_ms"))}',
        "# HELP medqc_runtime_request_latency_p95_ms P95 request latency in milliseconds.",
        "# TYPE medqc_runtime_request_latency_p95_ms gauge",
        f'medqc_runtime_request_latency_p95_ms{{env="{env}"}} {_safe_float(runtime_metrics.get("p95_latency_ms"))}',
        "# HELP medqc_runtime_requests_per_second Average requests per second since startup.",
        "# TYPE medqc_runtime_requests_per_second gauge",
        f'medqc_runtime_requests_per_second{{env="{env}"}} {_safe_float(runtime_metrics.get("requests_per_second"))}',
        "# HELP medqc_runtime_requests_per_second_1m Requests per second over the rolling 1-minute window.",
        "# TYPE medqc_runtime_requests_per_second_1m gauge",
        f'medqc_runtime_requests_per_second_1m{{env="{env}"}} {_safe_float(runtime_metrics.get("requests_per_second_1m"))}',
        "# HELP medqc_runtime_5xx_rate Ratio of 5xx responses across total requests.",
        "# TYPE medqc_runtime_5xx_rate gauge",
        f'medqc_runtime_5xx_rate{{env="{env}"}} {round(runtime_5xx_rate, 6)}',
        "# HELP medqc_dependency_supabase_up Supabase dependency status.",
        "# TYPE medqc_dependency_supabase_up gauge",
        f'medqc_dependency_supabase_up{{env="{env}"}} {1 if supabase_ok else 0}',
        "# HELP medqc_qc_total_calls Total calls sent to QC upstream.",
        "# TYPE medqc_qc_total_calls counter",
        f'medqc_qc_total_calls{{env="{env}"}} {int(qc_stats.get("total_calls", 0))}',
        "# HELP medqc_qc_success_rate Success rate of QC upstream calls.",
        "# TYPE medqc_qc_success_rate gauge",
        f'medqc_qc_success_rate{{env="{env}"}} {_safe_float(qc_stats.get("success_rate"))}',
        "# HELP medqc_qc_avg_api_time_seconds Average upstream QC API duration in seconds.",
        "# TYPE medqc_qc_avg_api_time_seconds gauge",
        f'medqc_qc_avg_api_time_seconds{{env="{env}"}} {_safe_float(qc_stats.get("avg_api_time"))}',
        "# HELP medqc_qc_total_tokens Total tokens consumed by QC upstream calls.",
        "# TYPE medqc_qc_total_tokens counter",
        f'medqc_qc_total_tokens{{env="{env}"}} {int(qc_stats.get("total_tokens", 0))}',
        "# HELP medqc_sync_window_runs_total Total sync runs observed in rolling window.",
        "# TYPE medqc_sync_window_runs_total gauge",
        f'medqc_sync_window_runs_total{{env="{env}"}} {sync_window_total}',
        "# HELP medqc_sync_window_success_runs_total Successful sync runs observed in rolling window.",
        "# TYPE medqc_sync_window_success_runs_total gauge",
        f'medqc_sync_window_success_runs_total{{env="{env}"}} {sync_window_success}',
        "# HELP medqc_sync_window_failed_runs_total Failed sync runs observed in rolling window.",
        "# TYPE medqc_sync_window_failed_runs_total gauge",
        f'medqc_sync_window_failed_runs_total{{env="{env}"}} {sync_window_failed}',
        "# HELP medqc_sync_failure_rate Sync failure ratio in rolling window.",
        "# TYPE medqc_sync_failure_rate gauge",
        f'medqc_sync_failure_rate{{env="{env}"}} {_safe_float(sync_stats.get("window_failure_rate"))}',
        "# HELP medqc_sync_last_success_lag_seconds Seconds since last successful sync.",
        "# TYPE medqc_sync_last_success_lag_seconds gauge",
        f'medqc_sync_last_success_lag_seconds{{env="{env}"}} {int(sync_stats.get("last_success_lag_seconds", 0))}',
        "# HELP medqc_sync_last_run_lag_seconds Seconds since last sync run (any status).",
        "# TYPE medqc_sync_last_run_lag_seconds gauge",
        f'medqc_sync_last_run_lag_seconds{{env="{env}"}} {int(sync_stats.get("last_run_lag_seconds", 0))}',
        "# HELP medqc_sync_backlog_estimate Estimated sync backlog size from failed runs in rolling window.",
        "# TYPE medqc_sync_backlog_estimate gauge",
        f'medqc_sync_backlog_estimate{{env="{env}"}} {sync_backlog_estimate}',
        "# HELP medqc_runtime_status_bucket_total HTTP response totals by status class.",
        "# TYPE medqc_runtime_status_bucket_total counter",
    ]

    for bucket in ("1xx", "2xx", "3xx", "4xx", "5xx", "unknown"):
        bucket_count = int(status_counts.get(bucket, 0)) if isinstance(status_counts, dict) else 0
        metrics_lines.append(
            f'medqc_runtime_status_bucket_total{{env="{env}",code_class="{bucket}"}} {bucket_count}'
        )

    return "\n".join(metrics_lines) + "\n"


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


async def _get_llm_health_cached(supabase) -> bool:
    now = time.time()
    if now < _llm_health_cache["expires_at"]:
        return bool(_llm_health_cache["llm_ok"])

    llm_ok = False
    if supabase is not None and _HEALTH_REMOTE_CHECK_ENABLED:
        try:
            async def _probe():
                p = await async_execute(
                    supabase.table("llm_api_providers").select("id").eq("is_active", True).limit(1)
                )
                m = await async_execute(
                    supabase.table("llm_models").select("id").eq("is_active", True).limit(1)
                )
                return p, m

            p, m = await asyncio.wait_for(_probe(), timeout=_HEALTH_REMOTE_TIMEOUT_SECONDS)
            llm_ok = bool((p.data or []) or (m.data or []))
        except asyncio.TimeoutError:
            logger.warning("LLM health probe timed out after %.1fs", _HEALTH_REMOTE_TIMEOUT_SECONDS)
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
            "llm_config": settings.llm_diagnostics(),
            "env": settings.ENV,
        },
        trace_id=get_trace_id(request)
    )


@router.get("/ready")
async def readiness(request: Request, response: Response):
    """
    Readiness probe for orchestrators and deployment gates.
    - returns 200 when minimum runtime dependencies are ready
    - returns 503 when critical dependency is unavailable
    """
    supabase = get_supabase()
    supabase_ok = supabase is not None
    runtime_metrics = runtime_request_metrics.snapshot()
    is_ready = supabase_ok

    if not is_ready:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE

    return success_response(
        data={
            "ready": is_ready,
            "dependencies": {
                "supabase": supabase_ok,
            },
            "runtime": runtime_metrics,
            "timestamp": datetime.utcnow().isoformat() + "Z",
        },
        trace_id=get_trace_id(request),
    )


@router.get("/metrics")
async def metrics(request: Request):
    """聚合简单运行指标，便于前端看板与运维脚本采集。"""
    sb = get_supabase()
    qc_stats = SichuanQCService().stats()
    runtime_metrics = runtime_request_metrics.snapshot()
    sync_stats = get_sync_health_stats(window_minutes=60)

    return success_response(
        data={
            "system": {
                "env": get_settings().ENV,
            },
            "dependencies": {
                "supabase": sb is not None,
            },
            "runtime": runtime_metrics,
            "qc": {
                "total_calls": qc_stats.get("total_calls", 0),
                "success_rate": qc_stats.get("success_rate", 0.0),
                "avg_api_time": qc_stats.get("avg_api_time", 0.0),
                "total_tokens": qc_stats.get("total_tokens", 0),
            },
            "sync": sync_stats,
            "timestamp": datetime.utcnow().isoformat() + "Z",
        },
        message="系统指标获取成功",
        trace_id=get_trace_id(request)
    )


@router.get("/metrics/prometheus")
async def metrics_prometheus():
    """
    Prometheus text exposition endpoint for production scraping.
    """
    sb = get_supabase()
    qc_stats = SichuanQCService().stats()
    runtime_metrics = runtime_request_metrics.snapshot()
    sync_stats = get_sync_health_stats(window_minutes=60)
    payload = _render_prometheus_metrics(
        runtime_metrics=runtime_metrics,
        qc_stats=qc_stats,
        sync_stats=sync_stats,
        supabase_ok=sb is not None,
        env=get_settings().ENV,
    )
    return Response(content=payload, media_type="text/plain; version=0.0.4")
