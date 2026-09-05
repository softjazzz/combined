# LX0609 真实生产规则扩展验收

## 结论

本次已把两条有正式业务定义的规则加入生产目录并走通 Canonical 主链：

- `LX0609-076`：死亡记录中的死亡时间完整性，来源业务规则 `LXE-43`；
- `LX0609-077`：首次病程鉴别诊断与第一诊断关联性，来源业务规则 `LX-011`。

它们不是 `990/991` 一类测试合同。当前生产目录为 `001-077`，客户交付 72 条、可执行 66 条、冻结 6 条。两条新规则均为 `phase_1_target`，分别由 `extended_document` 和 `course_quality` 执行。

## 正式执行链

实际链路为：

```text
生产规则目录
  -> Native Package 按 family 分组
  -> extended_document / course_quality
  -> RuleDecision + fact_refs
  -> Decision Binding 校验与统一状态归约
  -> 公共证据投影
  -> Canonical Result
  -> Aggregator 仅装配与 Renderer 声明式文案
```

正式编排测试确认：

- `LUXIAN_0609_UNIFIED_ENGINE_ENABLED=true`；
- 076 的 `executor_key=extended_document`，LLM 调用数为 0；
- 077 的 `executor_key=course_quality`，单次最多调用 LLM 1 次；
- `compatibility_rule_ids=()`；
- `compatibility_execution_rule_ids=()`；
- `legacy_wrapper_rules=[]`；
- 两条结果都由 Binding 归约后进入 Canonical Result；
- 客户证据可定位到真实测试文书 ID，而不是由执行器拼装证据 DTO。

## 三类业务入口

代码调用链核对确认：

- 运行/终末质控通过 `SichuanQCService` 调用 `prepare_luxian_0609_execution()`；
- 客户样本验证只负责冻结客户规则范围和创建任务，执行仍进入同一个 `SichuanQCService` 主链；
- 预生产单规则/批量验证通过 `preproduction_runner` 调用同一个 `prepare_luxian_0609_execution()`。

客户样本规则集测试确认 076/077 已进入 72 条交付范围和 66 条实际执行范围；正式编排集成测试确认两条规则没有转入旧执行器。

## 状态边界

### 076

- 非死亡病例：`not_applicable / trigger_absent_complete`；
- 死亡病例但无死亡记录：`not_applicable / eligibility_not_met`，避免与 060 重复报错；
- 死亡记录有可解析死亡时间：`compliant / requirement_satisfied`；
- 仅有记录完成时间、没有死亡时间：`non_compliant / defect_proven`；
- 来源不可用、截断或时间冲突：`data_gap`；
- 不调用 LLM。

### 077

- 第一诊断或鉴别诊断缺失：`data_gap / required_field_missing`，不调用模型；
- 语义相关：`compliant / requirement_satisfied`；
- 明显无关：`non_compliant / requirement_violated`；
- 材料存在但语义置信不足：`uncertain / semantic_low_confidence`；
- 超时、传输异常或输出结构非法：`technical_error`；
- 不重试，每次最多调用模型 1 次。

## 性能与稳定性

确定性 Stub 连续执行 10 次：

- Prompt 完全一致；
- 每次调用数均为 1；
- 每次输入/输出/总 Token 均为 `50/8/58`；
- Canonical 状态、原因码和证据定位完全一致。

真实模型使用无患者正文的结构化合成快照，预热后连续执行 10 次：

- 总调用数 10，单次调用数始终为 1；
- 10 次输入 Token 均为 174；
- 10 次输出 Token 均为 24；
- 10 次结果均为 `applicable/sufficient/satisfied`；
- 中位 API 耗时 0.4847 秒，最小 0.4063 秒，最大 1.1638 秒。

## 扩展成本

首次真实扩展暴露并消除了三处公共阻碍：

1. 新的正式 `native_async` 规则仍受旧规则迁移开关白名单限制；现改为：已有规则继续受历史开关控制，没有历史开关的新正式规则直接使用 typed decision 合同。
2. Runtime Manifest、运行审计、Golden Gate 和 20 例基准仍写死 `75/70/64/6` 或正式/临时规则数量；现改为依据 master 和 phase 的集合分区做一致性校验，历史审计仍可显式传入冻结目标。
3. 历史 0426-v3 样本固定覆盖 `001-075`；现明确保持冻结，不把 076/077 伪装成旧样本已覆盖。

除自动生成的验收矩阵外，本次生产代码、配置新增约 763 行、删除 38 行，其中两个独立规则模块共 470 行。公共层改动用于移除上述一次性扩展阻碍；没有新增引擎、状态机、fallback、注册中心或证据投影层。

下一条同类生产规则预计只需要：规则声明/合同、所属规则族执行器接线、独立规则模块、声明式文案和测试，不再修改固定规则总数或 typed rollout 白名单。

## 零侵入核对

本次没有修改：

- `luxian_0609_result_aggregator.py`；
- 公共任务 API DTO；
- 保存逻辑；
- 前端状态解释；
- 旧兼容执行器。

聚合器中不存在 `LX0609-076` 或 `LX0609-077` 的规则专属判断。

## 回归结果

- 真实生产规则聚焦测试：14 项通过；
- 真实规则与 20 例基准联合测试：70 项通过；
- 冻结 0426-v3 与证据快照：167 项通过；
- Runtime、规则集和客户样本入口：114 项通过；
- Golden Gate 与合同矩阵：70 项通过；
- LX0609 全影响范围：首次运行仅发现 4 项旧期望未随正式目录更新；修正后最终复跑 `4,366 passed`，耗时 49.64 秒。

全仓库一次性收集仍会遇到与本任务无关的本机环境问题：SciPy/Scikit-learn 使用 NumPy 1.x 构建但当前安装 NumPy 2.2.6，以及两个样本同步测试要求从仓库上级目录导入 `backend.scripts`。这些问题不属于 LX0609 执行链，本次未混入修复。
