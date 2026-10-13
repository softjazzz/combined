# N12受控事实合同（预先冻结，未运行）

基线036999e40cf88fc41261b2562aaccf414549db33，新分支codex/qc-fix-anesthesia-20261008；旧ledger分支保留，切分前后均clean，不reset/stash覆盖。只授权LX0609-04-04-02离线工程接入，无真实模型新批次授权，不表示语义验收。

独占native_surgery_document_execution.py仅037、新anesthesia_visit_fact_extraction.py、test_n12_anesthesia_visit_controlled_facts.py及本文。目录权限唯一命中app/data/luxian_0609_rule_contracts_v1.json该entry，获root批准v2→v3、program_only/0→program_then_optional_llm/1；extension没有该entry不修改。禁止其他目录、native_extended、critical、reader、共享Renderer/Finalizer/mapping写入。

四条原反例：术后意识状态→consciousness_status；术后呼吸情况→respiratory_status；术后并发症情况→complication_assessment；Mallampati气道分级→术前airway_assessment（本rule已有气道字段，不新增Mallampati或ASA必填项）。原临床输入只把相应已填片段替换成空标签，复用round6限定反例；正常ASA、有效阴性、神志清醒心率等保护原输入不变。N10继续开放，不纳入本次。

结构：ASA/signature/time沿用可靠结构字段；不存在的结构字段不注入作为SQL证据。明确空正文其余语义项缺失可0调用；非空自由正文最多1次有界批量抽取，原正常保护由0到1是本次显式权限变化，旧NoModel/0断言不改，另列影响。触发/来源/关联错误先行0调用，不跨不同麻醉事件拼材料。

模型仅输出schema_version/documents(document_ref,fields)，每字段严格包含state(present/absent/unknown)、同文书span_id与start/end/quote。present原值片段由既有span回取边界及rescue逐字坐标核查；absent必须start=0、end=本份完整正文长度、span/quote为null；unknown三个坐标/span/quote均null。字段必须恰等于请求字段集合，ID与候选一一对应、无重复/漏项/额外字段。不得输出合规结论、建议、时间/事件判定；Python控制缺项或资料不足。输入最大8份、单份6000字符、总12000，不截候选追绿。

unknown/无client/传输/JSON/ID/字段/引用/全文范围错误或超限均gap，不发布已填或确定missing。明确absent才沿现有missing_fields_by_visit不合规；完整present沿现有anesthesia_visits_complete。先冻结正式Snapshot→native→Binding/Reducer→Finalizer的独立Fake预期，真实模型与临床语义另验收。若现有投影不能接纳gap/安全事实，先报精确接缝，不改共享文件绕过。

预先冻结专属23项：权限1、原空标签4、正常/相邻标签5、非法/失败8、unknown及unknown同回执明确absent2、无client1、跨事件0调用1、真实来源结构空正文0调用1（合计23，实际pytest收集为最终依据）。当前未运行、生产未改；等root分配测试槽先红再实施。所有Fake为合成固定事实，无真实模型/患者/PG/env读取。

调用必须只使用native传入受控llm_client、复用既有发送边界，不实例化客户端或旁路identity provider；不记录原prompt或原异常。单次回执有任一unknown/非法字段就规则内gap，不因同回执另一个absent下确定不合规（额外合同未授权）。无client→gap及自由正文正常0→1的原输入/医学预期与工程差异单列；不将旧NoModel套件说成全绿。

## 附加冻结（生产仍036，未运行）

保留原23项不改预期，原文件副本存.tmp/n12/frozen-23.py（SHA CA9C8CD2BCB347A89AD2FECE855A2C72C75437BAF90E9E8D48D05D4A29F8F9D3）。追加最终编译Prompt/definition一致性1项；模型无client/unknown/传输的明确抽取资料不足reason3项；来源不可读/查询截断2项；正文截断/范围不完整2项；9份、单6001、总12001超限3项；缺/非字符串正文2项，累计36项。不存在的body类型不能转str冒认完整正文。

拟新增唯一data_gap理由semantic_extraction_unresolved，单037内部保留；不塞required_field_missing暗示医生漏写，等root窄锁。Prompt元数据申请catalog仅037.prompt_version同步lx0609-anesthesia-visit-facts-v1；定义版本与现总表保持一致并验证最终编译合同。逻辑调用<=1且本模块不重试，HTTP客户端自身重试预算属独立边界，不能声称真实HTTP<=1。返回的whole-document范围只能校验覆盖声明与输入长度一致，不能证明模型实际通读；语义正确性仍需另获授权的真实响应独审。本轮只Fake工程验收。

## 红测与限定实现记录

冻结36项在未改生产036基线上实际执行：32 failed / 4 passed / 1 warning，3.94秒，全部失败为AssertionError合同差异，无collection/fixture/type失败。原23预期与追加13预期不改；日志.tmp/n12/red.txt，测试SHA256 D9E48177B03C2F61B693DF6D9711EEE949EE4D44F24E3D03E06EE7C037A853C0。四空标签原结论合规、正常旧调用0、失败/未知仍非gap以及旧v2/Prompt元数据是红因；4项既有跨事件/来源截断/不可读/空正文结构保护已绿。禁止据此声称模型语义正确。

实现只替换037正式typed快照链的文书内容事实；先保留原触发、来源与事件关联门控。字段集合复用既有surgery_document_result_mapping.\_VISIT_FIELDS，不建立第二医学必填目录。可靠ASA/signature/time仍Python；非空正文请求其余字段，真实空字符串只提供确定absent，缺/非字符串不转str。不同实际文书不拼半套事实，同事件未知关联保守gap。模型present引用校验受控脱敏正文的同文书span及逐字坐标，未把患者原文外发；引用不进入公共事实。逻辑调用计量含失败1次，原HTTP重试边界不作1次承诺。

已批准窄锁包含主contracts仅037的v3及program_then_optional_llm/1、catalog仅037 Prompt版本、decision_model仅新增semantic_extraction_unresolved集合项；native仅本rule保留该原因。公共Renderer/Finalizer支持由critical owner独立提交，作者不写这些文件，正式公共解释集成验证前不宣称客户闭环。绿测尚未运行。

旧输入/断言变化保留：round2_document_boundaries的037正常、空标签、无效时间、无事件键正常4项仍传入禁止调用的NoModel；旧calls==0将与新许可调用1冲突；跨事件3项仍应0。N08八项与N04/N06的037语义十三项同受NoModel工程合同变化影响，旧文件及医学预期不改。本次新Fake正常和空标签验证医学预期，旧NoModel套件不能作为全绿声明。非typed兼容payload入口沿既有实现，本次没有扩该旧入口或授权语义验收。

037仅限保留既有candidate_scope_incomplete/source_readiness_unproven精确原因亦获root批准，不新增公共集合；分别对应候选预算超限与正文覆盖未证，不转换成适用性缺口。

## 聚焦验证与真实发送链

导入前基线036记录于.tmp/n12/source-baseline.json；仅cherry-pick公共解释源195e20cf16402052acb4aff23f76234d144296f4，本树生成1b973859d，不引入CT03祖先；无冲突，无stash/reset。支持四文件独立提交不计入本作者核心提交路径。

实际43项聚焦：新36全部通过，旧跨事件3通过；旧4在NoModel的零调用断言失败，合计39 passed / 4 failed / 1 warning，2.64秒。没有fixture/collection/真实接缝失败，没有修改旧医学预期；旧4分别是正常与有效阴性、空标签、无效记录时间、无事件键正常。NoModel抛出被新抽取模块捕获并转semantic_extraction_unresolved，逻辑调用1、Token0，故旧calls==0冲突；不将这些说成基线失败或全套绿。无真实模型、PG、env读取。日志.tmp/n12/green-43.txt。

实际生产同受控对象传递路径：execution.py:367-375构建并绑定身份provider再wrap；:453存入LegacyFamilyExecutionResources，:468绑定surgery_document函数；executor_registry.py:591-605直接传resources.llm_client与同一snapshot/materials/typed_rule_ids；native_surgery_document_execution.py:2442-2443→:1104不重建客户端；anesthesia_visit_fact_extraction.py:147唯一generate。llm_prompt_privacy.py:409-423每次发送冻结provider，泛脱敏后检查已知身份及kwargs再delegate；provider失败同样收敛抽取gap。离线直接native Fake不声称自身验证真实发送隐私，真实主链静态传递事实如上，不旁路其边界。

复用\_document_spans（native_preop_content_execution.py:230-239）没有strip；正则覆盖每一个非标点/标点/换行字符，span保持原空格及换行，累加offset按这些完整片段构造。引用坐标针对脱敏后受控正文，同文书逐字校验，不能拿其他文书span借值。待真实模型语义验证与独立生产链复核仍开放，N10继续开放。

## 多文书正常回退阻断与附加冻结（未运行）

独审指出new distinct_documents>1无条件gap误伤既有同application_id=A的多个各自完整访视；这属于待修正常回退，不能称保守合同。原36测试SHA与红绿证据保留，追加5项：同事件两个各自完整术前+完整术后合规/1；两个术前分别缺气道/禁食不能跨文书OR凑完整，非合规/1且缺项并集；不同事件与无共同身份分别关联gap/0；同事件任一文书unknown为semantic gap/1。附加Fake按输入文书索引固定事实，不用生产输出生成答案，不改变原医学输入。

拟仅去掉数量即gap的新增限制，沿原事件关联门控；逐document_ref独立核对，任一unknown/非法全规则gap，全部文书完整合规，存在明确缺项按角色汇总独立文书缺项并集。待root/独审确认后生产改，不运行测试抢槽。

root批准分组补充：材料evidence_material.py:44-74以canonical行与occurrence构造ref，没有拒绝重复document_id。仅同来源且明确同document_id/id可合并分段，缺文书ID每ref独立，不能以业务事件ID合正文。保留原所有material_refs作证据；合并使用内部ref，不新增原始文书ID送模。每行、原行数、合计预算先行，组后正文上限另核，任一片段来源不完整不假装整组完整。新增同doc两半共同完整与可靠ASA/signature/time分散两项，独立附加文件test_n12_anesthesia_visit_document_groups.py冻结7例，原36文件SHA恢复并保持D9E48177...，尚未运行。只批准设计，原版红测后再实现。

## 分组修复与完整旧影响实测

追加7红在未修分组版实际5 failed / 2 passed / 1 warning，14.60秒；失败均为医学/分组合同AssertionError，无fixture回调异常。附加冻结最终SHA256 E116F9EBB4A543BB917E0E6188B1BB72CE0E8E8DA04D0E8AB24E92E8EC021222（红前只修Fake缺少结构签名键风险，不改7项预期）。日志.tmp/n12/groups-red-7.txt。

批准后实现仅同source+明确document_id/id合并分段，缺ID每ref独立；正文组仅内部ref送模，原refs全部沿typed精确取证保留。每个实际文书组独立判定，不同doc缺项不得互补；存在缺项按角色汇总缺项并集。原行预算和组后正文预算同用visit_document_scope_issue，不减少8行限制或吞掉截断/缺正文行。

单进程71实际结果：新36与追加7全部43通过；旧28受影响中3关联保护通过、25在旧NoModel的calls==0断言失败，合计46 passed / 25 failed / 1 warning，3.95秒。旧25细分round2四项、N08八项、N04/N06的037十三项，全部在同一旧调用断言assert1==0失败；旧医学状态断言未执行到，不声称这25医学保护已通过，也不将其说成既有基线失败。旧原输入/预期/NoModel文件未修改，后续测试适配须独立批准且保留医学预期。本次43只证明合成固定原子事实的工程归约和被覆盖的正常输入，不代替真实模型语义验证。日志.tmp/n12/groups-green-71.txt，执行完立即释放槽，无遗留进程。

## 提交前门禁范围

本次8路径均为授权Python/目录单条元数据/专属测试与本文；不改旧3测试、IML01、RR-D02或其他owner生产。Python聚焦Ruff与git diff --check通过。前端src/package/tsconfig/eslint配置与8c9df71af相同（git diff名称输出为空），按root资源调度复用此前lint证据.tmp/iml01/lint-revision.txt：0 errors / 1214既有warnings，SHA256 478FF8AC56E06A91572145C3BCD79A34B586BAF0DAF256E840865B34584A12B6。不重跑全应用lint/type-check/test:unit；完整前端验证本作者未取得新结果，不宣称通过。本次将真实执行staged encoding与正常Husky，不绕过钩子、不安装或改D依赖。核心固定后独审独立执行；旧25测试的人工事实客户端适配须另提test-only提交并保留所有原医学输入与断言。

本次npm run check:encoding实际通过：staged 8 text files scanned。提交正常Husky结果随固定SHA回执披露。
