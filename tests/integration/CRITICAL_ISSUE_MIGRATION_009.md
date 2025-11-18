# 🚨 关键问题：Migration 009 未执行

**发现时间**: 2025-10-13  
**严重级别**: P0 (阻塞)  
**影响范围**: 所有科室规则相关功能无法使用

---

## 📋 问题描述

在执行第四阶段集成测试时，发现所有科室规则相关的 API 端点都返回 400 Bad Request 错误。

**错误示例**:
```
HTTP Request: GET https://dgsdkdbjpucyawnyfbdu.supabase.co/rest/v1/qc_rules?select=%2A&scope=eq.department
HTTP/1.1 400 Bad Request
```

---

## 🔍 根本原因分析

通过深入调试，发现问题的根本原因是：

### **Migration 009 还没有在 Supabase 数据库上执行！**

**证据 1**: 查询 `qc_rules` 表返回的数据中缺少 Migration 009 新增的字段

```bash
# 查询现有字段
curl "http://localhost:8001/api/v1/qc/rules/department?page=1&limit=1" \
  -H "Authorization: Bearer <token>" | \
  python3 -c "import sys, json; data = json.load(sys.stdin); print(list(data['data']['items'][0].keys()))"

# 实际输出（缺少 scope, department_id 等字段）:
['id', 'rule_code', 'name', 'description', 'category', 'subcategory', 
 'rule_type', 'severity', 'applicable_record_types', 'applicable_departments', 
 'target_sections', 'check_logic', 'scoring_config', 'prompt_template', 
 'examples', 'is_active', 'execution_order', 'estimated_tokens', 
 'timeout_seconds', 'version', 'created_by', 'created_at', 'updated_at', 
 'document_categories', 'primary_document_category', 'applicable_documents']
```

**证据 2**: Migration 009 应该新增的字段

根据 `infra/supabase/medqc/migrations/009_department_qc_rules.sql`，应该新增以下字段：

| 字段名 | 类型 | 说明 |
|--------|------|------|
| `scope` | VARCHAR(20) | 规则范围（'global' 或 'department'） |
| `department_id` | UUID | 科室 ID（外键） |
| `parent_rule_id` | UUID | 父规则 ID（用于继承） |
| `override_action` | VARCHAR(20) | 覆盖行为（'override' 或 'disable'） |
| `override_config` | JSONB | 覆盖配置 |
| `priority` | INTEGER | 优先级 |
| `status` | VARCHAR(20) | 状态（'draft', 'published', 'archived'） |
| `version` | INTEGER | 版本号 |
| `effective_from` | TIMESTAMPTZ | 生效开始时间 |
| `effective_to` | TIMESTAMPTZ | 生效结束时间 |
| `approved_by` | UUID | 审批人 ID |
| `approved_at` | TIMESTAMPTZ | 审批时间 |

**证据 3**: PostgREST 返回 400 错误

当代码尝试查询 `scope=eq.department` 时，PostgREST 返回 400 错误，因为 `scope` 字段不存在。

---

## 🔧 解决方案

### 方案 A: 使用 Supabase Dashboard（推荐）

这是最简单、最安全的方法。

**步骤**:

1. **登录 Supabase Dashboard**
   - 访问: https://supabase.com/dashboard
   - 登录您的账号

2. **选择项目**
   - 项目 URL: `https://dgsdkdbjpucyawnyfbdu.supabase.co`
   - 项目名称: (您的项目名称)

3. **打开 SQL Editor**
   - 在左侧菜单中点击 "SQL Editor"
   - 点击 "New query"

4. **执行 Migration 009**
   - 复制 Migration 009 脚本内容:
     ```bash
     cat /home/ubuntu/coding/health-qc-monorepo/infra/supabase/medqc/migrations/009_department_qc_rules.sql
     ```
   - 粘贴到 SQL Editor 中
   - 点击 "Run" 执行

5. **验证执行结果**
   - 创建新的查询
   - 复制验证脚本内容:
     ```bash
     cat /home/ubuntu/coding/health-qc-monorepo/infra/supabase/medqc/migrations/verify_009.sql
     ```
   - 粘贴并执行
   - 检查输出，确保所有检查都通过

**预期输出**:
```
✅ qc_rules 表存在
✅ scope 字段存在
✅ department_id 字段存在
✅ parent_rule_id 字段存在
✅ override_action 字段存在
✅ priority 字段存在
✅ status 字段存在
✅ qc_rule_change_logs 表存在
✅ get_applicable_qc_rules 函数存在
✅ trigger_log_qc_rule_changes 触发器存在
```

---

### 方案 B: 使用 psql 命令行

如果您有 Supabase 数据库的直接连接信息（主机、端口、密码），可以使用 psql 命令行。

**前提条件**:
- 已安装 PostgreSQL 客户端工具（psql）
- 知道 Supabase 数据库的连接信息

**步骤**:

1. **获取数据库连接信息**
   - 登录 Supabase Dashboard
   - 进入 Settings > Database
   - 复制 "Connection string" 或记录以下信息：
     - Host: `db.dgsdkdbjpucyawnyfbdu.supabase.co`
     - Port: `5432`
     - Database: `postgres`
     - User: `postgres`
     - Password: (您的数据库密码)

2. **执行 Migration 009**
   ```bash
   cd /home/ubuntu/coding/health-qc-monorepo/infra/supabase/medqc/migrations
   
   # 方式 1: 使用连接字符串
   psql "postgresql://postgres:[YOUR-PASSWORD]@db.dgsdkdbjpucyawnyfbdu.supabase.co:5432/postgres" \
        -f 009_department_qc_rules.sql
   
   # 方式 2: 使用单独的参数
   psql -h db.dgsdkdbjpucyawnyfbdu.supabase.co \
        -p 5432 \
        -U postgres \
        -d postgres \
        -f 009_department_qc_rules.sql
   ```

3. **验证执行结果**
   ```bash
   psql "postgresql://postgres:[YOUR-PASSWORD]@db.dgsdkdbjpucyawnyfbdu.supabase.co:5432/postgres" \
        -f verify_009.sql
   ```

---

### 方案 C: 使用 Supabase CLI

如果您已安装 Supabase CLI，可以使用以下命令。

**前提条件**:
- 已安装 Supabase CLI: `npm install -g supabase`
- 已链接到项目: `supabase link --project-ref dgsdkdbjpucyawnyfbdu`

**步骤**:

```bash
cd /home/ubuntu/coding/health-qc-monorepo

# 推送迁移到 Supabase
supabase db push

# 或者执行特定的迁移文件
supabase db execute -f infra/supabase/medqc/migrations/009_department_qc_rules.sql
```

---

## ✅ 验证 Migration 是否成功

执行 Migration 后，使用以下方法验证：

### 方法 1: 运行验证脚本

```bash
cd /home/ubuntu/coding/health-qc-monorepo/infra/supabase/medqc/migrations

# 使用 Supabase Dashboard 的 SQL Editor 执行
cat verify_009.sql

# 或使用 psql
psql "postgresql://postgres:[YOUR-PASSWORD]@db.dgsdkdbjpucyawnyfbdu.supabase.co:5432/postgres" \
     -f verify_009.sql
```

### 方法 2: 运行集成测试

```bash
cd /home/ubuntu/coding/health-qc-monorepo/tests/integration

# 运行基础 API 测试
python3 test_api_basic.py
```

**预期结果**: 所有 5 个测试都应该通过：
```
✅ 后端健康检查: 通过
✅ API 文档可访问性: 通过
✅ 登录功能: 通过
✅ 规则列表端点（带认证）: 通过
✅ 获取适用规则端点（带认证）: 通过
```

### 方法 3: 手动查询数据库

```sql
-- 检查 scope 字段是否存在
SELECT column_name, data_type 
FROM information_schema.columns 
WHERE table_name = 'qc_rules' 
  AND column_name = 'scope';

-- 预期输出:
-- column_name | data_type
-- ------------+-----------
-- scope       | character varying
```

---

## 📝 执行后的后续步骤

Migration 009 执行成功后，继续以下步骤：

1. **准备测试数据**
   ```bash
   cd /home/ubuntu/coding/health-qc-monorepo/tests/integration
   
   # 使用 Supabase Dashboard SQL Editor 执行
   cat prepare_test_data.sql
   ```

2. **运行完整的集成测试**
   ```bash
   ./run_all_tests.sh
   ```

3. **更新测试报告**
   - 记录 Migration 执行结果
   - 更新 `TEST_EXECUTION_REPORT.md`
   - 更新 `PHASE_4_INTEGRATION_TEST_REPORT.md`

---

## 🔄 如果需要回滚

如果 Migration 执行出现问题，可以使用回滚脚本：

```bash
cd /home/ubuntu/coding/health-qc-monorepo/infra/supabase/medqc/migrations

# 使用 Supabase Dashboard SQL Editor 执行
cat 009_department_qc_rules_rollback.sql

# 或使用 psql
psql "postgresql://postgres:[YOUR-PASSWORD]@db.dgsdkdbjpucyawnyfbdu.supabase.co:5432/postgres" \
     -f 009_department_qc_rules_rollback.sql
```

---

## 📚 相关文档

- [Migration 009 完成报告](../../infra/supabase/medqc/migrations/MIGRATION_009_COMPLETION_REPORT.md)
- [Migration 009 README](../../infra/supabase/medqc/migrations/README_009.md)
- [快速启动指南](../../docs/DEPARTMENT_RULES_QUICK_START.md)
- [第四阶段集成测试报告](../../docs/PHASE_4_INTEGRATION_TEST_REPORT.md)

---

## 💡 经验教训

1. **前置条件检查**: 在开始集成测试前，应该先验证所有前置条件是否满足。
2. **自动化验证**: 应该在测试脚本开始时自动检查 Migration 是否已执行。
3. **错误信息改进**: PostgREST 的 400 错误信息不够明确，需要更深入的调试才能发现根本原因。

---

**报告生成时间**: 2025-10-13  
**下次更新**: Migration 009 执行后

