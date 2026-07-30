# 质控结果区紧凑工作台 Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use `executing-plans` to implement this plan task-by-task.

**Goal:** 将单病历质控结果区重构为符合 MedQC 规范的单工作台、高密度结果列表，并保持 Canonical Envelope 直通渲染。

**Architecture:** 只重组 `SingleRecordQcResultPanel.vue` 的模板和局部展示辅助函数，不修改后端契约、父级工作台或 `single-record-result-model.ts`。时限指标从后端 `customer_display_facts` 中选择并格式化，不能在前端重新计算；原始事实列表保留未进入指标带的字段。

**Tech Stack:** Vue 3 `<script setup>`、TypeScript、Vitest、Vue Test Utils、局部 CSS。

---

### Task 1: 用测试锁定紧凑工作台结构

**Files:**

- Modify: `tests/unit/views/workstation-v4/customer-sample-validation/SingleRecordQcResultPanel.spec.ts`

**Step 1: 写入失败测试**

增加以下验收断言：

```ts
expect(wrapper.get('[data-testid="single-record-result-toolbar"]').exists()).toBe(true)
expect(wrapper.get('[data-testid="single-record-result-summary"]').text()).toContain('3 条结果')
expect(wrapper.findAll('[data-testid="single-record-result-row"]')).toHaveLength(3)
```

在 LX0609-002 用例中增加：

```ts
expect(wrapper.get('[data-testid="timeliness-metrics"]').text()).toContain('规定时限8 小时')
expect(wrapper.get('[data-testid="timeliness-metrics"]').text()).toContain('实际间隔448.6 小时')
expect(wrapper.get('[data-testid="timeliness-metrics"]').text()).toContain('超出时限440.6 小时')
expect(wrapper.get('[data-testid="timeliness-timeline"]').text()).toContain('2026-06-20 17:19:08')
```

为展开后的双栏和证据列表增加：

```ts
expect(wrapper.get('[data-testid="single-record-detail-grid"]').exists()).toBe(true)
expect(wrapper.get('[data-testid="single-record-evidence"]').classes()).toContain('evidence-row')
```

**Step 2: 运行测试确认失败**

Run:

```powershell
npm run test:unit -- --run tests/unit/views/workstation-v4/customer-sample-validation/SingleRecordQcResultPanel.spec.ts
```

Expected: FAIL，缺少新工作台和时限指标测试标识。

### Task 2: 重构结果面板结构

**Files:**

- Modify: `src/views/workstation-v4/customer-sample-validation/SingleRecordQcResultPanel.vue`

**Step 1: 合并工具栏**

将原 `panel-header + result-tabs` 改为单个 `result-toolbar`：

- 左侧为标题与 `{{ viewItems.length }} 条结果`。
- 右侧保留现有 `statusTabs` 和 `activeTab`。
- 保持 `role="tablist"`、`role="tab"`、`aria-selected` 和原 tab test id。

**Step 2: 压缩折叠结果行**

- 状态、编号、规则名称与折叠图标放在第一行。
- 后端 `conclusionText` 放在第二行，折叠时最多两行。
- 保持整行按钮、`aria-expanded`、`toggle(item.key)`、`select` 事件和引擎返回顺序。

**Step 3: 增加只读时限展示辅助函数**

仅选择后端字段，不做时差计算：

```ts
const TIMELINESS_METRIC_KEYS = ['threshold_hours', 'elapsed_hours', 'overdue_hours'] as const
const TIMELINESS_TIME_KEYS = ['anchor_time', 'observed_time'] as const

function timelinessMetrics(item: SingleRecordQcResultItem) {
  const facts = item.customer_display_facts
  if (!facts || typeof facts !== 'object') return []
  return displayFactRows(item).filter((row) =>
    TIMELINESS_METRIC_KEYS.includes(row.key as (typeof TIMELINESS_METRIC_KEYS)[number]),
  )
}
```

只有 `threshold_hours`、`elapsed_hours`、`overdue_hours` 全部存在时显示指标带。时间轴只展示已有时间字段。普通事实列表过滤掉已在指标带和时间轴中展示的字段，避免重复。

**Step 4: 重组展开详情**

- 摘要区承载 detail、actual、standard 和可选时限指标。
- `single-record-detail-grid` 左栏承载判定事实、数据缺口和逐项判定。
- 右栏承载证据列表和模型分析。
- 建议作为详情底部的轻量 footer。
- 证据按钮增加 `evidence-row` 类，继续原样 emit 后端 evidence 对象。

**Step 5: 重写局部样式**

- 主面板采用一个连续白色工作台。
- 工具栏约 48px；结果行内边距约 `12px 14px`。
- 结果列表不使用独立悬浮卡。
- 详情背景为低对比浅灰，内部用栅格和分隔线组织。
- 风险色只用于状态和超时指标。
- `@media (max-width: 900px)` 将详情双栏降为单栏。

### Task 3: 聚焦验证与回归

**Files:**

- Test: `tests/unit/views/workstation-v4/customer-sample-validation/SingleRecordQcResultPanel.spec.ts`
- Review: `src/views/workstation-v4/customer-sample-validation/SingleRecordQcResultPanel.vue`

**Step 1: 运行聚焦组件测试**

Run:

```powershell
npm run test:unit -- --run tests/unit/views/workstation-v4/customer-sample-validation/SingleRecordQcResultPanel.spec.ts
```

Expected: 组件用例全部 PASS。

**Step 2: 审查数据直通边界**

确认：

- 未修改 `single-record-result-model.ts`。
- 未新增超时差值计算。
- 未修改状态映射。
- 未修改 evidence 事件参数。
- 未改变结果排序。

**Step 3: 功能闭环后集中运行质量检查**

Run:

```powershell
npm run check:encoding
npm run lint
npm run type-check
```

Expected: 全部退出码为 0。若全仓历史问题导致失败，记录与本次改动是否相关，不用放宽类型或修改无关文件。

**Step 4: 单独提交本次实现**

只暂存以下文件：

```powershell
git add src/views/workstation-v4/customer-sample-validation/SingleRecordQcResultPanel.vue
git add tests/unit/views/workstation-v4/customer-sample-validation/SingleRecordQcResultPanel.spec.ts
git add docs/plans/2026-07-30-qc-result-workbench.md
git commit -m "重构：压缩单病历质控结果工作台"
```
