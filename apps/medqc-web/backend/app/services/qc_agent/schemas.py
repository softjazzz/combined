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


class GetRecordContextInput(BaseModel):
    visit_id: str = Field(..., min_length=1)
    patient_id: Optional[str] = None
    scene: Literal["running", "final", "frontpage", "coding", "settlement"] = "final"
    include_preview: bool = True


class RunFrontpageQCRuleScope(BaseModel):
    categories: Optional[List[Literal["required", "format", "logic", "consistency"]]] = None
    severities: Optional[List[Literal["error", "warning", "info"]]] = None


class RunFrontpageQCInput(BaseModel):
    visit_id: str = Field(..., min_length=1)
    patient_id: Optional[str] = None
    rule_scope: Optional[RunFrontpageQCRuleScope] = None
    include_passed: bool = False


class DocumentDateRange(BaseModel):
    start: Optional[str] = None
    end: Optional[str] = None


class DocumentScope(BaseModel):
    document_types: Optional[List[str]] = None
    keywords: Optional[List[str]] = None
    date_range: Optional[DocumentDateRange] = None
    max_documents: int = Field(default=10, ge=1, le=20)
    alias: Optional[Literal["ward_round", "discharge", "course", "consultation"]] = None


class SelectRecordDocumentsInput(BaseModel):
    visit_id: str = Field(..., min_length=1)
    patient_id: Optional[str] = None
    document_scope: DocumentScope = Field(default_factory=DocumentScope)


class DocumentQCScope(BaseModel):
    rule_ids: Optional[List[str]] = None
    rule_family: str = "document_general"
    include_evidence: bool = True
    include_passed: bool = False


class RunDocumentQCInput(BaseModel):
    visit_id: str = Field(..., min_length=1)
    patient_id: Optional[str] = None
    document_scope: DocumentScope = Field(default_factory=DocumentScope)
    qc_scope: DocumentQCScope = Field(default_factory=DocumentQCScope)
    document_alias: Optional[str] = None
    document_type: Optional[str] = None
    qc_point_type: Optional[str] = None
    rule_ids: Optional[List[str]] = None
    include_passed: Optional[bool] = None
    max_rules: int = Field(default=20, ge=1, le=50)


class ListQCRulesInput(BaseModel):
    document_alias: Optional[str] = None
    document_type: Optional[str] = None
    qc_point_type: Optional[str] = None
    source: Optional[str] = None
    severity: Optional[str] = None
    launch_tier: Optional[str] = None
    keyword: Optional[str] = None
    limit: int = Field(default=50, ge=1, le=200)


class ResolveRuleScopeInput(BaseModel):
    document_alias: Optional[str] = None
    document_type: Optional[str] = None
    qc_point_type: Optional[str] = None
    source: Optional[str] = None
    severity: Optional[str] = None
    launch_tier: Optional[str] = None
    keyword: Optional[str] = None
    limit: int = Field(default=50, ge=1, le=200)


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
