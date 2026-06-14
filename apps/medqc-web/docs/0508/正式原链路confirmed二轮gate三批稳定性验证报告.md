# 正式原链路 confirmed 二轮 gate 三批稳定性验证报告

生成时间：2026-05-15 18:24:51

## 范围

- 本报告只汇总三批随机 10 病历正式原链路抽检和 confirmed_defect 二轮 LLM gate 结果。
- 未使用 structured evidence POC，未接页面，未写正式业务表，未扩大单批样本。

## 三批整体对比

| batch  | 样本数 | first-pass 状态            | first-pass confirmed | second-pass confirmed | data_quality_gap | rejected_by_system | 二轮 technical | confirmed 保留率 | 二轮 tokens | 平均耗时(s/份) | final parse_error | recovered parse retry |
| ------ | -----: | -------------------------- | -------------------: | --------------------: | ---------------: | -----------------: | -------------: | ---------------: | ----------: | -------------: | ----------------: | --------------------: |
| batch1 |     10 | `completed`                |                   18 |                     2 |                6 |                 10 |              0 |           11.11% |       12520 |         31.855 |                 0 |                     0 |
| batch2 |     10 | `failed_provider_unstable` |                    8 |                     0 |                3 |                  5 |              0 |             0.0% |        6196 |         32.465 |                 0 |                     1 |
| batch3 |     10 | `failed_provider_unstable` |                   10 |                     3 |                2 |                  5 |              0 |            30.0% |        7238 |          33.76 |                 0 |                     2 |

## 样本重复检查

- 三批内重复 visit_id：`{}`。

## 误报收敛效果

- 二轮高频驳回/降级规则：
  - `SC-015`：5
  - `SC-118`：4
  - `SC-097`：3
  - `SC-123`：3
  - `SC-121`：3
  - `SC-008`：2
  - `SC-036`：2
  - `SC-014`：1
  - `SC-010`：1
  - `SC-050`：1
  - `SC-055`：1
  - `SC-012`：1
  - `SC-013`：1
  - `SC-004`：1
  - `SC-122`：1
- 二轮保留 confirmed 规则：
  - `SC-123`：2
  - `SC-083`：1
  - `SC-015`：1
  - `SC-013`：1
- evidence_too_short 但仍被 confirmed：1。
- quote_missing 但仍被 confirmed：0。

## first-pass parse_error 说明

- batch2/batch3 原 summary 中的 parse_error 来自已恢复的 pack retry，而非最终失败。
- 本报告按最终 pack diagnostic 重新统计：`final parse_error` 必须看 diagnostic.parse_error；已成功的 `pack_retry_reason=parse_error` 单独计入 recovered parse retry。

## 过严风险初筛

| batch  | visit_id | rule_id | 二轮状态           | possible_over_reject | possible_over_downgrade | reason                                                                          |
| ------ | -------- | ------- | ------------------ | -------------------- | ----------------------- | ------------------------------------------------------------------------------- |
| batch1 | 2229247  | SC-014  | rejected_by_system | False                | False                   | 抽样覆盖项，当前自动标签未提示明显过严。                                        |
| batch1 | 2229247  | SC-015  | rejected_by_system | True                 | False                   | first-pass 证据初筛未明显标记短证据/缺 quote/疑似误报，需人工确认是否二轮过严。 |
| batch1 | 2229247  | SC-097  | data_quality_gap   | False                | False                   | 抽样覆盖项，当前自动标签未提示明显过严。                                        |
| batch1 | 2310639  | SC-015  | rejected_by_system | False                | False                   | 抽样覆盖项，当前自动标签未提示明显过严。                                        |
| batch1 | 2310639  | SC-097  | data_quality_gap   | False                | False                   | 抽样覆盖项，当前自动标签未提示明显过严。                                        |
| batch1 | 2191573  | SC-097  | data_quality_gap   | False                | False                   | 抽样覆盖项，当前自动标签未提示明显过严。                                        |
| batch1 | 2035546  | SC-010  | rejected_by_system | False                | False                   | 抽样覆盖项，当前自动标签未提示明显过严。                                        |
| batch1 | 2035546  | SC-118  | data_quality_gap   | False                | False                   | 抽样覆盖项，当前自动标签未提示明显过严。                                        |
| batch1 | 2035546  | SC-123  | rejected_by_system | True                 | False                   | first-pass 证据初筛未明显标记短证据/缺 quote/疑似误报，需人工确认是否二轮过严。 |
| batch1 | 2243538  | SC-008  | rejected_by_system | False                | False                   | 抽样覆盖项，当前自动标签未提示明显过严。                                        |
| batch1 | 2243538  | SC-015  | rejected_by_system | False                | False                   | 抽样覆盖项，当前自动标签未提示明显过严。                                        |
| batch1 | 2068785  | SC-036  | rejected_by_system | False                | False                   | 抽样覆盖项，当前自动标签未提示明显过严。                                        |
| batch1 | 2097628  | SC-118  | data_quality_gap   | False                | False                   | 抽样覆盖项，当前自动标签未提示明显过严。                                        |
| batch1 | 2097628  | SC-121  | rejected_by_system | False                | False                   | 抽样覆盖项，当前自动标签未提示明显过严。                                        |
| batch1 | 2097628  | SC-123  | rejected_by_system | True                 | False                   | first-pass 证据初筛未明显标记短证据/缺 quote/疑似误报，需人工确认是否二轮过严。 |
| batch1 | 1962391  | SC-118  | data_quality_gap   | False                | False                   | 抽样覆盖项，当前自动标签未提示明显过严。                                        |
| batch2 | 2032392  | SC-118  | data_quality_gap   | False                | False                   | 抽样覆盖项，当前自动标签未提示明显过严。                                        |
| batch2 | 2037363  | SC-121  | rejected_by_system | False                | False                   | 抽样覆盖项，当前自动标签未提示明显过严。                                        |
| batch2 | 2037363  | SC-123  | rejected_by_system | False                | False                   | 抽样覆盖项，当前自动标签未提示明显过严。                                        |
| batch2 | 2273484  | SC-036  | rejected_by_system | True                 | False                   | first-pass 证据初筛未明显标记短证据/缺 quote/疑似误报，需人工确认是否二轮过严。 |

## 推荐结论

- 二轮 gate 在三批中稳定降低 first-pass confirmed 数量，具备 feature flag 旁路验证价值。
- 暂不建议默认接入正式链路：仍需人工复核二轮过严风险，尤其是被降级的高价值规则。
- 下一步优先补规则级准入约束：SC-097/SC-118/SC-123 等短片段/出院带药类规则，以及 SC-036 跨文书对照证据。
