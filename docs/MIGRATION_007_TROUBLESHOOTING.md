# Migration 007 故障排除指南

> 📅 **更新日期**: 2025-10-12  
> 🎯 **目的**: 解决执行迁移 007 时遇到的问题

---

## ❌ 问题：user_roles 表不存在

### 错误信息
```
Error: Failed to run sql query: {"error":"ERROR: 42P01: relation \"user_roles\" does not exist\nLINE 19: FROM user_roles \r\n ^\n",...}
```

### 原因分析
`user_roles` 表在初始化脚本 `000_init_base_schema.sql` 中定义，但可能还没有在你的 Supabase 数据库中创建。

---

## ✅ 解决方案

### 方案 1: 使用更新后的迁移脚本（推荐）

我已经更新了 `007_enhance_rls_policies.sql`，它现在会自动创建 `user_roles` 表（如果不存在）。

**步骤**:

1. **在 Supabase Dashboard SQL Editor 中执行预检查脚本**
   ```sql
   -- 复制 infra/supabase/medqc/migrations/pre_check_007.sql 的内容
   -- 粘贴到 SQL Editor
   -- 点击 "Run" 按钮
   ```

   **预期输出**:
   ```
   ==============================================
   开始检查数据库状态...
   ==============================================
   ✅ medical_records 表存在
   ✅ qc_rules 表存在
   ✅ qc_results 表存在
   ⚠️  user_roles 表不存在（迁移 007 会自动创建）
   ==============================================
   检查完成！
   ==============================================
   ```

2. **执行更新后的迁移 007**
   ```sql
   -- 复制 infra/supabase/medqc/migrations/007_enhance_rls_policies.sql 的全部内容
   -- 粘贴到 SQL Editor
   -- 点击 "Run" 按钮
   ```

   **预期输出**:
   ```
   ==============================================
   RLS 策略增强完成！
   已创建基于角色的细粒度访问控制策略
   ==============================================
   ```

---

### 方案 2: 先创建基础表（如果方案 1 失败）

如果你的数据库中缺少其他基础表（medical_records, qc_rules, qc_results），需要先执行初始化脚本。

**步骤**:

1. **检查哪些表缺失**
   ```sql
   SELECT table_name
   FROM information_schema.tables
   WHERE table_schema = 'public'
   AND table_name IN ('medical_records', 'qc_rules', 'qc_results', 'user_roles')
   ORDER BY table_name;
   ```

2. **如果缺少基础表，执行初始化脚本**
   ```sql
   -- 复制 infra/supabase/medqc/migrations/000_init_base_schema.sql 的内容
   -- 粘贴到 SQL Editor
   -- 点击 "Run" 按钮
   ```

3. **然后执行迁移 007**
   ```sql
   -- 复制 infra/supabase/medqc/migrations/007_enhance_rls_policies.sql 的内容
   -- 粘贴到 SQL Editor
   -- 点击 "Run" 按钮
   ```

---

### 方案 3: 手动创建 user_roles 表

如果你只想创建 `user_roles` 表而不执行完整的初始化脚本：

```sql
-- 创建 user_roles 表
CREATE TABLE IF NOT EXISTS user_roles (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID NOT NULL,
  role TEXT NOT NULL CHECK (role IN ('admin', 'qc_manager', 'qc_staff', 'doctor')),
  hospital_id TEXT,
  department TEXT,
  created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
  UNIQUE(user_id, role)
);

-- 创建索引
CREATE INDEX IF NOT EXISTS idx_user_roles_user ON user_roles(user_id);
CREATE INDEX IF NOT EXISTS idx_user_roles_role ON user_roles(role);

-- 启用 RLS
ALTER TABLE user_roles ENABLE ROW LEVEL SECURITY;

-- 验证表已创建
SELECT * FROM user_roles LIMIT 1;
```

然后执行迁移 007。

---

## 🔍 验证迁移成功

执行以下 SQL 验证迁移是否成功：

### 1. 检查辅助函数是否创建
```sql
SELECT proname, proargnames, prosrc
FROM pg_proc
WHERE proname IN ('get_user_roles', 'has_role', 'has_any_role')
ORDER BY proname;
```

**预期结果**: 应该返回 3 个函数

---

### 2. 检查 RLS 策略是否创建
```sql
SELECT 
  tablename,
  policyname,
  permissive,
  cmd
FROM pg_policies
WHERE tablename IN ('medical_records', 'qc_rules', 'qc_results', 'user_roles')
ORDER BY tablename, policyname;
```

**预期结果**: 应该返回 16 条策略

**详细列表**:
- `medical_records`: 5 条策略
  - admin_qc_view_all_medical_records
  - doctor_view_own_medical_records
  - admin_qc_manager_create_medical_records
  - admin_qc_manager_update_medical_records
  - admin_delete_medical_records

- `qc_rules`: 4 条策略
  - authenticated_view_qc_rules
  - admin_qc_manager_create_qc_rules
  - admin_qc_manager_update_qc_rules
  - admin_delete_qc_rules

- `qc_results`: 4 条策略
  - authenticated_view_qc_results
  - qc_staff_create_qc_results
  - qc_staff_update_qc_results
  - admin_qc_manager_delete_qc_results

- `user_roles`: 3 条策略
  - users_view_own_roles
  - admin_view_all_roles
  - admin_manage_roles

---

### 3. 检查 user_roles 表结构
```sql
\d user_roles
```

**预期结果**:
```
                          Table "public.user_roles"
   Column    |           Type           | Collation | Nullable |      Default
-------------+--------------------------+-----------+----------+-------------------
 id          | uuid                     |           | not null | gen_random_uuid()
 user_id     | uuid                     |           | not null |
 role        | text                     |           | not null |
 hospital_id | text                     |           |          |
 department  | text                     |           |          |
 created_at  | timestamp with time zone |           |          | now()
Indexes:
    "user_roles_pkey" PRIMARY KEY, btree (id)
    "user_roles_user_id_role_key" UNIQUE CONSTRAINT, btree (user_id, role)
    "idx_user_roles_role" btree (role)
    "idx_user_roles_user" btree (user_id)
Check constraints:
    "user_roles_role_check" CHECK (role = ANY (ARRAY['admin'::text, 'qc_manager'::text, 'qc_staff'::text, 'doctor'::text]))
Policies:
    POLICY "admin_manage_roles"
    POLICY "admin_view_all_roles"
    POLICY "users_view_own_roles"
```

---

### 4. 测试辅助函数
```sql
-- 插入测试数据
INSERT INTO user_roles (user_id, role) 
VALUES 
  ('00000000-0000-0000-0000-000000000001'::uuid, 'admin'),
  ('00000000-0000-0000-0000-000000000002'::uuid, 'qc_manager')
ON CONFLICT (user_id, role) DO NOTHING;

-- 测试 get_user_roles 函数
SELECT get_user_roles('00000000-0000-0000-0000-000000000001'::uuid);
-- 预期结果: {admin}

-- 测试 has_role 函数
SELECT has_role('00000000-0000-0000-0000-000000000001'::uuid, 'admin');
-- 预期结果: true

-- 测试 has_any_role 函数
SELECT has_any_role('00000000-0000-0000-0000-000000000002'::uuid, ARRAY['admin', 'qc_manager']);
-- 预期结果: true

-- 清理测试数据（可选）
DELETE FROM user_roles WHERE user_id IN (
  '00000000-0000-0000-0000-000000000001'::uuid,
  '00000000-0000-0000-0000-000000000002'::uuid
);
```

---

## 📝 更新后的迁移 007 变更

### 新增内容（第 0 节）

```sql
-- 0. 确保 user_roles 表存在（如果不存在则创建）
CREATE TABLE IF NOT EXISTS user_roles (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID NOT NULL,
  role TEXT NOT NULL CHECK (role IN ('admin', 'qc_manager', 'qc_staff', 'doctor')),
  hospital_id TEXT,
  department TEXT,
  created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
  UNIQUE(user_id, role)
);

-- 创建索引（如果不存在）
CREATE INDEX IF NOT EXISTS idx_user_roles_user ON user_roles(user_id);
CREATE INDEX IF NOT EXISTS idx_user_roles_role ON user_roles(role);

-- 启用 RLS（如果还没启用）
ALTER TABLE user_roles ENABLE ROW LEVEL SECURITY;
```

这段代码会：
- ✅ 检查 `user_roles` 表是否存在
- ✅ 如果不存在，则创建表
- ✅ 如果存在，则跳过（不会报错）
- ✅ 创建必要的索引
- ✅ 启用 RLS

---

## 🚀 快速执行步骤

### 完整流程（推荐）

```bash
# 1. 在 Supabase Dashboard SQL Editor 中执行

# 步骤 1: 预检查
-- 复制并执行 pre_check_007.sql

# 步骤 2: 执行迁移 007
-- 复制并执行 007_enhance_rls_policies.sql

# 步骤 3: 验证
-- 执行上面的验证 SQL

# 步骤 4: 执行迁移 008
-- 复制并执行 008_add_permission_audit_logs.sql
```

---

## ⚠️ 常见问题

### Q1: 如果执行迁移时仍然报错怎么办？

**A**: 请提供完整的错误信息，包括：
- 错误代码
- 错误消息
- 出错的 SQL 行号
- 当前数据库中的表列表

### Q2: 如何回滚迁移 007？

**A**: 执行以下 SQL：
```sql
-- 删除 RLS 策略
DROP POLICY IF EXISTS "admin_qc_view_all_medical_records" ON medical_records;
DROP POLICY IF EXISTS "doctor_view_own_medical_records" ON medical_records;
-- ... 删除所有策略

-- 删除辅助函数
DROP FUNCTION IF EXISTS get_user_roles(UUID);
DROP FUNCTION IF EXISTS has_role(UUID, TEXT);
DROP FUNCTION IF EXISTS has_any_role(UUID, TEXT[]);

-- 恢复旧策略（可选）
CREATE POLICY "认证用户可以查看医疗记录" ON medical_records
  FOR SELECT USING (auth.role() = 'authenticated');
```

### Q3: user_roles 表已存在但结构不同怎么办？

**A**: 检查表结构差异：
```sql
\d user_roles
```

如果需要修改表结构，可以使用 `ALTER TABLE` 命令。

---

**文档版本**: 1.0  
**最后更新**: 2025-10-12  
**维护者**: Augment Agent

