"""QC service: simple in-memory analysis generator and rule utilities.
Later, wrap real engines (e.g., SichuanQCService) with proper HTTP/timeouts.
"""

from typing import Dict, Any, List
from datetime import datetime
import uuid
import random

from ..schemas.qc import QCResult, QCIssue, QCSuggestion, QCRuleResult
from ..storage.memory import qc_rules_db


class QCService:
    async def evaluate(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        record_id = payload.get("record_id") or f"record-{uuid.uuid4().hex[:8]}"
        analysis_id = f"analysis-{uuid.uuid4().hex[:8]}"

        # Generate mock rule results based on existing rules
        rules = list(qc_rules_db.values())
        rule_results: List[QCRuleResult] = []
        issues: List[QCIssue] = []

        score_total = 0
        score_gain = 0
        for r in rules:
            weight = int(r.get("weight", 10))
            score_total += weight
            passed = bool(random.getrandbits(1))
            if passed:
                score_gain += weight
            rr = QCRuleResult(
                rule_id=r["id"],
                rule_name=r["name"],
                passed=passed,
                score=weight if passed else 0,
                details=f"规则执行详情：{'通过' if passed else '未通过'}质控检查",
            )
            rule_results.append(rr)
            if not passed:
                issues.append(
                    QCIssue(
                        id=f"issue-{uuid.uuid4().hex[:6]}",
                        rule_name=r["name"],
                        description=f"发现质控问题：{r['description']}",
                        severity=r.get("severity", "minor"),
                        category=r.get("category", "general"),
                        location="文档内容第3-5段",
                        suggestion="建议完善相关内容，确保符合医疗质控标准",
                    )
                )

        overall_score = int(100 * score_gain / max(score_total, 1))
        overall_grade = "A" if overall_score >= 90 else "B" if overall_score >= 75 else "C"
        suggestions = [
            QCSuggestion(
                id=f"sug-{uuid.uuid4().hex[:6]}",
                category="规范性",
                title="补充主诉描述",
                description="建议补充主诉持续时间与症状细节，提升记录完整度",
                priority="medium",
            )
        ]

        result = QCResult(
            id=analysis_id,
            record_id=record_id,
            overall_score=overall_score,
            overall_grade=overall_grade,
            analysis_date=datetime.utcnow().isoformat() + "Z",
            issues=issues,
            suggestions=suggestions,
            rule_results=rule_results,
        )
        return result.model_dump()
