from typing import Any, Dict, List, Optional

import asyncio
import contextlib
import json
import logging
import re
from io import BytesIO

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
logger = logging.getLogger(__name__)


def _extract_discharge_diagnoses_from_text(medical_text: str) -> List[str]:
    if not medical_text or not medical_text.strip():
        return []

    text = medical_text.replace("\r\n", "\n").replace("\r", "\n")
    lines = text.split("\n")
    start_idx = -1
    inline_text = ""
    for idx, raw in enumerate(lines):
        line = raw.strip()
        m = re.match(r"^出院诊断\s*[：:]\s*(.*)$", line)
        if m:
            start_idx = idx
            inline_text = m.group(1).strip()
            break
        if re.match(r"^出院诊断\s*$", line):
            start_idx = idx
            break
    if start_idx < 0:
        return []

    stop_header = re.compile(
        r"^(入院诊断|诊疗经过|出院情况|出院医嘱|医师签名|记录时间|主诉|现病史|既往史|体格检查|辅助检查|手术|手术名称|手术操作|操作名称)\s*[：:]?"
    )
    numbered = re.compile(r"^\s*\d{1,2}[\.、\)]\s*(.+?)\s*$")

    section: List[str] = []
    if inline_text:
        section.append(inline_text)
    for raw in lines[start_idx + 1 :]:
        line = raw.strip()
        if not line:
            continue
        if re.match(r"^={3,}$", line):
            break
        if stop_header.match(line):
            break
        section.append(raw)

    items: List[str] = []
    for raw in section:
        m = numbered.match(raw)
        text_line = (m.group(1) if m else raw).strip()
        if not text_line:
            continue
        split_parts = [p.strip() for p in re.split(r"[、，,；;]+", text_line) if p and p.strip()]
        if len(split_parts) == 1:
            tokens = [t.strip() for t in re.split(r"\s+", text_line) if t and t.strip()]
            if len(tokens) >= 2 and all(len(t) >= 4 for t in tokens):
                split_parts = tokens
        items.extend(split_parts if split_parts else [text_line])

    out: List[str] = []
    seen = set()
    for it in items:
        key = re.sub(r"[\s\-\u2022•·,，;；:：()（）\[\]【】]+", "", it.lower())
        if key and key not in seen:
            seen.add(key)
            out.append(it)
    return out


def _postprocess_frontpage_diagnoses(frontpage: Dict[str, Any], medical_text: str) -> Dict[str, Any]:
    diagnoses = frontpage.get("diagnoses")
    if not isinstance(diagnoses, dict):
        diagnoses = {}
        frontpage["diagnoses"] = diagnoses

    main = diagnoses.get("discharge_main_diagnosis_text")
    others = diagnoses.get("discharge_other_diagnoses_texts")
    has_main = isinstance(main, str) and bool(main.strip())
    has_others = isinstance(others, list) and any(str(x).strip() for x in others)
    if not has_main and not has_others:
        parsed = _extract_discharge_diagnoses_from_text(medical_text)
        if parsed:
            diagnoses["discharge_main_diagnosis_text"] = parsed[0]
            diagnoses["discharge_other_diagnoses_texts"] = parsed[1:]
            logger.info("frontpage auto-generate fallback parse filled diagnoses, count=%d", len(parsed))

    try:
        from ..services.local_icd_service import resolve_diagnosis_codes

        frontpage["diagnoses"] = resolve_diagnosis_codes(diagnoses)
    except Exception:
        logger.exception("frontpage auto-generate diagnosis postprocess failed")
    return frontpage


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
    force_llm: bool = Field(
        default=False, description="强制使用 LLM 提取（即使 SQL 层已有数据）"
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

        frontpage = draft.model_dump()
        if payload.medical_text:
            frontpage = _postprocess_frontpage_diagnoses(frontpage, payload.medical_text)

        return success_response(
            data={"frontpage": frontpage},
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
        print(f"\n[DEBUG] SSE 接口收到请求: visit_id={payload.visit_id}, medical_text_len={len(payload.medical_text or '')}, force_llm={payload.force_llm}")
        medical_text = payload.medical_text or ""
        visit_id = payload.visit_id or ""
        force_llm = payload.force_llm
        
        # 如果没有直接传入文本且有 visit_id，走三层架构（visit_id 透传给 stream 方法）
        # 三层架构会内部处理：SQL 直读 → 码表映射 → LLM 补缺
        if not medical_text and visit_id:
            print(f"[DEBUG] 三层架构模式: visit_id={visit_id}，SQL 直读 + LLM 补缺, force_llm={force_llm}")
            # 同时获取 LLM 需要的文本作为 fallback
            medical_text = await service._get_llm_context_text(visit_id)
            print(f"[DEBUG] 获取到 LLM 上下文文本长度: {len(medical_text)}")
        
        queue: asyncio.Queue = asyncio.Queue()
        producer_task: Optional[asyncio.Task] = None

        async def produce():
            try:
                async for event_name, data in service.extract_from_text_stream(medical_text, visit_id=visit_id, force_llm=force_llm):
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


# ==================== 首页导出 API ====================

from ..services.frontpage_export_service import FrontpageExportService, ExportFormat

_export_service = FrontpageExportService()


class ExportFrontpageRequest(BaseModel):
    """首页导出请求"""
    frontpage: Dict[str, Any] = Field(..., description="首页数据")
    format: str = Field("nhc", description="导出格式: nhc/insurance/settlement")


@router.post("/export")
async def export_frontpage(
    request: Request,
    payload: ExportFrontpageRequest,
):
    """
    导出病案首页为 Excel 文件。

    支持 3 种格式:
    - nhc: 卫健委标准住院病案首页
    - insurance: 医保病案首页
    - settlement: 医保结算清单
    """
    try:
        fmt = ExportFormat(payload.format)
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail=f"不支持的导出格式: {payload.format}。支持: nhc, insurance, settlement"
        )

    excel_bytes = _export_service.export(payload.frontpage, fmt)
    filename = _export_service.get_filename(payload.frontpage, fmt)

    return StreamingResponse(
        BytesIO(excel_bytes),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


from io import BytesIO as _BytesIO  # 避免与已有导入冲突

# 替换上面的 BytesIO 引用
@router.get("/export/formats")
async def get_export_formats(request: Request):
    """获取支持的导出格式列表。"""
    formats = [
        {"id": "nhc", "name": "卫健委标准住院病案首页", "description": "符合卫健委规范的标准住院病案首页"},
        {"id": "insurance", "name": "医保病案首页", "description": "医疗保险病案首页格式"},
        {"id": "settlement", "name": "医保结算清单", "description": "医疗保障基金结算清单"},
    ]
    return success_response(
        data=formats,
        message=f"支持 {len(formats)} 种导出格式",
        trace_id=get_trace_id(request),
    )

