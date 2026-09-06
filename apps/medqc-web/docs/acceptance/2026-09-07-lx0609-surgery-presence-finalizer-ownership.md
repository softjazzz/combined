# LX0609-030/032 手术文书存在性 Finalizer 所有权验收

日期：2026-09-07

## 目标与边界

将 030（手术记录存在性）和 032（手术安全核查表存在性）的客户展示 facts
白名单从 `canonical_result_finalizer.py` 迁至
`surgery_presence_result_mapping.py`。Finalizer 仅作为统一接收边界委托
mapping；不读取材料、不重新判定状态、不选择证据。

本阶段不声明 public `fact_refs`，不修改 Aggregator、native 执行器、Renderer、
Prompt、API 或前端。

## 合同冻结

- 030 目标文书固定为 `surgery_record`；032 固定为
  `surgery_safecheck_record`。
- 合法展示 facts 仅为：已确认存在的 `verification_kind` 形状，或
  `surgery_document_missing` / `surgery_document_blank` 失败形状；两者均要求
  `performed_surgery_confirmed=true`。
- 原始输入的额外内部字段不会进入展示 facts；单独的非法或私有输入 fail-closed。
- `finalizer_owns_executor_customer_display_facts` 通过 mapping 的规则归属函数
  认领 030/032；`finalizer_requires_public_fact_ref_evidence` 对两条仍为 `False`。

## 验证

```powershell
pytest -q backend/tests/unit/test_luxian_0609_surgery_presence_result_mapping.py backend/tests/unit/test_luxian_0609_surgery_presence_freeze.py backend/tests/unit/test_luxian_0609_canonical_result_finalizer.py
ruff check backend/app/services/luxian_0609/surgery_presence_result_mapping.py backend/app/services/luxian_0609/canonical_result_finalizer.py backend/tests/unit/test_luxian_0609_surgery_presence_result_mapping.py backend/tests/unit/test_luxian_0609_canonical_result_finalizer.py
git diff --check
```

通过标准：mapping 逐形状等价于 Finalizer 接收结果；030/032 Native → Binding →
Canonical 冻结回归保持绿色；Finalizer 委托测试确认不提前接管 public 证据。
