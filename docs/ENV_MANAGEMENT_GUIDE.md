# 环境变量管理指南

## 📋 概述

本文档说明如何在 Health-QC-Monorepo 项目中管理环境变量。

## 📁 文件结构

```
health-qc-monorepo/
├── apps/
│   ├── medqc-web/
│   │   ├── .env                    # 前端环境变量（不提交）
│   │   ├── .env.example            # 前端环境变量示例（提交）
│   │   ├── .env.development        # 开发环境配置
│   │   ├── .env.production         # 生产环境配置
│   │   └── backend/
│   │       ├── .env                # 后端环境变量（不提交）
│   │       └── .env.example        # 后端环境变量示例（提交）
│   └── yibao-web/
│       ├── .env                    # 前端环境变量（不提交）
│       └── .env.example            # 前端环境变量示例（提交）
```

## 🚀 快速开始

### 1. MedQC 项目配置

#### 前端配置

```bash
cd apps/medqc-web

# 复制示例文件
cp .env.example .env

# 编辑 .env 文件，填入实际配置
vim .env
```

**必填变量**:
- `VITE_SUPABASE_URL` - Supabase 项目 URL
- `VITE_SUPABASE_ANON_KEY` - Supabase 匿名密钥
- `VITE_API_BASE_URL` - 后端 API 地址
- `VITE_DEEPSEEK_API_KEY` - DeepSeek API 密钥

#### 后端配置

```bash
cd apps/medqc-web/backend

# 复制示例文件
cp .env.example .env

# 编辑 .env 文件，填入实际配置
vim .env
```

**必填变量**:
- `JWT_SECRET` - JWT 密钥（强随机字符串）
- `SUPABASE_URL` - Supabase 项目 URL
- `SUPABASE_ANON_KEY` - Supabase 匿名密钥
- `CORS_ORIGINS` - 允许的跨域来源

### 2. Yibao 项目配置

```bash
cd apps/yibao-web

# 复制示例文件
cp .env.example .env

# 编辑 .env 文件，填入实际配置
vim .env
```

**必填变量**:
- `JWT_SECRET` - JWT 密钥
- `VITE_SUPABASE_URL` - Supabase 项目 URL
- `VITE_SUPABASE_ANON_KEY` - Supabase 匿名密钥
- `VITE_API_BASE_URL` - 后端 API 地址

## 🔐 安全最佳实践

### 1. 密钥生成

**生成强随机 JWT 密钥**:
```bash
# 方法 1: 使用 openssl（推荐）
openssl rand -hex 32

# 方法 2: 使用 Python
python3 -c "import secrets; print(secrets.token_hex(32))"

# 方法 3: 使用 Node.js
node -e "console.log(require('crypto').randomBytes(32).toString('hex'))"
```

### 2. 环境变量安全规范

✅ **应该做的**:
- 始终将 `.env` 文件添加到 `.gitignore`
- 使用 `.env.example` 作为模板，不包含真实密钥
- 在生产环境使用强随机密钥
- 定期轮换密钥
- 使用环境变量管理工具（如 Vault、AWS Secrets Manager）

❌ **不应该做的**:
- ❌ 不要将 `.env` 文件提交到版本控制
- ❌ 不要在代码中硬编码密钥
- ❌ 不要在日志中打印敏感信息
- ❌ 不要在前端代码中使用 Service Role Key
- ❌ 不要在示例文件中使用真实密钥

### 3. 密钥权限层级

| 密钥类型 | 使用位置 | 权限级别 | 说明 |
|---------|---------|---------|------|
| `ANON_KEY` | 前端 + 后端 | 低 | 公开密钥，受 RLS 保护 |
| `SERVICE_ROLE_KEY` | 仅后端 | 高 | 绕过 RLS，仅服务端使用 |
| `JWT_SECRET` | 仅后端 | 高 | 用于签名和验证 JWT |

## 📝 环境变量说明

### MedQC Web 前端

| 变量名 | 必填 | 默认值 | 说明 |
|--------|------|--------|------|
| `VITE_SUPABASE_URL` | ✅ | - | Supabase 项目 URL |
| `VITE_SUPABASE_ANON_KEY` | ✅ | - | Supabase 匿名密钥 |
| `VITE_API_BASE_URL` | ✅ | `http://localhost:8001` | 后端 API 基础地址 |
| `VITE_API_VERSION` | ❌ | `v1` | API 版本号 |
| `VITE_WS_BASE_URL` | ❌ | `ws://localhost:8001` | WebSocket 地址 |
| `VITE_DEEPSEEK_API_KEY` | ✅ | - | DeepSeek API 密钥 |
| `VITE_DEEPSEEK_API_URL` | ✅ | - | DeepSeek API 地址 |
| `VITE_DEEPSEEK_MODEL` | ❌ | `deepseek-v3` | DeepSeek 模型名称 |
| `VITE_APP_NAME` | ❌ | `病案质控系统` | 应用名称 |
| `VITE_ENV` | ❌ | `development` | 运行环境 |
| `DATABASE_URL` | ❌ | - | 数据库连接串（仅迁移脚本） |

### MedQC Web 后端

| 变量名 | 必填 | 默认值 | 说明 |
|--------|------|--------|------|
| `JWT_SECRET` | ✅ | - | JWT 签名密钥 |
| `JWT_ALGORITHM` | ❌ | `HS256` | JWT 算法 |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | ❌ | `30` | Token 过期时间（分钟） |
| `CORS_ORIGINS` | ✅ | - | 允许的跨域来源 |
| `CORS_ALLOW_CREDENTIALS` | ❌ | `true` | 是否允许携带凭证 |
| `CORS_ALLOW_METHODS` | ❌ | `["*"]` | 允许的 HTTP 方法 |
| `CORS_ALLOW_HEADERS` | ❌ | `["*"]` | 允许的 HTTP 头 |
| `SUPABASE_URL` | ✅ | - | Supabase 项目 URL |
| `SUPABASE_ANON_KEY` | ✅ | - | Supabase 匿名密钥 |
| `SUPABASE_SERVICE_ROLE_KEY` | ❌ | - | Supabase Service Role 密钥 |
| `RECORDS_TABLE` | ❌ | `medical_records_test` | 病历记录表名 |
| `DOCUMENTS_TABLE` | ❌ | `medical_documents_test` | 医疗文档表名 |
| `ENV` | ❌ | `development` | 运行环境 |
| `API_PORT` | ❌ | `8001` | API 服务器端口 |
| `HOST` | ❌ | `0.0.0.0` | API 服务器主机 |
| `DEBUG` | ❌ | `true` | 调试模式 |
| `SICHUAN_API_ENDPOINT` | ❌ | - | 四川质控 API 端点 |
| `SICHUAN_API_KEY` | ❌ | - | 四川质控 API 密钥 |
| `SICHUAN_MODEL` | ❌ | `qwen2.5-14b-instruct` | 四川质控模型 |
| `SICHUAN_TIMEOUT_SECONDS` | ❌ | `120` | 四川质控超时时间 |
| `OUTBOUND_ALLOWLIST` | ❌ | `dashscope.aliyuncs.com` | 外部请求白名单 |

### Yibao Web

| 变量名 | 必填 | 默认值 | 说明 |
|--------|------|--------|------|
| `VITE_API_BASE_URL` | ✅ | `http://localhost:8002` | 后端 API 地址 |
| `YIBAO_API_PORT` | ❌ | `8002` | API 服务器端口 |
| `JWT_SECRET` | ✅ | - | JWT 签名密钥 |
| `VITE_SUPABASE_URL` | ✅ | - | Supabase 项目 URL |
| `VITE_SUPABASE_ANON_KEY` | ✅ | - | Supabase 匿名密钥 |
| `SUPABASE_SERVICE_ROLE_KEY` | ❌ | - | Supabase Service Role 密钥 |
| `NODE_ENV` | ❌ | `development` | Node.js 环境 |
| `DEBUG` | ❌ | `true` | 调试模式 |

## 🌍 多环境配置

### 开发环境

```bash
# 使用默认的 .env 文件
npm run dev
```

### 生产环境

```bash
# 使用 .env.production 文件
npm run build
npm run preview
```

### 测试环境

```bash
# 使用 .env.test 文件
npm run test
```

## 🔍 故障排查

### 1. 环境变量未生效

**症状**: 应用无法连接到 Supabase 或后端 API

**解决方案**:
1. 确认 `.env` 文件存在且格式正确
2. 检查变量名是否拼写正确（前端必须以 `VITE_` 开头）
3. 重启开发服务器（Vite 需要重启才能读取新的环境变量）
4. 检查 `.env` 文件编码为 UTF-8

### 2. CORS 错误

**症状**: 浏览器控制台显示 CORS 错误

**解决方案**:
1. 检查后端 `CORS_ORIGINS` 是否包含前端地址
2. 确保 URL 格式正确（无尾部斜杠）
3. 检查端口号是否匹配

### 3. JWT 验证失败

**症状**: 登录后无法访问受保护的路由

**解决方案**:
1. 确保前后端使用相同的 `JWT_SECRET`
2. 检查 Token 是否过期
3. 验证 `JWT_ALGORITHM` 配置

## 📚 参考资料

- [Vite 环境变量文档](https://vitejs.dev/guide/env-and-mode.html)
- [Supabase 环境变量最佳实践](https://supabase.com/docs/guides/getting-started/local-development#environment-variables)
- [OWASP 密钥管理指南](https://cheatsheetseries.owasp.org/cheatsheets/Key_Management_Cheat_Sheet.html)

## ✅ 检查清单

在部署前，请确保:

- [ ] 所有必填的环境变量都已设置
- [ ] JWT_SECRET 使用强随机密钥（至少 32 字节）
- [ ] `.env` 文件已添加到 `.gitignore`
- [ ] `.env.example` 文件不包含真实密钥
- [ ] 生产环境使用独立的密钥（不与开发环境共享）
- [ ] CORS 配置正确（不要使用 `*`）
- [ ] Service Role Key 仅在后端使用
- [ ] 所有环境变量都有注释说明

---

**文档维护**: P2-2 环境变量管理任务
**创建日期**: 2025-10-09
**最后更新**: 2025-10-09
