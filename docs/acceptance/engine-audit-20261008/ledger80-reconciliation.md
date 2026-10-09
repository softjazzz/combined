# 0609已实质审查80条：下一动作台账

日期：2026-10-09。固定集成版本：`7d92984a641ca6ca16882adb2688f9ad60e712a9`。

本次只核对已有证据和后续成果，不重审代码、不运行测试或模型。80条只统计一次，6条范围/目录核对项不混入分母。

| 主类 | 条数 | 占80条比例 |
| --- | ---: | ---: |
| A 确认缺陷待处理 | 9 | 11.25% |
| B 受改动影响需复验 | 15 | 18.75% |
| C 证据或合同待补 | 25 | 31.25% |
| D 可继承既有有限证据 | 31 | 38.75% |

主类按A→B→C→D确定下一动作，重叠事项保留在JSON的secondary_flags。A类是有既存未闭反例的处理项，本轮没有重新证明当前误判；D类仅继承有限证据，不代表整条合格。

真实语义、正式任务/API/页面/导出及客户环境等共通验收缺口另行保留，不据此把80条全部归C；有具体新增或规则专属缺口才逐条分类。发布范围沿旧冻结账继承，未重新执行当前范围判定。

## 逐条核对

| 规则（旧ID） | 质控点 | 主类 | 分类依据 | 下一动作 |
| --- | --- | --- | --- | --- |
| LX0609-01-01-01 / LX0609-001 | 入院记录：入院后24小时内是否完成 | D | 继承当前组24小时整点及+1秒的原生→归约→Finalizer零模型边界证据；未发现具体未闭反例或规则受影响重验事项。 | 保留该条已定位的有限证据与正常保护；没有新A/B/C专项任务，未来正式验收沿共通计划补证。 |
| LX0609-01-01-02 / LX0609-018 | 主诉能导出第一诊断：主诉书写不规范（1.只写症状不写诊断，2.>20字）或不能导出第一诊断。 | C | 本组仅有静态抽取/归约职责审查，未形成该规则当前替身或真实执行证据；明确缺诊断替代主诉例外及原子关系完整覆盖样本，不能由长度检查证明诊断方向正确。 | 固定例外/正常/不相关/未知的独立预期与完整来源，补该规则抽取及归约证据；正式链另列。 |
| LX0609-01-02-01 / LX0609-002 | 首次病程：入院后 8 小时内无首次病程记录 | D | 继承当前组8小时整点及+1秒的原生→归约→Finalizer零模型边界证据；旧历史SHA不移植为当前整规则通过。 | 保留该条已定位的有限证据与正常保护；没有新A/B/C专项任务，未来正式验收沿共通计划补证。 |
| LX0609-01-02-02 / LX0609-077 | 首次病程记录：鉴别诊断未与第一诊断相关联 | C | 本组只静态审查，未形成该规则当前替身或真实送模证据；跨系统合理关联、明显无关及多文书业务键冲突缺独立绑定样本。 | 补同一临床问题的跨系统正例、无关反例及业务键冲突资料，固定独立预期后验证抽取/引用对应。 |
| LX0609-02-01-01 / LX0609-005 | 上级医生查房记录：入院后 48 小时内无主治医师首次查房记录。 | D | 继承当前组48小时整点及+1秒的原生→归约→Finalizer证据；没有本条特定新缺陷/变更复验任务。 | 保留该条已定位的有限证据与正常保护；没有新A/B/C专项任务，未来正式验收沿共通计划补证。 |
| LX0609-02-01-02 / LX0609-006 | 上级医生查房记录：入院后 72小时内无最高级别（副主任医师或主任医师）首次查房记录。 | D | 继承当前组72小时整点及+1秒时限证据；含糊最高职称真实抽取仍是有限证据边界，未绑定新失败或批准修复。 | 保留该条已定位的有限证据与正常保护；没有新A/B/C专项任务，未来正式验收沿共通计划补证。 |
| LX0609-02-01-03 / LX0609-007 | 查房记录：病情稳定（未下病危、病重医嘱）患者3天内无查房病程记录 | D | 继承72小时精确边界与C-SECOND既有修复；多区间及缺时容量下界真实证据不足不变成新确认缺陷。 | 保留该条已定位的有限证据与正常保护；没有新A/B/C专项任务，未来正式验收沿共通计划补证。 |
| LX0609-02-01-04 / LX0609-008 | 查房记录：病重（下了病重医嘱）患者2天内无查房病程记录； | D | 继承完整空触发不适用和C-SEVERITY-SAME-TIME同刻停止/重开工程修复；旧版本变化声明已由后续修复记录限定，未发现具体当前受影响待办。 | 保留该条已定位的有限证据与正常保护；没有新A/B/C专项任务，未来正式验收沿共通计划补证。 |
| LX0609-02-01-05 / LX0609-009 | 查房记录：病危（下了病危医嘱）患者未每天记录查房病程，或病情变化时未记录病程 | D | 继承完整空触发不适用和同刻停止/重开工程修复；当前已有病情变化实现，不能沿旧计划称未实现；真实变化关联未验仍保留边界。 | 保留该条已定位的有限证据与正常保护；没有新A/B/C专项任务，未来正式验收沿共通计划补证。 |
| LX0609-03-01-01 / LX0609-020 | 会诊记录：有会诊记录单无请会诊执行记录 | C | 正式暂停：现有会诊物理文书属于执行记录，缺独立会诊记录单；旧真实重放不能证明当前正式启用。 | 客户确认独立意见文书与执行记录的源合同，接入验收后再决定解除暂停。 |
| LX0609-03-01-02 / LX0609-021 | 会诊记录：会诊申请单会诊目的不明确 | C | 正式暂停：未同步会诊申请单，没有会诊目的的权威来源。 | 补会诊申请单供数与目的字段合同；不得由执行记录推测申请目的。 |
| LX0609-03-01-03 / LX0609-022 | 会诊记录：会诊记录单会诊意见不明确（如出现必要时行**检查或**药物治疗） | C | 正式暂停：独立会诊意见源缺失，不能把旧词语判定或旧模型重放移作当前验收。 | 先确认意见来源和清晰性口径，完成来源验收后再排专属验证。 |
| LX0609-03-01-04 / LX0609-023 | 会诊记录：会诊建议未落实或执行记录不具体 | B | 当前口径已包括未找到执行证据，旧54/54采用无痕迹不适用，不能跨口径继承；逐建议匹配语义仍需复验。 | 按当前合同冻结逐建议预期，复验条件/未来建议、数量、关联和低置信安全降级。 |
| LX0609-03-02-01 / LX0609-050 | 疑难病历讨论记录：诊断不明确入院后7天未书写疑难病历讨论 | A | CT-01否定/未来条件误触发有明确合成反例，最新关闭清单仍排队；本次文档整理未重新运行。CT-02/03/04后续已关闭，不能继续并称四项当前缺陷。 | 仅围绕CT-01根因制定可泛化方案并另行授权验证；讨论成熟时间/问题关联的CT-R02另补业务合同。 |
| LX0609-04-01-01 / LX0609-029 | 术前小结：无术前小结（有手术医嘱） | C | 029原正常回退在当前两例控制中未重现，故不列A；多事件逐医嘱覆盖、模糊名称负向覆盖与注入关联键的真实供数证明仍缺。 | 补多事件负向预期及业务键来源证明；保留原正常控制，不把2/2扩大为整条验收。 |
| LX0609-04-01-02 / LX0609-039 | 术前讨论记录：除以紧急抢救生命为目的的急诊手术外，其他住院患者手术无术前讨论或术者未参加。 | C | 已有确定性冻结与空讨论/来源失败保护；报告明确缺参与者语义、紧急抢救豁免的当前独立金标。 | 先冻结术者参与与紧急抢救例外的独立预期及来源，再验证专属语义场景。 |
| LX0609-04-01-03 / LX0609-040 | 术前多学科讨论记录：四级手术术前讨论未多学科讨论。 | B | 来源查询失败分支公开facts与旧MDT冻结不同；最新SURGERY-FREEZE仅关闭已识别夹具/目录漂移，剩余差异仍开。没有证据证明临床状态误判。 | 明确查询失败公开事实合同，针对原冻结差异复验，不直接反改医学预期。 |
| LX0609-04-01-04 / LX0609-078 | 术前小结：内容不完整 | C | 有限真实验证及工程保护可继承，但C04/C12诊断充分性/术式归属仍有医学争议；最新清单未作改代码决定。 | 由医学负责人明确争议项口径及独立预期，再决定是否需要实现修改。 |
| LX0609-04-01-05 / LX0609-079 | 术前讨论记录：内容不完整 | C | 有限术前讨论验证无新增确认缺陷；医学充分性与术式归属争议仍未裁定，状态一致不能替代充分性判断。 | 先对齐争议医学合同，保留逐文书证据与已有有限验证，不重复已完成专项。 |
| LX0609-04-02-01 / LX0609-003 | 手术记录：手术后24小时内是否完成 | D | 逐台手术记录覆盖已修复，组报告104 gate及20逐台保护可继承；未发现本条特定新缺陷或未关闭输出漂移。 | 继承限定工程证据；正式临床验收按统一缺口另排。 |
| LX0609-04-02-02 / LX0609-030 | 手术记录：无手术记录（有手术医嘱） | B | 030原正常回退当前控制未重现；新增触发facts及presence冻结差异仍未全部关闭，故按B列定向复验。 | 先核剩余presence公开输出合同再复验；另补多事件逐医嘱负向覆盖与关联键供数证明。 |
| LX0609-04-02-03 / LX0609-024 | 手术记录：恶性肿瘤手术记录未书写淋巴结清扫情况 | C | 受控抽取后的程序判定和否定/计划保护可继承；报告专门指出恶性适用性及淋巴结处理语义缺独立金标，通用gate回归不能补足。 | 补恶性/非恶性、处理/未处理原因的独立医学预期与多事件对应，再安排验证。 |
| LX0609-04-02-04 / LX0609-025 | 手术记录：手术记录中未记录植入物名称、种类、规格/型号、材质及数量等信息 | C | 主表仍pending_definition，原因implant_five_field_real_gold_pending；五字段合同已冻结但多台、缺文书、冲突金标未补。 | 补五字段真实独立预期并确认正式启用条件；shadow或直接执行器成功不能解除暂停。 |
| LX0609-04-02-05 / LX0609-031 | 手术记录：手术记录非手术者签字（质控术者及签名医生） | D | 术者/签名资格不取提交人且已补逐台覆盖，组报告相关保护通过；无本条新增确认缺陷。 | 继承身份与逐台签名保护的限定证据；后续按统一验收边界补正式链。 |
| LX0609-04-02-06 / LX0609-060 | 死亡记录：死亡患者无死亡记录 | D | 后续060专属11项当前源码绑定回放全通过，无确认阻断；当前绑定缺口已补，可继承此限定证据。原历史SHA不可追溯和六例无死亡触发仅限制旧证据外推。 | 继承当前11项工程保护；历史SHA不可恢复不作为继续补审任务，死亡阳性临床与正式链按统一验收缺口另排。 |
| LX0609-04-02-07 / LX0609-069 | 会诊记录：会诊记录单未在会诊申请24小时内完成 | D | 空申请时间已按authoritative_time_missing降级，关联/时间文案8项保护可继承；未见新的时限误判反例。 | 继承申请—完成时间与关联的限定证据；真实多申请和正式链后续按统一范围补。 |
| LX0609-04-02-08 / LX0609-076 | 死亡记录：死亡时间缺失 | D | 死亡时间空正文/source_empty及completeness解释已有工程证据；没有本条未关闭新缺陷，不能用完成时间替代死亡时间。 | 继承限定死亡时间证据；死亡阳性源覆盖与正式链仍按统一缺口验收。 |
| LX0609-04-03-01 / LX0609-032 | 手术安全核查表：无手术安全核查表（有手术记录） | B | 032无触发文案、关联失败公开坐标与旧presence冻结存在剩余差异；状态未因此翻转，最新清单未关闭这些差异。 | 冻结当前公开facts/文案/坐标合同后定向复验原presence差异。 |
| LX0609-04-04-01 / LX0609-036 | 麻醉访视：无麻醉术前/麻醉术后访视记录（局麻除外）； | C | 客户源不提供麻醉术前/术后访视，正式pending_definition未解除；直接执行器测试不是正式启用证据。 | 由客户重新确认访视供数范围，补来源覆盖后再审批解除暂停。 |
| LX0609-04-04-02 / LX0609-037 | 麻醉访视：麻醉访视（术前和术后）记录填写不规范（局麻除外）； | B | N12 core与carrier已集成，旧空标签工程问题已关闭；新增受控语义及sN载体仅有有限合成证据，真实模型语义仍待验。 | 在冻结来源/预期后验证自然访视正文、事件关联及模型语义；保留375工程与有限marker证据边界。 |
| LX0609-04-04-03 / LX0609-038 | 麻醉记录单：无麻醉记录单（局麻除外）； | D | 存在性历史独立预期及计划/未实施、局麻、来源失败保护可继承；未见特定新增缺陷或输出漂移。 | 继承限定麻醉记录存在性证据，不扩大为多麻醉真实全量验收。 |
| LX0609-04-05-01 / LX0609-064 | 术后连续三天查房记录：术后三天无连续病程记录或术者查房记录 | D | 逐台第1–3日病程/术者查房及精确引用有既有冻结，组报告相关mapping通过；N10新正文语义不覆盖本规则。 | 继承现有连续病程限定证据；不要将065/067新测试当064语义验收。 |
| LX0609-04-05-02 / LX0609-065 | 术后三天内上级医师查房记录：无术后三天内上级医师查看病人记录 | B | N10受控正文事实与共享出口支持已集成，85事实/133旧回归/8合成SQLite通过；新增LLM语义尚未真实独立验收。 | 验证自然正文语义与独立预期，补专用TRUNCATED快照；时间/事件仍保持权威程序合同。 |
| LX0609-04-05-03 / LX0609-066 | 术后首次病程记录：无术后首次病程记录 | D | 每台首次术后病程及缺失事件精确引用有既有冻结，相关mapping通过；无本条特定新缺陷。 | 继承限定首次病程关联证据；真实同日多台可靠性后续按统一缺口验收。 |
| LX0609-05-01-02 / LX0609-054 | 抗菌药物：用药调整无充分理由 | C | 42db89910已补指定合成来源绑定，13组中本条6例3符合预期；计划/否定无client的technical_error是模型输入限制，未证真实误判。药品目录范围TP-Q03及理由分支阅读绑定仍有具体缺件，不将旧5差异统称缺陷。 | 补院方抗菌目录/批准映射及原054理由分支阅读证据；独立冻结计划/否定动作预期，已有合成正常/缺理由证据继承。 |
| LX0609-05-01-03 / LX0609-055 | 抗菌药物：48至72小时内无效果评价 | A | TP-D05原明确药物效果评价“体温下降”在48/60/72小时被判缺评价，闭合账仍queued_shared_module；未找到后续关闭。当前7d92984a6未新重现，不能按旧词覆盖自动宣布修复。 | 沿原明确评价及47/73小时正常反向保护收口，固定通用效果事实与原医学预期，不扩关键词凑绿。 |
| LX0609-05-01-05 / LX0609-057 | 抗菌药物：经验用药未说明理由 | C | 42db当前指定7合成5符合，另两差异分别是无样可采原因充分性与会诊同文来源范围，保持原TP-Q05/Q04争议；不是确认漏写。057分支历史阅读定位亦待绑定。 | 确认会诊来源参与触发范围及“无痰标本可采”充分性；补原057分支/来源定位，保留原7输入与预期。 |
| LX0609-05-01-06 / LX0609-058 | 抗菌药物：特殊级用药缺少专家查房或会诊 | C | TP-D04已由35dd/2f402集成，原18+补17独审35及SQLite3可继承，不能继续标跨药支持确认缺陷；仍具体缺院方特殊级目录、专家授权与未知药名自然资料签认。 | 取得院方特殊级目录/专家身份授权依据和未知药名签认，沿原跨药/时间归属/半覆盖保护继承，不重修已闭子项。 |
| LX0609-05-02-01 / LX0609-026 | 恶性肿瘤化学治疗记录：病程中化学治疗记录情况（药物名称、剂量、使用方法、时间）与医嘱不一致 | A | TP-D01及N13不假matched/错误日期排除子项已集成；TP-D02跨药剂量及否定实施、TP-D03取消状态仍开放。隔离候选67/65/2保留negated原NC实际DG、widened坏关系原NC实际C，旧115保护未恢复验证；此轮未重现当前集成。 | 按可泛化目标药物-动作-剂量关系解决，保留两个坏fake原oracle/N13六NC两计数/旧保护；三轮失败停报，整体候选未闭不集成。 |
| LX0609-06-01-01 | CT/MRI检查记录：医嘱与病程一致性 | B | IML01 US/培养角色有限修复已集成，新身份字段影响实际输入需复验。本条原联合case没有orders/course，不能继承06-01-03的C观察或把合同pending变本条已确认误判。 | 用本条适用的医嘱-检查-病程完整输入复验新身份字段、合并医嘱与单次抽取；保留CT/MRI剩余合同到相应消费规则，不臆造当前A。 |
| LX0609-06-01-02 / LX0609-010 | CT/MRI 检查记录：CT/MRI检查前有无病程记录（无行CT/MRI检查原因） | C | 检查前原因被硬裁前48小时；原业务基线仅检查前原因，未找到48小时院方确认依据。IML-D02最新为业务口径review，不能以旧测试固定行为当确认缺陷。 | 确认有效原因有无48小时有效期及评价范围，保留已有R-02身份投影保护与原检查前正常例。 |
| LX0609-06-01-03 | CT/MRI检查记录：报告单完整性 | C | 已集成US角色净修复保留；CT/MRI同键联合事件gap-vs-C及取消主记录配有效报告的最终/历史语义仍未定，IML-D01明确暂不计确认P1。归本条具体合同待补，不能沿原IML01五条共享标签直接A。 | 裁定同键联合CT/MRI与取消状态/正式报告权威合同，绑定原case与正常保护；保持acceptance_only不擅自启用。 |
| LX0609-06-01-04 / LX0609-011 | CT/MRI 检查记录：CT/MRI影像报告结果出具后24小时内在病程中未记录 | B | 报告后24小时结果记录原C09/C10输入在移除DR后已变，CT-INPUT-CHANGE仍需当前输入真实复验。原C12/C04逐字相同历史响应可有限回放，不能代替新模型；本条阅读摘录绑定待补为次级C。 | 固定当前完整送模文书目录和本条独立人工预期，核同次结果/记录与提交时间及阳性分析；补旧分支摘录，不从零重审。 |
| LX0609-06-01-05 / LX0609-012 | CT/MRI 检查记录：CT/MRI影像报告结果出具后24小时内阳性结果未进行分析 | B | 阳性结果24小时分析原C09/C10输入在移除DR后已变，CT-INPUT-CHANGE仍需当前输入真实复验。原C12/C04逐字相同历史响应可有限回放，不能代替新模型；本条阅读摘录绑定待补为次级C。 | 固定当前完整送模文书目录和本条独立人工预期，核同次结果/记录与提交时间及阳性分析；补旧分支摘录，不从零重审。 |
| LX0609-06-02-01 | 病理检查记录：报告单完整性 | C | 历史阶段A P01–P03真实Session/确定性发布技术证据与当前ID命名空间可继承；本条病理完整性阅读函数/行号/hash仍未绑定，不在42db七条补证范围。没有具体新未闭误判或受改动复验ID。 | 绑定既有病理完整性源码阅读摘录和执行身份，复用P01–P03限定证据；保持acceptance_only，不把缺阅读定位说成从未审。 |
| LX0609-06-02-02 / LX0609-019 | 病理检查：取材情况未在病程记录/手术记录中进行记录。 | B | 取材记录曾有历史审查；跨事件同键、标本/诊断关联与报告后时间门禁已变化，PATH-INPUT-CHANGE最新仍复验准备。旧响应不能证明当前关联输入正确。 | 以完整适用多事件报告/标本与对应取材记录冻结输入及独立预期，复验同命名空间、唯一关联/未决和报告时序，保留历史限定成果。 |
| LX0609-06-02-03 / LX0609-013 | 病理检查：病理检查结果在手术记录、病程中未记录 | B | 病理结果记录曾有历史审查；跨事件同键、标本/诊断关联与报告后时间门禁已变化，PATH-INPUT-CHANGE最新仍复验准备。旧响应不能证明当前关联输入正确。 | 以完整适用多事件报告/标本与对应病理结果记录冻结输入及独立预期，复验同命名空间、唯一关联/未决和报告时序，保留历史限定成果。 |
| LX0609-06-03-02 | 微生物培养检查记录：报告单完整性 | B | IML01培养明细角色修复已集成；exam-only CT/MRI联合case不适用于本条，不能据其未闭合同认定本条A。仍明确需新身份字段在培养多行真实输入/交付上的影响复验。 | 准备培养主/明细同test_id与非目标常规报告的完整实际输入，复验新字段与角色归属；继续acceptance_only，程序规则不制造模型调用。 |
| LX0609-06-03-03 / LX0609-014 | 细菌培养记录：细菌培养结果在病程中未记录（报告出具后24小时内） | C | 42db已补当前合成版本绑定，旧015身份literal由5f34698a2仅测试适配，root45/45；不能继续算失败。该条历史自然培养材料/真实语义批次执行SHA与case manifest未齐，专属阅读摘录仍待绑定；无具体新A或输入改动B。 | 补历史真实执行SHA/完整输入manifest与本条源阅读锚点，保留45节点分层（10直接+33共享+解析器/提示）；不以合成回放倒填历史真实运行。 |
| LX0609-06-03-04 / LX0609-015 | 细菌培养结果无分析：细菌培养结果有阳性菌，在病程记录中无分析（报告出具后24小时内）。 | C | 42db已补当前合成版本绑定，旧015身份literal由5f34698a2仅测试适配，root45/45；不能继续算失败。该条历史自然培养材料/真实语义批次执行SHA与case manifest未齐，专属阅读摘录仍待绑定；无具体新A或输入改动B。 | 补历史真实执行SHA/完整输入manifest与本条源阅读锚点，保留45节点分层（10直接+33共享+解析器/提示）；不以合成回放倒填历史真实运行。 |
| LX0609-06-04-01 / LX0609-052 | 危急值记录：6小时内未书写危急值处置记录 | D | IML02记录时间冒充报告时间与别名冲突子项已a8ad74e69集成；原缺时间/冲突及6小时处置窗口、SQLite限定工程证据可继承。最新账无本条具体未闭A/B/C新增待办，共通客户链缺口不把整条改C。 | 沿原报告时间权威/等价时区、多事件及6小时处置窗口保护继承，最终发布批次按共享验收计划核相关链路，不重修IML02。 |
| LX0609-06-04-02 / LX0609-053 | 危急值记录：危急值报告后无处置记录 | D | IML02记录时间冒充报告时间与别名冲突子项已a8ad74e69集成；原缺时间/冲突及处置存在性/先后时间、SQLite限定工程证据可继承。最新账无本条具体未闭A/B/C新增待办，共通客户链缺口不把整条改C。 | 沿原报告时间权威/等价时区、多事件及处置存在性/先后时间保护继承，最终发布批次按共享验收计划核相关链路，不重修IML02。 |
| LX0609-07-01-01 / LX0609-043 | 输血前辅助检查：输血前常规检查不完整； | A | TC01原TF_PLAN/TF_REFUSED/TF_POSTPONED把未实施判gate=present；准备报告明确正式executor逐条043共用_performed_source_state，门控后evaluate_pretransfusion_nine_items消费九项检查。这是明确影响本条的共同实施事实缺陷，不是五条各六例终态验证；当前集成未新重现。候选425/3未集成不计本条关闭。 | 沿原六冻结实施gate与本条九项检查正常保护固定版本复验/独审候选；保留计划/拒绝/暂缓原DG，不按词表或病例特判。 |
| LX0609-07-01-02 / LX0609-044 | 输血前评估：无输血前评估记录或输血前评估记录不完整； | A | TC01原TF_PLAN/TF_REFUSED/TF_POSTPONED把未实施判gate=present；准备报告明确正式executor逐条044共用_performed_source_state，门控后_programmatic_044_status消费评估存在/完整性。这是明确影响本条的共同实施事实缺陷，不是五条各六例终态验证；当前集成未新重现。候选425/3未集成不计本条关闭。 | 沿原六冻结实施gate与本条评估存在/完整性正常保护固定版本复验/独审候选；保留计划/拒绝/暂缓原DG，不按词表或病例特判。TR044原三node/rows/expected manifest缺件单列，勿造新例冒充。 |
| LX0609-07-01-03 / LX0609-070 | 输血前评估：未做输血前相关九项检查 | B | TC02原取消记录record_time当实施事实已由011d26b86+35909964a有限工程闭环，root289/289可继承；当前缺实际模型正确提取performed/plan/cancel及多时钟/多事件语义，不再把原取消反例归A。 | 固定已集成070版本和自然实际/计划/取消/未知及多时钟输入，先核可信身份/硬预算后真实语义复验；保留正常C缺labID精确卡边界，不扩成043–047候选通过。 |
| LX0609-07-02-01 / LX0609-045 | 输血记录：无输血病程记录； | A | TC01原TF_PLAN/TF_REFUSED/TF_POSTPONED把未实施判gate=present；准备报告明确正式executor逐条045共用_performed_source_state，门控后_programmatic_045_status消费病程记录存在。这是明确影响本条的共同实施事实缺陷，不是五条各六例终态验证；当前集成未新重现。候选425/3未集成不计本条关闭。 | 沿原六冻结实施gate与本条病程记录存在正常保护固定版本复验/独审候选；保留计划/拒绝/暂缓原DG，不按词表或病例特判。 |
| LX0609-07-02-02 / LX0609-046 | 输血记录：输血病程记录不完整或不规范； | A | TC01原TF_PLAN/TF_REFUSED/TF_POSTPONED把未实施判gate=present；准备报告明确正式executor逐条046共用_performed_source_state，门控后_programmatic_046_status消费逐份目的/指征及字段。这是明确影响本条的共同实施事实缺陷，不是五条各六例终态验证；当前集成未新重现。TF_PLAN_COMPLETE_FIELDS另有046纯函数NC误入分支证据。候选425/3未集成不计本条关闭。 | 沿原六冻结实施gate与本条逐份目的/指征及字段正常保护固定版本复验/独审候选；保留计划/拒绝/暂缓原DG，不按词表或病例特判。 |
| LX0609-07-03-01 / LX0609-047 | 输血后评价：无输血后评价 | A | TC01原TF_PLAN/TF_REFUSED/TF_POSTPONED把未实施判gate=present；准备报告明确正式executor逐条047共用_performed_source_state，门控后_programmatic_047_assessment消费结束后评价窗口。这是明确影响本条的共同实施事实缺陷，不是五条各六例终态验证；当前集成未新重现。候选425/3未集成不计本条关闭。 | 沿原六冻结实施gate与本条结束后评价窗口正常保护固定版本复验/独审候选；保留计划/拒绝/暂缓原DG，不按词表或病例特判。 |
| LX0609-07-04-01 / LX0609-048 | 输血记录：有术中输血，但手术记录、麻醉记录、术后首次病程记录中输血相关内容记录不一致。 | A | TC03原048_NEGATED_INTRAOPERATIVE三份均明确未输血，仅备血2U/4U/2U仍实际NC且confirmed=true；closure仍queued。b4a98783e配对/单位合同已关，TR048-REAL样本不足属次级B/C，不覆盖本明确未闭反例。当前集成未新重现。 | 沿原术中否定/备血反例与048_MATCHED/TIME_CONFLICT固定实际术中事件事实，不重开b4配对；另补真实实际触发及三类完整文书再复验。 |
| LX0609-08-01-01 / LX0609-061 | 出院记录：出院记录未在出院后24小时内完成 | D | 后续061原7项时限预期在当前责任源码绑定下全通过，当前定位已补；没有必须补验的特定原反例。旧执行manifest不可追溯仅限制历史运行证明。 | 继承当前7项纯时限证据；保留旧manifest限制，不为恢复历史运行追加审查。 |
| LX0609-08-01-02 / LX0609-062 | 出院记录：出院带药不详细 | C | 062现有非空字段保护不涵盖错药/错剂量一致性；最新结论要求权威出院药来源及错误定义，没有实跑错药金标，不能列确认临床误判。 | 明确带药权威表、版本/停用/关联、药品编码和剂量单位及错误定义，再冻结独立错药预期。 |
| LX0609-08-01-03 / LX0609-063 | 出院记录：出院诊断或死亡诊断错填漏填顺序错误 | D | DD-F01死亡无出院记录漏执行已集成b13043c3d，独审39/root73通过；旧漏执行反例不再当当前缺陷。 | 继承修复后的有限诊断证据与原反例保护，正式验收按统一缺口补。 |
| LX0609-08-01-04 / LX0609-027 | 出院记录：出院记录（恶性肿瘤患者）中是否有出院后肿瘤相关治疗的出院治疗计划 | C | 旧基线治疗或随访与当前客户主表肿瘤治疗口径不一致，DD-F05仍为业务依据复核；未决定改实现。 | 对齐口径文档并取得医学确认，保持当前客户已确认治疗合同，另补完整恶性适用链预期。 |
| LX0609-08-02-01 / LX0609-067 | 出院前病程记录：无出院前一天或当天的病程记录 | B | N10正文present/absent/unknown工程已集成，旧标题/签名问题保护已补；新增LLM语义及自然正文判断仍待真实独立验收。 | 验证自然出院前病程语义并补专用TRUNCATED快照；保留原字面无正文反例与单独夹具修正记录。 |
| LX0609-08-02-02 / LX0609-068 | 出院前病程记录：无上级医师同意出院的意见 | D | 后续068原4项native→Binding→Canonical源码绑定回放通过，当前定位已补；R2后续133旧保护还包含缺时间及native选中引用保护。旧manifest及初始化替身仅限制证据层，不构成当前必补原反例。 | 继承当前4项及R2后续相关旧保护；保留原历史manifest和初始化替身限制，不无限追补历史日志。 |
| LX0609-09-01-01 / LX0609-004 | 抢救记录：抢救结束后6小时内是否完成 | D | 继承同份抢救记录结束/完成时间关联及6小时含秒边界保护；缺真实多事件金标是证据限度，没有本条明确新反例。 | 保留该条已定位的有限证据与正常保护；没有新A/B/C专项任务，未来正式验收沿共通计划补证。 |
| LX0609-09-01-02 | 抢救记录：内容完整性 | C | 冻结范围为acceptance_only、撤出默认；六字段工程保护与R01回放可有限继承，内容验收及独立临床预期未完成。报告提否定词假阴性但未绑定明确未闭反例，本轮不升级为A。 | 在独立内容验收授权下补六字段正/缺/未知临床预期和否定句边界的精确反例；未验收前保持显式范围。 |
| LX0609-09-02-01 / LX0609-051 | 死亡病历讨论记录：患者死亡后7天未书写死亡病历讨论记录 | C | RR-D02未知完成时间被过滤的缺陷已集成闭项；剩余RR-D01是评价终点与材料可见性合同争议，旧离线行为不直接等于已批准缺陷。 | 先批准评价终点是否兼作文书可见截止的合同，保留未来讨论原反例；不得自行改变原医学预期。 |
| LX0609-10-01-01 / LX0609-071 | 交接班记录：经治医师变更时无交接班记录或未按时完成 | D | 继承变更事件/24小时窗口与匹配引用保护及C-GAP-CONTRACT限定成果；历史专表空不算阳性适用通过，也未构成确认缺陷。 | 保留该条已定位的有限证据与正常保护；没有新A/B/C专项任务，未来正式验收沿共通计划补证。 |
| LX0609-10-02-01 / LX0609-072 | 转科记录：转科病人24小时内未完成转入、转出记录 | D | 继承正式转科医嘱触发和双向24小时保护；旧计划暂不转科T01误报已消退，不列作当前A。 | 保留该条已定位的有限证据与正常保护；没有新A/B/C专项任务，未来正式验收沿共通计划补证。 |
| LX0609-10-02-02 / LX0609-073 | 转科记录：有转科医嘱无转入、转出记录 | D | 继承转科医嘱双向存在性保护；T02计划暂不转科旧反例已消退；真实多事件资料不足不等于当前缺陷。 | 保留该条已定位的有限证据与正常保护；没有新A/B/C专项任务，未来正式验收沿共通计划补证。 |
| LX0609-10-03-01 / LX0609-075 | 有创操作记录：有创操作医嘱无有创操作记录 | C | 冻结范围为pending_definition，有创操作目录未冻结；正式分区not_executed/空证据不算医学通过，低层075测试不能证明正式启用。 | 先冻结有创操作目录和触发/匹配业务合同，再另行授权启用；保持暂停出口。 |
| LX0609-11-01-01 / LX0609-033 | 手术知情同意书：无手术知情同意书(有手术记录） | D | 本轮仅继承customer_excluded范围约束证据；旧组存在性/字段保护是历史有限信息，无具体未定合同或批准重新启用任务，不支持当前医学合格结论。 | 维持冻结排除范围，不作为医学合格交付；重新启用须另行授权和专项验收。 |
| LX0609-11-02-01 / LX0609-034 | 麻醉知情同意书：无麻醉知情同意书（有麻醉记录） | D | 本轮仅继承customer_excluded范围约束证据；旧组存在性/字段保护是历史有限信息，无具体未定合同或批准重新启用任务，不支持当前医学合格结论。 | 维持冻结排除范围，不作为医学合格交付；重新启用须另行授权和专项验收。 |
| LX0609-11-02-02 / LX0609-035 | 麻醉知情同意书：麻醉知情同意书填写不规范（无患者或医生签名、签名时间未精确到分钟） | D | 本轮仅继承customer_excluded范围约束证据；旧组存在性/字段保护是历史有限信息，无具体未定合同或批准重新启用任务，不支持当前医学合格结论。 | 维持冻结排除范围，不作为医学合格交付；重新启用须另行授权和专项验收。 |
| LX0609-11-03-01 / LX0609-041 | 输血知情同意书：无输血知情同意书； | D | 本轮仅继承customer_excluded范围约束证据；旧组存在性/字段保护是历史有限信息，无具体未定合同或批准重新启用任务，不支持当前医学合格结论。 | 维持冻结排除范围，不作为医学合格交付；重新启用须另行授权和专项验收。 |
| LX0609-11-03-02 / LX0609-042 | 输血知情同意书：输血知情同意书填写或签名不完整； | D | 本轮仅继承customer_excluded范围约束证据；旧组存在性/字段保护是历史有限信息，无具体未定合同或批准重新启用任务，不支持当前医学合格结论。 | 维持冻结排除范围，不作为医学合格交付；重新启用须另行授权和专项验收。 |
| LX0609-12-01-01 / LX0609-016 | 不合理复制病历：不合理复制病历内容是指首次病程记录病例特点与入院记录、现病史完全相同 | D | 继承完全同文、包含关系非完全复制、缺段资料不足零模型保护；无具体未闭缺陷或受影响复验指向。 | 保留该条已定位的有限证据与正常保护；没有新A/B/C专项任务，未来正式验收沿共通计划补证。 |
| LX0609-12-01-02 / LX0609-017 | 不合理复制病历：2次以上病程记录完全相同（相似度大于70%） | D | 继承相似候选与单次模板复核保护及C-GAP-CONTRACT有限修复；70%采用现行业务≥70%基线，旧标题不能当未闭反例。 | 保留该条已定位的有限证据与正常保护；没有新A/B/C专项任务，未来正式验收沿共通计划补证。 |
| LX0609-12-02-01 / LX0609-074 | 病程记录：修正或补充诊断时未记录理由及诊断依据 | B | RR-M01权限/计量漂移已集成闭项；PROMPT-074仍明确要求当前Prompt真实输入输出复验，旧响应及合法替身不足以证明变更后语义。 | 沿PROMPT-074固定变更后完整输入/响应与理由、依据同文书独立预期，复验正常保护及未知/失败分支。 |

## 每条的证据索引与附加待办

### LX0609-01-01-01

- 范围说明：{'authority': '冻结T0台账及1958ae3bb历史overlay范围继承；本轮未实时重查注册器/执行范围', 'phase_status': 'phase_1_target', 'release_scope': 'default', 'customer_excluded': False, 'default_executes': True, 'existing_evidence_limits': ['真实当前版本原始字段/完成时间含义与正式保存/页面同源未验']}
- 问题ID：无规则专属未闭问题
- 附加待办：既有证据有限，不是整规则/真实医学通过；共通正式链缺口另列；本轮未执行测试/模型/注册器
- 证据：[admission-history.json](<F:/MedQC-worktrees/qc-integration-20261008/docs/acceptance/engine-audit-20261008/admission-history.json>) /rules/0；[overlay.json](<F:/MedQC-worktrees/qc-integration-20261008/docs/acceptance/engine-audit-20261008/next-batch/coverage-progress-current/overlay.json>) /rules/0

### LX0609-01-01-02

- 范围说明：{'authority': '冻结T0台账及1958ae3bb历史overlay范围继承；本轮未实时重查注册器/执行范围', 'phase_status': 'phase_1_target', 'release_scope': 'default', 'customer_excluded': False, 'default_executes': True, 'existing_evidence_limits': ['诊断替代主诉的规范例外与原子事实完整覆盖尚须真实模型和临床签认；当前全链保存回读未验']}
- 问题ID：无规则专属未闭问题
- 附加待办：既有证据有限，不是整规则/真实医学通过；共通正式链缺口另列；本轮未执行测试/模型/注册器
- 证据：[admission-history.json](<F:/MedQC-worktrees/qc-integration-20261008/docs/acceptance/engine-audit-20261008/admission-history.json>) /rules/7；[overlay.json](<F:/MedQC-worktrees/qc-integration-20261008/docs/acceptance/engine-audit-20261008/next-batch/coverage-progress-current/overlay.json>) /rules/17

### LX0609-01-02-01

- 范围说明：{'authority': '冻结T0台账及1958ae3bb历史overlay范围继承；本轮未实时重查注册器/执行范围', 'phase_status': 'phase_1_target', 'release_scope': 'default', 'customer_excluded': False, 'default_executes': True, 'existing_evidence_limits': ['真实当前版本原始字段/完成时间含义与正式保存/页面同源未验']}
- 问题ID：无规则专属未闭问题
- 附加待办：既有证据有限，不是整规则/真实医学通过；共通正式链缺口另列；本轮未执行测试/模型/注册器
- 证据：[admission-history.json](<F:/MedQC-worktrees/qc-integration-20261008/docs/acceptance/engine-audit-20261008/admission-history.json>) /rules/1；[overlay.json](<F:/MedQC-worktrees/qc-integration-20261008/docs/acceptance/engine-audit-20261008/next-batch/coverage-progress-current/overlay.json>) /rules/1

### LX0609-01-02-02

- 范围说明：{'authority': '冻结T0台账及1958ae3bb历史overlay范围继承；本轮未实时重查注册器/执行范围', 'phase_status': 'phase_1_target', 'release_scope': 'default', 'customer_excluded': False, 'default_executes': True, 'existing_evidence_limits': ['真实跨系统合理关联、明显无关、多文书业务键冲突样本及临床预期不足']}
- 问题ID：无规则专属未闭问题
- 附加待办：既有证据有限，不是整规则/真实医学通过；共通正式链缺口另列；本轮未执行测试/模型/注册器
- 证据：[admission-history.json](<F:/MedQC-worktrees/qc-integration-20261008/docs/acceptance/engine-audit-20261008/admission-history.json>) /rules/8；[overlay.json](<F:/MedQC-worktrees/qc-integration-20261008/docs/acceptance/engine-audit-20261008/next-batch/coverage-progress-current/overlay.json>) /rules/76

### LX0609-02-01-01

- 范围说明：{'authority': '冻结T0台账及1958ae3bb历史overlay范围继承；本轮未实时重查注册器/执行范围', 'phase_status': 'phase_1_target', 'release_scope': 'default', 'customer_excluded': False, 'default_executes': True, 'existing_evidence_limits': ['真实当前版本原始字段/完成时间含义与正式保存/页面同源未验']}
- 问题ID：无规则专属未闭问题
- 附加待办：既有证据有限，不是整规则/真实医学通过；共通正式链缺口另列；本轮未执行测试/模型/注册器
- 证据：[admission-history.json](<F:/MedQC-worktrees/qc-integration-20261008/docs/acceptance/engine-audit-20261008/admission-history.json>) /rules/2；[overlay.json](<F:/MedQC-worktrees/qc-integration-20261008/docs/acceptance/engine-audit-20261008/next-batch/coverage-progress-current/overlay.json>) /rules/4

### LX0609-02-01-02

- 范围说明：{'authority': '冻结T0台账及1958ae3bb历史overlay范围继承；本轮未实时重查注册器/执行范围', 'phase_status': 'phase_1_target', 'release_scope': 'default', 'customer_excluded': False, 'default_executes': True, 'existing_evidence_limits': ['真实当前版本原始字段/完成时间含义与正式保存/页面同源未验', '最高级别含糊职称抽取需真实模型']}
- 问题ID：无规则专属未闭问题
- 附加待办：既有证据有限，不是整规则/真实医学通过；共通正式链缺口另列；本轮未执行测试/模型/注册器
- 证据：[admission-history.json](<F:/MedQC-worktrees/qc-integration-20261008/docs/acceptance/engine-audit-20261008/admission-history.json>) /rules/3；[overlay.json](<F:/MedQC-worktrees/qc-integration-20261008/docs/acceptance/engine-audit-20261008/next-batch/coverage-progress-current/overlay.json>) /rules/5

### LX0609-02-01-03

- 范围说明：{'authority': '冻结T0台账及1958ae3bb历史overlay范围继承；本轮未实时重查注册器/执行范围', 'phase_status': 'phase_1_target', 'release_scope': 'default', 'customer_excluded': False, 'default_executes': True, 'existing_evidence_limits': ['缺时容量下界、多区间真实全源病例与正式保存回读未验']}
- 问题ID：C-SECOND
- 附加待办：既有证据有限，不是整规则/真实医学通过；共通正式链缺口另列；本轮未执行测试/模型/注册器；历史有限修复：C-SECOND
- 证据：[admission-history.json](<F:/MedQC-worktrees/qc-integration-20261008/docs/acceptance/engine-audit-20261008/admission-history.json>) /rules/4；[overlay.json](<F:/MedQC-worktrees/qc-integration-20261008/docs/acceptance/engine-audit-20261008/next-batch/coverage-progress-current/overlay.json>) /rules/6

### LX0609-02-01-04

- 范围说明：{'authority': '冻结T0台账及1958ae3bb历史overlay范围继承；本轮未实时重查注册器/执行范围', 'phase_status': 'phase_1_target', 'release_scope': 'default', 'customer_excluded': False, 'default_executes': True, 'existing_evidence_limits': ['病重起止重开真实样本不足；本轮未复现全部阳性自然日分支']}
- 问题ID：C-SEVERITY-SAME-TIME
- 附加待办：既有证据有限，不是整规则/真实医学通过；共通正式链缺口另列；本轮未执行测试/模型/注册器；历史有限修复：C-SEVERITY-SAME-TIME
- 证据：[admission-history.json](<F:/MedQC-worktrees/qc-integration-20261008/docs/acceptance/engine-audit-20261008/admission-history.json>) /rules/5；[overlay.json](<F:/MedQC-worktrees/qc-integration-20261008/docs/acceptance/engine-audit-20261008/next-batch/coverage-progress-current/overlay.json>) /rules/7

### LX0609-02-01-05

- 范围说明：{'authority': '冻结T0台账及1958ae3bb历史overlay范围继承；本轮未实时重查注册器/执行范围', 'phase_status': 'phase_1_target', 'release_scope': 'default', 'customer_excluded': False, 'default_executes': True, 'existing_evidence_limits': ['真实变化事件与检验/病程多源对应未验；阳性每日覆盖、变化误抽均需独立样本']}
- 问题ID：C-SEVERITY-SAME-TIME
- 附加待办：既有证据有限，不是整规则/真实医学通过；共通正式链缺口另列；本轮未执行测试/模型/注册器；历史有限修复：C-SEVERITY-SAME-TIME
- 证据：[admission-history.json](<F:/MedQC-worktrees/qc-integration-20261008/docs/acceptance/engine-audit-20261008/admission-history.json>) /rules/6；[overlay.json](<F:/MedQC-worktrees/qc-integration-20261008/docs/acceptance/engine-audit-20261008/next-batch/coverage-progress-current/overlay.json>) /rules/8

### LX0609-03-01-01

- 范围说明：0609实质审查分母；course-timing。本次仅文档台账分类，未重审生产代码、未重跑测试/模型；主类不代表整条临床或正式发布验收。
- 问题ID：无规则专属未闭问题
- 附加待办：policy_definition_pending；independent_consultation_source_missing
- 证据：[course-timing.json](<F:/MedQC-worktrees/qc-integration-20261008/docs/acceptance/engine-audit-20261008/course-timing.json>) /rules/0

### LX0609-03-01-02

- 范围说明：0609实质审查分母；course-timing。本次仅文档台账分类，未重审生产代码、未重跑测试/模型；主类不代表整条临床或正式发布验收。
- 问题ID：无规则专属未闭问题
- 附加待办：policy_definition_pending；consultation_application_source_missing
- 证据：[course-timing.json](<F:/MedQC-worktrees/qc-integration-20261008/docs/acceptance/engine-audit-20261008/course-timing.json>) /rules/1

### LX0609-03-01-03

- 范围说明：0609实质审查分母；course-timing。本次仅文档台账分类，未重审生产代码、未重跑测试/模型；主类不代表整条临床或正式发布验收。
- 问题ID：无规则专属未闭问题
- 附加待办：policy_definition_pending；consultation_opinion_source_missing
- 证据：[course-timing.json](<F:/MedQC-worktrees/qc-integration-20261008/docs/acceptance/engine-audit-20261008/course-timing.json>) /rules/2

### LX0609-03-01-04

- 范围说明：0609实质审查分母；course-timing。本次仅文档台账分类，未重审生产代码、未重跑测试/模型；主类不代表整条临床或正式发布验收。
- 问题ID：无规则专属未闭问题
- 附加待办：old_policy_evidence_not_portable；conditional_recommendation_contract_pending
- 证据：[course-timing.json](<F:/MedQC-worktrees/qc-integration-20261008/docs/acceptance/engine-audit-20261008/course-timing.json>) /risks/4；[course-timing.json](<F:/MedQC-worktrees/qc-integration-20261008/docs/acceptance/engine-audit-20261008/course-timing.json>) /rules/3

### LX0609-03-02-01

- 范围说明：0609实质审查分母；course-timing。本次仅文档台账分类，未重审生产代码、未重跑测试/模型；主类不代表整条临床或正式发布验收。
- 问题ID：course-timing:CT-01；course-timing:CT-02；course-timing:CT-03；course-timing:CT-04
- 附加待办：historical_counterexample_not_rerun_in_this_ledger；CT-02_closed；CT-03_closed；CT-04_closed；CT-R02_policy_dispute
- 证据：[closure-issues.json](<F:/MedQC-worktrees/qc-integration-20261008/docs/acceptance/engine-audit-20261008/closure-issues.json>) /issues/11；[closure-issues.json](<F:/MedQC-worktrees/qc-integration-20261008/docs/acceptance/engine-audit-20261008/closure-issues.json>) /issues/12；[closure-issues.json](<F:/MedQC-worktrees/qc-integration-20261008/docs/acceptance/engine-audit-20261008/closure-issues.json>) /issues/13；[closure-issues.json](<F:/MedQC-worktrees/qc-integration-20261008/docs/acceptance/engine-audit-20261008/closure-issues.json>) /issues/38；[course-timing.json](<F:/MedQC-worktrees/qc-integration-20261008/docs/acceptance/engine-audit-20261008/course-timing.json>) /findings/0; /risks/1；[course-timing.json](<F:/MedQC-worktrees/qc-integration-20261008/docs/acceptance/engine-audit-20261008/course-timing.json>) /rules/4

### LX0609-04-01-01

- 范围说明：0609实质审查分母；surgery-anesthesia。本次仅文档台账分类，未重审生产代码、未重跑测试/模型；主类不代表整条临床或正式发布验收。
- 问题ID：SURGERY-029030
- 附加待办：old_regression_not_reproduced；multi_event_negative_coverage_missing；source_association_contract_missing
- 证据：[closure-issues.json](<F:/MedQC-worktrees/qc-integration-20261008/docs/acceptance/engine-audit-20261008/closure-issues.json>) /issues/4；[review-v1.json](<F:/MedQC-worktrees/qc-integration-20261008/docs/acceptance/engine-audit-20261008/independent-closure/surgery029030-current/review-v1.json>) /cases/0；[surgery-anesthesia.json](<F:/MedQC-worktrees/qc-integration-20261008/docs/acceptance/engine-audit-20261008/surgery-anesthesia.json>) /rules/0

### LX0609-04-01-02

- 范围说明：0609实质审查分母；surgery-anesthesia。本次仅文档台账分类，未重审生产代码、未重跑测试/模型；主类不代表整条临床或正式发布验收。
- 问题ID：无规则专属未闭问题
- 附加待办：participant_semantic_gold_missing；emergency_exception_gold_missing
- 证据：[surgery-anesthesia.json](<F:/MedQC-worktrees/qc-integration-20261008/docs/acceptance/engine-audit-20261008/surgery-anesthesia.json>) /rules/1

### LX0609-04-01-03

- 范围说明：0609实质审查分母；surgery-anesthesia。本次仅文档台账分类，未重审生产代码、未重跑测试/模型；主类不代表整条临床或正式发布验收。
- 问题ID：SURGERY-FREEZE
- 附加待办：freeze_contract_difference；clinical_error_not_proven
- 证据：[closure-issues.json](<F:/MedQC-worktrees/qc-integration-20261008/docs/acceptance/engine-audit-20261008/closure-issues.json>) /issues/9；[surgery-anesthesia.json](<F:/MedQC-worktrees/qc-integration-20261008/docs/acceptance/engine-audit-20261008/surgery-anesthesia.json>) /freeze_differences/1；[surgery-anesthesia.json](<F:/MedQC-worktrees/qc-integration-20261008/docs/acceptance/engine-audit-20261008/surgery-anesthesia.json>) /rules/2

### LX0609-04-01-04

- 范围说明：0609实质审查分母；surgery-anesthesia。本次仅文档台账分类，未重审生产代码、未重跑测试/模型；主类不代表整条临床或正式发布验收。
- 问题ID：PREOP-MEDICAL
- 附加待办：PREOP-MEDICAL_business_dispute；bounded_real_validation_only
- 证据：[closure-issues.json](<F:/MedQC-worktrees/qc-integration-20261008/docs/acceptance/engine-audit-20261008/closure-issues.json>) /issues/5；[surgery-anesthesia.json](<F:/MedQC-worktrees/qc-integration-20261008/docs/acceptance/engine-audit-20261008/surgery-anesthesia.json>) /rules/3

### LX0609-04-01-05

- 范围说明：0609实质审查分母；surgery-anesthesia。本次仅文档台账分类，未重审生产代码、未重跑测试/模型；主类不代表整条临床或正式发布验收。
- 问题ID：PREOP-MEDICAL
- 附加待办：PREOP-MEDICAL_business_dispute；bounded_real_validation_only
- 证据：[closure-issues.json](<F:/MedQC-worktrees/qc-integration-20261008/docs/acceptance/engine-audit-20261008/closure-issues.json>) /issues/5；[surgery-anesthesia.json](<F:/MedQC-worktrees/qc-integration-20261008/docs/acceptance/engine-audit-20261008/surgery-anesthesia.json>) /rules/4

### LX0609-04-02-01

- 范围说明：0609实质审查分母；surgery-anesthesia。本次仅文档台账分类，未重审生产代码、未重跑测试/模型；主类不代表整条临床或正式发布验收。
- 问题ID：无规则专属未闭问题
- 附加待办：bounded_event_coverage_evidence
- 证据：[surgery-anesthesia.json](<F:/MedQC-worktrees/qc-integration-20261008/docs/acceptance/engine-audit-20261008/surgery-anesthesia.json>) /rules/5

### LX0609-04-02-02

- 范围说明：0609实质审查分母；surgery-anesthesia。本次仅文档台账分类，未重审生产代码、未重跑测试/模型；主类不代表整条临床或正式发布验收。
- 问题ID：SURGERY-029030；SURGERY-FREEZE
- 附加待办：old_regression_not_reproduced；freeze_contract_difference；multi_event_negative_coverage_missing
- 证据：[closure-issues.json](<F:/MedQC-worktrees/qc-integration-20261008/docs/acceptance/engine-audit-20261008/closure-issues.json>) /issues/4；[closure-issues.json](<F:/MedQC-worktrees/qc-integration-20261008/docs/acceptance/engine-audit-20261008/closure-issues.json>) /issues/9；[review-v1.json](<F:/MedQC-worktrees/qc-integration-20261008/docs/acceptance/engine-audit-20261008/independent-closure/surgery029030-current/review-v1.json>) /cases/1；[surgery-anesthesia.json](<F:/MedQC-worktrees/qc-integration-20261008/docs/acceptance/engine-audit-20261008/surgery-anesthesia.json>) /freeze_differences/0；[surgery-anesthesia.json](<F:/MedQC-worktrees/qc-integration-20261008/docs/acceptance/engine-audit-20261008/surgery-anesthesia.json>) /rules/6

### LX0609-04-02-03

- 范围说明：0609实质审查分母；surgery-anesthesia。本次仅文档台账分类，未重审生产代码、未重跑测试/模型；主类不代表整条临床或正式发布验收。
- 问题ID：无规则专属未闭问题
- 附加待办：malignancy_and_dissection_semantic_gold_missing
- 证据：[surgery-anesthesia.json](<F:/MedQC-worktrees/qc-integration-20261008/docs/acceptance/engine-audit-20261008/surgery-anesthesia.json>) /rules/7

### LX0609-04-02-04

- 范围说明：0609实质审查分母；surgery-anesthesia。本次仅文档台账分类，未重审生产代码、未重跑测试/模型；主类不代表整条临床或正式发布验收。
- 问题ID：无规则专属未闭问题
- 附加待办：pending_definition；implant_five_field_real_gold_pending
- 证据：[surgery-anesthesia.json](<F:/MedQC-worktrees/qc-integration-20261008/docs/acceptance/engine-audit-20261008/surgery-anesthesia.json>) /rules/8

### LX0609-04-02-05

- 范围说明：0609实质审查分母；surgery-anesthesia。本次仅文档台账分类，未重审生产代码、未重跑测试/模型；主类不代表整条临床或正式发布验收。
- 问题ID：无规则专属未闭问题
- 附加待办：bounded_identity_and_event_evidence
- 证据：[surgery-anesthesia.json](<F:/MedQC-worktrees/qc-integration-20261008/docs/acceptance/engine-audit-20261008/surgery-anesthesia.json>) /rules/9

### LX0609-04-02-06

- 范围说明：0609实质审查分母；surgery-anesthesia。本次仅文档台账分类，未重审生产代码、未重跑测试/模型；主类不代表整条临床或正式发布验收。
- 问题ID：无规则专属未闭问题
- 附加待办：current_binding_gap_closed；historical_source_sha_binding_missing；real_death_positive_gold_missing
- 证据：[review-v1.json](<F:/MedQC-worktrees/qc-integration-20261008/docs/acceptance/engine-audit-20261008/independent-closure/death060-current/review-v1.json>) /rules/0; /historical_binding; /remaining_validation_gaps；[surgery-anesthesia.json](<F:/MedQC-worktrees/qc-integration-20261008/docs/acceptance/engine-audit-20261008/surgery-anesthesia.json>) /rules/10

### LX0609-04-02-07

- 范围说明：0609实质审查分母；surgery-anesthesia。本次仅文档台账分类，未重审生产代码、未重跑测试/模型；主类不代表整条临床或正式发布验收。
- 问题ID：无规则专属未闭问题
- 附加待办：bounded_consultation_timeliness_evidence
- 证据：[surgery-anesthesia.json](<F:/MedQC-worktrees/qc-integration-20261008/docs/acceptance/engine-audit-20261008/surgery-anesthesia.json>) /rules/11

### LX0609-04-02-08

- 范围说明：0609实质审查分母；surgery-anesthesia。本次仅文档台账分类，未重审生产代码、未重跑测试/模型；主类不代表整条临床或正式发布验收。
- 问题ID：无规则专属未闭问题
- 附加待办：bounded_death_time_evidence
- 证据：[surgery-anesthesia.json](<F:/MedQC-worktrees/qc-integration-20261008/docs/acceptance/engine-audit-20261008/surgery-anesthesia.json>) /rules/12

### LX0609-04-03-01

- 范围说明：0609实质审查分母；surgery-anesthesia。本次仅文档台账分类，未重审生产代码、未重跑测试/模型；主类不代表整条临床或正式发布验收。
- 问题ID：SURGERY-FREEZE
- 附加待办：freeze_contract_difference；clinical_error_not_proven
- 证据：[closure-issues.json](<F:/MedQC-worktrees/qc-integration-20261008/docs/acceptance/engine-audit-20261008/closure-issues.json>) /issues/9；[surgery-anesthesia.json](<F:/MedQC-worktrees/qc-integration-20261008/docs/acceptance/engine-audit-20261008/surgery-anesthesia.json>) /freeze_differences/0；[surgery-anesthesia.json](<F:/MedQC-worktrees/qc-integration-20261008/docs/acceptance/engine-audit-20261008/surgery-anesthesia.json>) /rules/13

### LX0609-04-04-01

- 范围说明：0609实质审查分母；surgery-anesthesia。本次仅文档台账分类，未重审生产代码、未重跑测试/模型；主类不代表整条临床或正式发布验收。
- 问题ID：无规则专属未闭问题
- 附加待办：pending_definition；anesthesia_visit_sources_unavailable_customer_scope
- 证据：[surgery-anesthesia.json](<F:/MedQC-worktrees/qc-integration-20261008/docs/acceptance/engine-audit-20261008/surgery-anesthesia.json>) /rules/14

### LX0609-04-04-02

- 范围说明：0609实质审查分母；surgery-anesthesia。本次仅文档台账分类，未重审生产代码、未重跑测试/模型；主类不代表整条临床或正式发布验收。
- 问题ID：N12
- 附加待办：N12_engineering_closed；new_controlled_semantics_real_model_pending；marker_probe_bounded
- 证据：[resumption-reconciliation.md](<F:/MedQC-worktrees/qc-integration-20261008/docs/acceptance/engine-audit-20261008/resumption-reconciliation.md>) 行28、34：N12麻醉正式载体及过时状态纠正；[closure-issues.json](<F:/MedQC-worktrees/qc-integration-20261008/docs/acceptance/engine-audit-20261008/closure-issues.json>) /issues/0；[independent-review.md](<F:/MedQC-worktrees/qc-integration-20261008/docs/acceptance/engine-audit-20261008/independent-closure/n12-carrier-integration/independent-review.md>) 行5-13：375绿色、原首红保留及有限marker/真实语义边界；[surgery-anesthesia.json](<F:/MedQC-worktrees/qc-integration-20261008/docs/acceptance/engine-audit-20261008/surgery-anesthesia.json>) /rules/15

### LX0609-04-04-03

- 范围说明：0609实质审查分母；surgery-anesthesia。本次仅文档台账分类，未重审生产代码、未重跑测试/模型；主类不代表整条临床或正式发布验收。
- 问题ID：无规则专属未闭问题
- 附加待办：bounded_anesthesia_presence_evidence
- 证据：[surgery-anesthesia.json](<F:/MedQC-worktrees/qc-integration-20261008/docs/acceptance/engine-audit-20261008/surgery-anesthesia.json>) /rules/16

### LX0609-04-05-01

- 范围说明：0609实质审查分母；surgery-anesthesia。本次仅文档台账分类，未重审生产代码、未重跑测试/模型；主类不代表整条临床或正式发布验收。
- 问题ID：无规则专属未闭问题
- 附加待办：bounded_postoperative_window_evidence；N10_not_this_rule
- 证据：[surgery-anesthesia.json](<F:/MedQC-worktrees/qc-integration-20261008/docs/acceptance/engine-audit-20261008/surgery-anesthesia.json>) /rules/17

### LX0609-04-05-02

- 范围说明：0609实质审查分母；surgery-anesthesia。本次仅文档台账分类，未重审生产代码、未重跑测试/模型；主类不代表整条临床或正式发布验收。
- 问题ID：N10
- 附加待办：N10_engineering_closed；new_controlled_semantics_real_model_pending；TRUNCATED_snapshot_missing；fixture_adjustments_separately_disclosed
- 证据：[closure-issues.json](<F:/MedQC-worktrees/qc-integration-20261008/docs/acceptance/engine-audit-20261008/closure-issues.json>) /issues/1；[resumption-execution.md](<F:/MedQC-worktrees/qc-integration-20261008/docs/acceptance/engine-audit-20261008/resumption-execution.md>) 病程正文出口支持；[resumption-review.md](<F:/MedQC-worktrees/qc-integration-20261008/docs/acceptance/engine-audit-20261008/resumption-review.md>) R2最终工程集成结论，行92-100；N10四个旧坐标夹具追加独审，行162起；[surgery-anesthesia.json](<F:/MedQC-worktrees/qc-integration-20261008/docs/acceptance/engine-audit-20261008/surgery-anesthesia.json>) /rules/18

### LX0609-04-05-03

- 范围说明：0609实质审查分母；surgery-anesthesia。本次仅文档台账分类，未重审生产代码、未重跑测试/模型；主类不代表整条临床或正式发布验收。
- 问题ID：无规则专属未闭问题
- 附加待办：bounded_first_postoperative_course_evidence；N10_not_this_rule
- 证据：[surgery-anesthesia.json](<F:/MedQC-worktrees/qc-integration-20261008/docs/acceptance/engine-audit-20261008/surgery-anesthesia.json>) /rules/19

### LX0609-05-01-02

- 范围说明：默认执行范围的有限分类；不等于整条临床/发布验收完成。
- 问题ID：TP-L01；TP-Q03
- 附加待办：synthetic_source_binding_completed；real_semantics_pending_without_new_input_change；specific_catalog_contract_missing
- 证据：[review.md](<F:/MedQC-worktrees/qc-integration-20261008/docs/acceptance/engine-audit-20261008/independent-closure/antibiotic-current/review.md>) 精确输入与结果；完成层级与剩余门禁；[remaining-audit-evidence.json](<F:/MedQC-worktrees/qc-integration-20261008/docs/acceptance/engine-audit-20261008/remaining-audit-evidence.json>) /rules/35；[tumor-pathology.md](<F:/MedQC-worktrees/qc-integration-20261008/docs/acceptance/engine-audit-20261008/tumor-pathology.md>) 不按确定缺陷认领的差异

### LX0609-05-01-03

- 范围说明：默认执行范围的有限分类；不等于整条临床/发布验收完成。
- 问题ID：tumor-pathology:TP-D05
- 附加待办：current_counterexample_not_reproduced；clinical_gold_pending
- 证据：[closure-issues.json](<F:/MedQC-worktrees/qc-integration-20261008/docs/acceptance/engine-audit-20261008/closure-issues.json>) /issues/31；[tumor-pathology.md](<F:/MedQC-worktrees/qc-integration-20261008/docs/acceptance/engine-audit-20261008/tumor-pathology.md>) 可修问题：TP-D05；[tumor-pathology.json](<F:/MedQC-worktrees/qc-integration-20261008/docs/acceptance/engine-audit-20261008/tumor-pathology.json>) /findings/4

### LX0609-05-01-05

- 范围说明：默认执行范围的有限分类；不等于整条临床/发布验收完成。
- 问题ID：TP-Q04；TP-Q05
- 附加待办：synthetic_source_binding_completed；business_basis_dispute；real_semantics_pending_without_new_input_change
- 证据：[review.md](<F:/MedQC-worktrees/qc-integration-20261008/docs/acceptance/engine-audit-20261008/independent-closure/antibiotic-current/review.md>) 精确输入与结果case19/21；完成层级与剩余门禁；[remaining-audit-evidence.json](<F:/MedQC-worktrees/qc-integration-20261008/docs/acceptance/engine-audit-20261008/remaining-audit-evidence.json>) /rules/38

### LX0609-05-01-06

- 范围说明：默认执行范围的有限分类；不等于整条临床/发布验收完成。
- 问题ID：tumor-pathology:TP-D04
- 附加待办：limited_engineering_subissue_closed；clinical_source_signoff_pending
- 证据：[closure-issues.json](<F:/MedQC-worktrees/qc-integration-20261008/docs/acceptance/engine-audit-20261008/closure-issues.json>) /issues/30；[integration-progress.md](<F:/MedQC-worktrees/qc-integration-20261008/docs/acceptance/engine-audit-20261008/integration-progress.md>) N12 and TP-D04 fixed integration；[overlay.md](<F:/MedQC-worktrees/qc-integration-20261008/docs/acceptance/engine-audit-20261008/next-batch/coverage-progress-current/overlay.md>) 必须保留的限定结论：TP-D04（1958历史）

### LX0609-05-02-01

- 范围说明：默认执行范围的有限分类；不等于整条临床/发布验收完成。
- 问题ID：tumor-pathology:TP-D02；tumor-pathology:TP-D03；N13；tumor-pathology:TP-D01
- 附加待办：current_counterexample_not_reproduced；candidate_not_integrated；limited_N13_and_TPD01_inherited；legacy_regression_unverified；real_semantics_pending；unit_time_contract_disputes
- 证据：[closure-issues.json](<F:/MedQC-worktrees/qc-integration-20261008/docs/acceptance/engine-audit-20261008/closure-issues.json>) /issues/28；/issues/29；/issues/2；/issues/27；[resumption-reconciliation.md](<F:/MedQC-worktrees/qc-integration-20261008/docs/acceptance/engine-audit-20261008/resumption-reconciliation.md>) 五、化疗候选具体核对；附录A；[resumption-execution.md](<F:/MedQC-worktrees/qc-integration-20261008/docs/acceptance/engine-audit-20261008/resumption-execution.md>) 化疗与剩余项

### LX0609-06-01-01

- 范围说明：默认执行范围的有限分类；不等于整条临床/发布验收完成。
- 问题ID：imaging-laboratory:IML-01
- 附加待办：partial_engineering_integrated；rule_attribution_unknown_for_original_joint_case；specific_identity_contract_pending
- 证据：[integration-progress.md](<F:/MedQC-worktrees/qc-integration-20261008/docs/acceptance/engine-audit-20261008/integration-progress.md>) IML01 precise consumers mapped（118行）；[closure-issues.json](<F:/MedQC-worktrees/qc-integration-20261008/docs/acceptance/engine-audit-20261008/closure-issues.json>) /issues/17；[resumption-reconciliation.md](<F:/MedQC-worktrees/qc-integration-20261008/docs/acceptance/engine-audit-20261008/resumption-reconciliation.md>) 四、IML01

### LX0609-06-01-02

- 范围说明：默认执行范围的有限分类；不等于整条临床/发布验收完成。
- 问题ID：imaging-laboratory:IML-D02
- 附加待办：business_basis_dispute；old_R02_limited_fix_inherited
- 证据：[closure-issues.json](<F:/MedQC-worktrees/qc-integration-20261008/docs/acceptance/engine-audit-20261008/closure-issues.json>) /issues/20；[imaging-laboratory.md](<F:/MedQC-worktrees/qc-integration-20261008/docs/acceptance/engine-audit-20261008/imaging-laboratory.md>) IML-D02；逐规则06-01-02

### LX0609-06-01-03

- 范围说明：acceptance_only，已撤出默认，仅显式范围；分类不授权启用。
- 问题ID：imaging-laboratory:IML-01；imaging-laboratory:IML-D01
- 附加待办：partial_engineering_integrated；business_basis_dispute；acceptance_only_default_off；program_only_no_model_needed
- 证据：[integration-progress.md](<F:/MedQC-worktrees/qc-integration-20261008/docs/acceptance/engine-audit-20261008/integration-progress.md>) IML01 precise consumers mapped；[closure-issues.json](<F:/MedQC-worktrees/qc-integration-20261008/docs/acceptance/engine-audit-20261008/closure-issues.json>) /issues/17；/issues/19

### LX0609-06-01-04

- 范围说明：默认执行范围的有限分类；不等于整条临床/发布验收完成。
- 问题ID：CT-INPUT-CHANGE
- 附加待办：specific_source_reading_locator_missing；historical_real_response_limited_inheritance
- 证据：[closure-issues.json](<F:/MedQC-worktrees/qc-integration-20261008/docs/acceptance/engine-audit-20261008/closure-issues.json>) /issues/6；[imaging-laboratory.md](<F:/MedQC-worktrees/qc-integration-20261008/docs/acceptance/engine-audit-20261008/imaging-laboratory.md>) 旧CT真实证据；逐规则06-01-04；[remaining-audit-evidence.json](<F:/MedQC-worktrees/qc-integration-20261008/docs/acceptance/engine-audit-20261008/remaining-audit-evidence.json>) /rules/45

### LX0609-06-01-05

- 范围说明：默认执行范围的有限分类；不等于整条临床/发布验收完成。
- 问题ID：CT-INPUT-CHANGE
- 附加待办：specific_source_reading_locator_missing；historical_real_response_limited_inheritance
- 证据：[closure-issues.json](<F:/MedQC-worktrees/qc-integration-20261008/docs/acceptance/engine-audit-20261008/closure-issues.json>) /issues/6；[imaging-laboratory.md](<F:/MedQC-worktrees/qc-integration-20261008/docs/acceptance/engine-audit-20261008/imaging-laboratory.md>) 旧CT真实证据；逐规则06-01-05；[remaining-audit-evidence.json](<F:/MedQC-worktrees/qc-integration-20261008/docs/acceptance/engine-audit-20261008/remaining-audit-evidence.json>) /rules/46

### LX0609-06-02-01

- 范围说明：acceptance_only，已撤出默认，仅显式范围；分类不授权启用。
- 问题ID：无规则专属未闭问题
- 附加待办：specific_source_reading_locator_missing；historical_technical_chain_limited_inheritance；acceptance_only_default_off；program_only_no_model_needed
- 证据：[remaining-audit-evidence.json](<F:/MedQC-worktrees/qc-integration-20261008/docs/acceptance/engine-audit-20261008/remaining-audit-evidence.json>) /rules/47；[imaging-laboratory.md](<F:/MedQC-worktrees/qc-integration-20261008/docs/acceptance/engine-audit-20261008/imaging-laboratory.md>) 逐规则06-02-01；历史证据界限

### LX0609-06-02-02

- 范围说明：默认执行范围的有限分类；不等于整条临床/发布验收完成。
- 问题ID：PATH-INPUT-CHANGE
- 附加待办：historical_review_inherited；event_linkage_inputs_changed
- 证据：[closure-issues.json](<F:/MedQC-worktrees/qc-integration-20261008/docs/acceptance/engine-audit-20261008/closure-issues.json>) /issues/7；[imaging-laboratory.md](<F:/MedQC-worktrees/qc-integration-20261008/docs/acceptance/engine-audit-20261008/imaging-laboratory.md>) 逐规则06-02-02；病理历史与复验界限

### LX0609-06-02-03

- 范围说明：默认执行范围的有限分类；不等于整条临床/发布验收完成。
- 问题ID：PATH-INPUT-CHANGE
- 附加待办：historical_review_inherited；event_linkage_inputs_changed
- 证据：[closure-issues.json](<F:/MedQC-worktrees/qc-integration-20261008/docs/acceptance/engine-audit-20261008/closure-issues.json>) /issues/7；[imaging-laboratory.md](<F:/MedQC-worktrees/qc-integration-20261008/docs/acceptance/engine-audit-20261008/imaging-laboratory.md>) 逐规则06-02-03；病理历史与复验界限

### LX0609-06-03-02

- 范围说明：acceptance_only，已撤出默认，仅显式范围；分类不授权启用。
- 问题ID：imaging-laboratory:IML-01
- 附加待办：limited_culture_role_fix_inherited；acceptance_only_default_off；program_only_no_model_needed
- 证据：[integration-progress.md](<F:/MedQC-worktrees/qc-integration-20261008/docs/acceptance/engine-audit-20261008/integration-progress.md>) IML01 precise consumers mapped；[closure-issues.json](<F:/MedQC-worktrees/qc-integration-20261008/docs/acceptance/engine-audit-20261008/closure-issues.json>) /issues/17

### LX0609-06-03-03

- 范围说明：默认执行范围的有限分类；不等于整条临床/发布验收完成。
- 问题ID：无规则专属未闭问题
- 附加待办：current_synthetic_binding_and_literal_restored；historical_real_manifest_missing；specific_source_reading_locator_missing
- 证据：[evidence-binding-current.md](<F:/MedQC-worktrees/qc-integration-20261008/docs/acceptance/engine-audit-20261008/next-batch/evidence-binding-current.md>) 培养两条及2026-10-08后续45/45；[current-review.md](<F:/MedQC-worktrees/qc-integration-20261008/docs/acceptance/engine-audit-20261008/independent-closure/culture-current/current-review.md>) Binding and limits；[remaining-audit-evidence.json](<F:/MedQC-worktrees/qc-integration-20261008/docs/acceptance/engine-audit-20261008/remaining-audit-evidence.json>) /rules/52

### LX0609-06-03-04

- 范围说明：默认执行范围的有限分类；不等于整条临床/发布验收完成。
- 问题ID：无规则专属未闭问题
- 附加待办：current_synthetic_binding_and_literal_restored；historical_real_manifest_missing；specific_source_reading_locator_missing
- 证据：[evidence-binding-current.md](<F:/MedQC-worktrees/qc-integration-20261008/docs/acceptance/engine-audit-20261008/next-batch/evidence-binding-current.md>) 培养两条及2026-10-08后续45/45；[current-review.md](<F:/MedQC-worktrees/qc-integration-20261008/docs/acceptance/engine-audit-20261008/independent-closure/culture-current/current-review.md>) Binding and limits；[remaining-audit-evidence.json](<F:/MedQC-worktrees/qc-integration-20261008/docs/acceptance/engine-audit-20261008/remaining-audit-evidence.json>) /rules/53

### LX0609-06-04-01

- 范围说明：默认执行范围的有限分类；不等于整条临床/发布验收完成。
- 问题ID：imaging-laboratory:IML-02
- 附加待办：limited_engineering_subissue_closed；not_whole_rule_clinical_acceptance；common_formal_chain_pending
- 证据：[closure-issues.json](<F:/MedQC-worktrees/qc-integration-20261008/docs/acceptance/engine-audit-20261008/closure-issues.json>) /issues/18；[closure-ownership.json](<F:/MedQC-worktrees/qc-integration-20261008/docs/acceptance/engine-audit-20261008/closure-ownership.json>) /tasks/2（IML-02集成a8ad74e69）；[imaging-laboratory.md](<F:/MedQC-worktrees/qc-integration-20261008/docs/acceptance/engine-audit-20261008/imaging-laboratory.md>) T1 IML-02关闭标准（原历史）

### LX0609-06-04-02

- 范围说明：默认执行范围的有限分类；不等于整条临床/发布验收完成。
- 问题ID：imaging-laboratory:IML-02
- 附加待办：limited_engineering_subissue_closed；not_whole_rule_clinical_acceptance；common_formal_chain_pending
- 证据：[closure-issues.json](<F:/MedQC-worktrees/qc-integration-20261008/docs/acceptance/engine-audit-20261008/closure-issues.json>) /issues/18；[closure-ownership.json](<F:/MedQC-worktrees/qc-integration-20261008/docs/acceptance/engine-audit-20261008/closure-ownership.json>) /tasks/2（IML-02集成a8ad74e69）；[imaging-laboratory.md](<F:/MedQC-worktrees/qc-integration-20261008/docs/acceptance/engine-audit-20261008/imaging-laboratory.md>) T1 IML-02关闭标准（原历史）

### LX0609-07-01-01

- 范围说明：默认执行范围的有限分类；不等于整条临床/发布验收完成。
- 问题ID：treatment-consultation:TC-01
- 附加待办：current_integrated_counterexample_not_reproduced；shared_gate_defect_explicit_rule_path；candidate_not_integrated；candidate425_3_not_rule_pass_count
- 证据：[tc01-original-cases.json](<F:/MedQC-worktrees/qc-integration-20261008/docs/acceptance/engine-audit-20261008/next-batch/transfusion-family/tc01-original-cases.json>) /checks/0；/checks/1；/checks/2；/original_observations；[review.md](<F:/MedQC-worktrees/qc-integration-20261008/docs/acceptance/engine-audit-20261008/next-batch/transfusion-family/review.md>) 共用helper和各规则还缺的事实：043路径；旧结果边界；[closure-issues.json](<F:/MedQC-worktrees/qc-integration-20261008/docs/acceptance/engine-audit-20261008/closure-issues.json>) /issues/24；[resumption-execution.md](<F:/MedQC-worktrees/qc-integration-20261008/docs/acceptance/engine-audit-20261008/resumption-execution.md>) 2026-10-09：来源就绪状态修复（425/3，未集成）

### LX0609-07-01-02

- 范围说明：默认执行范围的有限分类；不等于整条临床/发布验收完成。
- 问题ID：treatment-consultation:TC-01；TR-044-MULTI
- 附加待办：current_integrated_counterexample_not_reproduced；shared_gate_defect_explicit_rule_path；candidate_not_integrated；candidate425_3_not_rule_pass_count；TR044_exact_manifest_missing；closed_db4_contract_inherited
- 证据：[tc01-original-cases.json](<F:/MedQC-worktrees/qc-integration-20261008/docs/acceptance/engine-audit-20261008/next-batch/transfusion-family/tc01-original-cases.json>) /checks/0；/checks/1；/checks/2；/original_observations；[review.md](<F:/MedQC-worktrees/qc-integration-20261008/docs/acceptance/engine-audit-20261008/next-batch/transfusion-family/review.md>) 共用helper和各规则还缺的事实：044路径；旧结果边界；[closure-issues.json](<F:/MedQC-worktrees/qc-integration-20261008/docs/acceptance/engine-audit-20261008/closure-issues.json>) /issues/24；/issues/3；[resumption-execution.md](<F:/MedQC-worktrees/qc-integration-20261008/docs/acceptance/engine-audit-20261008/resumption-execution.md>) 2026-10-09：来源就绪状态修复（425/3，未集成）

### LX0609-07-01-03

- 范围说明：默认执行范围的有限分类；不等于整条临床/发布验收完成。
- 问题ID：treatment-consultation:TC-02
- 附加待办：limited_engineering_and_formal_wrapper_closed；real_model_semantics_pending_after_input_change；normal_C_labID_precise_card_limit
- 证据：[closure-issues.json](<F:/MedQC-worktrees/qc-integration-20261008/docs/acceptance/engine-audit-20261008/closure-issues.json>) /issues/25；[pv-carrier-review.md](<F:/MedQC-worktrees/qc-integration-20261008/docs/acceptance/engine-audit-20261008/independent-closure/tc02-integration/pv-carrier-review.md>) fixed-196d independent acceptance；[integration-progress.md](<F:/MedQC-worktrees/qc-integration-20261008/docs/acceptance/engine-audit-20261008/integration-progress.md>) TC02固定独审、串行集成与root复跑

### LX0609-07-02-01

- 范围说明：默认执行范围的有限分类；不等于整条临床/发布验收完成。
- 问题ID：treatment-consultation:TC-01
- 附加待办：current_integrated_counterexample_not_reproduced；shared_gate_defect_explicit_rule_path；candidate_not_integrated；candidate425_3_not_rule_pass_count
- 证据：[tc01-original-cases.json](<F:/MedQC-worktrees/qc-integration-20261008/docs/acceptance/engine-audit-20261008/next-batch/transfusion-family/tc01-original-cases.json>) /checks/0；/checks/1；/checks/2；/original_observations；[review.md](<F:/MedQC-worktrees/qc-integration-20261008/docs/acceptance/engine-audit-20261008/next-batch/transfusion-family/review.md>) 共用helper和各规则还缺的事实：045路径；旧结果边界；[closure-issues.json](<F:/MedQC-worktrees/qc-integration-20261008/docs/acceptance/engine-audit-20261008/closure-issues.json>) /issues/24；[resumption-execution.md](<F:/MedQC-worktrees/qc-integration-20261008/docs/acceptance/engine-audit-20261008/resumption-execution.md>) 2026-10-09：来源就绪状态修复（425/3，未集成）

### LX0609-07-02-02

- 范围说明：默认执行范围的有限分类；不等于整条临床/发布验收完成。
- 问题ID：treatment-consultation:TC-01
- 附加待办：current_integrated_counterexample_not_reproduced；shared_gate_defect_explicit_rule_path；candidate_not_integrated；candidate425_3_not_rule_pass_count
- 证据：[tc01-original-cases.json](<F:/MedQC-worktrees/qc-integration-20261008/docs/acceptance/engine-audit-20261008/next-batch/transfusion-family/tc01-original-cases.json>) /checks/0；/checks/1；/checks/2；/original_observations；/original_observations/5；[review.md](<F:/MedQC-worktrees/qc-integration-20261008/docs/acceptance/engine-audit-20261008/next-batch/transfusion-family/review.md>) 共用helper和各规则还缺的事实：046路径；旧结果边界；[closure-issues.json](<F:/MedQC-worktrees/qc-integration-20261008/docs/acceptance/engine-audit-20261008/closure-issues.json>) /issues/24；[resumption-execution.md](<F:/MedQC-worktrees/qc-integration-20261008/docs/acceptance/engine-audit-20261008/resumption-execution.md>) 2026-10-09：来源就绪状态修复（425/3，未集成）

### LX0609-07-03-01

- 范围说明：默认执行范围的有限分类；不等于整条临床/发布验收完成。
- 问题ID：treatment-consultation:TC-01
- 附加待办：current_integrated_counterexample_not_reproduced；shared_gate_defect_explicit_rule_path；candidate_not_integrated；candidate425_3_not_rule_pass_count
- 证据：[tc01-original-cases.json](<F:/MedQC-worktrees/qc-integration-20261008/docs/acceptance/engine-audit-20261008/next-batch/transfusion-family/tc01-original-cases.json>) /checks/0；/checks/1；/checks/2；/original_observations；[review.md](<F:/MedQC-worktrees/qc-integration-20261008/docs/acceptance/engine-audit-20261008/next-batch/transfusion-family/review.md>) 共用helper和各规则还缺的事实：047路径；旧结果边界；[closure-issues.json](<F:/MedQC-worktrees/qc-integration-20261008/docs/acceptance/engine-audit-20261008/closure-issues.json>) /issues/24；[resumption-execution.md](<F:/MedQC-worktrees/qc-integration-20261008/docs/acceptance/engine-audit-20261008/resumption-execution.md>) 2026-10-09：来源就绪状态修复（425/3，未集成）

### LX0609-07-04-01

- 范围说明：默认执行范围的有限分类；不等于整条临床/发布验收完成。
- 问题ID：treatment-consultation:TC-03；TR-048-REAL
- 附加待办：current_counterexample_not_reproduced；closed_pairing_contract_inherited；affected_real_validation_pending；complete_three_document_sample_missing
- 证据：[treatment-consultation.json](<F:/MedQC-worktrees/qc-integration-20261008/docs/acceptance/engine-audit-20261008/treatment-consultation.json>) /findings/2（048_NEGATED_INTRAOPERATIVE）；[closure-issues.json](<F:/MedQC-worktrees/qc-integration-20261008/docs/acceptance/engine-audit-20261008/closure-issues.json>) /issues/26；/issues/10；[treatment-consultation.json](<F:/MedQC-worktrees/qc-integration-20261008/docs/acceptance/engine-audit-20261008/treatment-consultation.json>) /closed_work_preserved/0

### LX0609-08-01-01

- 范围说明：0609实质审查分母；discharge-death。本次仅文档台账分类，未重审生产代码、未重跑测试/模型；主类不代表整条临床或正式发布验收。
- 问题ID：无规则专属未闭问题
- 附加待办：current_binding_gap_closed；historical_execution_manifest_missing；pure_timeliness_only
- 证据：[current-evidence-review.json](<F:/MedQC-worktrees/qc-integration-20261008/docs/acceptance/engine-audit-20261008/independent-closure/discharge-death-current/current-evidence-review.json>) /rules/0; /attempts/4；[discharge-death.json](<F:/MedQC-worktrees/qc-integration-20261008/docs/acceptance/engine-audit-20261008/discharge-death.json>) /rules/0

### LX0609-08-01-02

- 范围说明：0609实质审查分母；discharge-death。本次仅文档台账分类，未重审生产代码、未重跑测试/模型；主类不代表整条临床或正式发布验收。
- 问题ID：discharge-death:DD-F02
- 附加待办：authority_discharge_medication_contract_missing；wrong_drug_or_dose_oracle_missing；mechanism_observation_not_clinical_failure
- 证据：[closure-issues.json](<F:/MedQC-worktrees/qc-integration-20261008/docs/acceptance/engine-audit-20261008/closure-issues.json>) /issues/15；[boundary.md](<F:/MedQC-worktrees/qc-integration-20261008/docs/acceptance/engine-audit-20261008/next-batch/discharge-medication/boundary.md>) 原要求含完整性和药名/剂量错误；原反例与限制；必须补件；[discharge-death.json](<F:/MedQC-worktrees/qc-integration-20261008/docs/acceptance/engine-audit-20261008/discharge-death.json>) /rules/1

### LX0609-08-01-03

- 范围说明：0609实质审查分母；discharge-death。本次仅文档台账分类，未重审生产代码、未重跑测试/模型；主类不代表整条临床或正式发布验收。
- 问题ID：discharge-death:DD-F01
- 附加待办：DD-F01_engineering_closed；bounded_diagnosis_evidence
- 证据：[closure-issues.json](<F:/MedQC-worktrees/qc-integration-20261008/docs/acceptance/engine-audit-20261008/closure-issues.json>) /issues/14；[discharge-death.json](<F:/MedQC-worktrees/qc-integration-20261008/docs/acceptance/engine-audit-20261008/discharge-death.json>) /rules/2

### LX0609-08-01-04

- 范围说明：0609实质审查分母；discharge-death。本次仅文档台账分类，未重审生产代码、未重跑测试/模型；主类不代表整条临床或正式发布验收。
- 问题ID：discharge-death:DD-F05
- 附加待办：DD-F05_business_basis_dispute；malignancy_applicability_evidence_missing
- 证据：[closure-issues.json](<F:/MedQC-worktrees/qc-integration-20261008/docs/acceptance/engine-audit-20261008/closure-issues.json>) /issues/16；[discharge-death.json](<F:/MedQC-worktrees/qc-integration-20261008/docs/acceptance/engine-audit-20261008/discharge-death.json>) /rules/3

### LX0609-08-02-01

- 范围说明：0609实质审查分母；discharge-death。本次仅文档台账分类，未重审生产代码、未重跑测试/模型；主类不代表整条临床或正式发布验收。
- 问题ID：N10
- 附加待办：N10_engineering_closed；new_controlled_semantics_real_model_pending；TRUNCATED_snapshot_missing；fixture_adjustments_separately_disclosed
- 证据：[closure-issues.json](<F:/MedQC-worktrees/qc-integration-20261008/docs/acceptance/engine-audit-20261008/closure-issues.json>) /issues/1；[resumption-execution.md](<F:/MedQC-worktrees/qc-integration-20261008/docs/acceptance/engine-audit-20261008/resumption-execution.md>) 病程正文出口支持；[resumption-review.md](<F:/MedQC-worktrees/qc-integration-20261008/docs/acceptance/engine-audit-20261008/resumption-review.md>) R2最终工程集成结论，行92-100；N10四个旧坐标夹具追加独审，行162起；[discharge-death.json](<F:/MedQC-worktrees/qc-integration-20261008/docs/acceptance/engine-audit-20261008/discharge-death.json>) /rules/5

### LX0609-08-02-02

- 范围说明：0609实质审查分母；discharge-death。本次仅文档台账分类，未重审生产代码、未重跑测试/模型；主类不代表整条临床或正式发布验收。
- 问题ID：无规则专属未闭问题
- 附加待办：current_binding_gap_closed；historical_execution_manifest_missing；declarative_initialization_substitute
- 证据：[resumption-review.md](<F:/MedQC-worktrees/qc-integration-20261008/docs/acceptance/engine-audit-20261008/resumption-review.md>) R2最终工程集成结论，行98-100；R2工程集成候选复核与缺件，行74；[current-evidence-review.json](<F:/MedQC-worktrees/qc-integration-20261008/docs/acceptance/engine-audit-20261008/independent-closure/discharge-death-current/current-evidence-review.json>) /rules/1; /attempts/4；[discharge-death.json](<F:/MedQC-worktrees/qc-integration-20261008/docs/acceptance/engine-audit-20261008/discharge-death.json>) /rules/6

### LX0609-09-01-01

- 范围说明：{'authority': '冻结T0台账及1958ae3bb历史overlay范围继承；本轮未实时重查注册器/执行范围', 'phase_status': 'phase_1_target', 'release_scope': 'default', 'customer_excluded': False, 'default_executes': True, 'existing_evidence_limits': '既有脱敏历史只证明结束时间可解析和离线等价；无临床金标，未验证真实多事件全面关联。'}
- 问题ID：无规则专属未闭问题
- 附加待办：既有证据有限，不是整规则/真实医学通过；共通正式链缺口另列；本轮未执行测试/模型/注册器
- 证据：[rescue-remaining.json](<F:/MedQC-worktrees/qc-integration-20261008/docs/acceptance/engine-audit-20261008/rescue-remaining.json>) /rules/0；[overlay.json](<F:/MedQC-worktrees/qc-integration-20261008/docs/acceptance/engine-audit-20261008/next-batch/coverage-progress-current/overlay.json>) /rules/3

### LX0609-09-01-02

- 范围说明：{'authority': '冻结T0台账及1958ae3bb历史overlay范围继承；本轮未实时重查注册器/执行范围', 'phase_status': 'phase_1_target', 'release_scope': 'acceptance_only', 'customer_excluded': False, 'default_executes': False, 'existing_evidence_limits': '只读脱敏历史R01为唯一真实抢救例，原响应回放无独立临床金标；保守否定词筛查的病情描述假阴性已知，泛化未确认。'}
- 问题ID：无规则专属未闭问题
- 附加待办：既有证据有限，不是整规则/真实医学通过；共通正式链缺口另列；本轮未执行测试/模型/注册器
- 证据：[rescue-remaining.json](<F:/MedQC-worktrees/qc-integration-20261008/docs/acceptance/engine-audit-20261008/rescue-remaining.json>) /rules/14；[overlay.json](<F:/MedQC-worktrees/qc-integration-20261008/docs/acceptance/engine-audit-20261008/next-batch/coverage-progress-current/overlay.json>) /rules/84

### LX0609-09-02-01

- 范围说明：{'authority': '冻结T0台账及1958ae3bb历史overlay范围继承；本轮未实时重查注册器/执行范围', 'phase_status': 'phase_1_target', 'release_scope': 'default', 'customer_excluded': False, 'default_executes': True, 'existing_evidence_limits': '历史30例死亡/死亡讨论专表零不证明适用性；两探针为合成业务预期，终点排除及未知文书有效性仍需独立业务确认。'}
- 问题ID：rescue-remaining:RR-D01；rescue-remaining:RR-D02
- 附加待办：既有证据有限，不是整规则/真实医学通过；共通正式链缺口另列；本轮未执行测试/模型/注册器；后续已闭：rescue-remaining:RR-D02
- 证据：[rescue-remaining.json](<F:/MedQC-worktrees/qc-integration-20261008/docs/acceptance/engine-audit-20261008/rescue-remaining.json>) /rules/8；[overlay.json](<F:/MedQC-worktrees/qc-integration-20261008/docs/acceptance/engine-audit-20261008/next-batch/coverage-progress-current/overlay.json>) /rules/50；[closure-issues.json](<F:/MedQC-worktrees/qc-integration-20261008/docs/acceptance/engine-audit-20261008/closure-issues.json>) /issues/21；[closure-issues.json](<F:/MedQC-worktrees/qc-integration-20261008/docs/acceptance/engine-audit-20261008/closure-issues.json>) /issues/22

### LX0609-10-01-01

- 范围说明：{'authority': '冻结T0台账及1958ae3bb历史overlay范围继承；本轮未实时重查注册器/执行范围', 'phase_status': 'phase_1_target', 'release_scope': 'default', 'customer_excluded': False, 'default_executes': True, 'existing_evidence_limits': '历史30例交/接班专表为空，未完整审查事件和签名时间线，未覆盖适用真实病例。'}
- 问题ID：C-GAP-CONTRACT
- 附加待办：既有证据有限，不是整规则/真实医学通过；共通正式链缺口另列；本轮未执行测试/模型/注册器；历史有限修复：C-GAP-CONTRACT
- 证据：[rescue-remaining.json](<F:/MedQC-worktrees/qc-integration-20261008/docs/acceptance/engine-audit-20261008/rescue-remaining.json>) /rules/9；[overlay.json](<F:/MedQC-worktrees/qc-integration-20261008/docs/acceptance/engine-audit-20261008/next-batch/coverage-progress-current/overlay.json>) /rules/70

### LX0609-10-02-01

- 范围说明：{'authority': '冻结T0台账及1958ae3bb历史overlay范围继承；本轮未实时重查注册器/执行范围', 'phase_status': 'phase_1_target', 'release_scope': 'default', 'customer_excluded': False, 'default_executes': True, 'existing_evidence_limits': '脱敏历史两真实多事件仅4/4资料不足；不能证明多事件业务完备。所有同义计划/否定边界未穷尽。'}
- 问题ID：无规则专属未闭问题
- 附加待办：既有证据有限，不是整规则/真实医学通过；共通正式链缺口另列；本轮未执行测试/模型/注册器
- 证据：[rescue-remaining.json](<F:/MedQC-worktrees/qc-integration-20261008/docs/acceptance/engine-audit-20261008/rescue-remaining.json>) /rules/10；[overlay.json](<F:/MedQC-worktrees/qc-integration-20261008/docs/acceptance/engine-audit-20261008/next-batch/coverage-progress-current/overlay.json>) /rules/71

### LX0609-10-02-02

- 范围说明：{'authority': '冻结T0台账及1958ae3bb历史overlay范围继承；本轮未实时重查注册器/执行范围', 'phase_status': 'phase_1_target', 'release_scope': 'default', 'customer_excluded': False, 'default_executes': True, 'existing_evidence_limits': '同072真实证据只证明资料不足，未形成临床金标。'}
- 问题ID：无规则专属未闭问题
- 附加待办：既有证据有限，不是整规则/真实医学通过；共通正式链缺口另列；本轮未执行测试/模型/注册器
- 证据：[rescue-remaining.json](<F:/MedQC-worktrees/qc-integration-20261008/docs/acceptance/engine-audit-20261008/rescue-remaining.json>) /rules/11；[overlay.json](<F:/MedQC-worktrees/qc-integration-20261008/docs/acceptance/engine-audit-20261008/next-batch/coverage-progress-current/overlay.json>) /rules/72

### LX0609-10-03-01

- 范围说明：{'authority': '冻结T0台账及1958ae3bb历史overlay范围继承；本轮未实时重查注册器/执行范围', 'phase_status': 'pending_definition', 'release_scope': 'default', 'customer_excluded': False, 'default_executes': False, 'existing_evidence_limits': '有创操作目录未冻结，客户业务验收未完成；本轮不新增主链旁路审查。'}
- 问题ID：无规则专属未闭问题
- 附加待办：既有证据有限，不是整规则/真实医学通过；共通正式链缺口另列；本轮未执行测试/模型/注册器
- 证据：[rescue-remaining.json](<F:/MedQC-worktrees/qc-integration-20261008/docs/acceptance/engine-audit-20261008/rescue-remaining.json>) /rules/13；[overlay.json](<F:/MedQC-worktrees/qc-integration-20261008/docs/acceptance/engine-audit-20261008/next-batch/coverage-progress-current/overlay.json>) /rules/74

### LX0609-11-01-01

- 范围说明：{'authority': '冻结T0台账及1958ae3bb历史overlay范围继承；本轮未实时重查注册器/执行范围', 'phase_status': 'phase_1_target', 'release_scope': 'default', 'customer_excluded': True, 'default_executes': False, 'existing_evidence_limits': '本轮未验证真实同意书/紧急授权例外、多手术逐事件临床正确率，合成门禁通过不代表上线批准。'}
- 问题ID：无规则专属未闭问题
- 附加待办：既有证据有限，不是整规则/真实医学通过；共通正式链缺口另列；本轮未执行测试/模型/注册器；customer_excluded；原组报告default已被冻结范围取代；本轮D仅继承范围约束，不支持医学合格
- 证据：[rescue-remaining.json](<F:/MedQC-worktrees/qc-integration-20261008/docs/acceptance/engine-audit-20261008/rescue-remaining.json>) /rules/3；[overlay.json](<F:/MedQC-worktrees/qc-integration-20261008/docs/acceptance/engine-audit-20261008/next-batch/coverage-progress-current/overlay.json>) /rules/32

### LX0609-11-02-01

- 范围说明：{'authority': '冻结T0台账及1958ae3bb历史overlay范围继承；本轮未实时重查注册器/执行范围', 'phase_status': 'phase_1_target', 'release_scope': 'default', 'customer_excluded': True, 'default_executes': False, 'existing_evidence_limits': '当前只证明受控来源和类型判定；紧急授权例外、同次住院多次麻醉对应关系缺独立真实证据。'}
- 问题ID：无规则专属未闭问题
- 附加待办：既有证据有限，不是整规则/真实医学通过；共通正式链缺口另列；本轮未执行测试/模型/注册器；customer_excluded；原组报告default已被冻结范围取代；本轮D仅继承范围约束，不支持医学合格
- 证据：[rescue-remaining.json](<F:/MedQC-worktrees/qc-integration-20261008/docs/acceptance/engine-audit-20261008/rescue-remaining.json>) /rules/4；[overlay.json](<F:/MedQC-worktrees/qc-integration-20261008/docs/acceptance/engine-audit-20261008/next-batch/coverage-progress-current/overlay.json>) /rules/33

### LX0609-11-02-02

- 范围说明：{'authority': '冻结T0台账及1958ae3bb历史overlay范围继承；本轮未实时重查注册器/执行范围', 'phase_status': 'phase_1_target', 'release_scope': 'default', 'customer_excluded': True, 'default_executes': False, 'existing_evidence_limits': '合法代理人签署等授权语义、实际病例和多事件未临床确认。'}
- 问题ID：无规则专属未闭问题
- 附加待办：既有证据有限，不是整规则/真实医学通过；共通正式链缺口另列；本轮未执行测试/模型/注册器；customer_excluded；原组报告default已被冻结范围取代；本轮D仅继承范围约束，不支持医学合格
- 证据：[rescue-remaining.json](<F:/MedQC-worktrees/qc-integration-20261008/docs/acceptance/engine-audit-20261008/rescue-remaining.json>) /rules/5；[overlay.json](<F:/MedQC-worktrees/qc-integration-20261008/docs/acceptance/engine-audit-20261008/next-batch/coverage-progress-current/overlay.json>) /rules/34

### LX0609-11-03-01

- 范围说明：{'authority': '冻结T0台账及1958ae3bb历史overlay范围继承；本轮未实时重查注册器/执行范围', 'phase_status': 'phase_1_target', 'release_scope': 'default', 'customer_excluded': True, 'default_executes': False, 'existing_evidence_limits': '只读10月7脱敏门控修复报告；未重验真实输血、授权例外或保存/API/浏览器。'}
- 问题ID：无规则专属未闭问题
- 附加待办：既有证据有限，不是整规则/真实医学通过；共通正式链缺口另列；本轮未执行测试/模型/注册器；customer_excluded；原组报告default已被冻结范围取代；本轮D仅继承范围约束，不支持医学合格
- 证据：[rescue-remaining.json](<F:/MedQC-worktrees/qc-integration-20261008/docs/acceptance/engine-audit-20261008/rescue-remaining.json>) /rules/6；[overlay.json](<F:/MedQC-worktrees/qc-integration-20261008/docs/acceptance/engine-audit-20261008/next-batch/coverage-progress-current/overlay.json>) /rules/40

### LX0609-11-03-02

- 范围说明：{'authority': '冻结T0台账及1958ae3bb历史overlay范围继承；本轮未实时重查注册器/执行范围', 'phase_status': 'phase_1_target', 'release_scope': 'default', 'customer_excluded': True, 'default_executes': False, 'existing_evidence_limits': '本轮未形成合法代理人、否定/复杂书写及多次输血同意关系真实金标。'}
- 问题ID：无规则专属未闭问题
- 附加待办：既有证据有限，不是整规则/真实医学通过；共通正式链缺口另列；本轮未执行测试/模型/注册器；customer_excluded；原组报告default已被冻结范围取代；本轮D仅继承范围约束，不支持医学合格
- 证据：[rescue-remaining.json](<F:/MedQC-worktrees/qc-integration-20261008/docs/acceptance/engine-audit-20261008/rescue-remaining.json>) /rules/7；[overlay.json](<F:/MedQC-worktrees/qc-integration-20261008/docs/acceptance/engine-audit-20261008/next-batch/coverage-progress-current/overlay.json>) /rules/41

### LX0609-12-01-01

- 范围说明：{'authority': '冻结T0台账及1958ae3bb历史overlay范围继承；本轮未实时重查注册器/执行范围', 'phase_status': 'phase_1_target', 'release_scope': 'default', 'customer_excluded': False, 'default_executes': True, 'existing_evidence_limits': '生产正文/结构化段映射真实覆盖及临床对复制业务答案未确认。'}
- 问题ID：无规则专属未闭问题
- 附加待办：既有证据有限，不是整规则/真实医学通过；共通正式链缺口另列；本轮未执行测试/模型/注册器
- 证据：[rescue-remaining.json](<F:/MedQC-worktrees/qc-integration-20261008/docs/acceptance/engine-audit-20261008/rescue-remaining.json>) /rules/1；[overlay.json](<F:/MedQC-worktrees/qc-integration-20261008/docs/acceptance/engine-audit-20261008/next-batch/coverage-progress-current/overlay.json>) /rules/15

### LX0609-12-01-02

- 范围说明：{'authority': '冻结T0台账及1958ae3bb历史overlay范围继承；本轮未实时重查注册器/执行范围', 'phase_status': 'phase_1_target', 'release_scope': 'default', 'customer_excluded': False, 'default_executes': True, 'existing_evidence_limits': '门槛≥70%按现行业务基线，旧标题“大于70%”不能作为新反例；缺独立真实高/低相似及模板金标。'}
- 问题ID：C-GAP-CONTRACT
- 附加待办：既有证据有限，不是整规则/真实医学通过；共通正式链缺口另列；本轮未执行测试/模型/注册器；历史有限修复：C-GAP-CONTRACT
- 证据：[rescue-remaining.json](<F:/MedQC-worktrees/qc-integration-20261008/docs/acceptance/engine-audit-20261008/rescue-remaining.json>) /rules/2；[overlay.json](<F:/MedQC-worktrees/qc-integration-20261008/docs/acceptance/engine-audit-20261008/next-batch/coverage-progress-current/overlay.json>) /rules/16

### LX0609-12-02-01

- 范围说明：{'authority': '冻结T0台账及1958ae3bb历史overlay范围继承；本轮未实时重查注册器/执行范围', 'phase_status': 'phase_1_target', 'release_scope': 'default', 'customer_excluded': False, 'default_executes': True, 'existing_evidence_limits': '当前只确认权限/计量合同漂移，不推断真实模型稳定性；结构化声明兼容路径及真实正文未新增审查。'}
- 问题ID：PROMPT-074；rescue-remaining:RR-M01
- 附加待办：既有证据有限，不是整规则/真实医学通过；共通正式链缺口另列；本轮未执行测试/模型/注册器；后续已闭：rescue-remaining:RR-M01
- 证据：[rescue-remaining.json](<F:/MedQC-worktrees/qc-integration-20261008/docs/acceptance/engine-audit-20261008/rescue-remaining.json>) /rules/12；[overlay.json](<F:/MedQC-worktrees/qc-integration-20261008/docs/acceptance/engine-audit-20261008/next-batch/coverage-progress-current/overlay.json>) /rules/73；[closure-issues.json](<F:/MedQC-worktrees/qc-integration-20261008/docs/acceptance/engine-audit-20261008/closure-issues.json>) /issues/8；[closure-issues.json](<F:/MedQC-worktrees/qc-integration-20261008/docs/acceptance/engine-audit-20261008/closure-issues.json>) /issues/23

## 排除的6条

仅范围/目录核对，不进入本表80条：LX0609-05-01-01、LX0609-05-01-04、LX0609-05-03-01、LX0609-06-03-01、LX0609-07-04-02、LX0609-08-01-05。

原始台账不覆盖；输入及分片SHA256、每条历史范围字段与证据见同名JSON。
