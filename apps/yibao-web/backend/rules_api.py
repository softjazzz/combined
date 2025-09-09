"""
医保规则管理 API
包含规则 CRUD、沙箱测试、统计分析等功能
"""

from typing import List, Dict, Any, Optional
from datetime import datetime
import json
import uuid
from fastapi import APIRouter, Depends, HTTPException, status, Query, UploadFile, File
from pydantic import BaseModel

from auth_utils import get_current_user
from rule_schema import MedicalRule, RuleBatch

router = APIRouter(prefix="/api/rules", tags=["医保规则管理"])

# ==================== 数据模型 ====================

class RuleBase(BaseModel):
    code: str
    name: str
    description: Optional[str] = None
    rule_type: str  # 'drug_age', 'drug_gender', 'diagnosis_drug', etc.
    severity: str   # 'info', 'warn', 'block'
    enabled: bool = True

class RuleCreate(RuleBase):
    conditions: List[Dict[str, Any]] = []
    actions: List[Dict[str, Any]] = []
    triggers: List[str] = []

class RuleUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    rule_type: Optional[str] = None
    severity: Optional[str] = None
    enabled: Optional[bool] = None
    conditions: Optional[List[Dict[str, Any]]] = None
    actions: Optional[List[Dict[str, Any]]] = None
    triggers: Optional[List[str]] = None

class RuleResponse(RuleBase):
    id: int
    created_at: str
    updated_at: str
    created_by: str
    conditions: List[Dict[str, Any]] = []
    actions: List[Dict[str, Any]] = []
    triggers: List[str] = []

class SandboxTestRequest(BaseModel):
    rule_id: int
    test_data: Dict[str, Any]

class SandboxTestResponse(BaseModel):
    rule_id: int
    decision: str  # 'pass', 'warn', 'block'
    hits: List[Dict[str, Any]]
    execution_time_ms: float

class RuleImportRequest(BaseModel):
    batch_name: str
    batch_description: Optional[str] = None
    rules: List[Dict[str, Any]]
    import_mode: str = "append"  # append, replace, update

class RuleImportResponse(BaseModel):
    batch_id: str
    imported_count: int
    failed_count: int
    errors: List[str]
    success: bool

class RuleValidationResponse(BaseModel):
    valid: bool
    errors: List[str]
    warnings: List[str]
    rule_count: int

class PaginatedRulesResponse(BaseModel):
    data: List[RuleResponse]
    total: int
    page: int
    page_size: int
    total_pages: int

# ==================== Mock 数据 ====================

def load_imported_rules():
    """加载导入的医保规则"""
    try:
        with open('medical_rules.json', 'r', encoding='utf-8') as f:
            imported_rules = json.load(f)

        # 为每个规则添加必要的字段
        for i, rule in enumerate(imported_rules):
            rule['id'] = i + 1
            rule['enabled'] = rule.get('enabled', True)
            rule['created_at'] = rule.get('created_at') or datetime.now().isoformat() + "Z"
            rule['updated_at'] = rule.get('updated_at') or datetime.now().isoformat() + "Z"
            rule['created_by'] = rule.get('created_by') or 'system'

            # 确保所有必需字段都存在且不为None
            rule['description'] = rule.get('description') or ''
            rule['conditions'] = rule.get('conditions') or []
            rule['actions'] = rule.get('actions') or []
            rule['triggers'] = rule.get('triggers') or []

        return imported_rules
    except FileNotFoundError:
        print("Warning: medical_rules.json not found, using default mock rules")
        return []
    except Exception as e:
        print(f"Error loading medical_rules.json: {e}")
        return []

# 尝试加载导入的规则，如果失败则使用默认规则
IMPORTED_RULES = load_imported_rules()

MOCK_RULES = IMPORTED_RULES if IMPORTED_RULES else [
    {
        "id": 1,
        "code": "DRUG_AGE_001",
        "name": "儿童用药年龄限制",
        "description": "检查儿童专用药物的年龄限制",
        "rule_type": "drug_age",
        "severity": "block",
        "enabled": True,
        "created_at": "2024-01-01T00:00:00Z",
        "updated_at": "2024-01-01T00:00:00Z",
        "created_by": "admin@yibao.com",
        "conditions": [
            {
                "fact": "patient.age",
                "op": "<",
                "value": 18
            },
            {
                "fact": "drug.category",
                "op": "==",
                "value": "adult_only"
            }
        ],
        "actions": [
            {
                "action_type": "intercept",
                "message_template": "患者年龄 {patient.age} 岁，不能使用成人专用药物 {drug.name}"
            }
        ],
        "triggers": ["prescription_create", "prescription_update"]
    },
    {
        "id": 2,
        "code": "DRUG_GENDER_001", 
        "name": "性别特定用药限制",
        "description": "检查性别特定药物的使用限制",
        "rule_type": "drug_gender",
        "severity": "warn",
        "enabled": True,
        "created_at": "2024-01-01T00:00:00Z",
        "updated_at": "2024-01-01T00:00:00Z",
        "created_by": "admin@yibao.com",
        "conditions": [
            {
                "fact": "patient.gender",
                "op": "==",
                "value": "male"
            },
            {
                "fact": "drug.contraindications",
                "op": "in",
                "value": ["male_contraindicated"]
            }
        ],
        "actions": [
            {
                "action_type": "warn",
                "message_template": "药物 {drug.name} 对男性患者可能存在禁忌，请谨慎使用"
            }
        ],
        "triggers": ["prescription_create"]
    }
]

# ==================== 规则管理 API ====================

@router.get("/", response_model=PaginatedRulesResponse)
async def get_rules(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    rule_type: Optional[str] = Query(None),
    severity: Optional[str] = Query(None),
    enabled: Optional[bool] = Query(None),
    search: Optional[str] = Query(None),
    current_user: dict = Depends(get_current_user)
):
    """获取规则列表"""

    # 使用 Mock 数据
    filtered_rules = MOCK_RULES.copy()

    # 应用筛选条件
    if rule_type:
        filtered_rules = [r for r in filtered_rules if r.get('rule_type') == rule_type]
    if severity:
        filtered_rules = [r for r in filtered_rules if r.get('severity') == severity]
    if enabled is not None:
        filtered_rules = [r for r in filtered_rules if r.get('enabled') == enabled]
    if search:
        filtered_rules = [r for r in filtered_rules if search.lower() in r.get('name', '').lower()]

    # 计算分页信息
    total = len(filtered_rules)
    total_pages = (total + page_size - 1) // page_size

    # 分页
    start = (page - 1) * page_size
    end = start + page_size
    paginated_rules = filtered_rules[start:end]

    return PaginatedRulesResponse(
        data=paginated_rules,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages
    )

@router.get("/{rule_id}", response_model=RuleResponse)
async def get_rule(rule_id: int, current_user: dict = Depends(get_current_user)):
    """获取单个规则详情"""
    
    if supabase:
        try:
            response = supabase.table('yibao_rules').select('*').eq('id', rule_id).execute()
            if response.data:
                return response.data[0]
        except Exception:
            pass
    
    # 使用 Mock 数据
    rule = next((r for r in MOCK_RULES if r['id'] == rule_id), None)
    if not rule:
        raise HTTPException(status_code=404, detail="规则不存在")
    
    return rule

@router.post("/", response_model=RuleResponse)
async def create_rule(rule_data: RuleCreate, current_user: dict = Depends(get_current_user)):
    """创建新规则"""
    
    if supabase:
        try:
            # 插入规则基本信息
            rule_insert = {
                "code": rule_data.code,
                "name": rule_data.name,
                "description": rule_data.description,
                "rule_type": rule_data.rule_type,
                "severity": rule_data.severity,
                "enabled": rule_data.enabled,
                "created_by": current_user["email"]
            }
            
            response = supabase.table('yibao_rules').insert(rule_insert).execute()
            if response.data:
                rule_id = response.data[0]['id']
                
                # 插入条件
                if rule_data.conditions:
                    conditions = [
                        {
                            "rule_id": rule_id,
                            "priority": i,
                            "expression_json": condition
                        }
                        for i, condition in enumerate(rule_data.conditions)
                    ]
                    supabase.table('yibao_rule_conditions').insert(conditions).execute()
                
                # 插入动作
                if rule_data.actions:
                    actions = [
                        {
                            "rule_id": rule_id,
                            "action_type": action.get("action_type", "warn"),
                            "message_template": action.get("message_template", "")
                        }
                        for action in rule_data.actions
                    ]
                    supabase.table('yibao_rule_actions').insert(actions).execute()
                
                # 插入触发器
                if rule_data.triggers:
                    triggers = [
                        {
                            "rule_id": rule_id,
                            "event_type": trigger
                        }
                        for trigger in rule_data.triggers
                    ]
                    supabase.table('yibao_rule_triggers').insert(triggers).execute()
                
                return response.data[0]
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"创建规则失败: {str(e)}")
    
    # Mock 模式
    new_rule = {
        "id": len(MOCK_RULES) + 1,
        "code": rule_data.code,
        "name": rule_data.name,
        "description": rule_data.description,
        "rule_type": rule_data.rule_type,
        "severity": rule_data.severity,
        "enabled": rule_data.enabled,
        "created_at": datetime.utcnow().isoformat() + "Z",
        "updated_at": datetime.utcnow().isoformat() + "Z",
        "created_by": current_user["email"],
        "conditions": rule_data.conditions,
        "actions": rule_data.actions,
        "triggers": rule_data.triggers
    }
    
    MOCK_RULES.append(new_rule)
    return new_rule

@router.put("/{rule_id}", response_model=RuleResponse)
async def update_rule(
    rule_id: int, 
    rule_data: RuleUpdate, 
    current_user: dict = Depends(get_current_user)
):
    """更新规则"""
    
    if supabase:
        try:
            # 更新规则基本信息
            update_data = {k: v for k, v in rule_data.dict().items() if v is not None}
            if update_data:
                update_data["updated_at"] = datetime.utcnow().isoformat() + "Z"
                response = supabase.table('yibao_rules').update(update_data).eq('id', rule_id).execute()
                if response.data:
                    return response.data[0]
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"更新规则失败: {str(e)}")
    
    # Mock 模式
    rule = next((r for r in MOCK_RULES if r['id'] == rule_id), None)
    if not rule:
        raise HTTPException(status_code=404, detail="规则不存在")
    
    # 更新字段
    for field, value in rule_data.dict().items():
        if value is not None:
            rule[field] = value
    
    rule["updated_at"] = datetime.utcnow().isoformat() + "Z"
    return rule

@router.delete("/{rule_id}")
async def delete_rule(rule_id: int, current_user: dict = Depends(get_current_user)):
    """删除规则"""
    
    if supabase:
        try:
            response = supabase.table('yibao_rules').delete().eq('id', rule_id).execute()
            if response.data:
                return {"message": "规则删除成功"}
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"删除规则失败: {str(e)}")
    
    # Mock 模式
    global MOCK_RULES
    MOCK_RULES = [r for r in MOCK_RULES if r['id'] != rule_id]
    return {"message": "规则删除成功"}

# ==================== 沙箱测试 API ====================

@router.post("/sandbox/test", response_model=SandboxTestResponse)
async def test_rule_in_sandbox(
    test_request: SandboxTestRequest,
    current_user: dict = Depends(get_current_user)
):
    """在沙箱环境中测试规则"""
    import time

    start_time = time.time()

    # 获取规则
    rule = next((r for r in MOCK_RULES if r['id'] == test_request.rule_id), None)
    if not rule:
        raise HTTPException(status_code=404, detail="规则不存在")

    # 模拟规则执行
    hits = []
    decision = "pass"

    # 简单的规则评估逻辑
    for condition in rule.get('conditions', []):
        fact_path = condition.get('fact', '')
        operator = condition.get('op', '')
        expected_value = condition.get('value')

        # 从测试数据中获取实际值
        actual_value = get_nested_value(test_request.test_data, fact_path)

        # 评估条件
        if evaluate_condition(actual_value, operator, expected_value):
            # 条件匹配，触发规则
            for action in rule.get('actions', []):
                hit = {
                    "rule_code": rule['code'],
                    "severity": rule['severity'],
                    "action": action.get('action_type', 'warn'),
                    "message": render_message_template(
                        action.get('message_template', rule['name']),
                        test_request.test_data
                    )
                }
                hits.append(hit)

            # 确定最终决策
            if rule['severity'] == 'block':
                decision = 'block'
            elif rule['severity'] == 'warn' and decision == 'pass':
                decision = 'warn'
            break

    execution_time = (time.time() - start_time) * 1000

    return SandboxTestResponse(
        rule_id=test_request.rule_id,
        decision=decision,
        hits=hits,
        execution_time_ms=execution_time
    )

@router.post("/sandbox/batch-test")
async def batch_test_rules(
    test_data: Dict[str, Any],
    rule_ids: Optional[List[int]] = None,
    current_user: dict = Depends(get_current_user)
):
    """批量测试多个规则"""

    # 如果没有指定规则ID，测试所有启用的规则
    if rule_ids is None:
        rules_to_test = [r for r in MOCK_RULES if r['enabled']]
    else:
        rules_to_test = [r for r in MOCK_RULES if r['id'] in rule_ids and r['enabled']]

    results = []
    overall_decision = "pass"

    for rule in rules_to_test:
        test_request = SandboxTestRequest(rule_id=rule['id'], test_data=test_data)
        result = await test_rule_in_sandbox(test_request, current_user)
        results.append(result)

        # 更新整体决策
        if result.decision == 'block':
            overall_decision = 'block'
        elif result.decision == 'warn' and overall_decision == 'pass':
            overall_decision = 'warn'

    return {
        "overall_decision": overall_decision,
        "total_rules_tested": len(results),
        "results": results
    }

# ==================== 统计分析 API ====================

@router.get("/statistics/overview")
async def get_rules_statistics(current_user: dict = Depends(get_current_user)):
    """获取规则统计概览"""

    # 使用 Mock 数据进行统计
    try:
        # 统计 Mock 规则数据
        total_rules = len(MOCK_RULES)
        enabled_rules = len([r for r in MOCK_RULES if r.get('enabled', True)])
        disabled_rules = total_rules - enabled_rules

        # 按严重级别统计
        severity_stats = {}
        for severity in ['info', 'warn', 'block']:
            severity_stats[severity] = len([r for r in MOCK_RULES if r.get('severity') == severity])

        # 按类型统计
        rule_types = {}
        for rule in MOCK_RULES:
            rule_type = rule.get('rule_type', 'unknown')
            rule_types[rule_type] = rule_types.get(rule_type, 0) + 1

        return {
            "total_rules": total_rules,
            "enabled_rules": enabled_rules,
            "disabled_rules": disabled_rules,
            "rule_types": rule_types,
            "severity_distribution": severity_stats,
            "recent_activity": {
                "created_today": 0,
                "updated_today": 0,
                "violations_today": 0
            }
        }
    except Exception as e:
        # 如果出错，返回基本统计
        return {
            "total_rules": len(MOCK_RULES),
            "enabled_rules": len([r for r in MOCK_RULES if r.get('enabled', True)]),
            "disabled_rules": len([r for r in MOCK_RULES if not r.get('enabled', True)]),
            "rule_types": {},
            "severity_distribution": {},
            "recent_activity": {
                "created_today": 0,
                "updated_today": 0,
                "violations_today": 0
            }
        }

# ==================== 工具函数 ====================

def get_nested_value(data: Dict[str, Any], path: str) -> Any:
    """从嵌套字典中获取值"""
    keys = path.split('.')
    value = data
    for key in keys:
        if isinstance(value, dict) and key in value:
            value = value[key]
        else:
            return None
    return value

def evaluate_condition(actual_value: Any, operator: str, expected_value: Any) -> bool:
    """评估条件"""
    if actual_value is None:
        return False

    try:
        if operator == '==':
            return actual_value == expected_value
        elif operator == '!=':
            return actual_value != expected_value
        elif operator == '>':
            return float(actual_value) > float(expected_value)
        elif operator == '>=':
            return float(actual_value) >= float(expected_value)
        elif operator == '<':
            return float(actual_value) < float(expected_value)
        elif operator == '<=':
            return float(actual_value) <= float(expected_value)
        elif operator == 'in':
            return actual_value in expected_value if isinstance(expected_value, list) else False
        elif operator == 'not_in':
            return actual_value not in expected_value if isinstance(expected_value, list) else True
        else:
            return False
    except (ValueError, TypeError):
        return False

def render_message_template(template: str, data: Dict[str, Any]) -> str:
    """渲染消息模板"""
    import re

    def replace_placeholder(match):
        path = match.group(1)
        value = get_nested_value(data, path)
        return str(value) if value is not None else f"{{{path}}}"

    return re.sub(r'\{([^}]+)\}', replace_placeholder, template)

# ==================== 规则导入相关 API ====================

@router.post("/validate", response_model=RuleValidationResponse)
async def validate_rules(
    rules_data: List[Dict[str, Any]],
    current_user: dict = Depends(get_current_user)
):
    """验证规则数据格式"""
    errors = []
    warnings = []
    valid_count = 0

    for idx, rule_data in enumerate(rules_data):
        try:
            # 尝试创建 MedicalRule 对象进行验证
            rule = MedicalRule(**rule_data)
            valid_count += 1

            # 检查规则编码是否重复
            if any(r.get("code") == rule.code for r in rules_data[:idx]):
                warnings.append(f"规则 {idx + 1}: 规则编码 {rule.code} 重复")

        except Exception as e:
            errors.append(f"规则 {idx + 1}: {str(e)}")

    return RuleValidationResponse(
        valid=len(errors) == 0,
        errors=errors,
        warnings=warnings,
        rule_count=len(rules_data)
    )

@router.post("/import", response_model=RuleImportResponse)
async def import_rules(
    import_request: RuleImportRequest,
    current_user: dict = Depends(get_current_user)
):
    """批量导入规则"""
    batch_id = str(uuid.uuid4())
    imported_count = 0
    failed_count = 0
    errors = []

    try:
        # 验证规则数据
        validation_result = await validate_rules(import_request.rules, current_user)
        if not validation_result.valid:
            return RuleImportResponse(
                batch_id=batch_id,
                imported_count=0,
                failed_count=len(import_request.rules),
                errors=validation_result.errors,
                success=False
            )

        # 处理导入模式
        if import_request.import_mode == "replace":
            # 清空现有规则（在实际实现中需要谨慎处理）
            MOCK_RULES.clear()

        # 导入规则
        for idx, rule_data in enumerate(import_request.rules):
            try:
                # 添加审计信息
                rule_data["created_by"] = current_user["email"]
                rule_data["created_at"] = datetime.now().isoformat()
                rule_data["updated_by"] = current_user["email"]
                rule_data["updated_at"] = datetime.now().isoformat()

                # 生成新的ID
                new_id = len(MOCK_RULES) + 1
                rule_data["id"] = new_id

                # 添加到Mock数据
                MOCK_RULES.append(rule_data)
                imported_count += 1

            except Exception as e:
                failed_count += 1
                errors.append(f"规则 {idx + 1}: {str(e)}")

        return RuleImportResponse(
            batch_id=batch_id,
            imported_count=imported_count,
            failed_count=failed_count,
            errors=errors,
            success=failed_count == 0
        )

    except Exception as e:
        return RuleImportResponse(
            batch_id=batch_id,
            imported_count=0,
            failed_count=len(import_request.rules),
            errors=[f"导入失败: {str(e)}"],
            success=False
        )

@router.post("/import/file")
async def import_rules_from_file(
    file: UploadFile = File(...),
    batch_name: str = "文件导入批次",
    batch_description: str = None,
    import_mode: str = "append",
    current_user: dict = Depends(get_current_user)
):
    """从文件导入规则"""
    try:
        # 读取文件内容
        content = await file.read()

        if file.filename.endswith('.json'):
            # JSON文件
            rules_data = json.loads(content.decode('utf-8'))
        else:
            raise HTTPException(
                status_code=400,
                detail="不支持的文件格式，请上传JSON文件"
            )

        # 创建导入请求
        import_request = RuleImportRequest(
            batch_name=batch_name,
            batch_description=batch_description or f"从文件 {file.filename} 导入",
            rules=rules_data,
            import_mode=import_mode
        )

        # 执行导入
        return await import_rules(import_request, current_user)

    except json.JSONDecodeError:
        raise HTTPException(
            status_code=400,
            detail="JSON文件格式错误"
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"文件导入失败: {str(e)}"
        )

@router.get("/export")
async def export_rules(
    format: str = "json",
    rule_type: Optional[str] = None,
    enabled_only: bool = True,
    current_user: dict = Depends(get_current_user)
):
    """导出规则"""
    try:
        # 过滤规则
        filtered_rules = MOCK_RULES.copy()

        if rule_type:
            filtered_rules = [r for r in filtered_rules if r.get("rule_type") == rule_type]

        if enabled_only:
            filtered_rules = [r for r in filtered_rules if r.get("enabled", True)]

        if format == "json":
            return {
                "rules": filtered_rules,
                "count": len(filtered_rules),
                "exported_at": datetime.now().isoformat(),
                "exported_by": current_user["email"]
            }
        else:
            raise HTTPException(
                status_code=400,
                detail="不支持的导出格式"
            )

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"导出失败: {str(e)}"
        )
