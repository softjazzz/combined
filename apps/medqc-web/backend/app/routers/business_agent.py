"""MedQC 业务会话与 DSH 运行时桥接；保留既有助手兼容入口。"""
from __future__ import annotations

import os
from urllib.parse import urlparse
from uuid import UUID

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import ValidationError

from app.core.security import get_current_user
from app.services.qc_agent.business_schemas import BusinessChat, BusinessSessionCreate, BusinessStop
from app.services.qc_agent.business_store import BusinessSessionStore, get_business_store
from app.services.qc_agent.business_tools import BusinessTools, statistics_text, tool_specs

router = APIRouter(prefix="/business", tags=["business-agent"])


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
async def create_session(payload: BusinessSessionCreate, user: dict = Depends(get_current_user), store: BusinessSessionStore = Depends(get_business_store)):
    # 先确认运行时可用，再创建仅含归属/上下文的本地元数据。
    await runtime_call("GET", "/health")
    metadata = store.create(user, payload.context)
    await runtime_call("POST", f"/sessions/{metadata['session_id']}", {"context": metadata["context"], "tools": tool_specs()})
    return {"session_id": metadata["session_id"], "context": metadata["context"], "turns": []}


@router.get("/sessions/{session_id}")
async def restore_session(session_id: UUID, user: dict = Depends(get_current_user), store: BusinessSessionStore = Depends(get_business_store)):
    metadata = store.get(str(session_id), user)
    data = await runtime_call("POST", f"/sessions/{session_id}/restore", {"context": metadata["context"], "tools": tool_specs()})
    return {"session_id": str(session_id), "context": metadata["context"], "turns": data["turns"]}


@router.post("/sessions/{session_id}/chat")
async def chat(session_id: UUID, payload: BusinessChat, request: Request, user: dict = Depends(get_current_user), store: BusinessSessionStore = Depends(get_business_store)):
    metadata = store.get(str(session_id), user)
    if payload.reference_id and payload.reference_id not in metadata["references"]:
        raise HTTPException(404, "所选来源不属于当前会话")
    return await runtime_call("POST", f"/sessions/{session_id}/chat", {
        "context": metadata["context"], "run_id": str(payload.run_id), "message": payload.message,
        "reference_id": payload.reference_id,
        "authorization": request.headers.get("authorization", ""),
        "backend_url": loopback_url("MEDQC_AGENT_BACKEND_URL", "http://127.0.0.1:8003"),
        "tools": tool_specs(),
    })


@router.post("/sessions/{session_id}/stop")
async def stop(session_id: UUID, payload: BusinessStop, user: dict = Depends(get_current_user), store: BusinessSessionStore = Depends(get_business_store)):
    store.get(str(session_id), user)
    return await runtime_call("POST", f"/sessions/{session_id}/stop", {"run_id": str(payload.run_id)})


def api_client(request: Request) -> httpx.AsyncClient:
    return httpx.AsyncClient(base_url=loopback_url("MEDQC_AGENT_BACKEND_URL", "http://127.0.0.1:8003"), headers={"Authorization": request.headers.get("authorization", "")}, timeout=15, trust_env=False)


@router.post("/sessions/{session_id}/tools/{name}")
async def run_tool(session_id: UUID, name: str, arguments: dict, request: Request, user: dict = Depends(get_current_user), store: BusinessSessionStore = Depends(get_business_store)):
    metadata = store.get(str(session_id), user)
    async with api_client(request) as client:
        try:
            return await BusinessTools(store, client).execute(name, arguments, metadata, user)
        except ValidationError as exc:
            raise HTTPException(422, "工具参数不符合当前业务合同") from exc


@router.get("/sessions/{session_id}/references/{reference_id:path}")
async def get_reference(session_id: UUID, reference_id: str, request: Request, user: dict = Depends(get_current_user), store: BusinessSessionStore = Depends(get_business_store)):
    metadata = store.get(str(session_id), user)
    binding = metadata["references"].get(reference_id)
    if binding:
        async with api_client(request) as client:
            tools = BusinessTools(store, client)
            if binding["kind"] == "saved_result":
                return (await tools.issue(metadata, reference_id))["references"][0]
            if binding["kind"] == "rule":
                return (await tools.execute("read_rule", {"rule_id": binding["rule_id"]}, metadata, user))["references"][0]
            if binding["kind"] == "record":
                data = await tools.saved_results(metadata, user, reference_id)
                return {"id": reference_id, "kind": "evidence", "title": "病例保存结果", "text": "\n\n".join(f"{row['rule_id']} · {row['title']}\n{row.get('conclusion', '')}\n{row.get('suggestion', '')}" for row in data.get("references", [])) or "当前病例暂无可读取的保存结果"}
            if binding["kind"] == "statistics":
                data = await tools.read_api("/api/v1/workstation/qc-result-analysis/luxian-0609", binding["filters"])
                return {"id": reference_id, "kind": "statistics", "title": "正式统计口径与规则分布", "locator": "按原筛选条件刷新读取；数据可能较上一轮更新", "text": "按质控完成时间，使用范围内每份病例最新 Canonical 结果。\n" + statistics_text(data)}
    return await runtime_call("POST", f"/sessions/{session_id}/reference", {"reference_id": reference_id, "context": metadata["context"], "tools": tool_specs()})
