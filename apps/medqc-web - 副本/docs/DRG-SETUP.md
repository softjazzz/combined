# DRG/DIP 模块设置指南

本文档介绍如何设置和使用病案质控系统的 DRG/DIP 模块。

## 📋 目录

1. [功能概述](#功能概述)
2. [架构设计](#架构设计)
3. [快速开始](#快速开始)
4. [数据库设置](#数据库设置)
5. [开发模式](#开发模式)
6. [生产部署](#生产部署)
7. [API 文档](#api-文档)
8. [常见问题](#常见问题)

---

## 功能概述

DRG/DIP 模块提供以下核心功能：

### 3.2.1 编码智能辅助
- **ICD 编码推荐**：LLM 根据疾病名称推荐 ICD-10/ICD-9-CM-3 编码
- **编码校验**：检查编码完整性和逻辑一致性
- **编码库搜索**：全文搜索 ICD 编码（支持中文分词）

### 3.2.2 自动入组预测
- **DRG 分组预测**：调用 OpenDRG 引擎进行分组
- **费用预测**：预估 DRG 基准支付金额
- **分组历史**：追踪分组版本变更

### 3.3 事中监控
- **实时预警**：费用超标、住院日过长等预警
- **编码优化建议**：LLM 分析病历后给出的建议

### 3.4 事后分析
- **盈亏分析**：对比基准支付与实际费用
- **DRG 绩效统计**：医生/科室维度的 DRG 绩效

---

## 架构设计

### 技术栈

```
前端：Vue 3 + TypeScript + Ant Design Vue
后端：Python FastAPI
数据库：Supabase (PostgreSQL)
分组引擎：OpenDRG
LLM：DeepSeek-V3 (阿里云百炼)
```

### 数据流

```
┌─────────────┐       ┌─────────────┐       ┌─────────────┐
│   编码员    │──────▶│  病案首页   │──────▶│ OpenDRG     │
│   (人工编码) │       │ (ICD编码)   │       │ (分组引擎)  │
└─────────────┘       └─────────────┘       └─────────────┘
                            │                       │
                            │                       ▼
                            │               ┌─────────────┐
                            │               │ DRG分组结果 │
                            │               │ (ADRG/DRG)  │
                            │               └─────────────┘
                            ▼
                    ┌─────────────┐
                    │ LLM分析     │
                    │ (编码建议)  │
                    └─────────────┘
```

**关键理解**：
- DRG 分组的数据来源是**病案首页**（编码员已完成 ICD 编码）
- LLM 的作用是**辅助编码员**，而非自动编码
- 编码员仍然是编码质量的最终责任人

---

## 快速开始

### 1. 环境配置

复制环境变量文件：

```bash
cp .env.example .env
```

编辑 `.env` 文件，配置以下变量：

```bash
# Supabase 配置
VITE_SUPABASE_URL=https://your-project-id.supabase.co
VITE_SUPABASE_ANON_KEY=your-supabase-anon-key

# DRG 模块配置
VITE_USE_DRG_MOCK=true          # 开发阶段使用 Mock 数据
VITE_DRG_DEFAULT_REGION=sichuan # DRG 地区版本

# LLM 配置（编码辅助）
VITE_DEEPSEEK_API_KEY=your-api-key
VITE_DEEPSEEK_API_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
VITE_DEEPSEEK_MODEL=deepseek-v3
```

### 2. 使用 Mock 数据快速开发（推荐）

如果你想立即开始前端开发，无需等待数据库设置：

```bash
# 1. 安装依赖
npm install

# 2. 启动开发服务器
npm run dev

# 3. 访问 DRG 模块
# http://localhost:5173/drg
```

此时系统会使用 Mock 数据（`src/data/drg/mock-*.ts`），无需真实数据库。

---

## 数据库设置

### 步骤 1：创建 DRG 表

**方式 A：在 Supabase Dashboard 执行（推荐）**

1. 打开 Supabase Dashboard: https://app.supabase.com/
2. 进入你的项目 → SQL Editor
3. 复制 `scripts/migrations/create-drg-tables.sql` 的内容
4. 粘贴并执行

**方式 B：使用命令行（需配置环境变量）**

```bash
npm run db:init-drg
```

此命令会显示 SQL 文件内容和执行说明。

### 步骤 2：验证表结构

```bash
npm run db:verify-drg
```

此脚本会检查：
- ✅ 所有 8 张表是否存在
- ✅ 外键约束是否生效
- ✅ 触发器是否正常工作

### 步骤 3：导入 ICD 编码数据

**开发/测试环境（使用 Mock 数据）**

```bash
npm run db:import-icd mock
```

这会导入 Mock 数据中的 ICD-10 和 ICD-9-CM-3 编码（约 14 条）。

**生产环境（使用真实数据）**

准备 JSON 文件（格式见下方），然后运行：

```bash
npm run db:import-icd json path/to/icd10.json path/to/icd9.json
```

JSON 文件格式示例：

```json
[
  {
    "code": "I21.001",
    "name": "急性前壁ST段抬高型心肌梗死",
    "category": "循环系统疾病",
    "notes": "限于有ST段抬高的急性前壁心肌梗死",
    "includes": ["急性前壁心肌梗死伴ST段抬高"],
    "excludes": ["陈旧性心肌梗死(I25.2)"],
    "is_active": true
  }
]
```

### 创建的表结构

| 表名 | 说明 | 行数（初始） |
|------|------|--------------|
| `case_front_page` | 病案首页主表 | 0 |
| `case_front_page_diagnoses` | 次诊断关联表 | 0 |
| `case_front_page_procedures` | 手术操作关联表 | 0 |
| `drg_groupings` | DRG 分组结果表 | 0 |
| `coding_suggestions` | 编码建议表 | 0 |
| `drg_alerts` | 预警记录表 | 0 |
| `icd10_codes` | ICD-10 编码库 | 9（Mock）/ 数千（生产） |
| `icd9_procedures` | ICD-9-CM-3 编码库 | 5（Mock）/ 数千（生产） |

---

## 开发模式

### Mock 数据模式（前后端分离开发）

**适用场景**：
- 前端开发，后端 API 尚未完成
- 快速原型验证
- 单元测试

**配置**：

```bash
# .env
VITE_USE_DRG_MOCK=true
```

**工作原理**：

所有 API 调用会被 `src/api/drg.ts` 拦截，返回 Mock 数据：

```typescript
// src/api/drg.ts
const USE_MOCK_DATA = import.meta.env.VITE_USE_DRG_MOCK === 'true'

export async function getCaseFrontPages() {
  if (USE_MOCK_DATA) {
    return Promise.resolve(mockCaseFrontPages)
  }
  // TODO: 调用真实 API
  const response = await fetch('/api/v1/case-front-page')
  return response.json()
}
```

**优点**：
- ✅ 无需等待后端开发
- ✅ 无需配置数据库
- ✅ 数据结构与真实 API 完全一致
- ✅ 随时可切换到真实 API（修改环境变量即可）

### 真实 API 模式

**配置**：

```bash
# .env
VITE_USE_DRG_MOCK=false
VITE_API_BASE_URL=http://localhost:8001  # FastAPI 后端地址
```

此时所有 API 调用会走真实的 FastAPI 后端。

---

## 生产部署

### 1. 数据库准备

```bash
# 1. 在 Supabase 执行建表 SQL
# 2. 导入完整的 ICD 编码数据
npm run db:import-icd json icd10.json icd9.json

# 3. 验证
npm run db:verify-drg
```

### 2. 后端部署（FastAPI）

```bash
cd backend-fastapi
pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 8001
```

### 3. 前端构建

```bash
# .env.production
VITE_USE_DRG_MOCK=false
VITE_API_BASE_URL=https://api.yourdomain.com

npm run build
npm run preview  # 本地预览
```

### 4. 配置 OpenDRG

后端需集成 OpenDRG：

```python
# backend-fastapi/app/services/drg_service.py
from opendrg import DRGGrouper

grouper = DRGGrouper(region='sichuan')
result = grouper.group(
    primary_diagnosis='I21.001',
    secondary_diagnoses=['I10.x01', 'E11.901'],
    procedures=['36.0700']
)
```

---

## API 文档

### 3.2.1 编码辅助 API

#### 1. ICD 编码推荐

```http
POST /api/v1/coding/suggest
Content-Type: application/json

{
  "diagnosis_name": "急性心肌梗死",
  "context": "患者突发胸痛，心电图示前壁ST段抬高...",
  "category": "diagnosis"
}
```

**响应**：

```json
{
  "candidates": [
    {
      "code": "I21.001",
      "name": "急性前壁ST段抬高型心肌梗死",
      "confidence": 0.92,
      "note": "建议确认部位和ST段变化"
    }
  ]
}
```

#### 2. 编码校验

```http
POST /api/v1/coding/validate
Content-Type: application/json

{
  "admission_id": "ADM20250104001",
  "primary_diagnosis": {
    "code": "I21.001",
    "name": "急性前壁ST段抬高型心肌梗死"
  },
  "secondary_diagnoses": [
    { "code": "I10.x01", "name": "高血压3级" }
  ],
  "procedures": [
    { "code": "36.0700", "name": "经皮冠状动脉介入术" }
  ]
}
```

**响应**：

```json
{
  "is_valid": true,
  "warnings": [
    {
      "type": "missing_diagnosis",
      "message": "病程记录中提到'心力衰竭'，建议补充次诊断",
      "evidence": "病程记录第3天：患者出现呼吸困难...",
      "severity": "info"
    }
  ],
  "conflicts": []
}
```

### 3.2.2 DRG 分组 API

#### DRG 入组预测

```http
POST /api/v1/drg/predict
Content-Type: application/json

{
  "admission_id": "ADM20250104001",
  "region": "sichuan"
}
```

**响应**：

```json
{
  "data": {
    "adrg_code": "FB1",
    "adrg_name": "急性心肌梗死",
    "drg_code": "FB19",
    "drg_name": "急性心肌梗死伴严重合并症",
    "weight": 2.8653,
    "baseline_payment": 42000.00,
    "expected_los": { "min": 10, "max": 15 },
    "confidence": 0.89,
    "risk_level": "high",
    "grouping_logic": "主诊断 FB1 + 合并症（高血压、糖尿病）"
  }
}
```

---

## 常见问题

### Q1: Mock 数据和真实 API 如何切换？

修改 `.env` 文件中的 `VITE_USE_DRG_MOCK`：

```bash
# 使用 Mock 数据
VITE_USE_DRG_MOCK=true

# 使用真实 API
VITE_USE_DRG_MOCK=false
```

重启开发服务器即可生效。

### Q2: 如何获取 ICD-10 和 ICD-9-CM-3 完整数据？

**官方数据源**：
- ICD-10 国家临床版 2.0：国家卫健委官网
- ICD-9-CM-3：中国医院协会病案管理专业委员会

**数据格式转换**：
- 如果是 Excel 格式，可使用 Python 脚本转换为 JSON
- 参考 `scripts/migrations/import-icd-codes.ts` 中的数据格式

### Q3: 表创建失败怎么办？

**检查步骤**：

1. 验证 Supabase 连接：
   ```bash
   npm run db:verify-drg
   ```

2. 检查是否有权限问题（需要 `service_role` 权限创建表）

3. 在 Supabase Dashboard SQL Editor 中手动执行：
   ```sql
   -- 复制 scripts/migrations/create-drg-tables.sql 内容
   ```

### Q4: 如何集成 OpenDRG？

OpenDRG 是 Python 库，需要在 FastAPI 后端集成：

```bash
pip install opendrg
```

参考文档：https://github.com/xxxxxx/opendrg

### Q5: LLM 编码建议的质量如何保证？

**多层把关**：
1. LLM 给出建议（带置信度）
2. 编码员人工审核
3. 质控员二次审核
4. 编码建议记录可追溯

**LLM 仅作为辅助工具，最终编码质量由人工保证**。

---

## 下一步

1. ✅ 完成数据库设置
2. ⏳ 开发 FastAPI 后端 API
3. ⏳ 集成 OpenDRG 分组引擎
4. ⏳ 开发前端 Vue 组件
5. ⏳ 集成 LLM 编码辅助
6. ⏳ 端到端测试

---

## 相关文档

- [DRG PRD 文档](../PRD-DRG.md)
- [API 接口文档](./API.md)
- [OpenDRG 文档](https://github.com/xxxxxx/opendrg)
- [DeepSeek API 文档](https://www.deepseek.com/docs)

---

**最后更新**：2025-01-04
**维护者**：医疗质控系统开发团队
