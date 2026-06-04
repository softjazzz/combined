# QC Agent Pi 回归测试报告

- 生成时间：2026-06-04T05:01:53+00:00
- Python：3.11.9
- pi-agent：0.1.0
- pi-agent-core：0.1.1
- requests：2.34.2
- 编排模式：requests_fallback
- 认证模式：missing
- 已尝试登录：否
- 登录账号：未记录
- API：http://127.0.0.1:8001/api/v1/qc-agent/chat
- visit_id：2361619

## 汇总

- 总数：2
- 通过：0
- 失败：0
- 跳过：2

## 用例结果

| case_id   | status  | passed | plan_tools | warnings                                                                                                                    | error                      |
| --------- | ------- | ------ | ---------- | --------------------------------------------------------------------------------------------------------------------------- | -------------------------- |
| env_check | skipped | 是     |            | Python/Pi/request 环境检查已通过，未调用 API。                                                                              |                            |
| api_auth  | skipped | 否     |            | 未设置 MEDQC_ACCESS_TOKEN，API 回归测试已跳过。<br>可通过 MEDQC_ACCESS_TOKEN 或 --login-account/--login-password 提供认证。 | missing MEDQC_ACCESS_TOKEN |

## 安全说明

- 脚本不导入 MedQC 后端 app 包，只作为外部 HTTP client 调用 QC Agent chat API。
- token 仅从 MEDQC_ACCESS_TOKEN 环境变量读取，报告和控制台都不输出 token。
- JSON/Markdown 报告只保存裁剪后的响应摘要，不保存完整 API 响应。
- 每个用例都会递归扫描 sensitive keys：medical_text、record_content、documents、bundle、structured_context、prompt、examples、internal_data、raw_llm_output。
- 当前 Pi 包用于独立测试环境校验；由于 Pi Agent API 尚未接入生产后端，本轮编排模式为 requests_fallback。
