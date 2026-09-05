# 会诊规则族 020–023 正式入口与性能验收（B3）

日期：2026-09-05

## 结论

B3 通过。会诊规则族 020–023 已在单病历任务、病历池批量任务和客户样本验证叶子任务
三个正式 worker 入口中统一走 `consultation_quality`，结果经同一 Canonical 主链保存；未
观察到 legacy、bundle fallback 或 LLM fallback。真实模型的 Prompt、调用次数和输入
Token 均未增加，中位耗时没有回归。

真实模型复放同时揭示了 B1 冻结基线中的一个既有技术缺陷：模型响应、episode 事实、
`RuleDecision` 和 Binding 均已成功，但旧聚合器因不认识会诊客户事实合同，将原本的
`compliant/requirement_satisfied` 覆盖为
`technical_error/model_invalid_output`。B2 删除该重复业务所有者后交付为 compliant。
因此，本次不是“最终状态逐字段不变”的纯结构搬迁；它在保持业务口径和 Prompt 不变的
前提下，修复了旧聚合器的错误覆盖。该偏差在本报告中明确记录，不作为模型随机性或性能
结果隐藏。

## 正式业务入口

隔离验收使用临时 SQLite 和脱敏固定资料，不读取 `.env`、PostgreSQL 或医院源库。仅将
物理资料读取替换为固定 fixture；正式 worker、Running/Final 门面、prepare、统一执行
引擎、会诊 episode executor、结果保存和 Canonical Envelope 均使用生产代码。

覆盖入口：

1. 单病历单规则任务；
2. 两病历并行的病历池批量任务；
3. 带 `sample_pool_id` 的客户样本验证叶子任务。

三个入口均满足：

- `LUXIAN_0609_UNIFIED_ENGINE_ENABLED=true`；
- 实际 Native 阶段事件为 `completed`；
- 保存后的任务结果 `metadata.executor_key=consultation_quality`；
- 相同病历的 status、reason、客户事实、子结论和证据坐标一致；
- 没有 legacy、pack fallback、bundle fallback 或 LLM fallback；
- Canonical Envelope 已保存，证据使用既有安全引用，不泄露内部文书 ID；
- `executor_key` 只保留在内部任务诊断元数据，不进入 Canonical 客户合同。

本阶段没有把历史深度审计接口冒充为正式单病历入口；它仍属于旧兼容链，不计入上述三个
入口的一致性证明。

## executor_key 运行溯源

`aggregate_luxian_0609_orchestrated_results()` 仅从已经校验的
`FamilyUsageAttribution` 投影规则到 `executor_key`：

- 没有归因的规则不会被伪造 executor key；
- 非法归因、同一规则重复归因和既有键冲突均直接抛出 `ValueError`；
- 异常沿 worker 失败链阻止任务完成和 Canonical 写入，不会被解释成 `data_gap` 或
  `uncertain`；
- 不改变状态、原因码、客户事实、证据、Prompt 或 executor type。

## 真实模型性能

在隔离基线 worktree 与候选代码之间交替执行 10 对、共 20 次真实模型调用。固定提供商为
Alibaba DashScope，模型为 `qwen3.7-flash`。病例内容为脱敏合成会诊材料，不连接业务
数据库。

| 指标              |        基线 |        候选 |    变化 |
| ----------------- | ----------: | ----------: | ------: |
| 调用次数          |          10 |          10 |       0 |
| 每次 HTTP attempt |           1 |           1 |       0 |
| 每次输入 Token    |        1133 |        1133 |       0 |
| 输入 Token 合计   |       11330 |       11330 |       0 |
| 输出 Token 合计   |        2211 |        2210 |      -1 |
| API 中位耗时      | 2054.659 ms | 1914.026 ms | -6.845% |
| 端到端中位耗时    | 2062.874 ms | 1922.089 ms | -6.825% |

10 对 Prompt 均逐字符一致；20 次均未使用 mock、retry 或 fallback。候选输入 Token 未
增加，中位耗时优于基线，满足“不超过 10% 回归”的批准门槛。

## 状态偏差的零网络复放定位

真实调用的状态分布为：基线 10/10
`technical_error/model_invalid_output`，候选 10/10
`compliant/requirement_satisfied`。为排除模型随机性，使用双方首个原始响应做零网络交叉
复放：

- 基线响应交给候选代码：compliant；
- 候选响应交给基线代码：technical_error。

两侧在最早公共阶段均满足：

- JSON 合同解析成功，顶层只有 `episodes`、`non_target_refs`、`unresolved_refs`；
- episode 事实归约成功；
- `RuleDecision` 为 `requirement_satisfied`；
- `fact_refs` 数量为 1；
- Binding 成功。

最早分叉发生在客户展示事实合同边界。B1 基线聚合器把通用投影无法识别的会诊 facts
加入 `incomplete_consultation_rules`，随后强制覆盖为 `model_invalid_output`。候选由
`consultation_customer_projection.py` 验证并剥离内部标识，再交给统一 Finalizer，保留
执行器已经确定的 compliant 状态。

这证明变化来自旧聚合器错误覆盖被移除，不来自 Prompt、模型输出合同、会诊语义或
Binding 口径变化。严格意义上的“最终状态完全等价”没有成立；批准目标中的“业务口径与
Prompt 不变”和“聚合器不再拥有会诊业务判断权”已经成立。

## 回归结果

- B3 聚焦测试：6 passed；
- B3 与相关主链组合：254 passed；
- 全部 `test_luxian_0609_*.py` 加 B3 集成测试：4317 passed，38 个既有 warning，
  34.93 秒；
- B3 文件 Ruff：通过；
- `git diff --check`：通过；
- 独立代码审查：GO，无 P0/P1。

`npm run lint` 在本项目中包含 `eslint src --fix`，会修改当前属于用户的前端脏改动；本次
后端闭环没有运行该破坏性检查。提交前只对本次精确暂存文件执行编码门禁。

## 公开边界与剩余风险

- 没有数据库迁移；
- 没有修改 API DTO 或前端；
- 没有修改 Canonical 结果结构；
- 没有新增执行引擎、fallback、状态机、注册中心或摘要字段；
- 没有给 DTO、Prompt、trace 或临时结果增加 SHA/digest；
- 基线隔离 worktree 未删除，避免未经确认执行文件删除。

非阻塞风险：非法 attribution 已有聚合层单测和 worker 调用链审查，但尚未增加“正式
worker 失败且 Canonical 不写入”的端到端负向测试。当前异常路径是 fail-closed，不影响
B3 合入；若以后修改 worker 的异常收敛合同，应把该反例补成独立小闭环。

## Goal 退出判断

020–023 已完成：正式链冻结、客户事实校验迁出聚合器、episode executor 选择真实
`fact_refs`、公共证据投影、三业务入口一致性、全量回归及真实模型性能验收。当前 Goal
可以关闭。后续规则族迁移和两个 6000 行文件的治理必须另立任务，不在本提交中继续扩展。
