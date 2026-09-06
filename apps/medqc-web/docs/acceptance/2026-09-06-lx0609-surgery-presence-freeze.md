# LX0609 手术存在性（030/032）本地冻结基线

## 状态与范围

状态：**技术状态覆盖缺陷已最小修复，待主协调审核；证据坐标阻塞仍在。**

- 基线提交：`42c92fc79`
- 规则：`LX0609-030`（手术记录）、`LX0609-032`（手术安全核查表）
- 实际执行器：`surgery_presence`，同步 `native_execution.execute_luxian_0609_native_rules()`
- 本次写入范围：`backend/tests/unit/test_luxian_0609_surgery_presence_freeze.py`、本文档；未改聚合器、Finalizer、执行器或既有测试。

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

| 资料形状                                         | 030                                        | 032                                         | 客户展示事实/文案                                                                                                          | 公共证据坐标集合                              | LLM |
| ------------------------------------------------ | ------------------------------------------ | ------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------- | --------------------------------------------- | --- |
| 完整来源、无已实施手术                           | `not_applicable / trigger_absent_complete` | 同左                                        | 无 facts；分别为“不要求形成手术记录／手术安全核查表”                                                                       | 空                                            | 0   |
| 已实施，手术记录与核查表均存在                   | `compliant / requirement_satisfied`        | 同左                                        | 两条 `surgery_document_present`，target 分别为 `surgery_record`、`surgery_safecheck_record`；文案均为“已确认本次手术具备…” | 单台：030 为手术记录；032 为手术记录 + 核查表 | 0   |
| 已实施，仅有手术记录                             | `compliant / requirement_satisfied`        | `non_compliant / required_document_missing` | 030 通过事实；032 为 `surgery_document_missing`                                                                            | 两条均仅手术记录                              | 0   |
| 两台手术、两份核查表以“手术时间”精确分钟双向关联 | `compliant / requirement_satisfied`        | 同左                                        | 两条通过事实及原有通过文案                                                                                                 | 当前为空（见风险 1）                          | 0   |
| 两台手术、核查表时间分钟重复而无法唯一关联       | `compliant / requirement_satisfied`        | `data_gap / association_failed`             | 032 无客户 facts；文案为“当前缺少已实施手术与手术安全核查表的单台手术关联信息，暂时无法完成核对”                           | 空                                            | 0   |
| 取消计划、无可信实际时间                         | `not_applicable / trigger_absent_complete` | 同左                                        | 无 facts，沿用无实施手术文案                                                                                               | 空                                            | 0   |
| `surgery_record` 查询异常                        | `technical_error / executor_exception`     | `data_gap / association_failed`             | 两条均无 facts；030 为“质控执行未完成”，032 为关联资料不足文案                                                             | 空                                            | 0   |

所有冻结形态均断言了 native typed 决策、Binding 后状态/原因码/fact refs、`criterion_results`、Canonical `customer_display_facts`、`findings` 及去重后的公共证据坐标集合。030/032 是确定性同步执行器，测试中 `llm_call_count`、`total_tokens` 均为 0。

## 聚合器残留与最小迁移判断

已按当前源码复核聚合器 `luxian_0609_result_aggregator.py:3181-3209`：030/032 各一次规则号引用位于 `safe_luxian_0609_customer_display_facts()` 的 `surgery_document_targets`。它校验 executor 给出的安全展示 facts 的 `target_document` 和字段枚举；**不是** `_customer_evidence_from_display_facts()` 的证据来源白名单，也不按时间、标题或 facts 推断文书。

公共证据仍唯一由 Binding 的 `fact_refs` 与 `project_selected_document_evidence()` 投影。当前多文书成功关联虽然判为合规，但 typed decision 绑定的是来源快照 ref，无法化为逐文书 ref，公共投影按“不猜测”合同交付空坐标；这是当前冻结行为，不能在迁移中暗自补猜。

初步最小方案（尚未获生产改动授权）：

1. 将 030/032 的约 30 行安全 facts 合同优先收拢到既有 `native_execution.py` 的小型函数，由通用 Finalizer 调用；原模块已拥有两条 `target_document` 定义和 facts 产生职责。
2. 删除聚合器中这两个 target 键，保留 029 的同族事实校验，避免为两条规则新建仅转发约 30 行的 mapper。
3. 保持 Binding 和公共投影不变；只有 native 能以同一 EvidenceSession 产出合法逐文书 `fact_refs` 时，才可另立最小改动改善多台手术坐标，不能由 Finalizer 或 Aggregator 反查补全。

导入边界初查：`native_execution.py` 已依赖 EvidenceSession/RuleDecision，但当前不依赖 Finalizer 或 Aggregator；Finalizer 已是聚合结果的通用收口层。若 Finalizer 只导入一个无副作用的 native 安全事实校验函数，不形成回环。生产实施前仍须用实际 import 图与聚焦测试复核，且需要主协调再次批准文件白名单。

## 仍存阻塞与已修复缺陷

1. 多台手术的明确关联成功后，030/032 结果的客户证据坐标集合为零；当前合同确保不猜测，但未满足迁移的客户定位门。须由执行器以同一 EvidenceSession 输出合法逐文书 `fact_refs` 后，才可获得定位；不得在 Finalizer 或聚合器反查补来源。
2. `surgery_record` 查询异常时，030 原先保持 `technical_error / executor_exception`，但 `native_execution.py` 的 032 多台关联收敛曾无条件覆盖前态，令 032 变为 `data_gap / association_failed`。该缺陷已在本次独立最小修复中处理：仅当 032 前态不是 `technical_error` 时才应用关联收敛；`surgery_record` 与 `surgery_safecheck_record` 查询异常均回归为 032 的 `technical_error / executor_exception`，且均无临床客户 facts。前者没有坐标；后者按既有公共投影合同保留同一 session 已绑定的手术记录坐标，不伪造核查表坐标。待主协调审核。

本次修复只处理第二项，未改变多台关联、时间匹配或其他状态算法。第一项仍须先明确合法逐文书 refs 的执行器合同与等价坐标目标；在此之前不得删除聚合器安全 facts 校验或宣称 presence 已收口。

## 验证记录

聚焦命令（在 `backend` 目录）：

```powershell
py -3.10 -m pytest -q tests/unit/test_luxian_0609_surgery_presence_freeze.py
```

本次修复后的聚焦命令：

```powershell
py -3.10 -m pytest -q backend/tests/unit/test_luxian_0609_surgery_presence_freeze.py backend/tests/unit/test_luxian_0609_native_execution.py
```

实际结果：`41 passed`（冻结 7 项 + 既有 native 34 项，0.57s；仅有现有应用启动弃用警告）。

主协调独立复核：presence、gate、事实合同及聚合器影响范围合计 `576 passed`（4.19s）。已审查最小状态 guard；仍有上述多文书定位阻塞，不声称聚合器已收口、生产迁移已完成、三入口/API 或客户环境已验收。
