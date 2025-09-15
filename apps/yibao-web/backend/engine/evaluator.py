"""
质控规则执行引擎
负责编译和执行规则，生成评估结果
"""

import time
from typing import Any, Callable, Dict, List, Optional, Tuple, Union
from dataclasses import dataclass, field
from enum import Enum

from .dsl import (
    Rule, RuleSet, Condition, AtomicCondition, CompositeCondition,
    Severity, ActionType, TriggerEvent
)
from .operators import evaluate_operator
from .templating import get_by_path, render_template
from .repository import repository
from .resilience import (
    with_circuit_breaker, with_retry, fallback_handler,
    CircuitBreakerConfig, RetryConfig, DEFAULT_RETRY_CONFIG,
    CONSERVATIVE_CIRCUIT_CONFIG
)


class Decision(str, Enum):
    """决策结果"""
    PASS = "pass"
    WARN = "warn"
    BLOCK = "block"


@dataclass
class RuleHit:
    """规则命中记录"""
    rule_id: Optional[int]
    rule_code: str
    rule_name: str
    severity: Severity
    messages: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    execution_time_ms: float = 0.0


@dataclass
class EvaluationResult:
    """评估结果"""
    decision: Decision
    hits: List[RuleHit] = field(default_factory=list)
    execution_time_ms: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def add_hit(self, hit: RuleHit) -> None:
        """添加命中记录"""
        self.hits.append(hit)
        # 更新决策（取最严重的）
        self._update_decision(hit.severity)
    
    def _update_decision(self, severity: Severity) -> None:
        """根据严重级别更新决策"""
        if severity == Severity.BLOCK:
            self.decision = Decision.BLOCK
        elif severity == Severity.WARN and self.decision != Decision.BLOCK:
            self.decision = Decision.WARN
        # INFO 级别不改变决策


class CompiledRule:
    """编译后的规则"""
    
    def __init__(self, rule: Rule):
        self.rule = rule
        self.condition_func = self._compile_condition(rule.conditions)
        self._cached_placeholders: Optional[List[str]] = None
    
    def _compile_condition(self, condition: Union[Condition, CompositeCondition, List[AtomicCondition]]) -> Callable[[Dict[str, Any]], bool]:
        """
        编译条件为可执行函数
        
        Args:
            condition: 规则条件
        
        Returns:
            接收 facts 返回 bool 的函数
        """
        # 处理列表形式（已在 DSL 中转换为 CompositeCondition）
        if isinstance(condition, list):
            # 列表默认为 all 逻辑
            condition = CompositeCondition(all=condition)
        
        if isinstance(condition, AtomicCondition):
            # 原子条件
            return self._compile_atomic_condition(condition)
        elif isinstance(condition, CompositeCondition):
            # 组合条件
            return self._compile_composite_condition(condition)
        else:
            # 未知类型，返回总是 False 的函数
            return lambda facts: False
    
    def _compile_atomic_condition(self, condition: AtomicCondition) -> Callable[[Dict[str, Any]], bool]:
        """编译原子条件"""
        fact_path = condition.fact
        operator = condition.operator
        expected_value = condition.value
        
        def evaluate(facts: Dict[str, Any]) -> bool:
            # 从 facts 中获取实际值
            actual_value = get_by_path(facts, fact_path)
            # 执行操作符比较
            return evaluate_operator(actual_value, operator, expected_value)
        
        return evaluate
    
    def _compile_composite_condition(self, condition: CompositeCondition) -> Callable[[Dict[str, Any]], bool]:
        """编译组合条件"""
        if condition.all is not None:
            # AND 逻辑
            sub_funcs = [self._compile_condition(sub) for sub in condition.all]
            
            def evaluate_all(facts: Dict[str, Any]) -> bool:
                # 短路求值：遇到 False 立即返回
                for func in sub_funcs:
                    if not func(facts):
                        return False
                return True
            
            return evaluate_all
        
        elif condition.any is not None:
            # OR 逻辑
            sub_funcs = [self._compile_condition(sub) for sub in condition.any]
            
            def evaluate_any(facts: Dict[str, Any]) -> bool:
                # 短路求值：遇到 True 立即返回
                for func in sub_funcs:
                    if func(facts):
                        return True
                return False
            
            return evaluate_any
        
        else:
            # 空条件，返回总是 True 的函数
            return lambda facts: True
    
    def evaluate(self, facts: Dict[str, Any]) -> Tuple[bool, float]:
        """
        执行规则评估
        
        Args:
            facts: 事实数据
        
        Returns:
            (是否命中, 执行时间毫秒)
        """
        start_time = time.perf_counter()
        try:
            result = self.condition_func(facts)
        except Exception as e:
            print(f"Error evaluating rule {self.rule.code}: {e}")
            result = False
        
        execution_time = (time.perf_counter() - start_time) * 1000  # 转换为毫秒
        return result, execution_time
    
    def render_messages(self, facts: Dict[str, Any]) -> List[str]:
        """渲染规则消息"""
        messages = []
        
        # 渲染每个 action 的消息
        for action in self.rule.actions:
            if action.message_template:
                message = render_template(action.message_template, facts)
                messages.append(message)
        
        # 如果没有 action 但有顶层的 message_template（兼容旧格式）
        if not messages and self.rule.message_template:
            message = render_template(self.rule.message_template, facts)
            messages.append(message)
        
        # 如果还是没有消息，生成默认消息
        if not messages:
            messages.append(f"规则 {self.rule.name} 被触发")
        
        return messages


class RuleEngine:
    """规则执行引擎（增强版）"""

    def __init__(self):
        self._compiled_rules: Dict[str, CompiledRule] = {}
        self._rule_set: Optional[RuleSet] = None

        # 注册降级处理函数
        self._register_fallback_handlers()

    def _register_fallback_handlers(self):
        """注册降级处理函数"""
        # 规则评估降级：返回通过结果
        fallback_handler.register_fallback(
            "rule_evaluation",
            self._fallback_evaluation
        )

        # 批量评估降级：逐个处理
        fallback_handler.register_fallback(
            "batch_evaluation",
            self._fallback_batch_evaluation
        )

    def _fallback_evaluation(self, event_type, context, rule_ids=None) -> EvaluationResult:
        """降级评估：返回安全的通过结果"""
        result = EvaluationResult(decision=Decision.PASS)
        result.metadata['fallback_used'] = True
        result.metadata['fallback_reason'] = 'Primary evaluation failed'
        return result

    def _fallback_batch_evaluation(self, event_type, contexts, rule_ids=None) -> List[EvaluationResult]:
        """降级批量评估：逐个安全处理"""
        results = []
        for context in contexts:
            try:
                result = self._fallback_evaluation(event_type, context, rule_ids)
                results.append(result)
            except Exception:
                # 最后的安全网
                safe_result = EvaluationResult(decision=Decision.PASS)
                safe_result.metadata['fallback_used'] = True
                safe_result.metadata['fallback_reason'] = 'Both primary and fallback failed'
                results.append(safe_result)
        return results
    
    def load_rules(self, rule_set: RuleSet) -> None:
        """
        加载规则集
        
        Args:
            rule_set: 规则集
        """
        self._rule_set = rule_set
        self._compiled_rules.clear()
        
        # 编译所有启用的规则
        for rule in rule_set.get_active_rules():
            cache_key = f"{rule.code}_{rule.version}"
            self._compiled_rules[cache_key] = CompiledRule(rule)
    
    def evaluate(
        self,
        event_type: Optional[TriggerEvent],
        context: Dict[str, Any],
        rule_ids: Optional[List[int]] = None
    ) -> EvaluationResult:
        """
        执行规则评估
        
        Args:
            event_type: 触发事件类型
            context: 评估上下文（facts）
            rule_ids: 指定要执行的规则 ID 列表（可选）
        
        Returns:
            评估结果
        """
        start_time = time.perf_counter()
        result = EvaluationResult(decision=Decision.PASS)
        
        if not self._rule_set:
            result.metadata['error'] = 'No rules loaded'
            return result
        
        # 获取要执行的规则（带上下文预过滤）
        rules_to_evaluate = self._get_rules_to_evaluate(event_type, rule_ids, context)
        
        # 执行每条规则
        for rule in rules_to_evaluate:
            cache_key = f"{rule.code}_{rule.version}"
            compiled_rule = self._compiled_rules.get(cache_key)
            
            if not compiled_rule:
                # 规则未编译，跳过
                continue
            
            # 评估规则
            hit, exec_time = compiled_rule.evaluate(context)
            
            if hit:
                # 规则命中，创建命中记录
                messages = compiled_rule.render_messages(context)
                rule_hit = RuleHit(
                    rule_id=rule.id,
                    rule_code=rule.code,
                    rule_name=rule.name,
                    severity=rule.severity,
                    messages=messages,
                    execution_time_ms=exec_time
                )
                result.add_hit(rule_hit)
        
        # 计算总执行时间
        result.execution_time_ms = (time.perf_counter() - start_time) * 1000
        result.metadata['total_rules_evaluated'] = len(rules_to_evaluate)
        result.metadata['total_hits'] = len(result.hits)
        
        return result
    
    def batch_evaluate(
        self,
        event_type: Optional[TriggerEvent],
        contexts: List[Dict[str, Any]],
        rule_ids: Optional[List[int]] = None
    ) -> List[EvaluationResult]:
        """
        批量评估
        
        Args:
            event_type: 触发事件类型
            contexts: 评估上下文列表
            rule_ids: 指定要执行的规则 ID 列表（可选）
        
        Returns:
            评估结果列表
        """
        results = []
        
        # 预先获取要评估的规则（所有 context 使用相同的规则集）
        rules_to_evaluate = self._get_rules_to_evaluate(event_type, rule_ids, None)
        
        # 预编译规则（如果还没有编译）
        for rule in rules_to_evaluate:
            cache_key = f"{rule.code}_{rule.version}"
            if cache_key not in self._compiled_rules:
                self._compiled_rules[cache_key] = CompiledRule(rule)
        
        # 对每个 context 执行评估
        for context in contexts:
            result = self._evaluate_single(rules_to_evaluate, context)
            results.append(result)
        
        return results
    
    def _evaluate_single(
        self,
        rules: List[Rule],
        context: Dict[str, Any]
    ) -> EvaluationResult:
        """评估单个 context"""
        start_time = time.perf_counter()
        result = EvaluationResult(decision=Decision.PASS)
        
        for rule in rules:
            cache_key = f"{rule.code}_{rule.version}"
            compiled_rule = self._compiled_rules.get(cache_key)
            
            if not compiled_rule:
                continue
            
            hit, exec_time = compiled_rule.evaluate(context)
            
            if hit:
                messages = compiled_rule.render_messages(context)
                rule_hit = RuleHit(
                    rule_id=rule.id,
                    rule_code=rule.code,
                    rule_name=rule.name,
                    severity=rule.severity,
                    messages=messages,
                    execution_time_ms=exec_time
                )
                result.add_hit(rule_hit)
        
        result.execution_time_ms = (time.perf_counter() - start_time) * 1000
        return result
    
    def _get_rules_to_evaluate(
        self,
        event_type: Optional[TriggerEvent],
        rule_ids: Optional[List[int]],
        context: Optional[Dict[str, Any]]
    ) -> List[Rule]:
        """获取要评估的规则列表"""
        if not self._rule_set:
            return []
        
        # 从活跃规则开始
        rules = self._rule_set.get_active_rules()
        
        # 按触发事件过滤
        if event_type:
            rules = [r for r in rules if not r.triggers or event_type in r.triggers]
        
        # 按规则 ID 过滤
        if rule_ids:
            rules = [r for r in rules if r.id in rule_ids]

        # 基于上下文的轻量预过滤（使用仓库索引）
        if context:
            candidate_keys: set[str] = set()

            # 药品
            drug_code = get_by_path(context, 'drug.code') or get_by_path(context, 'drug.drug_code')
            drug_name = get_by_path(context, 'drug.name')
            if drug_code:
                candidate_keys |= repository.index.by_drug_code.get(str(drug_code), set())
            if drug_name:
                candidate_keys |= repository.index.by_drug_code.get(str(drug_name), set())

            # 服务
            service_code = get_by_path(context, 'service.code') or get_by_path(context, 'service.service_code')
            service_name = get_by_path(context, 'service.name')
            if service_code:
                candidate_keys |= repository.index.by_service_code.get(str(service_code), set())
            if service_name:
                candidate_keys |= repository.index.by_service_code.get(str(service_name), set())

            # 诊断
            diag_code = (
                get_by_path(context, 'diagnosis.main.code')
                or get_by_path(context, 'diagnose.code')
                or get_by_path(context, 'diagnosis.code')
            )
            if diag_code:
                candidate_keys |= repository.index.by_diagnosis_code.get(str(diag_code), set())

            # 科室
            dept_name = get_by_path(context, 'department.name')
            dept_code = get_by_path(context, 'department.code')
            if dept_name:
                candidate_keys |= repository.index.by_department.get(str(dept_name), set())
            if dept_code:
                candidate_keys |= repository.index.by_department.get(str(dept_code), set())

            if candidate_keys:
                # 将规则过滤为候选集合内的规则
                rules = [
                    r for r in rules
                    if f"{r.code}_{r.version}" in candidate_keys
                ]
        
        return rules
    
    def clear_cache(self) -> None:
        """清空编译缓存"""
        self._compiled_rules.clear()
    
    def get_stats(self) -> Dict[str, Any]:
        """获取引擎统计信息"""
        return {
            'total_rules_loaded': len(self._rule_set.rules) if self._rule_set else 0,
            'active_rules': len(self._rule_set.get_active_rules()) if self._rule_set else 0,
            'compiled_rules_cached': len(self._compiled_rules)
        }


# 创建全局引擎实例
engine = RuleEngine()


# 导出
__all__ = [
    'Decision',
    'RuleHit',
    'EvaluationResult',
    'CompiledRule',
    'RuleEngine',
    'engine'
]
