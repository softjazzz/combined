"""规则验收接口：以规则为中心组织测试病例、运行、复核、结论与批准。"""
from __future__ import annotations

from typing import Any, Dict, Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from ..core.response import get_trace_id, success_response
from ..core.security import get_current_user, require_roles
from ..services.product_activation import require_product_activation
from ..services.rule_validation import (
    RuleValidationConflict,
    RuleValidationService,
    compare_cases,
    derive_stage,
)

router = APIRouter(
    prefix="/api/v1/qc/rule-validation",
    tags=["规则验收"],
    dependencies=[Depends(require_roles("admin", "qc_manager"))],
)


class CaseAnswerRequest(BaseModel):
    revision: int = Field(ge=0, description="当前预期修订号；新关联为 0")
    expected_status: Literal["compliant", "non_compliant", "not_applicable", "data_gap"]
    human_reason: str = Field(min_length=1, max_length=4000)
    purpose: Literal["development", "acceptance"] = "development"


class RunRequest(BaseModel):
    item_ids: Optional[list[str]] = Field(default=None, max_length=50, description="为空时运行全部已关联病例")


class CaseReviewRequest(BaseModel):
    decision: Literal["confirmed", "problem"]
    note: str = Field(min_length=1, max_length=4000)


class ConclusionRequest(BaseModel):
    run_id: str
    decision: Literal["accepted", "rejected"]
    note: str = Field(min_length=1, max_length=4000)
    gap_ack: str = Field(default="", max_length=4000)


class ApprovalRequest(BaseModel):
    decision: Literal["approved", "rejected"]
    note: str = Field(min_length=1, max_length=4000)


def _service() -> RuleValidationService:
    return RuleValidationService()


def _user(current_user: Dict[str, Any]) -> str:
    from .qc_sample_pools import _current_user_id
    return _current_user_id(current_user)


def _error(exc: Exception) -> HTTPException:
    status = 404 if isinstance(exc, LookupError) else 409 if isinstance(exc, RuleValidationConflict) else 422
    return HTTPException(status_code=status, detail=str(exc))


async def _read_job(request: Request, job_id: str | None, current_user: Dict[str, Any]) -> dict | None:
    if not job_id:
        return None
    # 读取通过 Envelope 校验的 Canonical 结果（正式保存层），不直接读 items_json；
    # 客户投影把病例坐标换成不可逆引用，无法按病例比较，所以比较在服务端完成，只返回比较行。
    # 任务号来自本系统的验收运行记录；本路由已限定 admin/qc_manager，多人协作复核不限任务创建人。
    from fastapi.concurrency import run_in_threadpool
    from .qc_sichuan import _hydrate_luxian_canonical_batch_job_or_409, _sichuan_workspace_service
    workspace = _sichuan_workspace_service()
    job = await run_in_threadpool(workspace.get_batch_job_for_processing, job_id=job_id)
    if not job:
        raise HTTPException(status_code=404, detail="验收运行对应的质控任务不存在")
    return await run_in_threadpool(_hydrate_luxian_canonical_batch_job_or_409, workspace=workspace, job=job)


async def _run_rows(request: Request, run: dict, current_user: Dict[str, Any]) -> list[dict]:
    job = await _read_job(request, run["job_id"], current_user)
    if job is None:
        job = {"status": "creation_failed" if run["state"] == "creation_failed" else "creating"}
    baseline_jobs = {}
    for case in run["regression_cases"]:
        baseline_id = case.get("baseline_job_id")
        if not baseline_id or baseline_id in baseline_jobs:
            continue
        try:
            baseline_jobs[baseline_id] = await _read_job(request, baseline_id, current_user)
        except HTTPException as exc:
            if exc.status_code not in {404, 409}:
                raise
            baseline_jobs[baseline_id] = None  # 历史结果缺失或合同不可读，明确列为基线缺口。
    # 本规则病例 + 同族回归病例（各按自己的规则比较）
    return compare_cases(run["rule_id"], run["cases"] + run["regression_cases"], job,
                         project=_project_result, baseline_jobs=baseline_jobs)


_RESULT_FIELDS = ("status", "display_status", "reason_code", "customer_conclusion", "conclusion",
                  "customer_suggestion", "suggestion", "findings", "evidence", "customer_display_facts", "criterion_results")


def _project_result(item: dict) -> dict:
    """逐例核对只展示客户安全投影字段，不回传病历身份或内部审计字段。"""
    from ..services.custom_qc_workspace_service import customer_safe_projection_key, project_customer_safe_result_item
    projected = project_customer_safe_result_item(item, hmac_key=customer_safe_projection_key())
    return {k: projected.get(k) for k in _RESULT_FIELDS}


async def _detail(request: Request, service: RuleValidationService, rule_id: str, current_user) -> dict:
    rule = service._rule(rule_id)
    cases = service.list_cases(rule_id)
    runs = service.list_runs(rule_id)
    events = service.list_events(rule_id)
    latest_rows = await _run_rows(request, runs[0], current_user) if runs else None
    summary = service.summarize(rule_id, run=runs[0] if runs else None, rows=latest_rows)
    return {
        "rule": rule,
        "stage": derive_stage(rule, cases, runs, events, latest_rows),
        "cases": cases,
        "coverage": summary["coverage"],
        "runs": runs,
        "latest_run_rows": latest_rows,
        "acceptance_blockers": summary["acceptance_blockers"] if runs else [],
        "regression_gaps": summary["regression_gaps"],
        "events": events,
    }


@router.get("/rules")
async def list_rules(request: Request, include_released: bool = False,
                     current_user: Dict[str, Any] = Depends(get_current_user)):
    service = _service()
    items = []
    for rule_id, rule in sorted(service.catalog().items()):
        if rule["release_scope"] != "acceptance_only" and not include_released:
            continue
        cases = service.list_cases(rule_id)
        runs = service.list_runs(rule_id)
        events = service.list_events(rule_id)
        latest_rows = None
        if runs:
            try:
                latest_rows = await _run_rows(request, runs[0], current_user)
            except HTTPException:
                latest_rows = None  # 任务不可读时列表只显示为验证中，不阻塞整页
        items.append({
            **rule,
            "stage": derive_stage(rule, cases, runs, events, latest_rows),
            "case_count": len(cases),
            "coverage": service.summarize(rule_id)["coverage"],
            "latest_run": runs[0] if runs else None,
        })
    return success_response(data={"items": items}, trace_id=get_trace_id(request))


@router.get("/rules/{rule_id}")
async def get_rule(request: Request, rule_id: str, current_user: Dict[str, Any] = Depends(get_current_user)):
    try:
        data = await _detail(request, _service(), rule_id, current_user)
    except (LookupError, ValueError) as exc:
        raise _error(exc) from exc
    return success_response(data=data, trace_id=get_trace_id(request))


@router.get("/rules/{rule_id}/candidate-cases")
async def list_candidate_cases(request: Request, rule_id: str,
                               current_user: Dict[str, Any] = Depends(get_current_user)):
    try:
        data = _service().list_candidate_cases(rule_id)
    except (LookupError, ValueError) as exc:
        raise _error(exc) from exc
    return success_response(data={"items": data}, trace_id=get_trace_id(request))


@router.put("/rules/{rule_id}/cases/{item_id}")
async def upsert_case_answer(request: Request, rule_id: str, item_id: str, payload: CaseAnswerRequest,
                             current_user: Dict[str, Any] = Depends(get_current_user)):
    try:
        answer = _service().upsert_answer(rule_id, item_id, revision=payload.revision,
                                          expected_status=payload.expected_status,
                                          human_reason=payload.human_reason, purpose=payload.purpose,
                                          user=_user(current_user))
    except (LookupError, ValueError) as exc:
        raise _error(exc) from exc
    return success_response(data=answer, trace_id=get_trace_id(request))


@router.delete("/rules/{rule_id}/cases/{item_id}")
async def remove_case_answer(request: Request, rule_id: str, item_id: str, revision: int,
                             current_user: Dict[str, Any] = Depends(get_current_user)):
    try:
        _service().remove_answer(rule_id, item_id, revision=revision)
    except (LookupError, ValueError) as exc:
        raise _error(exc) from exc
    return success_response(data={"removed": True}, trace_id=get_trace_id(request))


@router.post("/rules/{rule_id}/runs")
async def start_run(request: Request, rule_id: str, payload: RunRequest,
                    current_user: Dict[str, Any] = Depends(get_current_user),
                    activation: Dict[str, Any] = Depends(require_product_activation)):
    from . import qc_sample_pools as pools_api
    from ..services.custom_qc_sample_pool_service import CUSTOMER_TEST_POOL_ID
    service = _service()
    try:
        run = service.begin_run(rule_id, payload.item_ids, _user(current_user))
    except (LookupError, ValueError) as exc:
        raise _error(exc) from exc
    # 同一测试病例可能同时是本规则病例与同族保护集病例，提交任务时按病例去重
    unique_cases = list({c["item_id"]: c for c in run["cases"] + run["regression_cases"]}.values())
    item_ids = [c["item_id"] for c in unique_cases]
    try:
        request.state.rule_validation_reference = {"kind": "rule", "run_id": run["id"], "item_ids": item_ids}
        # 人工预期不进入运行请求；只传病例和目标规则，走正式样本池执行链。
        result = await pools_api.run_sample_pool_intrinsic_validation(
            request, CUSTOMER_TEST_POOL_ID,
            pools_api.SamplePoolRunRequest(
                sample_item_ids=item_ids,
                record_refs=[pools_api.SamplePoolRunRecordRef(**c["record_ref"]) for c in unique_cases],
                # 共享抽取批次规则按“上线后范围”执行：本规则 + 同执行器已上线规则
                selected_rule_ids=run["scope_rule_ids"], rule_set_key=pools_api.LUXIAN_0609_QC_RULE_SET_KEY,
                group_by_luxian_family=False),
            current_user, activation)
    except Exception:
        try:
            service.bind_run(run["id"], None, None)
        except RuleValidationConflict:
            pass
        raise
    finally:
        request.state.rule_validation_reference = None
    return success_response(data={"run_id": run["id"], "job_id": result["data"]["job_id"]},
                            trace_id=get_trace_id(request))


@router.get("/runs/{run_id}")
async def get_run(request: Request, run_id: str, current_user: Dict[str, Any] = Depends(get_current_user)):
    service = _service()
    try:
        run = service.get_run(run_id)
    except LookupError as exc:
        raise _error(exc) from exc
    rows = await _run_rows(request, run, current_user)
    reviews = [e for e in service.list_events(run["rule_id"]) if e["run_id"] == run_id and e["kind"] == "case_review"]
    return success_response(data={"run": run, "rows": rows, "reviews": reviews}, trace_id=get_trace_id(request))


@router.post("/runs/{run_id}/cases/{item_id}/reviews")
async def review_case(request: Request, run_id: str, item_id: str, payload: CaseReviewRequest,
                      current_user: Dict[str, Any] = Depends(get_current_user)):
    service = _service()
    try:
        run = service.get_run(run_id)
        rows = await _run_rows(request, run, current_user)
        event = service.review_case(run, rows, item_id, decision=payload.decision, note=payload.note,
                                    user=_user(current_user))
    except (LookupError, ValueError) as exc:
        raise _error(exc) from exc
    return success_response(data=event, trace_id=get_trace_id(request))


@router.post("/rules/{rule_id}/conclusion")
async def conclude(request: Request, rule_id: str, payload: ConclusionRequest,
                   current_user: Dict[str, Any] = Depends(get_current_user)):
    service = _service()
    try:
        run = service.get_run(payload.run_id)
        if run["rule_id"] != rule_id:
            raise LookupError("运行不属于该规则")
        latest = service.list_runs(rule_id)[0]
        if latest["id"] != run["id"]:
            raise RuleValidationConflict("只能对最新一次运行下结论")
        rows = await _run_rows(request, run, current_user)
        event = service.conclude(run, rows, decision=payload.decision, note=payload.note,
                                 gap_ack=payload.gap_ack, user=_user(current_user))
    except (LookupError, ValueError) as exc:
        raise _error(exc) from exc
    return success_response(data=event, trace_id=get_trace_id(request))


@router.post("/rules/{rule_id}/approval")
async def approve(request: Request, rule_id: str, payload: ApprovalRequest,
                  current_user: Dict[str, Any] = Depends(get_current_user)):
    try:
        event = _service().approve(rule_id, decision=payload.decision, note=payload.note, user=_user(current_user))
    except (LookupError, ValueError) as exc:
        raise _error(exc) from exc
    return success_response(data=event, trace_id=get_trace_id(request))
