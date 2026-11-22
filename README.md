# 医疗质控系统 Monorepo

> 🏥 基于 Vue 3 + TypeScript 的智能医疗质控管理平台

[![Node.js](https://img.shields.io/badge/Node.js-18.x+-green.svg)](https://nodejs.org/)
[![Vue.js](https://img.shields.io/badge/Vue.js-3.x-blue.svg)](https://vuejs.org/)
[![TypeScript](https://img.shields.io/badge/TypeScript-5.x-blue.svg)](https://www.typescriptlang.org/)
[![License](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

## 📋 项目概述

本项目是一个全栈医疗质控管理系统，采用 Monorepo 架构，包含两个核心应用：

- **MedQC-Web**: 通用医疗质控系统，支持病案质控、规则管理、AI 分析等功能
- **YiBao-Web**: 医保质控专业系统，专注于医保费用审核、违规检测等功能

## 🏗️ 项目架构

```
health-qc-monorepo/
├── apps/                          # 应用程序目录
│   ├── medqc-web/                 # 医疗质控系统 (端口: 3000)
│   │   ├── src/                   # 源代码
│   │   ├── public/                # 静态资源
│   │   ├── backend/               # FastAPI 后端 (端口: 8001)
│   │   ├── docs/                  # 项目文档
│   │   └── .env.template          # 环境变量模板
│   └── yibao-web/                 # 医保质控系统 (端口: 3008)
│       ├── src/                   # 源代码
│       ├── backend/               # FastAPI 后端 (端口: 8008)
│       ├── tests/                 # 测试文件
│       └── .env.template          # 环境变量模板
├── docs/                          # 共享文档
├── scripts/                       # 构建脚本
├── dev-env.sh                     # 开发环境管理脚本
├── DEVELOPMENT_PORTS.md           # 端口分配标准
└── package.json                   # Monorepo 根配置
```

## 🚀 快速开始

### 前置要求

- Node.js 18.x+
- pnpm 8.x+
- Python 3.10+（MedQC 后端）

### 1. 克隆项目

```bash
git clone <repository-url>
cd health-qc-monorepo
```

### 2. 安装依赖

```bash
pnpm install
```

### 3. 启动 MedQC

按 [MedQC 本地启动说明](apps/medqc-web/README.md#本地启动) 配置开发用 PostgreSQL 并启动 FastAPI（默认端口 8001）。然后在仓库根目录启动前端。

```bash
pnpm --dir apps/medqc-web dev
```

前端默认使用 3000 端口，将 API 请求代理到 8001。根目录脚本 `pnpm dev:medqc`、`pnpm dev:yibao` 和 `pnpm dev:all` 启动前端开发服务。

## 🎯 核心功能

### MedQC-Web (医疗质控系统)

- 🔍 **智能质控分析**: 基于 LLM 的病历质量评估
- 📊 **统计分析**: 多维度数据统计和趋势分析
- 🔔 **通知系统**: 实时质控结果通知和处理
- ⚖️ **申诉管理**: 完整的质控结果申诉流程
- 📋 **规则管理**: 灵活的质控规则配置和管理
- 🎪 **演示系统**: 完整的 LLM 质控流程演示

### YiBao-Web (医保质控系统)

- 💰 **费用审核**: 智能医保费用审核和违规检测
- 📋 **目录管理**: 药品、诊疗项目、设施目录管理
- 🔍 **欺诈检测**: 基于 AI 的医保欺诈检测
- 📊 **数据分析**: 医保数据统计和预测分析
- 🏥 **HIS 集成**: 与医院信息系统深度集成

## 🔧 开发工具

### 开发环境管理脚本

```bash
# 检查服务状态
./dev-env.sh status

# 清理占用端口
./dev-env.sh clean

# 启动所有服务
./dev-env.sh start-all

# 停止所有服务
./dev-env.sh stop

# 显示帮助
./dev-env.sh help
```

### 常用命令

```bash
# 开发相关
pnpm dev              # 启动 medqc-web
pnpm dev:medqc        # 启动 medqc-web (指定端口)
pnpm dev:yibao        # 启动 yibao-web (指定端口)
pnpm dev:all          # 并发启动所有前端服务

# 构建相关
pnpm build            # 构建所有应用
pnpm lint             # 代码检查
pnpm type-check       # 类型检查

# 测试相关
pnpm test             # 运行所有测试
pnpm --dir apps/medqc-web test:unit  # 运行 MedQC 前端单元测试
pnpm test:yibao       # 运行 yibao-web 所有测试

# 管理相关
pnpm status           # 检查服务状态
pnpm clean            # 清理端口
```

## 📡 端口分配

| 服务名称 | 端口 | 用途 | 访问地址 |
|---------|------|------|----------|
| medqc-web | 3000 | 医疗质控系统前端 | http://localhost:3000 |
| yibao-web | 3008 | 医保质控系统前端 | http://localhost:3008 |
| medqc-api | 8001 | 医疗质控API服务 | http://localhost:8001 |
| yibao-api | 8008 | 医保质控API服务 | http://localhost:8008 |

详细的端口分配和配置说明见 [DEVELOPMENT_PORTS.md](DEVELOPMENT_PORTS.md)。

## ⚙️ 环境配置

每个应用都提供了详细的环境变量模板：

- `apps/medqc-web/.env.template` - MedQC 系统配置模板
- `apps/yibao-web/.env.template` - YiBao 系统配置模板

复制模板文件为 `.env` 并根据实际环境修改配置值。

## 🧪 测试

### MedQC-Web 测试

```bash
cd apps/medqc-web
pnpm test:unit     # 单元测试
pnpm test:e2e      # 端到端测试
```

### YiBao-Web 测试

YiBao-Web 采用分层测试架构：

```bash
cd apps/yibao-web

# 前端测试
pnpm test:frontend

# 后端测试
pnpm test:backend

# 集成测试
pnpm test:integration

# 端到端测试
pnpm test:e2e

# 运行所有测试
pnpm test:all
```

## 📚 文档

- [开发环境配置](DEVELOPMENT_PORTS.md) - 端口分配和环境配置
- [MedQC 使用指南](apps/medqc-web/docs/LLM质控演示系统使用指南.md) - LLM 质控演示系统详细使用说明
- [YiBao 测试文档](apps/yibao-web/tests/README.md) - 测试架构和执行指南

## 🛠️ 技术栈

### 前端技术

- **框架**: Vue 3 + Composition API
- **语言**: TypeScript 5.x
- **构建工具**: Vite 6.x
- **UI 框架**: Ant Design Vue 4.x
- **状态管理**: Pinia
- **路由**: Vue Router 4.x
- **样式**: Less + CSS Modules
- **图表**: ECharts (计划集成)

### 后端技术

- **框架**: FastAPI (Python)
- **数据库**: PostgreSQL + Supabase
- **缓存**: Redis
- **AI/LLM**: OpenAI GPT / Anthropic Claude
- **部署**: Docker + Nginx

### 开发工具

- **包管理**: pnpm Workspace
- **代码质量**: ESLint + Prettier
- **类型检查**: Vue TSC
- **测试**: Vitest + Vue Test Utils
- **CI/CD**: GitHub Actions (待配置)

## 🔄 开发工作流

1. **功能开发**: 在对应的 `apps/` 目录下进行开发
2. **代码检查**: 提交前运行 `pnpm lint` 和 `pnpm type-check`
3. **测试验证**: 运行相关测试确保功能正常
4. **环境测试**: 使用 `./dev-env.sh` 验证多服务协作
5. **文档更新**: 更新相关文档和 README

## 🤝 贡献指南

1. Fork 本仓库
2. 创建功能分支 (`git checkout -b feature/amazing-feature`)
3. 提交更改 (`git commit -m 'Add some amazing feature'`)
4. 推送分支 (`git push origin feature/amazing-feature`)
5. 创建 Pull Request

## 📄 许可证

本项目采用 MIT 许可证 - 详见 [LICENSE](LICENSE) 文件

## 📞 支持与反馈

- 🐛 **Bug 报告**: 请在 [Issues](https://github.com/softjazzz/combined/issues) 中提交
- 💡 **功能建议**: 欢迎在 [Issues](https://github.com/softjazzz/combined/issues) 中讨论
- 📧 **技术支持**: 联系开发团队

---

<div align="center">

**🏥 让医疗质控更智能，让医疗服务更安全**

Made with ❤️ by MedQC Team

</div>
