# DD-F01 / 063 死亡诊断范围收口设计与工程记录

2026-10-08。独立树`F:/MedQC-worktrees/qc-fix-critical-v2-20261008`，基线`b85b49882bcdab5703ddacf54225c671bac353da`。主协调批准063局部作用域修复、必要来源及客户事实/文案合同；原DD-S01、独立新增冻结和旧死亡测试输入/合规预期均保留。全程真实模型调用0、PG/网络连接0、.env读取0。工程替身不代表临床或模型验收。

**063明确包含死亡诊断：可信权威死亡类型或明确死亡上下文成立时，独立核对死亡诊断，不因没有正常出院记录而跳过。** 正常出院与死亡诊断分别筛选；无法可靠选择范围时交付资料不足，不推断缺死亡诊断，不让死亡时刻冲突掩盖已确定的内容不一致。

## 依据及原反例

- `backend/app/data/luxian_0609_rule_master_v1.json:529`，active/customer_confirmed的质控点明确为“出院诊断或死亡诊断错填、漏填、顺序错误”。`docs/0602/泸县0609质控点-业务标准基线-v1.md:153`也包含死亡；现行`LX0609-我方口径标准汇编.md:59`要求既有结构化事实和病案首页主次排序口径。本项不新增医学排序算法。
- 集成树`docs/acceptance/engine-audit-20261008/discharge-death.json`冻结DD-F01/DD-S01：可读死亡记录SYN-DEATH、无discharge_record，mr死亡诊断甲与同文书书写死亡诊断乙冲突，应non_compliant，旧结果却not_applicable/trigger_absent_complete，文案“本次尚未形成出院记录”。原输入在`.tmp/engine-audit-20261008/discharge-death/supplemental.py:8`，未追加正文或记录时间改变原反例。
- 旧`test_063_compares_death_diagnoses`两侧可信结构化类型均为死亡诊断且同名；discharge_record只有record_time占位，没有明确存活断言。独立根审确认权威typed死亡类型本身可证明范围，unknown登记及记录时间占位不否定，因此旧输入/合规预期不修改。早期草案“缺death_record应gap”的建议过严，已在实施前撤回，没有机械给旧fixture补死亡证据。
- 审计者追加8项独立冻结`F:/MedQC-worktrees/review-artifacts/dd-f01-closure/typed-death-scope-independent-freeze-v1.json`，SHA256 `ba15b3e8b125c725a8ac8c973959ef2ad9d121a6fb36d06020c39e69177656f4`：typed死亡同名/错名、unknown登记无death_record、明确在院/存活矛盾、权威死亡/出院混合歧义、死亡时刻冲突、旧记录时间占位保护。原DD-S01没有覆盖。

## 来源与局部实现

现有discharge_record_diagnosis批准类型、序号、名称、document_id等字段，native reader按机构/患者/住院号直接查询，没有JOIN出院记录。故死亡诊断书写资料可独立读取，不新增death_record_diagnosis表、查询字段、Prompt、模型调用或目录条目。

063内部support新增inpat_registration/death_record，让单规则正式Evidence Session和Binding确实读取与允许引用死亡上下文；已有discharge_record/mr_diagnosis保留。旧精确集合测试正面按已批准合同增加这两项，不把它称为无效旧测试。mr_diagnosis已观察时仍是唯一权威，源不可读绝不回退diagnosis；只在未声明mr的旧正常出院回放保留无类型行兼容。

局部范围选择规则：

| 证据                                                                 | 处理                                                           |
| -------------------------------------------------------------------- | -------------------------------------------------------------- |
| 可读死亡记录、明确登记死亡事实，或可信唯一mr权威仅含精确死亡诊断类型 | death，只比较死亡诊断行；记录时间占位不反证                    |
| 明确在院/存活登记与死亡事实/权威死亡类型矛盾                         | scope_conflict/data_gap，不任取一侧                            |
| 权威同时含死亡/出院类型且无明确死亡上下文                            | scope_conflict/data_gap，不合并序列                            |
| 没有可靠死亡依据但可读正常出院记录且类型无冲突                       | discharge，仅比较出院类型；书写额外死亡行不补齐出院诊断        |
| 明确在院/存活，无终末触发，来源完整                                  | not_applicable/trigger_absent_complete，不代替其他规则判缺文书 |
| 状态未知、来源不足，无法确定终末范围                                 | scope_unknown/data_gap或对应来源gap，不默认为死亡/不判缺       |

死亡时刻不参与063内容比较；可读死亡文书或明确死亡标志已成立时，即使时间缺失或冲突，仍比较诊断。既有共享death_context、医学时间规则和其他规则不改。

两侧名称多重集/顺序合同保持：内容确定不一致先报non_compliant，即使顺序不可比较；同名但缺可靠多诊断序号、名称缺失或诊断表无可用行保持data_gap。063不凭空表判死亡记录缺失，也不借正常出院材料消除死亡诊断缺陷。

新增上下文来源只在本次范围判定需要时阻断。正常出院范围已可靠且权威/书写出院诊断可读时，death_record/inpat_registration缺表对应source_unavailable不得拖成整体技术失败；三种组合保护均已通过，不拖正常出院结果为gap/技术失败。

## 事实、文案及定位边界

仅063原`discharge_diagnosis_consistency_check`/`discharge_diagnosis_data_gap`两个kind支持可选diagnosis_scope=death/discharge。旧无scope事实默认原出院文案，普通出院native也保持原字段全等，只有death显式scope；新枚举严格，非法类型/值和内部载荷拒绝。选择death时文案为权威死亡诊断/书写死亡诊断，其他旧事实保持原文案。

新增authoritative_gap枚举scope_conflict/scope_unknown只能用于data_gap事实，written_gap必须None，不允许带chosen diagnosis_scope。它表示来源/范围不能可靠核对，不表示医生没有补写既有内容。Renderer仅消费已验证事实，解释来源不一致或范围依据不足，不读取材料、重判状态或要求补写已存在内容。

公开保存回读入口原只校验出院族事实schema，不能看见scope gap与伪造status矛盾。16项真实公开入口红测证实空/未知/technical/uncertain/not_executed/compliant/non_compliant/not_applicable均被接受。主协调另行批准Finalizer仅063+这两个新gap的窄谓词，调用既有出院族status校验；新scope gap必须data_gap。其它Finalizer、其他规则状态逻辑不扩。

消费行的真实document_id沿现有精确引用链；无ID首页诊断只能保留合法source snapshot锚点，不造ID或伪装逐行定位。混合无ID mr来源可核与真实death文书精确引用，已验证公共投影保留SYN-DEATH/death_record坐标且不生成虚假出院父文书。原DD-S01没有正文/记录时间，验证真实fact_ref并禁止虚假出院定位；有合成正文/记录时间的独立用例验证完整坐标。未修改共享投影；其无法表达的其它父子歧义保持定位缺口，不暗中扩大。

## 允许改动与冻结

本项仅：native_extended中063及其诊断scope筛选、source_registry中063 support、discharge_result_mapping中063两类事实及新gap状态谓词、customer_renderer中063两类文案、Finalizer上述窄谓词、新专属测试/本文，以及旧native测试中的063来源集合两项增量。旧死亡fixture不动；074两data、专属test/doc均与固定b85逐字相同，目录发布状态不变。

临时`.tmp/dd-f01/freeze-verification.json`验证native删除063分支与仅供063使用的selector后，其余区域逐字相同。Ruff与diff check静态通过。前端源码未改，继承本批1147文件冻结及先前lint证据；全量前端typecheck此前因资源限制结果未确认，unit未运行，不冒称通过。

## 红绿记录与交付边界

- 最初35例红26失败/9通过，其中一条无death记录但typed死亡预期过严；已保留日志、在根审后撤回，不把它作为业务回退证据。
- 正确独立冻结后的43例红34失败/9通过（1 warning，3.07秒），`.tmp/dd-f01/pytest-red-frozen.log`。
- 首次局部实现加公开状态保护69例：51通过、18失败；16项为公开入口真实状态漏洞，另两项为保留“存活+权威死亡类型”冲突预期和无ID mr混合坐标问题，均按根审正面修复/补齐保护，`.tmp/dd-f01/pytest-first-green-public-red.log`。
- 70例专属绿全通过（1 warning，3.74秒），`.tmp/dd-f01/pytest-green.log`。包括原DD-S01及8项独立冻结、合法scope兼容、非法字段/状态拒绝、隔离SQLite新engine+session保存回读合规/不合规/gap与客户API投影、混合source/docrefs真实坐标。真实模型/PG/网络为0。
- 新73项加出院事实/公开边界、诊断排序、死亡/出院交付边界、Finalizer及Renderer旧保护共663通过（1 warning，4.25秒），`.tmp/dd-f01/pytest-protection.log`。其中新增3例正常出院可选上下文source_unavailable均保持C。
- 原native063保护7通过、1失败：普通出院旧facts全等因新增可选discharge scope字段发生差异。按主协调确认，普通native不新增字段，保持无scope缺省discharge；旧事实断言不改，death显式scope。最终短槽复验73项新保护全部通过（1 warning，2.36秒）与8项旧原生保护全部通过（406 deselected，1 warning，1.89秒），`.tmp/dd-f01/pytest-final73.log`及`pytest-final-native8.log`。663项共同保护与最后73+8复验存在重复，分别记录，不相加冒充独立总数。

固定SHA后交独立审计重跑DD-S01及新增冻结，工程关闭不等同客户临床签认。

提交仅上述八批准路径，使用真实Husky、编码最低门禁与本批冻结前端lint证据；只有hook通过的固定SHA才交独审。提交输出保留`.tmp/dd-f01/commit.log`，不以工程绿测先行声明DD-F01已独审关闭。

最终有效日志SHA256：红43项`659e7e258080c78265364ad42213708c984a0623acf480a1c1197029659cbf66`；公开入口红`327376b4fde6393c5e9075a252ad3c279b0bd4cc555103c15f7677f06f9e26c8`；共同保护663项`9c71aa2bab23b11015822a754e81518797122a67f57643dabc7553ec3fd2d25b`；最终73项`350ceed5110e43e7e95fa06b38e6af931fa17578dddfad9de4af88de53be0fe5`；最终旧8项`dd788ca06228d1b845721cd485c39916b467f82afb60e58b4a6fd0624108cd94`。
