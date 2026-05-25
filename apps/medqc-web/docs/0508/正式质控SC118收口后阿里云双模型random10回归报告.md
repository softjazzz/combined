# 正式质控 SC-118 收口后阿里云双模型 random10 回归报告

生成时间：2026-05-26 00:14:39

## 执行范围

- 链路：正式原链路 `final fast_screen_full / sc_content_full_v1`，一审后走正式后处理与二轮裁决。
- 模型：一审 `qwen3.5-35b-a3b`，二审 `qwen3.6-35b-a3b`，provider 为阿里云百炼。
- 本轮基线：已包含 `dc75dda84 收紧SC118出院记录字段矩阵准入`。
- 运行方式：只读审计脚本，不写正式 QC 结果表，不接页面，不使用 structured evidence POC。
- 样本：复用同一批 random10 visit_id，不扩大到 20 份。

## 稳定性与性能

- 完成病历：10/10。
- 总墙钟耗时：492.70s；平均：49.27s；最慢：63.64s。
- LLM 调用数：142；总 token：783024；平均 token：78302。
- provider_error=0，provider_connection_error=0，upstream_http_error=0。
- parse_error=0，timeout=0，rate_limit=0，technical_error_internal=0。
- 稳定性门禁：通过。

## 终态统计

- confirmed_defect：0。
- data_quality_gap：100。
- rejected_by_system：84。
- technical_error_internal：0。

本轮没有 confirmed_defect，因此 confirmed keep rate 不可评价。该结果只能说明当前 guardrail 未产生确认缺陷误报，不能证明 confirmed 质量已经达到可演示或可扩大验收标准。

## SC-118 回归结论

SC-118 在 10 份病历中均被分流为 `data_quality_gap`，没有进入 `confirmed_defect`。

主要原因：

- SC-118 出院记录字段矩阵已生效，`admission_date`、`discharge_date`、`admission_diagnosis`、`treatment_course`、`discharge_condition`、`doctor_signature` 等关键字段缺口被标记为 `unknown` 或上下文不足。
- 当前逻辑不再把出院记录短片段、字段标题未出现、文书头或局部内容直接解释为“出院记录缺项”。
- `sc118_discharge_matrix_can_confirm_missing=false` 时，统一进入 `data_quality_gap`，符合“不能把当前证据没看到等同于病历确实没写”的准生产口径。

结论：SC-118 修复对防止短片段误 confirmed 有效，但目前偏保守。下一步应优先补齐出院记录结构化字段和完整段落覆盖，而不是继续加更宽泛的拦截。

## 同类规则观察

- SC-121：data_quality_gap=4，rejected_by_system=6，confirmed=0。
- SC-122：data_quality_gap=1，confirmed=0。
- SC-125：data_quality_gap=7，rejected_by_system=3，confirmed=0。
- SC-146：data_quality_gap=1，rejected_by_system=7，confirmed=0。

这些规则本轮没有 confirmed 误报，但 data_gap 仍较高，说明主要瓶颈已经从 confirmed 误判转为 evidence matrix / 源文书覆盖不足。

## Gate 影响

- SC-083：触发 10 条；decision={"data_quality_gap": 9, "rejected_by_system": 1}；programmatic_confirmed=0。
- SC-099：触发 10 条；decision={"data_quality_gap": 3, "pass_to_second_gate": 3, "rejected_by_system": 4}；programmatic_confirmed=0。
- SC-123：触发 10 条；decision={"data_quality_gap": 1, "pass_to_second_gate": 2, "rejected_by_system": 7}；programmatic_confirmed=0。
- 非 SC-083/099/123 gate metadata 异常：0。

既有 SC-083/SC-099/SC-123 gate 未回退，且没有任何程序化 confirmed。

## 质量结论

- 本轮不能计算 keep rate，因为 confirmed_defect=0。
- 不建议基于本轮结果扩大到 20 份；原因不是稳定性，而是没有 confirmed 样本可供质量验收。
- 不建议页面演示 confirmed 缺陷；可以用于展示稳定的四层分流和 gate 自我保护，但不能证明确认缺陷质量。
- 当前准生产策略仍应保持：高风险语义、跨文书、文书完整性规则没有 evidence matrix 或完整上下文时，不允许 confirmed。

## 下一步建议

1. 先补 SC-118 出院记录字段矩阵的数据覆盖：确认 `discharge_record` 的完整正文、结构化字段、段落切分是否进入正式 evidence context。
2. 针对 SC-121 做同类 evidence matrix 覆盖审计：重点是诊疗经过完整段落、住院医嘱、检查检验、病程变化之间的跨文书对照。
3. SC-125 需要诊断矩阵补强：入院诊断、出院诊断、主诊断标识、诊断顺序、手术/病理/主要治疗对照。
4. SC-146 保持现有稳定性修复，不扩大治理范围；如再次出现 confirmed 误报，再做 targeted replay。
5. 完成上述 evidence/source 覆盖补强后，再复用同一 random10 回归；在 confirmed 数量恢复且 keep rate 可评价前，不建议扩大到 20 份。
