# qwen3.5 下 SC-146 单规则 pack 稳定性定向诊断

## 范围

- visit_id=2013648；规则=SC-146；pack=daily_order_consistency；pack_concurrency=1。
- 只读运行正式 final fast_screen_full / sc_content_full_v1，不写正式 QC 结果表，不运行 random10。

## 结论

- 三次定向运行通过次数：3/3。
- provider_error=0；parse_error=0；timeout=0；rate_limit=0；technical_error_internal=0。
- SC-146 单规则 pack 已启用严格 JSON 输出约束，并兼容 SC146 / SC-146 等 rule_id 变体匹配。

## 逐次诊断摘要

- attempt=1 model=qwen3.5-35b-a3b tokens=5629 expected=['SC-146'] actual=['SC-146'] missing=[] retry=0 retry_reason=none parse_reason=none technical=0。
- attempt=2 model=qwen3.5-35b-a3b tokens=11134 expected=['SC-146'] actual=['SC-146'] missing=[] retry=2 retry_reason=parse_error parse_reason=none technical=0。
- attempt=3 model=qwen3.5-35b-a3b tokens=8363 expected=['SC-146'] actual=['SC-146'] missing=[] retry=1 retry_reason=parse_error parse_reason=none technical=0。

第 2/3 次首轮响应曾触发 parse_error retry，但严格 JSON prompt 与 rule_id 归一化后均恢复为 expected=actual=SC-146，最终 parse_error_count=0、technical_error_internal=0。

## 后续建议

- 若后续 random10 再出现 SC-146 technical_error_internal，应先查看本报告中的 raw_output_summary、expected/actual/missing_rule_ids，不应直接扩大样本。
- 本轮没有修改其他规则质量逻辑，也没有启用 qwen3.6 fallback。
