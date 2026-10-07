# 0916 连续批量验收目标

用户于2026-10-07要求设置长程任务、批量执行，减少逐步暂停。已建立当前任务长程目标及30分钟heartbeat续跑；无实质变化时不通知。达到本批批准标准后提交并停止扩展，自动续跑只继续未完成的授权事项。

## 证据与方案

018：上批root独立重放证实，raw明细夹具只有item_id、没有document_id，现有权威身份合同拒绝它；内存补齐后四Worker结果恢复且22项身份保护通过。实现前再次读取D工作区test_batch_worker.py与critical_value_018.py，确认代码及夹具仍未变化。本次最小方案只给该fixture补document_id=ITEM-1，不放宽生产身份校验，不改变模型输出或判定。

文件白名单：backend/tests/unit/luxian_0916/test_batch_worker.py单行fixture、本文及统一进度表。测试文件新增不是生产职责，不增加生产巨型文件内容或抽象。实现Agent只负责测试文件；root负责文档、审查与限定提交。假设需再次证伪：该单行能恢复四Worker预期且不影响缺失/重复身份拒绝；如失败，保留证据而不扩大修复。

验收指标：四个Worker参数化用例分别恢复原状态/原因，阶段二替身调用各1次；现存22项身份保护不回退，运行相关Worker测试；无真实模型、无PG连接/写入。通过仅表示测试夹具迁移完成，不计018临床或完整规则验收。

032：并发只读复核上批两例unknown工程草案和保存投影，找出能由现有材料回答的具体缺口。保留原始冻结预期，不改为确定临床答案、不新增来源/Prompt/模型调用。若材料不足，精确记为待复核并停止该路线，不用更多无意义探针填补统计。

023：旧副本只有bundle_status/updated_at漂移，原文/答案/旧job未变；原因未知。仍须用户明确批准仅这两个字段现值另存保护基线，不修改旧行/历史产物。批准前不执行runner。原一次新任务、4generate/8attempt、两现有身份各一次定向upsert预算不变，禁止旧job重入、人工预期修改、额外数据库写入或临床/上线批准。

## 协调与风险

并发仅用于互不写同一文件的实现和只读证伪，使用Sol6.1 medium；root亲审diff及实际输出。每个闭环限定路径提交，保留他人暂存/未提交改动。临床争议、授权不足、源码或材料漂移分别停止对应路线，其余独立事项继续。

完成本批目标后暂停heartbeat；全部剩余事项需用户决策时也暂停，避免定时空跑。不会自动将下一规则族加入本批，不将单测、整包回放或规范文档完成计算为单规则验收通过。

## 当前闭环结果

018正式fixture仅新增document_id=ITEM-1一行，生产文件未改。实现Agent三文件实际54通过，pytest计时0.99秒；root亲审单行diff并独立运行四Worker节点+22Stage1保护，26通过，pytest计时0.42秒（整个命令8.04秒含导入）。四分支状态/原因恢复原合同，Stage2各1次替身调用；provider/contract失败仍是data_quality_gap，不伪造成临床结论。正式pytest既有conftest导入app.main会初始化本地demo_feedbacks SQLite；不声称全环境零数据库副作用，没有正式PG任务/真实模型/HTTP。私有无conftest观测另26通过，实际结果见.tmp/0910-full-audit/20261007-018-fixture-observe-private.json。

032必须更正H31中的引文可见性判断：C30完整复访引文原裸字符串不在JSON编码Prompt中，不代表未送模。root独立解析保存Prompt的“待提取文书”JSON尾部，解码文书与selected及原始raw_text均逐字相同，长度2209、truncated=False；完整引文存在于解码content。此前裸字符串匹配被JSON换行转义造成假阴性，撤回该例“尾部截断/复访引文投影遗漏”说法；旧报告保留并附此更正，不覆盖冻结预期。证据见.tmp/0910-full-audit/20261007-032-json-visibility-root-private.json。C01带药适用性、C30个性化指导充分性/时间字段意义仍需人工复核，两例unknown不改，无新临床gold。

023仍未得到技术字段重冻结明确答复，不执行新任务。018最小修复与032只读核对达到本批可自动完成的标准；长程目标保持未完成，heartbeat下一次先检查授权更新，若全部剩余事项仍需用户决策则按保存提示暂停，避免空转。收到授权后继续未完成任务，而非重复已完成测试或模型任务。

提交门禁：check:encoding通过，lint -- --no-fix退出0（0错误、1214项现有警告），限定diff无空白错误。无前端/共享类型改动，未跑全量type-check/test:unit。暂存区含他人两份文档，使用限定路径提交并仅在单次提交进程关闭Husky，避免lint-staged改写他人文件；编码/lint已手动补跑，不修改钩子配置。

## 023续验授权

用户明确确认：允许仅将bundle_status、updated_at现值另存保护基线，按原预算继续023验收。root重新核65份实际生产源码与已审v2快照逐字相同；测试夹具提交不在生产集合内。下一步只读重新查询原两旧副本，确认历史差异仍仅属于原来那一个旧副本的两个已授权技术字段，其余字段/原文/旧任务及两新副本不变；另存精确现值基线，不修改历史文件。若再有其他漂移则停对应任务，不自动吸收。

私有v4 runner只替换OUT/STOP路径、添加已批准基线的冻结输入及严格整体比较；不得排除技术字段、放宽SQL或模型预算。独立审查须证明新基线允许当前两技术值，但原文/预期/身份/其他字段变化均拒绝。root执行一次正常新任务及两定向刷新，正常退出join及保护复核，另独立PG回读，最后真实浏览器确认本轮新run两结果。当前只验证两例023存在性正例，不升级完整临床验收。

## 023实际请求的内存异常

root21条只读语句完成精确现值重冻结，所有旧任务/临床材料及两新副本保持；v4窄差分23项root重跑通过，C三独立突变拒绝。实际启动完成acceptance零DDL门禁、内存账号认证及两新visit定向API核对，随后发送一次run POST。

实际失败不是质控判定：调用栈在rule_validation.begin_run的第一条INSERT进入before_cursor_execute后，私有guard.save对报告json.dumps的encode/join出现MemoryError，HTTP500；finally读取冻结源码再次MemoryError，不能宣称最终保存、正常join/退出保护已全部完成。最后有效报告仍initializing只是中途快照，不是仍活进程。root确认进程31560已退出，临时8003/3003无监听，关闭本批登录页，未登录结果页面或关闭他人服务。

root另独立只读PG核从started_at无新023 run、无creating run，旧job/run及旧模型事件不变；两旧副本等于批准后现值，两新sample/anesthesia/running逐字逐值不变，冻结源码/私有输入一致。结合真实before_cursor_execute调用栈及begin_run事务代码，确认没有新任务创建；最后有效报告模型0、DML0。此处不能用未完成finally宣称全环境零写入，app导入仍有本地SQLite初始化。原POST一次额度已使用，不私自重提；实际新任务/模型/定向Bundle额度未使用。已集中请求仅额外一次POST重提权限，其余上限不变。

最后有效报告约9.3MB，序列化失败后其他读取亦OOM，说明整串序列化是观察到的失败点，不足以证明它是主机资源不足的唯一原因；退出后资源回升不是故障现场可用内存。先仅在私有新版本将落盘改为流式json.dump+临时文件原子替换，降低额外整串分配，不改生产/Guard/预算或保证主机OOM已解决。

串行文件IO候选v5另有合成并发风险：root首次无序双线程未复现，保留失败脚本；C受控关闭流后首replace先完成再让第二replace，root独立重放均得到首成功、第二FileNotFoundError。它证明共享临时文件在该调度下不安全，不是v4 MemoryError现场原因。v5不得正式使用；仅另v6复用已有guard.RLock包住整个save，验证并发与可重入后再审，禁止新增平台或改变临床合同。

v6纯文件IO候选已完成，root亲读原Guard构造器确认先建立threading.RLock、没有在构造期间回调save；runner首次save发生在构造完成后。root另执行实际AST保存测试8项：与v5成功字节/解析值相同，中段MemoryError旧报告不变，后续恢复；两并发保存全部成功、最大dump并发1、save_count2；已有锁内回调save可重入无死锁。除保存块及新OUT/STOP路径外原源码逐字保持。它只降低额外序列化内存、避免新增临时文件竞态，不保证主机资源或正式验收；没有执行v6、新POST或新增模型。

证据：.tmp/0910-full-audit/20261007-023-approved-technical-baseline-private.json、20261007-023-v4-narrow-root-private.json、20261007-023-v4-memory-stop-root-private.json、20261007-023-v4-memory-stack-root-private.md、20261007-023-v5-save-ordered-result-root-private.json；最后有效v4原报告保留于B树，调用栈相关摘录在D树，过程数据均不提交。
