# 正式质控默认模型 qwen3.5 门禁验证报告

- 生成时间：2026-05-20T19:14:15
- provider：alibaba
- endpoint_host：dashscope.aliyuncs.com
- model：qwen3.5-35b-a3b
- key_present：True
- key_prefix_hash：93fac017a605

## 配置结论

- 正式质控默认 provider 已统一为 `alibaba`。
- 正式质控默认 endpoint 已统一为 `https://dashscope.aliyuncs.com/compatible-mode/v1`。
- 正式质控默认 model 已统一为 `qwen3.5-35b-a3b`。
- 本地 `backend/.env` 已仅在本机改为 `LLM_MODEL=qwen3.5-35b-a3b`，不纳入提交，不包含 API key。
- `user_llm_configs` 表当前不存在，运行时按现有逻辑回退到 `.env`；本轮门禁验证确认该回退路径使用 qwen3.5 成功。
- 仍存在 `qwen3.6-35b-a3b` 历史引用，主要是 SC-146/synthetic 既有基线数据、旧脚本默认值和历史报告，不属于本轮正式 final fast_screen_full 默认模型路径；本轮已移除后端内置模型列表中的 qwen3.6 默认展示项。

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
- total_tokens：40600
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

- total_tokens：40589
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

## 是否允许继续 random10

允许继续原 random10 A/B 或 prompt 修正回归；前提是继续使用 `qwen3.5-35b-a3b` 并保持只读、不写正式 QC 结果表。
