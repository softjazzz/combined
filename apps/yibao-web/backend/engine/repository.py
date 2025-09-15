"""
规则仓库
负责从数据库或 JSON 文件加载规则，并提供索引和缓存功能
"""

import json
import os
from typing import Any, Dict, List, Optional, Set
from datetime import datetime
from pathlib import Path

from .dsl import Rule, RuleSet, TriggerEvent, load_rule_from_json, load_rules_from_json_file
from .templating import get_by_path


class RuleIndex:
    """规则索引，用于快速查找规则"""
    
    def __init__(self):
        self.by_trigger: Dict[TriggerEvent, Set[str]] = {}
        self.by_drug_code: Dict[str, Set[str]] = {}
        self.by_service_code: Dict[str, Set[str]] = {}
        self.by_diagnosis_code: Dict[str, Set[str]] = {}
        self.by_department: Dict[str, Set[str]] = {}
    
    def build(self, rules: List[Rule]) -> None:
        """构建索引"""
        self.clear()
        
        for rule in rules:
            rule_key = f"{rule.code}_{rule.version}"
            
            # 按触发事件索引
            for trigger in rule.triggers:
                if trigger not in self.by_trigger:
                    self.by_trigger[trigger] = set()
                self.by_trigger[trigger].add(rule_key)
            
            # 尝试从条件中提取关键字段进行索引
            self._index_by_conditions(rule, rule_key)
    
    def _index_by_conditions(self, rule: Rule, rule_key: str) -> None:
        """根据规则条件建立索引"""
        # 递归遍历条件树，抽取常见关键字段建立反向索引
        def walk(node):
            if node is None:
                return
            # AtomicCondition
            if hasattr(node, 'fact') and hasattr(node, 'operator'):
                fact_path = getattr(node, 'fact', '') or ''
                # 药品代码/名称
                if fact_path in ('drug.code', 'drug.drug_code', 'drug_name', 'drug.name'):
                    # 仅在等值/包含列表时建立值索引
                    op = str(getattr(node, 'operator', '') or '')
                    val = getattr(node, 'value', None)
                    if op in ('==', 'in') and val is not None:
                        if op == '==':
                            values = [val]
                        else:
                            values = val if isinstance(val, (list, tuple, set)) else [val]
                        for v in values:
                            key = str(v)
                            self.by_drug_code.setdefault(key, set()).add(rule_key)
                # 服务编码
                if fact_path in ('service.code', 'service.service_code', 'service.name'):
                    op = str(getattr(node, 'operator', '') or '')
                    val = getattr(node, 'value', None)
                    if op in ('==', 'in') and val is not None:
                        if op == '==':
                            values = [val]
                        else:
                            values = val if isinstance(val, (list, tuple, set)) else [val]
                        for v in values:
                            key = str(v)
                            self.by_service_code.setdefault(key, set()).add(rule_key)
                # 诊断编码
                if fact_path in ('diagnosis.code', 'diagnose.code', 'diagnosis.main.code'):
                    op = str(getattr(node, 'operator', '') or '')
                    val = getattr(node, 'value', None)
                    if op in ('==', 'in') and val is not None:
                        if op == '==':
                            values = [val]
                        else:
                            values = val if isinstance(val, (list, tuple, set)) else [val]
                        for v in values:
                            key = str(v)
                            self.by_diagnosis_code.setdefault(key, set()).add(rule_key)
                # 科室名称
                if fact_path in ('department.name', 'department.code'):
                    op = str(getattr(node, 'operator', '') or '')
                    val = getattr(node, 'value', None)
                    if op in ('==', 'in') and val is not None:
                        if op == '==':
                            values = [val]
                        else:
                            values = val if isinstance(val, (list, tuple, set)) else [val]
                        for v in values:
                            key = str(v)
                            self.by_department.setdefault(key, set()).add(rule_key)
                return
            # CompositeCondition
            if hasattr(node, 'all') and node.all:
                for sub in node.all:
                    walk(sub)
            if hasattr(node, 'any') and node.any:
                for sub in node.any:
                    walk(sub)

        # 入口：rule.conditions 可能已被规范化为 CompositeCondition
        walk(rule.conditions)
    
    def find_by_trigger(self, trigger: TriggerEvent) -> Set[str]:
        """根据触发事件查找规则"""
        return self.by_trigger.get(trigger, set())
    
    def find_by_drug_code(self, drug_code: str) -> Set[str]:
        """根据药品代码查找规则"""
        return self.by_drug_code.get(drug_code, set())
    
    def find_by_service_code(self, service_code: str) -> Set[str]:
        """根据服务代码查找规则"""
        return self.by_service_code.get(service_code, set())
    
    def clear(self) -> None:
        """清空索引"""
        self.by_trigger.clear()
        self.by_drug_code.clear()
        self.by_service_code.clear()
        self.by_diagnosis_code.clear()
        self.by_department.clear()


class RuleRepository:
    """
    规则仓库
    支持从数据库或 JSON 文件加载规则
    """
    
    def __init__(self, supabase_client=None):
        self.supabase = supabase_client
        self.rule_set: Optional[RuleSet] = None
        self.index = RuleIndex()
        self._cache: Dict[str, Rule] = {}  # rule_key -> Rule
        self._last_reload_time: Optional[datetime] = None
        self._json_file_path: Optional[str] = None
    
    def set_json_file_path(self, path: str) -> None:
        """设置 JSON 文件路径"""
        self._json_file_path = path
    
    def load(self, force_json: bool = False) -> RuleSet:
        """
        加载规则
        
        Args:
            force_json: 是否强制从 JSON 加载
        
        Returns:
            规则集
        """
        if not force_json and self.supabase:
            # 尝试从数据库加载
            try:
                rule_set = self._load_from_database()
                if rule_set and rule_set.rules:
                    self.rule_set = rule_set
                    self._build_cache_and_index()
                    self._last_reload_time = datetime.now()
                    return rule_set
            except Exception as e:
                print(f"Failed to load rules from database: {e}")
        
        # 从 JSON 文件加载（回退方案）
        if self._json_file_path:
            try:
                rule_set = load_rules_from_json_file(self._json_file_path)
                self.rule_set = rule_set
                self._build_cache_and_index()
                self._last_reload_time = datetime.now()
                return rule_set
            except Exception as e:
                print(f"Failed to load rules from JSON: {e}")
        
        # 如果都失败了，返回空规则集
        self.rule_set = RuleSet()
        return self.rule_set
    
    def _load_from_database(self) -> Optional[RuleSet]:
        """从数据库加载规则"""
        if not self.supabase:
            return None
        
        try:
            # 查询规则表
            response = self.supabase.table('yibao_rules').select('*').eq('enabled', True).execute()
            
            if not response.data:
                return None
            
            rules = []
            for rule_data in response.data:
                # 查询条件
                conditions_response = self.supabase.table('yibao_rule_conditions')\
                    .select('*')\
                    .eq('rule_id', rule_data['id'])\
                    .execute()
                
                # 查询动作
                actions_response = self.supabase.table('yibao_rule_actions')\
                    .select('*')\
                    .eq('rule_id', rule_data['id'])\
                    .execute()
                
                # 查询触发器
                triggers_response = self.supabase.table('yibao_rule_triggers')\
                    .select('*')\
                    .eq('rule_id', rule_data['id'])\
                    .execute()
                
                # 组装规则数据
                rule_dict = {
                    'id': rule_data['id'],
                    'code': rule_data['code'],
                    'name': rule_data['name'],
                    'rule_type': rule_data.get('rule_type'),
                    'severity': rule_data.get('severity', 'info'),
                    'enabled': rule_data.get('enabled', True),
                    'conditions': self._build_conditions_from_db(conditions_response.data),
                    'actions': [
                        {
                            'action_type': action['action_type'],
                            'message_template': action.get('message_template')
                        }
                        for action in (actions_response.data or [])
                    ],
                    'triggers': [
                        trigger['event_type']
                        for trigger in (triggers_response.data or [])
                    ],
                    'version': rule_data.get('version', 1)
                }
                
                try:
                    rule = load_rule_from_json(rule_dict)
                    rules.append(rule)
                except Exception as e:
                    print(f"Failed to load rule {rule_data['code']}: {e}")
                    continue
            
            return RuleSet(rules=rules)
        
        except Exception as e:
            print(f"Database query failed: {e}")
            return None
    
    def _build_conditions_from_db(self, conditions_data: List[Dict]) -> Dict[str, Any]:
        """从数据库记录构建条件树"""
        if not conditions_data:
            return {"all": []}
        
        # 简化处理：假设条件是平铺的
        conditions = []
        for cond in conditions_data:
            conditions.append({
                'fact': cond['fact'],
                'operator': cond['operator'],
                'value': cond['value']
            })
        
        return {"all": conditions}
    
    def _build_cache_and_index(self) -> None:
        """构建缓存和索引"""
        if not self.rule_set:
            return
        
        # 清空缓存
        self._cache.clear()
        
        # 构建缓存
        for rule in self.rule_set.rules:
            rule_key = f"{rule.code}_{rule.version}"
            self._cache[rule_key] = rule
        
        # 构建索引
        self.index.build(self.rule_set.rules)
    
    def get_rule(self, rule_code: str, version: int = 1) -> Optional[Rule]:
        """获取单条规则"""
        rule_key = f"{rule_code}_{version}"
        return self._cache.get(rule_key)
    
    def get_rules_by_trigger(self, trigger: TriggerEvent) -> List[Rule]:
        """根据触发事件获取规则"""
        if not self.rule_set:
            return []
        
        rule_keys = self.index.find_by_trigger(trigger)
        rules = []
        for key in rule_keys:
            rule = self._cache.get(key)
            if rule and rule.enabled:
                rules.append(rule)
        
        return rules
    
    def search_rules(
        self,
        keyword: Optional[str] = None,
        rule_type: Optional[str] = None,
        severity: Optional[str] = None,
        enabled_only: bool = True
    ) -> List[Rule]:
        """搜索规则"""
        if not self.rule_set:
            return []
        
        rules = self.rule_set.rules
        
        # 过滤启用状态
        if enabled_only:
            rules = [r for r in rules if r.enabled]
        
        # 按类型过滤
        if rule_type:
            rules = [r for r in rules if r.rule_type == rule_type]
        
        # 按严重级别过滤
        if severity:
            rules = [r for r in rules if r.severity == severity]
        
        # 按关键字搜索
        if keyword:
            keyword_lower = keyword.lower()
            rules = [
                r for r in rules
                if keyword_lower in r.code.lower() or
                   keyword_lower in r.name.lower()
            ]
        
        return rules
    
    def reload(self) -> bool:
        """
        重新加载规则
        
        Returns:
            是否成功
        """
        try:
            self.load()
            return True
        except Exception as e:
            print(f"Failed to reload rules: {e}")
            return False
    
    def get_stats(self) -> Dict[str, Any]:
        """获取仓库统计信息"""
        if not self.rule_set:
            return {
                'total_rules': 0,
                'active_rules': 0,
                'cached_rules': 0,
                'last_reload_time': None
            }
        
        return {
            'total_rules': len(self.rule_set.rules),
            'active_rules': len(self.rule_set.get_active_rules()),
            'cached_rules': len(self._cache),
            'indexed_triggers': len(self.index.by_trigger),
            'last_reload_time': self._last_reload_time.isoformat() if self._last_reload_time else None
        }
    
    def export_to_json(self, file_path: str) -> None:
        """导出规则到 JSON 文件"""
        if not self.rule_set:
            raise ValueError("No rules to export")
        
        rules_data = []
        for rule in self.rule_set.rules:
            rule_dict = rule.model_dump(exclude_none=True)
            # 转换枚举为字符串
            if 'severity' in rule_dict:
                rule_dict['severity'] = str(rule_dict['severity'])
            if 'triggers' in rule_dict:
                rule_dict['triggers'] = [str(t) for t in rule_dict['triggers']]
            if 'actions' in rule_dict:
                for action in rule_dict['actions']:
                    if 'action_type' in action:
                        action['action_type'] = str(action['action_type'])
            
            rules_data.append(rule_dict)
        
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(rules_data, f, ensure_ascii=False, indent=2)


# 创建全局仓库实例
repository = RuleRepository()


# 初始化默认 JSON 文件路径
default_json_path = os.path.join(
    os.path.dirname(os.path.dirname(__file__)),
    'medical_rules.json'
)
if os.path.exists(default_json_path):
    repository.set_json_file_path(default_json_path)


# 导出
__all__ = [
    'RuleIndex',
    'RuleRepository',
    'repository'
]
