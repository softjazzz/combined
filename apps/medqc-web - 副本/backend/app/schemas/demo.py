"""
演示页面相关的 Pydantic 模型定义
用于 LX33 质控规则演示和反馈系统
"""

from datetime import datetime
from typing import Optional, List, Literal
from pydantic import BaseModel, Field
from uuid import UUID

# 错误类别类型
ErrorCategory = Literal[
    "false_positive",  # 误报
    "false_negative",  # 漏报
    "wrong_reasoning",  # 推理错误
    "incomplete_check",  # 检查不完整
    "rule_ambiguity",  # 规则歧义
    "other"  # 其他
]

# 反馈类型
FeedbackType = Literal["correct", "incorrect"]


# 反馈提交请求
class FeedbackCreate(BaseModel):
    """创建反馈的请求模型"""
    evaluation_id: Optional[str] = Field(None, description="评估记录ID（可选）")
    rule_id: str = Field(..., description="规则ID")
    rule_code: str = Field(..., description="规则编号")
    rule_name: str = Field(..., description="规则名称")
    document_name: str = Field(..., description="文档名称")
    evaluation_result: bool = Field(..., description="评估结果（True=合规，False=不合规）")
    feedback_type: FeedbackType = Field(..., description="反馈类型")
    error_category: Optional[ErrorCategory] = Field(None, description="错误类别（仅错误反馈需要）")
    error_detail: Optional[str] = Field(None, description="错误详情（仅错误反馈需要）")
    evidence: Optional[str] = Field(None, description="补充证据")
    feedback_by: Optional[str] = Field(None, description="反馈人")
    medical_text: Optional[str] = Field(None, description="进行质控的病历原文")


# 反馈记录响应
class FeedbackResponse(BaseModel):
    """反馈记录的响应模型"""
    feedback_id: str = Field(..., description="反馈ID")
    evaluation_id: Optional[str] = Field(None, description="评估记录ID")
    rule_id: str = Field(..., description="规则ID")
    rule_code: str = Field(..., description="规则编号")
    rule_name: str = Field(..., description="规则名称")
    document_name: str = Field(..., description="文档名称")
    evaluation_result: bool = Field(..., description="评估结果")
    feedback_type: FeedbackType = Field(..., description="反馈类型")
    error_category: Optional[ErrorCategory] = Field(None, description="错误类别")
    error_detail: Optional[str] = Field(None, description="错误详情")
    evidence: Optional[str] = Field(None, description="补充证据")
    feedback_by: Optional[str] = Field(None, description="反馈人")
    medical_text: Optional[str] = Field(None, description="进行质控的病历原文")
    created_at: str = Field(..., description="创建时间")


# 规则反馈统计
class RuleFeedbackStat(BaseModel):
    """单个规则的反馈统计"""
    rule_code: str = Field(..., description="规则编号")
    rule_name: str = Field(..., description="规则名称")
    total: int = Field(..., description="总反馈数")
    correct: int = Field(..., description="正确反馈数")
    incorrect: int = Field(..., description="错误反馈数")
    accuracy: float = Field(..., description="准确率")


# 反馈统计响应
class FeedbackStats(BaseModel):
    """反馈统计的响应模型"""
    total_feedbacks: int = Field(..., description="总反馈数")
    correct_feedbacks: int = Field(..., description="正确反馈数")
    incorrect_feedbacks: int = Field(..., description="错误反馈数")
    accuracy_rate: float = Field(..., description="准确率")
    best_rule: Optional[str] = Field(None, description="最高准确率规则")
    worst_rule: Optional[str] = Field(None, description="最低准确率规则")
    by_rule: Optional[List[RuleFeedbackStat]] = Field(None, description="按规则统计")
    error_categories: Optional[dict] = Field(None, description="错误类别统计")


# 分页反馈列表响应
class FeedbackListResponse(BaseModel):
    """反馈列表的响应模型"""
    success: bool = Field(True, description="请求是否成功")
    data: List[FeedbackResponse] = Field(..., description="反馈记录列表")
    total: int = Field(..., description="总记录数")
    page: int = Field(..., description="当前页码")
    page_size: int = Field(..., description="每页记录数")


class RuleGenerationRequest(BaseModel):
    """AI 生成质控规则的请求"""
    requirement: str = Field(..., min_length=10, max_length=1000, description="规则需求的自然语言描述")
    applicable_documents: List[str] = Field(default_factory=list, description="适用文书列表（中文）")
    defect_level: str = Field(..., description="缺陷级别")
    complexity: str = Field(..., description="规则复杂度")
    category: Optional[str] = Field(None, description="规则分类（可选）")


class RuleExample(BaseModel):
    """质控规则示例"""
    title: str = Field(..., description="示例标题")
    content: str = Field(..., description="示例病历内容")
    explanation: Optional[str] = Field(None, description="示例说明")


class DemoCustomRule(BaseModel):
    """Demo 生成的自定义规则"""
    rule_id: Optional[str] = Field(None, description="规则ID")
    rule_code: Optional[str] = Field(None, description="规则编号")
    name: str = Field(..., description="规则名称")
    description: str = Field(..., description="规则描述")
    custom_prompt: str = Field(..., description="质控提示词")
    category: Optional[str] = Field(None, description="规则类别")
    applicable_documents: List[str] = Field(default_factory=list, description="适用文书列表")
    defect_level: str = Field(..., description="缺陷级别")
    complexity: str = Field(..., description="复杂度")
    score_deduction: Optional[str] = Field(default="2", description="扣分分值")
    positive_example: RuleExample = Field(..., description="合规示例")
    negative_example: RuleExample = Field(..., description="不合规示例")
    source: Optional[str] = Field(default="ai_generated", description="规则来源")
    generation_params: Optional[dict] = Field(default=None, description="生成参数快照")


class CustomRuleSaveRequest(BaseModel):
    """保存自定义规则的请求"""
    rule: DemoCustomRule = Field(..., description="要保存的规则数据")
