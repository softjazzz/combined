# LX0609 肿瘤病理族：现状冻结与精确证据引用重冻结

## 范围与目的

先为 `LX0609-013/019/026/027` 建立迁移前的主链冻结证据；随后独立修复执行器的证据归属，重新冻结。未触碰聚合器、Finalizer、规则口径、Prompt、数据库、API 或前端。

冻结链路为：

```text
Evidence read session → tumor_pathology native executor → RuleDecision
→ Binding/Reducer → aggregate_luxian_0609_results → customer result
```

本族当前 `executor_key=tumor_pathology`，四条均在客户规则目录中；`LUXIAN_0609_CUSTOMER_EXCLUDED_RULE_IDS` 不包含这四条，当前没有暂停项。因此客户范围为：013、019、026、027 均 active。

## 现状冻结用例

新增测试：`backend/tests/unit/test_luxian_0609_tumor_pathology_freeze.py`。

主用例使用同一只读 session 的受控结构化材料：病理最终诊断、手术/病程中的病理记录、结构化化疗医嘱与对应病程、恶性诊断和出院记录。

| 规则 | 冻结状态 / reason                    | 冻结展示事实                                                   | 冻结客户证据坐标集合                                                                                     |
| ---- | ------------------------------------ | -------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------- |
| 013  | compliant / requirement_satisfied    | `pathology_result_documentation_check`                         | `pathology_exam_report:path-report-1`、`surgery_record:surgery-1`                                        |
| 019  | compliant / requirement_satisfied    | `pathology_sampling_documentation_check`                       | `pathology_exam_master:path-master-1`、`pathology_exam_report:path-report-1`、`surgery_record:surgery-1` |
| 026  | compliant / requirement_satisfied    | `chemotherapy_order_course_comparison`                         | `inpat_drug_order:chemo-order-1`、`daily_course_record:course-1`                                         |
| 027  | non_compliant / requirement_violated | `malignant_discharge_plan_check`，其中 `tumor_treatment=false` | `discharge_record:discharge-1`                                                                           |

该确定性用例的 LLM 调用、输入/输出 Token 均为 0。它证明相同事实链无需语义调用即可稳定输出；不代表 013/019 的语义兜底分支不存在。

另冻结完整空病理来源与病理报告查询异常：

| 输入形状                         | 013/019 状态 / reason                    |
| -------------------------------- | ---------------------------------------- |
| 两类病理来源均完整为空           | not_applicable / trigger_absent_complete |
| `pathology_exam_report` 查询异常 | technical_error / source_query_error     |

另冻结 019 进入语义兜底后的受控模型传输失败：执行器计为 1 次调用、0 Token，结果为 `technical_error / model_transport_error`；`fact_refs` 仅保留该次实际送入模型的病理、手术和病程文书。

既有 `test_typed_019_optional_llm_matches_raw_state_calls_tokens_and_prompt` 记录 019 语义兜底在相同材料下的单次调用与 110 Token；本次不重写该既有业务测试。

## 迁移前所有权基线

`luxian_0609_result_aggregator.py` 仍有四条规则的专属客户事实校验分支：013、026、027、019（约 1725–1860 行），且保留 026 的专属客户证据白名单。这是后续完整迁移需归零的基线，提交 A 不预写 `xfail` 或归零守卫。

## 已关闭的迁移前阻塞项

1. **技术失败语义：**模型传输失败和非法输出已固定为 `technical_error`，不再伪装成临床资料不足。
2. **fact_refs：**`RuleDecision` 由执行器仅选择实际触发、实际匹配或实际送模的材料行；空触发没有文书时保留来源级审计引用，公共投影不会伪造成客户文书。

仍未在本提交处理的结构债：聚合器仍是本族客户事实结构的第二业务所有者。后续迁移应让执行器给出原始受控事实，Finalizer 校验，公共投影处理证据，聚合器只装配。

本冻结用例中的 027 为“不合规”不是一个已确认的业务缺陷：文本“继续肿瘤专科治疗”未满足当前确定性治疗计划模式，是否应当视为充分计划需由业务口径单独确认，不能在架构迁移中改变。

## 验证命令

```powershell
Set-Location D:\LLM\LX888\apps\medqc-web\backend
py -3.10 -m pytest -q tests/unit/test_luxian_0609_tumor_pathology_freeze.py
```

结果：`9 passed`（Native → Binding → Aggregator，证据坐标按集合比较）。

## 下一步

1. 迁出本族完整的事实校验和“实际选中文书”策略；
2. 删除聚合器中本族四条规则的专属分支，并新增归零守卫；
3. 最后通过三入口回归验证客户结果、坐标集合、调用次数与 Token。
