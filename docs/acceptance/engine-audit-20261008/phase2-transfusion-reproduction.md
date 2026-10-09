# 第二阶段输血043–048当前版本复现

## 固定身份与范围

- 基线：`4dbcd8e819f439c576262eebd1565f0eab0774e2`，工作树 `F:/MedQC-worktrees/qc-integration-20261008`。
- 当前 `native_transfusion_execution.py` SHA256：`bdc7dfd538fa8b13cfa434804835d73777d9f25cd1b08e9bdc6a02d51edaf652`。
- 043–048 对应 `LX0609-07-01-01`、`07-01-02`、`07-02-01`、`07-02-02`、`07-03-01`、`07-04-01`。当前 `luxian_0609_rule_master_v1.json` 六条均为 `implementation_status=active`；均未声明非默认 `release_scope` 或暂停 `phase_status`。
- 现行 `luxian_0609_rule_master.py:182`、`:187` 将缺省字段分别补为 `default`、`phase_1_target`；`luxian_0609/phase_scope.py:174` 的选择分区保留 phase target。因此六条属于当前默认可执行范围。这里核实配置及选择逻辑，不声称已创建或执行真实任务。
- 当前输血合同六条均 `native_async`、`typed_shadow_v1`、`golden_gate_state=pending`。可执行范围不能证明实际终态已验收。

## 原反例、独立预期与复现边界

执行前冻结 `.tmp/phase2-transfusion-20261009/frozen-manifest.json`，保留历史输入及预期原样，并记录七份来源文件hash。原TC01来自 `next-batch/transfusion-family/tc01-original-cases.json`；原TC03来自 `.tmp/engine-audit-20261008/treatment-consultation/048-frozen-expectations.json`。

| 根因 | 冻结检查 | 独立预期 | 当前重放入口 |
| --- | --- | --- | --- |
| TC01：未实施正文被当作已实施 | TF_PLAN、TF_REFUSED、TF_POSTPONED、TF_PLAN_COMPLETE_FIELDS | gate=`data_gap`，不能据此进入缺陷分支 | `_performed_source_state`；完整计划另重放 `_programmatic_046_status` 原纯函数 |
| TC01正常保护 | TF_CANCELLED | gate=`data_gap` | `_performed_source_state` |
| TC01正常保护 | TF_ACTUAL_NO_REACTION | gate=`present` | `_performed_source_state` |
| TC03：术前备血被当作术中实施 | 048_NEGATED_INTRAOPERATIVE | `not_applicable`；不得把2U/4U/2U备血差异当作实际输血差异 | `_programmatic_048_status` |
| TC03正常保护 | 048_MATCHED | `compliant`（2U与2单位归一） | `_programmatic_048_status` |
| TC03正常保护 | 048_TIME_CONFLICT | `data_gap`，关联冲突 | `_programmatic_048_status` |

新脚本 `.tmp/phase2-transfusion-20261009/reproduce.py` 按当前源码AST抽取三个根函数及所有传递依赖，保留原节点/定义顺序，只替换来源reader为冻结合成行。库依赖显式提供；不导入应用，不访问环境/数据库/模型。输出依赖闭包、源码hash、基线、预期与实际结果，禁止覆盖首跑文件。

最小命令：`python .tmp/phase2-transfusion-20261009/reproduce.py`。root授予唯一窗口后已执行一次，退出0；窗口已释放。9例结果只能证明当前纯函数症状，不能证明正式executor、Typed Decision、Finalizer、保存/API/页面链通过。

## 共同门控消费者与后续保护入口

现行native executor `_performed_source_state` 位于2874；正式legacy调用3081，typed调用3115；随后非present退出，因此TC01可影响以下五条。不能只用gate结果关闭五条。

| 规则 | 实际消费者 | 现有合成测试入口（`tests/unit/test_luxian_0609_native_transfusion_execution.py`） |
| --- | --- | --- |
| 043 | `evaluate_pretransfusion_nine_items` | `test_043_incomplete_test_contract_is_data_gap_without_model`；`test_043_checks_nine_items_before_transfusion_and_returns_times`；`test_043_short_lab_codes_require_token_boundaries` |
| 044 | `_programmatic_044_status`，必要时受控理由抽取 | `test_044_clear_pretransfusion_assessment_truth_is_deterministic_without_model`；`test_typed_044_dedicated_fact_precedes_auxiliary_source_four_states`；`test_044_rejects_llm_reason_quote_outside_application_text` |
| 045 | `_programmatic_045_status` | `test_045_substantive_dedicated_course_record_is_compliant_without_model`；`test_045_explicit_missing_course_and_complete_empty_source_are_non_compliant`；`test_typed_045_uses_snapshot_material_not_conflicting_legacy_payload` |
| 046 | `_programmatic_046_status`，必要时受控成分抽取 | `test_046_each_complete_dedicated_record_is_compliant_without_model`；`test_046_incomplete_or_cross_record_fields_are_deterministic_defect`；`test_046_checks_every_transfusion_record_beyond_prompt_projection_limit` |
| 047 | `_programmatic_047_assessment` | `test_047_posttransfusion_evaluation_is_deterministic_without_model`；`test_047_multiple_transfusions_do_not_use_earlier_evaluation_for_later_end`；`test_047_missing_authoritative_end_stays_data_gap_without_daily_projection` |
| 048 | `_programmatic_048_status`，独立术中事件确认 | `test_048_without_credible_intraoperative_transfusion_is_not_applicable`；`test_048_compares_component_and_dose_across_three_documents`；`test_048_does_not_claim_three_document_mismatch_before_comparison_contract` |

另有 `tests/unit/test_luxian_0609_native_transfusion_freeze.py` 族冻结保护和 `tests/integration/test_luxian_0609_transfusion_family_convergence.py` 收敛入口。本次不自动运行；root按影响与单一窗口安排隔离runner。

## 合同及历史修复轮次

空模板与可信MR、取消文书在045/046中的职责、自定义129份材料的容量与最终引用上限，是未集成候选的三项冲突。原TC01四条非实施预期及TC03术中否定预期完整，不需要先改变这些合同才能重放。048的成分/单位配对已关闭成果需保护，不能以其替代本次动作否定缺陷。

本轮尚未修改生产代码，baseline复现不算失败修复轮次。历史候选轮次需root按同根因总账承接，不因新目录或新负责人清零。测试接线失败单独如实记账。

2026-10-09 root转达用户裁定：045负责确认整份缺失；046无有效记录时保留资料不足；custom129全链本批暂停，维持正式来源容量，单独验证真实selected refs128/129边界。此为新合同输入，需另版本化；不改变上表原预期和原反例。

历史轮次只读核对：`next-batch/transfusion-family/implementation-checkpoint.md` 保留baseline32失败（非修复轮次）、首次核心65项60过/5文案断言失败、root文案修正后97全过，以及同族356项265过/91失败。候选 `resume-three-production-residuals-readonly.md` 明确capacity2轮绿、046完整正文1轮绿、旧协议2轮闭合；三项剩余生产根因当时0轮。`readiness-resumption-final-report.json` 记录readiness生产1轮及helper尝试。不能把不同根因的失败简单相加为TC01轮次，也不能把TC01的新阶段设为0轮；本代理仅完成baseline复现，停止于生产修改之前，TC01累计失败修复轮次需root对照原会话及各manifest逐笔确认。

## 当前结果

首跑产物：`.tmp/phase2-transfusion-20261009/current-results.json`。manifest SHA256：`279bcf2f37f3ef54a46955999b8d06833e9de5c2b6d72d8c39d810cd74116f5a`。源码前后hash相同，34项传递依赖闭包保留于结果。没有接线错误、生产修改、应用导入、模型或数据库访问。

| 检查 | 当前实际 | 原预期匹配 | 分流 |
| --- | --- | --- | --- |
| TF_PLAN | gate=`present` | 否 | TC01仍存在 |
| TF_REFUSED | gate=`present` | 否 | TC01仍存在 |
| TF_POSTPONED | gate=`present` | 否 | TC01仍存在 |
| TF_CANCELLED | gate=`data_gap` | 是 | 正常保护通过 |
| TF_ACTUAL_NO_REACTION | gate=`present` | 是 | 正常保护通过 |
| TF_PLAN_COMPLETE_FIELDS | gate=`present`；046纯函数=`non_compliant/transfusion_purpose_or_indication_missing` | 否 | TC01仍存在，046消费者原症状亦重现 |
| 048_NEGATED_INTRAOPERATIVE | `non_compliant/transfusion_records_inconsistent`；术中实施确认true；2U/4U/2U备血进入comparison_matrix | 否 | TC03仍存在 |
| 048_MATCHED | `compliant/transfusion_records_consistent` | 是 | 配对/单位正常保护通过 |
| 048_TIME_CONFLICT | `data_gap/association_failed` | 是 | 关联冲突保护通过 |

分流结论：两项根因在当前纯函数层“仍存在”；043–047均受TC01共享gate影响，048纯函数误报已重现。本批缺陷关闭数0/6，没有把4/9保护通过计为规则关闭。043–045及047尚未逐条重放正式终态，应按上表消费者入口做后续针对性验证；不将gate失败重复声称为五条全链验证。

## 正式路径补充：三次支撑尝试后停止

冻结 `.tmp/phase2-transfusion-20261009/formal-frozen.json` 与 `test_formal_original_cases.py`：五个原非实施输入（含cancel正常保护）逐条043–047共25例，原actual输入仅045正常1例。计划路径为同snapshot→native typed→binding/reducer→Finalizer，人工scope状态独立冻结；旧bool=true仅刺激原流程，不代表临床真值。最终facts和真实selected refs要求逐case落盘。

| 接线尝试 | 结果 | 证据与处理 |
| --- | --- | --- |
| 1：pytest runner | 启动/导入停滞，未产生业务case/XML；root授权有界中止 | `formal-integration-1791529213065558400/pytest.log`、`interrupted-support.json`；精确PID停止，session退出1 |
| 2：直接asyncio runner | 导入完成，WindowsSelector创建socketpair卡在stdlib accept；尚未进入第1例 | `formal-direct-1791529483484476200/timeout-trace.log`、`stages.log`、`timeout.json`；30秒trace及90秒支撑截止均保留，session退出1，不修改业务预期 |
| 3：无loop coroutine直驱 | 26/26在snapshot reader前置报`SnapshotSourceRows.create() missing ... truncated`；未形成native业务结果 | `formal-direct-1791529589918217700/run-manifest.json`，原冻结reader遗漏必填参数是本代理接线错误；应用py/data-json前后hash相同，外树app模块0 |

达到root批准的三次支撑上限后停止，不再修改或重跑这批正式补充。三次均不计生产修复轮次，但必须保留支撑失败账；不得把第三次程序退出0或26个例外记成验证通过。本批正式native补充为“未复现待查（支撑接线缺口）”，已有纯函数症状证据仍有效。

## 只读修复准备与最小交接

- TC01候选准确16份相关生产/测试/合同文件的现行hash、集成版本hash、新增/删除行数见 `.tmp/phase2-transfusion-20261009/candidate-files-readonly.json`。这是只读字节对照，不是候选通过证明。候选含完整正文scope-v1、逐文书状态/连续引用、共享抽取/失败缓存、MR权威保留、正式来源容量、readiness修复；现行集成未含这些候选改动。
- 若root确认历史同根因轮次允许，TC01优先在候选按已批准新合同独立验收，保留原旧失败；共享owner应由root统一负责native、rules/contracts、renderer、finalizer、mapping，抽取模块可单独交接。保护入口已列上文。结构/人工scope通过仍缺真实语义验证。
- TC03不能直接复用住院bloodtrans_record的performed文书事实充当术中事件事实。现有scope没有三文书同一术中事件、动作及剂量归属约束；住院其它输血不能证明术中实施。最多第二根因方案为先冻结版本化术中动作/事件/连续引用事实，再让原成分与单位比较器消费，保留原配对保护，不扩正则词表凑原样本。尚无生产写授权。
- 新合同独立设计 `new-contract-frozen.json` 已提交独审；MR关联/全批准来源完整性及refs精确union128/129要求须在下批落实后执行。原custom129全链暂停。这份准备稿未运行，不属于本批通过证据。
- 本批没有生产修改、集成、commit、数据库或外部模型调用。后续修复前root须核清TC01历史同根因轮次，不能从新阶段0轮开始。
