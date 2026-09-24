# 核查明细类型的单一合同与交付验证

基线：`1c9a5f865`。范围仅为引擎阶段 C 的核查明细交付合同，不调整任何医学执行器、Prompt、模型、门控或并发。

## 已复现问题与修复

`RuleCriterionContract` 支持 presence、timeliness、coverage、completeness、consistency、text_length、semantic_relation 七类核查；Canonical 的 `safe_criterion_results` 另维护三类白名单。固定受控规则经过 Engine、绑定、归约、聚合后，presence/timeliness/coverage/consistency 被保存边界剔除；当其为不合规结果的唯一解释时，实际 SQLite 保存抛出解释合同不完整，不能交付。

复用规则合同的 `CRITERION_KINDS`，删除保存层重复类型集合。没有新增规则特判，也没有改变未知类型拒绝行为。

## 验证

- 七类固定受控规则均经过 Engine → Binding/Reducer → Aggregator → 实际 SQLite Canonical 写读 → 客户 DTO → CSV。状态、原因码和非空核查字段保持一致；文书证据仍指向 admission_record/chief_complaint；模型替身始终只调用一次，保存和读取不新增调用。
- DTO 既有行为会省略空字符串字段，比较时仅排除这些空字段；Canonical 中核查明细保持完整原值。CSV 自带管理摘要，按正式明细表头核对规则编号、状态、原因码。
- 未知类型仍不可交付。扩展边界、规则合同、Finalizer 共 **94 项通过**；ruff 通过。
- 测试注入两条四段式测试规则的目录及执行器，不绕过实际 Store 校验。但这不是正式目录编译、任务 API、客户 PostgreSQL 或浏览器端到端验收；不据此宣布阶段 C 全部完成。

本轮无前端修改。集成树最近完整前端检查为 lint/type-check 通过、单测 1063 通过及 3 失败，不能写成全绿；本轮不重复执行无关前端测试。
