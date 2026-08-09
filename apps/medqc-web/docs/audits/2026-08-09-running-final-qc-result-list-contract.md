# 运行病历与终末病历质控结果清单：数据合同冻结

日期：2026-08-09  
范围：仅冻结运行/终末病历质控结果清单的既有资料链、筛选与动作边界；不修改生产代码。

## 结论

可以进入“只读单行结果清单”的实现：正式病历池已经以三坐标返回病历、以服务端 `hospital_status` 区分在院/已出院，并投影当前 LX0609 规则集的最新已完成 Canonical 结果摘要。

不能在本期开放“开始质控/重新质控”：当前四川规则批任务请求和后端选中记录参数均为 `record_ids: string[]`，它们被解释为 `visit_id`。该入口不能表达或验证同一 `visit_id` 下的不同 `institute_id + patient_id`，与清单三坐标身份合同不一致。新清单在 Task 1--3 只能展示结果；Task 4 需单独接入真实三坐标执行入口后再开放操作。

## 1. 旧页面不是单行质控结果清单

| 页面                        | 现有证据                                                                                                                                                                                                 | 审计结论                                                                                 |
| --------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------- |
| `RunningRecordsViewNew.vue` | 同时维护 `records / defects / remediation` 三个视图（`currentView`），包含 `CreateTaskModal`、`RemediationPanel`、缺陷批量派发和导出；每行还可跳转“生成首页、编码质控、首页质控、结算质控、自定义质控”。 | 这是旧的病历、缺陷和整改工作台，不符合“每病历一行、只看质控结果”的页面合同。             |
| `FinalRecordsView.vue`      | 包含规则选择弹窗、`SemanticRulesBatchPanel`、任务详情/调试抽屉、`QCReviewDrawer`、自定义质控及首页/编码/结算跳转。                                                                                       | 这是终末批任务操作台，不是只读结果清单。                                                 |
| 路由                        | workstation-v4 的 `/records/running`、`/records/final` 仍直接指向上述两个旧页面。                                                                                                                        | Task 1 只替换这两个 workstation-v4 路由为共享清单视图；不删除旧页面及旧 Dashboard 路由。 |

精确证据：

- `src/views/dashboard/records/RunningRecordsViewNew.vue:222-275, 440-475, 535-605, 667-735`
- `src/views/dashboard/records/FinalRecordsView.vue:178-245, 353-389, 456-489, 624-644, 778-805`
- `src/router/index.ts:991-1000`

## 2. 正式病历池资料合同

唯一清单入口为 `GET /api/medical-records/workstation`，路由调用 `get_workstation_data`。它返回当前筛选全集的 `qc_summary` 与本页 `records`，不应回读旧 `QCResult`、旧批任务 `items` 或 Bundle。

### 2.1 每行可用字段

| 需求             | 可用字段                                                           | 依据/语义                                                                                                                         |
| ---------------- | ------------------------------------------------------------------ | --------------------------------------------------------------------------------------------------------------------------------- |
| 唯一身份         | `recordKey`，并同时返回 `instituteId`、`patientId`、`id`/`visitId` | 服务端把三坐标 JSON 序列化为 `recordKey`；三坐标不完整的记录不会进入响应。前端仅把 `recordKey` 用作行键，不能把它替代 `visitId`。 |
| 患者             | `name`、`id`（访问号）、`patientId`                                | 姓名、访问号及患者标识来自正式病案首页记录。                                                                                      |
| 科室、床位       | `department`、`bedNo`                                              | 科室优先出院记录，再回退首页；床位来自入院记录。                                                                                  |
| 入出院、最近更新 | `admissionDate`、`dischargeDate`、`updateTime`、`sortTime`         | 出院时间优先权威出院记录，再回退首页；在院/出院筛选也使用这一解析后的出院时间。                                                   |
| 单病历质控摘要   | `latest_qc_summary`                                                | 只投影当前 LX0609 规则集、当前版本、最新完成根任务的一份有效 Canonical Envelope。                                                 |
| 全集汇总         | `qc_summary`                                                       | 对服务端完整筛选全集聚合，不能由当前分页行数计算。                                                                                |
| 同步资料状态     | `source_state`                                                     | 当前固定为 `{ status: "unknown", last_sync_at: null, reason_code: null }`；它不能被文书数推断为完整。                             |

精确证据：

- `backend/app/services/medical_records/query_service.py:32-36, 85-176, 179-191, 730-750, 941-948`
- `src/views/workstation-v4/types.ts:3-59`
- `src/views/workstation-v4/normalize.ts:147-200, 204-235`

### 2.2 Canonical 状态与失败语义

`latest_qc_summary.status` 只有三种外层状态：

| 外层状态          | 清单含义                                         | 规则级状态处理                                                                                                                           |
| ----------------- | ------------------------------------------------ | ---------------------------------------------------------------------------------------------------------------------------------------- |
| `ready`           | 有一份通过结构校验的最新 Canonical 结果          | 读取 `status_counts` 中的 `non_compliant`、`data_gap`、`uncertain`、`compliant`、`not_applicable`、`not_executed` 等，前端必须分开展示。 |
| `not_run`         | 没有可按三坐标确认的当前版本结果                 | 显示“未质控/暂无结果”，不能显示成合规或资料缺失。                                                                                        |
| `technical_error` | 当前版本生成冲突、缺少 Envelope 或 Envelope 无效 | 显示“结果校验异常/技术异常”，不计入临床问题。                                                                                            |

Canonical 读取在如下场景失败关闭：当前版本生成冲突、较新任务缺 Envelope、同一选择任务有多个 Envelope、Envelope 缺 `rule_id` 或重复规则项。缺乏三坐标身份的历史任务不可进入 `ready`。

精确证据：

- `backend/app/services/custom_qc_workspace_service.py:3853-3865, 4034-4133, 4137-4180`
- `backend/app/services/medical_records/query_service.py:194-230`

## 3. 服务端筛选可用性

| 清单筛选项   | 当前是否可用         | 服务端参数/实际语义                                                                                     | 本期限制                                                                                                  |
| ------------ | -------------------- | ------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------- | ------------------------------------------------------ | ---------- | ------------------------------------------------------------------------ |
| 在院/已出院  | 可用                 | `hospital_status=inpatient                                                                              | discharged`；以权威解析后的出院时间是否存在判定。                                                         | 运行和终末页面必须固定传此参数，不能在当前页本地过滤。 |
| 科室         | 可用                 | `dept`，与解析后的科室名称精确匹配。                                                                    | 选项来自同一服务端筛选范围的 `departments`。                                                              |
| 日期         | 可用                 | `start_date`、`end_date`、`date_field=visit                                                             | admission                                                                                                 | discharge                                              | updated`。 | 页面明确显示当前日期字段；运行页默认入院、终末页默认出院仅是 UI 默认值。 |
| 关键词       | 可用                 | `keyword`，搜索姓名、病案号 `mr_no`、住院号 `inpat_no`。                                                | 不是全文、医生或文书内容搜索。                                                                            |
| 病区         | 不可用               | `/workstation` 没有 ward 参数或字段。                                                                   | Task 1 不显示病区筛选，不能以前端床位或科室伪造病区。                                                     |
| 质控结果状态 | 不可用作通用列表筛选 | 只有统计下钻专用 `analytics_result_status`，且必须随已完成根任务、时间范围、规则等 analytics 合同使用。 | Task 1 不显示“质控结果”筛选；若产品必须提供，需另立 API 合同，直接基于 Canonical 结果按三坐标服务端筛选。 |

精确证据：

- `backend/app/routers/medical_records_query.py:64-112`
- `backend/app/services/medical_records/query_service.py:469-534, 555-602, 785-824`
- `src/views/workstation-v4/composables/usePatientRecords.ts:83-156`

## 4. 当前质控启动入口：禁止接入清单

前端 `createSichuanWorkspaceBatchJob` 的 payload 只有 `record_ids?: string[]`；后端 `SichuanWorkspaceBatchJobCreateRequest` 同样只声明 `record_ids: Optional[List[str]]`。创建任务时，后端选取记录、构造 `effective_record_ids` 及后续任务快照均取 `record_id` 或 `visit_id`，没有三坐标选中集合。

因此，下列情况不能被现有公开入口安全表示：

```text
record A: institute_id=A, patient_id=P1, visit_id=V
record B: institute_id=B, patient_id=P2, visit_id=V
```

选择 A 的 `record_ids=[V]` 会把 `visit_id=V` 作为单键处理，无法保证不选中 B。清单不得把 `recordKey` 拆解或回退为 `visit_id` 来调用此接口。

结论：

- Task 1--3：隐藏选择框、批量开始质控和“重新质控”；页面用明确说明“质控任务创建能力待接入”。
- Task 4：只有后端任务创建、任务持久化、执行和结果回写都接受并验证 `[{ institute_id, patient_id, visit_id }]`，并有同 visit 不同三坐标的失败关闭回归后，才允许开放操作。
- 既有接口仍可被旧终末任务页使用；本审计不改变其行为。

精确证据：

- `src/services/sichuan-rule-workspace-service.ts:45-72`
- `backend/app/routers/qc_sichuan.py:470-488, 4272-4425`
- `backend/app/services/custom_qc_workspace_service.py:2485-2559, 3160-3250`

## 5. 后续任务的严格边界

| Task               | 允许范围                                                                                                 | 禁止范围                                                                 | 通过条件                                                             |
| ------------------ | -------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------ | -------------------------------------------------------------------- |
| Task 1             | 创建共享单行结果清单视图和表格；两个 workstation-v4 路由仅用 `carePhase` 固定 `hospital_status`。        | 不接任务创建，不修改后端、Canonical、Bundle、规则或旧页面。              | 每条病历唯一一行，行键为 `recordKey`，旧多功能入口在 DOM 中不存在。  |
| Task 2             | 用现有 `usePatientRecords` 正式接口映射三坐标、时间、`latest_qc_summary`、`qc_summary`、`source_state`。 | 不由分页行数汇总；不回读 legacy `QCResult`；不新增资料链。               | 运行/终末服务端范围、行身份、最近结果与 API 一致；顶端汇总跨页稳定。 |
| Task 3             | 新建只读质控详情抽屉，显示 Canonical 安全结果、现有可定位证据及文书目录。                                | 不展示首页/编码/结算/DRG/DIP/自定义质控、Prompt、原始模型输出或 Bundle。 | 同 `visit_id` 不同三坐标仍打开正确详情；身份冲突失败关闭。           |
| Task 4（条件任务） | 仅在真实三坐标任务创建入口完成后，接入选择、批量开始和单条重新质控。                                     | 不用 `record_ids=visit_id` 兼容代替；不前端循环伪造任务。                | 后端到回写全链三坐标，冲突整批零 API/零运行态写入，真实回归通过。    |

## 6. 可复现只读验证

```powershell
$CodeGraph = 'C:\Users\Coldplay\AppData\Roaming\npm\codegraph.cmd'
& $CodeGraph explore 'RunningRecordsViewNew FinalRecordsView get_workstation_data build_luxian_0609_completed_record_result_summaries createSichuanWorkspaceBatchJob'

rg -n -C 4 "def get_workstation_data|hospital_status|latest_qc_summary|qc_summary|source_state" backend/app/services/medical_records/query_service.py
rg -n -C 4 "build_luxian_0609_completed_record_result_summaries|canonical_envelope" backend/app/services/custom_qc_workspace_service.py
rg -n -C 4 "record_ids|create_workspace_batch_job" backend/app/routers/qc_sichuan.py src/services/sichuan-rule-workspace-service.ts
```

## 风险保留

1. `source_state` 当前只能诚实显示 `unknown`；不能把“病历池有文书”解释成同步完成。
2. 病历池的旧 `status` 仍来自 legacy `QCResult`，新清单不得用它表示 LX0609 结论，应只读 `latest_qc_summary`。
3. 质控状态筛选尚未具备独立的服务端 Canonical 合同；本期不做该筛选，避免前端分页假筛选。
4. 正式环境的演示病历策略已由先前 Task 1A 关闭；本任务未改该策略，验收时仍应以生产配置确认无演示数据。
