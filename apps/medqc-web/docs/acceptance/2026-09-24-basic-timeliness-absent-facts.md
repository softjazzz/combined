# P1-A01：基础时限族合法无独立 facts 结果的公开接收

基线 `80576bf4b` 的真实执行链路复现：原始 004 空抢救记录与空有效医嘱返回 `not_applicable/trigger_absent_complete`，无 `customer_display_facts`；经 native → Binding → Aggregator 后，在 `CanonicalResultStore.replace_for_job` 的公开读取入口抛合同 `ValueError`。同一红测覆盖 004 来源不可用、未决医嘱缺字段和原始 006 未成熟，均为合法无 facts 决策而在保存时被拒绝（4/4 红）。

修复仅在已发布接收边界利用规则 ID、已裁决状态及原因码识别可不带独立 facts 的分支；Store 向该边界传递既有上下文，不补造 facts，不更改原生判据或状态。原始 001/002/004/005/006 的合成 native 固定输入共 10 种无 facts 形态已完成 SQLite 保存加载，状态、原因码及空公开证据不变，LLM 调用和 Token 为 0。原始抢救内容规则 `LX0609-09-01-02` 来自独立原生入口并发布内容 facts，未纳入无 facts 例外。

合规、不合规及应有独立事实的缺口结果缺 facts 仍拒绝；带内部字段的事实仍拒绝；缺状态原因上下文的直接读取仍拒绝。修正后新测试与相邻公开合同共 111 项通过，Ruff 通过。`test_luxian_0609_native_basic_timeliness.py` 前 94 项通过，下一项因隔离 `DATABASE_URL=127.0.0.1:1` 的旧 fallback 试连失败，未宣称该宽组通过。未使用客户数据库、真实模型或真实病例，临床签收未覆盖。
