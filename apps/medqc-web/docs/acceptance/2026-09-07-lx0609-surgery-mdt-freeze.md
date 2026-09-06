# LX0609-040 surgery_mdt：提交 A 行为冻结

## 目的与边界

本提交只冻结 `LX0609-040` 当前正式 Canonical 主链的可见行为，为后续把
040 的专属客户事实校验和证据选择迁出聚合器准备基线。没有修改任何生产代码、
规则口径、Prompt、数据库、API 或前端。

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

040 目前仍在聚合器保留两处规则专属职责：

- `luxian_0609_result_aggregator.py:2138`：040 客户展示事实的字段合法性与
  急诊豁免解释；
- `luxian_0609_result_aggregator.py:2995`：040 仅允许 `mr_surgery` 的精确触发
  文书坐标。

因此它尚未完成职责收口；本冻结提交不提前加入“聚合器引用归零”守卫。

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

## 迁移前已知边界

当前 `_typed_decision_from_outcome()` 会把三个允许来源的**来源级**快照引用都
写入 `fact_refs`，即使 `presurg_discussion` 或 `consultation_record` 本次为空或
不可用。冻结测试故意固定这个现状，避免结构迁移时悄然改变证据链。

后续迁移若要实现“执行器只选择实际参与判定的文书”，必须作为明确的证据选择
口径调整单独审批、重新冻结，而不能混入本次等价迁移。

## 验证

```powershell
Set-Location D:\LLM\LX888\apps\medqc-web\backend
py -3.10 -m pytest -q `
  tests/unit/test_luxian_0609_surgery_mdt_freeze.py `
  tests/unit/test_luxian_0609_mdt_freeze.py `
  tests/unit/test_luxian_0609_native_mdt_execution.py
```

结果：`46 passed`。
