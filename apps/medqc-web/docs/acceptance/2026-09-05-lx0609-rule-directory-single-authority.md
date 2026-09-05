# LX0609 规则目录单一权威验收记录

日期：2026-09-05

## 目标

消除 `rule_master` 与 `phase_scope` 对固定 `LX0609-001` 至
`LX0609-075` 范围的重复定义。生产规则 ID 集合由 master 唯一声明；
phase 仅保有发布阶段状态，并验证自身 ID 顺序与 master 完全一致。

本次不增加生产规则、不修改生产 JSON，也不修改聚合器、执行器、Prompt、
Renderer、任务入口、保存、API、数据库或前端。

## 变更边界

- `compile_luxian_0609_rule_master()`：以实际条目数验证连续、有序的
  `LX0609-001..N`；拒绝空集合、缺号、重复和乱序；移除固定 75 条和固定状态
  汇总的校验。
- `compile_luxian_0609_phase_scope()`：phase 的全部 ID 必须按顺序精确等于
  master 的全部 ID，而不是 active 子集；`catalog_registered` 仍必须精确投影
  master 的 `implementation_status=active`。此外 `phase_1_target` 必须已经
  `catalog_registered=true`，合同就绪但未注册的规则不能借由 phase 状态进入执行。
- wrapper 目录仍只投影 active master 规则。因此 master 与 phase 即使临时
  声明 `076`，未提供 wrapper 时 `load_luxian_0609_rules()` 必须 fail closed，
  不会让半成品规则进入执行链。

## TDD 证据

1. 红测：临时复制 master 并追加 `LX0609-076` 时，旧实现因固定
   `001..075` 抛错；最小改动后通过。
2. 红测：临时复制 master 和 phase 并同步追加 `076/077` 时，旧 phase 因固定
   `001..075` 抛错；改为对照 master 后通过。
3. 固定失败边界：master 的空集合、缺号、重复、乱序、`LX0609-000`、非三位编号
   和错误前缀；phase 相对 master 的缺项、额外、重复、乱序；以及
   `phase_1_target` 未标记 `catalog_registered`、或 master 为 `contract_ready`
   而 phase 试图标记 target，均被拒绝。
4. 固定安全边界：临时 master/phase 接受 `076` 而 wrapper 未补齐时，完整
   execution catalog 抛出 drift 错误。

## 回归与行为等价

生产 JSON 未变，因此当前运行时仍是 75 条规则、原 ID 顺序和原状态汇总。该闭环
不调用模型、不写数据库，也不产生 Canonical 结果变化。

通过的聚焦测试：

```text
py -3.10 -m pytest \
  backend/tests/unit/test_luxian_0609_rule_master.py \
  backend/tests/unit/test_luxian_0609_phase_scope.py \
  backend/tests/unit/test_luxian_0609_production_extension_boundary.py -q

37 passed
```

正式统一主链与影响范围回归：

```text
py -3.10 -m pytest <全部 test_luxian_0609_*.py> -q --disable-warnings \
  -k "not <5 个固定基线节点>"

4266 passed, 5 deselected
```

5 个固定基线节点为 3 个既有 `row_ref` digest 断言、1 个 source registry
`v23/v24` 版本断言和 1 个 `LX0609-070` 多证据投影预期；未修改这些无关口径，
也未扩大排除范围。生产扩展主链测试仍显式断言 unified engine 开启、
`compatibility_rule_ids` 与 `compatibility_execution_rule_ids` 为空、
`legacy_wrapper_rules=[]`，并固定 `basic_timeliness` 的 `executor_key` 与证据坐标。

## 结论与剩余风险

固定 75 条目录门禁已经解除，但这不代表 `076` 已可执行。真实规则仍需独立补齐
master、phase、wrapper、合同、所属规则族执行器及真实病例验收；在 wrapper 或合同
缺失时，现有 fail-closed 检查会阻止其进入执行主链。
