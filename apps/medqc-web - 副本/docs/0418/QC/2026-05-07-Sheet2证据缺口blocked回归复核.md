# Sheet2 证据缺口 blocked 回归复核

日期：2026-05-07

## 结论

- 本轮复核 blocked 候选：45 条。
- `blocked -> exact_confirmed`：0 条；本轮不把 bundle covered 直接包装成 exact。
- blocked 原因更新：31 条。
- `needs_exact_review`：保持 0。

## 分类统计

| coverage_status                | count |
| ------------------------------ | ----: |
| not_in_repaired_evidence_scope |    14 |
| still_evidence_gap             |    22 |
| evidence_chain_recovered       |     9 |

## 本轮写回行

| row          | rule   | action                            | reason                                                                                                                                                      |
| ------------ | ------ | --------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Sheet2-R0031 | CL-275 | keep_blocked_with_specific_gap    | 仍缺少可进入样本验证页的关键证据域：consultation_record                                                                                                     |
| Sheet2-R0053 | SC-009 | keep_blocked_with_specific_gap    | 仍缺少可进入样本验证页的关键证据域：exam_item_report                                                                                                        |
| Sheet2-R0056 | SC-105 | keep_blocked_with_specific_gap    | 仍缺少可进入样本验证页的关键证据域：surgery_record、mr_surgery                                                                                              |
| Sheet2-R0066 | SC-020 | keep_blocked_move_to_rule_backlog | 本轮已补齐并验证所需 CDM/bundle 证据域，缺口不再是源文书缺失；但尚未取得与人工问题核心锚点等价的规则/LLM 命中，保持 blocked_with_reason，进入定向规则重放。 |
| Sheet2-R0073 | SC-023 | keep_blocked_move_to_rule_backlog | 本轮已补齐并验证所需 CDM/bundle 证据域，缺口不再是源文书缺失；但尚未取得与人工问题核心锚点等价的规则/LLM 命中，保持 blocked_with_reason，进入定向规则重放。 |
| Sheet2-R0077 | SC-074 | keep_blocked_move_to_rule_backlog | 本轮已补齐并验证所需 CDM/bundle 证据域，缺口不再是源文书缺失；但尚未取得与人工问题核心锚点等价的规则/LLM 命中，保持 blocked_with_reason，进入定向规则重放。 |
| Sheet2-R0093 | SC-105 | keep_blocked_move_to_rule_backlog | 本轮已补齐并验证所需 CDM/bundle 证据域，缺口不再是源文书缺失；但尚未取得与人工问题核心锚点等价的规则/LLM 命中，保持 blocked_with_reason，进入定向规则重放。 |
| Sheet2-R0096 | SC-097 | keep_blocked_with_specific_gap    | 仍缺少可进入样本验证页的关键证据域：surgery_record、mr_surgery                                                                                              |
| Sheet2-R0098 | SC-023 | keep_blocked_move_to_rule_backlog | 本轮已补齐并验证所需 CDM/bundle 证据域，缺口不再是源文书缺失；但尚未取得与人工问题核心锚点等价的规则/LLM 命中，保持 blocked_with_reason，进入定向规则重放。 |
| Sheet2-R0107 | SC-146 | keep_blocked_with_specific_gap    | 仍缺少可进入样本验证页的关键证据域：exam_item_report、surgery_record、mr_surgery                                                                            |
| Sheet2-R0109 | SC-032 | keep_blocked_with_specific_gap    | 仍缺少可进入样本验证页的关键证据域：labtest_item_report                                                                                                     |
| Sheet2-R0117 | SC-033 | keep_blocked_move_to_rule_backlog | 本轮已补齐并验证所需 CDM/bundle 证据域，缺口不再是源文书缺失；但尚未取得与人工问题核心锚点等价的规则/LLM 命中，保持 blocked_with_reason，进入定向规则重放。 |
| Sheet2-R0122 | SC-023 | keep_blocked_with_specific_gap    | 仍缺少可进入样本验证页的关键证据域：exam_item_report                                                                                                        |
| Sheet2-R0132 | SC-023 | keep_blocked_move_to_rule_backlog | 本轮已补齐并验证所需 CDM/bundle 证据域，缺口不再是源文书缺失；但尚未取得与人工问题核心锚点等价的规则/LLM 命中，保持 blocked_with_reason，进入定向规则重放。 |
| Sheet2-R0150 | LX-016 | keep_blocked_with_specific_gap    | 仍缺少可进入样本验证页的关键证据域：consultation_record                                                                                                     |
| Sheet2-R0159 | SC-097 | keep_blocked_with_specific_gap    | 仍缺少可进入样本验证页的关键证据域：surgery_record、mr_surgery                                                                                              |
| Sheet2-R0171 | SC-069 | keep_blocked_with_specific_gap    | 仍缺少可进入样本验证页的关键证据域：consultation_record                                                                                                     |
| Sheet2-R0191 | SC-097 | keep_blocked_with_specific_gap    | 仍缺少可进入样本验证页的关键证据域：surgery_record、mr_surgery                                                                                              |
| Sheet2-R0200 | SC-070 | keep_blocked_with_specific_gap    | 仍缺少可进入样本验证页的关键证据域：consultation_record                                                                                                     |
| Sheet2-R0205 | SC-081 | keep_blocked_with_specific_gap    | 仍缺少可进入样本验证页的关键证据域：surgery_record、mr_surgery                                                                                              |
| Sheet2-R0213 | SC-081 | keep_blocked_with_specific_gap    | 仍缺少可进入样本验证页的关键证据域：surgery_record、mr_surgery                                                                                              |
| Sheet2-R0221 | CL-275 | keep_blocked_with_specific_gap    | 仍缺少可进入样本验证页的关键证据域：consultation_record                                                                                                     |
| Sheet2-R0239 | SC-046 | keep_blocked_with_specific_gap    | 仍缺少可进入样本验证页的关键证据域：surgery_record、mr_surgery                                                                                              |
| Sheet2-R0242 | SC-036 | keep_blocked_move_to_rule_backlog | 本轮已补齐并验证所需 CDM/bundle 证据域，缺口不再是源文书缺失；但尚未取得与人工问题核心锚点等价的规则/LLM 命中，保持 blocked_with_reason，进入定向规则重放。 |
| Sheet2-R0246 | SC-083 | keep_blocked_with_specific_gap    | 仍缺少可进入样本验证页的关键证据域：consultation_record                                                                                                     |
| Sheet2-R0249 | SC-046 | keep_blocked_with_specific_gap    | 仍缺少可进入样本验证页的关键证据域：surgery_record、mr_surgery                                                                                              |
| Sheet2-R0251 | SC-097 | keep_blocked_with_specific_gap    | 仍缺少可进入样本验证页的关键证据域：surgery_record、mr_surgery                                                                                              |
| Sheet2-R0265 | SC-036 | keep_blocked_move_to_rule_backlog | 本轮已补齐并验证所需 CDM/bundle 证据域，缺口不再是源文书缺失；但尚未取得与人工问题核心锚点等价的规则/LLM 命中，保持 blocked_with_reason，进入定向规则重放。 |
| Sheet2-R0279 | SC-070 | keep_blocked_with_specific_gap    | 仍缺少可进入样本验证页的关键证据域：consultation_record                                                                                                     |
| Sheet2-R0283 | SC-036 | keep_blocked_with_specific_gap    | 仍缺少可进入样本验证页的关键证据域：consultation_record                                                                                                     |
| Sheet2-R0288 | SC-046 | keep_blocked_with_specific_gap    | 仍缺少可进入样本验证页的关键证据域：surgery_record、mr_surgery                                                                                              |
