# LX0609 肿瘤病理族提交 A：现状行为冻结

## 范围与目的

本提交仅为 `LX0609-013/019/026/027` 建立迁移前的主链冻结证据；不修改生产逻辑、规则口径、Prompt、数据库、API 或前端。

冻结链路为：

```text
Evidence read session → tumor_pathology native executor → RuleDecision
→ Binding/Reducer → aggregate_luxian_0609_results → customer result
```

本族当前 `executor_key=tumor_pathology`，四条均在客户规则目录中；`LUXIAN_0609_CUSTOMER_EXCLUDED_RULE_IDS` 不包含这四条，当前没有暂停项。因此客户范围为：013、019、026、027 均 active。

## 现状冻结用例

新增测试：`backend/tests/unit/test_luxian_0609_tumor_pathology_freeze.py`。

主用例使用同一只读 session 的受控结构化材料：病理最终诊断、手术/病程中的病理记录、结构化化疗医嘱与对应病程、恶性诊断和出院记录。

| 规则 | 冻结状态 / reason                    | 冻结展示事实                                                   | 冻结客户证据坐标集合                                                                                                                        |
| ---- | ------------------------------------ | -------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------- |
| 013  | compliant / requirement_satisfied    | `pathology_result_documentation_check`                         | 病理、手术记录、日常病程来源（由当前全来源 fact_refs 投影）                                                                                 |
| 019  | compliant / requirement_satisfied    | `pathology_sampling_documentation_check`                       | 病理、手术记录、日常病程来源（由当前全来源 fact_refs 投影）                                                                                 |
| 026  | compliant / requirement_satisfied    | `chemotherapy_order_course_comparison`                         | `inpat_drug_order:chemo-order-1`、`daily_course_record:course-1`                                                                            |
| 027  | non_compliant / requirement_violated | `malignant_discharge_plan_check`，其中 `tumor_treatment=false` | `diagnosis:diagnosis-1`、`discharge_record_diagnosis:discharge-dx-1`、`pathology_exam_report:path-report-1`、`discharge_record:discharge-1` |

该确定性用例的 LLM 调用、输入/输出 Token 均为 0。它证明相同事实链无需语义调用即可稳定输出；不代表 013/019 的语义兜底分支不存在。

另冻结完整空病理来源与病理报告查询异常：

| 输入形状                         | 013/019 状态 / reason                    |
| -------------------------------- | ---------------------------------------- |
| 两类病理来源均完整为空           | not_applicable / trigger_absent_complete |
| `pathology_exam_report` 查询异常 | technical_error / source_query_error     |

另冻结 019 进入语义兜底后出现受控模型传输失败的现状：执行器计为 1 次调用、0 Token，但客户结果为 `data_gap / required_field_missing`。这是下面列出的待修业务失败语义，不应在本提交中被掩盖。

既有 `test_typed_019_optional_llm_matches_raw_state_calls_tokens_and_prompt` 记录 019 语义兜底在相同材料下的单次调用与 110 Token；本次不重写该既有业务测试。

## 迁移前所有权基线

`luxian_0609_result_aggregator.py` 仍有四条规则的专属客户事实校验分支：013、026、027、019（约 1725–1860 行），且保留 026 的专属客户证据白名单。这是后续完整迁移需归零的基线，提交 A 不预写 `xfail` 或归零守卫。

## 发现的阻塞项

以下问题不能混入结构迁移提交，应先作为独立最小缺陷闭环确认或修复，并在修复后重新冻结。

1. **013/019 的 LLM 技术失败语义不符合总线红线。** 当前语义兜底的模型调用异常或返回非法 JSON 被发射为 `data_gap`（`tumor_llm_failure` / `tumor_llm_invalid_output`），随后缩减为资料不足；按照已批准的状态边界，模型传输失败和非法输出必须是 `technical_error`，不能伪装成临床资料不足。
2. **fact_refs 仍按来源全量选择，而不是按实际参与判定的文书选择。** `_typed_decision_from_outcome()` 对每条规则收集 `_TYPED_RULE_SOURCE_KEYS` 的全部 observation。冻结用例中 027 因此把诊断、出院诊断、病理报告和出院记录全部投影为客户证据，尽管客户要核对的是出院治疗计划。后续迁移必须让执行器选择实际 `fact_refs`，公共投影再生成坐标；不能继续由 Aggregator 过滤或猜测。
3. **聚合器仍是本族客户事实结构的第二业务所有者。** 四条规则的安全事实校验仍位于聚合器。迁移目标应是执行器给出原始受控事实，Finalizer 校验，公共投影处理证据；聚合器只装配。

本冻结用例中的 027 为“不合规”不是一个已确认的业务缺陷：文本“继续肿瘤专科治疗”未满足当前确定性治疗计划模式，是否应当视为充分计划需由业务口径单独确认，不能在架构迁移中改变。

## 验证命令

```powershell
Set-Location D:\LLM\LX888\apps\medqc-web\backend
py -3.10 -m pytest -q tests/unit/test_luxian_0609_tumor_pathology_freeze.py
```

结果：`3 passed`。

## 下一步

1. 先独立修复并验收 013/019 的 LLM 技术失败映射；
2. 重新冻结受影响状态；
3. 迁出本族完整的事实校验和“实际选中文书”策略；
4. 删除聚合器中本族四条规则的专属分支，并新增归零守卫；
5. 最后通过三入口回归验证客户结果、坐标集合、调用次数与 Token。
