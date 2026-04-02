import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, Query, Request
from fastapi import HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from ..core.response import get_trace_id, success_response
from ..core.security import get_current_user, require_roles
from ..services.custom_qc_service import (
    create_custom_qc_service,
    ensure_record_medical_text,
    evaluate_inline_rule,
    generate_custom_prompt,
)
from ..services.custom_qc_workspace_service import CustomQCWorkspaceService
from ..services.sichuan_qc_service import SichuanQCService

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/v1/custom-qc",
    tags=["custom-qc"],
    dependencies=[Depends(require_roles("admin", "qc_manager"))],
)


async def get_custom_qc_service() -> SichuanQCService:
    return await create_custom_qc_service()


def get_workspace_service() -> CustomQCWorkspaceService:
    return CustomQCWorkspaceService()


def _current_user_id(current_user: Dict[str, Any]) -> str:
    return (
        str(current_user.get("id") or current_user.get("user_id") or current_user.get("username") or "")
        .strip()
        or "anonymous"
    )


class PromptGenerateRequest(BaseModel):
    scene: str = Field(..., description="场景 running|final")
    document_type: str = Field(..., description="文书类型")
    rule_name: str = Field(..., description="质控点名称")
    description: str = Field(..., description="质控点描述")
    severity: str = Field(..., description="严重程度 critical|major|minor")


class DraftRulePayload(BaseModel):
    name: str
    description: str
    prompt_template: str
    severity: str = "major"
    document_type: str = "病程记录"
    scene: Optional[str] = None
    check_logic: Dict[str, Any] = Field(default_factory=dict)


class DraftRecordPayload(BaseModel):
    visit_id: Optional[str] = None
    record_id: str
    patient_name: Optional[str] = None
    department: Optional[str] = None
    medical_text: str


class CustomQCTestRequest(BaseModel):
    rule: DraftRulePayload
    records: List[DraftRecordPayload]
    temperature: Optional[float] = None
    top_p: Optional[float] = None
    max_tokens: Optional[int] = None


class WorkspaceDraftCreateRequest(BaseModel):
    name: str
    description: str
    source_requirement: Optional[str] = None
    prompt_template: str = ""
    document_type: str = "病程记录"
    severity: str = "major"
    defect_level: Optional[str] = None
    complexity: str = "中复杂度"
    scene: str = "running"
    generation_mode: str = "fallback_template"
    applicable_documents: List[str] = Field(default_factory=list)
    examples: List[Dict[str, Any]] = Field(default_factory=list)
    check_logic: Dict[str, Any] = Field(default_factory=dict)


class WorkspaceDraftUpdateRequest(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    source_requirement: Optional[str] = None
    prompt_template: Optional[str] = None
    document_type: Optional[str] = None
    severity: Optional[str] = None
    defect_level: Optional[str] = None
    complexity: Optional[str] = None
    scene: Optional[str] = None
    generation_mode: Optional[str] = None
    applicable_documents: Optional[List[str]] = None
    examples: Optional[List[Dict[str, Any]]] = None
    check_logic: Optional[Dict[str, Any]] = None
    last_test_summary: Optional[Dict[str, Any]] = None
    status: Optional[str] = None
    published_rule_id: Optional[str] = None


class WorkspaceRecordPayload(BaseModel):
    record_id: str
    visit_id: Optional[str] = None
    patient_name: Optional[str] = None
    department: Optional[str] = None
    doctor: Optional[str] = None
    medical_text: Optional[str] = None


class WorkspaceTestRequest(BaseModel):
    draft_id: str
    records: List[WorkspaceRecordPayload]
    temperature: Optional[float] = None
    top_p: Optional[float] = None
    max_tokens: Optional[int] = None


class WorkspaceBatchJobCreateRequest(BaseModel):
    draft_id: str
    scope: str = "final"
    department: Optional[str] = None
    doctor: Optional[str] = None
    date_field: str = "discharge"
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    keyword: Optional[str] = None
    record_ids: List[str] = Field(default_factory=list)
    temperature: Optional[float] = None
    top_p: Optional[float] = None
    max_tokens: Optional[int] = None


def _batch_job_payload_filters(payload: WorkspaceBatchJobCreateRequest) -> Dict[str, Any]:
    return {
        "department": payload.department,
        "doctor": payload.doctor,
        "date_field": payload.date_field,
        "start_date": payload.start_date,
        "end_date": payload.end_date,
        "keyword": payload.keyword,
        "temperature": payload.temperature,
        "top_p": payload.top_p,
        "max_tokens": payload.max_tokens,
    }


async def _run_workspace_batch_job(job_id: str) -> None:
    workspace = get_workspace_service()
    job = workspace.get_batch_job_for_processing(job_id=job_id)
    if not job:
        return

    try:
        workspace.mark_batch_job_running(job_id=job_id)
        draft = workspace.get_draft(draft_id=job["draft_id"], created_by=job["created_by"])
        if not draft:
            raise ValueError("规则草稿不存在或无权限")

        filters = job.get("filters") or {}
        records = workspace.collect_records(
            scope=job.get("scope") or "final",
            department=filters.get("department"),
            doctor=filters.get("doctor"),
            date_field=filters.get("date_field") or "discharge",
            start_date=filters.get("start_date"),
            end_date=filters.get("end_date"),
            keyword=filters.get("keyword"),
            record_ids=job.get("record_ids") or None,
        )
        hydrated_records = workspace.hydrate_records_with_medical_text(records)
        rule_payload = _workspace_rule_payload_from_draft(draft)
        qc_service = await create_custom_qc_service()

        items: List[Dict[str, Any]] = []
        failed_records: List[Dict[str, Any]] = []
        total_tokens = 0
        total_processing_time = 0.0

        for record in hydrated_records:
            try:
                ensure_record_medical_text([record])
                result = await evaluate_inline_rule(
                    qc_service=qc_service,
                    rule=rule_payload,
                    record=record,
                    temperature=filters.get("temperature"),
                    top_p=filters.get("top_p"),
                    max_tokens=filters.get("max_tokens"),
                )
                total_tokens += int((result.get("performance") or {}).get("token_usage") or 0)
                total_processing_time += float((result.get("performance") or {}).get("processing_time") or 0.0)
                items.append(result)
            except Exception as exc:
                logger.warning("workspace batch job record failed: %s", exc)
                failed_records.append(
                    {
                        "record_id": str(record.get("record_id") or ""),
                        "visit_id": str(record.get("visit_id") or ""),
                        "patient_name": str(record.get("patient_name") or ""),
                        "department": str(record.get("department") or ""),
                        "error": str(exc),
                    }
                )

        summary = {
            "total_records": len(hydrated_records),
            "success_count": len(items),
            "failed_count": len(failed_records),
            "issue_records": sum(1 for item in items if item.get("status") == "non_compliant"),
            "compliant_records": sum(1 for item in items if item.get("status") in {"compliant", "not_applicable"}),
            "total_tokens": total_tokens,
            "total_processing_time": total_processing_time,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        workspace.complete_batch_job(
            job_id=job_id,
            summary=summary,
            items=items,
            failed_records=failed_records,
        )
        workspace.save_last_test_summary(
            draft_id=job["draft_id"],
            created_by=job["created_by"],
            summary=summary,
        )
    except Exception as exc:
        logger.exception("workspace batch job failed: %s", exc)
        workspace.fail_batch_job(job_id=job_id, error_message=str(exc))


@router.post("/prompt/generate")
async def generate_prompt(request: Request, payload: PromptGenerateRequest):
    result = await generate_custom_prompt(
        scene=payload.scene,
        document_type=payload.document_type,
        rule_name=payload.rule_name,
        description=payload.description,
        severity=payload.severity,
    )
    return success_response(
        data=result,
        message="生成自定义质控 Prompt 成功",
        trace_id=get_trace_id(request),
    )


@router.post("/test")
async def test_custom_qc_single(
    request: Request,
    payload: CustomQCTestRequest,
    qc_service: SichuanQCService = Depends(get_custom_qc_service),
):
    if not payload.records:
        raise HTTPException(status_code=422, detail="至少需要提供一条病历")
    ensure_record_medical_text([record.model_dump() for record in payload.records])
    record = payload.records[0]
    result = await evaluate_inline_rule(
        qc_service=qc_service,
        rule=payload.rule.model_dump(),
        record=record.model_dump(),
        temperature=payload.temperature,
        top_p=payload.top_p,
        max_tokens=payload.max_tokens,
    )

    response = {
        "rule": payload.rule.model_dump(),
        "record": {
            "record_id": record.record_id,
            "visit_id": record.visit_id,
            "patient_name": record.patient_name,
            "department": record.department,
        },
        "result": result,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "status": "success",
    }
    return success_response(
        data=response,
        message="单病历测试完成",
        trace_id=get_trace_id(request),
    )


@router.post("/test/batch")
async def test_custom_qc_batch(
    request: Request,
    payload: CustomQCTestRequest,
    qc_service: SichuanQCService = Depends(get_custom_qc_service),
):
    if not payload.records:
        raise HTTPException(status_code=422, detail="至少需要提供一条病历")
    record_dicts = [record.model_dump() for record in payload.records]
    ensure_record_medical_text(record_dicts)

    items: List[Dict[str, Any]] = []
    failed_records: List[Dict[str, Any]] = []
    total_tokens = 0
    total_processing_time = 0.0

    for record in record_dicts:
        try:
            result = await evaluate_inline_rule(
                qc_service=qc_service,
                rule=payload.rule.model_dump(),
                record=record,
                temperature=payload.temperature,
                top_p=payload.top_p,
                max_tokens=payload.max_tokens,
            )
            total_tokens += int((result.get("performance") or {}).get("token_usage") or 0)
            total_processing_time += float(
                (result.get("performance") or {}).get("processing_time") or 0.0
            )
            items.append(result)
        except Exception as exc:
            logger.warning("custom-qc 批量测试单条病历失败: %s", exc)
            failed_item = {
                "record_id": str(record.get("record_id") or ""),
                "visit_id": str(record.get("visit_id") or ""),
                "patient_name": str(record.get("patient_name") or ""),
                "department": str(record.get("department") or ""),
                "error": str(exc),
            }
            failed_records.append(failed_item)

    summary = {
        "total_records": len(record_dicts),
        "success_count": len(items),
        "failed_count": len(failed_records),
        "issue_records": sum(1 for item in items if item.get("status") == "non_compliant"),
        "compliant_records": sum(
            1 for item in items if item.get("status") in {"compliant", "not_applicable"}
        ),
        "total_tokens": total_tokens,
        "total_processing_time": total_processing_time,
    }

    response = {
        "rule": payload.rule.model_dump(),
        "summary": summary,
        "items": items,
        "failed_records": failed_records,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "status": "success",
    }
    return success_response(
        data=response,
        message="批量病历测试完成",
        trace_id=get_trace_id(request),
    )


@router.get("/workspace/drafts")
async def list_workspace_drafts(
    request: Request,
    status: Optional[str] = Query(None, description="draft|published"),
    q: Optional[str] = Query(None, description="关键字"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
    current_user: Dict[str, Any] = Depends(get_current_user),
    workspace: CustomQCWorkspaceService = Depends(get_workspace_service),
):
    result = workspace.list_drafts(
        created_by=_current_user_id(current_user),
        status=status,
        query=q,
        page=page,
        page_size=page_size,
    )
    return success_response(
        data={
            "items": result.items,
            "total": result.total,
            "page": result.page,
            "page_size": result.page_size,
        },
        message="获取草稿列表成功",
        trace_id=get_trace_id(request),
    )


@router.post("/workspace/drafts")
async def create_workspace_draft(
    request: Request,
    payload: WorkspaceDraftCreateRequest,
    current_user: Dict[str, Any] = Depends(get_current_user),
    workspace: CustomQCWorkspaceService = Depends(get_workspace_service),
):
    draft = workspace.create_draft(
        created_by=_current_user_id(current_user),
        payload=payload.model_dump(),
    )
    return success_response(
        data=draft,
        message="创建草稿成功",
        trace_id=get_trace_id(request),
    )


@router.put("/workspace/drafts/{draft_id}")
async def update_workspace_draft(
    request: Request,
    draft_id: str,
    payload: WorkspaceDraftUpdateRequest,
    current_user: Dict[str, Any] = Depends(get_current_user),
    workspace: CustomQCWorkspaceService = Depends(get_workspace_service),
):
    updated = workspace.update_draft(
        draft_id=draft_id,
        created_by=_current_user_id(current_user),
        payload={k: v for k, v in payload.model_dump().items() if v is not None},
    )
    if not updated:
        raise HTTPException(status_code=404, detail="草稿不存在或无权限")
    return success_response(
        data=updated,
        message="更新草稿成功",
        trace_id=get_trace_id(request),
    )


@router.delete("/workspace/drafts/{draft_id}")
async def delete_workspace_draft(
    request: Request,
    draft_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user),
    workspace: CustomQCWorkspaceService = Depends(get_workspace_service),
):
    ok = workspace.delete_draft(
        draft_id=draft_id,
        created_by=_current_user_id(current_user),
    )
    if not ok:
        raise HTTPException(status_code=404, detail="草稿不存在或无权限")
    return success_response(
        data={"id": draft_id},
        message="删除草稿成功",
        trace_id=get_trace_id(request),
    )


@router.post("/workspace/drafts/{draft_id}/generate-prompt")
async def generate_workspace_draft_prompt(
    request: Request,
    draft_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user),
    workspace: CustomQCWorkspaceService = Depends(get_workspace_service),
):
    draft = workspace.get_draft(draft_id=draft_id, created_by=_current_user_id(current_user))
    if not draft:
        raise HTTPException(status_code=404, detail="草稿不存在或无权限")

    prompt_result = await generate_custom_prompt(
        scene=str(draft.get("scene") or "running"),
        document_type=str(draft.get("document_type") or "病程记录"),
        rule_name=str(draft.get("name") or "未命名规则"),
        description=str(draft.get("description") or ""),
        severity=str(draft.get("severity") or "major"),
    )
    check_logic = dict(draft.get("check_logic") or {})
    check_logic["generated_check_points"] = prompt_result.get("check_points") or []
    check_logic["examples"] = prompt_result.get("examples") or []
    check_logic["generation_mode"] = prompt_result.get("generation_mode") or "fallback_template"
    check_logic["last_prompt_summary"] = prompt_result.get("summary") or ""

    updated = workspace.update_draft(
        draft_id=draft_id,
        created_by=_current_user_id(current_user),
        payload={
            "prompt_template": prompt_result.get("prompt_template") or "",
            "generation_mode": prompt_result.get("generation_mode") or "fallback_template",
            "examples": prompt_result.get("examples") or [],
            "check_logic": check_logic,
        },
    )
    return success_response(
        data={
            "draft": updated,
            "prompt_result": prompt_result,
        },
        message="生成 Prompt 成功",
        trace_id=get_trace_id(request),
    )


@router.post("/workspace/drafts/{draft_id}/publish")
async def publish_workspace_draft(
    request: Request,
    draft_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user),
    workspace: CustomQCWorkspaceService = Depends(get_workspace_service),
):
    try:
        result = workspace.publish_draft(
            draft_id=draft_id,
            created_by=_current_user_id(current_user),
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return success_response(
        data=result,
        message="发布规则成功",
        trace_id=get_trace_id(request),
    )


@router.get("/workspace/records")
async def list_workspace_records(
    request: Request,
    scope: str = Query("all", description="all|running|final"),
    department: Optional[str] = Query(None),
    doctor: Optional[str] = Query(None),
    date_field: str = Query("admission", description="admission|discharge"),
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    keyword: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
    workspace: CustomQCWorkspaceService = Depends(get_workspace_service),
):
    result = workspace.list_records(
        scope=scope,
        department=department,
        doctor=doctor,
        date_field=date_field,
        start_date=start_date,
        end_date=end_date,
        keyword=keyword,
        page=page,
        page_size=page_size,
    )
    return success_response(
        data={
            "items": result.items,
            "total": result.total,
            "page": result.page,
            "page_size": result.page_size,
        },
        message="获取病历列表成功",
        trace_id=get_trace_id(request),
    )


@router.get("/workspace/filters")
async def get_workspace_filters(
    request: Request,
    scope: str = Query("all", description="all|running|final"),
    department: Optional[str] = Query(None),
    workspace: CustomQCWorkspaceService = Depends(get_workspace_service),
):
    result = workspace.get_record_filters(scope=scope, department=department)
    return success_response(
        data=result,
        message="获取筛选项成功",
        trace_id=get_trace_id(request),
    )


def _workspace_rule_payload_from_draft(draft: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "name": str(draft.get("name") or ""),
        "description": str(draft.get("description") or ""),
        "prompt_template": str(draft.get("prompt_template") or ""),
        "severity": str(draft.get("severity") or "major"),
        "document_type": str(draft.get("document_type") or "病程记录"),
        "scene": str(draft.get("scene") or "running"),
        "check_logic": dict(draft.get("check_logic") or {}),
    }


@router.post("/workspace/test")
async def test_workspace_single(
    request: Request,
    payload: WorkspaceTestRequest,
    qc_service: SichuanQCService = Depends(get_custom_qc_service),
    current_user: Dict[str, Any] = Depends(get_current_user),
    workspace: CustomQCWorkspaceService = Depends(get_workspace_service),
):
    if not payload.records:
        raise HTTPException(status_code=422, detail="至少需要提供一条病历")

    draft = workspace.get_draft(draft_id=payload.draft_id, created_by=_current_user_id(current_user))
    if not draft:
        raise HTTPException(status_code=404, detail="草稿不存在或无权限")

    hydrated = workspace.hydrate_records_with_medical_text([record.model_dump() for record in payload.records[:1]])
    ensure_record_medical_text(hydrated)
    target_record = hydrated[0]
    rule_payload = _workspace_rule_payload_from_draft(draft)
    result = await evaluate_inline_rule(
        qc_service=qc_service,
        rule=rule_payload,
        record=target_record,
        temperature=payload.temperature,
        top_p=payload.top_p,
        max_tokens=payload.max_tokens,
    )
    summary = {
        "total_records": 1,
        "success_count": 1,
        "failed_count": 0,
        "issue_records": 0 if result.get("is_compliant") else 1,
        "compliant_records": 1 if result.get("is_compliant") else 0,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    workspace.save_last_test_summary(
        draft_id=payload.draft_id,
        created_by=_current_user_id(current_user),
        summary=summary,
    )

    response = {
        "draft_id": payload.draft_id,
        "rule": rule_payload,
        "record": {
            "record_id": target_record.get("record_id"),
            "visit_id": target_record.get("visit_id"),
            "patient_name": target_record.get("patient_name"),
            "department": target_record.get("department"),
        },
        "result": result,
        "summary": summary,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "status": "success",
    }
    return success_response(
        data=response,
        message="单病历测试完成",
        trace_id=get_trace_id(request),
    )


@router.post("/workspace/test/batch")
async def test_workspace_batch(
    request: Request,
    payload: WorkspaceTestRequest,
    qc_service: SichuanQCService = Depends(get_custom_qc_service),
    current_user: Dict[str, Any] = Depends(get_current_user),
    workspace: CustomQCWorkspaceService = Depends(get_workspace_service),
):
    if not payload.records:
        raise HTTPException(status_code=422, detail="至少需要提供一条病历")

    draft = workspace.get_draft(draft_id=payload.draft_id, created_by=_current_user_id(current_user))
    if not draft:
        raise HTTPException(status_code=404, detail="草稿不存在或无权限")

    records = workspace.hydrate_records_with_medical_text([record.model_dump() for record in payload.records])
    rule_payload = _workspace_rule_payload_from_draft(draft)
    items: List[Dict[str, Any]] = []
    failed_records: List[Dict[str, Any]] = []
    total_tokens = 0
    total_processing_time = 0.0

    for record in records:
        try:
            ensure_record_medical_text([record])
            result = await evaluate_inline_rule(
                qc_service=qc_service,
                rule=rule_payload,
                record=record,
                temperature=payload.temperature,
                top_p=payload.top_p,
                max_tokens=payload.max_tokens,
            )
            total_tokens += int((result.get("performance") or {}).get("token_usage") or 0)
            total_processing_time += float(
                (result.get("performance") or {}).get("processing_time") or 0.0
            )
            items.append(result)
        except Exception as exc:
            logger.warning("workspace 批量测试单条病历失败: %s", exc)
            failed_records.append(
                {
                    "record_id": str(record.get("record_id") or ""),
                    "visit_id": str(record.get("visit_id") or ""),
                    "patient_name": str(record.get("patient_name") or ""),
                    "department": str(record.get("department") or ""),
                    "error": str(exc),
                }
            )

    summary = {
        "total_records": len(records),
        "success_count": len(items),
        "failed_count": len(failed_records),
        "issue_records": sum(1 for item in items if item.get("status") == "non_compliant"),
        "compliant_records": sum(
            1 for item in items if item.get("status") in {"compliant", "not_applicable"}
        ),
        "total_tokens": total_tokens,
        "total_processing_time": total_processing_time,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    workspace.save_last_test_summary(
        draft_id=payload.draft_id,
        created_by=_current_user_id(current_user),
        summary=summary,
    )
    response = {
        "draft_id": payload.draft_id,
        "rule": rule_payload,
        "summary": summary,
        "items": items,
        "failed_records": failed_records,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "status": "success",
    }
    return success_response(
        data=response,
        message="批量病历测试完成",
        trace_id=get_trace_id(request),
    )


@router.post("/workspace/batch-jobs")
async def create_workspace_batch_job(
    request: Request,
    payload: WorkspaceBatchJobCreateRequest,
    background_tasks: BackgroundTasks,
    current_user: Dict[str, Any] = Depends(get_current_user),
    workspace: CustomQCWorkspaceService = Depends(get_workspace_service),
):
    created_by = _current_user_id(current_user)
    draft = workspace.get_draft(draft_id=payload.draft_id, created_by=created_by)
    if not draft:
        raise HTTPException(status_code=404, detail="草稿不存在或无权限")

    records = workspace.collect_records(
        scope=payload.scope,
        department=payload.department,
        doctor=payload.doctor,
        date_field=payload.date_field,
        start_date=payload.start_date,
        end_date=payload.end_date,
        keyword=payload.keyword,
        record_ids=payload.record_ids or None,
    )
    if not records:
        raise HTTPException(status_code=422, detail="当前筛选条件下没有可执行的病历")

    job = workspace.create_batch_job(
        draft=draft,
        created_by=created_by,
        scope=payload.scope,
        filters=_batch_job_payload_filters(payload),
        record_ids=payload.record_ids or [],
        total_records=len(records),
    )
    background_tasks.add_task(_run_workspace_batch_job, job["id"])
    return success_response(
        data=job,
        message="批量任务已创建",
        trace_id=get_trace_id(request),
    )


@router.get("/workspace/batch-jobs")
async def list_workspace_batch_jobs(
    request: Request,
    draft_id: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    current_user: Dict[str, Any] = Depends(get_current_user),
    workspace: CustomQCWorkspaceService = Depends(get_workspace_service),
):
    result = workspace.list_batch_jobs(
        created_by=_current_user_id(current_user),
        draft_id=draft_id,
        page=page,
        page_size=page_size,
    )
    return success_response(
        data={
            "items": result.items,
            "total": result.total,
            "page": result.page,
            "page_size": result.page_size,
        },
        message="获取批量任务成功",
        trace_id=get_trace_id(request),
    )


@router.get("/workspace/batch-jobs/{job_id}")
async def get_workspace_batch_job(
    job_id: str,
    request: Request,
    current_user: Dict[str, Any] = Depends(get_current_user),
    workspace: CustomQCWorkspaceService = Depends(get_workspace_service),
):
    job = workspace.get_batch_job(job_id=job_id, created_by=_current_user_id(current_user))
    if not job:
        raise HTTPException(status_code=404, detail="批量任务不存在或无权限")
    return success_response(
        data=job,
        message="获取批量任务详情成功",
        trace_id=get_trace_id(request),
    )


@router.get("/workspace/batch-jobs/{job_id}/export")
async def export_workspace_batch_job(
    job_id: str,
    request: Request,
    format: str = Query("xlsx", description="xlsx|csv"),
    current_user: Dict[str, Any] = Depends(get_current_user),
    workspace: CustomQCWorkspaceService = Depends(get_workspace_service),
):
    job = workspace.get_batch_job(job_id=job_id, created_by=_current_user_id(current_user))
    if not job:
        raise HTTPException(status_code=404, detail="批量任务不存在或无权限")

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    safe_rule = (job.get("rule_code") or "workspace").replace("/", "_")
    if format.lower() == "csv":
        content = workspace.export_batch_job_csv(job=job)
        filename = f"{safe_rule}_{timestamp}.csv"
        return StreamingResponse(
            iter([content.getvalue().encode("utf-8-sig")]),
            media_type="text/csv; charset=utf-8",
            headers={"Content-Disposition": f"attachment; filename={filename}"},
        )

    workbook = workspace.export_batch_job_workbook(job=job)
    filename = f"{safe_rule}_{timestamp}.xlsx"
    return StreamingResponse(
        workbook,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )
