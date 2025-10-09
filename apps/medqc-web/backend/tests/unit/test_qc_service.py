"""
质控服务单元测试
"""

import pytest
from unittest.mock import patch, MagicMock, Mock
from app.services.qc_service import normalize_rule, validate_rule_structure


@pytest.mark.unit
@pytest.mark.service
@pytest.mark.qc
class TestQCService:
    """质控服务测试类"""

    def test_normalize_rule_basic(self):
        """测试规则标准化 - 基本情况"""
        rule = {
            "id": "rule-1",
            "name": "入院记录完整性",
            "description": "检查入院记录是否完整",
            "category": "completeness",
            "severity": "major"
        }

        normalized = normalize_rule(rule)

        assert normalized["id"] == "rule-1"
        assert normalized["name"] == "入院记录完整性"
        assert normalized["category"] == "completeness"
        assert normalized["severity"] == "major"
        assert "weight" in normalized
        assert "is_active" in normalized

    def test_normalize_rule_with_defaults(self):
        """测试规则标准化 - 使用默认值"""
        rule = {
            "id": "rule-2",
            "name": "测试规则"
        }

        normalized = normalize_rule(rule)

        assert normalized["id"] == "rule-2"
        assert normalized["name"] == "测试规则"
        assert normalized["category"] == "other"  # 默认分类
        assert normalized["severity"] == "medium"  # 默认严重程度
        assert normalized["weight"] == 1  # 默认权重
        assert normalized["is_active"] is True  # 默认激活

    def test_normalize_rule_with_custom_weight(self):
        """测试规则标准化 - 自定义权重"""
        rule = {
            "id": "rule-3",
            "name": "重要规则",
            "weight": 10
        }

        normalized = normalize_rule(rule)

        assert normalized["weight"] == 10

    def test_normalize_rule_inactive(self):
        """测试规则标准化 - 非激活状态"""
        rule = {
            "id": "rule-4",
            "name": "已禁用规则",
            "is_active": False
        }

        normalized = normalize_rule(rule)

        assert normalized["is_active"] is False

    def test_normalize_rule_with_conditions(self):
        """测试规则标准化 - 包含条件"""
        rule = {
            "id": "rule-5",
            "name": "条件规则",
            "conditions": "age > 18 && department == '心内科'"
        }

        normalized = normalize_rule(rule)

        assert "conditions" in normalized
        assert normalized["conditions"] == "age > 18 && department == '心内科'"

    def test_normalize_rule_with_metadata(self):
        """测试规则标准化 - 包含元数据"""
        rule = {
            "id": "rule-6",
            "name": "元数据规则",
            "metadata": {
                "author": "张医生",
                "version": "1.0",
                "tags": ["重要", "常用"]
            }
        }

        normalized = normalize_rule(rule)

        assert "metadata" in normalized
        assert normalized["metadata"]["author"] == "张医生"
        assert normalized["metadata"]["version"] == "1.0"
        assert "重要" in normalized["metadata"]["tags"]

    def test_normalize_rule_empty_dict(self):
        """测试规则标准化 - 空字典"""
        rule = {}

        normalized = normalize_rule(rule)

        # 应该有默认值
        assert "category" in normalized
        assert "severity" in normalized
        assert "weight" in normalized
        assert "is_active" in normalized

    def test_normalize_rule_preserves_extra_fields(self):
        """测试规则标准化 - 保留额外字段"""
        rule = {
            "id": "rule-7",
            "name": "测试规则",
            "custom_field": "自定义值",
            "another_field": 123
        }

        normalized = normalize_rule(rule)

        assert normalized["custom_field"] == "自定义值"
        assert normalized["another_field"] == 123

    def test_validate_rule_structure_valid(self):
        """测试规则结构验证 - 有效规则"""
        rule = {
            "id": "rule-8",
            "name": "有效规则",
            "description": "这是一个有效的规则",
            "category": "completeness",
            "severity": "major"
        }

        is_valid, errors = validate_rule_structure(rule)

        assert is_valid is True
        assert len(errors) == 0

    def test_validate_rule_structure_missing_id(self):
        """测试规则结构验证 - 缺少 ID"""
        rule = {
            "name": "无ID规则",
            "description": "缺少ID"
        }

        is_valid, errors = validate_rule_structure(rule)

        assert is_valid is False
        assert any("id" in error.lower() for error in errors)

    def test_validate_rule_structure_missing_name(self):
        """测试规则结构验证 - 缺少名称"""
        rule = {
            "id": "rule-9",
            "description": "缺少名称"
        }

        is_valid, errors = validate_rule_structure(rule)

        assert is_valid is False
        assert any("name" in error.lower() for error in errors)

    def test_validate_rule_structure_invalid_severity(self):
        """测试规则结构验证 - 无效严重程度"""
        rule = {
            "id": "rule-10",
            "name": "无效严重程度",
            "severity": "invalid_severity"
        }

        is_valid, errors = validate_rule_structure(rule)

        assert is_valid is False
        assert any("severity" in error.lower() for error in errors)

    def test_validate_rule_structure_invalid_category(self):
        """测试规则结构验证 - 无效分类"""
        rule = {
            "id": "rule-11",
            "name": "无效分类",
            "category": "invalid_category"
        }

        is_valid, errors = validate_rule_structure(rule)

        assert is_valid is False
        assert any("category" in error.lower() for error in errors)

    def test_validate_rule_structure_invalid_weight(self):
        """测试规则结构验证 - 无效权重"""
        rule = {
            "id": "rule-12",
            "name": "无效权重",
            "weight": -1  # 权重应该是正数
        }

        is_valid, errors = validate_rule_structure(rule)

        assert is_valid is False
        assert any("weight" in error.lower() for error in errors)

    def test_validate_rule_structure_multiple_errors(self):
        """测试规则结构验证 - 多个错误"""
        rule = {
            # 缺少 id 和 name
            "severity": "invalid",
            "weight": -1
        }

        is_valid, errors = validate_rule_structure(rule)

        assert is_valid is False
        assert len(errors) >= 2  # 至少有2个错误

    @pytest.mark.parametrize("severity", ["minor", "medium", "major", "critical"])
    def test_normalize_rule_valid_severities(self, severity):
        """测试规则标准化 - 所有有效的严重程度"""
        rule = {
            "id": f"rule-{severity}",
            "name": f"规则-{severity}",
            "severity": severity
        }

        normalized = normalize_rule(rule)

        assert normalized["severity"] == severity

    @pytest.mark.parametrize("category", [
        "completeness", "accuracy", "timeliness", 
        "consistency", "compliance", "other"
    ])
    def test_normalize_rule_valid_categories(self, category):
        """测试规则标准化 - 所有有效的分类"""
        rule = {
            "id": f"rule-{category}",
            "name": f"规则-{category}",
            "category": category
        }

        normalized = normalize_rule(rule)

        assert normalized["category"] == category

    def test_normalize_rule_with_execution_stats(self):
        """测试规则标准化 - 包含执行统计"""
        rule = {
            "id": "rule-13",
            "name": "统计规则",
            "execution_count": 100,
            "pass_rate": 85.5,
            "issue_count": 15
        }

        normalized = normalize_rule(rule)

        assert normalized["execution_count"] == 100
        assert normalized["pass_rate"] == 85.5
        assert normalized["issue_count"] == 15

    def test_normalize_rule_with_timestamps(self):
        """测试规则标准化 - 包含时间戳"""
        rule = {
            "id": "rule-14",
            "name": "时间戳规则",
            "created_at": "2025-01-01T00:00:00Z",
            "updated_at": "2025-01-09T00:00:00Z"
        }

        normalized = normalize_rule(rule)

        assert normalized["created_at"] == "2025-01-01T00:00:00Z"
        assert normalized["updated_at"] == "2025-01-09T00:00:00Z"

    def test_normalize_rule_with_document_category(self):
        """测试规则标准化 - 包含文书类别"""
        rule = {
            "id": "rule-15",
            "name": "文书规则",
            "primary_document_category": "admission_record",
            "applicable_documents": ["admission_record", "discharge_summary"]
        }

        normalized = normalize_rule(rule)

        assert normalized["primary_document_category"] == "admission_record"
        assert "admission_record" in normalized["applicable_documents"]
        assert "discharge_summary" in normalized["applicable_documents"]

    def test_normalize_rule_immutability(self):
        """测试规则标准化 - 不修改原始规则"""
        original_rule = {
            "id": "rule-16",
            "name": "原始规则"
        }

        # 保存原始规则的副本
        original_copy = original_rule.copy()

        # 标准化规则
        normalized = normalize_rule(original_rule)

        # 验证原始规则未被修改
        assert original_rule == original_copy
        # 验证返回了新对象
        assert normalized is not original_rule

    def test_normalize_rule_with_none_values(self):
        """测试规则标准化 - 包含 None 值"""
        rule = {
            "id": "rule-17",
            "name": "None值规则",
            "description": None,
            "conditions": None
        }

        normalized = normalize_rule(rule)

        # None 值应该被保留或替换为默认值
        assert "description" in normalized
        assert "conditions" in normalized

    def test_normalize_rule_with_empty_strings(self):
        """测试规则标准化 - 包含空字符串"""
        rule = {
            "id": "rule-18",
            "name": "",  # 空名称
            "description": ""
        }

        normalized = normalize_rule(rule)

        # 空字符串应该被保留
        assert normalized["name"] == ""
        assert normalized["description"] == ""

    def test_normalize_rule_with_unicode(self):
        """测试规则标准化 - 包含 Unicode 字符"""
        rule = {
            "id": "rule-19",
            "name": "测试规则 🏥",
            "description": "包含 emoji 和中文字符"
        }

        normalized = normalize_rule(rule)

        assert normalized["name"] == "测试规则 🏥"
        assert normalized["description"] == "包含 emoji 和中文字符"

    def test_normalize_rule_with_nested_objects(self):
        """测试规则标准化 - 包含嵌套对象"""
        rule = {
            "id": "rule-20",
            "name": "嵌套规则",
            "config": {
                "threshold": 0.8,
                "options": {
                    "strict": True,
                    "ignore_case": False
                }
            }
        }

        normalized = normalize_rule(rule)

        assert normalized["config"]["threshold"] == 0.8
        assert normalized["config"]["options"]["strict"] is True
        assert normalized["config"]["options"]["ignore_case"] is False

