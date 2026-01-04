"""
整改管理相关的数据模型
Rectification Management Schemas
"""
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
from enum import Enum


class TaskSeverity(str, Enum):
    """任务严重程度"""
    CRITICAL = "critical"  # 严重
    MAJOR = "major"        # 重要
    MINOR = "minor"        # 一般


class TaskStatus(str, Enum):
    """任务状态"""
    PENDING = "pending"        # 待处理
    IN_PROGRESS = "in_progress"  # 进行中
    SUBMITTED = "submitted"     # 已提交
    APPROVED = "approved"       # 已通过
    REJECTED = "rejected"       # 未通过


class ReviewResult(str, Enum):
    """验收结果"""
    PASS = "pass"      # 通过
    FAIL = "fail"      # 不通过


class RectificationTaskCreate(BaseModel):
    """创建整改任务请求"""
    qc_result_id: str = Field(..., description="质控结果ID")
    defect_id: str = Field(..., description="缺陷ID")
    record_id: str = Field(..., description="病案记录ID")
    appeal_id: Optional[str] = Field(None, description="关联申诉ID")
    
    task_title: str = Field(..., min_length=5, max_length=200, description="任务标题")
    task_description: str = Field(..., min_length=10, description="任务描述")
    defect_type: str = Field(..., description="缺陷类型")
    severity: TaskSeverity = Field(..., description="严重程度")
    
    assignee_id: str = Field(..., description="指派人ID")
    assignee_name: Optional[str] = Field(None, description="指派人姓名")
    department_id: Optional[str] = Field(None, description="科室ID")
    due_date: Optional[datetime] = Field(None, description="截止日期")


class RectificationTaskUpdate(BaseModel):
    """更新整改任务"""
    task_title: Optional[str] = Field(None, min_length=5, max_length=200)
    task_description: Optional[str] = Field(None, min_length=10)
    severity: Optional[TaskSeverity] = None
    due_date: Optional[datetime] = None
    status: Optional[TaskStatus] = None


class TaskAssignment(BaseModel):
    """任务分配"""
    assignee_id: str = Field(..., description="指派人ID")
    assignee_name: Optional[str] = Field(None, description="指派人姓名")
    comment: Optional[str] = Field(None, description="分配说明")


class TaskSubmission(BaseModel):
    """提交整改"""
    rectification_content: str = Field(..., min_length=10, description="整改说明")
    rectification_files: Optional[List[str]] = Field(default=[], description="整改文件URLs")


class TaskReview(BaseModel):
    """验收整改"""
    review_result: ReviewResult = Field(..., description="验收结果")
    review_comment: str = Field(..., min_length=5, description="验收意见")


class RectificationTaskResponse(BaseModel):
    """整改任务响应"""
    id: str
    qc_result_id: str
    defect_id: str
    record_id: str
    appeal_id: Optional[str] = None
    
    # 任务信息
    task_title: str
    task_description: str
    defect_type: str
    severity: TaskSeverity
    
    # 分配信息
    assignee_id: str
    assignee_name: Optional[str] = None
    assigner_id: Optional[str] = None
    assigner_name: Optional[str] = None
    department_id: Optional[str] = None
    due_date: Optional[datetime] = None
    
    # 状态
    status: TaskStatus
    
    # 整改内容
    rectification_content: Optional[str] = None
    rectification_files: List[str] = []
    submitted_at: Optional[datetime] = None
    
    # 验收信息
    reviewer_id: Optional[str] = None
    reviewer_name: Optional[str] = None
    review_comment: Optional[str] = None
    review_result: Optional[ReviewResult] = None
    reviewed_at: Optional[datetime] = None
    
    # 时间戳
    created_at: datetime
    updated_at: datetime
    completed_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True


class RectificationTaskListResponse(BaseModel):
    """整改任务列表响应"""
    items: List[RectificationTaskResponse]
    total: int
    page: int = 1
    page_size: int = 20
    has_more: bool


class TaskFilters(BaseModel):
    """任务筛选条件"""
    status: Optional[TaskStatus] = None
    severity: Optional[TaskSeverity] = None
    assignee_id: Optional[str] = None
    assigner_id: Optional[str] = None
    department_id: Optional[str] = None
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    overdue_only: bool = False
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=100)


class TaskStats(BaseModel):
    """整改任务统计"""
    total_count: int = 0
    pending_count: int = 0
    in_progress_count: int = 0
    submitted_count: int = 0
    approved_count: int = 0
    rejected_count: int = 0
    overdue_count: int = 0
    completion_rate: float = 0.0
    avg_completion_time_hours: float = 0.0
    on_time_rate: float = 0.0
