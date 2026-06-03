from __future__ import annotations

from typing import Any, Dict, List

from fastapi import APIRouter, Depends

from app.core.security import get_current_user
from app.services.qc_agent.orchestrator import run_intent
from app.services.qc_agent.schemas import AgentToolRunResponse, AgentToolSpec, QCAgentChatRequest, QCAgentChatResponse
from app.services.qc_agent.tools import assert_no_sensitive_output, create_default_registry
from app.services.qc_agent.tool_registry import AgentToolRegistry


router = APIRouter(prefix="/api/v1/qc-agent", tags=["qc-agent"])

_registry = create_default_registry()


def get_qc_agent_registry() -> AgentToolRegistry:
    return _registry


@router.get("/tools", response_model=List[AgentToolSpec])
async def list_qc_agent_tools(
    _current_user: Dict[str, Any] = Depends(get_current_user),
    registry: AgentToolRegistry = Depends(get_qc_agent_registry),
) -> List[AgentToolSpec]:
    return registry.list_specs()


@router.post(
    "/tools/{tool_name}/run",
    response_model=AgentToolRunResponse,
    response_model_exclude_none=True,
)
async def run_qc_agent_tool(
    tool_name: str,
    payload: Dict[str, Any],
    _current_user: Dict[str, Any] = Depends(get_current_user),
    registry: AgentToolRegistry = Depends(get_qc_agent_registry),
) -> AgentToolRunResponse:
    result = registry.execute(tool_name, payload)
    assert_no_sensitive_output(result.observation.public_data)
    result.observation.internal_data = None
    return result


@router.post(
    "/chat",
    response_model=QCAgentChatResponse,
    response_model_exclude_none=True,
)
async def run_qc_agent_chat(
    payload: QCAgentChatRequest,
    _current_user: Dict[str, Any] = Depends(get_current_user),
    registry: AgentToolRegistry = Depends(get_qc_agent_registry),
) -> QCAgentChatResponse:
    result = run_intent(payload, registry)
    assert_no_sensitive_output(result.model_dump())
    return result
