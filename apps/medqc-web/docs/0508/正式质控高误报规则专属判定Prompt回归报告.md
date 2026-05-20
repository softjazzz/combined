# 正式质控高误报规则专属判定Prompt回归报告

生成时间：2026-05-20 23:06:58
运行模型：provider=`alibaba`，model=`qwen3.5-35b-a3b`。

## 改动范围

- 新增规则级判定标准版本：`formal_high_false_positive_rule_criteria_v1`。
- 覆盖规则：SC-012、SC-013、SC-034、SC-118、SC-121、SC-122、SC-123。
- 一审 fast_screen_full 规则卡片注入 required_document / required_section / required_fields 与候选召回 guidance，避免把 confirmed 条件当作提前消灭候选的硬过滤。
- 二审 adjudicator payload 同步携带 rule_specific_criteria，并要求优先遵守规则专属判定标准。
- 保留 SC-083 / SC-099 / SC-123 applicability gate，不开放程序化 confirmed。

## A/B 结果

> 注意：after 本轮只完成 1/10（2013648）即因技术稳定性门禁失败停止，以下 after 数字仅为部分运行诊断，不构成有效质量 A/B 结论，不能用于判断 keep rate 已达标。

| 指标                            | baseline（三门控+二审补裁） | after（规则专属 Prompt） |
| ------------------------------- | --------------------------: | -----------------------: |
| confirmed_defect                |                           7 |                        2 |
| confirmed_keep                  |                           2 |                        2 |
| keep_rate                       |                       28.6% |                   100.0% |
| downgrade_to_data_gap           |                           4 |                        0 |
| downgrade_to_rejected_by_system |                           1 |                        0 |
| data_quality_gap                |                          84 |                        8 |
| rejected_by_system              |                          64 |                        7 |
| total_tokens                    |                      660443 |                    79002 |
| average_wall_clock_time         |                      34.353 |                   52.819 |

## 稳定性

- provider_error=1；connection=0；upstream=0；parse=0；timeout=0；rate_limit=0；technical=2。
- stability_pass=否。
- 失败集中在 2013648 / SC-146 单规则 pack，模型返回有 token，但 pack 重试后仍进入 technical_error_internal；这属于一审 pack 输出稳定性问题，不是 SC-118 / SC-121 规则专属 Prompt 的质量结论。

## 质量复核

- after confirmed review counts：{"keep": 2}。
- covered rule criteria rows：{"SC-118": 1, "SC-123": 1, "SC-121": 1}。
- confirmed 收缩率=71.4%；over_conservative_risk=是。
- 由于 after 未完成 10/10，`keep_rate=100%` 仅代表 2013648 局部结果，不可作为扩大到 20 份或页面演示依据。

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
- 不建议扩大到 20 份，不建议页面演示。
- 需要先收口 qwen3.5 下 SC-146 / consistency_cross_doc 单规则 pack 输出稳定性，再恢复同一 random10 A/B。
- 若仍未达标，优先继续治理 SC-105、SC-004、SC-015、SC-081、SC-050、SC-125。
- 未触碰 Sheet2 链路，本轮不跑 Sheet2 regression。
