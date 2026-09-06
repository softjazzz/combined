# LX0609-034/036/039 手术文书公共证据接管验收

日期：2026-09-07

## 变更范围

在已冻结 typed `fact_refs` 的基础上，034、036、039 由 Finalizer 声明为仅允许
公共逐行 `fact_refs` 投影客户证据的规则。Aggregator 删除
`legacy_surgery_document_customer_evidence` 的导入和调用；
`surgery_document_result_mapping.py` 删除该 legacy helper 及其专用的
`_valid_document_id`。

未改 native 判定、状态、原因码、客户 facts 合同、Prompt、Renderer、API 或前端。
029、035、037、038 不在本次 public evidence 声明中，维持既有事实/状态合同。

## 接管语义

- 034/036/039 的裸 `customer_display_facts` 即使带内部文书 ID，也不会重建
  `customer_evidence`。
- 只有同一 Evidence Session 内的 `ReducedRuleDecision.fact_refs` 经公共
  projector 才能产生客户证据坐标。
- 缺少精确 refs 时客户证据为空；不得按来源类型、display facts 或旧 adapter
  反推文书。

## 验证

```powershell
pytest -q backend/tests/unit/test_luxian_0609_surgery_document_evidence_freeze.py backend/tests/unit/test_luxian_0609_surgery_document_freeze.py backend/tests/unit/test_luxian_0609_native_surgery_document_execution.py backend/tests/unit/test_luxian_0609_surgery_document_result_mapping.py backend/tests/unit/test_luxian_0609_canonical_result_finalizer.py backend/tests/unit/test_luxian_0609_result_aggregator.py
ruff check backend/app/services/luxian_0609/surgery_document_result_mapping.py backend/app/services/luxian_0609/canonical_result_finalizer.py backend/app/services/luxian_0609_result_aggregator.py backend/tests/unit/test_luxian_0609_surgery_document_result_mapping.py backend/tests/unit/test_luxian_0609_canonical_result_finalizer.py backend/tests/unit/test_luxian_0609_result_aggregator.py
git diff --check
```

通过标准：冻结的 Native → Binding → projector 坐标不变；直调裸 facts 无证据；
提供精确 reduced `fact_refs` 时仅输出其对应文书坐标。
