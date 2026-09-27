# V3.6 病历质量分析报表合同（P2-R1）

> 日期：2026-09-27。对应 PRD 第 5 节以下各项：
> - “运行病历质量分析”
> - “终末病历质量分析”
> - “全院各科室病历质量详情”
> - “缺陷详情分析”（规则、文书、缺陷等级三个维度）
>
> 门急诊、首页、27 项指标、核心制度另行处理，见第 6 节。

## 1. 证据

- 旧 `/api/v1/reports/qc/*` 数据来自旧表 `qc_statistics_view`，不是 LX0609 Canonical 结果，所以不能继续扩展。
- V5 统计页 `/workstation/analytics/luxian-0609` 与病历列表的分析面板 `/workstation/qc-result-analysis/luxian-0609` 已经实现：
  - 按“病历池同一筛选口径 + 每份病历最新 ready Canonical 结果”统计；
  - 按规则、科室、医生下钻。
- 上述两个入口都**没有**以下指标：平均分、等级、单否、审核通过、人工缺陷、文书/缺陷等级分布、导出。PRD 要求的正是这些。

## 2. 事实来源（每个事实只有一个 owner，报表只做聚合）

| 指标 | owner | 读取方式 |
|---|---|---|
| 病历范围、科室、主治医师 | 病历池筛选口径 | `luxian_0609_result_analysis_service._load_current_workstation_records`（与分析面板同一函数） |
| 质控结论、缺陷条目 | 最新 ready Canonical 结果 | `build_luxian_0609_completed_record_result_summaries(include_items=True)`；条目经 `project_customer_items` 投影，`is_confirmed_issue` 由投影函数给出 |
| 得分、等级、单否 | 场景默认评分标准 + 纯函数 `score_result` | 一次读取默认标准，逐病例计分。结果不落库，也不重判条目 |
| 审核状态 | `qc_record_reviews` | `batch_review_states`，锚点取自读取器原始摘要（root_job_id/envelope_id） |
| 人工缺陷 | 任务人工缺陷（与人工缺陷审核同一谓词） | 按三坐标分组计数，并区分 pending/approved/rejected |
| 文书分类、缺陷等级 | LX0609 规则总表 `source_document` / 执行目录 `defect_level` | 按 rule_id 读取；文书不能使用包含质控点内容的 `category`（例如018为“主诉能导出第一诊断”），缺失归入“未归类”/“未分级” |

规则：

- **缺陷**：只计确认缺陷，即 `is_confirmed_issue`（`non_compliant`）。待核实、数据缺失、不适用都不计。
- **人工缺陷数**：只计未被驳回的（pending + approved），并单列 rejected 数。
- **单否缺陷数**：命中标准中 `is_veto` 条目的扣分条数。

## 3. 统计口径

**场景**：

- `scene=running`：病历池 `hospital_status=inpatient`，计分场景为 running；本批只覆盖当前在院子范围，不能声称覆盖出院未归档病历。
- `scene=final`：归档权威来源未核实，读取病例前返回 409 `archive_scope_unverified`，页面明确显示阻塞；不得用 `discharged` 替代已归档。

**筛选**：

- `department`：受工作台数据范围约束，科室角色只能看本科。
- `doctor`：主治医师。
- `completed_from/completed_to`：质控完成时间，闭区间，无时区的值按 Asia/Shanghai 解释。
- `defect_source=all|auto|manual`：这就是“质控类型筛选”，只影响缺陷类指标、分布和 top20。

**报表病例集**：范围内有 ready 结果、且完成时间在窗口内的病例。除“病历总数”外，所有指标都在这个集合上计算。

**概览 KPI**：

- `record_total`：范围内的病历数。
- `qc_ready_total`：报表病例集的大小。
- `qc_unavailable_total`：结果损坏或读取失败的病例数。
- `average_score`：已计分病例的均值，保留两位小数。以下两种情况为 `null`：
  - 未配置标准：`score_status=no_standard`；
  - 标准读取失败：`score_status=unavailable`。
- `scored_total`、`top_grade_name`、`top_grade_rate`：甲级率等于首档人数除以已计分数。
- `review_approved_total`：审核状态为 approved 的病例数；另给出 `review_state_counts`。审核读取失败时为 `null`，并给出 `review_status=unavailable`。
- `auto_defect_total`、`records_with_auto_defect`。
- `manual_defect_total`（不含驳回）、`manual_defect_rejected_total`。人工缺陷读取失败时为 `null`。
- `veto_defect_total`、`veto_record_total`。

**分布**：

- `grade_distribution`：各档人数，按标准档位顺序，否决等级单列。
- `score_distribution`：得分分段，含左端、不含右端：`<60`、`60–70`、`70–80`、`80–90`、`90–100`（包含100）、`>100`。评分标准允许基准分大于100，不把这些分数混入90–100。
- `defect_level_distribution`、`document_distribution`：缺陷条数，受 `defect_source` 影响。人工缺陷按其 `rule_code` 查目录，查不到归入“人工-未归类”。

**四维 top20**：按缺陷条数降序，并列时按名称升序。

- `top_rules`
- `top_departments`
- `top_doctors`
- `top_documents`

**科室明细 `department_rows`**（即“全院各科室病历质量详情”，也用作科室排名）：

- 字段：`record_total`、`qc_ready_total`、`average_score`、`top_grade_rate`、`review_approved_total`、`auto_defect_total`、`manual_defect_total`、`veto_defect_total`、`records_with_defect`。
- 默认排序：终末场景按平均分降序，运行场景按缺陷数降序。

**医生明细 `doctor_rows`**：字段与科室明细相同。

**不可用项**（显式声明，不伪造）：

| 指标 | 状态 | 原因 |
|---|---|---|
| 整改状态 | `unavailable` | `remediation_owner_undefined`：整改状态 owner 与七类口径未定义，医生通知通道也缺失 |
| 核心制度维度 | `unavailable` | `core_system_classification_missing`：规则尚无核心制度归类 |

**规模上限**：为避免无界装载病例结果，在读取结果条目前对候选病例集合实施 5000 例保守上限，超限返回 422 `range_too_large`，不截断统计。完成时间窗口在结果读取后应用，因此仅缩短完成时间不能绕过候选上限，需收窄科室或医生。现有范围 owner 仍先装配候选集合，超大范围的 SQL 级限流另列性能缺口。

**评分时点**：按当前场景默认评分标准对选中的最新结果按需重算，响应附标准 ID 与更新时间；不是执行当时冻结的历史分数。

## 4. 接口（`/api/v1/quality-reports`，角色 admin、qc_manager，数据范围同工作台）

- `GET /record-quality`：返回
  ```
  {
    scope, kpis, score_standard,
    grade_distribution, score_distribution,
    defect_level_distribution, document_distribution,
    top_rules, top_departments, top_doctors, top_documents,
    department_rows, doctor_rows,
    unavailable_dimensions
  }
  ```
- `GET /record-quality/records`：病例下钻，分页。
  - 维度参数：`department`、`doctor`、`rule_id`、`document`、`grade`、`has_defect`，可叠加。
  - 每行字段：三坐标、姓名、科室、医生、完成时间、得分、等级、单否、审核状态、自动缺陷数、人工缺陷数。
- `GET /record-quality/export?sheet=departments|doctors|records`：UTF-8 BOM CSV，写审计事件，并与页面同一口径。

错误处理：

| 情况 | 响应 |
|---|---|
| 参数非法 | 422 |
| 越权科室 | 403 |
| 终末归档范围未核实 | 409 `archive_scope_unverified`，读取前拒绝 |
| 结果读取故障 | 503，固定脱敏提示 |

审核读取失败、计分失败、人工缺陷读取失败都只把对应指标降级为 `null` 或 `unavailable`，不阻断整张报表。

## 5. 前端

**职责边界**：新增报表服务统一承担病例集装配、聚合、下钻和导出，避免扩张已有工作台查询大文件；新增页面承担单一报表工作流，复用既有 API、路由权限、布局及评分/审核 owner，不引入通用报表框架。新增模块超过200行源于完整业务职责，后续扩展其他报表时需重新评估边界。

新页面 `/dashboard/qc/reports/record-quality?scene=running|final`，“统计分析”菜单改为子菜单。页面分区如下：

- **总览**：KPI 卡片。未配置标准时，得分类卡片显示“未配置评分标准”；不可用时显示“不可用”。
- **筛选**：场景、科室、医生、完成时间、质控类型。
- **分布**：包括
  - 等级分布、得分分布（仅在已配置评分标准时显示）；
  - 缺陷等级分布、文书分布；
  - 四维 top20 标签页。
- **明细**：科室明细和医生明细两张表。
  - 列显示可选择，并按用户保存到本机浏览器。服务端的用户级列配置属于“自定义列”项，另行处理。
  - 点击科室、医生、规则或文书，下钻到病例列表。
- **导出**：按钮调用服务端 CSV 导出。
- **不可用项**：显示“整改状态：未接入（缺整改 owner）”“核心制度维度：未接入（缺核心制度归类）”。

## 6. 本批不做

| 项目 | 状态 | 原因 |
|---|---|---|
| 门急诊质量分析 | 阻塞 | 缺门急诊身份与规则集 |
| 病案首页统计 | 另批 | 首页质控结果 owner 不同 |
| 27 项指标 | 另批 | 需先逐项确认公式与数据源 |
| 18 项核心制度 | 阻塞 | 缺归类 |
| 运行及时率 | 阻塞 | 缺指标合同 |
| 特殊病历报表 | 阻塞 | 缺定义 |
| 质控员分析、人工质控报表 | P2-R2 | 下一批 |
