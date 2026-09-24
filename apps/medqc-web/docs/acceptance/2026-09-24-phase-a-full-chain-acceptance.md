# LX0609 阶段 A 两试点完整链验收接续卡

基线 `ce1e125284a18193d1638879c08ca657e5f4a4c7`，分支 `codex/lx0609-rule-id-integration`。仅验收抢救 `LX0609-09-01-02` 和病理 `LX0609-06-02-01`；不修改医学判据、Prompt、模型、CT、0916 或全局并发。当前状态：**技术交付链补证完成，阶段 A 尚不具备业务验收条件**。R01 真模型响应违反原子坐标合同，独立临床保护集合也尚未取得。

## 证据分层与矩阵

| 层次 | 输入/方式 | 要证明的事 | 当前状态 |
| --- | --- | --- | --- |
| 真实源候选 | 0910池 R01/P01/P02/P03，CDM只读冻结于私有快照 | 材料存在、候选数量和源字段 | 已完成；上游同步完整性未知 |
| 生产 Evidence Session | 同一三坐标调用当前 `read_luxian_0609_snapshot_source_rows`，`limit+1`，绑定同一会话材料 | 来源状态、截断和证据引用与生产路径一致 | R01/P01/P02/P03 已运行，所需源 `available/complete`、无截断；上游同步仍未知 |
| 原文事实核验 | 固定响应六个原子的坐标与源正文及实际发送正文逐字核对 | 引文坐标可复核 | 六项均不匹配，五项 span 长度还与引文长度不同；这是揭盲后的技术核验，不是独立临床审阅 |
| 抢救固定响应 | R01 当前配置/Prompt，最多一次模型请求，保存响应、用量和错误于私有文件 | 可重复模型侧抽取，隔离后续抖动 | 已调用一次并冻结；模型原子合同失败，不能形成正常语义结论 |
| 执行与发布 | 同一会话调用真实执行器、Reducer/Finalizer | 状态/原因/事实/引用/规则身份只发布一次 | 四例已回放；R01失败闭环可重复，病理三例确定性发布可重复 |
| 保存与交付 | 隔离 SQLite Canonical 保存/读取，任务/latest/反馈/导出真实入口 | 可见结果一致，反馈绑定准确，失败不变临床缺陷 | 四例通过；仅证明同一发布结果的技术一致性，不证明临床判断正确 |
| 合成异常边界 | 缺字段、公开事实损坏、取消、保存/读取故障 | 技术失败与业务结论分离 | 两规则固定单测92通过；Canonical代表性4通过，均为合成边界 |
| 独立业务验收 | 客户/临床审核的真实正负、资料不足及旧保护集合 | 业务正确与零回退 | 未取得；本次技术闭环不代替签收 |

## 进行顺序

1. 固定当前代码、源资料和测试时点；源库只读，限制查询超时与行数，任何患者原文只放 `.tmp/0910-full-audit/*-private`。
2. 经生产 source reader 建会话并检查来源状态、截断和引用。局部查询 `complete` 仅是本次行数未超限，不证明上游同步完整。
3. 抢救 R01 调用前复核模型名、输入字段/字符数、输出上限与成本；保存响应/错误，随后从固定响应回放。病理无模型调用。
4. 用隔离 SQLite 核对执行、发布、读取、反馈和导出；合成异常单列，不混为真实病例证据。
5. 记录精确命令、退出码、差异和剩余风险。父代理复核后统一提交；阶段 B/C/D 不自动启动。

## 当前既有材料

- [源候选可用性报告](2026-09-24-phase-a-source-readiness.md)仅证明有限材料及病理函数离线执行，尚未穿过生产 Evidence Session。
- 私有候选和离线回放位于 `.tmp/0910-full-audit/phase-a-*-private*`，禁止提交。
- 生产reader脚本 `.tmp/0910-full-audit/phase-a-production-evidence-private.py` 在只读PG上对四例实际调用当前 `build_luxian_0609_evidence_read_session`，并私有冻结 reader 返回的原始行、截断标志、limit和材料引用。结果：R01抢救/医嘱各1；P01病理1/1；P02病理3/1；P03病理3/3。固定 `created_at=2026-09-24T12:00:00+08:00` 是回放会话时点，不是源数据实际抓取时间。R01按冻结行复建后 snapshot hash 一致。
- R01 模型预算：现有环境 `alibaba/qwen3.8-flash`，1份完整文书765字符，Prompt 1621字符，最多1次调用、4096输出 tokens，`enable_thinking=False`。实际只调用一次，Prompt 956 tokens、完成 451 tokens、共 1407 tokens；原响应、脱敏后请求和用量存于 `.tmp/0910-full-audit/phase-a-rescue-model-20260924-private.json`。没有重试或改模型参数。
- 无可用的已临床签收旧保护集合，不能声称 79 条零回退。

## 四例固定输入的逐层结果

源行与模型响应分别冻结后，`.tmp/0910-full-audit/phase-a-full-chain-private.py` 从固定 Evidence Session 经正式 `prepare_luxian_0609_execution`、聚合/Finalizer 回放，严格核对 R01 复用的模型 Prompt/参数与原调用一致；模型只由固定响应客户端返回，绝不再次联网。

| 候选 | 规则 | 原子/事件情况 | 归约与发布状态 | 发布原因码 | 调用/Token |
| --- | --- | --- | --- | --- | --- |
| R01 | 抢救 | 六原子坐标均不符合；执行器 `failure_kind=model_invalid_output`，字段全为 unknown | `data_gap` | `required_field_missing` | 真调用 1/1407；固定回放 1/0 |
| P01 | 病理 | 一事件，有报告 | `compliant` | `requirement_satisfied` | 0/0 |
| P02 | 病理 | 三事件：两项执行未证明，一项报告存在 | `data_gap` | `required_field_missing` | 0/0 |
| P03 | 病理 | 三事件，有报告 | `compliant` | `requirement_satisfied` | 0/0 |

病理执行器内部逐事件原因仍保留在公开 `customer_display_facts.events`：P02 是两个 `pathology_execution_unproven` 和一个 `pathology_report_present`。顶层原因变成通用的 `required_field_missing` 是既有 Reducer/发布合同，不是保存层丢失细原因。抢救执行器在无效响应时安全降级为资料不足；此次没有证明其正常有效响应下的真实医学判定。

`.tmp/0910-full-audit/phase-a-delivery-roundtrip-private.py` 使用上述真实输入发布结果，在隔离 SQLite 建立任务与 Canonical Envelope，调用真实 `CanonicalResultStore.load_selected`、`build_latest_single_record_result_dto`、任务安全投影、反馈保存及 CSV/XLSX/HTML 导出。四例的规则身份、状态、原因及公开事实从发布到保存/读取/latest一致，反馈绑定任务/病历/规则/原状态，三种导出与已保存结果的规则、状态标签、结论一致。该脚本不模拟待验收的 Canonical、DTO、反馈和导出合同，仅用隔离库替换真实客户库。HTML一致性不等于临床正确。

## 失败归因与验收限制

`.tmp/0910-full-audit/phase-a-rescue-atom-check-private.py` 对 R01 的六个 `present` 原子逐项验证。源正文和实际发送正文都为765字符且完全相同，六项指定坐标都无法逐字回取模型引文，五项的 `end-start` 与引文长度本身不相等。因此 **本次失败不能仅归因于隐私脱敏坐标偏移**；直接触发当前解析器的 `model_invalid_output`。这只定位一次真实模型响应的技术失败，不能据此推断模型总体失败率，也不能私自放宽证据合同。

后续若要关闭抢救规则业务验收，应另立限定范围评估模型原子坐标可靠性：在不改变医学判据的前提下，比较维持严格坐标拒绝与受控的唯一原文回定位等最小方案；必须先冻结新的真实正负与资料不足病例、独立业务答案，并验证引文唯一性、隐私和漂移，才可批准生产改动。此次未改 Prompt、模型客户端或执行器。病理三例也仍缺客户/临床独立签收，不能用当前程序输出为自身作金标准。

## 验证命令与结果

- `python -X utf8 .tmp/0910-full-audit/phase-a-production-evidence-private.py`、`phase-a-rescue-budget-private.py`、`phase-a-rescue-model-private.py`、`phase-a-rescue-atom-check-private.py`、`phase-a-full-chain-private.py`、`phase-a-delivery-roundtrip-private.py`：分别退出码 0。仅 model 脚本执行了一次真实外部调用。
- `python -m pytest tests/unit/test_luxian_0609_rescue_record_completeness.py tests/unit/test_luxian_0609_pathology_report_completeness.py -q --tb=short`：92 通过，退出码 0；其中有效响应成功分支和异常边界使用合成输入，不是临床病例。
- Canonical 聚焦：`python -m pytest tests/unit/test_luxian_0609_canonical_result_delivery.py -q --disable-warnings --tb=short -k 'two_published_pilots_keep_identity or rescue_non_compliant_safe_facts_survive or pathology_published_facts_commit'`：4 通过，102 项未选，退出码 0。
- 曾尝试把上述 Canonical 整个文件与两规则文件合跑，得到 127 通过、71 失败，退出码 1；失败堆栈以测试用假 PostgreSQL `test:test@127.0.0.1:5432/test` 无法连接为主，不能作为当前代码回归或全绿证据，也未改用真实客户库执行写入。聚焦验证和隔离 SQLite 回放另行列示。
- 私有脚本 Ruff：`python -m ruff check .tmp/0910-full-audit/phase-a-*-private.py --ignore E402` 通过；`E402` 仅因为脚本需先将本 worktree 的 backend 加到导入路径。没有生产代码变更，也没有额外前端测试。测试期间CT代理可能存在并行未提交修改；结果只归属本文明确列出的试点文件/路径，不能当作全树基线。

## 主协调验收结论

主协调亲读并独立运行固定响应全链、SQLite交付和原子坐标核验脚本，四例结果一致；独立执行两规则及Canonical代表性测试96通过、102未选。接受本次技术证据报告，不接受“阶段A全部完成/临床零回退”声明。R01正常真实语义路径失败且无已签收保护集合，A0/A4仍未通过，B/C/D不启动。未修改抢救医学判据或Prompt。
