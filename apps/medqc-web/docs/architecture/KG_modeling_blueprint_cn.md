## MedQC 知识图谱建模蓝图与治理

本蓝图用于指导 MedQC 项目在 OpenSPG 上的知识建模、采集、校验与演进，作为“框架级”锚点。所有后续抽取、质控规则与前端集成均围绕本蓝图对齐落地。

### 1. 图空间与命名
- **图空间（space）**: `medqc`
- **命名约定**:
  - 类型名使用 PascalCase，例如 `Patient`、`Encounter`、`SeniorPhysicianRound`。
  - 属性名使用 lower_snake，如 `patient_id`、`occurrence_time`。
  - 关系名使用动词短语 lower_snake，如 `in_encounter`、`authored_by`、`mentions_finding`。
  - 代码/字典型字段采用标准编码体系（ICD-10、ICD-9/ICD-10-PCS、LOINC、ATC、SNOMED CT）并保留原始码与标准化码。

### 2. 核心类型（抽象）
- 实体（Entity）
  - `Patient` 患者
  - `Encounter` 就诊（住院/门诊，住院可用 admission_id 表示一次住院过程）
  - `Department` 科室
  - `Physician` 医师（含职称、角色）
  - `Document` 文档（病历记录，如入院记录、查房记录、进展病程等）
  - `Section` 文档段落（标题化片段，如“主任医师查房记录”）
  - `Finding` 临床所见（体征/症状/异常）
  - `Diagnosis` 诊断（含层级/标准码/疑似程度）
  - `MedicationOrder` 药嘱（医嘱意图）
  - `Procedure` 手术/处置
  - `LabResult` 检验结果
  - `VitalSignMeasurement` 生命体征测量
  - `QCDefect` 质控缺陷（用于承载规则判定输出）

- 事件（Event）
  - `Admission` 入院事件
  - `Discharge` 出院事件
  - `SeniorPhysicianRound` 主任/上级医师查房事件（4.13.2 对应的结构化承载体）
  - `ProgressNoteEvent` 病程记录事件
  - `MedicationAdministration` 给药事件
  - `ProcedurePerformed` 手术/处置执行事件
  - `LabTestPerformed` 检验执行事件

- 关系（Relation）
  - `belongs_to` (Physician -> Department)
  - `in_encounter` (Document/Event -> Encounter)
  - `about_patient` (Encounter/Document/Event -> Patient)
  - `authored_by` (Document/Section/Event -> Physician)
  - `has_section` (Document -> Section)
  - `mentions_finding` (Section/Document -> Finding)
  - `supports_diagnosis` (Finding/LabResult -> Diagnosis)
  - `contradicts_diagnosis` (Finding/LabResult -> Diagnosis)
  - `derived_from` (NodeA -> NodeB，用于谱系/来源追溯，如 Section 派生自 Document)
  - `precedes` (EventA -> EventB 时间先后)
  - `duplicates` (NodeA -> NodeB 内容相似/重复)
  - `same_as` (同一实体不同源头的对齐)

### 3. 标识与主键策略
- 全局外部标识：保留 `source_system` 与 `source_id`（例如 HIS/EMR 原始主键）。
- 业务主键：
  - `Patient`: `patient_id`（院内患者唯一号）
  - `Encounter`: `encounter_id`（就诊/住院号）；与 `patient_id` 组合保障唯一
  - `Document`: `document_id`（文档唯一）；与 `encounter_id` 组合保障唯一
  - `Event`: `event_id`（事件唯一，若无则用稳定哈希 `encounter_id + occurrence_time + event_type + author_id`）
- 版本与更正：
  - `version`（整型自增）；`is_current`（布尔）；`supersedes`（指向被替代版本）
  - 事件类节点采用“写一次”策略，修订通过新版本事件+关系表达

### 4. 时间模型
- `occurrence_time`: 事件/记录发生时间（UTC 标准存储，保留 `timezone`）
- `valid_time_start`, `valid_time_end`: 陈述有效期间（用于诊断有效性或医嘱生效期）
- 粒度：时间最小粒度分钟，若无则以日期+文档顺序近似
- 顺序关系：同一 `encounter` 内事件按 `occurrence_time` 与文档顺序建立 `precedes`

### 5. 文档与分段建模
- `Document` 承载原始文本、元数据（标题、类型、作者、创建/签署时间）
- `Section` 为结构化段（如“主任医师查房记录”），保留 `title`、`text_span`（起止行/字符）、`summary`
- 溯源：所有抽取出的 `Finding/Diagnosis/Event` 必须通过 `derived_from` 连接到具体 `Section`，并包含 `provenance` 元数据：
  - `source_doc_path`, `line_span`, `extractor_name`, `extractor_version`, `llm_model`, `confidence`

### 6. 4.13.2 上级医师查房事件结构
- 事件：`SeniorPhysicianRound`
  - 属性：`occurrence_time`, `round_level`（主任/副主任/主治等），`participants`（可拆关系），`content_hash`
  - 关系：
    - `in_encounter` -> `Encounter`
    - `about_patient` -> `Patient`
    - `authored_by` -> `Physician`（上级医师）
    - `derived_from` -> `Section`（标题含“主任/上级医师查房记录”）
    - `mentions_finding` -> `Finding`（体征/症状/异常）
    - `supports_diagnosis`/`contradicts_diagnosis` -> `Diagnosis`

### 7. 质控缺陷建模（图轨输出）
- `QCDefect`
  - 属性：`rule_id`, `defect_level`（A/B/C）, `explanation`, `created_at`, `missing_items`（JSON 列表）, `context_source`（graph/llm/graph+llm）
  - 关系：
    - `about_patient` -> `Patient`
    - `in_encounter` -> `Encounter`
    - `derived_from` -> `Document/Section/Event`（证据）

### 8. 索引与性能基线
- 单值索引：`Patient.patient_id`, `Encounter.encounter_id`, `Document.document_id`, `Event.event_id`
- 组合索引：`(encounter_id, occurrence_time)`, `(patient_id, encounter_id)`
- 前缀过滤：按 `encounter_id` 分片，支撑单病例全景查询

### 9. 质量与约束
- 唯一性：上述主键字段唯一
- 必填：事件类必须具备 `occurrence_time`；文档必须具备 `author_id` 或签名者
- 参考完整性：`in_encounter/about_patient/authored_by` 关系指向存在节点
- 代码有效性：标准码字段通过字典校验（可在入库前/后置校验）

### 10. 原始数据到子图（Raw→SubGraph）最小契约
- 输入：一份文档文本 + 元数据（患者、就诊、作者、时间）
- 输出：子图最小单元包含：
  - 1 个 `Document`，若包含目标段则建 1..n 个 `Section`
  - 0..n 个 `Event`（如 `SeniorPhysicianRound`）
  - 0..n 个 `Finding/Diagnosis/...`，并通过 `derived_from` 指回 `Section`
  - 必含 `provenance` 元数据与 `confidence`

### 11. 校验与 Cypher 校对集（样例）
```cypher
// 病例应至少存在一个 Encounter 与一个 Patient
MATCH (e:Encounter)-[:about_patient]->(p:Patient)
RETURN count(e) AS encounters, count(p) AS patients;

// 4.13.2：一个住院 Encounter 内，是否存在上级医师查房事件
MATCH (e:Encounter {encounter_id: $encounter_id})
OPTIONAL MATCH (r:SeniorPhysicianRound)-[:in_encounter]->(e)
RETURN e.encounter_id AS eid, count(r) AS round_events;

// 溯源：查房事件是否指回具体 Section
MATCH (r:SeniorPhysicianRound)-[:derived_from]->(s:Section)
WHERE s.title CONTAINS "查房"
RETURN r.event_id, s.title, s.text_span
LIMIT 20;
```

### 12. 治理流程（Schema 演进）
- 变更类别：新增类型/属性、属性重命名、关系语义变更、字段类型/约束调整、弃用
- 变更流程：提 PR → 蓝图评审 → 测试环境迁移与数据回放 → 评测通过 → 生产迁移
- 兼容策略：
  - 新增优先（向后兼容）
  - 重命名通过双写阶段+迁移脚本（保留 `supersedes`）
  - 破坏性调整需提供数据迁移/回滚方案

### 13. 隐私与合规
- PII 字段（姓名、手机号、地址等）以脱敏或哈希形式入库，保留可审计映射在合规域
- 日志中禁止输出原文敏感信息；模型训练数据需脱敏
- 保留访问审计与变更审计

### 14. 与质控双轨的衔接
- 图轨：以 `SeniorPhysicianRound`、`Finding/Diagnosis` 等结构化节点与关系提供可判定的确定性规则（如时效、频次、来源）
- LLM 轨：以图轨检索到的 `Document/Section` 为最小上下文入口，结合 Top-K 证据句与摘要执行语义判定
- 输出合并：`QCDefect` 统一承载，`context_source` 标注来源；缺失项通过 `missing_items` 列表化

### 15. 立即落地事项（与代码对齐）
- 在现有 `Medqc.schema` 中核对并补充：`SeniorPhysicianRound`、`Section`、`QCDefect`、核心关系（`in_encounter/about_patient/authored_by/derived_from/mentions_finding`）
- 为 Indexer 明确 Raw→SubGraph 最小契约（见第 10 节），保证抽取产物都可溯源
- 初始化校验脚本集（第 11 节样例）并纳入 CI 作为数据验收关卡

以上为稳定锚点；如需扩展，请遵循第 12 节治理流程提交变更。


