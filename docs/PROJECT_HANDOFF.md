# MedQC 病案质控系统 - 项目交接文档

> 📅 最后更新: 2026-01-04 20:25

---

## 一、项目概述

**MedQC** 是一个基于 AI 的医疗病案质量控制平台，核心功能包括：
- 从非结构化病历文本中**自动提取结构化病案首页信息**
- **ICD 编码智能推荐**（诊断 ICD-10、手术 ICD-9-CM-3）
- **DRG/DIP 分组预测**与费用分析
- 病历质控规则引擎

### 技术栈

| 层级 | 技术 |
|------|------|
| 前端 | Vue 3 + TypeScript + Ant Design Vue + TailwindCSS |
| 后端 | FastAPI (Python 3.11+) |
| 数据库 | Supabase (PostgreSQL) |
| AI/LLM | DeepSeek API / 外部编码服务 |

---

## 二、目录结构

```
health-qc-monorepo/
├── apps/medqc-web/           # 主应用
│   ├── src/                  # 前端源码
│   │   ├── views/demo/       # Demo 页面
│   │   │   └── FrontPageDemoView.vue  # ⭐ 核心演示页
│   │   └── components/       # 组件
│   ├── backend/              # FastAPI 后端
│   │   ├── app/
│   │   │   ├── main.py       # 应用入口
│   │   │   ├── routers/      # API 路由
│   │   │   │   ├── case_front_page.py  # ⭐ 编码提取 API
│   │   │   │   ├── frontpage.py        # 首页生成 API
│   │   │   │   └── drg.py              # DRG 相关
│   │   │   └── services/     # 业务服务
│   │   │       ├── external_coding_service.py  # ⭐ 外部编码 API 代理
│   │   │       └── llm_service.py              # LLM 调用
│   │   └── .venv/            # Python 虚拟环境
│   ├── vite.config.ts        # Vite 配置（含 API 代理）
│   └── start-services.sh     # 一键启动脚本
├── DRG/                      # DRG/编码相关文档
│   ├── CODING_API_INTEGRATION_GUIDE.md  # ⭐ 编码 API 接入指南
│   ├── CODING_API_TEST_REPORT.md        # API 测试报告
│   └── test_coding_api.py               # 测试脚本
└── docs/
    └── DRG_DIP_System_PRD.md            # 产品需求文档
```

---

## 三、已完成工作

### 3.1 前端 Demo 页面 (`FrontPageDemoView.vue`)

| 功能 | 状态 | 说明 |
|------|------|------|
| 病历原文展示 | ✅ | 左侧面板，支持加载测试病历 |
| AI 结构化提取 | ✅ | 调用后端 API 提取病案首页字段 |
| 结构化结果展示 | ✅ | 表格形式展示基本信息、住院信息、诊断、手术 |
| AI 画像分析 | ✅ | 诊断时间轴、手术闭环验证 |
| HM 模板预览 | ✅ | 标准病案首页模板渲染 |
| 医保清单 | ✅ | 费用概览 |
| **展开/收起模式** | ✅ | 右侧工作台可全屏展开 |

### 3.2 后端 API

| 端点 | 方法 | 功能 |
|------|------|------|
| `/api/v1/case-front-page/extract-coding` | POST | 调用外部编码服务提取 ICD 编码 |
| `/api/v1/frontpage/auto-generate-draft` | POST | 自动生成病案首页草稿 |
| `/api/v1/frontpage/profile/analyze` | POST | 医疗画像分析 |

### 3.3 外部 API 集成

**ICD 编码服务** (`http://122.51.111.253:8002`)
- 已实现代理服务：[external_coding_service.py](file:///home/ubuntu/coding/health-qc-monorepo/apps/medqc-web/backend/app/services/external_coding_service.py)
- 工作模式：异步（提交任务 → 轮询结果）
- 详细文档：[CODING_API_INTEGRATION_GUIDE.md](file:///home/ubuntu/coding/health-qc-monorepo/DRG/CODING_API_INTEGRATION_GUIDE.md)

---

## 四、如何运行

### 4.1 一键启动（推荐）

```bash
cd /home/ubuntu/coding/health-qc-monorepo/apps/medqc-web
./start-services.sh all
```

### 4.2 分别启动

```bash
# 后端 (端口 8001)
cd apps/medqc-web/backend
source .venv/bin/activate
uvicorn app.main:app --host 0.0.0.0 --port 8001 --reload

# 前端 (端口 3000)
cd apps/medqc-web
pnpm dev
```

### 4.3 访问地址

| 服务 | URL |
|------|-----|
| 前端 | http://localhost:3000 |
| 后端 API | http://localhost:8001 |
| API 文档 | http://localhost:8001/docs |
| Demo 页面 | http://localhost:3000/demo/frontpage |

---

## 五、下阶段任务

### 5.1 高优先级 (P0)

| 任务 | 说明 | 相关文件 |
|------|------|----------|
| **真实 LLM 提取** | 用 LLM 从病历原文提取全量首页字段（目前基本信息是 Mock） | `FrontPageExtractionService` |
| **ICD 编码校验** | 调用 `/api/v1/coding/validate` 校验编码合规性 | `external_coding_service.py` |
| **DRG 分组集成** | 调用 `https://medchat.fun/api/drg-grouping` 预测 DRG 分组 | 新建 `drg_grouping_service.py` |

### 5.2 中优先级 (P1)

| 任务 | 说明 |
|------|------|
| 费用预测 | 根据 DRG 分组预测医保支付额度 |
| 实时成本监控 | 住院期间费用预警 |
| 编码建议高亮 | 在病历原文中高亮 AI 提取的证据片段 |

### 5.3 低优先级 (P2)

| 任务 | 说明 |
|------|------|
| PDF/图片 OCR | 支持上传扫描件自动识别 |
| 导出功能 | CSV/PDF 导出病案首页 |
| HIS 系统对接 | 从医院 HIS 拉取真实病历 |

---

## 六、关键配置

### Vite 代理 (`vite.config.ts`)

```typescript
proxy: {
  '/api/v1/drg': { target: 'http://127.0.0.1:8001' },
  '/api': { target: 'http://127.0.0.1:8001' }
}
```

### 环境变量

后端需要 `JWT_SECRET` 环境变量（启动脚本已自动设置为 `dev-secret`）。

---

## 七、已知问题

| 问题 | 状态 | 备注 |
|------|------|------|
| 基本信息/住院信息为 Mock | ⚠️ | API 只返回诊断和手术，其他字段需 LLM 提取 |
| 编码服务 422 响应 | ℹ️ | 正常行为，表示需要人工确认 |
| 前端 TypeScript 类型松散 | ⚠️ | `frontpage` 使用 `any` 类型 |

---

## 八、参考文档

- [DRG/DIP 系统 PRD](file:///home/ubuntu/coding/health-qc-monorepo/docs/DRG_DIP_System_PRD.md)
- [编码 API 接入指南](file:///home/ubuntu/coding/health-qc-monorepo/DRG/CODING_API_INTEGRATION_GUIDE.md)
- [DRG 实现状态](file:///home/ubuntu/coding/health-qc-monorepo/apps/medqc-web/docs/DRG-IMPLEMENTATION-STATUS.md)
- [Gap 分析报告](file:///home/ubuntu/.gemini/antigravity/brain/e9370c06-130d-416d-8021-001011bff599/implementation_plan.md)
