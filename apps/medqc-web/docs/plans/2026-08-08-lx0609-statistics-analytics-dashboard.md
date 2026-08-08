# LX0609 质控统计分析 Dashboard Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 将 `/workstation-v4/stats` 建设为面向全院质控科的真实统计分析 Dashboard，支持按质控完成时间、科室、任务和规则集查看可下钻的 Canonical 结果统计。

**Architecture:** 不恢复旧 `/dashboard`，不复用 `src/views/dashboard/StatisticsView.vue` 的 mock 数据，也不建设第二套统计库。统计接口由现有 `WorkstationAggregationService` 和 `qc/public.luxian_0609_record_result_envelopes` / 根任务共同读取，按三坐标和 Canonical Envelope 聚合；前端只绘制服务端返回的结构化统计，并把筛选上下文传递给现有病历池下钻。

**Tech Stack:** FastAPI、SQLAlchemy、PostgreSQL、Vue 3、TypeScript、Ant Design Vue、CSS/SVG 轻量图表、Pytest、Vitest。

---

## 一、PRD 依据与产品边界

| PRD/方案 | 已确认要求 | 本方案落实 |
|---|---|---|
| `docs/PRD-内涵质控V3.6总需求与差距矩阵.md:141-152` | 统计分析应覆盖运行/终末质量、缺陷详情、科室质量；当前页面多为 mock，属于 P2 能力 | 本轮先交付终末 LX0609 的真实 Canonical 统计，不伪称已覆盖门急诊、评分、甲级率或医生绩效 |
| 同文档 `:247-253` | 报表支持时间、科室、任务和明细下钻 | 所有统计 API 与页面共享筛选合同；每个图表保留可下钻身份/筛选条件 |
| `docs/0418/PRD/PRD-病案工作台V4.md:335` | 质控结果统计看板需要科室维度缺陷分布 | 科室横向对比、规则 Top 10、结果结构作为 MVP 主图 |
| `docs/plans/2026-08-08-medqc-quasi-commercial-home-record-pool.md:193-198` | KPI 与列表 limit 解耦；无真实趋势不得展示；技术异常不得混入医疗不合规 | 统计全部由服务端全量聚合；技术异常单列；趋势为条件模块 |

产品定位：

```text
质控首页概览       = 今天/当前范围内该先处理什么
病历池             = 查找、筛选、执行和查看单份病历
统计分析 Dashboard = 某个已选统计范围内，质量问题分布在哪里、哪些规则和科室需要整改
```

路由边界：

- 沿用现有 `/workstation-v4/stats`；当前它错误指向 `WorkstationV2View` 的 workbench，必须替换为真实统计分析页。
- 旧 `/dashboard` 继续重定向到 `/workstation-v4`，不得恢复或维护第二套 Dashboard。
- 当前阶段保留“已登录即可查看全院”的临时全院范围；后续机构/科室授权必须在服务端查询范围层加入，不能靠隐藏图表实现。

## 二、统计数据合同

### 2.1 统计范围

MVP 仅支持 `scope=final`、`rule_set_key=luxian_0609_qc_v1`、当前规则版本的 **已完成根任务 Canonical Envelope**。

| 参数 | 含义 | 失败/缺失语义 |
|---|---|---|
| `completed_from` / `completed_to` | 根任务 `finished_at` 的闭区间；页面必须写明“按质控完成时间” | 非法日期或 `from > to` 返回 422 |
| `department` | 与病历池相同的 CDM 科室筛选 | 不从任务文案或结果文案推断 |
| `job_id` | 可选根任务 ID | 非根任务、非 completed、规则集版本不匹配时返回空范围，不回退其他任务 |
| `rule_set_key/version` | 服务端回显；前端不可写死为统计事实 | 不匹配返回 422 或空范围，按 API 合同冻结 |

稳定统计身份：`institute_id + patient_id + visit_id + root_job_id`。

- 同一次任务中同三坐标只计一次 Envelope。
- 同一病历在不同已完成根任务中属于不同“质控完成事件”；趋势只统计事件数，不能把它标成患者数。
- “病历数”卡片使用按三坐标去重的记录数；“完成事件”另行标注，不能混为一个数字。
- 无 Envelope、Envelope 非法、三坐标无法确认时，不能进入临床缺陷统计；只计入 `data_health.canonical_envelope_invalid_or_missing_total`。

### 2.2 MVP 返回模型

新增但不重复存储的只读端点：

```text
GET /api/v1/workstation/analytics/luxian-0609
```

返回结构示意：

```json
{
  "scope": {
    "time_basis": "qc_completed_at",
    "completed_from": "2026-08-01T00:00:00+08:00",
    "completed_to": "2026-08-31T23:59:59+08:00",
    "department": null,
    "job_id": null,
    "scene": "final",
    "rule_set_key": "luxian_0609_qc_v1",
    "rule_set_version": "2026-06-09",
    "generated_at": "..."
  },
  "kpis": {
    "distinct_record_total": 0,
    "completed_event_total": 0,
    "records_with_non_compliant": 0,
    "records_with_data_gap": 0,
    "canonical_invalid_or_missing_total": 0
  },
  "status_distribution": [
    {"status": "non_compliant", "count": 0},
    {"status": "data_gap", "count": 0},
    {"status": "uncertain", "count": 0},
    {"status": "compliant", "count": 0},
    {"status": "not_applicable", "count": 0},
    {"status": "not_executed", "count": 0}
  ],
  "department_distribution": [
    {
      "department": "...",
      "distinct_record_total": 0,
      "non_compliant_record_total": 0,
      "data_gap_record_total": 0,
      "uncertain_record_total": 0,
      "canonical_invalid_or_missing_total": 0
    }
  ],
  "rule_distribution": [
    {
      "rule_id": "LX0609-...",
      "rule_name": "...",
      "non_compliant_count": 0,
      "data_gap_count": 0,
      "uncertain_count": 0,
      "evaluated_count": 0
    }
  ],
  "completion_time_series": null
}
```

明确不包含：平均分、通过率、甲级率、医生排名、AI 准确率、整改率、环比/同比。这些字段当前没有与 Canonical 结果一致的权威合同。

### 2.3 图表与颜色

| 模块 | 图形 | 数据 | 行为 |
|---|---|---|---|
| 统计范围/KPI | 5 个紧凑卡片 | `kpis` | 强调本次范围和数据截至时间，不显示伪环比 |
| 结果结构 | 环形图 + 图例 | `status_distribution` | 临床结果只含已完成 Canonical 条目；技术异常不进图 |
| 科室质量对比 | Top 10 分组横条 | `department_distribution` | 红=确定问题，橙=资料待核实，蓝灰=待判断；点击携带科室条件下钻 |
| 高频问题规则 | Top 10 横条 | `rule_distribution` | 按确定问题数、资料待核实数、规则名称排序；点击携带规则筛选下钻 |
| 质控完成量趋势 | 按日/周柱线图 | `completion_time_series` | 仅当服务端返回至少两个真实时间桶时展示；否则整个模块隐藏 |
| 数据健康 | 小型说明卡 | `canonical_invalid_or_missing_total` | 只报告结果可用性，不装扮成医疗风险图表 |

不新增 ECharts/Chart.js。MVP 使用 CSS/SVG 和 Ant Design Vue；文字图例和表格为无障碍主信息，图形是视觉辅助。

## 三、实施任务

### Task 0：只读冻结统计资料合同与历史可用性

**Files:**

- Read: `backend/app/services/custom_qc_workspace_service.py`
- Read: `backend/app/services/luxian_0609/record_result_read_model.py`
- Read: `backend/app/services/workstation/worklist_service.py:335-590`
- Read: `backend/app/routers/workstation.py`
- Read: `src/router/index.ts:1048-1058`
- Read: `docs/audits/2026-08-08-medqc-record-pool-real-data-acceptance.md`

**Step 1: 审计历史任务与 Envelope 可用性**

在脱敏/只读条件下记录：

- 根任务 `finished_at` 的最早/最晚时间和每日分布；
- 当前规则集/版本的 completed 根任务数；
- 三坐标有效 Envelope 比例、无效/缺失原因数；
- 是否存在一日以上的可用完成事件时间桶；
- `department` 在每个三坐标记录上是否稳定可得。

**Step 2: 冻结 MVP 能力**

| 审计结果 | 允许能力 |
|---|---|
| 有完整时间桶、每桶至少一个可确认事件 | `completion_time_series` 可进入后续任务 |
| 只有单日或完成时间缺失 | `completion_time_series=null`，前端隐藏趋势 |
| 规则结果可读、部分 Envelope 缺失 | 临床统计可做，缺失仅进入 `data_health` |
| 三坐标/部门字段不稳定 | 停止开发统计接口，不用 visit_id 或文案回填 |

**Step 3: 输出只读审计报告并暂停**

Create: `docs/audits/2026-08-08-lx0609-analytics-data-contract.md`

不得修改 API、数据库、前端、任务或规则。

### Task 1：统计查询服务（TDD）

**Files:**

- Modify: `backend/app/services/workstation/worklist_service.py`
- Create: `backend/tests/unit/test_luxian_0609_analytics_service.py`

**Step 1: 写失败测试**

构造四类 completed 根任务/Envelope：

1. 两个三坐标、同一当前规则集版本的有效 Envelope；
2. 同一 visit_id、不同三坐标的有效 Envelope；
3. 当前版本但缺失/重复 `rule_id` 的非法 Envelope；
4. 非当前版本、子任务、非 completed 任务。

断言服务公开入口：

```python
payload = WorkstationAggregationService(session_factory=session_factory).get_luxian_0609_analytics(
    completed_from=..., completed_to=..., department=None, job_id=None
)
```

- 仅有效 completed 根任务进入临床统计；
- 同 visit_id 的不同三坐标独立计数；
- status、科室、规则统计精确；
- 非法/缺失 Envelope 仅进入数据健康；
- 空范围返回零值结构，不抛异常也不回退旧统计。

**Step 2: 运行失败测试**

Run:

```powershell
python -m pytest backend/tests/unit/test_luxian_0609_analytics_service.py -q
```

Expected: FAIL，缺少 `get_luxian_0609_analytics`。

**Step 3: 写最小实现**

在 `WorkstationAggregationService` 内新增专用只读方法和私有查询辅助函数。查询必须：

- 读取根任务、Canonical Envelope、规则总表和与病历池一致的 CDM 科室；
- 以 `root_job_id + institute_id + patient_id + visit_id` 建立事件身份；
- 用 Python/SQL 的固定枚举聚合状态，不从 `conclusion/findings` 文本判断；
- 只返回统计字段，不返回病历正文、Prompt、LLM 原始响应或完整单病历 items。

不要把这项统计写入 Bundle、task summary、临时表或缓存。

**Step 4: 运行通过测试**

Run:

```powershell
python -m pytest backend/tests/unit/test_luxian_0609_analytics_service.py -q
```

Expected: PASS。

**Step 5: Commit**

```powershell
git add backend/app/services/workstation/worklist_service.py backend/tests/unit/test_luxian_0609_analytics_service.py
git commit -m "feat: 增加泸县质控统计服务"
```

### Task 2：统计 API 与筛选合同（TDD）

**Files:**

- Modify: `backend/app/routers/workstation.py`
- Create: `backend/tests/unit/test_workstation_analytics_router.py`

**Step 1: 写失败路由测试**

覆盖：

- `GET /api/v1/workstation/analytics/luxian-0609` 返回 Task 1 的结构；
- 时间范围、科室、任务 ID 原样传入服务；
- 非法时间、反向范围、非 UUID/非法任务 ID 返回 422；
- 未登录 401，当前临时全院角色模型下已登录用户 200；
- 所有响应携带 `scope.time_basis="qc_completed_at"`。

**Step 2: 运行失败测试**

Run:

```powershell
python -m pytest backend/tests/unit/test_workstation_analytics_router.py -q
```

Expected: FAIL，路由不存在。

**Step 3: 写最小路由实现**

只新增一条 GET 路由和参数校验，调用 Task 1 服务；不得复制 SQL 或在 router 中聚合统计。

**Step 4: 运行通过测试并 Commit**

Run:

```powershell
python -m pytest backend/tests/unit/test_luxian_0609_analytics_service.py backend/tests/unit/test_workstation_analytics_router.py -q
```

Commit:

```powershell
git add backend/app/routers/workstation.py backend/tests/unit/test_workstation_analytics_router.py
git commit -m "feat: 提供泸县质控统计接口"
```

### Task 3：真实趋势的条件闭环（只在 Task 0 批准时）

**Files:**

- Modify: `backend/app/services/workstation/worklist_service.py`
- Modify: `backend/tests/unit/test_luxian_0609_analytics_service.py`

**Step 1: 写失败测试**

用三天已完成事件构造统计，断言：

- 按 `finished_at` 归入 ISO 日期；
- 每桶值是完成事件数，不是独立患者数；
- 只返回一个桶或缺时间时 `completion_time_series=null`。

**Step 2: 实现最小时间桶聚合**

仅新增：

```json
[{"bucket":"2026-08-08", "completed_event_total":4}]
```

不得生成通过率趋势、风险改善趋势、环比或预测。

**Step 3: 测试和 Commit**

```powershell
python -m pytest backend/tests/unit/test_luxian_0609_analytics_service.py -q
git add backend/app/services/workstation/worklist_service.py backend/tests/unit/test_luxian_0609_analytics_service.py
git commit -m "feat: 增加真实质控完成趋势"
```

若 Task 0 未通过，本任务不执行，前端保持隐藏趋势模块。

### Task 4：统计 Dashboard 前端（TDD）

**Files:**

- Create: `src/views/workstation-v4/LuxianQcAnalyticsView.vue`
- Modify: `src/router/index.ts:1048-1058`
- Modify: `src/views/workstation-v2/types.ts`
- Create: `tests/unit/views/workstation-v4/LuxianQcAnalyticsView.spec.ts`
- Modify: `src/router/index.spec.ts`

**Step 1: 写失败组件测试**

Mock 统计 API，断言：

- 默认页面标题为“质控统计分析”，副标题明确“按质控完成时间统计”；
- 顶部筛选含日期、科室、任务；
- 显示 5 个 KPI、结果结构环形图、科室对比、规则 Top 10、数据健康；
- `completion_time_series=null` 时不渲染趋势容器；
- 不出现旧 mock 数字、平均分、AI 准确率、固定涨跌、假趋势或 `DashboardView`。

**Step 2: 运行失败测试**

Run:

```powershell
npx vitest run tests/unit/views/workstation-v4/LuxianQcAnalyticsView.spec.ts
```

Expected: FAIL，页面或路由尚不存在。

**Step 3: 写最小实现**

页面结构：

```text
统计分析标题 + “按质控完成时间”范围说明
日期 / 科室 / 任务筛选 + 查询 / 重置
5 KPI
[ 结果结构环形图 ] [ 数据健康 ]
[ 科室质量对比（Top 10） ] [ 高频问题规则（Top 10） ]
[ 质控完成趋势（条件显示） ]
```

实现约束：

- 不新增图表包；用 CSS `conic-gradient`、横向条和文字图例。
- 图表加载时显示 `a-spin` 与“正在汇总统计范围”，不要先显示零值图。
- 数据为空时显示范围内暂无完成质控事件；技术异常与空数据要使用不同文案。
- 所有数值由 API 响应驱动；前端不得计算跨页总数、补全趋势或从规则名称分类。
- 将 `/workstation-v4/stats` 改为加载本页；旧 `StatisticsView.vue` 不删除、不再作为真实入口。

**Step 4: 运行通过测试**

Run:

```powershell
npx vitest run tests/unit/views/workstation-v4/LuxianQcAnalyticsView.spec.ts src/router/index.spec.ts
npm run check:encoding
npm run lint
npm run type-check
```

Expected: PASS。

**Step 5: Commit**

```powershell
git add src/views/workstation-v4/LuxianQcAnalyticsView.vue src/router/index.ts src/views/workstation-v2/types.ts tests/unit/views/workstation-v4/LuxianQcAnalyticsView.spec.ts src/router/index.spec.ts
git commit -m "feat: 增加泸县质控统计分析看板"
```

### Task 5：明细下钻与病历池一致性（TDD）

**Files:**

- Modify: `backend/app/services/medical_records/query_service.py`
- Modify: `backend/app/routers/medical_records_query.py`
- Modify: `src/views/workstation-v4/LuxianQcAnalyticsView.vue`
- Modify: `src/views/workstation-v4/composables/usePatientRecords.ts`
- Test: `backend/tests/unit/test_workstation_query_service.py`
- Test: `tests/unit/views/workstation-v4/LuxianQcAnalyticsView.spec.ts`

**Step 1: 先冻结下钻筛选合同**

新增受控、服务端生效的病历池查询参数：

```text
analytics_job_id
analytics_completed_from
analytics_completed_to
analytics_rule_id
analytics_result_status
```

每个参数都必须使用同一 completed 根任务 + Canonical + 三坐标资料链；不能拿前端图表数组作为明细。

**Step 2: 写失败后端测试**

断言点击：

- 某科室 → 病历池只返回同范围科室；
- 某规则 → 病历池只返回该 Canonical rule_id 命中的病历；
- 某结果状态 → 只返回对应状态；
- 技术异常 → 数据健康筛选，不能显示为不合规。

**Step 3: 实现最小服务端筛选和前端跳转**

图表点击只生成 URL query 并跳转 `/workstation-v4`；病历池重新由服务端取数。若某筛选尚无安全服务端合同，则图表不可点击并显示“明细筛选待接入”，不得本地过滤当前图表数据。

**Step 4: 验证和 Commit**

```powershell
python -m pytest backend/tests/unit/test_workstation_query_service.py -q
npx vitest run tests/unit/views/workstation-v4/LuxianQcAnalyticsView.spec.ts
git add backend/app/services/medical_records/query_service.py backend/app/routers/medical_records_query.py src/views/workstation-v4/LuxianQcAnalyticsView.vue src/views/workstation-v4/composables/usePatientRecords.ts backend/tests/unit/test_workstation_query_service.py tests/unit/views/workstation-v4/LuxianQcAnalyticsView.spec.ts
git commit -m "feat: 支持统计分析下钻病历池"
```

### Task 6：真实数据、性能与安全验收

**Files:**

- Create: `docs/audits/2026-08-08-lx0609-analytics-dashboard-acceptance.md`
- Test: `backend/tests/unit/test_luxian_0609_analytics_service.py`
- Test: `backend/tests/unit/test_workstation_analytics_router.py`
- Test: `tests/unit/views/workstation-v4/LuxianQcAnalyticsView.spec.ts`

**Step 1: 对账**

同一筛选范围内逐项对账：

```text
统计 Dashboard 的 distinct_record_total
= 病历池同一统计筛选下的去重三坐标数

科室分布总数
= 统计范围的 distinct_record_total

规则结构每个状态之和
= 有效 Canonical Envelope 内的规则条目总数

无效/缺失 Envelope 数
= data_health.canonical_invalid_or_missing_total
```

**Step 2: 真实浏览器验收**

- 1440px：筛选、KPI、4 个分析模块可扫描；窄屏改为单列。
- 统计范围、数据截至时间和“按质控完成时间”始终可见。
- 无时间序列不显示趋势，不显示空图或假折线。
- 点击已接入图表下钻后，病历池范围与 Dashboard 筛选一致。

**Step 3: 性能门槛**

- P50 < 1.5 秒，P95 < 2 秒（真实院内范围；单独记录 SQL 与序列化耗时）。
- 前端图表渲染只消费一次 API payload，不产生 N+1 请求。
- 超标时先定位 SQL/Envelope 解析；不得直接加全局缓存或物化视图。

**Step 4: 安全验收**

- API 不返回病历正文、Prompt、LLM 原文、完整 result items 或患者敏感细节。
- 未认证 401；未来权限接入前统计范围标注“全院临时范围”。
- 技术异常、资料同步未知、规则 `data_gap` 在颜色、图例和下钻上严格分开。

## 四、停止条件

出现以下任一事实时暂停并先修数据合同，不继续画图：

1. 无法按三坐标关联统计结果和病历池记录；
2. `finished_at`、任务身份或规则版本无法验证；
3. 需要从规则名称、客户文案、当前页面或固定 mock 值推断统计；
4. 趋势需要回填或伪造历史；
5. API 为了统计而返回病历正文、模型输出或敏感明细；
6. 同范围 Dashboard、病历池、Canonical 对账不一致；
7. 统计查询 P95 超过 2 秒且尚无 SQL/解析证据。

## 五、明确延后

- 门急诊质量分析、病案首页质量分析、平均分/甲级率、整改闭环、质控员绩效、医生排名、专项 27 项指标、导出 PDF/Excel。
- 机构/科室分级授权和跨院数据隔离的正式权限模型。
- 历史趋势、同比环比、预测、AI 洞察。

这些项目需要各自的数据合同和验收基线，不能混入本 Dashboard 的首轮开发。
