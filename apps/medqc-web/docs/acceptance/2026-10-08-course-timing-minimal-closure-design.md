# CT-02 候选病程时间缺口工程闭环与 CT-01/03 后续设计

实施基线 `bb3d0b5c3762ea7a0c8aa0580af8ec666794347b`。CT-02 已按 root 批准的窄范围完成候选时间缺口、公开事实/状态和文案修复，保留成熟确定 C/NC，聚焦 166 项通过；尚待固定提交独审。RR-PUB 哨兵修复、DD-F01 与 074 路径冻结。CT-01/03 仍为只读后续设计，未重审全规则；无 .env、PG、网络或真实模型访问。

本项仅实施 **CT-02：候选病程时间缺失不能证明完整未触发**。原独立冻结已明确 `data_gap`，无需选择 CT-03 空正文的临床缺陷口径，也无需引入 CT-01 语义抽取。三项均为同一规则 `LX0609-03-02-01`（旧序号 050），应分问题提交，不能把一项工程收敛称三项全部关闭。

## 固定依据与原反例

证据根为 `F:/MedQC-worktrees/qc-integration-20261008`：

- `docs/acceptance/engine-audit-20261008/course-timing.md/.json` 已确认 CT-01/02/03；0916 排除范围及 CT-R02 提前讨论关联争议均不纳入本轮。
- `.tmp/engine-audit-20261008/course-timing/expected.json` SHA256 `37ec08e8d766b9a071bd0bc60f7ae3ead925239ff22225c0c9181a1da9285752`，执行前冻结。
- 同目录 `probe.py` SHA256 `a06d10955fd3782d48e1491a69c8a4a282a60bb472f570844c361fd13baa010b`、`observed.json` SHA256 `6400e591ca012c801f9a41b32d4cc473f1ee79404842792274d1bf66cc1a1ee1`。本轮只读，不改或重跑。

原探针共同入院时间 `2026-06-01 08:00:00`，病程 document_id `SYN-COURSE`，常规病程时间 `2026-06-08 09:00:00`：

| 问题  | 原输入/探针                                                                                                                    | 原冻结预期 → 已观察输出                             |
| ----- | ------------------------------------------------------------------------------------------------------------------------------ | --------------------------------------------------- |
| CT-01 | `050_negated_marker`：“目前不存在诊断不明确的问题。”；`050_planned_marker`：“如后续诊断不明确，拟进行疑难讨论。”               | 两项 NA → NC/required_document_missing              |
| CT-02 | `050_missing_course_time`：“目前诊断仍不明确。”，不设置病程时间                                                                | gap → NA/trigger_absent_complete                    |
| CT-03 | `050_blank_discussion`：已过七天病程“目前诊断仍不明确。”；讨论行 SYN-BLANK、record_time=2026-06-09 09:00:00、record_content="" | data_gap_or_non_compliant → C/requirement_satisfied |

原 CT-03 期望有两种允许结论，不能把它自行改写成已冻结的唯一 NC 或唯一 gap。后续若选安全 gap，需 root/独立审计另附精确预期，不覆盖原冻结。

## 当前业务与来源合同

`rule_master_v1.json:420` 明确“诊断不明确（入院后7天）未书写疑难病历讨论”，active/customer_confirmed；业务基线 v1 第142行（旧050）记录批准临时口径。旧001–049 CSV 不覆盖050，不能从它推导新医学口径。

目录位于 `app/data/luxian_0609_phase1_rules_extension_v1.json:255`：病程、疑难讨论，依赖入院时间/诊断不明确事件/讨论记录，事件触发文书存在性，executor_type=program、prompt_version=none、rule_version=2026-08-02。执行覆盖为 `luxian_0609_phase1_rule_contracts_extension_v1.json:3`：extended_document/native_async、program_only/0、typed_shadow_v1、golden_gate pending。不是主 contracts JSON 缺条目；编译器会合并 phase1 extension。CT-02/03 可保持现模型预算；CT-01 如需语义提取必须另批准受控事实、Prompt、合同和调用上限，不能偷偷在 program_only/0 路径调用模型。

`source_registry.py:550` 的050 support 恰为 inpat_registration、admission_record、daily_course_record、diffcase_discussion_record。`source_evidence_reader.py:253/:586` 白名单提供：

- daily：document_id/title，正式文书时间四字段，作者/提交者/签名相关字段、record_content。
- discussion：document_id/title、正式文书时间四字段、record_content。
- `AUTHORITATIVE_DOCUMENT_TIME_FIELDS` 是 record_time、record_datetime、submit_time、submit_datetime；`authoritative_document_time_value:830` 按既有优先级选原值，`extended_document/shared.py:21/:36` 解析并将带时区时刻转换医院时区。

当前来源没有050专用的 current_diagnosis_uncertain/assertion_context/current_problem_id，也没有 discussion_completed/body_presence 受控临床事实。`EvidenceMaterialStore` 证明来源查询、行数和快照一致且未截断，**不证明每行正文可用或语义充分**。不能把 SQL 行存在、文书标题、作者签名或来源 COMPLETE 变成“已形成有效讨论正文”。

## 三项准确责任与可用事实

以下行号以本固定 HEAD 为准，原报告的2304/2309/2327已因前轮局部变更移位；责任仍在050分支，没有横跨其他规则。

| 项    | 当前责任                                                                                                                                                                            | 能以结构化数据判定的部分                                                                | 必须保留/补齐的语义合同                                                                                                                                                                      |
| ----- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| CT-01 | `extended_document/difficult_case_trigger.py:31` has_current_uncertain_diagnosis；native:2323消费布尔触发，2343–2346据讨论行输出 C/NC。`_material_text:987`还可能含标题及其他字段。 | 来源可读、文书坐标和形成时间、时间相对入院是否满7天。                                   | 当前整体诊断仍不明确、已否定、历史已解决、未来条件、局部病因未明及不同问题归属是语义事实。当前布尔词命中不能证明这些事实。禁止追加“拟/未/计划”等词表宣称关闭；现无正式结构化状态可直接复用。 |
| CT-02 | native:2320–2332在候选筛选中把 `_row_time is None` 排除；2339–2340把空候选视为完整未触发；2349–2361随后还生成无触发facts。                                                          | 四权威时间缺失/不可解析；入院时间有效；某候选不能定位于七天窗前或后。无需模型推测时间。 | 时间未知时只能说“既有触发器候选的时间条件未证实”，不能据此新确认诊断不明确，也不能确认未触发。CT-01语义风险继续单列。                                                                        |
| CT-03 | native:2343–2344仅 diffcase_rows 非空；2360把物理行数当 discussion_count。                                                                                                          | discussion源不可读/截断、无行、有行但正文缺键/None/非字符串/空串/纯空白；可读非空正文。 | 非空是否讨论本次诊断问题、是否只是计划/否定/复制标题、结论是否充分和提前讨论是否相关，均不能靠非空证明。窄修只阻止空白行证明C，不新增“已完成”词表或时间关联医学限制。                        |

## CT-02 批准的最小实施方案

先保留诊断候选，再独立按现有 `_row_time` 与 admission+7days 分为可定位满窗、可定位未满窗、不可定位三组；使用现触发函数，仅暴露“候选时间资料缺口”。不得用现在时间、入院时间、document_id、标题内日期或其他业务时间补造病程时刻，不修改共享时间解析器/别的规则。四合法时间别名和带偏移同一时刻沿既有合同消费，不追加容差；高优先时间原值非法时不偷偷改成低优先时间。

判定顺序应先保留 source_error、入院缺时的旧 gap，再处理已经可定位的既有成熟强候选：无讨论仍保留原 NC、有讨论仍沿旧 C。额外一行缺时不能掩盖另一行已确定的成熟缺陷；可选缺口摘要必须说明待核行，不给 NC 改原因。不因为另有讨论表行就把只有缺时触发候选的病例判C：讨论行无法证明该未知候选已满足七天适用条件。无成熟强候选且存在相关候选时间缺口时输出 `data_gap/authoritative_time_missing`；只有可定位未满窗候选或旧合法无候选时保留原NA。局部原因待查路径仍保持原 diagnosis_scope_uncertain，不在本项改成确定整体诊断。

客户事实需新增050专用时间缺口形态（名称可在实施时冻结，例如 `uncertain_diagnosis_course_time_gap`）：有效 admission_time、正整数 candidate_course_time_gap_count、现有 discussion_count；它表示无法完成时间定位，**不声明已满足临床触发**。已确定旧 C/NC 如混有缺时候选，允许追加安全计数摘要，旧无摘要构造与正常旧facts全等兼容。原正文、document_id、原始内部payload均不得进入公开facts。缺口锚使用实际消费的合法文书/来源引用，无ID只用既有source/snapshot合法锚，不制造ID或把整包充当精确文书。

`difficult_case_result_mapping.py:39/:73` 现只接受两kind且不允许050 gap解释，单改执行器会被 Finalizer 原有一致性检查变成 technical_error，或仍输出“未发现触发”误导文案，因此需要050限定合同/文案闭环：

- native_extended 仅050候选分组、状态/facts/消费证据；不改CT-01触发算法，不触碰别族。
- difficult_case_result_mapping 仅新时间gap形态/可选缺口计数白名单及状态自洽：新kind只许data_gap，伪C/NC/NA、空/未知状态、零/负/bool计数、未知枚举拒绝；旧C/NC/NA/局部uncertain无摘要兼容。
- customer_renderer 仅050时间缺口与已确定结论的额外缺口说明：“病程权威时间缺失/不可解析，无法判断是否位于入院满7天之后，请核对源系统时间及同步”，不声称不存在诊断问题、不催补已经存在的讨论、不要求医生倒签。
- Finalizer 当前 RR-PUB 冻结，**只有 root 另授锁后**才可必要时给050新gap kind加窄公开status校验，调用mapping既有检查器；不得改变通用None/sentinel、其他050形态/其他族门禁。保存层/API不改。
- 新专属测试与本文修复记录；source_registry/总表/目录/Prompt/共享解析器/Reducer无需改。

建议批准 CT-02 上述四生产边界加专属测试/文档后，独立审计先冻结原missing时间反例、known成熟NC+missing混合保护、各合法别名/时区及公开反状态预期，再给测试槽红→窄修→绿。测试只用fake/禁止模型（调用0）、正式执行→Binding/归约→Finalizer/文案→合成SQLite新实例回读。旧050六个执行保护与mapping旧facts/非050冻结保留，不机械改旧fixture。

## CT-01 与 CT-03 后续收敛边界

CT-01 暂不实施。来源若可提供经验证的“当前整体诊断状态/语义断言/问题归属”可先使用结构化状态；本树现白名单没有，不能虚构字段已可用。若改为最小受控语义抽取，应区分 present/absent/unknown、assertion（肯定/否定/条件/计划/历史）、整体/局部scope，绑定唯一来源及原句坐标，由Python校验时间/覆盖再判；unknown不能当缺少讨论，不能用另一诊断已明确抵消当前独立不明问题。需独立Prompt/预算与fake失败保护设计，属于下一项，不夹带在CT-02。

CT-03 原业务唯一可冻结底线是“空白行不能证明C”。来源record_content缺失/None/空白优先设计为正文可读性gap（不会催医生补写已存在文书），但需root确认工程状态及独立追加唯一预期。有效非空正文只证明形成材料，不自动证明临床相关/充分，相关性/提前讨论CT-R02保持争议。纯标题不代替正文，多个空行不能因数量判C；空+可用正文可保留旧C并说明空行未用作完成证据。建议另提交CT-03，不与CT-02一并重写050执行器。

本段 CT-01/03 后续方案仍待 root 审批；本轮 CT-02 合成工程验证不等于临床/模型验收。

## CT-02 实施准备补充

root 已批准只实施 CT-02：native050、difficult_case_result_mapping、renderer050、新专属测试/本文。RR-PUB 固定独审37项通过后，root另释放并授予Finalizer窄锁，只许050新kind或附加候选缺时计数调用既有status匹配，不改bb3 sentinel或任何公共其他逻辑。

专属测试 `test_luxian_0609_difficult_case_time_gap_closure.py` 已在生产修改前冻结准备；此时尚未运行。它保留原050_missing_course_time字面输入/独立gap预期，另覆盖讨论存在不能代替缺时证明、四权威别名/七天秒边界/同一时刻时区表达、成熟NC+缺时两顺序、成熟C+缺时安全摘要、缺时局部候选不确认为整体诊断不明、非候选无时不造缺口、源错误/入院缺时旧优先、真实ID与无ID引用、严格计数和公开状态、合成SQLite新Engine/新Store回读。CT-01/03原反例保持开放，不借该测试更改原预期。

## CT-02 最终实现与证据

生产路径限四项：native仅050分支，difficult_case_result_mapping只050合同，renderer只050，Finalizer仅050公开状态一致性十行。执行器先保留既有强/局部候选，再检查四权威时间；无可定位成熟强候选且有缺时（含不可解析）候选输出data_gap/authoritative_time_missing；存在成熟强候选则保留既有C/NC和原因，增加candidate_course_time_gap_count及安全缺口说明。正常旧facts没有追加字段。讨论行存在不证明未知时间条件成立；CT-03空正文判定未改。

新kind `uncertain_diagnosis_course_time_gap` 必须具有有效入院时间、空成熟强记录时间列表、非负非bool讨论计数、正整数非bool缺时计数；仅允许data_gap。既有check+附加计数只能保持原成熟记录/讨论计数对应C或NC；旧无摘要兼容，局部scope_uncertain不能借新增计数变为确定结论。公开读回对空/未知/矛盾状态拒绝，不变RR-PUB sentinel及其他规则。

消费证据附加引用只定位当前使用的成熟强候选/缺时候选及已计数讨论；无ID或重复ID只保留已有来源锚，不伪造文书。无ID专属保护同时核对daily source snapshot_ref属于fact_refs、候选材料实际可读、无无关病程引用以及客户customer_evidence为空/省略。真实ID用例确认对应真实document ref和客户坐标；没有公共projector改动。

验证按root唯一槽串行，结束即时释放：

- 可信红56项：26失败/30通过，2.92秒，`.tmp/ct02-closure/pytest-red-frozen.log`。失败分为13执行缺时/混合摘要、2未满窗/局部缺时候选、2证据定位（在NA先被阻断）、6合同、3保存（执行/摘要先被阻断）。原050_missing_course_time独立冻结输入/预期未改。
- 首次绿164项：155通过/9失败，`.tmp/ct02-closure/pytest-green.log`。其中8为新文案虽保留gap但出现“不能确认已触发或未触发”而命中文字禁止断言，改为直接说明时间条件无法核对；另1是新无IDfixture将解释字符串误当证据列表，改读customer_evidence并加强合法锚/空坐标保护。中间166项158通过/8失败发现通用structured_suggestion覆盖专属缺时建议，随后加仅050新gap kind的五行保留条件。原测试和医学预期未机械修改。
- 最终166项全通过，3.58秒，`.tmp/ct02-closure/pytest-final-green.log`。组成新56、旧050执行6、旧mapping3、旧renderer050两项、Finalizer70、RR-PUB29；56已在166内，不重复累计。SQLite正常写入→销毁Engine→新Engine/新Store回读gap/混合NC/混合C，保留状态/原因/事实/文案/合法证据；真实模型调用和Token为0。
- 初次红24失败/32通过中，1个fixture将合法evidence.field_path=record_content字符串误当raw透传，纠正为真实字典key检查；SQL三场景增加状态/计数前置断言后重新红产生上述26失败。保留`.tmp/ct02-closure/pytest-red.log`，不将fixture错误冒充产品失败。新测试红冻结SHA `76257e49eae27936df3bb6a35e339e0a6445dcaf81bc77f0ba0b550abbcbbf96`；后续仅修证据列表读取入口并加强无ID断言，没有改变missing gap/成熟NC独立预期。
- Ruff四生产+新测试、git diff --check通过；冻结验证`.tmp/ct02-closure/frozen-verification.json`确认native050以外逐字节不变、Finalizer只新增十行、触发词模块/共享解析器/来源注册/目录/合同/旧050测试/RR-PUB专属测试冻结。1147个前端输入hash逐一一致，复用批次lint 0 error/1214 existing warnings证据；此前type-check因资源压力正常停止，未确认完成；全量前端unit未运行，均不冒称通过。

提交限定六路径（上述四生产、新专属测试、本文），须root独占Git/Husky槽并真实hooks/encoding。`.tmp` runner、日志、冻结校验不提交。本工程结论只覆盖CT-02：CT-01否定/未来条件语义、CT-03空讨论正文以及CT-R02提前讨论关联口径继续开放。没有新增模型调用/重试、目录发布、共享时间解析、其他规则或临床时限变更。

精确五行 renderer 保留条件位于 `render_luxian_0609_customer_result` 的 DATA_GAP 下、structured_suggestion 覆盖条件中：

```python
or (
    decision.rule_id == "LX0609-03-02-01"
    and safe_customer_display_facts
    and safe_customer_display_facts.get("verification_kind") == "uncertain_diagnosis_course_time_gap"
)
```

原因是新gap的建议已明确核对源系统病程时间，但后续通用结构化整改建议会把它覆盖成“入院7天后疑难病例讨论记录的核对资料”，丢失具体缺口并泛化到文书/关联。仅对该新kind保留已形成的专属建议，050旧缺入院时间、旧source_error/旧无摘要和其他规则的通用建议行为不变。最终166已验证此条件，不再重跑宽回归。

最终专属测试SHA256 `9f92b5ab957f7bf5434e02251069dcf31b71598673a0b41c8bdf0a2e28a801e2`。root 已批准独占Git/Husky槽，仅上述六路径中文提交，真实hook日志 `.tmp/ct02-closure/commit.log`；固定提交后生产停止写入等待独审。
