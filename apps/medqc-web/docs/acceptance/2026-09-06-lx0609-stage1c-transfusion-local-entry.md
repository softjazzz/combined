# LX0609 阶段 1-C：输血族本地三入口验收记录（候选 `938497a57`）

## 范围与入口边界

本地固定资料已通过；业务三入口仅覆盖当前客户策略允许执行的 `043–048`：单病历工作台、两病历批量工作台、客户样本验证。每条都通过正式 detached worker，实际调用链为：

```text
prepare_luxian_0609_execution
→ Luxian0609ExecutionEngine
→ executor_registry[transfusion]
→ native_transfusion_execution
→ Binding / Finalizer / Canonical 保存与 latest-result API 回读
```

测试隔离医院资料读取、病历 Bundle、模型响应和临时 SQLite，并使用测试认证依赖、授权检查 stub 及固定运行配置；不替代路由业务、worker、统一引擎、输血执行器、聚合器或保存逻辑。固定夹具均为脱敏合成资料，不是客户真实病例，因此本记录仅证明本地主链与接口契约，不能替代最终客户环境验收。

## 043–048 本地验收结论

- 统一开关为 `LUXIAN_0609_UNIFIED_ENGINE_ENABLED=true`；每次实际引擎 batch 均为 `(("transfusion", (rule_id,)),)`，无 `legacy`、`llm_fallback`、`pack_fallback` 或 bundle fallback。
- `043–048` 各自执行单病历、两病历批量和客户样本三条入口；共记录 24 次统一引擎调用（6 条规则 × 4 个实际执行病例：单病历 1、两病历批量 2、客户样本 1）。同一规则三入口的 Canonical `status`、`reason_code`、`customer_display_facts`、`criterion_results`、客户文案和证据坐标集合一致，并均从持久化后的 latest-result API 回读。
- 每条合成资料均产生预期的 `compliant / requirement_satisfied`，不是以三个相同 technical error 充当一致性通过。
- 证据按集合验收，不依赖数组顺序；要求的文书 ID 必须全部出现：043=`TX-BLOOD`、`TX-LAB`，044=`TX-BLOOD`、`TX-APP`，045/046=`TX-BLOOD`，047=`TX-BLOOD`、`TX-COURSE`，048=`TX-BLOOD`、`TX-SURGERY`、`TX-ANES`、`TX-POST`。
- 043 夹具显式提供九项 `labtest_item_report` 与输血前报告时间；避免以 `labtest_master` 摘要误充九项明细。
- 044、046 都触发受控语义调用，共 8 次固定 stub 调用；每条规则在三入口中的调用次数为 4（单病历 1、两病历批量 2、客户样本 1），同规则 Prompt 完全相同。这里记录的是固定 stub 返回的 `100/10/110` token 记账，用于检测入口重复调用，不是实际模型 Token 性能结论。
- 047 固定输血结束时间 `2026-08-20 18:00:00` 与评价时间 `2026-08-20 19:00:00`，确认 `elapsed_hours=1.0`。

## 041、042、049 的正式策略保护

- 041、042 由当前客户运行策略在工作台创建任务前拒绝：HTTP 422，且没有 `Luxian0609ExecutionEngine.execute` 调用。它们不是“客户三入口业务通过”，而是已验证的客户策略排除。
- 049 在 `prepare_luxian_0609_execution` 中仍会被 phase 分区为 `not_executed`，原因码为 `policy_definition_pending`，没有 native executor batch；但当前工作台客户 scope 在创建任务前又将 049 过滤为空规则集，实际返回 HTTP 422、零派发。因此不得声称 049 已生成正式的 `not_executed` 任务项。
- 049 的 direct native 组件测试仅覆盖“无已实施输血触发”时的 `not_applicable / trigger_absent_complete`，不属于三入口业务验收。已实施输血下的 strict-facts 遗留问题保持独立阻塞，不使用 `xfail` 或 `skip` 伪装通过，也不在本轮修改生产 scope。

## 实测命令与结果

```powershell
Set-Location D:\LLM\LX888\apps\medqc-web\backend
py -3.10 -m pytest -q tests/integration/test_luxian_0609_transfusion_family_convergence.py
```

实现方结果：`11 passed, 15 warnings in 20.66s`。主协调 Agent 在固定候选上独立复跑：`11 passed, 15 warnings in 21.99s`。六条在用规则累计实际引擎派发 24 次，受控模型调用 8 次；warnings 为既有 FastAPI/Pydantic/SQLAlchemy 弃用告警，本测试未新增生产代码。

## 仍需完成

1. 候选版本部署至客户环境后，以真实脱敏病例执行 043–048 的三入口验收，并复核真实文书坐标与客户展示。
2. 049 是否应该在客户入口直接拒绝，或创建 `not_executed` 任务项，是独立产品策略与体验问题；本阶段保持既有行为。
3. 真实模型的调用、Token 和多轮中位耗时比较需另按固定协议执行；本地 stub 不构成真实模型性能验收。
