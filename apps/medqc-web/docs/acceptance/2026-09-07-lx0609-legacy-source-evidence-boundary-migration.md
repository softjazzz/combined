# LX0609 legacy 来源级证据投影边界迁移验收

## 范围与结论

本次是严格行为等价迁移：将结果聚合器中仅服务尚未迁移旧合同的
`ReducedRuleDecision` 来源级证据投影迁入
`customer_evidence_enrichment.py` 的
`project_legacy_source_level_evidence()`。

聚合器仍负责结果装配：先使用既有 selected-document 公共投影；只有该函数返回
`None` 且规则未声明必须使用公开 fact-ref 证据时，才委托新的 legacy 投影函数。没有
新增 fallback、规则选择、状态机、注册表或来源白名单。

未修改状态、原因码、`fact_refs`、Prompt、API、持久化或前端；
`project_selected_document_evidence()` 的原有合同也未修改。

## 等价行为冻结

聚焦用例冻结了下列历史可达形状：

- 已引用事实自带有效 `source_document_id` 时直接投影；
- 事实未带单行 ID 时，仅在同一来源冻结材料恰有一行且含有效 ID 时补回；
- 多材料行不猜测，即使其中有可用 ID；
- 仅绑定 `observation.snapshot_ref` 时，同样只接受唯一材料行；
- 含换行的 ID、非法来源名均不投影；
- 去重后至多保留 8 条，顺序保持事实顺序。

新增源码守卫确认 `luxian_0609_result_aggregator.py`：

- 不含 `evidence_materials.rows`；
- 不含 `source_document_id`；
- 不再含旧私有函数 `_customer_evidence_from_reduced_decision`；
- 仅调用 `project_legacy_source_level_evidence()` 完成旧合同投影。

## 验证

在 `backend` 目录运行：

```powershell
py -3.10 -m pytest tests/unit/test_luxian_0609_result_aggregator.py -q
py -3.10 -m pytest tests/unit/test_luxian_0609_selected_document_evidence.py tests/unit/test_luxian_0609_transfusion_selected_evidence.py -q
py -3.10 -m ruff check app/services/luxian_0609/customer_evidence_enrichment.py app/services/luxian_0609_result_aggregator.py
```

本次实测结果：聚合器全量 **384/384** 通过；selected-document 与 transfusion
selected-evidence **36/36** 通过；迁移前/后来源级冻结子集 **7/7** 通过；两个生产
模块 Ruff 通过。

还应执行 `git diff --check`，并复核 diff 仅涉及本文件、两个生产模块及聚焦测试。

## 剩余风险

尚未迁移旧合同继续依赖来源级 `fact_refs` / `snapshot_ref` 的历史语义；本次刻意保留该
行为。未来迁移某条规则时，应让执行器绑定精确逐行 `document_refs`，由既有
`project_selected_document_evidence()` 投影，不能扩展来源级 fallback。
