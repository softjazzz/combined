# 2026-10-08 化疗 N13 撤除不可靠日期排除

限定 `LX0609-05-02-01` 的缺字段竞争事件归属守卫。本轮结论是**工程防误判通过，6个业务期望未达**；N13仍开放，不称整条N13、该规则或临床验收通过。未达的给药日期语义归属能力并入TP-D02/日期归属开放范围。

## 固定交付基线与原始答案

已集成基线为 `e256e8ea926f0bcb19cb000cd826dd781e157eaf`，只合入TP-D01，尚未合入N13。中间 `df3ea683` 和 `e8f7dcb746a413d7736986535939f00d1573dad3` 均未交付，不能把e8作为生产正常基线。

原业务oracle的三个明确日期场景各正反序共6例：正文明确4月26日给药、今日给药、部分医嘱缺药名但处方日在另一天；期望始终为non_compliant。完整医嘱130mg与另一150但缺单位医嘱竞争，一条明确120mg病程应有该能力，但当前无可靠事件归属结构。原冻结 `n13-owner-frozen-tests.py` 与审计oracle不改；测试只添加business_oracle标识，不改NC答案、不使用xfail、不新增默认排除配置。

六例在e256固定源码以及最终源码均**实际执行**：分别6 failed / 14 deselected，全部actual data_gap vs expected non_compliant。基线原本就gap，所以不能把撤除未交付e8日期推断夸大为生产状态回退，也不能以工程保护通过掩盖既有业务能力未达。

## 工程修复

独立e8审计的4种事项日期反例各正反序共8例：今日复查/明确日期复查与昨日或无日期给药混排。整篇正文里的任意日期不能证明该药的给药日期；e8和父df3都错误确认剂量不一致。

仅撤掉N13 owner守卫的日期提取和日期排除。所有完整与不完整医嘱仍参与可能归属；同药或缺药名竞争保持unknown/unresolved/data_gap。已知不同药名且局部片段不含另一药时仍可排除该竞争事件，保留不同药明确独立non_compliant及完整病程真缺目标药non_compliant。

没有加入复查/昨日等关键词清单，不改原剂量/单位算法、原时间比较器、公开mapping或Renderer，不发明跨表医嘱ID，不新增模型、PG或网络调用。当前daily_course_record无结构化实际给药日期—order_id绑定合同，文书时间和医嘱计划时间不能补足它。

## 分轨实证

- 工程日期事项反例：固定未交付e8源码红8 failed；撤日期后全部通过。正式执行→Binding→Finalizer及隔离SQLite新Session回读保持事实、状态、理由和findings。
- 工程聚焦：160 passed / 6 business_oracle deselected，含68个本任务工程测试和92个旧合同/剂量保护。显式round2化疗节点27 passed，工程共187项通过。被选出的6例全部随后真实执行，不把deselect称为业务通过。
- 原业务oracle：e256基线6 failed / 14 deselected，最终同样6 failed / 14 deselected；原NC期望未修改，实际gap如实保留。普通未筛选运行仍会执行这些失败，不存在默认隐藏配置。
- Ruff三份Python文件All checks passed。前端源码/配置未改，沿用本工作树Lint 0 errors/1214 warnings，不重新跑前端全量。

隔离运行拒绝.env文件、客户数据库会话、模型与外部网络，只使用进程内合成SQLite；临时切换自有执行器文件为e256固定源码做对照后finally恢复并核对源码SHA256 `3e2299951c92f9835da0787f8c24fc5ef49b51a39b350429d654351411890264`。所有测试/静态进程结束，释放测试槽。

预期记录 `.tmp/chemo-closure/n13-date-withdrawal-oracle.json`；证据XML同目录：`n13-date-withdrawal-red.xml`、`n13-date-withdrawal-engineering.xml`、`n13-date-withdrawal-round2.xml`、`n13-date-withdrawal-business-e256.xml`、`n13-date-withdrawal-business-final.xml`。没有覆盖此前独审结果或原业务oracle。提交门禁待root串行发令，当前不能称后续已提交或整条验收通过。
