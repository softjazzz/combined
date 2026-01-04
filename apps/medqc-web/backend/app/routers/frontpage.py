from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from ..core.response import success_response, error_response, get_trace_id
from ..schemas.frontpage import FrontPageDraft
from ..services.frontpage_extraction_service import (
    FrontPageExtractionService,
    default_frontpage_service,
)

router = APIRouter(prefix="/api/v1/frontpage", tags=["frontpage"])


class FrontPageDocument(BaseModel):
    """用于直接传入文书内容的简单模型"""

    type: str = Field(..., description="文书类型，如 admission_record / discharge_record 等")
    content: str = Field(..., description="文书正文内容")
    meta: Optional[Dict[str, Any]] = Field(
        default=None, description="可选的元数据（时间、作者、科室等）"
    )


class AutoGenerateFrontPageRequest(BaseModel):
    """
    病案首页自动生成请求

    - visit_id、documents、medical_text 至少提供一个
    - 优先级：medical_text > documents > visit_id
    """

    visit_id: Optional[str] = Field(
        default=None, description="住院就诊 ID（后续用于从 EMR 获取全病历）"
    )
    documents: Optional[List[FrontPageDocument]] = Field(
        default=None, description="可选：直接传入文书列表，用于调试"
    )
    medical_text: Optional[str] = Field(
        default=None, description="可选：直接传入病历全文进行提取"
    )

    def ensure_valid(self) -> None:
        if not self.visit_id and not self.documents and not self.medical_text:
            raise ValueError("visit_id、documents、medical_text 至少需要提供一个")


def get_frontpage_service() -> FrontPageExtractionService:
    """依赖注入：获取首页抽取服务实例"""
    return default_frontpage_service


@router.post("/auto-generate-draft")
async def auto_generate_frontpage_draft(
    request: Request,
    payload: AutoGenerateFrontPageRequest,
    service: FrontPageExtractionService = Depends(get_frontpage_service),
):
    """
    自动生成病案首页草稿（不含 ICD 编码）

    当前实现：
    - 不解析真实病历，仅返回 demo JSON 中的 frontpage 数据，作为骨架和前端联调基础。
    - 后续将在此处接入：
      - 根据 visit_id 获取全病历文书；
      - 调用 LLM 抽取字段；
      - 构造 FrontPageDraft 返回。
    """
    trace_id = get_trace_id(request)
    try:
        payload.ensure_valid()
    except ValueError as ve:
        raise HTTPException(
            status_code=400,
            detail=error_response(
                error=str(ve), code="BAD_REQUEST", trace_id=trace_id
            )["error"],
        )

    try:
        if payload.medical_text:
            # 直接从传入的病历文本提取
            draft: FrontPageDraft = await service.extract_from_text(payload.medical_text)
        elif payload.documents:
            draft = await service.generate_draft_from_documents(
                [doc.model_dump() for doc in payload.documents]
            )
        else:
            # 当前版本 visit_id 未参与真实逻辑，仅作为参数占位
            draft = await service.generate_draft_from_visit(payload.visit_id or "demo")

        return success_response(
            data={"frontpage": draft.model_dump()},
            message="自动生成病案首页草稿成功",
            trace_id=trace_id,
        )
    except HTTPException:
        raise
    except Exception as exc:
        # 返回统一错误格式，便于前端 debug
        return error_response(
            error=f"自动生成病案首页草稿失败: {exc}",
            code="FRONTPAGE_GENERATE_ERROR",
            trace_id=trace_id,
        )


class ProfileAnalyzeRequest(BaseModel):
    """医疗画像分析请求"""
    visit_id: Optional[str] = None
    medical_text: Optional[str] = None
    frontpage_diagnoses: Optional[List[str]] = None
    frontpage_procedures: Optional[List[str]] = None


@router.post("/profile/analyze")
async def analyze_medical_profile(
    request: Request,
    payload: ProfileAnalyzeRequest,
):
    """
    F13：疾病诊断和手术操作画像分析
    
    功能：
    1. 诊断时间轴提取
    2. 手术闭环验证
    3. 首页差异分析
    
    返回：
    - diagnosis_timeline: 诊断时间轴
    - surgery_verification: 手术验证结果
    - discrepancies: 差异分析
    """
    from ..services.diagnosis_surgery_profiling_service import get_profiling_service
    
    trace_id = get_trace_id(request)
    
    try:
        service = get_profiling_service()
        
        # 获取病历文本
        medical_text = payload.medical_text
        if not medical_text and payload.visit_id:
            # 从 visit_id 获取病历（复用 frontpage service）
            fp_service = get_frontpage_service()
            medical_text = await fp_service._get_medical_text(payload.visit_id)
        
        if not medical_text:
            return error_response(
                error="需要提供 medical_text 或有效的 visit_id",
                code="MISSING_MEDICAL_TEXT",
                trace_id=trace_id,
            )
        
        # 分析画像
        profile = await service.analyze_medical_profile(
            medical_text=medical_text,
            frontpage_diagnoses=payload.frontpage_diagnoses,
            frontpage_procedures=payload.frontpage_procedures,
        )
        
        return success_response(
            data=profile.to_dict(),
            message="医疗画像分析完成",
            trace_id=trace_id,
        )
    except Exception as exc:
        return error_response(
            error=f"医疗画像分析失败: {exc}",
            code="PROFILE_ANALYZE_ERROR",
            trace_id=trace_id,
        )
