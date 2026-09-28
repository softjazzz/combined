# V3.6 测试病历真实化合同（P1-E3）

> 日期：2026-09-27。对应 PRD 第 6 节中的测试病历列表、新建、导入、编辑、查看应用质控点。

## 1. 证据

- `records/test` 页面（`services/test-medical-records.ts`、`stores/testMedicalRecords.ts`）全部是 mock，没有 HTTP 请求。
- `views/medical-records/*` 走旧病历表，不以三坐标为身份，不能作为落点。
- 已有真实链：
  - 创建：`POST /api/v1/qc/sample-pools/test-records` 写入 CDM 三坐标（`CUSTOMER_TEST` 机构）和文书，并挂到固定池 `customer-created-test-records-v1`；前端对应 `SyntheticCaseBuilderView`。
  - 派生可编辑副本：`source=customer_source_editable_copy`。
  - 查看文书：`/api/v1/emr/{visit_id}/documents` 与 `render`，只读。
  - 运行：`POST /{pool_id}/run`，按 `record_refs` 和 `selected_rule_ids`。
  - 看结果：workspace `latest-result`。
- 条目表 `manual_problem_sample_pool_items` 已有 `candidate_rule_ids_json`、`include_in_batch_1`、`exclude_reason`。

## 2. 合同（复用现有链，不新建平行存储）

**列表**：`GET /api/v1/qc/sample-pools/test-records`

- 只列固定池中未移除的条目，分页并给精确 total。
- 字段：条目 id、三坐标、患者名、科室、文书数、关联质控点数、`latest_job_id`、创建时间、来源（新建或派生），以及 `superseded_by` / `removed` 标记。
- 查询参数 `include_removed=true` 时同时列出已移除和已被替换的条目。

**关联质控点**：`PUT /api/v1/qc/sample-pools/test-records/{item_id}/rules`

- 请求体 `{rule_ids, updated_at}`，用 CAS 防并发覆盖。
- 规则必须属于当前规则集版本的全部规则（`resolve_rule_set_version` 的 active、paused、excluded 合集），否则返回 422。
- 写入 `candidate_rule_ids_json`，同时更新 `raw_payload_json` 中的 `selected_rule_ids`，保持一致。

**移除**：`DELETE /api/v1/qc/sample-pools/test-records/{item_id}?updated_at=`

- 软删除：`include_in_batch_1=false`，`exclude_reason='test_record_removed'`。
- 不删除 CDM 行，因为已跑的结果仍需要可追溯。

**编辑**：复用派生可编辑副本创建新病历。

- 新条目通过 `raw_payload_json.source.item_id` 指向旧条目。
- 旧条目标记为 `exclude_reason='superseded_by:<new_item_id>'`，并设为不纳入。
- 不在原地修改 CDM 文书，避免破坏已发布的 Bundle 和历史结果。

**运行与结果**：

- 对单条或多条测试病历运行其关联质控点（或临时勾选的规则），走现有 `/{pool_id}/run`。
- 结果用现有的结果抽屉查看。

**权限**：沿用样本池现有路由的权限写法。

## 3. 阻塞（缺权威数据，只标注不做）

- **预期结果比对**：`golden_answers` 只写入、从未读取，也没有权威来源。
- **含文书的 Excel 导入**：没有客户模板；现有导入只产出样本行。
- **文书类型 `other` 的归属**：目前被映射到日常病程，需客户确认口径。
- **新建质控点时的测试病历验证**：新质控点需先有执行器实现。

## 4. 2026-09-28 简单项收口：76 导出与 78 复制

- 本批仅补齐固定测试池的勾选导出和单例复制，不扩展质控引擎、真实来源池或数据库模型；前述导入阻塞是历史记录，当前以已实现的 V3.6 Excel 导入合同为准。
- `POST /api/v1/qc/sample-pools/test-records/export` 接收 `item_ids`（1–20 条），服务端核验固定池有效条目，生成现有模板版本的 XLSX。越界或不能完整表示的数据明确失败，不截断、不把结果报告冒充病历文件。验收包含现有导入解析器回读和 Excel 公式防护。
- `POST /api/v1/qc/sample-pools/test-records/{item_id}/copy` 接收源 `updated_at` 和可选名称，核对有效源条目后复用创建流程。保留基本信息、文书及关联质控点，生成新三坐标；不携带替换标记，不修改源条目，不复制历史任务和质控结果。
- 两项沿用管理员/质控经理权限与操作审计。前端使用真实响应，失败不显示成功，复制成功刷新列表；资料尚未准备完成时如实提示。
- 代码验收与隔离 PostgreSQL、业务库部署、浏览器验收分开记录；本批没有数据库写入或推送授权。
