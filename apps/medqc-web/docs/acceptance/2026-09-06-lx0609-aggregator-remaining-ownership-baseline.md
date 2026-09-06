# LX0609 聚合器剩余所有权与检查检验族迁移前审计

## 审计结论

**状态：READY FOR COMMIT A AFTER POLICY FIXES**

检查检验族适合作为下一批架构收口对象。审计发现的两类状态语义冲突已经通过两个独立业务口径提交关闭；现在可以基于修复后的批准行为建立提交 A，不能再以修复前状态作为等价迁移基线。

初始审计只读执行；本文件随后记录两个独立口径修复的关闭状态。

## 审计基线

- 基线提交：`7232e1d08a8cdde16af6238177a20101512ef289`
- 聚合器：`backend/app/services/luxian_0609_result_aggregator.py`
- 聚合器行数：5613
- 目标规则：`LX0609-010/011/012/014/015`
- 目标规则号出现次数：44

| 规则         | 出现次数 |
| ------------ | -------: |
| `LX0609-010` |       12 |
| `LX0609-011` |        9 |
| `LX0609-012` |        9 |
| `LX0609-014` |        7 |
| `LX0609-015` |        7 |

## 当前重复所有权

| 位置                                        | 目标规则引用       | 当前职责                             | 迁移后的唯一所有者                                             |
| ------------------------------------------- | ------------------ | ------------------------------------ | -------------------------------------------------------------- |
| 顶层检查检验证据来源配置                    | 011、012、014、015 | 规则专属来源白名单                   | 执行器选择 `fact_refs`，Binding 验证来源，公共证据投影生成坐标 |
| `safe_luxian_0609_customer_display_facts()` | 五条规则           | 事实结构校验、失败种类解释、字段过滤 | `exam_lab_result_mapping.py` 的规则族安全事实合同              |
| `_customer_evidence_from_display_facts()`   | 五条规则           | 来源选择、文书证据回退和来源类型转换 | `customer_evidence_enrichment.py` 公共投影                     |
| `_copy_native_customer_fields()`            | 010                | 严格合同例外、重复事实复制兼容       | Finalizer 统一校验并 fail closed                               |
| `aggregate_luxian_0609_results()`           | 010                | 聚合阶段再次处理严格事实合同         | Finalizer；聚合器仅装配                                        |

按函数统计：

| 函数                                      | 010 | 011 | 012 | 014 | 015 |
| ----------------------------------------- | --: | --: | --: | --: | --: |
| `safe_luxian_0609_customer_display_facts` |   6 |   5 |   5 |   3 |   3 |
| `_customer_evidence_from_display_facts`   |   3 |   3 |   3 |   3 |   3 |
| `_copy_native_customer_fields`            |   2 |   0 |   0 |   0 |   0 |
| `aggregate_luxian_0609_results`           |   1 |   0 |   0 |   0 |   0 |
| 顶层来源配置                              |   0 |   1 |   1 |   1 |   1 |

## 规则 × 可达状态预审

以下矩阵描述当前实现能够到达的公共语义，不要求每条规则人为制造全部状态：

| 规则 | `not_applicable`                         | `compliant`                  | `non_compliant`                      | `data_gap`               | `uncertain`                    | `technical_error`            |
| ---- | ---------------------------------------- | ---------------------------- | ------------------------------------ | ------------------------ | ------------------------------ | ---------------------------- |
| 010  | 可达：无实际检查触发                     | 可达：检查前已有原因说明     | 可达：缺少原因说明或已执行检查无报告 | 可达：关联/时间/投影缺失 | 可达：完整事实下原因语义不可靠 | 可达：来源查询或模型技术失败 |
| 011  | 可达：无目标检查事件或窗口未成熟         | 可达：24 小时内处理          | 可达：成熟窗口内未处理               | 可达：报告/时间/关联缺失 | 可达：完整事实下语义不可靠     | 可达                         |
| 012  | 可达：无目标事件、结果非阳性或窗口未成熟 | 可达：阳性结果 24 小时内分析 | 可达：成熟窗口内未分析               | 可达：报告/时间/关联缺失 | 可达：阳性或分析语义不可靠     | 可达                         |
| 014  | 可达：无危急检验事件或窗口未成熟         | 可达：24 小时内处理          | 可达：成熟窗口内未处理               | 可达：报告/时间/关联缺失 | 可达：完整事实下语义不可靠     | 可达                         |
| 015  | 可达：无培养阳性事件或窗口未成熟         | 可达：24 小时内分析          | 可达：成熟窗口内未分析               | 可达：报告/时间/关联缺失 | 可达：阳性或分析语义不可靠     | 可达                         |

`uncertain` 只在目标事件、权威时间、报告结果正文和病程投影完整，而受控语义仍无法可靠判断时可达。报告结果字段缺失、来源截断和事件关联失败仍为 `data_gap`，非法模型输出仍为 `technical_error`。

## 已关闭的状态语义冲突

### 冲突 1：评价窗口未成熟被归入 `data_gap`

`native_exam_lab_execution._single_text_fact_outcome()` 对 011、012、014、015 的 24 小时观察窗口处理为：

- 窗口成熟且未记录 → `non_compliant`；
- 窗口未成熟 → `data_gap / evaluation_window_not_mature`。

`exam_lab_result_mapping.build_exam_lab_rule_decision()` 又明确将 `evaluation_window_not_mature` 保留为 `data_gap`。

该冲突已在 `d0facbc57` 修复为 `not_applicable / evaluation_window_not_mature`。

现有测试已证明该分支真实可达，并非静态死代码：

- `test_post_rule_absence_needs_exact_mature_horizon_and_date_is_conservative`
- `test_lx012_data_gap_preserves_specific_evaluation_window_reason`

### 冲突 2：语义 unknown 当前可能落为 `data_gap`

当适用事件已存在但 `semantic_state` 不是 `present/absent` 时，当前主路径返回：

```text
data_gap / exam_lab_text_fact_unknown
```

该冲突已通过内部 `result_text_available` 事实完成分流：结果正文和来源完整时进入 `uncertain / semantic_output_unknown`；结果正文或来源不完整时保持 `data_gap`。

## 已符合批准边界的行为

- 完整来源中无触发事件 → `not_applicable / trigger_absent_complete`。
- 检查或报告业务键关联不唯一 → `data_gap / association_failed`。
- 数据源未接入 → `data_gap / source_unavailable`。
- 来源查询错误 → `technical_error / source_query_error`。
- 模型传输失败或非法输出 → `technical_error`，没有伪装成临床资料问题。
- 培养规则已有防止普通检验污染触发集的聚焦测试。

## 验证记录

运行命令：

```powershell
Set-Location backend
py -3.10 -m pytest -q `
  tests/unit/test_luxian_0609_native_exam_lab_execution.py::test_post_rule_absence_needs_exact_mature_horizon_and_date_is_conservative `
  tests/unit/test_luxian_0609_native_exam_lab_execution.py::test_evaluation_window_state_has_distinct_maturity_and_conflict_semantics `
  tests/unit/test_luxian_0609_native_exam_lab_execution.py::test_lx012_data_gap_preserves_specific_evaluation_window_reason `
  tests/unit/test_luxian_0609_native_exam_lab_execution.py::test_typed_all_empty_complete_sources_are_not_applicable_in_requested_order `
  tests/unit/test_luxian_0609_native_exam_lab_execution.py::test_typed_model_failure_and_invalid_output_are_technical_errors_without_echo
```

结果：12 项通过。通过结果证明当前实现稳定复现上述旧口径，并不代表该口径已经获批。

## 下一步

开始提交 A：只补充检查检验族的行为冻结测试与三入口基线，不修改生产逻辑，不创建预期失败的聚合器归零守卫。提交 A 审核通过后，才进入提交 B 的等价职责迁移。
