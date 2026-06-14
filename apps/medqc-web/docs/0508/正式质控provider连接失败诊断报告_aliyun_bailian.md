# 正式质控 provider 诊断报告：阿里云百炼临时切换

生成时间：2026-05-12

## 临时配置

- provider：`alibaba`
- endpoint：`https://dashscope.aliyuncs.com/compatible-mode/v1`
- model：`qwen3.6-35b-a3b`
- API key 来源：PowerShell 临时环境变量 `LLM_API_KEY=$env:DASHSCOPE_API_KEY`，并已确认不同于 backend `.env` 中的 SiliconFlow `LLM_API_KEY`。
- 本轮未提交密钥，未修改业务逻辑。

## 运行结果

| visit_id | pack_concurrency | report_status            | provider_error | timeout | rate_limit | technical_error_internal | total_tokens | wall_clock_time |
| -------- | ---------------: | ------------------------ | -------------: | ------: | ---------: | -----------------------: | -----------: | --------------: |
| 1915580  |                3 | failed_provider_unstable |             18 |       0 |          0 |                      116 |            0 |           5.793 |
| 1915580  |                1 | failed_provider_unstable |             18 |       0 |          0 |                      116 |            0 |          11.547 |

## 失败定位

- 本轮阿里云百炼没有复现 SiliconFlow 的 `All connection attempts failed`。
- 失败发生在 `fast_screen_first_pass` 的正式 pack fallback 层。
- 18 个 pack 的 `raw_error` 均为 `parse_error`。
- `pack_concurrency=1` 与 `pack_concurrency=3` 均失败，说明不是单纯并发造成。
- 因 `total_tokens=0` 且 `technical_error_internal>0`，本轮不具备质量验收价值。

## 门禁结论

- `1915580` 未通过 provider 稳定性门禁。
- 未继续运行 `2024757`、`2287309` 三病历稳定性诊断。
- 不允许扩大到 10 份抽检。
- 当前只能结论为：阿里云百炼临时切换后连接层错误消失，但正式 pack 响应解析仍不稳定，需要先定位 `parse_error` 的响应格式/JSON schema 兼容问题。

## 产物

- `formal_qc_provider_failure_diagnostics_aliyun_bailian_1915580_c3.csv`
- `formal_qc_provider_failure_diagnostics_aliyun_bailian_1915580_c3.json`
- `正式质控provider连接失败诊断报告_aliyun_bailian_1915580_c3.md`
- `formal_qc_provider_failure_diagnostics_aliyun_bailian_1915580_c1.csv`
- `formal_qc_provider_failure_diagnostics_aliyun_bailian_1915580_c1.json`
- `正式质控provider连接失败诊断报告_aliyun_bailian_1915580_c1.md`
