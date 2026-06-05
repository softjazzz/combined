# QC Agent Pi 回归测试报告

- 生成时间：2026-06-05T02:47:33+00:00
- Python：3.11.9
- pi-agent：0.1.0
- pi-agent-core：0.1.1
- requests：2.34.2
- 编排模式：requests_fallback
- 认证模式：auto_login_args
- 已尝试登录：是
- 登录账号：a\*\*\*@medqc.com
- API：http://127.0.0.1:8001/api/v1/qc-agent/chat
- visit_id：2298532

## 汇总

- 总数：6
- 通过：5
- 失败：0
- 跳过：1

## 用例结果

| case_id                  | status              | passed | plan_tools                                                                       | warnings                                                                                                                     | error |
| ------------------------ | ------------------- | ------ | -------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------- | ----- |
| direct_ward_round_qc     | completed           | 是     | get_record_context, select_record_documents, resolve_rule_scope, run_document_qc | 10 条规则因执行边界限制被跳过                                                                                                |       |
| explicit_rule_id_qc      | completed           | 是     | get_record_context, select_record_documents, resolve_rule_scope, run_document_qc | 已识别显式 rule_ids，将优先按 rule_ids 执行或跳过                                                                            |       |
| unsupported_write_intent | unsupported         | 是     |                                                                                  | 当前受控 Agent 不支持写入、删除、导出或持久化类操作                                                                          |       |
| discharge_record_qc      | completed           | 是     | get_record_context, select_record_documents, resolve_rule_scope, run_document_qc | 11 条规则因执行边界限制被跳过                                                                                                |       |
| vague_request            | needs_clarification | 是     |                                                                                  | 未识别到明确文书类型，请说明查房记录、病程记录、出院记录或会诊记录<br>needs_clarification 在病历不明确或文书缺失时允许通过。 |       |
| patient_search_qc        | skipped             | 是     |                                                                                  | 未提供 --patient-name 和 --department，跳过搜索类测试。                                                                      |       |

## 安全说明

- 脚本不导入 MedQC 后端 app 包，只作为外部 HTTP client 调用 QC Agent chat API。
- token 仅从 MEDQC_ACCESS_TOKEN 环境变量读取，报告和控制台都不输出 token。
- JSON/Markdown 报告只保存裁剪后的响应摘要，不保存完整 API 响应。
- 每个用例都会递归扫描 sensitive keys：medical_text、record_content、documents、bundle、structured_context、prompt、examples、internal_data、raw_llm_output。
- 当前 Pi 包用于独立测试环境校验；由于 Pi Agent API 尚未接入生产后端，本轮编排模式为 requests_fallback。
