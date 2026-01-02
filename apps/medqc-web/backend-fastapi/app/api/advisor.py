"""
编码建议顾问 API
提供编码完整性分析与影子分组功能
"""

from fastapi import APIRouter, Depends, HTTPException, status
try:
    from loguru import logger
except Exception:
    import logging
    logger = logging.getLogger(__name__)

from app.models.schemas import (
    ShadowGroupingBatchRequest,
    ShadowGroupingBatchResponse,
    ErrorResponse,
    CodingCompletenessAnalysisRequest,
    CodingCompletenessResponse
)
from app.services.advisor_service import AdvisorService

router = APIRouter(
    prefix="/advisor",
    tags=["advisor"],
    responses={404: {"description": "Not found"}},
)

def get_advisor_service() -> AdvisorService:
    """获取 advisor 服务实例"""
    return AdvisorService()

@router.post(
    "/shadow-grouping/batch",
    response_model=ShadowGroupingBatchResponse,
    summary="批量影子分组试算",
    description="上传基准病历与候选变更建议，批量计算分组差异"
)
async def batch_shadow_grouping(
    request: ShadowGroupingBatchRequest,
    service: AdvisorService = Depends(get_advisor_service)
):
    try:
        logger.info(f"收到影子分组请求 ID={request.request_id}, 候选数={len(request.candidates)}")
        return await service.batch_shadow_grouping(request)
    except Exception as e:
        logger.error(f"影子分组处理失败: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"影子分组处理失败: {str(e)}"
        )

@router.post(
    "/coding-completeness/analyze",
    response_model=CodingCompletenessResponse,
    summary="编码完整性分析 (Layer A/B)",
    description="上传病历文本与当前编码，执行实体抽取与差距分析"
)
async def analyze_coding_completeness(
    request: CodingCompletenessAnalysisRequest,
    service: AdvisorService = Depends(get_advisor_service)
):
    try:
        logger.info("收到编码完整性分析请求")
        return await service.analyze_coding_completeness(
            request.medical_record,
            request.current_data
        )
    except Exception as e:
        logger.error(f"完整性分析处理失败: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"完整性分析处理失败: {str(e)}"
        )
