# 0609主开发会话中断接续计划

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.
> 执行说明：以上为计划模板入口；执行采用当前可用技能和工具，不因别名缺失安装框架。本文件是中断接续增量，沿用既有收尾计划、86条目录账和冻结证据。

**Goal:** 从中断时的真实工作树状态接续0609验收收尾，先关闭输血043–047及病程正文065/067的当前工程缺口，再按既有台账补足剩余修复、真实语义及正式链路证据。

**Architecture:** 集成树维护唯一成果账；候选保留在原隔离工作树，按文件分配唯一写入者。固定候选版本后独立复核、逐笔集成，集成版本补跑受影响保护集。

**Tech Stack:** Python/FastAPI、现有事实抽取与规则执行器、隔离SQLite、Vue、Git worktree。

## 一、已核实的接管起点

核对日期：2026-10-08（America/Chicago）。原会话：`01a084f5-2ccb-72b3-83ad-8720fc296a3d`。

| 目录（均在F:/MedQC-worktrees/） | 当前分支 | HEAD | 本轮实际状态 |
| --- | --- | --- | --- |
| qc-integration-20261008 | codex/qc-integration-20261008 | 4757e4dee | 写本计划前干净 |
| qc-fix-critical-v2-20261008 | codex/qc-fix-transfusion-family-20261008 | 944650db9 | 7个已跟踪修改、3个新增文件 |
| qc-fix-ledger-20261008 | codex/qc-fix-course-body-20261008 | 0683dfb9e | 10个已跟踪修改、5个新增文件 |
| qc-fix-chemo-v2-20261008 | codex/qc-fix-chemo-local-facts-20261008 | fac4ef67c | 5个已跟踪修改、3个新增文件 |
| qc-fix-privacy-v2-20261008 | codex/qc-fix-scope-six-20261008 | b5d0991a2 | 干净 |

`qc-critical-gaps-20261008`、早期A/B/C/D修复树及D盘冻结树继续保留。目录复用过，不能按目录名推断当前任务；以分支和实际差异为准。

本轮读取了历史、Git状态、收尾计划、归属台账和输血候选设计/源码；没有重跑测试。97项专项通过、265通过/91失败、正文别名7项通过均是历史结果，不写成本轮实跑。

历史最新汇报为80条有实质审查证据、25条存在已集成修复子项，均不代表整条验收完成。覆盖叠加表固定于较早的1958ae3bb，ownership的integration_head仍指向2d66663b6；两者须增量对账，不能覆盖后续成果或直接当作当前统计。

## 二、范围、调度与接续原则

- 仅0609，共86项目录；0916、助手功能和无关UI不进入本轮。默认范围沿既有配置，重新核对后登记，不为完成统计修改启用范围。
- 继承原反例、正常保护、已集成提交和有效证据；只对相关变化补验，不重新派86条全量审查。
- 用户明确要求禁止硬编码修复：不得增加病例、文书ID、特定药名/数字、测试编号或特定答案分支；不得靠扩关键词、调整冻结医学预期消除失败。修复须落在权威数据来源、可泛化事实关系和调用合同。容量等工程限制复用既有权威合同，新增限制必须说明来源并验证边界，不用特殊数量补丁。
- 最多4个修复者；最新closure-ownership.json规定重型测试最多1个，覆盖旧计划中的2路。Git提交/Husky同样串行。
- 用户新增修复轮次上限：同一根因最多3轮“实现修改＋验证”，基线复现不计。3轮仍未通过，子代理停止修改并向root提交逐轮差异、失败证据、根因判断和未解点；第4轮须root重新审查方案决定，不得改名或拆分同一根因重置计数。
- 首批只安排输血和病程两条工作线；化疗先做候选差异及反例对账，再决定补修。实施前确认旧会话代理及相关测试进程状态，不从旧owner名称推断仍在运行，不直接终止未知进程。
- root负责集成、总账及共享文件协调。Renderer、Finalizer、rule_contracts.py及目录JSON按整文件唯一写入者串行交接，不能仅因修改不同规则就同时写。
- 保留患者材料私有存储边界。离线修复使用既有合成材料；后续真实模型批次先核当前有效授权、完整输入、身份检查和硬预算。历史耗尽批次不复用。
- 本轮计划交付不包含推送、部署、数据库写入或新模型调用；实施到相关阶段按已有有效授权执行。

## 三、接续任务与出口

### R0：固定三份候选及增量账

**文件：**
- `docs/acceptance/engine-audit-20261008/closure-ownership.json`
- `docs/acceptance/engine-audit-20261008/closure-issues.json`及`.md`
- `docs/acceptance/engine-audit-20261008/catalog-coverage.json`及`.md`
- `docs/acceptance/engine-audit-20261008/next-batch/coverage-progress-current/overlay.md`及其已有JSON

步骤：
1. 在各修复树记录分支、HEAD、tracked diff、未跟踪文件清单；为实际修改的源码、测试、设计生成哈希清单，保留原候选。
2. 检查局部AGENTS与运行环境，确认无人同时写入后再分配新owner；旧owner只保留为历史。
3. 按问题核对候选提交与集成树的祖先/补丁关系，避免cherry-pick重复成果。记录路径级差异，不整树覆盖或丢弃未提交修改。
4. 归并4757e4dee以前的后续证据，纠正过期状态与集成头字段。原初审层、工程修复层和真实验收层分别保留。

**出口：** 三份候选都有可恢复内容及明确owner；每项能追溯“基线→差异→冻结预期→旧实跑”；缺日志/manifest明确列缺件。R0完成后直接进入R1/R2，不再等待下一次“继续”。

### R1：输血043–047，最高优先级

**工作树：** `F:/MedQC-worktrees/qc-fix-critical-v2-20261008`。

**核心文件（相对于该树）：**
- `apps/medqc-web/backend/app/services/luxian_0609/transfusion_performance_scope_v1.py`
- `apps/medqc-web/backend/app/services/luxian_0609/native_transfusion_execution.py`
- `apps/medqc-web/backend/app/services/luxian_0609/transfusion_result_mapping.py`
- `apps/medqc-web/backend/app/services/luxian_0609/customer_renderer.py`
- `apps/medqc-web/backend/app/services/luxian_0609/canonical_result_finalizer.py`
- `apps/medqc-web/backend/app/services/luxian_0609/rule_contracts.py`
- `apps/medqc-web/backend/app/data/luxian_0609_rule_contracts_v1.json`
- `apps/medqc-web/backend/app/data/luxian_0609_rules_v1.json`
- `apps/medqc-web/backend/tests/unit/test_luxian_0609_transfusion_family_scope_closure.py`
- `apps/medqc-web/docs/acceptance/2026-10-08-transfusion-family-performance-scope-design.md`

步骤：
1. 收回原356项测试的命令、nodeid、失败原因和产物。以“旧调用桩合同变化、正文/时间兼容、第9份容量边界、真实判定/证据回退、其他待定位”分类；91是测试失败数，不当作91个缺陷。
2. 先复跑已落盘正文别名保护，核实content、record_content、assembled_text、raw_text及优先级；摘要字段不得冒充完整正文。
3. 针对旧入口时间读取补最小反例：实施时刻、开始/结束、记录时间各保留语义；不能以record_time替代实施时刻。
4. 从原同族第9份文书用例冻结预期，验证当前MAX_DOCUMENTS=8的影响。设计能覆盖完整候选的有界方案：优先在既有单次调用和字符预算内支持正常多文书；若确需分批，先明确总调用/Token上限、结果覆盖和失败语义，再调整合同。不得简单扩大常数后宣布解决，或把原正常例改成资料不足。
5. 逐类修复并运行最小保护；旧fake只适配新增调用次序/响应协议，原病例、预期状态、缺项、证据和正常多时钟断言保持。
6. 复验计划/取消不能补齐实际文书、unknown与真实缺陷混合、失败缓存及一次共享抽取、原理由/成分抽取、单选与组合预算、原041/042/048/049及070保护。
7. 原同族集在固定源码上完整重跑；新增失败全部解释或修复。后续才检查SQLite新实例保存回读及非法状态/计数拒存。

**首个精确命令：** 在该树`apps/medqc-web/backend`中使用已核定Python环境执行：

```powershell
python -m pytest tests/unit/test_luxian_0609_transfusion_family_scope_closure.py -k 'legacy_complete_body_aliases or promote_preview or full_body_precedence' -q
```

**随后：** 同目录运行该测试文件全体；原356项命令从历史日志恢复后写入本任务记录，不用新挑选的小集合冒充同族全回归。运行前检查现有测试隔离设置，保持离线。

**出口：** 原第9份和正文/时间兼容反例关闭；原正常保护无回退；调用预算与实际一致；无未解释的候选引入失败。独立复核固定版本后才能集成。TR-044-MULTI原manifest缺失及其他业务残留仍单列，不能一并宣布关闭。

### R2：接续病程正文065/067

**工作树：** `F:/MedQC-worktrees/qc-fix-ledger-20261008`。

**核心文件：**
- `apps/medqc-web/backend/app/services/luxian_0609/course_body_fact_extraction.py`
- `apps/medqc-web/backend/app/services/luxian_0609/native_extended_document_execution.py`
- `apps/medqc-web/backend/app/services/luxian_0609/extended_document/discharge_course.py`
- `apps/medqc-web/backend/app/data/luxian_0609_phase1_rule_contracts_extension_v1.json`
- `apps/medqc-web/backend/app/data/luxian_0609_phase1_rules_extension_v1.json`
- `apps/medqc-web/backend/tests/unit/luxian_0609_course_body_test_facts.py`
- `apps/medqc-web/backend/tests/unit/test_n10_course_body_controlled_facts.py`
- `apps/medqc-web/backend/tests/unit/test_n10_course_body_scope_boundaries.py`
- `apps/medqc-web/docs/acceptance/2026-10-08-n10-course-body-controlled-design.md`

步骤：
1. 先审现有15个改动/新增文件，尤其已修改的6个旧测试，核对是否只适配抽取合同和夹具；原医学预期变动逐项解释。
2. 继承纯标题、签名、模板空壳反例；保护“医生签名：继续观察”等非姓名正文，不以短汉字正则删掉有效记录。
3. 复核正文最小语义抽取；时间、事件归属及最终状态仍由程序判定。缺少原行身份/时间时不编造元数据。
4. 冻结后运行新测试、原065/067保护、相邻068缺时间和证据坐标映射保护；模型失败/非法响应、调用上限和保存回读纳入验证。
5. 如需Renderer/Finalizer支持，由root在R1锁释放后串行处理；避免直接合并同名共享文件的旧版本。

**聚焦命令：** 在该树`apps/medqc-web/backend`中：

```powershell
python -m pytest tests/unit/test_n10_course_body_controlled_facts.py tests/unit/test_n10_course_body_scope_boundaries.py tests/unit/test_n10_course_template_body.py tests/unit/test_067_068_missing_time.py tests/unit/test_luxian_0609_predischarge_course_body.py -q
```

**出口：** 有效正文不被误删、模板不冒充正文、原缺时间与引用身份约束保持；技术失败与确认缺失区分；独立复核后提交。R1/R2代码调查可并行，测试占用同一个槽。

### R3：化疗候选及其他既有剩余项

**工作树：** `F:/MedQC-worktrees/qc-fix-chemo-v2-20261008`。

**核心文件：** `apps/medqc-web/backend/app/services/luxian_0609/chemotherapy_local_dose_facts.py`、`native_tumor_pathology_execution.py`、`tumor_pathology_result_mapping.py`，`apps/medqc-web/backend/tests/unit/test_luxian_0609_chemo_local_dose_binding.py`及`docs/plans/2026-10-08-tp-d02-chemo-local-dose-binding.md`。

1. 原候选保持隔离，核对两个语义反例与旧回归失败，并确认N13已集成部分未被回退。
2. 用同输入对照候选和集成基线，先解释跨药剂量归属、未知与真实缺项的变化。
3. 方案明确后才排补修；目录JSON和rule_contracts.py等待R1锁释放。
4. 从原问题账领取其余确认缺陷：检查身份剩余合同、疑难讨论触发、手术关联、出院带药、死亡讨论及隐私CLI可信身份来源。每项先核后续补丁，已闭子项直接继承；业务争议、缺manifest和工程缺陷分开排。

**出口：** 候选能否集成有具体反例与保护依据；不因已有37/42等局部结果合并未关闭候选。

### R4：逐笔集成与当前证据更新

1. 每项形成中文独立提交、父版本、改动路径和测试记录。提交前检查暂存区，仅纳入本任务文件。
2. 按本批实际依赖次序集成；无共享依赖且先完成者可先合入，不人为等待另一整批。
3. root亲自检查关键diff及状态、事实、引用、建议、模型调用量，集成树重跑受影响保护。发现回退先保留证据并修正，不覆盖其他成果。
4. 同时更新原86行目录账及问题状态，记录工程关闭/真实语义待验/医学争议/正式链缺口。目录数、审查数、修复覆盖数、验收数分别统计。

### R5：真实语义与完整链路验收

1. 依据最新台账准备最小真实验证批次，优先覆盖新增或变化的输血、病程、麻醉、化疗抽取，以及CT/PATH/PROMPT074既有受影响项。纯程序问题不额外制造模型调用。
2. 每批冻结代码、原始输入范围、评价终点、独立工程预期、完整送模内容及已知身份检查。确认有效批次预算后执行；已保存旧响应只能支撑其原输入/版本，不能冒称新调用。
3. 对真实输出逐项核对事实、事件、状态、引用、文案，保留首调失败、恢复和不一致结果；医学争议列具体待裁定问题。
4. 固定候选SHA后验证正式创建→执行→发布→保存→新实例/API回读→页面证据与导出，并覆盖取消/重试/历史结果及规则范围。复用有效链路证据，只补相关变化。
5. 按仓库要求运行编码、Lint、类型、前端单测及相关Python检查；资源不足按最低门禁执行并记录未跑项，不能把历史encoding失败和OOM写成通过。

**最终出口：** 86项目录均有与发布状态匹配的证据和结论；拟启用规则的确认阻断关闭，适用的语义、正式链和人工裁定完成。暂停、撤默认、样本不足不计作通过；候选包与验收SHA一致。

## 四、下一次实际执行的最小批次

依次完成：R0候选冻结与owner接管 → R1正文别名7项复验及91项失败归因 → 第9份文书/旧时间入口最小修复 → R2旧测试差异核对。首个交付点是可审阅的输血兼容性修复及受影响回归，不再开展全量重复审查。

本计划阶段只写本文件。未创建新工作树、未重派旧代理、未修改生产候选、未重跑测试；实施证据在执行时追加到原任务账。
