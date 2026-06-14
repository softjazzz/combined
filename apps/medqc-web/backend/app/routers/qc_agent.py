from __future__ import annotations

import logging
import uuid
from typing import Any, Dict, List

from fastapi import APIRouter, Depends, HTTPException, Request, status

from app.core.audit import audit_event
from app.core.security import get_current_user
from app.services.qc_agent.intent_router import get_intent_router_health
from app.services.qc_agent.orchestrator import run_intent
from app.services.qc_agent.schemas import (
    AgentToolRunResponse,
    AgentToolSpec,
    QCAgentChatRequest,
    QCAgentChatResponse,
    QCAgentHealthResponse,
    QCAgentSessionCreateRequest,
    QCAgentSessionResponse,
)
from app.services.qc_agent.session_store import QCAgentSessionStore
from app.services.qc_agent.tools import assert_no_sensitive_output, create_default_registry
from app.services.qc_agent.tool_registry import AgentToolRegistry


logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/qc-agent", tags=["qc-agent"])

_registry = create_default_registry()


def get_qc_agent_registry() -> AgentToolRegistry:
    return _registry


def _has_tool_run_role(current_user: Dict[str, Any]) -> bool:
    roles = {str(item) for item in current_user.get("roles", [])}
    role = str(current_user.get("role") or "")
    if role:
        roles.add(role)
    return bool(roles.intersection({"admin", "qc_manager"}))


def _session_store_or_503() -> QCAgentSessionStore:
    return QCAgentSessionStore()


@router.get("/tools", response_model=List[AgentToolSpec])
async def list_qc_agent_tools(
    _current_user: Dict[str, Any] = Depends(get_current_user),
    registry: AgentToolRegistry = Depends(get_qc_agent_registry),
) -> List[AgentToolSpec]:
    return registry.list_specs()


@router.get("/health", response_model=QCAgentHealthResponse)
async def get_qc_agent_health(
    _current_user: Dict[str, Any] = Depends(get_current_user),
) -> QCAgentHealthResponse:
    return QCAgentHealthResponse(**get_intent_router_health())


@router.post("/sessions", response_model=QCAgentSessionResponse)
async def create_qc_agent_session(
    payload: QCAgentSessionCreateRequest,
    current_user: Dict[str, Any] = Depends(get_current_user),
    store: QCAgentSessionStore = Depends(_session_store_or_503),
) -> QCAgentSessionResponse:
    return QCAgentSessionResponse(
        **store.create_session(
            current_user=current_user,
            session_id=payload.session_id,
            user_context=payload.user_context,
            title=payload.title,
        )
    )


@router.get("/sessions/{session_id}", response_model=QCAgentSessionResponse)
async def get_qc_agent_session(
    session_id: str,
    _current_user: Dict[str, Any] = Depends(get_current_user),
    store: QCAgentSessionStore = Depends(_session_store_or_503),
) -> QCAgentSessionResponse:
    return QCAgentSessionResponse(**store.get_session(session_id))


@router.post(
    "/tools/{tool_name}/run",
    response_model=AgentToolRunResponse,
    response_model_exclude_none=True,
)
async def run_qc_agent_tool(
    request: Request,
    tool_name: str,
    payload: Dict[str, Any],
    current_user: Dict[str, Any] = Depends(get_current_user),
    registry: AgentToolRegistry = Depends(get_qc_agent_registry),
) -> AgentToolRunResponse:
    if not _has_tool_run_role(current_user):
        audit_event(
            request,
            action="qc_agent.tool_run",
            resource=f"qc_agent.tool.{tool_name}",
            outcome="forbidden",
            details={"tool_name": tool_name},
            current_user=current_user,
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="单工具调试接口仅限管理员或质控管理员",
        )
    try:
        result = registry.execute(tool_name, payload)
        assert_no_sensitive_output(result.observation.public_data)
        result.observation.internal_data = None
        spec = registry.get(tool_name).spec if registry.get(tool_name) else None
        audit_event(
            request,
            action="qc_agent.tool_run",
            resource=f"qc_agent.tool.{tool_name}",
            outcome=result.observation.status,
            details={
                "tool_name": tool_name,
                "risk_level": spec.risk_level if spec else "",
                "run_id": result.run_id,
            },
            current_user=current_user,
        )
        return result
    except Exception as exc:
        audit_event(
            request,
            action="qc_agent.tool_run",
            resource=f"qc_agent.tool.{tool_name}",
            outcome="error",
            details={"tool_name": tool_name, "error": type(exc).__name__},
            current_user=current_user,
        )
        raise


@router.post(
    "/chat",
    response_model=QCAgentChatResponse,
)
async def run_qc_agent_chat(
    payload: QCAgentChatRequest,
    current_user: Dict[str, Any] = Depends(get_current_user),
    registry: AgentToolRegistry = Depends(get_qc_agent_registry),
) -> QCAgentChatResponse:
    if not payload.session_id:
        payload = payload.model_copy(update={"session_id": str(uuid.uuid4())})
    result = run_intent(payload, registry)
    assert_no_sensitive_output(result.model_dump())
    try:
        store = QCAgentSessionStore()
        store.record_chat(
            current_user=current_user,
            request_message=payload.message,
            response=result,
            user_context=payload.user_context,
        )
        if payload.confirm_selection:
            store.resolve_pending_confirmation(session_id=str(payload.session_id or ""))
    except Exception as exc:
        logger.warning("qc_agent session trace persist skipped: %s", exc)
    return result
