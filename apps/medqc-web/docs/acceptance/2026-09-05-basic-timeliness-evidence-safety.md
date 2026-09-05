# LX0609 基础时限客户证据安全基线

## 本闭环范围

本闭环只修复基础时限规则在“未提供选中文书 ID”时，客户证据坐标可能借用同来源另一行文书 ID 的安全问题。规则判定、状态、原因码、Prompt、Binding 合同和材料仓均不改变。

允许的唯一回退条件是：同一冻结来源材料恰好一条、该条是可识别 Mapping 行，且其文书 ID 有效。来源存在多条材料行时，即使只有一个非空 ID，或多个行复用同一 ID，也不得从来源快照推测客户坐标。

## 冻结结论与遗留盲区

- 001/002/005/006 的 `fact_refs` 当前仍是来源快照级引用；测试按来源语义校验，不比较 SHA 字面值。
- 当前 001/002 的多文书样本虽然原始 facts 含选中文书 ID，但客户 `customer_evidence` 为空；这不是已完成的定位能力。
- 当前 005 的选中文书在 `daily_course_record`，客户坐标却投影为 `senior_course_record`，且没有 `field_path` / `record_time`。这是独立的来源误投影遗留问题，不在本闭环修复范围。
- 004 的明确 `source_document_id`、逐次 `rescue_events` 及抢救医嘱路径保持原样；本闭环不改变这些显式事实证据。
- 逐文书 `document_refs` 已在材料仓生成，但当前 Binding 只允许 FactV2 或来源 snapshot refs。将真实 `document_ref` 放入 `RuleDecision.fact_refs` 仍会得到 `technical_error/snapshot_mismatch`。完整单所有者/逐文书事实迁移尚未完成，本闭环不能宣称架构收口。

## 实际验证

已运行：

```text
python -m pytest \
  tests/unit/test_luxian_0609_basic_timeliness_evidence_freeze.py \
  tests/unit/test_luxian_0609_result_aggregator.py \
  tests/unit/test_luxian_0609_basic_timeliness_architecture_freeze.py -q
```

结果：386 passed。冻结测试包括：

- 选中文书缺 ID 时，同来源多行即使仅一条有非空 ID 也不产生客户坐标；
- 同一 ID 出现在多条、不同时刻材料行时不产生来源快照 fallback 坐标；
- 单条、有效 ID 的材料仍保留合法坐标；
- FactV2 缺行 ID 时，上述两类多行材料同样不回填，覆盖 FactV2 与 source-observation 两处 fallback。
