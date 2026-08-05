# LX0609 多台手术事件关联与文书字段映射修复 Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**目标：** 仅修复两类已在真实病例 `208790 / 2496813` 证明存在的资料链缺口：多台手术时无法把目标文书归属到具体手术事件，以及文书已进入 MaterialStore 但规则需要的字段没有被读取或受控提取。资料确实为空、字段在源库不存在、或关系无法唯一确认时，继续返回可解释的 `data_gap`，绝不为了减少数量制造结论。

**架构：** 保持 `EvidenceSnapshot / MaterialStore` 为唯一资料链。使用一个仅在本次规则执行内工作的确定性“手术事件关联纯函数”，输入已经读取的 `surgery_record`、`mr_surgery`、术前小结、核查表和术后文书行，输出可审计的关联结果；不持久化事件、不读取数据库、不读 Bundle、不调用 LLM。字段映射先做源表能力审计，再按单个规则最小接入已有字段或正文；不得预设源库一定有字段。

**技术栈：** Python、现有 Luxian0609 EvidenceSnapshot/MaterialStore、pytest、PostgreSQL（只读核验）。

---

## 0. 已冻结的问题证据与范围

### 0.1 真实复现病例

- 病历号：`208790`；三坐标：`泸县人民医院 / 0000225510 / 2496813`。
- 当前 75 条规则任务：`4117b5fa-1820-46d7-890c-804060799827`。
- 当前 `data_gap` 共 28 条；本计划只处理其中有明确资料链证据的两类，不能把其它 16 条来源空或来源未接入的问题混进来。

该病例存在两台真实手术记录：

| 手术事件 | 手术记录开始时间 | 手术记录                           | 已有可关联文书                                   |
| -------- | ---------------- | ---------------------------------- | ------------------------------------------------ |
| A        | 2026-07-07 16:30 | 血肿清除、硬脑膜修补、去骨瓣减压等 | 手术安全核查表、术前小结、术后首次病程、麻醉记录 |
| B        | 2026-07-08 15:55 | 眼球破裂修补术                     | 手术安全核查表、术后首次病程、麻醉记录           |

`mr_surgery` 有 8 行，是操作/明细行，不能被当作 8 台独立手术。当前规则把“当前住院有多台手术”直接降级为 `association_failed`，而没有先利用已存在的时间、文书标题及术式文字建立受控的逐台关系。

### 0.2 两个问题域的精确规则范围

| 问题域               | 本轮主规则                               | 仅回归、不改口径的相邻规则        |
| -------------------- | ---------------------------------------- | --------------------------------- |
| 多台手术事件关联     | `029`、`032`、`064`、`065`、`066`        | `030`、`003`、`031`、`033`、`048` |
| 文书已读但字段未映射 | 先审计 `025`、`028`、`031`、`038`、`048` | `062`、`063` 明确不在本轮         |

规则门控不能合并为一个“已实施手术”布尔值：

- `029`：当前住院是否有手术医嘱/申请所要求的术前小结；
- `030`：当前住院是否有正式手术记录；
- `032`：当前住院已实施手术是否有手术安全核查表；
- `064`、`065`、`066`：每一台实际手术后的连续病程、上级医师查房和术后首次病程。

### 0.3 明确不做

- 不新增 Bundle、Snapshot、持久化事件表、通用事件平台、配置开关、LLM 调用或 Prompt。
- 不修改 `execution.py`、Canonical Finalizer、Aggregator、Envelope、API、前端和数据库 schema。
- 不修改客户质控口径；源资料、时间精度或关系不足时保持保守结论。
- 不借机修复 `034–037`、`039`、`049`、`062`、`063` 等其它资料缺口。
- 每个实现子任务最多改一个低耦合规则族；完成、验证、独立提交并审核后暂停。

## 1. 目标合同

### 1.1 手术事件关联合同

事件关联器只消费调用方从 `MaterialStore` 已取得的行，且每个输出必须带来源文书引用。它不拥有住院状态、评价终点、资料完整性或业务状态的解释权。

关联优先级：

1. `surgery_record` 的结构化手术开始时间和手术名称建立本次住院的基准手术事件；
2. 目标文书有完整日期时间时，按同一事件日期 + 规范化术式文字一对一匹配；
3. 目标文书没有可用时间但术式文字能唯一对应一个基准事件时，可建立文字唯一匹配；
4. 同日有多台、术式文字同时命中多台、只有“今日急诊”等相对时间、或来源缺字段时，输出未关联原因，绝不猜测。

`mr_surgery` 仅作为对手术记录的补充明细，必须先归入一个已有基准手术事件，不能按行数生成事件数量。匹配结果只在当前调用内存在，使用可复现的来源引用组合，不新增跨任务 `event_id`。

每条规则按自己的门控选择关联结果；不得让 `029/030/032` 因共享“已实施手术”布尔值而改变正式口径。

### 1.2 字段映射合同

字段映射的首要原则是区分三种事实：

| 情形                                               | 正确结果                                                                   |
| -------------------------------------------------- | -------------------------------------------------------------------------- |
| 目标文书和需要字段在源表中存在，但 Reader/投影遗漏 | 修正该 source key 的受控字段映射或该规则的确定性提取；可形成原本应有的判定 |
| 文书存在、字段本身为空或正文无可验证字段           | 保留 `data_gap` 或规则既有保守状态，并明确缺少的具体字段                   |
| 原始表根本没有该文书/字段                          | 不写假 Reader，不推断值；记录为本地同步/源数据能力待核验                   |

正文提取只允许使用规则已需要的受控字段（如 `surgery_process`、`record_content`、`anesthesia_process`）；不把整段正文交给新 LLM，也不把不完整文字当结构化字段。

## 2. Task 0：冻结输入并完成字段能力只读审计

**目的：** 先证明字段第一次丢失位置，避免把“字段在源表不存在”误改成 Reader 缺陷。

**只读文件与来源：**

- `backend/app/services/luxian_0609/source_evidence_reader.py`
- `backend/app/services/luxian_0609/source_registry.py`
- `backend/app/services/luxian_0609/native_surgery_gate_execution.py`
- `backend/app/services/luxian_0609/native_surgery_document_execution.py`
- `backend/app/services/luxian_0609/native_transfusion_execution.py`
- `backend/app/services/luxian_0609/native_extended_document_execution.py`
- 当前 PG 的 `cdm` 源表（只读）。

**步骤：**

1. 固定 commit、三坐标、任务 ID 和当前 SourceObservation；导出五个字段规则的 MaterialStore 行数、已投影字段、文书引用和当前 Native/Canonical reason。
2. 以完整三坐标查询物理表的列清单与该病例原始行，禁止只按 `visit_id` 取第一行。
3. 对 `029/032/064/065/066` 记录当前公开执行器、触发门控、目标文书和“多台即关联失败”的实际代码位置；尤其确认 `029` 的手术医嘱/申请事实不能被手术记录替代。
4. 形成 `docs/audits/2026-08-05-lx0609-208790-surgery-field-capability.md`，每个规则一行：

   | 规则 | 必需字段                           | 原始表/列                       | Reader当前投影       | 首次丢失层 | 最小动作                   |
   | ---- | ---------------------------------- | ------------------------------- | -------------------- | ---------- | -------------------------- |
   | 025  | 植入物名称、种类、规格、材质、数量 | `surgery_record` 正文及结构化列 | `surgery_process` 等 | 待审计     | 映射 / 正文提取 / 保持缺口 |
   | 028  | 切口级别、预防属性、实际用药起止   | 手术与医嘱                      | 待审计               | 待审计     | 仅真实字段接入             |
   | 031  | 术者、签名医师及可比身份           | 手术记录、术前资料              | 待审计               | 待审计     | 仅真实字段接入             |
   | 038  | 麻醉记录正文、麻醉方式、记录时间   | 麻醉记录                        | 待审计               | 待审计     | 仅真实字段接入             |
   | 048  | 手术/麻醉/术后首次病程的成分、剂量 | 三类文书                        | 待审计               | 待审计     | 仅真实字段接入             |

5. 每项标记为 `mapping_defect_confirmed`、`source_field_empty`、`source_capability_absent` 或 `association_required`；没有证据不得进入代码任务。

**验收：** 审计能回答“字段在何处第一次丢失”，并且不修改代码、不触发 LLM、不重跑全量任务。

## 3. Task 1：以 TDD 锁定多台手术与核查表的关联（仅 LX0609-032）

**目标：** 先只修 `032`：多台手术时逐台核对手术安全核查表，而不是仅因手术记录计数大于 1 返回 `association_failed`。这一步建立可复用的纯关联事实，但不同时修改术前或术后规则。

**允许改动文件：**

- `backend/app/services/luxian_0609/surgery_event_linkage.py`（新建、纯函数，最多包含事件投影、关联函数及受控失败原因）
- `backend/app/services/luxian_0609/native_execution.py`
- `backend/tests/unit/test_luxian_0609_surgery_event_linkage.py`（新建）
- `backend/tests/unit/test_luxian_0609_native_execution.py`（若现有该文件名不同，先定位现有 030/032 公共入口测试文件，不能新建镜像测试）

`surgery_event_linkage.py` 不是通用平台：禁止导入 MaterialStore、Snapshot、数据库、LLM、Bundle 或执行器；只接收行和已存在的 source reference，并由调用者提供。

### 3.1 先写失败测试

建立一个双手术 fixture：两条正式手术记录在不同日期、两条安全核查表分别含相应时间/术式。测试必须经现有公开 Native 入口，而非只测新 helper。

覆盖以下 8–12 个高价值场景：

1. 两台不同日期的手术，各自安全核查表可唯一配对，`032` 不再因“总数>1”返回 `association_failed`；
2. 同日两台手术、目标文书只有含糊相对时间时，保留 `data_gap/association_failed`；
3. `mr_surgery` 多行归入同一正式手术记录，不能被当作多台手术；
4. `030` 的“正式手术记录存在”门控行为不变；
5. 所有上述场景 LLM 调用数与 Token 均为 0。

为每个确定结论锁定 `final_state`、`reason_code`、`customer_display_facts` 和定位证据；对不确定场景只断言保守失败与其具体关联原因。

### 3.2 最小实现

1. 用一组基准 `surgery_record` 行生成当前住院的 `LinkedSurgeryEvent`；需要结构化开始时间、规范化术式文字和 source reference。
2. 在纯函数内把 `mr_surgery` 明细归入唯一基准事件；不能归入时只保留为未关联明细，不增加事件数。
3. 仅为 `surgery_safecheck_record` 生成“唯一关联 / 无法关联”的局部结果。无精确时间时只有术式文字唯一命中才可配对；多候选时失败关闭。
4. 仅将 `032` 改为消费该局部结果，并为 `association_failed` 返回可读的关联缺口事实；不修改 `030` 的当前所有者或状态映射。
5. 不改变 `SurgeryEventFact`（其为 024/025/028/033 的文本事实/LLM 合同），避免把两套不同职责合并为一个大模型。

**聚焦命令：**

```powershell
python -m pytest backend/tests/unit/test_luxian_0609_surgery_event_linkage.py backend/tests/unit/test_luxian_0609_native_execution.py -q
```

**提交：**

```text
fix: 支持LX0609多台手术核查表逐事件关联
```

**暂停/拒绝条件：** 如需要以模糊自然语言猜测文书归属，立即停止并把反例记录进审计，不扩展算法。

## 4. Task 2：术后规则逐事件关联（仅 LX0609-064/065/066）

**前置条件：** Task 1 已独立审核通过；Task 0 证明三条规则的手术触发和时间来源完整。

**目标：** 复用 Task 1 的纯关联结果，使 064、065、066 按每台实际手术分别计算术后三天、上级医师查房和术后首次病程；不得再以“多台手术”作为整体阻断。

**允许改动文件：**

- `backend/app/services/luxian_0609/surgery_event_linkage.py`
- `backend/app/services/luxian_0609/native_extended_document_execution.py`
- `backend/tests/unit/test_luxian_0609_surgery_event_linkage.py`
- `backend/tests/unit/test_luxian_0609_native_extended_document_execution.py`

**先写失败测试：**

1. 两台手术各自有术后首次病程时，066 逐台通过；任一台缺失时，结果只以缺失的那台手术为证据；
2. 064/065 的 72 小时/三天覆盖从各自手术时间计算，不只使用最后一台的时间；
3. 同日多台、术后病程无法唯一归属时保留 `data_gap/association_failed`，不能把任一病程借给另一台；
4. 其它扩展文书规则状态与 Token 均不变。

**最小实现：** 每个基础手术事件只接收其关联的术后、日常和上级病程行；在现有 064/065/066 逻辑内逐事件汇总。任何一个需要的事件未关联时，输出关联缺口的客户事实；不改变手术适用性、评价时间或其它规则。

**聚焦命令：**

```powershell
python -m pytest backend/tests/unit/test_luxian_0609_surgery_event_linkage.py backend/tests/unit/test_luxian_0609_native_extended_document_execution.py -q
```

**提交：**

```text
fix: 按单台手术核对术后病程规则
```

**停止条件：** 如发现 064/065/066 需要客户重新定义“多台手术合并计算还是逐台计算”，立即停止，记录真值表，不自行选择口径。

## 5. Task 3：术前小结的关联可行性判定（仅 LX0609-029）

**前置条件：** Task 1–2 审核通过，且 Task 0 已确认 029 当前住院手术医嘱/申请事实的真实来源与精度。

**目标：** 仅在手术医嘱/申请门控已被证实时，使用既有事件关联事实检查术前小结归属。不能用正式手术记录替代手术医嘱，也不能因术前小结只有“今日急诊”等弱信息建立关联。

**允许改动文件：**

- `backend/app/services/luxian_0609/surgery_event_linkage.py`
- `backend/app/services/luxian_0609/native_surgery_document_execution.py`
- `backend/tests/unit/test_luxian_0609_surgery_event_linkage.py`
- `backend/tests/unit/test_luxian_0609_native_surgery_document_execution.py`

**TDD验收：** 两台手术中一台有已验证的术前门控且有唯一术前小结、另一台无文书时，不能借用同一小结；门控来源缺失时继续 `data_gap` 并说明缺少手术医嘱/申请关联，不改成不合规。

**提交：**

```text
fix: 按手术门控关联LX0609术前小结
```

## 6. Task 4：按审计结果处理一个已证实的字段映射缺口

**目标：** 从 Task 0 中选择一个且仅一个 `mapping_defect_confirmed` 规则闭环。当前最可能优先项是 `025`：该病例手术正文已出现“人工硬脑膜一张”，但当前 025 的受控规则仅接受明确的“植入物名称：…”字段；是否应从现有正文得到“实际植入”仍需按 Task 0 的来源与口径证据决定。

**文件白名单（按被选规则二选一/三选一；不得全部同时改）：**

| 被证实的缺口     | 允许生产文件                                                               | 对应测试                                                                                              |
| ---------------- | -------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------- |
| 025 植入物       | `source_evidence_reader.py` 或 `native_surgery_gate_execution.py` 之一     | `test_luxian_0609_source_evidence_reader.py`、`test_luxian_0609_native_surgery_gate_execution.py`     |
| 031 签名字段     | `source_evidence_reader.py` 或 `native_surgery_gate_execution.py` 之一     | 上述对应测试                                                                                          |
| 038 麻醉记录字段 | `source_evidence_reader.py` 或 `native_surgery_document_execution.py` 之一 | `test_luxian_0609_source_evidence_reader.py`、`test_luxian_0609_native_surgery_document_execution.py` |
| 048 输血比对字段 | `source_evidence_reader.py` 或 `native_transfusion_execution.py` 之一      | `test_luxian_0609_source_evidence_reader.py`、`test_luxian_0609_native_transfusion_execution.py`      |

`028` 只有同时查到切口级别、预防性用途和实际用药时间均存在而 Reader 漏映射时才可进入本任务；否则记为资料/口径缺口，不修改代码。

### 4.1 TDD合同

对选中的规则，先增加一个公开入口失败用例，至少锁定：

1. 原始资料具有字段时，SourceObservation 不得标为 reader 未注册或未证明，MaterialStore 行保留原字段，Native 形成对应事实；
2. 文书存在但该字段为空时，保留 `data_gap`，以客户可读字段名说明缺口；
3. 字段来自错误文书、错误手术事件或只有计划性描述时，不能借用成当前实际事实；
4. LLM 调用次数、Token 不增加。

只允许把 raw field 投影到既有 source key，或把已投影的明确标注字段交给本规则的确定性提取函数。禁止新增“全文字段”、模糊关键词放宽、来源补造或通用 Reader 框架。

### 4.2 真实病例验收

仅重跑 `208790 / 2496813` 的选中规则和受影响相邻规则。逐项对比修复前后：

```text
SourceObservation → MaterialStore 行/字段 → Native reason → RuleDecision
→ Canonical item → Envelope
```

核对 `status`、`reason_code`、关键事实、客户解释、定位证据、LLM 调用和 Token。只有源字段已存在且被正确读取时才允许状态发生变化；真实字段空缺必须仍为数据不足。

**提交：**

```text
fix: 补齐LX0609-<规则号>文书字段映射
```

## 7. Task 5：组合回归、独立审核与停止

仅当 Task 1–4 均已独立提交且聚焦测试通过时执行。

1. 运行两组聚焦测试及现有手术/输血相关回归，不在每个小补丁后运行完整全仓测试：

```powershell
python -m pytest backend/tests/unit/test_luxian_0609_surgery_event_linkage.py backend/tests/unit/test_luxian_0609_native_surgery_document_execution.py backend/tests/unit/test_luxian_0609_native_extended_document_execution.py backend/tests/unit/test_luxian_0609_native_surgery_gate_execution.py backend/tests/unit/test_luxian_0609_native_transfusion_execution.py -q
```

2. 对真实病例复核本计划涉及的 11 个规则（`025/028/029/030/031/032/038/048/064/065/066` 中实际执行的规则），出具前后对照：
   - 关联成功必须有两端 source ref；
   - 资料不足必须有具体缺口；
   - 没有新增技术异常；
   - 没有新增 LLM/Token；
   - 不因多台手术把一台的文书借给另一台。
3. 提交给独立审核 Agent，审核重点是：首次丢失层是否确实修复、没有把真实缺失强行转为确定状态、没有引入第二资料链或扩大至其它规则族。
4. 审核通过后暂停。后续是否处理 `028/031/038/048` 的其他项目，需要新的只读证据和用户授权。

## 8. 验收表

| 验收项   | 通过条件                                                                                   |
| -------- | ------------------------------------------------------------------------------------------ |
| 多台手术 | 多事件时不再以简单计数直接阻断；可唯一匹配才逐台判定，不能匹配时保守且说明原因             |
| 规则门控 | 029、030、032、064、065、066 不共用错误的单一“已实施手术”结论                              |
| 字段映射 | 每一处新字段均能追溯到真实源表列/正文；无字段时不伪造                                      |
| 主链     | Source Registry/Reader → Snapshot → MaterialStore → Native → Decision → Canonical 全程唯一 |
| 结果行为 | 同一冻结输入下，未涉及规则的状态、原因码、证据、LLM/Token 不变                             |
| 客户解释 | 保留数据不足时能说明“缺哪类资料/字段/关联”，不展示内部字段名或代码                         |
| 范围     | 无 API、前端、Envelope、Finalizer、LLM、数据库迁移和通用平台改动                           |
