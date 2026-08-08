# 质控首页概览与病历池真实数据合同审计（Task 0）

**审计日期：** 2026-08-08
**审计范围：** 准商用前的真实病历数据、访问范围、稳定身份、资料同步状态、最新 LX0609 正式结果和首页统计来源。
**审计方式：** 只读代码链路、现有持久化合同和数据库基线核对；未修改生产代码、数据库或配置。
**冻结基线：** Git `45f9e5653083b8abf0cb2c0700b9197253dfd1cf`。

## 结论

当前系统**不具备直接接入多机构真实病历的权限隔离条件**。阻塞点不在质控引擎或 Bundle，而在病历池入口和结果读取入口缺少“当前用户 → 机构 → 授权科室/病历范围”的权威合同。

可以确认：

- CDM 和 LX0609 Canonical Envelope 都已使用 `institute_id + patient_id + visit_id` 三坐标；
- `custom_qc_batch_jobs → luxian_0609_record_result_envelopes` 已是单病历正式结果的权威交付链；
- 演示病历在生产环境仍可能因文件配置混入，属于可独立修复的确定性问题；
- 普通病历的单病历资料完整性没有可用的持久化事实；当前响应尚未提供 `source_state`，Task 2 若新增该投影只能先返回 `unknown`；
- 现有首页 KPI 和病历池部分统计都不能代表真实全量范围。

因此：

```text
Task 0：完成
Task 1A（生产环境关闭演示病历）：具备最小实施条件，但未自动授权
Task 1B（机构/科室隔离与三坐标身份）：阻塞，等待权威用户授权来源
Task 2（病历池全量摘要与最新结果投影）：阻塞，等待 Task 1B 及“全院最新正式结果”合同
首页/病历池 UI：不得开始
```

## 1. 冻结数据基线

| 项目                                  |                     结果 | 证据/说明                                      |
| ------------------------------------- | -----------------------: | ---------------------------------------------- |
| `cdm.mr` 病历                         |                   454 份 | 覆盖 10 个机构                                 |
| `public.mr` 病历                      |                    30 份 | 仅 1 个机构，不能代表多机构真实数据范围        |
| `luxian_0609_record_result_envelopes` |                   340 条 | 已持久化 Canonical 单病历结果                  |
| 普通病历 `sync_visit_status`          |                     0 行 | 不能作为病历池同步/完整性状态                  |
| 全局同步状态                          | `last_sync_status=never` | 仅能表达全局任务健康，不能表达单病历资料完整性 |

## 2. 当前资料与结果主链

```text
CDM mr（真实三坐标）
→ /api/medical-records/workstation
→ 当前病历池行

自定义质控任务 custom_qc_batch_jobs
→ 每病历 Canonical Envelope luxian_0609_record_result_envelopes
→ 单病历 latest-result API
```

这两条链可以在 Task 2 受控汇合，但前提是先完成机构/科室隔离和结果读取三坐标收紧。不得从 Scene/Domain Bundle、文书条数或前端列表推断资料完整性，也不得让浏览器逐条调用单病历结果 API。

## 3. 病历身份与关联风险

### 已确认的权威身份

`cdm.mr` 使用以下复合主键：

```text
institute_id + patient_id + visit_id
```

证据：[cdm.py](D:/LLM/LX888/apps/medqc-web/backend/app/database/models/cdm.py:127)。

LX0609 Envelope 在写入前也验证每病历的三坐标一致，并持久化 `institute_id/patient_id/visit_id`。证据：[custom_qc_workspace_service.py](D:/LLM/LX888/apps/medqc-web/backend/app/services/custom_qc_workspace_service.py:1416)、[custom_qc_workspace_service.py](D:/LLM/LX888/apps/medqc-web/backend/app/services/custom_qc_workspace_service.py:4459)。

### 当前首次异常层

病历池序列化仍返回：

```text
id = visit_id
```

证据：[query_service.py](D:/LLM/LX888/apps/medqc-web/backend/app/services/medical_records/query_service.py:64)。

同时，床位、出院摘要、质控状态与队列状态的部分查询或映射只按 `visit_id`、或 `(patient_id, visit_id)` 聚合。跨机构存在相同就诊号时，可能发生床位、出院信息或质控状态串值。

最新正式结果读取也存在同一类风险：`/workspace/records/{record_id}/latest-result` 只接收 `record_id`，任务和 Envelope 读取条件使用 `created_by + record_id/visit_id + 规则集版本`，没有使用表内已持久化的三坐标。当前 `record_id` 全部等于 `visit_id`；同一创建者下不同机构若出现相同 `visit_id`，读取路径会按完成时间选择较新的候选，不会因机构不同失败关闭。

证据：

- [qc_sichuan.py](D:/LLM/LX888/apps/medqc-web/backend/app/routers/qc_sichuan.py:4657)
- [custom_qc_workspace_service.py](D:/LLM/LX888/apps/medqc-web/backend/app/services/custom_qc_workspace_service.py:3653)
- [custom_qc_workspace_service.py](D:/LLM/LX888/apps/medqc-web/backend/app/services/custom_qc_workspace_service.py:4514)
- [record_result_read_model.py](D:/LLM/LX888/apps/medqc-web/backend/app/services/luxian_0609/record_result_read_model.py:73)

**结论：** `visit_id` 不能作为真实病历池或 latest-result 的稳定病历身份；`created_by` 只表达结果创建者边界，不能替代机构隔离。Task 1B 必须把病历池、详情和 latest-result 的所有关联范围收紧到三坐标，并向前端提供受控 `record_key`。

## 4. 权限与机构隔离

### 当前入口状态

病历池查询路由只接受筛选参数，未注入当前用户：

- [medical_records_query.py](D:/LLM/LX888/apps/medqc-web/backend/app/routers/medical_records_query.py:62)
- [query_service.py](D:/LLM/LX888/apps/medqc-web/backend/app/services/medical_records/query_service.py:416)

工作台首页虽然使用 `get_current_user`，但只将 `recipient_id` 用于通知过滤，不限制 CDM 病历的机构范围：

- [workstation.py](D:/LLM/LX888/apps/medqc-web/backend/app/routers/workstation.py:35)
- [worklist_service.py](D:/LLM/LX888/apps/medqc-web/backend/app/services/workstation/worklist_service.py:271)

### 当前用户合同

当前认证用户提供 `id`、`department`、`roles` 等字段；`sys_users` 没有可用于真实隔离的 `institute_id/hospital_id` 或多科室授权关系：

- [security.py](D:/LLM/LX888/apps/medqc-web/backend/app/core/security.py:74)
- [auth_store.py](D:/LLM/LX888/apps/medqc-web/backend/app/services/auth_store.py:111)
- [qc.py](D:/LLM/LX888/apps/medqc-web/backend/app/database/models/qc.py:15)

### 安全结论

不存在权威“用户 → 机构 → 科室范围”时，以下行为都不可接受：

- 按前端传入的 `institute_id` 放开查询；
- 因用户角色是 `admin` 或 `qc_manager` 就默认看所有机构；
- 只用登录用户的文本 `department` 推断授权科室；
- 只在前端隐藏不应显示的病历；
- 先保护病历池列表，却让详情或最新结果 API 按可猜测的 ID 越权读取。

**Task 1B 停止条件：** 医院接口方或身份系统必须提供可持久化、可审计的用户—机构归属，以及科室授权范围（如适用）。在此之前，病历池真实数据接入保持暂停。

## 5. 演示数据隔离

`/api/medical-records/workstation` 当前会读取演示病历构造器，并由可配置的 `include_demo_records` 决定是否与真实病历混合：

- [query_service.py](D:/LLM/LX888/apps/medqc-web/backend/app/services/medical_records/query_service.py:400)
- [frontpage_settings.py](D:/LLM/LX888/apps/medqc-web/backend/app/services/frontpage_settings.py:82)

环境默认值虽然在 `production` 时倾向关闭，但配置文件可显式写入 `include_demo_records=true`，从而重新打开演示病历。

**Task 1A 结论：** 可通过最小失败关闭规则修复：生产环境下无论文件配置如何均不返回 demo；开发/测试环境保持显式演示能力。该任务不依赖机构授权来源，但仍需用户单独批准后实施。

## 6. 资料同步与 `source_state`

| 候选来源            | 当前语义                                                     | 能否用于全院病历池 `source_state` |
| ------------------- | ------------------------------------------------------------ | --------------------------------- |
| `sync_visit_status` | 理论状态为 `PENDING/PARTIAL/SYNCED/STALE/FAILED`，当前无数据 | 否                                |
| `qc.sync_job_state` | 全局 ETL 任务健康                                            | 否，不能表示单病历资料状态        |
| `visit_index`       | 三坐标、场景与镜像时间                                       | 否，没有完整性语义                |
| 样本池状态          | `synced/missing/pending/synthetic_seeded`                    | 否，仅对样本池成员有效            |
| CDM 文书行数        | 存在性                                                       | 否，不能推断完整、部分或失败      |

证据：

- [sync.py](D:/LLM/LX888/apps/medqc-web/backend/app/database/models/sync.py:13)
- [etl_sync.py](D:/LLM/LX888/apps/medqc-web/backend/app/services/etl_sync.py:2685)
- [visit_index_service.py](D:/LLM/LX888/apps/medqc-web/backend/app/services/visit_index_service.py:48)
- [custom_qc_sample_pool_service.py](D:/LLM/LX888/apps/medqc-web/backend/app/services/custom_qc_sample_pool_service.py:3323)

**当前合同：** `/api/medical-records/workstation` 目前不返回 `source_state` 字段。Task 2 若增加该投影，普通真实病历只能返回 `source_state.status=unknown`；在同步系统提供逐病历持久化事实前，不得实现 `ready/syncing/partial/failed` 的筛选或统计。

## 7. 最新 LX0609 正式结果

### 已确认的权威链

```text
custom_qc_batch_jobs
→ luxian_0609_record_result_envelopes
→ 单病历 latest-result API
```

任务表提供任务状态、完成时间、规则集 key/version；Envelope 提供该任务该病历的 Canonical 交付结果：

- [qc_sichuan.py](D:/LLM/LX888/apps/medqc-web/backend/app/routers/qc_sichuan.py:4273)
- [custom_qc_workspace_service.py](D:/LLM/LX888/apps/medqc-web/backend/app/services/custom_qc_workspace_service.py:4430)
- [record_result_read_model.py](D:/LLM/LX888/apps/medqc-web/backend/app/services/luxian_0609/record_result_read_model.py:73)

单病历最新结果读取只选择：同一创建者、完成态、根任务、当前 `rule_set_key/version`，按 `finished_at/created_at` 倒序；并列时失败关闭。它不回退任务 `items_json`。但当前选择和 Envelope 读取仍只按 `created_by + record_id/visit_id`，没有把三坐标加入条件，因此不能作为多机构安全读取合同。

### 可安全投影的字段

- 是否存在当前版本的正式结果；
- `job_id/root_job_id`、规则集 key/version、完成时间、结果数量；
- Envelope 内各规则状态的数量：`non_compliant`、`data_gap`、`technical_error`、`uncertain`、`compliant`、`not_applicable`；
- `data_gap`、`technical_error`、`non_compliant` 三类分别统计。

### 仍需业务/权限合同确认的部分

当前“最新结果”选择包含 `created_by`，是单病历客户结果交付合同，而不是全院病历池合同；它也不能隔离同一创建者下跨机构同 `record_id/visit_id` 的候选。准商用全院视图必须先明确：

```text
同一病历被不同授权用户执行多次时，谁拥有“全院最新正式结果”？
```

在该口径确认前，Task 2 不得简单去掉 `created_by` 条件，也不得从任务 JSON 文本中按 `LIKE` 反向猜测最新结果。

## 8. 首页与病历池统计真实性

| 页面               | 当前来源                            | 首次异常层                                | 结论                                      |
| ------------------ | ----------------------------------- | ----------------------------------------- | ----------------------------------------- |
| 病历池             | `MedicalRecordFrontpage` 服务端分页 | 前端从当前页 `workbenchRows` 计算多项 KPI | 不可用于真实全量统计                      |
| 病历池科室 warning | 当前页 QCResult 映射                | 未覆盖非当前页                            | 不可用于全量科室风险                      |
| 首页热点           | 当日通知 + 工作流记录               | `hotspot_limit` 截断后再计算 KPI          | KPI 不可信                                |
| 首页待办           | 工作流记录                          | `todo_limit` 截断后再计算 KPI             | KPI 不可信                                |
| 首页趋势           | 前端静态 SVG/固定文本               | 前端展示层                                | 真实数据接入前必须移除                    |
| 首页 KPI 环比      | 固定 `+12/+5/+3/-6` 及百分比文案    | 前端展示层                                | P1 伪统计，必须移除或改为服务端真实比较值 |
| 首页 LX0609 结果   | 未读取 Envelope                     | 服务端聚合合同缺失                        | 不能称为全病历质控首页                    |

关键证据：

- [WorkstationV4ListView.vue](D:/LLM/LX888/apps/medqc-web/src/views/workstation-v4/components/WorkstationV4ListView.vue:339)
- [QCOverviewView.vue](D:/LLM/LX888/apps/medqc-web/src/views/workstation/QCOverviewView.vue:457)
- [worklist_service.py](D:/LLM/LX888/apps/medqc-web/backend/app/services/workstation/worklist_service.py:800)

其中首页四张 KPI 的 `+12（10.3%）`、`+5（16.1%）`、`+3（20.0%）`、`-6（7.5%）` 并不来自接口或真实比较期，是面向客户的独立展示层 P1；不能仅以“趋势静态”概括。

## 9. 后续任务冻结结论

### Task 1A：可以单独审批

候选白名单：

```text
backend/app/services/frontpage_settings.py
backend/app/services/medical_records/query_service.py
backend/tests/unit/test_frontpage_settings.py
backend/tests/unit/test_workstation_query_service.py
```

必须锁定：生产环境即使配置 `include_demo_records=true` 也不返回 demo；开发/测试显式演示模式不回归。

### Task 1B：当前阻塞

等待医院或身份系统提供：

```text
用户 ID → institute_id
用户 ID → 一个或多个授权科室（如适用）
跨机构管理员的明确授权关系（如适用）
```

收到该合同后，再冻结数据库迁移、认证服务、病历池路由、详情/结果入口和测试的准确白名单。禁止先实现“默认全院”或“前端筛选”版本。

Task 1B 的必审影响路径至少包括：

```text
backend/app/routers/medical_records_query.py
backend/app/services/medical_records/query_service.py
backend/app/routers/qc_sichuan.py                         # latest-result 路由
backend/app/services/custom_qc_workspace_service.py        # 任务与 Envelope 读取
backend/app/services/luxian_0609/record_result_read_model.py
```

最终是否修改这些文件取决于权威身份源接入方式；但不得只修病历池列表而遗漏 latest-result 的三坐标和机构范围校验。

### Task 2：当前阻塞

启动前必须同时满足：

1. Task 1B 已实现并通过跨机构/跨科室越权测试；
2. Task 1B 已将 latest-result 的路由、任务选择和 Envelope 读取收紧为三坐标，`created_by` 不再承担病历身份隔离；
3. 客户确认全院最新正式结果的选择口径，尤其是跨 `created_by` 的所有权；
4. 单病历同步状态仍保持 `unknown`，或同步系统提供逐病历权威状态。

Task 2 只能增加既有病历池的服务端最新结果摘要投影；不得修改 Canonical/Envelope、规则引擎、Bundle 或新建结果表。

## 10. 恢复实施所需的用户决策

1. 真实上线的身份源是什么，能否提供用户到机构、科室授权的结构化映射？
2. 首页/病历池的“最新正式质控结果”是否以机构共享任务为准，还是仅显示当前创建者的任务？
3. 在同步系统补齐逐病历状态前，是否接受病历池统一显示“资料同步状态：暂不可判定”？

在这三项未明确前，当前任务正确结束于 Task 0，不应开始真实数据 UI 或全院统计开发。
