# 科室级质控规则配置功能 - 设计总结

> **文档版本**: 2.0
> **创建日期**: 2025-10-12
> **最后更新**: 2025-10-12
> **相关文档**: [完整 PRD](./PRD_DEPARTMENT_QC_RULES.md) | [变更日志](./PRD_DEPARTMENT_QC_RULES_CHANGELOG.md)

---

## 🎯 版本说明

**Version 2.0 重大改进**:
- ✅ 新增"禁用全局规则"的明确建模（`override_action` 字段）
- ✅ 新增规则版本与生效期管理（`status`, `effective_from/to` 字段）
- ✅ 新增规则变更审计日志（`qc_rule_change_logs` 表）
- ✅ 新增数据库 RPC 函数（统一规则匹配逻辑）
- ✅ 保留文书类别维度（`applicable_documents` 字段）
- ✅ 补充完整的测试用例（规则匹配、审计、边界条件）

详见：[变更日志](./PRD_DEPARTMENT_QC_RULES_CHANGELOG.md)

---

## 📋 快速导航

- [完整 PRD 文档](./PRD_DEPARTMENT_QC_RULES.md) - 详细的产品需求文档
- [变更日志](./PRD_DEPARTMENT_QC_RULES_CHANGELOG.md) - v2.0 改进说明
- [业务流程图](#业务流程图) - 核心业务流程可视化
- [数据模型](#数据模型) - 数据库设计方案
- [实施建议](#实施建议) - 开发和部署建议

---

## 🎯 功能概述

### 核心价值

**解决的问题**:
- ✅ 不同科室有不同的质控需求，统一规则无法满足
- ✅ 需要在保持统一标准的基础上，支持个性化配置
- ✅ 提高质控规则的适用性和准确性

**功能亮点**:
1. **三层规则体系**: 全局规则 → 科室覆盖规则 → 科室特有规则
2. **灵活的继承机制**: 科室规则可以继承并覆盖全局规则
3. **智能规则匹配**: 自动选择最适用的规则执行质控
4. **细粒度权限控制**: 基于 RBAC 的权限管理

---

## 📊 数据模型设计

### 方案选择：扩展现有 qc_rules 表（推荐）

**核心字段** (v2.0 新增 7 个字段):

```sql
ALTER TABLE qc_rules
-- 规则范围和科室
ADD COLUMN scope VARCHAR(20) DEFAULT 'global',           -- 规则范围
ADD COLUMN department_id UUID REFERENCES departments(id), -- 科室ID
ADD COLUMN parent_rule_id UUID REFERENCES qc_rules(id),  -- 父规则ID

-- 覆盖配置 (v2.0 新增)
ADD COLUMN override_action VARCHAR(20) DEFAULT 'override' -- 覆盖行为：override/disable
    CHECK (override_action IN ('override', 'disable')),
ADD COLUMN override_config JSONB DEFAULT '{}',           -- 覆盖配置
ADD COLUMN priority INTEGER DEFAULT 0,                   -- 优先级

-- 版本和生效期 (v2.0 新增)
ADD COLUMN status VARCHAR(20) DEFAULT 'published'        -- 规则状态
    CHECK (status IN ('draft', 'published', 'archived')),
ADD COLUMN version VARCHAR(20) DEFAULT '1.0',            -- 规则版本号
ADD COLUMN effective_from TIMESTAMPTZ,                   -- 生效开始时间
ADD COLUMN effective_to TIMESTAMPTZ,                     -- 生效结束时间

-- 审核信息 (v2.0 新增)
ADD COLUMN approved_by UUID,                             -- 审核人ID
ADD COLUMN approved_at TIMESTAMPTZ;                      -- 审核时间
```

**关键约束**:

```sql
-- 确保科室规则必须关联科室
ALTER TABLE qc_rules
ADD CONSTRAINT chk_department_scope
CHECK (
    (scope = 'global' AND department_id IS NULL) OR
    (scope = 'department' AND department_id IS NOT NULL)
);

-- 同一科室不能有重复的已发布规则代码 (v2.0 优化)
CREATE UNIQUE INDEX uk_dept_rule_code_published
ON qc_rules(department_id, rule_code)
WHERE scope = 'department' AND status = 'published';

-- 生效期索引 (v2.0 新增)
CREATE INDEX idx_qc_rules_effective
ON qc_rules(effective_from, effective_to);

-- 状态索引 (v2.0 新增)
CREATE INDEX idx_qc_rules_status
ON qc_rules(status);
```

### 数据示例

#### 全局规则

```json
{
  "id": "rule-001",
  "rule_code": "R001",
  "name": "主诉完整性检查",
  "scope": "global",
  "department_id": null,
  "severity": "major",
  "scoring_config": {
    "default_deduction": 5,
    "max_deduction": 10
  }
}
```

#### 科室覆盖规则

```json
{
  "id": "rule-002",
  "rule_code": "R001",
  "name": "主诉完整性检查-外科定制",
  "scope": "department",
  "department_id": "dept-002",
  "parent_rule_id": "rule-001",
  "severity": "critical",  // 覆盖
  "scoring_config": {
    "default_deduction": 10,  // 覆盖
    "max_deduction": 20       // 覆盖
  },
  "override_config": {
    "severity": true,
    "scoring_config": true
  },
  "priority": 10
}
```

#### 科室特有规则

```json
{
  "id": "rule-003",
  "rule_code": "R069",
  "name": "手术部位标记检查",
  "scope": "department",
  "department_id": "dept-006",
  "parent_rule_id": null,  // 无父规则
  "override_action": "override",
  "severity": "critical",
  "priority": 20,
  "status": "published",
  "effective_from": "2025-01-01T00:00:00+08:00"
}
```

#### 科室禁用规则 (v2.0 新增)

```json
{
  "id": "rule-004",
  "rule_code": "R010",
  "name": "禁用：成人用药剂量检查",
  "scope": "department",
  "department_id": "dept-003",  // 儿科
  "override_action": "disable",  // 禁用全局规则
  "is_active": true,
  "status": "published",
  "reason": "儿科使用儿童用药剂量标准，不适用成人标准"
}
```

---

## 🔄 业务流程图

### 1. 质控执行流程

已生成 Mermaid 流程图，展示了：
- 规则加载逻辑
- 规则合并和优先级处理
- 规则执行和结果汇总

**关键步骤**:
1. 获取病历所属科室
2. 加载全局规则和科室规则
3. 合并规则（科室规则覆盖全局规则）
4. 按优先级排序
5. 执行规则检查
6. 汇总结果并计算总分

### 2. 规则管理流程

已生成 Mermaid 流程图，展示了：
- 用户权限检查
- 规则 CRUD 操作
- 表单验证和错误处理
- API 调用和结果反馈

**支持的操作**:
- ✅ 查看规则
- ✅ 新增科室规则（基于全局规则或全新创建）
- ✅ 编辑科室规则
- ✅ 删除科室规则
- ✅ 启用/禁用规则

---

## 🔍 规则匹配算法

### 核心逻辑

```python
def get_applicable_rules(department_id: str) -> List[Rule]:
    """
    获取适用的质控规则
    
    优先级（从高到低）:
    1. 科室特有规则（priority 高）
    2. 科室覆盖规则（有 parent_rule_id）
    3. 全局规则（scope = 'global'）
    """
    # 1. 获取所有激活的全局规则
    global_rules = get_global_rules(is_active=True)
    
    # 2. 获取该科室的所有激活规则
    dept_rules = get_department_rules(department_id, is_active=True)
    
    # 3. 构建规则字典（按 rule_code 分组）
    rule_map = {}
    
    # 先添加全局规则
    for rule in global_rules:
        rule_map[rule.rule_code] = rule
    
    # 科室规则覆盖全局规则
    for rule in dept_rules:
        if rule.parent_rule_id:
            # 覆盖规则：替换全局规则
            rule_map[rule.rule_code] = rule
        else:
            # 新规则：直接添加
            rule_map[rule.rule_code] = rule
    
    # 4. 按优先级排序
    rules = sorted(rule_map.values(), key=lambda x: x.priority, reverse=True)
    
    return rules
```

### SQL 实现

```sql
-- 使用 CTE 实现规则匹配
WITH dept_rules AS (
    SELECT * FROM qc_rules
    WHERE scope = 'department' 
    AND department_id = :dept_id
    AND is_active = true
),
global_rules AS (
    SELECT * FROM qc_rules
    WHERE scope = 'global'
    AND is_active = true
    AND rule_code NOT IN (
        -- 排除被科室规则覆盖的全局规则
        SELECT rule_code FROM dept_rules WHERE parent_rule_id IS NOT NULL
    )
)
SELECT * FROM dept_rules
UNION ALL
SELECT * FROM global_rules
ORDER BY priority DESC, rule_code ASC;
```

---

## 🎨 界面设计要点

### 规则列表展示

**视觉层次**:
```
R001 主诉完整性检查 [🌐 全局] [重要] [启用]
  ├─ 主诉完整性检查-外科定制 [🔄 覆盖] [严重] [启用]
  └─ 主诉完整性检查-儿科定制 [🔄 覆盖] [重要] [启用]

R002 现病史完整性检查 [🌐 全局] [重要] [启用]

R069 手术部位标记检查 [🏥 科室] [严重] [启用]
```

**图标说明**:
- 🌐 全局规则（灰色）
- 🔄 覆盖规则（橙色）
- 🏥 科室特有规则（蓝色）

### 规则编辑表单

**分组设计**:
1. **基本信息**: 规则编号、名称、科室、描述
2. **规则配置**: 严重性、规则类型、检查逻辑、评分配置
3. **覆盖配置**: 选择要覆盖的字段（仅覆盖规则）

**表单验证**:
- ✅ 规则名称不能为空
- ✅ 科室必须选择
- ✅ 检查逻辑 JSON 格式正确
- ✅ 评分配置数值合理

---

## 🔐 权限控制

### 权限矩阵

| 操作 | Admin | QC Manager | Dept Admin | QC Staff | Doctor |
|------|-------|------------|------------|----------|--------|
| 查看全局规则 | ✅ | ✅ | ✅ | ✅ | ✅ |
| 编辑全局规则 | ✅ | ✅ | ❌ | ❌ | ❌ |
| 查看科室规则 | ✅ | ✅ | ✅ (本科室) | ✅ | ✅ |
| 创建科室规则 | ✅ | ✅ | ✅ (本科室) | ❌ | ❌ |
| 编辑科室规则 | ✅ | ✅ | ✅ (本科室) | ❌ | ❌ |
| 删除科室规则 | ✅ | ✅ | ✅ (本科室) | ❌ | ❌ |

### API 权限装饰器

```python
from app.core.permissions import require_permission, require_role

@router.post("/qc/rules/department")
@require_role([UserRole.ADMIN, UserRole.QC_MANAGER])
async def create_department_rule(rule: DepartmentRule):
    """创建科室规则"""
    pass

@router.put("/qc/rules/department/{rule_id}")
@require_role([UserRole.ADMIN, UserRole.QC_MANAGER])
async def update_department_rule(rule_id: str, rule: DepartmentRule):
    """更新科室规则"""
    pass

@router.delete("/qc/rules/department/{rule_id}")
@require_admin()
async def delete_department_rule(rule_id: str):
    """删除科室规则（仅管理员）"""
    pass
```

---

## 📝 API 接口设计

### 1. 获取规则列表

```http
GET /api/v1/qc/rules?scope={scope}&department_id={dept_id}

Response:
{
  "data": [
    {
      "id": "rule-001",
      "rule_code": "R001",
      "name": "主诉完整性检查",
      "scope": "global",
      "children": [...]  // 科室规则
    }
  ],
  "total": 72
}
```

### 2. 创建科室规则

```http
POST /api/v1/qc/rules/department

Request:
{
  "department_id": "dept-002",
  "base_rule_id": "rule-001",
  "rule_code": "R001",
  "name": "主诉完整性检查-外科定制",
  "severity": "critical",
  "override_config": {...}
}

Response:
{
  "id": "rule-002",
  "message": "科室规则创建成功"
}
```

### 3. 获取适用规则（执行质控时）

```http
GET /api/v1/qc/rules/applicable?department_id={dept_id}

Response:
{
  "data": [
    {
      "id": "rule-002",
      "rule_code": "R001",
      "priority": 10,
      "source": "department"
    }
  ]
}
```

---

## 🧪 测试策略

### 单元测试

```python
def test_rule_matching_priority():
    """测试规则匹配优先级"""
    # 创建全局规则
    global_rule = create_global_rule("R001", severity="major")
    
    # 创建科室覆盖规则
    dept_rule = create_dept_rule("R001", dept_id="dept-002", 
                                  severity="critical", 
                                  parent_rule_id=global_rule.id)
    
    # 获取适用规则
    rules = get_applicable_rules(department_id="dept-002")
    
    # 断言：科室规则优先
    assert rules[0].id == dept_rule.id
    assert rules[0].severity == "critical"

def test_rule_inheritance():
    """测试规则继承"""
    # 创建全局规则
    global_rule = create_global_rule("R001", 
                                      severity="major",
                                      scoring_config={"deduction": 5})
    
    # 创建科室规则（仅覆盖 severity）
    dept_rule = create_dept_rule("R001", dept_id="dept-002",
                                  severity="critical",
                                  parent_rule_id=global_rule.id,
                                  override_config={"severity": True})
    
    # 获取完整配置
    config = get_rule_config(dept_rule.id)
    
    # 断言：severity 被覆盖，scoring_config 继承
    assert config.severity == "critical"
    assert config.scoring_config["deduction"] == 5
```

### 集成测试

```python
def test_qc_execution_with_dept_rules():
    """测试使用科室规则执行质控"""
    # 创建测试病历
    record = create_test_record(department="外科")
    
    # 创建科室规则
    create_dept_rule("R001", dept_id="dept-002", severity="critical")
    
    # 执行质控
    result = execute_qc(record.id)
    
    # 断言：使用了科室规则
    assert result.rules_used[0].scope == "department"
    assert result.rules_used[0].severity == "critical"
```

---

## 🚀 实施建议

### 开发阶段（11 天）

| 阶段 | 任务 | 工作量 |
|------|------|--------|
| Phase 1 | 数据库设计和迁移 | 2 天 |
| Phase 2 | 后端 API 开发 | 3 天 |
| Phase 3 | 前端界面开发 | 3 天 |
| Phase 4 | 集成测试 | 2 天 |
| Phase 5 | 部署上线 | 1 天 |

### 技术栈

**后端**:
- FastAPI + Python
- PostgreSQL (Supabase)
- SQLAlchemy ORM

**前端**:
- Vue 3 + TypeScript
- Element Plus UI
- Pinia 状态管理

### 数据迁移步骤

```sql
-- 1. 创建 departments 表（如果不存在）
CREATE TABLE IF NOT EXISTS departments (...);

-- 2. 扩展 qc_rules 表
ALTER TABLE qc_rules ADD COLUMN scope VARCHAR(20) DEFAULT 'global';
ALTER TABLE qc_rules ADD COLUMN department_id UUID;
ALTER TABLE qc_rules ADD COLUMN parent_rule_id UUID;
ALTER TABLE qc_rules ADD COLUMN override_config JSONB DEFAULT '{}';
ALTER TABLE qc_rules ADD COLUMN priority INTEGER DEFAULT 0;

-- 3. 更新现有数据
UPDATE qc_rules SET scope = 'global' WHERE scope IS NULL;

-- 4. 添加约束和索引
ALTER TABLE qc_rules ADD CONSTRAINT chk_department_scope CHECK (...);
CREATE INDEX idx_qc_rules_scope ON qc_rules(scope);
CREATE INDEX idx_qc_rules_department ON qc_rules(department_id);
```

### 风险和缓解

| 风险 | 影响 | 缓解措施 |
|------|------|---------|
| 数据迁移失败 | 高 | 充分测试、备份数据、准备回滚方案 |
| 性能问题 | 中 | 添加索引、优化查询、使用缓存 |
| 用户接受度低 | 中 | 用户培训、详细文档、收集反馈 |

---

## 📚 相关文档

- [完整 PRD 文档](./PRD_DEPARTMENT_QC_RULES.md)
- [RBAC 权限系统实施指南](./RBAC_IMPLEMENTATION_GUIDE.md)
- [数据库迁移指南](../infra/supabase/medqc/migrations/README_006.md)
- [质控规则引擎设计](./TDD_病案质控系统技术设计文档.md)

---

## 🎯 下一步行动

1. **评审 PRD**: 与产品、技术团队评审需求
2. **技术方案评审**: 确认数据模型和 API 设计
3. **开发排期**: 安排开发资源和时间
4. **原型设计**: 设计详细的 UI 原型
5. **开发实施**: 按阶段推进开发工作

---

**文档版本**: 1.0  
**最后更新**: 2025-10-12  
**维护者**: Product Team

