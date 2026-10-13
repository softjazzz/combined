# 2026-10-08 化疗 N13 不完整医嘱可能归属修复

工作树 `F:/MedQC-worktrees/qc-fix-chemo-v2-20261008`，限定 `LX0609-05-02-01` 缺字段与完整事件并存的路径。被独立审计阻断的版本为 `df3ea6837225c85de81fe5fd9929853feeadb599`，不把该版本开发159项通过称为独立验收通过。

## 已确认反例

独立证据 `F:/MedQC-worktrees/review-artifacts/chemo-n13/results-independent.json`：同药同日两条不同医嘱，一条完整130mg，另一150但缺单位，只有一条120mg病程。正反两种排列均被旧新增守卫判 non_compliant/dose=mismatched/unresolved=0，独立冻结预期 data_gap/不能确认剂量不一致。原父版本 data_gap。根因是先把不完整事件从待比较列表排除，又仅按不同药名数量判独立，漏掉同药的竞争医嘱。不是130/150/120三值的特殊问题。

## 最小修复与责任边界

比较仍由原剂量/原单位算法负责，N01/N07不改。保留所有完整和不完整医嘱的已知药名及处方日期描述；每个完整事件的候选片段在进入字段比较前，对其余所有医嘱检查可能归属。字段不完整不能作为排除理由；同药同日、缺药名或缺日期的竞争事件仍可能拥有该片段，完整事件计 unresolved，缺字段事件计 missing_order_event_count，未比较字段全部unknown。

只有明确不同已知药名且局部片段未提另一药时，才能按药物身份排除。若片段还含另一目标药，日期不能补足药物与剂量局部关系，仍拒绝独立归属。若同药或药名未知，只有唯一可信临床日期明确匹配完整事件、且明确不匹配竞争事件的已知日期，才排除竞争事件；其他情形均保留可能归属。剂量与途径是待检查字段，不用它们不一致来反向证明身份。

可信日期仅取正文明确临床日期，或“今日/当日”加record_time/record_datetime。单独文书记录时间不能证明药物给药日期，submit_time/submit_datetime也不用于归属排除。多临床日期不能冒充唯一日期。此限定仅用于新归属守卫，不修改既有单事件时间比较口径。

实际加载合同：inpat_drug_order可加载order_id；daily_course_record只有document_id、临床文书时间、正文及作者等，没有order_id/linked_order_id。当前无可靠跨表事件ID合同，不虚构字段，不把document_id等同order_id；仅两条医嘱有不同order_id不足以给病程建立归属。

不同药明确独立的不一致继续non_compliant，附真实缺字段；完整目标药在完整病程确实未出现的既有分支保留。只有未能独立归属时才data_gap，不把全部缺字段批次统一吞成资料不足。公开事实合同仍由原mapping验证，本次不改mapping或Renderer，不改source reader和其他族。

## 冻结预期与验证

新20项前后排列预期已先于运行冻结在 `.tmp/chemo-closure/n13-owner-expectations.json`，SHA256 `bbf89248a47b239b0d4689c83177397e2e650cfa88aaa5d4c8178899993a6d7a`；包含原40项的60项测试备份 `n13-owner-frozen-tests.py`，SHA256 `606393ff6ea95a7868bed1a818b5890761c97798bbaa9e46686129e1b7f73c45`。新增覆盖同药同日、同药异日明确/相对日期、单独文书时间、仅提交时间、多临床日期、缺药名同日/异日、缺日期、只有医嘱ID而病程无link；原不同药独立NC及真缺目标NC保护不改。

已获唯一测试槽，固定被阻断 `df3ea683` 源码跑新20项，14 failed / 6 passed；仅临时切换自有执行器文件，finally恢复修复源码并验证SHA256 `ceb2de8299f24e001398a3c89f6d63fc81d9ee96760e1def471f483663804b52`。新20项加原40项专属及旧round4/关联/mapping92项共152 passed；显式round2化疗27项passed，总179通过，无deselected。原40项预期未改，SQLite新Session回读保持状态、理由、findings及精确事实。Ruff三份Python文件通过。XML保留在`.tmp/chemo-closure/n13-owner-red.xml`、`n13-owner-green-protection.xml`、`n13-owner-round2.xml`。全部测试/静态进程结束，释放测试槽。

前端源码/配置未改，Lint沿用本工作树0 errors/1214 warnings；前端全量不重复跑。编码及Husky提交门禁等待root串行发令，不能同时启动共享lint-staged stash。真实模型、PG、环境文件、网络均不访问。后续固定SHA需独立复核，TP-D02/03仍只保留设计未实施。
