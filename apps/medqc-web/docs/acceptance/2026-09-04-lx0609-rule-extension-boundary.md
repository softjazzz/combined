# LX0609 规则扩展边界验证

## 结论

现有执行合同可以承载一条确定性规则和一条受控语义规则，并通过：

```text
测试规则元数据/合同
  → 所属规则族执行器
  → FamilyExecutionEnvelope
  → RuleDecision + fact_refs
  → Binding / Reducer
  → Canonical Result
  → Aggregator 装配
  → 客户证据坐标
```

验证没有修改结果聚合器、公共任务入口、保存逻辑、API DTO 或前端，也没有新增引擎、fallback、状态机或生产规则。

## 验证方式

新增两条仅存在于测试中的合同：

- `LX0609-990`：确定性 `program_only`，零 LLM 调用；
- `LX0609-991`：`program_then_optional_llm`，使用确定性受控语义 Stub。

测试通过 monkeypatch 模拟新规则必需的规则目录和来源注册，测试结束后不会进入生产规则目录或运行时注册表。两条规则共用同一个只读 Evidence Session，并以 `fact_refs` 绑定同一份入院记录来源；公共证据投影最终生成真实文书 ID、字段路径和记录时间。

## 发现并修正的公共阻塞

首次测试时，`RuleDecision` 把规则号上限硬编码为 `LX0609-075`，导致合法的测试扩展合同在进入引擎后直接变成技术失败。该限制与目录、来源注册和 Binding 已承担的可信规则校验重复，也会迫使未来每批新增规则修改公共决策模型。

本阶段只将值对象格式约束调整为 `LX0609-001–999`：

- 仍拒绝 `LX0609-000` 和非三位数字格式；
- 规则是否真实存在仍由规则目录、来源注册和 Binding 校验；
- 未放宽未知规则进入生产任务的权限；
- 未修改状态、原因码或 Canonical 结构。

## Stub 协议结果

- native 规则：LLM 调用 0 次，Token 0；
- semantic 规则：LLM 调用 1 次；
- Prompt：固定为测试声明的最小受控语义指令，调用内容完全一致；
- 输入 Token：12；输出 Token：3；总 Token：15；
- Canonical 状态分别为 `compliant/requirement_satisfied` 和 `non_compliant/requirement_violated`；
- 两条结果均定位到 `admission_record / ADM-EXT-1 / chief_complaint / 2026-09-04 08:30:00`；
- 没有向普通 DTO、Prompt、trace 或客户结果新增 SHA 字段。

## 技术失败语义

既有引擎回归继续证明：

- 执行器超时 → `technical_error`；
- 执行器异常 → `technical_error`；
- Envelope 缺项或合同不匹配 → `technical_error`；
- 技术错误不会映射成 `data_gap`、`uncertain` 或 `not_applicable`。

## 测试结果

- 扩展边界测试：2/2 通过；
- 基础时限主链与路由聚焦回归：12/12 通过；
- 决策模型直接影响范围及基础时限主链聚焦回归：1518/1518 通过；
- 另行运行全量主链组合回归：301/303 通过。

组合回归中的两项失败是当前基线中的独立问题：

1. 输血规则 `049` 仍被任务计划标记为 `not_executed` 后进入旧派发；
2. `025/028` 仍被任务计划标记为 `not_executed` 后进入旧派发。

失败发生在 package plan / 旧派发阶段，本阶段改动的规则号格式校验、客户投影和聚合器均不在失败调用路径上。根据本任务“不得顺便清理旧链”的约束，这两项未在本提交中修复。

### 后续关闭结果（2026-09-04）

旧派发问题已在独立提交 `3bb25eacb` 中关闭。根因是
`Luxian0609PackagePlan.prepared_rule_ids_to_remove` 已包含阶段暂缓规则映射的旧执行 ID，
但遗漏了阶段暂缓的客户规则 ID 本身，导致 `049`、`025/028` 已生成
`not_executed` 结果后仍被再次派发到旧链。

修复仅把 `not_executed_rule_ids` 纳入准备规则清理集合，不改变阶段目录、质控口径、
Prompt、Canonical 合同、聚合器、API 或前端。Native 计划与完整主链相关测试现为
`180/180` 通过；三条规则继续保持 `not_executed`，旧派发调用为零，真正的兼容规则仍保留。

当前生产规则目录仍止于 `LX0609-075`，且没有已批准、业务定义完整的新增生产规则合同。
因此真实新增规则的双试点和真实模型十次性能协议尚不具备执行前提；不得用现有规则或
测试专用合同冒充该项生产验收。

## 运行时与边界

- 本机实际配置：`LUXIAN_0609_UNIFIED_ENGINE_ENABLED=true`；
- 基础时限执行器键：`basic_timeliness`；
- 测试扩展执行器键：`extension_native_test`、`extension_semantic_test`；
- 受控语义 Stub 只验证输入、调用预算和结果合同，不调用真实模型。真实模型 10 次中位耗时协议应在获得业务定义完整的新增语义规则后执行，不能用虚构规则消耗真实模型并宣称生产性能验收。

## 扩展成本结论

新增普通规则的稳定路径已得到验证，但应准确表述为：

- 每条新规则仍需增加规则目录/合同、来源声明、所属执行器实现和对应测试；
- 不需要修改 Aggregator、公共任务入口、保存、API DTO 或前端状态解释；
- Renderer 仅在需要新的客户标题或文案模板时增加声明式内容，不重新判定业务状态；
- 本阶段只消除了一个公共规则号上限阻塞，不代表其余 65 条规则族职责已经完成迁移。
