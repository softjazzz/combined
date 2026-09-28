# V3.6 评分申诉引用审计

## 范围与结论

本结论只覆盖后续评分申诉所需的引用合同，不实现申诉创建，也不改变当前计分语义。评分事实来源必须是 Canonical Envelope 链，不使用 `ModernCaseQcReadOnlyPanel` 对应的 `QCResultBiz/qc_results` 兼容链。

当前 `CaseScorePanel` 可以显示按现行默认标准重算的分数，但响应不足以冻结“用户看到的这一份结果 + 这一版标准”：

- Canonical 单病历 DTO 已返回三坐标选中的 `root_job_id`、`envelope_id`、`rule_set_key`、`rule_set_version`；见 `backend/app/services/custom_qc_workspace_service.py` 的 `build_latest_single_record_result_dto()`。
- `scoring_service.score_case()` 读取该 DTO 后只向前端搬运 `job_id`、规则集引用和计分值，遗漏了 `envelope_id/root_job_id`。
- 评分标准详情本身同时包含 `version_seq` 和 `updated_at`；`score_result()` 只返回 `standard_id` 与 `standard_updated_at`，未返回 `standard_version_seq`。
- `src/api/scoring.ts` 的 `CaseScoreScored` 已声明 `standard_updated_at`，但没有 `standard_version_seq` 和 Envelope 引用。
- `CaseScorePanel.vue` 当前只展示标准名称与满分；其响应校验也没有要求 `standard_id/standard_updated_at`，因此这些字段缺失时仍可能展示分数。

结论：现状适合只读展示，不足以作为评分申诉的并发控制或审计快照。

## 后续固定合同

计分成功响应应在现有分数、等级和扣分明细之外返回两个结构化引用：

```text
result_ref = {
  envelope_id, root_job_id,
  institute_id, patient_id, visit_id,
  rule_set_key, rule_set_version
}
standard_ref = {
  standard_id, version_seq, updated_at
}
```

UI 仍可显示后端已验证的分数；计分依据至少显示标准名称和可辨识的标准版本（`version_seq`），并保留 `updated_at` 作为提交时的精确 CAS 值。任一申诉引用缺失时不得用页面状态补齐，也不得开放评分申诉按钮；这不应把已经成立的只读分数伪装成 0。

后续创建评分申诉时，客户端提交上述两个引用及所见分数。服务端须在同一数据库事务内：

1. 以 `envelope_id + root_job_id + 三坐标` 回读精确 Canonical Envelope，禁止重新选择“最新结果”。
2. 以 `standard_id` 回读精确评分标准及组、条目，并核对 `version_seq + updated_at`。
3. 核对该标准仍是请求场景的当前默认启用标准；任一引用变化返回 409，要求刷新后重试。
4. 用该 Envelope 与该标准重新计分，并把结果引用、标准引用、分数、等级、扣分明细冻结到申诉快照；不能仅信任客户端分数。

`rule_set_version` 是 Canonical 结果的规则版本，`standard.version_seq` 是评分标准自身的 CAS 版本，两者不是同一版本轴。当前计分明确按“最新 ready Canonical 结果 + 当前默认评分标准”重算；**不得自动要求评分标准的规则集版本与 Canonical `rule_set_version` 相等**。本批只为后续评分申诉固定引用，不改变这一计分口径。

Canonical Envelope 当前没有 `run_number`。若后续评分申诉必须带任务运行号，应由服务端通过 `root_job_id` 的权威任务运行映射解析并冻结；前端不得从当前任务、路由或显示顺序推断。

## 同事务标准读取

`scoring_standard_service.py` 已有可复用的 session 内部构件：

- `_standard_row(session, standard_id, for_update=False)`：按 id 读取标准，可选行锁。
- `_groups_items(session, standard_id)`：在同一 session 读取项目组与条目。
- `_detail(session, row)`：组合完整标准，包含 `version_seq` 与 `updated_at`。

现有公开 `get_default_standard(scene)` 会自行创建和关闭 session，不可嵌入申诉创建事务；`_write_transactional_detail()` 也是自持事务的写入外壳，不是可注入的读取 helper。

后续实现应在 `scoring_standard_service.py` 增加一个显式 session 参数的内部/受控 helper，例如 `get_default_standard_in_session(session, scene, *, for_update=False)`，内部复用 `_detail()`。申诉创建事务应调用该 helper，不能在事务中再调用 `get_default_standard()` 打开第二个 session。若按 `standard_id` 回读，则复用 `_standard_row(..., for_update=True) + _detail()`，并在同一事务内核对它仍是当前默认标准。

## 后续测试门禁

- 计分服务：成功响应完整返回 `result_ref` 与 `standard_ref`；Envelope 或标准在读取期间变化时失败关闭。
- 前端 API：`scored` 缺 `envelope_id/root_job_id/standard_id/version_seq/updated_at` 时不得开放申诉，不用空字符串或当前页面状态补齐。
- 面板：展示标准版本；切换三坐标、场景、Envelope 或标准引用后清除旧申诉上下文并丢弃迟到响应。
- 创建服务：标准 `version_seq`、`updated_at`、默认状态或 Envelope 引用任一变化返回 409；同事务回滚不留下半条申诉。
- 兼容性：专门覆盖 Canonical `rule_set_version` 与评分标准创建时规则版本不同但仍按当前标准正常重算的用例，防止误加版本相等门禁。
