# LX0609 surgery_document 族提交 A：当前行为重新冻结

## 结论

- 冻结基线：`4125e0329`（包含 029 医嘱触发展示事实修复、035/039 原因码修复）。
- 规则范围：`LX0609-029、034、035、036、037、038、039`。
- 本提交仅更新测试和验收记录：真实链为 `native executor → Binding/Reducer → aggregate_luxian_0609_results → customer renderer`，不修改生产代码。
- `customer_evidence` 按 `(source_type, source_document_id)` **集合**比较，数组顺序不具有优先级语义。

## 冻结入口与当前所有者

| 层级           | 当前所有者                                                                  | 冻结内容                                       |
| -------------- | --------------------------------------------------------------------------- | ---------------------------------------------- |
| 原生判定       | `native_surgery_document_execution.py`                                      | 7 条规则的结构化判定、受控 facts、零 LLM/Token |
| 状态归约       | `decision_binding.py` / `decision_reducer.py`                               | `final_state`、`reason_code`、`fact_refs`      |
| 客户展示 facts | `luxian_0609_result_aggregator.py::safe_luxian_0609_customer_display_facts` | 当前 canonical `customer_display_facts`        |
| 客户证据       | 公共 selected-document 投影及聚合器旧兼容分支                               | 文书坐标集合                                   |
| 客户 finding   | `customer_renderer.py`                                                      | 已校验 facts 所对应的客户短句                  |

## 冻结矩阵

所有用例均使用真实 evidence read session、native executor、Binding/Reducer 与公开 canonical 聚合函数；不直接构造最终结果。每项均断言 `status`、`reason_code`、完整 `customer_display_facts`、精确 `fact_refs`、客户证据坐标集合及 `findings`。

| 规则/场景                           | 状态 / 原因码                               | 关键事实与客户 finding                                                                                                                                    | 精确事实 / 证据坐标                                                                                                                                |
| ----------------------------------- | ------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------- |
| 029：已实施手术且术前小结存在       | `compliant / requirement_satisfied`         | `surgery_trigger_kind=performed_surgery`；“已确认本次实施手术具备术前小结。”                                                                              | `presurg_summary`、空 `inpat_nondrug_order`、`mr_surgery`、`surgery_record` 四个 observation refs；证据为 `mr-surgery-1`、`surgery-1`、`summary-1` |
| 029：仅有有效手术医嘱且术前小结存在 | `compliant / requirement_satisfied`         | `surgery_trigger_kind=surgery_order`，只有 `surgery_order_confirmed=true`，**没有** `performed_surgery_confirmed`；“已发现手术医嘱，术前小结已完整记录。” | 聚合手术医嘱 Fact + 手术医嘱材料 `operation-order-1` + 小结材料 `summary-order-1`；证据为同两份真实文书                                            |
| 034：已麻醉但同意书缺失             | `non_compliant / required_document_missing` | `anesthesia_consent_missing`；“已实施麻醉，但未找到对应的麻醉知情同意书”                                                                                  | `anesthesia_record`、空 `consent_form`、`mr_surgery` observation refs；按当前旧投影冻结证据坐标                                                    |
| 035：同意书缺患者签名及时间         | `non_compliant / requirement_violated`      | `anesthesia_consent_incomplete` + 两项缺失字段；“发现质控问题”                                                                                            | `consent_form`、`anesthesia_record`、`mr_surgery` observation refs；三类真实文书坐标                                                               |
| 036：术前访视存在、术后访视缺失     | `non_compliant / required_document_missing` | `anesthesia_visit_missing/postane_surveil_record`；“已实施麻醉，但缺少麻醉术前或术后访视记录”                                                             | 空 `postane_surveil_record` 加上实际麻醉、手术、术前访视 observation refs                                                                          |
| 037：术前/术后访视完整              | `compliant / requirement_satisfied`         | `anesthesia_visits_complete` 与固定字段表；分项访视客户 finding                                                                                           | 麻醉、空同意书、MR 手术、术前及术后访视五个 observation refs；四份客户文书坐标                                                                     |
| 038：麻醉记录存在                   | `compliant / requirement_satisfied`         | `anesthesia_record_present`；“已确认本次麻醉具备麻醉记录单。”                                                                                             | 麻醉、空同意书、MR 手术 observation refs；客户证据仅 `anesthesia-1`                                                                                |
| 039：两台手术且术前讨论缺失         | `non_compliant / required_document_missing` | `preop_discussion_missing`；“发现质控问题”                                                                                                                | 空 `presurg_discussion`、空 `mr_surgery`、空 **`rescue_record`**、两条 `surgery_record` observation refs；客户证据空集合                           |
| 029：无手术触发                     | `not_applicable / performed_event_absent`   | 按当前输出冻结                                                                                                                                            | 当前输出冻结                                                                                                                                       |
| 029：多手术与单术前小结无法关联     | `data_gap / association_failed`             | 按当前输出冻结                                                                                                                                            | 当前输出冻结                                                                                                                                       |
| 034：麻醉记录查询异常               | `technical_error / source_query_error`      | 无伪造业务结论                                                                                                                                            | 当前输出冻结                                                                                                                                       |

`fact_refs` 是内容寻址引用，测试不将原始摘要写入基线。为保证精确性，它把每一条引用还原后逐项比较：Fact 比较 `fact_type/source/assertion/event_status`，source observation 比较 `source/query_state/record_count`，材料引用比较 `source/document_id`；Binding 前后必须完全一致。

所有场景均断言 `llm_call_count`、`prompt_tokens`、`completion_tokens` 与 `total_tokens` 均为 0，且传入的 LLM client 一旦被调用即失败。

## 当前迁移债（只登记，不在冻结提交处理）

1. 聚合器仍保有本族安全 facts 校验、`029/038` 专属投影和旧兼容证据处理；结构迁移必须迁出这些完整职责，不能把判断复制给 Renderer。
2. 已实施手术触发的 029 仍保留当前 observation 级 refs；仅医嘱触发才携带实际医嘱与小结材料 refs。后续若收紧为逐文书选择，属于证据投影职责调整，需先独立冻结其目标行为。
3. 034/036 的旧客户证据 source type 映射仍可能把 `mr_surgery` 触发文书标成 `anesthesia_record`。本次如实冻结，不能把它当作正确业务口径。
4. 035/039 已使用当前正确的 `requirement_violated` / `required_document_missing` 边界；后续结构提交不得顺手改变这些状态语义。

## 最小文件白名单

- `backend/tests/unit/test_luxian_0609_surgery_document_freeze.py`
- `docs/acceptance/2026-09-07-lx0609-surgery-document-freeze.md`

## 验收命令

```text
cd backend
py -3.10 -m pytest -q tests/unit/test_luxian_0609_native_surgery_document_execution.py tests/unit/test_luxian_0609_surgery_document_freeze.py
```

本次重新冻结的聚焦结果：`118 passed`（其中 freeze 文件 10 项）。
