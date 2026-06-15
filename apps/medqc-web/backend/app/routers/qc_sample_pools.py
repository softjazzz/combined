from __future__ import annotations

import json
import os
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Literal, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, Query, Request, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from ..core.response import get_trace_id, success_response
from ..core.security import get_current_user, require_roles
from ..services.fast_screen_qc import EXECUTION_STRATEGY_FAST_SCREEN, EXECUTION_STRATEGY_STANDARD, get_fast_screen_full_rule_ids
from ..routers.qc_sichuan import _run_sichuan_workspace_batch_job
from ..services.custom_qc_sample_pool_service import (
    CustomQCSamplePoolService,
    load_manual_case_rows_from_excel,
)
from ..services.custom_qc_workspace_service import CustomQCWorkspaceService
from ..services.customer_rule_sets import (
    CUSTOMER_LUXIAN_RULE_SET_KEY,
    get_customer_luxian_rule_set,
)
from ..services.detached_task_runner import submit_detached_task
from ..services.sample_validation_rule_sets import (
    FORMAL_FAST_SCREEN_FULL_MODE,
    FORMAL_FAST_SCREEN_FULL_RULE_SET_KEY,
    get_sample_programmatic_rule_set,
    list_sample_validation_rule_sets,
    resolve_sample_validation_rule_set_by_key,
    resolve_sample_validation_pseudo_draft,
)
from ..services.qc_rule_sets import get_sichuan_rule_set


router = APIRouter(
    prefix="/api/v1/qc/sample-pools",
    tags=["qc-sample-pools"],
    dependencies=[Depends(require_roles("admin", "qc_manager"))],
)

_IMPORT_UPLOAD_DIR = (
    Path(__file__).resolve().parents[2] / "data" / "sample_pool_uploads"
)
_FAST_SCREEN_FULL_RULE_ID_SET = {str(item).strip().upper() for item in get_fast_screen_full_rule_ids() if str(item).strip()}
_SHEET2_EXACT_REVIEW_ACCEPTANCE_JSON = (
    Path(__file__).resolve().parents[3] / "docs" / "0418" / "QC" / "sheet2_exact_review_acceptance_package.json"
)
_LUXIAN_0609_REPORT_DIR = Path(__file__).resolve().parents[3] / "docs" / "0602"
_LUXIAN_0609_REPORT_FILES = {
    "md": ("泸县0609质控点评估报告.md", "text/markdown; charset=utf-8"),
    "csv": ("luxian_0609_qc_eval.csv", "text/csv; charset=utf-8"),
    "json": ("luxian_0609_qc_eval.json", "application/json; charset=utf-8"),
}


def _service() -> CustomQCSamplePoolService:
    return CustomQCSamplePoolService()


def _workspace_service() -> CustomQCWorkspaceService:
    return CustomQCWorkspaceService()


def _current_user_id(current_user: Dict[str, Any]) -> str:
    return (
        str(current_user.get("id") or current_user.get("user_id") or current_user.get("username") or "")
        .strip()
        or "anonymous"
    )


def _resolve_sample_validation_execution_strategy(*, validation_mode: str, rule_ids: list[str]) -> str:
    if str(validation_mode or "").strip().lower() != "sc":
        return EXECUTION_STRATEGY_FAST_SCREEN
    normalized_rule_ids = {
        str(rule_id or "").strip().upper()
        for rule_id in list(rule_ids or [])
        if str(rule_id or "").strip()
    }
    if normalized_rule_ids and normalized_rule_ids.issubset(_FAST_SCREEN_FULL_RULE_ID_SET):
        return EXECUTION_STRATEGY_FAST_SCREEN
    return EXECUTION_STRATEGY_STANDARD


class SamplePoolImportRequest(BaseModel):
    pool_name: str = Field(..., description="样本池名称")
    source_file: str = Field(..., description="Excel 文件路径")
    source_sheet: str = Field(default="Sheet2", description="Sheet 名称")
    description: Optional[str] = Field(default=None, description="备注")
    scene: str = Field(default="running", description="目标场景")


class SamplePoolRunRequest(BaseModel):
    department: Optional[str] = None
    doctor: Optional[str] = None
    model_code: Optional[str] = None
    top_p: Optional[float] = None
    temperature: Optional[float] = None
    max_tokens: Optional[int] = None
    max_parallel_records: Optional[int] = Field(default=None, description="病历级并发数")
    sample_item_ids: list[str] = Field(default_factory=list, description="选中的样本项 ID")
    record_ids: list[str] = Field(default_factory=list, description="选中的真实病历 visit_id")
    validation_mode: str = Field(default="customer", description="验证模式：customer/sc/programmatic/formal_fast_screen_full")
    rule_set_key: Optional[str] = Field(default=None, description="指定规则包 key")


class SamplePoolSyncRequest(BaseModel):
    only_intrinsic: bool = Field(default=True, description="只同步内涵样本")
    include_in_batch_1: bool = Field(default=True, description="只同步首批样本")
    table_groups: list[str] = Field(
        default_factory=list,
        description="同步表分组；为空时使用样本验证服务默认组 sample_full_domain",
    )


class TestRecordBasicInfo(BaseModel):
    patient_name: str = Field(..., description="患者姓名")
    sex: str = Field(default="男", description="性别")
    age: int = Field(default=45, ge=0, le=120, description="年龄")
    mr_no: Optional[str] = Field(default=None, description="住院号")
    department: str = Field(..., description="科室")
    admission_time: datetime = Field(..., description="入院时间")
    discharge_time: Optional[datetime] = Field(default=None, description="出院时间")
    main_diagnosis: Optional[str] = Field(default=None, description="主要诊断")
    other_diagnoses: list[str] = Field(default_factory=list, description="其他诊断")
    doctor_name: Optional[str] = Field(default=None, description="默认记录医师")
    contact_number: Optional[str] = Field(default=None, description="联系电话")
    address: Optional[str] = Field(default=None, description="住址")


class TestRecordDocument(BaseModel):
    document_type: str = Field(..., description="文书类型")
    title: str = Field(..., description="文书标题")
    record_time: Optional[datetime] = Field(default=None, description="记录/报告/医嘱时间")
    submit_time: Optional[datetime] = Field(default=None, description="提交时间")
    content: str = Field(..., description="文书内容")
    doctor_name: Optional[str] = Field(default=None, description="记录医师")
    doctor_code: Optional[str] = Field(default=None, description="医师代码")
    enabled: bool = Field(default=True, description="是否写入")


class TestRecordGoldenAnswer(BaseModel):
    qc_point_id: str = Field(..., description="客户质控点 ID，如 LX0609-001")
    expected_status: Literal["non_compliant", "compliant", "not_applicable", "data_gap", "uncertain"] = Field(
        ..., description="人工预期状态"
    )
    trigger_facts: list[str] = Field(default_factory=list, description="触发事实")
    evidence_keywords: list[str] = Field(default_factory=list, description="证据关键词")
    human_reason: Optional[str] = Field(default=None, description="人工判定理由")


class TestRecordCreateRequest(BaseModel):
    case_title: str = Field(..., description="测试病历名称")
    basic_info: TestRecordBasicInfo
    documents: list[TestRecordDocument] = Field(..., min_length=1, description="文书列表")
    selected_rule_ids: list[str] = Field(default_factory=list, description="重点验证规则")
    manual_issue_text: Optional[str] = Field(default=None, description="样本说明")
    template_key: Optional[str] = Field(default=None, description="使用的测试病历模板 key")
    golden_answers: list[TestRecordGoldenAnswer] = Field(default_factory=list, description="人工预期结果")


def _run_sample_pool_sync_job(job_id: str) -> None:
    service = _service()
    job = service.get_sync_job(job_id=job_id)
    if not job:
        return
    payload = job.get("payload") or {}
    pool_id = str(job.get("pool_id") or "").strip()
    if not pool_id:
        service.fail_sync_job(job_id=job_id, error_message="同步任务缺少样本池标识")
        return

    service.mark_sync_job_running(job_id=job_id)

    def emit_progress(progress: Dict[str, Any]) -> None:
        service.update_sync_job_progress(job_id=job_id, progress=progress)

    try:
        result = service.sync_pool_records(
            pool_id=pool_id,
            only_intrinsic=bool(payload.get("only_intrinsic", True)),
            include_in_batch_1=bool(payload.get("include_in_batch_1", True)),
            table_groups=payload.get("table_groups") or None,
            progress_callback=emit_progress,
        )
        service.finish_sync_job(job_id=job_id, summary=result)
    except Exception as exc:
        service.fail_sync_job(job_id=job_id, error_message=str(exc))


@router.get("")
async def list_sample_pools(
    request: Request,
    q: Optional[str] = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    result = _service().list_pools(page=page, page_size=page_size, query=q)
    return success_response(
        data={
            "items": result.items,
            "total": result.total,
            "page": result.page,
            "page_size": result.page_size,
        },
        message="获取客户样本池成功",
        trace_id=get_trace_id(request),
    )


@router.post("/test-records")
async def create_test_record(
    request: Request,
    payload: TestRecordCreateRequest,
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    try:
        result = _service().create_customer_test_record(
            payload=payload.model_dump(mode="json"),
            created_by=_current_user_id(current_user),
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return success_response(
        data=result,
        message="客户自建测试病历已创建",
        trace_id=get_trace_id(request),
    )


@router.post("/import-manual-sheet")
async def import_manual_sheet(
    request: Request,
    payload: SamplePoolImportRequest,
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    file_path = os.path.abspath(payload.source_file)
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail=f"文件不存在: {file_path}")
    rows = load_manual_case_rows_from_excel(file_path=file_path, sheet_name=payload.source_sheet)
    if not rows:
        raise HTTPException(status_code=422, detail="Sheet 中未读取到有效样本行")
    pool = _service().create_pool_with_items(
        name=payload.pool_name,
        source_file=file_path,
        source_sheet=payload.source_sheet,
        created_by=_current_user_id(current_user),
        rows=rows,
        description=payload.description,
        scene=payload.scene,
    )
    return success_response(
        data={**pool, "imported_rows": len(rows)},
        message="客户样本池导入成功",
        trace_id=get_trace_id(request),
    )


@router.post("/import-upload")
async def import_manual_sheet_upload(
    request: Request,
    pool_name: str = Form(..., description="样本池名称"),
    source_sheet: str = Form(default="", description="Sheet 名称；为空时自动读取第一个工作表"),
    description: Optional[str] = Form(default=None, description="备注"),
    scene: str = Form(default="running", description="目标场景"),
    file: UploadFile = File(..., description="Excel 模板文件"),
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    filename = str(file.filename or "").strip()
    suffix = Path(filename).suffix.lower()
    if suffix not in {".xls", ".xlsx"}:
        raise HTTPException(status_code=422, detail="仅支持导入 .xls 或 .xlsx 模板文件")

    _IMPORT_UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    safe_stem = "".join(ch if ch.isalnum() or ch in ("-", "_") else "_" for ch in Path(filename).stem).strip("_")
    safe_stem = safe_stem or "manual_case_pool"
    saved_path = _IMPORT_UPLOAD_DIR / f"{safe_stem}-{uuid.uuid4().hex[:8]}{suffix}"

    content = await file.read()
    if not content:
        raise HTTPException(status_code=422, detail="上传文件为空")
    saved_path.write_bytes(content)

    rows = load_manual_case_rows_from_excel(file_path=str(saved_path), sheet_name=source_sheet)
    if not rows:
        raise HTTPException(status_code=422, detail="模板中未读取到有效样本行，请检查 Sheet 与表头格式")

    pool = _service().create_pool_with_items(
        name=str(pool_name).strip(),
        source_file=str(saved_path),
        source_sheet=str(source_sheet).strip() or "自动识别",
        created_by=_current_user_id(current_user),
        rows=rows,
        description=(description or "").strip() or None,
        scene=str(scene).strip() or "running",
    )
    return success_response(
        data={**pool, "imported_rows": len(rows)},
        message="客户样本模板导入成功",
        trace_id=get_trace_id(request),
    )


@router.get("/sheet2-exact-review/acceptance-package")
async def get_sheet2_exact_review_acceptance_package(
    request: Request,
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    if not _SHEET2_EXACT_REVIEW_ACCEPTANCE_JSON.exists():
        raise HTTPException(status_code=404, detail="Sheet2 精确复核验收包尚未生成")
    payload = json.loads(_SHEET2_EXACT_REVIEW_ACCEPTANCE_JSON.read_text(encoding="utf-8"))
    return success_response(
        data=payload,
        message="获取 Sheet2 精确复核验收包成功",
        trace_id=get_trace_id(request),
    )


@router.get("/rule-sets")
async def list_sample_validation_rule_set_catalog(
    request: Request,
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    return success_response(
        data={"items": list_sample_validation_rule_sets()},
        message="获取客户样本验证规则集成功",
        trace_id=get_trace_id(request),
    )


@router.get("/reports/luxian-0609")
async def download_luxian_0609_evaluation_report(
    request: Request,
    format: str = Query(default="md", description="导出格式：md/csv/json"),
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    normalized_format = str(format or "md").strip().lower()
    if normalized_format not in _LUXIAN_0609_REPORT_FILES:
        raise HTTPException(status_code=422, detail="仅支持导出 md、csv 或 json 格式")
    filename, media_type = _LUXIAN_0609_REPORT_FILES[normalized_format]
    file_path = _LUXIAN_0609_REPORT_DIR / filename
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="泸县0609质控点评估报告尚未生成")
    return FileResponse(
        path=str(file_path),
        media_type=media_type,
        filename=filename,
    )


@router.get("/{pool_id}")
async def get_sample_pool(
    request: Request,
    pool_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    pool = _service().get_pool(pool_id=pool_id)
    if not pool:
        raise HTTPException(status_code=404, detail="样本池不存在")
    return success_response(
        data=pool,
        message="获取客户样本池成功",
        trace_id=get_trace_id(request),
    )


@router.get("/{pool_id}/items")
async def list_sample_pool_items(
    request: Request,
    pool_id: str,
    coverage_type: Optional[str] = Query(default=None),
    match_status: Optional[str] = Query(default=None),
    include_in_batch_1: Optional[bool] = Query(default=None),
    q: Optional[str] = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=200),
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    pool = _service().get_pool(pool_id=pool_id)
    if not pool:
        raise HTTPException(status_code=404, detail="样本池不存在")
    result = _service().list_pool_items(
        pool_id=pool_id,
        coverage_type=coverage_type,
        match_status=match_status,
        include_in_batch_1=include_in_batch_1,
        query=q,
        page=page,
        page_size=page_size,
    )
    return success_response(
        data={
            "pool": pool,
            "items": result.items,
            "total": result.total,
            "page": result.page,
            "page_size": result.page_size,
        },
        message="获取客户样本明细成功",
        trace_id=get_trace_id(request),
    )


@router.get("/{pool_id}/records")
async def list_sample_pool_records(
    request: Request,
    pool_id: str,
    coverage_type: Optional[str] = Query(default=None),
    match_status: Optional[str] = Query(default=None),
    include_in_batch_1: Optional[bool] = Query(default=None),
    q: Optional[str] = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=200),
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    pool = _service().get_pool(pool_id=pool_id)
    if not pool:
        raise HTTPException(status_code=404, detail="样本池不存在")
    result = _service().list_pool_records(
        pool_id=pool_id,
        coverage_type=coverage_type,
        match_status=match_status,
        include_in_batch_1=include_in_batch_1,
        query=q,
        page=page,
        page_size=page_size,
    )
    return success_response(
        data={
            "pool": pool,
            "items": result.items,
            "total": result.total,
            "page": result.page,
            "page_size": result.page_size,
        },
        message="获取客户样本病历列表成功",
        trace_id=get_trace_id(request),
    )


@router.post("/{pool_id}/match")
async def match_sample_pool(
    request: Request,
    pool_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    pool = _service().get_pool(pool_id=pool_id)
    if not pool:
        raise HTTPException(status_code=404, detail="样本池不存在")
    result = _service().match_pool_items(pool_id=pool_id)
    return success_response(
        data=result,
        message="客户样本病历匹配完成",
        trace_id=get_trace_id(request),
    )


@router.post("/{pool_id}/sync-records")
async def sync_sample_pool_records(
    request: Request,
    pool_id: str,
    payload: SamplePoolSyncRequest,
    background_tasks: BackgroundTasks,
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    pool = _service().get_pool(pool_id=pool_id)
    if not pool:
        raise HTTPException(status_code=404, detail="样本池不存在")
    try:
        job = _service().create_sync_job(
            pool_id=pool_id,
            created_by=_current_user_id(current_user),
            payload=payload.model_dump(exclude_unset=True),
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    background_tasks.add_task(_run_sample_pool_sync_job, job["id"])
    return success_response(
        data={
            "job_id": job["id"],
            "pool_id": pool_id,
            "status": job["status"],
            "summary": job["summary"],
        },
        message="样本病历定向同步任务已创建",
        trace_id=get_trace_id(request),
    )


@router.get("/{pool_id}/sync-jobs/latest")
async def get_latest_sample_pool_sync_job(
    request: Request,
    pool_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    pool = _service().get_pool(pool_id=pool_id)
    if not pool:
        raise HTTPException(status_code=404, detail="样本池不存在")
    job = _service().get_latest_sync_job(pool_id=pool_id)
    return success_response(
        data=job,
        message="获取样本同步任务成功",
        trace_id=get_trace_id(request),
    )


@router.get("/sync-jobs/{job_id}")
async def get_sample_pool_sync_job(
    request: Request,
    job_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    job = _service().get_sync_job(job_id=job_id)
    if not job:
        raise HTTPException(status_code=404, detail="同步任务不存在")
    return success_response(
        data=job,
        message="获取样本同步任务成功",
        trace_id=get_trace_id(request),
    )


@router.post("/{pool_id}/run")
async def run_sample_pool_intrinsic_validation(
    request: Request,
    pool_id: str,
    payload: SamplePoolRunRequest,
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    service = _service()
    pool = service.get_pool(pool_id=pool_id)
    if not pool:
        raise HTTPException(status_code=404, detail="样本池不存在")

    requested_rule_set_key = str(payload.rule_set_key or "").strip()
    resolved_rule_set = None
    validation_mode = str(payload.validation_mode or "customer").strip().lower() or "customer"
    if requested_rule_set_key:
        try:
            resolved = resolve_sample_validation_rule_set_by_key(requested_rule_set_key)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        validation_mode = str(resolved["validation_mode"])
        resolved_rule_set = resolved["rule_set"]
    if validation_mode not in {"customer", "sc", "programmatic", FORMAL_FAST_SCREEN_FULL_MODE}:
        raise HTTPException(status_code=422, detail="未知验证模式，仅支持 customer、sc、programmatic 或 formal_fast_screen_full")
    is_formal_fast_screen_full = validation_mode == FORMAL_FAST_SCREEN_FULL_MODE
    requested_record_ids = [
        str(record_id or "").strip()
        for record_id in list(payload.record_ids or [])
        if str(record_id or "").strip()
    ]
    if is_formal_fast_screen_full and not requested_record_ids:
        raise HTTPException(status_code=422, detail="正式84条质控请先选择病历")

    runnable_items = service.get_runnable_items(
        pool_id=pool_id,
        validation_mode=validation_mode,
        item_ids=payload.sample_item_ids,
        record_ids=requested_record_ids,
    )
    if not runnable_items:
        if payload.record_ids:
            raise HTTPException(status_code=422, detail="当前选中病历没有可执行的样本问题")
        if payload.sample_item_ids:
            raise HTTPException(status_code=422, detail="当前选中样本没有可执行的病历")
        raise HTTPException(status_code=422, detail="当前样本池没有可执行的样本病历")

    record_ids = sorted(
        {
            str(item.get("matched_visit_id") or "").strip()
            for item in runnable_items
            if str(item.get("matched_visit_id") or "").strip()
        }
    )
    record_rule_map: Dict[str, list[str]] = {}
    if not is_formal_fast_screen_full and resolved_rule_set is None:
        for item in runnable_items:
            record_id = str(item.get("matched_visit_id") or "").strip()
            if not record_id:
                continue
            bucket = record_rule_map.setdefault(record_id, [])
            for rule_id in list(item.get("candidate_rule_ids") or []):
                normalized_rule_id = str(rule_id or "").strip()
                if normalized_rule_id and normalized_rule_id not in bucket:
                    bucket.append(normalized_rule_id)
    if not record_ids:
        raise HTTPException(status_code=422, detail="当前样本池没有已匹配的病历")

    if resolved_rule_set is not None:
        rule_ids = [str(rule_id).strip() for rule_id in resolved_rule_set.rule_ids if str(rule_id).strip()]
        rule_set_key = resolved_rule_set.key
        rule_set_name = resolved_rule_set.name
        rule_set_version = resolved_rule_set.version
    elif validation_mode == "customer":
        effective_rule_set_key = requested_rule_set_key or CUSTOMER_LUXIAN_RULE_SET_KEY
        if effective_rule_set_key == CUSTOMER_LUXIAN_RULE_SET_KEY:
            customer_rule_set = get_customer_luxian_rule_set()
        else:
            raise HTTPException(status_code=422, detail=f"未知客户规则包: {effective_rule_set_key}")
        rule_ids = sorted({str(rule_id).strip() for rule_id in customer_rule_set.rule_ids if str(rule_id).strip()})
        rule_set_key = customer_rule_set.key
        rule_set_name = customer_rule_set.name
        rule_set_version = customer_rule_set.version
    elif validation_mode == "sc":
        rule_ids = sorted(
            {
                str(rule_id).strip()
                for item in runnable_items
                for rule_id in (item.get("candidate_rule_ids") or [])
                if str(rule_id).strip()
            }
        )
        rule_set_key = ""
        rule_set_name = "SC样本规则模式"
        rule_set_version = "running-batch-1"
    elif validation_mode == "programmatic":
        programmatic_rule_set = get_sample_programmatic_rule_set()
        rule_ids = list(programmatic_rule_set.rule_ids)
        rule_set_key = programmatic_rule_set.key
        rule_set_name = programmatic_rule_set.name
        rule_set_version = programmatic_rule_set.version
    else:
        requested_rule_set_key = requested_rule_set_key or FORMAL_FAST_SCREEN_FULL_RULE_SET_KEY
        if requested_rule_set_key != FORMAL_FAST_SCREEN_FULL_RULE_SET_KEY:
            raise HTTPException(status_code=422, detail=f"正式质控 84 条仅支持规则集: {FORMAL_FAST_SCREEN_FULL_RULE_SET_KEY}")
        formal_rule_set = get_sichuan_rule_set(FORMAL_FAST_SCREEN_FULL_RULE_SET_KEY)
        if not formal_rule_set:
            raise HTTPException(status_code=422, detail=f"未知规则集: {FORMAL_FAST_SCREEN_FULL_RULE_SET_KEY}")
        rule_ids = [str(rule_id).strip() for rule_id in formal_rule_set.rule_ids if str(rule_id).strip()]
        rule_set_key = formal_rule_set.key
        rule_set_name = formal_rule_set.name
        rule_set_version = formal_rule_set.version

    if not rule_ids:
        raise HTTPException(status_code=422, detail="当前样本池没有可执行规则")
    execution_strategy = (
        EXECUTION_STRATEGY_FAST_SCREEN
        if is_formal_fast_screen_full
        else _resolve_sample_validation_execution_strategy(
            validation_mode=validation_mode,
            rule_ids=rule_ids,
        )
    )

    workspace = _workspace_service()
    requested_scope = "final" if is_formal_fast_screen_full else str(pool.get("scene") or "running").strip().lower() or "running"
    effective_scope = requested_scope
    record_count = workspace.count_records(
        scope=effective_scope,
        department=payload.department,
        doctor=payload.doctor,
        date_field="admission",
        start_date=None,
        end_date=None,
        keyword=None,
        record_ids=record_ids,
    )
    if record_count == 0 and is_formal_fast_screen_full:
        raise HTTPException(status_code=422, detail="选中病历未同步为终末病历，无法发起正式终末质控")
    if record_ids and effective_scope != "all" and record_count < len(record_ids):
        fallback_record_count = workspace.count_records(
            scope="all",
            department=payload.department,
            doctor=payload.doctor,
            date_field="admission",
            start_date=None,
            end_date=None,
            keyword=None,
            record_ids=record_ids,
        )
        if fallback_record_count > record_count:
            record_count = fallback_record_count
            effective_scope = "all"
    if record_count == 0:
        raise HTTPException(status_code=422, detail="样本池匹配病历未同步到当前 PG，无法执行")

    pseudo_draft = resolve_sample_validation_pseudo_draft(
        validation_mode=validation_mode,
        pool_name=str(pool.get("name") or ""),
        rule_count=len(rule_ids),
        rule_set_key=rule_set_key,
        rule_set_name=rule_set_name,
    )
    job_filters = {
        "rule_ids": rule_ids,
        "rule_set_key": rule_set_key,
        "rule_set_name": rule_set_name,
        "rule_set_version": rule_set_version,
        "rule_count": len(rule_ids),
        "execution_strategy": execution_strategy,
        "quality_profile": "throughput_v1",
        "bucket_strategy": "fixed_packs",
        "batch_output_mode": "minimal",
        "enable_selective_refine": False,
        "refine_confidence_threshold": 0.0,
        "max_refine_candidates": 0,
        "source": "manual_sample_formal_fast_screen_full" if is_formal_fast_screen_full else "manual_problem_sample_pool",
        "sample_pool_id": pool_id,
        "selected_record_ids": requested_record_ids,
        "selected_sample_item_ids": [str(item.get("id") or "").strip() for item in runnable_items if str(item.get("id") or "").strip()],
        "selected_sample_count": len(runnable_items),
        "dedup_record_count": len(record_ids),
        "department": payload.department,
        "doctor": payload.doctor,
        "temperature": payload.temperature,
        "top_p": payload.top_p,
        "max_tokens": payload.max_tokens,
        "model_code": payload.model_code,
        "max_parallel_records": payload.max_parallel_records,
        "effective_scope": effective_scope,
        "validation_mode": validation_mode,
    }
    if record_rule_map:
        job_filters["record_rule_map"] = record_rule_map

    job = workspace.create_batch_job(
        draft=pseudo_draft,
        created_by=_current_user_id(current_user),
        scope=effective_scope,
        filters=job_filters,
        record_ids=record_ids,
        total_records=record_count,
        draft_ids=rule_ids,
        execution_mode="multi",
        run_mode="parallel",
        rule_count=len(rule_ids),
    )
    service.update_pool_latest_job(pool_id=pool_id, job_id=job["id"], job_status="queued")
    submit_detached_task(
        "sample_pool_sichuan_workspace_batch_job",
        _run_sichuan_workspace_batch_job,
        job["id"],
    )
    return success_response(
        data={
            "pool_id": pool_id,
            "job_id": job["id"],
            "sample_item_count": len(runnable_items),
            "selected_record_count": len(requested_record_ids),
            "record_count": record_count,
            "rule_count": len(rule_ids),
            "record_ids": record_ids,
            "rule_ids": rule_ids,
            "validation_mode": validation_mode,
            "rule_set_key": rule_set_key,
            "rule_set_name": rule_set_name,
            "rule_set_version": rule_set_version,
        },
        message="正式质控任务已创建" if is_formal_fast_screen_full else "客户样本验证任务已创建",
        trace_id=get_trace_id(request),
    )
