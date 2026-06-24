# 正式质控小模型结构化证据 POC 报告

生成时间：2026-05-14 16:07:05

## POC 范围

- 只读运行，不接页面，不写正式质控业务表，不改 Sheet2 验收链路。
- evidence package：`surgery_pathology_implant_evidence`、`abnormal_result_followup_evidence`、`consultation_implementation_evidence`。
- 小模型只抽取 evidence package；审核模型只基于 evidence package + coverage flags 输出四层终态。

## 稳定性与解析

- visit 数：10；issue 决策数：50。
- 小模型 JSON 解析成功率：96.67%。
- extractor_provider_error=0，extractor_timeout=0，extractor_parse_error=1。
- adjudicator_provider_error=0，adjudicator_timeout=0，adjudicator_parse_error=0。

## Baseline 对比

- baseline_total_tokens=608247；poc_total_tokens=151598；token_delta=456649。
- baseline_wall_clock_time=320.585s；poc_wall_clock_time=359.473s。
- baseline_display_status_counts=`{"confirmed_defect": 14, "data_quality_gap": 85, "rejected_by_system": 44}`。
- poc_display_status_counts=`{"data_quality_gap": 44, "rejected_by_system": 6}`。

## POC 结论

- 本轮 POC 达到技术可比条件，且 token 低于 baseline，建议继续做规则族级 evidence builder 复核。

## 分病历摘要

| visit_id | patient | wall(s) | extractor_calls | adjudicator_calls | tokens | confirmed | data_gap | rejected | parse_errors |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 1915580 | 雷德超 | 44.68 | 3 | 3 | 15250 | 0 | 5 | 0 | 0 |
| 2024757 | 游德利 | 31.30 | 3 | 3 | 15212 | 0 | 5 | 0 | 0 |
| 2287309 | 陈光华 | 42.95 | 3 | 3 | 16632 | 0 | 2 | 3 | 0 |
| 2246915 | 黄金莲 | 46.31 | 3 | 3 | 19070 | 0 | 4 | 1 | 0 |
| 1883111 | 马章媛 | 25.78 | 3 | 3 | 12087 | 0 | 5 | 0 | 0 |
| 1966656 | 周光容 | 35.53 | 3 | 3 | 14144 | 0 | 5 | 0 | 0 |
| 2311318 | 范永勤 | 44.19 | 3 | 3 | 17344 | 0 | 3 | 2 | 0 |
| 2207717 | 邹才林 | 27.70 | 3 | 3 | 16369 | 0 | 5 | 0 | 0 |
| 1870471 | 蒲云鹏 | 31.68 | 3 | 3 | 12070 | 0 | 5 | 0 | 1 |
| 2268187 | 代云聪 | 29.34 | 3 | 3 | 13420 | 0 | 5 | 0 | 0 |

## confirmed_defect 明细


## 是否值得扩大

- 建议只在人工复核 confirmed 与 rejected 抽样后，再决定是否接入更多规则族；本 POC 不改变正式主链路。
