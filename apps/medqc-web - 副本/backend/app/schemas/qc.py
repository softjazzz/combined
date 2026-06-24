from pydantic import BaseModel, Field
from typing import Any, Dict, List, Optional
from datetime import datetime
from enum import Enum


# ============================================================================
# Enums
# ============================================================================

class RuleScope(str, Enum):
    """规则范围"""
    GLOBAL = "global"
    DEPARTMENT = "department"


class RuleStatus(str, Enum):
    """规则状态"""
    DRAFT = "draft"
    PUBLISHED = "published"
    ARCHIVED = "archived"


class OverrideAction(str, Enum):
    """覆盖行为"""
    OVERRIDE = "override"
    DISABLE = "disable"


# ============================================================================
# Existing Models
# ============================================================================

class QCIssue(BaseModel):
    id: str
    rule_name: str
    description: str
    severity: str
    category: str
    location: str
    suggestion: str
    evidence: Optional[str] = None


class QCSuggestion(BaseModel):
    id: str
    category: str
    title: str
    description: str
    priority: str


class QCRuleResult(BaseModel):
    rule_id: str
    rule_name: str
    passed: bool
    score: int
    details: str
    max_score: Optional[int] = None
    execution_time: Optional[int] = None
    confidence: Optional[float] = None


class QCAnalysisStep(BaseModel):
    id: str
    name: str
    description: str
    status: str
    started_at: Optional[str] = None
    completed_at: Optional[str] = None


class QCResult(BaseModel):
    id: str
    record_id: str
    overall_score: int
    overall_grade: str
    analysis_date: str
    issues: List[QCIssue]
    suggestions: List[QCSuggestion]
    rule_results: List[QCRuleResult]
    analysis_steps: Optional[List[QCAnalysisStep]] = None
    metadata: Optional[Dict[str, Any]] = None


class QCRule(BaseModel):
    """质控规则基础模型"""
    id: str
    rule_code: str
    name: str
    description: str
    category: str
    severity: str
    weight: int
    is_active: bool
    conditions: Optional[str] = None
    created_at: str
    updated_at: str
    execution_count: Optional[int] = 0
    pass_rate: Optional[float] = 0.0
    issue_count: Optional[int] = 0


# ============================================================================
# Department QC Rules Models (Migration 009)
# ============================================================================

class QCRuleExtended(QCRule):
    """扩展的质控规则模型（包含科室级规则字段）"""
    # 规则范围和科室
    scope: RuleScope = RuleScope.GLOBAL
    department_id: Optional[str] = None
    parent_rule_id: Optional[str] = None

    # 覆盖配置
    override_action: OverrideAction = OverrideAction.OVERRIDE
    override_config: Optional[Dict[str, Any]] = Field(default_factory=dict)
    priority: int = 0

    # 版本和生效期
    status: RuleStatus = RuleStatus.PUBLISHED
    version: Optional[str] = "1.0"
    effective_from: Optional[datetime] = None
    effective_to: Optional[datetime] = None

    # 审核信息
    approved_by: Optional[str] = None
    approved_at: Optional[datetime] = None

    # 其他字段
    check_logic: Optional[Dict[str, Any]] = Field(default_factory=dict)
    scoring_config: Optional[Dict[str, Any]] = Field(default_factory=dict)
    applicable_documents: Optional[List[str]] = Field(default_factory=list)


class DepartmentRuleCreate(BaseModel):
    """创建科室规则请求"""
    department_id: str = Field(..., description="科室ID")
    base_rule_id: Optional[str] = Field(None, description="基础规则ID（覆盖规则时使用）")
    rule_code: str = Field(..., description="规则编号")
    name: str = Field(..., description="规则名称")
    description: Optional[str] = Field(None, description="规则描述")
    category: str = Field(..., description="规则分类")
    severity: str = Field(..., description="严重程度")
    override_action: OverrideAction = Field(OverrideAction.OVERRIDE, description="覆盖行为")
    override_config: Optional[Dict[str, Any]] = Field(default_factory=dict, description="覆盖配置")
    priority: int = Field(0, description="优先级")
    status: RuleStatus = Field(RuleStatus.DRAFT, description="规则状态")
    effective_from: Optional[datetime] = Field(None, description="生效开始时间")
    effective_to: Optional[datetime] = Field(None, description="生效结束时间")
    check_logic: Optional[Dict[str, Any]] = Field(default_factory=dict, description="检查逻辑")
    scoring_config: Optional[Dict[str, Any]] = Field(default_factory=dict, description="评分配置")
    applicable_documents: Optional[List[str]] = Field(default_factory=list, description="适用文书类型")


class DepartmentRuleUpdate(BaseModel):
    """更新科室规则请求"""
    name: Optional[str] = Field(None, description="规则名称")
    description: Optional[str] = Field(None, description="规则描述")
    severity: Optional[str] = Field(None, description="严重程度")
    override_action: Optional[OverrideAction] = Field(None, description="覆盖行为")
    override_config: Optional[Dict[str, Any]] = Field(None, description="覆盖配置")
    priority: Optional[int] = Field(None, description="优先级")
    effective_from: Optional[datetime] = Field(None, description="生效开始时间")
    effective_to: Optional[datetime] = Field(None, description="生效结束时间")
    check_logic: Optional[Dict[str, Any]] = Field(None, description="检查逻辑")
    scoring_config: Optional[Dict[str, Any]] = Field(None, description="评分配置")
    applicable_documents: Optional[List[str]] = Field(None, description="适用文书类型")
    is_active: Optional[bool] = Field(None, description="是否激活")


class DepartmentRulePublish(BaseModel):
    """发布规则请求"""
    approved_by: str = Field(..., description="审核人ID")
    reason: Optional[str] = Field(None, description="发布原因")


class RuleChangeLog(BaseModel):
    """规则变更日志"""
    id: str
    rule_id: str
    department_id: Optional[str] = None
    action: str
    old_values: Optional[Dict[str, Any]] = None
    new_values: Optional[Dict[str, Any]] = None
    diff: Optional[Dict[str, Any]] = None
    actor_id: str
    actor_name: Optional[str] = None
    actor_role: Optional[str] = None
    reason: Optional[str] = None
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    created_at: datetime


class ApplicableRulesQuery(BaseModel):
    """获取适用规则查询参数"""
    department_id: str = Field(..., description="科室ID")
    document_type: Optional[str] = Field(None, description="文书类型")
    at: Optional[datetime] = Field(None, description="时间点（用于生效期判断）")
