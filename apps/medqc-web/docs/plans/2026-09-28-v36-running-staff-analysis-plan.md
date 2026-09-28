# V3.6 运行质控员分析 Implementation Plan

**Goal:** 在原50要求下交付真实运行场景人员工作量与缺陷处理统计；独立复核08，不扩充原PRD未要求的角色决策。

**Architecture:** 复用67/68冻结的审核、人工缺陷场景，服务端按事件owner聚合，前端只搬运。无法可靠归属的申诉指标采用字段级未知，不使已归属工作量整表不可用，也不将51标完整。

**Tech Stack:** SQLAlchemy、FastAPI、Vue、pytest、Vitest。

## 固定合同

- 原50见PRD矩阵256：平均质控病历、复审、人工缺陷、驳回和按时间人员排名。原51的申诉通过/驳回仍缺scene owner，本批不冒充51整项完成。
- `all`保留原事件全集及指标。`running/final`按`QCRecordReview.scene`和`QCDefect.scene`筛选审核、缺陷创建及审核事件；历史NULL只进入all。
- 具体场景的`summary/staff`返回已核实指标；`appeal_approved_count/appeal_rejected_count`在总览及每行都为null，附`unavailable_metrics`对象，两键值均为`scene_not_attributable`。顶层`unavailable_reason=null`表示报表可读取，不表示所有指标已知。
- 具体场景活跃人员只由可归属的审核/人工缺陷动作组成，不将场景未知的申诉人员混入；PRD人均病历`avg_reviewed_cases_per_reviewer`只除实际审核人数。旧`avg_record_reviews_per_active_staff`继续除全部活跃人数，保持API兼容，不将两个指标混同。前端显示具体场景工作记录，不称全部工作记录。
- 时间、阶段次数、三坐标去重、人员归属和排序仍沿用现有owner。旧全表不可用响应继续兼容；unknown绝不转换为0。
- 不新增迁移、真实数据库写入或质控引擎变更；已依赖67/68但未部署的事实需明确记录。

## 所有权与步骤

1. 后端：`staff_work_analysis_service.py`及原service/API测试，先加场景与未知反例，再追加精确过滤及nullable申诉指标；默认all保持行为。
2. 前端：`src/api/staffAnalysis.ts`、`StaffAnalysisView.vue`及两套专属测试，收窄DTO及字段级unknown显示；不重算人均，不扩大UI。
3. 独立测试：新`test_staff_analysis_scene_contract.py`，覆盖跨场景、历史NULL、真实空窗、人均分母和申诉only人员不混入；不改实现。
4. 08合同复验：新`test_record_ranking_actor_contract.py`，证明真实审核人稳定ID参与排名，当前角色变动不改写历史工作量；复跑原审核API角色/对象权限测试。原PRD未要求role字段、角色快照或只计qc_staff，不再把这些额外要求当阻断。
5. 只读复核：逐项核对原50/08及前后端合同、权限和未知语义；主要diff由主协调复审，Node门禁集中执行。

## 验收与提交

- 聚焦pytest/Ruff、类型、只读ESLint、编码和Vitest；全量未执行项如实记录，不以局部通过冒充。
- 更新80项清单和滚动计划，以50/08原整项要求验收后才计数；51保留部分。
- 分列代码/隔离PG/业务部署/真实病例浏览器，本批后面三层未做不得提升。仅暂存本批文件、中文提交、不推送。
