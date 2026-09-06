# LX0609 ReducedDecision 结果所有者收口

## 目标与边界

正式已裁决主链的唯一结果交付顺序固定为：`ReducedRuleDecision`、执行器原始
facts → Finalizer 合同校验 → Renderer → 公共 evidence projector → Finalizer
Canonical 收敛。Aggregator 只校验 wrapper/reduced 的索引与顺序、建立输入索引、
逐条装配和汇总；不得在此主链校验 facts、选择证据路径或覆盖客户 findings。

## 本次冻结

- `finalize_luxian_0609_reduced_customer_result` 是上述组合边界；它没有新增规则、
  状态、证据回退或事实合同，只复用已有 Finalizer、Renderer 和公共投影器。
- 原 Aggregator 中完整的 direct/native/mapped/gate 兼容职责（状态归一、旧结果
  选择、字段复制、schema/evidence formatter 和旧 native 投影）已物理迁至
  `luxian_0609_legacy_result_adapter.py`。Aggregator 由 839 行降至 184 行；adapter
  为 672 行，是唯一的旧交付边界。
- Aggregator 的 ReducedDecision 分支只传递冻结会话和原始 facts，并立即追加结果；
  架构守卫以 monkeypatch 证明该分支不会调用 legacy adapter，且建立 legacy 索引时
  不读取已裁决规则的旧 payload。
- 汇总只统计 Canonical `status`；非法 status 按 `technical_error` 统计，不再从
  `is_compliant` 推断临床状态。
- 在统一引擎与正式 active 规则均启用的主链中，每个交付规则均有
  `ReducedRuleDecision`，不会进入 adapter。pending 规则、统一引擎关闭或明确旧入口
  仍可使用该 adapter；这是隔离的兼容边界，不是正式主链 fallback。

## 验收

- Aggregator、Finalizer、Canonical delivery 聚焦测试冻结 facts、客户文案、证据
  坐标、技术失败与 Store 投影行为。
- 架构守卫断言 ReducedDecision 分支调用 Finalizer 组合入口而不直接调用
  Renderer 或公共 evidence projector；这些组合调用只位于 Finalizer 边界。
- 聚焦 Aggregator、Finalizer、Canonical delivery：536 通过；75 条正式三入口
  验收：2 通过（20.02 秒）；030/032 三入口回归：6 通过（分两组共 20.61 秒）；
  Python 编译、Ruff 与 diff-check 通过。
