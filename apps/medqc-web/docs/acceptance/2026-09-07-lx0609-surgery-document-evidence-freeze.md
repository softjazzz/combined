# LX0609-034/036/039 手术文书 typed 证据冻结验收

日期：2026-09-07

## 范围

本阶段只冻结 034（麻醉知情同意书存在）、036（麻醉术前/术后访视存在）和
039（术前讨论及术者参加）的 typed `fact_refs → Binding → 公共客户证据投影`。
不改 Finalizer、Aggregator、result mapping 的 legacy evidence helper，也不声明
public `fact_refs` 所有权。

035、037、038 只审计 `_typed_precise_terminal_refs` 的相邻分支，未调整其业务
口径或证据选择。

## 已冻结的选择合同

- 034：麻醉触发文书；当知情同意书已参与判断时，再包含对应知情同意书。
- 036：实际采用的麻醉触发文书，以及非空的术前/术后访视文书。
- 039：已确认实施手术文书，以及实际参与结论的抢救例外/术前讨论文书。
- 所有状态均仅由 RuleDecision 的同一 Evidence Session `fact_refs` 形成客户
  证据；无材料坐标时保持无客户证据，禁止从裸 display facts 或来源类型猜测。

## 验证矩阵

独立冻结测试覆盖每条规则的 `compliant`、`non_compliant`、`not_applicable`、
`data_gap`、`technical_error`。每例断言：

1. `fact_refs` 全部能还原为同会话 FactV2、来源观察或逐文书材料坐标；
2. 引用来源集合恰为本次判定使用的触发/目标来源；
3. 所有 material 坐标与 Aggregator 公共 projector 的 `customer_evidence` 集合
   完全相同。

```powershell
pytest -q backend/tests/unit/test_luxian_0609_surgery_document_evidence_freeze.py backend/tests/unit/test_luxian_0609_surgery_document_freeze.py backend/tests/unit/test_luxian_0609_native_surgery_document_execution.py
ruff check backend/tests/unit/test_luxian_0609_surgery_document_evidence_freeze.py
git diff --check
```
