# V3.6 病历审核与人工缺陷审核合同（P0-1）

> 日期：2026-09-26。用户已确认：病历初审/复审的权威 owner 绑定“一次已保存、含来源与三坐标的质控结果”，初审/复审独立保存并记事务事件。

## 1. 证据与边界

- 仓库此前没有病历级初审/复审的表、列或服务；`dashboard_api.py` 的 `record_stats.pending_review/pending_recheck` 与 `defect_stats.pending_review` 固定为 NULL。
- 内涵质控（LX0609）的结果保存在 `luxian_0609_record_result_envelopes` 中，由 `root_job_id` 和三坐标定位。同一 job 重试或父任务刷新时，Envelope 会先删后插，行 `id` 也会随之变化。因此审核必须同时绑定 `job_id` 和当时的 Envelope 行 `id`：行 id 变了，就说明审核对象已被替换。这里不另加哈希。
- 人工缺陷（`origin='manual'`、`source_key='task_assigned_qc'`）已有独立的 `manual_review_status`。旧的 `/defects/approve|reject` 本身就排除人工缺陷，而且没有旧状态 CAS，这次不复用。申诉复核继续由 `qc_appeals` 负责，两者不混用。
- 本批不负责以下事项，它们仍由各自原来的 owner 负责：任务病历“处理完成”、自动质控结论、缺陷整改状态、申诉。本批也不改质控引擎和结果选择器。

## 2. 病历审核（任务受领范围）

### 2.1 存储：`qc_record_reviews`（`qc`、`public` 双建，迁移 57）

只追加、不修改。每一行就是一次审核决定，本身即事务事件。

| 列 | 约束 |
|---|---|
| `id` | VARCHAR(36) 主键 |
| `request_id` | VARCHAR(36) 非空且唯一，用于客户端幂等 |
| `institute_id`/`patient_id`/`visit_id` | VARCHAR(128) 非空、非空白 |
| `rule_set_key`/`rule_set_version` | VARCHAR(96) 非空 |
| `job_id` | VARCHAR(36) 非空，指 root job |
| `envelope_id` | VARCHAR(36) 非空，指审核时的 Envelope 行 id |
| `task_id`/`task_record_id`/`run_number` | 非空，记录决定发生在哪个任务上下文 |
| `stage` | `initial` 或 `recheck` |
| `decision` | `approved` 或 `doubtful` |
| `reason` | TEXT；`doubtful` 时必须非空白 |
| `reviewer_id` | VARCHAR(64) 非空 |
| `created_at` | 非空 |

唯一约束为 `(job_id, envelope_id, institute_id, patient_id, visit_id, rule_set_key)`：同一个结果对象只能有一个决定，而且决定不可更改。要推翻结论，只能重质控，产生新的结果对象。

### 2.2 状态推导（只由服务端计算，前端原样展示）

对任务病历当前受领运行的结果对象 R，即 `(job_id, envelope_id, 三坐标, rule_set)`：

- R 已有决定：状态为 `approved` 或 `doubtful`。
- R 没有决定：取同一三坐标、同一 `rule_set_key` 在其他结果对象上的**最近一次**决定。
  - 若为 `doubtful`，状态为 `pending_recheck`，此时提交的决定 `stage=recheck`；
  - 否则状态为 `pending_review`，此时提交的决定 `stage=initial`。
- 结果不可用：`result_state != available`，或 Envelope 不存在或不唯一，或规则集不是 LX0609。此时状态为 `unavailable`，并返回原因码，不能提交决定。

### 2.3 接口

- `GET /api/v1/tasks/{task_id}/records/{task_record_id}/review?run_number=N`
  - 返回：`state`、`stage`、`current`（当前决定，没有则为 null）、`history`（该三坐标和规则集下的历史决定，按时间倒序，最多 50 条）、`result`（`job_id`、`envelope_id`）。
- `POST` 同一路径
  - 请求体：`{run_number, decision, reason?, request_id, envelope_id}`。
  - 权限：仅限当前受领人（`assignee_id`），任务和任务病历均为 `in_progress` 或病历已 `completed`，所用运行是本人的 assigned 运行。
  - 事务内依次执行：
    1. 加事务级 advisory lock，锁键按三坐标 + 规则集生成；
    2. 重新核对任务、关联、运行、job，并确认 Envelope 恰好 1 行且其 `id` 等于请求中的 `envelope_id`（不一致返回 409 `result_changed`）；
    3. 计算 `stage` 并插入一行决定。
- 幂等：同一 `request_id` 且内容相同时返回原结果；内容不同返回 409。
- `GET /api/v1/record-reviews/todo?stage=initial|recheck&page&page_size`
  - 返回本人受领、任务进行中、最新本人 assigned 运行结果可用且尚无决定的病例，分页并给出精确 `total`。
  - 规则集不支持的病例不计入。

### 2.4 失败语义

| 情况 | 返回 |
|---|---|
| 无权限或非受领人 | 403 |
| 任务或病历不存在 | 404 |
| 状态不符、结果已变化、已有决定、幂等冲突 | 409（带 `code`） |
| 数据库或数据源故障 | 固定脱敏 503 |

任何失败都不写入部分数据。存疑后的“医生通知”依赖医生—用户映射，目前缺失，标为外部阻塞：本批不发送通知，也不伪造通知成功。

## 3. 人工缺陷审核

- `GET /api/v1/manual-defects?review_status=pending|approved|rejected&page&page_size`
  - 需要 `QC_RESULTS.REVIEW` 权限（qc_manager/admin）。
  - 只返回 `origin='manual' AND source_key='task_assigned_qc' AND identity_version=1` 的行，给出精确 `total`。
  - 字段白名单：id、三坐标、task_id/task_record_id/run_number（取自 `manual_create` 历史）、rule_code/rule_name/description/severity/location/suggestion、`manual_review_status`、`manual_created_by`、created_at。
- `POST /api/v1/manual-defects/{defect_id}/review`
  - 请求体：`{decision: approved|rejected, reason?, expected_status: 'pending'}`；`rejected` 时 `reason` 必须非空白。
  - 需要 REVIEW 权限，且审核人不能是创建人（否则 403）。
  - 用行锁执行 `UPDATE ... WHERE manual_review_status='pending'`，同一事务里追加 `manual_review_approved` 或 `manual_review_rejected` 历史（含 reason 和 reviewer）。
  - 状态已不是 pending 返回 409；非人工缺陷或不存在返回 404。
  - 不写旧的 `approved_*`/`rejected_*`（那是整改审核的列），不改 `status`，也不改任务、评分或病历审核。

## 4. 待办

`/todo-stats`：

- `record_stats.pending_review`、`pending_recheck` 取第 2.3 节待办接口的本人精确计数。
- `defect_stats.pending_review`：有 REVIEW 权限时取人工缺陷 pending 的精确计数；没有权限时仍为 NULL，前端显示“不可用”。
- 任一计数失败时，整体沿用现有的 503 语义。
- 下钻分别进入病历审核待办列表和人工缺陷审核列表，并保留 `stage`/`review_status` 筛选。

## 5. 验收

- 迁移 57 在隔离库按序执行，并回读双 schema 的列、约束和唯一索引。
- 使用 PG 合成数据验证：初审通过；初审存疑后重质控，出现待复审，复审通过；Envelope 被重写后返回 409；并发重复提交只成功 1 次；非受领人被拒；人工缺陷审核的 CAS、禁止自审、驳回必须填写原因。
- 待办计数和下钻列表使用同一谓词，数量一致。
