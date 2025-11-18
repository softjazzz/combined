# Supabase 后台执行 Migration 009 指南

## 📋 执行步骤

### 步骤 1: 登录 Supabase Dashboard

1. 访问: https://supabase.com/dashboard
2. 登录您的账号
3. 选择项目: `dgsdkdbjpucyawnyfbdu`

### 步骤 2: 打开 SQL Editor

1. 在左侧菜单中点击 **"SQL Editor"**
2. 点击 **"New query"** 创建新查询

### 步骤 3: 执行 Migration 009

**复制下面的完整 SQL 脚本，粘贴到 SQL Editor 中，然后点击 "Run" 执行。**

---

## 📝 SQL 脚本

### Migration 009 完整脚本

**文件位置**: `infra/supabase/medqc/migrations/009_department_qc_rules.sql`

**说明**: 这个脚本会：
- 扩展 `qc_rules` 表，添加 11 个新字段
- 创建 `qc_rule_change_logs` 审计日志表
- 创建 `get_applicable_qc_rules` RPC 函数
- 创建触发器自动记录规则变更
- 创建辅助视图和索引

**执行时间**: 约 5-10 秒

**脚本内容**: 请复制以下完整脚本

```sql
-- 完整的 Migration 009 脚本在下一个文件中
-- 由于脚本较长（806 行），请直接复制文件内容
```

---

## ✅ 步骤 4: 验证执行结果

执行 Migration 009 后，创建**新的查询**，复制以下验证脚本并执行：

### 验证脚本（简化版）

```sql
-- ============================================================================
-- 验证 Migration 009 是否成功执行
-- ============================================================================

-- 1. 检查新增字段（应该返回 11 行）
SELECT 
    column_name,
    data_type,
    is_nullable
FROM information_schema.columns
WHERE table_name = 'qc_rules'
AND column_name IN (
    'scope', 'department_id', 'parent_rule_id', 'override_action',
    'override_config', 'priority', 'status', 'effective_from',
    'effective_to', 'approved_by', 'approved_at'
)
ORDER BY column_name;

-- 2. 检查审计日志表（应该返回 1 行）
SELECT table_name, table_type
FROM information_schema.tables
WHERE table_name = 'qc_rule_change_logs';

-- 3. 检查 RPC 函数（应该返回 2 行）
SELECT proname AS function_name, pronargs AS num_args
FROM pg_proc
WHERE proname IN ('get_applicable_qc_rules', 'log_qc_rule_changes')
ORDER BY proname;

-- 4. 检查索引（应该返回 7 行）
SELECT indexname, tablename
FROM pg_indexes
WHERE tablename = 'qc_rules'
AND indexname IN (
    'uk_dept_rule_code_published',
    'idx_qc_rules_scope',
    'idx_qc_rules_department',
    'idx_qc_rules_parent',
    'idx_qc_rules_status',
    'idx_qc_rules_effective',
    'idx_qc_rules_composite'
)
ORDER BY indexname;

-- 5. 检查数据（所有现有规则应该是 global/published）
SELECT 
    scope,
    status,
    COUNT(*) AS count
FROM qc_rules
GROUP BY scope, status
ORDER BY scope, status;

-- 6. 检查科室表（应该返回 8 个示例科室）
SELECT code, name, is_active
FROM departments
ORDER BY code;
```

### 预期结果

如果 Migration 执行成功，您应该看到：

1. **新增字段**: 11 个字段（scope, department_id, parent_rule_id 等）
2. **审计日志表**: `qc_rule_change_logs` 表存在
3. **RPC 函数**: 2 个函数（get_applicable_qc_rules, log_qc_rule_changes）
4. **索引**: 7 个索引
5. **数据**: 所有现有规则的 scope 为 'global'，status 为 'published'
6. **科室**: 8 个示例科室（内科、外科、儿科等）

---

## 🔄 步骤 5: 重新运行集成测试

Migration 执行成功后，回到终端运行测试：

```bash
cd /home/ubuntu/coding/health-qc-monorepo/tests/integration
python3 test_api_basic.py
```

**预期结果**: 所有 5 个测试都应该通过 ✅

---

## 🚨 如果遇到问题

### 问题 1: 执行失败，提示字段已存在

**原因**: Migration 可能已经部分执行过

**解决方案**: 
1. 先执行回滚脚本（见下方）
2. 然后重新执行 Migration 009

### 问题 2: 权限不足

**原因**: 当前用户没有足够的数据库权限

**解决方案**: 
1. 确保使用 `postgres` 用户登录
2. 或联系 Supabase 管理员

### 问题 3: 验证失败

**原因**: 某些步骤没有成功执行

**解决方案**: 
1. 查看 SQL Editor 的错误信息
2. 记录错误内容
3. 执行回滚脚本
4. 重新执行 Migration

---

## 🔙 回滚脚本（如果需要）

如果 Migration 执行出现问题，可以使用以下回滚脚本：

**文件位置**: `infra/supabase/medqc/migrations/009_department_qc_rules_rollback.sql`

**警告**: 回滚会删除所有科室规则数据和审计日志！

```sql
-- 回滚 Migration 009
-- 警告：这会删除所有科室规则和审计日志！

-- 删除触发器
DROP TRIGGER IF EXISTS trigger_log_qc_rule_changes ON qc_rules;

-- 删除函数
DROP FUNCTION IF EXISTS log_qc_rule_changes();
DROP FUNCTION IF EXISTS get_applicable_qc_rules(UUID, TEXT, TIMESTAMPTZ);

-- 删除视图
DROP VIEW IF EXISTS qc_rules_by_department;
DROP VIEW IF EXISTS qc_rules_department_statistics;

-- 删除审计日志表
DROP TABLE IF EXISTS qc_rule_change_logs;

-- 删除索引
DROP INDEX IF EXISTS idx_qc_rules_composite;
DROP INDEX IF EXISTS idx_qc_rules_effective;
DROP INDEX IF EXISTS idx_qc_rules_status;
DROP INDEX IF EXISTS idx_qc_rules_parent;
DROP INDEX IF EXISTS idx_qc_rules_department;
DROP INDEX IF EXISTS idx_qc_rules_scope;
DROP INDEX IF EXISTS uk_dept_rule_code_published;

-- 删除约束
ALTER TABLE qc_rules DROP CONSTRAINT IF EXISTS chk_department_scope;

-- 删除新增字段
ALTER TABLE qc_rules DROP COLUMN IF EXISTS approved_at;
ALTER TABLE qc_rules DROP COLUMN IF EXISTS approved_by;
ALTER TABLE qc_rules DROP COLUMN IF EXISTS effective_to;
ALTER TABLE qc_rules DROP COLUMN IF EXISTS effective_from;
ALTER TABLE qc_rules DROP COLUMN IF EXISTS status;
ALTER TABLE qc_rules DROP COLUMN IF EXISTS priority;
ALTER TABLE qc_rules DROP COLUMN IF EXISTS override_config;
ALTER TABLE qc_rules DROP COLUMN IF EXISTS override_action;
ALTER TABLE qc_rules DROP COLUMN IF EXISTS parent_rule_id;
ALTER TABLE qc_rules DROP COLUMN IF EXISTS department_id;
ALTER TABLE qc_rules DROP COLUMN IF EXISTS scope;

-- 注意：不删除 departments 表，因为可能有其他地方使用

SELECT 'Migration 009 rolled back successfully' AS status;
```

---

## 📚 相关文档

- [Migration 009 完整脚本](../../infra/supabase/medqc/migrations/009_department_qc_rules.sql)
- [Migration 009 验证脚本](../../infra/supabase/medqc/migrations/verify_009.sql)
- [Migration 009 完成报告](../../infra/supabase/medqc/migrations/MIGRATION_009_COMPLETION_REPORT.md)
- [快速启动指南](../../docs/DEPARTMENT_RULES_QUICK_START.md)

---

## ✅ 完成检查清单

- [ ] 登录 Supabase Dashboard
- [ ] 打开 SQL Editor
- [ ] 执行 Migration 009 脚本
- [ ] 执行验证脚本
- [ ] 确认所有验证通过
- [ ] 重新运行集成测试
- [ ] 确认所有测试通过

---

**准备好了吗？请继续下一页获取完整的 Migration 009 SQL 脚本！**

