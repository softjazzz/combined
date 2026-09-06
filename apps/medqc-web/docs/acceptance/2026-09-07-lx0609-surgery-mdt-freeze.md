# LX0609-040 surgery_mdt：行为冻结与职责收口

## 目的与边界

先冻结 `LX0609-040` 正式 Canonical 主链的可见行为，再将 040 的专属客户事实
校验和旧直调证据适配迁入 Finalizer。没有修改规则口径、Prompt、数据库、API
或前端。

本次覆盖的是零 LLM 的确定性形状；普通术前文书的语义灰区仍由既有
`test_luxian_0609_mdt_freeze.py` 覆盖，不把模型自然波动混入本次结构基线。

## 当前调用链审计

```text
规则合同 LX0609-040 (executor_key=surgery_mdt)
  -> executor_registry.surgery_mdt
  -> native_mdt_execution.execute_luxian_0609_native_mdt_rule
  -> RuleDecision + customer_display_facts
  -> decision_binding.bind_and_reduce_luxian_0609_rule_decisions
  -> aggregate_luxian_0609_results
  -> customer_evidence / customer_display_facts
```

迁移前，040 在聚合器保留两处规则专属职责：

- `luxian_0609_result_aggregator.py:2138`：040 客户展示事实的字段合法性与
  急诊豁免解释；
- `luxian_0609_result_aggregator.py:2995`：040 仅允许 `mr_surgery` 的精确触发
  文书坐标。

迁移后，这两项职责由 `surgery_mdt_result_mapping.py` 唯一拥有：执行器输出
事实和 `fact_refs`，Binding 校验同一快照引用，公共 selected-document projector
生成客户证据；聚合器只装配。归零守卫确认聚合器中 `LX0609-040` 引用为 0。

## 冻结矩阵

| 形状                       | Canonical 状态 / 原因码                    | `fact_refs` 当前来源集合                                  | 客户证据坐标集合                             | 客户事实重点                                           | LLM / Token |
| -------------------------- | ------------------------------------------ | --------------------------------------------------------- | -------------------------------------------- | ------------------------------------------------------ | ----------- |
| 四级手术 + 明确 MDT        | `compliant / requirement_satisfied`        | `mr_surgery`、`presurg_discussion`、`consultation_record` | 手术 `SURG-C`；讨论 `DISC-C`                 | 已实施四级手术、`completed`                            | 0 / 0       |
| 四级手术 + 无讨论文书      | `non_compliant / requirement_violated`     | 同上                                                      | 手术 `SURG-NC`                               | 已实施四级手术、`missing`                              | 0 / 0       |
| 三级手术                   | `not_applicable / trigger_absent_complete` | 同上                                                      | 空（当前 NA 投影不输出 `customer_evidence`） | 手术等级三级                                           | 0 / 0       |
| 讨论来源未接入             | `data_gap / source_unavailable`            | 同上                                                      | 手术 `SURG-DG`                               | 已实施四级手术、`unknown`                              | 0 / 0       |
| 手术来源查询异常           | `technical_error / source_query_error`     | 同上                                                      | 空                                           | 无客户事实                                             | 0 / 0       |
| 紧急抢救生命的急诊四级手术 | `not_applicable / trigger_absent_complete` | 同上                                                      | 空（当前 NA 投影不输出 `customer_evidence`） | `mdt_exception=emergency_lifesaving_surgery`、`exempt` | 0 / 0       |

证据按 `(source_type, source_document_id, field_path, record_time)` 集合比较，
不依赖数组排序。

## 已确认的急诊豁免

`presurg_summary` 中“急诊抢救、为挽救生命立即手术”会使已实施四级手术进入
`not_applicable`，并保留以下客户展示事实：

```text
emergency_surgery_confirmed=true
mdt_exception=emergency_lifesaving_surgery
mdt_discussion_state=exempt
```

此前 `test_luxian_0609_mdt_freeze.py` 仍期待旧的投影异常。本提交已将它改为
断言已修复的正常 Canonical 投影；这只更新测试基线，不改变生产口径。

## 精确证据与旧直调兼容边界

`a33cf558a` 已先行完成独立的精确引用修复并重冻：执行器只选择实际参与本次
判断的手术、讨论、会诊或急诊豁免文书。此次结构提交不再改动这一选择。

仍存在的 aggregate 直调兼容仅接受原始 facts 明确列出的 `mr_surgery` 文书坐标；
不会由展示 facts 猜测讨论或会诊文书。正式主链不依赖该兼容路径。

## 验证

```powershell
Set-Location D:\LLM\LX888\apps\medqc-web\backend
py -3.10 -m pytest -q `
  tests/unit/test_luxian_0609_surgery_mdt_freeze.py `
  tests/unit/test_luxian_0609_mdt_freeze.py `
  tests/unit/test_luxian_0609_native_mdt_execution.py `
  tests/unit/test_luxian_0609_surgery_mdt_result_mapping.py `
  tests/unit/test_luxian_0609_canonical_result_finalizer.py `
  tests/unit/test_luxian_0609_result_aggregator.py
```

结果：`486 passed`。其中 040 冻结覆盖 Native → Binding → Finalizer → Aggregator
的状态、原因码、`fact_refs` 来源、客户证据坐标集合、展示事实和零 LLM 用量。
