# 正式质控高误报规则专属判定Prompt回归报告

生成时间：2026-05-21 00:14:09
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
| completed_visit_count           |                          10 |                        1 |
| confirmed_defect                |                           7 |                        4 |
| confirmed_keep                  |                           2 |                        3 |
| keep_rate                       |                       28.6% |                    75.0% |
| downgrade_to_data_gap           |                           4 |                        1 |
| downgrade_to_rejected_by_system |                           1 |                        0 |
| data_quality_gap                |                          84 |                       10 |
| rejected_by_system              |                          64 |                        6 |
| total_tokens                    |                      660443 |                    83738 |
| average_wall_clock_time         |                      34.353 |                    53.86 |

## 稳定性

- provider_error=1；connection=0；upstream=0；parse=0；timeout=0；rate_limit=0；technical=2。
- stability_pass=否。
- after 实际完成 1/10 份；若未完成 10/10，后续质量指标只作为已完成样本的局部观察，不作为 random10 整体质量结论。

## 技术异常定位

- technical_error_diagnostics：{"technical_error_internal_count": 2, "reason_counts": {"provider、批量解析或 pack 执行异常，仅进入内部诊断，不作为医生缺陷。": 2}, "rule_ids": ["SC-146"], "visit_ids": ["2013648"]}。
- 本轮停止点为 2013648 / SC-146。SC-146 单规则 pack 已启用严格 JSON prompt，但本次 random10 中该 pack 在 2 次 parse_error retry 后仍未恢复，missing_rule_ids=['SC-146']，因此按稳定性门禁停止后续样本。
- 该结果说明 088368cdb 的定向 3/3 completed 不能完全覆盖 random10 运行态波动；下一步应继续治理 SC-146 单规则 pack 的随机稳定性，而不是扩大到 20 份。

## 质量复核

- after confirmed review counts：{"keep": 3, "downgrade_to_data_gap": 1}。
- covered rule criteria rows：{"SC-118": 1, "SC-123": 1, "SC-121": 1, "SC-122": 1}。
- confirmed 收缩率=42.9%；over_conservative_risk=否。

## 被压掉 confirmed 复核

- baseline confirmed 中 after 不再 confirmed：7 条。

| visit_id | 患者   | 规则   | baseline复核                    | after状态           | 风险说明                                                      |
| -------- | ------ | ------ | ------------------------------- | ------------------- | ------------------------------------------------------------- |
| 2262370  | 李昭云 | SC-118 | keep                            | not_in_issue_review | baseline人工复核建议保留，after被压掉，需人工确认是否过度保守 |
| 1962863  | 王良友 | SC-013 | downgrade_to_rejected_by_system | not_in_issue_review | baseline人工复核已建议降级，after压掉方向基本合理             |
| 2048454  | 陈祖佑 | SC-012 | downgrade_to_data_gap           | not_in_issue_review | baseline人工复核已建议降级，after压掉方向基本合理             |
| 2048454  | 陈祖佑 | SC-121 | downgrade_to_data_gap           | not_in_issue_review | baseline人工复核已建议降级，after压掉方向基本合理             |
| 2083787  | 付学云 | SC-013 | downgrade_to_data_gap           | not_in_issue_review | baseline人工复核已建议降级，after压掉方向基本合理             |
| 2328501  | 余菊芳 | SC-121 | keep                            | not_in_issue_review | baseline人工复核建议保留，after被压掉，需人工确认是否过度保守 |
| 2262981  | 屈义田 | SC-013 | downgrade_to_data_gap           | not_in_issue_review | baseline人工复核已建议降级，after压掉方向基本合理             |

## 重点样本

| visit_id | 规则   | after状态           | baseline复核 | 说明                                                          |
| -------- | ------ | ------------------- | ------------ | ------------------------------------------------------------- |
| 2262370  | SC-118 | not_in_issue_review | keep         | baseline人工复核建议保留，after被压掉，需人工确认是否过度保守 |
| 2328501  | SC-121 | not_in_issue_review | keep         | baseline人工复核建议保留，after被压掉，需人工确认是否过度保守 |

## 结论

- 本轮稳定性未通过，不做质量扩大结论。
- after 只完成部分样本，confirmed keep rate 不能用于判断规则专属 Prompt 的整体效果；需先治理 technical/provider 稳定性后再恢复同一 random10。
- 若仍未达标，优先继续治理 SC-105、SC-004、SC-015、SC-081、SC-050、SC-125。
- 未触碰 Sheet2 链路，本轮不跑 Sheet2 regression。
