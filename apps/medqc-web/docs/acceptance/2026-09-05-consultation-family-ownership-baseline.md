# 会诊规则族所有权收口基线（B1）

日期：2026-09-05

## 结论与范围

本基线只为下一闭环（B2）冻结会诊规则族的真实主链、职责迁移边界和验收口径。B1 的
允许写入范围仅为新增／修订验收测试和本文档；本次 B1 实际新增了冻结测试和本文档。B1 不改生产
代码、Prompt、API、数据库 schema 或前端，也不调用模型或写数据库。

正式主链不是历史 `native_consultation_execution.py` 的
`execute_luxian_0609_native_consultation_rules()`（第 1999 行）。正式主链为
`native_consultation_episode_execution.py` 的
`execute_luxian_0609_native_consultation_episode_rules()`（第 3026 行）：
`execution.py` 在统一引擎注册该函数（第 435–438 行），非统一引擎回退也直接调用该
函数（第 625–656 行）。执行器键唯一为 `consultation_quality`（episode 文件第 52 行；
registry 第 442–462 行）。

本规则族的范围严格为 `LX0609-020/021/022/023`：

- `CONSULTATION_EPISODE_RULE_IDS` 在 episode 执行器第 40–44 行声明四条规则；
  `native_package.py` 第 68–74 行也只将这四条路由至该族。
- 包级开关未开启 execution-link 时，`PACKAGE_NATIVE_CONSULTATION_RULE_IDS`
  只暂放行 021/022（episode 文件第 46–51 行）；开启后才放行完整的四条规则
  （`native_package.py` 第 343–349 行）。这是发布开关，不是第二个业务所有者。
- `LX0609-069` 是独立的会诊时限规则：聚合器的
  `controlled_consultation_events()`（第 628–675 行）及
  `consultation_timeliness_check` 映射（第 821、943、1391 行）保持在 069 原链，
  明确排除在本次会诊质量族迁移之外。

根因是客户结果聚合器仍同时持有 020–023 的事实合同解释、证据来源推断及
“事实不完整时改写客户结论”的规则族语义。这违反“执行器判定、Renderer 组织文案、
Finalizer 校验补缺、Aggregator 只装配排序”的边界；它也使同一会诊事实在执行器和
聚合器各有一个解释点。

## 当前主链和保留边界

```text
package plan / executor registry
  -> native_consultation_episode_execution (020–023 决策、facts、fact_refs、usage)
  -> Luxian0609ExecutionContext.customer_display_facts（execution.py:954）
  -> aggregate_luxian_0609_orchestrated_results（execution.py:989）
  -> aggregate_luxian_0609_results（result_aggregator.py:5858）
  -> customer renderer / canonical finalizer
```

聚合器在 `aggregate_luxian_0609_results()` 第 5893–5901 行已经先尝试
`validate_luxian_0609_executor_customer_display_facts()`；该公共接收边界在
`canonical_result_finalizer.py` 第 173–211 行。B2 应让会诊族也经由该边界交付已验证、
无内部 ID 的客户事实，不能让 Aggregator 继续按会诊规则号解释 facts。

## 聚合器专属职责清单（五类）

下表是 B2 前的完整、仅针对 020–023 的聚合器职责。行号均为 B1 当前源码行号。
“删除点”指 B2 成功后必须从聚合器删除或改为不再按会诊规则号分支的代码；不是保留
兼容入口的建议。

| 类别                                                                | 当前符号与行号                                                                                                                                                              | 当前所有者                         | 迁移后唯一所有者                                                                                                            | B2 删除点                                                                                                   |
| ------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ---------------------------------- | --------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------- |
| 1. 旧 payload 的事实白名单、规范化和 023 笼统执行兜底               | `safe_luxian_0609_customer_display_facts()` 第 492 行；020/021/022 分支第 4160–4336 行；020/023 分支第 4337–4651 行；023 旧兜底第 4652–4671 行                              | `luxian_0609_result_aggregator.py` | 正式 episode executor（私有 `consultation_customer_projection.py` 实现投影）；Finalizer 仅作无内部 ID 接收校验              | 删除上述四个会诊分支；聚合器不得为 020–023 回退 `safe_luxian_0609_customer_display_facts()`                 |
| 2. 从旧 display facts 推断客户证据文书                              | `_customer_evidence_from_display_facts()` 第 4685 行，020/023 专属来源分支第 5045–5080 行，020/021/022 的 `source_document_ids` 类型猜测第 5082–5121 行                     | `luxian_0609_result_aggregator.py` | 正式 episode executor 在判定选择点绑定 `RuleDecision.fact_refs`；公共 `project_selected_document_evidence()` 只投影这些坐标 | 删除 020–023 的来源白名单/ID 猜测；不得由 Aggregator 根据 `source_document_ids` 补造坐标                    |
| 3. 无效/不完整 facts 时仍从内部 ID 回退展示证据                     | `_customer_evidence_from_incomplete_consultation_facts()` 第 5124–5173 行；旧结果路径调用第 5816–5824 行；聚合循环调用第 5945–5955 行                                       | `luxian_0609_result_aggregator.py` | 正式 episode executor 的 fail-closed 投影合同：facts 不合法即产生既有技术失败；只交付已经绑定并可公共投影的 `fact_refs`     | 删除函数及两处调用；不存在聚合器会诊失败证据 fallback                                                       |
| 4. 旧 native-result 路径中把 facts 不完整改写为技术错误并拼客户结论 | `_copy_native_customer_fields()` 第 5553 行；会诊识别第 5557–5564 行；拒绝/标记第 5622–5683 行；改写 metadata 与结果第 5767–5805 行                                         | `luxian_0609_result_aggregator.py` | 正式 episode executor 输出的 `RuleDecision`/结果及其 fail-closed 投影合同；Renderer 只按确定的 status/reason/facts 组织文案 | 删除所有仅针对 020–023 的 `consultation_facts_incomplete`、状态/文案/`criterion_results` 改写与失败证据分支 |
| 5. typed-decision 聚合循环中再次识别会诊 facts、再次改写技术错误    | `aggregate_luxian_0609_results()` 第 5858 行；`incomplete_consultation_rules` 第 5881 行；拒绝/收集第 5913–5930 行；异常豁免第 5941–5955 行；Renderer 后改写第 5977–6001 行 | `luxian_0609_result_aggregator.py` | 正式 episode executor 一次决定；聚合器仅把通用已验证 facts 传给 Renderer 并装配公共 evidence                                | 删除集合、会诊特判日志、豁免、Renderer 后二次改写；保留通用 scope/重复 facts 防御，不得保留会诊例外         |

第 1–5 类只覆盖 020–023；第 069 的嵌套
`controlled_consultation_events()` 不在删除范围。迁移后 020–023 的**正式、唯一业务
owner** 是 `native_consultation_episode_execution.py` 的
`execute_luxian_0609_native_consultation_episode_rules()`，即 `consultation_quality`
episode executor；`consultation_customer_projection.py` 只是这个 owner 的私有深模块，
不构成第二个 owner。它不导入 Aggregator、不产生第二个 Bundle/Resolver/状态机。
Finalizer 只做公共合同的“接受或拒绝”，Renderer 只将确定的 facts/status/reason_code
转为客户文案。

## 两个孤儿／历史合同

1. `native_consultation_execution.py`：历史执行器，`CONSULTATION_RULE_IDS` 在第 46–53
   行、入口在第 1999 行；仓库搜索显示生产代码未导入它，只有
   `test_luxian_0609_native_consultation_execution.py` 直接测试它。本次不把它接回
   主链、不复制其 Prompt/重试/口径，也不以迁移名义删除它。若未来清理，须另立任务，
   先冻结该遗留合同的仍在使用证据。
2. `consultation_020_relation_contract.py`：孤立的 020 历史事实合同，
   `validate_consultation_020_relation_payload()` 第 106 行、
   `reduce_consultation_020_relation()` 第 263 行。仓库搜索显示仅其专属单测导入，
   episode 主链不导入它。本次不将其迁入 episode 执行器，不建立 adapter，也不让它
   重新解释 020 的现有 episode facts；避免形成两套 020 关系状态机。
3. `consultation_fact_contract.py`：会诊历史／测试事实合同（其专属单测为
   `test_luxian_0609_consultation_fact_contract.py`）。它不是 episode executor 的生产
   import，也不得成为 B2 的迁移目标或迁移后 owner；本次不做 adapter、合并或删除。
   未来若处理，须以真实主链调用证据另立任务，不能把测试合同反向接入生产。

## 五类病例冻结

每类病例必须使用固定的合成输入和确定的 stubbed LLM 响应，在 B2 前后分别跑
`episode -> decision binding -> aggregate -> canonical projection`。断言不比较摘要哈希；
按语义比较以下整组输出：四条规则的 `status`、`reason_code`、受控
`customer_display_facts`、解析后 `fact_refs` 的来源与证据坐标（`source_type`、
`source_document_id`、`field_path`、`record_time`）、`customer_evidence`、客户
`findings/evidence/suggestion`，以及每阶段 Prompt 调用次数和
`prompt_tokens/completion_tokens/total_tokens`。内部文书 ID 不得进入 customer facts。

| 冻结病例                              | 主覆盖现有测试                                                                                                                                                     | 预期客户结论（020/021/022/023）                                                                            | Prompt/Token 合同                                      |
| ------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------ | ---------------------------------------------------------------------------------------------------------- | ------------------------------------------------------ |
| A. 明确申请、明确意见、后续具体执行   | `test_020_023_execution_state_mapping`（episode 测试第 2251 行）及 `test_020_display_facts_bind_selected_opinion_and_execution_documents`（第 2651 行）            | 四条均为既有合规结论；事实和坐标定位到实际意见与执行材料                                                   | 保持两阶段既有调用；Token 精确等于 B1 fixture 基线     |
| B. 明确意见但只有笼统“遵会诊意见”执行 | `test_020_generic_course_trace_is_compliant_but_023_is_non_compliant`（第 2520 行）                                                                                | 020 保持合规，023 保持不合规；021/022 不被第二阶段改写                                                     | 保持既有两阶段调用与 Token                             |
| C. 明确意见、确认无执行               | `test_020_023_execution_state_mapping`（第 2251 行）                                                                                                               | 020 保持不合规、023 保持不适用；021/022 保持第一阶段结论                                                   | 保持既有两阶段调用与 Token                             |
| D. 来源/住院窗口不足                  | `test_020_023_without_authoritative_stay_window_is_data_gap_without_llm`（第 3987 行）及 `test_stage_two_stay_window_gap_does_not_downgrade_021_022`（第 4038 行） | 020/023 保持 `data_gap` 和原 reason；021/022 保持独立第一阶段结论                                          | 第二阶段零调用、零 Token；不得为补投影新增调用         |
| E. 模型输出或展示合同非法             | `test_020_023_semantic_contract_failure_keeps_typed_decision_technical_error`（第 4427 行）及 `test_invalid_episode_payload_is_technical_error`（第 1982 行）      | 相关规则保持 `technical_error` 与既有技术 reason；不残留临床 data-gap/criterion 结论，未受影响规则不被改写 | 保持既有失败路径调用数、Token 与重试语义；不得新增重试 |

“Token 精确等于 B1 fixture 基线”仅适用于 stubbed 可重复输入；真实模型性能验收另见
下节，不能将不同供应商的实际输出 Token 当作逻辑回归失败。

## 三入口隔离验收

同一五类输入在以下三条入口分别验收，比较每条入口的 canonical 业务结果和客户证据
坐标；入口之间不得通过聚合器的会诊特判互相补偿。真实验收必须使用可隔离、可清理的
**可写数据库**（独立 schema/数据库或等效临时环境），不得共享生产库或复用其他验收
任务的写入；每轮记录 visit/run 标识、写入对象范围和清理结果。B1 只记录此门禁，
不建库、不写库、不调用任一入口。

1. 单规则业务入口：在同一批任务中只选择一个 `rule_id`，分别覆盖 020、021、022、
   023 和 069 对照；验证单规则选择不会改变会诊族 facts、fact_refs 或客户结论。
2. 病历池批量业务入口：用同一冻结病例组成病历池批量任务，验证每条病历和每项规则的
   结果独立，且批量汇总不会二次解释会诊 facts。
3. 客户样本验证业务入口：从客户样本验证创建并执行任务，验证客户可见结果、证据坐标
   与单规则／病历池结果一致。

三条业务入口最终必须汇入同一个 workspace batch worker；验收需记录三条入口到该 worker
的调用证据以及 worker 产出的同一批次结果。`SichuanQCService._evaluate_rules_orchestrated()`
（`sichuan_qc_service.py` 第 1115、1169、1225 行）、非统一引擎下
`prepare_luxian_0609_execution()`（`execution.py` 第 213、625–656 行）和
`run_luxian_0609_preproduction()`（`preproduction_runner.py` 第 633、687、705 行）只可
作为附加路由回归：它们不能替代上述三条用户业务入口的验收。

每条入口都要覆盖有效 facts、非法 facts 和 069 对照：020–023 的非法 facts 必须由
正式 episode executor 侧 fail-closed，069 的 `consultation_timeliness_check` 结果不变。
验收同时断言 `native_consultation_execution`、`consultation_fact_contract` 和
`consultation_020_relation_contract` 均未被生产导入。

## 性能与模型协议

B1 不调用真实模型。B2 完成后，以同一五类中需要模型的固定病例、同一模型配置和同一
只读数据快照执行真实模型预热后 10 次交替对比（基线/候选交替，先预热不计入）。记录
每次输入 token、调用次数和端到端 API 时间，使用中位数比较：

- 输入 token 不增加；
- 模型调用数完全一致；
- 中位耗时增加不超过 10%。

若任一项不满足，B2 不得以“结构收口”宣称通过；先给出 Prompt、候选资料、调用路径
和模型侧波动的分离证据。整个闭环不得新增任何 digest/SHA/摘要哈希；比较语义输出和
来源坐标即可；不得新增 Prompt digest 或任何其他摘要哈希。

## B2 文件白名单与巨型文件门禁

允许修改的生产文件为：

1. 新建 `backend/app/services/luxian_0609/consultation_customer_projection.py`；
2. `backend/app/services/luxian_0609/native_consultation_episode_execution.py`；
3. `backend/app/services/luxian_0609/canonical_result_finalizer.py`；
4. `backend/app/services/luxian_0609_result_aggregator.py`。
5. 新建 `backend/app/services/luxian_0609/consultation_decision_evidence.py`，承载逐文书
   材料绑定与执行器已选 `fact_refs` 的完整职责；
6. `backend/app/services/luxian_0609/customer_evidence_enrichment.py`，只增加公共的
   已选分组文书引用安全投影，不选择业务证据；
7. `backend/app/services/luxian_0609/decision_binding.py`，只允许 020–023 在
   `trigger_absent_complete` 时不伪造不存在的文书引用，其他规则和原因仍维持原合同。

第 5–7 项是 B2 审查中发现的必要边界修正：如果不建立单一的材料引用选择职责，
聚合器删除旧证据推断后正式 `RuleDecision` 将无法定位真实文书；如果不复用公共安全
引用投影，会诊族又会形成第二个客户证据投影器。它们不新增业务状态、Prompt、
执行器、fallback 或公开 DTO。

允许修改的测试文件仅为：

1. `backend/tests/unit/test_luxian_0609_native_consultation_episode_execution.py`；
2. `backend/tests/unit/test_luxian_0609_canonical_result_finalizer.py`；
3. `backend/tests/unit/test_luxian_0609_result_aggregator.py`；
4. `backend/tests/unit/test_luxian_0609_execution_routing.py`；
5. `backend/tests/unit/test_luxian_0609_consultation_decision_evidence.py`；
6. `backend/tests/unit/test_luxian_0609_selected_document_evidence.py`；
7. `backend/tests/unit/test_luxian_0609_decision_binding.py`；
8. `backend/tests/unit/test_luxian_0609_mainline_services.py`；
9. `backend/tests/unit/test_luxian_0609_consultation_family_architecture_freeze.py`；
10. 必要时新增一个只覆盖三入口隔离的
    `backend/tests/unit/test_luxian_0609_consultation_family_ownership.py`。

新模块是必要的：episode 执行器当前 3553 行、结果聚合器当前 6308 行，均已越过巨型
文件预警；被迁出的不是转发壳，而是完整的“020–023 已判定事实 -> 无内部 ID 客户
facts + 已绑定证据坐标”的投影合同。该模块必须小而深，只向 episode 执行器和 Finalizer
提供稳定的会诊族合同；不新增注册表、全局 Store、Bundle、fallback 或通用状态机。
`native_consultation_episode_execution.py` 只在已选择事实时调用它并输出结果；
`canonical_result_finalizer.py` 只接入该合同作为通用接收校验；Aggregator 只删除会诊
专属解释，保留通用装配。

不在白名单内、且明确禁止修改：Prompt 文本、规则口径、API 契约、数据库 schema、
前端、`native_consultation_execution.py`、`consultation_020_relation_contract.py`、069
链路、模型调用策略及重试策略。

## B2 完成判据与剩余风险

- 表中五类聚合器会诊专属职责的删除点全部消失；聚合器不再含 020–023 的事实解释、
  内部 ID 到客户证据推断或状态/文案二次改写。
- 五类冻结病例、三入口隔离、020–023 和 069 的反向隔离均通过；同输入的
  status/reason/facts/fact_refs/坐标/客户结论以及 stubbed 调用与 Token 等价。
- B2 后再跑 CodeGraph/源码搜索，正式调用链只到 episode 执行器；两个孤儿仍未被迁入
  生产主链。
- 性能协议满足且无新增摘要哈希后，才可提交并暂停等待下一授权。

剩余风险是历史聚合器合同覆盖面很广，删除局部 020–023 分支时可能误伤其他规则；因此
每次删除必须以范围搜索和 069 对照证伪。真实模型输出有供应商波动，故性能结论只以
规定的交替十次和中位数作判断，B1 不声称已有真实模型性能结果。
