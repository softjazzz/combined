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

## 10. 第五批：任务详情与病历清单

详见 [第五批实施与验收记录](2026-09-22-task-record-details.md)。主 Agent 负责后端个人范围、真实只读核对和最终验收；Sol / medium 子代理负责前端完整详情抽屉，独立审查代理检查隔离、竞态与空值。

- `GET /api/v1/tasks/{id}` 增加可选 all/created/received 范围，默认 all 兼容。收到范围只返回当前质控员的关联；任务进度和总病历数仍是全任务口径。详情列表以关联 ID 为稳定 key，不按旧 `record_id` 合并。
- “我的任务”和“全部任务”均可打开实际详情及病历清单，含加载、错误重试、空状态、筛选、分页和响应过期保护；不以单个 `record_id` 开放文书跳转。
- 只读实测 5 个用户、13 组任务-用户的关联范围均与数据库一致；浏览器验证两个入口、错误重试及 390px 布局。后端聚焦 146 passed、前端聚焦 117 passed；全量单测仍有 3 条既有断言失败及 1 条独立重跑通过的波动用例。
- 审查发现收到范围两次读取间撤销分配的竞态，已修复并测试。`.single()` 零行会抛错的质疑经当前 SQLAlchemy 适配器和真实路由复核不成立；保留默认 all 的既有广义 READ 权限作为独立 RBAC 审计项。
- 下一批是病例三坐标持久化与详情合同。场景候选、抽样和重质控须沿同一病例身份链贯通；迁移及真实数据库写入未经授权，保持未执行。PRD 任务审核、缺陷及文书待办仍未交付，Goal 保持 active。

## 11. 第六批：任务病历三坐标数据库合同

详见 [第六批实施与验收记录](2026-09-23-task-record-identity.md)。本批只交付 `qc_task_records` 结构迁移代码与 ORM/隔离测试，不执行数据库迁移，不解锁场景抽样或演示重新质控。

- 主 Agent 只读核实实际库 revision44、qc 35 行与 public 0 行的索引和可空性漂移，现存旧标识无空值/重复。Sol / medium 实现代理负责 revision46/ORM/测试，独立审查发现 3 项 P2 后修正，主 Agent 复核关键 diff、SQL 表达式和 111 条相关 pytest。
- 新列 `institute_id/patient_id/visit_id` 可空，旧行不回填；CHECK 要求历史全 NULL 或新行三坐标完整，分模式部分唯一替换旧全局唯一。错误的同名约束、非法旧标识、重复身份和有现代数据的降级均失败关闭；实际 qc 的物理 nullable 不改动。
- 只读 PostgreSQL 已验证 ASCII 空白判定，`alembic heads` 指向 revision46；**业务库仍停在 revision44**。真实 DDL、升级/降级与并发写验收须获授权后进行。下一批还必须为主表增加 `record_refs` 配置合同，再接场景候选、抽样保存、详情与真实批量质控。Goal 保持 active。

## 12. 第七批：任务主表指定病例范围合同

详见 [第七批实施与验收记录](2026-09-23-task-record-refs-config.md)。本批增加主表 `record_refs` 结构迁移和显式三坐标创建 API，不执行迁移或真实写入。

- 主 Agent 只读核查实际库 revision44、qc/public 旧 `record_ids` 分别为 JSONB/Text、两表均无 `record_refs`；适配器序列化参数可在只读 PostgreSQL 解析为 JSONB 数组。旧字段不修改、不回填。
- Sol / medium 实现代理负责 revision47、ORM 和隔离迁移测试；主 Agent 负责创建 DTO、路由、反例和合同文档；两个独立审查轴找出日志泄露、空结果假成功、顶层错拼、列约束漂移及降级并发竞态，主 Agent 逐项修复复核。
- 显式病例范围必须为完整且唯一的三坐标，并带任务场景；旧 `record_ids` 不与其混用。未知顶层字段、空结果、错误列型/约束均失败关闭；降级先锁目标表再预检非空配置。相邻 Python 测试 163 passed。
- **迁移45–47仍未执行，业务库 revision44；真实 PostgreSQL DDL/写入和并发验收待授权。** 场景候选、抽样关联保存、详情和 workspace 真实执行尚未接通，门急诊无正样本。不得将本批写成三场景任务已交付；Goal 保持 active。

## 13. 第八批前置核查：三场景候选来源

详见 [三场景候选来源只读核查](2026-09-23-task-scene-candidate-source-audit.md)。主 Agent 与 Sol / medium 独立审查分别核对 PRD、真实代码和只读聚合，确认当前不能安全解除场景抽样 409。

- 终末必须是出院且归档；运行包括在院与出院未归档。`cdm.mr` 482 行中 481 行归档标志空，状态投影和门急诊文书均为 0；`archive_sign` 值域未获确认，不以出院时间、空标志或任务标签推断场景。
- 当前 `/records/final` 仅按出院时间筛选，与 PRD 终末口径有冲突；不得复用为任务候选。门急诊列表也未使用 `cdm.outpat_record`，后者还需要按三坐标从多文书去重。
- 已向用户请求迁移授权、医院归档值域与门急诊正样本/数据源。等待事实合同期间，可推进与场景候选独立的 PRD 闭环，但场景抽样、真实执行和三场景验收保持未完成，Goal 保持 active。

## 14. 第九批：临床申诉审核与撤回动作安全

详见 [申诉审核动作实施与验收记录](2026-09-23-appeal-review-atomicity.md)。本批只处理已有审核/撤回写入端点，不把旧申诉列表或 V5 首页待办视为已交付。

- 主 Agent 只读核实 5 条申诉的状态与审核人分布，检查真实 JSONB/带时区列；Sol / medium 实现单事务服务，另安排独立证伪，主 Agent 负责权限路由、状态/错误合同与最终验收。
- REVIEW 权限先于审核正文校验；仅 `pending/reviewing` 可审核或由申诉人撤回，历史 `accepted` 等终态返回 409。两条写入路径共用 qc 行锁，审核历史和主状态一次提交，数据库故障不伪报成功，错误响应与日志不带异常内容。
- 独立审查提出撤回覆盖审核、public 同名表、非法正文先 422 并回显原文三项反证，复核又发现手工校验导致 OpenAPI 请求体缺失；主 Agent 已逐项修复并补测试。聚焦 HTTP/事务测试 28 条、Ruff 和编译通过；未做真实数据库写入，PostgreSQL 行锁并发及真实提交流程待授权验收。共享池或个人队列、人工缺陷来源、病历复审状态机仍待明确；Goal 保持 active。
- 相邻申诉更新接口仍可能在审核提交后改写理由/证据（先读状态后无条件写）；该风险不影响本批审核状态/历史原子性，列为下一小闭环，不把申诉全流程标记完成。

## 15. 第十批：申诉更新终态竞争保护

详见 [申诉更新终态竞态小闭环](2026-09-23-appeal-update-race.md)。本批只修复申诉人更新接口在审核/撤回间隙改写终态内容，不包含待办列表。

- Sol / medium 实现代理负责更新路由和反例；独立审查核对 SQL 适配器与 PostgreSQL 条件更新语义，主 Agent 只读核查真实列型、审查最终 diff 并补客户端初始化故障反例。
- 查询与最终更新均限定 `qc.qc_appeals`；最终 UPDATE 以 id、申诉人和 `pending` 三条件作为数据库级门槛，零行返回 409。非法正文和数据库错误均脱敏，OpenAPI 请求体保留。
- 初版红测理由不足 DTO 最短长度、落在错误的 422 前置分支，已更正后重新验证；最终相邻申诉测试 39 passed，Ruff/编译通过。真实 PostgreSQL 竞争写未授权、不宣称完成。申诉待办、并发编辑版本控制和完整前端工作流仍未交付；Goal 总范围未完成。

## 16. 第十一批：临床申诉待审核读取与 V5 下钻

- 主 Agent 核对 PRD、路由、模型和真实数据库只读聚合：`qc.qc_appeals` 有 5 行（`pending` 2、`accepted` 2、`rejected` 1），申诉人 ID 均非空；`qc` 与 `public` 均有同名申诉表，权威读写统一限定 `qc`。源 `cdm.medical_records` 与 `qc.qc_results` 显式限定，避免不同 `search_path` 下创建成功却读不到。创建接口原先成功写入后传错响应参数，已修复并用隔离测试覆盖。
- Sol / medium 后端代理收紧列表、详情及统计权限；前端代理改真实 snake_case DTO、角色动作、历史 `accepted` 只读和详情/审核交互。独立审查发现列表竞态、虚假附件及证据列型兼容风险，主 Agent 补请求序号、移除未上传文件的假证据控件，并在 API 边界兼容数组与历史 JSON 文本。审核者共享池使用 `status=reviewable` 统计 `pending/reviewing`，普通用户仅能读取本人；失败不显示假零。
- V5 首页增加仅审核者可见的临床申诉待办，并下钻 `/dashboard/qc/appeals?todo=review`。桌面和 390px 移动端用 Playwright 隔离响应验证列表、详情与布局；移动端旧 Dashboard 侧栏自动收起、表格横向滚动。该验证未连接真实后端，也未执行数据库写入。
- 本批前端聚焦 17/17、后端申诉隔离测试 55/55 通过，type-check 与完整源代码 ESLint 无错误。全量前端单测复跑为 1183 passed / 3 failed，失败均在未改动的单病例结果与复核预览旧用例；首次全量运行另有 2 个波动失败，复跑消失。`qc.qc_appeals` 实库是 JSONB，旧 `public` 同名表是 TEXT；本批不迁移或合并旧表。真实创建/审核/撤回/并发提交、`single` 模式仅 public 的部署兼容、附件上传、人工缺陷和病历复审待办仍未验收。运行/终末场景候选继续 409，等待院方归档值域与来源完整性；迁移45–49仍待授权。Goal 保持 active。

## 17. 第十二批：终末列表查询失败关闭

- 主 Agent 对照 PRD 和只读来源审计核对：手册的终末是出院且归档；当前 V5 及旧接口都只按出院筛选。`cdm.mr` 482 行中 481 行归档标志为空，医院尚未确认 `archive_sign` 值域与来源完整性，不能把已出院列表作为终末正样本。门急诊权威文书源 `cdm.outpat_record` 为 0 行，亦无真实查询正样本。
- 旧 `/api/v1/records/final` 在数据库无会话时返回内存病历，在质控聚合 SQL 失败时把结果降为伪 `pending` 或假空 `passed/failed`。Sol / medium 实现代理删除这两条降级链，查询期异常统一脱敏 503；输入参数 422 和正常查询条件、结果映射保持原状。独立审查指出内部 `HTTPException` 透传风险，已一并收口。
- 聚焦反例 24/24 通过，覆盖数据库缺失、构建/进入失败、聚合失败但旧降级查询成功、内层异常脱敏；Ruff、编译与 diff 检查通过。未启动真实 PostgreSQL 写入或执行迁移。该批只修正失败语义，不宣称终末列表完成：归档过滤、评分标准、真实正反样本和三场景任务候选仍待业务来源确认；迁移45–49仍待授权。Goal 保持 active。

## 18. 第十三批：质控结果建议验证合同校准

- 独立核查稳定的 3 个前端单测失败：结果卡与复核预览均已使用共享 `QcRemediationSuggestion`，非合规状态显示“修改建议”并保留原建议全文；旧测试仍断言“处理建议”或已移除的 `.suggestion-details`。结果卡的建议独立于判定详情展开，复核预览按四段结构直接展示；当前 PRD 未要求恢复旧折叠节点。
- 两名 Sol / medium 实现代理各只更新一个测试文件，验证建议标题、正文与四段标签保真、空建议及历史纯文本、详情展开时无重复、证据按钮现行“定位原文”文案；生产组件和业务状态未改。主 Agent 复核 diff 与聚焦测试，完整前端单测 1187/1187 通过。此项恢复质量门禁，不代表病历级审核、整改通知或真实 PostgreSQL 工作流已验收；Goal 保持 active。

## 19. 第十四批：病历文书只读入口与标注读取隔离

- 主 Agent 核对 V5 在院/已出院列表的真实路由和详情动作：未质控行原先只能看到“暂无结果”，无法从该页打开病历原文。Sol 6 / medium 前端代理在三坐标完整的未质控选中行增加可见的“查看病历文书”按钮，复用现有 `documentOnly` 工作台读取已保存 Bundle；已有结果仍走原抽屉，不创建或展示伪质控结果。初版测试绕过实际按钮，主 Agent 审查发现后改为真实点击反例。
- 主 Agent 核对 `/api/v1/emr/{record_id}/render`：文书按机构、患者、就诊三坐标加载，旧 `qc_results` 只按 `record_id` 查询且表合同无三坐标，存在同就诊号跨病例标注混入风险。后端代理移除不可信单键标注读取，响应以 `annotations_status=unavailable_unscoped_source` 明示不可用；旧详情页不再将空标注显示为“0 个问题/暂无质控问题”。**这不是缺陷定位已实现**，须待可信三坐标结果源及文书锚点合同补齐。
- 已保存 Bundle 的路由直接故障、全量文书初始领域读取故障统一脱敏 503；身份不完整为 422，真实空文书保持 200。主 Agent 补查服务层原先吞掉领域异常的分支并加接口反例；可选投影刷新失败仍沿用旧 Bundle，需另行评估新鲜度与可见提示。
- 聚焦后端相邻测试 57 passed，前端全量单测 1189/1189、type-check、encoding 通过；全源只读 ESLint 0 errors，仓库原有风格警告仍在。`emr_view.py` 的既有 E731 lambda 在 HEAD 可复现，本批未扩范围修正。当前只有前端开发服务，后端未启动；未做真实病历浏览器联调、PostgreSQL 业务写入或迁移。门急诊详情的规范病例键、真实缺陷锚点、病历审核状态以及终末归档口径继续未交付；Goal 保持 active。

## 20. 第十五批：门急诊详情身份与读取失败语义

- 主 Agent 核对列表到详情调用链：`medical_records.id` 与业务 `record_id` 可不同，旧详情按输入单键并行读取病历、文书、缺陷、整改和申诉，且每段失败可退化为空；旧 Bundle 身份解析未限定三坐标与唯一性。新详情先用 `id`/`record_id` 查唯一病历行，文书只用已解析主键关联；找不到为 404、歧义为 409、来源故障为脱敏 503，不再从内存记录、单键质控表或未证实身份的 Bundle 补数。响应以 `qc_data_status=unavailable_identity_contract` 标明缺陷、复核、整改、申诉不可确认，不保留来源记录里的假质控状态/缺陷数。
- 前端去掉 `getRecordDetail` 失败后回退旧单病历接口；门急诊抽屉区分加载、读取故障和真实空文书，支持重试及前后记录切换的过期响应隔离，完整展开 `medical_documents` 原文。质控关联不可确认时不展示空缺陷或整改操作，也不将失败伪装成“无缺陷”。
- 只读来源核对：`cdm.medical_records` 4 行的 `id` 与 `record_id` 均不同，门急诊 0 行、`medical_documents` 0 行；`qc_task_records` 35 行/25 个不同非空 `record_id`，仅 1 个可唯一对应病历表，另外 24 个也无法经旧 CDM 身份解析、Bundle 或最新合格复核批次找到详情。此数字只说明当前数据状态，不代表其他页面全部病例或门急诊真实业务验收。缺陷表仍缺可信病例关联键，文书片段锚点与病历级审核状态未交付。
- 独立只读审计补证：`qc.qc_defects` 1192 行没有病历三坐标外键；相连 `qc.qc_results` 834 行中完整机构、患者、就诊三坐标为 0。主 Agent 复查调用方后，将门急诊列表的源表质控状态/分数/缺陷数改为中性不可用，单条及批量催办/通过、缺陷导出停用并移除按裸 `record_id` 取得缺陷后写入的链；病历文书入口保留。联审抽屉不再并发读单键缺陷，未获可信关联时隐藏分数、缺陷及操作，旧详情响应不会回填切换后的病例。其他全局缺陷视图未伪装为单病历结果。
- 后端 `/qc/defects` 列表、导出、统计三个读取出口统一对显式 `record_id`（含空值和空白）在查询前返回 422 `record_identity_unverifiable`；不带该参数的全局筛选、分页、统计和导出保持原合同。已有外部单键调用会从历史成功改为 422，属刻意失败关闭；按缺陷 ID 的管理接口未改，未来开放单病历操作需先补三坐标与结果来源一致的关联合同。当前门急诊无正样本，不能将这些停用项计入 PRD 已交付。
- 聚焦后端相邻测试 51/51、前端全量单测 1203/1203、type-check 通过；全源只读 ESLint 0 errors。`defects.py` 全文件 Ruff 的 11 项均位于本批未改行，新增后端测试及 `records.py` Ruff 通过。仅有前端开发服务监听 3010，后端未启动（启动可能执行未经授权 DDL）；未做真实门急诊浏览器联调、业务库写入或迁移。任务病例三坐标持久化、抽样、真实执行及终末归档值域仍待合同/授权；Goal 保持 active。

## 21. 第十六批：单任务按比例分配与规则集执行合同核查

- 用户明确选择“创建任务时显式选择规则集”。当前创建抽屉已强制选择并按场景过滤；后端显式传入时校验静态目录并保存 `rule_set_key`，执行路径读取该键。但旧兼容请求仍可同时省略 `scene/rule_set_key`，静态目录没有发布状态或版本冻结，不能宣称规则集已发布。运行/终末抽样仍 409，执行只接受运行/终末；门急诊无匹配规则集，因而创建→抽样→workspace 执行尚无可到达的真实正向场景。
- 主 Agent 只读核查 `qc.sys_users` 的 235 个活跃用户均无 `qc_staff` 角色，现有任务没有 `sampling`；业务库仍为 revision44。分配实现只支持 `by_ratio`，锁任务及关联，在同一事务中校验创建人、任务配置、有效质控员、三坐标、数量及未分配状态，逐行写入后转换为 `assigned`；同计划重放可识别，部分写入失败回滚。前端读取真实候选，空目录/故障阻断提交，移除列表里的假负责人及占位批量分配。其他三种策略不计入交付。
- 独立审查发现并修正了任务配置与请求方法不一致、登录角色 `roles_json` 优先级、同名人员汇总歧义。该批发现的通用 `PUT /tasks/{id}` 旧状态绕行已在第十七批收口；分配接口仍使用 `MEDICAL_RECORDS.UPDATE`，现有 RBAC 只覆盖 admin/doctor 而非 qc_manager/qc_staff，操作者范围待用户确认，不擅自扩大全局权限。真实 PostgreSQL 写入、行锁并发及有质控员的浏览器正向流程未经授权/无数据，保持未验收。
- 创建向导移除虚构质控员，当前只允许选择 `by_ratio`，抽样后再选真实人员；全部任务入口仅对创建人且 `sampling/by_ratio` 可见。分配失败或结果未知后锁定再次提交，关闭并等只读列表刷新成功方可重开。后端纯内存事务测试 16/16、无 lifespan 的审计路由测试此前 18/18、Ruff 通过；前端全量 1213/1213、type-check、无修复模式 ESLint 通过。浏览器连接工具本次失败，未进行真实交互/截图验收。
- **过程越界**：本批早期运行旧 `TestClient` fixture 时，FastAPI startup 在真实 PostgreSQL 执行并提交了 6 个 qc 视图的 DROP/CREATE；该动作未获数据库写入授权，已即时告知用户并停止这一路径。未擅自回滚或修复视图，当前没有可比对的变更前元数据。后续测试改为不启动 lifespan；登录测试账号 `admin@medqc.com` 经只读核查不在真实 `sys_users`，其登录时间更新走内存。应用导入还会初始化本地 demo SQLite 文件，后续纯事务测试采用 `--noconftest` 避开该导入副作用。任何进一步 DDL/业务库写入仍需明确授权。
- 继续以“代码合同”和“真实业务验收”分开计数；本批不能算完整任务分配或真实批量质控完成。下一小闭环优先打通运行/终末三坐标候选抽样，并在授权和真实样本具备后验证所选规则集的任务级运行；终末归档值域、门急诊正样本、迁移45–49、其余 PRD 功能继续保留。Goal 保持 active。

## 22. 第十七批：受领人开始任务状态保护

- 主 Agent 复核真实调用链：`MyTasksView` 是前端唯一的通用 `PUT /tasks/{id}` 调用，原实现允许草稿直接进入进行中，任何具备医疗记录更新权限的用户还可改任务状态及配置，且不核对更新行数。独立审查确认这是绕过抽样/分配的旧入口；本批把该 PUT 收敛为只接受 `{status:"in_progress"}`，任务元数据及其他状态一律 422。原通用编辑合同因此不再可用，未来任务编辑需独立设计带创建人/状态保护的入口，不能误报为已交付。
- 新状态服务只引用 revision44 已有的 `qc_tasks.id/status/updated_at` 与 `qc_task_records.task_id/assignee_id`，在单事务中以 `assigned` 且受领人关联存在为条件更新；无任务 404、非受领人 403、状态不允许或条件更新零行 409、数据库故障脱敏 503。本人对已开始任务可幂等重放。窄入口使用医疗记录 READ 加任务关联核验，不扩大共享 UPDATE 权限；前端仅对 `assigned` 显示开始，防双击，严格核对响应 id/status 后提示成功，失败只读刷新核对。
- 独立审查用只读事务确认实库 `updated_at` 为 `timestamptz`、会话时区 `Asia/Shanghai`，指出初版 naive UTC 将偏早 8 小时；已改为 aware UTC 并在测试断言绑定参数时区，重放读取真实时间。PostgreSQL/SQLite 方言编译证明 `UPDATE ... EXISTS` 条件正确；未在实库执行 UPDATE。
- 后端 `DATABASE_URL=''`、`pytest --noconftest` 的纯内存/无 lifespan 测试 23/23、Ruff 通过；前端全量单测 1220/1220、type-check、只读 ESLint 通过。真实 PostgreSQL 受领人开始与并发提交、浏览器交互仍待授权及可用任务样本；本批不代表完整任务状态机、质控执行或病历审核交付。Goal 保持 active。

## 23. 第十八批：创建规则集必选与抽样创建人保护

- 用户明确新任务须在创建时显式选择规则集。只读调用链核查发现仍挂载的运行病历旧弹窗只发送场景而不发送规则集，必然得到 422；`POST /tasks` 又允许场景与规则集同时缺省。现在两个创建入口均加载同一静态目录并按场景供用户选择，目录失败、无匹配或选择无效时不提交；新建请求的场景和规则集均必填，目录键及场景匹配继续由后端校验。历史任务的 `scene/rule_set_key` NULL 仍可读取，不迁移、不回填。静态目录没有发布状态或版本冻结，因此界面只称“可用规则集”，不声称已发布。
- 另一独立缺口是任意具备医疗记录更新权限者可触发他人任务抽样。路由现于候选读取前核对认证身份与非空 `creator_id`；原子保存事务在 `FOR UPDATE` 锁内再核对，非创建人及历史空创建人返回 403、快照漂移失败关闭，拒绝路径不写任务关联。本人首次保存和重放仍保留。独立审查未发现可复现的 P0/P1/P2 问题。
- 主 Agent 复跑后端纯内存/无 lifespan 聚焦测试 160/160；前端全量 1223/1223、type-check、只读 ESLint 通过。未启动可能执行 DDL 的后端、未写真实 PostgreSQL；实库仍为 revision44，迁移45–49、真实并发/提交及浏览器正向链路未验收。运行/终末抽样继续 409：PRD 运行范围包含出院未归档，不能以在院子集冒充完整范围；`archive_sign` 值域与完整性未确认，远端来源查询超时且没有可验收正样本。门急诊亦无匹配规则集和正样本。Goal 保持 active。

## 24. 第十九批：我创建任务入口与旧执行边界

- 主 Agent 对照 PRD 和真实调用链确认：后端 `created` 个人范围已存在，但 `/dashboard/tasks/my` 的列表、统计和详情一直固定为 `received`，普通创建人没有“我创建”任务入口。现于同页增加我收到/我创建分段模式，URL、列表、统计、详情同步 `created/received`；创建模式以草稿数下钻、不暴露受领人的开始/继续操作。切换清理待办基准与旧响应；非法 tab 或 created+todo 组合不查询，合法范围变为非法范围时清空旧统计。`/dashboard/tasks/all` 与后端默认/显式 `all` 均仅 admin/qc_manager 可用，doctor/qc_staff 在任何任务行查询前 403，个人范围不变。
- 旧 `POST /tasks/{id}/re-analyze` 确实仍由旧运行病历页调用；原来只靠通用 ANALYZE 权限即可跨任务读取关联并调用演示 `QCService`。现在先按认证创建人失败关闭，历史空创建人 403，现代场景本人仍 409；病历查询故障脱敏 503。逐条异常不再回传原文，成功、失败、未尝试分开计数，零成功 503 且不更新任务状态；旧页展示后端的部分完成说明。该旧链仍非原子、最多尝试前 50 条且重试可能重复调用，演示 `QCService` 不能作为真实批量质控验收；受领人的本人病历子集执行/结果隔离仍未实现，不能通过放开整任务 403 替代。
- 独立审查初步怀疑 `.single()` 零行会抛 PGRST116，主 Agent 复核自研 `_PgClient` 后已更正：零行返回 `data=None`，未做无依据的 404 改动。后端无 lifespan 的隔离测试和前端聚焦测试通过；浏览器控制工具仍报 `nodeRepl.fetch request failed`，本批未做真实浏览器交互、业务库写入、迁移或真实病例正向验收。任务候选/抽样的运行与终末场景仍 409，归档值域及来源完整性待确认；Goal 保持 active。

## 25. 第二十批：受领人本人病例质控运行

- 主 Agent 核对了任务详情、分配事务、任务→workspace job、job 所有者读取和两条执行 worker：直接放开创建人守卫会执行整任务病例；仅用 `visit_id` 回退还会在三坐标缺失时串病例。现以显式 `scope=all|assigned` 分开运行合同：默认 all 保持创建人整批；assigned 在任务行锁内校验完整抽样与分配后仅取当前受领人的三坐标，以本人身份创建 job。运行关联写入不可变 `run_scope`，历史按任务、范围及触发人隔离；前端“我收到/我创建”按页面范围调用，精确 job_id 查询仍遵循 workspace 原有所有者权限，同人双身份也不混用范围。
- 四川与 LX0916 两条 worker 对任务 job 缺失、为空或损坏的 `filters.record_refs` 均在收集病历前失败关闭；普通非任务 job 的既有回退保留。独立审查未发现可复现的 P0/P1 范围泄露，指出迁移 50 漂移预检过宽；主 Agent 已补默认值及弱约束反例。后端以空 `DATABASE_URL`、`--noconftest` 完成任务相关 315/315 隔离测试，前端 1240/1240 单测、type-check、只读 ESLint 通过。
- 迁移 45–50 仍未执行，未启动后端应用生命周期或写真实 PostgreSQL；浏览器控制再次报 `nodeRepl.fetch request failed`，真实病例、并发和页面正向验收未做。job completed 仅代表作业状态，不自动更新任务病历处理状态/进度；单病历结果下钻、创建人查看受领人 job 的受控投影、运行/终末完整候选及抽样仍为后续缺口。Goal 保持 active。
