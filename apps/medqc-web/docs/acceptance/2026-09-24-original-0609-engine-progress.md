# 原始 LX0609 引擎边界整改接续卡

## 范围与基线

- 工作树：`codex/lx0609-original-engine-20260924`，整改前提交 `775c17ede53930a685324e523f818b53da441698`。
- 本轮只审原始规则；新增抢救内容、病理报告完整性与 CT 扩展均不作试点或验收门槛。
- 首个聚焦点为原始 `LX0609-004`，正式编号 `LX0609-09-01-01`。`docs/0602/luxian_0609_formal_rule_catalog.csv` 和业务标准基线均定义为抢救结束后 6 小时内完成，四段式映射表确认同一身份。
- 固定输入先使用仓库已有原始规则合同测试中的合成事实。它用于技术回归，不是独立临床金标准。尚未发现可直接使用的原始规则真实签收保护集，不以新增规则候选代替。

## 已证实的重复解释

原始 004 的执行结果经 Finalizer 调用 `safe_basic_timeliness_customer_display_facts` 发布公开事实，Canonical Store 保存后，读取时由 `safe_customer_display_facts` 委托 `validate_luxian_0609_published_customer_display_facts`。后者对原始 004 仍回到执行器投影函数，重新计算逾期时长，并将输入中的公开字段静默改写。

在基线提交的固定反例：`elapsed_hours=7`、已保存的 `overdue_hours=999`，公开验证返回非空且将 `overdue_hours` 变成 `1.0`。这是已发布事实被读取层重新解释，不是原始规则判据的变化。复现命令在 `backend` 下调用 Python 3.10 的 `validate_luxian_0609_published_customer_display_facts(rule_id="LX0609-09-01-01", raw=facts)`；退出码 0，输出 `accepted True same False stored_overdue 999 read_overdue 1.0`。

## 最小实施与验收矩阵

| 项目 | 验收要求 | 状态 |
| --- | --- | --- |
| 原始身份和实际调用链 | 目录、基线、四段编号与 Store 路径相符 | 已核对 |
| 正常公开事实 | 发布与保存、读取结果逐字段相等 | 已写聚焦测试，基线通过此半段 |
| 损坏公开事实 | 读取受控拒绝，不静默修复或发布临床结论 | helper 与隔离 SQLite 的 Store 读回两条红测试均复现 `DID NOT RAISE`；待修复 |
| 原始规则保护 | 同一固定输入下状态、原因码、事实、证据不变 | 待基线与修复后比较 |
| 模型与性能 | 不改执行器或 Prompt，不增调用/Token；聚焦测试报告耗时 | 待验证 |
| 临床签收 | 独立原始规则业务答案与真实材料回放 | 未具备，不可宣称完成 |

只改公开事实验证边界和聚焦测试；不动医学执行器、资料选择、门控、模型配置、40 槽位或其他规则族。若查明既有历史公开形态与严格校验不兼容，先报告兼容事实，不扩大修复范围。后续阶段 B/C/D 仍按主计划门槛单独推进。

基线命令：`py -3.10 -m pytest -q tests/unit/test_luxian_0609_basic_timeliness_customer_projection.py::test_lx004_published_late_facts_are_read_without_recalculation --disable-warnings`，退出码 1，失败点仅为损坏公开事实未抛异常。合并运行原始时限测试与整个 Canonical delivery 文件，在第 44 项因伪 PostgreSQL DSN 无法连接停止：43 通过、1 失败，退出码 1；这是测试环境限制，不能表述为全部通过或本轮新增回归。

第二条独立红测试 `test_original_rescue_timeliness_store_rejects_changed_published_overdue_hours` 使用隔离 SQLite 真实执行 `replace_for_job`、`load_selected`，正常事实完整读回；仅把数据库公开事实中的逾期时长改成 999 后再次读取，基线未抛异常，退出码 1。此例只证明读取合同未拒绝被篡改的事实，不证明实际客户数据库已经发生篡改。原始时限族其余 28 项测试在基线均通过（排除新增红例的命令退出码 0）。

## 首轮最小修复与验证

原始004公开读取改用独立校验函数。它按已发布的正常、超时、未完成、缺时间、时间冲突、多次抢救和无抢救记录形态校验，不调用内部发布投影；有效事实逐字段原样返回。超时/剩余时长仅做一致性校验，不覆盖保存值；明显损坏或内部标识受控拒绝。原有医学执行器、判据、Prompt、证据选择、状态映射和并发未修改。

发布投影原本先舍入 `elapsed_hours`，再用未舍入的原间隔计算 `overdue_hours`/`remaining_hours`。因此只凭已发布两位小数不能严格反推衍生值。新校验接受最多 `0.01` 小时的双重舍入差异，并允许 `6.001` 小时发布成 `elapsed_hours=6.0, overdue_hours=0.0`。固定 7 个临界值及 0–10 小时每 0.001 小时的 30,003 组既有投影输出均被公开校验接受；该兼容范围不改变公开数值。

- 两条红测试修复后转绿；另测公开读取不调用内部投影、合法八类事实、私有标识、错误衍生值、不可哈希 JSON 字段和布尔阈值。
- 后端原始时限投影、Canonical SQLite 读回、Finalizer、证据冻结、架构冻结和原生时限执行共 `265 passed, 1 deselected`，退出码 0。被排除的是 `test_course_source_read_failure_is_data_gap_only_for_005_and_006`，它在伪 PG DSN 下连接失败，与本次004范围无关；未把它算为通过。
- Ruff 聚焦检查、`git diff --check` 已通过；编码检查将在按路径暂存后运行。没有执行真实 LLM 调用，调用数和 Token 增量为 0。现有004冻结测试验证固定输入下的状态、原因码、证据坐标；本次只改读取校验，不改变执行输出。
- 当前技术结论仅限原始004的一次发布与公开读取边界，不代表整个0609引擎整改或临床验收完成。任务投影、latest DTO、反馈和多格式导出的追加验证另行记录。
