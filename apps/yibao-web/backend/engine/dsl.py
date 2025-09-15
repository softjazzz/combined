"""
质控引擎 DSL (Domain Specific Language) 定义
定义规则的数据模型和字段规范化逻辑
"""

from typing import Any, Dict, List, Optional, Union
from pydantic import BaseModel, Field, field_validator
from datetime import datetime
from enum import Enum


class Severity(str, Enum):
    """规则严重级别"""
    INFO = "info"
    WARN = "warn"
    BLOCK = "block"


class ActionType(str, Enum):
    """动作类型"""
    INTERCEPT = "intercept"
    WARN = "warn"
    NOTIFY = "notify"
    LOG = "log"


class TriggerEvent(str, Enum):
    """触发事件类型"""
    PRESCRIPTION_CREATE = "prescription_create"
    PRESCRIPTION_UPDATE = "prescription_update"
    ORDER_CREATE = "order_create"
    ORDER_UPDATE = "order_update"
    ORDER_DRUG_SUBMIT = "order.drug.submit"  # 添加医嘱提交事件
    PAYMENT_CALCULATE = "payment_calculate"
    SETTLEMENT = "settlement"


class Operator(str, Enum):
    """操作符类型"""
    EQ = "=="
    NE = "!="
    GT = ">"
    GTE = ">="
    LT = "<"
    LTE = "<="
    IN = "in"
    NOT_IN = "not_in"
    CONTAINS = "contains"
    NOT_CONTAINS = "not_contains"
    REGEX = "regex"
    BETWEEN = "between"
    EXISTS = "exists"


class AtomicCondition(BaseModel):
    """原子条件（叶子节点）"""
    fact: str = Field(..., description="事实字段路径，如 patient.age")
    operator: Operator = Field(..., description="操作符")
    value: Any = Field(..., description="比较值")
    
    @field_validator('operator', mode='before')
    @classmethod
    def normalize_operator(cls, v: Any) -> Operator:
        """规范化操作符字段（兼容 op 和 operator）"""
        if isinstance(v, str):
            # 处理简写形式
            if v == 'op':
                return v
            # 尝试转换为枚举
            try:
                return Operator(v)
            except ValueError:
                # 如果不是有效的操作符，保持原值（后续验证会报错）
                pass
        return v


class CompositeCondition(BaseModel):
    """组合条件（树形结构）"""
    all: Optional[List[Union['CompositeCondition', AtomicCondition]]] = None
    any: Optional[List[Union['CompositeCondition', AtomicCondition]]] = None
    
    @field_validator('all', 'any', mode='before')
    @classmethod
    def validate_conditions(cls, v: Any) -> Optional[List]:
        """验证条件列表"""
        if v is None:
            return None
        if not isinstance(v, list):
            raise ValueError(f"Conditions must be a list, got {type(v)}")
        return v
    
    def is_valid(self) -> bool:
        """检查组合条件是否有效（all 和 any 不能同时存在）"""
        return not (self.all is not None and self.any is not None)


# 使用 Union 来表示条件可以是原子的或组合的
Condition = Union[AtomicCondition, CompositeCondition]


class Action(BaseModel):
    """规则动作"""
    action_type: ActionType = Field(..., description="动作类型")
    message_template: Optional[str] = Field(None, description="消息模板")
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict, description="额外元数据")


class Rule(BaseModel):
    """质控规则模型"""
    id: Optional[int] = Field(None, description="规则ID")
    code: str = Field(..., description="规则编码")
    name: str = Field(..., description="规则名称")
    rule_type: Optional[str] = Field(None, description="规则类型")
    severity: Severity = Field(Severity.INFO, description="严重级别")
    enabled: bool = Field(True, description="是否启用")
    conditions: Union[CompositeCondition, List[AtomicCondition]] = Field(..., description="规则条件")
    actions: List[Action] = Field(default_factory=list, description="触发动作")
    triggers: List[TriggerEvent] = Field(default_factory=list, description="触发事件")
    message_template: Optional[str] = Field(None, description="消息模板（兼容旧格式）")
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    created_by: Optional[str] = None
    version: int = Field(1, description="规则版本")
    
    @field_validator('conditions', mode='before')
    @classmethod
    def normalize_conditions(cls, v: Any) -> Union[CompositeCondition, List[AtomicCondition]]:
        """
        规范化条件字段：
        1. 如果是列表（平铺的叶子条件），保持为列表（后续会在 model_post_init 中处理）
        2. 如果已经是树形结构，转换为相应的模型
        """
        if isinstance(v, list):
            # 平铺的叶子列表，保持为列表
            return v
        elif isinstance(v, dict):
            # 已经是树形结构
            if 'all' in v or 'any' in v:
                return CompositeCondition(**v)
            else:
                # 单个原子条件，包装为 CompositeCondition
                return CompositeCondition(all=[v])
        elif isinstance(v, (AtomicCondition, CompositeCondition)):
            # 已经是模型实例
            return v
        return v
    
    @field_validator('actions', mode='before')
    @classmethod
    def normalize_actions(cls, v: Any) -> List[Action]:
        """规范化动作字段"""
        if v is None:
            return []
        if not isinstance(v, list):
            v = [v]
        
        actions = []
        for action in v:
            if isinstance(action, dict):
                actions.append(Action(**action))
            elif isinstance(action, Action):
                actions.append(action)
        return actions
    
    @field_validator('triggers', mode='before')
    @classmethod
    def normalize_triggers(cls, v: Any) -> List[TriggerEvent]:
        """规范化触发器字段"""
        if v is None:
            return []
        if not isinstance(v, list):
            v = [v]
        
        triggers = []
        for trigger in v:
            if isinstance(trigger, str):
                try:
                    triggers.append(TriggerEvent(trigger))
                except ValueError:
                    # 忽略无效的触发器
                    pass
            elif isinstance(trigger, TriggerEvent):
                triggers.append(trigger)
        return triggers
    
    def model_post_init(self, __context: Any) -> None:
        """模型初始化后的处理"""
        # 如果条件是列表，转换为 CompositeCondition
        if isinstance(self.conditions, list):
            self.conditions = CompositeCondition(all=self.conditions)
        
        # 如果没有 actions 但有 message_template，创建默认 action
        if not self.actions and self.message_template:
            default_action_type = ActionType.INTERCEPT if self.severity == Severity.BLOCK else ActionType.WARN
            self.actions = [Action(
                action_type=default_action_type,
                message_template=self.message_template
            )]


class RuleSet(BaseModel):
    """规则集合"""
    rules: List[Rule] = Field(default_factory=list, description="规则列表")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="元数据")
    
    def get_active_rules(self) -> List[Rule]:
        """获取所有启用的规则"""
        return [rule for rule in self.rules if rule.enabled]
    
    def filter_by_trigger(self, trigger: TriggerEvent) -> List[Rule]:
        """根据触发事件过滤规则"""
        return [
            rule for rule in self.get_active_rules()
            if trigger in rule.triggers
        ]
    
    def filter_by_severity(self, severity: Severity) -> List[Rule]:
        """根据严重级别过滤规则"""
        return [
            rule for rule in self.get_active_rules()
            if rule.severity == severity
        ]


# 更新前向引用
CompositeCondition.model_rebuild()


def load_rule_from_json(data: Dict[str, Any]) -> Rule:
    """
    从 JSON 数据加载规则，进行字段兼容性处理
    """
    # 处理 op vs operator 的兼容性
    if 'conditions' in data:
        conditions = data['conditions']
        if isinstance(conditions, list):
            for cond in conditions:
                if isinstance(cond, dict) and 'op' in cond and 'operator' not in cond:
                    cond['operator'] = cond.pop('op')
        elif isinstance(conditions, dict):
            def process_condition(cond: Dict) -> Dict:
                if 'op' in cond and 'operator' not in cond:
                    cond['operator'] = cond.pop('op')
                if 'all' in cond:
                    cond['all'] = [process_condition(c) if isinstance(c, dict) else c for c in cond['all']]
                if 'any' in cond:
                    cond['any'] = [process_condition(c) if isinstance(c, dict) else c for c in cond['any']]
                return cond
            data['conditions'] = process_condition(conditions)
    
    return Rule(**data)


def load_rules_from_json_file(file_path: str) -> RuleSet:
    """
    从 JSON 文件加载规则集
    """
    import json
    
    with open(file_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    rules = []
    # 处理不同的 JSON 格式
    if isinstance(data, list):
        # 直接是规则列表
        for rule_data in data:
            try:
                rule = load_rule_from_json(rule_data)
                rules.append(rule)
            except Exception as e:
                print(f"Failed to load rule: {e}")
                continue
    elif isinstance(data, dict):
        # 可能包含 rules 字段
        if 'rules' in data:
            for rule_data in data['rules']:
                try:
                    rule = load_rule_from_json(rule_data)
                    rules.append(rule)
                except Exception as e:
                    print(f"Failed to load rule: {e}")
                    continue
    
    return RuleSet(rules=rules)
