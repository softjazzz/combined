"""
缺陷操作相关 Schema

用于缺陷催办、整改标记、审核通过/存疑等操作
"""

from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
from enum import Enum


# ============================================================================
# Enums
# ============================================================================

class DefectStatus(str, Enum):
    """缺陷状态"""
    PENDING = "pending"             # 待处理
    URGED = "urged"                 # 已催办
    REMEDIATED = "remediated"       # 已整改
    APPROVED = "approved"           # 审核通过
    REJECTED = "rejected"           # 审核存疑（退回）


class DefectSeverity(str, Enum):
    """缺陷严重程度"""
    CRITICAL = "critical"           # 严重（一票否决）
    ERROR = "error"                 # 错误
    WARNING = "warning"             # 警告
    INFO = "info"                   # 提示


class DefectCategory(str, Enum):
    """缺陷分类"""
    SINGLE_VETO = "single_veto"     # 单否
    MANUAL = "manual"               # 人工
    CORE = "core"                   # 核心
    CODING = "coding"               # 编码
    OTHER = "other"                 # 其他


# ============================================================================
# Request Models
# ============================================================================

class DefectUrgeRequest(BaseModel):
    """催办缺陷请求"""
    message: str = Field("请尽快完成整改", description="催办消息")
    deadline: Optional[str] = Field(None, description="整改截止日期 (YYYY-MM-DD)")


class DefectCancelUrgeRequest(BaseModel):
    """撤回催办请求"""
    reason: Optional[str] = Field(None, description="撤回原因")


class DefectMarkRemediatedRequest(BaseModel):
    """标记已整改请求"""
    remediation_note: str = Field(..., description="整改说明")
    evidence: Optional[List[str]] = Field(default_factory=list, description="整改证据（文件路径）")


class DefectApproveRequest(BaseModel):
    """审核通过请求"""
    comment: Optional[str] = Field(None, description="审核意见")


class DefectRejectRequest(BaseModel):
    """审核存疑（退回）请求"""
    reason: str = Field(..., description="退回原因")
    suggestion: Optional[str] = Field(None, description="修改建议")


class DefectBatchActionRequest(BaseModel):
    """批量操作请求"""
    defect_ids: List[str] = Field(..., description="缺陷ID列表")
    action: str = Field(..., description="操作类型: approve | reject | urge")
    message: Optional[str] = Field(None, description="操作消息")


class DefectExportRequest(BaseModel):
    """导出缺陷列表请求"""
    format: str = Field("xlsx", description="导出格式: xlsx | csv")
    max_rows: int = Field(10000, le=10000, description="最大导出行数")
    # 筛选条件
    record_id: Optional[str] = Field(None, description="病历ID")
    department: Optional[str] = Field(None, description="科室")
    severity: Optional[str] = Field(None, description="严重程度")
    category: Optional[str] = Field(None, description="缺陷分类")
    status: Optional[str] = Field(None, description="缺陷状态")
    start_date: Optional[str] = Field(None, description="开始日期")
    end_date: Optional[str] = Field(None, description="结束日期")


# ============================================================================
# Response Models
# ============================================================================

class DefectActionResult(BaseModel):
    """缺陷操作结果"""
    defect_id: str
    action: str
    success: bool
    new_status: Optional[str] = None
    message: Optional[str] = None
    timestamp: str = Field(default_factory=lambda: datetime.now().isoformat())


class DefectExportResult(BaseModel):
    """导出结果"""
    file_path: str
    file_name: str
    total_rows: int
    format: str
    download_url: str
