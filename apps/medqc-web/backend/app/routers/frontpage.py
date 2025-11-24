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

    - visit_id 与 documents 至少提供一个
    - 当前骨架版本仅使用 demo 数据，不解析真实文书
    """

    visit_id: Optional[str] = Field(
        default=None, description="住院就诊 ID（后续用于从 EMR 获取全病历）"
    )
    documents: Optional[List[FrontPageDocument]] = Field(
        default=None, description="可选：直接传入文书列表，用于调试"
    )

    def ensure_valid(self) -> None:
        if not self.visit_id and not self.documents:
            raise ValueError("visit_id 和 documents 至少需要提供一个")


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
        if payload.documents:
            draft: FrontPageDraft = await service.generate_draft_from_documents(
                [doc.model_dump() for doc in payload.documents]
            )
        else:
            # 当前版本 visit_id 未参与真实逻辑，仅作为参数占位
            draft = await service.generate_draft_from_visit(payload.visit_id or "demo")

        return success_response(
            data={"frontpage": draft.model_dump()},  # visit 结构后续可补充
            message="自动生成病案首页草稿成功（demo 数据）",
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

