# 正式质控provider连接失败诊断报告

生成时间：2026-05-12 02:09:14

## 结论

- report_status：`failed_provider_unstable`。
- 本轮只诊断 provider/pack 稳定性，不做正式质控质量验收，不扩大样本。
- provider_error=46，timeout=0，rate_limit=0，technical_error_internal=162。
- tokens=0 且 technical_error_internal>0 的病历数：3。
- 失败 phase 分布：`{"fast_screen_first_pass": 322}`。
- 失败事件类型分布：`{"llm_generate_exception": 276, "pack_fallback": 46}`。

## 根因判断

- 失败发生在 `fast_screen_first_pass` 的 LLM pack 调用阶段；未进入可用于质量判断的二审结果稳定态。
- `pack_fallback` 是正式 pack 降级后的汇总记录，`llm_generate_exception` 是实际 provider 调用异常。
- 代表性 provider 异常：`All connection attempts failed`。
- 本机对同一 `https://api.siliconflow.cn/v1/chat/completions` 做最小 POST 可返回 200，说明 API key、模型名和基础 443 连通性不是完全不可用。
- 1915580 单病历 `pack_concurrency=1` 对照仍为 18 个 pack 全部 provider_error、tokens=0，基本排除“仅由 pack 并发=3 造成”。
- 运行日志显示本地 `user_llm_configs` 表不存在，服务回退 `.env` 配置；正式大 prompt/pack 调用路径仍稳定触发连接失败。
- 这不是 Sheet2 验收或二审 guardrail 的质量结论；provider 稳定前不得继续做 10/20 份质量抽检。

## 分病历稳定性

| visit_id | patient_name | wall(s) | tokens | provider | timeout | rate_limit | technical | status                   | display_status_counts                                    |
| -------- | ------------ | ------: | -----: | -------: | ------: | ---------: | --------: | ------------------------ | -------------------------------------------------------- |
| 1915580  | 雷德超       | 137.946 |      0 |       18 |       0 |          0 |        59 | failed_provider_unstable | `{"not_applicable": 25, "technical_error_internal": 59}` |
| 2024757  | 游德利       |   96.49 |      0 |       12 |       0 |          0 |        46 | failed_provider_unstable | `{"not_applicable": 38, "technical_error_internal": 46}` |
| 2287309  | 陈光华       | 129.696 |      0 |       16 |       0 |          0 |        57 | failed_provider_unstable | `{"not_applicable": 27, "technical_error_internal": 57}` |

## 门禁

- 若任一病历 `provider_error_count > 0`，本轮报告状态必须为 `failed_provider_unstable`。
- 若任一病历 `total_tokens=0` 且 `technical_error_internal_count>0`，本轮报告状态必须为 `failed_provider_unstable`。
- 只有 1915580、2024757、2287309 三份均满足 provider_error=0、timeout=0、rate_limit=0、tokens>0、technical_error_internal=0，才允许后续重新做 10 份抽检。
