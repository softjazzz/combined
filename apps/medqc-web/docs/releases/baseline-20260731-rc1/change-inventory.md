# 发布基线改动清单

- 候选标识：`baseline-20260731-rc1`
- Git HEAD：`b89e2a065d1cc504253e8960af2db8dbb343a0e6`
- 分支：`codex/lx0609-tech-debt-20260730`
- 已跟踪改动：181
- 未跟踪文件：35
- 未分类：0

| 类别 | 发布需要 | Git  | 路径                                                                                                               | 责任域           | 原因                                                        |
| ---- | -------: | ---- | ------------------------------------------------------------------------------------------------------------------ | ---------------- | ----------------------------------------------------------- |
| D    |       否 | `??` | `.worktrees`                                                                                                       | 本地工作树       | 本机 Git worktree 目录，不属于发布源码                      |
| E    |       否 | ` M` | `apps/medqc-web/.env.production`                                                                                   | 前端环境配置     | 实际环境配置必须由部署侧注入，不提交工作区值                |
| B    |       是 | ` M` | `apps/medqc-web/.gitignore`                                                                                        | 发布源码治理     | 隔离本地产物、历史交付包和临时验证输出                      |
| C    |       否 | ` M` | `apps/medqc-web/AGENTS.md`                                                                                         | 开发治理         | Agent 工作约束，不属于客户运行版本                          |
| B    |       是 | ` M` | `apps/medqc-web/backend/.env.example`                                                                              | 后端部署配置     | 安全环境变量模板和部署边界                                  |
| A    |       是 | ` M` | `apps/medqc-web/backend/app/core/settings.py`                                                                      | 后端发布功能     | 样本同步、Bundle、Native 规则、Envelope 或结果 API 运行代码 |
| A    |       是 | `??` | `apps/medqc-web/backend/app/data/luxian_0609_phase1_rule_contracts_extension_v1.json`                              | 后端发布功能     | 样本同步、Bundle、Native 规则、Envelope 或结果 API 运行代码 |
| A    |       是 | `??` | `apps/medqc-web/backend/app/data/luxian_0609_phase1_rules_extension_v1.json`                                       | 后端发布功能     | 样本同步、Bundle、Native 规则、Envelope 或结果 API 运行代码 |
| A    |       是 | `??` | `apps/medqc-web/backend/app/data/luxian_0609_phase_scope_v1.json`                                                  | 后端发布功能     | 样本同步、Bundle、Native 规则、Envelope 或结果 API 运行代码 |
| A    |       是 | ` M` | `apps/medqc-web/backend/app/data/luxian_0609_rule_contracts_v1.json`                                               | 后端发布功能     | 样本同步、Bundle、Native 规则、Envelope 或结果 API 运行代码 |
| A    |       是 | ` M` | `apps/medqc-web/backend/app/data/luxian_0609_rules_v1.json`                                                        | 后端发布功能     | 样本同步、Bundle、Native 规则、Envelope 或结果 API 运行代码 |
| A    |       是 | ` M` | `apps/medqc-web/backend/app/routers/emr_render.py`                                                                 | 后端发布功能     | 样本同步、Bundle、Native 规则、Envelope 或结果 API 运行代码 |
| A    |       是 | ` M` | `apps/medqc-web/backend/app/routers/llm_configs.py`                                                                | 后端发布功能     | 样本同步、Bundle、Native 规则、Envelope 或结果 API 运行代码 |
| A    |       是 | ` M` | `apps/medqc-web/backend/app/routers/llm_info.py`                                                                   | 后端发布功能     | 样本同步、Bundle、Native 规则、Envelope 或结果 API 运行代码 |
| A    |       是 | ` M` | `apps/medqc-web/backend/app/routers/qc_sample_pools.py`                                                            | 后端发布功能     | 样本同步、Bundle、Native 规则、Envelope 或结果 API 运行代码 |
| A    |       是 | ` M` | `apps/medqc-web/backend/app/services/bundles/assembly.py`                                                          | 后端发布功能     | 样本同步、Bundle、Native 规则、Envelope 或结果 API 运行代码 |
| A    |       是 | ` M` | `apps/medqc-web/backend/app/services/bundles/contracts.py`                                                         | 后端发布功能     | 样本同步、Bundle、Native 规则、Envelope 或结果 API 运行代码 |
| A    |       是 | ` M` | `apps/medqc-web/backend/app/services/bundles/emr_view.py`                                                          | 后端发布功能     | 样本同步、Bundle、Native 规则、Envelope 或结果 API 运行代码 |
| A    |       是 | ` M` | `apps/medqc-web/backend/app/services/custom_qc_sample_pool_service.py`                                             | 后端发布功能     | 样本同步、Bundle、Native 规则、Envelope 或结果 API 运行代码 |
| A    |       是 | ` M` | `apps/medqc-web/backend/app/services/custom_qc_workspace_service.py`                                               | 后端发布功能     | 样本同步、Bundle、Native 规则、Envelope 或结果 API 运行代码 |
| A    |       是 | ` M` | `apps/medqc-web/backend/app/services/document_assembly/__init__.py`                                                | 后端发布功能     | 样本同步、Bundle、Native 规则、Envelope 或结果 API 运行代码 |
| A    |       是 | ` M` | `apps/medqc-web/backend/app/services/document_assembly/assembler.py`                                               | 后端发布功能     | 样本同步、Bundle、Native 规则、Envelope 或结果 API 运行代码 |
| A    |       是 | ` M` | `apps/medqc-web/backend/app/services/etl_sync.py`                                                                  | 后端发布功能     | 样本同步、Bundle、Native 规则、Envelope 或结果 API 运行代码 |
| A    |       是 | ` M` | `apps/medqc-web/backend/app/services/luxian_0609/__init__.py`                                                      | 后端发布功能     | 样本同步、Bundle、Native 规则、Envelope 或结果 API 运行代码 |
| A    |       是 | `??` | `apps/medqc-web/backend/app/services/luxian_0609/consultation_020_relation_contract.py`                            | 后端发布功能     | 样本同步、Bundle、Native 规则、Envelope 或结果 API 运行代码 |
| A    |       是 | `??` | `apps/medqc-web/backend/app/services/luxian_0609/consultation_fact_contract.py`                                    | 后端发布功能     | 样本同步、Bundle、Native 规则、Envelope 或结果 API 运行代码 |
| A    |       是 | ` M` | `apps/medqc-web/backend/app/services/luxian_0609/customer_renderer.py`                                             | 后端发布功能     | 样本同步、Bundle、Native 规则、Envelope 或结果 API 运行代码 |
| A    |       是 | ` M` | `apps/medqc-web/backend/app/services/luxian_0609/customer_rule_package.py`                                         | 后端发布功能     | 样本同步、Bundle、Native 规则、Envelope 或结果 API 运行代码 |
| A    |       是 | ` M` | `apps/medqc-web/backend/app/services/luxian_0609/decision_model.py`                                                | 后端发布功能     | 样本同步、Bundle、Native 规则、Envelope 或结果 API 运行代码 |
| A    |       是 | ` M` | `apps/medqc-web/backend/app/services/luxian_0609/decision_reducer.py`                                              | 后端发布功能     | 样本同步、Bundle、Native 规则、Envelope 或结果 API 运行代码 |
| A    |       是 | ` M` | `apps/medqc-web/backend/app/services/luxian_0609/engine.py`                                                        | 后端发布功能     | 样本同步、Bundle、Native 规则、Envelope 或结果 API 运行代码 |
| A    |       是 | ` M` | `apps/medqc-web/backend/app/services/luxian_0609/execution.py`                                                     | 后端发布功能     | 样本同步、Bundle、Native 规则、Envelope 或结果 API 运行代码 |
| A    |       是 | ` M` | `apps/medqc-web/backend/app/services/luxian_0609/execution_contract.py`                                            | 后端发布功能     | 样本同步、Bundle、Native 规则、Envelope 或结果 API 运行代码 |
| A    |       是 | ` M` | `apps/medqc-web/backend/app/services/luxian_0609/executor_registry.py`                                             | 后端发布功能     | 样本同步、Bundle、Native 规则、Envelope 或结果 API 运行代码 |
| A    |       是 | ` M` | `apps/medqc-web/backend/app/services/luxian_0609/native_basic_timeliness.py`                                       | 后端发布功能     | 样本同步、Bundle、Native 规则、Envelope 或结果 API 运行代码 |
| A    |       是 | ` D` | `apps/medqc-web/backend/app/services/luxian_0609/native_consultation_021_023_execution.py`                         | 后端发布功能     | 样本同步、Bundle、Native 规则、Envelope 或结果 API 运行代码 |
| A    |       是 | ` M` | `apps/medqc-web/backend/app/services/luxian_0609/native_consultation_execution.py`                                 | 后端发布功能     | 样本同步、Bundle、Native 规则、Envelope 或结果 API 运行代码 |
| A    |       是 | ` M` | `apps/medqc-web/backend/app/services/luxian_0609/native_course_quality_execution.py`                               | 后端发布功能     | 样本同步、Bundle、Native 规则、Envelope 或结果 API 运行代码 |
| A    |       是 | ` M` | `apps/medqc-web/backend/app/services/luxian_0609/native_execution.py`                                              | 后端发布功能     | 样本同步、Bundle、Native 规则、Envelope 或结果 API 运行代码 |
| A    |       是 | `??` | `apps/medqc-web/backend/app/services/luxian_0609/native_extended_document_execution.py`                            | 后端发布功能     | 样本同步、Bundle、Native 规则、Envelope 或结果 API 运行代码 |
| A    |       是 | ` M` | `apps/medqc-web/backend/app/services/luxian_0609/native_package.py`                                                | 后端发布功能     | 样本同步、Bundle、Native 规则、Envelope 或结果 API 运行代码 |
| A    |       是 | ` M` | `apps/medqc-web/backend/app/services/luxian_0609/native_surgery_document_execution.py`                             | 后端发布功能     | 样本同步、Bundle、Native 规则、Envelope 或结果 API 运行代码 |
| A    |       是 | ` M` | `apps/medqc-web/backend/app/services/luxian_0609/native_surgery_gate_execution.py`                                 | 后端发布功能     | 样本同步、Bundle、Native 规则、Envelope 或结果 API 运行代码 |
| A    |       是 | ` M` | `apps/medqc-web/backend/app/services/luxian_0609/native_tumor_pathology_execution.py`                              | 后端发布功能     | 样本同步、Bundle、Native 规则、Envelope 或结果 API 运行代码 |
| A    |       是 | `??` | `apps/medqc-web/backend/app/services/luxian_0609/phase_scope.py`                                                   | 后端发布功能     | 样本同步、Bundle、Native 规则、Envelope 或结果 API 运行代码 |
| A    |       是 | ` M` | `apps/medqc-web/backend/app/services/luxian_0609/preproduction_runner.py`                                          | 后端发布功能     | 样本同步、Bundle、Native 规则、Envelope 或结果 API 运行代码 |
| A    |       是 | ` M` | `apps/medqc-web/backend/app/services/luxian_0609/rule_contracts.py`                                                | 后端发布功能     | 样本同步、Bundle、Native 规则、Envelope 或结果 API 运行代码 |
| A    |       是 | ` M` | `apps/medqc-web/backend/app/services/luxian_0609/runtime_shadow_input_provider.py`                                 | 后端发布功能     | 样本同步、Bundle、Native 规则、Envelope 或结果 API 运行代码 |
| A    |       是 | ` M` | `apps/medqc-web/backend/app/services/luxian_0609/source_evidence_reader.py`                                        | 后端发布功能     | 样本同步、Bundle、Native 规则、Envelope 或结果 API 运行代码 |
| A    |       是 | ` M` | `apps/medqc-web/backend/app/services/luxian_0609/source_registry.py`                                               | 后端发布功能     | 样本同步、Bundle、Native 规则、Envelope 或结果 API 运行代码 |
| A    |       是 | ` M` | `apps/medqc-web/backend/app/services/luxian_0609/surgery_text_fact_contract.py`                                    | 后端发布功能     | 样本同步、Bundle、Native 规则、Envelope 或结果 API 运行代码 |
| A    |       是 | ` M` | `apps/medqc-web/backend/app/services/luxian_0609_result_review_service.py`                                         | 后端发布功能     | 样本同步、Bundle、Native 规则、Envelope 或结果 API 运行代码 |
| A    |       是 | ` M` | `apps/medqc-web/backend/app/services/luxian_0609_rule_catalog.py`                                                  | 后端发布功能     | 样本同步、Bundle、Native 规则、Envelope 或结果 API 运行代码 |
| A    |       是 | ` M` | `apps/medqc-web/backend/app/services/sichuan_qc_service.py`                                                        | 后端发布功能     | 样本同步、Bundle、Native 规则、Envelope 或结果 API 运行代码 |
| B    |       是 | ` M` | `apps/medqc-web/backend/scripts/build_luxian_0609_golden_ledger.py`                                                | 后端发布工具     | 数据导出、黄金闸门和预生产验证工具                          |
| B    |       是 | ` M` | `apps/medqc-web/backend/scripts/export_visit_source_tables.ps1`                                                    | 后端发布工具     | 数据导出、黄金闸门和预生产验证工具                          |
| B    |       是 | ` M` | `apps/medqc-web/backend/scripts/run_luxian_0609_fixed10_readonly.py`                                               | 后端发布工具     | 数据导出、黄金闸门和预生产验证工具                          |
| B    |       是 | ` M` | `apps/medqc-web/backend/scripts/run_luxian_0609_preproduction_benchmark20.py`                                      | 后端发布工具     | 数据导出、黄金闸门和预生产验证工具                          |
| B    |       是 | ` M` | `apps/medqc-web/backend/scripts/run_luxian_0609_quality_gate.py`                                                   | 后端发布工具     | 数据导出、黄金闸门和预生产验证工具                          |
| B    |       是 | ` M` | `apps/medqc-web/backend/tests/unit/test_bundle_emr_view.py`                                                        | 后端测试         | 发布功能和结果链的回归证据                                  |
| B    |       是 | ` M` | `apps/medqc-web/backend/tests/unit/test_custom_qc_sample_pool_service.py`                                          | 后端测试         | 发布功能和结果链的回归证据                                  |
| B    |       是 | ` M` | `apps/medqc-web/backend/tests/unit/test_custom_qc_workspace_export_html.py`                                        | 后端测试         | 发布功能和结果链的回归证据                                  |
| B    |       是 | ` M` | `apps/medqc-web/backend/tests/unit/test_custom_qc_workspace_service_records.py`                                    | 后端测试         | 发布功能和结果链的回归证据                                  |
| B    |       是 | `??` | `apps/medqc-web/backend/tests/unit/test_document_assembly_blood_application.py`                                    | 后端测试         | 发布功能和结果链的回归证据                                  |
| B    |       是 | `??` | `apps/medqc-web/backend/tests/unit/test_document_identity_metadata.py`                                             | 后端测试         | 发布功能和结果链的回归证据                                  |
| B    |       是 | ` M` | `apps/medqc-web/backend/tests/unit/test_domain_bundle_assembly.py`                                                 | 后端测试         | 发布功能和结果链的回归证据                                  |
| B    |       是 | `??` | `apps/medqc-web/backend/tests/unit/test_export_visit_source_tables.py`                                             | 后端测试         | 发布功能和结果链的回归证据                                  |
| B    |       是 | ` M` | `apps/medqc-web/backend/tests/unit/test_llm_config_loader.py`                                                      | 后端测试         | 发布功能和结果链的回归证据                                  |
| B    |       是 | `??` | `apps/medqc-web/backend/tests/unit/test_luxian_0609_consultation_020_relation_contract.py`                         | 后端测试         | 发布功能和结果链的回归证据                                  |
| B    |       是 | `??` | `apps/medqc-web/backend/tests/unit/test_luxian_0609_consultation_fact_contract.py`                                 | 后端测试         | 发布功能和结果链的回归证据                                  |
| B    |       是 | ` M` | `apps/medqc-web/backend/tests/unit/test_luxian_0609_customer_renderer.py`                                          | 后端测试         | 发布功能和结果链的回归证据                                  |
| B    |       是 | ` M` | `apps/medqc-web/backend/tests/unit/test_luxian_0609_decision_reducer.py`                                           | 后端测试         | 发布功能和结果链的回归证据                                  |
| B    |       是 | ` M` | `apps/medqc-web/backend/tests/unit/test_luxian_0609_evidence_snapshot.py`                                          | 后端测试         | 发布功能和结果链的回归证据                                  |
| B    |       是 | ` M` | `apps/medqc-web/backend/tests/unit/test_luxian_0609_evidence_snapshot_provider.py`                                 | 后端测试         | 发布功能和结果链的回归证据                                  |
| B    |       是 | ` M` | `apps/medqc-web/backend/tests/unit/test_luxian_0609_execution_contract.py`                                         | 后端测试         | 发布功能和结果链的回归证据                                  |
| B    |       是 | ` M` | `apps/medqc-web/backend/tests/unit/test_luxian_0609_execution_failure_semantics.py`                                | 后端测试         | 发布功能和结果链的回归证据                                  |
| B    |       是 | ` M` | `apps/medqc-web/backend/tests/unit/test_luxian_0609_executor_registry.py`                                          | 后端测试         | 发布功能和结果链的回归证据                                  |
| B    |       是 | ` M` | `apps/medqc-web/backend/tests/unit/test_luxian_0609_full_regression_scope.py`                                      | 后端测试         | 发布功能和结果链的回归证据                                  |
| B    |       是 | ` M` | `apps/medqc-web/backend/tests/unit/test_luxian_0609_golden_gate.py`                                                | 后端测试         | 发布功能和结果链的回归证据                                  |
| B    |       是 | ` M` | `apps/medqc-web/backend/tests/unit/test_luxian_0609_golden_ledger.py`                                              | 后端测试         | 发布功能和结果链的回归证据                                  |
| B    |       是 | ` M` | `apps/medqc-web/backend/tests/unit/test_luxian_0609_mainline_services.py`                                          | 后端测试         | 发布功能和结果链的回归证据                                  |
| B    |       是 | ` M` | `apps/medqc-web/backend/tests/unit/test_luxian_0609_native_basic_timeliness.py`                                    | 后端测试         | 发布功能和结果链的回归证据                                  |
| B    |       是 | ` D` | `apps/medqc-web/backend/tests/unit/test_luxian_0609_native_consultation_021_023_execution.py`                      | 后端测试         | 发布功能和结果链的回归证据                                  |
| B    |       是 | ` M` | `apps/medqc-web/backend/tests/unit/test_luxian_0609_native_consultation_execution.py`                              | 后端测试         | 发布功能和结果链的回归证据                                  |
| B    |       是 | ` M` | `apps/medqc-web/backend/tests/unit/test_luxian_0609_native_course_quality_execution.py`                            | 后端测试         | 发布功能和结果链的回归证据                                  |
| B    |       是 | ` M` | `apps/medqc-web/backend/tests/unit/test_luxian_0609_native_execution.py`                                           | 后端测试         | 发布功能和结果链的回归证据                                  |
| B    |       是 | `??` | `apps/medqc-web/backend/tests/unit/test_luxian_0609_native_extended_document_execution.py`                         | 后端测试         | 发布功能和结果链的回归证据                                  |
| B    |       是 | ` M` | `apps/medqc-web/backend/tests/unit/test_luxian_0609_native_package.py`                                             | 后端测试         | 发布功能和结果链的回归证据                                  |
| B    |       是 | ` M` | `apps/medqc-web/backend/tests/unit/test_luxian_0609_native_surgery_document_execution.py`                          | 后端测试         | 发布功能和结果链的回归证据                                  |
| B    |       是 | ` M` | `apps/medqc-web/backend/tests/unit/test_luxian_0609_native_surgery_gate_execution.py`                              | 后端测试         | 发布功能和结果链的回归证据                                  |
| B    |       是 | ` M` | `apps/medqc-web/backend/tests/unit/test_luxian_0609_native_tumor_pathology_execution.py`                           | 后端测试         | 发布功能和结果链的回归证据                                  |
| B    |       是 | `??` | `apps/medqc-web/backend/tests/unit/test_luxian_0609_phase_scope.py`                                                | 后端测试         | 发布功能和结果链的回归证据                                  |
| B    |       是 | ` M` | `apps/medqc-web/backend/tests/unit/test_luxian_0609_preproduction_benchmark20.py`                                  | 后端测试         | 发布功能和结果链的回归证据                                  |
| B    |       是 | ` M` | `apps/medqc-web/backend/tests/unit/test_luxian_0609_preproduction_runner.py`                                       | 后端测试         | 发布功能和结果链的回归证据                                  |
| B    |       是 | ` M` | `apps/medqc-web/backend/tests/unit/test_luxian_0609_result_review_service.py`                                      | 后端测试         | 发布功能和结果链的回归证据                                  |
| B    |       是 | ` M` | `apps/medqc-web/backend/tests/unit/test_luxian_0609_rule_catalog.py`                                               | 后端测试         | 发布功能和结果链的回归证据                                  |
| B    |       是 | ` M` | `apps/medqc-web/backend/tests/unit/test_luxian_0609_rule_contracts.py`                                             | 后端测试         | 发布功能和结果链的回归证据                                  |
| B    |       是 | ` M` | `apps/medqc-web/backend/tests/unit/test_luxian_0609_runtime_shadow_input_provider.py`                              | 后端测试         | 发布功能和结果链的回归证据                                  |
| B    |       是 | `??` | `apps/medqc-web/backend/tests/unit/test_luxian_0609_single_record_evidence_excerpt.py`                             | 后端测试         | 发布功能和结果链的回归证据                                  |
| B    |       是 | ` M` | `apps/medqc-web/backend/tests/unit/test_luxian_0609_surgery_text_fact_contract.py`                                 | 后端测试         | 发布功能和结果链的回归证据                                  |
| B    |       是 | ` M` | `apps/medqc-web/backend/tests/unit/test_qc_sample_pools_router.py`                                                 | 后端测试         | 发布功能和结果链的回归证据                                  |
| B    |       是 | ` M` | `apps/medqc-web/backend/tests/unit/test_qc_sichuan_batch_throughput.py`                                            | 后端测试         | 发布功能和结果链的回归证据                                  |
| B    |       是 | ` M` | `apps/medqc-web/backend/tests/unit/test_settings_llm_env_alias.py`                                                 | 后端测试         | 发布功能和结果链的回归证据                                  |
| B    |       是 | ` M` | `apps/medqc-web/backend/tests/unit/test_sync_consistency.py`                                                       | 后端测试         | 发布功能和结果链的回归证据                                  |
| B    |       是 | `??` | `apps/medqc-web/backend/tests/unit/test_verify_release_source.py`                                                  | 后端测试         | 发布功能和结果链的回归证据                                  |
| B    |       是 | `??` | `apps/medqc-web/docs/0602/luxian0609-user-manual-assets`                                                           | 发布文档         | 规则范围、客户口径、部署或发布验收文档                      |
| B    |       是 | `??` | `apps/medqc-web/docs/0602/泸县0609客户样本验证用户使用手册.html`                                                   | 发布文档         | 规则范围、客户口径、部署或发布验收文档                      |
| B    |       是 | `??` | `apps/medqc-web/docs/0602/泸县0609质控点-客户业务口径反馈表-系统预填-v2.xlsx`                                      | 发布文档         | 规则范围、客户口径、部署或发布验收文档                      |
| B    |       是 | ` M` | `apps/medqc-web/docs/0602/泸县0609质控点-客户业务口径反馈表.xlsx`                                                  | 发布文档         | 规则范围、客户口径、部署或发布验收文档                      |
| B    |       是 | `??` | `apps/medqc-web/docs/deployment/客户机交付包编译打包指南.md`                                                       | 发布文档         | 规则范围、客户口径、部署或发布验收文档                      |
| B    |       是 | `??` | `apps/medqc-web/docs/plans/2026-07-23-customer-sample-validation-release-candidate.md`                             | 发布文档         | 规则范围、客户口径、部署或发布验收文档                      |
| B    |       是 | `??` | `apps/medqc-web/docs/plans/2026-07-27-lx0609-consultation-pause-progress.md`                                       | 发布文档         | 规则范围、客户口径、部署或发布验收文档                      |
| B    |       是 | `??` | `apps/medqc-web/docs/plans/2026-07-28-lx0609-case-2496813-repair-plan.md`                                          | 发布文档         | 规则范围、客户口径、部署或发布验收文档                      |
| B    |       是 | `??` | `apps/medqc-web/docs/plans/2026-07-29-lx0609-result-chain-stabilization-ledger.md`                                 | 发布文档         | 规则范围、客户口径、部署或发布验收文档                      |
| B    |       是 | `??` | `apps/medqc-web/docs/plans/2026-07-29-lx0609-single-record-result-vertical-slice.md`                               | 发布文档         | 规则范围、客户口径、部署或发布验收文档                      |
| B    |       是 | `??` | `apps/medqc-web/docs/plans/2026-07-31-qc-rule-defined-scope-development-task.md`                                   | 发布文档         | 规则范围、客户口径、部署或发布验收文档                      |
| B    |       是 | ` M` | `apps/medqc-web/docs/releases/baseline-20260731-rc1/classification-rules.json`                                     | 发布文档         | 规则范围、客户口径、部署或发布验收文档                      |
| B    |       是 | ` M` | `apps/medqc-web/scripts/package-customer-release.ps1`                                                              | 发布脚本         | 客户版打包、基线盘点和发布门禁脚本                          |
| B    |       是 | `??` | `apps/medqc-web/scripts/verify_release_source.py`                                                                  | 发布脚本         | 客户版打包、基线盘点和发布门禁脚本                          |
| D    |       否 | ` M` | `apps/medqc-web/src/components.d.ts`                                                                               | 前端生成文件     | 组件声明自动生成文件，开发环境已要求默认不生成              |
| A    |       是 | `??` | `apps/medqc-web/src/domain/customer-qc/status-policy.ts`                                                           | 前端质控领域模型 | Canonical 状态展示策略                                      |
| A    |       是 | ` M` | `apps/medqc-web/src/services/manual-case-sample-service.ts`                                                        | 前端样本服务     | 客户样本池 API 数据链                                       |
| C    |       否 | ` M` | `apps/medqc-web/src/views/dashboard/records/FinalRecordsView.vue`                                                  | 非本轮页面改动   | 与客户样本验证发布主链无直接关系，保留快照后转后续审查      |
| C    |       否 | ` M` | `apps/medqc-web/src/views/dashboard/records/OutpatientEmergencyDetailDrawer.vue`                                   | 非本轮页面改动   | 与客户样本验证发布主链无直接关系，保留快照后转后续审查      |
| C    |       否 | ` M` | `apps/medqc-web/src/views/dashboard/records/OutpatientEmergencyRecordsView.vue`                                    | 非本轮页面改动   | 与客户样本验证发布主链无直接关系，保留快照后转后续审查      |
| C    |       否 | ` M` | `apps/medqc-web/src/views/dashboard/records/RunningRecordsViewNew.vue`                                             | 非本轮页面改动   | 与客户样本验证发布主链无直接关系，保留快照后转后续审查      |
| C    |       否 | ` M` | `apps/medqc-web/src/views/drg-grouper/CnDrgGrouperView.vue`                                                        | 非本轮页面改动   | 与客户样本验证发布主链无直接关系，保留快照后转后续审查      |
| A    |       是 | ` M` | `apps/medqc-web/src/views/workstation-v4/CustomerSampleValidationView.vue`                                         | 客户样本验证     | 样本池同步、任务执行和结果入口主页面                        |
| A    |       是 | ` M` | `apps/medqc-web/src/views/workstation-v4/DataSyncConfigPage.vue`                                                   | 数据同步配置     | 客户数据同步配置与科室/住院范围入口                         |
| A    |       是 | ` M` | `apps/medqc-web/src/views/workstation-v4/WorkstationLoginView.vue`                                                 | 客户工作台登录   | 客户版实际登录入口                                          |
| C    |       否 | ` M` | `apps/medqc-web/src/views/workstation-v4/WorkstationV2View.vue`                                                    | 非本轮页面改动   | 与客户样本验证发布主链无直接关系，保留快照后转后续审查      |
| C    |       否 | ` M` | `apps/medqc-web/src/views/workstation-v4/WorkstationV3View.vue`                                                    | 非本轮页面改动   | 与客户样本验证发布主链无直接关系，保留快照后转后续审查      |
| A    |       是 | ` M` | `apps/medqc-web/src/views/workstation-v4/WorkstationV4HomeEntry.vue`                                               | 客户工作台入口   | 客户样本验证页面入口集成                                    |
| A    |       是 | ` M` | `apps/medqc-web/src/views/workstation-v4/WorkstationV4View.vue`                                                    | 客户工作台容器   | 客户样本验证路由和容器集成                                  |
| C    |       否 | ` M` | `apps/medqc-web/src/views/workstation-v4/components/ClinicalCompletenessPanel.vue`                                 | 非本轮页面改动   | 与客户样本验证发布主链无直接关系，保留快照后转后续审查      |
| C    |       否 | ` M` | `apps/medqc-web/src/views/workstation-v4/components/ContentQCTab.vue`                                              | 非本轮页面改动   | 与客户样本验证发布主链无直接关系，保留快照后转后续审查      |
| A    |       是 | ` M` | `apps/medqc-web/src/views/workstation-v4/components/DetailHeader.vue`                                              | 病历详情         | 在院/出院病历详情状态展示                                   |
| A    |       是 | ` M` | `apps/medqc-web/src/views/workstation-v4/components/DetailSidebar.vue`                                             | 病历详情         | 文书目录和质控结果核对入口                                  |
| C    |       否 | ` M` | `apps/medqc-web/src/views/workstation-v4/components/DraftListSidebar.vue`                                          | 非本轮页面改动   | 与客户样本验证发布主链无直接关系，保留快照后转后续审查      |
| C    |       否 | ` M` | `apps/medqc-web/src/views/workstation-v4/components/FrontpageRulesOverview.vue`                                    | 非本轮页面改动   | 与客户样本验证发布主链无直接关系，保留快照后转后续审查      |
| C    |       否 | ` M` | `apps/medqc-web/src/views/workstation-v4/components/FrontpageSheet.vue`                                            | 非本轮页面改动   | 与客户样本验证发布主链无直接关系，保留快照后转后续审查      |
| C    |       否 | ` M` | `apps/medqc-web/src/views/workstation-v4/components/FrontpageTenderValidationDrawer.vue`                           | 非本轮页面改动   | 与客户样本验证发布主链无直接关系，保留快照后转后续审查      |
| C    |       否 | ` M` | `apps/medqc-web/src/views/workstation-v4/components/FrontpageWorkspace.vue`                                        | 非本轮页面改动   | 与客户样本验证发布主链无直接关系，保留快照后转后续审查      |
| C    |       否 | ` M` | `apps/medqc-web/src/views/workstation-v4/components/FrontpageWorkspacePanel.vue`                                   | 非本轮页面改动   | 与客户样本验证发布主链无直接关系，保留快照后转后续审查      |
| C    |       否 | ` M` | `apps/medqc-web/src/views/workstation-v4/components/ICDDetailPanel.vue`                                            | 非本轮页面改动   | 与客户样本验证发布主链无直接关系，保留快照后转后续审查      |
| C    |       否 | ` M` | `apps/medqc-web/src/views/workstation-v4/components/ICDRecentBar.vue`                                              | 非本轮页面改动   | 与客户样本验证发布主链无直接关系，保留快照后转后续审查      |
| C    |       否 | ` M` | `apps/medqc-web/src/views/workstation-v4/components/ICDSearchHero.vue`                                             | 非本轮页面改动   | 与客户样本验证发布主链无直接关系，保留快照后转后续审查      |
| C    |       否 | ` M` | `apps/medqc-web/src/views/workstation-v4/components/ICDSearchPanel.vue`                                            | 非本轮页面改动   | 与客户样本验证发布主链无直接关系，保留快照后转后续审查      |
| A    |       是 | ` M` | `apps/medqc-web/src/views/workstation-v4/components/PatientCardGrid.vue`                                           | 病历池           | 在院/出院病历状态与病历池展示                               |
| C    |       否 | ` M` | `apps/medqc-web/src/views/workstation-v4/components/QCAgentChatDrawer.vue`                                         | 非本轮页面改动   | 与客户样本验证发布主链无直接关系，保留快照后转后续审查      |
| C    |       否 | ` M` | `apps/medqc-web/src/views/workstation-v4/components/QCAlertPanel.vue`                                              | 非本轮页面改动   | 与客户样本验证发布主链无直接关系，保留快照后转后续审查      |
| C    |       否 | ` M` | `apps/medqc-web/src/views/workstation-v4/components/QCResultTab.vue`                                               | 非本轮页面改动   | 与客户样本验证发布主链无直接关系，保留快照后转后续审查      |
| A    |       是 | ` M` | `apps/medqc-web/src/views/workstation-v4/components/RecordDetailWorkspace.vue`                                     | 病历详情         | 病历文书与质控结果工作区                                    |
| C    |       否 | ` M` | `apps/medqc-web/src/views/workstation-v4/components/SettlementRulesOverview.vue`                                   | 非本轮页面改动   | 与客户样本验证发布主链无直接关系，保留快照后转后续审查      |
| C    |       否 | ` M` | `apps/medqc-web/src/views/workstation-v4/components/SettlementSheet.vue`                                           | 非本轮页面改动   | 与客户样本验证发布主链无直接关系，保留快照后转后续审查      |
| C    |       否 | ` M` | `apps/medqc-web/src/views/workstation-v4/components/SettlementWorkspace.vue`                                       | 非本轮页面改动   | 与客户样本验证发布主链无直接关系，保留快照后转后续审查      |
| C    |       否 | ` M` | `apps/medqc-web/src/views/workstation-v4/components/TenderAcceptanceDashboard.vue`                                 | 非本轮页面改动   | 与客户样本验证发布主链无直接关系，保留快照后转后续审查      |
| A    |       是 | ` M` | `apps/medqc-web/src/views/workstation-v4/components/WorkstationV4DetailView.vue`                                   | 病历详情         | 客户工作台病历详情容器                                      |
| A    |       是 | ` M` | `apps/medqc-web/src/views/workstation-v4/components/WorkstationV4ListView.vue`                                     | 病历池           | 在院和已出院病历列表                                        |
| C    |       否 | ` M` | `apps/medqc-web/src/views/workstation-v4/components/WorkstationV4RulesView.vue`                                    | 非本轮页面改动   | 与客户样本验证发布主链无直接关系，保留快照后转后续审查      |
| C    |       否 | ` M` | `apps/medqc-web/src/views/workstation-v4/components/frontpage/FrontpageFieldsPanel.vue`                            | 非本轮页面改动   | 与客户样本验证发布主链无直接关系，保留快照后转后续审查      |
| C    |       否 | ` M` | `apps/medqc-web/src/views/workstation-v4/components/frontpage/FrontpagePreviewSheet.vue`                           | 非本轮页面改动   | 与客户样本验证发布主链无直接关系，保留快照后转后续审查      |
| C    |       否 | ` M` | `apps/medqc-web/src/views/workstation-v4/components/frontpage/FrontpagePreviewTabs.vue`                            | 非本轮页面改动   | 与客户样本验证发布主链无直接关系，保留快照后转后续审查      |
| C    |       否 | ` M` | `apps/medqc-web/src/views/workstation-v4/components/frontpage/MainDiagnosisEvidenceModal.vue`                      | 非本轮页面改动   | 与客户样本验证发布主链无直接关系，保留快照后转后续审查      |
| A    |       是 | ` M` | `apps/medqc-web/src/views/workstation-v4/components/sync-console/ConnectionStudio.vue`                             | 数据同步控制台   | 住院范围、字段映射和同步进度展示                            |
| A    |       是 | ` M` | `apps/medqc-web/src/views/workstation-v4/components/sync-console/FieldMappingWorkbench.vue`                        | 数据同步控制台   | 住院范围、字段映射和同步进度展示                            |
| A    |       是 | ` M` | `apps/medqc-web/src/views/workstation-v4/components/sync-console/SchemaExplorer.vue`                               | 数据同步控制台   | 住院范围、字段映射和同步进度展示                            |
| A    |       是 | ` M` | `apps/medqc-web/src/views/workstation-v4/components/sync-console/SyncOverviewBar.vue`                              | 数据同步控制台   | 住院范围、字段映射和同步进度展示                            |
| A    |       是 | ` M` | `apps/medqc-web/src/views/workstation-v4/components/sync-console/SyncRunPanel.vue`                                 | 数据同步控制台   | 住院范围、字段映射和同步进度展示                            |
| C    |       否 | ` M` | `apps/medqc-web/src/views/workstation-v4/components/workbench/BatchTablePanel.vue`                                 | 非本轮页面改动   | 与客户样本验证发布主链无直接关系，保留快照后转后续审查      |
| C    |       否 | ` M` | `apps/medqc-web/src/views/workstation-v4/components/workbench/PriorityLane.vue`                                    | 非本轮页面改动   | 与客户样本验证发布主链无直接关系，保留快照后转后续审查      |
| A    |       是 | ` M` | `apps/medqc-web/src/views/workstation-v4/customer-sample-validation/CustomerSampleTaskHistoryView.vue`             | 客户样本验证     | 病历文书、任务历史和样本详情展示                            |
| A    |       是 | ` M` | `apps/medqc-web/src/views/workstation-v4/customer-sample-validation/ReadonlyMedicalDocumentContent.vue`            | 客户样本验证     | 病历文书、任务历史和样本详情展示                            |
| A    |       是 | ` M` | `apps/medqc-web/src/views/workstation-v4/customer-sample-validation/ReadonlyMedicalDocumentDirectory.vue`          | 客户样本验证     | 病历文书、任务历史和样本详情展示                            |
| A    |       是 | ` M` | `apps/medqc-web/src/views/workstation-v4/customer-sample-validation/ReadonlyMedicalOrderTable.vue`                 | 客户样本验证     | 病历文书、任务历史和样本详情展示                            |
| A    |       是 | ` M` | `apps/medqc-web/src/views/workstation-v4/customer-sample-validation/SyntheticCaseBuilderView.vue`                  | 客户样本验证     | 病历文书、任务历史和样本详情展示                            |
| A    |       是 | ` M` | `apps/medqc-web/src/views/workstation-v4/customer-sample-validation/types.ts`                                      | 客户样本验证     | 病历文书、任务历史和样本详情展示                            |
| C    |       否 | ` M` | `apps/medqc-web/src/views/workstation-v4/frontpage/components/AIProfileDashboard.vue`                              | 非本轮页面改动   | 与客户样本验证发布主链无直接关系，保留快照后转后续审查      |
| C    |       否 | ` M` | `apps/medqc-web/src/views/workstation-v4/frontpage/components/CodingOptimizationDrawer.vue`                        | 非本轮页面改动   | 与客户样本验证发布主链无直接关系，保留快照后转后续审查      |
| C    |       否 | ` M` | `apps/medqc-web/src/views/workstation-v4/frontpage/components/DRGGroupingTab.vue`                                  | 非本轮页面改动   | 与客户样本验证发布主链无直接关系，保留快照后转后续审查      |
| C    |       否 | ` M` | `apps/medqc-web/src/views/workstation-v4/frontpage/components/ExcelUploadView.vue`                                 | 非本轮页面改动   | 与客户样本验证发布主链无直接关系，保留快照后转后续审查      |
| C    |       否 | ` M` | `apps/medqc-web/src/views/workstation-v4/frontpage/components/FieldMappingStep.vue`                                | 非本轮页面改动   | 与客户样本验证发布主链无直接关系，保留快照后转后续审查      |
| C    |       否 | ` M` | `apps/medqc-web/src/views/workstation-v4/frontpage/components/FrontPageResultTabs.vue`                             | 非本轮页面改动   | 与客户样本验证发布主链无直接关系，保留快照后转后续审查      |
| C    |       否 | ` M` | `apps/medqc-web/src/views/workstation-v4/frontpage/components/InProcessMonitoringView.vue`                         | 非本轮页面改动   | 与客户样本验证发布主链无直接关系，保留快照后转后续审查      |
| C    |       否 | ` M` | `apps/medqc-web/src/views/workstation-v4/frontpage/components/InsuranceClaimView.vue`                              | 非本轮页面改动   | 与客户样本验证发布主链无直接关系，保留快照后转后续审查      |
| C    |       否 | ` M` | `apps/medqc-web/src/views/workstation-v4/frontpage/components/MedicalRecordPanel.vue`                              | 非本轮页面改动   | 与客户样本验证发布主链无直接关系，保留快照后转后续审查      |
| C    |       否 | ` M` | `apps/medqc-web/src/views/workstation-v4/frontpage/components/OverCostAnalysisCard.vue`                            | 非本轮页面改动   | 与客户样本验证发布主链无直接关系，保留快照后转后续审查      |
| C    |       否 | ` M` | `apps/medqc-web/src/views/workstation-v4/frontpage/components/PaymentMonitoringView.vue`                           | 非本轮页面改动   | 与客户样本验证发布主链无直接关系，保留快照后转后续审查      |
| C    |       否 | ` M` | `apps/medqc-web/src/views/workstation-v4/frontpage/components/PostEventAnalysisView.vue`                           | 非本轮页面改动   | 与客户样本验证发布主链无直接关系，保留快照后转后续审查      |
| C    |       否 | ` M` | `apps/medqc-web/src/views/workstation-v4/frontpage/components/PreAnalysisView.vue`                                 | 非本轮页面改动   | 与客户样本验证发布主链无直接关系，保留快照后转后续审查      |
| A    |       是 | ` M` | `apps/medqc-web/src/views/workstation-v4/frontpage/components/StructuredDataView.vue`                              | 结构化文书查看   | 输血、麻醉及其他结构化文书展示                              |
| C    |       否 | ` M` | `apps/medqc-web/src/views/workstation-v4/frontpage/components/TestCaseListView.vue`                                | 非本轮页面改动   | 与客户样本验证发布主链无直接关系，保留快照后转后续审查      |
| A    |       是 | `??` | `apps/medqc-web/src/views/workstation-v4/semantic-rules/components/CustomerQcResultDetailCard.vue`                 | 质控结果展示     | 单一结果 API 的 Canonical Envelope 渲染与病历核对           |
| A    |       是 | ` M` | `apps/medqc-web/src/views/workstation-v4/semantic-rules/components/QCRecordCompareWorkbench.vue`                   | 质控结果展示     | 单一结果 API 的 Canonical Envelope 渲染与病历核对           |
| A    |       是 | ` M` | `apps/medqc-web/src/views/workstation-v4/semantic-rules/components/SemanticRulesBatchResultDrawer.vue`             | 质控结果展示     | 单一结果 API 的 Canonical Envelope 渲染与病历核对           |
| A    |       是 | ` M` | `apps/medqc-web/src/views/workstation-v4/semantic-rules/components/SemanticRulesTableSection.vue`                  | 质控结果展示     | 单一结果 API 的 Canonical Envelope 渲染与病历核对           |
| A    |       是 | ` M` | `apps/medqc-web/src/views/workstation-v4/semantic-rules/components/modals/SemanticRuleDetailModal.vue`             | 质控结果展示     | 单一结果 API 的 Canonical Envelope 渲染与病历核对           |
| A    |       是 | ` M` | `apps/medqc-web/src/views/workstation-v4/semantic-rules/components/modals/SemanticRuleTestModal.vue`               | 质控结果展示     | 单一结果 API 的 Canonical Envelope 渲染与病历核对           |
| A    |       是 | `??` | `apps/medqc-web/src/views/workstation-v4/semantic-rules/record-comparison-model.ts`                                | 质控结果展示     | 单一结果 API 的 Canonical Envelope 渲染与病历核对           |
| A    |       是 | ` M` | `apps/medqc-web/src/views/workstation-v4/semantic-rules/types.ts`                                                  | 质控结果展示     | 单一结果 API 的 Canonical Envelope 渲染与病历核对           |
| C    |       否 | ` M` | `apps/medqc-web/src/views/workstation/QCOverviewView.vue`                                                          | 非本轮页面改动   | 与客户样本验证发布主链无直接关系，保留快照后转后续审查      |
| C    |       否 | ` M` | `apps/medqc-web/src/views/workstation/components/HomeHeroBar.vue`                                                  | 非本轮页面改动   | 与客户样本验证发布主链无直接关系，保留快照后转后续审查      |
| C    |       否 | ` M` | `apps/medqc-web/src/views/workstation/components/HomeKpiStrip.vue`                                                 | 非本轮页面改动   | 与客户样本验证发布主链无直接关系，保留快照后转后续审查      |
| C    |       否 | ` M` | `apps/medqc-web/src/views/workstation/components/HotspotDetailPanel.vue`                                           | 非本轮页面改动   | 与客户样本验证发布主链无直接关系，保留快照后转后续审查      |
| C    |       否 | ` M` | `apps/medqc-web/src/views/workstation/components/HotspotListPanel.vue`                                             | 非本轮页面改动   | 与客户样本验证发布主链无直接关系，保留快照后转后续审查      |
| C    |       否 | ` M` | `apps/medqc-web/src/views/workstation/components/MyTodoListPanel.vue`                                              | 非本轮页面改动   | 与客户样本验证发布主链无直接关系，保留快照后转后续审查      |
| C    |       否 | ` M` | `apps/medqc-web/src/views/workstation/components/MyTodoSummaryPanel.vue`                                           | 非本轮页面改动   | 与客户样本验证发布主链无直接关系，保留快照后转后续审查      |
| C    |       否 | ` M` | `apps/medqc-web/src/views/workstation/components/StatusBar.vue`                                                    | 非本轮页面改动   | 与客户样本验证发布主链无直接关系，保留快照后转后续审查      |
| C    |       否 | ` M` | `apps/medqc-web/src/views/workstation/components/TeamSummaryPanel.vue`                                             | 非本轮页面改动   | 与客户样本验证发布主链无直接关系，保留快照后转后续审查      |
| B    |       是 | ` M` | `apps/medqc-web/tests/unit/services/manual-case-sample-service.spec.ts`                                            | 前端测试         | 客户样本验证和结果展示的回归证据                            |
| B    |       是 | ` M` | `apps/medqc-web/tests/unit/views/workstation-v4/CustomerSampleValidationView.spec.ts`                              | 前端测试         | 客户样本验证和结果展示的回归证据                            |
| B    |       是 | `??` | `apps/medqc-web/tests/unit/views/workstation-v4/customer-sample-validation/ReadonlyMedicalDocumentContent.spec.ts` | 前端测试         | 客户样本验证和结果展示的回归证据                            |
| B    |       是 | `??` | `apps/medqc-web/tests/unit/views/workstation-v4/semantic-rules/CustomerQcResultDetailCard.spec.ts`                 | 前端测试         | 客户样本验证和结果展示的回归证据                            |
| B    |       是 | ` M` | `apps/medqc-web/tests/unit/views/workstation-v4/semantic-rules/SemanticRulesBatchResultDrawer.spec.ts`             | 前端测试         | 客户样本验证和结果展示的回归证据                            |
| B    |       是 | `??` | `apps/medqc-web/tests/unit/views/workstation-v4/semantic-rules/recordComparisonModel.spec.ts`                      | 前端测试         | 客户样本验证和结果展示的回归证据                            |
| D    |       否 | `??` | `tmp-npm-single-record-panel`                                                                                      | 本地临时产物     | 仓库根目录临时验证产物                                      |
