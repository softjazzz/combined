"""首页质控 V2：规则、结论与评分项的数据结构。"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Callable, Dict, List, Optional, Tuple

from .document import FrontpageDoc


class Verdict(str, Enum):
    PASS = "pass"
    FAIL = "fail"
    DATA_GAP = "data_gap"
    NOT_APPLICABLE = "not_applicable"


class Severity(str, Enum):
    DEDUCT = "deduct"  # 对应评分表条目，扣分
    REQUIRED = "required"  # 76 项必填但评分表未单列，只计入填报完整率
    HINT = "hint"  # 可疑但不确定，不扣分


GROUP_LABELS = {"completeness": "完整性", "specification": "规范性", "logic": "逻辑一致性"}
SECTION_LABELS = {"patient": "患者信息", "hospitalization": "住院信息", "diagnosis": "诊疗信息", "cost": "费用信息"}
SEVERITY_LABELS = {"deduct": "扣分", "required": "必填", "hint": "提示"}


@dataclass(frozen=True)
class Detail:
    """一条具体问题：哪个字段、当前值、要求。item_index 用于逐条诊断/手术。"""

    field: str
    value: str
    expected: str
    item_index: Optional[int] = None


@dataclass(frozen=True)
class RuleEval:
    verdict: Verdict
    details: Tuple[Detail, ...] = ()
    reason: str = ""


def passed() -> RuleEval:
    return RuleEval(Verdict.PASS)


def not_applicable(reason: str = "") -> RuleEval:
    return RuleEval(Verdict.NOT_APPLICABLE, reason=reason)


def data_gap(reason: str, *details: Detail) -> RuleEval:
    return RuleEval(Verdict.DATA_GAP, tuple(details), reason)


def failed(*details: Detail) -> RuleEval:
    return RuleEval(Verdict.FAIL, tuple(details))


CheckFn = Callable[[FrontpageDoc], RuleEval]


@dataclass(frozen=True)
class Rule:
    rule_id: str
    name: str
    group: str
    section: str
    severity: Severity
    score_item: Optional[str]
    basis: str
    problem: str
    check: Optional[CheckFn] = None
    enabled: bool = True
    disabled_reason: str = ""
    condition: str = ""


@dataclass(frozen=True)
class ScoreItem:
    key: str
    label: str
    section: str
    klass: str  # A/B/C/D
    points: float
    per_item: bool = False
    item_cap: Optional[float] = None


@dataclass
class Finding:
    rule_id: str
    rule_name: str
    group: str
    section: str
    severity: str
    score_item: Optional[str]
    verdict: str
    problem: str
    reason: str
    details: List[Dict[str, object]]
    deduction: float = 0.0


@dataclass
class ItemScore:
    key: str
    label: str
    section: str
    klass: str
    status: str  # evaluated / data_gap / not_applicable
    deduction: float
    max_points: float


@dataclass
class FrontpageQcOutcome:
    institute_id: str
    patient_id: str
    visit_id: str
    ruleset_version: str
    score: float
    grade: str
    fail_count: int
    hint_count: int
    data_gap_count: int
    required_missing_count: int
    scorable_ratio: float
    completeness_rate: Optional[float]
    findings: List[Finding]
    item_scores: List[ItemScore]
    rule_verdicts: Dict[str, str]
    input_fingerprint: str
    notes: List[str] = field(default_factory=list)
