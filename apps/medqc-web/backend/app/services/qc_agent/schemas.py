from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field


RiskLevel = Literal["low", "medium", "high"]


class AgentToolSpec(BaseModel):
    name: str
    description: str
    input_schema: Dict[str, Any]
    risk_level: RiskLevel = "low"
    writes_db: bool = False
    requires_confirmation: bool = False
    timeout_ms: int = Field(default=5000, ge=1)
    max_records: int = Field(default=20, ge=1)


class AgentToolCall(BaseModel):
    tool_name: str
    arguments: Dict[str, Any] = Field(default_factory=dict)


class AgentToolObservation(BaseModel):
    tool_name: str
    status: Literal["success", "error", "rejected"]
    public_data: Dict[str, Any] = Field(default_factory=dict)
    internal_data: Optional[Dict[str, Any]] = None
    error: Optional[str] = None


class AgentToolRunResponse(BaseModel):
    run_id: str
    tool_call: AgentToolCall
    observation: AgentToolObservation
    trace: List[Dict[str, Any]] = Field(default_factory=list)


class SearchRecordsInput(BaseModel):
    scope: Literal["all", "running", "final"] = "all"
    department: Optional[str] = None
    doctor: Optional[str] = None
    date_field: Literal["admission", "discharge"] = "discharge"
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    keyword: Optional[str] = None
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=50)


class RecordSummary(BaseModel):
    visit_id: str = ""
    patient_id: str = ""
    patient_name: str = ""
    department: str = ""
    doctor: str = ""
    admission_date: str = ""
    discharge_date: str = ""


class SearchRecordsPublicData(BaseModel):
    records: List[RecordSummary]
    total: int
    page: int
    page_size: int
    capped: bool = False

