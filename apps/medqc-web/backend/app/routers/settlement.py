"""
医保结算清单 API 路由

挂载到 /api/medical-records 前缀下，与现有病案数据路由保持一致。
"""

from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from ..services.settlement_service import get_settlement_service

router = APIRouter(prefix="/api/medical-records", tags=["结算清单"])


@router.get("/settlement/list")
async def list_settlements(
    dept: Optional[str] = Query(None, description="科室筛选"),
    keyword: Optional[str] = Query(None, description="搜索病案号/住院号"),
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页条数"),
):
    """获取医保结算清单列表（分页）"""
    svc = get_settlement_service()
    return svc.list_settlements(dept=dept, keyword=keyword, page=page, page_size=page_size)


@router.get("/settlement/{patient_id}/{visit_id}")
async def get_settlement_detail(
    patient_id: str,
    visit_id: str,
    institute_id: Optional[str] = Query(None, description="机构号（可选，默认自动匹配）"),
):
    """获取单条结算清单完整详情（含诊断、手术、费用明细）"""
    svc = get_settlement_service()
    result = svc.get_settlement_detail(patient_id, visit_id, institute_id)
    if not result:
        raise HTTPException(status_code=404, detail="结算清单未找到")
    return result


@router.post("/settlement/{patient_id}/{visit_id}/qc")
async def run_settlement_qc(
    patient_id: str,
    visit_id: str,
    institute_id: Optional[str] = Query(None, description="机构号（可选）"),
):
    """对单条结算清单执行形式质控（136条规则）"""
    svc = get_settlement_service()
    result = svc.run_qc(patient_id, visit_id, institute_id)
    if not result:
        raise HTTPException(status_code=404, detail="结算清单未找到，无法执行质控")
    return result


@router.get("/settlement/rules")
async def get_settlement_qc_rules():
    """获取结算清单质控规则摘要"""
    svc = get_settlement_service()
    return svc.get_rules_summary()
