# 正式质控 gate 接入后 confirmed 质量根因分析报告

## 范围

- 输入：`formal_qc_gate_integrated_random10_rerun_issue_review` 与 `formal_qc_gate_integrated_random10_rerun_quality_review`。
- 方法：只读程序化聚类，不重跑正式质控，不调用 LLM，不改正式主链路。
- 样本：本轮 rerun 产生的 10 条 `confirmed_defect`。

## 总体结论

- confirmed 复核分布：keep=3，downgrade_to_data_gap=5，downgrade_to_rejected_by_system=2。
- keep 只有 3/10 的直接原因：confirmed guardrail 对短 quote、缺跨文书对照和候选 gate 后的二轮确认约束仍偏松。
- 最大误报来源：证据短片段/截断；根因分布：{"证据短片段/截断": 3, "已有 applicability gate 可覆盖": 2, "无明显误确认": 1, "LLM 语义误判": 2, "规则适用性未证明": 1, "缺跨文书对照": 1}。
- 需要收紧 confirmed guardrail：7 条；需要 evidence coverage flag：6 条；需要新增 applicability gate：1 条。
- 已有 SC-099/SC-123 gate 能覆盖但仍被二轮过度 confirmed 的样本：3 条，说明“适用性成立”仍被二轮误当“缺陷成立”。

## 规则级汇总

| rule_id | confirmed | keep | data_gap | rejected | 主要根因                       | 优先级 | 建议                                                                 |
| ------- | --------: | ---: | -------: | -------: | ------------------------------ | ------ | -------------------------------------------------------------------- |
| SC-010  |         1 |    0 |        1 |        0 | 规则适用性未证明               | P1     | 设计规则适用性 gate 或完整 evidence coverage flag。                  |
| SC-013  |         1 |    1 |        0 |        0 | 无明显误确认                   | P2     | 继续观察                                                             |
| SC-015  |         1 |    0 |        1 |        0 | 证据短片段/截断                | P1     | 收紧 confirmed guardrail，短 quote/缺对照转 data_gap。               |
| SC-099  |         1 |    0 |        1 |        0 | 证据短片段/截断                | P0     | 补 pathology/手术记录 contrast_quote 门槛，缺对照不得 confirmed。    |
| SC-105  |         2 |    0 |        1 |        1 | 证据短片段/截断                | P0     | 建立术后首次病程字段矩阵 coverage flag，空字段片段不足以 confirmed。 |
| SC-123  |         4 |    2 |        1 |        1 | 已有 applicability gate 可覆盖 | P0     | 收紧逐药品字段缺失准入，出院带药候选仍需二轮 item-level 裁决。       |

## P0 修复 Backlog

| priority | backlog                                             | target_rules                   | 验收方式                                                                                                                    |
| -------- | --------------------------------------------------- | ------------------------------ | --------------------------------------------------------------------------------------------------------------------------- |
| P0       | 收紧 confirmed guardrail：短证据/空字段片段不得确认 | SC-105, SC-010, SC-015, SC-099 | 当前 10 条回放中 evidence_too_short=true 的 confirmed 数降为 0；短 quote/记录头/空字段串统一转 data_quality_gap。           |
| P0       | SC-123 二轮准入改为逐药品字段矩阵                   | SC-123                         | 每条 confirmed 必须列出具体出院药品及缺失字段；无逐药品 quote 或仅出院建议文本时不得 confirmed。                            |
| P0       | SC-099 confirmed 需要手术记录与病理来源对照 quote   | SC-099                         | SC-099 confirmed 必须同时包含手术记录取材/送检 quote、病理来源 quote、缺失要件说明；缺 contrast_quote 转 data_quality_gap。 |

## 问题回答

1. 为什么 confirmed keep 只有 3/10？
   因为二轮 confirmed 仍允许短证据、缺跨文书对照、候选 gate 后要件不足的条目进入确认缺陷。
2. 最大误报来源是什么？
   当前最大聚类是 `证据短片段/截断`，集中体现为 quote 不能直接证明规则核心要件。
3. 哪些能通过 guardrail 收紧解决？
   SC-105、SC-010、SC-015、SC-099 的短 quote/空字段片段/缺对照问题优先通过 confirmed guardrail 拦截。
4. 哪些需要新增 applicability gate？
   入院记录病史类规则（SC-010/SC-015 等）需要先证明字段适用性与完整上下文；本轮不建议立即生产接入，应先只读回放。
5. 哪些只是 evidence/bundle 组织问题？
   SC-099 需要手术记录与 pathology 对照 quote；SC-123 需要逐药品字段矩阵；SC-105 需要术后首程字段矩阵。
6. 下一步是否应该先修 P0，再扩大到20份？
   是。稳定性已过关，但 confirmed 纯度不足；应先修 P0 guardrail/evidence coverage 后再扩大到 20 份。
7. 修完 P0 后的验收口径是什么？
   使用同一 10 份只读回放：confirmed 中 `evidence_too_short=true` 为 0，SC-099/SC-123 confirmed 必须有结构化对照 quote，confirmed keep 率应显著高于当前 3/10。

## 边界

- 本轮未改正式主链路、未注册新 gate、未调用 LLM、未重跑随机 10。
