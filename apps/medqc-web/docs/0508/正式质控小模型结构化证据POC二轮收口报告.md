# 正式质控小模型结构化证据 POC 二轮收口报告

生成时间：2026-05-14 21:46:58

## POC 范围

- 只读运行，不接页面，不写正式质控业务表，不改 Sheet2 验收链路。
- evidence package：`surgery_pathology_implant_evidence`、`abnormal_result_followup_evidence`、`consultation_implementation_evidence`。
- 小模型只抽取 evidence package；审核模型只基于 evidence package + coverage flags 输出四层终态。
- 本轮采用结构化强证据优先：植入物/耗材触发必须来自结构化表/字段或明确“植入/置入/使用 + 材料 + 数量”操作语句；样本文本词表仅作为 weak hint，不作为正式规则依据。

## 稳定性与解析

- visit 数：10；issue 决策数：50。
- 小模型 JSON 解析成功率：96.67%。
- extractor_provider_error=0，extractor_timeout=0，extractor_parse_error=1。
- adjudicator_provider_error=0，adjudicator_timeout=0，adjudicator_parse_error=0。

## Baseline 对比

- baseline_total_tokens=608247；poc_total_tokens=167467；token_delta=440780。
- 注意：baseline_total_tokens 来自正式 84 条全量链路，POC 只覆盖 5 条规则/3 个 evidence package，二者不是同口径 token 对比，只作为成本背景。
- baseline_wall_clock_time=320.585s；poc_wall_clock_time=351.556s。
- baseline_display_status_counts=`{"confirmed_defect": 14, "data_quality_gap": 85, "rejected_by_system": 44}`。
- baseline_target_rule_display_status_counts=`{"confirmed_defect": 2, "data_quality_gap": 8, "rejected_by_system": 7}`。
- poc_display_status_counts=`{"data_quality_gap": 26, "rejected_by_system": 24}`。

## 同规则族分布

- baseline 目标规则 issue 数：17。
- baseline 目标规则按 rule 分布：`{"SC-036": {"confirmed_defect": 1, "data_quality_gap": 4, "rejected_by_system": 2}, "SC-070": {"data_quality_gap": 1}, "SC-099": {"confirmed_defect": 1, "data_quality_gap": 1, "rejected_by_system": 3}, "SC-100": {"data_quality_gap": 1, "rejected_by_system": 2}, "SC-101": {"data_quality_gap": 1}}`。
- POC 同规则网格决策分布：`{"data_quality_gap": 26, "rejected_by_system": 24}`。

## POC 结论

- 本轮 POC 证明结构化证据分流有价值，但 token 与 84 条 baseline 非同口径；继续扩大前需要同规则族成本评估和人工抽样复核。

## 分病历摘要

| visit_id | patient | wall(s) | extractor_calls | adjudicator_calls | tokens | confirmed | data_gap | rejected | parse_errors |
| -------- | ------- | ------: | --------------: | ----------------: | -----: | --------: | -------: | -------: | -----------: |
| 1915580  | 雷德超  |   34.34 |               3 |                 3 |  15008 |         0 |        3 |        2 |            0 |
| 2024757  | 游德利  |   35.26 |               3 |                 3 |  18000 |         0 |        3 |        2 |            0 |
| 2287309  | 陈光华  |   39.77 |               3 |                 3 |  18374 |         0 |        2 |        3 |            0 |
| 2246915  | 黄金莲  |   39.46 |               3 |                 3 |  20028 |         0 |        3 |        2 |            0 |
| 1883111  | 马章媛  |   28.75 |               3 |                 3 |  14495 |         0 |        2 |        3 |            0 |
| 1966656  | 周光容  |   26.12 |               3 |                 3 |  14125 |         0 |        3 |        2 |            0 |
| 2311318  | 范永勤  |   41.82 |               3 |                 3 |  18547 |         0 |        3 |        2 |            0 |
| 2207717  | 邹才林  |   28.20 |               3 |                 3 |  17567 |         0 |        3 |        2 |            0 |
| 1870471  | 蒲云鹏  |   44.48 |               3 |                 3 |  15939 |         0 |        1 |        4 |            1 |
| 2268187  | 代云聪  |   33.34 |               3 |                 3 |  15384 |         0 |        3 |        2 |            0 |

## confirmed_defect 明细

## 是否值得扩大

- 建议先做同规则族成本评估和 POC issue 抽样复核，再决定是否接入更多规则族；本 POC 不改变正式主链路。
