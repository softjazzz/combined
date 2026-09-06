# LX0609 data_gap 客户文案等价迁移验收

## 范围

将 `canonical_result_finalizer.py` 中 data_gap 的默认 `customer_message` 选择迁入
`customer_renderer.py:data_gap_customer_message`。本次不改状态、原因码、结构化
facts、缺口字段或证据。

Finalizer 仍负责 `reason_label`、`missing_sources`、`missing_fields` 的默认值补全，
以及顶层字段与 `data_gap_details` 同名字段冲突的 fail-closed 校验。显式顶层或详情
`customer_message` 的优先级和冲突语义保持不变；仅在两者均未给出时调用 Renderer
取得默认文案。

## 依赖边界

`customer_renderer.py` 未导入 `canonical_result_finalizer.py`；Finalizer 在其 data_gap
补全函数内单向调用 Renderer，因此不存在循环导入。Renderer 函数为纯映射：只接收
`rule_id`、`reason_code`、`missing_sources`，不读取材料、不产生 DTO、不改变判定。

## 等价性冻结

单元测试逐字冻结了：

- 13 个通用 reason_code 的默认客户文案；
- 069、009、028、031、048 五个规则级默认文案；
- 048 在存在实际缺失来源时的动态文案；
- 未登记 reason_code 的原默认回退文案。

其中 048 动态文案继续只在
`LX0609-048/transfusion_comparison_fields_unavailable` 且 `missing_sources` 非空时生效。

## 验证

在 `backend` 目录执行：

```powershell
py -3.10 -m pytest -q tests/unit/test_luxian_0609_canonical_result_finalizer.py tests/unit/test_luxian_0609_customer_renderer.py tests/unit/test_luxian_0609_native_transfusion_execution.py tests/unit/test_luxian_0609_native_transfusion_freeze.py tests/unit/test_luxian_0609_transfusion_result_mapping.py tests/unit/test_luxian_0609_transfusion_selected_evidence.py
```

结果：`610 passed`。

后续静态检查和 diff-check 与本验收文档一并执行；本次不触及 Aggregator。
