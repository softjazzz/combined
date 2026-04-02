# Workstation V4 项目非 CDM 数据结构 CSV 说明

## 1. 文档目的

本说明文档配套：

- [project_pg_field_list_non_cdm_workstation_v4.csv](D:/LLM/lx0222/health-qc-monorepo/apps/medqc-web/backend/docs/project_pg_field_list_non_cdm_workstation_v4.csv)

这份文档不是全项目的数据库总表，而是 `workstation v4` 的测试专项版本。

目标很直接：

- 给测试环境核表用
- 给联调补样本用
- 给回归测试确认哪些表是 `v4` 真正会碰到的对象

你前面提到“要在测试环境做全方位测试，但数据表结构还不够清楚”，这份文档就是为这个问题收口的。

## 2. 这份 v4 文档的范围

本次交付只覆盖 `workstation v4` 当前主链路直接依赖的 `非 CDM / 兼容对象`。

覆盖对象分为 4 组：

### 2.1 登录与权限

- `sys_users`
- `sys_departments`

### 2.2 工作台与详情兼容对象

- `medical_records`
- `medical_documents`
- `ai_frontpage_draft`
- `ai_mr_snapshot`
- `ai_diagnosis_snapshot`
- `ai_mr_surgery_snapshot`
- `ai_mr_cost_snapshot`
- `qc_result`

这一组最关键，因为 `v4` 当前既有新链路，也保留了旧兼容路径：

- 工作台真实列表状态仍会参考 `qc_result`
- 详情页和文书质控会读 `medical_documents`
- 首页草稿恢复依赖 `ai_frontpage_draft`
- 历史病案回看 AI 首页样式依赖 AI 首页快照表组

### 2.3 新质控闭环对象

- `document_qc_results`
- `qc_results`
- `qc_defects`
- `qc_defect_history`
- `qc_rules`
- `document_category_config`
- `notifications`
- `qc_appeals`
- `qc_appeal_reviews`
- `qc_remediation_tasks`
- `qc_remediation_history`

### 2.4 同步与排障对象

- `sync_visit_status`
- `sync_watermarks`

这组不一定是前台每一步都可见，但测试环境排障非常有用，尤其是你们做测试数据补齐和增量同步验证的时候。

## 3. 明确不在这份 CSV 里的内容

这份 CSV 明确 **不覆盖 CDM 主表全量字段**。

也就是说，下面这些仍然重要，但不放进本次 `non_cdm_workstation_v4.csv`：

- `mr`
- `diagnosis`
- `mr_surgery`
- `mr_cost`
- `admission_record`
- `medical_insurance_settlement`
- `medical_insurance_settlement_cost`

原因不是它们不重要，而是它们属于 `CDM 主数据`，应该继续看：

- [cdm_field_list.csv](D:/LLM/lx0222/health-qc-monorepo/apps/medqc-web/backend/docs/cdm_field_list.csv)

一句话：

`要做完整的 v4 测试环境核表，必须把本次 v4 非 CDM CSV 和 cdm_field_list.csv 一起使用。`

## 4. 为什么这份 v4 文档和通用版不一样

你现有那份通用文档更像“项目层结构说明”。

这次我做的是 `workstation v4 专项测试版`，口径更收敛：

- 只保留 v4 当前页面和接口真正会用到的对象
- 把 `legacy` 和 `compat` 的对象单独写清楚
- 把“代码里会读，但 ORM 不一定完整声明”的兼容字段直接标出来

典型例子：

- `medical_documents.sort_order`
  - `records.py` 会直接按它排序
- `medical_documents.category_code`
  - 前端文书类别和规则适配会用到
- `document_category_config`
  - 后端接口直接读这个对象，但当前仓库没有看到正式 ORM 表声明

这类字段如果不提前说明，测试环境最容易出现：

- 接口能启动
- 页面能打开
- 但一进详情页或规则页就报字段缺失

## 5. CSV 字段说明

CSV 仍然沿用和 v5 示例一致的字段结构：

- `schema_name`
- `object_type`
- `object_name`
- `domain`
- `status`
- `source_of_truth`
- `field_name`
- `field_type`
- `nullable`
- `pk_flag`
- `index_flag`
- `default_value`
- `field_desc`
- `business_usage`
- `upstream_dependency`
- `downstream_dependency`
- `test_priority`
- `notes`

其中这几个字段在 v4 测试里最有用：

- `object_name`
  - 先看你到底要核哪张表
- `status`
  - 判断它是正式表还是兼容对象
- `source_of_truth`
  - 判断字段来自 ORM、路由依赖还是环境兼容口径
- `downstream_dependency`
  - 看缺了这个字段会炸哪条链路
- `test_priority`
  - 决定先补哪些对象和样本

## 6. v4 测试时要特别注意的 5 个事实

### 6.1 v4 现在是双轨质控结果

`v4` 不是只用一套结果表。

它至少有两条口径并存：

- 旧口径：`qc_result`
- 新口径：`qc_results` + `qc_defects`

因此你在测试环境里如果只补 `qc_results`，有些工作台状态仍然会不对。

### 6.2 v4 的质控结果持久化不是单表

当前代码里，质控结果至少有 5 条持久化落点：

- `qc_result`
  - 旧口径结果表，工作台真实列表仍会参考它聚合状态
- `qc_results`
  - `qc.py` 会把分析结果写入这里，但这条写入是 `non-blocking`
  - 也就是写失败时只记日志，不阻塞主流程
- `qc_defects`
  - 新口径缺陷闭环主表，催办、整改、审核、驳回都依赖它
- `medical_documents`
  - `qc_sichuan.py` 会 best-effort 回写 `qc_status`、`qc_score`、`qc_last_analyzed`、`qc_analysis_version`
- `document_qc_results`
  - `qc_sichuan.py` 会按单规则结果逐条插入，用于文书级规则结果明细

除此之外，还有一条 `非 PG` 但真实存在的持久化路径：

- `backend/app/storage/qc_results`
  - `qc_sichuan.py` 会把结果落成本地文件，作为文件级结果留痕

所以测试环境如果要验证“质控结果有没有真正落下来”，不能只核一张 `qc_results`。

### 6.3 medical_records 和 medical_documents 带明显兼容属性

这两个对象在代码里依赖很强，但字段来源并不完全统一：

- 一部分字段有 ORM
- 一部分字段来自环境实表
- 一部分字段来自前端兼容写法

所以我在 CSV 里把这两类对象标成：

- `compat_object`
- `兼容承载`

这不是降级，而是提醒测试时必须 `按真实环境核表`。

### 6.4 AI 首页快照表组是历史回显主落点

`v4` 现在已经不是只保存短期 `ai_frontpage_draft`。

为了支持“打开历史病案后还能看到当时 AI 生成的首页长什么样”，当前又新增了 4 张正式纳管表：

- `ai_mr_snapshot`
- `ai_diagnosis_snapshot`
- `ai_mr_surgery_snapshot`
- `ai_mr_cost_snapshot`

这 4 张表的职责要和 CDM 主表分开理解：

- `mr / diagnosis / mr_surgery / mr_cost`
  - 继续只读，代表原始 CDM 底账
- `ai_*_snapshot`
  - 代表 AI 生成首页的长期结构化快照
  - 供历史回显、测试核表、与原始 CDM 做人工对照

因此，如果测试目标包含“验证历史病案能回看 AI 首页样式”，这 4 张表必须纳入测试库核表范围。

### 6.5 document_category_config 是隐藏坑位

这个对象不是最显眼的业务表，但 `qc.py` 会直接查：

- `document_category_config`

如果测试环境没这张表，或者缺 `is_active`、`sort_order`、`required_sections` 这些字段，规则配置和类别配置会直接出问题。

### 6.6 frontpage_extraction_settings 不是 PG 表

前端 `v4` 会读取首页抽取配置，但当前后端实现不是数据库表持久化，而是文件配置。

因此它不进入这份 `PG 非CDM CSV`，但测试环境仍要额外确认：

- 首页抽取配置文件是否存在
- 接口是否能正常返回默认值或文件值

## 7. 推荐的测试环境核表顺序

如果你的目标是“先把 v4 主链路跑通”，建议按这个顺序核：

1. `sys_users`
2. `sys_departments`
3. `medical_records`
4. `medical_documents`
5. `qc_result`
6. `qc_results`
7. `qc_defects`
8. `document_qc_results`
9. `qc_rules`
10. `document_category_config`
11. `notifications`
12. `ai_frontpage_draft`
13. `ai_mr_snapshot`
14. `ai_diagnosis_snapshot`
15. `ai_mr_surgery_snapshot`
16. `ai_mr_cost_snapshot`

这 16 个对象补齐之后，`v4` 的登录、列表、详情、文书、规则、通知、首页草稿，以及“历史 AI 首页回显”几个主路径就基本能测了。

然后再补：

1. `qc_defect_history`
2. `qc_appeals`
3. `qc_appeal_reviews`
4. `qc_remediation_tasks`
5. `qc_remediation_history`
6. `sync_visit_status`
7. `sync_watermarks`

这组更偏向闭环测试和排障测试。

## 8. 建议你怎么用这两份表

如果你后面要组织测试环境核表和补样本，推荐这样用：

1. 先用这份 `workstation_v4` CSV 筛 `P0`
2. 再把 `P0` 对象逐张去测试环境核表
3. 然后用 `cdm_field_list.csv` 补主数据表
4. 最后按页面链路做联调样本

推荐按页面分组准备样本：

- 登录与权限
  - `sys_users`
  - `sys_departments`
- 工作台列表
  - `medical_records`
  - `qc_result`
  - `mr`
  - `admission_record`
- 首页生成与首页质控
  - `ai_frontpage_draft`
  - `mr`
  - `diagnosis`
  - `mr_surgery`
  - `mr_cost`
- 文书详情与内容质控
  - `medical_documents`
  - `qc_results`
  - `qc_defects`
  - `document_qc_results`
  - `qc_defect_history`
  - `qc_rules`
  - `document_category_config`
- 通知
  - `notifications`
- 申诉整改
  - `qc_appeals`
  - `qc_appeal_reviews`
  - `qc_remediation_tasks`
  - `qc_remediation_history`

## 9. 这次没有放进去的对象

这次我没有把下面这类对象并入 v4 专项 CSV：

- `qc_tasks`
- `qc_task_records`
- `v_qc_task_progress`
- `qc_async_jobs`

原因很明确：

- 这些对象在项目里存在
- 但 `workstation v4` 当前前台主路径并没有完整接通
- 尤其批量操作仍有明显占位逻辑

如果你后面要做“任务中心”或“异步链路”的专项测试，再单独补一版即可，没必要把本次 v4 核表范围继续摊大。

下面这些对象我这次也没有并入主清单，但原因不同：

- `scoring_rules`
- `scoring_config`
- `qc_coder_workload_daily`

它们不是“不存在”，而是当前更偏向评分引擎、评分阈值和编码员工作量统计。

如果你本轮测试目标包含下面任一项，就应该把它们追加进专项核表：

- 质控得分计算正确性
- 评分阈值配置变更
- 编码员日统计或排行

否则，当前这份 v4 文档先聚焦工作台主链路是更稳妥的范围控制。

## 10. 本次交付位置

本轮新增文件如下：

- [project_pg_field_list_non_cdm_workstation_v4.csv](D:/LLM/lx0222/health-qc-monorepo/apps/medqc-web/backend/docs/project_pg_field_list_non_cdm_workstation_v4.csv)
- [workstation*v4*项目非CDM数据结构CSV说明.md](D:/LLM/lx0222/health-qc-monorepo/apps/medqc-web/docs/gap/workstation_v4_项目非CDM数据结构CSV说明.md)

如果你下一步需要，我可以继续把这份 `v4 CSV` 再往下做成两种更适合测试执行的版本：

- `测试样本准备清单`
- `页面链路 -> 表 -> 字段` 的核对矩阵
