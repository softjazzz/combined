"""
申诉流程 Pydantic Schema 定义
"""

from datetime import datetime
from typing import Optional, List, Any
from pydantic import BaseModel, Field, UUID4
from enum import Enum


class AppealStatus(str, Enum):
    """申诉状态枚举"""
    PENDING = "pending"          # 待审核
    REVIEWING = "reviewing"      # 审核中
    APPROVED = "approved"        # 已通过
    REJECTED = "rejected"        # 已拒绝
    WITHDRAWN = "withdrawn"      # 已撤回


class AppealPriority(str, Enum):
    """申诉优先级枚举"""
    LOW = "low"          # 低优先级
    MEDIUM = "medium"    # 中优先级
    HIGH = "high"        # 高优先级
    URGENT = "urgent"    # 紧急


class AppealType(str, Enum):
    """申诉类型枚举"""
    DEFECT = "defect"    # 缺陷申诉
    SCORE = "score"      # 评分申诉


class ReviewAction(str, Enum):
    """审核动作枚举"""
    APPROVE = "approve"          # 批准
    REJECT = "reject"            # 拒绝
    REQUEST_INFO = "request_info"  # 要求补充信息
    FORWARD = "forward"          # 转发


# ============================
# 申诉创建和更新
# ============================

class AppealCreate(BaseModel):
    """创建申诉请求"""
    qc_result_id: UUID4 = Field(..., description="质控结果ID")
    record_id: UUID4 = Field(..., description="病历ID")
    appeal_type: AppealType = Field(..., description="申诉类型")
    defect_item: Optional[str] = Field(None, description="申诉的具体缺陷项")
    reason: str = Field(..., min_length=10, description="申诉理由（至少10个字符）")
    evidence: List[dict] = Field(default=[], description="证据材料")
    priority: AppealPriority = Field(AppealPriority.MEDIUM, description="优先级")
    appellant_department: Optional[str] = Field(None, description="申诉人科室")
    notes: Optional[str] = Field(None, description="备注")


class AppealUpdate(BaseModel):
    """更新申诉请求"""
    reason: Optional[str] = Field(None, min_length=10, description="申诉理由")
    evidence: Optional[List[dict]] = Field(None, description="证据材料")
    priority: Optional[AppealPriority] = Field(None, description="优先级")
    notes: Optional[str] = Field(None, description="备注")


class AppealWithdraw(BaseModel):
    """撤回申诉请求"""
    reason: Optional[str] = Field(None, description="撤回原因")


# ============================
# 审核相关
# ============================

class AppealReviewCreate(BaseModel):
    """创建审核记录请求"""
    action: ReviewAction = Field(..., description="审核动作")
    comment: Optional[str] = Field(None, description="审核意见")
    resolution: Optional[str] = Field(None, description="处理决定")


class AppealReviewResponse(BaseModel):
    """审核记录响应"""
    id: UUID4
    appeal_id: UUID4
    reviewer_id: UUID4
    reviewer_name: str
    reviewer_role: str
    action: ReviewAction
    comment: Optional[str]
    metadata: dict
    created_at: datetime

    class Config:
        from_attributes = True


# ============================
# 申诉响应
# ============================

class AppealResponse(BaseModel):
    """申诉记录响应"""
    id: UUID4
    appeal_number: str
    qc_result_id: UUID4
    record_id: UUID4
    appeal_type: AppealType
    defect_item: Optional[str]
    reason: str
    evidence: List[dict]
    status: AppealStatus
    priority: AppealPriority
    appellant_id: UUID4
    appellant_name: str
    appellant_department: Optional[str]
    reviewer_id: Optional[UUID4]
    reviewer_name: Optional[str]
    review_result: Optional[str]
    review_date: Optional[datetime]
    resolution: Optional[str]
    resolution_date: Optional[datetime]
    notes: Optional[str]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class AppealDetailResponse(AppealResponse):
    """申诉详情响应（包含审核历史）"""
    reviews: List[AppealReviewResponse] = Field(default=[], description="审核历史")


# ============================
# 列表和统计
# ============================

class AppealListQuery(BaseModel):
    """申诉列表查询参数"""
    status: Optional[AppealStatus] = Field(None, description="申诉状态")
    priority: Optional[AppealPriority] = Field(None, description="优先级")
    appeal_type: Optional[AppealType] = Field(None, description="申诉类型")
    appellant_id: Optional[UUID4] = Field(None, description="申诉人ID")
    reviewer_id: Optional[UUID4] = Field(None, description="审核人ID")
    start_date: Optional[datetime] = Field(None, description="开始日期")
    end_date: Optional[datetime] = Field(None, description="结束日期")
    page: int = Field(1, ge=1, description="页码")
    page_size: int = Field(20, ge=1, le=100, description="每页数量")


class AppealStatistics(BaseModel):
    """申诉统计"""
    total: int = Field(..., description="总数")
    pending: int = Field(..., description="待审核")
    reviewing: int = Field(..., description="审核中")
    approved: int = Field(..., description="已通过")
    rejected: int = Field(..., description="已拒绝")
    withdrawn: int = Field(..., description="已撤回")
    avg_resolution_time_hours: Optional[float] = Field(None, description="平均处理时长（小时）")
    by_type: dict = Field(default={}, description="按类型统计")
    by_priority: dict = Field(default={}, description="按优先级统计")
