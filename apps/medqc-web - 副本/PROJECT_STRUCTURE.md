# 📁 医疗质控系统项目结构

## 🎯 项目概述

这是一个基于 Vue 3 + FastAPI + Supabase 的智能医疗质控系统，采用现代化的项目结构组织，便于开发、维护和部署。

## 📂 目录结构

```
MedQC0817/
├── 📁 database/                    # 数据库相关文件
│   ├── 📁 setup/                   # 数据库初始化脚本
│   │   ├── database_init_complete.sql
│   │   ├── database_init_part2.sql
│   │   ├── database_init_part3.sql
│   │   ├── database_vector_search_setup.sql
│   │   └── verify_database.sql
│   ├── 📁 fixes/                   # 数据库修复脚本
│   │   ├── database_fix_chinese_search.sql
│   │   ├── database_simple_fix.sql
│   │   └── database_complete_setup.sql
│   ├── 📁 migrations/              # 数据库迁移文件
│   │   ├── migration-sql-for-copy-fixed.sql
│   │   └── database-update.sql
│   └── 📁 schemas/                 # 数据库架构文件
├── 📁 docs/                        # 项目文档
│   ├── 📁 deployment/              # 部署相关文档
│   │   ├── NEW_SUPABASE_DEPLOYMENT_GUIDE.md
│   │   ├── VECTOR_SEARCH_SETUP_GUIDE.md
│   │   └── QUICK_START.md
│   ├── 📁 development/             # 开发相关文档
│   │   ├── FRONTEND_INTEGRATION_GUIDE.md
│   │   ├── MIGRATION_COMPLETE_FINAL_REPORT.md
│   │   └── TAILWIND_REFACTOR_PROGRESS.md
│   ├── 📁 user-guides/             # 用户指南
│   │   ├── USER_MANUAL.md
│   │   ├── AUTH_SYSTEM_GUIDE.md
│   │   └── DOCTOR_WORKSTATION_REDESIGN_GUIDE.md
│   ├── 📁 architecture/            # 架构设计文档
│   │   ├── AUDIT_MODULE_STRUCTURE.md
│   │   ├── SOLUTION_SUMMARY.md
│   │   └── KG_modeling_blueprint_cn.md
│   └── 📁 reports/                 # 项目报告
│       ├── PROJECT_COMPLETION_REPORT.md
│       ├── FINAL_OPTIMIZATION_REPORT.md
│       └── 各种中文报告文档
├── 📁 tools/                       # 工具和脚本
│   ├── 📁 testing/                 # 测试工具
│   │   ├── test_new_supabase_connection.js
│   │   ├── test_api_with_timeout.py
│   │   └── debug_llm_issue.py
│   ├── 📁 deployment/              # 部署工具
│   │   ├── quick_start.sh
│   │   ├── start_frontend.sh
│   │   └── safety_check.sh
│   ├── 📁 database/                # 数据库工具
│   └── 📁 utilities/               # 通用工具
├── 📁 config/                      # 配置文件
│   ├── 📁 docker/                  # Docker 配置
│   │   └── docker-compose.production.yml
│   ├── 📁 build/                   # 构建配置
│   │   ├── tailwind.config.js
│   │   ├── vitest.config.js
│   │   └── eslint.config.js
│   └── 📁 environment/             # 环境配置
├── 📁 assets/                      # 静态资源
│   ├── 📁 data/                    # 测试数据文件
│   │   ├── 测试文件1.txt
│   │   └── 病历质量评定标准.csv
│   ├── 📁 templates/               # 模板文件
│   └── 📁 samples/                 # 示例文件
├── 📁 src/                         # 前端源码
│   ├── 📁 components/              # Vue 组件
│   ├── 📁 views/                   # 页面视图
│   ├── 📁 services/                # 服务层
│   ├── 📁 stores/                  # 状态管理
│   ├── 📁 types/                   # TypeScript 类型
│   └── 📁 utils/                   # 工具函数
├── 📁 production_system/           # 后端系统
│   ├── 📁 api/                     # API 路由
│   ├── 📁 core/                    # 核心业务逻辑
│   ├── 📁 models/                  # 数据模型
│   ├── 📁 services/                # 业务服务
│   └── 📁 utils/                   # 工具函数
├── 📁 tests/                       # 测试文件
├── 📁 scripts/                     # 脚本文件
├── 📁 reports/                     # 报告文件
├── 📄 package.json                 # 前端依赖配置
├── 📄 README.md                    # 项目说明
├── 📄 .env                         # 环境变量
└── 📄 PROJECT_STRUCTURE.md         # 本文档
```

## 🚀 快速开始

### 1. 数据库设置
```bash
# 按顺序执行数据库初始化脚本
database/setup/database_init_complete.sql
database/setup/database_init_part2.sql
database/setup/database_init_part3.sql
database/setup/verify_database.sql
```

### 2. 启动开发环境
```bash
# 前端开发服务器
pnpm dev

# 后端服务器
cd production_system
python main.py
```

### 3. 部署到生产环境
参考 `docs/deployment/NEW_SUPABASE_DEPLOYMENT_GUIDE.md`

## 📚 文档导航

### 🚀 快速开始
- [快速启动指南](docs/deployment/QUICK_START.md)
- [新 Supabase 部署指南](docs/deployment/NEW_SUPABASE_DEPLOYMENT_GUIDE.md)

### 👨‍💻 开发文档
- [前端集成指南](docs/development/FRONTEND_INTEGRATION_GUIDE.md)
- [迁移完成报告](docs/development/MIGRATION_COMPLETE_FINAL_REPORT.md)

### 👥 用户指南
- [用户手册](docs/user-guides/USER_MANUAL.md)
- [认证系统指南](docs/user-guides/AUTH_SYSTEM_GUIDE.md)

### 🏗️ 架构设计
- [审计模块结构](docs/architecture/AUDIT_MODULE_STRUCTURE.md)
- [解决方案总结](docs/architecture/SOLUTION_SUMMARY.md)

## 🔧 工具使用

### 测试工具
```bash
# 测试 Supabase 连接
node tools/testing/test_new_supabase_connection.js

# 测试 API 接口
python tools/testing/test_api_with_timeout.py
```

### 部署工具
```bash
# 快速启动
bash tools/deployment/quick_start.sh

# 启动前端
bash tools/deployment/start_frontend.sh
```

## 📊 核心功能

### 🏥 医疗记录管理
- 病历上传和存储
- 多格式文档支持
- 版本控制和历史记录

### 🤖 AI 质控分析
- 智能质控规则引擎
- 自动化问题检测
- 质量评分和建议

### 📈 统计分析
- 实时质控统计
- 科室和医生表现分析
- 趋势分析和预警

### 🔍 智能搜索
- 中文语义搜索
- 向量数据库支持
- 相似病例推荐

## 🔒 安全特性

- **用户认证**：基于 Supabase Auth
- **权限控制**：行级安全策略 (RLS)
- **数据隔离**：科室级别访问控制
- **审计日志**：完整的操作记录

## 🛠️ 技术栈

### 前端
- **框架**：Vue 3 + TypeScript
- **构建工具**：Vite
- **UI 库**：Ant Design Vue
- **样式**：Tailwind CSS
- **状态管理**：Pinia

### 后端
- **框架**：FastAPI + Python
- **数据库**：Supabase (PostgreSQL)
- **认证**：Supabase Auth
- **AI 服务**：OpenAI API

### 部署
- **容器化**：Docker
- **CI/CD**：GitHub Actions
- **监控**：自定义监控脚本

## 📞 支持

如有问题，请参考相关文档或联系开发团队。

---

**最后更新**：2024-12-25  
**版本**：2.0.0
