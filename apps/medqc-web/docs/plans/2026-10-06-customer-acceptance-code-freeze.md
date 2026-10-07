# 客户验收候选代码冻结清单（2026-10-06）

## 身份与范围

日常分支：`codex/lx0609-tech-debt-20260730`。盘点基线：`6e796ba1dccebe47950183f50bdf9819b274884f`。
本文件所在提交是候选代码冻结点，以 `git rev-parse HEAD` 的完整 SHA 作为后续干净工作树测试及打包依据；不从仍有私有材料的日常目录直接打包。

本次授权是整理并提交客户验收范围，不是批准医学规则上线、客户数据库迁移或部署。候选源代码包含已验证展示层和有限工程修复，临床争议保留为客户验收限制。

## 纳入内容

1. V7.1剩余工作台、ICD及DRG内部面板、页面内确认弹窗，客户样本浮动操作区和规则默认入口；助手已有能力保留，相关排版不新增业务权限。
2. 0609历史损坏任务列表逐行隔离、未成熟观察窗不适用结果保存合同；规则目录展示阶段状态。
3. CT/MRI和术前小结/讨论的已实现工程修复，保留来源与未知状态，不把未抽到改成医生漏写。
4. 0916入院005/006逐项事实、原文引用和受控重试；这是工程验证版本，不代表临床验收、发布批准或32条全部完成。
5. 出院诊疗经过三步实验实现，仅目录显式验收；语义稳定性、重要事件边界及真实病例答案未闭环，禁止默认交付执行。
6. 对应测试、合成工程预期以及本次UI验收说明。新增jsonschema依赖由出院实验模块使用，客户安装仍须在干净环境验证。

## 规则发布范围

0609目录共86条，release_scope为81条default、5条acceptance_only；目录数量不等于可执行数，仍受阶段暂停及客户排除影响。
待验收规则：`LX0609-06-01-03`, `LX0609-06-03-02`, `LX0609-06-02-01`, `LX0609-09-01-02`, `LX0609-08-01-05`。
`LX0609-06-01-03`不进入默认执行；`LX0609-08-01-05`不默认执行。CT/MRI医嘱与病程一致性`LX0609-06-01-01`按此前用户授权为default。此次整理不新增启用或扩大范围。
0916继续沿现有整包验证方式；不得凭工程测试宣称临床确认或批准上线。

## 不纳入内容

- 两份其他任务已暂存文档及未提交的滚动待办；保留原暂存内容。
- backend/.env、授权文件、数据库、凭据、运行时build声明及本地manifest。
- index.prebuilt.css生成物、复制项目目录、其他工作树、日志、探针、患者原文、响应与截图、opinion_freeze及.local排查文件。
- local_cdm_sample开发工具和相关测试；本轮不交付数据库恢复或抽样写库功能。
- 未使用的新图片和独立历史专题文档；不通过整库暂存夹带。

## 验收边界

本次首次大范围前端测试发生worker异常退出，后端874项组合回归在错误报告阶段MemoryError，类型检查并行任务被中止；这些不记为通过。
此前UI迁移全量1285项通过是开发侧历史证据，不能替代本固定SHA的干净环境验收。

### 本次重新检查

- 前端在Asia/Shanghai时区、单worker下重跑：143个文件、1285项全部通过。
- 类型检查单独重跑通过。
- 前端完整src范围ESLint只读检查通过；未使用全目录自动修复，以免改动其他任务文件。
- 候选Python文件Ruff检查未通过：15项（customer_rule_package的13项未使用导入、source_evidence_reader的2项重复字典键）。本次不自动修复或认定为历史问题，后续预检需要处理或给出基线证据。
- 后端单独重跑目录及读取/复核两个文件：25项通过、6项失败。失败尚未作基线对照归因，不称为历史欠账，作为打包前阻断项保留。
- 已暂存文本编码、凭据扫描及git diff空白检查通过；候选Python源码AST解析通过。
- 本次测试在日常工作区执行，仍须在固定SHA的干净环境复验；没有客户PG、真实模型或临床验收证据。

后端失败清单：

1. `test_luxian_0609_catalog_contains_migrated_rules_and_released_extensions`
2. `test_luxian_0609_batch_detail_hydrates_validated_canonical_items_before_summary_projection`
3. `test_luxian_0609_batch_detail_ignores_stale_internal_rule_results_after_canonical_hydration`
4. `test_projected_luxian_job_still_uses_safe_workspace_response`
5. `test_review_luxian_workspace_batch_job_persists_report`
6. `test_review_response_uses_customer_safe_projection_and_recomputes_issue_records`

尚未完成：候选产物打包、干净安装/重启、客户PG迁移预检、真实模型与角色业务全链路、客户临床验收。不推送、不部署、不写客户库。本候选不是“预检已全部通过”的交付包。

## 精确文件清单

- `.codex/skills/medqc-workstation-design/SKILL.md`
- `backend/app/data/luxian_0609_phase1_rule_contracts_extension_v1.json`
- `backend/app/data/luxian_0609_phase1_rules_extension_v1.json`
- `backend/app/data/luxian_0609_rule_master_v1.json`
- `backend/app/routers/qc_sichuan.py`
- `backend/app/services/luxian_0609/course_quality_result_mapping.py`
- `backend/app/services/luxian_0609/customer_remediation.py`
- `backend/app/services/luxian_0609/customer_renderer.py`
- `backend/app/services/luxian_0609/customer_rule_package.py`
- `backend/app/services/luxian_0609/discharge_result_mapping.py`
- `backend/app/services/luxian_0609/exam_lab_fact_extraction.py`
- `backend/app/services/luxian_0609/executor_registry.py`
- `backend/app/services/luxian_0609/extended_document/discharge_course_content.py`
- `backend/app/services/luxian_0609/extended_document/discharge_course_stages.py`
- `backend/app/services/luxian_0609/native_extended_document_execution.py`
- `backend/app/services/luxian_0609/native_preop_content_execution.py`
- `backend/app/services/luxian_0609/source_evidence_reader.py`
- `backend/app/services/luxian_0609/source_registry.py`
- `backend/app/services/luxian_0609_rule_catalog.py`
- `backend/app/services/luxian_0916/admission_content_items.py`
- `backend/app/services/luxian_0916/admission_rules.py`
- `backend/app/services/luxian_0916/semantic_extractor.py`
- `backend/requirements.txt`
- `backend/tests/fixtures/luxian_0609/discharge_scope_v1.json`
- `backend/tests/integration/test_luxian_0609_discharge_course_chain.py`
- `backend/tests/integration/test_luxian_0609_release_scope.py`
- `backend/tests/unit/luxian_0916/test_admission_item_facts.py`
- `backend/tests/unit/luxian_0916/test_admission_rules.py`
- `backend/tests/unit/test_course_007_immature_saved_boundary.py`
- `backend/tests/unit/test_luxian_0609_attempt_boundary_audit.py`
- `backend/tests/unit/test_luxian_0609_customer_renderer.py`
- `backend/tests/unit/test_luxian_0609_discharge_course_content.py`
- `backend/tests/unit/test_luxian_0609_formal_extension_chain.py`
- `backend/tests/unit/test_luxian_0609_native_exam_lab_execution.py`
- `backend/tests/unit/test_luxian_0609_native_preop_content_execution.py`
- `backend/tests/unit/test_luxian_0609_rule_catalog.py`
- `backend/tests/unit/test_qc_sichuan_result_review.py`
- `docs/plans/2026-10-06-ui-v71-remaining-pages.md`
- `src/components/icons/mqIcons.ts`
- `src/components/layout/WorkstationConfirmDialog.vue`
- `src/components/layout/WorkstationLayout.vue`
- `src/components/layout/workstationConfirmation.ts`
- `src/views/dashboard/records/OutpatientEmergencyDetailDrawer.vue`
- `src/views/dashboard/records/OutpatientEmergencyRecordsView.vue`
- `src/views/drg-grouper/GrouperTabsView.vue`
- `src/views/drg-grouper/grouper-workbench.css`
- `src/views/workstation-v4/CustomQCExperienceView.vue`
- `src/views/workstation-v4/CustomerSampleValidationView.css`
- `src/views/workstation-v4/DataSyncConfigPage.vue`
- `src/views/workstation-v4/WorkstationRulesView.vue`
- `src/views/workstation-v4/WorkstationV4HomeEntry.vue`
- `src/views/workstation-v4/WorkstationV4View.vue`
- `src/views/workstation-v4/components/BusinessAgentAnswer.vue`
- `src/views/workstation-v4/components/BusinessAgentChart.vue`
- `src/views/workstation-v4/components/BusinessAgentDrawer.vue`
- `src/views/workstation-v4/components/BusinessAgentWelcome.vue`
- `src/views/workstation-v4/components/ContentQCTab.vue`
- `src/views/workstation-v4/components/ICDDetailPanel.vue`
- `src/views/workstation-v4/components/ICDRecentBar.vue`
- `src/views/workstation-v4/components/ICDSearchHero.vue`
- `src/views/workstation-v4/components/ICDSearchPanel.vue`
- `src/views/workstation-v4/components/QCAlertPanel.vue`
- `src/views/workstation-v4/components/QCResultTab.vue`
- `src/views/workstation-v4/components/RecordDetailWorkspace.vue`
- `src/views/workstation-v4/components/TenderAcceptanceDashboard.vue`
- `src/views/workstation-v4/components/WorkstationAssistPanel.vue`
- `src/views/workstation-v4/components/WorkstationV4AssistView.vue`
- `src/views/workstation-v4/components/sync-console/SyncOverviewBar.vue`
- `src/views/workstation-v4/customer-sample-validation/CustomerSampleTaskHistoryView.vue`
- `src/views/workstation-v4/customer-sample-validation/SyntheticCaseBuilderView.vue`
- `src/views/workstation-v4/customer-sample-validation/useCustomerSamplePoolManagement.ts`
- `src/views/workstation-v4/customer-sample-validation/useCustomerSampleValidationController.ts`
- `src/views/workstation-v4/frontpage/components/AIProfileDashboard.vue`
- `src/views/workstation-v4/frontpage/components/DRGGroupingTab.vue`
- `src/views/workstation-v4/frontpage/components/ExcelUploadView.vue`
- `src/views/workstation-v4/frontpage/components/InProcessMonitoringView.vue`
- `src/views/workstation-v4/frontpage/components/PaymentMonitoringView.vue`
- `src/views/workstation-v4/frontpage/components/PostEventAnalysisView.vue`
- `src/views/workstation-v4/frontpage/components/PreAnalysisView.vue`
- `src/views/workstation-v4/frontpage/components/TestCaseListView.vue`
- `src/views/workstation-v4/frontpage/components/drg-dip-workbench.css`
- `src/views/workstation-v4/semantic-rules/components/CustomerQcResultDetailCard.vue`
- `src/views/workstation-v4/semantic-rules/useSemanticRulesBatchResultDrawerController.ts`
- `src/views/workstation-v4/styles/custom-qc-experience.css`
- `src/views/workstation-v4/styles/customer-sample-refined.css`
- `src/views/workstation-v4/styles/data-upload.css`
- `src/views/workstation-v4/styles/drg-grouping.css`
- `src/views/workstation-v4/styles/drg-in-process.css`
- `src/views/workstation-v4/styles/drg-payment.css`
- `src/views/workstation-v4/styles/drg-post-analysis.css`
- `src/views/workstation-v4/styles/drg-pre-analysis.css`
- `src/views/workstation-v4/styles/icd-detail-panel.css`
- `src/views/workstation-v4/styles/icd-recent-bar.css`
- `src/views/workstation-v4/styles/icd-search-hero.css`
- `src/views/workstation-v4/styles/icd-search-panel.css`
- `src/views/workstation-v4/styles/outpatient-detail.css`
- `src/views/workstation-v4/styles/outpatient-records.css`
- `src/views/workstation-v4/styles/synthetic-case.css`
- `src/views/workstation-v4/styles/task-history.css`
- `src/views/workstation-v4/styles/tender-acceptance.css`
- `tests/unit/components/WorkstationConfirmation.spec.ts`
- `tests/unit/views/workstation-v4/semantic-rules/CustomerQcResultDetailCard.spec.ts`
