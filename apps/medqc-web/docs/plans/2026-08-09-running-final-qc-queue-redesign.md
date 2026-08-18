# 运行病历与终末病历质控结果清单 Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 将“运行病历质控”和“终末病历质控”改造成两张病历质控结果清单：每份病历只占一行，点击一行才进入只读质控详情。

**Architecture:** 两个菜单保留独立 URL，但共用一个 `QcRecordResultListView`，仅通过 `carePhase` 固定服务端 `hospital_status=inpatient|discharged`。列表、汇总和详情只读取病历池的三坐标身份与 LX0609 Canonical 结果投影；不创建第二套任务、结果、统计或资料链。首页、编码、结算、DRG/DIP、自定义质控完全移出这两个页面。

**Tech Stack:** Vue 3、TypeScript、Ant Design Vue、Vitest；既有 `GET /api/medical-records/workstation`、`hospital_status`、三坐标 `recordKey`、`latest_qc_summary` 与 `qc_summary`。

---

## 产品合同

| 项目       | 运行病历质控                                    | 终末病历质控                                    |
| ---------- | ----------------------------------------------- | ----------------------------------------------- |
| 页面定位   | 在院病历的质控结果清单                          | 已出院病历的质控结果清单                        |
| 服务端范围 | `hospital_status=inpatient`                     | `hospital_status=discharged`                    |
| 每份病历   | 表格中的唯一一行                                | 表格中的唯一一行                                |
| 点击行     | 打开该病历质控详情                              | 打开该病历质控详情                              |
| 不包含     | 首页、编码、结算、DRG/DIP、自定义质控、整改流转 | 首页、编码、结算、DRG/DIP、自定义质控、整改流转 |

- 一行病历使用 `recordKey` / 三坐标唯一关联；不得按 visit_id 合并或串取结果。
- 结果只来自最新已完成的 LX0609 Canonical Envelope；不使用旧任务摘要、旧 QCResult、Bundle 或 mock 数据。
- `non_compliant`、`data_gap`、`uncertain`、`technical_error`、`not_run` 分开呈现。技术异常不计入临床问题，资料待核实不计入不合规。
- 本次只重构展示与结果读取，不改变在院/终末实际执行的规则集合。规则分期若需要调整，另立政策闭环。

## 目标页面

```text
运行病历质控 / 终末病历质控                    [开始质控]
[科室] [日期] [质控结果] [关键词] [重置]

纳入病历  待质控  需优先复核  资料待核实

患者 / 住院号 | 科室·床位 | 入院/出院时间 | 最新质控结果 | 问题摘要 | 最近质控 | 查看结果
──────────────────────────────────────────────────────────────────────────
一份病历 = 一行；不展开病历卡、不在行内放首页/编码/结算等操作
```

主表中“问题摘要”只显示结构化数量，例如“确定问题 2 · 待核实 1”。点击整行或“查看结果”打开抽屉；抽屉内才显示文书、证据定位和逐条结果。

## Task 0：冻结清单数据合同与动作边界

**Files:**

- Read: `src/router/index.ts`
- Read: `src/views/dashboard/records/RunningRecordsViewNew.vue`
- Read: `src/views/dashboard/records/FinalRecordsView.vue`
- Read: `src/views/workstation-v4/composables/usePatientRecords.ts`
- Read: `src/views/workstation-v4/types.ts`
- Read: `src/views/workstation-v4/customer-sample-validation/QCRecordResultComparisonDrawer.vue`
- Read: `src/services/sichuan-rule-workspace-service.ts`
- Read: `backend/app/services/medical_records/query_service.py`
- Read: `backend/app/services/custom_qc_workspace_service.py`
- Create: `docs/audits/2026-08-09-running-final-qc-result-list-contract.md`

**Step 1: Write the failing evidence checklist**

建立检查表，验证旧运行/终末页面仍是 mock/多功能页面；记录正式病历池接口中可用的三坐标、住院状态、病历时间、科室、病区、最新结果和完整汇总字段。

**Step 2: Verify the execution entry**

确认“开始质控/重新质控”是否存在支持真实三坐标集合的公开入口。若不存在，本期保留展示清单，按钮显示“该能力待接入”，禁止前端伪造任务创建。

**Step 3: Freeze list filter availability**

逐项确认科室、病区、时间、结果状态、关键词能否服务端过滤。没有后端字段的筛选项不得先做前端假筛选，报告其缺口。

**Step 4: Commit**

```powershell
git add docs/audits/2026-08-09-running-final-qc-result-list-contract.md
git commit -m "docs: 冻结运行终末质控结果清单合同"
```

## Task 1：创建共享的单行结果列表视图

**Files:**

- Create: `src/views/workstation-v4/QcRecordResultListView.vue`
- Create: `src/views/workstation-v4/components/qc/QcRecordResultTable.vue`
- Modify: `src/router/index.ts`
- Modify: `src/components/layout/WorkstationLayout.vue`
- Test: `tests/unit/views/workstation-v4/QcRecordResultListView.spec.ts`
- Test: `tests/unit/views/workstation-v4/components/qc/QcRecordResultTable.spec.ts`
- Test: `tests/unit/router/workstation-qc-result-list-routes.spec.ts`

**Step 1: Write failing route and structure tests**

测试两个 URL 都加载 `QcRecordResultListView`：

```text
/workstation-v4/records/running → carePhase=inpatient
/workstation-v4/records/final   → carePhase=discharged
```

断言每条记录只渲染一条表格 row；页面没有优先卡片、任务视图、缺陷 Tab、整改面板、首页/编码/结算/DRG/DIP/自定义质控入口。

**Step 2: Implement the minimal page shell**

页面只包含标题、固定范围标签、紧凑筛选行、四项结果汇总、单行表格。运行/终末视图的 DOM 完全相同，仅标题、时间列名和 `hospital_status` 不同。

**Step 3: Implement the table**

列固定为：

1. 患者 / 住院号
2. 科室 / 床位
3. 入院时间（运行）或出院时间（终末）
4. 最新质控结果
5. 问题摘要
6. 最近质控
7. 查看结果

不展示得分、文书数量、首页状态、编码状态、结算状态或阶段操作。行高保持可扫描；点击行与“查看结果”使用同一事件。

**Step 4: Verify**

- 桌面一屏能看到表头和至少 8 行病历；窄屏按列横向滚动，不把中文逐字换行。
- 无关功能在 DOM 中不存在，不是禁用状态。
- 两个路由的表格列、行主键和详情事件一致。

**Step 5: Commit**

```powershell
npx vitest run tests/unit/views/workstation-v4/QcRecordResultListView.spec.ts tests/unit/views/workstation-v4/components/qc/QcRecordResultTable.spec.ts tests/unit/router/workstation-qc-result-list-routes.spec.ts
git commit -m "feat: 增加运行终末质控结果清单"
```

## Task 2：接入病历池与 Canonical 结果摘要

**Files:**

- Modify: `src/views/workstation-v4/composables/usePatientRecords.ts`
- Modify: `src/views/workstation-v4/normalize.ts`
- Modify: `src/views/workstation-v4/types.ts`
- Modify: `src/views/workstation-v4/QcRecordResultListView.vue`
- Test: `tests/unit/views/workstation-v4/composables/usePatientRecords.spec.ts`
- Test: `tests/unit/views/workstation-v4/QcRecordResultListView.spec.ts`
- Test: `backend/tests/unit/test_workstation_query_service.py` _(仅当 Task 0 证明字段不足)_

**Step 1: Write failing projection tests**

断言运行页请求 `hospital_status=inpatient`，终末页请求 `hospital_status=discharged`；表格每行使用后端 `recordKey`，顶部四项汇总只读取服务端完整 `qc_summary`，不由当前页行数计算。

**Step 2: Implement the minimal data mapping**

给 `usePatientRecords` 增加显式初始住院状态参数，保留既有调用默认行为。映射 `recordKey`、三坐标、患者、科室/床位、入出院时间、`latest_qc_summary`、`source_state` 与 `qc_summary`；不回读 legacy 数据。

**Step 3: Lock failure semantics**

- 缺三坐标：不进入可操作清单。
- Canonical 无效：行状态“结果校验异常”，不计入临床问题。
- 未运行：行状态“未质控”，问题摘要显示“暂无结果”。
- `data_gap`：显示“资料待核实”，不显示为问题成立。
- `technical_error`：单列系统状态，不显示为不合规。

**Step 4: Verify with actual records**

各抽查 3 份在院、3 份已出院病历：API 的医院状态、页面归属、recordKey、最新结果状态、问题数量和最近质控时间完全一致；翻页不改变顶部汇总。

**Step 5: Commit**

```powershell
python -m pytest backend/tests/unit/test_workstation_query_service.py -q
npx vitest run tests/unit/views/workstation-v4/composables/usePatientRecords.spec.ts tests/unit/views/workstation-v4/QcRecordResultListView.spec.ts
git commit -m "feat: 接入病历质控结果摘要"
```

## Task 3：提供仅质控内容的单病历详情

**Files:**

- Create: `src/views/workstation-v4/components/qc/QcRecordResultDrawer.vue`
- Modify: `src/views/workstation-v4/QcRecordResultListView.vue`
- Test: `tests/unit/views/workstation-v4/components/qc/QcRecordResultDrawer.spec.ts`
- Test: `tests/unit/views/workstation-v4/QcRecordResultListView.spec.ts`

**Step 1: Write failing detail tests**

断言点击一行只以三坐标打开详情；详情没有首页、编码、结算、DRG/DIP、自定义质控标签或操作。

**Step 2: Implement the drawer**

抽屉固定三栏：

```text
文书目录 | 只读原文与证据定位 | 质控结果
```

右栏按“确定问题、资料待核实、待判断、技术异常”分组。每条结果只显示规则名、结论、客户化问题说明、证据定位和整改建议。

**Step 3: Verify**

- 证据只能引用 Canonical 安全引用；不显示 Prompt、模型原始输出、Bundle 或内部枚举。
- 同 visit_id 的不同三坐标打开正确详情；身份冲突失败关闭。
- 没有可定位原文时显示“未返回可定位原文”，不伪造链接。

**Step 4: Commit**

```powershell
npx vitest run tests/unit/views/workstation-v4/components/qc/QcRecordResultDrawer.spec.ts tests/unit/views/workstation-v4/QcRecordResultListView.spec.ts
git commit -m "feat: 增加单病历质控结果详情"
```

## Task 4：条件性接入质控操作

**Files:**

- Modify: `src/views/workstation-v4/QcRecordResultListView.vue`
- Modify: `src/views/workstation-v4/components/qc/QcRecordResultTable.vue`
- Modify: `src/services/sichuan-rule-workspace-service.ts` _(仅当 Task 0 已确认真实三坐标入口)_
- Test: `tests/unit/views/workstation-v4/QcRecordResultListView.spec.ts`
- Test: `tests/unit/services/sichuan-rule-workspace-service.spec.ts`
- Test: `backend/tests/integration/test_qc_sichuan_workspace_batch_flow.py` _(仅当需后端最小改动)_

**Step 1: Write failing action tests**

覆盖选择多条病历后创建任务、重新质控单条病历、同 visit_id 不同三坐标冲突时整批失败关闭，以及任务结束后刷新对应行摘要。

**Step 2: Implement only after a real entry is proven**

支持真实入口时：工具栏显示“开始质控”，行内仅显示“查看结果”或“重新质控”。执行中显示安全阶段状态，不在完成前展示结论。

不支持真实入口时：隐藏批量选择和开始按钮，页面显示“质控任务创建能力待接入”；不得用 mock 或前端循环伪造。

**Step 3: Verify**

- 批量请求与当前页面范围一致，不能混入另一住院状态病历。
- 每个任务、结果和回写都保持三坐标。
- 技术异常、资料待核实不会被显示为“已通过”。

**Step 4: Commit**

```powershell
python -m pytest backend/tests/integration/test_qc_sichuan_workspace_batch_flow.py -q
npx vitest run tests/unit/views/workstation-v4/QcRecordResultListView.spec.ts tests/unit/services/sichuan-rule-workspace-service.spec.ts
git commit -m "feat: 接入病历质控操作"
```

## Task 5：迁移旧入口并做真实验收

**Files:**

- Modify: `src/views/dashboard/DashboardView.vue`
- Modify: `src/components/dashboard/TodoBoard.vue`
- Modify: `src/components/layout/MainLayout.vue` _(仅保留旧 Dashboard 时需要)_
- Create: `docs/audits/2026-08-09-running-final-qc-result-list-acceptance.md`
- Test: `tests/unit/router/workstation-qc-result-list-routes.spec.ts`

**Step 1: Migrate links**

旧 Dashboard 的运行/终末入口都重定向到 workstation-v4 对应结果清单，保留已支持的筛选 query。旧 mock 页不删除，避免非菜单入口回归。

**Step 2: Run real acceptance**

记录 3 份在院、3 份出院病历的三坐标哈希、hospital_status、页面 URL、行状态、问题摘要、详情证据定位与加载耗时。验证一份病历在页面中仅一行，终末页没有在院病历，运行页没有已出院病历。

**Step 3: Run complete checks and commit**

```powershell
npm run check:encoding
npm run lint
npm run type-check
npm run test:unit
git commit -m "fix: 收敛运行终末质控结果入口"
```

## 不在本计划范围

- 首页生成、编码、结算清单、DRG/DIP、医保费用分析及自定义质控功能。
- 整改派发、审核流转、评分、缺陷问题池等二次工作台。
- 新建任务表、结果表、Bundle、统计平台或前端全局 Store。
- 在没有明确政策来源时改变在院/终末的规则集合。
- 根据文书数量推断资料完整性，或以 visit_id 单键关联病历。

## 交付门槛

1. 两个页面的主体都是单行病历质控结果表，不存在病历卡、病历内多功能或无关工作流。
2. 在院/已出院由服务端筛选；病历、任务与结果全程三坐标关联。
3. 所有状态来自 LX0609 Canonical，且临床问题、资料待核实和技术异常严格分开。
4. 点击一行只打开质控详情；详情只展示文书、证据和质控结果。
5. “开始质控”只在真实三坐标执行入口通过验证后开放。
