# V3.6 任务分配策略合同（P1-D）

> 日期：2026-09-27。对应 PRD 第 4 节“任务分配：原质控员、科室、比例、病历类型”。

## 1. 证据

- `task_assignment_service.assign_task_records` 只实现了 `by_ratio`：按 `created_at, id` 顺序平均切分，任务行锁下写入，已分配时按同一计划做幂等校验。
- 创建时的校验（第五十九批）拒绝 `keep/by_department/by_type`。
- `qc_task_records` 有 `record_type`、`scene`，没有科室列。
- 在院候选（`case_scope`）和门急诊候选在抽样时都带 `department`，但没有持久化。
- 病历审核决定表 `qc_record_reviews` 是“谁审核过该病历”的权威来源。

## 2. 新增策略

| method | 规则 | 失败语义 |
|---|---|---|
| `by_original_reviewer` | 每条任务病历取同一三坐标在 `qc_record_reviews` 中**最近一次**决定的 `reviewer_id`（任意上下文、任意规则集）。如果此人在本次选定的受领人中，就分给他。 | 有病历没有原质控员，或原质控员不在选定人中时，按请求参数 `fallback` 处理：`by_ratio` 表示剩余病历在选定人中按比例分配；`reject` 表示返回 409 `original_reviewer_unmatched`，并附不匹配的病历数。`fallback` 必填。 |
| `by_department` | 每条病历的 `department`（抽样时持久化）与受领人 `sys_users.department` 精确相等。同一科室有多名受领人时，在该科室内按比例分配。 | 任一病历没有科室返回 409 `department_missing`（历史任务或来源缺科室）；有科室没有对应受领人返回 409 `department_unassigned`，并列出这些科室。 |
| `by_record_type` | 不实现。当前可抽样的场景（显式在院运行、门急诊）同一场景内病历类型相同，没有可区分的权威事实。 | 创建时返回 422 `method_unavailable`，并附原因。 |

- **计划的确定性**：先按 `created_at, id` 排序；原质控员按最近一次决定的 `created_at, id` 取；按比例的剩余部分沿用现有切分算法。
- **幂等**：任务已经是 `assigned` 时，如果 `assign_method` 与请求一致，直接返回现有分配汇总（`idempotent=true`），不再重新计算，因为审核数据可能已经变化；方法不一致返回 409。
- **校验**：受领人仍须是在职的质控员。任务行锁和逐行 CAS 写入都与现有实现相同。

## 3. 存储（迁移 60，`qc`/`public` 双建）

- `qc_task_records` 增加 `department`：VARCHAR(100)，可空，无默认值，历史行保持 NULL。
- 抽样持久化（`task_sampling_persistence`）把候选的 `department` 去空白后写入，空字符串写成 NULL。

## 4. 创建与接口

- 任务创建请求的 `assign_method` 允许取 `by_ratio`、`by_original_reviewer`、`by_department`。
- `by_original_reviewer` 需要在 `assignee_config.fallback`（复用任务已有的 `assignee_config` 字段，不新增平行字段） 中给出 `by_ratio` 或 `reject`。
- `by_record_type` 以及其他值仍返回 422，并且不写入任务。
- 分配接口沿用现有路径，入参新增 `fallback`（仅 `by_original_reviewer` 使用）。
- 响应中的 `assignment_details` 增加 `reason_counts`，统计每人通过哪种途径获得病历：`original_reviewer`、`department`、`ratio_fallback`。

## 5. 前端

- 创建抽屉里的分配方式：按比例、原质控员（附“无原质控员时”的处理选择）、按科室。
- “病历类型”显示为不可用，并附原因。
- 分配结果按人显示数量和来源分布。
