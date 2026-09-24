import logging
from datetime import datetime, timezone
from typing import Annotated, Any, Dict, List, Mapping, Optional, Sequence

from fastapi import APIRouter, BackgroundTasks, Depends, Query, Request
from fastapi import HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, ConfigDict, Field, StringConstraints, ValidationError

from ..core.response import get_trace_id, success_response
from ..core.security import get_current_user, require_roles
from ..services.custom_qc_service import (
    create_custom_qc_service,
    ensure_record_medical_text,
    evaluate_inline_rule_orchestrated,
    generate_custom_prompt,
)
from ..services.custom_qc_workspace_service import CustomQCWorkspaceService
from ..services.llm_observability import llm_observation_context
from ..services.product_activation import require_product_activation
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
    document_type: str = "日常病程记录"
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
    document_type: str = "日常病程记录"
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


NonEmptyRecordCoordinate = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1),
]


class WorkspaceBatchRecordRef(BaseModel):
    model_config = ConfigDict(extra="forbid")

    institute_id: NonEmptyRecordCoordinate
    patient_id: NonEmptyRecordCoordinate
    visit_id: NonEmptyRecordCoordinate


class WorkspaceBatchJobCreateRequest(BaseModel):
    draft_id: Optional[str] = None
    draft_ids: List[str] = Field(default_factory=list)
    execution_mode: str = "single"
    run_mode: str = "serial"
    scope: str = "final"
    department: Optional[str] = None
    doctor: Optional[str] = None
    date_field: str = "discharge"
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    keyword: Optional[str] = None
    record_refs: List[WorkspaceBatchRecordRef] = Field(default_factory=list)
    # 仅保留旧客户端的显式失败提示；新任务不得再用 visit_id 列表创建。
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
        "execution_mode": payload.execution_mode,
        "run_mode": payload.run_mode,
    }


def _record_ref_key(value: Mapping[str, Any]) -> tuple[str, str, str] | None:
    coordinates = tuple(
        str(value.get(field_name) or "").strip()
        for field_name in ("institute_id", "patient_id", "visit_id")
    )
    return coordinates if all(coordinates) else None


def _record_ref_matches_are_exact(
    *,
    record_refs: Sequence[Mapping[str, Any]],
    records: Sequence[Mapping[str, Any]],
) -> bool:
    requested_keys = [_record_ref_key(item) for item in record_refs]
    if (
        not requested_keys
        or any(item is None for item in requested_keys)
        or len(set(requested_keys)) != len(requested_keys)
    ):
        return False
    match_counts = {item: 0 for item in requested_keys if item is not None}
    for record in records:
        record_key = _record_ref_key(record)
        if record_key not in match_counts:
            return False
        match_counts[record_key] += 1
    return all(count == 1 for count in match_counts.values())


def _validated_worker_record_refs(raw: Any) -> List[Dict[str, str]]:
    if not isinstance(raw, list) or not raw:
        raise ValueError("批量任务 record_refs 缺失或无效")
    try:
        record_refs = [
            WorkspaceBatchRecordRef.model_validate(item).model_dump()
            for item in raw
        ]
    except ValidationError as exc:
        raise ValueError("批量任务 record_refs 缺失或无效") from exc
    if not _record_ref_matches_are_exact(record_refs=record_refs, records=record_refs):
        raise ValueError("批量任务 record_refs 重复或无效")
    return record_refs


def _normalize_execution_mode(value: Optional[str]) -> str:
    return "multi" if str(value or "").strip().lower() == "multi" else "single"


def _normalize_run_mode(value: Optional[str]) -> str:
    return "serial"


_FINAL_ARCHIVE_UNVERIFIED = (
    "final_archive_unverified: 归档状态未核验，终末或包含终末的混合范围暂不能执行质控任务"
)


def _requires_archive_verification(scope: Any) -> bool:
    return str(scope or "").strip().lower() != "running"


async def _run_workspace_batch_job(job_id: str) -> None:
    workspace = get_workspace_service()
    job = workspace.get_batch_job_for_processing(job_id=job_id)
    if not job:
        return

    try:
        if str(job.get("status") or "").strip().lower() == "queued" and _requires_archive_verification(
            job.get("scope")
        ):
            raise ValueError(_FINAL_ARCHIVE_UNVERIFIED)
        if not workspace.mark_batch_job_running(job_id=job_id):
            return
        current_job = workspace.get_batch_job_for_processing(job_id=job_id) or job
        filters = current_job.get("filters") or {}
        draft_ids = [str(item).strip() for item in (current_job.get("draft_ids") or []) if str(item).strip()]
        if not draft_ids:
            current_draft_id = str(current_job.get("draft_id") or "").strip()
            if current_draft_id:
                draft_ids = [current_draft_id]
        if not draft_ids:
            raise ValueError("批量任务缺少 draft_id 或 draft_ids")

        unique_draft_ids: List[str] = []
        for draft_id in draft_ids:
            if draft_id not in unique_draft_ids:
                unique_draft_ids.append(draft_id)

        drafts: List[Dict[str, Any]] = []
        for draft_id in unique_draft_ids:
            draft = workspace.get_draft(draft_id=draft_id, created_by=current_job["created_by"])
            if not draft:
                raise ValueError(f"规则草稿不存在或无权限: {draft_id}")
            drafts.append(draft)

        total_rules = max(1, len(drafts))
        if "record_refs" in filters:
            worker_record_refs = _validated_worker_record_refs(filters.get("record_refs"))
            worker_record_ids = None
        else:
            # 仅升级前已持久化且明确没有 record_refs 的任务允许 visit_id 兼容读取。
            worker_record_refs = None
            worker_record_ids = current_job.get("record_ids") or None
        records = workspace.collect_records(
            scope=current_job.get("scope") or "final",
            department=filters.get("department"),
            doctor=filters.get("doctor"),
            date_field=filters.get("date_field") or "discharge",
            start_date=filters.get("start_date"),
            end_date=filters.get("end_date"),
            keyword=filters.get("keyword"),
            record_ids=worker_record_ids,
            record_refs=worker_record_refs,
        )
        if worker_record_refs is not None and not _record_ref_matches_are_exact(
            record_refs=worker_record_refs,
            records=records,
        ):
            raise ValueError("批量任务 record_refs 未唯一命中完整病历")
        hydrated_records = workspace.hydrate_records_with_medical_text(records)
        total_records = len(hydrated_records)
        workspace.update_batch_job_progress(
            job_id=job_id,
            step_key="filter",
            rule_index=0,
            rule_count=total_rules,
            processed_records=0,
            total_records=total_records,
            summary_patch={
                "rule_count": total_rules,
                "total_records": total_records,
                "success_count": 0,
                "failed_count": 0,
                "issue_records": 0,
                "compliant_records": total_records,
                "total_tokens": 0,
                "total_processing_time": 0.0,
                "executor_breakdown": {"program": 0, "llm": 0},
                "cache_breakdown": {"hit": 0, "miss": 0},
            },
        )
        qc_service = await create_custom_qc_service()

        items: List[Dict[str, Any]] = []
        failed_records: List[Dict[str, Any]] = []
        rule_results: List[Dict[str, Any]] = []
        issue_record_ids: set[str] = set()
        failed_record_ids: set[str] = set()
        total_tokens = 0
        total_processing_time = 0.0
        executor_program = 0
        executor_llm = 0
        cache_hit_count = 0
        cache_miss_count = 0

        for rule_index, draft in enumerate(drafts, start=1):
            latest = workspace.get_batch_job_for_processing(job_id=job_id)
            if not latest or str(latest.get("status") or "").lower() == "canceled":
                logger.info("workspace 批量任务 %s 已取消，停止执行", job_id)
                return
            rule_payload = _workspace_rule_payload_from_draft(draft)
            rule_code = str(draft.get("rule_code") or "")
            rule_name = str(draft.get("name") or rule_code or "未命名规则")
            rule_items: List[Dict[str, Any]] = []
            rule_failed: List[Dict[str, Any]] = []
            rule_tokens = 0
            rule_processing_time = 0.0
            rule_executor_program = 0
            rule_executor_llm = 0
            rule_cache_hit = 0
            rule_cache_miss = 0

            workspace.update_batch_job_progress(
                job_id=job_id,
                step_key="run",
                rule_index=rule_index,
                rule_count=total_rules,
                processed_records=0,
                total_records=total_records,
                summary_patch={
                    "rule_count": total_rules,
                    "rule_results": rule_results,
                    "total_records": total_records,
                    "success_count": len(items),
                    "failed_count": len(failed_records),
                    "issue_records": len(issue_record_ids),
                    "compliant_records": max(
                        0,
                        total_records - len(issue_record_ids) - len(failed_record_ids),
                    ),
                    "total_tokens": int(total_tokens),
                    "total_processing_time": float(total_processing_time),
                    "executor_breakdown": {
                        "program": executor_program,
                        "llm": executor_llm,
                    },
                    "cache_breakdown": {
                        "hit": cache_hit_count,
                        "miss": cache_miss_count,
                    },
                },
            )

            for processed_index, record in enumerate(hydrated_records, start=1):
                latest = workspace.get_batch_job_for_processing(job_id=job_id)
                if not latest or str(latest.get("status") or "").lower() == "canceled":
                    logger.info("workspace 批量任务 %s 已取消，停止执行", job_id)
                    return
                record_id = str(record.get("record_id") or record.get("visit_id") or "").strip()
                try:
                    ensure_record_medical_text([record])
                    result = await evaluate_inline_rule_orchestrated(
                        qc_service=qc_service,
                        rule=rule_payload,
                        record=record,
                        temperature=filters.get("temperature"),
                        top_p=filters.get("top_p"),
                        max_tokens=filters.get("max_tokens"),
                    )
                    enriched_result = {
                        **result,
                        "rule_code": rule_code,
                        "rule_name": rule_name,
                        "draft_id": str(draft.get("id") or ""),
                    }
                    metadata = dict(enriched_result.get("metadata") or {})
                    total_tokens += int((enriched_result.get("performance") or {}).get("token_usage") or 0)
                    total_processing_time += float(
                        (enriched_result.get("performance") or {}).get("processing_time") or 0.0
                    )
                    rule_tokens += int((enriched_result.get("performance") or {}).get("token_usage") or 0)
                    rule_processing_time += float(
                        (enriched_result.get("performance") or {}).get("processing_time") or 0.0
                    )
                    executor_type = str(metadata.get("executor_type") or "llm").strip().lower()
                    if executor_type == "program":
                        executor_program += 1
                        rule_executor_program += 1
                    else:
                        executor_llm += 1
                        rule_executor_llm += 1
                    if metadata.get("cache_hit") is True:
                        cache_hit_count += 1
                        rule_cache_hit += 1
                    else:
                        cache_miss_count += 1
                        rule_cache_miss += 1
                    if str(enriched_result.get("status") or "").lower() == "non_compliant":
                        issue_record_ids.add(record_id)
                    items.append(enriched_result)
                    rule_items.append(enriched_result)
                except Exception as exc:
                    logger.warning("workspace batch job record failed: %s", exc)
                    failed_record_ids.add(record_id)
                    failed_payload = {
                        "rule_code": rule_code,
                        "rule_name": rule_name,
                        "draft_id": str(draft.get("id") or ""),
                        "record_id": str(record.get("record_id") or ""),
                        "visit_id": str(record.get("visit_id") or ""),
                        "patient_name": str(record.get("patient_name") or ""),
                        "department": str(record.get("department") or ""),
                        "error": str(exc),
                    }
                    failed_records.append(failed_payload)
                    rule_failed.append(failed_payload)

                workspace.update_batch_job_progress(
                    job_id=job_id,
                    step_key="run",
                    rule_index=rule_index,
                    rule_count=total_rules,
                    processed_records=processed_index,
                    total_records=total_records,
                    summary_patch={
                        "rule_count": total_rules,
                        "rule_results": rule_results,
                        "total_records": total_records,
                        "success_count": len(items),
                        "failed_count": len(failed_records),
                        "issue_records": len(issue_record_ids),
                        "compliant_records": max(
                            0,
                            total_records - len(issue_record_ids) - len(failed_record_ids),
                        ),
                        "total_tokens": int(total_tokens),
                        "total_processing_time": float(total_processing_time),
                        "executor_breakdown": {
                            "program": executor_program,
                            "llm": executor_llm,
                        },
                        "cache_breakdown": {
                            "hit": cache_hit_count,
                            "miss": cache_miss_count,
                        },
                    },
                )
            rule_summary = {
                "total_records": total_records,
                "success_count": len(rule_items),
                "failed_count": len(rule_failed),
                "issue_records": sum(1 for item in rule_items if item.get("status") == "non_compliant"),
                "compliant_records": sum(
                    1 for item in rule_items if item.get("status") in {"compliant", "not_applicable"}
                ),
                "total_tokens": int(rule_tokens),
                "total_processing_time": float(rule_processing_time),
                "executor_breakdown": {
                    "program": rule_executor_program,
                    "llm": rule_executor_llm,
                },
                "cache_breakdown": {
                    "hit": rule_cache_hit,
                    "miss": rule_cache_miss,
                },
            }
            rule_results.append(
                {
                    "id": str(draft.get("id") or ""),
                    "draft_id": str(draft.get("id") or ""),
                    "rule_code": rule_code,
                    "rule_name": rule_name,
                    "status": "failed" if rule_summary["failed_count"] >= total_records and total_records > 0 else "completed",
                    "items": rule_items,
                    "failed_records": rule_failed,
                    "updated_at": datetime.now(timezone.utc).isoformat(),
                    **rule_summary,
                    "progress": {
                        "rule_index": rule_index,
                        "rule_count": total_rules,
                        "processed_records": total_records,
                    },
                }
            )
            workspace.update_batch_job_progress(
                job_id=job_id,
                step_key="aggregate",
                rule_index=rule_index,
                rule_count=total_rules,
                processed_records=total_records,
                total_records=total_records,
                summary_patch={
                    "rule_count": total_rules,
                    "rule_results": rule_results,
                    "total_records": total_records,
                    "success_count": len(items),
                    "failed_count": len(failed_records),
                    "issue_records": len(issue_record_ids),
                    "compliant_records": max(
                        0,
                        total_records - len(issue_record_ids) - len(failed_record_ids),
                    ),
                    "total_tokens": int(total_tokens),
                    "total_processing_time": float(total_processing_time),
                    "executor_breakdown": {
                        "program": executor_program,
                        "llm": executor_llm,
                    },
                    "cache_breakdown": {
                        "hit": cache_hit_count,
                        "miss": cache_miss_count,
                    },
                },
                items=items,
                failed_records=failed_records,
            )

        summary = {
            "total_records": total_records,
            "total_tasks": total_records * total_rules,
            "rule_count": total_rules,
            "execution_mode": "multi" if total_rules > 1 else "single",
            "success_count": len(items),
            "failed_count": len(failed_records),
            "issue_records": len(issue_record_ids),
            "compliant_records": max(0, total_records - len(issue_record_ids) - len(failed_record_ids)),
            "total_tokens": int(total_tokens),
            "total_processing_time": float(total_processing_time),
            "executor_breakdown": {
                "program": executor_program,
                "llm": executor_llm,
            },
            "cache_breakdown": {
                "hit": cache_hit_count,
                "miss": cache_miss_count,
            },
            "rule_results": rule_results,
            "processed_rule_count": len(rule_results),
            "progress": {
                "step_key": "completed",
                "rule_index": total_rules,
                "rule_count": total_rules,
                "processed_records": total_records,
                "total_records": total_records,
            },
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        workspace.complete_batch_job(
            job_id=job_id,
            summary=summary,
            items=items,
            failed_records=failed_records,
        )
        for draft in drafts:
            workspace.save_last_test_summary(
                draft_id=str(draft.get("id") or ""),
                created_by=current_job["created_by"],
                summary=summary,
            )
    except Exception as exc:
        logger.exception("workspace batch job failed: %s", exc)
        workspace.fail_batch_job(job_id=job_id, error_message=str(exc))


@router.post("/prompt/generate")
async def generate_prompt(request: Request, payload: PromptGenerateRequest):
    trace_id = get_trace_id(request)
    with llm_observation_context(
        business_scene="custom_qc_prompt_generation",
        root_job_id=trace_id,
        executor_key="custom_qc_prompt_generation",
    ):
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
        trace_id=trace_id,
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
    result = await evaluate_inline_rule_orchestrated(
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
    executor_program = 0
    executor_llm = 0
    cache_hit_count = 0
    cache_miss_count = 0

    for record in record_dicts:
        try:
            result = await evaluate_inline_rule_orchestrated(
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
            metadata = dict(result.get("metadata") or {})
            if str(metadata.get("executor_type") or "llm").strip().lower() == "program":
                executor_program += 1
            else:
                executor_llm += 1
            if metadata.get("cache_hit") is True:
                cache_hit_count += 1
            else:
                cache_miss_count += 1
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
        "executor_breakdown": {
            "program": executor_program,
            "llm": executor_llm,
        },
        "cache_breakdown": {
            "hit": cache_hit_count,
            "miss": cache_miss_count,
        },
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

    trace_id = get_trace_id(request)
    with llm_observation_context(
        business_scene="custom_qc_prompt_generation",
        root_job_id=trace_id,
        executor_key="custom_qc_prompt_generation",
    ):
        prompt_result = await generate_custom_prompt(
            scene=str(draft.get("scene") or "running"),
            document_type=str(draft.get("document_type") or "日常病程记录"),
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
        trace_id=trace_id,
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
    check_logic = dict(draft.get("check_logic") or {})
    applicable_documents = draft.get("applicable_documents")
    if not isinstance(applicable_documents, list) or not applicable_documents:
        applicable_documents = check_logic.get("applicable_documents")
    if not isinstance(applicable_documents, list):
        applicable_documents = []

    return {
        "rule_code": str(draft.get("rule_code") or draft.get("id") or "INLINE-DRAFT"),
        "name": str(draft.get("name") or ""),
        "description": str(draft.get("description") or ""),
        "prompt_template": str(draft.get("prompt_template") or ""),
        "severity": str(draft.get("severity") or "major"),
        "document_type": str(draft.get("document_type") or "日常病程记录"),
        "applicable_documents": applicable_documents,
        "scene": str(draft.get("scene") or "running"),
        "execution_domain": str(check_logic.get("execution_domain") or "").strip(),
        "doc_scope": str(check_logic.get("doc_scope") or "primary").strip(),
        "check_logic": check_logic,
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
    result = await evaluate_inline_rule_orchestrated(
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
    executor_program = 0
    executor_llm = 0
    cache_hit_count = 0
    cache_miss_count = 0

    for record in records:
        try:
            ensure_record_medical_text([record])
            result = await evaluate_inline_rule_orchestrated(
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
            metadata = dict(result.get("metadata") or {})
            if str(metadata.get("executor_type") or "llm").strip().lower() == "program":
                executor_program += 1
            else:
                executor_llm += 1
            if metadata.get("cache_hit") is True:
                cache_hit_count += 1
            else:
                cache_miss_count += 1
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
        "executor_breakdown": {
            "program": executor_program,
            "llm": executor_llm,
        },
        "cache_breakdown": {
            "hit": cache_hit_count,
            "miss": cache_miss_count,
        },
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
    current_user: Dict[str, Any] = Depends(require_product_activation),
    workspace: CustomQCWorkspaceService = Depends(get_workspace_service),
):
    if _requires_archive_verification(payload.scope):
        raise HTTPException(status_code=422, detail=_FINAL_ARCHIVE_UNVERIFIED)
    created_by = _current_user_id(current_user)
    if payload.record_ids:
        raise HTTPException(
            status_code=422,
            detail="新建批量任务不再接受 record_ids，请提交完整三坐标 record_refs",
        )
    record_refs = [item.model_dump() for item in payload.record_refs]
    if record_refs and not _record_ref_matches_are_exact(
        record_refs=record_refs,
        records=record_refs,
    ):
        raise HTTPException(status_code=422, detail="record_refs 存在重复或无效三坐标")
    requested_draft_ids = [str(item).strip() for item in (payload.draft_ids or []) if str(item).strip()]
    if payload.draft_id:
        draft_id = str(payload.draft_id).strip()
        if draft_id:
            requested_draft_ids.insert(0, draft_id)
    normalized_draft_ids: List[str] = []
    for draft_id in requested_draft_ids:
        if draft_id and draft_id not in normalized_draft_ids:
            normalized_draft_ids.append(draft_id)
    if not normalized_draft_ids:
        raise HTTPException(status_code=422, detail="draft_id 或 draft_ids 至少提供一个")

    drafts: List[Dict[str, Any]] = []
    missing_draft_ids: List[str] = []
    for draft_id in normalized_draft_ids:
        draft = workspace.get_draft(draft_id=draft_id, created_by=created_by)
        if draft:
            drafts.append(draft)
        else:
            missing_draft_ids.append(draft_id)
    if missing_draft_ids:
        raise HTTPException(status_code=404, detail=f"草稿不存在或无权限: {', '.join(missing_draft_ids)}")
    if not drafts:
        raise HTTPException(status_code=404, detail="草稿不存在或无权限")

    records = workspace.collect_records(
        scope=payload.scope,
        department=payload.department,
        doctor=payload.doctor,
        date_field=payload.date_field,
        start_date=payload.start_date,
        end_date=payload.end_date,
        keyword=payload.keyword,
        record_ids=None,
        record_refs=record_refs or None,
    )
    if record_refs:
        effective_record_refs = record_refs
    else:
        effective_record_refs = [
            {
                "institute_id": str(item.get("institute_id") or "").strip(),
                "patient_id": str(item.get("patient_id") or "").strip(),
                "visit_id": str(item.get("visit_id") or "").strip(),
            }
            for item in records
        ]
    if not _record_ref_matches_are_exact(
        record_refs=effective_record_refs,
        records=records,
    ):
        raise HTTPException(
            status_code=422,
            detail=(
                "请求的 record_refs 未全部唯一命中完整三坐标病历"
                if record_refs
                else "筛选结果为空或包含无法唯一识别的三坐标病历"
            ),
        )

    execution_mode = _normalize_execution_mode(payload.execution_mode)
    if len(drafts) > 1:
        execution_mode = "multi"
    run_mode = _normalize_run_mode(payload.run_mode)

    primary_draft = drafts[0]
    if execution_mode == "multi":
        primary_draft = {
            "id": drafts[0].get("id"),
            "rule_code": "CUST-MULTI",
            "name": f"自定义规则批量任务({len(drafts)}条)",
            "scene": drafts[0].get("scene") or "final",
        }

    job = workspace.create_batch_job(
        draft=primary_draft,
        created_by=created_by,
        scope=payload.scope,
        filters=_batch_job_payload_filters(payload),
        record_ids=[item["visit_id"] for item in effective_record_refs],
        record_refs=effective_record_refs,
        total_records=len(records),
        draft_ids=[str(item.get("id") or "") for item in drafts],
        execution_mode=execution_mode,
        run_mode=run_mode,
        rule_count=len(drafts),
    )
    background_tasks.add_task(_run_workspace_batch_job, job["id"])
    return success_response(
        data={
            **job,
            "draft_ids": [str(item.get("id") or "") for item in drafts],
            "execution_mode": execution_mode,
            "run_mode": run_mode,
            "rule_count": len(drafts),
        },
        message="批量任务已创建",
        trace_id=get_trace_id(request),
    )


@router.get("/workspace/batch-jobs")
async def list_workspace_batch_jobs(
    request: Request,
    draft_id: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    scope: Optional[str] = Query(None),
    q: Optional[str] = Query(None),
    executor_type: Optional[str] = Query(None),
    cache_hit: Optional[str] = Query(None),
    created_start_date: Optional[str] = Query(None),
    created_end_date: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    current_user: Dict[str, Any] = Depends(get_current_user),
    workspace: CustomQCWorkspaceService = Depends(get_workspace_service),
):
    executor_filter = str(executor_type or "").strip().lower() or None
    cache_hit_filter: Optional[bool] = None
    cache_hit_value = str(cache_hit or "").strip().lower()
    if cache_hit_value in {"hit", "true", "1", "yes"}:
        cache_hit_filter = True
    elif cache_hit_value in {"miss", "false", "0", "no"}:
        cache_hit_filter = False

    result = workspace.list_batch_jobs(
        created_by=_current_user_id(current_user),
        draft_id=draft_id,
        status=status,
        scope=scope,
        query=q,
        executor_type=executor_filter,
        cache_hit=cache_hit_filter,
        created_start_date=created_start_date,
        created_end_date=created_end_date,
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


@router.post("/workspace/batch-jobs/{job_id}/cancel")
async def cancel_workspace_batch_job(
    request: Request,
    job_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user),
    workspace: CustomQCWorkspaceService = Depends(get_workspace_service),
):
    job = workspace.cancel_batch_job(job_id=job_id, created_by=_current_user_id(current_user))
    if not job:
        raise HTTPException(status_code=404, detail="批量任务不存在或无权限")
    return success_response(
        data=job,
        message="批量任务已取消",
        trace_id=get_trace_id(request),
    )


@router.post("/workspace/batch-jobs/{job_id}/retry")
async def retry_workspace_batch_job(
    request: Request,
    job_id: str,
    background_tasks: BackgroundTasks,
    current_user: Dict[str, Any] = Depends(require_product_activation),
    workspace: CustomQCWorkspaceService = Depends(get_workspace_service),
):
    created_by = _current_user_id(current_user)
    existing_job = workspace.get_batch_job(job_id=job_id, created_by=created_by)
    if not existing_job:
        raise HTTPException(status_code=404, detail="批量任务不存在或无权限")
    if _requires_archive_verification(existing_job.get("scope")):
        raise HTTPException(status_code=422, detail=_FINAL_ARCHIVE_UNVERIFIED)
    job = workspace.retry_batch_job(job_id=job_id, created_by=created_by)
    if not job:
        raise HTTPException(status_code=404, detail="批量任务不存在或无权限")
    background_tasks.add_task(_run_workspace_batch_job, job_id)
    return success_response(
        data=job,
        message="批量任务已重新入队",
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
