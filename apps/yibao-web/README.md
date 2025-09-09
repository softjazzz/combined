# 智慧医保质控系统 (Yibao)

## 项目概述

智慧医保质控系统是一个独立的医保规则管理和质控分析平台，提供完整的前后端分离架构。

## 架构特点

- **前端**: Vue 3 + TypeScript + Ant Design Vue + Tailwind CSS
- **后端**: FastAPI + Python + Supabase
- **数据库**: PostgreSQL (通过 Supabase)
- **认证**: JWT Token 认证
- **部署**: 独立部署，与 medqc 项目完全分离

## 项目结构

```
apps/yibao-web/
├── src/                    # 前端源码
│   ├── components/         # Vue 组件
│   ├── views/             # 页面视图
│   ├── stores/            # Pinia 状态管理
│   ├── services/          # API 服务
│   └── router.ts          # 路由配置
├── backend/               # 后端源码
│   ├── main.py           # 主应用入口
│   ├── rules_api.py      # 规则管理 API
│   ├── requirements.txt  # Python 依赖
│   └── venv/            # Python 虚拟环境
├── package.json          # 前端依赖配置
├── vite.config.ts        # Vite 配置
└── README.md            # 项目文档
```

## 快速开始

### 1. 环境准备

确保已安装以下软件：
- Node.js 18+
- Python 3.8+
- npm 或 yarn

### 2. 安装依赖

```bash
# 安装前端依赖
npm install

# 安装后端依赖
cd backend
python3 -m venv venv
source venv/bin/activate  # Linux/Mac
# 或 venv\Scripts\activate  # Windows
pip install -r requirements.txt
```

### 3. 配置环境变量

复制环境变量模板：
```bash
cp .env.example .env
```

编辑 `.env` 文件，配置以下参数：
```env
# API 服务配置
VITE_API_BASE_URL=http://localhost:8002
YIBAO_API_PORT=8002

# Supabase 配置（可选）
VITE_SUPABASE_URL=your_supabase_url
VITE_SUPABASE_ANON_KEY=your_supabase_key
```

### 4. 启动服务

#### 方式一：分别启动前后端

```bash
# 启动后端服务 (端口 8002)
cd backend
source venv/bin/activate
python main.py

# 启动前端服务 (端口 3008)
npm run dev
```

#### 方式二：同时启动前后端

```bash
npm run start:full
```

### 5. 访问应用

- 前端应用: http://localhost:3008
- 后端 API: http://localhost:8002
- API 文档: http://localhost:8002/docs

## 功能特性

### 认证系统
- JWT Token 认证
- 用户登录/登出
- 权限管理
- Mock 用户支持

### 规则管理
- 医保规则 CRUD 操作
- 规则分类和筛选
- 规则启用/禁用
- 批量操作

### 沙箱测试
- 规则测试环境
- 单规则测试
- 批量规则测试
- 测试结果分析

### 统计分析
- 规则统计概览
- 按类型/严重级别分组
- 活动统计
- 数据可视化

## API 端点

### 认证相关
- `POST /api/auth/login` - 用户登录
- `GET /api/auth/me` - 获取当前用户信息
- `POST /api/auth/logout` - 用户登出
- `POST /api/auth/refresh` - 刷新 Token

### 规则管理
- `GET /api/rules` - 获取规则列表
- `POST /api/rules` - 创建新规则
- `GET /api/rules/{id}` - 获取规则详情
- `PUT /api/rules/{id}` - 更新规则
- `DELETE /api/rules/{id}` - 删除规则

### 沙箱测试
- `POST /api/rules/sandbox/test` - 单规则测试
- `POST /api/rules/sandbox/batch-test` - 批量测试

### 统计分析
- `GET /api/rules/statistics/overview` - 统计概览

## 默认用户账号

系统提供以下测试账号：

| 邮箱 | 密码 | 角色 | 部门 |
|------|------|------|------|
| admin@yibao.com | admin123 | 管理员 | 医保办 |
| doctor@yibao.com | doctor123 | 医生 | 内科 |
| auditor@yibao.com | auditor123 | 审核员 | 质控科 |

## 开发指南

### 添加新的 API 端点

1. 在 `backend/main.py` 或创建新的路由文件
2. 定义 Pydantic 模型
3. 实现 API 处理函数
4. 注册路由到主应用

### 添加新的前端页面

1. 在 `src/views/` 创建 Vue 组件
2. 在 `src/router.ts` 添加路由配置
3. 在 `src/services/` 添加 API 调用
4. 更新导航菜单

### 数据库集成

系统支持两种数据存储模式：

1. **Mock 模式**: 使用内存数据，适合开发和测试
2. **Supabase 模式**: 连接 PostgreSQL 数据库，适合生产环境

## 部署说明

### 开发环境
- 前端: Vite 开发服务器
- 后端: Uvicorn 开发服务器
- 数据库: Mock 数据或 Supabase

### 生产环境
- 前端: 静态文件部署 (Nginx/Apache)
- 后端: Uvicorn + Gunicorn
- 数据库: Supabase 或自建 PostgreSQL

## 与 medqc 项目的区别

| 特性 | yibao | medqc |
|------|-------|-------|
| 端口 | 8002 | 8001 |
| 功能范围 | 医保质控 | 医疗质控 |
| 数据库 | 独立 Supabase | 共享 Supabase |
| 部署 | 独立部署 | 独立部署 |
| 依赖关系 | 无依赖 | 无依赖 |

## 故障排除

### 常见问题

1. **后端启动失败**
   - 检查 Python 虚拟环境是否激活
   - 确认依赖包已正确安装
   - 检查端口 8002 是否被占用

2. **前端无法连接后端**
   - 确认后端服务已启动
   - 检查 vite.config.ts 中的代理配置
   - 验证 API 基础 URL 配置

3. **登录失败**
   - 使用提供的测试账号
   - 检查后端日志中的错误信息
   - 确认 JWT 密钥配置正确

## 贡献指南

1. Fork 项目
2. 创建功能分支
3. 提交更改
4. 创建 Pull Request

## 许可证

MIT License
