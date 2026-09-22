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
- 更正（2026-09-22 并行批次复核）：`/workstation-v5/records/outpatient-emergency` 已存在（`src/router/index.ts:998`），复用 `OutpatientEmergencyRecordsView.vue`；缺的是工作台菜单入口。此前“只存在于 dashboard”的判断错误，不能据此新增重复路由。
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
| S2 | 工作台“我的待办”按场景下钻 + 零数量反馈 | 3.1 全节 | P0 | 首页全部场景的个人任务待办已实现；三场景拆分及缺陷/病历待办未交付 | 需补任务场景合同及缺陷/病历状态权威 owner（见 2.4） |
| S3 | 运行/终末病历默认筛选（缺陷：临床申诉+待整改；病历：待审核+待复审） | 4.2.2.2 | P0 | 待处理 | 需先确定审核状态权威来源，后端列表暂不支持状态过滤 |
| S4 | 门急诊病历进入主产品导航 | 4.1 | P0 | 导航及读取失败语义已完成；完整业务能力未交付 | 门急诊独立统计及真实正样本仍待补齐 |
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

- 真实接口验证依赖 `DATABASE_URL`（凭据来自已配置且被忽略的 `backend/.env`）；凭据不进入提交。真实样本缺失的能力不能以 mock 结果代替完整业务验收。
- S2/S3/S6 的核心风险是状态域 owner 缺失，必须先确定权威合同，禁止在页面层再造一套状态。

## 6. 第一批并行实施（2026-09-22）

**目标**：先修复“我的任务统计与列表范围不一致”，并验证门急诊已有页面能否接入工作台菜单。本批不代表 S2 的三场景八项待办全部交付。

**协调方式**：主 Agent 负责业务证据、固定接口合同、关键 diff、真实数据核对和提交；子代理统一使用 `gpt-5.6-sol` / `medium`，按文件边界实现，不自行暂存或提交。主 Agent 验收后按业务闭环提交。

### 已核实根因与范围

- `backend/app/routers/tasks.py:120` 的任务列表通过 `tab=received`，按 `qc_task_records.assignee_id` 查当前用户的任务；`:190` 的统计没有用户范围。
- `src/views/dashboard/tasks/MyTasksView.vue` 列表请求 `received`，统计却无参数请求全量；“待处理”显示 `draft`，快捷筛选发出不存在于任务枚举的 `pending`。
- 任务统计唯一数据源保持 `qc_tasks`，分配关系保持 `qc_task_records`；未开始任务采用已有 `assigned` 状态，不引入新状态映射或从病历量估算。
- 只读数据库核查发现 `public` 与 `qc` 有同名任务表；必须核对应用 search_path 的实际解析，不能仅以某个 schema 有数据认定接口可用。
- 门急诊页面已有读取链 `getOutpatientEmergencyRecordList` → `/api/v1/records/outpatient-emergency`；后端存在旧数据回退，菜单实施前单独核实可用性，不以接上菜单等同于完整门急诊能力验收。

### 分工与固定合同

| 子任务 | 文件所有权 | 合同与验收 | 状态 |
| --- | --- | --- | --- |
| A 后端个人任务统计 | `backend/app/routers/tasks.py`、`backend/tests/unit/test_task_stats_scope.py` | stats 新增可选 `tab=all/created/received`，默认 all 兼容；列表与统计共用个人范围；去重、无分配为零、故障非成功、缺失个人身份拒绝 | 已验收，提交 `5cabccab9` |
| B 前端个人任务计数 | `src/api/tasks.ts`、`src/views/dashboard/tasks/MyTasksView.vue` 及专属单测 | 统计和列表都使用 received；未开始采用 assigned；成功零值提示、加载/失败不显示假零、可重试 | 已验收，提交 `5cabccab9` |
| C 门急诊工作台入口 | `WorkstationLayout.vue`、`OutpatientEmergencyRecordsView.vue`、`backend/app/routers/records.py` 及专属单测 | 复用已有路由；菜单权限一致；来源故障返回 503，不返回演示数据；列表可重试且清除旧数据；指标不引用全院口径 | 已验收本批范围 |
| D 独立复核 | 只读审查，无实现文件所有权 | 检查身份、范围、错误语义、路由权限和回归风险 | 已完成；遗留风险见下文 |
| 主 Agent | 本计划、局部工具栏布局、集成检查与真实输入核对 | 独立复核查询范围与真实只读接口、审查关键 diff、统一门禁和分项提交 | 已完成本批验收 |

### 验证顺序与失败语义

1. 子代理先用聚焦用例复现范围错误，再实现最小修复；禁止写生产数据库、删除文件或修改 0609/0916 规则。
2. 后端覆盖双用户隔离、重复分配去重、created/all 兼容、零任务、缺失身份、数据库故障、统计与列表总数相等。
3. 前端覆盖 tab 参数、assigned 筛选、零数量反馈、失败显示与重试；菜单覆盖允许/禁止角色和导航。
4. 主 Agent 用数据库只读事务复核实际 schema、真实任务状态分布及个人统计与列表一致；不提交患者数据或凭据。
5. 集成后执行 encoding、lint、type-check、unit，以及相关 pytest；失败项与基线分开记录，不能以聚焦测试通过替代全部验收。
6. 浏览器验证适用页面及错误状态。真实写入流程须单独获得数据库写操作授权，因此本批真实验收限只读请求。
7. 检查暂存文件清单，按业务闭环中文提交，不推送、不合并。完成本批后更新剩余能力与依赖。

### 主 Agent 验收结果

- 应用实际 search_path 为 `qc,sys,cdm,public,legacy`；任务表解析到 `qc`，病历解析到 `cdm`。本批复用既有表，无数据库迁移或业务数据写入需求，不能据此推断 PRD 所有功能的数据合同已齐备。
- 只读连接确认 `transaction_read_only=on`；5 个真实分配用户的统计/列表分别为 `1/1、3/3、3/3、3/3、3/3`，均为 `in_progress`，无孤立分配任务；全量任务为 11。读取校验冷启动约 273ms，其余约 64–70ms，无 LLM 调用。单元测试中的适配器调用上限为 1–2 次，不等同于物理 SQL 次数。
- 门急诊真实接口返回 `200 / total=0`；本地未找到真实正样本。数据源缺失或异常返回 503、正常空结果返回 200 的分支由隔离测试覆盖。前端不再读取全院 overview 或展示固定通过率；当前筛选病历使用列表总数，另外三项统计明确显示“暂不可用”。
- 浏览器验证菜单权限入口、选中展开、个人任务计数、零数量反馈及门急诊故障提示。主 Agent 发现并修复工具栏溢出，刷新后主内容 `scrollLeft=0`、`scrollWidth=clientWidth=1021`，不再挤到侧栏下方。服务恢复后门急诊显示真实空列表与总数 0。
- 后端聚焦测试 21 条通过；最终前端聚焦测试 5 文件 23 条通过，另含前序下钻的回归组合 6 文件 33 条通过；类型检查通过；全量 lint 为 0 errors / 953 warnings（使用 `--no-fix`）。
- 全量单测为 1068 passed / 4 failed：两个既有质控组件共 3 条断言失败，已在未修改的 HEAD 归档上独立复现；另 1 条 router 超时在独立重跑通过。未修改这些无关测试，也不宣称全量门禁全绿。
- 过程异常：一轮旧测试误走真实登录路径，可能更新演示账号最后登录时间，已向用户说明并停止该路径，未擅自回滚数据库。后续使用只读连接；本地验收启动脚本跳过登录时间更新，产品鉴权代码不变。临时脚本、日志与凭据不提交。

**剩余风险与下一批依赖**：场景与倒计时尚未接入；病历审核/复审状态写入链未找到；`create_task` 的旧 `user_id` 取值及历史空创建者需另行核实；任务和门急诊后端 READ 权限比菜单角色更宽，需独立权限审计；门急诊列表现有 5000 条截断及三项统计尚未完善。优先补齐三类待办的权威状态合同，再实施首页待办，不扩大本批改动。

## 7. 第二批：首页个人任务待办

详见 [第二批实施与验收记录](2026-09-22-home-task-todos.md)。主代理继续协调 Sol / Medium 前后端子代理及独立审查，先交付全部场景个人任务的 24 小时内到期、进行中、未开始计数与同口径下钻。

本批修复创建人 id 写入；不回填历史空创建者。真实任务表无场景字段，deadline 为 text；日期型旧值统一按北京时间日末解释。未进行数据库迁移，未把任务名称或病历当前状态推断为创建场景。第一批“场景与倒计时尚未接入”的风险在本批仅解决到期标签，三场景仍未完成；完整 S2 仍是部分交付。

## 8. 第三批：任务场景合同与查询

详见 [第三批实施与验收记录](2026-09-22-task-scene-contract.md)。本批分开追踪“代码合同已实现”和“数据库及完整抽样流程已验收”，不把阶段性进展标记为 S2 全部完成。

- 主代理亲自核验主表、关联表、旧 registry 和 CDM 归档事实。任务主表无 scene；关联表 35 行 scene 全 NULL；CDM 482 行中 481 行没有归档标志，出院不等于归档。
- Sol / medium 子代理并行实施后端创建/查询、前端场景过滤/下钻和创建表单；主代理负责迁移、抽样安全边界、真实只读浏览器及门禁；另安排独立审查。
- 场景创建后不可改，历史 NULL 保留未标注；list/stats/todo-stats 共用场景过滤，与个人范围取交集；前端切换防旧响应，非法场景不降级全量。
- 新场景任务不能进入旧未分场景候选池，当前明确 409；这是临时未完成状态，不是三场景抽样交付。旧 NULL 抽样数据源失败不再伪造候选或返回成功空池。
- 独立审查发现旧运行创建入口漏传场景、数量键 count/total 不一致，纳入同批修复；草稿创建成功但抽样失败须保留任务 ID 并停止假进度轮询，避免重复创建。
- 另发现旧抽样关联插入和任务状态更新不是同一事务。本批将异常显式返回，但不声称消除了部分写；原子保存/重试语义进入下一小闭环。
- revision `20260922_000045` 仅新增 qc/public 现存任务表可空 scene 与 CHECK，不回填。**迁移未授权、未执行；真实三场景正样本和创建写入尚未验收**。
- 下一步仍保持原目标：获得授权后执行并核验迁移，明确 CDM 场景候选和 registry 映射，完成三场景抽样与原子保存；继续缺陷/病历待办等 PRD 余项。Goal 保持 active。

## 9. 第四批：抽样原子保存与重试

详见 [第四批实施与验收记录](2026-09-22-task-sampling-transaction.md)。承接第三批明确记录的部分写风险，不扩大到分配或规则执行。

- 主代理核实旧适配器两次独立 commit，并且异常可能触发再次 execute；新保存职责绕过该写重试层，在同一事务中锁任务、核对状态/配置、写关联及任务状态。
- 仅 draft 新保存；sampling 重放已保存结果，包括零条。草稿遗留关联、保存数量不一致、场景尚未接通或配置变化均明确拒绝，不删数据、不自行修复。首次与重放均从持久化关联读取稳定的前 20 条。
- 主代理只读实测：旧适配器和 SessionLocal 都指向本地 medqc，search_path 为 `qc,sys,cdm,public,legacy`，两张任务表的实际 OID 一致；连接均确认 `transaction_read_only=on`。
- Sol / medium 保存实现、独立审查、场景身份调查并行，主代理负责路由、反向状态变化边界、测试与证据。场景调查确认旧任务 record_id 不能直接承接三坐标身份，详情及重新质控链也需要独立收敛，详见第四批记录。
- 本批未改 UI，未通过浏览器执行写操作；真实 PostgreSQL 行锁并发、故障注入与提交确认仍待授权，隔离 SQLite 回滚测试不能替代这些验收。三场景抽样保护保持，S2 与 PRD 总目标仍未完成。
