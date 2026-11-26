"""规则验收接口：以规则为中心组织测试病例、运行、复核、结论与批准。"""
from __future__ import annotations

from typing import Any, Dict, Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import select
from starlette.concurrency import run_in_threadpool

from ..core.response import get_trace_id, success_response
from ..core.roles import effective_roles
from ..core.security import get_current_user, require_roles
from ..services.product_activation import require_product_activation
from ..services.rule_validation import (
    RuleValidationConflict,
    RuleValidationService,
    _coverage,
    _event_view,
    _run_view,
    compare_cases,
    derive_stage,
    expected_statuses,
    RULE_SET_0609,
    RULE_SET_0916,
    RULE_SETS,
)

router = APIRouter(
    prefix="/api/v1/qc/rule-validation",
    tags=["规则验收"],
    dependencies=[Depends(require_roles("admin", "qc_manager", "super_admin"))],
)

_DEMO_FULL_ROLES = frozenset({"sync_admin", "super_admin", "developer"})


def _extract_user_roles(current_user: Optional[Dict[str, Any]]) -> set[str]:
    if not isinstance(current_user, dict):
        return set()
    roles = set(effective_roles(current_user.get("roles")))
    single = str(current_user.get("role") or "").strip()
    if single:
        roles.update(effective_roles([single]))
    return {r.strip().lower() for r in roles if isinstance(r, str) and r.strip()}


def _is_restricted_demo_account(current_user: Optional[Dict[str, Any]]) -> bool:
    if not isinstance(current_user, dict):
        return False
    if current_user.get("is_demo_account") is not True:
        return False
    return not bool(_extract_user_roles(current_user).intersection(_DEMO_FULL_ROLES))


def _reject_restricted_demo_account(
    current_user: Optional[Dict[str, Any]],
    detail: str = "演示账号禁止执行规则验收写操作",
) -> None:
    if _is_restricted_demo_account(current_user):
        raise HTTPException(status_code=403, detail=detail)


def _is_global_admin_sync(current_user: Optional[Dict[str, Any]]) -> bool:
    if not isinstance(current_user, dict):
        return False
    claim_roles = _extract_user_roles(current_user)
    claim_inst = str(current_user.get("institute_id") or "").strip()
    actor_id = str(current_user.get("id") or current_user.get("user_id") or "").strip()

    if actor_id and actor_id != "anonymous":
        try:
            from sqlalchemy import inspect as sa_inspect, text as sa_text
            from ..database import connection as db_connection
            from ..services.defect_rectification_service import _effective_persistent_roles
            from ..services.user_scope_owner import resolve_user_owner_schema

            session_factory = db_connection.SessionLocal
            if session_factory is not None:
                with session_factory() as session:
                    owner_schema = resolve_user_owner_schema(session)
                    inspector = sa_inspect(session.connection())
                    if inspector.has_table("sys_users", schema=owner_schema):
                        cols = {
                            col["name"]
                            for col in inspector.get_columns("sys_users", schema=owner_schema)
                        }
                        has_inst = "institute_id" in cols
                        table_ref = (
                            f'"{owner_schema}"."sys_users"'
                            if owner_schema
                            else '"sys_users"'
                        )
                        select_cols = (
                            "id, role, roles_json, is_active"
                            + (", institute_id" if has_inst else "")
                        )
                        row = (
                            session.execute(
                                sa_text(f"SELECT {select_cols} FROM {table_ref} WHERE id = :uid"),
                                {"uid": actor_id},
                            )
                            .mappings()
                            .one_or_none()
                        )
                        if row is not None:
                            if not bool(row.get("is_active")):
                                return False
                            p_roles = _effective_persistent_roles(
                                row.get("role"), row.get("roles_json")
                            )
                            if not p_roles:
                                return False
                            p_inst = str((row.get("institute_id") if has_inst else "") or "").strip()
                            return ("sync_admin" in p_roles) or (
                                bool(p_roles & {"admin", "super_admin"}) and not p_inst
                            )
        except Exception:
            pass

    return ("sync_admin" in claim_roles) or (
        bool(claim_roles & {"admin", "super_admin"}) and not claim_inst
    )


def _require_global_admin(
    current_user: Optional[Dict[str, Any]],
    detail: str = "仅全局管理员允许执行该操作",
) -> None:
    if not _is_global_admin_sync(current_user):
        raise HTTPException(status_code=403, detail=detail)


class CaseAnswerRequest(BaseModel):
    revision: int = Field(ge=0, description="当前预期修订号；新关联为 0")
    expected_status: Literal["compliant", "non_compliant", "not_applicable", "data_gap", "data_quality_gap"]
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


async def _read_job(
    request: Request,
    job_id: str | None,
    current_user: Dict[str, Any],
    *,
    job_cache: dict[str, dict | None] | None = None,
) -> dict | None:
    if not job_id:
        return None
    if job_cache is not None and job_id in job_cache:
        return job_cache[job_id]
    # 读取通过 Envelope 校验的 Canonical 结果（正式保存层），不直接读 items_json；
    # 客户投影把病例坐标换成不可逆引用，无法按病例比较，所以比较在服务端完成，只返回比较行。
    # 任务号来自本系统的验收运行记录；本路由已限定 admin/qc_manager，多人协作复核不限任务创建人。
    from .qc_sichuan import _hydrate_luxian_canonical_batch_job_or_409, _sichuan_workspace_service
    workspace = _sichuan_workspace_service()
    job = await run_in_threadpool(workspace.get_batch_job_for_processing, job_id=job_id)
    if not job:
        raise HTTPException(status_code=404, detail="验收运行对应的质控任务不存在")
    filters = job.get("filters") or {}
    if filters.get("rule_set_key") == RULE_SET_0916:
        from ..services.luxian_0916.execution_integrity import validate_luxian_0916_task_delivery
        if job.get("status") == "completed" or job.get("items"):
            try:
                validate_luxian_0916_task_delivery(
                    summary=job.get("summary") or {}, items=job.get("items") or [],
                    failures=job.get("failed_records") or [], expected_rule_ids=filters.get("rule_ids") or [],
                    expected_record_refs=filters.get("record_refs") or [])
            except ValueError as exc:
                raise HTTPException(status_code=409, detail="0916 已保存结果不符合交付合同，无法比较") from exc
        if job_cache is not None:
            job_cache[job_id] = job
        return job
    hydrated = await run_in_threadpool(_hydrate_luxian_canonical_batch_job_or_409, workspace=workspace, job=job)
    if job_cache is not None:
        job_cache[job_id] = hydrated
    return hydrated


async def _run_rows(
    request: Request,
    run: dict,
    current_user: Dict[str, Any],
    *,
    job_cache: dict[str, dict | None] | None = None,
) -> list[dict]:
    job = await _read_job(request, run["job_id"], current_user, job_cache=job_cache)
    if job is None:
        job = {"status": "creation_failed" if run["state"] == "creation_failed" else "creating"}
    baseline_jobs = {}
    for case in run["regression_cases"]:
        baseline_id = case.get("baseline_job_id")
        if not baseline_id or baseline_id in baseline_jobs:
            continue
        try:
            baseline_jobs[baseline_id] = await _read_job(request, baseline_id, current_user, job_cache=job_cache)
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
    if str(item.get("rule_id") or "").startswith("LX0916-"):
        # 0916 保存层已按原生合同验证。读取其公开事实，不套用 0609 Renderer 重写文案。
        # 只给有权限的验收者返回复核字段，排除诊断日志、模型原响应和病例身份。
        return {"status": item.get("status"), "reason_code": item.get("reason_code"),
                "findings": item.get("findings"), "conclusion": item.get("findings"),
                "suggestion": item.get("suggestion"),
                "evidence": item.get("evidence"),
                "customer_display_facts": item.get("decision_facts") or {},
                "document_anchors": item.get("document_anchors") or []}
    from ..services.custom_qc_workspace_service import customer_safe_projection_key, project_customer_safe_result_item
    projected = project_customer_safe_result_item(item, hmac_key=customer_safe_projection_key())
    return {k: projected.get(k) for k in _RESULT_FIELDS}


def _is_thread_isolated_sqlite_memory(service: Any) -> bool:
    """检测线程隔离内存 SQLite（SingletonThreadPool + :memory:），避免工作线程读到空库。"""
    try:
        from sqlalchemy.pool import SingletonThreadPool
        from ..database import connection as db_connection

        candidates = []
        sessions = getattr(service, "sessions", None)
        if sessions is not None:
            kw = getattr(sessions, "kw", None)
            if isinstance(kw, dict) and kw.get("bind") is not None:
                candidates.append(kw["bind"])
        sl = getattr(db_connection, "SessionLocal", None)
        if sl is not None:
            kw = getattr(sl, "kw", None)
            if isinstance(kw, dict) and kw.get("bind") is not None:
                candidates.append(kw["bind"])

        for bind in candidates:
            dialect_name = str(getattr(getattr(bind, "dialect", None), "name", "") or "")
            if dialect_name != "sqlite":
                return False
            pool = getattr(bind, "pool", None)
            url = getattr(bind, "url", None)
            db_name = getattr(url, "database", None) if url is not None else None
            return isinstance(pool, SingletonThreadPool) and db_name in (None, "", ":memory:")
    except Exception:
        pass
    return False


async def _run_service_sync(service: Any, fn, *args, **kwargs):
    if _is_thread_isolated_sqlite_memory(service):
        return fn(*args, **kwargs)
    return await run_in_threadpool(fn, *args, **kwargs)


def _load_rule_detail_sync(service: RuleValidationService, rule_id: str) -> tuple[dict, list[dict], list[dict], list[dict]]:
    rule = service._rule(rule_id)
    cases = service.list_cases(rule_id)
    runs = service.list_runs(rule_id)
    events = service.list_events(rule_id)
    return rule, cases, runs, events


def _load_rules_list_batch_sync(
    service: RuleValidationService,
    *,
    rule_set_key: str,
    include_released: bool,
) -> list[tuple[str, dict, list[dict], list[dict], list[dict], dict]]:
    """在工作线程中一次性批量加载规则列表所需的病例/运行/事件，消除 N+1 查库与事件循环阻塞。"""
    selected: list[tuple[str, dict]] = []
    for rule_id, rule in sorted(service.catalog().items()):
        if rule.get("rule_set_key", RULE_SET_0609) != rule_set_key:
            continue
        if rule["release_scope"] != "acceptance_only" and not include_released:
            continue
        selected.append((rule_id, rule))
    if not selected:
        return []

    if (
        isinstance(service, RuleValidationService)
        and hasattr(service, "_read_connection")
        and hasattr(service, "_customer_items")
        and hasattr(service, "_case_view")
        and hasattr(service, "runs")
        and hasattr(service, "events")
    ):
        rule_ids = [rule_id for rule_id, _ in selected]
        with service._read_connection() as session:
            customer_items = service._customer_items(session)
            run_rows = (
                session.execute(
                    select(service.runs)
                    .where(service.runs.c.rule_id.in_(rule_ids))
                    .order_by(service.runs.c.created_at.desc())
                )
                .mappings()
                .all()
            )
            event_rows = (
                session.execute(
                    select(service.events)
                    .where(service.events.c.rule_id.in_(rule_ids))
                    .order_by(service.events.c.created_at.asc())
                )
                .mappings()
                .all()
            )
        runs_by_rule: dict[str, list[dict]] = {rid: [] for rid in rule_ids}
        for row in run_rows:
            view = _run_view(dict(row))
            runs_by_rule.setdefault(view["rule_id"], []).append(view)
        events_by_rule: dict[str, list[dict]] = {rid: [] for rid in rule_ids}
        for row in event_rows:
            view = _event_view(dict(row))
            events_by_rule.setdefault(view["rule_id"], []).append(view)

        bundled: list[tuple[str, dict, list[dict], list[dict], list[dict], dict]] = []
        for rule_id, rule in selected:
            views = [service._case_view(item, rule_id) for item in customer_items]
            cases = sorted((v for v in views if v), key=lambda v: v["item_id"])
            runs = runs_by_rule.get(rule_id, [])
            events = events_by_rule.get(rule_id, [])
            coverage = _coverage(cases, expected_statuses(rule))
            bundled.append((rule_id, rule, cases, runs, events, coverage))
        return bundled

    bundled = []
    for rule_id, rule in selected:
        cases = service.list_cases(rule_id)
        runs = service.list_runs(rule_id)
        events = service.list_events(rule_id)
        coverage = service.summarize(rule_id)["coverage"]
        bundled.append((rule_id, rule, cases, runs, events, coverage))
    return bundled


async def _detail(request: Request, service: RuleValidationService, rule_id: str, current_user) -> dict:
    rule, cases, runs, events = await _run_service_sync(service, _load_rule_detail_sync, service, rule_id)
    latest_rows = await _run_rows(request, runs[0], current_user) if runs else None
    summary = await _run_service_sync(
        service,
        service.summarize,
        rule_id,
        run=runs[0] if runs else None,
        rows=latest_rows,
    )
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
                     rule_set_key: str = RULE_SET_0609,
                     current_user: Dict[str, Any] = Depends(get_current_user)):
    if rule_set_key not in RULE_SETS:
        raise HTTPException(status_code=422, detail="不支持的规则集")
    service = _service()
    bundled = await _run_service_sync(
        service,
        _load_rules_list_batch_sync,
        service,
        rule_set_key=rule_set_key,
        include_released=include_released,
    )
    job_cache: dict[str, dict | None] = {}
    items = []
    for rule_id, rule, cases, runs, events, coverage in bundled:
        latest_rows = None
        if runs:
            try:
                latest_rows = await _run_rows(request, runs[0], current_user, job_cache=job_cache)
            except HTTPException:
                latest_rows = None  # 任务不可读时列表只显示为验证中，不阻塞整页
        items.append({
            **rule,
            "stage": derive_stage(rule, cases, runs, events, latest_rows),
            "case_count": len(cases),
            "coverage": coverage,
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
def list_candidate_cases(request: Request, rule_id: str,
                         current_user: Dict[str, Any] = Depends(get_current_user)):
    try:
        data = _service().list_candidate_cases(rule_id)
    except (LookupError, ValueError) as exc:
        raise _error(exc) from exc
    return success_response(data={"items": data}, trace_id=get_trace_id(request))


@router.put("/rules/{rule_id}/cases/{item_id}")
def upsert_case_answer(request: Request, rule_id: str, item_id: str, payload: CaseAnswerRequest,
                       current_user: Dict[str, Any] = Depends(get_current_user)):
    _reject_restricted_demo_account(current_user, "演示账号禁止修改规则验收预期")
    _require_global_admin(current_user, "仅全局管理员可维护全平台规则验收预期")
    try:
        answer = _service().upsert_answer(rule_id, item_id, revision=payload.revision,
                                          expected_status=payload.expected_status,
                                          human_reason=payload.human_reason, purpose=payload.purpose,
                                          user=_user(current_user))
    except (LookupError, ValueError) as exc:
        raise _error(exc) from exc
    return success_response(data=answer, trace_id=get_trace_id(request))


@router.delete("/rules/{rule_id}/cases/{item_id}")
def remove_case_answer(request: Request, rule_id: str, item_id: str, revision: int,
                       current_user: Dict[str, Any] = Depends(get_current_user)):
    _reject_restricted_demo_account(current_user, "演示账号禁止删除规则验收预期")
    _require_global_admin(current_user, "仅全局管理员可维护全平台规则验收预期")
    try:
        _service().remove_answer(rule_id, item_id, revision=revision)
    except (LookupError, ValueError) as exc:
        raise _error(exc) from exc
    return success_response(data={"removed": True}, trace_id=get_trace_id(request))


@router.post("/rules/{rule_id}/runs")
async def start_run(request: Request, rule_id: str, payload: RunRequest,
                    current_user: Dict[str, Any] = Depends(get_current_user),
                    activation: Dict[str, Any] = Depends(require_product_activation)):
    _reject_restricted_demo_account(current_user, "演示账号禁止发起规则验收运行")
    from . import qc_sample_pools as pools_api
    from ..services.custom_qc_sample_pool_service import CUSTOMER_TEST_POOL_ID
    service = _service()
    try:
        rule = await _run_service_sync(service, service._rule, rule_id)
        run = await _run_service_sync(service, service.begin_run, rule_id, payload.item_ids, _user(current_user))
    except (LookupError, ValueError) as exc:
        raise _error(exc) from exc
    # 同一测试病例可能同时是本规则病例与同族保护集病例，提交任务时按病例去重
    unique_cases = list({c["item_id"]: c for c in run["cases"] + run["regression_cases"]}.values())
    item_ids = [c["item_id"] for c in unique_cases]
    try:
        rule_set_key = rule.get("rule_set_key", RULE_SET_0609)
        request.state.rule_validation_reference = {
            "kind": "rule", "run_id": run["id"], "item_ids": item_ids, "rule_set_key": rule_set_key}
        # 人工预期不进入运行请求；只传病例和目标规则，走正式样本池执行链。
        result = await pools_api.run_sample_pool_intrinsic_validation(
            request, CUSTOMER_TEST_POOL_ID,
            pools_api.SamplePoolRunRequest(
                sample_item_ids=item_ids,
                record_refs=[pools_api.SamplePoolRunRecordRef(**c["record_ref"]) for c in unique_cases],
                # 共享抽取批次规则按“上线后范围”执行：本规则 + 同执行器已上线规则
                **({"selected_rule_ids": run["scope_rule_ids"]} if rule_set_key != RULE_SET_0916 else {}),
                rule_set_key=rule_set_key,
                group_by_luxian_family=False),
            current_user, activation)
    except Exception:
        try:
            await _run_service_sync(service, service.bind_run, run["id"], None, None)
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
        run = await _run_service_sync(service, service.get_run, run_id)
    except LookupError as exc:
        raise _error(exc) from exc
    rows = await _run_rows(request, run, current_user)
    events = await _run_service_sync(service, service.list_events, run["rule_id"])
    reviews = [e for e in events if e["run_id"] == run_id and e["kind"] == "case_review"]
    return success_response(data={"run": run, "rows": rows, "reviews": reviews}, trace_id=get_trace_id(request))


@router.post("/runs/{run_id}/cases/{item_id}/reviews")
async def review_case(request: Request, run_id: str, item_id: str, payload: CaseReviewRequest,
                      current_user: Dict[str, Any] = Depends(get_current_user)):
    _reject_restricted_demo_account(current_user, "演示账号禁止提交规则验收复核")
    service = _service()
    try:
        run = await _run_service_sync(service, service.get_run, run_id)
        rows = await _run_rows(request, run, current_user)
        event = await _run_service_sync(
            service,
            service.review_case,
            run,
            rows,
            item_id,
            decision=payload.decision,
            note=payload.note,
            user=_user(current_user),
        )
    except (LookupError, ValueError) as exc:
        raise _error(exc) from exc
    return success_response(data=event, trace_id=get_trace_id(request))


@router.post("/rules/{rule_id}/conclusion")
async def conclude(request: Request, rule_id: str, payload: ConclusionRequest,
                   current_user: Dict[str, Any] = Depends(get_current_user)):
    _reject_restricted_demo_account(current_user, "演示账号禁止提交规则验收结论")
    service = _service()
    try:
        run = await _run_service_sync(service, service.get_run, payload.run_id)
        if run["rule_id"] != rule_id:
            raise LookupError("运行不属于该规则")
        runs = await _run_service_sync(service, service.list_runs, rule_id)
        if not runs:
            raise LookupError("该规则尚无验收运行记录")
        latest = runs[0]
        if latest["id"] != run["id"]:
            raise RuleValidationConflict("只能对最新一次运行下结论")
        rows = await _run_rows(request, run, current_user)
        event = await _run_service_sync(
            service,
            service.conclude,
            run,
            rows,
            decision=payload.decision,
            note=payload.note,
            gap_ack=payload.gap_ack,
            user=_user(current_user),
        )
    except (LookupError, ValueError) as exc:
        raise _error(exc) from exc
    return success_response(data=event, trace_id=get_trace_id(request))


@router.post("/rules/{rule_id}/approval")
def approve(request: Request, rule_id: str, payload: ApprovalRequest,
            current_user: Dict[str, Any] = Depends(get_current_user)):
    _reject_restricted_demo_account(current_user, "演示账号禁止批准规则上线")
    _require_global_admin(current_user, "仅全局管理员可批准全局规则上线")
    try:
        event = _service().approve(rule_id, decision=payload.decision, note=payload.note, user=_user(current_user))
    except (LookupError, ValueError) as exc:
        raise _error(exc) from exc
    return success_response(data=event, trace_id=get_trace_id(request))
