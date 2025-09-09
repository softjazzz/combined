# Yibao Edge Functions 部署指南

## 概述

Yibao 项目包含 3 个 Edge Functions，用于处理规则引擎、违规记录和统计数据：

1. **evaluate-rule** - 规则引擎执行器
2. **violations** - 违规记录管理
3. **statistics** - 统计数据聚合

## 部署步骤

### 1. 安装 Supabase CLI

```bash
# 方法1: 使用 npm (需要 Node.js)
npm install -g supabase

# 方法2: 使用官方安装脚本
curl -fsSL https://supabase.com/install.sh | sh

# 方法3: 手动下载 (Linux)
wget https://github.com/supabase/cli/releases/latest/download/supabase_linux_amd64.tar.gz
tar -xzf supabase_linux_amd64.tar.gz
sudo mv supabase /usr/local/bin/
```

### 2. 登录 Supabase

```bash
supabase login
```

### 3. 链接到项目

```bash
cd /home/ubuntu/health-qc-monorepo/Yibao
supabase link --project-ref apkvovxrsjzwmeuuzgnc
```

### 4. 部署 Edge Functions

```bash
# 部署所有函数
supabase functions deploy

# 或者单独部署
supabase functions deploy evaluate-rule
supabase functions deploy violations  
supabase functions deploy statistics
```

### 5. 设置环境变量

在 Supabase Dashboard > Edge Functions > Settings 中设置：

```
SUPABASE_URL=https://apkvovxrsjzwmeuuzgnc.supabase.co
SUPABASE_SERVICE_ROLE_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImFwa3Zvdnhyc2p6d21ldXV6Z25jIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc1NjQ1NjYxOSwiZXhwIjoyMDcyMDMyNjE5fQ.-ISIwI6qLtFIQ5PEqwep_9y-aucnNFDLhBnaoyU54WU
```

## 函数端点

部署后，函数将在以下端点可用：

- **evaluate-rule**: `https://apkvovxrsjzwmeuuzgnc.supabase.co/functions/v1/evaluate-rule`
- **violations**: `https://apkvovxrsjzwmeuuzgnc.supabase.co/functions/v1/violations`
- **statistics**: `https://apkvovxrsjzwmeuuzgnc.supabase.co/functions/v1/statistics`

## 测试函数

### 测试规则引擎

```bash
curl -X POST https://apkvovxrsjzwmeuuzgnc.supabase.co/functions/v1/evaluate-rule \
  -H "Authorization: Bearer YOUR_ANON_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "event": "drug_order",
    "context": {
      "patient": {"age": 30, "gender": "F"},
      "visit": {"type": "OUTPATIENT"},
      "order": {"drug_code": "DEMO_DRUG_INPATIENT"}
    },
    "record": true
  }'
```

### 测试违规查询

```bash
curl "https://apkvovxrsjzwmeuuzgnc.supabase.co/functions/v1/violations?page=1&limit=10" \
  -H "Authorization: Bearer YOUR_ANON_KEY"
```

### 测试统计数据

```bash
curl "https://apkvovxrsjzwmeuuzgnc.supabase.co/functions/v1/statistics/dashboard" \
  -H "Authorization: Bearer YOUR_ANON_KEY"
```

## CORS 配置

在 Supabase Dashboard > Settings > API > CORS Origins 中添加：

```
http://localhost:3001
http://localhost:3008
```

## 故障排除

1. **部署失败**: 检查 Supabase CLI 版本和项目权限
2. **函数错误**: 查看 Supabase Dashboard > Edge Functions > Logs
3. **CORS 错误**: 确保已正确配置 CORS Origins
4. **认证错误**: 检查 anon key 和 service role key 配置

## 本地开发

```bash
# 启动本地 Edge Functions 服务器
supabase functions serve

# 在另一个终端测试
curl -X POST http://localhost:54321/functions/v1/evaluate-rule \
  -H "Content-Type: application/json" \
  -d '{"event": "drug_order", "context": {...}}'
```
