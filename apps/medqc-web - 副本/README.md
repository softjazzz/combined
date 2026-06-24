# 🏥 医疗质控系统 (MedQC)

[![Vue 3](https://img.shields.io/badge/Vue-3.x-4FC08D?logo=vue.js)](https://vuejs.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.104+-009688?logo=fastapi)](https://fastapi.tiangolo.com/)
[![Supabase](https://img.shields.io/badge/Supabase-Database-3ECF8E?logo=supabase)](https://supabase.com/)
[![TypeScript](https://img.shields.io/badge/TypeScript-5.x-3178C6?logo=typescript)](https://www.typescriptlang.org/)
[![Python](https://img.shields.io/badge/Python-3.10+-3776AB?logo=python)](https://www.python.org/)

> 基于 AI 的智能医疗质控系统，提供病历质量分析、智能搜索和统计分析功能

## ✨ 核心特性

### 🤖 AI 智能质控
- **智能分析引擎**：基于大语言模型的病历质量分析
- **多维度评估**：完整性、准确性、及时性、一致性、合规性
- **自动化检测**：智能发现质控问题并提供改进建议
- **批量处理**：支持大规模病历批量质控分析

### 🔍 智能搜索
- **语义搜索**：基于向量数据库的中文语义搜索
- **相似病例**：智能推荐相似病例和治疗方案
- **全文检索**：支持中文分词和模糊匹配
- **混合搜索**：结合关键词和语义的混合搜索

### 📊 数据分析
- **实时统计**：科室、医生、病历质量实时统计
- **趋势分析**：质控指标趋势分析和预警
- **可视化报告**：丰富的图表和报告生成
- **多维度分析**：按时间、科室、医生等多维度分析

### 🔒 安全管理
- **用户认证**：基于 Supabase Auth 的安全认证
- **权限控制**：基于角色的精细化权限管理
- **数据隔离**：科室级别的数据访问控制
- **审计日志**：完整的操作审计和追踪

## 🚀 快速开始

### 📋 环境要求

- **Node.js** >= 18.0.0
- **Python** >= 3.10
- **pnpm** >= 8.0.0
- **Supabase** 账户

### 🛠️ 安装部署

#### 1. 克隆项目
```bash
git clone <repository-url>
cd MedQC0817
```

#### 2. 数据库设置
```bash
# 在 Supabase SQL Editor 中按顺序执行
database/setup/database_init_complete.sql
database/setup/database_init_part2.sql
database/setup/database_init_part3.sql
database/setup/verify_database.sql
```

#### 3. 环境配置
```bash
# 复制环境变量模板
cp .env.example .env

# 配置 Supabase 连接信息
VITE_SUPABASE_URL=your_supabase_url
VITE_SUPABASE_ANON_KEY=your_supabase_anon_key
```

#### 4. 安装依赖
```bash
# 前端依赖
pnpm install

# 后端依赖
cd production_system
pip install -r requirements.txt
```

#### 5. 启动服务
```bash
# 启动前端开发服务器
pnpm dev

# 启动后端服务器
cd production_system
python main.py
```

#### 6. 访问应用
- **前端**: http://localhost:5173
- **后端 API**: http://localhost:8001
- **API 文档**: http://localhost:8001/docs

## 📁 项目结构

```
MedQC0817/
├── 📁 database/                    # 数据库相关文件
│   ├── setup/                      # 初始化脚本
│   ├── fixes/                      # 修复脚本
│   └── migrations/                 # 迁移文件
├── 📁 docs/                        # 项目文档
│   ├── deployment/                 # 部署文档
│   ├── development/                # 开发文档
│   ├── user-guides/                # 用户指南
│   └── architecture/               # 架构设计
├── 📁 src/                         # 前端源码
├── 📁 production_system/           # 后端系统
├── 📁 tools/                       # 工具脚本
└── 📁 config/                      # 配置文件
```

详细结构说明请参考 [PROJECT_STRUCTURE.md](PROJECT_STRUCTURE.md)

## 📚 文档导航

### 🚀 快速开始
- [快速启动指南](docs/deployment/QUICK_START.md)
- [Supabase 部署指南](docs/deployment/NEW_SUPABASE_DEPLOYMENT_GUIDE.md)
- [向量搜索设置](docs/deployment/VECTOR_SEARCH_SETUP_GUIDE.md)

### 👨‍💻 开发文档
- [前端集成指南](docs/development/FRONTEND_INTEGRATION_GUIDE.md)
- [API 接口文档](docs/api/)
- [架构设计文档](docs/architecture/)

### 👥 用户指南
- [用户手册](docs/user-guides/USER_MANUAL.md)
- [认证系统指南](docs/user-guides/AUTH_SYSTEM_GUIDE.md)
- [医生工作站指南](docs/user-guides/DOCTOR_WORKSTATION_REDESIGN_GUIDE.md)

## 🛠️ 技术栈

### 前端技术
- **框架**: Vue 3 + TypeScript
- **构建工具**: Vite
- **UI 组件**: Ant Design Vue
- **样式框架**: Tailwind CSS
- **状态管理**: Pinia
- **路由**: Vue Router

### 后端技术
- **框架**: FastAPI + Python
- **数据库**: Supabase (PostgreSQL)
- **认证**: Supabase Auth
- **AI 服务**: OpenAI API
- **向量搜索**: pgvector

### 部署运维
- **容器化**: Docker
- **CI/CD**: GitHub Actions
- **监控**: 自定义监控脚本
- **日志**: 结构化日志记录

## 🔧 开发工具

### 测试工具
```bash
# 测试数据库连接
node tools/testing/test_new_supabase_connection.js

# 测试 API 接口
python tools/testing/test_api_with_timeout.py

# 运行前端测试
pnpm test

# 运行后端测试
cd production_system && python -m pytest
```

### 部署工具
```bash
# 快速启动脚本
bash tools/deployment/quick_start.sh

# 安全检查
bash tools/deployment/safety_check.sh
```

## 📊 功能模块

### 🏥 医疗记录管理
- 病历上传和存储
- 多格式文档支持
- 版本控制和历史记录
- 批量导入导出

### 🤖 质控分析
- AI 驱动的质量分析
- 多维度质控规则
- 自动化问题检测
- 质量评分和建议

### 📈 统计报告
- 实时质控统计
- 科室表现分析
- 医生工作效率
- 趋势分析和预警

### 🔍 智能搜索
- 语义搜索
- 相似病例推荐
- 全文检索
- 高级筛选

## 🤝 贡献指南

1. Fork 项目
2. 创建功能分支 (`git checkout -b feature/AmazingFeature`)
3. 提交更改 (`git commit -m 'Add some AmazingFeature'`)
4. 推送到分支 (`git push origin feature/AmazingFeature`)
5. 创建 Pull Request

## 📄 许可证

本项目采用 MIT 许可证 - 查看 [LICENSE](LICENSE) 文件了解详情

## 📞 支持

- 📧 邮箱: support@medqc.com
- 📖 文档: [项目文档](docs/)
- 🐛 问题反馈: [GitHub Issues](https://github.com/your-repo/issues)

## 🎯 路线图

- [ ] 移动端适配
- [ ] 多语言支持
- [ ] 高级 AI 分析
- [ ] 第三方系统集成
- [ ] 云原生部署

---

**最后更新**: 2024-12-25  
**版本**: 2.0.0  
**维护者**: MedQC 开发团队
