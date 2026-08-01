# 客户样本验证前端技术债收口 Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use `executing-plans` to implement this plan task-by-task.

**Goal:** 在不改变后端、质控合同和客户结果语义的前提下，消除重复的质控任务中心，并将两个超过一万行的 Vue 文件按真实职责 seam 逐批拆分。

**Architecture:** 保持现有客户链路 `同步病例 → Bundle → Native → Canonical Envelope → 保存 → 单一结果 API → 前端渲染` 不变。先把当前质控任务从右侧历史面板中独立出来，再删除重复历史 UI；随后一次只移动一个已有视觉/交互区块，父页面继续拥有请求、任务生命周期和结果状态权威逻辑。

**Tech Stack:** Vue 3、TypeScript、Ant Design Vue、Vitest、Vite。

---

## 1. 重新评估结论

### 1.1 当前证据

- `src/views/workstation-v4/CustomerSampleValidationView.vue` 共 11,244 行：模板 2,048 行、脚本 5,655 行、样式 3,539 行。
- `src/views/workstation-v4/semantic-rules/components/SemanticRulesBatchResultDrawer.vue` 共 10,144 行：模板 2,402 行、脚本 3,968 行、样式 3,772 行。
- 当前右侧“质控任务中心”同时承载当前任务和历史记录，但历史记录已有独立页面：
  - `src/views/workstation-v4/customer-sample-validation/CustomerSampleTaskHistoryView.vue`
  - 路由名 `WorkstationV4CustomerSampleValidationTasks`
- 当前任务轮询依赖 `taskHistoryOpen`。侧栏关闭后轮询停止，说明任务生命周期错误地依赖展示面板是否打开。
- 主页面和独立历史页分别维护任务状态文案与统计，已经出现数组型/对象型 `status_breakdown` 处理不一致。
- `SemanticRulesBatchResultDrawer.vue` 被三个入口复用，任何改动都会同时影响客户样本页、独立任务历史页和终末病历页。
- 结果 Drawer 当前聚焦测试实际为 23/25 通过，两个失败分别是：
  - 原生任务缺少测试期望的“本次执行质控点数”。
  - `LX0609-018` 的现有受控结论文案与旧断言不一致。

### 1.2 根因判断

当前主要技术债不是“缺少新架构”，而是三个职责混合问题：

1. 任务执行状态和任务历史 UI 混在同一面板，生命周期被 UI 开关控制。
2. 页面级请求、轮询、展示格式、弹窗和大段样式堆在单个 Vue 文件，修改局部功能需要理解整页。
3. 结果 Drawer 将结果来源选择、状态归类、排序、证据转换和视觉区块放在同一文件中；其中状态与证据逻辑属于高风险权威实现，不能与纯结构拆分同时修改。

### 1.3 技术决策

- 不重写两个页面。
- 不引入 Pinia、全局任务 Store 或新的统一任务框架。
- 不修改后端、数据库、API DTO、Canonical Envelope 或结果状态合同。
- 不以“文件必须降到多少行”为完成标准。
- 一次只处理一个 seam，每批独立测试、独立提交、可单独回滚。
- 第一阶段只处理 `CustomerSampleValidationView.vue`；其行为稳定后才允许处理结果 Drawer。

---

## 2. 目标结构

```text
CustomerSampleValidationView.vue
├── CustomerSampleQcTaskStatusBar.vue   当前/最新任务，主区域常驻
├── CustomerSampleTaskHistoryView.vue   独立历史页面，继续复用
├── batchJobPresentation.ts             两个调用方共享的任务展示归一
├── LuxianRuleScopePanel.vue             后续机械抽离
└── 页面继续拥有请求、轮询、结果 Drawer 和业务状态协调

SemanticRulesBatchResultDrawer.vue
├── BatchResultTraceModal.vue            纯诊断追踪弹窗
├── BatchResultOverview.vue              已计算好的结果总览
└── BatchResultAdvancedDiagnostics.vue   高级诊断整体区块
```

核心结果主体、Canonical 结果选择、状态归一、业务排序、事实和证据模型仍保留在现有权威位置。

---

## 3. 实施边界

### 本阶段做

1. 主区域新增紧凑的当前任务状态条。
2. 删除右侧重复的任务中心和历史任务列表。
3. 顶部“质控记录”直接进入独立历史页面。
4. 任务轮询改为由“是否存在运行中任务”控制。
5. 统一主状态条和历史页面的纯展示格式。
6. 机械抽离一个样本页低风险区块。
7. 在结果 Drawer 测试恢复绿色后，机械抽离三个纯展示区块。

### 本阶段不做

- 不拆后端巨型脚本。
- 不修改同步、Bundle、Native、Envelope、保存或单一结果 API。
- 不重写任务状态模型。
- 不重新设计结果 UI、状态颜色或客户文案。
- 不把结果解释逻辑分散到子模块。
- 不统一整个项目 CSS。
- 不处理与本计划无关的规则准确率、客户 pending 口径或发布打包。

---

## 4. 实施任务

### Task 0：冻结当前行为和修复红色基线

**Files:**

- Modify: `tests/unit/views/workstation-v4/CustomerSampleValidationView.spec.ts`
- Modify if product behavior is correct: `tests/unit/views/workstation-v4/semantic-rules/SemanticRulesBatchResultDrawer.spec.ts`
- Modify only if test reveals a real defect: `src/views/workstation-v4/semantic-rules/components/SemanticRulesBatchResultDrawer.vue`

**Step 1：记录当前失败**

运行：

```powershell
npm run test:unit -- tests/unit/views/workstation-v4/semantic-rules/SemanticRulesBatchResultDrawer.spec.ts --run
```

当前预期：23/25 通过，保留两条失败证据。

**Step 2：逐条判定是产品缺陷还是旧断言**

- “本次执行质控点数”若属于仍需展示的客户信息，补回展示；否则更新过期断言并记录原因。
- `LX0609-018` 以当前受控解释合同为准，只更新精确文案断言，不放宽为通用 `contains('不合规')`。

**Step 3：补任务生命周期基线测试**

在 `CustomerSampleValidationView.spec.ts` 固定以下行为：

- 创建任务后能看到运行中状态。
- 当前任务可查看实时结果、停止质控。
- 任务到达完成、失败、取消状态后停止轮询。
- 结果入口继续调用现有 `openBatchJob` 链路。
- 独立历史页面仍可查看、复核和导出结果。

**Step 4：验证**

```powershell
npm run test:unit -- tests/unit/views/workstation-v4/semantic-rules/SemanticRulesBatchResultDrawer.spec.ts tests/unit/views/workstation-v4/CustomerSampleValidationView.spec.ts --run
```

预期：相关测试全部通过。基线未绿色前，不进入 Task 1。

**Step 5：提交**

```powershell
git add tests/unit/views/workstation-v4/CustomerSampleValidationView.spec.ts tests/unit/views/workstation-v4/semantic-rules/SemanticRulesBatchResultDrawer.spec.ts
git commit -m "稳定客户样本任务与结果展示测试基线"
```

---

### Task 1：建立主区域当前任务深模块

**Files:**

- Create: `src/views/workstation-v4/customer-sample-validation/CustomerSampleQcTaskStatusBar.vue`
- Create: `tests/unit/views/workstation-v4/customer-sample-validation/CustomerSampleQcTaskStatusBar.spec.ts`
- Modify: `src/views/workstation-v4/CustomerSampleValidationView.vue`
- Modify: `tests/unit/views/workstation-v4/CustomerSampleValidationView.spec.ts`

**Step 1：先写状态条失败测试**

覆盖：

- 无任务时不渲染空卡片。
- `queued/running/completed/failed/canceled` 显示客户可读状态。
- 显示病历进度、结果回写、更新时间和必要状态计数。
- 运行中发出 `view-result`、`cancel`、`open-history`。
- 完成后发出 `view-result`、`review`、`export`、`open-history`。

**Step 2：定义小接口**

状态条只接收任务和动作状态，不接收原始 Envelope：

```ts
const props = defineProps<{
  task: SichuanBatchJob | null
  loading?: boolean
  canceling?: boolean
  reviewing?: boolean
}>()

const emit = defineEmits<{
  'view-result': [jobId: string]
  cancel: [jobId: string]
  review: [jobId: string]
  export: [jobId: string]
  'open-history': []
}>()
```

模块内部隐藏任务状态文案、进度和摘要渲染；父页面仍负责所有请求和副作用。

**Step 3：在主区域接入**

放置在现有同步状态条附近、病历池列表之前。保留现有处理函数：

- `openBatchJob`
- `confirmCancelBatchJob`
- `handleReviewTaskHistoryJob`
- `handleExportTaskHistoryJob`

**Step 4：聚焦验证**

```powershell
npm run test:unit -- tests/unit/views/workstation-v4/customer-sample-validation/CustomerSampleQcTaskStatusBar.spec.ts tests/unit/views/workstation-v4/CustomerSampleValidationView.spec.ts --run
```

**Step 5：提交**

```powershell
git add src/views/workstation-v4/customer-sample-validation/CustomerSampleQcTaskStatusBar.vue src/views/workstation-v4/CustomerSampleValidationView.vue tests/unit/views/workstation-v4/customer-sample-validation/CustomerSampleQcTaskStatusBar.spec.ts tests/unit/views/workstation-v4/CustomerSampleValidationView.spec.ts
git commit -m "将当前质控任务迁入样本池主区域"
```

---

### Task 2：解耦任务轮询并删除右侧任务中心

**Files:**

- Modify: `src/views/workstation-v4/CustomerSampleValidationView.vue`
- Modify: `tests/unit/views/workstation-v4/CustomerSampleValidationView.spec.ts`
- Create: `tests/unit/views/workstation-v4/customer-sample-validation/CustomerSampleTaskHistoryView.spec.ts`

**Step 1：写失败测试**

覆盖：

- 当前任务轮询不依赖任何面板打开状态。
- 当前样本池存在 `latest_job_id` 时恢复其最新任务。
- 切换样本池后状态条切换到对应样本池任务。
- 顶部“查看质控记录”直接路由到 `WorkstationV4CustomerSampleValidationTasks`。
- 页面不再渲染“质控任务中心”或内嵌历史列表。
- 独立历史页面可查询、打开结果、复核和导出。

**Step 2：替换任务状态**

- 将 `taskHistoryOpen`、`runningTaskCenterJob`、`currentTaskCenterJob` 收敛为当前池的 `currentQcTask`。
- 将 `openTaskCenterForJob(jobId)` 改为只加载并跟踪该任务。
- 轮询开始条件改为 `currentQcTask` 为运行态，终态或卸载时停止。
- 打开结果 Drawer 时避免同一任务出现两个轮询器；关闭 Drawer 后若任务仍运行，再恢复主状态条轮询。

**Step 3：删除重复 UI**

- 删除模板中的右侧 `<aside class="customer-sample-task-center">`。
- 删除双栏布局、任务中心和内嵌历史列表专属样式。
- 删除“展开/收起任务中心”逻辑。
- 将任务创建提示改为“任务已创建，正在执行质控”。

**Step 4：验证请求行为**

测试必须证明：

- 每个运行中 job 同时最多一个详情轮询器。
- 轮询周期保持现有值，不引入更高请求频率。
- 任务终态只触发一次病历池和列表刷新。
- 不修改任何请求参数、结果 DTO 或后端接口。

**Step 5：运行测试并提交**

```powershell
npm run test:unit -- tests/unit/views/workstation-v4/CustomerSampleValidationView.spec.ts tests/unit/views/workstation-v4/customer-sample-validation/CustomerSampleTaskHistoryView.spec.ts --run
git add src/views/workstation-v4/CustomerSampleValidationView.vue tests/unit/views/workstation-v4/CustomerSampleValidationView.spec.ts tests/unit/views/workstation-v4/customer-sample-validation/CustomerSampleTaskHistoryView.spec.ts
git commit -m "删除重复质控任务中心并保留独立历史入口"
```

---

### Task 3：统一任务展示归一，消除主页面和历史页漂移

**Files:**

- Create: `src/views/workstation-v4/customer-sample-validation/batchJobPresentation.ts`
- Create: `tests/unit/views/workstation-v4/customer-sample-validation/batchJobPresentation.spec.ts`
- Modify: `src/views/workstation-v4/customer-sample-validation/CustomerSampleQcTaskStatusBar.vue`
- Modify: `src/views/workstation-v4/customer-sample-validation/CustomerSampleTaskHistoryView.vue`

**Step 1：写纯函数失败测试**

至少覆盖：

- `status_breakdown` 为对象和数组两种返回形态。
- 规则范围、病历数、结果回写数和更新时间。
- 不合规、AI 判断、数据不足、不适用、合规、技术异常。
- 缺字段时给出中性回退，不伪造“排队中”或合规结果。

**Step 2：建立唯一展示归一模块**

该模块只读取任务 DTO 并返回展示模型，不发请求、不读取 Envelope、不改变任务状态。

**Step 3：替换两处重复实现**

主状态条和独立历史页共同调用该模块；删除各自重复的状态统计、摘要和文案函数。

**Step 4：验证并提交**

```powershell
npm run test:unit -- tests/unit/views/workstation-v4/customer-sample-validation/batchJobPresentation.spec.ts tests/unit/views/workstation-v4/customer-sample-validation/CustomerSampleQcTaskStatusBar.spec.ts tests/unit/views/workstation-v4/customer-sample-validation/CustomerSampleTaskHistoryView.spec.ts --run
git add src/views/workstation-v4/customer-sample-validation/batchJobPresentation.ts src/views/workstation-v4/customer-sample-validation/CustomerSampleQcTaskStatusBar.vue src/views/workstation-v4/customer-sample-validation/CustomerSampleTaskHistoryView.vue tests/unit/views/workstation-v4/customer-sample-validation
git commit -m "统一质控任务展示归一逻辑"
```

**阶段停止点：** Task 3 完成后先停止。确认主页面、独立历史页和结果入口稳定，再决定是否继续拆样本页面其他区域。

---

### Task 4：机械抽离样本页的一个低风险区块

**Files:**

- Create: `src/views/workstation-v4/customer-sample-validation/LuxianRuleScopePanel.vue`
- Create: `tests/unit/views/workstation-v4/customer-sample-validation/LuxianRuleScopePanel.spec.ts`
- Modify: `src/views/workstation-v4/CustomerSampleValidationView.vue`
- Modify: `tests/unit/views/workstation-v4/CustomerSampleValidationView.spec.ts`

**Step 1：只迁移泸县规则范围区块**

迁移当前模板中“泸县0609质控点范围”及其专属样式。父页面继续拥有：

- 规则目录加载。
- 已选择规则 ID。
- 任务创建参数。
- URL、样本池和运行模式状态。

子模块只接收规则族、选择状态和显示文案，通过事件报告全选、清空、展开和勾选动作。

**Step 2：停止条件**

如果抽离需要同时移动请求、任务创建、共享 Store 或超过 10 个互相依赖的独立 props，则停止 Task 4，不为追求行数继续扩范围。

**Step 3：验证**

```powershell
npm run test:unit -- tests/unit/views/workstation-v4/customer-sample-validation/LuxianRuleScopePanel.spec.ts tests/unit/views/workstation-v4/CustomerSampleValidationView.spec.ts --run
```

验证选中规则 ID、执行数量和任务请求参数与拆分前一致。

**Step 4：提交**

```powershell
git add src/views/workstation-v4/customer-sample-validation/LuxianRuleScopePanel.vue src/views/workstation-v4/CustomerSampleValidationView.vue tests/unit/views/workstation-v4/customer-sample-validation/LuxianRuleScopePanel.spec.ts tests/unit/views/workstation-v4/CustomerSampleValidationView.spec.ts
git commit -m "抽离泸县质控范围展示模块"
```

---

### Task 5：受控拆分结果 Drawer 的纯展示区块

**前置条件：** Task 0–4 稳定，且 Drawer 聚焦测试 25/25 通过。

**Files:**

- Modify: `src/views/workstation-v4/semantic-rules/components/SemanticRulesBatchResultDrawer.vue`
- Create: `src/views/workstation-v4/semantic-rules/components/BatchResultTraceModal.vue`
- Create: `src/views/workstation-v4/semantic-rules/components/BatchResultOverview.vue`
- Create: `src/views/workstation-v4/semantic-rules/components/BatchResultAdvancedDiagnostics.vue`
- Modify: `tests/unit/views/workstation-v4/semantic-rules/SemanticRulesBatchResultDrawer.spec.ts`
- Create: corresponding focused specs beside the existing Drawer spec

**Step 1：先抽诊断追踪 Modal**

- 只迁移现有诊断追踪模板和对应 scoped CSS。
- 子模块接收 `open/loading/error/sections`，只发出 `close`。
- 请求和 trace 转换仍由父 Drawer 管理。
- 聚焦测试通过后独立提交。

**Step 2：再抽结果总览**

- 只迁移已经计算好的任务/结果总览。
- 子模块不读取原始 Envelope，不调用 `normalizeCustomerQcResult`。
- 取消、导出、复核等 Header 操作暂时保留在父 Drawer。
- 聚焦测试通过后独立提交。

**Step 3：最后抽高级诊断整体区块**

- 高级诊断作为一个模块迁移，不继续拆成多个浅模块。
- 接收父 Drawer 已计算好的表格、聚合和 debug 模型。
- 筛选、分页和操作通过事件返回父 Drawer。
- 聚焦测试通过后独立提交。

**绝对禁止移动的代码：**

- Canonical 顶层结果优先选择逻辑。
- 非 LX0609 兼容映射。
- 状态规范化和业务排序。
- `normalizeCustomerQcResult`。
- `buildCustomerQcDisplayModel`。
- 事实、证据和原文定位转换。
- 业务结果主体和深度复核 Modal。

**Step 4：验证三个调用入口**

必须覆盖：

- `CustomerSampleValidationView.vue`
- `CustomerSampleTaskHistoryView.vue`
- `FinalRecordsView.vue`

三处 props、关闭行为、结果读取、导出、复核和取消行为保持不变。

---

### Task 6：最终质量门禁和差异审查

**Files:**

- Modify only if a real defect is found: files already listed above

**Step 1：逐批检查 diff**

```powershell
git diff --check
git diff -- src/views/workstation-v4/CustomerSampleValidationView.vue
git diff -- src/views/workstation-v4/semantic-rules/components/SemanticRulesBatchResultDrawer.vue
```

重点确认没有夹带：后端修改、结果合同修改、状态文案改写、请求参数变化或 `components.d.ts`。

**Step 2：运行完整前端门禁**

只在全部功能批次完成后运行一次：

```powershell
npm run check:encoding
npm run lint
npm run type-check
npm run test:unit
```

**Step 3：行为验收**

- 任务创建后主区域立即出现当前任务。
- 不打开任何侧栏也持续更新进度。
- 完成后可直接查看结果。
- 历史记录进入独立页面。
- 样本页不再出现右侧任务中心，也不因其展开而缩窄。
- Canonical Envelope 的读取、状态、排序、事实和证据展示完全不变。
- 结果 Drawer 三个入口全部正常。

**Step 4：最终提交**

```powershell
git add <本计划白名单内的最终修复文件>
git commit -m "完成客户样本前端技术债收口"
```

---

## 5. 每批硬性验收指标

| 指标                    | 要求                                   |
| ----------------------- | -------------------------------------- |
| 后端/API/Envelope diff  | 0                                      |
| 每批修改的主巨型文件    | 最多 1 个                              |
| 同一任务并行轮询器      | 最多 1 个                              |
| 新增全局 Store/任务框架 | 0                                      |
| 结果状态和客户文案变化  | 0，除 Task 0 明确确认的旧断言/真实缺陷 |
| 新模块测试              | 每个 seam 至少 1 个聚焦 spec           |
| 提交粒度                | 每个 seam 独立提交、可单独回滚         |
| 完整检查频率            | 闭环完成后一次，不在每个小改动后重复   |

---

## 6. 风险与控制

| 风险                           | 控制                                       |
| ------------------------------ | ------------------------------------------ |
| 删除任务中心后进度消失         | 先完成主状态条和独立轮询，再删侧栏         |
| 当前任务与结果 Drawer 重复轮询 | 同一 job 同时只允许一个轮询器              |
| 历史页与主页面状态统计漂移     | 使用 `batchJobPresentation.ts` 唯一归一    |
| 拆 Drawer 时改变结果语义       | 权威结果选择、状态、排序和事实代码不移动   |
| Vue scoped CSS 拆出后失效      | 模板与对应 scoped CSS 成对迁移             |
| 结构调整与当前未提交功能混杂   | 先恢复 25/25 结果测试并形成稳定提交        |
| 为减少行数制造浅模块           | props/事件过多或需要共享状态重写时立即停止 |

---

## 7. Definition of Done

本轮完成不是“两个文件都变得很短”，而是以下事实成立：

1. 当前任务在主区域可见、可持续刷新、可查看结果、可停止。
2. 内嵌任务中心被删除，历史记录只有一个独立入口和实现。
3. 任务展示统计只有一个归一模块，不再出现数组/对象格式漂移。
4. `CustomerSampleValidationView.vue` 至少移出当前任务和一个低风险业务区块。
5. `SemanticRulesBatchResultDrawer.vue` 只移出纯展示区块，权威结果链未改变。
6. 所有聚焦测试和完整前端门禁通过。
7. 没有后端、API、Envelope、Store 或发布体系的范围扩张。

完成 Task 3 即获得可独立交付的第一阶段收益；Task 4 或 Task 5 遇到停止条件时可以延期，不影响第一阶段成立。
