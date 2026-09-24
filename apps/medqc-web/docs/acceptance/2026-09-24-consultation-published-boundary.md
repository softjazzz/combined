# 原始 LX0609 会诊族已发布事实读取边界

## 身份与故障

起点 `1c9a5f865`，按 `docs/0602/luxian_0609_formal_rule_catalog.csv` 确认原始 020–023 分别对应 `LX0609-03-01-01` 至 `LX0609-03-01-04`。四条均属于正式目录 001–049。正式计划目前仅派发 023；020–022 因会诊来源合同暂停，仍交付 `not_executed/policy_definition_pending`，本次不恢复执行。

旧 Canonical 读取把已发布会诊 facts 再交给 `safe_consultation_customer_display_facts`。023 已发布基本计数形态附加 `source_document_ids` 后仍被接受，并静默删除该内部字段。逐建议 `opinion_refs`、`execution_refs` 也能沿内部投影路径被转换。修复后读取使用会诊族独立公开 JSON 校验：合法值逐值返回，私有引用、额外/缺失字段、错误类型和无效嵌套引用受控拒绝。首次发布继续使用原内部投影；Finalizer 复用其验证结果，避免第二次投影。未改原生执行器、Prompt、门控、医学状态和证据投影。

## 公开形态盘点

- 021/022：语义汇总五字段；早期发布可不含 `episode_results`，新形态可含逐次状态，且每项可有合法时间和标题。公开形态不含顶层 `source_document_ids` 或逐次 `source_document_id`。
- 020/023：执行计数、`verification_kind` 与 `relation_state`；020 可带 `recommendation_results`，两条可带公开 `recommendation_evidence`。逐建议仅接受 `opinion_evidence`/`execution_evidence` 中既有 `src_` 安全引用，仍复用公共引用形态校验；拒绝顶层 `source_document_ids`/`source_document_refs` 和嵌套 `opinion_refs`/`execution_refs`。
- 023 既有三字段 `consultation_execution_too_generic` 形态继续接受；020–022 既有 `consultation_assessment` 形态继续接受。旧形态中内部 ID 仍由首次发布剥离，已发布读取严格按公开键集核验。023 的历史 `relation_state` 值保持原有兼容集合。

公开校验没有调用内部 `_safe_*` 投影；长度/数量上限仅沿用原合同：逐次和总计数 100、逐建议 96、每组安全引用 8，没有新增限制。相对基线新增生产代码在既有会诊事实模块约 135 行、Finalizer 约 11 行，均低于单文件新增 200 行门槛。事实合同仍由会诊族模块持有，Finalizer 只做一个族入口和发布事实复用。

## 固定输入与验证

- 新增集中测试 18 项：各公开/legacy 形态先由旧首次投影发布，再做逐值读回；每条顶层内部 ID 污染拒绝；023 的两个嵌套私有引用、非法安全引用和顶层额外引用拒绝；隔离 SQLite Canonical Store 写读原值并在嵌套污染后受控拒绝。023 固定已归约决策在 Finalizer 内部投影调用恰好 1 次；020–022 正式暂停链仍零模型调用。
- 023 固定合成会诊意见和病程执行文书，加两次受控模型响应，经 native → Binding → Aggregator，保持 `compliant/requirement_satisfied`，客户证据仍定位两份文书，LLM 2 次、32 Token。原生绑定的相邻正例和模型合同失败聚合例单独 2 项通过。
- 聚焦及相邻会诊/Finalizer 105 项通过；`ruff check`、`compileall`、暂存编码检查和 `git diff --check` 为提交前门禁。
- 扩大到整个 `test_luxian_0609_native_consultation_episode_execution.py` 时共 381 项中 350 通过、31 失败，失败均在该未修改的大文件，故扩大组不记为通过。追查一个代表用例 `test_021_022_state_table[vague-clear]`：在独立 `1c9a5f865` 检出通过；当前树默认冻结目录下失败；将 `LUXIAN_0609_OPINION_FREEZE_DIR` 指向新的私有临时目录后当前树也通过。宽组运行曾生成未跟踪的默认 `backend/data/luxian_0609_opinion_freeze/v.json` 等文件，同一 visit 的意见冻结读回污染后续测试。不能声称 31 项是基线既有，也不能据此归因本次医学执行器回归；未再重复宽组，未更改判据/测试预期。

## 限制

上述均为固定合成来源与受控响应，没有客户 PostgreSQL、真实模型、真实病例业务签收或浏览器验收。扩大原生组须在隔离冻结目录下重新设计顺序无关的运行方式，现不作为本任务门槛。测试生成的 `backend/data/luxian_0609_opinion_freeze/` 未纳入本次提交。020–022 暂停状态及 023 临床建议判据保持原状。
