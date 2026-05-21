# 正式质控双模型 random10 只读验证报告

生成时间：2026-05-21 10:22:14

## 模型配置

- 一审模型：`qwen3.5-35b-a3b`
- 二审模型：`qwen3.6-35b-a3b`
- 策略：一审 fast_screen/pack 初筛使用 qwen3.5，二审 adjudicator 使用 qwen3.6。
- 本轮只读运行，不写正式 QC 结果表，不扩大到 20 份。
- 无效前序结果说明：上一轮 PowerShell 命令使用双引号包裹 -Command，外层 PowerShell 提前展开 $env:LLM_ADJUDICATOR_MODEL，传入 pwsh 后变成无效赋值；该轮结果标记为 invalid_env_assignment，不作为双模型验证结论。

## Minimal Probe

- first_pass: model=qwen3.5-35b-a3b, tokens=35, passed=True, provider_error=0, upstream_http_error=0, parse_error=0, timeout=0, rate_limit=0
- adjudicator: model=qwen3.6-35b-a3b, tokens=35, passed=True, provider_error=0, upstream_http_error=0, parse_error=0, timeout=0, rate_limit=0

## 2122521 单病历双模型门禁

- 状态：通过
- 一审模型：`qwen3.5-35b-a3b`
- 二审模型：`qwen3.6-35b-a3b`
- adjudicator_model_source：`env_adjudicator_model`
- technical_error_internal：0
- missing_rule_after_retry：0
- total_tokens：63232

## 稳定性

- probe 门禁：通过
- random10 状态：`completed`
- 完成病历数：10/10
- provider_error：0
- provider_connection_error：0
- upstream_http_error：0
- parse_error：0
- timeout：0
- rate_limit：0
- technical_error_internal：0
- 稳定性结论：通过

## 性能与成本

- 总耗时：486.54s
- 平均耗时：48.65s/份
- 最慢耗时：72.04s
- LLM 调用数：141
- 一审调用数：131
- 二审调用数：10
- total_tokens：736290
- 一审 tokens：507556
- 二审 tokens：228734

## 结果分层

- confirmed_defect：5
- data_quality_gap：81
- rejected_by_system：99
- technical_error_internal：0

## 质量参考

- confirmed 复核 keep：2/5
- keep rate：40.0%
- 2262370 / SC-118 状态：rejected_by_system
- 2328501 / SC-121 状态：data_quality_gap

## 对比 qwen3.5 全链路失败基线

- qwen3.5 全链路完成数：8/10
- qwen3.5 全链路 technical_error_internal：5
- qwen3.5 全链路稳定性：False

## 结论

- 双模型 random10 稳定性通过，说明 qwen3.5 一审 + qwen3.6 二审可恢复二审输出完整性。
- confirmed 质量仍未达到 70% 阈值，不建议直接扩大到 20 份。
- 暂不建议页面演示；下一步应继续治理 confirmed 低 keep 规则，而不是扩大样本。
