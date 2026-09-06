# LX0609 阶段 0：检查检验族本地资料形状覆盖账本

日期：2026-09-06  
基线提交：`7b5beeb96f397005e44d106933b3d3d18c241dc3`  
规则：`LX0609-010/011/012/014/015`  
状态：**本地通过·待最终客户验收**

本记录是阶段 0 的独立账本，补充而不改写
[检查检验规则族收口验收记录](./2026-09-06-lx0609-exam-lab-family-convergence.md)。
本次未连接客户环境、未读取真实病历正文、未写业务数据库、未改生产代码或前端。

## 问题证据、调用链与最小变更

计划要求对五条检查检验规则补齐本地正式 API/worker 的可达资料形状覆盖。CodeGraph
定位的主链为：

`prepare_luxian_0609_execution()` → `Luxian0609ExecutionEngine` → 注册的
`exam_lab` → `execute_luxian_0609_native_exam_lab_rules()` → Binding/Reducer →
`aggregate_luxian_0609_orchestrated_results()` → 工作台 worker 保存 Canonical Envelope。

审计发现原
`test_exam_lab_formal_worker_is_consistent_across_three_business_entries` 只以
`LX0609-012` 创建三种业务任务；虽然同文件的正式统一链冻结测试同时执行了全部五条，
但它没有覆盖每条规则经 worker 保存的三入口投影。

本阶段只修改
`backend/tests/integration/test_luxian_0609_exam_lab_family_convergence.py`：

- 三入口实际 ASGI 创建用例和直接 worker 用例均参数化为五个实际
  `EXAM_LAB_RULE_IDS`；
- job filter、draft、受控语义响应与读取的 Canonical rule id 均为测试参数，避免任一
  规则被 `012` 隐式复用；
- 对 010–015 使用受控的 JSON 事实响应；它只替代语义模型响应，不替代 prepare、统一引擎、
  `exam_lab` 执行器、Binding、聚合器、worker 或 SQLite Canonical 保存；
- 正式统一链冻结测试增加 `context.unified_engine_used is True`。
- 复用会诊族 ASGI 测试的隔离 router、样本池 SQLite 与 Canonical 回读夹具；010、011、
  012、014、015 各自通过工作台单病历、工作台病历池和客户样本池 POST 创建任务，再由
  真实 detached worker 完成并回读 Canonical Envelope。

没有修改 API 路由或生产公开接口。五条规则均经实际路由创建和真实 worker 派发；测试
参数化复用同一个明确的路由合同，不复制五份 HTTP 测试实现。

## 覆盖资料与可达形状

| 资料类别                           | 资料/形状                                                                                | 覆盖入口与结论                                                                                                                                      | 不可替代的内容                                     |
| ---------------------------------- | ---------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------- |
| 固定脱敏 fixture                   | 当前住院内 CT 报告、培养/药敏报告、报告后的病程记录；五条均适用且满足                    | 010/011/012/014/015 各自经单病历单规则、两病历病历池批量、带 `sample_pool_id` 的样本验证叶子任务；均 `completed`、`compliant/requirement_satisfied` | 不是客户真实病例，也不证明缺报告、歧义或多事件形状 |
| ASGI 路由 + 固定脱敏 fixture       | 五条规则分别使用上述资料；生产 `qc_sichuan`、`qc_sample_pools` router，隔离认证与 SQLite | 每条规则的工作台单病历 POST、工作台两病历 POST、客户样本 POST 均 200，真实 detached worker 保存并通过 latest-result API 回读                        | 固定脱敏资料不替代客户真实语义形状                 |
| 固定脱敏 fixture                   | 同一完整资料在直接正式统一链执行                                                         | 五条一次受控语义调用，`unified_engine_used=true`，每条 `compliant/requirement_satisfied`                                                            | 不替代 worker/API 三入口保存合同                   |
| 受控 stub                          | `_DeterministicExamLabFactClient` 为每个已选规则返回 schema v3 的单条 JSON 事实          | 仅稳定语义边界；每次调用固定 `100/10/110` Token 与 `0.2s` API 时间                                                                                  | 不是实际模型性能、模型准确率或客户验收             |
| 真实本地病例（既有记录，只读引用） | C01：无目标触发；R02：有检查医嘱/主记录但无正式报告                                      | 主验收记录已记载两病例经三入口的 M02/M05 结果；本次未重新创建任务                                                                                   | 无真实医院报告明细，不能替代适用病例               |

固定资料的三入口均断言：`metadata.executor_key=exam_lab`、无 `llm_fallback`、
无 `pack_fallback`、无 `bundle_fallback`、metadata 不含 `legacy`，三入口 Canonical
投影（状态、原因码、客户事实、子结论、客户证据）相等。样本验证叶子的 Canonical
Envelope 可读取，且其中证据仅保留脱敏 `source_ref`，没有原始 `source_document_id`。

ASGI 合同额外断言每条规则的三条路由生成同一 `rule_ids`、`selected_rule_ids` 和
`scoped_customer_rule_ids`；`record_rule_map` 使用正式 JSON 三坐标键。单病历与客户样本
均只映射 A，病历池映射 A/B，且每个键都仅映射当前参数规则。三任务均记录
`native_executor_phase/exam_lab` 完成事件；对统一引擎的生产 `execute()` 仅作调用记录后
仍执行原实现，证明四次记录级执行均以 `exam_lab` 批次进入统一引擎。各入口均为
`compliant/requirement_satisfied`，Canonical 的状态、原因码、客户事实、子结论与证据
坐标集合相等；证据数组顺序不作为优先级或验收条件。

## Canonical 事实和证据坐标集合

完整固定资料的冻结测试按集合而非数组顺序比对 `customer_evidence`。坐标四元组为
`(source_type, source_document_id, field_path, record_time)`；位置不表达证据优先级。

| 规则     | 状态/原因码                       | 证据坐标集合                                                                                              |
| -------- | --------------------------------- | --------------------------------------------------------------------------------------------------------- |
| 010      | `compliant/requirement_satisfied` | `exam_master / EXAM-REPORT-EXAM-VISIT-A / exam_conclusion / 2026-07-02 08:00:00`                          |
| 011、012 | `compliant/requirement_satisfied` | 上述 CT 报告，加 `daily_course_record / COURSE-AFTER-EXAM-VISIT-A / record_content / 2026-07-02 13:00:00` |
| 014、015 | `compliant/requirement_satisfied` | `labtest_master / CULTURE-REPORT-EXAM-VISIT-A / result / 2026-07-02 12:00:00`，加上述病程记录             |

010 的合规事实仍只在执行上下文中，不重复保存为聚合结果的
`customer_display_facts`；这是已冻结合同，并非丢失事实。011/012 的 subject 是 `ct_mri`，
014/015 的 subject 是 `culture_susceptibility`；012/015 的 `positive_state=positive`。

## 本地形状矩阵与证据边界

| 形状                                                                | 本地证据                                                  | 五条规则覆盖                                                           | 三入口正式 worker              | 客户最终验收       |
| ------------------------------------------------------------------- | --------------------------------------------------------- | ---------------------------------------------------------------------- | ------------------------------ | ------------------ |
| M02：无目标触发                                                     | 既有真实本地 C01 只读记录；另有 native 单测的明确缺失事实 | 五条均 `not_applicable/trigger_absent_complete`                        | 既有真实任务记录，未在本次重跑 | 待客户复验         |
| M03：适用且满足                                                     | 本次固定脱敏完整报告 fixture                              | 五条均 `compliant/requirement_satisfied`                               | **本次补齐，三入口均覆盖**     | 待真实适用病例复验 |
| M04：适用且确定违反                                                 | native 单测：012 阳性未分析、015 阳性培养待处理           | 012、015；010 的违反由既有 native 单测覆盖                             | 未做三入口 fixture             | 待客户复验         |
| M05：有医嘱/主记录、正式报告缺失                                    | 既有真实本地 R02 只读记录                                 | 010 `data_gap`；011/012 报告时间缺失；014/015 无培养触发（详见主记录） | 既有真实任务记录，未在本次重跑 | 待客户复验         |
| M06–M09：报告关联不唯一、多项目、多次同类、培养阳性与普通检验并存等 | 单元执行器有局部绑定/事件单测                             | 未形成完整三入口固定矩阵                                               | 未覆盖                         | 待客户验收矩阵     |

历史主验收记录对 R02 的 010 原因码同时出现过 `association_failed` 和
`required_field_missing` 两种描述。本阶段没有重跑该真实病例，也不以两者任一项作为冻结
预期；最终客户矩阵必须以同一候选重新创建任务并记录当次状态、原因码和证据集合。

## 验证记录

在 `backend/` 执行：

```powershell
py -3.10 -m pytest -q tests/integration/test_luxian_0609_exam_lab_family_convergence.py
# 11 passed, 15 warnings

py -3.10 -m pytest -q tests/integration/test_luxian_0609_exam_lab_family_convergence.py -k asgi_entries
# 5 passed, 6 deselected, 15 warnings

py -3.10 -m pytest -q tests/unit/test_luxian_0609_native_exam_lab_execution.py -k 'explicit_absent_current_visit_facts_are_not_applicable_without_model or no_explicit_exam_or_culture_fact_returns_data_gap_without_model or 010_missing_authoritative_exam_time_does_not_call_llm or 010_ambiguous_order_exam_linkage_stays_data_gap or lx0609_012_gold_explicit_positive_without_analysis_is_defect or lx0609_015_structured_positive_culture_with_pending_observation_is_defect'
# 6 passed, 150 deselected, 15 warnings in 0.39s
```

warnings 均为既有 FastAPI/SQLAlchemy/Pydantic 弃用提示；两条命令均无测试失败。

## 回退、剩余风险与最终客户矩阵

本阶段没有生产提交；如需撤回，仅回退本阶段的测试与本账本文档并重跑上述两条命令。

最终客户环境仍须对每条规则选择真实适用病例，并在同一评价时点按单病历、病历池、
样本验证三入口重新创建任务。每个单元须比对 unified、`executor_key`、状态、原因码、
客户事实、`criterion_results`、客户文案与证据坐标集合，并实际点击证据定位。至少补齐：

- 正常满足、确定违反；
- 有医嘱无报告、缺权威时间、关联不唯一；
- 一次检查多项目、同类检查多次；
- 培养阳性与普通检验同时存在；
- no fallback、Canonical Envelope 保存和三入口集合等价。

在以上矩阵完成前，本规则族只能报告“本地通过·待最终客户验收”。
