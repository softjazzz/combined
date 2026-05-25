# 正式质控 DeepSeek V4 Flash 切换与门禁验证报告

生成时间：2026-05-25 15:52

## 切换范围

- 正式质控默认 provider：`deepseek`
- 正式质控默认 endpoint：`https://api.deepseek.com`
- 正式质控默认 model：`deepseek-v4-flash`
- 二审默认 model：未显式配置时回退 `LLM_MODEL`；本地 `.env` 已设置为 `deepseek-v4-flash`
- 本轮未提交真实 `.env` 或 API key；`backend/.env` 仅做本地运行配置更新

## 配置改动

- `Settings.LLM_API_ENDPOINT` 默认值已从 DashScope 切到 DeepSeek 官方 API。
- `Settings.LLM_DEFAULT_PROVIDER` 默认值已从 `alibaba` 切到 `deepseek`。
- `Settings.LLM_MODEL` 默认值已从 `qwen3.5-35b-a3b` 切到 `deepseek-v4-flash`。
- `llm_config_loader` 中 DeepSeek provider 的默认模型已从 `deepseek-chat` 切到 `deepseek-v4-flash`。
- 当默认 provider 为 `deepseek` 时，DeepSeek runtime 支持复用统一配置 `LLM_API_KEY`，也兼容 `DEEPSEEK_API_KEY`。
- `.env.example` 已同步 DeepSeek 官方 endpoint/model；真实 `.env` 不纳入提交。

## qwen3.6 残留检查

- 正式默认配置不再使用 `qwen3.6-35b-a3b`。
- `LLM_ADJUDICATOR_MODEL` 代码默认仍为 `None`，未配置时回退一审模型。
- 历史 A/B、POC、双模型验证脚本和历史报告中仍保留 qwen 文本，用于复现实验口径，本轮未批量改写历史产物。

## Minimal Chat Probe

- provider：`deepseek`
- endpoint_host：`api.deepseek.com`
- model：`deepseek-v4-flash`
- key_present：`true`
- key_prefix_hash：`9670d79da86e`
- http_status：`200`
- has_choices：`true`
- usage_total_tokens：`41`
- provider_error：`0`
- upstream_http_error：`0`
- provider_connection_error：`0`
- parse_error：`0`
- timeout：`0`
- rate_limit：`0`

## 单病历 c1 门禁

- visit_id：`2122521`
- pack_concurrency：`1`
- wall_clock_time：`125.541s`
- llm_call_count：`10`
- total_tokens：`43827`
- provider_error：`0`
- upstream_http_error：`0`
- provider_connection_error：`0`
- parse_error：`0`
- timeout：`0`
- rate_limit：`0`
- technical_error_internal：`0`

## 单病历 c3 门禁

- visit_id：`2122521`
- pack_concurrency：`3`
- wall_clock_time：`54.242s`
- llm_call_count：`10`
- total_tokens：`44963`
- provider_error：`0`
- upstream_http_error：`0`
- provider_connection_error：`0`
- parse_error：`0`
- timeout：`0`
- rate_limit：`0`
- technical_error_internal：`0`

## 结论

DeepSeek 官方 API + `deepseek-v4-flash` 已通过 minimal、2122521 c1、2122521 c3 最小门禁。后续可以继续运行 random10 或规则 Prompt 回归，但应明确这是 DeepSeek v4 Flash 新基线，不再与 DashScope/qwen 双模型结果混用为同一质量结论。
