#!/usr/bin/env python3
"""
质控引擎单元测试
"""

import json
import pytest
from typing import Dict, Any

from .dsl import Rule, RuleSet, Severity, ActionType, TriggerEvent, load_rule_from_json
from .operators import evaluate_operator, register_operator
from .templating import get_by_path, render_template
from .evaluator import RuleEngine, Decision
from .repository import RuleRepository


class TestOperators:
    """测试操作符"""
    
    def test_equality_operators(self):
        """测试相等性操作符"""
        assert evaluate_operator(5, "==", 5) == True
        assert evaluate_operator(5, "==", 3) == False
        assert evaluate_operator(5, "!=", 3) == True
        assert evaluate_operator(5, "!=", 5) == False
        
        # 测试空值
        assert evaluate_operator(None, "==", None) == True
        assert evaluate_operator(None, "==", 5) == False
        assert evaluate_operator(5, "==", None) == False
    
    def test_numeric_operators(self):
        """测试数值比较操作符"""
        assert evaluate_operator(5, ">", 3) == True
        assert evaluate_operator(3, ">", 5) == False
        assert evaluate_operator(5, ">=", 5) == True
        assert evaluate_operator(5, ">=", 3) == True
        assert evaluate_operator(3, "<", 5) == True
        assert evaluate_operator(5, "<=", 5) == True
        
        # 测试类型转换
        assert evaluate_operator("5", ">", "3") == True
        assert evaluate_operator("5.5", ">", 5) == True
        
        # 测试无效类型
        assert evaluate_operator("abc", ">", 5) == False
        assert evaluate_operator(None, ">", 5) == False
    
    def test_collection_operators(self):
        """测试集合操作符"""
        assert evaluate_operator("a", "in", ["a", "b", "c"]) == True
        assert evaluate_operator("d", "in", ["a", "b", "c"]) == False
        assert evaluate_operator("d", "not_in", ["a", "b", "c"]) == True
        assert evaluate_operator("a", "not_in", ["a", "b", "c"]) == False
        
        # 测试空值
        assert evaluate_operator(None, "in", ["a", "b"]) == False
        assert evaluate_operator("a", "in", None) == False
    
    def test_string_operators(self):
        """测试字符串操作符"""
        assert evaluate_operator("hello world", "contains", "world") == True
        assert evaluate_operator("hello world", "contains", "foo") == False
        assert evaluate_operator("hello world", "not_contains", "foo") == True
        assert evaluate_operator("hello world", "not_contains", "world") == False
    
    def test_regex_operator(self):
        """测试正则表达式操作符"""
        assert evaluate_operator("test123", "regex", r"\d+") == True
        assert evaluate_operator("test", "regex", r"\d+") == False
        assert evaluate_operator("abc@example.com", "regex", r"^[\w\.-]+@[\w\.-]+\.\w+$") == True
    
    def test_between_operator(self):
        """测试区间操作符"""
        assert evaluate_operator(5, "between", [3, 7]) == True
        assert evaluate_operator(3, "between", [3, 7]) == True
        assert evaluate_operator(7, "between", [3, 7]) == True
        assert evaluate_operator(2, "between", [3, 7]) == False
        assert evaluate_operator(8, "between", [3, 7]) == False
    
    def test_exists_operator(self):
        """测试存在性操作符"""
        assert evaluate_operator("value", "exists", True) == True
        assert evaluate_operator(None, "exists", True) == False
        assert evaluate_operator(None, "exists", False) == True
        assert evaluate_operator("value", "exists", False) == False
    
    def test_custom_operator(self):
        """测试自定义操作符"""
        def starts_with(left, right):
            if left is None or right is None:
                return False
            return str(left).startswith(str(right))
        
        register_operator("starts_with", starts_with)
        
        assert evaluate_operator("hello", "starts_with", "he") == True
        assert evaluate_operator("hello", "starts_with", "wo") == False


class TestTemplating:
    """测试模板引擎"""
    
    def test_get_by_path(self):
        """测试路径获取"""
        data = {
            "patient": {
                "name": "张三",
                "age": 30,
                "info": {
                    "address": "北京"
                }
            },
            "items": [
                {"name": "item1"},
                {"name": "item2"}
            ]
        }
        
        assert get_by_path(data, "patient.name") == "张三"
        assert get_by_path(data, "patient.age") == 30
        assert get_by_path(data, "patient.info.address") == "北京"
        assert get_by_path(data, "items[0].name") == "item1"
        assert get_by_path(data, "items[1].name") == "item2"
        assert get_by_path(data, "nonexistent", "default") == "default"
    
    def test_render_template(self):
        """测试模板渲染"""
        template = "患者 {patient.name} 的年龄是 {patient.age} 岁"
        facts = {
            "patient": {
                "name": "张三",
                "age": 30
            }
        }
        
        result = render_template(template, facts)
        assert result == "患者 张三 的年龄是 30 岁"
        
        # 测试缺失字段
        template = "患者 {patient.name} 的性别是 {patient.gender}"
        result = render_template(template, facts, keep_placeholders=True)
        assert result == "患者 张三 的性别是 {patient.gender}"
        
        result = render_template(template, facts, keep_placeholders=False)
        assert result == "患者 张三 的性别是 "


class TestDSL:
    """测试 DSL 模型"""
    
    def test_load_rule(self):
        """测试规则加载"""
        rule_data = {
            "code": "TEST_001",
            "name": "测试规则",
            "severity": "warn",
            "conditions": {
                "all": [
                    {"fact": "patient.age", "operator": ">", "value": 18},
                    {"fact": "patient.gender", "operator": "==", "value": "male"}
                ]
            },
            "actions": [
                {
                    "action_type": "warn",
                    "message_template": "患者 {patient.name} 符合条件"
                }
            ],
            "triggers": ["prescription_create"]
        }
        
        rule = load_rule_from_json(rule_data)
        
        assert rule.code == "TEST_001"
        assert rule.name == "测试规则"
        assert rule.severity == Severity.WARN
        assert len(rule.actions) == 1
        assert rule.actions[0].action_type == ActionType.WARN
        assert len(rule.triggers) == 1
        assert rule.triggers[0] == TriggerEvent.PRESCRIPTION_CREATE
    
    def test_normalize_conditions(self):
        """测试条件规范化"""
        # 测试平铺条件转换为 all
        rule_data = {
            "code": "TEST_002",
            "name": "测试规则",
            "conditions": [
                {"fact": "patient.age", "op": ">", "value": 18}
            ]
        }
        
        rule = load_rule_from_json(rule_data)
        assert hasattr(rule.conditions, 'all')
    
    def test_backward_compatibility(self):
        """测试向后兼容性"""
        # 测试 op vs operator
        rule_data = {
            "code": "TEST_003",
            "name": "测试规则",
            "conditions": {
                "all": [
                    {"fact": "patient.age", "op": ">", "value": 18}
                ]
            }
        }
        
        rule = load_rule_from_json(rule_data)
        assert rule.conditions.all[0].operator == ">"


class TestEvaluator:
    """测试执行引擎"""
    
    def test_simple_evaluation(self):
        """测试简单规则评估"""
        rule_data = {
            "code": "AGE_CHECK",
            "name": "年龄检查",
            "severity": "warn",
            "conditions": {
                "fact": "patient.age",
                "operator": ">",
                "value": 65
            },
            "actions": [
                {
                    "action_type": "warn",
                    "message_template": "患者年龄 {patient.age} 岁，超过 65 岁"
                }
            ]
        }
        
        rule = load_rule_from_json(rule_data)
        rule_set = RuleSet(rules=[rule])
        
        engine = RuleEngine()
        engine.load_rules(rule_set)
        
        # 测试命中
        context = {"patient": {"age": 70}}
        result = engine.evaluate(None, context, None)
        
        assert result.decision == Decision.WARN
        assert len(result.hits) == 1
        assert result.hits[0].rule_code == "AGE_CHECK"
        assert "患者年龄 70 岁" in result.hits[0].messages[0]
        
        # 测试未命中
        context = {"patient": {"age": 60}}
        result = engine.evaluate(None, context, None)
        
        assert result.decision == Decision.PASS
        assert len(result.hits) == 0
    
    def test_complex_conditions(self):
        """测试复杂条件"""
        rule_data = {
            "code": "COMPLEX_CHECK",
            "name": "复杂检查",
            "severity": "block",
            "conditions": {
                "all": [
                    {"fact": "patient.age", "operator": "<", "value": 18},
                    {
                        "any": [
                            {"fact": "drug.category", "operator": "==", "value": "adult_only"},
                            {"fact": "drug.category", "operator": "==", "value": "restricted"}
                        ]
                    }
                ]
            },
            "actions": [
                {
                    "action_type": "intercept",
                    "message_template": "未成年患者不能使用该药品"
                }
            ]
        }
        
        rule = load_rule_from_json(rule_data)
        rule_set = RuleSet(rules=[rule])
        
        engine = RuleEngine()
        engine.load_rules(rule_set)
        
        # 测试命中（未成年 + 成人药品）
        context = {
            "patient": {"age": 15},
            "drug": {"category": "adult_only"}
        }
        result = engine.evaluate(None, context, None)
        
        assert result.decision == Decision.BLOCK
        assert len(result.hits) == 1
        
        # 测试未命中（成年人）
        context = {
            "patient": {"age": 20},
            "drug": {"category": "adult_only"}
        }
        result = engine.evaluate(None, context, None)
        
        assert result.decision == Decision.PASS
        assert len(result.hits) == 0
        
        # 测试未命中（未成年但药品类别正常）
        context = {
            "patient": {"age": 15},
            "drug": {"category": "normal"}
        }
        result = engine.evaluate(None, context, None)
        
        assert result.decision == Decision.PASS
        assert len(result.hits) == 0
    
    def test_batch_evaluation(self):
        """测试批量评估"""
        rule_data = {
            "code": "BATCH_TEST",
            "name": "批量测试",
            "severity": "warn",
            "conditions": {
                "fact": "value",
                "operator": ">",
                "value": 50
            }
        }
        
        rule = load_rule_from_json(rule_data)
        rule_set = RuleSet(rules=[rule])
        
        engine = RuleEngine()
        engine.load_rules(rule_set)
        
        contexts = [
            {"value": 30},  # 不命中
            {"value": 60},  # 命中
            {"value": 70},  # 命中
            {"value": 40},  # 不命中
        ]
        
        results = engine.batch_evaluate(None, contexts, None)
        
        assert len(results) == 4
        assert results[0].decision == Decision.PASS
        assert results[1].decision == Decision.WARN
        assert results[2].decision == Decision.WARN
        assert results[3].decision == Decision.PASS


class TestRepository:
    """测试规则仓库"""
    
    def test_load_from_json(self):
        """测试从 JSON 加载"""
        # 创建临时 JSON 文件
        import tempfile
        import os
        
        rules_data = [
            {
                "code": "REPO_TEST_001",
                "name": "仓库测试1",
                "severity": "info",
                "enabled": True,
                "conditions": {"fact": "test", "operator": "==", "value": 1}
            },
            {
                "code": "REPO_TEST_002",
                "name": "仓库测试2",
                "severity": "warn",
                "enabled": False,
                "conditions": {"fact": "test", "operator": "==", "value": 2}
            }
        ]
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(rules_data, f)
            temp_file = f.name
        
        try:
            repo = RuleRepository()
            repo.set_json_file_path(temp_file)
            rule_set = repo.load(force_json=True)
            
            assert len(rule_set.rules) == 2
            assert rule_set.rules[0].code == "REPO_TEST_001"
            assert rule_set.rules[1].code == "REPO_TEST_002"
            
            # 测试获取活跃规则
            active_rules = rule_set.get_active_rules()
            assert len(active_rules) == 1
            assert active_rules[0].code == "REPO_TEST_001"
            
        finally:
            os.unlink(temp_file)
    
    def test_search_rules(self):
        """测试规则搜索"""
        rules_data = [
            {
                "code": "DRUG_001",
                "name": "药品规则1",
                "rule_type": "drug",
                "severity": "warn",
                "enabled": True,
                "conditions": {"fact": "test", "operator": "==", "value": 1}
            },
            {
                "code": "SERVICE_001",
                "name": "服务规则1",
                "rule_type": "service",
                "severity": "block",
                "enabled": True,
                "conditions": {"fact": "test", "operator": "==", "value": 2}
            }
        ]
        
        rule_set = RuleSet(rules=[load_rule_from_json(r) for r in rules_data])
        
        repo = RuleRepository()
        repo.rule_set = rule_set
        repo._build_cache_and_index()
        
        # 按关键字搜索
        results = repo.search_rules(keyword="药品")
        assert len(results) == 1
        assert results[0].code == "DRUG_001"
        
        # 按类型搜索
        results = repo.search_rules(rule_type="service")
        assert len(results) == 1
        assert results[0].code == "SERVICE_001"
        
        # 按严重级别搜索
        results = repo.search_rules(severity="block")
        assert len(results) == 1
        assert results[0].code == "SERVICE_001"


if __name__ == "__main__":
    # 运行测试
    pytest.main([__file__, "-v"])
