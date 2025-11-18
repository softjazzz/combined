# Migration 009: 科室级质控规则配置功能

> **版本**: 2.0  
> **创建日期**: 2025-10-12  
> **状态**: ✅ 已完成

---

## 📋 概述

本迁移实现了科室级质控规则配置功能，允许为不同科室设置个性化的质控规则。

### 核心功能

1. **科室级规则配置** - 支持科室覆盖全局规则或创建科室特有规则
2. **规则版本管理** - 支持草稿、发布、归档状态
3. **生效期控制** - 支持规则定时生效和失效
4. **规则覆盖和禁用** - 支持覆盖全局规则配置或禁用全局规则
5. **变更审计** - 自动记录所有规则变更
6. **统一规则匹配** - 通过 RPC 函数统一规则匹配逻辑

---

## 📁 文件清单

| 文件 | 说明 |
|------|------|
| `009_department_qc_rules.sql` | 主迁移脚本 |
| `009_department_qc_rules_rollback.sql` | 回滚脚本 |
| `verify_009.sql` | 验证脚本 |
| `test_009_migration.sh` | 自动化测试脚本 |
| `README_009.md` | 本文档 |
| `MIGRATION_009_COMPLETION_REPORT.md` | 完成报告 |

---

## 🚀 快速开始

### 前置条件

1. PostgreSQL 数据库已安装并运行
2. 已执行之前的迁移（Migration 001-008）
3. 有数据库管理员权限

### 执行迁移

#### 方法 1: 使用自动化测试脚本（推荐）

```bash
# 进入迁移目录
cd infra/supabase/medqc/migrations

# 赋予执行权限
chmod +x test_009_migration.sh

# 执行测试脚本
./test_009_migration.sh
```

脚本会自动：
- 检查数据库连接
- 备份现有数据
- 执行迁移
- 验证迁移结果
- 可选：测试回滚

#### 方法 2: 手动执行

```bash
# 1. 执行迁移
psql -h localhost -U postgres -d medqc -f 009_department_qc_rules.sql

# 2. 验证迁移
psql -h localhost -U postgres -d medqc -f verify_009.sql
```

### Supabase 环境

如果使用 Supabase，可以通过 SQL Editor 执行：

1. 登录 Supabase Dashboard
2. 进入 SQL Editor
3. 复制 `009_department_qc_rules.sql` 内容
4. 执行
5. 复制 `verify_009.sql` 内容验证

---

## 📊 变更详情

### 数据库表变更

#### 1. 扩展 `qc_rules` 表

新增 11 个字段：

```sql
-- 规则范围和科室
scope VARCHAR(20) DEFAULT 'global'
department_id UUID
parent_rule_id UUID

-- 覆盖配置
override_action VARCHAR(20) DEFAULT 'override'
override_config JSONB DEFAULT '{}'
priority INTEGER DEFAULT 0

-- 版本和生效期
status VARCHAR(20) DEFAULT 'published'
effective_from TIMESTAMPTZ
effective_to TIMESTAMPTZ

-- 审核信息
approved_by UUID
approved_at TIMESTAMPTZ
```

#### 2. 新增 `qc_rule_change_logs` 表

审计日志表，自动记录所有规则变更。

#### 3. 新增 `departments` 表（如果不存在）

科室表，包含 8 个示例科室数据。

### 索引和约束

- **唯一索引**: `uk_dept_rule_code_published` - 确保同科室同规则编号的已发布规则唯一
- **普通索引**: 6 个索引优化查询性能
- **约束**: `chk_department_scope` - 确保科室规则必须关联科室

### 函数和触发器

- **RPC 函数**: `get_applicable_qc_rules()` - 获取适用的质控规则
- **触发器函数**: `log_qc_rule_changes()` - 自动记录规则变更
- **触发器**: `trigger_log_qc_rule_changes` - 在规则变更时触发

### 视图

- `qc_rules_department_statistics` - 规则统计视图
- `qc_rules_by_department` - 按科室统计规则

---

## 🧪 测试和验证

### 自动验证

执行验证脚本：

```bash
psql -h localhost -U postgres -d medqc -f verify_009.sql
```

验证项目：
- ✅ 11 个新增字段
- ✅ 2 个新增表
- ✅ 7 个索引
- ✅ 1 个约束
- ✅ 2 个函数
- ✅ 1 个触发器
- ✅ 2 个视图
- ✅ RPC 函数正常工作
- ✅ 触发器正常记录审计日志

### 手动测试

#### 测试 1: 创建科室覆盖规则

```sql
-- 外科覆盖全局规则
INSERT INTO qc_rules (
    rule_code, name, description, category, rule_type, severity,
    scope, department_id, parent_rule_id, override_action, priority, status,
    check_logic, scoring_config
) VALUES (
    'COMP_001', '基本信息完整性-外科定制', '外科科室的基本信息完整性检查',
    'completeness', 'objective', 'critical',
    'department', 
    (SELECT id FROM departments WHERE code = 'DEPT_002'),
    (SELECT id FROM qc_rules WHERE rule_code = 'COMP_001' AND scope = 'global'),
    'override', 10, 'published',
    '{}', '{"default_deduction": 10, "max_deduction": 20}'
);

-- 验证：检查审计日志
SELECT * FROM qc_rule_change_logs 
WHERE action = 'create' 
ORDER BY created_at DESC 
LIMIT 1;
```

#### 测试 2: 禁用全局规则

```sql
-- 儿科禁用成人用药规则
INSERT INTO qc_rules (
    rule_code, name, description, category, rule_type, severity,
    scope, department_id, override_action, status
) VALUES (
    'RATI_003', '禁用：成人药物剂量合理性', '儿科使用儿童用药剂量标准',
    'rationality', 'hybrid', 'major',
    'department',
    (SELECT id FROM departments WHERE code = 'DEPT_003'),
    'disable', 'published'
);

-- 验证：获取儿科的适用规则（应该不包含 RATI_003）
SELECT rule_code, name, source
FROM get_applicable_qc_rules(
    (SELECT id FROM departments WHERE code = 'DEPT_003'),
    NULL,
    NOW()
)
WHERE rule_code = 'RATI_003';
-- 应该返回 0 行
```

#### 测试 3: 测试 RPC 函数

```sql
-- 获取外科的适用规则
SELECT 
    rule_code,
    name,
    source,
    priority,
    override_action
FROM get_applicable_qc_rules(
    (SELECT id FROM departments WHERE code = 'DEPT_002'),
    NULL,
    NOW()
)
ORDER BY priority DESC, rule_code
LIMIT 10;
```

#### 测试 4: 测试生效期

```sql
-- 创建未来生效的规则
INSERT INTO qc_rules (
    rule_code, name, category, rule_type, severity,
    scope, status, effective_from, check_logic, scoring_config
) VALUES (
    'TEST_FUTURE', '未来生效的测试规则', 'completeness', 'objective', 'minor',
    'global', 'published', NOW() + INTERVAL '1 day', '{}', '{}'
);

-- 验证：当前时间获取规则（应该不包含 TEST_FUTURE）
SELECT rule_code FROM get_applicable_qc_rules(
    (SELECT id FROM departments LIMIT 1),
    NULL,
    NOW()
)
WHERE rule_code = 'TEST_FUTURE';
-- 应该返回 0 行

-- 验证：未来时间获取规则（应该包含 TEST_FUTURE）
SELECT rule_code FROM get_applicable_qc_rules(
    (SELECT id FROM departments LIMIT 1),
    NULL,
    NOW() + INTERVAL '2 days'
)
WHERE rule_code = 'TEST_FUTURE';
-- 应该返回 1 行

-- 清理测试数据
DELETE FROM qc_rules WHERE rule_code = 'TEST_FUTURE';
```

---

## 🔄 回滚

### 执行回滚

⚠️ **警告**：回滚将删除所有科室规则数据，执行前请确保已备份！

```bash
# 备份数据
pg_dump -h localhost -U postgres -d medqc -t qc_rules > qc_rules_backup.sql
pg_dump -h localhost -U postgres -d medqc -t qc_rule_change_logs > qc_rule_change_logs_backup.sql

# 执行回滚
psql -h localhost -U postgres -d medqc -f 009_department_qc_rules_rollback.sql
```

### 回滚内容

- 删除 11 个新增字段
- 删除 qc_rule_change_logs 表
- 删除所有索引和约束
- 删除所有函数和触发器
- 删除所有视图
- 删除所有科室规则数据

### 注意事项

- departments 表不会被删除（可能被其他功能使用）
- 如需删除 departments 表，请手动执行：`DROP TABLE departments CASCADE;`

---

## 📝 常见问题

### Q1: 迁移失败，提示"qc_rules table does not exist"

**A**: 请先执行之前的迁移（Migration 001-008），确保 qc_rules 表已创建。

### Q2: 迁移成功，但验证失败

**A**: 检查验证脚本的输出，确认哪些验证项失败。常见原因：
- 数据库权限不足
- 之前的迁移未完全执行
- 数据库版本不兼容

### Q3: 如何查看审计日志？

**A**: 查询 qc_rule_change_logs 表：

```sql
-- 查看最近的变更
SELECT 
    action,
    rule_id,
    actor_id,
    created_at
FROM qc_rule_change_logs
ORDER BY created_at DESC
LIMIT 10;

-- 查看特定规则的变更历史
SELECT 
    action,
    old_values->>'name' AS old_name,
    new_values->>'name' AS new_name,
    created_at
FROM qc_rule_change_logs
WHERE rule_id = 'your-rule-id'
ORDER BY created_at DESC;
```

### Q4: 如何设置当前用户ID（用于审计日志）？

**A**: 在应用层执行 SQL 前设置：

```sql
-- 设置当前用户ID
SET app.current_user_id = 'your-user-id';

-- 然后执行规则变更操作
INSERT INTO qc_rules (...) VALUES (...);

-- 审计日志会自动记录 your-user-id 作为 actor_id
```

### Q5: RPC 函数返回的规则数量不对

**A**: 检查以下几点：
- 规则的 status 是否为 'published'
- 规则的 is_active 是否为 true
- 规则的生效期是否包含当前时间
- 科室规则是否正确设置了 department_id

---

## 📚 相关文档

- [PRD 主文档](../../../../docs/PRD_DEPARTMENT_QC_RULES.md)
- [变更日志](../../../../docs/PRD_DEPARTMENT_QC_RULES_CHANGELOG.md)
- [评审响应](../../../../docs/PRD_DEPARTMENT_QC_RULES_REVIEW_RESPONSE.md)
- [设计总结](../../../../docs/PRD_DEPARTMENT_QC_RULES_SUMMARY.md)
- [完成报告](./MIGRATION_009_COMPLETION_REPORT.md)

---

## 🎯 下一步

迁移完成后，请继续：

1. **后端 API 开发** - 实现科室规则 CRUD 接口
2. **前端 UI 开发** - 实现规则管理界面
3. **集成测试** - 测试完整的规则配置流程
4. **性能测试** - 验证规则匹配性能

详见：[PRD 主文档 - 实施计划](../../../../docs/PRD_DEPARTMENT_QC_RULES.md#9-实施计划)

---

**文档版本**: 1.0  
**最后更新**: 2025-10-12  
**维护者**: Database Team

