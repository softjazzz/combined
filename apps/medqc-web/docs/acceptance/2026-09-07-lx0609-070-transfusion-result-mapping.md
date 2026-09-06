# LX0609-070 输血前法定传染病检验结构迁移验收

## 范围

- 只迁移 LX0609-070 的客户展示 facts 合同与证据职责。
- 原生链路保持为 native transfusion execution → RuleDecision/display facts → Binding → Finalizer → 公共证据投影 → Aggregator。
- 未修改原生判定、状态、原因码、Renderer、Prompt、API 或前端；048 文案与 047 缺陷不在本次范围。

## 所有权

- `transfusion_result_mapping.py` 接管 070 既有输血前九项摘要和逐笔 `event_checks` 白名单，包含逐笔输血时间、有效检验时间、缺失/无时间/迟到/院外项目，及既有失败时点与住院时点。
- Mapping 不读取材料、不选择证据、不构造客户证据 DTO。
- Finalizer 校验 070 的 status/facts 自洽；非法 facts、局部逐笔字段或状态冲突清除客户内容并降为 `technical_error`。
- 070 单独声明只允许公共 `fact_refs` 证据投影；041–048 的既有证据合同没有扩展。
- 资料源缺口或未触发而没有展示 facts 的既有 `data_gap` / `not_applicable` 结果保持原状态。

## 守卫与验证

- Aggregator 对 `LX0609-070` 的文本引用计数为 0，逐笔 facts 校验已完全迁出。
- Mapping 测试冻结完整逐笔形状、私有材料剥离、状态冲突技术降级、缺 facts 保持、070-only 公共 fact_refs 声明及 041–048 不扩展。

```powershell
pytest -q tests/unit/test_luxian_0609_transfusion_result_mapping.py tests/unit/test_luxian_0609_result_aggregator.py -k '070 or transfusion'
pytest -q tests/unit/test_luxian_0609_native_extended_document_execution.py -k '070'
pytest -q tests/unit/test_luxian_0609_canonical_result_finalizer.py
ruff check app/services/luxian_0609/transfusion_result_mapping.py app/services/luxian_0609/canonical_result_finalizer.py app/services/luxian_0609_result_aggregator.py tests/unit/test_luxian_0609_transfusion_result_mapping.py
git diff --check
```
