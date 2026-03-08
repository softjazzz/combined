"""
质控员工作量排名 API

功能:
- 人均质控病历数排名
- 复审病历数排名
- 人工发现缺陷数排名
- 综合工作量统计
"""

import logging
from typing import Optional

from fastapi import APIRouter, Request, Depends, Query

from ..core.response import success_response, get_trace_id
from ..core.security import get_current_user

router = APIRouter(prefix="/api/v1/staff-ranking", tags=["staff-ranking"])
logger = logging.getLogger(__name__)


# ==================== 内置 mock 数据 ====================
_STAFF_DATA = [
    {"user_id": "u1", "name": "王质控", "department": "质控科", "avatar": None},
    {"user_id": "u2", "name": "张质控", "department": "质控科", "avatar": None},
    {"user_id": "u3", "name": "李质控", "department": "质控科", "avatar": None},
    {"user_id": "u4", "name": "赵质控", "department": "质控科", "avatar": None},
    {"user_id": "u5", "name": "陈质控", "department": "质控科", "avatar": None},
    {"user_id": "u6", "name": "刘质控", "department": "质控科", "avatar": None},
]

_WORKLOAD_DATA = {
    "u1": {"qc_count": 156, "recheck_count": 42, "defect_found": 89, "pass_rate": 92.3},
    "u2": {"qc_count": 134, "recheck_count": 38, "defect_found": 76, "pass_rate": 88.7},
    "u3": {"qc_count": 128, "recheck_count": 35, "defect_found": 71, "pass_rate": 91.2},
    "u4": {"qc_count": 112, "recheck_count": 28, "defect_found": 65, "pass_rate": 85.4},
    "u5": {"qc_count": 98, "recheck_count": 22, "defect_found": 54, "pass_rate": 90.1},
    "u6": {"qc_count": 87, "recheck_count": 18, "defect_found": 43, "pass_rate": 93.5},
}


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
    """
    # 周期系数（模拟不同时间段的数据差异）
    period_factor = {"this_week": 0.25, "this_month": 1.0, "this_quarter": 3.0}.get(period, 1.0)

    rankings = []
    for staff in _STAFF_DATA:
        uid = staff["user_id"]
        workload = _WORKLOAD_DATA.get(uid, {})
        rankings.append({
            **staff,
            "qc_count": int(workload.get("qc_count", 0) * period_factor),
            "recheck_count": int(workload.get("recheck_count", 0) * period_factor),
            "defect_found": int(workload.get("defect_found", 0) * period_factor),
            "pass_rate": round(workload.get("pass_rate", 0), 1),
            "avg_daily": round(workload.get("qc_count", 0) * period_factor / (7 if period == "this_week" else 30 if period == "this_month" else 90), 1),
        })

    # 排序
    rankings.sort(key=lambda r: r.get(sort_by, 0), reverse=(sort_by != "pass_rate" or True))

    # 汇总
    summary = {
        "total_qc": sum(r["qc_count"] for r in rankings),
        "total_recheck": sum(r["recheck_count"] for r in rankings),
        "total_defects": sum(r["defect_found"] for r in rankings),
        "avg_pass_rate": round(sum(r["pass_rate"] for r in rankings) / max(len(rankings), 1), 1),
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
