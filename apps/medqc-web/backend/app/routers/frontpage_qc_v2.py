"""首页质控 V2 接口：规则目录、批量任务、结果列表与详情、复核、统计、导出。

确定性规则，不调用模型；CDM 只读，结果写入 qc schema 下首页质控专用表。
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Literal, Optional
from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import Response
from pydantic import BaseModel, ConfigDict, Field

from app.core.response import get_trace_id, success_response
from app.services.case_identity import CaseRef
from app.services.detached_task_runner import submit_detached_task
from app.services.frontpage_qc_v2 import RULES, RULESET_VERSION, FrontpageRef, build_frontpage_doc, load_frontpage_raw
from app.services.frontpage_qc_v2.config import GRADE_EXCELLENT, GRADE_LABELS, GRADE_QUALIFIED, SOURCE_GAP_FIELDS
from app.services.frontpage_qc_v2.engine import input_fingerprint
from app.services.frontpage_qc_v2.jobs import MAX_RECORDS_PER_RUN, refs_from_records, run_frontpage_qc_job
from app.services.frontpage_qc_v2.model import GROUP_LABELS, SECTION_LABELS, SEVERITY_LABELS
from app.services.frontpage_qc_v2.reporting import build_analytics, build_export_workbook
from app.services.frontpage_qc_v2.scoring_items import SCORE_ITEMS, SECTION_POINTS
from app.services.frontpage_qc_v2.store import (
    RUN_ACTIVE_STATUSES,
    FrontpageQcNotFound,
    FrontpageQcStore,
    FrontpageQcStoreUnavailable,
)
from app.services.product_activation import require_product_activation

router = APIRouter(prefix="/api/v1/frontpage-qc", tags=["首页质控V2"])

ALLOWED_ROLES = frozenset({"admin", "super_admin", "qc_manager", "coder"})
EXPORT_LIMIT = 5000
STALLED_AFTER = timedelta(minutes=10)
RESULT_ISSUE_FILTERS = ("fail", "hint", "data_gap", "clean")


async def require_frontpage_qc_user(current_user: Dict[str, Any] = Depends(require_product_activation)) -> Dict[str, Any]:
    roles = {str(role) for role in current_user.get("roles", [])}
    if not roles & ALLOWED_ROLES:
        raise HTTPException(403, "首页质控仅限质控管理员、编码员使用")
    return current_user


def _user_id(user: Dict[str, Any]) -> str:
    return str(user.get("id") or user.get("user_id") or user.get("username") or "").strip() or "anonymous"


def _cdm_session_factory():
    from app.database.connection import SessionLocal

    if SessionLocal is None:
        raise HTTPException(503, "数据库未配置")
    return SessionLocal


def get_frontpage_qc_store() -> FrontpageQcStore:
    from app.database.connection import DB_SCHEMA_MODE

    return FrontpageQcStore(_cdm_session_factory(), "qc" if str(DB_SCHEMA_MODE).lower() == "split" else None)


def get_record_repository():
    from app.services.qc_workspace.record_repository import RecordRepository

    return RecordRepository(session_factory=_cdm_session_factory())


def _unavailable(exc: Exception) -> HTTPException:
    return HTTPException(503, str(exc) or "首页质控存储不可用")


def _ok(request: Request, data: Any, message: str = "成功") -> Dict[str, Any]:
    return success_response(data=data, message=message, trace_id=get_trace_id(request))


def _record_key(item: Dict[str, Any]) -> str:
    return FrontpageRef(
        str(item.get("institute_id") or ""),
        str(item.get("patient_id") or ""),
        str(item.get("visit_id") or item.get("record_id") or ""),
    ).as_key()


def _record_public(item: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "institute_id": item.get("institute_id") or "",
        "patient_id": item.get("patient_id") or "",
        "visit_id": item.get("visit_id") or item.get("record_id") or "",
        "record_key": _record_key(item),
        "patient_name": item.get("patient_name") or "",
        "inpat_no": item.get("inpat_no") or "",
        "mr_no": item.get("mr_no") or "",
        "department": item.get("department") or "",
        "doctor": item.get("doctor") or "",
        "discharge_date": item.get("discharge_date") or "",
    }


def _collect(repository, *, department: str = "", start_date: str = "", end_date: str = "", keyword: str = "", refs=None) -> List[Dict[str, Any]]:
    return repository.collect_records(
        scope="final",
        department=department or None,
        doctor=None,
        date_field="discharge",
        start_date=start_date or None,
        end_date=end_date or None,
        keyword=keyword or None,
        record_refs=refs,
    )


def _settle_stalled(store: FrontpageQcStore, run: Dict[str, Any]) -> Dict[str, Any]:
    """服务重启或线程异常退出时，任务会停在 running；超时后落为失败，前端才能停止轮询。"""
    if run["status"] not in RUN_ACTIVE_STATUSES or not run.get("updated_at"):
        return run
    updated = datetime.fromisoformat(run["updated_at"])
    if datetime.now(timezone.utc) - updated < STALLED_AFTER:
        return run
    store.update_run(
        run["id"],
        status="failed",
        error_message="任务中断（服务重启或执行异常），请重新发起",
        finished_at=datetime.now(timezone.utc),
    )
    return store.get_run(run["id"])


# ---------------- 规则目录 ----------------


@router.get("/rules")
async def list_rules(request: Request, _user: Dict[str, Any] = Depends(require_frontpage_qc_user)):
    items = [
        {
            "rule_id": rule.rule_id,
            "name": rule.name,
            "group": rule.group,
            "group_label": GROUP_LABELS[rule.group],
            "section": rule.section,
            "section_label": SECTION_LABELS[rule.section],
            "severity": rule.severity.value,
            "severity_label": SEVERITY_LABELS[rule.severity.value],
            "score_item": rule.score_item,
            "score_item_label": SCORE_ITEMS[rule.score_item].label if rule.score_item else "",
            "points": SCORE_ITEMS[rule.score_item].points if rule.score_item else 0,
            "basis": rule.basis,
            "problem": rule.problem,
            "condition": rule.condition,
            "enabled": rule.enabled,
            "disabled_reason": rule.disabled_reason,
        }
        for rule in RULES
    ]
    return _ok(
        request,
        {
            "ruleset_version": RULESET_VERSION,
            "items": items,
            "section_points": SECTION_POINTS,
            "grades": {
                "excellent": {"label": GRADE_LABELS["excellent"], "min": GRADE_EXCELLENT},
                "qualified": {"label": GRADE_LABELS["qualified"], "min": GRADE_QUALIFIED},
                "unqualified": {"label": GRADE_LABELS["unqualified"], "min": 0},
            },
            "source_gap_fields": sorted(SOURCE_GAP_FIELDS),
        },
    )


# ---------------- 批量任务 ----------------


class RefIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    institute_id: str = Field(min_length=1, max_length=128)
    patient_id: str = Field(min_length=1, max_length=128)
    visit_id: str = Field(min_length=1, max_length=128)


class RunCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    record_refs: Optional[List[RefIn]] = Field(default=None, max_length=MAX_RECORDS_PER_RUN)
    department: str = Field(default="", max_length=100)
    start_date: str = Field(default="", max_length=10)
    end_date: str = Field(default="", max_length=10)
    keyword: str = Field(default="", max_length=100)


@router.post("/runs")
async def create_run(
    request: Request,
    payload: RunCreate,
    user: Dict[str, Any] = Depends(require_frontpage_qc_user),
    store: FrontpageQcStore = Depends(get_frontpage_qc_store),
    repository=Depends(get_record_repository),
):
    uid = _user_id(user)
    try:
        active = [_settle_stalled(store, run) for run in store.list_runs(created_by=uid, statuses=RUN_ACTIVE_STATUSES, limit=5)]
        active = [run for run in active if run["status"] in RUN_ACTIVE_STATUSES]
        if active:
            raise HTTPException(409, detail={"message": "已有进行中的首页质控任务，请等待完成或取消后再发起", "run": active[0]})

        if payload.record_refs:
            refs = [CaseRef(r.institute_id, r.patient_id, r.visit_id) for r in payload.record_refs]
            records = _collect(repository, refs=refs)
            found = {_record_key(item) for item in records}
            # 不在病历池出院范围内的显式病历也照常质控（任务里会如实报告是否有首页）
            records += [
                {"institute_id": r.institute_id, "patient_id": r.patient_id, "visit_id": r.visit_id}
                for r in payload.record_refs
                if FrontpageRef(r.institute_id, r.patient_id, r.visit_id).as_key() not in found
            ]
            filters: Dict[str, Any] = {"mode": "selected", "count": len(payload.record_refs)}
        else:
            records = _collect(
                repository,
                department=payload.department,
                start_date=payload.start_date,
                end_date=payload.end_date,
                keyword=payload.keyword,
            )
            filters = {
                "mode": "filtered",
                "department": payload.department,
                "start_date": payload.start_date,
                "end_date": payload.end_date,
                "keyword": payload.keyword,
            }
        refs = refs_from_records(records)
        if not refs:
            raise HTTPException(422, "当前条件下没有可质控的出院病历")
        if len(refs) > MAX_RECORDS_PER_RUN:
            raise HTTPException(422, f"当前条件下有 {len(refs)} 份病历，单次最多 {MAX_RECORDS_PER_RUN} 份，请缩小范围分批执行")
        meta = {
            _record_key(item): {"department": item.get("department") or "", "discharge_date": item.get("discharge_date") or ""}
            for item in records
        }
        run = store.create_run(created_by=uid, refs=refs, filters=filters, ruleset_version=RULESET_VERSION)
    except FrontpageQcStoreUnavailable as exc:
        raise _unavailable(exc) from exc

    submit_detached_task(
        "frontpage_qc_v2_run",
        run_frontpage_qc_job,
        run["id"],
        store=store,
        cdm_session_factory=_cdm_session_factory(),
        record_meta=meta,
    )
    return _ok(request, run, "首页质控任务已创建")


@router.get("/runs")
async def list_runs(
    request: Request,
    active: bool = Query(False),
    user: Dict[str, Any] = Depends(require_frontpage_qc_user),
    store: FrontpageQcStore = Depends(get_frontpage_qc_store),
):
    try:
        runs = store.list_runs(created_by=_user_id(user), statuses=RUN_ACTIVE_STATUSES if active else (), limit=20)
        runs = [_settle_stalled(store, run) for run in runs]
    except FrontpageQcStoreUnavailable as exc:
        raise _unavailable(exc) from exc
    if active:
        runs = [run for run in runs if run["status"] in RUN_ACTIVE_STATUSES]
    return _ok(request, {"items": runs})


@router.get("/runs/{run_id}")
async def get_run(
    request: Request,
    run_id: str,
    _user: Dict[str, Any] = Depends(require_frontpage_qc_user),
    store: FrontpageQcStore = Depends(get_frontpage_qc_store),
):
    try:
        return _ok(request, _settle_stalled(store, store.get_run(run_id)))
    except FrontpageQcNotFound as exc:
        raise HTTPException(404, str(exc)) from exc
    except FrontpageQcStoreUnavailable as exc:
        raise _unavailable(exc) from exc


@router.post("/runs/{run_id}/cancel")
async def cancel_run(
    request: Request,
    run_id: str,
    user: Dict[str, Any] = Depends(require_frontpage_qc_user),
    store: FrontpageQcStore = Depends(get_frontpage_qc_store),
):
    try:
        run = store.get_run(run_id)
        if run["created_by"] != _user_id(user) and not {"admin", "super_admin"} & set(user.get("roles", [])):
            raise HTTPException(403, "只能取消自己发起的任务")
        return _ok(request, store.request_cancel(run_id), "已请求取消")
    except FrontpageQcNotFound as exc:
        raise HTTPException(404, str(exc)) from exc
    except FrontpageQcStoreUnavailable as exc:
        raise _unavailable(exc) from exc


# ---------------- 结果 ----------------


@router.get("/filters")
async def get_filters(
    request: Request,
    _user: Dict[str, Any] = Depends(require_frontpage_qc_user),
    repository=Depends(get_record_repository),
):
    filters = repository.get_record_filters(scope="final", department=None)
    return _ok(request, {"departments": filters.get("departments", []), "date_bounds": filters.get("date_bounds", {})})


@router.get("/records")
async def list_records(
    request: Request,
    department: str = Query("", max_length=100),
    start_date: str = Query("", max_length=10),
    end_date: str = Query("", max_length=10),
    keyword: str = Query("", max_length=100),
    grade: Literal["", "excellent", "qualified", "unqualified"] = Query(""),
    issue: Literal["", "fail", "hint", "data_gap", "clean", "unchecked"] = Query(""),
    page: int = Query(1, ge=1),
    page_size: int = Query(15, ge=1, le=100),
    _user: Dict[str, Any] = Depends(require_frontpage_qc_user),
    store: FrontpageQcStore = Depends(get_frontpage_qc_store),
    repository=Depends(get_record_repository),
):
    try:
        if grade or issue in RESULT_ISSUE_FILTERS:
            keys = None
            info: Dict[str, Dict[str, Any]] = {}
            if keyword:
                matched = _collect(repository, department=department, start_date=start_date, end_date=end_date, keyword=keyword)
                info = {_record_key(item): _record_public(item) for item in matched}
                keys = list(info)
            results, total = store.query_latest(
                department=department,
                start_date=start_date,
                end_date=end_date,
                grade=grade,
                issue=issue if issue in RESULT_ISSUE_FILTERS else "",
                record_keys=keys,
                page=page,
                page_size=page_size,
            )
            missing = [r for r in results if r["record_key"] not in info]
            if missing:
                hydrated = _collect(repository, refs=[CaseRef(r["institute_id"], r["patient_id"], r["visit_id"]) for r in missing])
                info.update({_record_key(item): _record_public(item) for item in hydrated})
            items = [
                {**(info.get(r["record_key"]) or {k: r[k] for k in ("institute_id", "patient_id", "visit_id", "record_key", "department", "discharge_date")}), "result": r}
                for r in results
            ]
        elif issue == "unchecked":
            records = _collect(repository, department=department, start_date=start_date, end_date=end_date, keyword=keyword)
            latest = store.latest_by_keys([_record_key(item) for item in records])
            pending = [item for item in records if _record_key(item) not in latest]
            total = len(pending)
            window = pending[(page - 1) * page_size: page * page_size]
            items = [{**_record_public(item), "result": None} for item in window]
        else:
            listing = repository.list_records(
                scope="final",
                department=department or None,
                doctor=None,
                date_field="discharge",
                start_date=start_date or None,
                end_date=end_date or None,
                keyword=keyword or None,
                page=page,
                page_size=page_size,
            )
            latest = store.latest_by_keys([_record_key(item) for item in listing.items])
            total = listing.total
            items = [{**_record_public(item), "result": latest.get(_record_key(item))} for item in listing.items]
    except FrontpageQcStoreUnavailable as exc:
        raise _unavailable(exc) from exc
    return _ok(request, {"items": items, "total": total, "page": page, "page_size": page_size})


@router.get("/record")
async def get_record(
    request: Request,
    institute_id: str = Query(..., min_length=1, max_length=128),
    patient_id: str = Query(..., min_length=1, max_length=128),
    visit_id: str = Query(..., min_length=1, max_length=128),
    _user: Dict[str, Any] = Depends(require_frontpage_qc_user),
    store: FrontpageQcStore = Depends(get_frontpage_qc_store),
    repository=Depends(get_record_repository),
):
    ref = FrontpageRef(institute_id, patient_id, visit_id)
    session_factory = _cdm_session_factory()
    with session_factory() as session:
        raw = load_frontpage_raw(session, ref)
    if raw is None:
        raise HTTPException(404, "未找到病案首页")
    doc = build_frontpage_doc(raw)
    try:
        result = store.latest_detail(ref)
    except FrontpageQcStoreUnavailable as exc:
        raise _unavailable(exc) from exc
    records = _collect(repository, refs=[CaseRef(*ref.__dict__.values())])
    record = _record_public(records[0]) if records else _record_public(ref.__dict__)
    stale = bool(result) and (
        result["input_fingerprint"] != input_fingerprint(doc) or result["ruleset_version"] != RULESET_VERSION
    )
    return _ok(request, {"record": record, "result": result, "stale": stale, "frontpage": doc.as_display()})


class ReviewIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    status: Literal["pending", "confirmed", "false_alarm"]
    note: str = Field(default="", max_length=500)


@router.post("/findings/{finding_id}/review")
async def review_finding(
    request: Request,
    finding_id: str,
    payload: ReviewIn,
    user: Dict[str, Any] = Depends(require_frontpage_qc_user),
    store: FrontpageQcStore = Depends(get_frontpage_qc_store),
):
    if payload.status == "false_alarm" and not payload.note.strip():
        raise HTTPException(422, "标记误报时请填写原因")
    try:
        finding = store.review_finding(finding_id, status=payload.status, note=payload.note.strip(), reviewer=_user_id(user))
    except FrontpageQcNotFound as exc:
        raise HTTPException(404, str(exc)) from exc
    except FrontpageQcStoreUnavailable as exc:
        raise _unavailable(exc) from exc
    return _ok(request, finding, "复核已保存")


@router.get("/analytics")
async def analytics(
    request: Request,
    department: str = Query("", max_length=100),
    start_date: str = Query("", max_length=10),
    end_date: str = Query("", max_length=10),
    _user: Dict[str, Any] = Depends(require_frontpage_qc_user),
    store: FrontpageQcStore = Depends(get_frontpage_qc_store),
):
    try:
        rows = store.latest_rows_for_analytics(department=department, start_date=start_date, end_date=end_date)
    except FrontpageQcStoreUnavailable as exc:
        raise _unavailable(exc) from exc
    return _ok(request, build_analytics(rows))


class ExportIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    record_refs: Optional[List[RefIn]] = Field(default=None, max_length=EXPORT_LIMIT)
    department: str = Field(default="", max_length=100)
    start_date: str = Field(default="", max_length=10)
    end_date: str = Field(default="", max_length=10)
    keyword: str = Field(default="", max_length=100)
    grade: Literal["", "excellent", "qualified", "unqualified"] = ""
    issue: Literal["", "fail", "hint", "data_gap", "clean"] = ""


@router.post("/records/export")
async def export_records(
    payload: ExportIn,
    _user: Dict[str, Any] = Depends(require_frontpage_qc_user),
    store: FrontpageQcStore = Depends(get_frontpage_qc_store),
    repository=Depends(get_record_repository),
):
    try:
        if payload.record_refs:
            refs = [CaseRef(r.institute_id, r.patient_id, r.visit_id) for r in payload.record_refs]
            records = _collect(repository, refs=refs)
            keys = [FrontpageRef(r.institute_id, r.patient_id, r.visit_id).as_key() for r in payload.record_refs]
            summary = f"所选 {len(keys)} 份病历"
        else:
            records = _collect(
                repository,
                department=payload.department,
                start_date=payload.start_date,
                end_date=payload.end_date,
                keyword=payload.keyword,
            )
            keys = [_record_key(item) for item in records]
            parts = [payload.department or "全部科室"]
            if payload.start_date or payload.end_date:
                parts.append(f"出院 {payload.start_date or '不限'} 至 {payload.end_date or '不限'}")
            if payload.keyword:
                parts.append(f"关键词 {payload.keyword}")
            if payload.grade:
                parts.append(f"等级 {GRADE_LABELS[payload.grade]}")
            summary = "，".join(parts)
        results, total = store.query_latest(
            grade=payload.grade, issue=payload.issue, record_keys=keys, page=1, page_size=EXPORT_LIMIT
        )
        findings = store.latest_findings([r["id"] for r in results])
    except FrontpageQcStoreUnavailable as exc:
        raise _unavailable(exc) from exc
    if not results:
        raise HTTPException(422, "当前范围内没有已质控的首页，无法导出")
    info = {_record_key(item): _record_public(item) for item in records}
    content = build_export_workbook(filters_summary=summary, results=results, findings=findings, record_info=info)
    filename = f"首页质控结果_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx"
    return Response(
        content=content,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{quote(filename)}", "X-Export-Total": str(total)},
    )
