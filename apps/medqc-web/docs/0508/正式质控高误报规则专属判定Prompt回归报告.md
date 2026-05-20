# 正式质控高误报规则专属判定Prompt回归报告

生成时间：2026-05-20 18:25:37

## 改动范围

- 新增规则级判定标准版本：`formal_high_false_positive_rule_criteria_v1`。
- 覆盖规则：SC-012、SC-013、SC-034、SC-118、SC-121、SC-122、SC-123。
- 一审 fast_screen_full 规则卡片注入 required_document / required_section / required_fields / confirmed / not_confirmed / data_gap 条件。
- 二审 adjudicator payload 同步携带 rule_specific_criteria，并要求优先遵守规则专属判定标准。
- 保留 SC-083 / SC-099 / SC-123 applicability gate，不开放程序化 confirmed。

## A/B 结果

| 指标                            | baseline（三门控+二审补裁） | after（规则专属 Prompt） |
| ------------------------------- | --------------------------: | -----------------------: |
| confirmed_defect                |                           7 |                        0 |
| confirmed_keep                  |                           2 |                        0 |
| keep_rate                       |                       28.6% |                     0.0% |
| downgrade_to_data_gap           |                           4 |                        0 |
| downgrade_to_rejected_by_system |                           1 |                        0 |
| data_quality_gap                |                          84 |                       84 |
| rejected_by_system              |                          64 |                       77 |
| total_tokens                    |                      660443 |                   663026 |
| average_wall_clock_time         |                      34.353 |                   35.897 |

## 稳定性

- provider_error=0；connection=0；upstream=0；parse=0；timeout=0；rate_limit=0；technical=0。
- stability_pass=是。

## 质量复核

- after confirmed review counts：{}。
- covered rule criteria rows：{"SC-013": 10, "SC-118": 8, "SC-123": 10, "SC-121": 4, "SC-012": 2, "SC-034": 4, "SC-122": 1}。
- confirmed 收缩率=100.0%；over_conservative_risk=是。

## 被压掉 confirmed 复核

- baseline confirmed 中 after 不再 confirmed：7 条。

| visit_id | 患者   | 规则   | baseline复核                    | after状态           | 风险说明                                                      |
| -------- | ------ | ------ | ------------------------------- | ------------------- | ------------------------------------------------------------- |
| 2262370  | 李昭云 | SC-118 | keep                            | not_in_issue_review | baseline人工复核建议保留，after被压掉，需人工确认是否过度保守 |
| 1962863  | 王良友 | SC-013 | downgrade_to_rejected_by_system | data_quality_gap    | baseline人工复核已建议降级，after压掉方向基本合理             |
| 2048454  | 陈祖佑 | SC-012 | downgrade_to_data_gap           | not_in_issue_review | baseline人工复核已建议降级，after压掉方向基本合理             |
| 2048454  | 陈祖佑 | SC-121 | downgrade_to_data_gap           | data_quality_gap    | baseline人工复核已建议降级，after压掉方向基本合理             |
| 2083787  | 付学云 | SC-013 | downgrade_to_data_gap           | data_quality_gap    | baseline人工复核已建议降级，after压掉方向基本合理             |
| 2328501  | 余菊芳 | SC-121 | keep                            | data_quality_gap    | baseline人工复核建议保留，after被压掉，需人工确认是否过度保守 |
| 2262981  | 屈义田 | SC-013 | downgrade_to_data_gap           | data_quality_gap    | baseline人工复核已建议降级，after压掉方向基本合理             |

## 结论

- keep rate 未达 70%，不建议扩大到 20 份；下一步继续治理剩余高误报规则。
- 若仍未达标，优先继续治理 SC-105、SC-004、SC-015、SC-081、SC-050、SC-125。
- 未触碰 Sheet2 链路，本轮不跑 Sheet2 regression。
