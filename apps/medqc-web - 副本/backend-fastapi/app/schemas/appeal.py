"""
申诉管理相关的数据模型
Appeal Management Schemas
"""
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
from enum import Enum


class AppealType(str, Enum):
    """申诉类型"""
    INCORRECT_RULE = "incorrect_rule"  # 规则判定有误
    SPECIAL_CASE = "special_case"      # 特殊情况
    OTHER = "other"                     # 其他


class AppealStatus(str, Enum):
    """申诉状态"""
    PENDING = "pending"        # 待审核
    APPROVED = "approved"      # 已通过
    REJECTED = "rejected"      # 已驳回
    WITHDRAWN = "withdrawn"    # 已撤销


class AppealCreate(BaseModel):
    """创建申诉请求"""
    qc_result_id: str = Field(..., description="质控结果ID")
    defect_id: str = Field(..., description="缺陷ID")
    record_id: str = Field(..., description="病案记录ID")
    appeal_reason: str = Field(..., min_length=10, description="申诉理由")
    appeal_type: AppealType = Field(..., description="申诉类型")
    evidence_urls: Optional[List[str]] = Field(default=[], description="证据文件URLs")


class AppealUpdate(BaseModel):
    """更新申诉"""
    appeal_reason: Optional[str] = Field(None, min_length=10, description="申诉理由")
    appeal_type: Optional[AppealType] = Field(None, description="申诉类型")
    evidence_urls: Optional[List[str]] = Field(None, description="证据文件URLs")


class AppealReview(BaseModel):
    """申诉审核"""
    decision: str = Field(..., pattern="^(approve|reject)$", description="审核决定: approve/reject")
    comment: str = Field(..., min_length=5, description="审核意见")


class AppealResponse(BaseModel):
    """申诉响应"""
    id: str
    qc_result_id: str
    defect_id: str
    record_id: str
    
    # 申诉人信息
    appellant_id: str
    appellant_name: Optional[str] = None
    department_id: Optional[str] = None
    
    # 申诉内容
    appeal_reason: str
    appeal_type: AppealType
    evidence_urls: List[str] = []
    
    # 审核信息
    status: AppealStatus
    reviewer_id: Optional[str] = None
    reviewer_name: Optional[str] = None
    review_comment: Optional[str] = None
    reviewed_at: Optional[datetime] = None
    
    # 时间戳
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


class AppealListResponse(BaseModel):
    """申诉列表响应"""
    items: List[AppealResponse]
    total: int
    page: int = 1
    page_size: int = 20
    has_more: bool


class AppealFilters(BaseModel):
    """申诉筛选条件"""
    status: Optional[AppealStatus] = None
    appeal_type: Optional[AppealType] = None
    appellant_id: Optional[str] = None
    department_id: Optional[str] = None
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=100)


class AppealStats(BaseModel):
    """申诉统计"""
    total_count: int = 0
    pending_count: int = 0
    approved_count: int = 0
    rejected_count: int = 0
    withdrawn_count: int = 0
    approval_rate: float = 0.0
    avg_review_time_hours: float = 0.0
