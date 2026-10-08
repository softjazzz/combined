# 手术与麻醉全引擎验收第一轮（2026-10-08）

基线 `7b894dc84491b7b72eb096de58fe61f772cc0080`。范围20条0609现行04-*及5条0916（023–027），共25条。**本轮未验收通过；不新增临床签认或正式发布通过数。**

仅合成离线：0真实模型、0 provider HTTP、0 PG、0原始患者材料读取；不改生产、共享测试、TODO或提交。两个已有pending规则继续受正式phase gate约束。术前04-01-04/05只继承已有有限验证及保留争议，不重做专项探针。

## 当前确认阻断

1. **SA-01 / LX0916-024**：麻醉空源`unavailable/partial`仍投影`anesthesia_record_formed=false`，最终`not_applicable/trigger_event_not_present`；正确边界应保留事件未知。023同输入已修且返回`data_quality_gap/event_fact_unavailable`。这是历史明确保留的未修缺口，当前公开链确认。
2. **SA-02 / LX0916-024、025、026**：同源A完整、B仅空标题且明显未完成，受控提取器接受仅A的逐项事实后，build→merge→execute仍输出`compliant/required_document_complete`、公开anchor仅A。单A对照均合规；三项双文书反例均复现。证明单份合同不能覆盖多份文书，不证明真实模型实际错误率。

`semantic_extractor.py:1013`仅绑定被返回的单份文书，`surgery_consent_rules.py:324`据该份合同判病例；`input_context.py:130`仍把024空源形成事件投影False。完整输入/确定响应/实际事实/证据见专属合成产物。

## 本轮验证及未决冻结差异

首组11文件525 passed；扩展9文件468 passed、7 failed、4 deselected。累计993 passed、7 failed，不写成全绿。两组各1条既有Pydantic弃用警告。均使用`--noconftest -p no:cacheprovider`，跳过全局基础设施夹具。生成器为测试替身，套件内部模拟Token不能算真实调用。

6个存在性冻结失败涉及030/032（现04-02-02/04-03-01）的新增`surgery_trigger_kind`事实、032无触发文案及关联失败证据坐标差异，状态和原因码断言已先通过；未修改预期，未据此宣称临床误判。另1个MDT冻结失败：`technical_error/source_query_error`时仍公开`performed_surgery_confirmed=false, procedure_kind=unknown`，历史冻结明确无客户事实。独立合成脚本再次确认0调用；这是当前技术失败事实发布差异/风险，未证明临床结论错误。

12个0916新公开链合成探针：3个单份完整对照、3个多份缺覆盖反例、6个023/024空源readiness边界；另1个MDT来源错误独立复核。探针第一次JSON序列化遇到mappingproxy后修正记录输出，未改业务代码或状态。

## 逐条账册

所有历史病例数字均来自既有公开验收记录，本轮没有读取私有原文或复跑真实任务；离线回归证明工程边界，不代表新增真实金标。

| 规则 / 当前目录 | 既有证据 | 当前缺口与判定边界 |
| --- | --- | --- |
| LX0609-04-01-01 有手术医嘱但无术前小结 | 历史R02双轮30例存在性/关联验证；13例关联更正、17例保护不变。 [`记录`](../../../apps/medqc-web/docs/acceptance/2026-09-13-r02-029-surgery-event-association.md) | 单份实质文书/同台拆行有保护；同日源端漏第二台仍无法证明，本轮未复核历史原始病例。 |
| LX0609-04-01-02 除紧急抢救生命的急诊手术外，住院患者手术无术前讨论或术者未参加 | 正式typed术前讨论存在性、术者参与与紧急抢救例外已冻结。 [`记录`](../../../apps/medqc-web/docs/acceptance/2026-09-07-lx0609-surgery-document-freeze.md) | 多事件、源失败与空讨论离线保护存在；语义参与者/急诊豁免及临床来源覆盖仍缺独立当前金标。 |
| LX0609-04-01-03 四级手术术前讨论未开展多学科讨论 | 四级手术MDT有正式确定性冻结及事实/证据迁移记录。 [`记录`](../../../apps/medqc-web/docs/acceptance/2026-09-07-lx0609-surgery-mdt-freeze.md) | 当前source_query_error分支保留performed_surgery_confirmed=false，与冻结无facts不同；该分支测试失败且独立复现，尚不能批准冻结验收。 |
| LX0609-04-01-04 术前小结内容不完整 | 三例、四次既有已授权真实调用；92字段引用及限定语义复核、8/8状态及保存回读一致；337项已有保护。 [`记录`](../../../apps/medqc-web/docs/acceptance/2026-10-08-preop-bounded-real-validation.md) | C04/C12诊断充分性/术式归属争议、规则级自然unknown真实样例、泛化、客户PG及浏览器继续缺；本轮不重做专项探针、不新增真实调用。 |
| LX0609-04-01-05 术前讨论记录内容不完整 | 同批既有有限术前讨论验证；文书内容按单份核对，独立语义复核未发现新增确认缺陷。 [`记录`](../../../apps/medqc-web/docs/acceptance/2026-10-08-preop-bounded-real-validation.md) | 医学争议和泛化仍保留；状态一致不是全量医学充分性证明。本轮只继承历史结论，不重做已完成专项验证。 |
| LX0609-04-02-01 手术后24小时内是否完成 | 两台一份手术记录错误合规已有修复；20专属正式session→执行→归约→Finalizer例及134聚焦回归。 [`记录`](../../../apps/medqc-web/docs/acceptance/2026-10-07-surgery-record-event-coverage-fix.md) | 本轮104 gate及20逐台覆盖保护通过；独立当前真实多台手术记录时限、客户保存/API页面仍缺。 |
| LX0609-04-02-02 有手术医嘱但无手术记录 | 存在性facts所有权及目标surgery_record冻结，执行器拥有已实施手术触发。 [`记录`](../../../apps/medqc-web/docs/acceptance/2026-09-07-lx0609-surgery-presence-finalizer-ownership.md) | 本轮存在性旧冻结与surgery_trigger_kind新增facts不同；6个presence失败含本规则/032共享场景，不能写全绿或自动修改预期。 |
| LX0609-04-02-03 恶性肿瘤手术记录未书写淋巴结清扫情况 | 恶性肿瘤触发、淋巴结处理/未处理原因，由受控事实抽取后Python判定。 [`记录`](../../../apps/medqc-web/docs/acceptance/2026-09-06-lx0609-surgery-family-ownership-baseline.md) | 本轮gate套件含恶性/非恶性、否定及计划语气保护；抽取语义正确性、多台手术及真实充分性无新增独立金标，不以通用回归代替。 |
| LX0609-04-02-04 未记录植入物名称、种类、规格或型号、材质及数量等信息 | 当前主表pending_definition，原因implant_five_field_real_gold_pending；正式结果not_executed、空事实/空证据。 [`记录`](../../../apps/medqc-web/docs/acceptance/2026-09-07-lx0609-025-pending-legacy-evidence-audit.md) | 五字段口径已冻结，欠多台、文书缺失、字段冲突真实金标；直接执行器或shadow成功不代表正式发布通过。 |
| LX0609-04-02-05 手术记录非手术者签字（核对术者及签名医生） | 术者/签名资格不取提交人；2026-10-07补逐台覆盖、拒绝不同事件共用签名。 [`记录`](../../../apps/medqc-web/docs/acceptance/2026-10-07-surgery-record-event-coverage-fix.md) | 本轮20事件覆盖及gate保护通过；同台辨识依赖已有结构化身份，未补真实临床关联和正式保存/页面证据。 |
| LX0609-04-02-06 死亡患者无死亡记录 | 历史六例均无死亡触发；另有死亡文书迁移和合成触发/缺文书保护。 [`记录`](../../../apps/medqc-web/docs/acceptance/2026-10-07-round2-surgery-documents-audit.md) | 当前扩展执行与死亡mapping通过；历史无死亡阳性不能证明死亡缺记录的真实准确性。 |
| LX0609-04-02-07 会诊记录单未在会诊申请发出后24小时内完成 | 069历史已修正空申请时间缺口归因，既有Provider→native→binding→Finalizer真实回放保持data_gap且原因改为authoritative_time_missing；24小时时限未改。 [`记录`](../../../apps/medqc-web/docs/acceptance/2026-09-09-pending-069-empty-time.md) | 本轮069关联缺口与客户时间缺项文案8项通过；不能因物理位于手术目录而当手术证据，真实多申请/签名完成时间和保存链仍需专属验收。 |
| LX0609-04-02-08 死亡时间缺失 | 历史六例无死亡触发；2026-09-08另有076空正文source_empty及保存completeness解释修复、8例576项正式交付记录（整任务完成不等于全规则成功）。 [`记录`](../../../apps/medqc-web/docs/acceptance/2026-10-07-round2-surgery-documents-audit.md) | 本轮round2及extended通过；当前真实死亡阳性缺失、时间合法性和源覆盖仍未补，完成时间不能代替死亡时间。 |
| LX0609-04-03-01 有手术记录但无手术安全核查表 | 历史六例5合规、1关联失败，双手术单核查不反改冻结预期；按每台手术核对。 [`记录`](../../../apps/medqc-web/docs/acceptance/2026-10-07-round2-surgery-documents-audit.md) | 当前presence冻结在032无触发文案及association_failed公开坐标不同；状态未因此翻转，属于待核冻结差异，未重判真实C01。 |
| LX0609-04-04-01 无麻醉术前或麻醉术后访视记录（局麻除外） | 当前主表pending_definition，原因anesthesia_visit_sources_unavailable_customer_scope，客户源不提供访视故暂停。 [`记录`](../../../apps/medqc-web/docs/acceptance/2026-09-07-lx0609-surgery-document-freeze.md) | 直接执行器存在性测试不表示正式规则通过；需要真实源覆盖和客户重新确认供数范围，不能自动放开。 |
| LX0609-04-04-02 麻醉术前和术后访视记录填写不规范（局麻除外） | 第二轮空模板/非法时间/跨事件访视缺陷已有保护；N04/N08补前缀、相邻标签及空标签归属。 [`记录`](../../../apps/medqc-web/docs/acceptance/2026-10-07-n08-anesthesia-label-fix.md) | 本轮相关124+27+17+8测试通过；无业务键的单事件既有兼容仍允许，无多事件完整自然真实阳性金标及源覆盖证明，不外推全局关联正确。 |
| LX0609-04-04-03 无麻醉记录单（局麻除外） | 非局麻实施麻醉触发；历史R02两轮30例、五例独立预期相符，记录存在性不混入完整性。 [`记录`](../../../apps/medqc-web/docs/acceptance/2026-09-13-r02-038-anesthesia-record.md) | 本轮方法标签、计划/未实施、局麻、来源失败保护通过；多麻醉/跨手术独立缺记录当前真实覆盖仍缺。 |
| LX0609-04-05-01 术后三天无连续病程记录（包含术后术者查房记录） | 逐台手术的术后第1–3日病程、术者查房与精确引用冻结；观察窗口策略既有保护。 [`记录`](../../../apps/medqc-web/docs/acceptance/2026-09-07-lx0609-postoperative-fact-refs.md) | 本轮extended及postoperative mapping通过；病程可供哪些手术复用、同日多台和角色语义的独立临床金标未新增。 |
| LX0609-04-05-02 无术后三天内上级医师查看病人记录 | 权威手术结束+72小时与评价终点逐台判断；窗口未成熟不提前报缺，缺终点保持资料不足。 [`记录`](../../../apps/medqc-web/docs/acceptance/2026-09-07-lx0609-065-postoperative-window.md) | 本轮extended与round2时间边界保护通过；源端完整观察窗口和真实多台上级医师身份/查看记录仍缺当前独立验证。 |
| LX0609-04-05-03 无术后首次病程记录 | 每台手术关联首次术后病程，缺失证据仅引用未满足事件，既有最近已结束手术关联。 [`记录`](../../../apps/medqc-web/docs/acceptance/2026-09-07-lx0609-postoperative-fact-refs.md) | 本轮extended及postoperative mapping通过；最近已结束策略在同日多台/时间模糊的真实可靠性未新增验证。 |
| LX0916-023 无麻醉记录 | H33正式任务请求在INSERT前MemoryError/HTTP500停止，无新规则结果；H30来源阴性门控局部修复及两冻结正例。 [`记录`](../../../apps/medqc-web/docs/plans/2026-10-05-0916-unified-validation-progress.md) | 本轮26门控保护和空源公开链保护通过；真缺记录、独立麻醉触发、局麻、多麻醉/多手术关联及当前正式保存/页面仍缺。 |
| LX0916-024 麻醉记录缺项或描述不清 | H11两轮30例含16触发，整族9例变化、passed=false；无独立预冻结临床gold。 [`记录`](../../../apps/medqc-web/docs/plans/2026-10-05-0916-unified-validation-progress.md) | 本轮确认未完整读取空源仍record_formed=False→not_applicable；另确认双文书仅A事实可返回病例合规。 |
| LX0916-025 手术记录缺项或描述不清 | H11两轮各14资料不足+2不合规+14不适用，状态计数相同不能证明整族稳定；无独立预冻结gold。 [`记录`](../../../apps/medqc-web/docs/plans/2026-10-05-0916-unified-validation-progress.md) | 本轮确认双文书A完整+B空标题，受控单A事实可返回合规，B未核查；缺多事件覆盖合同、独立gold与正式回读。 |
| LX0916-026 手术安全核查记录缺项或描述不清 | H11资料不足6→2、不合规10→14，整族9例漂移；无真实输血阳性，条件仅合成保护。 [`记录`](../../../apps/medqc-web/docs/plans/2026-10-05-0916-unified-validation-progress.md) | 本轮确认双文书仅A事实可返回合规；逐阶段三方签字与真实输血/标本适用性、跨手术关联仍缺专项独立验证。 |
| LX0916-027 急诊手术缺主治及以上医师指示记录 | H0/H1/H8整包/事后审计；run5的30条均无法复核，无独立急诊触发专项预期。 [`记录`](../../../apps/medqc-web/docs/plans/2026-10-05-0916-unified-validation-progress.md) | 本轮60手术规则套件的泛化事件/未知保护不证明急诊真实性、医师职称和有效指示语义；需独立急诊阳性与事件关联专项。 |

## 专属产物与复核

- [机器账册](surgery-anesthesia.json)：25条规则、两类阻断、冻结差异、源码SHA256及本轮统计。
- 仓库根`.tmp/engine-audit-20261008/surgery-anesthesia/`：`probe.py`、`probe-results.json`、`probe-mdt-source-error.py`、`mdt-source-error-result.json`；均为合成，无患者原文。
- 复核：仓库根执行`python .tmp/engine-audit-20261008/surgery-anesthesia/probe.py`及MDT探针；不读取.env、不连接DB或模型。
- 后续先审阅SA-01/SA-02和7项冻结差异；任何修复需保持单文书正常、来源未知、真实多事件边界及phase gate，不能自动放开pending或改历史临床预期。

本轮保留真实死亡阳性、急诊上级指示、多麻醉/多手术完整覆盖、自然unknown、独立临床预期及正式保存/API/浏览器缺口。
