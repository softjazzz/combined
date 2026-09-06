# LX0609-040 手术 MDT 公共精确证据闭环

## 目标与范围

040 的正式 typed 主链已经为各可达状态产生精确 `RuleDecision.fact_refs`。本次只删除仍由 display facts 中 `source_document_refs` 驱动的旧 Aggregator 适配：客户文书证据唯一由 `fact_refs → Binding → 公共 selected-document projector` 提供。

修改范围：

- Finalizer 将 040 纳入 `requires_public_fact_ref_evidence`；非法 typed facts 仍收敛为 `technical_error/model_invalid_output`。
- Aggregator 删除 `legacy_surgery_mdt_customer_evidence` 导入和调用。
- `surgery_mdt_result_mapping` 删除 legacy evidence helper 及仅服务它的文书 ID 校验 helper。
- native MDT 不再构造 `customer_display_facts.source_document_refs`；不改变已有状态、原因码、Prompt 或 `fact_refs` 选择。

未修改 Renderer、API、前端或业务判定口径。

## 冻结证据合同

- `test_luxian_0609_native_mdt_execution.py` 覆盖正式 typed 结果的可达状态及 `fact_refs`；无手术、四级手术、术前讨论/会诊和模型失败的选中资料仍由 native 决策持有。
- `test_luxian_0609_surgery_mdt_freeze.py` 验证 Binding 后的 `fact_refs` 来源集合与公开客户证据坐标一致。
- Aggregator 回归验证：display facts 即使带旧私有 `source_document_refs` 也不会投影客户文书；有精确选中文书时仅公共 projector 的返回值成为客户证据。
- Finalizer 回归验证 040 已要求公共 `fact_refs` 证据，非法 typed facts 不会伪装为临床结果。

## 验证

```powershell
py -3.10 -m pytest -q tests/unit/test_luxian_0609_native_mdt_execution.py tests/unit/test_luxian_0609_surgery_mdt_result_mapping.py tests/unit/test_luxian_0609_surgery_mdt_freeze.py tests/unit/test_luxian_0609_canonical_result_finalizer.py tests/unit/test_luxian_0609_result_aggregator.py
# 487 passed

py -3.10 -m ruff check app/services/luxian_0609/native_mdt_execution.py app/services/luxian_0609/surgery_mdt_result_mapping.py app/services/luxian_0609/canonical_result_finalizer.py app/services/luxian_0609_result_aggregator.py tests/unit/test_luxian_0609_native_mdt_execution.py tests/unit/test_luxian_0609_surgery_mdt_result_mapping.py tests/unit/test_luxian_0609_surgery_mdt_freeze.py tests/unit/test_luxian_0609_canonical_result_finalizer.py

git diff --check -- app/services/luxian_0609/native_mdt_execution.py app/services/luxian_0609/surgery_mdt_result_mapping.py app/services/luxian_0609/canonical_result_finalizer.py app/services/luxian_0609_result_aggregator.py tests/unit/test_luxian_0609_native_mdt_execution.py tests/unit/test_luxian_0609_surgery_mdt_result_mapping.py tests/unit/test_luxian_0609_surgery_mdt_freeze.py tests/unit/test_luxian_0609_canonical_result_finalizer.py
```
