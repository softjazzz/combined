# 0916 023正式回读与两路预期复核 Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.
> 本机使用已安装writing-plans/executing-plans，无该命名空间。用户2026-10-06以“ok”批准下一批及仅两个新副本身份的Bundle/必要同步记录。

**Goal:** 完成023两个真实存在性正例的当前版本正式保存/回读门禁，并并发补018事实工程预期、首程保护差分的只读复核。

**Architecture:** 沿正常认证创建及0916正式Worker入口，不旁路资料生成/规则执行/保存。仅复用三棵现存工作树，子代理准备可独立复核的私有产物，主协调负责SQL护栏审核、实际执行及最终验收。无生产代码改造，发现缺陷只定位，另批修复。

**Tech Stack:** Python、冻结JSON、PostgreSQL、正常FastAPI/lifespan与认证API、浏览器。

---

## 证据、假设与边界

基线D `9c10265ef`及实际未提交工作区；不能以HEAD替代完整源码。上一批[H22](D:/LLM/LX888/apps/medqc-web/docs/plans/2026-10-06-0916-next-011018023-batch.md)已提交018 Stage1身份修复，首程Prompt候选因保护回归失败撤回。

023 C02/C03各一份实际麻醉文书，独立手术文书有实施麻醉记载；两个工程存在性预期已在新模型前冻结，gold/clinical=False。当前input_context.py:129以麻醉文书形成anesthesia_performed，surgery_consent_rules.py:264消费presence=present。此为代码路径及已读原文证据；待验证假设：正常新副本能保持来源/事实定位并正式交付同一存在性结果。子代理须独立证伪，不由正例通过推导独立触发、真实缺失或局麻适用性已覆盖。C05不入本批。

018 C16身份问题已关闭，一报告两真实PL明细及90分句Stage2纯输入ready；报告/处置的独立预期未冻结。待验证假设：现有90分句中是否存在可唯一归属该事件的报告/处置证据；先原文审读，不把模型旧答案或015/016事实复用为018答案。

首程C06-013与C17-013差分及quality状态映射已由保存响应/结果和相同执行器证实，但新旧临床答案正确性及Prompt因果未证实。待验证假设：冻结原文是否足以支持确定工程预期；先独立反证，争议保持未签认，不重跑模型或改旧预期。

## 三路任务与白名单

### A：023正式准备与回读

责任树lx0916-independent-regression-20261004，复用cost_review_010012_20261006。只可创建本树.tmp/0910-full-audit/20261006-followup-023-*-private脚本/产物；不得改D生产、旧私有产物或其他任务文件。不是独占代码库，不回退他人修改。

1. 使用H22源JSON和冻结两正例，准备正常test-record DTO；最多两新副本，假名/隔离身份，保留原文并记录新旧文书坐标映射。只测试存在性，不把文书压缩投影称完整病历。
2. 逐项列明正常创建、同步/Bundle、工程预期及正式任务入口所需SQL表/字段/身份边界；对每条写入给出仅新身份/新对象或目标池计数/指针的保护。DDL、旧对象更新、全局恢复、超量、018Stage2一律停止。
3. 借鉴H22正常TCP/lifespan、认证、SQL/调用/HTTP预算观测，准备私有脚本；仅draft，未经主协调审查不得执行任何PG/HTTP/模型。
4. 主协调冻结实际源、复核权限与剩余预算后执行一次正常023任务，保留所有有效结果及执行失败，不因整包非目标失败重提。核64计划对（若两副本整包）、原生023状态/原因/事实/证据/建议、成本完整性。
5. PG及正常认证任务/规则API逐值比较，页面回读两个023目标；无临床签认、case_review、gold升级或启用。若单病例查看缺结果，明确记录，不用其他页面替代该门禁。

### B：018独立工程预期

责任树lx0916-015016-acceptance-20261005，复用prepare_018_offline_20261006。白名单为本树.tmp/0910-full-audit/20261006-followup-018-*-private；只读H21严格源及H22修复后输入，使用当前D Stage1/Stage2纯函数，不导入app.main，不联网/PG/模型。

1. 独立核事件时点、报告明细、允许坐标及来源覆盖，原Stage1/Stage2输入与H22保存值逐值对照。
2. 逐分句审读report_recorded/disposition_recorded，引用必须是原文连续子串、正确文书/分句/时间、与事件关联明确；不能由检验报告存在代替病程“报告已记录”。
3. 另存两事实工程草案及所有候选/反证、未知原因；独立预期先于新模型，gold=False、clinical=False、ready_to_apply=False，争议不自动选边。
4. 提交给主协调亲读与独立复核。本路0PG、0HTTP、0模型、0生产修改，不计018专项通过。

### C：首程差分只读复核

责任树lx0916-validation-handoff，复用cost_fix_offline_20261006。白名单为本树.tmp/0910-full-audit/20261006-followup-firstcourse-*-private；只读H19/H21/H22冻结Prompt/响应/结果与当前原文、执行器。

1. 明确每个比较对应时点及完整输入相同与否，不能仅用HEAD/状态数推导因果。
2. 对C06 differential_diagnosis_quality与C17 diagnosis_basis_quality独立审读，列支持/反证原文和实现合同，缺事实与inadequate分开。
3. 当前规范和已实现判据可解释时另存工程候选，否则写明未能定论；不写“院方标准缺失”或擅改人工预期。
4. 输出是否有足够证据另批最小修复，不形成新Prompt/模型/生产修改；无需重复未变单测。

## 执行授权与护栏

- 三路均Sol6.1 medium；主协调亲自复核关键产物，不仅转发Agent报告。
- 023使用原批剩余一次正式任务，最多8generate/attempt/HTTP（含所有重试）。两次副本创建POST与正常认证不算正式任务POST，但均单独计数和列白名单。预算是上限，失败不重提。
- 最多2新副本及对应样本项/新工程预期；新run/newleaf及其更新、对应观测、目标池计数/latest及同账号登录时间戳。新增授权仅两个新副本身份的运行/终末/领域Bundle与必要同步记录，不刷新旧病例、不全局装配。原件、旧副本、旧答案/结果、启用与审批不变，禁止DDL。
- 有效新身份与对象ID须在第一条写入前或同一次受控生成链中唯一登记；任何无法从SQL绑定参数反查范围的写入都先停止，不以字段名猜归属。凭据仅读backend/.env，不输出/落盘。
- 原 source材料只在已知两身份和必要来源内复核；不扩病例扫描、不改原文，不在病例不完整时声称整条质量判定。
- 018及首程只读已有文件；即便A失败，另两路仍完成授权范围内的独立准备，不挪用模型额度。

## 验收、文件规模与停止

无生产代码改动，不向巨型创建/编排文件加入职责，无新增事实所有者、平台或配置。脚本/原文仅ignored私有目录；docs仅主协调维护本文与统一进度表，不提交原文/截图。

023成功标准为两个预冻结存在性正例的正常创建、原生结果、保存、认证和页面证据闭环；负例/独立触发/局麻适用性仍未覆盖，不升格整条临床验收。018和首程只关闭预期/争议复核准备门禁，不补算通过数。

源码/材料漂移、越界写入、DDL、超调用、模型返回失败或业务差分均留原产物并停相关阶段；不为凑通过数改预期或重试提交。本批按限定路径更新进度/提交、报告剩余门禁后停止。

## 本批实际复核与停止记录

### A：新增Bundle授权已收到，但发现独立DDL门禁

不能再把023未运行原因写成“新身份Bundle未获授权”。用户已明确批准；本次未执行是因为正常创建[custom_qc_sample_pool_service.py:4462](D:/LLM/LX888/apps/medqc-web/backend/app/services/custom_qc_sample_pool_service.py:4462)调用ingest_sync_rows，该函数在[visit_index_service.py:98](D:/LLM/LX888/apps/medqc-web/backend/app/services/visit_index_service.py:98)调用19–44行的无条件CREATE TABLE/CREATE INDEX IF NOT EXISTS。主协调独立读当前源码与调用链，并隔离捕获原ensure函数的两条SQL；它们仍是DDL，不因对象可能已存在而获准。实际PG/DDL为0，不把代码路径复现写成数据库实际发生。

同步函数136–145行捕获普通异常；在执行时仅raise后继续创建会掩盖门禁，因此在第一个创建POST前停止。当前assembly的scene/domain ensure（849–866）及refresh_manager ensure（46–70）已经只读，未发现它们本身还有无条件DDL。另有服务及rule_validation的create_all(checkfirst=True)条件路径，须由既有acceptance前置结构校验和执行总DDL护栏共同保护，不声明整条应用链天然零DDL。

两DTO及原文/坐标映射已准备，麻醉正文547/495字与冻结来源精确相同；只一份真实麻醉记录的最小存在性投影，不称完整病例。假名、年龄/性别/科室等是隔离测试元数据，不代表原患者；原record_datetime为空，DTO采用submit_datetime并明确来源，不冒充原临床发生时点。旧手术独立实施证据仍在原来源归档，不转为新的事实来源。两DTO ready_to_execute=False；未创建、未写新答案、未POST正式任务、未登录或启动临时服务，预算全部保留。

已向用户集中请求独立最小修复：仅既有验收模式将visit_index运行时建表改为只读结构门禁，缺结构停止，normal行为保持。此项不属于本批生产白名单，尚未实施；不猴补跳过、不吞DDL、不自行授权DDL。

### B：018候选引文已定位，两个草案仍保留关联复核

当前D Stage1/Stage2实际源码及两个保存输入与H22逐值一致，C16仍一报告两PL、90允许分句，C01仅原冻结副本保护。子代理逐句形成90条审读标签，保存6候选及17重点反证。主协调另一进程重建当前纯投影并核23段引文：原record_content连续子串、分句、authored_at、实际原行身份与偏移匹配。不是新PG读取或模型回放。

原初次报告00:21:45与07:15:12复查报告不同。病程最早报告关联候选7:15含同报告其他血气值；最早处置候选7:24确有特异血气pH复查恢复的记载，不能贬成泛泛观察或“无处理”。但PL原值/通知未直接写在候选句中，唯一事件关联及模型实际可见上下文仍保留复核；report_recorded/disposition_recorded均为unknown草案，null坐标，gold/clinical/ready_to_apply=False。不得写成absent或临床缺陷，也不修改既有定义/Prompt/结果。

主协调首次私有验证错误地要求原SQL同时绑定三坐标，离线断言失败。反查原SQL后更正并留痕：这些daily/senior原宽查询只有institute_id/visit_id谓词；23引文对应实际raw行的institute_id/patient_id/visit_id逐值相符。不能把“实际返回身份核对通过”写成“数据库查询有三坐标约束”。独立更正说明另存，原产物不覆盖，不将准备范围升级为完整来源链验收。

### C：首程原文相同，医学充分性不自动选边

主协调从H19/H21/H22原报告独立解析C06/C17实际Prompt：单首程文书数组逐值相同，未截断；H19/H21完整Prompt相同，H22不同，执行器三时点及当前D逐字相同。四段支持引文均在原栏目及实际模型输入中连续存在；候选Prompt仍已撤回。这些证据只排除了提供原文漂移，不能证明Prompt的因果效果。

C06有相关鉴别对象和本例否定理由，可保留adequate工程候选但未签认；C17确有症状体征及影像依据，归纳分析充分性仍有争议，不选定枚举。H22 C17缺quality是抽取未取得事实，不是医生未写或inadequate；既有缺事实映射保持，不补值、不用历史模型答案充当gold。现有证据不足直接批准生产修复，停止调Prompt/模型重放。

## 最终产物与未完成项

- 023：[DTO/源映射](C:/Users/Coldplay/.codex/worktrees/lx0916-independent-regression-20261004/LX888/apps/medqc-web/.tmp/0910-full-audit/20261006-followup-023-draft-private.json)、[权限及阻断审查](C:/Users/Coldplay/.codex/worktrees/lx0916-independent-regression-20261004/LX888/apps/medqc-web/.tmp/0910-full-audit/20261006-followup-023-permission-review-private.md)、[主协调隔离复现](D:/LLM/LX888/apps/medqc-web/.tmp/0910-full-audit/20261006-followup-root-023-gate-private.json)。后两者不是完整可运行SQL写入guard，更不是正式验收。
- 018：[工程草案及引文](C:/Users/Coldplay/.codex/worktrees/lx0916-015016-acceptance-20261005/LX888/apps/medqc-web/.tmp/0910-full-audit/20261006-followup-018-expectation-private.json)、[审读说明](C:/Users/Coldplay/.codex/worktrees/lx0916-015016-acceptance-20261005/LX888/apps/medqc-web/.tmp/0910-full-audit/20261006-followup-018-review-private.md)、[身份口径更正](C:/Users/Coldplay/.codex/worktrees/lx0916-015016-acceptance-20261005/LX888/apps/medqc-web/.tmp/0910-full-audit/20261006-followup-018-identity-addendum-private.md)、[主协调独立复核](D:/LLM/LX888/apps/medqc-web/.tmp/0910-full-audit/20261006-followup-root-018-review-private.json)。
- 首程：[两字段工程候选](C:/Users/Coldplay/.codex/worktrees/lx0916-validation-handoff/LX888/apps/medqc-web/.tmp/0910-full-audit/20261006-followup-firstcourse-candidates-private.json)、[三时点复核说明](C:/Users/Coldplay/.codex/worktrees/lx0916-validation-handoff/LX888/apps/medqc-web/.tmp/0910-full-audit/20261006-followup-firstcourse-review-private.md)、[主协调独立反查](D:/LLM/LX888/apps/medqc-web/.tmp/0910-full-audit/20261006-followup-root-firstcourse-review-private.json)。

本批0PG/0HTTP/0模型/0生产修改，不重复未变单测，不提交患者原文或过程脚本。两路只读准备已完成，023正式保存/回读仍未完成；三路不是三条规则通过。互斥工作记录仍9+2+3+18，4条限定工程阶段成果、临床签认0、上线批准0。剩余一次正式任务/八调用及两副本授权未消费，不自动挪作其他任务。
