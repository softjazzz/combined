# LX0609 阶段 1-A：输血 041–049 调用链与聚合器所有权基线

## 结论与状态

**状态：阶段 1-B 暂停，需先完成失败语义和证据选择的独立修复，再重新冻结；正式 worker/API 三入口验收留待阶段 1-C。**

2026-09-06 主协调复核发现以下准入缺口，原“可进入等价迁移”结论暂时撤回：

- 044/046 的模型调用异常、非法结构或非法引用，以及合法的语义未知，仍混合进入 `data_gap`；045 的通用布尔语义路径也将调用异常和非法结果归入资料不足。应按已批准的失败语义分别修复，并独立提交。
- 删除 045/046 聚合器证据回退后，多次输血冻结测试丢失两份 `bloodtrans_record` 坐标。执行器仅输出来源观察级引用，需补充同一 Evidence Session 中实际选中文书的既有引用。
- 045 旧冻结集合包含未参与确定性判定的 `daily_course_record`。不能为保持旧集合而人为选择无关文书；证据纠错应先独立完成，再以正确集合冻结。
- 044/047 还需验证申请理由、评价时间所在文书能够沿同一引用链定位。当前迁移改动尚未通过验收，未作为生产迁移提交。

失败语义修复复核：新增 044/046 实际 typed 调用至 Binding 的异常、非法 JSON、错误引用、合法未知和模型不可用测试，以及 045 通用布尔调用失败测试。原生测试 116 项通过；主协调扩大到 044 policy 后 123 项通过、1 项旧证据定位测试失败，该失败属于尚未完成的迁移。本族整体尚未通过。

049 补充基线：同一正式 typed 输血输入在原 HEAD 聚合器会抛 `Luxian0609CustomerDisplayFactsError`，并非已经稳定交付 `data_gap`。本轮新映射仅接管 041–048，049 的事实合同缺口单列待修。

本文件记录以下已存在的提交：

- 计划基线：`7b5beeb96f397005e44d106933b3d3d18c241dc3`（下称 `7b5`）；
- 冻结前缺陷修复一：`f4c5ee87d`，修复 047 多次输血时将早于最后一次输血结束的评价时间错误投影为最终评价；
- 冻结前缺陷修复二：`31fedfe44`，经独立复审后收紧 047 的评价时间权威性与缺失/过早时间语义；
- 冻结基线：`31fedfe44`。阶段 1-A 的行为比较、后续 1-B 等价迁移均以此提交为准。

冻结口径与本地结果：

- 047 缺少评价时间或评价时间早于对应输血结束时间时，保持 `data_gap / authoritative_time_missing`，不得伪装为合规或不合规；
- 非权威的评价时间 basis 必须被拒绝，不得参与 24 小时时限计算；
- 核心两文件聚焦测试 **98 passed**；扩大到五个相关文件的 `-k` 集合 **144 passed**；独立审查回归 **269 passed**。现有 warnings 均为既有警告；
- 上述测试是执行器、Binding/Finalizer 与聚合器合同冻结，不含正式 API 三入口、真实模型性能或客户环境验收。

`LX0609-041` 至 `LX0609-049` 的实际 `executor_key` 均为 **`transfusion`**，不是按编号连续性推定：

- `native_transfusion_execution.py:33-35` 将 `range(41, 50)` 定义为 `TRANSFUSION_RULE_IDS`，并声明 `EXECUTOR_KEY = "transfusion"`；
- `native_package.py:189-253` 构建权威依赖清单时，对成员命中 `TRANSFUSION_RULE_IDS` 的规则统一赋予 `native_async / TRANSFUSION_EXECUTOR_KEY`；
- 正式 unified 主链由 `execution.prepare_luxian_0609_execution` 准备执行计划，经 `Luxian0609ExecutionEngine` 和 `executor_registry` 选择 `transfusion` 执行器，最终进入 `execute_luxian_0609_native_transfusion_rules`；结果再进入 Binding、Finalizer 和聚合装配。
- `execution.py` 内存在的直接调用段属于 unified 未启用时的兼容/旧调度。它不是本阶段正式主链的冻结目标，也不能用来证明正式 worker 或 API 三入口走的是旧链。

| 规则 | 实际 executor_key | 原生执行入口                                   | 当前特例                                                                            |
| ---- | ----------------- | ---------------------------------------------- | ----------------------------------------------------------------------------------- |
| 041  | `transfusion`     | `execute_luxian_0609_native_transfusion_rules` | 程序化输血同意书存在性                                                              |
| 042  | `transfusion`     | 同上                                           | 程序化同意书字段完整性                                                              |
| 043  | `transfusion`     | 同上                                           | 程序化输血前九项检查                                                                |
| 044  | `transfusion`     | 同上                                           | 先程序化；仅“申请理由”候选不确定时调用一次受控 LLM                                  |
| 045  | `transfusion`     | 同上                                           | 程序化优先，不能定论时保留原有裁剪提示词路径                                        |
| 046  | `transfusion`     | 同上                                           | 程序化优先；成分候选时调用一次受控 LLM，否则可走既有裁剪提示词路径                  |
| 047  | `transfusion`     | 同上                                           | 程序化输血后 24 小时疗效评价                                                        |
| 048  | `transfusion`     | 同上                                           | 程序化三份文书成分/剂量比对                                                         |
| 049  | `transfusion`     | 同上                                           | 执行器内保守 `data_gap / billing_linkage_source_unavailable`；聚合器无 049 专属分支 |

## 审计基线与范围

- 计划基线提交：`7b5beeb96f397005e44d106933b3d3d18c241dc3`（`7b5beeb96 文档：细化核心质控本地验收与最终客户验收计划`）。
- 冻结前缺陷修复提交：`f4c5ee87d`（047 多次输血时评价时间投影最小修复）与 `31fedfe44`（047 权威评价时间与缺/早时间语义收紧）；冻结对照固定为 `31fedfe44` 的正式 unified 主链，不得倒把 `7b5` 或 `f4c5ee87d` 视为最终冻结基线。
- 审计方式：CodeGraph 状态确认索引最新后，核对 `native_package.py`、`execution.py`、`native_transfusion_execution.py`、`luxian_0609_result_aggregator.py` 与 `canonical_result_finalizer.py` 当前源码。
- 聚合器：`backend/app/services/luxian_0609_result_aggregator.py`，**5,187** 物理行、31 个函数/类定义。
- 聚合器规则文本引用：**138** 次，覆盖 **58** 个唯一规则号；输血 041–048 为 **34** 次、8 个唯一规则号。`LX0609-049` 为 **0** 次。
- 聚合器观察到的公开入口（无 `__all__`）：`safe_luxian_0609_customer_display_facts()`、`aggregate_luxian_0609_results()`、`summarize_luxian_0609_results()`，以及异常类型 `Luxian0609CustomerDisplayFactsError`。阶段 1 不改变这些入口签名。

正式 unified 调用主链为：

```text
规则目录 / native_package 依赖清单
  -> execution.prepare_luxian_0609_execution
  -> Luxian0609ExecutionEngine
  -> executor_registry[executor_key="transfusion"]
  -> execute_luxian_0609_native_transfusion_rules
       -> results + RuleDecision + customer_display_facts + usage attribution
  -> Binding / Canonical finalizer / 通用证据投影
  -> aggregate_luxian_0609_results（仅装配）
```

`LUXIAN_0609_UNIFIED_ENGINE_ENABLED=true` 是正式入口验收的前提。兼容/旧调度仅作为历史兼容路径保留；本阶段既不删除它，也不以它替代 unified 主链冻结。

## 当前重复所有权与目标边界

输血执行器已经拥有规则判定、来源组、受控提示词、原始 `customer_display_facts` 和 `RuleDecision` 生成；聚合器又按规则号重新解释同一事实合同、状态方向和文书来源。这是阶段 1 要消除的重复所有权。

目标边界如下，未在本审计中实施：

| 职责                                                 | 当前所有者                                                                                         | 目标唯一所有者                                                                                                                          | 聚合器删除条件                                                                                                                     |
| ---------------------------------------------------- | -------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------- |
| 041–049 的适用性、状态、原因码、来源组和 `fact_refs` | `native_transfusion_execution.py`（已有）                                                          | 同一输血执行器                                                                                                                          | 不新增任何聚合器判定替代逻辑；冻结输入下终态、原因码和事实来源不变                                                                 |
| 041–049 的安全客户事实字段合同与“事实—状态”一致性    | `luxian_0609_result_aggregator.py` 的 `safe_luxian_0609_customer_display_facts()` 及两个状态校验器 | 新增的输血族映射/投影模块（建议 `luxian_0609/transfusion_result_mapping.py`），由 `canonical_result_finalizer.py` 统一 fail-closed 接收 | Finalizer 能识别 041–049，合法 facts 原样安全投影；非法 facts 只令该规则为 `technical_error`，不得保留临床结论、证据或资料缺口说明 |
| 客户证据坐标的规则专属来源许可                       | 聚合器 `_customer_evidence_from_display_facts()`                                                   | 输血执行器选择真实 `fact_refs`；Binding 校验；公共证据投影按 `fact_refs` 生成坐标                                                       | 同一冻结输入得到去重后完全相同的 `customer_evidence` 坐标集合和数量；不得把内部 ID 放进 `customer_display_facts`                   |
| 客户文案                                             | 现有 `customer_renderer.py`                                                                        | 仍为 Renderer                                                                                                                           | 本阶段不修改 Prompt、阈值、Canonical/API 契约或客户文案口径                                                                        |

`customer_evidence_enrichment.py` 只能承接确有缺口的**通用**证据投影能力；本审计未发现可授权把输血来源白名单塞入该公共层的证据。因此它不是阶段 1 的默认改动点。

## 聚合器中必须迁出的输血专属分支

以下清单按物理分支而非仅按规则号统计。除明确标为共享保留的部分外，阶段 1-B 完成后这些输血内容应从聚合器归零。

| 位置                                     | 直接规则 / 间接分支     | 当前业务事实、状态或证据职责                                                                                         | 目标与删除条件                                                                                                                   |
| ---------------------------------------- | ----------------------- | -------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------- |
| `:275-298`                               | 041、042、043、044、048 | `_TRANSFUSION_SYSTEM_GAP_REASONS` 固定系统资料缺口原因；`system_data_contract_gap` 只能对应 `data_gap`               | 迁至输血映射合同；覆盖合法/非法 facts 与错误状态组合后删除                                                                       |
| `:301-323`                               | **044**（与 003 共享）  | `pretransfusion_assessment_complete/incomplete/missing/time_conflict` 与 `compliant/non_compliant` 的方向一致性      | 只迁出 044 条目；003 的手术规则条目必须留给手术族，不能整函数删除                                                                |
| `:1758-1791`                             | 041、042、043、044、048 | 对系统资料缺口的字段集、原因、`gap_owner` 和文案载荷做白名单过滤                                                     | 输血映射模块验证同一精确合同，Finalizer 接收后再删除                                                                             |
| `:1793-1840`                             | 041、042                | 同意书存在/缺失、签署字段完整/缺失的受控事实和字段白名单                                                             | 迁至输血映射模块；冻结 `verification_kind`/`failure_kind`、计数和字段列表                                                        |
| `:1841-1979`                             | 043；**间接共享 070**   | 九项检查、时间、ABO/Rh/抗体筛查事实；内部 `append_lx070_event_facts()` 还维护 070 的逐笔输血事实                     | 041–049 阶段只能迁出 043 部分；070 的逐笔事件、历史兼容和校验必须保留，或由 070 所属族在独立阶段迁走。不得因共享 `if` 块整段删除 |
| `:1980-2053`                             | 044                     | 输血前评估字段、缺项、申请/输血时间、时差与缺失时间字段                                                              | 迁至输血映射模块并验证 `044` 状态方向；保留共享 003 状态校验                                                                     |
| `:2054-2122`                             | 045、046                | 输血病程记录存在性、完整字段、缺失字段逐记录计数                                                                     | 迁至输血映射模块；保持字段枚举、计数范围和 fail-closed 行为                                                                      |
| `:2123-2143`                             | 047                     | 输血后评价 24 小时阈值、来源、时间与时差                                                                             | 迁至输血映射模块；冻结阈值 `24` 与状态/事实组合                                                                                  |
| `:2144-2198`                             | 048                     | 术中输血不存在、资料/字段缺失、三文书成分/剂量矩阵一致性                                                             | 迁至输血映射模块；冻结三来源矩阵和差异字段白名单                                                                                 |
| `:2199-2226`                             | 044、046、047、048      | `transfusion_requirement_not_documented` 的需求名及已核对来源白名单                                                  | 迁至输血映射模块；冻结 `requirement` 与 `checked_sources` 的精确组合                                                             |
| `:3848-3910`                             | 041、044、047           | 文书 ID 到客户证据的规则专属来源限制：041/047 仅 `bloodtrans_record`，044 为 `blood_application`/`bloodtrans_record` | 改由执行器 `fact_refs` + Binding + 公共投影；坐标集合等价后删除                                                                  |
| `:4141-4159`                             | 045、046                | 仅 `bloodtrans_record` 的 `source_document_ids` 兼容证据回退                                                         | 先用真实 `fact_refs` 覆盖所有冻结形状，证据坐标等价后删除；不能仅因“无规则号”而漏审                                              |
| `:4804-4844`、`:4878-4886`、`:5032-5040` | 间接聚合路径            | 聚合时二次调用输血 facts 过滤器、状态一致性校验并从 raw facts 取证据                                                 | 输血规则由 Finalizer 合同处理后，聚合器只调用通用装配/投影；两个聚合循环均不得遗留输血专属调用                                   |

### 049 的特别结论

049 同属 `transfusion`，但不是“聚合器遗漏了一个迁移分支”：

- `native_transfusion_execution.py:38-43` 将其列为 `_CONSERVATIVE_DATA_GAP_RULE_IDS`，原因为 `billing_linkage_source_unavailable`；
- 其 typed/legacy 执行路径在 `:2228-2235` 与 `:2301-2351` 内已保守生成结果；
- 聚合器没有 `LX0609-049` 文本引用，故阶段 1 的聚合器归零守卫应断言 **041–048 为零**，同时另以原生执行测试冻结 049 的 `data_gap`/技术失败语义。

## 状态、资料与 LLM 基线

原生执行器的统一缺来源语义是：未发现输血事实为 `not_applicable / transfusion_fact_absent`；来源未就绪为 `data_gap / transfusion_source_unavailable`；typed Evidence Session 不完整或失败按执行器既有 `data_gap` 或 `technical_error` 路径处理。049 在可执行情况下仍保守返回上述账单关联资料缺口，不得被迁移改写为临床不合规。

Prompt/LLM 基线（结构迁移必须保持）：

- 041、042、043、047、048 是原生程序化路径，相关冻结资料上的 LLM 调用数应为 `0 -> 0`。
- 044 只有申请理由候选需语义确认时调用 `_044_reason_prompt()`；046 只有成分候选时调用 `_046_component_prompt()`。两者都对返回枚举做本地校验；不可用、调用失败或非法/不确定输出沿既有 `data_gap` 原因码处理。
- 044–046 在确定性路径无法定论且来源投影完整时可落入既有 `_prompt(wrapper, context=...)` 裁剪提示词路径；上下文由该规则 `_RULE_CONTEXT_SOURCES` 构造，上限为 `_MAX_CONTEXT_CHARS = 18000`。
- 每次调用的 `llm_call_count`、prompt/completion/total tokens 与 API 时长由输血执行器累加，并经 `FamilyUsageAttribution` 汇总。迁移不得新增调用、扩大输入、修改 Prompt 或阈值；真实模型基准按计划做至少 10 对交替运行，结构门为中位耗时回归不超过 10%。

## 阶段 1-A/1-B 文件白名单与验收

本次只新增本文件。后续实施的最小生产白名单为：

1. `backend/app/services/luxian_0609/native_transfusion_execution.py`：仅在事实合同承载确实缺失时补齐受控投影/`fact_refs`，不改临床口径或 Prompt。
2. `backend/app/services/luxian_0609/transfusion_result_mapping.py`（新增）：041–049 的唯一安全客户事实合同与状态一致性；不得读取数据库、调用 LLM 或构造第二套证据 DTO。
3. `backend/app/services/luxian_0609/canonical_result_finalizer.py`：接入该合同并统一 fail-closed。
4. `backend/app/services/luxian_0609_result_aggregator.py`：只删除上表的输血专属判断、来源白名单和二次解释，保留通用装配、排序、去重、统计和共享非输血分支。

默认不改 `execution.py`、`native_package.py`、`customer_renderer.py`、数据库、API、前端或 Prompt。只有证据坐标无法通过既有 `fact_refs`/公共投影等价时，才先记录公共边界缺口并单独评审是否扩展白名单。

后续测试白名单：

1. `backend/tests/unit/test_luxian_0609_native_transfusion_execution.py`：041–049 冻结状态、原因码、facts、来源/时间形状、LLM 调用与 049 保守语义。
2. `backend/tests/unit/test_luxian_0609_transfusion_result_mapping.py`（新增）：安全 facts 合同、非法输出 fail-closed、044 状态方向、共享 070/003 不回归。
3. `backend/tests/unit/test_luxian_0609_transfusion_aggregator_ownership.py`（新增）：聚合器中 041–048 专属引用归零，且 049 从未被误计为聚合器所有者。
4. `backend/tests/unit/test_luxian_0609_canonical_result_finalizer.py` 与 `backend/tests/unit/test_luxian_0609_result_aggregator.py`：Finalizer 接入和通用装配回归。

迁移准入与删除验收：

- 冻结相同输入下，逐规则比较 `status`、`reason_code`、`customer_display_facts`、`criterion_results`、`fact_refs` 的语义来源、客户文案和去重后的证据坐标集合；除已批准业务修复外不得漂移。
- 覆盖无输血、多次输血、同意书/输血前检查/记录/疗效评价、来源或时间缺失、关联歧义、语义未知及技术失败；044 和 046 另覆盖受控 LLM 成功、不可用、失败和非法输出。
- 后续正式 worker/API 三入口验收必须确认 `LUXIAN_0609_UNIFIED_ENGINE_ENABLED=true`、结果元数据 `executor_key=transfusion`、没有旧链回退，并核对落库 Canonical 与 API 返回一致。阶段 1-A 的冻结测试只覆盖执行器、Binding/Finalizer、聚合器合同；不能代替这项正式入口验收。
- 共享保护：003 的状态校验和 070 的逐笔检查不计入输血归零；它们须由现有相应回归证明保持可用。

## 风险与待确认项

1. 043 与 070 共用一个事实校验块，044 与 003 共用一个状态校验器；机械删除整个分支会造成跨阶段回归。
2. 045/046 仍有 `source_document_ids` 的证据兼容回退。未先由 `fact_refs` 覆盖固定资料前，不能声称聚合器已无输血证据解释。
3. 049 的“保守资料缺口”是执行器语义，不应被聚合器归零测试掩盖；须单独冻结其状态与原因码。
4. 047 的两次冻结前修复已纳入 `31fedfe44` 基线；阶段 1-A 仅证明执行器、Binding/Finalizer 和聚合器合同冻结，不代表正式 worker/API 三入口已验收。
5. 本文件不代表正式 API 三入口验收、真实模型性能验收或客户验收通过。
