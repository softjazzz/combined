# LX0609-032 多台手术与安全核查表关联修复计划

**目标：** 只解决规则 `LX0609-032` 在同次住院有多台手术时，因正式手术记录数量大于 1 而直接返回 `data_gap / association_failed` 的问题。让每台可确定的正式手术与一份手术安全核查表一对一核对；资料或关联不足时继续保守返回数据不足。

**边界：** 资料仍只能来自既有 `EvidenceSnapshot / MaterialStore`。不新增 Bundle、Snapshot、持久化事件表、LLM、Prompt、配置开关或通用事件平台；不修改 `029`、`030`、`064–066`、字段映射、Canonical、Envelope、API、前端或数据库 schema。

## 1. 已证明的复现与业务合同

### 1.1 冻结复现

- 病历号：`208790`；三坐标：`泸县人民医院 / 0000225510 / 2496813`。
- 现有 75 规则任务：`4117b5fa-1820-46d7-890c-804060799827`。
- 当前病历有两份正式 `surgery_record`，开始时间分别为 `2026-07-07 16:30` 和 `2026-07-08 15:55`；有两份 `surgery_safecheck_record`。
- `mr_surgery` 有 8 行操作明细，不能当作 8 台独立手术。
- 当前 `native_execution.py` 对 `LX0609-032` 将“正式手术记录数量大于 1”直接改为 `data_gap / association_failed`，没有尝试利用当前资料中的业务关联键。

### 1.2 唯一允许的关联合同

1. 基准手术事件只来自本次住院的正式 `surgery_record`。
2. 同一 `surgery_record.document_id` 的重复行只能形成一台基准手术。
3. `mr_surgery` 只能作为补充明细，永远不能单独增加基准手术数量。
4. 每份安全核查表至多关联一台基准手术；每台基准手术至多关联一份安全核查表。
5. 任一台可确定的正式手术没有关联核查表，才形成该台对应的文书缺失结论；不能以另一台的核查表补足。
6. 全部基准手术均唯一关联时，才允许合规。
7. 关联不足、多个候选或来源不完整时，保持 `data_gap / association_failed`，并保存手术记录与核查表两端 source ref。

原始审计未发现结构化业务关联键，因此此前停止 Task 1。现客户已书面确认：核查表正文的受控字段 `手术时间：YYYY-MM-DD HH:MM:SS` 表示其所对应手术的开始时间。仅对 `LX0609-032`，该字段成为本次住院内的唯一关联键，替代下列原先无法满足的优先级。

受控关联必须同时满足：

1. 只解析核查表正文中精确字段名 `手术时间` 后的完整日期时间；不得把任意日期、记录时间或术式文本当作手术时间；
2. 与正式 `surgery_record.surgery_begin_time` 精确到分钟完全相等；
3. 两端均唯一，一份核查表和一份正式手术记录只能互相配对一次；
4. 两端时间缺失、格式不合法、重复或存在额外候选时，一律 `data_gap / association_failed`；
5. 两来源均完整、所有有效核查表均可解释但仍有正式手术没有匹配时，才 `non_compliant / required_document_missing`；
6. 不使用同日匹配、数量配对、模糊术式、文本相似度、关键词推断或 LLM。

原始关联优先级（仅保留为后续资料接口升级的参考，不在本 Task 实现）是：

1. 同一业务手术 ID、申请 ID、父子文书 ID 或其他明确结构化关联键；
2. 完整手术时间与结构化术式代码/名称同时一致；
3. 严格规范化后的术式名称仅命中一个基准手术；
4. 其余情况失败关闭。

禁止使用相似度、模糊包含、关键词猜测、“同日即同台”或“今日急诊”等相对时间推断关联。

## 2. Task 0A：只读核对 032 两类文书的可用关联键

**目的：** 先确认现有 Source Reader 是否已经把可用结构化键放入 MaterialStore。只有没有业务键而名称能严格唯一匹配时，才允许使用第三优先级；不先写关联算法。

**只读范围：**

- `backend/app/services/luxian_0609/source_evidence_reader.py`
- `backend/app/services/luxian_0609/source_registry.py`
- `backend/app/services/luxian_0609/native_execution.py`
- `backend/tests/unit/test_luxian_0609_native_execution.py`
- `cdm` 内 `surgery_record` 与 `surgery_safecheck_record` 的原始列和该病例行（完整三坐标、只读事务）。

**步骤：**

1. 固定当前 commit、三坐标、任务 ID 和两来源的 SourceObservation、MaterialStore 行、document ref。
2. 分别列出两张原始表和 Reader 投影中的：业务手术 ID、申请 ID、记录 ID、父子/关联 ID、文书 ID、手术开始时间、手术结束时间、结构化术式代码/名称、核查时间和标题字段。
3. 按一对一候选关系输出 `docs/audits/2026-08-05-lx0609-208790-safecheck-linkage.md`：

   | 基准手术记录 ref | 候选核查表 ref | 可用关联键 | 匹配等级 | 是否唯一 | 结论 |
   | ---------------- | -------------- | ---------- | -------- | -------- | ---- |

4. 明确首次丢失层：
   - `reader_mapping_missing`：原始表有业务键但 MaterialStore 没投影；
   - `linkage_logic_missing`：MaterialStore 已有足够键，当前执行器未关联；
   - `source_key_absent_or_ambiguous`：原始表不具备安全一对一关联键。

**停止条件：**

- 若原始表存在关联键但 Reader 未投影，本计划不顺手改 Reader；记录证据并等待单独授权。
- 若两个来源没有能满足上述三级合同的唯一关联，记录为真实关联不足，不进入 Task 1。
- 不读取或修改其它规则、其它文书、字段映射或合成数据。

**验收：** 审计报告能够说明本病例每份核查表为什么能或不能关联到一台正式手术；过程不写库、不调用 LLM、不触发质控任务。

## 3. Task 1：TDD 最小修复 032 的一对一关联

**前置条件：** Task 0A 判定为 `source_key_absent_or_ambiguous`；但客户已确认当前 MaterialStore 中核查表的受控正文时间字段可以作为单病例、精确到分钟的关联键。

**允许改动文件：**

- `backend/app/services/luxian_0609/native_execution.py`
- `backend/tests/unit/test_luxian_0609_native_execution.py`

关联辅助函数保留在 `native_execution.py` 内，只接收该执行器已从 MaterialStore 读取的行；不得导入数据库、Bundle、LLM 或新增通用事件平台。

### 3.1 先写公开入口失败测试

以两台手术/两份核查表的 fixture 锁定以下合同：

1. 两台手术分别唯一关联核查表时，032 不再因为记录总数大于 1 返回 `association_failed`；
2. 两台手术中任一台缺少可确定的核查表时，不能用另一台核查表复用补足；
3. 同一核查表候选两个手术，或同一手术候选多个核查表时，保持 `data_gap / association_failed`；
4. 同一 `document_id` 的重复手术行只算一台；额外 8 行 `mr_surgery` 不增加手术数；
5. `030` 与 `033` 对同一冻结输入的状态、reason code、证据、LLM 调用和 Token 均不变；
6. 032 的关联成功和关联失败均保留两端 source ref；全程 LLM/Token 为 0。

测试必须穿过现有 `execute_luxian_0609_native_rules` 公开入口和现有 Reducer/生产 Aggregator 核心，而不是仅断言新函数返回值。

### 3.2 最小实现

1. 在 `native_execution.py` 内固定实现：基准手术去重、客户确认的精确分钟关联、双向一对一占用检查和受控 `association_failed` 结果。
2. 仅替换 `native_execution.py` 中 032 的“手术记录数量大于 1即失败”分支；030 的正式手术记录存在性规则保持原路径。
3. 032 只根据关联输出决定：
   - 所有基准手术都有唯一核查表 → 沿用既有合规逻辑；
   - 已知一台缺表且资料完整 → 沿用既有缺文书逻辑；
   - 关系不唯一或来源不足 → `data_gap / association_failed`，附具体关联缺口事实。
4. 不修改 029、064–066 或任意字段映射逻辑。

**聚焦验证：**

```powershell
python -m pytest backend/tests/unit/test_luxian_0609_native_execution.py -q
```

**提交：**

```text
fix: 支持LX0609多台手术安全核查表关联
```

## 4. Task 2：真实病例交付核对、独立审核与暂停

1. 后端加载新代码后，使用新任务只重跑 `208790 / 2496813` 的 `LX0609-032`；不复用旧任务。
2. 对比修复前后：

```text
SourceObservation → MaterialStore → Native → RuleDecision
→ Canonical Envelope → 单一结果 API
```

核对 status、reason code、手术记录与核查表的 source ref、客户解释、LLM 调用和 Token。

3. 复跑 `030`、`033`，确认其结果没有改变。
4. 发起独立审核，审核重点：
   - 是否优先使用真实结构化关联键；
   - 是否发生文书跨手术复用；
   - 不明确关系是否仍保守；
   - 是否扩大至其它规则、字段映射或第二资料链。
5. 审核通过后立即暂停。`064–066`、029 和“已有文书但字段未映射”必须另立任务、重新审计并再次获得授权。

## 5. 验收标准

| 项目     | 通过条件                                                       |
| -------- | -------------------------------------------------------------- |
| 资料链   | 仅使用已有 Source Reader → Snapshot → MaterialStore 主链       |
| 基准事件 | 只来自去重后的 `surgery_record`；`mr_surgery` 不增量造事件     |
| 关联     | 结构化键优先；文本只允许严格唯一匹配；任何歧义失败关闭         |
| 结论     | 全部唯一关联才合规；已知缺表才缺陷；不确定仍 `data_gap`        |
| 可追溯   | 每个关联保存双端 source ref，客户解释不暴露内部字段名          |
| 非回归   | 030/033 及未涉及规则不变；LLM/Token 增量为 0                   |
| 范围     | 无字段映射、029、064–066、API、前端、Canonical、迁移或配置改动 |
