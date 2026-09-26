# V3.6 病历级操作记录时间线合同（P0-4）

> 日期：2026-09-27。对应 PRD“病历级操作与操作记录”。时间线只做装配和排序，每个事实仍由原来的 owner 负责，装配层不重新判定任何状态。

## 1. 事件来源（均按 `institute_id/patient_id/visit_id` 三坐标精确匹配）

| type | 来源 owner | 时间 | 操作人 | 摘要字段 |
|---|---|---|---|---|
| `qc_run_completed` | `luxian_0609_record_result_envelopes`（结果对象）join `custom_qc_batch_jobs` | Envelope `updated_at` | job `created_by` | job_id、rule_set_version、result_count；若 job filters 含 task_id/task_run_number 则附带 |
| `record_review` | `qc_record_reviews` | `created_at` | `reviewer_id` | review_context、stage、decision、reason、job_id、task_id |
| `manual_defect_created` | `qc_defects`（人工谓词）+ `qc_defect_history` 中的 `manual_create` | 历史 `created_at` | 历史 `actor_id` | defect_id、rule_name、task_id、run_number |
| `manual_defect_reviewed` | `qc_defect_history` 中的 `manual_review_approved/rejected` | 历史 `created_at` | 历史 `actor_id` | defect_id、decision、reason |
| `task_record_completed` | `qc_task_records`（由任务病历完成服务写入 `completed_at`） | `completed_at` | `assignee_id` | task_id、task_record_id、completed_run_number |

- 人工缺陷只取与审核接口相同的谓词：`origin='manual' AND source_key='task_assigned_qc' AND identity_version=1`。
- 自动缺陷的历史不进入时间线（旧入口的身份尚未核实）。
- `qc_task_records.started_at` 目前没有任何代码写入，不作为事件来源（读取没有 owner 的列会误导，缺列的库还会导致 503）；“开始处理”事件等有权威写入方后再加入。
- 操作人显示名：按 id 批量读取 `sys_users.display_name`，一次查询；读不到时给 `actor_name=null`，前端显示 id。

## 2. 接口

`GET /api/v1/record-operations/case?institute_id&patient_id&visit_id&limit=100`

- 权限：`QC_RESULTS.REVIEW`（admin/qc_manager），与抽屉审核面板一致，没有权限返回 403。
- 响应 `data`：
  - 顶层回显 `institute_id`/`patient_id`/`visit_id`，供前端校验返回的是当前病例；
  - `items`：`[{id, type, occurred_at, actor_id, actor_name, summary:{...}}]`，按 `occurred_at` 倒序，同一时间再按 `id` 排序，保证顺序稳定；
  - `total`：精确总数；
  - `limit`：上限 100，最大 200。
- 事件 `id` 是来源前缀加来源行主键，例如 `review:<id>`、`envelope:<id>`、`defect_history:<id>`、`task_record:<id>:started`。
- 失败语义：三坐标非法返回 422；数据库故障返回固定脱敏的 503。任一来源读取失败，整个请求返回 503，不返回“只缺一部分”的时间线，避免被误读为完整记录。

## 3. 前端

- 结果抽屉内，在人工缺陷区块下方增加“操作记录”区块，显示条件与审核面板相同。
- 按时间倒序展示：时间、类型中文名、操作人（有显示名用显示名，否则用 id）、摘要。
- 403 时隐藏；失败时显示可重试，不显示为“无记录”；切换三坐标时丢弃迟到响应。
- `total > items` 时提示“仅显示最近 N 条”。

## 4. 不在本批

- 催办和医生通知：依赖医生—用户映射，属于外部阻塞。
- “改评分标准”：没有评分标准的权威 owner。
- 自动缺陷的操作历史：旧入口身份未核实。
