# 正式质控小模型结构化证据 POC 三轮收口报告

生成时间：2026-05-14 22:41:05

## POC 范围

- 只读运行，不接页面，不写正式质控业务表，不改 Sheet2 验收链路。
- evidence package：`surgery_pathology_implant_evidence`、`abnormal_result_followup_evidence`、`consultation_implementation_evidence`。
- 小模型只抽取 evidence package；审核模型只基于 evidence package + coverage flags 输出四层终态。
- 本轮采用结构化强证据优先：植入物/耗材触发必须来自结构化表/字段或明确“植入/置入/使用 + 材料 + 数量”操作语句；样本文本词表仅作为 weak hint，不作为正式规则依据。
- v3 修复 trigger absent 优先级：extractor/coverage 已给出 absent 时，弱触发词不得覆盖 absent；SC-036/SC-101 gate 驳回必须保留可审计引用。

## 稳定性与解析

- visit 数：10；issue 决策数：50。
- 小模型 JSON 解析成功率：96.67%。
- extractor_provider_error=0，extractor_timeout=0，extractor_parse_error=1。
- adjudicator_provider_error=0，adjudicator_timeout=0，adjudicator_parse_error=0。
- absent_trigger_data_gap_count=0。
- rejected_without_supporting_quote_count（SC-036/SC-101）=0。

## Baseline 对比

- baseline_total_tokens=608247；poc_total_tokens=168862；token_delta=439385。
- 注意：baseline_total_tokens 来自正式 84 条全量链路，POC 只覆盖 5 条规则/3 个 evidence package，二者不是同口径 token 对比，只作为成本背景。
- baseline_wall_clock_time=320.585s；poc_wall_clock_time=351.541s。
- baseline_display_status_counts=`{"confirmed_defect": 14, "data_quality_gap": 85, "rejected_by_system": 44}`。
- baseline_target_rule_display_status_counts=`{"confirmed_defect": 2, "data_quality_gap": 8, "rejected_by_system": 7}`。
- poc_display_status_counts=`{"data_quality_gap": 19, "rejected_by_system": 31}`。

## 同规则族分布

- baseline 目标规则 issue 数：17。
- baseline 目标规则按 rule 分布：`{"SC-036": {"confirmed_defect": 1, "data_quality_gap": 4, "rejected_by_system": 2}, "SC-070": {"data_quality_gap": 1}, "SC-099": {"confirmed_defect": 1, "data_quality_gap": 1, "rejected_by_system": 3}, "SC-100": {"data_quality_gap": 1, "rejected_by_system": 2}, "SC-101": {"data_quality_gap": 1}}`。
- POC 同规则网格决策分布：`{"data_quality_gap": 19, "rejected_by_system": 31}`。

## POC 结论

- 本轮 POC 证明结构化证据分流有价值，但 token 与 84 条 baseline 非同口径；继续扩大前需要同规则族成本评估和人工抽样复核。

## 分病历摘要

| visit_id | patient | wall(s) | extractor_calls | adjudicator_calls | tokens | confirmed | data_gap | rejected | parse_errors |
| -------- | ------- | ------: | --------------: | ----------------: | -----: | --------: | -------: | -------: | -----------: |
| 1915580  | 雷德超  |   35.47 |               3 |                 3 |  15133 |         0 |        3 |        2 |            0 |
| 2024757  | 游德利  |   31.82 |               3 |                 3 |  17745 |         0 |        1 |        4 |            0 |
| 2287309  | 陈光华  |   43.02 |               3 |                 3 |  18922 |         0 |        2 |        3 |            0 |
| 2246915  | 黄金莲  |   37.94 |               3 |                 3 |  19847 |         0 |        4 |        1 |            0 |
| 1883111  | 马章媛  |   29.46 |               3 |                 3 |  14484 |         0 |        0 |        5 |            0 |
| 1966656  | 周光容  |   27.38 |               3 |                 3 |  14055 |         0 |        3 |        2 |            0 |
| 2311318  | 范永勤  |   38.51 |               3 |                 3 |  18317 |         0 |        3 |        2 |            0 |
| 2207717  | 邹才林  |   30.94 |               3 |                 3 |  18273 |         0 |        1 |        4 |            0 |
| 1870471  | 蒲云鹏  |   45.86 |               3 |                 3 |  16835 |         0 |        1 |        4 |            1 |
| 2268187  | 代云聪  |   31.15 |               3 |                 3 |  15251 |         0 |        1 |        4 |            0 |

## confirmed_defect 明细

## 是否值得扩大

- 建议先做同规则族成本评估和 POC issue 抽样复核，再决定是否接入更多规则族；本 POC 不改变正式主链路。
