"""
质控员工作量排名 API（PG 版）

功能:
- 人均质控病历数排名
- 复审病历数排名
- 人工发现缺陷数排名
- 综合工作量统计

数据源：PostgreSQL v_qc_coder_ranking 视图
"""

import logging
from typing import Optional

from fastapi import APIRouter, Request, Depends, Query

from ..core.supabase_client import get_supabase, async_execute
from ..core.response import success_response, get_trace_id
from ..core.security import get_current_user

router = APIRouter(prefix="/api/v1/staff-ranking", tags=["staff-ranking"])
logger = logging.getLogger(__name__)


@router.get("")
async def get_staff_ranking(
    request: Request,
    period: str = Query("this_month", description="统计周期: this_week/this_month/this_quarter"),
    sort_by: str = Query("qc_count", description="排序字段: qc_count/recheck_count/defect_found/pass_rate"),
    current_user: dict = Depends(get_current_user),
):
    """
    获取质控员工作量排名

    返回每个质控员的:
    - qc_count: 质控病历数
    - recheck_count: 复审病历数
    - defect_found: 发现缺陷数
    - pass_rate: 通过率
    - avg_daily: 日均质控量
    """
    sb = get_supabase()
    if sb is None:
        raise HTTPException(status_code=503, detail="数据库不可用")

    try:
        # 从 v_qc_coder_ranking 视图读取
        resp = await async_execute(sb.table('v_qc_coder_ranking').select('*'))
        rows = list(getattr(resp, 'data', None) or [])

        # 合法排序字段
        valid_sort = {"qc_count", "recheck_count", "defect_found", "pass_rate", "avg_daily"}
        sort_key = sort_by if sort_by in valid_sort else "qc_count"

        rankings = sorted(rows, key=lambda r: float(r.get(sort_key, 0) or 0), reverse=True)

        # 汇总
        summary = {
            "total_qc": sum(int(r.get("qc_count", 0) or 0) for r in rankings),
            "total_recheck": sum(int(r.get("recheck_count", 0) or 0) for r in rankings),
            "total_defects": sum(int(r.get("defect_found", 0) or 0) for r in rankings),
            "avg_pass_rate": round(
                sum(float(r.get("pass_rate", 0) or 0) for r in rankings) / max(len(rankings), 1), 1
            ),
            "staff_count": len(rankings),
        }

        return success_response(
            data={
                "rankings": rankings,
                "summary": summary,
                "period": period,
                "sort_by": sort_by,
            },
            trace_id=get_trace_id(request),
        )
    except Exception as e:
        logger.error(f"获取工作量排名失败: {e}")
        # 视图不存在或无数据时返回空
        return success_response(
            data={
                "rankings": [],
                "summary": {"total_qc": 0, "total_recheck": 0, "total_defects": 0, "avg_pass_rate": 0, "staff_count": 0},
                "period": period,
                "sort_by": sort_by,
            },
            message=f"暂无排名数据: {str(e)}",
            trace_id=get_trace_id(request),
        )


# 导入 HTTPException（staff_ranking.py 中使用到）
from fastapi import HTTPException
