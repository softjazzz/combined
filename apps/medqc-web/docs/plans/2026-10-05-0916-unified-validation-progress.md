# 0916 全32条统一验证进度

初次核对日期：2026-10-05，后续更新至2026-10-07第三十一章。范围仅为 LX0916-001 至 LX0916-032，不含病案首页。第二章保留初次版本盘点时点，第四章明细随新增证据更新；后续各章按发生顺序补记修复、测试及只读PG查询。最初盘点不调用模型、数据库或历史脚本；后续不改原工程预期、临床答案、启用或批准状态，历史文件保留。

## 一、统计纠正

原“完成4条、测试9条、23条未开始”只描述本轮专项推进，不能描述全部历史。统一去重后的记录如下：

| 维度 | 条数 | 范围与限制 |
| --- | ---: | --- |
| 有历史真实整包执行/冻结回放证据 | 32 | 30份0910真实病历；证明当时执行链、结果合同、隔离和回放记录，不代表32条医学判定通过 |
| 已纳入原9条专项统计 | 9 | 003、005、006、007、008、010、011、012、014；003/005/006不再加算 |
| 原统计漏列的历史专项 | 2 | 015、016；包括结构化触发以及后续Stage2真实回放，当前口径的独立临床验收未闭环 |
| 本次补找到的历史专项实验 | 3 | 024、025、026；专用30例两轮回放，稳定性门禁未通过，不能补计为完成 |
| 原专项/历史实验记录的规则去重合计 | 14 | 上述9+2+3；“做过专项”不是“专项验收通过”，不把普通门控修复单测混算为医学判定专项 |
| 尚未形成独立专项验收的规则（含工程准备/局部修复） | 18 | 001、002、004、009、013、017、018、019、020、021、022、023、027、028、029、030、031、032；H22补018输入身份修复/023工程预期，H30关闭023局部来源门控，正式验收仍缺 |
| 新增来源门控局部工程修复 | 1 | 023；H30公开红绿、198项聚焦测试及两冻结正例保护，正式PG/API/页面仍未闭环，不增加上述14条专项或完整验收数 |
| 原4条阶段性工程成果 | 4 | 005、006、010、012，在A树当时限定范围内有工程一致性/保存回读证据；保留，不升格为整条临床验收 |
| 另有历史触发/固定输入回归里程碑 | 2 | 015、016；与上述4条正式保存里程碑不是同一种门禁，不混算成“6条全部验收完成” |
| 可证明当前D树完整单规则工程验收完成 | 0 | 尚未形成覆盖当前D实际源码、同一门禁和完整规则范围的证据闭环；不是“32条完全没测试” |
| 找到独立临床签认完成的规则 | 0 | 工程预期、Agent交叉审查、状态一致均不替代临床签认 |
| 找到上线批准完成的规则 | 0 | 文档均保留测试/待复核；当前0916验收台仍为acceptance_only且publication_supported=False |
| 规范逐条说明/验收台基础建设 | 32 | 已完成，不计为32条临床验收 |

按互斥工作记录类别，32=本轮专项9+历史专项2+历史实验3+整包/审计18。按本轮规则判定证据口径，仍是9条已推进、23条尚未形成本轮逐规则判定验收证据；后23条中已有5条历史专项/实验，023另已进入正式启动但在取材阶段停止，不能称为完全未测试或完全未启动。重复病例、同病例多轮、整包非目标规则均不重复增加规则数。

H30的023来源门控局部修复是单列工程维度，不加到上述32条互斥分类，也不混算成第五条历史正式验收成果。

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
| LX0916-010 首程病例特点存在性 | 本轮专项 | H0/H1/H6/H10/H13/H15/H19/H21；先2真+2合成，后4真例正式保存 | V3；H19绑定b5fb15f76工作区；H21成本复验绑定d7a1cab21实际源，均非正式发布构建 | 两批工程预期分别4例；最新C01/C06/C17/C30仅正例，非临床质量答案 | H19独立010整包128有效/0失败、四行认证API same及页面回读；H21补成本保存和真实部分失败运输，不连带充分性验收 | 真实缺项、临床独立复核、正式发布版本；H19旧job成本0保留，不回填 | 当前正式Worker/PG/认证页面工程链路达成；完整未完成 | 待签 | 未批准 |
| LX0916-011 病例特点归纳充分性 | 本轮专项 | H0/H1/H9；C01/C30两真例本地受控抽取；H10/S1含非目标失败样本 | V3；D已补首程字段和031d失败交付，旧本地充分性结果仅条件复用 | 仅C01-011为窄范围工程adequate候选；C30人工复核；无临床独立答案 | 两例模型均合规，仅1个工程候选一致；evidence为空；D新增合成故障保护不是临床通过 | 归纳理由/直接证据、真实缺陷、正式保存/回读和临床判断 | 本地候选及故障保护；未完成 | 待签 | 未批准 |
| LX0916-012 首程三要素存在性 | 本轮专项 | H0/H1/H6/H10/H13/H15/H19/H21；2真+2合成后4真例；H21独立012正式任务 | V3；D d7a1cab21实际工作区28份列示源码冻结到退出未变，非发布构建 | 四真例预冻结工程预期均三栏非空；真实缺项候选有界扫描0，此前负例仍仅合成 | H21四目标冻结字段及历史原生8字段一致，PG/认证API/四例页面回读；125有效+3非目标执行失败完整覆盖128计划对；成本PG/API精确相符 | 真实缺项、独立临床复核及发布冻结；不评价充分性、不称整包全成功；模型事件job关联未建立 | 独立正式Worker/PG/认证页面及成本工程阶段达成；完整未完成 | 待签 | 未批准 |
| LX0916-013 诊断鉴别依据充分性 | 整包/审计 | H0/H1/H8；H10/S1及第十一章D合成故障保护，不是充分性专项 | V3，D031d已迁入失败交付，首程取值也已修复；当前模型/医学结果未复验 | 未找到独立充分性专项预期；技术异常样本不是临床负例 | 无本轮医学专项；D29有效/3技术失败的合成API保护不补计为013验收 | 充分性理由/证据及临床答案；当前D真实故障保存/认证页面 | 整包/故障工程证据；未完成 | 待签 | 未批准 |
| LX0916-014 诊疗计划全面具体 | 本轮专项 | H0/H1/H9；2真例本地抽取；H10/S1有非目标故障保护 | V3 | C01/C30均在运行前保留人工复核；无确定临床金标准/真负例 | 两例输出合规，均没有质量理由/直接evidence，不计临床通过 | 剂量/疗程等标准维度与Prompt检查范围需复核；证据及正式保存 | 有本地结果，未闭环；未完成 | 待签 | 未批准 |
| LX0916-015 病情变化记录完整 | 历史专项 | H0/H1/H5/H13/H14/H15/H16/H17/H18；旧文本盲测、结构化30例、Stage2两轮30例及七事件当前审读表 | V4，Stage2已接线；df199时点六例同快照核实两候选缓存、触发和五源实际宽查询；非旧运行恢复 | 结构化24无触发+6触发7事件；35工程草案已独立审读并整理交接，关联/最早坐标异议未转gold | 12候选五源complete、输入门禁无缺口，完整目录/Prompt/归一化事实精确相同；30项引用的60候选scene核查一致；新模型0 | 当前五事实预期冻结、正式任务scene、独立未见病例及临床签认；旧原响应仍缺；完整Worker未验收 | 历史回归/当前输入覆盖及草案审读；完整未完成 | 待签 | 未批准 |
| LX0916-016 病情变化分析处理 | 历史专项 | H0/H1/H5/H13/H14/H15/H16/H17/H18，同一专属抽取、Python分别判定 | V4，Stage2已实现；六例当前五源实际查询覆盖已核，不证明完整evidence/历史场景 | 同015；35事实草案与原注释精确保留并绑定新覆盖，独立异议不自动选边 | 历史两轮24不适用+6合规；当前两候选scene目录/Prompt/触发事实相同；C04五unknown仍非已证实缺失 | 分析/处理和事件归属预期冻结、正式场景、真实缺陷与临床签认；原merge不保证医学冲突校验 | 历史回归/当前输入覆盖及草案审读；完整未完成 | 待签 | 未批准 |
| LX0916-017 检查用药合理性 | 整包/审计 | H0/H1/H8，30真例整包 | V4，事件执行模块同但共享抽取/失败分类不同 | 未找到独立合理性专项预期 | 未找到本轮专项结果 | 独立临床合理性答案、医嘱触发/覆盖与证据解释 | 整包历史；未完成 | 待签 | 未批准 |
| LX0916-018 危急值报告处理 | 整包/审计，输入修复与预期准备 | H0/H1/H8/H12/H21/H22/H23/H31；严格输入、主键、当前纯重建及90分句审读草案 | H22身份修复9c10265ef保持；H31四回归失败是raw fixture缺document_id，未修改正式测试 | H23两事实unknown草案、6候选/17反证定位；关联保留，不当absence；C01仍仅副本 | H31内存仅补原始明细身份，四Worker恢复原预期+22身份保护共26通过，root重跑；真实Stage2模型0 | 正式fixture补丁未实施；报告/处置唯一关联、独立预期冻结、正式任务与临床复核；真实完整无触发仍缺 | Stage1闭环及草案准备；单规则验收未完成 | 待签 | 未批准 |
| LX0916-019 重要操作记录规范 | 整包/审计 | H0/H1/H8，30真例整包 | V4，事件模块同，旧响应版本未等价 | 未找到独立操作专项预期 | 未找到本轮专项结果 | 真实操作触发、记录缺陷、时间/关联及资料缺口验证 | 整包历史；未完成 | 待签 | 未批准 |
| LX0916-020 修正诊断理由依据 | 整包/审计 | H0/H1/H8，30真例整包 | V4 | 未找到独立诊断修正专项预期；不等于标准未定 | 未找到本轮专项结果 | 独立修正事件与病程依据关联、真实缺陷/来源不足 | 整包历史；未完成 | 待签 | 未批准 |
| LX0916-021 手术同意书完整性 | 整包/审计 | H0/H1/H8；run5的30条事后核对均无法复核 | V4，对应执行模块同，实验树不能替代整链 | 未找到独立冻结预期；30条无法复核不能当准确率 | 未找到本轮专项结果 | 同意书实际来源覆盖、手术关联与缺项引文 | 整包/事后审计；未完成 | 待签 | 未批准 |
| LX0916-022 麻醉同意书完整性 | 整包/审计 | H0/H1/H8；早期29资料不足+1不适用，发布来源门禁未过 | V4 | 未找到独立冻结临床预期；有合成路由保护，不是真实来源通过 | 未找到本轮专项结果 | 麻醉同意书真实来源链及适用性/具体缺项验证 | 来源门禁未过；未完成 | 待签 | 未批准 |
| LX0916-023 麻醉记录存在性 | 整包/审计，局部修复完成、正式验收未出结果 | H0/H1/H8/H22–H31；15条事后supported、两冻结正例、新副本/预期/旧run保存、来源门控及新任务前置停止 | H31实际HEAD推进但65份验收源码逐字同021f2e93d准备；不把HEAD当构建身份 | C02/C03两工程正例development，gold/clinical=False；新任务预算已批准，尚未提交 | H30来源修复保持；H31新任务前因旧保护副本两个技术字段不同停止，旧job/run/原文/答案不变；0新规则结果 | 等待允许仅技术字段现值重冻结；两定向running upsert/新任务预算未消费；真缺失/局麻/多麻醉关联/临床仍缺 | 创建/预期保存及来源门控局部修复；未完成正式规则验收 | 待签 | 未批准 |
| LX0916-024 麻醉记录完整性 | 历史实验 | H0/H1/H8/H11；专用两轮30例含16触发，run5另有10条事后支持 | V5，C实验未证明与D/A当前相同 | 未找到独立预冻结临床gold；整族稳定性试验不是逐规则准确率 | H11整族passed=false，9例跨轮变化；不将整族失败推断为024独有漂移 | 实验版本/输入绑定、稳定性、缺项证据、独立答案及正式回读 | 历史专项实验未通过整族门禁；未完成 | 待签 | 未批准 |
| LX0916-025 手术记录完整性 | 历史实验 | H0/H1/H8/H11；H11实际summary明确含025，不因文件名漏计；run5有1条支持 | V5 | 无独立预冻结临床gold；来源缺口多，不可用无异常数替代验收 | 两轮各14资料不足+2不合规+14不适用；整族稳定性失败 | 来源覆盖、手术关联、独立预期与可定位缺项；不能因025状态计数相同判全通过 | 历史专项实验未通过整族门禁；未完成 | 待签 | 未批准 |
| LX0916-026 手术安全核查完整性 | 历史实验 | H0/H1/H8/H11；两轮30例，run5另有10条事后支持 | V5 | 无独立临床gold；无真实输血阳性，输血条件仅合成保护 | 两轮资料不足6到2、不合规10到14；整族9例漂移、passed=false | 抽取合同、跨文书/多手术关联、真实输血条件与三方签字事实 | 历史专项实验未通过；未完成 | 待签 | 未批准 |
| LX0916-027 急诊手术上级指示 | 整包/审计 | H0/H1/H8；run5的30条均无法复核 | V4 | 无独立急诊触发专项预期 | 未找到本轮专项结果 | 急诊触发、上级医师角色/指示及手术关联验证 | 整包/事后审计；未完成 | 待签 | 未批准 |
| LX0916-028 非计划再次手术说明 | 整包/审计 | H0/H1/H8；run5的30条均无法复核 | V4 | 无独立非计划再次手术专项预期 | 未找到本轮专项结果 | 多手术事件、非计划属性、上次情况/原因关联及真例 | 整包/事后审计；未完成 | 待签 | 未批准 |
| LX0916-029 特殊项目同意书 | 整包/审计 | H0/H1/H8；run5的30条均无法复核 | V4 | 无独立特殊项目触发专项预期 | 未找到本轮专项结果 | 项目触发、对应同意书来源/角色及完整性验证 | 整包/事后审计；未完成 | 待签 | 未批准 |
| LX0916-030 病危重通知书完整性 | 整包/审计 | H0/H1/H8；run5的30条均无法复核 | V4 | 无独立通知书专项预期；015/016病危重医嘱回放不能代替本条 | 未找到本轮专项结果 | 通知书来源、签字/内容事实；与医嘱触发分开验收 | 整包/事后审计；未完成 | 待签 | 未批准 |
| LX0916-031 出院诊疗经过详细性 | 整包/审计 | H0/H1/H8；run5有5条supported，root-verify单文书词项核对 | V4，出院模块同，旧源/响应未绑定当前版 | 事后原文核对无独立预冻结临床答案 | 未找到本轮独立专项结果 | 全程诊疗事实与出院总结对应、充分性及临床签认 | 局部事后复核；未完成 | 待签 | 未批准 |
| LX0916-032 出院医嘱完整性 | 整包/审计，原文草案准备 | H0/H1/H8/H31；run5仅1条supported；新增两真实历史原文草案先冻结后看旧结果 | H31当前context/rule/selector纯投影及三源码快照，非当前PG或正式模型验收 | 两例最终均unknown草案，七连续引文精确命中；无临床gold/明确完整正负例 | root另核七定位、六完整引文可见；纯规则均semantic_fact_unavailable，非医嘱确实缺失 | 逐维度临床答案、真实全源覆盖、正文尾部投影及时间差异；没有独立表不等于没有权威原文 | 原文及可执行边界准备；未完成 | 待签 | 未批准 |

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
| H18 | [七事件工程审读交接表v2](C:/Users/Coldplay/.codex/worktrees/lx0916-015016-acceptance-20261005/LX888/apps/medqc-web/.tmp/0910-full-audit/20261005-long-c-seven-event-annotation-handoff-v2-private.md)；[原草案、独立异议与新覆盖索引v2](C:/Users/Coldplay/.codex/worktrees/lx0916-015016-acceptance-20261005/LX888/apps/medqc-web/.tmp/0910-full-audit/20261005-long-c-seven-event-annotation-handoff-v2-private.json)。099b时点6例7事件35原事实/注释精确保留，30项引用两候选scene匹配；零新模型/PG，不转gold，v1保留 |
| H19 | [当前版本正式认证/PG/页面回读](D:/LLM/LX888/apps/medqc-web/docs/plans/2026-10-06-0916-a3-formal-readback.md)。b5fb15f76实际工作区：2次POST、1 creation_failed run、1正常010整包job；128有效/0失败、四模型调用/20487Token，010四例认证页面回读；012仅整包结果。job成本错误保存0单列待修，不增临床通过 |
| H20 | [离线并发闭环及最小成本修复](D:/LLM/LX888/apps/medqc-web/docs/plans/2026-10-06-0916-offline-parallel-batch.md)。Worker新摘要累计可见generate成本；73项聚焦回归及主协调8个独立探针通过。新增索引历史真实正例/合成负例，018有限准备完成；0新模型/PG，不回填旧job，不增加临床通过 |
| H21 | [012独立正式回读与两路限定取材](D:/LLM/LX888/apps/medqc-web/docs/plans/2026-10-06-0916-012018-authorized-parallel.md)。1任务/5generate，125结果+3执行失败完整覆盖128计划对；012四例一致，PG/API成本及页面回读闭环；B未找到批准范围内真实缺项，C018只读输入准备，不加算临床通过 |
| H22 | [首程候选红灯、018输入身份修复和023预期准备](D:/LLM/LX888/apps/medqc-web/docs/plans/2026-10-06-0916-next-011018023-batch.md)。1任务/4generate，125结果+3运输执行失败；首程零回退门禁失败已撤回，018只关闭Stage1身份缺陷，023两工程正例尚未正式运行，不增整条通过 |
| H23 | [023正式入口门禁及两路只读工程预期](D:/LLM/LX888/apps/medqc-web/docs/plans/2026-10-06-0916-023-formal-018-expectation-batch.md)。新Bundle授权已获，创建前发现visit_index无条件DDL并停止；018候选引文和首程两字段审读完成，0PG/HTTP/模型/生产修改，不增通过数 |
| H29 | [023场景与证据链只读调查](D:/LLM/LX888/apps/medqc-web/docs/plans/2026-10-06-0916-visit-index-schema-repair-023.md)。冻结running重装仍空、final有麻醉但当前入口不能直接换场景；来源失败误判无事件有独立合成红灯，尚未修复，0新增外部调用/生产修改，不增加完成数 |
| H30 | [023来源空数组门控修复](D:/LLM/LX888/apps/medqc-web/docs/plans/2026-10-07-0916-023-anesthesia-source-gate.md)。17行生产增量、26项新保护/198项聚焦通过、两冻结正例四输入128native结果不变；018扩展4失败在原投影下重现；0外部调用，不加正式/临床验收 |
| H31 | [023/018/032三路批次](D:/LLM/LX888/apps/medqc-web/docs/plans/2026-10-07-0916-023018032-parallel-batch.md)。018四失败fixture根因及26内存候选保护、032两原文unknown草案、023新任务前旧保护技术字段差异停止；新任务/模型/PG写入0，不补计规则通过 |

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

## 十六、交付审计与七事件工程交接

主协调按原计划重新核对全部交付项，A1/A2、首程字段和共享失败交付的工程修复已有D源码与提交证据，008唯一候选无模型收益证明，按门禁停止实现。A3当前版本正式保存、认证HTTP及页面仍是必交项，不降为可选，也不以H10旧响应或131/235项测试替代。当前8001是其他任务的只读主应用入口，lifespan=off；唯一版本GET返回500，未证实正常启动和最终服务版本。没有重启、修改它或发认证/任务请求。当前完成审计及停止条件见[A任务书第七节](C:/Users/Coldplay/.codex/worktrees/lx0916-validation-handoff/LX888/apps/medqc-web/docs/plans/2026-10-05-0916-next-acceptance-plan.md)，A提交4d81a0892。

C将两份格式不同的草案整理为H18交接索引，生产不消费、不新增事实合同：6病例、7事件、35个唯一(event_id、fact_kind)，每个原fact及annotation逐字段保留，独立审读和更正意见并列，不自动选边。主协调重新核原对象、事件索引和60项候选scene引用检查；30项引文在新目录中的坐标唯一、连续子串、文书时间及事件允许坐标一致。C04五unknown没有原引用，仍是关联未确认，不标成确证缺失。

v1的空时间集合曾经all([])=true，主协调发现后要求另存v2，v1脚本/JSON/MD保留。v2有15项原引用含事件时间且匹配，另20项未提供该时间而为null；不把没有时间对照当已通过。本文“引文匹配”不重验原绝对offset，旧偏移证据仍单列，不扩大验证声明。gold=false、clinical_signoff=null、ready_to_apply=false全部保持；新的五源覆盖不回填旧readiness或历史scene。

本节没有直接PG查询或模型调用，只有一次不含患者数据的版本HTTP GET；未另行观测服务器中间件的数据库访问，不扩称端到端SQL为0。没有规则结果、旧预期、启用状态或批准变更。长程目标未完成，A3的新限定PG写入/16次generate额度及正常服务门禁已集中请求。其余未授权Stage2/008模型对照和临床签认不挪用A预算，32条统计不变。

## 十七、A3授权已收到，停止于公共启动门禁

2026-10-06用户明确授予此前A3限定范围：最多2次正常任务、16次generate（含重试）、PG保存及真实认证API/页面，不扩大DDL、旧任务恢复或临床/上线授权。后续不能继续表述“A3预算未授权”；前述历史段落保留其原时点。

主协调在D的9a5255266实际工作区冻结列示源码，亲自执行只读REPEATABLE READ核对：13 SELECT、2 SHOW、1 SET，4份旧副本的文书ID/结构化补丁、8条工程预期及4例原首程完整快照均未变。新正式任务、PG业务写入、DDL、generate均0，调用额度未消费；仅材料可复用，不计为当前版本正式验收。

主协调和Sol6.1 medium独立审查，再由主协调按当前源码反查确认：正常启动仍尝试6组视图DROP/CREATE，上传/DRG预热还经异步任务建表与恢复路径，0609queued重投和stale巡检也会启动。未启动服务，不能说这些写入/旧任务恢复实际发生。现存8001仍是其他任务的lifespan=off只读服务，不修改或借用它做写入。根因路径、证据边界与独立公共启动修复授权请求见[正常启动门禁](D:/LLM/LX888/apps/medqc-web/docs/plans/2026-10-06-0916-a3-startup-gate.md)。

A1/A2修复证据保持，A2不等于全应用零DDL；A3正式运行/保存/认证页面及成本仍未完成，不降为可选。已请求默认生产行为不变的最小验收启动控制，尚未实施。32条分类、临床签认、启用及上线批准状态均不变。

## 十八、显式验收启动控制闭环

2026-10-06用户同意最小启动控制修复。main仅增加13行显式分支，新独立模块负责模式/只读结构门禁，不改默认生产迁移与恢复职责。acceptance拒绝production、非法值及不齐结构，异常在宽容try外；成功走正常lifespan后不进入DDL/后台预热/旧任务恢复。根因与白名单见[修复任务](D:/LLM/LX888/apps/medqc-web/docs/plans/2026-10-06-0916-acceptance-startup-control.md)。

主协调第一次真实启动发现自己把缓存表误归cdm的假设，按现有0916入口的public默认值更正并保留红灯。新增严格schema保护后55项门禁、结合原父结构共68项通过；独立diff审核未发现阻断。主协调实际D、正常TCP/lifespan=on核验23 SELECT、1 SET，PG DDL/DML及0916客户端generate为0，无阻断；版本GET200绑定本进程、未认证验收GET401，未启动原恢复管理器/巡检，进程已退出。没有修改他人8001。

此处只关闭显式启动门禁；运行版本声明available=false，实际源时点/路径/PID另行冻结，不伪称正式发布身份。登录、正式任务/PG保存、真实模型成本及页面还需A3，原2任务/16generate额度未消费。32条验收分类、旧预期、临床签认和上线批准数量不变。

## 十九、当前A3正式工程回读与成本缺口

在D b5fb15f76实际工作区完成正常启动/真实认证、一个010正式整包任务、PG保存和四例页面回读；源码快照到进程退出未变。第一次POST因主协调私有SQL护栏误读rule_count而500，只保存creation_failed run，无job/模型；v1产物保留。修正后仅再POST一次010，保守计累计2次提交，不追加012。完整128计划对均有合法唯一结果、无失败/缺失/越界；四例010认证比较same，八010/012存在性目标与旧冻结程序预期全原生字段精确一致。原件完整行、副本文书ID/冻结补丁及八工程答案均未变，不扩称副本全字段复核。

主协调亲自反查投影代码、PG产物及四例页面，独立审查另重建128计划对。API保留公开事实/证据/建议，不暴露内部diagnostics；不能声称内部字段全经API回传。012仅该010整包中的原生结果，未完成独立012本轮认证验收。真实模型qwen3.8-flash，开启思考/budget256，四generate/四attempt/四HTTP、重试0，累计20487Token、86.848秒API时间；任务HTTP elapsed34.812秒，不与累计API时间混算。

进程退出后只读PG核实两run/一job/四事件；事件Token=20487，job成本两列为0。主协调按worker未传统计字段及保存层缺省0的当前代码反推确认，单列下一独立最小修复，不覆盖旧任务。新正式部分失败分支、独立012运行、成本修复、真实负例/临床复核和发布冻结仍未闭环。证据、预算及更正见H19；32条9+2+3+18分类、临床签认和上线批准数均不增加。

## 二十、成本修复离线闭环与验收准备

经用户批准，复用三棵工作树，Sol6.1 medium三路并发，未整树合并或覆盖历史修改。主协调先冻结当前D Worker副本，再审查候选与SDK/保存语义，最后在D整合69行净增及16项聚焦测试；原测试两处函数身份断言改为可调用性，实际参数/响应/异常保持另验。最终73项聚焦回归、ruff、编码和只检查lint通过；主协调独立重跑8个探针，其中六份合成交付除7新增统计字段外与不可变pre-edit Worker逐值相同。以上不是真实病例整包重放或临床准确率证明。

新任务摘要累计已知Token和API秒，所有generate入口同一任务局部包装，不叠加族诊断、不用壁钟补API时间；缺失/非法统计和异常标不完整。已保存的H19 job不回填。新增完整性只说明可见响应，SDK内部缺失attempt仍不可追溯；安全API投影尚未展示新完整性字段，不扩为页面已经可见。关闭的是成本摘要缺字段的离线实现缺口，真实新任务PG/API回读仍待限定验收。

B找回C09/C12历史真实正例及预先冻结S10/S12合成负例，主协调反查归档空栏/答案。30例旧只读字段盘点经主协调重算均单文书且四栏非空，仍不能补真实缺项覆盖；不重复加算六正例或两合成例。C完成018有限历史索引及触发/无触发/报告处置/覆盖/关联/尾部矩阵。两个专属脚本不能替代独立保存结果，015/016材料不能替代018严格检验来源；下一轮先冻结一个真实PL触发及一个完整无触发病例的权威输入和独立预期，不立即调用模型。

本批产物见H20及其私有索引。010/012成本剩余门禁改为“修复后新任务PG成本回读”；012独立正式任务、真实缺项、临床复核和发布配置仍未完成，018只完成准备，不升级专项通过。32条9本轮专项+2历史专项+3历史实验+18整包/审计分类、临床签认和上线批准数量不变；真实模型/PG访问/新验收任务均0。

## 二十一、012独立正式回读及018限定输入

2026-10-06按新授权执行一次012正式任务，D d7a1cab21实际工作区列示28份源码从启动到退出逐字未变。正常lifespan、真实认证/Worker/模型/PG保存，四份旧副本的文书ID/冻结字段、四原件完整行及八工程答案前后不变；不扩称副本所有字段复核。128计划对为125合法结果+3可定位执行失败，无遗漏/重复/越界，整包summary=partial_failed、存储status=failed，不能写为全部成功。

012四目标与冻结预期及历史八原生字段精确一致，认证规则比较same；主协调真实浏览器逐例核对三栏present、来源文书ID、无证据片段/无建议的实际展示，未提交case_review或批准。客户样本页另明确展示部分执行失败、125项保留及011/013/014三项技术失败。新job累计22958 Token、81.775110秒API时间、5generate/5attempt/5HTTP，PG摘要/成本两列与浏览器正常认证详情GET逐值相同。详情GET也确实保留全部7新增统计字段，纠正H20当时尚未实测投影的限制；不声称页面展示了完整性旗标。

C01两次响应均仅含semantic_facts，第二Prompt携invalid_top_level_facts，当前合同失败分支返回且未置成功重试标记。主协调用保存响应及semantic_extractor:1229–1239、batch_worker:820–835反推确认一次受控合同重试失败，不能由summary重试计数0宣称零重试；SDK长度重试0。失败不改写临床结果，012保留。5观测事件可按本进程逻辑调用与attempt对应，但root_job_id为空，不称PG已建立同任务关联；不在本批扩大SDK/观测改造。

B单只读快照在泸县人民医院、2025-07至08月、排除测试标识的四栏空值候选谓词内，最多60元数据行，实际0候选，6条SQL、正文0。不代表全库无真实缺项，不扩扫；真实缺项覆盖仍未补齐。C新只读快照46条SQL（43 SELECT/2 SHOW/1 SET），两候选严格检验及五病程readiness均complete、未超限、无跨三坐标行；38次未选源在PG前拒绝，不伪造空表。C16两条PL同报告、同item_id，当前Stage1为source_invalid/invalid_count1；主协调按冻结行和纯函数重建、唯一主表/时点/字段前提及明确标为合成的反事实分支探针，验证拒绝来自critical_value_018:191。不能据此判断没有危急值或擅改身份合同。C01完整空输入只属于冻结测试副本，不是原患者完整无触发证明。

本批没有生产源码修改、DDL、病例/旧答案/启用/批准变更；两个独立服务已退出，未触碰他人8001。012独立正式回读与新任务成本门禁关闭，但真实缺项、独立临床复核、发布冻结仍缺。018没有独立报告/处置答案或Stage2运行，仍是输入准备。32条9+2+3+18分类、4条限定工程成果及临床签认/上线批准0均不增加。私有证据与独立审查索引见H21，患者正文/截图不提交。

## 二十二、首程候选撤回，018输入修复及023独立预期

2026-10-06用户批准H22三路小闭环，复用独立工作树、Sol6.1 medium，主协调限定路径整合并亲自复核真实输入/状态/调用/保存。D 6d6aa060c工作区中单首程Prompt候选通过离线合同及历史响应重放后，仅一次012正常入口整包正式运行。128计划对=125合法唯一结果+3执行失败，PG与正常浏览器认证详情响应逐值相同，四012原工程字段一致；未增加独立011/013/014临床验收。

C01本次合同合法且三条合规，但C06-013由H19/H21合规变不合规，C17-013由合规变资料不足。主协调按保存quality及逐字相同的[first_course_rules.py:451](D:/LLM/LX888/apps/medqc-web/backend/app/services/luxian_0916/first_course_rules.py:451)至472行反查：分别由inadequate和缺quality映射而来，不宣称新旧临床答案哪方正确，也不宣称Prompt因果已证明。C30另为transport_error/http_transport生成失败，不是合同失败。H19保护20项6差分，最近H21保护17项5差分，门禁失败。候选32行已精准撤回，实施前实际semantic_extractor逐字节一致，他人005/006改动不变；候选测试留ignored归档，不提交，不继续调Prompt或补跑。

真实模型qwen3.8-flash，思考开启/budget256，1POST、4generate/4attempt/4HTTP、重试0。三个已知响应5045 Token/28.920631647 API秒，另一次成本未知，PG/API标不完整1次、complete=False；不以任务25.824秒墙钟替代API时间，不计算完整成本节省率。主协调验证旧原件完整行、旧副本文书ID/冻结字段及八工程答案前后不变，列示28源码到退出未变。页面验证部分失败摘要与C01-013，C17逐病例查看404、未回退其他病例，不能称四例逐病例页面闭环。事件job关联缺口不变。

018已核当前原表实际主键(institute_id,patient_id,visit_id,document_id)，只保留Stage1和对应测试的最小修复：raw定位使用document_id，grouped不伪造父报告/ordinal明细身份，缺身份及有效PL/PH重复冲突仍拒绝。主协调实际D纯函数回放确认C16恢复一报告两真实明细、原项目/结果/单位/PL/定位保持，Stage2输入ready但无模型调用；C01冻结副本输出不变。126项聚焦回归及独立反例审查通过，只关闭归一化身份缺陷，不等于018最终规则、临床或上线验收。

023一次20SQL只读限定三候选，C02/C03各一真实麻醉记录与手术记录，经主协调亲读后，模型输出前冻结两条工程存在性正例。C05只有局麻线索且该范围麻醉查询为空，不能据此冻结不合规或不适用。正常副本创建必经新身份Bundle同步，追加写入授权尚未收到；未绕过入口，创建/工程预期PG写入/正式运行均0，四合成函数探针不增专项通过。后续需限定新身份Bundle授权及正式保存/回读，不重复原只读取材。

本批临时后端、Vite及验收页已关闭，未触碰他人8001。完整证据与独立审查索引见H22；失败候选与原产物保留，患者原文/截图不提交。互斥工作记录仍为9+2+3+18，4条限定工程阶段成果、临床签认0、上线批准0；018输入修复和023预期单列，不冒充新增整条通过。

## 二十三、023新Bundle授权已获，正常创建前发现DDL门禁

用户批准023最多两个新身份Bundle/必要同步，剩余一次任务及八调用额度。本批三树Sol6.1 medium并发准备，主协调亲自复核正常创建链及另外两路关键产物。不能继续把未执行原因写成“Bundle未授权”：当前实际阻断是正常同步[visit_index_service.py:98](D:/LLM/LX888/apps/medqc-web/backend/app/services/visit_index_service.py:98)调用19–44行无条件建表/索引。root隔离捕获当前原函数两DDL，实际PG/DDL为0；因普通异常会被同步捕获，在第一个创建POST前停批，不试错写入。Bundle三ensure现为只读；条件create_all仍需前置结构及总DDL护栏，不能据此声称全应用零DDL。

两真实麻醉正文最小投影DTO与原文逐值相同，假名/元数据仅隔离测试、不代表原患者或完整病历；新副本未创建、工程预期未写PG、正式任务未运行。已集中请求仅既有验收模式的visit_index只读结构门禁修复，默认生产行为保持，本批未自行扩大生产白名单或DDL授权。

018当前纯输入与H22一致，子代理90逐句草案保存6候选及17反证，主协调独立核23段原record_content连续引文、原行完整身份和当前允许分句。初次报告与复查报告不同，最早报告关联候选7:15、特异复查候选7:24均真实存在，但两事实先为unknown草案而非absent。主协调初次私有断言错误要求SQL三绑定，反查后留痕更正：daily/senior旧查询只绑定院名/visit，实际23原行三坐标一致；不扩称数据库层完整身份约束。关联、预期冻结及正式模型仍未闭环。

首程C06/C17三时点提供文书数组逐值相同，四引文在原栏目/模型输入命中；执行器相同、候选已撤回。C06 adequate仅工程候选，C17分析充分性保留争议；缺quality不是医生缺项或inadequate，不用旧模型输出补值，不能推Prompt因果。现有证据不足直接批准生产修复，不继续调Prompt或补跑。

本批0PG/0HTTP/0模型/0生产修改，未启动临时服务；只读准备完成而023正式门禁未完成，剩余额度未消费。证据见H23，患者原文/过程脚本不提交，不重复未变单测。32条分类9+2+3+18、4条限定工程成果、临床签认0、上线批准0均不增加。

## 二十四、运行时DDL门禁修复与实际结构阻断

用户另批批准最小门禁修复，复用两个Sol6.1 medium实现/独立证伪。只改acceptance_startup与visit_index_service及对应测试，生产净增60行；现有验收模式启动只读检查与运行时SELECT校验共享一个结构owner，按实际search_path/OID解析，不硬编码schema。缺表、九写入字段、三坐标主键或指定有效索引即失败；验收异常不再吞掉，normal原两DDL/尽量成功行为保持。合法INCLUDE非键列不额外拒绝。

主协调亲自审最终diff、运行索引SELECT和公共启动门禁：实际对象qc.visit_index缺latest_mirror_success_time、mirror_delay_base_minutes、sync_interval_minutes，当前索引符合。最终只读探针26 SELECT/2 SET、回滚、0DDL/DML，明确在创建前阻断。不能把代码门禁已修写成数据库结构已修或023已正式测试；正常同步在该PG结构上的真实成功也未证明。

红灯20失败/57通过，最终84项；主协调含原父结构保护97项通过，ruff、只检查lint通过。独立v2公开入口15项无阻断，主协调反查原JSON源绑定及四组normal/未设置模式的SQL/参数/返回/commit完全一致。测试内存SQLite夹具/既有本地demo初始化不冒称真实PG病例；全前端type-check/test:unit未跑。本批无正式服务、认证、副本/预期/任务写入或模型调用；023两新副本、一次正式任务、八调用额度全部保留。需要另行授权实际结构修复，不跳门禁，不执行DDL。

任务与证据见[最小运行时门禁](D:/LLM/LX888/apps/medqc-web/docs/plans/2026-10-06-0916-visit-index-acceptance-gate.md)。32条分类9+2+3+18、4条限定工程成果、临床签认0、上线批准0保持，不将基础门禁算新规则通过。

提交前编码检查8份暂存文本通过；本任务仅6路径限定提交，其他两份暂存文档不变。为避免lint-staged改写他人文件，本次本地Husky钩子关闭并手动补编码/lint，不改CI。

## 二十五、授权结构修复已提交数据库，023正式验收待执行

用户明确授权数据库结构修复。root只读核当前search_path实际qc、OID199967与版本46，并亲自审迁移47/短事务白名单。新增三列来自既有同步合同，未改变临床口径、资料owner、原九字段或同名public表。独立审查root初稿两个保护缺口在任何DDL前更正：OID锚及提交后type/null/default核验；root反查真实代码确认，不仅转述代理报告。

真实事务3ADD仅qc.visit_index、唯一技术版本UPDATE46→47，同事务原九字段/15原行、列元数据、主键索引、OID/filenode逐值不变；提交后另只读连接复核类型/空值/default30及迁移重入无DDL，公共启动门禁通过。实际DDL受用户新授权，不把本阶段写成0DDL；正式验收恢复零DDL。

迁移公开红→绿33项，root含原门禁117项通过（首次导入路径错误留痕后修命令重跑）、ruff通过，未运行全前端type-check/test:unit。此处只是结构工程修复；没有创建023副本、写预期/正式任务、调用模型或临床批准。两副本/一次任务/八调用额度仍未使用，runner身份/成本与证据合同审核进行中。

依据与证据见[结构修复及023计划](D:/LLM/LX888/apps/medqc-web/docs/plans/2026-10-06-0916-visit-index-schema-repair-023.md)。分类9+2+3+18、限定工程成果4、临床签认0、上线批准0均不增加，不把SQL修复或门禁通过当新增质控点验收。

## 二十六、结构修复提交完成，023创建阶段护栏停止

结构修复提交`0b7e4a39e`，117项聚焦回归及真实PG结构/原值回读通过。随后正式验证准备中纠正两个私有假设：正常非生产认证可用既有内存qc_manager，不要求新增PG账号；刷新裸SQL实际owner为qc，public仅存在性gate，不是需要再迁表。formal1/2分别17 SELECT+3 SET、56 SELECT+3 SET，均0写入/任务/模型；不覆盖旧产物或把准备误判列为生产缺陷。护栏最终47项离线反例由root独立重跑通过，正式预算未放宽。

formal3两次新副本创建请求已使用，正常启动及API login/me成功；创建阶段因`sample_update_old_or_unbound_id`硬停止。两次工程预期PUT、一次run POST、模型generate/SDK/provider调用均0，无023结果或页面回读验收。被拦statement/context未保存，原因码不足以证明真实旧对象更新或私有护栏误报；暂不作因果结论。hard exit未执行finally，不用离线join替身冒称实际退出已核验。

root独立37 SELECT/1 SET只读回读：两新身份原始材料、索引及全部Bundle均已保存；C02样本ready/synced，C03 pending/synced，无latest_job_id。两例冻结原麻醉/手术及旧raw_payload、冻结源码逐值不变，仅保护该明确集合。副本保留，不删除、补状态或重新创建；临时8003/3003和浏览器页关闭。日志放行868 SELECT/6 SET/28 INSERT/10 UPDATE、0 DDL，不等同全部提交凭证。

023仍为准备/创建阶段未闭环，不增加专项通过。分类9+2+3+18、限定工程成果4、临床签认0、上线批准0保持；结构修复不能代替023验收。后续先只读定位护栏边界并复用现有副本，不自动执行剩余额度。具体停止、纠错与私有证据见[本批计划实际结果](D:/LLM/LX888/apps/medqc-web/docs/plans/2026-10-06-0916-visit-index-schema-repair-023.md)。

## 二十七、023两新副本创建与PG/API回读完成

用户再次同意创建。私有护栏只修缓存ID误拒的合成缺陷，root独立49项保护及C缓存反例通过；WHERE、实际目标集合、来源和预算未放宽。实际formal3被拦现场缺失仍不倒推确定根因。root执行前又发现样本列表GET存在自动heal写路径，明确撤回“无简易恢复接口”的判断；普通池页面可能更新旧pending，本批不打开，仅按本批新visit限定认证API并核唯一ID/三坐标。

formal4两次正常POST创建成功，两新样本ready/synced，PG与两次认证API的raw/ID/三坐标/状态一致，无预期或latest_job_id。正常退出在guard内join及退出来源检查通过；root另32 SELECT/2 SET只读连接核样本/麻醉整行、索引及全部Bundle已提交，原两真实材料/旧预期、formal3两副本逐值未变。0 DDL、PG auth写0、无越界；临时服务无监听。本轮两创建额度用完，不继续新建，后续选formal4唯一新item/visit，不复用同名旧pending。

只关闭副本创建/保存链路，不算023专项验收通过。PUT/run POST/generate/SDK/provider HTTP均0、页面未复核、医学判定/规则结果/临床签认/上线批准均未执行；两新副本重复同两原材料，不增加独立真实病例覆盖。分类9+2+3+18、限定规则工程成果4、临床签认0、上线批准0保持。实际证据及纠错详见[创建闭环结果](D:/LLM/LX888/apps/medqc-web/docs/plans/2026-10-06-0916-visit-index-schema-repair-023.md)。

## 二十八、023正式任务进度护栏停止与受控续验

复用formal4两新副本，formal5两development工程预期PUT及一次正式run/job已保存；私有护栏随后`job_update_scope`硬停，模型generate/SDK/provider HTTP均0，没有023规则结果。root另只读16 SELECT/2 SET核原job running、run bound、items/failed保持初始NULL，两答案和原材料/旧副本/源码逐值不变。硬停没有finally/join，不冒称正常退出；不计新增验收完成。

冻结真实进度helper证明原guard不兼容`id=job AND status!=canceled`，属于私有工具合成红→绿证据；缺现场SQL，仍不宣称formal5确定根因。独立审查另发现新候选共享WHERE绑定可掩盖非白名单SET，root亲自离线复现后阻止使用，A另修精确SET列合同，保留旧归档，未改生产执行器。

root进一步6 SELECT/1 SET只读核原run/job整行和两答案未变、池latest_job仍绑定原job、该root_job_id无PG模型事件、无部分交付。选择在原正式验证范围内仅一次正常Worker同job重入：0新增PUT/create/run/DDL，最多4 generate/8 SDK/8 provider尝试含重试；不调用会清结果/成本的retry API，不手工修改任务状态。该机制全量重算而非断点续跑，当前尚未执行，须guard修正和独立审查通过后root运行。最终模型/结果/PG/API/页面证据另记，不提前更新完成数。完整方案见[023续验方案](D:/LLM/LX888/apps/medqc-web/docs/plans/2026-10-06-0916-visit-index-schema-repair-023.md)。分类9+2+3+18、限定规则工程成果4、临床签认0、上线批准0暂保持。

随后formal6完成正常启动/认证及原任务单次派发，实际在`public.running_record_bundle`新C03三坐标upsert前被护栏硬停，现场SQL及actual绑定已保存；放行504 SELECT/4 SET/2原job UPDATE，模型三数组0、无023结果/64验收。create/PUT/run POST新增0，未再第二次重入、清结果或手工修状态。两次硬停均不声称finally/join完成。root最后两个成功探针各36 SELECT/2 SET只读回滚：原材料/旧副本不变，新样本等于已保存预期、麻醉整行及九索引/Bundle创建字段不变；原job running/run bound、结果NULL/成本0。

两新running scene虽bundle-v6但当前纯可用性函数均False。root用真实PG冻结row及当前loader AST隔离重建load→再load→assemble→upsert（组装/保存均stub），结合实际SQL和0916读取入口确认空场景要求重装配，而护栏run阶段不允许Bundle写入。不是已确认policy漂移、旧病例改写、023医学判定错误或模型失败。PG时间比较最初误把naive INSERT参数与aware timestamp直接比较，已核会话时区后更正并留原结果，不把探针错误当资料变更。

93项聚焦Python、编码、只检查lint通过；V2 guard15项及B7项root亲跑、独立审查完成均只是工具证据。浏览器正常登录尝试前端15秒先超时、后端稍后成功，未有结果页面证明；不改前端超时/注入token。临时8003/3003及浏览器页已关闭。后续先核专项场景可用性和精确刷新范围，不直接放开Bundle或重复跑模型。分类9+2+3+18、限定规则工程成果4、临床签认0、上线批准0保持，023行已更新为正式启动未出规则结果，而非尚未创建。

## 二十九、023场景与原始证据链只读核定

三路只读/离线调查，D工作区HEAD20b560368，0新增PG/HTTP/模型/服务/生产修改。冻结两最小副本只有麻醉文书；running优先来源不含麻醉，真实装配重建仍空，final各一麻醉且可用。root独立使用当前可用性函数核原PG归档，并亲读装配来源/真实隔离脚本确认边界；不能以ready行存在当作内容完整，也不能推断实时资料始终未变。

现有原始读取能取得麻醉并支持023presence/原docID anchor；场景定位白名单却使running下麻醉送模候选0，final候选1。root亲读并另存真实函数离线执行结果，两存在性正例仍compliant；没有正式Worker/模型/PG保存，024完整性不能算通过，017–020的事件coverage也不是023来源门控。

“换成终末场景跑”的候选在入口核对后收回：验收RunRequest无scene，客户池按running收集；仓储依据真实出院信息决定记录scope，Worker优先record.scope。不能仅改job.scope、伪造出院资料或改整个池。force_refresh_if_empty=False也会改变0916读取合同，不为绕护栏修改生产。

另独立合成反例证明，麻醉源unavailable空数组被投影为anesthesia_performed=False，023错误返回not_applicable；root另以纯context+023消费者构造保护断言红。它不是formal6硬停原因，尚未修复，不知真实发生比例。下一最小闭环先修该来源门控；精准两副本正常running upsert的17字段及后续任务/预算须重新批准，不再次自动派发旧job。

172项现有聚焦测试通过，新增来源失败保护例仍红；结论和私有证据见H29。分类9+2+3+18、限定规则工程成果4、当前D完整验收0、临床签认0、上线批准0不变；只读调查不增加正式通过数。

## 三十、023来源空数组阴性门控局部修复完成

用户批准H29后的小闭环，复用三树Sol6.1 medium。root亲核调用链和旧合成反例、明确事实所有者与公开测试边界后，A首红→最小绿，最终input_context净增17行，独立测试26项。空麻醉字段只有严格complete且原值为有效空数组才能支持False；partial/unavailable/覆盖未知、字段省略及非法原值都保留None。显式True/已有阳性与原anchor不变；未知在既有模型合并后保持。未改formed、手术、出院、Prompt、装配、查询或执行器。

root独立198项聚焦测试通过、ruff通过，历史私有红灯也已绿。扩Worker/编排/失败交付为238通过/4失败；root分别用当前和5264b0075修复前投影隔离执行相同四018节点，均4失败且断言差分相同，明确不是本次投影变更造成，不推测或顺手修改018根因。不得将扩展回归写成全部通过。

B保存修复前四输入128native基线，修复后同输入保持。root源绑定首检发现B after早于新增一行说明，反查仅注释后另执行并保存最终源回放，独立重算原文书/Bundle/selector/全部32唯一结果逐字段相同；023四结果仍compliant且docID等于冻结原麻醉。两原材料两场景不是四个独立病例，其他源模拟空，不替代完整病例或模型准确率。C独立反例无阻断；022 arranged=False依赖同一错误阴性时会从不适用变未知，这个间接纠错已实测并明确，不算022验收。

本轮0PG/HTTP/真实模型/服务启动、旧任务派发0，没有修改工程预期、批准或启用。023来源门控局部修复单列为1项工程成果，原9+2+3+18分类、4条历史限定正式成果、当前D完整验收0、临床签认0、上线批准0不变。后续正常running定向Bundle写入与正式任务仍需新独立范围/授权，不自动重入已消耗权限的旧job。详见H30及其私有证据。

## 三十一、三路准备成果与023保护基线停止

用户批准023两现有副本定向running刷新、1新任务/4generate/8attempt含重试，以及018独立排障/032最多两例草案。复用三树Sol6.1 medium，无生产或正式测试修改。018四失败由raw fixture缺document_id进入Stage1 invalid，root亲读代码/实际trace，并独立重放仅内存补字段的候选，四Worker恢复原预期且22身份保护保持，共26通过。修正后Stage1输出与H22前旧函数消费旧fixture逐值相同，证明范围仅四夹具失败；一行正式测试修复仍待实施，不扩大为018临床正确。

032两历史原文先冻结后查run5，最终两例均unknown草案；root独立七条docID/时间/offset连续引文全部匹配，六完整引文入当前Prompt、一条复访连续引文不完整可见。它不证明所有复访内容被省略，也不把文书/出院/随访时间差异直接定医学缺陷。纯投影两例均有出院门控但缺语义完整性事实而gap；来源可来自discharge_record和相关病程，没有独立表不等于无权威材料，当前PG完整性仍未证明。

023私有guard错误schema/policy反例由root/C证伪后另v2收紧，33项root重跑通过。v2固定HEAD前置假设在app导入前停止，其他任务推进HEAD而65登记源码不变，root另v3保持逐字source==prepared及私有冻结，HEAD仅元数据；实际断言三探针和C独立单源漂移反例通过，没有放宽SQL/身份/预算。

v3在正式服务/认证/POST前保护材料断言停止，40 SELECT/2 SET、0PG DDL/DML、0HTTP/模型/新任务，正常finally guard内join和退出source核验保持。root首探针误按357行检查旧job，另存更正：实际356行旧材料不等，旧job/run完整行相同；真实差异只一旧保护副本bundle_status/updated_at，原文/答案/其他字段不变。改动者未知，不能归因自愈或Agent。app导入有本地SQLite初始化，不能称全环境零写入。

root另17条独立只读语句核两新sample/anesthesia/running等于停机证明、旧技术现值稳定及旧任务不变；运行包表启用触发器/重写规则0、RLS关闭。已请求仅技术现值另存保护基线后继续原预算，确认前不自行改基线或再跑。临时前端检查时已无监听，退出原因未证实，未终止他人服务。新任务及模型预算未消费，023正式保存/页面仍未闭环。9+2+3+18、原4限定正式成果、局部门控修复1、完整验收/临床签认/上线批准0不变；准备、反例和单测不冒充新增规则验收。H31保存全部停止/更正及root独立证据。
