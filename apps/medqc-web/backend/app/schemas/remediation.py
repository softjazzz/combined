"""
整改跟踪 Pydantic Schema 定义
"""

from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field, UUID4
from enum import Enum


class RemediationStatus(str, Enum):
    """整改状态枚举"""
    PENDING = "pending"          # 待整改
    IN_PROGRESS = "in_progress"  # 整改中
    SUBMITTED = "submitted"      # 已提交（待验收）
    APPROVED = "approved"        # 已通过
    REJECTED = "rejected"        # 已退回
    OVERDUE = "overdue"          # 已逾期
    CLOSED = "closed"            # 已关闭


class RemediationPriority(str, Enum):
    """整改优先级枚举"""
    LOW = "low"          # 低优先级
    MEDIUM = "medium"    # 中优先级
    HIGH = "high"        # 高优先级
    CRITICAL = "critical"  # 严重


class HistoryAction(str, Enum):
    """历史记录动作枚举"""
    CREATE = "create"              # 创建
    SUBMIT = "submit"              # 提交
    APPROVE = "approve"            # 批准
    REJECT = "reject"              # 拒绝
    CLOSE = "close"                # 关闭
    STATUS_CHANGE = "status_change"  # 状态变更
    UPDATE = "update"              # 更新


# ============================
# 整改任务创建和更新
# ============================

class RemediationTaskCreate(BaseModel):
    """创建整改任务请求"""
    qc_result_id: UUID4 = Field(..., description="质控结果ID")
    record_id: UUID4 = Field(..., description="病历ID")
    defect_type: str = Field(..., min_length=1, description="缺陷类型")
    defect_description: str = Field(..., min_length=10, description="缺陷描述")
    defect_location: Optional[str] = Field(None, description="缺陷位置")
    severity: RemediationPriority = Field(RemediationPriority.MEDIUM, description="严重程度")
    remediation_requirement: str = Field(..., min_length=10, description="整改要求")
    deadline: Optional[datetime] = Field(None, description="截止时间")
    assignee_id: UUID4 = Field(..., description="整改负责人ID")
    assignee_name: str = Field(..., min_length=1, description="整改负责人姓名")
    assignee_department: Optional[str] = Field(None, description="整改负责人科室")
    notes: Optional[str] = Field(None, description="备注")


class RemediationTaskUpdate(BaseModel):
    """更新整改任务请求"""
    defect_description: Optional[str] = Field(None, min_length=10, description="缺陷描述")
    defect_location: Optional[str] = Field(None, description="缺陷位置")
    severity: Optional[RemediationPriority] = Field(None, description="严重程度")
    remediation_requirement: Optional[str] = Field(None, min_length=10, description="整改要求")
    deadline: Optional[datetime] = Field(None, description="截止时间")
    assignee_id: Optional[UUID4] = Field(None, description="整改负责人ID")
    assignee_name: Optional[str] = Field(None, min_length=1, description="整改负责人姓名")
    assignee_department: Optional[str] = Field(None, description="整改负责人科室")
    notes: Optional[str] = Field(None, description="备注")


class RemediationSubmit(BaseModel):
    """提交整改请求"""
    remediation_description: str = Field(..., min_length=10, description="整改说明")
    remediation_evidence: List[dict] = Field(default=[], description="整改证据")


class RemediationReview(BaseModel):
    """验收整改请求"""
    action: str = Field(..., description="验收动作：approve（通过）或 reject（退回）")
    review_comment: str = Field(..., min_length=10, description="验收意见")


class RemediationClose(BaseModel):
    """关闭整改任务请求"""
    reason: Optional[str] = Field(None, description="关闭原因")


# ============================
# 整改任务响应
# ============================

class RemediationTaskResponse(BaseModel):
    """整改任务响应"""
    id: UUID4
    task_number: str
    qc_result_id: UUID4
    record_id: UUID4
    defect_type: str
    defect_description: str
    defect_location: Optional[str]
    severity: RemediationPriority
    remediation_requirement: str
    deadline: Optional[datetime]
    assignee_id: UUID4
    assignee_name: str
    assignee_department: Optional[str]
    status: RemediationStatus
    remediation_description: Optional[str]
    remediation_evidence: List[dict]
    submitted_at: Optional[datetime]
    reviewer_id: Optional[UUID4]
    reviewer_name: Optional[str]
    review_comment: Optional[str]
    reviewed_at: Optional[datetime]
    notes: Optional[str]
    created_at: datetime
    updated_at: datetime
    closed_at: Optional[datetime]

    class Config:
        from_attributes = True


class RemediationHistoryResponse(BaseModel):
    """整改历史记录响应"""
    id: UUID4
    task_id: UUID4
    action: str
    actor_id: UUID4
    actor_name: str
    old_status: Optional[RemediationStatus]
    new_status: Optional[RemediationStatus]
    comment: Optional[str]
    metadata: dict
    created_at: datetime

    class Config:
        from_attributes = True


class RemediationTaskDetailResponse(RemediationTaskResponse):
    """整改任务详情响应（包含历史记录）"""
    history: List[RemediationHistoryResponse] = Field(default=[], description="历史记录")


# ============================
# 列表和统计
# ============================

class RemediationTaskListQuery(BaseModel):
    """整改任务列表查询参数"""
    status: Optional[RemediationStatus] = Field(None, description="整改状态")
    severity: Optional[RemediationPriority] = Field(None, description="严重程度")
    assignee_id: Optional[UUID4] = Field(None, description="负责人ID")
    reviewer_id: Optional[UUID4] = Field(None, description="验收人ID")
    defect_type: Optional[str] = Field(None, description="缺陷类型")
    is_overdue: Optional[bool] = Field(None, description="是否逾期")
    start_date: Optional[datetime] = Field(None, description="开始日期")
    end_date: Optional[datetime] = Field(None, description="结束日期")
    page: int = Field(1, ge=1, description="页码")
    page_size: int = Field(20, ge=1, le=100, description="每页数量")


class RemediationStatistics(BaseModel):
    """整改统计"""
    total: int = Field(..., description="总数")
    pending: int = Field(..., description="待整改")
    in_progress: int = Field(..., description="整改中")
    submitted: int = Field(..., description="已提交")
    approved: int = Field(..., description="已通过")
    rejected: int = Field(..., description="已退回")
    overdue: int = Field(..., description="已逾期")
    closed: int = Field(..., description="已关闭")
    avg_completion_time_hours: Optional[float] = Field(None, description="平均完成时长（小时）")
    by_severity: dict = Field(default={}, description="按严重程度统计")
    by_defect_type: dict = Field(default={}, description="按缺陷类型统计")


class AssigneeWorkload(BaseModel):
    """责任人工作负载"""
    assignee_id: UUID4 = Field(..., description="负责人ID")
    assignee_name: str = Field(..., description="负责人姓名")
    assignee_department: Optional[str] = Field(None, description="负责人科室")
    total_tasks: int = Field(..., description="总任务数")
    pending_tasks: int = Field(..., description="待整改任务数")
    in_progress_tasks: int = Field(..., description="整改中任务数")
    overdue_tasks: int = Field(..., description="逾期任务数")
    avg_completion_days: Optional[float] = Field(None, description="平均完成天数")


class OverdueTaskAlert(BaseModel):
    """逾期任务告警"""
    task_id: UUID4
    task_number: str
    assignee_name: str
    defect_description: str
    deadline: datetime
    overdue_days: int
    severity: RemediationPriority
