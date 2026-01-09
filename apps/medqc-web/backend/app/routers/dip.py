"""
DIP 分组路由

提供泸州市 DIP 入组预测接口
"""
from __future__ import annotations

from typing import Any, Dict, Optional
import logging

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/dip", tags=["dip"])


class DIPPredictRequest(BaseModel):
    """DIP 预测请求"""
    city_name: str = "泸州市"
    pdx_code: str  # 主诊断编码
    adx_code: Optional[str] = None  # 次要诊断编码
    proc_code: Optional[str] = None  # 手术/操作编码
    patient_gender: str = "M"  # M/F
    patient_age: int = 50
    los: int = 7  # 住院天数
    total_fee: float = 0  # 总费用


@router.post("/predict")
async def predict_dip_grouping(payload: DIPPredictRequest) -> Dict[str, Any]:
    """
    DIP 入组预测
    
    根据诊断和手术编码，预测 DIP 分组结果
    """
    from ..services.dip_grouping_service import DIPGrouperService
    
    try:
        service = DIPGrouperService()
        
        result = await service.group_dip(
            city_name=payload.city_name,
            pdx_code=payload.pdx_code,
            adx_code=payload.adx_code or "",
            proc_code=payload.proc_code or "",
            patient_gender=payload.patient_gender,
            patient_age=payload.patient_age,
            los=payload.los,
            total_fee=payload.total_fee
        )
        
        return {
            "success": True,
            "data": result,
            "message": "DIP 入组预测完成"
        }
    except Exception as e:
        logger.error(f"DIP 分组失败: {e}")
        # 返回降级结果
        return {
            "success": False,
            "data": {
                "dip_code": "CORE-综合",
                "dip_name": "综合分组",
                "dip_type": "综合",
                "grouping_path": f"降级模式: {str(e)}"
            },
            "message": f"DIP 分组降级: {str(e)}"
        }
