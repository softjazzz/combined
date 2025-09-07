# 审核模块数据模型
# 与现有三层质控引擎集成的审核功能数据模型

from pydantic import BaseModel, Field, validator
from typing import List, Optional, Dict, Any, Union
from datetime import datetime, date
from enum import Enum
import uuid

# 枚举类型定义
class AuditTaskType(str, Enum):
    ROUTINE = "routine"
    SPECIAL = "special"
    SPOT_CHECK = "spot_check"
    COMPLAINT_DRIVEN = "complaint_driven"

class AuditLevel(str, Enum):
    DEPARTMENT = "department"
    HOSPITAL = "hospital"
    EXPERT = "expert"

class AuditStatus(str, Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELLED = "cancelled"

class TaskItemStatus(str, Enum):
    PENDING = "pending"
    IN_REVIEW = "in_review"
    COMPLETED = "completed"
    APPEALED = "appealed"
    CANCELLED = "cancelled"

class RiskLevel(str, Enum):
    A = "A"  # 高风险
    B = "B"  # 中风险
    C = "C"  # 低风险

class DefectSeverity(str, Enum):
    CRITICAL = "critical"
    MAJOR = "major"
    MINOR = "minor"

class MessageType(str, Enum):
    QC_COMPLETED = "qc_completed"
    RECTIFICATION_REQUIRED = "rectification_required"
    AUDIT_RESULT = "audit_result"
    APPEAL_RESULT = "appeal_result"
    DEADLINE_REMINDER = "deadline_reminder"
    SYSTEM_ANNOUNCEMENT = "system_announcement"
    RECTIFICATION_SUBMITTED = "rectification_submitted"
    APPEAL_SUBMITTED = "appeal_submitted"
    TASK_ASSIGNED = "task_assigned"
    TASK_OVERDUE = "task_overdue"
    BATCH_COMPLETED = "batch_completed"
    EXPERT_CONSULTATION = "expert_consultation"

class MessagePriority(str, Enum):
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    URGENT = "urgent"

class SamplingMethod(str, Enum):
    RANDOM = "random"
    STRATIFIED = "stratified"
    SYSTEMATIC = "systematic"
    RISK_BASED = "risk_based"

# 基础数据模型
class AuditScope(BaseModel):
    departments: List[str]
    document_types: List[str]
    patient_types: Optional[List[str]] = None
    date_range: Optional[Dict[str, str]] = None
    include_discharged: Optional[bool] = True
    exclude_patterns: Optional[List[str]] = None

class StratificationRule(BaseModel):
    stratum_name: str
    criteria: Dict[str, Any]
    sample_ratio: float = Field(..., ge=0, le=1)
    min_sample_size: Optional[int] = 1
    max_sample_size: Optional[int] = None

class RiskBasedWeights(BaseModel):
    risk_A_weight: float = Field(0.6, ge=0, le=1)
    risk_B_weight: float = Field(0.3, ge=0, le=1)
    risk_C_weight: float = Field(0.1, ge=0, le=1)
    
    @validator('risk_C_weight')
    def validate_weights_sum(cls, v, values):
        total = v + values.get('risk_A_weight', 0) + values.get('risk_B_weight', 0)
        if abs(total - 1.0) > 0.01:
            raise ValueError('权重总和必须等于1.0')
        return v

class SamplingConfig(BaseModel):
    sampling_method: SamplingMethod
    total_sample_size: Optional[int] = None
    sampling_ratio: Optional[float] = Field(None, ge=0, le=1)
    stratification_rules: Optional[List[StratificationRule]] = None
    risk_based_weights: Optional[RiskBasedWeights] = None
    exclusion_criteria: Optional[List[str]] = None

class AssignedReviewer(BaseModel):
    user_id: str
    user_name: str
    role: str
    assigned_count: int = 0
    completed_count: int = 0
    assigned_at: datetime

# 审核任务相关模型
class QCAuditTaskBase(BaseModel):
    task_name: str = Field(..., min_length=1, max_length=200)
    task_type: AuditTaskType
    audit_level: AuditLevel
    audit_scope: AuditScope
    sampling_config: SamplingConfig
    planned_start_date: date
    planned_end_date: date
    description: Optional[str] = None
    priority: int = Field(5, ge=1, le=10)

class CreateAuditTaskRequest(QCAuditTaskBase):
    assigned_reviewers: List[str] = Field(..., min_items=1)

class QCAuditTask(QCAuditTaskBase):
    id: str
    task_code: str
    status: AuditStatus = AuditStatus.PENDING
    progress_percentage: float = Field(0, ge=0, le=100)
    actual_start_date: Optional[datetime] = None
    actual_end_date: Optional[datetime] = None
    created_by: str
    assigned_reviewers: List[AssignedReviewer]
    total_records: int = 0
    completed_records: int = 0
    defect_rate: Optional[float] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

# 审核任务明细模型
class QCAuditTaskItemBase(BaseModel):
    patient_id: str
    medical_record_id: str
    patient_name: str
    admission_date: date
    discharge_date: Optional[date] = None
    department_id: str
    department_name: str
    risk_level: RiskLevel
    complexity_score: int = Field(0, ge=0, le=100)

class QCAuditTaskItem(QCAuditTaskItemBase):
    id: str
    task_id: str
    audit_status: TaskItemStatus = TaskItemStatus.PENDING
    assigned_reviewer_id: Optional[str] = None
    overall_score: Optional[float] = None
    defect_count: int = 0
    has_critical_defects: bool = False
    assigned_at: Optional[datetime] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    reviewer_notes: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

# 审核结果模型
class QCAuditResultBase(BaseModel):
    audit_score: float = Field(..., ge=0, le=100)
    audit_conclusion: Optional[str] = None
    review_duration: Optional[int] = None  # 分钟

class CreateAuditResultRequest(QCAuditResultBase):
    defects: List[Dict[str, Any]] = []

class QCAuditResult(QCAuditResultBase):
    id: str
    task_item_id: str
    audit_level: AuditLevel
    reviewer_id: str
    reviewer_name: str
    status: str = "draft"
    is_final: bool = False
    submitted_at: Optional[datetime] = None
    approved_at: Optional[datetime] = None
    modified_by: Optional[str] = None
    modification_reason: Optional[str] = None
    original_score: Optional[float] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

# 缺陷模型
class QCDefectBase(BaseModel):
    defect_type: str
    defect_category: str
    severity: DefectSeverity
    title: str = Field(..., min_length=1, max_length=200)
    description: str
    location: Optional[str] = None
    evidence: Optional[str] = None
    rectification_requirement: Optional[str] = None
    rectification_suggestion: Optional[str] = None
    estimated_rectification_time: Optional[int] = None
    score_deduction: float = Field(0, ge=0)
    ai_assisted: bool = False
    ai_confidence: Optional[float] = Field(None, ge=0, le=100)

class QCDefect(QCDefectBase):
    id: str
    audit_result_id: str
    task_item_id: str
    status: str = "identified"
    identified_at: datetime
    rectification_deadline: Optional[datetime] = None
    resolved_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

# AI辅助相关模型
class AIDefectSuggestion(BaseModel):
    suggested_type: str
    suggested_category: str
    suggested_severity: DefectSeverity
    suggested_title: str
    suggested_description: str
    suggested_location: Optional[str] = None
    confidence: float = Field(..., ge=0, le=100)
    supporting_evidence: List[str] = []
    rectification_suggestions: List[str] = []

class DefectAnalysisContext(BaseModel):
    medical_record: Optional[Dict[str, Any]] = None
    audit_level: AuditLevel
    reviewer_expertise: List[str] = []
    historical_defects: Optional[List[QCDefect]] = None

# 批量操作模型
class BatchAuditRequest(BaseModel):
    task_id: str
    task_item_ids: List[str] = Field(..., min_items=1)
    audit_template: Optional[Dict[str, Any]] = None
    batch_notes: Optional[str] = None

class BatchAuditResult(BaseModel):
    total_processed: int
    successful_count: int
    failed_count: int
    errors: List[Dict[str, str]] = []
    processed_items: List[Dict[str, Any]] = []

# 消息通知模型
class MessageAction(BaseModel):
    id: str
    label: str
    type: str = Field(..., regex="^(primary|secondary|danger)$")
    action: str = Field(..., regex="^(navigate|api_call|modal|confirm)$")
    config: Dict[str, Any] = {}

class QCNotificationBase(BaseModel):
    type: MessageType
    priority: MessagePriority = MessagePriority.NORMAL
    recipient_id: str
    recipient_type: str = Field(..., regex="^(clinician|reviewer|admin)$")
    title: str = Field(..., min_length=1, max_length=200)
    content: str
    summary: Optional[str] = Field(None, max_length=500)
    related_data: Dict[str, Any] = {}
    actions: List[MessageAction] = []
    auto_expire: bool = False
    expires_at: Optional[datetime] = None

class QCNotification(QCNotificationBase):
    id: str
    status: str = "pending"
    sender_id: Optional[str] = None
    sender_name: Optional[str] = None
    sender_role: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    sent_at: Optional[datetime] = None
    delivered_at: Optional[datetime] = None
    read_at: Optional[datetime] = None
    processed_at: Optional[datetime] = None
    distribution_channel: Optional[str] = None
    delivery_attempts: int = 0
    last_attempt_at: Optional[datetime] = None

    class Config:
        from_attributes = True

# 请求和响应模型
class AuditTaskFilter(BaseModel):
    task_type: Optional[AuditTaskType] = None
    audit_level: Optional[AuditLevel] = None
    status: Optional[AuditStatus] = None
    assigned_reviewer: Optional[str] = None
    date_range: Optional[Dict[str, str]] = None
    search: Optional[str] = None

class AuditStatistics(BaseModel):
    total_tasks: int
    completed_tasks: int
    average_completion_time: float
    overall_defect_rate: float
    defects_by_severity: Dict[str, int]
    defects_by_category: Dict[str, int]
    reviewer_performance: List[Dict[str, Any]]

# 响应模型
class APIResponse(BaseModel):
    success: bool = True
    message: str = "操作成功"
    data: Optional[Any] = None
    errors: Optional[List[str]] = None

class PaginatedResponse(BaseModel):
    items: List[Any]
    total: int
    page: int = 1
    page_size: int = 20
    total_pages: int

    @validator('total_pages', always=True)
    def calculate_total_pages(cls, v, values):
        total = values.get('total', 0)
        page_size = values.get('page_size', 20)
        return (total + page_size - 1) // page_size if page_size > 0 else 0
