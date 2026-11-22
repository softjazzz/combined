# 🏥 医疗质控系统 (MedQC)

[![Vue 3](https://img.shields.io/badge/Vue-3.x-4FC08D?logo=vue.js)](https://vuejs.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.104+-009688?logo=fastapi)](https://fastapi.tiangolo.com/)
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
- **用户认证**：业务 API 负责用户认证
- **权限控制**：基于角色的精细化权限管理
- **数据隔离**：科室级别的数据访问控制
- **审计日志**：完整的操作审计和追踪

## 本地启动

需要 Node.js 18+、pnpm 8+、Python 3.10+ 和开发用 PostgreSQL。后端入口为 `backend/app/main.py`，前端使用 `vite.config.mjs`。初始化开发库可参照 [Alembic 迁移说明](backend/docs/ALEMBIC_MIGRATION.md)。

1. 在仓库根目录执行 `pnpm install`。
2. 从 `apps/medqc-web/backend/.env.example` 复制一份 `.env` 到同目录。设置开发库的 `DATABASE_URL`、与该库一致的 `DB_SCHEMA_MODE`、随机 `JWT_SECRET`，以及 `DATA_SOURCE=pg`。需要独立 CDM 时，按模板配置其只读连接。
3. 在独立终端启动后端。以下命令从仓库根目录执行。

   Linux 或 macOS

   ```bash
   cd apps/medqc-web/backend
   python3 -m venv .venv
   .venv/bin/python -m pip install -r requirements.txt
   .venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8001 --reload
   ```

   Windows PowerShell

   ```powershell
   Set-Location apps/medqc-web/backend
   py -3.10 -m venv .venv
   ./.venv/Scripts/python.exe -m pip install -r requirements.txt
   ./.venv/Scripts/python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8001 --reload
   ```

4. 在另一个终端从仓库根目录执行 `pnpm --dir apps/medqc-web dev`。前端默认访问 `http://localhost:3000`，代理至 `http://localhost:8001`。
5. 前端定向测试使用 `pnpm --dir apps/medqc-web test:unit <测试文件>`。后端隔离用例在 `backend` 内执行 `python -B scripts/run_pr8_offline_tests.py <测试文件>`。

## 项目结构

```text
apps/medqc-web/
├── src/              # Vue 前端
├── backend/          # FastAPI、Alembic 和后端测试
├── tests/            # 前端单元与端到端测试
└── docs/             # 设计、开发与部署资料
```

### 工作台源码入口

- `/workstation-v5` 由 [工作台路由](src/router/index.ts) 挂载。主入口在 `src/views/workstation-v4/`，首页由 [WorkstationV4HomeEntry](src/views/workstation-v4/WorkstationV4HomeEntry.vue) 加载 [QCOverviewView](src/views/workstation/QCOverviewView.vue)，病历池入口为 [WorkstationV4View](src/views/workstation-v4/WorkstationV4View.vue)。
- `/workstation-v4` 是现行路由的兼容别名。`/workstation-v2`、`/workstation-v3` 和 `/dashboard/medical-records/:id/legacy` 保留旧工作台与病历详情入口。
- `src/views/workstation-v2/WorkstationV4View.vue` 和 `src/views/workstation-v4/WorkstationV3View.vue` 是历史副本。旧 DRG 文档仍引用 `backend-fastapi/`，现行 FastAPI 入口为 [backend/app/main.py](backend/app/main.py)。

## 📚 文档导航

### 开发与部署入口

- [开发端口说明](../../DEVELOPMENT_PORTS.md)
- [现行 Workstation v7.1 设计规范](docs/0418/UI/WorkstationV4-医疗浅色-DESIGN.md)
- [Linux 发布与回滚手册](docs/deployment/P2_RELEASE_RUNBOOK.md)
- [Linux 后端启动脚本](../../scripts/run_backend_prod.sh)
- [历史 Docker 部署说明](docs/DEPLOYMENT.md)

### 👨‍💻 开发文档
- [前端集成指南](docs/development/FRONTEND_INTEGRATION_GUIDE.md)
- [API 接口文档](docs/api/)
- [架构设计文档](docs/architecture/)

### 👥 用户指南
- [用户手册](docs/0418/WORKSTATION_V4/USER_MANUAL.md)
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
- **数据库**: PostgreSQL
- **认证**: FastAPI 业务认证
- **AI 服务**: 由后端环境配置选择
- **向量搜索**: pgvector

### 部署运维
- **Linux 服务**: systemd
- **CI/CD**: GitHub Actions
- **监控**: 自定义监控脚本
- **日志**: 结构化日志记录

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
- 🐛 问题反馈: [GitHub Issues](https://github.com/softjazzz/combined/issues)

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
