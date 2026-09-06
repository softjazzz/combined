# LX0609-072 转科文书 24 小时观察窗修复验收

## 问题与范围

唯一转科医嘱存在而转入或转出记录缺失（或仅为历史记录）时，原实现直接输出
`non_compliant / required_document_missing`，没有使用任务冻结的评价终点确认 24 小时
观察窗已经结束。这会把尚未到时限的病历提前判为缺陷。

本闭环只修改 072 的评价终点资料链和判定，不改变 073 的文书存在性口径，也不修改
Aggregator、Finalizer、结构映射、客户 Renderer、API 或数据库合同。

## 批准后的状态语义

在唯一转科医嘱已确认、且所需转入/转出记录缺失或仅为历史记录时：

- 评价终点精确早于 `order_time + 24h`，或只有无法证明越过截止时点的日期：
  `not_applicable / evaluation_window_not_mature`；
- 评价终点缺失、重复或与医嘱时间冲突：`data_gap`，分别使用
  `authoritative_time_missing` 或 `authoritative_time_conflict`；
- 评价终点到达或超过 24 小时：
  `non_compliant / required_document_missing`。

073 仍是存在性规则：缺少当前转入或转出记录立即是
`non_compliant / required_document_missing`，不读取或等待 072 的观察窗。

## 实现边界

- `source_registry.py`：仅为 072 注册 `evaluation_context.horizon`；073 的资料合同未扩张。
- `evidence_snapshot_provider.py`：仅将 072 加入已有的冻结评价终点构造集合。
- `native_extended_document_execution.py`：复用既有的单一评价终点校验，将结果传给 072；
  072 的 `fact_refs` 同时绑定该终点资料。
- `transfer_documentation.py`：仅在 072 的缺文书/历史文书分支按 24 小时判断成熟度。

没有新增执行器、Bundle、状态机、Fallback 或证据投影实现。

## 回归证据

聚焦用例覆盖：

- 24 小时前缺转入记录为 `not_applicable/evaluation_window_not_mature`；
- 到达 24 小时后缺转入记录为 `non_compliant/required_document_missing`；
- 评价终点缺失和重复冲突为 `data_gap`；
- 073 在未成熟终点下仍保持立即缺文书；
- 生产 `build_luxian_0609_evidence_read_session()` 会为 072 构造并保存
  `evaluation_context.horizon`，不是测试夹具或快照创建时间的隐式替代。

执行：

```powershell
py -3.10 -m pytest -q backend/tests/unit/test_luxian_0609_native_extended_document_execution.py backend/tests/unit/test_luxian_0609_evidence_snapshot_provider.py -k '072 or 073 or evaluation_horizon'
```

结果：40 passed。

完整两文件回归在并行工作区中暴露既有 068 失败：
`test_068_automatic_discharge_preserves_canonical_customer_delivery` 当前因同工作区的
`canonical_result_finalizer.py` / Aggregator 并行变更输出 `technical_error/model_invalid_output`。
072 聚焦集通过；068 不属于本闭环白名单，也未在本提交中处理。
