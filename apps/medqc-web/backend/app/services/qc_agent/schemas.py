from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field


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


class QCAgentChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=2000)
    session_id: Optional[str] = None
    user_context: Optional[Dict[str, Any]] = None
    confirm_selection: Optional[Dict[str, Any]] = None
    dry_run: bool = False


class QCAgentParsedIntent(BaseModel):
    model_config = ConfigDict(extra="allow")

    task_type: Optional[str] = None
    capability: Optional[str] = None
    result_type: Optional[str] = None
    confidence: Optional[float] = None
    visit_id: str = ""
    patient_id: str = ""
    mr_no: str = ""
    patient_name: str = ""
    department: str = ""
    document_alias: Optional[str] = None
    document_type: Optional[str] = None
    qc_point_type: Optional[str] = None
    rule_ids: List[str] = Field(default_factory=list)
    source: Optional[str] = None
    icd_query: str = ""
    code_type: Optional[str] = None
    version: Optional[str] = None
    include_procedures: Optional[bool] = None
    pdx_code: str = ""
    adx_codes: List[str] = Field(default_factory=list)
    proc_codes: List[str] = Field(default_factory=list)
    primary_diagnosis_code: str = ""
    secondary_diagnosis_codes: List[str] = Field(default_factory=list)
    procedure_codes: List[str] = Field(default_factory=list)
    patient_age: Optional[int] = None
    patient_gender: Optional[str] = None
    los: Optional[int] = None
    total_fee: Optional[float] = None
    total_cost: Optional[float] = None
    intent_router: Optional[str] = None
    unsupported: bool = False


class QCAgentPlanStep(BaseModel):
    model_config = ConfigDict(extra="allow")

    tool_name: str = ""
    status: str = ""
    arguments: Dict[str, Any] = Field(default_factory=dict)
    summary: Dict[str, Any] = Field(default_factory=dict)
    elapsed_ms: Optional[int] = None
    error: Optional[str] = None


class QCAgentCard(BaseModel):
    model_config = ConfigDict(extra="allow")

    card_type: str
    title: str = ""
    summary: Dict[str, Any] = Field(default_factory=dict)
    items: List[Dict[str, Any]] = Field(default_factory=list)
    data: Dict[str, Any] = Field(default_factory=dict)


class QCAgentResultEnvelope(BaseModel):
    model_config = ConfigDict(extra="allow")

    result_type: str
    title: str = ""
    summary: Dict[str, Any] = Field(default_factory=dict)
    cards: List[QCAgentCard] = Field(default_factory=list)
    actions: List[Dict[str, Any]] = Field(default_factory=list)
    raw_kind: str = ""


class QCRulesResult(QCAgentResultEnvelope):
    result_type: Literal["qc_rules_catalog"] = "qc_rules_catalog"


class DocumentQCResult(QCAgentResultEnvelope):
    result_type: Literal["document_qc_report"] = "document_qc_report"


class ICDCandidatesResult(QCAgentResultEnvelope):
    result_type: Literal["icd_candidates"] = "icd_candidates"


class RecordICDSuggestionsResult(QCAgentResultEnvelope):
    result_type: Literal["record_icd_suggestions"] = "record_icd_suggestions"


class DIPGroupResult(QCAgentResultEnvelope):
    result_type: Literal["dip_grouping_result"] = "dip_grouping_result"


class DRGGroupResult(QCAgentResultEnvelope):
    result_type: Literal["drg_grouping_result"] = "drg_grouping_result"


class QCAgentHealthResponse(BaseModel):
    intent_router_enabled: bool
    endpoint_configured: bool
    api_key_configured: bool
    model: str = ""
    last_check_status: str = "unknown"
    last_error_summary: str = ""
    degraded_reason: str = ""
    can_chat_execute: bool = False


class QCAgentSessionCreateRequest(BaseModel):
    session_id: Optional[str] = None
    user_context: Optional[Dict[str, Any]] = None
    title: Optional[str] = None


class QCAgentSessionResponse(BaseModel):
    session_id: str
    status: str = "active"
    current_visit_id: str = ""
    current_patient_id: str = ""
    title: str = ""
    messages: List[Dict[str, Any]] = Field(default_factory=list)
    pending_confirmation: Optional[Dict[str, Any]] = None


class QCAgentChatResponse(BaseModel):
    status: Literal["completed", "needs_clarification", "needs_confirmation", "unsupported"]
    parsed_intent: QCAgentParsedIntent = Field(default_factory=QCAgentParsedIntent)
    plan: List[QCAgentPlanStep] = Field(default_factory=list)
    candidates: List[Dict[str, Any]] = Field(default_factory=list)
    result: Optional[QCAgentResultEnvelope] = None
    legacy_result: Optional[Dict[str, Any]] = None
    warnings: List[str] = Field(default_factory=list)
    run_id: str
    session_id: Optional[str] = None


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
    alias: Optional[Literal["ward_round", "discharge", "course", "consultation", "mdt"]] = None


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


class SearchICDCodesInput(BaseModel):
    query: str = Field(..., min_length=1, max_length=100)
    code_type: Literal["diagnosis", "procedure", "all"] = "all"
    version: Literal["insurance", "clinical"] = "insurance"
    limit: int = Field(default=20, ge=1, le=50)


class SuggestRecordICDCodesInput(BaseModel):
    visit_id: str = Field(..., min_length=1)
    patient_id: Optional[str] = None
    include_procedures: bool = True
    limit_per_item: int = Field(default=5, ge=1, le=20)


class PredictDIPGroupInput(BaseModel):
    city_name: str = Field(default="泸州市", min_length=1, max_length=50)
    pdx_code: str = Field(..., min_length=1, max_length=30)
    adx_codes: List[str] = Field(default_factory=list)
    proc_codes: List[str] = Field(default_factory=list)
    patient_gender: Optional[str] = None
    patient_age: Optional[int] = Field(default=None, ge=0, le=130)
    los: Optional[int] = Field(default=None, ge=0, le=1000)
    total_fee: Optional[float] = Field(default=None, ge=0)


class PredictDRGGroupInput(BaseModel):
    primary_diagnosis_code: str = Field(..., min_length=1, max_length=30)
    secondary_diagnosis_codes: List[str] = Field(default_factory=list)
    procedure_codes: List[str] = Field(default_factory=list)
    patient_age: Optional[int] = Field(default=None, ge=0, le=130)
    patient_gender: Optional[str] = None
    los: Optional[int] = Field(default=None, ge=0, le=1000)
    total_cost: Optional[float] = Field(default=None, ge=0)
    region: str = Field(default="四川省", max_length=50)


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
