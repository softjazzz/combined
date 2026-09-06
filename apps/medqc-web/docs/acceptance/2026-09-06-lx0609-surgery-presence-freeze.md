# LX0609 手术存在性（030/032）本地冻结基线

## 状态与范围

状态：**本地生产迁移完成，待主协调审核；未进行客户环境验收。**

- 基线提交：`42c92fc79`
- 规则：`LX0609-030`（手术记录）、`LX0609-032`（手术安全核查表）
- 实际执行器：`surgery_presence`，同步 `native_execution.execute_luxian_0609_native_rules()`
- 本次写入范围：`native_execution.py`、`canonical_result_finalizer.py`、`luxian_0609_result_aggregator.py`、冻结测试与本文档；未新增 mapper、未改阈值/关联算法/文案/API/Prompt。

## 已核对的正式调用链

```text
EvidenceSession（同一 snapshot + materials）
  -> native_execution.execute_luxian_0609_native_rules(decision_rule_ids=030/032)
  -> RuleDecision（surgery-presence-ruledecision-v2，0 LLM）
  -> bind_and_reduce_luxian_0609_rule_decisions
  -> aggregate_luxian_0609_results
       -> project_selected_document_evidence
       -> Canonical Finalizer / Renderer
```

冻结测试不手造 `RuleDecision`，而是由实际 typed native 执行器生成后进入 Binding 和公共投影。为满足 native 影子计划，EvidenceSession 在 030/032 目录资料之外显式读入 `inpat_nondrug_order`、`surgery_application` 两个支持来源。未补入时 runtime provider 找不到快照观察，整个 native 调用安全收敛为 `native_execution_failure`；这不是可用于验收的完整主链形态。

## 冻结矩阵（当前行为）

| 资料形状                                                | 030                                                 | 032                                         | 客户展示事实/文案                                                                                                          | 公共证据坐标集合                                    | LLM |
| ------------------------------------------------------- | --------------------------------------------------- | ------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------- | --- |
| 完整来源、无已实施手术                                  | `not_applicable / trigger_absent_complete`          | 同左                                        | 无 facts；分别为“不要求形成手术记录／手术安全核查表”                                                                       | 空                                                  | 0   |
| 已实施，手术记录与核查表均存在                          | `compliant / requirement_satisfied`                 | 同左                                        | 两条 `surgery_document_present`，target 分别为 `surgery_record`、`surgery_safecheck_record`；文案均为“已确认本次手术具备…” | 单台：030 为手术记录；032 为手术记录 + 核查表       | 0   |
| 已实施，仅有手术记录                                    | `compliant / requirement_satisfied`                 | `non_compliant / required_document_missing` | 030 通过事实；032 为 `surgery_document_missing`                                                                            | 两条均仅手术记录                                    | 0   |
| 两台手术、两份核查表以“手术时间”精确分钟双向关联        | `compliant / requirement_satisfied`                 | 同左                                        | 两条通过事实及原有通过文案                                                                                                 | 030：全部手术记录；032：全部手术记录 + 已关联核查表 | 0   |
| 两台手术、核查表时间分钟重复而无法唯一关联              | `compliant / requirement_satisfied`                 | `data_gap / association_failed`             | 032 无客户 facts；文案为“当前缺少已实施手术与手术安全核查表的单台手术关联信息，暂时无法完成核对”                           | 030：全部手术记录；032：空                          | 0   |
| 取消计划、无可信实际时间                                | `not_applicable / trigger_absent_complete`          | 同左                                        | 无 facts，沿用无实施手术文案                                                                                               | 空                                                  | 0   |
| `surgery_record` 或 `surgery_safecheck_record` 查询异常 | 对应规则保持 `technical_error / executor_exception` | 032 不被关联逻辑覆盖                        | 异常规则无临床 facts，文案为“质控执行未完成”                                                                               | 不伪造异常来源坐标                                  | 0   |

所有冻结形态均断言了 native typed 决策、Binding 后状态/原因码/fact refs、`criterion_results`、Canonical `customer_display_facts`、`findings` 及去重后的公共证据坐标集合。030/032 是确定性同步执行器，测试中 `llm_call_count`、`total_tokens` 均为 0。

## 已实施的职责收口

执行器仍是唯一业务所有者：状态、原因、客户 facts 和选中的 material refs 都在 `native_execution.py` 产生。030 合规选择同一 EvidenceSession 的全部 `surgery_record` 文书；032 合规选择这些手术记录和现有分钟关联确认的核查表；032 缺核查表时只保留手术事件 refs。Binding 校验这些 refs，`project_selected_document_evidence()` 仅按已选 refs 投影公共坐标。

030/032 的安全展示 facts 合同已移入 Finalizer 的输入验证与 fail-closed ownership；typed/reduced 输入若携带非法 facts，只将该规则安全降级为 `technical_error / model_invalid_output`，清除临床 facts/evidence，不由聚合器抛出。聚合器的 `surgery_document_targets` 只保留 029，冻结测试以源码归零断言阻止 030/032 专属 facts 分支回流。Finalizer 不反查或补猜文书。未新增 `surgery_presence_result_mapping.py`：本次移动约 30 行合同校验，单独建模块只会形成不足 250 行的转发壳，不能消除更多所有者。

## 已修复缺陷与剩余风险

1. 多文书定位阻塞已关闭：成功关联的公共证据集合与执行器 selected material refs 完全一致，且不会由 Finalizer/Aggregator 补猜。
2. 032 的 `technical_error` 前态保护保留：关联逻辑只在前态非技术错误时收敛，异常来源不生成临床 facts。
3. 未改变既有分钟关联、状态阈值或客户文案；同一文书含多次跨日期手术的口径不在本轮范围。客户环境真实病例和三入口验收尚未执行。

## 验证记录

聚焦命令（在 `backend` 目录）：

```powershell
py -3.10 -m pytest -q tests/unit/test_luxian_0609_surgery_presence_freeze.py
```

本次迁移后的聚焦命令：

```powershell
py -3.10 -m pytest -q backend/tests/unit/test_luxian_0609_surgery_presence_freeze.py backend/tests/unit/test_luxian_0609_native_execution.py backend/tests/unit/test_luxian_0609_canonical_result_finalizer.py backend/tests/unit/test_luxian_0609_result_aggregator.py backend/tests/unit/test_luxian_0609_decision_binding.py backend/tests/unit/test_luxian_0609_selected_document_evidence.py
```

主协调最终复跑：`505 passed`（5.48s；冻结 9 项 + native/Finalizer/Aggregator/Binding/selected-evidence 影响回归，15 条既有 warning）。迁移后 030 不再参加旧聚合器的通用严格 facts 参数组，改由专用回归完整冻结五个合同形状：普通显式入口的非法 facts 仍抛 `ValueError`；三种 native 输入只令该规则降为 `technical_error/model_invalid_output`，且不泄露临床 facts、证据或私有标记；不携带展示 facts 的结果仍可通过公共入口。没有减少原有覆盖。

生产变更规模：`native_execution.py` 565→628 行（+67/-4），`canonical_result_finalizer.py` 464→512 行（+49/-1），聚合器 4,796→4,792 行（+1/-5），生产代码净增 107 行；没有新增模块或公开接口。聚合器中 030/032 字面引用均为 0。未进行完整前端检查、API 三入口或客户环境验收。
