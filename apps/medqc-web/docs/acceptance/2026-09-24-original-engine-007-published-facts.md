# LX0609-02-01-03 已发布事实读取边界

## 问题与边界

`Finalizer.validate_luxian_0609_published_customer_display_facts` 曾把 007 的已发布 `customer_display_facts` 再送入内部事实投影。已发布 `interval_hours=1.234` 会被静默改成 `1.23`，使 Canonical Store 读取的事实不同于保存的事实。

本次只修读取与发布后复用：007 新增已发布 JSON 事实白名单校验，合法事实原样返回；非法字段、类型、NaN/Infinity、未按发布精度保存的数值受控拒绝。首次发布仍使用原 `_safe_007`，原生执行器、判据、状态映射、模型输入和规则目录均未改。聚合完成后的 Finalizer 复用已验证事实，避免第二次投影。新增生产代码约 114 行，职责留在既有 007 事实合同模块与 Finalizer 小分派，未建立新层。

## 冻结证据

- 合成 007 已发布形态覆盖：72 小时内、超时、按日截止、来源缺口、文书时间缺失、容量不足、不适用；带文书位置和秒数的增强形态保持原样。`72h+1s` 在纯已发布形态中可表示为 `interval_hours=72.0`，读取不按舍入值重判医学状态。
- 合成 native → Binding → Aggregator：72 小时整合规与 72 小时加 30 秒不合规，均保持状态、原因码、增强事实和证据路径；LLM 调用与 Token 均为 0。
- 隔离 SQLite Canonical Store：合法 Envelope 读回事实逐值相等；人为污染数值后读取受控拒绝。
- 已观察到的**既有发布缺陷**另有冻结测试：72 小时加 1 秒时，native/reduced 判 `non_compliant/threshold_exceeded`，旧内部发布投影先把 72.000… 小时舍入成 `72.0` 再以 `<=72` 拒绝，最终为 `technical_error/model_invalid_output`。本次不修改该发布判据，不能据此声称临界完整链路已修复；后续需独立处理。
- 主协调另行固定的 13 个本机候选仅覆盖 11 个 `not_applicable` 与 2 个 `data_gap`，不作为正常/超时临床实证。

## 验证与限制

`test_luxian_0609_original_007_public_boundary.py`、`test_luxian_0609_course_quality_freeze.py`、`test_luxian_0609_native_course_quality_execution.py`、`test_luxian_0609_original_005_006_public_boundary.py` 共 292 项通过。改动文件 `ruff check` 与 `compileall` 通过。未运行真实病例正常/超时临床验收、前端和完整批量任务；本修复不改变临床结论。
