# 正式质控 confirmed 准入收紧与证据补强报告

## 结论

- 三病历基线 confirmed/data_gap/rejected/technical：{'confirmed_defect': 6, 'data_quality_gap': 19, 'rejected_by_system': 20, 'technical_error_internal': 0}
- 收紧后 confirmed/data_gap/rejected/technical：{'confirmed_defect': 2, 'data_quality_gap': 21, 'rejected_by_system': 22, 'technical_error_internal': 0}
- guardrail 降级 confirmed 数量：4
- 本轮不改主规则口径、不增加规则数量；只收紧 confirmed 终态和补强 evidence_payload 上下文。

## Guardrail 规则

- confirmed_defect 必须有 adjudicator_reason 和足够 supporting_quote。
- 仅凭“未见/缺失/未提供”不能 confirmed，除非 evidence 能证明相关证据域完整覆盖。
- SC-083 需要手术等级 + MDT/多学科覆盖证据；SC-019 需要院外/入院前辅助检查触发 + 入院记录转录上下文；SC-100 需要植入物 + 条码/追溯码记录域。

## SC-083 / SC-019 / SC-100 补强点

- SC-083：补充手术等级、术前讨论参与人员、会诊/MDT 相关摘要，避免只凭参与人员判缺陷。
- SC-019：补充入院记录辅助检查、首次病程诊断依据、原始检查/检验报告摘要，避免只凭空字段判缺陷。
- SC-100：补充植入物/耗材、条形码/追溯码、费用/医嘱/执行对照，避免只凭植入物存在判条码缺失。

## 重点条目

| visit_id | rule_id | before             | after              | guardrail | reason                                                                                             |
| -------- | ------- | ------------------ | ------------------ | --------- | -------------------------------------------------------------------------------------------------- |
| 1915580  | SC-083  | confirmed_defect   | data_quality_gap   | True      | confirmed_defect 缺少二审 adjudicator_reason，不能作为正式确认缺陷。                               |
| 1915580  | SC-100  | data_quality_gap   | data_quality_gap   | False     | 已在 fast_screen evidence_payload 增加植入物、条形码/追溯码、耗材/费用/医嘱对照上下文。            |
| 2287309  | SC-019  | confirmed_defect   | data_quality_gap   | True      | SC-019 确认缺陷需要结构化 formal_evidence_coverage；当前结果缺少证据覆盖标记，不能直接 confirmed。 |
| 2287309  | SC-100  | rejected_by_system | rejected_by_system | False     | 已在 fast_screen evidence_payload 增加植入物、条形码/追溯码、耗材/费用/医嘱对照上下文。            |
| 2287309  | SC-097  | confirmed_defect   | rejected_by_system | True      | confirmed_defect 缺少足够长度的 adjudicator_supporting_quote，不能证明规则核心要件。               |
| 2287309  | SC-108  | confirmed_defect   | rejected_by_system | True      | confirmed_defect 缺少足够长度的 adjudicator_supporting_quote，不能证明规则核心要件。               |

## Sheet2 影响

- 本轮只处理正式 final fast_screen_full 结果准入和证据组织，不修改 Sheet2 acceptance package。
- Sheet2 目标统计仍应保持 exact_confirmed=156 / blocked_with_reason=102 / skip=25 / needs_exact_review=0。
