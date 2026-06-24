from __future__ import annotations

import pytest
from fastapi import HTTPException
from pydantic import BaseModel

from app.services.qc_agent.schemas import AgentToolObservation
from app.services.qc_agent.tool_registry import AgentToolRegistry


class DummyInput(BaseModel):
    keyword: str = ""


def _dummy_handler(payload: BaseModel) -> AgentToolObservation:
    return AgentToolObservation(
        tool_name="dummy",
        status="success",
        public_data={"keyword": getattr(payload, "keyword", "")},
        internal_data={"safe_ref": "ok"},
    )


def test_tool_registry_lists_registered_tool_spec():
    registry = AgentToolRegistry()
    registry.register(
        name="dummy",
        description="测试工具",
        input_model=DummyInput,
        handler=_dummy_handler,
        risk_level="low",
        writes_db=False,
        requires_confirmation=False,
        timeout_ms=100,
        max_records=5,
    )

    specs = registry.list_specs()

    assert len(specs) == 1
    spec = specs[0]
    assert spec.name == "dummy"
    assert spec.risk_level == "low"
    assert spec.writes_db is False
    assert spec.requires_confirmation is False
    assert spec.timeout_ms == 100
    assert spec.max_records == 5
    assert "properties" in spec.input_schema


def test_tool_registry_rejects_unknown_tool():
    registry = AgentToolRegistry()

    with pytest.raises(HTTPException) as exc_info:
        registry.execute("unknown", {})

    assert exc_info.value.status_code == 404
    assert "未注册工具" in str(exc_info.value.detail)


def test_tool_registry_rejects_write_tool():
    registry = AgentToolRegistry()
    registry.register(
        name="write_tool",
        description="写库工具",
        input_model=DummyInput,
        handler=_dummy_handler,
        writes_db=True,
    )

    with pytest.raises(HTTPException) as exc_info:
        registry.execute("write_tool", {})

    assert exc_info.value.status_code == 403
    assert "写库工具" in str(exc_info.value.detail)


def test_tool_registry_rejects_confirmation_tool():
    registry = AgentToolRegistry()
    registry.register(
        name="confirm_tool",
        description="需确认工具",
        input_model=DummyInput,
        handler=_dummy_handler,
        requires_confirmation=True,
    )

    with pytest.raises(HTTPException) as exc_info:
        registry.execute("confirm_tool", {})

    assert exc_info.value.status_code == 403
    assert "需确认工具" in str(exc_info.value.detail)


def test_tool_registry_validates_input_schema():
    class StrictInput(BaseModel):
        page_size: int

    registry = AgentToolRegistry()
    registry.register(
        name="strict",
        description="严格入参工具",
        input_model=StrictInput,
        handler=_dummy_handler,
    )

    with pytest.raises(HTTPException) as exc_info:
        registry.execute("strict", {"page_size": "not-int"})

    assert exc_info.value.status_code == 422

