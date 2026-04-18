# 质控业务数据库设计 PRD v2.6

> v2.6 | 2026-03-26 | PostgreSQL 单栈定版（补充现网兼容对象与字段缺口）

---

## 1. 背景与现状

### 1.1 现状

后端目前处于**“PostgreSQL ORM 落地 + Supabase/内存兼容回退”并行期**：部分路由已切换到本地 ORM，部分路由仍使用 Supabase 或内存回退。

### 1.2 代码中实际引用的全部表/视图

通过扫描 47 个 router 文件，代码中引用以下 Supabase 表名：

| 代码引用名                  | Router                                             | 类型     |
| --------------------------- | -------------------------------------------------- | -------- |
| `qc_tasks`                  | tasks.py                                           | 表       |
| `qc_task_records`           | tasks.py                                           | 表       |
| `v_qc_task_progress`        | tasks.py:566                                       | **视图** |
| `qc_results`                | dashboard_api.py                                   | 表       |
| `qc_defects`                | defects.py                                         | 表       |
| `qc_defect_history`         | defects.py:132                                     | 表       |
| `qc_appeals`                | appeals.py                                         | 表       |
| `qc_appeal_reviews`         | appeals.py:255                                     | 表       |
| `qc_appeals_statistics`     | appeals.py:621                                     | **视图** |
| `qc_remediation_tasks`      | remediation.py:108                                 | 表       |
| `qc_remediation_history`    | remediation.py:125                                 | 表       |
| `qc_remediation_statistics` | remediation.py:775                                 | **视图** |
| `qc_assignee_workload`      | remediation.py:866                                 | **视图** |
| `qc_statistics_view`        | reports.py:53 / reports.py:116                     | **视图** |
| `qc_rules`                  | semantic_rules.py / department_qc_rules.py / qc.py | 表       |
| `scoring_rules`             | scoring_rules.py                                   | 表       |
| `scoring_config`            | scoring_config.py                                  | 表       |
| `notifications`             | notifications.py                                   | 表       |

### 1.3 本地 `medqc` 库实际分布（盘点口径）

> 当前库约 77 张表，可按职责分为三类（用于评审和迁移优先级，不替代 P0 清单）。

| 分类       | 命名特征         | 数量（约） | 说明                                                                    |
| ---------- | ---------------- | ---------: | ----------------------------------------------------------------------- |
| CDM 病历表 | 无前缀，英文全名 |        ~50 | ETL 导入为主，如 `patient_information`、`admission_record`、`diagnosis` |
| QC 业务表  | `qc_` 前缀为主   |      ~9-12 | 本系统产生，如 `qc_tasks`、`qc_results`、`qc_defects`                   |
| 系统/杂项  | 混合             |        ~10 | 如 `sync_watermarks`、`llm_models`、`medical_records` 等                |

命名与职责说明（关键）：

1. `qc_rules` 是**在用规则主表**（语义规则、科室规则、规则管理均依赖），不应按“重复表”直接清理。
2. `scoring_rules`、`scoring_config` 为评分域对象，当前路由实现以内存为主，数据库表为落库目标与兼容承载。
3. `qc_result`（单数）与 `qc_results`（复数）当前并存，属于历史兼容阶段对象。

### 1.4 同库分 schema（定版）

在同一个 PostgreSQL 数据库中按 schema 做强隔离：

1. `cdm`：病历/CDM 业务表（ETL 导入为主，只读优先）。
2. `qc`：质控业务表与视图（本系统读写）。
3. `sys`：用户权限、同步元数据、系统管理表。
4. `legacy`：过渡兼容对象（如历史 `medical_records*` / `medical_documents*`）。

---

## 2. P0 必建对象清单（首批上线最小集）

### 2.1 总览

**14 张表 + 6 个视图 = 20 个数据库对象**

> 本 PRD 的 SQL 示例统一为 PostgreSQL 语法，不再维护 SQLite 分支。
> P0 质控对象默认落在 `qc` schema（如 `qc.qc_tasks`、`qc.v_qc_task_progress`）。

```
P0 表（14）:
├── qc_tasks                   # 质控抽查任务
├── qc_task_records            # 任务-病历关联
├── qc_results                 # 质控结果
├── qc_defects                 # 缺陷记录
├── qc_defect_history          # 缺陷操作历史
├── qc_appeals                 # 质控申诉
├── qc_appeal_reviews          # 申诉审核记录
├── qc_remediation_tasks       # 整改任务
├── qc_remediation_history     # 整改操作历史
├── qc_coder_workload_daily    # 编码员日工作量统计
├── qc_rules                   # 质控检查规则主表（含编码质控规则）
├── scoring_rules              # 评分规则
├── scoring_config             # 甲乙丙阈值配置
└── notifications              # 系统通知

P0 视图（6）:
├── v_qc_task_progress         # 任务进度聚合
├── qc_appeals_statistics      # 申诉统计聚合
├── qc_remediation_statistics  # 整改统计聚合
├── qc_assignee_workload       # 责任人工作负载
├── qc_statistics_view         # 报表统计聚合
└── v_qc_coder_ranking         # 编码员工作量排名
```

> 补充说明：`qc_coder_workload_daily` / `v_qc_coder_ranking` 为本次新增的编码员统计对象，当前 `staff_ranking.py` 仍是 mock，后续按本 PRD 切换。

---

### 2.2 `qc_tasks` — 质控抽查任务

> 对齐 `schemas/tasks.py` 枚举值

| 字段                | 类型         | 约束            | 说明                                                      |
| ------------------- | ------------ | --------------- | --------------------------------------------------------- |
| `id`                | VARCHAR(36)  | PK              | UUID                                                      |
| `task_number`       | VARCHAR(30)  | UNIQUE          | QC-YYYYMMDD-XXXX                                          |
| `task_name`         | VARCHAR(200) | NOT NULL        |                                                           |
| `task_type`         | VARCHAR(20)  | NOT NULL        | **`one_time` / `scheduled`**（非 once）                   |
| `schedule_config`   | TEXT         |                 | JSON cron                                                 |
| `date_range`        | TEXT         |                 | JSON `{start, end}`                                       |
| `department_filter` | TEXT         |                 | JSON array                                                |
| `record_ids`        | TEXT         |                 | JSON array（指定病历）                                    |
| `sampling_method`   | VARCHAR(20)  |                 | **`all` / `count` / `percentage`**                        |
| `sampling_config`   | TEXT         |                 | JSON                                                      |
| `assign_method`     | VARCHAR(20)  |                 | **`keep` / `by_department` / `by_ratio` / `by_type`**     |
| `assignee_config`   | TEXT         |                 | JSON                                                      |
| `status`            | VARCHAR(20)  | DEFAULT 'draft' | `draft→sampling→assigned→in_progress→completed→cancelled` |
| `total_records`     | INTEGER      | DEFAULT 0       |                                                           |
| `completed_records` | INTEGER      | DEFAULT 0       |                                                           |
| `progress`          | FLOAT        | DEFAULT 0       | 百分比                                                    |
| `deadline`          | VARCHAR(20)  |                 | ISO 8601                                                  |
| `creator_id`        | VARCHAR(36)  |                 |                                                           |
| `creator_name`      | VARCHAR(50)  |                 |                                                           |
| `created_at`        | DATETIME     | DEFAULT NOW     |                                                           |
| `updated_at`        | DATETIME     | DEFAULT NOW     |                                                           |

### 2.3 `qc_task_records` — 任务-病历关联

| 字段            | 类型         | 约束              | 说明                                          |
| --------------- | ------------ | ----------------- | --------------------------------------------- |
| `id`            | VARCHAR(36)  | PK                |                                               |
| `task_id`       | VARCHAR(36)  | INDEX             |                                               |
| `record_id`     | VARCHAR(100) | NOT NULL          | 病历关联键（目标态映射 CDM `visit_id`）       |
| `assignee_id`   | VARCHAR(36)  |                   |                                               |
| `assignee_name` | VARCHAR(50)  |                   |                                               |
| `status`        | VARCHAR(20)  | DEFAULT 'pending' | `pending / in_progress / completed / skipped` |
| `score`         | FLOAT        |                   |                                               |
| `defect_count`  | INTEGER      | DEFAULT 0         |                                               |
| `qc_result_id`  | VARCHAR(36)  |                   | 关联质控结果                                  |
| `completed_at`  | DATETIME     |                   |                                               |
| `created_at`    | DATETIME     | DEFAULT NOW       |                                               |

### 2.4 `v_qc_task_progress` — 视图

> tasks.py:566 查询时直接 `.table('v_qc_task_progress').select('*').eq('task_id', task_id)`

```sql
CREATE VIEW v_qc_task_progress AS
SELECT
    t.id AS task_id,
    t.task_name,
    t.status AS task_status,
    COUNT(tr.id) AS total_records,
    SUM(CASE WHEN tr.status = 'completed' THEN 1 ELSE 0 END) AS completed_records,
    SUM(CASE WHEN tr.status = 'in_progress' THEN 1 ELSE 0 END) AS working_count,
    SUM(CASE WHEN tr.status = 'pending' THEN 1 ELSE 0 END) AS pending_count,
    SUM(CASE WHEN tr.status = 'completed' THEN 1 ELSE 0 END) AS done_count,
    ROUND(
      CAST(SUM(CASE WHEN tr.status = 'completed' THEN 1 ELSE 0 END) AS FLOAT)
      / NULLIF(COUNT(tr.id), 0) * 100, 1
    ) AS progress_pct,
    AVG(CASE WHEN tr.score IS NOT NULL THEN tr.score END) AS avg_score,
    SUM(COALESCE(tr.defect_count, 0)) AS total_defects
FROM qc_tasks t
LEFT JOIN qc_task_records tr ON tr.task_id = t.id
GROUP BY t.id, t.task_name, t.status;
```

---

### 2.5 `qc_results` — 质控结果

> dashboard_api.py、qc.py、appeals.py、remediation.py 共同依赖  
> 当前处于“新质控结果表 + 历史字段兼容”并行期，字段设计必须覆盖现有读写口径

| 字段              | 类型         | 约束                | 说明                                                       |
| ----------------- | ------------ | ------------------- | ---------------------------------------------------------- |
| `id`              | VARCHAR(36)  | PK                  |                                                            |
| `record_id`       | VARCHAR(100) | NOT NULL, INDEX     | 病历关联键（目标态映射 CDM `visit_id`）                    |
| `rule_set`        | VARCHAR(50)  |                     | 规则集名称                                                 |
| `overall_score`   | FLOAT        |                     | **用 overall_score**（兼容 dashboard）；编码质控场景可为空 |
| `grade`           | VARCHAR(5)   |                     | **A / B / C**（对应甲/乙/丙）；编码质控场景可为空          |
| `status`          | VARCHAR(20)  | DEFAULT 'completed' | 当前质控状态；兼容 qc.py 写入                              |
| `issues`          | TEXT         |                     | JSON array，dashboard/qc.py 兼容字段                       |
| `defect_count`    | INTEGER      | DEFAULT 0           |                                                            |
| `analysis_engine` | VARCHAR(20)  |                     | llm / rule / hybrid                                        |
| `analysis_date`   | DATETIME     |                     |                                                            |
| `analyzed_by`     | VARCHAR(36)  |                     | 看板排名统计当前使用该字段                                 |
| `metadata`        | TEXT         |                     | JSON，分析元信息                                           |
| `raw_output`      | TEXT         |                     | JSON                                                       |
| `created_by`      | VARCHAR(36)  |                     |                                                            |
| `updated_at`      | DATETIME     | DEFAULT NOW         |                                                            |
| `created_at`      | DATETIME     | DEFAULT NOW         |                                                            |

> 兼容约束：
>
> 1. `created_by` 与 `analyzed_by` 现阶段允许并存，待看板统计统一后再收敛为单字段。
> 2. `issues` / `metadata` 为现有接口兼容字段，后续如切换到拆表结构，需保留兼容读取窗口。

### 2.6 `qc_defects` — 缺陷记录

> defects.py 按 `department`（非 `department_code`）筛选

| 字段                   | 类型         | 约束              | 说明                                       |
| ---------------------- | ------------ | ----------------- | ------------------------------------------ |
| `id`                   | VARCHAR(36)  | PK                |                                            |
| `result_id`            | VARCHAR(36)  |                   | 所属质控结果                               |
| `record_id`            | VARCHAR(100) | NOT NULL, INDEX   |                                            |
| `rule_code`            | VARCHAR(50)  |                   |                                            |
| `rule_name`            | VARCHAR(200) |                   |                                            |
| `description`          | TEXT         |                   |                                            |
| `severity`             | VARCHAR(20)  | NOT NULL          | **critical / error / warning / info**      |
| `category`             | VARCHAR(50)  |                   |                                            |
| `deduct_score`         | FLOAT        | DEFAULT 0         | 编码质控场景固定 0（仅提醒不扣分）         |
| `location`             | VARCHAR(200) |                   |                                            |
| `evidence`             | TEXT         |                   | 原文片段                                   |
| `suggestion`           | TEXT         |                   |                                            |
| `status`               | VARCHAR(20)  | DEFAULT 'pending' | pending→urged→remediated→approved/rejected |
| `department`           | VARCHAR(50)  |                   | **用 department**（兼容 defects.py 筛选）  |
| `urged_at`             | DATETIME     |                   |                                            |
| `urged_by`             | VARCHAR(36)  |                   |                                            |
| `urged_message`        | TEXT         |                   |                                            |
| `urged_deadline`       | VARCHAR(20)  |                   |                                            |
| `remediated_at`        | DATETIME     |                   |                                            |
| `remediated_by`        | VARCHAR(36)  |                   |                                            |
| `remediation_note`     | TEXT         |                   |                                            |
| `remediation_evidence` | TEXT         |                   | JSON array（整改证据）                     |
| `approved_at`          | DATETIME     |                   |                                            |
| `approved_by`          | VARCHAR(36)  |                   |                                            |
| `approve_comment`      | TEXT         |                   |                                            |
| `rejected_at`          | DATETIME     |                   |                                            |
| `rejected_by`          | VARCHAR(36)  |                   |                                            |
| `reject_reason`        | TEXT         |                   |                                            |
| `reject_suggestion`    | TEXT         |                   |                                            |
| `created_at`           | DATETIME     | DEFAULT NOW       |                                            |
| `updated_at`           | DATETIME     | DEFAULT NOW       |                                            |

### 2.7 `qc_defect_history` — 缺陷操作历史

> ⚠️ 表名用 `qc_defect_history`（非 `qc_defect_actions`，对齐 defects.py:132）

| 字段         | 类型        | 约束        | 说明                                                               |
| ------------ | ----------- | ----------- | ------------------------------------------------------------------ |
| `id`         | VARCHAR(36) | PK          |                                                                    |
| `defect_id`  | VARCHAR(36) | INDEX       |                                                                    |
| `action`     | VARCHAR(30) | NOT NULL    | urge / cancel*urge / mark_remediated / approve / reject / batch*\* |
| `actor_id`   | VARCHAR(36) |             |                                                                    |
| `actor_name` | VARCHAR(50) |             |                                                                    |
| `details`    | TEXT        |             | JSON                                                               |
| `created_at` | DATETIME    | DEFAULT NOW |                                                                    |

---

### 2.8 `qc_appeals` — 质控申诉

> 对齐 `schemas/appeals.py`，包含 appeal_number / appeal_type / priority / resolution 等字段

| 字段                   | 类型         | 约束              | 说明                                                                 |
| ---------------------- | ------------ | ----------------- | -------------------------------------------------------------------- |
| `id`                   | VARCHAR(36)  | PK                | UUID                                                                 |
| `appeal_number`        | VARCHAR(30)  | UNIQUE            | 申诉编号                                                             |
| `qc_result_id`         | VARCHAR(36)  | NOT NULL          | 关联质控结果                                                         |
| `record_id`            | VARCHAR(36)  | NOT NULL, INDEX   | 病历关联键（现状可能为 `medical_records.id`，目标态映射 `visit_id`） |
| `appeal_type`          | VARCHAR(20)  | NOT NULL          | **`defect` / `score`**                                               |
| `defect_item`          | VARCHAR(200) |                   | 具体缺陷项                                                           |
| `reason`               | TEXT         | NOT NULL          | 申诉理由（≥10字）                                                    |
| `evidence`             | TEXT         |                   | JSON array                                                           |
| `status`               | VARCHAR(20)  | DEFAULT 'pending' | **`pending / reviewing / approved / rejected / withdrawn`**          |
| `priority`             | VARCHAR(20)  | DEFAULT 'medium'  | **`low / medium / high / urgent`**                                   |
| `appellant_id`         | VARCHAR(36)  | NOT NULL          |                                                                      |
| `appellant_name`       | VARCHAR(50)  |                   |                                                                      |
| `appellant_department` | VARCHAR(50)  |                   |                                                                      |
| `reviewer_id`          | VARCHAR(36)  |                   |                                                                      |
| `reviewer_name`        | VARCHAR(50)  |                   |                                                                      |
| `review_result`        | TEXT         |                   | 审核结论                                                             |
| `review_date`          | DATETIME     |                   |                                                                      |
| `resolution`           | TEXT         |                   | 处理决定                                                             |
| `resolution_date`      | DATETIME     |                   |                                                                      |
| `notes`                | TEXT         |                   |                                                                      |
| `created_at`           | DATETIME     | DEFAULT NOW       |                                                                      |
| `updated_at`           | DATETIME     | DEFAULT NOW       |                                                                      |

### 2.9 `qc_appeal_reviews` — 申诉审核记录

> appeals.py:255 引用

| 字段            | 类型        | 约束        | 说明                                            |
| --------------- | ----------- | ----------- | ----------------------------------------------- |
| `id`            | VARCHAR(36) | PK          |                                                 |
| `appeal_id`     | VARCHAR(36) | INDEX       |                                                 |
| `reviewer_id`   | VARCHAR(36) |             |                                                 |
| `reviewer_name` | VARCHAR(50) |             |                                                 |
| `reviewer_role` | VARCHAR(30) |             |                                                 |
| `action`        | VARCHAR(30) | NOT NULL    | **`approve / reject / request_info / forward`** |
| `comment`       | TEXT        |             | 审核意见                                        |
| `metadata`      | TEXT        |             | JSON                                            |
| `created_at`    | DATETIME    | DEFAULT NOW |                                                 |

### 2.10 `qc_appeals_statistics` — 视图

> 代码 appeals.py:645 读字段 `avg_resolution_time_seconds`

```sql
CREATE VIEW qc_appeals_statistics AS
SELECT
    status,
    priority,
    appeal_type,
    COUNT(*) AS count,
    EXTRACT(EPOCH FROM AVG(COALESCE(resolution_date, NOW()) - created_at)) AS avg_resolution_time_seconds
FROM qc_appeals
GROUP BY status, priority, appeal_type;
```

---

### 2.11 `qc_remediation_tasks` — 整改任务

> 对齐 `schemas/remediation.py` + remediation.py:108

| 字段                      | 类型         | 约束              | 说明                                                                     |
| ------------------------- | ------------ | ----------------- | ------------------------------------------------------------------------ |
| `id`                      | VARCHAR(36)  | PK                | UUID, auto                                                               |
| `task_number`             | VARCHAR(30)  | UNIQUE            | **整改任务编号**（逾期接口查询用 remediation.py:912）                    |
| `qc_result_id`            | VARCHAR(36)  | NOT NULL          |                                                                          |
| `record_id`               | VARCHAR(36)  | NOT NULL, INDEX   | 病历关联键（现状并行，目标态映射 `visit_id`）                            |
| `defect_type`             | VARCHAR(50)  |                   | 缺陷类型                                                                 |
| `defect_description`      | TEXT         |                   |                                                                          |
| `defect_location`         | VARCHAR(200) |                   |                                                                          |
| `severity`                | VARCHAR(20)  |                   | **`low` / `medium` / `high` / `critical`**（= RemediationPriority 枚举） |
| `remediation_requirement` | TEXT         |                   | 整改要求                                                                 |
| `deadline`                | DATETIME     |                   |                                                                          |
| `assignee_id`             | VARCHAR(36)  |                   | 负责人                                                                   |
| `assignee_name`           | VARCHAR(50)  |                   |                                                                          |
| `assignee_department`     | VARCHAR(50)  |                   |                                                                          |
| `status`                  | VARCHAR(20)  | DEFAULT 'pending' | `pending→in_progress→submitted→approved/rejected→closed/overdue`         |
| `remediation_description` | TEXT         |                   | 整改说明                                                                 |
| `remediation_evidence`    | TEXT         |                   | JSON（整改证据）                                                         |
| `submitted_at`            | DATETIME     |                   |                                                                          |
| `reviewer_id`             | VARCHAR(36)  |                   | 验收人                                                                   |
| `reviewer_name`           | VARCHAR(50)  |                   |                                                                          |
| `review_comment`          | TEXT         |                   |                                                                          |
| `reviewed_at`             | DATETIME     |                   |                                                                          |
| `closed_at`               | DATETIME     |                   |                                                                          |
| `notes`                   | TEXT         |                   |                                                                          |
| `created_at`              | DATETIME     | DEFAULT NOW       |                                                                          |
| `updated_at`              | DATETIME     | DEFAULT NOW       |                                                                          |

### 2.12 `qc_remediation_history` — 整改操作历史

> remediation.py:125 引用

| 字段         | 类型        | 约束        | 说明                                                  |
| ------------ | ----------- | ----------- | ----------------------------------------------------- |
| `id`         | VARCHAR(36) | PK          | auto UUID                                             |
| `task_id`    | VARCHAR(36) | INDEX       | 关联整改任务                                          |
| `action`     | VARCHAR(30) | NOT NULL    | `create / update / submit / approve / reject / close` |
| `actor_id`   | VARCHAR(36) |             |                                                       |
| `actor_name` | VARCHAR(50) |             |                                                       |
| `old_status` | VARCHAR(20) |             |                                                       |
| `new_status` | VARCHAR(20) |             |                                                       |
| `comment`    | TEXT        |             |                                                       |
| `created_at` | DATETIME    | DEFAULT NOW |                                                       |

### 2.13 `qc_remediation_statistics` — 视图

> 代码 remediation.py:801 读字段 `avg_completion_time_seconds`

```sql
CREATE VIEW qc_remediation_statistics AS
SELECT
    status,
    severity,
    defect_type,
    COUNT(*) AS count,
    EXTRACT(EPOCH FROM AVG(COALESCE(closed_at, NOW()) - created_at)) AS avg_completion_time_seconds
FROM qc_remediation_tasks
GROUP BY status, severity, defect_type;
```

### 2.14 `qc_assignee_workload` — 视图

> remediation.py:866 查询 `supabase.table("qc_assignee_workload").select("*")`
> 对齐 `schemas/remediation.py` 的 `AssigneeWorkload` 响应模型

```sql
CREATE VIEW qc_assignee_workload AS
SELECT
    assignee_id,
    assignee_name,
    assignee_department,
    COUNT(*) AS total_tasks,
    SUM(CASE WHEN status = 'pending' THEN 1 ELSE 0 END) AS pending_tasks,
    SUM(CASE WHEN status = 'in_progress' THEN 1 ELSE 0 END) AS in_progress_tasks,
    SUM(CASE WHEN status IN ('overdue') OR (deadline < NOW() AND status IN ('pending','in_progress','submitted','rejected')) THEN 1 ELSE 0 END) AS overdue_tasks,
    AVG(CASE WHEN status = 'approved' THEN EXTRACT(EPOCH FROM (COALESCE(closed_at, reviewed_at) - created_at)) / 86400.0 END) AS avg_completion_days
FROM qc_remediation_tasks
GROUP BY assignee_id, assignee_name, assignee_department;
```

---

### 2.15 `qc_statistics_view` — 视图

> reports.py:53 / reports.py:116 查询 `supabase.table("qc_statistics_view").select("*")`
> 对齐 `reports.py` 导出字段：`record_id` / `total_documents` / `passed_count` / `warning_count` / `failed_count` / `pending_count` / `avg_qc_score` / `last_analyzed_time`
> **表名策略**：SQL 模板中写 `medical_documents`，`init_db()` 运行时会用 `DOCUMENTS_TABLE` 环境变量（默认 `medical_documents`）动态替换，确保新环境不会因表名偏差而建视图失败
> 过渡期兼容：当前实现依赖文书表的 `qc_status/qc_score/qc_last_analyzed` 字段，后续再切换到 CDM + QC 正式聚合链路

```sql
CREATE VIEW qc_statistics_view AS
SELECT
    d.record_id,
    COUNT(d.id) AS total_documents,
    COUNT(*) FILTER (WHERE d.qc_status = 'passed') AS passed_count,
    COUNT(*) FILTER (WHERE d.qc_status = 'warning') AS warning_count,
    COUNT(*) FILTER (WHERE d.qc_status = 'failed') AS failed_count,
    COUNT(*) FILTER (WHERE d.qc_status = 'pending') AS pending_count,
    ROUND(AVG(d.qc_score)::numeric, 2) AS avg_qc_score,
    MAX(d.qc_last_analyzed) AS last_analyzed_time
FROM medical_documents d
WHERE d.status = 'active'
GROUP BY d.record_id;
```

---

### 2.16 `qc_coder_workload_daily` — 编码员日工作量统计表

> 用于承载编码员工作量统计与排名的落库明细，替换 `staff_ranking.py` 的内置 mock 数据

| 字段                 | 类型        | 约束            | 说明                     |
| -------------------- | ----------- | --------------- | ------------------------ |
| `id`                 | VARCHAR(36) | PK              | UUID                     |
| `stat_date`          | DATE        | NOT NULL, INDEX | 统计日期                 |
| `coder_id`           | VARCHAR(36) | NOT NULL, INDEX | 编码员用户 ID            |
| `coder_name`         | VARCHAR(50) | NOT NULL        | 编码员姓名               |
| `department_id`      | VARCHAR(36) |                 | 科室 ID                  |
| `department_name`    | VARCHAR(50) |                 | 科室名                   |
| `qc_count`           | INTEGER     | DEFAULT 0       | 质控病历数               |
| `recheck_count`      | INTEGER     | DEFAULT 0       | 复审病历数               |
| `defect_found`       | INTEGER     | DEFAULT 0       | 编码质控提醒数（不扣分） |
| `passed_count`       | INTEGER     | DEFAULT 0       | 通过数                   |
| `warning_count`      | INTEGER     | DEFAULT 0       | 警告数                   |
| `failed_count`       | INTEGER     | DEFAULT 0       | 失败数                   |
| `avg_handle_seconds` | FLOAT       | DEFAULT 0       | 平均处理时长（秒）       |
| `created_at`         | DATETIME    | DEFAULT NOW     |                          |
| `updated_at`         | DATETIME    | DEFAULT NOW     |                          |

> **UNIQUE 约束**：`(stat_date, coder_id)`

### 2.17 `v_qc_coder_ranking` — 视图

> 统一输出编码员工作量排名指标，对齐 `staff_ranking.py` 返回结构：`qc_count / recheck_count / defect_found / pass_rate / avg_daily`

```sql
CREATE VIEW v_qc_coder_ranking AS
SELECT
    coder_id AS user_id,
    coder_name AS name,
    department_name AS department,
    SUM(qc_count) AS qc_count,
    SUM(recheck_count) AS recheck_count,
    SUM(defect_found) AS defect_found,
    ROUND(
      CASE WHEN SUM(qc_count) = 0 THEN 0
      ELSE SUM(passed_count)::numeric * 100.0 / SUM(qc_count)
      END, 1
    ) AS pass_rate,
    ROUND(SUM(qc_count)::numeric / GREATEST(COUNT(DISTINCT stat_date), 1), 1) AS avg_daily
FROM qc_coder_workload_daily
WHERE stat_date >= CURRENT_DATE - INTERVAL '30 day'
GROUP BY coder_id, coder_name, department_name;
```

### 2.18 `qc_rules` — 质控规则主表（语义/科室/编码）

> `semantic_rules.py`、`department_qc_rules.py`、`qc.py`、`qc_sichuan.py`、`reports.py` 共同依赖  
> 编码质控规则仅用于提醒编码员，不扣分

| 字段                        | 类型         | 约束                | 说明                                                 |
| --------------------------- | ------------ | ------------------- | ---------------------------------------------------- |
| `id`                        | VARCHAR(36)  | PK                  | 规则ID                                               |
| `rule_code`                 | VARCHAR(50)  | UNIQUE, NOT NULL    | 规则编码                                             |
| `name`                      | VARCHAR(200) | NOT NULL            | 规则名称                                             |
| `description`               | TEXT         |                     | 规则描述                                             |
| `category`                  | VARCHAR(50)  | NOT NULL            | 规则分类（含编码质控）                               |
| `severity`                  | VARCHAR(20)  |                     | 严重程度                                             |
| `rule_type`                 | VARCHAR(30)  |                     | 规则类型；`qc.py` / `semantic_rules.py` 当前直接筛选 |
| `scope`                     | VARCHAR(20)  | DEFAULT 'global'    | global / department                                  |
| `department_id`             | VARCHAR(36)  |                     | 科室规则时必填                                       |
| `parent_rule_id`            | VARCHAR(36)  |                     | 覆盖全局规则时关联父规则                             |
| `override_action`           | VARCHAR(20)  |                     | override / disable                                   |
| `override_config`           | TEXT         |                     | JSON（覆盖配置）                                     |
| `priority`                  | INTEGER      | DEFAULT 0           | 优先级                                               |
| `execution_order`           | INTEGER      | DEFAULT 0           | 当前规则列表排序依赖                                 |
| `status`                    | VARCHAR(20)  | DEFAULT 'published' | draft / published / archived                         |
| `version`                   | VARCHAR(20)  | DEFAULT '1.0'       | 规则版本                                             |
| `effective_from`            | DATETIME     |                     | 生效开始                                             |
| `effective_to`              | DATETIME     |                     | 生效结束                                             |
| `check_logic`               | TEXT         |                     | JSON（规则逻辑）                                     |
| `scoring_config`            | TEXT         |                     | JSON（评分配置；编码质控可为空）                     |
| `applicable_documents`      | TEXT         |                     | JSON array（适用文书）                               |
| `document_categories`       | TEXT         |                     | JSON array，兼容旧筛选口径                           |
| `primary_document_category` | VARCHAR(50)  |                     | `qc.py` 聚合查询依赖                                 |
| `is_active`                 | BOOLEAN      | DEFAULT TRUE        | 是否启用                                             |
| `metadata`                  | TEXT         |                     | JSON 扩展字段                                        |
| `created_by`                | VARCHAR(36)  |                     | 批量导入兼容字段                                     |
| `approved_by`               | VARCHAR(36)  |                     | 审批人                                               |
| `approved_at`               | DATETIME     |                     | 审批时间                                             |
| `created_at`                | DATETIME     | DEFAULT NOW         |                                                      |
| `updated_at`                | DATETIME     | DEFAULT NOW         |                                                      |

### 2.19 `scoring_rules` — 评分规则（仅医生质控评分场景）

> 字段定义为落库目标；当前 `scoring_rules.py` 运行态以内存实现为主  
> **不用于编码质控**（编码质控仅提醒，不扣分）

| 字段            | 类型         | 约束          | 说明                                |
| --------------- | ------------ | ------------- | ----------------------------------- |
| `id`            | VARCHAR(36)  | PK            |                                     |
| `code`          | VARCHAR(50)  | UNIQUE        | 规则编码                            |
| `name`          | VARCHAR(200) | NOT NULL      |                                     |
| `category`      | VARCHAR(50)  |               |                                     |
| `severity`      | VARCHAR(20)  |               |                                     |
| `deduction`     | FLOAT        | DEFAULT 0     | **用 deduction**（非 deduct_score） |
| `max_deduction` | FLOAT        |               |                                     |
| `veto`          | BOOLEAN      | DEFAULT FALSE | 一票否决                            |
| `description`   | TEXT         |               |                                     |
| `enabled`       | BOOLEAN      | DEFAULT TRUE  | **用 enabled**（非 is_active）      |
| `sort_order`    | INTEGER      | DEFAULT 0     |                                     |
| `created_at`    | DATETIME     | DEFAULT NOW   |                                     |
| `updated_at`    | DATETIME     | DEFAULT NOW   |                                     |

### 2.20 `scoring_config` — 甲乙丙阈值配置

| 字段           | 类型        | 约束             | 说明                  |
| -------------- | ----------- | ---------------- | --------------------- |
| `id`           | VARCHAR(36) | PK               |                       |
| `config_key`   | VARCHAR(50) | UNIQUE, NOT NULL | 如 `grade_thresholds` |
| `config_value` | TEXT        | NOT NULL         | JSON                  |
| `description`  | TEXT        |                  |                       |
| `updated_by`   | VARCHAR(36) |                  |                       |
| `updated_at`   | DATETIME    | DEFAULT NOW      |                       |

### 2.21 `notifications` — 系统通知

| 字段           | 类型         | 约束            | 说明                                                             |
| -------------- | ------------ | --------------- | ---------------------------------------------------------------- |
| `id`           | VARCHAR(36)  | PK              |                                                                  |
| `type`         | VARCHAR(30)  | NOT NULL        | defect_urge / task_assign / appeal_result / remediation / system |
| `title`        | VARCHAR(200) | NOT NULL        |                                                                  |
| `content`      | TEXT         |                 |                                                                  |
| `record_id`    | VARCHAR(100) |                 | 当前通知概览会按病历聚合                                         |
| `severity`     | VARCHAR(20)  |                 | 当前通知概览排序依赖                                             |
| `sender_id`    | VARCHAR(36)  |                 |                                                                  |
| `recipient_id` | VARCHAR(36)  | NOT NULL, INDEX |                                                                  |
| `related_type` | VARCHAR(30)  |                 | defect / task / appeal / remediation                             |
| `related_id`   | VARCHAR(36)  |                 |                                                                  |
| `metadata`     | TEXT         |                 | JSON 扩展信息                                                    |
| `payload`      | TEXT         |                 | JSON 扩展载荷                                                    |
| `is_read`      | BOOLEAN      | DEFAULT FALSE   |                                                                  |
| `read_at`      | DATETIME     |                 |                                                                  |
| `created_at`   | DATETIME     | DEFAULT NOW     |                                                                  |

### 2.22 `qc_async_jobs` — 异步任务台账主表（Redis 队列配套）

> 用于承接运行病历质控、终末病历质控、AI 首页生成、结算清单生成、DRG 批处理、智能上传解析等长任务  
> **不复用 `qc_tasks`**：`qc_tasks` 仍表示“业务抽查任务”，`qc_async_jobs` 表示“后台排队执行任务”

| 字段                | 类型         | 约束               | 说明                                                                                                                    |
| ------------------- | ------------ | ------------------ | ----------------------------------------------------------------------------------------------------------------------- |
| `id`                | VARCHAR(36)  | PK                 | 任务 UUID                                                                                                               |
| `job_number`        | VARCHAR(40)  | UNIQUE, NOT NULL   | 异步任务编号                                                                                                            |
| `job_type`          | VARCHAR(50)  | NOT NULL, INDEX    | running_record_qc / final_record_qc / frontpage_generate / settlement_generate / drg_batch_process / smart_upload_parse |
| `business_type`     | VARCHAR(50)  | INDEX              | 业务域：record / frontpage / settlement / drg / upload                                                                  |
| `business_id`       | VARCHAR(100) | INDEX              | 业务对象 ID，如 visit_id / batch_id                                                                                     |
| `record_id`         | VARCHAR(100) | INDEX              | 病历关联键（如适用）                                                                                                    |
| `source_module`     | VARCHAR(50)  |                    | 来源模块：workstation / drg / smart_upload / sync                                                                       |
| `priority`          | SMALLINT     | DEFAULT 5          | 优先级，值越小优先级越高                                                                                                |
| `status`            | VARCHAR(30)  | DEFAULT 'accepted' | accepted / queued / running / succeeded / failed / retry_waiting / cancelled / partial_succeeded                        |
| `queue_name`        | VARCHAR(50)  |                    | Redis 队列名                                                                                                            |
| `idempotency_key`   | VARCHAR(200) | UNIQUE             | 幂等键，避免重复创建                                                                                                    |
| `requested_by`      | VARCHAR(36)  | INDEX              | 发起人 user_id                                                                                                          |
| `requested_by_name` | VARCHAR(50)  |                    | 发起人名称冗余                                                                                                          |
| `tenant_key`        | VARCHAR(50)  |                    | 租户/院区/科室隔离键（如适用）                                                                                          |
| `payload`           | TEXT         |                    | JSON，请求摘要；避免存大对象                                                                                            |
| `result_summary`    | TEXT         |                    | JSON，结果摘要                                                                                                          |
| `progress_pct`      | FLOAT        | DEFAULT 0          | 粗粒度进度百分比                                                                                                        |
| `attempt_count`     | INTEGER      | DEFAULT 0          | 当前已重试次数                                                                                                          |
| `max_attempts`      | INTEGER      | DEFAULT 3          | 最大重试次数                                                                                                            |
| `next_retry_at`     | DATETIME     |                    | 下次重试时间                                                                                                            |
| `error_code`        | VARCHAR(50)  |                    | 失败码                                                                                                                  |
| `error_message`     | TEXT         |                    | 失败原因摘要                                                                                                            |
| `cancel_reason`     | TEXT         |                    | 取消原因                                                                                                                |
| `trace_id`          | VARCHAR(64)  | INDEX              | 链路追踪号                                                                                                              |
| `accepted_at`       | DATETIME     | DEFAULT NOW        | 受理时间                                                                                                                |
| `queued_at`         | DATETIME     |                    | 入队时间                                                                                                                |
| `started_at`        | DATETIME     |                    | 开始执行时间                                                                                                            |
| `finished_at`       | DATETIME     |                    | 完成时间                                                                                                                |
| `last_heartbeat_at` | DATETIME     |                    | Worker 最近心跳时间，仅用于恢复判断                                                                                     |
| `created_at`        | DATETIME     | DEFAULT NOW        |                                                                                                                         |
| `updated_at`        | DATETIME     | DEFAULT NOW        |                                                                                                                         |

> 推荐索引：
>
> 1. `(status, priority, created_at)`
> 2. `(job_type, status, created_at)`
> 3. `(business_type, business_id)`
> 4. `idempotency_key UNIQUE`

### 2.23 `qc_async_job_events` — 异步任务事件表

> 记录关键状态变化，用于排障、审计、重放分析  
> 只记录关键节点，不记录高频明细心跳

| 字段            | 类型        | 约束            | 说明                                                                                                           |
| --------------- | ----------- | --------------- | -------------------------------------------------------------------------------------------------------------- |
| `id`            | VARCHAR(36) | PK              |                                                                                                                |
| `job_id`        | VARCHAR(36) | NOT NULL, INDEX | FK 逻辑关联 `qc_async_jobs.id`                                                                                 |
| `event_type`    | VARCHAR(30) | NOT NULL        | accepted / queued / claimed / running / progress / retry_scheduled / succeeded / failed / cancelled / replayed |
| `old_status`    | VARCHAR(30) |                 | 变更前状态                                                                                                     |
| `new_status`    | VARCHAR(30) |                 | 变更后状态                                                                                                     |
| `operator_id`   | VARCHAR(36) |                 | 用户或 worker 标识                                                                                             |
| `operator_name` | VARCHAR(50) |                 | 操作人/执行器名称                                                                                              |
| `message`       | TEXT        |                 | 事件摘要                                                                                                       |
| `details`       | TEXT        |                 | JSON，少量附加上下文                                                                                           |
| `trace_id`      | VARCHAR(64) | INDEX           |                                                                                                                |
| `created_at`    | DATETIME    | DEFAULT NOW     |                                                                                                                |

### 2.24 `qc_async_job_dead_letters` — 异步任务失败沉淀表

> 仅存放达到上限仍失败或被人工转入待处理区的任务  
> 用于人工排查、重放和告警闭环

| 字段                      | 类型         | 约束             | 说明                 |
| ------------------------- | ------------ | ---------------- | -------------------- |
| `id`                      | VARCHAR(36)  | PK               |                      |
| `job_id`                  | VARCHAR(36)  | UNIQUE, NOT NULL | 原异步任务 ID        |
| `job_type`                | VARCHAR(50)  | NOT NULL, INDEX  |                      |
| `business_type`           | VARCHAR(50)  | INDEX            |                      |
| `business_id`             | VARCHAR(100) | INDEX            |                      |
| `final_status`            | VARCHAR(30)  | NOT NULL         | dead_letter / failed |
| `attempt_count`           | INTEGER      | DEFAULT 0        | 最终失败前已尝试次数 |
| `error_code`              | VARCHAR(50)  |                  |                      |
| `error_message`           | TEXT         |                  | 最终失败原因         |
| `payload_snapshot`        | TEXT         |                  | JSON，请求快照       |
| `result_snapshot`         | TEXT         |                  | JSON，已完成部分摘要 |
| `requested_by`            | VARCHAR(36)  |                  |                      |
| `trace_id`                | VARCHAR(64)  | INDEX            |                      |
| `moved_to_dead_letter_at` | DATETIME     | DEFAULT NOW      |                      |
| `resolved_at`             | DATETIME     |                  | 人工处理完成时间     |
| `resolved_by`             | VARCHAR(36)  |                  | 处理人               |
| `resolution_note`         | TEXT         |                  | 处理说明             |
| `created_at`              | DATETIME     | DEFAULT NOW      |                      |

### 2.25 Redis 与 PostgreSQL 分工约束（队列管理）

> 该约束用于避免后续把运行态字段错误堆进业务表或数据库主表

1. Redis 负责排队顺序、执行闸门、短期运行锁和短期取消信号。
2. PostgreSQL 负责异步任务的状态真相、历史查询、失败原因和审计记录。
3. `qc_async_jobs` 是后台长任务的唯一台账主表，**不得**继续用进程内内存作为事实来源。
4. `qc_tasks` 与 `qc_async_jobs` 职责不同，前者不增加队列调度字段，避免业务任务和执行任务混淆。
5. 不将“每秒级进度刷新”“临时队列顺序”“大模型原始全文结果”直接写入 PostgreSQL 主表。
6. 服务重启后，恢复逻辑必须以 `qc_async_jobs.status` 为准重建 Redis 队列，而不是反向依赖 Redis 自身历史。

### 2.26 现网兼容 / 支撑对象清单（当前代码仍依赖）

> 下列对象不全部属于本 PRD 的主业务域，但当前路由仍直接访问。  
> 若短期内不完成代码迁移，则必须提供兼容表或兼容视图，否则按本 PRD 单独建库后业务仍会缺对象。

#### 2.26.1 `legacy.medical_records`

最小兼容字段：

1. `id`
2. `status`
3. `department`

说明：

1. `dashboard_api.py`、`appeals.py`、`remediation.py`、`emr_render.py` 当前仍直接读取。
2. 目标态应逐步被 CDM 主链路替代，但过渡期不能删除。

#### 2.26.2 `legacy.medical_documents`

最小兼容字段：

1. `id`
2. `record_id`
3. `document_type`
4. `content`
5. `status`
6. `qc_status`
7. `qc_score`
8. `qc_last_analyzed`
9. `qc_analysis_version`
10. `created_at`
11. `updated_at`

说明：

1. `qc_statistics_view`、`emr_render.py`、`qc_sichuan.py` 当前仍依赖。
2. 若后续改为 CDM + 正式结果聚合，需要同步调整报表视图和渲染路由。

#### 2.26.3 `qc.document_qc_results`

最小兼容字段：

1. `document_id`
2. `rule_id`
3. `result_status`
4. `score`
5. `max_score`
6. `confidence_score`
7. `issue_description`
8. `evidence_text`
9. `analysis_time_ms`
10. `created_at`

说明：

1. `qc_sichuan.py` 当前有 best-effort 写入逻辑。
2. 如果决定弃用，需要先移除该写入路径。

#### 2.26.4 `qc.document_category_config`

最小兼容字段：

1. `id`
2. `name`
3. `code`
4. `sort_order`
5. `is_active`

说明：

1. `qc.py` 当前直接读取该表作为文书类别配置来源。

#### 2.26.5 `qc.qc_rule_change_logs`

最小兼容字段：

1. `id`
2. `rule_id`
3. `change_type`
4. `old_value`
5. `new_value`
6. `operator_id`
7. `operator_name`
8. `created_at`

说明：

1. `department_qc_rules.py` 当前直接查询规则变更历史。

#### 2.26.6 `sys.departments`（或到 `sys_departments` 的兼容视图）

最小兼容字段：

1. `id`
2. `code`
3. `name`
4. `is_active`

说明：

1. 现有代码仍使用 `departments` 表名，不是 `sys_departments`。
2. 过渡期建议提供兼容视图，避免双表维护。

#### 2.26.7 `sys.user_profiles`（兼容对象）

最小兼容字段：

1. `id`

说明：

1. `semantic_rules.py` 批量导入存在兜底读取。
2. 若后续彻底迁到 `sys_users`，需同步移除该兼容逻辑。

#### 2.26.8 `sys.llm_api_providers`

最小兼容字段：

1. `id`
2. `is_active`

说明：

1. `semantic_rules.py`、`system.py` 当前健康检查仍探测此表。

#### 2.26.9 `sys.llm_models`

最小兼容字段：

1. `id`
2. `is_active`

说明：

1. `semantic_rules.py`、`system.py` 当前健康检查仍探测此表。

---

## 3. P1 用户权限体系（第二阶段）

### 3.1 总览

**4 张表 + 1 张附属表**，替换当前 `storage/memory.py` 中的硬编码用户和 `core/permissions.py` 中的硬编码权限矩阵。

```
P1 表：
├── sys_users                  # 系统用户
├── sys_departments            # 科室
├── sys_roles                  # 角色定义
├── sys_role_permissions       # 角色-权限映射
└── scoring_rule_sets          # 评分规则集（代码暂未依赖）
```

### 3.2 角色体系设计

> 现有代码 4 角色（admin/qc_manager/qc_staff/doctor），新增 `dept_director`（科室主任）

| 角色         | 代码值              | 定位                 | 典型用户           |
| ------------ | ------------------- | -------------------- | ------------------ |
| 系统管理员   | `admin`             | 全局管理             | 信息科管理员       |
| 质控主管     | `qc_manager`        | 质控全流程管理       | 质控科科长         |
| 质控专员     | `qc_staff`          | 执行质控检查         | 质控科质控员       |
| **科室主任** | **`dept_director`** | **本科室病历监管**   | **各临床科室主任** |
| 医生         | `doctor`            | 查看自己的病历和缺陷 | 临床医生           |

### 3.3 权限矩阵（资源 × 角色）

> 在 `core/permissions.py` 的 `ROLE_PERMISSIONS` 基础上扩展

| 资源         | 操作       | admin | qc_manager | qc_staff | dept_director | doctor |
| ------------ | ---------- | :---: | :--------: | :------: | :-----------: | :----: |
| **病历**     | 查看全院   |  ✅   |     ✅     |    ✅    |      ❌       |   ❌   |
|              | 查看本科室 |  ✅   |     ✅     |    ✅    |      ✅       |   ❌   |
|              | 查看自己的 |  ✅   |     ✅     |    ✅    |      ✅       |   ✅   |
|              | 创建/编辑  |  ✅   |     ❌     |    ❌    |      ❌       |   ✅   |
| **质控结果** | 执行质控   |  ✅   |     ✅     |    ✅    |      ❌       |   ❌   |
|              | 查看全院   |  ✅   |     ✅     |    ✅    |      ❌       |   ❌   |
|              | 查看本科室 |  ✅   |     ✅     |    ✅    |      ✅       |   ❌   |
|              | 查看自己的 |  ✅   |     ✅     |    ✅    |      ✅       |   ✅   |
| **缺陷**     | 催办/审核  |  ✅   |     ✅     |    ✅    |      ❌       |   ❌   |
|              | 标记整改   |  ✅   |     ✅     |    ❌    |      ✅       |   ✅   |
|              | 导出       |  ✅   |     ✅     |    ✅    |      ✅       |   ❌   |
| **任务**     | 创建/分配  |  ✅   |     ✅     |    ❌    |      ❌       |   ❌   |
|              | 执行抽样   |  ✅   |     ✅     |    ✅    |      ❌       |   ❌   |
| **申诉**     | 发起申诉   |  ❌   |     ❌     |    ❌    |      ✅       |   ✅   |
|              | 审核申诉   |  ✅   |     ✅     |    ❌    |      ❌       |   ❌   |
| **整改**     | 创建/验收  |  ✅   |     ✅     |    ✅    |      ❌       |   ❌   |
|              | 提交整改   |  ❌   |     ❌     |    ❌    |      ✅       |   ✅   |
| **评分规则** | 配置       |  ✅   |     ✅     |    ❌    |      ❌       |   ❌   |
|              | 查看       |  ✅   |     ✅     |    ✅    |      ✅       |   ❌   |
| **统计**     | 全院统计   |  ✅   |     ✅     |    ❌    |      ❌       |   ❌   |
|              | 科室统计   |  ✅   |     ✅     |    ✅    |      ✅       |   ❌   |
|              | 个人统计   |  ✅   |     ✅     |    ✅    |      ✅       |   ✅   |
| **系统设置** | 管理       |  ✅   |     ❌     |    ❌    |      ❌       |   ❌   |
| **用户管理** | 管理       |  ✅   |     ❌     |    ❌    |      ❌       |   ❌   |

### 3.4 科室级数据隔离

| 角色               | 隔离规则                 | SQL 条件示例                                                  |
| ------------------ | ------------------------ | ------------------------------------------------------------- |
| admin / qc_manager | 全院可见                 | 无额外 WHERE                                                  |
| qc_staff           | 全院可见（需要跨科质控） | 无额外 WHERE                                                  |
| dept_director      | **仅本科室**             | `WHERE department = :user_dept`                               |
| doctor             | **仅自己的病历**         | `WHERE created_by = :user_id` 或 `WHERE doctor_id = :user_id` |

### 3.5 `sys_users` — 系统用户

> 替换 `storage/memory.py` 中的 `users_db`

| 字段              | 类型         | 约束                    | 说明                                                           |
| ----------------- | ------------ | ----------------------- | -------------------------------------------------------------- |
| `id`              | VARCHAR(36)  | PK                      | UUID                                                           |
| `username`        | VARCHAR(50)  | UNIQUE, NOT NULL        | 用户名                                                         |
| `email`           | VARCHAR(100) | UNIQUE                  | 邮箱（可选登录方式）                                           |
| `password_hash`   | TEXT         | NOT NULL                | bcrypt 哈希                                                    |
| `display_name`    | VARCHAR(50)  | NOT NULL                | 显示名称                                                       |
| `phone`           | VARCHAR(20)  |                         | 手机号                                                         |
| `avatar`          | TEXT         |                         | 头像 URL                                                       |
| `department_id`   | VARCHAR(36)  | FK → sys_departments.id | 所属科室                                                       |
| `department_name` | VARCHAR(50)  |                         | 冗余：科室名                                                   |
| `role`            | VARCHAR(20)  | NOT NULL                | 主角色：admin / qc_manager / qc_staff / dept_director / doctor |
| `roles`           | TEXT         |                         | JSON array，支持多角色：`["admin","qc_manager"]`               |
| `bio`             | TEXT         |                         | 简介                                                           |
| `is_active`       | BOOLEAN      | DEFAULT TRUE            |                                                                |
| `last_login_at`   | DATETIME     |                         |                                                                |
| `created_at`      | DATETIME     | DEFAULT NOW             |                                                                |
| `updated_at`      | DATETIME     | DEFAULT NOW             |                                                                |

### 3.6 `sys_departments` — 科室

| 字段          | 类型        | 约束             | 说明                         |
| ------------- | ----------- | ---------------- | ---------------------------- |
| `id`          | VARCHAR(36) | PK               | UUID                         |
| `code`        | VARCHAR(20) | UNIQUE, NOT NULL | 科室代码（对齐 CDM）         |
| `name`        | VARCHAR(50) | NOT NULL         | 科室名称                     |
| `category`    | VARCHAR(20) |                  | clinical / auxiliary / admin |
| `parent_id`   | VARCHAR(36) |                  | 上级科室（树形结构）         |
| `director_id` | VARCHAR(36) |                  | 科室主任 user_id             |
| `is_active`   | BOOLEAN     | DEFAULT TRUE     |                              |
| `sort_order`  | INTEGER     | DEFAULT 0        |                              |
| `created_at`  | DATETIME    | DEFAULT NOW      |                              |

### 3.7 `sys_roles` — 角色定义（动态 RBAC）

> 替换 `permissions.py` 中的硬编码 `UserRole` 常量

| 字段          | 类型        | 约束             | 说明                                                   |
| ------------- | ----------- | ---------------- | ------------------------------------------------------ |
| `id`          | VARCHAR(36) | PK               |                                                        |
| `code`        | VARCHAR(30) | UNIQUE, NOT NULL | admin / qc_manager / qc_staff / dept_director / doctor |
| `name`        | VARCHAR(50) | NOT NULL         | 显示名（系统管理员 / 质控主管 / ...）                  |
| `description` | TEXT        |                  |                                                        |
| `is_builtin`  | BOOLEAN     | DEFAULT FALSE    | 内置角色不可删除                                       |
| `is_active`   | BOOLEAN     | DEFAULT TRUE     |                                                        |
| `created_at`  | DATETIME    | DEFAULT NOW      |                                                        |

### 3.8 `sys_role_permissions` — 角色-权限映射

> 替换 `permissions.py` 中的硬编码 `ROLE_PERMISSIONS` 字典

| 字段         | 类型        | 约束            | 说明                                                                 |
| ------------ | ----------- | --------------- | -------------------------------------------------------------------- |
| `id`         | VARCHAR(36) | PK              |                                                                      |
| `role_code`  | VARCHAR(30) | NOT NULL, INDEX | FK → sys_roles.code                                                  |
| `resource`   | VARCHAR(50) | NOT NULL        | medical_records / qc_results / qc_rules / ...                        |
| `action`     | VARCHAR(30) | NOT NULL        | create / read / update / delete / analyze / review / export / manage |
| `scope`      | VARCHAR(20) | DEFAULT 'all'   | `all`=全院 / `department`=本科室 / `own`=仅自己                      |
| `created_at` | DATETIME    | DEFAULT NOW     |                                                                      |

> **UNIQUE 约束**：`(role_code, resource, action)` 三元组唯一

### 3.9 `scoring_rule_sets` — 评分规则集（附属）

| 字段          | 类型         | 约束         | 说明 |
| ------------- | ------------ | ------------ | ---- |
| `id`          | VARCHAR(36)  | PK           |      |
| `name`        | VARCHAR(100) | NOT NULL     |      |
| `description` | TEXT         |              |      |
| `version`     | VARCHAR(20)  |              |      |
| `is_active`   | BOOLEAN      | DEFAULT TRUE |      |
| `created_at`  | DATETIME     | DEFAULT NOW  |      |
| `updated_at`  | DATETIME     | DEFAULT NOW  |      |

### 3.10 迁移策略

| 步骤 | 内容                                                                                    |
| ---- | --------------------------------------------------------------------------------------- |
| 1    | 建 4 张系统表 ORM                                                                       |
| 2    | Seed 初始数据：5 个内置角色 + 对应权限行 + 从 `memory.py` 迁移 3 个用户                 |
| 3    | 改 `core/security.py`：`get_current_user` 从数据库查而非内存                            |
| 4    | 改 `core/permissions.py`：`has_permission()` 查 `sys_role_permissions` 表而非硬编码字典 |
| 5    | 各 router 中涉及数据隔离的查询加 `scope` 过滤                                           |
| 6    | 前端 `stores/auth.ts` 的 `hasRole()` 不需要改（后端返回 roles 数组格式不变）            |

> P0 阶段所有 user_id 字段暂不建物理外键，等 P1 `sys_users` 落地后再补

---

## 4. 与 CDM 的关系

- 目标态：通过 `record_id -> CDM visit_id` 进行逻辑关联，**不建物理外键**
- 现状：`record_id` 在不同路由中仍可能对应 `medical_records.id`、`visit_id` 或临时业务 ID，尚未完全统一
- 要求：在映射统一完成前，不将 `record_id = visit_id` 作为既成事实写入代码逻辑
- 不建物理外键原因：CDM 数据来自 ETL 批量导入，物理外键会导致导入顺序约束

### 4.1 现状差异说明（从 CDM 契约迁入）

1. `appeals.py`、`remediation.py` 仍按 `medical_records.id` 校验病历存在性，不等同于 CDM `visit_id`。
2. `medical_records.py` 主链路以三元键和 `visit_id` 为核心，和 `record_id` 语义处于并行期。
3. 因此 `record_id = visit_id` 仅能作为目标态约束，不能当作当前事实做强依赖。

### 4.2 遗留对象（从 CDM 契约迁入）

1. `medical_records_test` / `medical_documents_test`（历史遗留表名；配置默认值已切换到正式表名）。
2. `medical_records` / `medical_documents`（Supabase 兼容路径）。
3. `qc_result`（repository 历史表）与 `qc_results`（新质控域）并存。
4. `qc_rules` 为在用规则主表（语义规则、科室规则、规则管理均依赖），不得按“重复表”清理。
5. `scoring_rules`、`scoring_config` 已建表但当前路由以内存实现为主，属于“已建模、未完全落库”的兼容阶段对象。

### 4.3 并轨原则（从 CDM 契约迁入）

1. 业务新开发仅依赖 CDM + `qc_*`。
2. 遗留对象只做兼容层，不作为新增功能依赖。
3. 对外接口稳定优先，内部存储逐步切换。
4. `qc_rules` 保留为规则主干表；`scoring_*` 是否改名或并入 `qc_*` 需在功能落库完成后再决策。

### 4.4 并轨执行清单（从 CDM 契约迁入）

1. D1：新增 `record_identity_map`，统一 `record_id` 映射来源。
2. D2：`emr_render.py` 去 Supabase 主路径，改为 CDM 主路径。
3. D3：`repository.py` 从“SQLite/Mongo 文案”更新为“PostgreSQL/CDM 文案”。
4. D4：评估 `qc_result` 与 `qc_results` 合并策略（字段映射+回填脚本）。
5. D5：移除 `RECORDS_TABLE/DOCUMENTS_TABLE` 默认 `*_test` 依赖（已完成）。
6. D6：明确 `qc_rules` / `scoring_rules` / `scoring_config` 分工边界，补充落库改造计划与弃用路径。

---

## 5. 实施步骤

| 天  | 内容                                                                                                                                         | 交付物      |
| --- | -------------------------------------------------------------------------------------------------------------------------------------------- | ----------- |
| D1  | 创建 `database/models/qc.py` (14 表 ORM) + 6 个视图 SQL                                                                                      | 模型文件    |
| D1  | 在 `connection.py` 的 `init_db` 中注册新模型                                                                                                 | 启动无报错  |
| D2  | 改造 `tasks.py`、`defects.py` 从 Supabase/内存 → ORM                                                                                         | 2 个 router |
| D3  | 改造 `appeals.py`、`remediation.py`                                                                                                          | 2 个 router |
| D4  | 改造 `qc.py`、`semantic_rules.py`、`department_qc_rules.py`、`scoring_rules.py`、`scoring_config.py`、`notifications.py`、`staff_ranking.py` | 7 个 router |
| D5  | API 单测：核心路径（状态流转、统计视图、分页、枚举值）                                                                                       | 测试通过    |

### 验收标准

- [ ] 启动无 "table/view not found" 错误（含 6 个视图）
- [ ] 6 个核心 router 全部 CRUD + 统计接口可通
- [ ] 枚举值全部对齐：`task_type=one_time/scheduled`、`sampling_method=all/count/percentage`、`assign_method=keep/by_department/by_ratio/by_type`；`qc_defects.severity=critical/error/warning/info`；`qc_remediation_tasks.severity=low/medium/high/critical`
- [ ] 统计视图字段名正确：`avg_resolution_time_seconds`（非 hours）、`avg_completion_time_seconds`（非 hours）、`last_analyzed_time`
- [ ] 编码员统计排名可用：`v_qc_coder_ranking` 返回 `qc_count/recheck_count/defect_found/pass_rate/avg_daily`
- [ ] 编码质控场景只记录结果、不扣分：`qc_results.overall_score/grade` 可为空，`qc_defects.deduct_score = 0`
- [ ] 不再出现 `qc_defect_actions`、`total_score`、`department_code` 等旧名

---

## 6. 关键决策点（已确定）

> [!IMPORTANT]

1. **数据库选型（已确定）**：统一使用 PostgreSQL（开发/测试/生产同构）
2. **Supabase 策略（已确定）**：彻底移除 Supabase，统一走 PostgreSQL（ORM + SQL）
3. **部署策略（已确定）**：CDM 与质控同库部署，按 schema 隔离（`cdm` / `qc` / `sys` / `legacy`）；命名上以 `qc_` 前缀为主区分，`qc_rules` / `scoring_rules` / `scoring_config` 作为历史兼容例外保留原名
4. **迁移策略（已确定）**：引入 Alembic，统一管理 schema 变更与回滚
5. **编码质控策略（已确定）**：编码质控仅提醒编码员，不面向医生扣分；评分规则仅用于医生质控评分场景
