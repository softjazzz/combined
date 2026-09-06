# LX0609 Canonical Store 重复事实所有者退出验收

## 目标

`canonical_result_store` 只搬运 Finalizer 已验证的 Canonical facts，不能按规则号重建展示 facts，也不能在写入时改变业务状态。

## 变更边界

- Store 的 `safe_customer_display_facts` 仅调用 `validate_luxian_0609_executor_customer_display_facts`：只有返回字典才复制交付，`None` 或 `NotImplemented` 一律为空 facts。
- 删除 Store 内的规则号 facts fallback、对 Aggregator 的反向导入，以及 `non_compliant -> data_gap` / `historical_evidence_missing` 隐式降级。
- 未修改 Aggregator、Finalizer、规则族 mapping、API 或前端。

## 冻结证据

- 024、025、028、029、030、032、034--037、039 的有效 facts 在共享 Finalizer 与 Store 中输出一致。
- 裸旧 025 payload、私有/不完整 facts 与未知规则均 fail-closed；Store 不再补造 facts。
- 当前 typed/native 的无 facts 且 `non_compliant` 结果在写入前被既有解释合同拒绝，状态不会被 Store 改写。
- 源码守卫确认 Store 不含规则号字面量、`result_aggregator` 导入、`surgery_document_targets` 或 `historical_evidence_missing`。

## 口径与剩余风险

正式三入口已经通过 Finalizer 生成受控 facts，因此有效 Canonical 结果不变。本次会拒绝曾依赖 Store fallback 的裸旧 payload；这是为了避免数据库层把不完整 facts 重新解释为客户确定结论。旧历史结果的展示兼容仍由既有客户安全投影负责，不属于本次 Store 写入链路。
