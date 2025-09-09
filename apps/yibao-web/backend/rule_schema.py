"""
医保规则数字化JSON格式定义
定义了统一的数据结构来表示各种类型的医保规则
"""

from typing import List, Dict, Any, Optional, Union
from pydantic import BaseModel, Field
from enum import Enum

class RuleType(str, Enum):
    """规则类型枚举"""
    DRUG_GENDER = "drug_gender"           # 药品性别限制
    DRUG_AGE = "drug_age"                 # 药品年龄限制
    DRUG_CHILDREN_ONLY = "drug_children_only"  # 儿童专用药品
    DRUG_CHILDREN_LIMIT = "drug_children_limit"  # 限制儿童使用
    DRUG_INSURANCE_TYPE = "drug_insurance_type"  # 保险类型限制
    DRUG_HOSPITAL_LEVEL = "drug_hospital_level"  # 医疗机构级别限制
    DRUG_PAYMENT_COURSE = "drug_payment_course"  # 支付疗程限制
    DRUG_VISIT_TYPE = "drug_visit_type"   # 就医方式限制
    SERVICE_GENDER = "service_gender"     # 医疗服务性别限制
    SURGERY_PRICING = "surgery_pricing"   # 手术项目定价规则

class SeverityLevel(str, Enum):
    """严重级别枚举"""
    INFO = "info"       # 信息提示
    WARN = "warn"       # 警告
    BLOCK = "block"     # 拦截

class OperatorType(str, Enum):
    """操作符类型"""
    EQUALS = "=="
    NOT_EQUALS = "!="
    GREATER_THAN = ">"
    GREATER_EQUAL = ">="
    LESS_THAN = "<"
    LESS_EQUAL = "<="
    IN = "in"
    NOT_IN = "not_in"
    CONTAINS = "contains"
    NOT_CONTAINS = "not_contains"
    REGEX = "regex"

class TriggerEvent(str, Enum):
    """触发事件类型"""
    PRESCRIPTION_CREATE = "prescription_create"    # 处方开立
    PRESCRIPTION_UPDATE = "prescription_update"    # 处方修改
    ORDER_CREATE = "order_create"                  # 医嘱录入
    ORDER_UPDATE = "order_update"                  # 医嘱修改
    PAYMENT_CALCULATE = "payment_calculate"        # 费用计算
    SETTLEMENT = "settlement"                      # 结算

class RuleCondition(BaseModel):
    """规则条件"""
    fact: str = Field(..., description="事实字段路径，如 patient.age, drug.name")
    operator: OperatorType = Field(..., description="操作符")
    value: Union[str, int, float, List[str], Dict[str, Any]] = Field(..., description="比较值")
    description: Optional[str] = Field(None, description="条件描述")

class RuleAction(BaseModel):
    """规则动作"""
    action_type: str = Field(..., description="动作类型：intercept, warn, log, calculate")
    message_template: str = Field(..., description="消息模板，支持变量替换")
    parameters: Optional[Dict[str, Any]] = Field(default_factory=dict, description="动作参数")

class DrugInfo(BaseModel):
    """药品信息"""
    drug_codes: List[str] = Field(default_factory=list, description="药品代码列表")
    drug_names: List[str] = Field(default_factory=list, description="药品通用名列表")
    categories: List[str] = Field(default_factory=list, description="药品分类")

class MedicalRule(BaseModel):
    """医保规则完整定义"""
    # 基本信息
    code: str = Field(..., description="规则编码，唯一标识")
    name: str = Field(..., description="规则名称")
    description: Optional[str] = Field(None, description="规则描述")
    rule_type: RuleType = Field(..., description="规则类型")
    severity: SeverityLevel = Field(..., description="严重级别")
    
    # 规则逻辑
    conditions: List[RuleCondition] = Field(..., description="触发条件列表")
    actions: List[RuleAction] = Field(..., description="执行动作列表")
    triggers: List[TriggerEvent] = Field(..., description="触发事件列表")
    
    # 适用范围
    drug_info: Optional[DrugInfo] = Field(None, description="适用药品信息")
    applicable_scenarios: List[str] = Field(default_factory=list, description="适用场景")
    
    # 元数据
    source: Optional[str] = Field(None, description="规则来源，如国家药品目录2024版")
    version: str = Field("1.0", description="规则版本")
    effective_date: Optional[str] = Field(None, description="生效日期")
    expiry_date: Optional[str] = Field(None, description="失效日期")
    enabled: bool = Field(True, description="是否启用")
    
    # 审计信息
    created_by: Optional[str] = Field(None, description="创建人")
    created_at: Optional[str] = Field(None, description="创建时间")
    updated_by: Optional[str] = Field(None, description="更新人")
    updated_at: Optional[str] = Field(None, description="更新时间")

class RuleBatch(BaseModel):
    """规则批次导入"""
    batch_name: str = Field(..., description="批次名称")
    batch_description: Optional[str] = Field(None, description="批次描述")
    source_file: Optional[str] = Field(None, description="源文件名")
    rules: List[MedicalRule] = Field(..., description="规则列表")
    import_mode: str = Field("append", description="导入模式：append, replace, update")

# 预定义的规则模板
RULE_TEMPLATES = {
    "drug_gender": {
        "name": "药品性别限制规则",
        "description": "检查药品是否适用于患者性别",
        "conditions": [
            {
                "fact": "patient.gender",
                "operator": "!=",
                "value": "{required_gender}",
                "description": "患者性别不符合要求"
            },
            {
                "fact": "drug.code",
                "operator": "in",
                "value": "{drug_codes}",
                "description": "药品在限制列表中"
            }
        ],
        "actions": [
            {
                "action_type": "intercept",
                "message_template": "患者性别为{patient.gender}，不能使用{drug.name}（该药品限{required_gender}性使用）",
                "parameters": {}
            }
        ],
        "triggers": ["prescription_create", "prescription_update"]
    },
    
    "drug_age": {
        "name": "药品年龄限制规则", 
        "description": "检查药品使用的年龄限制",
        "conditions": [
            {
                "fact": "patient.age",
                "operator": "{age_operator}",
                "value": "{age_limit}",
                "description": "患者年龄不在允许范围内"
            },
            {
                "fact": "drug.code",
                "operator": "in", 
                "value": "{drug_codes}",
                "description": "药品在限制列表中"
            }
        ],
        "actions": [
            {
                "action_type": "intercept",
                "message_template": "患者年龄{patient.age}岁，不能使用{drug.name}（该药品限{age_description}使用）",
                "parameters": {}
            }
        ],
        "triggers": ["prescription_create", "prescription_update"]
    },
    
    "drug_payment_course": {
        "name": "药品支付疗程限制规则",
        "description": "检查药品支付的疗程天数限制", 
        "conditions": [
            {
                "fact": "prescription.duration_days",
                "operator": ">",
                "value": "{max_days}",
                "description": "处方天数超过限制"
            },
            {
                "fact": "drug.code",
                "operator": "in",
                "value": "{drug_codes}",
                "description": "药品在限制列表中"
            }
        ],
        "actions": [
            {
                "action_type": "warn",
                "message_template": "{drug.name}支付天数不能超过{max_days}天，当前处方{prescription.duration_days}天",
                "parameters": {"max_days": "{max_days}"}
            }
        ],
        "triggers": ["prescription_create", "payment_calculate"]
    }
}
