# DeepSeek 关闭 thinking 后 2013648 定向复跑报告

生成时间：2026-05-25 21:19:35

## 运行范围

- 链路：正式 `final fast_screen_full / sc_content_full_v1`
- provider：`deepseek`
- model：`deepseek-v4-flash`
- thinking：显式 `{"type":"disabled"}`
- visit_id：`2013648`，患者：鲁明山
- 重点规则：`SC-070`
- 模式：只读，不写正式 QC 结果表，不跑 random10，不扩大样本

## 稳定性与 token

- report_status：`completed`
- total_tokens：80855
- prompt_tokens：43053
- completion_tokens：6425
- wall_clock_time：49.37s
- llm_call_count：16
- provider_error：0
- provider_connection_error：0
- upstream_http_error：0
- parse_error：0
- timeout：0
- rate_limit：0
- technical_error_internal：0

## thinking 观测

- metadata_row_count：26
- llm_metadata_row_count：25
- non_llm_or_blank_metadata_row_count：1
- requested_disable_thinking=true：25
- requested_enable_thinking=true：0
- response_has_reasoning_content=true：0
- all_llm_calls_requested_disable_thinking：True
- any_response_has_reasoning_content：False
- cot_mode_counts：`{"blank": 1, "disabled": 25}`

## SC-070 对比

- 原状态：`confirmed_defect`
- 新状态：`data_quality_gap`
- 误报是否修正：True
- 原 adjudicator_reason：会诊意见已记录，但病程记录中未记录执行情况
- 新 adjudicator_reason：病程记录中未见会诊意见及执行情况，但缺乏会诊记录或相关文书来源，无法确认是否存在会诊。
- 原 supporting_quote：会诊记录存在，但日常病程及上级查房未提及会诊意见执行
- 新 supporting_quote：查房内容：:今日查房：患者精神食欲尚可，睡眠一般，大便通畅，小便困难，患者诉左小腿疼痛不适较前明显缓解
- 新 postprocess_reason：病程记录中未见会诊意见及执行情况，但缺乏会诊记录或相关文书来源，无法确认是否存在会诊。
- 新 evidence：【当前文书】查房内容：:今日查房：患者精神食欲尚可，睡眠一般，大便通畅，小便困难，患者诉左小腿疼痛不适较前明显缓解

## 结论

- thinking 已显式关闭且未返回 reasoning_content；SC-070 不再是 confirmed_defect，本轮定向误报已修正。
