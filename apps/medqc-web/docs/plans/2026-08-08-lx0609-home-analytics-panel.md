# LX0609 质控首页全院分析区 Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 在不伪造趋势、不新增统计链路的前提下，将质控首页收敛为“首屏工作入口 + 第二屏全院分析”的可用工作驾驶舱。

**Architecture:** 继续由 `GET /api/v1/workstation/home` 的 `clinical_qc` 作为唯一数据源。首屏只承载范围、KPI、优先复核队列和数据运行状态；第二屏只将已返回的全量结构化事实可视化。科室、覆盖和结论结构不发起第二次请求；规则族图只在服务端具有权威规则族事实时输出，趋势仍以 `trend=null` 隐藏。

**Tech Stack:** FastAPI、SQLAlchemy、Vue 3、TypeScript、Ant Design Vue、CSS `conic-gradient`、Pytest、Vitest。

---

## 一、已确认的产品口径

本方案以以下文档为准：

- `docs/plans/2026-08-08-medqc-quasi-commercial-home-record-pool.md`：首屏回答“当前哪里需要处理”，分析区为“科室分布｜高频规则族｜真实趋势（有数据才显示）”；无真实历史序列时必须隐藏趋势。
- `docs/gap/Workstation V4 新首页融合版设计方案.md`：第一屏不被图表抢占，第二屏才放团队视角图表。
- `docs/0418/UI/WorkstationV4-医疗浅色-DESIGN.md`：保持浅色医疗工作台风格，不增加图表依赖，优先使用进度条、排行和现有组件能力。

当前权威字段与展示边界：

| 图表 | 权威字段 | 口径 | 本轮状态 |
|---|---|---|---|
| 质控覆盖构成 | `clinical_qc.kpis` + `data_health.technical_error_total` | `已完成`、`待质控`、`结果校验异常` 均按病历计数 | 可直接实施 |
| 结论结构 | `clinical_qc.canonical_status_counts` | 仅统计已形成 Canonical 最终结论的规则条目 | 可直接实施 |
| 科室风险排行 | `clinical_qc.department_distribution` | 按 `high_risk_review_total` 排序，辅助显示资料待核实 | 可直接实施 |
| 高频规则族 Top 5 | `clinical_qc.rule_family_distribution` | 必须是服务端权威规则族字段，不从规则标题/编号推断 | 先只读审计 |
| 趋势 | `clinical_qc.trend` | 只显示服务端真实时间序列 | 保持隐藏 |

禁止事项：

- 不从当前页病历、优先队列、文案关键词或规则标题反推统计。
- 不将 `technical_error`、`data_gap` 和 `non_compliant` 合并为同一种风险。
- 不为了“好看”生成环比、同比、趋势线或预测。
- 不新增 ECharts、Chart.js、第二份首页接口、统计表或缓存平台。

## 二、目标页面结构

```text
首屏：工作入口
范围栏
4 个 KPI
[ 优先复核队列（65%） ] [ 数据运行状态（35%） ]

第二屏：全院分析
[ 质控覆盖构成（60%） ] [ 结论结构（40%） ]
[ 科室风险排行（60%） ] [ 高频规则族 Top 5（40%，有真实数据才显示） ]
```

图表交互原则：

- 图表首先是摘要，不替代“优先复核”工作队列。
- 图例必须同时展示中文状态、数量和口径说明；颜色不能作为唯一信息载体。
- 图表中的 `data_gap` 使用橙色，`non_compliant` 使用红色，`uncertain` 使用蓝灰，`compliant` 使用绿色，`not_applicable/not_executed` 使用中性灰。
- `technical_error` 只出现在覆盖构成和数据运行状态，绝不进入临床高风险排行榜。
- 所有图表在窄屏纵向堆叠；不隐藏数值和口径文字。

## 三、实施任务

### Task 0：冻结规则族事实合同（只读）

**Files:**

- Read: `backend/app/services/workstation/worklist_service.py:335-508`
- Read: `backend/app/data/luxian_0609_rule_master_v1.json`
- Read: `backend/app/data/luxian_0609_rule_contracts_v1.json`
- Read: `backend/tests/unit/test_workstation_home_service.py`

**Step 1: 核对当前规则族字段来源**

确认 `clinical_qc.rule_family_distribution` 当前是否为空常量、规则总表是否存在稳定的客户规则族字段，以及该字段是否能覆盖结果 Envelope 中的 `rule_id/rule_code`。

**Step 2: 写只读结论**

记录以下其中之一：

- 有一对一、稳定的规则族字段：批准 Task 4。
- 没有权威字段或映射存在歧义：本轮永久隐藏“高频规则族 Top 5”，不实现任何猜测映射。

**Step 3: 验收**

不得修改生产代码、数据库、规则执行器、Canonical Envelope 或前端。

### Task 1：覆盖构成图（首个 TDD 闭环）

**Files:**

- Modify: `src/views/workstation/QCOverviewView.vue`
- Test: `tests/unit/views/workstation/QCOverviewView.spec.ts`

**Step 1: 写失败测试**

在现有 `clinicalQcPayload` 中构造：

```ts
kpis: { records_total: 454, qc_completed_total: 5, qc_pending_total: 220 }
data_health: { technical_error_total: 229 }
```

断言：

- `[data-testid="qc-coverage-chart"]` 存在；
- 三个区段均显示“已完成 5”“待质控 220”“结果校验异常 229”；
- 区段百分比总和为 100%；
- `technical_error` 不出现在高风险 KPI 或优先复核队列。

**Step 2: 运行失败测试**

Run:

```powershell
npx vitest run tests/unit/views/workstation/QCOverviewView.spec.ts
```

Expected: FAIL，缺少 `qc-coverage-chart`。

**Step 3: 写最小实现**

在 `QCOverviewView.vue` 中从已有字段构造 `coverageSegments`：

```ts
const coverageSegments = computed(() => {
  const total = Math.max(0, Number(clinicalQc.value?.kpis.records_total || 0))
  return [
    { key: 'completed', label: '已完成', value: Number(kpis?.qc_completed_total || 0), tone: 'success' },
    { key: 'pending', label: '待质控', value: Number(kpis?.qc_pending_total || 0), tone: 'warning' },
    { key: 'technical', label: '结果校验异常', value: Number(dataHealth?.technical_error_total || 0), tone: 'neutral' },
  ].map((segment) => ({ ...segment, percent: total ? segment.value / total * 100 : 0 }))
})
```

使用一个可访问的分段横条和文字图例。若三段和与 `records_total` 不相等，显示“统计范围待核实”，不得擅自把差额归入任何状态。

**Step 4: 运行通过测试**

Run:

```powershell
npx vitest run tests/unit/views/workstation/QCOverviewView.spec.ts
```

Expected: PASS。

**Step 5: Commit**

```powershell
git add src/views/workstation/QCOverviewView.vue tests/unit/views/workstation/QCOverviewView.spec.ts
git commit -m "feat: 增加首页质控覆盖构成图"
```

### Task 2：结论结构图（第二个 TDD 闭环）

**Files:**

- Modify: `src/views/workstation/QCOverviewView.vue`
- Test: `tests/unit/views/workstation/QCOverviewView.spec.ts`

**Step 1: 写失败测试**

提供：

```ts
canonical_status_counts: {
  non_compliant: 33,
  data_gap: 70,
  uncertain: 5,
  compliant: 72,
  not_applicable: 139,
  not_executed: 4,
}
```

断言 `[data-testid="qc-conclusion-chart"]`：

- 展示全部状态的中文名称和准确数量；
- 文案明确为“已完成病历中的规则结论”；
- 不把 `technical_error` 加入该图；
- 无任何计数时显示“暂无已完成质控结论”，而非空白圆环。

**Step 2: 运行失败测试**

Run:

```powershell
npx vitest run tests/unit/views/workstation/QCOverviewView.spec.ts
```

Expected: FAIL，缺少 `qc-conclusion-chart`。

**Step 3: 写最小实现**

在同一页内（不新建通用图表平台）构造固定状态顺序和颜色映射。使用 CSS `conic-gradient` 渲染装饰性圆环，并保留可读图例：

```ts
const conclusionSegments = computed(() => FIXED_STATUS_ORDER
  .map((status) => ({ status, value: Number(counts[status] || 0), ...STATUS_META[status] }))
  .filter((segment) => segment.value > 0))
```

圆环仅消费这些数值；中心文字显示“已完成规则结论 / 总条数”，不显示未经服务端提供的通过率。

**Step 4: 运行通过测试**

Run:

```powershell
npx vitest run tests/unit/views/workstation/QCOverviewView.spec.ts
```

Expected: PASS。

**Step 5: Commit**

```powershell
git add src/views/workstation/QCOverviewView.vue tests/unit/views/workstation/QCOverviewView.spec.ts
git commit -m "feat: 增加首页质控结论结构图"
```

### Task 3：重排首屏和第二屏分析区

**Files:**

- Modify: `src/views/workstation/QCOverviewView.vue`
- Test: `tests/unit/views/workstation/QCOverviewView.spec.ts`

**Step 1: 写失败测试**

断言 DOM 层级：

- `priority-queue` 和 `data-health` 位于 `home-workspace`；
- 覆盖图、结论图、科室排行位于 `home-analysis`；
- `department-chart` 不再作为首屏侧栏的一部分。

**Step 2: 运行失败测试**

Run:

```powershell
npx vitest run tests/unit/views/workstation/QCOverviewView.spec.ts
```

Expected: FAIL，分析区容器不存在或层级不正确。

**Step 3: 写最小实现**

保留现有 `priority-queue` 和 `data-health` 的业务内容，仅重排模板：

```text
home-workspace
├─ priority-queue
└─ data-health

home-analysis
├─ qc-coverage-chart
├─ qc-conclusion-chart
└─ department-chart
```

桌面端使用 `1.3fr / 1fr`；窄屏降为一列。科室图继续最多展示 8 个科室，排序和“其余 N 个科室已收起”文案保持不变。

**Step 4: 运行通过测试**

Run:

```powershell
npx vitest run tests/unit/views/workstation/QCOverviewView.spec.ts
```

Expected: PASS。

**Step 5: Commit**

```powershell
git add src/views/workstation/QCOverviewView.vue tests/unit/views/workstation/QCOverviewView.spec.ts
git commit -m "feat: 重排首页工作区与分析区"
```

### Task 4：条件性规则族 Top 5

**Files (only if Task 0 has authoritative mapping):**

- Modify: `backend/app/services/workstation/worklist_service.py`
- Modify: `src/views/workstation-v2/types.ts`
- Modify: `src/views/workstation/QCOverviewView.vue`
- Test: `backend/tests/unit/test_workstation_home_service.py`
- Test: `tests/unit/views/workstation/QCOverviewView.spec.ts`

**Step 1: 写失败服务测试**

构造两个有明确规则族字段的 Canonical 结果，断言：

- 只按服务端规则总表的权威 `rule_family` 聚合；
- 非 `ready`、`technical_error` 和无规则族字段的条目不猜测归类；
- 返回前 5 个规则族，排序为确定问题数、资料待核实数、规则族名称。

**Step 2: 运行失败测试**

Run:

```powershell
python -m pytest backend/tests/unit/test_workstation_home_service.py -q
```

Expected: FAIL，`rule_family_distribution` 仍为空。

**Step 3: 写最小后端实现**

仅在 `_build_luxian_0609_home_projection()` 使用任务已读取的 Canonical 摘要和规则总表确定性字段生成：

```json
[
  {"rule_family":"手术相关记录", "non_compliant_count":3, "data_gap_count":1, "rule_count":4}
]
```

不得查询第二套结果表、解析客户文案或通过规则编号前缀猜测规则族。

**Step 4: 写失败前端测试并实现**

仅当数组非空渲染 `[data-testid="rule-family-chart"]`；为空时整个卡片不渲染，不显示“暂无数据”的装饰卡。

**Step 5: 验证与 Commit**

Run:

```powershell
python -m pytest backend/tests/unit/test_workstation_home_service.py -q
npx vitest run tests/unit/views/workstation/QCOverviewView.spec.ts
npm run check:encoding
npm run lint
npm run type-check
git diff --check
```

Commit:

```powershell
git add backend/app/services/workstation/worklist_service.py src/views/workstation-v2/types.ts src/views/workstation/QCOverviewView.vue backend/tests/unit/test_workstation_home_service.py tests/unit/views/workstation/QCOverviewView.spec.ts
git commit -m "feat: 增加首页高频规则族分析"
```

### Task 5：真实数据与视觉验收

**Files:**

- Read: `docs/audits/2026-08-08-medqc-record-pool-real-data-acceptance.md`
- Test: `backend/tests/unit/test_workstation_home_service.py`
- Test: `tests/unit/views/workstation/QCOverviewView.spec.ts`

**Step 1: 服务端口径复核**

对同一个 department/keyword 范围比较：

```text
病历池 total
= 首页 kpis.records_total

已完成 + 待质控 + 结果校验异常
= 首页 kpis.records_total

结论结构各状态之和
= 已完成病历的 Canonical 规则条目总数
```

若任一等式不成立：覆盖图显示“统计范围待核实”，停止上线；不得用前端补差。

**Step 2: 浏览器验收**

- 首屏在 1440px 宽度内优先展示优先队列和数据运行状态；第二屏才出现图表。
- 390px 宽度图表纵向排列，图例和值不截断。
- 技术异常不着色为临床风险；没有 `trend` 时不出现曲线/环比。
- 刷新、科室筛选、关键字筛选只调用现有 `/api/v1/workstation/home`，无第二次统计请求。

**Step 3: 性能验收**

以 454 份真实病历为基线，首页服务端聚合 P50/P95 不得劣于当前约 1.5 秒的单次实测；图表只能使用已返回 payload 的本地计算。

**Step 4: 最终 Commit / 审核**

仅提交验收测试或必要的客户文案修复；图表和数据合同不要混入规则执行、Bundle、LLM 或权限改动。每个 Task 独立审查后暂停。

## 四、剩余风险

- 当前 `technical_error_total=229` 属于历史 Canonical Envelope 缺失问题；覆盖图必须如实展示，但不能解释为医疗质量风险。
- `source_sync_status` 与运行任务状态仍是 `unknown`，只能留在数据运行状态，不纳入任何图表推导。
- 规则族 Top 5 尚无已确认权威字段；Task 0 未通过时，该卡片不做“待接入”占位，以免把空能力误导为结果。
- 真正趋势必须等待服务端时间序列合同，不能由当前任务完成时间临时拼接。
