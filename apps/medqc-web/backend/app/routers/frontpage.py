from typing import Any, Dict, List, Optional

import asyncio
import contextlib
import json

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
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


@router.post("/auto-generate-draft-stream")
async def auto_generate_frontpage_draft_stream(
    request: Request,
    payload: AutoGenerateFrontPageRequest,
    service: FrontPageExtractionService = Depends(get_frontpage_service),
):
    """
    自动生成病案首页草稿（流式分批返回）

    返回 `text/event-stream`：
    - event: update, data: {"module": "...", "frontpage": {...}}
    - event: done, data: {"frontpage": {...}}
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

    async def event_generator():
        print(f"\n[DEBUG] SSE 接口收到请求: visit_id={payload.visit_id}, medical_text_len={len(payload.medical_text or '')}")
        medical_text = payload.medical_text or ""
        visit_id = payload.visit_id or ""
        
        # 如果没有直接传入文本且有 visit_id，走三层架构（visit_id 透传给 stream 方法）
        # 三层架构会内部处理：SQL 直读 → 码表映射 → LLM 补缺
        if not medical_text and visit_id:
            print(f"[DEBUG] 三层架构模式: visit_id={visit_id}，SQL 直读 + LLM 补缺")
            # 同时获取 LLM 需要的文本作为 fallback
            medical_text = await service._get_llm_context_text(visit_id)
            print(f"[DEBUG] 获取到 LLM 上下文文本长度: {len(medical_text)}")
        
        queue: asyncio.Queue = asyncio.Queue()
        producer_task: Optional[asyncio.Task] = None

        async def produce():
            try:
                async for event_name, data in service.extract_from_text_stream(medical_text, visit_id=visit_id):
                    await queue.put((event_name, data))
            except Exception as exc:
                await queue.put(("error", {"success": False, "error": str(exc), "trace_id": trace_id}))
            finally:
                await queue.put(("__done__", None))

        try:
            # Flush headers/body immediately to avoid proxy idle timeouts
            yield ": ping\n\n"

            producer_task = asyncio.create_task(produce())

            while True:
                try:
                    event_name, data = await asyncio.wait_for(queue.get(), timeout=10)
                except asyncio.TimeoutError:
                    # Keep the connection alive during long LLM calls
                    yield ": ping\n\n"
                    continue

                if event_name == "__done__":
                    break

                if not isinstance(data, dict):
                    data = {}

                # Keep trace_id attached for debugging in devtools
                if "trace_id" not in data:
                    data["trace_id"] = trace_id

                yield f"event: {event_name}\n"
                yield f"data: {json.dumps(data, ensure_ascii=False)}\n\n"
        finally:
            if producer_task is not None and not producer_task.done():
                producer_task.cancel()
                with contextlib.suppress(Exception):
                    await producer_task

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Trace-Id": trace_id,
            "X-Accel-Buffering": "no",
        },
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
