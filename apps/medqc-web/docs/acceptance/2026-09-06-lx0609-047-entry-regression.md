# LX0609-047 入口回归冻结（待窗口链路修复）

基线：`42c92fc79`。本记录只覆盖输血规则 `LX0609-047` 的客户正式入口；不改动
路由、worker、provider、native executor 或既有集成套件。

## 冻结范围

新增的 `backend/tests/integration/test_luxian_0609_047_entry_regression.py` 使用隔离
SQLite 和脱敏的 running 病历资料行，保留真实 API、detached worker、unified engine、typed
`transfusion` executor、Binding、保存及 Canonical `latest-result` 回读。

“三入口”是三种任务形状，并非三条不同 API 路由：

- `POST /api/v1/qc/sichuan/workspace/batch-jobs`：单病历、单规则；
- 同一 workspace route：两病历批量（回读病历 A）；
- `POST /api/v1/qc/sample-pools/{pool_id}/run`：单样本、单规则。

每种形状都只选择 `LX0609-047`，并断言引擎真实批次为
`(("transfusion", ("LX0609-047",)),)`。测试没有替换 worker、engine 或保存；唯一
资料替换是 evidence-session 的正式 `row_reader` seam。LLM client 一旦被调用立即
失败，冻结的调用数和 tokens 都是 `0`。

## 目标公共结果

所有断言均使用 typed 决策经 Canonical 映射后的状态/原因，不使用 native 内部 raw
reason：

| 情形                                     | 固定逐例 horizon | 目标 Canonical 状态 / 原因                      |
| ---------------------------------------- | ---------------- | ----------------------------------------------- |
| 已成熟且未记录评价                       | 2026-01-03       | `non_compliant / requirement_violated`          |
| 24 小时窗口未成熟                        | 2026-01-02       | `not_applicable / evaluation_window_not_mature` |
| 缺少可用 horizon                         | 无               | `data_gap / authoritative_time_missing`         |
| 输血结束时间无法解析                     | 2026-01-03       | `data_gap / required_field_missing`             |
| 早期事件已成熟且缺评价、较晚事件尚未成熟 | 2026-01-03       | `non_compliant / requirement_violated`          |

最后一行要求两个输血记录坐标都可从保存结果回读，防止最新未成熟事件遮蔽更早已成熟的
缺评价事件。测试同时比较三种任务形状的 customer facts、criterion results、客户结论及
资料坐标集合；资料缺口允许空集合。任务 JSON 保留脱敏夹具的 document id，保存后的
公共 Envelope 会将它转为 `src_*` 安全坐标，因此任务与保存层比较 source/field/time
三元组，三份已保存 Envelope 再比较完整安全坐标集合。
保存引用校验复用 `build_customer_safe_source_ref`，并断言所有 `src_[0-9a-f]{24}`
非空、不含原 document id；测试不自行计算 HMAC 或哈希。

## 固定时点与实际传递

测试在两个 route 模块的 `build_record_evaluation_horizon_snapshot` seam 固定逐病例快照，
目标是让 worker 向真实 `evaluate_running_final_bundle_input` 传递：已解析时为
`evaluation_as_of_date=<固定日期>, evaluation_horizon_policy=frozen_task_date`；无
horizon 时为 `None, disabled, authoritative_time_missing`。

夹具的 `record_scene`、workspace scope、sample-pool scene 与 bundle scene 都为 `running`，
因此 `task_frozen_date` 是合法的评价依据。两个真实 route 均调用 builder；创建的三个 job
id 各不相同，未复用幂等旧任务。worker 对三种任务形状共四次实际评估（两病历批量含两次）
均接收到预期的三元参数。夹具必须使用 `CaseRef.as_key()` 生成 snapshot `record_key`；手写
分隔符键会使 worker 的逐例 snapshot 索引未命中，不能作为 route/worker 缺陷。

## 验证记录

```powershell
cd D:/LLM/LX888/apps/medqc-web/backend
py -3.10 -m py_compile tests/integration/test_luxian_0609_047_entry_regression.py
py -3.10 -m pytest -q tests/integration/test_luxian_0609_047_entry_regression.py
```

实测：`5 passed, 15 warnings in 14.53s`。warnings 均为既有 FastAPI/Pydantic/SQLAlchemy
弃用提示。测试数据库位于 pytest 临时目录，未写入本机业务库；未发生 LLM 调用或 token
消耗。

主协调独立复跑本文件与既有输血族入口套件：`16 passed`（36.75 秒，15 条既有告警）。新 047 五种资料形状共经过 20 次真实 unified 执行（每种：单条 1 次、两病历批量 2 次、样本验证 1 次），新增 047 路径的模型调用和 Token 均为 0。真实模型和客户源库不在本次测试范围。

窗口实现提交：`bec27288f`。本记录只证明该窗口修复在本地三种正式任务形状的传递和保存；047 多次输血跳过日常病程评价的旧关联缺陷仍待独立修复，不能据此标记整条规则或整个输血族业务问题已清零。
