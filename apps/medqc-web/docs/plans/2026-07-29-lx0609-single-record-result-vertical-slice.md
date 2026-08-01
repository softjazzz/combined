# LX0609 单病历质控结果纵向切片 Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 保留现有病历文书目录和原文对照工作台，只重建右侧质控结果区及其单病历只读接口，使任意已保存的 LX0609 单病历结果稳定、唯一、可解释并能安全定位原文。

**Architecture:** 现有 49 条质控执行器、任务持久化、病历文书读取和中间原文展示保持不变。后端新增一个窄的单病历结果读模型，从当前用户有权访问的已完成任务中确定性选出该病历的权威结果，投影为固定 DTO；前端新增独立右侧结果面板并由现有 `QCRecordCompareWorkbench` 承载文书定位联动。完成切换后删除单病历入口中的任务列表查询、父子任务拼装、前端去重和旧文案兜底。

**Tech Stack:** FastAPI、SQLAlchemy、Python 3、Vue 3、TypeScript、Ant Design Vue、Vitest、Pytest。

---

## 一、冻结范围

### 保留且不重构

- `src/views/workstation-v4/semantic-rules/components/ReadonlyMedicalDocumentDirectory.vue`
- `src/views/workstation-v4/semantic-rules/components/ReadonlyMedicalDocumentContent.vue`
- `src/views/workstation-v4/semantic-rules/components/ReadonlyMedicalOrderTable.vue`
- `QCRecordCompareWorkbench.vue` 中的左侧文书目录、中间原文/医嘱展示、文书加载和证据定位算法。
- LX0609 49 条规则执行器、模型调用、Evidence Session、RuleDecision、Aggregator 和任务持久化表。
- 批量任务结果页及批量结果抽屉。
- 会诊 020/023 继续保持当前 shadow/默认关闭口径。
- 输血 041–049 继续按当前数据源状态展示，不在本任务接入新数据。

### 重建

- 单病历“最近一次已保存结果”的后端读取边界。
- 单病历结果固定 DTO。
- 右侧质控结果列表、展开详情和状态汇总。
- 右侧结果到中间文书/章节的安全引用联动。

### 删除

- 单病历抽屉先调用任务列表、再调用任务详情的两阶段前端查询。
- 前端从父任务、子任务、`items`、`rule_results` 中自行选择和去重结果。
- 以状态、原因码、文案长度或解释完整度决定“哪条结果是真结果”的逻辑。
- 单病历入口回退到批量结果页或其他病历结果的逻辑。
- 确定问题使用“发现该质控点对应的明确问题”等通用占位文案的兜底。

## 二、目标链路

```text
病历列表中的当前 visit/record
        ↓
GET 单病历最新已保存结果
        ↓
服务端校验当前用户、任务归属、病历归属、规则集和完成状态
        ↓
确定性选择一个权威任务
        ↓
一病历 × 一规则最多一条；冲突显式 technical_error
        ↓
SingleRecordQcResultDTO
        ↓
右侧 QCRecordResultPanel
        ↓ 点击 evidence.source_ref
现有 QCRecordCompareWorkbench 定位中间文书/章节
```

## 三、固定 DTO 契约

后端第一版只返回页面所需字段，不返回父子任务结构、原始数据库主键、提示词或内部 trace。

```json
{
  "schema_version": "lx0609-single-record-result-v1",
  "record": {
    "record_ref": "rec_xxx",
    "visit_ref": "visit_xxx",
    "display_label": "患者显示标签"
  },
  "execution": {
    "job_ref": "op_xxx",
    "job_id": "仅服务端授权读取文书所需的受控任务标识",
    "rule_set_key": "luxian_0609_qc_v1",
    "rule_set_version": "v1",
    "completed_at": "2026-07-29T20:00:00+08:00"
  },
  "completeness": {
    "expected_rule_count": 49,
    "actual_rule_count": 49,
    "is_complete": true
  },
  "items": [
    {
      "rule_id": "LX0609-018",
      "rule_name": "主诉能导出第一诊断",
      "status": "non_compliant",
      "display_status": "确定问题",
      "reason_code": "chief_complaint_requirement_not_met",
      "conclusion": "主诉共14字；诊断指向性未通过。",
      "detail": "两个子项的完整医学判断。",
      "actual": "实际值和病历事实。",
      "standard": "规则核对标准。",
      "suggestion": "针对未通过子项的修改建议。",
      "model_analysis": "允许折叠展示的受控医学分析，不含提示词和内部追踪。",
      "evidence": [
        {
          "source_ref": "src_xxx",
          "source_type": "admission_record",
          "source_label": "入院记录—主诉",
          "field_path": "chief_complaint"
        }
      ]
    }
  ]
}
```

不变量：

- `status`、`reason_code`、文案和证据不能参与权威结果选择。
- `record_ref + rule_id + execution_scope` 是结果槽位；同槽位出现多个当前结果时输出一条技术冲突，不静默挑选。
- 解释不完整只触发展示降级，不允许从旧任务补文案。
- `non_compliant` 必须具有具体 `conclusion`、`detail/actual`、`standard`；否则客户状态降为待确认。
- 有可定位文书时必须返回服务端生成的 `source_ref`；没有目标文书时明确“目标文书缺失，无可定位原文”，不得伪造引用。

## Task 1：为单病历权威结果选择建立 RED 测试

**Files:**

- Create: `backend/tests/unit/test_luxian_0609_record_result_read_model.py`
- Reference: `backend/app/services/custom_qc_workspace_service.py`

**Step 1: 写失败测试**

覆盖以下输入：

```python
def test_latest_completed_generation_wins_without_explanation_ranking():
    # 旧任务解释完整但已被新任务替代；必须选择新任务。
    ...


def test_duplicate_current_rule_results_become_explicit_conflict():
    # 同一当前任务、同一 record_ref、同一 rule_id 出现两个状态。
    # 必须生成 technical_error，不允许按状态或解释长度选择。
    ...


def test_other_record_results_are_never_projected():
    # 多病历任务只能返回目标 record_ref 的结果。
    ...


def test_incomplete_confirmed_result_is_downgraded_for_customer_display():
    # 当前权威结果仍保留内部来源，但客户展示不得是空泛确定问题。
    ...
```

**Step 2: 验证 RED**

Run:

```powershell
Set-Location backend
python -m pytest tests/unit/test_luxian_0609_record_result_read_model.py -q --confcutdir=tests/unit
```

Expected: 因 `record_result_read_model` 尚不存在而失败。

**Step 3: Commit**

```powershell
git add backend/tests/unit/test_luxian_0609_record_result_read_model.py
git commit -m "测试：锁定单病历权威结果选择契约"
```

## Task 2：实现窄的后端单病历读模型

**Files:**

- Create: `backend/app/services/luxian_0609/record_result_read_model.py`
- Modify: `backend/app/services/custom_qc_workspace_service.py`
- Test: `backend/tests/unit/test_luxian_0609_record_result_read_model.py`

**Step 1: 定义纯函数和 DTO**

核心接口保持小而确定：

```python
def select_authoritative_completed_job(
    jobs: Sequence[Mapping[str, Any]],
    *,
    record_id: str,
    rule_set_key: str,
) -> Mapping[str, Any] | None:
    ...


def build_single_record_result_dto(
    job: Mapping[str, Any],
    *,
    record_id: str,
    hmac_key: str,
    expected_rule_ids: Sequence[str],
) -> dict[str, Any]:
    ...
```

选择条件只允许：

1. 当前用户可见；
2. `status == completed`；
3. 任务确实包含目标病历；
4. `rule_set_key` 为 LX0609；
5. 明确的当前父任务/当前执行代次；
6. 当前规则契约版本；
7. 当前槽位唯一。

不得新增 Ranking、置信度评分或解释权重。

**Step 2: 将存储读取保持在现有 Workspace Service**

`CustomQCWorkspaceService` 只新增一个窄的查询方法，返回候选持久化任务，不生成 DTO：

```python
def list_completed_jobs_for_record(
    self,
    *,
    created_by: str,
    record_id: str,
    rule_set_key: str,
    limit: int = 20,
) -> list[dict[str, Any]]:
    ...
```

查询必须绑定 `created_by`，排除其他用户任务；不得新增数据库表或 migration。

**Step 3: 实现冲突和解释质量门**

```python
if len(current_items_for_slot) > 1:
    return build_conflict_item(
        rule_id=rule_id,
        reason_code="duplicate_current_result",
    )
```

若权威 `non_compliant` 缺少规则事实、子结论或标准：

```python
display_status = "evaluation_unknown"
reason_code = "customer_explanation_incomplete"
```

并清除“发现问题”“明确违规”等确定性兜底文案。

**Step 4: 运行聚焦测试**

Run:

```powershell
Set-Location backend
python -m pytest tests/unit/test_luxian_0609_record_result_read_model.py tests/unit/test_luxian_0609_result_review_service.py tests/unit/test_custom_qc_workspace_export_html.py -q --confcutdir=tests/unit
```

Expected: 全部通过。

**Step 5: Commit**

```powershell
git add backend/app/services/luxian_0609/record_result_read_model.py backend/app/services/custom_qc_workspace_service.py backend/tests/unit/test_luxian_0609_record_result_read_model.py
git commit -m "重构：建立单病历权威结果读模型"
```

## Task 3：新增单病历只读 API

**Files:**

- Modify: `backend/app/routers/qc_sichuan.py`
- Modify: `src/services/sichuan-rule-workspace-service.ts`
- Test: `backend/tests/integration/test_qc_sichuan_workspace_batch_flow.py`
- Test: `tests/unit/services/semantic-rules-workspace-service.spec.ts`

**Step 1: 写路由 RED**

新增接口：

```http
GET /api/v1/qc/sichuan/workspace/records/{record_id}/latest-result
```

测试必须覆盖：

- 当前用户的已完成 LX0609 任务正常返回；
- 任务不包含病历时 404；
- 其他用户任务不可见；
- 多病历任务只返回目标病历；
- 结果不足 49 条时 `is_complete=false`；
- 当前槽位冲突时仅该规则为 `technical_error`。

**Step 2: 实现路由**

路由只做：

```python
jobs = workspace.list_completed_jobs_for_record(...)
dto = build_latest_single_record_result_dto(...)
return success_response(data=dto, ...)
```

不得在路由层重新计算状态或文案。

**Step 3: 新增前端 API 函数**

```ts
export async function getLatestLuxian0609RecordResult(recordId: string) {
  return requestEnvelope<SingleRecordQcResultDTO>({
    method: 'GET',
    url: `/api/v1/qc/sichuan/workspace/records/${encodeURIComponent(recordId)}/latest-result`,
  }, '获取该病历最近一次质控结果失败')
}
```

**Step 4: 运行接口测试**

```powershell
Set-Location backend
python -m pytest tests/integration/test_qc_sichuan_workspace_batch_flow.py -q
Set-Location ..
npm run test:unit -- tests/unit/services/semantic-rules-workspace-service.spec.ts
```

Expected: 全部通过。

**Step 5: Commit**

```powershell
git add backend/app/routers/qc_sichuan.py backend/tests/integration/test_qc_sichuan_workspace_batch_flow.py src/services/sichuan-rule-workspace-service.ts tests/unit/services/semantic-rules-workspace-service.spec.ts
git commit -m "功能：新增单病历最新质控结果接口"
```

## Task 4：建立新的右侧质控结果面板

**Files:**

- Create: `src/views/workstation-v4/customer-sample-validation/SingleRecordQcResultPanel.vue`
- Create: `src/views/workstation-v4/customer-sample-validation/single-record-result-model.ts`
- Modify: `src/views/workstation-v4/semantic-rules/types.ts`
- Test: `tests/unit/views/workstation-v4/customer-sample-validation/SingleRecordQcResultPanel.spec.ts`

**Step 1: 写组件 RED**

测试以下客户行为：

- 顶部只显示结果数和紧凑状态分布；
- 默认按确定问题、待确认/技术异常、数据不足、不适用、合规排序；
- 折叠条目显示状态、规则编号、规则名称和一句话结论；
- 展开显示完整判定说明、实际情况、核对标准、关键证据和处理建议；
- `model_analysis` 存在时放在“医学分析”折叠区；
- 点击证据只 emit `locate-evidence`，组件自身不猜文书；
- 确定问题若缺少具体解释，显示“结果解释不完整，需重新质控”，不显示泛化问题文案。

**Step 2: 实现展示组件**

视觉要求：

- 保持 `workstation-v4` 浅色医疗工作台语言；
- 右栏是一层列表，不再使用卡片套卡片；
- 使用弱分隔线、8px 控件圆角和低饱和状态色；
- 红色只用于确定问题，橙色用于待确认/数据不足；
- 条目展开时用单列信息分组，不出现第二个独立详情框；
- 中文完整换行，避免窄列逐字换行。

**Step 3: 运行组件测试**

```powershell
npm run test:unit -- tests/unit/views/workstation-v4/customer-sample-validation/SingleRecordQcResultPanel.spec.ts
```

Expected: 全部通过。

**Step 4: Commit**

```powershell
git add src/views/workstation-v4/customer-sample-validation/SingleRecordQcResultPanel.vue src/views/workstation-v4/customer-sample-validation/single-record-result-model.ts src/views/workstation-v4/semantic-rules/types.ts tests/unit/views/workstation-v4/customer-sample-validation/SingleRecordQcResultPanel.spec.ts
git commit -m "功能：重建单病历右侧质控结果面板"
```

## Task 5：在现有对照工作台中仅替换右栏

**Files:**

- Modify: `src/views/workstation-v4/semantic-rules/components/QCRecordCompareWorkbench.vue`
- Modify: `src/views/workstation-v4/customer-sample-validation/QCRecordResultComparisonDrawer.vue`
- Test: `tests/unit/views/workstation-v4/semantic-rules/QCRecordCompareWorkbench.spec.ts`
- Test: `tests/unit/views/workstation-v4/customer-sample-validation/QCRecordResultComparisonDrawer.spec.ts`

**Step 1: 锁定左侧和中间区域不变**

新增回归断言：

- 文书目录仍由 `ReadonlyMedicalDocumentDirectory` 渲染；
- 中间普通文书仍由 `ReadonlyMedicalDocumentContent` 渲染；
- 医嘱仍由 `ReadonlyMedicalOrderTable` 渲染；
- 默认优先打开入院记录；
- 选中文书、搜索和滚动行为不改变。

**Step 2: 替换右侧模板**

删除 `QCRecordCompareWorkbench.vue` 中当前内嵌的结果 `<aside>` 模板，替换为：

```vue
<SingleRecordQcResultPanel
  :items="issues"
  :selected-key="selectedIssueKey"
  @select="selectIssue"
  @locate-evidence="locateEvidence"
/>
```

左侧、中间和现有 `locateEvidence` 的安全匹配逻辑保持不变。

**Step 3: 抽屉改为一次 API 调用**

`QCRecordResultComparisonDrawer.vue` 删除：

- `listSichuanWorkspaceBatchJobs`；
- `getSichuanWorkspaceBatchJob`；
- `buildRecordComparisonIssues`；
- `record_ids` 和 `record_focus` 的前端拼装。

改为：

```ts
const result = await getLatestLuxian0609RecordResult(focus.recordId || focus.visitId)
```

成功时直接把 DTO 的 `items`、`record_ref` 和受控 `job_id` 交给工作台。

**Step 4: 运行聚焦前端回归**

```powershell
npm run test:unit -- tests/unit/views/workstation-v4/customer-sample-validation/QCRecordResultComparisonDrawer.spec.ts tests/unit/views/workstation-v4/customer-sample-validation/SingleRecordQcResultPanel.spec.ts tests/unit/views/workstation-v4/semantic-rules/QCRecordCompareWorkbench.spec.ts
```

Expected: 全部通过。

**Step 5: Commit**

```powershell
git add src/views/workstation-v4/semantic-rules/components/QCRecordCompareWorkbench.vue src/views/workstation-v4/customer-sample-validation/QCRecordResultComparisonDrawer.vue tests/unit/views/workstation-v4/customer-sample-validation/QCRecordResultComparisonDrawer.spec.ts tests/unit/views/workstation-v4/semantic-rules/QCRecordCompareWorkbench.spec.ts
git commit -m "重构：单病历对照页切换至新结果面板"
```

## Task 6：删除单病历旧拼装职责

**Files:**

- Modify: `src/views/workstation-v4/semantic-rules/record-comparison-model.ts`
- Modify: `tests/unit/views/workstation-v4/semantic-rules/recordComparisonModel.spec.ts`
- Modify: `src/views/workstation-v4/CustomerSampleValidationView.vue`（仅删除不再使用的单病历结果状态，禁止改病历池和任务执行）
- Modify: `backend/app/services/custom_qc_workspace_service.py`

**Step 1: 确认调用者**

使用 CodeGraph 检查 `buildRecordComparisonIssues`、单病历旧状态和旧去重函数的剩余调用者。

**Step 2: 删除旧职责**

- 若 `buildRecordComparisonIssues` 仅剩批量页使用，则移动到批量页目录并改名为批量专用；
- 删除单病历前端按 `status + reason_code` 去重；
- 删除“解释更完整优先”的候选选择；
- 保留导出和批量页仍需要的安全投影，不顺手重构。

**Step 3: 聚焦验证**

```powershell
npm run test:unit -- tests/unit/views/workstation-v4/customer-sample-validation/QCRecordResultComparisonDrawer.spec.ts tests/unit/views/workstation-v4/semantic-rules/QCRecordCompareWorkbench.spec.ts
Set-Location backend
python -m pytest tests/unit/test_luxian_0609_record_result_read_model.py tests/unit/test_luxian_0609_result_review_service.py tests/unit/test_custom_qc_workspace_export_html.py -q --confcutdir=tests/unit
```

Expected: 全部通过，且 CodeGraph 不再显示单病历入口调用旧任务拼装函数。

**Step 4: Commit**

```powershell
git add src/views/workstation-v4/semantic-rules/record-comparison-model.ts src/views/workstation-v4/CustomerSampleValidationView.vue backend/app/services/custom_qc_workspace_service.py
git commit -m "清理：移除单病历结果旧拼装路径"
```

## Task 7：真实持久化回读和浏览器验收

**Files:**

- Create: `docs/reports/2026-07-29-lx0609-single-record-result-acceptance.md`
- Test data: 固定已保存的普通病历任务，不写客户正式结果。

**Step 1: 后端真实回读**

对一份含 49 条结果的已完成任务读取新 API，记录安全摘要：

```text
record_ref
job_ref
expected_rule_count
actual_rule_count
status_counts
duplicate_rule_count
generic_placeholder_count
locatable_evidence_count
technical_error_count
```

严禁把患者姓名、病历正文、原始数据库 ID 写入报告。

**Step 2: 浏览器核对**

逐项确认：

1. 单病历“查看结果”只打开病历对照页；
2. 左侧文书目录与当前版本一致；
3. 中间默认打开入院记录；
4. 医嘱仍显示表格；
5. 右侧正好显示当前病历结果；
6. 确定问题没有泛化“发现问题”；
7. 018 能显示两个子结论和医学分析；
8. 025 能显示植入物缺失字段；
9. 007 能显示缺失的查房日期区间；
10. 017 能显示两份文书及相似度；
11. 点击证据定位到正确文书/章节；
12. 无证据时明确说明缺失边界；
13. 切换病历不会残留上一病历结果。

**Step 3: 反向用例**

- 无已保存结果：明确空态；
- 当前任务不包含病历：服务端拒绝；
- 多病历任务：只返回目标病历；
- 重跑任务：只显示当前代次；
- 结果少于 49 条：显示“结果不完整”，不伪装全量；
- 冲突结果：显示技术异常，不静默选择。

**Step 4: 完整质量门**

功能闭环完成后再运行：

```powershell
npm run check:encoding
npm run lint
npm run type-check
npm run test:unit
Set-Location backend
python -m pytest tests/unit/test_luxian_0609_record_result_read_model.py tests/integration/test_qc_sichuan_workspace_batch_flow.py -q
```

Expected: 全部通过；既有无关 warning 单独记录，不修改无关代码。

**Step 5: Commit**

```powershell
git add docs/reports/2026-07-29-lx0609-single-record-result-acceptance.md
git commit -m "文档：记录单病历质控结果验收证据"
```

## 四、完成标准

以下条件同时满足才允许替换正式入口：

- 左侧病历目录和中间原文/医嘱展示无行为回归；
- 单病历入口只调用新的单病历结果 API；
- 任意已保存病历不会打开其他病历结果；
- 一病历一规则最多一条客户结果；
- 选择 49 条时明确显示 `49/49`，不足时明确报警；
- 确定问题均具备原因、实际情况、标准和处理建议；
- 有文书证据时可以精确定位，不能定位时不猜测；
- 旧结果、旧规则版本和历史重跑不会覆盖当前结果；
- 当前结果冲突时显式技术异常；
- 真实持久化回读和浏览器验收均通过；
- 新入口稳定后删除单病历旧拼装路径，不永久双轨。

## 五、不在本计划内

- 重写 LX0609 49 条执行器；
- 修改模型或提示词；
- 新建 Evidence Graph、Ranking、Resolver、事件溯源或数据库表；
- 扩大到批量任务结果页；
- 默认启用会诊 020/023；
- 接入输血 041–049 新数据源；
- 为兼容所有历史 DTO 保留无限兜底。
