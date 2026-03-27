"""
智能上传 + 字段映射 + 报表生成 API
从 drg 项目迁移并整合到 medqc 的统一路由。

流程：
1. POST /smart-upload — 上传任意 Excel，自动启动 LLM 字段映射
2. GET  /mapping-status/{file_id} — 轮询映射完成状态
3. POST /mapping/suggest — 获取 AI 推荐的字段映射
4. POST /mapping/confirm — 确认映射并执行分析，生成报表
"""
from __future__ import annotations

import json
import logging
import os
from typing import Dict, Optional

import pandas as pd
from fastapi import APIRouter, Depends, File, HTTPException, Query, Request, UploadFile
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from ..core.rate_limit import enforce_rate_limit
from ..core.security import get_current_user
from ..core.upload_security import validate_uploaded_file
from ..services.field_mapper import STANDARD_FIELDS, suggest_field_mapping
from ..services.multi_file_processor import MultiFileProcessor
from ..services.smart_upload_async_service import get_smart_upload_async_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/drg", tags=["smart-upload"])

# 上传目录配置
UPLOAD_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)

MAX_FILE_SIZE = 50 * 1024 * 1024  # 50 MB
ALLOWED_EXTENSIONS = {".xlsx", ".xls", ".csv", ".zip"}
ALLOWED_MIME_TYPES = {
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "application/vnd.ms-excel",
    "text/csv",
    "application/csv",
    "text/plain",
    "application/zip",
    "application/x-zip-compressed",
}


# ============================================================================
# Pydantic Models
# ============================================================================

class MappingSuggestRequest(BaseModel):
    file_id: str

class MappingConfirmRequest(BaseModel):
    file_id: str
    mappings: Dict[str, str]  # {"用户列名": "标准字段key", ...}

class ReportGenerateRequest(BaseModel):
    file_id: str
    field_mappings: Optional[Dict[str, str]] = None
    target_department: Optional[str] = None


# ============================================================================
# 1. 上传文件
# ============================================================================

@router.post("/smart-upload")
async def smart_upload(
    request: Request,
    file: UploadFile = File(...),
    sync: bool = Query(False),
    current_user: dict = Depends(get_current_user),
):
    """
    智能上传：上传任意格式的 Excel/CSV/ZIP 文件

    默认异步返回 task_id；显式 sync=true 时返回原始同步结果。
    """
    enforce_rate_limit(request, bucket="drg_smart_upload", max_requests=10, window_seconds=60)
    task_service = get_smart_upload_async_service(UPLOAD_DIR)

    filename = file.filename or "unknown"
    ext = os.path.splitext(filename)[1].lower()

    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"不支持的文件格式: {ext}，仅支持 .xlsx/.xls/.csv/.zip"
        )

    # 读取文件
    content = await file.read()
    validate_uploaded_file(
        request=request,
        file=file,
        content=content,
        allowed_extensions=ALLOWED_EXTENSIONS,
        allowed_content_types=ALLOWED_MIME_TYPES,
        max_bytes=MAX_FILE_SIZE,
    )

    if sync:
        try:
            result = task_service.process_upload_sync(filename=filename, content=content)
            return result
        except HTTPException:
            raise
        except Exception as exc:
            raise HTTPException(status_code=400, detail=f"文件处理失败: {exc}") from exc

    task = task_service.submit_upload(filename=filename, content=content, current_user=current_user)
    return JSONResponse(
        status_code=202,
        content={
            "success": True,
            "message": "任务已提交，正在后台处理",
            "task_id": task["task_id"],
            "file_id": task["file_id"],
            "filename": task["filename"],
            "status": task["status"],
            "progress": task["progress"],
            "status_url": f"/api/v1/drg/smart-upload/tasks/{task['task_id']}",
            "result_url": f"/api/v1/drg/smart-upload/tasks/{task['task_id']}/result",
            "cancel_url": f"/api/v1/drg/smart-upload/tasks/{task['task_id']}/cancel",
        },
    )


# =====================================================================
# 1.1 任务状态 / 结果 / 取消
# =====================================================================

@router.get("/smart-upload/tasks/{task_id}")
async def get_smart_upload_task_status(task_id: str):
    service = get_smart_upload_async_service(UPLOAD_DIR)
    return service.get_task_status(task_id)


@router.get("/smart-upload/tasks/{task_id}/result")
async def get_smart_upload_task_result(task_id: str):
    service = get_smart_upload_async_service(UPLOAD_DIR)
    return service.get_task_result(task_id)


@router.post("/smart-upload/tasks/{task_id}/cancel")
async def cancel_smart_upload_task(task_id: str):
    service = get_smart_upload_async_service(UPLOAD_DIR)
    return service.cancel_task(task_id)


# ============================================================================ 
# 2. 映射状态查询（前端轮询）
# ============================================================================

@router.get("/mapping-status/{file_id}")
async def get_mapping_status(file_id: str):
    """查询后台 LLM 字段映射是否完成"""
    if ".." in file_id or "/" in file_id or "\\" in file_id:
        raise HTTPException(status_code=400, detail="无效的文件 ID")
    
    cache_path = os.path.join(UPLOAD_DIR, file_id, "mapping.json")
    
    if os.path.exists(cache_path):
        try:
            with open(cache_path, "r", encoding="utf-8") as f:
                cached = json.load(f)
            return {
                "ready": True,
                "mapping_count": len(cached.get("mappings", {})),
                "confidence": cached.get("confidence", 0),
                "mappings": cached.get("mappings", {}),
                "unmapped": cached.get("unmapped", []),
                "missing_required": cached.get("missing_required", []),
            }
        except Exception:
            return {"ready": False}
    
    return {"ready": False}


# ============================================================================
# 3. 获取字段映射建议
# ============================================================================

@router.post("/mapping/suggest")
async def suggest_mapping(request: MappingSuggestRequest):
    """
    获取 AI 推荐的字段映射

    如果后台 LLM 映射已完成则直接返回缓存结果，
    否则同步调用 LLM 获取映射建议。
    """
    file_id = request.file_id
    file_dir = os.path.join(UPLOAD_DIR, file_id)
    
    if not os.path.exists(file_dir):
        raise HTTPException(status_code=404, detail="文件不存在")
    
    # 优先检查缓存
    cache_path = os.path.join(file_dir, "mapping.json")
    if os.path.exists(cache_path):
        try:
            with open(cache_path, "r", encoding="utf-8") as f:
                cached = json.load(f)
            if cached.get("mappings"):
                return {
                    "file_id": file_id,
                    "suggested_mappings": cached["mappings"],
                    "confidence": cached.get("confidence", 0.85),
                    "unmapped": cached.get("unmapped", []),
                    "missing_required": cached.get("missing_required", []),
                    "standard_fields": STANDARD_FIELDS,
                    "fallback": cached.get("fallback", False),
                }
        except Exception:
            pass
    
    # 缓存不存在，读取文件数据后同步调用 LLM
    excel_files = [
        os.path.join(file_dir, f)
        for f in os.listdir(file_dir)
        if f.endswith((".xlsx", ".xls"))
    ]
    if not excel_files:
        raise HTTPException(status_code=404, detail="数据文件不存在")
    
    processor = MultiFileProcessor(file_dir)
    processor.explore_files(excel_files)
    if not processor.files_info:
        raise HTTPException(status_code=400, detail="Excel 解析失败")

    first_file = processor.files_info[0]
    try:
        preview_df = pd.read_excel(first_file["path"], sheet_name=first_file.get("sheet_name", 0), nrows=5)
    except Exception:
        preview_df = pd.read_excel(first_file["path"], nrows=5)

    preview_df.columns = [processor._normalize_column_name(c) for c in list(preview_df.columns)]
    columns = list(preview_df.columns)
    sample_data = preview_df.fillna("").astype(str).to_dict(orient="records")
    
    mapping_result = await suggest_field_mapping(columns, sample_data)
    
    # 写入缓存
    try:
        with open(cache_path, "w", encoding="utf-8") as f:
            json.dump(mapping_result, f, ensure_ascii=False, indent=2)
    except Exception:
        pass
    
    return {
        "file_id": file_id,
        "columns": columns,
        "sample_data": sample_data,
        "suggested_mappings": mapping_result.get("mappings", {}),
        "confidence": mapping_result.get("confidence", 0.5),
        "unmapped": mapping_result.get("unmapped", []),
        "missing_required": mapping_result.get("missing_required", []),
        "standard_fields": STANDARD_FIELDS,
        "fallback": mapping_result.get("fallback", False),
    }


# ============================================================================
# 4. 确认映射 + 执行分析 + 生成报表
# ============================================================================

@router.post("/mapping/confirm")
async def confirm_mapping(request: MappingConfirmRequest):
    """
    确认字段映射，执行数据清洗 + EnhancedAnalyzer 分析 + ChartService 生成报表

    返回完整的分析结果（包含 ECharts 配置和 AI 洞察）
    """
    from ..services.analyzers import EnhancedAnalyzer
    from ..services.charts import ChartService
    
    file_id = request.file_id
    file_dir = os.path.join(UPLOAD_DIR, file_id)
    
    if not os.path.exists(file_dir):
        raise HTTPException(status_code=404, detail="文件不存在")
    
    # 1. 读取并处理数据
    excel_files = [
        os.path.join(file_dir, f)
        for f in os.listdir(file_dir)
        if f.endswith((".xlsx", ".xls"))
    ]
    if not excel_files:
        raise HTTPException(status_code=404, detail="数据文件不存在")
    
    processor = MultiFileProcessor(file_dir)
    processor.explore_files(excel_files)
    processor.merge_files(column_mode="intersection")
    processor.clean_data()
    
    df = processor.merged_df
    if df is None or df.empty:
        raise HTTPException(status_code=400, detail="数据为空")
    
    # 2. 应用字段映射
    mappings = request.mappings
    df_mapped = df.copy()
    rename_map = {k: v for k, v in mappings.items() if k in df_mapped.columns}
    if rename_map:
        df_mapped = df_mapped.rename(columns=rename_map)
    
    # 应用内部别名（与 drg 项目一致）
    internal_aliases = {
        "department_name": "department",
        "attending_doctor": "doctor",
        "actual_cost": "total_cost",
        # 兼容历史字段键，避免前端仍提交旧 key 时误判缺字段
        "dip_payment_amount": "dip_payment",
        "profit_loss_amount": "profit_loss",
    }
    alias_rename = {k: v for k, v in internal_aliases.items() if k in df_mapped.columns}
    if alias_rename:
        df_mapped = df_mapped.rename(columns=alias_rename)
    
    # 去重列
    if df_mapped.columns.duplicated().any():
        df_mapped = df_mapped.loc[:, ~df_mapped.columns.duplicated()]

    # 3. 确认映射前字段校验（避免进入分析阶段后才抛 500）
    # 标准字段到分析内部字段的映射（与内部 alias 规则保持一致）
    standard_to_internal = {
        "department_name": "department",
        "attending_doctor": "doctor",
        "actual_cost": "total_cost",
        "main_diagnosis": "diagnosis_name",
        "main_diagnosis_code": "diagnosis_code",
        "dip_payment": "dip_payment",
        "dip_payment_amount": "dip_payment",
        "profit_loss_amount": "profit_loss",
    }
    # 分析器核心必需字段（仅校验会导致运行失败的字段）
    analyzer_required = ["department", "total_cost", "dip_payment"]
    missing_fields = sorted(
        {
            field
            for field in analyzer_required
            if field not in df_mapped.columns
        }
    )
    # 当前分析器在存在 dip_name 时会使用 dip_weight 做聚合，这里提前校验
    if "dip_name" in df_mapped.columns and "dip_weight" not in df_mapped.columns:
        missing_fields.append("dip_weight")
        missing_fields = sorted(set(missing_fields))

    if missing_fields:
        reverse_internal_map = {v: k for k, v in standard_to_internal.items()}
        display_names = []
        for field in missing_fields:
            std_key = reverse_internal_map.get(field, field)
            field_meta = STANDARD_FIELDS.get(std_key, {})
            display_names.append(field_meta.get("name", field))

        # 标准必填缺失仅提示，不阻断
        recommended_required = []
        for std_key, field_info in STANDARD_FIELDS.items():
            if not bool(field_info.get("required")):
                continue
            internal_key = standard_to_internal.get(std_key, std_key)
            if internal_key not in df_mapped.columns:
                recommended_required.append(std_key)

        detail = {
            "success": False,
            "error": "字段校验失败，请先完成必填字段映射",
            "missing_fields": missing_fields,
            "missing_field_names": display_names,
            "recommended_missing_required": recommended_required,
            "present_fields": list(df_mapped.columns),
        }
        logger.warning("确认映射前字段校验失败: %s", detail)
        raise HTTPException(status_code=400, detail=detail)
    
    # 4. 执行分析
    try:
        analyzer = EnhancedAnalyzer(df_mapped, user_mappings=mappings)
        results = analyzer.run_full_analysis()
    except Exception as e:
        logger.error(f"分析执行失败: {e}")
        raise HTTPException(status_code=500, detail=f"数据分析失败: {str(e)}")
    
    # 5. 生成图表配置
    try:
        all_charts = ChartService.generate_all_charts(results)
    except Exception as e:
        logger.error(f"图表生成失败: {e}")
        all_charts = {}
    
    # 6. 生成 AI 洞察
    ai_insights = []
    overview = results.get("overview", {})
    if overview:
        total_cases = overview.get("total_cases", 0)
        profit_rate = overview.get("profit_rate", 0)
        total_profit = overview.get("total_profit_loss", 0)
        
        if total_cases > 0:
            ai_insights.append(f"本批次共 {total_cases} 例病例，总体盈亏率 {profit_rate}%")
        if total_profit < 0:
            ai_insights.append(f"⚠️ 当前批次整体亏损 {abs(total_profit):,.0f} 元，建议关注高亏损科室")
        
        # 科室分析洞察
        dept_top10 = results.get("department_top10", [])
        if dept_top10:
            loss_depts = [d for d in dept_top10 if d.get("盈亏额", d.get("profit_loss", 0)) < 0]
            if loss_depts:
                dept_names = ", ".join([d.get("department", d.get("科室", "")) for d in loss_depts[:3]])
                ai_insights.append(f"亏损科室: {dept_names}，建议优化费用结构")
    
    # 7. 保存映射配置
    try:
        config_path = os.path.join(file_dir, "mapping_confirmed.json")
        with open(config_path, "w", encoding="utf-8") as f:
            json.dump({
                "mappings": mappings,
                "row_count": len(df_mapped),
                "columns": list(df_mapped.columns),
            }, f, ensure_ascii=False, indent=2)
    except Exception:
        pass
    
    return {
        "success": True,
        "file_id": file_id,
        "row_count": len(df_mapped),
        "analysis_results": results,
        "charts": all_charts,
        "ai_insights": ai_insights,
        "process_log": processor.get_process_log(),
    }


# ============================================================================
# 5. 标准字段定义查询
# ============================================================================

@router.get("/mapping/fields")
async def get_standard_fields_api():
    """获取标准字段定义（供前端展示下拉选项）"""
    return {"fields": STANDARD_FIELDS}
