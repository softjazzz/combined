# 正式质控provider连接失败诊断报告

生成时间：2026-05-12 03:15:16

## 结论

- report_status：`failed_provider_unstable`。
- 本轮只诊断 provider/pack 稳定性，不做正式质控质量验收，不扩大样本。
- provider_error=1，provider_connection_error=1，upstream_http_error=0，parse_error=0。
- timeout=0，rate_limit=0，technical_error_internal=0。
- tokens=0 且 technical_error_internal>0 的病历数：0。
- 失败 phase 分布：`{"minimal_chat_probe": 1}`。
- 失败事件类型分布：`{"minimal_chat_probe": 1}`。

## 根因判断

- 失败发生在 `minimal_chat_probe`，未进入正式 pack。
- `pack_fallback` 是正式 pack 降级后的汇总记录，`llm_generate_exception` 是实际 provider 调用异常。
- 代表性异常：`All connection attempts failed`。
- 归因：provider_connection_error。
- 这不是 Sheet2 验收或二审 guardrail 的质量结论；provider 稳定前不得继续做 10/20 份质量抽检。

## 分病历稳定性

| visit_id | patient_name | wall(s) | tokens | provider | upstream_http | parse | timeout | rate_limit | technical | status | display_status_counts |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- | --- |
| minimal_chat_probe |  | 0.258 | 0 | 1 | 0 | 0 | 0 | 0 | 0 | failed_provider_unstable | `{}` |

## 门禁

- 若任一病历 `provider_error_count > 0`，本轮报告状态必须为 `failed_provider_unstable`。
- 若任一病历 `upstream_http_error_count > 0`，本轮报告状态必须为 `failed_provider_unstable`。
- 若任一病历 `parse_error_count > 0`，本轮报告状态必须为 `failed_provider_unstable`，并归因为 `response_parse_error`。
- 若任一病历 `total_tokens=0` 且 `technical_error_internal_count>0`，本轮报告状态必须为 `failed_provider_unstable`。
- 只有 1915580、2024757、2287309 三份均满足 provider_error=0、timeout=0、rate_limit=0、tokens>0、technical_error_internal=0，才允许后续重新做 10 份抽检。
