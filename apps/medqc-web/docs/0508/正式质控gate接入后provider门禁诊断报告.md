# 正式质控 gate 接入后 provider 门禁诊断报告

- 生成时间：2026-05-19T15:03:52
- provider：alibaba
- endpoint_host：dashscope.aliyuncs.com
- model：qwen3.6-35b-a3b
- key_present：True
- key_prefix_hash：93fac017a605

## Minimal Chat Probe

- success：True
- http_status：200
- has_choices：True
- usage_total_tokens：28
- exception_type：
- provider_error：0
- upstream_http_error：0
- provider_connection_error：0
- parse_error：0
- timeout：0
- rate_limit：0
- upstream_error_summary：

## 单病历 c1 门禁

- visit_id：2122521
- total_tokens：40839
- llm_call_count：10
- wall_clock_time：41.177
- provider_error：0
- upstream_http_error：0
- provider_connection_error：0
- parse_error：0
- timeout：0
- rate_limit：0
- technical_error_internal：0
- exception_type：
- raw_error_summary：

## 单病历 c3 门禁

- total_tokens：40791
- llm_call_count：10
- wall_clock_time：19.513
- provider_error：0
- upstream_http_error：0
- provider_connection_error：0
- parse_error：0
- timeout：0
- rate_limit：0
- technical_error_internal：0
- exception_type：
- raw_error_summary：

## 门禁结论

minimal、c1、c3 均通过；后续才允许另行重跑随机 10。
