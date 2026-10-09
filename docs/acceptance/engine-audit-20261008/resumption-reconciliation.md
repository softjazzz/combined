# 0609接续增量对账（R0/R3）

核对基点：集成 `4757e4dee`；化疗树 `fac4ef67c0f68da1625f419ea5dddb47f38aa78b`。范围仅0609，继承原86行目录与问题账，不重新全审。本文是本轮只读Git、源码、测试文本与既有报告的增量核对；**本轮未执行pytest/npm、模型、网络、PG、患者材料或生产运行**。下列通过/失败数字均是明确引用的历史实跑。

已读根AGENTS、`apps/medqc-web/AGENTS.md`、`docs/AGENTS.md`及接续计划。根无`.codegraph/`，不使用CodeGraph。局部AGENTS引用的`docs/plans/PROJECT_ROLLING_TODO.md`在当前根路径不存在；此次以明确接续计划为入口。外树Git首次普通沙箱读取被拒，随后只读升级成功，未更改权限。

## 一、历史层与增量的关系

|证据层|可继承内容|不得推出的结论|
|---|---|---|
|T0 `catalog-coverage.*`|86报告齐、51限定继承/29原开放/6受影响；11已完成问题涉及14规则；初审来源与限定证据|51整条通过；86临床完成；缺manifest等于真正未审|
|`coverage-progress-current/overlay.*`，固定1958ae3bb|原逐行证据、19祖先集成涉及13规则、16有限问题关闭、下一动作索引|固定快照统计是4757当前统计；所有旧pending标签仍有效|
|`closure-issues.json`与后续归档|问题级最新状态、后续提交、原失败与恢复过程|历史claim/source_classification可替代最新state；合成补证可补造历史真实manifest|
|当前核对|1958→4757祖先日志、候选差分、两个反例原断言|当前执行通过、真实模型语义已验、最终发布链已完成|

默认65执行、10注册暂停、5客户排除、5acceptance_only、1未注册的原范围合同继续继承；本轮未核改启用配置，不因进度改变分母或默认范围。历史“80条有实质审查、25条有修复子项”只能作为既有汇报，不能转成整条验收数或在未重新汇总时作为当前已核数字。

## 二、1958以后的具体接续成果

以下提交均由`git log 1958ae3bb..4757e4dee`核实位于当前集成历史；只核版本/报告，不新跑相应用例。

|问题/规则|提交及具体路径|可继承历史结果与边界|
|---|---|---|
|手术029旧夹具/目录漂移|`fad64946e`，`test_luxian_0609_surgery_document_freeze.py`、`test_surgery_029_mr_fixture_contract.py`；归档`56322bcff`|原MR字段合同与族tuple测试适配，root354/354；原医学输入/预期保留。029/030多医嘱语义关联仍开放，不能继续把已恢复的两旧测试失败当新阻断|
|七条历史版本绑定缺口|`42db89910`；`next-batch/evidence-binding-current.md`及`independent-closure/{antibiotic-current,culture-current,death060-current,discharge-death-current}/`|060十一项、061七时间节点、068四项执行/绑定/Canonical；054/057十三项13历史观察一致但仅8原预期符合；014/015原45为44/1。均补合成版本来源，不补真实病例manifest、HTTP/Store/客户端验收|
|培养旧身份literal|`5f34698a2`、归档`e5f5696f5`；`independent-closure/culture-identity-integration/`|两处身份literal测试适配，root同45/45，生产及医学oracle未改；44/1保留原始历史但该失败已接续恢复|
|070实施事实与正式隐私载体|`011d26b86`+`35909964a`、归档`f229b09f8`；`extended_document/transfusion_performance_extraction.py`、native_extended、mapping、Renderer、Finalizer及070目录合同|源219b+196d固定独审；作者289/289，root首次276/13是guard bytes路径支撑错误，修guard后同289/289。真实模型、多事件多时钟及正常C缺labID精确卡边界仍开放；不扩成043–047同族关闭|
|N12麻醉正式载体|`f1c6ec095`、归档`2d66663b6`；`anesthesia_visit_fact_extraction.py`、`test_n12_formal_privacy_carrier.py`及手工fixture reader|root375/375、前后hash一致；旧red6/9、firstgreen370/5支撑失败保留。`0683dfb9e`补同ID sN标记2合成病例/3文书纯捕获证据，限制于该冻结组合，不是任意标记或真实语义验证|
|043–047 WIP与N10计划|`9d2f5421e`、`458356f1b`、`f0f2ea5fe`、`4757e4dee`；`next-batch/transfusion-family/implementation-checkpoint.md`|仅设计/过程记录，未集成生产候选。原65为60/5文案词保护失败，随后97专项通过，原8文件356为265/91未关闭；正文别名7绿是历史，不能记本轮重跑。91是节点失败数，不是91缺陷|

## 三、原账应纠正的过期字段

1. `closure-ownership.json.integration_head`仍为`2d66663b6`；root应写实际冻结头/后续集成头，保留原历史基点。旧owner和复用目录分支只作历史，不证明仍在运行或当前写权。
2. `N12-COPY.state=integrated_copy_support_core_pending`已被core5649及carrier f1c接续；应标有限工程core/copy/carrier已集成、真实语义待验。N12最新记录已有375及sN有限补证，不能退回初审“未找到关闭”。
3. overlay固定1958的七条“针对性阅读/manifest待补”已由42db补**当前合成来源绑定**；培养旧literal再由5f346恢复。更新下一动作时只移除相应缺口，原真实manifest/自然适用资料/业务争议仍保留。
4. T0 N13“未比较matched”、IML01 blanket旧标签、手术原正常回退和CT02/03等旧开放文字是原审计层。当前工程层应继承N13有限不假matched、IML01 US/培养角色子项、手术夹具恢复和已集成CT02/03/04；剩余子项见下文，不能重新修已闭部分。
5. TC02应继续沿011d+359工程闭环；新043–047候选不覆盖或宣布070真实语义完成。化疗TP-D02最新67/65/2与旧115未恢复已经入closure-issues，不能退回37/42或误标完整绿色。
6. overlay.md末尾链接仍指原`review-artifacts/coverage-progress-current`绝对位置；集成附件存在，可在root更新时改成当前仓库附件引用，避免新读者误取旧副本。

本文不改共享JSON/Markdown总账，以上由root维护。

## 四、剩余确认问题与验证缺口

|问题|当前剩余，不重复已集成子项|
|---|---|
|IML01|06-01-03 CT/MRI同键联合事件业务合同；06-01-01原case缺orders/course不能继承C观察；06-03-02培养不能消费exam-only反例，余新字段真实输入/链路影响。US/培养已闭角色子项保留。IML-D01/D02按原业务争议继续|
|CT01|否定/未来条件的“诊断不明确”错误触发仍开放；CT02可信时间缺口、CT03正文不可用、CT04阈前讨论子项已关，不重新展开|
|SURGERY029030|多医嘱、事件与文书关联负向覆盖；SURGERY-FREEZE中已确认夹具/目录漂移已恢复，其余语义、事实/引用变化针对性验。PREOP-MEDICAL仍独立人工诊断/术式归属争议|
|DD-F02|当前只有带药完整性；master还要求药名/剂量错误、业务基线含与医嘱一致。缺权威出院标识、有效版本、唯一配对、剂量含义及医生错误口径；不把住院医嘱药名共现变成NC答案。见`next-batch/discharge-medication/boundary.md`|
|RR-D01|死亡讨论评价终点与可见材料合同；不能把冻结评价终点改成来源可见性截点。RR-D02已闭。DD-F05维持原业务争议|
|PRIV003|限定拒发边界已集成；两CLI可信已知身份来源/自然caller未接，failclosed保留。不是确认继续泄漏；不猜身份或搭新接口|
|输血|043–047候选91失败归因、9份容量、旧时间/正文兼容与合法NC保存保护；TR044-MULTI原manifest缺失独立保留；TC03/TR048真实触发/三类完整文书不足，不用新合成代替|
|病程N10|065/067正文事实与模板、签名有效内容边界；旧6测试适配需独审；新候选未集成，按R2接续|
|化疗/肿瘤|TP-D02两个语义反例、旧115保护；TP-D03医嘱状态；N13六NC能力+两计数归属；TP-D05及未知药名范围不因TP-D04有限修复关闭。054/057五旧差异按TP-L01/Q03/Q05/Q04原归属处理|

共通验收缺口：CT-INPUT、PATH-INPUT、PROMPT074等受影响真实输入输出；N12/070及未来化疗/病程抽取真实语义；原历史manifest缺件；自然资料与独立医学预期；最终候选创建→执行→发布→Store→新实例/API→浏览器/历史/导出及客户环境/构建身份。原SQLite和TestClient按原界限继承，不能冒充客户全链。全仓encoding失败、typecheck资源中断、全量单测未完成保留，历史lint exit0/1214warnings不等于全门禁绿。

## 五、化疗候选具体核对

化疗Git HEAD确认为fac4ef67c，祖先核验`merge-base --is-ancestor fac4ef67c 4757e4dee`返回0。HEAD是既有麻醉test-only集成版本，并非化疗候选提交。当前5已跟踪修改、3新增：

- 修改：`app/data/luxian_0609_rule_contracts_v1.json`、`app/data/luxian_0609_rules_v1.json`、`services/luxian_0609/native_tumor_pathology_execution.py`、`rule_contracts.py`、`tumor_pathology_result_mapping.py`（均在backend）。已跟踪差分85插入/6删除。
- 新增：`services/luxian_0609/chemotherapy_local_dose_facts.py`、`tests/unit/test_luxian_0609_chemo_local_dose_binding.py`、`docs/plans/2026-10-08-tp-d02-chemo-local-dose-binding.md`。

本轮直接读native/mapping差分：原N13候选归属函数、partial竞争门禁与missing/unresolved计数没有被删除；新局部dose替换发生在原candidate唯一选择和independent_owner检查之后，新增local未知子集与窄NC优先条件。故静态未见回退到中间e8错误日期排除，但这**不是N13当前运行保护通过**。旧N13源59b3→集成880a：47观察39全符合，六NC仍DG、两DG计数期望0实际1，20合同/14剂量保护可继承；原六能力不足不因candidate可选局部抽取自动关闭。

候选新抽取一次batch8文书/8000字符/12动作/2048completion，不分批、不重试；总预算含恶性门控由1→2、v4→v5。只发送目标药名和正文，不发送医嘱剂量。原文/脱敏同view和唯一回投工程保护有历史证据。新增local计数是unresolved子集，只有local==全部unresolved>0、无unknown_time、至少一个完整独立事件且mismatch才接受NC；旧无字段/混合关联未决合同维持。

两个业务反例均在原测试文本中，未xfail：

|nodeid/位置|原输入与期望|历史最终观察|本轮源码因果|
|---|---|---|---|
|`test_original_local_drug_dose_business_oracles_through_finalizer[negated_course]`，约206–218|否定给予130mg，NC|DG，仍失败|native将negated/planned统一归local未知；另一个工程DG保护约224明确不替代原NC|
|`test_widened_action_span_foreign_dose_remains_semantic_business_gap`，约450–457|目标药120mg、另一药130mg，坏事实整篇action+130mg，NC|C，仍失败|parser只核目标名包含、逐字坐标及dose在action内；整篇跨度可同时包含另一药剂量，几何合法不能证明归属|

候选计划记录原五4红/1绿；首次35为34/1；283为164/119，其中专属39为35/4、原四文件115失败。旧四文件74=23/51、111=98/13、33=6/27、26=2/24；首失败104旧0calls+11语义/计数断言，另3新公共合同红+1否定NC。42为37/5；最后67为65/2：37旧绿保持、3公共红转绿、25新矩阵绿。旧115未恢复验证，N13六NC/两计数有些被0call前置遮挡，不可抹除。本文没有重新读取运行XML逐节点或复跑，数字来源于计划、closure-issues与integration-progress；root候选冻结manifest另行绑定。

## 六、化疗后续最小方案（待实施，不改代码）

1. 保留原五oracle、两个业务红例、N1347观察、全部旧状态/facts/refs/copy/SQLite断言；固定当前8路径字节及旧XML/manifest，再作新方案差分。不得依据病例ID、特定药名、130/120数字、关键词或句号距离设分支凑绿。
2. 先完善通用最小事实合同：同一文书内显式药物提及span、给药动作标识及state、剂量span与其所属动作引用；剂量只能比较已证明绑定到目标药物动作的事实。多药共句、多动作、否定/计划作用域、执行与计划并存、跨文书/跨日期归属均保留独立竞争关系；不把整篇action包含目标名等价于归属。结构校验可拒绝重复键、坏引用、越界和不完整集合，但不能把模型自报的关系当语义正确证明。
3. 用原跨药坏响应与名称/数值/顺序/文书位置互换的同类保护检查关系合同；正例确认目标剂量、反例确保另一药剂量不能借用。自然模型对该关系的准确性必须后续独立语义验证；如果仍无法证明，保留未决，不能宣布原NC达成。
4. 否定NC的原业务期望继续冻结；“已执行医嘱与明确否定给药是否构成确认不一致”通过事实语义/同事件归属与现合同对齐解决，不伪造dose mismatch，也不只改DG预期。TP-D03医嘱状态与N13日期归属分开，不能借此扩大本轮实现。
5. 旧fixture只显式提供手工冻结局部事实及适配调用协议；不按源码关键字生成答案、不改原医学断言。先核104前置0call与11剩余断言，不把119都归fixture。测试槽释放后按原四文件完整保护+新反例/N13保护验证；生产与测试适配分提交、固定blob独审。
6. 新模块、native、mapping、预算/版本、fixture是同一正式接线依赖；不单合没有生产消费者的mapping或孤立模块。整体在两个语义红与旧保护未闭前保持隔离。共享rule_contracts/目录JSON待root锁释放。

新核对结论：候选可恢复且差异明确，仍不可整体集成；有限工程保护与历史修复继承，不提升为真实语义或整条验收。R0候选三树冻结由root及各唯一owner完成，本文只对账化疗与后续集成历史。

## 附录A：R3两个冻结反例的可泛化关系合同设计

本附录为追加只读设计，未修改生产/测试、未执行pytest、真实模型或PG。使用brainstorming方式核上下文与比较方案；原约束、独占写入和不硬编码要求优先，设计仍供root审核，并非实施通过结论。新增读取了旧`results-current-contract.json`的失败清单，但没有重跑或将该早期源码hash当最终67版本。

### A1. 推荐路径及不可越过的能力界限

三种方案比较：

|方案|实际能力|取舍|
|---|---|---|
|单次受控关系事实图，Python验证及比较（推荐）|在同次局部batch中分清药物提及、实施动作、否定/计划作用域及剂量归属；程序掌管数值、事件、状态、证据|保持当前最多2总调用，但模型语义仍须独立验证，结构校验不保证临床正确|
|给旧action_span加长度/句号/固定距离或风险关键词限制|可令特定坏fake红转其他状态|不推荐；不能覆盖跨句详情、共句多药、代词、省略、反向表达，违反不硬编码约束|
|额外裁判/重试模型确认关系|可能减少特定错误响应|本轮不采用；超过冻结单次局部batch/总2调用，不保证独立性，须另立预算及验收，不能偷偷接线|

**原widened坏fake的信息不足是实施阻断，不能由新schema自动抹去。** 它只声明整篇目标动作和另一药剂量，没有提供正确目标剂量事实。关系不合法时可拒绝为未决，但不能仅凭拒绝证明目标剂量不一致；若自洽地伪报“另一药剂量属于目标药”，结构校验仍不能证明它错。程序不得从整篇数字或固定药名再捞正确数值凑NC。原临床输入的NC期望仍保留；坏输出oracle也不得修改、xfail或偷偷改成好fake。若固定坏响应下仍不能达到冻结NC，必须明确报告其未达，不能用新增“拒绝坏输出”工程保护冒充关闭。正确且完整关系事实下能达NC是另一项需要独立证明的结果。

### A2. 最小内部类型与关系边界

保持`LocalDoseLLMClient.generate`协议、usage、一次generate、同view/原文回投边界；建议升级内部schema/prompt版本，禁止v1裸跨度被自动当v2可信关系。名称与剂量只来自原文和请求目标集合，不在生产内配置具体药名字典/数字分支。

建议局部响应每文书拥有三个有限集合，ID仅为本响应内受控引用，不是来源身份：

- `DrugMention(mention_ref, drug_span)`：所有参与该次给药关系的药物提及，包括非目标共同给药者。`drug_span`必须连续、逐字、同文书；目标映射由程序对请求药名做现有规范化身份对照，模型不能新增“等价药名”或猜药码。
- `AdministrationAction(action_ref, participant_refs, predicate_span, state, scope_span)`：动作有明确participant引用、动作证据与否定/计划作用域；state保留`administered/planned/negated/uncertain`。动作可有多个参与者，不能把共同行为强行拆成唯一药物；`scope_span`用于复核语义，不作为归属证明。
- `DoseMention(dose_ref, dose_span, owner_action_ref, owner_mention_ref, relation_state, relation_span)`：明确是某动作/某参与药物的剂量、归属未决或共享剂量。引用不存在、跨文书、参与者不属于该动作、同一剂量被声称互斥独占、重复ID/重复键、坏坐标、集合缺项均拒绝。共享或歧义剂量不比较，不按最近药名猜归属。

内部归一结果建议为`LocalDoseAction`的下一版本，携带已校验药物span、动作state、动作证据、可比较dose及关系诊断；`LocalDoseResolution`继续区分ready与受控失败/未决，不向客户DTO透传原JSON或模型解释。该设计不添加公开动作图，也不让模型输出质控状态。是否在同一次响应中列非目标提及，只为检测竞争归属，不扩大需要核对的医嘱范围。

**结构与语义分别验。** 程序能证明span逐字、ID引用、同文书和集合一致，不能证明否定作用域、participant或owner的医学语义。给模型新增字段只是可追溯语义事实，不是“已验证关系”。响应漏报非目标提及、错误owner仍可能自洽：独立手工关系金标和后续真实语义批次必须覆盖此点。无法证明覆盖完整时保留未决，不写C。

### A3. native判定与否定反例

正式026先沿原来源/恶性门控、完整医嘱及可比较材料筛选；局部关系解析一次。程序以权威医嘱为预期值，只对唯一归属目标药物且`administered`的动作比较dose。实际动作与计划改量并存时分别保留：唯一实际动作的真实剂量可比较，计划动作不覆盖它；多个实际动作或无法区分同事件仍未决。不以`len(local_actions)==1`把所有有计划的正常资料整批降级。

否定动作本身不是剂量错误。`negated_course`的NC应由“同一可比较医嘱事件与明确未实施事实冲突”支持，不能把130mg改成错误数值或强置dose=mismatched。当前公开四字段只有drug_name/dose/route/time，且`missing_course_event_count`意为没有目标记录；文书存在但明确否定不适合塞进这个计数或伪装drug_name错误。

最小候选公共合同设计为**可选且有界的`confirmed_nonadministration_event_count`**：仅当完整、适用的预期事件已唯一绑定明确negated动作，且无同事件已实施证据、未知时间/竞争医嘱/其他否定作用域时正计。与missing_order、missing_course、unresolved、unknown_time按互斥事件计数，不能重复相加；旧载荷缺该字段时沿原合同。该分支可用既有`chemotherapy_record_mismatch`原因，但公开四比较字段不得伪造matched/mismatched，文案需准确表示“医嘱与明确未实施记录不一致”。该字段只是方案，未获得生产字段写入授权、未声称现Finalizer已支持。

`planned`不能直接视为同事件已否定；计划、延期、取消医嘱属于TP-D03及事件状态边界，需要适用性/有效医嘱事实证明。不得由“出现未字/拟字”Python关键词判state，不把医嘱`order_status`硬映成临床实施。N13竞争partial与日期绑定能力保留，不在R3跨药剂量补修时顺带改变。

### A4. 准确文件和所有权交接

相对于`apps/medqc-web/backend/`：

|文件/符号|建议责任与边界|
|---|---|
|`app/services/luxian_0609/chemotherapy_local_dose_facts.py`：`OriginalSpan`、`LocalDoseAction`、`LocalDoseResolution`、`_parse_actions`、`_restore_original_actions`、`resolve_chemotherapy_local_dose_facts`|只负责关系schema、严格原文/引用/预算/usage/隐私输入检查及内部事实；不用药名/数字/风险词分支；新span均同view验证后唯一回原文|
|`native_tumor_pathology_execution.py`：`_typed_chemotherapy_comparison`、正式026调用处|Python维护事件绑定、状态优先、精确dose比较、计数和真实来源行；受控关系不复用整篇任一数值匹配。旧直调机械入口按现兼容边界保留，不能声称它有新语义能力|
|同文件：`_course_event_candidates`、`_chemotherapy_candidate_has_independent_owner`、`_chemotherapy_time_state`|保留已集成N13保护。本批若需从字符句片段转受控action定位，先比较同输入事件/计数；不得以新的span重新启用不可靠正文任意日期排除|
|`tumor_pathology_result_mapping.py`：`_safe_026`、`tumor_pathology_customer_fact_status_is_valid`|只验证可选新计数的类型/范围/互斥总和/状态；维持local unresolved窄例外及旧无字段合同。不将unknown升级成确认缺陷|
|`rule_contracts.py`、`app/data/luxian_0609_rule_contracts_v1.json`、`app/data/luxian_0609_rules_v1.json`|只026版本/prompt版本；总预算维持2，不增加新调用。整文件等R1锁释放/root唯一owner交接|
|`customer_renderer.py`：026 `chemotherapy_order_course_comparison`分支（当前约2752）|如新否定计数采用，由root安排整文件唯一owner写准确结果/建议；不重判状态，不把否定说成剂量不一致、缺文书或建议补写|
|`canonical_result_finalizer.py`与`decision_model.py`|先用现正式mapping/合同测试核是否可消费，不预先改全局类型/枚举。确需公开字段或reason扩展，由root窄授权、单独交接；不旁路Finalizer|
|`tests/unit/test_luxian_0609_chemo_local_dose_binding.py`|关系工程保护及原五/两个坏响应固定oracle；保留business_oracle实际执行，不跳过|

候选预算8文书/8000原文与view字符/12动作/2048completion保持；新增mention/dose数量须有明确有限上限且避免无上限ID/嵌套，不按每药单独调用。关系schema变大后2048内不能完整列出则失败/未决，不截断冒称完整。升级版本不等于提高预算；原恶性一次+局部一次最多2，无026/不适用/无完整比较事件/材料不可读时按批准触发合同0局部调用。当前候选在缺完整字段时仍可能走has_candidate抽取，需先核触发合同，不仅为了适配0call断言继续无效调用。

### A5. fake只允许哪些协议适配

旧四文件已由`results-current-contract.json.failures`精确定位：`test_luxian_0609_chemo_closure.py`、`test_luxian_0609_native_tumor_pathology_execution.py`、`test_round2_tumor_dose_discharge_boundaries.py`、`test_round4_chemo_dose_and_findings.py`。104节点首停0call，11节点首停语义/计数；这不是104已证明仅fixture、11已证明产品失败。

|fake/调用点|可作的适配|禁止变化|
|---|---|---|
|chemo_closure `_NoModel`及`_run`（约30/60/71）；round2 `NoModel`、`execute`，round4复用该execute|针对正式026需要局部调用的原输入，显式注入**预先手工标注**关系响应；无语义触发病例仍NoModel。更新其真实新调用/usage断言，先解开前置遮挡，再看原断言|保留原rows、参数、状态、field_results、missing/unresolved/unknown_time、证据/保存/文案断言；不得从正文关键词/预期status自动产出模型答案|
|native测试 `_Client`（约73）与`_RawResponseClient`（约105）|原恶性`lx0609_malignancy_v1`响应序列不变；在真实新增调用点追加手工局部响应，带单choice `finish_reason=stop`、完整usage、max_completion=2048、retry=False消费；原错误响应client仍保留其失败场景|不得把所有_Client改成宽容万能fake或改变其他规则恶性/病理响应；不得让队列弹出错schema后蒙混绿|
|专属 `OfflineLocalDoseClient`、`HandLabeledClient`、`_action`、`_fixture_actions`（约128–173及后续）|v2版本与ID/mention/action/dose结构可按原人工语义标注增加字段，hand facts不依赖生产提取器；实际/计划/否定分开列|不能把widened坏响应中错误剂量owner改正确、补一个正确120mg响应后仍称同个坏oracle通过；不能按case_id在生产加分支|
|旧11语义/计数首失败节点|逐项明确新客户端是否没提供合法抽取回执（当前_Client缺finish_reason）、是否多一调用，保留原断言重评|不能预先归11全部fixture；N13原六NC/两计数仍开放，不能改它们预期|

必须保持的11节点族：`test_typed_026_compares_four_structured_order_fields_without_model`两参数、`does_not_borrow_fields_between_chemotherapy_events`、`fails_closed_when_two_orders_share_one_course_clause`、`keeps_one_event_fields_together_within_one_course_record`、`keeps_each_multi_drug_event_with_its_following_detail_clauses`、`does_not_take_detail_clauses_past_the_next_drug_name`、`binds_course_time_semantics_to_record_date`三参数、`test_inpatient_uses_admission_diagnosis_for_026_and_skips_027`。名称含without_model的旧测试应保留医学断言并明确新合同，不能仅改名或0call就声明行为等价。

### A6. 最小保护及停止规则

先冻结附录设计与原输入/oracle，未来唯一测试槽可用时分层验证：

1. 原五、negated原NC、widened坏响应原NC全量实际执行；新增正确关系下目标不一致NC、完整匹配C、执行与计划并存只比较真实执行。原坏响应未达就保留失败，不用新测试替换。
2. 关系工程负向：跨药owner、跨文书owner、同剂量双独占、participant不属于action、漏文书、重复ID/key、遗漏共同药物、动作scope跨到另一药、空剂量、多实际动作、shared/uncertain、否定作用域属于另一药/另一事件。自洽错误owner单列语义反例，不能只用几何违规例证明归属安全。
3. 泛化变换由人工标注：替换药名、替换相等/不等数字、互换药物顺序、反向句法、共句与跨句、插入非剂量数字、医嘱正逆序。生产不识别任何测试case_id；变换保持临床关系，不能用自动标签生成器充独立gold。
4. N13原47观察与N01/N07、原四文件保护；原missing_order/unknown/local计数互斥、bool/负数/超界/缺字段/旧facts兼容、确认NC+独立未知的窄合同、全未知不得C/NC。新增否定计数如采用，要先原公开合同红例，再合法C/NC/DG及混合计数、篡改拒存/SQLite新实例回读；同一否定证据不能既计缺文书又计已确认冲突。
5. 正式privacy wrapper地址/电话/多文书、同view精确quote、重复quote回投拒绝、已知身份failclosed；8/9文书、字符/动作/输出上限、深层JSON、finish_reason/usage、运输失败一次计账、不retry/不切片、恶性+局部真实总2。纯工程保护不代替真实模型关系准确性。

未来同一根因最多3轮有明确假设的修复/验证；每轮固定输入、预期、源码hash与首失败，不能在轮间改临床oracle。同根因第三轮仍失败，立即停止扩修并向root报告原反例、三轮差分/证据及未决能力；不第四轮增加关键词/药名/数字特判，不把测试支撑错误当新产品根因凑轮次。真实语义批次仍待root另核授权和预算，本附录未授权调用。
