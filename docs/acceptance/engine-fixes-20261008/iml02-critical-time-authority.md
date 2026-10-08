# IML-02 危急值报告时间权威来源修复

2026-10-08，独立修复树 `F:/MedQC-worktrees/qc-fix-critical-v2-20261008`，分支 `codex/qc-fix-critical-v2-20261008`，基线 `6930540f27e9c279241d35ac05d1c1c6e9134f82`。根与应用 AGENTS 已读，无 `.codegraph/`。本轮承接 T1 的 IML-02；旧 `4d5322c4a` 来源缺口/发布/保存合同继续保留，不重复冒充本问题的证据。

## 判据与最小修复

业务标准基线052/053要求危急值报告时间及同次对应处置：052从报告时间起6小时内处置，053只要求报告后对应处置，不额外附加6小时。

`_critical_value_item_from_row` 原先使用 `report_time or report_datetime or record_time`。本轮仅消费非空的两个报告字段；字段缺失或任一给定报告字段不可解析时保留 `data_gap/authoritative_time_missing`，绝不以记录时间填补。两个有效报告时间按既有共享解析器转换到医院时区后精确比较；相差一天、1秒或同一墙钟时间但不同实际时刻均为 `data_gap/authoritative_time_conflict`，没有额外容差。两个字段表示同一实际时刻可使用归一化后的报告时间；未标时区仍遵守既有医院本地时间约定。

生产范围为原生投影与同族判定。`CriticalValueItem` 增加默认 `report_time_error=None`，保留已有调用者构造兼容性。冲突时没有单选报告时间，不计算间隔、处置先后或窗口成熟。新增同族 `critical_value_report_time_conflict` 展示合同，只公开项目名、PL/PH及冲突数量，拒绝原始行、关联键、任取的报告时间和多余载荷；仅支持资料不足状态。Renderer仅新增两条危急值规则的报告时间冲突说明，Finalizer仅在既有危急值缺口强制状态条件增加该kind及混合摘要存在检查，拒绝空/未知/内部状态和确定状态矛盾。以上范围经协调方逐项批准。

没有修改目录、共享解析器、其他规则判定、其他规则文案或保存层/API。报告时间冲突仅引用实际危急值明细，不因已有处置记录而猜测其对应有效报告时刻。

## 红绿验证与交付链

专属文件 `apps/medqc-web/backend/tests/unit/test_luxian_0609_critical_time_authority_closure.py` 先冻结核心预期再改生产。初次14项为 **5 failed / 9 passed / 1 warning，7.57s**：记录时间回退（仅record_time、空report_time）以及一天/一秒/不同实际时刻的别名冲突错误合规。无报告时间且无可解析报告字段的保护与正常/时区等价/隔离回读对照通过。

单事件时间缺口及冲突闭环阶段聚焦六文件 **598 passed / 1 warning，11.07s**（后续混合事件扩展不能继承为最终绿测）：

- 新专属报告时间闭环52项；包括缺失、坏字段不能被另一别名遮盖、冲突、精确秒差、时区等价、记录时间不能影响已明确报告时间、公开合同载荷白名单与非法状态拒绝。
- 继承 `test_luxian_0609_critical_value_source_gaps.py`、`test_luxian_0609_critical_value_disposition_time.py`、`test_luxian_0609_native_extended_document_execution.py`、`test_luxian_0609_critical_value_public_boundary.py`、`test_luxian_0609_critical_value_result_mapping.py`，覆盖PL/PH、多事件关联、坏处置时间、052成熟/未成熟及6小时边界、053无6小时附加与已发布原值。

测试链为 typed 原生执行→绑定归约→Aggregator/Renderer→隔离SQLite保存→关闭写Session与引擎→新引擎/新Session正式回读→客户安全API投影。新增SQLite读回分别覆盖T1缺失反例、冲突反例及正常1小时处置；逐字段保持状态、原因、客户事实、结论、建议、证据及子项一致。SQLite临时实例是合成测试写入，未访问真实数据库。

冻结T1输入在集成树 `.tmp/engine-audit-20261008/imaging-laboratory/expected-extra.json`，SHA256 `4540b293986702c6501cb929dc11ce052863157259fd8d6748d388860a22ff8a`。本轮合成探针 `.tmp/iml02-closure/results.json`，SHA256 `906b7884278ae59a4267a1d24449124e3349d5d6a65d277cddd9a56562228ef6`，不提交临时产物。两个反例两规则均为对应资料不足，建议核对同步、关联信息及权威时间，均不再“继续保持”；正常报告与时区等价对照仍合规，实际间隔1小时。所有执行LLM调用0、Token0。

隔离runner仿照既有审计runner，禁dotenv、.env读取及网络，仅允许asyncio本地socketpair控制通道；SQLite Engine检查拒绝非SQLite。没有PG、网络、真实模型、真实患者原文或旧私有真实产物。

## 提交前门禁与边界

Ruff对五个生产文件及专属测试通过，`git diff --check`通过。前端隔离树最初没有node_modules，Lint/type-check/unit分别因找不到eslint/vue-tsc/vitest退出1；这是环境失败，未称门禁通过。协调方随后授权本F树Junction只读复用集成F树既有依赖，禁止安装或改变依赖，Lint使用 `npm run lint -- --no-fix`，逐项串行复跑。复用后Lint通过，0错误、1214既有警告，准确结果保留于工具输出chunk `11b654`。type-check在资源压力下约2.2GB内存，协调方要求停止本任务检查，终止控制后工具返回exit_code=0且进程消失；因发送过中断，标记检查结果不确定，不冒称无歧义通过。全量unit复跑未启动。当时资源门禁暂停，未提交、未绕过钩子；后续按AGENTS资源不足最低门禁完成编码和Lint，并由协调方批准固定提交供独立复核。

本轮只证明固定合成边界与继承保护集，尚未完成当前真实病例、HTTP服务器或浏览器验证；不能称危急值全族临床验收通过。真实频率与客户数据联调由后续授权验收负责。源码SHA由协调方独立复审索引登记，不与旧资料缺口合同提交混同。


## 独立复核新增混合事件边界

协调方批准并冻结：独立报告A已确认无处置或超过6小时，报告B缺时间/别名冲突时，不能以整规则资料不足覆盖A已确定缺陷。独立冻结输入位于 `F:/MedQC-worktrees/review-artifacts/iml02-closure/expected.json`，SHA256 `d9041cbdcec154a7e98d3465c5425d2c958f32bbd05fdc87a240860dbf485eea`，修复者不修改该预期。

本轮附加的最小方案仅在业务键足以证明独立事件、且全部处置具备已知事件键时隔离缺口事件；同键跨行存在任一报告时间缺口时整事件隔离，无键/未知键处置不能被丢弃后声称A无处置。可靠事件仍经既有052/053判定，成熟口径与6小时规则保持原样。其已有明确不合规时保留原状态/原因/可靠事件及证据，另附白名单 `report_time_gaps` 摘要（项目名、PL/PH、missing/conflict），避免向缺口事件编造时间或间隔。其未证明缺陷时仍为资料不足，不因一个正常事件而默认整体合规。

混合客户文案区分已确认处置问题与另列的待核查时间项目；建议先整改已确定问题、先核对缺口项目来源，不认定缺口事件处置缺失。公开合同禁止仅凭缺口摘要伪造不合规，以及空/非法/内部/合规等矛盾状态；旧无摘要事实保持原值读取。

新增专属测试文本覆盖missing/conflict混合、输入顺序、A1h/A7h/A无处置、无键/未知键处置、同键与052未成熟、混合SQLite新引擎回读、公开伪造和状态保护。**混合扩展最终225 passed / 1 warning，8.41s**（93项专属 + 132项既有危急值source gaps/disposition/public boundary/mapping），日志 `.tmp/iml02-closure/pytest-final.log`。唯一测试槽已立即释放；没有复跑其他族全文件或全量前端。Ruff与diff空白检查再次通过；实际暂存的六个应用文本经 `npm run check:encoding` 全部通过。协调方批准按明确七个路径经真实Husky钩子提交；固定SHA仍待独立冻结预期复核，不称临床或真实模型验收通过。

本批前端检查输入清单 `.tmp/iml02-closure/frontend-check-inputs.json`：1147个源码/测试/配置文件，清单SHA256 `d32b0953d985eb1cfe33cc1bd9e59d8f2adea67315bf9efad7eed7f08e6bcac2`。前端源码与配置未修改；当前全量类型及单元门禁仍不能宣称完整通过。
