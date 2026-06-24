# 正式质控 gate 接入后 P0 质量修复回归报告

生成时间：2026-05-19 18:10:59

## 修复内容

- P0-1：收紧 confirmed guardrail。支撑 quote 为空、过短、仅记录时间/标题/文书头/空字段时降级，不再展示为确认缺陷。
- P0-2：SC-123 gate 增加 `discharge_medication_matrix`，只在可核查出院带药药品明细且字段缺失时进入二轮。
- P0-3：SC-099 gate 增加 `pathology_linkage_context`，要求手术取材/送病理 quote 与病理来源 quote 可审计对照。

## A/B 对比

| 指标                            | baseline |   after |
| ------------------------------- | -------: | ------: |
| confirmed_defect                |       10 |       7 |
| confirmed_keep                  |        3 |       4 |
| confirmed_keep_rate             |    30.0% |   57.1% |
| downgrade_to_data_gap           |        5 |       3 |
| downgrade_to_rejected_by_system |        2 |       0 |
| data_quality_gap                |       73 |      74 |
| rejected_by_system              |       55 |      50 |
| total_tokens                    |   642896 |  634649 |
| average_wall_clock_time         |  32.492s | 32.567s |

## Gate 分流结论

- SC-099/SC-123 仍无程序化 confirmed，Python gate 只做适用性与证据覆盖分流。
- SC-123 已补逐药品字段矩阵，减少“没有明确出院带药却判出院带药不详细”的误判风险。
- SC-099 已补手术记录与病理来源对照 quote，缺少可审计对照时不会被程序化确认为缺陷。

## After confirmed 全量复核摘要

- after confirmed_defect=7，keep=4，keep_rate=57.1%。
- 目标 `confirmed_keep_rate >= 70%` 未达成。
- confirmed 数从 10 降到 7，误确认有所收敛，但剩余 confirmed 仍不足以支撑扩大验收或页面演示。

## 后续优先规则

下一轮不应先扩大到 20 份，应优先处理 after confirmed 涉及的规则：

- SC-105
- SC-004
- SC-015
- SC-081
- SC-050
- SC-125

这些规则需要继续区分：短证据/文书头导致的误确认、规则适用性未证明、跨文书对照不足，以及二轮 guardrail 仍偏松的场景。

## 结论

- P0 修复有效，但未达标：confirmed keep rate 从 30.0% 提升到 57.1%，仍低于 70% 目标。
- 不建议扩大到 20 份，也不建议作为正式页面演示口径。
- 下一步应继续针对 SC-105、SC-004、SC-015、SC-081、SC-050、SC-125 做规则级 evidence/gate/guardrail 收口。
- 若 confirmed 数继续下降但保留项质量提升，属于可接受方向；本阶段优先保证可展示缺陷纯度，不追求 confirmed 数量。
