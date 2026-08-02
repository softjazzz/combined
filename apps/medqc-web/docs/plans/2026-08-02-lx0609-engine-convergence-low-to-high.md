# LX0609 质控引擎后续收口 Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use executing-plans to implement this plan task-by-task.

**Goal:** 按难度从低到高完成 LX0609 剩余规则族迁移，使当前结果只经过 `Bundle → Native → Canonical Envelope → 保存 → 单一 API`，并让每条合规、不合规、不适用和数据不足结果均有可解释事实。

**Architecture:** 不新增通用规则 DSL、事件图或第二套事实存储。每个规则族仅抽取自己的最小 Fact、Association、Applicability 和 Decision，复用现有 Source Observation、规则合同和 Canonical Envelope；一个规则族验收并提交后才进入下一族。

**Tech Stack:** Python、Pydantic/dataclass、SQLAlchemy/PostgreSQL、pytest、现有 LX0609 Native 执行器、CanonicalQcResultEnvelope、CodeGraph。

---

## 0. 执行原则

### 难度与依赖

| 顺序 | 批次                  | 难度   | 原因                                                   |
| ---- | --------------------- | ------ | ------------------------------------------------------ |
| 1    | 6A 基础时限与病程收尾 | 低     | 已有事实模块和测试基线，只处理定义明确部分             |
| 2    | 6F 扩展文书           | 低至中 | 主要是文书存在性、确定性时间和适用性门控               |
| 3    | 6C 会诊               | 中     | 需要申请、意见、执行记录的 episode 关联                |
| 4    | 6B 检查检验与病理     | 中高   | 需要报告聚合、阳性/危急值及病程响应关联                |
| 5    | 6E 抗菌药与肿瘤       | 高     | 依赖客户药品字典、用药意图和语义事实                   |
| 6    | 6D 输血               | 最高   | 跨医嘱、申请、检验、输注、文书、收费的多源事件关联     |
| 7    | Task 7–9 全局收口     | 依赖型 | 必须等待全部规则族稳定后删除旧链、优化性能和设发布门禁 |

### 并发策略

每个规则族最多安排三条并行轨道：

1. 调用链和数据源只读审计。
2. 验收 fixture、失败测试和真实病例基线准备。
3. 前两项结论明确后，由单一实现轨道修改共享执行器和规则合同。

禁止多个代理同时修改 `rule_contracts.py`、`source_registry.py`、`executor_registry.py` 或同一个 Native 执行器。规则族之间不并行迁移。

### 每族统一完成标准

- exactly-once 派发，规则不得漏执行或重复执行。
- 适用性事实不矛盾；资料缺失不得伪装成不适用。
- 数据不足使用客户可懂的具体缺口。
- 合规和不合规均返回简明事实、关键时间/数值及定位证据。
- 同一源资料只观测一次；同一语义事实最多一次受控 LLM 调用。
- 验收矩阵通过，并至少使用两份脱敏真实病例回读 Envelope 与单一结果 API。
- 当前规则族完成后删除已确认零调用的局部兼容分支，独立提交。

---

### Task 1：完成 6A 基础时限与病程收尾

**范围：** LX0609-007、008、009、016、017；018 保持当前已收敛口径。

**Files:**

- Modify: `backend/app/services/luxian_0609/native_course_quality_execution.py`
- Modify: `backend/app/services/luxian_0609/source_registry.py`
- Modify: `backend/app/services/luxian_0609/rule_contracts.py`
- Test: `backend/tests/unit/test_luxian_0609_native_course_quality_execution.py`
- Test: `backend/tests/contract/test_luxian_0609_acceptance_matrix.py`
- Verify: `backend/tests/integration/test_luxian_0609_delivery_envelope.py`

**Step 1: 锁定不可实施口径**

把“病情变化事件”和 017 正式相似度算法继续标为 pending；不得为了让结果通过而自行定义。

**Step 2: 写失败测试**

覆盖：无病危/病重医嘱时 007 适用；存在病重医嘱时 008 进入确定性日覆盖；存在病危医嘱时 009 进入已批准的每日覆盖；同一严重程度事实不得在三条规则中矛盾。

**Step 3: 运行失败测试**

Run: `python -m pytest backend/tests/unit/test_luxian_0609_native_course_quality_execution.py -q`

Expected: 新增的一致性或事实展示断言失败。

**Step 4: 最小实现**

只补严重程度时间轴、日覆盖事实和客户展示事实；不推断医嘱解除时间，不修改 016/017 医学阈值。

**Step 5: 验证真实病例**

使用 208790、359787 只读执行并核对：门控事实、每日覆盖日期、最终 Envelope 与 API 投影一致。需要保存新 Envelope 时先取得数据库写入授权。

**Step 6: 运行聚焦测试并提交**

Run: `python -m pytest backend/tests/unit/test_luxian_0609_native_course_quality_execution.py backend/tests/unit/test_luxian_0609_rule_contracts.py backend/tests/contract/test_luxian_0609_acceptance_matrix.py -q`

Commit: `修复：完成LX0609基础病程已定义口径收敛`

---

### Task 2：迁移 6F 扩展文书规则族

**范围：** 死亡、出院、术后病程、会诊时限、交接班、转科、诊断修正和有创操作等 050–075 中已进入正式/临时验收口径的规则。

**Files:**

- Modify: `backend/app/services/luxian_0609/native_extended_document_execution.py`
- Create: `backend/app/services/luxian_0609/extended_document_facts.py`
- Modify: `backend/app/services/luxian_0609/source_registry.py`
- Test: `backend/tests/unit/test_luxian_0609_native_extended_document_execution.py`
- Test: `backend/tests/contract/test_luxian_0609_acceptance_matrix.py`

**Step 1: 建立规则—触发事件—目标文书表**

明确死亡、出院、手术、转科、医生变更和有创操作的触发事实、权威时间、目标文书及不适用依据。

**Step 2: 写失败测试**

至少覆盖每条规则的：触发事件不存在、不适用；触发存在且文书存在，合规；触发存在且文书缺失，不合规；触发源缺失，数据不足。

**Step 3: 抽取最小 Fact**

`extended_document_facts.py` 只输出触发事件、时间、目标文书和来源引用，不输出最终状态。

**Step 4: 迁移确定性 Decision**

所有存在性和时限规则使用 Python；不得调用 LLM。诊断修正理由等语义规则仅在最小上下文中调用一次，并对输出做枚举校验。

**Step 5: 验收与提交**

Run: `python -m pytest backend/tests/unit/test_luxian_0609_native_extended_document_execution.py backend/tests/contract/test_luxian_0609_acceptance_matrix.py -q`

Commit: `重构：收敛LX0609扩展文书规则族`

---

### Task 3：迁移 6C 会诊规则族

**范围：** LX0609-020、021、022、023、069。

**Files:**

- Modify: `backend/app/services/luxian_0609/consultation_fact_contract.py`
- Modify: `backend/app/services/luxian_0609/consultation_020_relation_contract.py`
- Modify: `backend/app/services/luxian_0609/native_consultation_episode_execution.py`
- Modify: `backend/app/services/luxian_0609/native_consultation_execution.py`
- Test: `backend/tests/unit/test_luxian_0609_consultation_fact_contract.py`
- Test: `backend/tests/unit/test_luxian_0609_consultation_020_relation_contract.py`
- Test: `backend/tests/unit/test_luxian_0609_native_consultation_episode_execution.py`
- Test: `backend/tests/unit/test_luxian_0609_native_consultation_execution.py`

**Step 1: 固定 episode 主键优先级**

优先使用源业务键；没有业务键时使用患者、申请时间、申请科室、会诊科室组成的受控关联键；模糊匹配不得直接产生确定问题。

**Step 2: 写失败测试**

覆盖多次会诊不得串单、历史文本不得作为当前会诊、申请与意见关联失败返回具体缺口、执行记录只关联到同一 episode、069 使用申请发出时间作为起算点。

**Step 3: 收窄事实提取**

LLM 只允许识别文书角色、目的/意见是否明确和执行记录是否归纳总结；不得输出规则状态。

**Step 4: Python 严格关联和决策**

将 020/023 的关系判断和 069 的时间判断放回确定性代码；关联置信度不足时返回待确认或资料不足，不得猜测。

**Step 5: 验收与提交**

Run: `python -m pytest backend/tests/unit/test_luxian_0609_consultation_fact_contract.py backend/tests/unit/test_luxian_0609_consultation_020_relation_contract.py backend/tests/unit/test_luxian_0609_native_consultation_episode_execution.py backend/tests/unit/test_luxian_0609_native_consultation_execution.py -q`

Commit: `重构：收敛LX0609会诊episode关联链路`

---

### Task 4：迁移 6B 检查检验与病理规则族

**范围：** LX0609-010～015、019，以及危急值相关规则。

**Files:**

- Modify: `backend/app/services/luxian_0609/exam_lab_fact_extraction.py`
- Modify: `backend/app/services/luxian_0609/native_exam_lab_execution.py`
- Modify: `backend/app/services/luxian_0609/native_tumor_pathology_execution.py`
- Modify: `backend/app/services/luxian_0609/source_registry.py`
- Test: `backend/tests/unit/test_luxian_0609_native_exam_lab_execution.py`
- Test: `backend/tests/unit/test_luxian_0609_native_tumor_pathology_execution.py`
- Test: `backend/tests/unit/test_document_assembly_exam_lab_master.py`
- Test: `backend/tests/unit/test_document_assembly_pathology.py`

**Step 1: 固定报告聚合合同**

一张检验申请/报告为一个主事件，检验项目为子项；禁止每个项目形成一份独立文书。检查报告同样保留申请、执行、报告时间和报告身份。

**Step 2: 写关联失败测试**

覆盖多份同类 CT/MRI、报告晚于病程、病程仅提及检查名但未分析结果、病理源未接入不得判不适用、PL/PH 危急值起算时间为报告时间。

**Step 3: 抽取最小关联事实**

输出 `report_event`、`finding`、`reported_at`、`response_document`、`response_at` 和定位引用；阳性只按受控结构字段或报告明确“阳性”识别。

**Step 4: 决策与客户文案**

Python 计算 24 小时/6 小时窗口；语义模型只判断病程是否针对该报告进行了分析或处置。缺失时明确说明缺报告时间、结果、关联病程或定位证据中的哪一项。

**Step 5: 验收与提交**

Run: `python -m pytest backend/tests/unit/test_luxian_0609_native_exam_lab_execution.py backend/tests/unit/test_luxian_0609_native_tumor_pathology_execution.py backend/tests/unit/test_document_assembly_exam_lab_master.py backend/tests/unit/test_document_assembly_pathology.py -q`

Commit: `重构：收敛LX0609检查检验与病理关联链路`

---

### Task 5：迁移 6E 抗菌药与肿瘤规则族

**范围：** 预防抗菌药、重点/特殊级抗菌药、病原学检查、用药理由/效果评价，以及恶性肿瘤诊断、病理、化疗和出院计划。

**Files:**

- Modify: `backend/app/services/luxian_0609/native_tumor_pathology_execution.py`
- Modify: `backend/app/services/luxian_0609/rule_contracts.py`
- Create: `backend/app/services/luxian_0609/antimicrobial_facts.py`
- Create: `backend/app/services/luxian_0609/antimicrobial_catalog.py`
- Test: `backend/tests/unit/test_luxian_0609_native_tumor_pathology_execution.py`
- Create: `backend/tests/unit/test_luxian_0609_antimicrobial_facts.py`

**Step 1: 固定客户字典版本**

把 2025 年泸县人民医院抗菌药物分级目录作为带版本配置加载，统一通用名、商品名、复方名、剂型和分级；未命中字典不得擅自归类。

**Step 2: 写药品归一化和适用性失败测试**

覆盖同义名、复方药、特殊级药、预防/治疗意图不明、切口等级缺失、恶性肿瘤证据缺失和化疗事件关联失败。

**Step 3: 抽取用药 episode**

使用医嘱起止时间、药品身份、用法和用途建立最小 episode；模型只提取“理由、评价、无样可采原因”等受控语义事实。

**Step 4: 决策与验收**

Python 负责分级、时间窗、数量和病原学先后关系；缺少切口等级或用药意图时返回具体资料缺口。

Run: `python -m pytest backend/tests/unit/test_luxian_0609_antimicrobial_facts.py backend/tests/unit/test_luxian_0609_native_tumor_pathology_execution.py -q`

Commit: `重构：收敛LX0609抗菌药与肿瘤规则族`

---

### Task 6：迁移 6D 输血规则族

**范围：** LX0609-041～049 及输血前九项相关扩展规则。

**Files:**

- Modify: `backend/app/services/luxian_0609/native_transfusion_execution.py`
- Create: `backend/app/services/luxian_0609/transfusion_episode.py`
- Modify: `backend/app/services/luxian_0609/source_registry.py`
- Test: `backend/tests/unit/test_luxian_0609_native_transfusion_execution.py`
- Create: `backend/tests/unit/test_luxian_0609_transfusion_episode.py`

**Step 1: 写多源事件表和失败测试**

为一次输血列出医嘱、申请、输注、九项检查、知情同意、输血前评估、输血病程、术中记录、输血后评价和收费。覆盖多次输血不得串单、缺业务键、时间冲突和只有部分来源的情况。

**Step 2: 建立确定性关联优先级**

依次使用源业务键、申请/医嘱关联键、血液成分与时间窗；仅靠文本相似不得建立确定关联。

**Step 3: 固定输血前九项**

乙肝五项、HIV、HCV、梅毒和 ALT 使用客户确认口径；保存项目身份、结果时间、与输血时间的先后关系及缺项列表。

**Step 4: 一致性比较**

048 必须实际比较手术记录、麻醉记录和术后首次病程中的血液成分、数量与时间；不能因单份文书缺失直接声称三方不一致。

**Step 5: 费用关联与失败语义**

049 只有医嘱、实际输注和收费均可关联时才判一致/不一致；收费源缺失应明确返回“未同步输血收费明细”。

**Step 6: 验收与提交**

Run: `python -m pytest backend/tests/unit/test_luxian_0609_transfusion_episode.py backend/tests/unit/test_luxian_0609_native_transfusion_execution.py -q`

Commit: `重构：收敛LX0609输血事件关联链路`

---

### Task 7：删除失效兼容路径

**Files:**

- Modify: `backend/app/services/luxian_0609/execution.py`
- Modify: `backend/app/services/luxian_0609/executor_registry.py`
- Modify: `backend/app/services/luxian_0609/native_package.py`
- Modify: `backend/app/services/luxian_0609/rule_decision_settings.py`

**Step 1:** 使用 CodeGraph 为每个候选 legacy 符号列出生产、测试和脚本调用方。

**Step 2:** 只删除生产调用方为零且已有验收报告覆盖的分支、开关和适配器。

**Step 3:** 运行完整 LX0609 unit、contract、integration 测试，确认当前结果只有一条生产执行路径。

**Step 4:** 同步 CodeGraph，再次证明被删符号无生产调用方。

Commit: `清理：移除LX0609失效兼容执行路径`

---

### Task 8：性能与稳定性收口

**Files:**

- Modify: `backend/app/services/luxian_0609/engine.py`
- Modify: `backend/app/services/luxian_0609/execution.py`
- Test: LX0609 concurrency、repeatability、fault-injection tests

**Step 1:** 记录两份真实病例每族耗时、数据库读取数、LLM 调用数和 token 基线。

**Step 2:** 先消除重复读取和重复事实提取，再将无共享状态的确定性执行器并发设为 2。

**Step 3:** 同一病例连续执行 10 次，要求结果顺序、状态和 Envelope 哈希稳定。

**Step 4:** 注入单族超时，确认其他规则结果保留且错误归属到正确规则族。

Commit: `优化：收敛LX0609执行性能与故障隔离`

---

### Task 9：发布门禁与最终验收

**Files:**

- Modify: `scripts/qc/run_luxian_0609_mainline_synthetic_eval.py`
- Modify: release smoke scripts and LX0609 acceptance reports
- Test: complete LX0609 release suite

**Step 1:** 对唯一规则总表逐条核对正式 67 条和临时 8 条的执行覆盖、定义版本和预期状态。

**Step 2:** 使用合成验证集覆盖每条规则的合规、不合规、数据不足和不适用边界。

**Step 3:** 使用至少两份真实病例完成“执行 → 保存 Envelope → 单一 API 原样读取”的端到端核对。

**Step 4:** 验证技术异常为零、未执行占位为零、规则数与已执行数分别展示且一致。

**Step 5:** 运行编码、后端完整 LX0609 测试及发布烟测；不在本任务中打客户包。

Commit: `验证：建立LX0609质控引擎发布基线`

---

## 总体停止条件

- 客户尚未确认的定义需要被写成生产口径。
- 新抽象不能直接解决当前规则族的真实失败病例。
- 需要修改 Canonical Envelope 或单一结果 API 合同才能迁移单个规则。
- 通过增加第二套聚合器、状态解释器或通用图框架才能继续。
- 聚焦测试通过但真实病例事实、证据或耗时没有改善。

出现停止条件时，将对应规则标为 pending 并记录缺口，不扩大本批次范围。
