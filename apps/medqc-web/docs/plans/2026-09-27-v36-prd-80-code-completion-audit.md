# V3.6 PRD 80 项代码完成清单

## 基线与结论

- 核对日期：2026-09-28；首次盘点基线：`e1703611c`；最新增量为滚动计划第97节（接续 `bac8f6ef5`）；分支：`codex/v36-manual-gap-drilldown-20260922`。12/41/27、14/40/26和16/38/26历史结论保留于第89至91节，本表为增量后的代码状态。
- 第98节新增现代申诉来源解析前置能力，尚非创建/授权闭环，04/51状态与汇总计数不变；接续`15bdcdd44`。
- 第99节新增评分标准精确引用校验与只读重算快照；尚无申诉创建及授权闭环，计数仍为20/35/25。计分响应与前端引用另批接续，不视为本批已完成。
- 第100节接通计分响应与前端标准版本引用，仍是申诉前置，不提升整项或改变20/35/25计数。
- 分母固定为 `docs/PRD-内涵质控V3.6总需求与差距矩阵.md` 中带 P0/P1/P2/P3 的 80 个功能行，按原文顺序编号。没有删除外部阻塞项，也没有把新增技术工作算成额外完成项。
- 本清单评估代码，不替代原矩阵的业务覆盖/验收状态。部署未做、浏览器未验收，不单独导致代码降级；但真实接口缺失、入口停用、场景身份无法成立、必需动作未实现，会影响代码完整性。

| 代码状态 | 项数 | 占全部80项 |
| --- | ---: | ---: |
| 代码完整 | 20 | 25% |
| 部分实现 | 35 | 43.75% |
| 未实现 | 25 | 31.25% |
| 合计 | 80 | 100% |

**整项代码完成率为20/80 = 25%。有直接功能实现的条目为55/80 = 68.75%，但68.75%不是完成率，也不是工时进度。** 部分项不统一按50%折算；一行可能同时要求多个动作或多个场景，各行工作量也不相等。剩余60项不等于还有75%的开发工时。

代码完整项：02、03、06、07、08、10、22、26、35、37、50、59、62、63、73、74、75、77、79、80。

| 模块 | 完整 | 部分 | 未实现 | 总数 |
| --- | ---: | ---: | ---: | ---: |
| 登录、工作台、门急诊（01–20） | 6 | 5 | 9 | 20 |
| 运行、终末、任务（21–43） | 4 | 18 | 1 | 23 |
| 统计分析（44–56） | 1 | 6 | 6 | 13 |
| 规则、文书、测试病历（57–80） | 9 | 6 | 9 | 24 |

## 判定方法

- **代码完整**：该行约定动作已接真实服务，存在对应测试与权限/状态处理；仍可能有未验证的规模、部署和集成风险，不表示绝无缺陷。
- **部分实现**：已有直接业务代码，但缺子动作、完整场景、数据来源或入口串接。表中明确哪些能力可用，哪些仍阻塞。
- **未实现**：未找到该场景下可执行的直接实现；仅有模型、底层服务、示例、禁用按钮或其他模块的类似能力不算实现。表示此次检查未找到交付证据，不断言仓库没有任何相关文字。
- 依据同时包含功能行、主要差距和所处模块场景，不仅看最短的验收描述。手机号加密码不等于扫码；当前在院不等于完整运行；已出院不等于已归档；操作事件次数不等于去重病例数。
- 证据路径相对 `apps/medqc-web`，行号对应上述基线。提交列列出代表性实现/边界修复提交，不声称一个提交独自交付整行；“无专项交付”表示未找到满足该功能的专项提交。
- 三个只读子任务分别核对01–20、21–43、57–80；主协调核对44–56并复查关键判定。02初步被泛化权限疑虑降级，复查没有具体证据支持，已按实际分流、范围守卫和测试计为完整。

## 01–20 登录、工作台、门急诊

| ID | PRD功能点 | 代码状态 | 已实现及剩余缺口 | 代码证据 | 相关提交 |
| --- | --- | --- | --- | --- | --- |
| 01 | 三种登录方式：账号密码、手机号、扫码 | 部分实现 | 账号/邮箱/手机号加密码可登录；缺扫码认证，也没有独立短信验证码方式。 | `src/components/auth/LoginForm.vue:16`；`backend/app/services/auth_store.py:172` | `6c3910685` |
| 02 | 登录后角色分流 | 代码完整 | 角色落地、路由和菜单过滤、无权落点已实现；数据范围有全院/医生科室/拒绝规则及测试。 | `src/utils/routeAccess.ts:101`；`backend/app/core/data_scope.py:46` | `18f094b8d`、`4876026f0`、`df803acfd` |
| 03 | 我的待办：倒计时任务、进行中任务、未开始任务 | 代码完整 | 三种真实受领任务计数、场景与as_of同口径下钻及分页已接通。 | `backend/app/routers/tasks.py:588`；`src/views/workstation/HomeTaskTodos.vue:188` | `f8cbae6ae` |
| 04 | 我的待办：临床申诉、待审核人工缺陷 | 部分实现 | 人工缺陷计数与列表按冻结scene同谓词筛选，下钻携带场景，历史NULL仅all；申诉精确计数、权限和账号切换保护已有。但原总验收要求三场景下钻，申诉缺冻结场景与现代身份创建链，不能整项升级。 | `src/views/workstation/HomeReviewTodos.vue:1`；`src/views/qc/ManualDefectReviewView.vue:1`；`src/views/workstation/HomeAppealTodos.vue:1` | 第97节 |
| 05 | 我的待办：待审核、待复审病历 | 部分实现 | V5首页接入初审/复审真实计数与下钻、权限及迟到请求保护；范围仍为本人受领任务的已核实结果，未覆盖全部病历来源。 | `backend/app/services/record_review_service.py:979`；`src/views/workstation/HomeReviewTodos.vue:1` | `8caf74817`；第91节B线 |
| 06 | 我的待办：零数量反馈 | 代码完整 | 已知真零显示无待处理事项且不下钻，未知/故障不伪造零；不把尚未接入类别算作零。 | `src/components/dashboard/TodoBoard.vue:139`；`src/views/workstation/HomeTaskTodos.vue:129` | `8caf74817` |
| 07 | 工作表现：质控缺陷排名 | 代码完整 | 本周/上周窗口、真实人工创建人及通过/驳回计数、竞争排名、三场景精确筛选；场景由创建事务锁内任务冻结，历史NULL仅all；自动缺陷不计。迁移68未执行，不代表部署/真实病例验收。 | `backend/app/services/performance_ranking_service.py:162`；`backend/app/services/task_manual_defect_service.py:1` | `3dc1f3efa`；第95节 |
| 08 | 工作表现：质控病历排名 | 代码完整 | 真实授权审核人、病例三坐标去重、初审/复审分项、周窗口及冻结场景均已接通；历史NULL仅all。原PRD未要求按当前角色重筛历史或角色快照，撤销此前额外阻断；角色变化反例及原审核权限测试通过。迁移67未执行。 | `backend/app/services/performance_ranking_service.py:102`；`backend/tests/unit/test_record_ranking_actor_contract.py:1` | `101e83e11`；第96节 |
| 09 | 查询：时间、评分标准、病历信息 | 部分实现 | 门急诊可按日期、科室、关键字查询；页面缺评分标准筛选，身份映射和取数上限仍有限制。 | `src/views/dashboard/records/OutpatientEmergencyRecordsView.vue:46`；`backend/app/routers/records.py:588` | `bb74b48dc` |
| 10 | 筛选：新建筛选、快捷筛选、修改筛选、重置筛选 | 代码完整 | 门急诊专属用户模板创建、快捷应用、更新、默认、删除、重置已接真实服务；用户/页面隔离、字段校验、CAS与账号切换竞态有测试。依赖未执行的迁移63。 | `src/views/dashboard/records/OutpatientFilterTemplateBar.vue:1`；`backend/alembic/versions/20260927_000063_outpatient_filter_templates.py:1` | 第91节A线 |
| 11 | 缺陷列表：导出全部列表 | 未实现 | 通用导出存在，但门急诊导出禁用，未建立该场景可信缺陷身份与万条模板导出链。 | `src/views/dashboard/records/OutpatientEmergencyRecordsView.vue:120`；`backend/app/routers/defects.py:490` | 无门急诊专项交付 |
| 12 | 缺陷列表：批量催办 | 未实现 | 门急诊批量动作禁用；缺身份、通知及操作记录闭环。 | `src/views/dashboard/records/OutpatientEmergencyRecordsView.vue:100` | 无专项交付 |
| 13 | 缺陷列表：查看详情并定位病历原文 | 部分实现 | 可打开可信原始病历文书；不能从门急诊缺陷定位命中片段。 | `src/views/dashboard/records/OutpatientEmergencyDetailDrawer.vue:307` | `e2d600c0d` |
| 14 | 缺陷列表：催办/撤回催办 | 未实现 | 有通用催办API，但门急诊行禁用，身份和医生消息未接通。 | `src/views/dashboard/records/OutpatientEmergencyRecordsView.vue:227`；`src/api/defects.ts:112` | 无门急诊专项交付 |
| 15 | 缺陷列表：标记已整改/查看整改 | 未实现 | 门急诊质控关联不可用，没有可信整改标记和整改前后对比。 | `src/views/dashboard/records/OutpatientEmergencyDetailDrawer.vue:215` | 无专项交付 |
| 16 | 缺陷列表：自定义列、排序、筛选 | 未实现 | 页面为固定病历列，未接该场景缺陷列配置、持久化与列筛选。 | `src/views/dashboard/records/OutpatientEmergencyRecordsView.vue:190` | 无专项交付 |
| 17 | 病历列表：导出质控详情 | 未实现 | 门急诊缺陷/审核结果关联不可用，其他场景导出不算本项。 | `src/views/dashboard/records/OutpatientEmergencyRecordsView.vue:141` | 无专项交付 |
| 18 | 病历列表：导出全部列表 | 未实现 | 门急诊页无可用列表导出；旧通用接口返回虚拟下载地址。 | `backend/app/routers/records.py:1100` | 无专项交付 |
| 19 | 病历列表：批量重新质控、批量通过、批量催办 | 未实现 | 门急诊批量通过/催办禁用，未接批量重质控与结果回写。 | `src/views/dashboard/records/OutpatientEmergencyRecordsView.vue:100` | 无专项交付 |
| 20 | 病历列表：通过/审核存疑 | 未实现 | 门急诊行通过禁用；通用缺陷审核不能代替本场景病历级审核。 | `src/views/dashboard/records/OutpatientEmergencyRecordsView.vue:233` | 无专项交付 |

## 21–43 运行、终末、任务

| ID | PRD功能点 | 代码状态 | 已实现及剩余缺口 | 代码证据 | 相关提交 |
| --- | --- | --- | --- | --- | --- |
| 21 | 查询：周期、评分标准、病历信息 | 部分实现 | 当前在院日期/科室/医生/关键字/审核状态及得分已接；出院未归档范围、评分标准筛选缺失。 | `src/views/workstation-v4/QcRecordResultListView.vue:67` | `8e1af54e9` |
| 22 | 筛选模板 | 代码完整 | 用户模板创建、保存、应用、更新、设默认、重置、删除，后端用户隔离及CAS均有实现和测试。 | `src/views/workstation-v4/components/qc/RecordFilterTemplateBar.vue:19`；`backend/app/services/filter_template_service.py:257` | `223d2f6e5` |
| 23 | 缺陷列表操作 | 部分实现 | 旧运行页有缺陷动作与接口；V5可信全运行范围、整改派发、医生通知未贯通。 | `src/views/dashboard/records/RunningRecordsViewNew.vue:780` | `fcdb32852` |
| 24 | 病历详情联审 | 部分实现 | 三坐标文书、审核、相邻病例导航和人工缺陷已接；完整运行范围与精确命中片段仍缺。 | `src/views/workstation-v4/QcRecordResultListView.vue:266` | `348ad8b3a` |
| 25 | 病历列表批量操作 | 部分实现 | 任务抽样/重跑基础存在；运行列表勾选后直接批量重跑及统一进度尚未闭环。 | `backend/app/services/task_sampling_service.py:299`；`src/views/workstation-v4/QcRecordResultListView.vue:725` | `2102a39b8` |
| 26 | 自定义列 | 代码完整 | 运行列表列显隐、恢复默认与用户/阶段隔离的浏览器持久化已接；固定身份/选择/操作列，存储异常失败提示，保留旧布局。非跨设备同步。 | `src/views/workstation-v4/components/qc/QcRecordColumnSettings.vue:1`；`src/views/workstation-v4/components/qc/qcRecordColumnPreferences.ts:1` | 第90节专项提交 |
| 27 | 默认筛选与快捷筛选 | 部分实现 | 审核快捷项、默认模板和重置已接；缺陷临床申诉/待整改默认分区未完成。 | `src/views/workstation-v4/components/qc/RecordFilterTemplateBar.vue:176` | `223d2f6e5` |
| 28 | 详情分区与结构化文书 | 部分实现 | 结果、人工缺陷、文书可查看；五类分区及逐条命中片段定位未齐。 | `src/views/workstation-v4/components/qc/QcRecordReviewPreview.vue:142` | `348ad8b3a` |
| 29 | 病历级操作与操作记录 | 部分实现 | 病历通过/存疑与按三坐标操作时间线已接；改标准、催办/通知等动作与相应历史未齐。 | `backend/app/routers/record_reviews.py:1`；`backend/app/services/case_operation_timeline_service.py:283` | `fcdb32852`、`b62fa9790` |
| 30 | 终末病历列表查询 | 部分实现 | 已出院列表有筛选和结果；归档来源未确认，不能算权威终末集合。 | `src/views/workstation-v4/QcRecordResultListView.vue:357`；`src/views/dashboard/records/FinalRecordsView.vue:11` | `f62adcadd` |
| 31 | 批量质控 | 部分实现 | 已有任务作业链和终末门禁；归档范围无权威来源，终末执行仍不可用。 | `backend/app/services/task_sampling_service.py:323` | `f62adcadd` |
| 32 | 病历详情和联审 | 部分实现 | 已出院病例文书及通用保存结果审核有实现；终末集合和缺陷整改未闭环。 | `src/views/workstation-v4/QcRecordResultListView.vue:266` | `fcdb32852` |
| 33 | 归档相关操作（MedQC 扩展） | 未实现 | 无平台归档服务、权威状态回读与归档操作审计；仍保留在80项分母。 | `src/views/dashboard/records/FinalRecordsView.vue:11` | 无专项交付 |
| 34 | 导出列表和质控详情 | 部分实现 | 列表导出及审核字段已实现；缺已归档终末范围证明，不能以已出院导出冒充终末。 | `src/views/workstation-v4/QcRecordResultListView.vue:725` | `68dec70b1` |
| 35 | 我收到的任务：任务列表 | 代码完整 | 本人受领任务、三坐标病历清单和详情权限已接真实接口及范围测试。 | `src/views/dashboard/tasks/MyTasksView.vue:390`；`backend/app/routers/tasks.py:640` | `13e67d5e4` |
| 36 | 我收到的任务：重新质控 | 部分实现 | 受领人作业、历史、进度、单例结果已接；场景覆盖和病例级重跑闭环未齐。 | `src/components/qc/TaskDetailDrawer.vue:137`；`backend/app/services/task_qc_run_service.py:1` | `bece2305c` |
| 37 | 我创建的任务：任务列表 | 代码完整 | 创建人列表、统计、详情、进度与分配信息按created范围查询，有测试。 | `src/views/dashboard/tasks/MyTasksView.vue:394`；`backend/app/routers/tasks.py:1274` | `bab0a581e` |
| 38 | 新建抽查任务：单次任务 | 部分实现 | 选择场景/规则集、冻结版本和抽样保存已接；完整运行、终末和可用门急诊规则集仍缺。 | `backend/app/routers/tasks.py:355`；`backend/app/services/task_sampling_service.py:323` | `bece2305c` |
| 39 | 新建抽查任务：定时任务 | 部分实现 | 独立计划管理、到期领取、自动生成抽样子任务、运行回执、失租恢复与失败重试已接；当前限运行中活动病例，其他场景及部署调度未验收。基线为未实现，不计十项Goal。 | `backend/app/services/task_schedule_job_service.py:1`；`backend/app/jobs/task_schedule_tick.py:1` | 第94节 |
| 40 | 病历范围：自定义筛选、指定病历 | 部分实现 | 三坐标指定病例及基础日期/科室条件可用；复杂条件和完整场景范围未齐。 | `backend/app/services/task_sampling_service.py:94` | `2102a39b8` |
| 41 | 病历抽样：全部、数量、比例等 | 部分实现 | 全部、数量、比例和科室分层已实现；手册全部抽样方式与完整场景未覆盖。 | `backend/app/services/task_sampling_service.py:334` | `76a134fc3` |
| 42 | 任务分配：原质控员、科室、比例、病历类型 | 部分实现 | 原质控员、科室、比例三种已实现；病历类型策略明确不可用。 | `backend/app/services/task_assignment_service.py:22`；`src/components/qc/CreateTaskDrawer.vue:537` | `e3e453490` |
| 43 | 全部任务 | 部分实现 | 列表、批量分配、私有模板、分析、草稿规划/活动元数据编辑和筛选CSV导出已有；新增持久定时计划、幂等创建、运行回执、租约恢复与抽样子任务。仅接运行中活动病例，重抽样编辑及其他场景未齐，迁移64–66未执行，不提升整项。 | `backend/app/services/task_schedule_service.py:1`；`backend/app/services/task_schedule_job_service.py:1`；`src/views/dashboard/tasks/AllTasksView.vue:1` | `cc0fa210f`；第91至94节 |

## 44–56 统计分析

| ID | PRD功能点 | 代码状态 | 已实现及剩余缺口 | 代码证据 | 相关提交 |
| --- | --- | --- | --- | --- | --- |
| 44 | 门急诊病历质量分析 | 未实现 | 通用概览不能替代门急诊专题；新报表仅支持running/final参数，无该场景数据集与指标链。 | `backend/app/routers/quality_reports.py:26`；`src/router/index.ts:716` | 无专项交付 |
| 45 | 运行病历质量分析 | 部分实现 | 当前在院KPI、等级/得分/缺陷分布、Top20、明细、下钻、CSV和本地列配置已接；缺出院未归档与七类整改状态。 | `backend/app/services/record_quality_report_service.py:26`；`backend/app/services/record_quality_report_service.py:461` | `43442c4b9` |
| 46 | 终末病历质量分析 | 部分实现 | 有共用聚合/页面/导出代码；final因归档来源未核验在读取前拒绝，终末报表不可用。 | `backend/app/services/record_quality_report_service.py:172` | `43442c4b9` |
| 47 | 病案首页统计分析 | 未实现 | 有首页质控与通用汇总，不是按首页病案、问题病案、编码/非编码缺陷及科室生成的专题报表。 | `backend/app/routers/reports.py:305`；`src/router/index.ts:716` | 无专项交付 |
| 48 | 缺陷详情分析 | 部分实现 | 当前在院规则/文书/等级分布、四维Top20及下钻已做；完整场景、核心制度分类等维度缺失。 | `backend/app/services/record_quality_report_service.py:461`；`backend/app/services/record_quality_report_service.py:637` | `43442c4b9` |
| 49 | 全院各科室病历质量详情 | 部分实现 | 当前在院科室均分、总数、等级率、缺陷数及导出已做；全场景范围不齐，评分依赖已配置标准。 | `backend/app/services/record_quality_report_service.py:422`；`backend/app/services/record_quality_report_service.py:693` | `43442c4b9` |
| 50 | 运行质控员分析 | 代码完整 | 冻结运行场景的审核量、复审、去重病例、人均、人工缺陷与驳回、人员排名及时间窗口已接通；历史NULL仅all。场景未知申诉按字段null显示未知，不抹掉真实工作量。依赖67/68未部署。 | `backend/app/services/staff_work_analysis_service.py:196`；`src/views/qc/reports/StaffAnalysisView.vue:1` | 第96节 |
| 51 | 终末质控员分析 | 部分实现 | 已返回冻结final审核/人工缺陷的真实工作量；原51要求的申诉通过/驳回仍缺可信场景归属，字段null，不把全部申诉当终末工作量。 | `backend/app/services/staff_work_analysis_service.py:196` | `e1703611c`；第96节 |
| 52 | 特殊病历报表 | 未实现 | 缺特殊病例定义、独立数据集、专题查询与展示，不以通用报表计入。 | `src/router/index.ts:716`；`docs/plans/2026-09-27-v36-handoff-to-next-agent.md`第5节 | 无专项交付 |
| 53 | 病案管理 27 项指标 | 未实现 | 有指标资料，未找到27项公式、查询、明细与导出专项实现。 | `src/router/index.ts:716`；`docs/plans/2026-09-27-v36-handoff-to-next-agent.md`第5节 | 无专项交付 |
| 54 | 18 项医疗核心制度 | 未实现 | 有相关质控规则，但不是制度列表/原文/问题率专题报表；分类仍标不可用。 | `backend/app/services/record_quality_report_service.py:43` | 无专项报表交付 |
| 55 | 人工质控报表（手册仅列名称） | 部分实现 | 人工缺陷录入、审核通过/驳回已有按人事件统计与质量报表指标；整改owner和完整报表合同仍缺。 | `backend/app/services/staff_work_analysis_service.py:116`；`backend/app/services/record_quality_report_service.py:42` | `e1703611c`、`43442c4b9` |
| 56 | 运行病历及时率（手册仅列名称） | 未实现 | 时间起点、完成事件、分母与排除条件未定，无可核实及时率计算和逾期明细。 | `docs/plans/2026-09-27-v36-handoff-to-next-agent.md`第5节 | 无专项交付 |

## 57–80 规则、文书、测试病历

| ID | PRD功能点 | 代码状态 | 已实现及剩余缺口 | 代码证据 | 相关提交 |
| --- | --- | --- | --- | --- | --- |
| 57 | 门急诊规则配置 | 部分实现 | 通用标准服务识别场景，但门急诊目录无可评分规则集，页面禁止新建，无法完成项目组配置。 | `backend/app/services/scoring_standard_service.py:112`；`src/views/qc/ScoringStandardsView.vue:35` | `10f2a9592`、`8e1af54e9` |
| 58 | 住院规则配置 | 部分实现 | 运行/终末标准和规则版本启停可用；科室生效范围、医生端开关未接。 | `backend/app/services/scoring_standard_service.py:38`；`backend/app/services/rule_set_version_service.py:43` | `10f2a9592`、`25340aec6` |
| 59 | 评分标准新增、编辑、删除 | 代码完整 | 草稿CRUD、任意等级名称及区间校验、界面和测试已做；已启用版本通过复制草稿再改。 | `backend/app/routers/scoring.py:190`；`backend/app/services/scoring_standard_service.py:221` | `10f2a9592`、`8e1af54e9` |
| 60 | 默认评分标准配置 | 部分实现 | 运行/终末启用替换及active非默认直接设默认均已接；场景锁、CAS、替换与回读同事务。门急诊规则来源及首页/特殊报表默认场景仍未齐。 | `backend/app/services/scoring_standard_service.py:1`；`src/views/qc/ScoringStandardsView.vue:1` | `10f2a9592`、`8e1af54e9`；第91节C线 |
| 61 | 评分项目组配置 | 部分实现 | 项目组、扣分条目和启用可维护；生效科室及文书等范围未完整建模。 | `src/views/qc/scoring/ScoringStandardEditor.vue:219`；`backend/app/services/scoring_standard_service.py:317` | `10f2a9592`、`8e1af54e9` |
| 62 | 规则导入/导出 | 代码完整 | 新评分标准与规则集版本均有版本化Excel模板、导出、导入草稿及逐Sheet/行/字段错误和成功回执。评分标准只新建草稿；生命周期只导入已登记规则状态，不导入新执行器或规则定义。资源/公式/外链、版本竞争、草稿删除重建、事务回滚和未知响应有反例。 | `backend/app/services/scoring_standard_excel_service.py:1`；`backend/app/services/rule_set_version_excel_service.py:1` | 第92节两条Excel专项提交 |
| 63 | 非编码质控点已上线列表 | 代码完整 | 当前版本真实条目，开启/暂停/下线写草稿并发布，已有组件与服务测试。 | `src/views/dashboard/quality-control/QualityControlPointManagement.vue:69`；`backend/app/services/rule_set_version_service.py:421` | `25340aec6` |
| 64 | 非编码质控点未上线列表 | 部分实现 | 未上线列表与批量上线可用；单项编辑、删除未接。 | `src/views/dashboard/quality-control/QualityControlPointManagement.vue:73` | `25340aec6` |
| 65 | 编码质控点管理 | 未实现 | 有编码规则结果，但缺编码质控点已上线/未上线管理及规定批量动作。 | `src/views/dashboard/quality-control/ruleSetVersionModel.ts:15` | 无专项交付 |
| 66 | 新建质控点：基础信息 | 未实现 | 新建表单禁用，不能保存规则基础信息草稿。 | `src/views/dashboard/quality-control/QualityControlPointCreate.vue:27` | 无专项交付 |
| 67 | 新建质控点：条件、时效条件、条件组 | 未实现 | 没有可保存的可视化条件编排链。 | `src/views/dashboard/quality-control/QualityControlPointCreate.vue:50` | 无专项交付 |
| 68 | 新建质控点：测试病历验证 | 未实现 | 独立测试病历可运行，但未接“新建质控点上线前必选病例并查结果”流程。 | `src/views/dashboard/quality-control/QualityControlPointCreate.vue:27`；`src/views/test-medical-records/TestMedicalRecordsView.vue:351` | 无专项交付 |
| 69 | 质控点批量操作 | 部分实现 | 批量开启/暂停/下线可发布刷新；删除缺失。 | `src/views/dashboard/quality-control/QualityControlPointManagement.vue:365` | `25340aec6` |
| 70 | 文书列表 | 未实现 | 病历文书可看，但没有文书类型/模板管理列表。 | `src/views/test-medical-records/TestMedicalRecordsView.vue:190` | 无专项交付 |
| 71 | 导入文书 | 未实现 | 样本Excel导入不等于文书定义导入，缺定义字段校验。 | `backend/app/routers/qc_sample_pools.py:730` | 无专项交付 |
| 72 | 文书搜索 | 未实现 | 病例搜索不是文书定义名称检索，尚无管理入口。 | `backend/app/services/custom_qc_sample_pool_service.py:4760` | 无专项交付 |
| 73 | 测试病历列表 | 代码完整 | 固定池真实分页、三坐标、文书数和关联规则已接，有列表与关联测试。 | `backend/app/routers/qc_sample_pools.py:631`；`src/views/test-medical-records/TestMedicalRecordsView.vue:67` | `1b81e6fdb` |
| 74 | 新建测试病历 | 代码完整 | 合成病历编辑器逐文书填写并调用真实创建服务，至少一份有效文书的校验已做。 | `src/views/workstation-v4/customer-sample-validation/SyntheticCaseBuilderView.vue:413`；`backend/app/services/custom_qc_sample_pool_service.py:4311` | `1b81e6fdb` |
| 75 | 导入测试病历 | 代码完整 | 应用定义的V3.6 XLSX模板下载、多病例多文书导入、全文件预检、Sheet/行/字段错误、逐病例真实回执及页面接入已测；仅合成数据、单次20病例，不声称兼容未提供的原手册模板或具备持久幂等。 | `backend/app/services/test_record_import_service.py:1`；`src/views/test-medical-records/components/TestRecordImportDrawer.vue:1` | 第91节E线 |
| 76 | 导出测试病历 | 未实现 | 固定池列表无标准测试病历文件勾选导出，结果报告导出不是此功能。 | `src/views/test-medical-records/TestMedicalRecordsView.vue:45` | 无专项交付 |
| 77 | 编辑测试病历 | 代码完整 | 基本信息及文书可改，派生新版本并事务标记旧版本，CAS及前后端测试已做。 | `src/views/test-medical-records/components/TestRecordEditDrawer.vue:75`；`backend/tests/unit/test_customer_test_record_management.py:307` | `1b81e6fdb` |
| 78 | 复制测试病历 | 未实现 | 新固定池无复制命令/API；旧页复制仅模拟成功，编辑派生版本不当作复制操作。 | `src/views/medical-records/MedicalRecordsView.vue:865` | 无专项交付 |
| 79 | 删除测试病历 | 代码完整 | 确认、软移除、权限与CAS已接；原条目同事务保存操作者/UTC时间/旧版本审计，损坏载荷和重复请求拒绝，回读失败回滚；保留CDM与历史结果。 | `src/views/test-medical-records/TestMedicalRecordsView.vue:390`；`backend/app/services/custom_qc_sample_pool_service.py:4993` | `1b81e6fdb`；第90节专项提交 |
| 80 | 查看应用质控点 | 代码完整 | 列表及弹窗真实显示关联规则ID/名称，后端归属校验与关联持久化有测试。 | `src/views/test-medical-records/TestMedicalRecordsView.vue:146`；`backend/app/services/custom_qc_sample_pool_service.py:4916` | `1b81e6fdb` |

## 最近提交实际补齐了什么

第91节五线代码提交映射：A（10）`9530a011d`，B（04/05）`bb55eb59c`，C（60）`bcf627490`，D（43）`4a1da1003`，E（75）`61ebee2f6`。上述条目中的“第91节X线”即此固定提交。

| 提交 | 对应条目 | 不能扩大成的结论 |
| --- | --- | --- |
| 第91节：五线收尾 | 10、75部分升完整；04、05、43、60补子缺口，仍为部分 | 不等于40项全部收口、跨场景覆盖、持久导入幂等或数据库/业务验收完成 |
| 第90节：列配置与软移除审计 | 26由未实现升为完整，79由部分升为完整 | 不等于跨设备列配置同步、数据库部署或真实病例验收 |
| `e1703611c` 全场景质控员工作分析 | 50、51、55的共用事件聚合及页面 | 不等于运行、终末分别可统计；不等于整改报表已完成 |
| `43442c4b9` 当前在院质量报表 | 45、46、48、49、55的相关子能力 | 不等于完整运行/终末范围、七类整改状态或核心制度报表完成 |
| `8e1af54e9`、`10f2a9592` 评分标准前后端 | 57–61；59代码完整 | 不等于门急诊规则来源、科室/医生生效范围全部完成 |
| `25340aec6` 质控点版本管理页面 | 63、64、69；63代码完整 | 不等于新建规则、条件编排、删除已实现 |
| `1b81e6fdb` 测试病历真实化 | 73、74、77、79、80；73/74/77/80代码完整 | 不等于导入模板、标准导出、复制、删除审计完成 |
| `223d2f6e5` 用户筛选模板 | 22、27；22代码完整 | 不等于门急诊模板或运行缺陷默认整改筛选完成 |

## 验证与交付分层

| 层级 | 本次结论 |
| --- | --- |
| 代码完成 | 20项完整、35项部分、25项未实现；第96节08/50部分升完整，43/51仍部分；新十项Goal累计4/10 |
| 非生产验证 | 历史各批有不同范围的单测/合成PG/只读冒烟，不能给80项统一通过率；最新报表及人员分析只读PG窗口为空，不是非空正向验收 |
| 业务库部署 | 本开发批次未完成部署；不能把隔离库revision62当业务库已升级 |
| 真实病例与浏览器验收 | 未对80项形成逐项签收清单；本次代码审计不能代替业务验收 |

关键测试证据入口（首次盘点读取历史记录；第90节功能开发另有集中复验）：

- 02：`tests/unit/router/route-permission-matrix.spec.ts`、`backend/tests/unit/test_workstation_data_scope.py`。
- 03/06：`backend/tests/unit/test_task_todos.py`、`backend/tests/unit/test_tasks_todo_large_scope.py`、`tests/unit/views/workstation/HomeTaskTodos.spec.ts`、`tests/unit/components/dashboard/TodoBoard.spec.ts`。
- 22：`backend/tests/unit/test_filter_template_service.py`、`backend/tests/unit/test_filter_templates_api.py`。
- 26：`QcRecordColumnSettings.spec.ts`、`qcRecordColumnPreferences.spec.ts`、`QcRecordResultTable.spec.ts`；合成组件浏览器检查显隐、刷新保持、恢复默认及390px窄屏。
- 79：`backend/tests/unit/test_customer_test_record_management.py`，35项覆盖权限、CAS、持久审计、原载荷保留与回读失败回滚；不是实际PG写入验收。
- 35/37：`backend/tests/unit/test_task_detail_scope.py`、`backend/tests/unit/test_task_progress_scope.py`、`backend/tests/unit/test_task_stats_scope.py`。大规模真实PostgREST的详情取数完整性仍需专项验收。
- 59/63：`tests/unit/views/qc/ScoringStandardsView.spec.ts`、`backend/tests/unit/test_rule_set_version_service.py`、`src/views/dashboard/quality-control/__tests__/QualityControlPointManagement.spec.ts`。
- 62：两套Excel服务及API测试；第92节主协调后端组合107项通过，全量前端214文件/2020项通过。数据库写入和真实文件浏览器往返仍未验收。
- 07：第95节主协调创建、幂等、迁移、排名、API与人工审核组合171项通过，前端排名API/组件20项通过；历史NULL、场景冲突、跨院同号、自动缺陷排除、时间边界均有反例。仅合成测试，未执行迁移68或真实病例验收。
- 73/74/77/80：`backend/tests/unit/test_customer_test_record_management.py`及相关合成病历创建测试；不同人口学信息、文书类型和真实数据库行为仍需集成验收。
- 最近代码基线的前端全量204文件/1924项、类型检查、ESLint与编码检查已通过，见滚动计划§88；这不能换算成PRD完成百分比。

## 后续维护

每批交付必须更新受影响ID的状态、已实现内容、剩余缺口和提交依据，并重新计算三个状态的数量。外部依赖单列但不从分母删除。未经逐项复核，不把“部分实现”批量升级；也不再拿旧矩阵中零个“已包含”回答代码完成率。
