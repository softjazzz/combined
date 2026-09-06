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

- 来源完整且无已实施手术：executor/Binding 的六条均为 `not_applicable / performed_event_absent`，无模型调用；003 的 evaluator 为 `surgery-timeliness-003-ruledecision-v1`，其余五条为 `surgery-gate-ruledecision-shadow-v2`。025 不产生 display facts；但该形状目前**不能完成聚合**。聚合器残余的 025 严格 guard 要求 `implant_not_used` facts，而 gate 正确地不为无手术伪造植入物阴性事实，故抛出 `ValueError: lx0609_025_display_fact_status_mismatch`。冻结测试以精确 `pytest.raises` 记录这个已知缺陷；它不是业务验收通过。
- 已实施手术且受控文本事实明确“未植入”：025 走不同的文本事实分支，最终为 `not_applicable / trigger_absent_complete`，并且必须携带 `verification_kind=implant_not_used` 和 `performed_surgery_confirmed=true`。该分支不能因前一分支缺 facts 而被放宽。
- `surgery_record` 查询异常：六条均为 `technical_error / source_query_error`，不伪造文书坐标。
- 受控 LLM：成功、非法 JSON、经 parser 验证字段完整的合法 `unknown` 与超时分别走真实 executor；非法 JSON 为 `technical_error / model_invalid_output`、超时为 `technical_error / model_transport_error`，合法 `unknown` 为 `data_gap / required_field_missing`，不将模型异常改写为临床不合规。
- 主样本、非法 JSON 与合法 `unknown` 样本均为一次联合调用：`llm_call_count=1`，`prompt_tokens=101`，`total_tokens=112`。超时样本同样记录一次调用，但没有模型 usage 回包，故 `prompt_tokens=completion_tokens=total_tokens=0`；纯无手术与来源异常路径不调用模型。

## HEAD 迁移审计基线（未实施）

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

## 待验证与下一步

本冻结只覆盖固定脱敏资料的本地单元主链，尚未替代三正式 API 入口或客户实际文书定位验收。下一步仅可在新的授权下修改：

1. `backend/app/services/luxian_0609/native_surgery_gate_execution.py`；
2. `backend/app/services/luxian_0609/canonical_result_finalizer.py`；
3. `backend/app/services/luxian_0609_result_aggregator.py`；
4. `backend/tests/unit/test_luxian_0609_surgery_gate_freeze.py`，以及仅在接收边界改动时对应的
   `test_luxian_0609_result_aggregator.py` / `test_luxian_0609_canonical_result_finalizer.py`。

待补的冻结形状不是通过项：003 的超时/权威时间缺失及逐文书坐标；024 的淋巴结未记录；025 的
五字段缺项、实际语义未知、已实施但明确未植入与多事件选中文书；028 的合规、不合规及 24/48
小时边界；031 的术者不合格；033 的缺文书/正文/签名与资料不足。所有形状都须穿过真实
native → Binding → 聚合 → 公共 projector，断言状态、原因、facts、客户文案、完整安全坐标和
LLM 调用/token。

025 的最小修复建议须另立任务，不可混入上述架构迁移：guard 不可仅因 `not_applicable` 就接受
缺失 display facts，也不可要求 executor 补造 `implant_not_used`。仅真实无手术的 typed
`performed_event_absent + raw_facts is None` 可作为精确例外；已实施且明确未植入仍为
`trigger_absent_complete + implant_not_used`，并必须保留其阴性植入物事实。不得放宽所有 NA，
否则会把无手术伪造成“已核验未植入”。
