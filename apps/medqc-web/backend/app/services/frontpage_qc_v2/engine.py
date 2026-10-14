"""首页质控 V2：执行规则并按 2016 版评分表计分。"""
from __future__ import annotations

import hashlib
import json
import logging
from collections import defaultdict
from typing import Dict, Iterable, List, Optional, Tuple

from .catalog import RULES
from .config import RULESET_VERSION, grade_of
from .document import FrontpageDoc
from .model import (
    Finding,
    FrontpageQcOutcome,
    ItemScore,
    Rule,
    RuleEval,
    Severity,
    Verdict,
    data_gap,
)
from .scoring_items import GROUP_CAPS, SCORE_ITEMS, max_points

logger = logging.getLogger(__name__)


def _run_rule(rule: Rule, doc: FrontpageDoc) -> RuleEval:
    try:
        return rule.check(doc)  # type: ignore[misc]
    except Exception as exc:  # noqa: BLE001 - 规则异常一律判资料不足，不默认通过
        logger.warning("首页质控规则执行异常 rule=%s error=%s", rule.rule_id, type(exc).__name__)
        return data_gap(f"规则执行异常：{type(exc).__name__}")


def input_fingerprint(doc: FrontpageDoc) -> str:
    payload = json.dumps(doc.as_display(), ensure_ascii=False, sort_keys=True, default=str)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:32]


def _round(value: float) -> float:
    return round(value + 1e-9, 2)


def _score(results: Iterable[Tuple[Rule, RuleEval]]) -> Tuple[float, List[ItemScore], Dict[str, float]]:
    fails: Dict[str, List[RuleEval]] = defaultdict(list)
    statuses: Dict[str, set] = defaultdict(set)
    for rule, result in results:
        if rule.score_item is None or rule.severity is not Severity.DEDUCT or not rule.enabled:
            continue
        statuses[rule.score_item].add(result.verdict)
        if result.verdict is Verdict.FAIL:
            fails[rule.score_item].append(result)

    item_deductions: Dict[str, float] = {}
    item_scores: List[ItemScore] = []
    for key, item in SCORE_ITEMS.items():
        seen = statuses.get(key, set())
        if Verdict.FAIL in seen or Verdict.PASS in seen:
            status = "evaluated"
        elif Verdict.DATA_GAP in seen:
            status = "data_gap"
        else:
            status = "not_applicable"
        deduction = 0.0
        if key in fails:
            if item.per_item:
                # 同一条诊断/手术被多条规则命中只算一项
                indexed = {d.item_index for r in fails[key] for d in r.details if d.item_index is not None}
                unindexed = sum(1 for r in fails[key] for d in r.details if d.item_index is None)
                count = max(1, len(indexed) + unindexed)
                deduction = min(item.points * count, max_points(item))
            else:
                deduction = item.points
        item_deductions[key] = deduction
        item_scores.append(ItemScore(key, item.label, item.section, item.klass, status, deduction, max_points(item)))

    group_totals: Dict[Tuple[str, str], float] = defaultdict(float)
    for key, deduction in item_deductions.items():
        item = SCORE_ITEMS[key]
        group_totals[(item.section, item.klass)] += deduction
    total = 0.0
    for group, amount in group_totals.items():
        cap = GROUP_CAPS.get(group)
        total += min(amount, cap) if cap is not None else amount
    return _round(max(0.0, 100.0 - total)), item_scores, item_deductions


def evaluate_frontpage(doc: FrontpageDoc, rules: Optional[Iterable[Rule]] = None) -> FrontpageQcOutcome:
    rule_list = tuple(rules) if rules is not None else RULES
    results: List[Tuple[Rule, RuleEval]] = []
    for rule in rule_list:
        if not rule.enabled or rule.check is None:
            continue
        results.append((rule, _run_rule(rule, doc)))

    score, item_scores, item_deductions = _score(results)

    findings: List[Finding] = []
    charged: set = set()
    for rule, result in results:
        if result.verdict not in (Verdict.FAIL, Verdict.DATA_GAP):
            continue
        deduction = 0.0
        if (
            result.verdict is Verdict.FAIL
            and rule.severity is Severity.DEDUCT
            and rule.score_item is not None
            and rule.score_item not in charged
        ):
            deduction = item_deductions.get(rule.score_item, 0.0)
            charged.add(rule.score_item)
        findings.append(
            Finding(
                rule_id=rule.rule_id,
                rule_name=rule.name,
                group=rule.group,
                section=rule.section,
                severity=rule.severity.value,
                score_item=rule.score_item,
                verdict=result.verdict.value,
                problem=rule.problem,
                reason=result.reason,
                details=[detail.__dict__.copy() for detail in result.details],
                deduction=deduction,
            )
        )

    fails = [f for f in findings if f.verdict == Verdict.FAIL.value]
    completeness = [(rule, result) for rule, result in results if rule.group == "completeness"]
    judged = [result for _rule, result in completeness if result.verdict in (Verdict.PASS, Verdict.FAIL)]
    completeness_rate = (
        _round(sum(1 for result in judged if result.verdict is Verdict.PASS) / len(judged)) if judged else None
    )
    evaluated_points = sum(item.max_points for item in item_scores if item.status == "evaluated")
    gap_points = sum(item.max_points for item in item_scores if item.status == "data_gap")
    scorable_ratio = _round(evaluated_points / (evaluated_points + gap_points)) if evaluated_points + gap_points else 0.0

    return FrontpageQcOutcome(
        institute_id=doc.institute_id,
        patient_id=doc.patient_id,
        visit_id=doc.visit_id,
        ruleset_version=RULESET_VERSION,
        score=score,
        grade=grade_of(score),
        fail_count=sum(1 for f in fails if f.severity == Severity.DEDUCT.value),
        hint_count=sum(1 for f in fails if f.severity == Severity.HINT.value),
        required_missing_count=sum(1 for f in fails if f.severity == Severity.REQUIRED.value),
        data_gap_count=sum(1 for f in findings if f.verdict == Verdict.DATA_GAP.value),
        scorable_ratio=scorable_ratio,
        completeness_rate=completeness_rate,
        findings=findings,
        item_scores=item_scores,
        rule_verdicts={rule.rule_id: result.verdict.value for rule, result in results},
        input_fingerprint=input_fingerprint(doc),
        notes=list(doc.notes),
    )
