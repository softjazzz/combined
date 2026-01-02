"""
Pydantic 数据模型
定义所有 API 的请求和响应结构
"""

from typing import List, Optional, Literal, Dict, Any
from datetime import datetime
from pydantic import BaseModel, Field


# ============================================
# 基础模型
# ============================================

class ICDCode(BaseModel):
    """ICD 编码"""
    code: str
    name: str
    category: Optional[str] = None
    notes: Optional[str] = None


class DiagnosisItem(BaseModel):
    """诊断项"""
    code: str
    name: str
    sequence: Optional[int] = None
    is_complication: bool = False


class ProcedureItem(BaseModel):
    """手术操作项"""
    code: str
    name: str
    sequence: Optional[int] = None
    procedure_date: Optional[datetime] = None


# ============================================
# 3.2.1 编码辅助 - 请求和响应
# ============================================

class CodingSuggestRequest(BaseModel):
    """ICD 编码推荐请求"""
    diagnosis_name: str = Field(..., description="诊断名称，例如：急性心肌梗死")
    context: Optional[str] = Field(None, description="病历上下文，用于提高推荐准确度")
    category: Literal['diagnosis', 'procedure'] = Field(..., description="编码类型：diagnosis=诊断, procedure=手术操作")


class ICDSuggestion(BaseModel):
    """ICD 编码推荐结果"""
    code: str = Field(..., description="ICD 编码")
    name: str = Field(..., description="ICD 名称")
    confidence: float = Field(..., ge=0.0, le=1.0, description="置信度 0-1")
    note: Optional[str] = Field(None, description="推荐说明")


class CodingSuggestResponse(BaseModel):
    """ICD 编码推荐响应"""
    candidates: List[ICDSuggestion] = Field(..., description="推荐的编码列表，按置信度降序")
    total: int = Field(..., description="推荐结果总数")


class CodingValidateRequest(BaseModel):
    """编码校验请求"""
    admission_id: str = Field(..., description="住院ID")
    primary_diagnosis: DiagnosisItem = Field(..., description="主诊断")
    secondary_diagnoses: List[DiagnosisItem] = Field(default_factory=list, description="次诊断列表")
    procedures: List[ProcedureItem] = Field(default_factory=list, description="手术操作列表")


class ValidationWarning(BaseModel):
    """编码校验警告"""
    type: Literal['missing_diagnosis', 'procedure_missing', 'complication_marking', 'logic_conflict']
    message: str
    evidence: Optional[str] = None
    severity: Literal['info', 'warning', 'error'] = 'info'


class ValidationResult(BaseModel):
    """编码校验结果"""
    is_valid: bool = Field(..., description="编码是否有效")
    warnings: List[ValidationWarning] = Field(default_factory=list, description="警告列表")
    conflicts: List[str] = Field(default_factory=list, description="逻辑冲突列表")


class ICDSearchRequest(BaseModel):
    """ICD 编码搜索请求"""
    keyword: str = Field(..., min_length=1, description="搜索关键词")
    category: Literal['diagnosis', 'procedure'] = Field(..., description="编码类型")
    limit: int = Field(default=20, ge=1, le=100, description="返回结果数量")


class ICDSearchResponse(BaseModel):
    """ICD 编码搜索响应"""
    results: List[ICDCode]
    total: int


# ============================================
# 3.2.2 DRG 分组 - 请求和响应
# ============================================

class DRGPredictRequest(BaseModel):
    """DRG 入组预测请求"""
    admission_id: str = Field(..., description="住院ID")
    region: str = Field(default='sichuan', description="DRG 地区版本")


class DRGGroupingResult(BaseModel):
    """DRG 分组结果"""
    adrg_code: str = Field(..., description="ADRG 编码，例如：FB1")
    adrg_name: str = Field(..., description="ADRG 名称")
    drg_code: str = Field(..., description="DRG 编码，例如：FB19")
    drg_name: str = Field(..., description="DRG 名称")
    weight: float = Field(..., description="DRG 权重系数")
    baseline_payment: float = Field(..., description="基准支付金额（元）")
    expected_los: Optional[dict] = Field(None, description="预期住院日范围 {min: 10, max: 15}")
    confidence: float = Field(default=1.0, ge=0.0, le=1.0, description="分组置信度")
    risk_level: Literal['low', 'medium', 'high'] = Field(default='low', description="风险等级")
    grouping_logic: Optional[str] = Field(None, description="分组逻辑说明")


class DRGPredictionResponse(BaseModel):
    """DRG 入组预测响应"""
    data: DRGGroupingResult
    message: str = "分组成功"


class DRGGroupingHistoryItem(BaseModel):
    """DRG 分组历史记录"""
    grouping_id: int
    drg_code: str
    drg_name: str
    weight: float
    baseline_payment: float
    actual_cost: Optional[float] = None
    profit_margin: Optional[float] = None
    version: int
    is_latest: bool
    grouped_at: datetime


class DRGGroupingHistoryResponse(BaseModel):
    """DRG 分组历史响应"""
    history: List[DRGGroupingHistoryItem]
    total: int


# ============================================
# 3.2.3 DIP 分组 - 请求和响应
# ============================================

class DIPPredictRequest(BaseModel):
    """DIP 入组预测请求"""
    admission_id: Optional[str] = Field(None, description="住院ID")
    city_name: str = Field(..., description="城市名称")
    pdx_code: str = Field(..., description="主诊断编码")
    adx_code: Optional[str] = Field(None, description="次诊断编码（分号分隔）")
    proc_code: Optional[str] = Field(None, description="手术编码（分号分隔）")
    patient_gender: str = Field(..., description="性别 女/男")
    patient_age: int = Field(..., description="年龄")
    los: int = Field(..., description="住院天数")
    total_fee: float = Field(0, description="总费用")


class DIPGroupingResult(BaseModel):
    """DIP 分组结果"""
    dip_code: str = Field(..., description="DIP 编码")
    dip_name: str = Field(..., description="DIP 名称")
    dip_type: str = Field(..., description="DIP 类型 (如: 核心病种)")
    diag_code: Optional[str] = Field(None, description="诊断编码")
    proc_code: Optional[str] = Field(None, description="手术编码")
    grouping_path: Optional[str] = Field(None, description="分组路径/验证结果")


class DIPPredictionResponse(BaseModel):
    """DIP 入组预测响应"""
    data: DIPGroupingResult
    message: str = "分组成功"



# ============================================
# 3.3 事中监控 - 请求和响应
# ============================================

class CodingSuggestionItem(BaseModel):
    """编码优化建议"""
    admission_id: str
    suggestion_id: int
    suggestion_type: Literal['missing_diagnosis', 'procedure_missing', 'complication_marking', 'logic_conflict']
    diagnosis_code: Optional[str] = None
    diagnosis_name: Optional[str] = None
    message: str
    evidence: Optional[str] = None
    severity: Literal['info', 'warning', 'error']
    status: Literal['pending', 'accepted', 'rejected']
    created_at: datetime


class CodingSuggestionsResponse(BaseModel):
    """编码建议列表响应"""
    suggestions: List[CodingSuggestionItem]
    total: int


class HandleSuggestionRequest(BaseModel):
    """处理编码建议请求"""
    suggestion_id: int
    action: Literal['accept', 'reject']
    handled_by: str = Field(..., description="处理人ID")


class HandleSuggestionResponse(BaseModel):
    """处理编码建议响应"""
    success: bool
    message: str


class HandleAlertRequest(BaseModel):
    """处理 DRG 预警请求"""
    alert_id: int
    action: Literal['acknowledge', 'resolve']
    handled_by: str = Field(..., description="处理人ID")


class HandleAlertResponse(BaseModel):
    """处理 DRG 预警响应"""
    success: bool
    message: str


class DRGAlertItem(BaseModel):
    """DRG 预警项"""
    admission_id: str
    alert_id: int
    alert_type: Literal['cost_overrun', 'los_long', 'coding_abnormal', 'profit_loss']
    alert_level: Literal['info', 'warning', 'critical']
    message: str
    metric_value: Optional[float] = None
    threshold_value: Optional[float] = None
    status: Literal['pending', 'acknowledged', 'resolved']
    triggered_at: datetime


class DRGAlertsRequest(BaseModel):
    """DRG 预警查询请求"""
    admission_id: Optional[str] = None
    alert_level: Optional[Literal['info', 'warning', 'critical']] = None
    status: Optional[Literal['pending', 'acknowledged', 'resolved']] = None
    limit: int = Field(default=50, ge=1, le=200)


class DRGAlertsResponse(BaseModel):
    """DRG 预警响应"""
    alerts: List[DRGAlertItem]
    total: int


# ============================================
# 病案首页相关
# ============================================

class CaseFrontPageBase(BaseModel):
    """病案首页基础信息"""
    admission_id: str
    patient_id: str
    patient_name: str
    patient_age: int
    patient_gender: Literal['M', 'F']

    primary_diagnosis_code: str
    primary_diagnosis_name: str

    main_procedure_code: Optional[str] = None
    main_procedure_name: Optional[str] = None
    main_procedure_date: Optional[datetime] = None

    admission_route: Optional[str] = None
    discharge_status: Optional[str] = None
    total_hospital_days: Optional[int] = None
    total_cost: Optional[float] = None


class CaseFrontPageCreate(CaseFrontPageBase):
    """创建病案首页请求"""
    secondary_diagnoses: List[DiagnosisItem] = Field(default_factory=list)
    procedures: List[ProcedureItem] = Field(default_factory=list)


class CaseFrontPageDetail(CaseFrontPageBase):
    """病案首页详情"""
    front_page_id: int
    coding_status: Literal['draft', 'completed', 'reviewed']
    review_status: Literal['pending', 'approved', 'rejected']
    coder_id: Optional[str] = None
    reviewer_id: Optional[str] = None
    coding_started_at: Optional[datetime] = None
    coding_completed_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    # 关联数据
    secondary_diagnoses: List[DiagnosisItem] = Field(default_factory=list)
    procedures: List[ProcedureItem] = Field(default_factory=list)

    class Config:
        from_attributes = True


class CaseFrontPageListResponse(BaseModel):
    """病案首页列表响应"""
    data: List[CaseFrontPageDetail]
    total: int


# ============================================
# 通用响应
# ============================================

class SuccessResponse(BaseModel):
    """成功响应"""
    success: bool = True
    message: str
    data: Optional[dict] = None


class ErrorResponse(BaseModel):
    """错误响应"""
    success: bool = False
    error: str
    detail: Optional[str] = None

# ============================================
# 3.4 影子分组 - 请求和响应
# ============================================

class ShadowGroupingBaseline(BaseModel):
    """影子分组基准信息"""
    primary_diagnosis: str
    secondary_diagnoses: List[str]
    procedures: List[str] = []
    patient_age: int
    patient_gender: str
    total_hospital_days: Optional[int] = None


class SecondaryDiagnosisChange(BaseModel):
    """次诊断变更"""
    from_code: Optional[str] = None  # 如果是替换，指定原编码
    to_code: str  # 目标编码


class ShadowGroupingCandidate(BaseModel):
    """影子分组候选方案"""
    id: str = Field(..., description="建议ID")
    add_secondary_diagnoses: List[str] = Field(default_factory=list, description="新增次诊断")
    replace_secondary_diagnoses: List[SecondaryDiagnosisChange] = Field(default_factory=list, description="替换次诊断")
    add_procedures: List[str] = Field(default_factory=list, description="新增手术")
    eligible: bool = Field(True, description="是否符合试算条件")


class ShadowGroupingBatchRequest(BaseModel):
    """影子分组批处理请求"""
    request_id: str
    baseline: ShadowGroupingBaseline
    candidates: List[ShadowGroupingCandidate]
    options: Optional[dict] = Field(default_factory=dict, description="配置项: max_candidates, include_rw")


class ShadowGroupingResultData(BaseModel):
    """影子分组结果数据"""
    drg: str
    adrg: Optional[str] = None
    drg_name: Optional[str] = None
    rw: Optional[float] = None  # 可选，暂不强制要求


class ShadowGroupingResultItem(BaseModel):
    """单条影子分组结果"""
    id: str
    status: Literal['computed', 'skipped', 'error']
    with_candidate: Optional[ShadowGroupingResultData] = None
    drg_change_type: Literal['base_to_cc', 'cc_to_mcc', 'no_change', 'drg_changed', 'error']
    rw_delta: Optional[float] = None
    impact_description: Optional[str] = None
    notes: List[str] = Field(default_factory=list)
    error_message: Optional[str] = None


class ShadowGroupingBatchResponse(BaseModel):
    """影子分组批处理响应"""
    baseline: ShadowGroupingResultData
    results: List[ShadowGroupingResultItem]


# ============================================
# 3.5 编码完整性分析 (Layer A/B) - 模型定义
# ============================================

class Evidence(BaseModel):
    """证据片段"""
    source: str = Field(..., description="来源文档，如 admission_note")
    text: str = Field(..., description="原文片段")
    start: Optional[int] = None
    end: Optional[int] = None
    evidence_type: Literal['explicit_statement', 'lab_indicator', 'medication_indicator', 'procedure_indicator']
    strength: Literal['strong', 'medium', 'weak']


class ClinicalEntity(BaseModel):
    """临床实体"""
    text: str
    category: Literal['diagnosis', 'procedure', 'indicator']
    evidence: Evidence


class ExtractionResult(BaseModel):
    """Layer A 抽取结果"""
    explicit_diagnoses: List[ClinicalEntity] = []
    clinical_indicators: List[ClinicalEntity] = []
    procedure_mentions: List[ClinicalEntity] = []


class CodingGap(BaseModel):
    """编码差距/建议"""
    id: str
    category: Literal['diagnosis', 'procedure']
    subtype: Literal['missing_code', 'code_refinement', 'needs_doc_update']
    action: Literal['add_code', 'needs_doc_update', 'ignore']
    risk_level: Literal['low', 'medium', 'high']
    target_code: Optional[str] = None
    target_name: str
    confidence: float
    evidence: List[Evidence]
    justification_points: List[str]
    required_documentation: List[str] = []
    # 关联的影子分组结果 (可选)
    shadow_grouping: Optional[ShadowGroupingResultItem] = None


class CodingCompletenessResponse(BaseModel):
    """完整性分析响应"""
    structure_extraction: ExtractionResult
    suggestions: List[CodingGap]


class CodingCompletenessAnalysisRequest(BaseModel):
    """完整性分析请求"""
    medical_record: str = Field(..., description="病历文本(入院记录/病程记录/出院小结)")
    current_data: Dict[str, Any] = Field(..., description="当前已编码数据(主诊断/次诊断/手术)")


