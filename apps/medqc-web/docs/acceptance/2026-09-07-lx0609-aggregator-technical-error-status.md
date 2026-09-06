# LX0609 聚合器技术失败状态收口验收

日期：2026-09-07

## 目标与边界

修复聚合器旧兼容路径中的两处技术失败状态漂移：

- 旧映射结果的状态归一化防御分支不得将非法状态降为 `data_gap`，统一输出
  `technical_error`；
- 缺少任何映射执行结果属于编排技术失败，不得输出 `uncertain`，输出
  `technical_error` 与原因码 `missing_mapped_result`。

本变更不修改临床规则口径、客户展示事实、证据选择、Finalizer、Renderer、API 或前端。

## TDD 证据

生产修改前新增的两项测试均失败：

- 非 Canonical 状态进入 `_copy_customer_fields()` 时得到 `data_gap`；
- 无映射执行结果得到 `uncertain`，但同一结果元数据标记
  `technical_error_internal=true`。

最小修复后，两项测试均验证为 `technical_error`；后者同时固定
`reason_code=missing_mapped_result`。

## 验证

```powershell
py -3.10 -m pytest tests/unit/test_luxian_0609_result_aggregator.py -q
py -3.10 -m pytest tests/unit/test_luxian_0609_mainline_services.py::test_luxian_0609_summary_should_use_canonical_statuses_and_exclude_not_applicable_denominator tests/unit/test_luxian_0609_rule_extension_boundary.py -q
py -3.10 -m ruff check app/services/luxian_0609_result_aggregator.py
py -3.10 -m ruff check tests/unit/test_luxian_0609_result_aggregator.py --ignore E701,F821
git diff --check
```

通过标准：381 项聚合器单元测试与 3 项相关主链/扩展边界测试通过；不增加新的
`data_gap` 或 `uncertain` 业务解释分支。

注：完整聚合器测试文件现有 12 项 Ruff 问题（`E701`、`F821`）位于未改动的
历史行；本闭环未放宽全局 lint 配置。
