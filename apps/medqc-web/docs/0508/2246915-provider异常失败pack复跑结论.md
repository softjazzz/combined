# 2246915 provider异常失败pack复跑结论

生成时间：2026-05-08 20:59:19

## 原异常来源

- 小样本正式质控抽检中，`visit_id=2246915` 出现 `provider_error=3`。
- 质量治理中 12 条 `technical_error` 均来自入院记录相关规则包批量执行异常后降级为 `uncertain`。
- 受影响规则：SC-004, SC-007, SC-008, SC-009, SC-010, SC-011, SC-012, SC-013, SC-014, SC-015, SC-016, SC-018。

## 复跑范围

- 本轮只读重跑指定规则，不写 `qc_results/qc_defects`，不改规则、prompt、Sheet2 或原始抽检文件。
- 实际命中的 pack：admission_content_core, admission_consistency_core。
- 最大尝试次数：2；pack_concurrency=1。

## 复跑结果

- 复跑成功：至少一次 attempt 的 `provider_error_count=0`。
- 结论：原异常更像偶发 provider/批量响应问题，重跑可恢复。
- 最终状态分布：{"not_applicable": 2, "compliant": 9, "non_compliant": 1}。
- 12 条 technical_error 可在人工复核视角中解除，但是否为正式缺陷仍需按 evidence 和后处理准入策略判断。

## 分次明细

- attempt 1: wall=68.92s, provider=0, timeout=0, rate_limit=0, tokens=10871, status={"not_applicable": 2, "compliant": 9, "non_compliant": 1}

## 对演示结论的影响

- 技术链路仍可演示。
- 结果质量演示仍不建议直接推进；需要先落地后处理分层，避免 provider_error/数据缺口混入医生缺陷清单。
