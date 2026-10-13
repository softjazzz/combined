# 0916-023麻醉来源空数组门控 Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.
> 本机对应工作流：writing-plans、executing-plans和TDD；复用现有独立工作树，不创建新树。

**Goal:** 麻醉来源不完整且未读到记录时，不再把空数组投影成“无麻醉事件”，023通过现有执行器返回资料未知；保留冻结正例。

**Architecture:** 仍由现有programmatic evidence拥有源读取及source_readiness，input_context只投影事实，023执行器负责状态。只约束anesthesia_performed的阴性投影，以None保留未知并阻止后续模型False覆盖，不新增来源、状态、配置或编排层。

**Tech Stack:** Python、pytest、现有0916公开上下文/语义合并/规则执行入口；无PG、HTTP、真实模型或服务。

## 证据、待验证假设与边界

用户在只读调查后回复“ok”，批准本次来源失败门控小闭环，未批准新的数据库写入/旧任务重入。D分支codex/lx0609-tech-debt-20260730，实施前HEAD5264b0075；源码磁盘版本另冻结，不用HEAD代替未提交实现。

root已独立构造红灯：timeline含anesthesia_record=[]、source_readiness=unavailable，当前input_context.py:132投影False，023执行器返回not_applicable/trigger_event_not_present。其私有脚本为20261007-023-source-failure-red-root-private.py。该合成机制不是formal6硬停原因，不代表真实发生比例。

待独立证伪的实施假设：在既有事件覆盖优先级之后，只把“没有正证据、且不能证明来源完整为空”的anesthesia_performed设为None，即可关闭错误阴性，同时既有merge保留None不让模型重新写成False。不得把假设直接写成已关闭结论。

白名单仅backend/app/services/luxian_0916/input_context.py、新backend/tests/unit/luxian_0916/test_anesthesia_presence_source_gate.py，以及本文和统一进度表。生产增量预计不足20行；input_context现约374行，职责就是既有事实投影，不能迁成新Resolver/Bundle/覆盖平台。不改共享装配、读取/查询、Prompt、状态词表、执行器、保存、API、前端或其他规则合同。

## 事实语义

- 有麻醉记录：保留现有事件、presence、原docID anchor及显式事实优先级，不要求全源完整才能证明局部存在。
- 空记录列表且source_readiness严格为complete：保留现有False阴性投影；这不扩展为独立麻醉事件缺记录的医学验收。
- 空列表且partial/unavailable/缺少或非法readiness：阴性事件设None；源失败状态已出现但文书字段省略时同样未知。
- 显式阳性anesthesia_performed=True保留，文书存在性仍由既有链路决定；空来源覆盖不全时显式或模型False不能覆盖未知。
- 同时缺文书字段和该源readiness时，保留既有未投影行为，不凭空补事件。未知应存在于本次已尝试/已提供的来源事实中，而非新增全局兼容语义。
- 不修改anesthesia_record_formed、手术/出院事件或其他文书完整性。anesthesia_performed也被022使用，事实改正可使其依赖同一错误阴性的输入转为未知；需报告该间接影响，不能宣称022已验收或扩修其他规则。

## 保护集合及验收边界

两份C02/C03冻结原麻醉行和running/final包来自root formal6-stop-v2归档；对照为5264b0075时点未改的实际函数执行产物20261007-023-raw-evidence-path-root-private.json，不用更早正式结果当本次源码等价证明。两例已有023compliant/anesthesia_record_present及原docID anchor，均为工程正例，不是临床gold。

公开测试边界与用户批准范围相同：build_luxian_0916_context -> merge_luxian_0916_semantic_facts -> execute_surgery_consent_rules/execute_luxian_0916。不mock内部函数、不用私有判定函数证明正式验收。DB读取仅在冻结输入复核脚本中使用已保存行替身；测试不能连接真实PG。

### Task 1: 最小红灯与修复

实现A只拥有D生产/test两路径，先新增一个unavailable空数组公开链测试，要求023 data_quality_gap/event_fact_unavailable和event_value=None。运行并保存红灯，然后最小实现，原测试绿；不预写整包平台测试，不提交。source_readiness只从timeline现有字段取，None保留在event_facts，放在显式事实合并后保证空覆盖不全的False不能回流。

命令（D目录，PowerShell）：

```powershell
$env:PYTHONPATH = (Join-Path (Get-Location) 'backend')
python -m pytest --confcutdir=backend/tests/unit/luxian_0916 backend/tests/unit/luxian_0916/test_anesthesia_presence_source_gate.py -q
```

### Task 2: 保护与独立证伪

在首个红绿完成后增加partial/缺readiness/非法readiness、字段省略且源失败、complete空源保留not_applicable、正证据preserve anchor、显式True/False、模型False合并的逐步公开保护；相邻投影不变。C只拥有C树private反例/审查，先独立按合同证伪再审关键diff，不得扩大修复。B只拥有B树private冻结回放，先保存当前基线，修复后同输入比较状态/原因/关键事实/anchors及其他31条结果，禁止读取真实数据库或调用模型。

root亲审diff、独立执行新测试及既有四组聚焦回归，反查B实际上下文/来源/引文与原冻结麻醉，验证既有阳性结果和阴性complete未变。任何保护回退、额外文件改动或范围冲突立即停，不改工程预期。

### Task 3: 记录与提交后停止

root运行编码、只检查lint及上述Python测试；只提交四个白名单路径，私有患者产物不提交。暂存区有他人文档则路径限定提交，必要时仅关闭本次本地Husky，手动补检查并在提交说明记录，不改CI/他人暂存。

完成仅表示来源门控修复及离线保护闭环，023正式结果/PG/API/页面仍缺，完整规则工程验收、临床签认、上线批准数量不增加。下一次正常running Bundle定向upsert及原任务/新任务、调用预算需要新的独立方案与授权，本轮不得自动续验。

## 剩余风险

存在记录的权威性沿用现有输入合同，未解决多麻醉/多手术关联、独立“已麻醉但缺记录”触发源、源读取更宽坐标查询或实际来源失败频率。running目录不含麻醉而阻止共享质量抽取的问题仍在，不用本次023门控修复宣称024族闭环。未运行真实模型、PG保存、页面或完整前端type-check/test:unit。

024使用的anesthesia_record_formed仍沿旧投影，来源失败空数组下的024结果不因本修复改变；相关来源门控需另评审，不能宣称整个麻醉族的空源分支都已修复。

## 实际结果

最小公开链测试先红：root独立运行build -> merge -> execute_surgery_consent_rules，来源unavailable空数组实际not_applicable，断言资料未知失败；A保存首红。生产最终仅input_context.py净增17行（含一行中文说明），新独立测试文件212行/26项，不新增helper、来源、枚举、开关或查询。门控读取现有timeline.source_readiness及原始文书字段，只有严格complete的有效空Sequence支持阴性；字段省略、类型非法或非法行被过滤后形成的“空”都不能伪装完整空源。显式事件合并后保留True，否则设None；现有后展开合并令未知保持，不让模型False回流。anesthesia_record_formed、手术、出院投影及执行器均未修改。

root亲审关键diff和全部新测试，首例独立绿，并重跑此前私有红灯脚本得到data_quality_gap/event_fact_unavailable/event_value=None。新26项加既有上下文、手术规则、语义抽取及bundle读取共198项通过（0.66秒），ruff通过。扩展编排、Worker及共享抽取失败交付共242项时为238通过/4失败；不能写成242全绿。

四失败均是既有018 Worker测试。root另开两个隔离进程，分别使用当前build函数和B保存的5264b0075修复前函数，执行相同四节点：两侧均4失败，nodeid及断言差分逐值相同，实际为critical_value_source_invalid。替换仅内存中的投影函数，未还原或改写生产文件；不以原因码进一步猜测018根因，本批不修改018或其测试。该对照只排除本次投影修复造成这四个失败，不宣称整个历史测试集一直失败。

冻结保护：B先保存修复前4输入/128原生结果；两原麻醉行及running/final包真实归档，其他来源DB替身模拟空，无模型。A修复后B同脚本逐值比较通过。root首次最终源绑定检查发现input_context比B after多一行后补说明，拒绝将较早源码当最终源；亲读差分确认仅注释后，用同脚本另存root最终源after，重新独立计算128结果、32规则唯一集合、原行/Bundle/selector和私有输入完全相同。每个023仍compliant/anesthesia_record_present，原anchor文书ID与冻结麻醉document_id一致；其他31条在这四个输入上亦逐字段相同。不是四个独立病例，不证明完整Worker/模型或临床准确率。

C独立公开链13组及补充7组证伪无阻断，root亲读实际输出并核相应代码：None保留、有效complete空源仍False、显式True/现有阳性anchor和既有显式优先不变；其他上下文字段和024结果保持。022的间接影响明确为arranged=False加失败空源时，从False/not_applicable变None/data_quality_gap/event_fact_unavailable；arranged=True触发仍True。这是共享事实纠错，不宣称022验收。本地None也优先于模型True，这是既有merge优先级，本次不另改。

本次关闭的是023来源阴性投影错误及离线保护，不是023正式验收。无PG/HTTP/真实模型/服务启动，无旧run/job再派发、任务状态修补、工程预期或启用变化。当前D完整单规则工程验收0、临床签认0、上线批准0保持；新增023局部修复单列，不把测试数量加算为规则通过。

提交前check:encoding六份暂存文本通过，lint只检查通过（0错误、1214警告）、ruff及diff检查通过。本批没有前端/API类型边界修改，未跑完整前端type-check/test:unit，使用上述聚焦Python验收。两份他人暂存文档保留原blob；本次四路径限定提交并仅关闭本次本地Husky，防止lint-staged改写他人文件，理由写提交说明，手动补编码/lint，不改CI。

证据：[首红及实现](C:/Users/Coldplay/.codex/worktrees/lx0916-validation-handoff/LX888/apps/medqc-web/.tmp/0910-full-audit/20261007-023-source-gate-implementation-private.md)、[修复前32条冻结基线](C:/Users/Coldplay/.codex/worktrees/lx0916-independent-regression-20261004/LX888/apps/medqc-web/.tmp/0910-full-audit/20261007-023-source-gate-baseline-private.json)、[root最终源回放](D:/LLM/LX888/apps/medqc-web/.tmp/0910-full-audit/20261007-023-source-gate-after-root-private.json)、[独立候选审查](C:/Users/Coldplay/.codex/worktrees/lx0916-015016-acceptance-20261005/LX888/apps/medqc-web/.tmp/0910-full-audit/20261007-023-source-gate-review-candidate-private.md)、[018前后投影测试对照](D:/LLM/LX888/apps/medqc-web/.tmp/0910-full-audit/20261007-023-worker-018-baseline-check-root-private.py)。患者原文/坐标和一次性脚本不提交。
