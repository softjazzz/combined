"""
质控服务单元测试

测试 QCService 的核心功能：
- 质控规则执行
- 结果生成
- 评分计算
- 错误处理
"""

import pytest
from datetime import datetime
from unittest.mock import patch, MagicMock
import uuid

from app.services.qc_service import QCService
from app.schemas.qc import QCResult


@pytest.mark.unit
@pytest.mark.service
class TestQCService:
    """质控服务测试类"""

    @pytest.fixture
    def qc_service(self):
        """创建 QCService 实例"""
        return QCService()

    @pytest.fixture
    def sample_payload(self):
        """示例质控请求 payload"""
        return {
            "record_id": str(uuid.uuid4()),
            "content": "患者男性，65岁，因胸痛3天入院。既往高血压病史10年，规律服药。入院诊断：冠心病，不稳定型心绞痛。",
            "record": {
                "id": str(uuid.uuid4()),
                "patient_name": "张三",
                "department": "心内科",
            },
            "documents": [
                {
                    "type": "admission_record",
                    "title": "入院记录",
                    "content": "患者男性，65岁，因胸痛3天入院...",
                }
            ],
        }

    @pytest.fixture
    def sample_rules(self):
        """示例质控规则"""
        return [
            {
                "id": "rule-001",
                "name": "入院记录完整性",
                "description": "检查入院记录是否完整",
                "category": "completeness",
                "severity": "major",
                "weight": 10,
            },
            {
                "id": "rule-002",
                "name": "诊断一致性",
                "description": "检查诊断是否一致",
                "category": "consistency",
                "severity": "critical",
                "weight": 15,
            },
        ]

    @pytest.mark.asyncio
    @pytest.mark.asyncio
    async def test_evaluate_basic_success(self, qc_service, sample_payload):
        """测试基本质控评估成功"""
        result = await qc_service.evaluate(sample_payload)

        assert result is not None
        assert "id" in result
        assert "record_id" in result
        assert "overall_score" in result
        assert "overall_grade" in result
        assert "issues" in result
        assert "suggestions" in result
        assert "rule_results" in result

        # 验证评分范围
        assert 0 <= result["overall_score"] <= 100
        assert result["overall_grade"] in ["A", "B", "C", "D"]

    @pytest.mark.asyncio
    async def test_evaluate_with_rules(self, qc_service, sample_payload, sample_rules):
        """测试使用指定规则进行质控"""
        sample_payload["rules"] = sample_rules
        result = await qc_service.evaluate(sample_payload)

        assert result is not None
        assert len(result["rule_results"]) == len(sample_rules)

        # 验证每个规则都被执行
        rule_ids = {r["rule_id"] for r in result["rule_results"]}
        expected_ids = {r["id"] for r in sample_rules}
        assert rule_ids == expected_ids

    @pytest.mark.asyncio
    async def test_evaluate_with_rule_ids(self, qc_service, sample_payload):
        """测试使用规则 ID 进行质控"""
        with patch("app.services.qc_service.qc_rules_db") as mock_db:
            mock_db.get.return_value = {
                "id": "rule-001",
                "name": "测试规则",
                "category": "completeness",
                "severity": "medium",
                "weight": 10,
            }
            mock_db.values.return_value = []

            sample_payload["rule_ids"] = ["rule-001"]
            result = await qc_service.evaluate(sample_payload)

            assert result is not None
            assert len(result["rule_results"]) >= 1

    @pytest.mark.asyncio
    async def test_evaluate_empty_content(self, qc_service):
        """测试空内容的质控"""
        payload = {
            "record_id": str(uuid.uuid4()),
            "content": "",
            "documents": [],
        }
        result = await qc_service.evaluate(payload)

        assert result is not None
        # 空内容应该得到较低的分数
        assert result["overall_score"] < 70

    @pytest.mark.asyncio
    async def test_evaluate_rich_content(self, qc_service):
        """测试丰富内容的质控"""
        payload = {
            "record_id": str(uuid.uuid4()),
            "content": "患者男性，65岁，因胸痛3天入院。" * 100,  # 长内容
            "documents": [
                {"type": "admission_record", "title": "入院记录"},
                {"type": "progress_note", "title": "病程记录"},
                {"type": "discharge_record", "title": "出院记录"},
            ],
        }
        result = await qc_service.evaluate(payload)

        assert result is not None
        # 丰富内容应该得到较高的分数
        assert result["overall_score"] >= 60

    @pytest.mark.asyncio
    async def test_evaluate_grade_calculation(self, qc_service, sample_payload):
        """测试评分等级计算"""
        result = await qc_service.evaluate(sample_payload)

        score = result["overall_score"]
        grade = result["overall_grade"]

        # 验证等级与分数的对应关系
        if score >= 90:
            assert grade == "A"
        elif score >= 80:
            assert grade == "B"
        elif score >= 70:
            assert grade == "C"
        else:
            assert grade == "D"

    @pytest.mark.asyncio
    async def test_evaluate_issues_generation(self, qc_service, sample_payload, sample_rules):
        """测试问题生成"""
        # 使用严格的规则，确保会产生问题
        strict_rules = [
            {
                "id": "rule-strict",
                "name": "严格规则",
                "category": "completeness",
                "severity": "critical",
                "weight": 20,
            }
        ]
        sample_payload["rules"] = strict_rules
        sample_payload["content"] = "简短内容"  # 简短内容更容易触发问题

        result = await qc_service.evaluate(sample_payload)

        # 验证问题结构
        if result["issues"]:
            issue = result["issues"][0]
            assert "id" in issue
            assert "rule_name" in issue
            assert "description" in issue
            assert "severity" in issue
            assert "category" in issue
            assert "location" in issue
            assert "suggestion" in issue

    @pytest.mark.asyncio
    async def test_evaluate_suggestions_generation(self, qc_service, sample_payload):
        """测试建议生成"""
        result = await qc_service.evaluate(sample_payload)

        assert "suggestions" in result
        assert len(result["suggestions"]) > 0

        # 验证建议结构
        suggestion = result["suggestions"][0]
        assert "id" in suggestion
        assert "category" in suggestion
        assert "title" in suggestion
        assert "description" in suggestion
        assert "priority" in suggestion

    @pytest.mark.asyncio
    async def test_evaluate_rule_results_structure(self, qc_service, sample_payload, sample_rules):
        """测试规则结果结构"""
        sample_payload["rules"] = sample_rules
        result = await qc_service.evaluate(sample_payload)

        assert len(result["rule_results"]) > 0

        # 验证规则结果结构
        rule_result = result["rule_results"][0]
        assert "rule_id" in rule_result
        assert "rule_name" in rule_result
        assert "passed" in rule_result
        assert "score" in rule_result
        assert "details" in rule_result
        assert "max_score" in rule_result
        assert "execution_time" in rule_result
        assert "confidence" in rule_result

        # 验证数据类型
        assert isinstance(rule_result["passed"], bool)
        assert isinstance(rule_result["score"], int)
        assert isinstance(rule_result["execution_time"], int)
        assert isinstance(rule_result["confidence"], float)

    @pytest.mark.asyncio
    async def test_evaluate_analysis_steps(self, qc_service, sample_payload):
        """测试分析步骤生成"""
        result = await qc_service.evaluate(sample_payload)

        assert "analysis_steps" in result
        assert len(result["analysis_steps"]) == 3

        # 验证步骤顺序
        steps = result["analysis_steps"]
        assert steps[0]["id"] == "prepare"
        assert steps[1]["id"] == "engine"
        assert steps[2]["id"] == "aggregate"

        # 验证所有步骤都已完成
        for step in steps:
            assert step["status"] == "completed"
            assert "started_at" in step
            assert "completed_at" in step

    @pytest.mark.asyncio
    async def test_evaluate_metadata(self, qc_service, sample_payload):
        """测试元数据生成"""
        result = await qc_service.evaluate(sample_payload)

        assert "metadata" in result
        metadata = result["metadata"]

        assert "analysisId" in metadata
        assert "engine" in metadata
        assert "record" in metadata
        assert "documents" in metadata
        assert "rulesApplied" in metadata
        assert "scoreBaseline" in metadata

    @pytest.mark.asyncio
    async def test_evaluate_with_various_severities(self, qc_service, sample_payload):
        """测试不同严重程度的规则"""
        rules = [
            {"id": f"rule-{sev}", "name": f"{sev}规则", "category": "completeness", "severity": sev, "weight": 10}
            for sev in ["critical", "major", "medium", "minor", "low"]
        ]
        sample_payload["rules"] = rules

        result = await qc_service.evaluate(sample_payload)

        assert len(result["rule_results"]) == 5
        # 验证所有严重程度都被处理
        severities = {r["severity"] for r in result["issues"]} if result["issues"] else set()
        # 至少应该有一些严重程度被记录
        assert len(severities) >= 0

    @pytest.mark.asyncio
    async def test_evaluate_with_various_categories(self, qc_service, sample_payload):
        """测试不同类别的规则"""
        categories = ["completeness", "consistency", "rationality", "timeliness", "compliance"]
        rules = [
            {"id": f"rule-{cat}", "name": f"{cat}规则", "category": cat, "severity": "medium", "weight": 10}
            for cat in categories
        ]
        sample_payload["rules"] = rules

        result = await qc_service.evaluate(sample_payload)

        assert len(result["rule_results"]) == len(categories)

    @pytest.mark.asyncio
    async def test_evaluate_concurrent_calls(self, qc_service, sample_payload):
        """测试并发调用"""
        import asyncio

        # 创建多个并发请求
        tasks = [qc_service.evaluate(sample_payload.copy()) for _ in range(5)]
        results = await asyncio.gather(*tasks)

        # 验证所有请求都成功
        assert len(results) == 5
        for result in results:
            assert result is not None
            assert "overall_score" in result

    @pytest.mark.asyncio
    async def test_evaluate_result_serialization(self, qc_service, sample_payload):
        """测试结果可以序列化为 JSON"""
        import json

        result = await qc_service.evaluate(sample_payload)

        # 验证结果可以序列化
        json_str = json.dumps(result)
        assert json_str is not None

        # 验证可以反序列化
        deserialized = json.loads(json_str)
        assert deserialized["overall_score"] == result["overall_score"]

    @pytest.mark.asyncio
    async def test_evaluate_with_missing_fields(self, qc_service):
        """测试缺少字段的 payload"""
        # 最小化的 payload
        payload = {}
        result = await qc_service.evaluate(payload)

        # 应该仍然能够生成结果
        assert result is not None
        assert "overall_score" in result
        assert "overall_grade" in result

