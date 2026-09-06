# LX0609 surgery_document 族提交 A：当前行为冻结

## 结论

- 冻结基线：`f9cfd8bbff696fc4a64fe365511d2b2bab40e8de`（已包含 038 单规则麻醉资料源合同修复）。
- 规则范围：`LX0609-029、034、035、036、037、038、039`。
- 本提交只记录当前 `native executor -> Binding/Reducer -> aggregate_luxian_0609_results` 的真实可达行为；没有修改生产代码，也没有预写迁移后的 facts 或聚合器归零断言。
- **迁移阻断**：冻结暴露出 reason 口径和证据投影缺陷。提交 A 不是对这些异常口径的业务背书；应先以独立最小任务修正业务口径，再重新冻结，之后才允许提交 B 搬迁所有权。

## 冻结入口与业务所有者

| 层级           | 当前所有者                                                                  | 本次冻结内容                                                |
| -------------- | --------------------------------------------------------------------------- | ----------------------------------------------------------- |
| 原生判定       | `native_surgery_document_execution.py`                                      | 7 条规则的结构化判定、原始受控 facts、零 LLM/Token          |
| 状态归约       | `decision_binding.py` / `decision_reducer.py`                               | `final_state`、`reason_code`、`fact_refs`                   |
| 客户展示 facts | `luxian_0609_result_aggregator.py::safe_luxian_0609_customer_display_facts` | 当前 canonical `customer_display_facts`；仍存在本族专用分支 |
| 客户证据       | `luxian_0609_result_aggregator.py`                                          | 当前 `customer_evidence` 坐标集合及旧 source_type 映射      |

聚合器所有权基线测试只证明当前仍由聚合器接受并生产本族旧展示 facts。迁移前没有增加“聚合器本族分支必须为零”的预期失败守卫。

## 冻结矩阵

以下均通过真实 evidence read session、native executor、Binding/Reducer 与公开 canonical 聚合函数，不直接构造最终结果。

| 规则/场景                         | canonical 状态    | reason_code                 | canonical facts 摘要                                | 客户证据坐标集合                                                                                                        |
| --------------------------------- | ----------------- | --------------------------- | --------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------- |
| 029：已实施手术且术前小结存在     | `compliant`       | `requirement_satisfied`     | `surgery_document_present / presurg_summary`        | `mr_surgery:mr-surgery-1`、`surgery_record:surgery-1`、`presurg_summary:summary-1`                                      |
| 034：已麻醉但同意书缺失           | `non_compliant`   | `required_document_missing` | `anesthesia_consent_missing`                        | `anesthesia_record:anesthesia-1`、`anesthesia_record:mr-surgery-1`（当前异常映射）                                      |
| 035：同意书缺患者签名及时间       | `non_compliant`   | `required_document_missing` | `anesthesia_consent_incomplete` + 两项缺失字段      | `anesthesia_record`、`consent_form`、`mr_surgery` 三类真实文书坐标                                                      |
| 036：术前访视存在、术后访视缺失   | `non_compliant`   | `required_document_missing` | `anesthesia_visit_missing / postane_surveil_record` | `anesthesia_record:anesthesia-1`、`anesthesia_record:mr-surgery-1`（当前异常映射）、`preane_surveil_record:pre-visit-1` |
| 037：术前/术后访视完整            | `compliant`       | `requirement_satisfied`     | `anesthesia_visits_complete` + 固定检查字段         | 麻醉记录、MR 手术、术前及术后访视四类坐标                                                                               |
| 038：麻醉记录存在                 | `compliant`       | `requirement_satisfied`     | `anesthesia_record_present`                         | `anesthesia_record:anesthesia-1`                                                                                        |
| 039：多台已实施手术且术前讨论缺失 | `non_compliant`   | `required_document_missing` | `preop_discussion_missing`                          | 空集合（多手术无法唯一投影）                                                                                            |
| 029：无已实施手术                 | `not_applicable`  | `performed_event_absent`    | 按当前输出冻结                                      | 按当前输出冻结                                                                                                          |
| 029：多手术与单术前小结无法关联   | `data_gap`        | `association_failed`        | 按当前输出冻结                                      | 按当前输出冻结                                                                                                          |
| 034：麻醉记录查询异常             | `technical_error` | `source_query_error`        | 无伪造业务结论                                      | 按当前输出冻结                                                                                                          |

所有上述场景同时断言：`llm_call_count == 0`，`prompt_tokens == 0`，`completion_tokens == 0`，`total_tokens == 0`，且传入的 LLM client 一旦被调用即失败。

`fact_refs` 不断言不稳定摘要常量，而是冻结为当前 snapshot 中对应来源 observation ref 的精确有序集合，并验证 Binding 前后完全相等。各规则来源集合按当前真实行为固定；038 在本基线上绑定 `anesthesia_record + mr_surgery + consent_form`。

## 已知业务缺陷与迁移 blocker（只登记、不修复）

1. **034/036 客户证据 source_type 错标。** 触发证据来自 `mr_surgery`，canonical 聚合后坐标被标成 `anesthesia_record`。冻结测试记录当前输出，但不认可该映射为正确业务口径。
2. **“文书不完整”被归约为“文书缺失”。** 035 的原生 outcome 是 `anesthesia_consent_incomplete`，037 的不完整分支是 `anesthesia_visit_incomplete`，但当前 Decision 转换统一得到 `required_document_missing`。状态仍为 `non_compliant`，reason 语义丢失。
3. **039“术者未参加讨论”同样会丢失细分原因。** 原生 outcome 的 `surgeon_not_in_preop_discussion` 在 Decision 转换后仍会统一成 `required_document_missing`。应由业务口径任务决定使用 `requirement_violated` 还是新增受控 reason，不能在结构迁移中顺手修改。
4. 旧兼容 LLM 分支仍把模型失败/非法输出降为 `data_gap`；本族正式合同为 `program_only`、零调用。迁移不得把这条兼容语义带回 typed 主链。

因此提交 B 的前置条件不是“本冻结测试绿色”本身，而是：上述 1-3 项经独立业务口径任务裁决并修复、同一真实链重新冻结为绿色。第 4 项仅保留在旧兼容入口，不得成为新所有者依赖。

## 最小文件白名单

- `backend/tests/unit/test_luxian_0609_native_surgery_document_execution.py`（本提交未改）
- `backend/tests/unit/test_luxian_0609_surgery_document_freeze.py`
- `docs/acceptance/2026-09-07-lx0609-surgery-document-freeze.md`

## 提交 A 验收标准

1. 7 条规则均经过真实 native -> Binding -> aggregate 链，并冻结 `final_state/reason_code/customer_display_facts/fact_refs/customer_evidence`。
2. 家族可达的 `compliant/non_compliant/not_applicable/data_gap/technical_error` 均至少有一个真实场景。
3. 所有场景零 LLM 调用、零 prompt/completion/total token。
4. 当前聚合器所有权有正向基线；不存在迁移后的预期失败归零守卫。
5. 已知异常只登记为 blocker，不改生产代码、不篡改当前预期、不宣称异常口径正确。
6. 聚焦命令绿色：

   ```text
   cd backend
   py -3.10 -m pytest -q tests/unit/test_luxian_0609_native_surgery_document_execution.py tests/unit/test_luxian_0609_surgery_document_freeze.py
   ```
