# 客户样本内涵性质控点 not_returned 根因分析报告

## 结论摘要

- 分析样本数：20。
- 根因分布：`{"evidence_matrix_gap": 2, "gate_rejected": 2, "rule_not_in_formal_84": 9, "same_family_rule_returned": 7}`。
- not_returned 根因分布：`{"rule_not_in_formal_84": 9, "same_family_rule_returned": 7}`。
- 优先级分布：`{"P0": 19, "P1": 1}`。

## 关键发现

- 规则不在正式 84 条：9 条。
- 同族/相邻规则已返回但目标规则未进入终态：7 条。
- gate/guardrail 驳回：2 条。
- 真正需要按漏召回/误驳回治理：0 条。
- 受上一轮 replay 只保存 terminal rows 影响，仍需 raw dump 才能最终确认 compliant/not_applicable/raw 缺失的诊断盲区：7 条。

## 回答问题

1. 20 条中 not_returned 的真实根因分布：见 `not_returned 根因分布`。多数不是 provider 或 parse 问题，而是同族返回/规则映射/回放脚本未保存非终态结果导致。
2. 规则不在正式 84 条或映射不一致：见 `rule_not_in_formal_84` 明细，重点关注 LXE 扩展规则或 Sheet2 映射到非正式规则的样本。
3. 候选召回/pack selection 问题：现有正式 full pack 中目标规则通常有 pack 定义；但上一轮产物未保留 full raw results，不能直接证明 pack 未跑，需下一轮 raw dump。
4. 同族规则返回但脚本误判：`same_family_rule_returned` 表示同 visit 同 pack/family 有其他终态结果，目标规则可能被判 compliant/not_applicable 后未保存，或 Sheet2 映射需调整。
5. gate/guardrail 过度拦截：当前只在目标规则已有终态时可识别，SC-083 等需结合 customer policy 和 gate metadata 复核。
6. 真正正式链路漏召回：本轮现有产物不能直接证明 `true_miss`；所有疑似漏召回需先补目标规则 full raw/adjudicated 状态再判。

## P0 下一步

- 修改客户样本回放诊断脚本：每个 sample 必须保存目标 rule 的 raw_status、first_pass_display_status、postprocess 状态、adjudicator 状态，即使最终是 compliant/not_applicable。
- 对 `same_family_rule_returned` 样本复核 Sheet2 映射：确认应看目标规则、同族规则，还是客户人工问题超出正式规则 scope。
- 对 SC-083 gate 驳回样本和 1-3 条 `same_family_rule_returned` 样本做定向 dry-run，保留完整 prompt hash、targeted evidence matrix 和二审理由。

## P1 下一步

- 对非正式规则或 LXE 扩展规则，明确是否纳入正式 84 条或从准确率母集剔除。
- 对 evidence matrix gap 样本补充源文书/bundle 字段后再回归。

## 是否建议客户机冒烟

- 不建议。当前多数问题是未召回/诊断脚本观测不足，尚不能证明正式链路对客户内涵 exact 样本稳定可演示。

## P0 规则分布

- SC-036: 3
- SC-083: 2
- SC-080: 2
- SC-082: 2
- LXE-18: 2
- SC-070: 1
- SC-146: 1
- SC-008: 1
- SC-116: 1
- SC-009: 1
- SC-048: 1
- SC-021: 1
- SC-023: 1
