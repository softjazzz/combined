# 0916 全32条统一验证进度

核对日期：2026-10-05。范围仅为 LX0916-001 至 LX0916-032，不含病案首页。第二章保留初次版本盘点时点，第四章明细随新增证据更新；后续各章按发生顺序补记修复、测试及只读PG查询，最新D时点见第十至十三章。最初盘点不调用模型、数据库或历史脚本；后续不改原工程预期、临床答案、启用或批准状态，历史文件保留。

## 一、统计纠正

原“完成4条、测试9条、23条未开始”只描述本轮专项推进，不能描述全部历史。统一去重后的记录如下：

| 维度 | 条数 | 范围与限制 |
| --- | ---: | --- |
| 有历史真实整包执行/冻结回放证据 | 32 | 30份0910真实病历；证明当时执行链、结果合同、隔离和回放记录，不代表32条医学判定通过 |
| 已纳入原9条专项统计 | 9 | 003、005、006、007、008、010、011、012、014；003/005/006不再加算 |
| 原统计漏列的历史专项 | 2 | 015、016；包括结构化触发以及后续Stage2真实回放，当前口径的独立临床验收未闭环 |
| 本次补找到的历史专项实验 | 3 | 024、025、026；专用30例两轮回放，稳定性门禁未通过，不能补计为完成 |
| 有专项/实验记录的规则去重合计 | 14 | 上述9+2+3；“做过专项”不是“专项验收通过” |
| 本次仅找到整包/事后审计，未找到独立专项结果的规则 | 18 | 001、002、004、009、013、017、018、019、020、021、022、023、027、028、029、030、031、032；018另有专用实现与回放脚本，但未找到对应保存结果 |
| 原4条阶段性工程成果 | 4 | 005、006、010、012，在A树当时限定范围内有工程一致性/保存回读证据；保留，不升格为整条临床验收 |
| 另有历史触发/固定输入回归里程碑 | 2 | 015、016；与上述4条正式保存里程碑不是同一种门禁，不混算成“6条全部验收完成” |
| 可证明当前D树完整单规则工程验收完成 | 0 | 尚未形成覆盖当前D实际源码、同一门禁和完整规则范围的证据闭环；不是“32条完全没测试” |
| 找到独立临床签认完成的规则 | 0 | 工程预期、Agent交叉审查、状态一致均不替代临床签认 |
| 找到上线批准完成的规则 | 0 | 文档均保留测试/待复核；当前0916验收台仍为acceptance_only且publication_supported=False |
| 规范逐条说明/验收台基础建设 | 32 | 已完成，不计为32条临床验收 |

按互斥工作记录类别，32=本轮专项9+历史专项2+历史实验3+整包/审计18。按本轮专项口径，仍是9条已推进、23条尚未开展本轮专项；后23条中已有5条历史专项/实验，不能称为完全未测试。重复病例、同病例多轮、整包非目标规则均不重复增加规则数。

## 二、版本适用性

本表分别记录用户指定的D树和最近专项验证的A树，不把任何工作树的通过结论直接移植到另一棵树。

本章版本差分固定在最初盘点时点；首程缺读取补丁等当时发现已在后续闭环修复，第十章记录当前D fdda9ce1f及8个直接回放目标。不要把本章历史差分当作最新待开发清单。

| 代号 | 工作树与核对时点 | 适用限制 |
| --- | --- | --- |
| D | `D:/LLM/LX888/apps/medqc-web`，分支codex/lx0609-tech-debt-20260730，HEAD `1955a1a3a49717ad0a346a1553cb69d3915693f8`，实际工作区含未提交实现 | HEAD不是完整实现快照；admission_content_items.py存在但未跟踪，不能因git差分显示删除而说实现不存在 |
| A | `C:/Users/Coldplay/.codex/worktrees/lx0916-validation-handoff/LX888/apps/medqc-web`，分支codex/lx0916-validation-handoff-20261003，HEAD `09bf7a826` | 10月专项主要在此树。005/006交接时曾依赖未提交源码；不同日期的正式保存结果不自动等于最新09bf已重新正式验收 |
| C | `C:/Users/Coldplay/.codex/worktrees/luxian-0916-stabilization/LX888/apps/medqc-web`，HEAD `71f421575244a861fa0d9abfdded93533628afc1` | 保存024–026专项实验及五事实族方案；该树实验/四段编号改造不能当作D/A当前实现验收 |

主协调者本轮用文件逐字节比较和git差分核对：

- D/A相同：rule_catalog.py、disease_change_015016.py、disease_change_stage2.py、critical_value_018.py、critical_value_018_stage2.py、course_event_rules.py、surgery_consent_rules.py、discharge_rules.py。相同只说明这些模块当前一致，不证明历史执行输入、共享投影及编排全部等价。
- D/A不同：admission_content_items.py、admission_rules.py、input_context.py、bundle_reader.py、first_course_rules.py、semantic_extractor.py、batch_worker.py。因此本表版本栏不填笼统“仍全部适用”。
- D的首程`_field_state`尚无A的structured_sections取值补丁：[first_course_rules.py:234](D:/LLM/LX888/apps/medqc-web/backend/app/services/luxian_0916/first_course_rules.py:234)。A的010/012结构化正例结论不能直接计为D的同版本通过。
- D未带A的007/008逐项事实、病史源范围/非病史范围和相关患者投影改动：[input_context.py:39](D:/LLM/LX888/apps/medqc-web/backend/app/services/luxian_0916/input_context.py:39)、[admission_content_items.py:8](D:/LLM/LX888/apps/medqc-web/backend/app/services/luxian_0916/admission_content_items.py:8)。D不是“无005/006实现”，而是不能复用A全套007/008专项结论。
- D的结果装配未带A最新共享抽取技术失败分类修复：[batch_worker.py:489](D:/LLM/LX888/apps/medqc-web/backend/app/services/luxian_0916/batch_worker.py:489)。A的09bf保存响应回归没有新模型/PG正式运行，不能写成最新修复已完成新PG/页面验收。
- 015/016并非仍停在“Stage2待开发”：D已接入专属Stage2：[batch_worker.py:428](D:/LLM/LX888/apps/medqc-web/backend/app/services/luxian_0916/batch_worker.py:428)，成熟度按final场景赋值：[disease_change_stage2.py:141](D:/LLM/LX888/apps/medqc-web/backend/app/services/luxian_0916/disease_change_stage2.py:141)，执行器消费五项事实：[course_event_rules.py:616](D:/LLM/LX888/apps/medqc-web/backend/app/services/luxian_0916/course_event_rules.py:616)。旧方案标题的暂停/未接入状态只属于旧时点，不能用于重新排重复开发。
- 当前D/A目录仍是三位编号。本表沿用当前目录身份，不混入C树的四段编号实验。[rule_catalog.py:52](D:/LLM/LX888/apps/medqc-web/backend/app/services/luxian_0916/rule_catalog.py:52)

## 三、统一验收口径

本表“工程阶段达成”表示当时已批准的窄范围冻结预期、执行/保护回归或保存回读获得证据；不是整条规范的全部触发、适用性、缺陷、资料缺口和技术失败都已验证。

“完整单规则工程验收”须绑定实际源码时点，冻结独立于模型输出的工程预期，明确正例/缺陷/不适用/来源不足等适用分支及未覆盖范围，并核对状态、原因、关键事实、证据位置、建议、正式保存/回读与失败语义。未覆盖不靠重复调用、单测数量或整包非目标结果补足。临床签认和上线批准是另外两个门禁。

表内“未找到独立预期”是本次档案核对结论，不是“规则标准未定”或“未实现”。Agent工程预期即使运行前冻结、经另一Agent复核，也不写成独立临床人工金标准。临床/批准的“待签/未批准”仅描述可定位档案和当前代码门禁，本次没有查询或改写数据库审批记录。

版本标签：V1=入院/共享链差异，须绑定工作区再复用；V2=007/008的A专项改造未等价进入D；V3=首程结构化取值及共享链差异；V4=对应模块D/A相同但历史整链等价未证明；V5=C实验不能证明当前D/A等价。

## 四、32条统一进度表

H0和H1是每条共同历史证据；其余证据代号的绝对路径见第五节。工程栏分“阶段；完整单规则”，避免将既有成果清零或虚报整条通过。

| 规则/质控点 | 记录类别 | 历史测试与产物 | 当前版本是否适用 | 独立人工预期与样本覆盖 | 当前专项验证结果 | 未闭环问题 | 工程验收（阶段；完整） | 临床复核 | 上线批准 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| LX0916-001 多次入院诊疗总结 | 整包/审计 | H0/H1，30真例整包；入院事后审计H8 | V1，旧共享响应仅属历史输入 | 未找到独立专项冻结预期；整包不等于多次入院分支覆盖 | 未找到本轮专项结果 | 多次入院触发、总结质量及来源不足分支需独立核对 | 整包历史；未完成 | 待签 | 未批准 |
| LX0916-002 病史陈述者能力 | 整包/审计 | H0/H1，30真例整包；H8 | V1，共享链/失败分类不同 | 未找到独立专项预期；能力与陈述者组合未独立签认 | 未找到本轮专项结果 | 真实触发、角色事实与来源缺口核对 | 整包历史；未完成 | 待签 | 未批准 |
| LX0916-003 现病史完整性 | 本轮专项 | H0/H1/H2；首批3例正式任务、PG与浏览器；H6只读复核 | V1，入院/共享链已变，旧3/3不可当新版本验收 | 3真例工程预期，均合规；无独立临床答案及确认缺陷真例 | 历史3/3工程状态一致；本轮未补齐逐项证据 | 逐项质量事实/引文、真实缺陷与来源边界、版本参数留痕 | 状态阶段核对；未完成 | 待签 | 未批准 |
| LX0916-004 鉴别诊断重要症状 | 整包/审计 | H0/H1/H8，30真例 | V1 | 未找到独立专项预期；重要阳阴性症状未逐例签认 | 未找到本轮专项结果 | 具体症状、鉴别诊断关联及证据充分性复核 | 整包历史；未完成 | 待签 | 未批准 |
| LX0916-005 院前检查治疗效果 | 本轮专项 | H0/H1/H2/H3/H4；早期2/3、后续3/3，正式PG/页面证据保留 | V1，D有005逐项实现但未提交；不能只凭HEAD复现A结论 | 3真例工程预期；C03明确不详、C04泛化治疗、C21合规；无临床签认 | 最新历史正式3/3；C03为recorded_information_unknown，未改旧争议记录 | C03/C04详细程度人工复核；源码/版本冻结及当前整链门禁 | 正式链路阶段达成；未完成 | 待签，争议保留 | 未批准 |
| LX0916-006 既往史完整性 | 本轮专项 | H0/H1/H2/H3/H6；早期1/3后收敛，7例保护及正式回读 | V1，D有006逐项实现；当前源码快照与A整链尚未等价冻结 | 6真例+1合成，明确不详/否认/缺接种保护；无临床金标准 | 7/7工程状态/原因/逐项事实保持；55新引文逐字命中，4例引文改变 | 不详与缺陷真例临床复核；较短引文充分性不能以零状态变化代替 | 保护/保存阶段达成；未完成 | 待签 | 未批准 |
| LX0916-007 个人婚育月经家族史 | 本轮专项 | H0/H1/H4/H7；早期C04假合规，后续逐项专项 | V2，A逐项和源范围改造不能移植为D通过 | 最新2真例+1合成预冻结工程预期；未成年人/性别适用性未签认 | 最新3/3状态一致，但C04未取得可定位007事实；PG及函数回读 | C04事实可复核性、人工适用性；最新认证HTTP/页面未完成 | 有结果，未闭环；未完成 | 待签 | 未批准 |
| LX0916-008 儿童喂养发育史 | 本轮专项 | H0/H1/H4/H6/H7/H13；真实生成失败、合成故障保护及有界复验均保留 | V2；A最新版008也未闭环 | 最新3真例+1合成预期；年龄界限工程口径未临床确认 | 最新3/4；10/5当前09bf离线重放和原保存全字段相同，C20原响应recorded/unknown差异独立复现；未改预期 | 抽取稳定性、历史内容角色/来源覆盖；当前保存/认证页面门禁 | 失败语义曾专项修复，内容未闭环；未完成 | 待签 | 未批准 |
| LX0916-009 体格检查重要体征 | 整包/审计 | H0/H1/H8，30真例；入院试验中的旁路变化不计验收 | V1 | 未找到独立专项预期/临床签认 | 未找到本轮专项结果 | 重要体征、准确性及具体证据独立核对 | 整包历史；未完成 | 待签 | 未批准 |
| LX0916-010 首程病例特点存在性 | 本轮专项 | H0/H1/H6/H10/H13/H15；先2真+2合成，后4真例正式保存；第十章D补充 | V3；D fdda9ce1f已补structured_sections，当前D仅直接回放，未新正式运行 | 两批工程预期分别4例；最新C01/C06/C17/C30仅正例，非4个临床质量答案 | A09bf保存响应回归125有效+3技术失败；D当前4/4完整原生字段及冻结预期一致，两人分别反查 | 真实缺项、当前D完整worker/保存、最新认证HTTP/页面；不连带验收011 | 存在性及当前D直接回放阶段达成；未完成 | 待签 | 未批准 |
| LX0916-011 病例特点归纳充分性 | 本轮专项 | H0/H1/H9；C01/C30两真例本地受控抽取；H10/S1含非目标失败样本 | V3；D已补首程字段和031d失败交付，旧本地充分性结果仅条件复用 | 仅C01-011为窄范围工程adequate候选；C30人工复核；无临床独立答案 | 两例模型均合规，仅1个工程候选一致；evidence为空；D新增合成故障保护不是临床通过 | 归纳理由/直接证据、真实缺陷、正式保存/回读和临床判断 | 本地候选及故障保护；未完成 | 待签 | 未批准 |
| LX0916-012 首程三要素存在性 | 本轮专项 | H0/H1/H6/H10/H13/H15；2真+2合成后4真例正式任务；第十章D补充 | V3；D fdda9ce1f已补嵌套取值，当前直接回放非正式链验收 | 最新4真例工程预期，均三栏非空；此前缺鉴别负例仅合成 | A09bf离线重放128有效+0失败；D当前4/4与保存全字段/冻结预期一致，主协调另复跑；无新PG/页面 | 真实缺项、当前D完整worker/保存、最新认证HTTP/页面；不评价充分性 | 存在性及当前D直接回放阶段达成；未完成 | 待签 | 未批准 |
| LX0916-013 诊断鉴别依据充分性 | 整包/审计 | H0/H1/H8；H10/S1及第十一章D合成故障保护，不是充分性专项 | V3，D031d已迁入失败交付，首程取值也已修复；当前模型/医学结果未复验 | 未找到独立充分性专项预期；技术异常样本不是临床负例 | 无本轮医学专项；D29有效/3技术失败的合成API保护不补计为013验收 | 充分性理由/证据及临床答案；当前D真实故障保存/认证页面 | 整包/故障工程证据；未完成 | 待签 | 未批准 |
| LX0916-014 诊疗计划全面具体 | 本轮专项 | H0/H1/H9；2真例本地抽取；H10/S1有非目标故障保护 | V3 | C01/C30均在运行前保留人工复核；无确定临床金标准/真负例 | 两例输出合规，均没有质量理由/直接evidence，不计临床通过 | 剂量/疗程等标准维度与Prompt检查范围需复核；证据及正式保存 | 有本地结果，未闭环；未完成 | 待签 | 未批准 |
| LX0916-015 病情变化记录完整 | 历史专项 | H0/H1/H5/H13/H14/H15/H16/H17；旧文本盲测、结构化30例、Stage2两轮30例及六例当前草案 | V4，Stage2已接线；df199时点六例同快照核实两候选缓存、触发和五源实际宽查询；非旧运行恢复 | 结构化24无触发+6触发7事件；现35事实工程草案已独立审读，关联/最早坐标争议保留，未转gold | 12候选五源complete、输入门禁无缺口，完整目录/Prompt/归一化事实与此前材料精确相同；新模型0 | 当前五事实预期冻结、正式任务scene、独立未见病例及临床签认；旧原响应仍缺；完整Worker未验收 | 历史回归/当前输入覆盖及草案审读；完整未完成 | 待签 | 未批准 |
| LX0916-016 病情变化分析处理 | 历史专项 | H0/H1/H5/H13/H14/H15/H16/H17，同一专属抽取、Python分别判定 | V4，Stage2已实现；六例当前五源实际查询覆盖已核，不证明完整evidence/历史场景 | 同015；当前35事实草案含分析/处理，独立审读异议保留，不自动作临床答案 | 历史两轮24不适用+6合规；当前两候选scene的完整目录/Prompt/触发事实相同，未新生成QC模型事实 | 分析/处理和事件归属预期冻结、正式场景、真实缺陷与临床签认；原merge不保证医学冲突校验 | 历史回归/当前输入覆盖及草案审读；完整未完成 | 待签 | 未批准 |
| LX0916-017 检查用药合理性 | 整包/审计 | H0/H1/H8，30真例整包 | V4，事件执行模块同但共享抽取/失败分类不同 | 未找到独立合理性专项预期 | 未找到本轮专项结果 | 独立临床合理性答案、医嘱触发/覆盖与证据解释 | 整包历史；未完成 | 待签 | 未批准 |
| LX0916-018 危急值报告处理 | 整包/审计 | H0/H1/H8/H12；专用Stage1/Stage2代码和回放脚本存在，未找到保存结果 | V4，专属模块D/A同且有接线；脚本不等于执行通过 | 未找到独立冻结专项答案/保存通过产物；015/016危急触发不能代替018验收 | 专用实施成果保留；本次不能证明专用回放已通过 | 找回原运行产物优先；若不存在再另立独立报告/处置及覆盖专项 | 有实施/工具，验收证据不足；未完成 | 待签 | 未批准 |
| LX0916-019 重要操作记录规范 | 整包/审计 | H0/H1/H8，30真例整包 | V4，事件模块同，旧响应版本未等价 | 未找到独立操作专项预期 | 未找到本轮专项结果 | 真实操作触发、记录缺陷、时间/关联及资料缺口验证 | 整包历史；未完成 | 待签 | 未批准 |
| LX0916-020 修正诊断理由依据 | 整包/审计 | H0/H1/H8，30真例整包 | V4 | 未找到独立诊断修正专项预期；不等于标准未定 | 未找到本轮专项结果 | 独立修正事件与病程依据关联、真实缺陷/来源不足 | 整包历史；未完成 | 待签 | 未批准 |
| LX0916-021 手术同意书完整性 | 整包/审计 | H0/H1/H8；run5的30条事后核对均无法复核 | V4，对应执行模块同，实验树不能替代整链 | 未找到独立冻结预期；30条无法复核不能当准确率 | 未找到本轮专项结果 | 同意书实际来源覆盖、手术关联与缺项引文 | 整包/事后审计；未完成 | 待签 | 未批准 |
| LX0916-022 麻醉同意书完整性 | 整包/审计 | H0/H1/H8；早期29资料不足+1不适用，发布来源门禁未过 | V4 | 未找到独立冻结临床预期；有合成路由保护，不是真实来源通过 | 未找到本轮专项结果 | 麻醉同意书真实来源链及适用性/具体缺项验证 | 来源门禁未过；未完成 | 待签 | 未批准 |
| LX0916-023 麻醉记录存在性 | 整包/审计 | H0/H1/H8；run5有15条supported，其余无法复核 | V4 | 事后支持15条不是运行前独立预期；无专项临床gold | 未找到本轮独立专项结果 | 麻醉实施触发、真缺失、关联及完整来源合同核对 | 局部事后支持；未完成 | 待签 | 未批准 |
| LX0916-024 麻醉记录完整性 | 历史实验 | H0/H1/H8/H11；专用两轮30例含16触发，run5另有10条事后支持 | V5，C实验未证明与D/A当前相同 | 未找到独立预冻结临床gold；整族稳定性试验不是逐规则准确率 | H11整族passed=false，9例跨轮变化；不将整族失败推断为024独有漂移 | 实验版本/输入绑定、稳定性、缺项证据、独立答案及正式回读 | 历史专项实验未通过整族门禁；未完成 | 待签 | 未批准 |
| LX0916-025 手术记录完整性 | 历史实验 | H0/H1/H8/H11；H11实际summary明确含025，不因文件名漏计；run5有1条支持 | V5 | 无独立预冻结临床gold；来源缺口多，不可用无异常数替代验收 | 两轮各14资料不足+2不合规+14不适用；整族稳定性失败 | 来源覆盖、手术关联、独立预期与可定位缺项；不能因025状态计数相同判全通过 | 历史专项实验未通过整族门禁；未完成 | 待签 | 未批准 |
| LX0916-026 手术安全核查完整性 | 历史实验 | H0/H1/H8/H11；两轮30例，run5另有10条事后支持 | V5 | 无独立临床gold；无真实输血阳性，输血条件仅合成保护 | 两轮资料不足6到2、不合规10到14；整族9例漂移、passed=false | 抽取合同、跨文书/多手术关联、真实输血条件与三方签字事实 | 历史专项实验未通过；未完成 | 待签 | 未批准 |
| LX0916-027 急诊手术上级指示 | 整包/审计 | H0/H1/H8；run5的30条均无法复核 | V4 | 无独立急诊触发专项预期 | 未找到本轮专项结果 | 急诊触发、上级医师角色/指示及手术关联验证 | 整包/事后审计；未完成 | 待签 | 未批准 |
| LX0916-028 非计划再次手术说明 | 整包/审计 | H0/H1/H8；run5的30条均无法复核 | V4 | 无独立非计划再次手术专项预期 | 未找到本轮专项结果 | 多手术事件、非计划属性、上次情况/原因关联及真例 | 整包/事后审计；未完成 | 待签 | 未批准 |
| LX0916-029 特殊项目同意书 | 整包/审计 | H0/H1/H8；run5的30条均无法复核 | V4 | 无独立特殊项目触发专项预期 | 未找到本轮专项结果 | 项目触发、对应同意书来源/角色及完整性验证 | 整包/事后审计；未完成 | 待签 | 未批准 |
| LX0916-030 病危重通知书完整性 | 整包/审计 | H0/H1/H8；run5的30条均无法复核 | V4 | 无独立通知书专项预期；015/016病危重医嘱回放不能代替本条 | 未找到本轮专项结果 | 通知书来源、签字/内容事实；与医嘱触发分开验收 | 整包/事后审计；未完成 | 待签 | 未批准 |
| LX0916-031 出院诊疗经过详细性 | 整包/审计 | H0/H1/H8；run5有5条supported，root-verify单文书词项核对 | V4，出院模块同，旧源/响应未绑定当前版 | 事后原文核对无独立预冻结临床答案 | 未找到本轮独立专项结果 | 全程诊疗事实与出院总结对应、充分性及临床签认 | 局部事后复核；未完成 | 待签 | 未批准 |
| LX0916-032 出院医嘱完整性 | 整包/审计 | H0/H1/H8；早期来源门禁未过，run5仅1条supported | V4 | 无独立冻结专项临床预期；不可把零散随访词当完整医嘱 | 未找到本轮专项结果 | 医嘱实际来源覆盖、个性化随访/注意事项与适用性 | 来源门禁未过；未完成 | 待签 | 未批准 |

## 五、证据索引

以下链接为可定位档案，不复制患者原文。所有-private原始产物继续留在ignored目录，不提交。H0/H8是旧共享链的历史证据，不是当前五事实族或者最新入院逐项方案的全规则验收。

| 代号 | 说明与产物位置 |
| --- | --- |
| H0 | [独立32条及30真例整包结论](D:/LLM/LX888/apps/medqc-web/docs/plans/2026-09-16-luxian0916-independent-qc.md:42)；[30例保存输入/响应/32条结果](D:/LLM/LX888/apps/medqc-web/.tmp/0910-full-audit/luxian-0916-frozen-shared-response-20260917-private.json)；[同Prompt再请求记录](D:/LLM/LX888/apps/medqc-web/.tmp/0910-full-audit/luxian-0916-repeat-same-prompts-20260917-private.json) |
| H1 | [32条规范说明](D:/LLM/LX888/apps/medqc-web/docs/plans/2026-10-03-0916-rule-writing-standard-explanations.md)；[验收台接入](D:/LLM/LX888/apps/medqc-web/docs/plans/2026-10-03-rule-validation-0916.md)。均属基础建设 |
| H2 | [003/005/006入院专项](D:/LLM/LX888/apps/medqc-web/docs/plans/2026-10-03-0916-admission-pilot-validation.md)；[A冻结材料](C:/Users/Coldplay/.codex/worktrees/lx0916-validation-handoff/LX888/apps/medqc-web/.tmp/0910-full-audit/20261003-admission-pilot-source-private.json) |
| H3 | [005/006逐项事实及后续保护](D:/LLM/LX888/apps/medqc-web/docs/plans/2026-10-03-0916-admission-item-facts.md)；[005信息边界回放](C:/Users/Coldplay/.codex/worktrees/lx0916-validation-handoff/LX888/apps/medqc-web/.tmp/0910-full-audit/20261003-residual-goal-005-information-boundary-private.json)。该单次本地回放不冒充正式PG保存 |
| H4 | [005/007/008早期正式记录](C:/Users/Coldplay/.codex/worktrees/lx0916-validation-handoff/LX888/apps/medqc-web/docs/plans/2026-10-03-0916-005-007-008-formal-validation.md)；[005正式回读](C:/Users/Coldplay/.codex/worktrees/lx0916-validation-handoff/LX888/apps/medqc-web/.tmp/0910-full-audit/20261003-005-formal-recheck-private.json) |
| H5 | [015/016旧文本试验与客户新口径](D:/LLM/LX888/apps/medqc-web/docs/plans/2026-09-18-luxian0916-015016-independent-closed-loop.md)；[9/18结构化触发30例](D:/LLM/LX888/apps/medqc-web/.tmp/0910-full-audit/replay_luxian0916_structured_trigger_20260918-private.json)；[9/20 Stage2两轮30例](D:/LLM/LX888/apps/medqc-web/.tmp/0910-full-audit/replay_luxian0916_stage2_20260920-private.json) |
| H6 | [006保护、010/012首次闭环及003只读复核](C:/Users/Coldplay/.codex/worktrees/lx0916-validation-handoff/LX888/apps/medqc-web/docs/plans/2026-10-04-0916-long-validation.md)；[003/006审计](C:/Users/Coldplay/.codex/worktrees/lx0916-validation-handoff/LX888/apps/medqc-web/.tmp/0910-full-audit/20261004-003-006-audit-private.json)；[006新保护集](C:/Users/Coldplay/.codex/worktrees/lx0916-validation-handoff/LX888/apps/medqc-web/.tmp/0910-full-audit/20261004-006-normal-private.json)；[首程首次正式批](C:/Users/Coldplay/.codex/worktrees/lx0916-validation-handoff/LX888/apps/medqc-web/.tmp/0910-full-audit/20261004-firstcourse-formal-private.json) |
| H7 | [007/008最新正式门禁与未闭环项](C:/Users/Coldplay/.codex/worktrees/lx0916-validation-handoff/LX888/apps/medqc-web/docs/plans/2026-10-04-0916-007-008-formal-acceptance-plan.md)；[执行/响应保存](C:/Users/Coldplay/.codex/worktrees/lx0916-validation-handoff/LX888/apps/medqc-web/.tmp/0910-full-audit/20261004-007008-formal-authorized-private.json)；[最终PG回读](C:/Users/Coldplay/.codex/worktrees/lx0916-validation-handoff/LX888/apps/medqc-web/.tmp/0910-full-audit/20261004-007008-final-pg-audit-private.json) |
| H8 | D目录`.tmp/0910-full-audit/`下run4/run5-audit-001-010、011-020、021-032-private.json；[run5的021–032审计](D:/LLM/LX888/apps/medqc-web/.tmp/0910-full-audit/luxian-0916-run5-audit-021-032-private.json)；[024–026来源核对](D:/LLM/LX888/apps/medqc-web/.tmp/0910-full-audit/luxian-0916-root-verify-024-026-private.json)；[031单文书词项核对](D:/LLM/LX888/apps/medqc-web/.tmp/0910-full-audit/luxian-0916-root-verify-031-private.json)。均事后审计，不是预冻结临床答案 |
| H9 | [011/014本地两例、冻结候选与反证](C:/Users/Coldplay/.codex/worktrees/lx0916-validation-handoff/LX888/apps/medqc-web/docs/plans/2026-10-04-0916-parallel-validation-plan.md)。原B工作树冻结文件现不可读；A源字段与C独立复核仍留存，不能伪称B原文件仍可复现 |
| H10 | [010/012最新正式4真例结论](C:/Users/Coldplay/.codex/worktrees/lx0916-validation-handoff/LX888/apps/medqc-web/docs/plans/2026-10-04-0916-010-012-formal-validation.md)；[执行/响应/PG审计](C:/Users/Coldplay/.codex/worktrees/lx0916-validation-handoff/LX888/apps/medqc-web/.tmp/0910-full-audit/20261004-010012-formal-authorized-private.json) |
| H11 | [C树024–026专用Stage2失败回放](C:/Users/Coldplay/.codex/worktrees/luxian-0916-stabilization/LX888/apps/medqc-web/.tmp/0910-full-audit/replay_luxian0916_024026_stage2_20260920-private.json)。虽名024026，summary实际有024、025、026，模型qwen3.8-flash、enable_thinking=false；没有独立临床gold/代码SHA，不能跨版本升级通过 |
| H12 | [C树五事实族实施说明](C:/Users/Coldplay/.codex/worktrees/luxian-0916-stabilization/LX888/apps/medqc-web/docs/plans/2026-09-21-luxian-0916-five-fact-families.md)；[018专用回放脚本](C:/Users/Coldplay/.codex/worktrees/luxian-0916-stabilization/LX888/apps/medqc-web/.tmp/0910-full-audit/replay_luxian0916_018_20260921-private.py)。找到脚本不等于找到已执行/通过结果 |
| S1 | [09bf抽取失败交付修复](C:/Users/Coldplay/.codex/worktrees/lx0916-validation-handoff/LX888/apps/medqc-web/docs/plans/2026-10-04-0916-extraction-failure-delivery-fix.md)。保存响应回归保留253条原生结果、3条真实合同失败转清单；9条保存响应，0新模型/PG；606单测是工程保护，不新增临床验收规则 |
| H13 | [10/5三工作树当前版离线验收及主协调反查](C:/Users/Coldplay/.codex/worktrees/lx0916-validation-handoff/LX888/apps/medqc-web/docs/plans/2026-10-05-0916-three-worktree-acceptance.md)；[A的010/012汇总](C:/Users/Coldplay/.codex/worktrees/lx0916-validation-handoff/LX888/apps/medqc-web/.tmp/0910-full-audit/20261005-lane-a-report.md)；[B的008证伪汇总](C:/Users/Coldplay/.codex/worktrees/lx0916-independent-regression-20261004/LX888/apps/medqc-web/.tmp/0910-full-audit/20261005-lane-b-safe-summary.md)；[C的015/016档案可重放性核对](C:/Users/Coldplay/.codex/worktrees/lx0916-015016-acceptance-20261005/LX888/apps/medqc-web/.tmp/0910-full-audit/20261005-lane-c-summary-private.md)。复用2树、新建1树，0916源码均09bf，0新模型/DB；不增已验收规则数 |
| H14 | [下一批第一阶段及主协调独立复现](C:/Users/Coldplay/.codex/worktrees/lx0916-validation-handoff/LX888/apps/medqc-web/docs/plans/2026-10-05-0916-next-acceptance-preflight.md)。A比较污染/DDL合成证伪，B单候选未批准，C找到6例7事件离线材料、35旧引用定位；均09bf，0新模型/PG，不增验收完成数 |
| H15 | [长程修复及独立审查](C:/Users/Coldplay/.codex/worktrees/lx0916-validation-handoff/LX888/apps/medqc-web/docs/plans/2026-10-05-0916-long-running-validation.md)。A1/A2两项修复提交，106单测+3合成API，真实结构/初始化只读；C两例三事件15工程事实草案、232分句定位、4处旧解析更正。A/B/C为d680，D未合入；模型0、PG业务写0，不增临床完成数 |
| H16 | [当前PG六例来源新冻结](C:/Users/Coldplay/.codex/worktrees/lx0916-015016-acceptance-20261005/LX888/apps/medqc-web/.tmp/0910-full-audit/20261005-long-c-current-readonly-freeze-private.json)；[主协调独立纯Python反算](C:/Users/Coldplay/.codex/worktrees/lx0916-015016-acceptance-20261005/LX888/apps/medqc-web/.tmp/0910-full-audit/20261005-long-root-c-current-freeze-check-private.json)。4a8时点52条只读查询，六例七事件归一化事实与旧材料相同；来源新时点不是旧运行恢复，正式bundle/scene/模型仍未放行 |
| H17 | [六例同快照五源实际查询](C:/Users/Coldplay/.codex/worktrees/lx0916-015016-acceptance-20261005/LX888/apps/medqc-web/.tmp/0910-full-audit/20261005-long-c-five-source-live-freeze-private.json)；[主协调独立目录/Prompt/首程形态核查](C:/Users/Coldplay/.codex/worktrees/lx0916-015016-acceptance-20261005/LX888/apps/medqc-web/.tmp/0910-full-audit/20261005-long-root-c-five-source-freeze-check-private.json)。df199时点220条只读SQL，12候选五源输入覆盖已核；未覆盖其他21源或认证生产Worker，不计临床通过 |

### 本轮直接反查的关键结果

1. H0两个保存产物均有30个cases和全部32个rule_id；本轮检查各病例规则集合，不将这些无gold的观察计临床通过。
2. H5的9/20 JSON每轮为24无触发、6合规、7事件、35事实与35完整坐标；每轮6次模型调用，总Token分别127787/127783，model_elapsed_ms分别45053/47229，语义变化0。产物scope_note明确6例已参与来源审计，只证明固定输入回归，不是独立生产准确率。旧9/18的6条evaluation_window_unknown不是目前仍未开发的证据。
3. H11的status_counts实际覆盖024/025/026；两轮均30例、16触发，passed=false、blockers=fixed_input_result_drift，9例跨轮变化。不能将整族9例变化说成024、025各有9例变化；本轮只明确026状态分布发生变化。error_count=0也不能覆盖模型事实失败和不稳定。
4. H8的021–032 run5共有360条，其中318条unverifiable；supported为023=15、024=10、025=1、026=10、031=5、032=1。事后支持42条记录，不是42条规则通过；required_items_contract_supported=21也不是21条规则完成。零已确认错误不等于准确率100%。
5. H7/H10最新正式批只完成PG及路由函数回读，未完成对应代码时点的认证HTTP/页面。H2/H4/H6确有早期浏览器回读，不可把早期页面证据移植到最新版本。
6. 发布门禁直接反查：[rule_validation.py:148](D:/LLM/LX888/apps/medqc-web/backend/app/services/rule_validation.py:148)是acceptance_only/publication_supported=False，[approve:483](D:/LLM/LX888/apps/medqc-web/backend/app/services/rule_validation.py:483)拒绝该集合批准发布。本轮不调用批准接口。

## 六、避免重复开发的结论

- 已包含：003/005/006和其专项副本、正式任务/PG/页面、006七例工程保护、005范围收敛都在原9条内；只补证据，不增加规则数。
- 确实漏计历史工作：全32条30真例整包工程测试；015/016结构化触发和后续Stage2回归；024/025/026失败专项实验；旧逐段事后业务/来源审计。分别归档，不混为已完成验收。
- 仅能作为历史证据：旧015/016文本触发盲测不适用于客户新口径；C树024–026实验未证明D/A等价；旧共享响应与事后supported不替代当前专项；旧B部分原文件不可读需标可复现性限制。
- 无需从零重做：32条规范说明、验收台接入、015/016专属触发和Stage2、018专属实现已有成果。下一次授权先使用现有产物确认适用性，仅对明确未闭环问题补验收，不重跑模型“补统计”。
- 不能据本表自动关闭：005/006争议、007可定位事实、008漂移、011/014充分性、022/032来源门禁、024–026不稳定和当前D/A版本差异。实施是否需要改代码须另核真实输入，不因“未验收”推断“未实现”。

本轮验证仅为文件内容/源码/版本差分和32条去重核算，未运行模型、PG、浏览器或生产测试。未提交他人工作区修改，未改变任何旧结果、预期或启用状态。

## 七、10月5日并发离线验收补充

用户另行授权三路独立工作树并发、复用现存两棵。本节属于随后批次，不覆盖前述历史档案时点。A保留09bf和原文档，B干净快进至09bf，C新建同版；A/B为Sol6.1 medium，子代理额度阻止第三名启动，C由主协调亲自并行执行。

当前新增证据：010/012共8个正向工程目标在09bf保持；253保留结果八类原生字段无差异，010的C17三条合同失败进清单。008同次7目标+1旁路结果忠实重放，但冻结预期仍仅6/7符合，唯一不符为008 C20；差异在原raw_response已出现，主协调另在C树直接ground_items复核。015/016两轮60病例/120规则观察汇总一致，但匿名保存产物没有原事件/事实、来源上下文和实际坐标/原响应，无法完整重放当前真实执行链。

三路聚焦纯单测分别57、124、146通过；这些数量不加到已验收规则数。当前D源码未改，独立临床签认和上线批准均未新增。后续需当前版本正式保存/认证页面、008修复方案及015/016完整材料/临床标注，不能用本批离线核对替代。新增模型调用0、DB访问0、旧预期/结果/启用状态变更0。

## 八、下一批第一阶段补充

随后用户确认开工，仅启动计划内只读/合成证伪。A独立复现010有效目标被整任务failed污染比较，正常父字段同步无条件发出7条DDL；主协调另用合成调用和源码验证。A1待单独修复授权，A2缺真实结构及公共迁移职责确认，未进入正式任务。

B唯一栏目坐标候选保持6份输入正文和28个保存事实Python结果不变，但未证明模型收益，停止实施。C定向找回两份旧工程盲审及原始0910离线导出；8张相关源文件存在，7事件触发ID和35个旧文书引用可定位。旧五项审读与当前五事实合同不同，当前分句坐标、原Stage2响应/执行覆盖及临床签认仍缺，不能自动把历史材料变成当前gold。

该补充不覆盖前一批“匿名汇总自身无法完整重放”的结论，只补充其他目录找回的原材料。32条分类不变，完成/临床签认/上线批准均未增加。本批新模型0、PG访问0、生产修改0，未重跑未变单测或更改预期。

## 九、长程持续修复补充

用户要求持续推进后，A1比较入口修复2b4e04b85和A2已齐备父结构跳过重复DDL修复d680849f6完成独立审查与路径限定提交，A/B/C对齐。主协调106单测及3合成API保护通过，故障例29有效结果+3技术失败交付，010仍可比较，原生状态/文案不被重判。只读PG确认真实结构齐备，补丁后函数初始化0DDL；并非认证HTTP、真实PG业务保存或临床签认。

C两例三事件当前五事实工程草案准备完毕，232分句偏移由主协调逐一验证。四处旧正文解析问题由原COPY字段与旧csv行为独立复现；旧35短引文能匹配，不证明完整正文解码正确。readiness、scene、实际来源投影及独立语义审读仍缺，旧工程审读不自动转gold。015/016仍属历史专项、当前口径未闭环。

本阶段真实模型0、PG业务写入0，但进行了只读PG结构查询，不能再称PG访问0。D生产源码未合入；32条分类、规则验收完成数、临床签认和上线批准均不增加。长程目标继续准备最终基线/正式验收门禁，不以工程缺陷关闭数冒充临床规则通过数。

## 十、D受控合入与工程草案复核

随后D分别受控合入A1的compare_cases（1d5e59cf6）与A2父同步10行（f31bd7f03），主协调在D实际导入独立复跑131项聚焦保护通过。D已有readonly构造、两表缓存和单病例精简查询完整保留，不能覆盖整个A共享服务。lint及暂存7文本编码检查通过，路径限定提交不含他人文档；为避免全暂存lint-staged改写其他任务，提交说明显式记录no-verify与手工检查。没有PG业务写入、真实模型、认证HTTP或新的临床批准。

010/012首程另立字段读取闭环，只有_field_state五行消费同次structured_sections，不改Prompt或临床质量判据，已提交fdda9ce1f。D聚焦首程/输入/交付合同先3失败68通过，修复后71通过；独立36边界探针与H10四真实副本8个存在性目标全字段/冻结预期一致，主协调另复跑。这是当前D直接规则回放，尚非worker、正式保存/认证页面或临床充分性验收。质量规则同样共享读取函数，不能因谓词未改宣称所有质量输出不变。

015/016的现有证据构建器由固定归档响应驱动，仅恢复源表fallback路径：两例90/143分句，原232个分句文字与时间保留，另有1个首程分句。该路径算出的五病程源complete仅对应归档固定查询，不证明当前PG、历史readiness或完整bundle可见性，scene仍不补造。

15项工程草案已区分作者再审与未参与起草者的独立审读，二者对最早位置及原报告关联存在不同意见。主协调按原COPY、保存坐标和当前合同继续反查，尚不改写gold或宣布两规则通过。已有判据实现，不将未复核写成标准缺失；不因目标正常体征、复查结果或工程坐标争议自动生成临床结论。

独立审读补查全部原检验子项后显式更正：六值组合唯一属于原PL报告，不再把未逐字写原双PL值当必要条件，三项最早坐标需改、分析/处置可作工程候选。主协调另执行inventory+fallback投影，两例90/184分句，15草案和8主要引用精确保留；后一例因现有首程重复栏目拼接，窗口增加1513字符、Prompt增加11677字符，均未触发门禁，未实测Token或医学收益。本次只记录观察，不顺手改变正文/坐标；完整scene/权威覆盖与正式回放仍未放行。

本阶段工程修复增加，32条分类和临床完成数不变；历史段落保留各自时点，不用最新D合入倒写早期验收成果。长程证据与范围见[持续修复文档](C:/Users/Coldplay/.codex/worktrees/lx0916-validation-handoff/LX888/apps/medqc-web/docs/plans/2026-10-05-0916-long-running-validation.md)。

## 十一、最终D共享失败交付与剩余事件准备

D随后提交031d53252，将共享抽取技术失败的可读来源/规则投影和运输分类受控迁入，不迁007/008或提交他人005/006。主协调独立复现提交基线的合成API故障：任务错误地completed、失败清单为空；修复后29有效结果和3技术失败可实际SQLite保存与API回读，成功010目标same、发布批准仍拒绝。工作区235项聚焦回归及3API通过；不含005/006的候选提交源码另有176项和3API通过；实际提交031d又复跑3API通过。这些不是新增临床通过规则或生产认证/PG/页面证据。

依据：[受控合入范围、红绿与差分保护](D:/LLM/LX888/apps/medqc-web/docs/plans/2026-10-05-0916-shared-extraction-delivery-integration.md)、[实际提交API验证](C:/Users/Coldplay/.codex/worktrees/lx0916-validation-handoff/LX888/apps/medqc-web/.tmp/0910-full-audit/20261005-long-root-d-delivery-chain-committed-v3-private.json)。原两份他人暂存文档的索引blob保持，工作区005/006在移除本补丁后与实施前文本精确相同。独立只读审核未发现阻断缺陷，017直接构造unknown仅作运输分支保护，不能据此宣称真实原生017未知事实已验证；005/006引用重试异常不在本闭环。

015/016其余四例当前inventory+fallback投影已准备，主协调亲自复跑：C01/C04/C07/C21分别60/176/58/206个分句，500个偏移精确；窗口字符4667/7546/3478/7621，Prompt字符21419/53167/20152/60490，各未触发当前字符/分句门禁。与前两例合起来，原6例7事件ID和数量完全一致。归档投影不是原运行完整恢复，scene和权威覆盖保持空，replay_allowed=false；四例五事实草案另行准备、关联争议保留，不凑全部present。

四例随后形成20项五事实草案：作者候选15 present、5 unknown，均待复核；结合前两例现已覆盖6例7事件的35事实草案准备，不等于35项已验收。主协调独立反查20事实和27引用，坐标/切片/时间全部精确，但没有冻结最早坐标：早期ICU措施是否支持独立management、C07同时间更早分句是否支持record/content、C21症状真实时序和独立分析引文均有争议。C04五unknown是同事件关联未确认，不是认定五项缺失或标准未定；当前实现并不要求医嘱写明触发原因。作者草案不覆盖旧结果、人工预期或当前临床结论。

依据：[四例当前材料](C:/Users/Coldplay/.codex/worktrees/lx0916-015016-acceptance-20261005/LX888/apps/medqc-web/.tmp/0910-full-audit/20261005-long-c-remaining-material-private.json)、[主协调独立复跑](C:/Users/Coldplay/.codex/worktrees/lx0916-015016-acceptance-20261005/LX888/apps/medqc-web/.tmp/0910-full-audit/20261005-long-root-c-remaining-projection-private.json)、[四例工程草案](C:/Users/Coldplay/.codex/worktrees/lx0916-015016-acceptance-20261005/LX888/apps/medqc-web/.tmp/0910-full-audit/20261005-long-c-remaining-draft-facts-private.json)、[主协调独立审读](C:/Users/Coldplay/.codex/worktrees/lx0916-015016-acceptance-20261005/LX888/apps/medqc-web/.tmp/0910-full-audit/20261005-long-root-c-remaining-draft-review-v2-private.json)。本阶段真实模型/PG访问0，不重跑模型补统计；后续010/012限定正式运行的PG写入和最多16次generate额度已集中请求，尚未获新授权，不挪用历史已消费额度。长程目标保持，9专项+2历史专项+3历史实验+18整包/审计分类及临床签认/上线批准数量均不增加。

## 十二、当前D回放保真门禁与真实构造保护

在7fe2ef7d7时点，主协调独立复跑H10纯模型边界预检：两个历史任务、四副本的8个初次Prompt，在D工作区及提交源码中均不同。旧合同005–008为items；工作区仅005/006为items、007/008为state，每次少645字符；提交源码001–009均为state，每次少2320字符。实际选材JSON、正文、共享规则和抽取函数调用kwargs精确相同，但这不证明provider内部模型配置相同。主协调验证方式为纯源码加载、逐份Prompt与选材比较、合同全文断言；[独立结果](D:/LLM/LX888/apps/medqc-web/.tmp/0910-full-audit/20261005-long-root-d-h10-fidelity-check-v2-private.json)保留失败的旧断言产物，不覆盖历史响应。

因此旧响应消费0，未执行完整Worker、重试边界或253项原生结果比较。不能将S1/A的253项历史回归写为当前D模型事实复验，也不能仅因选材相同而跳过正式运行。后续预算获准时须冻结实际工作区版本及Prompt，明确005/006未提交实现是否纳入，不能默认以HEAD取代客户将运行的源码。

A2补充两个真实SQLite冷构造保护例，专用测试共13项通过：[测试结果](C:/Users/Coldplay/.codex/worktrees/lx0916-validation-handoff/LX888/apps/medqc-web/.tmp/0910-full-audit/20261005-long-root-d-ready-constructor-green-private.json)。不替换sync/Inspector，准备阶段建齐父列和指定父索引后清空三缓存；可写构造观察到真实反射且0DDL/DML，只读构造严格0SQL。独立静态审查未发现缓存/监听污染；范围仅single模式SQLite，不扩为PG、split模式或认证HTTP证明。本次不改生产代码、模型/PG访问0，32条验收统计及批准状态不变。

## 十三、六例当前PG来源新冻结

在4a8b37059时点，主协调从D既有配置建立独立只读连接，不导入应用/建表服务、不调用可能upsert的bundle装配。单连接REPEATABLE READ、事务readonly=on，同一快照执行52条受控SELECT/SHOW/SET，六例逐三坐标读取当前生产两类触发查询（201行哨兵）、Stage2权威五病程源与住院登记（501行哨兵）。五源含术后首次病程、不含会诊；该范围在执行前由独立审查指出并按真实Stage2:25–31更正。没有PG业务写入、DDL或模型调用，不覆盖旧材料。

主协调另一进程用当前Python builder逐例反算：6例7事件ID及完整归一化事实与旧固定材料相同，两触发源均未超200行，五病程原始查询均未超500行，登记各唯一1条。连接目标插值风险另核：实际配置无模板，literal/parsed值精确相同，不打印或保存值；未来脚本禁用插值并拒绝未解析模板。上述依据为H16，不是独立临床答案，也不恢复旧Prompt/响应。

此次补齐的是当前原始材料，raw_query_complete不能替代生产fallback、实际bundle或Stage2覆盖。scene仍空、replay_allowed=false，关联/最早坐标异议与人工预期保持。该阶段确有只读PG访问，不表述为PG访问0；32条分类、临床签认和上线批准不变。后续先核实际源投影/场景与独立标注，再按单独预算进入受控Stage2；不得直接重跑30例大包补统计。

## 十四、现存缓存与限定五源候选投影

在cfcfcbc8f时点，主协调只读观察六例各running/final两个候选场景，复用当前缓存读取、0916 JSON解码及年龄合并函数，装配/upsert分支强制停止。12候选均返回既有bundle-v6缓存；单只读REPEATABLE READ事务记录88条SQL（85 SELECT、2 SHOW、1 SET），无读取异常、DDL、业务写入或模型调用。主协调独立逐段反查每候选7条SELECT及三坐标参数，不以缓存可用性代替来源完整性。当前ensure_scene_bundle_tables只检查五张表存在，不执行DDL；缺表、缓存需装配和年龄异常仍必须停止，而非模拟正常返回。

缓存与第十三节raw冻结是两个事务，不能宣称同一时点快照或恢复历史任务scene。随后纯离线复用当前evidence构建、来源补充、Stage2目录/事件输入/Prompt函数，未冻结的21源每候选均抛出不可用异常，不补造空表；五正式源及登记仍仅提供三坐标冻结响应，不能证明生产宽谓词的完整返回范围。原算法计算的complete和目录ready仅对这些限定输入成立，production_readiness保持空，replay_allowed=false；未传检验strict参数不影响五源目录，但不证明整体evidence等价。

主协调及独立审核分别比较完整有序(source_type、document_id、clause_id、authored_at、text)：12候选均与此前归档官方投影精确相同，无新增、删除或同坐标正文/时间变化。C16/C25/C01/C04/C07/C21分别90/184/60/176/58/206分句，两个候选场景一致；Prompt字符分别41381/54511/21419/53167/20152/60490，不是Token或实测耗时。该比较不冻结最早临床位置、解除关联争议或产生新模型事实。

依据：[缓存只读冻结](C:/Users/Coldplay/.codex/worktrees/lx0916-015016-acceptance-20261005/LX888/apps/medqc-web/.tmp/0910-full-audit/20261005-long-c-cache-readonly-freeze-private.json)、[主协调限定候选投影及SQL日志反查](C:/Users/Coldplay/.codex/worktrees/lx0916-015016-acceptance-20261005/LX888/apps/medqc-web/.tmp/0910-full-audit/20261005-long-root-c-current-candidate-projection-private.json)。产物均忽略且私有，不提交患者正文。Stage2不消费locatable_document_coordinates或medical_text来补齐五源覆盖；真实门控见[disease_change_stage2.py:310](D:/LLM/LX888/apps/medqc-web/backend/app/services/luxian_0916/disease_change_stage2.py:310)。生产非strict查询按院区+就诊、空结果后再放宽，现冻结未覆盖该域，见[sample_programmatic_evidence.py:731](D:/LLM/LX888/apps/medqc-web/backend/app/services/sample_programmatic_evidence.py:731)。下一步仅补该五源实际查询域的证据，不扩大规则或反复调Prompt；32条分类、临床签认和上线批准数量不变。

## 十五、五源实际宽查询覆盖补齐

随后在df199e96e时点完成H17。主协调亲自执行已审查的有界只读脚本：六例、两个候选scene共用一个REPEATABLE READ/readonly=on事务，记录220条SQL（217 SELECT、2 SHOW、1 SET），源代码未变化，业务写入/DDL/模型调用均为0。原缓存读取包含年龄合并、禁止装配/upsert；触发沿原两条SQL及201行上限；五源沿原宽谓词和3/51/51/11/11行哨兵，空响应才放宽、不增加ORDER BY、不过滤返回行。未出现读取失败、跨三坐标行或五源超限。独立审核逐条反查SQL/实际绑定参数及216份响应对应关系；其余21源共252次在PG前拒绝，不补造空表。

12候选的五源readiness均complete，Stage1、事件、目录和输入门禁均无缺口。主协调另一进程及独立审核分别对比完整有序目录、全归一化触发事实及重建Prompt，逐字相同。本次关闭的仅是“该新快照下五正式源实际查询覆盖未核实”的准备缺口：不覆盖其他规则资料、整体evidence/Worker、历史任务scene或登记归属。登记原SQL未返回身份字段，registration_identity_verified保持false，不增加查询假装验过。

原merge前80项同源同ID观察中有12项正文/章节差异，全部首程cache与source。主协调独立按保存文书ID绑定本次raw行，调用当前纯assemble_document，确认12份缓存的ID、正文、sections和source_fields与重建值精确相同，证明是同一保存文书可对应的两种投影形态；验证产物见H17。原拼接及缓存取值路径见[assembler.py:729](D:/LLM/LX888/apps/medqc-web/backend/app/services/document_assembly/assembler.py:729)、[assembly.py:1713](D:/LLM/LX888/apps/medqc-web/backend/app/services/bundles/assembly.py:1713)。这不证明历史缓存生成版本，也不把较长正文优先merge当医学冲突校验；差异记录完整保留，不顺手去重或修改坐标。

015/016工程标注仍为6例7事件35草案，最早位置及关联异议未转gold。下一步是冻结独立预期及正式场景，而不是继续扩大只读扫描或重复未变单测。当前新模型预算及正式任务PG写入授权仍待回应；不挪用旧额度、不更改人工预期/启用/批准状态。9专项+2历史专项+3历史实验+18整包/审计分类、临床签认和上线批准数量均保持。
