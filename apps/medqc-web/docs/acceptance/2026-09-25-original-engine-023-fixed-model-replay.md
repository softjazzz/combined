# 原始 LX0609-03-01-04：固定模型响应跨提交回放

基线 `29fb46569`，现行对照 `6bf5c8306`。新增的 `backend/tests/fixtures/luxian_0609/consultation-023-engine-replay.json` 只有合成会诊、病程和两条受控模型响应；不连接病例库或模型，不含患者资料。回放使用现有 `backend/scripts/verify_consultation_family_acceptance.py`，直接运行会诊执行器、RuleDecision reducer 与正式聚合出口。

初次比对曾出现一次 Prompt 不等。排查发现离线回放器仍把会诊意见冻结事实写到默认 `backend/data/luxian_0609_opinion_freeze/`，相同合成 visit 的旧事实有机会改变下一次受控响应的消费；不能单凭这项机制断定初次差异的唯一原因。现在每次 `run_replay` 都用独立临时冻结目录，并恢复原环境变量；不改生产冻结合同。旧的 `consultation-family-replay.json` 使用已过时的一阶段响应形状，独立空目录中也不能消费完两条响应；保留该历史夹具，但把五项现行回放器测试切到新的 023 夹具。

在两个独立检出及隔离冻结目录下，固定输入/响应的正式变体比较结果为：Prompt 字节相同、两边各 2 次逻辑模型调用、各 38 Token；唯一的 023 结果均为 `compliant / requirement_satisfied`，公开事实、事实引用数及证据坐标逐项相同。隔离后的双进程比较与聚焦测试中连续两次回放均未复现 Prompt 差异。聚焦的现行回放器及隔离回归 **6/6 通过**，Ruff 通过。

该比较只覆盖一条**合成的正常模型响应分支**，回放器的公开比较不含完整结论/建议文本，也没有真实模型、客户 PG 或独立临床答案。原始规则保护集、其他语义族和客户联机验收仍按主计划待验；不得据此宣称 LX0609 整体医学准确率或 A 阶段关闭。
