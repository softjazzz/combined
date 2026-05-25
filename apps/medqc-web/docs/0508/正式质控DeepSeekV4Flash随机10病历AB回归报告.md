# 正式质控 DeepSeek V4 Flash random10 A/B 回归报告

生成时间：2026-05-25 16:29:27

## 运行范围

- 链路：正式原链路 `final fast_screen_full / sc_content_full_v1`
- 模型：`deepseek-v4-flash`
- provider：`deepseek`
- endpoint_host：`api.deepseek.com`
- 样本：复用 qwen 双模型 random10 同一批 10 个 visit_id
- 模式：只读，不写正式 QC 结果表，不扩大到 20 份

## Provider 门禁

- provider：`deepseek`
- model：`deepseek-v4-flash`
- tokens：74
- has_choices：True
- provider_error：0
- upstream_http_error：0
- parse_error：0
- timeout：0
- rate_limit：0
- 门禁：通过

## 稳定性

- report_status：`completed`
- completed_visit_count：10/10
- provider_error：0
- provider_connection_error：0
- upstream_http_error：0
- parse_error：0
- timeout：0
- rate_limit：0
- technical_error_internal：0
- 稳定性结论：通过

## 性能与 token

- total_wall_clock_time：1147.23s
- average_wall_clock_time：114.72s/份
- max_wall_clock_time：156.53s
- llm_call_count：140
- total_tokens：890596

## A/B 质量对比

- baseline confirmed_defect：5
- DeepSeek confirmed_defect：20
- baseline confirmed_keep：2
- DeepSeek confirmed_keep：7
- baseline keep_rate：40.0%
- DeepSeek keep_rate：35.0%
- confirmed 收缩率：-300.0%
- DeepSeek data_quality_gap：115
- DeepSeek rejected_by_system：104

## DeepSeek confirmed 误报聚类

- SC-118 / downgrade_to_data_gap：5
- SC-014 / downgrade_to_data_gap：2
- SC-044 / keep：2
- SC-118 / keep：2
- SC-146 / keep：2
- SC-014 / downgrade_to_rejected_by_system：1
- SC-014 / keep：1
- SC-020 / downgrade_to_data_gap：1
- SC-070 / downgrade_to_rejected_by_system：1
- SC-097 / downgrade_to_data_gap：1
- SC-125 / downgrade_to_data_gap：1
- SC-146 / downgrade_to_data_gap：1

## 下一步治理建议

- P0：SC-118。DeepSeek 将出院记录字段缺项类 confirmed 放大，5 条建议转 data_quality_gap，说明出院记录完整字段矩阵仍不足。
- P0：SC-014。个人史/婚育史/家族史等生活史字段被放大为 confirmed，需按字段矩阵和客户口径收紧。
- P1：SC-146、SC-125、SC-097。当前数量较少，但仍有 confirmed 证据链不足，需要保留在下一轮误报治理清单。
- 暂不扩大到 20 份；先治理上述规则，再用同一 random10 复验。

## 结论

- 稳定性通过，但 confirmed keep rate 未达到 70%；不建议扩大到 20 份，下一步应继续治理具体误报规则。
