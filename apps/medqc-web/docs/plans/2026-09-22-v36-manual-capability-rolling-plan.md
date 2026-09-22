# V3.6 手册目标能力补齐 · 滚动实施计划

> 建立时间：2026-09-22
> 基线提交：`9a29f46b2`
> 工作分支：`codex/v36-manual-gap-drilldown-20260922`
> 权威目标文档：`docs/PRD-内涵质控V3.6总需求与差距矩阵.md`
> 手册原文：`C:\Users\Coldplay\Downloads\MinerU_markdown_内涵质控V3.6用户手册20240407__2102235238396878848.md`

## 1. 目标与口径

1. V3.6 手册是产品能力下限，MedQC 可以优化和超越，但不能删除、弱化或遗漏手册功能。
2. 本计划只记录已核实的实现事实（附文件:行号）或明确标注的待验证假设；不把 PRD 的旧覆盖状态当作事实。
3. 一次只推进 1–2 个相互关联的业务点，形成“真实问题 → 最小修改 → 聚焦测试 → 真实接口/浏览器验证 → 中文提交”的闭环。
4. 不修改 `backend/app/services/luxian_0609`、`backend/app/services/luxian_0916` 及其规则合同；不影响现有 0609/0916 结果、并发与门控。
5. 不新增第二套任务/缺陷/病历状态机；纯展示需求不修改后端合同。

## 2. 现状审计事实（2026-09-22 只读核对）

### 2.1 产品入口与导航

- 主入口为 `/workstation-v5`，`/workstation-v4` 仅作 alias（`src/router/index.ts:4-5,970-971`）。
- 侧边栏已挂：工作台首页、病历池、统计分析、运行病历、终末病历、规则管理、ICD、DRG、数据管理、系统配置（`src/components/layout/WorkstationLayout.vue:81-201`）。
- `门急诊病历` 只存在于 `/dashboard/records/outpatient-emergency`（`src/router/index.ts:87-95`），未进入 workstation-v5 导航 → 手册一级模块“门急诊病历”在主产品路径不可达。
- 运行病历 `/workstation-v5/records/running`、终末病历 `/workstation-v5/records/final` 均渲染 `QcRecordResultListView.vue`（`src/router/index.ts:997-1014`），与 `/dashboard/*` 下的 `RunningRecordsViewNew.vue`、`FinalRecordsView.vue` 是两套页面。

### 2.2 工作台首页

- 首页为 `QCOverviewView.vue`（`src/views/workstation/QCOverviewView.vue`），当前由“范围行 + 4 项 KPI + 3 个工作入口 + 缺陷分析 + 结论结构 + 数据与服务状态”组成（同文件 10-118、118-390）。
- 该页**没有任何“我的待办”区块**，也无任务/缺陷/病历三类待办的场景（运行/终末/门急诊）拆分 → 与手册 3.1 直接不符。
- KPI 卡片为纯展示 `div`，无点击下钻（同文件 91-100）。
- 首页唯一数据源是 `/api/v1/workstation/qc-home`，服务端明确“不读取旧热点、待办或通知聚合”（`src/views/workstation/QCOverviewView.vue:645-662`；`backend/app/services/workstation/worklist_service.py:335-357`）。
- 该投影的 KPI 口径为：`qc_pending_total` = 无 ready 摘要的病历（同文件:870）、`qc_completed_total` = ready 摘要（:875）、`high_risk_review_total` = 至少一条 `non_compliant`（:902）。

### 2.3 下钻契约（本轮重点）

- 统计分析页的下钻写入 `source=analytics` + `analytics_scope` / `analytics_completed_from|to` / `analytics_job_id` / `analytics_rule_id`，目标路径为 `/workstation-v5`（`src/views/workstation-v4/LuxianQcAnalyticsView.vue:638-652`）。
- 前端列表通过读取 URL 上的同名参数下发后端（`src/views/workstation-v4/composables/usePatientRecords.ts:148-165`）。
- 后端 `/api/medical-records/workstation` 已支持这些参数，并对取值做白名单校验（`backend/app/routers/medical_records_query.py:79-140`；`backend/app/services/medical_records/query_service.py:984-997,1056-1099`）。
- **缺陷**：`/workstation-v5` 由 `WorkstationV4HomeEntry.vue` 决定渲染首页还是病历池，判定条件只认 `record_id/action/from_stage/taskId/stage`（`src/views/workstation-v4/WorkstationV4HomeEntry.vue:33-41`）。因此携带 `source=analytics` 的下钻会落回首页，`analytics_*` 被静默丢弃，病历池从未渲染。
- 单元测试已把 `analytics_*` 视为 `/workstation-v5` 上的合法入口（`tests/unit/views/workstation-v4/usePatientRecords.spec.ts:59-71` 使用 `'/workstation-v5?department=ICU&analytics_scope=final'`），说明入口判定与数据层契约不一致。
- 二次缺陷：`resetFilters()` 只重置本地状态，URL 上的 `analytics_*` 仍会随每次 `fetchData` 重新下发（`src/views/workstation-v4/composables/usePatientRecords.ts:246-257,148-165`），用户界面无“退出下钻”的手段。

### 2.4 手册“我的待办”所需状态的事实边界

- 手册 3.1 需要 8 个计数 × 3 场景：倒计时 1 天/进行中/未开始任务、临床申诉/待审核人工缺陷、待审核/待复审病历；点击下钻，0 时提示“没有待处理的事项”（手册 32-133 行）。
- 唯一现存的待办聚合是旧入口 `/api/v1/dashboard/todo-stats`，其中 `not_started` 由病历 `pending` 近似、`total_defects` 由整改任务量近似，并在无 DB 统计时用 `max(1, total // 10)` 这类**伪造兜底**返回（`backend/app/routers/dashboard_api.py:265-379`，兜底分支起于 :339）。
- 因此完整“我的待办”需要先确定其权威 owner（任务/缺陷/病历三个状态域），否则会引入第二套状态机 → 列为后续切片，不在本轮实现。

## 3. 切片排序（第一阶段）

| 序号 | 切片 | 手册依据 | 优先级 | 状态 | 依赖 |
| ---- | ---- | -------- | ------ | ---- | ---- |
| S1 | 统计/首页下钻上下文贯通（进入 · 可见 · 可退出） | 3.1“点击任务数/缺陷数/病历数可下钻至对应列表” | P0 | 已完成（本分支本闭环提交） | 无 |
| S2 | 工作台“我的待办”按场景下钻 + 零数量反馈 | 3.1 全节 | P0 | 待处理 | 需先确定任务/缺陷/病历状态权威 owner（见 2.4） |
| S3 | 运行/终末病历默认筛选（缺陷：临床申诉+待整改；病历：待审核+待复审） | 4.2.2.2 | P0 | 待处理 | 需先确定审核状态权威来源，后端列表暂不支持状态过滤 |
| S4 | 门急诊病历进入主产品导航 | 4.1 | P0 | 待处理 | 需确认门急诊数据源范围 |
| S5 | 详情联审与缺陷原文定位（从运行/终末列表进入） | 4.2.4.4 | P0 | 待处理 | 需先核实现有证据定位组件可复用边界 |
| S6 | 审核/催办/整改/重质控与操作记录统一闭环 | 4.2.3-4.2.4 | P0 | 待处理 | 需先确认缺陷与整改唯一合同 owner |
| S7 | 工作表现（本周/上周质控缺陷与病历排名） | 3.2 | P1 | 待处理 | 现有 `getPerformanceRanking` 口径待核 |

## 4. 切片 S1 详情

**问题**：统计页下钻写了 `analytics_*` 上下文，但进入 `/workstation-v5` 后既没有转到病历池（上下文被丢弃），进入后也没有任何可见范围提示，且没有退出下钻的入口。

**最小修改范围**（全部前端，不改后端合同）：

1. `src/views/workstation-v4/WorkstationV4HomeEntry.vue`：把统计下钻参数纳入启动判定，使携带 `analytics_*`/`source=analytics` 的 `/workstation-v5` 直接进入病历池。
2. 新增 `src/views/workstation-v4/analyticsDrilldown.ts`：集中解析、清除与展示文案，避免多处自行拼 URL。
3. `src/views/workstation-v4/composables/usePatientRecords.ts`：改用统一解析函数（行为不变）。
4. `src/views/workstation-v4/WorkstationV4View.vue`：从路由 query 生成下钻范围，传入列表视图；“重置筛选”与“清除下钻”都要真正去掉 URL 参数后再取数。
5. `src/views/workstation-v4/components/WorkstationV4ListView.vue`：显示下钻范围提示条与清除按钮（沿用现有 `wv4-stage-context` 提示样式）。

**验收证据**：

1. 单元测试（4 个文件 46 条用例通过）：`analyticsDrilldown.spec.ts`（解析/清除/退出目标）、`WorkstationV4HomeEntry.spec.ts`（携带 `analytics_*` 进入病历池、普通 query 仍回首页）、`WorkstationV4ListView.spec.ts`（范围提示与清除事件）、`usePatientRecords.spec.ts`（继续下发 `analytics_*`）。
   - 反证：临时回退 `WorkstationV4HomeEntry.vue` 时，新增用例 “enters the record pool with the analytics drill-down scope instead of the home” 失败（1 failed / 4 passed），确认该用例锁定的是真实缺陷。
2. 真实接口（本地后端 `http://127.0.0.1:8001`，`DATABASE_URL` 指向本地 PostgreSQL）：
   - `/api/medical-records/workstation?hospital_status=discharged` → `total=482`；
   - 追加 `analytics_scope=final&analytics_result_status=non_compliant` → `91`；`data_gap` → `107`；`uncertain` → `29`；
   - 追加 `dept=消化内科` + `non_compliant` → `5`，证明科室与状态上下文可同时生效；
   - `/api/v1/workstation/qc-home` → `records_total=482 / qc_pending_total=196 / qc_completed_total=112 / high_risk_review_total=81`。
3. 浏览器（本地 Vite `http://127.0.0.1:3010`，演示账号登录）：
   - 打开 `?source=analytics&department=消化内科&analytics_scope=final&analytics_result_status=non_compliant` → 落点为病历池，显示“统计下钻范围 科室：消化内科 结果范围：最终结果 结果状态：确定问题”，列表 `共 5 份`（与接口 5 一致）；
   - 点“清除下钻” → 仍停留在 `/workstation-v5/worklist?department=消化内科`，范围提示消失，列表刷新为 `共 50 份`；
   - 点“重置筛选” → `/workstation-v5/worklist`（无 query），`全部科室 / 共 492 份`；
   - 回归：无参数进入 `/workstation-v5` 仍渲染“质控首页概览”；无参数进入 `/workstation-v5/worklist` 仍渲染病历池 `共 492 份`，均无下钻提示。

**待核口径（不影响 S1 合同，进入 S2 前必须澄清）**：首页 `high_risk_review_total=81` 与列表 `analytics_result_status=non_compliant` 的 `91` 不是同一口径（前者=含至少一条 `non_compliant` 的病历，后者=命中指定规则/任务范围内该状态的病历）。S2 若要用首页数字直接下钻到条数一致的列表，必须先确定唯一口径。

**环境说明**：本地真实接口验证使用的 `backend/.env`（gitignore 命中）从主工作区复制而来，仅用于本机启动后端，不进入提交；`src/styles/index.prebuilt.css` 由 `npm run dev` 的 predev 步骤重新生成，已在提交前恢复为基线，不纳入 diff。

## 5. 阻塞与风险

- 真实接口验证依赖 `DATABASE_URL`（凭据来自 `backend/.env`）。本 worktree 未包含 `.env`；若无法取得凭据，则真实接口/浏览器验证标记为阻塞，不以 mock 结果代替。
- S2/S3/S6 的核心风险是状态域 owner 缺失，必须先确定权威合同，禁止在页面层再造一套状态。
