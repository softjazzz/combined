from __future__ import annotations

import time
import uuid
from dataclasses import dataclass
from typing import Any, Callable, Dict, Iterable, Optional

from fastapi import HTTPException, status
from pydantic import BaseModel, ValidationError

from .schemas import AgentToolCall, AgentToolObservation, AgentToolRunResponse, AgentToolSpec


ToolHandler = Callable[[BaseModel], AgentToolObservation]


@dataclass(frozen=True)
class RegisteredTool:
    spec: AgentToolSpec
    input_model: type[BaseModel]
    handler: ToolHandler


def _model_schema(model: type[BaseModel]) -> Dict[str, Any]:
    schema_fn = getattr(model, "model_json_schema", None)
    if callable(schema_fn):
        return schema_fn()
    return model.schema()


class AgentToolRegistry:
    """受控 Agent 工具注册表，只允许白名单工具执行。"""

    def __init__(self) -> None:
        self._tools: Dict[str, RegisteredTool] = {}

    def register(
        self,
        *,
        name: str,
        description: str,
        input_model: type[BaseModel],
        handler: ToolHandler,
        risk_level: str = "low",
        writes_db: bool = False,
        requires_confirmation: bool = False,
        timeout_ms: int = 5000,
        max_records: int = 20,
    ) -> None:
        spec = AgentToolSpec(
            name=name,
            description=description,
            input_schema=_model_schema(input_model),
            risk_level=risk_level,  # type: ignore[arg-type]
            writes_db=writes_db,
            requires_confirmation=requires_confirmation,
            timeout_ms=timeout_ms,
            max_records=max_records,
        )
        self._tools[name] = RegisteredTool(spec=spec, input_model=input_model, handler=handler)

    def list_specs(self) -> list[AgentToolSpec]:
        return [tool.spec for tool in self._tools.values()]

    def get(self, name: str) -> Optional[RegisteredTool]:
        return self._tools.get(name)

    def execute(self, tool_name: str, arguments: Dict[str, Any]) -> AgentToolRunResponse:
        registered = self.get(tool_name)
        run_id = str(uuid.uuid4())
        call = AgentToolCall(tool_name=tool_name, arguments=arguments)
        started = time.time()

        if registered is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"未注册工具: {tool_name}",
            )

        spec = registered.spec
        if spec.writes_db:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"M1a 不允许执行写库工具: {tool_name}",
            )
        if spec.requires_confirmation:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"M1a 不允许执行需确认工具: {tool_name}",
            )

        try:
            payload = registered.input_model(**arguments)
        except ValidationError as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=exc.errors(),
            ) from exc

        observation = registered.handler(payload)
        elapsed_ms = int((time.time() - started) * 1000)
        trace = [
            {
                "step": "tool_call",
                "tool_name": tool_name,
                "status": observation.status,
                "elapsed_ms": elapsed_ms,
            }
        ]
        return AgentToolRunResponse(
            run_id=run_id,
            tool_call=call,
            observation=observation,
            trace=trace,
        )


def build_registry(tools: Iterable[RegisteredTool]) -> AgentToolRegistry:
    registry = AgentToolRegistry()
    for tool in tools:
        registry._tools[tool.spec.name] = tool
    return registry

