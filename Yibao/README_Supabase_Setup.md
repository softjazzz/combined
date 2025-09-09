# Yibao 项目 Supabase 配置说明

## 概述

本文档说明如何为智慧医保临床实时质控系统配置 Supabase 环境。

## 1. Supabase 项目创建

### 1.1 创建新项目
1. 访问 [Supabase Dashboard](https://supabase.com/dashboard)
2. 点击 "New Project"
3. 填写项目信息：
   - **Name**: `yibao-qc-system`
   - **Database Password**: 设置强密码
   - **Region**: 选择最近的区域（如 `ap-southeast-1`）

### 1.2 获取项目配置
项目创建完成后，在 Settings > API 页面获取：
- **Project URL**: `https://your-project-id.supabase.co`
- **Anon Key**: `eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...`
- **Service Role Key**: `eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...` (保密)

## 2. 环境变量配置

### 2.1 创建环境变量文件
在 `apps/yibao-web/` 目录下创建 `.env` 文件：

```bash
# Supabase 配置
VITE_SUPABASE_URL=https://apkvovxrsjzwmeuuzgnc.supabase.co
VITE_SUPABASE_ANON_KEY=请填入该项目的 anon key

# 应用配置
VITE_APP_NAME=智慧医保临床实时质控系统
VITE_APP_VERSION=1.0.0
```

### 2.2 服务端配置（用于 Edge Functions）
创建 `supabase/.env` 文件：

```bash
SUPABASE_URL=https://apkvovxrsjzwmeuuzgnc.supabase.co
SUPABASE_SERVICE_ROLE_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImFwa3Zvdnhyc2p6d21ldXV6Z25jIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc1NjQ1NjYxOSwiZXhwIjoyMDcyMDMyNjE5fQ.-ISIwI6qLtFIQ5PEqwep_9y-aucnNFDLhBnaoyU54WU
DATABASE_URL=postgresql://postgres:[password]@db.apkvovxrsjzwmeuuzgnc.supabase.co:5432/postgres
```

## 3. 数据库迁移

### 3.1 执行迁移文件
在 Supabase Dashboard > SQL Editor 中依次执行：

1. **001_reset_and_create_unified_rules.sql** - 创建表结构
2. **002_seed_minimal_rules.sql** - 插入种子数据  
3. **003_setup_rls_policies.sql** - 配置 RLS 策略

### 3.2 验证迁移结果
执行以下 SQL 验证表是否创建成功：

```sql
-- 检查表是否存在
SELECT table_name FROM information_schema.tables 
WHERE table_schema = 'public' AND table_name LIKE 'yibao_%';

-- 检查种子数据
SELECT COUNT(*) as rule_count FROM yibao_rules;
SELECT COUNT(*) as category_count FROM yibao_rule_categories;
```

## 4. 认证配置

### 4.1 启用认证提供商
在 Authentication > Providers 中启用：
- **Email** (默认启用)
- 可选：**Google**, **GitHub** 等第三方登录

### 4.2 配置用户角色
在 Authentication > Users 中为测试用户添加 metadata：

```json
{
  "role": "admin",
  "department": "医保办",
  "display_name": "张三"
}
```

## 5. Edge Functions 准备

### 5.1 创建 Edge Functions 目录
```bash
mkdir -p supabase/functions
```

### 5.2 规划 Functions
按照开发计划，需要创建以下 Edge Functions：
- `rule-engine` - 规则引擎执行器
- `violations` - 违规记录处理
- `statistics` - 统计数据聚合
- `audit` - 审计任务处理

## 6. 本地开发配置

### 6.1 安装依赖
```bash
cd apps/yibao-web
npm install @supabase/supabase-js
```

### 6.2 启动开发服务器
```bash
npm run dev
```

### 6.3 验证连接
访问 `http://localhost:3008`，检查浏览器控制台是否有 Supabase 连接相关的警告或错误。

## 7. 安全注意事项

### 7.1 环境变量安全
- ✅ **VITE_SUPABASE_URL** 和 **VITE_SUPABASE_ANON_KEY** 可以暴露在前端
- ❌ **SUPABASE_SERVICE_ROLE_KEY** 绝不能暴露在前端，仅用于服务端

### 7.2 RLS 策略
- 所有表已启用 Row Level Security
- 前端用户只能读取数据
- 写操作必须通过 Edge Functions 进行

### 7.3 数据访问控制
- `authenticated` 角色：只读权限
- `service_role` 角色：完全权限（仅 Edge Functions 使用）
- `anon` 角色：无权限

## 8. 故障排除

### 8.1 常见问题
1. **连接失败**: 检查 URL 和 Key 是否正确
2. **RLS 阻止访问**: 确认用户已登录且策略配置正确
3. **CORS 错误**: 在 Supabase Dashboard > Settings > API 中配置允许的域名

### 8.2 调试工具
- Supabase Dashboard > Logs
- 浏览器开发者工具 Network 面板
- `supabaseConfig` 对象（在浏览器控制台中查看）

## 9. 下一步

完成 Supabase 配置后，继续执行开发计划清单中的下一项任务：
- ✅ 初始化 Supabase 项目与本地环境变量
- ⏭️ 编写并执行数据库迁移（V1.1 schema）
