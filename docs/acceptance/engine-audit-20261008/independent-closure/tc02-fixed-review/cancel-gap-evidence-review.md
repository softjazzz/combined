# TC02 cancel_gap 精确证据卡失败：只读因果核对

基线 fac4ef67c0f68da1625f419ea5dddb47f38aa78b；候选为可变 WIP。仅070。未运行测试、模型、PG/env或编辑生产。

结论：**不是 SQLite 引入丢证据，也不能笼统称旧070无facts gap合同继承。** 旧公共投影门禁相同；TC02新的取消分支没有执行九项判定，却复用 helper 纳入九项检验引用，范围过宽。配对检验没有可定位文书ID，导致整组卡在保存前为空。root要求窄修消费引用；原精确卡失败日志和断言保留。随后候选同202全通过，固定commit复审仍待进行。

## 原失败保留

只读作者现有 green83.log/.xml：82 passed、1 failed。失败为 test_tc02_synthetic_sqlite_new_instance_preserves_status_scope_and_real_source_refs[cancel_gap] :507 找不到精确专用卡而 StopIteration。此前 native真实逐行ref断言、gap状态及SQLite回读status/reason/facts/findings/suggestion等值断言已通过。日志路径与SHA256见JSON。本审查未独立重跑，不能将作者输出当独立验收。

## 真实可达路径

- run_case 向 reduced Finalizer 提供 raw=None。其 :1166 条件为 raw非空或missing-facts检查；后者 :794–799 转到 surgery_gate mapping :38–40，仅025，所以070跳过executor-fact函数，继续公共文书投影。
- 我曾消息推断070无facts shortcut提前返回；该分支确存在fac4 :1049–1058/1172–1173和候选 :1065–1074/1188–1189，但**本实际路径不可达**，已向root/作者更正，不能据存在源码冒充执行证据。
- 070 allcancel路径跳过九项 evaluator，但旧 _070_document_refs :572–582 无条件选择九项labrefs。binding :267–285校验允许引用，reducer :127保留引用。
- 固定配对九项行只有 item_code/item_name/result/report_time，缺 document_id/test_id/labtest_id/report_id 等 projector :15–28 的任何身份字段。project_selected_document_evidence :335–351 对非登记选中行无ID整组return[]。fac4同文件相同行原样存在；整个projector当前未改。
- Finalizer接收空列表后不借来源级回退造卡；envelope :492–522只处理已有证据行，因此保存 evidence=[]；load_selected :739–757读取该Envelope，public DTO :362–390/:691同样只搬运已有行。不是数据库吞卡。

## source hash 与公开引用不同

evidence_material :44–68 按canonical原始行材料、source_key、occurrence构造逐行digest；:225–281检查同一snapshot、完整性、行数、source snapshot ref。决策携带snapshot_hash；public projector核对snapshot/material一致。

公开 src_24hex 是HMAC坐标，不是原始行内容digest。Envelope白名单 :410–423不保存native snapshot_hash/fact_refs，也不会由非空来源级引用反推精确卡。native准确refs、保存状态一致和公共精确卡是三项不同的检查，不能相互替代。

## 继承与新增分别记账

正常C：原7423完整九项合成输入也缺检验文书ID，旧整体坐标门禁产生无卡。这是既有fixture/坐标限制；保留C，不能称正常C精确卡回读通过，也不据此推断所有真实病例无卡。

新增cancel gap：九项判定未执行而选择九项引用，是新取消路径的消费范围未收口。它暴露旧projector全组门禁，但不能因此降低新的取消精确卡期望。allcancel等无确认实施路径应只选择实际消费的专用输血记录，正常C/已确认NC的真实检验引用策略保留，不改globalprojector。

已独立读取窄helper native SHA256 a987a4d81783505be3a64c2550c5110e2b63c3a16f161809c4bd5242cfbaec1b：:543–568新增include_pretransfusion_materials默认True；False在同snapshot专用行验证后按consumed过滤去重返回，不读取注册/MR/labs；:3211传bool(actual_transfusion_rows)，True维持旧确认事件路径。global projector/保存链未改。原cancel_card :507–511精确断言仍在，新10边界先冻结但未运行。

剩余静态接线：070 _decision仍默认把源级snapshot refs加回逐行refs，新10集合等值断言会揭示。应仅无actual_transfusion_rows、存在consumed_bloodtrans_rows且无输血来源错误时开启exact_document_refs。正常实际/MR路径保留源摘要+逐行引用；完整无来源NA同样保留旧摘要，因为binding :125–148仍要求NA非空refs。原82/1日志及失败断言不删除。状态/事实可分别讨论有限工程进展；完整证据卡闭环未验收，不称83全绿或TC02完全关闭。

所有精确路径、基线Git blob及WIP读SHA256见JSON。目录 F:/MedQC-worktrees/review-artifacts/tc02-review-prep/。

## 旧实际事件引用契约与新4保护的预期修订依据

fac4旧test_070_multi_transfusion_preserves_canonical_decision_facts_and_evidence :7646–7659构造四来源snapshot摘要，并要求fact_refs严格等于“source_snapshot_refs | selected_document_refs”。当前同断言在:7660，未被修改；本轮existing test diff仅7423加入受控fake performed client。正常实际/MR的来源摘要是审计合同，不可自动称未消费引用。

新冻结JSON明确expectedConfirmedMRRefs='original complete consumed sources unchanged'；但新4MR用例:591写成只等于12逐行refs，过度缩窄，违背冻结意图及旧契约。应附加修订记录，把这4项改为12逐行+独立从session.snapshot计算的4来源snapshot摘要；旧医学判定、旧多事件测试和原取消SQLite精确卡断言不变。新6无确认实施场景仍仅精确专用逐行refs。

root/作者报告同202第二次实际201pass/1fail，唯一为旧多事件引用合同。审查者未运行；已有green-exact-refs.log/.xml及source-hashes.json的绝对路径/SHA见JSON，已只读核对201/1原日志。我的先前“所有active均exact”建议在实际/MR部分过宽，已向root/作者撤回，以以上旧契约为准。后续已独立读取native72789f8b6953e55bdfe2e276fce052ec80428bd2ac742ffa3662b2432265e442 :3208，exact仅not actual&&consumed&&无来源错误。实际/MR和完整无来源NA保留旧源摘要。新test6ea5d17282d7ed2eceae95fc8b15a49767b1aae1e16dd9b1546fd3ea9265e36e :591–607另建expected_session，独立计算4snapshot+12逐行=16。v1仍fa5998da…，v2独立fdfe06cd…；旧多事件医学/引用断言、原取消精确卡断言均保留。global projector/store/public DTO未改。未发现新增静态阻断；等待同202重跑和固定commit验收，不称完成。

## 候选同202后续证据（作者运行，审查者只读）

已独立读green-compatible-refs.log/.xml/source-hashes.json：202passed，4.48秒；XML为202tests/0failures/0errors/0skipped。三项SQLite actual_c/cancel_gap/known_nc_unknown及旧070多事件canonical事实/证据用例均出现且无失败。manifest native72789f8b…、test6ea5d172…与本静态复核版本匹配。绝对路径/SHA256见JSON。

这是作者授权运行的候选工程证据，审查者未重跑。原82/1和201/1不抹除；修正预期依据/v1v2仍保留。未发现新增静态阻断，可进入固定commit核对；不是固定SHA独立验收完成，也不代表真实模型/临床语义验证。

