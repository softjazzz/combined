# 正式质控provider连接失败诊断报告

生成时间：2026-05-12 02:58:24

## 结论

- report_status：`provider_stability_pass`。
- 本轮只诊断 provider/pack 稳定性，不做正式质控质量验收，不扩大样本。
- provider_error=0，provider_connection_error=0，upstream_http_error=0，parse_error=0。
- timeout=0，rate_limit=0，technical_error_internal=0。
- tokens=0 且 technical_error_internal>0 的病历数：0。
- 失败 phase 分布：`{}`。
- 失败事件类型分布：`{}`。

## 根因判断

- 3 份稳定性复跑均未出现 provider/timeout/rate_limit/technical_error。
- 当前可以把 provider 层标记为临时稳定，但仍不代表结果质量已经可演示。

## 分病历稳定性

| visit_id | patient_name | wall(s) | tokens | provider | upstream_http | parse | timeout | rate_limit | technical | status | display_status_counts |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- | --- |
| minimal_chat_probe |  | 0.845 | 27 | 0 | 0 | 0 | 0 | 0 | 0 | provider_stability_pass | `{}` |

## 门禁

- 若任一病历 `provider_error_count > 0`，本轮报告状态必须为 `failed_provider_unstable`。
- 若任一病历 `upstream_http_error_count > 0`，本轮报告状态必须为 `failed_provider_unstable`。
- 若任一病历 `parse_error_count > 0`，本轮报告状态必须为 `failed_provider_unstable`，并归因为 `response_parse_error`。
- 若任一病历 `total_tokens=0` 且 `technical_error_internal_count>0`，本轮报告状态必须为 `failed_provider_unstable`。
- 只有 1915580、2024757、2287309 三份均满足 provider_error=0、timeout=0、rate_limit=0、tokens>0、technical_error_internal=0，才允许后续重新做 10 份抽检。
