# 🚀 新 Supabase 项目部署指南

## 📋 项目信息

**新 Supabase 项目配置：**
- **Project URL**: `https://dgsdkdbjpucyawnyfbdu.supabase.co`
- **Anon Key**: `eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImRnc2RrZGJqcHVjeWF3bnlmYmR1Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3NTYwODYyODcsImV4cCI6MjA3MTY2MjI4N30.k3178KRejQEoOogYjQ7EI_NfEW8ztVxFes3zLJ51JFw`

---

## 🔧 第一步：环境配置更新

### ✅ 已完成的配置更新

1. **前端环境变量** (`.env`)
   ```bash
   VITE_SUPABASE_URL=https://dgsdkdbjpucyawnyfbdu.supabase.co
   VITE_SUPABASE_ANON_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImRnc2RrZGJqcHVjeWF3bnlmYmR1Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3NTYwODYyODcsImV4cCI6MjA3MTY2MjI4N30.k3178KRejQEoOogYjQ7EI_NfEW8ztVxFes3zLJ51JFw
   ```

2. **前端 Supabase 客户端** (`src/lib/supabase.ts`)
   - 已更新硬编码的 URL 和 API Key

3. **后端环境变量** (`production_system/.env`)
   - 已创建新的环境配置文件
   - 已添加 Supabase Python 客户端依赖

---

## 🗄️ 第二步：数据库初始化

### 📁 数据库脚本文件

已创建以下 SQL 脚本文件：

1. **`database_init_complete.sql`** - 主要表结构
   - PostgreSQL 扩展启用
   - 用户管理表（user_profiles, departments）
   - 业务核心表（medical_records, qc_rules, qc_results）
   - 任务处理表（batch_processing_tasks, qc_analysis_history, alert_records）

2. **`database_init_part2.sql`** - 统计分析和优化
   - 统计分析表（analytics_metrics, report_templates, data_snapshots）
   - 性能索引创建
   - 统计分析视图

3. **`database_init_part3.sql`** - 安全和初始数据
   - RLS（行级安全）策略
   - 函数和触发器
   - 初始化数据（科室、分析指标）

4. **`database_init_qc_rules.sql`** - 质控规则
   - 基础质控规则数据
   - 需要在用户档案创建后执行

5. **`verify_database.sql`** - 验证脚本
   - 全面的数据库验证检查

### 🚀 执行步骤

**在 Supabase SQL Editor 中按顺序执行：**

```bash
# 1. 主要表结构
执行 database_init_complete.sql

# 2. 统计分析和索引
执行 database_init_part2.sql

# 3. 如果遇到中文搜索配置错误，执行修复脚本
执行 database_fix_chinese_search.sql

# 4. 安全策略和初始数据
执行 database_init_part3.sql

# 5. 如果遇到分析指标约束错误，执行修复脚本
执行 database_fix_analytics_constraints.sql

# 6. 验证数据库设置
执行 verify_database.sql

# 7. 创建用户账户后，执行质控规则初始化
执行 database_init_qc_rules.sql
```

---

## 🔍 第三步：验证和测试

### 📊 数据库验证

运行验证脚本检查：
- ✅ 12+ 张表创建成功
- ✅ 3+ 个视图创建成功  
- ✅ 20+ 个索引创建成功
- ✅ 8+ 个 RLS 策略启用
- ✅ 7+ 个科室初始数据
- ✅ 5+ 个分析指标数据

### 🧪 连接测试

运行前端连接测试：
```bash
# 在项目根目录执行
node test_new_supabase_connection.js
```

预期输出：
```
🚀 测试新 Supabase 项目连接...
✅ 基本连接成功
✅ 表 departments 存在
✅ 表 user_profiles 存在
✅ 科室数据: 7 条记录
✅ 分析指标数据: 5 条记录
🎉 连接测试完成!
```

---

## 📦 第四步：依赖更新

### 前端依赖

前端依赖已经是最新的，包含：
- `@supabase/supabase-js@^2.48.0`
- 其他必要的 Vue 3 生态依赖

### 后端依赖

已更新 `production_system/requirements.txt`：
```bash
# 新增 Supabase 支持
supabase==2.3.4
postgrest==0.13.2

# 安装依赖
cd production_system
pip install -r requirements.txt
```

---

## 🎯 第五步：应用启动（仅开发验证）

> 生产部署请按 `P2_RELEASE_RUNBOOK.md` 和 `scripts/deploy_medqc_release.sh` 执行。

### 前端启动

```bash
# 安装依赖
pnpm install

# 启动开发服务器（仅开发使用）
pnpm dev  # 仅开发使用

# 访问 http://localhost:5173
```

### 后端启动

```bash
cd production_system

# 安装 Python 依赖
pip install -r requirements.txt

# 启动后端服务
python main.py

# 访问 http://localhost:8001
```

---

## 🔐 第六步：用户管理设置

### 创建管理员账户

1. **在 Supabase Dashboard 中：**
   - 进入 Authentication > Users
   - 点击 "Add user"
   - 创建管理员账户

2. **在应用中创建用户档案：**
   ```sql
   INSERT INTO user_profiles (
       user_id, username, full_name, email, role_type, department_id
   ) VALUES (
       'auth-user-uuid', -- 替换为实际的 auth.users ID
       'admin',
       '系统管理员', 
       'admin@medqc.com',
       'admin',
       (SELECT id FROM departments WHERE code = 'INTERNAL' LIMIT 1)
   );
   ```

3. **执行质控规则初始化：**
   ```bash
   # 在 SQL Editor 中执行
   database_init_qc_rules.sql
   ```

---

## ✅ 验证清单

### 数据库验证
- [ ] 所有表创建成功
- [ ] 索引创建完成
- [ ] 视图可以查询
- [ ] RLS 策略启用
- [ ] 初始数据加载

### 应用验证
- [ ] 前端可以连接数据库
- [ ] 后端可以连接数据库
- [ ] 用户认证功能正常
- [ ] 基本 CRUD 操作正常
- [ ] 质控分析功能可用

### 功能验证
- [ ] 医疗记录上传
- [ ] 质控规则配置
- [ ] 质控分析执行
- [ ] 报告生成功能
- [ ] 用户权限控制

---

## 🚨 故障排除

### 常见问题

1. **中文全文搜索配置错误** ⚠️
   ```
   ERROR: text search configuration "chinese" does not exist
   ```
   **解决方案：**
   - 执行 `database_fix_chinese_search.sql` 修复脚本
   - 该脚本会自动检测并创建兼容的搜索配置
   - 使用 pg_trgm 扩展提供更好的中文搜索支持

2. **分析指标约束错误** ⚠️
   ```
   ERROR: new row for relation "analytics_metrics" violates check constraint "analytics_metrics_category_check"
   ```
   **解决方案：**
   - 执行 `database_fix_analytics_constraints.sql` 修复脚本
   - 该脚本会更新约束条件，支持更多的指标类别
   - 重新插入正确的分析指标数据

2. **连接失败**
   - 检查 URL 和 API Key 是否正确
   - 确认网络连接正常
   - 验证 Supabase 项目状态

3. **表不存在**
   - 确认 SQL 脚本执行成功
   - 检查 SQL Editor 中的错误信息
   - 验证表创建权限

4. **RLS 策略问题**
   - 检查用户认证状态
   - 验证策略配置正确
   - 确认用户角色权限

5. **数据插入失败**
   - 检查外键约束
   - 验证数据格式正确
   - 确认必填字段完整

6. **索引创建失败**
   - 检查扩展是否正确启用
   - 确认表数据类型匹配
   - 验证索引语法正确

### 联系支持

如遇到问题，请提供：
- 错误信息截图
- 浏览器控制台日志
- 数据库执行日志
- 具体操作步骤

---

## 🎉 部署完成

恭喜！新的 Supabase 项目已成功配置。现在你可以：

1. **开始开发** - 使用全新的数据库架构
2. **测试功能** - 验证所有核心功能
3. **添加数据** - 导入真实的医疗记录
4. **配置规则** - 设置质控规则参数
5. **生成报告** - 使用统计分析功能

系统现在已经准备好进入生产部署流程！🚀
