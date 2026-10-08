# 化疗下一最小闭环只读方案

根指定固定基线 aa7a98c7e，2026-10-08。只读原 N13 / TP-D02 / TP-D03 证据与现有发送链；本轮没有 Git 命令、测试/生产执行、模型/网络、PG、环境文件读取，也没有编辑源码/测试或新建工作树。只写本目录方案和 evidence-inheritance.json。aa7a 短SHA由根提供，本轮遵守禁Git要求没有独立解析其完整SHA；当前集成 native_tumor_pathology_execution.py 字节仍与最终59b3独审源相等，SHA256 3e2299951c92f9835da0787f8c24fc5ef49b51a39b350429d654351411890264。其他相关固定文件哈希在机器证据中。

**没有一个剩余观察能仅靠当前真实结构字段安全关闭。** N13八观察同属“目标给药动作—临床日期—医嘱归属”事实能力未达；后两项是该能力的计数表现，不是独立计数算术缺陷。TP-D02需要同一局部药物动作的剂量/实施语义，TP-D03还须医院医嘱状态码及已实施冲突政策。建议先只闭环原 foreign_drug_dose，明确局部目标药-剂量事实，保留原剂量比较算法和六NC/两归属差异，不一口气改日期、否定及医嘱筛选。此建议依赖新的受控事实抽取与调用预算批准，不是现成零调用结构修复。

## 八个原冻结差异的继承

权威原oracle：
F:/MedQC-worktrees/review-artifacts/chemo-n13/expectations-independent.json、
expectations-association-supplement.json、
expectations-e8-supplement.json。
既有固定结果 results-final-independent.json、review-final.md、verdict-final.json、hashes-final-independent.json 均在同目录。本轮核对这些冻结哈希没有变化，仅复制引用/观察作说明，不覆盖文件或改答案。

完整事件：奥沙利铂130mg、静滴、2026-04-26 09:00；partial事件默认同药150、缺单位、2026-04-27 09:00。病程记录时间2026-04-26 16:00；以下各有医嘱正逆序两个观察。

| 原case | 原业务预期 | 最终既有结果 | 真正缺口 |
| --- | --- | --- | --- |
| different_day_explicit_mismatch | NC、unresolved0 | DG、unresolved1 | “2026-04-26 使用奥沙利铂120mg 静滴”的日期没有被已验证地绑定到该给药动作，不能排除27日partial |
| different_day_relative_mismatch | NC、unresolved0 | DG、unresolved1 | “今日使用…”的今日须先绑定目标动作，再用可信记录日解释，不能凭全文今日或任意文书时间 |
| partial_missing_name_different_day_explicit | NC、unresolved0 | DG、unresolved1 | partial缺药名不能用药名排除；须以真实动作日期排除27日事件，不能用120/150剂量反推身份 |
| different_day_explicit_matched | DG、unresolved0 | DG、unresolved1 | 完整事件若被独立归属应核对成功，剩余partial仍缺字段；目前归属未证明，所以有额外unresolved1 |

前3×2是六NC未达；第4×2是两计数差异。既有交付对照e256与最终的六状态均DG，未交付e8曾判NC但同时存在复查日期假归属，不能当正常生产基线。两计数冻结0继续保留，不能因当前实现保守而把oracle改1，不能仅归零掩盖未证明归属。机器产物记录原fixture的文档性重建、正逆观察与既有e256/59b3结果；**没有在aa7a重跑**。

真实结构可支持的只是一侧医嘱 drug/name/dose/route/prescribed/order_status，以及病程文书ID、权威记录时间、原正文。source_evidence_reader.py:253–279 daily/senior投影没有给药对象、动作发生日期、病程order_id或执行记录列表；:369–395医嘱有order_id不等于另一侧有绑定。document_id、submit时间不能自动证明给药归属。native:1372–1394守卫只对明确不同药可排除竞争，已保护独立120vs130/真缺病程NC；同药或缺名竞争维持未知是当前能力描述，不改变明确日期业务标准。

## 与TP-D02/D03的关系

既有原证据：
F:/MedQC-worktrees/qc-integration-20261008/.tmp/engine-audit-20261008/tumor-pathology/expectations.json / results.json；
原审计文档 docs/acceptance/engine-audit-20261008/tumor-pathology.md。
旧结果代码基线7b894dc、文档6930540；本轮没有把旧结果冒称aa7a新运行。

| 已有case | 原预期/旧实际 | 能力维度与边界 |
| --- | --- | --- |
| foreign_drug_dose | NC/C | 目标实际120mg不得借后句昂丹司琼130mg；需要药物动作与局部剂量关系 |
| negated_course | NC/C | 执行医嘱与明确未给予冲突；否定须作用于目标药动作 |
| planned_course | DG/C | 只有拟给予不能证明实施，计划不能被抽成肯定给药 |
| conflicting_dose_in_one_record | **DG/C** | 实际120+计划130的原oracle就是DG；旧设计里实际120产生NC是待议想法，不能覆盖此冻结答案 |
| order_取消/撤销/作废 | NA/C | source有order_status，但生产代码值映射和取消后实际已给药优先关系未冻结；须状态码表与动作事实 |
| order_拟执行 | DG/C | 不把拟执行当已实施，仍保留原DG |
| relative_date_submit_only | DG/C | 另有时间来源口径风险，不能把submit当临床给药时间 |

N13日期、TP-D02剂量/极性共享“同一目标药动作的受控局部事实”方向，但不能把不同维度一起当一条小修；D03另有医院政策前提。纯JSON字段、现有剂量数字边界、事实计数本身均不提供缺失语义。句号/逗号是证据切片辅助，不能单凭连续句子或目标名出现次数证明药物动作、极性和日期关系。绝不追加复查/昨日/否定/药名排除清单，绝不用所有事件DG代替原NC标准。

## 现有共享抽取是否可复用

1. app/services/luxian_0609_fact_extraction.py:25–42 的 Luxian0609Fact 只有 fact_type/family/source_document_type/id/record_time/quote/confidence/extractor/trace。:354–365、:566–579的chemo_fact是化疗存在性/摘要，缺少每次药物、实施/计划/否定、剂量单位、临床日期与连续范围归属。不能从quote或trace自由字段假装已获得经校验动作合同。
2. 同文件:664–713 extract_luxian_0609_facts_with_llm 按family筛候选、拼文书、每family一次generate，输出facts列表；:774–815显式POC统一表，:860–885的prompt仍上述摘要schema，未注册可用化疗给药事实contract版本。该接口没有严格输入逐项bijection、quote回原材料校验或本次所需绑定。静态非测试调用检索没有发现formal026消费它；正式native:1947–2057直接source_for_rule→恶性门控→_typed_chemotherapy_comparison→emit_outcome(program)。
3. 真正请求级共享的是 malignancy_fact.py 的 MalignancyFactResolver，schema lx0609_malignancy_v1；它发送诊断/病理条目，返回explicit_malignant/explicit_nonmalignant/uncertain，不发送或返回给药局部事实。native:1988附近claim_usage计入这一次恶性解析；不能把既有恶性调用包装成“已有化疗抽取可零新增复用”。
4. extended_document/antimicrobial_action_extraction.py 的 lx0609_antimicrobial_actions_v1按抗菌目录/动作生成候选，严格返回item_id/antimicrobial/state/action_quote；state还将negated_or_planned合并，且没有dose/date字段。可参考“受控批量/连续原文/无重试”验证方式，不能扩大该字典或把抗菌响应当化疗事实，不改其owner/shared文件。FactV2/legacy adapter也要求明确mapping，不会从旧摘要自动创造药物动作关系。

结论：可复用请求内不可变Evidence Session、模型client、既有usage归集和原文回投机制；**不能原样复用任何现有事实响应完成本缺陷**。扩POC共享schema会影响surgery_anesthesia/tumor_pathology家族，第一闭环不建议这么做。

## 推荐一个最小闭环：foreign_drug_dose局部绑定

业务预期已清楚：原目标奥沙利铂130mg医嘱，正文明确本药120mg与另药130mg，必须NC；正常dose_130mg仍C。无需重定该业务答案，所欠是可靠局部事实抽取及验证证据。先限定剂量关系，不同步恢复N13日期排除、不过滤order_status、不改否定/计划混合oracle。

拟定专属contract版本 **lx0609_chemo_local_dose_facts_v1**，尚未注册/实现/调用。输入只用当前Evidence Session中daily_course原文和请求内匿名item_ref、结构化目标药名；不发医嘱期望剂量给模型，避免将“130mg正确答案”照抄为原文事实。返回逐item受控target_drug与动作断言，断言包含连续action_quote的原文坐标、实施/否定/计划/未知的独立状态，以及同一动作的raw dose_quote/坐标。不要返回质控状态、reason、医嘱ID关联、改写剂量、换算或临床建议。未知关系如实未知，不拼接其他药数值。

Python验证版本/严格键/输入完整不重不漏、药名身份、原文item、整数非bool范围、连续原文逐字相等、剂量坐标属于同一动作范围、日期/途径不由未定义字段偷渡。原有_chemotherapy_dose_matches只接已验证目标剂量片段，不改正负号/千分位/单位分母数字算法。范围与原文字面校验是必要条件，**不能证明模型归属判断总正确**；仍需原反例正常对照与真实抽取响应/人工gold验证，不能把替身生成的正确字段冒充模型已具备能力。模型无结果/协议错误/超限必须失败闭合，不能回原整篇any又虚报C；已有独立确定NC不得被额外失败吞掉，错误到公开结果的合同需根一并批准。

具体路径（都是未来候选，当前未写）：
- app/services/luxian_0609/native_tumor_pathology_execution.py，仅05-02-01及候选/typed比较接入与usage归集；
- 如根批准拆出局部contract：app/services/luxian_0609/chemotherapy_local_dose_facts.py，新小文件只持此schema/验证/一次发送，不建通用框架；
- 独占新tests/unit/test_luxian_0609_chemo_local_dose_binding.py，原case拷贝/引用及合同验证；现有test_luxian_0609_chemo_closure.py及所有冻结business_oracle不修改；
- 专属修复说明。原tumor_pathology_result_mapping8字段合同/Renderer/Finalizer/antimicrobial/shared legacy抽取均先不改。若发现消费局部事实需跨owner/公开合同变化，先报根扩大范围，不绕到后层重判。
上述路径均在F:/MedQC-worktrees/qc-integration-20261008/apps/medqc-web/backend/下，仅为root分配后实际owner路径模板，不在集成树直接编辑。

现有typed_document_refs:1744–1778通过_source_material_row回投原材料文书，可继承真实document证据锚点；当前公开摘录是文书级，并没有自动公开局部span的合同，不能称现有Finalizer已经证明字段级局部摘录。内部抽取证据应保留连续范围供复核，公开层仍带真实文书和准确mismatched事实；如必须公开精确局部范围，那是额外证据合同批准事项，不能在本轮偷加DTO字段。

## 调用预算必须单独批准

当前local administration/dose语义抽取0次；拟议在026已选中、恶性门控通过、有完整可比较事件和可读病程时，**0→最多1次/病例本次026请求**，一次batch涵盖全部候选，**不是每医嘱/每药物/每事件1次**。正常130mg等同样可能从0变1，不能用不可靠风险词筛选假称正常零增。无026、不适用/无完整候选/来源缺口则0次。请求内重复消费同一证据只归集一次，不新增跨病例缓存。

恶性门控原0或1次独立保留，因此该家族总预算是原有调用数+最多1；现合成C18.9正常原总0可能到1，需语义恶性判别病例原总1可能到2。不借共享恶性或POC调用名义隐藏增量，不重复发送诊断/出院整篇。仅026受新contract影响，不改其他tumor_pathology规则或抗菌规则调用。

建议批准时同时冻结candidate/input/output上限（拟8文书、8000原文字、12动作、2048 completion tokens）与超限失败语义；这些是设计值，未经运行/模型吞吐验证，不当已确定生产容量。不自动chunk成多调用，不长度重试。统计prompt/completion/total tokens和一次api_time，禁止把新调用预算藏在复用函数。此只读阶段真实新增调用为0；root批准预算后仍需真实响应/金标验证授权，受控替身只验证机械合同。

## 保护与下一轮退出条件

沿原样本，不新造医学答案：foreign_drug_dose原NC与dose_130mg原C为单闭环主对照；原negated/planned/conflicting三条保留NC/DG/DG，不能因v1实现混淆推翻答案。保留原N01/N07完整数字/原单位/L-OHP、D01空病程、N13单缺字段不假matched、不同药独立120vs130/真缺病程NC、同药同日partial歧义DG、四种复查日期正逆8项DG、document_time_only/submit_only、多日期、缺名/缺日以及八项开放oracle。冻结路径和case名称全部继承，不写新oracle。

下一轮先复制已有foreign_drug_dose及正常对照做正式native→binding/reducer→Finalizer固定红；根审contract/预算再做纯合同校验与原样本controlled替身绿，随后必须证明真实局部抽取响应与连续范围归属。保存验证换新SQLite实例回读，证明公开mismatched/原因/文书锚点/客户文案不是借另药130mg或继续保持，来源行实际回投。工程/替身通过与真实语义通过分别报告。八项开放oracle必须实际完整执行且继续报告失败，不用marker默认过滤/xfail改答求绿；第一闭环成功最多关闭TP-D02跨药剂量子项，不关闭N13/TP-D02全语义或TP-D03。

N13后续再扩绝对/相对临床日期事实时需新版本并独立批准；不能往v1 trace塞日期实现隐性恢复e8。order_status需医院状态码表、停止/取消时点及已实施优先口径另列，当前不自造。若root坚持新增语义调用预算仍0且无更可靠结构来源，则本次没有可诚实承诺的生产修复；可完成的下一步仅原反例正式链证据/合同设计，不用关键词或全gap冒充关闭。
