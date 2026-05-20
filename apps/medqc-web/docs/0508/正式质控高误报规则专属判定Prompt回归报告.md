# 正式质控高误报规则专属判定Prompt回归报告

生成时间：2026-05-21 07:55:48
运行模型：provider=`alibaba`，model=`qwen3.5-35b-a3b`。

## 改动范围

- 新增规则级判定标准版本：`formal_high_false_positive_rule_criteria_v1`。
- 覆盖规则：SC-012、SC-013、SC-034、SC-118、SC-121、SC-122、SC-123。
- 一审 fast_screen_full 规则卡片注入 required_document / required_section / required_fields 与候选召回 guidance，避免把 confirmed 条件当作提前消灭候选的硬过滤。
- 二审 adjudicator payload 同步携带 rule_specific_criteria，并要求优先遵守规则专属判定标准。
- 保留 SC-083 / SC-099 / SC-123 applicability gate，不开放程序化 confirmed。

## A/B 结果

| 指标                            | baseline（三门控+二审补裁） | after（规则专属 Prompt） |
| ------------------------------- | --------------------------: | -----------------------: |
| completed_visit_count           |                          10 |                        8 |
| confirmed_defect                |                           7 |                       11 |
| confirmed_keep                  |                           2 |                        4 |
| keep_rate                       |                       28.6% |                    36.4% |
| downgrade_to_data_gap           |                           4 |                        5 |
| downgrade_to_rejected_by_system |                           1 |                        2 |
| data_quality_gap                |                          84 |                       72 |
| rejected_by_system              |                          64 |                       60 |
| total_tokens                    |                      660443 |                   652433 |
| average_wall_clock_time         |                      34.353 |                   55.332 |

## 稳定性

- pack_concurrency=4；after 实际完成 8/10 份。
- provider_error=0；connection=0；upstream=0；parse=0；timeout=0；rate_limit=0；technical=5。
- stability_pass=否。
- 若未完成 10/10，后续质量指标只作为已完成样本的局部观察，不作为 random10 整体质量结论。

## 技术异常定位

- technical_error_diagnostics：{"technical_error_internal_count": 5, "reason_counts": {"adjudicator_missing_rule_output_after_retry: 正式质控二审补裁后仍缺少该规则裁决，进入内部技术异常。": 5}, "rule_ids": ["SC-036", "SC-076", "SC-097", "SC-099", "SC-110"], "visit_ids": ["2263802"]}。
- 本轮停止点为 2263802；technical rule_ids=['SC-036', 'SC-076', 'SC-097', 'SC-099', 'SC-110']。
- 本轮没有 provider/connection/upstream/parse/timeout/rate_limit 错误；停止原因是二审补裁后仍缺少部分规则裁决，进入 technical_error_internal。
- SC-146 在本轮已不再是停止点；下一步应治理当前停止 visit 的二审 missing-rule 完整性，而不是扩大到 20 份。

## 质量复核

- after confirmed review counts：{"downgrade_to_rejected_by_system": 2, "downgrade_to_data_gap": 5, "keep": 4}。
- covered rule criteria rows：{"SC-118": 8, "SC-123": 8, "SC-121": 8, "SC-034": 2, "SC-013": 1}。
- confirmed 收缩率=-57.1%；over_conservative_risk=否。

## 被压掉 confirmed 复核

- baseline confirmed 中 after 不再 confirmed：6 条。

| visit_id | 患者   | 规则   | baseline复核                    | after状态           | 风险说明                                                      |
| -------- | ------ | ------ | ------------------------------- | ------------------- | ------------------------------------------------------------- |
| 2262370  | 李昭云 | SC-118 | keep                            | rejected_by_system  | baseline人工复核建议保留，after被压掉，需人工确认是否过度保守 |
| 1962863  | 王良友 | SC-013 | downgrade_to_rejected_by_system | not_in_issue_review | baseline人工复核已建议降级，after压掉方向基本合理             |
| 2048454  | 陈祖佑 | SC-012 | downgrade_to_data_gap           | not_in_issue_review | baseline人工复核已建议降级，after压掉方向基本合理             |
| 2083787  | 付学云 | SC-013 | downgrade_to_data_gap           | not_in_issue_review | baseline人工复核已建议降级，after压掉方向基本合理             |
| 2328501  | 余菊芳 | SC-121 | keep                            | not_in_issue_review | baseline人工复核建议保留，after被压掉，需人工确认是否过度保守 |
| 2262981  | 屈义田 | SC-013 | downgrade_to_data_gap           | not_in_issue_review | baseline人工复核已建议降级，after压掉方向基本合理             |

## 重点样本

| visit_id | 规则   | after状态           | baseline复核 | 说明                                                          |
| -------- | ------ | ------------------- | ------------ | ------------------------------------------------------------- |
| 2262370  | SC-118 | rejected_by_system  | keep         | baseline人工复核建议保留，after被压掉，需人工确认是否过度保守 |
| 2328501  | SC-121 | not_in_issue_review | keep         | baseline人工复核建议保留，after被压掉，需人工确认是否过度保守 |

## 结论

- 本轮稳定性未通过，不做质量扩大结论。
- after 只完成部分样本，confirmed keep rate 不能用于判断规则专属 Prompt 的整体效果；需先治理 technical/provider 稳定性后再恢复同一 random10。
- 若仍未达标，优先继续治理 SC-105、SC-004、SC-015、SC-081、SC-050、SC-125。
- 未触碰 Sheet2 链路，本轮不跑 Sheet2 regression。
