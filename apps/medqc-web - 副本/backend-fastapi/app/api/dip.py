"""
DIP 分组 API
"""
from fastapi import APIRouter, HTTPException
try:
    from loguru import logger
except Exception:
    import logging
    logger = logging.getLogger(__name__)

from app.models.schemas import DIPPredictRequest, DIPPredictionResponse
from app.services.dip_grouper import dip_grouper

router = APIRouter(prefix="/dip", tags=["DIP分组"])

@router.post(
    "/predict",
    response_model=DIPPredictionResponse,
    summary="DIP 入组预测",
    description="调用外部 DIP 引擎进行入组预测"
)
async def predict_dip_grouping(request: DIPPredictRequest):
    try:
        logger.info(f"接收 DIP 分组预测请求: City={request.city_name}, PDX={request.pdx_code}")
        
        result = await dip_grouper.group(
            city_name=request.city_name,
            pdx_code=request.pdx_code,
            adx_code=request.adx_code,
            proc_code=request.proc_code,
            patient_gender=request.patient_gender,
            patient_age=request.patient_age,
            los=request.los,
            total_fee=request.total_fee
        )
        
        return DIPPredictionResponse(
            data=result,
            message="分组成功"
        )

    except Exception as e:
        logger.error(f"DIP 分组失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"分组失败: {str(e)}")
