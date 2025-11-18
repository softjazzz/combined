# MedQC 文档中心

> 🏥 医疗质控系统 (MedQC) 完整文档集合

## 📚 文档目录

### 🚀 启动指南
- **[启动指南.md](./启动指南.md)** - 中文版前后端启动完整指南
- **[STARTUP_GUIDE.md](./STARTUP_GUIDE.md)** - English version startup guide
- **[start-services.sh](../start-services.sh)** - 一键启动脚本

### 📋 功能文档
- **[LLM质控演示系统使用指南.md](./LLM质控演示系统使用指南.md)** - LLM质控演示系统详细使用说明（PRD）
- **[LLM质控演示系统技术文档.md](./LLM质控演示系统技术文档.md)** - LLM质控演示系统技术架构文档

### 🔧 开发文档
- **[四川省质控功能实现总结.md](./四川省质控功能实现总结.md)** - 四川省质控规则实现总结
- **[四川语义质控68条-导入与字段映射说明.md](./四川语义质控68条-导入与字段映射说明.md)** - 质控规则导入说明

### 🎯 LLM 质控演示系统重构文档（2025-10-17 新增）
- **[LLM质控演示系统重构-TDD-1017.md](./LLM质控演示系统重构-TDD-1017.md)** - 技术设计文档（架构、设计、实施计划）
- **[LLM质控演示系统重构-开发者手册-1017.md](./LLM质控演示系统重构-开发者手册-1017.md)** - 开发者手册（代码示例、规范、最佳实践）
- **[LLM质控演示系统重构-快速参考-1017.md](./LLM质控演示系统重构-快速参考-1017.md)** - 快速参考卡片（代码片段、速查表）
- **[LLM质控演示系统-质控规则设计说明-1017.md](./LLM质控演示系统-质控规则设计说明-1017.md)** - 质控规则设计说明（规则来源、分类、配置）

### 📊 项目管理
- **[项目完成总结报告.md](./项目完成总结报告.md)** - 项目整体完成情况总结
- **[生产环境集成完成报告.md](./生产环境集成完成报告.md)** - 生产环境部署报告

## 🚀 快速开始

### 方法一：使用启动脚本 (推荐)
```bash
# 进入项目目录
cd /home/ubuntu/coding/health-qc-monorepo/apps/medqc-web

# 启动所有服务
./start-services.sh

# 或者分别启动
./start-services.sh frontend  # 仅启动前端
./start-services.sh backend   # 仅启动后端
./start-services.sh status    # 检查状态
./start-services.sh stop      # 停止服务
```

### 方法二：手动启动
```bash
# 启动前端 (端口 3000)
cd /home/ubuntu/coding/health-qc-monorepo
pnpm dev:medqc

# 启动后端 (端口 8001) - 新终端
cd /home/ubuntu/coding/health-qc-monorepo/apps/medqc-web/backend
source venv/bin/activate
export JWT_SECRET=dev-secret
uvicorn app.main:app --host 0.0.0.0 --port 8001 --reload
```

## 🌐 访问地址

| 服务 | 端口 | 访问地址 | 说明 |
|------|------|----------|------|
| 前端应用 | 3000 | http://localhost:3000 | Vue 3 应用主界面 |
| 后端API | 8001 | http://localhost:8001 | FastAPI 服务 |
| API文档 | 8001 | http://localhost:8001/docs | Swagger UI 文档 |
| 健康检查 | 8001 | http://localhost:8001/api/health | 服务状态检查 |

## 📋 核心功能

### 🤖 AI 智能质控
- 基于大语言模型的病历质量分析
- 多维度评估：完整性、准确性、及时性、一致性、合规性
- 自动化检测质控问题并提供改进建议

### 📊 文书分类管理
- **标准六大类文书分类**：
  1. 入院记录 (`admission_record`)
  2. 病程记录 (`progress_note`)
  3. 出院记录 (`discharge_record`)
  4. 手术相关记录 (`operation_record`)
  5. 辅助检查 (`examination_report`)
  6. 知情同意书 (`consent_form`)

### 🔍 质控规则引擎
- 68条四川省质控规则
- 智能规则匹配和执行
- 多文书类型交叉检查

### 🎪 演示系统
- 完整的LLM质控流程演示
- 医生端通知处理模拟
- 申诉管理系统

## 🛠️ 技术架构

### 前端技术栈
- **框架**: Vue 3 + Composition API + TypeScript
- **构建工具**: Vite 6.x
- **UI组件**: Ant Design Vue 4.x
- **状态管理**: Pinia
- **样式**: Tailwind CSS + Less

### 后端技术栈
- **框架**: FastAPI (Python)
- **数据库**: Supabase (PostgreSQL)
- **认证**: Supabase Auth
- **AI服务**: OpenAI API / Anthropic Claude
- **向量搜索**: pgvector

## 📝 开发规范

### 代码规范
- **TypeScript**: 严格类型检查
- **ESLint**: 代码质量检查
- **Prettier**: 代码格式化

### 文书类型规范
- 使用标准六大类分类代码
- 前后端类型定义保持一致
- 质控规则映射标准化

## ❗ 常见问题

### 启动问题
1. **后端启动失败**: 检查虚拟环境和JWT_SECRET设置
2. **端口冲突**: 使用脚本自动处理或手动停止冲突进程
3. **依赖缺失**: 确保安装了所有必要依赖

### 功能问题
1. **API调用失败**: 确认后端在8001端口运行
2. **文书分类错误**: 检查是否使用标准六大类代码
3. **质控规则不匹配**: 验证文书类型与规则映射关系

## 📞 技术支持

### 文档支持
- 详细启动指南: [启动指南.md](./启动指南.md)
- 英文文档: [STARTUP_GUIDE.md](./STARTUP_GUIDE.md)
- 功能说明: [LLM质控演示系统使用指南.md](./LLM质控演示系统使用指南.md)

### 脚本工具
- 启动脚本: `./start-services.sh`
- 状态检查: `./start-services.sh status`
- 服务停止: `./start-services.sh stop`

### 联系方式
- 开发团队: MedQC Development Team
- 项目仓库: health-qc-monorepo
- 文档维护: 持续更新

---

## 🆕 最新更新（2025-10-17）

### LLM 质控演示系统重构文档发布

为了更好地支持 LLM 质控演示系统的重构工作，我们新增了以下三份文档：

1. **技术设计文档（TDD）**
   - 完整的架构设计和组件层级结构
   - 详细的实施计划和任务分解
   - 明确的验收标准和质量要求
   - 适合：开发前了解整体设计，制定开发计划

2. **开发者手册**
   - 8 个核心组件的完整代码示例
   - Ant Design Vue 组件使用规范
   - Store 扩展指南和最佳实践
   - 适合：开发时参考具体实现方法

3. **快速参考卡片**
   - 常用代码片段和工具函数
   - Ant Design 组件速查表
   - Store 方法速查表
   - 适合：开发时快速查找和复制代码

**推荐阅读顺序**：
- 首次接触：PRD → TDD-1017 → 开发者手册-1017 → 快速参考-1017
- 日常开发：快速参考-1017 → 开发者手册-1017 → TDD-1017

---

**最后更新**: 2025-10-17
**文档版本**: v1.1.0
**维护者**: MedQC 开发团队
