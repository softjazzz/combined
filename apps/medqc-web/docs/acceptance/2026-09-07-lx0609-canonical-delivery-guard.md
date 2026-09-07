# LX0609 Canonical 结果交付收紧验收

## 目标

正式 LX0609 任务显式声明 `canonical_straight_through`。规则执行完成后，结果只能来自：

1. `ReducedDecision` 经 Finalizer 生成的 Canonical 结果；
2. phase gate 生成的 `not_executed` Canonical 结果；
3. 规则族明确生成的 `technical_error` Canonical 结果。

缺少以上结果时，按 `decision_contract_violation` 生成 `technical_error`。正式任务不得读取或自动切换到 legacy result adapter。

## 实施边界

- `prepare_luxian_0609_execution()` 根据正式主链设置显式声明交付模式。
- Canonical 模式不索引 `execution_results`，也不调用 legacy adapter。
- 历史离线诊断和兼容测试只有在显式使用 `legacy_compatible` 时才能进入 adapter。
- 未发布规则的 `not_executed` 结果补齐 Canonical 合同字段。
- 规则族基础设施失败保留原始技术原因码，不被通用缺裁决错误覆盖。
- 批量任务详情从已校验的 Record Result Envelope 读取结果并重新生成汇总。

## 相关缺陷闭环

- 020/023 第二阶段模型输出遗漏部分建议时，只对遗漏建议补问一次；仍不完整则输出 `technical_error/model_invalid_output`，不把遗漏默认解释为未执行。
- 新批量任务的紧凑结果保存 `schema_version`、`result_status` 和 `display_status`。
- 旧候选 Envelope 在读取时继承已验证的 Envelope 合同，并补齐当前目录中的规则版本；不重新解释业务状态。

## 自动化验收

- Canonical 读取、复核、批量详情及批任务接口聚焦回归：153 项通过。
- LX0609 全量影响范围按以下可复现命令执行：

```powershell
$files = Get-ChildItem -LiteralPath 'backend\tests' -Recurse -Filter 'test_luxian_0609*.py' |
    Sort-Object FullName |
    Select-Object -ExpandProperty FullName
py -3.10 -m pytest -q --disable-warnings @files
```

- 测试文件：145 个；
- 收集并通过：4958 项；
- 失败：0 项；
- 耗时：234.91 秒。
- 严格边界测试使用会立即失败的 adapter 替身，证明缺少 `ReducedDecision` 时没有触碰 legacy adapter。
- 正式编排测试确认 `delivery_mode=canonical_straight_through` 被显式传入聚合器并写入编排结果。
- 批量结果复核入口先从已校验的 Canonical Envelope 读取结果；Envelope 缺失时返回 409，不读取任务行中的旧 `items`。
- 编码检查、ESLint 和 TypeScript 类型检查通过。
- 全量前端单测为 840 项通过、0 项失败。

## 本机真实病历验收

候选任务：`e8335812-bca5-494d-ba3d-50d4a324af44`

- 病历数：5。
- 每份结果数：72；总结果数：360。
- 72 条是当前客户交付完整范围：规则总表 77 条，扣除客户明确排除的 `033/034/035/041/042` 后为 72 条；其中 66 条正式执行，6 条按阶段策略输出 `not_executed`。这 5 条不是执行遗漏。
- 任务状态：`completed`。
- 5 个 Record Result Envelope 均为 `canonical_straight_through`，每个包含 72 条结果。
- Canonical 状态分布：`compliant=55`、`non_compliant=21`、`not_applicable=111`、`data_gap=143`、`not_executed=30`、`technical_error=0`。
- 批量详情重新投影后仍为 360 条，状态分布完全一致。
- 目标病例的 020/023 均为 `compliant/requirement_satisfied`，未再出现原先的模型输出技术错误。

## 剩余边界

- legacy adapter 仍为历史离线调用保留，但正式任务必须显式使用 Canonical 模式；后续不得向 adapter 增加新规则逻辑。
- 旧任务列表的缓存摘要不会批量回写；打开任务详情时以已校验 Envelope 重新生成准确汇总，新创建任务直接保存完整 Canonical 标记。
