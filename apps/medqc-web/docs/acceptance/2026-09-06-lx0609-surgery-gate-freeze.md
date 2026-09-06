# LX0609 阶段 2-A.2：surgery_gate 行为冻结

## 范围

- 基线：`42c92fc797eaa1e1ed3d2d3002732446df0a922c`
- executor_key：`surgery_gate`
- 规则：`003`、`024`、`025`、`028`、`031`、`033`
- 本轮白名单：`backend/tests/unit/test_luxian_0609_surgery_gate_freeze.py` 与本文；不修改生产代码、既有测试或共享文档。

## 冻结链路和资料

新增冻结测试从同一 `EvidenceReadSession` 读取固定脱敏行，经真实
`execute_luxian_0609_native_surgery_gate_rules()`、`bind_and_reduce_luxian_0609_rule_decisions()`、
`aggregate_luxian_0609_results()` 与公共 selected-document 投影完成。测试不构造
`RuleDecision`，受控客户端只返回当前 schema 的语义事实，记录 Prompt 次数与 token。

主样本是一台已实施手术：手术结束 `2026-01-01 10:00:00`、记录时间
`2026-01-01 12:00:00`，手术记录、主表、病理/诊断、药嘱、病程与知情同意书均有固定脱敏来源。

| 规则 | 冻结状态 / 原因码                          | 关键冻结项                                   |
| ---- | ------------------------------------------ | -------------------------------------------- |
| 003  | `compliant / requirement_within_threshold` | 只以结束时间计算 2.0 小时；展示手术记录 ID。 |
| 024  | `compliant / requirement_satisfied`        | 联合受控语义事实与手术记录引用。             |
| 025  | `compliant / requirement_satisfied`        | 五字段唯一来自手术记录；病程不替代来源。     |
| 028  | `data_gap / required_field_missing`        | 未给出可验证的实际预防用药区间时不伪造合规。 |
| 031  | `compliant / requirement_satisfied`        | 单台术者与术者签名匹配。                     |
| 033  | `compliant / requirement_satisfied`        | 公共投影坐标为手术记录和知情同意书两份文书。 |

客户文案、`customer_display_facts`、空 `criterion_results`、`fact_refs`、去重后的 033 坐标集合均在冻结测试中断言。

另有两台固定脱敏手术资料：第一台术者已签、第二台术者签名为空。真实 031 executor、Binding 和聚合链收敛为 `data_gap / required_field_missing`，且不因第一台签名覆盖第二台；该路径模型调用与 token 均为 0。028 的 24/48 小时给药界限由既有 `test_luxian_0609_surgery_text_fact_contract.py` 的 Python 事实合同覆盖；本轮主链样本冻结其“无实际给药区间 → data_gap”结果。

## 失败语义与成本冻结

- 来源完整且无已实施手术：executor/Binding 的六条均为 `not_applicable / performed_event_absent`，无模型调用；003 的 evaluator 为 `surgery-timeliness-003-ruledecision-v1`，其余五条为 `surgery-gate-ruledecision-shadow-v2`。025 不产生 display facts，并通过已独立提交的精确例外完成聚合；该例外只接受 typed `performed_event_absent + raw_facts is None`，不会把无手术伪造成“已核验未植入”。
- 已实施手术且受控文本事实明确“未植入”：025 走不同的文本事实分支，最终为 `not_applicable / trigger_absent_complete`，并且必须携带 `verification_kind=implant_not_used` 和 `performed_surgery_confirmed=true`。该分支不能因前一分支缺 facts 而被放宽。
- `surgery_record` 查询异常：六条均为 `technical_error / source_query_error`，不伪造文书坐标。
- 受控 LLM：成功、非法 JSON、经 parser 验证字段完整的合法 `unknown` 与超时分别走真实 executor；非法 JSON 为 `technical_error / model_invalid_output`、超时为 `technical_error / model_transport_error`，合法 `unknown` 为 `data_gap / required_field_missing`，不将模型异常改写为临床不合规。
- 主样本、非法 JSON 与合法 `unknown` 样本均为一次联合调用：`llm_call_count=1`，`prompt_tokens=101`，`total_tokens=112`。超时样本同样记录一次调用，但没有模型 usage 回包，故 `prompt_tokens=completion_tokens=total_tokens=0`；纯无手术与来源异常路径不调用模型。

## HEAD 迁移审计基线

静态审计基于 HEAD `f724cf093`。六条规则在规则合同、registry 与真实 native 执行中均为
`executor_key=surgery_gate`；030/032 的并行工作区改动不属于本族，未计入。以下是聚合器当前
仍直接承载的规则专属业务分支，**不是已完成迁移或通过的验收项**：

| 规则 | 聚合器残余职责                                                     | 预计归零的显式规则引用 |
| ---- | ------------------------------------------------------------------ | ---------------------- |
| 003  | 状态—结束/记录时间 facts 一致性校验、003 facts 投影                | 5                      |
| 024  | 淋巴结处理 `checked_sources` facts 投影                            | 1                      |
| 025  | 严格状态—facts guard、安全 facts、缺项文书坐标及证据 fallback 兼容 | 12                     |
| 028  | 实际给药/停药及 24/48 小时 facts 投影                              | 1                      |
| 031  | 逐台签名 kind、schema 与逐台 facts 投影                            | 3                      |
| 033  | 同意书 facts 投影及手术记录触发文书定位                            | 2                      |

总计 24 处。迁移目标是只令这 24 处聚合器专属引用归零：业务 facts 和实际选中文书
`fact_refs` 仍由 native executor 产生，Binding 仍是 refs 合法性边界，客户坐标仍由已有
公共 selected-document projector 生成。不得新增 fallback、第二事实源或注册层。Renderer 的客户
文案分支，以及 Finalizer 现有的 028 `required_field_missing`、031 `association_failed` 缺口文案，
不属于本轮归零目标。

## 行为等价迁移结果

- 聚合器由 4823 行降为 4255 行；本族 24 处显式规则号引用及 031 的死配置字段合同归零。
- 新增并在兼容复核后定稿为 449 行的 `surgery_gate_result_mapping.py`，完整承载六条规则的客户安全 facts 合同与显式旧入口兼容，不是转发壳。
- executor 负责状态、原因码、业务 facts 与实际选中文书 `fact_refs`；Binding 继续验证引用；现有公共 selected-document projector 统一生成客户证据坐标。
- Aggregator 只调用通用 Finalizer、复制 Canonical 字段并完成装配，不再按本族规则号解释事实或选择文书。
- 旧 aggregate 直调入口曾从已验证的 025 facts 携带手术记录坐标；该行为保留在本族映射模块的显式 legacy 兼容函数中。新主链仍只允许 `fact_refs` 经公共投影产生证据，两者不共享自动回退。
- 003 仅在评价窗口成熟且形成确定结论时选择实际手术记录；024 只选择真正贡献恶性肿瘤/淋巴结判断的手术行；031 保持逐台事实；033 空壳同意书只选择同意书文书。
- 两台手术且知情同意书来源已证明完整为空时，两台手术都是独立的缺失触发事件，因此 033 客户证据按坐标集合保留两份真实手术记录；数组顺序不参与优先级判断。
- 聚合器公开入口的既有严格异常合同保持不变；Finalizer 直接入口遇到非法合同仍安全收敛为 `technical_error`，未混入业务状态。

生产代码结构迁移后的本地回归：572 项聚焦单元测试通过；registry、执行失败语义和执行合同 62 项通过。未新增引擎、fallback、状态机、Prompt、数据库、API DTO 或前端解释逻辑。

## 正式入口边界

003/024/031 为当前客户正式入口启用规则，必须验证 workspace 单条、批量和客户样本三入口一致。025/028 在当前客户配置中为暂停规则，正式 workspace 入口应稳定返回 `not_executed`，同时保留 executor → Binding → 公共投影的独立合同验收。033 当前仍由客户规则集主动排除；历史提交 `d11c13a47` 记录的原因是客户源库不提供手术知情同意书。直接删除排除会把“机构数据源未接入”系统性误判为“缺同意书”，因此不把解除 033 排除混入本次结构迁移。

本族完成口径为：三条客户启用规则完成三入口验收；025/028 验证暂停投影与独立合同；033 完成 native → Binding → 公共投影 → Canonical 独立主链验收，并保留客户数据源保护。只有真实客户链路同时证明“有同意书、完整空查询、来源不可用”三种 readiness 轨迹后，才另立缺陷任务恢复 033 客户入口。

## 本地正式入口验收

`test_luxian_0609_surgery_gate_entry_regression.py` 用同一批受控脱敏资料贯通 workspace 单病历、workspace 批量与客户样本验证三个正式创建入口，经 worker、unified engine、Binding、公共证据投影、保存与读回完成 5 种状态形状验收：无已实施手术、全部合规、已证明缺陷、关键资料缺口、手术数据源异常。

- 5 个场景全部通过，三入口的 `status`、`reason_code`、客户事实和去重证据坐标集合一致。
- 003/024/031 的 `executor_key` 均为 `surgery_gate`，未发生 legacy、LLM fallback 或 pack fallback。
- 只有 024 触发受控语义调用；每次任务的 Prompt、调用数与 token 用量一致。
- 正式 workspace 任务中 025/028 稳定投影为暂停，033 未进入客户 scoped rules，与当前产品配置一致。

验收命令结果：`5 passed`，用时 12.27 秒。
