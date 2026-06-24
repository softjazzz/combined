"""QC service: simple in-memory analysis generator and rule utilities.
Later, wrap real engines (e.g., SichuanQCService) with proper HTTP/timeouts.
"""

from typing import Dict, Any, List
from datetime import datetime, timedelta
import uuid

from ..schemas.qc import (
    QCResult,
    QCIssue,
    QCSuggestion,
    QCRuleResult,
    QCAnalysisStep,
)
from ..storage.memory import qc_rules_db


class QCService:
    async def evaluate(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Run a lightweight deterministic QC evaluation.

        The demo前端会传入病历内容、选中文书与规则，本方法根据这些信息
        生成一个稳定但富有语义的分析结果，以便在演示模式下模拟真实质控流程。
        """

        # ===== 基础上下文 =====
        record: Dict[str, Any] = payload.get("record") or {}
        record_id = payload.get("record_id") or record.get("id") or f"record-{uuid.uuid4().hex[:8]}"
        analysis_id = f"analysis-{uuid.uuid4().hex[:8]}"
        content: str = payload.get("content") or record.get("content") or ""
        documents: List[Dict[str, Any]] = payload.get("documents") or record.get("documents") or []
        rules_payload: List[Dict[str, Any]] = payload.get("rules") or []
        rule_ids: List[str] = payload.get("rule_ids") or []

        # ===== 规则归一化 =====
        def normalize_rule(raw: Dict[str, Any]) -> Dict[str, Any]:
            """
            归一化质控规则数据

            将来自不同来源的规则数据统一为标准格式，确保：
            - 所有必需字段都有默认值
            - 字段名称标准化
            - 数据类型正确

            Args:
                raw: 原始规则数据，可能包含不同的字段名和格式

            Returns:
                Dict[str, Any]: 标准化后的规则数据，包含以下字段：
                    - id: 规则唯一标识
                    - name: 规则名称
                    - description: 规则描述
                    - category: 规则类别（completeness, consistency等）
                    - severity: 严重程度（critical, major, medium, minor, low）
                    - weight: 权重（用于计算总分）
                    - rule_code: 规则编码

            Example:
                >>> raw = {"ruleCode": "R001", "ruleName": "入院记录完整性"}
                >>> normalized = normalize_rule(raw)
                >>> print(normalized["id"])  # "R001" or generated UUID
            """
            return {
                "id": str(raw.get("id") or raw.get("rule_id") or raw.get("ruleCode") or f"rule-{uuid.uuid4().hex[:6]}"),
                "name": str(raw.get("name") or raw.get("rule_name") or raw.get("ruleName") or "未命名规则"),
                "description": str(raw.get("description") or ""),
                "category": str(raw.get("category") or "general").lower(),
                "severity": str(raw.get("severity") or raw.get("defect_level") or "medium").lower(),
                "weight": int(float(raw.get("weight") or raw.get("max_score") or 10)),
                "rule_code": raw.get("rule_code") or raw.get("ruleCode") or "",
            }

        normalized_rules: List[Dict[str, Any]] = []
        if rules_payload:
            normalized_rules = [normalize_rule(r) for r in rules_payload if isinstance(r, dict)]
        elif rule_ids:
            for rid in rule_ids:
                data = qc_rules_db.get(rid)
                if data:
                    normalized_rules.append(normalize_rule(data))
        else:
            normalized_rules = [normalize_rule(r) for r in qc_rules_db.values()]

        if not normalized_rules:
            normalized_rules = [normalize_rule(r) for r in qc_rules_db.values()]

        # ===== 计算辅助变量 =====
        content_lower = content.lower()
        content_strength = min(30, max(0, len(content_lower) // 400 * 5))
        doc_types = {str(doc.get("type") or "").lower() for doc in documents if doc.get("type")}
        doc_titles = {str(doc.get("title") or "").lower() for doc in documents if doc.get("title")}

        CATEGORY_KEYWORDS: Dict[str, List[str]] = {
            "completeness": ["完整", "完整性", "补充"],
            "consistency": ["一致", "逻辑"],
            "rationality": ["合理", "依据"],
            "timeliness": ["及时", "时间"],
            "compliance": ["规范", "符合"],
        }
        CATEGORY_DOC_HINTS: Dict[str, set] = {
            "completeness": {"admission", "first_course", "record"},
            "consistency": {"progress", "daily"},
            "rationality": {"discharge", "summary"},
            "timeliness": {"nursing", "progress"},
            "compliance": {"operation", "surgery"},
        }
        SEVERITY_THRESHOLD = {
            "critical": 78,
            "major": 72,
            "medium": 68,
            "minor": 62,
            "low": 60,
        }

        rule_results: List[QCRuleResult] = []
        issues: List[QCIssue] = []
        suggestions: List[QCSuggestion] = []

        total_weight = sum(max(1, r["weight"]) for r in normalized_rules) or 1
        accumulated_score = 0

        for rule in normalized_rules:
            severity = rule["severity"]
            threshold = SEVERITY_THRESHOLD.get(severity, 65)
            keywords = CATEGORY_KEYWORDS.get(rule["category"], [])
            keyword_hits = sum(1 for kw in keywords if kw and kw in content_lower)
            keyword_bonus = min(12, keyword_hits * 6)

            doc_bonus = 0
            hint_targets = CATEGORY_DOC_HINTS.get(rule["category"], set())
            if hint_targets and doc_types.intersection(hint_targets):
                doc_bonus = 8
            elif documents:
                doc_bonus = 4

            score_components = 50 + content_strength + keyword_bonus + doc_bonus
            score_components = min(98, score_components)

            passed = score_components >= threshold
            weight = max(1, rule["weight"])
            if passed:
                accumulated_score += weight
            else:
                accumulated_score += int(weight * 0.5)

            execution_time = 400 + len(content) // 20 + weight * 5
            confidence = round(min(0.98, 0.55 + score_components / 200), 2)

            rule_result = QCRuleResult(
                rule_id=rule["id"],
                rule_name=rule["name"],
                passed=passed,
                score=int(score_components if passed else score_components * 0.6),
                details=(
                    f"⚙️ 规则 `{rule['name']}` 评估完成："
                    f"{'符合' if passed else '存在待改进项'}，评分 {score_components:.0f}"
                ),
                max_score=100,
                execution_time=execution_time,
                confidence=confidence,
            )
            rule_results.append(rule_result)

            if not passed:
                first_doc = documents[0] if documents else {}
                # 为不同类别的规则分配可匹配的 evidence 文本
                _evidence_map = {
                    "completeness": "主诉：发热3天伴咳嗽",
                    "consistency": "初步诊断：社区获得性肺炎",
                    "rationality": "症状未见明显好转，为求进一步诊治",
                    "timeliness": "入院日期：2026年2月15日",
                    "compliance": "诊疗计划",
                }
                evidence = _evidence_map.get(rule["category"], "体格检查")
                issues.append(
                    QCIssue(
                        id=f"issue-{uuid.uuid4().hex[:6]}",
                        rule_name=rule["name"],
                        description=rule["description"] or "需要进一步完善该项记录",
                        severity=severity,
                        category=rule["category"],
                        location=str(first_doc.get("title") or first_doc.get("type") or "病历正文"),
                        suggestion="请补充相关内容，确保符合医疗质控标准",
                        evidence=evidence,
                    )
                )

        # 总体评分与等级
        overall_score = int(accumulated_score / total_weight * 100)
        if overall_score >= 90:
            overall_grade = "A"
        elif overall_score >= 80:
            overall_grade = "B"
        elif overall_score >= 70:
            overall_grade = "C"
        else:
            overall_grade = "D"

        if not issues:
            suggestions.append(
                QCSuggestion(
                    id=f"sug-{uuid.uuid4().hex[:6]}",
                    category="质量保持",
                    title="保持文书质量",
                    description="当前质控结果良好，请持续保持规范记录。",
                    priority="low",
                )
            )
        else:
            suggestions.append(
                QCSuggestion(
                    id=f"sug-{uuid.uuid4().hex[:6]}",
                    category="整改建议",
                    title="完善重点文书内容",
                    description="针对未通过的规则逐项补充或修订，并在提交前再次核对。",
                    priority="medium",
                )
            )

        now = datetime.utcnow()
        step_start = now - timedelta(seconds=3)
        analysis_steps = [
            QCAnalysisStep(
                id="prepare",
                name="准备数据",
                description="整合病历、文书与质控规则",
                status="completed",
                started_at=step_start.isoformat() + "Z",
                completed_at=(step_start + timedelta(seconds=1)).isoformat() + "Z",
            ),
            QCAnalysisStep(
                id="engine",
                name="调用质控引擎",
                description="执行规则匹配与语义分析",
                status="completed",
                started_at=(step_start + timedelta(seconds=1)).isoformat() + "Z",
                completed_at=(step_start + timedelta(seconds=2)).isoformat() + "Z",
            ),
            QCAnalysisStep(
                id="aggregate",
                name="生成分析结果",
                description="整合规则评分，产出最终报告",
                status="completed",
                started_at=(step_start + timedelta(seconds=2)).isoformat() + "Z",
                completed_at=now.isoformat() + "Z",
            ),
        ]

        metadata: Dict[str, Any] = {
            "analysisId": analysis_id,
            "engine": "demo-qc-engine",
            "record": {
                "id": record_id,
                "patientName": record.get("patient_name") or record.get("patientName"),
                "department": record.get("department"),
            },
            "documents": documents,
            "rulesApplied": len(normalized_rules),
            "scoreBaseline": {
                "contentStrength": content_strength,
                "documentBonus": len(documents),
            },
        }

        result = QCResult(
            id=analysis_id,
            record_id=record_id,
            overall_score=overall_score,
            overall_grade=overall_grade,
            analysis_date=now.isoformat() + "Z",
            issues=issues,
            suggestions=suggestions,
            rule_results=rule_results,
            analysis_steps=analysis_steps,
            metadata=metadata,
        )
        return result.model_dump()
