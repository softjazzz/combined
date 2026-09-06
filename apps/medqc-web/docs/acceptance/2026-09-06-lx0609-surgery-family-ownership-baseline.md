# LX0609 阶段 2-A：手术存在性与手术门控族调用链、所有权基线

## 结论与范围

**状态：只读审计完成；尚未开始生产迁移或行为冻结提交。**

阶段 2-A 不能按规则编号连续性设计为一个“大手术族”。正式依赖目录和实际执行器显示，必须拆为两个可独立冻结、迁移和回滚的小闭环：

| 小闭环     | 客户规则                     | 实际 `executor_key` | 执行入口                                                                        |
| ---------- | ---------------------------- | ------------------- | ------------------------------------------------------------------------------- |
| 手术存在性 | 030、032                     | `surgery_presence`  | `native_execution.execute_luxian_0609_native_rules()`                           |
| 手术门控   | 003、024、025、028、031、033 | `surgery_gate`      | `native_surgery_gate_execution.execute_luxian_0609_native_surgery_gate_rules()` |

以下规则明确排除出本阶段，不能因读取同一手术资料而混迁：

| 规则    | 实际归属           | 排除原因                                                              |
| ------- | ------------------ | --------------------------------------------------------------------- |
| 029     | `surgery_document` | 术前小结逐台关联属于手术文书规则。                                    |
| 034–039 | `surgery_document` | 麻醉知情、麻醉访视、麻醉记录和术前讨论是阶段 2-B 的完整职责。         |
| 040     | `surgery_mdt`      | 四级手术 MDT 有独立的四级触发、急诊豁免和受控语义抽取，属于阶段 2-C。 |

`003` 虽然依赖麻醉记录辅助确定手术时间，`031` 也会读取术前小结/讨论作为关联材料，但它们的实际执行器仍是 `surgery_gate`；这些依赖不改变本阶段的所有权边界。

## 调用链与正式主链

审计基线为当前工作树的正式 unified 执行设计。`LUXIAN_0609_UNIFIED_ENGINE_ENABLED=true` 是后续三业务入口验收的前提；`execution.py` 中仅在 unified 未启用时使用的直接调用兼容段不是本阶段迁移目标，不能用旧调度替代正式验收。

```text
规则目录 / rule_contracts / native_package 权威依赖清单
  -> execution.prepare_luxian_0609_execution
  -> Luxian0609ExecutionEngine
  -> executor_registry
       -> surgery_presence（030、032）
       -> surgery_gate（003、024、025、028、031、033）
  -> 执行器输出 RuleDecision + fact_refs + 原始 customer_display_facts
  -> decision_binding.bind_and_reduce_luxian_0609_rule_decisions
  -> aggregate_luxian_0609_orchestrated_results
  -> aggregate_luxian_0609_results
       -> 公共 project_selected_document_evidence
       -> Canonical Finalizer / Renderer
       -> 仅装配、排序、统计
```

关键边界：

- `decision_binding.py` 校验同一 Evidence Session、规则允许来源和 `fact_refs`，合同或引用不合法只能收敛为 `technical_error`；
- `customer_evidence_enrichment.project_selected_document_evidence()` 只消费已绑定的 `fact_refs`，并统一生成文书 ID/来源坐标；它不得按标题、时间或展示事实重新选择文书；
- `canonical_result_finalizer.py` 只能验证受控客户事实、补齐通用资料缺口解释和 fail-closed；不能重新判定手术事实；
- `customer_renderer.py` 的标题、说明、整改模板属于声明式客户文案，本阶段不改变其业务口径；
- 聚合器在迁移完成后不得继续按本阶段规则号解释状态、事实或证据。

## 当前执行器、适用性与来源事实

### 手术存在性：030、032

`native_execution.py` 的 `NATIVE_RULE_IDS` 实际仅为 030、032。它们使用正式手术记录和 `mr_surgery` 的严格时间、逐台关联：

- 030：已实施手术与手术记录存在性；
- 032：已实施手术与手术安全核查表存在性；多台手术时仅按“手术时间”精确到分钟的双向唯一映射关联。

`surgery_applicability.resolve_surgery_applicability()` 是共用的“已实施手术”边界：肯定事实可由可信来源独立证明；否定结论要求来源完整且不存在已实施手术；目录确认的非手术操作不触发手术规则。它不凭术式名称、科室或计划信息推断已经实施。

### 手术门控：003、024、025、028、031、033

`native_surgery_gate_execution.py` 的 `SURGERY_GATE_RULE_IDS` 为 003、024、025、028、031、033，`EXECUTOR_KEY = "surgery_gate"`。其受控来源和业务职责如下：

| 规则 | 受控来源/关键事实                                                      | 判定要点                                                         |
| ---- | ---------------------------------------------------------------------- | ---------------------------------------------------------------- |
| 003  | `surgery_record`、`anesthesia_record`、`mr_surgery`                    | 手术结束至手术记录完成的 24 小时时限及单台关联。                 |
| 024  | `surgery_record`、诊断、病理、出院阶段资料                             | 恶性肿瘤手术的淋巴结处理/未处理原因。                            |
| 025  | `surgery_record`（五个植入字段唯一事实源），可选 `daily_course_record` | 永久植入物实际使用及五字段完整性；病程不能替代正式手术记录字段。 |
| 028  | `surgery_record`、`inpat_drug_order`、`daily_course_record`            | I/II 类切口预防用药与实际给药/停药时限。                         |
| 031  | `surgery_record`、`mr_surgery`，可读取术前材料辅助关联                 | 每台手术的术者签名资格；禁止用提交人替代术者签名。               |
| 033  | `surgery_record`、`surgery_inform_consent`                             | 已实施手术的知情同意书；多次手术/多份同意书需要受控语义关联。    |

024、025、028、033 可合并一次裁剪后的受控语义事实抽取；Python 保有时间边界、字段范围、证据引用和最终状态映射。触发来源超过安全容量时保持 `data_gap`，不得静默截断后继续调用模型。

## 聚合器所有权基线

审计对象为 `backend/app/services/luxian_0609_result_aggregator.py`，当前约 **5,187 行**。阶段 2-A 规则的直接文本引用基线如下：

| 规则 | 当前直接引用数 | 聚合器现有职责                                                | 迁移目标                                             |
| ---- | -------------: | ------------------------------------------------------------- | ---------------------------------------------------- |
| 003  |              5 | 与 044 共享的状态一致性映射；手术记录时限展示事实             | 只移出 003 条目，044 保留到输血族边界。              |
| 024  |              1 | 淋巴结处理缺失事实白名单                                      | 迁至 `surgery_gate` 事实合同。                       |
| 025  |             12 | 严格 facts 校验、状态一致性、植入物逐事件证据、旧证据回退控制 | 完整迁至 `surgery_gate` 合同；不得复制旧来源级反查。 |
| 028  |              1 | 预防用药时长/切口等级展示事实白名单                           | 迁至 `surgery_gate` 事实合同。                       |
| 030  |              1 | 手术记录 target-document 来源推断                             | 迁至 `surgery_presence` 合同与事实引用。             |
| 031  |              3 | 逐台签名展示 facts 的 schema/字段校验                         | 迁至 `surgery_gate` 事实合同。                       |
| 032  |              1 | 核查表 target-document 来源推断                               | 迁至 `surgery_presence` 合同与事实引用。             |
| 033  |              2 | 同意书展示 facts 和证据来源白名单                             | 迁至 `surgery_gate`；证据最终由公共投影获得。        |

### 必须迁出的手术存在性分支

| 位置                | 当前职责                                                                               | 删除条件                                                                    |
| ------------------- | -------------------------------------------------------------------------------------- | --------------------------------------------------------------------------- |
| 聚合器 `:3543-3544` | 030/032 的 `target_document` 到 `surgery_record`/`surgery_safecheck_record` 的来源推断 | 执行器输出合法 facts 和 `fact_refs`，Binding 与公共文书投影能产生等价坐标。 |

### 必须迁出的手术门控分支

| 位置                                                       | 当前职责                                                         | 共享边界或删除条件                                                        |
| ---------------------------------------------------------- | ---------------------------------------------------------------- | ------------------------------------------------------------------------- |
| `:301-323`                                                 | `_validate_lx0609_003_044_fact_status()` 为 003/044 二次解释状态 | 仅删除 003 映射，必须保留 044。                                           |
| `:326-359`、`:425-441`、`:483-486`                         | 025 的严格事实—状态校验、复制和清洗                              | 由 gate 映射合同和 Finalizer fail-closed 替代。                           |
| `:777`、`:1022`、`:3570`                                   | 031 的逐台签名 kind、事件列表和字段白名单                        | 迁至 gate 映射合同；冻结逐台缺项事实。                                    |
| `:2408`                                                    | 024 的恶性手术/淋巴结处理展示 facts                              | 迁至 gate 映射合同。                                                      |
| `:2437`                                                    | 028 的切口、实际间隔与阈值展示 facts                             | 迁至 gate 映射合同。                                                      |
| `:2762`、`:3931-3954`、`:4550`、`:4825-4838`、`:4919-4925` | 025 的客户 facts、逐事件证据和兼容证据回退                       | 新主链须优先命中 selected-document 公共投影；严禁把来源级反查搬到新模块。 |
| `:2946`                                                    | 003 的时限展示 facts                                             | 迁至 gate 映射合同。                                                      |
| `:2981`、`:3850`                                           | 033 的同意书 facts 和仅 `surgery_record` 的旧证据白名单          | facts 迁出；证据坐标由公共投影唯一拥有。                                  |

### 明确不动的共享分支

| 位置                                | 保留归属           | 原因                                      |
| ----------------------------------- | ------------------ | ----------------------------------------- |
| `:301-323` 中 044 部分              | 输血族             | 003/044 只是共享校验器，不能整段删除。    |
| `:3542`                             | 029 / 阶段 2-B     | 同一 target-document 映射中的术前小结键。 |
| `:2477-2600`、`:3594`、`:3951-3961` | 034–039 / 阶段 2-B | 麻醉文书和术前讨论规则的独立业务事实。    |
| `:2709`、`:3851`                    | 040 / 阶段 2-C     | MDT 的四级手术触发与 `mr_surgery` 证据。  |

`canonical_result_finalizer.py` 仍有 028 的资料缺口文案和 031 的资料缺口文案。这些声明式说明可以保留，但不得再承担 facts 校验或证据选择；如迁移发现它们正在解释业务事实，必须拆开后再继续。

## 状态 × 资料形状基线

以下是冻结和后续真实病例集的最低矩阵。不要为覆盖率强造每条规则的 `uncertain`：030/032 的合同支持 `evaluation_unknown -> uncertain`，但当前正常来源路径没有已证明的真实业务资料形状；应标记为“合同可达，待真实样本证明”。其余 gate 规则的模型未知/截断按既有口径收敛为 `data_gap` 或 `technical_error`，不应伪装成 `uncertain`。

| 资料形状                                          | 030/032 预期                                        | 003/024/025/028/031/033 预期                                 | 重点证据                                                                                       |
| ------------------------------------------------- | --------------------------------------------------- | ------------------------------------------------------------ | ---------------------------------------------------------------------------------------------- |
| 来源完整、无已实施手术                            | `not_applicable / performed_event_absent`           | `not_applicable / performed_event_absent` 或规则自身触发缺失 | 完整空来源；非手术操作也不触发。                                                               |
| 取消/计划未实施，来源完整且无可信实际时间         | `not_applicable`                                    | `not_applicable`                                             | 当前代码主要以可信实际开始/结束时间认定“实施”；须单列冻结样本。                                |
| 明确已实施、单台且要求文书/字段满足               | `compliant`                                         | `compliant`                                                  | `fact_refs` 能定位同一真实文书。                                                               |
| 明确已实施、单台且目标文书/字段缺失或超时         | `non_compliant`                                     | `non_compliant`                                              | 003 的 24 小时、025 五字段、028 实际区间、031 签名、033 同意书。                               |
| 两台手术、两份目标文书可唯一关联                  | `compliant` 或逐台 `non_compliant`                  | 逐台综合，已证明缺陷不得被另一台覆盖                         | 032 精确分钟双向映射；031 逐台签名。                                                           |
| 两台手术、仅一份术前小结/同意书或文书无法唯一关联 | 030/032 视目标文书与关联规则而定，歧义为 `data_gap` | `data_gap / association_failed` 或对应资料不足               | 不能凭行数、标题或任意一份文书替代逐台关联。                                                   |
| 来源未接入、截断、权威时间缺失或关联冲突          | `data_gap`                                          | `data_gap`                                                   | `source_unavailable`、`source_truncated`、`authoritative_time_missing`、`association_failed`。 |
| 查询异常、snapshot/合同不匹配、模型输出非法       | `technical_error`                                   | `technical_error`                                            | 技术失败不得落入 `data_gap` 或 `uncertain`。                                                   |

### 取消事件的已知风险

当前 `has_trusted_performed_surgery()` 以可信实际时间为核心，并未发现针对 `order_status=取消` 的独立口径分支。因此：

1. 计划/取消记录没有可信实际时间时，应按“未实施”走不适用；
2. 若源表的取消行错误携带可被识别为实际手术的时间，当前逻辑可能仍将其视为已实施；
3. 阶段 2-A 冻结必须先加入该资料形状的测试并记录现有行为；如要更改口径，必须另立业务修复，不得混入等价迁移。

## 现有测试与冻结缺口

已有单元测试已覆盖重要安全边界：

- 003：多 `mr_surgery` 事件同结束时间的关联歧义、严格时区/结束时间、来源异常；
- 031：逐台签名、术者与提交人区分、主表/手术记录回退、跨表不能唯一关联；
- 025：多事件优先级、五字段唯一事实源、两份手术记录歧义、证据 ID 不伪造；
- 028：切口/预防药/实际时间边界、治疗转换、跨文书时间关联；
- 033：完整空来源、空壳同意书、多份同意书与当前手术关联、LLM 非法输出；
- 032：多台手术的精确分钟关联与关联失败形态；
- Binding：同一 snapshot、允许来源和 `fact_refs` 校验；公共证据投影：只按已选文书引用定位。

尚缺以下冻结，未完成前不得开始删除聚合器分支：

1. 030/032 与 003/024/025/028/031/033 各自的聚合器前后 Canonical 冻结：`status`、`reason_code`、`customer_display_facts`、`criterion_results`、`fact_refs` 语义来源、客户文案和证据坐标集合；
2. 真实 unified 的单规则、批量质控、客户样本验证三入口等价测试；必须记录 `executor_key`、无旧链回退和 Canonical 落库/API 一致；
3. “取消或计划未实施但来源完整”资料形状；
4. 030/032 `evaluation_unknown -> uncertain` 的真实可达性证明，或明确将其保留为合同分支而不纳入客户语义覆盖；
5. 聚合器归零守卫：presence 对 030/032，gate 对 003/024/025/028/031/033；守卫必须只在迁移提交添加，基线提交不使用 `xfail` 伪绿。

## 后续文件白名单与归零口径

### 2-A.1：手术存在性（030、032）

允许的最小生产文件：

1. `backend/app/services/luxian_0609/surgery_presence_result_mapping.py`（新增）：030/032 的安全客户事实合同与状态一致性；不得读库、调用 LLM 或创建第二套证据 DTO；
2. `backend/app/services/luxian_0609/canonical_result_finalizer.py`：接入上述合同并统一 fail-closed；
3. `backend/app/services/luxian_0609_result_aggregator.py`：删除 030/032 的业务分支，保留通用装配；
4. `backend/app/services/luxian_0609/native_execution.py`：仅在冻结证明 `fact_refs` 或客户事实合同确有缺口时调整，禁止改判定口径。

归零条件：聚合器不再出现 030/032 的 `target_document`、来源选择、facts 校验或证据回退；相同冻结输入的状态、原因码、客户事实和去重后的证据坐标集合不变。

### 2-A.2：手术门控（003、024、025、028、031、033）

允许的最小生产文件：

1. `backend/app/services/luxian_0609/surgery_gate_result_mapping.py`（新增）：六条规则的安全客户事实合同和事实—状态一致性；
2. `backend/app/services/luxian_0609/canonical_result_finalizer.py`：接入 gate 合同并统一 fail-closed；
3. `backend/app/services/luxian_0609_result_aggregator.py`：仅删除上表列出的 gate 专属校验、来源白名单和证据回退；
4. `backend/app/services/luxian_0609/native_surgery_gate_execution.py`：仅在冻结证明 facts 或 `fact_refs` 未足以支持公共投影时调整；Prompt、调用上限和状态映射不得变化。

归零条件：聚合器中不再按 003/024/025/028/031/033 解释业务状态、受控 facts 或文书来源。025 的旧来源级证据回退必须消失，改由执行器 `fact_refs`、Binding 和 `project_selected_document_evidence()` 得到等价证据坐标。003/044、029、034–040 的共享或相邻分支不计入 gate 归零，也不得受影响。

后续测试白名单：

1. `backend/tests/unit/test_luxian_0609_native_execution.py`、`test_luxian_0609_native_surgery_gate_execution.py`、`test_luxian_0609_surgery_text_fact_contract.py`：冻结资料形状、状态、原因码、事实引用、LLM 调用和 Prompt；
2. `backend/tests/unit/test_luxian_0609_surgery_presence_result_mapping.py`（新增）与 `test_luxian_0609_surgery_gate_result_mapping.py`（新增）：字段合同、非法 facts 的 `technical_error` 收敛和共享规则不回归；
3. `backend/tests/unit/test_luxian_0609_surgery_presence_aggregator_ownership.py`（新增）与 `test_luxian_0609_surgery_gate_aggregator_ownership.py`（新增）：聚合器分支归零；
4. `backend/tests/unit/test_luxian_0609_canonical_result_finalizer.py`、`test_luxian_0609_result_aggregator.py`、`test_luxian_0609_decision_binding.py`：公共合同和装配回归；
5. 后续阶段 2-C 才补充正式三入口和真实模型性能记录，不能用局部单测代替。

默认禁止改动 `execution.py`、`executor_registry.py`、`native_package.py`、`customer_renderer.py`、数据库、API、前端或任意 Prompt。若公共事实/证据合同无法表达冻结结果，必须先报告缺口、替代方案和最小影响范围，不能直接向聚合器增加新规则分支。

## 风险与停止条件

1. 003/044、029/030/032、034–040 在聚合器有共享或相邻代码；机械按大段删除会导致跨阶段回归。
2. 025 的植入物逐事件证据和兼容回退是本阶段最大风险。若新 `fact_refs` 无法得到等价证据坐标，先停止迁移，不得重建来源级猜测逻辑。
3. 030/032 及 003/031/033 的多台手术口径依赖真实事件关联。未获得唯一关联时必须保持 `data_gap`，不能把“只有一份术前小结”简化成单纯文书缺失。
4. 本文仅完成所有权与测试缺口基线；不代表阶段 2-A 的生产迁移、三入口验收、真实模型性能验收或客户环境验收已经通过。
