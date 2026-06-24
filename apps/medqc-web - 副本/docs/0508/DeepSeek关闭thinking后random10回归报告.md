# DeepSeek 关闭 thinking 后 random10 回归报告

生成时间：2026-05-25 22:22:33

## 运行范围

- 链路：正式 `final fast_screen_full / sc_content_full_v1`
- provider/model：`deepseek / deepseek-v4-flash`
- thinking：显式 `{"type":"disabled"}`
- 样本：复用原 DeepSeek random10 完全相同 10 个 visit_id
- 模式：只读，不写正式 QC 结果表，不扩大到 20 份，不改规则 prompt/gate

visit_id：`2013648`, `2191214`, `1965856`, `2262370`, `1962863`, `2048454`, `2083787`, `2263802`, `2328501`, `2262981`

## 新旧对比

| 指标                     | 原 DeepSeek thinking 默认 | 关闭 thinking 后 |   变化 |
| ------------------------ | ------------------------: | ---------------: | -----: |
| total_tokens             |                    890596 |           791387 | -11.1% |
| first_pass_total_tokens  |                    550552 |           476900 | -13.4% |
| adjudicator_total_tokens |                    340044 |           314487 |  -7.5% |
| total_wall_clock_time    |                  1147.23s |          435.10s | -62.1% |
| average_wall_clock_time  |                   114.72s |           43.51s | -62.1% |
| llm_call_count           |                       140 |              140 |     +0 |
| confirmed_defect         |                        20 |               14 |     -6 |
| data_quality_gap         |                       115 |              119 |     +4 |
| rejected_by_system       |                       104 |              113 |     +9 |
| confirmed_keep_rate      |                     35.0% |            21.4% | -13.6% |

## thinking 与稳定性门禁

- requested_disable_thinking_count：235
- llm_metadata_row_count：235
- response_has_reasoning_content_count：0
- cot_mode 分布：`{"blank": 11, "disabled": 235}`
- provider_error：0
- provider_connection_error：0
- upstream_http_error：0
- parse_error：0
- timeout：0
- rate_limit：0
- technical_error_internal：0
- 门禁：通过

## 重点规则状态分布

| rule_id | 原 DeepSeek 分布                                                          | 关闭 thinking 后分布                                                      |
| ------- | ------------------------------------------------------------------------- | ------------------------------------------------------------------------- |
| SC-118  | `{"confirmed_defect": 7, "data_quality_gap": 3}`                          | `{"confirmed_defect": 6, "data_quality_gap": 3}`                          |
| SC-014  | `{"confirmed_defect": 4, "data_quality_gap": 4, "rejected_by_system": 2}` | `{}`                                                                      |
| SC-146  | `{"confirmed_defect": 3, "data_quality_gap": 5}`                          | `{"confirmed_defect": 2, "data_quality_gap": 2, "rejected_by_system": 3}` |
| SC-125  | `{"confirmed_defect": 1, "data_quality_gap": 4, "rejected_by_system": 5}` | `{"data_quality_gap": 7, "rejected_by_system": 3}`                        |
| SC-097  | `{"confirmed_defect": 1, "data_quality_gap": 4}`                          | `{"data_quality_gap": 4, "rejected_by_system": 1}`                        |
| SC-070  | `{"confirmed_defect": 1, "data_quality_gap": 3, "rejected_by_system": 1}` | `{"data_quality_gap": 2, "rejected_by_system": 4}`                        |

## 质量复核

- confirmed_defect：14
- confirmed_keep：3
- confirmed keep rate：21.4%

## 结论

- 稳定性和 thinking 门禁通过，但 confirmed keep rate 仍未达 70%；不建议扩大到 20 份，应继续治理具体误报规则。
