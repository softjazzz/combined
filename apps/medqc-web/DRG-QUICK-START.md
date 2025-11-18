# DRG 模块快速开始 🚀

> **5 分钟快速上手 DRG/DIP 模块开发**

## ✅ 已完成的工作

我已经为您创建了完整的 DRG 模块基础设施：

1. ✅ **Mock 数据**（3个文件）- 支持无后端前端开发
2. ✅ **API 适配层**（1个文件）- 一键切换 Mock/真实 API
3. ✅ **数据库脚本**（4个文件）- 完整的建表、验证、导入工具
4. ✅ **文档**（3个文件）- 完整的设置指南和实现状态
5. ✅ **npm 脚本**（3个命令）- 一键执行工具

---

## 🎯 三种开发模式

### 模式 1️⃣：纯前端开发（无需数据库，推荐新手）

```bash
# 1. 配置环境变量
echo "VITE_USE_DRG_MOCK=true" >> .env

# 2. 启动开发服务器
npm run dev

# 3. 开始开发 Vue 组件
# 所有 API 调用会自动返回 Mock 数据！
```

**适用场景**：
- ✅ 前端开发者
- ✅ 快速原型验证
- ✅ 后端 API 尚未完成
- ✅ 学习 Vue 3 组件开发

---

### 模式 2️⃣：前端 + 数据库（有 Supabase）

```bash
# 1. 运行建表辅助脚本
npm run db:init-drg

# 2. 在 Supabase Dashboard 中执行 SQL
#    复制 scripts/migrations/create-drg-tables.sql 内容
#    → SQL Editor → 粘贴 → Run

# 3. 验证表是否创建成功
npm run db:verify-drg

# 4. 导入测试 ICD 编码数据
npm run db:import-icd mock

# 5. 启动开发服务器
npm run dev
```

**适用场景**：
- ✅ 有 Supabase 账号
- ✅ 想测试真实数据库交互
- ✅ 开发需要持久化的功能

---

### 模式 3️⃣：全栈开发（前端 + 后端 + 数据库）

```bash
# 1. 完成模式 2 的所有步骤

# 2. 修改环境变量使用真实 API
echo "VITE_USE_DRG_MOCK=false" >> .env

# 3. 开始开发 FastAPI 后端
#    参考文档：docs/DRG-SETUP.md

# 4. 启动后端服务
cd backend-fastapi
uvicorn app.main:app --reload --port 8001

# 5. 启动前端开发服务器
npm run dev
```

**适用场景**：
- ✅ 全栈开发者
- ✅ 准备生产部署
- ✅ 需要集成 OpenDRG 和 LLM

---

## 📁 重要文件位置

### Mock 数据（前端开发必看）

```
src/data/drg/
├── mock-case-front-page.ts    # 病案首页数据（2个案例）
├── mock-drg-grouping.ts        # DRG分组结果（2个案例）
└── mock-icd-codes.ts           # ICD编码库（14个编码）
```

### API 服务（前端调用入口）

```
src/api/
└── drg.ts                      # 所有 DRG API 接口
```

使用示例：

```typescript
import { drgApi } from '@/api/drg'

// 获取病案首页列表
const cases = await drgApi.getCaseFrontPages()

// ICD 编码推荐
const suggestions = await drgApi.suggestCoding({
  diagnosis_name: '急性心肌梗死',
  category: 'diagnosis'
})

// DRG 入组预测
const result = await drgApi.predictDRGGrouping({
  admission_id: 'ADM20250104001',
  region: 'sichuan'
})
```

### 数据库脚本

```
scripts/migrations/
├── create-drg-tables.sql       # 建表 SQL（8张表）
├── create-drg-tables.ts        # 建表辅助脚本
├── verify-drg-tables.ts        # 验证脚本
└── import-icd-codes.ts         # ICD 编码导入
```

### 文档

```
docs/
├── DRG-SETUP.md                      # 完整设置指南（必读）
└── DRG-IMPLEMENTATION-STATUS.md      # 实现进度和待办任务
```

---

## 🛠️ npm 脚本命令

```bash
# 数据库相关
npm run db:init-drg        # 显示建表 SQL 和执行说明
npm run db:verify-drg      # 验证表是否正确创建
npm run db:import-icd mock # 导入 Mock ICD 编码数据

# 开发相关
npm run dev                # 启动开发服务器
npm run build              # 构建生产版本
npm run type-check         # TypeScript 类型检查
```

---

## 🎨 开始开发 Vue 组件

### 1. 创建路由（如果还没有）

编辑 `src/router/index.ts`：

```typescript
{
  path: '/drg',
  name: 'DRG',
  children: [
    {
      path: 'coding',
      name: 'CodingAssistant',
      component: () => import('@/views/drg/CodingAssistant.vue')
    },
    {
      path: 'grouping',
      name: 'GroupingPredict',
      component: () => import('@/views/drg/GroupingPredict.vue')
    }
  ]
}
```

### 2. 创建第一个 DRG 页面

创建 `src/views/drg/CodingAssistant.vue`：

```vue
<script setup lang="ts">
import { ref } from 'vue'
import { drgApi } from '@/api/drg'

const diagnosisName = ref('')
const suggestions = ref([])

async function getSuggestions() {
  suggestions.value = await drgApi.suggestCoding({
    diagnosis_name: diagnosisName.value,
    category: 'diagnosis'
  })
}
</script>

<template>
  <div class="coding-assistant">
    <h1>ICD 编码辅助</h1>

    <a-input
      v-model:value="diagnosisName"
      placeholder="输入诊断名称，例如：急性心肌梗死"
      @press-enter="getSuggestions"
    />

    <a-button type="primary" @click="getSuggestions">
      推荐编码
    </a-button>

    <a-table
      :dataSource="suggestions"
      :columns="[
        { title: 'ICD编码', dataIndex: 'code' },
        { title: '诊断名称', dataIndex: 'name' },
        { title: '置信度', dataIndex: 'confidence' }
      ]"
    />
  </div>
</template>
```

### 3. 访问页面

启动开发服务器后，访问：

```
http://localhost:5173/drg/coding
```

---

## 🔧 环境变量配置

创建 `.env` 文件（复制 `.env.example`）：

```bash
# Supabase 配置（如果使用数据库）
VITE_SUPABASE_URL=https://your-project-id.supabase.co
VITE_SUPABASE_ANON_KEY=your-anon-key

# DRG 模块配置
VITE_USE_DRG_MOCK=true              # true=Mock, false=真实API
VITE_DRG_DEFAULT_REGION=sichuan     # 四川版本

# LLM 配置（如果需要编码辅助）
VITE_DEEPSEEK_API_KEY=your-api-key
VITE_DEEPSEEK_API_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
VITE_DEEPSEEK_MODEL=deepseek-v3
```

---

## 📖 Mock 数据说明

### 病案 1：急性心肌梗死（完整案例）

```typescript
{
  admission_id: 'ADM20250104001',
  patient_name: '张三',
  patient_age: 65,
  patient_gender: 'M',

  // 主诊断
  primary_diagnosis_code: 'I21.001',
  primary_diagnosis_name: '急性前壁ST段抬高型心肌梗死',

  // 主手术
  main_procedure_code: '36.0700',
  main_procedure_name: '经皮冠状动脉介入术',

  // 次诊断（3个）
  diagnoses: [
    { code: 'I10.x01', name: '高血压3级（极高危）' },
    { code: 'E11.901', name: '2型糖尿病' },
    { code: 'I50.001', name: '心力衰竭', is_complication: true }
  ],

  // DRG 分组结果
  drg_code: 'FB19',
  drg_name: '急性心肌梗死伴严重合并症',
  weight: 2.8653,
  baseline_payment: 42000.00
}
```

### 病案 2：肺炎（简单案例）

```typescript
{
  admission_id: 'ADM20250104002',
  patient_name: '李四',
  primary_diagnosis_code: 'J18.901',
  primary_diagnosis_name: '肺炎，未特指病原体',
  drg_code: 'RB13',
  weight: 1.2341
}
```

---

## 🐛 常见问题

### Q1: API 调用返回空数据？

检查 `.env` 文件中的 `VITE_USE_DRG_MOCK` 是否为 `true`。

### Q2: TypeScript 类型错误？

运行类型检查：
```bash
npm run type-check
```

### Q3: 表创建失败？

1. 检查 Supabase 连接
2. 验证权限（需要创建表的权限）
3. 在 Dashboard 手动执行 SQL

### Q4: Mock 数据不够用？

编辑 `src/data/drg/mock-*.ts` 文件，添加更多测试数据。

---

## 📞 下一步

### 完成前端开发后

1. 阅读后端开发指南：`docs/DRG-SETUP.md` → "生产部署" 章节
2. 开发 FastAPI 后端 API
3. 集成 OpenDRG 分组引擎
4. 集成 DeepSeek LLM
5. 修改 `.env` 切换到真实 API：`VITE_USE_DRG_MOCK=false`

### 需要帮助？

- 📖 查看完整文档：`docs/DRG-SETUP.md`
- 📊 查看实现进度：`docs/DRG-IMPLEMENTATION-STATUS.md`
- 🔍 检查 Mock 数据：`src/data/drg/mock-*.ts`
- 🛠️ 查看 API 接口：`src/api/drg.ts`

---

**创建时间**：2025-01-04
**适用版本**：medqc-web v1.0.0
**维护者**：医疗质控系统开发团队

🎉 **祝开发顺利！**
