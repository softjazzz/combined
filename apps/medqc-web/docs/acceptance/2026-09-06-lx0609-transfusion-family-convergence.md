# LX0609 阶段 1-B：输血族 041–048 本地职责收口验收

## 结论

**状态：本地通过，待阶段 1-C 正式三入口与客户真实病例验收。**

本阶段以 `31fedfe44` 的合法业务结果冻结为对照，以 `6b11cb97c` 的失败语义和证据选择修复为直接前置。041–048 已由输血执行器产出 `RuleDecision + fact_refs`，Binding 校验后由公共投影生成客户证据；安全客户事实由输血映射和 Canonical Finalizer 唯一接收。聚合器保留通用装配，不再按 041–048 解释状态、事实或文书来源。049 保持独立的 `pending_definition`，未改变其保守资料缺口语义。

## 修改范围和职责

| 范围                               | 结果                                                                                                      |
| ---------------------------------- | --------------------------------------------------------------------------------------------------------- |
| `transfusion_result_mapping.py`    | 新增 041–048 的唯一安全客户事实合同；不读取资料、不调用 LLM、不生成第二证据 DTO。                         |
| `canonical_result_finalizer.py`    | 接入该合同；非法执行器 facts、双来源冲突和状态冲突隔离为 `technical_error / model_invalid_output`。       |
| `luxian_0609_result_aggregator.py` | 删除 041–048 专属事实/状态/证据解释；技术错误结果不再被通用装配回填缓存 facts 或证据。                    |
| 证据                               | 执行器 `fact_refs` → Binding → `project_selected_document_evidence()`；合法同 ID 多材料行由公共投影保留。 |

公开 API、任务入口、数据库、前端、Renderer、Prompt、阈值与 LLM 调用策略均未修改。003 的共享状态校验、070 的逐笔检查合同和 049 均未迁入本模块。

## 冻结与差分边界

1. **合法 Typed 主链**：041–048 的 `status`、`reason_code`、安全 facts、子结论、客户文案及去重后的证据坐标集合保持冻结等价；045/046 已改用实际参与判定的 `bloodtrans_record`，不再把无关日常病程作为证据。
2. **已批准的非法执行器合同**：不是业务等价目标。非法 facts、非法双来源和事实—状态冲突现 fail-closed 为 `technical_error`，且不保留临床结论、展示 facts 或客户证据；不得误报为 `data_gap` 或 `uncertain`。
3. **无 Typed 合同的旧私有 locator**：不再由聚合器根据 `source_document_ids` 猜测证据。044 等真实坐标由 native→Binding→公共投影测试覆盖；缺少可消费 native/Typed 合同的显式非法 facts 在公共边界抛错。

该三类差分仅涉及错误载荷和旧私有定位回退；不得据此声称全部旧 API 非法输入行为完全等价。

## 证据覆盖

- 041：输血同意书和输血锚点，排除手术同意噪声。
- 044：结构化申请路径的申请单和输血记录；同一业务行的 `application_id` 与 `document_id` 分别精确映射；非结构化路径仅保留实际命中来源。
- 045/046：合规时逐笔选择实际核对的输血记录，缺项时只定位缺项记录；重复业务 ID 的合法多材料行均保留。
- 047：评价所在的实际日常病程与对应输血结束记录；不重新计算时限。
- 043、048：安全 facts 合同、系统资料缺口和非法合同的 fail-closed 路径。
- 049：仍由原生冻结测试覆盖，未被本阶段映射接管。

## 本地验证

从 `backend` 目录执行：

```powershell
py -3.10 -m pytest -q tests/unit/test_luxian_0609_native_transfusion_execution.py tests/unit/test_luxian_0609_native_transfusion_freeze.py tests/unit/test_luxian_0609_transfusion_selected_evidence.py tests/unit/test_luxian_0609_transfusion_result_mapping.py tests/unit/test_luxian_0609_transfusion_aggregator_ownership.py tests/unit/test_luxian_0609_canonical_result_finalizer.py tests/unit/test_luxian_0609_result_aggregator.py tests/unit/test_luxian_0609_mainline_services.py tests/unit/test_luxian_0609_rule_044_policy.py
```

主协调 Agent 独立复跑上述集合中除 `test_luxian_0609_mainline_services.py` 外的八个文件：**570 passed，15 项既有 warning，5.03 秒测试时间**。实现方运行包含主链服务测试的完整上述集合：**737 passed，15 项既有 warning，16.33 秒**。生产文件及新增测试 Ruff 检查通过，相关生产文件 `compileall` 通过；`test_luxian_0609_result_aggregator.py` 全文件 Ruff 仍有 9 条既有 E701，均位于本轮未触及的 030 旧测试行。

## 变更规模

- 聚合器：`6b11cb97c` 对照为 5,187 行，当前 4,796 行，减少 391 行。
- Finalizer：429 → 464 行，增加 35 行。
- 新输血事实合同模块：456 行，承载完整 041–048 安全 facts 职责。
- 生产代码净变化：**+100 行**（统一按含空行的物理行数计）；减少的是聚合器重复所有权，不以行数作为通过理由。
- 聚合器中的 `LX0609-041` 至 `LX0609-048` 业务文本引用均为 **0**；049 未新增引用。
- `aggregate_luxian_0609_results()` 及其他公开接口签名未变。

## 阶段 1-C 待验收

1. 在 `LUXIAN_0609_UNIFIED_ENGINE_ENABLED=true` 下，用同一候选分别走单病历单规则、病历池批量、客户样本验证三个正式入口。
2. 确认三入口实际 `executor_key=transfusion`、无旧链回退，落库 Canonical 与 API 返回一致。
3. 使用客户真实病例复核文书定位、规则状态和证据坐标；真实模型路径按计划做预热后的十对交替性能比较。
4. 客户环境通过前，本阶段只能报告“本地通过、客户待验收”。

实际入口范围遵从现有客户策略：041/042 已排除，049 为 `pending_definition`；本地三入口业务执行验收针对 043–048，另测试未开放规则被拒绝且无派发。不能为了验收临时解禁。真实客户病例和真实模型十对性能比较尚未完成，上述测试耗时不能替代该性能门。
