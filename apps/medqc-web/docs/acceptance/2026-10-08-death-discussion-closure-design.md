# RR-D02最小修复设计与离线验证

固定工作树源码基线`8c9df71af38c934570df6402f9251e046c489a98`。只读核对发现RR-D02控制流仍在：death_discussion.py先过滤无权威完成时间的行，仅全部无时才资料不足，已选最早晚讨论直接超时。该模块与当前集成树SHA256均为`14D851A864FDF6248BED3968B41AA25977C4D24E1C42291FA3EA6FC64851B60D`；未运行测试或模型，无PG、真实病例、env读取。

原审计冻结expectations.json SHA256 `AC8FA19A601AFB97E69593BA6667C6ABA804E61B15546CE63B72778044F619DB`，保持不变。原D02探针只给未知时间文书ID，没给record_content，不能据此证明真实讨论正文。新增专属测试在生产修改前冻结明确的合成非空正文反例；缺正文、明确空正文、真实非空正文分开。

批准文件独占：`backend/app/services/luxian_0609/extended_document/death_discussion.py`、`backend/tests/unit/test_luxian_0609_death_discussion_closure.py`及本文。禁止改native_extended_document_execution、customer_renderer、Finalizer、source_registry及其他owner文件。

## 最小决策

当现有最早有时讨论在168小时内，保持合规与该文书精确引用，未知时间候选不能整体污染为资料不足。当现有最早有时讨论已超时，而另有权威完成时间不可解析且record_content明确非空的讨论候选，返回data_gap/authoritative_time_missing，不再断言“最早讨论超时”。沿用现有无display_facts时间缺口结果，由正式入口保留来源事实引用，不新增结果语义或关键词。

明确为空/空白/None正文不满足此新增保护；没有正文列不冒认真实讨论，未知无正文+晚讨论保持当前结果，原只含时间的有时最小夹具仍按原合同判断。全部无时、无文书与成熟评价终点等既有分支不扩大。本修复仅使用现有\_row_time与\_clean，来源death_discussion已经允许record_content，无需改reader。非空标题模板是否有真实讨论内容尚无批准合同，本次不增加模板关键词或语义模型。

## RR-D01保留

评价终点现有文档称任务冻结的逐病例评价终点/评价截止日期，日期精度不得补00:00或23:59；Provider没有据此过滤未来文书。把终点扩展成文书可见材料截止尚未冻结，协调者明确本次不实施。只有9月10日讨论而评价9月3日的原偏差仍保留，不能因RR-D02通过声称D01关闭。合法未来任务评价日期不能凭机器now判无效。

## 测试预期

初冻测试19项：真实非空正文未知时间（None/空串/不可解析）与晚讨论两种顺序均资料不足6项；明确空正文候选不阻断晚讨论3项；缺正文单列1项；未知+晚+真实及时讨论两种顺序保持合规及精确引用2项；正常未来冻结评价终点1项；原最小有时夹具168小时与+1秒2项；无讨论未成熟/成熟2项；正式执行→归约→Finalizer分别未知+晚与增加及时记录2项。两条正式链必须0模型/Token，资料不足不能再出现超时48小时文案。

已有多死亡时刻由native死亡事实门控判冲突，本模块只有单death_time入口，不新建多事件关联合同。后续仅获测试槽后继承现有离线隔离runner执行新红测，再作模块内最小修订与聚焦保护；不全族测试、不启动Node/PG/真实模型。独立审计者先只读核对此未跑预期。

## 独立静态核对补充

原审计者已只读确认初冻19项测试SHA256 `CBEDA9D4F671BD2A0D34BEA9C84BCD48D89E9DD6DFBE7D4230CCAA4AAB0D00E6` 与原新增expected SHA256 `ABC6D5AF95129F3E5A1707F5D40AA1954F0BC47E615D9978B130FE23248354C0`，未运行或给出测试通过结论。其要求正文必须实际为字符串且strip非空；不能用\_clean把数字/布尔/对象转换成字符串冒认正文。新增4项非字符串占位值（数字、布尔、字典、列表）保持原晚判定，累计23项；原expected文件不覆盖。

实现计划仅在现有选定讨论hours>168分支、映射确定超时前，检查是否另有\_row_time不可解析且record_content为真实非空字符串的行；命中即沿用data_gap/authoritative_time_missing无display_facts返回。及时分支先行、不引入模板词或终点过滤。先获槽运行23项红测，确认业务预期失败后再编辑生产模块。

## 实施与红绿证据

按协调者唯一测试槽调度，先在未修改death模块的固定8c9df71af运行冻结23项，7 failed / 16 passed / 1 warning / 4.36s；6项真实非空正文未知时间与晚讨论对照及正式链无及时记录反例失败，实际均仍断言超时。随后仅在已选讨论hours>168分支加入8行严格字符串正文/未知时间检查，复跑23项新测试及16项既有051保护，共39 passed / 1 warning / 3.16s。正式执行、归约及Finalizer的资料不足与及时合规两例均0调用/Token；没有真实数据或模型。测试槽执行后立即释放，没有宽套件或前端全量重跑。

`.tmp/rr-d02/red.txt` SHA256 `68E106A78B4138C0A6661E743D401BD4E495D7BD7A5F9B1F20B3E20B1F7CA550`；`green.txt` SHA256 `DF76D38A52512BA616EDD2306EA7BB8F3F96E0D0D0098BD78F8D58CDBE207380`。runner继承IML01离线隔离：dotenv替换、拒绝.env读取/网络连接、允许asyncio本地socketpair，禁缓存与字节码；不接PG，不读取私有原材料。原审计冻结文件未覆盖。

两Python文件Ruff与git diff --check通过。前端源码与本树8c9df71af完全相同，依协调者资源指令复用`.tmp/iml01/lint-revision.txt`的相同源码lint证据（0 errors / 1214既有warnings，SHA256 `478FF8AC56E06A91572145C3BCD79A34B586BAF0DAF256E840865B34584A12B6`），不重复全应用门禁；本次staged encoding与真实Husky结果随提交回执披露。完整前端type-check/test:unit仍由IML02唯一负责，本文未取得结果，不宣称已通过。

RR-D02工程修复待原审计者在固定提交SHA独立复核，非临床验收；RR-D01继续开放，未将评价终点扩成文书可见截止。缺正文或非空标签模板仍不声称真实讨论有效性，未扩模板关键词、源投影或下游重判。
