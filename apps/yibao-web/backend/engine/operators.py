"""
可插拔的操作符注册表
支持所有比较操作符的实现，并允许动态注册新操作符
"""

import re
from typing import Any, Callable, Dict, Optional
from functools import wraps


class OperatorRegistry:
    """操作符注册表"""
    
    def __init__(self):
        self._operators: Dict[str, Callable[[Any, Any], bool]] = {}
        self._register_default_operators()
    
    def register(self, name: str, func: Callable[[Any, Any], bool]) -> None:
        """
        注册一个新的操作符
        
        Args:
            name: 操作符名称
            func: 操作符实现函数，接收 (left_value, right_value) 返回 bool
        """
        self._operators[name] = func
    
    def get(self, name: str) -> Optional[Callable]:
        """获取操作符函数"""
        return self._operators.get(name)
    
    def evaluate(self, left: Any, operator: str, right: Any) -> bool:
        """
        执行操作符比较
        
        Args:
            left: 左值（通常是 fact 的值）
            operator: 操作符名称
            right: 右值（规则中定义的比较值）
        
        Returns:
            比较结果
        """
        func = self.get(operator)
        if func is None:
            # 未知操作符，返回 False 并记录警告
            print(f"Warning: Unknown operator '{operator}'")
            return False
        
        try:
            return func(left, right)
        except Exception as e:
            # 操作符执行失败，返回 False
            print(f"Error evaluating operator '{operator}': {e}")
            return False
    
    def _register_default_operators(self) -> None:
        """注册默认操作符"""
        
        # 相等性操作符
        self.register("==", self._op_eq)
        self.register("!=", self._op_ne)
        
        # 数值比较操作符
        self.register(">", self._op_gt)
        self.register(">=", self._op_gte)
        self.register("<", self._op_lt)
        self.register("<=", self._op_lte)
        
        # 集合操作符
        self.register("in", self._op_in)
        self.register("not_in", self._op_not_in)
        
        # 字符串操作符
        self.register("contains", self._op_contains)
        self.register("not_contains", self._op_not_contains)
        
        # 正则表达式
        self.register("regex", self._op_regex)
        
        # 区间操作符
        self.register("between", self._op_between)
        
        # 存在性检查
        self.register("exists", self._op_exists)
    
    @staticmethod
    def _safe_numeric(func: Callable) -> Callable:
        """装饰器：安全的数值比较"""
        @wraps(func)
        def wrapper(left: Any, right: Any) -> bool:
            if left is None or right is None:
                return False
            try:
                # 尝试转换为数值
                left_num = float(left)
                right_num = float(right)
                return func(left_num, right_num)
            except (TypeError, ValueError):
                return False
        return wrapper
    
    @staticmethod
    def _op_eq(left: Any, right: Any) -> bool:
        """相等操作符"""
        if left is None and right is None:
            return True
        if left is None or right is None:
            return False
        return left == right
    
    @staticmethod
    def _op_ne(left: Any, right: Any) -> bool:
        """不等操作符"""
        if left is None and right is None:
            return False
        if left is None or right is None:
            return True
        return left != right
    
    @staticmethod
    @_safe_numeric
    def _op_gt(left: float, right: float) -> bool:
        """大于操作符"""
        return left > right
    
    @staticmethod
    @_safe_numeric
    def _op_gte(left: float, right: float) -> bool:
        """大于等于操作符"""
        return left >= right
    
    @staticmethod
    @_safe_numeric
    def _op_lt(left: float, right: float) -> bool:
        """小于操作符"""
        return left < right
    
    @staticmethod
    @_safe_numeric
    def _op_lte(left: float, right: float) -> bool:
        """小于等于操作符"""
        return left <= right
    
    @staticmethod
    def _op_in(left: Any, right: Any) -> bool:
        """包含操作符"""
        if right is None:
            return False
        if not hasattr(right, '__contains__'):
            return False
        try:
            return left in right
        except (TypeError, ValueError):
            return False
    
    @staticmethod
    def _op_not_in(left: Any, right: Any) -> bool:
        """不包含操作符"""
        if right is None:
            return True
        if not hasattr(right, '__contains__'):
            return True
        try:
            return left not in right
        except (TypeError, ValueError):
            return True
    
    @staticmethod
    def _op_contains(left: Any, right: Any) -> bool:
        """字符串包含操作符"""
        if left is None or right is None:
            return False
        try:
            left_str = str(left)
            right_str = str(right)
            return right_str in left_str
        except (TypeError, ValueError):
            return False
    
    @staticmethod
    def _op_not_contains(left: Any, right: Any) -> bool:
        """字符串不包含操作符"""
        if left is None:
            return True
        if right is None:
            return True
        try:
            left_str = str(left)
            right_str = str(right)
            return right_str not in left_str
        except (TypeError, ValueError):
            return True
    
    @staticmethod
    def _op_regex(left: Any, right: Any) -> bool:
        """正则表达式匹配操作符"""
        if left is None or right is None:
            return False
        try:
            left_str = str(left)
            pattern = str(right)
            return bool(re.search(pattern, left_str))
        except (TypeError, ValueError, re.error):
            return False
    
    @staticmethod
    def _op_between(left: Any, right: Any) -> bool:
        """
        区间操作符
        right 应该是一个包含两个元素的列表或元组 [min, max]
        """
        if left is None or right is None:
            return False
        try:
            if not isinstance(right, (list, tuple)) or len(right) != 2:
                return False
            
            left_num = float(left)
            min_val = float(right[0])
            max_val = float(right[1])
            
            return min_val <= left_num <= max_val
        except (TypeError, ValueError, IndexError):
            return False
    
    @staticmethod
    def _op_exists(left: Any, right: Any) -> bool:
        """
        存在性检查操作符
        right 为 True 时检查 left 是否存在（非 None）
        right 为 False 时检查 left 是否不存在（为 None）
        """
        exists = left is not None
        expected = bool(right)
        return exists == expected


# 全局操作符注册表实例
operator_registry = OperatorRegistry()


def register_operator(name: str, func: Callable[[Any, Any], bool]) -> None:
    """
    全局函数：注册自定义操作符
    
    Example:
        def my_custom_op(left, right):
            return left.startswith(right)
        
        register_operator("starts_with", my_custom_op)
    """
    operator_registry.register(name, func)


def evaluate_operator(left: Any, operator: str, right: Any) -> bool:
    """
    全局函数：执行操作符比较
    
    Args:
        left: 左值
        operator: 操作符名称
        right: 右值
    
    Returns:
        比较结果
    """
    return operator_registry.evaluate(left, operator, right)


# 导出常用函数
__all__ = [
    'OperatorRegistry',
    'operator_registry',
    'register_operator',
    'evaluate_operator'
]
