# 泸县0609真实病历合成验证集 v3 data_gap 根因清账

## 冻结基线

- 审计 Git：`d78397a984e62ec58c7db28925c099b1bddf764e`
- 冻结任务：`1f63f39e-6ce2-44f7-a86b-5d65032e93a9`（运行完成：2026-08-03 20:21:07.832675）
- 病例 / 规则：38 / 75
- 三坐标集合哈希：`fcaa891604a95ea308afc278c485b56026e766687a4172a5e668b3fd375c5126`
- 引擎配置：`{"execution_mode":"multi","execution_rule_count":75,"execution_strategy":"fast_screen","max_parallel_records":3,"model_code":null,"quality_profile":"throughput_v1","run_mode":"parallel","validation_mode":"customer"}`
- 最终状态：`{"compliant":353,"data_gap":651,"non_compliant":322,"not_applicable":1460,"uncertain":64}`

本报告在单个 `REPEATABLE READ, READ ONLY` 事务中重建当前资料快照，未写入数据库、未运行质控、未调用 LLM。

## data_gap 汇总

- data_gap：**651** 条，涉及 **38** 份病例。
- 已证实的真实/保守资料缺口：239 条；存在资料缺口指征、但尚不能定性：352 条；存在关联失败指征、但尚不能定性为引擎缺陷：2 条；已证实的交付/读取错误：0 条；证据不足、不得臆断：9 条。
- 分类置信度：`{"confirmed":288,"indicated":354,"unresolved":9}`。

### 按主要根因

| 根因                       | 条数 |
| -------------------------- | ---: |
| source_truly_absent        |  352 |
| authoritative_time_missing |  124 |
| applicability_unresolved   |  115 |
| other_with_evidence        |   58 |
| event_linkage_failed       |    2 |

### 影响最大的三个根因

- `source_truly_absent`：352 条。
- `authoritative_time_missing`：124 条。
- `applicability_unresolved`：115 条。

### 真实缺失与错误 data_gap 比例

- 仅以可证实结果计：真实/保守资料缺口 239，错误 data_gap 0；比例为 `239:0`。
- 另有 352 条来源为空指征、2 条关联失败指征和 9 条未解析项，均不得强行并入任一侧。

### 按规则（全部见 CSV）

| 规则       | data_gap 条数 |
| ---------- | ------------: |
| LX0609-051 |            36 |
| LX0609-060 |            36 |
| LX0609-062 |            35 |
| LX0609-071 |            35 |
| LX0609-063 |            30 |
| LX0609-028 |            26 |
| LX0609-003 |            24 |
| LX0609-031 |            24 |
| LX0609-039 |            24 |
| LX0609-012 |            21 |
| LX0609-010 |            20 |
| LX0609-011 |            20 |
| LX0609-033 |            20 |
| LX0609-052 |            20 |
| LX0609-053 |            20 |
| LX0609-020 |            19 |
| LX0609-023 |            19 |
| LX0609-025 |            18 |
| LX0609-069 |            18 |
| LX0609-007 |            18 |
| LX0609-064 |            17 |
| LX0609-065 |            17 |
| LX0609-066 |            17 |
| LX0609-013 |            12 |
| LX0609-024 |            12 |
| LX0609-021 |            11 |
| LX0609-022 |            11 |
| LX0609-049 |             9 |
| LX0609-005 |             8 |
| LX0609-017 |             8 |
| LX0609-055 |             8 |
| LX0609-006 |             6 |
| LX0609-029 |             6 |
| LX0609-014 |             5 |
| LX0609-015 |             4 |
| LX0609-043 |             4 |
| LX0609-070 |             4 |
| LX0609-047 |             4 |
| LX0609-016 |             3 |
| LX0609-008 |             2 |

## 资料链结论与限制

1. 每一条 CSV 均记录了规则依赖、重建 Snapshot 的查询状态/行数、MaterialStore 行数/截断、任务原始项与 Envelope 一致性及首次可观察异常层。
2. 历史任务没有持久化逐规则 `RuleDecision` 或当时的 Snapshot Observation；因此本审计不能伪造‘历史原始 Decision 已完全回放’。CSV 统一标记 `historical_rule_decision_not_persisted`。
3. `required_field_missing` 且来源已读取的结果统一保守归为 `other_with_evidence`，不把泛化文案擅自判成字段映射缺陷。
4. 本阶段未修改任何规则、Canonical、Envelope、API、前端、LLM 调用或资料链。是否进入最多两个确定性修复，必须先从 CSV 中选出至少影响 3 条且能定位首次丢失位置的根因。

## 下一步建议

1. 本阶段没有修复项：任务限定为只读审计，不能为了减少 data_gap 改写状态。
2. 未修复的资料能力项：`LX0609-071` 35 条；`LX0609-033` 14 条。它们的首次可观察异常层是 Source Registry/Reader 能力，不是可在本任务中凭空补齐的源数据；修复会引入新的资料读取能力，触发停止条件。
3. `authoritative_time_missing` 分布在多个规则族，现有证据指向合成记录缺少规则所需的权威时间，而非一个可安全共用的代码缺陷；应先补验证资料或逐规则确认时间来源。
4. 对 `unresolved` 项保留 data_gap，先补可观测 trace 或在用户批准后用受控重跑验证，不能直接改变临床结论。
5. 本报告完成后暂停，等待独立审核确认根因分类与范围。
