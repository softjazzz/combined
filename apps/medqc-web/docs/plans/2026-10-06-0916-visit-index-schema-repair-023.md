# 0916索引结构修复与023正式验证 Implementation Plan

> 用户2026-10-06明确授权数据库结构修复；沿用此前两新副本、一次正式任务、最多八模型调用预算。使用本机writing-plans/executing-plans工作流。

**Goal:** 只补实际visit_index三个缺字段，恢复已批准的验收启动门禁，再完成023两个麻醉记录存在性正例的正式交付验证。

**Architecture:** 在既有Alembic链追加单条可重入迁移，不改正常同步或质控判据。主协调使用应用连接的短事务、明确qc对象和SQL白名单执行该迁移及必要版本登记；正式验收另开无DDL护栏，两阶段权限不可混用。

**Tech Stack:** PostgreSQL18.3、SQLAlchemy、Alembic、pytest、正常FastAPI/Worker/认证浏览器入口。

## 证据、假设与范围

主协调当前只读PG核对：应用DB_SEARCH_PATH=qc,sys,cdm,public,legacy，实际解析qc.visit_index(OID199967)，不是public同名表。qc约15行、public1行；两表不能由名称混同，不更改public。实际schema及OID须在写事务内再次确认，不只靠既有产物。当前public.alembic_version唯一20261003_000046，仓库最新也是该版本。

visit_index_service.py:26–36现有合同定义latest_mirror_success_time为TIMESTAMP NULL、mirror_delay_base_minutes及sync_interval_minutes为INTEGER NOT NULL DEFAULT30，当前qc缺这三列。现有九列、三坐标主键/索引正常；scene_history已有[]默认，无需新增字段或改变其默认。实际无用户触发器/检查约束/RLS。只读元数据是已观测证据，待证伪假设：该增量迁移可恢复现有写入合同，且不改变原列/原值、约束、索引和资料所有者。

## 白名单与事务

- 新增backend/alembic/versions/20261006_000047_visit_index_sync_fields.py，down_revision=20261003_000046；现有split模式仅qc，single模式按旧迁移惯例public。本次执行只允许split/qc。
- 新增backend/tests/unit/test_visit_index_sync_fields_migration.py，只验证该迁移公开upgrade：三类型/空值/default30、已有合法列不重复DDL、类型/空值/默认错误拒绝、缺表失败；downgrade拒绝自动删既有字段，参照000043。
- 两生产门禁模块不再修改，main/env/巨型创建服务/其他规则一律不改。迁移为现有结构版本责任，预计不足100行，不构建新平台或新增事实owner。
- root私有执行及formal脚本仅.tmp/0910-full-audit/*-private；原文/标识/过程日志不提交。长期仅本文及统一进度表。

执行前冻结源/目标版本/列合同并审查。真实事务设置lock_timeout=5s、statement_timeout=30s；仅锁qc.visit_index，列出最多101原行的原九字段，超过100即停止不扩大读取。在锁内核实际OID/schema及现有列，执行最多三条ADD COLUMN，绝不ALTER原列/UPDATE病例/创建表或索引。新增列提供两个30默认，使旧行读到新字段默认值；这属于获准结构增量，不冒称新字段从原业务数据回填。原九字段前后逐值相同，行数/OID/filenode及原列/约束/索引不变，然后在同连接校验现有验收合同。

唯一额外技术写入为public.alembic_version从唯一46登记到47；通过既有Alembic MigrationContext/Operations执行单条迁移和stamp，不运行upgrade head的未知链，不改其他版本或业务表。所有步骤同事务，失败回滚；提交后另连接只读重新检查三列及公共启动门禁。实际SQL只允许这三ADD、目标锁、元数据SELECT/SET及该版本登记，其他DDL/DML立即停止。没有授权DROP/DELETE/旧病例或结果更新。

## 并发分工与验收

实现cost_fix_offline_20261006负责迁移/测试两路径，禁止自行PG/HTTP/模型/提交。prepare_018_offline_20261006独立离线审查修复合同/事务脚本，仅其树私有产物。cost_review_010012_20261006准备023正常运行私有脚本及完整身份/写入/调用护栏，0执行；root亲自审核后运行。均复用现存Sol6.1 medium，不新增工作树，保护他人修改。

先迁移公共入口红→绿、SQL编译/独立证伪，再root实际受控迁移和原值保护。修复后验收阶段重新恢复零DDL：正常lifespan/auth、新副本test-records、对应Bundle及工程预期、新023 run/leaf、PG/API/逐例页面。两DTO保留原麻醉文书，假名元数据不代表原患者，独立工程预期仍非clinical/gold批准。

正式阶段预算最多两副本创建POST、两新工程答案PUT、一次run POST、八generate/attempt/HTTP（所有重试合计，018Stage2禁止）。先核实际族调用路径是否可落预算；任何超量、越界、源漂移、非目标旧对象更新、DDL或模型失败均保存产物停止，不重新提交任务或改预期。若两副本整包，64计划对须恰好各一个合法结果或执行失败；023目标须与冻结存在性状态/原因/事实/证据/建议一致，其他失败不伪造临床结论。

PG/正常认证API逐值核公开字段，页面逐例验证；不得以其他病例页面代替缺结果。真实调用参数/Token/API秒/任务墙钟分开记录，未知成本保留不完整。023只验存在性，不声称独立触发/真实缺记录/局麻边界或完整临床验收。临床签认、启用、上线批准均不写。

## 风险与停止

结构ADD持短独占锁；超时/目标漂移则回滚，不扩权限。既有qc/public同名表未收敛，但当前读取明确qc；本批不扩到跨来源治理。原行比较仅qc索引原列，不声称全库冻结。外部并发事务在提交后可改变表/源码，正式执行前后重新核；不能改他人8001或旧任务恢复。

编码/lint、聚焦Python回归后只提交本任务四路径；他人两暂存文档保持，必要时关闭本次Husky并手动补门槛，理由写提交说明。有限闭环结束报告并停止，不迁下族、不调首程Prompt/运行018模型。

## 结构修复实际结果

迁移公开upgrade先红23失败/7通过（空实现），最终33项通过；主协调独立合并门禁/同步共117项通过（pytest1.18秒）、ruff通过。root首次使用confcutdir排除应用conftest后漏PYTHONPATH，收集出现2个ModuleNotFoundError；补正确backend导入路径后通过，没有为此改生产代码或测试判据。

独立审查定位root事务脚本初稿未锚定预期OID、提交后只检查字段存在而没检查type/default。主协调反查自己的初稿及共享门禁只读取column.name的实际实现确认后，在任何DDL前补OID199967锚、提交后独立只读连接复用migration.upgrade完整合同及幂等检查。另补拒绝DDL事件触发器及版本表用户DML触发器/规则。安装Alembic的stamp/update源码和实际编译SQL经root亲读，确认外部事务中只执行唯一版本UPDATE，不自行提交或运行其他迁移。

root受控实际事务成功提交：3ADD仅qc.visit_index，1UPDATE仅public.alembic_version的46→47，5秒锁等待/30秒语句超时。该执行探针统计77 SELECT/4 SET/1 LOCK/3 ALTER/1 UPDATE；不是此前全部元数据读取量。原九字段的列元数据与15原行逐值完全相同，主键、索引、检查/外键、OID及filenode均不变。旧行仅新两字段读到默认30，时间字段NULL；没有业务回填、旧病例/预期/结果更新。没有修同名public.visit_index。

提交后独立只读连接核三列type/null/default并重入upgrade无新DDL、版本47；公共启动门禁passed。root另外一进程重新解析原/后JSON确认保护集合相同，再新连接核实际三列及版本仍47。当前只关闭结构合同缺口，不能算023已运行或临床通过。正式阶段尚未执行，权限恢复零DDL。

023存在性工程预期另确认：root亲读input_context.py:190–228及surgery_consent_rules.py:153–184/264–275，023判定只看event/presence；024有效逐项抽取可改变运输的completeness/docID/evidence，不能用它倒填023人工质量预期。POST前冻结核心存在性结果及条件证据定位合同，全部实际公开字段PG/API逐值比较，不修改H22旧预期，不把024质量算023临床验收。

私有证据：[受控事务及原值](D:/LLM/LX888/apps/medqc-web/.tmp/0910-full-audit/20261006-schema-repair-root-private.json)、[实现红绿](D:/LLM/LX888/apps/medqc-web/.tmp/0910-full-audit/20261006-visit-index-schema-repair-implementation-private.md)。患者标识/原行及过程脚本不提交。

独立[迁移与事务审查](C:/Users/Coldplay/.codex/worktrees/lx0916-015016-acceptance-20261005/LX888/apps/medqc-web/.tmp/0910-full-audit/20261006-schema-repair-review-result-private.md)未发现剩余阻断。root另外解析其原JSON核迁移源码逐字绑定，8不兼容反例全在DDL前拒绝，3ADD+1版本UPDATE编译精确，外部事务true/框架自身commit0。独立离线探针root源码冻结早于最后两个版本触发器/规则SELECT；代理及root对最后增量另亲读核定，未把较早探针写成完整最终源码执行。实际迁移及回读由root真实PG产物证明。

提交前只检查lint已通过；编码手动补跑。因暂存区有他人两文档，本次仅4路径限定提交并关闭本地Husky，避免lint-staged改写他人文件，理由写提交说明；不改CI。完整前端type-check/test:unit未跑，使用仓库允许的编码/lint及117聚焦Python回归。

## 正式验证实际停止与纠错

结构迁移及测试已提交为`0b7e4a39e`，此前验收只读门禁为`4e23ff55c`。以下是私有验收脚本的准备及执行记录，不另算生产引擎缺陷或质控点通过。

初次子进程在应用导入前因继承的模型凭据与项目环境不一致而停止，0外部调用；后续仅在该子进程绑定项目现有配置，不改全局环境或模型配置。formal1要求PG持久化qc_manager账号，17 SELECT/3 SET后停止。root反查auth_store.py:218–235及storage/memory.py:46–59，确认当前非生产正常认证支持既有内存测试账号，并独立核不存在PG账号/ID/email冲突及现有密码匹配；没有创建账号或绕过认证。formal2又因私有护栏误把刷新记录owner设为public而停止，56 SELECT/3 SET。root用实际源码refresh_manager.py:275–286及连接解析核裸SQL指向qc.bundle_refresh_failures(OID200356)，public同名表(OID207742)只供既有存在性gate，两表字段相同；这不是新增结构缺陷，不迁表。两次均0 DDL/DML、创建、工程预期、任务及模型，旧产物保留。

正式护栏离线曾发现NOT和跨schema反例；修正后最终v5为47/47，root独立重跑root-v5同样通过。认证ORM及返回合同另有15项保护；正常SDK返回是dict而不是root初稿误设的str，已按qc_llm_client.py:189–198/322–342纠正。root亲自逐字符核formal2→formal3差分仅唯一qc刷新owner、新身份fresh检查及新的产物路径；预算/身份/来源冻结/生命周期未放宽。代理延迟worker替身证明正常finally要在guard内join再检查旧材料，但不是实际hard exit的退出证明。

formal3真实执行通过正常acceptance启动、401保护和既有内存qc_manager正常login/me；这不代表生产持久账号链已验证。两次新副本POST已发出，C02响应200，C03响应未完成。护栏随后因`sample_update_old_or_unbound_id`硬停止，尚未进行两次工程答案PUT、一次run POST或任何generate/SDK/provider调用。停止前记录868 SELECT/6 SET/28 INSERT/10 UPDATE，0 DDL；这些是before_cursor_execute放行记录，不能直接等同已提交数量。没有sys用户、任务、结果或模型事件写记录。runner记录4个完成HTTP200，另有未认证GET401和一次浏览器正常登录尝试，不能把4当全部网络请求数。

被拦截语句/context没有保存，不能由原因码断言本次试图修改旧对象，也不能直接断言编译缓存导致误报。hard exit未经过finally，产物没有退出来源检查/worker join字段，不冒称实际退出核验已完成。本批不放宽护栏、重跑创建、补写C03状态或删除副本。

独立离线反例发现私有护栏的确定性缺陷：相同形状Core UPDATE第二个新ID命中SQLAlchemy编译缓存时，cached BindParameter.value仍为第一个新ID，实际绑定已是第二个新ID；护栏要求二者相同而拒绝合法更新。禁缓存对照两条均通过。root亲读实际创建尾部custom_qc_sample_pool_service.py:4516–4521确为Session.execute(Core UPDATE)，并核保存反例源码逐字等于formal3冻结guard、同一compiled对象、actual/bind差异和禁缓存对照；只确认合成机制，不把它倒推成本次正式停止的已确认根因。该私有工具缺陷不归到生产质控引擎，仍需被拦现场证据；本批不继续扩大修复或运行。

root另开独立只读进程37 SELECT/1 SET、重复读事务回滚，核两新身份各有patient/registration/mr/anesthesia、qc索引、running/final及六领域Bundle；两样本均已存在，C02 ready/synced、C03 pending/synced，均无latest_job_id。冻结两例原麻醉/手术及旧raw_payload逐值未变，冻结生产及私有源也未变。保护范围只是这两例冻结集合，不声称全库或未保存的环境快照不变。临时8003后端、3003 Vite与本批浏览器页已关闭，未触碰8001；没有023结果页面证明。

023仍未完成正式工程验收：两次创建额度已使用；工程预期、任务及八模型额度未使用，不据此自行再执行。后续只读定位私有护栏的拦截边界，优先复用现有副本；任何新写入/重跑均需新的明确闭环。患者原文、标识及脚本全部私有保留，不提交；临床签认/启用/上线批准均未写。

私有证据：[formal3停止](C:/Users/Coldplay/.codex/worktrees/lx0916-independent-regression-20261004/LX888/apps/medqc-web/.tmp/0910-full-audit/20261006-023-formal3-result-private.json)、[root独立停机回读](D:/LLM/LX888/apps/medqc-web/.tmp/0910-full-audit/20261006-023-poststop-root-private.json)、[独立日志复核](C:/Users/Coldplay/.codex/worktrees/lx0916-015016-acceptance-20261005/LX888/apps/medqc-web/.tmp/0910-full-audit/20261006-023-runner-review-formal3-stop-private.md)。

## 用户同意创建后的最小续验方案

用户再次明确“同意创建”。当前两例已落库，第二例样本pending；root亲读qc_sample_pools.py:1077–1098及inspect_run_selection，正常入口仍会拦pending，不绕过就绪门禁。已向用户确认复用两例或另建两例的范围；未答前只离线准备，不恢复写入。若另建，最多再两新副本、两工程答案PUT、一次正式任务、八SDK/provider尝试（含重试）；上一批副本不更新、不删除。若复用，须先核正常定向同步的新增写范围，不能把创建许可自动扩成任意状态回填。

已确认问题仅为合成Core缓存触发的私有护栏误拒；formal3真实根因仍待证伪。A独立新guard只移除ID校验对cached默认值的依赖，保留精确WHERE/表列归属/BindParameter/compiled绑定名及当前实际参数属于获准ID集合；运行state、预算等不放宽。拒绝时只保存该语句最小私有上下文。先原冻结guard红例，再同缓存绿例与旧ID、缺绑定、NOT/OR、跨schema及额外谓词拒绝对照。B新formal4草案保护旧副本及原材料，C独立证伪，root亲审关键diff和真实产物后才执行。三树既有Sol6.1 medium，0外部准备；旧formal产物不覆盖。

生产文件白名单为空；代码仅各树.tmp新private guard/probe/runner，长期更新本文及统一进度。此职责是一次性护栏修复，不向巨型生产文件新增逻辑、不建新事实Owner/通用层；新增SQL诊断预计不足30行，不做结构拆分。最终仍核64计划对交付完整性、023冻结存在性核心事实及条件证据、PG/API八字段和逐例页面、实际模型参数/调用与成本。来源漂移、越界、DDL、超预算或模型失败保存停止；无临床签认、启用或上线批准。instrumentation下墙钟不能声称生产性能。

本轮范围更正：root进一步查正常样本就绪入口及测试副本路由，pending不能直接复用且未找到简易状态恢复接口；初先建议复用需额外同步写入，不应默认扩大“同意创建”的授权。可选范围问题未得到回复，因此依用户明确创建请求采用最小创建闭环：仅另建两新副本并PG/API/页面存在回读。formal4中两PUT/run POST/generate/SDK/provider HTTP预算全部硬0，创建后停止，不动以前全链剩余额度；旧两副本保护不更新。此前所列一次任务/八调用只是旧剩余额度，本轮不执行。副本创建成功不算023规则验收通过。A私有缓存修复净增14行，root已独立49/49通过，C另6反例通过，均0外部；正式停止因果仍不倒推。

执行前进一步纠错：root亲读list_pool_items/list_pool_records发现均调用`_heal_customer_test_bundle_statuses`（custom_qc_sample_pool_service.py:5105–5164），GET列表可自动refresh与更新pending，故此前“无简易恢复入口”不成立。该机制尚未实际用于本批旧副本，不默认扩大授权修复旧状态。本轮撤销普通样本池页面及等待窗口，避免页面全列表扫描旧pending造成写入；只按当前新visit限定GET items，已ready新行在5118直接跳过自愈，创建后独立PG/认证API逐值证明后正常退出，页面明确未复核。HTTPhelper新增items/records查询必须匹配本批新visit的门禁。根因口径更正留痕，不把GET自愈改作本轮生产修复。

## 创建闭环实际结果

formal4于本地2026-10-06执行，UTC2026-10-07 01:13:36正常退出0：两次正常创建POST与两次按新visit限定的认证GET均200，两新样本PG状态ready/synced，无latest_job_id、golden_answers为空，原麻醉正文保持。新索引、running/final及六领域Bundle均存在。API返回唯一新item ID、三坐标、raw_payload及ready与PG逐值一致；q本身仍为既有多字段ILIKE，不冒称数据库层三坐标精确筛选，旧写入同时由guard拒绝。

护栏记录910 SELECT/9 SET/28 INSERT/12 UPDATE，0 DDL，全部新身份及指定样本池计数范围内；这是before_cursor_execute观测，不单独当提交凭证。正常finally在guard内关闭服务、join detached executor，再核原两源/旧预期及formal3两副本整行/麻醉前后、退出逐值相同；源码/.env/内存认证源及旧formal3归档未变，PG auth写0，violations为空。root随后另一进程32 SELECT/2 SET只读回滚，亲自核两新样本/麻醉整行等于保存产物、9张索引/Bundle各1行、原材料和旧两副本未变；不是只引用runner布尔值。临时8003/3003无监听，未打开普通样本池页面；页面明确未复核。

本轮PUT/run POST/generate/SDK/provider HTTP全0，没有执行023临床判定、保存规则结果或签认/启用/上线。缓存双新ID护栏红→绿与49项保护、独立6项缓存反例、最后窄GET约束独立3项通过；它们只证明私有创建护栏和范围保护，不倒推formal3缺失现场的根因。两次新创建预算已使用，不继续第三例；新两副本仍来自同两份原麻醉材料，不增加独立真实病例覆盖数。下一次正式验证应使用formal4新item ID/三坐标，不要用同名旧pending副本或重新建例。

本批主要证据：[正常创建及认证API](C:/Users/Coldplay/.codex/worktrees/lx0916-independent-regression-20261004/LX888/apps/medqc-web/.tmp/0910-full-audit/20261006-023-formal4-result-private.json)、[root退出后独立PG回读](D:/LLM/LX888/apps/medqc-web/.tmp/0910-full-audit/20261006-023-creation-root-readback-private.json)。新item/visit/doc坐标、原文、全过程脚本均只留private，不提交；instrumentation启用的耗时不作为生产性能收益。

独立[实际产物复核](C:/Users/Coldplay/.codex/worktrees/lx0916-015016-acceptance-20261005/LX888/apps/medqc-web/.tmp/0910-full-audit/20261006-023-runner-review-formal4-actual-private.md)重算日志：12 UPDATE为样本池6、qc刷新成功4、新sample2；两sample实际绑定ID等于本次新INSERT的两ID，旧两ID不在sample DML。7项完成HTTP200（另401保护不入wrapper日志），PUT/run及模型3列表均0。原材料/旧副本before/after/exit/root四方字典相同，61源码/私有快照逐字绑定当前源。独立审查没有连接PG：新行原字典比较来自runner实际保存，root另连接的读取比较由其脚本断言及成功产物证明；不将审查的只读归档当独立第二次PG查询。

## 复用新副本的正式验证方案

用户在创建闭环报告后明确“继续”。本轮仅复用formal4两新副本：0创建、0DDL，两工程预期PUT、一次023正式任务、最多八次generate/SDK/provider尝试（含全部重试），018 Stage2调用禁止；不写临床签认、启用或上线批准。实际源码与formal4冻结快照仍相同，root亲读023执行器确认仅消费事件和presence，024完整性只能记录实际值，不能倒填023预期。当前待证伪假设是既有护栏在只读核对新副本后预注册其唯一身份/ID/raw，可完整保护正式任务，不需要新增通用层或生产修改。

文件范围：三树仅新增私有复用runner/保护及独立反例，长期只更新本文和统一进度表。生产文件白名单为空，不向巨型文件加入职责。B最小适配原正常认证/启动/答案/run/保存链，A验证既有护栏预注册及旧ID负例，C独立审查；root亲审diff、实际模型输入和产物后执行。进入任何写入前，PG两新样本及麻醉整行必须等于formal4已保存材料，ready/synced、无旧任务、工程预期为空；原材料、formal3旧副本及源码冻结。创建入口始终禁止，GET仅限定新visit或当前run/job，不打开会自愈旧pending的全池列表。

验收：64病例规则对恰好各一个合法结果或执行失败，023两例冻结核心状态/原因/事实/建议及条件证据成立；PG与认证API全部公开字段逐值一致；单独记录真实模型参数、输入、调用/Token、API耗时及任务墙钟。正常退出须在guard内join再核原材料/旧副本、新临床材料和源码。页面只沿不会读取全池的正常结果入口；不安全则明确未完成，不放宽SQL护栏。超量、来源漂移、未知写入或模型失败保存停止，不重提任务、不改预期；两例正例不声称023缺记录、独立触发或完整临床验收。

## formal5停止与原任务单次重入方案

formal5运行前已将实际generate上限从初稿8收紧为4（每例2），SDK/provider尝试各8含重试；没有使用初稿较宽额度。实际已保存两次development工程预期PUT并创建一次run/job；随后私有护栏以`job_update_scope`硬停，generate/SDK/provider均0，没有023结果。硬停未经过finally，不声称完成join或退出校验。root独立只读16 SELECT/2 SET确认原run仍bound、原job仍running，items/failed字段保持INSERT时NULL、两答案已保存，原材料/formal3副本及源码未变。不能把任务创建或预期保存计为规则验收通过。

现场拒绝SQL未保存，正式停止根因仍待证伪。root亲读`custom_qc_workspace_service.py:108`及`batch_worker.py:185`，确认当前正常进度UPDATE使用`id=job AND status!=canceled`，原私有guard只支持单ID WHERE且错误把status绑定归入SET字段。A以冻结真实helper AST编译红→绿：原guard12/13（正常helper误拒）、新guard13/13（正常路径允许、取消/NOT/OR/额外谓词/跨schema/旧实际ID等拒绝），仅证明该工具与当前源的确定性不兼容，不倒推缺失的现场SQL。

本次用户“继续”的原有正式验证范围内，root选择原任务单次Worker重入而非重提run；这是对前述“停止不重提任务”的明确受控续验补充，不启动自动恢复或无限重试。root新增只读6 SELECT/1 SET核原job/run整行仍等于停机证明、池latest_job仍为原ID、两答案未变化、`sys.llm_call_events`该root_job_id为0、原源码未变；只读事务回滚。实际存在正常retry API但它会清空summary/results/cost，本批禁止使用。

实施方案与白名单：仅B树新增private重入runner，采用A新私有guard；正常acceptance启动/login后GET精确原run/job核同一用户、绑定、32规则/2坐标，再仅调用现有`submit_detached_task`一次派发`_run_sichuan_workspace_batch_job`原job。生产白名单为空，不新增公共职责、不修改巨型文件。预注册只能来自上述PG证明的唯一原run/job，禁止所有run/job INSERT、PUT/create/retry/状态手工修复。root亲读`qc_sichuan.py:1828–1864`、`detached_task_runner.py:35–53`及`mark_batch_job_running`确认正常0916 running可重入、会重置started_at和本轮局部成本，不是断点续跑；因0916无该路径领取CAS，须确认旧8003无监听、只派发一次，任何并发/漂移停止。

验收沿用023存在性两例冻结合同、64交付对、PG/API逐值及安全逐例页面；本次新增提交额度0，最多4 generate（每例2）、8 SDK/8 provider HTTP含重试，formal5实际0调用不增加可用额度。模型参数沿用正式配置并逐实际请求校验，禁止018 Stage2。任何新的guard/model失败仍保存停止，不再重入第二次、不改预期。正常finally须guard内join与保护核对，另root独立PG回读。先A/C独立审查、root关键diff核验再运行；不因工具修复宣布临床通过。已停formal5归档不覆盖。

## 单次重入实际停止结果

独立C发现guard第一候选的共享WHERE绑定可掩盖`SET created_by`，root亲自离线复现后拒用；V2仅追加6行实际SET列白名单核验。A原反例红14/15、V2绿15/15，root重跑15/15；C另核合法status、旧actual ID及取消/cache反例。B重入草案7项最小离线探针由root独立重跑，root又要求先在run phase等待原Future完成再PG/page验收。未知不存在表INSERT在额外wrapper解析时可能缺现场上下文，但仍拒绝执行；此诊断残余记录，不扩大本批工具修复。独立审查最终源逐字相同后才运行。

首次子进程预检因继承的DEEPSEEK_API_KEY与项目.env冲突退出，在app/guard/PG/HTTP/Worker之前，没有产物或外部调用；随后只在新子进程绑定项目既有.env，不改全局环境/模型配置。formal6正常acceptance启动通过、401保护及原账号login/me正常，PG/API核原run/job/用户/两引用后仅派发原job一次。冻结的0916语义客户端为qwen3.8-flash、思考开启/budget256、0/1采样；正常共享服务另初始化0.2/0.9客户端，仅供当前入口读取HTTP并发槽，不能把其初始化日志当0916实际请求。没有任何模型请求，不能称该模型已用于本批抽取。

formal6实际硬停`bundle_write_scope`，这次有完整被拦SQL/context：`public.running_record_bundle`三坐标upsert目标是formal4的C03新副本，并非旧病例。日志放行504 SELECT/4 SET/2 UPDATE，两UPDATE均原job（开始/prepare进度），另一次upsert在执行前被拒；日志不是提交凭证。wrapper完成12 GET/1 authPOST，create/PUT/runPOST均0，唯一detached派发1，generate/SDK/provider均0，023结果和64交付验收均不存在。硬停没有finally/Future/executor join/退出保护记录；不拿继承的旧exit_sample冒充本次退出证明。

root亲自另进程只读取证：最后两个成功探针各36 SELECT/2 SET、重复读事务回滚；原两来源及formal3副本逐值不变，两新sample仍等于formal5已保存答案行、麻醉整行不变，九张索引/Bundle全部创建时显式字段与formal4 INSERT参数一致。原run仍bound、原job仍running、results/failed仍NULL、成本0，无该root_job_id事件。首次比较忽略PG会话时区导致naive创建参数与aware timestamp误不等，root查实际timestamp with time zone及TimeZone后按会话时区解释再比较；不把此探针错误当资料改写。未手工修任务状态、回填成本或扩大PG写入。

已验证阻断范围：两新运行scene为bundle-v6，但`_scene_bundle_has_usable_content`都False，ready/synced不等于当前场景可直接消费。root把当前原函数AST隔离于只读PG冻结row，逐例重建当前loader分支为load→再load→assemble→upsert（后两步仅stub，0写入）。实际Worker在[batch_worker.py:430](D:/LLM/LX888/apps/medqc-web/backend/app/services/luxian_0916/batch_worker.py:430)调用[bundle_reader.py:90](D:/LLM/LX888/apps/medqc-web/backend/app/services/luxian_0916/bundle_reader.py:90)，后者force_refresh=False、force_refresh_if_empty=True；[assembly.py:2579](D:/LLM/LX888/apps/medqc-web/backend/app/services/bundles/assembly.py:2579)检查schema及可用内容，不能用空scene直接返回。现场upsert及冻结输入/源码分支证明执行链需要重新装配这一范围，不声称保存了当时Python调用栈。policy-legacy-v1是被拦重装配payload值，不是已确认的policy漂移触发原因。护栏run阶段禁止Bundle写入而拒绝，没有023医学判定问题或模型失败证据。

root浏览器通过正常表单尝试登录，但前端[apiService.ts:57](D:/LLM/LX888/apps/medqc-web/src/services/apiService.ts:57)15秒超时先报错，后端同次请求稍后才返回成功；没有页面结果回读证明，不为本批改超时或注入token。本次启用私有profile/SQL/快照保存，墙钟不作为生产性能数据，也未证明超时由instrumentation单独造成。8003后端已退出，3003 Vite及临时浏览器页已关闭，未触碰8001；本轮不再第二次重入，也不重新创建任务。

后续先按当前场景读取合同只读核专项副本的可用内容及正常重装配会写的精确范围，再确定最小修复；不能仅把样本状态改ready、放宽所有Bundle写入或重复跑模型试错。本轮临床签认/启用/上线批准均0，023专项存在性仍未正式闭环，分类与完成数不增加。

证据：[formal6硬停现场](C:/Users/Coldplay/.codex/worktrees/lx0916-independent-regression-20261004/LX888/apps/medqc-web/.tmp/0910-full-audit/20261007-023-formal6-reentry-private.json)、[root独立PG及纯分支重建](D:/LLM/LX888/apps/medqc-web/.tmp/0910-full-audit/20261007-023-formal6-stop-root-v2-private.json)、[独立实际归档复核](C:/Users/Coldplay/.codex/worktrees/lx0916-015016-acceptance-20261005/LX888/apps/medqc-web/.tmp/0910-full-audit/20261007-023-formal6-actual-review-private.md)。患者原文/完整标识/过程脚本均仅private，不提交。93项聚焦Python回归、编码与只检查lint通过；无前端或共享契约修改，未跑全前端type-check/test:unit。
