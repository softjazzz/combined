"""业务动作编排：服务端预览 → 用户确认 → 调用正式任务链 → 回读进度与前后保存结果。

模型只能生成预览；确认只来自用户按钮。任务状态由正式任务服务所有，本模块只搬运。
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import httpx
from fastapi import HTTPException
from pydantic import BaseModel, ConfigDict, Field
from starlette.concurrency import run_in_threadpool

from . import business_reads
from .business_action_store import PREVIEWED, REJECTED, SUBMITTED, SUBMITTING, UNKNOWN, BusinessActionStore
from .business_actions import (
    ActionConfirmation, ActionPreview, ActionRecordRef, ActionRequest, MaterialVersion,
    build_action_preview, validate_confirmation,
)
from .business_schemas import BusinessContext
from .business_store import owner_id

PREVIEW_MINUTES = 15
SPECIALIST_LIMIT = 20
TASK_PATH = "/api/v1/qc/sichuan/workspace/batch-jobs"
ACTION_LABELS = {"single_recheck": "单病例复检", "specialist_batch": "专项质控任务"}
STATUS_LABELS = {PREVIEWED: "待确认", SUBMITTING: "正在提交", SUBMITTED: "已创建正式任务", REJECTED: "正式任务服务拒绝创建", UNKNOWN: "提交结果未知"}
RESULT_LABELS = {"compliant": "合规", "non_compliant": "不合规", "data_gap": "资料不足", "not_applicable": "不适用",
                 "not_executed": "未执行", "needs_review": "待复核", "uncertain": "不确定", "technical_error": "技术错误"}


class PreviewRecheck(BaseModel):
    model_config = ConfigDict(extra="forbid")
    rule_ids: list[str] = Field(min_length=1, max_length=75)


class PreviewSpecialist(BaseModel):
    model_config = ConfigDict(extra="forbid")
    record_references: list[str] = Field(min_length=1, max_length=SPECIALIST_LIMIT)
    rule_ids: list[str] = Field(min_length=1, max_length=75)


def material_version(identity: dict) -> MaterialVersion:
    """读取病例级同步记录；无记录时如实标为未证实，不用全局同步状态替代。"""
    from app.database.connection import SessionLocal
    from app.database.models.sync import SyncVisitStatus
    ref = ActionRecordRef(**identity)
    if SessionLocal is None:
        return MaterialVersion(record_ref=ref, version="未提供病例级同步记录")
    with SessionLocal() as session:
        row = session.get(SyncVisitStatus, (identity["institute_id"], identity["patient_id"], identity["visit_id"]))
    if row is None:
        return MaterialVersion(record_ref=ref, version="未提供病例级同步记录")
    verified = row.sync_status == "SYNCED" and row.local_synced_at is not None and (
        row.mongo_update_time is None or row.local_synced_at >= row.mongo_update_time)
    return MaterialVersion(record_ref=ref, version=f"{row.sync_status}|{row.mongo_update_time}|{row.local_synced_at}",
                           synchronization_verified=verified, synchronization_failed=row.sync_status == "FAILED")


def record_care_phase(identity: dict) -> str | None:
    """按病历池同一口径判断在院/出院；两边都不在时不猜。"""
    from app.services.workstation.luxian_0609_result_analysis_service import _load_current_workstation_records
    for phase in ("discharged", "inpatient"):
        rows = _load_current_workstation_records(department=None, doctor=None, hospital_status=phase)
        if any(all(row.get(key) == identity[key] for key in identity) for row in rows):
            return phase
    return None


def saved_statuses(identity: dict, rule_ids: list[str]) -> dict:
    """记录预览时的保存结果，用于完成后并列展示；读取失败只标未取得。"""
    try:
        saved = business_reads.saved_record(identity)
    except HTTPException:
        return {"job_id": None, "statuses": {}}
    items = {(item.get("rule_id") or item.get("rule_code")): item.get("status") for item in saved.get("items", []) if isinstance(item, dict)}
    return {"job_id": saved.get("job_id"), "statuses": {rule: items.get(rule) for rule in rule_ids}}


def rule_titles(rule_ids) -> dict:
    from app.services.luxian_0609_rule_master import load_luxian_0609_rule_master
    catalog = {row.rule_id: row.title for row in load_luxian_0609_rule_master()}
    return {rule: catalog.get(rule, "目录未收录") for rule in rule_ids}


def _identities(metadata: dict, operation: str, record_references: list[str] | None) -> list[dict]:
    context = metadata["context"]
    if operation == "single_recheck" and context["view"] != "doctor":
        raise HTTPException(422, "单病例复检仅在医生当前病例会话中提供")
    if operation == "specialist_batch" and context["view"] != "manager":
        raise HTTPException(422, "专项任务仅在管理工作台提供")
    if operation == "single_recheck":
        return [{key: context[key] for key in ("institute_id", "patient_id", "visit_id")}]
    identities = []
    for reference in record_references or []:
        binding = metadata["references"].get(reference)
        if not binding or binding.get("kind") != "record":
            raise HTTPException(422, "专项任务只能选择本会话统计下钻或提醒中已出现的病例")
        identities.append(binding["identity"])
    return identities


def current_inputs(metadata, user, access, operation, identities):
    """每次预览和确认都从服务端重新读取：授权病例子集、材料版本、病例范围。"""
    context = BusinessContext.model_validate(metadata["context"])
    if operation == "single_recheck" and context.view != "doctor":
        raise HTTPException(422, "单病例复检仅在医生当前病例会话中提供")
    if operation == "specialist_batch" and context.view != "manager":
        raise HTTPException(422, "专项任务仅在管理工作台提供")
    authorized = []
    for identity in identities:
        try:
            business_reads.require_record(access, user, identity, context.view, context.department)
            authorized.append(ActionRecordRef(**identity))
        except HTTPException:
            continue
    if context.view == "doctor":
        # 医生上下文不带病例范围；由服务端按病历池口径确定，不由模型或前端提供。
        phase = record_care_phase(identities[0])
        context = context.model_copy(update={"care_phase": phase}) if phase else context
    return context, tuple(authorized), tuple(material_version(identity) for identity in identities)


def _sync_preview(metadata, user, access, operation, rule_ids, identities):
    context, authorized, materials = current_inputs(metadata, user, access, operation, identities)
    rules = [rule.strip().upper() for rule in rule_ids]
    now = datetime.now(timezone.utc)
    preview = build_action_preview(
        ActionRequest(operation=operation, record_refs=tuple(ActionRecordRef(**identity) for identity in identities), rule_ids=tuple(rules)),
        context=context, owner_id=owner_id(user), session_id=metadata["session_id"], authorized_record_refs=authorized,
        material_versions=materials, expires_at=now + timedelta(minutes=PREVIEW_MINUTES), now=now,
    )
    baseline = {json.dumps(identity, sort_keys=True): saved_statuses(identity, rules) for identity in identities} if preview.allowed else {}
    return preview, baseline, rule_titles(rules)


async def create_preview(store, action_store: BusinessActionStore, metadata, user, access, operation, rule_ids, record_references=None) -> dict:
    identities = _identities(metadata, operation, record_references)
    preview, baseline, titles = await run_in_threadpool(_sync_preview, metadata, user, access, operation, rule_ids, identities)
    action_id = str(uuid4())
    document = {"preview": preview.model_dump(mode="json"), "baseline": baseline, "titles": titles}
    await run_in_threadpool(action_store.create, action_id=action_id, owner_id=preview.owner_id, session_id=preview.session_id,
                            operation=operation, preview_json=json.dumps(document, ensure_ascii=False),
                            confirmation_hash=preview.confirmation_hash, expires_at=preview.expires_at)
    reference_id = f"action:{action_id}"
    store.bind(metadata["session_id"], user, reference_id, {"kind": "action", "action_id": action_id})
    row = await run_in_threadpool(action_store.get, action_id=action_id, owner_id=preview.owner_id, session_id=preview.session_id)
    return {"preview": {"action_id": action_id, "operation": operation, "allowed": preview.allowed,
                        "blocked_reasons": list(preview.blocked_reasons), "warnings": list(preview.warnings),
                        "record_count": len(preview.request.record_refs), "rule_ids": list(preview.request.rule_ids)},
            "references": [action_reference(row, None, None)]}


def _document(row) -> tuple[ActionPreview, dict]:
    document = json.loads(row["preview_json"])
    return ActionPreview.model_validate(document["preview"]), document


def action_reference(row: dict, job: dict | None, comparison: list | None) -> dict:
    preview, document = _document(row)
    titles = document.get("titles", {})
    lines = [f"操作：{ACTION_LABELS[preview.request.operation]}；状态：{STATUS_LABELS.get(row['status'], row['status'])}"]
    if preview.request.operation == "single_recheck":
        lines.append("病例：当前会话病例")
    else:
        lines.append(f"病例（{len(preview.request.record_refs)}份）：" + "、".join(ref.visit_id for ref in preview.request.record_refs))
    lines.append("规则：" + "；".join(f"{rule} {titles.get(rule, '')}" for rule in preview.request.rule_ids))
    if preview.formal_request is not None:
        lines.append(f"质控范围：{'出院终末' if preview.formal_request.scope == 'final' else '在院运行'}；规则集：{preview.formal_request.rule_set_key}")
    lines.extend(f"不能执行：{reason}" for reason in preview.blocked_reasons)
    lines.extend(f"提示：{warning}" for warning in preview.warnings)
    if row["status"] == PREVIEWED and preview.allowed:
        lines.append(f"确认有效期至 {preview.expires_at.astimezone(timezone(timedelta(hours=8))).strftime('%Y年%m月%d日 %H:%M')}（UTC+08:00）；需点击“确认执行”，助手不会自行执行。")
    if row.get("message"):
        lines.append(f"说明：{row['message']}")
    if job:
        lines.append(f"正式任务 {job.get('id')}：{job.get('status', '未提供状态')}；病例 {job.get('total_records', '未提供')}，成功 {job.get('success_count', '未提供')}，失败 {job.get('failed_count', '未提供')}")
        if job.get("error_message"):
            lines.append(f"任务错误：{job['error_message']}")
    for row_cmp in comparison or []:
        lines.append(f"{row_cmp['rule_id']}：复检前 {row_cmp['before']} → 复检后 {row_cmp['after']}")
    if comparison:
        lines.append("前后状态均为正式保存结果原值；助手未重新判定，问题关闭以业务流程为准。")
    lines.append("任务创建与执行由正式质控任务服务负责；停止对话不会取消已创建任务。")
    return {"id": f"action:{row['id']}", "kind": "action", "action_id": row["id"],
            "title": f"{ACTION_LABELS[preview.request.operation]} · {len(preview.request.rule_ids)}条规则",
            "status": row["status"], "allowed": preview.allowed, "confirmation_hash": preview.confirmation_hash if row["status"] == PREVIEWED else None,
            "expires_at": preview.expires_at.isoformat(), "job_id": row.get("job_id"),
            "locator": "操作预览与正式任务关联；结果以正式任务和保存结果为准", "text": "\n".join(lines)}


def _formal_body(preview: ActionPreview) -> dict:
    formal = preview.formal_request
    return {"rule_set_key": formal.rule_set_key, "rule_ids": list(formal.rule_ids), "scope": formal.scope,
            "record_refs": [ref.model_dump() for ref in formal.record_refs]}


async def confirm(store, action_store: BusinessActionStore, client: httpx.AsyncClient, metadata, user, access, action_id, confirmation: ActionConfirmation) -> dict:
    owner = owner_id(user)
    row = await run_in_threadpool(action_store.get, action_id=action_id, owner_id=owner, session_id=metadata["session_id"])
    if row["status"] != PREVIEWED:
        # 重复确认或并发确认：返回既有结果，不再提交。
        return await view(action_store, client, metadata, user, action_id)
    preview, _ = _document(row)
    # 用同一请求重新读取授权、目录、材料与病例范围；变化时要求重新预览。
    identities = [ref.model_dump() for ref in preview.request.record_refs]
    context, authorized, materials = await run_in_threadpool(current_inputs, metadata, user, access, preview.request.operation, identities)
    try:
        formal = validate_confirmation(preview, confirmation, owner_id=owner, session_id=metadata["session_id"],
                                       context=context, authorized_record_refs=authorized,
                                       material_versions=materials, now=datetime.now(timezone.utc))
    except ValueError as exc:
        raise HTTPException(409, f"{exc}；本次未提交任务") from exc
    if not await run_in_threadpool(action_store.claim, action_id=action_id, owner_id=owner, session_id=metadata["session_id"]):
        return await view(action_store, client, metadata, user, action_id)
    try:
        response = await client.post(TASK_PATH, json=_formal_body(preview.model_copy(update={"formal_request": formal})))
    except httpx.HTTPError:
        await run_in_threadpool(action_store.finish, action_id=action_id, status=UNKNOWN,
                                message="提交时连接中断，无法确认是否已创建任务；未自动重试，刷新时将按本人任务列表回查")
        return await view(action_store, client, metadata, user, action_id)
    if response.status_code in {500, 502, 504}:
        await run_in_threadpool(action_store.finish, action_id=action_id, status=UNKNOWN,
                                message=f"正式任务服务返回 HTTP {response.status_code}，无法确认是否已创建任务；未自动重试")
        return await view(action_store, client, metadata, user, action_id)
    if response.status_code >= 400:
        detail = _detail(response)
        await run_in_threadpool(action_store.finish, action_id=action_id, status=REJECTED,
                                message=f"正式任务服务拒绝创建（HTTP {response.status_code}）" + (f"：{detail}" if detail else ""))
        return await view(action_store, client, metadata, user, action_id)
    data = (response.json() or {}).get("data") or {}
    job_id = data.get("id") if isinstance(data, dict) else None
    if not isinstance(job_id, str) or not job_id:
        await run_in_threadpool(action_store.finish, action_id=action_id, status=UNKNOWN, message="正式任务服务未返回任务标识；未自动重试")
    else:
        message = "正式任务服务复用了同范围排队或运行中的任务" if data.get("idempotency_reused") else None
        await run_in_threadpool(action_store.finish, action_id=action_id, status=SUBMITTED, job_id=job_id, message=message)
    return await view(action_store, client, metadata, user, action_id)


def _detail(response) -> str:
    try:
        detail = response.json().get("detail")
    except ValueError:
        return ""
    return detail if isinstance(detail, str) and len(detail) <= 200 else ""


async def _read_job(client, job_id: str) -> dict | None:
    try:
        response = await client.get(f"{TASK_PATH}/{job_id}")
    except httpx.HTTPError:
        return None
    if response.status_code >= 400:
        return None
    data = (response.json() or {}).get("data")
    if not isinstance(data, dict):
        return None
    return {key: data.get(key) for key in ("id", "status", "total_records", "success_count", "failed_count", "error_message", "finished_at")}


async def _reconcile(action_store, client, row, preview) -> None:
    """未知状态只按本人任务列表回查唯一匹配；无法唯一确认时保持未知，不重发。"""
    try:
        response = await client.get(TASK_PATH, params={"page": 1, "page_size": 20})
    except httpx.HTTPError:
        return
    if response.status_code >= 400:
        return
    items = ((response.json() or {}).get("data") or {}).get("items") or []
    refs = sorted(json.dumps(ref.model_dump(), sort_keys=True) for ref in preview.request.record_refs)
    rules = sorted(preview.request.rule_ids)
    claimed = row.get("claimed_at")
    matches = []
    for item in items:
        filters = item.get("filters") if isinstance(item.get("filters"), dict) else {}
        item_refs = sorted(json.dumps({k: r.get(k) for k in ("institute_id", "patient_id", "visit_id")}, sort_keys=True)
                           for r in filters.get("record_refs") or [] if isinstance(r, dict))
        if item_refs == refs and sorted(filters.get("selected_rule_ids") or []) == rules:
            created = item.get("created_at")
            try:
                created_at = datetime.fromisoformat(str(created).replace("Z", "+00:00"))
                created_at = created_at if created_at.tzinfo else created_at.replace(tzinfo=timezone.utc)
            except ValueError:
                continue
            if claimed is None or created_at >= _aware(claimed) - timedelta(seconds=60):
                matches.append(item.get("id"))
    if len(matches) == 1 and matches[0]:
        await run_in_threadpool(action_store.finish, action_id=row["id"], status=SUBMITTED, job_id=matches[0],
                                message="提交结果曾未知，已按本人任务列表唯一匹配到该任务", expected=UNKNOWN)


def _aware(value: datetime) -> datetime:
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


async def view(action_store: BusinessActionStore, client: httpx.AsyncClient, metadata, user, action_id) -> dict:
    owner = owner_id(user)
    row = await run_in_threadpool(action_store.get, action_id=action_id, owner_id=owner, session_id=metadata["session_id"])
    preview, document = _document(row)
    if row["status"] == UNKNOWN:
        await _reconcile(action_store, client, row, preview)
        row = await run_in_threadpool(action_store.get, action_id=action_id, owner_id=owner, session_id=metadata["session_id"])
    job = await _read_job(client, row["job_id"]) if row.get("job_id") else None
    comparison = None
    if job and job.get("status") in {"completed", "partial_success", "partial"} and preview.request.operation == "single_recheck":
        comparison = await run_in_threadpool(_comparison, preview, document, row["job_id"])
    return action_reference(row, job, comparison)


def _comparison(preview: ActionPreview, document: dict, job_id: str) -> list:
    identity = preview.request.record_refs[0].model_dump()
    before = document.get("baseline", {}).get(json.dumps(identity, sort_keys=True), {}).get("statuses", {})
    try:
        saved = business_reads.saved_record(identity)
    except HTTPException:
        return []
    if saved.get("job_id") != job_id:
        return [{"rule_id": rule, "before": RESULT_LABELS.get(before.get(rule), "未取得"), "after": "新任务结果尚未成为最新保存结果"}
                for rule in preview.request.rule_ids]
    after = {(item.get("rule_id") or item.get("rule_code")): item.get("status") for item in saved.get("items", []) if isinstance(item, dict)}
    return [{"rule_id": rule, "before": RESULT_LABELS.get(before.get(rule), "未取得"), "after": RESULT_LABELS.get(after.get(rule), "未取得")}
            for rule in preview.request.rule_ids]
