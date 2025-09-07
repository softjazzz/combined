from pydantic import BaseModel
from typing import List, Optional


class QCIssue(BaseModel):
    id: str
    rule_name: str
    description: str
    severity: str
    category: str
    location: str
    suggestion: str


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


class QCResult(BaseModel):
    id: str
    record_id: str
    overall_score: int
    overall_grade: str
    analysis_date: str
    issues: List[QCIssue]
    suggestions: List[QCSuggestion]
    rule_results: List[QCRuleResult]


class QCRule(BaseModel):
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

