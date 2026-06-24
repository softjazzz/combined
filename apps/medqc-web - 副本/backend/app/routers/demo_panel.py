"""
演示面板 API 路由

为 P4-P8 前端面板提供数据接口：
- /api/v1/panel/messages/summary - 质控消息摘要
- /api/v1/panel/messages        - 质控消息列表
- /api/v1/panel/monitoring/alerts     - DRG 预警列表
- /api/v1/panel/monitoring/cmi-trend  - CMI 趋势
- /api/v1/panel/monitoring/cost-index - 费用消耗指数
- /api/v1/panel/monitoring/stats      - 事中监控统计
- /api/v1/panel/analysis/kpis         - 事后分析 KPI
- /api/v1/panel/analysis/report       - 事后分析报告
"""
from typing import Optional

from fastapi import APIRouter, Query, Request

from ..core.response import success_response, get_trace_id
from ..services.demo_panel_service import DemoPanelService

router = APIRouter(prefix="/api/v1/panel", tags=["panel"])
_service = DemoPanelService()


# ==================== P5: 质控消息概览 ====================

@router.get("/messages/summary")
async def get_qc_message_summary(request: Request):
    """获取质控消息统计摘要。"""
    data = _service.get_qc_message_summary()
    return success_response(data=data, message="获取消息摘要成功", trace_id=get_trace_id(request))


@router.get("/messages")
async def get_qc_messages(
    request: Request,
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    severity: Optional[str] = Query(None),
):
    """获取质控消息列表。"""
    data = _service.get_qc_messages(page=page, limit=limit)
    return success_response(data=data, message="获取消息列表成功", trace_id=get_trace_id(request))


# ==================== P7: 事中监控 ====================

@router.get("/monitoring/alerts")
async def get_drg_alerts(request: Request):
    """获取 DRG 预警列表。"""
    data = _service.get_drg_alerts()
    return success_response(data=data, message=f"共 {len(data)} 条预警", trace_id=get_trace_id(request))


@router.get("/monitoring/cmi-trend")
async def get_cmi_trend(
    request: Request,
    days: int = Query(7, ge=1, le=30),
):
    """获取 CMI 趋势数据。"""
    data = _service.get_cmi_trend(days=days)
    return success_response(data=data, message="获取CMI趋势成功", trace_id=get_trace_id(request))


@router.get("/monitoring/cost-index")
async def get_dept_cost_index(request: Request):
    """获取各科室费用消耗指数。"""
    data = _service.get_dept_cost_index()
    return success_response(data=data, message="获取费用消耗指数成功", trace_id=get_trace_id(request))


@router.get("/monitoring/stats")
async def get_monitoring_stats(request: Request):
    """获取事中监控统计卡片数据。"""
    data = _service.get_monitoring_stats()
    return success_response(data=data, message="获取监控统计成功", trace_id=get_trace_id(request))


# ==================== P8: 事后分析 ====================

@router.get("/analysis/kpis")
async def get_post_analysis_kpis(request: Request):
    """获取事后分析 KPI 卡片。"""
    data = _service.get_post_analysis_kpis()
    return success_response(data=data, message=f"共 {len(data)} 个指标", trace_id=get_trace_id(request))


@router.get("/analysis/report")
async def get_post_analysis_report(request: Request):
    """获取事后分析报告。"""
    data = _service.get_post_analysis_report()
    return success_response(data=data, message="获取分析报告成功", trace_id=get_trace_id(request))
