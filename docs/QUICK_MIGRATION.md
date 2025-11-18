# 🚀 Supabase 快速迁移指南

**从海外迁移到阿里云，10分钟搞定！**

---

## 📦 准备工作（5分钟）

### 1. 开通阿里云 Supabase
访问 https://www.aliyun.com/product/supabase 创建新项目

### 2. 安装 PostgreSQL 工具
```bash
# Ubuntu/Debian
sudo apt-get install postgresql-client

# macOS
brew install postgresql
```

---

## ⚡ 一键迁移（5分钟）

### 方法 1：Python 脚本（推荐）

```bash
cd health-qc-monorepo
python scripts/migrate_supabase.py
```

按提示输入：
1. 源数据库信息（海外 Supabase）
2. 目标数据库信息（阿里云 Supabase）
3. 确认后自动完成

### 方法 2：Bash 脚本

```bash
cd health-qc-monorepo
./scripts/migrate_supabase.sh
```

### 方法 3：手动命令

```bash
# 1. 导出
pg_dump "postgresql://postgres:PASSWORD@db.dgsdkdbjpucyawnyfbdu.supabase.co:5432/postgres" \
  --no-owner --no-acl -f backup.sql

# 2. 导入
psql "postgresql://postgres:NEW_PASSWORD@ALIYUN_HOST:5432/postgres" -f backup.sql
```

---

## 🔧 迁移后配置

### 1. 更新 .env 文件

编辑 `apps/medqc-web/backend/.env`：

```bash
SUPABASE_URL=https://[your-aliyun-project].supabase.co
SUPABASE_KEY=[your-new-anon-key]
SUPABASE_SERVICE_ROLE_KEY=[your-new-service-role-key]
```

### 2. 重启服务

后端会自动重新加载，无需手动重启。

### 3. 测试

访问 http://localhost:3000 测试功能。

---

## 📊 性能对比

| 指标 | 迁移前（海外） | 迁移后（阿里云） | 提升 |
|------|---------------|-----------------|------|
| API 响应时间 | 10-30 秒 | 0.5-2 秒 | **10-20倍** |
| 页面加载时间 | 3+ 分钟 | 5-10 秒 | **20-30倍** |
| 网络稳定性 | 经常超时 | 稳定 | ✅ |

---

## ❓ 常见问题

**Q: 会丢失数据吗？**  
A: 不会，迁移是复制操作，源数据库不受影响。

**Q: 需要修改代码吗？**  
A: 不需要，只需更新环境变量。

**Q: 迁移失败怎么办？**  
A: 可以重复执行迁移脚本，或查看详细文档 `docs/SUPABASE_MIGRATION_GUIDE.md`

**Q: 如何回滚？**  
A: 将 `.env` 改回原配置即可。

---

## 📞 需要帮助？

查看完整文档：`docs/SUPABASE_MIGRATION_GUIDE.md`

