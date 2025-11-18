# Supabase 数据库迁移指南

从海外 Supabase 迁移到阿里云 Supabase 的完整指南。

## 📋 目录

- [为什么要迁移](#为什么要迁移)
- [迁移前准备](#迁移前准备)
- [迁移方案对比](#迁移方案对比)
- [推荐方案：使用自动化脚本](#推荐方案使用自动化脚本)
- [手动迁移方案](#手动迁移方案)
- [迁移后配置](#迁移后配置)
- [常见问题](#常见问题)

---

## 为什么要迁移

### 当前问题
- 🐌 **网络延迟高**：海外 Supabase 访问延迟 10-30 秒/请求
- 🌍 **跨境网络不稳定**：经常出现超时和连接失败
- 💰 **成本高**：跨境流量费用较高

### 迁移后收益
- ⚡ **速度提升 10-20 倍**：国内访问延迟降至 100-500ms
- 🎯 **稳定性提升**：避免跨境网络问题
- 💵 **成本降低**：国内流量费用更低

---

## 迁移前准备

### 1. 开通阿里云 Supabase

访问 [阿里云 Supabase](https://www.aliyun.com/product/supabase) 并创建新项目。

### 2. 获取数据库连接信息

#### 海外 Supabase（源数据库）
1. 登录 [Supabase Dashboard](https://app.supabase.com)
2. 选择项目 `dgsdkdbjpucyawnyfbdu`
3. 进入 **Project Settings** → **Database**
4. 复制 **Connection string** (Direct connection)

示例：
```
postgresql://postgres:[YOUR-PASSWORD]@db.dgsdkdbjpucyawnyfbdu.supabase.co:5432/postgres
```

#### 阿里云 Supabase（目标数据库）
1. 登录阿里云 Supabase 控制台
2. 选择新创建的项目
3. 获取数据库连接信息

### 3. 安装 PostgreSQL 客户端工具

```bash
# Ubuntu/Debian
sudo apt-get install postgresql-client

# macOS
brew install postgresql

# CentOS/RHEL
sudo yum install postgresql

# Windows
# 下载并安装 PostgreSQL: https://www.postgresql.org/download/windows/
```

验证安装：
```bash
pg_dump --version
psql --version
```

---

## 迁移方案对比

| 方案 | 难度 | 时间 | 适用场景 | 推荐度 |
|------|------|------|----------|--------|
| **自动化脚本** | ⭐ 简单 | 10分钟 | 所有场景 | ⭐⭐⭐⭐⭐ |
| **手动 pg_dump** | ⭐⭐ 中等 | 15分钟 | 熟悉命令行 | ⭐⭐⭐⭐ |
| **Supabase CLI** | ⭐⭐⭐ 复杂 | 20分钟 | 需要额外工具 | ⭐⭐⭐ |
| **CSV 导入导出** | ⭐⭐⭐⭐ 繁琐 | 1小时+ | 小数据量 | ⭐⭐ |

---

## 推荐方案：使用自动化脚本

### 方案 A：Python 脚本（推荐）

**优点**：
- ✅ 交互式界面，友好易用
- ✅ 自动检查依赖
- ✅ 彩色输出，进度清晰
- ✅ 错误处理完善

**使用步骤**：

```bash
# 1. 进入项目目录
cd health-qc-monorepo

# 2. 运行迁移脚本
python scripts/migrate_supabase.py

# 3. 按照提示输入信息
# - 源数据库信息（海外 Supabase）
# - 目标数据库信息（阿里云 Supabase）

# 4. 确认后自动完成迁移
```

### 方案 B：Bash 脚本

**优点**：
- ✅ 无需 Python 环境
- ✅ 适合 Linux/macOS

**使用步骤**：

```bash
# 1. 添加执行权限
chmod +x scripts/migrate_supabase.sh

# 2. 运行脚本
./scripts/migrate_supabase.sh

# 3. 按照提示输入信息
```

---

## 手动迁移方案

如果你想手动控制每一步，可以使用以下方法：

### 步骤 1：导出海外数据库

```bash
# 设置源数据库连接信息
export SOURCE_DB="postgresql://postgres:[PASSWORD]@db.dgsdkdbjpucyawnyfbdu.supabase.co:5432/postgres"

# 导出数据库
pg_dump "$SOURCE_DB" \
  --no-owner \
  --no-acl \
  --clean \
  --if-exists \
  -f supabase_backup.sql

# 查看备份文件大小
ls -lh supabase_backup.sql
```

**参数说明**：
- `--no-owner`：不导出所有者信息（避免权限问题）
- `--no-acl`：不导出访问控制列表
- `--clean`：在重新创建之前清理数据库对象
- `--if-exists`：使用 IF EXISTS 子句（避免错误）

### 步骤 2：导入到阿里云数据库

```bash
# 设置目标数据库连接信息
export TARGET_DB="postgresql://postgres:[NEW-PASSWORD]@[ALIYUN-HOST]:5432/postgres"

# 导入数据库
psql "$TARGET_DB" -f supabase_backup.sql

# 或者使用管道（更快）
cat supabase_backup.sql | psql "$TARGET_DB"
```

### 步骤 3：验证数据

```bash
# 连接到目标数据库
psql "$TARGET_DB"

# 检查表数量
\dt

# 检查数据量
SELECT 
  schemaname,
  tablename,
  pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) AS size,
  (SELECT COUNT(*) FROM information_schema.columns WHERE table_name = tablename) AS columns
FROM pg_tables
WHERE schemaname = 'public'
ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC;

# 退出
\q
```

---

## 迁移后配置

### 1. 更新环境变量

编辑 `health-qc-monorepo/apps/medqc-web/backend/.env` 文件：

```bash
# 旧配置（海外 Supabase）
# SUPABASE_URL=https://dgsdkdbjpucyawnyfbdu.supabase.co
# SUPABASE_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
# SUPABASE_SERVICE_ROLE_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...

# 新配置（阿里云 Supabase）
SUPABASE_URL=https://[your-aliyun-project].supabase.co
SUPABASE_KEY=[your-new-anon-key]
SUPABASE_SERVICE_ROLE_KEY=[your-new-service-role-key]
```

**获取新的 API Keys**：
1. 登录阿里云 Supabase 控制台
2. 进入 **Project Settings** → **API**
3. 复制 `anon` 和 `service_role` keys

### 2. 重启后端服务

```bash
# 如果后端正在运行，会自动重新加载
# 如果没有运行，手动启动：
cd health-qc-monorepo/apps/medqc-web/backend
source venv/bin/activate
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### 3. 测试应用

1. 访问前端：http://localhost:3000
2. 登录系统
3. 测试以下功能：
   - ✅ 病历列表加载
   - ✅ 病历详情查看
   - ✅ 文书预览
   - ✅ 质控分析

### 4. 性能对比

迁移前后性能对比：

```bash
# 测试 API 响应时间
time curl -X GET "http://localhost:8000/api/v1/records?page=1&page_size=10" \
  -H "Authorization: Bearer YOUR_TOKEN"
```

**预期结果**：
- 迁移前：10-30 秒
- 迁移后：0.5-2 秒

---

## 常见问题

### Q1: 迁移会影响现有数据吗？

**A**: 不会。迁移是将数据**复制**到新数据库，不会删除或修改源数据库。

### Q2: 迁移需要多长时间？

**A**: 取决于数据量：
- 小型数据库（< 100MB）：5-10 分钟
- 中型数据库（100MB - 1GB）：10-30 分钟
- 大型数据库（> 1GB）：30 分钟 - 2 小时

### Q3: 迁移失败怎么办？

**A**: 
1. 检查网络连接
2. 确认数据库密码正确
3. 查看错误日志
4. 重新运行迁移脚本（幂等操作，可以重复执行）

### Q4: 如何回滚到海外数据库？

**A**: 只需将 `.env` 文件中的配置改回原来的值，然后重启服务即可。

### Q5: 迁移后需要修改代码吗？

**A**: 不需要。只需更新环境变量即可，代码无需修改。

### Q6: 阿里云 Supabase 和海外 Supabase 有什么区别？

**A**: 
- ✅ 功能完全相同（都是 PostgreSQL + Supabase 扩展）
- ✅ API 接口兼容
- ⚡ 主要区别是网络延迟和访问速度

### Q7: 迁移后如何保持数据同步？

**A**: 
- **方案 1**：停止使用海外数据库，只使用阿里云数据库
- **方案 2**：使用 PostgreSQL 逻辑复制（复杂，不推荐）
- **推荐**：迁移后完全切换到阿里云，不再使用海外数据库

---

## 技术支持

如果遇到问题，请：

1. 查看迁移脚本的输出日志
2. 检查备份文件是否生成成功
3. 验证数据库连接信息是否正确
4. 联系技术支持

---

## 附录：数据库结构

当前数据库包含以下主要表：

- `medical_records_test` - 病历记录
- `medical_documents_test` - 医疗文书
- `document_categories_test` - 文书分类
- `document_types_test` - 文书类型
- `qc_rules` - 质控规则
- `users` - 用户表

迁移会完整复制所有表结构和数据。

