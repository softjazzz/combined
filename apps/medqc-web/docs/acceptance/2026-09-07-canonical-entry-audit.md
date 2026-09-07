# Canonical 正式入口守卫复核

## 结论与范围

本次不修改生产代码、不改变兼容默认值、不删除旧链。补充三入口实际聚合调用的模式断言、禁止 legacy adapter 的哨兵，以及部分 ReducedDecision 缺失反例。

## 代码证据

- `luxian_0609/execution.py` 的 prepare 根据 `LUXIAN_0609_MAINLINE_RULE_DECISION_ENABLED` 显式设置 delivery_mode；设置类默认开启。aggregate 编排显式将 context.delivery_mode 传给聚合器。
- 生产调用经 `sichuan_qc_service.py` 或 `sichuan_qc/running_final_bundle_service.py` 进入上述公共编排；预发布 runner 也复用该编排。
- 聚合器 Canonical 分支不读取 legacy execution_results；缺少 ReducedDecision 且没有显式 Canonical 结果时生成 technical_error/decision_contract_violation。显式待发布结果仍允许 not_executed。
- 关闭主链开关后的兼容路径及聚合器 legacy_compatible 默认值仍保留。本次没有证明所有外部诊断调用可以删除，因此没有改默认值。

## 测试证据

在 backend 目录执行：

```powershell
python -m pytest tests/integration/test_luxian_0609_all_rules_three_entry_acceptance.py tests/unit/test_luxian_0609_result_aggregator.py -k 'three_entries or canonical_delivery' -q --tb=short
```

首次复跑：4 passed，18.63 秒。包含两个三入口场景和既有两个 Canonical 边界测试。

新增部分裁决缺失反例后执行：

```powershell
python -m pytest tests/unit/test_luxian_0609_result_aggregator.py -k canonical_delivery -q --tb=short
```

3 个边界案例：全部裁决缺失、部分裁决缺失、显式待发布结果。缺失项不能采用旧执行结果中的 compliant。

三入口场景经过生产路由、worker、隔离 SQLite 保存和 API 回读；每次聚合均断言显式 Canonical 模式，legacy adapter 被替换为触碰即失败的哨兵。每个场景要求至少三次聚合，避免空跑通过。

## 验收限制

医院资料、认证和模型传输使用测试替身；没有执行客户真实病例、真实模型性能比较或发布打包。不能据此关闭客户最终验收，也不宣称全部旧链已移除。模式开关关闭仍是显式兼容行为，不是 Canonical 缺裁决回退。
