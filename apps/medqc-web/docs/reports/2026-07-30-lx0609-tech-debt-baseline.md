# LX0609 技术债治理基线

## 1. 基线身份

- 采集日期：2026-07-30
- 仓库：`D:\LLM\LX888\apps\medqc-web`
- 当前分支：`codex/synthetic-case-wizard-20260619`
- HEAD：`8eb667a5ac9b61d704ba470edecbcf67f6b1bb41`
- CodeGraph：索引正常且为最新，8438 个文件、176331 个节点、514453 条边
- 实施计划：`docs/plans/2026-07-30-lx0609-tech-debt-remediation-plan.md`

## 2. 工作区状态和实施边界

当前工作区包含大量未提交修改，不能将其视为干净的 HEAD 基线。与本轮前两个修复批次直接相关的状态如下：

| 文件 | 当前状态 | 计划批次 |
|---|---|---|
| `backend/app/services/luxian_0609/execution.py` | 已修改 | Task 1 |
| `backend/app/services/sichuan_qc_service.py` | 已修改 | Task 1 |
| `backend/app/services/luxian_0609/decision_reducer.py` | 已修改 | Task 1 |
| `backend/app/services/luxian_0609/source_registry.py` | 已修改 | Task 2 |
| `backend/app/services/luxian_0609/source_evidence_reader.py` | 已修改 | Task 2 |
| `backend/app/services/bundles/assembly.py` | HEAD 状态 | Task 2 |
| `backend/app/services/bundles/emr_view.py` | HEAD 状态 | Task 2 |
| `backend/app/services/custom_qc_workspace_service.py` | 已修改 | Task 4/5 |
| `backend/app/services/luxian_0609/record_result_read_model.py` | 未跟踪 | Task 4/5 |
| `src/domain/customer-qc/result-normalizer.ts` | 未跟踪 | Task 7 |
| `src/views/workstation-v4/customer-sample-validation/single-record-result-model.ts` | 未跟踪 | Task 7 |
| `src/views/workstation-v4/semantic-rules/customer-qc-display-model.ts` | 未跟踪 | Task 7 |

实施约束：

1. 只按任务文件白名单编辑和暂存。
2. 不 reset、restore、覆盖或批量格式化现有修改。
3. 每次编辑前后都单独审查目标文件 diff。
4. 不让两个实现者同时修改同一文件。
5. 无法证明某段现有 diff 属于本轮时，停止并先拆分归属。

计划初稿曾把 Bundle 路径误写为
`backend/app/services/luxian_0609/bundle/...`；只读调用链复核确认真实模块为
`backend/app/services/bundles/{assembly,emr_view}.py`，计划已同步修正。

## 3. 后端测试基线

基线命令：

```powershell
python -m pytest backend/tests/unit/test_luxian_0609_mainline_services.py backend/tests/unit/test_luxian_0609_result_aggregator.py backend/tests/unit/test_luxian_0609_record_result_read_model.py backend/tests/integration/test_qc_sichuan_workspace_batch_flow.py -q
```

已知基线：

- 共 247 项。
- 232 项通过、15 项失败、19 条 warning。
- Pytest 内部耗时 15.69 秒，PowerShell 端到端墙钟 57.183 秒。
- `test_luxian_0609_result_aggregator.py`：69 项通过。
- `test_luxian_0609_record_result_read_model.py`：4 项通过。
- `test_qc_sichuan_workspace_batch_flow.py`：4 项通过。
- `test_luxian_0609_mainline_services.py`：170 项中 155 项通过、15 项失败。

15 项失败：

1. `test_unified_engine_uses_registry_order_once_and_keeps_customer_order`
2. `test_transfusion_044_047_typed_decisions_replace_raw_results_without_drift`
3. `test_tumor_and_course_admission_typed_flags_reach_unified_reducer`
4. `test_native_transfusion_public_entry_bypasses_legacy_rules_and_keeps_order`
5. `test_remaining_native_families_bypass_all_legacy_rules_and_keep_customer_order`
6. `test_lx0609_033_available_consent_preserves_semantic_dispatch_without_live_reader[non_compliant]`
7. `test_aggregator_should_prioritize_non_compliant_over_primary_compliant`
8. `test_aggregator_should_keep_specimen_detail_absence_as_non_compliant`
9. `test_aggregator_should_use_copy_compare_evidence_for_lx0609_017`
10. `test_aggregator_should_strip_sensitive_raw_fields`
11. `test_aggregator_should_add_schema_fields_for_non_compliant_result`
12. `test_aggregator_should_prioritize_direct_customer_programmatic_result`
13. `test_programmatic_timeline_schema_should_include_threshold_actual_and_delta`
14. `test_cross_document_schema_should_keep_multiple_source_documents_and_quotes`
15. `test_lx0609_018_semantic_result_should_be_review_needed`

失败原因初步分组：

1. 新 Decision/Reducer 合同与旧状态断言漂移。
2. 客户解释质量门将缺少受控事实的 `non_compliant` 安全降为 `uncertain`，旧聚合断言仍期待确定不合规。
3. 测试 fixture 使用 `SimpleNamespace`，缺少新增的 `customer_display_facts` 字段。
4. 会诊 033 等派发和状态合同仍有未收口差异。

上述失败在 Task 6 前不得通过批量修改 expected 或删除测试处理。

## 4. 前端测试基线

基线命令：

```powershell
npm run test:unit -- --run tests/unit/views/workstation-v4/customer-sample-validation tests/unit/views/workstation-v4/semantic-rules/customerQcDisplayModel.spec.ts tests/unit/views/workstation-v4/semantic-rules/CustomerQcResultDetailCard.spec.ts
```

基线结果：

- 5 个测试文件。
- 27 项测试全部通过。
- Vitest 内部耗时 18.67 秒，PowerShell 端到端墙钟 25.435 秒。
- 非阻断提示：`caniuse-lite` 数据约 11 个月未更新。
- 单病历结果模型会保留后端规范状态。
- 非合规解释不完整时不会由浏览器补造医学事实。
- 未识别和非确定状态进入待确认分组。

## 5. 真实病例 Envelope 基线

只读查询范围：

```text
institute_id = 泸县人民医院
patient_id = 0000225510
visit_id / record_id = 2496813
最近 5 个 record result envelopes
```

最近五次结果完全一致：

| 指标 | 数值 |
|---|---:|
| Envelope 数 | 5 |
| 每次声明结果数 | 49 |
| 每次实际结果数 | 49 |
| compliant | 14 |
| non_compliant | 4 |
| not_applicable | 7 |
| data_gap | 23 |
| uncertain | 1 |
| 重复 rule_id | 0 |
| 空 `data_gap_details` | 23 |

结论：结果数量与唯一性当前稳定，但数据缺口解释完整度为 0%，是客户可解释性阻断项。

## 6. Bundle 基线

同一病例通过当前 `load_bundle_documents` 只读装载：

- 文书/数据项总数：270。
- Domain 命中：admission、course、surgery、consult_discussion、terminal、index_coding_settlement。

主要来源计数：

| doc_type | 数量 |
|---|---:|
| admission_record | 1 |
| anesthesia_record | 2 |
| bloodtrans_record | 3 |
| consultation_record | 6 |
| daily_course_record | 9 |
| discharge_record | 1 |
| first_course_record | 1 |
| inpat_drug_order | 113 |
| inpat_nondrug_order | 113 |
| postsurg_firstcourse_record | 2 |
| presurg_summary | 1 |
| rescue_record | 1 |
| senior_course_record | 7 |
| surgery_application | 2 |
| surgery_inventory_record | 1 |
| surgery_record | 2 |
| surgery_safecheck_record | 2 |

Bundle 中没有 `preane_surveil_record`、`postane_surveil_record` 和麻醉知情同意书。当前 Evidence source 侧已能独立表达麻醉访视来源，因此存在执行材料与展示材料的注册漂移。

## 7. 性能和模型成本基线

病例最近一次任务：

| 指标 | 数值 |
|---|---:|
| wall time | 11.675289 秒 |
| total processing time | 10.801333 秒 |
| total tokens | 6909 |
| prompt tokens（任务摘要） | 5529 |
| completion tokens（任务摘要） | 1400 |
| retry count | 0 |
| provider error count | 0 |
| timeout count | 0 |
| cache hit/miss | 0 / 49 |

性能元数据另记录：

- `llm_call_count = 47`
- `llm_call_count_basis = result_participation_count`
- `actual_llm_pack_call_count = 0`
- `program_call_count = 2`

这里的 47 不是可验证的真实供应商请求次数，而是“结果参与计数”。Task 8 比较模型调用成本时必须同时报告真实请求数和参与规则数，不能混用。

## 8. 当前发布判断

当前不能判断为结果链路稳定完成，原因：

1. 后端主链仍有 15 项失败。
2. 真实病例 23 条数据缺口均无结构化说明。
3. Evidence 与 Bundle 来源目录存在已证明的漂移。
4. 技术错误、业务数据缺口和客户展示降级尚未形成完整可执行不变量。
5. Envelope 写入失败仍可能与任务完成状态脱节。

Task 1 的首个 tracer bullet 固定为：

```text
Evidence snapshot 内部构建异常
  -> 受控 technical_error
  -> 保留内部 trace
  -> 不转换为 data_gap
```

只有该行为完成 RED→GREEN 并审查目标文件现有 diff 后，才进入合规率口径修复。
