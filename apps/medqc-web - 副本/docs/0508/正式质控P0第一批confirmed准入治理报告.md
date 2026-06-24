# 正式质控 P0 第一批 confirmed 准入治理报告

生成时间：2026-05-21 22:03:41

## 范围

- 本轮治理规则：SC-015、SC-018、SC-047、SC-036、SC-050、SC-105、SC-121、SC-125。
- 生产链路保持双模型：一审 qwen3.5-35b-a3b，二审 qwen3.6-35b-a3b。
- 不写正式 QC 结果表，不扩大到 20 份，不改页面。
- 已有 SC-083 / SC-099 / SC-123 applicability gate 不回退，且不允许程序化 confirmed。

## 子 Agent 分工结论摘要

- A（SC-015/SC-018）：入院记录类必须依赖性别/年龄/指定段落/查体矩阵；“详见专科检查”和“具体不详”类边界不直接 confirmed。
- B（SC-047/SC-036）：诊断修正必须先证明修正/补充诊断动作；异常检查必须有异常报告、后续病程和处理意见时间线。
- C（SC-050/SC-105）：上级查房和术后首次病程必须使用完整文书字段矩阵，短片段不得 confirmed。
- D（SC-121/SC-125）：出院诊疗经过需完整出院记录上下文；诊断错填/漏填/顺序错误需诊断矩阵和客观对照。

## 规则准入标准

- SC-015：性别/年龄/个人史/婚育史/月经史/家族史矩阵；男性月经史不适用；“具体不详”客户口径未确认前转 data_quality_gap。
- SC-018：必须有主诉/诊断或部位、一般查体、专科/局部查体；只有“详见专科检查”转 data_quality_gap。
- SC-047：无诊断修正/补充/调整动作直接 rejected_by_system；有动作但缺时间/前后诊断/邻近病程转 data_quality_gap。
- SC-036：异常报告 + 后续病程 + 处理/分析对照；仅“辅助检查同前”转 data_quality_gap。
- SC-050：查房时间、医师级别、病情分析、诊疗意见矩阵；有分析和意见则 rejected_by_system。
- SC-105：术后首次病程字段矩阵；缺完整正文转 data_quality_gap，字段明确缺项才保留 confirmed 候选。
- SC-121：完整出院记录诊疗经过和必要跨文书对照；短句或截断上下文转 data_quality_gap。
- SC-125：入院/出院/死亡诊断矩阵和客观对照；仅主观认为顺序应调整转 rejected_by_system。

## A/B 结果

- baseline confirmed_defect：5，keep：2/5，keep rate：40.0%
- after confirmed_defect：3，keep：2/3，keep rate：66.7%
- after data_quality_gap：96
- after rejected_by_system：86
- P0 规则 after confirmed 条数：3

## 稳定性

- completed_visit_count：10/10
- provider_error：0
- provider_connection_error：0
- upstream_http_error：0
- parse_error：0
- timeout：0
- rate_limit：0
- technical_error_internal：0
- total_tokens：748585
- average_wall_clock_time：45.55s
- 稳定性结论：通过

## 结论

- confirmed keep rate 高于治理前基线，P0 第一批准入治理有效。
- keep rate 仍未达到 70%，建议继续针对剩余失败规则做小批治理，不直接扩大样本。
