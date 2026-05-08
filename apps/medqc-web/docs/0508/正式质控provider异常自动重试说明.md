# 正式质控provider异常自动重试说明

生成时间：2026-05-08

## 背景

- 小样本抽检中 `visit_id=2246915` 的入院记录规则包曾出现 provider 批量执行异常，12 条规则被降级为 `uncertain`。
- 后续只读复跑同一失败 pack，第 1 次 attempt 即成功，`provider_error=0`、`timeout=0`、`rate_limit=0`。
- 结论：该类异常更符合偶发 provider/批量响应异常，应由后台自动恢复，不应要求医生或质控科手工点击重跑。

## 重试范围

- 仅接入正式 `final fast_screen` 主路径。
- 重试粒度为失败的 pack，不重跑整份病历。
- 默认最多自动重试 1 次。
- 保持原 `pack_id`、`rule_ids`、prompt、上下文、`quality_profile`、`batch_output_mode` 不变。

## 触发条件

- `evaluate_batch_compact` 抛出异常。
- provider/rate-limit/timeout metadata 可识别异常。
- 批量响应解析失败。
- 整包或大部分规则缺失结果。
- 整包均为 `confidence=0`、无 evidence 且 findings 指向“批量执行异常”。

个别 rule 缺失时仍按原保护逻辑只降级该规则为 `uncertain`，不重跑整个 pack，避免把正常低置信或局部缺项误判为 provider 异常。

## 页面策略

- 自动重试成功后，页面只展示真实 LLM 重试后的正常规则结果。
- 自动重试失败后，规则结果降级为 `uncertain` 并带内部 `technical_error_internal=true` metadata。
- 不在医生质控缺陷清单展示“建议重跑”类文案。
- 技术异常仅进入后台诊断、审计日志和后处理分层，不作为临床 `non_compliant` 缺陷。

## 诊断字段

- `pack_retry_attempts`
- `pack_retry_success`
- `pack_retry_reason`
- `provider_error_count`
- `timeout_count`
- `rate_limit_count`
- `technical_error_internal`
- `final_decision_source`: `batch` / `batch_retry` / `technical_error_fallback`

## 准确性保护

- 不改规则口径。
- 不改 prompt。
- 不裁剪证据上下文。
- 不关闭任何 pack。
- 不把 `technical_error` 改成 `compliant`。
- 重试成功结果必须来自真实 LLM 调用。
- Sheet2 客户样本验证链路和 acceptance package 不受影响。
