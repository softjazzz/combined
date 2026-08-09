# 运行与终末病历质控结果展示 Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 将 `/workstation-v4/records/running` 与 `/workstation-v4/records/final` 收敛为“每份病历一行、当前页抽屉查看一份病历质控报告”的结果工作台，避免在主表或抽屉中逐条平铺全部质控点。

**Architecture:** 两个路由继续共用 `QcRecordResultListView`，主表只展示病历级总体结论和状态计数。点击病历后复用既有三坐标单病历结果接口、`QCRecordResultComparisonDrawer` 和 `QCRecordCompareWorkbench`；单病历结果只读模型由规则总表附加 `source_document` 与 `qc_point` 展示元数据，前端按权威 `source_document` 分组，不修改 Canonical Envelope、规则状态或证据。现有样本验证抽屉保持默认逐条模式，新页面显式启用分组模式。

**Tech Stack:** Vue 3、TypeScript、Ant Design Vue、Vitest、FastAPI/Python、Pytest；既有 LX0609 Canonical Envelope、规则总表、三坐标最新结果接口。

---

## 一、产品与数据合同

### 1. 两个页面的职责

| 页面         | 固定范围                     | 主时间列 | 结果语义                               |
| ------------ | ---------------------------- | -------- | -------------------------------------- |
| 运行病历质控 | `hospital_status=inpatient`  | 入院时间 | 当前在院病历的最近一次已完成质控结果   |
| 终末病历质控 | `hospital_status=discharged` | 出院时间 | 已出院病历的最近一次已完成终末质控结果 |

两个页面不得出现首页生成、编码、结算、DRG/DIP、自定义质控、整改流转或评分功能。

### 2. 主表一份病历一行

```text
患者 / 住院号 | 科室 / 床位 | 入院或出院时间 | 总体结论 | 结果摘要 | 最近质控 | 查看结果
```

- 行主键只能使用 `recordKey`，详情读取必须同时携带 `instituteId + patientId + visitId`。
- 结果摘要只显示非零计数：`确定问题 11 · 待核实 13 · 待判断 2`。
- `technical_error` 显示“结果校验异常”，不能计入临床问题。
- `source_state=unknown` 不在主表逐行重复显示；只有来源异常时才显示低干扰提示。
- 时间统一格式为 `YYYY-MM-DD HH:mm`，不得暴露 ISO `T`、微秒或时区原始串。
- 缺床位时不显示“床位待接入”第二行；只保留真实可用字段。

### 3. 当前页抽屉是一份病历一份报告

```text
病历质控结果
患者 / 科室 / 住院号 / 质控完成时间

[确定问题 11] [资料待核实 13] [待判断 2] [全部规则 75]

手术记录（4）
  LX0609-025  植入物相关记录       缺少种类、数量       2处证据
  LX0609-031  手术记录签名         术者签名不一致       1处证据

会诊记录（2）
  LX0609-020  会诊意见执行情况     后续病程未记录       3处证据
```

- 默认打开“确定问题”；没有确定问题时依次打开“资料待核实”“待判断”“全部规则”。
- 规则按规则总表 `source_document` 分组，不根据规则编号、关键词、执行器 `family_key` 或证据来源猜测。
- 一条规则只出现一次；同一规则涉及多台手术、多次输血或多份文书时，在该规则下显示事件数、证据数，展开后再查看具体事实。
- 规则状态保持独立，视觉分组不得合并或改写不同规则的结论。
- `data_gap` 独立为“资料待核实”；`uncertain/evaluation_unknown` 独立为“待判断”。
- `technical_error` 只显示在“系统状态”提示条和“全部规则”，不进入确定问题、资料待核实或待判断数量。
- 合规、不适用、未执行默认折叠在“全部规则”，不占据默认首屏。
- 选中规则或证据时继续使用既有文书目录、原文和安全证据定位；不显示 Prompt、模型原始输出、Bundle 或内部枚举。

### 4. 权威所有者

```text
Canonical Envelope
  → 状态、原因码、客户事实、证据唯一所有者

规则总表 luxian_0609_rule_master_v1.json
  → source_document、qc_point、客户政策说明唯一所有者

单病历结果 API
  → 只把两类权威资料组装成只读 DTO

前端
  → 只分组、排序和展开，不重算结论
```

禁止新增第二套 Bundle、结果表、规则分类表、前端硬编码规则编号分组或兼容结果回退。

## 二、实施顺序

### Task 0：冻结单病历展示元数据合同

**Files:**

- Read: `backend/app/data/luxian_0609_rule_master_v1.json`
- Read: `backend/app/services/luxian_0609_rule_master.py`
- Read: `backend/app/services/custom_qc_workspace_service.py`
- Test: `backend/tests/unit/test_luxian_0609_canonical_result_delivery.py`

**Step 1: 写公开服务入口失败测试**

经 `CustomQCWorkspaceService.build_latest_single_record_result_dto` 构造当前版本、三坐标匹配、已完成根任务和合法 Envelope，断言每个返回 item 具有：

```python
{
    "rule_id": "LX0609-025",
    "source_document": "手术记录",
    "qc_point": "未记录植入物名称、种类、规格或型号、材质及数量等信息",
}
```

同时断言 Envelope 原始 JSON 未被改写，`status/reason_code/customer_display_facts/evidence` 原样保留。

**Step 2: 运行红测**

```powershell
python -m pytest backend/tests/unit/test_luxian_0609_canonical_result_delivery.py -k "single_record and presentation" -q
```

预期：因 DTO 尚未投影 `source_document/qc_point` 失败。

**Step 3: 最小实现**

在 `build_latest_single_record_result_dto` 返回前，以 `load_luxian_0609_rule_master()` 建立 `rule_id → master_entry` 映射，仅复制 item 并附加：

```python
projected_item["source_document"] = master_entry.source_document
projected_item["qc_point"] = master_entry.qc_point
```

不得写回 Envelope，不附加 `family_key`，不改变 DTO `state`。

**Step 4: 补边界测试**

- 75 条当前规则均能从总表取得展示元数据。
- 规则顺序与 Envelope 一致。
- 重复或缺失 `rule_id` 仍沿用既有 `canonical_result_envelope_invalid`，不能被展示投影掩盖。
- 总表元数据不参与最新任务选择。

**Step 5: 验证并提交**

```powershell
python -m pytest backend/tests/unit/test_luxian_0609_canonical_result_delivery.py backend/tests/unit/test_luxian_0609_rule_catalog.py -q
git diff --check
git commit -m "feat: 投影单病历质控展示元数据"
```

完成后独立审核并暂停。

### Task 1：建立分组展示纯函数

**Files:**

- Modify: `src/views/workstation-v4/customer-sample-validation/single-record-result-model.ts`
- Test: `tests/unit/views/workstation-v4/customer-sample-validation/single-record-result-model.spec.ts`

**Step 1: 扩展只读类型**

给 `SingleRecordQcResultItem` 增加：

```typescript
source_document?: string
qc_point?: string
```

字段仅用于展示，不参与状态判断。

**Step 2: 写分组纯函数红测**

新增：

```typescript
buildSingleRecordQcPresentation(items)
```

返回：

```typescript
{
  counts: {
    nonCompliant: number
    dataGap: number
    uncertain: number
    technicalError: number
    other: number
  }
  sectionsByTab: Record<ResultReportTab, ResultDocumentGroup[]>
}
```

测试覆盖：

- 同一 `source_document` 的规则进入同一组。
- 同一规则只保留一项；若输入出现重复 rule_id，函数抛出合同错误，不静默去重。
- `technical_error` 不进入三类临床计数。
- 合规、不适用、未执行只在 `all`。
- 缺 `source_document` 使用“其他质控点”，不根据 rule_id 推断。
- 组内按后端 item 顺序稳定展示，不按前端严重度改写结果。

**Step 3: 实现最小纯函数**

状态页签固定为：

```typescript
type ResultReportTab = 'non_compliant' | 'data_gap' | 'uncertain' | 'all'
```

其中 `uncertain` 包含 `uncertain`、`evaluation_unknown`、`ai_suggested_non_compliant`；具体原始状态仍保留在行内。

**Step 4: 验证并提交**

```powershell
npx vitest run tests/unit/views/workstation-v4/customer-sample-validation/single-record-result-model.spec.ts
npx eslint src/views/workstation-v4/customer-sample-validation/single-record-result-model.ts tests/unit/views/workstation-v4/customer-sample-validation/single-record-result-model.spec.ts
git commit -m "feat: 增加单病历质控结果分组模型"
```

完成后独立审核并暂停。

### Task 2：为结果面板增加可选分组模式

**Files:**

- Modify: `src/views/workstation-v4/customer-sample-validation/SingleRecordQcResultPanel.vue`
- Modify: `src/views/workstation-v4/semantic-rules/components/QCRecordCompareWorkbench.vue`
- Modify: `src/views/workstation-v4/customer-sample-validation/QCRecordResultComparisonDrawer.vue`
- Test: `tests/unit/views/workstation-v4/customer-sample-validation/SingleRecordQcResultPanel.spec.ts`
- Test: `tests/unit/views/workstation-v4/semantic-rules/QCRecordCompareWorkbench.spec.ts`
- Test: `tests/unit/views/workstation-v4/customer-sample-validation/QCRecordResultComparisonDrawer.spec.ts`

**Step 1: 写兼容性红测**

断言：

- 默认 `presentation-mode="flat"` 保留客户样本验证现有展示。
- 新增 `presentation-mode="grouped"` 时才显示四个结果页签和文书主题组。
- 抽屉与 Workbench 只透传展示模式，不改变 `single-record-items`。

**Step 2: 实现分组模式**

`SingleRecordQcResultPanel` 新增：

```typescript
presentationMode?: 'flat' | 'grouped'
```

分组模式布局：

1. 顶部四个计数页签。
2. 技术异常存在时显示低干扰“系统状态”提示条。
3. 中部按 `source_document` 渲染折叠组。
4. 规则摘要行只显示规则编号、规则名称、客户结论和证据数。
5. 点击规则后复用现有详细事实、建议和证据定位区域。

不得复制 `displayFactRows`、`dataGapRows` 或证据定位逻辑到第二组件。

**Step 3: 无障碍与响应式**

- 页签有选中状态和数量。
- 主题组支持键盘展开。
- 选中规则后焦点可到达详情。
- 宽屏保留三栏对照；窄屏沿用 Workbench 移动标签，不把中文逐字换行。

**Step 4: 验证并提交**

```powershell
npx vitest run tests/unit/views/workstation-v4/customer-sample-validation/SingleRecordQcResultPanel.spec.ts tests/unit/views/workstation-v4/semantic-rules/QCRecordCompareWorkbench.spec.ts tests/unit/views/workstation-v4/customer-sample-validation/QCRecordResultComparisonDrawer.spec.ts
npm run type-check
git commit -m "feat: 增加病历质控报告分组视图"
```

完成后独立审核并暂停。

### Task 3：接入运行与终末清单的当前页抽屉

**Files:**

- Modify: `src/views/workstation-v4/QcRecordResultListView.vue`
- Modify: `src/views/workstation-v4/components/qc/QcRecordResultTable.vue`
- Modify: `src/views/workstation-v4/customer-sample-validation/QCRecordResultComparisonDrawer.vue`
- Test: `tests/unit/views/workstation-v4/QcRecordResultListView.spec.ts`
- Test: `tests/unit/views/workstation-v4/components/qc/QcRecordResultTable.spec.ts`

**Step 1: 写病历身份红测**

测试两条 `visitId` 相同但 `recordKey/instituteId/patientId` 不同的病历：点击第二行必须向抽屉传第二条完整三坐标，不得按 visit_id 查找或回退第一条。

**Step 2: 扩展表格行只读身份**

`QcRecordResultRow` 增加：

```typescript
instituteId: string
patientId: string
```

行点击仍只 emit `recordKey`；父页面用 `recordKey` 在当前规范化记录中唯一定位，再构建 `QCRecordResultFocus`。

**Step 3: 挂载结果抽屉**

在 `QcRecordResultListView` 内挂载既有 `QCRecordResultComparisonDrawer`：

```vue
<QCRecordResultComparisonDrawer
  :open="drawerOpen"
  :focus="selectedFocus"
  presentation-mode="grouped"
  @close="closeDrawer"
/>
```

移除 Task 1 的“下一闭环接入”页面提示，不新增第三个详情路由。

**Step 4: 清单视觉收敛**

- 删除每行重复的“来源未知”。
- 缺床位时不渲染占位副标题。
- 用统一安全函数格式化最近质控时间。
- 结果摘要保持单行省略，鼠标悬停或抽屉查看完整内容。
- 行与“查看结果”按钮触发同一抽屉。

**Step 5: 失败语义**

- `not_run`：按钮显示“暂无结果”，点击后显示“这份病历暂无已保存质控结果”。
- `technical_error`：抽屉显示服务端错误，不回退旧任务或其他病历。
- 缺三坐标：该行已在 Task 2 被排除，抽屉不得自行补全身份。
- 新请求未完成前清空上一病历结果，防止闪现串病历。

**Step 6: 验证并提交**

```powershell
npx vitest run tests/unit/views/workstation-v4/QcRecordResultListView.spec.ts tests/unit/views/workstation-v4/components/qc/QcRecordResultTable.spec.ts tests/unit/views/workstation-v4/customer-sample-validation/QCRecordResultComparisonDrawer.spec.ts
npm run type-check
git commit -m "feat: 接入运行终末病历质控报告"
```

完成后独立审核并暂停。

### Task 4：真实数据与视觉验收

**Files:**

- Create: `docs/audits/2026-08-09-running-final-qc-result-presentation-acceptance.md`
- Modify production code only if a focused acceptance case fails.

**Step 1: 登录态真实抽查**

至少抽查：

- 运行病历 2 份：一份有确定问题，一份未质控或只有待核实。
- 终末病历 2 份：一份多主题问题，一份存在待判断或技术异常。

记录脱敏三坐标哈希、页面范围、列表总体结论、摘要计数、抽屉计数、主题分组、证据定位和加载耗时。

**Step 2: 对账**

同一病历必须满足：

```text
列表 latest_qc_summary.status_counts
= 单病历结果 API items 状态计数
= 抽屉顶部计数
= 各主题组规则数之和
```

技术异常单独对账，不进入临床问题数。

**Step 3: 浏览器视觉验收**

- 1440px 首屏看到表头和至少 7 行病历。
- 抽屉默认首屏只见状态摘要和异常主题，不见全部 75 条规则。
- 390px 窄屏无逐字换行，文书/原文/结果可切换。
- 主表无原始 ISO 时间、重复来源小字或跨模块功能。

**Step 4: 完整验证**

```powershell
npm run check:encoding
npm run lint
npm run type-check
npm run test:unit
python -m pytest backend/tests/unit/test_luxian_0609_canonical_result_delivery.py -q
git diff --check
```

验收失败时，只为第一个可复现问题建立小闭环，不在本任务中修改任务创建、规则判定或 Canonical 聚合。

## 三、不在本方案范围

- “开始质控”“重新质控”及批量选择；现入口仍只有 visit_id，须等待三坐标任务合同。
- 新增质控状态筛选 API、病区筛选、评分或整改工作流。
- 修改任何 LX0609 规则状态、原因码、客户事实或证据生成。
- 以执行器 `family_key` 作为客户展示分类。
- 把同一主题内的多条规则合并成一条新结论。
- 根据文书数量推断资料完整性。

## 四、交付门槛

1. 两个页面始终一份病历一行，点击后在当前页打开一份病历报告。
2. 默认只展示确定问题、资料待核实和待判断，不平铺全部规则。
3. 规则按总表 `source_document` 分组，每条规则只出现一次且保持原状态。
4. 技术异常与临床问题严格分离；合规、不适用和未执行默认折叠。
5. 三坐标、Canonical、证据定位和客户政策均只有现有权威所有者，没有前端重算或第二资料链。
6. 真实运行/终末病历的列表计数、抽屉计数与单病历 API 完全一致。
