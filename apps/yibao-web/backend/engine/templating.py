"""
消息模板渲染引擎
支持从 facts 中提取数据并渲染消息模板
"""

import re
from typing import Any, Dict, Optional


def get_by_path(obj: Any, path: str, default: Any = None) -> Any:
    """
    通过点分隔的路径从嵌套对象中获取值
    
    Args:
        obj: 源对象
        path: 点分隔的路径，如 "patient.age" 或 "diagnosis.main.code"
        default: 找不到路径时的默认值
    
    Returns:
        路径对应的值，如果路径不存在则返回默认值
    
    Example:
        data = {"patient": {"age": 30, "name": "张三"}}
        get_by_path(data, "patient.age")  # 返回 30
        get_by_path(data, "patient.gender", "未知")  # 返回 "未知"
    """
    if obj is None:
        return default
    
    try:
        # 分割路径
        keys = path.split('.')
        result = obj
        
        for key in keys:
            if result is None:
                return default
            
            # 处理数组索引，如 items[0]
            array_match = re.match(r'^(.+)\[(\d+)\]$', key)
            if array_match:
                field_name, index = array_match.groups()
                index = int(index)
                
                # 先获取字段
                if isinstance(result, dict):
                    result = result.get(field_name, default)
                else:
                    result = getattr(result, field_name, default)
                
                # 再获取索引
                if isinstance(result, (list, tuple)) and 0 <= index < len(result):
                    result = result[index]
                else:
                    return default
            else:
                # 普通字段访问
                if isinstance(result, dict):
                    result = result.get(key, default)
                else:
                    result = getattr(result, key, default)
        
        return result
    except (AttributeError, KeyError, TypeError, IndexError):
        return default


def render_template(template: str, facts: Dict[str, Any], keep_placeholders: bool = True) -> str:
    """
    渲染消息模板，将 {path} 占位符替换为实际值
    
    Args:
        template: 消息模板，包含 {path} 格式的占位符
        facts: 包含数据的字典
        keep_placeholders: 是否保留找不到值的占位符
    
    Returns:
        渲染后的消息
    
    Example:
        template = "患者 {patient.name} 的年龄是 {patient.age} 岁"
        facts = {"patient": {"name": "张三", "age": 30}}
        render_template(template, facts)  # "患者 张三 的年龄是 30 岁"
    """
    if not template:
        return ""
    
    def replacer(match):
        """替换函数"""
        # 获取占位符中的路径
        path = match.group(1).strip()
        
        # 从 facts 中获取值
        value = get_by_path(facts, path)
        
        if value is None:
            # 如果找不到值
            if keep_placeholders:
                # 保留原始占位符
                return match.group(0)
            else:
                # 返回空字符串
                return ""
        
        # 转换为字符串
        return str(value)
    
    # 使用正则表达式替换所有 {path} 格式的占位符
    pattern = r'\{([^}]+)\}'
    result = re.sub(pattern, replacer, template)
    
    return result


def render_template_with_context(
    template: str,
    facts: Dict[str, Any],
    additional_context: Optional[Dict[str, Any]] = None,
    keep_placeholders: bool = True
) -> str:
    """
    使用 facts 和额外上下文渲染模板
    
    Args:
        template: 消息模板
        facts: 主要数据源
        additional_context: 额外的上下文数据
        keep_placeholders: 是否保留找不到值的占位符
    
    Returns:
        渲染后的消息
    """
    # 合并上下文
    context = facts.copy()
    if additional_context:
        context.update(additional_context)
    
    return render_template(template, context, keep_placeholders)


def extract_placeholders(template: str) -> list:
    """
    从模板中提取所有占位符路径
    
    Args:
        template: 消息模板
    
    Returns:
        占位符路径列表
    
    Example:
        template = "患者 {patient.name} 的年龄是 {patient.age} 岁"
        extract_placeholders(template)  # ["patient.name", "patient.age"]
    """
    if not template:
        return []
    
    pattern = r'\{([^}]+)\}'
    matches = re.findall(pattern, template)
    
    # 去重并保持顺序
    seen = set()
    result = []
    for path in matches:
        path = path.strip()
        if path not in seen:
            seen.add(path)
            result.append(path)
    
    return result


def validate_template(template: str) -> tuple[bool, Optional[str]]:
    """
    验证模板格式是否正确
    
    Args:
        template: 消息模板
    
    Returns:
        (是否有效, 错误信息)
    """
    if not template:
        return True, None
    
    # 检查大括号是否匹配
    open_count = template.count('{')
    close_count = template.count('}')
    
    if open_count != close_count:
        return False, f"大括号不匹配：{open_count} 个 '{{' 和 {close_count} 个 '}}'"
    
    # 检查是否有空的占位符
    if '{}' in template:
        return False, "存在空的占位符 {}"
    
    # 检查占位符格式
    pattern = r'\{([^}]+)\}'
    matches = re.findall(pattern, template)
    
    for match in matches:
        if not match.strip():
            return False, f"占位符内容不能为空：{{{match}}}"
        
        # 检查路径格式（简单验证）
        path = match.strip()
        if path.startswith('.') or path.endswith('.'):
            return False, f"无效的路径格式：{{{match}}}"
        
        # 检查是否包含非法字符
        if re.search(r'[^\w\.\[\]]+', path):
            return False, f"路径包含非法字符：{{{match}}}"
    
    return True, None


class TemplateEngine:
    """模板引擎类，支持缓存和批量渲染"""
    
    def __init__(self):
        self._cache: Dict[str, list] = {}  # 缓存提取的占位符
    
    def render(
        self,
        template: str,
        facts: Dict[str, Any],
        cache_key: Optional[str] = None,
        keep_placeholders: bool = True
    ) -> str:
        """
        渲染模板
        
        Args:
            template: 消息模板
            facts: 数据源
            cache_key: 缓存键，用于缓存占位符提取结果
            keep_placeholders: 是否保留找不到值的占位符
        
        Returns:
            渲染后的消息
        """
        if not template:
            return ""
        
        # 如果提供了缓存键，尝试使用缓存的占位符
        if cache_key and cache_key in self._cache:
            placeholders = self._cache[cache_key]
        else:
            placeholders = extract_placeholders(template)
            if cache_key:
                self._cache[cache_key] = placeholders
        
        # 构建替换字典
        replacements = {}
        for path in placeholders:
            value = get_by_path(facts, path)
            if value is not None:
                replacements[path] = str(value)
            elif not keep_placeholders:
                replacements[path] = ""
        
        # 执行替换
        result = template
        for path, value in replacements.items():
            result = result.replace(f"{{{path}}}", value)
        
        return result
    
    def render_batch(
        self,
        template: str,
        facts_list: list[Dict[str, Any]],
        keep_placeholders: bool = True
    ) -> list[str]:
        """
        批量渲染模板
        
        Args:
            template: 消息模板
            facts_list: 数据源列表
            keep_placeholders: 是否保留找不到值的占位符
        
        Returns:
            渲染后的消息列表
        """
        # 提取占位符（只需要做一次）
        placeholders = extract_placeholders(template)
        
        results = []
        for facts in facts_list:
            # 构建替换字典
            replacements = {}
            for path in placeholders:
                value = get_by_path(facts, path)
                if value is not None:
                    replacements[path] = str(value)
                elif not keep_placeholders:
                    replacements[path] = ""
            
            # 执行替换
            result = template
            for path, value in replacements.items():
                result = result.replace(f"{{{path}}}", value)
            
            results.append(result)
        
        return results
    
    def clear_cache(self):
        """清空缓存"""
        self._cache.clear()


# 创建全局模板引擎实例
template_engine = TemplateEngine()


# 导出常用函数
__all__ = [
    'get_by_path',
    'render_template',
    'render_template_with_context',
    'extract_placeholders',
    'validate_template',
    'TemplateEngine',
    'template_engine'
]
