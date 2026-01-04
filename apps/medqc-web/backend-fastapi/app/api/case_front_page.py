"""\
病案首页 API
提供病案首页的查询与维护接口
"""

from typing import List, Optional, Dict, Any

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
try:
    from loguru import logger
except Exception:
    import logging

    logger = logging.getLogger(__name__)

from app.config import settings
from app.models.schemas import CaseFrontPageCreate, CaseFrontPageDetail
from app.services.database import db_service
from app.services.demo_data_store import get_demo_store
from app.services.llm_service import llm_service
from app.services.external_coding_service import external_coding_service

router = APIRouter(prefix="/case-front-page", tags=["病案首页"])


# 请求模型
class ExtractFrontpageRequest(BaseModel):
    """提取病案首页请求"""
    medical_text: str


class ExtractCodingRequest(BaseModel):
    """提取 ICD 编码请求"""
    medical_text: str
    patient_age: int = 50
    patient_gender: str = "M"  # M or F


@router.post(
    "/extract",
    summary="从病历原文中提取结构化数据",
    description="使用 LLM 从病历原文（入院记录、出院小结等）中提取病案首页结构化数据"
)
async def extract_frontpage_from_text(request: ExtractFrontpageRequest) -> Dict[str, Any]:
    """
    从病历原文中提取病案首页结构化数据
    
    Args:
        request: 包含 medical_text 的请求体
        
    Returns:
        结构化的病案首页数据
    """
    try:
        if not request.medical_text or len(request.medical_text.strip()) < 50:
            raise HTTPException(status_code=400, detail="病历原文内容过短，无法进行结构化提取")
        
        logger.info(f"开始 LLM 结构化提取，文本长度: {len(request.medical_text)}")
        
        result = await llm_service.extract_frontpage_structured(request.medical_text)
        
        if not result:
            raise HTTPException(status_code=500, detail="LLM 结构化提取失败，请检查 LLM 服务配置")
        
        return {
            "success": True,
            "data": result
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"结构化提取失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"结构化提取失败: {str(e)}")


@router.post(
    "/extract-coding",
    summary="从病历原文中提取 ICD 编码",
    description="调用外部编码服务，从病历原文中提取诊断和手术操作的 ICD 编码"
)
async def extract_coding_from_text(request: ExtractCodingRequest) -> Dict[str, Any]:
    """
    从病历原文中提取 ICD 编码
    
    使用外部专业编码服务（异步任务队列模式），
    返回主诊断、次诊断、主手术、次手术的 ICD 编码及置信度。
    
    Args:
        request: 包含 medical_text, patient_age, patient_gender 的请求体
        
    Returns:
        包含 coding_data 的结构化 ICD 编码结果
    """
    try:
        if not request.medical_text or len(request.medical_text.strip()) < 50:
            raise HTTPException(status_code=400, detail="病历原文内容过短，无法进行编码提取")
        
        logger.info(f"开始外部编码服务调用，文本长度: {len(request.medical_text)}")
        
        result = await external_coding_service.extract_coding(
            medical_text=request.medical_text,
            patient_context={
                "gender": request.patient_gender,
                "age": request.patient_age
            }
        )
        
        if not result.get("success"):
            raise HTTPException(
                status_code=500, 
                detail=result.get("error", "编码提取失败")
            )
        
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"编码提取失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"编码提取失败: {str(e)}")


class AnalyzeProfileRequest(BaseModel):
    """患者画像分析请求"""
    medical_text: str
    frontpage_diagnoses: List[str] = []
    frontpage_procedures: List[str] = []


@router.post(
    "/analyze-profile",
    summary="AI 患者画像分析",
    description="使用 LLM 对病历进行深度分析，生成诊断时间轴、生命体征趋势、风险评估等"
)
async def analyze_patient_profile(request: AnalyzeProfileRequest) -> Dict[str, Any]:
    """
    AI 患者画像分析
    
    从病历原文中提取：
    - 诊断发生发展时间轴
    - 生命体征趋势分析
    - 化验检查结果评估
    - 综合风险评估
    - 人体部位标记（用于可视化）
    
    Args:
        request: 包含病历原文和首页信息的请求体
        
    Returns:
        患者画像分析结果
    """
    try:
        if not request.medical_text or len(request.medical_text.strip()) < 50:
            raise HTTPException(status_code=400, detail="病历原文内容过短，无法进行画像分析")
        
        logger.info(f"开始患者画像分析，文本长度: {len(request.medical_text)}")
        
        result = await llm_service.analyze_patient_profile(
            medical_text=request.medical_text,
            frontpage_diagnoses=request.frontpage_diagnoses,
            frontpage_procedures=request.frontpage_procedures
        )
        
        if not result:
            raise HTTPException(status_code=500, detail="画像分析失败，请检查 LLM 服务配置")
        
        return {
            "success": True,
            "data": result
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"画像分析失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"画像分析失败: {str(e)}")


@router.get(
    "",
    response_model=List[CaseFrontPageDetail],
    summary="获取病案首页列表",
    description="获取病案首页列表（用于编码辅助列表页）"
)
async def list_case_front_pages(
    limit: int = Query(100, ge=1, le=500, description="返回数量"),
):
    try:
        if settings.DEMO_MODE or getattr(db_service, 'client', None) is None:
            store = get_demo_store()
            records = store.list_cases(limit=limit)
            return [CaseFrontPageDetail(**record) for record in records]

        records = await db_service.list_case_front_pages(limit=limit)
        if not records:
            store = get_demo_store()
            records = store.list_cases(limit=limit)
        return [CaseFrontPageDetail(**record) for record in records]
    except Exception as e:
        logger.error(f"获取病案首页列表失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"获取列表失败: {str(e)}")


@router.get(
    "/{admission_id}",
    response_model=CaseFrontPageDetail,
    summary="获取病案首页详情",
    description="根据住院号获取病案首页详情（包含次诊断、手术操作）"
)
async def get_case_front_page_detail(admission_id: str):
    try:
        if settings.DEMO_MODE or getattr(db_service, 'client', None) is None:
            store = get_demo_store()
            record = store.get_case_detail(admission_id)
            if not record:
                raise HTTPException(status_code=404, detail=f"未找到住院号 {admission_id} 的病案首页")
            return CaseFrontPageDetail(**record)

        record = await db_service.get_case_front_page_detail(admission_id)
        if not record:
            store = get_demo_store()
            record = store.get_case_detail(admission_id)
        if not record:
            raise HTTPException(status_code=404, detail=f"未找到住院号 {admission_id} 的病案首页")
        return CaseFrontPageDetail(**record)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取病案首页详情失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"获取详情失败: {str(e)}")


@router.post(
    "",
    response_model=CaseFrontPageDetail,
    summary="创建或更新病案首页",
    description="创建或更新病案首页（会同步保存次诊断、手术操作列表）"
)
async def upsert_case_front_page(payload: CaseFrontPageCreate):
    try:
        logger.info(f"保存病案首页: {payload.admission_id}")
        if settings.DEMO_MODE:
            store = get_demo_store()
            record = store.upsert_case(payload.model_dump())
            return CaseFrontPageDetail(**record)
        record = await db_service.upsert_case_front_page(payload)
        return CaseFrontPageDetail(**record)
    except Exception as e:
        logger.error(f"保存病案首页失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"保存失败: {str(e)}")

