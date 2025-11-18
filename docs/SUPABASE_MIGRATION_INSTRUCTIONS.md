# Supabase 数据库迁移操作说明

## 📋 任务概述

将海外 Supabase 数据库完整迁移到阿里云 Supabase，包括所有表结构、数据、索引和约束。

---

## 🎯 迁移目标

- **源数据库**：海外 Supabase (`dgsdkdbjpucyawnyfbdu.supabase.co`)
- **目标数据库**：阿里云 Supabase (`sbp-a41klzf2d6lvsjoj.supabase.opentrust.net`)
- **数据量**：约 247 条记录（根据 2025-10 快照），分布在 20+ 个业务表中
- **预期性能提升**：响应时间从 10-30 秒降低到 0.5-2 秒（**10-20 倍提升**）

---

## 📊 数据库信息

### 源数据库（海外 Supabase）

```
URL: https://dgsdkdbjpucyawnyfbdu.supabase.co
数据库主机: db.dgsdkdbjpucyawnyfbdu.supabase.co
端口: 5432
用户名: postgres
数据库名: postgres
密码: rK6XqKqU6hB45iMS

Service Role Key:
eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImRnc2RrZGJqcHVjeWF3bnlmYmR1Iiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc1NjA4NjI4NywiZXhwIjoyMDcxNjYyMjg3fQ.DKVfet4m99w-eQayUt-C_mNfJyQhGf3Oobr8L5VMUVQ
```

### 目标数据库（阿里云 Supabase）

```
URL: https://sbp-a41klzf2d6lvsjoj.supabase.opentrust.net
数据库主机: sbp-a41klzf2d6lvsjoj.supabase.opentrust.net
端口: 5432
用户名: postgres
数据库名: postgres
密码: Han1979919

Anon Key:
eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJyb2xlIjoiYW5vbiIsInJlZiI6InNicC1hNDFrbHpmMmQ2bHZzam9qIiwiaXNzIjoic3VwYWJhc2UiLCJpYXQiOjE3NjEwMjUxNTEsImV4cCI6MjA3NjYwMTE1MX0.at6_SWq4JEpPfA5nXdZokycGvXqKqKFgzKdHm-oBdno
```

**⚠️ 重要**：需要获取阿里云 Supabase 的 **Service Role Key**
- 访问：https://sbp-a41klzf2d6lvsjoj.supabase.opentrust.net/project/default/settings/api
- 找到 `service_role` 密钥并复制

---

## 📦 需要迁移的表

| 表名 | 记录数（2025-10 快照） | 说明 |
|------|------------------------|------|
| `user_profiles` | 4 | 前端展示所需的用户信息（与 Supabase Auth 同步） |
| `user_roles` | 0 | 用户角色关联表 |
| `departments` | 14 | 科室基础数据 |
| `qc_rules` | 75 | 质控规则主表 |
| `report_templates` | 0 | 报表模板 |
| `alert_records` | 0 | 告警记录 |
| `analytics_metrics` | 20 | 质控统计指标配置 |
| `data_snapshots` | 0 | 报表快照 |
| `document_categories_test` | 7 | 测试环境文书分类（一级） |
| `document_types_test` | 28 | 测试环境文书类型（二级） |
| `medical_records_test` | 10 | 测试病历（含 JSON 字段） |
| `medical_documents_test` | 45 | 测试病历关联文书 |
| `medical_records` | 1 | 正式病历记录 |
| `medical_documents` | 1 | 正式病历文书 |
| `qc_results` | 0 | 质控执行结果 |
| `qc_analysis_cache` | 0 | 质控缓存结果 |
| `qc_analysis_history` | 0 | 质控历史 |
| `batch_processing_tasks` | 0 | 批处理任务 |
| `llm_api_providers` | 9 | LLM 服务商配置 |
| `llm_models` | 33 | LLM 模型配置 |

> 说明：表记录数为最新快照，仅用于估算迁移规模，实际数量可能因后续使用而变化。

---

## 🚀 迁移方案

### 方案 A：使用 pg_dump（推荐，最快最可靠）

**前提条件**：
- 需要能够直连海外 Supabase 数据库（端口 5432）
- 已安装 PostgreSQL 客户端工具（`pg_dump`, `psql`）

**问题**：
- 当前环境无法直连海外数据库（IPv6 网络不可达）
- 错误信息：`connection to server at "db.dgsdkdbjpucyawnyfbdu.supabase.co" (2406:da18:243:7421:6e7d:cc58:b538:81fb), port 5432 failed: Network is unreachable`

**解决方案**：
1. 使用支持 IPv6 的网络环境
2. 或使用 IPv4 强制连接（需要配置）
3. 或将导出命令放在云服务器等可直连环境中执行

**操作步骤**：
1. 编辑 `scripts/full_pg_dump_restore.sh`，填写源库/目标库连接信息（已预置项目默认值）。
2. 在具备连通性的环境中执行：
   ```bash
   cd health-qc-monorepo
   bash scripts/full_pg_dump_restore.sh
   ```
3. 观察脚本输出，确认 `pg_dump` 导出成功并在目标库恢复结束。
4. 恢复完成后，执行 “验证迁移结果” 中的 SQL/脚本进行核对。

> 提醒：脚本默认会 TRUNCATE 目标库 `public` schema，如需保留数据请先修改 `TRUNCATE_PUBLIC` 参数。

---

### 方案 B：使用 REST API（当前推荐）

**优点**：
- 不需要直连数据库
- 通过 HTTPS 访问，网络兼容性好
- 已有现成脚本

**缺点**：
- 速度较慢（需要多次 HTTP 请求）
- 需要处理 RLS（Row Level Security）权限问题

**步骤**：

#### 步骤 1：获取阿里云 Supabase Service Role Key

1. 访问阿里云 Supabase 控制台：
   ```
   https://sbp-a41klzf2d6lvsjoj.supabase.opentrust.net/project/default/settings/api
   ```

2. 在 **Project API keys** 部分找到 `service_role` 密钥

3. 点击 "Reveal" 或眼睛图标显示密钥

4. 复制完整的密钥（通常以 `eyJ` 开头）

#### 步骤 2：禁用目标数据库的 RLS

在阿里云 Supabase SQL Editor 中执行以下 SQL，批量关闭 `public` 下所有表的 RLS 并授予访问权限：

```sql
DO $$
DECLARE
    rec record;
BEGIN
    FOR rec IN (
        SELECT tablename
        FROM pg_tables
        WHERE schemaname = 'public'
    ) LOOP
        EXECUTE format('ALTER TABLE public.%I DISABLE ROW LEVEL SECURITY;', rec.tablename);
    END LOOP;
END $$;

GRANT ALL ON ALL TABLES IN SCHEMA public TO anon;
GRANT ALL ON ALL TABLES IN SCHEMA public TO authenticated;
GRANT ALL ON ALL TABLES IN SCHEMA public TO service_role;
GRANT ALL ON ALL SEQUENCES IN SCHEMA public TO service_role;
```

命令行版本：

```bash
PGPASSWORD='Han1979919' psql \
  -h sbp-a41klzf2d6lvsjoj.supabase.opentrust.net \
  -p 5432 \
  -U postgres \
  -d postgres <<'SQL'
DO $$
DECLARE
    rec record;
BEGIN
    FOR rec IN (
        SELECT tablename
        FROM pg_tables
        WHERE schemaname = 'public'
    ) LOOP
        EXECUTE format('ALTER TABLE public.%I DISABLE ROW LEVEL SECURITY;', rec.tablename);
    END LOOP;
END $$;
GRANT ALL ON ALL TABLES IN SCHEMA public TO anon;
GRANT ALL ON ALL TABLES IN SCHEMA public TO authenticated;
GRANT ALL ON ALL TABLES IN SCHEMA public TO service_role;
GRANT ALL ON ALL SEQUENCES IN SCHEMA public TO service_role;
SQL
```

#### 步骤 3：运行 REST API 迁移脚本

`api_migration_with_progress.py` 已默认内置 20+ 个业务表，并按依赖顺序迁移。执行方式：

```bash
cd health-qc-monorepo
python3 api_migration_with_progress.py
```

脚本会自动检测源库可访问的表，跳过未开放 REST API 的表。提示输入 Service Role Key 时，粘贴步骤 1 中获取的密钥。

如需新增自定义表，可编辑脚本顶部的 `TABLE_ORDER` 常量并再次运行。

#### 步骤 4：验证迁移结果

检查目标数据库中的数据，可选方式如下：

1. 使用脚本：
   ```bash
   python3 check_aliyun_data.py
   ```
   该脚本会依次检查 20+ 张表的记录数，并展示关键字段示例。

2. 或在 `psql` 中执行统计 SQL：
   ```sql
   SELECT 'user_profiles' AS table, COUNT(*) FROM user_profiles
   UNION ALL SELECT 'user_roles', COUNT(*) FROM user_roles
   UNION ALL SELECT 'departments', COUNT(*) FROM departments
   UNION ALL SELECT 'qc_rules', COUNT(*) FROM qc_rules
   UNION ALL SELECT 'report_templates', COUNT(*) FROM report_templates
   UNION ALL SELECT 'alert_records', COUNT(*) FROM alert_records
   UNION ALL SELECT 'analytics_metrics', COUNT(*) FROM analytics_metrics
   UNION ALL SELECT 'data_snapshots', COUNT(*) FROM data_snapshots
   UNION ALL SELECT 'document_categories_test', COUNT(*) FROM document_categories_test
   UNION ALL SELECT 'document_types_test', COUNT(*) FROM document_types_test
   UNION ALL SELECT 'medical_records_test', COUNT(*) FROM medical_records_test
   UNION ALL SELECT 'medical_documents_test', COUNT(*) FROM medical_documents_test
   UNION ALL SELECT 'medical_records', COUNT(*) FROM medical_records
   UNION ALL SELECT 'medical_documents', COUNT(*) FROM medical_documents
   UNION ALL SELECT 'qc_results', COUNT(*) FROM qc_results
   UNION ALL SELECT 'qc_analysis_cache', COUNT(*) FROM qc_analysis_cache
   UNION ALL SELECT 'qc_analysis_history', COUNT(*) FROM qc_analysis_history
   UNION ALL SELECT 'batch_processing_tasks', COUNT(*) FROM batch_processing_tasks
   UNION ALL SELECT 'llm_api_providers', COUNT(*) FROM llm_api_providers
   UNION ALL SELECT 'llm_models', COUNT(*) FROM llm_models;
   ```

若需要与源库对比，可在源库运行相同 SQL，并核对结果是否一致。

#### 步骤 5：更新应用配置

前端和后端的环境变量已经更新，无需手动修改。

**前端配置** (`apps/medqc-web/.env`):
```bash
VITE_SUPABASE_URL=https://sbp-a41klzf2d6lvsjoj.supabase.opentrust.net
VITE_SUPABASE_ANON_KEY=eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJyb2xlIjoiYW5vbiIsInJlZiI6InNicC1hNDFrbHpmMmQ2bHZzam9qIiwiaXNzIjoic3VwYWJhc2UiLCJpYXQiOjE3NjEwMjUxNTEsImV4cCI6MjA3NjYwMTE1MX0.at6_SWq4JEpPfA5nXdZokycGvXqKqKFgzKdHm-oBdno
```

**后端配置** (`apps/medqc-web/backend/.env`):
```bash
SUPABASE_URL=https://sbp-a41klzf2d6lvsjoj.supabase.opentrust.net
SUPABASE_ANON_KEY=eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJyb2xlIjoiYW5vbiIsInJlZiI6InNicC1hNDFrbHpmMmQ2bHZzam9qIiwiaXNzIjoic3VwYWJhc2UiLCJpYXQiOjE3NjEwMjUxNTEsImV4cCI6MjA3NjYwMTE1MX0.at6_SWq4JEpPfA5nXdZokycGvXqKqKFgzKdHm-oBdno
```

#### 步骤 6：重启服务并测试

后端会自动重新加载，前端需要刷新浏览器：

```bash
# 刷新浏览器页面
# 访问 http://localhost:3000
# 测试病历列表加载
# 测试病历详情查看
# 测试质控分析功能
```

---

## 🔧 可用的迁移脚本

项目中已准备好以下脚本：

| 脚本文件 | 说明 | 使用场景 |
|---------|------|---------|
| `api_migration_with_progress.py` | REST API 迁移（带进度显示） | **推荐使用** |
| `reliable_migration.sh` | pg_dump 迁移 | 需要直连数据库 |
| `check_source_data.py` | 检查源数据库数据 | 验证源数据 |
| `check_aliyun_data.py` | 检查目标数据库数据 | 验证迁移结果 |
| `test_insert.py` | 测试单条记录插入 | 调试权限问题 |

---

## ⚠️ 已知问题和解决方案

### 问题 1：无法直连海外数据库

**错误信息**：
```
connection to server at "db.dgsdkdbjpucyawnyfbdu.supabase.co" failed: Network is unreachable
```

**原因**：服务器返回 IPv6 地址，但当前网络不支持 IPv6

**解决方案**：
- 使用方案 B（REST API 方式）
- 或在支持 IPv6 的网络环境中执行迁移

### 问题 2：REST API 插入失败

**错误信息**：
```
📤 插入数据 |████████████████████████████████████████| 100.0% (成功:0 失败:10)
❌ 插入失败
```

**原因**：RLS（Row Level Security）阻止了 ANON_KEY 的写入权限

**解决方案**：
1. 禁用 RLS（见步骤 2）
2. 使用 Service Role Key 而不是 Anon Key
3. 授予 anon 角色写入权限

### 问题 3：缺少 Service Role Key

**解决方案**：
1. 访问阿里云 Supabase 控制台
2. 进入 Project Settings → API
3. 复制 `service_role` 密钥

---

## ✅ 验证清单

迁移完成后，请验证以下内容：

- [ ] 所有 5 个表都已创建
- [ ] 所有 165 条记录都已迁移
- [ ] 前端可以正常加载病历列表
- [ ] 前端可以正常查看病历详情
- [ ] 文档预览功能正常
- [ ] 质控分析功能正常
- [ ] API 响应时间显著降低（从 10-30 秒降到 0.5-2 秒）

---

## 📞 需要帮助？

如果遇到问题，请检查：

1. **网络连接**：确保可以访问阿里云 Supabase
2. **权限配置**：确保 RLS 已禁用，权限已授予
3. **Service Role Key**：确保使用正确的密钥
4. **日志输出**：查看脚本的详细错误信息

---

## 📝 迁移后清理

迁移成功后，可以选择性删除以下临时文件：

```bash
rm -f health-qc-monorepo/test_aliyun_supabase.py
rm -f health-qc-monorepo/test_db_connection.sh
rm -f health-qc-monorepo/migrate_now.sh
rm -f health-qc-monorepo/migrate_via_api.py
rm -f health-qc-monorepo/check_source_data.py
rm -f health-qc-monorepo/test_insert.py
rm -rf health-qc-monorepo/backups/
```

**保留以下文件**（用于未来参考）：
- `docs/SUPABASE_MIGRATION_GUIDE.md`
- `docs/QUICK_MIGRATION.md`
- `docs/SUPABASE_MIGRATION_INSTRUCTIONS.md`（本文档）
- `scripts/migrate_supabase.py`
- `scripts/migrate_supabase.sh`

---

## 🎉 预期结果

迁移成功后，你将获得：

✅ **性能提升 10-20 倍**
- API 响应时间：10-30 秒 → 0.5-2 秒
- 页面加载时间：3+ 分钟 → 5-10 秒

✅ **稳定性提升**
- 不再有网络超时问题
- 国内访问速度快且稳定

✅ **用户体验改善**
- 页面响应迅速
- 操作流畅无卡顿

---

**祝迁移顺利！** 🚀
