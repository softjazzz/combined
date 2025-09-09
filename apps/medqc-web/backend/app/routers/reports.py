from fastapi import APIRouter, HTTPException
from datetime import datetime
from typing import List, Dict, Any
import time
import csv
import os
from pydantic import BaseModel

from ..core.supabase_client import get_supabase
from ..core.settings import get_settings
from ..services.sichuan_qc_service import SichuanQCService

# naive in-memory cache for summary
_QC_SUMMARY_CACHE: Dict[str, Any] | None = None
_QC_SUMMARY_CACHE_TS: float = 0.0
_QC_SUMMARY_TTL_SECONDS = 10.0


router = APIRouter(prefix="/api/reports", tags=["reports"])


@router.get("/qc/summary")
async def qc_summary():
    """质控看板汇总（改为真实聚合）。

    - 从视图 `qc_statistics_view` 聚合：按病历维度统计文书总数、通过/告警/失败数量、平均分、最近分析时间。
    - `active_rules` 仍按启用规则计数。
    - 保留 10s 内存缓存以降低 Supabase 压力。
    """
    global _QC_SUMMARY_CACHE, _QC_SUMMARY_CACHE_TS
    now = time.time()
    if _QC_SUMMARY_CACHE is not None and (now - _QC_SUMMARY_CACHE_TS) < _QC_SUMMARY_TTL_SECONDS:
        return _QC_SUMMARY_CACHE

    sb = get_supabase()
    active_rules = 0
    total_records = 0
    totals = {
        "executions": 0,
        "passed": 0,
        "warning": 0,
        "failed": 0,
        "pending": 0,
        "avg_qc_score": 0.0,
    }

    if sb is not None:
        try:
            # 读取聚合视图
            view_rows = sb.table("qc_statistics_view").select("*").limit(1000).execute()
            rows = view_rows.data or []
            total_records = len(rows)
            if rows:
                for r in rows:
                    totals["executions"] += int(r.get("total_documents", 0) or 0)
                    totals["passed"] += int(r.get("passed_count", 0) or 0)
                    totals["warning"] += int(r.get("warning_count", 0) or 0)
                    totals["failed"] += int(r.get("failed_count", 0) or 0)
                    totals["pending"] += int(r.get("pending_count", 0) or 0)
                # 平均分（按视图返回的 avg_qc_score 做一次简单均值）
                avg_list = [float(r.get("avg_qc_score", 0) or 0) for r in rows if r.get("avg_qc_score") is not None]
                if avg_list:
                    totals["avg_qc_score"] = sum(avg_list) / len(avg_list)
        except Exception:
            pass

        try:
            rr = sb.table("qc_rules").select("*").eq("is_active", True).limit(1000).execute()
            active_rules = len(rr.data or [])
        except Exception:
            pass

    qc_stats = SichuanQCService().stats()

    result = {
        "success": True,
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "kpis": {
            "total_records": total_records,
            "active_rules": active_rules,
            "qc_executions": totals["executions"],
            "pass_rate": qc_stats.get("success_rate", 0.0),
            "avg_api_time": qc_stats.get("avg_api_time", 0.0),
            "avg_qc_score": round(totals["avg_qc_score"], 2),
            "passed": totals["passed"],
            "warning": totals["warning"],
            "failed": totals["failed"],
            "pending": totals["pending"],
        },
        "top_categories": [],
    }
    _QC_SUMMARY_CACHE = result
    _QC_SUMMARY_CACHE_TS = now
    return result


class ExportRequest(BaseModel):
    record_ids: List[str] | None = None


@router.post("/qc/export")
async def qc_export(payload: ExportRequest):
    """导出质控汇总（CSV）。

    - 数据来源：`qc_statistics_view`（若 Supabase 可用），否则返回 503。
    - 文件位置：`app/downloads/qc_summary_*.csv`，通过 `/downloads/*` 访问。
    """
    sb = get_supabase()
    if sb is None:
        raise HTTPException(status_code=503, detail="supabase unavailable")

    # 查询视图
    q = sb.table("qc_statistics_view").select("*").limit(5000)
    if payload.record_ids:
        # 过滤指定 record_id
        q = q.in_("record_id", payload.record_ids)
    resp = q.execute()
    rows: List[Dict[str, Any]] = list(resp.data or [])

    export_id = datetime.utcnow().strftime("%Y%m%d%H%M%S")
    filename = f"qc_summary_{export_id}.csv"
    downloads_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "downloads"))
    os.makedirs(downloads_dir, exist_ok=True)
    file_path = os.path.join(downloads_dir, filename)

    # 写 CSV
    headers = [
        "record_id",
        "total_documents",
        "passed_count",
        "warning_count",
        "failed_count",
        "pending_count",
        "avg_qc_score",
        "last_analyzed_time",
    ]
    with open(file_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=headers)
        writer.writeheader()
        for r in rows:
            writer.writerow({k: r.get(k) for k in headers})

    return {
        "success": True,
        "export_id": export_id,
        "requested_records": payload.record_ids or [],
        "download_url": f"/downloads/{filename}",
        "count": len(rows),
    }



