"""MedQC 业务会话与 DSH 运行时桥接；保留既有助手兼容入口。"""
from __future__ import annotations

import os
from datetime import datetime
from typing import Literal
from urllib.parse import urlparse
from uuid import UUID

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import ValidationError
from starlette.concurrency import run_in_threadpool

from app.core.security import get_current_user
from app.services.qc_agent.business_schemas import BusinessChat, BusinessContext, BusinessSessionCreate, BusinessStop
from app.services.qc_agent.business_access import BusinessAccess, get_business_access
from app.services.qc_agent import business_reads, business_documents, business_followups
from app.services.qc_agent.business_store import BusinessSessionStore, get_business_store
from app.services.qc_agent.business_reports import ComposeReport
from app.services.qc_agent.business_tools import BusinessTools, SearchCodes, TrendStatistics, statistics_scope_text, statistics_text, tool_specs
from app.services.qc_agent import business_feedback
from app.services.qc_agent import business_action_flow, business_capabilities, business_charts, business_write_switch
from app.services.qc_agent.business_action_store import get_action_store
from app.services.qc_agent.business_actions import ActionConfirmation

router = APIRouter(prefix="/business", tags=["business-agent"])

_CONTRACT_ERRORS = {"string_too_long": "超过长度上限", "string_too_short": "不能为空", "too_long": "条目过多", "too_short": "条目不足",
                    "missing": "缺少必填项", "extra_forbidden": "不允许的字段", "list_type": "应为数组", "string_type": "应为文本",
                    "int_type": "应为整数", "literal_error": "取值不在允许范围", "string_pattern_mismatch": "格式不符合要求",
                    "less_than_equal": "超过上限", "greater_than_equal": "低于下限", "value_error": "取值不合法"}


def contract_errors(exc: ValidationError) -> str:
    """只给字段路径与错误类型，供模型改写参数；不回显参数值。"""
    parts = [".".join(str(part) for part in error["loc"]) + " " + _CONTRACT_ERRORS.get(error["type"], "不符合要求") for error in exc.errors()[:3]]
    return "；".join(parts) or "参数格式不符合要求"


@router.get("/access")
async def get_access(user: dict = Depends(get_current_user), access: BusinessAccess = Depends(get_business_access)):
    return access.visible_scope(user)


@router.get("/records/{visit_id}/latest-result")
async def read_record_result(visit_id: str, institute_id: str = Query(..., min_length=1), patient_id: str = Query(..., min_length=1), view: Literal["doctor", "manager"] = "doctor", department: str | None = None, user: dict = Depends(get_current_user), access: BusinessAccess = Depends(get_business_access)):
    identity = {"institute_id": institute_id, "patient_id": patient_id, "visit_id": visit_id}
    await run_in_threadpool(business_reads.require_record, access, user, identity, view, department)
    return {"data": await run_in_threadpool(business_reads.saved_record, identity)}


@router.get("/statistics")
async def read_statistics(institute_id: str, department: str, care_phase: Literal["inpatient", "discharged"], completed_from: datetime, completed_to: datetime, rule_id: str | None = None, result_status: str | None = None, page: int = Query(1, ge=1, le=100), user: dict = Depends(get_current_user), access: BusinessAccess = Depends(get_business_access)):
    access.require_context(user, BusinessContext(view="manager", institute_id=institute_id, department=department, care_phase=care_phase, completed_from=completed_from.isoformat(), completed_to=completed_to.isoformat()))
    try:
        data = await run_in_threadpool(business_reads.department_analysis, institute_id=institute_id, department=department, care_phase=care_phase, completed_from=completed_from, completed_to=completed_to, rule_id=rule_id, result_status=result_status, page=page)
    except ValueError as exc:
        raise HTTPException(422, "统计参数不符合正式接口口径") from exc
    return {"data": data}


def loopback_url(setting: str, fallback: str) -> str:
    value = os.getenv(setting, fallback).rstrip("/")
    parsed = urlparse(value)
    if parsed.scheme != "http" or parsed.hostname not in {"127.0.0.1", "localhost", "::1"} or parsed.username or parsed.password:
        raise HTTPException(503, "业务助手内部地址须为本机独立服务")
    return value


async def runtime_call(method: str, path: str, body: dict | None = None) -> dict:
    key = os.getenv("MEDQC_AGENT_RUNTIME_KEY", "")
    if not key:
        raise HTTPException(503, "智能业务助手运行时尚未配置")
    async with httpx.AsyncClient(timeout=65, trust_env=False) as client:
        try:
            response = await client.request(method, loopback_url("MEDQC_AGENT_RUNTIME_URL", "http://127.0.0.1:8013") + path, json=body, headers={"X-MedQC-Runtime-Key": key})
        except httpx.HTTPError as exc:
            raise HTTPException(503, "智能业务助手运行时连接失败") from exc
    if response.status_code >= 400:
        raise HTTPException(response.status_code, "助手运行未完成，请检查运行时状态")
    try:
        data = response.json()
    except ValueError as exc:
        raise HTTPException(503, "助手运行时未返回有效结果") from exc
    if not isinstance(data, dict):
        raise HTTPException(503, "助手运行时结果格式不完整")
    return data


@router.post("/sessions")
async def create_session(payload: BusinessSessionCreate, user: dict = Depends(get_current_user), store: BusinessSessionStore = Depends(get_business_store), access: BusinessAccess = Depends(get_business_access)):
    access.require_context(user, payload.context)
    # 先确认运行时可用，再创建仅含归属/上下文的本地元数据。
    await runtime_call("GET", "/health")
    metadata = store.create(user, payload.context)
    await runtime_call("POST", f"/sessions/{metadata['session_id']}", {"context": metadata["context"], "tools": tool_specs(metadata["context"]["view"])})
    return {"session_id": metadata["session_id"], "context": metadata["context"], "turns": []}


@router.get("/sessions/{session_id}")
async def restore_session(session_id: UUID, user: dict = Depends(get_current_user), store: BusinessSessionStore = Depends(get_business_store), access: BusinessAccess = Depends(get_business_access)):
    metadata = store.get(str(session_id), user)
    access.require_context(user, BusinessContext.model_validate(metadata["context"]))
    data = await runtime_call("POST", f"/sessions/{session_id}/restore", {"context": metadata["context"], "tools": tool_specs(metadata["context"]["view"])})
    return {"session_id": str(session_id), "context": metadata["context"], "turns": data["turns"]}


@router.get("/sessions/{session_id}/followups")
async def read_session_followups(session_id: UUID, kind: Literal["notifications", "remediations"], page: int = Query(1, ge=1, le=100), page_size: int = Query(5, ge=1, le=10), user: dict = Depends(get_current_user), store: BusinessSessionStore = Depends(get_business_store), access: BusinessAccess = Depends(get_business_access)):
    metadata = store.get(str(session_id), user)
    context = BusinessContext.model_validate(metadata["context"])
    access.require_context(user, context)
    return {"data": await run_in_threadpool(business_followups.read_followups, user=user, context=context, access=access, kind=kind, page=page, page_size=page_size)}


@router.get("/sessions/{session_id}/feedback")
async def read_session_feedback(session_id: UUID, reference_id: str = Query(..., min_length=1, max_length=200), user: dict = Depends(get_current_user), store: BusinessSessionStore = Depends(get_business_store), access: BusinessAccess = Depends(get_business_access), feedback_store=Depends(business_feedback.get_feedback_store)):
    metadata = store.get(str(session_id), user)
    target = await run_in_threadpool(business_feedback.resolve_target, metadata, user, access, reference_id)
    data = await run_in_threadpool(feedback_store.read, uid=metadata["owner_id"], session_id=str(session_id), reference_id=reference_id)
    return {"target": business_feedback.public_target(target), "data": data}


@router.post("/sessions/{session_id}/feedback")
async def submit_session_feedback(session_id: UUID, payload: business_feedback.FeedbackSubmit, user: dict = Depends(get_current_user), store: BusinessSessionStore = Depends(get_business_store), access: BusinessAccess = Depends(get_business_access), feedback_store=Depends(business_feedback.get_feedback_store)):
    business_write_switch.require_feedback_write()
    metadata = store.get(str(session_id), user)
    target = await run_in_threadpool(business_feedback.resolve_target, metadata, user, access, payload.reference_id)
    data = await run_in_threadpool(feedback_store.submit, uid=metadata["owner_id"], session_id=str(session_id), target=target, payload=payload)
    return {"data": data}


@router.post("/sessions/{session_id}/chat")
async def chat(session_id: UUID, payload: BusinessChat, request: Request, user: dict = Depends(get_current_user), store: BusinessSessionStore = Depends(get_business_store), access: BusinessAccess = Depends(get_business_access)):
    metadata = store.get(str(session_id), user)
    access.require_context(user, BusinessContext.model_validate(metadata["context"]))
    if payload.reference_id and payload.reference_id not in metadata["references"]:
        raise HTTPException(404, "所选来源不属于当前会话")
    return await runtime_call("POST", f"/sessions/{session_id}/chat", {
        "context": metadata["context"], "run_id": str(payload.run_id), "message": payload.message,
        "reference_id": payload.reference_id,
        "authorization": request.headers.get("authorization", ""),
        "backend_url": loopback_url("MEDQC_AGENT_BACKEND_URL", "http://127.0.0.1:8003"),
        "tools": tool_specs(metadata["context"]["view"]),
    })


@router.post("/sessions/{session_id}/stop")
async def stop(session_id: UUID, payload: BusinessStop, user: dict = Depends(get_current_user), store: BusinessSessionStore = Depends(get_business_store)):
    store.get(str(session_id), user)
    return await runtime_call("POST", f"/sessions/{session_id}/stop", {"run_id": str(payload.run_id)})


def api_client(request: Request) -> httpx.AsyncClient:
    return httpx.AsyncClient(base_url=loopback_url("MEDQC_AGENT_BACKEND_URL", "http://127.0.0.1:8003"), headers={"Authorization": request.headers.get("authorization", "")}, timeout=15, trust_env=False)


@router.post("/sessions/{session_id}/tools/{name}")
async def run_tool(session_id: UUID, name: str, arguments: dict, request: Request, user: dict = Depends(get_current_user), store: BusinessSessionStore = Depends(get_business_store), access: BusinessAccess = Depends(get_business_access)):
    metadata = store.get(str(session_id), user)
    access.require_context(user, BusinessContext.model_validate(metadata["context"]))
    # 动作存储只在预览工具中解析；只读工具不因写库未配置而失败。
    actions = request.app.dependency_overrides.get(get_action_store, get_action_store) if name.startswith("preview_") else None
    async with api_client(request) as client:
        try:
            return await BusinessTools(store, client, access=access, actions=actions() if actions else None).execute(name, arguments, metadata, user)
        except ValidationError as exc:
            raise HTTPException(422, "工具参数不符合当前业务合同：" + contract_errors(exc)) from exc


@router.get("/sessions/{session_id}/references/{reference_id:path}")
async def get_reference(session_id: UUID, reference_id: str, request: Request, user: dict = Depends(get_current_user), store: BusinessSessionStore = Depends(get_business_store), access: BusinessAccess = Depends(get_business_access)):
    metadata = store.get(str(session_id), user)
    access.require_context(user, BusinessContext.model_validate(metadata["context"]))
    binding = metadata["references"].get(reference_id)
    if binding:
        async with api_client(request) as client:
            tools = BusinessTools(store, client)
            if binding["kind"] == "saved_result":
                return (await tools.issue(metadata, reference_id))["references"][0]
            if binding["kind"] == "rule":
                return (await tools.execute("read_rule", {"rule_id": binding["rule_id"]}, metadata, user))["references"][0]
            if binding["kind"] == "report":
                try:
                    return await tools.report_reference(metadata, user, ComposeReport.model_validate(binding["arguments"]), reference_id)
                except HTTPException as exc:
                    if exc.status_code == 422:
                        raise HTTPException(409, "来源统计已更新，报告草稿中的数值不再与当前统计一致；请重新生成，本次未展示旧数值") from exc
                    raise
            if binding["kind"] == "codes":
                return (await tools.code_search(SearchCodes.model_validate(binding["arguments"]), reference_id))["references"][0]
            if binding["kind"] == "capabilities":
                return business_capabilities.capabilities(metadata["context"]["view"])["references"][0]
            if binding["kind"] == "action":
                actions = request.app.dependency_overrides.get(get_action_store, get_action_store)()
                return await business_action_flow.view(actions, client, metadata, user, binding["action_id"])
            if binding["kind"] == "trend":
                params = TrendStatistics.model_validate(binding["arguments"])
                return (await tools.trend_statistics(params, metadata, user, reference_id))["references"][0]
            if binding["kind"] == "draft":
                return await tools.draft_reference(metadata, binding["result_id"], binding["segments"], reference_id)
            if binding["kind"] == "rule_validation":
                return (await tools.execute("read_rule_validation", {"rule_id": binding["rule_id"]}, metadata, user))["references"][0]
            if binding["kind"] == "record":
                data = await tools.saved_results(metadata, user, reference_id)
                page = data.get("result_page")
                scope = f"当前显示第{page['page']}页{page['returned']}条，匹配{page['matched_total']}条、保存共{page['total']}条；其余页请继续查询。\n\n" if page else ""
                return {"id": reference_id, "kind": "evidence", "title": "病例保存结果", "text": scope + ("\n\n".join(f"{row['rule_id']} · {row['title']}\n{row.get('conclusion', '')}\n{row.get('suggestion', '')}" for row in data.get("references", [])) or "当前病例暂无可读取的保存结果")}
            if binding["kind"] == "statistics":
                data = await tools.read_api("/api/v1/qc-agent/business/statistics", binding["filters"])
                return {"id": reference_id, "kind": "statistics", "title": binding.get("title") or "正式统计口径与规则分布", "locator": "按原筛选条件刷新读取；数据可能较上一轮更新", "text": statistics_scope_text(binding["filters"]) + statistics_text(data),
                        **({"chart": chart} if (chart := business_charts.ranking_chart(data)) else {})}
    return await runtime_call("POST", f"/sessions/{session_id}/reference", {"reference_id": reference_id, "context": metadata["context"], "tools": tool_specs(metadata["context"]["view"])})


@router.post("/sessions/{session_id}/actions/{action_id}/confirm")
async def confirm_action(session_id: UUID, action_id: UUID, payload: ActionConfirmation, request: Request, user: dict = Depends(get_current_user), store: BusinessSessionStore = Depends(get_business_store), access: BusinessAccess = Depends(get_business_access), actions=Depends(get_action_store)):
    # 确认只来自用户按钮的独立请求；模型没有确认工具。写入开关关闭时即使已有预览也不提交。
    business_write_switch.require_task_write()
    metadata = store.get(str(session_id), user)
    access.require_context(user, BusinessContext.model_validate(metadata["context"]))
    async with api_client(request) as client:
        return await business_action_flow.confirm(store, actions, client, metadata, user, access, str(action_id), payload)


@router.get("/sessions/{session_id}/actions/{action_id}")
async def read_action(session_id: UUID, action_id: UUID, request: Request, user: dict = Depends(get_current_user), store: BusinessSessionStore = Depends(get_business_store), access: BusinessAccess = Depends(get_business_access), actions=Depends(get_action_store)):
    metadata = store.get(str(session_id), user)
    access.require_context(user, BusinessContext.model_validate(metadata["context"]))
    async with api_client(request) as client:
        return await business_action_flow.view(actions, client, metadata, user, str(action_id))


@router.get("/sessions/{session_id}/evidence-document")
async def get_evidence_document(session_id: UUID, request: Request, reference_id: str = Query(..., min_length=1, max_length=200), evidence_index: int = Query(..., ge=0, le=100), user: dict = Depends(get_current_user), store: BusinessSessionStore = Depends(get_business_store), access: BusinessAccess = Depends(get_business_access)):
    metadata = store.get(str(session_id), user)
    access.require_context(user, BusinessContext.model_validate(metadata["context"]))
    async with api_client(request) as client:
        # 先回查同一保存任务/问题，再由服务端选择其证据坐标；前端不提交文书 ID。
        issue = await BusinessTools(store, client).issue(metadata, reference_id)
    evidence = issue["evidence"]
    if evidence_index >= len(evidence) or not isinstance(evidence[evidence_index], dict):
        raise HTTPException(404, "该问题未提供所选证据")
    identity = metadata["references"][reference_id]["identity"]
    await run_in_threadpool(business_reads.require_record, access, user, identity, metadata["context"]["view"], metadata["context"].get("department"))
    return await run_in_threadpool(business_documents.read_evidence_document, identity, evidence[evidence_index])
