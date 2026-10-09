# 0609 下一阶段 A 类独立预期冻结

日期：2026-10-09。冻结基线 `4dbcd8e819f439c576262eebd1565f0eab0774e2`。责任范围仅026、043–048、050、055九条；未修改实现、原反例或原预期，未运行测试、模型或数据库，未自行提交。仓库无 `.codegraph/`。其他代理拥有实现文件，本报告不覆盖其修改。

## 证据等级与冻结载体

- 业务依据：`apps/medqc-web/docs/0602/泸县0609质控点-业务标准基线-v1.md` 的026（107行）、043–048（129–134行）、050（142行）、055（145行）。这是仓库批准口径；本轮不自行补充临床定义。
- 原合成预期：执行前冻结的原输入/预期与脚本，证明明确场景的原 oracle；不是独立临床金标。
- 工程观察：旧纯函数/执行器/Finalizer结果及人工模型事实仅证明该版本程序行为；不证明真实模型语义。
- 当前性：由 root 调度的新离线执行确认，旧台账A类本身不证明当前仍可复现。真实模型与正式链路分别缺件。

机器冻结文件 `.tmp/phase2-independent-20261009/frozen-original-expectations.json` 保存原JSON记录及七份来源SHA256；050输入仍以原 `course-timing/probe.py:54–73` 的构造为准。原反例与旧日志不覆盖。

## 九条原预期与正常保护

| 条目 | 原反例和预期 | 正例及边界保护 | 可确认范围 / 未决 |
| --- | --- | --- | --- |
| 026 | `foreign_drug_dose` NC：执行目标药120mg、另一药130mg不能匹配130mg医嘱；`negated_course` NC；`planned_course` DG；实际120mg+计划130mg `conflicting_dose_in_one_record` DG | 同药肯定130mg C；合法前缀L-OHP、跨邻句单药、完整数值/单位分母/千分位；N13六NC与两计数原保护；原旧四文件115保护 | 药物—动作—剂量不能跨归属是通用依据。结构合法但语义错误的宽action不能视为归属证明；人工坏响应不证明真实模型正确。 |
| 026 状态子项 | 取消/撤销/作废+未给予原NA；拟执行+未给予原DG；原观察均C | 执行状态+肯定给药C；取消与明确实际给药冲突不得简单删事件 | 已批准合同可确定不得肯定一致；院方码表、停用/已给药冲突及拟执行终态仍待裁定。 |
| 043 | TC01共同六输入门控：TF_PLAN/REFUSED/POSTPONED/CANCELLED/PLAN_COMPLETE_FIELDS均DG；TF_ACTUAL_NO_REACTION present | 本规则原检查结果/早于对应事件、来源错误与缺时间保护 | 六例为共同gate冻结，不是本条六份正式终态证据；本条九项事实仍需独立核对。 |
| 044 | 同一六输入gate预期原样保持 | 单事件申请理由/指标、严格提前、缺时间、同ID双来源、已闭db4字段/状态合同 | TR-044-MULTI原三node/rows/expected manifest unknown；不得造新例冒充恢复。 |
| 045 | 同一六输入gate预期原样保持 | 实际对应病程、多记录/多时钟、真实selected文书refs、重复业务ID材料映射 | 可靠事件≠病程存在；MR+空模板旧C合同冲突另列。 |
| 046 | 同一六输入gate；PLAN_COMPLETE_FIELDS旧错误进入NC/purpose_missing，原预期仍DG | 实际完整字段C；第9份缺成分剂量NC/count9/incomplete1/第9份证据；完整正文1400后字段；多记录多时钟 | 未确认/取消文书不能借字段或计字段缺项；MR+cancel旧NC冲突另列。 |
| 047 | 同一六输入gate预期原样保持 | 实际结束时刻、对应评价、24小时成熟窗口、多事件结束与完成时间 | 实施时刻、结束时刻、文书完成时间分开；不能用时间去重代替事件归属。 |
| 048 | 三文书明确未输血、仅备血2U/4U/2U：`048_NEGATED_INTRAOPERATIVE` 原NA | `048_MATCHED` C（2U=2单位）；`048_TIME_CONFLICT` DG/association_failed | 其他住院阶段实际输血不能替代术中实际事件；已闭b4配对/单位合同不重开。完整三类真实文书及模型语义仍缺件。 |
| 050 | “目前不存在诊断不明确的问题。”与“如后续诊断不明确，拟进行疑难讨论。”原NA | 当前诊断仍不明确且成熟原NC；已明确原NA；缺course_time原DG；已闭CT02/03/04保留 | 否定和未来条件不证明当前触发；早期讨论与问题关联CT-R02独立合同未决，不能阻塞明确否定反例复现。 |
| 055 | 明确“美罗培南抗感染治疗效果评价：体温下降。”48/60/72小时原C | 47/73小时原NC；“抗感染治疗有效，体温下降”原正常C；镇痛评价/任意CRP趋势不能替代目标药疗效 | 055基线含疗效和安全性评价；本原oracle只冻结明确评价漏识别，不自行把它升级为所有安全字段的临床完成证明。 |

NC/C/NA/DG分别为 non_compliant/compliant/not_applicable/data_gap；present 是实施gate事实而非最终C。

原来源：`tumor-pathology/expectations.json` 与 `probe.py:55–66`；`antimicrobial-expectations.json` 与 `antimicrobial_probe.py:13–17`；`course-timing/expected.json` 与 `probe.py:54–73`；`treatment-consultation/048-frozen-expectations.json`；公开附件 `next-batch/transfusion-family/tc01-original-cases.json`。均位于 `.tmp/engine-audit-20261008/`，最后一项位于本报告同级目录。旧版本/观察详见 `tumor-pathology.json`、`course-timing.json`、`treatment-consultation.json` 和 `resumption-reconciliation.md`。

## 输血三项冲突的推荐行为与裁定点

### 1. 可信MR + 空模板，045旧C

可由批准045标准确定：可信MR实际事件保留；空模板/unknown不证明对应有效病程，不能交付C，不能把旧bool True翻译成模型performed。应遍历已批准来源，包含相应日常病程候选；仅bloodtrans为空不能推断所有来源无记录。

推荐：来源完整且已确认对应有效病程不存在时045 NC；来源/关联/正文可判定性未决时保留DG或现合同的evaluation_unknown。精确分支需要来源就绪和关联证据，不能只由“空模板”三个字决定。旧C保留为合同冲突历史，不静默改测后称恢复。新增正文存在/关联事实、来源及预算必须版本化，但“不凭空模板给C”无需新增临床裁定。

### 2. 可信MR + 唯一取消文书，046旧NC

可确定：MR实施不得被cancel抹掉；取消文书不是实际记录，不能发布record_count=1、取消doc引用及字段缺项事实。045可靠事件需对应病程，046描述已定位病程字段，两种责任不能偷换。

推荐：来源完整且确认无对应病程由045 NC报告；046保持记录关联/材料缺口，若有实际病程再逐字段判定。是否让046同时承担整份记录缺失NC、如何计重复缺陷，需要明确新合同并由root裁定，独审不自定。若裁定允许，应新增“整份记录缺失”的事件事实、缺文书证据、文案与计数，不能零record配全部missing_field_counts=0凑NC。

### 3. 自定义完整129材料与最终128引用护栏

可确定：正式SQL第51行触发truncated与消费者scope能力属于来源/容量层；最终RuleDecision的128上限是实际observations+selected refs合并去重后的坐标union，raw材料数/事件数不等价。独立128合法、129拒绝及重复ID映射保护可以直接验证。

未确定：generic reader声明完整limit129后是否允许同一scope抽取129份、在2048输出token及总输入/调用预算下的能力合同。推荐保留正式来源限制和真实truncated护栏，准确标记custom129原端到端路径未恢复；不能rawcount>128提前technical_error迎合原测试，也不能把新增scope限制改为DG后称零回退。若扩大能力，须另定预算/全覆盖合同；人工fake usage15不证明真实模型足够。

## 哪些阻塞，哪些不阻塞

TC01六冻结、048术中否定、050否定/未来条件、055明确评价、026跨药/否定/计划有原输入可直接复现。其根因证据不依赖以上三冲突裁定；不得将未知归缺失，也不得只按案例药名/数字/ID凑绿。

MR+空模板、MR+cancel与custom129阻塞整个输血候选“原保护全部恢复/可整体集成”的结论，不阻塞明确gate缺陷的当前复现与有限根因定位。readiness空投影覆盖旧data_gap是技术问题，不是临床裁定；候选已14绿、425/428的历史报告只支持该工程子项，当前集成版仍需由root重验。

同根因至多3轮失败实现/验证；测试接线错误也计尝试，首败与每轮输出独立保留。任何新oracle裁定独立版本记录，不覆盖本freeze。独立复核新结果时同时看status、事实、引用、计量和客户文案，人工事实只能认证工程接线。

## 已批准新决议 v1（与旧 oracle 并列）

root于本轮传达用户明确批准：045负责已确认整份缺失；046无有效记录保留资料不足；本批维持正式来源容量，custom129全链兼容单列暂停。正式版本见 `phase2-transfusion-decisions.md`。上述推荐中的这两项已成为新验收合同，其余关联/来源未知仍不能当已确认缺失。

| 场景 | 保留旧 oracle | 新合同 v1 | 结论记账 |
| --- | --- | --- | --- |
| MR可信，空模板且来源/关联未证完整 | 045 C | 不允许C；资料不足，不能推断已确认整份缺失 | 合同校准差异；旧C不再作为新金标，原反例不删除 |
| MR可信，仅cancel，无有效对应记录 | 046 NC | 046 DG；若完整来源已确认整份缺失，由045 NC承担 | 业务责任调整；不算原NC不变的修复关闭 |
| custom reader完整129材料 | 原最终technical_error/executor_exception | 本批维持正式来源容量；custom129端到端兼容暂停，实际selected refs union128/129护栏继续独立验证 | 容量范围决议；旧端到端反例未恢复，不记通过 |

## 当前结果

输血首跑独审完成：`.tmp/phase2-transfusion-20261009/current-results.json` 的9例为4符合、5不符。只读逐项比较确认六TC01输入/预期与原附件完全相等，三048输入/预期与原freeze完全相等；七份冻结来源及运行manifest/source hash均匹配。独审产物为 `.tmp/phase2-independent-20261009/transfusion-first-run-review.json`。

5项不符为TF_PLAN、TF_REFUSED、TF_POSTPONED、TF_PLAN_COMPLETE_FIELDS仍gate=present，以及048_NEGATED_INTRAOPERATIVE仍NC且confirmed=true。4正常控制为TF_CANCELLED DG、TF_ACTUAL_NO_REACTION present、048_MATCHED C、048_TIME_CONFLICT DG/association_failed。PLAN_COMPLETE_FIELDS纯046还返回NC/purpose_missing，仍不是本规则正式终态。

脚本 `reproduce.py` 按AST递归收齐源码内顶层依赖、保持原顺序，外部库用标准库原对象，仅reader替换为冻结合成rows；阻断socket、应用/SQLAlchemy/PG导入及常见环境/数据库文件。未执行应用导入，hash前后核对、首调输出禁止覆盖。该边界足以支持当前纯函数机制仍可复现，不能推导043–047五规则最终状态、Typed/Finalizer、模型语义、保存/API/UI链通过。

050/055首跑独审完成：050四例2符合2误NC（negated/planned）；055六例3符合3误NC（48/60/72小时），47/73小时及无关镇痛评价正常NC。新fixture中026/055原rows、rule、expected逐项等于原JSON；050预期等于原freeze，正文和时间构造对照原脚本不变。fixture/四原来源hash核对相符，三份产物before=after_import=after。

other脚本使用隔离合成reader，替换数据库connection、禁止网络与环境读取，NoModel.generate拒绝调用；050/055经历真实当前执行器→binding→Finalizer且计量断言0，证据仅限确定性合成路径。026首跑五例全部 `RuntimeError: no running event loop`，是手动驱动协程缺事件循环的支撑失败，未形成医学结果，不把该次算作当前跨药误C或修复失败的医学证据。该首败仍保留且计入验证尝试。产物索引见 `.tmp/phase2-independent-20261009/other-first-run-review.json`。

026后续v2在guard安装时被标准库平台探测子进程阻断，业务执行0例；结构化首败摘要保留。v3仅预热platform缓存并使用受guard保护的事件循环，产物 `baseline-v3-026-1791529029807805400.json` 五例1符合4误C：肯定130mg正常C；negated原NC、planned原DG、foreign_drug_dose原NC、conflicting_dose原DG全部错误C/requirement_satisfied。

独审核对五原输入/expected/rule不变；v3 before=after_import=after，逐文件当前hash与运行hash一致，包括runner、guard、fixture、生产族模块及目录。`NoModel`拒绝generate且原0-call断言保持，因此认可当前确定性executor→binding→Finalizer误判复现，不与隔离候选的局部模型事实语义结果拼接。独审产物 `.tmp/phase2-independent-20261009/026-v3-review.json`。v1/v2支撑失败均未删除；root已要求026历史至少三失败停止生产试修，不重置次数。

050/055设计独审只列阻断：8份/12000/6000/2048预算建议没有本规则权威来源限制和最大输出基数推导，不能搬其他模块魔数；多诊断/多药问题与事件身份须有程序可核span/可信事件键，模型自报ID不证明关联；新增0→1调用须版本化计量/失败合同，unknown、非法协议及来源不可用不得统一为absent或DG。055具体变化需明确评价语境，不能扩大为任意趋势。这些是设计进入生产前的门禁，不改变原临床oracle。

输血新合同 `.tmp/phase2-transfusion-20261009/new-contract-frozen.json` 已只读预审，三MR组×045/046状态预期符合用户v1；尚未执行。要求消除“MR证明另有事件”表述（输入未证明另一个事件），045 NC前显式冻结全部批准病程来源完整及关联条件。引用方案应以真实snapshot observations和selected material.document_rows按source+ID映射去重，精确断言union128/129及129触达RuleDecision实际护栏；正式容量动态取权威限制，手工全覆盖不证明2048真实模型预算充分。原custom129全链仍暂停。新正式六TC01测试的正文/原gate冻结与原附件等值、test hash匹配；actual正常C只用于045，不外推其他四规则。

## 本批正式输血支撑收口

正式26组合（5未实施原输入×043–047，加实际无反应045正常例）尝试三次，全部支撑失败：第一次pytest启动卡住，由root有界中断，无case/XML；第二次direct在标准库socketpair.accept创建事件循环处卡住，90秒退出124，无case；第三次 `formal-direct-1791529589918217700/run-manifest.json` 为26条统一 `SnapshotSourceRows.create()` 缺必填 `truncated` 的TypeError，无业务输出。26是尝试的规则/场景组合，不是26医学失败或成功。

第三次manifest独审核实：before=after；actual HEAD等于冻结基线；test/frozen/runner/guard hash一致；加载app路径全部在选定集成backend内，outside为空。显式stub仅数据库路由、bundles装配及当前静态RULE_FAMILY_DEFINITIONS；未替换质控符号。新版测试虽设计了完整native/reduced/final/snapshot/selected refs逐case JSON，但本次未达到写出，因此完整引用无法复核。六正文/原gate预期仍与原附件完全相等。

依据同根因三次失败停止支撑迭代，本批不再扩大候选或重跑。043–047当前结论仍仅共享gate实际误触发机制及其逐规则调用风险，未完成各规则正式终态复现；048仍限纯consumer。独审产物 `.tmp/phase2-independent-20261009/transfusion-formal-support-review.json` 保留精确身份和限制。此结论不撤销已完成的026/050/055当前正式合成路径结果，不混合不同执行层统计。

九条完整临床验收数未知；本轮真实语义及正式链路验证均为0。
