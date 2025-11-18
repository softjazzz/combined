# Migration 009 完成报告

> **迁移名称**: 科室级质控规则配置功能  
> **版本**: 2.0  
> **创建日期**: 2025-10-12  
> **状态**: ✅ 已完成

---

## 📋 迁移概述

### 目标

实现科室级质控规则配置功能，支持：
1. 科室级规则配置（覆盖全局规则或创建科室特有规则）
2. 规则版本管理和生效期控制
3. 规则覆盖和禁用机制
4. 规则变更审计日志
5. 统一的规则匹配逻辑（RPC 函数）

### 相关文档

- [PRD 主文档](../../../../docs/PRD_DEPARTMENT_QC_RULES.md)
- [变更日志](../../../../docs/PRD_DEPARTMENT_QC_RULES_CHANGELOG.md)
- [评审响应](../../../../docs/PRD_DEPARTMENT_QC_RULES_REVIEW_RESPONSE.md)

---

## 🔄 变更内容

### 1. 数据库表变更

#### 1.1 扩展 `qc_rules` 表

新增 11 个字段：

| 字段 | 类型 | 说明 | 默认值 |
|------|------|------|--------|
| `scope` | VARCHAR(20) | 规则范围 (global/department) | 'global' |
| `department_id` | UUID | 科室ID（仅科室规则） | NULL |
| `parent_rule_id` | UUID | 父规则ID（覆盖规则时使用） | NULL |
| `override_action` | VARCHAR(20) | 覆盖行为 (override/disable) | 'override' |
| `override_config` | JSONB | 覆盖配置 | '{}' |
| `priority` | INTEGER | 优先级 | 0 |
| `status` | VARCHAR(20) | 规则状态 (draft/published/archived) | 'published' |
| `effective_from` | TIMESTAMPTZ | 生效开始时间 | NULL |
| `effective_to` | TIMESTAMPTZ | 生效结束时间 | NULL |
| `approved_by` | UUID | 审核人ID | NULL |
| `approved_at` | TIMESTAMPTZ | 审核时间 | NULL |

#### 1.2 新增 `qc_rule_change_logs` 表

审计日志表，记录所有规则变更：

```sql
CREATE TABLE qc_rule_change_logs (
    id UUID PRIMARY KEY,
    rule_id UUID NOT NULL,
    department_id UUID,
    action VARCHAR(20),  -- create/update/delete/enable/disable/publish/archive
    old_values JSONB,
    new_values JSONB,
    diff JSONB,
    actor_id UUID NOT NULL,
    actor_name VARCHAR(200),
    actor_role VARCHAR(50),
    reason TEXT,
    ip_address VARCHAR(50),
    user_agent TEXT,
    created_at TIMESTAMPTZ
);
```

#### 1.3 新增 `departments` 表（如果不存在）

科室表：

```sql
CREATE TABLE departments (
    id UUID PRIMARY KEY,
    code VARCHAR(50) UNIQUE NOT NULL,
    name VARCHAR(200) NOT NULL,
    description TEXT,
    parent_id UUID,
    level INTEGER DEFAULT 1,
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMPTZ,
    updated_at TIMESTAMPTZ
);
```

### 2. 索引和约束

#### 2.1 新增约束

- `chk_department_scope`: 确保科室规则必须关联科室

#### 2.2 新增索引

| 索引名称 | 类型 | 字段 | 说明 |
|---------|------|------|------|
| `uk_dept_rule_code_published` | UNIQUE | (department_id, rule_code) | 同科室同规则编号的已发布规则唯一 |
| `idx_qc_rules_scope` | INDEX | scope | 规则范围索引 |
| `idx_qc_rules_department` | INDEX | department_id | 科室索引 |
| `idx_qc_rules_parent` | INDEX | parent_rule_id | 父规则索引 |
| `idx_qc_rules_status` | INDEX | status | 状态索引 |
| `idx_qc_rules_effective` | INDEX | (effective_from, effective_to) | 生效期索引 |
| `idx_qc_rules_composite` | INDEX | (scope, department_id, is_active, status, ...) | 复合索引 |

### 3. 函数和触发器

#### 3.1 RPC 函数

**`get_applicable_qc_rules(p_department_id, p_document_type, p_at)`**

功能：获取适用于指定科室和文书类型的质控规则

逻辑：
1. 获取有效的全局规则
2. 获取有效的科室规则
3. 处理覆盖和禁用逻辑
4. 按优先级排序返回

#### 3.2 触发器函数

**`log_qc_rule_changes()`**

功能：自动记录规则变更到审计日志

触发时机：INSERT / UPDATE / DELETE on qc_rules

### 4. 视图

#### 4.1 `qc_rules_department_statistics`

规则统计视图，包含：
- 总规则数、全局规则数、科室规则数
- 按状态统计（published/draft/archived）
- 覆盖规则数、禁用规则数

#### 4.2 `qc_rules_by_department`

按科室统计规则数量

---

## 📊 迁移统计

### 变更统计

| 类型 | 数量 | 详情 |
|------|------|------|
| 新增字段 | 11 | qc_rules 表 |
| 新增表 | 2 | qc_rule_change_logs, departments (可选) |
| 新增索引 | 7 | 包含 1 个唯一索引 |
| 新增约束 | 1 | chk_department_scope |
| 新增函数 | 2 | RPC + 触发器函数 |
| 新增触发器 | 1 | trigger_log_qc_rule_changes |
| 新增视图 | 2 | 统计视图 |

### 数据迁移

- ✅ 所有现有规则设置为 `scope='global'`
- ✅ 所有激活规则设置为 `status='published'`
- ✅ 所有未激活规则设置为 `status='archived'`
- ✅ 插入 8 个示例科室数据

---

## ✅ 验证结果

### 自动验证

运行验证脚本：
```bash
psql -h localhost -U postgres -d medqc -f verify_009.sql
```

验证项目：
- [x] 11 个新增字段存在
- [x] qc_rule_change_logs 表存在
- [x] departments 表存在
- [x] 7 个索引创建成功
- [x] 1 个约束创建成功
- [x] 2 个函数创建成功
- [x] 1 个触发器创建成功
- [x] 2 个视图创建成功
- [x] RPC 函数正常工作
- [x] 触发器正常记录审计日志

### 手动验证

#### 测试 1: 创建科室规则

```sql
-- 创建科室覆盖规则
INSERT INTO qc_rules (
    rule_code, name, scope, department_id, 
    parent_rule_id, override_action, priority, status
) VALUES (
    'COMP_001', '基本信息完整性-外科定制', 'department',
    (SELECT id FROM departments WHERE code = 'DEPT_002'),
    (SELECT id FROM qc_rules WHERE rule_code = 'COMP_001' AND scope = 'global'),
    'override', 10, 'published'
);
```

预期结果：
- ✅ 规则创建成功
- ✅ 审计日志自动记录

#### 测试 2: 禁用全局规则

```sql
-- 儿科禁用成人用药规则
INSERT INTO qc_rules (
    rule_code, name, scope, department_id, 
    override_action, status
) VALUES (
    'RATI_003', '禁用：成人药物剂量合理性', 'department',
    (SELECT id FROM departments WHERE code = 'DEPT_003'),
    'disable', 'published'
);
```

预期结果：
- ✅ 规则创建成功
- ✅ 该科室执行质控时不使用 RATI_003 规则

#### 测试 3: 获取适用规则

```sql
-- 获取外科的适用规则
SELECT rule_code, name, source, priority
FROM get_applicable_qc_rules(
    (SELECT id FROM departments WHERE code = 'DEPT_002'),
    NULL,
    NOW()
)
ORDER BY priority DESC
LIMIT 10;
```

预期结果：
- ✅ 返回全局规则和外科规则
- ✅ 科室规则优先级更高
- ✅ 按优先级排序

---

## 🔄 回滚方案

### 回滚脚本

文件：`009_department_qc_rules_rollback.sql`

执行：
```bash
psql -h localhost -U postgres -d medqc -f 009_department_qc_rules_rollback.sql
```

### 回滚内容

1. 删除视图
2. 删除 RPC 函数
3. 删除触发器和触发器函数
4. 删除 qc_rule_change_logs 表
5. 删除索引
6. 删除约束
7. 删除所有科室规则数据
8. 删除 11 个新增字段

### 注意事项

⚠️ **警告**：回滚将删除所有科室规则数据，执行前请确保已备份！

⚠️ **注意**：departments 表不会被删除（可能被其他功能使用）

---

## 📝 后续步骤

### 第二阶段：后端 API 开发

1. **更新数据模型**
   - [ ] 更新 `app/models/qc_rule.py`
   - [ ] 更新 Pydantic schemas

2. **实现 API 接口**
   - [ ] POST /api/v1/qc/rules/department
   - [ ] PUT /api/v1/qc/rules/department/{id}
   - [ ] DELETE /api/v1/qc/rules/department/{id}
   - [ ] PATCH /api/v1/qc/rules/department/{id}/publish
   - [ ] GET /api/v1/qc/rules/department/{id}/history
   - [ ] GET /api/v1/qc/rules/applicable

3. **集成权限控制**
   - [ ] 使用 @require_role 装饰器
   - [ ] 确保 RLS 策略正确应用

4. **编写单元测试**
   - [ ] 测试规则 CRUD 操作
   - [ ] 测试规则匹配逻辑
   - [ ] 测试权限控制
   - [ ] 测试审计日志

### 第三阶段：前端 UI 开发

1. **更新规则管理页面**
   - [ ] 添加"科室规则"标签页
   - [ ] 实现规则列表（树形展示）
   - [ ] 添加状态筛选
   - [ ] 添加科室筛选

2. **实现规则编辑功能**
   - [ ] 创建/编辑规则表单
   - [ ] 支持"基于全局规则创建"和"全新创建"
   - [ ] 支持"覆盖配置"和"禁用规则"
   - [ ] 生效期选择器

3. **实现规则发布功能**
   - [ ] 草稿规则发布按钮
   - [ ] 发布确认对话框
   - [ ] 审核信息记录

4. **实现变更历史查看**
   - [ ] 变更历史时间线
   - [ ] 变更前后对比视图
   - [ ] 显示操作人和原因

---

## 🎯 验收标准

- [x] 数据库迁移成功，无数据丢失
- [x] 所有索引和约束创建成功
- [x] RPC 函数正常工作
- [x] 触发器正常记录审计日志
- [x] 验证脚本全部通过
- [ ] 后端 API 接口正常工作
- [ ] 前端 UI 功能完整
- [ ] 所有单元测试通过（覆盖率 > 80%）
- [ ] 所有集成测试通过
- [ ] 性能指标达标

---

## 📚 参考资料

### 迁移文件

- `009_department_qc_rules.sql` - 主迁移脚本
- `009_department_qc_rules_rollback.sql` - 回滚脚本
- `verify_009.sql` - 验证脚本

### 文档

- [PRD 主文档](../../../../docs/PRD_DEPARTMENT_QC_RULES.md)
- [变更日志](../../../../docs/PRD_DEPARTMENT_QC_RULES_CHANGELOG.md)
- [评审响应](../../../../docs/PRD_DEPARTMENT_QC_RULES_REVIEW_RESPONSE.md)
- [设计总结](../../../../docs/PRD_DEPARTMENT_QC_RULES_SUMMARY.md)

---

## ✅ 签署

| 角色 | 姓名 | 日期 | 签名 |
|------|------|------|------|
| 数据库工程师 | - | 2025-10-12 | ✅ |
| 后端开发负责人 | - | - | ⏳ |
| 前端开发负责人 | - | - | ⏳ |
| QA 负责人 | - | - | ⏳ |
| 技术负责人 | - | - | ⏳ |

---

**文档版本**: 1.0  
**最后更新**: 2025-10-12  
**维护者**: Database Team

