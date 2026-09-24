# 原始 LX0609 危急值 052/053 已发布事实读取边界

## 身份、反例与改动范围

起点 `eccdfd144`。按 `docs/0602/泸县0609质控点-业务标准基线-v1.md` 第 84–85 行，原始 052 是报告后 6 小时内有危急值处置记录，053 是报告后必须有对应处置记录；内部 ID 分别为 `LX0609-06-04-01`、`LX0609-06-04-02`。正式 CSV 只覆盖 001–049，本次没有跨区间套用它的允许状态。

旧 Finalizer 已发布读取回落到内部 `safe_critical_value_customer_display_facts`。052 已发布 `actual_interval_hours=[1.23456]` 且事件 `interval_hours=1.23456` 会被静默改为 `1.23`。这证明读取重做首次投影，而非核验公开合同。此次在既有危急值事实模块增加独立已发布 JSON 校验，由 Finalizer 一个族入口调用；合法值原样返回，损坏公开事实受控拒绝。首次内部投影及其舍入保持原样，Finalizer 对整个族复用首次已验证 facts，`critical_value_customer_fact_status_is_valid`、原生执行、Prompt、门控、阈值和模型调用均未改。

## 公开形态与失败语义

- 052：检验结果明细缺失、观察截止资料缺失（两类 issue）、常规事件结果，以及观察窗口未成熟的 `evaluation_time` 或 `evaluation_date` 两种形态。053：检验结果明细缺失、常规处置存在性事件。两条无独立 facts 的合法 `None` 保留旧读取语义。
- 公开事件沿用首次发布的名称最多 20、事件最多 100、文本长度等限制；052 顶层 `actual_interval_hours` 旧投影没有长度上限，也允许有限负数，公开校验不新增加上限或重新判断医学合理性。已发布小时数只核验有限数和两位精度；不重新计算 6 小时是否超限。窗口日期/时间只检查公开形态与可解析性，不重算截止日和报告时差。
- 顶层内部键、嵌套额外键、错误类型、非有限数及多余发布精度拒绝。读取校验不调用内部 `_safe_052`、`_safe_053` 或 `_safe_events`，不剥键、不舍入。无效 Envelope 沿原解释合同 `ValueError` 路径失败。

相对起点新增生产代码为族模块 125 行、Finalizer 11 行，均未达到单文件新增 200 行门槛。既有模块继续拥有危急值展示事实合同，没有新层或通用框架。

## 固定证据与验证

- 新增集中测试 29 项：所有上述首次发布形态先由旧投影生成，再断言公开读回逐值相等；052 未发布精度、NaN、布尔值及内部键/嵌套污染拒绝；053 嵌套非法标志拒绝；读回时将内部投影替换为抛错函数仍成功。101 个（含负值）顶层间隔由旧投影发布并被读取接受，保护没有误加新长度限制。
- 固定合成血钾 `PH` 报告和观察截止输入，经 native → Binding → Aggregator：052 `not_applicable/evaluation_window_not_mature`，053 `non_compliant/required_document_missing`，公开 facts 与执行器首次发布值逐字段相等，客户证据等于既有选择文书投影；LLM 调用与 Token 均为 0。052 固定缺明细决策的 Finalizer 内部投影计数恰好 1 次。
- 隔离 SQLite Canonical Store 完整写读 052 合法 Envelope 事实逐值相等；污染事件小时数为 `2.3456` 后读取受控拒绝。没有访问客户数据库。
- `backend` 目录使用 `JWT_SECRET=isolated-test-secret-not-for-production-0609`、`DATABASE_URL=postgresql://test:test@127.0.0.1:1/test`：`py -3.10 -m pytest --confcutdir=tests/unit -q tests/unit/test_luxian_0609_critical_value_public_boundary.py tests/unit/test_luxian_0609_critical_value_result_mapping.py tests/unit/test_luxian_0609_canonical_result_finalizer.py --tb=line`，111 项通过。`test_luxian_0609_native_extended_document_execution.py -k 'critical_value or 052_'` 41 项通过。改动文件 `ruff check`、`compileall`、暂存编码和 diff 检查作为提交前门禁。

以上是代码合同及固定合成输入回归，不是临床真实病例签收、客户 PostgreSQL 或前端验收。前一任务留下的未跟踪 `backend/data/luxian_0609_opinion_freeze/` 不属于本次危急值改动，不提交也不删除。
